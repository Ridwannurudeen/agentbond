import axios from "axios";
import type {
  Agent, DashboardStats, RunListItem, Run, ClaimListItem, ClaimResult,
  Score, ScoreHistoryPoint, Policy, Memory, ReplayResult,
  RegisterAgentResult, PolicyRegisterResult, StakeResult, RunExecuteResult,
  SSEEventData,
} from "./types";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "/api",
});

export async function fetchDashboardStats(): Promise<DashboardStats> {
  const { data } = await api.get<DashboardStats>("/dashboard/stats");
  return data;
}

// legacy alias
export async function fetchStats(): Promise<DashboardStats> {
  return fetchDashboardStats();
}

export async function fetchAgents(): Promise<Agent[]> {
  const { data } = await api.get<Agent[]>("/agents");
  return data;
}

export async function fetchAgent(id: number): Promise<Agent> {
  const { data } = await api.get<Agent>(`/agents/${id}`);
  return data;
}

export async function registerAgent(
  walletAddress: string,
  metadataUri: string,
  extras?: { signature?: string; message?: string; chain_agent_id?: string; chain_tx?: string }
): Promise<RegisterAgentResult> {
  const { data } = await api.post<RegisterAgentResult>("/agents", {
    wallet_address: walletAddress,
    metadata_uri: metadataUri,
    ...extras,
  });
  return data;
}

export async function generateApiKey(walletAddress: string, signature?: string, message?: string) {
  const body = signature && message ? { signature, message } : {};
  const { data } = await api.post<{ operator_id: number; wallet_address: string; api_key: string }>(`/operators/${walletAddress}/api-key`, body);
  return data;
}

export async function fetchRuns(agentId?: number): Promise<RunListItem[]> {
  const params = agentId ? { agent_id: agentId } : {};
  const { data } = await api.get<RunListItem[]>("/runs", { params });
  return data;
}

export async function fetchRun(runId: string): Promise<Run> {
  const { data } = await api.get<Run>(`/runs/${runId}`);
  return data;
}

export async function executeRun(
  agentId: number,
  userInput: string,
  userAddress?: string,
  apiKey?: string,
  signature?: string,
  message?: string,
): Promise<RunExecuteResult> {
  const headers = apiKey ? { "X-API-Key": apiKey } : undefined;
  const { data } = await api.post<RunExecuteResult>("/runs", {
    agent_id: agentId,
    user_input: userInput,
    ...(userAddress ? { user_address: userAddress } : {}),
    ...(signature ? { signature, message } : {}),
  }, { headers });
  return data;
}

export async function replayRun(runId: string): Promise<ReplayResult> {
  const { data } = await api.get<ReplayResult>(`/runs/${runId}/replay`);
  return data;
}

export async function fetchClaims(agentId?: number): Promise<ClaimListItem[]> {
  const params = agentId ? { agent_id: agentId } : {};
  const { data } = await api.get<ClaimListItem[]>("/claims", { params });
  return data;
}

export async function submitClaim(
  runId: string,
  claimantAddress: string,
  reasonCode: string,
  signature: string,
  message: string,
  extras?: { chain_claim_id?: number; chain_submit_tx?: string }
): Promise<ClaimResult> {
  const { data } = await api.post<ClaimResult>("/claims", {
    run_id: runId,
    claimant_address: claimantAddress,
    reason_code: reasonCode,
    signature,
    message,
    ...extras,
  });
  return data;
}

export async function fetchScore(agentId: number): Promise<Score> {
  const { data } = await api.get<Score>(`/scores/${agentId}`);
  return data;
}

export async function fetchAllScores(): Promise<Score[]> {
  const { data } = await api.get<Score[]>("/scores");
  return data;
}

export async function fetchPolicies(agentId?: number): Promise<Policy[]> {
  const params = agentId ? { agent_id: agentId } : {};
  const { data } = await api.get<Policy[]>("/policies", { params });
  return data;
}

export async function registerPolicy(
  agentId: number,
  rules: object,
  extras?: { chain_policy_id?: string; chain_tx?: string },
  apiKey?: string
): Promise<PolicyRegisterResult> {
  const body = { agent_id: agentId, rules, ...extras };
  const { data } = apiKey
    ? await api.post<PolicyRegisterResult>("/policies", body, { headers: { "X-API-Key": apiKey } })
    : await api.post<PolicyRegisterResult>("/policies", body);
  return data;
}

export async function activatePolicy(policyId: number): Promise<Policy> {
  const { data } = await api.post<Policy>(`/policies/${policyId}/activate`);
  return data;
}

export async function stakeCollateral(
  agentId: number,
  amountWei: string,
  txHash?: string,
  apiKey?: string
): Promise<StakeResult> {
  const body = { amount_wei: amountWei, ...(txHash ? { tx_hash: txHash } : {}) };
  const { data } = apiKey
    ? await api.post<StakeResult>(`/agents/${agentId}/stake`, body, { headers: { "X-API-Key": apiKey } })
    : await api.post<StakeResult>(`/agents/${agentId}/stake`, body);
  return data;
}

export async function unstakeCollateral(agentId: number, amountWei: string): Promise<StakeResult> {
  const { data } = await api.post<StakeResult>(`/agents/${agentId}/unstake`, {
    amount_wei: amountWei,
  });
  return data;
}

export async function fetchAgentMemories(agentId: number, limit = 20): Promise<Memory[]> {
  const { data } = await api.get<Memory[]>(`/agents/${agentId}/memories`, { params: { limit } });
  return data;
}

export function streamRun(
  agentId: number,
  userInput: string,
  onEvent: (event: string, data: SSEEventData) => void,
  onDone: () => void,
  onError: (err: string) => void,
  auth?: { apiKey: string; signature: string; message: string },
): () => void {
  const baseUrl = import.meta.env.VITE_API_BASE_URL || "/api";
  const url = `${baseUrl}/runs/stream`;

  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (auth?.apiKey) headers["X-API-Key"] = auth.apiKey;

  const body: Record<string, unknown> = { agent_id: agentId, user_input: userInput };
  if (auth?.signature) body.signature = auth.signature;
  if (auth?.message) body.message = auth.message;

  fetch(url, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  })
    .then(async (res) => {
      if (!res.ok || !res.body) {
        onError(`HTTP ${res.status}`);
        return;
      }
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) { onDone(); break; }
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop() ?? "";
        for (const part of parts) {
          const line = part.replace(/^data:\s*/, "").trim();
          if (!line) continue;
          try {
            const parsed = JSON.parse(line);
            onEvent(parsed.event, parsed.data);
          } catch { /* ignore malformed */ }
        }
      }
    })
    .catch((err) => onError(err.message ?? "Stream failed"));

  return () => {}; // abort not needed for short runs
}

export default api;

export async function fetchScoreHistory(agentId: number): Promise<ScoreHistoryPoint[]> {
  const { data } = await api.get<ScoreHistoryPoint[]>(`/scores/${agentId}/history`);
  return data;
}
