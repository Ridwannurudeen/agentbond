"""Agent memory service — stores run context per agent and injects it into LLM prompts.

Each run's outcome (pass/fail, violations, score change) is stored as a structured
memory. Before execution, recent memories are retrieved and injected into the system
prompt so the LLM has awareness of the agent's behavioural history.
"""

import logging
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.schema import AgentMemory, Agent, ReputationSnapshot

logger = logging.getLogger(__name__)

# How many recent memories to inject into the LLM context
MEMORY_CONTEXT_LIMIT = 10


async def store_run_memory(
    db: AsyncSession,
    agent_id: int,
    run_id: str,
    verdict: str,
    reason_codes: list[str] | None,
    trust_score: int,
) -> None:
    """Store a memory record after a run completes."""
    if verdict == "fail" and reason_codes:
        memory_type = "violation"
        content = (
            f"Run {run_id[:8]} failed policy check. "
            f"Violations: {', '.join(reason_codes)}. "
            f"Trust score after: {trust_score}."
        )
        meta = {"reason_codes": reason_codes, "trust_score": trust_score}
    else:
        memory_type = "success"
        content = (
            f"Run {run_id[:8]} passed all policy checks. "
            f"Trust score: {trust_score}."
        )
        meta = {"trust_score": trust_score}

    memory = AgentMemory(
        agent_id=agent_id,
        run_id=run_id,
        memory_type=memory_type,
        content=content,
        metadata_json=meta,
    )
    db.add(memory)
    # caller commits


async def store_context_memory(
    db: AsyncSession,
    agent_id: int,
    content: str,
    metadata: dict | None = None,
) -> None:
    """Store a free-form context memory (e.g. operator notes, config changes)."""
    memory = AgentMemory(
        agent_id=agent_id,
        run_id=None,
        memory_type="context",
        content=content,
        metadata_json=metadata,
    )
    db.add(memory)
    await db.commit()


async def get_recent_memories(
    db: AsyncSession,
    agent_id: int,
    limit: int = MEMORY_CONTEXT_LIMIT,
    memory_type: str | None = None,
) -> list[AgentMemory]:
    """Retrieve the most recent memories for an agent."""
    query = (
        select(AgentMemory)
        .where(AgentMemory.agent_id == agent_id)
        .order_by(AgentMemory.id.desc())
        .limit(limit)
    )
    if memory_type:
        query = query.where(AgentMemory.memory_type == memory_type)

    result = await db.execute(query)
    memories = result.scalars().all()
    return list(reversed(memories))  # chronological order


async def build_memory_context(
    db: AsyncSession,
    agent_id: int,
) -> str:
    """Build a system-prompt memory block from recent agent history.

    Returns an empty string if there are no memories yet (first run).
    """
    memories = await get_recent_memories(db, agent_id, limit=MEMORY_CONTEXT_LIMIT)
    if not memories:
        return ""

    agent = await db.get(Agent, agent_id)
    lines = [
        f"## Agent Behavioural Memory (agent_id={agent_id})",
        f"Total runs: {agent.total_runs if agent else '?'}, "
        f"Violations: {agent.violations if agent else '?'}, "
        f"Trust score: {agent.trust_score if agent else '?'}",
        "",
        "Recent history (oldest → newest):",
    ]
    for m in memories:
        ts = m.created_at.strftime("%Y-%m-%d %H:%M") if m.created_at else "?"
        lines.append(f"  [{ts}] [{m.memory_type.upper()}] {m.content}")

    lines.append(
        "\nUse this context to avoid repeating past violations and maintain compliance."
    )
    return "\n".join(lines)
