"""The engine defaults from before the scorecard cards (Mase 2026-11-08, mentorship/cards.py).

Many unit tests were written against those defaults: they check one switch's behaviour on the old baseline.
Modules listed in conftest.LEGACY_MODULES see `Params` as LegacyParams, which is Params with these
values as its defaults (any keyword a test passes still wins). The card defaults themselves are tested in
tests/test_cards.py and by the variant look-ahead tests.
"""
from mentorship.strategy import Params

LEGACY = dict(
    entry="edge", stop_mode="ob_mt", mss_mode="close", breaker_zone="range", fomc_pm_from=885,
    reentry_half=False, reentry_risk_mult=0.5, org_close=0, pre_0700=False, ipda_pools=False, or_extra=False,
    resistance_mode="off", pre_cpi="off", news_judas="off", skip_holiday_eve=False, big_day_am_skip=False,
    big_day_am_resume=0, week_done_on_draw="off", ob_pick="blend", ndog_scalp=False, asia_session=False,
    lunch_macro_entry=False, hold_through_0830=True, thu_cap=False, pm_macro_runner=False, lunch_raid="off",
    holiday_week_skip=False, smt_ym=True, lunch_range=(720, 810), macro_grid="fixed", season_quality="off",
)


class LegacyParams(Params):
    """Params with the pre-card defaults (no @dataclass: the fields, __post_init__ and replace() are Params')."""

    def __init__(self, **kw):
        super().__init__(**{**LEGACY, **kw})
