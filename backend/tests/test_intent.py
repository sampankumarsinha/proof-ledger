from app.analyst import classify_intent


def test_intent_selection():
    assert classify_intent("Why did cash decrease this month?") == "cash_autopsy"
    assert classify_intent("Which customers owe me money?") == "receivables"
    assert classify_intent("Which products are driving refunds?") == "top_products"
    assert classify_intent("Which settlements are delayed?") == "settlements"
    assert classify_intent("Compare this period with the prior period.") == "compare"
    assert classify_intent("Show me unreconciled payments") == "unreconciled"


def test_no_causal_overreach_defaults_to_autopsy():
    # a leading causal question should route to investigation, not assert cause
    assert classify_intent("Did refunds definitely cause the cash decline?") == "cash_autopsy"
