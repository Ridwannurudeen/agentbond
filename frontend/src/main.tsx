import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import AgentDetail from "./pages/AgentDetail";
import RunDetail from "./pages/RunDetail";
import Claims from "./pages/Claims";
import Operator from "./pages/Operator";
import Layout from "./components/Layout";
import { WalletProvider } from "./context/WalletContext";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <WalletProvider>
      <BrowserRouter>
        <Layout>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/agents/:id" element={<AgentDetail />} />
            <Route path="/runs/:id" element={<RunDetail />} />
            <Route path="/claims" element={<Claims />} />
            <Route path="/operator" element={<Operator />} />
          </Routes>
        </Layout>
      </BrowserRouter>
    </WalletProvider>
  </React.StrictMode>
);
