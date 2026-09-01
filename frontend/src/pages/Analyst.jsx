import { useState, useEffect } from "react";
import { useMutation } from "@tanstack/react-query";
import { api, apiError } from "@/lib/api";
import { useEvidence } from "@/components/EvidenceDrawer";
import { Chip, ConfidenceBar, Card, SectionTitle } from "@/components/shared";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { Sparkles, Send, CheckCircle2, Search, Lightbulb, Save, FileSearch, Calendar, Layers } from "lucide-react";

const SUGGESTIONS = [
  "Why did cash decrease this month?",
  "Which products are driving refunds?",
  "Which customers owe me money?",
  "Which settlements are delayed?",
  "Compare this period with the prior period.",
  "Show me unreconciled payments.",
];

const STAGES = [
  "Understanding question...",
  "Selecting financial tools...",
  "Querying financial records...",
  "Calculating verified result...",
  "Collecting evidence...",
  "Preparing explanation...",
];

export default function Analyst() {
  const { open } = useEvidence();
  const [q, setQ] = useState("");
  const [result, setResult] = useState(null);
  const [context, setContext] = useState(null);
  const [stageIdx, setStageIdx] = useState(0);

  useEffect(() => {
    let timer;
    if (stageIdx < STAGES.length - 1) {
      timer = setTimeout(() => setStageIdx((prev) => prev + 1), 350);
    }
    return () => clearTimeout(timer);
  }, [stageIdx]);

  const ask = useMutation({
    mutationFn: async (question) => {
      setStageIdx(0);
      const res = await api.post("/ai/ask", { question, context });
      return res.data;
    },
    onSuccess: (d) => {
      setResult(d);
      if (d.context) {
        setContext(d.context);
      }
    },
    onError: (e) => toast.error(apiError(e.response?.data?.detail)),
  });

  const submit = (question) => {
    const text = question || q;
    if (!text.trim()) return;
    setQ(text);
    setResult(null);
    ask.mutate(text);
  };

  const saveInvestigation = async () => {
    try {
      await api.post("/investigations", { title: result.question.slice(0, 60), question: result.question });
      toast.success("Saved to Investigations");
    } catch (e) {
      toast.error(apiError(e.response?.data?.detail));
    }
  };

  return (
    <div className="mx-auto max-w-4xl space-y-6 pl-fade" data-testid="ai-analyst">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-sm bg-navy text-white">
            <Sparkles className="h-5 w-5" />
          </div>
          <div>
            <h2 className="font-display text-2xl tracking-tight text-slate-900">AI Financial Analyst</h2>
            <p className="text-sm text-slate-500">Ask in plain English. Numbers are computed deterministically and proven.</p>
          </div>
        </div>
        {context?.metric && (
          <div className="flex items-center gap-1.5 rounded-sm border bg-slate-50 px-2.5 py-1 text-xs text-slate-600">
            <Layers className="h-3.5 w-3.5 text-primary" /> Active Context: <span className="font-medium text-slate-900">{context.metric.replace(/_/g, " ")}</span>
          </div>
        )}
      </div>

      {/* input */}
      <Card className="p-2">
        <div className="flex items-center gap-2">
          <input
            data-testid="analyst-input"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && submit()}
            placeholder="e.g. Why did cash decrease this month?"
            className="flex-1 bg-transparent px-3 py-2 text-sm outline-none placeholder:text-slate-400"
          />
          <Button
            onClick={() => submit()}
            disabled={ask.isPending}
            data-testid="analyst-ask-btn"
            className="rounded-sm bg-primary text-white hover:bg-primary/90"
          >
            <Send className="mr-1 h-4 w-4" /> Investigate
          </Button>
        </div>
      </Card>

      {!result && !ask.isPending && (
        <div>
          <div className="mb-2 text-[11px] uppercase tracking-widest text-slate-400">Suggested questions</div>
          <div className="flex flex-wrap gap-2">
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                onClick={() => submit(s)}
                data-testid="suggestion-chip"
                className="rounded-sm border bg-white px-3 py-1.5 text-sm text-slate-600 hover:border-primary hover:text-primary"
              >
                {s}
              </button>
            ))}
          </div>
        </div>
      )}

      {ask.isPending && (
        <Card className="p-6 space-y-3">
          <div className="flex items-center gap-2 text-sm font-medium text-slate-800">
            <Search className="h-4 w-4 animate-spin text-primary" /> Investigating financial records...
          </div>
          <div className="grid grid-cols-2 gap-2 text-xs text-slate-500 pt-2 border-t">
            {STAGES.map((stg, i) => (
              <div key={i} className={`flex items-center gap-2 ${i <= stageIdx ? "text-slate-700 font-medium" : "text-slate-300"}`}>
                <CheckCircle2 className={`h-3.5 w-3.5 ${i <= stageIdx ? "text-fact" : "text-slate-200"}`} />
                {stg}
              </div>
            ))}
          </div>
        </Card>
      )}

      {result && (
        <div className="space-y-6 pl-fade">
          {/* tool execution */}
          <Card className="p-5">
            <SectionTitle
              label="Investigation"
              right={
                <div className="flex items-center gap-2">
                  {result.period?.label && (
                    <span className="inline-flex items-center gap-1 rounded-sm bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
                      <Calendar className="h-3 w-3" /> {result.period.label}
                    </span>
                  )}
                  <Chip type={result.intent === "cash_autopsy" || result.intent === "investigation" ? "DERIVED_FACT" : "VERIFIED_FACT"}>
                    {result.intent.replace(/_/g, " ")}
                  </Chip>
                </div>
              }
            />
            {result.tool_log.length > 0 ? (
              <div className="space-y-1.5">
                {result.tool_log.map((t, i) => (
                  <div key={i} className="flex items-center gap-2 text-sm text-slate-600" style={{ animation: "pl-fade .3s ease both", animationDelay: `${i * 70}ms` }}>
                    <CheckCircle2 className="h-4 w-4 text-fact" />
                    <span>{t.label}</span>
                    <span className="tabular text-xs text-slate-400">✓ {t.records} records</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-slate-500">General financial knowledge response (no database queries required).</p>
            )}

            <div className="mt-4 flex items-center justify-between border-t pt-4">
              <ConfidenceBar confidence={result.confidence} />
              <span className="text-[11px] text-slate-400">Explainer: {result.ai_available ? result.explainer : "deterministic (no AI key)"}</span>
            </div>
          </Card>

          {/* summary */}
          <Card className="p-5">
            <SectionTitle label="Answer" />
            <p className="text-sm leading-relaxed text-slate-700">{result.summary}</p>
            <p className="mt-3 text-xs italic text-slate-400">{result.confidence.explanation}</p>
          </Card>

          {/* findings */}
          {result.findings?.length > 0 && (
            <Card className="p-5">
              <SectionTitle
                label="Findings"
                right={
                  <Button onClick={saveInvestigation} variant="outline" size="sm" className="rounded-sm" data-testid="save-investigation">
                    <Save className="mr-1 h-3.5 w-3.5" /> Save investigation
                  </Button>
                }
              />
              <div className="space-y-2" data-testid="findings-list">
                {result.findings.map((f, i) => (
                  <div key={i} className="flex items-start justify-between gap-3 rounded-sm border bg-slate-50 p-3">
                    <span className="text-sm text-slate-700">{f.statement}</span>
                    <Chip type={f.type} />
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* autopsy contributors with Show Proof */}
          {result.autopsy && (
            <Card className="p-5" data-testid="autopsy-contributors">
              <SectionTitle label="Ranked contributors" right={<Chip type="INFERENCE">Observed movements</Chip>} />
              <p className="mb-3 text-xs text-slate-400">{result.autopsy.interpretation}</p>
              <div className="divide-y rounded-sm border">
                {result.autopsy.contributors.map((c, i) => (
                  <div key={i} className="row-hover flex items-center justify-between px-4 py-3">
                    <div>
                      <div className="text-sm font-medium capitalize text-slate-800">{c.metric.replace(/_/g, " ")}</div>
                      <div className="text-xs text-slate-500">{c.note}</div>
                      <code className="mt-1 block text-[11px] text-slate-400">{c.calculation}</code>
                    </div>
                    <div className="flex items-center gap-3">
                      <div className="text-right">
                        <div className={`tabular text-sm font-semibold ${c.impact < 0 ? "text-alert" : "text-fact"}`}>{c.impact_display}</div>
                        <div className="text-[11px] text-slate-400">{c.evidence_count} records</div>
                      </div>
                      <button
                        onClick={() =>
                          open(
                            c.metric === "settlement_timing"
                              ? "pending_settlements"
                              : c.metric === "processing_fees"
                              ? "fee_total"
                              : c.metric === "receivables"
                              ? "receivables_outstanding"
                              : c.metric === "failed_payments"
                              ? "failed_payments"
                              : c.metric,
                            c.metric.replace(/_/g, " ")
                          )
                        }
                        data-testid={`show-proof-${c.metric}`}
                        className="flex items-center gap-1 rounded-sm border border-primary/40 px-2 py-1 text-xs font-medium text-primary hover:bg-accent"
                      >
                        <FileSearch className="h-3.5 w-3.5" /> Show proof
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* recommendations */}
          {result.recommendations?.length > 0 && (
            <Card className="p-5">
              <SectionTitle label="Recommendations" right={<Chip type="RECOMMENDATION" />} />
              <ul className="space-y-2">
                {result.recommendations.map((r, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-slate-700">
                    <Lightbulb className="mt-0.5 h-4 w-4 text-inference" /> {r}
                  </li>
                ))}
              </ul>
            </Card>
          )}

          {/* next questions */}
          {result.next_questions?.length > 0 && (
            <div className="space-y-2">
              <div className="text-[11px] uppercase tracking-widest text-slate-400">Suggested follow-ups</div>
              <div className="flex flex-wrap gap-2">
                {result.next_questions.map((s) => (
                  <button
                    key={s}
                    onClick={() => submit(s)}
                    className="rounded-sm border bg-white px-3 py-1.5 text-sm text-slate-600 hover:border-primary hover:text-primary"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
