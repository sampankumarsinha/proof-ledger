"""Typed financial tool registry with Pydantic validation.

The AI planner may ONLY invoke tools defined here. No arbitrary queries.
Every tool returns structured facts computed by FinancialEngine / MongoDB.
"""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from .engine import FinancialEngine, resolve_period, top_customers, top_products, get_record
from .date_ranges import resolve_period_key, prior_period
from .reconciliation import reconcile
from .money import format_inr, pct
from .db import get_db


# ---------- Pydantic argument models ----------

class PeriodArgs(BaseModel):
    period: str = "current"
    date_from: Optional[str] = Field(None, alias="from")
    date_to: Optional[str] = Field(None, alias="to")

    model_config = {"populate_by_name": True}

    def resolve(self) -> dict:
        return resolve_period(self.period, self.date_from, self.date_to)


class ComparePeriodsArgs(BaseModel):
    metric: str = "cash_received"
    current_period: Optional[str] = None
    prior_period: Optional[str] = None
    date_from: Optional[str] = Field(None, alias="from")
    date_to: Optional[str] = Field(None, alias="to")
    prior_from: Optional[str] = None
    prior_to: Optional[str] = None

    model_config = {"populate_by_name": True}


class SearchTransactionsArgs(BaseModel):
    date_from: Optional[str] = Field(None, alias="from")
    date_to: Optional[str] = Field(None, alias="to")
    period: str = "current"
    min_amount_paise: Optional[int] = None
    max_amount_paise: Optional[int] = None
    status: Optional[str] = None
    collection: Literal["payments", "refunds", "settlements"] = "payments"
    limit: int = Field(50, ge=1, le=200)
    offset: int = Field(0, ge=0)

    model_config = {"populate_by_name": True}


class GetTransactionArgs(BaseModel):
    collection: Literal["payments", "refunds", "settlements", "invoices", "orders"]
    transaction_id: str


class CustomerTransactionsArgs(BaseModel):
    customer_id: str
    period: str = "current"
    date_from: Optional[str] = Field(None, alias="from")
    date_to: Optional[str] = Field(None, alias="to")
    limit: int = Field(50, ge=1, le=200)

    model_config = {"populate_by_name": True}


class GroupMetricArgs(BaseModel):
    metric: str = "gross_revenue"
    group_by: Literal["day", "customer", "product"] = "day"
    period: str = "current"
    date_from: Optional[str] = Field(None, alias="from")
    date_to: Optional[str] = Field(None, alias="to")
    limit: int = Field(30, ge=1, le=90)

    model_config = {"populate_by_name": True}


class AnalyzeMetricArgs(BaseModel):
    metric: str = "refunds"
    period: str = "current"
    date_from: Optional[str] = Field(None, alias="from")
    date_to: Optional[str] = Field(None, alias="to")

    model_config = {"populate_by_name": True}


class LimitArgs(BaseModel):
    period: str = "current"
    date_from: Optional[str] = Field(None, alias="from")
    date_to: Optional[str] = Field(None, alias="to")
    limit: int = Field(10, ge=1, le=50)

    model_config = {"populate_by_name": True}


class GetEvidenceArgs(BaseModel):
    metric: str
    period: str = "current"
    date_from: Optional[str] = Field(None, alias="from")
    date_to: Optional[str] = Field(None, alias="to")

    model_config = {"populate_by_name": True}


class InvestigationArgs(BaseModel):
    period: str = "current"
    date_from: Optional[str] = Field(None, alias="from")
    date_to: Optional[str] = Field(None, alias="to")

    model_config = {"populate_by_name": True}


# ---------- Tool specs (description for planner) ----------

TOOL_SPECS: dict[str, str] = {
    "get_payments": "List captured payments for a period (paginated)",
    "get_payment_summary": "Payment volume, gross revenue, success/failure counts",
    "get_refunds": "Total refund amount for a period",
    "get_refund_summary": "Refund amount and refund rate for a period",
    "get_settlements": "List settlements for a period",
    "get_settlement_summary": "Pending and processed settlement totals",
    "get_receivables": "Outstanding receivables (all time)",
    "get_receivables_summary": "Outstanding + overdue receivables",
    "get_fees": "Processing fees and GST for a period",
    "get_fee_summary": "Fee totals with component breakdown",
    "get_reconciliation_exceptions": "Reconciliation exceptions and duplicates",
    "get_cash_flow": "Cash received (settled) for a period",
    "compare_periods": "Compare a metric between two periods",
    "analyze_metric": "Analyze a single metric with period context",
    "group_metric": "Group a metric by day, customer, or product",
    "get_transaction": "Fetch a single transaction by ID",
    "search_transactions": "Search payments/refunds/settlements with filters",
    "get_customer_transactions": "All transactions for a customer in a period",
    "get_evidence": "Metric fact with source record IDs",
    "get_investigation_data": "Cash movement decomposition (autopsy)",
    "get_revenue": "Gross revenue (captured payments) for a period",
    "get_net_revenue": "Net revenue = gross - fees - refunds",
    "get_cash_received": "Cash actually settled to bank in period",
    "get_payment_volume": "Successful payment count and average value",
    "get_refund_rate": "Refund rate = refunds / gross revenue",
    "get_pending_settlements": "Sum of settlements still pending",
    "get_overdue_receivables": "Overdue receivables",
    "get_unreconciled_transactions": "Captured payments with no settlement",
    "get_failed_payments": "Failed payment count",
    "get_top_customers": "Top customers by revenue",
    "get_top_products": "Top products by revenue",
    "get_receivables_aging": "Receivables split by aging buckets",
}


TOOL_ARG_MODELS: dict[str, type[BaseModel]] = {
    "get_payments": PeriodArgs,
    "get_payment_summary": PeriodArgs,
    "get_refunds": PeriodArgs,
    "get_refund_summary": PeriodArgs,
    "get_settlements": PeriodArgs,
    "get_settlement_summary": PeriodArgs,
    "get_receivables": PeriodArgs,
    "get_receivables_summary": PeriodArgs,
    "get_fees": PeriodArgs,
    "get_fee_summary": PeriodArgs,
    "get_reconciliation_exceptions": PeriodArgs,
    "get_cash_flow": PeriodArgs,
    "compare_periods": ComparePeriodsArgs,
    "analyze_metric": AnalyzeMetricArgs,
    "group_metric": GroupMetricArgs,
    "get_transaction": GetTransactionArgs,
    "search_transactions": SearchTransactionsArgs,
    "get_customer_transactions": CustomerTransactionsArgs,
    "get_evidence": GetEvidenceArgs,
    "get_investigation_data": InvestigationArgs,
    "get_revenue": PeriodArgs,
    "get_net_revenue": PeriodArgs,
    "get_cash_received": PeriodArgs,
    "get_payment_volume": PeriodArgs,
    "get_refund_rate": PeriodArgs,
    "get_pending_settlements": PeriodArgs,
    "get_overdue_receivables": PeriodArgs,
    "get_unreconciled_transactions": PeriodArgs,
    "get_failed_payments": PeriodArgs,
    "get_top_customers": LimitArgs,
    "get_top_products": LimitArgs,
    "get_receivables_aging": PeriodArgs,
}


def validate_tool_args(name: str, args: dict | None) -> BaseModel:
    model = TOOL_ARG_MODELS.get(name)
    if not model:
        raise ValueError(f"Unknown tool: {name}")
    return model.model_validate(args or {})


def _range_q(field: str, period: dict) -> dict:
    return {field: {"$gte": period["from"], "$lte": period["to"]}}


async def run_tool(org_id: str, name: str, args: dict | None = None, source: str = "DEMO") -> Any:
    """Execute a typed financial tool. All numbers computed deterministically."""
    validated = validate_tool_args(name, args)
    eng = FinancialEngine(org_id, source)
    db = get_db()
    base = {"organization_id": org_id, "deleted_at": None, "source": source}

    # --- period-based tools ---
    if name in ("get_payments", "get_payment_summary", "get_refunds", "get_refund_summary",
                "get_settlements", "get_settlement_summary", "get_receivables", "get_receivables_summary",
                "get_fees", "get_fee_summary", "get_reconciliation_exceptions", "get_cash_flow",
                "get_revenue", "get_net_revenue", "get_cash_received", "get_payment_volume",
                "get_refund_rate", "get_pending_settlements", "get_overdue_receivables",
                "get_unreconciled_transactions", "get_failed_payments"):
        period = validated.resolve() if hasattr(validated, "resolve") else resolve_period("current")

    if name == "get_payments":
        q = {**base, "status": "captured", **_range_q("created_at", period)}
        docs = await db.payments.find(q, {"_id": 0}).sort("created_at", -1).limit(100).to_list(100)
        total = sum(d["amount_paise"] for d in docs)
        return {
            "metric": "payments", "period": period, "amount_paise": total,
            "amount_display": format_inr(total), "transaction_count": len(docs),
            "currency": "INR", "source": source,
            "evidence_ids": [d["id"] for d in docs], "rows": docs[:50],
        }

    if name == "get_payment_summary":
        gross = await eng.gross_revenue(period)
        success, failed = await eng.payment_counts(period)
        return {
            "metric": "payment_summary", "period": period,
            "gross_revenue_paise": gross["value"], "gross_revenue_display": gross["value_display"],
            "successful_count": success, "failed_count": failed,
            "transaction_count": success + failed, "currency": "INR", "source": source,
            "evidence_ids": gross["source_records"],
        }

    if name == "get_refunds":
        fact = await eng.refunds(period)
        return _structured_fact(fact, source)

    if name == "get_refund_summary":
        refs = await eng.refunds(period)
        rate = await eng.refund_rate(period)
        return {
            "metric": "refund_summary", "period": period,
            "amount_paise": refs["value"], "amount_display": refs["value_display"],
            "refund_rate_pct": rate["value"], "refund_rate_display": rate["value_display"],
            "transaction_count": refs["source_count"], "currency": "INR", "source": source,
            "evidence_ids": refs["source_records"],
        }

    if name == "get_settlements":
        q = {**base, **_range_q("created_at", period)}
        docs = await db.settlements.find(q, {"_id": 0}).sort("created_at", -1).limit(100).to_list(100)
        total = sum(d["amount_paise"] for d in docs)
        return {
            "metric": "settlements", "period": period, "amount_paise": total,
            "amount_display": format_inr(total), "transaction_count": len(docs),
            "currency": "INR", "source": source,
            "evidence_ids": [d["id"] for d in docs], "rows": docs[:50],
        }

    if name == "get_settlement_summary":
        pending = await eng.pending_settlements(period)
        cash = await eng.cash_received(period)
        now_iso = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
        overdue_q = {**base, "status": "pending", "expected_at": {"$lt": now_iso}}
        overdue_docs = await db.settlements.find(overdue_q, {"_id": 0, "id": 1, "amount_paise": 1}).to_list(1000)
        overdue_total = sum(d["amount_paise"] for d in overdue_docs)
        return {
            "metric": "settlement_summary", "period": period,
            "pending_paise": pending["value"], "pending_display": pending["value_display"],
            "cash_received_paise": cash["value"], "cash_received_display": cash["value_display"],
            "overdue_paise": overdue_total, "overdue_display": format_inr(overdue_total),
            "overdue_count": len(overdue_docs), "currency": "INR", "source": source,
            "evidence_ids": pending["source_records"] + cash["source_records"],
        }

    if name == "get_receivables":
        fact = await eng.receivables_outstanding(period)
        return _structured_fact(fact, source)

    if name == "get_receivables_summary":
        outstanding = await eng.receivables_outstanding(period)
        overdue = await eng.overdue_receivables(period)
        return {
            "metric": "receivables_summary", "period": period,
            "outstanding_paise": outstanding["value"], "outstanding_display": outstanding["value_display"],
            "overdue_paise": overdue["value"], "overdue_display": overdue["value_display"],
            "currency": "INR", "source": source,
            "evidence_ids": outstanding["source_records"] + overdue["source_records"],
        }

    if name == "get_fees":
        fact = await eng.fee_total(period)
        return _structured_fact(fact, source)

    if name == "get_fee_summary":
        fees = await eng.fee_total(period)
        gross = await eng.gross_revenue(period)
        fee_pct = pct(fees["value"], gross["value"]) if gross["value"] else 0.0
        return {
            "metric": "fee_summary", "period": period,
            "amount_paise": fees["value"], "amount_display": fees["value_display"],
            "gross_revenue_paise": gross["value"], "fee_pct_of_revenue": fee_pct,
            "transaction_count": fees["source_count"], "currency": "INR", "source": source,
            "evidence_ids": fees["source_records"],
        }

    if name == "get_reconciliation_exceptions":
        rec = await reconcile(org_id, limit=500, source=source)
        exceptions = [e for e in rec["exceptions"] if e.get("classification") != "MATCHED"]
        return {
            "metric": "reconciliation_exceptions", "period": period,
            "exception_count": len(exceptions), "match_rate": rec["match_rate"],
            "summary": rec["summary"], "rows": exceptions[:50],
            "currency": "INR", "source": source,
            "evidence_ids": [e.get("payment_id") for e in exceptions if e.get("payment_id")],
        }

    if name == "get_cash_flow":
        fact = await eng.cash_received(period)
        return _structured_fact(fact, source)

    if name == "compare_periods":
        v: ComparePeriodsArgs = validated
        if v.date_from and v.date_to:
            cur_p = resolve_period("custom", v.date_from, v.date_to)
        elif v.current_period:
            cur_p = resolve_period_key(v.current_period)
        else:
            cur_p = resolve_period("current")
        if v.prior_from and v.prior_to:
            prior_p = resolve_period("custom", v.prior_from, v.prior_to)
        elif v.prior_period:
            prior_p = resolve_period_key(v.prior_period)
        else:
            prior_p = prior_period(cur_p)
        metric_fn = getattr(eng, v.metric, None)
        if not metric_fn:
            raise ValueError(f"Unknown metric: {v.metric}")
        cmp = await eng.compare_periods(v.metric, cur_p, prior_p)
        return {
            "metric": f"{v.metric}_comparison",
            "current_period": cur_p, "prior_period": prior_p,
            "current_paise": cmp["current"]["value"],
            "current_display": cmp["current"]["value_display"],
            "prior_paise": cmp["prior"]["value"],
            "prior_display": cmp["prior"]["value_display"],
            "difference_paise": cmp["delta"],
            "difference_display": cmp["delta_display"],
            "change_pct": cmp["change_pct"], "direction": cmp["direction"],
            "currency": "INR", "source": source,
            "evidence_ids": cmp["current"].get("source_records", []),
            "calculation": {
                "current_period": cmp["current"]["value"],
                "prior_period": cmp["prior"]["value"],
                "difference": cmp["delta"],
            },
            "verification_status": "DERIVED_FACT",
        }

    if name == "analyze_metric":
        v: AnalyzeMetricArgs = validated
        period = resolve_period(v.period, v.date_from, v.date_to)
        fn = getattr(eng, v.metric, None)
        if not fn:
            raise ValueError(f"Unknown metric: {v.metric}")
        fact = await fn(period)
        return _structured_fact(fact, source)

    if name == "group_metric":
        v: GroupMetricArgs = validated
        period = resolve_period(v.period, v.date_from, v.date_to)
        if v.group_by == "day":
            return await _group_by_day(org_id, v.metric, period, v.limit, source)
        if v.group_by == "customer":
            return await top_customers(org_id, period, v.limit, source)
        return await top_products(org_id, period, v.limit, source)

    if name == "get_transaction":
        v: GetTransactionArgs = validated
        doc = await get_record(org_id, v.collection, v.transaction_id)
        if not doc or doc.get("organization_id") != org_id:
            return {"metric": "transaction", "found": False, "transaction_id": v.transaction_id}
        return {"metric": "transaction", "found": True, "collection": v.collection,
                "record": doc, "source": source}

    if name == "search_transactions":
        v: SearchTransactionsArgs = validated
        period = resolve_period(v.period, v.date_from, v.date_to)
        q = {**base, **_range_q("created_at", period)}
        if v.status:
            q["status"] = v.status
        if v.min_amount_paise is not None:
            q.setdefault("amount_paise", {})["$gte"] = v.min_amount_paise
        if v.max_amount_paise is not None:
            q.setdefault("amount_paise", {})["$lte"] = v.max_amount_paise
        coll = v.collection
        total = await db[coll].count_documents(q)
        docs = await db[coll].find(q, {"_id": 0}).sort("created_at", -1).skip(v.offset).limit(v.limit).to_list(v.limit)
        amount = sum(d.get("amount_paise", 0) for d in docs)
        return {
            "metric": "search_transactions", "period": period, "collection": coll,
            "total_count": total, "returned_count": len(docs),
            "amount_paise": amount, "amount_display": format_inr(amount),
            "rows": docs, "currency": "INR", "source": source,
            "evidence_ids": [d["id"] for d in docs],
        }

    if name == "get_customer_transactions":
        v: CustomerTransactionsArgs = validated
        period = resolve_period(v.period, v.date_from, v.date_to)
        q = {**base, "customer_id": v.customer_id, **_range_q("created_at", period)}
        payments = await db.payments.find(q, {"_id": 0}).limit(v.limit).to_list(v.limit)
        refunds = await db.refunds.find(
            {**base, "customer_id": v.customer_id, **_range_q("created_at", period)},
            {"_id": 0}).limit(v.limit).to_list(v.limit)
        return {
            "metric": "customer_transactions", "period": period,
            "customer_id": v.customer_id, "payments": payments, "refunds": refunds,
            "payment_count": len(payments), "refund_count": len(refunds),
            "currency": "INR", "source": source,
            "evidence_ids": [d["id"] for d in payments] + [d["id"] for d in refunds],
        }

    if name == "get_evidence":
        v: GetEvidenceArgs = validated
        period = resolve_period(v.period, v.date_from, v.date_to)
        fn = getattr(eng, v.metric, None)
        if not fn:
            raise ValueError(f"Unknown metric: {v.metric}")
        try:
            fact = await fn(period)
        except TypeError:
            fact = await fn()
        return _structured_fact(fact, source)

    if name == "get_investigation_data":
        from .autopsy import cash_autopsy
        v: InvestigationArgs = validated
        period = resolve_period(v.period, v.date_from, v.date_to)
        prior = prior_period(period)
        return await cash_autopsy(org_id, source, period, prior)

    # --- legacy tool names (backward compatible) ---
    if name == "get_revenue":
        return _structured_fact(await eng.gross_revenue(validated.resolve()), source)
    if name == "get_net_revenue":
        return _structured_fact(await eng.net_revenue(validated.resolve()), source)
    if name == "get_cash_received":
        return _structured_fact(await eng.cash_received(validated.resolve()), source)
    if name == "get_payment_volume":
        return _structured_fact(await eng.average_payment_value(validated.resolve()), source)
    if name == "get_refund_rate":
        return _structured_fact(await eng.refund_rate(validated.resolve()), source)
    if name == "get_pending_settlements":
        return _structured_fact(await eng.pending_settlements(validated.resolve()), source)
    if name == "get_overdue_receivables":
        return _structured_fact(await eng.overdue_receivables(validated.resolve()), source)
    if name == "get_unreconciled_transactions":
        return _structured_fact(await eng.unreconciled_amount(validated.resolve()), source)
    if name == "get_failed_payments":
        return _structured_fact(await eng.failed_payments(validated.resolve()), source)
    if name == "get_receivables_aging":
        aging = await eng.receivables_aging()
        return {"metric": "receivables_aging", **aging, "source": source, "verified": True}
    if name == "get_top_customers":
        v: LimitArgs = validated
        return await top_customers(org_id, v.resolve(), v.limit, source)
    if name == "get_top_products":
        v: LimitArgs = validated
        return await top_products(org_id, v.resolve(), v.limit, source)

    raise ValueError(f"Unknown tool: {name}")


def _structured_fact(fact: dict, source: str) -> dict:
    """Normalize engine fact into structured analyst format."""
    if fact.get("metric") and "amount_paise" not in fact:
        out = {
            "metric": fact["metric"],
            "period": fact.get("period"),
            "amount_paise": fact.get("value"),
            "amount_display": fact.get("value_display"),
            "value": fact.get("value"),
            "value_display": fact.get("value_display"),
            "transaction_count": fact.get("source_count", 0),
            "source_count": fact.get("source_count", 0),
            "currency": fact.get("currency", "INR"),
            "source": source,
            "evidence_ids": fact.get("source_records", []),
            "source_records": fact.get("source_records", []),
            "formula": fact.get("formula"),
            "verification_status": fact.get("verification_status", "VERIFIED_FACT"),
            "calculation_version": fact.get("calculation_version"),
        }
        out.update({k: v for k, v in fact.items() if k not in out})
        return out
    return fact


async def _group_by_day(org_id: str, metric: str, period: dict, limit: int, source: str) -> dict:
    db = get_db()
    coll_map = {"gross_revenue": "payments", "refunds": "refunds", "cash_received": "settlements",
                "fee_total": "payments"}
    coll = coll_map.get(metric, "payments")
    date_field = "settled_at" if metric == "cash_received" else "created_at"
    pipeline = [
        {"$match": {"organization_id": org_id, "deleted_at": None, "source": source,
                    date_field: {"$gte": period["from"], "$lte": period["to"]}}},
        {"$group": {"_id": {"$substr": [f"${date_field}", 0, 10]},
                    "total": {"$sum": "$amount_paise"}, "count": {"$sum": 1}}},
        {"$sort": {"total": -1}}, {"$limit": limit},
    ]
    if coll == "payments":
        pipeline[0]["$match"]["status"] = "captured"
    if coll == "settlements":
        pipeline[0]["$match"]["status"] = "processed"
    rows = await db[coll].aggregate(pipeline).to_list(limit)
    out = [{"date": r["_id"], "amount_paise": r["total"], "amount_display": format_inr(r["total"]),
            "count": r["count"]} for r in rows]
    peak = out[0] if out else None
    return {
        "metric": f"{metric}_by_day", "period": period, "rows": out,
        "peak_day": peak, "currency": "INR", "source": source,
    }
