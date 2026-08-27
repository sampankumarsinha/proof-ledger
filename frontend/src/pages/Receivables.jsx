import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Spinner, Card, SectionTitle, RiskBadge } from "@/components/shared";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Cell } from "recharts";

const ORDER = ["current", "1-7", "8-30", "31-60", "60+"];
const COLORS = { current: "#15803D", "1-7": "#1D4ED8", "8-30": "#0284C7", "31-60": "#B45309", "60+": "#B91C1C" };

export default function Receivables() {
  const { data, isLoading } = useQuery({ queryKey: ["receivables"], queryFn: async () => (await api.get("/receivables/intelligence")).data });
  if (isLoading) return <Spinner label="Aging receivables" />;

  const chart = ORDER.map((k) => ({ bucket: k, value: (data.aging.buckets[k] || 0) / 100 }));

  return (
    <div className="space-y-6 pl-fade" data-testid="receivables">
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card className="p-5">
          <SectionTitle label="Aging buckets" />
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={chart}>
              <CartesianGrid strokeDasharray="2 4" stroke="#E2E8F0" vertical={false} />
              <XAxis dataKey="bucket" tick={{ fontSize: 11, fill: "#64748B" }} tickLine={false} axisLine={false} />
              <YAxis tick={{ fontSize: 10, fill: "#94A3B8" }} tickLine={false} axisLine={false} width={54}
                tickFormatter={(v) => `₹${(v / 1000).toFixed(0)}k`} />
              <Tooltip formatter={(v) => `₹${v.toLocaleString("en-IN")}`} contentStyle={{ borderRadius: 4, fontSize: 12 }} />
              <Bar dataKey="value" radius={[2, 2, 0, 0]}>
                {chart.map((e) => <Cell key={e.bucket} fill={COLORS[e.bucket]} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>
        <Card className="p-5">
          <SectionTitle label="Risk rule (deterministic)" />
          <p className="text-sm text-slate-600">{data.risk_rule}</p>
          <div className="mt-4 grid grid-cols-2 gap-2">
            {ORDER.map((k) => (
              <div key={k} className="flex items-center justify-between rounded-sm border p-3">
                <span className="text-[11px] uppercase tracking-wider text-slate-400">{k}</span>
                <span className="tabular font-semibold" style={{ color: COLORS[k] }}>{data.aging.buckets_display[k]}</span>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <Card className="p-5">
        <SectionTitle label="Outstanding invoices" />
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-[11px] uppercase tracking-wider text-slate-400">
                <th className="px-3 py-2 text-left">Invoice</th>
                <th className="px-3 py-2 text-left">Customer</th>
                <th className="px-3 py-2 text-right">Amount</th>
                <th className="px-3 py-2 text-right">Age (days)</th>
                <th className="px-3 py-2 text-left">Risk</th>
              </tr>
            </thead>
            <tbody data-testid="receivables-rows">
              {data.rows.map((r) => (
                <tr key={r.invoice_id} className="row-hover border-b">
                  <td className="px-3 py-2 font-mono text-xs text-slate-500">{r.external_id}</td>
                  <td className="px-3 py-2 text-slate-700">{r.customer}</td>
                  <td className="tabular px-3 py-2 text-right font-medium">{r.amount_display}</td>
                  <td className="tabular px-3 py-2 text-right">{r.age_days}</td>
                  <td className="px-3 py-2"><RiskBadge risk={r.risk} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
