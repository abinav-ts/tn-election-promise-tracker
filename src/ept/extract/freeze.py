"""Frozen terms (spec 02 §4.9, D-039): every extract step refuses to re-extract them."""

from __future__ import annotations

from ept.config import Config


class FrozenTermError(RuntimeError):
    pass


def is_frozen(cfg: Config, term_id: str) -> bool:
    return term_id in cfg.settings.extract.frozen_terms


def check_writable(cfg: Config, term_id: str, step: str) -> None:
    """Raise if `step` would rewrite a frozen term's outputs (`--force` included)."""
    if is_frozen(cfg, term_id):
        raise FrozenTermError(
            f"{term_id} is frozen (data/frozen/promises_{term_id}.jsonl); `extract {step}` refuses to touch it. "
            "Un-freezing needs a decision-log entry (spec 02 §4.9)."
        )


# --- `ept extract freeze` (spec 02 §4.9, D-039) ---------------------------------------


def snapshot_path(cfg: Config, term_id: str):
    return cfg.path("frozen") / f"promises_{term_id}.jsonl"


def freeze_blockers(cfg: Config, conn, term_id: str) -> list[str]:
    """§4.9: freeze only after the full run, with zero unresolved failures, no unexplained coverage gap and a
    completed spot-check (no more than half `wrong`)."""
    import csv
    import json

    from ept import db
    from ept.extract.pages import term_dir
    from ept.extract.units import read_units

    out = []
    n = db.query(conn, "SELECT COUNT(*) AS n FROM promises WHERE term_id = ?", (term_id,))[0]["n"]
    if not n:
        out.append("no promises in the DB")
    summary_path = term_dir(cfg, term_id) / "promises_summary.json"
    summary = json.loads(summary_path.read_text()) if summary_path.exists() else {}
    if summary.get("units") != len(read_units(cfg, term_id)):
        out.append(f"the last promises run covered {summary.get('units')} of {len(read_units(cfg, term_id))} units")
    if summary.get("unresolved_failures"):
        out.append(f"{summary['unresolved_failures']} unresolved check failures")
    cov_path = term_dir(cfg, term_id) / "coverage.json"
    cov = json.loads(cov_path.read_text()) if cov_path.exists() else {}
    if cov.get("unexplained"):
        out.append(f"unexplained coverage gaps: {cov['unexplained']}")
    sheet = cfg.spotcheck_path("02")
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
    import re

    path = cfg.root / "config" / "settings.yaml"
    text = path.read_text(encoding="utf-8")
    new, n = re.subn(r"(?m)^(  frozen_terms: )\[.*?\]", lambda m: m.group(1) + "[" + ", ".join(terms) + "]", text,
                     count=1)
    if n != 1:
        raise RuntimeError("extract.frozen_terms not found in settings.yaml")
    path.write_text(new, encoding="utf-8")
    cfg.settings.extract.frozen_terms[:] = terms


def run_freeze(term_id: str) -> dict:
    import json

    from ept import db

    cfg = _cfg()
    check_writable(cfg, term_id, "freeze")
    conn = db.connect()
    try:
        blockers = freeze_blockers(cfg, conn, term_id)
        if blockers:
            raise FrozenTermError(f"{term_id} can't be frozen yet: " + "; ".join(blockers))
        rows = db.select_models(conn, "promises", "term_id = ? ORDER BY promise_id", (term_id,))
    finally:
        conn.close()
    path = snapshot_path(cfg, term_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r.model_dump(mode="json"), ensure_ascii=False) + "\n" for r in rows),
                    encoding="utf-8")
    _set_frozen_terms(cfg, sorted(set(cfg.settings.extract.frozen_terms) | {term_id}))
    return {"term": term_id, "promises": len(rows), "snapshot": path.relative_to(cfg.root).as_posix()}


def load_frozen(conn, cfg: Config, term_id: str) -> int:
    """A frozen term's promises come from its committed snapshot (a lost DB or cache can't change them)."""
    import json

    from ept import db
    from ept.schema import Promise

    rows = [Promise.model_validate(json.loads(line)) for line in
            snapshot_path(cfg, term_id).read_text(encoding="utf-8").splitlines() if line.strip()]
    with conn:
        conn.execute("DELETE FROM promises WHERE term_id = ?", (term_id,))
        for r in rows:
            db.upsert(conn, r, commit=False)
    return len(rows)


def _cfg() -> Config:
    from ept.config import get_config

    return get_config()
