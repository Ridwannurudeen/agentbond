"""Agent registration, versioning, status, and staking endpoints."""

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from web3 import Web3

from backend.auth import require_operator_key, verify_wallet_signature
from backend.contracts.interface import contracts
from backend.db import get_db
from backend.models.schema import Agent, Operator, AgentVersion, AgentStatus, StakeEvent, Policy, AgentMemory
from backend.schemas import (
    RegisterAgentResponse, AgentDetailResponse, AgentListItem,
    PublishVersionResponse, SetStatusResponse, WebhookConfigResponse,
    StakeResponse, UnstakeResponse, MemoryItem, AddMemoryResponse,
)
from backend.services.memory import get_recent_memories, store_context_memory

router = APIRouter(prefix="/api/agents", tags=["agents"])
logger = logging.getLogger(__name__)


class RegisterAgentRequest(BaseModel):
    wallet_address: str
    metadata_uri: str
    webhook_url: str | None = None
    # Optional on-chain data from frontend MetaMask flow
    signature: str | None = None
    message: str | None = None
    chain_agent_id: str | None = None
    chain_tx: str | None = None


class PublishVersionRequest(BaseModel):
    version_hash: str
    policy_id: int | None = None


class StakeRequest(BaseModel):
    amount_wei: str  # string to handle large numbers
    tx_hash: str | None = None  # On-chain tx hash from frontend MetaMask flow


class UnstakeRequest(BaseModel):
    amount_wei: str


class SetStatusRequest(BaseModel):
    status: str  # "active", "paused", "retired"


@router.post("", response_model=RegisterAgentResponse)
async def register_agent(req: RegisterAgentRequest, db: AsyncSession = Depends(get_db)):
    """Register a new agent."""
    # Signature is required — wallet ownership must be proven before registration
    if not req.signature or not req.message:
        raise HTTPException(401, "Wallet signature required. Connect your wallet and sign the message.")
    if not verify_wallet_signature(req.message, req.signature, req.wallet_address):
        raise HTTPException(401, "Signature verification failed: wallet ownership not proven")

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

    # Wire up on-chain: use frontend-provided chain data if available, else call contracts
    chain_agent_id = None
    chain_tx = None
    if req.chain_agent_id is not None:
        # Frontend already did the on-chain registration via MetaMask
        chain_agent_id = int(req.chain_agent_id)
        chain_tx = req.chain_tx
        agent.chain_agent_id = chain_agent_id
        await db.commit()
        logger.info(f"Agent {agent.id} on-chain data from frontend: chainId={chain_agent_id} tx={chain_tx}")
    elif contracts.is_configured():
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


@router.get("/{agent_id}", response_model=AgentDetailResponse)
async def get_agent(agent_id: int, db: AsyncSession = Depends(get_db)):
    """Get agent details including score."""
    agent = await db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")

    operator = await db.get(Operator, agent.operator_id)

    return {
        "id": agent.id,
        "operator_id": agent.operator_id,
        "operator_wallet": operator.wallet_address if operator else None,
        "metadata_uri": agent.metadata_uri,
        "active_version": agent.active_version,
        "status": agent.status.value if agent.status else "active",
        "trust_score": agent.trust_score,
        "total_runs": agent.total_runs,
        "violations": agent.violations,
        "chain_agent_id": agent.chain_agent_id,
        "created_at": agent.created_at.isoformat() if agent.created_at else None,
    }


@router.get("", response_model=list[AgentListItem])
async def list_agents(
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """List all agents."""
    result = await db.execute(select(Agent).order_by(Agent.id.desc()).limit(limit).offset(offset))
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


@router.post("/{agent_id}/versions", response_model=PublishVersionResponse)
async def publish_version(
    agent_id: int,
    req: PublishVersionRequest,
    db: AsyncSession = Depends(get_db),
    operator: Operator = Depends(require_operator_key),
):
    """Publish a new agent version."""
    agent = await db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")
    if agent.operator_id != operator.id:
        raise HTTPException(403, "Agent does not belong to your operator account")

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


@router.post("/{agent_id}/status", response_model=SetStatusResponse)
async def set_agent_status(
    agent_id: int,
    req: SetStatusRequest,
    db: AsyncSession = Depends(get_db),
    operator: Operator = Depends(require_operator_key),
):
    """Update agent status."""
    agent = await db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")
    if agent.operator_id != operator.id:
        raise HTTPException(403, "Agent does not belong to your operator account")

    try:
        agent.status = AgentStatus(req.status)
    except ValueError:
        raise HTTPException(400, f"Invalid status: {req.status}")

    await db.commit()
    return {"id": agent_id, "status": agent.status.value}


class WebhookConfigRequest(BaseModel):
    webhook_url: str | None = None


@router.post("/{agent_id}/webhook", response_model=WebhookConfigResponse)
async def configure_webhook(
    agent_id: int,
    req: WebhookConfigRequest,
    db: AsyncSession = Depends(get_db),
    operator: Operator = Depends(require_operator_key),
):
    """Configure webhook URL for the operator of this agent."""
    agent = await db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")
    if agent.operator_id != operator.id:
        raise HTTPException(403, "Agent does not belong to your operator account")

    operator.webhook_url = req.webhook_url
    await db.commit()

    return {
        "agent_id": agent_id,
        "operator_id": operator.id,
        "webhook_url": operator.webhook_url,
    }


@router.post("/{agent_id}/stake", response_model=StakeResponse)
async def stake_collateral(
    agent_id: int,
    req: StakeRequest,
    db: AsyncSession = Depends(get_db),
    operator: Operator = Depends(require_operator_key),
):
    """Stake collateral in WarrantyPool on-chain, then record the event."""
    agent = await db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")
    if agent.operator_id != operator.id:
        raise HTTPException(403, "Agent does not belong to your operator account")

    amount_wei = int(req.amount_wei)
    tx_hash = None

    if req.tx_hash is not None:
        # Frontend already staked via MetaMask — just record the event
        tx_hash = req.tx_hash
        logger.info(f"Stake recorded from frontend tx for agent {agent_id}: tx={tx_hash}")
    elif contracts.is_configured() and agent.chain_agent_id is not None:
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


@router.post("/{agent_id}/unstake", response_model=UnstakeResponse)
async def request_unstake(
    agent_id: int,
    req: UnstakeRequest,
    db: AsyncSession = Depends(get_db),
    operator: Operator = Depends(require_operator_key),
):
    """Request unstake from WarrantyPool on-chain, then record the event."""
    agent = await db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")
    if agent.operator_id != operator.id:
        raise HTTPException(403, "Agent does not belong to your operator account")

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


# ---------------------------------------------------------------------------
# Agent memory endpoints
# ---------------------------------------------------------------------------

class AddMemoryRequest(BaseModel):
    content: str
    metadata: dict | None = None


@router.get("/{agent_id}/memories", response_model=list[MemoryItem])
async def list_agent_memories(
    agent_id: int,
    memory_type: str | None = None,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """List recent memories for an agent (run outcomes, violations, context)."""
    agent = await db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")

    memories = await get_recent_memories(db, agent_id, limit=min(limit, 100), memory_type=memory_type)
    return [
        {
            "id": m.id,
            "run_id": m.run_id,
            "memory_type": m.memory_type,
            "content": m.content,
            "metadata": m.metadata_json,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in memories
    ]


@router.post("/{agent_id}/memories", response_model=AddMemoryResponse)
async def add_agent_memory(
    agent_id: int,
    req: AddMemoryRequest,
    db: AsyncSession = Depends(get_db),
    operator: Operator = Depends(require_operator_key),
):
    """Add a context memory for an agent (operator-only)."""
    agent = await db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")
    if agent.operator_id != operator.id:
        raise HTTPException(403, "Agent does not belong to your operator account")

    await store_context_memory(db, agent_id, req.content, req.metadata)
    return {"agent_id": agent_id, "status": "memory stored"}
