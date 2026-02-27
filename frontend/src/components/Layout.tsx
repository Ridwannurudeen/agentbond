import React from "react";
import { Link, useLocation } from "react-router-dom";
import { useWallet } from "../context/WalletContext";

const navItems = [
  { path: "/", label: "Dashboard" },
  { path: "/claims", label: "Claims" },
  { path: "/operator", label: "Operator" },
];

function truncateAddress(addr: string) {
  return `${addr.slice(0, 6)}…${addr.slice(-4)}`;
}

export default function Layout({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  const { address, chainId, isConnecting, connect, disconnect } = useWallet();

  return (
    <div>
      <nav
        style={{
          background: "#111118",
          borderBottom: "1px solid #2a2a3a",
          padding: "0 24px",
          display: "flex",
          alignItems: "center",
          height: 56,
          gap: 32,
        }}
      >
        <Link to="/" style={{ fontWeight: 700, fontSize: 18, color: "#6c63ff" }}>
          AgentBond
        </Link>
        {navItems.map((item) => (
          <Link
            key={item.path}
            to={item.path}
            style={{
              color: location.pathname === item.path ? "#6c63ff" : "#888",
              fontWeight: location.pathname === item.path ? 600 : 400,
              fontSize: 14,
            }}
          >
            {item.label}
          </Link>
        ))}

        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 12 }}>
          {address ? (
            <>
              {chainId && (
                <span style={{ fontSize: 12, color: "#666", fontFamily: "monospace" }}>
                  chain:{chainId}
                </span>
              )}
              <button
                onClick={disconnect}
                style={{
                  background: "transparent",
                  border: "1px solid #2a2a3a",
                  color: "#6c63ff",
                  padding: "6px 14px",
                  borderRadius: 8,
                  fontSize: 13,
                  cursor: "pointer",
                  fontFamily: "monospace",
                }}
              >
                {truncateAddress(address)}
              </button>
            </>
          ) : (
            <button
              onClick={connect}
              disabled={isConnecting}
              style={{
                background: "#6c63ff",
                border: "none",
                color: "#fff",
                padding: "6px 16px",
                borderRadius: 8,
                fontSize: 13,
                cursor: isConnecting ? "wait" : "pointer",
                fontWeight: 600,
              }}
            >
              {isConnecting ? "Connecting…" : "Connect Wallet"}
            </button>
          )}
        </div>
      </nav>
      <main className="container" style={{ paddingTop: 32, paddingBottom: 48 }}>
        {children}
      </main>
    </div>
  );
}
