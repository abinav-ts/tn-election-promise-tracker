"""`ept judge aggregate` (spec 05 §4.7, D-088): indicator verdicts → one promise verdict per promise × run × cutoff.

From one run's indicator verdicts only:
1. one indicator → the promise verdict equals it;
2. directional → any dated indicator → fulfilled; else in_progress; else blocked_external; else all unverifiable
   → unverifiable; else not_started;
3. otherwise, first match: all fulfilled → fulfilled; all diluted → diluted; any realised → partial; any
   in_progress; any blocked_external; all unverifiable; else not_started.
Fields: the earliest dated indicator's date (by period_start, ties → finer precision); cited chunks = union in
indicator order; confidence = minimum; needs_review = any; rationale built by code. A run aggregates only
promise × cutoffs whose indicators it judged in full.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Any, Optional

from ept import db
from ept.config import get_config
from ept.dates import period_start
from ept.judge import directional as dirmod
from ept.judge.store import indicator_rows, latest_run, runs, verdict_rows, write_verdicts
from ept.schema import IndicatorVerdict, Verdict

REALISED = ("fulfilled", "partial", "diluted")
_PREC = {"day": 0, "month": 1, "year": 2}


@dataclass
class Agg:
    status: str
    realisation_date: Optional[dt.date] = None
    date_precision: Optional[str] = None
    date_chunk_id: Optional[str] = None
    cited_chunk_ids: list[str] = field(default_factory=list)
    rationale: str = ""
    confidence: float = 0.0
    needs_review: bool = False


def date_sort_key(d: dt.date, precision: str) -> tuple[dt.date, int]:
    """Earliest first; at equal period start, the finer precision first."""
    return period_start(d, precision), _PREC[precision]


def combine_status(statuses: list[str], dated: list[bool], directional: bool) -> str:
    if len(statuses) == 1:
        return statuses[0]
    if directional:
        if any(dated):
            return "fulfilled"
        for s in ("in_progress", "blocked_external"):
            if s in statuses:
                return s
        return "unverifiable" if all(s == "unverifiable" for s in statuses) else "not_started"
    if all(s == "fulfilled" for s in statuses):
        return "fulfilled"
    if all(s == "diluted" for s in statuses):
        return "diluted"
    if any(s in REALISED for s in statuses):
        return "partial"
    for s in ("in_progress", "blocked_external"):
        if s in statuses:
            return s
    return "unverifiable" if all(s == "unverifiable" for s in statuses) else "not_started"


def _label(iid: str) -> str:
    return "I" + iid.rsplit("-I", 1)[1]


def aggregate(rows: list[IndicatorVerdict], directional: bool, max_words: int,
              aliases: Optional[dict[str, dict[str, str]]] = None) -> Agg:
    """`rows` = all indicator verdicts of one promise × run × cutoff, in indicator order. `aliases` maps
    indicator_id → {chunk_id: extract alias} for the rationale (optional)."""
    rows = sorted(rows, key=lambda r: int(r.indicator_id.rsplit("-I", 1)[1]))
    statuses = [r.status for r in rows]
    status = combine_status(statuses, [r.realisation_date is not None for r in rows], directional)
    out = Agg(status=status, confidence=min(r.confidence for r in rows), needs_review=any(r.needs_review for r in rows))
    for r in rows:
        for c in r.cited_chunk_ids:
            if c not in out.cited_chunk_ids:
                out.cited_chunk_ids.append(c)
    if status in REALISED:
        dated = [r for r in rows if r.realisation_date is not None]
        best = min(dated, key=lambda r: date_sort_key(r.realisation_date, r.date_precision))
        out.realisation_date, out.date_precision, out.date_chunk_id = (best.realisation_date, best.date_precision,
                                                                       best.date_chunk_id)
    if len(rows) == 1:
        out.rationale = rows[0].rationale
        return out
    parts = []
    for r in rows:
        p = f"{_label(r.indicator_id)} {r.status}"
        if r.realisation_date is not None:
            shown = {"day": r.realisation_date.isoformat(), "month": r.realisation_date.strftime("%Y-%m"),
                     "year": str(r.realisation_date.year)}[r.date_precision]
            alias = (aliases or {}).get(r.indicator_id, {}).get(r.date_chunk_id or "", "")
            p += f" {shown}" + (f" ({alias})" if alias else "")
        parts.append(p)
    head = "; ".join(parts) + "."
    room = max_words - len(head.split())
    first = rows[0].rationale.split()
    out.rationale = head if room <= 1 else head + " " + " ".join(first[:room - 1] if len(first) > room - 1
                                                                 else first)
    out.rationale = " ".join(out.rationale.split()[:max_words])
    return out


def to_verdict(promise_id: str, run_id: str, cutoff_date: Optional[dt.date], a: Agg, source: str,
               model: Optional[str], version: Optional[str]) -> Verdict:
    return Verdict(promise_id=promise_id, run_id=run_id, cutoff_date=cutoff_date, status=a.status,
                   realisation_date=a.realisation_date, date_precision=a.date_precision,
                   cited_chunk_ids=a.cited_chunk_ids, rationale=a.rationale, confidence=a.confidence,
                   needs_review=a.needs_review, judge_source=source, judge_model=model, prompt_version=version)


def promise_verdicts(rows: list[IndicatorVerdict], indicators_by_promise: dict[str, list[str]],
                     directional: dict[str, bool], max_words: int) -> dict[tuple[str, Optional[dt.date]], Agg]:
    """{(promise_id, cutoff_date): Agg} for every promise × cutoff whose indicators are all present."""
    by: dict[tuple[str, Optional[dt.date]], dict[str, IndicatorVerdict]] = {}
    for r in rows:
        pid = r.indicator_id.rsplit("-I", 1)[0]
        by.setdefault((pid, r.cutoff_date), {})[r.indicator_id] = r
    out = {}
    for (pid, cut), got in by.items():
        want = indicators_by_promise.get(pid, [])
        if not want or any(i not in got for i in want):
            continue
        out[(pid, cut)] = aggregate([got[i] for i in want], directional.get(pid, False), max_words)
    return out


def aggregate_run(conn, run_id: str) -> dict[str, Any]:
    """Write `verdicts` for one bulk or strong run; rows identical to the stored ones are not rewritten."""
    cfg = get_config()
    rows = indicator_rows(conn, run_id)
    by_promise: dict[str, list[str]] = {}
    for r in conn.execute("SELECT indicator_id, promise_id FROM indicators ORDER BY indicator_id"):
        by_promise.setdefault(r["promise_id"], []).append(r["indicator_id"])
    flags = dirmod.load_all(cfg, [t.term_id for t in cfg.settings.terms])
    aggs = promise_verdicts(rows, by_promise, flags, cfg.settings.judge.rationale_max_words)
    first = rows[0] if rows else None
    source = first.judge_source if first else "bulk"
    new = [to_verdict(pid, run_id, cut, a, source, first.judge_model if first else None,
                      first.prompt_version if first else None) for (pid, cut), a in sorted(
        aggs.items(), key=lambda kv: (kv[0][0], kv[0][1] or dt.date.max))]
    old = {(v.promise_id, v.cutoff_date): v for v in verdict_rows(conn, run_id)}
    changed = [v for v in new if old.get((v.promise_id, v.cutoff_date)) != v]
    write_verdicts(conn, changed)
    return {"run_id": run_id, "promise_cutoffs": len(new), "written": len(changed)}


def run_aggregate(run_id: Optional[str] = None) -> dict[str, Any]:
    """Default: the latest bulk run and every strong run."""
    cfg = get_config()
    conn = db.connect()
    db.init_schema(conn)
    if run_id:
        targets = [run_id]
    else:
        bulk = latest_run(cfg, "bulk")
        targets = ([bulk["run_id"]] if bulk else []) + [m["run_id"] for m in runs(cfg, "strong")]
    out = {"runs": [aggregate_run(conn, r) for r in targets]}
    conn.close()
    return out
