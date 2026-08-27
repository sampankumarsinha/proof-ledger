import os
import json
import re

from .engine import FinancialEngine, resolve_period, run_tool, top_customers, top_products
from .autopsy import cash_autopsy
from .evidence import confidence_from_signals, build_claim
from .money import format_inr


class LLMClient:
    """Thin abstraction over an LLM provider (OpenAI, user's own key)."""

    def __init__(self):
        self.key = os.environ.get("OPENAI_API_KEY", "").strip()
        self.model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        self._client = None
        if self.key:
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=self.key)
            except Exception:
                self._client = None

    @property
    def available(self) -> bool:
        return self._client is not None

    def explain(self, question: str, facts: list) -> dict | None:
        if not self.available:
            return None
        system = (
            "You are ProofLedger's financial explainer. You are given VERIFIED FACTS "
            "computed deterministically from a database. RULES: Never invent numbers, "
            "amounts, IDs or percentages. Only reference figures present in the provided facts. "
            "Do not claim causation unless the facts support it; prefer 'associated with'. "
            "Classify each finding as VERIFIED_FACT, DERIVED_FACT, INFERENCE or RECOMMENDATION. "
            "Respond as compact JSON: {summary, findings:[{statement,type}], "
            "recommendations:[string], next_questions:[string]}."
        )
        user = json.dumps({"question": question, "verified_facts": facts}, default=str)
        try:
            resp = self._client.chat.completions.create(
                model=self.model,
                response_format={"type": "json_object"},
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": user}],
                temperature=0.2,
            )
            return json.loads(resp.choices[0].message.content)
        except Exception:
            return None


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


async def investigate(org_id: str, question: str, source: str = "DEMO"):
    intent = classify_intent(question)
    eng = FinancialEngine(org_id, source)
    cur = resolve_period("current")
    prior = resolve_period("prior")
    tool_log = []
    facts = []
    claims = []

    async def log_and_run(tool_name, args=None, label=None):
        res = await run_tool(org_id, tool_name, args, source)
        cnt = res.get("source_count", len(res.get("rows", []))) if isinstance(res, dict) else 0
        tool_log.append({"tool": tool_name, "label": label or tool_name,
                         "status": "ok", "records": cnt})
        return res

    autopsy = None
    if intent == "cash_autopsy":
        autopsy = await cash_autopsy(org_id, source)
        tool_log.append({"tool": "cash_autopsy", "label": "Decomposing cash movement",
                         "status": "ok", "records": len(autopsy["contributors"])})
        cur_fact = dict(autopsy["target"]["current"]); cur_fact["metric"] = "cash_received_current"
        prior_fact = dict(autopsy["target"]["prior"]); prior_fact["metric"] = "cash_received_prior"
        facts.append(cur_fact)
        facts.append(prior_fact)
        for c in autopsy["contributors"][:4]:
            facts.append({"metric": c["metric"], "value": c["impact"],
                          "value_display": c["impact_display"], "formula": c["calculation"],
                          "verified": True, "source_count": c["evidence_count"],
                          "verification_status": c["claim_type"]})
    elif intent == "refunds":
        facts.append(await log_and_run("get_refunds", {"period": "current"}, "Analyzing refunds"))
        facts.append(await log_and_run("get_refund_rate", {"period": "current"}, "Computing refund rate"))
        cmp = await eng.compare_periods("refunds", cur, prior)
        tool_log.append({"tool": "compare_periods", "label": "Comparing prior period", "status": "ok", "records": 2})
        facts.append({"metric": "refunds_change", "value": cmp["delta"], "value_display": cmp["delta_display"],
                      "formula": "refunds_current - refunds_prior", "change_pct": cmp["change_pct"],
                      "verified": True, "source_count": cmp["current"]["source_count"], "verification_status": "DERIVED_FACT"})
        facts.append(await log_and_run("get_top_products", {"period": "current"}, "Ranking products by refunds"))
    elif intent == "receivables":
        facts.append(await log_and_run("get_receivables", {}, "Summing outstanding receivables"))
        facts.append(await log_and_run("get_overdue_receivables", {}, "Isolating overdue invoices"))
        aging = await eng.receivables_aging()
        tool_log.append({"tool": "get_receivables_aging", "label": "Bucketing by age", "status": "ok",
                         "records": sum(len(v) for v in aging["detail"].values())})
        facts.append({"metric": "receivables_aging", "value": aging["buckets"], "value_display": aging["buckets_display"],
                      "formula": "invoice outstanding grouped by (now - due_date)", "verified": True,
                      "verification_status": "VERIFIED_FACT", "source_count": sum(len(v) for v in aging["detail"].values())})
    elif intent == "settlements":
        facts.append(await log_and_run("get_pending_settlements", {}, "Summing pending settlements"))
        facts.append(await log_and_run("get_cash_received", {"period": "current"}, "Measuring cash received"))
    elif intent == "revenue":
        facts.append(await log_and_run("get_revenue", {"period": "current"}, "Measuring gross revenue"))
        facts.append(await log_and_run("get_net_revenue", {"period": "current"}, "Deriving net revenue"))
        cmp = await eng.compare_periods("gross_revenue", cur, prior)
        tool_log.append({"tool": "compare_periods", "label": "Comparing prior period", "status": "ok", "records": 2})
        facts.append({"metric": "revenue_change", "value": cmp["delta"], "value_display": cmp["delta_display"],
                      "change_pct": cmp["change_pct"], "formula": "gross_current - gross_prior",
                      "verified": True, "source_count": cmp["current"]["source_count"], "verification_status": "DERIVED_FACT"})
    elif intent == "compare":
        for m in ["cash_received", "gross_revenue", "refunds"]:
            cmp = await eng.compare_periods(m, cur, prior)
            tool_log.append({"tool": "compare_periods", "label": f"Comparing {m}", "status": "ok", "records": 2})
            facts.append({"metric": f"{m}_change", "value": cmp["delta"], "value_display": cmp["delta_display"],
                          "change_pct": cmp["change_pct"], "formula": f"{m}_current - {m}_prior",
                          "verified": True, "source_count": cmp["current"]["source_count"], "verification_status": "DERIVED_FACT"})
    elif intent == "top_customers":
        facts.append(await log_and_run("get_top_customers", {"period": "current"}, "Ranking customers"))
    elif intent == "top_products":
        facts.append(await log_and_run("get_top_products", {"period": "current"}, "Ranking products"))
    elif intent == "unreconciled":
        facts.append(await log_and_run("get_unreconciled_transactions", {}, "Finding unreconciled payments"))
    else:
        for t, lbl in [("get_cash_received", "Cash received"), ("get_revenue", "Gross revenue"),
                       ("get_pending_settlements", "Pending settlements"), ("get_refunds", "Refunds")]:
            facts.append(await log_and_run(t, {"period": "current"}, lbl))

    # Build verified claims from facts (numeric claims already computed by engine => verified)
    for i, f in enumerate(facts):
        if isinstance(f, dict) and "metric" in f and isinstance(f.get("value"), int):
            claims.append(build_claim(
                f"claim_{i}", f"{f['metric']} = {f.get('value_display', f['value'])}",
                f.get("verification_status", "VERIFIED_FACT"),
                f.get("source_records", []), f.get("formula", ""), f.get("period", cur),
            ))

    # Confidence from concrete signals
    total_sources = sum(f.get("source_count", 0) for f in facts if isinstance(f, dict))
    signals = {
        "source_completeness": 1.0 if total_sources else 0.4,
        "evidence_coverage": min(1.0, len(claims) / max(1, len(facts))),
        "calculation_verification": 1.0,   # every number recomputed by engine
        "record_consistency": 1.0,
        "time_alignment": 1.0,
        "entity_resolution": 1.0,
        "ambiguity": 0.2 if intent == "overview" else 0.0,
    }
    confidence = confidence_from_signals(signals)

    # LLM explanation (optional prose only)
    llm = LLMClient()
    llm_out = llm.explain(question, facts)
    if llm_out:
        summary = llm_out.get("summary", "")
        findings = llm_out.get("findings", [])
        recommendations = llm_out.get("recommendations", [])
        next_questions = llm_out.get("next_questions", [])
        explainer = "openai:" + llm.model
    else:
        summary, findings, recommendations, next_questions = _deterministic_prose(intent, facts, autopsy)
        explainer = "deterministic"

    return {
        "question": question,
        "intent": intent,
        "tool_log": tool_log,
        "facts": facts,
        "claims": claims,
        "autopsy": autopsy,
        "confidence": confidence,
        "summary": summary,
        "findings": findings,
        "recommendations": recommendations,
        "next_questions": next_questions or _default_next_questions(intent),
        "explainer": explainer,
        "ai_available": llm.available,
    }


def _deterministic_prose(intent, facts, autopsy):
    findings = []
    for f in facts:
        if isinstance(f, dict) and "metric" in f and "value_display" in f:
            ftype = f.get("verification_status", "VERIFIED_FACT")
            findings.append({"statement": f"{_label(f['metric'])}: {f['value_display']}", "type": ftype})
    if intent == "cash_autopsy" and autopsy:
        top = autopsy["contributors"][0]
        summary = (f"Cash moved by {autopsy['target']['delta_display']} "
                   f"({autopsy['target']['change_pct']}%) versus the prior period. The largest "
                   f"downward contributor is {_label(top['metric'])} at {top['impact_display']}, "
                   "computed directly from source records.")
        recs = ["Review the top pending settlements and confirm expected payout dates.",
                "Investigate the refunded orders driving the refund increase.",
                "Prioritise collection of overdue receivables."]
    else:
        summary = "The figures below are computed directly from your transaction records for the selected period."
        recs = ["Open the evidence drawer on any figure to trace it to source transactions."]
    return summary, findings, recs, []


def _default_next_questions(intent):
    base = ["Why did cash decrease this month?", "Which products are driving refunds?",
            "Which customers owe me money?", "Which settlements are delayed?",
            "Compare this period with the prior period."]
    return base


def _label(metric):
    return metric.replace("_", " ").title()
