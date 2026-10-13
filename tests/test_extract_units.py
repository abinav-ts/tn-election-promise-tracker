"""Spec 02 §7: the generic cutter on one small fixture per profile; character accounting = 100 %."""

import pymupdf
import pytest

from ept.config import ManifestoProfile
from ept.extract.pages import nonspace_len, text_layer_page
from ept.extract.units import Cutter, PageLine, number_gaps, to_units

DMK = ManifestoProfile.model_validate({
    "file": "x.pdf", "lang": "en", "route": "text_layer", "title": "t", "text_column_x": 120,
    "drop_tamil_lines": True, "clip_bottom_y": 780,
    "furniture": [r"\d{1,2}/\d{1,2}/\d{2}, \d{1,2}:\d{2} [AP]M", r"\d{1,2}/29"],
    "heading": {"bold_line": True},
    "item_marker": {"kind": "running_number", "pattern": r"(\d{1,3})(?:\.(?:\s|$|(?=[A-Za-z]))|$)"},
})
AIADMK = ManifestoProfile.model_validate({
    "file": "x.pdf", "lang": "ta", "route": "font_map", "title": "t", "furniture": [r"\d{1,2}"],
    "heading": {"pattern": r"\d{1,2}\.\s.*:"}, "item_marker": {"kind": "bullet", "pattern": r"•\s"},
    "paragraph": {"hanging_x": 126, "indent_x": 117},
})
TVK = ManifestoProfile.model_validate({
    "file": "x.pdf", "lang": "ta", "route": "ocr", "title": "t", "furniture": [r"தமிழக வெற்றிக் கழகம்\s*\d{0,3}"],
    "heading": {"pattern": r"[A-Z]\.\s.*"}, "item_marker": {"kind": "section_number", "pattern": r"(\d{1,2})(?:[.)]?\s|$)"},
})


def L(page, text, x=None, heading=False):
    return PageLine(page, text, x, heading)


def cut(profile, lines, cfg):
    opened, furniture, numbers = Cutter(profile, cfg).cut(lines)
    units = to_units("T-1", opened)
    total = sum(nonspace_len(ln.text) for ln in lines)
    assert sum(nonspace_len(u.text) for u in units) + furniture == total  # 100 % accounted
    return units, numbers


@pytest.fixture
def cfg(root):
    from ept.config import get_config

    return get_config()


def test_dmk_running_numbers_sublist_duplicate_and_wrapped_amount(cfg):
    lines = [
        L(1, "5/19/23, 5:09 PM"), L(1, "MANIFESTO TITLE"), L(1, "State Rights", heading=True),
        L(1, "1. First item"), L(1, "2.Second item with no space"), L(1, "wage raised to Rs"), L(1, "300."),
        L(1, "1/29"), L(2, "3. Rail tracks"), L(2, "1. Route A"), L(2, "2. Route B"),
        L(2, "3. Duplicate number, different text"), L(2, "5"), L(2, "Bare number line item"),
    ]
    units, numbers = cut(DMK, lines, cfg)
    assert [u.marker for u in units] == ["front_matter", "running_number", "running_number", "running_number",
                                         "running_number", "running_number"]
    assert units[1].text.startswith("State Rights\n1. First") and units[1].section == "State Rights"
    assert units[2].text.endswith("Rs\n300.")  # "300." is a wrapped amount, not item 300
    assert units[3].sub_list and "Route B" in units[3].text  # reset below the count = sub-list
    assert numbers == [1, 2, 3, 3, 5] and number_gaps(numbers) == [4]


def test_aiadmk_bullets_paragraph_and_heading(cfg):
    lines = [
        L(1, "முன்னுரை வரி", 104), L(1, "1. விவசாயம் :", 77), L(1, "• கடன் தள்ளுபடி", 104),
        L(1, "செய்யப்படும்.", 126), L(1, "கடந்த ஆண்டுகளில் வழங்கப்பட்டது", 117), L(1, "தொடர்ச்சி", 104),
        L(1, "• மானியம் வழங்கப்படும்.", 104), L(1, "1", 72), L(2, "தொடரும் வரி", 126),
        L(2, "2. கல்வி :", 73), L(2, "• பள்ளிகள்", 104),
    ]
    units, _ = cut(AIADMK, lines, cfg)
    assert [u.marker for u in units] == ["front_matter", "bullet", "paragraph", "bullet", "bullet"]
    assert units[1].text.startswith("1. விவசாயம் :\n•") and units[1].section == "1. விவசாயம் :"
    assert units[2].text == "கடந்த ஆண்டுகளில் வழங்கப்பட்டது\nதொடர்ச்சி"
    assert units[3].page_start == 1 and units[3].page_end == 2  # continues across the page break
    assert units[3].page_offsets == [[0, 1], [len("• மானியம் வழங்கப்படும்.") + 1, 2]]
    assert units[4].section == "2. கல்வி :"


def test_tvk_section_numbering_page_block_front_matter(cfg):
    lines = [
        L(1, "முன்னுரை பக்கம்"), L(2, "இரண்டாம் முன்னுரை"), L(3, "A. முதல் பிரிவு"), L(3, "1 முதல் தலைப்பு"),
        L(3, "விளக்கம்"), L(3, "2 இரண்டாம் தலைப்பு"), L(3, "B. இரண்டாம் பிரிவு"), L(3, "1 புதிய எண்ணிக்கை"),
        L(3, "தமிழக வெற்றிக் கழகம் 3"), L(4, "எண் இல்லாத பக்கம்"), L(4, "தொடர்ச்சி"),
    ]
    units, numbers = cut(TVK, lines, cfg)
    assert [u.marker for u in units] == ["front_matter", "front_matter", "section_number", "section_number",
                                         "section_number", "page_block"]
    assert numbers == [1, 2, 1]
    assert units[4].section == "B. இரண்டாம் பிரிவு" and units[5].text == "எண் இல்லாத பக்கம்\nதொடர்ச்சி"


def test_text_layer_sidebar_clip_and_furniture(root):
    pdf = pymupdf.open()
    page = pdf.new_page(width=600, height=800)
    page.insert_text((30, 20), "5/19/23, 5:09 PM", fontname="helv", fontsize=8)  # furniture left of column
    page.insert_text((40, 100), "Anna Arivalayam, Chennai", fontname="helv", fontsize=10)  # sidebar
    page.insert_text((130, 70), "Heading Line", fontname="hebo", fontsize=12)
    page.insert_text((130, 130), "1. An item", fontname="helv", fontsize=12)
    page.insert_text((130, 785), "2. Clipped copy", fontname="helv", fontsize=12)
    out = text_layer_page(page, DMK)
    assert out.lines == ["5/19/23, 5:09 PM", "Heading Line", "1. An item"]
    assert out.heading_lines == [1]
    assert out.removed_chars == nonspace_len("Anna Arivalayam, Chennai") + nonspace_len("2. Clipped copy")
    assert out.lines.index("Heading Line") == 1


def test_running_header_page_number_wrapped_and_repeated_heading(cfg):
    profile = TVK.model_copy(update={"running_header_lines": 5, "running_header_in_section": 2,
                                     "page_number_lines": 2,
                                     "heading": TVK.heading.model_copy(update={"wrap_max_chars": 40})})
    lines = [
        L(1, "அறம்"), L(1, "01"), L(1, "தலைப்பு"), L(1, "A. முதல் பிரிவு நீண்ட"), L(1, "தலைப்பு வரி"),
        L(1, "1"), L(1, "முதல் உருப்படி"), L(1, "தமிழக வெற்றிக் கழகம்"), L(1, "7"),
        L(2, "அறம்"), L(2, "01"), L(2, "தலைப்பு"), L(2, "A. முதல் பிரிவு நீண்ட"), L(2, "2"), L(2, "இரண்டாம்"),
        L(2, "10"), L(2, "தமிழக வெற்றிக் கழகம்"), L(2, "8"),
    ]
    units, numbers = cut(profile, lines, cfg)
    assert [u.marker for u in units] == ["section_number", "section_number"]
    assert numbers == [1, 2]  # the repeated heading on page 2 doesn't reset numbering; "10" there is no item
    assert units[0].section == "அறம் 01 / A. முதல் பிரிவு நீண்ட தலைப்பு வரி"
    assert units[0].text.startswith("A. முதல் பிரிவு நீண்ட\nதலைப்பு வரி\n1")
    assert "7" not in units[0].text.split("\n")  # page number is furniture
