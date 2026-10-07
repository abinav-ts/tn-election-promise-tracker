"""S1: the www.tn.gov.in department documents listing (spec 01 §2.3).

Listing: document.php?dep_id=b64(n)&year=b64("YYYY-YYYY")&cate_name=YWxs, one page per
department × fiscal year. Kept: policy notes, performance budgets (D-022), and, from the
same listing, budget speeches, Governor's addresses and state sector policies (D-025).
Citizen Charters and everything else are catalogued but excluded.
"""

from __future__ import annotations

import logging
import re
from typing import Iterator, Optional
from urllib.parse import parse_qs, urljoin, urlsplit

from bs4 import BeautifulSoup

from ept.corpus.catalogue import CatalogueItem
from ept.corpus.lang import filename_lang
from ept.corpus.sources.base import SourceAdapter, b64, unb64
from ept.dates import fiscal_years_between, normalize_fy
from ept.net import FetchError
from ept.runs import Budget
from ept.schema import DocType

log = logging.getLogger(__name__)

_PN = re.compile(r"policy\s*note|(?:^|_)pn(?:_|$)", re.I)
_PB = re.compile(r"performance\s*budget|(?:^|_)pb(?:_|$)", re.I)
_CC = re.compile(r"citizen'?s?\s*charter|(?:^|_)cc(?:_|$)", re.I)
_BS = re.compile(r"budget\s*speech", re.I)
_GA = re.compile(r"governor'?s?\s+address|address\s+delivered\s+by\s+the\s+hon'?ble\s+governor", re.I)
_POLICY = re.compile(r"\bpolicy\b", re.I)
_DRAFT = re.compile(r"\bdraft\b", re.I)
EXCLUDED_OTHER = "not a listed document type (D-022, D-025)"


def _speech_subtype(title: str) -> Optional[str]:
    parts = [p for p in ("agriculture", "interim", "revised") if re.search(p, title, re.I)]
    return "_".join(parts) or None


def classify(title: str, filename: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """(doc_type, subtype, excluded_reason) from the listing title and file name."""
    stem = filename.rsplit(".", 1)[0]
    if _CC.search(title) or _CC.search(stem):
        return None, "citizen_charter", "citizen charter (D-022)"
    if _PN.search(title) or _PN.search(stem):
        return DocType.policy_note.value, None, None
    if _PB.search(title) or _PB.search(stem):
        return DocType.other.value, "performance_budget", None
    if _BS.search(title):
        return DocType.budget_speech.value, _speech_subtype(title), None
    if _GA.search(title):
        return DocType.governor_address.value, None, None
    if _POLICY.search(title) or _POLICY.search(stem):
        return DocType.other.value, "policy_draft" if _DRAFT.search(title + " " + stem) else "policy", None
    return None, None, EXCLUDED_OTHER


def parse_dept_list(html: str) -> dict[str, str]:
    """dep_id -> department name from document_dept_list.php."""
    soup = BeautifulSoup(html, "lxml")
    out: dict[str, str] = {}
    for a in soup.find_all("a", href=True):
        if "document.php" not in a["href"]:
            continue
        qs = parse_qs(urlsplit(a["href"]).query)
        if "dep_id" in qs:
            out[unb64(qs["dep_id"][0])] = a.get_text(" ", strip=True)
    return out


def parse_listing(html: str, page_url: str) -> tuple[Optional[str], list[tuple[str, str]]]:
    """(department heading, [(absolute url, title)]) from one department × FY page."""
    soup = BeautifulSoup(html, "lxml")
    content = soup.select_one("#content") or soup
    heading = content.find("h4")
    dept_name = heading.get_text(" ", strip=True) if heading else None
    links: dict[str, str] = {}
    for a in content.find_all("a", href=True):
        href = a["href"].strip()
        if not href.lower().endswith(".pdf") and "docfiles" not in href:
            continue
        url = urljoin(page_url, href)
        title = a.get_text(" ", strip=True)
        if title or url not in links:
            links[url] = title or links.get(url, "")
    return dept_name, list(links.items())


class TnPolicyNotes(SourceAdapter):
    name = "tn_policy_notes"

    def _dep_ids(self, force: bool) -> dict[str, str]:
        deps = dict(self.cfg.sources.departments)
        try:
            listed = parse_dept_list(self.http.get_listing(self.scfg.get("dept_list_url"), use_cache=not force))
        except FetchError as e:
            log.warning("%s: department list unavailable (%s); using sources.yaml map", self.name, e)
            listed = {}
        for dep_id, name in listed.items():
            if dep_id not in deps:
                log.warning("%s: dep_id %s (%r) not in sources.yaml departments", self.name, dep_id, name)
                deps[dep_id] = name
        return deps

    def catalogue(self, budget: Budget, force: bool = False) -> Iterator[CatalogueItem]:
        window = self.cfg.settings.evidence_window
        fys = fiscal_years_between(window.start, window.end_or_today())
        for dep_id, dep_name in self._dep_ids(force).items():
            for fy in fys:
                if budget.expired():
                    return
                long_fy = f"{fy[:4]}-{int(fy[:4]) + 1}"
                page = urljoin(self.scfg.get("base_url"),
                               self.scfg.get("dept_page").format(dep_id_b64=b64(dep_id), fy_b64=b64(long_fy)))
                try:
                    html = self.http.get_listing(page, use_cache=not force)
                except FetchError as e:
                    log.warning("%s: listing failed %s: %s", self.name, page, e)
                    continue
                heading, links = parse_listing(html, page)
                for url, title in links:
                    filename = urlsplit(url).path.rsplit("/", 1)[-1]
                    doc_type, subtype, excluded = classify(title, filename)
                    yield CatalogueItem(
                        url=url,
                        source=self.name,
                        doc_type=doc_type,
                        subtype=subtype,
                        department=self.department(dep_id, heading or dep_name),
                        dep_id=dep_id,
                        title=title or None,
                        fiscal_year=normalize_fy(filename) or normalize_fy(title) or fy,
                        lang_hint=filename_lang(filename),
                        identifiers={"listing_fy": fy},
                        listing_url=page,
                        excluded_reason=excluded,
                    )
