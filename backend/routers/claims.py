"""Claim submission and resolution endpoints."""

import asyncio
import hashlib
import json
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from web3 import Web3

from backend.contracts.interface import contracts
from backend.db import get_db
from backend.models.schema import Claim, Run, Agent, ClaimStatus
from backend.services.claim_verifier import verify_claim
from backend.services.reputation import snapshot_score
from backend.services.webhooks import notify_claim_submitted, notify_claim_resolved
from backend.validation import validate_reason_code

router = APIRouter(prefix="/api/claims", tags=["claims"])
logger = logging.getLogger(__name__)


class SubmitClaimRequest(BaseModel):
    run_id: str  # the run's UUID
    agent_id: int
    claimant_address: str
    reason_code: str
    evidence: dict | None = None


@router.post("")
async def submit_claim(req: SubmitClaimRequest, db: AsyncSession = Depends(get_db)):
    """Submit a warranty claim against a run."""
    # Validate reason code
    try:
        validate_reason_code(req.reason_code)
    except ValueError as e:
        raise HTTPException(400, str(e))

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

    # Notify operator of claim submission
    await notify_claim_submitted(
        db, req.agent_id, claim.id, req.reason_code, req.run_id
    )

    # Auto-verify
    verification = await verify_claim(db, claim.id)

    if verification.approved:
        claim.status = ClaimStatus.approved
        claim.payout_amount = 10000000000000000  # 0.01 ETH in wei
        claim.resolved_at = datetime.utcnow()
        await db.commit()

        # Update reputation
        await snapshot_score(db, req.agent_id)

    # Notify operator of resolution
    await notify_claim_resolved(
        db, req.agent_id, claim.id, verification.approved, verification.reason
    )

    # Wire up on-chain: submit + verify + payout
    chain_claim_id = None
    chain_submit_tx = None
    chain_payout_tx = None

    agent = await db.get(Agent, req.agent_id)
    if contracts.is_configured() and agent and agent.chain_agent_id is not None:
        try:
            run_id_bytes = Web3.keccak(text=run.run_id)
            evidence_hash_bytes = bytes.fromhex(evidence_hash)

            chain_claim_id, chain_submit_tx = await asyncio.to_thread(
                contracts.submit_claim,
                run_id_bytes,
                agent.chain_agent_id,
                req.reason_code,
                evidence_hash_bytes,
            )
            claim.chain_claim_id = chain_claim_id
            await db.commit()
            logger.info(f"Claim {claim.id} submitted on-chain: chainClaimId={chain_claim_id} tx={chain_submit_tx}")

            # Verify on-chain
            await asyncio.to_thread(
                contracts.verify_claim, chain_claim_id, verification.approved
            )

            # Execute payout if approved
            if verification.approved:
                chain_payout_tx = await asyncio.to_thread(
                    contracts.execute_payout, chain_claim_id
                )
                claim.status = ClaimStatus.paid
                await db.commit()
                logger.info(f"Claim {claim.id} paid on-chain: tx={chain_payout_tx}")

        except Exception as e:
            logger.warning(f"On-chain claim processing failed (non-fatal): {e}")

    return {
        "claim_id": claim.id,
        "status": claim.status.value,
        "approved": verification.approved,
        "reason": verification.reason,
        "evidence_hash": verification.evidence_hash,
        "chain_claim_id": chain_claim_id,
        "chain_submit_tx": chain_submit_tx,
        "chain_payout_tx": chain_payout_tx,
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
        "chain_claim_id": claim.chain_claim_id,
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
            "chain_claim_id": c.chain_claim_id,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in claims
    ]
