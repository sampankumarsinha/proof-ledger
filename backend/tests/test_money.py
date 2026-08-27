from app.money import to_paise, rupees, format_inr, pct


def test_to_paise_and_back():
    assert to_paise(100.0) == 10000
    assert to_paise(8700.55) == 870055
    assert rupees(870055) == 8700.55


def test_format_inr_indian_grouping():
    assert format_inr(87000000) == "₹8,70,000.00"
    assert format_inr(10000) == "₹100.00"
    assert format_inr(-500000) == "-₹5,000.00"
    assert format_inr(0) == "₹0.00"


def test_pct_safe():
    assert pct(50, 200) == 25.0
    assert pct(10, 0) == 0.0


def test_determinism_no_float_drift():
    # summing integer paise never drifts, unlike float rupees
    total = sum([333, 333, 334])
    assert total == 1000
    assert rupees(total) == 10.0
