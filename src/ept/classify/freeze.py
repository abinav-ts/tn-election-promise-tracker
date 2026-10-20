"""Frozen classification (spec 03 §4.8, D-064).

`ept classify freeze --term T` writes data/frozen/classification_{T}.jsonl and adds T to
`classify.frozen_terms`. A frozen term is loaded from its snapshot (a lost cache or DB can't change
an `indicator_id`) and every classify step refuses to re-classify it, `--force` included. The promise
snapshots (data/frozen/promises_{term}.jsonl, D-039) are never written here.
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any

from ept.config import Config, get_config

SNAPSHOT_FIELDS = ("promise_id", "sector", "promise_type", "specificity", "cost_band", "union_dependent",
                   "continues_existing", "headline", "covariates_version", "union_basis", "continues_cue",
                   "headline_signal", "headline_rank", "indicators")


class FrozenClassificationError(RuntimeError):
    pass


def is_frozen(cfg: Config, term_id: str) -> bool:
    return term_id in cfg.settings.classify.frozen_terms


def check_writable(cfg: Config, term_id: str) -> None:
    if is_frozen(cfg, term_id):
        raise FrozenClassificationError(
            f"{term_id}'s classification is frozen ({snapshot_path(cfg, term_id).name}); `ept classify` refuses "
            "to re-classify it, --force included. Un-freezing needs a decision-log entry (spec 03 §4.8).")


def snapshot_path(cfg: Config, term_id: str) -> Path:
    return cfg.root / cfg.settings.paths.classification_frozen.format(term=term_id)


def load_snapshot(conn, cfg: Config, term_id: str) -> int:
    """Covariates and indicators of a frozen term, from its snapshot into the DB."""
    from ept.classify.run import term_promises, write_db

    term_promises(conn, cfg, term_id)  # the promise rows must exist
    records = [json.loads(line) for line in snapshot_path(cfg, term_id).read_text(encoding="utf-8").splitlines()
               if line.strip()]
    write_db(conn, records)
    return len(records)


def freeze_blockers(cfg: Config, term_id: str) -> list[str]:
    """§4.8: only after the full run with zero unresolved failures and a passed spot-check."""
    from ept.classify.run import read_interim, read_summary

    out = []
    summary = read_summary(cfg, term_id)
    if not summary:
        out.append("no classify run")
    else:
        if summary.get("limit") is not None or summary.get("promises") != summary.get("promises_in_term"):
            out.append(f"the last run covered {summary.get('promises')} of {summary.get('promises_in_term')} "
                       "promises (run without --limit)")
        if summary.get("unresolved"):
            out.append(f"{summary['unresolved']} unresolved check failures")
    recs = read_interim(cfg, term_id)
    if any(r["sector"] is None for r in recs):
        out.append("promises without covariates")
    sheet = cfg.spotcheck_path("03")
    if not sheet.exists():
        out.append("no spot-check sheet")
    else:
        with sheet.open(encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        if any(not r["verdict"].strip() for r in rows):
            out.append("spot-check verdicts missing")
        elif sum(r["verdict"].strip() == "wrong" for r in rows) * 2 > len(rows):
            out.append("more than half of the spot-check is wrong")
    return out


def _set_frozen_terms(cfg: Config, terms: list[str]) -> None:
    """Rewrite `frozen_terms` inside the `classify:` block of settings.yaml (extract has its own)."""
    path = cfg.root / "config" / "settings.yaml"
    text = path.read_text(encoding="utf-8")
    new, n = re.subn(r"(?m)^(classify:\n(?:[ #].*\n|\n)*?  frozen_terms: )\[.*?\]",
                     lambda m: m.group(1) + "[" + ", ".join(terms) + "]", text, count=1)
    if n != 1:
        raise RuntimeError("classify.frozen_terms not found in settings.yaml")
    path.write_text(new, encoding="utf-8")
    cfg.settings.classify.frozen_terms[:] = terms


def run_freeze(term_id: str) -> dict[str, Any]:
    from ept.classify.run import read_interim

    cfg = get_config()
    check_writable(cfg, term_id)
    blockers = freeze_blockers(cfg, term_id)
    if blockers:
        raise FrozenClassificationError(f"{term_id} can't be frozen yet: " + "; ".join(blockers))
    records = read_interim(cfg, term_id)
    path = snapshot_path(cfg, term_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps({k: r[k] for k in SNAPSHOT_FIELDS}, ensure_ascii=False) + "\n"
                            for r in records), encoding="utf-8")
    _set_frozen_terms(cfg, sorted(set(cfg.settings.classify.frozen_terms) | {term_id}))
    return {"term": term_id, "promises": len(records),
            "indicators": sum(len(r["indicators"]) for r in records),
            "snapshot": path.relative_to(cfg.root).as_posix()}
