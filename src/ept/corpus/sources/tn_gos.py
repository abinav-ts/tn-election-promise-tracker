"""S2: Government Orders on www.tn.gov.in (spec 01 §2.3).

Listing: go.php?dep_id=b64(n)&year=b64(YYYY), one page per department × calendar year.
Each GO card gives the listing date (day precision), number and series, subject, and the PDF.
"""

from __future__ import annotations

import datetime as dt
import logging
import re
from typing import Iterator, Optional
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from ept.corpus.catalogue import CatalogueItem
from ept.corpus.lang import filename_lang
from ept.corpus.sources.base import SourceAdapter, b64
from ept.dates import fiscal_year_of
from ept.net import FetchError
from ept.runs import Budget
from ept.schema import DocType

log = logging.getLogger(__name__)

_GO_NO = re.compile(r"G\.?\s*O\.?\s*\(?\s*(?P<series>\d?[A-Za-z]{1,3})\s*\)?\s*\.?\s*No\.?\s*(?P<no>\d+)", re.I)
_DATE = re.compile(r"(\d{1,2})[-./](\d{1,2})[-./](\d{4})")


def parse_go_number(text: str) -> tuple[Optional[str], Optional[str]]:
    """'G.O (D) No.1347' -> ('D', '1347'); 'G.O.(Ms) No. 45' -> ('Ms', '45')."""
    m = _GO_NO.search(text)
    if not m:
        return None, None
    series = m.group("series")
    series = {"ms": "Ms", "d": "D", "rt": "Rt"}.get(series.lower(), series)
    return series, str(int(m.group("no")))


def parse_listing(html: str, page_url: str) -> list[dict]:
    """GO cards on one department × year page."""
    soup = BeautifulSoup(html, "lxml")
    out = []
    for card in soup.select(".row.go-list"):
        link = card.select_one("h4.event-name a[href]") or card.select_one("a[href$='.pdf']")
        if link is None:
            continue
        date_el = card.select_one(".Calendar") or card.select_one(".date-box")  # lxml splits <p class="Day"><center>
        m = _DATE.search(date_el.get_text(" ", strip=True)) if date_el else None
        listing_date = None
        if m:
            try:
                listing_date = dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
            except ValueError:
                listing_date = None
        detail = card.select_one(".event-detail")
        number_text = link.get_text(" ", strip=True)
        series, number = parse_go_number(number_text)
        out.append({
            "url": urljoin(page_url, link["href"].strip()),
            "number_text": number_text,
            "series": series,
            "number": number,
            "subject": " ".join(detail.get_text(" ", strip=True).split()) if detail else "",
            "listing_date": listing_date,
        })
    return out


class TnGos(SourceAdapter):
    name = "tn_gos"

    def catalogue(self, budget: Budget, force: bool = False) -> Iterator[CatalogueItem]:
        window = self.cfg.settings.evidence_window
        years = range(window.start.year, window.end_or_today().year + 1)
        base = self.scfg.get("base_url")
        for dep_id in self.cfg.sources.departments:
            for year in years:
                if budget.expired():
                    return
                page = urljoin(base, self.scfg.get("dept_page").format(dep_id_b64=b64(dep_id), year_b64=b64(str(year))))
                try:
                    html = self.http.get_listing(page, use_cache=not force)
                except FetchError as e:
                    log.warning("%s: listing failed %s: %s", self.name, page, e)
                    continue
                heading = BeautifulSoup(html, "lxml").select_one("h3")
                for go in parse_listing(html, page):
                    filename = urlsplit(go["url"]).path.rsplit("/", 1)[-1]
                    d = go["listing_date"]
                    yield CatalogueItem(
                        url=go["url"],
                        source=self.name,
                        doc_type=DocType.go.value,
                        department=self.department(dep_id, heading.get_text(" ", strip=True) if heading else None),
                        dep_id=dep_id,
                        title=f"{go['number_text']}: {go['subject']}"[:500],
                        listing_date=d,
                        fiscal_year=fiscal_year_of(d) if d else None,
                        lang_hint=filename_lang(filename),
                        identifiers={k: v for k, v in {
                            "go_series": go["series"], "go_number": go["number"],
                            "go_year": str(d.year) if d else str(year), "listing_year": str(year),
                        }.items() if v},
                        listing_url=page,
                    )
