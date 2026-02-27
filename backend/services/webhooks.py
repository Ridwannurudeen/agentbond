"""Webhook notification service — delivers events to operator endpoints.

Features:
- HMAC-SHA256 payload signing (X-AgentBond-Signature: sha256=<hex>)
- Up to 3 delivery attempts with exponential backoff (0s / 2s / 8s)
- Per-attempt audit log written to webhook_deliveries table
- Non-blocking: fire_and_forget() schedules delivery as a background asyncio task
"""

import asyncio
import hashlib
import hmac
import json
import logging
import time
from datetime import datetime

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.schema import Agent, Operator, WebhookDelivery
from backend.metrics import WEBHOOK_DELIVERIES_TOTAL, WEBHOOK_DURATION

logger = logging.getLogger(__name__)

WEBHOOK_TIMEOUT = 10.0  # seconds per attempt
MAX_RETRIES = 3
RETRY_DELAYS = [0, 2, 8]  # seconds before each attempt


# ---------------------------------------------------------------------------
# Signing
# ---------------------------------------------------------------------------

def _sign_payload(payload_bytes: bytes, secret: str) -> str:
    """Return HMAC-SHA256 hex digest of payload_bytes keyed with secret."""
    return hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()


# ---------------------------------------------------------------------------
# Single delivery attempt
# ---------------------------------------------------------------------------

async def _deliver_once(
    db: AsyncSession,
    operator_id: int,
    agent_id: int | None,
    event_type: str,
    webhook_url: str,
    payload_bytes: bytes,
    payload_dict: dict,
    secret: str | None,
    attempt: int,
) -> bool:
    """POST payload to webhook_url once. Logs the attempt. Returns True on 2xx."""
    headers = {"Content-Type": "application/json"}
    if secret:
        sig = _sign_payload(payload_bytes, secret)
        headers["X-AgentBond-Signature"] = f"sha256={sig}"

    start = time.monotonic()
    status_code: int | None = None
    error_message: str | None = None
    success = False

    try:
        async with httpx.AsyncClient(timeout=WEBHOOK_TIMEOUT) as client:
            response = await client.post(
                webhook_url, content=payload_bytes, headers=headers
            )
            status_code = response.status_code
            success = status_code < 300
    except Exception as exc:
        error_message = str(exc)

    duration_ms = int((time.monotonic() - start) * 1000)

    # Record Prometheus metrics
    WEBHOOK_DELIVERIES_TOTAL.labels(event_type=event_type, success=str(success).lower()).inc()
    WEBHOOK_DURATION.labels(event_type=event_type).observe(duration_ms / 1000)

    # Write audit record
    delivery = WebhookDelivery(
        operator_id=operator_id,
        agent_id=agent_id,
        event_type=event_type,
        webhook_url=webhook_url,
        payload_json=payload_dict,
        attempt=attempt,
        status_code=status_code,
        success=success,
        error_message=error_message,
        duration_ms=duration_ms,
    )
    db.add(delivery)
    await db.commit()

    if success:
        logger.info(
            "Webhook OK: %s agent=%s attempt=%d -> %s (%d) %dms",
            event_type, agent_id, attempt, webhook_url, status_code, duration_ms,
        )
    else:
        logger.warning(
            "Webhook FAIL: %s agent=%s attempt=%d -> %s status=%s err=%s",
            event_type, agent_id, attempt, webhook_url, status_code, error_message,
        )

    return success


# ---------------------------------------------------------------------------
# Core delivery with retry
# ---------------------------------------------------------------------------

async def notify_operator(
    db: AsyncSession,
    agent_id: int,
    event_type: str,
    payload: dict,
) -> bool:
    """Deliver an event to the operator of agent_id. Retries up to MAX_RETRIES times.

    Returns True if any attempt succeeded.
    """
    agent = await db.get(Agent, agent_id)
    if not agent:
        return False

    operator = await db.get(Operator, agent.operator_id)
    if not operator or not operator.webhook_url:
        return False

    full_payload = {
        "event": event_type,
        "agent_id": agent_id,
        "operator_id": operator.id,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "data": payload,
    }
    # Serialize once so signature and body are identical
    payload_bytes = json.dumps(full_payload, separators=(",", ":")).encode()

    for attempt, delay in enumerate(RETRY_DELAYS[:MAX_RETRIES], start=1):
        if delay > 0:
            await asyncio.sleep(delay)

        success = await _deliver_once(
            db=db,
            operator_id=operator.id,
            agent_id=agent_id,
            event_type=event_type,
            webhook_url=operator.webhook_url,
            payload_bytes=payload_bytes,
            payload_dict=full_payload,
            secret=operator.api_key,
            attempt=attempt,
        )

        if success:
            return True

    logger.warning(
        "Webhook exhausted %d attempts: %s for agent %d", MAX_RETRIES, event_type, agent_id
    )
    return False


# ---------------------------------------------------------------------------
# Background / fire-and-forget
# ---------------------------------------------------------------------------

async def _background_notify(agent_id: int, event_type: str, payload: dict) -> None:
    """Creates its own DB session so it can run outside the request lifecycle."""
    from backend.db import async_session  # local import avoids circular at module load

    async with async_session() as db:
        await notify_operator(db, agent_id, event_type, payload)


def fire_and_forget(agent_id: int, event_type: str, payload: dict) -> None:
    """Schedule webhook delivery as an asyncio background task (non-blocking)."""
    asyncio.create_task(_background_notify(agent_id, event_type, payload))


# ---------------------------------------------------------------------------
# Public helpers (backward-compatible signatures)
# ---------------------------------------------------------------------------

async def notify_claim_submitted(
    db: AsyncSession, agent_id: int, claim_id: int, reason_code: str, run_id: str
) -> None:
    fire_and_forget(agent_id, "claim.submitted", {
        "claim_id": claim_id,
        "reason_code": reason_code,
        "run_id": run_id,
    })


async def notify_claim_resolved(
    db: AsyncSession, agent_id: int, claim_id: int, approved: bool, reason: str
) -> None:
    fire_and_forget(agent_id, "claim.resolved", {
        "claim_id": claim_id,
        "approved": approved,
        "reason": reason,
    })


async def notify_score_changed(
    db: AsyncSession, agent_id: int, old_score: int, new_score: int
) -> None:
    if old_score != new_score:
        fire_and_forget(agent_id, "score.changed", {
            "old_score": old_score,
            "new_score": new_score,
        })
