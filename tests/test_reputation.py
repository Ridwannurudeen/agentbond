"""Unit tests for reputation scoring engine."""

import hashlib
import json
from datetime import datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from unittest.mock import patch, AsyncMock

from backend.db import Base
from backend.models.schema import Agent, Operator, Run, Claim, ClaimStatus, ReputationSnapshot


TEST_DB_URL = "sqlite+aiosqlite:///test_reputation.db"


@pytest.fixture
async def db():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_maker() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


async def _create_agent(db: AsyncSession, total_runs: int = 0, violations: int = 0) -> Agent:
    """Helper to create an operator + agent with given stats."""
    operator = Operator(wallet_address=f"0xop_{total_runs}_{violations}_{id(db)}")
    db.add(operator)
    await db.flush()

    agent = Agent(
        operator_id=operator.id,
        metadata_uri="ipfs://QmTest",
        total_runs=total_runs,
        violations=violations,
        trust_score=100,
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return agent


async def _add_paid_claim(db: AsyncSession, agent: Agent) -> Claim:
    """Helper to create a run + paid claim for an agent."""
    run = Run(
        run_id=f"run-{agent.id}-{id(db)}-{datetime.utcnow().timestamp()}",
        agent_id=agent.id,
        policy_verdict="fail",
    )
    db.add(run)
    await db.flush()

    claim = Claim(
        run_id=run.id,
        agent_id=agent.id,
        claimant_address="0xclaimant",
        reason_code="TOOL_WHITELIST_VIOLATION",
        evidence_hash="abc123",
        status=ClaimStatus.paid,
    )
    db.add(claim)
    await db.commit()
    return claim


async def _add_clean_run(db: AsyncSession, agent: Agent, days_ago: int = 0) -> Run:
    """Helper to create a passing run, optionally backdated."""
    created = datetime.utcnow() - timedelta(days=days_ago)
    run = Run(
        run_id=f"clean-{agent.id}-{days_ago}-{datetime.utcnow().timestamp()}",
        agent_id=agent.id,
        policy_verdict="pass",
        created_at=created,
    )
    db.add(run)
    await db.commit()
    return run


class TestComputeScore:
    @pytest.mark.asyncio
    async def test_zero_runs_returns_perfect_score(self, db):
        from backend.services.reputation import compute_score

        agent = await _create_agent(db, total_runs=0, violations=0)
        result = await compute_score(db, agent.id)

        assert result["score"] == 100
        assert result["total_runs"] == 0
        assert result["violations"] == 0
        assert result["paid_claims"] == 0
        assert result["breakdown"]["violation_penalty"] == 0
        assert result["breakdown"]["claim_penalty"] == 0
        assert result["breakdown"]["recency_bonus"] == 0

    @pytest.mark.asyncio
    async def test_no_violations_full_score(self, db):
        from backend.services.reputation import compute_score

        agent = await _create_agent(db, total_runs=10, violations=0)
        result = await compute_score(db, agent.id)

        assert result["breakdown"]["violation_penalty"] == 0
        assert result["breakdown"]["claim_penalty"] == 0
        # Score is 100 + recency_bonus (capped at 100)
        assert result["score"] == 100

    @pytest.mark.asyncio
    async def test_all_violations_maximum_penalty(self, db):
        from backend.services.reputation import compute_score

        agent = await _create_agent(db, total_runs=10, violations=10)
        result = await compute_score(db, agent.id)

        # violation_ratio = 10/10 = 1.0, penalty = min(1.0*60, 60) = 60
        assert result["breakdown"]["violation_penalty"] == 60
        # Score = 100 - 60 - claim_penalty + recency_bonus
        assert result["score"] <= 40

    @pytest.mark.asyncio
    async def test_partial_violations_proportional_penalty(self, db):
        from backend.services.reputation import compute_score

        agent = await _create_agent(db, total_runs=10, violations=3)
        result = await compute_score(db, agent.id)

        # violation_ratio = 3/10 = 0.3, penalty = 0.3 * 60 = 18
        assert result["breakdown"]["violation_penalty"] == 18
        assert result["score"] == 82

    @pytest.mark.asyncio
    async def test_score_decreases_with_more_violations(self, db):
        from backend.services.reputation import compute_score

        agent_low = await _create_agent(db, total_runs=20, violations=2)
        agent_high = await _create_agent(db, total_runs=20, violations=10)

        score_low = await compute_score(db, agent_low.id)
        score_high = await compute_score(db, agent_high.id)

        assert score_low["score"] > score_high["score"]

    @pytest.mark.asyncio
    async def test_paid_claims_add_penalty(self, db):
        from backend.services.reputation import compute_score

        agent = await _create_agent(db, total_runs=10, violations=0)
        await _add_paid_claim(db, agent)

        result = await compute_score(db, agent.id)

        # claim_ratio = 1/10 = 0.1, penalty = 0.1 * 30 = 3
        assert result["paid_claims"] == 1
        assert result["breakdown"]["claim_penalty"] == 3.0
        assert result["score"] == 97

    @pytest.mark.asyncio
    async def test_recency_bonus_for_recent_clean_runs(self, db):
        from backend.services.reputation import compute_score

        agent = await _create_agent(db, total_runs=5, violations=1)
        # Add 4 clean runs within the last 7 days
        for i in range(4):
            await _add_clean_run(db, agent, days_ago=i)

        result = await compute_score(db, agent.id)

        # recency_bonus = min(4 * 0.5, 10) = 2.0
        assert result["breakdown"]["recency_bonus"] == 2.0

    @pytest.mark.asyncio
    async def test_recency_bonus_capped_at_10(self, db):
        from backend.services.reputation import compute_score

        agent = await _create_agent(db, total_runs=30, violations=0)
        # Add 25 clean runs within the last 7 days
        for i in range(25):
            await _add_clean_run(db, agent, days_ago=i % 7)

        result = await compute_score(db, agent.id)

        # recency_bonus = min(25 * 0.5, 10) = 10
        assert result["breakdown"]["recency_bonus"] == 10

    @pytest.mark.asyncio
    async def test_old_runs_get_no_recency_bonus(self, db):
        from backend.services.reputation import compute_score

        agent = await _create_agent(db, total_runs=5, violations=1)
        # All runs are 10 days old -- outside 7-day window
        for i in range(3):
            await _add_clean_run(db, agent, days_ago=10 + i)

        result = await compute_score(db, agent.id)
        assert result["breakdown"]["recency_bonus"] == 0

    @pytest.mark.asyncio
    async def test_score_never_below_zero(self, db):
        from backend.services.reputation import compute_score

        # All runs are violations + paid claims for maximum penalty
        agent = await _create_agent(db, total_runs=5, violations=5)
        for _ in range(5):
            await _add_paid_claim(db, agent)

        result = await compute_score(db, agent.id)

        # violation_penalty = 60, claim_penalty = min(5/5*30, 30) = 30
        # score = max(0, 100 - 60 - 30 + 0) = 10
        assert result["score"] >= 0

    @pytest.mark.asyncio
    async def test_score_never_above_100(self, db):
        from backend.services.reputation import compute_score

        agent = await _create_agent(db, total_runs=1, violations=0)
        # 20+ clean runs gives recency_bonus = 10
        for _ in range(25):
            await _add_clean_run(db, agent, days_ago=0)

        result = await compute_score(db, agent.id)

        # 100 - 0 - 0 + 10 = 110 -> capped at 100
        assert result["score"] == 100

    @pytest.mark.asyncio
    async def test_single_run_with_violation(self, db):
        from backend.services.reputation import compute_score

        agent = await _create_agent(db, total_runs=1, violations=1)
        result = await compute_score(db, agent.id)

        # violation_ratio = 1/1 = 1.0, penalty = 60
        assert result["breakdown"]["violation_penalty"] == 60
        assert result["score"] == 40

    @pytest.mark.asyncio
    async def test_nonexistent_agent_raises(self, db):
        from backend.services.reputation import compute_score

        with pytest.raises(ValueError, match="Agent 99999 not found"):
            await compute_score(db, 99999)

    @pytest.mark.asyncio
    async def test_many_runs_dilutes_violation_ratio(self, db):
        from backend.services.reputation import compute_score

        # 1 violation in 100 runs vs 1 violation in 2 runs
        agent_many = await _create_agent(db, total_runs=100, violations=1)
        agent_few = await _create_agent(db, total_runs=2, violations=1)

        score_many = await compute_score(db, agent_many.id)
        score_few = await compute_score(db, agent_few.id)

        assert score_many["score"] > score_few["score"]
        # 1/100*60 = 0.6 penalty vs 1/2*60 = 30 penalty
        assert score_many["breakdown"]["violation_penalty"] == 0.6
        assert score_few["breakdown"]["violation_penalty"] == 30


class TestSnapshotScore:
    @pytest.mark.asyncio
    async def test_snapshot_persists_record(self, db):
        from backend.services.reputation import snapshot_score
        from sqlalchemy import select

        agent = await _create_agent(db, total_runs=5, violations=1)

        with patch("backend.services.webhooks.notify_score_changed", new_callable=AsyncMock), \
             patch("backend.contracts.interface.contracts") as mock_contracts:
            mock_contracts.is_configured.return_value = False
            result = await snapshot_score(db, agent.id)

        # Verify snapshot was stored
        snapshots = await db.execute(
            select(ReputationSnapshot).where(ReputationSnapshot.agent_id == agent.id)
        )
        snapshot = snapshots.scalar_one()

        assert snapshot.agent_id == agent.id
        assert snapshot.score == result["score"]
        assert snapshot.total_runs == 5
        assert snapshot.violations == 1
        assert snapshot.snapshot_hash is not None

    @pytest.mark.asyncio
    async def test_snapshot_updates_agent_trust_score(self, db):
        from backend.services.reputation import snapshot_score

        agent = await _create_agent(db, total_runs=10, violations=5)

        with patch("backend.services.webhooks.notify_score_changed", new_callable=AsyncMock), \
             patch("backend.contracts.interface.contracts") as mock_contracts:
            mock_contracts.is_configured.return_value = False
            result = await snapshot_score(db, agent.id)

        await db.refresh(agent)
        assert agent.trust_score == result["score"]

    @pytest.mark.asyncio
    async def test_snapshot_hash_is_deterministic(self, db):
        from backend.services.reputation import snapshot_score

        agent = await _create_agent(db, total_runs=3, violations=0)

        with patch("backend.services.webhooks.notify_score_changed", new_callable=AsyncMock), \
             patch("backend.contracts.interface.contracts") as mock_contracts:
            mock_contracts.is_configured.return_value = False
            result = await snapshot_score(db, agent.id)

        # Verify hash matches manual computation
        payload = json.dumps(result, sort_keys=True)
        expected_hash = hashlib.sha256(payload.encode()).hexdigest()

        from sqlalchemy import select
        snapshots = await db.execute(
            select(ReputationSnapshot).where(ReputationSnapshot.agent_id == agent.id)
        )
        snapshot = snapshots.scalar_one()
        assert snapshot.snapshot_hash == expected_hash
