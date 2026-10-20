"""`ept retrieve run` (spec 04 §4.3–§4.8): top-k chunks per indicator × cutoff into `retrievals`.

Per term and cutoff: eligible set (available_by inside the term window) → BM25 built on those chunks
only, each search query scored separately and RRF-fused → exact dense search inside the eligible rows →
RRF fusion, per-document cap, GO places → delete-then-insert per (run_id, indicator_id, cutoff_date).
No LLM call; queries are used exactly as frozen in stage 03 (D-079).

A run with the same fingerprint resumes (stored pairs skipped); a changed fingerprint or `--force`
starts a new run. Run metadata: reports/runs/{run_id}.json, incl. `fingerprint` and `complete`.
Per-pair diagnostics (BM25/dense overlap, cap, GO places) go to `paths.retrieve_diag` for the report
and spot-check.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Optional

import numpy as np

from ept import db
from ept.classify.freeze import snapshot_path as classification_snapshot
from ept.config import Config, get_config
from ept.retrieve import bm25, dense, eligible as el, fuse
from ept.retrieve import tokenize as tok
from ept.runs import finish_run, make_run_id, progress, start_run
from ept.schema import Retrieval

STAGE = "retrieve"
# code that shapes the rows: a change starts a new run instead of resuming (build clarification, spec 04 §10)
_ROW_CODE = ["dates.py", "retrieve/eligible.py", "retrieve/tokenize.py", "retrieve/stopwords.py",
             "retrieve/bm25.py", "retrieve/dense.py", "retrieve/fuse.py", "retrieve/run.py"]


class EmptyEligibleSet(RuntimeError):
    """A term-cutoff with no eligible chunk: stop and ask the user (spec 04 §4.12)."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else "missing"


def fingerprint(cfg: Config, manifest: dict[str, Any], ids: list[str],
                avail: Optional[list[el.ChunkAvail]] = None) -> dict[str, Any]:
    s = cfg.settings
    pkg = Path(__file__).resolve().parents[1]
    code = hashlib.sha256(b"".join((pkg / f).read_bytes() for f in _ROW_CODE)).hexdigest()
    parts = {
        "retrieve": s.retrieve.model_dump(mode="json", exclude={"spotcheck", "tokens_per_word"}),
        "fy_bound": s.date.fy_bound.model_dump(mode="json"),
        "fetch_bound": s.date.fetch_bound.model_dump(mode="json"),
        # every chunk's availability date: a re-dated or re-fetched document starts a new run
        "availability": hashlib.sha256("\n".join(f"{c.chunk_id} {c.available_by}" for c in avail or []).encode()
                                       ).hexdigest(),
        "terms": [t.model_dump(mode="json") for t in s.terms],
        "embedding": {k: manifest.get(k) for k in ("model", "revision", "max_seq_length", "n", "index_text_hash",
                                                  "dim")},
        "tokenizer": tok.fingerprint(),
        "classification": {t.term_id: _sha256(classification_snapshot(cfg, t.term_id)) for t in s.terms},
        "chunk_ids": hashlib.sha256("\n".join(ids).encode()).hexdigest(),
        "code": code,
    }
    return {"hash": hashlib.sha256(json.dumps(parts, sort_keys=True).encode()).hexdigest(), "parts": parts}


def _runs(cfg: Config) -> list[dict[str, Any]]:
    out = []
    for p in sorted(cfg.path("runs").glob(f"{STAGE}-*.json")):
        meta = json.loads(p.read_text(encoding="utf-8"))
        if meta.get("stage") == STAGE:
            out.append(meta)
    return sorted(out, key=lambda m: m["run_id"])


def latest_run(cfg: Config, complete_only: bool = False) -> Optional[dict[str, Any]]:
    """The latest retrieve run (stage 05 reads the latest complete one)."""
    runs = [m for m in _runs(cfg) if m.get("complete") or not complete_only]
    return runs[-1] if runs else None


def _write_meta(cfg: Config, meta: dict[str, Any]) -> None:
    (cfg.path("runs") / f"{meta['run_id']}.json").write_text(json.dumps(meta, indent=2, default=str),
                                                          encoding="utf-8")


def _read_meta(cfg: Config, run_id: str) -> dict[str, Any]:
    return json.loads((cfg.path("runs") / f"{run_id}.json").read_text(encoding="utf-8"))


def diag_path(cfg: Config, run_id: str) -> Path:
    return cfg.root / cfg.settings.paths.retrieve_diag.format(run_id=run_id)


def read_diag(cfg: Config, run_id: str) -> dict[tuple[str, str], dict[str, Any]]:
    """{(indicator_id, cutoff key): record}; the last line for a pair wins."""
    path = diag_path(cfg, run_id)
    out: dict[tuple[str, str], dict[str, Any]] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            out[(r["indicator_id"], r["cutoff"])] = r
    return out


def term_indicators(conn: sqlite3.Connection, term_id: str, limit: Optional[int]) -> list[sqlite3.Row]:
    sql = ("SELECT i.indicator_id, i.text, i.search_queries FROM indicators i JOIN promises p "
           "ON p.promise_id = i.promise_id WHERE p.term_id = ? ORDER BY i.indicator_id")
    rows = conn.execute(sql, (term_id,)).fetchall()
    return rows[:limit] if limit is not None else rows


def _stored(conn: sqlite3.Connection, run_id: str, cutoff: el.Cutoff) -> set[str]:
    rows = conn.execute("SELECT DISTINCT indicator_id FROM retrievals WHERE run_id = ? AND cutoff_date IS ?",
                        (run_id, cutoff.cutoff_date.isoformat() if cutoff.cutoff_date else None))
    return {r["indicator_id"] for r in rows}


def write_pair(conn: sqlite3.Connection, run_id: str, indicator_id: str, cutoff: el.Cutoff,
               chunks: list[fuse.Candidate]) -> None:
    """Delete-then-insert one (run_id, indicator_id, cutoff_date) in the caller's transaction; a null
    cutoff_date is matched with IS NULL (SQLite treats NULLs in a key as distinct)."""
    cd = cutoff.cutoff_date.isoformat() if cutoff.cutoff_date else None
    conn.execute("DELETE FROM retrievals WHERE run_id = ? AND indicator_id = ? AND cutoff_date IS ?",
                 (run_id, indicator_id, cd))
    for rank, c in enumerate(chunks, start=1):
        db.upsert(conn, Retrieval(indicator_id=indicator_id, chunk_id=c.chunk_id, rank=rank, scores=c.scores(),
                                  cutoff_date=cutoff.cutoff_date, run_id=run_id), commit=False)


class Corpus:
    """Everything a run needs about the chunks, aligned in chunk_id order."""

    def __init__(self, conn: sqlite3.Connection, cfg: Config):
        self.avail = el.load_availability(conn, cfg)
        ids, texts = dense.corpus_texts(conn)
        self.ids = ids
        self.text_hash = dense.texts_hash(ids, texts)
        self.index = dense.load_index(cfg, ids, self.text_hash)
        self.tokens = bm25.load_tokens(cfg, ids, self.text_hash)
        self.snapshot = el.snapshot_end(cfg, self.avail, el.latest_fetch(conn))


def retrieve_one(queries: list[list[str]], qvec: np.ndarray, sub_vecs: np.ndarray, run_bm25: bm25.RunBM25,
                 positions: np.ndarray, corpus: Corpus, cfg: Config) -> tuple[fuse.Selection, dict[str, Any]]:
    """One indicator against one run's eligible set. `positions` maps eligible rows to corpus rows."""
    r = cfg.settings.retrieve
    sims = sub_vecs @ qvec
    dense_top = dense.ranked(sims, r.dense.depth)
    q_scores = [run_bm25.scores(q) for q in queries]
    q_tops = [bm25.top_positive(s, r.bm25.depth) for s in q_scores]
    bm25_order = bm25.rrf_fuse(q_tops, r.rrf.k)
    cands: dict[int, fuse.Candidate] = {}

    def cand(p: int) -> fuse.Candidate:
        if p not in cands:
            a = corpus.avail[int(positions[p])]
            cands[p] = fuse.Candidate(pos=p, chunk_id=a.chunk_id, doc_id=a.doc_id, is_go=a.doc_type == "go",
                                      dense_cos=float(sims[p]))
        return cands[p]

    for rank, (p, _) in enumerate(bm25_order, start=1):
        c = cand(p)
        best = int(np.argmax([s[p] for s in q_scores]))
        c.bm25_rank, c.bm25_score, c.bm25_query = rank, float(q_scores[best][p]), best
    for rank, p in enumerate(dense_top.tolist(), start=1):
        cand(p).dense_rank = rank
    order = fuse.fuse(list(cands.values()), r)
    sel = fuse.select(order, r)
    top5_b = {p for p, _ in bm25_order[: r.k]}
    top5_d = set(dense_top[: r.k].tolist())
    diag = {"n_bm25": len(bm25_order), "overlap_top_k": len(top5_b & top5_d) if top5_b else None,
            "top1_cos": float(sims[dense_top[0]]) if len(dense_top) else None,
            "top1_rrf": sel.chunks[0].rrf if sel.chunks else None, "cap_applied": sel.cap_applied,
            "go_places": sel.go_places, "displaced": sel.displaced, "go_rule_ok": sel.go_rule_ok, "n_selected": len(sel.chunks),
            "bm25_top_k": [corpus.avail[int(positions[p])].chunk_id for p, _ in bm25_order[: r.k]],
            "dense_top_k": [corpus.avail[int(positions[p])].chunk_id for p in dense_top[: r.k].tolist()]}
    return sel, diag


def _start_or_resume(cfg: Config, fp: dict[str, Any], force: bool, params: dict[str, Any]) -> tuple[str, bool]:
    if not force:
        for meta in reversed(_runs(cfg)):
            if meta.get("fingerprint", {}).get("hash") == fp["hash"]:
                meta.setdefault("resumed_at", []).append(time.strftime("%Y-%m-%dT%H:%M:%S"))
                _write_meta(cfg, meta)
                return meta["run_id"], True
    while (cfg.path("runs") / f"{make_run_id(STAGE)}.json").exists():  # run ids have one-second resolution
        time.sleep(0.1)
    run_id = start_run(STAGE, params)
    meta = _read_meta(cfg, run_id)
    meta.update(fingerprint=fp, complete=False, term_cutoffs={})
    _write_meta(cfg, meta)
    return run_id, False


def configured(cfg: Config, snapshot) -> list[el.Cutoff]:
    return [c for t in cfg.settings.terms for c in el.term_cutoffs(cfg, t.term_id, snapshot)]


def is_complete(conn: sqlite3.Connection, cfg: Config, run_id: str, cutoffs: list[el.Cutoff]) -> bool:
    for c in cutoffs:
        if len(_stored(conn, run_id, c)) < len(term_indicators(conn, c.term_id, None)):
            return False
    return True


def run_retrieve(term: Optional[str] = None, limit: Optional[int] = None, force: bool = False,
                 cutoffs: Optional[list[str]] = None) -> dict[str, Any]:
    cfg = get_config()
    conn = db.connect()
    db.init_schema(conn)
    corpus = Corpus(conn, cfg)
    fp = fingerprint(cfg, corpus.index.manifest, corpus.ids, corpus.avail)
    terms = [term] if term else [t.term_id for t in cfg.settings.terms]
    plan = [c for t in terms for c in el.term_cutoffs(cfg, t, corpus.snapshot, cutoffs)]  # refusals raise first
    run_id, resumed = _start_or_resume(cfg, fp, force, {"term": term, "limit": limit, "force": force,
                                                         "cutoffs": cutoffs})
    emb = dense.embedder(cfg)
    instr = cfg.settings.retrieve.dense.query_instruction
    dpath = diag_path(cfg, run_id)
    dpath.parent.mkdir(parents=True, exist_ok=True)
    stats: dict[str, Any] = {"run_id": run_id, "resumed": resumed, "written": 0, "skipped": 0, "rows": 0}
    meta = _read_meta(cfg, run_id)
    qcache: dict[str, tuple[list[sqlite3.Row], np.ndarray]] = {}
    for cutoff in plan:
        t0 = time.monotonic()
        inds = term_indicators(conn, cutoff.term_id, limit)
        if cutoff.term_id not in qcache:
            qcache[cutoff.term_id] = (inds, emb.encode([instr + i["text"] for i in inds]) if inds else
                                      np.zeros((0, corpus.index.vectors.shape[1]), dtype=np.float32))
        inds, qvecs = qcache[cutoff.term_id]
        done = _stored(conn, run_id, cutoff)
        todo = [(n, i) for n, i in enumerate(inds) if i["indicator_id"] not in done]
        positions = np.array(el.eligible_indices(corpus.avail, cutoff), dtype=np.int64)
        if len(positions) == 0:
            raise EmptyEligibleSet(f"{cutoff.term_id} {cutoff.label}: no eligible chunk (stop and ask the user)")
        rec = {"eligible": int(len(positions)), "indicators": len(inds), "skipped": len(inds) - len(todo)}
        stats["skipped"] += rec["skipped"]
        if todo:
            run_bm25 = bm25.RunBM25([corpus.tokens[p] for p in positions.tolist()], cfg.settings.retrieve.bm25)
            sub = corpus.index.vectors[positions]
            with conn, dpath.open("a", encoding="utf-8") as df:  # diag flushed before the commit
                for n, ind in todo:
                    queries = [tok.tokenize(q) for q in json.loads(ind["search_queries"])]
                    sel, diag = retrieve_one(queries, qvecs[n], sub, run_bm25, positions, corpus, cfg)
                    df.write(json.dumps({"indicator_id": ind["indicator_id"], "cutoff": cutoff.key, **diag}) + "\n")
                    write_pair(conn, run_id, ind["indicator_id"], cutoff, sel.chunks)
                    stats["rows"] += len(sel.chunks)
            stats["written"] += len(todo)
        rec.update(written=len(todo), seconds=round(time.monotonic() - t0, 1))
        meta["term_cutoffs"][f"{cutoff.term_id}@{cutoff.key}"] = rec
        progress(f"retrieve {cutoff.term_id} {cutoff.label}: {rec['eligible']} eligible chunks, "
                 f"{rec['written']} written, {rec['skipped']} skipped, {rec['seconds']} s")
    complete = is_complete(conn, cfg, run_id, configured(cfg, corpus.snapshot))
    conn.close()
    fresh = _read_meta(cfg, run_id)
    fresh.update(term_cutoffs={**fresh.get("term_cutoffs", {}), **meta["term_cutoffs"]}, complete=complete)
    _write_meta(cfg, fresh)
    finish_run(run_id, counts={k: v for k, v in stats.items() if k != "run_id"},
               models={"embedding": f"{corpus.index.manifest['model']}@{corpus.index.manifest['revision']}"})
    stats["complete"] = complete
    return stats
