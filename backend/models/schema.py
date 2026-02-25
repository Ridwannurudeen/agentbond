import enum
from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, DateTime, Text, Numeric, Enum, ForeignKey, JSON
)
from sqlalchemy.orm import relationship

from backend.db import Base


class AgentStatus(str, enum.Enum):
    active = "active"
    paused = "paused"
    retired = "retired"


class PolicyStatus(str, enum.Enum):
    active = "active"
    deprecated = "deprecated"


class ClaimStatus(str, enum.Enum):
    submitted = "submitted"
    verified = "verified"
    approved = "approved"
    rejected = "rejected"
    paid = "paid"


class Operator(Base):
    __tablename__ = "operators"

    id = Column(Integer, primary_key=True, autoincrement=True)
    wallet_address = Column(String(42), unique=True, nullable=False)
    webhook_url = Column(Text, nullable=True)
    api_key = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    agents = relationship("Agent", back_populates="operator")


class Agent(Base):
    __tablename__ = "agents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chain_agent_id = Column(Integer, unique=True, nullable=True)
    operator_id = Column(Integer, ForeignKey("operators.id"), nullable=False)
    metadata_uri = Column(Text, nullable=False)
    active_version = Column(Integer, default=0)
    status = Column(Enum(AgentStatus), default=AgentStatus.active)
    trust_score = Column(Integer, default=100)
    total_runs = Column(Integer, default=0)
    violations = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    operator = relationship("Operator", back_populates="agents")
    versions = relationship("AgentVersion", back_populates="agent")
    policies = relationship("Policy", back_populates="agent")
    runs = relationship("Run", back_populates="agent")
    claims = relationship("Claim", back_populates="agent")


class AgentVersion(Base):
    __tablename__ = "agent_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=False)
    version_hash = Column(String(66), nullable=False)
    policy_id = Column(Integer, ForeignKey("policies.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    agent = relationship("Agent", back_populates="versions")


class Policy(Base):
    __tablename__ = "policies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chain_policy_id = Column(Integer, unique=True, nullable=True)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=False)
    policy_hash = Column(String(66), nullable=False)
    rules_json = Column(JSON, nullable=False)
    status = Column(Enum(PolicyStatus), default=PolicyStatus.active)
    created_at = Column(DateTime, default=datetime.utcnow)

    agent = relationship("Agent", back_populates="policies")


class Run(Base):
    __tablename__ = "runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(66), unique=True, nullable=False)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=False)
    user_address = Column(String(42), nullable=True)
    input_hash = Column(String(66), nullable=True)
    output_hash = Column(String(66), nullable=True)
    transcript_json = Column(JSON, nullable=True)
    settlement_tx = Column(String(66), nullable=True)
    policy_verdict = Column(String(10), nullable=True)  # "pass" or "fail"
    reason_codes = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    agent = relationship("Agent", back_populates="runs")
    claims = relationship("Claim", back_populates="run")


class Claim(Base):
    __tablename__ = "claims"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chain_claim_id = Column(Integer, unique=True, nullable=True)
    run_id = Column(Integer, ForeignKey("runs.id"), nullable=False)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=False)
    claimant_address = Column(String(42), nullable=False)
    reason_code = Column(String(64), nullable=False)
    evidence_hash = Column(String(66), nullable=False)
    status = Column(Enum(ClaimStatus), default=ClaimStatus.submitted)
    payout_amount = Column(Numeric(precision=36, scale=18), nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    run = relationship("Run", back_populates="claims")
    agent = relationship("Agent", back_populates="claims")


class StakeEvent(Base):
    __tablename__ = "stake_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=False)
    event_type = Column(String(20), nullable=False)  # "stake", "unstake", "slash"
    amount = Column(Numeric(precision=36, scale=18), nullable=False)
    tx_hash = Column(String(66), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ReputationSnapshot(Base):
    __tablename__ = "reputation_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=False)
    score = Column(Integer, nullable=False)
    total_runs = Column(Integer, nullable=False)
    violations = Column(Integer, nullable=False)
    snapshot_hash = Column(String(66), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
