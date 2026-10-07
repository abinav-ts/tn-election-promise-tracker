"""Paragraph-aware, word-count chunking (spec 01 §4.4).

Chunks hold `min_words`..`max_words` words (target `target_words`); only a
document's last chunk may be shorter. Splits happen at paragraph ends when
possible, else at sentence ends, else between words; never inside a word.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Optional

from ept.schema import Chunk

_ABBREVS = ["No", "Nos", "Rs", "Dr", "Mr", "Mrs", "Ms", "Thiru", "Tmt", "Selvi", "St", "vs", "viz", "Hon", "Govt",
            "Dept", "etc", "Ltd", "Sl", "Ms.No", "i.e", "e.g"]
_NOT_ABBREV = "".join(rf"(?<!\b{re.escape(a)}\.)" for a in _ABBREVS) + r"(?<!\b[A-Z]\.)"
_SENT_RE = re.compile(r"(?<=[.!?])" + _NOT_ABBREV + r"\s+(?=[\"“'(\[]?[A-Z0-9])")


@dataclass
class Paragraph:
    text: str
    page: int


@dataclass
class _Piece:
    words: list[str]
    page: int
    para_end: bool


def split_sentences(text: str) -> list[str]:
    return [s for s in _SENT_RE.split(text.strip()) if s.strip()]


def _pieces(paragraphs: Iterable[Paragraph], max_words: int) -> list[_Piece]:
    out: list[_Piece] = []
    for para in paragraphs:
        sentences = [s.split() for s in split_sentences(para.text)]
        sentences = [s for s in sentences if s]
        for i, words in enumerate(sentences):
            last = i == len(sentences) - 1
            # a sentence longer than max_words is cut between words
            for start in range(0, len(words), max_words):
                part = words[start:start + max_words]
                out.append(_Piece(part, para.page, last and start + max_words >= len(words)))
    return out


@dataclass
class _Draft:
    parts: list[tuple[list[str], int, bool]]

    @property
    def n(self) -> int:
        return sum(len(w) for w, _, _ in self.parts)

    def text(self) -> str:
        out: list[str] = []
        for words, _, para_end in self.parts:
            out.append(" ".join(words))
            out.append("\n\n" if para_end else " ")
        return "".join(out).strip()

    def pages(self) -> tuple[int, int]:
        pages = [p for _, p, _ in self.parts]
        return min(pages), max(pages)


def chunk_paragraphs(paragraphs: Iterable[Paragraph], target: int, min_words: int,
                     max_words: int) -> list[tuple[str, int, int, int]]:
    """[(text, page_start, page_end, n_words)]"""
    drafts: list[_Draft] = []
    cur = _Draft([])
    queue = _pieces(paragraphs, max_words)
    i = 0
    while i < len(queue):
        piece = queue[i]
        n = len(piece.words)
        if cur.n + n <= max_words:
            cur.parts.append((piece.words, piece.page, piece.para_end))
            i += 1
            if cur.n >= target and (piece.para_end or cur.n >= max_words):
                drafts.append(cur)
                cur = _Draft([])
            continue
        if cur.n >= min_words:
            drafts.append(cur)
            cur = _Draft([])
            continue
        # cur too short and the next piece would overflow: take words up to the target
        k = max(target - cur.n, 1)
        cur.parts.append((piece.words[:k], piece.page, False))
        drafts.append(cur)
        cur = _Draft([])
        queue[i] = _Piece(piece.words[k:], piece.page, piece.para_end)
    if cur.parts:
        if drafts and cur.n < min_words and drafts[-1].n + cur.n <= max_words:
            drafts[-1].parts.extend(cur.parts)
        else:
            drafts.append(cur)
    out = []
    for d in drafts:
        start, end = d.pages()
        text = d.text()
        out.append((text, start, end, len(text.split())))
    return out


def make_chunks(doc_id: str, paragraphs: Iterable[Paragraph], doc_date, target: int, min_words: int,
                max_words: int) -> list[Chunk]:
    return [
        Chunk(chunk_id=f"{doc_id}-{seq:04d}", doc_id=doc_id, seq=seq, text=text, page_start=ps, page_end=pe,
              doc_date=doc_date, n_words=n)
        for seq, (text, ps, pe, n) in enumerate(chunk_paragraphs(paragraphs, target, min_words, max_words))
    ]


_HYPHEN_RE = re.compile(r"(\w)-\n(?=[a-z])")


def clean_block(text: str) -> Optional[str]:
    """Join a PDF text block's lines into one paragraph."""
    text = _HYPHEN_RE.sub(r"\1", text)
    text = " ".join(text.split())
    return text or None
