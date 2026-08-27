import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useEvidence } from "@/components/EvidenceDrawer";
import { Spinner, Card, SectionTitle, Chip } from "@/components/shared";
import { FileSearch } from "lucide-react";

const proofMetric = (m) =>
  m === "settlement_timing" ? "pending_settlements"
  : m === "processing_fees" ? "fee_total"
  : m === "receivables" ? "receivables_outstanding"
  : m;

export default function Autopsy() {
  const { open } = useEvidence();
  const { data, isLoading } = useQuery({ queryKey: ["autopsy"], queryFn: async () => (await api.get("/autopsy/cash")).data });
  if (isLoading) return <Spinner label="Running financial autopsy" />;

  const t = data.target;
  const max = Math.max(...data.contributors.map((c) => c.abs_impact), 1);

  return (
    <div className="space-y-6 pl-fade" data-testid="financial-autopsy">
      <Card className="p-6">
        <div className="text-[11px] uppercase tracking-widest text-slate-400">Target metric · Cash received</div>
        <div className="mt-1 flex items-baseline gap-4">
          <span className="tabular text-3xl font-bold text-slate-900">{t.current.value_display}</span>
          <span className={`tabular text-lg font-semibold ${t.delta < 0 ? "text-alert" : "text-fact"}`}>
            {t.delta_display} ({t.change_pct}%)
          </span>
          <span className="text-sm text-slate-400">vs prior {t.prior.value_display}</span>
        </div>
      </Card>

      <Card className="p-6">
        <SectionTitle label="Deterministic decomposition" right={<Chip type="INFERENCE">Observed movements</Chip>}>Ranked contributors</SectionTitle>
        <p className="mb-4 text-xs text-slate-400">{data.interpretation}</p>
        <div className="space-y-3" data-testid="autopsy-contributors">
          {data.contributors.map((c, i) => (
            <div key={i} className="grid grid-cols-12 items-center gap-3">
              <div className="col-span-3 text-sm font-medium capitalize text-slate-800">{c.metric.replace(/_/g, " ")}</div>
              <div className="col-span-6">
                <div className="h-6 w-full rounded-sm bg-slate-100">
                  <div className={`h-6 rounded-sm ${c.impact < 0 ? "bg-alert/80" : "bg-fact/80"}`}
                    style={{ width: `${(c.abs_impact / max) * 100}%` }} />
                </div>
              </div>
              <div className={`col-span-2 tabular text-right text-sm font-semibold ${c.impact < 0 ? "text-alert" : "text-fact"}`}>{c.impact_display}</div>
              <div className="col-span-1 text-right">
                <button onClick={() => open(proofMetric(c.metric), c.metric.replace(/_/g, " "))}
                  data-testid={`autopsy-proof-${c.metric}`}
                  className="rounded-sm border border-primary/40 p-1.5 text-primary hover:bg-accent" title="Show proof">
                  <FileSearch className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
