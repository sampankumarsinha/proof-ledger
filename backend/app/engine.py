"""Deterministic financial calculation engine + typed tool system.

CRITICAL TRUST RULE: every financial number surfaced to the user originates
here, computed from source records in MongoDB. The LLM never produces numbers.
Each calculation returns a structured "fact" with value, formula, period,
currency, source record ids and a verification status.
"""
from datetime import datetime, timezone, timedelta

from .db import get_db
from .money import rupees, format_inr, pct
from .date_ranges import resolve_period_key

CALC_VERSION = "1.0.0"


def resolve_period(period_key: str = "current", date_from: str = None, date_to: str = None):
    """Resolve a period key or explicit dates. Delegates to date_ranges module."""
    return resolve_period_key(period_key, date_from, date_to)


def _range_q(field, period):
    return {field: {"$gte": period["from"], "$lte": period["to"]}}


def _fact(metric, value_paise, formula, period, source_records, status="VERIFIED_FACT", extra=None):
    f = {
        "metric": metric,
        "value": value_paise,
        "value_display": format_inr(value_paise) if isinstance(value_paise, int) else value_paise,
        "value_rupees": rupees(value_paise) if isinstance(value_paise, int) else value_paise,
        "currency": "INR",
        "formula": formula,
        "period": period,
        "source_records": source_records[:200],
        "source_count": len(source_records),
        "verification_status": status,
        "calculation_version": CALC_VERSION,
        "verified": True,
    }
    if extra:
        f.update(extra)
    return f


DEFAULT_SOURCE = "DEMO"


async def get_active_source(org_id: str) -> str:
    org = await get_db().organizations.find_one({"id": org_id}, {"_id": 0, "active_source": 1})
    return (org or {}).get("active_source") or DEFAULT_SOURCE


class FinancialEngine:
    def __init__(self, org_id: str, source: str = DEFAULT_SOURCE):
        self.org = org_id
        self.source = source
        self.db = get_db()

    def _base(self):
        return {"organization_id": self.org, "deleted_at": None, "source": self.source}

    async def gross_revenue(self, period):
        q = {**self._base(), "status": "captured", **_range_q("created_at", period)}
        docs = await self.db.payments.find(q, {"_id": 0, "id": 1, "amount_paise": 1}).to_list(100000)
        total = sum(d["amount_paise"] for d in docs)
        return _fact("gross_revenue", total,
                     "SUM(payment.amount) WHERE status=captured",
                     period, [d["id"] for d in docs])

    async def fee_total(self, period):
        q = {**self._base(), "status": "captured", **_range_q("created_at", period)}
        docs = await self.db.payments.find(q, {"_id": 0, "id": 1, "fee_paise": 1, "tax_paise": 1}).to_list(100000)
        total = sum(d["fee_paise"] + d["tax_paise"] for d in docs)
        return _fact("fee_total", total, "SUM(payment.fee + payment.gst)", period, [d["id"] for d in docs])

    async def refunds(self, period):
        q = {**self._base(), **_range_q("created_at", period)}
        docs = await self.db.refunds.find(q, {"_id": 0, "id": 1, "amount_paise": 1}).to_list(100000)
        total = sum(d["amount_paise"] for d in docs)
        return _fact("refunds", total, "SUM(refund.amount)", period, [d["id"] for d in docs])

    async def net_revenue(self, period):
        gross = await self.gross_revenue(period)
        fees = await self.fee_total(period)
        refs = await self.refunds(period)
        value = gross["value"] - fees["value"] - refs["value"]
        return _fact("net_revenue", value,
                     "gross_revenue - fees - refunds",
                     period, [], status="DERIVED_FACT",
                     extra={"components": {"gross_revenue": gross["value"], "fees": fees["value"], "refunds": refs["value"]}})

    async def cash_received(self, period):
        q = {**self._base(), "status": "processed", "settled_at": {"$ne": None, "$gte": period["from"], "$lte": period["to"]}}
        docs = await self.db.settlements.find(q, {"_id": 0, "id": 1, "amount_paise": 1}).to_list(100000)
        total = sum(d["amount_paise"] for d in docs)
        return _fact("cash_received", total,
                     "SUM(settlement.net_amount) WHERE status=processed AND settled_in_period",
                     period, [d["id"] for d in docs])

    async def pending_settlements(self, period=None):
        q = {**self._base(), "status": "pending"}
        docs = await self.db.settlements.find(q, {"_id": 0, "id": 1, "amount_paise": 1, "expected_at": 1}).to_list(100000)
        total = sum(d["amount_paise"] for d in docs)
        return _fact("pending_settlements", total,
                     "SUM(settlement.net_amount) WHERE status=pending",
                     period or resolve_period(), [d["id"] for d in docs])

    async def receivables_outstanding(self, period=None):
        q = {**self._base(), "status": {"$ne": "paid"}}
        docs = await self.db.invoices.find(q, {"_id": 0, "id": 1, "amount_paise": 1, "paid_amount_paise": 1}).to_list(100000)
        total = sum(d["amount_paise"] - d.get("paid_amount_paise", 0) for d in docs)
        return _fact("receivables_outstanding", total,
                     "SUM(invoice.amount - invoice.paid) WHERE status != paid",
                     period or resolve_period(), [d["id"] for d in docs])

    async def overdue_receivables(self, period=None):
        now_iso = datetime.now(timezone.utc).isoformat()
        q = {**self._base(), "status": {"$ne": "paid"}, "due_date": {"$lt": now_iso}}
        docs = await self.db.invoices.find(q, {"_id": 0, "id": 1, "amount_paise": 1, "paid_amount_paise": 1}).to_list(100000)
        total = sum(d["amount_paise"] - d.get("paid_amount_paise", 0) for d in docs)
        return _fact("overdue_receivables", total,
                     "SUM(invoice.amount - invoice.paid) WHERE due_date < now AND status != paid",
                     period or resolve_period(), [d["id"] for d in docs])

    async def receivables_aging(self):
        now = datetime.now(timezone.utc)
        q = {**self._base(), "status": {"$ne": "paid"}}
        docs = await self.db.invoices.find(q, {"_id": 0}).to_list(100000)
        buckets = {"current": 0, "1-7": 0, "8-30": 0, "31-60": 0, "60+": 0}
        detail = {k: [] for k in buckets}
        for d in docs:
            outstanding = d["amount_paise"] - d.get("paid_amount_paise", 0)
            due = datetime.fromisoformat(d["due_date"])
            days = (now - due).days
            if days <= 0:
                b = "current"
            elif days <= 7:
                b = "1-7"
            elif days <= 30:
                b = "8-30"
            elif days <= 60:
                b = "31-60"
            else:
                b = "60+"
            buckets[b] += outstanding
            detail[b].append(d["id"])
        return {"buckets": buckets, "buckets_display": {k: format_inr(v) for k, v in buckets.items()},
                "detail": detail, "currency": "INR"}

    async def unreconciled_amount(self, period=None):
        q = {**self._base(), "status": "captured", "settlement_id": None}
        docs = await self.db.payments.find(q, {"_id": 0, "id": 1, "amount_paise": 1}).to_list(100000)
        total = sum(d["amount_paise"] for d in docs)
        return _fact("unreconciled_amount", total,
                     "SUM(payment.amount) WHERE captured AND settlement_id IS NULL",
                     period or resolve_period(), [d["id"] for d in docs])

    async def payment_counts(self, period):
        base = {**self._base(), **_range_q("created_at", period)}
        success = await self.db.payments.count_documents({**base, "status": "captured"})
        failed = await self.db.payments.count_documents({**base, "status": "failed"})
        return success, failed

    async def successful_payments(self, period):
        s, _ = await self.payment_counts(period)
        return _fact("successful_payments", s, "COUNT(payment) WHERE status=captured", period, [],
                     status="VERIFIED_FACT", extra={"value_display": str(s), "value_rupees": s})

    async def failed_payments(self, period):
        _, f = await self.payment_counts(period)
        return _fact("failed_payments", f, "COUNT(payment) WHERE status=failed", period, [],
                     status="VERIFIED_FACT", extra={"value_display": str(f), "value_rupees": f})

    async def payment_success_rate(self, period):
        s, f = await self.payment_counts(period)
        rate = pct(s, s + f)
        return _fact("payment_success_rate", rate, "captured / (captured + failed)", period, [],
                     status="DERIVED_FACT", extra={"value_display": f"{rate}%", "value_rupees": rate})

    async def average_payment_value(self, period):
        gross = await self.gross_revenue(period)
        s, _ = await self.payment_counts(period)
        avg = gross["value"] // s if s else 0
        return _fact("average_payment_value", avg, "gross_revenue / successful_payments", period,
                     [], status="DERIVED_FACT")

    async def refund_rate(self, period):
        gross = await self.gross_revenue(period)
        refs = await self.refunds(period)
        rate = pct(refs["value"], gross["value"])
        return _fact("refund_rate", rate, "refunds / gross_revenue * 100", period, [],
                     status="DERIVED_FACT",
                     extra={"value_display": f"{rate}%", "value_rupees": rate,
                            "components": {"refunds": refs["value"], "gross_revenue": gross["value"]}})

    # ---------- period comparison ----------
    async def compare_periods(self, metric: str, cur_period, prior_period):
        fn = getattr(self, metric)
        cur = await fn(cur_period)
        prior = await fn(prior_period)
        delta = cur["value"] - prior["value"]
        change_pct = pct(delta, prior["value"]) if prior["value"] else 0.0
        return {
            "metric": metric,
            "current": cur, "prior": prior,
            "delta": delta, "delta_display": format_inr(delta) if isinstance(delta, int) else delta,
            "change_pct": change_pct,
            "direction": "up" if delta > 0 else ("down" if delta < 0 else "flat"),
        }


# ---------- record fetchers ----------
async def get_record(org_id, collection, record_id):
    db = get_db()
    doc = await db[collection].find_one({"organization_id": org_id, "id": record_id}, {"_id": 0})
    return doc


async def top_customers(org_id, period, limit=10, source=DEFAULT_SOURCE):
    db = get_db()
    pipeline = [
        {"$match": {"organization_id": org_id, "status": "captured", "deleted_at": None, "source": source,
                    "created_at": {"$gte": period["from"], "$lte": period["to"]}}},
        {"$group": {"_id": "$customer_id", "total": {"$sum": "$amount_paise"}, "count": {"$sum": 1}}},
        {"$sort": {"total": -1}}, {"$limit": limit},
    ]
    rows = await db.payments.aggregate(pipeline).to_list(limit)
    out = []
    for r in rows:
        cust = await db.customers.find_one({"id": r["_id"]}, {"_id": 0, "name": 1, "id": 1})
        out.append({"customer_id": r["_id"], "name": cust["name"] if cust else "Unknown",
                    "total": r["total"], "total_display": format_inr(r["total"]), "count": r["count"]})
    return {"metric": "top_customers", "rows": out, "period": period, "verified": True}


async def top_products(org_id, period, limit=10, source=DEFAULT_SOURCE):
    db = get_db()
    pipeline = [
        {"$match": {"organization_id": org_id, "status": "captured", "deleted_at": None, "source": source,
                    "created_at": {"$gte": period["from"], "$lte": period["to"]}}},
        {"$group": {"_id": "$product_id", "total": {"$sum": "$amount_paise"}, "count": {"$sum": 1}}},
        {"$sort": {"total": -1}}, {"$limit": limit},
    ]
    rows = await db.payments.aggregate(pipeline).to_list(limit)
    out = []
    for r in rows:
        prod = await db.products.find_one({"id": r["_id"]}, {"_id": 0, "name": 1})
        refund_rows = await db.refunds.aggregate([
            {"$match": {"organization_id": org_id, "product_id": r["_id"], "deleted_at": None, "source": source}},
            {"$group": {"_id": None, "t": {"$sum": "$amount_paise"}}},
        ]).to_list(1)
        refunded = refund_rows[0]["t"] if refund_rows else 0
        out.append({"product_id": r["_id"], "name": prod["name"] if prod else "Unknown",
                    "total": r["total"], "total_display": format_inr(r["total"]),
                    "count": r["count"], "refunded": refunded,
                    "refund_rate": pct(refunded, r["total"])})
    return {"metric": "top_products", "rows": out, "period": period, "verified": True}


# ================= TYPED TOOL REGISTRY =================
# Re-exported from tools.py for backward compatibility.
from .tools import TOOL_SPECS, run_tool  # noqa: E402, F401
