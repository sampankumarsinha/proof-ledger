import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Spinner, Card, SectionTitle, ClassBadge } from "@/components/shared";

export default function Reconciliation() {
  const { data, isLoading } = useQuery({ queryKey: ["recon"], queryFn: async () => (await api.get("/reconciliation")).data });
  if (isLoading) return <Spinner label="Reconciling payments" />;

  const classes = Object.entries(data.summary).filter(([, v]) => v.count > 0);

  return (
    <div className="space-y-6 pl-fade" data-testid="reconciliation">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Card className="p-4">
          <div className="text-[11px] uppercase tracking-widest text-slate-400">Match rate</div>
          <div className="tabular mt-1 text-2xl font-bold text-fact">{data.match_rate}%</div>
        </Card>
        <Card className="p-4">
          <div className="text-[11px] uppercase tracking-widest text-slate-400">Total payments</div>
          <div className="tabular mt-1 text-2xl font-bold text-slate-900">{data.total_payments}</div>
        </Card>
        <Card className="p-4">
          <div className="text-[11px] uppercase tracking-widest text-slate-400">Exceptions</div>
          <div className="tabular mt-1 text-2xl font-bold text-alert">{data.exceptions.length}</div>
        </Card>
        <Card className="p-4">
          <div className="text-[11px] uppercase tracking-widest text-slate-400">Method</div>
          <div className="mt-1 text-sm font-medium text-slate-700">Deterministic</div>
        </Card>
      </div>

      <Card className="p-5">
        <SectionTitle label="Classification breakdown" />
        <div className="grid grid-cols-2 gap-2 md:grid-cols-3 lg:grid-cols-4">
          {classes.map(([k, v]) => (
            <div key={k} className="flex flex-col items-start gap-1.5 rounded-sm border p-3 sm:flex-row sm:items-center sm:justify-between sm:gap-2">
              <ClassBadge cls={k} />
              <div className="text-left sm:text-right">
                <div className="tabular text-sm font-semibold">{v.count}</div>
                <div className="tabular text-[11px] text-slate-400">{v.amount_display}</div>
              </div>
            </div>
          ))}
        </div>
      </Card>

      <Card className="p-5">
        <SectionTitle label="Exceptions requiring review" />
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-[11px] uppercase tracking-wider text-slate-400">
                <th className="px-3 py-2 text-left">Payment</th>
                <th className="px-3 py-2 text-left">Classification</th>
                <th className="px-3 py-2 text-right">Amount</th>
                <th className="px-3 py-2 text-left">Explanation</th>
              </tr>
            </thead>
            <tbody data-testid="recon-exceptions">
              {data.exceptions.map((r) => (
                <tr key={r.payment_id} className="row-hover border-b">
                  <td className="px-3 py-2 font-mono text-xs text-slate-500">{r.external_id}</td>
                  <td className="px-3 py-2"><ClassBadge cls={r.classification} /></td>
                  <td className="tabular px-3 py-2 text-right font-medium">{r.amount_display}</td>
                  <td className="px-3 py-2 text-slate-600">{r.explanation}</td>
                </tr>
              ))}
              {data.exceptions.length === 0 && (
                <tr><td colSpan={4} className="py-8 text-center text-slate-400">Everything reconciles.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
