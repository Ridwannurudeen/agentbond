"""Webhook notification service for operators."""

import logging
from datetime import datetime

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.schema import Agent, Operator

logger = logging.getLogger(__name__)

WEBHOOK_TIMEOUT = 5.0  # seconds


async def notify_operator(
    db: AsyncSession,
    agent_id: int,
    event_type: str,
    payload: dict,
) -> bool:
    """Send a webhook notification to the operator of an agent.

    Returns True if delivered successfully, False otherwise.
    """
    agent = await db.get(Agent, agent_id)
    if not agent:
        return False

    operator = await db.get(Operator, agent.operator_id)
    if not operator or not operator.webhook_url:
        return False

    webhook_data = {
        "event": event_type,
        "agent_id": agent_id,
        "operator_id": operator.id,
        "timestamp": datetime.utcnow().isoformat(),
        "data": payload,
    }

    try:
        async with httpx.AsyncClient(timeout=WEBHOOK_TIMEOUT) as client:
            headers = {"Content-Type": "application/json"}
            if operator.api_key:
                headers["X-AgentBond-Signature"] = operator.api_key

            response = await client.post(
                operator.webhook_url,
                json=webhook_data,
                headers=headers,
            )
            if response.status_code < 300:
                logger.info(
                    f"Webhook delivered: {event_type} for agent {agent_id} "
                    f"-> {operator.webhook_url} ({response.status_code})"
                )
                return True
            else:
                logger.warning(
                    f"Webhook failed: {event_type} for agent {agent_id} "
                    f"-> {operator.webhook_url} ({response.status_code})"
                )
                return False
    except Exception as e:
        logger.warning(f"Webhook error for agent {agent_id}: {e}")
        return False


async def notify_claim_submitted(
    db: AsyncSession, agent_id: int, claim_id: int, reason_code: str, run_id: str
):
    await notify_operator(db, agent_id, "claim.submitted", {
        "claim_id": claim_id,
        "reason_code": reason_code,
        "run_id": run_id,
    })


async def notify_claim_resolved(
    db: AsyncSession, agent_id: int, claim_id: int, approved: bool, reason: str
):
    await notify_operator(db, agent_id, "claim.resolved", {
        "claim_id": claim_id,
        "approved": approved,
        "reason": reason,
    })


async def notify_score_changed(
    db: AsyncSession, agent_id: int, old_score: int, new_score: int
):
    await notify_operator(db, agent_id, "score.changed", {
        "old_score": old_score,
        "new_score": new_score,
    })
