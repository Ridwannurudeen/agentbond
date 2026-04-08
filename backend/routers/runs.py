"""Run execution and replay endpoints."""

import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth import require_operator_key
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


@router.post("", response_model=ExecuteRunResponse)
async def create_run(
    req: ExecuteRunRequest,
    db: AsyncSession = Depends(get_db),
    operator: Operator = Depends(require_operator_key),
):
    """Execute a new agent run via OG SDK. Requires operator API key."""
    # Verify operator owns this agent
    agent = await db.get(Agent, req.agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")
    if agent.operator_id != operator.id:
        raise HTTPException(403, "Agent does not belong to your operator account")

    try:
        result = await execute_run(
            db=db,
            agent_id=req.agent_id,
            user_input=req.user_input,
            user_address=req.user_address,
            simulate_tools=req.simulate_tools,
        )
        return result
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/stream")
async def stream_run(
    req: ExecuteRunRequest,
    db: AsyncSession = Depends(get_db),
    operator: Operator = Depends(require_operator_key),
):
    """Execute an agent run and stream progress via Server-Sent Events.

    Requires operator API key. Each event is formatted as:
        data: {"event": "<type>", "data": {...}}\\n\\n
    """
    # Verify operator owns this agent
    agent = await db.get(Agent, req.agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")
    if agent.operator_id != operator.id:
        raise HTTPException(403, "Agent does not belong to your operator account")

    async def _sse_generator():
        try:
            async for event in execute_run_streaming(
                db=db,
                agent_id=req.agent_id,
                user_input=req.user_input,
                user_address=req.user_address,
                simulate_tools=req.simulate_tools,
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
    """Get run details including proof references."""
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
        "policy_verdict": run.policy_verdict,
        "reason_codes": run.reason_codes,
        "created_at": run.created_at.isoformat() if run.created_at else None,
    }


@router.get("/{run_id}/replay", response_model=ReplayRunResponse)
async def replay_run_endpoint(run_id: str, db: AsyncSession = Depends(get_db)):
    """Re-verify a run independently."""
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
            "settlement_tx": r.settlement_tx,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in runs
    ]
