"""AgentBond API - Verifiable Agent Warranty Network."""

import logging
import logging.config
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db import init_db, get_db
from backend.routers import agents, runs, claims, policies, scores, operators
from backend.middleware import RateLimitMiddleware, MetricsMiddleware
from backend.auth import generate_api_key
from backend.models.schema import Operator

# ---------------------------------------------------------------------------
# Structured JSON logging
# ---------------------------------------------------------------------------

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "backend.logging_setup.JsonFormatter",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
        },
    },
    "root": {
        "level": "INFO",
        "handlers": ["console"],
    },
    "loggers": {
        "uvicorn.access": {"level": "WARNING"},   # suppress noisy access log
        "sqlalchemy.engine": {"level": "WARNING"},
    },
}

logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# App lifecycle
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing database", extra={"event": "startup"})
    await init_db()
    logger.info("AgentBond API ready", extra={"event": "startup"})
    yield
    logger.info("AgentBond API shutting down", extra={"event": "shutdown"})


app = FastAPI(
    title="AgentBond",
    description="Verifiable Agent Warranty Network on OpenGradient",
    version="0.1.0",
    lifespan=lifespan,
)

# Metrics middleware first so it wraps everything (including rate-limit 429s)
app.add_middleware(MetricsMiddleware)
app.add_middleware(RateLimitMiddleware, requests_per_minute=120)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(agents.router)
app.include_router(runs.router)
app.include_router(claims.router)
app.include_router(policies.router)
app.include_router(scores.router)
app.include_router(operators.router)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/api/health")
async def health(db: AsyncSession = Depends(get_db)):
    """Liveness + readiness probe. Checks DB connectivity."""
    db_ok = False
    try:
        await db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        pass

    status = "ok" if db_ok else "degraded"
    return {
        "status": status,
        "service": "agentbond",
        "checks": {
            "database": "ok" if db_ok else "error",
        },
    }


# ---------------------------------------------------------------------------
# Prometheus metrics
# ---------------------------------------------------------------------------

@app.get("/metrics", include_in_schema=False)
async def metrics():
    """Expose Prometheus metrics for scraping."""
    data = generate_latest()
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)


# ---------------------------------------------------------------------------
# Operator API key generation
# ---------------------------------------------------------------------------

@app.post("/api/operators/{wallet_address}/api-key")
async def generate_operator_api_key(
    wallet_address: str, db: AsyncSession = Depends(get_db)
):
    """Generate a new API key for an operator."""
    result = await db.execute(
        select(Operator).where(Operator.wallet_address == wallet_address)
    )
    operator = result.scalar_one_or_none()
    if not operator:
        from fastapi import HTTPException
        raise HTTPException(404, "Operator not found")

    key = generate_api_key()
    operator.api_key = key
    await db.commit()

    return {
        "operator_id": operator.id,
        "wallet_address": operator.wallet_address,
        "api_key": key,
    }


# ---------------------------------------------------------------------------
# Dashboard stats
# ---------------------------------------------------------------------------

@app.get("/api/dashboard/stats")
async def dashboard_stats():
    """Redirect to scores router stats endpoint."""
    from backend.db import async_session
    from backend.routers.scores import get_dashboard_stats
    async with async_session() as db:
        return await get_dashboard_stats(db)
