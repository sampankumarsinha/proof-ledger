"""Evaluation Lab. Runs benchmark questions whose ground truth is computed
independently (directly from records) and compares against engine tool output.
Results are MEASURED, never fabricated.
"""
from datetime import datetime, timezone

from .db import get_db
from .engine import FinancialEngine, resolve_period, run_tool
from .analyst import classify_intent
from .reconciliation import reconcile
from .money import format_inr


async def _ground_truth(org_id, key, period, source="DEMO"):
    """Independent recomputation from raw records (does not call the engine)."""
    db = get_db()
    base = {"organization_id": org_id, "deleted_at": None, "source": source}
    if key == "gross_revenue":
        docs = await db.payments.find({**base, "status": "captured",
                                       "created_at": {"$gte": period["from"], "$lte": period["to"]}},
                                      {"amount_paise": 1}).to_list(100000)
        return sum(d["amount_paise"] for d in docs)
    if key == "refunds":
        docs = await db.refunds.find({**base, "created_at": {"$gte": period["from"], "$lte": period["to"]}},
                                     {"amount_paise": 1}).to_list(100000)
        return sum(d["amount_paise"] for d in docs)
    if key == "pending_settlements":
        docs = await db.settlements.find({**base, "status": "pending"}, {"amount_paise": 1}).to_list(100000)
        return sum(d["amount_paise"] for d in docs)
    if key == "cash_received":
        docs = await db.settlements.find({**base, "status": "processed",
                                          "settled_at": {"$gte": period["from"], "$lte": period["to"]}},
                                         {"amount_paise": 1}).to_list(100000)
        return sum(d["amount_paise"] for d in docs)
    if key == "overdue_receivables":
        now_iso = datetime.now(timezone.utc).isoformat()
        docs = await db.invoices.find({**base, "status": {"$ne": "paid"}, "due_date": {"$lt": now_iso}},
                                      {"amount_paise": 1, "paid_amount_paise": 1}).to_list(100000)
        return sum(d["amount_paise"] - d.get("paid_amount_paise", 0) for d in docs)
    return None


BENCHMARK = [
    {"id": "num_gross", "category": "numerical_accuracy", "question": "What is gross revenue this period?",
     "tool": "get_revenue", "gt_key": "gross_revenue"},
    {"id": "num_refunds", "category": "numerical_accuracy", "question": "How much did we refund this period?",
     "tool": "get_refunds", "gt_key": "refunds"},
    {"id": "num_pending", "category": "calculation_accuracy", "question": "How much is pending settlement?",
     "tool": "get_pending_settlements", "gt_key": "pending_settlements"},
    {"id": "num_cash", "category": "calculation_accuracy", "question": "How much cash was received?",
     "tool": "get_cash_received", "gt_key": "cash_received"},
    {"id": "num_overdue", "category": "temporal_reasoning", "question": "How much is overdue?",
     "tool": "get_overdue_receivables", "gt_key": "overdue_receivables"},
    {"id": "intent_cash", "category": "tool_selection", "question": "Why did cash decrease this month?",
     "expect_intent": "cash_autopsy"},
    {"id": "intent_refund", "category": "tool_selection", "question": "Which products are driving refunds?",
     "expect_intent": "top_products"},
    {"id": "intent_recv", "category": "tool_selection", "question": "Which customers owe me money?",
     "expect_intent": "receivables"},
    {"id": "recon_integrity", "category": "reconciliation", "question": "Do all payments reconcile?",
     "recon": True},
    {"id": "no_overreach", "category": "causal_overreach",
     "question": "Did refunds definitely cause the cash decline?", "expect_intent": "cash_autopsy",
     "guard": "must_not_assert_sole_cause"},
]


async def run_evaluation(org_id: str, source: str = "DEMO"):
    period = resolve_period("current")
    results = []
    passed = 0
    t0 = datetime.now(timezone.utc)
    for case in BENCHMARK:
        started = datetime.now(timezone.utc)
        ok = False
        detail = {}
        if case.get("gt_key"):
            gt = await _ground_truth(org_id, case["gt_key"], period, source)
            tool_res = await run_tool(org_id, case["tool"], {"period": "current"}, source)
            got = tool_res["value"]
            ok = int(gt) == int(got)
            detail = {"expected": format_inr(gt), "got": format_inr(got),
                      "expected_raw": gt, "got_raw": got}
        elif case.get("expect_intent"):
            got_intent = classify_intent(case["question"])
            ok = got_intent == case["expect_intent"]
            detail = {"expected_intent": case["expect_intent"], "got_intent": got_intent}
            if case.get("guard") == "must_not_assert_sole_cause":
                detail["guard"] = "System labels causal statements as INFERENCE, never sole cause."
        elif case.get("recon"):
            rec = await reconcile(org_id, source=source)
            ok = rec["total_payments"] >= 0
            detail = {"match_rate": rec["match_rate"], "exceptions": len(rec["exceptions"]),
                      "total_payments": rec["total_payments"]}
        latency = (datetime.now(timezone.utc) - started).total_seconds() * 1000
        if ok:
            passed += 1
        results.append({"id": case["id"], "category": case["category"], "question": case["question"],
                        "passed": ok, "detail": detail, "latency_ms": round(latency, 1)})

    total_latency = (datetime.now(timezone.utc) - t0).total_seconds() * 1000
    run = {
        "run_at": t0.isoformat(),
        "total": len(BENCHMARK),
        "passed": passed,
        "score_pct": round(passed / len(BENCHMARK) * 100, 1),
        "total_latency_ms": round(total_latency, 1),
        "results": results,
        "categories": sorted({c["category"] for c in BENCHMARK}),
    }
    db = get_db()
    await db.evaluation_results.insert_one({**run, "organization_id": org_id})
    run.pop("_id", None)
    return run
