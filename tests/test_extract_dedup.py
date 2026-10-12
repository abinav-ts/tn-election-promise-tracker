"""Spec 02 §7: candidate threshold; yes -> later dropped, no -> both kept; IDs contiguous; parent_group, page."""

import json
import shutil

import pytest

from conftest import REPO

UNITS = [
    {"unit_id": "DMK-2021-U0001", "text": "1. Free bus travel will be provided to women.", "pages": [[0, 1]]},
    {"unit_id": "DMK-2021-U0002", "text": "2. Women will get free bus travel.\nA hospital will be built in Erode.",
     "pages": [[0, 1], [35, 2]]},
]
PIECES = [
    ("DMK-2021-U0001", 0, "Provide free bus travel to women.", "Free bus travel will be provided to women"),
    ("DMK-2021-U0002", 0, "Provide free bus travel for women.", "Women will get free bus travel."),
    ("DMK-2021-U0002", 1, "Build a hospital in Erode.", "A hospital will be built in Erode"),
]


@pytest.fixture
def term(root, conn):
    from ept.config import get_config

    shutil.copy(REPO / "prompts" / "dedup_check.md", root / "prompts")
    cfg = get_config()
    cfg.settings.llm.models["bulk"] = "test-model"
    folder = cfg.path("manifesto_interim") / "DMK-2021"
    folder.mkdir(parents=True)
    (folder / "units.jsonl").write_text("".join(json.dumps({
        "unit_id": u["unit_id"], "page_start": u["pages"][0][1], "page_end": u["pages"][-1][1], "section": "S",
        "marker": "running_number", "text": u["text"], "number": n, "sub_list": False, "page_offsets": u["pages"]})
        + "\n" for n, u in enumerate(UNITS, 1)), encoding="utf-8")
    (folder / "pieces.jsonl").write_text("".join(json.dumps({
        "term": "DMK-2021", "unit_id": uid, "piece": k, "text": t, "source_text": s, "section_en": "S",
        "source_lang": "en", "origin": "llm"}) + "\n" for uid, k, t, s in PIECES), encoding="utf-8")
    return root


def _answer(root, same):
    folder = root / "tests" / "fixtures" / "llm" / "dedup_check"
    shutil.rmtree(folder, ignore_errors=True)
    folder.mkdir(parents=True)
    (folder / "000.json").write_text(json.dumps({"pairs": [{"pair_id": 0, "same": same, "reason": "x"}]}))


def test_candidate_threshold():
    from ept.extract.dedup import candidate_pairs

    pairs = candidate_pairs(["Provide free bus travel to women.", "Provide free bus travel for women.",
                             "Build a hospital in Erode."], 0.8)
    assert [(i, j) for i, j, _ in pairs] == [(0, 1)]


def test_yes_drops_later_ids_contiguous(term, conn):
    from ept.extract.dedup import run_dedup

    _answer(term, True)
    stats = run_dedup(term="DMK-2021")
    assert stats["dropped"] == 1 and stats["llm_calls"] == 1
    rows = [dict(r) for r in conn.execute("SELECT * FROM promises ORDER BY promise_id")]
    assert [r["promise_id"] for r in rows] == ["DMK-2021-0001", "DMK-2021-0002"]
    assert [r["parent_group"] for r in rows] == ["DMK-2021-U0001", "DMK-2021-U0002"]
    assert rows[1]["page"] == 2  # source_text starts on the unit's second page
    assert rows[0]["sector"] is None and rows[0]["source_lang"] == "en"
    log = (term / "data" / "interim" / "promise_dedup.csv").read_text()
    assert "dropped_later" in log and "DMK-2021-0001" in log
    cov = json.loads((term / "data/interim/manifestos/DMK-2021/coverage.json").read_text())
    assert cov["unexplained"] == []  # item 2 still has the hospital promise


def test_no_keeps_both(term, conn):
    from ept.extract.dedup import run_dedup

    _answer(term, False)
    run_dedup(term="DMK-2021")
    assert conn.execute("SELECT COUNT(*) FROM promises").fetchone()[0] == 3
    assert "kept_both" in (term / "data" / "interim" / "promise_dedup.csv").read_text()


def test_source_offset_after_normalisation():
    from ept.extract.dedup import source_offset

    unit = "Line one ends\nhere and   the\npromise starts"
    assert source_offset("here and the promise", unit) == unit.index("here")
