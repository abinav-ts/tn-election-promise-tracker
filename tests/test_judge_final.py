"""Spec 05 §4.10 / §7: precedence human > strong > bulk; carry-forward; overrides validated."""

import csv
import datetime as dt
import json

import pytest

from ept.judge.final import OverrideError, Pick, carry_forward, non_monotone, validate_override
from ept.schema import Verdict
from judge_helpers import FakeJudge, install, setup_judge


def v(cut, status="not_started", date=None, prec=None, src="bulk", cited=()):
    return Verdict(promise_id="X-2021-0001", run_id="r", cutoff_date=cut, status=status, realisation_date=date,
                   date_precision=prec, cited_chunk_ids=list(cited), rationale="r", confidence=0.8, judge_source=src)


M5, M12, M24 = dt.date(2021, 10, 7), dt.date(2022, 5, 7), dt.date(2023, 5, 7)


def test_carry_forward_earliest_date_and_non_monotone():
    picks = [Pick(v(M5)), Pick(v(M12, "partial", dt.date(2022, 3, 1), "month", cited=("a",)), "a"),
             Pick(v(M24, "fulfilled", dt.date(2022, 1, 10), "day", cited=("b",)), "b"),
             Pick(v(None, "not_started"))]
    out = carry_forward(picks)
    assert out[0].verdict.realisation_date is None
    assert out[1].verdict.realisation_date == dt.date(2022, 3, 1)
    # m24 is earlier than m12's: its own date is the earliest so far
    assert (out[2].verdict.realisation_date, out[2].verdict.date_precision) == (dt.date(2022, 1, 10), "day")
    # full term said not_started: the latest earlier realised verdict is carried, flagged
    f = out[3]
    assert f.verdict.status == "fulfilled" and f.verdict.cutoff_date is None and f.verdict.needs_review
    assert "non_monotone" in f.reasons and f.verdict.realisation_date == dt.date(2022, 1, 10)
    realised = [p.verdict.realisation_date is not None for p in out]
    assert realised == sorted(realised)  # monotone


def test_later_verdict_takes_earlier_date_and_its_chunk():
    out = carry_forward([Pick(v(M5, "fulfilled", dt.date(2021, 8, 1), "day", cited=("a",)), "a"),
                         Pick(v(M12, "fulfilled", dt.date(2022, 2, 1), "day", cited=("b",)), "b")])
    assert out[1].verdict.realisation_date == dt.date(2021, 8, 1) and out[1].verdict.cited_chunk_ids == ["b", "a"]
    assert out[1].verdict.status == "fulfilled" and "non_monotone" not in out[1].reasons


def test_non_monotone_helper():
    assert non_monotone([None, dt.date(2020, 1, 1), None]) and not non_monotone([None, dt.date(2020, 1, 1)])


@pytest.mark.parametrize("row,msg", [
    (dict(reason=""), "no reason"),
    (dict(source="gold_labels.csv"), "not a spot-check"),
    (dict(reason="as in the gold set"), "gold"),
    (dict(status="done"), "not in §8"),
    (dict(realisation_date=""), "iff"),
    (dict(cutoff="2030-01-01"), "cutoff"),
])
def test_override_validation(row, msg):
    base = dict(promise_id="DMK-2021-0001", cutoff="full", status="fulfilled", realisation_date="2021-06-01",
                date_precision="day", cited_chunk_ids="c1", source="spotcheck_05#3", reason="wrong date chunk")
    validate_override(base, {"full"})
    with pytest.raises(OverrideError, match=msg):
        validate_override(base | row, {"full"})


def test_final_run_precedence_coverage_monotone_and_export(root, conn, monkeypatch):
    from ept.config import get_config
    from ept.judge.aggregate import run_aggregate
    from ept.judge.bulk import run_bulk
    from ept.judge.final import OVERRIDE_COLUMNS, run_final

    setup_judge(root, conn)
    install(monkeypatch, FakeJudge())
    bulk = run_bulk()
    run_aggregate()
    cfg = get_config()
    # a strong run covering one promise at full term
    from ept.judge.store import fp_hash, start_or_resume, write_verdicts

    srun, _ = start_or_resume(cfg, "strong", fp_hash({"x": 1}), False, {})
    write_verdicts(conn, [Verdict(promise_id="TVK-2026-0001", run_id=srun, cutoff_date=dt.date(2026, 10, 10),
                                  status="in_progress", rationale="strong", confidence=0.7, judge_source="strong",
                                  judge_model="claude")])
    with cfg.path("verdict_overrides").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=OVERRIDE_COLUMNS)
        w.writeheader()
        w.writerow(dict(promise_id="DMK-2021-0003", cutoff="full", status="not_started", realisation_date="",
                        date_precision="", cited_chunk_ids="", source="spotcheck_05#1", reason="no GO in the chunks"))
    s = run_final()
    assert s["missing_promise_cutoffs"] == 0 and s["sources"]["human"] == 1 and s["sources"]["strong"] >= 1
    rows = conn.execute("SELECT * FROM verdicts WHERE run_id = ?", (s["run_id"],)).fetchall()
    by = {(r["promise_id"], r["cutoff_date"]): r for r in rows}
    assert by[("TVK-2026-0001", "2026-10-10")]["judge_source"] == "strong"
    assert by[("DMK-2021-0003", None)]["judge_source"] == "human"
    # realised by cutoff is monotone per promise
    from ept.judge.tasks import Context

    ctx = Context(conn, cfg)
    for pid, p in ctx.promises.items():
        seq = [by[(pid, c.cutoff_date.isoformat() if c.cutoff_date else None)]["realisation_date"] is not None
               for c in ctx.cutoffs(p["term_id"])]
        assert seq == sorted(seq), pid
    export = [json.loads(x) for x in (cfg.root / s["export"]).read_text().splitlines()]
    assert len(export) == len(rows)
    again = run_final()
    assert again["run_id"] == s["run_id"] and again["written"] == 0
    assert bulk["complete"]
