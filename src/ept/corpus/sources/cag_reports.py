"""S5: CAG audit reports on Tamil Nadu, via Wayback CDX only (spec 01 §2.3).

cag.gov.in is unreachable live. Catalogue = Wayback captures under
`cag.gov.in/uploads/download_audit_report/` whose file name mentions Tamil Nadu.
Only full reports are kept: chapter/annexure/index splits, Puducherry reports and
explicit Tamil-language versions are catalogued but excluded.
"""

from __future__ import annotations

import logging
import re
from typing import Iterator

from ept.corpus.catalogue import CatalogueItem
from ept.corpus.sources.base import SourceAdapter
from ept.corpus.sources.tnbudget_speeches import filename_of
from ept.corpus.wayback import Wayback, WaybackUnavailable
from ept.dates import normalize_fy
from ept.runs import Budget
from ept.schema import Discovery, DocType, Lang

log = logging.getLogger(__name__)

_PART = re.compile(
    r"^(?:\d+[-_]|annexures?[_\-]|appendi(?:x|ces)[_\-]|chapter[_\-]|index[_\-]|preface[_\-]|overview[_\-]|"
    r"glossary[_\-]|executive[_\-]summary[_\-])|[_\-](?:annexure|appendices|append|app|ann|chap[_\-]?\d+\w*|index|"
    r"overview|preface|glossary|front[_\-]page|toc|back[_\-]cover)(?:[_\-]\d+)?\.pdf$",
    re.I,
)
_TAMIL_LANGUAGE = re.compile(r"\(tamil\)", re.I)
_YEAR_DIR = re.compile(r"/download_audit_report/((?:19|20)\d{2})/", re.I)


def exclusion(key: str, name: str, min_year: int) -> str | None:
    m = _YEAR_DIR.search(key)
    if not m:
        return "no year folder"
    if int(m.group(1)) < min_year:
        return f"report folder {m.group(1)} before the evidence window"
    if not name.lower().endswith(".pdf"):
        return "not a PDF"
    if re.search(r"puducherry", name, re.I):
        return "Puducherry, not Tamil Nadu"
    if _TAMIL_LANGUAGE.search(name):
        return "Tamil-language version"
    if _PART.search(name):
        return "part of a report (chapter/annexure/index); the full report is kept"
    return None


class CagReports(SourceAdapter):
    name = "cag_reports"

    def catalogue(self, budget: Budget, force: bool = False) -> Iterator[CatalogueItem]:
        try:
            index = self.wayback.prefix_index(self.scfg.get("cdx_prefix"), tuple(self.scfg.get("cdx_filters") or ()))
        except WaybackUnavailable as e:
            log.warning("%s: Wayback unavailable (%s); catalogue not refreshed", self.name, e)
            return
        min_year = self.cfg.settings.evidence_window.start.year
        for key, caps in sorted(index.items()):
            name = filename_of(key)
            latest = Wayback.latest(caps)
            folder = _YEAR_DIR.search(key)
            yield CatalogueItem(
                url=latest.original,
                source=self.name,
                doc_type=DocType.cag_report.value,
                title=name.rsplit(".", 1)[0],
                fiscal_year=normalize_fy(name),
                lang_hint=Lang.en.value,  # "Tamil" in these names is the state; parse detects the language
                identifiers={"report_folder": folder.group(1) if folder else "", "wayback_latest": latest.timestamp},
                discovery=Discovery.wayback_cdx.value,
                excluded_reason=exclusion(key, name, min_year),
            )
