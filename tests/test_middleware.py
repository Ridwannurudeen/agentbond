"""Tests for rate limiting middleware."""

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from backend.db import Base, get_db
from backend.main import app


TEST_DB_URL = "sqlite+aiosqlite:///test_middleware.db"


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


class TestRateLimiting:
    @pytest.mark.asyncio
    async def test_normal_requests_pass(self, client):
        """Requests under the limit should succeed."""
        for _ in range(5):
            r = await client.get("/api/health")
            assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_rate_limit_enforced(self, client):
        """Requests over the limit should get 429."""
        # The app is configured with 120 rpm. Flood it.
        # We need to clear any existing rate limit state first
        from backend.middleware import RateLimitMiddleware

        # Find the rate limit middleware and set a low limit for testing
        for middleware in app.user_middleware:
            if middleware.cls is RateLimitMiddleware:
                break

        # Send enough requests to exceed the 120 rpm limit
        responses = []
        for i in range(125):
            r = await client.get("/api/health")
            responses.append(r.status_code)

        # At least the last few should be 429
        assert 429 in responses
        # First requests should pass
        assert responses[0] == 200
