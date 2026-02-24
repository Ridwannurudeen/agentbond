"""AgentBond API - Verifiable Agent Warranty Network."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.db import init_db
from backend.routers import agents, runs, claims, policies, scores

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


@app.get("/api/dashboard/stats")
async def dashboard_stats():
    """Redirect to scores router stats endpoint."""
    from backend.db import async_session
    from backend.routers.scores import get_dashboard_stats
    async with async_session() as db:
        return await get_dashboard_stats(db)
