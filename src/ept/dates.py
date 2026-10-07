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
