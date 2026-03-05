import React, { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import {
  fetchAgent, fetchRuns, fetchClaims, fetchScore, fetchPolicies, activatePolicy,
  fetchAgentMemories, streamRun,
} from "../api";
import { ChevronLeft, Play, Activity, FileWarning, ShieldCheck, TrendingUp, ExternalLink, Brain } from "lucide-react";
import { motion } from "framer-motion";

// ── Identicon ────────────────────────────────────────────────────────────────
function Identicon({ id, size = 48 }: { id: number; size?: number }) {
  const hue = (id * 137.508) % 360;
  const color = `hsl(${hue}, 55%, 58%)`;
  const seed = id * 2654435761;
  const cells = Array.from({ length: 15 }, (_, i) => !!(seed & (1 << (i % 30))));
  const grid: boolean[][] = [];
  for (let y = 0; y < 5; y++) {
    grid.push([cells[y * 3], cells[y * 3 + 1], cells[y * 3 + 2], cells[y * 3 + 1], cells[y * 3]]);
  }
  const cs = size / 5;
  return (
    <svg width={size} height={size} style={{ borderRadius: 10, display: "block" }}>
      <rect width={size} height={size} fill="#18181b" />
      {grid.map((row, y) =>
        row.map((filled, x) =>
          filled ? <rect key={`${x}-${y}`} x={x * cs} y={y * cs} width={cs} height={cs} fill={color} /> : null
        )
      )}
    </svg>
  );
}

// ── Score ring ───────────────────────────────────────────────────────────────
function ScoreRing({ score }: { score: number }) {
  const color = score >= 80 ? "#10b981" : score >= 60 ? "#f59e0b" : "#ef4444";
  const textColor = score >= 80 ? "text-emerald-400" : score >= 60 ? "text-amber-400" : "text-red-400";
  const r = 28;
  const circ = 2 * Math.PI * r;
  return (
    <div className="relative flex items-center justify-center" style={{ width: 72, height: 72 }}>
      <svg width={72} height={72} className="absolute -rotate-90">
        <circle cx={36} cy={36} r={r} fill="none" stroke="#27272a" strokeWidth={5} />
        <circle cx={36} cy={36} r={r} fill="none" stroke={color} strokeWidth={5}
          strokeDasharray={`${(score / 100) * circ} ${circ}`} strokeLinecap="round" />
      </svg>
      <span className={`text-lg font-bold tabular-nums z-10 ${textColor}`}>{score}</span>
    </div>
  );
}

export default function AgentDetail() {
  const { id } = useParams<{ id: string }>();

  const [agent, setAgent] = useState<any>(null);
  const [runs, setRuns] = useState<any[]>([]);
  const [claims, setClaims] = useState<any[]>([]);
  const [score, setScore] = useState<any>(null);
  const [policies, setPolicies] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [memories, setMemories] = useState<any[]>([]);

  const [userInput, setUserInput] = useState("");
  const [running, setRunning] = useState(false);
  const [runResult, setRunResult] = useState<any>(null);
  const [runError, setRunError] = useState<string | null>(null);
  const [streamEvents, setStreamEvents] = useState<{ event: string; data: any }[]>([]);

  useEffect(() => {
    if (!id) return;
    const agentId = parseInt(id);
    Promise.all([fetchAgent(agentId), fetchRuns(agentId), fetchClaims(agentId), fetchScore(agentId), fetchPolicies(agentId), fetchAgentMemories(agentId)])
      .then(([a, r, c, s, p, m]) => { setAgent(a); setRuns(r); setClaims(c); setScore(s); setPolicies(p); setMemories(m); })
      .catch((err) => setError(err.response?.data?.detail || err.message || "Failed to load agent"))
      .finally(() => setLoading(false));
  }, [id]);

  const handleRun = (e: React.FormEvent) => {
    e.preventDefault();
    if (!id) return;
    setRunning(true); setRunResult(null); setRunError(null); setStreamEvents([]);
    const agentId = parseInt(id);

    streamRun(
      agentId,
      userInput,
      (event, data) => {
        setStreamEvents((prev) => [...prev, { event, data }]);
        if (event === "complete") {
          setRunResult(data);
          Promise.all([fetchRuns(agentId), fetchAgent(agentId), fetchAgentMemories(agentId)])
            .then(([r, a, m]) => { setRuns(r); setAgent(a); setMemories(m); });
        }
        if (event === "error") setRunError(data.message ?? "Run failed");
      },
      () => setRunning(false),
      (err) => { setRunError(err); setRunning(false); },
    );
  };

  const handleActivatePolicy = async (policyId: number) => {
    try {
      await activatePolicy(policyId);
      const updated = await fetchPolicies(parseInt(id!));
      setPolicies(updated);
    } catch (err: any) { alert(err.response?.data?.detail || err.message); }
  };

  if (loading)
    return <div className="flex items-center justify-center pt-20 text-zinc-600 text-sm">Loading...</div>;
  if (error)
    return <div className="glass-card p-8 border-red-900/50 bg-red-950/20 text-red-400 text-sm">{error}</div>;
  if (!agent)
    return <div className="text-zinc-600 pt-10">Agent not found.</div>;

  const activePolicy = policies.find((p) => p.status === "active");

  return (
    <div>
      {/* Back */}
      <Link to="/" className="inline-flex items-center gap-1.5 text-xs text-zinc-600 hover:text-zinc-300 no-underline mb-6 transition-colors">
        <ChevronLeft size={14} /> Dashboard
      </Link>

      {/* Agent hero */}
      <motion.div className="glass-card p-6 mb-5 flex items-center justify-between" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
        <div className="flex items-center gap-5">
          <Identicon id={agent.id} size={52} />
          <div>
            <div className="flex items-center gap-3 mb-1">
              <h1 className="text-xl font-bold text-zinc-100">Agent #{agent.id}</h1>
              {agent.status === "active" ? (
                <span className="badge-active flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-blue-400 pulse-dot" />
                  {agent.status}
                </span>
              ) : (
                <span className="badge-fail">{agent.status}</span>
              )}
            </div>
            <p className="text-xs text-zinc-600 font-mono">{agent.metadata_uri}</p>
            {agent.active_version && (
              <p className="text-xs text-zinc-600 mt-0.5">v{agent.active_version}</p>
            )}
          </div>
        </div>
        <ScoreRing score={agent.trust_score} />
      </motion.div>

      {/* Stat grid */}
      <div className="grid grid-cols-4 gap-4 mb-5">
        {[
          { label: "Total Runs", value: agent.total_runs, icon: Activity, color: "text-zinc-100" },
          { label: "Violations", value: agent.violations, icon: FileWarning, color: agent.violations > 0 ? "text-red-400" : "text-emerald-400" },
          { label: "Active Policy", value: activePolicy ? "Yes" : "None", icon: ShieldCheck, color: activePolicy ? "text-emerald-400" : "text-zinc-600" },
          { label: "Operator ID", value: `#${agent.operator_id}`, icon: TrendingUp, color: "text-violet-400" },
        ].map(({ label, value, icon: Icon, color }) => (
          <motion.div key={label} className="glass-card p-4" whileHover={{ y: -2 }} transition={{ duration: 0.15 }}>
            <div className="flex items-center justify-between mb-2">
              <span className="stat-label">{label}</span>
              <Icon size={13} className="text-zinc-700" />
            </div>
            <div className={`text-2xl font-bold tabular-nums ${color}`}>{value}</div>
          </motion.div>
        ))}
      </div>

      {/* Score breakdown */}
      {score?.breakdown && (
        <div className="glass-card p-5 mb-5">
          <h3 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-4">Score Breakdown</h3>
          <div className="flex gap-8">
            {[
              { label: "Base", value: `${score.breakdown.base}`, positive: true },
              { label: "Violation Penalty", value: `-${score.breakdown.violation_penalty}`, positive: score.breakdown.violation_penalty === 0 },
              { label: "Claim Penalty", value: `-${score.breakdown.claim_penalty}`, positive: score.breakdown.claim_penalty === 0 },
              { label: "Recency Bonus", value: `+${score.breakdown.recency_bonus}`, positive: true },
            ].map(({ label, value, positive }) => (
              <div key={label} className="text-center">
                <div className="text-xs text-zinc-600 mb-1">{label}</div>
                <div className={`text-xl font-bold tabular-nums ${positive ? "text-emerald-400" : "text-red-400"}`}>{value}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Execute run */}
      <div className="glass-card p-5 mb-5">
        <div className="flex items-center gap-2 mb-4">
          <Play size={14} className="text-violet-400" />
          <h3 className="text-sm font-semibold text-zinc-100">Execute Run</h3>
        </div>
        <form onSubmit={handleRun} className="flex gap-3 items-end">
          <div className="flex-1">
            <label className="form-label">User Input</label>
            <textarea
              className="form-input"
              value={userInput}
              onChange={(e) => setUserInput(e.target.value)}
              rows={2}
              placeholder="What is the current price of ETH?"
              required
            />
          </div>
          <button type="submit" disabled={running || agent.status !== "active"} className="btn-primary flex-shrink-0 self-end">
            <Play size={13} />
            {running ? "Running..." : "Execute"}
          </button>
        </form>
        {agent.status !== "active" && (
          <p className="text-xs text-zinc-600 mt-2">Agent must be active to run.</p>
        )}
        {/* SSE progress */}
        {streamEvents.length > 0 && (
          <div className="mt-3 space-y-1">
            {streamEvents.map((ev, i) => {
              const labels: Record<string, string> = {
                memory_loaded: "Memory loaded",
                inference_start: "Inference started",
                inference_done: "Inference complete",
                policy_evaluated: "Policy evaluated",
                complete: "Run stored",
                error: "Error",
              };
              const colors: Record<string, string> = {
                memory_loaded: "text-violet-400",
                inference_start: "text-blue-400",
                inference_done: "text-blue-300",
                policy_evaluated: ev.data?.verdict === "pass" ? "text-emerald-400" : "text-red-400",
                complete: "text-emerald-400",
                error: "text-red-400",
              };
              return (
                <div key={i} className={`text-xs font-mono flex items-center gap-2 ${colors[ev.event] ?? "text-zinc-500"}`}>
                  <span className="opacity-50">›</span>
                  <span>{labels[ev.event] ?? ev.event}</span>
                  {ev.event === "policy_evaluated" && (
                    <span className={`badge-${ev.data.verdict === "pass" ? "pass" : "fail"}`}>{ev.data.verdict}</span>
                  )}
                  {ev.event === "complete" && (
                    <Link to={`/runs/${ev.data.run_id}`} className="text-violet-400 flex items-center gap-1">
                      View run <ExternalLink size={10} />
                    </Link>
                  )}
                </div>
              );
            })}
          </div>
        )}
        {runError && (
          <div className="mt-3 p-3 rounded-lg bg-red-950/30 border border-red-900/50 text-red-400 text-xs">{runError}</div>
        )}
        {runResult?.reason_codes?.length > 0 && (
          <div className="mt-2 flex gap-1.5 flex-wrap">
            {runResult.reason_codes.map((code: string, i: number) => (
              <span key={i} className="badge-fail text-xs">{code}</span>
            ))}
          </div>
        )}
      </div>

      {/* Policies */}
      <h2 className="text-base font-semibold text-zinc-100 mb-3">Policies</h2>
      <div className="glass-card overflow-hidden mb-5">
        {policies.length === 0 ? (
          <div className="py-8 text-center text-zinc-600 text-sm">No policies registered.</div>
        ) : (
          <table className="data-table">
            <thead><tr><th>ID</th><th>Hash</th><th>Status</th><th>Created</th><th></th></tr></thead>
            <tbody>
              {policies.map((p: any) => (
                <tr key={p.id}>
                  <td className="text-zinc-400 font-mono text-xs">#{p.id}</td>
                  <td className="font-mono text-xs text-zinc-600">{p.policy_hash?.substring(0, 16)}...</td>
                  <td><span className={`badge-${p.status === "active" ? "active" : "pending"}`}>{p.status}</span></td>
                  <td className="text-xs text-zinc-600">{p.created_at ? new Date(p.created_at).toLocaleString() : "—"}</td>
                  <td>
                    {p.status !== "active" && (
                      <button onClick={() => handleActivatePolicy(p.id)} className="btn-ghost py-1 px-2 text-xs">
                        Activate
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Runs */}
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-base font-semibold text-zinc-100">Runs</h2>
        <Link to="/runs" className="text-xs text-zinc-600 hover:text-violet-400 no-underline transition-colors">View all →</Link>
      </div>
      <div className="glass-card overflow-hidden mb-5">
        {runs.length === 0 ? (
          <div className="py-8 text-center text-zinc-600 text-sm">No runs yet.</div>
        ) : (
          <table className="data-table">
            <thead><tr><th>Run ID</th><th>Verdict</th><th>Settlement TX</th><th>Time</th></tr></thead>
            <tbody>
              {runs.slice(0, 20).map((r: any) => (
                <tr key={r.run_id}>
                  <td><Link to={`/runs/${r.run_id}`} className="font-mono text-xs text-violet-400">{r.run_id.substring(0, 14)}...</Link></td>
                  <td><span className={`badge-${r.policy_verdict === "pass" ? "pass" : "fail"}`}>{r.policy_verdict}</span></td>
                  <td className="font-mono text-xs text-zinc-600">{r.settlement_tx?.substring(0, 14) || "—"}</td>
                  <td className="text-xs text-zinc-600">{r.created_at ? new Date(r.created_at).toLocaleString() : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Claims */}
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-base font-semibold text-zinc-100">Claims</h2>
        <Link to="/claims" className="text-xs text-zinc-600 hover:text-violet-400 no-underline transition-colors">Submit claim →</Link>
      </div>
      <div className="glass-card overflow-hidden mb-5">
        {claims.length === 0 ? (
          <div className="py-8 text-center text-zinc-600 text-sm">No claims filed.</div>
        ) : (
          <table className="data-table">
            <thead><tr><th>ID</th><th>Reason</th><th>Status</th><th>Created</th></tr></thead>
            <tbody>
              {claims.map((c: any) => (
                <tr key={c.id}>
                  <td className="text-zinc-400 font-mono text-xs">#{c.id}</td>
                  <td><span className="font-mono text-[10px] text-zinc-500 bg-zinc-800/60 px-1.5 py-0.5 rounded">{c.reason_code}</span></td>
                  <td>
                    <span className={`badge-${c.status === "approved" || c.status === "paid" ? "pass" : c.status === "rejected" ? "fail" : "pending"}`}>
                      {c.status}
                    </span>
                  </td>
                  <td className="text-xs text-zinc-600">{c.created_at ? new Date(c.created_at).toLocaleString() : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Memory */}
      <div className="flex items-center gap-2 mb-3">
        <Brain size={14} className="text-violet-400" />
        <h2 className="text-base font-semibold text-zinc-100">Agent Memory</h2>
        <span className="text-xs text-zinc-600">({memories.length} records)</span>
      </div>
      <div className="glass-card overflow-hidden">
        {memories.length === 0 ? (
          <div className="py-8 text-center text-zinc-600 text-sm">No memory yet — run the agent to build history.</div>
        ) : (
          <div className="divide-y divide-zinc-800/60">
            {memories.map((m: any) => (
              <div key={m.id} className="px-4 py-3 flex items-start gap-3">
                <span className={`mt-0.5 shrink-0 text-[10px] font-semibold px-1.5 py-0.5 rounded uppercase tracking-wider ${
                  m.memory_type === "violation" ? "bg-red-950/60 text-red-400" :
                  m.memory_type === "success"   ? "bg-emerald-950/60 text-emerald-400" :
                  "bg-violet-950/60 text-violet-400"
                }`}>{m.memory_type}</span>
                <div className="flex-1 min-w-0">
                  <p className="text-xs text-zinc-300 leading-relaxed">{m.content}</p>
                  {m.metadata?.reason_codes?.length > 0 && (
                    <div className="flex gap-1.5 mt-1.5 flex-wrap">
                      {m.metadata.reason_codes.map((code: string, i: number) => (
                        <span key={i} className="font-mono text-[10px] text-zinc-500 bg-zinc-800/60 px-1.5 py-0.5 rounded">{code}</span>
                      ))}
                    </div>
                  )}
                </div>
                <span className="shrink-0 text-[10px] text-zinc-600 tabular-nums">
                  {m.created_at ? new Date(m.created_at).toLocaleString() : "—"}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
