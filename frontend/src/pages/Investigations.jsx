import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, apiError, RAW_BASE } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Spinner, Card, SectionTitle, Chip, ConfidenceBar } from "@/components/shared";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { toast } from "sonner";
import { Plus, FileDown, FolderSearch } from "lucide-react";

export default function Investigations() {
  const qc = useQueryClient();
  const { user } = useAuth();
  const canWrite = ["OWNER", "ADMIN", "ANALYST"].includes(user?.role);
  const [sel, setSel] = useState(null);
  const [title, setTitle] = useState("");
  const [question, setQuestion] = useState("Why did cash decrease this month?");
  const [openNew, setOpenNew] = useState(false);

  const { data, isLoading } = useQuery({ queryKey: ["investigations"], queryFn: async () => (await api.get("/investigations")).data });

  const create = useMutation({
    mutationFn: async () => (await api.post("/investigations", { title: title || question.slice(0, 50), question })).data,
    onSuccess: (d) => { toast.success("Investigation created"); setOpenNew(false); setSel(d); qc.invalidateQueries({ queryKey: ["investigations"] }); },
    onError: (e) => toast.error(apiError(e.response?.data?.detail)),
  });

  const decide = useMutation({
    mutationFn: async ({ id, decision }) => (await api.post(`/investigations/${id}/decision`, { decision })).data,
    onSuccess: (_, v) => { toast.success(`Marked ${v.decision}`); setSel((s) => ({ ...s, decision: { decision: v.decision } })); qc.invalidateQueries({ queryKey: ["investigations"] }); },
    onError: (e) => toast.error(apiError(e.response?.data?.detail)),
  });

  if (isLoading) return <Spinner />;

  return (
    <div className="grid grid-cols-1 gap-6 pl-fade lg:grid-cols-3" data-testid="investigations">
      <div className="lg:col-span-1">
        <div className="mb-3 flex items-center justify-between">
          <SectionTitle label="Workspace">Investigations</SectionTitle>
          {canWrite && (
          <Dialog open={openNew} onOpenChange={setOpenNew}>
            <DialogTrigger asChild><Button size="sm" className="rounded-sm bg-primary text-white" data-testid="new-investigation-btn"><Plus className="mr-1 h-4 w-4" />New</Button></DialogTrigger>
            <DialogContent className="rounded-sm">
              <DialogHeader><DialogTitle className="font-display">New investigation</DialogTitle></DialogHeader>
              <div className="space-y-3">
                <Input placeholder="Title" value={title} onChange={(e) => setTitle(e.target.value)} className="rounded-sm" data-testid="inv-title" />
                <Input placeholder="Question" value={question} onChange={(e) => setQuestion(e.target.value)} className="rounded-sm" data-testid="inv-question" />
                <Button onClick={() => create.mutate()} disabled={create.isPending} className="w-full rounded-sm bg-primary text-white" data-testid="inv-create">
                  {create.isPending ? "Investigating…" : "Run & save"}
                </Button>
              </div>
            </DialogContent>
          </Dialog>
          )}
        </div>
        <div className="space-y-2">
          {data.investigations.map((inv) => (
            <button key={inv.id} onClick={() => setSel(inv)} data-testid="inv-item"
              className={`w-full rounded-sm border p-3 text-left row-hover ${sel?.id === inv.id ? "border-primary" : ""}`}>
              <div className="flex items-center justify-between">
                <span className="truncate text-sm font-medium text-slate-800">{inv.title}</span>
                <span className={`text-[10px] font-semibold ${inv.status === "OPEN" ? "text-inference" : "text-fact"}`}>{inv.status}</span>
              </div>
              <div className="truncate text-xs text-slate-400">{inv.question}</div>
            </button>
          ))}
          {data.investigations.length === 0 && <div className="rounded-sm border p-6 text-center text-sm text-slate-400"><FolderSearch className="mx-auto mb-2 h-5 w-5" />No investigations yet.</div>}
        </div>
      </div>

      <div className="lg:col-span-2">
        {!sel ? (
          <Card className="flex h-64 items-center justify-center text-sm text-slate-400">Select an investigation.</Card>
        ) : (
          <div className="space-y-4">
            <Card className="p-5">
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="font-display text-xl text-slate-900">{sel.title}</h3>
                  <p className="text-sm text-slate-500">{sel.question}</p>
                </div>
                <ConfidenceBar confidence={sel.confidence} />
              </div>
              <p className="mt-3 text-sm text-slate-700">{sel.summary}</p>
              <div className="mt-4 flex gap-2">
                {canWrite && ["APPROVE", "REVIEW", "DISMISS"].map((d) => (
                  <Button key={d} size="sm" variant={sel.decision?.decision === d ? "default" : "outline"}
                    onClick={() => decide.mutate({ id: sel.id, decision: d })}
                    data-testid={`decide-${d}`}
                    className={`rounded-sm ${sel.decision?.decision === d ? "bg-primary text-white" : ""}`}>{d}</Button>
                ))}
                <a href={`${RAW_BASE}/investigations/${sel.id}/report.pdf`} target="_blank" rel="noreferrer"
                  className="ml-auto flex items-center gap-1 rounded-sm border border-primary/40 px-3 py-1.5 text-sm font-medium text-primary hover:bg-accent" data-testid="export-pdf">
                  <FileDown className="h-3.5 w-3.5" /> PDF
                </a>
                <a href={`${RAW_BASE}/investigations/${sel.id}/report`} target="_blank" rel="noreferrer"
                  className="flex items-center gap-1 rounded-sm border px-3 py-1.5 text-sm text-slate-600 hover:text-primary" data-testid="export-json">
                  <FileDown className="h-3.5 w-3.5" /> JSON
                </a>
                <a href={`${RAW_BASE}/investigations/${sel.id}/report?fmt=csv`} target="_blank" rel="noreferrer"
                  className="flex items-center gap-1 rounded-sm border px-3 py-1.5 text-sm text-slate-600 hover:text-primary" data-testid="export-csv">
                  <FileDown className="h-3.5 w-3.5" /> CSV
                </a>
              </div>
            </Card>
            <Card className="p-5">
              <SectionTitle label="Findings" />
              <div className="space-y-2">
                {(sel.findings || []).map((f, i) => (
                  <div key={i} className="flex items-start justify-between gap-3 rounded-sm border bg-slate-50 p-3">
                    <span className="text-sm text-slate-700">{f.statement}</span><Chip type={f.type} />
                  </div>
                ))}
              </div>
            </Card>
            {sel.recommendations?.length > 0 && (
              <Card className="p-5">
                <SectionTitle label="Recommendations" right={<Chip type="RECOMMENDATION" />} />
                <ul className="list-disc pl-5 text-sm text-slate-700">{sel.recommendations.map((r, i) => <li key={i}>{r}</li>)}</ul>
              </Card>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
