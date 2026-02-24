"""Objective claim verification against run data and policy."""

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.schema import Run, Policy, Claim, Agent, ClaimStatus
from backend.services.policy_engine import evaluate_policy

logger = logging.getLogger(__name__)

VALID_REASON_CODES = {
    "TOOL_WHITELIST_VIOLATION",
    "VALUE_LIMIT_EXCEEDED",
    "PROHIBITED_TARGET",
    "FREQUENCY_EXCEEDED",
    "STALE_DATA",
    "MODEL_MISMATCH",
}


@dataclass
class VerificationResult:
    valid: bool
    approved: bool
    reason: str
    evidence_hash: str


async def verify_claim(db: AsyncSession, claim_id: int) -> VerificationResult:
    """Verify a claim by re-evaluating the run against its policy."""
    claim = await db.get(Claim, claim_id)
    if not claim:
        return VerificationResult(False, False, "Claim not found", "")

    if claim.status != ClaimStatus.submitted:
        return VerificationResult(False, False, f"Invalid claim status: {claim.status}", "")

    if claim.reason_code not in VALID_REASON_CODES:
        return VerificationResult(True, False, f"Invalid reason code: {claim.reason_code}", "")

    # Fetch the run
    run = await db.get(Run, claim.run_id)
    if not run:
        return VerificationResult(True, False, "Referenced run not found", "")

    # Fetch policy
    policy_result = await db.execute(
        select(Policy).where(
            Policy.agent_id == run.agent_id,
            Policy.status == "active"
        ).order_by(Policy.id.desc()).limit(1)
    )
    policy = policy_result.scalar_one_or_none()
    policy_rules = policy.rules_json if policy else {}

    # Re-evaluate the policy against the run transcript
    run_metadata = {}
    verdict = evaluate_policy(
        transcript=run.transcript_json or [],
        policy=policy_rules,
        run_metadata=run_metadata,
    )

    # Check if the claimed reason code is actually present in violations
    if claim.reason_code in verdict.failed_codes:
        return VerificationResult(
            valid=True,
            approved=True,
            reason=f"Violation confirmed: {claim.reason_code}",
            evidence_hash=verdict.evidence_hash,
        )

    return VerificationResult(
        valid=True,
        approved=False,
        reason=f"Claimed violation {claim.reason_code} not found in re-evaluation",
        evidence_hash=verdict.evidence_hash,
    )
