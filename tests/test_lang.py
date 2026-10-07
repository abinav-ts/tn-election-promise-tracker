from ept.corpus.lang import detect, filename_lang, legacy_garbage_ratio, tamil_ratio


def test_filename_tags():
    assert filename_lang("https://cms.tn.gov.in/x/hfw_e_pn_2022_23.pdf") == "en"
    assert filename_lang("https://cms.tn.gov.in/x/hfw_t_pn_2022_23.pdf") == "ta"
    assert filename_lang("agri_e_2016_17_pn.pdf") == "en"
    assert filename_lang("BS_2021_22_ENG_FINAL.pdf") == "en"
    assert filename_lang("BS_2021_22_TAM_FINAL.pdf") == "ta"
    assert filename_lang("Governor Address (Eng).pdf") == "en"
    assert filename_lang("Governor Address (Tam).pdf") == "ta"
    assert filename_lang("speech_English.pdf") == "en" and filename_lang("speech_Tamil.pdf") == "ta"
    assert filename_lang("Telephone_Directory_2023.pdf") is None
    assert filename_lang("treasury_code_vol_1.pdf") is None


def test_tamil_ratio():
    assert tamil_ratio("தமிழ்நாடு அரசு") > 0.9
    assert tamil_ratio("Government of Tamil Nadu") == 0.0
    assert 0.4 < tamil_ratio("அரசு ஆணை Order") < 0.7
    assert tamil_ratio("123 456") == 0.0


def test_legacy_font_garbage():
    garbage = "jkpo;ehL muR ãŸ‰ òu¤F ãu¢ïjè¢ fy¥ò ©uÈ ¡¢£¤¥ ¦§¨© ª«¬­® ¯°±²³"
    assert legacy_garbage_ratio(garbage) > 0.25
    assert legacy_garbage_ratio("Plain English text only.") == 0.0
    assert detect(garbage, 0.30, 0.25, hint="ta") == "ta"
    assert detect(garbage, 0.30, 0.25, hint=None) == "en"  # garbage alone needs the _t_ tag
    assert detect("தமிழ்நாடு அரசு ஆணை", 0.30, 0.25) == "ta"
    assert detect("Government Order", 0.30, 0.25, hint="ta") == "en"
