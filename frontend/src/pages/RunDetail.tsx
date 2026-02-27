import React, { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { fetchRun, replayRun, submitClaim } from "../api";
import { useWallet } from "../context/WalletContext";

const REASON_CODES = [
  "TOOL_WHITELIST_VIOLATION",
  "VALUE_LIMIT_EXCEEDED",
  "PROHIBITED_TARGET",
  "FREQUENCY_EXCEEDED",
  "STALE_DATA",
  "MODEL_MISMATCH",
];

export default function RunDetail() {
  const { id } = useParams<{ id: string }>();
  const { address } = useWallet();

  const [run, setRun] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [replay, setReplay] = useState<any>(null);
  const [replaying, setReplaying] = useState(false);

  // Claim form
  const [claimantAddress, setClaimantAddress] = useState("");
  const [reasonCode, setReasonCode] = useState(REASON_CODES[0]);
  const [submittingClaim, setSubmittingClaim] = useState(false);
  const [claimResult, setClaimResult] = useState<any>(null);
  const [claimError, setClaimError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    fetchRun(id)
      .then(setRun)
      .catch((err) => setError(err.response?.data?.detail || err.message || "Run not found"))
      .finally(() => setLoading(false));
  }, [id]);

  useEffect(() => {
    if (address) setClaimantAddress(address);
  }, [address]);

  const handleReplay = async () => {
    if (!id) return;
    setReplaying(true);
    setReplay(null);
    try {
      const result = await replayRun(id);
      setReplay(result);
    } catch (err: any) {
      setReplay({ error: err.response?.data?.detail || err.message });
    }
    setReplaying(false);
  };

  const handleClaim = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!run) return;
    setSubmittingClaim(true);
    setClaimResult(null);
    setClaimError(null);
    try {
      const res = await submitClaim(run.run_id, run.agent_id, claimantAddress, reasonCode);
      setClaimResult(res);
    } catch (err: any) {
      setClaimError(err.response?.data?.detail || err.message || "Failed to submit claim");
    }
    setSubmittingClaim(false);
  };

  if (loading)
    return <div style={{ textAlign: "center", paddingTop: 80, color: "#666" }}>Loading...</div>;
  if (error)
    return (
      <div style={{ background: "#1a0a0a", border: "1px solid #3a1a1a", borderRadius: 12, padding: 32, color: "#f44336" }}>
        {error}
      </div>
    );
  if (!run)
    return <div style={{ color: "#666", paddingTop: 40 }}>Run not found.</div>;

  const isFail = run.policy_verdict !== "pass";

  return (
    <div>
      <div style={{ marginBottom: 8 }}>
        <Link to={`/agents/${run.agent_id}`} style={{ fontSize: 13, color: "#666" }}>
          ← Agent #{run.agent_id}
        </Link>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 24 }}>
        <h1 style={{ marginBottom: 0 }}>Run Detail</h1>
        <span
          className={`badge badge-${run.policy_verdict === "pass" ? "pass" : "fail"}`}
          style={{ fontSize: 15 }}
        >
          {run.policy_verdict}
        </span>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <h3 style={{ marginBottom: 12 }}>Run Info</h3>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px 24px", fontSize: 13 }}>
          <div>
            <div style={{ color: "#666", marginBottom: 2 }}>Run ID</div>
            <div style={{ fontFamily: "monospace", wordBreak: "break-all" }}>{run.run_id}</div>
          </div>
          <div>
            <div style={{ color: "#666", marginBottom: 2 }}>Agent</div>
            <div><Link to={`/agents/${run.agent_id}`}>#{run.agent_id}</Link></div>
          </div>
          <div>
            <div style={{ color: "#666", marginBottom: 2 }}>User</div>
            <div style={{ fontFamily: "monospace" }}>{run.user_address || "—"}</div>
          </div>
          <div>
            <div style={{ color: "#666", marginBottom: 2 }}>Created</div>
            <div style={{ color: "#aaa" }}>
              {run.created_at ? new Date(run.created_at).toLocaleString() : "—"}
            </div>
          </div>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <h3 style={{ marginBottom: 12 }}>Proof References</h3>
        <div style={{ display: "flex", flexDirection: "column", gap: 10, fontSize: 13 }}>
          {[
            { label: "Input Hash", value: run.input_hash },
            { label: "Output Hash", value: run.output_hash },
            { label: "Settlement TX", value: run.settlement_tx },
          ].map(({ label, value }) => (
            <div key={label}>
              <div style={{ color: "#666", marginBottom: 2 }}>{label}</div>
              <div style={{ fontFamily: "monospace", color: value ? "#ccc" : "#444", wordBreak: "break-all" }}>
                {value || "—"}
              </div>
            </div>
          ))}
        </div>
      </div>

      {run.reason_codes && run.reason_codes.length > 0 && (
        <div className="card" style={{ marginBottom: 16, background: "#1a0a0a", border: "1px solid #3a1a1a" }}>
          <h3 style={{ marginBottom: 12, color: "#f44336" }}>Violations</h3>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {run.reason_codes.map((code: string, i: number) => (
              <span key={i} className="badge badge-fail">{code}</span>
            ))}
          </div>
        </div>
      )}

      <div className="card" style={{ marginBottom: 16 }}>
        <h3 style={{ marginBottom: 12 }}>Transcript</h3>
        <pre
          style={{
            background: "#0d0d15",
            padding: 16,
            borderRadius: 8,
            overflow: "auto",
            maxHeight: 400,
            fontSize: 13,
            lineHeight: 1.5,
          }}
        >
          {JSON.stringify(run.transcript, null, 2)}
        </pre>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <h3 style={{ marginBottom: 8 }}>Independent Replay</h3>
        <p style={{ marginBottom: 12, color: "#666", fontSize: 13 }}>
          Re-fetch proof from OpenGradient and re-evaluate policy independently.
        </p>
        <button onClick={handleReplay} disabled={replaying}>
          {replaying ? "Replaying..." : "↻ Replay & Verify"}
        </button>

        {replay && (
          <div style={{ marginTop: 16, padding: 16, background: "#0d0d15", borderRadius: 8, fontSize: 13 }}>
            {replay.error ? (
              <div style={{ color: "#f44336" }}>{replay.error}</div>
            ) : (
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                <div>
                  <div style={{ color: "#666", marginBottom: 2 }}>Proof Valid</div>
                  <div style={{ color: replay.proof_valid ? "#4caf50" : "#f44336", fontWeight: 600 }}>
                    {replay.proof_valid ? "Yes" : "No"}
                  </div>
                </div>
                <div>
                  <div style={{ color: "#666", marginBottom: 2 }}>Input Hash Match</div>
                  <div style={{ color: replay.input_hash_match ? "#4caf50" : "#f44336", fontWeight: 600 }}>
                    {replay.input_hash_match ? "Yes" : "No"}
                  </div>
                </div>
                <div>
                  <div style={{ color: "#666", marginBottom: 2 }}>Re-evaluated Verdict</div>
                  <span className={`badge badge-${replay.policy_verdict === "pass" ? "pass" : "fail"}`}>
                    {replay.policy_verdict}
                  </span>
                </div>
                <div>
                  <div style={{ color: "#666", marginBottom: 2 }}>Original Verdict</div>
                  <div style={{ color: "#aaa" }}>{replay.original_verdict}</div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Submit Claim — only shown for failed runs */}
      {isFail && (
        <div className="card" style={{ border: "1px solid #3a1a1a", background: "#0f0808" }}>
          <h3 style={{ marginBottom: 4 }}>Submit a Claim</h3>
          <p style={{ fontSize: 13, color: "#888", marginBottom: 16 }}>
            This run resulted in a policy violation. File a claim to request reimbursement.
          </p>
          <form onSubmit={handleClaim}>
            <div className="form-group">
              <label>
                Claimant Address{" "}
                {address && (
                  <span style={{ fontSize: 12, color: "#6c63ff", fontWeight: 400 }}>
                    (auto-filled from wallet)
                  </span>
                )}
              </label>
              <input
                value={claimantAddress}
                onChange={(e) => setClaimantAddress(e.target.value)}
                placeholder="0x..."
                required
              />
            </div>
            <div className="form-group">
              <label>Reason Code</label>
              <select
                value={reasonCode}
                onChange={(e) => setReasonCode(e.target.value)}
                style={{
                  background: "#1a1a2e",
                  border: "1px solid #2a2a3a",
                  color: "#e0e0e0",
                  padding: "10px 14px",
                  borderRadius: 8,
                  width: "100%",
                  fontSize: 14,
                }}
              >
                {REASON_CODES.map((code) => (
                  <option key={code} value={code}>{code}</option>
                ))}
              </select>
            </div>
            <button type="submit" disabled={submittingClaim} style={{ background: "#c0392b" }}>
              {submittingClaim ? "Submitting..." : "Submit Claim"}
            </button>
          </form>

          {claimError && (
            <div style={{ marginTop: 12, padding: 12, background: "#1a0a0a", borderRadius: 8, color: "#f44336", fontSize: 13 }}>
              {claimError}
            </div>
          )}

          {claimResult && (
            <div style={{ marginTop: 12, padding: 12, background: "#0d0d15", borderRadius: 8, fontSize: 13 }}>
              <p><strong>Claim ID:</strong> {claimResult.claim_id}</p>
              <p><strong>Status:</strong> {claimResult.status}</p>
              <p>
                <strong>Approved:</strong>{" "}
                <span style={{ color: claimResult.approved ? "#4caf50" : "#f44336", fontWeight: 600 }}>
                  {claimResult.approved ? "Yes" : "No"}
                </span>
              </p>
              <p><strong>Reason:</strong> {claimResult.reason}</p>
              <Link to="/claims" style={{ fontSize: 13, color: "#6c63ff", display: "block", marginTop: 8 }}>
                View all claims →
              </Link>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
