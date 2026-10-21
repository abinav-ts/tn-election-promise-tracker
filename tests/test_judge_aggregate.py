"""Spec 05 §4.7 / §7: every aggregation rule, incl. all-diluted vs one-diluted and directional."""

import datetime as dt

import pytest

from ept.judge.aggregate import aggregate, combine_status
from ept.schema import IndicatorVerdict


def iv(n, status, date=None, prec=None, conf=0.9, review=False, cited=("c1",), chunk=None):
    realised = status in ("fulfilled", "partial", "diluted")
    return IndicatorVerdict(indicator_id=f"X-2021-0001-I{n}", run_id="r", cutoff_date=None, judging_key=f"k{n}",
                            status=status, realisation_date=date, date_precision=prec,
                            date_chunk_id=chunk or (f"c{n}" if realised else None),
                            cited_chunk_ids=list(cited), rationale=f"rationale {n}", confidence=conf,
                            needs_review=review, judge_source="bulk")


@pytest.mark.parametrize("statuses,expected", [
    (["fulfilled", "fulfilled"], "fulfilled"),
    (["diluted", "diluted"], "diluted"),
    (["diluted", "fulfilled"], "partial"),
    (["diluted", "not_started"], "partial"),
    (["fulfilled", "not_started"], "partial"),
    (["partial", "unverifiable"], "partial"),
    (["in_progress", "not_started"], "in_progress"),
    (["blocked_external", "not_started"], "blocked_external"),
    (["in_progress", "blocked_external"], "in_progress"),
    (["unverifiable", "unverifiable"], "unverifiable"),
    (["unverifiable", "not_started"], "not_started"),
])
def test_combine_rules(statuses, expected):
    dated = [s in ("fulfilled", "partial", "diluted") for s in statuses]
    assert combine_status(statuses, dated, False) == expected


@pytest.mark.parametrize("statuses,expected", [
    (["fulfilled", "not_started"], "fulfilled"),
    (["in_progress", "not_started"], "in_progress"),
    (["blocked_external", "not_started"], "blocked_external"),
    (["unverifiable", "unverifiable"], "unverifiable"),
    (["unverifiable", "not_started"], "not_started"),
])
def test_directional_rules(statuses, expected):
    dated = [s == "fulfilled" for s in statuses]
    assert combine_status(statuses, dated, True) == expected


def test_single_indicator_equals_indicator_verdict():
    a = aggregate([iv(1, "partial", dt.date(2017, 3, 1), "month", conf=0.7)], False, 80)
    assert (a.status, a.realisation_date, a.date_precision, a.confidence, a.rationale) == \
        ("partial", dt.date(2017, 3, 1), "month", 0.7, "rationale 1")


def test_fields_earliest_date_ties_finer_union_min_any():
    rows = [iv(2, "fulfilled", dt.date(2017, 1, 1), "year", conf=0.8, cited=("a", "b")),
            iv(1, "fulfilled", dt.date(2017, 1, 1), "day", conf=0.6, review=True, cited=("b", "c"))]
    a = aggregate(rows, False, 80)
    assert a.status == "fulfilled"
    assert (a.realisation_date, a.date_precision, a.date_chunk_id) == (dt.date(2017, 1, 1), "day", "c1")
    assert a.cited_chunk_ids == ["b", "c", "a"]  # indicator order
    assert a.confidence == 0.6 and a.needs_review
    assert a.rationale.startswith("I1 fulfilled 2017-01-01; I2 fulfilled 2017.")
    assert len(a.rationale.split()) <= 80


def test_one_diluted_with_fulfilled_gives_partial_with_earliest_date():
    a = aggregate([iv(1, "diluted", dt.date(2018, 5, 1), "month"), iv(2, "fulfilled", dt.date(2017, 2, 3), "day"),
                   iv(3, "not_started", cited=())], False, 80)
    assert a.status == "partial" and a.realisation_date == dt.date(2017, 2, 3)


def test_realised_iff_dated_and_rationale_capped():
    long = iv(1, "not_started", cited=())
    long = long.model_copy(update={"rationale": "w " * 80})
    a = aggregate([long, iv(2, "not_started", cited=())], False, 80)
    assert a.realisation_date is None and len(a.rationale.split()) <= 80


def test_promise_verdicts_need_every_indicator():
    from ept.judge.aggregate import promise_verdicts

    rows = [iv(1, "fulfilled", dt.date(2017, 1, 1), "day")]
    assert promise_verdicts(rows, {"X-2021-0001": ["X-2021-0001-I1", "X-2021-0001-I2"]}, {}, 80) == {}
    assert len(promise_verdicts(rows, {"X-2021-0001": ["X-2021-0001-I1"]}, {}, 80)) == 1
