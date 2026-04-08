"""Pydantic response models for all API endpoints."""

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

class HealthChecks(BaseModel):
    database: str

class HealthResponse(BaseModel):
    status: str
    service: str
    checks: HealthChecks


# ---------------------------------------------------------------------------
# Operators
# ---------------------------------------------------------------------------

class OperatorKeyResponse(BaseModel):
    operator_id: int
    wallet_address: str
    api_key: str


class WebhookDeliveryItem(BaseModel):
    id: int
    agent_id: int | None
    event_type: str
    webhook_url: str
    attempt: int
    status_code: int | None
    success: bool
    error_message: str | None
    duration_ms: int | None
    created_at: str | None


# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------

class RegisterAgentResponse(BaseModel):
    id: int
    operator_id: int
    metadata_uri: str
    status: str
    trust_score: int
    chain_agent_id: int | None
    chain_tx: str | None


class AgentDetailResponse(BaseModel):
    id: int
    operator_id: int
    operator_wallet: str | None
    metadata_uri: str
    active_version: int | None
    status: str
    trust_score: int
    total_runs: int
    violations: int
    chain_agent_id: int | None
    created_at: str | None


class AgentListItem(BaseModel):
    id: int
    operator_id: int
    metadata_uri: str
    status: str
    trust_score: int
    total_runs: int
    violations: int
    chain_agent_id: int | None


class PublishVersionResponse(BaseModel):
    version_id: int
    agent_id: int
    version_hash: str
    chain_version_id: int | None
    chain_tx: str | None


class SetStatusResponse(BaseModel):
    id: int
    status: str


class WebhookConfigResponse(BaseModel):
    agent_id: int
    operator_id: int
    webhook_url: str | None


class StakeResponse(BaseModel):
    agent_id: int
    amount_wei: str
    event: str
    tx_hash: str | None


class UnstakeResponse(BaseModel):
    agent_id: int
    amount_wei: str
    event: str
    tx_hash: str | None


class MemoryItem(BaseModel):
    id: int
    run_id: str | None
    memory_type: str
    content: str
    metadata: dict | None
    created_at: str | None


class AddMemoryResponse(BaseModel):
    agent_id: int
    status: str


# ---------------------------------------------------------------------------
# Runs
# ---------------------------------------------------------------------------

class ExecuteRunResponse(BaseModel):
    run_id: str
    agent_id: int
    output: str
    policy_verdict: str
    reason_codes: list[str] | None
    settlement_tx: str | None
    verified: bool
    evidence_hash: str


class RunDetailResponse(BaseModel):
    id: int
    run_id: str
    agent_id: int
    user_address: str | None
    input_hash: str | None
    output_hash: str | None
    transcript: list | None
    settlement_tx: str | None
    verified: bool
    policy_verdict: str | None
    reason_codes: list[str] | None
    created_at: str | None


class ReplayRunResponse(BaseModel):
    run_id: str
    proof_valid: bool
    input_hash_match: bool
    output_hash_match: bool
    policy_verdict: str
    reason_codes: list[str]
    evidence_hash: str
    original_verdict: str | None


class RunListItem(BaseModel):
    id: int
    run_id: str
    agent_id: int
    policy_verdict: str | None
    verified: bool
    settlement_tx: str | None
    created_at: str | None


# ---------------------------------------------------------------------------
# Claims
# ---------------------------------------------------------------------------

class SubmitClaimResponse(BaseModel):
    claim_id: int
    status: str
    approved: bool
    reason: str
    evidence_hash: str
    chain_claim_id: int | None
    chain_submit_tx: str | None
    chain_payout_tx: str | None


class ClaimDetailResponse(BaseModel):
    id: int
    run_id: str | None
    agent_id: int
    claimant_address: str
    reason_code: str
    evidence_hash: str | None
    status: str
    payout_amount: str | None
    chain_claim_id: int | None
    resolved_at: str | None
    created_at: str | None


class ClaimListItem(BaseModel):
    id: int
    run_id: str | None
    agent_id: int
    reason_code: str
    status: str
    chain_claim_id: int | None
    created_at: str | None


# ---------------------------------------------------------------------------
# Policies
# ---------------------------------------------------------------------------

class RegisterPolicyResponse(BaseModel):
    id: int
    agent_id: int
    policy_hash: str
    rules: dict
    status: str
    chain_policy_id: int | None
    chain_tx: str | None


class PolicyDetailResponse(BaseModel):
    id: int
    agent_id: int
    policy_hash: str
    rules: dict
    status: str
    chain_policy_id: int | None
    created_at: str | None


class ActivatePolicyResponse(BaseModel):
    policy_id: int
    agent_id: int
    status: str
    chain_tx: str | None


class PolicyListItem(BaseModel):
    id: int
    agent_id: int
    policy_hash: str
    status: str
    chain_policy_id: int | None
    created_at: str | None


# ---------------------------------------------------------------------------
# Scores
# ---------------------------------------------------------------------------

class ScoreBreakdown(BaseModel):
    base: int
    violation_penalty: float
    claim_penalty: float
    recency_bonus: float


class ScoreResponse(BaseModel):
    agent_id: int
    score: int
    total_runs: int
    violations: int
    paid_claims: int
    breakdown: ScoreBreakdown


class ScoreHistoryItem(BaseModel):
    id: int
    score: int
    total_runs: int
    violations: int
    snapshot_hash: str | None
    created_at: str | None


class DashboardStats(BaseModel):
    total_agents: int
    total_runs: int
    total_claims: int
    paid_claims: int
    total_violations: int
