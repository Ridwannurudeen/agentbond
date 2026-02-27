import React, { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import {
  fetchAgent,
  fetchRuns,
  fetchClaims,
  fetchScore,
  fetchPolicies,
  executeRun,
  activatePolicy,
} from "../api";

function ScoreRing({ score }: { score: number }) {
  const color = score >= 80 ? "#4caf50" : score >= 60 ? "#ff9800" : "#f44336";
  return (
    <div className="score-ring" style={{ borderColor: color, color, width: 64, height: 64, fontSize: 22 }}>
      {score}
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

  // Run executor state
  const [userInput, setUserInput] = useState("");
  const [running, setRunning] = useState(false);
  const [runResult, setRunResult] = useState<any>(null);
  const [runError, setRunError] = useState<string | null>(null);

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
      .catch((err) => setError(err.response?.data?.detail || err.message || "Failed to load agent"))
      .finally(() => setLoading(false));
  }, [id]);

  const handleRun = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!id) return;
    setRunning(true);
    setRunResult(null);
    setRunError(null);
    try {
      const res = await executeRun(parseInt(id), userInput);
      setRunResult(res);
      // Refresh runs list and agent stats
      const [updatedRuns, updatedAgent] = await Promise.all([
        fetchRuns(parseInt(id)),
        fetchAgent(parseInt(id)),
      ]);
      setRuns(updatedRuns);
      setAgent(updatedAgent);
    } catch (err: any) {
      setRunError(err.response?.data?.detail || err.message || "Run failed");
    }
    setRunning(false);
  };

  const handleActivatePolicy = async (policyId: number) => {
    try {
      await activatePolicy(policyId);
      const updated = await fetchPolicies(parseInt(id!));
      setPolicies(updated);
    } catch (err: any) {
      alert(err.response?.data?.detail || err.message);
    }
  };

  if (loading)
    return <div style={{ textAlign: "center", paddingTop: 80, color: "#666" }}>Loading...</div>;
  if (error)
    return (
      <div style={{ background: "#1a0a0a", border: "1px solid #3a1a1a", borderRadius: 12, padding: 32, color: "#f44336" }}>
        {error}
      </div>
    );
  if (!agent)
    return <div style={{ color: "#666", paddingTop: 40 }}>Agent not found.</div>;

  return (
    <div>
      <div style={{ marginBottom: 8 }}>
        <Link to="/" style={{ fontSize: 13, color: "#666" }}>← Dashboard</Link>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 20, marginBottom: 28 }}>
        <ScoreRing score={agent.trust_score} />
        <div>
          <h1 style={{ marginBottom: 4 }}>Agent #{agent.id}</h1>
          <span className={`badge badge-${agent.status === "active" ? "active" : "fail"}`}>
            {agent.status}
          </span>
        </div>
      </div>

      <div className="grid" style={{ marginBottom: 24 }}>
        <div className="stat-card">
          <h3>Total Runs</h3>
          <div className="value">{agent.total_runs}</div>
        </div>
        <div className="stat-card">
          <h3>Violations</h3>
          <div className="value" style={{ color: agent.violations > 0 ? "#f44336" : "#4caf50" }}>
            {agent.violations}
          </div>
        </div>
        <div className="stat-card">
          <h3>Active Policy</h3>
          <div style={{ fontSize: 18, fontWeight: 700, color: "#6c63ff", marginTop: 8 }}>
            {policies.find((p) => p.status === "active") ? "Yes" : "None"}
          </div>
        </div>
        <div className="stat-card">
          <h3>Operator ID</h3>
          <div style={{ fontSize: 12, color: "#aaa", marginTop: 8, wordBreak: "break-all", fontFamily: "monospace" }}>
            {agent.operator_id}
          </div>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 13 }}>
          <div>
            <span style={{ color: "#666" }}>Metadata URI: </span>
            <span style={{ color: "#ccc" }}>{agent.metadata_uri}</span>
          </div>
          {agent.active_version && (
            <div>
              <span style={{ color: "#666" }}>Active Version: </span>
              <span style={{ color: "#ccc" }}>{agent.active_version}</span>
            </div>
          )}
          <div>
            <span style={{ color: "#666" }}>Registered: </span>
            <span style={{ color: "#aaa" }}>
              {agent.created_at ? new Date(agent.created_at).toLocaleString() : "—"}
            </span>
          </div>
        </div>
      </div>

      {score?.breakdown && (
        <div className="card" style={{ marginBottom: 16 }}>
          <h3 style={{ marginBottom: 16 }}>Score Breakdown</h3>
          <div style={{ display: "flex", gap: 32, flexWrap: "wrap" }}>
            {[
              { label: "Base", value: `${score.breakdown.base}`, positive: true },
              { label: "Violation Penalty", value: `-${score.breakdown.violation_penalty}`, positive: score.breakdown.violation_penalty === 0 },
              { label: "Claim Penalty", value: `-${score.breakdown.claim_penalty}`, positive: score.breakdown.claim_penalty === 0 },
              { label: "Recency Bonus", value: `+${score.breakdown.recency_bonus}`, positive: true },
            ].map(({ label, value, positive }) => (
              <div key={label} style={{ textAlign: "center" }}>
                <div style={{ fontSize: 12, color: "#666", marginBottom: 4 }}>{label}</div>
                <div style={{ fontSize: 20, fontWeight: 700, color: positive ? "#4caf50" : "#f44336" }}>
                  {value}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Execute Run */}
      <div className="card" style={{ marginBottom: 16 }}>
        <h3 style={{ marginBottom: 12 }}>Execute Run</h3>
        <form onSubmit={handleRun}>
          <div className="form-group">
            <label>User Input</label>
            <textarea
              value={userInput}
              onChange={(e) => setUserInput(e.target.value)}
              rows={3}
              placeholder="What is the current price of ETH?"
              required
            />
          </div>
          <button type="submit" disabled={running || agent.status !== "active"}>
            {running ? "Running..." : "▶ Execute"}
          </button>
          {agent.status !== "active" && (
            <span style={{ marginLeft: 12, fontSize: 13, color: "#888" }}>
              Agent must be active to run
            </span>
          )}
        </form>

        {runError && (
          <div style={{ marginTop: 12, padding: 12, background: "#1a0a0a", borderRadius: 8, color: "#f44336", fontSize: 13 }}>
            {runError}
          </div>
        )}

        {runResult && (
          <div style={{ marginTop: 12 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 8 }}>
              <span
                className={`badge badge-${runResult.policy_verdict === "pass" ? "pass" : "fail"}`}
                style={{ fontSize: 14 }}
              >
                {runResult.policy_verdict}
              </span>
              <Link to={`/runs/${runResult.run_id}`} style={{ fontSize: 13, color: "#6c63ff" }}>
                View run details →
              </Link>
            </div>
            {runResult.reason_codes?.length > 0 && (
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                {runResult.reason_codes.map((code: string, i: number) => (
                  <span key={i} className="badge badge-fail" style={{ fontSize: 12 }}>
                    {code}
                  </span>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Policies */}
      <h2>Policies</h2>
      <div className="card" style={{ marginBottom: 16 }}>
        {policies.length === 0 ? (
          <div style={{ color: "#555", padding: "16px 0" }}>No policies registered.</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Hash</th>
                <th>Status</th>
                <th>Created</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {policies.map((p: any) => (
                <tr key={p.id}>
                  <td>#{p.id}</td>
                  <td style={{ fontFamily: "monospace", fontSize: 12, color: "#aaa" }}>
                    {p.policy_hash?.substring(0, 16)}...
                  </td>
                  <td>
                    <span className={`badge badge-${p.status === "active" ? "active" : "pending"}`}>
                      {p.status}
                    </span>
                  </td>
                  <td style={{ fontSize: 13, color: "#aaa" }}>
                    {p.created_at ? new Date(p.created_at).toLocaleString() : "—"}
                  </td>
                  <td>
                    {p.status !== "active" && (
                      <button
                        onClick={() => handleActivatePolicy(p.id)}
                        style={{
                          padding: "4px 10px",
                          fontSize: 12,
                          background: "transparent",
                          border: "1px solid #6c63ff",
                          color: "#6c63ff",
                        }}
                      >
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
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
        <h2 style={{ marginBottom: 0 }}>Runs</h2>
        <Link to="/runs" style={{ fontSize: 13, color: "#6c63ff" }}>View all →</Link>
      </div>
      <div className="card" style={{ marginBottom: 16 }}>
        {runs.length === 0 ? (
          <div style={{ color: "#555", padding: "16px 0" }}>No runs yet.</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Run ID</th>
                <th>Verdict</th>
                <th>Settlement TX</th>
                <th>Time</th>
              </tr>
            </thead>
            <tbody>
              {runs.slice(0, 20).map((r: any) => (
                <tr key={r.run_id}>
                  <td style={{ fontFamily: "monospace", fontSize: 13 }}>
                    <Link to={`/runs/${r.run_id}`}>{r.run_id.substring(0, 14)}...</Link>
                  </td>
                  <td>
                    <span className={`badge badge-${r.policy_verdict === "pass" ? "pass" : "fail"}`}>
                      {r.policy_verdict}
                    </span>
                  </td>
                  <td style={{ fontFamily: "monospace", fontSize: 12, color: "#aaa" }}>
                    {r.settlement_tx?.substring(0, 14) || "—"}
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

      {/* Claims */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
        <h2 style={{ marginBottom: 0 }}>Claims</h2>
        <Link to="/claims" style={{ fontSize: 13, color: "#6c63ff" }}>Submit claim →</Link>
      </div>
      <div className="card">
        {claims.length === 0 ? (
          <div style={{ color: "#555", padding: "16px 0" }}>No claims filed.</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Reason</th>
                <th>Status</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {claims.map((c: any) => (
                <tr key={c.id}>
                  <td>#{c.id}</td>
                  <td style={{ fontSize: 13 }}>{c.reason_code}</td>
                  <td>
                    <span
                      className={`badge ${
                        c.status === "approved" || c.status === "paid"
                          ? "badge-pass"
                          : c.status === "rejected"
                          ? "badge-fail"
                          : "badge-pending"
                      }`}
                    >
                      {c.status}
                    </span>
                  </td>
                  <td style={{ fontSize: 13, color: "#aaa" }}>
                    {c.created_at ? new Date(c.created_at).toLocaleString() : "—"}
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
