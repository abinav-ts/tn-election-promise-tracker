"""Spec 04 §4.8 / §7: end to end on a fixture DB with the mock embedder."""

import hashlib
import json

import pytest

from retrieve_helpers import build_mock_index, make_corpus


@pytest.fixture
def corpus(conn):
    make_corpus(conn)
    build_mock_index(conn)
    return conn


def _rows(conn, run_id):
    return conn.execute("SELECT indicator_id, chunk_id, rank, cutoff_date, scores FROM retrievals WHERE run_id = ? "
                        "ORDER BY indicator_id, cutoff_date, rank", (run_id,)).fetchall()


def _stage01_hash(conn):
    h = hashlib.sha256()
    for table in ("documents", "chunks"):
        for r in conn.execute(f"SELECT * FROM {table} ORDER BY 1"):
            h.update(repr(tuple(r)).encode())
    return h.hexdigest()


def test_index_skipped_when_current_and_rebuilt_with_force(corpus):
    from ept.config import get_config
    from ept.retrieve.dense import build_index, read_manifest

    cfg = get_config()
    m = read_manifest(cfg)
    assert m["n"] == corpus.execute("SELECT count(*) FROM chunks").fetchone()[0] and m["revision"] == "mock"
    assert build_index(corpus, cfg)["written"] == 0
    assert build_index(corpus, cfg, force=True)["written"] == m["n"]
    timed = build_index(corpus, cfg, limit=5)
    assert timed["timed_chunks"] == 5 and timed["written"] == 0


def test_full_run_rows_resume_force_and_report(corpus):
    from ept.config import get_config
    from ept.retrieve import eligible as el
    from ept.retrieve.report import run_report
    from ept.retrieve.run import latest_run, run_retrieve

    cfg = get_config()
    before = _stage01_hash(corpus)
    first = run_retrieve()
    assert first["complete"] and first["written"] == 7 * 3 + 7 * 3 + 1  # AIADMK 3 indicators, DMK 3, TVK 1 (m5 only)
    rows = _rows(corpus, first["run_id"])
    by_pair = {}
    for r in rows:
        by_pair.setdefault((r["indicator_id"], r["cutoff_date"]), []).append(r)
    assert len(by_pair) == 43
    av = {c.chunk_id: c for c in el.load_availability(corpus, cfg)}
    doc_types = {r["doc_id"]: r["doc_type"] for r in corpus.execute("SELECT doc_id, doc_type FROM documents")}
    for (iid, cd), rs in by_pair.items():
        assert [r["rank"] for r in rs] == list(range(1, len(rs) + 1)) and 1 <= len(rs) <= 5
        docs = [av[r["chunk_id"]].doc_id for r in rs]
        assert max(docs.count(d) for d in docs) <= 2
    assert el.check_retrievals(corpus, cfg)["violations"] == 0
    # a full-term (null cutoff) row is not duplicated by a resume; same fingerprint -> 0 writes
    again = run_retrieve()
    assert again["run_id"] == first["run_id"] and again["resumed"] and again["written"] == 0
    assert len(_rows(corpus, first["run_id"])) == len(rows)
    # --force: a new run with identical ranks
    forced = run_retrieve(force=True)
    assert forced["run_id"] != first["run_id"]
    strip = lambda rs: [(r["indicator_id"], r["chunk_id"], r["rank"], r["cutoff_date"]) for r in rs]  # noqa: E731
    assert strip(_rows(corpus, forced["run_id"])) == strip(rows)
    meta = latest_run(cfg)
    assert meta["run_id"] == forced["run_id"] and meta["complete"] and meta["fingerprint"]["hash"]
    assert len(meta["term_cutoffs"]) == 15
    out = run_report()
    assert out["leakage_violations"] == 0 and out["pairs"] == 43 and out["structure"] == {}
    data = json.loads(cfg.path("retrieval_json").read_text())
    assert len(data["cutoffs"]) == 15 and data["fy_bound_effect"]["totals"] == {"tightened": 1, "newly_dated": 1}
    assert "Leakage line (this run): 0 violations" in cfg.path("retrieval_md").read_text().replace("**", "")
    assert _stage01_hash(corpus) == before


def test_resume_after_partial_write_and_delete_then_insert(corpus):
    from ept.retrieve.run import run_retrieve

    first = run_retrieve(term="DMK-2021", cutoffs=["full"], limit=1)
    assert first["written"] == 1 and not first["complete"]
    # a stray duplicate of the full-term pair must be replaced, not kept, on the next write of that pair
    n_before = corpus.execute("SELECT count(*) FROM retrievals WHERE cutoff_date IS NULL").fetchone()[0]
    second = run_retrieve(term="DMK-2021", cutoffs=["full"])
    assert second["run_id"] == first["run_id"] and second["written"] == 2 and second["skipped"] == 1
    n_after = corpus.execute("SELECT count(*) FROM retrievals WHERE cutoff_date IS NULL AND indicator_id = "
                             "'DMK-2021-0001-I1'").fetchone()[0]
    assert n_after == n_before


def test_write_pair_replaces_null_cutoff_rows(corpus):
    from ept.retrieve import eligible as el
    from ept.retrieve.fuse import Candidate
    from ept.retrieve.run import write_pair
    from retrieve_helpers import add_promise

    cut = el.full_term(__import__("ept.config", fromlist=["get_config"]).get_config().term("DMK-2021"))
    cid = corpus.execute("SELECT chunk_id FROM chunks LIMIT 1").fetchone()[0]
    c = Candidate(pos=0, chunk_id=cid, doc_id="x", is_go=False, dense_cos=0.1, dense_rank=1, rrf=0.1)
    with corpus:
        write_pair(corpus, "r1", "DMK-2021-0001-I1", cut, [c])
    with corpus:
        write_pair(corpus, "r1", "DMK-2021-0001-I1", cut, [c])
    assert corpus.execute("SELECT count(*) FROM retrievals WHERE run_id = 'r1'").fetchone()[0] == 1


def test_limit_takes_first_indicators(corpus):
    from ept.retrieve.run import run_retrieve

    out = run_retrieve(term="AIADMK-2016", limit=1, cutoffs=["12"])
    ids = {r[0] for r in corpus.execute("SELECT DISTINCT indicator_id FROM retrievals WHERE run_id = ?",
                                        (out["run_id"],))}
    assert ids == {"AIADMK-2016-0001-I1"}


def test_changed_index_needs_reindex(corpus):
    from ept.retrieve.dense import IndexMissing
    from ept.retrieve.run import run_retrieve
    from retrieve_helpers import add_doc

    add_doc(corpus, "f000000000000001", "go", "2022-01-01", "day", None, "new", ("bus fare",))
    with pytest.raises(IndexMissing):
        run_retrieve(term="DMK-2021")


def test_empty_eligible_set_stops(conn):
    from ept.retrieve.run import EmptyEligibleSet, run_retrieve
    from retrieve_helpers import add_doc, add_promise

    add_doc(conn, "d000000000000001", "go", "2025-06-01", "day", None, "late", ("bus fare women",))
    add_promise(conn, "DMK-2021-0001", "Provide free bus travel for women.", [["bus fare", "women bus"]])
    build_mock_index(conn)
    with pytest.raises(EmptyEligibleSet):
        run_retrieve(term="DMK-2021", cutoffs=["5"])
