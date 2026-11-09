"""Shared test setup."""
import pytest


@pytest.fixture(autouse=True)
def _default_news_calendar():
    """Coverage gap 1: every run selects its own news calendar (Params.news_cal), but direct calendar calls read the source the last
    run left in force - start every test from the default source so results never depend on test order."""
    from mentorship import calendar as C
    C.use("csv")
    yield


# Test modules written against the pre-card engine defaults (tests/_legacy.py): their `Params` is LegacyParams,
# and so is every other loaded module's (test helpers, and a default `Params()` built inside the engine or study).
LEGACY_MODULES: set[str] = {
    "test_bias_htf", "test_caption_gap_bh1", "test_caption_gap_bh1d", "test_caption_gap_bh1f", "test_caption_gap_bh2",
    "test_caption_gap_bh2b", "test_caption_gap_bh2c", "test_caption_gap_bh3", "test_caption_gap_bh3c", "test_caption_gap_bh4c",
    "test_caption_gap_bh5", "test_caption_gap_bh5b", "test_caption_gap_bh6b", "test_caption_gap_bh7", "test_caption_gap_bh7b",
    "test_caption_gap_dwc1", "test_caption_gap_dwc2", "test_caption_gap_dwc3", "test_caption_gap_es1a", "test_caption_gap_es1b",
    "test_caption_gap_es1c", "test_caption_gap_es2a", "test_caption_gap_es2b", "test_caption_gap_es2c", "test_caption_gap_es3a",
    "test_caption_gap_es3b", "test_caption_gap_ld1", "test_caption_gap_ld1_review", "test_caption_gap_ld2",
    "test_caption_gap_ld2_review", "test_caption_gap_ld3", "test_caption_gap_ld3_review", "test_caption_gap_me1a",
    "test_caption_gap_me1a2", "test_caption_gap_me1a3", "test_caption_gap_me1b", "test_caption_gap_me1c", "test_caption_gap_me2d",
    "test_caption_gap_me2e", "test_caption_gap_me3b", "test_caption_gap_me3c", "test_caption_gap_me3d", "test_caption_gap_nct1",
    "test_caption_gap_sb1", "test_caption_gap_sm1a", "test_caption_gap_sm1b", "test_caption_gap_sm1c", "test_caption_gap_sm2a",
    "test_caption_gap_sm2b", "test_caption_gap_sm3a", "test_caption_gap_sm3b", "test_caption_gap_sm4a", "test_caption_gap_sm4b",
    "test_caption_gap_sm4c", "test_caption_gap_sm5b", "test_caption_gap_sm6a", "test_caption_gap_sm6b", "test_caption_gap_sm6c",
    "test_caption_gap_sm7a", "test_caption_gap_sm7b", "test_caption_gap_tp1a", "test_caption_gap_tp1b", "test_caption_gap_tp2b",
    "test_caption_gap_tp3a", "test_caption_gap_tp3b", "test_caption_gap_tp4a", "test_caption_gap_tp4b", "test_day_week_context",
    "test_day_week_scenarios", "test_entries_stops", "test_levels_detectors", "test_levels_review", "test_management_exits",
    "test_mentorship", "test_news_calendar", "test_owner_answers_oa1029", "test_owner_directives", "test_review_fixes",
    "test_setups_models", "test_silver_bullet", "test_targets_partials",
}
import os as _os
LEGACY_MODULES |= {m for m in _os.environ.get("MENTORSHIP_LEGACY_MODULES", "").split(",") if m}     # diagnostic reruns


_PRELOADED = []


def _preload():
    """Import every engine module once with the real Params first, so none binds LegacyParams (or builds a table such as
    study.DECISIONS from the old defaults) because a legacy test module happened to import it first."""
    if _PRELOADED:
        return
    _PRELOADED.append(1)
    import importlib
    import pkgutil
    import mentorship
    for m in pkgutil.walk_packages(mentorship.__path__, "mentorship."):
        if m.name.endswith("__main__"):
            continue
        try:
            importlib.import_module(m.name)
        except Exception:
            pass


@pytest.hookimpl(hookwrapper=True)
def pytest_make_collect_report(collector):
    """A legacy module is imported with strategy.Params = LegacyParams, so its `from mentorship.strategy import Params` and its
    module-level Params(...) constants (and the helper modules it imports first) get the old defaults."""
    if not (isinstance(collector, pytest.Module) and collector.path.stem in LEGACY_MODULES):
        yield
        return
    _preload()
    from mentorship import strategy
    from _legacy import LegacyParams
    orig = strategy.Params
    strategy.Params = LegacyParams
    try:
        yield
    finally:
        strategy.Params = orig


@pytest.fixture(autouse=True)
def _legacy_defaults(request, monkeypatch):
    mod = request.module
    if mod.__name__.rsplit(".", 1)[-1] in LEGACY_MODULES:
        import sys
        from _legacy import LegacyParams
        from mentorship.strategy import Params
        for m in [mod] + list(sys.modules.values()):          # (test helper modules and the engine's own imports)
            if getattr(m, "Params", None) is Params:
                monkeypatch.setattr(m, "Params", LegacyParams)
    yield
