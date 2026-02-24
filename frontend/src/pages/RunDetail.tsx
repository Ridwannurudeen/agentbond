import React, { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { fetchRun, replayRun } from "../api";

export default function RunDetail() {
  const { id } = useParams<{ id: string }>();
  const [run, setRun] = useState<any>(null);
  const [replay, setReplay] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [replaying, setReplaying] = useState(false);

  useEffect(() => {
    if (!id) return;
    fetchRun(id)
      .then(setRun)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [id]);

  const handleReplay = async () => {
    if (!id) return;
    setReplaying(true);
    try {
      const result = await replayRun(id);
      setReplay(result);
    } catch (e) {
      console.error(e);
    }
    setReplaying(false);
  };

  if (loading) return <p>Loading...</p>;
  if (!run) return <p>Run not found</p>;

  return (
    <div>
      <h1>Run Detail</h1>

      <div className="card">
        <h3>Run Info</h3>
        <p><strong>Run ID:</strong> <code>{run.run_id}</code></p>
        <p>
          <strong>Agent:</strong>{" "}
          <Link to={`/agents/${run.agent_id}`}>#{run.agent_id}</Link>
        </p>
        <p><strong>User:</strong> {run.user_address || "N/A"}</p>
        <p>
          <strong>Policy Verdict:</strong>{" "}
          <span className={`badge badge-${run.policy_verdict}`}>{run.policy_verdict}</span>
        </p>
        <p><strong>Created:</strong> {run.created_at}</p>
      </div>

      <div className="card">
        <h3>Proof References</h3>
        <p><strong>Input Hash:</strong> <code>{run.input_hash}</code></p>
        <p><strong>Output Hash:</strong> <code>{run.output_hash}</code></p>
        <p><strong>Settlement TX:</strong> <code>{run.settlement_tx || "N/A"}</code></p>
      </div>

      {run.reason_codes && run.reason_codes.length > 0 && (
        <div className="card">
          <h3>Violations</h3>
          {run.reason_codes.map((code: string, i: number) => (
            <span key={i} className="badge badge-fail" style={{ marginRight: 8 }}>
              {code}
            </span>
          ))}
        </div>
      )}

      <div className="card">
        <h3>Transcript</h3>
        <pre
          style={{
            background: "#0d0d15",
            padding: 16,
            borderRadius: 8,
            overflow: "auto",
            maxHeight: 400,
            fontSize: 13,
          }}
        >
          {JSON.stringify(run.transcript, null, 2)}
        </pre>
      </div>

      <div className="card">
        <h3>Independent Replay</h3>
        <p style={{ marginBottom: 12, color: "#888" }}>
          Re-verify this run by re-fetching proof and re-evaluating policy independently.
        </p>
        <button onClick={handleReplay} disabled={replaying}>
          {replaying ? "Replaying..." : "Replay & Verify"}
        </button>

        {replay && (
          <div style={{ marginTop: 16 }}>
            <p><strong>Proof Valid:</strong> {replay.proof_valid ? "Yes" : "No"}</p>
            <p><strong>Input Hash Match:</strong> {replay.input_hash_match ? "Yes" : "No"}</p>
            <p><strong>Output Hash Match:</strong> {replay.output_hash_match ? "Yes" : "No"}</p>
            <p>
              <strong>Re-evaluated Verdict:</strong>{" "}
              <span className={`badge badge-${replay.policy_verdict}`}>
                {replay.policy_verdict}
              </span>
            </p>
            <p><strong>Original Verdict:</strong> {replay.original_verdict}</p>
            {replay.reason_codes?.length > 0 && (
              <p>
                <strong>Violations:</strong>{" "}
                {replay.reason_codes.map((c: string, i: number) => (
                  <span key={i} className="badge badge-fail" style={{ marginRight: 4 }}>
                    {c}
                  </span>
                ))}
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
