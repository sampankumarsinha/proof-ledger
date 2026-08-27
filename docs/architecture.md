# Architecture

## Layers
```
React SPA ──HTTPS──▶ FastAPI (/api/v1)
                     ├─ auth (JWT Bearer, bcrypt, RBAC, multi-tenant)
                     ├─ analyst  → planner → tool registry → engine
                     ├─ engine (deterministic calculations, integer paise)
                     ├─ reconciliation (deterministic matching)
                     ├─ autopsy / scenarios / evaluation
                     ├─ evidence (claims + confidence)
                     └─ observability middleware (request id, latency, structured logs)
                             │
                          MongoDB (multi-tenant, indexed)
```

## Request lifecycle (AI ask)
1. `POST /api/v1/ai/ask` with a natural-language question.
2. **Deterministic planner** classifies intent (keyword rules) and selects approved tools.
3. Tools call the **FinancialEngine**, which reads source records and computes values in **integer paise**.
4. Each result is a structured **fact**: `{ metric, value, formula, period, source_records, verification_status }`.
5. **Evidence engine** builds claims and computes **explainable confidence** from concrete signals.
6. Optional **LLM** writes prose (summary/recommendations/next questions) around figures it is given; authoritative numbers are always rendered from facts.
7. The interaction is written to the **audit trail**.

## Money
All amounts are integer paise. Rupee floats are for display only. This removes floating-point drift so figures reconcile exactly.

## Multi-tenancy
Every document carries `organization_id`; every query is scoped to the caller's org. RBAC levels: VIEWER < ANALYST < ADMIN < OWNER, enforced server-side via a dependency.

## Collections & indexes
`users, organizations, customers, products, orders, payments, refunds, settlements, invoices, investigations, decisions, scenarios, evaluation_results, audit_logs, data_imports`. Compound indexes on `(organization_id, created_at)`, `(organization_id, order_id)`, `(organization_id, settlement_id)`, etc.
