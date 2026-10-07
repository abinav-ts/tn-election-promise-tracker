"""Language: filename tags first, then detection on the parsed text (spec 01 §4.3, §4.4)."""

from __future__ import annotations

import re
from typing import Optional
from urllib.parse import unquote, urlsplit

from ept.schema import Lang

_TAMIL_RE = re.compile(r"[஀-௿]")
_LETTER_RE = re.compile(r"[^\W\d_]", re.UNICODE)
# Legacy Tamil fonts (e.g. TAM/TAB/Bamini) map Tamil glyphs onto Latin-1 symbols and accented letters.
_LEGACY_RE = re.compile(r"[¡-ÿŒœŠšŸŽžƒˆ˜–-›]")

_TAGS = [
    (re.compile(r"(?:^|[_\-./ ])e(?:[_\-./ ]|$)", re.I), Lang.en),
    (re.compile(r"(?:^|[_\-./ ])t(?:[_\-./ ]|$)", re.I), Lang.ta),
    (re.compile(r"(?:^|[_\-./ (])eng(?:lish)?(?:[_\-./ )]|$)", re.I), Lang.en),
    (re.compile(r"(?:^|[_\-./ (])tam(?:il)?(?:[_\-./ )]|$)", re.I), Lang.ta),
]


def filename_lang(url_or_name: str) -> Optional[Lang]:
    """`_e_`/`_t_`, `ENG`/`TAM`, `(Eng)`/`(Tam)`, `English`/`Tamil` in the file name. None if no tag or both."""
    name = unquote(urlsplit(url_or_name).path.rsplit("/", 1)[-1] or url_or_name)
    stem = name.rsplit(".", 1)[0]
    found = {lang for rx, lang in _TAGS if rx.search(stem)}
    return found.pop() if len(found) == 1 else None


def tamil_ratio(text: str) -> float:
    """Share of script characters in the Tamil Unicode block (vowel signs count as Tamil)."""
    tamil = len(_TAMIL_RE.findall(text))
    other = sum(1 for ch in _LETTER_RE.findall(text) if not _TAMIL_RE.match(ch))
    return tamil / (tamil + other) if tamil + other else 0.0


def legacy_garbage_ratio(text: str) -> float:
    """Share of non-space characters that look like legacy-font Tamil (Latin-1 symbols/accents)."""
    chars = [c for c in text if not c.isspace()]
    if not chars:
        return 0.0
    return sum(1 for c in chars if _LEGACY_RE.match(c)) / len(chars)


def detect(text: str, tamil_threshold: float, legacy_threshold: float, hint: Optional[Lang] = None) -> Lang:
    """Tamil if the Tamil-script ratio passes the threshold, or legacy-font garbage in a Tamil-tagged file."""
    if tamil_ratio(text) >= tamil_threshold:
        return Lang.ta
    if hint == Lang.ta and legacy_garbage_ratio(text) >= legacy_threshold:
        return Lang.ta
    return Lang.en
