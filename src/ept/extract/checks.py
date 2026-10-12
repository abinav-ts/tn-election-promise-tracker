"""Promise checks V1–V4 (spec 02 §4.5, leakage rules 1, 3, 6).

- V1 verbatim: `source_text` is a substring of the unit text after NFC and whitespace normalisation.
- V2 numbers: every digit group in `text` (commas removed) occurs in `source_text`; a digit group in
  `source_text` missing from `text` is a warning.
- V3 names: a capitalised token in `text` that isn't sentence-initial, isn't a common word and doesn't
  occur in the unit text goes to `names_to_check`: a failure for English source, a flag for Tamil.
- V4 shape: `text` non-empty and at most `max_text_words` words (every unit returning >= 1 piece is
  checked where the call's output is read).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

_ZERO_WIDTH = dict.fromkeys(map(ord, "​‌‍﻿"))
_DIGITS_RE = re.compile(r"[0-9]+(?:\.[0-9]+)?")
_THOUSANDS_RE = re.compile(r"(?<=[0-9]),(?=[0-9])")
_CAP_RE = re.compile(r"\b[A-Z][A-Za-z'\-]*")


def norm(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", text).translate(_ZERO_WIDTH).split())


def digit_groups(text: str) -> list[str]:
    return _DIGITS_RE.findall(_THOUSANDS_RE.sub("", text))


@dataclass
class CheckResult:
    failures: list[str] = field(default_factory=list)  # rule codes with detail, e.g. "V1: ..."
    warnings: list[str] = field(default_factory=list)
    names_to_check: list[str] = field(default_factory=list)
    v3_flag: bool = False  # Tamil source: names to check are a spot-check flag, not a failure

    @property
    def ok(self) -> bool:
        return not self.failures

    def passed(self, rule: str) -> bool:
        return not any(f.startswith(rule) for f in self.failures)


def check_v1(source_text: str, unit_text: str) -> bool:
    return bool(norm(source_text)) and norm(source_text) in norm(unit_text)


def check_v2(text: str, source_text: str) -> tuple[list[str], list[str]]:
    """(digit groups in text missing from source, digit groups in source missing from text)."""
    src, out = digit_groups(source_text), digit_groups(text)
    return [d for d in out if d not in src], [d for d in src if d not in out]


def names_to_check(text: str, unit_text: str, common_words: set[str]) -> list[str]:
    tokens = [(m.start(), m.group()) for m in _CAP_RE.finditer(text)]
    unit_lower = norm(unit_text).lower()
    out = []
    for start, tok in tokens:
        if start == len(text) - len(text.lstrip()):  # sentence-initial
            continue
        word = tok.strip("'-")
        if word in common_words or word.lower() in unit_lower:
            continue
        if word not in out:
            out.append(word)
    return out


def check_promise(text: str, source_text: str, unit_text: str, source_lang: str, *, common_words: set[str],
                  max_words: int) -> CheckResult:
    r = CheckResult()
    if not check_v1(source_text, unit_text):
        r.failures.append("V1: source_text is not a verbatim span of the unit")
    missing, dropped = check_v2(text, source_text)
    if missing:
        r.failures.append(f"V2: numbers not in source_text: {', '.join(missing)}")
    if dropped:
        r.warnings.append(f"V2: source numbers not in text: {', '.join(dropped)}")
    r.names_to_check = names_to_check(text, unit_text, common_words)
    if r.names_to_check:
        if source_lang == "en":
            r.failures.append(f"V3: names not in the unit: {', '.join(r.names_to_check)}")
        else:
            r.v3_flag = True
    n_words = len(text.split())
    if n_words == 0:
        r.failures.append("V4: empty text")
    elif n_words > max_words:
        r.failures.append(f"V4: {n_words} words > {max_words}")
    return r
