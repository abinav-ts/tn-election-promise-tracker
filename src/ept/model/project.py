"""TVK projection (spec 07 §4.5): pooled two-term Cox model, equal-weight baselines, pace update, bootstrap band."""

from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd

from ept.config import Config
from ept.model import data
from ept.model.cox import CoxFit, expected_events, fit_cox, pace_factor


def _rng(seed: str, salt: int = 0) -> np.random.Generator:
    return np.random.default_rng(int(hashlib.sha256(f"{seed}:{salt}".encode()).hexdigest()[:12], 16))


def project_curve(fit: CoxFit, tvk: pd.DataFrame, snap_day: int, months: list[int], dpm: float, c: float,
                  use_pace: bool) -> dict:
    """Observed share at the snapshot plus the expected extra share by each month; also k, O, E."""
    days = np.array([snap_day] + [round(t * dpm) for t in months])
    S = fit.survival(tvk, days)
    S0, St = S[:, 0], S[:, 1:]
    realised = tvk["E1"].values.astype(int)
    O, E = float(realised.sum()), expected_events(S0)
    k = pace_factor(O, E, c) if use_pace else 1.0
    cond = np.clip(St[realised == 0] / np.clip(S0[realised == 0][:, None], 1e-12, None), 0, 1) ** k
    share = (O + (1 - cond).sum(axis=0)) / len(tvk)
    return {"k": k, "observed": O, "expected": E, "share": share.tolist(), "per_row_extra": None,
            "_extra": (1 - cond), "_unrealised": realised == 0}


def project(cfg: Config, tbl: pd.DataFrame, event: str = "E1") -> dict:
    m = cfg.settings.model
    dpm = m.days_per_month
    train_terms = [t.term_id for t in cfg.settings.terms if str(t.role) in ("train", "backtest")]
    train = tbl[tbl.term_id.isin(train_terms)]
    tvk_id = next(t.term_id for t in cfg.settings.terms if str(t.role) == "project")
    tvk = tbl[tbl.term_id == tvk_id].reset_index(drop=True)
    snap_day = data.censor_days(cfg, tvk_id)
    months = list(range(6, m.horizon_months + 1))
    fit = fit_cox(train, m.covariates, m.reference, train_terms, strata="term_id", event=event)
    out: dict = {"term": tvk_id, "train_terms": train_terms, "snapshot_day": snap_day, "months": months,
                 "n": int(len(tvk)), "observed_events": int(tvk[event].sum()),
                 "observed_share_snapshot": float(tvk[event].mean()), "hazard_ratios": fit.hazard_ratios().round(4).reset_index().to_dict("records")}
    for label, c, use in [("no_update", m.pace_prior_events, False), ("pace_update", m.pace_prior_events, True),
                          *[(f"pace_update_c{x}", x, True) for x in m.pace_prior_sensitivity]]:
        r = project_curve(fit, tvk, snap_day, months, dpm, c, use)
        extra, un = r.pop("_extra"), r.pop("_unrealised")
        r.pop("per_row_extra")
        types = {}
        for typ in sorted(tvk["promise_type"].unique()):
            idx = np.where(tvk["promise_type"].values == typ)[0]
            sel = [j for j, i in enumerate(np.where(un)[0]) if tvk["promise_type"].values[i] == typ]
            n_t = len(idx)
            types[typ] = {"n": n_t, "share": ((tvk[event].values[idx].sum() + extra[sel].sum(axis=0)) / n_t).tolist()}
        r["by_promise_type"] = types
        out[label] = r
    # bootstrap over training promises, resampled within term (fitting uncertainty only)
    n_ok, curves = 0, {"no_update": [], "pace_update": []}
    for b in range(m.bootstrap.n):
        g = _rng(m.bootstrap.seed, b)
        parts = [d.iloc[g.integers(0, len(d), len(d))] for _, d in train.groupby("term_id")]
        try:
            bf = fit_cox(pd.concat(parts, ignore_index=True), m.covariates, m.reference, train_terms,
                         strata="term_id", event=event)
            for label, use in (("no_update", False), ("pace_update", True)):
                curves[label].append(project_curve(bf, tvk, snap_day, months, dpm, m.pace_prior_events, use)["share"])
            n_ok += 1
        except Exception:  # a resample that fails to converge is skipped and counted
            continue
    lo_q, hi_q = m.bootstrap.band
    out["bootstrap"] = {"n_requested": m.bootstrap.n, "n_ok": n_ok, "band": [lo_q, hi_q]}
    for label, arr in curves.items():
        if arr:
            a = np.array(arr)
            out[label]["lo"] = np.quantile(a, lo_q, axis=0).tolist()
            out[label]["hi"] = np.quantile(a, hi_q, axis=0).tolist()
    return out
