"""Tamil catalogue pairing (spec 01 §4.6, D-017): data/interim/lang_pairs.csv.

Tamil items (catalogue items tagged Tamil, plus documents whose text was detected as Tamil) are
paired with an English item by key, most specific first:
  GO: (dept, GO number, series, year); budget speech / Governor's address / policy note:
  (doc_type, dept, fiscal year, subtype if any); otherwise (doc_type, dept, date). No match = `tamil_only`.
Tamil documents are never added to the evidence pool here.
"""

from __future__ import annotations

import csv
from typing import Any, Optional

from ept import db
from ept.config import Config, get_config
from ept.corpus.catalogue import EXCLUDED, CatalogueItem, doc_id_for_url, load_all
from ept.corpus.fetch import in_range
from ept.schema import DocType

COLUMNS = ["ta_item", "ta_doc_id", "en_doc_id", "pair_key", "status", "doc_type", "year", "title"]
FY_TYPES = {DocType.budget_speech.value, DocType.governor_address.value, DocType.policy_note.value}


def pair_key(doc_type: Optional[str], department: Optional[str], identifiers: dict[str, str],
             fiscal_year: Optional[str], date: Optional[str], subtype: Optional[str] = None) -> Optional[str]:
    if doc_type == DocType.go.value and identifiers.get("go_number"):
        return "|".join(["go", department or "?", identifiers["go_number"], identifiers.get("go_series", "?"),
                         identifiers.get("go_year", "?")])
    if doc_type in FY_TYPES and fiscal_year:
        # subtype keeps interim and revised speeches of the same year apart
        return "|".join([doc_type, department or "?", fiscal_year] + ([subtype] if subtype else []))
    if date:
        return "|".join([doc_type or "?", department or "?", date])
    return None


def _item_key(i: CatalogueItem) -> Optional[str]:
    return pair_key(i.doc_type, i.department, i.identifiers, i.fiscal_year,
                    i.listing_date.isoformat() if i.listing_date else None, i.subtype)


def _relevant(i: CatalogueItem, cfg: Config) -> bool:
    """Catalogued with a document type and inside the evidence window. An exclusion that only says
    another source already has the English version ("covered by ...") doesn't apply to Tamil."""
    if i.doc_type is None:
        return False
    if i.status == EXCLUDED and not (i.excluded_reason or "").startswith("covered by"):
        return False
    w = cfg.settings.evidence_window
    return in_range(i, w.start, w.end_or_today())


def build_pairs(cfg: Optional[Config] = None) -> list[dict[str, Any]]:
    cfg = cfg or get_config()
    items = [i for c in load_all(cfg).values() for i in c if _relevant(i, cfg)]
    english: dict[str, str] = {}
    for i in items:
        if (i.lang_hint or "en") == "en":
            key = _item_key(i)
            if key:
                english.setdefault(key, i.doc_id or doc_id_for_url(i.url))
    rows = []
    seen: set[str] = set()
    for i in items:
        if i.lang_hint != "ta":
            continue
        key = _item_key(i)
        en = english.get(key) if key else None
        year = (i.listing_date.isoformat()[:4] if i.listing_date else (i.fiscal_year or "")[:4]) or "?"
        rows.append({"ta_item": i.url, "ta_doc_id": i.doc_id or "", "en_doc_id": en or "", "pair_key": key or "",
                     "status": "paired" if en else "tamil_only", "doc_type": i.doc_type, "year": year,
                     "title": (i.title or "")[:120]})
        seen.add(i.doc_id or doc_id_for_url(i.url))
    # documents whose text turned out to be Tamil although the file name didn't say so
    conn = db.connect()
    for r in db.query(conn, "SELECT * FROM documents WHERE lang = 'ta'"):
        if r["doc_id"] in seen:
            continue
        key = pair_key(r["doc_type"], r["department"], {}, r["fiscal_year"], r["doc_date"])
        en = english.get(key) if key else None
        rows.append({"ta_item": r["source_url"] or r["local_path"], "ta_doc_id": r["doc_id"], "en_doc_id": en or "",
                     "pair_key": key or "", "status": "paired" if en else "tamil_only", "doc_type": r["doc_type"],
                     "year": (r["doc_date"] or r["fiscal_year"] or "?")[:4], "title": (r["title"] or "")[:120]})
    conn.close()
    return rows


def write_pairs(cfg: Optional[Config] = None) -> dict[str, int]:
    cfg = cfg or get_config()
    rows = build_pairs(cfg)
    path = cfg.path("lang_pairs")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: (r["doc_type"], r["year"], r["ta_item"])))
    return {"tamil_items": len(rows), "paired": sum(r["status"] == "paired" for r in rows),
            "tamil_only": sum(r["status"] == "tamil_only" for r in rows)}
