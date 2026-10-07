from ept import db
from ept.corpus.chunk import Paragraph, chunk_paragraphs, make_chunks, split_sentences

T, MIN, MAX = 400, 300, 500


def _para(n_words, page=1, word="w"):
    sentences = []
    for i in range(0, n_words, 10):
        k = min(10, n_words - i)
        sentences.append(" ".join([word] * (k - 1) + [word + "."]) if k > 0 else "")
    return Paragraph(" ".join(s.capitalize() for s in sentences), page)


def _check_bounds(chunks):
    for text, ps, pe, n in chunks[:-1]:
        assert MIN <= n <= MAX, n
    assert chunks[-1][3] <= MAX


def test_word_bounds_and_last_chunk_exception():
    chunks = chunk_paragraphs([_para(120, p) for p in range(1, 15)], T, MIN, MAX)
    _check_bounds(chunks)
    assert sum(c[3] for c in chunks) == 120 * 14


def test_page_ranges():
    chunks = chunk_paragraphs([_para(250, 1), _para(250, 2), _para(250, 3)], T, MIN, MAX)
    assert chunks[0][1] == 1 and chunks[0][2] == 2
    assert chunks[-1][2] == 3


def test_long_paragraph_split_at_sentences_never_mid_word():
    words = [f"word{i}" for i in range(1700)]
    text = " ".join(w + ("." if i % 25 == 24 else "") for i, w in enumerate(words))
    chunks = chunk_paragraphs([Paragraph(text, 1)], T, MIN, MAX)
    _check_bounds(chunks)
    rebuilt = " ".join(c[0] for c in chunks).replace(".", "").split()
    assert rebuilt == words  # nothing lost, no word cut


def test_giant_sentence_cut_between_words():
    chunks = chunk_paragraphs([Paragraph(" ".join(["x"] * 1200), 1)], T, MIN, MAX)
    _check_bounds(chunks)
    assert sum(c[3] for c in chunks) == 1200


def test_small_tail_merges_when_it_fits():
    chunks = chunk_paragraphs([_para(400, 1), _para(50, 2)], T, MIN, MAX)
    assert [c[3] for c in chunks] == [450]


def test_short_document_single_chunk():
    chunks = chunk_paragraphs([_para(40)], T, MIN, MAX)
    assert len(chunks) == 1 and chunks[0][3] == 40


def test_deterministic_ids():
    paras = [_para(300, p) for p in range(1, 5)]
    a = make_chunks("abcdef0123456789", paras, None, T, MIN, MAX)
    b = make_chunks("abcdef0123456789", paras, None, T, MIN, MAX)
    assert [c.chunk_id for c in a] == [f"abcdef0123456789-{i:04d}" for i in range(len(a))]
    assert a == b


def test_sentence_split_keeps_abbreviations():
    s = split_sentences("G.O.(Ms) No. 45 was issued. Rs. 500 crore was given to Dr. Rao. It ended.")
    assert s == ["G.O.(Ms) No. 45 was issued.", "Rs. 500 crore was given to Dr. Rao.", "It ended."]


def test_rechunk_replaces_only_that_document(conn, root, monkeypatch):
    from ept.config import get_config
    from ept.corpus import ocr
    from ept.corpus.parse import parse_document
    from helpers import register

    monkeypatch.setattr(ocr, "run_tesseract", lambda *a: "")
    a = register(conn, "pdf/text.pdf", url="https://x.tn.gov.in/a.pdf", listing_date="2021-05-12")
    b = register(conn, "pdf/text.pdf", url="https://x.tn.gov.in/b.pdf", listing_date="2021-05-13")
    cfg = get_config()
    import datetime as dt
    parse_document(conn, cfg, a, dt.date(2026, 10, 7))
    parse_document(conn, cfg, b, dt.date(2026, 10, 7))
    before_b = db.select_models(conn, "chunks", "doc_id = ?", (b.doc_id,))
    parse_document(conn, cfg, db.get(conn, "documents", a.doc_id), dt.date(2026, 10, 7))
    assert db.select_models(conn, "chunks", "doc_id = ?", (b.doc_id,)) == before_b
    n_a = len(db.select_models(conn, "chunks", "doc_id = ?", (a.doc_id,)))
    assert db.query(conn, "SELECT count(*) n FROM chunks")[0]["n"] == n_a + len(before_b)
