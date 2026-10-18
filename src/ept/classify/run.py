"""`ept classify run` (spec 03 §4.3–§4.5): covariates + indicators for every promise.

Per term: promises (read-only, ID order) -> deterministic batches -> one bulk call per batch -> answers
matched by alias -> checks C1–C6 per promise. A promise that fails is retried alone, once; one that
still fails gets no covariates or indicators and is logged in classify_failures_03.csv. A row in
config/classify_overrides.csv replaces the model's answer for its promise and passes C1–C6 like any
answer. `indicators_json` there is {"search_queries": [...]} (specific) or {"indicators": [{"text": ...,
"search_queries": [...]}, ...]} (vague).

Indicators: a specific promise gets `{promise_id}-I1` = its own text, `is_self` true, built by code; a
vague one gets the model's indicators as -I1…-In in its order (D-065). Then the headline cap per term
(§4.5). Writes only the 8 covariate columns of `promises`, the term's `indicators` rows, and
data/interim/classify/{term}.jsonl (+ _summary.json) with the audit fields (D-069).
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from ept import db
from ept.classify import headline as hl
from ept.classify.batches import Batch, front_matter, limit_promises, make_batches, payload, single
from ept.classify.checks import Limits, Subject, check_result, match_results, parse_override, rule_of
from ept.classify.freeze import check_writable, is_frozen, load_snapshot
from ept.classify.rubric import PROMPT, ClassifyOut, PromiseOut, covariates_version
from ept.config import Config, get_config
from ept.extract.freeze import load_frozen, snapshot_path as promise_snapshot
from ept.extract.units import Unit, read_units
from ept.llm import LLMClient, LLMValidationError, QuotaExhausted, load_prompt
from ept.runs import finish_run, progress, start_run
from ept.schema import Indicator, Promise

FAILURE_COLUMNS = ["promise_id", "rule", "detail", "resolved_by"]
COVARIATE_COLUMNS = ["sector", "promise_type", "specificity", "cost_band", "union_dependent", "continues_existing",
                     "headline", "covariates_version"]


@dataclass
class Outcome:
    """One promise after the call, the retry and any override."""

    promise: Promise
    result: Optional[PromiseOut] = None  # None = unresolved
    origin: str = "llm"  # llm | override
    retried: bool = False
    first_failures: list[str] = field(default_factory=list)  # failures of the batch answer (or the first try)
    first_answer: Optional[dict[str, Any]] = None  # the REJECTED answer, for the spot-check
    failures: list[str] = field(default_factory=list)  # unresolved
    resolved_by: str = ""  # retry alone | override


# --- calls ------------------------------------------------------------------------


@dataclass
class Caller:
    client: LLMClient
    units: dict[str, Unit]
    front_matter: str
    calls: int = 0
    cache_hits: int = 0
    extra_ids: int = 0

    def __call__(self, batch: Batch) -> tuple[dict[str, PromiseOut], dict[str, str]]:
        """Answers and C1 failures, keyed by promise_id."""
        aliases = batch.aliases()
        before = self.client.calls
        try:
            out = self.client.complete_json(PROMPT, {"front_matter": self.front_matter,
                                                     "units": payload(batch, self.units)}, ClassifyOut)
        except LLMValidationError as e:
            self.calls += self.client.calls - before
            return {}, {pid: f"C1: invalid JSON for the batch: {str(e)[:200]}" for pid in aliases.values()}
        self.calls += self.client.calls - before
        self.cache_hits += int(self.client.last.cache_hit)
        matched, c1, extras = match_results(list(aliases), out.promises)
        self.extra_ids += len(extras)
        return ({aliases[a]: r for a, r in matched.items()}, {aliases[a]: f for a, f in c1.items()})


def subject(p: Promise, units: dict[str, Unit]) -> Subject:
    unit = units.get(p.parent_group or "")
    return Subject(text=p.text, source_text=p.source_text, source_lang=p.source_lang, section=p.section,
                   unit_text=unit.text if unit else "")


def _judge(p: Promise, answers: dict[str, PromiseOut], c1: dict[str, str], units: dict[str, Unit],
           lim: Limits) -> tuple[Optional[PromiseOut], list[str]]:
    if p.promise_id in c1:
        return None, [c1[p.promise_id]]
    r = answers[p.promise_id]
    fails = check_result(r, subject(p, units), lim)
    return (None, fails) if fails else (r, [])


def classify_batch(call: Caller, batch: Batch, overrides: dict[str, dict[str, str]], lim: Limits) -> list[Outcome]:
    answers, c1 = call(batch)
    outcomes = []
    for p in batch.promises:
        o = Outcome(promise=p)
        o.result, fails = _judge(p, answers, c1, call.units, lim)
        if fails:  # retry this promise alone, once
            o.first_failures = fails
            if p.promise_id in answers:
                o.first_answer = answers[p.promise_id].model_dump(exclude={"promise_id"})
            o.retried = True
            a2, c2 = call(single(batch, p))
            o.result, fails = _judge(p, a2, c2, call.units, lim)
            if not fails:
                o.resolved_by = "retry alone"
        if p.promise_id in overrides:
            r, f = parse_override(overrides[p.promise_id], "P01")
            if r is not None:
                f = check_result(r, subject(p, call.units), lim)
            if fails and not f:
                o.resolved_by = "override"
            o.origin, o.result, fails = "override", (r if not f else None), f
        o.failures = fails
        outcomes.append(o)
    return outcomes


# --- records -------------------------------------------------------------------------


def indicators_for(p: Promise, r: PromiseOut) -> list[Indicator]:
    if r.specificity == "specific":
        return [Indicator(indicator_id=f"{p.promise_id}-I1", promise_id=p.promise_id, text=p.text, is_self=True,
                          search_queries=list(r.search_queries))]
    return [Indicator(indicator_id=f"{p.promise_id}-I{i}", promise_id=p.promise_id, text=ind.text, is_self=False,
                      search_queries=list(ind.search_queries)) for i, ind in enumerate(r.indicators, 1)]


def record(o: Outcome, version: str, head: tuple[bool, Optional[int]]) -> dict[str, Any]:
    """One snapshot line (§3): covariates, audit fields, indicators. Unresolved -> covariates null."""
    p, r = o.promise, o.result
    if r is None:
        return {"promise_id": p.promise_id, **{c: None for c in COVARIATE_COLUMNS}, "union_basis": None,
                "continues_cue": None, "headline_signal": None, "headline_rank": None, "indicators": []}
    return {
        "promise_id": p.promise_id, "sector": r.sector, "promise_type": r.promise_type,
        "specificity": r.specificity, "cost_band": r.cost_band, "union_dependent": r.union_dependent,
        "continues_existing": r.continues_existing, "headline": head[0], "covariates_version": version,
        "union_basis": r.union_basis, "continues_cue": r.continues_cue, "headline_signal": r.headline_signal,
        "headline_rank": head[1],
        "indicators": [i.model_dump(exclude={"promise_id"}) for i in indicators_for(p, r)],
    }


def write_db(conn, records: list[dict[str, Any]]) -> None:
    """Only the covariate columns of `promises` and the promises' `indicators` rows."""
    sets = ", ".join(f"{c} = ?" for c in COVARIATE_COLUMNS)
    with conn:
        for rec in records:
            conn.execute(f"UPDATE promises SET {sets} WHERE promise_id = ?",
                         [rec[c] for c in COVARIATE_COLUMNS] + [rec["promise_id"]])
            conn.execute("DELETE FROM indicators WHERE promise_id = ?", (rec["promise_id"],))
            for ind in rec["indicators"]:
                db.upsert(conn, Indicator(promise_id=rec["promise_id"], **ind), commit=False)


def interim_path(cfg: Config, term: str) -> Path:
    return cfg.path("classify_interim") / f"{term}.jsonl"


def summary_path(cfg: Config, term: str) -> Path:
    return cfg.path("classify_interim") / f"{term}_summary.json"


def read_interim(cfg: Config, term: str) -> list[dict[str, Any]]:
    path = interim_path(cfg, term)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def read_summary(cfg: Config, term: str) -> dict[str, Any]:
    path = summary_path(cfg, term)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_overrides(cfg: Config) -> dict[str, dict[str, str]]:
    path = cfg.path("classify_overrides")
    if not path.exists():
        return {}
    with path.open(encoding="utf-8", newline="") as f:
        return {r["promise_id"]: r for r in csv.DictReader(f) if r.get("promise_id")}


def _write_failures(cfg: Config, term: str, outcomes: list[Outcome]) -> None:
    path = cfg.path("classify_failures")
    keep = []
    if path.exists():
        with path.open(encoding="utf-8", newline="") as f:
            keep = [r for r in csv.DictReader(f) if not r["promise_id"].startswith(term + "-")]
    rows = []
    for o in outcomes:
        first = o.first_failures if o.retried else o.failures
        for fail in first:
            rows.append({"promise_id": o.promise.promise_id, "rule": rule_of(fail), "detail": fail,
                         "resolved_by": o.resolved_by if not o.failures else ""})
        if o.retried and o.failures and o.failures != o.first_failures:
            rows += [{"promise_id": o.promise.promise_id, "rule": rule_of(f), "detail": f"after retry: {f}",
                      "resolved_by": ""} for f in o.failures]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FAILURE_COLUMNS)
        w.writeheader()
        w.writerows(keep + rows)


# --- a term --------------------------------------------------------------------------


def term_promises(conn, cfg: Config, term: str) -> list[Promise]:
    rows = db.select_models(conn, "promises", "term_id = ? ORDER BY promise_id", (term,))
    if not rows and promise_snapshot(cfg, term).exists():
        load_frozen(conn, cfg, term)  # stage 02 snapshot, read-only (D-039)
        rows = db.select_models(conn, "promises", "term_id = ? ORDER BY promise_id", (term,))
    return rows  # type: ignore[return-value]


def classify_term(conn, client: LLMClient, cfg: Config, term: str, limit: Optional[int]) -> dict[str, Any]:
    c = cfg.settings.classify
    version = covariates_version(load_prompt(PROMPT, cfg).version)
    all_promises = term_promises(conn, cfg, term)
    promises = limit_promises(all_promises, limit)
    unit_list = read_units(cfg, term)
    units = {u.unit_id: u for u in unit_list}
    fm = front_matter(unit_list)
    call = Caller(client, units, fm)
    overrides = read_overrides(cfg)
    lim = Limits.from_config(cfg)
    batches = make_batches(promises, c.promises_per_call)
    outcomes: list[Outcome] = []
    for i, b in enumerate(batches, 1):
        progress(f"classify: {term} batch {i}/{len(batches)} ({len(b.promises)} promises)")
        outcomes += classify_batch(call, b, overrides, lim)

    fm_words = hl.words(fm)
    heads = hl.assign([hl.Candidate(o.promise.promise_id, o.result.headline_signal, o.result.cost_band,
                                    hl.frontmatter_overlap(o.promise.source_text, fm_words)
                                    >= c.headline_frontmatter_ratio)
                       for o in outcomes if o.result is not None], c.headline_cap)
    records = []
    for o in outcomes:
        rec = record(o, version, heads.get(o.promise.promise_id, (False, None)))
        rec.update(origin=o.origin, retried=o.retried, resolved_by=o.resolved_by, first_failures=o.first_failures,
                   first_answer=o.first_answer, failures=o.failures)
        records.append(rec)
    write_db(conn, records)
    path = interim_path(cfg, term)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8")
    _write_failures(cfg, term, outcomes)
    done = [r for r in records if r["sector"] is not None]
    summary = {
        "term": term, "covariates_version": version, "limit": limit, "promises_in_term": len(all_promises),
        "promises": len(records), "classified": len(done), "unresolved": len(records) - len(done),
        "batches": len(batches), "llm_calls": call.calls, "cache_hits": call.cache_hits,
        "retried": sum(o.retried for o in outcomes), "resolved_by_retry": sum(o.resolved_by == "retry alone"
                                                                              for o in outcomes),
        "overrides": sum(o.origin == "override" for o in outcomes), "extra_ids": call.extra_ids,
        "vague": sum(r["specificity"] == "vague" for r in done),
        "vague_share": round(sum(r["specificity"] == "vague" for r in done) / len(done), 4) if done else None,
        "headline": sum(bool(r["headline"]) for r in done),
    }
    summary_path(cfg, term).write_text(json.dumps(summary, indent=1), encoding="utf-8")
    return summary


def run_classify(term: Optional[str] = None, limit: Optional[int] = None, force: bool = False) -> dict[str, Any]:
    """`--limit N` = the first N promises per term (rounded up to a whole unit). Answers come from the LLM
    cache on a re-run (0 backend calls); a prompt version bump is what re-asks the model. A frozen term is
    loaded from its snapshot; re-classifying it is refused (`--force` included)."""
    cfg = get_config()
    terms = [term] if term else [t.term_id for t in cfg.settings.terms]
    run_id = start_run("classify", {"term": term, "limit": limit, "force": force})
    client = LLMClient(cfg)
    conn = db.connect()
    db.init_schema(conn)
    db.sync_terms(conn)
    stats: dict[str, Any] = {"promises": 0, "classified": 0, "unresolved": 0, "llm_calls": 0, "terms": {},
                             "skipped": {}, "stopped": None}
    try:
        for term_id in terms:
            if is_frozen(cfg, term_id):
                if force:
                    check_writable(cfg, term_id)
                stats["skipped"][term_id] = f"frozen: {load_snapshot(conn, cfg, term_id)} promises loaded"
                continue
            before = client.calls
            try:
                s = classify_term(conn, client, cfg, term_id, limit)
            except QuotaExhausted as e:
                stats["stopped"] = str(e)
                stats["llm_calls"] += client.calls - before
                break
            stats["terms"][term_id] = s
            for k in ("promises", "classified", "unresolved", "llm_calls"):
                stats[k] += s[k]
    finally:
        conn.close()
        finish_run(run_id, stats, models={"bulk": cfg.settings.llm.models.get("bulk")},
                   status=f"stopped: {stats['stopped']}" if stats["stopped"] else "done")
    return stats
