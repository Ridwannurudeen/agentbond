"""Agent execution orchestrator. Ties together OG SDK, policy engine, and DB."""

import hashlib
import json
import logging
import time
import uuid
from datetime import datetime
from typing import AsyncGenerator, Awaitable, Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.schema import Agent, Run, Policy
from backend.services.og_client import OGExecutionClient, RunResult, DEFAULT_MODEL
from backend.services.policy_engine import evaluate_policy
from backend.services.memory import build_memory_context, store_run_memory
from backend.config import settings
from backend.metrics import RUNS_TOTAL, RUN_DURATION

logger = logging.getLogger(__name__)

og_client = OGExecutionClient(
    private_key=settings.og_private_key,
    require_verified=settings.require_verified_execution,
)


def _hash_policy_rules(rules: dict) -> str:
    """Deterministic hash of a policy body — binds replay to the exact rules at run time."""
    serialized = json.dumps(rules or {}, sort_keys=True, separators=(",", ":"))
    return "0x" + hashlib.sha256(serialized.encode()).hexdigest()


async def _execute_run_core(
    db: AsyncSession,
    agent_id: int,
    user_input: str,
    user_address: str | None = None,
    simulate_tools: list[dict] | None = None,
    run_signature: str | None = None,
    run_message: str | None = None,
    on_event: "Callable[[str, dict], Awaitable[None]] | None" = None,
) -> dict:
    """Shared core logic for execute_run and execute_run_streaming.

    Snapshots the full execution bundle (policy hash, policy body, agent version,
    model ID, allowed tools, operator signature) onto the Run record so replay and
    claim verification cannot be rewritten by later policy changes.

    If *on_event* is provided, it is called at each milestone with
    (event_name, event_data) so the streaming wrapper can yield SSE events.
    """

    async def _emit(event: str, data: dict) -> None:
        if on_event is not None:
            await on_event(event, data)

    # Fetch agent
    agent = await db.get(Agent, agent_id)
    if not agent:
        raise ValueError(f"Agent {agent_id} not found")
    status_val = agent.status.value if hasattr(agent.status, 'value') else str(agent.status)
    if status_val != "active":
        raise ValueError(f"Agent {agent_id} is not active (status: {status_val})")

    # Fetch active policy — snapshot it immediately
    policy_result = await db.execute(
        select(Policy).where(
            Policy.agent_id == agent_id,
            Policy.status == "active"
        ).order_by(Policy.id.desc()).limit(1)
    )
    policy = policy_result.scalar_one_or_none()
    policy_rules = policy.rules_json if policy else {}
    policy_hash = _hash_policy_rules(policy_rules)
    policy_id_snap = policy.id if policy else None
    allowed_tools_snap = policy_rules.get("allowed_tools")
    agent_version_snap = agent.active_version

    # Determine model from metadata or use default
    model_id = DEFAULT_MODEL

    # Build memory context from prior run history and inject into prompt
    memory_block = await build_memory_context(db, agent_id)
    await _emit("memory_loaded", {
        "has_context": bool(memory_block),
        "agent_id": agent_id,
    })

    augmented_input = (
        f"{memory_block}\n\n## Current Request\n{user_input}"
        if memory_block
        else user_input
    )

    await _emit("inference_start", {"model": model_id, "agent_id": agent_id})

    # Execute via OG SDK (timed for Prometheus). Fail closed: RuntimeError propagates.
    run_start = time.perf_counter()
    run_result: RunResult = await og_client.execute_agent_run(
        model_id=model_id,
        user_input=augmented_input,
        tools=allowed_tools_snap,
        simulate_tools=simulate_tools,
    )
    RUN_DURATION.observe(time.perf_counter() - run_start)

    await _emit("inference_done", {
        "output": run_result.raw_output,
        "settlement_tx": run_result.settlement_tx,
    })

    # Evaluate policy against the SNAPSHOT (not any later state)
    run_metadata = {
        "declared_model": model_id,
        "executed_model": run_result.model_cid,
    }
    verdict = evaluate_policy(
        transcript=run_result.transcript,
        policy=policy_rules,
        run_metadata=run_metadata,
    )

    await _emit("policy_evaluated", {
        "verdict": "pass" if verdict.passed else "fail",
        "reason_codes": verdict.failed_codes if verdict.failed_codes else [],
    })

    # Derive proof_status: verified requires both TEE attestation and a settlement tx
    proof_status = "verified" if run_result.verified else "unverified"

    # Store run with full execution-bundle snapshot
    run = Run(
        run_id=run_result.run_id,
        agent_id=agent_id,
        user_address=user_address,
        input_hash=run_result.input_hash,
        output_hash=run_result.output_hash,
        transcript_json=run_result.transcript,
        settlement_tx=run_result.settlement_tx,
        verified=run_result.verified,
        proof_status=proof_status,
        # Execution-bundle snapshot — immutable after this commit
        policy_id_snapshot=policy_id_snap,
        policy_hash_snapshot=policy_hash,
        policy_rules_snapshot=policy_rules,
        agent_version_snapshot=agent_version_snap,
        model_id_snapshot=run_result.model_cid or model_id,
        allowed_tools_snapshot=allowed_tools_snap,
        run_signature=run_signature,
        run_message=run_message,
        policy_verdict="pass" if verdict.passed else "fail",
        reason_codes=verdict.failed_codes if verdict.failed_codes else None,
    )
    db.add(run)

    # Update agent stats
    agent.total_runs += 1
    if not verdict.passed:
        agent.violations += 1

    # Store memory record for this run
    await store_run_memory(
        db=db,
        agent_id=agent_id,
        run_id=run_result.run_id,
        verdict="pass" if verdict.passed else "fail",
        reason_codes=verdict.failed_codes if verdict.failed_codes else None,
        trust_score=agent.trust_score,
    )

    await db.commit()
    await db.refresh(run)

    RUNS_TOTAL.labels(verdict=run.policy_verdict).inc()

    return {
        "run_id": run.run_id,
        "agent_id": agent_id,
        "output": run_result.raw_output,
        "policy_verdict": run.policy_verdict,
        "reason_codes": run.reason_codes,
        "settlement_tx": run_result.settlement_tx,
        "verified": run_result.verified,
        "proof_status": proof_status,
        "policy_hash": policy_hash,
        "evidence_hash": verdict.evidence_hash,
    }


async def execute_run(
    db: AsyncSession,
    agent_id: int,
    user_input: str,
    user_address: str | None = None,
    simulate_tools: list[dict] | None = None,
    run_signature: str | None = None,
    run_message: str | None = None,
) -> dict:
    """Execute an agent run: call OG SDK, evaluate policy, store results."""
    return await _execute_run_core(
        db=db,
        agent_id=agent_id,
        user_input=user_input,
        user_address=user_address,
        simulate_tools=simulate_tools,
        run_signature=run_signature,
        run_message=run_message,
    )


async def execute_run_streaming(
    db: AsyncSession,
    agent_id: int,
    user_input: str,
    user_address: str | None = None,
    simulate_tools: list[dict] | None = None,
    run_signature: str | None = None,
    run_message: str | None = None,
) -> AsyncGenerator[dict, None]:
    """Streaming version of execute_run — yields progress events as SSE dicts.

    Yields dicts with keys: event (str), data (dict).
    """
    events: list[dict] = []

    async def _collect_event(event: str, data: dict) -> None:
        events.append({"event": event, "data": data})

    try:
        result = await _execute_run_core(
            db=db,
            agent_id=agent_id,
            user_input=user_input,
            user_address=user_address,
            simulate_tools=simulate_tools,
            run_signature=run_signature,
            run_message=run_message,
            on_event=_collect_event,
        )
    except ValueError as e:
        yield {"event": "error", "data": {"message": str(e)}}
        return

    for ev in events:
        yield ev

    yield {"event": "complete", "data": result}


async def replay_run(db: AsyncSession, run_id: str) -> dict:
    """Re-verify a run independently against its ORIGINAL snapshotted policy.

    Uses the execution bundle frozen at run time (policy_rules_snapshot) rather than
    the currently active policy, so operators cannot rewrite history by changing
    policies after a violation.
    """
    result = await db.execute(select(Run).where(Run.run_id == run_id))
    run = result.scalar_one_or_none()
    if not run:
        raise ValueError(f"Run {run_id} not found")

    # Verify proof via OG
    proof = await og_client.verify_proof(run.run_id, run.settlement_tx or "")

    # Use the SNAPSHOTTED policy — frozen at execution time, immutable
    policy_rules = run.policy_rules_snapshot or {}

    verdict = evaluate_policy(
        transcript=run.transcript_json or [],
        policy=policy_rules,
    )

    return {
        "run_id": run.run_id,
        "proof_valid": proof.valid,
        "proof_status": run.proof_status,
        "input_hash_match": proof.input_hash_match,
        "output_hash_match": proof.output_hash_match,
        "policy_verdict": "pass" if verdict.passed else "fail",
        "reason_codes": verdict.failed_codes,
        "evidence_hash": verdict.evidence_hash,
        "original_verdict": run.policy_verdict,
        "policy_hash": run.policy_hash_snapshot,
        "model_id": run.model_id_snapshot,
    }
