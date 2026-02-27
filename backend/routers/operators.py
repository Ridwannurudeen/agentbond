"""Operator management endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth import require_operator_key
from backend.db import get_db
from backend.models.schema import Operator, WebhookDelivery

router = APIRouter(prefix="/api/operators", tags=["operators"])


@router.get("/{operator_id}/webhook-deliveries")
async def list_webhook_deliveries(
    operator_id: int,
    event_type: str | None = Query(default=None),
    success: bool | None = Query(default=None),
    agent_id: int | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    operator: Operator = Depends(require_operator_key),
):
    """List webhook delivery attempts for an operator.

    Only the authenticated operator can view their own deliveries.
    Supports filtering by event_type, success status, and agent_id.
    """
    if operator.id != operator_id:
        raise HTTPException(403, "Cannot view another operator's webhook deliveries")

    query = (
        select(WebhookDelivery)
        .where(WebhookDelivery.operator_id == operator_id)
        .order_by(WebhookDelivery.id.desc())
        .limit(limit)
        .offset(offset)
    )

    if event_type:
        query = query.where(WebhookDelivery.event_type == event_type)
    if success is not None:
        query = query.where(WebhookDelivery.success == success)
    if agent_id is not None:
        query = query.where(WebhookDelivery.agent_id == agent_id)

    result = await db.execute(query)
    deliveries = result.scalars().all()

    return [
        {
            "id": d.id,
            "agent_id": d.agent_id,
            "event_type": d.event_type,
            "webhook_url": d.webhook_url,
            "attempt": d.attempt,
            "status_code": d.status_code,
            "success": d.success,
            "error_message": d.error_message,
            "duration_ms": d.duration_ms,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in deliveries
    ]
