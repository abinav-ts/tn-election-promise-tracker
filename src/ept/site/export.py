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
    summary = {"statuses": STATUS_ORDER, "cells": []}
    cell: dict[tuple, Counter] = defaultdict(Counter)
    src: dict[tuple, Counter] = defaultdict(Counter)
    for r in rows:
        term = r["promise_id"].rsplit("-", 1)[0]
        k = (term, months.get((term, r["cutoff_date"]), 0))
        cell[k][r["status"]] += 1
        src[k][r["judge_source"]] += 1
    for (term, m), c in sorted(cell.items()):
        n = sum(c.values())
        summary["cells"].append({"term": term, "month": m, "n": n, "status": dict(c), "realised": sum(c[s] for s in E1) / n,
                                 "judge_source": dict(src[(term, m)])})
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


def export(cfg: Optional[Config] = None) -> dict:
    cfg = cfg or get_config()
    out = cfg.root / SITE / "data"
    out.mkdir(parents=True, exist_ok=True)
    built = build(cfg)
    (out / "promises.json").write_text(_json(built["promises"]), encoding="utf-8")
    (out / "summary.json").write_text(_json(built["summary"]), encoding="utf-8")
    if built["summary_bulk"]:
        (out / "summary_bulk.json").write_text(_json(built["summary_bulk"]), encoding="utf-8")
    model = json.loads(cfg.path("model_outputs").read_text(encoding="utf-8"))
    (out / "model.json").write_text(_json(model), encoding="utf-8")
    mb = cfg.path("model_outputs").with_name("model_outputs_bulk.json")
    if mb.exists():
        (out / "model_bulk.json").write_text(_json(json.loads(mb.read_text(encoding="utf-8"))), encoding="utf-8")
    ev_path = cfg.path("evaluation_json")
    if ev_path.exists():
        ev = json.loads(ev_path.read_text(encoding="utf-8"))
        # aggregate tables only: drop the per-promise listing of disagreements
        for j in ev.get("judges", {}).values():
            j.get("disagreements", {}).pop("listed", None)
        (out / "evaluation.json").write_text(_json(ev), encoding="utf-8")
    return {"promises": len(built["promises"]), "bytes": {p.name: p.stat().st_size for p in out.glob("*.json")}}
