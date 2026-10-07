import json

from ept.corpus.catalogue import Catalogue, CatalogueItem
from ept.corpus.coverage import SECTIONS, run_coverage
from helpers import register


def test_report_has_all_sections_and_valid_gap_list(conn, root):
    register(conn, "pdf/text.pdf", url="https://cms.tn.gov.in/x/go1.pdf", listing_date="2021-05-12")
    cat = Catalogue("tn_policy_notes")
    cat.add([CatalogueItem(url="https://cms.tn.gov.in/x/hfw_e_pn_2021_22.pdf", source="tn_policy_notes",
                           doc_type="policy_note", department="Health and Family Welfare Department",
                           fiscal_year="2021-22", lang_hint="en")])
    cat.save()
    summary = run_coverage()
    md = (root / "reports" / "coverage_01.md").read_text()
    for s in SECTIONS:
        assert f"## {s}" in md
    data = json.loads((root / "reports" / "coverage_01.json").read_text())
    assert summary["documents"] == 1 and isinstance(data["gaps"], list) and data["gaps"]
    for g in data["gaps"]:
        assert g["issue"] and "suggested_search" in g
    kinds = {g["doc_type"] for g in data["gaps"]}
    # one policy-note year is listed, so every other FY is a gap; no speech or address is listed at all
    assert {"policy_note", "budget_speech", "governor_address", "cag_report", "go"} <= kinds
    pn_gaps = {g["fiscal_year"] for g in data["gaps"] if g["doc_type"] == "policy_note"}
    assert "2021-22" not in pn_gaps and "2016-17" in pn_gaps
    assert list((root / "reports" / "runs").glob("coverage-*.json"))
