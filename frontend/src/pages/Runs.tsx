import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchRuns } from "../api";
import { Filter } from "lucide-react";
import { motion } from "framer-motion";

type VerdictFilter = "all" | "pass" | "fail";

export default function Runs() {
  const [runs, setRuns] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [verdict, setVerdict] = useState<VerdictFilter>("all");
  const [agentFilter, setAgentFilter] = useState("");
  const [refreshing, setRefreshing] = useState(false);

  const load = async (silent = false) => {
    if (!silent) setLoading(true);
    else setRefreshing(true);
    setError(null);
    try {
      const agentId = agentFilter ? parseInt(agentFilter) : undefined;
      const data = await fetchRuns(agentId);
      setRuns(data);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || "Failed to load runs");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleFilter = (e: React.FormEvent) => { e.preventDefault(); load(); };

  const filtered = verdict === "all" ? runs : runs.filter((r) => r.policy_verdict === verdict);

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-zinc-100">Runs</h1>
          <p className="text-sm text-zinc-600 mt-0.5">Agent execution history</p>
        </div>
        <button
          onClick={() => load(true)}
          disabled={refreshing}
          className="btn-ghost gap-2"
        >
          {refreshing ? "Refreshing..." : "↻ Refresh"}
        </button>
      </div>

      {/* Filter bar */}
      <div className="glass-card p-4 mb-4 flex items-center gap-4 flex-wrap">
        <form onSubmit={handleFilter} className="flex items-end gap-3">
          <div>
            <label className="form-label flex items-center gap-1.5">
              <Filter size={10} /> Agent ID
            </label>
            <input
              className="form-input w-36"
              value={agentFilter}
              onChange={(e) => setAgentFilter(e.target.value)}
              placeholder="All agents"
            />
          </div>
          <button type="submit" className="btn-primary py-2">
            Filter
          </button>
        </form>

        {/* Verdict toggle */}
        <div className="ml-auto flex items-center gap-1 bg-zinc-900 rounded-lg p-1 border border-zinc-800">
          {(["all", "pass", "fail"] as VerdictFilter[]).map((v) => (
            <button
              key={v}
              onClick={() => setVerdict(v)}
              className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all cursor-pointer border-0 ${
                verdict === v
                  ? v === "pass"
                    ? "bg-emerald-950 text-emerald-400 border border-emerald-900"
                    : v === "fail"
                    ? "bg-red-950 text-red-400 border border-red-900"
                    : "bg-violet-950 text-violet-400 border border-violet-900"
                  : "text-zinc-600 hover:text-zinc-300 bg-transparent"
              }`}
            >
              {v.charAt(0).toUpperCase() + v.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center pt-16 text-zinc-600 text-sm">Loading...</div>
      ) : error ? (
        <div className="glass-card p-6 border-red-900/50 bg-red-950/20 text-red-400 text-sm">{error}</div>
      ) : (
        <motion.div
          className="glass-card overflow-hidden"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.2 }}
        >
          <div className="px-4 py-3 border-b border-zinc-800/60 flex items-center justify-between">
            <span className="text-xs text-zinc-600">
              {filtered.length} run{filtered.length !== 1 ? "s" : ""}
              {verdict !== "all" ? ` (${verdict})` : ""}
            </span>
          </div>
          {filtered.length === 0 ? (
            <div className="py-12 text-center text-zinc-600 text-sm">
              No runs match the current filter.
            </div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Run ID</th>
                  <th>Agent</th>
                  <th>Verdict</th>
                  <th>Violations</th>
                  <th>Settlement TX</th>
                  <th>Time</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((r: any) => (
                  <tr key={r.run_id}>
                    <td>
                      <Link to={`/runs/${r.run_id}`} className="font-mono text-xs text-violet-400">
                        {r.run_id.substring(0, 16)}...
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
                    <td>
                      {r.reason_codes && r.reason_codes.length > 0 ? (
                        <span className="text-xs text-red-400 font-mono">
                          {r.reason_codes.join(", ")}
                        </span>
                      ) : (
                        <span className="text-zinc-700">—</span>
                      )}
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
        </motion.div>
      )}
    </div>
  );
}
