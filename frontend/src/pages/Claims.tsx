import React, { useEffect, useState } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { fetchClaims, submitClaim } from "../api";
import { useWallet } from "../context/WalletContext";
import { FileWarning, CheckCircle2, XCircle } from "lucide-react";
import { motion } from "framer-motion";

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

  const [runId, setRunId] = useState(searchParams.get("runId") || "");
  const [agentId, setAgentId] = useState(searchParams.get("agentId") || "");
  const [claimantAddress, setClaimantAddress] = useState("");
  const [reasonCode, setReasonCode] = useState(searchParams.get("reasonCode") || REASON_CODES[0]);
  const [result, setResult] = useState<any>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);

  useEffect(() => { if (address) setClaimantAddress(address); }, [address]);

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

  const claimStatusClass = (status: string) => {
    if (status === "approved" || status === "paid") return "badge-pass";
    if (status === "rejected") return "badge-fail";
    return "badge-pending";
  };

  return (
    <div>
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-zinc-100">Claims</h1>
        <p className="text-sm text-zinc-600 mt-0.5">Submit and track policy violation claims</p>
      </div>

      <div className="grid grid-cols-[1fr,1.6fr] gap-6 mb-6">
        {/* Submit form */}
        <div className="glass-card p-6">
          <div className="flex items-center gap-2 mb-5">
            <div className="w-7 h-7 rounded-lg bg-red-950/60 flex items-center justify-center">
              <FileWarning size={14} className="text-red-400" />
            </div>
            <h3 className="text-sm font-semibold text-zinc-100">Submit a Claim</h3>
          </div>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="form-label">Run ID</label>
              <input className="form-input" value={runId} onChange={(e) => setRunId(e.target.value)} placeholder="Run UUID" required />
            </div>
            <div>
              <label className="form-label">Agent ID</label>
              <input className="form-input" value={agentId} onChange={(e) => setAgentId(e.target.value)} placeholder="1" required />
            </div>
            <div>
              <label className="form-label flex items-center gap-1.5">
                Claimant Address
                {address && <span className="text-violet-500 font-normal normal-case tracking-normal">· auto-filled</span>}
              </label>
              <input className="form-input font-mono" value={claimantAddress} onChange={(e) => setClaimantAddress(e.target.value)} placeholder="0x..." required />
            </div>
            <div>
              <label className="form-label">Reason Code</label>
              <select
                className="form-input"
                value={reasonCode}
                onChange={(e) => setReasonCode(e.target.value)}
              >
                {REASON_CODES.map((code) => (
                  <option key={code} value={code} className="bg-zinc-900">{code}</option>
                ))}
              </select>
            </div>
            <button type="submit" disabled={submitting} className="btn-danger w-full justify-center">
              {submitting ? "Submitting..." : "Submit Claim"}
            </button>
          </form>

          {/* Feedback */}
          {submitError && (
            <motion.div
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              className="mt-4 p-3 rounded-lg bg-red-950/40 border border-red-900/50 text-red-400 text-xs flex items-start gap-2"
            >
              <XCircle size={13} className="mt-0.5 flex-shrink-0" />
              {submitError}
            </motion.div>
          )}
          {result && !submitError && (
            <motion.div
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              className="mt-4 p-4 rounded-lg bg-zinc-900 border border-zinc-700 text-xs space-y-1.5"
            >
              <div className="flex items-center gap-2 mb-2">
                <CheckCircle2 size={14} className="text-emerald-400" />
                <span className="text-zinc-200 font-medium">Claim submitted</span>
              </div>
              <div className="flex justify-between text-zinc-500"><span>Claim ID</span><span className="text-zinc-300 font-mono">#{result.claim_id}</span></div>
              <div className="flex justify-between text-zinc-500"><span>Status</span><span className="text-zinc-300">{result.status}</span></div>
              <div className="flex justify-between text-zinc-500">
                <span>Approved</span>
                <span className={result.approved ? "text-emerald-400" : "text-red-400"}>
                  {result.approved ? "Yes" : "No"}
                </span>
              </div>
              <div className="flex justify-between text-zinc-500"><span>Reason</span><span className="text-zinc-300">{result.reason}</span></div>
            </motion.div>
          )}
        </div>

        {/* Quick guide */}
        <div className="glass-card p-6">
          <h3 className="text-sm font-semibold text-zinc-400 mb-4">Reason Codes</h3>
          <div className="space-y-2">
            {[
              { code: "TOOL_WHITELIST_VIOLATION", desc: "Used tool not in policy" },
              { code: "VALUE_LIMIT_EXCEEDED", desc: "Action exceeded max value" },
              { code: "PROHIBITED_TARGET", desc: "Interacted with blocked address" },
              { code: "FREQUENCY_EXCEEDED", desc: "Too many actions in time window" },
              { code: "STALE_DATA", desc: "Data older than freshness requirement" },
              { code: "MODEL_MISMATCH", desc: "Declared model ≠ executed model" },
            ].map(({ code, desc }) => (
              <div key={code} className="flex items-start gap-3 py-2 border-b border-zinc-800/50 last:border-0">
                <span className="font-mono text-[10px] text-violet-400 bg-violet-950/40 px-2 py-0.5 rounded mt-0.5 flex-shrink-0">{code}</span>
                <span className="text-xs text-zinc-600">{desc}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Claims history */}
      <h2 className="text-base font-semibold text-zinc-100 mb-3">Claim History</h2>
      <div className="glass-card overflow-hidden">
        {loading ? (
          <div className="py-10 text-center text-zinc-600 text-sm">Loading...</div>
        ) : listError ? (
          <div className="p-6 text-red-400 text-sm">{listError}</div>
        ) : claims.length === 0 ? (
          <div className="py-12 text-center text-zinc-600 text-sm">No claims filed yet.</div>
        ) : (
          <table className="data-table">
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
                  <td className="text-zinc-400 font-mono text-xs">#{c.id}</td>
                  <td>
                    <Link to={`/agents/${c.agent_id}`} className="text-xs">#{c.agent_id}</Link>
                  </td>
                  <td>
                    {c.run_id ? (
                      <Link to={`/runs/${c.run_id}`} className="font-mono text-xs text-violet-400">
                        {c.run_id.substring(0, 10)}...
                      </Link>
                    ) : <span className="text-zinc-700">—</span>}
                  </td>
                  <td>
                    <span className="font-mono text-[10px] text-zinc-500 bg-zinc-800/60 px-2 py-0.5 rounded">
                      {c.reason_code}
                    </span>
                  </td>
                  <td>
                    <span className={claimStatusClass(c.status)}>{c.status}</span>
                  </td>
                  <td className="text-xs text-zinc-600">
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
