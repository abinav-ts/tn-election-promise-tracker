"""Tesseract OCR fallback for pages with too little extractable text (spec 01 §4.4)."""

from __future__ import annotations

import shutil
import subprocess

import pymupdf


class OcrUnavailable(RuntimeError):
    pass


def run_tesseract(png: bytes, lang: str, timeout_s: float) -> str:
    """tesseract stdin -> stdout. Kept separate so tests can mock it."""
    exe = shutil.which("tesseract")
    if exe is None:
        raise OcrUnavailable("tesseract not found on PATH")
    proc = subprocess.run([exe, "stdin", "stdout", "-l", lang], input=png, capture_output=True,
                          timeout=timeout_s, check=False)
    if proc.returncode != 0:
        raise OcrUnavailable(proc.stderr.decode("utf-8", "replace")[:300])
    return proc.stdout.decode("utf-8", "replace")


def ocr_page(page: pymupdf.Page, lang: str, dpi: int, timeout_s: float) -> str:
    pix = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY)
    return run_tesseract(pix.tobytes("png"), lang, timeout_s)
