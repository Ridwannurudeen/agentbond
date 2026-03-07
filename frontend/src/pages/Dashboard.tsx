import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchDashboardStats, fetchAgents, fetchRuns, streamRun } from "../api";
import { CopyButton } from "../components/CopyButton";
import { Bot, Activity, FileWarning, TrendingUp, ArrowRight, ExternalLink, Play, ChevronDown, CheckCircle2, XCircle } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

// ── Identicon ────────────────────────────────────────────────────────────────
function Identicon({ id, size = 28 }: { id: number; size?: number }) {
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
    <svg width={size} height={size} style={{ borderRadius: 6, display: "block", flexShrink: 0 }}>
      <rect width={size} height={size} fill="#18181b" />
      {grid.map((row, y) =>
        row.map((filled, x) =>
          filled ? <rect key={`${x}-${y}`} x={x * cs} y={y * cs} width={cs} height={cs} fill={color} /> : null
        )
      )}
    </svg>
  );
}

// ── Radial gauge ─────────────────────────────────────────────────────────────
function RadialGauge({ value }: { value: number }) {
  const r = 28;
  const circ = 2 * Math.PI * r;
  const dash = (value / 100) * circ;
  const color = value >= 80 ? "#10b981" : value >= 60 ? "#f59e0b" : "#ef4444";
  return (
    <svg width={72} height={72} className="-rotate-90">
      <circle cx={36} cy={36} r={r} fill="none" stroke="#27272a" strokeWidth={6} />
      <circle cx={36} cy={36} r={r} fill="none" stroke={color} strokeWidth={6}
        strokeDasharray={`${dash} ${circ}`} strokeLinecap="round"
        style={{ transition: "stroke-dasharray 0.6s ease" }} />
    </svg>
  );
}

// ── Sparkline ────────────────────────────────────────────────────────────────
function Sparkline({ runs }: { runs: any[] }) {
  if (runs.length < 2) return <div className="w-20 h-8" />;
  const last = runs.slice(-20);
  const w = 80, h = 32;
  const dx = w / (last.length - 1);
  const points = last.map((r: any, i: number) => `${i * dx},${r.policy_verdict === "pass" ? 4 : h - 4}`).join(" ");
  return (
    <svg width={w} height={h} className="opacity-70">
      <polyline points={points} fill="none" stroke="#8b5cf6" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

const scoreColor = (s: number) =>
  s >= 80 ? "text-emerald-400" : s >= 60 ? "text-amber-400" : "text-red-400";

const scoreBorderColor = (s: number) =>
  s >= 80 ? "#10b981" : s >= 60 ? "#f59e0b" : "#ef4444";

// ── Stat card ────────────────────────────────────────────────────────────────
function StatCard({ label, value, icon: Icon, sub }: {
  label: string; value: React.ReactNode; icon: React.ElementType; sub?: React.ReactNode;
}) {
  return (
    <motion.div className="glass-card p-5 flex flex-col gap-3" whileHover={{ y: -2 }} transition={{ duration: 0.15 }}>
      <div className="flex items-center justify-between">
        <span className="stat-label">{label}</span>
        <div className="w-7 h-7 rounded-lg bg-zinc-800/80 flex items-center justify-center">
          <Icon size={14} className="text-zinc-500" />
        </div>
      </div>
      <div className="stat-value">{value}</div>
      {sub && <div className="text-xs text-zinc-600">{sub}</div>}
    </motion.div>
  );
}

const EVENT_LABELS: Record<string, string> = {
  memory_loaded: "Memory loaded",
  inference_start: "Inference started",
  inference_done: "Inference complete",
  policy_evaluated: "Policy evaluated",
  complete: "Done",
  error: "Error",
};
const EVENT_COLORS: Record<string, string> = {
  memory_loaded: "text-violet-400",
  inference_start: "text-blue-400",
  inference_done: "text-blue-300",
  complete: "text-emerald-400",
  error: "text-red-400",
};

// ── Main ─────────────────────────────────────────────────────────────────────
export default function Dashboard() {
  const [stats, setStats] = useState<any>(null);
  const [agents, setAgents] = useState<any[]>([]);
  const [runs, setRuns] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [playAgentId, setPlayAgentId] = useState<string>("");
  const [playInput, setPlayInput] = useState("");
  const [playRunning, setPlayRunning] = useState(false);
  const [playEvents, setPlayEvents] = useState<{ event: string; data: any }[]>([]);
  const [playResult, setPlayResult] = useState<any>(null);
  const [playError, setPlayError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([fetchDashboardStats(), fetchAgents(), fetchRuns()])
      .then(([s, a, r]) => {
        setStats(s); setAgents(a); setRuns(r);
        const active = a.filter((ag: any) => ag.status === "active");
        if (active.length > 0) setPlayAgentId(String(active[0].id));
        else if (a.length > 0) setPlayAgentId(String(a[0].id));
      })
      .catch((err) => setError(err.response?.data?.detail || err.message || "Failed to load"))
      .finally(() => setLoading(false));
  }, []);

  const handlePlay = (e: React.FormEvent) => {
    e.preventDefault();
    if (!playAgentId || !playInput.trim()) return;
    setPlayRunning(true); setPlayEvents([]); setPlayResult(null); setPlayError(null);
    streamRun(
      parseInt(playAgentId),
      playInput,
      (event, data) => {
        setPlayEvents((prev) => [...prev, { event, data }]);
        if (event === "complete") { setPlayResult(data); fetchRuns().then(setRuns); }
        if (event === "error") setPlayError(data?.message ?? "Run failed");
      },
      () => setPlayRunning(false),
      (err) => { setPlayError(err); setPlayRunning(false); },
    );
  };

  if (loading)
    return <div className="flex items-center justify-center pt-20 text-zinc-600 text-sm">Loading...</div>;
  if (error)
    return <div className="glass-card p-8 border-red-900/50 bg-red-950/20 text-red-400 text-sm">{error}</div>;

  const passRate = stats?.total_runs > 0
    ? Math.round(((stats.total_runs - (stats.total_violations ?? 0)) / stats.total_runs) * 100)
    : null;

  const containerVariants = { hidden: {}, show: { transition: { staggerChildren: 0.05 } } };
  const itemVariants = { hidden: { opacity: 0, y: 8 }, show: { opacity: 1, y: 0 } };
  const activeAgents = agents.filter((a) => a.status === "active");

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-zinc-100">Dashboard</h1>
          <p className="text-sm text-zinc-600 mt-0.5">Verifiable agent execution overview</p>
        </div>
        <Link to="/operator" className="no-underline">
          <button className="btn-primary">+ Register Agent</button>
        </Link>
      </div>

      {/* Stat cards */}
      <motion.div className="grid grid-cols-4 gap-4 mb-8" variants={containerVariants} initial="hidden" animate="show">
        <motion.div variants={itemVariants}>
          <StatCard label="Agents" value={stats?.total_agents ?? 0} icon={Bot}
            sub={`${activeAgents.length} active`} />
        </motion.div>
        <motion.div variants={itemVariants}>
          <StatCard label="Total Runs" value={stats?.total_runs ?? 0} icon={Activity}
            sub={<Sparkline runs={runs} />} />
        </motion.div>
        <motion.div variants={itemVariants}>
          <StatCard label="Claims" value={stats?.total_claims ?? 0} icon={FileWarning}
            sub={`${stats?.total_violations ?? 0} violations`} />
        </motion.div>
        <motion.div variants={itemVariants}>
          <motion.div className="glass-card p-5 flex flex-col gap-2" whileHover={{ y: -2 }} transition={{ duration: 0.15 }}>
            <div className="flex items-center justify-between">
              <span className="stat-label">Pass Rate</span>
              <div className="w-7 h-7 rounded-lg bg-zinc-800/80 flex items-center justify-center">
                <TrendingUp size={14} className="text-zinc-500" />
              </div>
            </div>
            <div className="flex items-center gap-4">
              <div className={`text-4xl font-bold tabular-nums ${
                passRate === null ? "text-zinc-600" :
                passRate >= 80 ? "text-emerald-400" : passRate >= 60 ? "text-amber-400" : "text-red-400"
              }`}>
                {passRate === null ? "—" : `${passRate}%`}
              </div>
              {passRate !== null && <RadialGauge value={passRate} />}
            </div>
          </motion.div>
        </motion.div>
      </motion.div>

      {/* ── Quick Run Playground ──────────────────────────────────────────── */}
      <motion.div
        className="glass-card p-5 mb-8 border-violet-900/30"
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
      >
        <div className="flex items-center gap-2 mb-4">
          <div className="w-6 h-6 rounded-md bg-violet-950/60 flex items-center justify-center">
            <Play size={12} className="text-violet-400" />
          </div>
          <h2 className="text-sm font-semibold text-zinc-100">Quick Run</h2>
          <span className="text-xs text-zinc-600">Try any agent directly</span>
        </div>

        {activeAgents.length === 0 ? (
          <div className="flex items-center gap-3 py-4 text-zinc-600 text-sm">
            <Bot size={16} />
            No active agents yet.{" "}
            <Link to="/operator" className="text-violet-400 no-underline hover:underline">Register one →</Link>
          </div>
        ) : (
          <form onSubmit={handlePlay} className="flex gap-3 items-end">
            <div className="w-44 flex-shrink-0">
              <label className="form-label">Agent</label>
              <div className="relative">
                <select
                  className="form-input appearance-none pr-7"
                  value={playAgentId}
                  onChange={(e) => setPlayAgentId(e.target.value)}
                >
                  {activeAgents.map((a) => (
                    <option key={a.id} value={a.id} className="bg-zinc-900">Agent #{a.id}</option>
                  ))}
                </select>
                <ChevronDown size={12} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-zinc-500 pointer-events-none" />
              </div>
            </div>
            <div className="flex-1">
              <label className="form-label">Prompt</label>
              <input
                className="form-input"
                value={playInput}
                onChange={(e) => setPlayInput(e.target.value)}
                placeholder="What is the current price of ETH?"
                required
              />
            </div>
            <button type="submit" disabled={playRunning || !playInput.trim()} className="btn-primary flex-shrink-0 self-end">
              <Play size={13} />
              {playRunning ? "Running…" : "Run"}
            </button>
          </form>
        )}

        <AnimatePresence>
          {playEvents.length > 0 && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="mt-4 space-y-1 overflow-hidden"
            >
              {playEvents.map((ev, i) => {
                const verdict = ev.data?.verdict;
                const color = ev.event === "policy_evaluated"
                  ? (verdict === "pass" ? "text-emerald-400" : "text-red-400")
                  : EVENT_COLORS[ev.event] ?? "text-zinc-500";
                return (
                  <div key={i} className={`text-xs font-mono flex items-center gap-2 ${color}`}>
                    <span className="opacity-40">›</span>
                    <span>{EVENT_LABELS[ev.event] ?? ev.event}</span>
                    {ev.event === "policy_evaluated" && (
                      <span className={`badge-${verdict === "pass" ? "pass" : "fail"}`}>{verdict}</span>
                    )}
                    {ev.event === "complete" && ev.data?.run_id && (
                      <Link to={`/runs/${ev.data.run_id}`} className="text-violet-400 flex items-center gap-1">
                        View run <ExternalLink size={10} />
                      </Link>
                    )}
                  </div>
                );
              })}
            </motion.div>
          )}
        </AnimatePresence>

        <AnimatePresence>
          {playResult?.output && (
            <motion.div
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              className="mt-3 p-3 rounded-lg bg-zinc-900/80 border border-zinc-700/60 text-sm text-zinc-200 leading-relaxed"
            >
              <div className="flex items-center gap-1.5 mb-2">
                <CheckCircle2 size={12} className="text-emerald-400" />
                <span className="text-xs text-zinc-500">Output</span>
                {playResult.run_id && (
                  <Link to={`/runs/${playResult.run_id}`} className="ml-auto text-xs text-violet-400 flex items-center gap-1 no-underline hover:underline">
                    Full run <ExternalLink size={10} />
                  </Link>
                )}
              </div>
              {playResult.output}
            </motion.div>
          )}
        </AnimatePresence>

        {playError && (
          <div className="mt-3 p-3 rounded-lg bg-red-950/30 border border-red-900/50 text-red-400 text-xs flex items-center gap-2">
            <XCircle size={12} /> {playError}
          </div>
        )}
      </motion.div>

      {/* Agents table */}
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-base font-semibold text-zinc-100">Agents</h2>
      </div>
      <div className="glass-card mb-6 overflow-hidden">
        {agents.length === 0 ? (
          <div className="flex flex-col items-center py-16 gap-4">
            <div className="w-12 h-12 rounded-xl bg-zinc-800/80 flex items-center justify-center">
              <Bot size={20} className="text-zinc-600" />
            </div>
            <p className="text-zinc-600 text-sm">No agents registered yet.</p>
            <Link to="/operator" className="no-underline">
              <button className="btn-ghost text-xs">Register Your First Agent</button>
            </Link>
          </div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Agent</th>
                <th>Metadata URI</th>
                <th>Status</th>
                <th>Trust Score</th>
                <th>Runs</th>
                <th>Violations</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {agents.map((a: any) => (
                <tr key={a.id}>
                  <td>
                    <div className="flex items-center gap-2.5">
                      <Identicon id={a.id} size={28} />
                      <Link to={`/agents/${a.id}`} className="font-mono text-xs text-violet-400">#{a.id}</Link>
                    </div>
                  </td>
                  <td className="max-w-[200px] truncate text-zinc-500 text-xs font-mono">{a.metadata_uri}</td>
                  <td>
                    {a.status === "active" ? (
                      <span className="badge-active flex items-center gap-1.5 w-fit">
                        <span className="w-1.5 h-1.5 rounded-full bg-blue-400 pulse-dot" />{a.status}
                      </span>
                    ) : (
                      <span className="badge-fail">{a.status}</span>
                    )}
                  </td>
                  <td>
                    <div className="flex items-center gap-2">
                      <svg width={32} height={32} className="-rotate-90">
                        <circle cx={16} cy={16} r={11} fill="none" stroke="#27272a" strokeWidth={3} />
                        <circle cx={16} cy={16} r={11} fill="none" stroke={scoreBorderColor(a.trust_score)}
                          strokeWidth={3}
                          strokeDasharray={`${(a.trust_score / 100) * 2 * Math.PI * 11} ${2 * Math.PI * 11}`}
                          strokeLinecap="round" />
                      </svg>
                      <span className={`text-sm font-bold tabular-nums ${scoreColor(a.trust_score)}`}>{a.trust_score}</span>
                    </div>
                  </td>
                  <td className="tabular-nums text-zinc-400">{a.total_runs}</td>
                  <td>
                    <span className={a.violations > 0 ? "text-red-400 tabular-nums font-medium" : "text-emerald-400 tabular-nums"}>
                      {a.violations}
                    </span>
                  </td>
                  <td>
                    <Link to={`/agents/${a.id}`} className="no-underline">
                      <button className="btn-ghost py-1 px-2 text-xs gap-1">View <ExternalLink size={11} /></button>
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Recent Runs */}
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-base font-semibold text-zinc-100">Recent Runs</h2>
        <Link to="/runs" className="text-xs text-zinc-500 hover:text-violet-400 flex items-center gap-1 no-underline transition-colors">
          View all <ArrowRight size={12} />
        </Link>
      </div>
      <div className="glass-card overflow-hidden">
        {runs.length === 0 ? (
          <div className="flex flex-col items-center py-12 gap-3">
            <Activity size={20} className="text-zinc-700" />
            <p className="text-zinc-600 text-sm">No runs yet.</p>
            <p className="text-zinc-700 text-xs">Use Quick Run above to execute your first run.</p>
          </div>
        ) : (
          <table className="data-table">
            <thead>
              <tr><th>Run ID</th><th>Agent</th><th>Verdict</th><th>Settlement TX</th><th>Time</th></tr>
            </thead>
            <tbody>
              {runs.slice(0, 10).map((r: any) => (
                <tr key={r.run_id}>
                  <td>
                    <div className="flex items-center gap-1.5">
                      <Link to={`/runs/${r.run_id}`} className="font-mono text-xs text-violet-400">
                        {r.run_id.substring(0, 12)}…
                      </Link>
                      <CopyButton value={r.run_id} />
                    </div>
                  </td>
                  <td><Link to={`/agents/${r.agent_id}`} className="text-xs text-zinc-400">#{r.agent_id}</Link></td>
                  <td><span className={`badge-${r.policy_verdict === "pass" ? "pass" : "fail"}`}>{r.policy_verdict}</span></td>
                  <td>
                    {r.settlement_tx ? (
                      <div className="flex items-center gap-1.5">
                        <span className="font-mono text-xs text-zinc-600">{r.settlement_tx.substring(0, 14)}…</span>
                        <CopyButton value={r.settlement_tx} />
                      </div>
                    ) : <span className="text-zinc-700">—</span>}
                  </td>
                  <td className="text-xs text-zinc-600">{r.created_at ? new Date(r.created_at).toLocaleString() : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
