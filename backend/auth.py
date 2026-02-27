"""API key authentication for operator endpoints."""

import secrets
from fastapi import Header, HTTPException, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db import get_db
from backend.models.schema import Operator


def generate_api_key() -> str:
    """Generate a random 48-character API key."""
    return secrets.token_hex(24)


async def verify_operator_key(
    x_api_key: str = Header(default=None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
) -> Operator | None:
    """Verify API key and return the operator, or None if no key provided.

    For MVP, authentication is optional. When an API key is provided,
    it must match a registered operator.
    """
    if not x_api_key:
        return None

    result = await db.execute(
        select(Operator).where(Operator.api_key == x_api_key)
    )
    operator = result.scalar_one_or_none()
    if not operator:
        raise HTTPException(401, "Invalid API key")
    return operator


async def require_operator_key(
    x_api_key: str = Header(default=None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
) -> Operator:
    """Require a valid API key. Raises 401 if missing or invalid."""
    if not x_api_key:
        raise HTTPException(401, "API key required. Include X-API-Key header.")

    result = await db.execute(
        select(Operator).where(Operator.api_key == x_api_key)
    )
    operator = result.scalar_one_or_none()
    if not operator:
        raise HTTPException(401, "Invalid API key")
    return operator
