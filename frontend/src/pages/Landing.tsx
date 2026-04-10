import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import {
  Shield,
  Lock,
  Cpu,
  Scale,
  Zap,
  ArrowRight,
  CheckCircle2,
  AlertTriangle,
  Eye,
  Coins,
  FileCheck,
  Github,
} from "lucide-react";

const fadeUp = {
  initial: { opacity: 0, y: 20 },
  animate: { opacity: 1, y: 0 },
};

function FeatureCard({
  icon: Icon,
  title,
  description,
  delay,
}: {
  icon: typeof Shield;
  title: string;
  description: string;
  delay: number;
}) {
  return (
    <motion.div
      {...fadeUp}
      transition={{ duration: 0.4, delay }}
      className="glass-card p-6 space-y-3"
    >
      <div className="w-10 h-10 rounded-lg bg-violet-600/15 border border-violet-500/25 flex items-center justify-center">
        <Icon size={18} className="text-violet-400" />
      </div>
      <h3 className="text-base font-semibold text-zinc-100">{title}</h3>
      <p className="text-sm text-zinc-400 leading-relaxed">{description}</p>
    </motion.div>
  );
}

function StepCard({
  number,
  title,
  description,
  delay,
}: {
  number: number;
  title: string;
  description: string;
  delay: number;
}) {
  return (
    <motion.div
      {...fadeUp}
      transition={{ duration: 0.4, delay }}
      className="relative flex gap-4"
    >
      <div className="flex flex-col items-center">
        <div className="w-8 h-8 rounded-full bg-violet-600/20 border border-violet-500/30 flex items-center justify-center text-sm font-bold text-violet-400 flex-shrink-0">
          {number}
        </div>
        {number < 5 && (
          <div className="w-px flex-1 bg-zinc-800 mt-2" />
        )}
      </div>
      <div className="pb-8">
        <h4 className="text-sm font-semibold text-zinc-100 mb-1">{title}</h4>
        <p className="text-sm text-zinc-500 leading-relaxed">{description}</p>
      </div>
    </motion.div>
  );
}

export default function Landing() {
  return (
    <div className="min-h-screen bg-zinc-950">
      {/* Nav */}
      <nav className="fixed top-0 left-0 right-0 z-50 backdrop-blur-xl bg-zinc-950/80 border-b border-zinc-800/60">
        <div className="max-w-5xl mx-auto px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg bg-violet-600/20 border border-violet-500/30 flex items-center justify-center">
              <Shield size={14} className="text-violet-400" />
            </div>
            <span className="font-bold text-sm text-zinc-100">AgentBond</span>
          </div>
          <div className="flex items-center gap-3">
            <a
              href="https://github.com/Ridwannurudeen/agentbond"
              target="_blank"
              rel="noopener noreferrer"
              className="btn-ghost text-xs py-1.5 px-3 no-underline"
            >
              <Github size={14} />
              GitHub
            </a>
            <Link to="/dashboard" className="btn-primary text-xs py-1.5 px-3 no-underline">
              Launch App
              <ArrowRight size={14} />
            </Link>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section className="pt-32 pb-20 px-6">
        <div className="max-w-3xl mx-auto text-center space-y-6">
          <motion.div {...fadeUp} transition={{ duration: 0.4 }}>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-violet-600/10 border border-violet-500/20 text-xs text-violet-400 font-medium mb-4">
              <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 pulse-dot" />
              Live on Base Sepolia
            </div>
          </motion.div>

          <motion.h1
            {...fadeUp}
            transition={{ duration: 0.4, delay: 0.05 }}
            className="text-4xl md:text-5xl font-bold text-zinc-100 leading-tight tracking-tight"
          >
            Verifiable Warranties
            <br />
            <span className="text-violet-400">for AI Agents</span>
          </motion.h1>

          <motion.p
            {...fadeUp}
            transition={{ duration: 0.4, delay: 0.1 }}
            className="text-lg text-zinc-400 max-w-2xl mx-auto leading-relaxed"
          >
            AgentBond is an on-chain accountability layer for AI agents that handle
            real money. Operators stake collateral as a guarantee. Every agent
            execution is verified through OpenGradient TEE attestation. Policy
            violations trigger automatic slashing and user reimbursement.
          </motion.p>

          <motion.div
            {...fadeUp}
            transition={{ duration: 0.4, delay: 0.15 }}
            className="flex items-center justify-center gap-3 pt-2"
          >
            <Link to="/dashboard" className="btn-primary no-underline">
              Launch App
              <ArrowRight size={16} />
            </Link>
            <a
              href="https://github.com/Ridwannurudeen/agentbond"
              target="_blank"
              rel="noopener noreferrer"
              className="btn-ghost no-underline"
            >
              View Source
            </a>
          </motion.div>
        </div>
      </section>

      {/* Problem */}
      <section className="py-16 px-6 border-t border-zinc-800/60">
        <div className="max-w-5xl mx-auto">
          <motion.div
            {...fadeUp}
            transition={{ duration: 0.4 }}
            className="text-center mb-12"
          >
            <h2 className="text-2xl font-bold text-zinc-100 mb-3">The Problem</h2>
            <p className="text-sm text-zinc-400 max-w-xl mx-auto">
              AI agents are making financial decisions, executing trades, and
              managing wallets. But when an agent misbehaves, there is no
              accountability, no insurance, and no recourse for users.
            </p>
          </motion.div>

          <div className="grid md:grid-cols-3 gap-4">
            <FeatureCard
              icon={AlertTriangle}
              title="No Accountability"
              description="An agent can drain a wallet, execute a bad trade, or ignore safety limits with zero consequences for the operator."
              delay={0.05}
            />
            <FeatureCard
              icon={Eye}
              title="No Verifiability"
              description="Users cannot verify what the agent actually did. Logs can be tampered with. There is no cryptographic proof of execution."
              delay={0.1}
            />
            <FeatureCard
              icon={Coins}
              title="No Insurance"
              description="When things go wrong, affected users have no way to recover losses. There is no staked collateral backing the agent's promises."
              delay={0.15}
            />
          </div>
        </div>
      </section>

      {/* How it works */}
      <section className="py-16 px-6 border-t border-zinc-800/60">
        <div className="max-w-5xl mx-auto">
          <motion.div
            {...fadeUp}
            transition={{ duration: 0.4 }}
            className="text-center mb-12"
          >
            <h2 className="text-2xl font-bold text-zinc-100 mb-3">How AgentBond Works</h2>
            <p className="text-sm text-zinc-400 max-w-xl mx-auto">
              A staking-based warranty system with cryptographic proof of every
              agent execution. No trust required.
            </p>
          </motion.div>

          <div className="max-w-lg mx-auto">
            <StepCard
              number={1}
              title="Operator Registers and Stakes Collateral"
              description="The operator deploys their AI agent on-chain through the AgentRegistry contract and deposits ETH into the WarrantyPool as a financial guarantee of good behavior."
              delay={0.05}
            />
            <StepCard
              number={2}
              title="Policies Define the Rules"
              description="A deterministic policy engine defines what the agent is and is not allowed to do. Policies are evidence-hashed so anyone can independently verify them."
              delay={0.1}
            />
            <StepCard
              number={3}
              title="Every Execution is TEE-Attested"
              description="Agent runs execute through OpenGradient's Trusted Execution Environment. The TEE produces a cryptographic attestation proving exactly what the agent did, with no possibility of tampering."
              delay={0.15}
            />
            <StepCard
              number={4}
              title="Policy Engine Evaluates Every Run"
              description="After each execution, the policy engine checks the agent's behavior against its registered rules. Violations are flagged automatically with the specific rule that was broken."
              delay={0.2}
            />
            <StepCard
              number={5}
              title="Automatic Slashing and Reimbursement"
              description="When a violation is confirmed, the ClaimManager contract automatically slashes the operator's staked collateral and reimburses the affected user. No dispute process, no manual review."
              delay={0.25}
            />
          </div>
        </div>
      </section>

      {/* OpenGradient */}
      <section className="py-16 px-6 border-t border-zinc-800/60">
        <div className="max-w-5xl mx-auto">
          <motion.div
            {...fadeUp}
            transition={{ duration: 0.4 }}
            className="text-center mb-12"
          >
            <h2 className="text-2xl font-bold text-zinc-100 mb-3">
              Powered by OpenGradient
            </h2>
            <p className="text-sm text-zinc-400 max-w-xl mx-auto">
              OpenGradient provides the verifiable inference layer that makes
              AgentBond's warranty model possible. Without cryptographic proof
              of execution, there is no way to know what an agent actually did.
            </p>
          </motion.div>

          <div className="grid md:grid-cols-2 gap-4">
            <FeatureCard
              icon={Cpu}
              title="TEE Attestation"
              description="Every agent execution runs inside OpenGradient's Trusted Execution Environment. The hardware produces an attestation certificate that proves the exact inputs, model, and outputs — tamper-proof by design."
              delay={0.05}
            />
            <FeatureCard
              icon={FileCheck}
              title="Verifiable Inference"
              description="The attestation is stored alongside the agent run. Anyone can independently verify that the agent's output was produced by the claimed model with the claimed inputs. No blind trust."
              delay={0.1}
            />
            <FeatureCard
              icon={Lock}
              title="Evidence-Backed Claims"
              description="When a user files a warranty claim, the claim verifier checks the TEE attestation against the policy rules. The cryptographic evidence makes disputes objective, not subjective."
              delay={0.15}
            />
            <FeatureCard
              icon={Scale}
              title="Deterministic Policy Evaluation"
              description="Policy evaluation is pure computation over attested data. Given the same attestation and the same policy rules, any verifier will reach the same conclusion. No ambiguity, no appeals."
              delay={0.2}
            />
          </div>
        </div>
      </section>

      {/* Use cases */}
      <section className="py-16 px-6 border-t border-zinc-800/60">
        <div className="max-w-5xl mx-auto">
          <motion.div
            {...fadeUp}
            transition={{ duration: 0.4 }}
            className="text-center mb-12"
          >
            <h2 className="text-2xl font-bold text-zinc-100 mb-3">Use Cases</h2>
          </motion.div>

          <div className="grid md:grid-cols-3 gap-4">
            <FeatureCard
              icon={Coins}
              title="DeFi Trading Agents"
              description="An agent executes trades on behalf of users. AgentBond guarantees it follows the approved strategy. If it deviates, the operator's collateral covers the user's loss."
              delay={0.05}
            />
            <FeatureCard
              icon={Shield}
              title="Wallet Management Agents"
              description="An agent manages a multi-sig or smart wallet. Policy rules cap transaction sizes, restrict destinations, and enforce time delays. Violations trigger instant slashing."
              delay={0.1}
            />
            <FeatureCard
              icon={Zap}
              title="Autonomous Service Agents"
              description="An agent provides paid services (code review, data analysis, content generation). The warranty guarantees output quality. Users who receive substandard work get reimbursed automatically."
              delay={0.15}
            />
          </div>
        </div>
      </section>

      {/* Architecture */}
      <section className="py-16 px-6 border-t border-zinc-800/60">
        <div className="max-w-5xl mx-auto">
          <motion.div
            {...fadeUp}
            transition={{ duration: 0.4 }}
            className="text-center mb-12"
          >
            <h2 className="text-2xl font-bold text-zinc-100 mb-3">Architecture</h2>
          </motion.div>

          <div className="grid md:grid-cols-2 gap-4">
            <motion.div {...fadeUp} transition={{ duration: 0.4, delay: 0.05 }} className="glass-card p-6 space-y-4">
              <h3 className="text-base font-semibold text-zinc-100">On-Chain (Base Sepolia)</h3>
              <ul className="space-y-2 text-sm text-zinc-400">
                <li className="flex items-start gap-2">
                  <CheckCircle2 size={14} className="text-emerald-400 mt-0.5 flex-shrink-0" />
                  <span><strong className="text-zinc-200">AgentRegistry</strong> — agent registration, versioning, trust scores</span>
                </li>
                <li className="flex items-start gap-2">
                  <CheckCircle2 size={14} className="text-emerald-400 mt-0.5 flex-shrink-0" />
                  <span><strong className="text-zinc-200">WarrantyPool</strong> — collateral staking, slashing, payouts</span>
                </li>
                <li className="flex items-start gap-2">
                  <CheckCircle2 size={14} className="text-emerald-400 mt-0.5 flex-shrink-0" />
                  <span><strong className="text-zinc-200">PolicyRegistry</strong> — on-chain policy storage and activation</span>
                </li>
                <li className="flex items-start gap-2">
                  <CheckCircle2 size={14} className="text-emerald-400 mt-0.5 flex-shrink-0" />
                  <span><strong className="text-zinc-200">ClaimManager</strong> — claim submission, verification, settlement</span>
                </li>
                <li className="flex items-start gap-2">
                  <CheckCircle2 size={14} className="text-emerald-400 mt-0.5 flex-shrink-0" />
                  <span><strong className="text-zinc-200">Heartbeat</strong> — liveness proofs for registered agents</span>
                </li>
              </ul>
            </motion.div>

            <motion.div {...fadeUp} transition={{ duration: 0.4, delay: 0.1 }} className="glass-card p-6 space-y-4">
              <h3 className="text-base font-semibold text-zinc-100">Off-Chain</h3>
              <ul className="space-y-2 text-sm text-zinc-400">
                <li className="flex items-start gap-2">
                  <CheckCircle2 size={14} className="text-violet-400 mt-0.5 flex-shrink-0" />
                  <span><strong className="text-zinc-200">OpenGradient TEE</strong> — verifiable AI inference with attestation</span>
                </li>
                <li className="flex items-start gap-2">
                  <CheckCircle2 size={14} className="text-violet-400 mt-0.5 flex-shrink-0" />
                  <span><strong className="text-zinc-200">Policy Engine</strong> — deterministic rule evaluation (pure Python, evidence-hashed)</span>
                </li>
                <li className="flex items-start gap-2">
                  <CheckCircle2 size={14} className="text-violet-400 mt-0.5 flex-shrink-0" />
                  <span><strong className="text-zinc-200">Claim Verifier</strong> — automatic claim validation against attested runs</span>
                </li>
                <li className="flex items-start gap-2">
                  <CheckCircle2 size={14} className="text-violet-400 mt-0.5 flex-shrink-0" />
                  <span><strong className="text-zinc-200">FastAPI Backend</strong> — orchestration, run history, SSE streaming</span>
                </li>
                <li className="flex items-start gap-2">
                  <CheckCircle2 size={14} className="text-violet-400 mt-0.5 flex-shrink-0" />
                  <span><strong className="text-zinc-200">React Dashboard</strong> — operator console, agent inspection, claim management</span>
                </li>
              </ul>
            </motion.div>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-20 px-6 border-t border-zinc-800/60">
        <motion.div
          {...fadeUp}
          transition={{ duration: 0.4 }}
          className="max-w-2xl mx-auto text-center space-y-6"
        >
          <h2 className="text-2xl font-bold text-zinc-100">Try it now</h2>
          <p className="text-sm text-zinc-400">
            AgentBond is live on Base Sepolia testnet. Connect a wallet, register
            an agent, stake collateral, and run a verified execution in under five
            minutes.
          </p>
          <div className="flex items-center justify-center gap-3">
            <Link to="/dashboard" className="btn-primary no-underline">
              Launch App
              <ArrowRight size={16} />
            </Link>
            <a
              href="https://github.com/Ridwannurudeen/agentbond"
              target="_blank"
              rel="noopener noreferrer"
              className="btn-ghost no-underline"
            >
              <Github size={14} />
              GitHub
            </a>
          </div>
        </motion.div>
      </section>

      {/* Footer */}
      <footer className="py-8 px-6 border-t border-zinc-800/60">
        <div className="max-w-5xl mx-auto flex items-center justify-between text-xs text-zinc-600">
          <div className="flex items-center gap-2">
            <Shield size={12} className="text-violet-500" />
            <span>AgentBond</span>
          </div>
          <span>Built on Base Sepolia with OpenGradient</span>
        </div>
      </footer>
    </div>
  );
}
