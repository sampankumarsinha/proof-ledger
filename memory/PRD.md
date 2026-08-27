# ProofLedger — PRD

## Original problem statement
Build a production-quality, evidence-backed AI financial intelligence & investigation platform ("ProofLedger — AI that doesn't guess about your money"). Core principle: **AI reasoning is separated from financial truth.** All numbers are computed deterministically from source records; the LLM only classifies intent, selects approved tools, and explains verified facts. Every conclusion traces to transactions.

## Stack (as built)
React + FastAPI + MongoDB (adapted from the requested Next.js/Postgres/Redis; engine & trust model are stack-agnostic). JWT Bearer auth, bcrypt, RBAC, multi-tenant. Optional OpenAI (user key) via an LLM abstraction with deterministic fallback. Razorpay adapter (test mode + webhook HMAC) with DEMO DATA mode. Recharts, TanStack Query, shadcn/ui, Tailwind, Lucide.

## Architecture
question → deterministic planner → typed tool registry → FinancialEngine (integer paise) → verified facts → evidence engine (claims + explainable confidence) → optional LLM prose → audit trail. LLM cannot produce authoritative numbers (rendered from facts, not parsed from text).

## User personas
- **CFO / Owner** — control tower, decisions, reports.
- **Finance Controller / Analyst** — investigations, reconciliation, scenarios.
- **Viewer** — read-only dashboards and evidence.

## Core requirements (static)
Deterministic financial engine; evidence + claim verification; reconciliation; multi-tenant isolation; RBAC (OWNER/ADMIN/ANALYST/VIEWER); auditable answers; demo mode that never claims live data.

## Implemented (2026-06)
- Auth (JWT Bearer, bcrypt, brute-force lockout), 4 seeded roles, multi-tenant.
- Deterministic engine: gross/net revenue, cash received, fees, refunds, refund rate, pending settlements, receivables (outstanding/overdue/aging), unreconciled, payment counts, avg value, period comparison.
- Typed tool registry (no arbitrary queries); AI Analyst with intent planner + LLM/deterministic explainer.
- Financial Autopsy (ranked contributors, Show Proof), Evidence Engine (claims + confidence), Evidence Graph.
- Reconciliation (9 classes, 98.3% match, real exceptions isolated from explained refund adjustments).
- Settlement / Receivables / Refund intelligence.
- Investigation workspace (create/decide/export JSON+CSV), Scenario Simulator, Counterfactuals, Decision Center.
- Evaluation Lab (independent ground truth, live 100%/10 benchmark), Audit trail, Data Explorer, CSV import, Razorpay status/webhook.
- Coherent seed stories: delayed/partial/missing settlement, refund spike, overdue receivables, fee discrepancy, duplicate payment, timing difference.
- Premium fintech UI (navy sidebar, cobalt accent, Cabinet Grotesk + IBM Plex, dense tables, evidence drawer, confidence indicator), mobile-responsive.
- Repo: README, LICENSE, .env.example, .gitignore, docker-compose, Dockerfiles, GitHub Actions CI, docs/{architecture,ai-trust-model,evaluation,security,api}.md.
- Tests: 65 backend pytest passing; frontend build passing; testing agent 56/56 backend + full frontend e2e verified.

## Backlog / remaining
- **P2/P3:** live Razorpay incremental sync + historical backfill; PDF report rendering; force-directed evidence graph.
- **P4:** scheduled digests/alerts, anomaly baselines, notifications, shared usePermissions hook refactor.

## Next tasks
1. Live Razorpay test sync when credentials provided.
2. PDF export for investigations.
3. Scheduled email digests of attention items.
