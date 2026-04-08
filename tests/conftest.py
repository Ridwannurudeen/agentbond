"""Shared test configuration and fixtures."""

import pytest
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from backend.main import app
from backend.db import Base, get_db


TEST_DB_URL = "sqlite+aiosqlite:///test_shared.db"

# Dummy values passed in requests so the presence check passes
TEST_SIGNATURE = "0x" + "a" * 130
TEST_MESSAGE = "test message"


@pytest.fixture(autouse=True)
def mock_verify_wallet_signature():
    """Bypass wallet signature verification in all tests."""
    with patch("backend.auth.verify_wallet_signature", return_value=True), \
         patch("backend.routers.agents.verify_wallet_signature", return_value=True), \
         patch("backend.routers.claims.verify_wallet_signature", return_value=True), \
         patch("backend.main.verify_wallet_signature", return_value=True):
        yield
