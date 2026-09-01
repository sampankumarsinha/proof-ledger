"""Natural-language and explicit date range resolution for the AI Analyst.

All financial queries use explicit date_from / date_to ISO timestamps.
The LLM never chooses dates — this module parses them deterministically.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone, timedelta
from dateutil.relativedelta import relativedelta

MONTH_MAP = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3,
    "april": 4, "apr": 4, "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7,
    "august": 8, "aug": 8, "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10, "november": 11, "nov": 11, "december": 12, "dec": 12,
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _start_of_day(dt: datetime) -> datetime:
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


def _end_of_day(dt: datetime) -> datetime:
    return dt.replace(hour=23, minute=59, second=59, microsecond=999999)


def _period(key: str, start: datetime, end: datetime, label: str) -> dict:
    return {"key": key, "from": _iso(start), "to": _iso(end), "label": label}


def prior_period(period: dict) -> dict:
    """Return the immediately preceding period of equal length."""
    start = datetime.fromisoformat(period["from"])
    end = datetime.fromisoformat(period["to"])
    duration = end - start
    prior_end = start - timedelta(microseconds=1)
    prior_start = prior_end - duration
    return _period("prior", prior_start, prior_end, f"Prior to {period['label']}")


def resolve_period_key(period_key: str = "current", date_from: str = None, date_to: str = None) -> dict:
    """Resolve a period key or explicit dates (used by FinancialEngine)."""
    if date_from and date_to:
        return _period("custom", datetime.fromisoformat(date_from), datetime.fromisoformat(date_to), "Custom range")
    now = _now()
    parsers = {
        "current": lambda: _period("current", now - timedelta(days=30), now, "Last 30 days"),
        "prior": lambda: _period("prior", now - timedelta(days=60), now - timedelta(days=30), "Prior 30 days"),
        "today": lambda: _period("today", _start_of_day(now), now, "Today"),
        "yesterday": lambda: _period("yesterday", _start_of_day(now - timedelta(days=1)),
                                      _end_of_day(now - timedelta(days=1)), "Yesterday"),
        "this_week": lambda: _period("this_week", _start_of_day(now - timedelta(days=now.weekday())), now, "This week"),
        "last_week": lambda: (
            s := _start_of_day(now - timedelta(days=now.weekday() + 7)),
            _period("last_week", s, s + timedelta(days=6, hours=23, minutes=59, seconds=59), "Last week"),
        )[-1],
        "this_month": lambda: _period("this_month", now.replace(day=1, hour=0, minute=0, second=0, microsecond=0),
                                      now, "This month"),
        "last_month": lambda: (
            lm := now.replace(day=1) - timedelta(days=1),
            _period("last_month", lm.replace(day=1, hour=0, minute=0, second=0, microsecond=0),
                    _end_of_day(lm), "Last month"),
        )[-1],
        "this_quarter": lambda: (
            qm := ((now.month - 1) // 3) * 3 + 1,
            _period("this_quarter", now.replace(month=qm, day=1, hour=0, minute=0, second=0, microsecond=0),
                    now, "This quarter"),
        )[-1],
        "last_quarter": lambda: (
            qm := ((now.month - 1) // 3) * 3 + 1,
            qs := now.replace(month=qm, day=1) - timedelta(days=1),
            qstart := ((qs.month - 1) // 3) * 3 + 1,
            _period("last_quarter", qs.replace(month=qstart, day=1, hour=0, minute=0, second=0, microsecond=0),
                    _end_of_day(qs), "Last quarter"),
        )[-1],
        "last_7_days": lambda: _period("last_7_days", now - timedelta(days=7), now, "Last 7 days"),
        "last_14_days": lambda: _period("last_14_days", now - timedelta(days=14), now, "Last 14 days"),
        "last_30_days": lambda: _period("last_30_days", now - timedelta(days=30), now, "Last 30 days"),
        "last_90_days": lambda: _period("last_90_days", now - timedelta(days=90), now, "Last 90 days"),
        "last_6_months": lambda: _period("last_6_months", now - relativedelta(months=6), now, "Last 6 months"),
        "last_12_months": lambda: _period("last_12_months", now - relativedelta(months=12), now, "Last 12 months"),
        "all": lambda: _period("all", datetime(2020, 1, 1, tzinfo=timezone.utc), now, "All available history"),
    }
    fn = parsers.get(period_key)
    if fn:
        return fn()
    return parsers["current"]()


def _parse_day_month(text: str, year: int | None = None) -> datetime | None:
    """Parse '1aug', '1 August', '1st Aug', '15 Aug 2026', 'Aug 1', etc."""
    text = text.strip().lower()
    text = re.sub(r"(\d+)(st|nd|rd|th)\b", r"\1", text)

    # 1aug or 1 aug or 1 august 2026
    m = re.match(r"^(\d{1,2})\s*([a-z]+)(?:\s*(\d{4}))?$", text)
    if m:
        day, mon, yr = int(m.group(1)), m.group(2), m.group(3)
        month = MONTH_MAP.get(mon)
        if month:
            y = int(yr) if yr else (year or _now().year)
            try:
                return datetime(y, month, day, tzinfo=timezone.utc)
            except ValueError:
                pass

    # aug 1 or august 1 2026
    m = re.match(r"^([a-z]+)\s*(\d{1,2})(?:\s*(\d{4}))?$", text)
    if m:
        mon, day, yr = m.group(1), int(m.group(2)), m.group(3)
        month = MONTH_MAP.get(mon)
        if month:
            y = int(yr) if yr else (year or _now().year)
            try:
                return datetime(y, month, day, tzinfo=timezone.utc)
            except ValueError:
                pass

    # Slash or dash format: 1/8/2026 or 1-8-2026
    m = re.match(r"^(\d{1,2})[/.-](\d{1,2})(?:[/.-](\d{2,4}))?$", text)
    if m:
        day, month = int(m.group(1)), int(m.group(2))
        yr = m.group(3)
        if 1 <= month <= 12 and 1 <= day <= 31:
            if yr:
                y = int(yr) if len(yr) == 4 else 2000 + int(yr)
            else:
                y = year or _now().year
            try:
                return datetime(y, month, day, tzinfo=timezone.utc)
            except ValueError:
                pass
    return None


def _parse_custom_range(q: str) -> dict | None:
    """Parse explicit date ranges (including shorthand like 1aug to 4aug) and single month queries."""
    now = _now()
    q_norm = re.sub(r"(\d+)(st|nd|rd|th)\b", r"\1", q, flags=re.I)

    # "between 1aug to 4aug" / "from 1aug to 4aug" / "1aug - 4aug" / "1 aug to 4 aug"
    m = re.search(
        r"(?:from|between\s+)?(\d{1,2}\s*?[a-z]+(?:\s*\d{4})?|[a-z]+\s*?\d{1,2}(?:\s*\d{4})?|\d{1,2}[/.-]\d{1,2}(?:[/.-]\d{2,4})?)\s*(?:to|until|and|-)\s*(\d{1,2}\s*?[a-z]+(?:\s*\d{4})?|[a-z]+\s*?\d{1,2}(?:\s*\d{4})?|\d{1,2}[/.-]\d{1,2}(?:[/.-]\d{2,4})?)",
        q_norm, re.I,
    )
    if m:
        start = _parse_day_month(m.group(1))
        end = _parse_day_month(m.group(2))
        if start and end:
            return _period("custom", _start_of_day(start), _end_of_day(end),
                           f"{start.strftime('%d %b %Y')} – {end.strftime('%d %b %Y')}")

    # "between January and February" (current year)
    m = re.search(r"between\s+([a-z]+)\s+and\s+([a-z]+)", q, re.I)
    if m:
        m1, m2 = MONTH_MAP.get(m.group(1).lower()), MONTH_MAP.get(m.group(2).lower())
        if m1 and m2:
            start = datetime(now.year, m1, 1, tzinfo=timezone.utc)
            end_month = datetime(now.year, m2, 1, tzinfo=timezone.utc) + relativedelta(months=1) - timedelta(days=1)
            return _period("custom", start, _end_of_day(end_month),
                           f"{m.group(1).title()} – {m.group(2).title()} {now.year}")

    # "in August 2026", "for January", "in August"
    m = re.search(r"\b(?:in|for|during)\s+([a-z]+)(?:\s+(\d{4}))?\b", q, re.I)
    if m:
        m_num = MONTH_MAP.get(m.group(1).lower())
        if m_num:
            y = int(m.group(2)) if m.group(2) else now.year
            start = datetime(y, m_num, 1, tzinfo=timezone.utc)
            end_month = start + relativedelta(months=1) - timedelta(days=1)
            return _period("custom", start, _end_of_day(end_month),
                           f"{m.group(1).title()} {y}")
    return None


def _match_period_keyword(q: str) -> dict | None:
    """Match natural-language period phrases (longest match first)."""
    now = _now()
    patterns = [
        (r"\blast\s+12\s+months\b", "last_12_months"),
        (r"\blast\s+6\s+months\b", "last_6_months"),
        (r"\blast\s+90\s+days\b", "last_90_days"),
        (r"\blast\s+30\s+days\b", "last_30_days"),
        (r"\blast\s+14\s+days\b", "last_14_days"),
        (r"\blast\s+7\s+days\b", "last_7_days"),
        (r"\bthis\s+quarter\b", "this_quarter"),
        (r"\blast\s+quarter\b", "last_quarter"),
        (r"\bthis\s+month\b", "this_month"),
        (r"\blast\s+month\b", "last_month"),
        (r"\bthis\s+week\b", "this_week"),
        (r"\blast\s+week\b", "last_week"),
        (r"\byesterday\b", "yesterday"),
        (r"\btoday\b", "today"),
        (r"\ball\s+(?:available\s+)?history\b", "all"),
    ]
    for pat, key in patterns:
        if re.search(pat, q, re.I):
            return resolve_period_key(key)
    return None


def _wants_comparison(q: str) -> bool:
    return bool(re.search(
        r"\b(compare|versus|vs\.?|compared\s+(?:to|with)|month\s+over\s+month|"
        r"previous\s+period|prior\s+period|before\s+that|the\s+month\s+before)\b",
        q, re.I,
    ))


def _is_follow_up(q: str) -> bool:
    return bool(re.search(
        r"\b(that|those|it|them|same\s+period|what\s+caused|why\s+did\s+it|"
        r"how\s+does\s+that|break\s+(?:this|that)\s+down|supporting\s+transactions|"
        r"show\s+(?:me\s+)?the\s+transactions)\b",
        q, re.I,
    ))


def parse_question_dates(question: str, context: dict | None = None) -> tuple[dict, dict | None, bool]:
    """Parse primary and optional comparison periods from a question.

    Returns (primary_period, comparison_period_or_none, is_comparison_query).
    Uses conversation context for follow-up questions.
    """
    q = question.lower()
    context = context or {}

    # Follow-up: reuse context period
    if _is_follow_up(q) and context.get("period"):
        primary = context["period"]
        if _wants_comparison(q):
            comp = context.get("comparison_period") or prior_period(primary)
            return primary, comp, True
        return primary, None, False

    # Custom explicit range
    custom = _parse_custom_range(q)
    if custom:
        comp = prior_period(custom) if _wants_comparison(q) else None
        return custom, comp, comp is not None

    # Keyword period
    kw = _match_period_keyword(q)
    if kw:
        comp = None
        if _wants_comparison(q):
            if "last month" in q and "this month" in q:
                comp = resolve_period_key("last_month")
                primary = resolve_period_key("this_month")
            elif "last month" in q:
                primary = resolve_period_key("last_month")
                comp = prior_period(primary)
            elif "last week" in q and "this week" in q:
                comp = resolve_period_key("last_week")
                primary = resolve_period_key("this_week")
            elif "last quarter" in q and "this quarter" in q:
                comp = resolve_period_key("last_quarter")
                primary = resolve_period_key("this_quarter")
            else:
                comp = prior_period(kw)
                primary = kw
        else:
            primary = kw
        return primary, comp, comp is not None

    # Default: last 30 days (no hardcoded limit on custom queries)
    primary = resolve_period_key("last_30_days")
    comp = prior_period(primary) if _wants_comparison(q) else None
    return primary, comp, comp is not None
