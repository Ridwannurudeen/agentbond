import React from "react";
import { Link, useLocation } from "react-router-dom";
import { useWallet } from "../context/WalletContext";
import {
  Shield,
  LayoutDashboard,
  Activity,
  FileWarning,
  Settings,
  Wallet,
  LogOut,
  Zap,
} from "lucide-react";
import { motion } from "framer-motion";

const navItems = [
  { path: "/", label: "Dashboard", icon: LayoutDashboard, exact: true },
  { path: "/runs", label: "Runs", icon: Activity, exact: false },
  { path: "/claims", label: "Claims", icon: FileWarning, exact: false },
  { path: "/operator", label: "Operator", icon: Settings, exact: false },
];

function truncateAddress(addr: string) {
  return `${addr.slice(0, 6)}…${addr.slice(-4)}`;
}

export default function Layout({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  const { address, chainId, isConnecting, connect, disconnect } = useWallet();

  const isActive = (path: string, exact: boolean) =>
    exact ? location.pathname === path : location.pathname.startsWith(path);

  return (
    <div className="flex min-h-screen bg-zinc-950">
      {/* Sidebar */}
      <aside className="fixed left-0 top-0 h-screen w-[220px] flex flex-col bg-zinc-900/40 border-r border-zinc-800/60 z-50 backdrop-blur-xl">
        {/* Logo */}
        <div className="px-5 py-5 border-b border-zinc-800/60">
          <Link to="/" className="no-underline">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-violet-600/20 border border-violet-500/30 flex items-center justify-center flex-shrink-0">
                <Shield size={16} className="text-violet-400" />
              </div>
              <div>
                <div className="font-bold text-sm text-zinc-100 leading-none">AgentBond</div>
                <div className="text-[10px] text-zinc-600 mt-0.5 leading-none">Warranty Network</div>
              </div>
            </div>
          </Link>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 py-4 space-y-0.5">
          {navItems.map((item) => {
            const active = isActive(item.path, item.exact);
            return (
              <Link key={item.path} to={item.path} className="no-underline block">
                <div
                  className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-all duration-150 ${
                    active
                      ? "bg-violet-500/10 text-violet-400 border border-violet-500/20"
                      : "text-zinc-500 hover:text-zinc-200 hover:bg-zinc-800/60 border border-transparent"
                  }`}
                >
                  <item.icon size={16} />
                  {item.label}
                  {active && (
                    <div className="ml-auto w-1.5 h-1.5 rounded-full bg-violet-500" />
                  )}
                </div>
              </Link>
            );
          })}
        </nav>

        {/* Network badge */}
        {chainId && (
          <div className="px-4 py-2">
            <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-md bg-zinc-800/60 border border-zinc-700/50">
              <Zap size={10} className="text-amber-400" />
              <span className="text-[10px] text-zinc-500 font-mono">chain:{chainId}</span>
            </div>
          </div>
        )}

        {/* Wallet */}
        <div className="px-3 py-4 border-t border-zinc-800/60">
          {address ? (
            <div className="space-y-2">
              <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-zinc-800/60 border border-zinc-700/50">
                <Wallet size={13} className="text-zinc-500 flex-shrink-0" />
                <span className="text-xs text-zinc-300 font-mono truncate flex-1">
                  {truncateAddress(address)}
                </span>
              </div>
              <button
                onClick={disconnect}
                className="w-full flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs text-zinc-600 hover:text-red-400 hover:bg-red-950/30 transition-colors cursor-pointer bg-transparent border-0"
              >
                <LogOut size={12} />
                Disconnect
              </button>
            </div>
          ) : (
            <button
              onClick={connect}
              disabled={isConnecting}
              className="btn-primary w-full justify-center text-xs py-2"
            >
              <Wallet size={13} />
              {isConnecting ? "Connecting…" : "Connect Wallet"}
            </button>
          )}
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 ml-[220px] min-h-screen">
        <div className="max-w-[1200px] mx-auto px-8 py-8">
          <motion.div
            key={location.pathname}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.18 }}
          >
            {children}
          </motion.div>
        </div>
      </main>
    </div>
  );
}
