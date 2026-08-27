import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Spinner, Card, SectionTitle } from "@/components/shared";

export default function Audit() {
  const { data, isLoading } = useQuery({ queryKey: ["audit"], queryFn: async () => (await api.get("/audit")).data });
  if (isLoading) return <Spinner />;

  return (
    <Card className="p-5 pl-fade" data-testid="audit">
      <SectionTitle label={`${data.total} events`}>Audit trail</SectionTitle>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead><tr className="border-b text-[11px] uppercase tracking-wider text-slate-400">
            <th className="px-3 py-2 text-left">Time</th>
            <th className="px-3 py-2 text-left">User</th>
            <th className="px-3 py-2 text-left">Action</th>
            <th className="px-3 py-2 text-left">Payload</th>
          </tr></thead>
          <tbody data-testid="audit-rows">
            {data.logs.map((l) => (
              <tr key={l.id} className="row-hover border-b align-top">
                <td className="px-3 py-2 text-xs text-slate-500">{new Date(l.created_at).toLocaleString()}</td>
                <td className="px-3 py-2 text-slate-600">{l.user_email}</td>
                <td className="px-3 py-2"><span className="rounded-sm border bg-slate-50 px-2 py-0.5 text-xs font-medium">{l.action}</span></td>
                <td className="px-3 py-2 font-mono text-[11px] text-slate-500">{JSON.stringify(l.payload).slice(0, 120)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {data.logs.length === 0 && <div className="py-8 text-center text-sm text-slate-400">No audit events yet.</div>}
      </div>
    </Card>
  );
}
