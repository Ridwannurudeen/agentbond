"""Objective claim verification against run data and the snapshotted policy."""

import logging
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.schema import Run, Claim, ClaimStatus
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
    """Verify a claim by re-evaluating the run against its ORIGINAL policy snapshot.

    Uses the policy frozen into the run at execution time, not the currently active
    policy. An operator changing policy after the fact cannot invalidate a valid claim.
    """
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

    # Unverified runs (mock or failed TEE) cannot back a warranty claim
    if run.proof_status != "verified":
        return VerificationResult(
            valid=True,
            approved=False,
            reason=f"Run is not TEE-verified (proof_status={run.proof_status}); not insurable",
            evidence_hash="",
        )

    # Use the SNAPSHOTTED policy frozen at run time — immutable
    policy_rules = run.policy_rules_snapshot or {}

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
