"""Tamil text quality metrics and the OCR quality gate (spec 02 §4.2–4.3, D-036).

- Tamil share: share of letters in the Tamil block (ept.corpus.lang.tamil_ratio).
- Orthographic validity: share of Tamil words that don't start with a dependent
  vowel sign or a pulli and don't hold two vowel signs in a row. Legacy-map and
  OCR errors produce such words.
- CER: Levenshtein distance / reference length, after NFC and whitespace collapse.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import unicodedata
from dataclasses import dataclass
from typing import Any, Iterable, Optional

import pymupdf
from rapidfuzz.distance import Levenshtein

from ept.corpus.lang import tamil_ratio

_TAMIL_WORD_RE = re.compile(r"[\u0B80-\u0BFF]+")
_VOWEL_SIGNS = set(chr(c) for c in range(0x0BBE, 0x0BCD)) | {"\u0BD7"}
_PULLI = "\u0BCD"


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


# --- Tesseract -------------------------------------------------------------

ZERO_WIDTH = dict.fromkeys(map(ord, "\u200B\u200C\u200D\uFEFF"))


class OcrUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class OcrResult:
    lines: list[str]
    mean_conf: Optional[float]  # mean word confidence (0-100); None if no words


def run_tesseract_tsv(image: bytes, lang: str, psm: int, timeout_s: float) -> str:
    """tesseract stdin -> TSV on stdout. Kept separate so tests can replace it."""
    exe = shutil.which("tesseract")
    if exe is None:
        raise OcrUnavailable("tesseract not found on PATH")
    proc = subprocess.run([exe, "stdin", "stdout", "-l", lang, "--psm", str(psm), "tsv"], input=image,
                          capture_output=True, timeout=timeout_s, check=False)
    if proc.returncode != 0:
        raise OcrUnavailable(proc.stderr.decode("utf-8", "replace")[:300])
    return proc.stdout.decode("utf-8", "replace")


def parse_tsv(tsv: str) -> OcrResult:
    """Words grouped into lines by (block, paragraph, line); zero-width joiners removed (a Tesseract
    artefact after the pulli; font-mapped and printed text don't carry them)."""
    lines: dict[tuple[int, int, int], list[str]] = {}
    confs = []
    for row in tsv.splitlines()[1:]:
        cols = row.split("\t")
        if len(cols) < 12 or cols[0] != "5":
            continue
        word = unicodedata.normalize("NFC", cols[11].translate(ZERO_WIDTH)).strip()
        if not word:
            continue
        lines.setdefault((int(cols[2]), int(cols[3]), int(cols[4])), []).append(word)
        conf = float(cols[10])
        if conf >= 0:
            confs.append(conf)
    return OcrResult(lines=[" ".join(ws) for _, ws in sorted(lines.items())],
                     mean_conf=round(sum(confs) / len(confs), 2) if confs else None)


def ocr_image(image: bytes, lang: str, psm: int, timeout_s: float, runner=None) -> OcrResult:
    return parse_tsv((runner or run_tesseract_tsv)(image, lang, psm, timeout_s))


def page_image(page: pymupdf.Page, ppi: Optional[int] = None) -> bytes:
    """The page's own scan at native resolution if it is a single-image page; else a render at `ppi`."""
    images = page.get_images(full=True)
    if ppi is None and len(images) == 1:
        return page.parent.extract_image(images[0][0])["image"]
    pix = page.get_pixmap(dpi=ppi or 150, colorspace=pymupdf.csGRAY)
    return pix.tobytes("png")


# --- calibration (spec 02 §4.3 step 1) --------------------------------------


def calibration_pages(n_pages: int, k: int, skip: Iterable[int] = ()) -> list[int]:
    """k evenly spaced 1-based page numbers, skipping `skip`; deterministic."""
    pool = [p for p in range(1, n_pages + 1) if p not in set(skip)]
    if k >= len(pool):
        return pool
    return [pool[round(i * (len(pool) - 1) / (k - 1))] for i in range(k)] if k > 1 else [pool[0]]


def calibrate(pdf: pymupdf.Document, reference: dict[int, str], pages: list[int], *, ppi: int, lang: str,
              psm: int, timeout_s: float, runner=None) -> dict[str, Any]:
    """OCR the reference pages rendered at `ppi`; CER against their font-mapped text (pooled over pages)."""
    per_page = []
    edits = ref_len = 0
    for n in pages:
        ocr = ocr_image(page_image(pdf[n - 1], ppi), lang, psm, timeout_s, runner)
        hyp, ref = normalise("\n".join(ocr.lines)), normalise(reference[n])
        dist = Levenshtein.distance(hyp, ref)
        edits += dist
        ref_len += len(ref)
        per_page.append({"page": n, "cer": round(dist / len(ref), 4) if ref else None, "mean_conf": ocr.mean_conf,
                         "ref_chars": len(ref)})
    return {"pages": per_page, "cer": round(edits / ref_len, 4) if ref_len else None, "ppi": ppi,
            "lang": lang, "psm": psm}
