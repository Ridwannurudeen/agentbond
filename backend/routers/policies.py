"""Policy CRUD endpoints."""

import hashlib
import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db import get_db
from backend.models.schema import Policy, Agent, PolicyStatus

router = APIRouter(prefix="/api/policies", tags=["policies"])


class RegisterPolicyRequest(BaseModel):
    agent_id: int
    rules: dict


class ActivatePolicyRequest(BaseModel):
    agent_id: int


@router.post("")
async def register_policy(req: RegisterPolicyRequest, db: AsyncSession = Depends(get_db)):
    """Register a new policy for an agent."""
    agent = await db.get(Agent, req.agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")

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

    return {
        "id": policy.id,
        "agent_id": policy.agent_id,
        "policy_hash": policy.policy_hash,
        "rules": policy.rules_json,
        "status": policy.status.value,
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
        "created_at": policy.created_at.isoformat() if policy.created_at else None,
    }


@router.post("/{policy_id}/activate")
async def activate_policy(
    policy_id: int, req: ActivatePolicyRequest, db: AsyncSession = Depends(get_db)
):
    """Activate a policy for an agent (deprecates previous active policy)."""
    policy = await db.get(Policy, policy_id)
    if not policy:
        raise HTTPException(404, "Policy not found")

    if policy.agent_id != req.agent_id:
        raise HTTPException(400, "Policy does not belong to this agent")

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

    return {"policy_id": policy_id, "agent_id": req.agent_id, "status": "activated"}


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
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in policies
    ]
