"""Deterministic reconciliation engine. Classifies each captured payment by
matching it against its order, settlement, fees and refunds. No AI involved.
"""
from datetime import datetime, timezone

from .db import get_db
from .money import format_inr

FEE_BPS = 200
GST_BPS = 1800
FEE_TOLERANCE = 100          # 1 rupee tolerance in paise
PARTIAL_TOLERANCE_BPS = 100  # 1% shortfall tolerance

CLASSES = [
    "MATCHED", "PARTIAL", "FEE_DIFFERENCE", "TIMING_DIFFERENCE", "DUPLICATE",
    "MISSING_PAYMENT", "MISSING_SETTLEMENT", "REFUND_ADJUSTMENT", "UNEXPLAINED",
]


async def reconcile(org_id: str, limit: int = 1000, source: str = "DEMO"):
    db = get_db()
    base = {"organization_id": org_id, "deleted_at": None, "source": source}
    payments = await db.payments.find({**base, "status": "captured"}, {"_id": 0}).to_list(100000)
    settlements = {s["id"]: s for s in await db.settlements.find(base, {"_id": 0}).to_list(100000)}
    refunds_by_pay = {}
    for r in await db.refunds.find(base, {"_id": 0}).to_list(100000):
        refunds_by_pay.setdefault(r["payment_id"], []).append(r)

    # detect duplicates: same (order_id, amount) captured more than once
    seen = {}
    for p in payments:
        key = (p["order_id"], p["amount_paise"])
        seen.setdefault(key, []).append(p)
    dup_ids = set()
    for key, group in seen.items():
        if len(group) > 1:
            for p in group[1:]:
                dup_ids.add(p["id"])

    now = datetime.now(timezone.utc)
    results = []
    summary = {c: {"count": 0, "amount": 0} for c in CLASSES}

    for p in payments:
        expected_fee = p["amount_paise"] * FEE_BPS // 10000
        expected_tax = expected_fee * GST_BPS // 10000
        pay_refunds = refunds_by_pay.get(p["id"], [])
        cls, explanation = "MATCHED", "Payment matches order, fee schedule and settlement."

        if p["id"] in dup_ids:
            cls = "DUPLICATE"
            explanation = "A second captured payment exists for the same order and amount."
        elif not p.get("settlement_id"):
            age = (now - datetime.fromisoformat(p["created_at"])).days
            if age >= 3:
                cls = "MISSING_SETTLEMENT"
                explanation = f"Captured {age} days ago but never assigned to a settlement batch."
            else:
                cls = "TIMING_DIFFERENCE"
                explanation = "Captured recently; settlement expected in the next cycle."
        else:
            s = settlements.get(p["settlement_id"])
            if not s:
                cls = "UNEXPLAINED"
                explanation = "References a settlement that does not exist."
            else:
                fee_diff = (p["fee_paise"] - expected_fee) + (p["tax_paise"] - expected_tax)
                if abs(fee_diff) > FEE_TOLERANCE:
                    cls = "FEE_DIFFERENCE"
                    explanation = (f"Recorded fee {format_inr(p['fee_paise'] + p['tax_paise'])} differs from "
                                   f"contracted {format_inr(expected_fee + expected_tax)} by {format_inr(fee_diff)}.")
                elif s.get("adjustment_paise", 0) < 0 and abs(s["adjustment_paise"]) > p["amount_paise"] * PARTIAL_TOLERANCE_BPS // 10000:
                    cls = "PARTIAL"
                    explanation = f"Settlement short by {format_inr(-s['adjustment_paise'])} versus expected net."
                elif pay_refunds:
                    cls = "REFUND_ADJUSTMENT"
                    total_r = sum(r["amount_paise"] for r in pay_refunds)
                    explanation = f"Payment reconciled with {len(pay_refunds)} refund(s) totalling {format_inr(total_r)}."
                elif s["status"] == "processed" and s.get("expected_at") and s.get("settled_at") and s["settled_at"] > s["expected_at"]:
                    cls = "TIMING_DIFFERENCE"
                    explanation = "Settled later than the expected date, but amounts reconcile."

        summary[cls]["count"] += 1
        summary[cls]["amount"] += p["amount_paise"]
        results.append({
            "payment_id": p["id"], "external_id": p["external_id"], "order_id": p["order_id"],
            "settlement_id": p.get("settlement_id"), "amount": p["amount_paise"],
            "amount_display": format_inr(p["amount_paise"]),
            "classification": cls, "explanation": explanation,
            "expected_fee": expected_fee + expected_tax, "recorded_fee": p["fee_paise"] + p["tax_paise"],
            "created_at": p["created_at"],
        })

    results.sort(key=lambda r: (r["classification"] == "MATCHED", r["created_at"]), reverse=False)
    for c in summary:
        summary[c]["amount_display"] = format_inr(summary[c]["amount"])
    # MATCHED plus explained-but-benign classes count as reconciled.
    reconciled_classes = {"MATCHED", "REFUND_ADJUSTMENT", "TIMING_DIFFERENCE"}
    reconciled = sum(summary[c]["count"] for c in reconciled_classes)
    total = len(results)
    return {
        "summary": summary,
        "match_rate": round(reconciled / total * 100, 2) if total else 0,
        "reconciled": reconciled,
        "total_payments": total,
        "exceptions": [r for r in results if r["classification"] not in reconciled_classes][:limit],
        "explained": [r for r in results if r["classification"] in ("REFUND_ADJUSTMENT", "TIMING_DIFFERENCE")][:limit],
        "results_sample": results[:limit],
    }
