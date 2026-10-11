"""Fetch chain (live -> Wayback `id_` -> fetch_failed), registration, and the crawl loop.

Spec 01 §4.2–4.3. Raw files are immutable: an existing file is never rewritten,
and `--force` never re-downloads.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import logging
import sqlite3
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlsplit

from ept import db
from ept.config import Config
from ept.corpus import catalogue as cat
from ept.corpus.catalogue import MANUAL_PREFIX, Catalogue, CatalogueItem, doc_id_for_url
import pymupdf

from ept.corpus.wayback import Capture, Wayback, WaybackUnavailable, payload_digest
from ept.dates import fy_bounds
from ept.net import FetchError, Http, RobotsDisallowed, is_transient, is_transient_text
from ept.runs import Budget, eta, progress
from ept.schema import DatePrecision, DateSource, Document, Lang, ParseStatus

log = logging.getLogger(__name__)

HTML_EXTS = {".htm", ".html", ".php", ".asp", ".aspx", ".jsp", ""}


# --- payload checks ---------------------------------------------------------


def expected_ext(url: str) -> str:
    suffix = Path(urlsplit(url).path).suffix.lower()
    return ".html" if suffix in HTML_EXTS else suffix


def looks_like_html(data: bytes) -> bool:
    head = data[:2048].lstrip().lower()
    return head.startswith((b"<!doctype html", b"<html", b"<head", b"<?xml")) or b"<html" in head


PDF_TAIL_BYTES = 1024  # %%EOF must sit in the last KB, after trailing padding is stripped


def pdf_incomplete(data: bytes) -> Optional[str]:
    """Why PDF bytes look truncated or broken (D-030), or None. Trailing NUL/whitespace padding,
    which some servers append, is ignored."""
    if b"%%EOF" not in data.rstrip(b"\x00 \t\r\n\x0c")[-PDF_TAIL_BYTES:]:
        return f"truncated PDF: no %%EOF at the end ({len(data)} bytes)"
    try:
        with pymupdf.open(stream=data, filetype="pdf") as doc:
            if doc.page_count == 0:
                return "PDF has no pages"
    except Exception as e:  # pymupdf raises several types for broken files
        return f"PDF does not open: {type(e).__name__}"
    return None


def opens_with_pages(data: bytes) -> bool:
    try:
        with pymupdf.open(stream=data, filetype="pdf") as doc:
            return doc.page_count > 0
    except Exception:
        return False


def payload_error(data: bytes, url: str) -> Optional[str]:
    """Why a payload is not the complete document we asked for, or None if it looks right."""
    if not data:
        return "empty response"
    ext = expected_ext(url)
    if ext == ".pdf":
        if not data[:1024].lstrip().startswith(b"%PDF") and b"%PDF" not in data[:1024]:
            return "HTML error page instead of PDF" if looks_like_html(data) else "not a PDF"
        return pdf_incomplete(data)
    if ext == ".html" and not looks_like_html(data):
        return "not HTML"
    return None


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# --- sidecars ---------------------------------------------------------------


def sidecar_path(raw_file: Path) -> Path:
    return raw_file.with_name(raw_file.name.split(".", 1)[0] + ".meta.json")


def read_sidecar(raw_file: Path) -> dict[str, Any]:
    p = sidecar_path(raw_file)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def write_sidecar(raw_file: Path, meta: dict[str, Any]) -> None:
    p = sidecar_path(raw_file)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(meta, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    tmp.replace(p)


def update_sidecar(raw_file: Path, **fields: Any) -> dict[str, Any]:
    meta = read_sidecar(raw_file)
    meta.update(fields)
    write_sidecar(raw_file, meta)
    return meta


# --- fetcher ----------------------------------------------------------------


class Deferred(FetchError):
    """Not a definitive failure (connection problem, throttling, outage): stays pending for a later run."""


@dataclass
class FetchResult:
    status: str  # downloaded | exists | duplicate | fetch_failed | deferred
    doc_id: Optional[str] = None
    error: Optional[str] = None
    via: Optional[str] = None
    size: int = 0
    seconds: float = 0.0


@dataclass
class _Payload:
    data: bytes
    via: str  # live | wayback
    archive_url: Optional[str] = None
    attempts: list[str] = field(default_factory=list)
    rejected: list[dict[str, str]] = field(default_factory=list)  # incomplete Wayback captures skipped
    note: Optional[str] = None


class Fetcher:
    def __init__(self, cfg: Config, http: Http, wayback: Wayback, conn: sqlite3.Connection):
        self.cfg = cfg
        self.http = http
        self.wayback = wayback
        self.conn = conn

    def raw_file(self, doc_type: str, doc_id: str, ext: str) -> Path:
        return self.cfg.path("raw_evidence") / doc_type / f"{doc_id}{ext}"

    def rel(self, path: Path) -> str:
        return path.relative_to(self.cfg.root).as_posix()

    def _download(self, url: str) -> _Payload:
        """Live, then the latest Wayback capture. Raises FetchError only when both answered definitively
        (e.g. 404 and no capture); any connection problem, throttling or outage raises Deferred."""
        attempts: list[str] = []
        live_final = wayback_final = False
        try:
            data, headers = self.http.get_bytes(url)
            err = payload_error(data, url)
            if err is None:
                return _Payload(data, "live", attempts=attempts)
            # D-033: the server's own file lacks %%EOF, but all announced bytes arrived and it opens
            if (err.startswith("truncated PDF") and str(len(data)) == headers.get("Content-Length")
                    and opens_with_pages(data)):
                return _Payload(data, "live", attempts=attempts,
                                note="accepted without %%EOF: size matches Content-Length and it opens (D-033)")
            attempts.append(f"live: {err}")
            live_final = True
        except RobotsDisallowed:
            raise
        except FetchError as e:
            attempts.append(f"live: {e.reason}")
            live_final = not is_transient(e)
        rejected: list[dict[str, str]] = []
        try:
            caps = self.wayback.captures(url)
            if not caps:
                attempts.append("wayback: no 200 capture")
                wayback_final = True
            else:
                # D-018 keeps the newest version, but a truncated capture is not a newer version (D-030):
                # try distinct digests newest first and keep the first complete one.
                newest: dict[str, Capture] = {}
                for c in sorted(caps, key=lambda c: c.timestamp, reverse=True):
                    newest.setdefault(c.digest, c)
                tries = list(newest.values())[: self.cfg.settings.wayback.max_versions_tried]
                for cap in tries:
                    try:
                        data = self.wayback.fetch_raw(cap)
                    except FetchError as e:  # definitive for this capture (e.g. 404); try the next
                        attempts.append(f"wayback {cap.timestamp}: {e.reason}")
                        continue
                    err = payload_error(data, url)
                    if err is None:
                        return _Payload(data, "wayback", self.wayback.raw_url(cap.timestamp, cap.original),
                                        attempts, rejected)
                    attempts.append(f"wayback {cap.timestamp}: {err}")
                    rejected.append({"digest": cap.digest, "timestamp": cap.timestamp, "reason": err})
                attempts.append(f"wayback: none of the {len(tries)} newest versions is complete")
                wayback_final = True
        except WaybackUnavailable as e:  # outage, throttling or a download over the time limit: retry later
            attempts.append(f"wayback unavailable: {str(e)[:120]}")
        if live_final and wayback_final:
            raise FetchError(url, "; ".join(attempts))
        raise Deferred(url, "; ".join(attempts))

    def _duplicate_of(self, sha: str, doc_id: str) -> Optional[Document]:
        rows = db.query(self.conn, "SELECT * FROM documents WHERE sha256 = ? AND doc_id != ?", (sha, doc_id))
        return db.as_model("documents", rows[0]) if rows else None

    def fetch(self, item: CatalogueItem) -> FetchResult:
        doc_id = doc_id_for_url(item.url)
        raw = self.raw_file(item.doc_type, doc_id, expected_ext(item.url))
        existing = db.get(self.conn, "documents", doc_id)
        if existing is not None and existing.local_path and (self.cfg.root / existing.local_path).exists():
            return FetchResult("exists", doc_id)

        meta = read_sidecar(raw)
        manual = item.url.startswith(MANUAL_PREFIX)
        seconds = 0.0
        if manual:
            src = self.cfg.path("manual_dir") / item.url[len(MANUAL_PREFIX):]
            raw = self.raw_file(item.doc_type, doc_id, src.suffix.lower())
            meta = read_sidecar(raw)
            if not src.exists():
                return FetchResult(cat.FETCH_FAILED, doc_id, error=f"manual file missing: {src.name}")
            data, via, archive_url = src.read_bytes(), "manual", None
        else:
            if raw.exists() and payload_error(raw.read_bytes(), item.url):
                quarantine(self.cfg, raw, payload_error(raw.read_bytes(), item.url) or "")
            if raw.exists():  # file stored by an interrupted run: register without re-downloading
                data = raw.read_bytes()
                via = meta.get("fetched_from", "live")
                archive_url = meta.get("archive_url")
            else:
                started = time.monotonic()
                try:
                    payload = self._download(item.url)
                except Deferred as e:
                    return FetchResult("deferred", doc_id, error=e.reason, seconds=time.monotonic() - started)
                except FetchError as e:
                    return FetchResult(cat.FETCH_FAILED, doc_id, error=e.reason, seconds=time.monotonic() - started)
                data, via, archive_url = payload.data, payload.via, payload.archive_url
                meta = read_sidecar(raw)
                if payload.note:
                    meta["complete_check"] = {"size": len(data), "ok": True, "note": payload.note}
                if payload.rejected:
                    meta["wayback_rejected"] = payload.rejected
                seconds = time.monotonic() - started

        sha = sha256_bytes(data)
        dup = self._duplicate_of(sha, doc_id)
        if dup is not None:
            dup_file = self.cfg.root / dup.local_path
            aliases = read_sidecar(dup_file).get("aliases", [])
            if item.url not in aliases:
                update_sidecar(dup_file, aliases=aliases + [item.url])
            return FetchResult(cat.DUPLICATE, dup.doc_id, via=via, size=len(data), seconds=seconds)

        fetched_at = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
        if not raw.exists():
            raw.parent.mkdir(parents=True, exist_ok=True)
            tmp = raw.with_suffix(raw.suffix + ".part")
            tmp.write_bytes(data)
            tmp.replace(raw)
        meta.update({
            "doc_id": doc_id,
            "source_url": item.identifiers.get("source_url") if manual else item.url,
            "manual_path": item.url[len(MANUAL_PREFIX):] if manual else None,
            "archive_url": archive_url,
            "fetched_from": via,
            "fetched_at": meta.get("fetched_at") or fetched_at.isoformat(),
            "sha256": sha,
            "payload_digest": payload_digest(data),
            "listing": item.model_dump(mode="json", exclude={"status", "fetch_error", "doc_id"}),
            "aliases": meta.get("aliases", []),
        })
        meta.setdefault("wayback", {"checked": manual})  # manual files are dated by the manifest
        write_sidecar(raw, meta)

        self._register(item, doc_id, raw, sha, archive_url, fetched_at, item.listing_date)
        if not manual:
            self.wayback_lookup(raw)
        return FetchResult(cat.DOWNLOADED, doc_id, via=via, size=len(data), seconds=seconds)

    def _register(self, item: CatalogueItem, doc_id: str, raw: Path, sha: str, archive_url: Optional[str],
                  fetched_at: dt.datetime, listing_date: Optional[dt.date]) -> None:
        manual = item.url.startswith(MANUAL_PREFIX)
        precision = (item.identifiers.get("date_precision") or DatePrecision.day.value) if listing_date else None
        doc = Document(
            doc_id=doc_id,
            source_url=item.identifiers.get("source_url") if manual else item.url,
            archive_url=archive_url,
            local_path=self.rel(raw),
            doc_type=item.doc_type,
            department=item.department,
            title=item.title,
            lang=item.lang_hint or Lang.en,  # provisional; parse confirms (§4.3)
            doc_date=listing_date,
            date_precision=precision,
            date_source=(DateSource.manual if manual else DateSource.listing) if listing_date else DateSource.none,
            fiscal_year=item.fiscal_year,
            discovery=item.discovery,
            sha256=sha,
            fetched_at=fetched_at,
            parse_status=ParseStatus.pending,
        )
        db.upsert(self.conn, doc)

    def wayback_lookup(self, raw: Path) -> bool:
        """Store the URL's captures, versions and the first capture of the kept bytes (§4.3 step 5, D-018).

        Returns False if Wayback was unavailable (the sidecar stays `checked: false` for a later run).
        """
        meta = read_sidecar(raw)
        url = meta.get("source_url")
        if meta.get("manual_path") or not url:
            return True  # manual files are dated by the manifest
        try:
            caps = self.wayback.captures(url)
            legacy = [c for alias in self.wayback.legacy_aliases(url) for c in self.wayback.captures(alias)]
        except WaybackUnavailable as e:
            meta["wayback"] = {"checked": False, "error": str(e)[:300]}
            write_sidecar(raw, meta)
            return False
        kept_digest = meta.get("payload_digest")
        # first capture of the kept bytes, at this URL or at a legacy location of the same file (D-018)
        kept_first: Optional[Capture] = Wayback.first_of_digest(caps + legacy, kept_digest) if kept_digest else None
        # incomplete captures skipped at download time are not "newer versions" (D-030)
        rejected = {r["digest"] for r in meta.get("wayback_rejected", [])}
        versions = [v for v in Wayback.versions(caps) if v.digest not in rejected]
        meta["wayback"] = {
            "checked": True,
            "checked_at": dt.date.today().isoformat(),
            "n_captures": len(caps),
            "url_first_capture": caps[0].timestamp if caps else None,
            "kept_digest": kept_digest,
            "kept_first_capture": kept_first.timestamp if kept_first else None,
            "kept_first_capture_url": kept_first.original if kept_first else None,
            "legacy_captures": len(legacy),
            "versions": [v.__dict__ for v in versions],
            "superseded": [v.__dict__ for v in versions if v.digest != kept_digest],
            "incomplete_captures": meta.get("wayback_rejected", []),
        }
        write_sidecar(raw, meta)
        return True


# --- raw-file completeness (D-030) -------------------------------------------


def quarantine(cfg: Config, raw: Path, reason: str) -> Path:
    """Move an incomplete raw file and its sidecar to _quarantine/ (never deleted, never overwritten),
    so the next crawl can fetch a complete copy into the normal place."""
    dest_dir = cfg.path("quarantine") / raw.parent.name
    dest_dir.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = dest_dir / f"{raw.stem}.{stamp}{raw.suffix}"
    shutil.move(str(raw), dest)
    side = sidecar_path(raw)
    if side.exists():
        meta = json.loads(side.read_text(encoding="utf-8"))
        meta["quarantine"] = {"reason": reason, "moved_to": dest.relative_to(cfg.root).as_posix(), "at": stamp}
        (dest_dir / f"{raw.stem}.{stamp}.meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1),
                                                                encoding="utf-8")
        side.unlink()
    log.warning("quarantined %s: %s", raw.name, reason)
    return dest


def verify_raw(conn: sqlite3.Connection, cfg: Config, catalogues: dict[str, Catalogue]) -> list[dict[str, str]]:
    """Check every stored PDF once (result cached in its sidecar). Incomplete ones are quarantined, their
    document and chunks removed, and their catalogue item reset so the crawl fetches them again."""
    found = []
    for r in db.query(conn, "SELECT doc_id, local_path, source_url FROM documents WHERE local_path LIKE '%.pdf'"):
        raw = cfg.root / r["local_path"]
        if not raw.exists():
            continue
        meta = read_sidecar(raw)
        size = raw.stat().st_size
        if (meta.get("complete_check") or {}).get("size") == size:
            continue
        err = pdf_incomplete(raw.read_bytes())
        if err is None:
            meta["complete_check"] = {"size": size, "ok": True}
            write_sidecar(raw, meta)
            continue
        source = (meta.get("listing") or {}).get("source")
        url = (meta.get("listing") or {}).get("url") or r["source_url"]
        quarantine(cfg, raw, err)
        with conn:
            conn.execute("DELETE FROM chunks WHERE doc_id = ?", (r["doc_id"],))
            conn.execute("DELETE FROM documents WHERE doc_id = ?", (r["doc_id"],))
        catalogue = catalogues.get(source)
        if catalogue is not None and catalogue.get(url) is not None:
            catalogue.update(url, status=cat.NEW, doc_id=None, fetch_error=f"quarantined (retry): {err}")
            catalogue.save()
        found.append({"doc_id": r["doc_id"], "source": source or "?", "reason": err})
    return found


# --- crawl loop -------------------------------------------------------------


@dataclass
class CrawlStats:
    catalogued_new: int = 0
    in_scope: int = 0
    to_fetch: int = 0
    downloaded: int = 0
    exists: int = 0
    duplicate: int = 0
    fetch_failed: int = 0
    deferred: int = 0
    wayback_backfilled: int = 0
    stopped: Optional[str] = None  # None = done; "time budget"

    def as_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


def item_period(item: CatalogueItem) -> Optional[tuple[dt.date, dt.date]]:
    if item.listing_date:
        return item.listing_date, item.listing_date
    if item.fiscal_year:
        return fy_bounds(item.fiscal_year)
    return None


def in_range(item: CatalogueItem, start: dt.date, end: dt.date) -> bool:
    period = item_period(item)
    if period is None:
        return True  # unknown date: keep; dating happens at parse
    return period[0] <= end and period[1] >= start


def in_scope(item: CatalogueItem, cfg: Config, lang: str, term: Optional[str]) -> bool:
    """Catalogued, not excluded, requested language, inside the evidence window (and term, if given)."""
    if item.status == cat.EXCLUDED or item.doc_type is None:
        return False
    if (item.lang_hint or Lang.en) != lang:
        return False
    window = cfg.settings.evidence_window
    if not in_range(item, window.start, window.end_or_today()):
        return False
    if term:
        t = cfg.term(term)
        if not in_range(item, t.sworn_in, t.term_end or dt.date.today()):
            return False
    return True


def pending(item: CatalogueItem, force: bool) -> bool:
    """Not yet fetched. A fetch_failed item is retried with --force, or always if its stored error was
    transient (items wrongly marked failed by a temporary outage before the fix are retried this way)."""
    if item.status in (cat.DOWNLOADED, cat.DUPLICATE):
        return False
    if item.status == cat.FETCH_FAILED:
        return force or is_transient_text(item.fetch_error or "")
    return True


def sample_key(item: CatalogueItem) -> str:
    """Deterministic, well-spread order, so `--limit N` always means the same N items."""
    return hashlib.sha1(item.url.encode("utf-8")).hexdigest()


def select(catalogue: Catalogue, cfg: Config, lang: str, term: Optional[str], limit: Optional[int],
           force: bool) -> tuple[list[CatalogueItem], int]:
    """(items still to fetch, number in scope). `--limit N` = the first N in-scope items in sample order."""
    scope = sorted((i for i in catalogue if in_scope(i, cfg, lang, term)), key=sample_key)
    if limit is not None:
        scope = scope[:limit]
    return [i for i in scope if pending(i, force)], len(scope)


def backfill_wayback(fetcher: Fetcher, budget: Budget, stats: CrawlStats) -> None:
    """Retry Wayback lookups that failed earlier (e.g. during an Internet Archive outage)."""
    if fetcher.wayback.down:
        return
    rows = db.query(fetcher.conn, "SELECT local_path FROM documents WHERE local_path IS NOT NULL")
    for r in rows:
        if budget.expired() or fetcher.wayback.down:
            return
        raw = fetcher.cfg.root / r["local_path"]
        meta = read_sidecar(raw)
        if meta and not meta.get("wayback", {}).get("checked"):
            if fetcher.wayback_lookup(raw):
                stats.wayback_backfilled += 1


def crawl_source(adapter, fetcher: Fetcher, catalogue: Catalogue, *, lang: str, download: bool,
                 term: Optional[str], limit: Optional[int], force: bool, budget: Budget,
                 stats: CrawlStats) -> None:
    every = fetcher.cfg.settings.progress
    progress(f"{adapter.name}: reading listings")
    seen = 0
    try:
        for item in adapter.catalogue(budget, force=force):
            stats.catalogued_new += catalogue.add([item])
            seen += 1
            if seen % every.every_catalogued == 0:
                progress(f"{adapter.name}: {seen} listing items read")
    finally:
        catalogue.save()
    if budget.expired():
        stats.stopped = "time budget"
        return
    if not download:
        return
    todo, n_scope = select(catalogue, fetcher.cfg, lang, term, limit, force)
    stats.in_scope += n_scope
    stats.to_fetch += len(todo)
    progress(f"{adapter.name}: {seen} listing items, {n_scope} in scope, {len(todo)} to fetch")
    start = time.monotonic()
    counts = {"downloaded": 0, "duplicate": 0, "fetch_failed": 0, "deferred": 0, "exists": 0}
    try:
        for n, item in enumerate(todo):
            if n and n % every.every_items == 0:
                progress(f"{adapter.name}: {n}/{len(todo)} fetched ("
                         + ", ".join(f"{k} {v}" for k, v in counts.items() if v)
                         + f"{eta(n, len(todo), time.monotonic() - start)})")
            if budget.expired():
                stats.stopped = "time budget"
                return
            result = fetcher.fetch(item)
            setattr(stats, result.status, getattr(stats, result.status) + 1)
            counts[result.status] += 1
            note = "" if result.status == cat.DOWNLOADED else f" {result.status.upper()}"
            if result.error:
                note += f": {result.error[:100]}"
            progress(f"[{n + 1}/{len(todo)}] {adapter.name} {result.doc_id} {result.size / 2**20:.2f} MB "
                     f"{result.seconds:.0f}s{' via ' + result.via if result.via else ''}{note}")
            if result.status == "deferred":
                catalogue.update(item.url, fetch_error=result.error)  # stays pending for the next run
                continue
            status = cat.DOWNLOADED if result.status == "exists" else result.status
            catalogue.update(item.url, status=status, doc_id=result.doc_id, fetch_error=result.error)
            if n % 20 == 19:
                catalogue.save()
        if todo:
            progress(f"{adapter.name}: {len(todo)}/{len(todo)} fetched ("
                     + ", ".join(f"{k} {v}" for k, v in counts.items() if v) + ")")
    finally:
        catalogue.save()
