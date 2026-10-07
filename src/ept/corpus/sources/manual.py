"""S7: hand-added files in data/raw/evidence/_manual/ described by manual_manifest.csv (spec 01 §2.3).

Columns: filename, doc_type, department, title, doc_date, date_precision, lang, source_url, note.
Dates come from the manifest (`date_source=manual`).
"""

from __future__ import annotations

import csv
import datetime as dt
import logging
from typing import Iterator

from ept.corpus.catalogue import MANUAL_PREFIX, CatalogueItem
from ept.corpus.sources.base import SourceAdapter
from ept.dates import fiscal_year_of, normalize_fy
from ept.runs import Budget
from ept.schema import DocType, Discovery

log = logging.getLogger(__name__)

COLUMNS = ["filename", "doc_type", "department", "title", "doc_date", "date_precision", "lang", "source_url", "note"]


class Manual(SourceAdapter):
    name = "manual"

    def catalogue(self, budget: Budget, force: bool = False) -> Iterator[CatalogueItem]:
        manifest = self.cfg.path("manual_manifest")
        if not manifest.exists():
            manifest.parent.mkdir(parents=True, exist_ok=True)
            with manifest.open("w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow(COLUMNS)
            return
        with manifest.open(newline="", encoding="utf-8") as f:
            for n, row in enumerate(csv.DictReader(f), start=2):
                name = (row.get("filename") or "").strip()
                if not name:
                    continue
                problems = []
                if not (self.cfg.path("manual_dir") / name).exists():
                    problems.append("file missing")
                doc_type = (row.get("doc_type") or "").strip()
                if doc_type not in {d.value for d in DocType}:
                    problems.append(f"bad doc_type {doc_type!r}")
                date = None
                if row.get("doc_date"):
                    try:
                        date = dt.date.fromisoformat(row["doc_date"].strip())
                    except ValueError:
                        problems.append(f"bad doc_date {row['doc_date']!r}")
                if problems:
                    log.warning("manual_manifest.csv line %d (%s): %s", n, name, "; ".join(problems))
                yield CatalogueItem(
                    url=MANUAL_PREFIX + name,
                    source=self.name,
                    doc_type=doc_type if doc_type in {d.value for d in DocType} else None,
                    department=(row.get("department") or "").strip() or None,
                    title=(row.get("title") or "").strip() or name,
                    listing_date=date,
                    fiscal_year=fiscal_year_of(date) if date else normalize_fy(name),
                    lang_hint=(row.get("lang") or "en").strip() or "en",
                    identifiers={k: v for k, v in {
                        "date_precision": (row.get("date_precision") or "").strip(),
                        "source_url": (row.get("source_url") or "").strip(),
                        "note": (row.get("note") or "").strip(),
                    }.items() if v},
                    discovery=Discovery.manual.value,
                    excluded_reason="; ".join(problems) or None,
                )
