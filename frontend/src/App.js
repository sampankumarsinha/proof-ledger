import { BrowserRouter, Routes, Route, Navigate, Outlet } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import "@/App.css";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import { EvidenceProvider } from "@/components/EvidenceDrawer";
import Layout from "@/components/Layout";
import { api } from "@/lib/api";
import { Spinner } from "@/components/shared";
import { Toaster } from "@/components/ui/sonner";

import Login from "@/pages/Login";
import Overview from "@/pages/Overview";
import Analyst from "@/pages/Analyst";
import Autopsy from "@/pages/Autopsy";
import CashFlow from "@/pages/CashFlow";
import Payments from "@/pages/Payments";
import Settlements from "@/pages/Settlements";
import Refunds from "@/pages/Refunds";
import Receivables from "@/pages/Receivables";
import Reconciliation from "@/pages/Reconciliation";
import Investigations from "@/pages/Investigations";
import Scenarios from "@/pages/Scenarios";
import Decisions from "@/pages/Decisions";
import Evidence from "@/pages/Evidence";
import Evaluation from "@/pages/Evaluation";
import Audit from "@/pages/Audit";
import DataExplorer from "@/pages/DataExplorer";
import SettingsPage from "@/pages/Settings";

function Shell() {
  const { data } = useQuery({
    queryKey: ["env"],
    queryFn: async () => (await api.get("/integrations/status")).data,
  });
  return (
    <EvidenceProvider>
      <Layout env={data?.mode || "DEMO_DATA"}>
        <Outlet />
      </Layout>
    </EvidenceProvider>
  );
}

function Protected() {
  const { user, loading } = useAuth();
  if (loading) return <div className="flex h-screen items-center justify-center"><Spinner label="Loading ProofLedger" /></div>;
  if (!user) return <Navigate to="/login" replace />;
  return <Shell />;
}

function App() {
  return (
    <div className="App">
      <Toaster position="top-right" />
      <BrowserRouter>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route element={<Protected />}>
              <Route path="/" element={<Overview />} />
              <Route path="/analyst" element={<Analyst />} />
              <Route path="/autopsy" element={<Autopsy />} />
              <Route path="/cashflow" element={<CashFlow />} />
              <Route path="/payments" element={<Payments />} />
              <Route path="/settlements" element={<Settlements />} />
              <Route path="/refunds" element={<Refunds />} />
              <Route path="/receivables" element={<Receivables />} />
              <Route path="/reconciliation" element={<Reconciliation />} />
              <Route path="/investigations" element={<Investigations />} />
              <Route path="/scenarios" element={<Scenarios />} />
              <Route path="/decisions" element={<Decisions />} />
              <Route path="/evidence" element={<Evidence />} />
              <Route path="/evaluation" element={<Evaluation />} />
              <Route path="/audit" element={<Audit />} />
              <Route path="/data" element={<DataExplorer />} />
              <Route path="/settings" element={<SettingsPage />} />
            </Route>
          </Routes>
        </AuthProvider>
      </BrowserRouter>
    </div>
  );
}

export default App;
