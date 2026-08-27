import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Spinner, Card, SectionTitle } from "@/components/shared";

export default function Settlements() {
  const { data, isLoading } = useQuery({ queryKey: ["settlements"], queryFn: async () => (await api.get("/settlements/intelligence")).data });
  if (isLoading) return <Spinner label="Analyzing settlements" />;

  return (
    <div className="space-y-6 pl-fade" data-testid="settlements">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        <Card className="p-4 md:col-span-1">
          <div className="text-[11px] uppercase tracking-widest text-slate-400">Pending total</div>
          <div className="tabular mt-1 text-xl font-bold text-alert">{data.pending_total}</div>
        </Card>
        {Object.entries(data.aging).map(([k, v]) => (
          <Card key={k} className="p-4">
            <div className="text-[11px] uppercase tracking-widest text-slate-400">Aging {k}</div>
            <div className="tabular mt-1 text-lg font-semibold text-slate-900">{v}</div>
          </Card>
        ))}
      </div>

      <Card className="p-5">
        <SectionTitle label="Pending settlements" right={<span className="text-xs text-slate-400">Sorted by age</span>}>Settlement timeline</SectionTitle>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-[11px] uppercase tracking-wider text-slate-400">
                <th className="px-3 py-2 text-left">Settlement</th>
                <th className="px-3 py-2 text-right">Net amount</th>
                <th className="px-3 py-2 text-right">Fee + GST</th>
                <th className="px-3 py-2 text-right">Age (days)</th>
                <th className="px-3 py-2 text-left">Expected</th>
              </tr>
            </thead>
            <tbody data-testid="pending-settlements">
              {data.pending.map((s) => (
                <tr key={s.id} className="row-hover border-b">
                  <td className="px-3 py-2 font-mono text-xs text-slate-500">{s.external_id}</td>
                  <td className="tabular px-3 py-2 text-right font-medium">{s.amount_display}</td>
                  <td className="tabular px-3 py-2 text-right text-slate-500">{s.fee_display}</td>
                  <td className={`tabular px-3 py-2 text-right font-semibold ${s.age_days > 5 ? "text-alert" : "text-slate-700"}`}>{s.age_days}</td>
                  <td className="px-3 py-2 text-xs text-slate-500">{s.expected_at ? new Date(s.expected_at).toLocaleDateString() : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
