import React, { useEffect, useState } from "react";
import { registerAgent, generateApiKey, registerPolicy, stakeCollateral, executeRun, fetchAgent } from "../api";
import { useWallet } from "../context/WalletContext";
import { getAgentRegistry, getWarrantyPool, getPolicyRegistry } from "../contracts";
import { sha256, toUtf8Bytes } from "ethers";
import { Bot, ShieldCheck, Coins, Play, CheckCircle2, XCircle } from "lucide-react";
import { motion } from "framer-motion";

function ResultBox({ result }: { result: any }) {
  if (!result) return null;
  const isError = !!result.error;
  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      className={`mt-4 rounded-lg border text-xs overflow-auto max-h-48 ${
        isError
          ? "bg-red-950/30 border-red-900/50 text-red-400"
          : "bg-zinc-900/80 border-zinc-700 text-zinc-300"
      }`}
    >
      {isError && (
        <div className="flex items-center gap-2 px-4 py-2 border-b border-red-900/40 text-red-400">
          <XCircle size={12} /> Error
        </div>
      )}
      {!isError && (
        <div className="flex items-center gap-2 px-4 py-2 border-b border-zinc-700/50 text-emerald-400">
          <CheckCircle2 size={12} /> Success
        </div>
      )}
      <pre className="p-4 font-mono leading-relaxed">{JSON.stringify(result, null, 2)}</pre>
    </motion.div>
  );
}

function Section({
  icon: Icon,
  title,
  children,
  delay = 0,
}: {
  icon: React.ElementType;
  title: string;
  children: React.ReactNode;
  delay?: number;
}) {
  return (
    <motion.div
      className="glass-card p-6"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.2 }}
    >
      <div className="flex items-center gap-2.5 mb-5">
        <div className="w-7 h-7 rounded-lg bg-violet-950/60 flex items-center justify-center">
          <Icon size={14} className="text-violet-400" />
        </div>
        <h3 className="text-sm font-semibold text-zinc-100">{title}</h3>
      </div>
      {children}
    </motion.div>
  );
}

export default function Operator() {
  const { address, signer } = useWallet();

  const [metadataUri, setMetadataUri] = useState("");
  const [agentResult, setAgentResult] = useState<any>(null);
  const [agentLoading, setAgentLoading] = useState(false);

  // Stored API key after registration
  const [apiKey, setApiKey] = useState<string | null>(null);

  const [policyAgentId, setPolicyAgentId] = useState("");
  const [policyRules, setPolicyRules] = useState(
    JSON.stringify({ allowed_tools: ["get_price", "get_portfolio"], max_value_per_action: 1000, prohibited_targets: [], max_actions_per_window: 100, window_seconds: 3600 }, null, 2)
  );
  const [policyResult, setPolicyResult] = useState<any>(null);
  const [policyLoading, setPolicyLoading] = useState(false);

  const [stakeAgentId, setStakeAgentId] = useState("");
  const [stakeAmount, setStakeAmount] = useState("");
  const [stakeResult, setStakeResult] = useState<any>(null);
  const [stakeLoading, setStakeLoading] = useState(false);

  const [runAgentId, setRunAgentId] = useState("");
  const [userInput, setUserInput] = useState("");
  const [runResult, setRunResult] = useState<any>(null);

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!address || !signer) {
      setAgentResult({ error: "Connect your wallet first." });
      return;
    }
    setAgentLoading(true);
    setAgentResult(null);
    try {
      // Step 1: Sign ownership message
      const ts = Date.now();
      const message = `Register AgentBond operator\nWallet: ${address}\nTimestamp: ${ts}`;
      const signature = await signer.signMessage(message);

      // Step 2: Call AgentRegistry.registerAgent on-chain
      const agentRegistry = getAgentRegistry(signer);
      const tx = await agentRegistry.registerAgent(metadataUri);
      const receipt = await tx.wait();

      // Step 3: Extract chain_agent_id from AgentRegistered event
      let chainAgentId: string | undefined;
      for (const log of receipt.logs) {
        try {
          const parsed = agentRegistry.interface.parseLog(log);
          if (parsed?.name === "AgentRegistered") {
            chainAgentId = parsed.args.agentId.toString();
            break;
          }
        } catch { /* not this event */ }
      }

      // Step 4: POST to backend
      const result = await registerAgent(address, metadataUri, {
        signature,
        message,
        chain_agent_id: chainAgentId,
        chain_tx: receipt.hash,
      });

      // Step 5: Fetch API key for subsequent protected calls
      try {
        const keyData = await generateApiKey(address);
        setApiKey(keyData.api_key);
        setAgentResult({ ...result, api_key: keyData.api_key, chain_tx: receipt.hash });
      } catch {
        setAgentResult({ ...result, chain_tx: receipt.hash });
      }
    } catch (err: any) {
      setAgentResult({ error: err.response?.data?.detail || err.message });
    } finally {
      setAgentLoading(false);
    }
  };

  const handlePolicy = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!signer) {
      setPolicyResult({ error: "Connect your wallet first." });
      return;
    }
    setPolicyLoading(true);
    setPolicyResult(null);
    try {
      const agentDbId = parseInt(policyAgentId);
      const rules = JSON.parse(policyRules);

      // Fetch agent to get chain_agent_id
      const agent = await fetchAgent(agentDbId);
      if (!agent.chain_agent_id) {
        setPolicyResult({ error: "Agent has no on-chain ID. Register agent on-chain first." });
        return;
      }

      // Compute policyHash (bytes32) and rulesURI
      const rulesStr = JSON.stringify(rules);
      const policyHashBytes32 = sha256(toUtf8Bytes(rulesStr));
      const rulesUri = `data:application/json,${rulesStr}`;

      // Call PolicyRegistry.registerPolicy on-chain
      const policyRegistry = getPolicyRegistry(signer);
      const tx = await policyRegistry.registerPolicy(agent.chain_agent_id, policyHashBytes32, rulesUri);
      const receipt = await tx.wait();

      // Extract chain_policy_id from PolicyRegistered event
      let chainPolicyId: string | undefined;
      for (const log of receipt.logs) {
        try {
          const parsed = policyRegistry.interface.parseLog(log);
          if (parsed?.name === "PolicyRegistered") {
            chainPolicyId = parsed.args.policyId.toString();
            break;
          }
        } catch { /* not this event */ }
      }

      // POST to backend
      const result = await registerPolicy(
        agentDbId,
        rules,
        { chain_policy_id: chainPolicyId, chain_tx: receipt.hash },
        apiKey || undefined
      );
      setPolicyResult({ ...result, chain_tx: receipt.hash });
    } catch (err: any) {
      setPolicyResult({ error: err.response?.data?.detail || err.message });
    } finally {
      setPolicyLoading(false);
    }
  };

  const handleStake = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!signer) {
      setStakeResult({ error: "Connect your wallet first." });
      return;
    }
    setStakeLoading(true);
    setStakeResult(null);
    try {
      const agentDbId = parseInt(stakeAgentId);
      const amountWei = BigInt(stakeAmount);

      // Fetch agent to get chain_agent_id
      const agent = await fetchAgent(agentDbId);
      if (!agent.chain_agent_id) {
        setStakeResult({ error: "Agent has no on-chain ID. Register agent on-chain first." });
        return;
      }

      // Call WarrantyPool.stake on-chain
      const warrantyPool = getWarrantyPool(signer);
      const tx = await warrantyPool.stake(agent.chain_agent_id, { value: amountWei });
      const receipt = await tx.wait();

      // POST to backend to record the event
      const result = await stakeCollateral(agentDbId, stakeAmount, receipt.hash, apiKey || undefined);
      setStakeResult({ ...result, chain_tx: receipt.hash });
    } catch (err: any) {
      setStakeResult({ error: err.response?.data?.detail || err.message });
    } finally {
      setStakeLoading(false);
    }
  };

  const handleRun = async (e: React.FormEvent) => {
    e.preventDefault();
    try { setRunResult(await executeRun(parseInt(runAgentId), userInput)); }
    catch (err: any) { setRunResult({ error: err.response?.data?.detail || err.message }); }
  };

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-zinc-100">Operator Console</h1>
        <p className="text-sm text-zinc-600 mt-0.5">Register agents, configure policies, and execute runs</p>
      </div>

      <div className="grid grid-cols-2 gap-5">
        {/* Register Agent */}
        <Section icon={Bot} title="Register Agent" delay={0}>
          <form onSubmit={handleRegister} className="space-y-4">
            <div>
              <label className="form-label flex items-center gap-1.5">
                Wallet Address
                {address && <span className="text-violet-500 font-normal normal-case tracking-normal">· auto-filled from MetaMask</span>}
              </label>
              <input className="form-input font-mono" value={address || ""} readOnly placeholder="Connect wallet to fill" />
            </div>
            <div>
              <label className="form-label">Metadata URI</label>
              <input className="form-input" value={metadataUri} onChange={(e) => setMetadataUri(e.target.value)} placeholder="ipfs://..." required />
            </div>
            <button type="submit" className="btn-primary" disabled={agentLoading || !signer}>
              {agentLoading ? "Signing & Registering…" : "Register (MetaMask)"}
            </button>
          </form>
          <ResultBox result={agentResult} />
        </Section>

        {/* Register Policy */}
        <Section icon={ShieldCheck} title="Register Policy" delay={0.05}>
          <form onSubmit={handlePolicy} className="space-y-4">
            <div>
              <label className="form-label">Agent ID</label>
              <input className="form-input" value={policyAgentId} onChange={(e) => setPolicyAgentId(e.target.value)} placeholder="1" required />
            </div>
            <div>
              <label className="form-label">Policy Rules (JSON)</label>
              <textarea
                className="form-input font-mono text-xs leading-relaxed"
                value={policyRules}
                onChange={(e) => setPolicyRules(e.target.value)}
                rows={7}
              />
            </div>
            <button type="submit" className="btn-primary" disabled={policyLoading || !signer}>
              {policyLoading ? "Registering…" : "Register Policy (MetaMask)"}
            </button>
          </form>
          <ResultBox result={policyResult} />
        </Section>

        {/* Stake Collateral */}
        <Section icon={Coins} title="Stake Collateral" delay={0.1}>
          <form onSubmit={handleStake} className="space-y-4">
            <div>
              <label className="form-label">Agent ID</label>
              <input className="form-input" value={stakeAgentId} onChange={(e) => setStakeAgentId(e.target.value)} placeholder="1" required />
            </div>
            <div>
              <label className="form-label">Amount (wei)</label>
              <input className="form-input font-mono" value={stakeAmount} onChange={(e) => setStakeAmount(e.target.value)} placeholder="10000000000000000" required />
            </div>
            <button type="submit" className="btn-primary" disabled={stakeLoading || !signer}>
              {stakeLoading ? "Staking…" : "Stake (MetaMask)"}
            </button>
          </form>
          <ResultBox result={stakeResult} />
        </Section>

        {/* Execute Run */}
        <Section icon={Play} title="Execute Agent Run" delay={0.15}>
          <form onSubmit={handleRun} className="space-y-4">
            <div>
              <label className="form-label">Agent ID</label>
              <input className="form-input" value={runAgentId} onChange={(e) => setRunAgentId(e.target.value)} placeholder="1" required />
            </div>
            <div>
              <label className="form-label">User Input</label>
              <textarea
                className="form-input"
                value={userInput}
                onChange={(e) => setUserInput(e.target.value)}
                rows={4}
                placeholder="What is the current price of ETH?"
              />
            </div>
            <button type="submit" className="btn-primary">
              <Play size={13} /> Execute
            </button>
          </form>
          <ResultBox result={runResult} />
        </Section>
      </div>
    </div>
  );
}
