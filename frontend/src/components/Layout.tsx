import React from "react";
import { Link, useLocation } from "react-router-dom";

const navItems = [
  { path: "/", label: "Dashboard" },
  { path: "/claims", label: "Claims" },
  { path: "/operator", label: "Operator" },
];

export default function Layout({ children }: { children: React.ReactNode }) {
  const location = useLocation();

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
      </nav>
      <main className="container" style={{ paddingTop: 32, paddingBottom: 48 }}>
        {children}
      </main>
    </div>
  );
}
