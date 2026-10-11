import csv
import datetime as dt

from ept.corpus.catalogue import Catalogue, CatalogueItem
from ept.corpus.pairing import write_pairs


def _go(url, lang, no="45", series="Ms", year="2021", date="2021-05-12", dept="Transport Department"):
    return CatalogueItem(url=url, source="tn_gos", doc_type="go", department=dept, lang_hint=lang,
                         listing_date=dt.date.fromisoformat(date),
                         identifiers={"go_number": no, "go_series": series, "go_year": year})


def _rows(root):
    return {r["ta_item"].rsplit("/", 1)[-1]: r for r in csv.DictReader((root / "data" / "interim" / "lang_pairs.csv").open())}


def test_go_fy_and_date_pairing(conn, root):
    gos = Catalogue("tn_gos")
    gos.add([_go("https://x/tr_e_45_2021.pdf", "en"), _go("https://x/tr_t_45_2021.pdf", "ta"),
             _go("https://x/tr_t_99_2021.pdf", "ta", no="99")])
    gos.save()
    pn = Catalogue("tn_policy_notes")
    pn.add([CatalogueItem(url="https://x/hfw_e_pn_2021_22.pdf", source="tn_policy_notes", doc_type="policy_note",
                          department="Health", fiscal_year="2021-22", lang_hint="en"),
            CatalogueItem(url="https://x/hfw_t_pn_2021_22.pdf", source="tn_policy_notes", doc_type="policy_note",
                          department="Health", fiscal_year="2021-22", lang_hint="ta")])
    pn.save()
    sch = Catalogue("tn_schemes")
    sch.add([CatalogueItem(url="https://x/e1", source="tn_schemes", doc_type="scheme_page", department="Agri",
                           listing_date=dt.date(2021, 6, 1), lang_hint="en"),
             CatalogueItem(url="https://x/t_same", source="tn_schemes", doc_type="scheme_page", department="Agri",
                           listing_date=dt.date(2021, 6, 1), lang_hint="ta"),
             CatalogueItem(url="https://x/t_other", source="tn_schemes", doc_type="scheme_page", department="Agri",
                           listing_date=dt.date(2021, 7, 9), lang_hint="ta")])
    sch.save()
    out = write_pairs()
    rows = _rows(root)
    assert rows["tr_t_45_2021.pdf"]["status"] == "paired" and rows["tr_t_45_2021.pdf"]["en_doc_id"]
    assert rows["tr_t_99_2021.pdf"]["status"] == "tamil_only"
    assert rows["hfw_t_pn_2021_22.pdf"]["status"] == "paired"
    assert rows["t_same"]["status"] == "paired" and rows["t_other"]["status"] == "tamil_only"  # different date
    assert out == {"tamil_items": 5, "paired": 3, "tamil_only": 2}
