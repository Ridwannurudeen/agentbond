import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import Runs from "../pages/Runs";

vi.mock("../api", () => ({
  fetchRuns: vi.fn(),
}));

import * as api from "../api";
const mockFetchRuns = api.fetchRuns as ReturnType<typeof vi.fn>;

const RUNS = [
  { run_id: "run-pass-001", agent_id: 1, policy_verdict: "pass", reason_codes: [], settlement_tx: "0xabc", created_at: "2026-01-01T00:00:00" },
  { run_id: "run-fail-002", agent_id: 2, policy_verdict: "fail", reason_codes: ["TOOL_WHITELIST_VIOLATION"], settlement_tx: null, created_at: "2026-01-02T00:00:00" },
  { run_id: "run-pass-003", agent_id: 1, policy_verdict: "pass", reason_codes: [], settlement_tx: null, created_at: "2026-01-03T00:00:00" },
];

const renderRuns = () =>
  render(
    <MemoryRouter>
      <Runs />
    </MemoryRouter>
  );

beforeEach(() => {
  vi.clearAllMocks();
});

// ---------------------------------------------------------------------------

describe("Runs — loading and error", () => {
  it("shows loading spinner initially", () => {
    mockFetchRuns.mockReturnValue(new Promise(() => {}));
    renderRuns();
    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });

  it("shows error message on fetch failure", async () => {
    mockFetchRuns.mockRejectedValue({ message: "Server Error" });
    renderRuns();
    await waitFor(() => expect(screen.getByText("Server Error")).toBeInTheDocument());
  });
});

describe("Runs — displays all runs", () => {
  beforeEach(() => {
    mockFetchRuns.mockResolvedValue(RUNS);
  });

  it("shows run count", async () => {
    renderRuns();
    await waitFor(() => expect(screen.getByText("3 runs")).toBeInTheDocument());
  });

  it("renders pass and fail verdict badges", async () => {
    renderRuns();
    await waitFor(() => {
      expect(screen.getAllByText("pass")).toHaveLength(2);
      expect(screen.getByText("fail")).toBeInTheDocument();
    });
  });

  it("renders violation reason codes for failed runs", async () => {
    renderRuns();
    await waitFor(() =>
      expect(screen.getByText("TOOL_WHITELIST_VIOLATION")).toBeInTheDocument()
    );
  });

  it("shows — for runs without settlement tx", async () => {
    renderRuns();
    await waitFor(() => {
      const dashes = screen.getAllByText("—");
      expect(dashes.length).toBeGreaterThan(0);
    });
  });
});

describe("Runs — verdict filter", () => {
  beforeEach(() => {
    mockFetchRuns.mockResolvedValue(RUNS);
  });

  it("filters to pass runs only", async () => {
    renderRuns();
    await waitFor(() => screen.getByText("3 runs"));

    fireEvent.click(screen.getByRole("button", { name: "Pass" }));
    expect(screen.getByText("2 runs (pass)")).toBeInTheDocument();
    expect(screen.getAllByText("pass")).toHaveLength(2);
    expect(screen.queryByText("fail")).not.toBeInTheDocument();
  });

  it("filters to fail runs only", async () => {
    renderRuns();
    await waitFor(() => screen.getByText("3 runs"));

    fireEvent.click(screen.getByRole("button", { name: "Fail" }));
    expect(screen.getByText("1 run (fail)")).toBeInTheDocument();
    expect(screen.getByText("fail")).toBeInTheDocument();
  });

  it("restores all runs when All is clicked", async () => {
    renderRuns();
    await waitFor(() => screen.getByText("3 runs"));

    fireEvent.click(screen.getByRole("button", { name: "Fail" }));
    fireEvent.click(screen.getByRole("button", { name: "All" }));
    expect(screen.getByText("3 runs")).toBeInTheDocument();
  });
});

describe("Runs — empty filter result", () => {
  it("shows empty message when filter matches nothing", async () => {
    mockFetchRuns.mockResolvedValue([
      { run_id: "run-pass-x", agent_id: 1, policy_verdict: "pass", reason_codes: [], settlement_tx: null, created_at: null },
    ]);
    renderRuns();
    await waitFor(() => screen.getByText("1 run"));

    fireEvent.click(screen.getByRole("button", { name: "Fail" }));
    expect(screen.getByText("No runs match the current filter.")).toBeInTheDocument();
  });
});

describe("Runs — agent filter", () => {
  it("calls fetchRuns with agent_id when filter form is submitted", async () => {
    mockFetchRuns.mockResolvedValue([]);
    const user = userEvent.setup();
    renderRuns();
    await waitFor(() => screen.getByText("0 runs"));

    const input = screen.getByPlaceholderText("All agents");
    await user.clear(input);
    await user.type(input, "3");
    fireEvent.click(screen.getByRole("button", { name: "Filter" }));

    await waitFor(() =>
      expect(mockFetchRuns).toHaveBeenCalledWith(3)
    );
  });
});

describe("Runs — refresh button", () => {
  it("re-fetches data on refresh click", async () => {
    mockFetchRuns.mockResolvedValue(RUNS);
    renderRuns();
    await waitFor(() => screen.getByText("3 runs"));

    mockFetchRuns.mockResolvedValue([]);
    fireEvent.click(screen.getByRole("button", { name: "↻ Refresh" }));

    await waitFor(() => expect(screen.getByText("0 runs")).toBeInTheDocument());
    expect(mockFetchRuns).toHaveBeenCalledTimes(2);
  });
});
