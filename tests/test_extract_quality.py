"""Spec 02 §7: Tamil share, validity, CER, gate decisions."""

import pytest

from ept.extract.ocr_gate import cer, gate_page, tamil_share, validity, word_is_valid

GATE = dict(max_cer=0.05, min_conf=80, min_validity=0.98)


def test_tamil_share():
    assert tamil_share("தமிழ் நாடு") == 1.0
    assert tamil_share("தமிழ் Wi-Fi 2016") == pytest.approx(5 / 9)  # 5 Tamil code points, 4 Latin letters
    assert tamil_share("2016") == 0.0


def test_validity_flags_orphan_signs():
    assert word_is_valid("தமிழ்")
    assert not word_is_valid("ொப")  # starts with a vowel sign
    assert not word_is_valid("்த")  # starts with a pulli
    assert not word_is_valid("தாி")  # two vowel signs in a row
    assert validity("தமிழ் நாடு") == 1.0
    assert validity("தமிழ் ொப") == 0.5
    assert validity("no tamil here") == 1.0


def test_cer():
    assert cer("தமிழ் நாடு", "தமிழ் நாடு") == 0.0
    assert cer("abcd", "abce") == pytest.approx(0.25)
    assert cer("a  b\n", "a b") == 0.0  # whitespace collapsed
    assert cer("", "") == 0.0


def test_gate_calibration_fail_sends_every_page():
    d = gate_page(0.10, 95.0, 1.0, **GATE)
    assert d.to_vision and "calibrated CER" in d.reasons[0]


def test_gate_low_confidence_or_validity():
    assert not gate_page(0.03, 90.0, 0.99, **GATE).to_vision
    assert gate_page(0.03, 70.0, 0.99, **GATE).to_vision
    assert gate_page(0.03, 90.0, 0.90, **GATE).to_vision
    assert gate_page(0.03, None, 0.99, **GATE).to_vision


TSV = "\n".join([
    "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext",
    "1\t1\t0\t0\t0\t0\t0\t0\t100\t100\t-1\t",
    "5\t1\t1\t1\t1\t1\t0\t0\t10\t10\t90\tதமிழ்\u200C",
    "5\t1\t1\t1\t1\t2\t0\t0\t10\t10\t70\tநாடு",
    "5\t1\t1\t1\t2\t1\t0\t0\t10\t10\t80\t2026",
    "5\t1\t2\t1\t1\t1\t0\t0\t10\t10\t-1\t ",
])


def test_parse_tsv_lines_conf_and_zero_width():
    from ept.extract.ocr_gate import parse_tsv

    res = parse_tsv(TSV)
    assert res.lines == ["தமிழ் நாடு", "2026"]  # ZWNJ after the pulli removed
    assert res.mean_conf == 80.0


def test_calibration_pages_even_and_deterministic():
    from ept.extract.ocr_gate import calibration_pages

    assert calibration_pages(41, 5) == [1, 11, 21, 31, 41]
    assert calibration_pages(41, 5, skip=[1]) == [2, 12, 22, 31, 41]
    assert calibration_pages(3, 5) == [1, 2, 3]


def test_calibrate_with_fake_ocr():
    import pymupdf

    from ept.extract.ocr_gate import calibrate

    pdf = pymupdf.open()
    pdf.new_page()
    fake = lambda image, lang, psm, timeout: TSV  # noqa: E731
    out = calibrate(pdf, {1: "தமிழ் நாடு\n2026"}, [1], ppi=150, lang="tam", psm=3, timeout_s=10, runner=fake)
    assert out["cer"] == 0.0 and out["pages"][0]["mean_conf"] == 80.0
