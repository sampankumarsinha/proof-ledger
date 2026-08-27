import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { apiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ShieldCheck, ArrowRight } from "lucide-react";

const DEMO = [
  { role: "OWNER", email: "cfo@proofledger.com" },
  { role: "ANALYST", email: "analyst@proofledger.com" },
];

export default function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState("cfo@proofledger.com");
  const [password, setPassword] = useState("Demo123!");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setErr("");
    setBusy(true);
    try {
      await login(email, password);
      nav("/");
    } catch (e2) {
      setErr(apiError(e2.response?.data?.detail) || e2.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="grid min-h-screen grid-cols-1 lg:grid-cols-2">
      {/* left brand panel */}
      <div className="relative hidden flex-col justify-between bg-navy p-12 text-slate-100 lg:flex pl-grid-bg">
        <div className="flex items-center gap-2">
          <div className="flex h-9 w-9 items-center justify-center rounded-sm bg-primary font-display text-xl font-extrabold">P</div>
          <span className="font-display text-xl font-bold tracking-tight">ProofLedger</span>
        </div>
        <div className="max-w-md">
          <h1 className="font-display text-4xl font-bold leading-tight tracking-tight">
            AI that doesn't guess about your money.
          </h1>
          <p className="mt-4 text-sm leading-relaxed text-slate-300">
            Financial facts are computed deterministically from your records. AI only plans the
            investigation and explains verified facts — every conclusion traces to source transactions.
          </p>
          <div className="mt-8 space-y-2 text-sm text-slate-300">
            {["Deterministic financial engine", "Evidence-backed claims", "Full audit trail"].map((f) => (
              <div key={f} className="flex items-center gap-2">
                <ShieldCheck className="h-4 w-4 text-primary" /> {f}
              </div>
            ))}
          </div>
        </div>
        <div className="text-xs text-slate-500">Evidence-backed AI Finance Controller · INR</div>
      </div>

      {/* right form */}
      <div className="flex items-center justify-center bg-background px-6 py-12">
        <form onSubmit={submit} className="w-full max-w-sm" data-testid="login-form">
          <h2 className="font-display text-2xl font-medium tracking-tight text-slate-900">Sign in</h2>
          <p className="mt-1 text-sm text-slate-500">Access your finance control tower.</p>

          <div className="mt-6 space-y-4">
            <div>
              <Label htmlFor="email" className="text-xs uppercase tracking-wide text-slate-500">Email</Label>
              <Input id="email" data-testid="login-email" value={email} onChange={(e) => setEmail(e.target.value)}
                className="mt-1 rounded-sm" required />
            </div>
            <div>
              <Label htmlFor="password" className="text-xs uppercase tracking-wide text-slate-500">Password</Label>
              <Input id="password" data-testid="login-password" type="password" value={password}
                onChange={(e) => setPassword(e.target.value)} className="mt-1 rounded-sm" required />
            </div>
          </div>

          {err && <div data-testid="login-error" className="mt-4 rounded-sm border border-red-200 bg-red-50 px-3 py-2 text-sm text-alert">{err}</div>}

          <Button type="submit" disabled={busy} data-testid="login-submit"
            className="mt-6 w-full rounded-sm bg-primary text-white hover:bg-primary/90">
            {busy ? "Signing in…" : <span className="flex items-center justify-center gap-2">Sign in <ArrowRight className="h-4 w-4" /></span>}
          </Button>

          <div className="mt-6 rounded-sm border bg-white p-3">
            <div className="text-[11px] uppercase tracking-widest text-slate-400">Demo accounts (password: Demo123!)</div>
            <div className="mt-2 space-y-1">
              {DEMO.map((d) => (
                <button key={d.email} type="button" onClick={() => { setEmail(d.email); setPassword("Demo123!"); }}
                  data-testid={`demo-${d.role.toLowerCase()}`}
                  className="row-hover flex w-full items-center justify-between rounded-sm px-2 py-1 text-left text-sm">
                  <span className="text-slate-600">{d.email}</span>
                  <span className="text-[11px] font-semibold text-primary">{d.role}</span>
                </button>
              ))}
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}
