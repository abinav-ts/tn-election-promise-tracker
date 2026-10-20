"""Cutoffs and the eligible set (spec 04 §4.2–§4.3, D-075–D-077).

A chunk is eligible for a run iff its availability date (`ept.dates.available_by`) is known and
`sworn_in` ≤ available_by ≤ cutoff (landmark) or `term_end` (full term). Undated chunks are never eligible.
"""

from __future__ import annotations

import datetime as dt
import sqlite3
from dataclasses import dataclass
from typing import Any, Optional

from ept.config import Config
from ept.dates import add_months, availability, parse_iso
from ept.schema import Term

FULL = "full"


class CutoffRefused(ValueError):
    """A cutoff after `term_end` or after the corpus snapshot (spec 04 §4.3)."""


@dataclass(frozen=True)
class Cutoff:
    term_id: str
    label: str  # "m5", "m12", … or "full"
    month: Optional[int]
    cutoff_date: Optional[dt.date]  # retrievals.cutoff_date; None = full term
    lower: dt.date  # sworn_in
    upper: dt.date  # the cutoff, or term_end for a full-term run

    @property
    def key(self) -> str:
        """Used in spot-check item ids: the cutoff date, or 'full'."""
        return self.cutoff_date.isoformat() if self.cutoff_date else FULL


@dataclass(frozen=True)
class ChunkAvail:
    chunk_id: str
    doc_id: str
    doc_type: str
    available_by: Optional[dt.date]
    basis: Optional[str]  # dates.BASIS_*; None = undated


def load_availability(conn: sqlite3.Connection, cfg: Config) -> list[ChunkAvail]:
    """Every chunk with its document's availability date, in chunk_id order."""
    fyb = cfg.settings.date.fy_bound
    docs: dict[str, tuple[str, Optional[dt.date], Optional[str]]] = {}
    for r in conn.execute("SELECT doc_id, doc_type, doc_date, date_precision, fiscal_year, title FROM documents"):
        a, basis = availability(r["doc_date"], r["date_precision"], r["doc_type"], r["fiscal_year"], r["title"], fyb)
        docs[r["doc_id"]] = (r["doc_type"], a, basis)
    out = []
    for r in conn.execute("SELECT chunk_id, doc_id FROM chunks ORDER BY chunk_id"):
        doc_type, a, basis = docs[r["doc_id"]]
        out.append(ChunkAvail(r["chunk_id"], r["doc_id"], doc_type, a, basis))
    return out


def latest_fetch(conn: sqlite3.Connection) -> Optional[dt.date]:
    row = conn.execute("SELECT max(fetched_at) FROM documents").fetchone()
    return parse_iso(row[0]) if row and row[0] else None


def snapshot_end(cfg: Config, avail: list[ChunkAvail], fetched: Optional[dt.date] = None) -> dt.date:
    """`evidence_window.end`, else the latest availability date in the corpus, but never after the latest
    fetch (`fetched`): fiscal-year and year-precision bounds can lie in the future (build clarification)."""
    if cfg.settings.evidence_window.end:
        return cfg.settings.evidence_window.end
    dates = [c.available_by for c in avail if c.available_by]
    if not dates:
        raise CutoffRefused("the corpus has no dated chunk")
    return min(max(dates), fetched) if fetched else max(dates)


def landmark(term: Term, month: int, snapshot: dt.date) -> Cutoff:
    sworn = parse_iso(term.sworn_in)
    c = add_months(sworn, month)
    if term.term_end and c > parse_iso(term.term_end):
        raise CutoffRefused(f"{term.term_id} month {month} ({c}) is after term_end {term.term_end}")
    if c > snapshot:
        raise CutoffRefused(f"{term.term_id} month {month} ({c}) is after the corpus snapshot {snapshot}")
    return Cutoff(term.term_id, f"m{month}", month, c, sworn, c)


def full_term(term: Term) -> Cutoff:
    if not term.term_end:
        raise CutoffRefused(f"{term.term_id} is ongoing: no full-term run (D-075)")
    return Cutoff(term.term_id, FULL, None, None, parse_iso(term.sworn_in), parse_iso(term.term_end))


def term_cutoffs(cfg: Config, term_id: str, snapshot: dt.date, only: Optional[list[str]] = None) -> list[Cutoff]:
    """The configured cutoffs of a term (landmarks, then full term), optionally restricted by `--cutoff`
    values ('full' or a landmark month). A requested cutoff that isn't configured is refused."""
    r = cfg.settings.retrieve
    term = cfg.term(term_id)
    months = list(r.landmarks_months.get(term_id, []))
    want_full = r.full_term and term.term_end is not None
    if only:
        req_months = {int(o) for o in only if o != FULL}
        unknown = req_months - set(months)
        if unknown or (FULL in only and not want_full):
            raise CutoffRefused(f"{term_id}: cutoff(s) {sorted(unknown) or [FULL]} not configured "
                                f"(landmarks {months}, full term {want_full})")
        months = [m for m in months if m in req_months]
        want_full = want_full and FULL in only
    out = [landmark(term, m, snapshot) for m in months]
    if want_full:
        out.append(full_term(term))
    return out


def eligible(c: ChunkAvail, cutoff: Cutoff) -> bool:
    return c.available_by is not None and cutoff.lower <= c.available_by <= cutoff.upper


def eligible_indices(avail: list[ChunkAvail], cutoff: Cutoff) -> list[int]:
    return [i for i, c in enumerate(avail) if eligible(c, cutoff)]


def exclusions(avail: list[ChunkAvail], cutoff: Cutoff) -> dict[str, int]:
    """Why chunks are not eligible (report §4.9 item 1)."""
    out = {"undated": 0, "before_sworn_in": 0, "after_cutoff": 0}
    for c in avail:
        if c.available_by is None:
            out["undated"] += 1
        elif c.available_by < cutoff.lower:
            out["before_sworn_in"] += 1
        elif c.available_by > cutoff.upper:
            out["after_cutoff"] += 1
    return out


def check_retrievals(conn: sqlite3.Connection, cfg: Config, run_id: Optional[str] = None) -> dict[str, Any]:
    """DB-wide leakage check (spec 04 §4.9 item 6, §6 criterion 2): every retrievals row must satisfy
    sworn_in ≤ available_by ≤ (cutoff_date, or term_end for a full-term row); undated chunks never appear."""
    avail = {c.chunk_id: c for c in load_availability(conn, cfg)}
    terms = {t.term_id: t for t in cfg.settings.terms}
    sql = ("SELECT r.indicator_id, r.chunk_id, r.cutoff_date, r.run_id, p.term_id FROM retrievals r "
           "JOIN indicators i ON i.indicator_id = r.indicator_id JOIN promises p ON p.promise_id = i.promise_id")
    params: list[Any] = []
    if run_id:
        sql += " WHERE r.run_id = ?"
        params.append(run_id)
    rows = violations = undated = missing = 0
    examples: list[dict[str, Any]] = []
    for r in conn.execute(sql, params):
        rows += 1
        c = avail.get(r["chunk_id"])
        term = terms[r["term_id"]]
        upper = parse_iso(r["cutoff_date"]) if r["cutoff_date"] else (parse_iso(term.term_end) if term.term_end
                                                                       else None)
        bad = None
        if c is None:
            missing += 1
            bad = "chunk not in corpus"
        elif c.available_by is None:
            undated += 1
            bad = "undated chunk"
        elif c.available_by < parse_iso(term.sworn_in):
            bad = f"available_by {c.available_by} before sworn_in {term.sworn_in}"
        elif upper is None or c.available_by > upper:
            bad = f"available_by {c.available_by} after bound {upper}"
        if bad:
            violations += 1
            if len(examples) < 10:
                examples.append({"indicator_id": r["indicator_id"], "chunk_id": r["chunk_id"],
                                 "cutoff_date": r["cutoff_date"], "run_id": r["run_id"], "why": bad})
    return {"rows": rows, "violations": violations, "undated": undated, "missing_chunks": missing,
            "examples": examples}
