"""`ept retrieve spotcheck` (spec 04 §4.10, global §12.4): the 7–10 most problematic indicator × cutoff items.

Problem groups, in priority order:
  a. method disagreement + weak: BM25 top k and dense top k share no chunk, and the top-1 dense cosine is in
     the term's bottom quartile;
  b. weakest evidence on a full-term run (lowest top-1 rrf, then cosine);
  c. the generic-query override promises (config/classify_overrides.csv), lowest top-1 cosine;
  d. headline promises, lowest top-1 cosine;
  e. date-sensitive: a selected chunk whose available_by comes from the fiscal-year bound, or lies within
     `near_cutoff_days` before the run's upper bound;
  f. fill: a GO-place chunk that displaced a higher-ranked chunk.
At most `per_term` per term and `per_group` per group, one item per promise; within a group the terms take
turns (best item of each term first). A sheet that already holds verdicts is archived, never overwritten.
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import numpy as np

from ept import db
from ept.config import Config, get_config
from ept.dates import BASIS_FETCHED, BASIS_FY_ONLY, BASIS_FY_TIGHTENED, parse_iso
from ept.retrieve import eligible as el
from ept.retrieve.report import load_pairs, override_notes, override_promises
from ept.retrieve.run import latest_run, read_diag, _read_meta
from ept.retrieve.tokenize import tokenize

COLUMNS = ["item_id", "term", "group", "why_flagged", "what_to_check", "open", "verdict", "note"]
GROUPS = "abcdef"
Q_RELEVANT = ("Is at least one of the 5 chunks about this commitment (evidence for or against delivery)? "
              "ok = yes; wrong = none is; unsure = can't tell.")
Q_DATE = ("Was this document plausibly issued by its available-by date (look at the flagged chunk's document: "
          "its own dates, the fiscal year, events it reports)? ok = yes; wrong = it must be later; unsure.")


@dataclass
class Item:
    indicator_id: str
    promise_id: str
    term: str
    cutoff: str  # cutoff date or "full"
    group: str
    key: tuple  # ascending = more problematic
    why: str
    flagged_chunk: Optional[str] = None

    @property
    def item_id(self) -> str:
        return f"{self.indicator_id}@{self.cutoff}"


def build(pairs: dict, avail: dict[str, el.ChunkAvail], overrides: set[str], uppers: dict[tuple[str, str], dt.date],
          near_days: int) -> list[Item]:
    items: list[Item] = []
    cos_by_term: dict[str, list[float]] = {}
    for p in pairs.values():
        if p["diag"].get("top1_cos") is not None:
            cos_by_term.setdefault(p["term"], []).append(p["diag"]["top1_cos"])
    q1 = {t: float(np.percentile(v, 25)) for t, v in cos_by_term.items()}
    for (iid, cut), p in pairs.items():
        d, t, pid = p["diag"], p["term"], p["promise_id"]
        cos = d.get("top1_cos")
        cos = 1.0 if cos is None else cos
        mk = lambda g, key, why, chunk=None: items.append(Item(iid, pid, t, cut, g, key, why, chunk))  # noqa: E731
        if d.get("overlap_top_k") == 0 and cos <= q1.get(t, -1):
            mk("a", (cos,), f"BM25 top 5 and dense top 5 share no chunk; top-1 dense cosine {cos:.3f} is in "
                            f"{t}'s bottom quartile (≤ {q1[t]:.3f})")
        if cut == el.FULL:
            rrf = d.get("top1_rrf") or 0.0
            mk("b", (rrf, cos), f"full-term run: weakest evidence (top-1 rrf {rrf:.4f}, cosine {cos:.3f})")
        if pid in overrides:
            mk("c", (cos,), f"generic override queries (stage 03): top-1 cosine {cos:.3f}")
        if p["headline"]:
            mk("d", (cos,), f"headline promise: top-1 cosine {cos:.3f}")
        upper = uppers[(t, cut)]
        for row in p["rows"]:
            a = avail[row["chunk_id"]]
            days = (upper - a.available_by).days
            if a.basis in (BASIS_FY_TIGHTENED, BASIS_FY_ONLY, BASIS_FETCHED):
                how = {BASIS_FY_TIGHTENED: "capped at its fiscal-year end (D-077)",
                       BASIS_FY_ONLY: "dated only by its fiscal-year end (D-077)",
                       BASIS_FETCHED: "capped at the day it was fetched (D-082)"}[a.basis]
                mk("e", (row["rank"], 0 if a.basis == BASIS_FY_ONLY else 1, days),
                   f"rank {row['rank']} chunk {row['chunk_id']} ({a.doc_type}) is available by {a.available_by}, "
                   f"{how}; {days} days before the bound {upper}", row["chunk_id"])
                break
            if days <= near_days:
                mk("e", (row["rank"], 2, days),
                   f"rank {row['rank']} chunk {row['chunk_id']} ({a.doc_type}) is available by {a.available_by}, "
                   f"{days} days before the bound {upper}", row["chunk_id"])
                break
        if d.get("go_places"):
            gos = [r for r in p["rows"] if r["scores"].get("go_reserved")]
            mk("f", (-d["go_places"], -max(r["rank"] for r in gos)),
               f"{d['go_places']} GO place(s): {', '.join(r['chunk_id'] for r in gos)} replaced "
               f"{', '.join(d.get('displaced') or [])}", gos[0]["chunk_id"])
    return items


def select(items: list[Item], max_items: int, per_term: int, per_group: int,
           reserve_per_term: Optional[dict[str, int]] = None) -> list[Item]:
    """Priority order with the spread caps; `reserve_per_term` {group: n} first takes each term's best n
    items of that group (D-083), which count toward the caps."""
    by_key = sorted(items, key=lambda it: (it.key, it.item_id))
    turn: dict[tuple[str, str], int] = {}
    order: dict[int, int] = {}
    for it in by_key:  # the n-th best item of a term within its group gets turn n
        k = (it.group, it.term)
        order[id(it)] = turn.get(k, 0)
        turn[k] = order[id(it)] + 1
    ranked = sorted(items, key=lambda it: (GROUPS.index(it.group), order[id(it)], it.key, it.item_id))
    out: list[Item] = []
    n_term: dict[str, int] = {}
    n_group: dict[str, int] = {}
    seen: set[str] = set()

    def take(it: Item) -> bool:
        if (it in out or it.promise_id in seen or n_term.get(it.term, 0) >= per_term
                or n_group.get(it.group, 0) >= per_group or len(out) >= max_items):
            return False
        out.append(it)
        seen.add(it.promise_id)
        n_term[it.term] = n_term.get(it.term, 0) + 1
        n_group[it.group] = n_group.get(it.group, 0) + 1
        return True

    for group, n in (reserve_per_term or {}).items():
        for term in sorted({it.term for it in items}):
            got = 0
            for it in by_key:
                if got >= n:
                    break
                if it.group == group and it.term == term and take(it):
                    got += 1
    for it in ranked:
        take(it)
    return sorted(out, key=lambda it: (GROUPS.index(it.group), order[id(it)], it.key, it.item_id))


def snippet(text: str, query_tokens: set[str], n_words: int) -> str:
    """The `n_words`-word window with the most query-word matches; matches in bold."""
    words = text.split()
    hits = np.array([1 if set(tokenize(w)) & query_tokens else 0 for w in words], dtype=np.int64)
    if len(words) <= n_words:
        start = 0
    else:
        sums = np.convolve(hits, np.ones(n_words, dtype=np.int64), mode="valid")
        start = int(np.argmax(sums))
    window = words[start:start + n_words]
    shown = " ".join(f"**{w}**" if hits[start + i] else w for i, w in enumerate(window))
    return ("… " if start > 0 else "") + shown + (" …" if start + n_words < len(words) else "")


def write_md(path: Path, it: Item, info: dict[str, Any], rows: list[dict[str, Any]], cfg: Config) -> None:
    sc = cfg.settings.retrieve.spotcheck
    qtok = {t for q in info["queries"] for t in tokenize(q)}
    cut = "full term (sworn_in … term_end)" if it.cutoff == el.FULL else f"cutoff {it.cutoff}"
    L = [f"# {it.item_id}", "", f"**Question:** {Q_DATE if it.group == 'e' else Q_RELEVANT}", "",
         f"- Term: {it.term} · {cut} · group {it.group}", f"- Why flagged: {it.why}",
         f"- Promise ({it.promise_id}): {info['promise_text']}",
         f"- Indicator{' (the promise itself)' if info['is_self'] else ''}: {info['indicator_text']}",
         f"- Search queries: {' | '.join(info['queries'])}"]
    if info.get("override_note"):
        L.append(f"- Stage 03 override note (why the queries are generic): {info['override_note']}")
    L.append("")
    for r in rows:
        flag = " ⚑ FLAGGED" if r["chunk_id"] == it.flagged_chunk else ""
        s = r["scores"]
        L += [f"## Rank {r['rank']}{flag} — {r['title'] or '(no title)'}", "",
              f"`{r['doc_type']}` · available by **{r['available_by']}** ({r['basis']}; stored date "
              f"{r['doc_date'] or 'none'} {r['date_precision'] or ''}, source {r['date_source']}, FY "
              f"{r['fiscal_year'] or '–'}) · chunk `{r['chunk_id']}` · file `{r['local_path']}`"
              + (f" p{r['page_start']}" if r["page_start"] else ""),
              f"scores: rrf {s.get('rrf', 0):.4f}, BM25 rank {int(s['bm25_rank']) if 'bm25_rank' in s else '–'}, "
              f"dense rank {int(s['dense_rank']) if 'dense_rank' in s else '–'}, cosine {s.get('dense_cos', 0):.3f}"
              + (", GO place" if s.get("go_reserved") else ""), "",
              "> " + snippet(r["text"], qtok, sc.snippet_words), ""]
    path.write_text("\n".join(L), encoding="utf-8")


def _archive_if_reviewed(path: Path, md_dir: Path) -> Optional[str]:
    """A sheet that already holds verdicts is moved aside (with its .md files), never overwritten."""
    if not path.exists():
        return None
    with path.open(encoding="utf-8", newline="") as f:
        if not any((r.get("verdict") or "").strip() for r in csv.DictReader(f)):
            return None
    stamp = dt.datetime.now().strftime("%Y%m%dT%H%M%S")
    dest = path.with_name(f"{path.stem}_reviewed_{stamp}{path.suffix}")
    path.rename(dest)
    if md_dir.exists():
        md_dir.rename(md_dir.with_name(f"{md_dir.name}_reviewed_{stamp}"))
    return str(dest)


def run_spotcheck(term: Optional[str] = None, run_id: Optional[str] = None) -> dict[str, Any]:
    cfg = get_config()
    s, sc = cfg.settings.spotcheck, cfg.settings.retrieve.spotcheck
    meta = _read_meta(cfg, run_id) if run_id else latest_run(cfg)
    if not meta:
        raise RuntimeError("no retrieve run yet: run `ept retrieve run`")
    run_id = meta["run_id"]
    conn = db.connect()
    avail_list = el.load_availability(conn, cfg)
    avail = {c.chunk_id: c for c in avail_list}
    pairs = {k: p for k, p in load_pairs(conn, run_id, read_diag(cfg, run_id)).items()
             if term in (None, p["term"])}
    uppers = {}
    for t in {p["term"] for p in pairs.values()}:
        tm = cfg.term(t)
        uppers[(t, el.FULL)] = parse_iso(tm.term_end) if tm.term_end else None
        for (_, cut), p in pairs.items():
            if p["term"] == t and cut != el.FULL:
                uppers[(t, cut)] = parse_iso(cut)
    chosen = select(build(pairs, avail, override_promises(cfg), uppers, sc.near_cutoff_days),
                    s.max_items, sc.per_term, sc.per_group, sc.reserve_per_term)
    notes = override_notes(cfg)
    path = cfg.spotcheck_path("04")
    md_dir = cfg.path("spotcheck_04_dir")
    path.parent.mkdir(parents=True, exist_ok=True)
    archived = _archive_if_reviewed(path, md_dir)
    shutil.rmtree(md_dir, ignore_errors=True)
    md_dir.mkdir(parents=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        for n, it in enumerate(chosen, start=1):
            info = conn.execute("SELECT i.text AS indicator_text, i.is_self, i.search_queries, p.text AS promise_text "
                                "FROM indicators i JOIN promises p ON p.promise_id = i.promise_id "
                                "WHERE i.indicator_id = ?", (it.indicator_id,)).fetchone()
            info = {**dict(info), "queries": json.loads(info["search_queries"]),
                    "override_note": notes.get(it.promise_id, "")}
            rows = []
            for r in pairs[(it.indicator_id, it.cutoff)]["rows"]:
                c = conn.execute("SELECT c.text, c.page_start, d.title, d.doc_date, d.date_precision, d.date_source, "
                                 "d.fiscal_year, d.local_path FROM chunks c JOIN documents d ON d.doc_id = c.doc_id "
                                 "WHERE c.chunk_id = ?", (r["chunk_id"],)).fetchone()
                a = avail[r["chunk_id"]]
                rows.append({**r, **dict(c), "available_by": a.available_by, "basis": a.basis})
            md = md_dir / f"{n}.md"
            write_md(md, it, info, rows, cfg)
            w.writerow({"item_id": it.item_id, "term": it.term, "group": it.group, "why_flagged": it.why,
                        "what_to_check": Q_DATE if it.group == "e" else Q_RELEVANT,
                        "open": md.relative_to(cfg.root).as_posix(), "verdict": "", "note": ""})
    conn.close()
    return {"rows": len(chosen), "below_minimum": len(chosen) < s.min_items, "path": str(path),
            "groups": [it.group for it in chosen], "archived": archived, "run_id": run_id}
