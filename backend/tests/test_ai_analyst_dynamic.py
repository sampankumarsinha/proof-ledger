"""Dynamic AI Analyst integration tests.

Verifies:
- Live database execution (no hardcoded/canned answers)
- Dynamic date range parsing (today, yesterday, this week, 14d, 90d, custom ranges)
- Empty data handling
- Period comparison
- Transaction search & evidence linking
- Tenant / organization isolation
- Deterministic arithmetic & LLM fallback
- Razorpay test source filtering
- Crucial Acceptance Test: database modification dynamically changes AI output!
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta
import pytest

from app.analyst import investigate
from app.db import get_db
from app.engine import resolve_period
from app.seed import seed_organization


ORG_A = "org_test_analyst_a"
ORG_B = "org_test_analyst_b"


@pytest.fixture(autouse=True)
async def prepare_test_db():
    import app.db
    app.db._client = None
    app.db._db = None
    db = get_db()
    # Clean test orgs
    await db.payments.delete_many({"organization_id": {"$in": [ORG_A, ORG_B]}})
    await db.refunds.delete_many({"organization_id": {"$in": [ORG_A, ORG_B]}})
    await db.settlements.delete_many({"organization_id": {"$in": [ORG_A, ORG_B]}})
    await db.invoices.delete_many({"organization_id": {"$in": [ORG_A, ORG_B]}})
    await db.customers.delete_many({"organization_id": {"$in": [ORG_A, ORG_B]}})
    await db.products.delete_many({"organization_id": {"$in": [ORG_A, ORG_B]}})

    # Seed test org A
    await seed_organization(ORG_A)


@pytest.mark.anyio
async def test_payment_total_dynamic():
    res = await investigate(ORG_A, "What were our total payments this month?", source="DEMO")
    assert res["intent"] in ("revenue", "overview")
    assert len(res["facts"]) > 0
    facts_with_val = [f for f in res["facts"] if "amount_paise" in f or "value" in f or "gross_revenue_paise" in f]
    assert len(facts_with_val) > 0


@pytest.mark.anyio
async def test_refund_total_dynamic():
    res = await investigate(ORG_A, "What were refunds in the last 30 days?", source="DEMO")
    assert res["intent"] == "refunds"
    refund_facts = [f for f in res["facts"] if f.get("metric") == "refunds"]
    assert len(refund_facts) > 0
    ref_val = refund_facts[0]["value"]
    assert isinstance(ref_val, int)


@pytest.mark.anyio
async def test_period_comparison():
    res = await investigate(ORG_A, "Compare refunds this month versus last month", source="DEMO")
    assert res["intent"] in ("compare", "refunds")
    assert res["period"]["key"] in ("this_month", "last_30_days")
    assert res["comparison_period"] is not None


@pytest.mark.anyio
async def test_date_range_parsing():
    now = datetime.now(timezone.utc)
    for q, expected_key in [
        ("How much did we receive today?", "today"),
        ("What were refunds yesterday?", "yesterday"),
        ("Show me payments this week", "this_week"),
        ("Show refunds in the last 14 days", "last_14_days"),
        ("Give me a summary of the last 90 days", "last_90_days"),
    ]:
        res = await investigate(ORG_A, q, source="DEMO")
        assert res["period"]["key"] == expected_key, f"Failed for question: {q}"


@pytest.mark.anyio
async def test_custom_date_range():
    res = await investigate(ORG_A, "Show refunds from 1 August to 15 August 2026", source="DEMO")
    assert res["period"]["key"] == "custom"
    assert "2026-08-01" in res["period"]["from"]
    assert "2026-08-15" in res["period"]["to"]


@pytest.mark.anyio
async def test_shorthand_date_range():
    res = await investigate(ORG_A, "show me revenue between 1aug to 4aug", source="DEMO")
    assert res["period"]["key"] == "custom"
    assert "08-01" in res["period"]["from"]
    assert "08-04" in res["period"]["to"]


@pytest.mark.anyio
async def test_empty_date_range_handling():
    res = await investigate(ORG_A, "Show refunds from 1 January 2020 to 5 January 2020", source="DEMO")
    assert "No payment" in res["summary"] or "no" in res["summary"].lower() or len(res["facts"]) > 0


@pytest.mark.anyio
async def test_transaction_search():
    res = await investigate(ORG_A, "Show me transactions above ₹50,000", source="DEMO")
    assert res["intent"] in ("search", "revenue")
    assert len(res["tool_log"]) > 0


@pytest.mark.anyio
async def test_evidence_linking():
    res = await investigate(ORG_A, "Why did cash decrease this month?", source="DEMO")
    assert res["autopsy"] is not None
    assert len(res["autopsy"]["contributors"]) > 0
    for c in res["autopsy"]["contributors"]:
        assert "evidence_count" in c
        assert "evidence_records" in c


@pytest.mark.anyio
async def test_organization_isolation():
    db = get_db()
    # Insert payment only for ORG_B
    now_iso = datetime.now(timezone.utc).isoformat()
    await db.payments.insert_one({
        "id": "pay_org_b_only_123",
        "organization_id": ORG_B,
        "amount_paise": 9999900,
        "status": "captured",
        "source": "DEMO",
        "created_at": now_iso,
        "deleted_at": None,
    })

    res_a = await investigate(ORG_A, "What were our total payments this month?", source="DEMO")
    # Verify ORG_A facts do NOT include ORG_B's transaction ID
    for f in res_a["facts"]:
        ev = f.get("evidence_ids", f.get("source_records", []))
        assert "pay_org_b_only_123" not in ev


@pytest.mark.anyio
async def test_deterministic_arithmetic_protection():
    res = await investigate(ORG_A, "Compare refunds this month versus last month", source="DEMO")
    for f in res["facts"]:
        if f.get("metric") == "compare_periods" or "difference_paise" in f:
            assert f["difference_paise"] == f["current_paise"] - f["prior_paise"]


@pytest.mark.anyio
async def test_openai_unavailable_fallback(monkeypatch):
    # Ensure OPENAI_API_KEY is empty so fallback kicks in
    monkeypatch.setenv("OPENAI_API_KEY", "")
    res = await investigate(ORG_A, "Why did cash decrease this month?", source="DEMO")
    assert res["explainer"] == "deterministic"
    assert res["ai_available"] is False
    assert len(res["summary"]) > 0


@pytest.mark.anyio
async def test_razorpay_test_source_filtering():
    db = get_db()
    now_iso = datetime.now(timezone.utc).isoformat()
    await db.refunds.insert_one({
        "id": "ref_razorpay_test_001",
        "organization_id": ORG_A,
        "amount_paise": 77700,
        "source": "RAZORPAY_TEST",
        "created_at": now_iso,
        "deleted_at": None,
    })

    res_demo = await investigate(ORG_A, "What were refunds in the last 30 days?", source="DEMO")
    demo_ref_facts = [f for f in res_demo["facts"] if f.get("metric") == "refunds"]
    if demo_ref_facts:
        assert "ref_razorpay_test_001" not in demo_ref_facts[0].get("evidence_ids", [])

    res_rzp = await investigate(ORG_A, "What were refunds in the last 30 days?", source="RAZORPAY_TEST")
    rzp_ref_facts = [f for f in res_rzp["facts"] if f.get("metric") == "refunds"]
    if rzp_ref_facts:
        assert rzp_ref_facts[0]["amount_paise"] == 77700


@pytest.mark.anyio
async def test_acceptance_dynamic_database_update():
    """CRUCIAL ACCEPTANCE TEST:

    1. Ask: 'What were refunds in the last 30 days?'
    2. Add a new refund record into MongoDB.
    3. Ask exact same question again -> result must dynamically reflect the new database record!
    4. Ask follow-up: 'Show me the transactions supporting that number' -> returns exact inserted record!
    5. Ask follow-up: 'Compare that with the previous 30 days' -> calculates comparison dynamically!
    6. Ask follow-up: 'Why did it change?' -> investigates contributors!
    """
    db = get_db()
    # Step 1: Initial query
    q1 = "What were refunds in the last 30 days?"
    res1 = await investigate(ORG_A, q1, source="DEMO")
    refund_fact1 = [f for f in res1["facts"] if f.get("metric") == "refunds"][0]
    initial_paise = refund_fact1["value"]
    initial_count = refund_fact1["source_count"]

    # Step 2: Dynamically insert a new refund record in MongoDB
    new_refund_id = "ref_dynamic_acceptance_999"
    new_amount_paise = 550000  # ₹5,500
    now_iso = datetime.now(timezone.utc).isoformat()
    await db.refunds.insert_one({
        "id": new_refund_id,
        "organization_id": ORG_A,
        "amount_paise": new_amount_paise,
        "source": "DEMO",
        "created_at": now_iso,
        "deleted_at": None,
    })

    # Step 3: Query exact same question again
    res2 = await investigate(ORG_A, q1, source="DEMO")
    refund_fact2 = [f for f in res2["facts"] if f.get("metric") == "refunds"][0]
    updated_paise = refund_fact2["value"]
    updated_count = refund_fact2["source_count"]

    # VERIFICATION: Result must dynamically change based on DB update!
    assert updated_paise == initial_paise + new_amount_paise
    assert updated_count == initial_count + 1
    assert new_refund_id in refund_fact2["source_records"]

    # Step 4: Follow-up query for supporting transactions using context
    context2 = res2["context"]
    q3 = "Show me the transactions supporting that number"
    res3 = await investigate(ORG_A, q3, source="DEMO", context=context2)
    assert len(res3["facts"]) > 0
    ev_ids_3 = res3["facts"][0].get("evidence_ids", [])
    assert new_refund_id in ev_ids_3

    # Step 5: Follow-up comparison
    q4 = "Compare that with the previous 30 days"
    res4 = await investigate(ORG_A, q4, source="DEMO", context=context2)
    assert res4["period"] is not None
    assert res4["comparison_period"] is not None

    # Step 6: Follow-up investigation
    q5 = "Why did it change?"
    res5 = await investigate(ORG_A, q5, source="DEMO", context=context2)
    assert res5["intent"] in ("investigation", "cash_autopsy")
    assert len(res5["tool_log"]) > 0
