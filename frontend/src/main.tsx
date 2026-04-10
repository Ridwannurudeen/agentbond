import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import Landing from "./pages/Landing";
import Dashboard from "./pages/Dashboard";
import AgentDetail from "./pages/AgentDetail";
import RunDetail from "./pages/RunDetail";
import Runs from "./pages/Runs";
import Claims from "./pages/Claims";
import Operator from "./pages/Operator";
import Leaderboard from "./pages/Leaderboard";
import Layout from "./components/Layout";
import { WalletProvider } from "./context/WalletContext";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <WalletProvider>
      <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/dashboard" element={<Layout><Dashboard /></Layout>} />
          <Route path="/agents/:id" element={<Layout><AgentDetail /></Layout>} />
          <Route path="/runs" element={<Layout><Runs /></Layout>} />
          <Route path="/runs/:id" element={<Layout><RunDetail /></Layout>} />
          <Route path="/claims" element={<Layout><Claims /></Layout>} />
          <Route path="/leaderboard" element={<Layout><Leaderboard /></Layout>} />
          <Route path="/operator" element={<Layout><Operator /></Layout>} />
        </Routes>
      </BrowserRouter>
    </WalletProvider>
  </React.StrictMode>
);
