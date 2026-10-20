"""Stage 04 fixture DB: documents, chunks, promises and indicators written straight into SQLite."""

from __future__ import annotations

from typing import Optional

from ept import db
from ept.schema import Chunk, Document, Indicator, Promise


def add_doc(conn, doc_id: str, doc_type: str = "go", doc_date: Optional[str] = "2021-06-01",
            precision: Optional[str] = "day", fy: Optional[str] = None, title: str = "A document",
            texts: tuple[str, ...] = ("some text",)) -> list[str]:
    db.upsert(conn, Document(doc_id=doc_id, doc_type=doc_type, lang="en", discovery="listing", title=title,
                             doc_date=doc_date, date_precision=precision if doc_date else None,
                             date_source="listing" if doc_date else "none", fiscal_year=fy,
                             local_path=f"data/raw/evidence/{doc_type}/{doc_id}.pdf"))
    ids = []
    for seq, text in enumerate(texts):
        cid = f"{doc_id}-{seq:04d}"
        db.upsert(conn, Chunk(chunk_id=cid, doc_id=doc_id, seq=seq, text=text, doc_date=doc_date,
                              n_words=len(text.split())))
        ids.append(cid)
    return ids


def add_promise(conn, promise_id: str, text: str, queries: list[list[str]] | None = None,
                headline: bool = False, indicator_texts: list[str] | None = None) -> list[str]:
    term = promise_id.rsplit("-", 1)[0]
    db.upsert(conn, Promise(promise_id=promise_id, term_id=term, text=text, source_text=text, source_lang="en",
                            page=1, parent_group=f"{term}-U{promise_id[-4:]}", headline=headline,
                            specificity="specific" if not indicator_texts else "vague"))
    texts = indicator_texts or [text]
    queries = queries or [[text]] * len(texts)
    ids = []
    for n, (t, q) in enumerate(zip(texts, queries), start=1):
        iid = f"{promise_id}-I{n}"
        db.upsert(conn, Indicator(indicator_id=iid, promise_id=promise_id, text=t, is_self=not indicator_texts,
                                  search_queries=q))
        ids.append(iid)
    return ids
