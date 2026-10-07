import datetime as dt

from ept.corpus.datefind import (
    Candidate, date_from_filename, find_dates, issue_date_from_text, latest_mention, listing_candidate, needs_review,
    resolve, wayback_candidate,
)

D = dt.date
TODAY = D(2026, 10, 7)
KW = dict(window_start=D(2016, 5, 1), today=TODAY, conflict_days=7, fy_slack_months=3)


def C(source, date, precision="day"):
    return Candidate(source, date, precision)


def test_find_dates_formats():
    found = {(f.date, f.precision) for f in find_dates(
        "on 12.05.2021, 3-6-2019 and 7/8/2018; the 16th June 2016; August 13, 2021; 2nd day of March, 2020; "
        "in January 2022; 31.02.2021 is invalid")}
    assert (D(2021, 5, 12), "day") in found and (D(2019, 6, 3), "day") in found and (D(2018, 8, 7), "day") in found
    assert (D(2016, 6, 16), "day") in found and (D(2021, 8, 13), "day") in found and (D(2020, 3, 2), "day") in found
    assert (D(2022, 1, 1), "month") in found
    assert not any(d == D(2021, 3, 3) for d, _ in found)
    # a day date is not also reported as a month date
    assert (D(2016, 6, 1), "month") not in found


def test_issue_date_keywords():
    assert issue_date_from_text("G.O.(Ms) No.45 Dated: 12.05.2021").date == "2021-05-12"
    c = issue_date_from_text("Budget speech presented on 13th August 2021 in the Assembly")
    assert c.date == "2021-08-13" and c.source == "document_text"
    assert issue_date_from_text("Address in the Legislative Assembly on 21st June 2021").date == "2021-06-21"
    assert issue_date_from_text("Laid on the Table of the House in March 2019").precision == "month"
    assert issue_date_from_text("POLICY NOTE 2016-2017. Scheme started on 01.04.2016") is None


def test_filename_dates():
    assert date_from_filename("http://x/Budget_Speech_04_08_2011.pdf", TODAY).date == "2011-08-04"
    assert date_from_filename("http://x/governor_address_e_160616.pdf", TODAY).date == "2016-06-16"
    assert date_from_filename("http://x/GA_e_050122.pdf", TODAY).date == "2022-01-05"
    assert date_from_filename("http://x/hfw_e_pn_2016_17.pdf", TODAY) is None
    assert date_from_filename("http://x/report_311299.pdf", TODAY) is None  # 31-12-2099 is in the future


def test_precedence_ranks():
    cands = [C("wayback_capture", "2021-09-01"), C("filename", "2021-08-14"), C("document_text", "2021-08-13"),
             C("listing", "2021-08-12"), C("manual", "2021-08-11")]
    for expected in ["manual", "listing", "document_text", "filename", "wayback_capture"]:
        r = resolve(cands, fiscal_year="2021-22", latest_mentioned=None, **KW)
        assert r.source == expected
        cands = [c for c in cands if c.source != expected]
    r = resolve([], fiscal_year="2021-22", latest_mentioned=None, **KW)
    assert r.source == "none" and r.doc_date is None and needs_review(r)


def test_review_flags_for_weak_sources():
    for src in ("filename", "wayback_capture"):
        r = resolve([C(src, "2021-08-13")], fiscal_year="2021-22", latest_mentioned=None, **KW)
        assert needs_review(r) and r.reasons
    r = resolve([C("listing", "2021-08-13")], fiscal_year="2021-22", latest_mentioned=None, **KW)
    assert not needs_review(r)


def test_conflict():
    r = resolve([C("listing", "2021-08-13"), C("document_text", "2021-09-30")], fiscal_year=None,
                latest_mentioned=None, **KW)
    assert r.source == "listing" and any(x.startswith("conflict") for x in r.reasons)
    r = resolve([C("listing", "2021-08-13"), C("document_text", "2021-08-15")], fiscal_year=None,
                latest_mentioned=None, **KW)
    assert not r.reasons


def test_anachronism_uses_period_end():
    r = resolve([C("listing", "2021-08-13")], fiscal_year=None, latest_mentioned=C("text_mention", "2021-09-01"), **KW)
    assert any(x.startswith("anachronism") for x in r.reasons)
    r = resolve([C("document_text", "2021-08-01", "month")], fiscal_year=None,
                latest_mentioned=C("text_mention", "2021-08-20"), **KW)
    assert not r.reasons  # within the month


def test_out_of_window_and_fy_mismatch():
    r = resolve([C("listing", "2015-03-01")], fiscal_year=None, latest_mentioned=None, **KW)
    assert any(x.startswith("out of window") for x in r.reasons)
    r = resolve([C("listing", "2022-09-01")], fiscal_year="2021-22", latest_mentioned=None, **KW)
    assert any(x.startswith("FY mismatch") for x in r.reasons)
    r = resolve([C("listing", "2022-06-01")], fiscal_year="2021-22", latest_mentioned=None, **KW)
    assert not r.reasons  # within ± 3 months


def test_fiscal_year_only_stays_null():
    r = resolve([], fiscal_year="2019-20", latest_mentioned=None, **KW)
    assert r.doc_date is None and r.precision is None and "fiscal year only" in r.reasons[0]


def test_latest_mention_ignores_future():
    f = latest_mention("from 01.05.2014 to 30.04.2017, extended to 30.04.2030", TODAY)
    assert f.date == D(2017, 4, 30)


def test_listing_and_wayback_candidates():
    assert listing_candidate({"listing_date": "2021-06-01", "discovery": "listing"}).source == "listing"
    m = listing_candidate({"listing_date": "2021-06-01", "discovery": "manual",
                           "identifiers": {"date_precision": "month"}})
    assert m.source == "manual" and m.precision == "month"
    assert listing_candidate({"listing_date": None}) is None
    assert wayback_candidate({"kept_first_capture": "20170329054014"}).date == "2017-03-29"
    assert wayback_candidate({"url_first_capture": "20170101000000"}) is None  # never the URL's first capture


def test_copyright_year_candidate():
    from ept.corpus.datefind import copyright_year

    for text in ["© Government of Tamil Nadu 2016", "©\n\nTamil Nadu Government \n2024", "© GOVERNMENT OF TAMILNADU 2019"]:
        c = copyright_year(text)
        assert c.kind == "copyright" and c.precision == "year" and c.source == "document_text"
    assert copyright_year("© Government of Tamil Nadu 2016").date == "2016-01-01"
    assert copyright_year("POLICY NOTE 2016-2017 DEMAND NO. 31") is None


def _cr(year):
    return Candidate("document_text", f"{year}-01-01", "year", "© Government of Tamil Nadu", kind="copyright")


def test_copyright_ranks_after_wayback():
    r = resolve([_cr(2016), C("wayback_capture", "2017-07-22")], fiscal_year="2016-17", latest_mentioned=None, **KW)
    assert r.source == "wayback_capture"
    r = resolve([_cr(2016)], fiscal_year="2016-17", latest_mentioned=None, **KW)
    assert r.source == "document_text" and r.precision == "year" and r.doc_date == D(2016, 1, 1)
    assert needs_review(r) and "© year" in r.reasons[0]
    # the © candidate never creates a "conflict" with day-precision sources
    r = resolve([C("listing", "2016-08-01"), _cr(2016)], fiscal_year="2016-17", latest_mentioned=None, **KW)
    assert r.source == "listing" and not r.reasons


def test_copyright_leak_guards():
    # stale template year: earlier than the fiscal year -> not used
    r = resolve([_cr(2016)], fiscal_year="2017-18", latest_mentioned=None, **KW)
    assert r.source == "none" and any("not used: earlier than fiscal year" in x for x in r.reasons)
    # text mentions a date after 31 Dec of the © year -> not used
    r = resolve([_cr(2016)], fiscal_year="2016-17", latest_mentioned=C("text_mention", "2017-02-01"), **KW)
    assert r.source == "none" and any("not used: text mentions later date" in x for x in r.reasons)
    r = resolve([_cr(2016)], fiscal_year="2016-17", latest_mentioned=C("text_mention", "2016-12-31"), **KW)
    assert r.source == "document_text"


def test_dated_keyword_beats_assembly_mention():
    text = ("Schemes - Announcement made on the Floor of the Legislative Assembly on 19.10.2022 - Orders - Issued.\n"
            "G.O. (Ms) No.132 Dated: 06.12.2022\nRead: letter dated 04.11.2022")
    assert issue_date_from_text(text).date == "2022-12-06"
