"""`ept spotcheck`: the stage 01 worst-case review sheet (global spec §12.4, D-027; spec 01 step 8).

Ranks every downloaded document by spec 01's problem score and writes the top items,
at most `per_source` from one source, to data/interim/spotcheck_01.csv with a
specific `what_to_check` for each. `verdict` and `note` are left for the user.
"""

from __future__ import annotations

import csv
import datetime as dt
import re
import sqlite3
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from ept import db
from ept.config import Config, get_config
from ept.corpus.fetch import read_sidecar

COLUMNS = ["item_id", "why_flagged", "what_to_check", "path", "verdict", "note"]
# (a) failed date checks, strongest first; "dated by Wayback"/"undated" reasons belong to group (b)
DATE_FAILURES = [("anachronism", 4), ("conflict", 4), ("FY mismatch", 3), ("out of window", 2)]


def _dmy(iso: Optional[str]) -> str:
    return dt.date.fromisoformat(iso).strftime("%d-%m-%Y") if iso else "?"


@dataclass
class Item:
    doc: dict[str, Any]
    meta: dict[str, Any]
    n_chunks: int
    source: str
    reasons: list[str] = field(default_factory=list)
    score: tuple = ()
    why: list[str] = field(default_factory=list)
    checks: list[str] = field(default_factory=list)


def _find_page(text_path: Optional[Path], needle: str) -> Optional[int]:
    if not text_path or not text_path.exists() or not needle:
        return None
    for i, page in enumerate(text_path.read_text(encoding="utf-8").split("\f"), start=1):
        if needle in page:
            return i
    return None


def _copyright_dated(meta: dict[str, Any]) -> bool:
    resolved = (meta.get("dating") or {}).get("resolved") or {}
    return any(r.startswith("dated from © year") for r in resolved.get("reasons", []))


def score_item(it: Item, cfg: Config, chunk_ratio_bounds: tuple[float, float]) -> None:
    d, meta = it.doc, it.meta
    dating = meta.get("dating") or {}
    resolved = dating.get("resolved") or {}
    parse = meta.get("parse") or {}
    text_path = cfg.root / parse["text_path"] if parse.get("text_path") else None
    title = d["title"] or "(no title)"
    stored = f"{d['doc_date']} ({d['date_precision']}, {d['date_source']})" if d["doc_date"] else "none"

    # (a) failed date checks
    a = 0
    for r in resolved.get("reasons", []):
        for key, weight in DATE_FAILURES:
            if r.startswith(key):
                a += weight
                it.why.append(r)
                if key == "anachronism":
                    m = re.search(r"mentions (\S+) \('(.+)'\)", r)
                    when, snippet = (m.group(1), m.group(2)) if m else ("?", "")
                    page = _find_page(text_path, snippet)
                    it.checks.append(f"Text{f' p.{page}' if page else ''} mentions {_dmy(when)} ('{snippet}'), after "
                                     f"the stored date {_dmy(d['doc_date'])}: is it a future/target date (ok) or is "
                                     f"the document really later than {_dmy(d['doc_date'])} (wrong)?")
                elif key == "conflict":
                    m = re.search(r"conflict: (\S+) (\S+) vs (\S+) (\S+)", r)
                    if m:
                        snippet = (dating.get("text_candidate") or {}).get("evidence", "")
                        page = _find_page(text_path, snippet.split()[-1]) if snippet else None
                        it.checks.append(f"Listing date {_dmy(m.group(2))} vs date in text {_dmy(m.group(4))}"
                                         f"{f' (p.{page}: {snippet!r})' if page else ''}: which is the document's "
                                         f"own issue date?")
                elif key == "FY mismatch":
                    it.checks.append(f"Stored date {_dmy(d['doc_date'])} ({d['date_source']}) is outside FY "
                                     f"{d['fiscal_year']} ± {cfg.settings.date.fy_slack_months} months: confirm the "
                                     f"file is the {d['fiscal_year']} document named in the title, and nothing in it "
                                     f"is dated after {_dmy(d['doc_date'])}.")
                elif key == "out of window":
                    it.checks.append(f"Stored date {_dmy(d['doc_date'])} is before the evidence window "
                                     f"({cfg.settings.evidence_window.start}): confirm it is an old snapshot "
                                     f"(kept as context only).")
                break

    # (b) weak dates: none, Wayback capture, © year (stored as document_text, D-024)
    b = 0
    if d["date_source"] == "none":
        b = 3
        it.why.append("undated")
        it.checks.append("No issue date found: look at the cover and first 2 pages for a date we missed "
                         "(e.g. 'presented on', 'dated', a G.O. header).")
    elif _copyright_dated(meta):
        b = 2
        ev = next((c["evidence"] for c in dating.get("candidates", []) if c.get("kind") == "copyright"), "©")
        it.why.append("dated from © year (D-024)")
        it.checks.append(f"Cover should say '{ev}': confirm the © year matches the year this {d['fiscal_year']} "
                         f"document was tabled (not a stale template year).")
    elif d["date_source"] == "wayback_capture":
        b = 1
        it.why.append("Wayback-dated (upper bound)")
        if not any(c.startswith(("Stored date", "Text")) for c in it.checks):
            it.checks.append(f"Wayback first capture {_dmy(d['doc_date'])} is used as an upper bound: open the "
                             f"file and check it is '{title[:80]}' and that nothing in it is dated later.")

    # (c) parsing fallbacks
    c = 0.0
    if d["parse_status"] == "failed":
        c = 2
        it.why.append(f"parse failed: {parse.get('error')}")
        it.checks.append("Parse failed: does the file open, and does it contain text?")
    elif d["parse_status"] == "ocr":
        n_pages = parse.get("n_pages") or 1
        ocr_pages = parse.get("ocr_pages") or []
        c = len(ocr_pages) / n_pages
        if c >= 0.5:
            it.why.append(f"OCR on {len(ocr_pages)}/{n_pages} pages")
            it.checks.append(f"OCR text (p.{ocr_pages[0]}): is the first chunk readable English, not garbage?")
    if d["lang"] == "ta":
        it.why.append(f"detected Tamil (ratio {parse.get('tamil_ratio')}), not chunked")
        it.checks.append("Confirm the file is in Tamil (it is kept out of the evidence pool).")

    # (d) unmapped department or doubtful doc_type
    dd = 0
    known = set(cfg.sources.departments.values())
    listing = meta.get("listing") or {}
    if d["department"] and d["department"] not in known:
        dd = 1
        it.why.append(f"unmapped department {d['department']!r}")
        it.checks.append(f"Which department issued this? Stored as {d['department']!r}.")
    if d["doc_type"] == "governor_address" and d["department"] != "Public Department":
        dd = 1
        it.why.append(f"governor_address filed under {d['department']}")
        it.checks.append(f"Is this the Governor's address? (title '{title[:70]}')")
    if d["doc_type"] == "other" and listing.get("subtype", "").startswith("policy"):
        dd = 1
        it.why.append(f"doc_type other/{listing.get('subtype')}")
        it.checks.append(f"Is '{title[:70]}' an adopted state policy (or a draft, if subtype says so)?")

    # (e) chunk-count outliers relative to page count
    e = 0
    pages = parse.get("n_pages") or 0
    if d["lang"] == "en" and d["parse_status"] in ("ok", "ocr") and pages:
        ratio = it.n_chunks / pages
        lo, hi = chunk_ratio_bounds
        if ratio < lo or ratio > hi:
            e = 1
            it.why.append(f"{it.n_chunks} chunks for {pages} pages")
            it.checks.append(f"{it.n_chunks} chunks from {pages} pages is unusual: is the text complete "
                             f"(not just a cover or index)?")

    if d["doc_type"] == "go" and d["date_source"] == "listing":
        num = listing.get("identifiers", {})
        it.checks.insert(0, f"GO header should read {num.get('go_series', '?')} No.{num.get('go_number', '?')} "
                            f"dated {_dmy(d['doc_date'])}, {d['department']}.")
    it.score = (a, b, c, dd, e)


def chunk_ratio_bounds(items: list[Item]) -> tuple[float, float]:
    """Tukey fences (1.5 × IQR) on chunks per page over English parsed documents."""
    ratios = [it.n_chunks / it.meta["parse"]["n_pages"] for it in items
              if it.doc["lang"] == "en" and (it.meta.get("parse") or {}).get("n_pages")]
    if len(ratios) < 4:
        return 0.0, float("inf")
    q1, _, q3 = statistics.quantiles(ratios, n=4)
    return q1 - 1.5 * (q3 - q1), q3 + 1.5 * (q3 - q1)


def build(conn: sqlite3.Connection, cfg: Config) -> list[Item]:
    counts = {r["doc_id"]: r["n"] for r in db.query(conn, "SELECT doc_id, count(*) n FROM chunks GROUP BY doc_id")}
    items = []
    for r in db.query(conn, "SELECT * FROM documents WHERE local_path IS NOT NULL ORDER BY doc_id"):
        doc = dict(r)
        meta = read_sidecar(cfg.root / doc["local_path"])
        items.append(Item(doc, meta, counts.get(doc["doc_id"], 0), (meta.get("listing") or {}).get("source", "?")))
    bounds = chunk_ratio_bounds(items)
    for it in items:
        score_item(it, cfg, bounds)
    return items


def select(items: list[Item], max_items: int, per_source: int) -> list[Item]:
    ranked = sorted((it for it in items if any(it.score)), key=lambda it: (tuple(-s for s in it.score),
                                                                           it.doc["doc_id"]))
    out: list[Item] = []
    per: dict[str, int] = {}
    for it in ranked:
        if per.get(it.source, 0) < per_source:
            out.append(it)
            per[it.source] = per.get(it.source, 0) + 1
        if len(out) == max_items:
            break
    return out


def run_spotcheck() -> dict[str, Any]:
    cfg = get_config()
    s = cfg.settings.spotcheck
    conn = db.connect()
    chosen = select(build(conn, cfg), s.max_items, s.per_source)
    path = cfg.spotcheck_path("01")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        for it in chosen:
            d = it.doc
            w.writerow({
                "item_id": d["doc_id"],
                "why_flagged": f"[{it.source} · {d['doc_type']}] " + "; ".join(it.why),
                "what_to_check": f"'{(d['title'] or '')[:90]}' (stored date {d['doc_date'] or 'none'}). "
                                 + " ".join(it.checks),
                "path": d["local_path"] + (f" | {d['source_url']}" if d["source_url"] else ""),
                "verdict": "", "note": "",
            })
    conn.close()
    return {"rows": len(chosen), "below_minimum": len(chosen) < s.min_items, "path": str(path)}
