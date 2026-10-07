"""Register fixture files as downloaded documents in a temp project root."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional

from ept import db
from ept.config import get_config
from ept.corpus.catalogue import CatalogueItem, doc_id_for_url
from ept.corpus.fetch import sha256_bytes, write_sidecar
from ept.corpus.wayback import payload_digest
from ept.schema import Document
from conftest import FIXTURES


def register(conn, fixture: str, *, url: str, doc_type: str = "go", lang_hint: Optional[str] = "en",
             listing_date: Optional[str] = None, fiscal_year: Optional[str] = None, wayback: Optional[dict] = None,
             source: str = "tn_gos", discovery: str = "listing") -> Document:
    cfg = get_config()
    src = FIXTURES / fixture
    doc_id = doc_id_for_url(url)
    raw = cfg.path("raw_evidence") / doc_type / f"{doc_id}{Path(fixture).suffix}"
    raw.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(src, raw)
    data = raw.read_bytes()
    item = CatalogueItem(url=url, source=source, doc_type=doc_type, lang_hint=lang_hint,
                         listing_date=listing_date, fiscal_year=fiscal_year, discovery=discovery)
    write_sidecar(raw, {
        "doc_id": doc_id, "source_url": url, "fetched_from": "live", "sha256": sha256_bytes(data),
        "payload_digest": payload_digest(data), "listing": item.model_dump(mode="json"), "aliases": [],
        "wayback": wayback if wayback is not None else {"checked": True, "kept_first_capture": None},
    })
    doc = Document(doc_id=doc_id, source_url=url, local_path=raw.relative_to(cfg.root).as_posix(),
                   doc_type=doc_type, lang=lang_hint or "en", discovery=discovery, sha256=sha256_bytes(data),
                   fiscal_year=fiscal_year, doc_date=listing_date,
                   date_precision="day" if listing_date else None,
                   date_source="listing" if listing_date else "none")
    db.upsert(conn, doc)
    return doc
