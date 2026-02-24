import axios from "axios";

const api = axios.create({
  baseURL: "/api",
});

export async function fetchStats() {
  const { data } = await api.get("/dashboard/stats");
  return data;
}

export async function fetchAgents() {
  const { data } = await api.get("/agents");
  return data;
}

export async function fetchAgent(id: number) {
  const { data } = await api.get(`/agents/${id}`);
  return data;
}

export async function registerAgent(walletAddress: string, metadataUri: string) {
  const { data } = await api.post("/agents", {
    wallet_address: walletAddress,
    metadata_uri: metadataUri,
  });
  return data;
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

export async function executeRun(agentId: number, userInput: string) {
  const { data } = await api.post("/runs", {
    agent_id: agentId,
    user_input: userInput,
  });
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

export async function fetchPolicies(agentId?: number) {
  const params = agentId ? { agent_id: agentId } : {};
  const { data } = await api.get("/policies", { params });
  return data;
}

export async function registerPolicy(agentId: number, rules: object) {
  const { data } = await api.post("/policies", {
    agent_id: agentId,
    rules,
  });
  return data;
}

export async function stakeCollateral(agentId: number, amountWei: string) {
  const { data } = await api.post(`/agents/${agentId}/stake`, {
    amount_wei: amountWei,
  });
  return data;
}

export default api;
