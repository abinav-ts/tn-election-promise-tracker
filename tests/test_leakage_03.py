"""Spec 03 §5/§7 leakage checks: invented few-shots, no party/term name in the template, no corpus access."""

import pytest

from conftest import REPO
from test_leakage_02 import _manifesto_texts, _runs

PROMPT = REPO / "prompts" / "classify_promises.md"


def test_few_shot_examples_share_no_8_word_run_with_manifestos():
    texts = _manifesto_texts()
    units = list((REPO / "data" / "interim" / "manifestos").glob("*/units.jsonl"))
    texts += [u.read_text(encoding="utf-8") for u in units]
    if not texts:
        pytest.skip("no local manifesto text (run `ept extract pages`)")
    manifesto_runs = set().union(*(_runs(t) for t in texts))
    overlap = _runs(PROMPT.read_text(encoding="utf-8")) & manifesto_runs
    assert not overlap, sorted(overlap)[:3]


def test_prompt_template_names_no_party_or_term():
    from ept.config import load_config

    body = PROMPT.read_text(encoding="utf-8").lower()
    for t in load_config(REPO).settings.terms:
        for name in (t.party, t.term_id, str(t.manifesto_year)):
            assert name.lower() not in body, name
    for tamil in ("கழக", "திமுக", "அதிமுக", "தவெக"):
        assert tamil not in body


def test_stage_reads_no_corpus_tracker_or_evidence_path():
    forbidden = ["raw_evidence", "text_dir", "trackers_raw", "tracker_leads", "catalogue_dir", "FROM chunks",
                 "FROM documents", "FROM retrievals", "FROM verdicts", "data/gold", "judgments"]
    for path in (REPO / "src" / "ept" / "classify").glob("*.py"):
        src = path.read_text(encoding="utf-8")
        for f in forbidden:
            assert f not in src, (path.name, f)


def test_c3_runs_on_every_promise_indicator_query_and_override(root, conn, monkeypatch):
    import csv as _csv
    import json as _json

    from classify_helpers import FakeLLM, install, setup_term
    from ept.classify import checks, run

    setup_term(root, conn)
    seen = []
    real = checks.check_c3
    monkeypatch.setattr(checks, "check_c3", lambda r, s, lim: seen.append((s.text, len(checks.checked_strings(r, s.text))))
                        or real(r, s, lim))
    strings = []
    real_unseen = checks.unseen
    monkeypatch.setattr(checks, "unseen", lambda s, *a, **k: strings.append(s) or real_unseen(s, *a, **k))
    path = root / "config" / "classify_overrides.csv"
    cols = path.read_text().strip().split(",")
    with path.open("w", newline="") as f:
        w = _csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerow({"promise_id": "DMK-2021-0004", "sector": "health", "promise_type": "infrastructure",
                    "specificity": "specific", "cost_band": "low", "union_dependent": "false", "union_basis": "none",
                    "continues_existing": "false", "continues_cue": "", "headline_signal": "0",
                    "indicators_json": _json.dumps({"search_queries": ["new hospital Erode", "hospital order"]}),
                    "note": ""})
    install(monkeypatch, FakeLLM())
    run.run_classify(term="DMK-2021")
    texts = [t for t, _ in seen]
    assert texts.count("Build a new hospital in Erode.") == 2  # model answer + override
    assert len(set(texts)) == 5
    assert "new hospital Erode" in strings and "hospital order" in strings
    assert sum(n for _, n in seen) == len(strings)
