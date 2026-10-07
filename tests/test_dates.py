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
