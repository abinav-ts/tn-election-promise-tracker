"""`ept judge spotcheck` (spec 05 §4.12, D-093, global §12.4): the stage's one human check, drawn from the tier A
bulk run before any strong batch. Gold promises are excluded from the sheet and its pages (labelling stays blind).

Problem groups, in priority order:
  a. unresolved tasks;
  b. realised verdicts whose date chunk is a budget speech, policy note or Governor's address (the announcement
     rule), lowest confidence first;
  c. non-monotone promises (realised at a cutoff, not at a later one);
  d. realised headline promises, lowest confidence;
  e. a realisation date within `near_days` of `sworn_in` or of the cutoff;
  f. fill: `not_started` at full term on headline promises, lowest top-1 retrieval cosine.
At most `per_term` per term and `per_group` per group, one item per promise, terms take turns within a group
(the stage 04 selection). A sheet that already holds verdicts is archived, never overwritten (D-073).
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from ept import db
from ept.config import Config, get_config
from ept.dates import parse_iso
from ept.judge.prompt import date_label
from ept.judge.store import indicator_rows, latest_run, verdict_rows
from ept.judge.tasks import FULL, Context, gold_promise_ids, load_retrievals, task_tiers
from ept.retrieve.run import read_diag
from ept.retrieve.spotcheck import _archive_if_reviewed, select, snippet
from ept.retrieve.tokenize import tokenize

COLUMNS = ["item_id", "term", "group", "why_flagged", "what_to_check", "open", "verdict", "note"]
QUESTION = ("Given only these extracts, are the status and the date right? ok = yes; wrong = the status or the date "
            "is not supported by the extracts (say which in the note); unsure = can't tell.")
ANNOUNCEMENT_TYPES = ("budget_speech", "policy_note", "governor_address")
REALISED = ("fulfilled", "partial", "diluted")


@dataclass
class Item:
    promise_id: str
    term: str
    cutoff: str  # cutoff date or "full"
    group: str
    key: tuple
    why: str
    indicator_ids: list[str] = field(default_factory=list)  # empty = every indicator of the promise

    @property
    def item_id(self) -> str:
        return f"{self.promise_id}@{self.cutoff}"


def _ck(cut: Optional[dt.date]) -> str:
    return cut.isoformat() if cut else FULL


def build(ctx: Context, cfg: Config, run_id: str, gold: set[str], diag: dict) -> list[Item]:
    j = cfg.settings.judge.spotcheck
    rows = [r for r in indicator_rows(ctx.conn, run_id) if r.indicator_id.rsplit("-I", 1)[0] not in gold]
    tier_a: dict[str, set[str]] = {}
    for t in cfg.settings.terms:
        tiers = task_tiers(cfg, t.term_id, ctx.cutoffs(t.term_id))
        tier_a[t.term_id] = {c.key for c in ctx.cutoffs(t.term_id) if "A" in tiers[c.label]}
    pv = {(v.promise_id, _ck(v.cutoff_date)): v for v in verdict_rows(ctx.conn, run_id) if v.promise_id not in gold}
    dtype = {}
    for r in rows:
        if r.date_chunk_id and r.date_chunk_id in ctx.avail:
            dtype[r.date_chunk_id] = ctx.avail[r.date_chunk_id].doc_type
    items: list[Item] = []
    for r in rows:
        pid = r.indicator_id.rsplit("-I", 1)[0]
        term = ctx.promises[pid]["term_id"]
        cut = _ck(r.cutoff_date)
        if cut not in tier_a[term]:
            continue
        if "unresolved" in r.review_reasons:
            items.append(Item(pid, term, cut, "a", (0, r.indicator_id), f"{r.indicator_id} unresolved after "
                              "mini-batch and solo retries (stored as unverifiable)", [r.indicator_id]))
        if r.status in REALISED and r.date_chunk_id and dtype.get(r.date_chunk_id) in ANNOUNCEMENT_TYPES:
            items.append(Item(pid, term, cut, "b", (r.confidence,), f"{r.indicator_id} {r.status}, dated from a "
                              f"{dtype[r.date_chunk_id]} (announcement rule), confidence {r.confidence:.2f}",
                              [r.indicator_id]))
        if r.realisation_date and r.date_precision:
            sworn = ctx.sworn_in(term)
            tm = cfg.term(term)
            upper = r.cutoff_date or (parse_iso(tm.term_end) if tm.term_end else ctx.snapshot)
            d_s = (r.realisation_date - sworn).days
            d_c = (upper - r.realisation_date).days
            near = min(abs(d_s), abs(d_c))
            if near <= j.near_days:
                which = f"{d_s} days after sworn_in {sworn}" if abs(d_s) <= abs(d_c) else f"{d_c} days before " \
                                                                                        f"the bound {upper}"
                items.append(Item(pid, term, cut, "e", (near,), f"{r.indicator_id} dated "
                                  f"{date_label(r.realisation_date, r.date_precision)}, {which}", [r.indicator_id]))
    # c: non-monotone promises over the tier A cutoffs
    for pid, p in ctx.promises.items():
        if pid in gold:
            continue
        seq = [(c.key, pv.get((pid, c.key))) for c in ctx.cutoffs(p["term_id"]) if c.key in tier_a[p["term_id"]]]
        seen = None
        for k, v in seq:
            if v is None:
                continue
            if v.realisation_date is not None:
                seen = seen or k
            elif seen:
                items.append(Item(pid, p["term_id"], k, "c", (0, pid), f"realised at {seen}, {v.status} at {k} "
                                  "(non-monotone; carry-forward would keep the earlier realisation)"))
                break
    for (pid, cut), v in pv.items():
        p = ctx.promises[pid]
        if cut not in tier_a[p["term_id"]] or not p["headline"]:
            continue
        if v.status in REALISED:
            items.append(Item(pid, p["term_id"], cut, "d", (v.confidence,), f"headline promise {v.status}, "
                              f"confidence {v.confidence:.2f}"))
        if cut == FULL and v.status == "not_started":
            cos = min([(diag.get((i, FULL)) or {}).get("top1_cos") or 1.0 for i in ctx.by_promise.get(pid, [])] or [1.0])
            items.append(Item(pid, p["term_id"], cut, "f", (cos,), f"headline promise not_started at full term; "
                              f"top-1 retrieval cosine {cos:.3f}"))
    return items


def _highlight(text: str, quote: Optional[str]) -> tuple[str, bool]:
    """The chunk text with the quote in bold when it is found verbatim (case and spaces relaxed)."""
    if not quote:
        return text, False
    words = [re.escape(w) for w in quote.split()]
    m = re.search(r"\s+".join(words), text, re.I) if words else None
    if not m:
        return text, False
    return text[:m.start()] + "**" + text[m.start():m.end()] + "**" + text[m.end():], True


def write_md(path: Path, n: int, it: Item, ctx: Context, run_id: str, retr: dict, snippet_words: int) -> None:
    conn = ctx.conn
    p = ctx.promises[it.promise_id]
    cd = None if it.cutoff == FULL else it.cutoff
    v = conn.execute("SELECT * FROM verdicts WHERE run_id = ? AND promise_id = ? AND cutoff_date IS ?",
                     (run_id, it.promise_id, cd)).fetchone()
    cut = "full term" if it.cutoff == FULL else f"cutoff {it.cutoff}"
    L = [f"# Item {n} — {it.item_id}", "", f"**Question:** {QUESTION}", "",
         f"- Term: {it.term} · {cut} · group {it.group}", f"- Why flagged: {it.why}",
         f"- Promise: {p['text']}"]
    if v is not None:
        date = date_label(parse_iso(v["realisation_date"]), v["date_precision"]) if v["realisation_date"] else "none"
        L += [f"- **Promise verdict (bulk):** {v['status']} · date {date} · confidence {v['confidence']:.2f}",
              f"- Promise rationale: {v['rationale']}"]
    L.append("")
    for iid in it.indicator_ids or ctx.by_promise.get(it.promise_id, []):
        ind = ctx.indicators[iid]
        r = conn.execute("SELECT * FROM indicator_verdicts WHERE run_id = ? AND indicator_id = ? AND cutoff_date IS ?",
                         (run_id, iid, cd)).fetchone()
        quotes = json.loads(r["quotes"] or "{}") if r else {}
        reasons = json.loads(r["review_reasons"] or "[]") if r else []
        L += [f"## Indicator {iid.rsplit('-', 1)[1]}" + (" (the promise itself)" if ind["is_self"] else ""), ""]
        if not ind["is_self"]:
            L += [f"- Indicator: {ind['text']}"]
        if r:
            date = date_label(parse_iso(r["realisation_date"]), r["date_precision"]) if r["realisation_date"] else "none"
            label = "Verdict" if "unresolved" not in reasons else \
                "Stored verdict (unresolved: every model answer was REJECTED by the checks)"
            L += [f"- **{label}:** {r['status']} · date {date} · confidence {r['confidence']:.2f} · review "
                  f"{', '.join(reasons) or '–'}", f"- Rationale: {r['rationale']}"]
            if "unresolved" in reasons:
                first = _first_answer(ctx.cfg, run_id, r["judging_key"])
                if first:
                    L.append(f"- REJECTED first answer (failed the checks, not used): {first}")
        L.append("")
        qtok = {t for t in tokenize(ind["text"])}
        for rank, cid in enumerate(retr.get((iid, cd), ()), start=1):
            c = ctx.chunks([cid])[cid]
            marks = []
            if r and cid == r["date_chunk_id"]:
                marks.append("⚑ DATE CHUNK")
            if cid in quotes:
                marks.append("cited")
            L += [f"### C{rank}{' — ' + ', '.join(marks) if marks else ''} — {c.title or '(no title)'}", "",
                  f"`{c.doc_type}` · document date {date_label(c.doc_date, c.date_precision)} · available by "
                  f"{c.available_by} · chunk `{cid}`", ""]
            if cid in quotes:
                shown, found = _highlight(c.text, quotes[cid])
                L += [f"Quote: “{quotes[cid]}”" + ("" if found else " (matched only after normalisation)"), "",
                      "> " + " ".join(shown.split()), ""]
            else:
                L += ["> " + snippet(c.text, qtok, snippet_words), ""]
    path.write_text("\n".join(L), encoding="utf-8")


def _first_answer(cfg: Config, run_id: str, key: str) -> str:
    path = cfg.path("judge_failures")
    if not path.exists():
        return ""
    with path.open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if r["run_id"] == run_id and r["judging_key"] == key and r["first_answer"]:
                return r["first_answer"][:600]
    return ""


def run_spotcheck() -> dict[str, Any]:
    cfg = get_config()
    s = cfg.settings.spotcheck
    j = cfg.settings.judge.spotcheck
    run = latest_run(cfg, "bulk", tier="A")
    if not run:
        raise RuntimeError("no bulk run with tier A complete: run `ept judge run --tier A`")
    run_id = run["run_id"]
    conn = db.connect()
    ctx = Context(conn, cfg)
    retr = load_retrievals(conn, run["retrieval_run"])
    diag = read_diag(cfg, run["retrieval_run"])
    items = build(ctx, cfg, run_id, gold_promise_ids(cfg), diag)
    chosen = select(items, s.max_items, j.per_term, j.per_group)
    path = cfg.spotcheck_path("05")
    md_dir = cfg.path("spotcheck_05_dir")
    path.parent.mkdir(parents=True, exist_ok=True)
    archived = _archive_if_reviewed(path, md_dir)
    shutil.rmtree(md_dir, ignore_errors=True)
    md_dir.mkdir(parents=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        for n, it in enumerate(chosen, start=1):
            md = md_dir / f"{n}.md"
            write_md(md, n, it, ctx, run_id, retr, cfg.settings.retrieve.spotcheck.snippet_words)
            w.writerow({"item_id": it.item_id, "term": it.term, "group": it.group, "why_flagged": it.why,
                        "what_to_check": QUESTION, "open": md.relative_to(cfg.root).as_posix(), "verdict": "",
                        "note": ""})
    conn.close()
    return {"rows": len(chosen), "below_minimum": len(chosen) < s.min_items, "path": str(path),
            "groups": [it.group for it in chosen], "candidates": len(items), "archived": archived, "run_id": run_id}
