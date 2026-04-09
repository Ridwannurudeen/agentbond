/**
 * Build a canonical per-run authorization message and its SHA-256 prompt hash.
 *
 * The backend requires every run to be signed by the operator wallet with a
 * message that binds to:
 *   - the agent id (prevents cross-agent replay)
 *   - a SHA-256 hash of the prompt (prevents prompt swap)
 *   - a recent UNIX timestamp (prevents long-term replay, 5 min window)
 *
 * Keeping this in one place guarantees the frontend and backend agree on the
 * exact format; any drift breaks auth loudly instead of silently.
 */
export async function sha256Hex(input: string): Promise<string> {
  const bytes = new TextEncoder().encode(input);
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

export async function buildRunMessage(agentId: number, userInput: string): Promise<string> {
  const promptHash = await sha256Hex(userInput);
  const timestamp = Math.floor(Date.now() / 1000);
  return [
    "AgentBond run",
    `Agent: ${agentId}`,
    `Prompt: ${promptHash}`,
    `Timestamp: ${timestamp}`,
  ].join("\n");
}
