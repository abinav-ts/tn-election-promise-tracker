"""Stage 01 leakage guards (spec 01 §5)."""

import datetime as dt

import pytest

from ept import db
from ept.config import get_config
from ept.corpus import ocr
from ept.corpus.parse import parse_document, redate_all
from helpers import register

TODAY = dt.date(2026, 10, 7)


@pytest.fixture(autouse=True)
def _no_ocr(monkeypatch):
    monkeypatch.setattr(ocr, "run_tesseract", lambda *a: "")


def _n_chunks(conn, doc_id):
    return db.query(conn, "SELECT count(*) n FROM chunks WHERE doc_id = ?", (doc_id,))[0]["n"]


def test_manifesto_never_chunked(conn, root):
    doc = register(conn, "pdf/text.pdf", url="file://manifesto.pdf", doc_type="manifesto")
    out = parse_document(conn, get_config(), doc, TODAY)
    assert out.status == "ok" and _n_chunks(conn, doc.doc_id) == 0


def test_tamil_documents_not_chunked(conn, root, monkeypatch):
    from ept.corpus import parse

    monkeypatch.setattr(parse.langmod, "detect", lambda *a, **k: "ta")
    doc = register(conn, "pdf/text.pdf", url="https://x/hfw_t_pn_2021_22.pdf", lang_hint="ta")
    parse_document(conn, get_config(), doc, TODAY)
    assert db.get(conn, "documents", doc.doc_id).lang == "ta"
    assert _n_chunks(conn, doc.doc_id) == 0


def test_no_doc_date_from_fiscal_year_only(conn, root):
    doc = register(conn, "pdf/text.pdf", url="https://x/pn_2019_20.pdf", fiscal_year="2019-20", doc_type="policy_note")
    # text.pdf mentions "Dated: 12.05.2021"; drop the text candidate to test FY-only
    cfg = get_config()
    parse_document(conn, cfg, doc, TODAY)
    from ept.corpus.fetch import read_sidecar, write_sidecar
    raw = root / doc.local_path
    meta = read_sidecar(raw)
    meta["dating"]["text_candidate"] = None
    write_sidecar(raw, meta)
    redate_all(conn, cfg, TODAY)
    stored = db.get(conn, "documents", doc.doc_id)
    assert stored.doc_date is None and stored.date_source == "none" and stored.fiscal_year == "2019-20"
    assert all(r["doc_date"] is None for r in db.query(conn, "SELECT doc_date FROM chunks WHERE doc_id = ?",
                                                         (doc.doc_id,)))


def test_wayback_dated_docs_are_flagged(conn, root):
    import csv

    doc = register(conn, "pdf/image_only.pdf", url="https://x/pn_2019_20.pdf", fiscal_year="2019-20",
                   wayback={"checked": True, "kept_first_capture": "20191222061649"}, doc_type="policy_note")
    redate_all(conn, get_config(), TODAY)
    stored = db.get(conn, "documents", doc.doc_id)
    assert stored.date_source == "wayback_capture" and stored.doc_date == dt.date(2019, 12, 22)
    rows = list(csv.DictReader((root / "data" / "interim" / "date_review.csv").open()))
    assert [r["doc_id"] for r in rows] == [doc.doc_id]
    assert "Wayback first capture" in rows[0]["reasons"]


def test_chunk_dates_follow_redating(conn, root):
    doc = register(conn, "pdf/text.pdf", url="https://x/a.pdf", fiscal_year="2021-22",
                   wayback={"checked": False}, doc_type="policy_note")
    cfg = get_config()
    parse_document(conn, cfg, doc, TODAY)
    from ept.corpus.fetch import read_sidecar, write_sidecar
    raw = root / doc.local_path
    meta = read_sidecar(raw)
    meta["dating"]["text_candidate"] = None
    meta["wayback"] = {"checked": True, "kept_first_capture": "20211124044737"}
    write_sidecar(raw, meta)
    redate_all(conn, cfg, TODAY)
    dates = {r["doc_date"] for r in db.query(conn, "SELECT doc_date FROM chunks WHERE doc_id = ?", (doc.doc_id,))}
    assert dates == {"2021-11-24"}
