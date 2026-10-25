"""Reverse backtest (spec 07 §4.4): fit on the training term only, predict the target term from its landmark states."""

from __future__ import annotations

import numpy as np
import pandas as pd
from lifelines.utils import concordance_index

from ept.config import Config
from ept.dates import add_months
from ept.model import data
from ept.model.cox import (CoxFit, assert_only_terms, expected_events, fit_cox, km_survival, pace_factor)


def _months_grid(cfg: Config, censor: int) -> list[int]:
    m = cfg.settings.model
    return list(range(1, min(m.horizon_months, int(censor / m.days_per_month)) + 1))


def _predict_share(S_m: np.ndarray, S_t: np.ndarray, realised: np.ndarray, k: float) -> np.ndarray:
    """Predicted share realised at each t: realised at m + sum over unrealised of 1 - (S(t)/S(m))^k."""
    n = len(realised)
    un = realised == 0
    cond = np.clip(S_t[un] / np.clip(S_m[un][:, None], 1e-12, None), 0.0, 1.0) ** k
    return (realised.sum() + (1.0 - cond).sum(axis=0)) / n


def reverse_backtest(cfg: Config, tbl: pd.DataFrame, rows: list[dict], train_term: str, target_term: str,
                     event: str = "E1") -> dict:
    m = cfg.settings.model
    dpm = m.days_per_month
    train = tbl[tbl.term_id == train_term]
    target = tbl[tbl.term_id == target_term].reset_index(drop=True)
    fit = fit_cox(train, m.covariates, m.reference, [train_term], event=event)  # rule 5: train term only
    assert_only_terms(train, [train_term])
    sworn = cfg.term(target_term).sworn_in
    censor = data.censor_days(cfg, target_term)
    grid = _months_grid(cfg, censor)
    t_days = np.array([round(t * dpm) for t in grid])
    obs = np.array([float(((target["T"] <= d) & (target[event] == 1)).mean()) for d in t_days])
    km = km_survival(train, event)
    unseen = int(sum((~target[c].astype(str).isin(train[c].astype(str))).sum()
                     for c in m.covariates if c not in ("union_dependent", "continues_existing")))
    result: dict = {"train": train_term, "target": target_term, "event": event, "n_train": int(len(train)),
                    "n_target": int(len(target)), "unseen_level_rows": unseen, "months": grid,
                    "observed": obs.tolist(), "landmarks": {}}
    risk = fit.rel_hazard(target)
    result["concordance"] = float(concordance_index(target["T"], -risk, target[event]))
    for lm in m.landmarks_months:
        state = data.landmark_state(cfg, target_term, lm, rows).reindex(target["promise_id"]).fillna(0).astype(int).values
        day_m = (add_months(sworn, lm) - sworn).days
        later = [i for i, t in enumerate(grid) if t > lm]
        days_all = np.concatenate([[day_m], t_days[later]])
        S = fit.survival(target, days_all)
        S_m, S_t = S[:, 0], S[:, 1:]
        base = np.repeat(km.survival_function_at_times(days_all).values[None, :], len(target), axis=0)
        E = expected_events(S_m)
        entry = {"day": int(day_m), "realised_at_landmark": int(state.sum()), "expected": E, "t_months": [grid[i] for i in later],
                 "observed": [float(obs[i]) for i in later]}
        for label, c in [("c=" + str(m.pace_prior_events), m.pace_prior_events),
                         *[(f"c={x}", x) for x in m.pace_prior_sensitivity]]:
            entry["k_" + label] = pace_factor(float(state.sum()), E, c)
        k = entry[f"k_c={m.pace_prior_events}"]
        entry["pred_model"] = _predict_share(S_m, S_t, state, 1.0).tolist()
        entry["pred_model_pace"] = _predict_share(S_m, S_t, state, k).tolist()
        entry["pred_baseline"] = _predict_share(base[:, 0], base[:, 1:], state, 1.0).tolist()
        o = np.array(entry["observed"])
        for key in ("pred_model", "pred_model_pace", "pred_baseline"):
            entry["mae_" + key[5:]] = float(np.mean(np.abs(np.array(entry[key]) - o)) * 100)
        result["landmarks"][str(lm)] = entry
    return result
