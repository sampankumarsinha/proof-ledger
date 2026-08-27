// display helpers — numbers themselves always come from the backend
export function inr(display) {
  return display ?? "—";
}

export function pctStr(v) {
  if (v == null) return "—";
  const sign = v > 0 ? "+" : "";
  return `${sign}${v}%`;
}

export function classColor(cls) {
  const map = {
    MATCHED: "text-fact bg-emerald-50 border-emerald-200",
    PARTIAL: "text-inference bg-amber-50 border-amber-200",
    FEE_DIFFERENCE: "text-inference bg-amber-50 border-amber-200",
    TIMING_DIFFERENCE: "text-sky-700 bg-sky-50 border-sky-200",
    DUPLICATE: "text-alert bg-red-50 border-red-200",
    MISSING_PAYMENT: "text-alert bg-red-50 border-red-200",
    MISSING_SETTLEMENT: "text-alert bg-red-50 border-red-200",
    REFUND_ADJUSTMENT: "text-violet-700 bg-violet-50 border-violet-200",
    UNEXPLAINED: "text-alert bg-red-50 border-red-200",
  };
  return map[cls] || "text-slate-600 bg-slate-50 border-slate-200";
}

export function factColor(type) {
  const t = (type || "").toUpperCase();
  if (t.includes("VERIFIED")) return "text-fact bg-emerald-50 border-emerald-200";
  if (t.includes("DERIVED")) return "text-sky-700 bg-sky-50 border-sky-200";
  if (t.includes("INFERENCE") || t.includes("CORRELATION")) return "text-inference bg-amber-50 border-amber-200";
  if (t.includes("RECOMMEND")) return "text-violet-700 bg-violet-50 border-violet-200";
  if (t.includes("INSUFFICIENT")) return "text-alert bg-red-50 border-red-200";
  return "text-slate-600 bg-slate-50 border-slate-200";
}

export function riskColor(risk) {
  const map = {
    HIGH: "text-alert bg-red-50 border-red-200",
    MEDIUM: "text-inference bg-amber-50 border-amber-200",
    LOW: "text-sky-700 bg-sky-50 border-sky-200",
    CURRENT: "text-fact bg-emerald-50 border-emerald-200",
  };
  return map[risk] || "text-slate-600 bg-slate-50 border-slate-200";
}
