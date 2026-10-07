import datetime as dt

import pytest

from ept import db
from ept.config import get_config
from ept.corpus import ocr
from ept.corpus.fetch import read_sidecar
from ept.corpus.parse import extract_html, parse_document, run_parse
from helpers import register

TODAY = dt.date(2026, 10, 7)


@pytest.fixture
def fake_ocr(monkeypatch):
    calls = []

    def fake(png, lang, timeout_s):
        calls.append(lang)
        return "OCR TEXT from a scanned page. " * 30

    monkeypatch.setattr(ocr, "run_tesseract", fake)
    return calls


def test_text_pdf_parses_ok_and_chunks(conn, root, fake_ocr):
    doc = register(conn, "pdf/text.pdf", url="https://x.tn.gov.in/go/tr_e_45_2021.pdf", listing_date="2021-05-12")
    out = parse_document(conn, get_config(), doc, TODAY)
    assert out.status == "ok" and out.error is None and fake_ocr == []
    stored = db.get(conn, "documents", doc.doc_id)
    assert stored.parse_status == "ok" and stored.lang == "en"
    assert stored.doc_date == dt.date(2021, 5, 12) and stored.date_source == "listing"
    chunks = db.select_models(conn, "chunks", "doc_id = ?", (doc.doc_id,))
    assert chunks and all(c.doc_date == stored.doc_date for c in chunks)
    assert chunks[0].page_start == 1
    text = (root / "data" / "interim" / "text" / f"{doc.doc_id}.txt").read_text()
    assert text.count("\f") == 1  # two pages
    meta = read_sidecar(root / doc.local_path)
    assert meta["dating"]["text_candidate"]["date"] == "2021-05-12"


def test_image_only_pdf_goes_through_ocr(conn, root, fake_ocr):
    doc = register(conn, "pdf/image_only.pdf", url="https://x.tn.gov.in/go/scan.pdf")
    out = parse_document(conn, get_config(), doc, TODAY)
    assert out.status == "ocr" and fake_ocr == ["eng"]
    assert db.get(conn, "documents", doc.doc_id).parse_status == "ocr"
    assert read_sidecar(root / doc.local_path)["parse"]["ocr_pages"] == [1]


def test_ocr_unavailable_leaves_failed(conn, root, monkeypatch):
    def broken(*a, **k):
        raise ocr.OcrUnavailable("no tesseract")

    monkeypatch.setattr(ocr, "run_tesseract", broken)
    doc = register(conn, "pdf/image_only.pdf", url="https://x.tn.gov.in/go/scan2.pdf")
    out = parse_document(conn, get_config(), doc, TODAY)
    assert out.status == "failed" and "no text" in out.error


def test_corrupt_pdf_fails_with_reason(conn, root, fake_ocr):
    doc = register(conn, "pdf/corrupt.pdf", url="https://x.tn.gov.in/go/bad.pdf")
    out = parse_document(conn, get_config(), doc, TODAY)
    assert out.status == "failed"
    assert read_sidecar(root / doc.local_path)["parse"]["error"]
    assert db.query(conn, "SELECT count(*) n FROM chunks")[0]["n"] == 0


def test_html_main_content_extraction(tmp_path):
    page = tmp_path / "p.html"
    page.write_text("<html><body><header>Site header</header><nav>Menu Home About</nav>"
                    "<div id='main'><h1>Scheme title</h1><p>Eligibility: women aged 21.</p></div>"
                    "<div class='side'>Sidebar</div><footer>Footer text</footer>"
                    "<script>var x=1;</script></body></html>")
    ext = extract_html(page, "#main", [])
    assert ext.pages == [["Scheme title", "Eligibility: women aged 21."]]
    ext = extract_html(page, None, [".side"])
    assert "Sidebar" not in ext.page_texts[0] and "Menu" not in ext.page_texts[0]
    assert "Footer" not in ext.page_texts[0] and "var x" not in ext.page_texts[0]


def test_run_parse_is_idempotent(conn, root, fake_ocr):
    register(conn, "pdf/text.pdf", url="https://x.tn.gov.in/go/a.pdf", listing_date="2021-05-12")
    first = run_parse(limit=5)
    second = run_parse(limit=5)
    assert first["ok"] == 1 and first["chunks_written"] >= 1
    assert second["to_parse"] == 0 and second["chunks_written"] == 0
    third = run_parse(limit=5, force=True)
    assert third["chunks_written"] == first["chunks_written"]
    assert db.query(conn, "SELECT count(*) n FROM chunks")[0]["n"] == first["chunks_written"]
