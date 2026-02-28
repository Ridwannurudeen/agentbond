import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchDashboardStats, fetchAgents, fetchRuns } from "../api";
import { Bot, Activity, FileWarning, TrendingUp, ArrowRight, ExternalLink } from "lucide-react";
import { motion } from "framer-motion";

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
      <circle
        cx={36} cy={36} r={r}
        fill="none"
        stroke={color}
        strokeWidth={6}
        strokeDasharray={`${dash} ${circ}`}
        strokeLinecap="round"
        style={{ transition: "stroke-dasharray 0.6s ease" }}
      />
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

// ── Score colour helper ──────────────────────────────────────────────────────
const scoreColor = (s: number) =>
  s >= 80 ? "text-emerald-400" : s >= 60 ? "text-amber-400" : "text-red-400";

const scoreBorderColor = (s: number) =>
  s >= 80 ? "#10b981" : s >= 60 ? "#f59e0b" : "#ef4444";

// ── Stat card ────────────────────────────────────────────────────────────────
function StatCard({
  label,
  value,
  icon: Icon,
  sub,
}: {
  label: string;
  value: React.ReactNode;
  icon: React.ElementType;
  sub?: React.ReactNode;
}) {
  return (
    <motion.div
      className="glass-card p-5 flex flex-col gap-3"
      whileHover={{ y: -2 }}
      transition={{ duration: 0.15 }}
    >
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

// ── Main ─────────────────────────────────────────────────────────────────────
export default function Dashboard() {
  const [stats, setStats] = useState<any>(null);
  const [agents, setAgents] = useState<any[]>([]);
  const [runs, setRuns] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([fetchDashboardStats(), fetchAgents(), fetchRuns()])
      .then(([s, a, r]) => { setStats(s); setAgents(a); setRuns(r); })
      .catch((err) => setError(err.response?.data?.detail || err.message || "Failed to load"))
      .finally(() => setLoading(false));
  }, []);

  if (loading)
    return (
      <div className="flex items-center justify-center pt-20 text-zinc-600 text-sm">
        Loading...
      </div>
    );

  if (error)
    return (
      <div className="glass-card p-8 border-red-900/50 bg-red-950/20 text-red-400 text-sm">
        {error}
      </div>
    );

  const passRate =
    stats?.total_runs > 0
      ? Math.round(((stats.total_runs - (stats.total_violations ?? 0)) / stats.total_runs) * 100)
      : null;

  const containerVariants = {
    hidden: {},
    show: { transition: { staggerChildren: 0.05 } },
  };
  const itemVariants = {
    hidden: { opacity: 0, y: 8 },
    show: { opacity: 1, y: 0 },
  };

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-zinc-100">Dashboard</h1>
          <p className="text-sm text-zinc-600 mt-0.5">Verifiable agent execution overview</p>
        </div>
        <Link to="/operator" className="no-underline">
          <button className="btn-primary">
            + Register Agent
          </button>
        </Link>
      </div>

      {/* Stat cards — bento grid */}
      <motion.div
        className="grid grid-cols-4 gap-4 mb-8"
        variants={containerVariants}
        initial="hidden"
        animate="show"
      >
        <motion.div variants={itemVariants}>
          <StatCard
            label="Agents"
            value={stats?.total_agents ?? 0}
            icon={Bot}
            sub={`${agents.filter((a) => a.status === "active").length} active`}
          />
        </motion.div>
        <motion.div variants={itemVariants}>
          <StatCard
            label="Total Runs"
            value={stats?.total_runs ?? 0}
            icon={Activity}
            sub={<Sparkline runs={runs} />}
          />
        </motion.div>
        <motion.div variants={itemVariants}>
          <StatCard
            label="Claims"
            value={stats?.total_claims ?? 0}
            icon={FileWarning}
            sub={`${stats?.total_violations ?? 0} violations`}
          />
        </motion.div>

        {/* Pass rate card with radial gauge */}
        <motion.div variants={itemVariants}>
          <motion.div className="glass-card p-5 flex flex-col gap-2" whileHover={{ y: -2 }} transition={{ duration: 0.15 }}>
            <div className="flex items-center justify-between">
              <span className="stat-label">Pass Rate</span>
              <div className="w-7 h-7 rounded-lg bg-zinc-800/80 flex items-center justify-center">
                <TrendingUp size={14} className="text-zinc-500" />
              </div>
            </div>
            <div className="flex items-center gap-4">
              <div>
                <div
                  className={`text-4xl font-bold tabular-nums ${
                    passRate === null
                      ? "text-zinc-600"
                      : passRate >= 80
                      ? "text-emerald-400"
                      : passRate >= 60
                      ? "text-amber-400"
                      : "text-red-400"
                  }`}
                >
                  {passRate === null ? "—" : `${passRate}%`}
                </div>
              </div>
              {passRate !== null && <RadialGauge value={passRate} />}
            </div>
          </motion.div>
        </motion.div>
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
                      <Link to={`/agents/${a.id}`} className="font-mono text-xs text-violet-400">
                        #{a.id}
                      </Link>
                    </div>
                  </td>
                  <td className="max-w-[200px] truncate text-zinc-500 text-xs font-mono">
                    {a.metadata_uri}
                  </td>
                  <td>
                    {a.status === "active" ? (
                      <span className="badge-active flex items-center gap-1.5 w-fit">
                        <span className="w-1.5 h-1.5 rounded-full bg-blue-400 pulse-dot" />
                        {a.status}
                      </span>
                    ) : (
                      <span className="badge-fail">{a.status}</span>
                    )}
                  </td>
                  <td>
                    <div className="flex items-center gap-2">
                      <svg width={32} height={32} className="-rotate-90">
                        <circle cx={16} cy={16} r={11} fill="none" stroke="#27272a" strokeWidth={3} />
                        <circle
                          cx={16} cy={16} r={11}
                          fill="none"
                          stroke={scoreBorderColor(a.trust_score)}
                          strokeWidth={3}
                          strokeDasharray={`${(a.trust_score / 100) * 2 * Math.PI * 11} ${2 * Math.PI * 11}`}
                          strokeLinecap="round"
                        />
                      </svg>
                      <span className={`text-sm font-bold tabular-nums ${scoreColor(a.trust_score)}`}>
                        {a.trust_score}
                      </span>
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
                      <button className="btn-ghost py-1 px-2 text-xs gap-1">
                        View <ExternalLink size={11} />
                      </button>
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
          View all → <ArrowRight size={12} />
        </Link>
      </div>
      <div className="glass-card overflow-hidden">
        {runs.length === 0 ? (
          <div className="py-12 text-center text-zinc-600 text-sm">
            No runs yet. Select an agent and execute a run.
          </div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Run ID</th>
                <th>Agent</th>
                <th>Verdict</th>
                <th>Settlement TX</th>
                <th>Time</th>
              </tr>
            </thead>
            <tbody>
              {runs.slice(0, 10).map((r: any) => (
                <tr key={r.run_id}>
                  <td>
                    <Link to={`/runs/${r.run_id}`} className="font-mono text-xs text-violet-400">
                      {r.run_id.substring(0, 12)}...
                    </Link>
                  </td>
                  <td>
                    <Link to={`/agents/${r.agent_id}`} className="text-xs text-zinc-400">
                      #{r.agent_id}
                    </Link>
                  </td>
                  <td>
                    <span className={`badge-${r.policy_verdict === "pass" ? "pass" : "fail"}`}>
                      {r.policy_verdict}
                    </span>
                  </td>
                  <td className="font-mono text-xs text-zinc-600">
                    {r.settlement_tx ? `${r.settlement_tx.substring(0, 14)}...` : "—"}
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
    </div>
  );
}
