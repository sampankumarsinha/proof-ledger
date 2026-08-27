import { createContext, useContext, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { api } from "@/lib/api";
import { Chip, Spinner } from "@/components/shared";
import { FileText, Database, Sigma, ArrowRight, GitCompareArrows, ShieldCheck } from "lucide-react";

const EvidenceCtx = createContext(null);
export const useEvidence = () => useContext(EvidenceCtx);

export function EvidenceProvider({ children }) {
  const [state, setState] = useState({ open: false, metric: null, label: "" });
  const [record, setRecord] = useState(null);
  const open = (metric, label) => setState({ open: true, metric, label });
  const close = () => setState((s) => ({ ...s, open: false }));

  const { data, isFetching } = useQuery({
    queryKey: ["evidence", state.metric],
    queryFn: async () => (await api.get(`/evidence/metric/${state.metric}`)).data,
    enabled: !!state.metric && state.open,
  });

  const fact = data?.fact;

  return (
    <EvidenceCtx.Provider value={{ open }}>
      {children}
      <Sheet open={state.open} onOpenChange={(o) => !o && close()}>
        <SheetContent className="w-full overflow-y-auto rounded-none border-l sm:max-w-xl" data-testid="evidence-drawer">
          <SheetHeader>
            <SheetTitle className="font-display flex items-center gap-2 text-xl">
              <ShieldCheck className="h-4 w-4 text-primary" /> Show Proof — {state.label || state.metric}
            </SheetTitle>
          </SheetHeader>
          {isFetching && <Spinner label="Tracing evidence" />}
          {fact && (
            <div className="mt-5 space-y-5 pl-fade">
              {/* Claim */}
              <div className="rounded-sm border bg-slate-50 p-4">
                <div className="text-[11px] uppercase tracking-widest text-slate-400">Claim</div>
                <div className="tabular mt-1 text-2xl font-semibold text-slate-900">{fact.value_display}</div>
                <div className="mt-2 flex items-center gap-2">
                  <Chip type={fact.verification_status} />
                  <span className="rounded-sm border bg-white px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-slate-500">{data.source}</span>
                </div>
              </div>

              {/* Formula */}
              <div>
                <div className="mb-1 flex items-center gap-2 text-[11px] uppercase tracking-widest text-slate-400">
                  <Sigma className="h-3 w-3" /> Calculation / Formula
                </div>
                <code className="block rounded-sm border bg-navy px-3 py-2 text-xs text-slate-100">{fact.formula}</code>
              </div>

              {/* Current vs Prior */}
              {data.prior_fact && data.delta && (
                <div>
                  <div className="mb-1 flex items-center gap-2 text-[11px] uppercase tracking-widest text-slate-400">
                    <GitCompareArrows className="h-3 w-3" /> Period comparison
                  </div>
                  <div className="grid grid-cols-3 gap-2 text-center">
                    <div className="rounded-sm border p-2"><div className="text-[10px] uppercase text-slate-400">Current</div><div className="tabular text-sm font-semibold">{fact.value_display}</div></div>
                    <div className="rounded-sm border p-2"><div className="text-[10px] uppercase text-slate-400">Previous</div><div className="tabular text-sm font-semibold text-slate-500">{data.prior_fact.value_display}</div></div>
                    <div className="rounded-sm border p-2"><div className="text-[10px] uppercase text-slate-400">Delta</div><div className={`tabular text-sm font-semibold ${data.delta.value < 0 ? "text-alert" : "text-fact"}`}>{data.delta.display}</div></div>
                  </div>
                </div>
              )}

              {/* Coverage */}
              <div className="grid grid-cols-3 gap-3 text-sm">
                <div className="rounded-sm border p-3">
                  <div className="text-[10px] uppercase tracking-widest text-slate-400">Evidence coverage</div>
                  <div className="tabular mt-1 text-lg font-semibold">{Math.round((data.evidence_coverage || 0) * 100)}%</div>
                </div>
                <div className="rounded-sm border p-3">
                  <div className="text-[10px] uppercase tracking-widest text-slate-400">Source txns</div>
                  <div className="tabular mt-1 text-lg font-semibold">{data.source_transaction_count}</div>
                </div>
                <div className="rounded-sm border p-3">
                  <div className="text-[10px] uppercase tracking-widest text-slate-400">Calc version</div>
                  <div className="tabular mt-1 text-lg font-semibold">{fact.calculation_version}</div>
                </div>
              </div>

              {/* Source records */}
              <div>
                <div className="mb-2 flex items-center gap-2 text-[11px] uppercase tracking-widest text-slate-400">
                  <Database className="h-3 w-3" /> Source transactions — {data.record_collection}
                  <span className="ml-auto normal-case text-slate-300">click to open</span>
                </div>
                <div className="divide-y rounded-sm border">
                  {(data.records || []).slice(0, 25).map((r) => (
                    <button key={r.id} onClick={() => setRecord(r)} data-testid="evidence-record"
                      className="row-hover flex w-full items-center justify-between px-3 py-2 text-left text-sm">
                      <span className="font-mono text-xs text-slate-500">{r.external_id}</span>
                      <span className="tabular font-medium text-slate-800">{r.amount_display || r.amount_paise}</span>
                      <ArrowRight className="h-3 w-3 text-slate-300" />
                    </button>
                  ))}
                  {(!data.records || data.records.length === 0) && (
                    <div className="px-3 py-6 text-center text-xs text-slate-400">Derived from other verified facts.</div>
                  )}
                </div>
              </div>
            </div>
          )}
        </SheetContent>
      </Sheet>

      <Dialog open={!!record} onOpenChange={(o) => !o && setRecord(null)}>
        <DialogContent className="max-w-lg rounded-sm">
          <DialogHeader><DialogTitle className="font-display flex items-center gap-2"><FileText className="h-4 w-4 text-primary" /> Source transaction</DialogTitle></DialogHeader>
          {record && <div className="max-h-[60vh] overflow-y-auto rounded-sm border bg-slate-50 p-4"><pre className="whitespace-pre-wrap font-mono text-xs text-slate-700">{JSON.stringify(record, null, 2)}</pre></div>}
        </DialogContent>
      </Dialog>
    </EvidenceCtx.Provider>
  );
}
