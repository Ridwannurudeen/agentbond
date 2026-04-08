/**
 * Tests for fetchAgentMemories and streamRun in api.ts
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

vi.mock("axios", () => {
  const instance = { get: vi.fn(), post: vi.fn() };
  return { default: { create: vi.fn(() => instance), ...instance } };
});

import { fetchAgentMemories, streamRun } from "../api";
import api from "../api";
const mockedApi = api as unknown as { get: ReturnType<typeof vi.fn>; post: ReturnType<typeof vi.fn> };

beforeEach(() => vi.clearAllMocks());
afterEach(() => vi.restoreAllMocks());

// ---------------------------------------------------------------------------
// fetchAgentMemories
// ---------------------------------------------------------------------------

describe("fetchAgentMemories", () => {
  it("calls GET /agents/{id}/memories with default limit", async () => {
    const payload = [
      { id: 1, memory_type: "success", content: "Passed all checks.", run_id: "abc", metadata: null, created_at: "2026-03-05T00:00:00" },
    ];
    mockedApi.get.mockResolvedValue({ data: payload });

    const result = await fetchAgentMemories(42);
    expect(mockedApi.get).toHaveBeenCalledWith("/agents/42/memories", { params: { limit: 20 } });
    expect(result).toEqual(payload);
  });

  it("passes custom limit", async () => {
    mockedApi.get.mockResolvedValue({ data: [] });
    await fetchAgentMemories(7, 50);
    expect(mockedApi.get).toHaveBeenCalledWith("/agents/7/memories", { params: { limit: 50 } });
  });

  it("returns empty array when no memories", async () => {
    mockedApi.get.mockResolvedValue({ data: [] });
    const result = await fetchAgentMemories(1);
    expect(result).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// streamRun
// ---------------------------------------------------------------------------

function makeReadableStream(chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  let i = 0;
  return new ReadableStream({
    pull(controller) {
      if (i < chunks.length) {
        controller.enqueue(encoder.encode(chunks[i++]));
      } else {
        controller.close();
      }
    },
  });
}

describe("streamRun", () => {
  const originalFetch = globalThis.fetch;

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  function mockFetch(sseLines: string[]) {
    const body = makeReadableStream(sseLines);
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      body,
      status: 200,
    });
  }

  it("calls POST /runs/stream with correct body", async () => {
    mockFetch([`data: {"event":"complete","data":{"run_id":"x"}}\n\n`]);

    await new Promise<void>((resolve) => {
      streamRun(5, "Hello", () => {}, resolve, () => resolve());
    });

    expect(globalThis.fetch).toHaveBeenCalledWith(
      expect.stringContaining("/runs/stream"),
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ agent_id: 5, user_input: "Hello" }),
      }),
    );
  });

  it("fires onEvent for each SSE message", async () => {
    const events = [
      `data: {"event":"memory_loaded","data":{"has_context":false}}\n\n`,
      `data: {"event":"inference_start","data":{"model":"CLAUDE_SONNET_4_6"}}\n\n`,
      `data: {"event":"complete","data":{"run_id":"abc","policy_verdict":"pass"}}\n\n`,
    ];
    mockFetch(events);

    const received: { event: string; data: Record<string, unknown> }[] = [];
    await new Promise<void>((resolve) => {
      streamRun(1, "test", (ev, data) => received.push({ event: ev, data }), resolve, () => resolve());
    });

    expect(received).toHaveLength(3);
    expect(received[0].event).toBe("memory_loaded");
    expect(received[1].event).toBe("inference_start");
    expect(received[2].event).toBe("complete");
    expect(received[2].data.run_id).toBe("abc");
  });

  it("calls onDone when stream ends", async () => {
    mockFetch([`data: {"event":"complete","data":{}}\n\n`]);

    const onDone = vi.fn();
    await new Promise<void>((resolve) => {
      streamRun(1, "test", () => {}, () => { onDone(); resolve(); }, () => resolve());
    });

    expect(onDone).toHaveBeenCalledOnce();
  });

  it("calls onError on HTTP failure", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500, body: null });

    const onError = vi.fn();
    await new Promise<void>((resolve) => {
      streamRun(1, "test", () => {}, () => resolve(), (err) => { onError(err); resolve(); });
    });

    expect(onError).toHaveBeenCalledWith("HTTP 500");
  });

  it("calls onError on network failure", async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(new Error("Network Error"));

    const onError = vi.fn();
    await new Promise<void>((resolve) => {
      streamRun(1, "test", () => {}, () => resolve(), (err) => { onError(err); resolve(); });
    });

    expect(onError).toHaveBeenCalledWith("Network Error");
  });

  it("handles multi-chunk SSE messages correctly", async () => {
    // Split a single SSE event across two chunks
    const chunks = [
      `data: {"event":"memory_loaded",`,
      `"data":{"has_context":true}}\n\ndata: {"event":"complete","data":{"run_id":"z"}}\n\n`,
    ];
    mockFetch(chunks);

    const received: string[] = [];
    await new Promise<void>((resolve) => {
      streamRun(1, "test", (ev) => received.push(ev), resolve, () => resolve());
    });

    expect(received).toContain("memory_loaded");
    expect(received).toContain("complete");
  });

  it("ignores malformed JSON lines without throwing", async () => {
    mockFetch([
      `data: not-valid-json\n\n`,
      `data: {"event":"complete","data":{}}\n\n`,
    ]);

    const received: string[] = [];
    await new Promise<void>((resolve) => {
      streamRun(1, "test", (ev) => received.push(ev), resolve, () => resolve());
    });

    // Only the valid event should be received
    expect(received).toEqual(["complete"]);
  });
});
