"""Scenario Simulator + Counterfactual analysis. All projections are computed
deterministically from a real current baseline. Simulated values are clearly
labelled and never mixed with historical facts.
"""
from .engine import FinancialEngine, resolve_period
from .money import format_inr


async def baseline(org_id: str, source: str = "DEMO"):
    eng = FinancialEngine(org_id, source)
    p = resolve_period("current")
    cash = await eng.cash_received(p)
    refunds = await eng.refunds(p)
    pending = await eng.pending_settlements(p)
    receivables = await eng.receivables_outstanding(p)
    gross = await eng.gross_revenue(p)
    fees = await eng.fee_total(p)
    return {
        "cash_received": cash["value"], "refunds": refunds["value"],
        "pending_settlements": pending["value"], "receivables": receivables["value"],
        "gross_revenue": gross["value"], "fees": fees["value"],
    }


async def simulate(org_id: str, inputs: dict, source: str = "DEMO"):
    """inputs (all optional):
      refund_change_pct, settlement_clear_pct, payment_volume_change_pct,
      avg_payment_change_pct, receivables_collect_pct, fee_change_pct
    Returns current vs scenario vs delta for projected cash position.
    """
    base = await baseline(org_id, source)

    refund_change = inputs.get("refund_change_pct", 0) / 100.0
    settle_clear = inputs.get("settlement_clear_pct", 0) / 100.0
    vol_change = inputs.get("payment_volume_change_pct", 0) / 100.0
    recv_collect = inputs.get("receivables_collect_pct", 0) / 100.0
    fee_change = inputs.get("fee_change_pct", 0) / 100.0

    # Deterministic projection: projected available cash position.
    projected_refunds = int(base["refunds"] * (1 + refund_change))
    refund_effect = base["refunds"] - projected_refunds  # positive = cash saved

    settlement_effect = int(base["pending_settlements"] * settle_clear)
    receivables_effect = int(base["receivables"] * recv_collect)
    revenue_effect = int(base["gross_revenue"] * vol_change)
    fee_effect = -int(base["fees"] * fee_change)

    projected_cash = (base["cash_received"] + refund_effect + settlement_effect
                      + receivables_effect + revenue_effect + fee_effect)
    delta = projected_cash - base["cash_received"]

    def row(label, cur, scen):
        return {"label": label, "current": cur, "current_display": format_inr(cur),
                "scenario": scen, "scenario_display": format_inr(scen),
                "delta": scen - cur, "delta_display": format_inr(scen - cur)}

    return {
        "label": "SIMULATION",
        "disclaimer": "Projected values are SIMULATED from the current baseline and are not historical facts.",
        "inputs": inputs,
        "baseline_cash": base["cash_received"],
        "baseline_cash_display": format_inr(base["cash_received"]),
        "projected_cash": projected_cash,
        "projected_cash_display": format_inr(projected_cash),
        "delta": delta, "delta_display": format_inr(delta),
        "breakdown": [
            row("Refund change", 0, refund_effect),
            row("Pending settlements cleared", 0, settlement_effect),
            row("Receivables collected", 0, receivables_effect),
            row("Payment volume change", 0, revenue_effect),
            row("Fee change", 0, fee_effect),
        ],
    }


async def counterfactual(org_id: str, kind: str, source: str = "DEMO"):
    """Named counterfactuals. Clearly labelled COUNTERFACTUAL/PROJECTED."""
    base = await baseline(org_id, source)
    if kind == "no_refunds":
        projected = base["cash_received"] + base["refunds"]
        desc = "Cash if no refunds had been issued this period."
    elif kind == "settlements_cleared":
        projected = base["cash_received"] + base["pending_settlements"]
        desc = "Cash if all pending settlements had cleared."
    elif kind == "refunds_down_10":
        projected = base["cash_received"] + int(base["refunds"] * 0.10)
        desc = "Cash if the refund rate were reduced by 10%."
    else:
        projected = base["cash_received"]
        desc = "Unknown counterfactual."
    return {
        "label": "COUNTERFACTUAL",
        "kind": kind,
        "description": desc,
        "actual_cash": base["cash_received"], "actual_cash_display": format_inr(base["cash_received"]),
        "counterfactual_cash": projected, "counterfactual_cash_display": format_inr(projected),
        "difference": projected - base["cash_received"],
        "difference_display": format_inr(projected - base["cash_received"]),
        "disclaimer": "This is a COUNTERFACTUAL projection, not a historical fact.",
    }
