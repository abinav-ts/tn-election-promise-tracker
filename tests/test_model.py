"""Stage 07 tests (spec 07 §8): synthetic data, offline."""

import datetime as dt
import pathlib
import re

import numpy as np
import pandas as pd
import pytest

from ept.config import load_config
from ept.model import backtest, data
from ept.model.cox import LeakageError, assert_only_terms, fit_cox, pace_factor, expected_events

SW = dt.date(2021, 5, 7)


def test_event_days_rules():
    assert data.event_days("2021-06-06", "day", SW, 1000) == 30
    assert data.event_days("2016-01-01", "year", SW, 1000) == 1               # before sworn_in -> day 1
    assert data.event_days("2021-06-01", "month", SW, 1000, "start") == 25  # 2021-06-01
    assert data.event_days("2021-06-01", "month", SW, 1000, "end") == 54    # 2021-06-30
    assert data.event_days("2021-06-01", "month", SW, 1000, "midpoint") == 39
    assert data.event_days("2030-01-01", "day", SW, 500) == 500          # clipped to censoring


def test_realised_without_date_refused():
    cfg = load_config()
    rows = [{"promise_id": "DMK-2021-0001", "cutoff_date": None, "status": "fulfilled", "realisation_date": None,
             "date_precision": None, "judge_source": "bulk"}]
    with pytest.raises(ValueError):
        data.analysis_table(cfg, rows=rows)


def test_real_export_counts():
    cfg = load_config()
    t = data.analysis_table(cfg)
    n = t.groupby("term_id").size().to_dict()
    assert n == {"AIADMK-2016": 312, "DMK-2021": 667, "TVK-2026": 695}
    assert t.groupby("term_id")["E1"].sum().to_dict() == {"AIADMK-2016": 270, "DMK-2021": 408, "TVK-2026": 23}
    assert (t["T"] >= 1).all()


def _sim(n=1500, hr=2.0, seed=1, term="DMK-2021"):
    g = np.random.default_rng(seed)
    x = g.integers(0, 2, n)
    t = g.exponential(1.0 / (0.002 * np.where(x == 1, hr, 1.0)))
    c = 800
    df = pd.DataFrame({"term_id": term, "T": np.minimum(t, c).round().clip(1), "E1": (t < c).astype(int)})
    df["E2"] = df["E1"]
    df["union_dependent"] = x; df["continues_existing"] = g.integers(0, 2, n)
    df["promise_type"] = "administrative"; df["cost_band"] = "none"; df["specificity"] = "specific"
    return df


COVS = ["union_dependent", "continues_existing"]


def test_cox_recovers_known_hazard_ratio():
    f = fit_cox(_sim(), COVS, {}, ["DMK-2021"])
    hr = f.hazard_ratios().loc["union_dependent", "hr"]
    assert 1.7 < hr < 2.35


def test_fit_refuses_target_term_rows():
    df = pd.concat([_sim(), _sim(term="AIADMK-2016", seed=2)])
    with pytest.raises(LeakageError):
        fit_cox(df, COVS, {}, ["DMK-2021"])
    with pytest.raises(LeakageError):
        assert_only_terms(df, ["DMK-2021"])


def test_pace_factor_and_expected():
    assert pace_factor(23, 237, 20) == pytest.approx(43 / 257)
    assert pace_factor(10, 10, 20) == 1.0
    assert expected_events(np.array([0.9, 0.5])) == pytest.approx(0.6)


def test_conditional_prediction_matches_known_baseline():
    # exponential baseline: S(t)=exp(-0.002 t); nothing realised at the landmark -> predicted share is 1 - S(t)/S(m)
    S = lambda d: np.exp(-0.002 * np.array(d, dtype=float))[None, :].repeat(4, axis=0)
    got = backtest._predict_share(S([100])[:, 0], S([200, 300]), np.zeros(4, dtype=int), 1.0)
    assert got == pytest.approx(1 - np.exp(-0.002 * np.array([100, 200])))
    one_done = backtest._predict_share(S([100])[:, 0], S([200]), np.array([1, 0, 0, 0]), 1.0)
    assert one_done[0] == pytest.approx((1 + 3 * (1 - np.exp(-0.2))) / 4)


def test_model_package_never_opens_gold_labels():
    root = pathlib.Path(__file__).resolve().parents[1] / "src" / "ept" / "model"
    for f in root.glob("*.py"):
        assert not re.search(r"gold_(labels|relabel)|data/gold", f.read_text()), f.name


def test_matched_terms_picks_same_judge_term():
    from ept.model import project
    cfg = load_config()
    mk = lambda pid, cutoff, src, st: {"promise_id": pid, "cutoff_date": cutoff, "judge_source": src, "status": st}
    rows = [mk("TVK-2026-0001", "2026-10-10", "strong", "fulfilled"), mk("TVK-2026-0002", "2026-10-10", "strong", "not_started"),
            mk("DMK-2021-0001", "2021-10-07", "strong", "fulfilled"), mk("DMK-2021-0002", "2021-10-07", "strong", "not_started"),
            mk("DMK-2021-0003", "2021-10-07", "strong", "not_started"), mk("DMK-2021-0004", "2021-10-07", "strong", "not_started"),
            mk("AIADMK-2016-0001", "2016-10-23", "bulk", "fulfilled")]
    ids, share = project.matched_terms(cfg, rows, "TVK-2026", 5, 0.9)
    assert ids == ["DMK-2021"] and share == pytest.approx(0.25)
