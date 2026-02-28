import React, { useEffect, useState } from "react";
import { registerAgent, registerPolicy, stakeCollateral, executeRun } from "../api";
import { useWallet } from "../context/WalletContext";
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
  const { address } = useWallet();

  const [wallet, setWallet] = useState("");
  const [metadataUri, setMetadataUri] = useState("");
  const [agentResult, setAgentResult] = useState<any>(null);

  const [policyAgentId, setPolicyAgentId] = useState("");
  const [policyRules, setPolicyRules] = useState(
    JSON.stringify({ allowed_tools: ["get_price", "get_portfolio"], max_value_per_action: 1000, prohibited_targets: [], max_actions_per_window: 100, window_seconds: 3600 }, null, 2)
  );
  const [policyResult, setPolicyResult] = useState<any>(null);

  const [stakeAgentId, setStakeAgentId] = useState("");
  const [stakeAmount, setStakeAmount] = useState("");
  const [stakeResult, setStakeResult] = useState<any>(null);

  const [runAgentId, setRunAgentId] = useState("");
  const [userInput, setUserInput] = useState("");
  const [runResult, setRunResult] = useState<any>(null);

  useEffect(() => { if (address) setWallet(address); }, [address]);

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    try { setAgentResult(await registerAgent(wallet, metadataUri)); }
    catch (err: any) { setAgentResult({ error: err.response?.data?.detail || err.message }); }
  };

  const handlePolicy = async (e: React.FormEvent) => {
    e.preventDefault();
    try { setPolicyResult(await registerPolicy(parseInt(policyAgentId), JSON.parse(policyRules))); }
    catch (err: any) { setPolicyResult({ error: err.message }); }
  };

  const handleStake = async (e: React.FormEvent) => {
    e.preventDefault();
    try { setStakeResult(await stakeCollateral(parseInt(stakeAgentId), stakeAmount)); }
    catch (err: any) { setStakeResult({ error: err.response?.data?.detail || err.message }); }
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
                {address && <span className="text-violet-500 font-normal normal-case tracking-normal">· auto-filled</span>}
              </label>
              <input className="form-input font-mono" value={wallet} onChange={(e) => setWallet(e.target.value)} placeholder="0x..." required />
            </div>
            <div>
              <label className="form-label">Metadata URI</label>
              <input className="form-input" value={metadataUri} onChange={(e) => setMetadataUri(e.target.value)} placeholder="ipfs://..." required />
            </div>
            <button type="submit" className="btn-primary">Register</button>
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
            <button type="submit" className="btn-primary">Register Policy</button>
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
            <button type="submit" className="btn-primary">Stake</button>
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
