import csv
import datetime as dt

import pytest

from ept import db
from ept.corpus.catalogue import Catalogue, CatalogueItem, doc_id_for_url
from ept.corpus.leads import extract, run_leads
from fakes import FakeResponse, FakeSession, make_pdf


@pytest.mark.parametrize("text,series,no,year", [
    ("as per G.O.(Ms) No.45, Transport Department, dated 12.05.2021", "Ms", "45", "2021"),
    ("vide G.O. Ms. No. 132 dated 06.12.2022", "Ms", "132", "2022"),
    ("GO (D) No 1347 of 2021", "D", "1347", "2021"),
    ("G.O.(Rt) No.12", "Rt", "12", ""),
    ("G.O.(2D)No.100 dt. 08.11.2022", "2D", "100", "2022"),
])
def test_go_reference_variants(text, series, no, year):
    gos = [l for l in extract(text) if l["kind"] == "go"]
    assert [(l["go_series"], l["go_number"], l["go_year"]) for l in gos] == [(series, no, year)]


def test_acts_and_official_urls():
    leads = extract("Under the Tamil Nadu Town and Country Planning Act, 1971 and see "
                    "https://cms.tn.gov.in/cms_migrated/document/GO/tr_e_45_2021.pdf. Also https://www.cm.tn.gov.in.")
    kinds = sorted((l["kind"], l["text"]) for l in leads)
    assert ("act", "Tamil Nadu Town and Country Planning Act, 1971") in [(k, t.replace("The ", "")) for k, t in kinds]
    assert sum(k == "url" for k, _ in kinds) == 2


def test_resolution_and_tracker_lead_tag(conn, root):
    from ept.config import get_config

    gos = Catalogue("tn_gos")
    gos.add([CatalogueItem(url="https://cms.tn.gov.in/x/tr_e_45_2021.pdf", source="tn_gos", doc_type="go",
                           listing_date=dt.date(2021, 5, 12),
                           identifiers={"go_number": "45", "go_series": "Ms", "go_year": "2021"})])
    gos.save()
    page = (b"<html><body><p>Free bus travel: G.O.(Ms) No.45 dated 12.05.2021; also G.O.(Ms) No.77 dated "
            b"01.01.2022.</p><a href='https://cms.tn.gov.in/docs/scheme_note.pdf'>note</a>"
            b"<a href='https://www.cm.tn.gov.in/'>CM</a></body></html>")
    cfg = get_config()
    cfg.sources.trackers[:] = [{"name": "t", "url": "https://tracker.example/p", "term_id": "DMK-2021"}]
    import ept.corpus.leads as leads_mod
    session = FakeSession([("robots.txt", FakeResponse(404)),
                           ("tracker.example", FakeResponse(200, page, {"Content-Type": "text/html"})),
                           ("scheme_note.pdf", FakeResponse(200, make_pdf("note"), {"Content-Type": "application/pdf"})),
                           ("showNumPages", FakeResponse(200, b"1")), ("cdx/search", FakeResponse(200, b"[]"))])
    orig = leads_mod.build_clients
    leads_mod.build_clients = lambda c: orig(c, session=session, sleep=lambda s: None)
    try:
        out = run_leads()
    finally:
        leads_mod.build_clients = orig
    rows = {r["text"]: r for r in csv.DictReader((root / "data" / "interim" / "tracker_leads.csv").open())}
    go45 = next(r for t, r in rows.items() if "No.45" in t)
    assert go45["status"] == "resolved" and go45["resolved_doc_id"] == doc_id_for_url("https://cms.tn.gov.in/x/tr_e_45_2021.pdf")
    assert next(r for t, r in rows.items() if "No.77" in t)["status"] == "unresolved"
    fetched = next(r for r in rows.values() if r["kind"] == "url" and r["url"].endswith(".pdf"))
    assert fetched["status"] == "fetched"
    doc = db.get(conn, "documents", fetched["resolved_doc_id"])
    assert doc.discovery == "tracker_lead"
    assert next(r for r in rows.values() if "cm.tn.gov.in" in r["url"])["status"] == "not_a_document"
    assert out["trackers"] == 1 and all(r["term_id"] == "DMK-2021" for r in rows.values())
    # the tracker page itself is stored raw only, never as a document
    assert list((root / "data" / "raw" / "trackers").glob("*.html"))
    assert db.query(conn, "SELECT count(*) n FROM documents WHERE source_url LIKE '%tracker.example%'")[0]["n"] == 0


def test_unresolved_go_lead_triggers_targeted_listing_reread(conn, root):
    from ept.config import get_config
    from ept.corpus.catalogue import load_all
    from ept.corpus.crawl import build_clients
    from ept.corpus.fetch import Fetcher
    from ept.corpus.leads import _go_index, _YearRefresh, resolve
    from conftest import FIXTURES

    cfg = get_config()
    cfg.sources.departments.clear()
    cfg.sources.departments["11"] = "Health and Family Welfare Department"
    listing = (FIXTURES / "html" / "s2_hfw_2021.html").read_bytes()  # lists G.O (D) No.1347 of 2021
    session = FakeSession([("robots.txt", FakeResponse(404)),
                           ("go.php", FakeResponse(200, listing, {"Content-Type": "text/html"})),
                           ("hfw_e_1347_2021.pdf", FakeResponse(200, make_pdf("1347"), {"Content-Type": "application/pdf"})),
                           ("showNumPages", FakeResponse(200, b"1")), ("cdx/search", FakeResponse(200, b"[]"))])
    http, wayback = build_clients(cfg, session=session, sleep=lambda s: None)
    catalogues = load_all(cfg)
    fetcher = Fetcher(cfg, http, wayback, conn)
    lead = {"kind": "go", "text": "G.O.(D) No.1347 of 2021", "go_series": "D", "go_number": "1347",
            "go_year": "2021", "url": ""}
    status, doc_id = resolve(lead, catalogues, _go_index(catalogues), fetcher, cfg, _YearRefresh(fetcher, catalogues))
    assert status == "fetched" and db.get(conn, "documents", doc_id).discovery == "tracker_lead"
    unknown = {**lead, "go_number": "9999", "text": "G.O.(D) No.9999 of 2021"}
    assert resolve(unknown, catalogues, _go_index(catalogues), fetcher, cfg,
                   _YearRefresh(fetcher, catalogues))[0] == "unresolved"
