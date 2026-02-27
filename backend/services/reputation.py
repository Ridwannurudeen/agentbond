"""Reputation scoring engine for agents.

Score formula (0-100):
  base = 100
  violation_penalty = (violations / total_runs) * 60  (max 60 points lost)
  claim_penalty = (paid_claims / total_runs) * 30     (max 30 points lost)
  recency_bonus = up to 10 points for recent clean runs
"""

import asyncio
import logging
from datetime import datetime, timedelta

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.schema import Agent, Run, Claim, ClaimStatus, ReputationSnapshot

logger = logging.getLogger(__name__)


async def compute_score(db: AsyncSession, agent_id: int) -> dict:
    """Compute trust score for an agent based on run history."""
    agent = await db.get(Agent, agent_id)
    if not agent:
        raise ValueError(f"Agent {agent_id} not found")

    total_runs = agent.total_runs
    violations = agent.violations

    if total_runs == 0:
        return {
            "agent_id": agent_id,
            "score": 100,
            "total_runs": 0,
            "violations": 0,
            "paid_claims": 0,
            "breakdown": {
                "base": 100,
                "violation_penalty": 0,
                "claim_penalty": 0,
                "recency_bonus": 0,
            },
        }

    # Count paid claims
    paid_claims_result = await db.execute(
        select(func.count(Claim.id)).where(
            Claim.agent_id == agent_id,
            Claim.status == ClaimStatus.paid,
        )
    )
    paid_claims = paid_claims_result.scalar() or 0

    # Count recent clean runs (last 7 days)
    week_ago = datetime.utcnow() - timedelta(days=7)
    recent_clean_result = await db.execute(
        select(func.count(Run.id)).where(
            Run.agent_id == agent_id,
            Run.policy_verdict == "pass",
            Run.created_at >= week_ago,
        )
    )
    recent_clean = recent_clean_result.scalar() or 0

    # Compute score
    base = 100
    violation_ratio = violations / total_runs
    violation_penalty = min(violation_ratio * 60, 60)

    claim_ratio = paid_claims / total_runs if total_runs > 0 else 0
    claim_penalty = min(claim_ratio * 30, 30)

    recency_bonus = min(recent_clean * 0.5, 10)

    score = max(0, round(base - violation_penalty - claim_penalty + recency_bonus))
    score = min(100, score)

    breakdown = {
        "base": base,
        "violation_penalty": round(violation_penalty, 2),
        "claim_penalty": round(claim_penalty, 2),
        "recency_bonus": round(recency_bonus, 2),
    }

    return {
        "agent_id": agent_id,
        "score": score,
        "total_runs": total_runs,
        "violations": violations,
        "paid_claims": paid_claims,
        "breakdown": breakdown,
    }


async def snapshot_score(db: AsyncSession, agent_id: int) -> dict:
    """Compute and persist a reputation snapshot, then sync to chain."""
    import hashlib, json

    score_data = await compute_score(db, agent_id)

    snapshot_payload = json.dumps(score_data, sort_keys=True)
    snapshot_hash = hashlib.sha256(snapshot_payload.encode()).hexdigest()

    snapshot = ReputationSnapshot(
        agent_id=agent_id,
        score=score_data["score"],
        total_runs=score_data["total_runs"],
        violations=score_data["violations"],
        snapshot_hash=snapshot_hash,
    )
    db.add(snapshot)

    # Update agent's trust score in DB
    agent = await db.get(Agent, agent_id)
    if agent:
        agent.trust_score = score_data["score"]

    await db.commit()

    # Sync trust score to chain
    from backend.contracts.interface import contracts
    if agent and agent.chain_agent_id is not None and contracts.is_configured():
        try:
            await asyncio.to_thread(
                contracts.update_score,
                agent.chain_agent_id,
                score_data["score"],
                score_data["total_runs"],
                score_data["violations"],
            )
            logger.info(
                f"Agent {agent_id} score synced on-chain: score={score_data['score']}"
            )
        except Exception as e:
            logger.warning(f"On-chain score sync failed (non-fatal): {e}")

    return score_data
