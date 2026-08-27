# ProofLedger

> **AI that doesn't guess about your money.**

ProofLedger is an evidence-backed AI financial intelligence and investigation platform for merchants and finance teams. Its core principle: **AI reasoning is separated from financial truth.** Financial facts are computed deterministically from the database; the LLM only classifies intent, selects approved tools, and explains verified facts. Every material conclusion traces directly to source records.

```
┌───────────────────────────────┐
│             USER              │
│      Financial Question       │
└───────────────┬───────────────┘
                │
                ▼
┌───────────────────────────────┐
│       AI QUERY PLANNER        │
│  Understand intent & context  │
└───────────────┬───────────────┘
                │
                ▼
┌───────────────────────────────┐
│     APPROVED FINANCIAL        │
│           TOOLS               │
│  No arbitrary DB/SQL queries  │
└───────────────┬───────────────┘
                │
                ▼
┌───────────────────────────────┐
│           DATABASE            │
│        MongoDB Records        │
│ Payments • Refunds • Fees     │
│ Settlements • Receivables     │
└───────────────┬───────────────┘
                │
                ▼
┌───────────────────────────────┐
│   DETERMINISTIC CALCULATIONS  │
│       Financial Engine        │
│       Integer Paise Math      │
└───────────────┬───────────────┘
                │
                ▼
┌───────────────────────────────┐
│       VERIFIED FINANCIAL      │
│            FACTS              │
│  Amounts • Changes • Metrics  │
└───────────────┬───────────────┘
                │
                ▼
┌───────────────────────────────┐
│       EVIDENCE ENGINE         │
│  Calculations → Transactions  │
└───────────────┬───────────────┘
                │
                ▼
┌───────────────────────────────┐
│       CLAIM VERIFICATION      │
│  Fact vs inference vs claim   │
└───────────────┬───────────────┘
                │
                ▼
┌───────────────────────────────┐
│       AI EXPLANATION          │
│   Explain verified results    │
│       without guessing        │
└───────────────┬───────────────┘
                │
                ▼
┌───────────────────────────────┐
│       AUDITABLE ANSWER        │
│  Answer + Calculation + Proof │
│       + Source Records        │
└───────────────────────────────┘
```

---

## Key Features & Overview

### 1. Problem & Solution
* **Problem:** Finance teams cannot trust "AI numbers." An LLM that invents or hallucinates financial figures is dangerous. However, raw static dashboards cannot investigate *why* cash moved.
* **Solution:** ProofLedger computes all figures deterministically via an in-database financial engine, verifies them against source records, and only then uses AI to orchestrate the investigation and explain the verified findings.

### 2. Non-Negotiable Trust Model
The LLM **cannot** invent amounts, transactions, IDs, customer data, totals, or evidence, and cannot claim causation without underlying data support. It **may** classify intent, select authorized tools, summarize verified facts, and suggest next investigation steps. If no OpenAI API key is configured, a deterministic rule-based explainer is used, ensuring 100% functionality without LLM dependencies.

---

## Architecture & Tech Stack

* **Frontend:** React 19, React Router v7, TanStack Query, Tailwind CSS, shadcn/ui, Recharts, Lucide Icons
* **Backend:** FastAPI, Pydantic, Motor (Async MongoDB Driver), Pytest, JWT Authentication
* **Database:** MongoDB (integer-paise precision money calculations, compound indexes, multi-tenant by `organization_id`)
* **AI Engine:** OpenAI (structured outputs) via a pluggable LLM abstraction layer
* **Integrations:** Razorpay Adapter (Test mode & webhook signature verification), CSV Data Importer

---

## Core Platform Modules

* **Control Tower:** Key performance indicators and executive metric overview
* **AI Financial Analyst:** Natural language investigation powered by deterministic tools
* **Financial Autopsy:** Root-cause analysis of cash drops and revenue changes
* **Evidence Explorer & Graph:** Visual trace from high-level metrics down to raw ledger entries
* **Reconciliation Center:** Automated classification of payment vs settlement discrepancies
* **Settlement Intelligence:** Delayed payout tracking, rolling reserves, and fee analysis
* **Receivables & Refund Intelligence:** Aging analysis, risk scoring, and return reason trends
* **Investigation Workspace & Decision Center:** Collaborative decision tracking and scenario simulations
* **Evaluation Lab & Audit Trail:** Quantitative accuracy benchmark and full system change logs

---

## Integrations & Features

### Razorpay Integration (Test Mode)
Add `RAZORPAY_KEY_ID` and `RAZORPAY_KEY_SECRET` to `backend/.env`. In **Settings → Razorpay integration**, test the connection and run initial or incremental syncs. The adapter paginates orders, payments, refunds, and settlements into standardized ProofLedger models. A data-source toggle switches the entire UI between **DEMO DATA** and **RAZORPAY TEST** safely without mixing datasets.

### Anomaly Baselines & Attention Center
The Overview module computes rolling baselines (current vs prior period) for payment volume, refund rate, settlement cash, and fees with **NORMAL / ELEVATED / UNUSUAL** status flags. The Attention Center prioritizes pending settlements, reconciliation exceptions, refund spikes, and fee discrepancies with recommended actions and evidence links.

---



## Quick Start & Local Setup

### 1. Manual Setup

```bash
# 1. Backend Setup
cd backend
pip install -r requirements.txt
cp .env.example .env            
uvicorn server:app --host 0.0.0.0 --port 8001 --reload

# 2. Frontend Setup (in a new terminal tab)
cd frontend
npm install                     
cp .env.example .env            
npm start                       
```

### 2. Docker Compose Setup

```bash
# Build and launch all services (Frontend :3000, Backend :8001, Mongo :27017)
docker compose up --build
```

---

## Demo Credentials & Guided Walkthrough

### Credentials
| Role | Email | Password |
|------|-------|----------|
| **OWNER** | `cfo@proofledger.com` | `Demo123!` |
| **ADMIN** | `admin@proofledger.com` | `Demo123!` |
| **ANALYST** | `analyst@proofledger.com` | `Demo123!` |
| **VIEWER** | `viewer@proofledger.com` | `Demo123!` |

### 5-Minute Guided Demo Flow
1. Open **Control Tower** — observe cash received status vs prior period.
2. Ask the **AI Analyst**: *"Why did cash decrease this month?"*
3. Watch the tool execution workflow produce verified findings ranked by impact.
4. Click **Show Proof** on any contributor to inspect formula lineage down to source transactions.
5. Navigate to **Reconciliation Center** to review exceptions and fee discrepancies.
6. Explore **Settlements**, **Refunds**, and **Receivables** intelligence, save an **Investigation**, and check the **Audit Trail**.

---

