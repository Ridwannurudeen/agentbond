"""Run execution and replay endpoints."""

import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth import require_operator_key, verify_wallet_signature
from backend.db import get_db
from backend.models.schema import Run, Agent, Operator
from backend.schemas import ExecuteRunResponse, RunDetailResponse, ReplayRunResponse, RunListItem
from backend.services.orchestrator import execute_run, execute_run_streaming, replay_run

router = APIRouter(prefix="/api/runs", tags=["runs"])


class ExecuteRunRequest(BaseModel):
    agent_id: int
    user_input: str
    user_address: str | None = None
    simulate_tools: list[dict] | None = None
    # Per-run authorization: the operator wallet signs a message binding this specific
    # run. Without a valid signature the run cannot be anchored to a real identity —
    # "authorized run" stops being UI theater.
    signature: str | None = None
    message: str | None = None


async def _verify_run_authorization(
    req: ExecuteRunRequest,
    operator: Operator,
    agent: Agent,
) -> None:
    """Verify that the operator wallet signed this specific run request.

    Requires:
      - signature + message present
      - signature recovers to the operator's wallet_address
      - message contains the agent_id so signatures cannot be reused across agents
    """
    if not req.signature or not req.message:
        raise HTTPException(
            401,
            "Per-run signature required. Sign the run message with your operator wallet."
        )
    if not verify_wallet_signature(req.message, req.signature, operator.wallet_address):
        raise HTTPException(401, "Run signature does not match operator wallet")
    if str(agent.id) not in req.message and (
        agent.chain_agent_id is None or str(agent.chain_agent_id) not in req.message
    ):
        raise HTTPException(
            401,
            "Run message must reference the agent id — prevents cross-agent signature replay"
        )


@router.post("", response_model=ExecuteRunResponse)
async def create_run(
    req: ExecuteRunRequest,
    db: AsyncSession = Depends(get_db),
    operator: Operator = Depends(require_operator_key),
):
    """Execute a new agent run via OG SDK. Requires operator API key + per-run signature."""
    # Verify operator owns this agent
    agent = await db.get(Agent, req.agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")
    if agent.operator_id != operator.id:
        raise HTTPException(403, "Agent does not belong to your operator account")

    # Verify the operator wallet signed THIS specific run
    await _verify_run_authorization(req, operator, agent)

    try:
        result = await execute_run(
            db=db,
            agent_id=req.agent_id,
            user_input=req.user_input,
            user_address=req.user_address,
            simulate_tools=req.simulate_tools,
            run_signature=req.signature,
            run_message=req.message,
        )
        return result
    except ValueError as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        # OG SDK unavailable while fail-closed is enforced
        raise HTTPException(503, str(e))


@router.post("/stream")
async def stream_run(
    req: ExecuteRunRequest,
    db: AsyncSession = Depends(get_db),
    operator: Operator = Depends(require_operator_key),
):
    """Execute an agent run and stream progress via Server-Sent Events.

    Requires operator API key AND per-run signature. Each event is formatted as:
        data: {"event": "<type>", "data": {...}}\\n\\n
    """
    # Verify operator owns this agent
    agent = await db.get(Agent, req.agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")
    if agent.operator_id != operator.id:
        raise HTTPException(403, "Agent does not belong to your operator account")

    # Verify the operator wallet signed THIS specific run
    await _verify_run_authorization(req, operator, agent)

    async def _sse_generator():
        try:
            async for event in execute_run_streaming(
                db=db,
                agent_id=req.agent_id,
                user_input=req.user_input,
                user_address=req.user_address,
                simulate_tools=req.simulate_tools,
                run_signature=req.signature,
                run_message=req.message,
            ):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'event': 'error', 'data': {'message': str(e)}})}\n\n"

    return StreamingResponse(
        _sse_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/{run_id}", response_model=RunDetailResponse)
async def get_run(run_id: str, db: AsyncSession = Depends(get_db)):
    """Get run details including proof references and execution-bundle snapshot."""
    result = await db.execute(select(Run).where(Run.run_id == run_id))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(404, "Run not found")

    return {
        "id": run.id,
        "run_id": run.run_id,
        "agent_id": run.agent_id,
        "user_address": run.user_address,
        "input_hash": run.input_hash,
        "output_hash": run.output_hash,
        "transcript": run.transcript_json,
        "settlement_tx": run.settlement_tx,
        "verified": run.verified,
        "proof_status": run.proof_status,
        "policy_hash": run.policy_hash_snapshot,
        "model_id": run.model_id_snapshot,
        "policy_verdict": run.policy_verdict,
        "reason_codes": run.reason_codes,
        "created_at": run.created_at.isoformat() if run.created_at else None,
    }


@router.get("/{run_id}/replay", response_model=ReplayRunResponse)
async def replay_run_endpoint(run_id: str, db: AsyncSession = Depends(get_db)):
    """Re-verify a run independently against its original snapshotted policy."""
    try:
        result = await replay_run(db=db, run_id=run_id)
        return result
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.get("", response_model=list[RunListItem])
async def list_runs(
    agent_id: int | None = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """List runs, optionally filtered by agent."""
    query = select(Run).order_by(Run.id.desc()).limit(limit).offset(offset)
    if agent_id:
        query = query.where(Run.agent_id == agent_id)

    result = await db.execute(query)
    runs = result.scalars().all()

    return [
        {
            "id": r.id,
            "run_id": r.run_id,
            "agent_id": r.agent_id,
            "policy_verdict": r.policy_verdict,
            "verified": r.verified,
            "proof_status": r.proof_status,
            "settlement_tx": r.settlement_tx,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in runs
    ]
