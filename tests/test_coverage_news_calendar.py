"""Coverage gap 1 (coverage_build_2026-10-31 package 1): the news calendar from macro_risk_dates.csv (Params.news_cal)."""
import os
from datetime import date

import pytest

from mentorship import calendar as C, study
from mentorship.strategy import Params

CSV = os.path.isfile(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), C.CSV_DEFAULT))
pytestmark = pytest.mark.skipif(not CSV, reason="no data/mentorship/macro_risk_dates.csv")


@pytest.fixture(autouse=True)
def _restore():
    yield
    C.use("csv")


def test_defaults_and_validation():
    p = Params()
    assert (p.news_cal, p.news_cal_path, p.gdp_tags) == ("csv", "data/mentorship/macro_risk_dates.csv", ("gdp_adv",))
    for kw in (dict(news_cal="x"), dict(gdp_tags=("gdp_x",))):
        with pytest.raises(ValueError):
            Params(**kw)
    assert study.PRE_OWNER["news_cal"] == "legacy" and study.CURRENT["news_cal"] == "legacy"
    assert study.DECISIONS["NEWS-legacy"] == {"news_cal": "legacy"}


def test_spec_dates_csv():
    assert C.use("csv") == "csv"
    ev = C.events
    assert "fomc" in ev(date(2016, 12, 14)) and "jobs" in ev(date(2017, 6, 2))
    assert "gdp" in ev(date(2018, 10, 26)) and "gdp" not in ev(date(2018, 10, 25))
    assert "pce" in ev(date(2019, 3, 1)) and "pce" not in ev(date(2019, 2, 19))
    assert {"pce", "gdp"} <= ev(date(2026, 7, 30)) and "pce" not in ev(date(2026, 8, 4))       # the claude_hf 2026 PCE list is wrong after April
    assert "ppi" in ev(date(2017, 6, 14)) or any("ppi" in ev(date(2017, 6, k)) for k in range(1, 31))   # PPI 2016-2018 from the file
    assert "ppi" in ev(date(2023, 5, 11))                                            # ... and the built 2019+ list


def test_holidays_and_elections():
    assert not C.is_trading_day(date(2018, 12, 5))                                   # the Bush mourning closure
    assert C.next_trading_day(date(2016, 11, 23)) == date(2016, 11, 25)
    assert not C.is_trading_day(date(2017, 4, 14)) and C.is_trading_day(date(2017, 4, 13))
    assert date(2016, 11, 8) in C.ELECTIONS


def test_release_times_use_the_row_time():
    C.use("csv")
    assert 600 in C.release_times(date(2019, 11, 27)) and 600 in C.release_times(date(2024, 11, 27))   # PCE at 10:00 on those dates
    assert C.release_times(date(2016, 12, 14))[-1] == 840


def test_gdp_tags_switch():
    C.use("csv", gdp_tags=("gdp_adv",))
    adv = {d for d in C.EV["gdp"]}
    C.use("csv", gdp_tags=("gdp_adv", "gdp_2nd", "gdp_3rd", "gdp_other"))
    assert adv < C.EV["gdp"]


def test_legacy_is_the_built_calendar_and_claude_hf_untouched():
    from claude_hf import daytypes as DT
    C.use("csv")
    assert date(2016, 12, 14) not in DT.FOMC and date(2026, 8, 4) in DT.PCE          # the claude_hf sets are never rewritten
    C.use("legacy")
    assert "fomc" not in C.events(date(2016, 12, 14))
    assert C.events(date(2023, 3, 22)) == DT.events(date(2023, 3, 22))
    for d in (date(2021, 6, 4), date(2022, 9, 13), date(2026, 8, 4)):
        assert C.events(d) == DT.events(d)


def test_run_selects_the_calendar_per_params():
    from mentorship import strategy as S
    C.use("legacy")
    import inspect
    assert "_calendar.use(p.news_cal" in inspect.getsource(S.run_day)
    C.use(Params().news_cal)
    assert C.source() == "csv"


def test_membership_reads_no_row_after_the_date():
    """No look-ahead: event membership and release times depend only on the date - the result for d is the same when the file's rows after d are removed."""
    import csv
    import tempfile
    rows = [l for l in open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), C.CSV_DEFAULT), encoding="utf8") if not l.startswith("#")]
    cut = date(2020, 6, 30)
    head, body = rows[0], [r for r in rows[1:] if date.fromisoformat(r.split(",")[0]) <= cut]
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf8") as f:
        f.write(head + "".join(body))
    try:
        days = [date(2020, 1, 2) + __import__("datetime").timedelta(days=k) for k in range(180)]
        C.use("csv")
        full = [(C.events(d) - {"opex", "quad_witching"}, C.release_times(d)) for d in days]
        C.load_csv.cache_clear()
        C.use("csv", path=f.name)
        part = [(C.events(d) - {"opex", "quad_witching"}, C.release_times(d)) for d in days]
        assert full == part
    finally:
        os.unlink(f.name)
        C.load_csv.cache_clear()
