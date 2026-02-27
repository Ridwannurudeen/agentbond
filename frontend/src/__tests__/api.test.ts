import { describe, it, expect, vi, beforeEach } from "vitest";
import axios from "axios";

// Mock axios so no real HTTP calls are made
vi.mock("axios", () => {
  const instance = {
    get: vi.fn(),
    post: vi.fn(),
  };
  return {
    default: {
      create: vi.fn(() => instance),
      ...instance,
    },
  };
});

// Import after mock is set up
import {
  fetchDashboardStats,
  fetchAgents,
  fetchAgent,
  fetchRuns,
  fetchRun,
  executeRun,
  replayRun,
  fetchClaims,
  submitClaim,
  fetchScore,
  fetchAllScores,
  fetchPolicies,
  registerPolicy,
  stakeCollateral,
  unstakeCollateral,
} from "../api";

// Grab the mocked instance axios.create() returned
import api from "../api";
const mockedApi = api as unknown as { get: ReturnType<typeof vi.fn>; post: ReturnType<typeof vi.fn> };

beforeEach(() => {
  vi.clearAllMocks();
});

// ---------------------------------------------------------------------------
// GET helpers
// ---------------------------------------------------------------------------

describe("fetchDashboardStats", () => {
  it("calls GET /dashboard/stats and returns data", async () => {
    const payload = { total_agents: 3, total_runs: 42 };
    mockedApi.get.mockResolvedValue({ data: payload });
    const result = await fetchDashboardStats();
    expect(mockedApi.get).toHaveBeenCalledWith("/dashboard/stats");
    expect(result).toEqual(payload);
  });
});

describe("fetchAgents", () => {
  it("calls GET /agents", async () => {
    mockedApi.get.mockResolvedValue({ data: [] });
    await fetchAgents();
    expect(mockedApi.get).toHaveBeenCalledWith("/agents");
  });
});

describe("fetchAgent", () => {
  it("calls GET /agents/{id}", async () => {
    const agent = { id: 7, trust_score: 85 };
    mockedApi.get.mockResolvedValue({ data: agent });
    const result = await fetchAgent(7);
    expect(mockedApi.get).toHaveBeenCalledWith("/agents/7");
    expect(result).toEqual(agent);
  });
});

describe("fetchRuns", () => {
  it("calls GET /runs with no params when agentId omitted", async () => {
    mockedApi.get.mockResolvedValue({ data: [] });
    await fetchRuns();
    expect(mockedApi.get).toHaveBeenCalledWith("/runs", { params: {} });
  });

  it("passes agent_id param when provided", async () => {
    mockedApi.get.mockResolvedValue({ data: [] });
    await fetchRuns(5);
    expect(mockedApi.get).toHaveBeenCalledWith("/runs", { params: { agent_id: 5 } });
  });
});

describe("fetchRun", () => {
  it("calls GET /runs/{runId}", async () => {
    mockedApi.get.mockResolvedValue({ data: { run_id: "abc" } });
    await fetchRun("abc");
    expect(mockedApi.get).toHaveBeenCalledWith("/runs/abc");
  });
});

describe("replayRun", () => {
  it("calls GET /runs/{runId}/replay", async () => {
    mockedApi.get.mockResolvedValue({ data: { proof_valid: true } });
    await replayRun("abc");
    expect(mockedApi.get).toHaveBeenCalledWith("/runs/abc/replay");
  });
});

describe("fetchClaims", () => {
  it("calls GET /claims with no params when agentId omitted", async () => {
    mockedApi.get.mockResolvedValue({ data: [] });
    await fetchClaims();
    expect(mockedApi.get).toHaveBeenCalledWith("/claims", { params: {} });
  });

  it("passes agent_id param when provided", async () => {
    mockedApi.get.mockResolvedValue({ data: [] });
    await fetchClaims(3);
    expect(mockedApi.get).toHaveBeenCalledWith("/claims", { params: { agent_id: 3 } });
  });
});

describe("fetchScore", () => {
  it("calls GET /scores/{agentId}", async () => {
    mockedApi.get.mockResolvedValue({ data: { score: 90 } });
    await fetchScore(2);
    expect(mockedApi.get).toHaveBeenCalledWith("/scores/2");
  });
});

describe("fetchAllScores", () => {
  it("calls GET /scores", async () => {
    mockedApi.get.mockResolvedValue({ data: [] });
    await fetchAllScores();
    expect(mockedApi.get).toHaveBeenCalledWith("/scores");
  });
});

describe("fetchPolicies", () => {
  it("calls GET /policies with no params when agentId omitted", async () => {
    mockedApi.get.mockResolvedValue({ data: [] });
    await fetchPolicies();
    expect(mockedApi.get).toHaveBeenCalledWith("/policies", { params: {} });
  });

  it("passes agent_id param when provided", async () => {
    mockedApi.get.mockResolvedValue({ data: [] });
    await fetchPolicies(9);
    expect(mockedApi.get).toHaveBeenCalledWith("/policies", { params: { agent_id: 9 } });
  });
});

// ---------------------------------------------------------------------------
// POST helpers
// ---------------------------------------------------------------------------

describe("executeRun", () => {
  it("POSTs to /runs with agent_id and user_input", async () => {
    const response = { run_id: "run-xyz", policy_verdict: "pass" };
    mockedApi.post.mockResolvedValue({ data: response });
    const result = await executeRun(1, "What is 2+2?");
    expect(mockedApi.post).toHaveBeenCalledWith("/runs", {
      agent_id: 1,
      user_input: "What is 2+2?",
    });
    expect(result).toEqual(response);
  });
});

describe("submitClaim", () => {
  it("POSTs to /claims with correct payload", async () => {
    const response = { claim_id: 10, status: "submitted" };
    mockedApi.post.mockResolvedValue({ data: response });
    const result = await submitClaim("run-1", 2, "0xabc", "POLICY_VIOLATION");
    expect(mockedApi.post).toHaveBeenCalledWith("/claims", {
      run_id: "run-1",
      agent_id: 2,
      claimant_address: "0xabc",
      reason_code: "POLICY_VIOLATION",
    });
    expect(result).toEqual(response);
  });
});

describe("registerPolicy", () => {
  it("POSTs to /policies with agent_id and rules", async () => {
    mockedApi.post.mockResolvedValue({ data: { id: 1 } });
    await registerPolicy(3, { allowed_tools: ["search"] });
    expect(mockedApi.post).toHaveBeenCalledWith("/policies", {
      agent_id: 3,
      rules: { allowed_tools: ["search"] },
    });
  });
});

describe("stakeCollateral", () => {
  it("POSTs to /agents/{id}/stake", async () => {
    mockedApi.post.mockResolvedValue({ data: { event: "staked" } });
    await stakeCollateral(4, "1000000000000000000");
    expect(mockedApi.post).toHaveBeenCalledWith("/agents/4/stake", {
      amount_wei: "1000000000000000000",
    });
  });
});

describe("unstakeCollateral", () => {
  it("POSTs to /agents/{id}/unstake", async () => {
    mockedApi.post.mockResolvedValue({ data: { event: "unstake_requested" } });
    await unstakeCollateral(4, "500000000000000000");
    expect(mockedApi.post).toHaveBeenCalledWith("/agents/4/unstake", {
      amount_wei: "500000000000000000",
    });
  });
});
