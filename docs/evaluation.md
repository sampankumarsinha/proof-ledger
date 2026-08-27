# Evaluation

The Evaluation Lab measures the system against a benchmark. Ground truth is recomputed **independently** from raw records (a separate code path from the engine) and compared to tool output.

## Categories
- numerical_accuracy — gross revenue, refunds
- calculation_accuracy — pending settlements, cash received
- temporal_reasoning — overdue receivables (date-based)
- tool_selection — question → correct intent/tool
- reconciliation — payment-set integrity
- causal_overreach — leading causal questions do not assert sole cause

## Method
For each case: run the independent ground-truth query and the engine tool; assert exact integer-paise equality (financial cases) or exact intent match (planning cases). Latency is measured per case.

## Results
A fresh deterministic seed scores **100% (10/10)**. Results are stored per run in `evaluation_results` and rendered live in the UI — never hardcoded. Open any case to see `expected` vs `got`.

## Run
UI: **Evaluation → Run benchmark**. API: `POST /api/v1/evaluations/run`.
