"""Tests for rate limiting middleware."""

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from backend.db import Base, get_db
from backend.main import app
from tests.conftest import _find_rate_limit_middleware


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
        """Requests over the limit should get 429.

        conftest.py relaxes rpm to 10 million so unrelated tests never hit
        the limit. Here we tighten it back down and flood the endpoint to
        exercise the limiter end-to-end.
        """
        mw = _find_rate_limit_middleware()
        assert mw is not None, "RateLimitMiddleware not found in app stack"
        mw.rpm = 120
        mw.requests.clear()

        responses = []
        for _ in range(125):
            r = await client.get("/api/health")
            responses.append(r.status_code)

        assert 429 in responses
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

    def test_operator_limit_is_lower_than_ip_limit(self):
        """Operator rpm should be tighter than the global IP limit."""
        mw = self._make_middleware(operator_rpm=30)
        # operator_rpm is 30; IP limit defaults to 120
        assert mw.operator_rpm < mw.rpm

    def test_requests_dict_keyed_separately_for_ip_and_key(self):
        """IP and API-key buckets use distinct namespaced keys."""
        import time
        mw = self._make_middleware(operator_rpm=3)
        now = time.time()
        mw._check("ip:1.2.3.4", mw.rpm, now)
        mw._check("key:abc123", mw.operator_rpm, now)
        assert "ip:1.2.3.4" in mw.requests
        assert "key:abc123" in mw.requests
        # Exhausting one does not affect the other
        for _ in range(3):
            mw._check("key:abc123", mw.operator_rpm, now)
        assert mw._check("key:abc123", mw.operator_rpm, now) is False
        assert mw._check("ip:1.2.3.4", mw.rpm, now) is True
