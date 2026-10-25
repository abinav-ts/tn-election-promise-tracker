"""Builds the data bundle for the gold labelling page (spec 06 §G6). Stdlib + PyYAML.

Per gold promise: the promise and its manifesto unit, plus up to K corpus candidates
from a plain BM25 keyword search on the promise's own English text (no model output,
no stage-03 queries, no stage-04 retrieval). Also a title index of every English
evidence document for free lookup. Output: data/interim/gold_page/page_data.json.
"""
from __future__ import annotations

import calendar
import csv
import datetime as dt
import json
import math
import re
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
K = 8                 # candidates per promise
MAX_PER_DOC = 2
K1, B = 1.5, 0.75
SNAPSHOT_END = "2026-10-10"   # corpus snapshot; bound for the ongoing TVK term
STOP = set("""a an and are as at be been by for from has have in into is it its of on or that the their this
to was were will with within all any each every more new other such than these those through under upto up
also per who which whose shall can may provide providing provided ensure take taken make made given give
tamil nadu government state govt scheme schemes""".split())
TOK = re.compile(r"[a-z0-9]+")


def toks(s: str) -> list[str]:
    return [t for t in TOK.findall(s.lower()) if len(t) > 1 and t not in STOP]


def period_end(d, prec):
    d = dt.date.fromisoformat(d[:10])
    if prec == "month":
        return d.replace(day=calendar.monthrange(d.year, d.month)[1])
    if prec == "year":
        return d.replace(month=12, day=31)
    return d


def available_by(doc_date, prec, doc_type, fy, title, fyb):
    base = period_end(doc_date, prec) if doc_date and prec else None
    bounded = doc_type in fyb["doc_types"] or any(
        (title or "").strip().lower().startswith(p.lower()) for p in fyb["title_prefixes"].get(doc_type, []))
    m = re.search(r"((?:19|20)\d{2})\s*[-_/–]\s*((?:19|20)?\d{2})", fy or "")
    fy_end = None
    if bounded and m and int(m.group(2)[-2:]) == (int(m.group(1)) + 1) % 100:
        fy_end = dt.date(int(m.group(1)) + 1, 3, 31)
    if fy_end is None:
        return base
    return fy_end if base is None or fy_end < base else base


def main():
    settings = yaml.safe_load(open(ROOT / "config/settings.yaml"))
    fyb = settings["date"]["fy_bound"]
    terms = {t["term_id"]: t for t in settings["terms"]} if isinstance(settings.get("terms"), list) else {}
    sample = list(csv.DictReader(open(ROOT / "data/gold/gold_sample.csv", encoding="utf-8")))
    prom, units = {}, {}
    for t in {r["term_id"] for r in sample}:
        for l in open(ROOT / f"data/frozen/promises_{t}.jsonl", encoding="utf-8"):
            p = json.loads(l); prom[p["promise_id"]] = p
        for l in open(ROOT / f"data/interim/manifestos/{t}/units.jsonl", encoding="utf-8"):
            u = json.loads(l); units[u["unit_id"]] = u
    con = sqlite3.connect(ROOT / "data/ept.sqlite")
    docs = {}
    for row in con.execute("select doc_id, doc_type, title, doc_date, date_precision, fiscal_year, source_url, "
                           "archive_url, department from documents where lang='en' and doc_type!='manifesto'"):
        doc_id, typ, title, dd, prec, fy, src, arc, dept = row
        av = available_by(dd, prec, typ, fy, title, fyb)
        docs[doc_id] = {"id": doc_id, "type": typ, "title": (title or "").strip(), "date": dd, "prec": prec,
                        "avail": av.isoformat() if av else None, "url": src or arc, "dept": dept}
    term_dates = {}
    for t in {r["term_id"] for r in sample}:
        s, e = con.execute("select sworn_in, term_end from terms where term_id=?", (t,)).fetchone()
        term_dates[t] = (s, e or SNAPSHOT_END)
    # queries
    q_by_term = defaultdict(dict)
    for r in sample:
        q_by_term[r["term_id"]][r["promise_id"]] = Counter(toks(prom[r["promise_id"]]["text"]))
    cands = {}
    for t, queries in q_by_term.items():
        lo, hi = term_dates[t]
        vocab = set().union(*queries.values())
        df, N, total_len = Counter(), 0, 0
        stats = []  # (chunk_id, doc_id, len, {term: tf})
        for cid, did, text in con.execute("select chunk_id, doc_id, text from chunks"):
            d = docs.get(did)
            if not d or not d["avail"] or not (lo <= d["avail"] <= hi):
                continue
            tk = toks(d["title"] + " " + text)
            N += 1; total_len += len(tk)
            tf = Counter(x for x in tk if x in vocab)
            for x in tf:
                df[x] += 1
            if tf:
                stats.append((cid, did, len(tk), tf))
        avgdl = total_len / max(N, 1)
        idf = {x: math.log(1 + (N - df[x] + 0.5) / (df[x] + 0.5)) for x in vocab}
        print(t, "eligible chunks", N)
        for pid, q in queries.items():
            scored = []
            for cid, did, L, tf in stats:
                s = sum(idf[x] * tf[x] * (K1 + 1) / (tf[x] + K1 * (1 - B + B * L / avgdl)) for x in q if x in tf)
                if s > 0:
                    scored.append((s, cid, did))
            scored.sort(reverse=True)
            per_doc, top = Counter(), []
            for s, cid, did in scored:
                if per_doc[did] >= MAX_PER_DOC:
                    continue
                per_doc[did] += 1; top.append((cid, round(s, 2)))
                if len(top) == K:
                    break
            cands[pid] = top
    need = {cid for v in cands.values() for cid, _ in v}
    chunk_rows = {}
    for cid in need:
        did, seq, text, ps, pe = con.execute("select doc_id, seq, text, page_start, page_end from chunks where chunk_id=?",
                                             (cid,)).fetchone()
        chunk_rows[cid] = {"doc": did, "text": text, "p": [ps, pe]}
    items = []
    for r in sample:
        p = prom[r["promise_id"]]
        u = units.get(p["parent_group"], {})
        items.append({"order": int(r["order"]), "id": p["promise_id"], "term": p["term_id"], "block": r["block"],
                      "text": p["text"], "src": p["source_text"], "lang": p["source_lang"], "section": p["section"],
                      "page": p["page"], "unit": u.get("text", ""), "term_window": term_dates[p["term_id"]],
                      "cands": [{"cid": c, "score": s, **chunk_rows[c]} for c, s in cands[p["promise_id"]]]})
    used_docs = {c["doc"] for it in items for c in it["cands"]}
    out = {"generated_at": dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
           "sample_meta": json.load(open(ROOT / "data/gold/gold_sample_meta.json")),
           "items": items,
           "docs": [[d["id"], d["type"], d["avail"] or "", d["title"][:220], d["url"] or ""] for d in docs.values()],
           "cand_doc_meta": {k: docs[k] for k in used_docs}}
    od = ROOT / "data/interim/gold_page"; od.mkdir(parents=True, exist_ok=True)
    (od / "page_data.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("items", len(items), "chunks", len(chunk_rows), "docs", len(docs),
          "bytes", (od / "page_data.json").stat().st_size)


if __name__ == "__main__":
    main()
