"""Per-run signature binding enforcement tests.

The run signature is the anchor that turns "authorized run" from UI theater into
a real cryptographic check. These tests guarantee that:

  - A signature tied to a different prompt is rejected (prompt swap attack)
  - A signature older than the freshness window is rejected (long-term replay)
  - A signature without agent id / prompt hash / timestamp is rejected
  - A valid signature passes
"""

import hashlib
import time

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from backend.main import app
from backend.db import Base, get_db


TEST_DB_URL = "sqlite+aiosqlite:///test_sig_binding.db"


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
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
    app.dependency_overrides.clear()


@pytest.fixture
async def client(test_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def _msg(agent_id: int, prompt: str, ts: int | None = None) -> str:
    ts = ts if ts is not None else int(time.time())
    prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()
    return f"AgentBond run\nAgent: {agent_id}\nPrompt: {prompt_hash}\nTimestamp: {ts}"


async def _setup(client):
    wallet = "0xsigbind0000000000000000000000000000001"
    r = await client.post("/api/agents", json={
        "wallet_address": wallet,
        "metadata_uri": "ipfs://sigbind",
        "signature": "0xtest", "message": "test",
    })
    agent_id = r.json()["id"]
    r = await client.post(f"/api/operators/{wallet}/api-key")
    key = r.json()["api_key"]
    await client.post("/api/policies", json={
        "agent_id": agent_id,
        "rules": {"allowed_tools": ["get_price"]},
    }, headers={"X-API-Key": key})
    return agent_id, {"X-API-Key": key}


class TestPerRunSignatureBinding:
    @pytest.mark.asyncio
    async def test_valid_signature_accepted(self, client):
        agent_id, headers = await _setup(client)
        prompt = "What is ETH price?"
        r = await client.post("/api/runs", json={
            "agent_id": agent_id,
            "user_input": prompt,
            "signature": "0xtest",
            "message": _msg(agent_id, prompt),
        }, headers=headers)
        assert r.status_code == 200, r.text

    @pytest.mark.asyncio
    async def test_missing_signature_rejected(self, client):
        agent_id, headers = await _setup(client)
        r = await client.post("/api/runs", json={
            "agent_id": agent_id,
            "user_input": "hi",
        }, headers=headers)
        assert r.status_code == 401
        assert "signature required" in r.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_prompt_swap_rejected(self, client):
        """Signature was computed for prompt A, request uses prompt B."""
        agent_id, headers = await _setup(client)
        signed_message = _msg(agent_id, "Prompt A")
        r = await client.post("/api/runs", json={
            "agent_id": agent_id,
            "user_input": "Prompt B — different!",
            "signature": "0xtest",
            "message": signed_message,
        }, headers=headers)
        assert r.status_code == 401
        assert "prompt" in r.json()["detail"].lower() or "sha-256" in r.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_stale_signature_rejected(self, client):
        """Signature timestamp older than the freshness window is rejected."""
        agent_id, headers = await _setup(client)
        prompt = "stale run"
        stale_ts = int(time.time()) - 3600  # 1 hour old
        r = await client.post("/api/runs", json={
            "agent_id": agent_id,
            "user_input": prompt,
            "signature": "0xtest",
            "message": _msg(agent_id, prompt, ts=stale_ts),
        }, headers=headers)
        assert r.status_code == 401
        assert "expired" in r.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_missing_timestamp_rejected(self, client):
        agent_id, headers = await _setup(client)
        prompt = "no ts"
        prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()
        no_ts_msg = f"AgentBond run\nAgent: {agent_id}\nPrompt: {prompt_hash}"
        r = await client.post("/api/runs", json={
            "agent_id": agent_id,
            "user_input": prompt,
            "signature": "0xtest",
            "message": no_ts_msg,
        }, headers=headers)
        assert r.status_code == 401
        assert "timestamp" in r.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_wrong_agent_id_rejected(self, client):
        """Signature references agent 999, request is for agent_id."""
        agent_id, headers = await _setup(client)
        prompt = "cross-agent"
        wrong_msg = _msg(999, prompt)
        r = await client.post("/api/runs", json={
            "agent_id": agent_id,
            "user_input": prompt,
            "signature": "0xtest",
            "message": wrong_msg,
        }, headers=headers)
        assert r.status_code == 401
        assert "agent" in r.json()["detail"].lower()
