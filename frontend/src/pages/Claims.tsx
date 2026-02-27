import React, { useEffect, useState } from "react";
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
  const [claims, setClaims] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  const [runId, setRunId] = useState("");
  const [agentId, setAgentId] = useState("");
  const [claimantAddress, setClaimantAddress] = useState("");
  const [reasonCode, setReasonCode] = useState(REASON_CODES[0]);
  const [result, setResult] = useState<any>(null);

  // Auto-fill claimant address from connected wallet
  useEffect(() => {
    if (address) setClaimantAddress(address);
  }, [address]);

  useEffect(() => {
    fetchClaims()
      .then(setClaims)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setResult(null);
    try {
      const res = await submitClaim(runId, parseInt(agentId), claimantAddress, reasonCode);
      setResult(res);
      // Refresh claims list
      const updated = await fetchClaims();
      setClaims(updated);
    } catch (err: any) {
      setResult({ error: err.response?.data?.detail || err.message });
    }
    setSubmitting(false);
  };

  return (
    <div>
      <h1>Claims</h1>

      <div className="card">
        <h3>Submit a Claim</h3>
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Run ID</label>
            <input value={runId} onChange={(e) => setRunId(e.target.value)} placeholder="Run UUID" required />
          </div>
          <div className="form-group">
            <label>Agent ID</label>
            <input value={agentId} onChange={(e) => setAgentId(e.target.value)} placeholder="1" required />
          </div>
          <div className="form-group">
            <label>
              Claimant Address{" "}
              {address && (
                <span style={{ fontSize: 12, color: "#6c63ff", fontWeight: 400 }}>
                  (auto-filled from MetaMask)
                </span>
              )}
            </label>
            <input value={claimantAddress} onChange={(e) => setClaimantAddress(e.target.value)} placeholder="0x..." required />
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
              }}
            >
              {REASON_CODES.map((code) => (
                <option key={code} value={code}>
                  {code}
                </option>
              ))}
            </select>
          </div>
          <button type="submit" disabled={submitting}>
            {submitting ? "Submitting..." : "Submit Claim"}
          </button>
        </form>

        {result && (
          <div style={{ marginTop: 16, padding: 12, background: "#0d0d15", borderRadius: 8 }}>
            {result.error ? (
              <p style={{ color: "#f44336" }}>{result.error}</p>
            ) : (
              <>
                <p><strong>Claim ID:</strong> {result.claim_id}</p>
                <p><strong>Status:</strong> {result.status}</p>
                <p><strong>Approved:</strong> {result.approved ? "Yes" : "No"}</p>
                <p><strong>Reason:</strong> {result.reason}</p>
              </>
            )}
          </div>
        )}
      </div>

      <h2>Claim History</h2>
      <div className="card">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Agent</th>
              <th>Reason</th>
              <th>Status</th>
              <th>Created</th>
            </tr>
          </thead>
          <tbody>
            {claims.map((c: any) => (
              <tr key={c.id}>
                <td>#{c.id}</td>
                <td>#{c.agent_id}</td>
                <td>{c.reason_code}</td>
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
                <td>{c.created_at ? new Date(c.created_at).toLocaleString() : "-"}</td>
              </tr>
            ))}
            {claims.length === 0 && (
              <tr>
                <td colSpan={5} style={{ textAlign: "center", color: "#666" }}>
                  {loading ? "Loading..." : "No claims yet"}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
