"""BM25 tokeniser (spec 04 §4.4). The same function tokenises chunks and queries."""

from __future__ import annotations

import hashlib
import re
import unicodedata

from ept.retrieve.stopwords import STOPWORDS

VERSION = "tok-v1"
_TOKEN = re.compile(r"[a-z0-9]+")


def fold(token: str) -> str:
    """Light plural folding: -ies -> -y (length > 4); -es dropped after s/x/z/ch/sh; a final -s dropped
    (length > 3, not -ss/-us/-is)."""
    if token.endswith("ies") and len(token) > 4:
        return token[:-3] + "y"
    if token.endswith("es") and token[:-2].endswith(("s", "x", "z", "ch", "sh")):
        return token[:-2]
    if token.endswith("s") and len(token) > 3 and not token.endswith(("ss", "us", "is")):
        return token[:-1]
    return token


def tokenize(text: str) -> list[str]:
    """NFKC, lower case, [a-z0-9]+ tokens; 1-character tokens and stopwords dropped; plurals folded."""
    raw = _TOKEN.findall(unicodedata.normalize("NFKC", text or "").lower())
    return [fold(t) for t in raw if len(t) > 1 and t not in STOPWORDS]


def fingerprint() -> str:
    """Tokeniser version + stopword list, for the run fingerprint (spec 04 §4.8)."""
    words = "\n".join(sorted(STOPWORDS))
    return f"{VERSION}:{hashlib.sha256(words.encode()).hexdigest()[:16]}"
