"""Spec 02 §5/§7 leakage checks: invented few-shot examples, no corpus access, checks on every piece."""

import re
from pathlib import Path

import pytest

from conftest import REPO

PROMPTS = ["extract_promises", "dedup_check", "transcribe_page"]


def _runs(text, n=8):
    words = re.findall(r"[\w\u0B80-\u0BFF]+", text.lower())
    return {" ".join(words[i:i + n]) for i in range(len(words) - n + 1)}


def _manifesto_texts():
    """Local page text of the manifestos (data/interim, not committed) plus committed transcriptions."""
    files = list((REPO / "data" / "interim" / "manifestos").glob("*/page_*.txt"))
    files += list((REPO / "data" / "frozen" / "transcriptions").glob("*/page_*.txt"))
    return [f.read_text(encoding="utf-8") for f in files]


def test_few_shot_examples_share_no_8_word_run_with_manifestos():
    texts = _manifesto_texts()
    if not texts:
        pytest.skip("no local manifesto text (run `ept extract pages`)")
    manifesto_runs = set().union(*(_runs(t) for t in texts))
    for name in PROMPTS:
        overlap = _runs((REPO / "prompts" / f"{name}.md").read_text(encoding="utf-8")) & manifesto_runs
        assert not overlap, (name, sorted(overlap)[:3])


def test_stage_reads_no_corpus_or_tracker_path():
    forbidden = ["raw_evidence", "text_dir", "trackers_raw", "tracker_leads", "catalogue_dir", "FROM chunks",
                 "FROM documents"]
    for path in (REPO / "src" / "ept" / "extract").glob("*.py"):
        src = path.read_text(encoding="utf-8")
        for f in forbidden:
            assert f not in src, (path.name, f)


def test_checks_run_on_every_promise_and_override(root, monkeypatch):
    from ept.config import get_config
    from ept.extract import promises
    from ept.extract.units import Unit

    seen = []
    real = promises.check_promise
    monkeypatch.setattr(promises, "check_promise", lambda *a, **k: seen.append(a[0]) or real(*a, **k))
    unit = Unit("T-U0001", 1, 1, None, "bullet", "a b c will be done. d e will be done.")
    out = promises.UnitOut(unit_id="T-U0001", pieces=[
        promises.Piece(kind="promise", text="Do a b c.", source_text="a b c will be done"),
        promises.Piece(kind="promise", text="Do d e.", source_text="d e will be done"),
        promises.Piece(kind="other", text="", source_text="a")])
    promises.judge_unit("T", unit, out, "en", get_config())
    promises.apply_overrides("T", unit, [{"text": "Do Kerala x.", "source_text": "a b c", "section_en": ""}], "en",
                             get_config())
    assert seen == ["Do a b c.", "Do d e.", "Do Kerala x."]
