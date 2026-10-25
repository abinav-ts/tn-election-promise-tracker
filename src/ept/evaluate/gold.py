"""Gold labels: loading and validation (spec 06 §G4, §G9). Only `ept.evaluate` opens the label files."""

from __future__ import annotations

import csv
import re
from pathlib import Path

E1 = {"fulfilled", "partial", "diluted"}
NO_EVIDENCE_OK = {"not_started", "unverifiable"}
STATUSES = {"fulfilled", "partial", "diluted", "in_progress", "not_started", "blocked_external", "unverifiable"}
CHUNK_RE = re.compile(r"^[0-9a-f]{16}-\d{4}$")


class LabelError(ValueError):
    pass


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as f:
        return [dict(r) for r in csv.DictReader(f)]


def tags(notes: str) -> dict:
    n = notes or ""
    m = re.search(r"\[after_term:([0-9-]+)\]", n)
    return {"unsure": "[unsure]" in n, "directional": "[directional]" in n, "web_checked": "[web-checked]" in n,
            "after_term": m.group(1) if m else None}


def validate_row(r: dict, window: tuple[str, str]) -> None:
    pid = r.get("promise_id")
    st = (r.get("status") or "").strip()
    if st not in STATUSES:
        raise LabelError(f"{pid}: status {st!r} is not in §8")
    date = (r.get("realisation_date") or "").strip()
    if (st in E1) != bool(date):
        raise LabelError(f"{pid}: a date is required exactly when the status is fulfilled, partial or diluted")
    if date and not (window[0] <= date <= window[1]):
        raise LabelError(f"{pid}: date {date} outside the term window {window}")
    if date and (r.get("date_precision") or "") not in ("day", "month", "year"):
        raise LabelError(f"{pid}: date_precision missing")
    if st not in NO_EVIDENCE_OK and not (r.get("evidence") or "").strip():
        raise LabelError(f"{pid}: evidence is required for status {st}")
    if tags(r.get("notes", ""))["directional"] and st in ("partial", "diluted"):
        raise LabelError(f"{pid}: a directional promise cannot be partial or diluted")


def load_prefix(labels: list[dict], sample: list[dict], windows: dict[str, tuple[str, str]], min_labels: int
                ) -> list[dict]:
    """Labels as a gap-free prefix of the sample order; each row gets `order` and `term_id`. Refuses too few."""
    by = {r["promise_id"]: r for r in labels}
    out = []
    for s in sorted(sample, key=lambda x: int(x["order"])):
        r = by.get(s["promise_id"])
        if r is None:
            break
        validate_row(r, windows[s["term_id"]])
        out.append({**r, "order": int(s["order"]), "term_id": s["term_id"]})
    if len(out) < min_labels:
        raise LabelError(f"only {len(out)} complete labels form a gap-free prefix of the sample order; "
                         f"the minimum is {min_labels}")
    extra = len(by) - len(out)
    if extra > 0:
        for r in out:
            pass
    return out
