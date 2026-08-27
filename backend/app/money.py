"""Deterministic money helpers. All monetary amounts are stored as INTEGER PAISE.

Storing amounts as integers eliminates floating point drift, which is essential
for a financially deterministic system where numbers must reconcile exactly.
"""
from __future__ import annotations


def rupees(paise: int) -> float:
    """Convert integer paise to a rupee float for display only."""
    return round(int(paise) / 100.0, 2)


def to_paise(rupees_value: float) -> int:
    """Convert a rupee value to integer paise, rounding half-up."""
    return int(round(float(rupees_value) * 100))


def format_inr(paise: int) -> str:
    """Format integer paise as an Indian-formatted rupee string, e.g. ₹8,70,000.00"""
    value = int(paise)
    negative = value < 0
    value = abs(value)
    whole = value // 100
    frac = value % 100
    s = str(whole)
    if len(s) > 3:
        last3 = s[-3:]
        rest = s[:-3]
        parts = []
        while len(rest) > 2:
            parts.insert(0, rest[-2:])
            rest = rest[:-2]
        if rest:
            parts.insert(0, rest)
        formatted = ",".join(parts) + "," + last3
    else:
        formatted = s
    out = f"₹{formatted}.{frac:02d}"
    return f"-{out}" if negative else out


def pct(numerator: float, denominator: float) -> float:
    """Safe percentage; returns 0.0 when denominator is zero."""
    if not denominator:
        return 0.0
    return round((numerator / denominator) * 100, 2)
