// ── Domain types for AgentBond frontend ─────────────────────────────────────

export interface Agent {
  id: number;
  operator_id: number;
  wallet_address: string;
  operator_wallet: string | null;
  metadata_uri: string;
  status: string;
  trust_score: number;
  total_runs: number;
  violations: number;
  active_version: string | null;
  chain_agent_id: string | null;
  created_at: string | null;
}

export interface DashboardStats {
  total_agents: number;
  total_runs: number;
  total_claims: number;
  total_violations: number;
}

export interface RunListItem {
  run_id: string;
  agent_id: number;
  policy_verdict: string;
  reason_codes: string[] | null;
  settlement_tx: string | null;
  evidence_hash: string | null;
  created_at: string | null;
}

export interface Run extends RunListItem {
  user_address: string | null;
  input_hash: string | null;
  output_hash: string | null;
  transcript: unknown;
}

export interface ClaimListItem {
  id: number;
  agent_id: number;
  run_id: string | null;
  reason_code: string;
  claimant_address: string;
  status: string;
  created_at: string | null;
}

export interface ClaimResult {
  claim_id: number;
  status: string;
  approved: boolean;
  reason: string;
}

export interface Score {
  agent_id: number;
  score: number;
  breakdown: ScoreBreakdown | null;
}

export interface ScoreBreakdown {
  base: number;
  violation_penalty: number;
  claim_penalty: number;
  recency_bonus: number;
}

export interface ScoreHistoryPoint {
  score: number;
  created_at: string;
}

export interface Policy {
  id: number;
  agent_id: number;
  policy_hash: string | null;
  rules: PolicyRules | null;
  status: string;
  chain_policy_id: string | null;
  chain_tx: string | null;
  created_at: string | null;
}

export interface PolicyRules {
  allowed_tools?: string[];
  prohibited_targets?: string[];
  max_value_per_action?: number;
  max_actions_per_window?: number;
  window_seconds?: number;
  required_data_freshness_seconds?: number;
  max_slippage_bps?: number;
}

export interface Memory {
  id: number;
  agent_id: number;
  memory_type: string;
  content: string;
  metadata: MemoryMetadata | null;
  created_at: string | null;
}

export interface MemoryMetadata {
  reason_codes?: string[];
}

export interface SSEEvent {
  event: string;
  data: SSEEventData;
}

export interface SSEEventData {
  verdict?: string;
  message?: string;
  run_id?: string;
  output?: string;
  reason_codes?: string[];
  [key: string]: unknown;
}

export interface ReplayResult {
  proof_valid: boolean;
  input_hash_match: boolean;
  policy_verdict: string;
  original_verdict: string;
  error?: string;
}

export interface RegisterAgentResult {
  id: number;
  wallet_address: string;
  metadata_uri: string;
  status: string;
  api_key?: string;
  chain_tx?: string;
  error?: string;
}

export interface PolicyRegisterResult {
  id: number;
  agent_id: number;
  policy_hash: string;
  status: string;
  chain_tx?: string;
  error?: string;
}

export interface StakeResult {
  agent_id: number;
  amount_wei: string;
  chain_tx?: string;
  error?: string;
}

export interface RunExecuteResult {
  run_id: string;
  agent_id: number;
  policy_verdict: string;
  reason_codes?: string[];
  output?: string;
  error?: string;
}

/** Generic result shape used by the Operator console ResultBox */
export interface OperationResult {
  error?: string;
  [key: string]: unknown;
}
