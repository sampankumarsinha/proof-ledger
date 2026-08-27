import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, apiError } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Spinner, Card, SectionTitle } from "@/components/shared";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { CheckCircle2, XCircle, Play } from "lucide-react";

export default function Evaluation() {
  const qc = useQueryClient();
  const { user } = useAuth();
  const canWrite = ["OWNER", "ADMIN", "ANALYST"].includes(user?.role);
  const { data, isLoading } = useQuery({ queryKey: ["eval"], queryFn: async () => (await api.get("/evaluations/latest")).data });
  const run = useMutation({
    mutationFn: async () => (await api.post("/evaluations/run")).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["eval"] }),
    onError: (e) => toast.error(apiError(e.response?.data?.detail)),
  });
  if (isLoading) return <Spinner />;

  const hasRun = data?.results;

  return (
    <div className="space-y-6 pl-fade" data-testid="evaluation">
      <div className="flex items-center justify-between">
        <SectionTitle label="Evaluation Lab">Benchmark accuracy</SectionTitle>
        <Button onClick={() => run.mutate()} disabled={run.isPending || !canWrite}
          title={canWrite ? "" : "Requires ANALYST role or higher"}
          className="rounded-sm bg-primary text-white" data-testid="run-eval">
          <Play className="mr-1 h-4 w-4" /> {run.isPending ? "Running…" : "Run benchmark"}
        </Button>
      </div>

      {!hasRun ? (
        <Card className="p-10 text-center text-sm text-slate-400">No runs yet. Benchmark has {data?.benchmark_size} test cases with ground truth computed independently from records.</Card>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Card className="p-4"><div className="text-[11px] uppercase text-slate-400">Score</div><div className="tabular mt-1 text-2xl font-bold text-fact">{data.score_pct}%</div></Card>
            <Card className="p-4"><div className="text-[11px] uppercase text-slate-400">Passed</div><div className="tabular mt-1 text-2xl font-bold">{data.passed}/{data.total}</div></Card>
            <Card className="p-4"><div className="text-[11px] uppercase text-slate-400">Total latency</div><div className="tabular mt-1 text-2xl font-bold">{data.total_latency_ms}ms</div></Card>
            <Card className="p-4"><div className="text-[11px] uppercase text-slate-400">Categories</div><div className="mt-1 text-sm text-slate-600">{data.categories.length}</div></Card>
          </div>

          <Card className="p-5">
            <SectionTitle label="Test cases" right={<span className="text-xs text-slate-400">Ground truth computed independently</span>} />
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead><tr className="border-b text-[11px] uppercase tracking-wider text-slate-400">
                  <th className="px-3 py-2 text-left">Result</th>
                  <th className="px-3 py-2 text-left">Category</th>
                  <th className="px-3 py-2 text-left">Question</th>
                  <th className="px-3 py-2 text-left">Detail</th>
                  <th className="px-3 py-2 text-right">Latency</th>
                </tr></thead>
                <tbody data-testid="eval-results">
                  {data.results.map((r) => (
                    <tr key={r.id} className="row-hover border-b align-top">
                      <td className="px-3 py-2">{r.passed ? <CheckCircle2 className="h-4 w-4 text-fact" /> : <XCircle className="h-4 w-4 text-alert" />}</td>
                      <td className="px-3 py-2 text-xs text-slate-500">{r.category.replace(/_/g, " ")}</td>
                      <td className="px-3 py-2 text-slate-700">{r.question}</td>
                      <td className="px-3 py-2 font-mono text-[11px] text-slate-500">{JSON.stringify(r.detail)}</td>
                      <td className="tabular px-3 py-2 text-right text-slate-500">{r.latency_ms}ms</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      )}
    </div>
  );
}
