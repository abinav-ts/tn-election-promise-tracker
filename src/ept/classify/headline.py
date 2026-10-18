"""Headline cap (spec 03 §4.5, D-068).

Within a term, promises with `headline_signal` ≥ 1 are ranked by
  signal desc, cost band desc, appears in the front matter desc, promise_id asc;
the top `classify.headline_cap` are headline. "Appears in the front matter" = at least
`classify.headline_frontmatter_ratio` of the promise's distinct `source_text` words occur in the
front matter. `source_text` is used (not the English `text`) because it is in the front matter's
language. Signal 0 is never headline; `headline_rank` is set for every promise with signal ≥ 1.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from ept.extract.checks import norm
from ept.schema import COST_BANDS

_WORD = re.compile(r"[\w஀-௿]+")


def words(text: str) -> set[str]:
    return set(_WORD.findall(norm(text).lower()))


def frontmatter_overlap(source_text: str, fm_words: set[str]) -> float:
    w = words(source_text)
    return len(w & fm_words) / len(w) if w else 0.0


@dataclass(frozen=True)
class Candidate:
    promise_id: str
    signal: int
    cost_band: str
    in_front_matter: bool


def rank_key(c: Candidate) -> tuple:
    return (-c.signal, -COST_BANDS.index(c.cost_band), not c.in_front_matter, c.promise_id)


def assign(candidates: list[Candidate], cap: int) -> dict[str, tuple[bool, Optional[int]]]:
    """promise_id -> (headline, headline_rank)."""
    ranked = sorted((c for c in candidates if c.signal >= 1), key=rank_key)
    out: dict[str, tuple[bool, Optional[int]]] = {c.promise_id: (False, None) for c in candidates}
    for i, c in enumerate(ranked, 1):
        out[c.promise_id] = (i <= cap, i)
    return out
