"""Analysis table (spec 07 §4.1): one row per promise with event time, censoring and covariates.

Reads only the final verdict export and the frozen classification (manifesto-derived covariates, rule 3).
Gold labels are never read here (spec 07 §6).
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Optional

import pandas as pd

from ept.config import Config
from ept.dates import add_months, parse_iso, period_end, period_start

E1_STATUSES = {"fulfilled", "partial", "diluted"}
E2_STATUSES = {"fulfilled"}


def newest_final(cfg: Config) -> Path:
    pattern = cfg.settings.paths.final_verdicts_glob
    files = sorted(cfg.root.glob(pattern))
    if not files:
        raise FileNotFoundError(f"no final verdict export matches {pattern} (run `ept judge final`)")
    return files[-1]


def load_final(cfg: Config) -> list[dict]:
    with newest_final(cfg).open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def load_covariates(cfg: Config) -> pd.DataFrame:
    rows = []
    for term in cfg.settings.terms:
        path = cfg.root / cfg.settings.paths.frozen / f"classification_{term.term_id}.jsonl"
        with path.open(encoding="utf-8") as f:
            for line in f:
                r = json.loads(line)
                rows.append({"promise_id": r["promise_id"], "term_id": term.term_id,
                             **{k: r[k] for k in ("sector", "promise_type", "specificity", "cost_band",
                                                  "union_dependent", "continues_existing", "headline")}})
    return pd.DataFrame(rows)


def snapshot_date(cfg: Config, term_id: str) -> dt.date:
    """Right-censoring date: `term_end`, or for the running term its month-5 landmark (the corpus snapshot)."""
    term = cfg.term(term_id)
    if term.term_end is not None:
        return term.term_end
    return add_months(term.sworn_in, cfg.settings.retrieve.landmarks_months[term_id][0])


def censor_days(cfg: Config, term_id: str) -> int:
    return (snapshot_date(cfg, term_id) - cfg.term(term_id).sworn_in).days


def event_days(realisation_date: str, precision: str, sworn_in: dt.date, censor: int, mode: str = "midpoint") -> int:
    """Event time in days since `sworn_in`. Coarse dates use the middle (or start/end) of their period,
    clipped to [1, censor] so a year-precision date before the swearing-in becomes day 1."""
    if precision == "day":
        d = parse_iso(realisation_date)
    else:
        a, b = period_start(realisation_date, precision), period_end(realisation_date, precision)
        d = a if mode == "start" else b if mode == "end" else a + (b - a) / 2
    return int(min(max((d - sworn_in).days, 1), censor))


def _term_rows(rows: list[dict], term_id: str, term_end: Optional[dt.date], snap: dt.date) -> dict[str, dict]:
    """The comparison row per promise: full term (null cutoff) for completed terms, the snapshot cutoff for TVK."""
    want = None if term_end is not None else snap.isoformat()
    return {r["promise_id"]: r for r in rows
            if r["promise_id"].startswith(term_id + "-") and r["cutoff_date"] == want}


def analysis_table(cfg: Config, mode: Optional[str] = None, rows: Optional[list[dict]] = None) -> pd.DataFrame:
    mode = mode or cfg.settings.model.coarse_dates
    rows = rows if rows is not None else load_final(cfg)
    cov = load_covariates(cfg).set_index("promise_id")
    out = []
    for term in cfg.settings.terms:
        snap = snapshot_date(cfg, term.term_id)
        cens = censor_days(cfg, term.term_id)
        by = _term_rows(rows, term.term_id, term.term_end, snap)
        for pid, r in by.items():
            e1 = r["status"] in E1_STATUSES
            if e1 != bool(r.get("realisation_date")):
                raise ValueError(f"{pid}: a realised status needs a date and no other status may have one")
            t = event_days(r["realisation_date"], r["date_precision"], term.sworn_in, cens, mode) if e1 else cens
            out.append({"promise_id": pid, "term_id": term.term_id, "T": t, "E1": int(e1),
                        "E2": int(r["status"] in E2_STATUSES), "status": r["status"],
                        "date_precision": r.get("date_precision"), "judge_source": r["judge_source"],
                        **cov.loc[pid].drop("term_id").to_dict()})
    df = pd.DataFrame(out)
    return df.sort_values("promise_id").reset_index(drop=True)


def landmark_state(cfg: Config, term_id: str, months: int, rows: Optional[list[dict]] = None) -> pd.Series:
    """Realised-by-landmark flag (E1) per promise from the final run's row AT that cutoff only (rule 2)."""
    rows = rows if rows is not None else load_final(cfg)
    cutoff = add_months(cfg.term(term_id).sworn_in, months).isoformat()
    s = {r["promise_id"]: int(r["status"] in E1_STATUSES) for r in rows
         if r["promise_id"].startswith(term_id + "-") and r["cutoff_date"] == cutoff}
    return pd.Series(s, name=f"realised_m{months}")


def judge_source_table(cfg: Config, rows: Optional[list[dict]] = None) -> list[dict]:
    """Share of final rows by judge source per term × cutoff (spec 07 §4.7)."""
    rows = rows if rows is not None else load_final(cfg)
    df = pd.DataFrame(rows)
    df["term"] = df["promise_id"].str.rsplit("-", n=1).str[0]
    df["cutoff"] = df["cutoff_date"].fillna("full")
    g = df.groupby(["term", "cutoff", "judge_source"]).size().unstack(fill_value=0)
    return [{"term": t, "cutoff": c, **{k: int(v) for k, v in r.items()}, "n": int(r.sum())}
            for (t, c), r in g.iterrows()]
