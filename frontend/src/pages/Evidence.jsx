import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useEvidence } from "@/components/EvidenceDrawer";
import { Spinner, Card, SectionTitle } from "@/components/shared";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { User, ShoppingCart, CreditCard, Banknote, RotateCcw, ArrowRight } from "lucide-react";

const TYPE_META = {
  customer: { icon: User, coll: "customers", color: "text-navy" },
  order: { icon: ShoppingCart, coll: "orders", color: "text-slate-700" },
  payment: { icon: CreditCard, coll: "payments", color: "text-primary" },
  settlement: { icon: Banknote, coll: "settlements", color: "text-fact" },
  refund: { icon: RotateCcw, coll: "refunds", color: "text-alert" },
};
const COLUMNS = ["customer", "order", "payment", "settlement", "refund"];
const METRICS = [
  ["gross_revenue", "Gross Revenue"], ["net_revenue", "Net Revenue"], ["cash_received", "Cash Received"],
  ["pending_settlements", "Pending Settlements"], ["refunds", "Refunds"], ["fee_total", "Fees + GST"],
  ["receivables_outstanding", "Receivables"], ["overdue_receivables", "Overdue"], ["unreconciled_amount", "Unreconciled"],
];

export default function Evidence() {
  const { open } = useEvidence();
  const [custId, setCustId] = useState(null);
  const [sel, setSel] = useState(null);

  const { data: custs } = useQuery({ queryKey: ["custlist"], queryFn: async () => (await api.get("/data/customers?size=25")).data });
  const { data: graph, isFetching } = useQuery({
    queryKey: ["graph", custId], enabled: !!custId,
    queryFn: async () => (await api.get(`/evidence/graph/${custId}`)).data,
  });

  const openRecord = async (node) => {
    const coll = TYPE_META[node.type]?.coll;
    if (!coll) return;
    const { data } = await api.get(`/record/${coll}/${node.id}`);
    setSel(data);
  };

  return (
    <div className="space-y-6 pl-fade" data-testid="evidence">
      <Card className="p-5">
        <SectionTitle label="Data lineage">Metric formulas</SectionTitle>
        <div className="grid grid-cols-2 gap-2 md:grid-cols-3 lg:grid-cols-5">
          {METRICS.map(([m, l]) => (
            <button key={m} onClick={() => open(m, l)} data-testid={`evidence-metric-${m}`}
              className="kpi-hover rounded-sm border p-3 text-left">
              <div className="text-sm font-medium text-slate-700">{l}</div>
              <div className="mt-1 flex items-center gap-1 text-xs text-primary">Trace evidence <ArrowRight className="h-3 w-3" /></div>
            </button>
          ))}
        </div>
      </Card>

      <Card className="p-5">
        <SectionTitle label="Evidence graph" right={
          <Select value={custId || ""} onValueChange={setCustId}>
            <SelectTrigger className="w-56 rounded-sm" data-testid="graph-customer-select"><SelectValue placeholder="Select a customer…" /></SelectTrigger>
            <SelectContent>
              {custs?.records?.map((c) => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}
            </SelectContent>
          </Select>
        }>Relationship explorer</SectionTitle>

        {!custId && <div className="py-12 text-center text-sm text-slate-400">Pick a customer to visualise Customer → Order → Payment → Settlement / Refund.</div>}
        {isFetching && <Spinner label="Building graph" />}
        {graph && (
          <div className="grid grid-cols-5 gap-3" data-testid="graph-columns">
            {COLUMNS.map((type) => {
              const Meta = TYPE_META[type];
              const nodes = graph.nodes.filter((n) => n.type === type);
              return (
                <div key={type}>
                  <div className="mb-2 flex items-center gap-1 text-[11px] uppercase tracking-wider text-slate-400">
                    <Meta.icon className="h-3 w-3" /> {type} ({nodes.length})
                  </div>
                  <div className="space-y-1.5">
                    {nodes.slice(0, 30).map((n) => (
                      <button key={n.id} onClick={() => openRecord(n)} data-testid="graph-node"
                        className="w-full rounded-sm border p-2 text-left row-hover">
                        <div className={`font-mono text-[11px] ${Meta.color}`}>{n.label}</div>
                        {n.amount && <div className="tabular text-xs font-medium text-slate-700">{n.amount}</div>}
                        {n.status && <div className="text-[10px] text-slate-400">{n.status}</div>}
                      </button>
                    ))}
                    {nodes.length === 0 && <div className="rounded-sm border border-dashed p-2 text-center text-[11px] text-slate-300">none</div>}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </Card>

      <Dialog open={!!sel} onOpenChange={(o) => !o && setSel(null)}>
        <DialogContent className="max-w-lg rounded-sm">
          <DialogHeader><DialogTitle className="font-display">Record</DialogTitle></DialogHeader>
          {sel && <div className="max-h-[60vh] overflow-y-auto rounded-sm border bg-slate-50 p-4"><pre className="whitespace-pre-wrap font-mono text-xs text-slate-700">{JSON.stringify(sel, null, 2)}</pre></div>}
        </DialogContent>
      </Dialog>
    </div>
  );
}
