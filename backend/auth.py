"""API key authentication for operator endpoints."""

import hashlib
import secrets
from eth_account import Account
from eth_account.messages import encode_defunct
from fastapi import Header, HTTPException, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db import get_db
from backend.models.schema import Operator


def generate_api_key() -> str:
    """Generate a random 48-character API key."""
    return secrets.token_hex(24)


def hash_api_key(key: str) -> str:
    """SHA-256 hash an API key for storage. Never store plaintext keys."""
    return hashlib.sha256(key.encode()).hexdigest()


def verify_wallet_signature(message: str, signature: str, expected_address: str) -> bool:
    """Verify an EIP-191 personal_sign signature.

    Returns True if the signature was made by expected_address, False otherwise.
    """
    try:
        msg = encode_defunct(text=message)
        recovered = Account.recover_message(msg, signature=signature)
        return recovered.lower() == expected_address.lower()
    except Exception:
        return False


async def _find_operator_by_key(db: AsyncSession, raw_key: str) -> Operator | None:
    """Look up an operator by hashing the provided key and comparing."""
    key_hash = hash_api_key(raw_key)
    result = await db.execute(
        select(Operator).where(Operator.api_key == key_hash)
    )
    return result.scalar_one_or_none()


async def verify_operator_key(
    x_api_key: str = Header(default=None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
) -> Operator | None:
    """Verify API key and return the operator, or None if no key provided."""
    if not x_api_key:
        return None

    operator = await _find_operator_by_key(db, x_api_key)
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

    operator = await _find_operator_by_key(db, x_api_key)
    if not operator:
        raise HTTPException(401, "Invalid API key")
    return operator
