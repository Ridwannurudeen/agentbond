"""Agent registration, versioning, status, and staking endpoints."""

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from web3 import Web3

from backend.contracts.interface import contracts
from backend.db import get_db
from backend.models.schema import Agent, Operator, AgentVersion, AgentStatus, StakeEvent, Policy

router = APIRouter(prefix="/api/agents", tags=["agents"])
logger = logging.getLogger(__name__)


class RegisterAgentRequest(BaseModel):
    wallet_address: str
    metadata_uri: str
    webhook_url: str | None = None


class PublishVersionRequest(BaseModel):
    version_hash: str
    policy_id: int | None = None


class StakeRequest(BaseModel):
    amount_wei: str  # string to handle large numbers


class UnstakeRequest(BaseModel):
    amount_wei: str


class SetStatusRequest(BaseModel):
    status: str  # "active", "paused", "retired"


@router.post("")
async def register_agent(req: RegisterAgentRequest, db: AsyncSession = Depends(get_db)):
    """Register a new agent."""
    # Find or create operator
    result = await db.execute(
        select(Operator).where(Operator.wallet_address == req.wallet_address)
    )
    operator = result.scalar_one_or_none()
    if not operator:
        operator = Operator(wallet_address=req.wallet_address, webhook_url=req.webhook_url)
        db.add(operator)
        await db.flush()
    elif req.webhook_url:
        operator.webhook_url = req.webhook_url

    agent = Agent(
        operator_id=operator.id,
        metadata_uri=req.metadata_uri,
        status=AgentStatus.active,
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)

    # Wire up on-chain: register agent
    chain_agent_id = None
    chain_tx = None
    if contracts.is_configured():
        try:
            chain_agent_id, chain_tx = await asyncio.to_thread(
                contracts.register_agent, req.metadata_uri
            )
            agent.chain_agent_id = chain_agent_id
            await db.commit()
            logger.info(f"Agent {agent.id} registered on-chain: chainId={chain_agent_id} tx={chain_tx}")
        except Exception as e:
            logger.warning(f"On-chain agent registration failed (non-fatal): {e}")

    return {
        "id": agent.id,
        "operator_id": operator.id,
        "metadata_uri": agent.metadata_uri,
        "status": agent.status.value,
        "trust_score": agent.trust_score,
        "chain_agent_id": chain_agent_id,
        "chain_tx": chain_tx,
    }


@router.get("/{agent_id}")
async def get_agent(agent_id: int, db: AsyncSession = Depends(get_db)):
    """Get agent details including score."""
    agent = await db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")

    return {
        "id": agent.id,
        "operator_id": agent.operator_id,
        "metadata_uri": agent.metadata_uri,
        "active_version": agent.active_version,
        "status": agent.status.value if agent.status else "active",
        "trust_score": agent.trust_score,
        "total_runs": agent.total_runs,
        "violations": agent.violations,
        "chain_agent_id": agent.chain_agent_id,
        "created_at": agent.created_at.isoformat() if agent.created_at else None,
    }


@router.get("")
async def list_agents(db: AsyncSession = Depends(get_db)):
    """List all agents."""
    result = await db.execute(select(Agent).order_by(Agent.id.desc()))
    agents = result.scalars().all()
    return [
        {
            "id": a.id,
            "operator_id": a.operator_id,
            "metadata_uri": a.metadata_uri,
            "status": a.status.value if a.status else "active",
            "trust_score": a.trust_score,
            "total_runs": a.total_runs,
            "violations": a.violations,
            "chain_agent_id": a.chain_agent_id,
        }
        for a in agents
    ]


@router.post("/{agent_id}/versions")
async def publish_version(
    agent_id: int, req: PublishVersionRequest, db: AsyncSession = Depends(get_db)
):
    """Publish a new agent version."""
    agent = await db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")

    version = AgentVersion(
        agent_id=agent_id,
        version_hash=req.version_hash,
        policy_id=req.policy_id,
    )
    db.add(version)
    await db.flush()

    agent.active_version = version.id
    await db.commit()
    await db.refresh(version)

    # Wire up on-chain: publish version
    chain_version_id = None
    chain_tx = None
    if contracts.is_configured() and agent.chain_agent_id is not None:
        try:
            version_hash_bytes = Web3.keccak(text=req.version_hash)
            chain_policy_id = 0
            if req.policy_id:
                policy = await db.get(Policy, req.policy_id)
                if policy and policy.chain_policy_id:
                    chain_policy_id = policy.chain_policy_id

            chain_version_id, chain_tx = await asyncio.to_thread(
                contracts.publish_version,
                agent.chain_agent_id,
                version_hash_bytes,
                chain_policy_id,
            )
            logger.info(f"Version {version.id} published on-chain: chainVersionId={chain_version_id} tx={chain_tx}")
        except Exception as e:
            logger.warning(f"On-chain publish_version failed (non-fatal): {e}")

    return {
        "version_id": version.id,
        "agent_id": agent_id,
        "version_hash": version.version_hash,
        "chain_version_id": chain_version_id,
        "chain_tx": chain_tx,
    }


@router.post("/{agent_id}/status")
async def set_agent_status(
    agent_id: int, req: SetStatusRequest, db: AsyncSession = Depends(get_db)
):
    """Update agent status."""
    agent = await db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")

    try:
        agent.status = AgentStatus(req.status)
    except ValueError:
        raise HTTPException(400, f"Invalid status: {req.status}")

    await db.commit()
    return {"id": agent_id, "status": agent.status.value}


class WebhookConfigRequest(BaseModel):
    webhook_url: str | None = None


@router.post("/{agent_id}/webhook")
async def configure_webhook(
    agent_id: int, req: WebhookConfigRequest, db: AsyncSession = Depends(get_db)
):
    """Configure webhook URL for the operator of this agent."""
    agent = await db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")

    operator = await db.get(Operator, agent.operator_id)
    if not operator:
        raise HTTPException(404, "Operator not found")

    operator.webhook_url = req.webhook_url
    await db.commit()

    return {
        "agent_id": agent_id,
        "operator_id": operator.id,
        "webhook_url": operator.webhook_url,
    }


@router.post("/{agent_id}/stake")
async def stake_collateral(
    agent_id: int, req: StakeRequest, db: AsyncSession = Depends(get_db)
):
    """Stake collateral in WarrantyPool on-chain, then record the event."""
    agent = await db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")

    amount_wei = int(req.amount_wei)
    tx_hash = None

    if contracts.is_configured() and agent.chain_agent_id is not None:
        try:
            tx_hash = await asyncio.to_thread(
                contracts.stake, agent.chain_agent_id, amount_wei
            )
            logger.info(f"Staked {amount_wei} wei for agent {agent_id} on-chain: tx={tx_hash}")
        except Exception as e:
            logger.warning(f"On-chain stake failed (non-fatal): {e}")

    event = StakeEvent(
        agent_id=agent_id,
        event_type="stake",
        amount=amount_wei,
        tx_hash=tx_hash,
    )
    db.add(event)
    await db.commit()

    return {"agent_id": agent_id, "amount_wei": req.amount_wei, "event": "staked", "tx_hash": tx_hash}


@router.post("/{agent_id}/unstake")
async def request_unstake(
    agent_id: int, req: UnstakeRequest, db: AsyncSession = Depends(get_db)
):
    """Request unstake from WarrantyPool on-chain, then record the event."""
    agent = await db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")

    amount_wei = int(req.amount_wei)
    tx_hash = None

    if contracts.is_configured() and agent.chain_agent_id is not None:
        try:
            _request_id, tx_hash = await asyncio.to_thread(
                contracts.request_unstake, agent.chain_agent_id, amount_wei
            )
            logger.info(f"Unstake requested for agent {agent_id}, amount={amount_wei} wei, tx={tx_hash}")
        except Exception as e:
            logger.warning(f"On-chain request_unstake failed (non-fatal): {e}")

    event = StakeEvent(
        agent_id=agent_id,
        event_type="unstake_request",
        amount=amount_wei,
        tx_hash=tx_hash,
    )
    db.add(event)
    await db.commit()

    return {"agent_id": agent_id, "amount_wei": req.amount_wei, "event": "unstake_requested", "tx_hash": tx_hash}
