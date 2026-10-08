import csv
import datetime as dt

from ept.corpus.fetch import read_sidecar, write_sidecar
from ept.corpus.parse import redate_all
from ept.corpus.spotcheck import COLUMNS, run_spotcheck
from helpers import register

TODAY = dt.date(2026, 10, 7)


def _set_dating(root, doc, **dating):
    raw = root / doc.local_path
    meta = read_sidecar(raw)
    meta.setdefault("dating", {}).update(dating)
    write_sidecar(raw, meta)


def test_sheet_ranks_failures_first_caps_sources_and_leaves_verdicts_empty(conn, root):
    from ept.config import get_config

    # 4 GOs with an anachronism, 1 © -dated policy note, 1 Wayback-dated policy note, 1 clean GO
    for i in range(4):
        d = register(conn, "pdf/text.pdf", url=f"https://x/go{i}.pdf", listing_date="2021-05-12")
        _set_dating(root, d, latest_mention={"date": "2021-09-01", "precision": "day", "text": "01.09.2021"})
    cr = register(conn, "pdf/text.pdf", url="https://x/pn_cr.pdf", doc_type="policy_note", fiscal_year="2021-22",
                  source="tn_policy_notes")
    _set_dating(root, cr, copyright_candidate={"source": "document_text", "date": "2021-01-01", "precision": "year",
                                               "evidence": "© Government of Tamil Nadu 2021", "kind": "copyright"})
    wb = register(conn, "pdf/text.pdf", url="https://x/pn_wb.pdf", doc_type="policy_note", fiscal_year="2021-22",
                  source="tn_policy_notes", wayback={"checked": True, "kept_first_capture": "20210801000000"})
    register(conn, "pdf/text.pdf", url="https://x/clean.pdf", listing_date="2021-05-12", source="other_src")
    redate_all(conn, get_config(), TODAY)

    out = run_spotcheck()
    rows = list(csv.DictReader((root / "data" / "interim" / "spotcheck_01.csv").open()))
    assert list(rows[0]) == COLUMNS and out["rows"] == len(rows) == 5
    assert all(r["verdict"] == "" and r["note"] == "" for r in rows)
    assert [r["why_flagged"].split("]")[0] for r in rows[:3]] == ["[tn_gos · go"] * 3  # failures first, max 3
    assert "anachronism" in rows[0]["why_flagged"] and "GO header should read" in rows[0]["what_to_check"]
    assert "dated from © year" in rows[3]["why_flagged"]  # © year ranks with the weak-date group, above Wayback
    assert "Wayback-dated" in rows[4]["why_flagged"] and cr.doc_id == rows[3]["item_id"] and wb.doc_id == rows[4]["item_id"]
