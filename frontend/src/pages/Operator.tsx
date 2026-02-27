import React, { useEffect, useState } from "react";
import { registerAgent, registerPolicy, stakeCollateral, executeRun } from "../api";
import { useWallet } from "../context/WalletContext";

export default function Operator() {
  const { address } = useWallet();

  // Register Agent
  const [wallet, setWallet] = useState("");
  const [metadataUri, setMetadataUri] = useState("");

  // Sync wallet address from MetaMask whenever it changes
  useEffect(() => {
    if (address) setWallet(address);
  }, [address]);
  const [agentResult, setAgentResult] = useState<any>(null);

  // Register Policy
  const [policyAgentId, setPolicyAgentId] = useState("");
  const [policyRules, setPolicyRules] = useState(
    JSON.stringify(
      {
        allowed_tools: ["get_price", "get_portfolio"],
        max_value_per_action: 1000,
        prohibited_targets: [],
        max_actions_per_window: 100,
        window_seconds: 3600,
      },
      null,
      2
    )
  );
  const [policyResult, setPolicyResult] = useState<any>(null);

  // Stake
  const [stakeAgentId, setStakeAgentId] = useState("");
  const [stakeAmount, setStakeAmount] = useState("");
  const [stakeResult, setStakeResult] = useState<any>(null);

  // Execute Run
  const [runAgentId, setRunAgentId] = useState("");
  const [userInput, setUserInput] = useState("");
  const [runResult, setRunResult] = useState<any>(null);

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await registerAgent(wallet, metadataUri);
      setAgentResult(res);
    } catch (err: any) {
      setAgentResult({ error: err.response?.data?.detail || err.message });
    }
  };

  const handlePolicy = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const rules = JSON.parse(policyRules);
      const res = await registerPolicy(parseInt(policyAgentId), rules);
      setPolicyResult(res);
    } catch (err: any) {
      setPolicyResult({ error: err.message });
    }
  };

  const handleStake = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await stakeCollateral(parseInt(stakeAgentId), stakeAmount);
      setStakeResult(res);
    } catch (err: any) {
      setStakeResult({ error: err.response?.data?.detail || err.message });
    }
  };

  const handleRun = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await executeRun(parseInt(runAgentId), userInput);
      setRunResult(res);
    } catch (err: any) {
      setRunResult({ error: err.response?.data?.detail || err.message });
    }
  };

  const ResultBox = ({ result }: { result: any }) => {
    if (!result) return null;
    return (
      <pre
        style={{
          marginTop: 12,
          padding: 12,
          background: "#0d0d15",
          borderRadius: 8,
          fontSize: 13,
          overflow: "auto",
          maxHeight: 200,
        }}
      >
        {JSON.stringify(result, null, 2)}
      </pre>
    );
  };

  return (
    <div>
      <h1>Operator Console</h1>

      <div className="card">
        <h3>Register Agent</h3>
        <form onSubmit={handleRegister}>
          <div className="form-group">
            <label>
              Wallet Address{" "}
              {address && (
                <span style={{ fontSize: 12, color: "#6c63ff", fontWeight: 400 }}>
                  (auto-filled from MetaMask)
                </span>
              )}
            </label>
            <input value={wallet} onChange={(e) => setWallet(e.target.value)} placeholder="0x..." required />
          </div>
          <div className="form-group">
            <label>Metadata URI</label>
            <input value={metadataUri} onChange={(e) => setMetadataUri(e.target.value)} placeholder="ipfs://..." required />
          </div>
          <button type="submit">Register</button>
        </form>
        <ResultBox result={agentResult} />
      </div>

      <div className="card">
        <h3>Register Policy</h3>
        <form onSubmit={handlePolicy}>
          <div className="form-group">
            <label>Agent ID</label>
            <input value={policyAgentId} onChange={(e) => setPolicyAgentId(e.target.value)} placeholder="1" required />
          </div>
          <div className="form-group">
            <label>Policy Rules (JSON)</label>
            <textarea
              value={policyRules}
              onChange={(e) => setPolicyRules(e.target.value)}
              rows={8}
              style={{ fontFamily: "monospace", fontSize: 13 }}
            />
          </div>
          <button type="submit">Register Policy</button>
        </form>
        <ResultBox result={policyResult} />
      </div>

      <div className="card">
        <h3>Stake Collateral</h3>
        <form onSubmit={handleStake}>
          <div className="form-group">
            <label>Agent ID</label>
            <input value={stakeAgentId} onChange={(e) => setStakeAgentId(e.target.value)} placeholder="1" required />
          </div>
          <div className="form-group">
            <label>Amount (wei)</label>
            <input value={stakeAmount} onChange={(e) => setStakeAmount(e.target.value)} placeholder="10000000000000000" required />
          </div>
          <button type="submit">Stake</button>
        </form>
        <ResultBox result={stakeResult} />
      </div>

      <div className="card">
        <h3>Execute Agent Run</h3>
        <form onSubmit={handleRun}>
          <div className="form-group">
            <label>Agent ID</label>
            <input value={runAgentId} onChange={(e) => setRunAgentId(e.target.value)} placeholder="1" required />
          </div>
          <div className="form-group">
            <label>User Input</label>
            <textarea
              value={userInput}
              onChange={(e) => setUserInput(e.target.value)}
              rows={3}
              placeholder="What is the current price of ETH?"
            />
          </div>
          <button type="submit">Execute</button>
        </form>
        <ResultBox result={runResult} />
      </div>
    </div>
  );
}
