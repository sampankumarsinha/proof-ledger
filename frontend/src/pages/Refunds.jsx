import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Spinner, Card, SectionTitle, Chip } from "@/components/shared";
import { pctStr } from "@/lib/format";

export default function Refunds() {
  const { data, isLoading } = useQuery({ queryKey: ["refunds"], queryFn: async () => (await api.get("/refunds/intelligence")).data });
  if (isLoading) return <Spinner label="Analyzing refunds" />;

  return (
    <div className="space-y-6 pl-fade" data-testid="refunds">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Card className="p-4">
          <div className="text-[11px] uppercase tracking-widest text-slate-400">Refund rate</div>
          <div className="tabular mt-1 text-2xl font-bold text-slate-900">{data.refund_rate.value_display}</div>
        </Card>
        <Card className="p-4">
          <div className="text-[11px] uppercase tracking-widest text-slate-400">Refunds (period)</div>
          <div className="tabular mt-1 text-2xl font-bold text-slate-900">{data.change.current.value_display}</div>
        </Card>
        <Card className="p-4">
          <div className="text-[11px] uppercase tracking-widest text-slate-400">vs prior</div>
          <div className={`tabular mt-1 text-2xl font-bold ${data.change.change_pct > 0 ? "text-alert" : "text-fact"}`}>{pctStr(data.change.change_pct)}</div>
        </Card>
        <Card className="p-4">
          <div className="text-[11px] uppercase tracking-widest text-slate-400">Prior period</div>
          <div className="tabular mt-1 text-2xl font-bold text-slate-500">{data.change.prior.value_display}</div>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card className="p-5">
          <SectionTitle label="By product" right={<Chip type="VERIFIED_FACT" />}>What's driving refunds</SectionTitle>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-[11px] uppercase tracking-wider text-slate-400">
                <th className="px-3 py-2 text-left">Product</th>
                <th className="px-3 py-2 text-right">Revenue</th>
                <th className="px-3 py-2 text-right">Refunded</th>
                <th className="px-3 py-2 text-right">Rate</th>
              </tr>
            </thead>
            <tbody data-testid="refunds-by-product">
              {data.by_product.map((p) => (
                <tr key={p.product_id} className="row-hover border-b">
                  <td className="px-3 py-2 text-slate-700">{p.name}</td>
                  <td className="tabular px-3 py-2 text-right">{p.total_display}</td>
                  <td className="tabular px-3 py-2 text-right text-alert">{"₹" + (p.refunded / 100).toLocaleString("en-IN")}</td>
                  <td className={`tabular px-3 py-2 text-right font-semibold ${p.refund_rate > 10 ? "text-alert" : "text-slate-600"}`}>{p.refund_rate}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
        <Card className="p-5">
          <SectionTitle label="By reason" />
          <div className="space-y-2" data-testid="refunds-by-reason">
            {data.by_reason.map((r) => (
              <div key={r.reason} className="flex items-center justify-between rounded-sm border p-3">
                <span className="text-sm text-slate-700">{r.reason}</span>
                <span className="tabular text-sm font-medium">{r.total_display} <span className="text-xs text-slate-400">({r.count})</span></span>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
