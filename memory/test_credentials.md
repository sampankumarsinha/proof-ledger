# ProofLedger — Test Credentials

All users belong to the demo organization **Meridian Commerce Pvt Ltd** (seeded on startup).

| Role    | Email                     | Password  |
|---------|---------------------------|-----------|
| OWNER   | cfo@proofledger.com       | Demo123!  |
| ADMIN   | admin@proofledger.com     | Demo123!  |
| ANALYST | analyst@proofledger.com   | Demo123!  |
| VIEWER  | viewer@proofledger.com    | Demo123!  |

## Auth endpoints (JWT Bearer token)
- POST `/api/v1/auth/login`  body: `{ "email", "password" }` → `{ token, user }`
- POST `/api/v1/auth/register` body: `{ email, password, name, organization_name }`
- GET  `/api/v1/auth/me`  header: `Authorization: Bearer <token>`

Frontend stores the token in localStorage and sends `Authorization: Bearer <token>` on every request.

## Notes
- Financial data is deterministic demo data with coherent stories (delayed/partial/missing settlements, refund spike, overdue receivables, fee discrepancy, duplicate payment).
- AI explanation uses the user's OpenAI key if `OPENAI_API_KEY` is set in backend/.env; otherwise a deterministic explainer is used (findings/numbers are always deterministic regardless).
