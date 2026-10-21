"""`ept judge report` (spec 05 §4.11): reports/judgment_05.md + .json. Aggregates only: no per-promise listing,
so no verdict of a gold promise is shown (§5).

Leakage line (must be 0): realised indicator verdicts without a citation or date chunk; cited or date chunks
outside the task's retrieval rows; dates outside the J5 window (before `sworn_in`, after the latest
`available_by` of the cited chunks, or after the cutoff); calls whose tasks span more than one term or judging
cutoff (from the run's call log; strong batches from their manifests).
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import statistics
from collections import Counter
from typing import Any, Optional
from zoneinfo import ZoneInfo

from ept import db
from ept.config import Config, get_config
from ept.dates import parse_iso, period_end, period_start
from ept.judge import directional as dirmod
from ept.judge.bulk import first_fail_rate, read_calls
from ept.judge.store import latest_run, read_meta, runs
from ept.judge.tasks import FULL, Context, load_retrievals

REALISED = ("fulfilled", "partial", "diluted")
STATUSES = ("fulfilled", "partial", "diluted", "in_progress", "not_started", "blocked_external", "unverifiable")


def _cut_key(c: Optional[str]) -> str:
    return c or FULL


def leakage(conn, cfg: Config, ctx: Context, run_ids: list[str], retrieval_run: str,
            calls: list[dict[str, Any]], batch_groups: Optional[list[list[str]]] = None) -> dict[str, Any]:
    """Counts of each leakage kind over the given judge runs (bulk/strong); every one must be 0."""
    retr = load_retrievals(conn, retrieval_run)
    out = {"realised_uncited": 0, "cited_outside_retrieval": 0, "date_outside_window": 0, "mixed_calls": 0,
           "examples": []}
    marks = ",".join("?" * len(run_ids))
    if run_ids:
        for r in conn.execute(f"SELECT * FROM indicator_verdicts WHERE run_id IN ({marks})", run_ids):
            cited = json.loads(r["cited_chunk_ids"] or "[]")
            allowed = set(retr.get((r["indicator_id"], r["cutoff_date"]), ()))
            why = []
            if r["status"] in REALISED and (not cited or not r["date_chunk_id"] or not r["realisation_date"]):
                out["realised_uncited"] += 1
                why.append("realised without citation/date chunk")
            outside = [c for c in cited + ([r["date_chunk_id"]] if r["date_chunk_id"] else []) if c not in allowed]
            if outside:
                out["cited_outside_retrieval"] += 1
                why.append(f"cites {outside[0]} outside the retrieval rows")
            if r["realisation_date"]:
                d, p = parse_iso(r["realisation_date"]), r["date_precision"]
                term = ctx.promises[r["indicator_id"].rsplit("-I", 1)[0]]["term_id"]
                sworn = ctx.sworn_in(term)
                tm = cfg.term(term)
                upper = parse_iso(r["cutoff_date"]) if r["cutoff_date"] else (parse_iso(tm.term_end) if tm.term_end
                                                                               else ctx.snapshot)
                avail = [ctx.avail[c].available_by for c in cited if c in ctx.avail and ctx.avail[c].available_by]
                if period_end(d, p) < sworn or not avail or period_start(d, p) > max(avail) or \
                        period_start(d, p) > upper:
                    out["date_outside_window"] += 1
                    why.append(f"date {r['realisation_date']} outside [{sworn}, cited availability / cutoff {upper}]")
            if why and len(out["examples"]) < 10:
                out["examples"].append({"run_id": r["run_id"], "cutoff": _cut_key(r["cutoff_date"]), "why": why})
    for c in calls:
        if len(c.get("groups", [])) > 1:
            out["mixed_calls"] += 1
    for g in batch_groups or []:
        if len(set(g)) > 1:
            out["mixed_calls"] += 1
    out["total"] = sum(out[k] for k in ("realised_uncited", "cited_outside_retrieval", "date_outside_window",
                                        "mixed_calls"))
    return out


def _dist(rows, field: str = "status") -> dict[str, int]:
    c = Counter(r[field] for r in rows)
    return {s: c.get(s, 0) for s in STATUSES}


def _quota_days(calls: list[dict[str, Any]], tz: str) -> list[str]:
    z = ZoneInfo(tz)
    return sorted({dt.datetime.fromisoformat(c["ts"]).astimezone(z).date().isoformat() for c in calls
                   if c.get("backend_calls") and "T" in c.get("ts", "") and "+" in c["ts"]})


def build(conn, cfg: Config) -> dict[str, Any]:
    ctx = Context(conn, cfg)
    bulk = latest_run(cfg, "bulk")
    if not bulk:
        raise RuntimeError("no bulk judge run yet: run `ept judge run`")
    run_id = bulk["run_id"]
    calls = read_calls(cfg, run_id)
    strong = runs(cfg, "strong")
    final = latest_run(cfg, "final")
    probe = latest_run(cfg, "probe")
    terms = [t.term_id for t in cfg.settings.terms]
    rep: dict[str, Any] = {"generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                           "bulk_run": run_id, "retrieval_run": bulk.get("retrieval_run"),
                           "tiers": bulk.get("tiers", {}), "complete": bulk.get("complete", False)}
    # per term x cutoff
    per: dict[str, Any] = {}
    for t in terms:
        for c in ctx.cutoffs(t):
            cd = c.cutoff_date.isoformat() if c.cutoff_date else None
            ind = conn.execute("SELECT iv.status, iv.review_reasons, iv.realisation_date FROM indicator_verdicts iv "
                               "JOIN indicators i ON i.indicator_id = iv.indicator_id JOIN promises p ON "
                               "p.promise_id = i.promise_id WHERE iv.run_id = ? AND p.term_id = ? AND "
                               "iv.cutoff_date IS ?", (run_id, t, cd)).fetchall()
            pv = conn.execute("SELECT v.status FROM verdicts v JOIN promises p ON p.promise_id = v.promise_id "
                              "WHERE v.run_id = ? AND p.term_id = ? AND v.cutoff_date IS ?", (run_id, t, cd)).fetchall()
            src = []
            if final:
                src = conn.execute("SELECT v.judge_source AS status FROM verdicts v JOIN promises p ON "
                                   "p.promise_id = v.promise_id WHERE v.run_id = ? AND p.term_id = ? AND "
                                   "v.cutoff_date IS ?", (final["run_id"], t, cd)).fetchall()
            n_promises = sum(1 for p in ctx.promises.values() if p["term_id"] == t)
            per[f"{t}@{c.label}"] = {
                "cutoff": c.key, "indicator_verdicts": len(ind), "indicator_status": _dist(ind),
                "promise_verdicts": len(pv), "promises_in_term": n_promises, "promise_status": _dist(pv),
                "realised_share": round(sum(r["status"] in REALISED for r in pv) / len(pv), 4) if pv else None,
                "judge_source": dict(Counter(r["status"] for r in src)) if src else {},
            }
    rep["per_term_cutoff"] = per
    # checks and review reasons
    first = [c for c in calls if c["stage"] == "first"]
    mini = [c for c in calls if c["stage"] == "mini"]
    n_first = sum(c["n_tasks"] for c in first)
    unres = conn.execute("SELECT count(DISTINCT judging_key) FROM indicator_verdicts WHERE run_id = ? AND "
                         "review_reasons LIKE '%\"unresolved\"%'", (run_id,)).fetchone()[0]
    keys = conn.execute("SELECT count(DISTINCT judging_key) FROM indicator_verdicts WHERE run_id = ?",
                        (run_id,)).fetchone()[0]
    reasons: Counter = Counter()
    for r in conn.execute("SELECT judging_key, review_reasons FROM indicator_verdicts WHERE run_id = ? "
                          "GROUP BY judging_key", (run_id,)):
        reasons.update(json.loads(r["review_reasons"] or "[]"))
    by_check: Counter = Counter()
    fpath = cfg.path("judge_failures")
    if fpath.exists():
        with fpath.open(encoding="utf-8", newline="") as f:
            by_check.update(r["check"] for r in csv.DictReader(f) if r["run_id"] == run_id and r["stage"] == "first")
    rep["checks"] = {"keys_judged": keys, "first_pass_tasks": n_first,
                     "first_answer_fail_rate": first_fail_rate(calls),
                     "fail_rate_after_mini": round(sum(c["failed"] for c in mini) / n_first, 4) if n_first else None,
                     "unresolved": unres, "unresolved_share": round(unres / keys, 4) if keys else None,
                     "first_failures_by_check": dict(sorted(by_check.items())),
                     "review_reasons_per_key": dict(sorted(reasons.items()))}
    flags = {t: dirmod.read_flags(cfg, t) for t in terms}
    rep["directional"] = {t: {"promises": len(f), "directional": sum(r["directional"] for r in f.values()),
                              "d3_override": sum(r.get("flag") == "d3_override" for r in f.values()),
                              "unresolved": sum(r.get("flag") == "unresolved" for r in f.values())}
                          for t, f in flags.items()}
    dtypes = Counter(r[0] for r in conn.execute(
        "SELECT d.doc_type FROM indicator_verdicts iv JOIN chunks c ON c.chunk_id = iv.date_chunk_id JOIN documents d "
        "ON d.doc_id = c.doc_id WHERE iv.run_id = ? AND iv.date_chunk_id IS NOT NULL GROUP BY iv.judging_key",
        (run_id,)))
    rep["date_chunk_doc_types"] = dict(dtypes.most_common())
    # non-monotone (raw bulk promise verdicts) and the final run
    nm = 0
    for t in terms:
        order = [c.cutoff_date.isoformat() if c.cutoff_date else None for c in ctx.cutoffs(t)]
        seq: dict[str, dict[Optional[str], bool]] = {}
        for r in conn.execute("SELECT v.promise_id, v.cutoff_date, v.realisation_date FROM verdicts v JOIN promises p "
                              "ON p.promise_id = v.promise_id WHERE v.run_id = ? AND p.term_id = ?", (run_id, t)):
            seq.setdefault(r["promise_id"], {})[r["cutoff_date"]] = r["realisation_date"] is not None
        for pid, m in seq.items():
            seen = False
            for c in order:
                if c not in m:
                    continue
                if m[c]:
                    seen = True
                elif seen:
                    nm += 1
                    break
    rep["non_monotone_promises_bulk"] = nm
    rep["final"] = (read_meta(cfg, final["run_id"]).get("counts", {}) | {"run_id": final["run_id"]}) if final else None
    rep["probe"] = (read_meta(cfg, probe["run_id"]).get("counts", {}) | {"run_id": probe["run_id"]}) if probe else None
    # calls and tokens
    live = [c for c in calls if c.get("backend_calls")]
    est = [c["est_tokens"] for c in live if c.get("est_tokens")]
    meas = [c["prompt_tokens"] for c in live if c.get("prompt_tokens")]
    rep["usage"] = {"calls_logged": len(calls), "backend_calls": sum(c.get("backend_calls", 0) for c in calls),
                    "cache_hits": sum(bool(c.get("cache_hit")) for c in calls),
                    "est_tokens_total": sum(est), "prompt_tokens_total": sum(meas),
                    "output_tokens_total": sum(c.get("output_tokens", 0) for c in live),
                    "prompt_tokens_per_first_call_median": statistics.median(
                        [c["prompt_tokens"] for c in live if c["stage"] == "first" and c.get("prompt_tokens")] or [0]),
                    "est_tokens_per_first_call_max": max([c["est_tokens"] for c in live if c["stage"] == "first"] or [0]),
                    "tpm_limit": cfg.settings.llm.bulk.tpm,
                    "quota_days": _quota_days(calls, cfg.settings.llm.bulk.quota_tz)}
    # strong coverage
    strong_cov = {}
    batch_groups = []
    for m in strong:
        strong_cov[m["run_id"]] = m.get("coverage", {})
        batch_groups += [b.get("groups", []) for b in m.get("batches", [])]
    rep["strong"] = strong_cov
    run_ids = [run_id] + [m["run_id"] for m in strong]
    rep["leakage"] = leakage(conn, cfg, ctx, run_ids, bulk.get("retrieval_run"), calls, batch_groups)
    # neutrality: one prompt version, model and config for every term
    pv_by_term = {}
    for t in terms:
        rows = conn.execute("SELECT DISTINCT iv.prompt_version, iv.judge_model FROM indicator_verdicts iv JOIN indicators i "
                            "ON i.indicator_id = iv.indicator_id JOIN promises p ON p.promise_id = i.promise_id WHERE "
                            "iv.run_id = ? AND p.term_id = ?", (run_id, t)).fetchall()
        pv_by_term[t] = sorted({f"{r[0]}|{r[1]}" for r in rows})
    distinct = {x for v in pv_by_term.values() for x in v}
    rep["neutrality"] = {"by_term": pv_by_term, "same_for_every_term": len(distinct) <= 1,
                         "config": "one judge config and check set (fingerprint " +
                                   bulk.get("fingerprint", {}).get("hash", "")[:12] + ")"}
    return rep


def to_md(rep: dict[str, Any]) -> str:
    L = ["# Stage 05 — Judgment report", "",
         f"Generated {rep['generated_at']} · bulk run `{rep['bulk_run']}` · retrieval run `{rep['retrieval_run']}` · "
         f"complete: {rep['complete']}", "",
         "Aggregates only: no per-promise verdicts are listed (gold labelling is blind, spec 05 §5).", ""]
    lk = rep["leakage"]
    L += ["## Leakage line", "",
          f"**{lk['total']}** — realised without citation {lk['realised_uncited']}, cited outside retrieval "
          f"{lk['cited_outside_retrieval']}, dates outside the J5 window {lk['date_outside_window']}, calls mixing "
          f"terms or judging cutoffs {lk['mixed_calls']}.", ""]
    nt = rep["neutrality"]
    L += ["## Neutrality line", "", f"Same prompt version and model for every term: **{nt['same_for_every_term']}** "
          f"({'; '.join(f'{t}: {v}' for t, v in nt['by_term'].items())}). {nt['config']}.", ""]
    L += ["## Tiers", ""] + [f"- {t}: {json.dumps(v)}" for t, v in rep["tiers"].items()] + [""]
    L += ["## Promise status per term × cutoff (bulk)", "",
          "| term@cutoff | promises | " + " | ".join(STATUSES) + " | realised share | judge source (final) |",
          "|---|---|" + "---|" * len(STATUSES) + "---|---|"]
    for k, v in rep["per_term_cutoff"].items():
        L.append(f"| {k} | {v['promise_verdicts']}/{v['promises_in_term']} | " +
                 " | ".join(str(v["promise_status"][s]) for s in STATUSES) +
                 f" | {v['realised_share']} | {v['judge_source'] or '–'} |")
    L += ["", "## Indicator status per term × cutoff (bulk)", "",
          "| term@cutoff | indicator verdicts | " + " | ".join(STATUSES) + " |", "|---|---|" + "---|" * len(STATUSES)]
    for k, v in rep["per_term_cutoff"].items():
        L.append(f"| {k} | {v['indicator_verdicts']} | " + " | ".join(str(v["indicator_status"][s]) for s in STATUSES)
                 + " |")
    c = rep["checks"]
    L += ["", "## Checks", "",
          f"- Judging keys: {c['keys_judged']}; first-pass tasks {c['first_pass_tasks']}",
          f"- First-answer failure rate {c['first_answer_fail_rate']}; after mini-batches {c['fail_rate_after_mini']}; "
          f"unresolved {c['unresolved']} ({c['unresolved_share']})",
          f"- First failures by check: {c['first_failures_by_check']}",
          f"- Review reasons (per key): {c['review_reasons_per_key']}",
          f"- Directional: {rep['directional']}",
          f"- Date chunks by doc_type (per key): {rep['date_chunk_doc_types']}",
          f"- Non-monotone promises (raw bulk): {rep['non_monotone_promises_bulk']}",
          f"- Final run: {rep['final']}", f"- Memory probe: {rep['probe']}", "", "## Usage", ""]
    L += [f"- {k}: {v}" for k, v in rep["usage"].items()]
    L += ["", "## Strong judge", "", f"{rep['strong'] or 'no strong batches yet'}", ""]
    return "\n".join(L)


def run_report() -> dict[str, Any]:
    cfg = get_config()
    conn = db.connect()
    db.init_schema(conn)
    rep = build(conn, cfg)
    conn.close()
    cfg.path("judgment_json").parent.mkdir(parents=True, exist_ok=True)
    cfg.path("judgment_json").write_text(json.dumps(rep, indent=1, default=str), encoding="utf-8")
    cfg.path("judgment_md").write_text(to_md(rep), encoding="utf-8")
    return {"leakage": rep["leakage"]["total"], "neutral": rep["neutrality"]["same_for_every_term"],
            "first_answer_fail_rate": rep["checks"]["first_answer_fail_rate"],
            "unresolved": rep["checks"]["unresolved"], "path": str(cfg.path("judgment_md"))}
