"""`ept judge final` (spec 05 §4.10, D-090): one verdict per promise × cutoff for stages 07 and 08.

Selection per promise × cutoff: human (config/verdict_overrides.csv: rows made only from approved spot-check
fixes, each with a source `spotcheck_NN#n` and a reason; never gold labels) > strong (the latest strong run
covering it) > bulk (the latest complete bulk run).

Carry-forward (leak-safe: evidence available at an earlier cutoff is available at every later one), cutoffs in
time order with the full term last:
- a selected verdict with a date takes the earliest date among the selected verdicts at cutoffs ≤ i (with that
  verdict's precision); its date chunk joins `cited_chunk_ids`;
- a selected verdict without a date, after a realised one, is replaced by the latest earlier realised verdict
  (status, date, citations), with `needs_review` and reason `non_monotone`.
So "realised by cutoff" never flips from yes to no. Raw per-run verdicts stay unchanged. The run is exported to
data/judgments/final_{run_id}.jsonl (committed).
"""

from __future__ import annotations

import csv
import datetime as dt
import json
from dataclasses import dataclass, field
from typing import Any, Optional

from ept import db
from ept.config import Config, get_config
from ept.dates import parse_iso
from ept.judge.aggregate import REALISED, date_sort_key
from ept.judge.store import (code_hash, file_sha, fp_hash, latest_run, read_meta, runs, start_or_resume, update_meta,
                             verdict_rows, write_verdicts)
from ept.judge.tasks import Context
from ept.runs import finish_run
from ept.schema import Status, Verdict

OVERRIDE_COLUMNS = ["promise_id", "cutoff", "status", "realisation_date", "date_precision", "cited_chunk_ids",
                    "source", "reason"]
FINAL_CODE = ["dates.py", "judge/aggregate.py", "judge/final.py"]


class OverrideError(ValueError):
    pass


@dataclass
class Pick:
    """One promise × cutoff verdict as selected, plus what carry-forward needs."""

    verdict: Verdict
    date_chunk_id: Optional[str] = None
    reasons: list[str] = field(default_factory=list)

    @property
    def realised(self) -> bool:
        return self.verdict.realisation_date is not None


# --- overrides --------------------------------------------------------------------------------------


def read_overrides(cfg: Config) -> list[dict[str, str]]:
    path = cfg.path("verdict_overrides")
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as f:
        return [r for r in csv.DictReader(f) if (r.get("promise_id") or "").strip()]


def validate_override(r: dict[str, str], cutoffs: set[str]) -> None:
    """Every human verdict has a reason and a spot-check source, and none comes from the gold set."""
    where = f"verdict_overrides.csv {r.get('promise_id')}@{r.get('cutoff')}"
    if not (r.get("reason") or "").strip():
        raise OverrideError(f"{where}: no reason")
    src = (r.get("source") or "").strip()
    if not src.startswith("spotcheck_"):
        raise OverrideError(f"{where}: source {src!r} is not a spot-check item (spotcheck_NN#n)")
    if any("gold" in (v or "").lower() for v in r.values()):
        raise OverrideError(f"{where}: refers to the gold set (gold labels are never human overrides, D-090)")
    if r.get("status") not in [s.value for s in Status]:
        raise OverrideError(f"{where}: status {r.get('status')!r} not in §8")
    has_date = bool((r.get("realisation_date") or "").strip())
    if (r["status"] in REALISED) != has_date or (has_date and not (r.get("date_precision") or "").strip()):
        raise OverrideError(f"{where}: a date (with precision) is required iff the status is realised")
    if r.get("cutoff") not in cutoffs:
        raise OverrideError(f"{where}: cutoff {r.get('cutoff')!r} is not a configured cutoff of the term")


def override_verdict(r: dict[str, str], run_id: str) -> Verdict:
    cut = None if r["cutoff"] == "full" else parse_iso(r["cutoff"])
    cited = [c.strip() for c in (r.get("cited_chunk_ids") or "").split(";") if c.strip()]
    return Verdict(promise_id=r["promise_id"], run_id=run_id, cutoff_date=cut, status=r["status"],
                   realisation_date=r.get("realisation_date") or None, date_precision=r.get("date_precision") or None,
                   cited_chunk_ids=cited, rationale=" ".join(f"Human override ({r['source']}): {r['reason']}".split()[:80]),
                   confidence=1.0, needs_review=False, judge_source="human", judge_model="human",
                   prompt_version=None)


# --- carry-forward ------------------------------------------------------------------------------------


def carry_forward(picks: list[Pick]) -> list[Pick]:
    """`picks` of one promise in cutoff time order → carried picks (same order)."""
    out: list[Pick] = []
    earliest: Optional[Pick] = None  # the earliest-dated realised pick so far
    latest_realised: Optional[Pick] = None
    for p in picks:
        v = p.verdict
        if p.realised:
            if earliest is None or date_sort_key(p.verdict.realisation_date, p.verdict.date_precision) < \
                    date_sort_key(earliest.verdict.realisation_date, earliest.verdict.date_precision):
                earliest = p
            cited = list(v.cited_chunk_ids)
            if earliest.date_chunk_id and earliest.date_chunk_id not in cited:
                cited.append(earliest.date_chunk_id)
            new = v.model_copy(update={"realisation_date": earliest.verdict.realisation_date,
                                       "date_precision": earliest.verdict.date_precision, "cited_chunk_ids": cited})
            q = Pick(new, earliest.date_chunk_id, list(p.reasons))
            latest_realised = q
            out.append(q)
        elif latest_realised is not None:
            lv = latest_realised.verdict
            note = f"[non_monotone] carried from an earlier cutoff; this cutoff said {v.status}."
            carried = lv.model_copy(update={"cutoff_date": v.cutoff_date, "needs_review": True,
                                            "rationale": " ".join((note + " " + lv.rationale).split()[:80])})
            out.append(Pick(carried, latest_realised.date_chunk_id, list(latest_realised.reasons) + ["non_monotone"]))
        else:
            out.append(p)
    return out


def non_monotone(statuses_in_order: list[Optional[dt.date]]) -> bool:
    """True if a realised cutoff is followed by an unrealised one (dates in cutoff order; None = not realised)."""
    seen = False
    for d in statuses_in_order:
        if d is not None:
            seen = True
        elif seen:
            return True
    return False


# --- run ---------------------------------------------------------------------------------------------------


def _date_chunks(conn, run_id: str) -> dict[tuple[str, Optional[str]], Optional[str]]:
    """{(promise_id, cutoff iso): date chunk of its earliest-dated indicator verdict} for one run."""
    best: dict[tuple[str, Optional[str]], tuple] = {}
    for r in conn.execute("SELECT indicator_id, cutoff_date, realisation_date, date_precision, date_chunk_id "
                          "FROM indicator_verdicts WHERE run_id = ? AND realisation_date IS NOT NULL", (run_id,)):
        k = (r["indicator_id"].rsplit("-I", 1)[0], r["cutoff_date"])
        sk = date_sort_key(parse_iso(r["realisation_date"]), r["date_precision"])
        if k not in best or sk < best[k][0]:
            best[k] = (sk, r["date_chunk_id"])
    return {k: v[1] for k, v in best.items()}


def run_final(force: bool = False) -> dict[str, Any]:
    cfg = get_config()
    conn = db.connect()
    db.init_schema(conn)
    bulk = latest_run(cfg, "bulk", complete_only=True) or latest_run(cfg, "bulk")
    if not bulk:
        raise RuntimeError("no bulk run: run `ept judge run` first")
    strong = runs(cfg, "strong")
    overrides = read_overrides(cfg)
    fp = fp_hash({"bulk": bulk["run_id"], "bulk_complete": bool(bulk.get("complete")),
                  "bulk_rows": conn.execute("SELECT count(*) FROM verdicts WHERE run_id = ?", (bulk["run_id"],)).fetchone()[0],
                  "strong": [(m["run_id"], conn.execute("SELECT count(*) FROM verdicts WHERE run_id = ?",
                                                        (m["run_id"],)).fetchone()[0]) for m in strong],
                  "overrides": file_sha(cfg.path("verdict_overrides")), "code": code_hash(FINAL_CODE)})
    run_id, resumed = start_or_resume(cfg, "final", fp, force, {"force": force},
                                      extra={"bulk_run": bulk["run_id"], "strong_runs": [m["run_id"] for m in strong]})
    if resumed and read_meta(cfg, run_id).get("complete"):
        conn.close()
        return {"run_id": run_id, "resumed": True, "written": 0}
    ctx = Context(conn, cfg)
    order: dict[str, list[Optional[dt.date]]] = {}
    for t in cfg.settings.terms:
        order[t.term_id] = [c.cutoff_date for c in ctx.cutoffs(t.term_id)]
    # selection: bulk, then strong (later runs win), then human
    chosen: dict[tuple[str, Optional[dt.date]], Pick] = {}
    for src_run in [bulk["run_id"]] + [m["run_id"] for m in strong]:
        dchunks = _date_chunks(conn, src_run)
        for v in verdict_rows(conn, src_run):
            chosen[(v.promise_id, v.cutoff_date)] = Pick(
                v, dchunks.get((v.promise_id, v.cutoff_date.isoformat() if v.cutoff_date else None)))
    for r in overrides:
        term = r.get("promise_id", "").rsplit("-", 1)[0]
        cuts = {c.key for c in ctx.cutoffs(term)} if term in order else set()
        validate_override(r, cuts)
        v = override_verdict(r, run_id)
        chosen[(v.promise_id, v.cutoff_date)] = Pick(v, None)
    by_promise: dict[str, list[Pick]] = {}
    for (pid, cut), p in chosen.items():
        by_promise.setdefault(pid, []).append(p)
    finals: list[tuple[Pick, str]] = []
    for pid, picks in sorted(by_promise.items()):
        term = ctx.promises[pid]["term_id"]
        seq = order[term]
        picks.sort(key=lambda p: seq.index(p.verdict.cutoff_date) if p.verdict.cutoff_date in seq else len(seq))
        for p in carry_forward(picks):
            finals.append((p, p.verdict.judge_source))
    rows = [p.verdict.model_copy(update={"run_id": run_id}) for p, _ in finals]
    write_verdicts(conn, rows)
    out_path = cfg.path("judgments") / f"final_{run_id}.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for p, _ in finals:
            rec = p.verdict.model_copy(update={"run_id": run_id}).model_dump(mode="json")
            rec.update(date_chunk_id=p.date_chunk_id, review_reasons=p.reasons)
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    missing = _coverage_gaps(ctx, chosen)
    stats = {"run_id": run_id, "resumed": resumed, "written": len(rows),
             "non_monotone": sum("non_monotone" in p.reasons for p, _ in finals),
             "sources": {s: sum(1 for _, x in finals if x == s) for s in ("bulk", "strong", "human")},
             "missing_promise_cutoffs": missing, "export": str(out_path.relative_to(cfg.root))}
    finish_run(run_id, counts=stats)
    update_meta(cfg, run_id, kind="final", fingerprint=fp, complete=missing == 0, bulk_run=bulk["run_id"],
                strong_runs=[m["run_id"] for m in strong])
    conn.close()
    return stats


def _coverage_gaps(ctx: Context, chosen: dict) -> int:
    n = 0
    for pid, p in ctx.promises.items():
        if pid not in ctx.by_promise:
            continue
        for c in ctx.cutoffs(p["term_id"]):
            if (pid, c.cutoff_date) not in chosen:
                n += 1
    return n
