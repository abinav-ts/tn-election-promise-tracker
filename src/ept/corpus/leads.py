"""`ept leads`: GO references from third-party promise trackers (spec 01 §4.7, D-020).

Tracker pages are stored raw in data/raw/trackers/ and mined with deterministic regexes (no LLM)
for GO references, Act/Bill names with years and official *.tn.gov.in URLs. GO leads are resolved
against the GO catalogue; a lead pointing at an official PDF not yet in the corpus is fetched and
tagged `discovery=tracker_lead`. Tracker text (claims, verdicts) is never stored as a document,
chunked or shown to a judge.
"""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import re
from typing import Any, Optional
from urllib.parse import urlsplit

import pymupdf
from bs4 import BeautifulSoup

from ept import db
from ept.config import Config, get_config
from ept.corpus.catalogue import Catalogue, CatalogueItem, canonical_url, doc_id_for_url, load_all
from ept.corpus.crawl import build_clients
from ept.corpus.fetch import Fetcher
from ept.net import FetchError
from ept.runs import finish_run, progress, start_run
from ept.schema import Discovery

COLUMNS = ["lead_id", "term_id", "tracker", "kind", "text", "go_series", "go_number", "go_year", "url",
           "status", "resolved_doc_id"]

GO_REF = re.compile(
    r"G\.?\s*O\.?\s*\(?\s*(?P<series>\d?[A-Za-z]{1,3})\s*\)?\.?\s*No\.?\s*(?P<no>\d{1,4})"
    r"(?:[^\n]{0,60}?(?:dated|dt\.?)\s*(?P<date>\d{1,2}[./-]\d{1,2}[./-](?:19|20)\d{2}))?"
    r"(?:[^\n]{0,20}?(?P<year>(?:19|20)\d{2}))?",
    re.I,
)
_CAP = r"[A-Z][\w'()&.-]*"
ACT = re.compile(rf"\b(?:The\s+)?{_CAP}(?:\s+(?:(?:and|of|for|the|in|on|to|&)\s+)?{_CAP}){{0,14}}?\s+(?:Act|Bill),?\s+"
                 r"(?:19|20)\d{2}")
OFFICIAL_URL = re.compile(r"https?://(?:[\w-]+\.)*tn\.gov\.in(?:/[^\s\"'<>)\]]*)?", re.I)


def tracker_text(data: bytes, url: str) -> str:
    if data[:4] == b"%PDF":
        with pymupdf.open(stream=data, filetype="pdf") as doc:
            return "\n".join(p.get_text() for p in doc)
    text = data.decode("utf-8", errors="replace")
    if "<html" in text[:2000].lower():
        soup = BeautifulSoup(text, "lxml")
        for s in soup(["script", "style"]):
            s.decompose()
        hrefs = " ".join(a["href"] for a in soup.find_all("a", href=True))
        return soup.get_text("\n") + "\n" + hrefs
    return text  # JavaScript bundle or plain text


def extract(text: str) -> list[dict[str, str]]:
    out: dict[tuple, dict[str, str]] = {}
    for m in GO_REF.finditer(text):
        year = m.group("year") or (m.group("date")[-4:] if m.group("date") else "")
        series = {"ms": "Ms", "d": "D", "rt": "Rt"}.get(m.group("series").lower(), m.group("series"))
        lead = {"kind": "go", "text": " ".join(m.group(0).split())[:120], "go_series": series,
                "go_number": str(int(m.group("no"))), "go_year": year, "url": ""}
        out[("go", series, lead["go_number"], year)] = lead
    for m in ACT.finditer(text):
        name = " ".join(m.group(0).split())
        name = re.sub(r"^(?:\w+\s+){0,2}?[Tt]he\s+", "", name)  # "Under the Tamil Nadu ... Act" -> "Tamil Nadu ... Act"
        out[("act", name.lower())] = {"kind": "act", "text": name[:160], "go_series": "", "go_number": "",
                                       "go_year": name[-4:], "url": ""}
    for m in OFFICIAL_URL.finditer(text):
        url = m.group(0).rstrip(".,;")
        out[("url", canonical_url(url))] = {"kind": "url", "text": url[:200], "go_series": "", "go_number": "",
                                             "go_year": "", "url": canonical_url(url)}
    return list(out.values())


def _go_index(catalogues: dict[str, Catalogue]) -> dict[tuple, CatalogueItem]:
    idx: dict[tuple, CatalogueItem] = {}
    for i in catalogues.get("tn_gos", []):
        ids = i.identifiers
        if ids.get("go_number"):
            idx.setdefault((ids["go_number"], ids.get("go_year", "")), i)
            idx.setdefault((ids.get("go_series", ""), ids["go_number"], ids.get("go_year", "")), i)
    return idx


def _lookup(lead: dict[str, str], go_idx: dict[tuple, CatalogueItem]) -> Optional[CatalogueItem]:
    return go_idx.get((lead["go_series"], lead["go_number"], lead["go_year"])) \
        or go_idx.get((lead["go_number"], lead["go_year"]))


class _YearRefresh:
    """Targeted fetch for an unresolved GO lead (spec 01 §4.7): re-read that year's GO listings of all
    departments, bypassing the listing cache, once per year per run. Wayback can't be searched for a GO
    without its file name, so that step is not possible from a tracker reference."""

    def __init__(self, fetcher: Fetcher, catalogues: dict[str, Catalogue]):
        self.fetcher = fetcher
        self.catalogues = catalogues
        self.done: set[str] = set()

    def __call__(self, year: str) -> Optional[dict[tuple, CatalogueItem]]:
        if not year or year in self.done:
            return None
        self.done.add(year)
        from ept.corpus.sources.tn_gos import TnGos
        from ept.runs import Budget

        cfg = self.fetcher.cfg
        adapter = TnGos(cfg, self.fetcher.http, self.fetcher.wayback)
        catalogue = self.catalogues.setdefault("tn_gos", Catalogue("tn_gos", cfg))
        added = catalogue.add(adapter.catalogue(Budget(None), force=True, years=[int(year)]))
        catalogue.save()
        progress(f"leads: re-read {year} GO listings, {added} new GOs listed")
        return _go_index(self.catalogues)


def resolve(lead: dict[str, str], catalogues: dict[str, Catalogue], go_idx: dict[tuple, CatalogueItem],
            fetcher: Fetcher, cfg: Config, refresh: Optional[_YearRefresh] = None) -> tuple[str, str]:
    """(status, doc_id). Statuses: resolved, fetched, unresolved, not_a_document, noted."""
    if lead["kind"] == "act":
        return "noted", ""  # mapping Acts to documents needs promises (stage 04 gap check)
    if lead["kind"] == "go":
        hit = _lookup(lead, go_idx)
        if hit:
            return "resolved", hit.doc_id or doc_id_for_url(hit.url)
        fresh = refresh(lead["go_year"]) if refresh else None
        if fresh is not None:
            go_idx.update(fresh)
            hit = _lookup(lead, go_idx)
            if hit:  # listed since our crawl: fetch it, tagged as found through a tracker lead
                item = hit.model_copy(update={"discovery": Discovery.tracker_lead.value})
                result = fetcher.fetch(item)
                if result.status in ("downloaded", "exists", "duplicate"):
                    catalogues["tn_gos"].update(hit.url, status="downloaded", doc_id=result.doc_id)
                    catalogues["tn_gos"].save()
                    return "fetched", result.doc_id or ""
        return "unresolved", ""
    url = lead["url"]
    for c in catalogues.values():
        if c.get(url) is not None:
            item = c.get(url)
            return "resolved", item.doc_id or doc_id_for_url(item.url)
    if not urlsplit(url).path.lower().endswith(".pdf"):
        return "not_a_document", ""  # a site or scheme home page, not a dated document
    item = CatalogueItem(url=url, source="tracker_leads", doc_type="other", subtype="tracker_lead",
                         discovery=Discovery.tracker_lead.value, title=urlsplit(url).path.rsplit("/", 1)[-1])
    result = fetcher.fetch(item)
    if result.status in ("downloaded", "exists", "duplicate"):
        return "fetched", result.doc_id or ""
    return "unresolved", ""


def run_leads(limit: Optional[int] = None, force: bool = False) -> dict[str, Any]:
    cfg = get_config()
    run_id = start_run("leads", {"limit": limit, "force": force})
    http, wayback = build_clients(cfg)
    conn = db.connect()
    db.init_schema(conn)
    fetcher = Fetcher(cfg, http, wayback, conn)
    catalogues = load_all(cfg)
    go_idx = _go_index(catalogues)
    refresh = _YearRefresh(fetcher, catalogues)
    rows: list[dict[str, Any]] = []
    trackers = cfg.sources.trackers[:limit] if limit else cfg.sources.trackers
    failed = []
    try:
        for t in trackers:
            url = t["url"]
            raw = cfg.path("trackers_raw") / (hashlib.sha1(url.encode()).hexdigest() + (t.get("ext") or ".html"))
            if raw.exists() and not force:
                data = raw.read_bytes()
            else:
                try:
                    data, _ = http.get_bytes(url)
                except FetchError as e:
                    failed.append({"tracker": url, "error": e.reason})
                    progress(f"leads: could not fetch {url}: {e.reason}")
                    continue
                raw.parent.mkdir(parents=True, exist_ok=True)
                raw.write_bytes(data)
            found = extract(tracker_text(data, url))
            progress(f"leads: {t.get('name', url)} ({t['term_id']}): {len(found)} references")
            for lead in found:
                status, doc_id = resolve(lead, catalogues, go_idx, fetcher, cfg, refresh)
                lead_id = hashlib.sha1(f"{url}|{lead['kind']}|{lead['text']}".encode()).hexdigest()[:12]
                rows.append({"lead_id": lead_id, "term_id": t["term_id"], "tracker": url, **lead,
                             "status": status, "resolved_doc_id": doc_id})
        path = cfg.path("tracker_leads")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=COLUMNS)
            w.writeheader()
            w.writerows(rows)
    finally:
        conn.close()
    by_kind: dict[str, int] = {}
    for r in rows:
        k = f"{r['kind']}:{r['status']}"
        by_kind[k] = by_kind.get(k, 0) + 1
    out = {"trackers": len(trackers), "trackers_failed": len(failed), "leads": len(rows), **by_kind,
           "stopped": None}
    finish_run(run_id, {**out, "failed": failed})
    return out
