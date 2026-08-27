import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Spinner, Card, SectionTitle } from "@/components/shared";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

const COLLECTIONS = ["payments", "refunds", "settlements", "invoices", "orders", "customers", "products"];
const HIDE = new Set(["organization_id", "deleted_at", "_id", "product_id", "customer_id", "order_id", "settlement_id"]);

export default function DataExplorer({ only }) {
  const [coll, setColl] = useState(only || "payments");
  const [page, setPage] = useState(1);
  const [sel, setSel] = useState(null);

  const { data, isLoading } = useQuery({
    queryKey: ["data", coll, page],
    queryFn: async () => (await api.get(`/data/${coll}?page=${page}&size=25`)).data,
  });

  const cols = data?.records?.[0]
    ? Object.keys(data.records[0]).filter((k) => !HIDE.has(k) && !k.endsWith("_paise"))
    : [];

  return (
    <div className="space-y-5 pl-fade" data-testid="data-explorer">
      {!only && (
        <div className="flex flex-wrap gap-1">
          {COLLECTIONS.map((c) => (
            <button key={c} onClick={() => { setColl(c); setPage(1); }}
              data-testid={`data-tab-${c}`}
              className={`rounded-sm border px-3 py-1.5 text-sm capitalize ${coll === c ? "border-primary bg-accent text-primary" : "text-slate-500 hover:text-slate-800"}`}>
              {c}
            </button>
          ))}
        </div>
      )}

      <Card className="p-5">
        <SectionTitle label={`${coll} · ${data?.total ?? 0} records`} />
        {isLoading ? <Spinner /> : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-[11px] uppercase tracking-wider text-slate-400">
                  {cols.map((c) => <th key={c} className={`px-3 py-2 ${c.includes("display") ? "text-right" : "text-left"}`}>{c.replace("_display", "").replace(/_/g, " ")}</th>)}
                </tr>
              </thead>
              <tbody>
                {data.records.map((r) => (
                  <tr key={r.id} onClick={() => setSel(r)} className="row-hover cursor-pointer border-b" data-testid="data-row">
                    {cols.map((c) => (
                      <td key={c} className={`px-3 py-2 ${c.includes("display") ? "tabular text-right font-medium" : "text-slate-600"} ${c === "external_id" ? "font-mono text-xs" : ""}`}>
                        {String(r[c] ?? "—").slice(0, 40)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <div className="mt-4 flex items-center justify-between">
          <span className="text-xs text-slate-400">Page {page} · {data?.size} per page</span>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" className="rounded-sm" disabled={page === 1} onClick={() => setPage((p) => p - 1)}>Prev</Button>
            <Button variant="outline" size="sm" className="rounded-sm" disabled={data && page * data.size >= data.total} onClick={() => setPage((p) => p + 1)}>Next</Button>
          </div>
        </div>
      </Card>

      <Dialog open={!!sel} onOpenChange={(o) => !o && setSel(null)}>
        <DialogContent className="max-w-lg rounded-sm">
          <DialogHeader><DialogTitle className="font-display">Record detail</DialogTitle></DialogHeader>
          {sel && (
            <div className="max-h-[60vh] overflow-y-auto rounded-sm border bg-slate-50 p-4">
              <pre className="whitespace-pre-wrap font-mono text-xs text-slate-700">{JSON.stringify(sel, null, 2)}</pre>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
