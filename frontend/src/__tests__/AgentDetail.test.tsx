/**
 * Component tests for AgentDetail page — SSE streaming UI and memory panel.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

// ── Mock all API calls ────────────────────────────────────────────────────────
vi.mock("../api", () => ({
  fetchAgent: vi.fn(),
  fetchRuns: vi.fn(),
  fetchClaims: vi.fn(),
  fetchScore: vi.fn(),
  fetchScoreHistory: vi.fn(),
  fetchPolicies: vi.fn(),
  fetchAgentMemories: vi.fn(),
  activatePolicy: vi.fn(),
  streamRun: vi.fn(),
  generateApiKey: vi.fn(),
}));

// Mock the wallet context so tests have a signing wallet
vi.mock("../context/WalletContext", () => ({
  useWallet: () => ({
    address: "0xabc123",
    signer: { signMessage: vi.fn().mockResolvedValue("0xsig") },
    provider: null,
    chainId: null,
    connect: vi.fn(),
    disconnect: vi.fn(),
  }),
}));

// Mock buildRunMessage — the real impl uses crypto.subtle which isn't always
// available in CI jsdom/happy-dom environments. Tests only care about the UI
// flow, not the exact canonical message format.
vi.mock("../utils/runSignature", () => ({
  buildRunMessage: vi.fn().mockResolvedValue("AgentBond run\nAgent: 1\nPrompt: x\nTimestamp: 0"),
  sha256Hex: vi.fn().mockResolvedValue("deadbeef"),
}));

import {
  fetchAgent,
  fetchRuns,
  fetchClaims,
  fetchScore,
  fetchScoreHistory,
  fetchPolicies,
  fetchAgentMemories,
  streamRun,
  generateApiKey,
} from "../api";

import AgentDetail from "../pages/AgentDetail";

// ── Fixtures ──────────────────────────────────────────────────────────────────

const AGENT = {
  id: 1,
  status: "active",
  metadata_uri: "ipfs://QmTest",
  trust_score: 95,
  total_runs: 3,
  violations: 0,
  operator_id: 1,
};

const MEMORIES = [
  {
    id: 1,
    memory_type: "success",
    content: "Run passed all checks.",
    run_id: "abc",
    metadata: null,
    created_at: "2026-03-05T00:00:00",
  },
  {
    id: 2,
    memory_type: "violation",
    content: "Violated tool_not_allowed.",
    run_id: "def",
    metadata: { reason_codes: ["tool_not_allowed"] },
    created_at: "2026-03-05T01:00:00",
  },
  {
    id: 3,
    memory_type: "context",
    content: "Prefer ETH trades.",
    run_id: null,
    metadata: null,
    created_at: "2026-03-05T02:00:00",
  },
];

function setup(agentId = "1") {
  return render(
    <MemoryRouter initialEntries={[`/agents/${agentId}`]}>
      <Routes>
        <Route path="/agents/:id" element={<AgentDetail />} />
      </Routes>
    </MemoryRouter>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  (fetchAgent as ReturnType<typeof vi.fn>).mockResolvedValue(AGENT);
  (fetchRuns as ReturnType<typeof vi.fn>).mockResolvedValue([]);
  (fetchClaims as ReturnType<typeof vi.fn>).mockResolvedValue([]);
  (fetchScore as ReturnType<typeof vi.fn>).mockResolvedValue({ score: 95, snapshots: [] });
  (fetchScoreHistory as ReturnType<typeof vi.fn>).mockResolvedValue([]);
  (fetchPolicies as ReturnType<typeof vi.fn>).mockResolvedValue([]);
  (fetchAgentMemories as ReturnType<typeof vi.fn>).mockResolvedValue([]);
  (streamRun as ReturnType<typeof vi.fn>).mockImplementation(() => {});
  (generateApiKey as ReturnType<typeof vi.fn>).mockResolvedValue({
    operator_id: 1,
    wallet_address: "0xabc123",
    api_key: "test-key",
  });
});

afterEach(() => {
  vi.restoreAllMocks();
});

// ── Tests ─────────────────────────────────────────────────────────────────────

describe("AgentDetail — initial load", () => {
  it("shows agent heading after load", async () => {
    setup();
    await waitFor(() => expect(screen.getByText("Agent #1")).toBeInTheDocument());
  });

  it("calls fetchAgentMemories on mount", async () => {
    setup();
    await waitFor(() => expect(fetchAgentMemories).toHaveBeenCalledWith(1));
  });

  it("renders run form with textarea and execute button", async () => {
    setup();
    await waitFor(() => screen.getByText("Agent #1"));
    // textarea (not textbox role in all browsers, but should be)
    expect(screen.getByPlaceholderText(/current price of ETH/i)).toBeInTheDocument();
    // Button text is "Execute"
    expect(screen.getByRole("button", { name: /execute/i })).toBeInTheDocument();
  });
});

describe("AgentDetail — memory panel", () => {
  it("shows success memory content", async () => {
    (fetchAgentMemories as ReturnType<typeof vi.fn>).mockResolvedValue(MEMORIES);
    setup();
    await waitFor(() => expect(screen.getByText("Run passed all checks.")).toBeInTheDocument());
  });

  it("shows violation memory content", async () => {
    (fetchAgentMemories as ReturnType<typeof vi.fn>).mockResolvedValue(MEMORIES);
    setup();
    await waitFor(() => expect(screen.getByText("Violated tool_not_allowed.")).toBeInTheDocument());
  });

  it("shows context memory content", async () => {
    (fetchAgentMemories as ReturnType<typeof vi.fn>).mockResolvedValue(MEMORIES);
    setup();
    await waitFor(() => expect(screen.getByText("Prefer ETH trades.")).toBeInTheDocument());
  });

  it("shows empty state when no memories exist", async () => {
    (fetchAgentMemories as ReturnType<typeof vi.fn>).mockResolvedValue([]);
    setup();
    await waitFor(() =>
      expect(screen.getByText(/No memory yet/i)).toBeInTheDocument()
    );
  });

  it("renders memory type badges", async () => {
    (fetchAgentMemories as ReturnType<typeof vi.fn>).mockResolvedValue(MEMORIES);
    setup();
    await waitFor(() => screen.getByText("Prefer ETH trades."));
    // All three badge labels should appear
    expect(screen.getByText("success")).toBeInTheDocument();
    expect(screen.getByText("violation")).toBeInTheDocument();
    expect(screen.getByText("context")).toBeInTheDocument();
  });
});

describe("AgentDetail — SSE streaming run", () => {
  it("calls streamRun with correct agent id and input", async () => {
    setup();
    await waitFor(() => screen.getByText("Agent #1"));

    const textarea = screen.getByPlaceholderText(/current price of ETH/i);
    fireEvent.change(textarea, { target: { value: "test query" } });
    fireEvent.submit(textarea.closest("form")!);

    // handleRun is async (signs, generates key, then streams) — wait for streamRun
    await waitFor(() => expect(streamRun).toHaveBeenCalled());

    expect(streamRun).toHaveBeenCalledWith(
      1,
      "test query",
      expect.any(Function),
      expect.any(Function),
      expect.any(Function),
      expect.objectContaining({ apiKey: "test-key" }),
    );
  });

  it("disables execute button while streaming", async () => {
    (streamRun as ReturnType<typeof vi.fn>).mockImplementation(() => {});

    setup();
    await waitFor(() => screen.getByText("Agent #1"));

    const textarea = screen.getByPlaceholderText(/current price of ETH/i);
    fireEvent.change(textarea, { target: { value: "hello" } });
    fireEvent.submit(textarea.closest("form")!);

    // Button should now show "Running..." and be disabled
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /running/i })).toBeDisabled()
    );
  });

  it("displays 'Memory loaded' label when memory_loaded event fires", async () => {
    let capturedOnEvent: ((ev: string, data: Record<string, unknown>) => void) | null = null;

    (streamRun as ReturnType<typeof vi.fn>).mockImplementation(
      (_id, _input, onEvent) => { capturedOnEvent = onEvent; }
    );

    setup();
    await waitFor(() => screen.getByText("Agent #1"));

    const textarea = screen.getByPlaceholderText(/current price of ETH/i);
    fireEvent.change(textarea, { target: { value: "stream test" } });
    fireEvent.submit(textarea.closest("form")!);

    await waitFor(() => expect(capturedOnEvent).toBeTruthy());

    act(() => {
      capturedOnEvent!("memory_loaded", { has_context: false });
    });

    await waitFor(() =>
      expect(screen.getByText("Memory loaded")).toBeInTheDocument()
    );
  });

  it("displays 'Run stored' label after complete event", async () => {
    let capturedOnEvent: ((ev: string, data: Record<string, unknown>) => void) | null = null;
    let capturedOnDone: (() => void) | null = null;

    (streamRun as ReturnType<typeof vi.fn>).mockImplementation(
      (_id, _input, onEvent, onDone) => {
        capturedOnEvent = onEvent;
        capturedOnDone = onDone;
      }
    );

    setup();
    await waitFor(() => screen.getByText("Agent #1"));

    const textarea = screen.getByPlaceholderText(/current price of ETH/i);
    fireEvent.change(textarea, { target: { value: "final test" } });
    fireEvent.submit(textarea.closest("form")!);

    await waitFor(() => expect(capturedOnEvent).toBeTruthy());

    act(() => {
      capturedOnEvent!("complete", {
        run_id: "run-xyz",
        policy_verdict: "pass",
        output: "Agent response.",
        reason_codes: null,
      });
      capturedOnDone!();
    });

    await waitFor(() =>
      expect(screen.getByText("Run stored")).toBeInTheDocument()
    );
  });

  it("shows error message when onError is called", async () => {
    let capturedOnError: ((err: string) => void) | null = null;

    (streamRun as ReturnType<typeof vi.fn>).mockImplementation(
      (_id, _input, _onEvent, _onDone, onError) => { capturedOnError = onError; }
    );

    setup();
    await waitFor(() => screen.getByText("Agent #1"));

    const textarea = screen.getByPlaceholderText(/current price of ETH/i);
    fireEvent.change(textarea, { target: { value: "error test" } });
    fireEvent.submit(textarea.closest("form")!);

    await waitFor(() => expect(capturedOnError).toBeTruthy());

    act(() => { capturedOnError!("HTTP 500"); });

    await waitFor(() =>
      expect(screen.getByText("HTTP 500")).toBeInTheDocument()
    );
  });

  it("re-enables execute button after stream completes", async () => {
    let capturedOnDone: (() => void) | null = null;

    (streamRun as ReturnType<typeof vi.fn>).mockImplementation(
      (_id, _input, _onEvent, onDone) => { capturedOnDone = onDone; }
    );

    setup();
    await waitFor(() => screen.getByText("Agent #1"));

    const textarea = screen.getByPlaceholderText(/current price of ETH/i);
    fireEvent.change(textarea, { target: { value: "done test" } });
    fireEvent.submit(textarea.closest("form")!);

    // handleRun is async — wait for streamRun to be called and the onDone
    // callback to be captured before invoking it.
    await waitFor(() => expect(capturedOnDone).toBeTruthy());

    // Verify it's disabled while running
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /running/i })).toBeDisabled()
    );

    act(() => { capturedOnDone!(); });

    // After done, button returns to "Execute" and is enabled
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /execute/i })).not.toBeDisabled()
    );
  });
});
