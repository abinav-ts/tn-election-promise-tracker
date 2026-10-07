"""The catalogue: everything discovered per source, downloaded or not.

`data/interim/catalogue/{source}.jsonl`, one item per canonical URL. The file is
rewritten atomically on save, so an interrupted run never leaves it half-written.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from pathlib import Path
from typing import Iterable, Iterator, Optional
from urllib.parse import urlsplit, urlunsplit

from pydantic import BaseModel, ConfigDict

from ept.config import Config, get_config
from ept.schema import Discovery, DocType, Lang

# Item states
NEW = "new"
DOWNLOADED = "downloaded"
DUPLICATE = "duplicate"
FETCH_FAILED = "fetch_failed"
EXCLUDED = "excluded"


def canonical_url(url: str) -> str:
    """Lower-case scheme and host, drop default ports and fragments; path and query kept as is."""
    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower()
    host = (parts.hostname or "").lower()
    port = parts.port
    if port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
        host = f"{host}:{port}"
    return urlunsplit((scheme, host, parts.path or "/", parts.query, ""))


def doc_id_for_url(url: str) -> str:
    """§7: first 16 hex chars of sha1(canonical source_url)."""
    return hashlib.sha1(canonical_url(url).encode("utf-8")).hexdigest()[:16]


def doc_id_for_manual(relative_path: str) -> str:
    return hashlib.sha1(("manual/" + relative_path.replace(os.sep, "/")).encode("utf-8")).hexdigest()[:16]


class CatalogueItem(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    url: str
    source: str
    doc_type: Optional[DocType] = None
    subtype: Optional[str] = None
    department: Optional[str] = None
    dep_id: Optional[str] = None
    title: Optional[str] = None
    listing_date: Optional[dt.date] = None
    fiscal_year: Optional[str] = None
    lang_hint: Optional[Lang] = None
    identifiers: dict[str, str] = {}
    listing_url: Optional[str] = None
    discovery: Discovery = Discovery.listing
    # state
    status: str = NEW
    excluded_reason: Optional[str] = None
    doc_id: Optional[str] = None
    fetch_error: Optional[str] = None
    first_seen: Optional[dt.date] = None

    def model_post_init(self, __context) -> None:
        self.url = canonical_url(self.url)
        if self.first_seen is None:
            self.first_seen = dt.date.today()
        if self.excluded_reason and self.status == NEW:
            self.status = EXCLUDED


class Catalogue:
    def __init__(self, source: str, cfg: Optional[Config] = None):
        self.cfg = cfg or get_config()
        self.source = source
        self.path: Path = self.cfg.path("catalogue_dir") / f"{source}.jsonl"
        self._items: dict[str, CatalogueItem] = {}
        self._dirty = False
        if self.path.exists():
            with self.path.open(encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        item = CatalogueItem.model_validate_json(line)
                        self._items[item.url] = item

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self) -> Iterator[CatalogueItem]:
        return iter(self._items.values())

    def get(self, url: str) -> Optional[CatalogueItem]:
        return self._items.get(canonical_url(url))

    def add(self, items: Iterable[CatalogueItem]) -> int:
        """Append items not yet catalogued; returns the number added.

        A known item that was never fetched (new/excluded) takes the fresh listing fields, so a
        changed classification rule applies on the next run. Fetched items are left untouched."""
        n = 0
        for item in items:
            old = self._items.get(item.url)
            if old is None:
                self._items[item.url] = item
                n += 1
                self._dirty = True
            elif old.status in (NEW, EXCLUDED):
                fresh = item.model_copy(update={"first_seen": old.first_seen,
                                                "status": EXCLUDED if item.excluded_reason else NEW})
                if fresh != old:
                    self._items[item.url] = fresh
                    self._dirty = True
        return n

    def update(self, url: str, **fields) -> CatalogueItem:
        item = self._items[canonical_url(url)]
        updated = item.model_copy(update=fields)
        self._items[item.url] = updated
        self._dirty = True
        return updated

    def save(self) -> None:
        if not self._dirty and self.path.exists():
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".jsonl.tmp")
        with tmp.open("w", encoding="utf-8") as f:
            for item in self._items.values():
                f.write(json.dumps(item.model_dump(mode="json"), ensure_ascii=False) + "\n")
        os.replace(tmp, self.path)
        self._dirty = False


def load_all(cfg: Optional[Config] = None) -> dict[str, Catalogue]:
    cfg = cfg or get_config()
    folder = cfg.path("catalogue_dir")
    return {p.stem: Catalogue(p.stem, cfg) for p in sorted(folder.glob("*.jsonl"))}
