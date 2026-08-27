# ProofLedger

**AI that doesn't guess about your money.**

ProofLedger is an evidence-backed AI financial intelligence and investigation platform for merchants and finance teams. Its core principle: **AI reasoning is separated from financial truth.** Financial facts are computed deterministically from the database; the LLM only classifies intent, selects approved tools, and explains verified facts. Every material conclusion traces to source records.

```
USER → AI QUERY PLANNER → APPROVED FINANCIAL TOOLS → DATABASE
     → DETERMINISTIC CALCULATIONS → VERIFIED FACTS → EVIDENCE ENGINE
     → CLAIM VERIFICATION → AI EXPLANATION → AUDITABLE ANSWER
```

## Problem
Finance teams can't trust "AI numbers." An LLM that invents a revenue figure is worse than useless. But raw dashboards can't investigate *why* cash moved.

## Solution
ProofLedger computes the numbers itself (deterministic engine over the database), proves them (evidence engine + claim verification), and only then uses AI to plan the investigation and explain the verified facts — with every figure traceable to transactions.

## Trust model (non-negotiable)
The LLM **cannot** invent amounts, transactions, IDs, customer data, totals, or evidence, and cannot claim causation without support. It **may** classify intent, choose tools, summarize/explain verified facts, and suggest next questions. The authoritative numbers shown in any AI answer are always rendered from structured backend facts — never parsed from LLM text. If no OpenAI key is configured, a deterministic explainer is used and all findings/numbers remain fully functional.

## Tech stack
- **Frontend:** React, React Router, TanStack Query, Tailwind, shadcn/ui, Recharts, Lucide
- **Backend:** FastAPI, Pydantic, Motor (async MongoDB), JWT (bcrypt), pytest
- **Database:** MongoDB (integer-paise money, compound indexes, multi-tenant by `organization_id`)
- **AI:** OpenAI (structured outputs) via a pluggable LLM abstraction layer
- **Integration:** Razorpay adapter (test mode + webhook signature verification), CSV import

> This repository targets the **React + FastAPI + MongoDB** runtime. The financial engine, tool system, evidence model, and trust architecture are stack-agnostic and map 1:1 to the originally-specified Postgres/Redis design.

## Modules
Control Tower · AI Financial Analyst · Financial Autopsy · Evidence Explorer & Graph · Reconciliation Center · Settlement Intelligence · Receivables Intelligence · Refund Intelligence · Investigation Workspace · Scenario Simulator · Counterfactual Analysis · Decision Center · Evaluation Lab · Audit Trail · Data Explorer · Razorpay Integration · Data Import · Reports/Export.

## Razorpay integration (TEST mode)
Add `RAZORPAY_KEY_ID` + `RAZORPAY_KEY_SECRET` (and optional `RAZORPAY_WEBHOOK_SECRET`) to `backend/.env` — server-side only, never exposed to React. Then in **Settings → Razorpay integration**: **Test connection**, **Sync now (initial)**, then **Incremental sync** for subsequent runs. The adapter paginates orders/payments/refunds/settlements, normalizes them into the same ProofLedger models with `source=RAZORPAY_TEST` and `external_id=<razorpay id>`, and is idempotent (re-syncing updates, never duplicates). A **data-source toggle** (Settings) switches every module between **DEMO DATA** and **RAZORPAY TEST** — the same FinancialEngine / ReconciliationEngine / EvidenceEngine run on both; datasets are never mixed. Webhooks are verified via the SDK's `verify_webhook_signature`. Without credentials the app stays in clearly-labelled **DEMO DATA** mode and never claims live data.

> Note: Razorpay TEST accounts usually have **no settlements** unless payouts were simulated, so `cash_received` may be small/zero on live test data — the demo dataset tells the richer delayed-settlement story.

## Anomaly baselines & Attention center
Overview shows transparent rolling baselines (current vs prior period) for payment volume, refund rate, settlement cash and fees with **NORMAL / ELEVATED / UNUSUAL** status (fixed thresholds, `GET /analytics/baselines`), and an Attention center (`GET /analytics/attention`) listing pending settlements, reconciliation exceptions, refund spikes, fee discrepancies and unusual movements — each with reason, amount, severity, evidence and a recommended action. Nothing is called fraud without evidence.

## Deployment Setup
No external runtime locks or proprietary server requirements.
- **Frontend**: `cd frontend && yarn build` → deploy the static `build/` (Vercel/Netlify/S3). Set `REACT_APP_BACKEND_URL` to the backend URL.
- **Backend**: `uvicorn server:app --host 0.0.0.0 --port 8001` on Render/Railway/Fly. Set env vars below.
- **Database**: MongoDB Atlas — put the connection string in `MONGODB_URI` (or `MONGO_URL`).
- **Docker**: `docker compose up --build` runs frontend + backend + mongo + redis.

Required environment variables: `MONGODB_URI`, `JWT_SECRET`, `OPENAI_API_KEY`, `OPENAI_MODEL`, `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET` (+ optional `RAZORPAY_WEBHOOK_SECRET`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`).

## Local setup
```bash
# Backend
cd backend
pip install -r requirements.txt
cp .env.example .env            # set MONGO_URL, JWT_SECRET, (optional) OPENAI_API_KEY / RAZORPAY_*
uvicorn server:app --host 0.0.0.0 --port 8001

# Frontend
cd frontend
yarn install
cp .env.example .env            # set REACT_APP_BACKEND_URL
yarn start
```
Demo data (coherent financial stories) is seeded automatically on first backend startup.

## Docker
```bash
docker compose up --build
# frontend :3000  backend :8001  mongo :27017  redis :6379
```

## Environment variables
| Var | Where | Purpose |
|-----|-------|---------|
| `MONGO_URL`, `DB_NAME` | backend | Database |
| `JWT_SECRET` | backend | Token signing |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | backend | Seeded owner account |
| `OPENAI_API_KEY`, `OPENAI_MODEL` | backend | Optional AI explainer (your own key) |
| `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET` | backend | Optional Razorpay **test** integration |
| `REACT_APP_BACKEND_URL` | frontend | API base |

Secrets are server-side only and never exposed to the client.

## Demo credentials
| Role | Email | Password |
|------|-------|----------|
| OWNER | cfo@proofledger.com | Demo123! |
| ADMIN | admin@proofledger.com | Demo123! |
| ANALYST | analyst@proofledger.com | Demo123! |
| VIEWER | viewer@proofledger.com | Demo123! |

## Demo (3–5 min)
1. Open **Control Tower** — cash received is down vs prior period.
2. Ask the **AI Analyst**: *"Why did cash decrease this month?"*
3. Watch tool execution → verified findings ranked by impact (settlement timing, refunds, receivables…).
4. Click **Show Proof** on a contributor → formula → source transactions.
5. Open **Reconciliation** → inspect an exception (missing/partial/duplicate/fee difference).
6. Review **Settlements / Refunds / Receivables** intelligence, save an **Investigation**, and check the **Audit** trail.
7. **Evaluation Lab** → run the benchmark and see measured accuracy against independently-computed ground truth.

## Razorpay integration
Provide `RAZORPAY_KEY_ID/SECRET` (test mode) to switch the environment badge to **RAZORPAY TEST** and enable a live connection check. Without credentials, the app runs in clearly-labelled **DEMO DATA** mode and never claims live data. Webhooks are verified via HMAC-SHA256 using `RAZORPAY_WEBHOOK_SECRET`.

## Testing
```bash
cd backend && pytest -q          # calculation / evidence / intent unit tests
cd frontend && yarn build        # typecheck + production build
```

