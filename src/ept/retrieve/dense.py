"""Embedding index and dense search (spec 04 §4.1, §4.5; D-079).

`ept index` embeds every chunk's index text (document title + newline + chunk text) with
`BAAI/bge-small-en-v1.5` and writes `vectors.npy` (float32, L2-normalised), `chunk_ids.json` and
`manifest.json`; it also writes the BM25 token cache. Search is exact (numpy dot products) inside each
run's eligible rows. `torch` / `sentence-transformers` are imported lazily, so tests (mock embedder) never
load or download a model.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import shutil
import sqlite3
import time
from dataclasses import dataclass
from typing import Any, Optional

import numpy as np

from ept.config import Config
from ept.retrieve import bm25
from ept.retrieve.tokenize import tokenize
from ept.runs import eta, progress

MOCK_ENV = "EPT_EMBED_MOCK"


class IndexMissing(RuntimeError):
    """No usable embedding index for the current chunks and model: run `ept index`."""


def index_text(title: Optional[str], text: str) -> str:
    return f"{title or ''}\n{text}"


def corpus_texts(conn: sqlite3.Connection) -> tuple[list[str], list[str]]:
    """(chunk_ids, index texts) in chunk_id order."""
    rows = conn.execute("SELECT c.chunk_id, d.title, c.text FROM chunks c JOIN documents d ON d.doc_id = c.doc_id "
                        "ORDER BY c.chunk_id").fetchall()
    return [r["chunk_id"] for r in rows], [index_text(r["title"], r["text"]) for r in rows]


def texts_hash(ids: list[str], texts: list[str]) -> str:
    h = hashlib.sha256()
    for i, t in zip(ids, texts):
        h.update(i.encode())
        h.update(b"\0")
        h.update(t.encode())
        h.update(b"\n")
    return h.hexdigest()


def use_mock(cfg: Config) -> bool:
    return cfg.settings.retrieve.dense.mock or os.environ.get(MOCK_ENV) == "1"


class MockEmbedder:
    """Deterministic hashing embedder for offline tests: signed token buckets, L2-normalised."""

    name = "mock-hashing"
    revision = "mock"

    def __init__(self, dim: int):
        self.dim = dim

    def encode(self, texts: list[str]) -> np.ndarray:
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for row, text in enumerate(texts):
            for tok in tokenize(text):
                h = int.from_bytes(hashlib.sha1(tok.encode()).digest()[:8], "big")
                out[row, h % self.dim] += 1.0 if (h >> 32) & 1 else -1.0
        return _normalise(out)


class SentenceEmbedder:
    """sentence-transformers model at a pinned revision (imported lazily)."""

    def __init__(self, cfg: Config):
        d = cfg.settings.retrieve.dense
        if not d.revision:
            raise IndexMissing(f"retrieve.dense.revision is not pinned in config/settings.yaml: set it to the "
                               f"commit hash of {d.model} before building the real index (spec 04 §4.5)")
        from sentence_transformers import SentenceTransformer  # lazy: pulls torch

        self.name, self.revision, self.batch_size = d.model, d.revision, d.batch_size
        self.model = SentenceTransformer(d.model, revision=d.revision, device=_device(d.device))
        self.model.max_seq_length = d.max_seq_length
        self.dim = int(self.model.get_sentence_embedding_dimension())

    def encode(self, texts: list[str]) -> np.ndarray:
        vecs = self.model.encode(texts, batch_size=self.batch_size, normalize_embeddings=True,
                                 convert_to_numpy=True, show_progress_bar=False)
        return np.asarray(vecs, dtype=np.float32)


def _device(setting: str) -> str:
    if setting != "auto":
        return setting
    import torch

    return "mps" if torch.backends.mps.is_available() else "cpu"


def _normalise(m: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(m, axis=1, keepdims=True)
    return (m / np.where(norms == 0, 1.0, norms)).astype(np.float32)


def embedder(cfg: Config):
    if use_mock(cfg):
        return MockEmbedder(cfg.settings.retrieve.dense.mock_dim)
    return SentenceEmbedder(cfg)


def _expected(cfg: Config, n: int, h: str) -> dict[str, Any]:
    d = cfg.settings.retrieve.dense
    mock = use_mock(cfg)
    return {"model": "mock-hashing" if mock else d.model, "revision": "mock" if mock else d.revision,
            "max_seq_length": None if mock else d.max_seq_length, "n": n, "index_text_hash": h}


def _matches(manifest: dict[str, Any], expected: dict[str, Any]) -> bool:
    return all(manifest.get(k) == v for k, v in expected.items())


def read_manifest(cfg: Config) -> Optional[dict[str, Any]]:
    path = cfg.path("embeddings_dir") / "manifest.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def build_index(conn: sqlite3.Connection, cfg: Config, force: bool = False, limit: Optional[int] = None
                ) -> dict[str, Any]:
    """Embed every chunk (resumable shards) and write the BM25 token cache.

    `limit` = timing run: embed the first N index texts, report the time and the full-corpus estimate,
    write nothing.
    """
    ids, texts = corpus_texts(conn)
    h = texts_hash(ids, texts)
    if limit is not None:
        emb = embedder(cfg)
        t0 = time.monotonic()
        emb.encode(texts[:limit])
        secs = time.monotonic() - t0
        n = min(limit, len(texts))
        return {"timed_chunks": n, "seconds": round(secs, 1),
                "estimated_full_minutes": round(secs / max(n, 1) * len(texts) / 60, 1), "written": 0}
    expected = _expected(cfg, len(ids), h)
    manifest = read_manifest(cfg)
    tokens_ok = bm25.token_cache_ok(cfg, h)
    if not force and manifest and _matches(manifest, expected) and tokens_ok:
        return {"chunks": len(ids), "skipped": "index matches the current chunks and model", "written": 0}
    stats: dict[str, Any] = {"chunks": len(ids)}
    if force or not tokens_ok:
        t0 = time.monotonic()
        bm25.write_token_cache(cfg, ids, texts, h)
        stats["bm25_tokens_s"] = round(time.monotonic() - t0, 1)
    if force or not (manifest and _matches(manifest, expected)):
        stats.update(_embed_all(cfg, ids, texts, expected, force))
    return stats


def _embed_all(cfg: Config, ids: list[str], texts: list[str], expected: dict[str, Any], force: bool
               ) -> dict[str, Any]:
    out_dir = cfg.path("embeddings_dir")
    shard_dir = out_dir / "shards"
    state_path = shard_dir / "state.json"
    key = hashlib.sha256(json.dumps(expected, sort_keys=True).encode()).hexdigest()
    if force or not state_path.exists() or json.loads(state_path.read_text())["key"] != key:
        shutil.rmtree(shard_dir, ignore_errors=True)
    shard_dir.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps({"key": key}), encoding="utf-8")
    size = cfg.settings.retrieve.index_shard
    n_shards = (len(texts) + size - 1) // size
    emb = None
    t0, embedded = time.monotonic(), 0
    for s in range(n_shards):
        path = shard_dir / f"{s:05d}.npy"
        if path.exists():
            continue
        emb = emb or embedder(cfg)
        vecs = emb.encode(texts[s * size:(s + 1) * size])
        np.save(path.with_suffix(".tmp.npy"), vecs)
        path.with_suffix(".tmp.npy").rename(path)
        embedded += len(vecs)
        done = s + 1
        progress(f"index shard {done}/{n_shards} ({embedded} chunks embedded"
                 f"{eta(done, n_shards, time.monotonic() - t0) if embedded == done * size else ''})")
    vectors = np.concatenate([np.load(shard_dir / f"{s:05d}.npy") for s in range(n_shards)]) if n_shards else \
        np.zeros((0, cfg.settings.retrieve.dense.mock_dim), dtype=np.float32)
    np.save(out_dir / "vectors.npy", vectors)
    (out_dir / "chunk_ids.json").write_text(json.dumps(ids), encoding="utf-8")
    manifest = {**expected, "dim": int(vectors.shape[1]),
                "created": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    shutil.rmtree(shard_dir, ignore_errors=True)
    return {"embedded": embedded, "embed_s": round(time.monotonic() - t0, 1), "dim": manifest["dim"],
            "written": len(ids)}


@dataclass
class DenseIndex:
    vectors: np.ndarray
    chunk_ids: list[str]
    manifest: dict[str, Any]


def load_index(cfg: Config, ids: list[str], h: str) -> DenseIndex:
    """The index, checked against the current chunk ids and index texts (row order = chunk_id order)."""
    out_dir = cfg.path("embeddings_dir")
    manifest = read_manifest(cfg)
    if not manifest:
        raise IndexMissing("no embedding index: run `ept index`")
    stored = json.loads((out_dir / "chunk_ids.json").read_text(encoding="utf-8"))
    if stored != ids:
        raise IndexMissing("the embedding index does not match the current chunks: run `ept index`")
    if manifest.get("index_text_hash") != h:
        raise IndexMissing("chunk texts or titles changed since `ept index`: run `ept index`")
    if not _matches(manifest, _expected(cfg, len(ids), h)):
        raise IndexMissing(f"the embedding index was built with {manifest.get('model')} "
                           f"@ {manifest.get('revision')}, not the configured model: run `ept index --force`")
    return DenseIndex(np.load(out_dir / "vectors.npy"), stored, manifest)


def ranked(sims: np.ndarray, depth: int) -> np.ndarray:
    """Positions of the top `depth` similarities, ties broken by position (= chunk_id order)."""
    order = np.lexsort((np.arange(len(sims)), -sims))
    return order[:depth]
