import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchDashboardStats, fetchAgents, fetchRuns } from "../api";

export default function Dashboard() {
  const [stats, setStats] = useState<any>(null);
  const [agents, setAgents] = useState<any[]>([]);
  const [runs, setRuns] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([fetchDashboardStats(), fetchAgents(), fetchRuns()])
      .then(([s, a, r]) => {
        setStats(s);
        setAgents(a);
        setRuns(r);
      })
      .catch((err) => setError(err.response?.data?.detail || err.message || "Failed to load"))
      .finally(() => setLoading(false));
  }, []);

  if (loading)
    return <div style={{ textAlign: "center", paddingTop: 80, color: "#666" }}>Loading...</div>;

  if (error)
    return (
      <div style={{ background: "#1a0a0a", border: "1px solid #3a1a1a", borderRadius: 12, padding: 32, color: "#f44336" }}>
        {error}
      </div>
    );

  const passRate =
    stats?.total_runs > 0
      ? Math.round(((stats.total_runs - (stats.total_violations ?? 0)) / stats.total_runs) * 100)
      : null;

  const scoreColor = (s: number) => (s >= 80 ? "#4caf50" : s >= 60 ? "#ff9800" : "#f44336");

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 24 }}>
        <h1 style={{ marginBottom: 0 }}>Dashboard</h1>
        <Link to="/operator">
          <button>+ Register Agent</button>
        </Link>
      </div>

      <div className="grid" style={{ marginBottom: 32 }}>
        <div className="stat-card">
          <h3>Agents</h3>
          <div className="value">{stats?.total_agents ?? 0}</div>
        </div>
        <div className="stat-card">
          <h3>Total Runs</h3>
          <div className="value">{stats?.total_runs ?? 0}</div>
        </div>
        <div className="stat-card">
          <h3>Claims</h3>
          <div className="value">{stats?.total_claims ?? 0}</div>
        </div>
        <div className="stat-card">
          <h3>Pass Rate</h3>
          <div
            className="value"
            style={{
              color:
                passRate === null
                  ? "#666"
                  : passRate >= 80
                  ? "#4caf50"
                  : passRate >= 60
                  ? "#ff9800"
                  : "#f44336",
            }}
          >
            {passRate === null ? "—" : `${passRate}%`}
          </div>
        </div>
      </div>

      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
        <h2 style={{ marginBottom: 0 }}>Agents</h2>
      </div>
      <div className="card">
        {agents.length === 0 ? (
          <div style={{ textAlign: "center", padding: "48px 0", color: "#666" }}>
            <p style={{ marginBottom: 16 }}>No agents registered yet.</p>
            <Link to="/operator">
              <button>Register Your First Agent</button>
            </Link>
          </div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>ID</th>
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
                    <Link to={`/agents/${a.id}`}>#{a.id}</Link>
                  </td>
                  <td
                    style={{
                      maxWidth: 220,
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                      fontSize: 13,
                      color: "#aaa",
                    }}
                  >
                    {a.metadata_uri}
                  </td>
                  <td>
                    <span className={`badge badge-${a.status === "active" ? "active" : "fail"}`}>
                      {a.status}
                    </span>
                  </td>
                  <td>
                    <span
                      className="score-ring"
                      style={{
                        width: 40,
                        height: 40,
                        fontSize: 14,
                        borderColor: scoreColor(a.trust_score),
                        color: scoreColor(a.trust_score),
                      }}
                    >
                      {a.trust_score}
                    </span>
                  </td>
                  <td>{a.total_runs}</td>
                  <td>
                    <span style={{ color: a.violations > 0 ? "#f44336" : "#4caf50" }}>
                      {a.violations}
                    </span>
                  </td>
                  <td>
                    <Link to={`/agents/${a.id}`}>
                      <button style={{ padding: "4px 12px", fontSize: 12 }}>View</button>
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
        <h2 style={{ marginBottom: 0 }}>Recent Runs</h2>
        <Link to="/runs" style={{ fontSize: 13, color: "#6c63ff" }}>
          View all →
        </Link>
      </div>
      <div className="card">
        {runs.length === 0 ? (
          <div style={{ textAlign: "center", padding: "32px 0", color: "#555" }}>
            No runs yet. Select an agent and execute a run.
          </div>
        ) : (
          <table>
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
                    <Link to={`/runs/${r.run_id}`}>{r.run_id.substring(0, 12)}...</Link>
                  </td>
                  <td>
                    <Link to={`/agents/${r.agent_id}`}>#{r.agent_id}</Link>
                  </td>
                  <td>
                    <span className={`badge badge-${r.policy_verdict === "pass" ? "pass" : "fail"}`}>
                      {r.policy_verdict}
                    </span>
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
    </div>
  );
}
