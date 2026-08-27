# API

Base: `/api/v1` · OpenAPI: `/api/docs` · Auth: `Authorization: Bearer <token>`

## Auth
- `POST /auth/register` `{ email, password, name, organization_name }`
- `POST /auth/login` `{ email, password }` → `{ token, user }`
- `GET  /auth/me`

## Dashboard / analytics
- `GET /dashboard?period=current`
- `GET /dashboard/trend?metric=cash_received|refunds`

## AI analyst
- `GET  /ai/suggestions`
- `POST /ai/ask` `{ question }` → findings, facts, claims, autopsy, confidence, tool_log
- `GET  /autopsy/cash`

## Evidence
- `GET /evidence/metric/{metric}?period=current` → fact + source records
- `GET /evidence/graph/{customer_id}` → nodes/links

## Financial intelligence
- `GET /reconciliation`
- `GET /settlements/intelligence`
- `GET /receivables/intelligence`
- `GET /refunds/intelligence`

## Investigations / decisions
- `GET/POST /investigations`, `GET /investigations/{id}`
- `POST /investigations/{id}/decision` `{ decision }`
- `GET /investigations/{id}/report?fmt=json|csv`
- `GET /decisions`, `POST /decisions/{item_id}` `{ decision }`

## Scenarios
- `POST /scenarios/simulate` `{ refund_change_pct, settlement_clear_pct, ... }`
- `GET  /scenarios/counterfactual/{no_refunds|settlements_cleared|refunds_down_10}`
- `GET  /scenarios/baseline`

## Evaluation / audit / data
- `POST /evaluations/run`, `GET /evaluations/latest`
- `GET /audit?page=1&size=50`
- `GET /data/{collection}?page&size&q`, `GET /record/{collection}/{id}`

## Integrations / imports
- `GET  /integrations/status`
- `POST /integrations/webhook` (HMAC-verified)
- `POST /imports/csv?entity=payments|invoices` (multipart file)

RBAC: write actions (investigations, decisions, evaluations, imports) require ANALYST+.
