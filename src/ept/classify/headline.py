"""Headline cap (spec 03 §4.5, D-068, D-072).

Within a term, promises with `headline_signal` ≥ 1 are ranked by
  signal desc, cost band desc, promise_id asc;
the top `classify.headline_cap` are headline. Signal 0 is never headline; `headline_rank` is set
for every promise with signal ≥ 1. The front matter plays no part (D-072: the manifestos' front
matter ranges from a bare title to an 11,000-character preface, so a front-matter point or
tie-break would favour some terms).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ept.schema import COST_BANDS


@dataclass(frozen=True)
class Candidate:
    promise_id: str
    signal: int
    cost_band: str


def rank_key(c: Candidate) -> tuple:
    return (-c.signal, -COST_BANDS.index(c.cost_band), c.promise_id)


def assign(candidates: list[Candidate], cap: int) -> dict[str, tuple[bool, Optional[int]]]:
    """promise_id -> (headline, headline_rank)."""
    ranked = sorted((c for c in candidates if c.signal >= 1), key=rank_key)
    out: dict[str, tuple[bool, Optional[int]]] = {c.promise_id: (False, None) for c in candidates}
    for i, c in enumerate(ranked, 1):
        out[c.promise_id] = (i <= cap, i)
    return out
