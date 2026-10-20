"""Spec 04 §4.3 / §7: eligibility boundaries, landmark dates, refused cutoffs, the DB-wide check."""

import datetime as dt

import pytest

from retrieve_helpers import add_doc

D = dt.date


def _avail(conn):
    from ept.config import get_config
    from ept.retrieve.eligible import load_availability

    return {c.chunk_id: c for c in load_availability(conn, get_config())}


def _cut(term, month=None, snapshot=D(2030, 1, 1)):
    from ept.config import get_config
    from ept.retrieve.eligible import full_term, landmark

    t = get_config().term(term)
    return landmark(t, month, snapshot) if month is not None else full_term(t)


def test_landmark_dates_are_add_months_of_sworn_in(root):
    assert _cut("DMK-2021", 5).cutoff_date == D(2021, 10, 7)
    assert _cut("DMK-2021", 12).cutoff_date == D(2022, 5, 7)
    assert _cut("AIADMK-2016", 6).cutoff_date == D(2016, 11, 23)
    assert _cut("TVK-2026", 5).cutoff_date == D(2026, 10, 10)
    full = _cut("DMK-2021")
    assert full.cutoff_date is None and full.upper == D(2026, 5, 9) and full.lower == D(2021, 5, 7)


def test_configured_cutoffs_per_term(root):
    from ept.config import get_config
    from ept.retrieve.eligible import term_cutoffs

    cfg = get_config()
    snap = D(2026, 10, 10)
    assert [c.label for c in term_cutoffs(cfg, "DMK-2021", snap)] == ["m5", "m6", "m12", "m24", "m36", "m48", "full"]
    assert [c.label for c in term_cutoffs(cfg, "TVK-2026", snap)] == ["m5"]
    assert [c.label for c in term_cutoffs(cfg, "AIADMK-2016", snap, ["full", "12"])] == ["m12", "full"]
    assert sum(len(term_cutoffs(cfg, t.term_id, snap)) for t in cfg.settings.terms) == 15


def test_refused_cutoffs(root):
    from ept.config import get_config
    from ept.retrieve.eligible import CutoffRefused, landmark, term_cutoffs

    cfg = get_config()
    with pytest.raises(CutoffRefused):  # after the snapshot
        landmark(cfg.term("TVK-2026"), 5, D(2026, 10, 9))
    with pytest.raises(CutoffRefused):  # after term_end
        landmark(cfg.term("AIADMK-2016"), 60, D(2030, 1, 1))
    with pytest.raises(CutoffRefused):  # ongoing term: no full-term run
        term_cutoffs(cfg, "TVK-2026", D(2026, 10, 10), ["full"])
    with pytest.raises(CutoffRefused):  # not configured
        term_cutoffs(cfg, "DMK-2021", D(2026, 10, 10), ["7"])


def test_snapshot_end_is_latest_available_by(conn):
    from ept.config import get_config
    from ept.retrieve.eligible import load_availability, snapshot_end

    add_doc(conn, "a" * 16, doc_date="2021-06-01")
    add_doc(conn, "b" * 16, doc_date="2021-07-01", precision="month")
    assert snapshot_end(get_config(), load_availability(conn, get_config())) == D(2021, 7, 31)


def test_boundaries(conn):
    from ept.retrieve.eligible import eligible

    on = add_doc(conn, "1" * 16, doc_date="2021-10-07")[0]  # on the m5 cutoff
    after = add_doc(conn, "2" * 16, doc_date="2021-10-08")[0]  # a day after
    month = add_doc(conn, "3" * 16, doc_date="2021-10-01", precision="month")[0]  # month of the cutoff
    sept = add_doc(conn, "4" * 16, doc_date="2021-09-01", precision="month")[0]
    year = add_doc(conn, "5" * 16, doc_date="2021-01-01", precision="year")[0]
    undated = add_doc(conn, "6" * 16, doc_date=None, doc_type="cag_report")[0]
    before = add_doc(conn, "7" * 16, doc_date="2021-05-06")[0]  # day before sworn_in
    first = add_doc(conn, "8" * 16, doc_date="2021-05-07")[0]  # sworn_in itself
    end = add_doc(conn, "9" * 16, doc_date="2026-05-09")[0]  # term_end
    past = add_doc(conn, "a" * 16, doc_date="2026-05-10")[0]  # day after term_end
    av = _avail(conn)
    m5, full = _cut("DMK-2021", 5), _cut("DMK-2021")
    assert eligible(av[on], m5) and not eligible(av[after], m5)
    assert not eligible(av[month], m5)  # Oct 2021 ends 2021-10-31 > 2021-10-07
    assert eligible(av[sept], m5)
    assert not eligible(av[year], m5) and eligible(av[year], _cut("DMK-2021", 12))
    assert not eligible(av[undated], m5) and not eligible(av[undated], full)
    assert not eligible(av[before], m5) and not eligible(av[before], full)
    assert eligible(av[first], m5)
    assert eligible(av[end], full) and not eligible(av[past], full)


def test_month_precision_in_on_month_end_cutoff(conn):
    from ept.config import get_config
    from ept.retrieve.eligible import Cutoff, eligible

    cid = add_doc(conn, "1" * 16, doc_date="2021-10-01", precision="month")[0]
    c = Cutoff("DMK-2021", "x", None, D(2021, 10, 31), get_config().term("DMK-2021").sworn_in, D(2021, 10, 31))
    assert eligible(_avail(conn)[cid], c)


def test_fiscal_year_bound_applies_in_eligibility(conn):
    from ept.retrieve.eligible import eligible

    late = add_doc(conn, "1" * 16, doc_type="policy_note", doc_date="2022-08-01", fy="2021-22")[0]
    undated = add_doc(conn, "2" * 16, doc_type="policy_note", doc_date=None, fy="2021-22")[0]
    av = _avail(conn)
    assert av[late].available_by == D(2022, 3, 31) and av[undated].available_by == D(2022, 3, 31)
    assert eligible(av[late], _cut("DMK-2021", 12)) and eligible(av[undated], _cut("DMK-2021", 12))
    assert not eligible(av[late], _cut("DMK-2021", 6))


def test_db_wide_check_catches_planted_violation(conn):
    from ept import db
    from ept.config import get_config
    from ept.retrieve.eligible import check_retrievals
    from ept.schema import Retrieval
    from retrieve_helpers import add_promise

    ok = add_doc(conn, "1" * 16, doc_date="2021-09-01")[0]
    late = add_doc(conn, "2" * 16, doc_date="2021-10-08")[0]
    undated = add_doc(conn, "3" * 16, doc_date=None, doc_type="cag_report")[0]
    iid = add_promise(conn, "DMK-2021-0001", "Build roads.")[0]
    db.upsert(conn, Retrieval(indicator_id=iid, chunk_id=ok, rank=1, cutoff_date="2021-10-07", run_id="r"))
    assert check_retrievals(conn, get_config())["violations"] == 0
    db.upsert(conn, Retrieval(indicator_id=iid, chunk_id=late, rank=2, cutoff_date="2021-10-07", run_id="r"))
    db.upsert(conn, Retrieval(indicator_id=iid, chunk_id=undated, rank=1, cutoff_date=None, run_id="r"))
    out = check_retrievals(conn, get_config())
    assert out["violations"] == 2 and out["undated"] == 1
