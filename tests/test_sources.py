import pytest

from ept.corpus.sources.base import b64, unb64
from ept.corpus.sources.tn_policy_notes import classify, parse_dept_list, parse_listing
from conftest import FIXTURES

HTML = FIXTURES / "html"


def test_base64_round_trip():
    assert b64("2022-2023") == "MjAyMi0yMDIz"
    assert unb64("MTE=") == "11"
    for v in ["1", "45", "2016-2017", "2026"]:
        assert unb64(b64(v)) == v


def test_s1_dept_list():
    deps = parse_dept_list((HTML / "s1_dept_list.html").read_text(encoding="utf-8"))
    assert len(deps) == 38
    assert deps["11"] == "Health and Family Welfare Department"
    assert deps["2"].startswith("Agriculture")


def test_s1_listing_page():
    page = "https://www.tn.gov.in/document.php?dep_id=MTE=&year=MjAxOS0yMDIw&cate_name=YWxs"
    heading, links = parse_listing((HTML / "s1_hfw_2019_20.html").read_text(encoding="utf-8"), page)
    assert heading == "Health and Family Welfare Department"
    base = "https://cms.tn.gov.in/cms_migrated/document/docfiles/"
    assert [u for u, _ in links] == [base + "hfw_e_pn_2019_20.pdf", base + "hfw_e_pb_2019_20.pdf",
                                     base + "hfw_e_cc_2019_20.pdf"]
    assert all(t for _, t in links)  # the title link wins over the icon link


@pytest.mark.parametrize("title,filename,expected", [
    ("Policy Note of Health and Family Welfare Department - 2019-2020", "hfw_e_pn_2019_20.pdf",
     ("policy_note", None, None)),
    ("Performance Budget of Health and Family Welfare Department - 2018-2019", "hfw_e_pb_2019_20.pdf",
     ("other", "performance_budget", None)),
    ("Citizens Charter of Agriculture Department - 2016-2017", "agri_e_2016_17_cc.pdf",
     (None, "citizen_charter", "citizen charter (D-022)")),
    ("Policy note of Agriculture Department- 2016-2017", "agri_e_2016_17_pn.pdf", ("policy_note", None, None)),
    ("Telephone Directory - 2023", "Telephone_Directory_2023.pdf",
     (None, None, "not a listed document type (D-022, D-025)")),
    ("Interim Budget Speech for the year 2016-2017", "interim_budget_speech_e_2016-17.pdf",
     ("budget_speech", "interim", None)),
    ("Budget Speech for the year 2017-2018", "fin_budget_speech_e_2017_18.pdf", ("budget_speech", None, None)),
    ("Agriculture Interim Budget Speech - 2026-2027", "IAB_e_2026_27.pdf",
     ("budget_speech", "agriculture_interim", None)),
    ("Honble Governors Address in the Legislative Assembly on 16th June 2016", "governor_address_e_160616.pdf",
     ("governor_address", None, None)),
    ("Address delivered by the Honble Governor in the Legislative Assembly on 6th January 2025",
     "GA_e_060125.pdf", ("governor_address", None, None)),
    ("Tamil Nadu Data Centre Policy - 2021", "TN_Data_Centre_Policy_2021.pdf", ("other", "policy", None)),
    ("Draft Tamil Nadu Dog Breeding Policy", "Draft_TN_Dog_Breeding_Policy.pdf", ("other", "policy_draft", None)),
    ("Local Fund Audit Department - Consolidated Audit Report -2016-2017", "lfa_consolidated_audit_report_e_2016_17.pdf",
     (None, None, "not a listed document type (D-022, D-025)")),
])
def test_s1_classify(title, filename, expected):
    assert classify(title, filename) == expected


def test_s1_adapter_yields_items(root):
    from ept.config import get_config
    from ept.corpus.sources.tn_policy_notes import TnPolicyNotes
    from ept.corpus.wayback import Wayback
    from ept.net import Http
    from ept.runs import Budget
    from fakes import FakeResponse, FakeSession

    page = (HTML / "s1_hfw_2019_20.html").read_bytes()
    session = FakeSession([
        ("robots.txt", FakeResponse(404)),
        ("document_dept_list.php", FakeResponse(200, (HTML / "s1_dept_list.html").read_bytes(),
                                                {"Content-Type": "text/html; charset=UTF-8"})),
        ("dep_id=MTE=&year=MjAxOS0yMDIw", FakeResponse(200, page, {"Content-Type": "text/html"})),
        ("document.php", FakeResponse(200, b"<html><div id='content'></div></html>", {"Content-Type": "text/html"})),
    ])
    cfg = get_config()
    http = Http(cfg, session=session, sleep=lambda s: None)
    items = list(TnPolicyNotes(cfg, http, Wayback(http)).catalogue(Budget(None)))
    assert len(items) == 3
    pn = items[0]
    assert pn.doc_type == "policy_note" and pn.department == "Health and Family Welfare Department"
    assert pn.fiscal_year == "2019-20" and pn.lang_hint == "en" and pn.dep_id == "11"
    assert items[2].status == "excluded"
