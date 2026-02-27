import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchRuns } from "../api";

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

  useEffect(() => {
    load();
  }, []);

  const handleFilter = (e: React.FormEvent) => {
    e.preventDefault();
    load();
  };

  const filtered =
    verdict === "all" ? runs : runs.filter((r) => r.policy_verdict === verdict);

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 24 }}>
        <h1 style={{ marginBottom: 0 }}>Runs</h1>
        <button
          onClick={() => load(true)}
          disabled={refreshing}
          style={{ background: "transparent", border: "1px solid #2a2a3a", color: "#aaa" }}
        >
          {refreshing ? "Refreshing..." : "↻ Refresh"}
        </button>
      </div>

      <div className="card" style={{ display: "flex", gap: 12, alignItems: "flex-end", flexWrap: "wrap", marginBottom: 16 }}>
        <form onSubmit={handleFilter} style={{ display: "flex", gap: 12, alignItems: "flex-end" }}>
          <div className="form-group" style={{ marginBottom: 0 }}>
            <label>Agent ID</label>
            <input
              value={agentFilter}
              onChange={(e) => setAgentFilter(e.target.value)}
              placeholder="All agents"
              style={{ width: 140 }}
            />
          </div>
          <button type="submit" style={{ height: 40 }}>
            Filter
          </button>
        </form>

        <div style={{ display: "flex", gap: 8, marginLeft: "auto" }}>
          {(["all", "pass", "fail"] as VerdictFilter[]).map((v) => (
            <button
              key={v}
              onClick={() => setVerdict(v)}
              style={{
                background:
                  verdict === v
                    ? v === "pass"
                      ? "#1a3a1a"
                      : v === "fail"
                      ? "#3a1a1a"
                      : "#1a1a3a"
                    : "transparent",
                border: "1px solid #2a2a3a",
                color:
                  verdict === v
                    ? v === "pass"
                      ? "#4caf50"
                      : v === "fail"
                      ? "#f44336"
                      : "#6c63ff"
                    : "#666",
                padding: "6px 14px",
                fontSize: 13,
              }}
            >
              {v === "all" ? "All" : v.charAt(0).toUpperCase() + v.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div style={{ textAlign: "center", paddingTop: 60, color: "#666" }}>Loading...</div>
      ) : error ? (
        <div style={{ background: "#1a0a0a", border: "1px solid #3a1a1a", borderRadius: 12, padding: 24, color: "#f44336" }}>
          {error}
        </div>
      ) : (
        <div className="card">
          <div style={{ fontSize: 13, color: "#666", marginBottom: 12 }}>
            {filtered.length} run{filtered.length !== 1 ? "s" : ""}
            {verdict !== "all" ? ` (${verdict})` : ""}
          </div>
          {filtered.length === 0 ? (
            <div style={{ textAlign: "center", padding: "40px 0", color: "#555" }}>
              No runs match the current filter.
            </div>
          ) : (
            <table>
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
                    <td style={{ fontFamily: "monospace", fontSize: 13 }}>
                      <Link to={`/runs/${r.run_id}`}>{r.run_id.substring(0, 16)}...</Link>
                    </td>
                    <td>
                      <Link to={`/agents/${r.agent_id}`}>#{r.agent_id}</Link>
                    </td>
                    <td>
                      <span className={`badge badge-${r.policy_verdict === "pass" ? "pass" : "fail"}`}>
                        {r.policy_verdict}
                      </span>
                    </td>
                    <td>
                      {r.reason_codes && r.reason_codes.length > 0 ? (
                        <span style={{ fontSize: 12, color: "#f44336" }}>
                          {r.reason_codes.join(", ")}
                        </span>
                      ) : (
                        <span style={{ color: "#555" }}>—</span>
                      )}
                    </td>
                    <td style={{ fontFamily: "monospace", fontSize: 12, color: "#aaa" }}>
                      {r.settlement_tx ? `${r.settlement_tx.substring(0, 14)}...` : "—"}
                    </td>
                    <td style={{ fontSize: 13, color: "#aaa" }}>
                      {r.created_at ? new Date(r.created_at).toLocaleString() : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}
