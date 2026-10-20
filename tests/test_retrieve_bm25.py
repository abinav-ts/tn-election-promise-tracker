"""Spec 04 §4.4 / §7: tokeniser, per-run BM25 on eligible chunks only, per-query RRF."""

import numpy as np

from retrieve_helpers import add_doc, build_mock_index, make_corpus


def test_tokenizer_case_stopwords_plurals():
    from ept.retrieve.tokenize import fold, tokenize

    assert tokenize("The Subsidies of BUSES and Taxes, classes; a b x 12") == ["subsidy", "bus", "tax", "class", "12"]
    assert tokenize("schemes Schools women's status campus thesis") == ["scheme", "school", "women", "status",
                                                                        "campus", "thesis"]
    assert tokenize("ＦＵＬＬ－ｗｉｄｔｈ") == ["full", "width"]  # NFKC
    assert fold("churches") == "church" and fold("dishes") == "dish" and fold("ties") == "tie"
    assert fold("glass") == "glass" and fold("bus") == "bus" and fold("gas") == "gas"


def test_tokenizer_fingerprint_changes_with_stopwords(monkeypatch):
    from ept.retrieve import tokenize as tok

    before = tok.fingerprint()
    monkeypatch.setattr(tok, "STOPWORDS", tok.STOPWORDS | {"scheme"})
    assert tok.fingerprint() != before


def test_top_positive_and_rrf():
    from ept.retrieve.bm25 import rrf_fuse, top_positive

    s = np.array([0.0, 2.0, 1.0, 2.0, -1.0])
    assert top_positive(s, 10).tolist() == [1, 3, 2]  # > 0 only, ties by position
    assert top_positive(s, 2).tolist() == [1, 3]
    fused = rrf_fuse([np.array([1, 2]), np.array([2, 3])], 60)
    assert [p for p, _ in fused] == [2, 1, 3]
    assert abs(fused[0][1] - (1 / 62 + 1 / 61)) < 1e-12


def test_run_bm25_matches_rank_bm25():
    from rank_bm25 import BM25Okapi

    from ept.config import Bm25Cfg
    from ept.retrieve.bm25 import RunBM25

    corpus = [["bus", "fare", "women"], ["school", "meal"], ["bus", "bus", "route"], []]
    c = Bm25Cfg(k1=1.5, b=0.75, epsilon=0.25, depth=100)
    ref = BM25Okapi(corpus, k1=1.5, b=0.75, epsilon=0.25).get_scores(["bus", "women"])
    assert np.allclose(RunBM25(corpus, c).scores(["bus", "women"]), ref)
    assert RunBM25([[], []], c).scores(["bus"]).tolist() == [0.0, 0.0]


def _scores(conn, run_id, cutoff):
    import json

    rows = conn.execute("SELECT indicator_id, chunk_id, scores FROM retrievals WHERE run_id = ? AND cutoff_date IS ?",
                        (run_id, cutoff)).fetchall()
    return {(r["indicator_id"], r["chunk_id"]): json.loads(r["scores"]).get("bm25_score") for r in rows}


def test_post_cutoff_chunks_leave_bm25_scores_unchanged(conn):
    from ept.retrieve.run import run_retrieve

    make_corpus(conn)
    build_mock_index(conn)
    first = run_retrieve(term="DMK-2021", cutoffs=["5"])
    before = _scores(conn, first["run_id"], "2021-10-07")
    assert any(v for v in before.values())
    # many later chunks full of the query words: they would change IDF and avgdl if they were in the index
    add_doc(conn, "e000000000000001", "go", "2023-01-05", "day", None, "G.O. bus women",
            tuple("free bus travel women bus fare " * 20 for _ in range(6)))
    build_mock_index(conn)
    second = run_retrieve(term="DMK-2021", cutoffs=["5"], force=True)
    assert second["run_id"] != first["run_id"]
    assert _scores(conn, second["run_id"], "2021-10-07") == before


def test_bm25_is_built_on_the_eligible_chunks_only(conn, monkeypatch):
    from ept.config import get_config
    from ept.retrieve import bm25, eligible as el, run

    make_corpus(conn)
    build_mock_index(conn)
    sizes = []
    real = bm25.RunBM25.__init__
    monkeypatch.setattr(bm25.RunBM25, "__init__", lambda self, corpus, c: sizes.append(len(corpus)) or
                        real(self, corpus, c))
    run.run_retrieve(term="DMK-2021")
    cfg = get_config()
    av = el.load_availability(conn, cfg)
    expected = [len(el.eligible_indices(av, c)) for c in el.term_cutoffs(cfg, "DMK-2021", el.snapshot_end(cfg, av))]
    assert sizes == expected and len(set(sizes)) > 1
