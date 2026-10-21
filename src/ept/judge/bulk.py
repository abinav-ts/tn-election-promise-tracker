"""`ept judge run` (spec 05 §4.5, D-085): the bulk model judges every judging key of a tier.

Per tier (A, then B): keys not yet stored in this run → groups of one term and one judging cutoff → calls of
`judge.bulk.tasks_per_call` keys in indicator_id order (deterministic, so a re-run hits the cache) → checks
J1–J7 per task. A group's failing tasks are re-asked in mini-batches of `retry_tasks_per_call`, then alone;
a task still failing is *unresolved*: stored as `unverifiable` with `needs_review` and reason `unresolved`, and
listed in judge_failures_05.csv. Each key's verdict is written for every cutoff that retrieved its chunk list.

Every backend call (cache hits included) is a line in the run's call log (`paths.judge_calls`): stage, term,
judging cutoff, keys, token estimate and measurement, first-answer failures. The report's leakage line and
failure rates read it.

Stops: `QuotaExhausted` (clean, exit code 2; a re-run resumes from the cache and the DB); unresolved keys above
`judge.max_unresolved_share` of a tier's keys (`StopForUser`); and, on a `--limit` run, a first-answer failure
rate above `judge.smoke_max_first_fail` (reported as `smoke_stop`).
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from ept import db
from ept.config import Config, get_config
from ept.judge import directional as dirmod
from ept.judge.checks import Checked, Limits, TaskInput, check_task, feedback, match_answers, rule_of
from ept.judge.prompt import PROMPT, JudgeOut, TaskVerdictOut, extract_alias, render_task, render_tasks, task_alias
from ept.judge.store import (code_hash, file_sha, fp_hash, read_meta, start_or_resume, stored_keys, update_meta,
                             write_indicator_verdicts)
from ept.judge.tasks import (Context, Key, MissingDirectional, batches, build_keys, groups, load_retrievals,
                             tier_list)
from ept.llm import LLMClient, LLMValidationError, QuotaExhausted, load_prompt, mock_enabled
from ept.retrieve.run import latest_run as latest_retrieval
from ept.runs import eta, finish_run, progress
from ept.schema import IndicatorVerdict

# code that shapes the rows: a change starts a new run instead of resuming (as D-081a)
ROW_CODE = ["dates.py", "judge/tasks.py", "judge/prompt.py", "judge/checks.py", "judge/bulk.py", "judge/store.py"]
FAILURE_COLUMNS = ["run_id", "judging_key", "term", "indicator_id", "judging_cutoff", "stage", "check", "detail",
                   "first_answer", "resolved_by"]


class StopForUser(RuntimeError):
    """A spec 05 §4.15 stop rule fired: the user decides before the run continues."""


@dataclass
class Outcome:
    key: Key
    checked: Optional[Checked] = None  # None = unresolved
    stage: str = "unresolved"  # first | mini | solo | unresolved
    first_failures: list[str] = field(default_factory=list)
    last_failures: list[str] = field(default_factory=list)
    first_answer: Optional[dict[str, Any]] = None  # the first answer as given (may have been rejected)


def judge_model(cfg: Config) -> str:
    return "mock" if mock_enabled() else (cfg.settings.llm.models.get("bulk") or "unset")


def fingerprint(cfg: Config, retrieval_run: str, prompt_version: str, terms: list[str]) -> dict[str, Any]:
    j = cfg.settings.judge
    return fp_hash({
        "judge": j.model_dump(mode="json", include={"tiers", "bulk", "quote", "quote_fuzzy_min", "review_confidence",
                                                   "rationale_max_words"}),
        "prompt_version": prompt_version,
        "model": judge_model(cfg),
        "directional": {t: file_sha(dirmod.path_for(cfg, t)) for t in terms},
        "retrieval_run": retrieval_run,
        "terms": [t.model_dump(mode="json") for t in cfg.settings.terms],
        "code": code_hash(ROW_CODE),
    })


def calls_path(cfg: Config, run_id: str) -> Path:
    return cfg.root / cfg.settings.paths.judge_calls.format(run_id=run_id)


def read_calls(cfg: Config, run_id: str) -> list[dict[str, Any]]:
    p = calls_path(cfg, run_id)
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x] if p.exists() else []


class Caller:
    """Renders keys as one call, asks the model, checks every task against its own input."""

    def __init__(self, client: LLMClient, ctx: Context, run_id: str, log: Path, lim: Limits,
                 call_kind: str = "bulk"):
        self.client, self.ctx, self.run_id, self.log, self.lim = client, ctx, run_id, log, lim
        self.call_kind = call_kind
        self.body = load_prompt(PROMPT, ctx.cfg).body
        self.n = 0

    def inputs(self, keys: list[Key], with_extracts: bool = True, notes: Optional[dict[str, list[str]]] = None
               ) -> tuple[list[dict], dict[str, TaskInput]]:
        items, inputs = [], {}
        for i, k in enumerate(keys, 1):
            alias = task_alias(i)
            chunks = self.ctx.chunks(k.chunk_ids) if with_extracts else {}
            ext = [chunks[c] for c in k.chunk_ids] if with_extracts else []
            ind = self.ctx.indicators[k.indicator_id]
            sworn = self.ctx.sworn_in(k.term_id)
            items.append(render_task(alias, self.ctx.promises[k.promise_id]["text"],
                                     None if ind["is_self"] else ind["text"], k.directional, sworn, ext,
                                     feedback((notes or {}).get(k.key, []))))
            inputs[alias] = TaskInput(alias, {extract_alias(j): c for j, c in enumerate(ext, 1)}, sworn, k.directional)
        return items, inputs

    def __call__(self, keys: list[Key], stage: str, with_extracts: bool = True,
                 notes: Optional[dict[str, list[str]]] = None
                 ) -> dict[str, tuple[Optional[TaskVerdictOut], Optional[Checked], list[str]]]:
        """`notes` = {key: failures of the previous answer}: shown to the model on a retry."""
        items, inputs = self.inputs(keys, with_extracts, notes)
        tasks_str = render_tasks(items)
        before = self.client.calls
        try:
            answers: Optional[list[TaskVerdictOut]] = self.client.complete_json(PROMPT, {"tasks": tasks_str},
                                                                               JudgeOut).verdicts
            error = ""
        except LLMValidationError as e:
            answers, error = None, str(e)[:200]
        out: dict[str, tuple[Optional[TaskVerdictOut], Optional[Checked], list[str]]] = {}
        extras: list[str] = []
        if answers is None:
            for k in keys:
                out[k.key] = (None, None, [f"J1: invalid JSON for the call: {error}"])
        else:
            matched, j1, extras = match_answers(list(inputs), answers)
            for i, k in enumerate(keys, 1):
                alias = task_alias(i)
                if alias in j1:
                    out[k.key] = (None, None, [j1[alias]])
                    continue
                chk = check_task(matched[alias], inputs[alias], self.lim)
                out[k.key] = (matched[alias], chk, chk.failures)
        self.n += 1
        last = self.client.last
        line = {
            "call": self.n, "run_id": self.run_id, "kind": self.call_kind, "stage": stage,
            "groups": sorted({f"{k.term_id}@{k.judging.key}" for k in keys}),
            "keys": [k.key[:16] for k in keys], "indicators": [k.indicator_id for k in keys], "n_tasks": len(keys),
            "cache_hit": last.cache_hit, "backend_calls": self.client.calls - before,
            "est_tokens": last.est_tokens or self.client.estimate_tokens(self.body + tasks_str),
            "prompt_tokens": last.prompt_tokens, "output_tokens": last.output_tokens,
            "failed": sum(1 for v in out.values() if v[2]), "extra_aliases": len(extras),
            "ts": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        }
        with self.log.open("a", encoding="utf-8") as f:
            f.write(json.dumps(line) + "\n")
        return out


def judge_group(call: Caller, group: list[Key], per_call: int, retry_size: int,
                on_batch=lambda b: None) -> list[Outcome]:
    """First calls of `per_call` keys → the group's failing tasks pooled into mini-batches of `retry_size` (spec 05
    §4.5: "from the same group") → still failing alone (`judge.bulk.solo_retries` tries, a one-task mini-batch
    counting as the first; user's decision after the smoke test, D-094) → unresolved. Each retry shows the task's
    previous check failures (`checks.feedback`); the checks are the same. Deterministic, so a resumed group is
    answered from the cache."""
    outcomes: dict[str, Outcome] = {}
    failing: list[Key] = []
    for batch in batches(group, per_call):
        res = call(batch, "first")
        for k in batch:
            ans, chk, fails = res[k.key]
            o = Outcome(k, first_failures=fails, last_failures=fails,
                        first_answer=ans.model_dump(mode="json") if ans else None)
            if fails:
                failing.append(k)
            else:
                o.checked, o.stage = chk, "first"
            outcomes[k.key] = o
        on_batch(batch)
    still: list[tuple[Key, int]] = []  # (key, tries alone already made)
    for mb in batches(failing, retry_size):
        r2 = call(mb, "mini", notes={k.key: outcomes[k.key].first_failures for k in mb})
        for k in mb:
            _, chk, fails = r2[k.key]
            o = outcomes[k.key]
            o.last_failures = fails
            if fails:
                still.append((k, 1 if len(mb) == 1 else 0))  # a one-task mini-batch counts as a try alone
            else:
                o.checked, o.stage = chk, "mini"
    for k, done in still:
        o = outcomes[k.key]
        for _ in range(call.ctx.cfg.settings.judge.bulk.solo_retries - done):  # each try sees the last failures
            _, chk, fails = call([k], "solo", notes={k.key: o.last_failures})[k.key]
            o.last_failures = fails
            if not fails:
                o.checked, o.stage = chk, "solo"
                break
    return [outcomes[k.key] for k in group]


def _words(text: str, n: int) -> str:
    w = text.split()
    return " ".join(w[:n])


def rows_for(o: Outcome, run_id: str, model: str, version: str, cfg: Config) -> list[IndicatorVerdict]:
    j = cfg.settings.judge
    c = o.checked
    if c is None:
        base = dict(status="unverifiable", rationale=_words("Unresolved after retries: " + "; ".join(o.last_failures),
                                                            j.rationale_max_words),
                    confidence=0.0, needs_review=True, review_reasons=["unresolved"])
    else:
        reasons = list(c.reasons)
        if o.stage in ("mini", "solo"):
            reasons.insert(0, "retried")
        if c.confidence < j.review_confidence:
            reasons.insert(0, "low_confidence")
        base = dict(status=c.status, realisation_date=c.realisation_date, date_precision=c.date_precision,
                    date_chunk_id=c.date_chunk_id, cited_chunk_ids=c.cited_chunk_ids, quotes=c.quotes,
                    rationale=c.rationale, confidence=c.confidence, needs_review=bool(reasons),
                    review_reasons=reasons)
    return [IndicatorVerdict(indicator_id=o.key.indicator_id, run_id=run_id, cutoff_date=t.cutoff.cutoff_date,
                             judging_key=o.key.key, judge_source="bulk", judge_model=model, prompt_version=version,
                             **base) for t in o.key.tasks]


def failure_rows(o: Outcome, run_id: str) -> list[dict[str, Any]]:
    if not o.first_failures:
        return []
    resolved = {"mini": "mini-batch", "solo": "alone", "unresolved": ""}.get(o.stage, "")
    rows = [{"run_id": run_id, "judging_key": o.key.key, "term": o.key.term_id, "indicator_id": o.key.indicator_id,
             "judging_cutoff": o.key.judging.key, "stage": "first", "check": rule_of(f), "detail": f,
             "first_answer": json.dumps(o.first_answer, ensure_ascii=False) if o.first_answer else "",
             "resolved_by": resolved} for f in o.first_failures]
    if o.stage == "unresolved" and o.last_failures != o.first_failures:
        rows += [{"run_id": run_id, "judging_key": o.key.key, "term": o.key.term_id,
                  "indicator_id": o.key.indicator_id, "judging_cutoff": o.key.judging.key, "stage": "last",
                  "check": rule_of(f), "detail": f, "first_answer": "", "resolved_by": ""} for f in o.last_failures]
    return rows


def write_failures(cfg: Config, run_id: str, new: list[dict[str, Any]]) -> None:
    """The file holds the current run's rows (earlier sessions of the same run kept)."""
    path = cfg.path("judge_failures")
    keep: list[dict[str, Any]] = []
    if path.exists():
        with path.open(encoding="utf-8", newline="") as f:
            keep = [r for r in csv.DictReader(f) if r.get("run_id") == run_id]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FAILURE_COLUMNS)
        w.writeheader()
        w.writerows(keep + new)


def unresolved_keys(conn: sqlite3.Connection, run_id: str) -> set[str]:
    return {r[0] for r in conn.execute("SELECT DISTINCT judging_key FROM indicator_verdicts WHERE run_id = ? AND "
                                       "review_reasons LIKE '%\"unresolved\"%'", (run_id,))}


def first_fail_rate(calls: list[dict[str, Any]]) -> Optional[float]:
    first = [c for c in calls if c["stage"] == "first"]
    n = sum(c["n_tasks"] for c in first)
    return round(sum(c["failed"] for c in first) / n, 4) if n else None


def run_bulk(tier: str = "all", term: Optional[str] = None, limit: Optional[int] = None,
             force: bool = False) -> dict[str, Any]:
    cfg = get_config()
    j = cfg.settings.judge
    conn = db.connect()
    db.init_schema(conn)
    ctx = Context(conn, cfg)
    rmeta = latest_retrieval(cfg, complete_only=True)
    if not rmeta:
        raise RuntimeError("no complete retrieve run: run `ept retrieve run` first")
    all_terms = [t.term_id for t in cfg.settings.terms]
    terms = [term] if term else all_terms
    version = load_prompt(PROMPT, cfg).version
    flags = dirmod.load_all(cfg, all_terms)
    retrievals = load_retrievals(conn, rmeta["run_id"])
    keys = build_keys(ctx, retrievals, flags, version, terms, limit)  # raises if a flag or retrieval is missing
    try:
        full = keys if (limit is None and term is None) else build_keys(ctx, retrievals, flags, version, all_terms)
    except MissingDirectional:
        full = None  # a --limit run before the full directional pass: no tier can be complete
    fp = fingerprint(cfg, rmeta["run_id"], version, all_terms)
    run_id, resumed = start_or_resume(cfg, "bulk", fp, force,
                                      {"tier": tier, "term": term, "limit": limit, "force": force},
                                      extra={"retrieval_run": rmeta["run_id"], "tiers": {}})
    log = calls_path(cfg, run_id)
    log.parent.mkdir(parents=True, exist_ok=True)
    client = LLMClient(cfg)
    lim = Limits.from_config(cfg)
    call = Caller(client, ctx, run_id, log, lim)
    model = judge_model(cfg)
    stats: dict[str, Any] = {"run_id": run_id, "resumed": resumed, "keys_written": 0, "rows_written": 0,
                             "unresolved": 0, "llm_calls": 0, "stopped": None, "stop_for_user": None, "tiers": {}}
    fails: list[dict[str, Any]] = []
    t0 = time.monotonic()
    try:
        for tr in tier_list(tier, cfg):
            tier_keys = [k for k in keys if tr in k.tiers]
            stored = stored_keys(conn, run_id)
            todo = [k for k in tier_keys if k.key not in stored]
            n_full = len([k for k in (full or tier_keys) if tr in k.tiers])
            unresolved = len(unresolved_keys(conn, run_id) & {k.key for k in tier_keys})
            tstats = {"keys": len(tier_keys), "todo": len(todo), "written": 0, "unresolved_new": 0}
            stats["tiers"][tr] = tstats
            done = 0
            for grp in groups(todo, all_terms):
                def tick(b: list[Key], n=[0]) -> None:  # progress per first-pass call
                    n[0] += len(b)
                    progress(f"judge run: tier {tr} {b[0].term_id} {b[0].judging.label}: {done + n[0]}/{len(todo)} "
                             f"keys, {unresolved} unresolved, {client.calls} calls"
                             f"{eta(done + n[0], len(todo), time.monotonic() - t0)}")

                outcomes = judge_group(call, grp, j.bulk.tasks_per_call, j.bulk.retry_tasks_per_call, tick)
                rows = [r for o in outcomes for r in rows_for(o, run_id, model, version, cfg)]
                write_indicator_verdicts(conn, rows)
                fails += [r for o in outcomes for r in failure_rows(o, run_id)]
                new_unres = sum(o.checked is None for o in outcomes)
                unresolved += new_unres
                tstats["written"] += len(grp)
                tstats["unresolved_new"] += new_unres
                stats["keys_written"] += len(grp)
                stats["rows_written"] += len(rows)
                stats["unresolved"] += new_unres
                done += len(grp)
                progress(f"judge run: tier {tr} group {grp[0].term_id} {grp[0].judging.label} written: {len(grp)} "
                         f"keys, {new_unres} unresolved")
                if unresolved > j.max_unresolved_share * n_full:
                    raise StopForUser(f"tier {tr}: {unresolved} unresolved keys > {j.max_unresolved_share:.0%} "
                                      f"of {n_full} (spec 05 §4.15): the user decides before the run continues")
            _record_tier(cfg, conn, run_id, tr, full, unresolved)
    except QuotaExhausted as e:
        stats["stopped"] = str(e)
    except StopForUser as e:
        stats["stop_for_user"] = str(e)
    finally:
        write_failures(cfg, run_id, fails)
        stats["llm_calls"] = client.calls
        calls = read_calls(cfg, run_id)
        stats["first_fail_rate"] = first_fail_rate(calls)
        stats["smoke_stop"] = bool(limit is not None and stats["first_fail_rate"] is not None
                                   and stats["first_fail_rate"] > j.smoke_max_first_fail)
        meta = read_meta(cfg, run_id)
        tiers_meta = meta.get("tiers", {})
        complete = bool(tiers_meta) and all(tiers_meta.get(t, {}).get("complete") for t in tier_list("all", cfg))
        finish_run(run_id, counts={k: v for k, v in stats.items() if k not in ("run_id",)},
                   models={"bulk": model}, status="stopped" if stats["stopped"] or stats["stop_for_user"] else "done")
        update_meta(cfg, run_id, kind="bulk", fingerprint=fp, retrieval_run=rmeta["run_id"], tiers=tiers_meta,
                    complete=complete)
        conn.close()
    stats["complete"] = complete
    return stats


def _record_tier(cfg: Config, conn: sqlite3.Connection, run_id: str, tier: str, full: Optional[list[Key]],
                 unresolved: int) -> None:
    """A tier is complete when every key of the full (unlimited) tier plan is stored in this run."""
    meta = read_meta(cfg, run_id)
    tiers = meta.get("tiers", {})
    if full is None:
        tiers[tier] = {"complete": False, "note": "limited run"}
    else:
        tk = [k for k in full if tier in k.tiers]
        stored = stored_keys(conn, run_id)
        tiers[tier] = {"complete": all(k.key in stored for k in tk), "keys": len(tk),
                       "tasks": sum(sum(1 for t in k.tasks if tier in _task_tier(cfg, t)) for k in tk),
                       "stored": sum(k.key in stored for k in tk), "unresolved": unresolved,
                       "unresolved_share": round(unresolved / len(tk), 4) if tk else None}
    update_meta(cfg, run_id, tiers=tiers)


def _task_tier(cfg: Config, t) -> set[str]:
    from ept.judge.tasks import task_tiers

    return task_tiers(cfg, t.term_id, [t.cutoff])[t.cutoff.label]
