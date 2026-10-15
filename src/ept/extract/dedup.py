"""`ept extract dedup` (spec 02 §4.6, D-038, D-050): within-term duplicates, then IDs.

1. Every pair of promise texts in a term with token-set similarity >= `dedup.candidate_ratio`
   is a candidate.
2. Candidates go to the bulk model with `dedup_check.md`, `dedup.pairs_per_call` per call.
3. On "same", the later piece (document order) is dropped and logged in promise_dedup.csv;
   on "not same" both are kept (high-similarity "not same" pairs feed spot-check group e).
4. IDs only after dedup: `{term}-{seq:04d}`, contiguous in document order; `parent_group` =
   unit_id; `page` = page where `source_text` starts; `section` = `section_en`.
5. Coverage check for running-number manifestos: every printed main item maps to >= 1
   promise or to a logged reason; holes in the printed sequence are explained gaps.
"""

from __future__ import annotations

import csv
import json
import unicodedata
from collections import Counter
from typing import Any, Optional

from pydantic import BaseModel
from rapidfuzz import fuzz

from ept import db
from ept.config import Config, get_config
from ept.extract.checks import norm
from ept.extract.freeze import check_writable, is_frozen, load_frozen
from ept.extract.pages import term_dir
from ept.extract.promises import Accepted, read_pieces
from ept.extract.units import Unit, number_gaps, read_units
from ept.llm import LLMClient, QuotaExhausted
from ept.runs import finish_run, progress, start_run
from ept.schema import Promise

PROMPT = "dedup_check"
ZERO_WIDTH_CHARS = "\u200b\u200c\u200d\ufeff"
DEDUP_COLUMNS = ["term", "kept_id", "kept_unit_id", "kept_text", "dropped_unit_id", "dropped_text", "similarity",
                 "llm_same", "reason", "action"]


class PairOut(BaseModel):
    pair_id: int
    same: bool
    reason: str = ""


class DedupOut(BaseModel):
    pairs: list[PairOut]


def candidate_pairs(texts: list[str], ratio: float) -> list[tuple[int, int, float]]:
    """(i, j, similarity) with i < j and token-set similarity >= ratio, in document order."""
    out = []
    cutoff = ratio * 100
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            score = fuzz.token_set_ratio(texts[i], texts[j], score_cutoff=cutoff)
            if score >= cutoff:
                out.append((i, j, round(score / 100, 3)))
    return out


def ask_pairs(client: LLMClient, cfg: Config, texts: list[str],
              pairs: list[tuple[int, int, float]]) -> dict[tuple[int, int], PairOut]:
    size = cfg.settings.extract.dedup.pairs_per_call
    out: dict[tuple[int, int], PairOut] = {}
    for b in range(0, len(pairs), size):
        batch = pairs[b:b + size]
        payload = json.dumps([{"pair_id": k, "a": texts[i], "b": texts[j]} for k, (i, j, _) in enumerate(batch)],
                             ensure_ascii=False, indent=1)
        res = client.complete_json(PROMPT, {"pairs": payload}, DedupOut)
        by_id = {p.pair_id: p for p in res.pairs}
        for k, (i, j, _) in enumerate(batch):
            if k in by_id:
                out[(i, j)] = by_id[k]
    return out


def source_offset(source_text: str, unit_text: str) -> int:
    """Offset in `unit_text` where `source_text` starts, matching after NFC/whitespace normalisation."""
    raw = unit_text.find(source_text)
    if raw >= 0:
        return raw
    chars, index = [], []  # normalised text and, per character, its offset in the original
    for k, ch in enumerate(unicodedata.normalize("NFC", unit_text)):
        if ch in ZERO_WIDTH_CHARS:
            continue
        if ch.isspace():
            if not chars or chars[-1] == " ":
                continue
            ch = " "
        chars.append(ch)
        index.append(k)
    pos = "".join(chars).find(norm(source_text))
    return index[pos] if pos >= 0 else 0


def page_of(unit: Unit, offset: int) -> int:
    page = unit.page_start
    for start, p in unit.page_offsets:
        if start <= offset:
            page = p
    return page


def coverage(units: list[Unit], kept_units: set[str], dropped_units: dict[str, str],
             deduped_units: set[str]) -> dict[str, Any]:
    """Running-number manifestos: each printed main item -> promise, logged drop or dedup."""
    main = [u for u in units if u.marker == "running_number"]
    if not main:
        return {}
    rows, unexplained = [], []
    for u in main:
        if u.unit_id in kept_units:
            status = "promise"
        elif u.unit_id in deduped_units:
            status = "dedup"
        elif u.unit_id in dropped_units:
            status = f"dropped: {dropped_units[u.unit_id]}"
        else:
            status = "unexplained"
            unexplained.append(u.number)
        rows.append({"number": u.number, "unit_id": u.unit_id, "status": status})
    return {"main_items": len(main), "not_printed": number_gaps([u.number for u in main]) if len(main) else [],
            "unexplained": unexplained, "items": rows}


def _units_processed(cfg: Config, term: str, default: int) -> int:
    path = term_dir(cfg, term) / "promises_summary.json"
    return json.loads(path.read_text(encoding="utf-8"))["units"] if path.exists() else default


def _dropped_kinds(cfg: Config, term: str) -> dict[str, str]:
    path = cfg.path("extract_dropped")
    out: dict[str, set[str]] = {}
    if path.exists():
        with path.open(encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                if r["term"] == term:
                    out.setdefault(r["unit_id"], set()).add(r["kind"])
    return {k: "no promise (" + ", ".join(sorted(v)) + ")" for k, v in out.items()}


def dedup_term(client: LLMClient, cfg: Config, term: str) -> dict[str, Any]:
    pieces = read_pieces(cfg, term)
    units = {u.unit_id: u for u in read_units(cfg, term)}
    order = {uid: k for k, uid in enumerate(units)}
    pieces.sort(key=lambda a: (order[a.unit_id], a.piece))
    texts = [a.text for a in pieces]
    pairs = candidate_pairs(texts, cfg.settings.extract.dedup.candidate_ratio)
    progress(f"dedup: {term} {len(pieces)} pieces, {len(pairs)} candidate pairs")
    answers = ask_pairs(client, cfg, texts, pairs)
    dropped: dict[int, int] = {}  # later index -> earlier index it duplicates
    for i, j, _ in pairs:
        a = answers.get((i, j))
        if a and a.same and j not in dropped:
            dropped[j] = i
    keep = [k for k in range(len(pieces)) if k not in dropped]
    ids = {k: f"{term}-{n:04d}" for n, k in enumerate(keep, 1)}
    lang = cfg.profiles()[term].lang

    def root(k: int) -> int:
        while k in dropped:
            k = dropped[k]
        return k

    rows = []
    for i, j, sim in pairs:
        a = answers.get((i, j))
        rows.append({"term": term, "kept_id": ids.get(root(i), ""), "kept_unit_id": pieces[i].unit_id,
                     "kept_text": texts[i], "dropped_unit_id": pieces[j].unit_id, "dropped_text": texts[j],
                     "similarity": sim, "llm_same": "" if a is None else a.same,
                     "reason": "" if a is None else a.reason,
                     "action": "dropped_later" if dropped.get(j) == i else "kept_both"})
    section_en = canonical_sections(pieces, units, cfg.profiles()[term].section_glossary)
    promises = []
    for k in keep:
        a: Accepted = pieces[k]
        u = units[a.unit_id]
        promises.append(Promise(promise_id=ids[k], term_id=term, text=a.text, source_text=a.source_text,
                                source_lang=lang, section=section_en.get(units[a.unit_id].section, a.section_en),
                                page=page_of(u, source_offset(a.source_text, u.text)), parent_group=a.unit_id))
    kept_units = {p.parent_group for p in promises}
    deduped_units = {pieces[j].unit_id for j in dropped} - kept_units
    processed = list(units.values())[:_units_processed(cfg, term, len(units))]  # a --limit run covers N units
    cov = coverage(processed, kept_units, _dropped_kinds(cfg, term), deduped_units)
    return {"promises": promises, "dedup_rows": rows, "coverage": cov, "pairs": len(pairs),
            "dropped": len(dropped)}


def canonical_sections(pieces: list[Accepted], units: dict[str, Unit], glossary: dict[str, str]) -> dict[Any, str]:
    """One English name per printed section: the most common model rendering among its units (batches
    rendered the same heading differently), with the profile's fixed renderings for heading words applied
    to the first segment (D-061)."""
    votes: dict[Any, Counter] = {}
    for a in pieces:
        if a.section_en:
            votes.setdefault(units[a.unit_id].section, Counter())[a.section_en] += 1
    out = {}
    for section, c in votes.items():
        name = c.most_common(1)[0][0]
        if glossary and section:
            head, _, rest_ta = section.partition(" / ")
            for word, fixed in glossary.items():
                head = head.replace(word, fixed)
            _, _, rest_en = name.partition(" / ")
            name = f"{head} / {rest_en}" if rest_ta and rest_en else (head if not rest_ta else name)
        out[section] = name
    return out


def write_promises(conn, term: str, promises: list[Promise]) -> None:
    with conn:
        conn.execute("DELETE FROM promises WHERE term_id = ?", (term,))
        for p in promises:
            db.upsert(conn, p, commit=False)


def _rewrite_dedup_csv(cfg: Config, term: str, rows: list[dict[str, Any]]) -> None:
    path = cfg.path("promise_dedup")
    keep = []
    if path.exists():
        with path.open(encoding="utf-8", newline="") as f:
            keep = [r for r in csv.DictReader(f) if r.get("term") != term]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=DEDUP_COLUMNS)
        w.writeheader()
        w.writerows(keep + rows)


def run_dedup(term: Optional[str] = None, limit: Optional[int] = None, force: bool = False) -> dict[str, Any]:
    """Works on the pieces of the last `promises` run (a `--limit` run gives provisional IDs)."""
    cfg = get_config()
    profiles = cfg.profiles()
    terms = [term] if term else list(profiles)
    run_id = start_run("extract-dedup", {"term": term, "limit": limit, "force": force})
    client = LLMClient(cfg)
    conn = db.connect()
    db.init_schema(conn)
    db.sync_terms(conn)
    stats: dict[str, Any] = {"promises": 0, "pairs": 0, "dropped": 0, "llm_calls": 0, "skipped": {}, "stopped": None}
    try:
        for term_id in terms:
            if is_frozen(cfg, term_id):
                if force:
                    check_writable(cfg, term_id, "dedup")
                stats["skipped"][term_id] = f"frozen: {load_frozen(conn, cfg, term_id)} promises loaded from the snapshot"
                continue
            if not read_pieces(cfg, term_id):
                stats["skipped"][term_id] = "no pieces (run `extract promises`)"
                continue
            before = client.calls
            try:
                out = dedup_term(client, cfg, term_id)
            except QuotaExhausted as e:
                stats["stopped"] = str(e)
                break
            finally:
                stats["llm_calls"] += client.calls - before
            write_promises(conn, term_id, out["promises"])
            _rewrite_dedup_csv(cfg, term_id, out["dedup_rows"])
            (term_dir(cfg, term_id) / "coverage.json").write_text(json.dumps(out["coverage"], indent=1),
                                                                   encoding="utf-8")
            stats["promises"] += len(out["promises"])
            stats["pairs"] += out["pairs"]
            stats["dropped"] += out["dropped"]
            if out["coverage"]:
                stats[f"{term_id}_coverage_unexplained"] = len(out["coverage"]["unexplained"])
    finally:
        finish_run(run_id, stats, models={"bulk": cfg.settings.llm.models.get("bulk")},
                   status=f"stopped: {stats['stopped']}" if stats["stopped"] else "done")
        conn.close()
    return stats
