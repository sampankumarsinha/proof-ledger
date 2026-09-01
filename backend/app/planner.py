"""AI query planner: intent routing, tool selection, and multi-step execution plans.

The planner selects approved tools deterministically from question text and
conversation context. The LLM never chooses tools or computes numbers.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .date_ranges import parse_question_dates, prior_period


# General knowledge patterns (no live data needed)
GENERAL_PATTERNS = [
    r"what is a settlement", r"what is a refund", r"what is receivable",
    r"explain how razorpay", r"how does razorpay", r"how do settlements work",
    r"what does reconciliation mean", r"define ", r"explain the concept",
]


FINANCIAL_METRIC_KEYWORDS = [
    ("refunds", ["refund", "returned", "chargeback"]),
    ("cash_received", ["cash received", "cash decrease", "cash decline", "cash fall", "cash drop",
                       "where is my cash", "cash stuck", "why did cash", "what happened to my cash",
                       "money received", "how much did we receive", "how much did i receive"]),
    ("gross_revenue", ["revenue", "sales", "income", "top line", "payment volume", "payments this"]),
    ("pending_settlements", ["settlement", "settle", "payout", "delayed settlement", "pending settlement"]),
    ("receivables_outstanding", ["owe", "receivable", "outstanding", "unpaid invoice", "who owes",
                                 "collect", "money pending", "money is still pending", "still pending"]),
    ("unreconciled_amount", ["unreconciled", "unexplained", "not matching", "mismatch", "duplicate payment"]),
    ("failed_payments", ["failed payment", "payment failure"]),
    ("fee_total", ["fee", "processing fee", "fee discrepancy"]),
]


INVESTIGATION_KEYWORDS = [
    "why did", "what caused", "what changed", "what happened", "what's unusual",
    "investigate", "break down", "contributor",
]


@dataclass
class ToolStep:
    tool: str
    args: dict
    label: str


@dataclass
class QueryPlan:
    route: str  # "financial" | "general" | "follow_up"
    intent: str
    period: dict
    comparison_period: dict | None
    is_comparison: bool
    steps: list[ToolStep] = field(default_factory=list)
    metric: str | None = None


def route_intent(question: str, context: dict | None = None) -> str:
    q = question.lower()
    if context and _is_follow_up(q):
        return "follow_up"
    for pat in GENERAL_PATTERNS:
        if re.search(pat, q):
            # Unless they ask about THEIR data
            if not re.search(r"\b(my|our|mine|we)\b", q):
                return "general"
    return "financial"


def _is_follow_up(q: str) -> bool:
    return bool(re.search(
        r"\b(that|those|it|them|same|what caused|why did it|how does that compare|"
        r"the month before|previous period|prior period|supporting transactions|"
        r"break.*down|show me the transactions)\b", q,
    ))


def _detect_metric(q: str, context: dict | None = None) -> str | None:
    if context and context.get("metric"):
        if _is_follow_up(q):
            return context["metric"]
    for metric, kws in FINANCIAL_METRIC_KEYWORDS:
        if any(k in q for k in kws):
            return metric
    return None


def _is_investigation(q: str) -> bool:
    return any(k in q for k in INVESTIGATION_KEYWORDS)


def _is_comparison(q: str) -> bool:
    return bool(re.search(
        r"\b(compare|versus|vs\.?|compared|increase|decrease|change|month over month|"
        r"difference|how much.*more|how much.*less)\b", q,
    ))


def _period_args(period: dict) -> dict:
    return {"period": period["key"], "from": period["from"], "to": period["to"]}


def plan_query(question: str, context: dict | None = None) -> QueryPlan:
    """Build a multi-step tool execution plan from question + context."""
    context = context or {}
    route = route_intent(question, context)
    q = question.lower()

    if route == "general":
        return QueryPlan(route="general", intent="general", period={}, comparison_period=None,
                         is_comparison=False, steps=[])

    period, comp_period, is_comp = parse_question_dates(question, context)
    metric = _detect_metric(q, context) or context.get("metric")
    intent = _classify_intent(q, metric, context)

    steps: list[ToolStep] = []
    pa = _period_args(period)
    comp_pa = _period_args(comp_period) if comp_period else None

    # Follow-up: comparison using context metric
    if route == "follow_up" and context.get("metric"):
        metric = context["metric"]
        if _is_comparison(q) or "compare" in q or "month before" in q or "previous" in q:
            intent = "compare"
            is_comp = True
            comp_period = comp_period or prior_period(period)
            comp_pa = _period_args(comp_period)
        if "supporting transactions" in q or "show me the transactions" in q or "transactions supporting" in q:
            coll = _metric_to_search_tool(metric)
            steps.append(ToolStep("search_transactions", {**pa, "collection": coll}, f"Fetching {metric} transactions"))
            return QueryPlan(route="follow_up", intent="evidence", period=period,
                             comparison_period=comp_period, is_comparison=False, steps=steps, metric=metric)
        if "why" in q or "caused" in q or "what changed" in q:
            intent = "investigation"

    # Investigation / cash autopsy
    if intent == "investigation" or (intent == "cash_autopsy"):
        steps.append(ToolStep("get_investigation_data", pa, "Decomposing cash movement"))
        steps.append(ToolStep("get_refunds", pa, "Analyzing refunds"))
        steps.append(ToolStep("get_settlement_summary", pa, "Checking settlements"))
        steps.append(ToolStep("get_receivables_summary", {}, "Checking receivables"))
        steps.append(ToolStep("get_fee_summary", pa, "Checking fees"))
        steps.append(ToolStep("get_reconciliation_exceptions", pa, "Checking reconciliation exceptions"))
        if comp_period:
            steps.append(ToolStep("compare_periods",
                                  {"metric": "cash_received", **pa,
                                   "prior_from": comp_period["from"], "prior_to": comp_period["to"]},
                                  "Comparing periods"))
        return QueryPlan(route="financial", intent="investigation", period=period,
                         comparison_period=comp_period, is_comparison=is_comp, steps=steps, metric="cash_received")

    # Comparison queries
    if is_comp or intent == "compare":
        m = metric or "cash_received"
        cmp_args = {"metric": m, **pa}
        if comp_period:
            cmp_args["prior_from"] = comp_period["from"]
            cmp_args["prior_to"] = comp_period["to"]
        steps.append(ToolStep("compare_periods", cmp_args, f"Comparing {m.replace('_', ' ')}"))
        steps.append(ToolStep(f"get_{_metric_to_tool(m)}", pa, f"Current period {m.replace('_', ' ')}"))
        return QueryPlan(route="financial", intent="compare", period=period,
                         comparison_period=comp_period, is_comparison=True, steps=steps, metric=m)

    # Metric-specific plans
    if metric == "refunds":
        steps.append(ToolStep("get_refunds", pa, "Analyzing refunds"))
        steps.append(ToolStep("get_refund_summary", pa, "Computing refund rate"))
        if is_comp and comp_period:
            steps.append(ToolStep("compare_periods",
                                  {"metric": "refunds", **pa,
                                   "prior_from": comp_period["from"], "prior_to": comp_period["to"]},
                                  "Comparing refund periods"))
        if "largest" in q or "biggest" in q or "top" in q:
            steps.append(ToolStep("search_transactions",
                                  {**pa, "collection": "refunds", "limit": 10},
                                  "Finding largest refunds"))
        return QueryPlan(route="financial", intent="refunds", period=period,
                         comparison_period=comp_period, is_comparison=is_comp, steps=steps, metric="refunds")

    if metric == "receivables_outstanding":
        steps.append(ToolStep("get_receivables_summary", {}, "Summing receivables"))
        steps.append(ToolStep("get_receivables_aging", {}, "Bucketing by age"))
        if "customer" in q or "who" in q:
            steps.append(ToolStep("get_top_customers", {**pa, "limit": 10}, "Ranking customers"))
        return QueryPlan(route="financial", intent="receivables", period=period,
                         comparison_period=comp_period, is_comparison=False, steps=steps,
                         metric="receivables_outstanding")

    if metric == "pending_settlements" or "settlement" in q:
        steps.append(ToolStep("get_settlement_summary", pa, "Checking settlements"))
        if "overdue" in q or "delayed" in q:
            steps.append(ToolStep("search_transactions",
                                  {**pa, "collection": "settlements", "status": "pending", "limit": 20},
                                  "Finding overdue settlements"))
        return QueryPlan(route="financial", intent="settlements", period=period,
                         comparison_period=comp_period, is_comparison=False, steps=steps,
                         metric="pending_settlements")

    if metric == "unreconciled_amount":
        steps.append(ToolStep("get_reconciliation_exceptions", pa, "Finding reconciliation exceptions"))
        steps.append(ToolStep("get_unreconciled_transactions", pa, "Finding unreconciled payments"))
        return QueryPlan(route="financial", intent="unreconciled", period=period,
                         comparison_period=comp_period, is_comparison=False, steps=steps,
                         metric="unreconciled_amount")

    if metric == "failed_payments" or "failed" in q:
        steps.append(ToolStep("get_failed_payments", pa, "Counting failed payments"))
        steps.append(ToolStep("search_transactions",
                              {**pa, "collection": "payments", "status": "failed", "limit": 20},
                              "Listing failed payments"))
        return QueryPlan(route="financial", intent="failed_payments", period=period,
                         comparison_period=comp_period, is_comparison=False, steps=steps,
                         metric="failed_payments")

    if metric == "fee_total":
        steps.append(ToolStep("get_fee_summary", pa, "Analyzing fees"))
        steps.append(ToolStep("get_reconciliation_exceptions", pa, "Checking fee discrepancies"))
        return QueryPlan(route="financial", intent="fees", period=period,
                         comparison_period=comp_period, is_comparison=False, steps=steps, metric="fee_total")

    if metric == "gross_revenue" or "payment" in q:
        steps.append(ToolStep("get_payment_summary", pa, "Measuring payments"))
        if "highest" in q or "largest" in q:
            steps.append(ToolStep("search_transactions",
                                  {**pa, "collection": "payments", "limit": 10},
                                  "Finding largest payments"))
        if "day" in q and ("highest" in q or "volume" in q):
            steps.append(ToolStep("group_metric",
                                  {**pa, "metric": "gross_revenue", "group_by": "day"},
                                  "Grouping by day"))
        if is_comp and comp_period:
            steps.append(ToolStep("compare_periods",
                                  {"metric": "gross_revenue", **pa,
                                   "prior_from": comp_period["from"], "prior_to": comp_period["to"]},
                                  "Comparing revenue periods"))
        return QueryPlan(route="financial", intent="revenue", period=period,
                         comparison_period=comp_period, is_comparison=is_comp, steps=steps,
                         metric="gross_revenue")

    if "duplicate" in q:
        steps.append(ToolStep("get_reconciliation_exceptions", pa, "Finding duplicate payments"))
        return QueryPlan(route="financial", intent="duplicates", period=period,
                         comparison_period=comp_period, is_comparison=False, steps=steps,
                         metric="unreconciled_amount")

    if "unusual" in q or "anomal" in q:
        steps.append(ToolStep("get_investigation_data", pa, "Investigating activity"))
        steps.append(ToolStep("get_reconciliation_exceptions", pa, "Checking exceptions"))
        steps.append(ToolStep("compare_periods",
                              {"metric": "gross_revenue", **pa,
                               "prior_from": prior_period(period)["from"],
                               "prior_to": prior_period(period)["to"]},
                              "Comparing activity levels"))
        return QueryPlan(route="financial", intent="anomaly", period=period,
                         comparison_period=prior_period(period), is_comparison=True, steps=steps,
                         metric="gross_revenue")

    # Amount threshold search: "above ₹50,000"
    m = re.search(r"(?:above|over|greater than|>)\s*(?:₹|rs\.?)?\s*([\d,]+)", q)
    if m:
        amount_paise = int(m.group(1).replace(",", "")) * 100
        steps.append(ToolStep("search_transactions",
                              {**pa, "collection": "payments", "min_amount_paise": amount_paise},
                              f"Searching payments above {m.group(1)}"))
        return QueryPlan(route="financial", intent="search", period=period,
                         comparison_period=comp_period, is_comparison=False, steps=steps,
                         metric="gross_revenue")

    if "top customer" in q or "biggest customer" in q:
        steps.append(ToolStep("get_top_customers", {**pa, "limit": 10}, "Ranking customers"))
        return QueryPlan(route="financial", intent="top_customers", period=period,
                         comparison_period=comp_period, is_comparison=False, steps=steps,
                         metric="gross_revenue")

    if "top product" in q or "product" in q and "refund" in q:
        steps.append(ToolStep("get_top_products", {**pa, "limit": 10}, "Ranking products"))
        return QueryPlan(route="financial", intent="top_products", period=period,
                         comparison_period=comp_period, is_comparison=False, steps=steps,
                         metric="refunds")

    if "summary" in q and ("90 day" in q or "last" in q):
        steps.append(ToolStep("get_payment_summary", pa, "Payment summary"))
        steps.append(ToolStep("get_refund_summary", pa, "Refund summary"))
        steps.append(ToolStep("get_settlement_summary", pa, "Settlement summary"))
        steps.append(ToolStep("get_cash_flow", pa, "Cash flow"))
        return QueryPlan(route="financial", intent="overview", period=period,
                         comparison_period=comp_period, is_comparison=False, steps=steps,
                         metric="gross_revenue")

    # Default overview
    for tool, label in [("get_payment_summary", "Payments"), ("get_refund_summary", "Refunds"),
                        ("get_settlement_summary", "Settlements"), ("get_cash_flow", "Cash flow")]:
        steps.append(ToolStep(tool, pa, label))
    return QueryPlan(route="financial", intent="overview", period=period,
                     comparison_period=comp_period, is_comparison=False, steps=steps,
                     metric="gross_revenue")


def _classify_intent(q: str, metric: str | None, context: dict | None) -> str:
    if _is_investigation(q) and ("cash" in q or metric == "cash_received"):
        return "investigation"
    if "cash" in q and any(w in q for w in ("decrease", "decline", "fall", "drop", "why", "change")):
        return "investigation"
    if _is_comparison(q):
        return "compare"
    if metric == "refunds":
        return "refunds"
    if metric == "receivables_outstanding":
        return "receivables"
    if metric == "pending_settlements":
        return "settlements"
    if metric == "gross_revenue":
        return "revenue"
    if metric == "unreconciled_amount":
        return "unreconciled"
    return context.get("intent", "overview") if context else "overview"


def _metric_to_tool(metric: str) -> str:
    mapping = {
        "refunds": "refunds", "cash_received": "cash_received", "gross_revenue": "revenue",
        "pending_settlements": "pending_settlements", "receivables_outstanding": "receivables",
        "fee_total": "fees", "unreconciled_amount": "unreconciled_transactions",
        "failed_payments": "failed_payments",
    }
    return mapping.get(metric, metric)


def _metric_to_search_tool(metric: str) -> str:
    mapping = {
        "refunds": "refunds", "cash_received": "settlements", "gross_revenue": "payments",
        "pending_settlements": "settlements", "fee_total": "payments",
    }
    return mapping.get(metric, "payments")


# Backward-compatible intent classifier (used by tests)
PLAN_KEYWORDS = [
    ("cash_autopsy", ["cash decrease", "cash decline", "cash fall", "cash drop", "where is my cash",
                      "cash stuck", "why did cash", "what happened to my cash", "what changed"]),
    ("top_products", ["top product", "which product", "product refund", "products driving",
                      "products are driving", "highest refund"]),
    ("top_customers", ["top customer", "biggest customer", "highest revenue customer"]),
    ("refunds", ["refund", "returned", "chargeback"]),
    ("receivables", ["owe", "receivable", "outstanding", "unpaid", "collect", "who owes"]),
    ("settlements", ["settlement", "settle", "payout", "delayed", "pending"]),
    ("revenue", ["revenue", "sales", "income", "top line"]),
    ("compare", ["compare", "vs", "versus", "month over month", "this month with", "against"]),
    ("unreconciled", ["unreconciled", "unexplained", "difference", "not matching", "mismatch"]),
]


def classify_intent(question: str) -> str:
    q = question.lower()
    for intent, kws in PLAN_KEYWORDS:
        if any(k in q for k in kws):
            return intent
    return "overview"
