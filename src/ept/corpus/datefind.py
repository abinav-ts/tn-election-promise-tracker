"""Document dating (spec 01 §4.5).

Precedence: manual > listing > document_text > filename > wayback_capture > none.
A fiscal year alone never becomes a doc_date. Every candidate is kept in the
sidecar; checks add reasons that send the document to date_review.csv.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import asdict, dataclass
from typing import Any, Iterable, Optional
from urllib.parse import unquote, urlsplit

from ept.dates import add_months, fy_bounds, period_end, period_start
from ept.schema import DatePrecision, DateSource

MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3, "apr": 4, "april": 4, "may": 5,
    "jun": 6, "june": 6, "jul": 7, "july": 7, "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}
_MON = r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sept?(?:ember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
_ORD = r"(?:st|nd|rd|th)?"

_NUMERIC = re.compile(r"(?<!\d)(\d{1,2})\s?[./-]\s?(\d{1,2})\s?[./-]\s?((?:19|20)\d{2})(?!\d)")
_DAY_MON_YEAR = re.compile(rf"(?<!\d)(\d{{1,2}}){_ORD}\s*(?:day\s+of\s+|of\s+)?{_MON}\.?,?\s*((?:19|20)\d{{2}})(?!\d)", re.I)
_MON_DAY_YEAR = re.compile(rf"\b{_MON}\.?\s+(\d{{1,2}}){_ORD},?\s*((?:19|20)\d{{2}})(?!\d)", re.I)
_MON_YEAR = re.compile(rf"\b{_MON}\.?,?\s+((?:19|20)\d{{2}})(?!\d)", re.I)

# Issue-date keywords, strongest first: a GO's "Dated:" beats an earlier "Assembly on <date>" in its subject.
_KEYWORDS = [
    re.compile(r"\b(dated|date\s*:)", re.I),
    re.compile(r"\b(presented\s+on|delivered\s+on|laid\s+(?:on|before)|tabled\s+on|issued\s+on|signed\s+on)\b", re.I),
    re.compile(r"\b(assembly\s+on)\b", re.I),
]
_KEYWORD_WINDOW = 60  # characters after a keyword in which the date must start

COPYRIGHT_RANK = 5.5  # after wayback_capture: only dates documents that would otherwise stay undated (D-024)

RANK = {
    DateSource.manual: 1,
    DateSource.listing: 2,
    DateSource.document_text: 3,
    DateSource.filename: 4,
    DateSource.wayback_capture: 5,
    DateSource.none: 6,
}
NEEDS_REVIEW = {DateSource.filename, DateSource.wayback_capture, DateSource.none}


def rank(c: "Candidate") -> float:
    return COPYRIGHT_RANK if c.kind == "copyright" else RANK[DateSource(c.source)]


@dataclass(frozen=True)
class Found:
    date: dt.date
    precision: str
    start: int
    end: int
    text: str


@dataclass(frozen=True)
class Candidate:
    source: str
    date: str  # ISO
    precision: str
    evidence: str = ""
    kind: str = ""  # "copyright" for the © year fallback (D-024)

    @property
    def d(self) -> dt.date:
        return dt.date.fromisoformat(self.date)


def _mk(y: int, m: int, d: int) -> Optional[dt.date]:
    try:
        return dt.date(y, m, d)
    except ValueError:
        return None


def find_dates(text: str) -> list[Found]:
    """Every date in the text, day precision first; month-only dates where no day date overlaps."""
    found: list[Found] = []
    taken: list[tuple[int, int]] = []
    for m in _NUMERIC.finditer(text):
        d = _mk(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        if d:
            found.append(Found(d, "day", m.start(), m.end(), m.group(0)))
            taken.append(m.span())
    for rx, order in ((_DAY_MON_YEAR, "dmy"), (_MON_DAY_YEAR, "mdy")):
        for m in rx.finditer(text):
            if any(s < m.end() and m.start() < e for s, e in taken):
                continue
            if order == "dmy":
                day, mon, year = m.group(1), m.group(2), m.group(3)
            else:
                mon, day, year = m.group(1), m.group(2), m.group(3)
            d = _mk(int(year), MONTHS[mon.lower().rstrip(".")], int(day))
            if d:
                found.append(Found(d, "day", m.start(), m.end(), m.group(0)))
                taken.append(m.span())
    for m in _MON_YEAR.finditer(text):
        if any(s < m.end() and m.start() < e for s, e in taken):
            continue
        d = _mk(int(m.group(2)), MONTHS[m.group(1).lower().rstrip(".")], 1)
        if d:
            found.append(Found(d, "month", m.start(), m.end(), m.group(0)))
    return sorted(found, key=lambda f: f.start)


def issue_date_from_text(front_matter: str) -> Optional[Candidate]:
    """First date that follows an issue keyword ("dated", "presented on", ...) in the front matter."""
    dates = find_dates(front_matter)
    for rx in _KEYWORDS:
        for kw in rx.finditer(front_matter):
            for f in dates:
                if kw.end() <= f.start <= kw.end() + _KEYWORD_WINDOW:
                    snippet = " ".join(front_matter[kw.start():f.end].split())
                    return Candidate(DateSource.document_text.value, f.date.isoformat(), f.precision, snippet[:120])
    return None


_COPYRIGHT = re.compile(r"(?:©|\(c\)|copyright)\s*([^\d©]{0,60}?)\s*((?:19|20)\d{2})(?!\d)", re.I)


def copyright_year(front_matter: str) -> Optional[Candidate]:
    """'© Government of Tamil Nadu 2016' -> year-precision candidate (D-024)."""
    m = _COPYRIGHT.search(front_matter)
    if not m:
        return None
    snippet = " ".join(m.group(0).split())
    return Candidate(DateSource.document_text.value, f"{m.group(2)}-01-01", DatePrecision.year.value, snippet[:80],
                     kind="copyright")


_FN_DMY = re.compile(r"(?<!\d)(\d{2})[_\-.]?(\d{2})[_\-.]?((?:19|20)\d{2})(?!\d)")
_FN_DMY6 = re.compile(r"(?<![\d])(\d{2})(\d{2})(\d{2})(?!\d)")


def date_from_filename(url: str, today: dt.date) -> Optional[Candidate]:
    """Explicit date in the file name, e.g. Budget_Speech_04_08_2011, governor_address_e_160616."""
    name = unquote(urlsplit(url).path.rsplit("/", 1)[-1]).rsplit(".", 1)[0]
    for m in _FN_DMY.finditer(name):
        d = _mk(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        if d and d <= today:
            return Candidate(DateSource.filename.value, d.isoformat(), "day", name)
    for m in _FN_DMY6.finditer(name):
        d = _mk(2000 + int(m.group(3)), int(m.group(2)), int(m.group(1)))
        if d and d <= today:
            return Candidate(DateSource.filename.value, d.isoformat(), "day", name)
    return None


MENTION_RULE = "v2"  # D-028: forward-looking and end-of-period dates don't count for the anachronism flag
_FORWARD = re.compile(
    r"\b(?:before|by|up\s*to|upto|till|until|with\s+effect\s+from|effective\s+from|w\.?\s*e\.?\s*f\.?)\s*[:,]?\s*(?:the\s+)?$", re.I)


def is_forward_or_period_end(text: str, f: Found) -> bool:
    """A date after 'before/by/up to/till/until/with effect from/effective from', or a year/FY end (31 Dec, 31 Mar,
    December, March): these usually describe deadlines or periods, not when the document was written."""
    if _FORWARD.search(text[max(0, f.start - 30):f.start]):
        return True
    if f.precision == "day":
        return (f.date.month, f.date.day) in {(12, 31), (3, 31)}
    return f.precision == "month" and f.date.month in (12, 3)


def latest_mention(text: str, today: dt.date, narrow: bool = False) -> Optional[Found]:
    """Latest date mentioned anywhere in the text, ignoring dates after the run date.
    With `narrow`, forward-looking and end-of-period dates are skipped (anachronism flag, D-028)."""
    dates = [f for f in find_dates(text) if f.date <= today and not (narrow and is_forward_or_period_end(text, f))]
    return max(dates, key=lambda f: f.date) if dates else None


@dataclass
class Dating:
    doc_date: Optional[dt.date]
    precision: Optional[str]
    source: str
    reasons: list[str]

    def as_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out["doc_date"] = self.doc_date.isoformat() if self.doc_date else None
        return out


def resolve(
    candidates: Iterable[Candidate],
    *,
    fiscal_year: Optional[str],
    latest_mentioned: Optional[Candidate],
    latest_any: Optional[Candidate] = None,
    window_start: dt.date,
    today: dt.date,
    conflict_days: int,
    fy_slack_months: int,
    extra_reasons: Iterable[str] = (),
) -> Dating:
    reasons = list(extra_reasons)
    kept = []
    for c in candidates:
        if c.kind == "copyright":
            # the © leak guard keeps using every mentioned date, not the narrowed one
            why = _copyright_rejection(c, fiscal_year, latest_any or latest_mentioned)
            if why:
                reasons.append(f"© year {c.date[:4]} not used: {why}")
                continue
        kept.append(c)
    cands = sorted(kept, key=rank)
    if not cands:
        dating = Dating(None, None, DateSource.none.value, reasons)
        dating.reasons.insert(0, "undated (fiscal year only)" if fiscal_year else "undated")
        return dating
    best = cands[0]
    doc_date, precision = best.d, best.precision
    source = DateSource(best.source)
    if best.kind == "copyright":
        reasons.insert(0, "dated from © year (year precision)")
    elif source in (DateSource.filename, DateSource.wayback_capture):
        reasons.insert(0, {DateSource.filename: "dated from filename",
                           DateSource.wayback_capture: "dated by Wayback first capture (upper bound)"}[source])

    ranked = [c for c in cands if c.kind != "copyright" and DateSource(c.source) in (
        DateSource.listing, DateSource.document_text, DateSource.filename)]
    for i, a in enumerate(ranked):
        for b in ranked[i + 1:]:
            if abs((a.d - b.d).days) > conflict_days:
                reasons.append(f"conflict: {a.source} {a.date} vs {b.source} {b.date}")
    if latest_mentioned and latest_mentioned.d > period_end(doc_date, precision):
        reasons.append(f"anachronism: text mentions {latest_mentioned.date} ({latest_mentioned.evidence[:40]!r})")
    if period_end(doc_date, precision) < window_start or period_start(doc_date, precision) > today:
        reasons.append(f"out of window: {doc_date.isoformat()}")
    if fiscal_year:
        lo, hi = fy_bounds(fiscal_year)
        lo, hi = add_months(lo, -fy_slack_months), add_months(hi, fy_slack_months)
        if not (lo <= doc_date <= hi):
            reasons.append(f"FY mismatch: {doc_date.isoformat()} outside {fiscal_year} ± {fy_slack_months} months")
    return Dating(doc_date, precision, source.value, reasons)


def _copyright_rejection(c: Candidate, fiscal_year: Optional[str], latest: Optional[Candidate]) -> Optional[str]:
    """Leak guards for the © year: a stale template year would date a document too early."""
    year = int(c.date[:4])
    if fiscal_year and year < fy_bounds(fiscal_year)[0].year:
        return f"earlier than fiscal year {fiscal_year}"
    if latest and latest.d > period_end(c.d, c.precision):
        return f"text mentions later date {latest.date}"
    return None


def needs_review(dating: Dating) -> bool:
    return DateSource(dating.source) in NEEDS_REVIEW or bool(dating.reasons)


def listing_candidate(listing: dict[str, Any]) -> Optional[Candidate]:
    if listing.get("listing_date"):
        manual = listing.get("discovery") == "manual"
        return Candidate((DateSource.manual if manual else DateSource.listing).value, listing["listing_date"],
                         (listing.get("identifiers") or {}).get("date_precision") or DatePrecision.day.value, "listing")
    return None


def wayback_candidate(wayback: dict[str, Any]) -> Optional[Candidate]:
    ts = (wayback or {}).get("kept_first_capture")
    if not ts:
        return None
    d = dt.datetime.strptime(ts[:8], "%Y%m%d").date()
    return Candidate(DateSource.wayback_capture.value, d.isoformat(), "day", f"first capture of kept bytes {ts}")
