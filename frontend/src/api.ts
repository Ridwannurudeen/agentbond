import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "/api",
});

export async function fetchDashboardStats() {
  const { data } = await api.get("/dashboard/stats");
  return data;
}

// legacy alias
export async function fetchStats() {
  return fetchDashboardStats();
}

export async function fetchAgents() {
  const { data } = await api.get("/agents");
  return data;
}

export async function fetchAgent(id: number) {
  const { data } = await api.get(`/agents/${id}`);
  return data;
}

export async function registerAgent(
  walletAddress: string,
  metadataUri: string,
  extras?: { signature?: string; message?: string; chain_agent_id?: string; chain_tx?: string }
) {
  const { data } = await api.post("/agents", {
    wallet_address: walletAddress,
    metadata_uri: metadataUri,
    ...extras,
  });
  return data;
}

export async function generateApiKey(walletAddress: string, signature?: string, message?: string) {
  const body = signature && message ? { signature, message } : {};
  const { data } = await api.post(`/operators/${walletAddress}/api-key`, body);
  return data as { operator_id: number; wallet_address: string; api_key: string };
}

export async function fetchRuns(agentId?: number) {
  const params = agentId ? { agent_id: agentId } : {};
  const { data } = await api.get("/runs", { params });
  return data;
}

export async function fetchRun(runId: string) {
  const { data } = await api.get(`/runs/${runId}`);
  return data;
}

export async function executeRun(
  agentId: number,
  userInput: string,
  userAddress?: string,
  apiKey?: string,
  signature?: string,
  message?: string,
) {
  const headers = apiKey ? { "X-API-Key": apiKey } : undefined;
  const { data } = await api.post("/runs", {
    agent_id: agentId,
    user_input: userInput,
    ...(userAddress ? { user_address: userAddress } : {}),
    ...(signature ? { signature, message } : {}),
  }, { headers });
  return data;
}

export async function replayRun(runId: string) {
  const { data } = await api.get(`/runs/${runId}/replay`);
  return data;
}

export async function fetchClaims(agentId?: number) {
  const params = agentId ? { agent_id: agentId } : {};
  const { data } = await api.get("/claims", { params });
  return data;
}

export async function submitClaim(
  runId: string,
  agentId: number,
  claimantAddress: string,
  reasonCode: string
) {
  const { data } = await api.post("/claims", {
    run_id: runId,
    agent_id: agentId,
    claimant_address: claimantAddress,
    reason_code: reasonCode,
  });
  return data;
}

export async function fetchScore(agentId: number) {
  const { data } = await api.get(`/scores/${agentId}`);
  return data;
}

export async function fetchAllScores() {
  const { data } = await api.get("/scores");
  return data;
}

export async function fetchPolicies(agentId?: number) {
  const params = agentId ? { agent_id: agentId } : {};
  const { data } = await api.get("/policies", { params });
  return data;
}

export async function registerPolicy(
  agentId: number,
  rules: object,
  extras?: { chain_policy_id?: string; chain_tx?: string },
  apiKey?: string
) {
  const body = { agent_id: agentId, rules, ...extras };
  const { data } = apiKey
    ? await api.post("/policies", body, { headers: { "X-API-Key": apiKey } })
    : await api.post("/policies", body);
  return data;
}

export async function activatePolicy(policyId: number) {
  const { data } = await api.post(`/policies/${policyId}/activate`);
  return data;
}

export async function stakeCollateral(
  agentId: number,
  amountWei: string,
  txHash?: string,
  apiKey?: string
) {
  const body = { amount_wei: amountWei, ...(txHash ? { tx_hash: txHash } : {}) };
  const { data } = apiKey
    ? await api.post(`/agents/${agentId}/stake`, body, { headers: { "X-API-Key": apiKey } })
    : await api.post(`/agents/${agentId}/stake`, body);
  return data;
}

export async function unstakeCollateral(agentId: number, amountWei: string) {
  const { data } = await api.post(`/agents/${agentId}/unstake`, {
    amount_wei: amountWei,
  });
  return data;
}

export async function fetchAgentMemories(agentId: number, limit = 20) {
  const { data } = await api.get(`/agents/${agentId}/memories`, { params: { limit } });
  return data;
}

export function streamRun(
  agentId: number,
  userInput: string,
  onEvent: (event: string, data: any) => void,
  onDone: () => void,
  onError: (err: string) => void,
): () => void {
  const baseUrl = import.meta.env.VITE_API_BASE_URL || "/api";
  const url = `${baseUrl}/runs/stream`;

  fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ agent_id: agentId, user_input: userInput }),
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
