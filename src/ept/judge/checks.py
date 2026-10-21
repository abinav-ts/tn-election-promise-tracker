"""Checks J1–J7 on one judged task, each against that task's own input (spec 05 §4.5; leakage rules 1–2).

- J1 schema: every alias answered exactly once; status in §8; confidence 0–1; rationale ≤ 80 words; date
  format `YYYY-MM-DD` | `YYYY-MM` | `YYYY` (the format sets the precision).
- J2 citations: statuses other than `not_started` / `unverifiable` cite ≥ 1 extract; every cited extract and
  the `date_extract` is one of this task's extracts; the `date_extract` is itself cited (so the date's source
  carries a verified quote).
- J3 quotes: 5–40 words, found in the cited chunk after normalisation (NFKC, lower case, non-alphanumerics →
  space, spaces collapsed); else rapidfuzz `partial_ratio` ≥ `judge.quote_fuzzy_min` passes with review
  reason `quote_fuzzy`.
- J4 date presence: a date iff the status is fulfilled / partial / diluted; a date needs a `date_extract`.
- J5 date window: period_end(date) ≥ sworn_in and period_start(date) ≤ the latest `available_by` among the
  cited chunks (never after the cutoff, since every retrieved chunk is eligible at it).
- J6 date source: the date, at its precision, matches the date chunk's stored document date or a date written
  in its text (`ept.corpus.datefind.find_dates`; for year precision the 4-digit year in the text).
- J7 directional: no `partial` / `diluted` for a directional promise.
"""

from __future__ import annotations

import datetime as dt
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Iterable, Optional

from rapidfuzz import fuzz

from ept.corpus.datefind import find_dates
from ept.dates import period_end, period_start
from ept.judge.prompt import TaskVerdictOut
from ept.judge.tasks import ChunkInfo

STATUSES = ("fulfilled", "partial", "diluted", "in_progress", "not_started", "blocked_external", "unverifiable")
REALISED = frozenset({"fulfilled", "partial", "diluted"})
NO_CITATION_NEEDED = frozenset({"not_started", "unverifiable"})
_DATE_RE = re.compile(r"^(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?$")
_NON_ALNUM = re.compile(r"[^0-9a-z]+")
_PREC_RANK = {"day": 0, "month": 1, "year": 2}


@dataclass(frozen=True)
class Limits:
    quote_min_words: int
    quote_max_words: int
    quote_fuzzy_min: float
    rationale_max_words: int

    @classmethod
    def from_config(cls, cfg) -> "Limits":
        j = cfg.settings.judge
        return cls(j.quote.min_words, j.quote.max_words, j.quote_fuzzy_min, j.rationale_max_words)


@dataclass(frozen=True)
class TaskInput:
    """What the checks know about one task: its extracts by alias, the start date, the directional flag."""

    alias: str
    extracts: dict[str, ChunkInfo]  # "C1" -> chunk
    sworn_in: dt.date
    directional: bool


@dataclass
class Checked:
    """A task's answer after the checks; `failures` empty = passed."""

    failures: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)  # review reasons from the checks (quote_fuzzy)
    status: str = "unverifiable"
    realisation_date: Optional[dt.date] = None
    date_precision: Optional[str] = None
    date_chunk_id: Optional[str] = None
    cited_chunk_ids: list[str] = field(default_factory=list)
    quotes: dict[str, str] = field(default_factory=dict)
    rationale: str = ""
    confidence: float = 0.0

    @property
    def ok(self) -> bool:
        return not self.failures


def rule_of(failure: str) -> str:
    return failure.split(":", 1)[0]


# --- J1 matching ----------------------------------------------------------------------------


def match_answers(aliases: Iterable[str], answers: Iterable[TaskVerdictOut]
                  ) -> tuple[dict[str, TaskVerdictOut], dict[str, str], list[str]]:
    """(answer by alias, J1 failure by alias, aliases answered that were not asked)."""
    wanted = list(aliases)
    seen: dict[str, list[TaskVerdictOut]] = {}
    extras = []
    for a in answers:
        if a.task in wanted:
            seen.setdefault(a.task, []).append(a)
        else:
            extras.append(a.task)
    matched, fails = {}, {}
    for alias in wanted:
        got = seen.get(alias, [])
        if len(got) == 1:
            matched[alias] = got[0]
        else:
            fails[alias] = f"J1: task {alias} answered {len(got)} times"
    return matched, fails, extras


# --- helpers -----------------------------------------------------------------------------------


def parse_claimed_date(s: str) -> tuple[dt.date, str]:
    """`YYYY-MM-DD` | `YYYY-MM` | `YYYY` -> (first day of the period, precision); ValueError if invalid."""
    m = _DATE_RE.match(s.strip())
    if not m:
        raise ValueError(f"date {s!r} is not YYYY-MM-DD, YYYY-MM or YYYY")
    y, mo, d = m.group(1), m.group(2), m.group(3)
    if d:
        return dt.date(int(y), int(mo), int(d)), "day"
    if mo:
        return dt.date(int(y), int(mo), 1), "month"
    return dt.date(int(y), 1, 1), "year"


def normalise(text: str) -> str:
    t = unicodedata.normalize("NFKC", text).lower()
    return " ".join(_NON_ALNUM.sub(" ", t).split())


def quote_match(quote: str, chunk_text: str, fuzzy_min: float) -> Optional[str]:
    """'exact' | 'fuzzy' | None (not found)."""
    q, c = normalise(quote), normalise(chunk_text)
    if not q:
        return None
    if f" {q} " in f" {c} ":
        return "exact"
    return "fuzzy" if fuzz.partial_ratio(q, c) >= fuzzy_min else None


def same_period(d: dt.date, prec: str, other: dt.date, other_prec: str) -> bool:
    """`other` (at a precision at least as fine as `prec`) falls on the same day / month / year as `d`."""
    if _PREC_RANK[other_prec] > _PREC_RANK[prec]:
        return False
    if prec == "day":
        return other == d
    if prec == "month":
        return (other.year, other.month) == (d.year, d.month)
    return other.year == d.year


def date_in_chunk(d: dt.date, prec: str, chunk: ChunkInfo) -> bool:
    """J6: the chunk's stored document date, or a date written in its text, matches `d` at `prec`."""
    if chunk.doc_date and chunk.date_precision and same_period(d, prec, chunk.doc_date, chunk.date_precision):
        return True
    if any(same_period(d, prec, f.date, f.precision) for f in find_dates(chunk.text)):
        return True
    return prec == "year" and re.search(rf"(?<!\d){d.year}(?!\d)", chunk.text) is not None


# --- the checks ---------------------------------------------------------------------------------


def check_task(a: TaskVerdictOut, t: TaskInput, lim: Limits) -> Checked:
    out = Checked(status=a.status, rationale=a.rationale.strip(), confidence=a.confidence)
    f = out.failures
    # J1
    if a.status not in STATUSES:
        f.append(f"J1: status {a.status!r} not in §8")
    if not 0.0 <= a.confidence <= 1.0:
        f.append(f"J1: confidence {a.confidence} outside 0–1")
    if len(out.rationale.split()) > lim.rationale_max_words:
        f.append(f"J1: rationale has {len(out.rationale.split())} words (max {lim.rationale_max_words})")
    date_str = (a.realisation_date or "").strip()
    if date_str:
        try:
            out.realisation_date, out.date_precision = parse_claimed_date(date_str)
        except ValueError as e:
            f.append(f"J1: {e}")
    # J2
    cited = [c for c in a.cited if c.extract.strip()]
    if a.status not in NO_CITATION_NEEDED and not cited:
        f.append(f"J2: status {a.status} cites no extract")
    for c in cited:
        alias = c.extract.strip()
        if alias not in t.extracts:
            f.append(f"J2: cited extract {alias!r} is not one of this task's extracts")
            continue
        chunk = t.extracts[alias]
        if chunk.chunk_id in out.quotes:
            continue  # a second quote for the same extract: the first one counts
        out.cited_chunk_ids.append(chunk.chunk_id)
        out.quotes[chunk.chunk_id] = c.quote
        # J3
        n = len(normalise(c.quote).split())
        if not lim.quote_min_words <= n <= lim.quote_max_words:
            f.append(f"J3: quote for {alias} has {n} words (allowed {lim.quote_min_words}–{lim.quote_max_words})")
            continue
        how = quote_match(c.quote, chunk.text, lim.quote_fuzzy_min)
        if how is None:
            f.append(f"J3: quote for {alias} not found in the extract")
        elif how == "fuzzy" and "quote_fuzzy" not in out.reasons:
            out.reasons.append("quote_fuzzy")
    date_alias = (a.date_extract or "").strip()
    if date_alias:
        if date_alias not in t.extracts:
            f.append(f"J2: date_extract {date_alias!r} is not one of this task's extracts")
        elif t.extracts[date_alias].chunk_id not in out.quotes:
            f.append(f"J2: date_extract {date_alias} is not cited")
        else:
            out.date_chunk_id = t.extracts[date_alias].chunk_id
    # J4
    realised = a.status in REALISED
    if realised and not date_str:
        f.append(f"J4: status {a.status} without a realisation date")
    if not realised and date_str:
        f.append(f"J4: status {a.status} with a realisation date")
    if date_str and not date_alias:
        f.append("J4: a realisation date without date_extract")
    # J5, J6
    if out.realisation_date and out.date_precision:
        d, p = out.realisation_date, out.date_precision
        if period_end(d, p) < t.sworn_in:
            f.append(f"J5: date {date_str} before the government took office ({t.sworn_in})")
        avail = [t.extracts[c.extract.strip()].available_by for c in cited
                 if c.extract.strip() in t.extracts and t.extracts[c.extract.strip()].available_by]
        if not avail or period_start(d, p) > max(avail):
            f.append(f"J5: date {date_str} after the latest availability date of the cited extracts "
                     f"({max(avail) if avail else 'none'})")
        if out.date_chunk_id and not date_in_chunk(d, p, t.extracts[date_alias]):
            f.append(f"J6: date {date_str} is neither the document date of {date_alias} nor written in it")
    # J7
    if t.directional and a.status in ("partial", "diluted"):
        f.append(f"J7: status {a.status} for a directional promise")
    if not realised:
        out.realisation_date = out.date_precision = out.date_chunk_id = None
    return out
