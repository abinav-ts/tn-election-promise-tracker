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


# --- S3 / S5 / S6 ------------------------------------------------------------

def _cdx_body(originals):
    import json
    header = ["timestamp", "original", "statuscode", "digest", "mimetype", "length"]
    rows = [[f"2021010{i}000000", o, "200", f"D{i}", "application/pdf", "1"] for i, o in enumerate(originals)]
    return json.dumps([header] + rows).encode()


def _clients(routes):
    from ept.config import get_config
    from ept.corpus.wayback import Wayback
    from ept.net import Http
    from fakes import FakeResponse, FakeSession

    cfg = get_config()
    http = Http(cfg, session=FakeSession([("robots.txt", FakeResponse(404))] + routes), sleep=lambda s: None)
    return cfg, http, Wayback(http)


def test_s3_cdx_catalogue_skips_years_s1_covers(root):
    from ept.corpus.catalogue import Catalogue, CatalogueItem
    from ept.corpus.sources.tnbudget_speeches import TnBudgetSpeeches
    from ept.runs import Budget
    from fakes import FakeResponse

    s1 = Catalogue("tn_policy_notes")
    s1.add([CatalogueItem(url="https://cms.tn.gov.in/x/budget_speech_e_2022_2023.pdf", source="tn_policy_notes",
                          doc_type="budget_speech", fiscal_year="2022-23", lang_hint="en")])
    s1.save()
    base = "http://www.tnbudget.tn.gov.in:80/tnweb_files/"
    body = _cdx_body([base + "budget_speech_e_2020_21.pdf", base + "BS_2022_23_ENG_FINAL.pdf",
                      base + "budget_speech_t_2020_21.pdf", base + "budget%20highlights/2019-20/BS%202019-20%20English-highlights.pdf",
                      base + "MTFP_2020_2021_eng.pdf"])
    cfg, http, wb = _clients([("showNumPages", FakeResponse(200, b"1")), ("cdx/search", FakeResponse(200, body))])
    items = {i.title: i for i in TnBudgetSpeeches(cfg, http, wb).catalogue(Budget(None))}
    assert set(items) == {"budget_speech_e_2020_21", "BS_2022_23_ENG_FINAL", "budget_speech_t_2020_21",
                          "BS 2019-20 English-highlights"}
    keep = items["budget_speech_e_2020_21"]
    assert keep.status == "new" and keep.fiscal_year == "2020-21" and keep.lang_hint == "en"
    assert keep.discovery == "wayback_cdx" and keep.url == "http://www.tnbudget.tn.gov.in/tnweb_files/budget_speech_e_2020_21.pdf"
    assert items["BS_2022_23_ENG_FINAL"].excluded_reason == "covered by tn_policy_notes (D-025)"
    assert items["budget_speech_t_2020_21"].lang_hint == "ta"
    assert items["BS 2019-20 English-highlights"].excluded_reason == "budget highlights, not the speech"


@pytest.mark.parametrize("name,expected", [
    ("Tamil_Nadu_Report_5_of_2016_Economic_Sector.pdf", None),
    ("Report_No.1_of_2017_-_Economic_Sector_Government_of_Tamil_Nadu.pdf", None),
    ("Chapter_2_Performance_Audit_of_Report_No_7_of_2017_-_Economic_Sector_Government_of_Tamil_Nadu.pdf", "part"),
    ("Annexures_Tamil_Nadu_Report_4_of_2016_PSUs.pdf", "part"),
    ("Tamil_Nadu_Revenue_1_2013_Chap_4.pdf", "before"),
    ("6-Chapter-I-Tamil-0675959bc33cff3.98564847.pdf", "part"),
    ("Report-No.2-of-2023---Housing-for-Urban-Poor-(Tamil)-065269051922cd6.pdf", "Tamil-language"),
    ("Government-of-the-Union-Territory-of-Puducherry-Report-No.-1-of-2023-Tamil.pdf", "Puducherry"),
])
def test_s5_cag_exclusions(name, expected):
    from ept.corpus.sources.cag_reports import exclusion

    year = "2013" if "2013" in name else "2017"
    reason = exclusion(f"cag.gov.in/uploads/download_audit_report/{year}/{name}", name, 2016)
    assert (reason is None) if expected is None else (expected in reason)


def test_s6_scheme_department_and_list_pages():
    from ept.corpus.sources.tn_schemes import parse_departments, parse_scheme_list

    deps = parse_departments((HTML / "s6_schemes.html").read_text(encoding="utf-8"))
    assert deps["2"].startswith("Agriculture") and len(deps) == 11
    items = parse_scheme_list((HTML / "s6_scheme_list.html").read_text(encoding="utf-8"),
                              "https://www.tn.gov.in/scheme_list.php?dep_id=Mg==")
    assert items[0] == ("https://www.tn.gov.in/scheme_details.php?id=MTU2Ng==", "Training to Farmers")
    assert len(items) == len({u for u, _ in items})


def test_s6_scheme_pages_extract_as_label_value_rows():
    from ept.corpus.parse import extract_html

    rows = "tr, .node_viewlist_even, .node_viewlist_odd"
    cur = extract_html(HTML / "s6_scheme_detail.html", "table.ng-table, .region-content", [], rows)
    assert any(p.startswith("Scheme Title/Name:") and "UYEGP" in p for p in cur.pages[0])
    old = extract_html(HTML / "s6_scheme_old.html", "table.ng-table, .region-content", [], rows)
    assert old.pages[0][0].startswith("Concerned Department : Agriculture")


def test_s2_go_cards():
    from ept.corpus.sources.tn_gos import parse_go_number, parse_listing
    import datetime as dt

    gos = parse_listing((HTML / "s2_hfw_2021.html").read_text(encoding="utf-8"),
                        "https://www.tn.gov.in/go.php?dep_id=MTE=&year=MjAyMQ==")
    assert len(gos) == 4
    first = gos[0]
    assert first["url"] == "https://cms.tn.gov.in/cms_migrated/document/GO/hfw_e_1347_2021.pdf"
    assert first["listing_date"] == dt.date(2021, 12, 20)
    assert (first["series"], first["number"]) == ("D", "1347")
    assert first["subject"].startswith("Indian Medicine and Homoeopathy - Admission")
    assert parse_go_number("G.O.(Ms) No. 045") == ("Ms", "45")
    assert parse_go_number("G.O.(Rt) No.12") == ("Rt", "12")
    assert parse_go_number("G.O.(2D)No.100") == ("2D", "100")
    assert parse_go_number("Notification") == (None, None)
