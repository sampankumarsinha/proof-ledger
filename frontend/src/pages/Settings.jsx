import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, apiError } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Spinner, Card, SectionTitle } from "@/components/shared";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { Database, Sparkles, Upload, RefreshCw, PlugZap, ToggleLeft, CheckCircle2, XCircle } from "lucide-react";

export default function Settings() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const canWrite = ["OWNER", "ADMIN", "ANALYST"].includes(user?.role);
  const [file, setFile] = useState(null);
  const [summary, setSummary] = useState(null);
  const [busy, setBusy] = useState("");

  const { data: integ, isLoading, refetch } = useQuery({ queryKey: ["integ"], queryFn: async () => (await api.get("/integrations/status")).data });
  const { data: history, refetch: refetchHist } = useQuery({ queryKey: ["rzp-history"], queryFn: async () => (await api.get("/integrations/razorpay/history")).data });

  const refreshAll = () => { refetch(); refetchHist(); qc.invalidateQueries({ queryKey: ["env"] }); qc.invalidateQueries({ queryKey: ["dashboard"] }); };

  const act = async (fn, key) => {
    setBusy(key);
    try { await fn(); } catch (e) { toast.error(apiError(e.response?.data?.detail)); } finally { setBusy(""); }
  };
  const testConn = () => act(async () => { const { data } = await api.post("/integrations/razorpay/test"); data.connected ? toast.success(data.detail) : toast.error(data.detail); }, "test");
  const sync = (incremental) => act(async () => {
    const { data } = await api.post(`/integrations/razorpay/sync?incremental=${incremental}`);
    toast.success(`Synced: ${data.counts.orders} orders, ${data.counts.payments} payments, ${data.counts.settlements} settlements`);
    refreshAll();
  }, incremental ? "inc" : "init");
  const switchSource = (source) => act(async () => { await api.post("/integrations/source", { source }); toast.success(`Data source: ${source}`); refreshAll(); }, "switch");

  const upload = async () => {
    if (!file) return toast.error("Choose a CSV file first");
    const fd = new FormData(); fd.append("file", file);
    try {
      const { data } = await api.post("/imports/csv?entity=payments", fd, { headers: { "Content-Type": "multipart/form-data" } });
      setSummary(data); toast.success(`Imported ${data.records_imported} records`);
    } catch (e) { toast.error(apiError(e.response?.data?.detail)); }
  };

  if (isLoading) return <Spinner />;
  const active = integ.active_source;

  return (
    <div className="space-y-6 pl-fade" data-testid="settings">
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card className="p-5">
          <SectionTitle label="Account" />
          <div className="space-y-2 text-sm">
            <Row k="Name" v={user?.name} /><Row k="Email" v={user?.email} /><Row k="Role" v={user?.role} />
            <Row k="Organization" v="Meridian Commerce Pvt Ltd" />
          </div>
        </Card>

        <Card className="p-5">
          <SectionTitle label="Active data source" right={
            <span className={`rounded-sm border px-2 py-1 text-[11px] font-semibold uppercase ${active === "RAZORPAY_TEST" ? "border-sky-300 bg-sky-50 text-sky-700" : "border-amber-300 bg-amber-50 text-amber-700"}`}>{active === "RAZORPAY_TEST" ? "Razorpay Test" : "Demo Data"}</span>
          } />
          <p className="text-sm text-slate-500">All engines operate on the active source. Switching is instant and never mixes datasets.</p>
          <div className="mt-3 flex gap-2">
            <Button variant={active === "DEMO" ? "default" : "outline"} size="sm" disabled={!canWrite || busy === "switch"}
              onClick={() => switchSource("DEMO")} data-testid="source-demo"
              className={`rounded-sm ${active === "DEMO" ? "bg-primary text-white" : ""}`}><ToggleLeft className="mr-1 h-4 w-4" /> Demo Data</Button>
            <Button variant={active === "RAZORPAY_TEST" ? "default" : "outline"} size="sm"
              disabled={!canWrite || busy === "switch" || !integ.credentials_present}
              title={integ.credentials_present ? "" : "Add Razorpay credentials to backend/.env"}
              onClick={() => switchSource("RAZORPAY_TEST")} data-testid="source-razorpay"
              className={`rounded-sm ${active === "RAZORPAY_TEST" ? "bg-primary text-white" : ""}`}>Razorpay Test</Button>
          </div>
        </Card>
      </div>

      <Card className="p-5">
        <SectionTitle label="Razorpay integration" right={
          <span className={`flex items-center gap-1 text-xs ${integ.connected ? "text-fact" : "text-slate-400"}`}>
            {integ.connected ? <CheckCircle2 className="h-4 w-4" /> : <XCircle className="h-4 w-4" />}
            {integ.connected ? "Connected" : (integ.credentials_present ? "Credentials present" : "No credentials")}
          </span>
        }>Sync test-mode data</SectionTitle>
        <p className="text-sm text-slate-500">{integ.detail}</p>
        <div className="mt-4 flex flex-wrap gap-2">
          <Button onClick={testConn} disabled={!canWrite || busy === "test"} variant="outline" size="sm" className="rounded-sm" data-testid="rzp-test">
            <PlugZap className="mr-1 h-4 w-4" /> {busy === "test" ? "Testing…" : "Test connection"}
          </Button>
          <Button onClick={() => sync(false)} disabled={!canWrite || !integ.credentials_present || busy === "init"} size="sm" className="rounded-sm bg-primary text-white" data-testid="rzp-sync">
            <RefreshCw className="mr-1 h-4 w-4" /> {busy === "init" ? "Syncing…" : "Sync now (initial)"}
          </Button>
          <Button onClick={() => sync(true)} disabled={!canWrite || !integ.credentials_present || busy === "inc"} size="sm" variant="outline" className="rounded-sm" data-testid="rzp-sync-inc">
            {busy === "inc" ? "Syncing…" : "Incremental sync"}
          </Button>
        </div>
        {!integ.credentials_present && (
          <div className="mt-3 rounded-sm border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-700">
            Add <code>RAZORPAY_KEY_ID</code> and <code>RAZORPAY_KEY_SECRET</code> to <code>backend/.env</code> (server-side only), then Test &amp; Sync.
          </div>
        )}

        <div className="mt-5">
          <div className="mb-2 text-[11px] uppercase tracking-widest text-slate-400">Sync history</div>
          <div className="divide-y rounded-sm border" data-testid="sync-history">
            {(history?.runs || []).map((r) => (
              <div key={r.id} className="flex items-center justify-between px-3 py-2 text-sm">
                <span className="text-slate-600">{new Date(r.started_at).toLocaleString()} · {r.type}</span>
                <span className="tabular text-xs text-slate-500">O:{r.counts.orders} P:{r.counts.payments} R:{r.counts.refunds} S:{r.counts.settlements}</span>
                <span className={`text-[11px] font-semibold ${r.status.includes("error") ? "text-inference" : r.status === "skipped" ? "text-slate-400" : "text-fact"}`}>{r.status}</span>
              </div>
            ))}
            {(!history?.runs || history.runs.length === 0) && <div className="px-3 py-6 text-center text-xs text-slate-400">No syncs yet.</div>}
          </div>
        </div>
      </Card>

      <Card className="p-5">
        <SectionTitle label="AI explainer" />
        <div className="flex items-start gap-3 rounded-sm border p-3">
          <Sparkles className="mt-0.5 h-5 w-5 text-primary" />
          <div className="text-xs text-slate-500">Numbers are always deterministic. The LLM only explains verified facts when an OpenAI key is configured server-side (<code>OPENAI_API_KEY</code>). It never calculates financial values.</div>
        </div>
      </Card>

      <Card className="p-5">
        <SectionTitle label="Data import" right={<span className="text-xs text-slate-400">CSV columns: external_id, amount, status</span>}>Import payments (CSV → Demo source)</SectionTitle>
        <div className="flex items-center gap-3">
          <input type="file" accept=".csv" onChange={(e) => setFile(e.target.files[0])} data-testid="csv-file" className="text-sm" />
          <Button onClick={upload} disabled={!canWrite} className="rounded-sm bg-primary text-white" data-testid="csv-upload"><Upload className="mr-1 h-4 w-4" /> Upload</Button>
        </div>
        {summary && (
          <div className="mt-4 grid grid-cols-4 gap-3 text-center">
            {[["Imported", summary.records_imported], ["Rejected", summary.records_rejected], ["Duplicates", summary.duplicates], ["Warnings", summary.warnings.length]].map(([l, v]) => (
              <div key={l} className="rounded-sm border p-3"><div className="text-[11px] uppercase text-slate-400">{l}</div><div className="tabular mt-1 text-xl font-bold">{v}</div></div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}

function Row({ k, v }) {
  return <div className="flex justify-between border-b py-1.5"><span className="text-slate-400">{k}</span><span className="font-medium text-slate-800">{v}</span></div>;
}
