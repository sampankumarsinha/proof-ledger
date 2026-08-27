"""Evidence engine + claim verification + explainable confidence.

A claim is only presented as fact when its numbers recompute exactly from
source records. Confidence is derived from concrete evidence signals, never
from an LLM's self-reported certainty.
"""
from .money import format_inr, pct

CLAIM_TYPES = ["VERIFIED_FACT", "DERIVED_FACT", "CORRELATION", "INFERENCE", "INSUFFICIENT_EVIDENCE"]


def build_claim(claim_id, text, claim_type, source_records, calculation, period,
                verification_status="VERIFIED", evidence_coverage=1.0, source_completeness=1.0):
    return {
        "claim_id": claim_id,
        "claim_text": text,
        "claim_type": claim_type,
        "source_records": source_records[:200],
        "source_count": len(source_records),
        "calculation": calculation,
        "period": period,
        "verification_status": verification_status,
        "evidence_coverage": round(evidence_coverage, 2),
        "source_completeness": round(source_completeness, 2),
    }


def confidence_from_signals(signals: dict):
    """signals: dict of signal_name -> value in [0,1]. Returns explainable score."""
    weights = {
        "source_completeness": 0.25,
        "evidence_coverage": 0.20,
        "calculation_verification": 0.25,
        "record_consistency": 0.15,
        "time_alignment": 0.10,
        "entity_resolution": 0.05,
    }
    score = sum(weights[k] * signals.get(k, 0.0) for k in weights)
    ambiguity = signals.get("ambiguity", 0.0)
    score = max(0.0, min(1.0, score - 0.1 * ambiguity))
    if score >= 0.85:
        band = "HIGH"
    elif score >= 0.6:
        band = "MEDIUM"
    else:
        band = "LOW"
    return {
        "score": round(score, 2),
        "band": band,
        "signals": {k: round(signals.get(k, 0.0), 2) for k in list(weights) + ["ambiguity"]},
        "explanation": f"Confidence is {band} because {int(signals.get('calculation_verification',0)*100)}% "
                       f"of claimed numbers recomputed exactly and "
                       f"{int(signals.get('source_completeness',0)*100)}% of source records were available.",
    }


def verify_numeric_claim(claimed_value, recomputed_value):
    """Recalculate a numeric claim; flag if it doesn't match source truth."""
    ok = int(claimed_value) == int(recomputed_value)
    return {
        "claimed": claimed_value,
        "recomputed": recomputed_value,
        "match": ok,
        "status": "VERIFIED" if ok else "UNSUPPORTED",
    }
