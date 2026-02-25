"""AgentBond API - Verifiable Agent Warranty Network."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db import init_db, get_db
from backend.routers import agents, runs, claims, policies, scores
from backend.middleware import RateLimitMiddleware
from backend.auth import generate_api_key
from backend.models.schema import Operator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing database...")
    await init_db()
    logger.info("AgentBond API ready")
    yield


app = FastAPI(
    title="AgentBond",
    description="Verifiable Agent Warranty Network on OpenGradient",
    version="0.1.0",
    lifespan=lifespan,
)

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


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "agentbond"}


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


@app.get("/api/dashboard/stats")
async def dashboard_stats():
    """Redirect to scores router stats endpoint."""
    from backend.db import async_session
    from backend.routers.scores import get_dashboard_stats
    async with async_session() as db:
        return await get_dashboard_stats(db)
