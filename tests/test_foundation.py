import datetime as dt
import json
import socket

import pytest

from ept import db, schema
from ept.config import get_config, load_config
from ept.runs import RUN_ID_RE, finish_run, make_run_id, start_run


def test_network_blocked():
    with pytest.raises(Exception):
        socket.create_connection(("example.com", 80))


def test_config_loads_and_root_override(root):
    cfg = get_config()
    assert cfg.root == root
    assert cfg.path("db") == root / "data" / "ept.sqlite"
    assert [t.term_id for t in cfg.settings.terms] == ["AIADMK-2016", "DMK-2021", "TVK-2026"]
    assert cfg.term("DMK-2021").sworn_in == dt.date(2021, 5, 7)
    assert cfg.term("AIADMK-2016").term_end == dt.date(2021, 5, 6)
    assert cfg.term("TVK-2026").term_end is None
    assert cfg.settings.evidence_window.start == dt.date(2016, 5, 1)
    assert cfg.settings.chunk.min_words == 300 and cfg.settings.chunk.max_words == 500
    assert cfg.settings.tamil.include_in_evidence is False


def test_config_rejects_unknown_keys(root):
    p = root / "config" / "settings.yaml"
    p.write_text(p.read_text() + "\nsurprise: 1\n")
    with pytest.raises(Exception):
        load_config(root)


def _values(enum):
    return {e.value for e in enum}


def test_enums_match_global_spec():
    assert _values(schema.DocType) == {
        "manifesto", "policy_note", "budget_speech", "governor_address", "go",
        "cag_report", "scheme_page", "news", "other",
    }
    assert _values(schema.Lang) == {"en", "ta"}
    assert _values(schema.DatePrecision) == {"day", "month", "year"}
    assert _values(schema.DateSource) == {"listing", "document_text", "filename", "wayback_capture", "manual", "none"}
    assert _values(schema.Discovery) == {"listing", "wayback_cdx", "tracker_lead", "manual"}
    assert _values(schema.ParseStatus) == {"pending", "ok", "ocr", "failed"}
    assert _values(schema.TermRole) == {"train", "backtest", "project"}
    assert _values(schema.JudgeSource) == {"bulk", "strong", "human"}
    assert _values(schema.Specificity) == {"specific", "vague"}
    assert _values(schema.Status) == {
        "fulfilled", "partial", "diluted", "in_progress", "not_started", "blocked_external", "unverifiable",
    }


def test_table_fields_match_global_spec():
    expected = {
        "terms": "term_id party manifesto_year sworn_in term_end role",
        "documents": "doc_id source_url archive_url local_path doc_type department title lang doc_date "
        "date_precision date_source fiscal_year discovery sha256 fetched_at parse_status",
        "chunks": "chunk_id doc_id seq text page_start page_end doc_date n_words",
        "promises": "promise_id term_id text source_text source_lang section page parent_group sector "
        "promise_type specificity cost_band union_dependent continues_existing headline covariates_version",
        "indicators": "indicator_id promise_id text is_self search_queries",
        "retrievals": "indicator_id chunk_id rank scores cutoff_date run_id",
        "verdicts": "promise_id run_id cutoff_date status realisation_date date_precision cited_chunk_ids "
        "rationale confidence needs_review judge_source judge_model prompt_version",
        "indicator_verdicts": "indicator_id run_id cutoff_date judging_key status realisation_date date_precision "
        "date_chunk_id cited_chunk_ids quotes rationale confidence needs_review review_reasons judge_source "
        "judge_model prompt_version",
    }
    assert set(schema.TABLES) == set(expected)
    for name, fields in expected.items():
        assert list(schema.TABLES[name].model.model_fields) == fields.split()
    assert list(schema.GoldLabel.model_fields) == (
        "promise_id status realisation_date date_precision evidence in_corpus notes labelled_at".split()
    )


def test_init_schema_idempotent(conn):
    db.init_schema(conn)
    db.init_schema(conn)
    names = {r["name"] for r in db.query(conn, "SELECT name FROM sqlite_master WHERE type='table'")}
    assert set(schema.TABLES) <= names
    assert len(db.query(conn, "SELECT * FROM terms")) == 3


def _samples():
    doc = schema.Document(
        doc_id="0123456789abcdef", source_url="https://x/y.pdf", doc_type="go", lang="en",
        doc_date=dt.date(2021, 6, 1), date_precision="day", date_source="listing", fiscal_year="2021-22",
        discovery="listing", sha256="ab" * 32, fetched_at=dt.datetime(2026, 10, 7, 12, 0, 0),
    )
    promise = schema.Promise(
        promise_id="DMK-2021-0001", term_id="DMK-2021", text="t", source_text="s", source_lang="ta"
    )
    return [
        schema.Term(term_id="X-2000", party="X", manifesto_year=2000, sworn_in=dt.date(2000, 1, 1), role="train"),
        doc,
        schema.Chunk(chunk_id="0123456789abcdef-0000", doc_id=doc.doc_id, seq=0, text="hello", n_words=1,
                     doc_date=doc.doc_date, page_start=1, page_end=2),
        promise,
        schema.Indicator(indicator_id="DMK-2021-0001-I1", promise_id=promise.promise_id, text="i", is_self=True,
                         search_queries=["a", "b"]),
        schema.Retrieval(indicator_id="DMK-2021-0001-I1", chunk_id="0123456789abcdef-0000", rank=1,
                         scores={"bm25": 1.5}, run_id="retrieve-20261007T000000Z"),
        schema.Verdict(promise_id=promise.promise_id, run_id="judge-20261007T000000Z", status="fulfilled",
                       realisation_date=dt.date(2021, 6, 1), date_precision="day",
                       cited_chunk_ids=["0123456789abcdef-0000"], rationale="r", confidence=0.8,
                       judge_source="bulk"),
        schema.IndicatorVerdict(indicator_id=f"{promise.promise_id}-I1", run_id="judge-20261007T000000Z",
                                judging_key="k" * 64, status="fulfilled", realisation_date=dt.date(2021, 6, 1),
                                date_precision="day", date_chunk_id="0123456789abcdef-0000",
                                cited_chunk_ids=["0123456789abcdef-0000"], quotes={"0123456789abcdef-0000": "q"},
                                rationale="r", confidence=0.8, review_reasons=["retried"], judge_source="bulk"),
    ]


def test_upsert_round_trip_every_table(conn):
    samples = _samples()
    covered = {schema.table_for(type(m)).name for m in samples}
    assert covered == set(schema.TABLES)
    for m in samples:
        db.upsert(conn, m)
        db.upsert(conn, m)  # idempotent
        spec = schema.table_for(type(m))
        pk = tuple(getattr(m, c) for c in spec.pk)
        assert db.get(conn, spec.name, pk) == m
        assert db.query(conn, f"SELECT count(*) AS n FROM {spec.name}")[0]["n"] >= 1
    # composite keys with NULL cutoff stay unique
    assert db.query(conn, "SELECT count(*) AS n FROM verdicts")[0]["n"] == 1
    assert db.query(conn, "SELECT count(*) AS n FROM retrievals")[0]["n"] == 1


def test_upsert_updates(conn):
    doc = _samples()[1]
    db.upsert(conn, doc)
    db.upsert(conn, doc.model_copy(update={"parse_status": "ok"}))
    assert db.get(conn, "documents", doc.doc_id).parse_status == "ok"


def test_verdict_rationale_limit():
    with pytest.raises(Exception):
        schema.Verdict(promise_id="p", run_id="r", status="fulfilled", confidence=0.5, judge_source="bulk",
                       rationale=" ".join(["w"] * 81))


def test_run_id_format_and_metadata(root):
    rid = make_run_id("crawl", dt.datetime(2026, 10, 7, 1, 2, 3))
    assert rid == "crawl-20261007T010203Z"
    assert RUN_ID_RE.match(rid)
    rid = start_run("crawl", {"limit": 5})
    assert RUN_ID_RE.match(rid)
    meta = finish_run(rid, {"downloaded": 5})
    saved = json.loads((root / "reports" / "runs" / f"{rid}.json").read_text())
    assert saved == json.loads(json.dumps(meta, default=str))
    assert saved["status"] == "done" and saved["counts"] == {"downloaded": 5}
    assert "settings" in saved["config"]
