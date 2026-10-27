"""Kaplan–Meier tables (spec 07 §4.2): share realised by month t, per term and by promise group."""

from __future__ import annotations

import numpy as np
import pandas as pd

from ept.config import Config
from ept.model.cox import km_survival

TABLE_MONTHS = [5, 6, 12, 24, 36, 48, 60]


def _realised_at(df: pd.DataFrame, event: str, days: np.ndarray) -> list[float]:
    km = km_survival(df, event)
    return [float(1 - v) for v in km.survival_function_at_times(days).values]


def km_tables(cfg: Config, df: pd.DataFrame) -> dict:
    m = cfg.settings.model
    dpm = m.days_per_month
    out: dict = {"months": TABLE_MONTHS, "terms": {}, "groups": {}}
    for term, d in df.groupby("term_id"):
        cens = int(d["T"].max()) if d["E1"].sum() == 0 else int(d.loc[d["E1"] == 0, "T"].max()) if (d["E1"] == 0).any() else int(d["T"].max())
        # a point for every month and one at the exact end of observation, so the curve reaches the end of the term
        # (AIADMK's term is 59.4 months, so a fixed month-60 point would be dropped and the line would stop at 48)
        months = list(range(1, int(cens / dpm) + 1))
        days = [round(t * dpm) for t in months]
        if cens > days[-1]:
            months.append(round(cens / dpm, 2))
            days.append(cens)
        days = np.array(days)
        entry = {"n": int(len(d)), "months": months}
        for ev in ("E1", "E2"):
            km = km_survival(d, ev)
            sf = km.survival_function_at_times(days).values
            ci = km.confidence_interval_survival_function_
            lo = [float(1 - ci.iloc[:, 1].asof(x)) if x >= ci.index.min() else 0.0 for x in days]
            hi = [float(1 - ci.iloc[:, 0].asof(x)) if x >= ci.index.min() else 0.0 for x in days]
            entry[ev] = {"events": int(d[ev].sum()), "realised": [float(1 - v) for v in sf], "lo": lo, "hi": hi}
        out["terms"][term] = entry
        gtab = {}
        for var in m.group_vars:
            for level, g in d.groupby(var):
                if len(g) < m.min_group_size:
                    continue
                gtab[f"{var}={level}"] = {"n": int(len(g)), "events": int(g["E1"].sum()),
                                          "realised": _realised_at(g, "E1", days)}
        out["groups"][term] = gtab
    return out
