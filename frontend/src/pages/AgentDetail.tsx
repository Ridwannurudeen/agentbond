import React, { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { fetchAgent, fetchRuns, fetchClaims, fetchScore, fetchPolicies } from "../api";

export default function AgentDetail() {
  const { id } = useParams<{ id: string }>();
  const [agent, setAgent] = useState<any>(null);
  const [runs, setRuns] = useState<any[]>([]);
  const [claims, setClaims] = useState<any[]>([]);
  const [score, setScore] = useState<any>(null);
  const [policies, setPolicies] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;
    const agentId = parseInt(id);
    Promise.all([
      fetchAgent(agentId),
      fetchRuns(agentId),
      fetchClaims(agentId),
      fetchScore(agentId),
      fetchPolicies(agentId),
    ])
      .then(([a, r, c, s, p]) => {
        setAgent(a);
        setRuns(r);
        setClaims(c);
        setScore(s);
        setPolicies(p);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return <p>Loading...</p>;
  if (!agent) return <p>Agent not found</p>;

  return (
    <div>
      <h1>Agent #{agent.id}</h1>

      <div className="grid" style={{ marginBottom: 24 }}>
        <div className="stat-card">
          <h3>Trust Score</h3>
          <div className="score-ring">{agent.trust_score}</div>
        </div>
        <div className="stat-card">
          <h3>Total Runs</h3>
          <div className="value">{agent.total_runs}</div>
        </div>
        <div className="stat-card">
          <h3>Violations</h3>
          <div className="value">{agent.violations}</div>
        </div>
        <div className="stat-card">
          <h3>Status</h3>
          <span className={`badge badge-${agent.status === "active" ? "active" : "fail"}`}>
            {agent.status}
          </span>
        </div>
      </div>

      <div className="card">
        <h3>Details</h3>
        <p><strong>Operator ID:</strong> {agent.operator_id}</p>
        <p><strong>Metadata URI:</strong> {agent.metadata_uri}</p>
        <p><strong>Active Version:</strong> {agent.active_version}</p>
        <p><strong>Created:</strong> {agent.created_at}</p>
      </div>

      {score?.breakdown && (
        <div className="card">
          <h3>Score Breakdown</h3>
          <p>Base: {score.breakdown.base}</p>
          <p>Violation Penalty: -{score.breakdown.violation_penalty}</p>
          <p>Claim Penalty: -{score.breakdown.claim_penalty}</p>
          <p>Recency Bonus: +{score.breakdown.recency_bonus}</p>
        </div>
      )}

      <h2>Policies</h2>
      <div className="card">
        <table>
          <thead>
            <tr><th>ID</th><th>Hash</th><th>Status</th><th>Created</th></tr>
          </thead>
          <tbody>
            {policies.map((p: any) => (
              <tr key={p.id}>
                <td>#{p.id}</td>
                <td style={{ fontFamily: "monospace", fontSize: 12 }}>{p.policy_hash?.substring(0, 16)}...</td>
                <td><span className={`badge badge-${p.status === "active" ? "active" : "pending"}`}>{p.status}</span></td>
                <td>{p.created_at ? new Date(p.created_at).toLocaleString() : "-"}</td>
              </tr>
            ))}
            {policies.length === 0 && <tr><td colSpan={4} style={{ color: "#666" }}>No policies</td></tr>}
          </tbody>
        </table>
      </div>

      <h2>Runs</h2>
      <div className="card">
        <table>
          <thead>
            <tr><th>Run ID</th><th>Verdict</th><th>Settlement TX</th><th>Time</th></tr>
          </thead>
          <tbody>
            {runs.slice(0, 20).map((r: any) => (
              <tr key={r.run_id}>
                <td><Link to={`/runs/${r.run_id}`}>{r.run_id.substring(0, 12)}...</Link></td>
                <td><span className={`badge badge-${r.policy_verdict}`}>{r.policy_verdict}</span></td>
                <td style={{ fontFamily: "monospace", fontSize: 12 }}>{r.settlement_tx?.substring(0, 14) || "-"}</td>
                <td>{r.created_at ? new Date(r.created_at).toLocaleString() : "-"}</td>
              </tr>
            ))}
            {runs.length === 0 && <tr><td colSpan={4} style={{ color: "#666" }}>No runs yet</td></tr>}
          </tbody>
        </table>
      </div>

      <h2>Claims</h2>
      <div className="card">
        <table>
          <thead>
            <tr><th>ID</th><th>Reason</th><th>Status</th><th>Created</th></tr>
          </thead>
          <tbody>
            {claims.map((c: any) => (
              <tr key={c.id}>
                <td>#{c.id}</td>
                <td>{c.reason_code}</td>
                <td><span className={`badge badge-${c.status === "approved" || c.status === "paid" ? "pass" : "pending"}`}>{c.status}</span></td>
                <td>{c.created_at ? new Date(c.created_at).toLocaleString() : "-"}</td>
              </tr>
            ))}
            {claims.length === 0 && <tr><td colSpan={4} style={{ color: "#666" }}>No claims</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
