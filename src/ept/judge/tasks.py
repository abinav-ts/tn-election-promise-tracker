"""Retrieval tasks, judging keys, judging cutoffs and tiers (spec 05 §4.1, D-084, D-085).

A retrieval task is (indicator, cutoff) with its ranked chunks from the latest complete stage 04 run. The
judging key is sha256(indicator_id, ordered chunk_ids, directional flag, prompt version): the prompt shows no
cutoff date, so tasks with one key have identical inputs and are judged once; the verdict is stored for every
cutoff that retrieved the list. A key's judging cutoff is the earliest configured cutoff of its term that
retrieved it, and calls group keys by (term, judging cutoff) only, so no task sees a chunk that was not
eligible at another task's cutoff.

`Context` holds what rendering and the checks need: promise and indicator texts, chunk texts and the
availability date of every chunk (`ept.dates.available_by`, via `ept.retrieve.eligible.load_availability`).
"""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional

from ept.config import Config
from ept.dates import parse_iso
from ept.retrieve import eligible as el

FULL = el.FULL
TIERS_ORDER = ("A", "B")


@dataclass(frozen=True)
class Task:
    term_id: str
    promise_id: str
    indicator_id: str
    cutoff: el.Cutoff
    chunk_ids: tuple[str, ...]


@dataclass
class Key:
    key: str
    term_id: str
    promise_id: str
    indicator_id: str
    chunk_ids: tuple[str, ...]
    directional: bool
    tasks: list[Task] = field(default_factory=list)  # every cutoff that retrieved this list, in time order
    tiers: set[str] = field(default_factory=set)

    @property
    def judging(self) -> el.Cutoff:
        """The earliest cutoff that retrieved this chunk list."""
        return self.tasks[0].cutoff

    @property
    def group(self) -> tuple[str, str]:
        return self.term_id, self.judging.key


def cutoff_order(c: el.Cutoff) -> tuple[dt.date, bool]:
    """Time order of a term's cutoffs: landmarks by date, the full term last."""
    return c.upper, c.label == FULL


def judging_key(indicator_id: str, chunk_ids: Iterable[str], directional: bool, prompt_version: str) -> str:
    payload = json.dumps([indicator_id, list(chunk_ids), bool(directional), prompt_version])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def promise_of(indicator_id: str) -> str:
    return indicator_id.rsplit("-I", 1)[0]


# --- tiers ---------------------------------------------------------------------------


def tier_labels(value: Any, cutoffs: list[el.Cutoff]) -> set[str]:
    """`all` | `landmarks` | a list of `full` / landmark months (`5` or `m5`) -> cutoff labels."""
    if value == "all":
        return {c.label for c in cutoffs}
    if value == "landmarks":
        return {c.label for c in cutoffs if c.label != FULL}
    if isinstance(value, str):
        raise ValueError(f"judge.tiers: unknown value {value!r}")
    out = set()
    for v in value:
        s = str(v)
        out.add(s if s == FULL or s.startswith("m") else f"m{s}")
    return out


def task_tiers(cfg: Config, term_id: str, cutoffs: list[el.Cutoff]) -> dict[str, set[str]]:
    """{cutoff label: tiers containing it} for one term."""
    out: dict[str, set[str]] = {c.label: set() for c in cutoffs}
    for tier, terms in cfg.settings.judge.tiers.items():
        if term_id in terms:
            for label in tier_labels(terms[term_id], cutoffs):
                if label in out:
                    out[label].add(tier)
    return out


def tier_list(tier: str, cfg: Config) -> list[str]:
    tiers = [t for t in TIERS_ORDER if t in cfg.settings.judge.tiers] + \
            sorted(t for t in cfg.settings.judge.tiers if t not in TIERS_ORDER)
    if tier == "all":
        return tiers
    if tier not in tiers:
        raise ValueError(f"unknown tier {tier!r} (configured: {tiers})")
    return [tier]


# --- context -------------------------------------------------------------------------


@dataclass(frozen=True)
class ChunkInfo:
    chunk_id: str
    title: str
    doc_type: str
    doc_date: Optional[dt.date]
    date_precision: Optional[str]
    text: str
    available_by: Optional[dt.date]


class Context:
    """Read-only inputs of a judging run (spec 05 §2)."""

    def __init__(self, conn: sqlite3.Connection, cfg: Config):
        self.conn, self.cfg = conn, cfg
        avail = el.load_availability(conn, cfg)
        self.avail = {c.chunk_id: c for c in avail}
        self.snapshot = el.snapshot_end(cfg, avail, el.latest_fetch(conn))
        self.promises = {r["promise_id"]: dict(r) for r in conn.execute(
            "SELECT promise_id, term_id, text, headline, specificity FROM promises")}
        self.indicators = {r["indicator_id"]: dict(r) for r in conn.execute(
            "SELECT indicator_id, promise_id, text, is_self FROM indicators ORDER BY indicator_id")}
        self.by_promise: dict[str, list[str]] = {}
        for iid, r in self.indicators.items():
            self.by_promise.setdefault(r["promise_id"], []).append(iid)
        self._chunks: dict[str, ChunkInfo] = {}

    def sworn_in(self, term_id: str) -> dt.date:
        return parse_iso(self.cfg.term(term_id).sworn_in)

    def cutoffs(self, term_id: str) -> list[el.Cutoff]:
        return sorted(el.term_cutoffs(self.cfg, term_id, self.snapshot), key=cutoff_order)

    def chunks(self, ids: Iterable[str]) -> dict[str, ChunkInfo]:
        missing = [i for i in ids if i not in self._chunks]
        for n in range(0, len(missing), 500):
            part = missing[n:n + 500]
            sql = ("SELECT c.chunk_id, c.text, d.title, d.doc_type, d.doc_date, d.date_precision FROM chunks c "
                   f"JOIN documents d ON d.doc_id = c.doc_id WHERE c.chunk_id IN ({','.join('?' * len(part))})")
            for r in self.conn.execute(sql, part):
                a = self.avail.get(r["chunk_id"])
                self._chunks[r["chunk_id"]] = ChunkInfo(
                    r["chunk_id"], r["title"] or "", r["doc_type"], parse_iso(r["doc_date"]) if r["doc_date"] else None,
                    r["date_precision"], r["text"], a.available_by if a else None)
        return {i: self._chunks[i] for i in ids if i in self._chunks}


# --- retrievals -> keys --------------------------------------------------------------------


def load_retrievals(conn: sqlite3.Connection, run_id: str) -> dict[tuple[str, Optional[str]], tuple[str, ...]]:
    """{(indicator_id, cutoff_date iso or None): chunk_ids in rank order}. Read-only."""
    out: dict[tuple[str, Optional[str]], list[str]] = {}
    for r in conn.execute("SELECT indicator_id, cutoff_date, chunk_id FROM retrievals WHERE run_id = ? "
                          "ORDER BY indicator_id, cutoff_date, rank", (run_id,)):
        out.setdefault((r["indicator_id"], r["cutoff_date"]), []).append(r["chunk_id"])
    return {k: tuple(v) for k, v in out.items()}


def term_indicator_ids(ctx: Context, term_id: str, limit: Optional[int]) -> list[str]:
    """The term's indicators in indicator_id order; `--limit N` = the first N (spec 05 §4.13)."""
    ids = [iid for iid in ctx.indicators if ctx.promises[ctx.indicators[iid]["promise_id"]]["term_id"] == term_id]
    return ids[:limit] if limit is not None else ids


def build_keys(ctx: Context, retrievals: dict[tuple[str, Optional[str]], tuple[str, ...]],
               directional: dict[str, bool], prompt_version: str, terms: list[str],
               limit: Optional[int] = None) -> list[Key]:
    """Every judging key of `terms` (all their configured cutoffs), with tasks in time order and tiers."""
    keys: dict[str, Key] = {}
    for term_id in terms:
        cutoffs = ctx.cutoffs(term_id)
        tiers = task_tiers(ctx.cfg, term_id, cutoffs)
        for iid in term_indicator_ids(ctx, term_id, limit):
            pid = ctx.indicators[iid]["promise_id"]
            if pid not in directional:
                raise MissingDirectional(f"no directional flag for {pid}: run `ept judge directional` first")
            for c in cutoffs:
                chunk_ids = retrievals.get((iid, c.cutoff_date.isoformat() if c.cutoff_date else None))
                if not chunk_ids:
                    raise MissingRetrieval(f"{iid} @ {c.key}: no retrieval rows in the stage 04 run")
                k = judging_key(iid, chunk_ids, directional[pid], prompt_version)
                key = keys.setdefault(k, Key(k, term_id, pid, iid, chunk_ids, directional[pid]))
                key.tasks.append(Task(term_id, pid, iid, c, chunk_ids))
                key.tiers |= tiers[c.label]
    return list(keys.values())


class MissingDirectional(RuntimeError):
    pass


class MissingRetrieval(RuntimeError):
    pass


def groups(keys: list[Key], term_order: list[str]) -> list[list[Key]]:
    """Keys grouped by (term, judging cutoff), groups in term and time order, keys by indicator_id."""
    by: dict[tuple[str, str], list[Key]] = {}
    cut: dict[tuple[str, str], el.Cutoff] = {}
    for k in keys:
        by.setdefault(k.group, []).append(k)
        cut[k.group] = k.judging
    order = sorted(by, key=lambda g: (term_order.index(g[0]), cutoff_order(cut[g])))
    return [sorted(by[g], key=lambda k: k.indicator_id) for g in order]


def batches(group: list[Key], size: int) -> list[list[Key]]:
    return [group[i:i + size] for i in range(0, len(group), size)]


# --- gold IDs (spec 05 §5: promise_id and term_id only, never labels) -----------------------


def gold_promise_ids(cfg: Config) -> set[str]:
    """Promise IDs of the gold sample, for the strong queue (P1) and the spot-check exclusion. Reads only the
    `promise_id` and `term_id` columns of gold_sample.csv; never a label file."""
    path: Path = cfg.path("gold_sample")
    if not path.exists():
        return set()
    with path.open(encoding="utf-8", newline="") as f:
        return {r["promise_id"].strip() for r in csv.DictReader(f)
                if (r.get("promise_id") or "").strip() and (r.get("term_id") or "").strip()}
