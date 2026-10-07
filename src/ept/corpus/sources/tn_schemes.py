"""S6: scheme pages (spec 01 §2.3).

Current site (live, today's snapshot only): schemes.php -> scheme_list.php?dep_id=b64(n)
-> scheme_details.php?id=b64(n). Older versions: the previous portal's
`www.tn.gov.in/scheme/data_view/N` pages, catalogued from Wayback CDX.
Scheme pages are dated only by a Wayback capture (an upper bound); the
"Introduced On" field is a scheme fact, not the page's publication date.
"""

from __future__ import annotations

import logging
from typing import Iterator
from urllib.parse import parse_qs, urljoin, urlsplit

from bs4 import BeautifulSoup

from ept.corpus.catalogue import CatalogueItem
from ept.corpus.sources.base import SourceAdapter, b64, unb64
from ept.corpus.wayback import Wayback, WaybackUnavailable
from ept.net import FetchError
from ept.runs import Budget
from ept.schema import Discovery, DocType, Lang

log = logging.getLogger(__name__)


def parse_departments(html: str) -> dict[str, str]:
    soup = BeautifulSoup(html, "lxml")
    out = {}
    for a in soup.find_all("a", href=True):
        if a["href"].startswith("scheme_list.php"):
            qs = parse_qs(urlsplit(a["href"]).query)
            if "dep_id" in qs:
                out[unb64(qs["dep_id"][0])] = a.get_text(" ", strip=True)
    return out


def parse_scheme_list(html: str, page_url: str) -> list[tuple[str, str]]:
    soup = BeautifulSoup(html, "lxml")
    root = soup.select_one("#content") or soup
    seen: dict[str, str] = {}
    for a in root.find_all("a", href=True):
        if "scheme_details.php" in a["href"]:
            seen.setdefault(urljoin(page_url, a["href"]), " ".join(a.get_text(" ", strip=True).split()))
    return list(seen.items())


class TnSchemes(SourceAdapter):
    name = "tn_schemes"

    def catalogue(self, budget: Budget, force: bool = False) -> Iterator[CatalogueItem]:
        yield from self._current(budget, force)
        yield from self._archived()

    def _current(self, budget: Budget, force: bool) -> Iterator[CatalogueItem]:
        base = self.scfg.get("base_url")
        try:
            deps = parse_departments(self.http.get_listing(urljoin(base, self.scfg.get("list_url")),
                                                           use_cache=not force))
        except FetchError as e:
            log.warning("%s: scheme department list unavailable: %s", self.name, e)
            return
        for dep_id, dep_name in deps.items():
            if budget.expired():
                return
            page = urljoin(base, f"scheme_list.php?{self.scfg.get('dept_param')}={b64(dep_id)}")
            try:
                html = self.http.get_listing(page, use_cache=not force)
            except FetchError as e:
                log.warning("%s: listing failed %s: %s", self.name, page, e)
                continue
            for url, title in parse_scheme_list(html, page):
                yield CatalogueItem(
                    url=url, source=self.name, doc_type=DocType.scheme_page.value, subtype="current",
                    department=self.department(dep_id, dep_name), dep_id=dep_id, title=title or None,
                    lang_hint=Lang.en.value, listing_url=page,
                )

    def _archived(self) -> Iterator[CatalogueItem]:
        try:
            index = self.wayback.prefix_index(self.scfg.get("archived_prefix"))
        except WaybackUnavailable as e:
            log.warning("%s: Wayback unavailable (%s); archived scheme pages not refreshed", self.name, e)
            return
        for key, caps in sorted(index.items()):
            tail = key.rsplit("/", 1)[-1]
            if not tail.isdigit():
                continue  # listing/index pages, not a scheme
            latest = Wayback.latest(caps)
            yield CatalogueItem(
                url=latest.original, source=self.name, doc_type=DocType.scheme_page.value, subtype="archived",
                title=f"Scheme page {tail} (previous portal)", lang_hint=Lang.en.value,
                identifiers={"scheme_node": tail, "wayback_latest": latest.timestamp},
                discovery=Discovery.wayback_cdx.value,
            )

