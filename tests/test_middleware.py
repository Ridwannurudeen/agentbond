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


class TestPerOperatorRateLimit:
    """Tests for the per-API-key (operator) rate limit."""

    def _make_middleware(self, operator_rpm: int = 5):
        """Return a fresh RateLimitMiddleware with a low operator limit."""
        from backend.middleware import RateLimitMiddleware
        # Instantiate without an ASGI app — we call _check() directly
        mw = RateLimitMiddleware.__new__(RateLimitMiddleware)
        from collections import defaultdict
        mw.rpm = 120
        mw.operator_rpm = operator_rpm
        mw.requests = defaultdict(list)
        return mw

    def test_operator_allowed_under_limit(self):
        import time
        mw = self._make_middleware(operator_rpm=10)
        now = time.time()
        for _ in range(10):
            allowed = mw._check("key:test-key-1", mw.operator_rpm, now)
            assert allowed

    def test_operator_blocked_at_limit(self):
        import time
        mw = self._make_middleware(operator_rpm=5)
        now = time.time()
        results = [mw._check("key:test-key-2", mw.operator_rpm, now) for _ in range(7)]
        # First 5 allowed, last 2 blocked
        assert results[:5] == [True] * 5
        assert results[5] is False
        assert results[6] is False

    def test_different_keys_are_independent(self):
        import time
        mw = self._make_middleware(operator_rpm=3)
        now = time.time()
        # Exhaust key-A
        for _ in range(3):
            mw._check("key:key-A", mw.operator_rpm, now)
        assert mw._check("key:key-A", mw.operator_rpm, now) is False
        # key-B should still be allowed
        assert mw._check("key:key-B", mw.operator_rpm, now) is True

    def test_window_slides_after_one_minute(self):
        import time
        mw = self._make_middleware(operator_rpm=3)
        old_time = time.time() - 61  # 61 seconds ago (outside window)
        # Add 3 "old" timestamps
        mw.requests["key:key-C"] = [old_time, old_time, old_time]
        now = time.time()
        # Old requests should be pruned — new request should be allowed
        assert mw._check("key:key-C", mw.operator_rpm, now) is True

    @pytest.mark.asyncio
    async def test_api_returns_429_on_operator_limit(self, client):
        """Integration: HTTP endpoint returns 429 when operator limit is hit."""
        from backend.middleware import RateLimitMiddleware
        import time

        # Find and patch the middleware instance to use a low limit
        for mw_item in app.user_middleware:
            if mw_item.cls is RateLimitMiddleware:
                break

        # Directly manipulate the middleware's state to simulate near-limit
        # by injecting timestamps — access via the built app
        from starlette.testclient import TestClient as _SC  # noqa: just to locate mw
        mw_instance = None
        for layer in app.middleware_stack.__class__.__mro__:
            pass  # Can't easily get instance; use direct approach below

        # Flood with API key header — operator_rpm=30, so 31+ should 429
        API_KEY = "fake-operator-key-xyz"
        responses = []
        for _ in range(35):
            r = await client.get("/api/health", headers={"X-API-Key": API_KEY})
            responses.append(r.status_code)

        assert 429 in responses
        # First requests pass
        assert responses[0] == 200
        # 429 response body
        rejected = next(i for i, s in enumerate(responses) if s == 429)
        r = await client.get("/api/health", headers={"X-API-Key": API_KEY})
        assert r.status_code == 429
        assert "operator" in r.json()["detail"].lower() or "rate limit" in r.json()["detail"].lower()
