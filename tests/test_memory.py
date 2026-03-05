"""Tests for the agent memory service and API endpoints."""

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from backend.main import app
from backend.db import Base, get_db
from backend.models.schema import Agent, Operator, AgentMemory
from backend.services.memory import (
    store_run_memory,
    store_context_memory,
    get_recent_memories,
    build_memory_context,
    MEMORY_CONTEXT_LIMIT,
)

TEST_DB_URL = "sqlite+aiosqlite:///test_memory.db"


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
async def engine():
    eng = create_async_engine(TEST_DB_URL, echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()


@pytest.fixture
async def db(engine):
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        yield session


@pytest.fixture
async def agent(db):
    """Create a minimal operator + agent for testing."""
    op = Operator(wallet_address="0xmem0000000000000000000000000000000001")
    db.add(op)
    await db.flush()
    ag = Agent(operator_id=op.id, metadata_uri="ipfs://QmMem", trust_score=100)
    db.add(ag)
    await db.commit()
    await db.refresh(ag)
    return ag


@pytest.fixture
async def test_db(engine):
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


@pytest.fixture
async def client(test_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ── Unit tests: memory service ────────────────────────────────────────────────

class TestStoreRunMemory:
    @pytest.mark.asyncio
    async def test_stores_violation_memory(self, db, agent):
        await store_run_memory(
            db=db,
            agent_id=agent.id,
            run_id="abc123",
            verdict="fail",
            reason_codes=["tool_not_allowed", "value_limit_exceeded"],
            trust_score=85,
        )
        await db.commit()

        memories = await get_recent_memories(db, agent.id)
        assert len(memories) == 1
        m = memories[0]
        assert m.memory_type == "violation"
        assert "tool_not_allowed" in m.content
        assert m.metadata_json["reason_codes"] == ["tool_not_allowed", "value_limit_exceeded"]
        assert m.metadata_json["trust_score"] == 85

    @pytest.mark.asyncio
    async def test_stores_success_memory(self, db, agent):
        await store_run_memory(
            db=db,
            agent_id=agent.id,
            run_id="def456",
            verdict="pass",
            reason_codes=None,
            trust_score=100,
        )
        await db.commit()

        memories = await get_recent_memories(db, agent.id)
        assert len(memories) == 1
        assert memories[0].memory_type == "success"
        assert "passed" in memories[0].content.lower()

    @pytest.mark.asyncio
    async def test_run_id_attached(self, db, agent):
        await store_run_memory(db, agent.id, "run999", "pass", None, 100)
        await db.commit()
        memories = await get_recent_memories(db, agent.id)
        assert memories[0].run_id == "run999"


class TestStoreContextMemory:
    @pytest.mark.asyncio
    async def test_stores_context(self, db, agent):
        await store_context_memory(db, agent.id, "Operator note: prefer ETH trades.", {"key": "val"})
        memories = await get_recent_memories(db, agent.id)
        assert len(memories) == 1
        assert memories[0].memory_type == "context"
        assert "Operator note" in memories[0].content
        assert memories[0].metadata_json == {"key": "val"}

    @pytest.mark.asyncio
    async def test_null_metadata_allowed(self, db, agent):
        await store_context_memory(db, agent.id, "No metadata here.")
        memories = await get_recent_memories(db, agent.id)
        assert memories[0].metadata_json is None


class TestGetRecentMemories:
    @pytest.mark.asyncio
    async def test_returns_chronological_order(self, db, agent):
        for i in range(5):
            await store_run_memory(db, agent.id, f"run{i}", "pass", None, 100)
            await db.commit()

        memories = await get_recent_memories(db, agent.id)
        ids = [m.id for m in memories]
        assert ids == sorted(ids), "Memories should be in chronological (ascending ID) order"

    @pytest.mark.asyncio
    async def test_limit_respected(self, db, agent):
        for i in range(15):
            await store_run_memory(db, agent.id, f"run{i}", "pass", None, 100)
            await db.commit()

        memories = await get_recent_memories(db, agent.id, limit=5)
        assert len(memories) == 5

    @pytest.mark.asyncio
    async def test_filter_by_type(self, db, agent):
        await store_run_memory(db, agent.id, "r1", "fail", ["tool_not_allowed"], 90)
        await db.commit()
        await store_run_memory(db, agent.id, "r2", "pass", None, 100)
        await db.commit()
        await store_context_memory(db, agent.id, "A note.")

        violations = await get_recent_memories(db, agent.id, memory_type="violation")
        assert len(violations) == 1
        assert violations[0].memory_type == "violation"

        successes = await get_recent_memories(db, agent.id, memory_type="success")
        assert len(successes) == 1

    @pytest.mark.asyncio
    async def test_empty_for_new_agent(self, db, agent):
        memories = await get_recent_memories(db, agent.id)
        assert memories == []

    @pytest.mark.asyncio
    async def test_default_limit_is_context_limit(self, db, agent):
        for i in range(MEMORY_CONTEXT_LIMIT + 5):
            await store_run_memory(db, agent.id, f"run{i}", "pass", None, 100)
            await db.commit()

        memories = await get_recent_memories(db, agent.id)
        assert len(memories) == MEMORY_CONTEXT_LIMIT


class TestBuildMemoryContext:
    @pytest.mark.asyncio
    async def test_empty_string_when_no_memories(self, db, agent):
        context = await build_memory_context(db, agent.id)
        assert context == ""

    @pytest.mark.asyncio
    async def test_contains_agent_stats(self, db, agent):
        await store_run_memory(db, agent.id, "r1", "pass", None, 100)
        await db.commit()
        context = await build_memory_context(db, agent.id)
        assert "Agent Behavioural Memory" in context
        assert "Trust score" in context

    @pytest.mark.asyncio
    async def test_contains_memory_content(self, db, agent):
        await store_run_memory(db, agent.id, "r1", "fail", ["tool_not_allowed"], 85)
        await db.commit()
        context = await build_memory_context(db, agent.id)
        assert "tool_not_allowed" in context
        assert "VIOLATION" in context

    @pytest.mark.asyncio
    async def test_capped_at_context_limit(self, db, agent):
        for i in range(MEMORY_CONTEXT_LIMIT + 3):
            await store_run_memory(db, agent.id, f"run{i}", "pass", None, 100)
            await db.commit()
        context = await build_memory_context(db, agent.id)
        # Should not contain more than MEMORY_CONTEXT_LIMIT entries
        assert context.count("[SUCCESS]") <= MEMORY_CONTEXT_LIMIT


# ── API endpoint tests ────────────────────────────────────────────────────────

class TestMemoryEndpoints:
    async def _setup_agent_with_key(self, client) -> tuple[int, str]:
        """Register agent, generate API key, return (agent_id, api_key)."""
        r = await client.post("/api/agents", json={
            "wallet_address": "0xmemapi000000000000000000000000000001",
            "metadata_uri": "ipfs://QmMemAPI",
        })
        agent_id = r.json()["id"]
        wallet = "0xmemapi000000000000000000000000000001"
        r = await client.post(f"/api/operators/{wallet}/api-key")
        api_key = r.json()["api_key"]
        return agent_id, api_key

    @pytest.mark.asyncio
    async def test_list_memories_empty(self, client):
        r = await client.post("/api/agents", json={
            "wallet_address": "0xmemlist000000000000000000000000000001",
            "metadata_uri": "ipfs://QmList",
        })
        agent_id = r.json()["id"]

        r = await client.get(f"/api/agents/{agent_id}/memories")
        assert r.status_code == 200
        assert r.json() == []

    @pytest.mark.asyncio
    async def test_list_memories_not_found(self, client):
        r = await client.get("/api/agents/99999/memories")
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_add_memory_requires_auth(self, client):
        r = await client.post("/api/agents", json={
            "wallet_address": "0xmemadd0000000000000000000000000000001",
            "metadata_uri": "ipfs://QmAdd",
        })
        agent_id = r.json()["id"]

        r = await client.post(f"/api/agents/{agent_id}/memories", json={"content": "test"})
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_add_and_list_memory(self, client):
        agent_id, api_key = await self._setup_agent_with_key(client)

        r = await client.post(
            f"/api/agents/{agent_id}/memories",
            json={"content": "Prefer low-risk trades.", "metadata": {"risk": "low"}},
            headers={"X-API-Key": api_key},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "memory stored"

        r = await client.get(f"/api/agents/{agent_id}/memories")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 1
        assert data[0]["memory_type"] == "context"
        assert data[0]["content"] == "Prefer low-risk trades."
        assert data[0]["metadata"]["risk"] == "low"

    @pytest.mark.asyncio
    async def test_add_memory_wrong_operator(self, client):
        # Register two separate agents with separate operators
        r1 = await client.post("/api/agents", json={
            "wallet_address": "0xmemown1000000000000000000000000000001",
            "metadata_uri": "ipfs://QmOwn1",
        })
        agent1_id = r1.json()["id"]

        r2 = await client.post("/api/agents", json={
            "wallet_address": "0xmemown2000000000000000000000000000002",
            "metadata_uri": "ipfs://QmOwn2",
        })
        agent2_id = r2.json()["id"]

        # Get key for operator 2
        r = await client.post("/api/operators/0xmemown2000000000000000000000000000002/api-key")
        key2 = r.json()["api_key"]

        # Try to write memory to agent1 using operator2's key — should 403
        r = await client.post(
            f"/api/agents/{agent1_id}/memories",
            json={"content": "Unauthorized note."},
            headers={"X-API-Key": key2},
        )
        assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_list_memories_limit(self, client):
        agent_id, api_key = await self._setup_agent_with_key(client)

        # Add 5 memories
        for i in range(5):
            await client.post(
                f"/api/agents/{agent_id}/memories",
                json={"content": f"Memory {i}"},
                headers={"X-API-Key": api_key},
            )

        r = await client.get(f"/api/agents/{agent_id}/memories?limit=3")
        assert r.status_code == 200
        assert len(r.json()) == 3

    @pytest.mark.asyncio
    async def test_memories_populated_after_run(self, client):
        agent_id, api_key = await self._setup_agent_with_key(client)

        # Execute a run (mock mode)
        r = await client.post("/api/runs", json={
            "agent_id": agent_id,
            "user_input": "Hello agent",
        })
        assert r.status_code == 200

        # Memory should now have a record
        r = await client.get(f"/api/agents/{agent_id}/memories")
        assert r.status_code == 200
        memories = r.json()
        assert len(memories) >= 1
        assert memories[0]["memory_type"] in ("success", "violation")

    @pytest.mark.asyncio
    async def test_memory_type_filter(self, client):
        agent_id, api_key = await self._setup_agent_with_key(client)

        # Add a context memory
        await client.post(
            f"/api/agents/{agent_id}/memories",
            json={"content": "Context note"},
            headers={"X-API-Key": api_key},
        )

        # Run to create a success/violation memory
        await client.post("/api/runs", json={
            "agent_id": agent_id,
            "user_input": "Test run",
        })

        # Filter by type
        r = await client.get(f"/api/agents/{agent_id}/memories?memory_type=context")
        assert r.status_code == 200
        for m in r.json():
            assert m["memory_type"] == "context"
