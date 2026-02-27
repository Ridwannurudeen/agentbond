"""End-to-end lifecycle tests using FastAPI TestClient."""

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from backend.main import app
from backend.db import Base, get_db


# Use SQLite for testing
TEST_DB_URL = "sqlite+aiosqlite:///test.db"


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


class TestHealthCheck:
    @pytest.mark.asyncio
    async def test_health(self, client):
        r = await client.get("/api/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


class TestFullLifecycle:
    @pytest.mark.asyncio
    async def test_register_agent(self, client):
        r = await client.post("/api/agents", json={
            "wallet_address": "0xtest1111111111111111111111111111111111",
            "metadata_uri": "ipfs://QmTest",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["id"] >= 1
        assert data["trust_score"] == 100

    @pytest.mark.asyncio
    async def test_register_and_get_agent(self, client):
        # Register
        r = await client.post("/api/agents", json={
            "wallet_address": "0xtest2222222222222222222222222222222222",
            "metadata_uri": "ipfs://QmTest2",
        })
        agent_id = r.json()["id"]

        # Get
        r = await client.get(f"/api/agents/{agent_id}")
        assert r.status_code == 200
        assert r.json()["metadata_uri"] == "ipfs://QmTest2"

    @pytest.mark.asyncio
    async def test_full_lifecycle(self, client):
        wallet = "0xlifecycle000000000000000000000000000001"

        # 1. Register agent
        r = await client.post("/api/agents", json={
            "wallet_address": wallet,
            "metadata_uri": "ipfs://QmLifecycle",
        })
        assert r.status_code == 200
        agent_id = r.json()["id"]

        # Get API key for operator
        r = await client.post(f"/api/operators/{wallet}/api-key")
        assert r.status_code == 200
        auth_headers = {"X-API-Key": r.json()["api_key"]}

        # 2. Register policy
        r = await client.post("/api/policies", json={
            "agent_id": agent_id,
            "rules": {
                "allowed_tools": ["get_price"],
                "max_value_per_action": 100,
            },
        }, headers=auth_headers)
        assert r.status_code == 200
        policy_id = r.json()["id"]

        # 3. Stake
        r = await client.post(f"/api/agents/{agent_id}/stake", json={
            "amount_wei": "100000000000000000",
        }, headers=auth_headers)
        assert r.status_code == 200

        # 4. Execute run
        r = await client.post("/api/runs", json={
            "agent_id": agent_id,
            "user_input": "What is the price of ETH?",
        })
        assert r.status_code == 200
        run_data = r.json()
        run_id = run_data["run_id"]
        assert run_data["policy_verdict"] in ["pass", "fail"]

        # 5. Get run details
        r = await client.get(f"/api/runs/{run_id}")
        assert r.status_code == 200
        assert r.json()["run_id"] == run_id

        # 6. Replay run
        r = await client.get(f"/api/runs/{run_id}/replay")
        assert r.status_code == 200
        assert "proof_valid" in r.json()

        # 7. Check score
        r = await client.get(f"/api/scores/{agent_id}")
        assert r.status_code == 200
        assert r.json()["score"] >= 0

        # 8. Submit claim
        r = await client.post("/api/claims", json={
            "run_id": run_id,
            "agent_id": agent_id,
            "claimant_address": "0xclaimant00000000000000000000000000001",
            "reason_code": "TOOL_WHITELIST_VIOLATION",
        })
        assert r.status_code == 200
        claim_data = r.json()
        assert claim_data["claim_id"] >= 1

        # 9. Verify duplicate claim is rejected
        r = await client.post("/api/claims", json={
            "run_id": run_id,
            "agent_id": agent_id,
            "claimant_address": "0xclaimant00000000000000000000000000002",
            "reason_code": "TOOL_WHITELIST_VIOLATION",
        })
        assert r.status_code == 409

        # 10. Dashboard stats
        r = await client.get(f"/api/scores")
        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_agent_not_found(self, client):
        r = await client.get("/api/agents/99999")
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_run_not_found(self, client):
        r = await client.get("/api/runs/nonexistent-id")
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_list_agents_empty(self, client):
        r = await client.get("/api/agents")
        assert r.status_code == 200
        assert r.json() == []
