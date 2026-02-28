import React, { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { fetchRun, replayRun, submitClaim } from "../api";
import { useWallet } from "../context/WalletContext";
import { ChevronLeft, RefreshCw, ShieldAlert, CheckCircle2, XCircle } from "lucide-react";
import { motion } from "framer-motion";

const REASON_CODES = [
  "TOOL_WHITELIST_VIOLATION",
  "VALUE_LIMIT_EXCEEDED",
  "PROHIBITED_TARGET",
  "FREQUENCY_EXCEEDED",
  "STALE_DATA",
  "MODEL_MISMATCH",
];

function InfoRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-xs text-zinc-600">{label}</span>
      <span className="text-sm text-zinc-300">{children}</span>
    </div>
  );
}

export default function RunDetail() {
  const { id } = useParams<{ id: string }>();
  const { address } = useWallet();

  const [run, setRun] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [replay, setReplay] = useState<any>(null);
  const [replaying, setReplaying] = useState(false);

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

  useEffect(() => { if (address) setClaimantAddress(address); }, [address]);

  const handleReplay = async () => {
    if (!id) return;
    setReplaying(true); setReplay(null);
    try { setReplay(await replayRun(id)); }
    catch (err: any) { setReplay({ error: err.response?.data?.detail || err.message }); }
    setReplaying(false);
  };

  const handleClaim = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!run) return;
    setSubmittingClaim(true); setClaimResult(null); setClaimError(null);
    try { setClaimResult(await submitClaim(run.run_id, run.agent_id, claimantAddress, reasonCode)); }
    catch (err: any) { setClaimError(err.response?.data?.detail || err.message || "Failed to submit claim"); }
    setSubmittingClaim(false);
  };

  if (loading)
    return <div className="flex items-center justify-center pt-20 text-zinc-600 text-sm">Loading...</div>;
  if (error)
    return <div className="glass-card p-8 border-red-900/50 bg-red-950/20 text-red-400 text-sm">{error}</div>;
  if (!run)
    return <div className="text-zinc-600 pt-10">Run not found.</div>;

  const isFail = run.policy_verdict !== "pass";

  return (
    <div>
      {/* Back */}
      <Link to={`/agents/${run.agent_id}`} className="inline-flex items-center gap-1.5 text-xs text-zinc-600 hover:text-zinc-300 no-underline mb-6 transition-colors">
        <ChevronLeft size={14} /> Agent #{run.agent_id}
      </Link>

      {/* Hero */}
      <motion.div className="flex items-center gap-4 mb-6" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
        <div>
          <div className="flex items-center gap-3 mb-1">
            <h1 className="text-2xl font-bold text-zinc-100">Run Detail</h1>
            <span className={`badge-${run.policy_verdict === "pass" ? "pass" : "fail"} text-sm`}>
              {run.policy_verdict}
            </span>
          </div>
          <p className="text-xs text-zinc-600 font-mono">{run.run_id}</p>
        </div>
      </motion.div>

      <div className="grid grid-cols-[1fr,1fr] gap-5 mb-5">
        {/* Run info */}
        <div className="glass-card p-5">
          <h3 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-4">Run Info</h3>
          <div className="grid grid-cols-2 gap-4">
            <InfoRow label="Agent">
              <Link to={`/agents/${run.agent_id}`} className="text-violet-400">#{run.agent_id}</Link>
            </InfoRow>
            <InfoRow label="User">
              <span className="font-mono text-xs">{run.user_address || "—"}</span>
            </InfoRow>
            <InfoRow label="Created">
              {run.created_at ? new Date(run.created_at).toLocaleString() : "—"}
            </InfoRow>
            <InfoRow label="Verdict">
              <span className={`badge-${run.policy_verdict === "pass" ? "pass" : "fail"}`}>
                {run.policy_verdict}
              </span>
            </InfoRow>
          </div>
        </div>

        {/* Proof references */}
        <div className="glass-card p-5">
          <h3 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-4">Proof References</h3>
          <div className="space-y-3">
            {[
              { label: "Input Hash", value: run.input_hash },
              { label: "Output Hash", value: run.output_hash },
              { label: "Settlement TX", value: run.settlement_tx },
            ].map(({ label, value }) => (
              <div key={label}>
                <div className="text-xs text-zinc-600 mb-0.5">{label}</div>
                <div className={`font-mono text-xs break-all ${value ? "text-zinc-400" : "text-zinc-700"}`}>
                  {value || "—"}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Violations */}
      {run.reason_codes && run.reason_codes.length > 0 && (
        <div className="glass-card p-5 mb-5 border-red-900/40 bg-red-950/10">
          <div className="flex items-center gap-2 mb-3">
            <ShieldAlert size={14} className="text-red-400" />
            <h3 className="text-sm font-semibold text-red-400">Policy Violations</h3>
          </div>
          <div className="flex gap-2 flex-wrap">
            {run.reason_codes.map((code: string, i: number) => (
              <span key={i} className="badge-fail">{code}</span>
            ))}
          </div>
        </div>
      )}

      {/* Transcript */}
      <div className="glass-card p-5 mb-5">
        <h3 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-3">Transcript</h3>
        <pre className="bg-zinc-950/80 rounded-lg p-4 overflow-auto max-h-96 text-xs text-zinc-400 leading-relaxed font-mono border border-zinc-800/50">
          {JSON.stringify(run.transcript, null, 2)}
        </pre>
      </div>

      {/* Independent replay */}
      <div className="glass-card p-5 mb-5">
        <h3 className="text-sm font-semibold text-zinc-100 mb-1">Independent Replay</h3>
        <p className="text-xs text-zinc-600 mb-4">
          Re-fetch proof from OpenGradient and re-evaluate policy independently.
        </p>
        <button onClick={handleReplay} disabled={replaying} className="btn-ghost gap-2">
          <RefreshCw size={13} className={replaying ? "animate-spin" : ""} />
          {replaying ? "Replaying..." : "↻ Replay & Verify"}
        </button>

        {replay && (
          <motion.div
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-4 rounded-lg bg-zinc-900 border border-zinc-700 p-4"
          >
            {replay.error ? (
              <div className="text-red-400 text-sm">{replay.error}</div>
            ) : (
              <div className="grid grid-cols-2 gap-4 text-sm">
                {[
                  { label: "Proof Valid", value: replay.proof_valid ? "Yes" : "No", ok: replay.proof_valid },
                  { label: "Input Hash Match", value: replay.input_hash_match ? "Yes" : "No", ok: replay.input_hash_match },
                  { label: "Re-evaluated Verdict", value: replay.policy_verdict, badge: true },
                  { label: "Original Verdict", value: replay.original_verdict, badge: true },
                ].map(({ label, value, ok, badge }) => (
                  <div key={label}>
                    <div className="text-xs text-zinc-600 mb-1">{label}</div>
                    {badge ? (
                      <span className={`badge-${value === "pass" ? "pass" : "fail"}`}>{value}</span>
                    ) : (
                      <span className={`font-semibold ${ok ? "text-emerald-400" : "text-red-400"}`}>{value}</span>
                    )}
                  </div>
                ))}
              </div>
            )}
          </motion.div>
        )}
      </div>

      {/* Claim form — only for failed runs */}
      {isFail && (
        <motion.div
          className="glass-card p-5 border-red-900/30 bg-red-950/5"
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
        >
          <div className="flex items-center gap-2 mb-1">
            <ShieldAlert size={14} className="text-red-400" />
            <h3 className="text-sm font-semibold text-zinc-100">Submit a Claim</h3>
          </div>
          <p className="text-xs text-zinc-600 mb-4">
            This run resulted in a policy violation. File a claim to request reimbursement.
          </p>
          <form onSubmit={handleClaim} className="space-y-4">
            <div>
              <label className="form-label flex items-center gap-1.5">
                Claimant Address
                {address && <span className="text-violet-500 font-normal normal-case tracking-normal">· auto-filled</span>}
              </label>
              <input className="form-input font-mono" value={claimantAddress} onChange={(e) => setClaimantAddress(e.target.value)} placeholder="0x..." required />
            </div>
            <div>
              <label className="form-label">Reason Code</label>
              <select className="form-input" value={reasonCode} onChange={(e) => setReasonCode(e.target.value)}>
                {REASON_CODES.map((code) => (
                  <option key={code} value={code} className="bg-zinc-900">{code}</option>
                ))}
              </select>
            </div>
            <button type="submit" disabled={submittingClaim} className="btn-danger">
              {submittingClaim ? "Submitting..." : "Submit Claim"}
            </button>
          </form>

          {claimError && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mt-3 p-3 rounded-lg bg-red-950/40 border border-red-900/50 text-red-400 text-xs flex items-start gap-2">
              <XCircle size={13} className="mt-0.5 flex-shrink-0" /> {claimError}
            </motion.div>
          )}

          {claimResult && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mt-3 p-4 rounded-lg bg-zinc-900 border border-zinc-700 text-xs space-y-1.5">
              <div className="flex items-center gap-2 mb-2">
                <CheckCircle2 size={14} className="text-emerald-400" />
                <span className="text-zinc-200 font-medium">Claim submitted</span>
              </div>
              <div className="flex justify-between text-zinc-500"><span>Claim ID</span><span className="text-zinc-300 font-mono">#{claimResult.claim_id}</span></div>
              <div className="flex justify-between text-zinc-500"><span>Status</span><span className="text-zinc-300">{claimResult.status}</span></div>
              <div className="flex justify-between text-zinc-500">
                <span>Approved</span>
                <span className={claimResult.approved ? "text-emerald-400" : "text-red-400"}>{claimResult.approved ? "Yes" : "No"}</span>
              </div>
              <div className="flex justify-between text-zinc-500"><span>Reason</span><span className="text-zinc-300">{claimResult.reason}</span></div>
              <Link to="/claims" className="block text-violet-400 text-xs mt-2 no-underline hover:underline">
                View all claims →
              </Link>
            </motion.div>
          )}
        </motion.div>
      )}
    </div>
  );
}
