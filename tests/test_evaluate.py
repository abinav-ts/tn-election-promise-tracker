"""Stage 06 Part 2 tests (spec 06 §H): fixtures only; no real gold labels are read."""

import pathlib
import re

import pytest

from ept.config import load_config
from ept.evaluate import gold as G
from ept.evaluate import metrics as M
from ept.evaluate import run as R


def test_wilson_interval():
    p, lo, hi = M.wilson(8, 10)
    assert p == 0.8 and 0.49 < lo < 0.50 and 0.94 < hi < 0.95
    assert M.wilson(0, 0) == (None, None, None)


def test_e1_table_counts():
    pairs = [("fulfilled", "fulfilled"), ("fulfilled", "not_started"), ("not_started", "partial"), ("not_started", "unverifiable")]
    t = M.e1_table(pairs)
    assert (t["tp"], t["fn"], t["fp"], t["tn"]) == (1, 1, 1, 1)
    assert t["accuracy"]["p"] == 0.5 and t["recall"]["k"] == 1 and t["precision"]["n"] == 2


def test_status_agreement_merges_not_started_unverifiable():
    a = M.status_agreement([("not_started", "unverifiable"), ("fulfilled", "fulfilled"), ("partial", "fulfilled")])
    assert a["exact"]["k"] == 1 and a["exact_merging_not_started_unverifiable"]["k"] == 2


def test_date_error_uses_period_midpoints():
    d = M.date_error([{"gold_date": "2017-03-01", "gold_precision": "day", "judge_date": "2017-04-01", "judge_precision": "day"},
                      {"gold_date": "2017-01-01", "gold_precision": "year", "judge_date": "2017-07-02", "judge_precision": "day"}], 90)
    assert d["n"] == 2 and d["median_signed_days"] == 15.5 and d["within_90_days"]["k"] == 2


def test_realised_by_cutoff():
    import datetime as dt
    assert M.realised_by("fulfilled", "2017-03-01", "day", dt.date(2017, 3, 1))
    assert not M.realised_by("fulfilled", "2017-03-02", "day", dt.date(2017, 3, 1))
    assert not M.realised_by("not_started", None, None, dt.date(2017, 3, 1))


def test_bucket_order():
    assert M.bucket({"in_corpus": False, "unsure": True}) == "evidence_outside_corpus"
    assert M.bucket({"in_corpus": True, "unsure": True}) == "label_uncertain"
    assert M.bucket({"evidence_chunks_missing": True, "evidence_checked": True}) == "retrieval_miss"
    assert M.bucket({"evidence_checked": True}) == "judge_error"
    assert M.bucket({}) == "other"


WIN = {"DMK-2021": ("2021-05-07", "2026-05-09"), "AIADMK-2016": ("2016-05-23", "2021-05-06")}


def _lab(pid, status, date="", prec="", ev="", notes=""):
    return {"promise_id": pid, "status": status, "realisation_date": date, "date_precision": prec, "evidence": ev,
            "in_corpus": "true", "notes": notes, "labelled_at": "x"}


def test_validator_rules():
    with pytest.raises(G.LabelError):
        G.validate_row(_lab("a", "fulfilled", "2017-01-01", "day", ""), WIN["AIADMK-2016"])      # evidence missing
    with pytest.raises(G.LabelError):
        G.validate_row(_lab("a", "not_started", "2017-01-01", "day"), WIN["AIADMK-2016"])        # date on non-E1
    with pytest.raises(G.LabelError):
        G.validate_row(_lab("a", "fulfilled", "2030-01-01", "day", "u"), WIN["AIADMK-2016"])     # outside the term
    with pytest.raises(G.LabelError):
        G.validate_row(_lab("a", "partial", "2017-01-01", "day", "u", "[directional]"), WIN["AIADMK-2016"])
    G.validate_row(_lab("a", "not_started"), WIN["AIADMK-2016"])


def test_prefix_must_be_gap_free_and_long_enough():
    sample = [{"order": str(i), "promise_id": f"DMK-2021-{i:04d}", "term_id": "DMK-2021"} for i in range(1, 6)]
    labels = [_lab(f"DMK-2021-{i:04d}", "not_started") for i in (1, 2, 4)]
    assert len(G.load_prefix(labels, sample, WIN, 2)) == 2
    with pytest.raises(G.LabelError):
        G.load_prefix(labels, sample, WIN, 3)


def test_evaluate_core_on_fixtures():
    cfg = load_config()
    sample = []
    labels = [{**_lab("DMK-2021-0001", "fulfilled", "2022-01-01", "day", "abcdef0123456789-0001"), "term_id": "DMK-2021"},
              {**_lab("DMK-2021-0002", "not_started"), "term_id": "DMK-2021"}]
    V = {("DMK-2021-0001", None): {"status": "fulfilled", "date": "2022-02-01", "precision": "day"},
         ("DMK-2021-0002", None): {"status": "partial", "date": "2023-01-01", "precision": "day"}}
    res = R.evaluate(cfg, labels, sample, None, {"bulk": V}, {"DMK-2021-0001": {"abcdef0123456789-0001"}, "DMK-2021-0002": {"x-0001"}})
    g = res["judges"]["bulk"]["groups"]["DMK-2021"]
    assert g["e1"]["tp"] == 1 and g["e1"]["fp"] == 1 and g["date"]["median_abs_days"] == 31
    d = res["judges"]["bulk"]["disagreements"]
    assert d["n"] == 1 and d["bucket_sum_ok"] and d["buckets"] == {"judge_error": 1}


def test_only_evaluate_package_opens_gold_labels():
    root = pathlib.Path(__file__).resolve().parents[1] / "src" / "ept"
    for f in root.rglob("*.py"):
        if "evaluate" in f.parts or f.name == "config.py":   # config only declares the path keys
            continue
        assert not re.search(r"gold_(labels|relabel)", f.read_text()), f"{f} refers to the gold label files"
