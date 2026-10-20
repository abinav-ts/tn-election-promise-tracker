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


TOPICS = {
    "bus": "free bus travel for women in town buses operated by the transport corporation fare exemption",
    "school": "breakfast scheme for school children in government primary schools nutritious meal",
    "loan": "crop loan waiver for small and marginal farmers in cooperative banks agricultural credit",
    "road": "village road works and rural roads upgraded under the rural development department",
}
FILLER = "the department reviewed progress and issued instructions to district officers for implementation"


def _text(topic: str, n: int) -> str:
    return f"{TOPICS[topic]} {FILLER} item {n}"


def make_corpus(conn) -> dict[str, list[str]]:
    """Chunks in every term window and landmark of the configured terms, a few GOs, policy notes, one
    undated CAG report, and one document after the last landmark (the corpus snapshot)."""
    docs = [
        # (doc_id, doc_type, date, precision, fy, title, topics)
        ("a000000000000001", "go", "2016-06-10", "day", None, "G.O. on bus fare exemption", ["bus", "bus"]),
        ("a000000000000002", "policy_note", None, None, "2016-17", "Policy Note Transport 2016-17", ["bus", "loan"]),
        ("a000000000000003", "go", "2017-08-01", "day", None, "G.O. crop loan waiver", ["loan"]),
        ("a000000000000004", "scheme_page", "2019-01-01", "year", None, "Rural roads scheme", ["road", "road", "road"]),
        ("a000000000000005", "go", "2020-11-01", "day", None, "G.O. school meal", ["school"]),
        ("d000000000000001", "go", "2021-05-20", "day", None, "G.O. free bus travel for women", ["bus"]),
        ("d000000000000008", "go", "2021-07-01", "day", None, "G.O. school meal timings", ["school", "loan"]),
        ("d000000000000009", "scheme_page", "2021-09-01", "month", None, "Rural roads page", ["road"]),
        ("d000000000000002", "policy_note", "2022-08-01", "day", "2021-22", "Policy Note Transport 2021-22",
         ["bus", "bus", "school"]),
        ("d000000000000003", "go", "2022-09-15", "day", None, "G.O. breakfast scheme", ["school", "school"]),
        ("d000000000000004", "budget_speech", "2023-03-20", "day", "2023-24", "Budget Speech 2023-24",
         ["school", "bus", "loan", "road"]),
        ("d000000000000005", "scheme_page", "2024-01-01", "month", None, "Breakfast scheme page", ["school"]),
        ("d000000000000006", "go", "2025-06-01", "day", None, "G.O. village roads", ["road"]),
        ("d000000000000007", "cag_report", None, None, "2022-23", "CAG report", ["bus", "school"]),
        ("t000000000000001", "go", "2026-06-01", "day", None, "G.O. bus fare", ["bus"]),
        ("t000000000000002", "go", "2026-10-10", "day", None, "G.O. school", ["school"]),
    ]
    out = {}
    for n, (did, dtp, date, prec, fy, title, topics) in enumerate(docs):
        out[did] = add_doc(conn, did, dtp, date, prec, fy, title, tuple(_text(t, n * 10 + i)
                                                                         for i, t in enumerate(topics)))
    add_promise(conn, "AIADMK-2016-0001", "Waive crop loans of small farmers.",
                [["crop loan waiver farmers", "cooperative bank loans"]])
    add_promise(conn, "AIADMK-2016-0002", "Improve rural roads.", [["village road works", "rural roads"],
                                                                   ["road upgrade", "rural development roads"]],
                indicator_texts=["Village roads upgraded.", "Rural road works sanctioned."])
    add_promise(conn, "DMK-2021-0001", "Provide free bus travel for women.", [["free bus travel women", "bus fare"]],
                headline=True)
    add_promise(conn, "DMK-2021-0002", "Start a breakfast scheme in schools.", [["breakfast scheme school",
                                                                               "school children meal"]])
    add_promise(conn, "DMK-2021-0003", "Upgrade village roads.", [["village roads", "rural roads upgrade"]])
    add_promise(conn, "TVK-2026-0001", "Give free bus travel to students.", [["free bus travel", "bus pass"]])
    return out


def build_mock_index(conn) -> dict:
    from ept.config import get_config
    from ept.retrieve.dense import build_index

    return build_index(conn, get_config())
