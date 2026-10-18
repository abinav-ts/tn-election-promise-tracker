"""Deterministic batches for `ept classify run` (spec 03 §4.3).

Promises in ID order, grouped by unit (`parent_group`); a batch closes once it holds at least
`classify.promises_per_call` promises, so a unit is never split and a batch may run over by one unit.
Same promises -> same batches -> same cache keys.

The prompt sees batch-local aliases (P01…, U01…) instead of promise and unit IDs, because those IDs
carry the term name (`DMK-2021-0001`) and the template must stay party- and term-neutral (§5, §9.2).
Answers are matched back by alias, never by position (C1).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional

from ept.extract.units import Unit
from ept.schema import Promise


@dataclass(frozen=True)
class Group:
    unit_id: str
    promises: tuple[Promise, ...]


@dataclass(frozen=True)
class Batch:
    groups: tuple[Group, ...]

    @property
    def promises(self) -> list[Promise]:
        return [p for g in self.groups for p in g.promises]

    def aliases(self) -> dict[str, str]:
        """alias -> promise_id, in batch order."""
        return {f"P{i:02d}": p.promise_id for i, p in enumerate(self.promises, 1)}


def group_by_unit(promises: list[Promise]) -> list[Group]:
    groups: list[Group] = []
    for p in sorted(promises, key=lambda p: p.promise_id):
        key = p.parent_group or p.promise_id
        if groups and groups[-1].unit_id == key:
            groups[-1] = Group(key, groups[-1].promises + (p,))
        else:
            groups.append(Group(key, (p,)))
    return groups


def limit_promises(promises: list[Promise], limit: Optional[int]) -> list[Promise]:
    """The first `limit` promises in ID order, rounded up to a whole unit."""
    if limit is None:
        return sorted(promises, key=lambda p: p.promise_id)
    out: list[Promise] = []
    for g in group_by_unit(promises):
        if len(out) >= limit:
            break
        out += g.promises
    return out


def make_batches(promises: list[Promise], per_call: int) -> list[Batch]:
    batches: list[Batch] = []
    current: list[Group] = []
    n = 0
    for g in group_by_unit(promises):
        current.append(g)
        n += len(g.promises)
        if n >= per_call:
            batches.append(Batch(tuple(current)))
            current, n = [], 0
    if current:
        batches.append(Batch(tuple(current)))
    return batches


def single(batch: Batch, promise: Promise) -> Batch:
    """A batch holding one promise of `batch` (its unit text goes with it): the retry-alone call."""
    return Batch((Group(promise.parent_group or promise.promise_id, (promise,)),))


def payload(batch: Batch, units: dict[str, Unit]) -> str:
    """The `units` variable of the prompt: unit text once per unit, then its promises."""
    alias_of = {pid: a for a, pid in batch.aliases().items()}
    rows = []
    for i, g in enumerate(batch.groups, 1):
        unit = units.get(g.unit_id)
        rows.append({
            "unit": f"U{i:02d}",
            "section": g.promises[0].section,
            "unit_text": unit.text if unit else "",
            "promises": [{"id": alias_of[p.promise_id], "text": p.text, "source_text": p.source_text,
                          "source_lang": p.source_lang} for p in g.promises],
        })
    return json.dumps(rows, ensure_ascii=False, indent=1)


def front_matter(units: list[Unit]) -> str:
    """The term's front-matter units, joined (the headline signal's third point, §4.5)."""
    return "\n\n".join(u.text for u in units if u.marker == "front_matter").strip() or "(none)"
