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


import importlib.abc as _iabc
import sys as _sys


class _TestModuleLoader(_iabc.Loader):
    """Runs a test module with strategy.Params = LegacyParams when it is a legacy module and the real Params otherwise, whoever imports
    it first (pytest's collection or another test module's helper import), so its `from mentorship.strategy import Params`, its own
    `class Params(Params)` and its module-level Params(...) constants get the right defaults in any run order or subset."""

    def __init__(self, inner, legacy: bool):
        self.inner, self.legacy = inner, legacy

    def create_module(self, spec):
        return self.inner.create_module(spec)

    def exec_module(self, module):
        _preload()
        from mentorship import strategy
        from _legacy import LegacyParams
        prev = strategy.Params
        strategy.Params = LegacyParams if self.legacy else LegacyParams.__mro__[1]
        try:
            self.inner.exec_module(module)
        finally:
            strategy.Params = prev

    def __getattr__(self, name):
        return getattr(self.inner, name)


class _TestModuleFinder(_iabc.MetaPathFinder):
    def find_spec(self, name, path, target=None):
        if "." in name or not name.startswith("test_"):
            return None
        for f in _sys.meta_path:                             # the next finder (pytest's assertion rewriter, then the path finder)
            if f is self or not hasattr(f, "find_spec"):
                continue
            spec = f.find_spec(name, path, target)
            if spec is not None:
                if spec.loader is not None:
                    spec.loader = _TestModuleLoader(spec.loader, name in LEGACY_MODULES)
                return spec
        return None


def pytest_configure(config):
    if not any(isinstance(f, _TestModuleFinder) for f in _sys.meta_path):
        _sys.meta_path.insert(0, _TestModuleFinder())


@pytest.fixture(autouse=True)
def _legacy_defaults(request, monkeypatch):
    mod = request.module
    from _legacy import LegacyParams
    legacy = mod.__name__.rsplit(".", 1)[-1] in LEGACY_MODULES
    if isinstance(getattr(mod, "Params", None), type):
        assert issubclass(mod.Params, LegacyParams) == legacy, f"{mod.__name__}: Params {'is not' if legacy else 'is'} the legacy one"
    if legacy:
        import sys
        from mentorship.strategy import Params
        for m in [mod] + list(sys.modules.values()):          # (test helper modules and the engine's own imports)
            if getattr(m, "Params", None) is Params:
                monkeypatch.setattr(m, "Params", LegacyParams)
    yield
