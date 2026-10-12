"""`font_map` route (spec 02 §4.2, D-035): legacy-font Tamil spans -> Unicode.

Steps: read characters with their font and position; drop fake-bold overprint
copies; re-join characters into lines by position; convert each run of
legacy-font characters with the vendored VANAVIL table (so a word split across
spans is converted as one); keep other fonts as they are; NFC.

Overprint removal works per character, not per span: the copies of a bold line
are not always split into identical spans (e.g. "jä" x3 then "jäœ ehL"), so a
character is dropped when the same glyph was already kept within
`overprint_px` of its origin. This is the spec's rule applied at glyph level.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import Iterable

import pymupdf

from ept.extract.vanavil_map import vanavil2unicode


@dataclass(frozen=True)
class Glyph:
    c: str
    font: str
    x0: float
    x1: float
    y: float  # baseline (origin y)


@dataclass(frozen=True)
class Line:
    y: float
    x0: float
    text: str
    legacy_text: str  # converted legacy-font runs only (the font-map gate measures these)


def page_glyphs(page: pymupdf.Page) -> list[Glyph]:
    out = []
    for block in page.get_text("rawdict")["blocks"]:
        for line in block.get("lines", []):
            for span in line["spans"]:
                for ch in span["chars"]:
                    out.append(Glyph(ch["c"], span["font"], ch["bbox"][0], ch["bbox"][2], ch["origin"][1]))
    return out


def remove_overprint(glyphs: Iterable[Glyph], px: float) -> list[Glyph]:
    """Drop a glyph if the same character in the same font was kept within `px` (x and y) of it."""
    kept: list[Glyph] = []
    index: dict[tuple[str, str, int, int], list[Glyph]] = {}
    for g in glyphs:
        bx, by = int(g.x0 // px), int(g.y // px)
        dup = False
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for k in index.get((g.c, g.font, bx + dx, by + dy), ()):
                    if abs(k.x0 - g.x0) <= px and abs(k.y - g.y) <= px:
                        dup = True
                        break
                if dup:
                    break
            if dup:
                break
        if not dup:
            kept.append(g)
            index.setdefault((g.c, g.font, bx, by), []).append(g)
    return kept


def group_lines(glyphs: Iterable[Glyph], tol: float) -> list[list[Glyph]]:
    """Glyphs whose baselines lie within `tol` of a line's first baseline form one line, sorted by x."""
    lines: list[list[Glyph]] = []
    for g in sorted(glyphs, key=lambda g: (g.y, g.x0)):
        if lines and abs(g.y - lines[-1][0].y) <= tol:
            lines[-1].append(g)
        else:
            lines.append([g])
    return [sorted(line, key=lambda g: g.x0) for line in lines]


def _is_legacy(font: str, legacy_fonts: set[str]) -> bool:
    return font.split("+")[-1] in legacy_fonts


def line_text(glyphs: list[Glyph], legacy_fonts: set[str], bullet_fonts: set[str], bullet: str,
              space_gap_px: float) -> tuple[str, str]:
    """Convert one line -> (text, converted legacy-font runs only).

    A gap wider than `space_gap_px` between glyphs with no space glyph becomes a space."""
    runs: list[tuple[str, list[str]]] = []  # (kind, chars); kind = legacy | bullet | plain
    prev = None
    for g in glyphs:
        font = g.font.split("+")[-1]
        kind = "bullet" if font in bullet_fonts else "legacy" if _is_legacy(font, legacy_fonts) else "plain"
        if prev is not None and g.x0 - prev.x1 > space_gap_px and not g.c.isspace() and not prev.c.isspace():
            runs.append(("plain", [" "]))
        if runs and runs[-1][0] == kind and kind != "bullet":
            runs[-1][1].append(g.c)
        else:
            runs.append((kind, [g.c]))
        prev = g
    parts, legacy_parts = [], []
    for kind, chars in runs:
        text = "".join(chars)
        if kind == "legacy":
            parts.append(vanavil2unicode(text))
            legacy_parts.append(parts[-1])
        elif kind == "bullet":
            parts.append(bullet if text.strip() else text)
        else:
            parts.append(text)
    return _clean("".join(parts)), _clean(" ".join(legacy_parts))


def _clean(text: str) -> str:
    return unicodedata.normalize("NFC", " ".join(text.split()))


def page_lines(page: pymupdf.Page, legacy_fonts: Iterable[str], bullet_fonts: Iterable[str], bullet: str,
               overprint_px: float, line_tol_px: float, space_gap_px: float) -> tuple[list[Line], dict[str, int]]:
    """All non-empty lines of a font-mapped page, top to bottom, plus glyph counts (raw, overprint dropped)."""
    legacy, bullets = set(legacy_fonts), set(bullet_fonts)
    raw = page_glyphs(page)
    kept = remove_overprint(raw, overprint_px)
    out = []
    for glyphs in group_lines(kept, line_tol_px):
        text, legacy_text = line_text(glyphs, legacy, bullets, bullet, space_gap_px)
        if text:
            out.append(Line(y=glyphs[0].y, x0=glyphs[0].x0, text=text, legacy_text=legacy_text))
    return out, {"glyphs": len(raw), "overprint_dropped": len(raw) - len(kept)}

