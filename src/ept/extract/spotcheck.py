"""`ept extract spotcheck` (spec 02 §4.7, global §12.4): the 7–10 most problematic items.

Problem groups, in priority order:
  a. a check failure (unresolved, or resolved by retry/override) or a coverage gap;
  b. promises from the weakest pages (lowest validity / OCR confidence, flagged or
     accepted-below-threshold font-map pages, largest vision-vs-OCR disagreement);
  c. a V3 `names_to_check` flag (possible model-memory leak);
  d. split outliers (> max_promises_per_unit) and dropped pieces whose source carries a
     commitment marker (may be missed promises);
  e. dedup decisions near the threshold.
At most `extract.spotcheck.per_term` items per term and `per_term_group` per term and group (D-054);
7–10 items; verdict/note left empty.
"""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from typing import Any, Optional

from ept import db
from ept.config import Config, get_config
from ept.extract.pages import manifesto_path, read_records, term_dir
from ept.extract.units import read_units

COLUMNS = ["item_id", "term", "group", "why_flagged", "what_to_check", "pdf_page", "unit_text", "extracted",
           "verdict", "note"]
GROUPS = "abcde"
_EN_COMMIT = re.compile(r"\b(will|shall)\b", re.I)
_TA_COMMIT = re.compile("ப்படும்")


@dataclass
class Item:
    item_id: str
    term: str
    group: str
    score: float  # within-group ordering, higher = more problematic
    why: str
    what: str
    unit_id: str
    page: Optional[int]
    extracted: str


def _csv(path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def build(cfg: Config, conn, terms: list[str]) -> list[Item]:
    ex = cfg.settings.extract
    items: list[Item] = []
    failures, dropped, dedup = (_csv(cfg.path(k)) for k in ("extract_failures", "extract_dropped", "promise_dedup"))
    for term in terms:
        units = {u.unit_id: u for u in read_units(cfg, term)}
        promises = db.query(conn, "SELECT * FROM promises WHERE term_id = ? ORDER BY promise_id", (term,))
        by_unit: dict[str, list] = {}
        for p in promises:
            by_unit.setdefault(p["parent_group"], []).append(p)

        def shown(uid: str) -> str:
            return " || ".join(f"{p['promise_id']}: {p['text']}" for p in by_unit.get(uid, [])) or "(no promise kept)"

        # a. failures and coverage gaps
        for f in (r for r in failures if r["term"] == term):
            how = f"resolved by {f['resolved_by']}" if f["resolved_by"] else "UNRESOLVED"
            items.append(Item(f"{f['unit_id']}:{f['rule']}", term, "a", 2.0 if not f["resolved_by"] else 1.0,
                              f"check {f['rule']} failed ({how}): {f['detail'][:200]}",
                              "Is the kept promise text faithful to the unit (no added number/name)? "
                              "If unresolved: write the correct promise as an override row.",
                              f["unit_id"], units[f["unit_id"]].page_start if f["unit_id"] in units else None,
                              shown(f["unit_id"])))
        cov_path = term_dir(cfg, term) / "coverage.json"
        cov = json.loads(cov_path.read_text()) if cov_path.exists() else {}
        for row in cov.get("items", []):
            if row["status"] == "unexplained":
                items.append(Item(f"{row['unit_id']}:coverage", term, "a", 1.5, f"item {row['number']} maps to "
                                  "no promise and no logged drop", "Does this item contain a promise?",
                                  row["unit_id"], units[row["unit_id"]].page_start, shown(row["unit_id"])))
        # b. weakest pages
        weak: dict[int, tuple[float, str]] = {}
        for r in read_records(cfg, term):
            if r.get("lang") == "en" or r.get("tamil_share") is None:
                continue
            reasons, score = [], 0.0
            if r.get("flags"):
                reasons.append("; ".join(r["flags"]))
                score += 1
            if r.get("tamil_share") is not None and r["tamil_share"] < ex.fontmap_min_tamil_share:
                reasons.append(f"page Tamil share {r['tamil_share']} (accepted: Latin-font English words)")
                score += ex.fontmap_min_tamil_share - r["tamil_share"]
            if r.get("validity") is not None and r["validity"] < 1.0:
                reasons.append(f"validity {r['validity']}")
                score += 1.0 - r["validity"]
            if r.get("vision_cer") is not None:
                reasons.append(f"vision-vs-OCR CER {r['vision_cer']}")
                score += r["vision_cer"]
            if reasons and score > 0:
                weak[r["page"]] = (score, "; ".join(reasons))
        for p in promises:
            pg = p["page"]
            if pg in weak:
                items.append(Item(p["promise_id"], term, "b", weak[pg][0], f"weak page {pg}: {weak[pg][1]}",
                                  "Compare source_text with the printed page; is the promise text right?",
                                  p["parent_group"], pg, f"{p['promise_id']}: {p['text']} | source: {p['source_text']}"))
        # c. V3 flags (Tamil source)
        pieces_path = term_dir(cfg, term) / "pieces.jsonl"
        pieces = [json.loads(l) for l in pieces_path.read_text(encoding="utf-8").splitlines()] if pieces_path.exists() else []
        texts = {(p["parent_group"], p["text"]): p for p in promises}
        for pc in pieces:
            if pc.get("v3_flag") and (pc["unit_id"], pc["text"]) in texts:
                p = texts[(pc["unit_id"], pc["text"])]
                names = [n for n in pc["names_to_check"] if n not in set(ex.common_words)]
                items.append(Item(p["promise_id"], term, "c", float(len(names)),
                                  f"names not found verbatim in the Tamil unit: {', '.join(names)}",
                                  "Is each name a transliteration of a name printed in the unit (not added from "
                                  "model memory)?", p["parent_group"], p["page"],
                                  f"{p['promise_id']}: {p['text']} | source: {p['source_text']}"))
        # d. split outliers and dropped pieces with a commitment marker
        for uid, ps in by_unit.items():
            if len(ps) > ex.max_promises_per_unit:
                items.append(Item(f"{uid}:split", term, "d", float(len(ps)), f"{len(ps)} promises from one unit "
                                  f"(> {ex.max_promises_per_unit})", "Is the split right (S1–S3)?", uid,
                                  units[uid].page_start if uid in units else None, shown(uid)))
        for d in (r for r in dropped if r["term"] == term and r["kind"] in ("achievement", "values", "other")):
            src = d["source_text"]
            if _EN_COMMIT.search(src) or _TA_COMMIT.search(src):
                items.append(Item(f"{d['unit_id']}:drop", term, "d", 0.5 + min(len(src), 400) / 1000,
                                  f"dropped as {d['kind']} but contains a future marker", "Is this a missed promise?",
                                  d["unit_id"], units[d["unit_id"]].page_start if d["unit_id"] in units else None,
                                  f"dropped ({d['kind']}): {src[:300]}"))
        # e. dedup near the threshold
        for r in (r for r in dedup if r["term"] == term):
            sim = float(r["similarity"])
            if r["action"] == "kept_both":
                score, why = sim, f"similarity {sim} but judged different"
            else:
                score, why = 1.0 - sim + ex.dedup.candidate_ratio, f"similarity {sim}, judged the same: later dropped"
            items.append(Item(f"{r['dropped_unit_id']}:dedup", term, "e", score, why,
                              "Same commitment (action, beneficiaries, amount)?", r["dropped_unit_id"],
                              units[r["dropped_unit_id"]].page_start if r["dropped_unit_id"] in units else None,
                              f"kept {r['kept_id']}: {r['kept_text']} || other: {r['dropped_text']}"))
    return items


def select(items: list[Item], max_items: int, per_term: int, per_term_group: int) -> list[Item]:
    ranked = sorted(items, key=lambda it: (GROUPS.index(it.group), -it.score, it.item_id))
    out, per, per_group, seen = [], {}, {}, set()
    for it in ranked:
        key = (it.unit_id, it.group)
        if (per.get(it.term, 0) >= per_term or per_group.get((it.term, it.group), 0) >= per_term_group
                or key in seen):
            continue
        out.append(it)
        seen.add(key)
        per[it.term] = per.get(it.term, 0) + 1
        per_group[(it.term, it.group)] = per_group.get((it.term, it.group), 0) + 1
        if len(out) == max_items:
            break
    return out


def run_spotcheck(term: Optional[str] = None) -> dict[str, Any]:
    cfg = get_config()
    s = cfg.settings.spotcheck
    profiles = cfg.profiles()
    terms = [term] if term else [t for t in profiles if read_units(cfg, t)]
    conn = db.connect()
    caps = cfg.settings.extract.spotcheck
    chosen = select(build(cfg, conn, terms), s.max_items, caps.per_term, caps.per_term_group)
    conn.close()
    units = {t: {u.unit_id: u for u in read_units(cfg, t)} for t in terms}
    path = cfg.spotcheck_path("02")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        for it in chosen:
            u = units[it.term].get(it.unit_id)
            pdf = manifesto_path(cfg, profiles[it.term]).relative_to(cfg.root).as_posix()
            w.writerow({"item_id": it.item_id, "term": it.term, "group": it.group, "why_flagged": it.why,
                        "what_to_check": it.what, "pdf_page": f"{pdf} p{it.page}",
                        "unit_text": u.text if u else "", "extracted": it.extracted, "verdict": "", "note": ""})
    return {"rows": len(chosen), "below_minimum": len(chosen) < s.min_items, "path": str(path),
            "groups": [it.group for it in chosen]}
