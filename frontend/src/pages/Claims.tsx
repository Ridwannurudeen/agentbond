import React, { useEffect, useState } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { fetchClaims, submitClaim } from "../api";
import { useWallet } from "../context/WalletContext";

const REASON_CODES = [
  "TOOL_WHITELIST_VIOLATION",
  "VALUE_LIMIT_EXCEEDED",
  "PROHIBITED_TARGET",
  "FREQUENCY_EXCEEDED",
  "STALE_DATA",
  "MODEL_MISMATCH",
];

export default function Claims() {
  const { address } = useWallet();
  const [searchParams] = useSearchParams();

  const [claims, setClaims] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [listError, setListError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Pre-fill from query params (e.g. linked from RunDetail)
  const [runId, setRunId] = useState(searchParams.get("runId") || "");
  const [agentId, setAgentId] = useState(searchParams.get("agentId") || "");
  const [claimantAddress, setClaimantAddress] = useState("");
  const [reasonCode, setReasonCode] = useState(searchParams.get("reasonCode") || REASON_CODES[0]);
  const [result, setResult] = useState<any>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);

  useEffect(() => {
    if (address) setClaimantAddress(address);
  }, [address]);

  useEffect(() => {
    fetchClaims()
      .then(setClaims)
      .catch((err) => setListError(err.response?.data?.detail || err.message || "Failed to load claims"))
      .finally(() => setLoading(false));
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setResult(null);
    setSubmitError(null);
    try {
      const res = await submitClaim(runId, parseInt(agentId), claimantAddress, reasonCode);
      setResult(res);
      const updated = await fetchClaims();
      setClaims(updated);
    } catch (err: any) {
      setSubmitError(err.response?.data?.detail || err.message || "Submission failed");
    }
    setSubmitting(false);
  };

  return (
    <div>
      <h1>Claims</h1>

      <div className="card" style={{ marginBottom: 24 }}>
        <h3 style={{ marginBottom: 16 }}>Submit a Claim</h3>
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Run ID</label>
            <input
              value={runId}
              onChange={(e) => setRunId(e.target.value)}
              placeholder="Run UUID"
              required
            />
          </div>
          <div className="form-group">
            <label>Agent ID</label>
            <input
              value={agentId}
              onChange={(e) => setAgentId(e.target.value)}
              placeholder="1"
              required
            />
          </div>
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
          <button type="submit" disabled={submitting}>
            {submitting ? "Submitting..." : "Submit Claim"}
          </button>
        </form>

        {submitError && (
          <div style={{ marginTop: 12, padding: 12, background: "#1a0a0a", borderRadius: 8, color: "#f44336", fontSize: 13 }}>
            {submitError}
          </div>
        )}

        {result && !submitError && (
          <div style={{ marginTop: 12, padding: 12, background: "#0d0d15", borderRadius: 8, fontSize: 13 }}>
            <p><strong>Claim ID:</strong> {result.claim_id}</p>
            <p><strong>Status:</strong> {result.status}</p>
            <p>
              <strong>Approved:</strong>{" "}
              <span style={{ color: result.approved ? "#4caf50" : "#f44336", fontWeight: 600 }}>
                {result.approved ? "Yes" : "No"}
              </span>
            </p>
            <p><strong>Reason:</strong> {result.reason}</p>
          </div>
        )}
      </div>

      <h2>Claim History</h2>
      <div className="card">
        {loading ? (
          <div style={{ textAlign: "center", padding: "32px 0", color: "#666" }}>Loading...</div>
        ) : listError ? (
          <div style={{ color: "#f44336", padding: 16 }}>{listError}</div>
        ) : claims.length === 0 ? (
          <div style={{ textAlign: "center", padding: "40px 0", color: "#555" }}>
            No claims filed yet.
          </div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Agent</th>
                <th>Run</th>
                <th>Reason</th>
                <th>Status</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {claims.map((c: any) => (
                <tr key={c.id}>
                  <td>#{c.id}</td>
                  <td>
                    <Link to={`/agents/${c.agent_id}`}>#{c.agent_id}</Link>
                  </td>
                  <td style={{ fontFamily: "monospace", fontSize: 12 }}>
                    {c.run_id ? (
                      <Link to={`/runs/${c.run_id}`} style={{ color: "#6c63ff" }}>
                        {c.run_id.substring(0, 10)}...
                      </Link>
                    ) : "—"}
                  </td>
                  <td style={{ fontSize: 13 }}>{c.reason_code}</td>
                  <td>
                    <span
                      className={`badge ${
                        c.status === "approved" || c.status === "paid"
                          ? "badge-pass"
                          : c.status === "rejected"
                          ? "badge-fail"
                          : "badge-pending"
                      }`}
                    >
                      {c.status}
                    </span>
                  </td>
                  <td style={{ fontSize: 13, color: "#aaa" }}>
                    {c.created_at ? new Date(c.created_at).toLocaleString() : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
