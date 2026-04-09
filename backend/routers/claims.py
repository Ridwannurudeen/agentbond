"""Claim submission and resolution endpoints."""

import asyncio
import hashlib
import json
import logging
from datetime import datetime, date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from web3 import Web3

from backend.auth import verify_wallet_signature
from backend.contracts.interface import contracts
from backend.db import get_db
from sqlalchemy.orm import selectinload

from backend.models.schema import Claim, Run, Agent, ClaimStatus
from backend.services.claim_verifier import verify_claim
from backend.services.reputation import snapshot_score
from backend.services.webhooks import notify_claim_submitted, notify_claim_resolved
from backend.schemas import SubmitClaimResponse, ClaimDetailResponse, ClaimListItem
from backend.validation import validate_reason_code
from backend.metrics import CLAIMS_TOTAL

DAILY_CLAIM_LIMIT = 5  # max claims per claimant address per UTC day

router = APIRouter(prefix="/api/claims", tags=["claims"])
logger = logging.getLogger(__name__)


class SubmitClaimRequest(BaseModel):
    run_id: str  # the run's UUID (agent_id is DERIVED from this, never trusted from the request)
    claimant_address: str
    reason_code: str
    evidence: dict | None = None
    signature: str  # EIP-191 wallet signature proving claimant_address ownership
    message: str    # the signed message
    # Optional: the user's on-chain claim submission tx hash. If present, the user already
    # submitted the claim on-chain via MetaMask and this is the audit receipt. The backend
    # never submits claims as itself — on-chain claimant is always the real user wallet.
    chain_claim_id: int | None = None
    chain_submit_tx: str | None = None


@router.post("", response_model=SubmitClaimResponse)
async def submit_claim(req: SubmitClaimRequest, db: AsyncSession = Depends(get_db)):
    """Submit a warranty claim against a run.

    Trust model:
    - claimant_address must prove ownership via wallet signature
    - agent_id is DERIVED from the referenced run, never trusted from the request
    - On-chain claim is submitted by the user's wallet (frontend / MetaMask), not the
      backend — the resolver only verifies and executes payout.
    """
    # Verify wallet signature — claimant must prove address ownership
    if not verify_wallet_signature(req.message, req.signature, req.claimant_address):
        raise HTTPException(401, "Signature verification failed: claimant address ownership not proven")

    # Validate reason code
    try:
        validate_reason_code(req.reason_code)
    except ValueError as e:
        raise HTTPException(400, str(e))

    # Circuit breaker: per-claimant daily limit
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    daily_count_result = await db.execute(
        select(func.count(Claim.id)).where(
            Claim.claimant_address == req.claimant_address,
            Claim.created_at >= today_start,
        )
    )
    daily_count = daily_count_result.scalar_one()
    if daily_count >= DAILY_CLAIM_LIMIT:
        raise HTTPException(
            429,
            f"Daily claim limit reached. Maximum {DAILY_CLAIM_LIMIT} claims per address per day.",
        )

    # Validate run exists — and derive agent_id from it (never trust req)
    result = await db.execute(select(Run).where(Run.run_id == req.run_id))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(404, "Run not found")
    agent_id = run.agent_id  # authoritative source

    # Unverified runs cannot back a claim — trust model requires TEE attestation
    if run.proof_status != "verified":
        raise HTTPException(
            400,
            f"Run is not TEE-verified (proof_status={run.proof_status}); not insurable"
        )

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
        agent_id=agent_id,
        claimant_address=req.claimant_address,
        reason_code=req.reason_code,
        evidence_hash=evidence_hash,
        status=ClaimStatus.submitted,
        chain_claim_id=req.chain_claim_id,  # recorded from user's on-chain tx
    )
    db.add(claim)
    await db.commit()
    await db.refresh(claim)

    CLAIMS_TOTAL.labels(status="submitted").inc()

    # Notify operator of claim submission
    await notify_claim_submitted(
        db, agent_id, claim.id, req.reason_code, req.run_id
    )

    # Auto-verify against the snapshotted policy
    verification = await verify_claim(db, claim.id)

    if verification.approved:
        claim.status = ClaimStatus.approved
        claim.payout_amount = 10000000000000000  # 0.01 ETH in wei
        claim.resolved_at = datetime.utcnow()
        await db.commit()
        CLAIMS_TOTAL.labels(status="approved").inc()

        # Update reputation
        await snapshot_score(db, agent_id)

    if not verification.approved:
        CLAIMS_TOTAL.labels(status="rejected").inc()

    # Notify operator of resolution
    await notify_claim_resolved(
        db, agent_id, claim.id, verification.approved, verification.reason
    )

    # Resolver-side on-chain actions (verify + payout). The resolver wallet only acts
    # on an already-submitted user claim — it never submits the claim itself, so the
    # on-chain `claimant` is always the real user, not the backend.
    chain_payout_tx = None

    agent = await db.get(Agent, agent_id)
    if (
        contracts.is_configured()
        and agent
        and agent.chain_agent_id is not None
        and req.chain_claim_id is not None
    ):
        try:
            # Verify on-chain using the user's claim ID
            await asyncio.to_thread(
                contracts.verify_claim, req.chain_claim_id, verification.approved
            )

            # Execute payout to the user if approved
            if verification.approved:
                chain_payout_tx = await asyncio.to_thread(
                    contracts.execute_payout, req.chain_claim_id
                )
                claim.status = ClaimStatus.paid
                await db.commit()
                logger.info(f"Claim {claim.id} paid on-chain: tx={chain_payout_tx}")

        except Exception as e:
            logger.warning(f"On-chain claim resolution failed (non-fatal): {e}")

    return {
        "claim_id": claim.id,
        "status": claim.status.value,
        "approved": verification.approved,
        "reason": verification.reason,
        "evidence_hash": verification.evidence_hash,
        "chain_claim_id": req.chain_claim_id,
        "chain_submit_tx": req.chain_submit_tx,
        "chain_payout_tx": chain_payout_tx,
    }


@router.get("/{claim_id}", response_model=ClaimDetailResponse)
async def get_claim(claim_id: int, db: AsyncSession = Depends(get_db)):
    """Get claim status and details."""
    result = await db.execute(
        select(Claim).options(selectinload(Claim.run)).where(Claim.id == claim_id)
    )
    claim = result.scalar_one_or_none()
    if not claim:
        raise HTTPException(404, "Claim not found")

    return {
        "id": claim.id,
        "run_id": claim.run.run_id if claim.run else None,  # UUID string
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


@router.get("", response_model=list[ClaimListItem])
async def list_claims(
    agent_id: int | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """List claims with optional filters."""
    query = (
        select(Claim)
        .options(selectinload(Claim.run))
        .order_by(Claim.id.desc())
        .limit(limit)
        .offset(offset)
    )
    if agent_id:
        query = query.where(Claim.agent_id == agent_id)
    if status:
        query = query.where(Claim.status == status)

    result = await db.execute(query)
    claims = result.scalars().all()

    return [
        {
            "id": c.id,
            "run_id": c.run.run_id if c.run else None,  # UUID string for frontend links
            "agent_id": c.agent_id,
            "reason_code": c.reason_code,
            "status": c.status.value,
            "chain_claim_id": c.chain_claim_id,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in claims
    ]
