"""Spec 04 §5 / §7 leakage checks: no gold/verdict/manifesto/tracker reads, no LLM, the DB-wide check works."""

from conftest import REPO

PKG = REPO / "src" / "ept" / "retrieve"


def test_stage_reads_no_gold_verdicts_units_or_trackers():
    forbidden = ["data/gold", "gold_labels", "FROM verdicts", "judgments", "manifesto_interim", "read_units",
                 "units.jsonl", "trackers_raw", "tracker_leads", "manifestos_raw", "frozen/promises"]
    for path in PKG.glob("*.py"):
        src = path.read_text(encoding="utf-8")
        for f in forbidden:
            assert f not in src, (path.name, f)


def test_stage_makes_no_llm_call():
    for path in PKG.glob("*.py"):
        src = path.read_text(encoding="utf-8")
        assert "ept.llm" not in src and "LLMClient" not in src and "genai" not in src, path.name


def test_queries_used_exactly_as_frozen(conn, monkeypatch):
    """The run tokenises each stored search query and nothing else (no expansion, D-079)."""
    import json

    from ept.retrieve import run, tokenize
    from retrieve_helpers import build_mock_index, make_corpus

    make_corpus(conn)
    build_mock_index(conn)
    seen = []
    real = tokenize.tokenize
    monkeypatch.setattr(run.tok, "tokenize", lambda t: seen.append(t) or real(t))
    run.run_retrieve(term="TVK-2026")
    stored = json.loads(conn.execute("SELECT search_queries FROM indicators WHERE indicator_id = "
                                     "'TVK-2026-0001-I1'").fetchone()[0])
    assert seen == stored


def test_db_wide_check_catches_planted_violation(conn):
    from ept import db
    from ept.config import get_config
    from ept.retrieve.eligible import check_retrievals
    from ept.retrieve.run import run_retrieve
    from ept.schema import Retrieval
    from retrieve_helpers import build_mock_index, make_corpus

    make_corpus(conn)
    build_mock_index(conn)
    out = run_retrieve(term="DMK-2021", cutoffs=["5"])
    assert check_retrievals(conn, get_config())["violations"] == 0
    late = conn.execute("SELECT chunk_id FROM chunks WHERE doc_id = 'd000000000000006'").fetchone()[0]  # 2025 GO
    db.upsert(conn, Retrieval(indicator_id="DMK-2021-0001-I1", chunk_id=late, rank=9, cutoff_date="2021-10-07",
                              run_id=out["run_id"]))
    res = check_retrievals(conn, get_config(), out["run_id"])
    assert res["violations"] == 1 and res["examples"][0]["chunk_id"] == late


def test_mock_embedder_never_loads_a_model(conn):
    import sys

    from ept.retrieve.run import run_retrieve
    from retrieve_helpers import build_mock_index, make_corpus

    make_corpus(conn)
    build_mock_index(conn)
    run_retrieve(term="TVK-2026")
    assert "sentence_transformers" not in sys.modules and "torch" not in sys.modules
