"""Tamil text quality metrics and the OCR quality gate (spec 02 §4.2–4.3, D-036).

- Tamil share: share of letters in the Tamil block (ept.corpus.lang.tamil_ratio).
- Orthographic validity: share of Tamil words that don't start with a dependent
  vowel sign or a pulli and don't hold two vowel signs in a row. Legacy-map and
  OCR errors produce such words.
- CER: Levenshtein distance / reference length, after NFC and whitespace collapse.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Optional

from rapidfuzz.distance import Levenshtein

from ept.corpus.lang import tamil_ratio

_TAMIL_WORD_RE = re.compile(r"[஀-௿]+")
_VOWEL_SIGNS = set(chr(c) for c in range(0x0BBE, 0x0BCD)) | {"ௗ"}
_PULLI = "்"


def normalise(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", text).split())


def tamil_share(text: str) -> float:
    return tamil_ratio(text)


def word_is_valid(word: str) -> bool:
    if not word or word[0] in _VOWEL_SIGNS or word[0] == _PULLI:
        return False
    return not any(a in _VOWEL_SIGNS and b in _VOWEL_SIGNS for a, b in zip(word, word[1:]))


def validity(text: str) -> float:
    """1.0 when the text has no Tamil words (nothing to judge)."""
    words = _TAMIL_WORD_RE.findall(unicodedata.normalize("NFC", text))
    if not words:
        return 1.0
    return sum(word_is_valid(w) for w in words) / len(words)


def cer(hypothesis: str, reference: str) -> float:
    ref, hyp = normalise(reference), normalise(hypothesis)
    if not ref:
        return 0.0 if not hyp else 1.0
    return Levenshtein.distance(hyp, ref) / len(ref)


@dataclass(frozen=True)
class GateDecision:
    to_vision: bool
    reasons: tuple[str, ...]


def gate_page(calibrated_cer: float, mean_conf: Optional[float], page_validity: float, *, max_cer: float,
              min_conf: float, min_validity: float) -> GateDecision:
    """Spec 02 §4.3 step 2: calibration fail -> every page to vision; else low confidence or validity."""
    if calibrated_cer > max_cer:
        return GateDecision(True, (f"calibrated CER {calibrated_cer:.3f} > {max_cer}",))
    reasons = []
    if mean_conf is None or mean_conf < min_conf:
        reasons.append(f"mean confidence {mean_conf if mean_conf is not None else 'n/a'} < {min_conf}")
    if page_validity < min_validity:
        reasons.append(f"validity {page_validity:.3f} < {min_validity}")
    return GateDecision(bool(reasons), tuple(reasons))
