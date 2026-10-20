import datetime as dt

from ept.config import get_config
from ept.dates import (
    add_months, fiscal_year_of, fiscal_years_between, fy_bounds, month_in_term, normalize_fy, period_end,
    period_start,
)

D = dt.date


def test_period_end_day_month_year():
    assert period_end(D(2021, 6, 15), "day") == D(2021, 6, 15)
    assert period_end(D(2021, 6, 1), "month") == D(2021, 6, 30)
    assert period_end(D(2021, 12, 1), "month") == D(2021, 12, 31)
    assert period_end(D(2020, 2, 1), "month") == D(2020, 2, 29)
    assert period_end(D(2021, 2, 1), "month") == D(2021, 2, 28)
    assert period_end(D(2021, 1, 1), "year") == D(2021, 12, 31)
    assert period_end("2021-03-01", "month") == D(2021, 3, 31)
    assert period_start(D(2021, 6, 15), "month") == D(2021, 6, 1)


def test_month_in_term(root):
    term = get_config().term("DMK-2021")  # sworn in 2021-05-07
    assert month_in_term(D(2021, 5, 7), term) == 0
    assert month_in_term(D(2021, 6, 6), term) == 0
    assert month_in_term(D(2021, 6, 7), term) == 1
    assert month_in_term(D(2022, 5, 7), term) == 12
    assert month_in_term(D(2026, 5, 9), term) == 60
    assert month_in_term(D(2021, 5, 1), term) == 0 - 0  # same month, earlier day: floor toward start
    assert month_in_term(D(2021, 4, 7), term) == -1


def test_add_months():
    assert add_months(D(2021, 1, 31), 1) == D(2021, 2, 28)
    assert add_months(D(2021, 11, 15), 3) == D(2022, 2, 15)
    assert add_months(D(2021, 3, 15), -3) == D(2020, 12, 15)


def test_fiscal_years():
    assert fiscal_year_of(D(2021, 3, 31)) == "2020-21"
    assert fiscal_year_of(D(2021, 4, 1)) == "2021-22"
    assert fiscal_year_of(D(1999, 12, 1)) == "1999-00"
    assert normalize_fy("2021-2022") == "2021-22"
    assert normalize_fy("pn_2021_22.pdf") == "2021-22"
    assert normalize_fy("2021-23") is None
    assert normalize_fy("nothing") is None
    assert fy_bounds("2021-22") == (D(2021, 4, 1), D(2022, 3, 31))
    assert fiscal_years_between(D(2016, 5, 1), D(2018, 4, 2)) == ["2016-17", "2017-18", "2018-19"]


# --- spec 04 §4.2: available_by (D-077) ---

def _ab(doc_date, precision, doc_type, fy=None, title=None):
    from ept.dates import available_by

    return available_by(doc_date, precision, doc_type, fy, title)


def test_available_by_precisions(root):
    assert _ab("2021-06-15", "day", "go") == D(2021, 6, 15)
    assert _ab("2021-06-01", "month", "go") == D(2021, 6, 30)
    assert _ab("2021-01-01", "year", "scheme_page") == D(2021, 12, 31)


def test_available_by_fiscal_year_bound(root):
    # policy note with a late Wayback date -> fiscal-year end
    assert _ab("2022-05-17", "day", "policy_note", "2021-22") == D(2022, 3, 31)
    # undated policy note -> fiscal-year end
    assert _ab(None, None, "policy_note", "2021-22") == D(2022, 3, 31)
    # a strong date earlier than the FY end is kept (min never moves a date later)
    assert _ab("2021-08-24", "day", "policy_note", "2021-22") == D(2021, 8, 24)
    # © year: period_end 2021-12-31 is before the FY end 2022-03-31
    assert _ab("2021-01-01", "year", "policy_note", "2021-22") == D(2021, 12, 31)
    assert _ab("2023-01-01", "day", "budget_speech", "2021-22") == D(2022, 3, 31)
    # performance budget by title prefix (case-insensitive)
    assert _ab("2021-12-28", "day", "other", "2020-21", "Performance budget of Sericulture-2020-21") == D(2021, 3, 31)
    assert _ab(None, None, "other", "2020-21", "PERFORMANCE BUDGET of X") == D(2021, 3, 31)


def test_available_by_not_tightened(root):
    # state policy (other, no prefix), CAG report and GO keep their own date
    assert _ab("2022-05-17", "day", "other", "2021-22", "Tamil Nadu Data Centre Policy - 2021") == D(2022, 5, 17)
    assert _ab("2024-05-17", "day", "cag_report", "2021-22") == D(2024, 5, 17)
    assert _ab("2022-05-17", "day", "go", "2021-22") == D(2022, 5, 17)
    assert _ab("2022-05-17", "day", "governor_address", "2021-22") == D(2022, 5, 17)
    # undated without a fiscal-year bound -> None
    assert _ab(None, None, "cag_report", "2021-22") is None
    assert _ab(None, None, "policy_note", None) is None
    assert _ab(None, None, "other", None, "Performance Budget of X") is None


def test_availability_basis(root):
    from ept.dates import BASIS_FY_ONLY, BASIS_FY_TIGHTENED, BASIS_STORED, availability

    assert availability("2022-05-17", "day", "policy_note", "2021-22", None)[1] == BASIS_FY_TIGHTENED
    assert availability(None, None, "policy_note", "2021-22", None)[1] == BASIS_FY_ONLY
    assert availability("2021-08-24", "day", "policy_note", "2021-22", None)[1] == BASIS_STORED
    assert availability("2022-03-31", "day", "policy_note", "2021-22", None) == (D(2022, 3, 31), BASIS_STORED)
    assert availability(None, None, "go", None, None) == (None, None)
