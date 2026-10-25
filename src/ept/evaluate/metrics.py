"""Plain metrics (spec 06 §H4): counts, percentages, Wilson intervals, one confusion matrix. Pure functions."""

from __future__ import annotations

import datetime as dt
import math
from collections import Counter
from typing import Optional

import numpy as np

from ept.dates import parse_iso, period_end, period_start
from ept.evaluate.gold import E1


def wilson(k: int, n: int, z: float = 1.96) -> tuple[Optional[float], Optional[float], Optional[float]]:
    """Share k/n with its 95 % Wilson interval."""
    if n == 0:
        return None, None, None
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    w = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return p, (c - w) / d, (c + w) / d


def _ci(k: int, n: int) -> dict:
    p, lo, hi = wilson(k, n)
    return {"k": k, "n": n, "p": p, "lo": lo, "hi": hi}


def e1_table(pairs: list[tuple[str, str]]) -> dict:
    """pairs = (gold_status, judge_status). Positive = realised (E1)."""
    tp = sum(g in E1 and j in E1 for g, j in pairs)
    fn = sum(g in E1 and j not in E1 for g, j in pairs)
    fp = sum(g not in E1 and j in E1 for g, j in pairs)
    tn = sum(g not in E1 and j not in E1 for g, j in pairs)
    return {"tp": tp, "fn": fn, "fp": fp, "tn": tn, "n": len(pairs),
            "accuracy": _ci(tp + tn, len(pairs)), "recall": _ci(tp, tp + fn),
            "precision": _ci(tp, tp + fp), "specificity": _ci(tn, tn + fp)}


def status_agreement(pairs: list[tuple[str, str]]) -> dict:
    same = sum(g == j for g, j in pairs)
    merge = lambda s: "not_started_or_unverifiable" if s in ("not_started", "unverifiable") else s
    same_m = sum(merge(g) == merge(j) for g, j in pairs)
    conf = Counter((g, j) for g, j in pairs)
    return {"exact": _ci(same, len(pairs)), "exact_merging_not_started_unverifiable": _ci(same_m, len(pairs)),
            "confusion": [{"gold": g, "judge": j, "n": n} for (g, j), n in sorted(conf.items())]}


def _mid(date: str, precision: str) -> dt.date:
    a, b = period_start(date, precision), period_end(date, precision)
    return a + (b - a) / 2


def date_error(rows: list[dict], within: int) -> dict:
    """rows with gold/judge date + precision, for promises both call realised. Differences in days (judge - gold)."""
    diffs = []
    for r in rows:
        if r["gold_date"] and r["judge_date"]:
            diffs.append((_mid(r["judge_date"], r["judge_precision"] or "day") -
                          _mid(r["gold_date"], r["gold_precision"] or "day")).days)
    if not diffs:
        return {"n": 0}
    a = np.array(diffs)
    return {"n": len(a), "median_abs_days": float(np.median(np.abs(a))), "median_signed_days": float(np.median(a)),
            f"within_{within}_days": _ci(int((np.abs(a) <= within).sum()), len(a))}


def realised_by(status: str, date: Optional[str], precision: Optional[str], cutoff: dt.date) -> bool:
    return status in E1 and bool(date) and period_start(date, precision or "day") <= cutoff


def split_accuracy(items: list[tuple[str, bool]], small_n: int) -> dict:
    """items = (group, judge E1 agrees with gold E1). Groups below small_n print as too few."""
    out = {}
    for g in sorted({g for g, _ in items}):
        ok = [a for gg, a in items if gg == g]
        out[g] = {"n": len(ok), "accuracy": "too few" if len(ok) < small_n else sum(ok) / len(ok)}
    return out


def bucket(r: dict) -> str:
    """One bucket per disagreement, first match wins (spec 06 §H5)."""
    if r.get("in_corpus") is False:
        return "evidence_outside_corpus"
    if r.get("unsure"):
        return "label_uncertain"
    if r.get("evidence_chunks_missing"):
        return "retrieval_miss"
    if r.get("evidence_checked"):
        return "judge_error"
    return "other"


def weighted_e1_accuracy(rows: list[dict], population: dict[str, dict[str, float]]) -> dict:
    """Per term: re-weight each specificity stratum by population share / sample share (post-stratification);
    pooled = the mean of the terms (equal term weight)."""
    per = {}
    for t, strata in population.items():
        tr = [r for r in rows if r["term_id"] == t]
        num = den = 0.0
        for s, share in strata.items():
            sr = [r for r in tr if r["specificity"] == s]
            if sr:
                num += share * sum(r["e1_agree"] for r in sr) / len(sr)
                den += share
        if den:
            per[t] = num / den
    return {"per_term": per, "pooled": float(np.mean(list(per.values()))) if per else None}
