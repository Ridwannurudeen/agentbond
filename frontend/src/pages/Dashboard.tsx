import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchStats, fetchAgents, fetchRuns } from "../api";

export default function Dashboard() {
  const [stats, setStats] = useState<any>(null);
  const [agents, setAgents] = useState<any[]>([]);
  const [runs, setRuns] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([fetchStats(), fetchAgents(), fetchRuns()])
      .then(([s, a, r]) => {
        setStats(s);
        setAgents(a);
        setRuns(r);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p>Loading...</p>;

  return (
    <div>
      <h1>Dashboard</h1>

      {stats && (
        <div className="grid" style={{ marginBottom: 32 }}>
          <div className="stat-card">
            <h3>Agents</h3>
            <div className="value">{stats.total_agents}</div>
          </div>
          <div className="stat-card">
            <h3>Total Runs</h3>
            <div className="value">{stats.total_runs}</div>
          </div>
          <div className="stat-card">
            <h3>Claims</h3>
            <div className="value">{stats.total_claims}</div>
          </div>
          <div className="stat-card">
            <h3>Violations</h3>
            <div className="value">{stats.total_violations}</div>
          </div>
        </div>
      )}

      <h2>Agents</h2>
      <div className="card">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Metadata</th>
              <th>Status</th>
              <th>Trust Score</th>
              <th>Runs</th>
              <th>Violations</th>
            </tr>
          </thead>
          <tbody>
            {agents.map((a: any) => (
              <tr key={a.id}>
                <td>
                  <Link to={`/agents/${a.id}`}>#{a.id}</Link>
                </td>
                <td style={{ maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis" }}>
                  {a.metadata_uri}
                </td>
                <td>
                  <span className={`badge badge-${a.status === "active" ? "active" : "fail"}`}>
                    {a.status}
                  </span>
                </td>
                <td>
                  <span className="score-ring" style={{ width: 40, height: 40, fontSize: 14 }}>
                    {a.trust_score}
                  </span>
                </td>
                <td>{a.total_runs}</td>
                <td>{a.violations}</td>
              </tr>
            ))}
            {agents.length === 0 && (
              <tr>
                <td colSpan={6} style={{ textAlign: "center", color: "#666" }}>
                  No agents registered yet
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <h2>Recent Runs</h2>
      <div className="card">
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
                  <Link to={`/runs/${r.run_id}`}>
                    {r.run_id.substring(0, 12)}...
                  </Link>
                </td>
                <td>
                  <Link to={`/agents/${r.agent_id}`}>#{r.agent_id}</Link>
                </td>
                <td>
                  <span className={`badge badge-${r.policy_verdict}`}>
                    {r.policy_verdict}
                  </span>
                </td>
                <td style={{ fontFamily: "monospace", fontSize: 12 }}>
                  {r.settlement_tx ? `${r.settlement_tx.substring(0, 14)}...` : "-"}
                </td>
                <td>{r.created_at ? new Date(r.created_at).toLocaleString() : "-"}</td>
              </tr>
            ))}
            {runs.length === 0 && (
              <tr>
                <td colSpan={5} style={{ textAlign: "center", color: "#666" }}>
                  No runs yet
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
