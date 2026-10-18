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
