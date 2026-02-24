"""Agent execution orchestrator. Ties together OG SDK, policy engine, and DB."""

import hashlib
import json
import logging
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.schema import Agent, Run, Policy
from backend.services.og_client import OGExecutionClient, RunResult
from backend.services.policy_engine import evaluate_policy
from backend.config import settings

logger = logging.getLogger(__name__)

og_client = OGExecutionClient(private_key=settings.og_private_key)


async def execute_run(
    db: AsyncSession,
    agent_id: int,
    user_input: str,
    user_address: str | None = None,
) -> dict:
    """Execute an agent run: call OG SDK, evaluate policy, store results."""

    # Fetch agent
    agent = await db.get(Agent, agent_id)
    if not agent:
        raise ValueError(f"Agent {agent_id} not found")
    if agent.status != "active":
        raise ValueError(f"Agent {agent_id} is not active (status: {agent.status})")

    # Fetch active policy
    policy_result = await db.execute(
        select(Policy).where(
            Policy.agent_id == agent_id,
            Policy.status == "active"
        ).order_by(Policy.id.desc()).limit(1)
    )
    policy = policy_result.scalar_one_or_none()
    policy_rules = policy.rules_json if policy else {}

    # Determine model from metadata
    model_id = "meta-llama/llama-3.1-8b"  # default

    # Execute via OG SDK
    run_result: RunResult = await og_client.execute_agent_run(
        model_id=model_id,
        user_input=user_input,
        tools=policy_rules.get("allowed_tools"),
    )

    # Evaluate policy
    run_metadata = {
        "declared_model": model_id,
        "executed_model": run_result.model_cid,
    }
    verdict = evaluate_policy(
        transcript=run_result.transcript,
        policy=policy_rules,
        run_metadata=run_metadata,
    )

    # Store run
    run = Run(
        run_id=run_result.run_id,
        agent_id=agent_id,
        user_address=user_address,
        input_hash=run_result.input_hash,
        output_hash=run_result.output_hash,
        transcript_json=run_result.transcript,
        settlement_tx=run_result.settlement_tx,
        policy_verdict="pass" if verdict.passed else "fail",
        reason_codes=verdict.failed_codes if verdict.failed_codes else None,
    )
    db.add(run)

    # Update agent stats
    agent.total_runs += 1
    if not verdict.passed:
        agent.violations += 1

    await db.commit()
    await db.refresh(run)

    return {
        "run_id": run.run_id,
        "agent_id": agent_id,
        "output": run_result.raw_output,
        "policy_verdict": run.policy_verdict,
        "reason_codes": run.reason_codes,
        "settlement_tx": run_result.settlement_tx,
        "evidence_hash": verdict.evidence_hash,
    }


async def replay_run(db: AsyncSession, run_id: str) -> dict:
    """Re-verify a run independently by re-fetching proof and re-evaluating policy."""
    result = await db.execute(select(Run).where(Run.run_id == run_id))
    run = result.scalar_one_or_none()
    if not run:
        raise ValueError(f"Run {run_id} not found")

    # Verify proof via OG
    proof = await og_client.verify_proof(run.run_id, run.settlement_tx or "")

    # Re-evaluate policy
    policy_result = await db.execute(
        select(Policy).where(
            Policy.agent_id == run.agent_id,
            Policy.status == "active"
        ).order_by(Policy.id.desc()).limit(1)
    )
    policy = policy_result.scalar_one_or_none()
    policy_rules = policy.rules_json if policy else {}

    verdict = evaluate_policy(
        transcript=run.transcript_json or [],
        policy=policy_rules,
    )

    return {
        "run_id": run.run_id,
        "proof_valid": proof.valid,
        "input_hash_match": proof.input_hash_match,
        "output_hash_match": proof.output_hash_match,
        "policy_verdict": "pass" if verdict.passed else "fail",
        "reason_codes": verdict.failed_codes,
        "evidence_hash": verdict.evidence_hash,
        "original_verdict": run.policy_verdict,
    }
