"""Middleware for rate limiting, request validation, and Prometheus metrics."""

import time
import logging
from collections import defaultdict
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from backend.metrics import HTTP_REQUESTS_TOTAL, HTTP_REQUEST_DURATION, RATE_LIMIT_HITS_TOTAL

logger = logging.getLogger(__name__)


def _route_path(request: Request) -> str:
    """Return the route template (e.g. /api/agents/{agent_id}) instead of the
    resolved path, to avoid high-cardinality metric labels."""
    route = request.scope.get("route")
    if route and hasattr(route, "path"):
        return route.path
    # Fallback: strip numeric segments so /api/agents/42 → /api/agents/{id}
    import re
    return re.sub(r"/\d+", "/{id}", request.url.path)


class MetricsMiddleware(BaseHTTPMiddleware):
    """Record Prometheus HTTP metrics for every request."""

    async def dispatch(self, request: Request, call_next):
        method = request.method
        path = _route_path(request)
        start = time.perf_counter()

        response = await call_next(request)

        duration = time.perf_counter() - start
        status = str(response.status_code)

        HTTP_REQUESTS_TOTAL.labels(method=method, path=path, status=status).inc()
        HTTP_REQUEST_DURATION.labels(method=method, path=path).observe(duration)

        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """In-memory rate limiter — enforces limits per IP and per API key.

    - Global IP limit: requests_per_minute (default 120)
    - Per-operator limit: operator_rpm (default 30) — applied when X-API-Key is present
    """

    def __init__(self, app, requests_per_minute: int = 120, operator_rpm: int = 30):
        super().__init__(app)
        self.rpm = requests_per_minute
        self.operator_rpm = operator_rpm
        self.requests: dict[str, list[float]] = defaultdict(list)

    def _check(self, key: str, limit: int, now: float) -> bool:
        """Return True if request should be allowed, False if rate-limited."""
        window_start = now - 60
        self.requests[key] = [t for t in self.requests[key] if t > window_start]
        if len(self.requests[key]) >= limit:
            return False
        self.requests[key].append(now)
        return True

    async def dispatch(self, request: Request, call_next):
        now = time.time()
        client_ip = request.client.host if request.client else "unknown"

        # IP-level check
        if not self._check(f"ip:{client_ip}", self.rpm, now):
            RATE_LIMIT_HITS_TOTAL.inc()
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Try again later."},
            )

        # Per-operator check (keyed by API key, not IP)
        api_key = request.headers.get("x-api-key") or request.headers.get("X-API-Key")
        if api_key:
            if not self._check(f"key:{api_key}", self.operator_rpm, now):
                RATE_LIMIT_HITS_TOTAL.inc()
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Operator rate limit exceeded. Max 30 requests/min."},
                )

        return await call_next(request)
