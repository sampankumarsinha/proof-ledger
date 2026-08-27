# Security

- **Auth:** JWT Bearer tokens (HS256), 12h expiry; bcrypt password hashing.
- **RBAC:** VIEWER < ANALYST < ADMIN < OWNER, enforced server-side via dependency (`require_role`).
- **Multi-tenant isolation:** every query scoped by `organization_id`; no cross-tenant reads/writes.
- **Brute-force protection:** login attempts are counted per (ip,email) with a temporary lockout.
- **Secrets:** OpenAI/Razorpay keys and DB credentials are server-side only (env vars); never sent to the client. Razorpay credentials never leave the backend.
- **Webhooks:** Razorpay webhooks verified with HMAC-SHA256 (`compare_digest`).
- **Input validation:** Pydantic models on request bodies; typed tool arguments; CSV import validates schema, types and amounts.
- **Database:** parameterized driver calls (no string-built queries); the LLM cannot issue arbitrary queries.
- **CORS:** configured via `CORS_ORIGINS`.
- **Observability without leakage:** structured logs include request id, method, path, status and latency; secrets/tokens/passwords are never logged.
- **Error UX:** unhandled errors return a safe, explained message with a request id — never a raw stack trace.

## Endpoints
- `GET /api/health` — liveness
- `GET /api/ready` — readiness with database / AI / integration checks
