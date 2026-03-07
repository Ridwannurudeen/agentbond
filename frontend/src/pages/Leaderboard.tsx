import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchAgents } from "../api";
import { Trophy, TrendingUp, Activity, ShieldAlert } from "lucide-react";
import { motion } from "framer-motion";

function Identicon({ id, size = 32 }: { id: number; size?: number }) {
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
    <svg width={size} height={size} style={{ borderRadius: 7, display: "block", flexShrink: 0 }}>
      <rect width={size} height={size} fill="#18181b" />
      {grid.map((row, y) =>
        row.map((filled, x) =>
          filled ? <rect key={`${x}-${y}`} x={x * cs} y={y * cs} width={cs} height={cs} fill={color} /> : null
        )
      )}
    </svg>
  );
}

function ScoreBar({ score }: { score: number }) {
  const color = score >= 80 ? "#10b981" : score >= 60 ? "#f59e0b" : "#ef4444";
  return (
    <div className="flex items-center gap-3 w-full">
      <div className="flex-1 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-700"
          style={{ width: `${score}%`, backgroundColor: color }}
        />
      </div>
      <span
        className="text-sm font-bold tabular-nums w-8 text-right"
        style={{ color }}
      >
        {score}
      </span>
    </div>
  );
}

const MEDAL: Record<number, { icon: string; cls: string }> = {
  0: { icon: "🥇", cls: "text-yellow-400" },
  1: { icon: "🥈", cls: "text-zinc-400" },
  2: { icon: "🥉", cls: "text-amber-700" },
};

export default function Leaderboard() {
  const [agents, setAgents] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [sortBy, setSortBy] = useState<"score" | "runs" | "violations">("score");

  useEffect(() => {
    fetchAgents()
      .then((data) => setAgents(data))
      .finally(() => setLoading(false));
  }, []);

  const sorted = [...agents].sort((a, b) => {
    if (sortBy === "score") return b.trust_score - a.trust_score;
    if (sortBy === "runs") return b.total_runs - a.total_runs;
    return b.violations - a.violations;
  });

  const topScore = sorted[0]?.trust_score ?? 100;
  const totalRuns = agents.reduce((s, a) => s + a.total_runs, 0);
  const cleanAgents = agents.filter((a) => a.violations === 0 && a.total_runs > 0).length;
  const avgScore = agents.length
    ? Math.round(agents.reduce((s, a) => s + a.trust_score, 0) / agents.length)
    : 0;

  if (loading)
    return <div className="flex items-center justify-center pt-20 text-zinc-600 text-sm">Loading...</div>;

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-zinc-100">Leaderboard</h1>
          <p className="text-sm text-zinc-600 mt-0.5">Agents ranked by trust score</p>
        </div>
      </div>

      {/* Summary stats */}
      <div className="grid grid-cols-4 gap-4 mb-8">
        {[
          { label: "Agents", value: agents.length, icon: Trophy, color: "text-zinc-100" },
          { label: "Avg Score", value: avgScore, icon: TrendingUp, color: avgScore >= 80 ? "text-emerald-400" : avgScore >= 60 ? "text-amber-400" : "text-red-400" },
          { label: "Total Runs", value: totalRuns, icon: Activity, color: "text-zinc-100" },
          { label: "Clean Agents", value: cleanAgents, icon: ShieldAlert, color: "text-emerald-400" },
        ].map(({ label, value, icon: Icon, color }) => (
          <motion.div key={label} className="glass-card p-5" whileHover={{ y: -2 }} transition={{ duration: 0.15 }}>
            <div className="flex items-center justify-between mb-2">
              <span className="stat-label">{label}</span>
              <Icon size={13} className="text-zinc-700" />
            </div>
            <div className={`text-3xl font-bold tabular-nums ${color}`}>{value}</div>
          </motion.div>
        ))}
      </div>

      {/* Sort tabs */}
      <div className="flex items-center gap-1 mb-4">
        {(["score", "runs", "violations"] as const).map((s) => (
          <button
            key={s}
            onClick={() => setSortBy(s)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors border-0 cursor-pointer ${
              sortBy === s
                ? "bg-violet-500/15 text-violet-400 border border-violet-500/30"
                : "bg-transparent text-zinc-500 hover:text-zinc-300"
            }`}
          >
            {s === "score" ? "Trust Score" : s === "runs" ? "Most Runs" : "Most Violations"}
          </button>
        ))}
      </div>

      {/* Leaderboard table */}
      <div className="glass-card overflow-hidden">
        {sorted.length === 0 ? (
          <div className="py-16 text-center text-zinc-600 text-sm">
            No agents yet. <Link to="/operator" className="text-violet-400 no-underline hover:underline">Register one →</Link>
          </div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th className="w-12">Rank</th>
                <th>Agent</th>
                <th>Status</th>
                <th className="w-48">Trust Score</th>
                <th>Runs</th>
                <th>Violations</th>
                <th>Pass Rate</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((a, i) => {
                const passRate = a.total_runs > 0
                  ? Math.round(((a.total_runs - a.violations) / a.total_runs) * 100)
                  : null;
                const isTop3 = i < 3;

                return (
                  <motion.tr
                    key={a.id}
                    initial={{ opacity: 0, x: -8 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.03, duration: 0.2 }}
                  >
                    <td>
                      {isTop3 ? (
                        <span className="text-base">{MEDAL[i].icon}</span>
                      ) : (
                        <span className="text-zinc-600 tabular-nums text-sm font-mono">#{i + 1}</span>
                      )}
                    </td>
                    <td>
                      <div className="flex items-center gap-2.5">
                        <Identicon id={a.id} size={32} />
                        <div>
                          <Link to={`/agents/${a.id}`} className="text-xs font-mono text-violet-400 block">
                            Agent #{a.id}
                          </Link>
                          <span className="text-[10px] text-zinc-600 truncate max-w-[140px] block">
                            {a.metadata_uri}
                          </span>
                        </div>
                      </div>
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
                    <td className="w-48">
                      <ScoreBar score={a.trust_score} />
                    </td>
                    <td className="tabular-nums text-zinc-400">{a.total_runs}</td>
                    <td>
                      <span className={a.violations > 0 ? "text-red-400 tabular-nums font-medium" : "text-emerald-400 tabular-nums"}>
                        {a.violations}
                      </span>
                    </td>
                    <td>
                      {passRate !== null ? (
                        <span className={`tabular-nums text-sm font-medium ${
                          passRate === 100 ? "text-emerald-400" : passRate >= 80 ? "text-emerald-400" : passRate >= 60 ? "text-amber-400" : "text-red-400"
                        }`}>
                          {passRate}%
                        </span>
                      ) : (
                        <span className="text-zinc-700">—</span>
                      )}
                    </td>
                    <td>
                      <Link to={`/agents/${a.id}`} className="no-underline">
                        <button className="btn-ghost py-1 px-2 text-xs">View</button>
                      </Link>
                    </td>
                  </motion.tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
