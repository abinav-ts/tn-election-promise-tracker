"""`ept export-site` (spec 08 §4.1): writes site/public/data/*.json from the committed results. No gold labels are read."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Optional

from ept import db
from ept.config import Config, get_config
from ept.dates import add_months
from ept.model import data as mdata

SITE = "site/public"
E1 = {"fulfilled", "partial", "diluted"}
STATUS_ORDER = ["fulfilled", "partial", "diluted", "in_progress", "not_started", "blocked_external", "unverifiable"]
QUOTE_MAX, TITLE_MAX, EVIDENCE_MAX = 320, 150, 5


def cutoff_months(cfg: Config) -> dict[tuple[str, Optional[str]], int]:
    """(term_id, cutoff_date) -> month in tenure; the full term is month 0 key with None."""
    out = {}
    for t in cfg.settings.terms:
        for m in cfg.settings.retrieve.landmarks_months[t.term_id]:
            out[(t.term_id, add_months(t.sworn_in, m).isoformat())] = m
    return out


def _json(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def load_promises(cfg: Config) -> dict[str, dict]:
    out = {}
    for t in cfg.settings.terms:
        for kind in ("promises", "classification"):
            p = cfg.root / cfg.settings.paths.frozen / f"{kind}_{t.term_id}.jsonl"
            for line in p.read_text(encoding="utf-8").splitlines():
                r = json.loads(line)
                d = out.setdefault(r["promise_id"], {})
                if kind == "promises":
                    d.update(id=r["promise_id"], term=r["term_id"], text=r["text"], src=r["source_text"] if r["source_lang"] != "en" else "",
                             section=r["section"], page=r["page"])
                else:
                    d.update(sector=r["sector"], type=r["promise_type"], spec=r["specificity"], head=bool(r["headline"]),
                             cost=r["cost_band"], union=bool(r["union_dependent"]), cont=bool(r["continues_existing"]))
    return out


def quotes_by_promise(cfg: Config) -> dict[str, dict[str, str]]:
    """promise_id -> chunk_id -> verbatim quote (strong-run quotes win; any cutoff)."""
    out: dict[str, dict[str, str]] = defaultdict(dict)
    with db.connect() as conn:
        rows = conn.execute("select indicator_id, judge_source, quotes from indicator_verdicts where quotes != '{}' "
                            "order by case judge_source when 'strong' then 1 else 0 end").fetchall()
    for iid, _src, q in rows:
        pid = iid.rsplit("-I", 1)[0]
        for cid, text in json.loads(q).items():
            out[pid][cid] = text
    return out


def chunk_docs(cfg: Config, chunk_ids: set[str]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    ids = sorted(chunk_ids)
    with db.connect() as conn:
        for i in range(0, len(ids), 500):
            part = ids[i:i + 500]
            q = ("select c.chunk_id, d.title, d.doc_type, d.doc_date, d.date_precision, d.source_url, d.archive_url "
                 "from chunks c join documents d on d.doc_id = c.doc_id where c.chunk_id in (%s)" % ",".join("?" * len(part)))
            for r in conn.execute(q, part):
                out[r[0]] = {"title": (r[1] or "")[:TITLE_MAX], "type": r[2], "date": r[3], "prec": r[4], "url": r[5] or r[6] or ""}
    return out


def summary_for(cfg: Config, rows: list[dict], months: dict) -> dict:
    promises_all = load_promises(cfg)
    summary = {"statuses": STATUS_ORDER, "cells": []}
    cell: dict[tuple, Counter] = defaultdict(Counter)
    src: dict[tuple, Counter] = defaultdict(Counter)
    for r in rows:
        term = r["promise_id"].rsplit("-", 1)[0]
        k = (term, months.get((term, r["cutoff_date"]), 0))
        cell[k][r["status"]] += 1
        src[k][r["judge_source"]] += 1
    totals = {t.term_id: sum(1 for p in promises_all if p.startswith(t.term_id + "-")) for t in cfg.settings.terms}
    for (term, m), c in sorted(cell.items()):
        n = sum(c.values())
        summary["cells"].append({"term": term, "month": m, "n": n, "of": totals[term], "complete": n >= 0.99 * totals[term],
                                 "status": dict(c), "realised": sum(c[s] for s in E1) / n, "judge_source": dict(src[(term, m)])})
    summary["terms"] = {t.term_id: {"party": t.party, "sworn_in": t.sworn_in.isoformat(),
                                    "term_end": t.term_end.isoformat() if t.term_end else None, "role": str(t.role)}
                        for t in cfg.settings.terms}
    summary["final_export"] = mdata.newest_final(cfg).name
    return summary


def build(cfg: Config) -> dict:
    rows = mdata.load_final(cfg)
    prom = load_promises(cfg)
    months = cutoff_months(cfg)
    q = quotes_by_promise(cfg)
    by: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by[r["promise_id"]].append(r)
    show: dict[str, dict] = {}   # the verdict whose evidence is displayed: full term (TVK: its snapshot)
    for pid, rs in by.items():
        term = pid.rsplit("-", 1)[0]
        want = None if cfg.term(term).term_end is not None else mdata.snapshot_date(cfg, term).isoformat()
        show[pid] = next(r for r in rs if r["cutoff_date"] == want)
    docs = chunk_docs(cfg, {c for r in show.values() for c in r["cited_chunk_ids"]})
    items = []
    for pid in sorted(prom):
        p = dict(prom[pid])
        term = p["term"]
        v = {}
        for r in by[pid]:
            m = months.get((term, r["cutoff_date"]), 0)
            v[str(m)] = [r["status"], r["realisation_date"] or "", r["date_precision"] or "", r["judge_source"]]
        s = show[pid]
        ev = []
        for cid in s["cited_chunk_ids"][:EVIDENCE_MAX]:
            d = docs.get(cid)
            if d:
                ev.append({**d, "quote": q.get(pid, {}).get(cid, "")[:QUOTE_MAX]})
        p.update(v=v, shown=str(months.get((term, s["cutoff_date"]), 0)), why=s["rationale"], conf=round(s["confidence"], 2),
                 review=bool(s["needs_review"]), reasons=s.get("review_reasons") or [], model=s["judge_model"], ev=ev)
        items.append(p)
    summary = summary_for(cfg, rows, months)
    alt = {}
    try:
        brows = mdata.load_final(cfg, "bulk")
        bsum = summary_for(cfg, brows, months)
        for r in brows:
            if r["promise_id"] in show and r["cutoff_date"] == show[r["promise_id"]]["cutoff_date"]:
                alt[r["promise_id"]] = [r["status"], r["realisation_date"] or "", r["date_precision"] or ""]
        for it in items:
            it["alt"] = alt.get(it["id"])
    except FileNotFoundError:
        bsum = None
    return {"promises": items, "summary": summary, "summary_bulk": bsum}


def work_stats(cfg: Config) -> dict:
    """Counts for the 'Work done' page, computed from the repository and the DB (nothing typed by hand)."""
    import re
    import subprocess

    conn = db.connect()
    one = lambda q: conn.execute(q).fetchone()[0]
    docs = dict(conn.execute("select doc_type, count(*) from documents group by 1").fetchall())
    promises = dict(conn.execute("select term_id, count(*) from promises group by 1").fetchall())
    rr = conn.execute("select run_id from retrievals order by rowid desc limit 1").fetchone()[0]
    manifest = json.loads((cfg.path("judgments") / "judge-20261022T070634Z" / "manifest.json").read_text(encoding="utf-8"))
    imported = [b for b in manifest["batches"] if str(b.get("status", "")).startswith("imported")]
    log = (cfg.root / "docs/decisions/log.md").read_text(encoding="utf-8")
    sh = lambda *a: subprocess.run(a, cwd=cfg.root, capture_output=True, text=True).stdout.strip()
    loc = sum(len(p.read_text(encoding="utf-8").splitlines()) for p in (cfg.root / "src/ept").rglob("*.py"))
    tests = re.findall(r"(\d+) tests? collected", sh("python", "-m", "pytest", "--collect-only", "-q") or "")
    return {"documents": one("select count(*) from documents"), "documents_by_type": docs, "chunks": one("select count(*) from chunks"),
            "promises": promises, "promises_total": sum(promises.values()), "indicators": one("select count(*) from indicators"),
            "retrieval_tasks": one(f"select count(*) from (select distinct indicator_id, cutoff_date from retrievals where run_id='{rr}')"),
            "indicator_verdicts": one("select count(*) from indicator_verdicts"),
            "strong_batches_run": len({b["n"] for b in imported if not b.get("retry_of")}),
            "strong_batches_exported": len({b["n"] for b in manifest["batches"] if not b.get("retry_of")}),
            "subagent_tokens": int(sum(b.get("tokens") or 0 for b in imported)),
            "decisions": len(re.findall(r"^- \*\*D-\d+", log, flags=re.M)),
            "specs": len(list((cfg.root / "specs").glob("0*.md"))), "commits": int(sh("git", "rev-list", "--count", "HEAD") or 0),
            "python_lines": loc, "tests": int(tests[-1]) if tests else None}


def _stamp(obj: dict, setting: str, standin: bool = False) -> dict:
    """Data-contract wrapper: every per-setting file carries which judging setting it is (D-121)."""
    return {"meta": {"setting": setting, "standin": standin}, **obj}


def export(cfg: Optional[Config] = None) -> dict:
    cfg = cfg or get_config()
    out = cfg.root / SITE / "data"
    out.mkdir(parents=True, exist_ok=True)
    built = build(cfg)
    (out / "promises.json").write_text(_json(built["promises"]), encoding="utf-8")
    (out / "summary.json").write_text(_json(built["summary"]), encoding="utf-8")
    (out / "work.json").write_text(_json(work_stats(cfg)), encoding="utf-8")
    if built["summary_bulk"]:
        (out / "summary_bulk.json").write_text(_json(built["summary_bulk"]), encoding="utf-8")
    model = json.loads(cfg.path("model_outputs").read_text(encoding="utf-8"))
    (out / "model.json").write_text(_json(model), encoding="utf-8")
    mb = cfg.path("model_outputs").with_name("model_outputs_bulk.json")
    if mb.exists():
        (out / "model_bulk.json").write_text(_json(json.loads(mb.read_text(encoding="utf-8"))), encoding="utf-8")
    # data contract for the redesigned overview (D-121): summary_/model_ {gemini, claude}, plus pace.json.
    # The Claude-only files are the Claude-preferred data (stand-in) until the Claude-only run exists.
    mc = cfg.path("model_outputs").with_name("model_outputs_strong.json")
    claude_model = json.loads(mc.read_text(encoding="utf-8")) if mc.exists() else model
    standin = not mc.exists()
    sg = built["summary_bulk"]
    try:
        csum = summary_for(cfg, mdata.load_final(cfg, "strong"), cutoff_months(cfg))
    except FileNotFoundError:
        csum = built["summary"]
    (out / "summary_claude.json").write_text(_json(_stamp(csum, "claude", standin)), encoding="utf-8")
    (out / "model_claude.json").write_text(_json(_stamp(claude_model, "claude", standin)), encoding="utf-8")
    if sg:
        (out / "summary_gemini.json").write_text(_json(_stamp(sg, "gemini")), encoding="utf-8")
        (out / "model_gemini.json").write_text(_json(_stamp(json.loads(mb.read_text(encoding="utf-8")), "gemini")), encoding="utf-8")
    pace = {"claude": _stamp(claude_model["projection"].get("pace", {}), "claude", standin)}
    if mb.exists():
        pace["gemini"] = _stamp(json.loads(mb.read_text(encoding="utf-8"))["projection"].get("pace", {}), "gemini")
    pace["claude_preferred_mixed"] = _stamp(model["projection"].get("pace", {}), "claude_preferred_mixed")
    (out / "pace.json").write_text(_json(pace), encoding="utf-8")
    ev_path = cfg.path("evaluation_json")
    if ev_path.exists():
        ev = json.loads(ev_path.read_text(encoding="utf-8"))
        # aggregate tables only: drop the per-promise listing of disagreements
        for j in ev.get("judges", {}).values():
            j.get("disagreements", {}).pop("listed", None)
        (out / "evaluation.json").write_text(_json(ev), encoding="utf-8")
    return {"promises": len(built["promises"]), "bytes": {p.name: p.stat().st_size for p in out.glob("*.json")}}
