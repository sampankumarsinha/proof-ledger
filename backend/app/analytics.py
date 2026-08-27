"""Transparent rolling baselines + attention queue. Fully deterministic:
the baseline is the prior comparable period; deviation and status use fixed,
published thresholds. Nothing is called an anomaly/fraud without evidence.
"""
from .engine import FinancialEngine, resolve_period
from .reconciliation import reconcile
from .money import format_inr, pct

NORMAL, ELEVATED, UNUSUAL = "NORMAL", "ELEVATED", "UNUSUAL"


def _status(dev_pct: float) -> str:
    a = abs(dev_pct)
    if a <= 15:
        return NORMAL
    if a <= 40:
        return ELEVATED
    return UNUSUAL


async def baselines(org_id: str, source: str = "DEMO"):
    eng = FinancialEngine(org_id, source)
    cur = resolve_period("current")
    prior = resolve_period("prior")
    specs = [
        ("Payment volume", "gross_revenue", False),
        ("Refund rate", "refund_rate", True),
        ("Settlement cash", "cash_received", False),
        ("Processing fees", "fee_total", False),
    ]
    out = []
    for label, fn, is_rate in specs:
        c = await getattr(eng, fn)(cur)
        p = await getattr(eng, fn)(prior)
        cur_v, base_v = c["value"], p["value"]
        dev = round(cur_v - base_v, 2) if is_rate else pct(cur_v - base_v, base_v)
        status = _status(dev)
        out.append({
            "metric": label,
            "current": f"{cur_v}%" if is_rate else format_inr(cur_v),
            "baseline": f"{base_v}%" if is_rate else format_inr(base_v),
            "deviation_pct": dev if not is_rate else round(cur_v - base_v, 2),
            "deviation_display": (f"{'+' if (cur_v-base_v) >= 0 else ''}{round(cur_v-base_v,2)} pts"
                                  if is_rate else f"{'+' if dev >= 0 else ''}{dev}%"),
            "status": status,
            "rule": "NORMAL ≤15% deviation · ELEVATED ≤40% · UNUSUAL >40% (vs prior period)",
        })
    return {"baselines": out}


async def attention(org_id: str, source: str = "DEMO"):
    eng = FinancialEngine(org_id, source)
    cur = resolve_period("current")
    prior = resolve_period("prior")
    items = []

    pending = await eng.pending_settlements(cur)
    if pending["value"] > 0:
        items.append({"type": "pending_settlement", "reason": "Captured funds not yet settled to bank",
                      "amount": pending["value_display"], "severity": "high",
                      "evidence": f"{pending['source_count']} pending settlements",
                      "metric": "pending_settlements",
                      "recommended_action": "Review settlement schedule with payment provider"})

    overdue = await eng.overdue_receivables()
    if overdue["value"] > 0:
        items.append({"type": "overdue_receivables", "reason": "Invoices past due date",
                      "amount": overdue["value_display"], "severity": "medium",
                      "evidence": f"{overdue['source_count']} overdue invoices",
                      "metric": "overdue_receivables",
                      "recommended_action": "Trigger collection follow-up"})

    unrec = await eng.unreconciled_amount()
    rec = await reconcile(org_id, source=source)
    if unrec["value"] > 0 or rec["exceptions"]:
        items.append({"type": "reconciliation_exception", "reason": "Payments without a clean settlement match",
                      "amount": unrec["value_display"], "severity": "high",
                      "evidence": f"{len(rec['exceptions'])} reconciliation exceptions",
                      "metric": "unreconciled_amount",
                      "recommended_action": "Investigate exceptions in the Reconciliation Center"})

    fee_diff = rec["summary"].get("FEE_DIFFERENCE", {}).get("count", 0)
    if fee_diff:
        items.append({"type": "fee_discrepancy", "reason": "Recorded fees differ from the contracted schedule",
                      "amount": rec["summary"]["FEE_DIFFERENCE"]["amount_display"], "severity": "medium",
                      "evidence": f"{fee_diff} payments with fee differences",
                      "metric": "fee_total",
                      "recommended_action": "Raise a fee reconciliation query with the provider"})

    ref_cmp = await eng.compare_periods("refunds", cur, prior)
    if ref_cmp["change_pct"] > 20:
        items.append({"type": "refund_spike", "reason": f"Refunds up {ref_cmp['change_pct']}% vs prior period",
                      "amount": ref_cmp["current"]["value_display"], "severity": "medium",
                      "evidence": f"{ref_cmp['current']['source_count']} refunds this period",
                      "metric": "refunds",
                      "recommended_action": "Review the top refunded products and reasons"})

    base = await baselines(org_id, source)
    for b in base["baselines"]:
        if b["status"] == UNUSUAL:
            items.append({"type": "unusual_movement", "reason": f"{b['metric']} is unusual vs baseline",
                          "amount": b["current"], "severity": "medium",
                          "evidence": f"Current {b['current']} vs baseline {b['baseline']} ({b['deviation_display']})",
                          "metric": None,
                          "recommended_action": "Open an investigation to explain the movement"})

    order = {"high": 0, "medium": 1, "low": 2}
    items.sort(key=lambda x: order.get(x["severity"], 3))
    return {"items": items, "count": len(items)}
