import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, apiError } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Spinner, Card, SectionTitle } from "@/components/shared";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { ShieldCheck } from "lucide-react";

export default function Decisions() {
  const qc = useQueryClient();
  const { user } = useAuth();
  const { data, isLoading } = useQuery({ queryKey: ["decisions"], queryFn: async () => (await api.get("/decisions")).data });
  const decide = useMutation({
    mutationFn: async ({ id, decision }) => (await api.post(`/decisions/${id}`, { decision })).data,
    onSuccess: (_, v) => { toast.success(`Marked ${v.decision}`); qc.invalidateQueries({ queryKey: ["decisions"] }); },
    onError: (e) => toast.error(apiError(e.response?.data?.detail)),
  });
  if (isLoading) return <Spinner />;
  const canWrite = ["OWNER", "ADMIN", "ANALYST"].includes(user?.role);

  return (
    <div className="space-y-4 pl-fade" data-testid="decisions">
      <div className="flex items-center gap-2 rounded-sm border bg-accent/50 px-4 py-2 text-sm text-slate-600">
        <ShieldCheck className="h-4 w-4 text-primary" /> {data.note}
      </div>
      {data.items.map((it) => (
        <Card key={it.id} className="p-5" data-testid={`decision-${it.id}`}>
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <div className="text-lg font-semibold text-slate-900">{it.issue}</div>
              <div className="mt-1 flex items-center gap-3 text-sm text-slate-500">
                <span>Evidence: <span className="font-semibold text-fact">{it.evidence}</span> ({it.evidence_records} records)</span>
                <span>Impact: <span className="tabular font-semibold text-slate-800">{it.financial_impact}</span></span>
              </div>
              <div className="mt-1 text-sm text-slate-600">Suggested: {it.suggested_action}</div>
            </div>
            <div className="flex gap-2">
              {["APPROVE", "REVIEW", "DISMISS"].map((d) => (
                <Button key={d} size="sm" variant={it.decision === d ? "default" : "outline"}
                  onClick={() => decide.mutate({ id: it.id, decision: d })} disabled={!canWrite}
                  title={canWrite ? "" : "Requires ANALYST role or higher"}
                  data-testid={`decision-${it.id}-${d}`}
                  className={`rounded-sm ${it.decision === d ? "bg-primary text-white" : ""}`}>{d}</Button>
              ))}
            </div>
          </div>
        </Card>
      ))}
      {data.items.length === 0 && <Card className="p-10 text-center text-sm text-slate-400">No open decisions. Everything is healthy.</Card>}
    </div>
  );
}
