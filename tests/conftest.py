"""Shared test setup."""
import pytest


@pytest.fixture(autouse=True)
def _default_news_calendar():
    """Coverage gap 1: every run selects its own news calendar (Params.news_cal), but direct calendar calls read the source the last
    run left in force - start every test from the default source so results never depend on test order."""
    from mentorship import calendar as C
    C.use("csv")
    yield


# Test modules written against the pre-card engine defaults (tests/_legacy.py): their `Params` is LegacyParams.
LEGACY_MODULES: set[str] = set()
import os as _os
LEGACY_MODULES |= {m for m in _os.environ.get("MENTORSHIP_LEGACY_MODULES", "").split(",") if m}     # diagnostic reruns


@pytest.fixture(autouse=True)
def _legacy_defaults(request, monkeypatch):
    mod = request.module
    if mod.__name__.rsplit(".", 1)[-1] in LEGACY_MODULES and hasattr(mod, "Params"):
        from _legacy import LegacyParams
        monkeypatch.setattr(mod, "Params", LegacyParams)
    yield
