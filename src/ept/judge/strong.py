"""Strong judge (spec 05 §4.9, D-086; global §6.2–§6.3): a priority queue judged by fresh Claude Code subagents.

Queue units are promise × cutoff with all their indicators, in priority order (deterministic within a level by
sha256(`promise_id@cutoff`)):
  P1 gold (IDs from gold_sample.csv only) and P2 headline, at full term (completed terms) or the current
  landmark (ongoing term); P3 the remaining promises of the ongoing term at its landmark; P4 bulk-flagged
  (`needs_review`) promises at full term; P5 flagged at the backtest term's landmarks; P6 flagged at the training
  term's landmarks. (Terms are picked by their §7 `role`, not by name.)

Batches (`judge.strong.tasks_per_batch`): one term and one cutoff per batch, a unit is never split, and a key is
judged once and reused only for units at the same or a later cutoff (so no judgment was made beside chunks dated
after a cutoff it is stored for). Files: data/judgments/{run_id}/in/batch_NNN.jsonl (tasks as rendered, aliases
only), …/out/batch_NNN.jsonl, …/manifest.json. A batch with failing tasks is re-run once with only those tasks
(`batch_NNN_r`); tasks still failing keep their bulk verdict (`strong_failed`).
"""

from __future__ import annotations

import hashlib
import json
import shutil
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from pydantic import ValidationError

from ept import db
from ept.config import Config, get_config
from ept.judge import directional as dirmod
from ept.judge.bulk import Caller
from ept.judge.checks import Limits, TaskInput, check_task, feedback, match_answers
from ept.judge.prompt import PROMPT, TaskVerdictOut, extract_alias, render_task, task_alias
from ept.judge.store import (code_hash, file_sha, fp_hash, latest_run, read_meta, start_or_resume, update_meta,
                             write_indicator_verdicts, verdict_rows)
from ept.judge.tasks import FULL, Context, Key, build_keys, cutoff_order, gold_promise_ids, load_retrievals
from ept.llm import load_prompt
from ept.retrieve import eligible as el
from ept.retrieve.run import latest_run as latest_retrieval
from ept.schema import IndicatorVerdict

FORBIDDEN_IN_PATHS_NOTE = "scratch paths carry no party or term name (D-057)"


@dataclass
class Unit:
    promise_id: str
    term_id: str
    cutoff: el.Cutoff
    level: str
    keys: list[Key]

    @property
    def uid(self) -> str:
        return f"{self.promise_id}@{self.cutoff.key}"


def _h(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def queue(ctx: Context, cfg: Config, keys: list[Key], bulk_run: Optional[str], gold: set[str]) -> list[Unit]:
    by_task: dict[tuple[str, str], Key] = {}
    for k in keys:
        for t in k.tasks:
            by_task[(t.indicator_id, t.cutoff.key)] = k
    terms = {t.term_id: t for t in cfg.settings.terms}
    flagged: set[tuple[str, str]] = set()
    if bulk_run:
        flagged = {(v.promise_id, v.cutoff_date.isoformat() if v.cutoff_date else FULL)
                   for v in verdict_rows(ctx.conn, bulk_run) if v.needs_review}

    def headline_cut(term_id: str) -> el.Cutoff:
        cuts = ctx.cutoffs(term_id)
        full = [c for c in cuts if c.label == FULL]
        return full[0] if full else cuts[-1]

    out: list[Unit] = []
    seen: set[str] = set()

    def level(name: str, cands: list[tuple[str, el.Cutoff]]) -> None:
        for pid, c in sorted(cands, key=lambda x: _h(f"{x[0]}@{x[1].key}")):
            uid = f"{pid}@{c.key}"
            if uid in seen or pid not in ctx.by_promise:
                continue
            ks = [by_task.get((iid, c.key)) for iid in ctx.by_promise[pid]]
            if any(k is None for k in ks):
                continue
            seen.add(uid)
            out.append(Unit(pid, ctx.promises[pid]["term_id"], c, name, ks))  # type: ignore[arg-type]

    promises = ctx.promises
    level("gold", [(pid, headline_cut(promises[pid]["term_id"])) for pid in gold if pid in promises])
    level("headline", [(pid, headline_cut(p["term_id"])) for pid, p in promises.items() if p["headline"]])
    level("tvk_current", [(pid, headline_cut(p["term_id"])) for pid, p in promises.items()
                          if terms[p["term_id"]].role == "project"])
    # D-096: tier B (the training term's landmarks) is judged by Claude subagents instead of the bulk model
    level("tier_b", [(pid, c) for pid, p in promises.items() if terms[p["term_id"]].role == "train"
                     for c in ctx.cutoffs(p["term_id"]) if c.label != FULL])
    # D-120: the Claude-only regime. Every completed-term promise at full term, then AIADMK's early landmarks
    # (the reverse backtest's states); units already judged by Claude are skipped as already exported.
    completed = [(pid, p) for pid, p in promises.items() if terms[p["term_id"]].role in ("train", "backtest")]
    # D-122: full-term units still lacking a strong verdict for some indicator (keys that were only "reused" from batches
    # that were exported but never run). Defined before claude_full so these units take this label.
    have_full = {r[0] for r in ctx.conn.execute(
        "select indicator_id from indicator_verdicts where judge_source = 'strong' and cutoff_date is null")}
    level("claude_full_gap", [(pid, c) for pid, p in completed for c in ctx.cutoffs(p["term_id"]) if c.label == FULL
                              and any(i not in have_full for i in ctx.by_promise.get(pid, []))])
    level("claude_full", [(pid, c) for pid, p in completed for c in ctx.cutoffs(p["term_id"]) if c.label == FULL])
    for lab in ("m5", "m6", "m12"):
        level(f"claude_aiadmk_{lab}", [(pid, c) for pid, p in completed if terms[p["term_id"]].role == "backtest"
                                       for c in ctx.cutoffs(p["term_id"]) if c.label == lab])
    level("claude_dmk_m12", [(pid, c) for pid, p in completed if terms[p["term_id"]].role == "train"
                             for c in ctx.cutoffs(p["term_id"]) if c.label == "m12"])
    level("flagged_full", [(pid, c) for pid, p in promises.items() for c in ctx.cutoffs(p["term_id"])
                           if c.label == FULL and (pid, FULL) in flagged])
    for name, role in (("flagged_aiadmk_landmarks", "backtest"), ("flagged_dmk_landmarks", "train")):
        level(name, [(pid, c) for pid, p in promises.items() if terms[p["term_id"]].role == role
                     for c in ctx.cutoffs(p["term_id"]) if c.label != FULL and (pid, c.key) in flagged])
    return out


def make_batches(units: list[Unit], size: int, done: dict[str, tuple[str, list]]) -> list[dict[str, Any]]:
    """Batches of whole units, one (term, cutoff) per batch. `done` = {key: (term, [cutoff order])} of keys
    already exported; a key is reused only for a unit at the same or a later cutoff of its judging batch."""
    open_: dict[tuple[str, str], dict[str, Any]] = {}
    closed: list[dict[str, Any]] = []
    for u in units:
        g = (u.term_id, u.cutoff.key)
        new, reuse = [], []
        for k in u.keys:
            prev = done.get(k.key)
            if prev and prev[0] == u.term_id and tuple(prev[1]) <= tuple(_order(u.cutoff)):
                reuse.append(k)
            else:
                new.append(k)
        b = open_.get(g)
        if b is not None and len(b["keys"]) + len(new) > size:
            closed.append(b)
            b = None
        if b is None:
            b = open_[g] = {"group": f"{u.term_id}@{u.cutoff.key}", "term": u.term_id, "cutoff": u.cutoff.key,
                            "levels": [], "units": [], "keys": [], "reused": []}
        b["units"].append(u.uid)
        if u.level not in b["levels"]:
            b["levels"].append(u.level)
        for k in new:
            if all(x.key != k.key for x in b["keys"]):
                b["keys"].append(k)
            done[k.key] = (u.term_id, list(_order(u.cutoff)))
        b["reused"] += [{"key": k.key, "indicator_id": k.indicator_id, "cutoff": u.cutoff.key} for k in reuse]
        if len(b["keys"]) >= size:
            closed.append(open_.pop(g))
    closed += list(open_.values())
    return closed


def _order(c: el.Cutoff) -> tuple:
    d, full = cutoff_order(c)
    return (d.isoformat(), full)


# --- files ------------------------------------------------------------------------------------------


def run_dir(cfg: Config, run_id: str) -> Path:
    return cfg.path("judgments") / run_id


def manifest_path(cfg: Config, run_id: str) -> Path:
    return run_dir(cfg, run_id) / "manifest.json"


def read_manifest(cfg: Config, run_id: str) -> dict[str, Any]:
    p = manifest_path(cfg, run_id)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"run_id": run_id, "batches": []}


def write_manifest(cfg: Config, run_id: str, m: dict[str, Any]) -> None:
    p = manifest_path(cfg, run_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(m, indent=1, ensure_ascii=False), encoding="utf-8")


def batch_name(n: int, retry: bool = False) -> str:
    return f"batch_{n:03d}" + ("_r" if retry else "")


def _keys_index(ctx: Context, cfg: Config, retrieval_run: str) -> tuple[list[Key], str]:
    terms = [t.term_id for t in cfg.settings.terms]
    version = load_prompt(PROMPT, cfg).version
    keys = build_keys(ctx, load_retrievals(ctx.conn, retrieval_run), dirmod.load_all(cfg, terms), version, terms)
    return keys, version


def _write_batch(path: Path, call: Caller, keys: list[Key], notes: Optional[dict[str, list[str]]] = None) -> None:
    items, _ = call.inputs(keys, True, notes)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(i, ensure_ascii=False) + "\n" for i in items), encoding="utf-8")


STRONG_CODE = ["dates.py", "judge/tasks.py", "judge/prompt.py", "judge/checks.py", "judge/strong.py"]
NEEDS_BULK = {"flagged_full", "flagged_aiadmk_landmarks", "flagged_dmk_landmarks"}


def strong_fingerprint(cfg: Config, retrieval_run: str, version: str) -> dict[str, Any]:
    terms = [t.term_id for t in cfg.settings.terms]
    return fp_hash({"prompt_version": version, "retrieval_run": retrieval_run,
                    "directional": {t: file_sha(dirmod.path_for(cfg, t)) for t in terms},
                    "strong": cfg.settings.judge.strong.model_dump(mode="json"), "code": code_hash(STRONG_CODE)})


def run_export(levels: Optional[list[str]] = None, run_id: Optional[str] = None,
               retry: Optional[int] = None) -> dict[str, Any]:
    """Export the next batches of the queue for `levels` (default: gold and headline), or (`retry` = N) a retry
    batch of batch N's failing tasks."""
    cfg = get_config()
    conn = db.connect()
    db.init_schema(conn)
    ctx = Context(conn, cfg)
    want = set(levels or ["gold", "headline"])
    bulk = latest_run(cfg, "bulk", tier="A")
    if want & NEEDS_BULK and not bulk:
        raise RuntimeError("the flagged levels wait for a bulk run with tier A complete")
    rmeta = latest_retrieval(cfg, complete_only=True)
    retrieval_run = bulk["retrieval_run"] if bulk else rmeta["run_id"]
    keys, version = _keys_index(ctx, cfg, retrieval_run)
    fp = strong_fingerprint(cfg, retrieval_run, version)
    if run_id is None:
        run_id, _ = start_or_resume(cfg, "strong", fp, False, {"levels": levels},
                                    extra={"retrieval_run": retrieval_run, "bulk_run": bulk["run_id"] if bulk else None})
    elif read_meta(cfg, run_id).get("fingerprint", {}).get("hash") != fp["hash"]:
        raise RuntimeError(f"{run_id}: inputs changed since it was started (prompt, directional flags or code)")
    m = read_manifest(cfg, run_id)
    call = Caller(None, ctx, run_id, Path("/dev/null"), Limits.from_config(cfg), call_kind="strong")  # type: ignore[arg-type]
    key_by = {k.key: k for k in keys}
    if retry is not None:
        b = next(x for x in m["batches"] if x["n"] == retry and not x.get("retry_of"))
        failed = b.get("failed") or {}
        if not failed:
            conn.close()
            return {"run_id": run_id, "retry_of": retry, "tasks": 0}
        tasks = [t for t in b["tasks"] if t["alias"] in failed]
        rk = [key_by[t["key"]] for t in tasks]
        name = batch_name(retry, True)
        _write_batch(run_dir(cfg, run_id) / "in" / f"{name}.jsonl", call, rk,
                     {t["key"]: failed[t["alias"]] for t in tasks})
        m["batches"].append({"n": retry, "retry_of": retry, "name": name, "group": b["group"], "levels": b["levels"],
                             "units": b["units"], "tasks": [dict(t, alias=task_alias(i)) for i, t in enumerate(tasks, 1)],
                             "reused": [], "status": "exported"})
        write_manifest(cfg, run_id, m)
        conn.close()
        return {"run_id": run_id, "retry_of": retry, "batch": name, "tasks": len(tasks)}
    levels = levels or ["gold", "headline"]
    unknown = set(levels) - set(cfg.settings.judge.strong.priorities)
    if unknown:
        raise ValueError(f"unknown level(s) {sorted(unknown)}; levels: {cfg.settings.judge.strong.priorities}")
    exported_units = {u for b in m["batches"] if not b.get("retry_of") for u in b["units"]}
    gap_level = "claude_full_gap"
    bulk_id = bulk["run_id"] if bulk else None
    units = [u for u in queue(ctx, cfg, keys, bulk_id, gold_promise_ids(cfg))
             if u.level in levels and (u.uid not in exported_units or u.level == gap_level)]
    # within a level, earlier cutoffs first, so a chunk list shared by later landmarks is judged once (reuse)
    units.sort(key=lambda u: (levels.index(u.level), _order(u.cutoff)))
    # D-122: a key counts as done (reusable) only if its batch was actually imported, never merely exported
    done = {t["key"]: (b["term"], b["order"]) for b in m["batches"]
            if not b.get("retry_of") and str(b.get("status", "")).startswith("imported") for t in b["tasks"]}
    new = make_batches(units, cfg.settings.judge.strong.tasks_per_batch, done)
    n0 = max([b["n"] for b in m["batches"]] or [0])
    unit_cut = {u.uid: u.cutoff for u in units}
    for i, b in enumerate(new, start=n0 + 1):
        name = batch_name(i)
        cut = unit_cut[b["units"][0]]
        _write_batch(run_dir(cfg, run_id) / "in" / f"{name}.jsonl", call, b["keys"])
        m["batches"].append({
            "n": i, "name": name, "group": b["group"], "term": b["term"], "cutoff": b["cutoff"],
            "order": list(_order(cut)), "levels": b["levels"], "units": b["units"],
            "tasks": [{"alias": task_alias(j), "key": k.key, "indicator_id": k.indicator_id} for j, k in
                      enumerate(b["keys"], 1)],
            "reused": b["reused"], "status": "exported"})
    m["levels"] = _coverage(m, queue(ctx, cfg, keys, bulk_id, gold_promise_ids(cfg)))
    write_manifest(cfg, run_id, m)
    update_meta(cfg, run_id, coverage=m["levels"], batches=[{"name": b["name"], "groups": [b["group"]]}
                                                            for b in m["batches"]])
    conn.close()
    return {"run_id": run_id, "new_batches": [batch_name(b) for b in range(n0 + 1, n0 + 1 + len(new))],
            "units": len(units), "tasks": sum(len(b["keys"]) for b in new)}


def _coverage(m: dict[str, Any], q: list[Unit]) -> dict[str, Any]:
    imported = {u for b in m["batches"] if b.get("status", "").startswith("imported") for u in b.get("complete_units", [])}
    exported = {u for b in m["batches"] for u in b["units"]}
    out: dict[str, Any] = {}
    for u in q:
        d = out.setdefault(u.level, {"units": 0, "exported": 0, "judged": 0, "tasks": 0})
        d["units"] += 1
        d["tasks"] += len(u.keys)
        d["exported"] += u.uid in exported
        d["judged"] += u.uid in imported
    return out


def scratch_dirs(base: Path, run_id: str, name: str) -> tuple[Path, Path]:
    """A neutral scratch folder per batch: {base}/sj-{run stamp}-{name}/{in,out}. No party or term name."""
    stamp = run_id.split("-", 1)[1]
    root = Path(base) / f"sj-{stamp}-{name}"
    return root / "in", root / "out"


def stage(run_id: str, name: str, base: Path) -> dict[str, str]:
    """Copy the prompt and one batch into a neutral scratch folder for a fresh subagent."""
    cfg = get_config()
    src = run_dir(cfg, run_id) / "in" / f"{name}.jsonl"
    if not src.exists():
        raise FileNotFoundError(src)
    in_dir, out_dir = scratch_dirs(base, run_id, name)
    shutil.rmtree(in_dir.parent, ignore_errors=True)
    in_dir.mkdir(parents=True)
    out_dir.mkdir(parents=True)
    shutil.copy(cfg.path("prompts") / f"{PROMPT}.md", in_dir / "instructions.md")
    tasks = [json.loads(x) for x in src.read_text(encoding="utf-8").splitlines() if x.strip()]
    (in_dir / "batch.md").write_text(batch_markdown(tasks), encoding="utf-8")
    return {"prompt": str(in_dir / "instructions.md"), "batch": str(in_dir / "batch.md"),
            "output": str(out_dir / "verdicts.jsonl"), "tasks": str(len(tasks))}


SUBAGENT_BRIEF = """You are an isolated judge. Read exactly these two files and nothing else:
1. {prompt} (your instructions)
2. {batch} (the tasks: each "## Task Txx" section is one task with its extracts; it takes the place of the Tasks section of the instructions)

The batch file is long: read it in consecutive parts (with offset and limit) until you have read every task.

Rules: do not read any other file, do not list or search folders, do not search the web, do not run shell commands. Judge only from the extracts in the batch, never from what you know about Tamil Nadu, its governments or its schemes. Follow the instructions exactly; in particular, each quote is one continuous passage copied character for character from the extract it is cited for, and a date comes only from its cited date extract.

Write exactly one file: {output}
It holds one JSON object per line, one line per task, in batch order, each with the keys task, status, realisation_date, date_extract, cited, rationale, confidence, and nothing else (no code fences, no commentary). Then reply with only: done <number of lines written>."""


def brief(paths: dict[str, str]) -> str:
    """The message a fresh subagent gets for one staged batch (D-057, D-086)."""
    return SUBAGENT_BRIEF.format(**paths)


def _wrap(text: str, width: int = 150) -> str:
    return textwrap.fill(" ".join(str(text).split()), width=width, break_long_words=False, break_on_hyphens=False)


def batch_markdown(tasks: list[dict[str, Any]]) -> str:
    """The batch as the subagent reads it: the same fields as the .jsonl tasks, with long text wrapped (file-reading
    tools truncate very long lines). The checks collapse whitespace, so wrapping can't change a quote's match."""
    L = [f"# Batch of {len(tasks)} tasks", "",
         "Each `## Task` section is one task with the fields described in the instructions. Long text is wrapped "
         "at spaces: treat a line break inside a field as a space.", ""]
    for t in tasks:
        L += [f"## Task {t['task']}", "", "promise:", _wrap(t["promise"]), ""]
        if t.get("indicator"):
            L += ["indicator:", _wrap(t["indicator"]), ""]
        L += [f"directional: {t['directional']}", "", f"context: {t['context']}", ""]
        if t.get("note"):
            L += [f"note: {t['note']}", ""]
        if t.get("previous_answer_failed"):
            L += ["previous_answer_failed:"] + [f"- {x}" for x in t["previous_answer_failed"]] + [""]
        for e in t["extracts"]:
            L += [f"### Extract {e['extract']} (of task {t['task']})", "", "title:", _wrap(e["title"]), "",
                  f"doc_type: {e['doc_type']}", "", f"date: {e['date']}", "", "text:", _wrap(e["text"]), ""]
    return "\n".join(L) + "\n"


def _parse_out(path: Path) -> tuple[list[TaskVerdictOut], list[str]]:
    answers, bad = [], []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            answers.append(TaskVerdictOut.model_validate(json.loads(line)))
        except (json.JSONDecodeError, ValidationError) as e:
            bad.append(f"line {n}: {str(e)[:120]}")
    return answers, bad


def run_import(run_id: str, batches: Optional[list[int]] = None, model: Optional[str] = None,
               from_dir: Optional[Path] = None, tokens: Optional[int] = None) -> dict[str, Any]:
    """Validate out/batch files with J1–J7 against the real chunks and load the passing tasks."""
    cfg = get_config()
    conn = db.connect()
    db.init_schema(conn)
    ctx = Context(conn, cfg)
    m = read_manifest(cfg, run_id)
    meta = read_meta(cfg, run_id)
    keys, version = _keys_index(ctx, cfg, meta["retrieval_run"])
    key_by = {k.key: k for k in keys}
    lim = Limits.from_config(cfg)
    stats: dict[str, Any] = {"run_id": run_id, "imported": [], "rows": 0, "failed_tasks": 0}
    for b in m["batches"]:
        if batches and b["n"] not in batches:
            continue
        if b.get("status", "").startswith("imported"):
            continue
        out = run_dir(cfg, run_id) / "out" / f"{b['name']}.jsonl"
        if from_dir is not None:
            src = Path(from_dir) / "verdicts.jsonl"
            if src.exists():
                out.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(src, out)
        if not out.exists():
            continue
        answers, bad = _parse_out(out)
        aliases = [t["alias"] for t in b["tasks"]]
        matched, j1, _ = match_answers(aliases, answers)
        rows, failed = [], {}
        unit_cuts = {u.split("@", 1)[1] for u in b["units"]}
        cut_of = {c.key: c for t in cfg.settings.terms for c in ctx.cutoffs(t.term_id)}
        for t in b["tasks"]:
            k = key_by[t["key"]]
            if t["alias"] in j1:
                failed[t["alias"]] = [j1[t["alias"]]] + [f"J1: {x}" for x in bad[:2]]
                continue
            chunks = ctx.chunks(k.chunk_ids)
            ti = TaskInput(t["alias"], {extract_alias(j): chunks[c] for j, c in enumerate(k.chunk_ids, 1)},
                           ctx.sworn_in(k.term_id), k.directional)
            chk = check_task(matched[t["alias"]], ti, lim)
            if chk.failures:
                failed[t["alias"]] = chk.failures
                continue
            reasons = list(chk.reasons) + (["retried"] if b.get("retry_of") else [])
            if chk.confidence < cfg.settings.judge.review_confidence:
                reasons.insert(0, "low_confidence")
            # stored for this batch's unit cutoffs and for later units that reuse the key
            cuts = sorted(unit_cuts | {r["cutoff"] for x in m["batches"] for r in x.get("reused", [])
                                       if r["key"] == k.key})
            for ck in cuts:
                if (k.indicator_id, ck) not in {(tt.indicator_id, tt.cutoff.key) for tt in k.tasks}:
                    continue
                rows.append(IndicatorVerdict(
                    indicator_id=k.indicator_id, run_id=run_id, cutoff_date=cut_of[f"{ck}"].cutoff_date
                    if ck != FULL else None, judging_key=k.key, status=chk.status,
                    realisation_date=chk.realisation_date, date_precision=chk.date_precision,
                    date_chunk_id=chk.date_chunk_id, cited_chunk_ids=chk.cited_chunk_ids, quotes=chk.quotes,
                    rationale=chk.rationale, confidence=chk.confidence, needs_review=bool(reasons),
                    review_reasons=reasons, judge_source="strong",
                    judge_model=f"claude-subagent:{model or b.get('model') or 'unknown'}", prompt_version=version))
        write_indicator_verdicts(conn, rows)
        b["status"] = "imported" if not failed else "imported_with_failures"
        b["failed"] = {a: feedback(f) for a, f in failed.items()} if not b.get("retry_of") else {}
        if b.get("retry_of"):
            b["strong_failed"] = sorted(failed)
        b["model"] = model or b.get("model")
        if tokens is not None:
            b["tokens"] = tokens
        b["complete_units"] = _complete_units(conn, run_id, b, ctx)
        stats["imported"].append(b["name"])
        stats["rows"] += len(rows)
        stats["failed_tasks"] += len(failed)
    m["levels"] = _coverage(m, queue(ctx, cfg, keys, meta.get("bulk_run"), gold_promise_ids(cfg)))
    write_manifest(cfg, run_id, m)
    update_meta(cfg, run_id, coverage=m["levels"],
                batches=[{"name": b["name"], "groups": [b["group"]], "tokens": b.get("tokens"),
                          "model": b.get("model"), "status": b.get("status")} for b in m["batches"]])
    conn.close()
    return stats


def _complete_units(conn, run_id: str, b: dict[str, Any], ctx: Context) -> list[str]:
    out = []
    for uid in b["units"]:
        pid, ck = uid.split("@", 1)
        cd = None if ck == FULL else ck
        n = conn.execute("SELECT count(*) FROM indicator_verdicts WHERE run_id = ? AND cutoff_date IS ? AND "
                         "indicator_id LIKE ?", (run_id, cd, f"{pid}-I%")).fetchone()[0]
        if n == len(ctx.by_promise.get(pid, [])):
            out.append(uid)
    return out
