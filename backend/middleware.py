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
    """Simple in-memory rate limiter per IP address."""

    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.rpm = requests_per_minute
        self.requests: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        window_start = now - 60

        self.requests[client_ip] = [
            t for t in self.requests[client_ip] if t > window_start
        ]

        if len(self.requests[client_ip]) >= self.rpm:
            RATE_LIMIT_HITS_TOTAL.inc()
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Try again later."},
            )

        self.requests[client_ip].append(now)
        return await call_next(request)
