"""`ept extract promises` (spec 02 §4.5): units -> checked promise pieces.

Units go to the bulk model in fixed batches of `extract.units_per_call`, in document
order (deterministic batches -> stable cache keys). A unit whose output is missing or
holds a promise failing V1–V4 is retried alone, once; a piece that still fails is
logged to extract_failures_02.csv and not kept. Human fixes come from
config/promise_overrides.csv: a unit with override rows takes those rows as its
promises (checked like any other piece) instead of the model's promises.

Writes data/interim/manifestos/{term}/pieces.jsonl (accepted promise pieces, before
deduplication and IDs), and the term's rows of extract_dropped_02.csv and
extract_failures_02.csv.
"""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal, Optional

from pydantic import BaseModel

from ept.config import Config, ManifestoProfile, get_config
from ept.extract.checks import check_promise
from ept.extract.freeze import check_writable, is_frozen
from ept.extract.pages import term_dir
from ept.extract.units import Unit, read_units
from ept.llm import LLMClient, LLMValidationError, QuotaExhausted
from ept.runs import finish_run, progress, start_run

PROMPT = "extract_promises"
LANGUAGE = {"en": "English", "ta": "Tamil"}
DROPPED_COLUMNS = ["term", "unit_id", "kind", "text", "source_text", "reason"]
FAILURE_COLUMNS = ["term", "unit_id", "rule", "detail", "resolved_by"]
OVERRIDE_COLUMNS = ["unit_id", "text", "source_text", "section_en", "note"]


class Piece(BaseModel):
    kind: Literal["promise", "achievement", "criticism", "values", "other"]
    text: str = ""
    source_text: str


class UnitOut(BaseModel):
    unit_id: str
    section_en: Optional[str] = None
    pieces: list[Piece]


class ExtractOut(BaseModel):
    units: list[UnitOut]


@dataclass
class Accepted:
    """One promise piece that passed V1–V4 (V3 may be a Tamil flag)."""

    term: str
    unit_id: str
    piece: int  # order within the unit
    text: str
    source_text: str
    section_en: Optional[str]
    source_lang: str
    origin: str  # llm | override
    warnings: list[str] = field(default_factory=list)
    names_to_check: list[str] = field(default_factory=list)
    v3_flag: bool = False
    retried: bool = False


@dataclass
class UnitResult:
    unit: Unit
    accepted: list[Accepted]
    dropped: list[dict[str, Any]]
    failures: list[dict[str, Any]]  # unresolved
    resolved: list[dict[str, Any]]  # failures of the first attempt fixed by the retry
    n_promises_raw: int = 0


# --- one call -------------------------------------------------------------


def unit_payload(units: list[Unit]) -> str:
    return json.dumps([{"unit_id": u.unit_id, "section": u.section, "text": u.text} for u in units],
                      ensure_ascii=False, indent=1)


def call_batch(client: LLMClient, term: str, profile: ManifestoProfile, units: list[Unit],
               model: Optional[str] = None) -> dict[str, UnitOut]:
    """One call for `units`; returns the outputs keyed by unit_id (units the model skipped are absent)."""
    party = term.split("-")[0]
    out = client.complete_json(PROMPT, {"party": party, "language": LANGUAGE[profile.lang],
                                        "units": unit_payload(units)}, ExtractOut, model=model)
    wanted = {u.unit_id for u in units}
    return {u.unit_id: u for u in out.units if u.unit_id in wanted}


def judge_unit(term: str, unit: Unit, out: Optional[UnitOut], lang: str, cfg: Config,
               retried: bool = False) -> tuple[list[Accepted], list[dict[str, Any]], list[dict[str, Any]], int]:
    """Check one unit's output: (accepted promises, dropped pieces, failures, promises returned)."""
    ex = cfg.settings.extract
    if out is None:
        return [], [], [{"term": term, "unit_id": unit.unit_id, "rule": "V4", "detail": "unit missing from output"}], 0
    if not out.pieces:
        return [], [], [{"term": term, "unit_id": unit.unit_id, "rule": "V4", "detail": "no pieces"}], 0
    accepted, dropped, failures = [], [], []
    common = set(ex.common_words)
    n = 0
    for i, p in enumerate(out.pieces):
        if p.kind != "promise":
            dropped.append({"term": term, "unit_id": unit.unit_id, "kind": p.kind, "text": p.text,
                            "source_text": p.source_text, "reason": f"kind {p.kind}"})
            continue
        n += 1
        r = check_promise(p.text, p.source_text, unit.text, lang, common_words=common, max_words=ex.max_text_words)
        if not r.ok:
            for f in r.failures:
                failures.append({"term": term, "unit_id": unit.unit_id, "rule": f.split(":")[0],
                                 "detail": f"{f} | text: {p.text} | source: {p.source_text}"})
            continue
        accepted.append(Accepted(term=term, unit_id=unit.unit_id, piece=i, text=p.text, source_text=p.source_text,
                                 section_en=out.section_en, source_lang=lang, origin="llm", warnings=r.warnings,
                                 names_to_check=r.names_to_check, v3_flag=r.v3_flag, retried=retried))
    return accepted, dropped, failures, n


# --- overrides --------------------------------------------------------------


def read_overrides(cfg: Config) -> dict[str, list[dict[str, str]]]:
    path = cfg.path("promise_overrides")
    out: dict[str, list[dict[str, str]]] = {}
    if not path.exists():
        return out
    with path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if row.get("unit_id"):
                out.setdefault(row["unit_id"], []).append(row)
    return out


def apply_overrides(term: str, unit: Unit, rows: list[dict[str, str]], lang: str,
                    cfg: Config) -> tuple[list[Accepted], list[dict[str, Any]]]:
    """Override rows pass V1–V4 like any other piece (§4.5, leakage rules 1/3/6)."""
    ex = cfg.settings.extract
    accepted, failures = [], []
    for i, row in enumerate(rows):
        r = check_promise(row["text"], row["source_text"], unit.text, lang, common_words=set(ex.common_words),
                          max_words=ex.max_text_words)
        if not r.ok:
            failures += [{"term": term, "unit_id": unit.unit_id, "rule": f.split(":")[0],
                          "detail": f"override: {f}"} for f in r.failures]
            continue
        accepted.append(Accepted(term=term, unit_id=unit.unit_id, piece=i, text=row["text"],
                                 source_text=row["source_text"], section_en=row.get("section_en") or None,
                                 source_lang=lang, origin="override", warnings=r.warnings,
                                 names_to_check=r.names_to_check, v3_flag=r.v3_flag))
    return accepted, failures


# --- a term -------------------------------------------------------------------


def process_units(client: LLMClient, cfg: Config, term: str, profile: ManifestoProfile,
                  units: list[Unit]) -> list[UnitResult]:
    size = cfg.settings.extract.units_per_call
    overrides = read_overrides(cfg)
    results = []
    for b in range(0, len(units), size):
        batch = units[b:b + size]
        progress(f"promises: {term} units {b + 1}-{b + len(batch)} of {len(units)}")
        try:
            outs = call_batch(client, term, profile, batch)
        except LLMValidationError:
            outs = {}  # the whole batch is retried unit by unit
        for unit in batch:
            acc, drop, fail, n = judge_unit(term, unit, outs.get(unit.unit_id), profile.lang, cfg)
            resolved: list[dict[str, Any]] = []
            if fail:  # retry this unit alone, once
                try:
                    alone = call_batch(client, term, profile, [unit]).get(unit.unit_id)
                except LLMValidationError:
                    alone = None
                acc2, drop2, fail2, n2 = judge_unit(term, unit, alone, profile.lang, cfg, retried=True)
                if alone is not None:
                    resolved = [dict(f, resolved_by="retry alone") for f in fail] if not fail2 else []
                    acc, drop, n = acc2, drop2, n2
                    fail = fail2 if fail2 else []
            if unit.unit_id in overrides:
                acc_o, fail_o = apply_overrides(term, unit, overrides[unit.unit_id], profile.lang, cfg)
                resolved += [dict(f, resolved_by="override") for f in fail]
                acc, fail = acc_o, fail_o
                drop = [d for d in drop]  # non-promise pieces stay logged
            results.append(UnitResult(unit=unit, accepted=acc, dropped=drop, failures=fail, resolved=resolved,
                                      n_promises_raw=n))
    return results


def pieces_path(cfg: Config, term: str) -> Path:
    return term_dir(cfg, term) / "pieces.jsonl"


def read_pieces(cfg: Config, term: str) -> list[Accepted]:
    path = pieces_path(cfg, term)
    if not path.exists():
        return []
    return [Accepted(**json.loads(line)) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _rewrite_csv(path: Path, columns: list[str], term: str, rows: list[dict[str, Any]]) -> None:
    """Replace this term's rows in a shared CSV, keep other terms' rows."""
    keep = []
    if path.exists():
        with path.open(encoding="utf-8", newline="") as f:
            keep = [r for r in csv.DictReader(f) if r.get("term") != term]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        w.writeheader()
        w.writerows(keep + rows)


def write_term(cfg: Config, term: str, results: list[UnitResult]) -> None:
    with pieces_path(cfg, term).open("w", encoding="utf-8") as f:
        for r in results:
            for a in r.accepted:
                f.write(json.dumps(asdict(a), ensure_ascii=False) + "\n")
    _rewrite_csv(cfg.path("extract_dropped"), DROPPED_COLUMNS, term, [d for r in results for d in r.dropped])
    failures = [dict(f, resolved_by="") for r in results for f in r.failures]
    failures += [f for r in results for f in r.resolved]
    _rewrite_csv(cfg.path("extract_failures"), FAILURE_COLUMNS, term, failures)
    summary = {
        "units": len(results), "promises": sum(len(r.accepted) for r in results),
        "dropped": sum(len(r.dropped) for r in results),
        "unresolved_failures": sum(len(r.failures) for r in results),
        "resolved_failures": sum(len(r.resolved) for r in results),
        "retried_units": sum(1 for r in results if any(a.retried for a in r.accepted) or r.resolved),
        "split_outliers": [r.unit.unit_id for r in results
                           if len(r.accepted) > cfg.settings.extract.max_promises_per_unit],
        "v3_flags": sum(1 for r in results for a in r.accepted if a.v3_flag),
    }
    (term_dir(cfg, term) / "promises_summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")


def run_promises(term: Optional[str] = None, limit: Optional[int] = None, force: bool = False) -> dict[str, Any]:
    """`--limit N` = the first N units per term in document order. `--force` re-checks every unit; LLM
    answers still come from the cache (a prompt version bump is what re-asks the model)."""
    cfg = get_config()
    profiles = cfg.profiles()
    terms = [term] if term else list(profiles)
    run_id = start_run("extract-promises", {"term": term, "limit": limit, "force": force})
    client = LLMClient(cfg)
    stats: dict[str, Any] = {"units": 0, "promises": 0, "unresolved_failures": 0, "llm_calls": 0,
                             "skipped": {}, "stopped": None}
    try:
        for term_id in terms:
            if is_frozen(cfg, term_id):
                if force or term:
                    check_writable(cfg, term_id, "promises")
                stats["skipped"][term_id] = "frozen"
                continue
            units = read_units(cfg, term_id)
            if not units:
                stats["skipped"][term_id] = "no units (run `extract units`)"
                continue
            if limit is not None:
                units = units[:limit]
            before = client.calls
            try:
                results = process_units(client, cfg, term_id, profiles[term_id], units)
            except QuotaExhausted as e:
                stats["stopped"] = str(e)
                stats["llm_calls"] += client.calls - before
                break
            stats["llm_calls"] += client.calls - before
            write_term(cfg, term_id, results)
            stats["units"] += len(results)
            stats["promises"] += sum(len(r.accepted) for r in results)
            stats["unresolved_failures"] += sum(len(r.failures) for r in results)
    finally:
        finish_run(run_id, stats, models={"bulk": cfg.settings.llm.models.get("bulk")},
                   status=f"stopped: {stats['stopped']}" if stats["stopped"] else "done")
    return stats
