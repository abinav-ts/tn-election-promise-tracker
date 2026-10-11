"""`ept crawl`: run source adapters in the configured order (spec 01 §4.3)."""

from __future__ import annotations

from typing import Any, Optional

from ept import db
from ept.config import get_config
from ept.corpus.catalogue import Catalogue, load_all
from ept.corpus.fetch import CrawlStats, Fetcher, backfill_wayback, crawl_source, verify_raw
from ept.corpus.sources import ADAPTERS
from ept.corpus.wayback import Wayback
from ept.net import Http
from ept.runs import Budget, finish_run, progress, start_run


def build_clients(cfg=None, session=None, sleep=None) -> tuple[Http, Wayback]:
    cfg = cfg or get_config()
    http = Http(cfg, session=session) if sleep is None else Http(cfg, session=session, sleep=sleep)
    prefixes = tuple(p for s in cfg.sources.sources.values() for p in (s.get("wayback_prefixes") or []))
    legacy = {cur: (olds, list(s.get("wayback_legacy_suffixes") or [""]))
              for s in cfg.sources.sources.values() for cur, olds in (s.get("wayback_legacy") or {}).items()}
    return http, Wayback(http, prefixes, legacy)


def run_crawl(sources: Optional[list[str]] = None, lang: str = "en", download: Optional[bool] = None,
              term: Optional[str] = None, limit: Optional[int] = None, force: bool = False,
              time_budget: Optional[float] = None, session=None) -> dict[str, Any]:
    cfg = get_config()
    if download is None:
        download = lang == "en"  # Tamil defaults to catalogue-only (§4.6)
    names = sources or [n for n in cfg.sources.order if n in ADAPTERS]
    unknown = [n for n in names if n not in ADAPTERS]
    if unknown:
        raise SystemExit(f"unknown or not yet implemented source(s): {unknown}")
    budget = Budget(time_budget)
    run_id = start_run("crawl", {"sources": names, "lang": lang, "download": download, "term": term,
                                 "limit": limit, "force": force, "time_budget": time_budget})
    conn = db.connect()
    db.init_schema(conn)
    db.sync_terms(conn)
    http, wayback = build_clients(cfg, session)
    fetcher = Fetcher(cfg, http, wayback, conn)
    stats = CrawlStats()
    per_source: dict[str, Any] = {}
    status = "done"
    progress("checking stored PDFs for truncation (first run checks every file; later runs only new ones)")
    quarantined = verify_raw(conn, cfg, load_all(cfg))
    for q in quarantined:
        progress(f"quarantined {q['source']} {q['doc_id']}: {q['reason']}; it will be fetched again")
    per_source["quarantined"] = quarantined
    try:
        for name in names:
            before = dict(stats.as_dict())
            adapter = ADAPTERS[name](cfg, http, wayback)
            # --limit N = the first N in-scope items of each source (fetch.select)
            crawl_source(adapter, fetcher, Catalogue(name, cfg), lang=lang, download=download, term=term,
                         limit=limit, force=force, budget=budget, stats=stats)
            per_source[name] = {k: v - before[k] for k, v in stats.as_dict().items()
                                if isinstance(v, int) and v != before[k]}
            if stats.stopped:
                break
        if not stats.stopped and download:
            backfill_wayback(fetcher, budget, stats)
        if lang == "ta" and not stats.stopped:
            from ept.corpus.pairing import write_pairs

            per_source["tamil_pairing"] = write_pairs(cfg)
            progress(f"tamil pairing: {per_source['tamil_pairing']}")
        if wayback.down:
            per_source["wayback_unavailable"] = wayback.down
        if not stats.stopped and stats.deferred:
            stats.stopped = f"{stats.deferred} deferred: Wayback unavailable"
        if stats.stopped:
            status = f"stopped: {stats.stopped}"
    finally:
        out = stats.as_dict()
        out["sources"] = per_source
        finish_run(run_id, out, status=status)
        conn.close()
    return out
