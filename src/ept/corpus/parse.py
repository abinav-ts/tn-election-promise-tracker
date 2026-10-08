"""`ept parse`: extract text, check language, date, and chunk (spec 01 §4.4–4.5).

Re-dating runs over every document on each parse run, because a Wayback lookup
that was pending at download time can arrive later; chunks follow their document's date.
"""

from __future__ import annotations

import csv
import datetime as dt
import logging
import sqlite3
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

import pymupdf
from bs4 import BeautifulSoup

from ept import db
from ept.config import Config, get_config
from ept.corpus import datefind, lang as langmod, ocr
from ept.corpus.chunk import Paragraph, clean_block, make_chunks
from ept.corpus.fetch import read_sidecar, write_sidecar
from ept.dates import fy_bounds
from ept.runs import Budget, eta, finish_run, progress, start_run
from ept.schema import DocType, Document, Lang, ParseStatus

log = logging.getLogger(__name__)
pymupdf.TOOLS.mupdf_display_errors(False)

DEFAULT_STRIP = ["nav", "header", "footer", "script", "style", "noscript", "form", "iframe"]
REVIEW_COLUMNS = ["doc_id", "doc_type", "department", "title", "fiscal_year", "doc_date", "date_precision",
                  "date_source", "reasons", "candidates", "source_url", "local_path"]


@dataclass
class Extracted:
    pages: list[list[str]] = field(default_factory=list)  # paragraphs per page
    ocr_pages: list[int] = field(default_factory=list)  # 1-based pages whose text came from OCR
    error: Optional[str] = None
    notes: list[str] = field(default_factory=list)

    @property
    def page_texts(self) -> list[str]:
        return ["\n\n".join(p) for p in self.pages]

    @property
    def n_chars(self) -> int:
        return sum(len(t) for t in self.page_texts)


# --- extraction -------------------------------------------------------------


def extract_pdf(path: Path, cfg: Config) -> Extracted:
    out = Extracted()
    p = cfg.settings.parse
    try:
        doc = pymupdf.open(path)
    except Exception as e:  # pymupdf raises several types for corrupt files
        out.error = f"cannot open PDF: {type(e).__name__}: {e}"[:300]
        return out
    with doc:
        if doc.needs_pass and not doc.authenticate(""):
            out.error = "encrypted PDF"
            return out
        if doc.page_count == 0:
            out.error = "PDF has no pages"
            return out
        for i, page in enumerate(doc, start=1):
            try:
                blocks = page.get_text("blocks", sort=True)
            except Exception as e:
                out.notes.append(f"page {i}: text extraction failed: {e}")
                blocks = []
            paras = [c for b in blocks if b[6] == 0 for c in [clean_block(b[4])] if c]
            if sum(len(x) for x in paras) < p.ocr_min_chars_per_page:
                try:
                    text = ocr.ocr_page(page, p.ocr_lang, p.ocr_dpi, p.ocr_timeout_s)
                except (ocr.OcrUnavailable, OSError, Exception) as e:  # keep what we have
                    out.notes.append(f"page {i}: OCR failed: {str(e)[:120]}")
                else:
                    ocr_paras = [c for block in text.split("\n\n") for c in [clean_block(block)] if c]
                    if sum(len(x) for x in ocr_paras) > sum(len(x) for x in paras):
                        paras = ocr_paras
                        out.ocr_pages.append(i)
            out.pages.append(paras)
    if out.n_chars == 0:
        out.error = "no text (even after OCR)"
    return out


def extract_html(path: Path, main_selector: Optional[str], strip: list[str],
                 row_selector: Optional[str] = None) -> Extracted:
    out = Extracted()
    raw = path.read_bytes()
    soup = BeautifulSoup(raw, "lxml")
    for sel in DEFAULT_STRIP + strip:
        for el in soup.select(sel):
            el.decompose()
    root = soup.select_one(main_selector) if main_selector else None
    root = root or soup.body or soup
    rows = root.select(row_selector) if row_selector else []
    if rows:  # one paragraph per table row / labelled field: "Label : value"
        paras = [t for r in rows for t in [" ".join(r.get_text(" ", strip=True).split())] if t]
    else:
        lines = [" ".join(line.split()) for line in root.get_text("\n").split("\n")]
        paras = [line for line in lines if line]
    out.pages.append(paras)
    if out.n_chars == 0:
        out.error = "no text in HTML main content"
    return out


# --- per-document -----------------------------------------------------------


@dataclass
class ParseOutcome:
    doc_id: str
    status: str
    lang: str
    n_chunks: int
    ocr_pages: int
    error: Optional[str] = None


def _source_cfg(cfg: Config, meta: dict[str, Any]):
    source = (meta.get("listing") or {}).get("source")
    return cfg.sources.sources.get(source) if source else None


def text_dating(ext: Extracted, cfg: Config, today: dt.date, use_text: bool = True) -> dict[str, Any]:
    """Issue-date and © candidates from the front matter (unless the source disables text dating),
    plus the latest date mentioned anywhere (for the anachronism check)."""
    front = "\n\n".join(ext.page_texts[: cfg.settings.parse.front_matter_pages])
    issue = datefind.issue_date_from_text(front) if use_text else None
    copyright = datefind.copyright_year(front) if use_text else None
    return {
        "text_candidate": asdict(issue) if issue else None,
        "copyright_candidate": asdict(copyright) if copyright else None,
        **mentions("\n\n".join(ext.page_texts), today),
    }


def _found(f: Optional[datefind.Found]) -> Optional[dict[str, Any]]:
    return {"date": f.date.isoformat(), "precision": f.precision, "text": f.text} if f else None


def mentions(text: str, today: dt.date) -> dict[str, Any]:
    """Latest date in the text: narrowed for the anachronism flag, unnarrowed for the © leak guard (D-028)."""
    return {
        "latest_mention": _found(datefind.latest_mention(text, today, narrow=True)),
        "latest_mention_any": _found(datefind.latest_mention(text, today)),
        "mention_rule": datefind.MENTION_RULE,
    }


def refresh_mentions(meta: dict[str, Any], cfg: Config, today: dt.date) -> None:
    """Documents parsed under an older mention rule: recompute from the saved text (no OCR)."""
    dating = meta.get("dating")
    text_path = (meta.get("parse") or {}).get("text_path")
    if not dating or dating.get("mention_rule") == datefind.MENTION_RULE or not text_path:
        return
    path = cfg.root / text_path
    if path.exists():
        dating.update(mentions(path.read_text(encoding="utf-8").replace("\f", "\n\n"), today))


def parse_document(conn: sqlite3.Connection, cfg: Config, doc: Document, today: dt.date) -> ParseOutcome:
    raw = cfg.root / doc.local_path
    meta = read_sidecar(raw)
    if doc.local_path.lower().endswith(".pdf"):
        ext = extract_pdf(raw, cfg)
    else:
        scfg = _source_cfg(cfg, meta)
        ext = extract_html(raw, scfg.get("html_main") if scfg else None,
                           list(scfg.get("html_strip") or []) if scfg else [],
                           scfg.get("html_rows") if scfg else None)

    hint = (meta.get("listing") or {}).get("lang_hint")
    full_text = "\n\n".join(ext.page_texts)
    s = cfg.settings
    lang = Lang(langmod.detect(full_text, s.lang.tamil_ratio, s.lang.legacy_garbage_ratio,
                               Lang(hint) if hint else None) if not ext.error else (hint or doc.lang))
    status = ParseStatus.failed if ext.error else (ParseStatus.ocr if ext.ocr_pages else ParseStatus.ok)

    text_path = cfg.path("text_dir") / f"{doc.doc_id}.txt"
    if not ext.error:
        text_path.parent.mkdir(parents=True, exist_ok=True)
        text_path.write_text("\f".join(ext.page_texts), encoding="utf-8")

    meta["parse"] = {
        "status": status.value, "error": ext.error, "notes": ext.notes[:20], "n_pages": len(ext.pages),
        "ocr_pages": ext.ocr_pages, "n_chars": ext.n_chars, "lang": lang.value,
        "tamil_ratio": round(langmod.tamil_ratio(full_text), 3),
        "text_path": text_path.relative_to(cfg.root).as_posix() if not ext.error else None,
        "parsed_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
    }
    scfg = _source_cfg(cfg, meta)
    use_text = scfg.get("text_dating", True) if scfg else True
    meta.setdefault("dating", {}).update(text_dating(ext, cfg, today, use_text) if not ext.error else {})
    write_sidecar(raw, meta)

    doc = doc.model_copy(update={"parse_status": status.value, "lang": lang.value})
    doc = apply_dating(doc, meta, cfg, today)
    chunks = []
    if chunkable(doc, cfg):
        paragraphs = [Paragraph(t, page) for page, paras in enumerate(ext.pages, start=1) for t in paras]
        c = s.chunk
        chunks = make_chunks(doc.doc_id, paragraphs, doc.doc_date, c.target_words, c.min_words, c.max_words)
    with conn:
        db.upsert(conn, doc, commit=False)
        conn.execute("DELETE FROM chunks WHERE doc_id = ?", (doc.doc_id,))
        for ch in chunks:
            db.upsert(conn, ch, commit=False)
    return ParseOutcome(doc.doc_id, status.value, lang.value, len(chunks), len(ext.ocr_pages), ext.error)


def chunkable(doc: Document, cfg: Config) -> bool:
    if doc.parse_status not in (ParseStatus.ok.value, ParseStatus.ocr.value):
        return False
    if doc.doc_type == DocType.manifesto.value:  # manifestos never enter the evidence pool (§5)
        return False
    if doc.lang == Lang.ta.value and not cfg.settings.tamil.include_in_evidence:
        return False
    return True


# --- dating -----------------------------------------------------------------


def candidates_for(meta: dict[str, Any], today: dt.date) -> list[datefind.Candidate]:
    cands = []
    listing = meta.get("listing") or {}
    c = datefind.listing_candidate(listing)
    if c:
        cands.append(c)
    for key in ("text_candidate", "copyright_candidate"):
        found = (meta.get("dating") or {}).get(key)
        if found:
            cands.append(datefind.Candidate(**found))
    c = datefind.date_from_filename(meta.get("source_url") or "", today)
    if c:
        cands.append(c)
    c = datefind.wayback_candidate(meta.get("wayback") or {})
    if c:
        cands.append(c)
    return cands


def apply_dating(doc: Document, meta: dict[str, Any], cfg: Config, today: dt.date) -> Document:
    """Resolve doc_date from the sidecar's candidates; store the result back in the sidecar."""
    refresh_mentions(meta, cfg, today)
    cands = candidates_for(meta, today)
    dating = meta.get("dating") or {}

    def as_cand(m: Optional[dict[str, Any]]) -> Optional[datefind.Candidate]:
        return datefind.Candidate("text_mention", m["date"], m["precision"], m["text"]) if m else None

    latest_c = as_cand(dating.get("latest_mention"))
    # sidecars from before D-028 have no "_any": their latest_mention is the unnarrowed one
    any_c = as_cand(dating.get("latest_mention_any", dating.get("latest_mention")))
    extra = []
    if not (meta.get("wayback") or {}).get("checked"):
        extra.append("wayback lookup pending")
    s = cfg.settings
    dating = datefind.resolve(
        cands, fiscal_year=doc.fiscal_year, latest_mentioned=latest_c, latest_any=any_c,
        window_start=s.evidence_window.start,
        today=today, conflict_days=s.date.conflict_days, fy_slack_months=s.date.fy_slack_months,
        extra_reasons=extra,
    )
    meta.setdefault("dating", {})
    meta["dating"]["candidates"] = [asdict(c) for c in cands]
    meta["dating"]["resolved"] = dating.as_dict()
    meta["dating"]["needs_review"] = datefind.needs_review(dating)
    write_sidecar(cfg.root / doc.local_path, meta)
    return doc.model_copy(update={"doc_date": dating.doc_date, "date_precision": dating.precision,
                                  "date_source": dating.source})


def redate_all(conn: sqlite3.Connection, cfg: Config, today: dt.date) -> tuple[int, int]:
    """Re-resolve every document's date, keep chunks in sync, and rewrite date_review.csv.

    Returns (documents whose date changed, rows in the review sheet)."""
    changed = 0
    rows = []
    for doc in db.select_models(conn, "documents", "local_path IS NOT NULL"):
        raw = cfg.root / doc.local_path
        meta = read_sidecar(raw)
        if not meta:
            continue
        new = apply_dating(doc, meta, cfg, today)
        if (new.doc_date, new.date_precision, new.date_source) != (doc.doc_date, doc.date_precision, doc.date_source):
            with conn:
                db.upsert(conn, new, commit=False)
                conn.execute("UPDATE chunks SET doc_date = ? WHERE doc_id = ?",
                             (new.doc_date.isoformat() if new.doc_date else None, new.doc_id))
            changed += 1
        dating = meta["dating"]
        if dating["needs_review"]:
            resolved = dating["resolved"]
            rows.append({
                "doc_id": new.doc_id, "doc_type": new.doc_type, "department": new.department, "title": new.title,
                "fiscal_year": new.fiscal_year, "doc_date": resolved["doc_date"],
                "date_precision": resolved["precision"], "date_source": resolved["source"],
                "reasons": "; ".join(resolved["reasons"]),
                "candidates": "; ".join(f"{c.get('kind') or c['source']}={c['date']}" for c in dating["candidates"]),
                "source_url": new.source_url, "local_path": new.local_path,
            })
    path = cfg.path("date_review")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=REVIEW_COLUMNS)
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: (r["doc_type"], r["doc_id"])))
    return changed, len(rows)


# --- run --------------------------------------------------------------------


def in_term(doc: Document, cfg: Config, term: Optional[str]) -> bool:
    if not term:
        return True
    t = cfg.term(term)
    end = t.term_end or dt.date.today()
    if doc.doc_date:
        return t.sworn_in <= doc.doc_date <= end
    if doc.fiscal_year:
        lo, hi = fy_bounds(doc.fiscal_year)
        return lo <= end and hi >= t.sworn_in
    return True


def run_parse(term: Optional[str] = None, limit: Optional[int] = None, force: bool = False,
              time_budget: Optional[float] = None) -> dict[str, Any]:
    cfg = get_config()
    budget = Budget(time_budget)
    today = dt.date.today()
    run_id = start_run("parse", {"term": term, "limit": limit, "force": force, "time_budget": time_budget})
    conn = db.connect()
    db.init_schema(conn)
    stats: dict[str, Any] = {"in_scope": 0, "to_parse": 0, "ok": 0, "ocr": 0, "failed": 0, "tamil": 0,
                             "chunks_written": 0, "redated": 0, "date_review_rows": 0, "stopped": None}
    try:
        # `--limit N` = the first N documents (doc_id order), so a re-run touches the same documents
        docs = [d for d in db.select_models(conn, "documents", "local_path IS NOT NULL ORDER BY doc_id")
                if in_term(d, cfg, term)]
        if limit is not None:
            docs = docs[:limit]
        stats["in_scope"] = len(docs)
        todo = [d for d in docs if force or d.parse_status == ParseStatus.pending.value]
        stats["to_parse"] = len(todo)
        every = cfg.settings.progress.every_items
        progress(f"parse: {len(docs)} documents in scope, {len(todo)} to parse")
        start = time.monotonic()
        for n, doc in enumerate(todo):
            if n and n % every == 0:
                progress(f"parse: {n}/{len(todo)} (ok {stats['ok']}, ocr {stats['ocr']}, failed {stats['failed']}"
                         f"{eta(n, len(todo), time.monotonic() - start)})")
            if budget.expired():
                stats["stopped"] = "time budget"
                break
            out = parse_document(conn, cfg, doc, today)
            stats[out.status] += 1
            stats["chunks_written"] += out.n_chunks
            if out.lang == Lang.ta.value:
                stats["tamil"] += 1
        progress("parse: re-dating all documents and writing date_review.csv")
        stats["redated"], stats["date_review_rows"] = redate_all(conn, cfg, today)
    finally:
        finish_run(run_id, stats, status=f"stopped: {stats['stopped']}" if stats["stopped"] else "done")
        conn.close()
    return stats
