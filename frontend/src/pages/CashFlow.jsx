import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Spinner, Card, SectionTitle } from "@/components/shared";
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import { useEvidence } from "@/components/EvidenceDrawer";

export default function CashFlow() {
  const { open } = useEvidence();
  const [metric, setMetric] = useState("cash_received");
  const { data: trend, isLoading } = useQuery({
    queryKey: ["cf", metric],
    queryFn: async () => (await api.get(`/dashboard/trend?metric=${metric}`)).data,
  });
  const { data: dash } = useQuery({ queryKey: ["dashboard"], queryFn: async () => (await api.get("/dashboard")).data });
  if (isLoading) return <Spinner label="Loading cash flow" />;

  const m = dash?.metrics || {};
  const stat = [
    ["cash_received", "Cash Received"], ["pending_settlements", "Pending"],
    ["gross_revenue", "Gross Revenue"], ["refunds", "Refunds"],
  ];

  return (
    <div className="space-y-6 pl-fade" data-testid="cashflow">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {stat.map(([k, l]) => (
          <button key={k} onClick={() => open(k, l)} className="kpi-hover rounded-sm border bg-card p-4 text-left" data-testid={`cf-kpi-${k}`}>
            <div className="text-[11px] uppercase tracking-widest text-slate-400">{l}</div>
            <div className="tabular mt-1 text-xl font-bold text-slate-900">{m[k]?.current?.value_display || "—"}</div>
          </button>
        ))}
      </div>
      <Card className="p-5">
        <div className="mb-3 flex items-center justify-between">
          <SectionTitle label="Daily flow (30 days)">{metric === "refunds" ? "Refund outflow" : "Payment inflow"}</SectionTitle>
          <div className="flex gap-1">
            {["cash_received", "refunds"].map((t) => (
              <button key={t} onClick={() => setMetric(t)} className={`rounded-sm border px-2 py-1 text-xs ${metric === t ? "border-primary bg-accent text-primary" : "text-slate-500"}`}>
                {t === "cash_received" ? "Payments" : "Refunds"}
              </button>
            ))}
          </div>
        </div>
        <ResponsiveContainer width="100%" height={320}>
          <AreaChart data={trend.series}>
            <defs><linearGradient id="cf" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#1D4ED8" stopOpacity={0.28} /><stop offset="100%" stopColor="#1D4ED8" stopOpacity={0} /></linearGradient></defs>
            <CartesianGrid strokeDasharray="2 4" stroke="#E2E8F0" vertical={false} />
            <XAxis dataKey="date" tick={{ fontSize: 10, fill: "#94A3B8" }} interval={3} tickLine={false} axisLine={false} />
            <YAxis tick={{ fontSize: 10, fill: "#94A3B8" }} tickLine={false} axisLine={false} width={54} tickFormatter={(v) => `₹${(v / 1000).toFixed(0)}k`} />
            <Tooltip formatter={(v) => `₹${v.toLocaleString("en-IN")}`} contentStyle={{ borderRadius: 4, fontSize: 12 }} />
            <Area type="monotone" dataKey="value" stroke="#1D4ED8" strokeWidth={2} fill="url(#cf)" />
          </AreaChart>
        </ResponsiveContainer>
      </Card>
    </div>
  );
}
