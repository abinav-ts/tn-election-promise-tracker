"""Spec 02 §7: VANAVIL table, non-legacy spans untouched, overprint removal, span re-joining."""

from ept.extract.fontmap import Glyph, group_lines, line_text, remove_overprint
from ept.extract.vanavil_map import vanavil2unicode

LEGACY = {"VANAVIL-Avvaiyar", "VANAVIL-Swetha"}
BULLETS = {"Wingdings"}


def glyphs(text, font="VANAVIL-Avvaiyar", x=100.0, y=50.0, w=6.0):
    out = []
    for c in text:
        out.append(Glyph(c, font, x, x + w, y))
        x += w
    return out


def convert(gs):
    return line_text(gs, LEGACY, BULLETS, "•", 1.5)[0]


def test_table_known_strings():
    assert vanavil2unicode("jäœ ehL") == "தமிழ் நாடு"
    assert vanavil2unicode("bgh") == "பொ"  # prefix vowel sign written before the consonant, reordered
    assert vanavil2unicode("nfh") == "கோ"
    assert vanavil2unicode("ä") == "மி" and vanavil2unicode("Â") == "தி"  # ligature glyphs


def test_non_legacy_span_untouched():
    gs = glyphs("jäœ") + glyphs(" (hub and spoke) 2016", font="Helvetica", x=118.0)
    assert convert(gs) == "தமிழ் (hub and spoke) 2016"


def test_overprint_four_copies_to_one():
    base = glyphs("jäœ ehL")
    copies = base + [Glyph(g.c, g.font, g.x0 + dx, g.x1 + dx, g.y + dy) for dx, dy in
                     [(0.24, 0.0), (0.0, 0.24), (0.24, 0.24)] for g in base]
    kept = remove_overprint(copies, 1.0)
    assert len(kept) == len(base)
    assert convert(group_lines(kept, 2.0)[0]) == "தமிழ் நாடு"


def test_partial_overprint_spans():
    # the real file splits copies unevenly: "jä" x3, then "jäœ ehL", then "œ ehL" x2
    full = glyphs("jäœ ehL")
    parts = full[:2] + full[:2] + full[:2] + full + full[2:] + full[2:]
    kept = remove_overprint(parts, 1.0)
    assert convert(group_lines(kept, 2.0)[0]) == "தமிழ் நாடு"


def test_identical_letters_side_by_side_are_kept():
    gs = glyphs("ff")  # two real glyphs one width apart, not an overprint
    assert len(remove_overprint(gs, 1.0)) == 2


def test_word_split_across_spans_is_mended():
    # prefix vowel "b" in one span (font), consonant + "h" in another: converted as one run
    gs = glyphs("b", font="VANAVIL-Swetha") + glyphs("gh", font="VANAVIL-Avvaiyar", x=106.0)
    assert convert(gs) == "பொ"


def test_lines_grouped_by_baseline_and_sorted_by_x():
    a = glyphs("ehL", y=80.0, x=140.0)
    b = glyphs("jäœ", y=80.2, x=100.0)
    c = glyphs("f", y=120.0)
    lines = group_lines(c + a + b, 2.0)
    assert len(lines) == 2
    assert convert(lines[0]) == "தமிழ் நாடு"  # gap between the two runs becomes a space
    assert convert(lines[1]) == "க"


def test_bullet_glyph_becomes_marker():
    gs = glyphs("\x01", font="Wingdings", x=80.0) + glyphs("f", x=110.0)
    assert convert(gs) == "• க"
