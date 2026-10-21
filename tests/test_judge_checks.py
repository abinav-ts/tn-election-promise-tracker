"""Spec 05 §4.5 / §7: checks J1–J7 and D1–D3 with fixture answers."""

import datetime as dt

import pytest

from ept.judge.checks import Limits, TaskInput, check_task, match_answers, normalise, quote_match
from ept.judge.prompt import TaskVerdictOut
from ept.judge.tasks import ChunkInfo

LIM = Limits(5, 40, 95, 80)
GO_TEXT = ("G.O.(Ms) No.45 Dated: 14.08.2017. Government accord sanction for free bus travel for women in town "
           "buses operated by the transport corporation from 1st September 2017.")
PN_TEXT = "The fare exemption scheme for women continues. In 2018 the coverage was widened to all districts."


def chunk(cid, text, doc_date=None, prec=None, avail=None, doc_type="go"):
    return ChunkInfo(cid, "title", doc_type, doc_date, prec, text, avail)


@pytest.fixture
def task():
    return TaskInput("T01", {
        "C1": chunk("go-0000", GO_TEXT, dt.date(2017, 8, 14), "day", dt.date(2017, 8, 14)),
        "C2": chunk("pn-0001", PN_TEXT, dt.date(2018, 1, 1), "year", dt.date(2019, 3, 31), "policy_note"),
    }, dt.date(2016, 5, 23), False)


def ans(**kw):
    base = dict(task="T01", status="fulfilled", realisation_date="2017-08-14", date_extract="C1",
                cited=[{"extract": "C1", "quote": "Government accord sanction for free bus travel for women"}],
                rationale="C1 is the GO.", confidence=0.9)
    base.update(kw)
    return TaskVerdictOut.model_validate(base)


def test_valid_answer_passes(task):
    c = check_task(ans(), task, LIM)
    assert c.ok, c.failures
    assert c.date_chunk_id == "go-0000" and c.cited_chunk_ids == ["go-0000"] and c.date_precision == "day"


def test_j1_matching_missing_duplicate_extra():
    a = [ans(task="T01"), ans(task="T02"), ans(task="T02"), ans(task="T09")]
    matched, fails, extras = match_answers(["T01", "T02", "T03"], a)
    assert set(matched) == {"T01"} and set(fails) == {"T02", "T03"} and extras == ["T09"]


@pytest.mark.parametrize("kw,rule", [
    (dict(confidence=1.4), "J1"),
    (dict(rationale="word " * 81), "J1"),
    (dict(realisation_date="14.08.2017"), "J1"),
    (dict(realisation_date="2017-13"), "J1"),
    (dict(cited=[]), "J2"),
    (dict(cited=[{"extract": "C7", "quote": "Government accord sanction for free bus travel"}]), "J2"),
    (dict(date_extract="C2"), "J2"),  # C2 not cited
    (dict(cited=[{"extract": "C1", "quote": "free bus"}]), "J3"),
    (dict(cited=[{"extract": "C1", "quote": "the scheme was launched for all women in the state"}]), "J3"),
    (dict(realisation_date=None, date_extract=None), "J4"),
    (dict(status="not_started", cited=[]), "J4"),
    (dict(date_extract=None), "J4"),
    (dict(realisation_date="2016-04-01"), "J5"),
    (dict(realisation_date="2017-09-01"), "J5"),  # after C1's availability
    (dict(realisation_date="2017-08-10"), "J6"),
])
def test_failures(task, kw, rule):
    c = check_task(ans(**kw), task, LIM)
    assert any(f.startswith(rule) for f in c.failures), c.failures


def test_unverifiable_and_not_started_need_no_citation(task):
    for s in ("unverifiable", "not_started"):
        assert check_task(ans(status=s, realisation_date=None, date_extract=None, cited=[]), task, LIM).ok


def test_quote_normalised_and_fuzzy(task):
    assert quote_match("GOVERNMENT accord  sanction, for free-bus travel", GO_TEXT, 95) == "exact"
    c = check_task(ans(cited=[{"extract": "C1", "quote": "Government acord sanction for free bus travel for women"}]),
                   task, LIM)
    assert c.ok and c.reasons == ["quote_fuzzy"]
    assert normalise("G.O.(Ms) No.45") == "g o ms no 45"


def test_date_from_text_month_and_year_precision(task):
    # "1st September 2017" in the GO text; C1 availability is 2017-08-14, so a later date fails J5 not J6
    c = check_task(ans(realisation_date="2017-08"), task, LIM)
    assert c.ok and c.date_precision == "month"
    q = [{"extract": "C2", "quote": "In 2018 the coverage was widened to all districts"}]
    c = check_task(ans(realisation_date="2018", date_extract="C2", cited=q, status="partial"), task, LIM)
    assert c.ok, c.failures  # year written in the text, period_start ≤ C2 availability 2019-03-31
    c = check_task(ans(realisation_date="2018-06", date_extract="C2", cited=q, status="partial"), task, LIM)
    assert any(f.startswith("J6") for f in c.failures)


def test_j5_precision_edges(task):
    edge = TaskInput("T01", {"C1": chunk("go-0000", "Order dated 2016 May on fares for women in town buses here",
                                         dt.date(2016, 5, 1), "month", dt.date(2016, 5, 31))}, dt.date(2016, 5, 23), False)
    q = [{"extract": "C1", "quote": "fares for women in town buses"}]
    assert check_task(ans(realisation_date="2016-05", cited=q), edge, LIM).ok  # period_end ≥ sworn_in
    assert any(f.startswith("J5") for f in check_task(ans(realisation_date="2016-05-01", cited=q), edge, LIM).failures)


def test_j7_directional_refuses_partial_and_diluted(task):
    d = TaskInput(task.alias, task.extracts, task.sworn_in, True)
    for s in ("partial", "diluted"):
        assert any(f.startswith("J7") for f in check_task(ans(status=s), d, LIM).failures)
    assert check_task(ans(), d, LIM).ok


def test_directional_checks_d1_d2_d3():
    from ept.judge.directional import DirItem, check_item

    nw = ["one", "crore"]
    assert check_item(None, "x", nw)[3][0].startswith("D1")
    assert check_item(DirItem(id="P01", directional=True, cue="Promote"), "Encourage farming.", nw)[3][0].startswith("D2")
    assert check_item(DirItem(id="P01", directional=True, cue="encourage"), "Encourage  farming.", nw)[:3] == \
        (True, "encourage", "")
    assert check_item(DirItem(id="P01", directional=True, cue="Promote"), "Promote one district.", nw)[:3] == \
        (False, "", "d3_override")
    assert check_item(DirItem(id="P01", directional=True, cue="Promote"), "Promote 5 parks.", nw)[2] == "d3_override"
    assert check_item(DirItem(id="P01", directional=False, cue="x"), "Promote parks.", nw)[:3] == (False, "", "")


def test_quote_and_date_may_come_from_the_title(task):
    t = TaskInput("T01", {"C1": ChunkInfo("go-0000", "G.O.Ms.No.9 dated 02.07.2017 - Free bus travel for women",
                                          "go", dt.date(2017, 8, 14), "day", GO_TEXT, dt.date(2017, 8, 14))},
                  task.sworn_in, False)
    c = check_task(ans(cited=[{"extract": "C1", "quote": "Free bus travel for women"}], realisation_date="2017-07-02"),
                   t, LIM)
    assert c.ok, c.failures


def test_feedback_names_the_check_without_internal_values():
    from ept.judge.checks import feedback

    out = feedback(["J3: quote for C3 not found in the extract",
                    "J5: date 2017-09-01 after the latest availability date of the cited extracts (2017-08-14)",
                    "J5: date 2017-09-02 after the latest availability date of the cited extracts (2017-08-14)"])
    assert out[0].startswith("J3: quote for C3 not found in the extract verbatim")
    assert len(out) == 2 and "2017-08-14" not in out[1]


def test_amount_gloss_is_ignored():
    text = "accord permission to dovetail a sum of Rs.50.00 crore (Rupees fifty crore only) from the schemes"
    assert quote_match("dovetail a sum of Rs.50.00 crore from the schemes", text, 95) == "exact"
    assert quote_match("dovetail a sum of Rs.60.00 crore from the schemes", text, 99) is None
