from app.evidence import confidence_from_signals, verify_numeric_claim, build_claim


def test_confidence_bands():
    high = confidence_from_signals({k: 1.0 for k in [
        "source_completeness", "evidence_coverage", "calculation_verification",
        "record_consistency", "time_alignment", "entity_resolution"]})
    assert high["band"] == "HIGH"
    low = confidence_from_signals({"source_completeness": 0.2})
    assert low["band"] == "LOW"


def test_verify_numeric_claim_flags_unsupported():
    assert verify_numeric_claim(100, 100)["status"] == "VERIFIED"
    bad = verify_numeric_claim(100, 101)
    assert bad["match"] is False and bad["status"] == "UNSUPPORTED"


def test_build_claim_shape():
    c = build_claim("c1", "x", "VERIFIED_FACT", ["a", "b"], "SUM(x)", {"key": "current"})
    assert c["source_count"] == 2
    assert c["claim_type"] == "VERIFIED_FACT"
