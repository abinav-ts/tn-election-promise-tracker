"""Cox model with a fixed, small covariate set (spec 07 §4.3), plus the survival maths the backtest and
projection share. All fits go through `fit_cox`, which refuses frames that contain a term it was not told to use."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd
from lifelines import CoxPHFitter, KaplanMeierFitter

BOOL_COVS = ("union_dependent", "continues_existing", "headline")


class LeakageError(RuntimeError):
    pass


def assert_only_terms(df: pd.DataFrame, allowed: list[str]) -> None:
    """Rule 5: a fit receives training-term rows only."""
    extra = set(df["term_id"].unique()) - set(allowed)
    if extra:
        raise LeakageError(f"fit frame contains term(s) {sorted(extra)} outside the training set {allowed}")


def levels_of(df: pd.DataFrame, covs: list[str], reference: dict[str, str]) -> dict[str, list[str]]:
    """Non-reference levels of each categorical covariate, from the training frame."""
    out: dict[str, list[str]] = {}
    for c in covs:
        if c in BOOL_COVS:
            continue
        vals = sorted(df[c].astype(str).unique())
        ref = reference.get(c, vals[0])
        out[c] = [v for v in vals if v != ref]
    return out


def design(df: pd.DataFrame, covs: list[str], levels: dict[str, list[str]]) -> pd.DataFrame:
    """Numeric design matrix with the columns fixed by `levels` (unseen levels fall on the reference)."""
    X = pd.DataFrame(index=df.index)
    for c in covs:
        if c in BOOL_COVS:
            X[c] = df[c].astype(int)
        else:
            for v in levels[c]:
                X[f"{c}={v}"] = (df[c].astype(str) == v).astype(int)
    return X


@dataclass
class CoxFit:
    model: CoxPHFitter
    covs: list[str]
    levels: dict[str, list[str]]
    terms: list[str]
    strata: Optional[str] = None
    columns: list[str] = field(default_factory=list)

    def X(self, df: pd.DataFrame) -> pd.DataFrame:
        return design(df, self.covs, self.levels)

    def hazard_ratios(self) -> pd.DataFrame:
        s = self.model.summary
        return pd.DataFrame({"hr": np.exp(s["coef"]), "lo": s["exp(coef) lower 95%"],
                             "hi": s["exp(coef) upper 95%"], "p": s["p"]})

    def rel_hazard(self, df: pd.DataFrame) -> np.ndarray:
        X = self.X(df)
        if self.strata:
            X = X.assign(**{self.strata: df[self.strata].values})
        return np.asarray(self.model.predict_partial_hazard(X)).ravel()

    def baseline(self, days: np.ndarray, weights: Optional[dict[str, float]] = None) -> np.ndarray:
        """Cumulative baseline hazard at `days` (a step function). With strata: the weighted mean over strata
        (equal weights by default)."""
        H = self.model.baseline_cumulative_hazard_
        idx = H.index.values
        pos = np.searchsorted(idx, days, side="right") - 1
        cols = list(H.columns)
        mats = []
        for j, c in enumerate(cols):
            v = H.iloc[:, j].values
            mats.append(np.where(pos >= 0, v[np.clip(pos, 0, None)], 0.0))
        w = np.ones(len(cols)) / len(cols)
        if weights:
            w = np.array([weights[str(c[0] if isinstance(c, tuple) else c)] for c in cols], dtype=float)
            w = w / w.sum()
        return np.tensordot(w, np.array(mats), axes=1)

    def survival(self, df: pd.DataFrame, days: np.ndarray, weights: Optional[dict[str, float]] = None) -> np.ndarray:
        """S(t | x) for each row of `df` at each of `days`: shape (n, len(days))."""
        return np.exp(-np.outer(self.rel_hazard(df), self.baseline(np.asarray(days), weights)))


def fit_cox(df: pd.DataFrame, covs: list[str], reference: dict[str, str], train_terms: list[str],
            strata: Optional[str] = None, event: str = "E1", penalizer: float = 0.0) -> CoxFit:
    assert_only_terms(df, train_terms)
    levels = levels_of(df, covs, reference)
    X = design(df, covs, levels)
    frame = X.assign(T=df["T"].values, E=df[event].values)
    if strata:
        frame[strata] = df[strata].values
    m = CoxPHFitter(penalizer=penalizer)
    m.fit(frame, duration_col="T", event_col="E", strata=[strata] if strata else None)
    return CoxFit(m, covs, levels, list(train_terms), strata, list(X.columns))


def km_survival(df: pd.DataFrame, event: str = "E1") -> KaplanMeierFitter:
    return KaplanMeierFitter().fit(df["T"], df[event])


def expected_events(S_at_day: np.ndarray) -> float:
    """Model-expected number of events by a day: sum of 1 - S(day | x) over promises."""
    return float(np.sum(1.0 - S_at_day))


def pace_factor(observed: float, expected: float, prior: float) -> float:
    """k = (O + c) / (E + c): a damped ratio of observed to expected events (spec 07 §4.5)."""
    return float((observed + prior) / (expected + prior))
