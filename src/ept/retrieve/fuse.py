"""Fusion and selection (spec 04 §4.6, D-078): RRF of the BM25 and dense ranks, a per-document cap,
and up to `go_min` places for GOs that the ranking pushed out."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ept.config import Retrieve


@dataclass
class Candidate:
    pos: int  # position in the run's eligible arrays (chunk_id order)
    chunk_id: str
    doc_id: str
    is_go: bool
    dense_cos: float
    bm25_rank: Optional[int] = None
    bm25_score: Optional[float] = None
    bm25_query: Optional[int] = None
    dense_rank: Optional[int] = None
    rrf: float = 0.0
    go_reserved: bool = False

    def scores(self) -> dict[str, float]:
        """`retrievals.scores`: float values, keys omitted where they don't apply."""
        out = {"rrf": self.rrf, "dense_cos": self.dense_cos}
        if self.bm25_rank is not None:
            out.update(bm25_rank=float(self.bm25_rank), bm25_score=float(self.bm25_score),
                       bm25_query=float(self.bm25_query))
        if self.dense_rank is not None:
            out["dense_rank"] = float(self.dense_rank)
        if self.go_reserved:
            out["go_reserved"] = 1.0
        return out


@dataclass
class Selection:
    chunks: list[Candidate]  # final order, rank = index + 1
    cap_applied: bool = False  # a chunk was skipped because its document already had max_per_doc
    go_places: int = 0
    displaced: list[str] = field(default_factory=list)  # chunk ids replaced by GO places
    go_rule_ok: bool = True  # ≥ go_min GOs, or no addable GO left in the pool, or no non-GO left to replace


def fuse(cands: list[Candidate], r: Retrieve) -> list[Candidate]:
    """Set `rrf` and order: rrf desc, dense cosine desc, chunk_id."""
    for c in cands:
        c.rrf = ((r.rrf.w_bm25 / (r.rrf.k + c.bm25_rank) if c.bm25_rank is not None else 0.0)
                 + (r.rrf.w_dense / (r.rrf.k + c.dense_rank) if c.dense_rank is not None else 0.0))
    return sorted(cands, key=lambda c: (-c.rrf, -c.dense_cos, c.chunk_id))


def select(order: list[Candidate], r: Retrieve) -> Selection:
    """Top k with at most `max_per_doc` per document, then GO places from the top `go_pool`."""
    position = {c.chunk_id: i for i, c in enumerate(order)}
    chosen: list[Candidate] = []
    per_doc: dict[str, int] = {}
    cap_applied = False
    for c in order:
        if len(chosen) == r.k:
            break
        if per_doc.get(c.doc_id, 0) >= r.max_per_doc:
            cap_applied = True
            continue
        chosen.append(c)
        per_doc[c.doc_id] = per_doc.get(c.doc_id, 0) + 1
    sel = Selection(chosen, cap_applied)
    n_go = sum(c.is_go for c in chosen)
    if n_go < r.go_min:
        ids = {c.chunk_id for c in chosen}
        for g in order[: r.go_pool]:
            if n_go >= r.go_min:
                break
            if not g.is_go or g.chunk_id in ids or per_doc.get(g.doc_id, 0) >= r.max_per_doc:
                continue
            victims = [c for c in chosen if not c.is_go]
            if not victims:
                break
            # a GO left out of a full selection: it replaces the lowest-ranked selected non-GO (a GO and a
            # non-GO never share a document). With fewer than k selected, every unselected chunk was capped.
            victim = max(victims, key=lambda c: position[c.chunk_id])
            chosen.remove(victim)
            per_doc[victim.doc_id] -= 1
            sel.displaced.append(victim.chunk_id)
            g.go_reserved = True
            chosen.append(g)
            ids.add(g.chunk_id)
            per_doc[g.doc_id] = per_doc.get(g.doc_id, 0) + 1
            n_go += 1
            sel.go_places += 1
    sel.chunks = sorted(chosen, key=lambda c: position[c.chunk_id])
    sel.go_rule_ok = go_rule_ok(order, sel.chunks, r)
    return sel


def go_rule_ok(order: list[Candidate], chosen: list[Candidate], r: Retrieve) -> bool:
    """Independent check of §4.6 step 4 on a final selection."""
    if sum(c.is_go for c in chosen) >= r.go_min or not any(not c.is_go for c in chosen):
        return True
    ids = {c.chunk_id for c in chosen}
    per_doc: dict[str, int] = {}
    for c in chosen:
        per_doc[c.doc_id] = per_doc.get(c.doc_id, 0) + 1
    return not any(g.is_go and g.chunk_id not in ids and per_doc.get(g.doc_id, 0) < r.max_per_doc
                   for g in order[: r.go_pool])
