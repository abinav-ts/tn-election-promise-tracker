"""Date helpers (global spec §9.3).

`period_end` is the function stage 04's cutoff filter must use (spec 01 §5):
a partial date is stored as the first day of its period, so comparing the
stored date with a cutoff would let a month- or year-precision document leak early.
"""

from __future__ import annotations

import calendar
import datetime as dt
import re
from typing import Optional, Union

from ept.schema import DatePrecision, Term

DateLike = Union[dt.date, str]


def parse_iso(value: DateLike) -> dt.date:
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    return dt.date.fromisoformat(value.strip()[:10])


def period_start(d: DateLike, precision: str) -> dt.date:
    d = parse_iso(d)
    p = DatePrecision(precision)
    if p is DatePrecision.day:
        return d
    if p is DatePrecision.month:
        return d.replace(day=1)
    return d.replace(month=1, day=1)


def period_end(d: DateLike, precision: str) -> dt.date:
    """Last day of the period a partial date stands for."""
    d = parse_iso(d)
    p = DatePrecision(precision)
    if p is DatePrecision.day:
        return d
    if p is DatePrecision.month:
        return d.replace(day=calendar.monthrange(d.year, d.month)[1])
    return d.replace(month=12, day=31)


def add_months(d: dt.date, months: int) -> dt.date:
    total = d.year * 12 + (d.month - 1) + months
    year, month = divmod(total, 12)
    month += 1
    return dt.date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


def whole_months_between(start: dt.date, end: dt.date) -> int:
    """floor of months from start to end (negative if end < start)."""
    months = (end.year - start.year) * 12 + (end.month - start.month)
    if end >= start and end.day < start.day:
        months -= 1
    elif end < start and end.day > start.day:
        months += 1
    return months


def month_in_term(d: DateLike, term: Term) -> int:
    """Whole months since the term's swearing-in (§9.3)."""
    return whole_months_between(parse_iso(term.sworn_in), parse_iso(d))


# --- fiscal years (April–March), canonical form "2021-22" ---

_FY_RE = re.compile(r"(?<!\d)((?:19|20)\d{2})\s*[-_/–]\s*((?:19|20)?\d{2})(?!\d)")


def fiscal_year_of(d: DateLike) -> str:
    d = parse_iso(d)
    start = d.year if d.month >= 4 else d.year - 1
    return f"{start}-{(start + 1) % 100:02d}"


def normalize_fy(text: str) -> Optional[str]:
    """'2021-2022', '2021-22', '2021_22' -> '2021-22'. None if no valid FY found."""
    m = _FY_RE.search(text)
    if not m:
        return None
    start = int(m.group(1))
    end = m.group(2)
    end_two = int(end[-2:])
    if end_two != (start + 1) % 100:
        return None
    return f"{start}-{end_two:02d}"


def fy_start_year(fy: str) -> int:
    norm = normalize_fy(fy)
    if norm is None:
        raise ValueError(f"not a fiscal year: {fy!r}")
    return int(norm[:4])


def fy_bounds(fy: str) -> tuple[dt.date, dt.date]:
    start = fy_start_year(fy)
    return dt.date(start, 4, 1), dt.date(start + 1, 3, 31)


def fiscal_years_between(start: dt.date, end: dt.date) -> list[str]:
    first = fy_start_year(fiscal_year_of(start))
    last = fy_start_year(fiscal_year_of(end))
    return [f"{y}-{(y + 1) % 100:02d}" for y in range(first, last + 1)]


# --- availability date (spec 04 §4.2, D-077) ---

BASIS_STORED = "stored"  # the stored date's period_end
BASIS_FY_TIGHTENED = "fy_tightened"  # stored date later than the fiscal-year end: capped at it
BASIS_FY_ONLY = "fy_only"  # undated: the fiscal-year end is the only date
BASIS_FETCHED = "fetched"  # capped at the fetch date (D-082)


def fy_bounded(doc_type: str, title: Optional[str], fy_bound) -> bool:
    """Policy notes, budget speeches, and `other` documents whose title starts with a listed prefix."""
    if doc_type in fy_bound.doc_types:
        return True
    prefixes = fy_bound.title_prefixes.get(doc_type) or []
    t = (title or "").strip().lower()
    return any(t.startswith(p.lower()) for p in prefixes)


def _fy_availability(doc_date, date_precision, doc_type, fiscal_year, title, fy_bound
                     ) -> tuple[Optional[dt.date], Optional[str]]:
    base = period_end(doc_date, date_precision) if doc_date and date_precision else None
    fy_end = None
    if fiscal_year and fy_bounded(doc_type, title, fy_bound) and normalize_fy(fiscal_year):
        fy_end = fy_bounds(fiscal_year)[1]
    if fy_end is None:
        return (base, BASIS_STORED) if base else (None, None)
    if base is None:
        return fy_end, BASIS_FY_ONLY
    return (fy_end, BASIS_FY_TIGHTENED) if fy_end < base else (base, BASIS_STORED)


def fetch_capped(title: Optional[str], fetch_bound) -> bool:
    t = (title or "").lower()
    return not any(p.lower() in t for p in fetch_bound.exclude_title_patterns)


def availability(doc_date: Optional[DateLike], date_precision: Optional[str], doc_type: str,
                 fiscal_year: Optional[str], title: Optional[str], fy_bound=None,
                 fetched_at: Optional[DateLike] = None, fetch_bound=None) -> tuple[Optional[dt.date], Optional[str]]:
    """(available_by, basis); (None, None) for an undated document without a fiscal-year bound.

    Fetch-date bound (D-082): a dated document is never later than the day we fetched it (it existed then);
    it never dates an undated document, and titles matching `exclude_title_patterns` (interim budgets, which
    the outgoing government presents) keep their date.
    """
    if fy_bound is None or (fetched_at is not None and fetch_bound is None):
        from ept.config import get_config

        d = get_config().settings.date
        fy_bound = fy_bound or d.fy_bound
        fetch_bound = fetch_bound or d.fetch_bound
    a, basis = _fy_availability(doc_date, date_precision, doc_type, fiscal_year, title, fy_bound)
    if a is not None and fetched_at and fetch_capped(title, fetch_bound):
        f = parse_iso(fetched_at)
        if f < a:
            return f, BASIS_FETCHED
    return a, basis


def available_by(doc_date: Optional[DateLike], date_precision: Optional[str], doc_type: str,
                 fiscal_year: Optional[str], title: Optional[str], fy_bound=None,
                 fetched_at: Optional[DateLike] = None, fetch_bound=None) -> Optional[dt.date]:
    """The date from which a document's chunks count as available (global §9.1, §9.3; D-077, D-082).

    `period_end` of the stored date, but never later than the fiscal-year end for policy notes, performance
    budgets and budget speeches (for such an undated document, the fiscal-year end), and never later than
    the document's fetch date. None = undated.
    """
    return availability(doc_date, date_precision, doc_type, fiscal_year, title, fy_bound, fetched_at,
                        fetch_bound)[0]
