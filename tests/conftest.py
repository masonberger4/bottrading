"""Shared test setup."""
import pytest


@pytest.fixture(autouse=True)
def _default_news_calendar():
    """Coverage gap 1: every run selects its own news calendar (Params.news_cal), but direct calendar calls read the source the last
    run left in force - start every test from the default source so results never depend on test order."""
    from mentorship import calendar as C
    C.use("csv")
    yield
