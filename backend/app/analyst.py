"""Dynamic AI Analyst core: executes multi-step query plans using approved backend tools.

CRITICAL TRUST RULE:
The LLM never invents or calculates financial numbers.
All figures come from MongoDB records processed through FinancialEngine / tools.
The LLM is a planner and explainer only.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Optional

from .autopsy import cash_autopsy
from .engine import FinancialEngine, run_tool
from .evidence import build_claim, confidence_from_signals
from .money import format_inr
from .planner import QueryPlan, classify_intent, plan_query


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
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=0.2,
            )
            return json.loads(resp.choices[0].message.content)
        except Exception:
            return None

    def explain_general(self, question: str) -> dict | None:
        if not self.available:
            return None
        system = (
            "You are ProofLedger's financial educator. Answer general financial "
            "or accounting questions clearly and concisely. Do not invent transaction data. "
            "Respond as compact JSON: {summary, findings:[{statement,type}], recommendations:[string], next_questions:[string]}."
        )
        try:
            resp = self._client.chat.completions.create(
                model=self.model,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": question},
                ],
                temperature=0.3,
            )
            return json.loads(resp.choices[0].message.content)
        except Exception:
            return None


async def investigate(
    org_id: str,
    question: str,
    source: str = "DEMO",
    context: Optional[dict] = None,
) -> dict:
    """Execute dynamic multi-step financial investigation or general explanation."""
    plan: QueryPlan = plan_query(question, context)
    eng = FinancialEngine(org_id, source)
    llm = LLMClient()

    # --- GENERAL KNOWLEDGE ROUTE ---
    if plan.route == "general":
        llm_out = llm.explain_general(question)
        if llm_out:
            summary = llm_out.get("summary", "")
            findings = llm_out.get("findings", [])
            recs = llm_out.get("recommendations", [])
            next_q = llm_out.get("next_questions", [])
            explainer = "openai:" + llm.model
        else:
            summary = _general_fallback_explanation(question)
            findings = [{"statement": summary, "type": "VERIFIED_FACT"}]
            recs = ["Ask a question about your live database records to see verified financial calculations."]
            next_q = ["How much did we receive this month?", "Why did cash decrease this month?"]
            explainer = "deterministic"

        return {
            "question": question,
            "intent": "general",
            "route": "general",
            "period": plan.period,
            "comparison_period": plan.comparison_period,
            "tool_log": [],
            "facts": [],
            "claims": [],
            "autopsy": None,
            "confidence": {
                "score": 100,
                "band": "HIGH",
                "explanation": "General financial knowledge question.",
            },
            "summary": summary,
            "findings": findings,
            "recommendations": recs,
            "next_questions": next_q,
            "explainer": explainer,
            "ai_available": llm.available,
            "context": {"intent": "general", "metric": None, "period": None, "comparison_period": None},
        }

    # --- FINANCIAL & FOLLOW-UP ROUTE ---
    tool_log = []
    facts = []
    claims = []
    autopsy = None

    async def log_and_run(tool_name: str, args: dict | None = None, label: str | None = None) -> Any:
        res = await run_tool(org_id, tool_name, args, source)
        cnt = 0
        if isinstance(res, dict):
            cnt = res.get("transaction_count", res.get("returned_count", res.get("total_count", len(res.get("rows", [])))))
        tool_log.append({
            "tool": tool_name,
            "label": label or tool_name,
            "status": "ok",
            "records": cnt,
        })
        return res

    for step in plan.steps:
        res = await log_and_run(step.tool, step.args, step.label)
        if isinstance(res, dict):
            facts.append(res)

    if plan.intent in ("cash_autopsy", "investigation") and not autopsy:
        autopsy = await cash_autopsy(org_id, source, plan.period, plan.comparison_period)
        if not any(t["tool"] == "cash_autopsy" for t in tool_log):
            tool_log.insert(0, {
                "tool": "cash_autopsy",
                "label": "Decomposing cash movement",
                "status": "ok",
                "records": len(autopsy["contributors"]),
            })
        facts.append({
            "metric": "cash_received_current",
            "value": autopsy["target"]["current"]["value"],
            "value_display": autopsy["target"]["current"]["value_display"],
            "period": plan.period,
            "evidence_ids": autopsy["target"]["current"].get("source_records", []),
        })
        facts.append({
            "metric": "cash_received_prior",
            "value": autopsy["target"]["prior"]["value"],
            "value_display": autopsy["target"]["prior"]["value_display"],
            "period": plan.comparison_period,
            "evidence_ids": autopsy["target"]["prior"].get("source_records", []),
        })

    # Build claims with evidence
    for i, f in enumerate(facts):
        if isinstance(f, dict) and "metric" in f:
            val_disp = f.get("value_display") or f.get("amount_display") or str(f.get("value", f.get("amount_paise", "")))
            ev_ids = f.get("evidence_ids", f.get("source_records", []))
            claims.append(build_claim(
                claim_id=f"claim_{i}",
                text=f"{_label(f['metric'])} = {val_disp}",
                claim_type=f.get("verification_status", "VERIFIED_FACT"),
                source_records=ev_ids,
                calculation=f.get("formula", f.get("calculation", "")),
                period=f.get("period", plan.period),
            ))

    # Empty data check
    is_empty = False
    has_data_records = any(
        isinstance(f, dict) and (
            f.get("amount_paise", 0) > 0 or
            f.get("transaction_count", 0) > 0 or
            f.get("returned_count", 0) > 0 or
            len(f.get("rows", [])) > 0 or
            f.get("gross_revenue_paise", 0) > 0
        )
        for f in facts
    )
    if not has_data_records and not autopsy:
        is_empty = True

    # Confidence score
    total_sources = sum(
        f.get("transaction_count", f.get("source_count", len(f.get("rows", []))))
        for f in facts if isinstance(f, dict)
    )
    signals = {
        "source_completeness": 1.0 if (total_sources or not is_empty) else 0.2,
        "evidence_coverage": min(1.0, len(claims) / max(1, len(facts))),
        "calculation_verification": 1.0,
        "record_consistency": 1.0,
        "time_alignment": 1.0,
        "entity_resolution": 1.0,
        "ambiguity": 0.0 if plan.intent != "overview" else 0.1,
    }
    confidence = confidence_from_signals(signals)

    # LLM prose vs Deterministic prose
    llm_out = llm.explain(question, facts)
    if llm_out:
        summary = llm_out.get("summary", "")
        findings = llm_out.get("findings", [])
        recommendations = llm_out.get("recommendations", [])
        next_questions = llm_out.get("next_questions", [])
        explainer = "openai:" + llm.model
    else:
        summary, findings, recommendations, next_questions = _deterministic_prose(
            plan.intent, facts, autopsy, plan.period, is_empty
        )
        explainer = "deterministic"

    next_questions = next_questions or _generate_next_questions(plan, facts)

    new_context = {
        "intent": plan.intent,
        "metric": plan.metric,
        "period": plan.period,
        "comparison_period": plan.comparison_period,
        "last_question": question,
    }

    return {
        "question": question,
        "intent": plan.intent,
        "route": plan.route,
        "period": plan.period,
        "comparison_period": plan.comparison_period,
        "tool_log": tool_log,
        "facts": facts,
        "claims": claims,
        "autopsy": autopsy,
        "confidence": confidence,
        "summary": summary,
        "findings": findings,
        "recommendations": recommendations,
        "next_questions": next_questions,
        "explainer": explainer,
        "ai_available": llm.available,
        "context": new_context,
    }


def _deterministic_prose(intent: str, facts: list, autopsy: dict | None, period: dict, is_empty: bool):
    if is_empty:
        period_lbl = period.get("label") or "the selected period"
        summary = f"No payment or financial records were found for {period_lbl}, so metrics cannot be calculated."
        findings = [{"statement": f"No transactions recorded for {period_lbl}.", "type": "VERIFIED_FACT"}]
        recs = ["Check if the date range covers active trading periods or sync live Razorpay data."]
        return summary, findings, recs, []

    findings = []
    for f in facts:
        if not isinstance(f, dict):
            continue
        metric_name = f.get("metric", "")
        disp = f.get("amount_display") or f.get("value_display") or f.get("gross_revenue_display")
        if metric_name and disp:
            ftype = f.get("verification_status", "VERIFIED_FACT")
            findings.append({"statement": f"{_label(metric_name)}: {disp}", "type": ftype})
        elif f.get("rows"):
            count = len(f["rows"])
            coll = f.get("collection", "transactions")
            findings.append({"statement": f"Found {count} matching {coll} records.", "type": "VERIFIED_FACT"})
        elif f.get("current_display") and f.get("difference_display"):
            findings.append({
                "statement": f"{_label(metric_name)} changed by {f['difference_display']} ({f.get('change_pct', 0)}%) versus prior period.",
                "type": "DERIVED_FACT",
            })

    if intent in ("cash_autopsy", "investigation") and autopsy:
        top = autopsy["contributors"][0]
        summary = (
            f"Cash received shifted by {autopsy['target']['delta_display']} "
            f"({autopsy['target']['change_pct']}%) versus the comparison period. "
            f"The primary downward movement is associated with {_label(top['metric'])} ({top['impact_display']}), "
            "computed deterministically from source records."
        )
        recs = [
            "Review pending settlements to confirm expected payout dates.",
            "Investigate refunded orders to identify specific product or customer causes.",
            "Prioritise collection of overdue receivables.",
        ]
    else:
        period_lbl = period.get("label", "selected period")
        summary = f"Financial calculations computed directly from source records for {period_lbl}."
        recs = ["Click 'Show Proof' on any finding to inspect supporting source transactions."]

    return summary, findings, recs, []


def _generate_next_questions(plan: QueryPlan, facts: list) -> list[str]:
    m = plan.metric
    if m == "refunds" or plan.intent == "refunds":
        return [
            "Which products are driving refunds?",
            "Compare refunds this month versus last month.",
            "Show me the largest refunds.",
        ]
    if m == "receivables_outstanding" or plan.intent == "receivables":
        return [
            "Which customers have the highest outstanding receivables?",
            "Which invoices are overdue?",
            "Show me receivables aging breakdown.",
        ]
    if m == "pending_settlements" or plan.intent == "settlements":
        return [
            "Which settlements are delayed?",
            "Compare settlements with gross revenue.",
            "Why did cash decrease this month?",
        ]
    if plan.intent in ("cash_autopsy", "investigation"):
        return [
            "Break this down by day.",
            "Show supporting transactions.",
            "Compare with last quarter.",
        ]
    return [
        "Why did cash decrease this month?",
        "Compare this month with last month.",
        "Which products are driving refunds?",
        "Show supporting transactions.",
    ]


def _general_fallback_explanation(question: str) -> str:
    q = question.lower()
    if "settlement" in q:
        return (
            "A settlement is the payout transfer of captured payment funds from your payment processor "
            "(e.g., Razorpay) to your bank account, minus fees and chargebacks."
        )
    if "refund" in q:
        return (
            "A refund is the return of funds to a customer for a previously captured payment, "
            "reversing gross revenue."
        )
    if "receivable" in q:
        return (
            "Receivables represent outstanding invoice balances owed to your business by customers "
            "for delivered goods or services."
        )
    if "reconciliation" in q:
        return (
            "Reconciliation is the process of matching captured payments against bank settlement statements "
            "to ensure every rupee is accounted for."
        )
    return "ProofLedger deterministically computes financial metrics and verifies every claim against database records."


def _label(metric: str) -> str:
    return metric.replace("_", " ").title()
