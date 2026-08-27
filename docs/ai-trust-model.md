# AI Trust Model

**Principle:** AI reasons over financial evidence; AI never invents financial truth.

## Separation of concerns
| Concern | Owner |
|---|---|
| Numbers, totals, IDs, dates | Deterministic engine (MongoDB) |
| Proof of a number | Evidence engine (claims + source records) |
| Verification | Claim verification (recompute + record check) |
| Intent, tool choice, prose | LLM (optional) |

## What the LLM must NOT do
Invent amounts, transactions, IDs, customer data; compute financial totals itself; fabricate evidence; assert causation without support.

## What the LLM may do
Classify intent, choose approved tools, summarize/explain verified facts, suggest next questions, explain uncertainty.

## Enforcement
- The LLM can only trigger a **fixed registry of typed tools** — no arbitrary queries/SQL.
- Authoritative figures are rendered from structured **facts**, not parsed from LLM text.
- Claim types are explicit: `VERIFIED_FACT`, `DERIVED_FACT`, `CORRELATION`, `INFERENCE`, `INSUFFICIENT_EVIDENCE`.
- Causal questions route to an **autopsy** that presents ranked *observed movements* labelled `INFERENCE`, never a sole-cause assertion.
- **No key, no problem:** with no OpenAI key, a deterministic explainer runs and all numbers/findings remain intact.

## Confidence
Confidence is computed from signals — source completeness, evidence coverage, calculation verification, record consistency, time alignment, entity resolution, ambiguity — and shown with a plain-language explanation. We never display "95% AI confidence" without evidence.
