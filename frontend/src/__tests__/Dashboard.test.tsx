import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Dashboard from "../pages/Dashboard";

// Mock the API module — no real HTTP
vi.mock("../api", () => ({
  fetchDashboardStats: vi.fn(),
  fetchAgents: vi.fn(),
  fetchRuns: vi.fn(),
}));

import * as api from "../api";
const mockStats = api.fetchDashboardStats as ReturnType<typeof vi.fn>;
const mockAgents = api.fetchAgents as ReturnType<typeof vi.fn>;
const mockRuns = api.fetchRuns as ReturnType<typeof vi.fn>;

const renderDashboard = () =>
  render(
    <MemoryRouter>
      <Dashboard />
    </MemoryRouter>
  );

beforeEach(() => {
  vi.clearAllMocks();
});

// ---------------------------------------------------------------------------

describe("Dashboard — loading state", () => {
  it("shows Loading... while fetching", () => {
    // Never resolves during this test
    mockStats.mockReturnValue(new Promise(() => {}));
    mockAgents.mockReturnValue(new Promise(() => {}));
    mockRuns.mockReturnValue(new Promise(() => {}));

    renderDashboard();
    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });
});

describe("Dashboard — error state", () => {
  it("shows error message when API call fails", async () => {
    mockStats.mockRejectedValue({ message: "Network Error" });
    mockAgents.mockResolvedValue([]);
    mockRuns.mockResolvedValue([]);

    renderDashboard();
    await waitFor(() => expect(screen.getByText("Network Error")).toBeInTheDocument());
  });
});

describe("Dashboard — stat cards", () => {
  beforeEach(() => {
    mockStats.mockResolvedValue({
      total_agents: 5,
      total_runs: 20,
      total_claims: 3,
      total_violations: 4,
    });
    mockAgents.mockResolvedValue([]);
    mockRuns.mockResolvedValue([]);
  });

  it("renders Agents count", async () => {
    renderDashboard();
    await waitFor(() => expect(screen.getByText("5")).toBeInTheDocument());
  });

  it("renders Total Runs count", async () => {
    renderDashboard();
    await waitFor(() => expect(screen.getByText("20")).toBeInTheDocument());
  });

  it("renders Claims count", async () => {
    renderDashboard();
    await waitFor(() => expect(screen.getByText("3")).toBeInTheDocument());
  });

  it("renders pass rate correctly — (20-4)/20 = 80%", async () => {
    renderDashboard();
    await waitFor(() => expect(screen.getByText("80%")).toBeInTheDocument());
  });

  it("renders — for pass rate when total_runs is 0", async () => {
    mockStats.mockResolvedValue({ total_agents: 0, total_runs: 0, total_claims: 0 });
    renderDashboard();
    await waitFor(() => expect(screen.getByText("—")).toBeInTheDocument());
  });
});

describe("Dashboard — agents table", () => {
  beforeEach(() => {
    mockStats.mockResolvedValue({ total_agents: 1, total_runs: 0, total_claims: 0 });
    mockRuns.mockResolvedValue([]);
  });

  it("shows empty state when no agents", async () => {
    mockAgents.mockResolvedValue([]);
    renderDashboard();
    await waitFor(() =>
      expect(screen.getByText("No agents registered yet.")).toBeInTheDocument()
    );
  });

  it("renders agent row with id and metadata_uri", async () => {
    mockAgents.mockResolvedValue([
      {
        id: 1,
        metadata_uri: "ipfs://QmTest",
        status: "active",
        trust_score: 95,
        total_runs: 10,
        violations: 0,
      },
    ]);
    renderDashboard();
    await waitFor(() => expect(screen.getByText("#1")).toBeInTheDocument());
    expect(screen.getByText("ipfs://QmTest")).toBeInTheDocument();
    expect(screen.getByText("active")).toBeInTheDocument();
    expect(screen.getByText("95")).toBeInTheDocument();
  });

  it("renders multiple agents", async () => {
    mockAgents.mockResolvedValue([
      { id: 1, metadata_uri: "ipfs://A", status: "active", trust_score: 90, total_runs: 5, violations: 0 },
      { id: 2, metadata_uri: "ipfs://B", status: "paused", trust_score: 60, total_runs: 2, violations: 1 },
    ]);
    renderDashboard();
    await waitFor(() => {
      expect(screen.getByText("#1")).toBeInTheDocument();
      expect(screen.getByText("#2")).toBeInTheDocument();
    });
  });
});

describe("Dashboard — recent runs", () => {
  beforeEach(() => {
    mockStats.mockResolvedValue({ total_agents: 0, total_runs: 2, total_claims: 0 });
    mockAgents.mockResolvedValue([]);
  });

  it("shows empty runs message when no runs", async () => {
    mockRuns.mockResolvedValue([]);
    renderDashboard();
    await waitFor(() =>
      expect(
        screen.getByText("No runs yet. Select an agent and execute a run.")
      ).toBeInTheDocument()
    );
  });

  it("renders run rows with verdict badges", async () => {
    mockRuns.mockResolvedValue([
      {
        run_id: "abc123def456ghi",
        agent_id: 1,
        policy_verdict: "pass",
        settlement_tx: null,
        created_at: "2026-01-01T00:00:00",
      },
    ]);
    renderDashboard();
    await waitFor(() => expect(screen.getByText("pass")).toBeInTheDocument());
    expect(screen.getByText("abc123def456...")).toBeInTheDocument();
  });

  it("shows View all → link to /runs", async () => {
    mockRuns.mockResolvedValue([]);
    renderDashboard();
    await waitFor(() => {
      const link = screen.getByRole("link", { name: "View all →" });
      expect(link).toHaveAttribute("href", "/runs");
    });
  });
});
