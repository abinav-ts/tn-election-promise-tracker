"""Spec 02 §7: V1–V4."""

from ept.extract.checks import check_promise, check_v1, check_v2, digit_groups

COMMON = {"Union", "Government", "Tamil", "Nadu", "Rs"}


def chk(text, source, unit, lang="en"):
    return check_promise(text, source, unit, lang, common_words=COMMON, max_words=60)


def test_v1_whitespace_and_nfc():
    unit = "12. Free bus travel will be\nprovided   to women."
    assert check_v1("Free bus travel will be provided to women", unit)
    assert check_v1("கொள்கை", "புதிய கொள்கை")  # NFC-equal
    assert check_v1("தமிழ்\u200C நாடு", "தமிழ் நாடு")  # zero-width joiner ignored
    assert not check_v1("Free bus travel for women", unit)
    assert check_v1("under Kalaignar's regime", "established under Kalaignar\u2019s regime")  # D-056
    assert not check_v1("   ", unit)


def test_v2_commas_missing_fails_dropped_warns():
    assert digit_groups("Rs 1,000 and 2.50 lakh") == ["1000", "2.50"]
    assert check_v2("Provide Rs 1000 a month.", "Rs 1,000 per month") == ([], [])
    r = chk("Provide Rs 2000 a month.", "Rs 1,000 per month", "Rs 1,000 per month")
    assert not r.ok and r.failures[0].startswith("V2")
    r = chk("Provide a monthly grant.", "Rs 1,000 per month", "Rs 1,000 per month")
    assert r.ok and r.warnings and r.warnings[0].startswith("V2")


def test_v3_english_failure_tamil_flag():
    unit = "A new bus terminus will be built in Madurai."
    assert chk("Build a new bus terminus in Madurai.", "A new bus terminus will be built in Madurai", unit).ok
    r = chk("Build the Kalaignar bus terminus in Madurai.", "A new bus terminus will be built in Madurai", unit)
    assert not r.ok and r.names_to_check == ["Kalaignar"]
    tamil_unit = "மதுரையில் புதிய பேருந்து நிலையம் அமைக்கப்படும்."
    r = chk("Build a new bus terminus in Madurai.", "மதுரையில் புதிய பேருந்து நிலையம் அமைக்கப்படும்", tamil_unit, "ta")
    assert r.ok and r.v3_flag and r.names_to_check == ["Madurai"]
    assert chk("Urge the Union Government to act.", "act", "act").ok  # common words, sentence-initial
    assert chk("Revive the institute set up in Kalaignar's regime.", "x", "under Kalaignar\u2019s regime x").ok


def test_v4_shape():
    assert not chk("", "x", "x").ok
    long_text = "Provide " + "very " * 60 + "much."
    assert any(f.startswith("V4") for f in chk(long_text, "x", "x").failures)
