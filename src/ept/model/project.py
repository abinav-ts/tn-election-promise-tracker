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


def matched_terms(cfg: Config, rows: list[dict], target: str, months: int, min_share: float,
                  totals: dict[str, int] | None = None) -> tuple[list[str], float]:
    """Scenario B (D-114): completed terms whose landmark-`months` rows used the same judge as the target's snapshot
    rows (>= `min_share` of them); returns their ids and the mean documented (landmark) E1 share."""
    from ept.dates import add_months
    from ept.model.data import E1_STATUSES

    def at(term_id: str, cutoff: str) -> list[dict]:
        return [r for r in rows if r["promise_id"].startswith(term_id + "-") and r["cutoff_date"] == cutoff]

    if totals is None:
        cov = data.load_covariates(cfg)
        totals = cov.groupby("term_id").size().to_dict()
    snap = add_months(cfg.term(target).sworn_in, months).isoformat()
    t_rows = at(target, snap)
    judge = max({r["judge_source"] for r in t_rows}, key=lambda j: sum(r["judge_source"] == j for r in t_rows))
    ids, shares = [], []
    for t in cfg.settings.terms:
        if t.term_id == target or t.term_end is None:
            continue
        rr = at(t.term_id, add_months(t.sworn_in, months).isoformat())
        # D-123: the landmark must be covered (not a subset), else its documented share is biased
        covered = len(rr) / totals.get(t.term_id, len(rr)) if rr else 0.0
        if rr and covered >= min_share and sum(r["judge_source"] == judge for r in rr) / len(rr) >= min_share:
            ids.append(t.term_id)
            shares.append(sum(r["status"] in E1_STATUSES for r in rr) / len(rr))
    return ids, float(np.mean(shares)) if shares else float("nan")


def pace_indicator(cfg: Config, rows: list[dict], tvk: pd.DataFrame, event: str = "E1") -> dict:
    """The pace strip (spec 07 §4.5, D-121): TVK's documented month-5 count against what the completed terms judged by
    the same judge had documented at the same point. k = (O + c)/(E + c) is the posterior mean of a Gamma(c, c) prior
    updated with O ~ Poisson(k E); the 80 % interval is that posterior's 10th-90th percentile."""
    from scipy.stats import gamma

    from ept.dates import add_months
    from ept.model.data import E1_STATUSES

    m = cfg.settings.model
    tvk_id = str(tvk["term_id"].iloc[0])
    month = m.landmarks_months[0]
    totals_all = data.load_covariates(cfg).groupby("term_id").size().to_dict()
    ids, share = matched_terms(cfg, rows, tvk_id, month, m.matched_min_same_judge, totals_all)
    O, N, c = float(tvk[event].sum()), len(tvk), float(m.pace_prior_events)
    shares = {}
    for t in cfg.settings.terms:
        cut = add_months(t.sworn_in, month).isoformat()
        rr = [r for r in rows if r["promise_id"].startswith(t.term_id + "-") and r["cutoff_date"] == cut]
        if rr:
            judges = {}
            for r in rr:
                judges[r["judge_source"]] = judges.get(r["judge_source"], 0) + 1
            shares[t.term_id] = {"n": len(rr), "of": int(totals_all.get(t.term_id, len(rr))),
                                 "documented_share": sum(r["status"] in E1_STATUSES for r in rr) / len(rr),
                                 "judge_source": judges}
    out = {"month": month, "observed": O, "n": N, "observed_share": O / N, "matched_terms": ids,
           "documented_share_by_term": shares, "prior_events": c}
    if ids:
        E = share * N
        d = gamma(c + O, scale=1.0 / (c + E))
        out.update(expected=E, k=(c + O) / (c + E), k_lo=float(d.ppf(0.10)), k_hi=float(d.ppf(0.90)),
                   p_k_ge_1=float(1 - d.cdf(1.0)))
    return out


def project_curve(fit: CoxFit, tvk: pd.DataFrame, snap_day: int, months: list[int], dpm: float, c: float,
                  use_pace: bool, expected_override: float | None = None) -> dict:
    """Observed share at the snapshot plus the expected extra share by each month; also k, O, E."""
    days = np.array([snap_day] + [round(t * dpm) for t in months])
    S = fit.survival(tvk, days)
    S0, St = S[:, 0], S[:, 1:]
    realised = tvk["E1"].values.astype(int)
    O = float(realised.sum())
    E = expected_events(S0) if expected_override is None else float(expected_override)
    k = pace_factor(O, E, c) if use_pace else 1.0
    cond = np.clip(St[realised == 0] / np.clip(S0[realised == 0][:, None], 1e-12, None), 0, 1) ** k
    share = (O + (1 - cond).sum(axis=0)) / len(tvk)
    return {"k": k, "observed": O, "expected": E, "share": share.tolist(), "per_row_extra": None,
            "_extra": (1 - cond), "_unrealised": realised == 0}


def project(cfg: Config, tbl: pd.DataFrame, event: str = "E1", rows: list[dict] | None = None) -> dict:
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
    rows = rows if rows is not None else data.load_final(cfg)
    m_ids, m_share = matched_terms(cfg, rows, tvk_id, m.landmarks_months[0], m.matched_min_same_judge)
    E_matched = m_share * len(tvk)
    out["matched"] = {"terms": m_ids, "documented_share_month5": m_share, "expected": E_matched}
    out["pace"] = pace_indicator(cfg, rows, tvk, event)
    variants = [("no_update", m.pace_prior_events, False, None), ("pace_update", m.pace_prior_events, True, None),
                *[(f"pace_update_c{x}", x, True, None) for x in m.pace_prior_sensitivity]]
    if m_ids:
        variants += [("matched_update", m.pace_prior_events, True, E_matched),
                     *[(f"matched_update_c{x}", x, True, E_matched) for x in m.pace_prior_sensitivity]]
    for label, c, use, eo in variants:
        r = project_curve(fit, tvk, snap_day, months, dpm, c, use, eo)
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
    n_ok, curves = 0, {"no_update": [], "pace_update": [], **({"matched_update": []} if m_ids else {})}
    for b in range(m.bootstrap.n):
        g = _rng(m.bootstrap.seed, b)
        parts = [d.iloc[g.integers(0, len(d), len(d))] for _, d in train.groupby("term_id")]
        try:
            bf = fit_cox(pd.concat(parts, ignore_index=True), m.covariates, m.reference, train_terms,
                         strata="term_id", event=event)
            for label, use, eo in (("no_update", False, None), ("pace_update", True, None),
                                   *((("matched_update", True, E_matched),) if m_ids else ())):
                curves[label].append(project_curve(bf, tvk, snap_day, months, dpm, m.pace_prior_events, use, eo)["share"])
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
