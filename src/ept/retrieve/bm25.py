"""BM25 (spec 04 §4.4): token cache, and an Okapi index built per run on that run's eligible chunks only,
so document frequencies and lengths never include a chunk the run may not see (rule 2)."""

from __future__ import annotations

import gzip
import json
from typing import Optional

import numpy as np

from ept.config import Bm25Cfg, Config
from ept.retrieve import tokenize as tok


def _meta(h: str) -> dict[str, str]:
    return {"tokenizer": tok.fingerprint(), "index_text_hash": h}


def write_token_cache(cfg: Config, ids: list[str], texts: list[str], h: str) -> None:
    path = cfg.path("bm25_tokens")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with gzip.open(tmp, "wt", encoding="utf-8") as f:
        f.write(json.dumps({"_meta": _meta(h)}) + "\n")
        for cid, text in zip(ids, texts):
            f.write(json.dumps({"chunk_id": cid, "tokens": tok.tokenize(text)}) + "\n")
    tmp.replace(path)


def _read_meta(cfg: Config) -> Optional[dict[str, str]]:
    path = cfg.path("bm25_tokens")
    if not path.exists():
        return None
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return json.loads(f.readline()).get("_meta")


def token_cache_ok(cfg: Config, h: str) -> bool:
    return _read_meta(cfg) == _meta(h)


def load_tokens(cfg: Config, ids: list[str], h: str) -> list[list[str]]:
    """Tokens aligned with `ids` (chunk_id order); refuses a cache built from other texts or tokeniser."""
    from ept.retrieve.dense import IndexMissing

    if not token_cache_ok(cfg, h):
        raise IndexMissing("the BM25 token cache does not match the current chunks or tokeniser: run `ept index`")
    with gzip.open(cfg.path("bm25_tokens"), "rt", encoding="utf-8") as f:
        f.readline()
        rows = [json.loads(line) for line in f]
    if [r["chunk_id"] for r in rows] != ids:
        raise IndexMissing("the BM25 token cache does not match the current chunk ids: run `ept index`")
    return [r["tokens"] for r in rows]


class RunBM25:
    """BM25Okapi (`rank_bm25`) over one run's eligible chunks, in chunk_id order."""

    def __init__(self, corpus: list[list[str]], c: Bm25Cfg):
        from rank_bm25 import BM25Okapi

        self.n = len(corpus)
        self.empty = not any(corpus)
        self.bm = None if self.empty else BM25Okapi(corpus, k1=c.k1, b=c.b, epsilon=c.epsilon)

    def scores(self, query_tokens: list[str]) -> np.ndarray:
        if self.empty or not query_tokens:
            return np.zeros(self.n)
        return np.asarray(self.bm.get_scores(query_tokens), dtype=np.float64)


def top_positive(scores: np.ndarray, depth: int) -> np.ndarray:
    """Positions of the top `depth` scores above 0, ties by position (= chunk_id)."""
    pos = np.flatnonzero(scores > 0)
    order = np.lexsort((pos, -scores[pos]))
    return pos[order][:depth]


def rrf_fuse(rankings: list[np.ndarray], k: float) -> list[tuple[int, float]]:
    """RRF over several rankings (Σ 1/(k + rank), rank from 1): [(position, score)], best first, ties by position."""
    acc: dict[int, float] = {}
    for ranking in rankings:
        for r, p in enumerate(ranking.tolist(), start=1):
            acc[p] = acc.get(p, 0.0) + 1.0 / (k + r)
    return sorted(acc.items(), key=lambda kv: (-kv[1], kv[0]))
