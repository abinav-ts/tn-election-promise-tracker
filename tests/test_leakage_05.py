"""Spec 05 §5 / §7 leakage checks: invented examples, no gold IDs or label files, neutral templates, and a
planted cross-cutoff call and uncited realisation caught by the leakage line."""

import csv
import json

import pytest

from conftest import REPO
from judge_helpers import FakeJudge, install, setup_judge
from test_leakage_02 import _manifesto_texts, _runs

PROMPTS = [REPO / "prompts" / "judge_indicator.md", REPO / "prompts" / "directional_check.md"]
JUDGE_SRC = sorted((REPO / "src" / "ept" / "judge").glob("*.py"))


def _promise_texts():
    out = []
    for p in (REPO / "data" / "frozen").glob("promises_*.jsonl"):
        for line in p.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            out += [r.get("text", ""), r.get("source_text", "")]
    for u in (REPO / "data" / "interim" / "manifestos").glob("*/units.jsonl"):
        out.append(u.read_text(encoding="utf-8"))
    return out


def test_prompts_share_no_8_word_run_with_promises_units_or_manifestos():
    texts = _promise_texts() + _manifesto_texts()
    if not texts:
        pytest.skip("no frozen promises or manifesto text")
    runs = set().union(*(_runs(t) for t in texts))
    for p in PROMPTS:
        overlap = _runs(p.read_text(encoding="utf-8")) & runs
        assert not overlap, (p.name, sorted(overlap)[:3])


def test_prompts_contain_no_gold_promise_id_and_no_promise_id_at_all():
    import re

    gold = REPO / "data" / "gold" / "gold_sample.csv"
    ids = set()
    if gold.exists():
        with gold.open(encoding="utf-8", newline="") as f:
            ids = {r["promise_id"] for r in csv.DictReader(f) if r.get("promise_id")}
    for p in PROMPTS:
        body = p.read_text(encoding="utf-8")
        assert not any(i in body for i in ids)
        assert not re.search(r"[A-Z]+-\d{4}-\d{4}", body)


def test_templates_name_no_party_term_or_cutoff():
    from ept.config import load_config
    from ept.llm import load_prompt

    cfg = load_config(REPO)
    for p in PROMPTS:
        body = load_prompt(p.stem, cfg).body.lower()  # what the model sees (the header is not sent)
        for t in cfg.settings.terms:
            for name in (t.party, t.term_id, str(t.manifesto_year)):
                assert name.lower() not in body, (p.name, name)
        assert "cutoff" not in body
        for tamil in ("கழக", "திமுக", "அதிமுக", "தவெக"):
            assert tamil not in body


def test_judge_never_opens_label_files_and_reads_gold_ids_in_one_place():
    for path in JUDGE_SRC:
        src = path.read_text(encoding="utf-8")
        assert "gold_labels" not in src and "gold_relabel" not in src, path.name
        assert "data/gold" not in src, path.name
        if path.name != "tasks.py":
            assert 'path("gold_sample")' not in src, path.name


def test_rendered_task_has_no_ids_or_cutoff(root, conn, monkeypatch):
    from ept.judge.bulk import run_bulk

    setup_judge(root, conn)
    fake = install(monkeypatch, FakeJudge())
    run_bulk(limit=1)
    for call in fake.calls:
        for t in call:
            assert set(t) <= {"task", "promise", "indicator", "directional", "context", "extracts", "note",
                              "previous_answer_failed"}
            for e in t["extracts"]:
                assert set(e) == {"extract", "title", "doc_type", "date", "text"}
                assert "-" not in e["extract"]  # an alias, never a chunk_id


def test_planted_cross_cutoff_call_and_uncited_realisation_are_caught(root, conn, monkeypatch):
    from ept.config import get_config
    from ept.judge.bulk import calls_path, run_bulk
    from ept.judge.report import build

    setup_judge(root, conn)
    install(monkeypatch, FakeJudge())
    s = run_bulk()
    cfg = get_config()
    assert build(conn, cfg)["leakage"]["total"] == 0
    with calls_path(cfg, s["run_id"]).open("a", encoding="utf-8") as f:
        f.write(json.dumps({"call": 999, "stage": "first", "groups": ["DMK-2021@2021-10-07", "DMK-2021@full"],
                            "n_tasks": 2, "failed": 0, "backend_calls": 0, "ts": "2026-10-22T00:00:00+00:00"}) + "\n")
    row = conn.execute("SELECT indicator_id, cutoff_date FROM indicator_verdicts WHERE run_id = ? AND status = "
                       "'not_started' LIMIT 1", (s["run_id"],)).fetchone()
    conn.execute("UPDATE indicator_verdicts SET status = 'fulfilled', realisation_date = '2021-06-01', "
                 "date_precision = 'day' WHERE run_id = ? AND indicator_id = ? AND cutoff_date IS ?",
                 (s["run_id"], row[0], row[1]))
    conn.commit()
    lk = build(conn, cfg)["leakage"]
    assert lk["mixed_calls"] == 1 and lk["realised_uncited"] == 1 and lk["total"] >= 2
