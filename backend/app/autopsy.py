"""Financial Autopsy: deterministic decomposition of a metric change into
ranked contributors. Each contributor's impact is CALCULATED from source
records. Causation is never asserted beyond what the data supports.
"""
from .engine import FinancialEngine, resolve_period
from .money import format_inr, rupees
from .db import get_db


async def _failed_value(org_id, period, source="DEMO"):
    db = get_db()
    docs = await db.payments.find(
        {"organization_id": org_id, "status": "failed", "deleted_at": None, "source": source,
         "created_at": {"$gte": period["from"], "$lte": period["to"]}},
        {"_id": 0, "id": 1, "amount_paise": 1}).to_list(100000)
    return sum(d["amount_paise"] for d in docs), [d["id"] for d in docs]


async def _unpaid_created(org_id, period, source="DEMO"):
    db = get_db()
    docs = await db.invoices.find(
        {"organization_id": org_id, "status": {"$ne": "paid"}, "deleted_at": None, "source": source,
         "created_at": {"$gte": period["from"], "$lte": period["to"]}},
        {"_id": 0, "id": 1, "amount_paise": 1, "paid_amount_paise": 1}).to_list(100000)
    return sum(d["amount_paise"] - d.get("paid_amount_paise", 0) for d in docs), [d["id"] for d in docs]


async def _pending_created(org_id, period, source="DEMO"):
    db = get_db()
    docs = await db.settlements.find(
        {"organization_id": org_id, "status": "pending", "deleted_at": None, "source": source,
         "created_at": {"$gte": period["from"], "$lte": period["to"]}},
        {"_id": 0, "id": 1, "amount_paise": 1}).to_list(100000)
    return sum(d["amount_paise"] for d in docs), [d["id"] for d in docs]


async def cash_autopsy(org_id: str, source: str = "DEMO", cur=None, prior=None):
    eng = FinancialEngine(org_id, source)
    cur = cur or resolve_period("current")
    prior = prior or resolve_period("prior")

    cash_cur = await eng.cash_received(cur)
    cash_prior = await eng.cash_received(prior)
    cash_delta = cash_cur["value"] - cash_prior["value"]

    gross_c = await eng.gross_revenue(cur); gross_p = await eng.gross_revenue(prior)
    ref_c = await eng.refunds(cur); ref_p = await eng.refunds(prior)
    pend_c_v, pend_c_ids = await _pending_created(org_id, cur, source)
    pend_p_v, _ = await _pending_created(org_id, prior, source)
    fee_c = await eng.fee_total(cur); fee_p = await eng.fee_total(prior)
    fail_c_v, fail_c_ids = await _failed_value(org_id, cur, source)
    fail_p_v, _ = await _failed_value(org_id, prior, source)
    recv_c_v, recv_c_ids = await _unpaid_created(org_id, cur, source)
    recv_p_v, _ = await _unpaid_created(org_id, prior, source)

    def contributor(metric, impact, calc, records, note, ctype="DERIVED_FACT"):
        return {
            "metric": metric,
            "impact": impact,                       # negative impact = pulls cash DOWN
            "impact_display": format_inr(impact),
            "abs_impact": abs(impact),
            "direction": "reduces_cash" if impact < 0 else "increases_cash",
            "calculation": calc,
            "evidence_records": records[:100],
            "evidence_count": len(records),
            "note": note,
            "claim_type": ctype,
            "confidence": "HIGH" if records else "MEDIUM",
        }

    contributors = [
        contributor("settlement_timing", -(pend_c_v - pend_p_v),
                    "-(pending_settlements_created_current - prior)",
                    pend_c_ids,
                    "Cash captured but not yet settled to the bank is higher this period."),
        contributor("refunds", -(ref_c["value"] - ref_p["value"]),
                    "-(refunds_current - refunds_prior)", ref_c["source_records"],
                    "Increased refunds returned money to customers."),
        contributor("gross_revenue", (gross_c["value"] - gross_p["value"]),
                    "gross_revenue_current - gross_revenue_prior", gross_c["source_records"],
                    "Change in captured payment volume."),
        contributor("processing_fees", -(fee_c["value"] - fee_p["value"]),
                    "-(fees_current - fees_prior)", fee_c["source_records"],
                    "Change in processing fees and GST deducted at settlement."),
        contributor("failed_payments", -(fail_c_v - fail_p_v),
                    "-(failed_value_current - failed_value_prior)", fail_c_ids,
                    "Value of payments that failed and never became cash."),
        contributor("receivables", -(recv_c_v - recv_p_v),
                    "-(unpaid_invoices_created_current - prior)", recv_c_ids,
                    "New invoiced revenue not yet collected."),
    ]
    # rank by magnitude of downward pressure
    contributors.sort(key=lambda c: c["impact"])

    return {
        "question": "Why did cash change this period?",
        "target": {
            "metric": "cash_received",
            "current": cash_cur, "prior": cash_prior,
            "delta": cash_delta, "delta_display": format_inr(cash_delta),
            "change_pct": round(cash_delta / cash_prior["value"] * 100, 2) if cash_prior["value"] else 0,
        },
        "contributors": contributors,
        "interpretation_type": "INFERENCE",
        "interpretation": ("The ranked contributors above are computed directly from source records. "
                           "They quantify observed movements; they do not by themselves prove a single "
                           "root cause. Review the evidence for each contributor before concluding."),
    }
