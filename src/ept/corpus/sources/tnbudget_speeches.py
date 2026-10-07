"""S3: budget speeches from tnbudget.tn.gov.in, via Wayback CDX only (spec 01 §2.3).

The live site is unreachable, so the catalogue is built from the Wayback prefix index.
Since D-025 the S1 listing supplies most speeches; S3 keeps only speeches whose
(fiscal year, subtype) S1 does not have, and excludes the rest with a reason.
"""

from __future__ import annotations

import logging
import re
from typing import Iterator, Optional
from urllib.parse import unquote, urlsplit

from ept.corpus.catalogue import Catalogue, CatalogueItem
from ept.corpus.lang import filename_lang
from ept.corpus.sources.base import SourceAdapter
from ept.corpus.wayback import Wayback, WaybackUnavailable
from ept.dates import normalize_fy
from ept.runs import Budget
from ept.schema import Discovery, DocType

log = logging.getLogger(__name__)

_SPEECH = re.compile(r"budget[\s_]*speech|(?:^|[_\s])BS[_\s]", re.I)
_INTERIM = re.compile(r"interim|(?:^|[_\s])VOA(?:[_\s]|$)", re.I)
_REVISED = re.compile(r"revised|(?:^|[_\s])RBE(?:[_\s]|$)", re.I)


def filename_of(url: str) -> str:
    return unquote(urlsplit(url if "://" in url else "http://" + url).path.rsplit("/", 1)[-1])


def speech_subtype(name: str) -> Optional[str]:
    parts = [p for p, rx in (("interim", _INTERIM), ("revised", _REVISED)) if rx.search(name)]
    return "_".join(parts) or None


def covered_by(catalogue: Catalogue) -> set[tuple[str, Optional[str]]]:
    """(fiscal_year, subtype) of English budget speeches another source already lists."""
    return {(i.fiscal_year, i.subtype) for i in catalogue
            if i.doc_type == DocType.budget_speech.value and i.status != "excluded" and (i.lang_hint or "en") == "en"}


class TnBudgetSpeeches(SourceAdapter):
    name = "tnbudget_speeches"

    def catalogue(self, budget: Budget, force: bool = False) -> Iterator[CatalogueItem]:
        prefix = self.scfg.get("cdx_prefix")
        try:
            index = self.wayback.prefix_index(prefix)
        except WaybackUnavailable as e:
            log.warning("%s: Wayback unavailable (%s); catalogue not refreshed", self.name, e)
            return
        covered_source = self.scfg.get("skip_if_covered_by")
        covered = covered_by(Catalogue(covered_source, self.cfg)) if covered_source else set()
        for key, caps in sorted(index.items()):
            name = filename_of(key)
            if not name.lower().endswith(".pdf") or not _SPEECH.search(name):
                continue
            latest = Wayback.latest(caps)
            fy = normalize_fy(name)
            subtype = speech_subtype(name)
            excluded = None
            if re.search(r"highlight", name, re.I):
                excluded = "budget highlights, not the speech"
            elif fy is None:
                excluded = "no fiscal year in file name"
            elif (fy, subtype) in covered or (subtype is None and fy in {c[0] for c in covered}):
                # an untagged speech for a year the listing has is the same speech under another name
                excluded = f"covered by {covered_source} (D-025)"
            yield CatalogueItem(
                url=latest.original,
                source=self.name,
                doc_type=DocType.budget_speech.value,
                subtype=subtype,
                department=self.cfg.sources.departments.get(str(self.scfg.get("dep_id"))),
                dep_id=str(self.scfg.get("dep_id")),
                title=name.rsplit(".", 1)[0],
                fiscal_year=fy,
                lang_hint=filename_lang(name),
                identifiers={"wayback_latest": latest.timestamp, "wayback_captures": str(len(caps))},
                discovery=Discovery.wayback_cdx.value,
                excluded_reason=excluded,
            )
