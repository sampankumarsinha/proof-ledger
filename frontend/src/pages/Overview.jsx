import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useEvidence } from "@/components/EvidenceDrawer";
import { Spinner, SectionTitle, Card } from "@/components/shared";
import { pctStr } from "@/lib/format";
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import { ArrowUpRight, ArrowDownRight, AlertTriangle, Activity, ChevronRight } from "lucide-react";

const KPIS = [
  { key: "gross_revenue", label: "Gross Revenue", cmp: true },
  { key: "net_revenue", label: "Net Revenue", cmp: true },
  { key: "cash_received", label: "Cash Received", cmp: true, invert: false, headline: true },
  { key: "pending_settlements", label: "Pending Settlements", cmp: false },
  { key: "refunds", label: "Refunds", cmp: true, invert: true },
  { key: "refund_rate", label: "Refund Rate", cmp: true, invert: true, pct: true },
  { key: "receivables_outstanding", label: "Receivables", cmp: false },
  { key: "overdue_receivables", label: "Overdue", cmp: false },
  { key: "unreconciled_amount", label: "Unreconciled", cmp: false },
  { key: "successful_payments", label: "Successful Pmts", cmp: true, count: true },
  { key: "failed_payments", label: "Failed Pmts", cmp: true, count: true, invert: true },
  { key: "average_payment_value", label: "Avg Payment", cmp: true },
];

function Kpi({ cfg, metric, onClick }) {
  if (!metric) return null;
  const cur = metric.current;
  const value = cfg.count ? cur.value_display : cfg.pct ? cur.value_display : cur.value_display;
  const change = cfg.cmp ? metric.change_pct : null;
  const good = change == null ? null : cfg.invert ? change < 0 : change > 0;
  const Arrow = change > 0 ? ArrowUpRight : ArrowDownRight;
  return (
    <button
      onClick={onClick}
      data-testid={`kpi-${cfg.key}`}
      title={cur.formula}
      className={`kpi-hover group relative flex flex-col items-start rounded-sm border bg-card p-4 text-left ${cfg.headline ? "ring-1 ring-primary/30" : ""}`}
    >
      <div className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-400">{cfg.label}</div>
      <div className="tabular mt-2 w-full truncate text-base font-semibold leading-tight text-slate-900 sm:text-lg lg:text-xl">{value}</div>
      <div className="mt-1 flex h-4 items-center gap-1">
        {change != null && (
          <span className={`flex items-center gap-0.5 text-xs font-medium ${good ? "text-fact" : "text-alert"}`}>
            <Arrow className="h-3 w-3" /> {pctStr(change)}
          </span>
        )}
      </div>
      <ChevronRight className="absolute right-3 top-3 h-3.5 w-3.5 text-slate-300 opacity-0 transition-opacity group-hover:opacity-100" />
    </button>
  );
}

export default function Overview() {
  const { open } = useEvidence();
  const [trendMetric, setTrendMetric] = useState("cash_received");

  const { data, isLoading } = useQuery({ queryKey: ["dashboard"], queryFn: async () => (await api.get("/dashboard")).data });
  const { data: trend } = useQuery({
    queryKey: ["trend", trendMetric],
    queryFn: async () => (await api.get(`/dashboard/trend?metric=${trendMetric}`)).data,
  });
  const { data: baselines } = useQuery({ queryKey: ["baselines"], queryFn: async () => (await api.get("/analytics/baselines")).data });
  const { data: attn } = useQuery({ queryKey: ["attention"], queryFn: async () => (await api.get("/analytics/attention")).data });

  if (isLoading) return <Spinner label="Building control tower" />;
  const m = data.metrics;

  return (
    <div className="space-y-8 pl-fade" data-testid="control-tower">
      {/* health + summary */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="text-[11px] uppercase tracking-[0.15em] text-slate-400">Control Tower · {data.period.label}</div>
          <h2 className="font-display text-3xl tracking-tight text-slate-900">
            Cash received {m.cash_received.current.value_display}
            <span className={`ml-3 text-lg ${m.cash_received.change_pct < 0 ? "text-alert" : "text-fact"}`}>
              {pctStr(m.cash_received.change_pct)}
            </span>
          </h2>
          <p className="mt-1 text-sm text-slate-500">Compared with the prior 30-day period. Click any metric to trace its evidence.</p>
        </div>
        <Card className="flex items-center gap-4 px-5 py-4">
          <Activity className="h-8 w-8 text-primary" />
          <div>
            <div className="text-[11px] uppercase tracking-widest text-slate-400">Financial Health</div>
            <div className="tabular text-2xl font-bold text-slate-900">{data.health_score}<span className="text-sm text-slate-400">/100</span></div>
          </div>
        </Card>
      </div>

      {/* KPI grid */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6">
        {KPIS.map((cfg) => (
          <Kpi key={cfg.key} cfg={cfg} metric={m[cfg.key]} onClick={() => open(cfg.key, cfg.label)} />
        ))}
      </div>

      {/* Anomaly baselines */}
      {baselines && (
        <Card className="p-5" data-testid="baselines">
          <SectionTitle label="Anomaly baselines" right={<span className="text-xs text-slate-400">vs prior period · transparent thresholds</span>} />
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            {baselines.baselines.map((b) => (
              <div key={b.metric} className="rounded-sm border p-3">
                <div className="text-[11px] uppercase tracking-widest text-slate-400">{b.metric}</div>
                <div className="tabular mt-1 text-lg font-semibold text-slate-900">{b.current}</div>
                <div className="mt-1 flex items-center justify-between text-xs">
                  <span className="text-slate-400">base {b.baseline}</span>
                  <span className={`rounded-sm border px-1.5 py-0.5 text-[10px] font-semibold ${b.status === "UNUSUAL" ? "border-red-200 bg-red-50 text-alert" : b.status === "ELEVATED" ? "border-amber-200 bg-amber-50 text-inference" : "border-emerald-200 bg-emerald-50 text-fact"}`}>{b.status}</span>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* trend */}
        <Card className="lg:col-span-2 p-5">
          <div className="mb-4 flex items-center justify-between">
            <SectionTitle label="30-day trend">{trendMetric === "refunds" ? "Refund flow" : "Captured payment flow"}</SectionTitle>
            <div className="flex gap-1">
              {["cash_received", "refunds"].map((t) => (
                <button key={t} onClick={() => setTrendMetric(t)}
                  data-testid={`trend-${t}`}
                  className={`rounded-sm border px-2 py-1 text-xs ${trendMetric === t ? "border-primary bg-accent text-primary" : "text-slate-500"}`}>
                  {t === "cash_received" ? "Payments" : "Refunds"}
                </button>
              ))}
            </div>
          </div>
          <ResponsiveContainer width="100%" height={260}>
            <AreaChart data={trend?.series || []} margin={{ left: 0, right: 8, top: 8 }}>
              <defs>
                <linearGradient id="g" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#1D4ED8" stopOpacity={0.28} />
                  <stop offset="100%" stopColor="#1D4ED8" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="2 4" stroke="#E2E8F0" vertical={false} />
              <XAxis dataKey="date" tick={{ fontSize: 10, fill: "#94A3B8" }} interval={4} tickLine={false} axisLine={false} />
              <YAxis tick={{ fontSize: 10, fill: "#94A3B8" }} tickLine={false} axisLine={false} width={54}
                tickFormatter={(v) => `₹${(v / 1000).toFixed(0)}k`} />
              <Tooltip formatter={(v) => `₹${v.toLocaleString("en-IN")}`} contentStyle={{ borderRadius: 4, border: "1px solid #E2E8F0", fontSize: 12 }} />
              <Area type="monotone" dataKey="value" stroke="#1D4ED8" strokeWidth={2} fill="url(#g)" />
            </AreaChart>
          </ResponsiveContainer>
        </Card>

        {/* attention */}
        <Card className="p-5">
          <SectionTitle label="Attention center" />
          <div className="space-y-2" data-testid="attention-items">
            {(attn?.items || []).map((a, i) => (
              <div key={i} className="rounded-sm border bg-slate-50 p-3">
                <div className="flex items-start gap-3">
                  <AlertTriangle className={`mt-0.5 h-4 w-4 ${a.severity === "high" ? "text-alert" : "text-inference"}`} />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-sm font-medium text-slate-800">{a.reason}</span>
                      <span className="tabular text-sm font-semibold text-slate-900">{a.amount}</span>
                    </div>
                    <div className="text-xs text-slate-500">{a.evidence}</div>
                    <div className="mt-1 text-xs text-primary">→ {a.recommended_action}</div>
                  </div>
                </div>
              </div>
            ))}
            {(!attn?.items || attn.items.length === 0) && <div className="py-8 text-center text-sm text-slate-400">All clear.</div>}
          </div>
        </Card>
      </div>
    </div>
  );
}
