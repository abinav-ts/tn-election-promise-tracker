"""Spec 02 §7: mock LLM batching, retry alone, overrides, drops, cache."""

import csv
import json
import shutil

import pytest

from conftest import REPO

UNITS = [
    {"unit_id": "DMK-2021-U0001", "text": "1. Free bus travel will be provided to women.", "number": 1},
    {"unit_id": "DMK-2021-U0002", "text": "2. The last regime failed farmers. Rs 5,000 will be given to farmers.",
     "number": 2},
    {"unit_id": "DMK-2021-U0003", "text": "3. A new hospital will be built in Erode.", "number": 3},
]


def _unit_rows(units):
    return "".join(json.dumps({"unit_id": u["unit_id"], "page_start": 1, "page_end": 1, "section": None,
                               "marker": "running_number", "text": u["text"], "number": u["number"],
                               "sub_list": False, "page_offsets": [[0, 1]]}) + "\n" for u in units)


def _answer(units):
    return {"units": units}


GOOD_1 = {"unit_id": "DMK-2021-U0001", "section_en": None, "pieces": [
    {"kind": "promise", "text": "Provide free bus travel to women.", "source_text": "Free bus travel will be provided to women"}]}
GOOD_2 = {"unit_id": "DMK-2021-U0002", "section_en": None, "pieces": [
    {"kind": "criticism", "text": "", "source_text": "The last regime failed farmers."},
    {"kind": "promise", "text": "Give Rs 5,000 to farmers.", "source_text": "Rs 5,000 will be given to farmers"}]}
BAD_3 = {"unit_id": "DMK-2021-U0003", "section_en": None, "pieces": [
    {"kind": "promise", "text": "Build a new hospital in Erode.", "source_text": "A hospital will be built in Erode"}]}
GOOD_3 = {"unit_id": "DMK-2021-U0003", "section_en": None, "pieces": [
    {"kind": "promise", "text": "Build a new hospital in Erode.", "source_text": "A new hospital will be built in Erode"}]}


@pytest.fixture
def term(root):
    from ept.config import get_config

    shutil.copy(REPO / "prompts" / "extract_promises.md", root / "prompts")
    cfg = get_config()
    cfg.settings.llm.models["bulk"] = "test-model"
    cfg.settings.extract.units_per_call = 3
    folder = cfg.path("manifesto_interim") / "DMK-2021"
    folder.mkdir(parents=True)
    (folder / "units.jsonl").write_text(_unit_rows(UNITS), encoding="utf-8")
    return root


def _fixtures(root, *answers):
    folder = root / "tests" / "fixtures" / "llm" / "extract_promises"
    shutil.rmtree(folder, ignore_errors=True)
    folder.mkdir(parents=True)
    for i, a in enumerate(answers):
        (folder / f"{i:03d}.json").write_text(json.dumps(a, ensure_ascii=False), encoding="utf-8")


def _pieces(root):
    path = root / "data" / "interim" / "manifestos" / "DMK-2021" / "pieces.jsonl"
    return [json.loads(l) for l in path.read_text().splitlines()]


def _csv(root, name):
    with (root / "data" / "interim" / name).open() as f:
        return list(csv.DictReader(f))


def test_batch_then_failing_unit_retried_alone(term):
    from ept.extract.promises import run_promises

    # call 1 = the batch (unit 3 fails V1); call 2 = unit 3 alone (mock serves files by attempt order)
    _fixtures(term, _answer([GOOD_1, GOOD_2, BAD_3]))
    stats = run_promises(term="DMK-2021")
    assert stats["llm_calls"] == 2  # batch + unit 3 alone
    assert [p["unit_id"] for p in _pieces(term)] == ["DMK-2021-U0001", "DMK-2021-U0002"]
    fails = _csv(term, "extract_failures_02.csv")
    assert fails and fails[0]["rule"] == "V1" and fails[0]["resolved_by"] == ""
    drops = _csv(term, "extract_dropped_02.csv")
    assert [d["kind"] for d in drops] == ["criticism"]


def test_retry_alone_resolves(term, monkeypatch):
    from ept.extract import promises

    answers = iter([_answer([GOOD_1, GOOD_2, BAD_3]), _answer([GOOD_3])])
    monkeypatch.setattr(promises, "call_batch",
                        lambda client, t, p, units, model=None: {u["unit_id"]: promises.UnitOut(**u)
                                                                 for u in next(answers)["units"]})
    promises.run_promises(term="DMK-2021")
    assert [p["unit_id"] for p in _pieces(term)][-1] == "DMK-2021-U0003"
    assert _pieces(term)[-1]["retried"] is True
    assert _csv(term, "extract_failures_02.csv")[0]["resolved_by"] == "retry alone"


def test_override_applied_and_checked(term):
    from ept.extract.promises import run_promises

    _fixtures(term, _answer([GOOD_1, GOOD_2, BAD_3]))
    with (term / "config" / "promise_overrides.csv").open("a", encoding="utf-8") as f:
        f.write('DMK-2021-U0003,Build a new hospital in Erode.,A new hospital will be built in Erode,,fixed V1\n')
        f.write('DMK-2021-U0001,Provide free bus travel to women in Kerala.,Free bus travel will be provided to women,,bad\n')
    run_promises(term="DMK-2021")
    pieces = _pieces(term)
    assert [(p["unit_id"], p["origin"]) for p in pieces] == [("DMK-2021-U0002", "llm"), ("DMK-2021-U0003", "override")]
    fails = _csv(term, "extract_failures_02.csv")
    assert any(f["unit_id"] == "DMK-2021-U0001" and f["detail"].startswith("override: V3") for f in fails)
    assert any(f["unit_id"] == "DMK-2021-U0003" and f["resolved_by"] == "override" for f in fails)


def test_limit_and_cache_rerun_zero_calls(term):
    from ept.extract.promises import run_promises

    _fixtures(term, _answer([GOOD_1, GOOD_2]))
    assert run_promises(term="DMK-2021", limit=2)["llm_calls"] == 1
    first = _pieces(term)
    assert run_promises(term="DMK-2021", limit=2)["llm_calls"] == 0
    assert _pieces(term) == first


def test_frozen_term_refused(term):
    from ept.config import get_config
    from ept.extract.freeze import FrozenTermError
    from ept.extract.promises import run_promises

    get_config().settings.extract.frozen_terms.append("DMK-2021")
    with pytest.raises(FrozenTermError):
        run_promises(term="DMK-2021", force=True)
