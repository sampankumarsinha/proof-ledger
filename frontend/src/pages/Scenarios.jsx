import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Card, SectionTitle, Chip, Spinner } from "@/components/shared";
import { Button } from "@/components/ui/button";

const INPUTS = [
  { key: "refund_change_pct", label: "Refund change %", min: -50, max: 50 },
  { key: "settlement_clear_pct", label: "Pending settlements cleared %", min: 0, max: 100 },
  { key: "receivables_collect_pct", label: "Receivables collected %", min: 0, max: 100 },
  { key: "payment_volume_change_pct", label: "Payment volume change %", min: -30, max: 30 },
  { key: "fee_change_pct", label: "Fee change %", min: -20, max: 20 },
];

const CF = [
  { kind: "no_refunds", label: "What if there were no refunds?" },
  { kind: "settlements_cleared", label: "What if pending settlements cleared?" },
  { kind: "refunds_down_10", label: "What if refunds dropped 10%?" },
];

export default function Scenarios() {
  const [vals, setVals] = useState({ settlement_clear_pct: 100, refund_change_pct: -10 });
  const [cfKind, setCfKind] = useState(null);

  const sim = useMutation({ mutationFn: async () => (await api.post("/scenarios/simulate", vals)).data });
  const { data: cf } = useQuery({
    queryKey: ["cf", cfKind],
    queryFn: async () => (await api.get(`/scenarios/counterfactual/${cfKind}`)).data,
    enabled: !!cfKind,
  });

  const r = sim.data;

  return (
    <div className="grid grid-cols-1 gap-6 pl-fade lg:grid-cols-2" data-testid="scenarios">
      <Card className="p-5">
        <SectionTitle label="Scenario Simulator" right={<Chip type="INFERENCE">Simulation</Chip>}>Adjust levers</SectionTitle>
        <div className="space-y-5">
          {INPUTS.map((inp) => (
            <div key={inp.key}>
              <div className="flex justify-between text-sm">
                <span className="text-slate-600">{inp.label}</span>
                <span className="tabular font-semibold text-primary">{vals[inp.key] ?? 0}%</span>
              </div>
              <input type="range" min={inp.min} max={inp.max} value={vals[inp.key] ?? 0}
                onChange={(e) => setVals((v) => ({ ...v, [inp.key]: Number(e.target.value) }))}
                data-testid={`slider-${inp.key}`}
                className="mt-1 w-full accent-primary" />
            </div>
          ))}
          <Button onClick={() => sim.mutate()} disabled={sim.isPending} className="w-full rounded-sm bg-primary text-white" data-testid="run-scenario">
            {sim.isPending ? "Computing…" : "Project cash impact"}
          </Button>
        </div>
      </Card>

      <div className="space-y-6">
        <Card className="p-5">
          <SectionTitle label="Projected result" right={r && <Chip type="INFERENCE">{r.label}</Chip>} />
          {!r ? <div className="py-8 text-center text-sm text-slate-400">Adjust levers and run a projection.</div> : (
            <>
              <div className="grid grid-cols-3 gap-3 text-center">
                <div className="rounded-sm border p-3"><div className="text-[11px] uppercase text-slate-400">Baseline</div><div className="tabular mt-1 font-bold">{r.baseline_cash_display}</div></div>
                <div className="rounded-sm border border-primary/40 bg-accent p-3"><div className="text-[11px] uppercase text-primary">Projected</div><div className="tabular mt-1 font-bold text-primary">{r.projected_cash_display}</div></div>
                <div className="rounded-sm border p-3"><div className="text-[11px] uppercase text-slate-400">Delta</div><div className={`tabular mt-1 font-bold ${r.delta < 0 ? "text-alert" : "text-fact"}`}>{r.delta_display}</div></div>
              </div>
              <div className="mt-4 space-y-1">
                {r.breakdown.map((b, i) => (
                  <div key={i} className="flex justify-between border-b py-1.5 text-sm">
                    <span className="text-slate-600">{b.label}</span>
                    <span className={`tabular font-medium ${b.scenario < 0 ? "text-alert" : b.scenario > 0 ? "text-fact" : "text-slate-400"}`}>{b.scenario_display}</span>
                  </div>
                ))}
              </div>
              <p className="mt-3 text-xs italic text-slate-400">{r.disclaimer}</p>
            </>
          )}
        </Card>

        <Card className="p-5">
          <SectionTitle label="Counterfactuals" right={<Chip type="INFERENCE">Counterfactual</Chip>} />
          <div className="flex flex-wrap gap-2">
            {CF.map((c) => (
              <button key={c.kind} onClick={() => setCfKind(c.kind)} data-testid={`cf-${c.kind}`}
                className={`rounded-sm border px-3 py-1.5 text-sm ${cfKind === c.kind ? "border-primary bg-accent text-primary" : "text-slate-600"}`}>{c.label}</button>
            ))}
          </div>
          {cf && (
            <div className="mt-4 rounded-sm border bg-slate-50 p-4">
              <div className="text-sm text-slate-600">{cf.description}</div>
              <div className="mt-2 flex items-center gap-6">
                <div><div className="text-[11px] uppercase text-slate-400">Actual</div><div className="tabular font-bold">{cf.actual_cash_display}</div></div>
                <div><div className="text-[11px] uppercase text-slate-400">Counterfactual</div><div className="tabular font-bold text-primary">{cf.counterfactual_cash_display}</div></div>
                <div><div className="text-[11px] uppercase text-slate-400">Difference</div><div className="tabular font-bold text-fact">{cf.difference_display}</div></div>
              </div>
              <p className="mt-2 text-xs italic text-slate-400">{cf.disclaimer}</p>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
