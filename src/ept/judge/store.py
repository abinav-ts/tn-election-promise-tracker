"""Judge runs and storage (spec 05 §4.8).

`run_id` = `judge-{UTC}`; reports/runs/{run_id}.json records `kind` (bulk | strong | probe | final), the
retrieval run, a fingerprint and per-tier completion. Same fingerprint → the run resumes (stored keys are
skipped, so a complete run writes nothing); a change or `--force` → a new run. The bulk tiers share one run, so
"the latest complete bulk run" holds tiers A and B (build clarification, spec 05 §10).

Writes to `indicator_verdicts` and `verdicts` are delete-then-insert per (run_id, id, cutoff_date), a null
cutoff matched with IS NULL (`ept.db.upsert` does this for keys with a nullable column).
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Iterable, Optional

from ept import db
from ept.config import Config
from ept.runs import make_run_id, start_run
from ept.schema import IndicatorVerdict, Verdict

STAGE = "judge"
PKG = Path(__file__).resolve().parents[1]


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else "missing"


def code_hash(files: Iterable[str]) -> str:
    """sha256 over package source files (paths relative to src/ept)."""
    return hashlib.sha256(b"".join((PKG / f).read_bytes() for f in files)).hexdigest()


def fp_hash(parts: dict[str, Any]) -> dict[str, Any]:
    return {"hash": hashlib.sha256(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest(),
            "parts": parts}


def meta_path(cfg: Config, run_id: str) -> Path:
    return cfg.path("runs") / f"{run_id}.json"


def read_meta(cfg: Config, run_id: str) -> dict[str, Any]:
    return json.loads(meta_path(cfg, run_id).read_text(encoding="utf-8"))


def write_meta(cfg: Config, meta: dict[str, Any]) -> None:
    meta_path(cfg, meta["run_id"]).write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")


def runs(cfg: Config, kind: Optional[str] = None) -> list[dict[str, Any]]:
    out = []
    for p in sorted(cfg.path("runs").glob(f"{STAGE}-*.json")):
        meta = json.loads(p.read_text(encoding="utf-8"))
        if meta.get("stage") == STAGE and (kind is None or meta.get("kind") == kind):
            out.append(meta)
    return sorted(out, key=lambda m: m["run_id"])


def latest_run(cfg: Config, kind: str, complete_only: bool = False, tier: Optional[str] = None
               ) -> Optional[dict[str, Any]]:
    """The latest run of a kind; `complete_only` = every tier done; `tier` = that tier done."""
    out = runs(cfg, kind)
    if complete_only:
        out = [m for m in out if m.get("complete")]
    if tier:
        out = [m for m in out if (m.get("tiers") or {}).get(tier, {}).get("complete")]
    return out[-1] if out else None


def start_or_resume(cfg: Config, kind: str, fp: dict[str, Any], force: bool, params: dict[str, Any],
                    extra: Optional[dict[str, Any]] = None) -> tuple[str, bool]:
    if not force:
        for meta in reversed(runs(cfg, kind)):
            if meta.get("fingerprint", {}).get("hash") == fp["hash"]:
                meta.setdefault("resumed_at", []).append(time.strftime("%Y-%m-%dT%H:%M:%S"))
                write_meta(cfg, meta)
                return meta["run_id"], True
    while meta_path(cfg, make_run_id(STAGE)).exists():  # one-second run ids
        time.sleep(0.1)
    run_id = start_run(STAGE, params)
    meta = read_meta(cfg, run_id)
    meta.update(kind=kind, fingerprint=fp, complete=False, **(extra or {}))
    write_meta(cfg, meta)
    return run_id, False


def update_meta(cfg: Config, run_id: str, **fields: Any) -> dict[str, Any]:
    meta = read_meta(cfg, run_id)
    meta.update(fields)
    write_meta(cfg, meta)
    return meta


# --- DB -------------------------------------------------------------------------------------


def stored_keys(conn: sqlite3.Connection, run_id: str) -> set[str]:
    return {r[0] for r in conn.execute("SELECT DISTINCT judging_key FROM indicator_verdicts WHERE run_id = ?",
                                       (run_id,))}


def write_indicator_verdicts(conn: sqlite3.Connection, rows: list[IndicatorVerdict]) -> None:
    with conn:
        for r in rows:
            db.upsert(conn, r, commit=False)


def write_verdicts(conn: sqlite3.Connection, rows: list[Verdict]) -> None:
    with conn:
        for r in rows:
            db.upsert(conn, r, commit=False)


def indicator_rows(conn: sqlite3.Connection, run_id: str) -> list[IndicatorVerdict]:
    return db.select_models(conn, "indicator_verdicts", "run_id = ? ORDER BY indicator_id, cutoff_date",
                            (run_id,))  # type: ignore[return-value]


def verdict_rows(conn: sqlite3.Connection, run_id: str) -> list[Verdict]:
    return db.select_models(conn, "verdicts", "run_id = ? ORDER BY promise_id, cutoff_date",
                            (run_id,))  # type: ignore[return-value]
