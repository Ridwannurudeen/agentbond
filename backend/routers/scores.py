"""Reputation score query endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db import get_db
from backend.models.schema import Agent, Run, Claim, ClaimStatus, ReputationSnapshot
from backend.services.reputation import compute_score

router = APIRouter(prefix="/api/scores", tags=["scores"])


@router.get("/{agent_id}")
async def get_score(agent_id: int, db: AsyncSession = Depends(get_db)):
    """Get trust score breakdown for an agent."""
    try:
        result = await compute_score(db, agent_id)
        return result
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.get("/{agent_id}/history")
async def get_score_history(
    agent_id: int, limit: int = 20, db: AsyncSession = Depends(get_db)
):
    """Get historical score snapshots."""
    result = await db.execute(
        select(ReputationSnapshot)
        .where(ReputationSnapshot.agent_id == agent_id)
        .order_by(ReputationSnapshot.id.desc())
        .limit(limit)
    )
    snapshots = result.scalars().all()

    return [
        {
            "id": s.id,
            "score": s.score,
            "total_runs": s.total_runs,
            "violations": s.violations,
            "snapshot_hash": s.snapshot_hash,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in snapshots
    ]


@router.get("")
async def get_dashboard_stats(db: AsyncSession = Depends(get_db)):
    """Global dashboard statistics."""
    agents_count = (await db.execute(select(func.count(Agent.id)))).scalar() or 0
    runs_count = (await db.execute(select(func.count(Run.id)))).scalar() or 0
    claims_count = (await db.execute(select(func.count(Claim.id)))).scalar() or 0
    paid_claims = (
        await db.execute(
            select(func.count(Claim.id)).where(Claim.status == ClaimStatus.paid)
        )
    ).scalar() or 0

    violations_count = (
        await db.execute(
            select(func.count(Run.id)).where(Run.policy_verdict == "fail")
        )
    ).scalar() or 0

    return {
        "total_agents": agents_count,
        "total_runs": runs_count,
        "total_claims": claims_count,
        "paid_claims": paid_claims,
        "total_violations": violations_count,
    }
