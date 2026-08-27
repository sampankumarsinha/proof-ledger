import { useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import {
  LayoutDashboard, Sparkles, Stethoscope, TrendingUp, CreditCard, Banknote,
  RotateCcw, Receipt, GitCompareArrows, FolderSearch, SlidersHorizontal,
  Gavel, ShieldCheck, FlaskConical, ScrollText, Database, Settings, LogOut, Menu, X,
} from "lucide-react";

const NAV = [
  { to: "/", label: "Overview", icon: LayoutDashboard, end: true },
  { to: "/analyst", label: "AI Analyst", icon: Sparkles },
  { to: "/autopsy", label: "Financial Autopsy", icon: Stethoscope },
  { to: "/cashflow", label: "Cash Flow", icon: TrendingUp },
  { to: "/payments", label: "Payments", icon: CreditCard },
  { to: "/settlements", label: "Settlements", icon: Banknote },
  { to: "/refunds", label: "Refunds", icon: RotateCcw },
  { to: "/receivables", label: "Receivables", icon: Receipt },
  { to: "/reconciliation", label: "Reconciliation", icon: GitCompareArrows },
  { to: "/investigations", label: "Investigations", icon: FolderSearch },
  { to: "/scenarios", label: "Scenarios", icon: SlidersHorizontal },
  { to: "/decisions", label: "Decisions", icon: Gavel },
  { to: "/evidence", label: "Evidence", icon: ShieldCheck },
  { to: "/evaluation", label: "Evaluation", icon: FlaskConical },
  { to: "/audit", label: "Audit", icon: ScrollText },
  { to: "/data", label: "Data", icon: Database },
  { to: "/settings", label: "Settings", icon: Settings },
];

export default function Layout({ children, env = "DEMO_DATA" }) {
  const { user, logout } = useAuth();
  const loc = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);
  const current = NAV.find((n) => (n.end ? loc.pathname === n.to : loc.pathname.startsWith(n.to) && n.to !== "/")) || NAV[0];

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      {mobileOpen && <div className="fixed inset-0 z-30 bg-black/40 md:hidden" onClick={() => setMobileOpen(false)} />}
      {/* Sidebar */}
      <aside className={`fixed inset-y-0 left-0 z-40 flex w-60 flex-shrink-0 transform flex-col bg-navy text-slate-100 transition-transform md:static md:translate-x-0 ${mobileOpen ? "translate-x-0" : "-translate-x-full"}`}>
        <div className="flex items-center justify-between px-5 py-5">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-sm bg-primary font-display text-lg font-extrabold text-white">P</div>
            <div>
              <div className="font-display text-lg font-bold leading-none tracking-tight">ProofLedger</div>
              <div className="text-[10px] uppercase tracking-[0.2em] text-slate-400">Finance Controller</div>
            </div>
          </div>
          <button onClick={() => setMobileOpen(false)} className="text-slate-400 md:hidden"><X className="h-5 w-5" /></button>
        </div>
        <div className="px-5 pb-3">
          <span
            data-testid="env-badge"
            className={`inline-flex items-center gap-1.5 rounded-sm border px-2 py-1 text-[10px] font-semibold uppercase tracking-wider ${
              env === "RAZORPAY_TEST"
                ? "border-sky-500/40 bg-sky-500/10 text-sky-300"
                : "border-amber-500/40 bg-amber-500/10 text-amber-300"
            }`}
          >
            <span className="h-1.5 w-1.5 rounded-full bg-current" />
            {env === "RAZORPAY_TEST" ? "Razorpay Test" : "Demo Data"}
          </span>
        </div>
        <nav className="flex-1 space-y-0.5 overflow-y-auto px-3 pb-4">
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.end}
              onClick={() => setMobileOpen(false)}
              data-testid={`nav-${n.label.toLowerCase().replace(/\s+/g, "-")}`}
              className={({ isActive }) =>
                `nav-item flex items-center gap-3 rounded-sm px-3 py-2 text-sm ${
                  isActive ? "bg-primary/90 font-medium text-white" : "text-slate-300 hover:bg-white/5 hover:text-white"
                }`
              }
            >
              <n.icon className="h-4 w-4" />
              {n.label}
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-white/10 px-4 py-3">
          <div className="flex items-center gap-2">
            <img
              src="https://images.unsplash.com/photo-1701096374092-bb70915fdc5c?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjA3MDR8MHwxfHNlYXJjaHwzfHxwcm9mZXNzaW9uYWwlMjBjb3Jwb3JhdGUlMjBoZWFkc2hvdHxlbnwwfHx8fDE3ODc2NTk4NjZ8MA&ixlib=rb-4.1.0&q=85&w=64&h=64&fit=crop"
              alt="user"
              className="h-8 w-8 rounded-sm object-cover"
            />
            <div className="min-w-0 flex-1">
              <div className="truncate text-sm font-medium text-white">{user?.name}</div>
              <div className="truncate text-[11px] text-slate-400">{user?.role}</div>
            </div>
            <button onClick={logout} data-testid="logout-btn" className="rounded-sm p-1.5 text-slate-400 hover:bg-white/10 hover:text-white">
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        </div>
      </aside>

      {/* Main */}
      <div className="flex flex-1 flex-col overflow-hidden">
        <header className="flex items-center justify-between border-b bg-white/90 px-4 py-4 backdrop-blur-xl md:px-8">
          <div className="flex items-center gap-3">
            <button onClick={() => setMobileOpen(true)} className="text-slate-500 md:hidden" data-testid="mobile-menu-btn"><Menu className="h-5 w-5" /></button>
            <h1 className="font-display text-xl font-medium tracking-tight text-slate-900">{current.label}</h1>
          </div>
          <div className="hidden text-xs text-slate-400 sm:block">
            {user?.email} · <span className="font-medium text-slate-600">Meridian Commerce</span>
          </div>
        </header>
        <main className="flex-1 overflow-y-auto px-4 py-5 md:px-8 md:py-6">{children}</main>
      </div>
    </div>
  );
}
