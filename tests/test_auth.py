"""Tests for API key authentication."""

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from backend.main import app
from backend.db import Base, get_db
from backend.auth import generate_api_key


TEST_DB_URL = "sqlite+aiosqlite:///test_auth.db"


@pytest.fixture
async def test_db():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    yield session_maker

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
    app.dependency_overrides.clear()


@pytest.fixture
async def client(test_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestGenerateApiKey:
    def test_generates_48_char_hex(self):
        key = generate_api_key()
        assert len(key) == 48
        assert all(c in "0123456789abcdef" for c in key)

    def test_generates_unique_keys(self):
        keys = {generate_api_key() for _ in range(100)}
        assert len(keys) == 100


class TestApiKeyEndpoint:
    @pytest.mark.asyncio
    async def test_generate_key_for_operator(self, client):
        # Register an agent (creates operator)
        r = await client.post("/api/agents", json={
            "wallet_address": "0xaaaa000000000000000000000000000000000001",
            "metadata_uri": "ipfs://QmAuth",
        })
        assert r.status_code == 200
        wallet = "0xaaaa000000000000000000000000000000000001"

        # Generate API key
        r = await client.post(f"/api/operators/{wallet}/api-key")
        assert r.status_code == 200
        data = r.json()
        assert "api_key" in data
        assert len(data["api_key"]) == 48

    @pytest.mark.asyncio
    async def test_generate_key_operator_not_found(self, client):
        r = await client.post("/api/operators/0xdead000000000000000000000000000000000000/api-key")
        assert r.status_code == 404
