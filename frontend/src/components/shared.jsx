import { Loader2 } from "lucide-react";
import { factColor, classColor, riskColor } from "@/lib/format";

export function Chip({ type, children, className = "" }) {
  return (
    <span className={`inline-flex items-center gap-1 rounded-sm border px-2 py-0.5 text-[11px] font-medium uppercase tracking-wide ${factColor(type)} ${className}`}>
      {children || type}
    </span>
  );
}

export function ClassBadge({ cls }) {
  return (
    <span className={`inline-flex items-center rounded-sm border px-2 py-0.5 text-[11px] font-medium tracking-wide ${classColor(cls)}`}>
      {cls.replace(/_/g, " ")}
    </span>
  );
}

export function RiskBadge({ risk }) {
  return (
    <span className={`inline-flex items-center rounded-sm border px-2 py-0.5 text-[11px] font-semibold tracking-wide ${riskColor(risk)}`}>
      {risk}
    </span>
  );
}

export function ConfidenceBar({ confidence }) {
  if (!confidence) return null;
  const seg = 5;
  const filled = Math.round(confidence.score * seg);
  const color = confidence.band === "HIGH" ? "bg-fact" : confidence.band === "MEDIUM" ? "bg-inference" : "bg-alert";
  return (
    <div className="flex items-center gap-2" data-testid="confidence-indicator">
      <div className="flex gap-0.5">
        {Array.from({ length: seg }).map((_, i) => (
          <div key={i} className={`h-2 w-4 rounded-[1px] ${i < filled ? color : "bg-slate-200"}`} />
        ))}
      </div>
      <span className="text-xs font-semibold text-slate-700">{confidence.band}</span>
      <span className="tabular text-xs text-slate-400">{Math.round(confidence.score * 100)}%</span>
    </div>
  );
}

export function SectionTitle({ label, children, right }) {
  return (
    <div className="mb-4 flex items-end justify-between">
      <div>
        <div className="text-[11px] font-semibold uppercase tracking-[0.15em] text-slate-400">{label}</div>
        {children && <h2 className="font-display text-2xl tracking-tight text-slate-900">{children}</h2>}
      </div>
      {right}
    </div>
  );
}

export function Spinner({ label = "Loading" }) {
  return (
    <div className="flex items-center gap-2 py-16 text-slate-400">
      <Loader2 className="h-4 w-4 animate-spin" />
      <span className="text-sm">{label}…</span>
    </div>
  );
}

export function Empty({ children }) {
  return <div className="py-12 text-center text-sm text-slate-400">{children}</div>;
}

export function Card({ children, className = "", ...rest }) {
  return (
    <div className={`rounded-sm border bg-card ${className}`} {...rest}>
      {children}
    </div>
  );
}
