import React, { useEffect, useRef, useState } from "react";
import { useParams, Link } from "react-router-dom";
import {
  fetchAgent, fetchRuns, fetchClaims, fetchScore, fetchScoreHistory, fetchPolicies,
  activatePolicy, fetchAgentMemories, streamRun, generateApiKey,
} from "../api";
import { buildRunMessage } from "../utils/runSignature";
import { useWallet } from "../context/WalletContext";
import { CopyButton } from "../components/CopyButton";
import {
  ChevronLeft, Play, Activity, FileWarning, ShieldCheck, TrendingUp,
  ExternalLink, Brain, History,
} from "lucide-react";
import { motion } from "framer-motion";
import type { Agent, RunListItem, ClaimListItem, Score, ScoreHistoryPoint, Policy, Memory, PolicyRules, SSEEvent, SSEEventData } from "../types";

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
  const r = 28, circ = 2 * Math.PI * r;
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

// ── Score history chart ───────────────────────────────────────────────────────
function ScoreHistoryChart({ history, currentScore }: { history: ScoreHistoryPoint[]; currentScore: number }) {
  if (history.length === 0) {
    return (
      <div className="flex items-center justify-center h-20 text-zinc-700 text-xs">
        No history yet — updates after each run
      </div>
    );
  }

  const W = 400, H = 72;
  const scores = history.map((p) => p.score);
  const minS = Math.max(0, Math.min(...scores) - 5);
  const maxS = Math.min(100, Math.max(...scores) + 5);
  const range = maxS - minS || 1;

  const toX = (i: number) => history.length === 1 ? W / 2 : (i / (history.length - 1)) * W;
  const toY = (s: number) => H - ((s - minS) / range) * (H - 8) - 4;

  const pathD = history.length === 1
    ? ""
    : "M " + history.map((p, i) => `${toX(i)},${toY(p.score)}`).join(" L ");

  const areaD = history.length > 1
    ? `${pathD} L ${toX(history.length - 1)},${H} L ${toX(0)},${H} Z`
    : "";

  const lineColor = currentScore >= 80 ? "#10b981" : currentScore >= 60 ? "#f59e0b" : "#ef4444";

  return (
    <div>
      <svg width="100%" height={H + 4} viewBox={`0 0 ${W} ${H + 4}`} preserveAspectRatio="none" className="w-full overflow-visible">
        <defs>
          <linearGradient id="scoreAreaGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={lineColor} stopOpacity="0.18" />
            <stop offset="100%" stopColor={lineColor} stopOpacity="0" />
          </linearGradient>
        </defs>
        {areaD && <path d={areaD} fill="url(#scoreAreaGrad)" />}
        {pathD && <path d={pathD} fill="none" stroke={lineColor} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />}
        {history.map((p, i) => (
          <circle key={i} cx={toX(i)} cy={toY(p.score)} r={3} fill={lineColor} />
        ))}
      </svg>
      <div className="flex justify-between text-[10px] text-zinc-600 mt-1">
        {history.length === 1 ? (
          <span>{new Date(history[0].created_at).toLocaleDateString()}</span>
        ) : (
          <>
            <span>{new Date(history[0].created_at).toLocaleDateString()}</span>
            <span>{new Date(history[history.length - 1].created_at).toLocaleDateString()}</span>
          </>
        )}
      </div>
    </div>
  );
}

// ── Policy rules chips ────────────────────────────────────────────────────────
function PolicyRulesChips({ rules }: { rules: PolicyRules }) {
  if (!rules || typeof rules !== "object") return null;
  const chips: { label: string; cls: string }[] = [];

  if (Array.isArray(rules.allowed_tools) && rules.allowed_tools.length > 0) {
    rules.allowed_tools.forEach((t: string) =>
      chips.push({ label: t, cls: "bg-emerald-950/60 text-emerald-400" })
    );
  }
  if (Array.isArray(rules.prohibited_targets) && rules.prohibited_targets.length > 0) {
    rules.prohibited_targets.forEach((t: string) =>
      chips.push({ label: `blocked: ${t.substring(0, 8)}…`, cls: "bg-red-950/60 text-red-400" })
    );
  }
  if (rules.max_value_per_action !== undefined) {
    chips.push({ label: `max $${rules.max_value_per_action}`, cls: "bg-blue-950/60 text-blue-400" });
  }
  if (rules.max_actions_per_window !== undefined) {
    const w = rules.window_seconds ? `${rules.window_seconds}s` : "window";
    chips.push({ label: `${rules.max_actions_per_window} actions/${w}`, cls: "bg-zinc-800/60 text-zinc-400" });
  }
  if (rules.required_data_freshness_seconds !== undefined) {
    chips.push({ label: `data < ${rules.required_data_freshness_seconds}s old`, cls: "bg-zinc-800/60 text-zinc-400" });
  }
  if (rules.max_slippage_bps !== undefined) {
    chips.push({ label: `slippage ≤ ${rules.max_slippage_bps}bps`, cls: "bg-zinc-800/60 text-zinc-400" });
  }

  if (chips.length === 0) return null;
  return (
    <div className="flex gap-1.5 flex-wrap mt-2">
      {chips.map((chip, i) => (
        <span key={i} className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${chip.cls}`}>{chip.label}</span>
      ))}
    </div>
  );
}

// ── Main ─────────────────────────────────────────────────────────────────────
export default function AgentDetail() {
  const { id } = useParams<{ id: string }>();
  const { address, signer } = useWallet();
  const runFormRef = useRef<HTMLDivElement>(null);

  const [agent, setAgent] = useState<Agent | null>(null);
  const [runs, setRuns] = useState<RunListItem[]>([]);
  const [claims, setClaims] = useState<ClaimListItem[]>([]);
  const [score, setScore] = useState<Score | null>(null);
  const [scoreHistory, setScoreHistory] = useState<ScoreHistoryPoint[]>([]);
  const [policies, setPolicies] = useState<Policy[]>([]);
  const [memories, setMemories] = useState<Memory[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [userInput, setUserInput] = useState("");
  const [running, setRunning] = useState(false);
  const [runResult, setRunResult] = useState<SSEEventData | null>(null);
  const [runError, setRunError] = useState<string | null>(null);
  const [streamEvents, setStreamEvents] = useState<SSEEvent[]>([]);

  useEffect(() => {
    if (!id) return;
    const agentId = parseInt(id);
    Promise.all([
      fetchAgent(agentId), fetchRuns(agentId), fetchClaims(agentId),
      fetchScore(agentId), fetchScoreHistory(agentId), fetchPolicies(agentId), fetchAgentMemories(agentId),
    ])
      .then(([a, r, c, s, sh, p, m]) => {
        setAgent(a); setRuns(r); setClaims(c); setScore(s);
        setScoreHistory(Array.isArray(sh) ? sh : []);
        setPolicies(p); setMemories(m);
      })
      .catch((err) => setError(err.response?.data?.detail || err.message || "Failed to load agent"))
      .finally(() => setLoading(false));
  }, [id]);

  const handleRun = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!id) return;
    if (!address || !signer) {
      setRunError("Connect your wallet to execute a run");
      return;
    }
    setRunning(true); setRunResult(null); setRunError(null); setStreamEvents([]);
    const agentId = parseInt(id);
    try {
      const sigForKey = await signer.signMessage("AgentBond API key request");
      const { api_key } = await generateApiKey(address, sigForKey, "AgentBond API key request");

      // Canonical run message: binds to agent id, prompt hash, and a fresh timestamp
      const runMessage = await buildRunMessage(agentId, userInput);
      const runSignature = await signer.signMessage(runMessage);

      streamRun(
        agentId, userInput,
        (event, data) => {
          setStreamEvents((prev) => [...prev, { event, data }]);
          if (event === "complete") {
            setRunResult(data);
            Promise.all([
              fetchRuns(agentId), fetchAgent(agentId), fetchAgentMemories(agentId), fetchScoreHistory(agentId),
            ]).then(([r, a, m, sh]) => {
              setRuns(r); setAgent(a); setMemories(m);
              setScoreHistory(Array.isArray(sh) ? sh : []);
            });
          }
          if (event === "error") setRunError(data.message ?? "Run failed");
        },
        () => setRunning(false),
        (err) => { setRunError(err); setRunning(false); },
        { apiKey: api_key, signature: runSignature, message: runMessage },
      );
    } catch (err: unknown) {
      const e = err as { message?: string };
      setRunError(e.message ?? "Run authorization failed");
      setRunning(false);
    }
  };

  const handleActivatePolicy = async (policyId: number) => {
    try {
      await activatePolicy(policyId);
      setPolicies(await fetchPolicies(parseInt(id!)));
    } catch (err: unknown) { const e = err as { response?: { data?: { detail?: string } }; message?: string }; alert(e.response?.data?.detail || e.message); }
  };

  if (loading) return <div className="flex items-center justify-center pt-20 text-zinc-600 text-sm">Loading...</div>;
  if (error) return <div className="glass-card p-8 border-red-900/50 bg-red-950/20 text-red-400 text-sm">{error}</div>;
  if (!agent) return <div className="text-zinc-600 pt-10">Agent not found.</div>;

  const activePolicy = policies.find((p) => p.status === "active");
  const firstFailRun = runs.find((r) => r.policy_verdict !== "pass");

  return (
    <div>
      <Link to="/" className="inline-flex items-center gap-1.5 text-xs text-zinc-600 hover:text-zinc-300 no-underline mb-6 transition-colors">
        <ChevronLeft size={14} /> Dashboard
      </Link>

      {/* Agent hero */}
      <motion.div className="glass-card p-6 mb-5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
        <div className="flex items-center gap-5">
          <Identicon id={agent.id} size={52} />
          <div>
            <div className="flex items-center gap-3 mb-1">
              <h1 className="text-xl font-bold text-zinc-100">Agent #{agent.id}</h1>
              {agent.status === "active" ? (
                <span className="badge-active flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-blue-400 pulse-dot" />{agent.status}
                </span>
              ) : (
                <span className="badge-fail">{agent.status}</span>
              )}
            </div>
            <p className="text-xs text-zinc-600 font-mono">{agent.metadata_uri}</p>
            {agent.active_version && <p className="text-xs text-zinc-600 mt-0.5">v{agent.active_version}</p>}
          </div>
        </div>
        <ScoreRing score={agent.trust_score} />
      </motion.div>

      {/* Stat grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-5">
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

      {/* Score breakdown + history */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-5">
        {score?.breakdown && (
          <div className="glass-card p-5">
            <h3 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-4">Score Breakdown</h3>
            <div className="flex flex-wrap gap-4 sm:gap-8">
              {[
                { label: "Base", value: `${score.breakdown.base}`, positive: true },
                { label: "Violation", value: `-${score.breakdown.violation_penalty}`, positive: score.breakdown.violation_penalty === 0 },
                { label: "Claim", value: `-${score.breakdown.claim_penalty}`, positive: score.breakdown.claim_penalty === 0 },
                { label: "Recency", value: `+${score.breakdown.recency_bonus}`, positive: true },
              ].map(({ label, value, positive }) => (
                <div key={label} className="text-center">
                  <div className="text-xs text-zinc-600 mb-1">{label}</div>
                  <div className={`text-xl font-bold tabular-nums ${positive ? "text-emerald-400" : "text-red-400"}`}>{value}</div>
                </div>
              ))}
            </div>
          </div>
        )}
        <div className="glass-card p-5">
          <div className="flex items-center gap-2 mb-3">
            <History size={13} className="text-zinc-600" />
            <h3 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">Score History</h3>
            <span className="text-xs text-zinc-700 ml-auto">{scoreHistory.length} snapshot{scoreHistory.length !== 1 ? "s" : ""}</span>
          </div>
          <ScoreHistoryChart history={scoreHistory} currentScore={agent.trust_score} />
        </div>
      </div>

      {/* Execute run */}
      <div className="glass-card p-5 mb-5" ref={runFormRef}>
        <div className="flex items-center gap-2 mb-4">
          <Play size={14} className="text-violet-400" />
          <h3 className="text-sm font-semibold text-zinc-100">Execute Run</h3>
        </div>
        <form onSubmit={handleRun} className="flex flex-col sm:flex-row gap-3 sm:items-end">
          <div className="flex-1">
            <label className="form-label">User Input</label>
            <textarea className="form-input" value={userInput} onChange={(e) => setUserInput(e.target.value)}
              rows={2} placeholder="What is the current price of ETH?" required />
          </div>
          <button type="submit" disabled={running || agent.status !== "active"} className="btn-primary flex-shrink-0 self-end">
            <Play size={13} />
            {running ? "Running..." : "Execute"}
          </button>
        </form>
        {agent.status !== "active" && (
          <p className="text-xs text-zinc-600 mt-2">Agent must be active to run.</p>
        )}
        {streamEvents.length > 0 && (
          <div className="mt-3 space-y-1">
            {streamEvents.map((ev, i) => {
              const labels: Record<string, string> = {
                memory_loaded: "Memory loaded", inference_start: "Inference started",
                inference_done: "Inference complete", policy_evaluated: "Policy evaluated",
                complete: "Run stored", error: "Error",
              };
              const colors: Record<string, string> = {
                memory_loaded: "text-violet-400", inference_start: "text-blue-400",
                inference_done: "text-blue-300",
                policy_evaluated: ev.data?.verdict === "pass" ? "text-emerald-400" : "text-red-400",
                complete: "text-emerald-400", error: "text-red-400",
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
        {(runResult?.reason_codes?.length ?? 0) > 0 && (
          <div className="mt-2 flex gap-1.5 flex-wrap">
            {runResult!.reason_codes!.map((code: string, i: number) => (
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
          <div className="divide-y divide-zinc-800/60">
            {policies.map((p) => (
              <div key={p.id} className="px-4 py-3">
                <div className="flex items-center gap-3">
                  <span className="font-mono text-xs text-zinc-600">#{p.id}</span>
                  <div className="flex items-center gap-1.5">
                    <span className="font-mono text-xs text-zinc-600">{p.policy_hash?.substring(0, 16)}…</span>
                    {p.policy_hash && <CopyButton value={p.policy_hash} />}
                  </div>
                  <span className={`badge-${p.status === "active" ? "active" : "pending"} ml-1`}>{p.status}</span>
                  <span className="text-xs text-zinc-600 ml-1">
                    {p.created_at ? new Date(p.created_at).toLocaleDateString() : "—"}
                  </span>
                  <div className="ml-auto">
                    {p.status !== "active" && (
                      <button onClick={() => handleActivatePolicy(p.id)} className="btn-ghost py-1 px-2 text-xs">
                        Activate
                      </button>
                    )}
                  </div>
                </div>
                {p.rules && <PolicyRulesChips rules={p.rules} />}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Runs */}
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-base font-semibold text-zinc-100">Runs</h2>
        <Link to="/runs" className="text-xs text-zinc-600 hover:text-violet-400 no-underline transition-colors">View all →</Link>
      </div>
      <div className="glass-card overflow-hidden overflow-x-auto mb-5">
        {runs.length === 0 ? (
          <div className="flex flex-col items-center py-10 gap-3">
            <Activity size={20} className="text-zinc-700" />
            <p className="text-zinc-600 text-sm">No runs yet.</p>
            <button
              className="btn-ghost text-xs gap-1.5"
              onClick={() => runFormRef.current?.scrollIntoView({ behavior: "smooth", block: "center" })}
            >
              <Play size={11} /> Run this agent
            </button>
          </div>
        ) : (
          <table className="data-table">
            <thead>
              <tr><th>Run ID</th><th>Verdict</th><th>Evidence Hash</th><th>Time</th></tr>
            </thead>
            <tbody>
              {runs.slice(0, 20).map((r) => (
                <tr key={r.run_id}>
                  <td>
                    <div className="flex items-center gap-1.5">
                      <Link to={`/runs/${r.run_id}`} className="font-mono text-xs text-violet-400">
                        {r.run_id.substring(0, 14)}…
                      </Link>
                      <CopyButton value={r.run_id} />
                    </div>
                  </td>
                  <td><span className={`badge-${r.policy_verdict === "pass" ? "pass" : "fail"}`}>{r.policy_verdict}</span></td>
                  <td>
                    {r.evidence_hash ? (
                      <div className="flex items-center gap-1.5">
                        <span className="font-mono text-xs text-zinc-600">{r.evidence_hash.substring(0, 14)}…</span>
                        <CopyButton value={r.evidence_hash} />
                      </div>
                    ) : <span className="font-mono text-xs text-zinc-700">—</span>}
                  </td>
                  <td className="text-xs text-zinc-600">
                    {r.created_at ? new Date(r.created_at).toLocaleString() : "—"}
                  </td>
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
      <div className="glass-card overflow-hidden overflow-x-auto mb-5">
        {claims.length === 0 ? (
          <div className="py-8 text-center">
            <p className="text-zinc-600 text-sm">No claims filed.</p>
            {firstFailRun && (
              <p className="text-zinc-700 text-xs mt-1">
                This agent has failing runs —{" "}
                <Link to={`/runs/${firstFailRun.run_id}`} className="text-violet-400 no-underline hover:underline">
                  file a claim
                </Link>
              </p>
            )}
          </div>
        ) : (
          <table className="data-table">
            <thead><tr><th>ID</th><th>Reason</th><th>Status</th><th>Created</th></tr></thead>
            <tbody>
              {claims.map((c) => (
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
            {memories.map((m) => (
              <div key={m.id} className="px-4 py-3 flex items-start gap-3">
                <span className={`mt-0.5 shrink-0 text-[10px] font-semibold px-1.5 py-0.5 rounded uppercase tracking-wider ${
                  m.memory_type === "violation" ? "bg-red-950/60 text-red-400" :
                  m.memory_type === "success" ? "bg-emerald-950/60 text-emerald-400" :
                  "bg-violet-950/60 text-violet-400"
                }`}>{m.memory_type}</span>
                <div className="flex-1 min-w-0">
                  <p className="text-xs text-zinc-300 leading-relaxed">{m.content}</p>
                  {(m.metadata?.reason_codes?.length ?? 0) > 0 && (
                    <div className="flex gap-1.5 mt-1.5 flex-wrap">
                      {m.metadata!.reason_codes!.map((code: string, i: number) => (
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
