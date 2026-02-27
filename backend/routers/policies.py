"""Policy CRUD endpoints."""

import asyncio
import hashlib
import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth import require_operator_key
from backend.contracts.interface import contracts
from backend.db import get_db
from backend.models.schema import Policy, Agent, Operator, PolicyStatus

router = APIRouter(prefix="/api/policies", tags=["policies"])
logger = logging.getLogger(__name__)


class RegisterPolicyRequest(BaseModel):
    agent_id: int
    rules: dict


class ActivatePolicyRequest(BaseModel):
    agent_id: int


@router.post("")
async def register_policy(
    req: RegisterPolicyRequest,
    db: AsyncSession = Depends(get_db),
    operator: Operator = Depends(require_operator_key),
):
    """Register a new policy for an agent."""
    agent = await db.get(Agent, req.agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")
    if agent.operator_id != operator.id:
        raise HTTPException(403, "Agent does not belong to your operator account")

    rules_str = json.dumps(req.rules, sort_keys=True)
    policy_hash = hashlib.sha256(rules_str.encode()).hexdigest()

    policy = Policy(
        agent_id=req.agent_id,
        policy_hash=policy_hash,
        rules_json=req.rules,
        status=PolicyStatus.active,
    )
    db.add(policy)
    await db.commit()
    await db.refresh(policy)

    # Wire up on-chain: register policy
    chain_policy_id = None
    chain_tx = None
    if contracts.is_configured() and agent.chain_agent_id is not None:
        try:
            policy_hash_bytes = bytes.fromhex(policy_hash)
            rules_uri = f"data:application/json,{rules_str}"
            chain_policy_id, chain_tx = await asyncio.to_thread(
                contracts.register_policy,
                agent.chain_agent_id,
                policy_hash_bytes,
                rules_uri,
            )
            policy.chain_policy_id = chain_policy_id
            await db.commit()
            logger.info(f"Policy {policy.id} registered on-chain: chainId={chain_policy_id} tx={chain_tx}")
        except Exception as e:
            logger.warning(f"On-chain register_policy failed (non-fatal): {e}")

    return {
        "id": policy.id,
        "agent_id": policy.agent_id,
        "policy_hash": policy.policy_hash,
        "rules": policy.rules_json,
        "status": policy.status.value,
        "chain_policy_id": chain_policy_id,
        "chain_tx": chain_tx,
    }


@router.get("/{policy_id}")
async def get_policy(policy_id: int, db: AsyncSession = Depends(get_db)):
    """Get policy details."""
    policy = await db.get(Policy, policy_id)
    if not policy:
        raise HTTPException(404, "Policy not found")

    return {
        "id": policy.id,
        "agent_id": policy.agent_id,
        "policy_hash": policy.policy_hash,
        "rules": policy.rules_json,
        "status": policy.status.value,
        "chain_policy_id": policy.chain_policy_id,
        "created_at": policy.created_at.isoformat() if policy.created_at else None,
    }


@router.post("/{policy_id}/activate")
async def activate_policy(
    policy_id: int,
    req: ActivatePolicyRequest,
    db: AsyncSession = Depends(get_db),
    operator: Operator = Depends(require_operator_key),
):
    """Activate a policy for an agent (deprecates previous active policy)."""
    policy = await db.get(Policy, policy_id)
    if not policy:
        raise HTTPException(404, "Policy not found")

    if policy.agent_id != req.agent_id:
        raise HTTPException(400, "Policy does not belong to this agent")

    agent = await db.get(Agent, req.agent_id)
    if not agent or agent.operator_id != operator.id:
        raise HTTPException(403, "Agent does not belong to your operator account")

    # Deprecate other active policies for this agent
    result = await db.execute(
        select(Policy).where(
            Policy.agent_id == req.agent_id,
            Policy.status == PolicyStatus.active,
            Policy.id != policy_id,
        )
    )
    for old_policy in result.scalars().all():
        old_policy.status = PolicyStatus.deprecated

    policy.status = PolicyStatus.active
    await db.commit()

    # Wire up on-chain: activate policy
    chain_tx = None
    if (
        contracts.is_configured()
        and agent
        and agent.chain_agent_id is not None
        and policy.chain_policy_id is not None
    ):
        try:
            chain_tx = await asyncio.to_thread(
                contracts.activate_policy,
                agent.chain_agent_id,
                policy.chain_policy_id,
            )
            logger.info(f"Policy {policy_id} activated on-chain: tx={chain_tx}")
        except Exception as e:
            logger.warning(f"On-chain activate_policy failed (non-fatal): {e}")

    return {"policy_id": policy_id, "agent_id": req.agent_id, "status": "activated", "chain_tx": chain_tx}


@router.get("")
async def list_policies(
    agent_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    """List policies, optionally filtered by agent."""
    query = select(Policy).order_by(Policy.id.desc())
    if agent_id:
        query = query.where(Policy.agent_id == agent_id)

    result = await db.execute(query)
    policies = result.scalars().all()

    return [
        {
            "id": p.id,
            "agent_id": p.agent_id,
            "policy_hash": p.policy_hash,
            "status": p.status.value,
            "chain_policy_id": p.chain_policy_id,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in policies
    ]
