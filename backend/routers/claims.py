"""Claim submission and resolution endpoints."""

import hashlib
import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db import get_db
from backend.models.schema import Claim, Run, Agent, ClaimStatus
from backend.services.claim_verifier import verify_claim
from backend.services.reputation import snapshot_score

router = APIRouter(prefix="/api/claims", tags=["claims"])


class SubmitClaimRequest(BaseModel):
    run_id: str  # the run's UUID
    agent_id: int
    claimant_address: str
    reason_code: str
    evidence: dict | None = None


@router.post("")
async def submit_claim(req: SubmitClaimRequest, db: AsyncSession = Depends(get_db)):
    """Submit a warranty claim against a run."""
    # Validate run exists
    result = await db.execute(select(Run).where(Run.run_id == req.run_id))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(404, "Run not found")

    # Check no existing claim for this run
    existing = await db.execute(
        select(Claim).where(Claim.run_id == run.id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(409, "Claim already exists for this run")

    # Compute evidence hash
    evidence_data = json.dumps(req.evidence or {}, sort_keys=True)
    evidence_hash = hashlib.sha256(evidence_data.encode()).hexdigest()

    claim = Claim(
        run_id=run.id,
        agent_id=req.agent_id,
        claimant_address=req.claimant_address,
        reason_code=req.reason_code,
        evidence_hash=evidence_hash,
        status=ClaimStatus.submitted,
    )
    db.add(claim)
    await db.commit()
    await db.refresh(claim)

    # Auto-verify
    verification = await verify_claim(db, claim.id)

    if verification.approved:
        claim.status = ClaimStatus.approved
        claim.payout_amount = 10000000000000000  # 0.01 ETH in wei
        claim.resolved_at = datetime.utcnow()
        await db.commit()

        # Update reputation
        await snapshot_score(db, req.agent_id)

    return {
        "claim_id": claim.id,
        "status": claim.status.value,
        "approved": verification.approved,
        "reason": verification.reason,
        "evidence_hash": verification.evidence_hash,
    }


@router.get("/{claim_id}")
async def get_claim(claim_id: int, db: AsyncSession = Depends(get_db)):
    """Get claim status and details."""
    claim = await db.get(Claim, claim_id)
    if not claim:
        raise HTTPException(404, "Claim not found")

    return {
        "id": claim.id,
        "run_id": claim.run_id,
        "agent_id": claim.agent_id,
        "claimant_address": claim.claimant_address,
        "reason_code": claim.reason_code,
        "evidence_hash": claim.evidence_hash,
        "status": claim.status.value,
        "payout_amount": str(claim.payout_amount) if claim.payout_amount else None,
        "resolved_at": claim.resolved_at.isoformat() if claim.resolved_at else None,
        "created_at": claim.created_at.isoformat() if claim.created_at else None,
    }


@router.get("")
async def list_claims(
    agent_id: int | None = None,
    status: str | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """List claims with optional filters."""
    query = select(Claim).order_by(Claim.id.desc()).limit(limit)
    if agent_id:
        query = query.where(Claim.agent_id == agent_id)
    if status:
        query = query.where(Claim.status == status)

    result = await db.execute(query)
    claims = result.scalars().all()

    return [
        {
            "id": c.id,
            "agent_id": c.agent_id,
            "reason_code": c.reason_code,
            "status": c.status.value,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in claims
    ]
