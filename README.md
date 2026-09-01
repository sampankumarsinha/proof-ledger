# ProofLedger

> **AI that doesn't guess about your money.**

ProofLedger is an evidence-backed AI financial intelligence and investigation platform for merchants and finance teams. Its core principle is simple: **AI reasoning is separated from financial truth.** Financial facts are calculated deterministically from the database, while the AI is used to understand questions, select approved tools, and explain verified results. Every material conclusion can be traced back to the underlying source records.

```text
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
│  Controlled access to data    │
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

## Problem

Finance teams have access to more financial data than ever, but having the data is not the same as understanding it.

A dashboard can show that cash decreased, refunds increased, or settlements are delayed. The harder question is usually **why** it happened.

Using a general-purpose LLM directly for financial analysis creates another problem: the model may generate a convincing answer containing numbers or explanations that cannot be verified.

An invented financial figure is worse than no figure at all.

ProofLedger is designed around this gap between **financial data, investigation, and trustworthy explanation.**

---

## Solution

ProofLedger combines a deterministic financial engine with an AI-assisted investigation layer.

The backend calculates financial metrics directly from stored records rather than asking an LLM to perform the accounting.

The system then connects important results to supporting evidence and source transactions.

The AI is used to understand the user's question, select the appropriate financial tools, organize the investigation, and explain the verified results.

This creates a workflow where:

**AI investigates → backend calculates → evidence supports → AI explains.**

The goal is not simply to add a chatbot to a financial dashboard. The goal is to make financial investigation easier while keeping the underlying numbers auditable.

---

## Trust Model

The separation between AI reasoning and financial truth is a core design requirement.

The LLM **cannot**:

- Invent financial amounts
- Invent transaction IDs
- Invent customer records
- Invent totals
- Create fake evidence
- Arbitrarily query the database
- Claim causation without supporting evidence

The LLM **may**:

- Understand user intent
- Select approved financial tools
- Help plan an investigation
- Summarize verified results
- Explain financial findings
- Suggest additional questions

Authoritative financial numbers come from structured backend calculations and are not parsed from generated AI text.

If an OpenAI API key is not configured, the application can fall back to a deterministic explainer while the underlying financial calculations continue to work.

---

## Architecture & Tech Stack

- **Frontend:** React 19, React Router, TanStack Query, Tailwind CSS, shadcn/ui, Recharts, Lucide Icons

- **Backend:** FastAPI, Pydantic, Motor (Async MongoDB Driver), Pytest, JWT Authentication

- **Database:** MongoDB with integer-paise financial representation, compound indexes, and organization-level data separation

- **AI Engine:** OpenAI structured outputs through a pluggable LLM abstraction layer

- **Integrations:** Razorpay adapter for Test Mode, webhook signature verification, and CSV data import

The repository targets a **React + FastAPI + MongoDB** runtime. The financial engine, evidence model, and trust architecture are designed so that the underlying data source can be changed without changing the investigation workflow.

---

## Core Platform Modules

- **Control Tower:** Executive overview of important financial metrics and changes

- **AI Financial Analyst:** Natural-language financial investigation using approved deterministic tools

- **Financial Autopsy:** Investigation of significant cash and revenue movements

- **Evidence Explorer & Graph:** Trace financial findings back to calculations and source records

- **Reconciliation Center:** Identification and classification of payment and settlement discrepancies

- **Settlement Intelligence:** Analysis of settlement timing, pending payouts, and settlement-related fees

- **Receivables Intelligence:** Aging and analysis of outstanding receivables

- **Refund Intelligence:** Refund trends, spikes, and return activity

- **Investigation Workspace:** Save and organize financial investigations and supporting evidence

- **Scenario Simulator & Counterfactual Analysis:** Explore the possible impact of financial changes

- **Decision Center:** Record decisions and actions based on investigation findings

- **Evaluation Lab:** Test calculation accuracy, tool selection, and investigation behavior

- **Audit Trail:** Record important system and investigation activity

- **Data Explorer:** Inspect underlying financial records

- **Razorpay Integration:** Import and synchronize Razorpay Test Mode records

- **Data Import:** Support for structured CSV financial data

- **Reports / Export:** Export investigation and financial information for further review

---

## Razorpay Integration (Test Mode)

ProofLedger can connect to Razorpay Test Mode so that the application can work with actual payment records rather than relying only on synthetic demo data.

Add the Razorpay credentials to the backend environment:

```env
RAZORPAY_KEY_ID=rzp_test_xxxxxxxxx
RAZORPAY_KEY_SECRET=xxxxxxxxxxxxxxxx
RAZORPAY_WEBHOOK_SECRET=xxxxxxxxxxxxxxxx
```

These values must remain server-side and should never be exposed to the React application.

From **Settings → Razorpay Integration**, the user can test the connection and initiate synchronization.

The integration supports:

- Orders
- Payments
- Refunds
- Settlements

The adapter converts Razorpay records into ProofLedger's internal financial models while retaining the external Razorpay transaction reference.

For example, if a test payment of **₹5,000** is created through Razorpay, synchronization can bring that payment into ProofLedger so that it becomes searchable and available to the financial engine.

The flow is:

```text
Razorpay Test Payment
        ↓
Razorpay API
        ↓
ProofLedger Adapter
        ↓
MongoDB
        ↓
Financial Engine
        ↓
Evidence & Investigation
```

The synchronization process is designed to be idempotent, meaning that syncing an existing record should update the corresponding ProofLedger record rather than continuously creating duplicates.

A data-source toggle allows the application to distinguish between:

```text
DEMO DATA
```

and:

```text
RAZORPAY TEST
```

The two datasets are kept separate so that demonstration data is not accidentally mixed with Razorpay records.

> Note: Razorpay Test accounts may not contain realistic settlement activity unless appropriate test settlement scenarios are available. Because of this, settlement-related values can be small or empty when using Razorpay Test data.

---

## Anomaly Baselines & Attention Center

ProofLedger includes transparent baseline comparisons for important financial metrics.

The system can compare current activity with previous periods for:

- Payment volume
- Refund rate
- Settlement cash
- Fees

Results can be categorized as:

```text
NORMAL
ELEVATED
UNUSUAL
```

The thresholds are designed to make the reason for an alert understandable rather than hiding the decision behind an unexplained model score.

The **Attention Center** collects items that may require finance-team review, including:

- Pending settlements
- Reconciliation exceptions
- Refund spikes
- Fee discrepancies
- Unusual movements

Each attention item can include a reason, severity, amount, evidence, and recommended next action.

The system does not automatically label unusual activity as fraud without supporting evidence.

---

## Quick Start & Local Setup

### Prerequisites

Make sure the following are installed:

- Python 3.11+
- Node.js 20+
- npm
- MongoDB or MongoDB Atlas
- Git

---

### 1. Clone the repository

```bash
git clone https://github.com/sampankumarsinha/proof-ledger.git
cd proof-ledger
```

---

### 2. Backend Setup

```bash
cd backend

python -m venv .venv
```

Activate the virtual environment.

#### macOS / Linux

```bash
source .venv/bin/activate
```

#### Windows

```powershell
.venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create the environment file:

```bash
cp .env.example .env
```

Configure the required backend variables inside `.env`.

Start the backend:

```bash
uvicorn server:app --host 0.0.0.0 --port 8001 --reload
```

The backend will be available at:

```text
http://localhost:8001
```

FastAPI documentation is available at:

```text
http://localhost:8001/docs
```

---

### 3. Frontend Setup

Open another terminal:

```bash
cd frontend
```

Install dependencies:

```bash
npm install
```

Create the frontend environment file:

```bash
cp .env.example .env
```

Set:

```env
REACT_APP_BACKEND_URL=http://localhost:8001
```

Start the application:

```bash
npm start
```

The frontend will normally be available at:

```text
http://localhost:3000
```

Demo data is seeded automatically when the backend is initialized according to the repository configuration.

---

## Docker Compose Setup

If Docker Desktop is installed, the complete local stack can be started with:

```bash
docker compose up --build
```

The exact services and ports are defined in:

```text
docker-compose.yml
```

The default configuration includes the application services and supporting infrastructure used by the project.

---

## Environment Variables

Backend:

| Variable | Where | Purpose |
|---|---|---|
| `MONGO_URL` | Backend | MongoDB connection |
| `DB_NAME` | Backend | Database name |
| `JWT_SECRET` | Backend | JWT signing secret |
| `ADMIN_EMAIL` | Backend | Seeded owner account |
| `ADMIN_PASSWORD` | Backend | Seeded owner password |
| `OPENAI_API_KEY` | Backend | Optional AI functionality |
| `OPENAI_MODEL` | Backend | OpenAI model configuration |
| `RAZORPAY_KEY_ID` | Backend | Razorpay Test API key |
| `RAZORPAY_KEY_SECRET` | Backend | Razorpay Test API secret |
| `RAZORPAY_WEBHOOK_SECRET` | Backend | Razorpay webhook verification |

Frontend:

| Variable | Where | Purpose |
|---|---|---|
| `REACT_APP_BACKEND_URL` | Frontend | Backend API base URL |

For local development:

```env
REACT_APP_BACKEND_URL=http://localhost:8001
```

For a deployed frontend, this value should point to the publicly accessible backend URL.

Never commit `.env` files or private API credentials to GitHub.

---

## Demo Credentials

The demo environment provides the following accounts:

| Role | Email | Password |
|---|---|---|
| OWNER | `cfo@proofledger.com` | `Demo123!` |
| ADMIN | `admin@proofledger.com` | `Demo123!` |
| ANALYST | `analyst@proofledger.com` | `Demo123!` |
| VIEWER | `viewer@proofledger.com` | `Demo123!` |

These credentials are intended for demonstration and development.

Production deployments should use new credentials and appropriate secret management.

---

## 5-Minute Guided Demo

A typical demonstration can follow this flow.

### 1. Control Tower

Start with the Control Tower and show the current financial picture.

Point out changes in cash, payments, refunds, settlements, and other important metrics.

### 2. AI Financial Analyst

Ask:

> **"Why did cash decrease this month?"**

The system starts an investigation rather than simply generating a free-form answer.

### 3. Verified Findings

Show the contributors returned by the financial tools.

Explain that the numbers come from backend calculations.

### 4. Show Proof

Open **Show Proof** on one of the findings.

Demonstrate the path:

```text
Finding
   ↓
Formula
   ↓
Calculated Difference
   ↓
Supporting Evidence
   ↓
Source Transactions
```

This is the key difference between a normal AI answer and an evidence-backed financial investigation.

### 5. Razorpay

Open the Razorpay integration and switch from **DEMO DATA** to **RAZORPAY TEST**.

Show the synchronized test transaction.

For example:

```text
Razorpay Test Payment
Amount: ₹5,000
        ↓
Synchronization
        ↓
ProofLedger Record
        ↓
Searchable Evidence
```

This demonstrates that the same financial workflow can operate on payment-provider data instead of only synthetic records.

### 6. Reconciliation

Open the Reconciliation Center and review an exception such as a missing, partial, duplicate, or fee-difference record.

### 7. Investigation & Audit

Finish by opening an investigation and showing its evidence and audit trail.

---



## API Health Checks

The backend includes health/readiness endpoints where configured.

Typical endpoints include:

```text
/api/health
/api/ready
```

These endpoints can be used by a deployment platform to determine whether the backend is running correctly.

---

## Testing

Run the backend test suite:

```bash
cd backend
pytest -q
```

Build the frontend:

```bash
cd frontend
npm run build
```

Backend tests cover areas such as financial calculations, evidence behavior, intent handling, and other core application functionality.

The frontend production build checks that the application can be compiled successfully for deployment.

---

## Project Structure

```text
proof-ledger/
│
├── api/
│   └── index.py
│
├── backend/
│   ├── server.py
│   ├── requirements.txt
│   ├── .env.example
│   └── ...
│
├── frontend/
│   ├── package.json
│   ├── .env.example
│   └── ...
│
├── docs/
│   ├── architecture.md
│   ├── ai-trust-model.md
│   ├── evaluation.md
│   ├── security.md
│   └── api.md
│
├── docker-compose.yml
├── vercel.json
├── LICENSE
└── README.md
```

---

## Design Principles

### Financial truth comes from data

Financial amounts are calculated from stored financial records rather than generated by the LLM.

### AI is not the accounting system

The AI helps with investigation and explanation, but does not become the source of financial truth.

### Findings should be explainable

Users should be able to understand how important financial numbers were calculated.

### Evidence should be accessible

Important findings should be traceable to the underlying transactions whenever supporting records are available.

### Facts and inference should remain separate

For example, an increase in refunds is a measurable fact.

Saying that the increase caused a reduction in cash requires additional evidence and should not be presented as a fact without support.

### Unusual does not automatically mean fraud

The platform highlights unusual behavior for investigation rather than making unsupported fraud accusations.

---

## Security

ProofLedger includes security controls such as:

- JWT authentication
- Password hashing
- Role-based access
- Organization-level data separation
- Server-side authorization
- Protected financial endpoints
- Razorpay webhook signature verification
- Environment-based secret configuration

API secrets are intended to remain on the backend.

---

## Limitations

The current version has several practical limitations:

- Razorpay integration is currently focused on Test Mode.
- Razorpay Test accounts may not contain realistic settlement activity.
- Historical backfill depends on the configured synchronization workflow.
- OpenAI is optional for the financial calculation layer.
- Production deployment requires appropriate MongoDB, authentication, secrets, and infrastructure configuration.
- Some advanced features may require additional production hardening before being used for real financial operations.

---

## Future Improvements

Planned or possible improvements include:

- More complete incremental Razorpay synchronization
- Scheduled financial summaries
- Attention and anomaly alerts
- Email notifications
- Richer evidence graphs
- Advanced anomaly detection
- PDF investigation reports
- Additional payment-provider integrations
- Configurable financial baselines
- Larger evaluation datasets
- More advanced investigation workflows

---

## Documentation

Additional technical documentation can be found in:

```text
docs/architecture.md
docs/ai-trust-model.md
docs/evaluation.md
docs/security.md
docs/api.md
```


---

