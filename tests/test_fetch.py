import json

import pytest

from ept import db
from ept.config import get_config
from ept.corpus.catalogue import Catalogue, CatalogueItem, doc_id_for_url
from ept.corpus.fetch import (
    CrawlStats, Fetcher, crawl_source, payload_error, read_sidecar, select,
)
from ept.corpus.wayback import Wayback, payload_digest
from ept.net import Http
from ept.runs import Budget
from fakes import ERROR_PAGE, PDF, FakeResponse, FakeSession

URL = "https://cms.tn.gov.in/cms_migrated/document/docfiles/hfw_e_pn_2019_20.pdf"
PDF_HDR = {"Content-Type": "application/pdf"}


def _cdx(rows):
    header = ["timestamp", "original", "statuscode", "digest", "mimetype", "length"]
    return FakeResponse(200, json.dumps([header] + rows).encode(), {"Content-Type": "application/json"})


def _item(url=URL, **kw):
    base = dict(url=url, source="tn_policy_notes", doc_type="policy_note", fiscal_year="2019-20",
                lang_hint="en", department="Health and Family Welfare Department", title="PN")
    base.update(kw)
    return CatalogueItem(**base)


def _fetcher(conn, routes):
    cfg = get_config()
    session = FakeSession([("robots.txt", FakeResponse(404))] + routes)
    http = Http(cfg, session=session, sleep=lambda s: None)
    return Fetcher(cfg, http, Wayback(http), conn), session


def test_payload_error_detects_html_instead_of_pdf():
    assert payload_error(ERROR_PAGE, URL) == "HTML error page instead of PDF"
    assert payload_error(b"", URL) == "empty response"
    assert payload_error(PDF, URL) is None
    assert payload_error(b"<html><body>x</body></html>", "https://www.tn.gov.in/scheme.php") is None


def test_live_download_registers_document(conn, root):
    f, _ = _fetcher(conn, [(URL, FakeResponse(200, PDF, PDF_HDR)), ("cdx", _cdx([]))])
    r = f.fetch(_item())
    assert r.status == "downloaded" and r.via == "live"
    doc = db.get(conn, "documents", doc_id_for_url(URL))
    assert doc.parse_status == "pending" and doc.discovery == "listing" and doc.archive_url is None
    raw = root / doc.local_path
    assert raw.read_bytes() == PDF and raw.parent.name == "policy_note"
    meta = read_sidecar(raw)
    assert meta["source_url"] == URL and meta["fetched_from"] == "live" and meta["wayback"]["checked"] is True


def test_live_error_page_falls_back_to_wayback(conn, root):
    digest = payload_digest(PDF)
    cdx = _cdx([["20200101000000", URL, "200", "OLDDIGEST", "application/pdf", "1"],
                ["20220101000000", URL, "200", digest, "application/pdf", "1"]])
    f, session = _fetcher(conn, [
        ("web.archive.org/web/20220101000000id_/", FakeResponse(200, PDF, PDF_HDR)),
        ("cdx/search", cdx),
        (URL, FakeResponse(200, ERROR_PAGE, {"Content-Type": "text/html"})),
    ])
    r = f.fetch(_item())
    assert r.status == "downloaded" and r.via == "wayback"
    doc = db.get(conn, "documents", r.doc_id)
    assert doc.source_url == URL  # always the original URL
    assert doc.archive_url == "https://web.archive.org/web/20220101000000id_/" + URL
    wb = read_sidecar(root / doc.local_path)["wayback"]
    assert wb["kept_first_capture"] == "20220101000000"  # first capture of the kept bytes
    assert wb["url_first_capture"] == "20200101000000"
    assert [v["digest"] for v in wb["superseded"]] == ["OLDDIGEST"]


def test_both_fail_definitively_marks_fetch_failed(conn):
    f, _ = _fetcher(conn, [("cdx/search", _cdx([])), (URL, FakeResponse(404))])
    r = f.fetch(_item())
    assert r.status == "fetch_failed" and "live: HTTP 404" in r.error and "no 200 capture" in r.error
    assert db.get(conn, "documents", r.doc_id) is None


def test_server_error_or_connection_problem_defers(conn):
    import requests

    f, _ = _fetcher(conn, [("cdx/search", _cdx([])), (URL, FakeResponse(500))])
    assert f.fetch(_item()).status == "deferred"  # 5xx may work next time

    def refuse(url):
        raise requests.ConnectionError("connection reset")

    f, _ = _fetcher(conn, [("cdx/search", _cdx([])), (URL, refuse)])
    assert f.fetch(_item()).status == "deferred"


def test_wayback_outage_leaves_lookup_pending(conn, root):
    f, _ = _fetcher(conn, [(URL, FakeResponse(200, PDF, PDF_HDR)), ("cdx/search", FakeResponse(503))])
    r = f.fetch(_item())
    assert r.status == "downloaded"
    meta = read_sidecar(root / db.get(conn, "documents", r.doc_id).local_path)
    assert meta["wayback"]["checked"] is False


def test_existing_raw_file_is_never_overwritten(conn, root):
    f, session = _fetcher(conn, [(URL, FakeResponse(200, PDF, PDF_HDR)), ("cdx", _cdx([]))])
    raw = f.raw_file("policy_note", doc_id_for_url(URL), ".pdf")
    raw.parent.mkdir(parents=True)
    raw.write_bytes(b"%PDF-1.4 earlier bytes")
    r = f.fetch(_item())
    assert r.status == "downloaded"
    assert raw.read_bytes() == b"%PDF-1.4 earlier bytes"
    assert URL not in session.calls  # registered from disk, not re-downloaded
    assert f.fetch(_item()).status == "exists"


def test_sha256_dedup_adds_alias(conn, root):
    other = URL.replace("hfw_e_pn", "hfw_e_pn_copy")
    f, _ = _fetcher(conn, [(other, FakeResponse(200, PDF, PDF_HDR)), (URL, FakeResponse(200, PDF, PDF_HDR)),
                           ("cdx", _cdx([]))])
    first = f.fetch(_item())
    second = f.fetch(_item(url=other))
    assert second.status == "duplicate" and second.doc_id == first.doc_id
    assert db.query(conn, "SELECT count(*) n FROM documents")[0]["n"] == 1
    assert read_sidecar(root / db.get(conn, "documents", first.doc_id).local_path)["aliases"] == [other]


class _OneShotAdapter:
    name = "test_source"

    def __init__(self, items):
        self.items = items

    def catalogue(self, budget, force=False):
        yield from self.items


def _items(n):
    return [_item(url=URL.replace("2019_20", f"x{i}")) for i in range(n)]


def test_limit_selects_the_same_items(conn, root):
    cat = Catalogue("tn_policy_notes")
    cat.add(_items(10))
    todo, n = select(cat, get_config(), "en", None, 3, False)
    assert n == 3 and len(todo) == 3
    assert [i.url for i in todo] == [i.url for i in select(cat, get_config(), "en", None, 3, False)[0]]


def test_limit_and_rerun_downloads_zero(conn, root):
    routes = [("cms.tn.gov.in", FakeResponse(200, b"%PDF-1.4 " + b"x", PDF_HDR)), ("cdx", _cdx([]))]
    f, _ = _fetcher(conn, routes)
    # distinct bytes per URL so dedup doesn't kick in
    f.http.session.routes[1] = ("cms.tn.gov.in", lambda u: FakeResponse(200, b"%PDF-1.4 " + u.encode(), PDF_HDR))
    adapter = _OneShotAdapter(_items(10))
    for expected in (3, 0):
        stats = CrawlStats()
        crawl_source(adapter, f, Catalogue("tn_policy_notes"), lang="en", download=True, term=None, limit=3,
                     force=False, budget=Budget(None), stats=stats)
        assert stats.downloaded == expected and stats.stopped is None


def test_time_budget_stops_cleanly_and_resumes(conn, root):
    f, _ = _fetcher(conn, [("cms.tn.gov.in", lambda u: FakeResponse(200, b"%PDF-1.4 " + u.encode(), PDF_HDR)),
                           ("cdx", _cdx([]))])
    adapter = _OneShotAdapter(_items(4))
    ticks = iter(range(100))
    budget = Budget(2.5, clock=lambda: next(ticks))  # expires after a couple of checks
    stats = CrawlStats()
    crawl_source(adapter, f, Catalogue("tn_policy_notes"), lang="en", download=True, term=None, limit=None,
                 force=False, budget=budget, stats=stats)
    assert stats.stopped == "time budget" and 0 < stats.downloaded < 4
    stats2 = CrawlStats()
    crawl_source(adapter, f, Catalogue("tn_policy_notes"), lang="en", download=True, term=None, limit=None,
                 force=False, budget=Budget(None), stats=stats2)
    assert stats2.stopped is None and stats.downloaded + stats2.downloaded == 4


def test_out_of_window_and_tamil_items_are_not_selected(conn, root):
    cat = Catalogue("tn_policy_notes")
    cat.add([_item(url=URL + "?a", fiscal_year="2014-15"), _item(url=URL + "?b", lang_hint="ta"),
             _item(url=URL + "?c")])
    todo, n = select(cat, get_config(), "en", None, None, False)
    assert [i.url for i in todo] == [URL + "?c"]
    assert [i.url for i in select(cat, get_config(), "en", "AIADMK-2016", None, False)[0]] == [URL + "?c"]
    assert select(cat, get_config(), "en", "DMK-2021", None, False)[0] == []  # FY 2019-20 ends before 2021-05-07


def test_wayback_outage_defers_instead_of_failing(conn, root):
    f, _ = _fetcher(conn, [("cdx/search", FakeResponse(503)), (URL, FakeResponse(404))])
    r = f.fetch(_item())
    assert r.status == "deferred" and "wayback unavailable" in r.error
    cat_ = Catalogue("tn_policy_notes")
    stats = CrawlStats()
    crawl_source(_OneShotAdapter([_item()]), f, cat_, lang="en", download=True, term=None, limit=None,
                 force=False, budget=Budget(None), stats=stats)
    assert stats.deferred == 1 and cat_.get(URL).status == "new"


def test_manual_drop_registers_with_manual_date(conn, root):
    import shutil

    from ept.corpus.catalogue import doc_id_for_manual
    from ept.corpus.parse import redate_all
    from ept.corpus.sources.manual import Manual
    from conftest import FIXTURES
    import datetime as dt

    cfg = get_config()
    mdir = cfg.path("manual_dir")
    mdir.mkdir(parents=True)
    shutil.copy(FIXTURES / "pdf" / "text.pdf", mdir / "ga_2016.pdf")
    cfg.path("manual_manifest").write_text(
        "filename,doc_type,department,title,doc_date,date_precision,lang,source_url,note\n"
        "ga_2016.pdf,governor_address,Public Department,Governor's Address June 2016,2016-06-01,month,en,"
        "https://example.org/ga.pdf,from assembly library\n"
        "missing.pdf,go,,,,,,,\n")
    f, session = _fetcher(conn, [])
    items = list(Manual(cfg, f.http, f.wayback).catalogue(Budget(None)))
    assert [i.status for i in items] == ["new", "excluded"]
    r = f.fetch(items[0])
    assert r.status == "downloaded" and r.doc_id == doc_id_for_manual("ga_2016.pdf")
    assert session.calls == []  # no network for manual files
    doc = db.get(conn, "documents", r.doc_id)
    assert doc.discovery == "manual" and doc.date_source == "manual" and doc.date_precision == "month"
    assert doc.source_url == "https://example.org/ga.pdf" and doc.local_path.startswith("data/raw/evidence/governor_address/")
    redate_all(conn, cfg, dt.date(2026, 10, 7))
    doc = db.get(conn, "documents", r.doc_id)
    assert doc.date_source == "manual" and doc.doc_date == dt.date(2016, 6, 1)


def test_breaker_trips_after_repeated_failures_and_recovers():
    from ept.net import Breaker

    now = [0.0]
    b = Breaker(threshold=3, cooldown_s=120, max_cooldown_s=1800, clock=lambda: now[0])
    b.failure("x"); b.failure("x")
    assert b.open_reason() is None  # two failures are not enough
    b.failure("x")
    assert b.open_reason() == "x"
    now[0] = 121
    assert b.open_reason() is None  # cooldown over: try again
    for _ in range(3):
        b.failure("y")
    assert b.open_reason() == "y" and b.cooldown == 480  # 240 now, doubles again next time
    now[0] = 121 + 241
    b.success()
    assert b.open_reason() is None and b.cooldown == 120


def test_one_connection_blip_does_not_poison_the_host(conn, root):
    import requests

    calls = {"n": 0}

    def flaky(url):
        calls["n"] += 1
        if calls["n"] == 1:
            raise requests.ConnectionError("blip")
        return FakeResponse(200, b"%PDF-1.4 " + url.encode(), PDF_HDR)

    f, _ = _fetcher(conn, [("cdx/search", _cdx([])), ("cms.tn.gov.in", flaky)])
    results = [f.fetch(i).status for i in _items(3)]
    assert results == ["downloaded"] * 3  # the blip is absorbed by the request retries


def test_items_wrongly_failed_by_an_outage_are_retried(conn, root):
    from ept.corpus.fetch import pending

    old_bug = _item().model_copy(update={"status": "fetch_failed", "fetch_error":
                                         "live: host unreachable earlier in this run (ConnectionError: ...)"})
    real_404 = _item().model_copy(update={"status": "fetch_failed", "fetch_error":
                                          "live: HTTP 404; wayback: no 200 capture"})
    assert pending(old_bug, force=False) and not pending(real_404, force=False) and pending(real_404, force=True)
