"""Run metadata (global spec §9.4): reports/runs/{run_id}.json."""

from __future__ import annotations

import datetime as dt
import json
import re
import subprocess
import time
from typing import Any, Optional

from ept.config import get_config

RUN_ID_RE = re.compile(r"^[a-z0-9_-]+-\d{8}T\d{6}Z$")
_VERSION_RE = re.compile(r"^\s*version:\s*(\S+)", re.MULTILINE)


def _utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def make_run_id(stage: str, when: Optional[dt.datetime] = None) -> str:
    when = when or _utc_now()
    return f"{stage}-{when.strftime('%Y%m%dT%H%M%SZ')}"


def git_commit() -> Optional[str]:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=get_config().root, capture_output=True, text=True, timeout=10
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() or None


def prompt_versions() -> dict[str, str]:
    prompts = get_config().path("prompts")
    versions = {}
    for p in sorted(prompts.glob("*.md")):
        m = _VERSION_RE.search(p.read_text(encoding="utf-8")[:500])
        if m:
            versions[p.stem] = m.group(1)
    return versions


def _run_path(run_id: str):
    return get_config().path("runs") / f"{run_id}.json"


def start_run(stage: str, params: Optional[dict[str, Any]] = None) -> str:
    cfg = get_config()
    run_id = make_run_id(stage)
    path = _run_path(run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    meta = {
        "run_id": run_id,
        "stage": stage,
        "started_at": _utc_now().isoformat(timespec="seconds"),
        "finished_at": None,
        "status": "running",
        "git_commit": git_commit(),
        "params": params or {},
        "prompt_versions": prompt_versions(),
        "models": {},
        "counts": {},
        "config": cfg.snapshot(),
    }
    path.write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")
    return run_id


def finish_run(
    run_id: str,
    counts: Optional[dict[str, Any]] = None,
    status: str = "done",
    models: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    path = _run_path(run_id)
    meta = json.loads(path.read_text(encoding="utf-8"))
    meta["finished_at"] = _utc_now().isoformat(timespec="seconds")
    meta["status"] = status
    meta["counts"] = counts or {}
    if models:
        meta["models"] = models
    path.write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")
    return meta


class Budget:
    """--time-budget: commands check `expired()` between items and stop cleanly."""

    def __init__(self, seconds: Optional[float], clock=None):
        self._clock = clock or time.monotonic
        self.deadline = None if seconds is None else self._clock() + seconds

    def expired(self) -> bool:
        return self.deadline is not None and self._clock() >= self.deadline
