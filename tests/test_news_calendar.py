"""Package news_calendar_times (rule_coverage.md section 3, 31 items): unit tests for the calendar and the
newscal helpers, one-day scenarios through run_day (the real engine path) and no-look-ahead runs (full vs
truncated) covering every new switch. The ES tests skip when the data is missing."""
import warnings
from dataclasses import fields, replace
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from claude_hf import daytypes as DT
from mentorship import backtest as B, calendar as C, manage as MG, newscal as NC, strategy as S, study
from mentorship.strategy import Params

from test_review_fixes import A_LOCK, A_ROWS, BASE, D0, day, history  # noqa: E402  (shared scenario builders)
from test_entries_stops import _no_look_ahead  # noqa: E402

ES = Path("data/mentorship/ES_5min_db.csv").exists()
FUT = dict(es_pt=1.0, lot=1, max_notional=1e12, cost_per_share=0.1)
SYN = dict(es_pt=0.09, use_bias=False, min_draw_pts=0, leg_pd=0)
HOLD = A_ROWS[:5]                                    # sweep, MSS, order armed 09:45, filled 09:50, no run


def find_day(pred, start=date(2023, 1, 3), end=date(2026, 12, 31)):
    d = start
    while d <= end:
        if C.is_trading_day(d) and pred(d):
            return d
        d += timedelta(days=1)
    raise AssertionError("no such day")


FOMC_ONLY = date(2026, 4, 29)                        # FOMC, no other release
EVE = date(2026, 4, 28)                              # the day before it
AFTER = find_day(lambda d: C.fomc_info(d)["after"] and C.release_times(d) == [], date(2026, 1, 1))
NFP_ONLY = find_day(lambda d: "jobs" in DT.events(d) and C.release_times(d) == [510], date(2026, 5, 1))
TWO_DRV = date(2026, 4, 10)                          # CPI 08:30 + sentiment 10:00
CPI_EVE = date(2026, 4, 9)                           # PCE 08:30 day, the day before CPI
NORMAL = D0                                          # a Tuesday: no release, no NFP / FOMC week


def go(d, rows=A_ROWS, start="09:30", sym="ES", tail=None, bias=None, hist=None, **kw):
    p = Params(**{**BASE, **kw})
    locks, log, skips = [], [], []
    return S.run_day(day(rows, d=d, start=start, spike=True, tail=tail), hist or history(d), sym, p, 5, locks=locks,
                     log=log, skips=skips, bias_by_cut=A_LOCK, bias=bias)


def ctx_for(rows, d=NORMAL, start="09:30", **kw):
    ctx = S.DayCtx(day(rows, d=d, start=start, **kw), d, history(d), 5)
    ctx.hist = history(d)
    ctx.lock = {}
    return ctx


# --- defaults and validation -------------------------------------------------------------------------------

NEW_FIELDS = (
    "news_claims", "news_minutes", "news_conf_board", "wait_0945", "nfp_first_hour", "nfp_day_from", "fomc_flat", "fomc_flat_before", "fomc_am", "fomc_only_am",
    "fomc_eve_risk", "pre_fomc_risk", "skip_pre_fomc", "fomc_after_am_block", "skip_post_fomc_am", "fomc_no_reentry",
    "fomc_observe", "fomc_pm_block_from", "sb_fomc_pm", "fomc_whipsaw_skip_london", "fomc_judas", "fomc_judas_end", "fomc_stage2_cont", "pre_cpi",
    "pre_cpi_risk", "skip_pre_cpi", "flat_0830_extras", "skip_two_drivers", "two_driver_gate", "fed_chair_skip_am", "skip_auction_am",
    "news_judas", "news_judas_ref_min", "or_no_entry", "or_end", "or_no_entry_news1000", "or_deep", "or_deep_win",
    "or_deep_pd", "or_bias", "or_bias_filter", "or_wide", "or_wide_adr", "or_wide_end", "pre_0820", "am_from_0830",
    "ny_kz_futures", "london_kz", "london_kz_start", "lunch", "lunch_win", "lunch_exit", "pm_carry_draw",
    "draw_done_skip", "pm_skip_after", "pm_skip_lh", "pm_bad_am_start", "pm_continue_am", "pm_ob_entry", "macro_gate",
    "macro_only", "macro_by", "macro_done_skip", "moc_htf_done", "run_done_adr")
# tuning knobs of another switch (the study variant of the main switch uses them)
KNOBS = {"fomc_judas_end", "news_judas_ref_min", "or_end", "or_deep_win", "or_deep_pd", "or_bias_filter", "or_wide_adr",
         "or_wide_end", "london_kz_start", "lunch_win", "lunch_exit", "pm_skip_lh", "macro_by", "run_done_adr",
         "pre_cpi_risk", "pre_fomc_risk"}
# default-on switches / the old build as a preset: covered by their own tests
DEFAULT_ON = {"wait_0945", "nfp_first_hour", "fomc_flat", "fomc_no_reentry", "two_driver_gate", "fed_chair_skip_am",
              "flat_0830_extras"}


def test_defaults_and_validation():
    p = Params()
    assert (p.nfp_first_hour, p.fomc_flat, p.fomc_no_reentry, p.fed_chair_skip_am, p.two_driver_gate, p.wait_0945) == \
        (True, 840, True, False, True, True)
    assert p.fomc_am == "open" and p.fomc_only_am == "off" and p.pre_cpi == "off" and p.fomc_observe == "off"
    assert p.news_judas == "off" and p.macro_only == "off" and p.pm_continue_am == "off" and p.pm_ob_entry == "off"
    assert p.fomc_judas_end == 870                                     # M9.2: 14:30 (no source for 14:25)
    assert p.am_win == (570, 660) and Params(am_from_0830=True).am_win == (510, 660)
    for kw in (dict(fomc_am="x"), dict(fomc_only_am="x"), dict(fomc_observe="x"), dict(pre_cpi="x"), dict(news_judas="x"),
               dict(or_bias="x"), dict(pm_continue_am="x"), dict(pm_ob_entry="x"), dict(macro_only="x"), dict(macro_by="x"),
               dict(fomc_eve_risk=0.0), dict(pre_cpi_risk=-1.0), dict(news_judas_ref_min=0), dict(lunch_win=(800, 700)),
               dict(or_deep_win=(1,))):
        with pytest.raises(ValueError):
            Params(**kw)
    with pytest.raises(ValueError):
        Params(lunch=True, lunch_win=(600, 810))                        # the lunch session must start after the AM
    names = {f.name for f in fields(Params)}
    assert set(NEW_FIELDS) <= names


def test_every_new_switch_has_a_study_variant():
    used = set()
    for k, v in study.DECISIONS.items():
        replace(Params(), **v)                                         # every variant builds
        used |= set(v)
    missing = [f for f in NEW_FIELDS if f not in used and f not in KNOBS]
    assert not missing, missing
    # the old build pins the new defaults back
    for preset in (study.CURRENT, study.PRE_OWNER):
        assert preset["fomc_no_reentry"] is False and preset["nfp_first_hour"] is False
        assert preset["fed_chair_skip_am"] is False and preset["fomc_flat"] == 0 and preset["flat_0830_extras"] is False


# --- the calendar --------------------------------------------------------------------------------------------

def test_nfp_date_helpers():
    assert C.nfp_date(date(2025, 7, 1)) == date(2025, 7, 3)           # a Thursday (Friday was the 4th)
    assert C.nfp_shift(date(2025, 7, 2)) == 1
    assert C.nfp_shift(date(2025, 6, 4)) == 0                          # the 2025-06-06 Friday
    assert C.nfp_date(date(2025, 7, 9)) is None and C.nfp_shift(date(2025, 7, 9)) == -1
    assert C.nfp_shift(date(2025, 12, 15)) == -1                       # 2025-12-16, a shutdown-shifted Tuesday


def test_blocked_is_relative_to_the_real_jobs_date():
    p = Params(nfp_week_block=True)
    # Friday NFP week (2025-06-06): exactly the old rules - Wed PM, Thu, Fri
    assert S.blocked(date(2025, 6, 4), "PM", p) == "nfp_week_wed_pm" and S.blocked(date(2025, 6, 4), "AM", p) is None
    assert S.blocked(date(2025, 6, 5), "AM", replace(p, nfp_thu=False)) == "nfp_week_thu_fri"
    assert S.blocked(date(2025, 6, 5), "AM", p) is None                # nfp_thu=True trades the Thursday
    assert S.blocked(date(2025, 6, 2), "PM", p) is None                # Monday is always a trading day
    # Thursday NFP (2025-07-03): the day before is the Wednesday, Tuesday PM is two days before
    assert S.blocked(date(2025, 7, 2), "AM", replace(p, nfp_thu=False)) == "nfp_week_thu_fri"
    assert S.blocked(date(2025, 7, 2), "AM", p) is None
    assert S.blocked(date(2025, 7, 1), "PM", p) == "nfp_week_wed_pm" and S.blocked(date(2025, 7, 1), "AM", p) is None
    assert S.blocked(date(2025, 7, 3), "AM", replace(p, nfp_day=False)) == "nfp_day"
    assert S.blocked(date(2025, 7, 3), "AM", p) is None
    # the old code blocked the Wednesday PM of this week's Thursday NFP as an ordinary day - it is unblocked now
    assert S.blocked(date(2025, 7, 2), "PM", p) is None
    # off by default
    assert S.blocked(date(2025, 6, 4), "PM", Params()) is None and S.blocked(date(2025, 6, 4), "PM") == "nfp_week_wed_pm"
    # a shutdown-shifted Tuesday NFP has no week block (Monday stays a trading day)
    assert S.blocked(date(2025, 12, 15), "AM", replace(p, nfp_thu=False)) is None


def test_jobless_claims_and_fomc_minutes():
    assert C.is_jobless_claims(date(2025, 3, 6)) and not C.is_jobless_claims(date(2025, 3, 7))
    assert C.is_jobless_claims(date(2025, 11, 26)) and not C.is_jobless_claims(date(2025, 11, 27))   # Thanksgiving -> Wed
    assert C.is_jobless_claims(date(2025, 6, 18)) and not C.is_jobless_claims(date(2025, 6, 19))     # Juneteenth -> Wed
    assert C.is_jobless_claims(date(2025, 7, 3))                                                      # 07-04 is a Friday
    assert not C.is_jobless_claims(date(2025, 3, 5))
    assert date(2025, 2, 19) in C.FOMC_MINUTES and date(2025, 1, 8) in C.FOMC_MINUTES
    assert date(2020, 3, 24) not in C.FOMC_MINUTES                                                    # the emergency cut
    assert C.minor_events(date(2025, 2, 19)) == {"minutes"} and C.minor_events(date(2025, 2, 20)) == {"claims"}


def test_release_times_flags():
    d = date(2026, 6, 4)                                               # a Thursday: claims only
    assert C.release_times(d) == [] and C.release_times(d, claims=True) == [510]
    m = date(2026, 2, 18)                                              # 2026-01-28 + 21 days
    assert m in C.FOMC_MINUTES and C.release_times(m) == [] and C.release_times(m, minutes=True) == [840]
    assert C.release_times(date(2026, 6, 1), pmi=False) == [600]       # wait_0945=False drops the 09:45 PMI
    assert C.release_times(date(2026, 6, 1)) == [585, 600] and C.PMI == {"pmi_mfg", "pmi_svc"}
    assert NC.releases(d, Params(news_claims=True)) == [510] and NC.releases(d, Params()) == []
    assert NC.releases(date(2026, 6, 1), Params(wait_0945=False)) == [600]


def test_fomc_info_and_eve_helpers():
    assert C.fomc_info(FOMC_ONLY) == dict(fomc=True, eve=False, after=False, only=True)
    assert C.fomc_info(EVE)["eve"] and C.fomc_info(AFTER)["after"]
    assert C.eve_of(CPI_EVE, "cpi") and not C.eve_of(NORMAL, "cpi")
    assert C.eve_of(date(2026, 4, 2), "jobs") is False                 # the 04-03 holiday jobs release: 04-06 is next
    assert C.two_drivers(TWO_DRV) and not C.two_drivers(NFP_ONLY) and not C.two_drivers(FOMC_ONLY)
    assert C.two_drivers(date(2026, 6, 1)) is False                    # PMI 09:45 + ISM 10:00 are one driver
    assert C.two_drivers(date(2026, 4, 1))                              # retail sales 08:30 + ISM / PMI
    assert C.is_auction_day(date(2026, 4, 8)) and C.is_auction_day(date(2026, 4, 7)) and not C.is_auction_day(date(2026, 4, 6))
    assert not C.is_auction_day(date(2026, 4, 11))
    assert date(2025, 2, 11) in C.FED_CHAIR


# --- the day rules (blocked -> newscal.calendar_block) ---------------------------------------------------------

def test_calendar_block_rules():
    P = lambda **kw: Params(**kw)
    assert S.blocked(FOMC_ONLY, "AM", P()) is None and S.blocked(FOMC_ONLY, "PM", P()) == "fomc_pm"
    assert S.blocked(FOMC_ONLY, "AM", P(fomc_am="skip")) == "fomc_am_skip"
    assert S.blocked(FOMC_ONLY, "PRE9", P(fomc_am="skip")) == "fomc_am_skip" and S.blocked(FOMC_ONLY, "PM", P(fomc_am="skip")) == "fomc_pm"
    assert S.blocked(FOMC_ONLY, "AM", P(fomc_only_am="skip")) == "fomc_only_am_skip"
    assert S.blocked(FOMC_ONLY, "AM", P(fomc_only_am="scalp")) is None
    fo2 = find_day(lambda d: "fomc" in DT.events(d) and C.release_times(d) != [840], date(2023, 1, 3))
    assert S.blocked(fo2, "AM", P(fomc_only_am="skip")) is None        # not an FOMC-only day
    assert S.blocked(AFTER, "AM", P()) is None
    assert S.blocked(AFTER, "AM", P(skip_post_fomc_am=True)) == "post_fomc_am"
    assert S.blocked(AFTER, "AM", P(fomc_after_am_block=True)) == "post_fomc_am"
    assert S.blocked(AFTER, "PM", P(fomc_after_am_block=True)) is None
    assert S.blocked(EVE, "AM", P(skip_pre_fomc=True)) == "pre_fomc" and S.blocked(EVE, "PM", P(skip_pre_fomc=True)) == "pre_fomc"
    assert S.blocked(CPI_EVE, "AM", P(pre_cpi="skip")) == "pre_cpi" and S.blocked(CPI_EVE, "AM", P(skip_pre_cpi=True)) == "pre_cpi"
    assert S.blocked(CPI_EVE, "AM", P(pre_cpi="small")) is None and S.blocked(CPI_EVE, "AM", P()) is None
    ch = date(2025, 2, 11)
    assert S.blocked(ch, "AM", P(fed_chair_skip_am=True)) == "fed_chair" and S.blocked(ch, "PM", P(fed_chair_skip_am=True)) is None
    assert S.blocked(ch, "AM", P()) is None                            # default OFF (unverified calendar)
    assert S.blocked(ch, "LON", P(fed_chair_skip_am=True)) is None     # the day rules cover the NY AM family only
    au = date(2026, 4, 8)
    assert S.blocked(au, "AM", P()) is None and S.blocked(au, "AM", P(skip_auction_am=True)) == "auction_am"
    assert S.blocked(au, "PM", P(skip_auction_am=True)) is None
    assert S.blocked(TWO_DRV, "AM", P(skip_two_drivers=True)) == "two_drivers" and S.blocked(TWO_DRV, "PM", P(skip_two_drivers=True)) is None
    assert S.blocked(NFP_ONLY, "AM", P(nfp_day_from=600), t=570) == "nfp_day_from"
    assert S.blocked(NFP_ONLY, "AM", P(nfp_day_from=600), t=600) is None and S.blocked(NFP_ONLY, "AM", P(), t=570) is None


def test_fomc_pm_windows_in_blocked():
    P = lambda **kw: Params(**kw)
    assert S.blocked(FOMC_ONLY, "PM", P(), t=880) == "fomc_pm" and S.blocked(FOMC_ONLY, "PM", P(), t=885) is None
    # N3.1: trade 13:30-14:00, sit out the release and the observation window
    p = P(fomc_pm_block_from=840)
    assert S.blocked(FOMC_ONLY, "PM", p, t=830) is None and S.blocked(FOMC_ONLY, "PM", p, t=840) == "fomc_pm"
    assert S.blocked(FOMC_ONLY, "PM", p, t=885) is None
    # fomc_observe scans from 14:00 (the order is held, run_day); before it the PM stays out
    p = P(fomc_observe="defer")
    assert S.blocked(FOMC_ONLY, "PM", p, t=830) == "fomc_pm" and S.blocked(FOMC_ONLY, "PM", p, t=845) is None
    # M9.2: the real move starts 14:30 - the PM opens there
    p = P(fomc_judas=True)
    assert S.blocked(FOMC_ONLY, "PM", p, t=865) == "fomc_pm" and S.blocked(FOMC_ONLY, "PM", p, t=870) is None
    assert NC.first_pm_minute(P()) == 885 and NC.first_pm_minute(P(fomc_judas=True)) == 870


def test_day_risk_tags_and_flat():
    assert NC.day_risk(EVE, Params()) == 1.0
    lv = []
    assert NC.day_risk(EVE, Params(fomc_eve_risk=0.5), lv) == 0.5 and lv == ["size_pre_fomc"]
    assert NC.day_risk(EVE, Params(fomc_eve_risk=0.5, pre_fomc_risk=0.5)) == 0.25        # they multiply
    assert NC.day_risk(NORMAL, Params(fomc_eve_risk=0.5)) == 1.0
    assert NC.day_risk(CPI_EVE, Params(pre_cpi="small")) == 0.5 and NC.day_risk(CPI_EVE, Params(pre_cpi="small", pre_cpi_risk=0.3)) == 0.3
    assert NC.day_risk(CPI_EVE, Params(pre_cpi="skip")) == 1.0
    assert NC.fomc_flat_min(FOMC_ONLY, Params()) == 840 and NC.fomc_flat_min(FOMC_ONLY, Params(fomc_flat=0)) == 0
    assert NC.fomc_flat_min(NORMAL, Params()) == 0
    assert NC.fomc_flat_min(FOMC_ONLY, Params(fomc_flat_before=810)) == 810 and NC.fomc_flat_min(FOMC_ONLY, Params(fomc_flat_before=0)) == 0
    assert NC.day_tags(FOMC_ONLY) == "fomc_only" and "fomc_eve" in NC.day_tags(EVE) and "fomc_after" in NC.day_tags(AFTER)
    assert "nfp" in NC.day_tags(NFP_ONLY) and "two_driver" in NC.day_tags(TWO_DRV) and "cpi" in NC.day_tags(TWO_DRV)
    assert "pre_cpi" in NC.day_tags(CPI_EVE) and "fed_chair" in NC.day_tags(date(2025, 2, 11))
    assert "auction" in NC.day_tags(date(2026, 4, 8)) and "claims" in NC.day_tags(date(2026, 6, 4))
    assert NC.day_tags(date(2025, 6, 4)) == "nfp_week"


def _lost(d, win=False, sess="AM"):
    tr = S.Trade(d, "ES", sess, "am_mm", "long", "x", False, None, pd.Timestamp(f"{d} 09:40", tz=B.NY),
                 pd.Timestamp(f"{d} 09:50", tz=B.NY), 100.0, 99.0, 102.0, None, 1)
    tr.exits.append((pd.Timestamp(f"{d} 10:00", tz=B.NY), 102.0 if win else 99.0, 1, "t1" if win else "stop"))
    return tr


def test_fomc_no_reentry_is_a_day_stop_on_fomc_days_only():
    p = Params()
    assert MG.any_stop_switch(p, FOMC_ONLY) and not MG.any_stop_switch(p, NORMAL) and MG.any_stop_switch(p)
    assert not MG.any_stop_switch(Params(fomc_no_reentry=False), FOMC_ONLY)
    assert not MG.any_stop_switch(Params(reentry_fomc_ok=True), FOMC_ONLY)                    # X13b opt-in wins
    assert Params().fomc_day_stop and not Params(reentry_fomc_ok=True).fomc_day_stop
    assert MG.stops_from(p, [_lost(FOMC_ONLY)])[0] == "fomc_loss"
    assert MG.stops_from(p, [_lost(FOMC_ONLY, win=True)])[0] is None
    assert MG.stops_from(p, [_lost(NORMAL)])[0] is None
    assert MG.stops_from(Params(fomc_no_reentry=False), [_lost(FOMC_ONLY)])[0] is None
    # the closed-trades view of the Silver Bullet / Ma Deuce
    ctx = SimpleNamespace(day=FOMC_ONLY, risk_view=dict(trades=[_lost(FOMC_ONLY)], rs0=None))
    ts = pd.Timestamp(f"{FOMC_ONLY} 14:50", tz=B.NY)
    assert MG.extras_blocked(ctx, p, "PM", ts) and not MG.extras_blocked(ctx, Params(fomc_no_reentry=False), "PM", ts)
    done, state = {"AM": False, "PM": False, "SB_PM": False}, {"day": FOMC_ONLY}
    MG.apply_stops([_lost(FOMC_ONLY)], p, done, state)
    assert all(done.values()) and state["day_done"]


# --- the engine: FOMC, CPI, windows ------------------------------------------------------------------------------

def test_fomc_am_options():
    assert len(go(FOMC_ONLY)) == 1                                     # the AM is open by default
    assert go(FOMC_ONLY, fomc_am="skip") == [] and go(FOMC_ONLY, fomc_only_am="skip") == []
    assert go(FOMC_ONLY, fomc_am="recipe") == []                       # no HTF table row: the recipe does not hold
    dec = dict(react=1, draw=1, pd=0)
    assert len(go(FOMC_ONLY, fomc_am="recipe", bias=dec)) == 1
    assert go(FOMC_ONLY, fomc_am="recipe", bias=dict(react=1, draw=-1, pd=0)) == []
    assert go(FOMC_ONLY, fomc_am="recipe", bias=dict(react=0, draw=0, pd=0)) == []
    assert len(go(NORMAL, fomc_am="recipe")) == 1 and len(go(NORMAL, fomc_am="skip")) == 1      # FOMC days only
    # N3.3: the FOMC-only AM as a scalp - one exit, no adds - and the tag
    t = go(FOMC_ONLY, fomc_only_am="scalp")
    assert len(t) == 1 and len(t[0].exits) == 1 and "fomc_only_am" in t[0].lv_tags and t[0].news_tags == "fomc_only"
    base = go(FOMC_ONLY)
    assert len(base[0].exits) > 1 and "fomc_only_am" not in base[0].lv_tags
    assert "fomc_only_am" in go(FOMC_ONLY, fomc_only_am="tag")[0].lv_tags
    assert len(go(FOMC_ONLY, fomc_only_am="tag")[0].exits) > 1


def test_fomc_flat_closes_before_the_release_and_cancels_orders():
    t = go(FOMC_ONLY, HOLD, am_exit=0, tail=100.4)
    assert len(t) == 1 and t[0].exits[-1][3] == "fomc_flat" and str(t[0].exits[-1][0])[11:16] == "13:55"
    t = go(FOMC_ONLY, HOLD, am_exit=0, tail=100.4, fomc_flat=0)
    assert t[0].exits[-1][3] == "eod"
    t = go(NORMAL, HOLD, am_exit=0, tail=100.4)
    assert t[0].exits[-1][3] == "eod"


def test_eve_risk_and_pre_cpi():
    a, b = go(EVE)[0], go(EVE, fomc_eve_risk=0.5)[0]
    assert b.shares * 2 <= a.shares + 1 and b.shares < a.shares and "size_pre_fomc" in b.lv_tags
    c = go(date(2026, 6, 23))[0]
    assert go(date(2026, 6, 23), fomc_eve_risk=0.5)[0].shares == c.shares
    # the day before CPI (2026-04-09 is also a 08:30 PCE day: the news range gate holds the AM there, so test the sizing
    # on a quiet day before a CPI date)
    cq = find_day(lambda d: C.eve_of(d, "cpi") and C.release_times(d) == [], date(2023, 1, 3), date(2026, 12, 31))
    a = go(cq)[0]
    b = go(cq, pre_cpi="small")[0]
    assert b.shares < a.shares and "size_pre_cpi" in b.lv_tags
    assert go(cq, pre_cpi="skip") == [] and go(cq, skip_pre_cpi=True) == []
    assert go(cq, pre_cpi="small", pre_cpi_risk=1.0)[0].shares == a.shares


def test_post_fomc_am_block_in_the_engine():
    assert len(go(AFTER)) == 1
    assert go(AFTER, skip_post_fomc_am=True) == [] and go(AFTER, fomc_after_am_block=True) == []
    assert len(go(AFTER, A_ROWS, start="13:30", skip_post_fomc_am=True)) == 1                  # only the AM


def test_pre_open_windows_pre8_lon_and_am_from_0830():
    t = go(NORMAL, A_ROWS, start="08:20", pre_0820=True)
    assert len(t) == 1 and t[0].session == "PRE8" and t[0].setup == "pre8"
    assert go(NORMAL, A_ROWS, start="08:20") == []                                             # off by default
    assert len(go(NORMAL, A_ROWS, start="08:20", pre_0820=True, sym="SPY")) == 1               # pre_0820 is not futures-only
    assert go(NORMAL, A_ROWS, start="08:20", ny_kz_futures=True, sym="SPY") == []              # ny_kz_futures is
    assert go(date(2026, 4, 14), A_ROWS, start="08:20", pre_0820=True) == []                    # an 08:30 release day: skipped
    t = go(NORMAL, A_ROWS, start="08:20", ny_kz_futures=True)
    assert len(t) == 1 and t[0].session == "PRE8"
    t = go(NORMAL, A_ROWS, start="08:30", am_from_0830=True)
    assert len(t) == 1 and t[0].session == "AM" and str(t[0].entry_time)[11:16] < "09:30"
    assert go(NORMAL, A_ROWS, start="08:30") == []
    t = go(NORMAL, A_ROWS, start="02:00", london_kz=True)
    assert len(t) == 1 and t[0].session == "LON" and t[0].setup == "lon"
    assert go(NORMAL, A_ROWS, start="02:00") == []
    t = go(NORMAL, A_ROWS, start="01:00", london_kz=True, london_kz_start=60)
    assert len(t) == 1 and t[0].session == "LON"
    # futures only: an equity symbol has no LON / PRE8 window (its day frame starts at 04:00 - emulated by the symbol)
    assert go(NORMAL, A_ROWS, start="02:00", london_kz=True, sym="SPY") == []


def test_window_helpers():
    ctx = ctx_for(A_ROWS)
    assert NC.extra_windows(Params(), ctx, NORMAL, "ES") == []
    assert NC.extra_windows(Params(pre_0820=True), ctx, NORMAL, "ES") == [("PRE8", 500, 570)]
    assert NC.extra_windows(Params(pre_0820=True, am_from_0830=True), ctx, NORMAL, "ES") == [("PRE8", 500, 510)]
    assert NC.extra_windows(Params(pre_0820=True, pre_0900=True), ctx, NORMAL, "ES") == [("PRE8", 500, 540)]
    assert NC.extra_windows(Params(pre_0820=True), ctx, date(2026, 4, 14), "ES") == []
    assert NC.extra_windows(Params(ny_kz_futures=True), ctx, date(2026, 4, 14), "ES") == [("PRE8", 500, 570)]
    assert NC.extra_windows(Params(ny_kz_futures=True), ctx, NORMAL, "SPY") == []
    assert NC.extra_windows(Params(london_kz=True), ctx, NORMAL, "ES") == [("LON", 120, 300)]
    assert NC.lock_cuts_extra(Params()) == set()
    assert NC.lock_cuts_extra(Params(am_from_0830=True, pre_0820=True, london_kz=True)) == {510, 500, 120}
    assert {510, 500} <= B.lock_cuts(Params(am_from_0830=True, pre_0820=True)) and 510 not in B.lock_cuts(Params())
    assert B.lock_cuts(Params(am_from_0830=True)) >= {510}


def test_nfp_first_hour_and_two_driver_gate_on_the_pre9_window():
    kw = dict(start="09:00", pre_0900=True, news_wait="off")
    assert len(go(NORMAL, A_ROWS, **kw)) == 1
    assert go(NFP_ONLY, A_ROWS, **kw) == []                                                    # N1: nobody trades the first hour
    assert len(go(NFP_ONLY, A_ROWS, nfp_first_hour=False, **kw)) == 1
    assert go(TWO_DRV, A_ROWS, **kw) == []                                                     # N5.4: before the second release
    assert len(go(TWO_DRV, A_ROWS, two_driver_gate=False, **kw)) == 1
    t = go(NFP_ONLY, A_ROWS, nfp_first_hour=False, **kw)
    assert t[0].news_tags == "nfp"


def test_lunch_session_and_carried_draw():
    t = go(NORMAL, HOLD, start="11:50", lunch=True)
    assert len(t) == 1 and t[0].session == "LUNCH" and t[0].setup == "lunch"
    assert t[0].exits[-1][3] == "lunch_exit" and str(t[0].exits[-1][0])[11:16] == "13:25"        # never held into the PM
    assert go(NORMAL, HOLD, start="11:50") == []
    t = go(NORMAL, HOLD, start="11:50", lunch=True, lunch_exit=900)
    assert t[0].exits[-1][3] == "lunch_exit"


def test_lunch_range_is_the_am_range_known_before_it():
    rows = [(100.0, 101.0, 99.0, 100.5)] * 12 + [(100.0, 105.0, 95.0, 100.0)] * 12      # 09:30-10:25 / 10:30-11:25
    ctx = ctx_for(rows)
    p = Params()
    hl = NC.am_range(ctx, p)                                                                  # 09:30 .. 11:00 only
    assert hl == (105.0, 95.0)
    ctx2 = ctx_for(rows[:12] + [(100.0, 101.0, 99.0, 100.0)] * 12 + [(100, 120, 80, 100)] * 6)   # the 11:30+ spike is not in it
    assert NC.am_range(ctx2, p) == (101.0, 99.0)


def test_pm_skip_after_and_gate():
    assert len(go(NORMAL, A_ROWS, start="13:30")) == 1
    assert go(NORMAL, A_ROWS, start="13:30", pm_skip_after=810) == []                         # nothing traded by 13:30
    assert len(go(NORMAL, A_ROWS, start="13:30", pm_skip_after=900)) == 1
    ctx = ctx_for(A_ROWS)
    p = Params(pm_skip_after=870)
    assert NC.gate(ctx, p, NORMAL, "PM", 875, 0, 950, []) == "x_pm_skip_after"
    assert NC.gate(ctx, p, NORMAL, "PM", 860, 0, 950, []) is None
    pm_tr = SimpleNamespace(session="PM")
    assert NC.gate(ctx, p, NORMAL, "PM", 875, 0, 950, [pm_tr]) is None                        # a PM trade exists
    assert NC.gate(ctx, p, NORMAL, "PM", 905, 0, 950, []) is None                             # the last hour stays open
    assert NC.gate(ctx, replace(p, pm_skip_lh=True), NORMAL, "PM", 905, 0, 950, []) == "x_pm_skip_after"
    assert NC.gate(ctx, p, NORMAL, "AM", 875, 0, 660, []) is None


def test_pm_bad_am_start():
    p = Params(pm_bad_am_start=825)
    assert NC.pm_start(p, 810, []) == 810
    assert NC.pm_start(p, 810, [_lost(NORMAL, win=True)]) == 810
    assert NC.pm_start(p, 810, [_lost(NORMAL)]) == 825
    assert NC.pm_start(p, 830, [_lost(NORMAL)]) == 830
    assert NC.pm_start(Params(), 810, [_lost(NORMAL)]) == 810
    assert NC.pm_start(p, 810, [_lost(NORMAL, sess="PM")]) == 810


def test_macro_gates():
    # the order is armed 09:50 when the rows start at 09:35 (inside the 09:50-10:10 macro), 09:45 at 09:30 (outside)
    assert len(go(NORMAL, A_ROWS)) == 1
    assert go(NORMAL, A_ROWS, macro_gate=True) == [] and go(NORMAL, A_ROWS, macro_only="all") == []
    t = go(NORMAL, A_ROWS, start="09:35", macro_gate=True)
    assert len(t) == 1 and t[0].macro_wins == "0950" and t[0].macro_win == "0950"
    assert go(NORMAL, A_ROWS)[0].macro_wins == "" and "macro" not in go(NORMAL, A_ROWS)[0].lv_tags
    assert len(go(NORMAL, A_ROWS, start="09:35", macro_only="0950")) == 1
    assert go(NORMAL, A_ROWS, start="09:35", macro_only="0950", macro_by="start") == []       # the sweep began before 09:50
    assert len(go(NORMAL, A_ROWS, start="09:45", macro_only="0950", macro_by="start")) == 1   # the sweep (09:50-09:55) inside
    # tags (multi): 13:10-13:40 and the 13:30-13:35 macro overlap
    assert NC.macro_wins(812) == ["1310", "1330"] and NC.macro_wins(819) == ["1310", "1339"] and NC.macro_wins(600) == ["0950"]
    assert NC.macro_wins(500) == []
    # macro_done_skip: the day's range already spans run_done_adr x ADR5 -> the macro entry is skipped
    assert go(NORMAL, A_ROWS, start="09:35", macro_gate=True, macro_done_skip=True, run_done_adr=10.0)   # ADR 18: not done
    assert go(NORMAL, A_ROWS, start="09:35", macro_gate=True, macro_done_skip=True, run_done_adr=0.2) == []   # range > 3.6
    assert len(go(NORMAL, A_ROWS, start="09:35", macro_gate=True, macro_done_skip=False, run_done_adr=0.2)) == 1


def test_run_done_helper():
    ctx = ctx_for(A_ROWS)
    i = S._idx_at(ctx, 840)                                                                  # 14:00: after the whole run
    assert NC.run_done(ctx, i, Params(run_done_adr=0.5)) and not NC.run_done(ctx, i, Params(run_done_adr=0.0))
    assert not NC.run_done(ctx, i, Params(run_done_adr=100.0))
    k = S._idx_at(ctx, 600)
    ctx.lock = {"AM": dict(delivered=True, delivered_i=k)}
    assert NC.run_done(ctx, k + 1, Params(run_done_adr=0.0)) and not NC.run_done(ctx, k - 1, Params(run_done_adr=0.0))


def test_or_no_entry_fill_gate_and_deep_exception():
    assert len(go(NORMAL, A_ROWS)) == 1
    t = go(NORMAL, A_ROWS, or_no_entry=True)
    assert t == []                                                                           # armed 09:45, fill 09:50 < 10:00
    # the order is kept for the 10:00 fills: a later retrace to the entry fills it
    rows = A_ROWS[:3] + [(99.8, 100.8, 99.7, 100.7)] + [(100.7, 100.9, 100.4, 100.6)] * 2 + [(100.6, 100.7, 99.9, 100.2)] + \
        [(100.2, 103.0, 100.1, 102.9), (102.9, 108.5, 102.8, 108.4)]
    t = go(NORMAL, rows, or_no_entry=True)
    assert len(t) == 1 and str(t[0].entry_time)[11:16] == "10:00"
    # the order dict: fill_from / anchor / deep window
    ctx = ctx_for(A_ROWS)
    sd = S.Side(1, ctx.o, ctx.h, ctx.l, ctx.c, 1, 0.0)
    i = ctx.start + 9 * 12 + 3 + 18                                                          # a bar before 10:00
    i = S._idx_at(ctx, 585)
    o = NC.post_order(ctx, sd, i, Params(or_no_entry=True), "AM", dict(entry=100.0, ext_i=i, lv_tags=""), ctx.hist)
    assert o["fill_from"] == 600 and o["anchor_i"] == S._idx_at(ctx, 600) and "fill_win" not in o
    o = NC.post_order(ctx, sd, i, Params(or_no_entry=True, or_deep=True, or_deep_pd=0.6), "AM",
                      dict(entry=100.0, ext_i=i, lv_tags=""), ctx.hist)                      # (100-90)/18 = 0.56 <= 0.6
    assert o["fill_win"] == ((577, 586),) and "or_deep" in o["lv_tags"]
    o = NC.post_order(ctx, sd, i, Params(or_no_entry=True, or_deep=True), "AM", dict(entry=100.0, ext_i=i, lv_tags=""), ctx.hist)
    assert "fill_win" not in o
    o = NC.post_order(ctx, sd, i, Params(or_no_entry=True), "PM", dict(entry=100.0, ext_i=i, lv_tags=""), ctx.hist)
    assert "fill_from" not in o                                                              # AM orders only
    ssd = S.Side(-1, ctx.o, ctx.h, ctx.l, ctx.c, 1, 0.0)
    o = NC.post_order(ctx, ssd, i, Params(or_no_entry=True, or_deep=True, or_deep_pd=0.6), "AM",
                      dict(entry=-100.0, ext_i=i, lv_tags=""), ctx.hist)                     # a short: from the top of the range
    assert "fill_win" in o
    # 10:00 release days: the release gate holds those; or_no_entry_news1000 applies it anyway
    ctx10 = ctx_for(A_ROWS, d=date(2026, 4, 6))
    sd10 = S.Side(1, ctx10.o, ctx10.h, ctx10.l, ctx10.c, 1, 0.0)
    o = NC.post_order(ctx10, sd10, i, Params(or_no_entry=True), "AM", dict(entry=100.0, ext_i=i, lv_tags=""), ctx10.hist)
    assert "fill_from" not in o
    o = NC.post_order(ctx10, sd10, i, Params(or_no_entry=True, or_no_entry_news1000=True), "AM",
                      dict(entry=100.0, ext_i=i, lv_tags=""), ctx10.hist)
    assert o["fill_from"] == 600
    assert NC.fill_ok(dict(fill_from=600), 600) and not NC.fill_ok(dict(fill_from=600), 595)
    assert NC.fill_ok(dict(fill_from=600, fill_win=((577, 586),)), 580) and not NC.fill_ok(dict(fill_from=600, fill_win=((577, 586),)), 590)
    assert NC.fill_ok({}, 0)
    t = go(NORMAL, A_ROWS, or_no_entry=True, or_end=570)                                     # an OR that is over at once
    assert len(t) == 1


def test_or_bias_wide_or_and_pm_continue_helpers():
    rows = [(100.0, 101.0, 99.5, 100.5), (100.5, 103.0, 100.4, 102.5), (102.5, 102.6, 98.0, 99.0), (99.0, 100.5, 98.5, 100.2),
            (100.2, 101.5, 100.0, 101.0), (101.0, 102.0, 100.8, 101.8)]
    ctx = ctx_for(rows)
    assert NC.or_dir(ctx, "judas", 600) == -1                                                # the high came first: the Judas
    assert NC.or_dir(ctx, "close", 600) == 1                                                 # closed above the midpoint (100.5)
    ctx_lh = ctx_for([(100.0, 100.2, 97.0, 97.5), (97.5, 103.0, 97.4, 102.0)] + [(102.0, 102.1, 101.8, 102.0)] * 4)
    assert NC.or_dir(ctx_lh, "judas", 600) == 1                                              # the low came first
    assert NC.or_dir(ctx_for([(100, 100.2, 99.9, 100)] * 6), "judas", 600) == 0                  # one flat bar repeated: a tie
    p = Params(or_bias="judas", or_end=600)
    assert NC.side_filter(ctx, p, "AM", 1, 0, 610) == "x_or_bias" and NC.side_filter(ctx, p, "AM", -1, 0, 610) is None
    assert NC.side_filter(ctx, p, "AM", 1, 0, 590) is None                                   # before the OR is over
    assert NC.side_filter(ctx, replace(p, or_bias_filter=False), "AM", 1, 0, 610) is None   # tag only
    assert NC.side_filter(ctx, replace(p, or_bias="close"), "AM", -1, 0, 610) == "x_or_bias"
    assert NC.side_filter(ctx, p, "PM", 1, 0, 860) is None and NC.side_filter(ctx, Params(), "AM", 1, 0, 610) is None
    # the wide OR: range 5 vs ADR5 18 -> wide at 0.2; the far end from the last close (101.8 above the mid 100.5): down
    pw = Params(or_wide=True, or_wide_end=600, or_wide_adr=0.2)
    assert NC.wide_or_dir(ctx, pw) == 1 or NC.wide_or_dir(ctx, pw) == -1
    c2 = ctx_for(rows)
    assert NC.wide_or_dir(c2, replace(pw, or_wide_adr=0.2)) == -1                            # 101.8 > mid (100.5) -> toward the low
    assert NC.wide_or_dir(ctx_for(rows), replace(pw, or_wide_adr=0.5)) == 0                  # 5 < 9: not wide
    assert NC.side_filter(c2, pw, "AM", 1, 0, 610) == "x_or_wide" and NC.side_filter(c2, pw, "AM", -1, 0, 610) is None
    # the PM continues the AM
    up = ctx_for([(100 + k * 0.3, 100.4 + k * 0.3, 99.9 + k * 0.3, 100.3 + k * 0.3) for k in range(30)])
    assert NC.am_dir(up, Params()) == 1
    pc = Params(pm_continue_am="filter")
    assert NC.side_filter(up, pc, "PM", -1, 0, 830) == "x_pm_continue_am" and NC.side_filter(up, pc, "PM", 1, 0, 830) is None
    assert NC.side_filter(up, Params(pm_continue_am="tag"), "PM", -1, 0, 830) is None
    assert NC.am_dir(ctx_for([(100, 100.2, 99.8, 100)] * 30), Params()) == 0


def test_pm_continue_am_and_ob_tags_in_the_engine():
    t = go(NORMAL, A_ROWS, start="13:30", pm_continue_am="tag")
    assert len(t) == 1 and ("pm_vs_am" in t[0].lv_tags or "pm_am_flat" in t[0].lv_tags)
    assert len(go(NORMAL, A_ROWS, start="13:30", pm_continue_am="filter")) in (0, 1)
    t = go(NORMAL, A_ROWS, start="13:30", pm_ob_entry="tag")
    assert len(t) == 1
    assert len(go(NORMAL, A_ROWS, start="13:30", pm_ob_entry="require")) in (0, 1)


def test_pm_ob_helper():
    # an AM down-close series 09:50-10:05 (the OB, 99-100) that held, then a long entry inside it at 13:30+
    rows = [(101, 101.5, 100.8, 101.2)] * 4 + [(101.2, 101.3, 99.5, 99.8), (99.8, 99.9, 99.0, 99.2), (99.2, 99.6, 99.0, 99.4)] + \
        [(99.4, 102.0, 99.3, 101.9)] * 60
    ctx = ctx_for(rows)
    sd = S.Side(1, ctx.o, ctx.h, ctx.l, ctx.c, 1, 0.0)
    i = S._idx_at(ctx, 815)
    assert NC._ob_before_pm(ctx, sd, i, 99.5) is True or NC._ob_before_pm(ctx, sd, i, 99.5) is False
    assert NC._ob_before_pm(ctx, sd, i, 150.0) is False                                      # far from any block
    o = NC.post_order(ctx, sd, i, Params(pm_ob_entry="require"), "PM", dict(entry=150.0, ext_i=i, lv_tags=""), ctx.hist)
    assert o is None
    o = NC.post_order(ctx, sd, i, Params(pm_ob_entry="tag"), "PM", dict(entry=150.0, ext_i=i, lv_tags=""), ctx.hist)
    assert o is not None and "pm_ob" not in o["lv_tags"]


# --- news Judas ------------------------------------------------------------------------------------------------------

def _news_rows(first):
    """08:30 release with the first run up (+1), down (-1), both (up-close) or none."""
    return {"up": [(100.0, 101.5, 99.9, 101.0)], "down": [(100.0, 100.1, 98.5, 99.0)],
            "both": [(100.0, 101.5, 98.5, 101.2)], "none": [(100.0, 100.1, 99.9, 100.0)]}[first]


def test_first_run_and_judas_gate():
    for first, want in (("up", 1), ("down", -1), ("both", -1), ("none", None)):
        ctx = ctx_for(_news_rows(first) + [(100.0, 100.1, 99.9, 100.0)] * 5, start="08:30", d=date(2026, 5, 12))
        fr = NC.first_run(ctx, 510, 60)
        assert fr["ref"] is True
        k = S._idx_at(ctx, 510)
        if want is None:
            assert fr["k"] is None
        else:
            assert (fr["k"], fr["dir"]) == (k, want)
        drv = dict(R=510)
        p = Params(news_judas="block")
        i = k + 2
        assert NC.judas_gate(ctx, p, ctx.day, drv, i, 520) == ((want or 0), False)
        assert NC.judas_gate(ctx, p, ctx.day, drv, k - 1, 505) == (0, False)               # before the run: nothing yet
        assert NC.judas_gate(ctx, Params(), ctx.day, drv, i, 520) == (0, False)
        w = NC.judas_gate(ctx, Params(news_judas="wait"), ctx.day, drv, i, 520)
        assert w == ((want, False) if want else (0, True))
        assert NC.judas_gate(ctx, p, ctx.day, None, i, 520) == (0, False)
    # an earlier run only: the pre-release reference window can be different
    ctx = ctx_for(_news_rows("up") + [(100, 100.1, 99.9, 100)] * 5, start="08:30", d=date(2026, 5, 12))
    assert NC.first_run(ctx, 510, 30)["ref"] and NC.first_run(ctx, 510, 30)["k"] == S._idx_at(ctx, 510)
    # no reference bars (the release is the first bar of the day frame): no gate at all
    assert NC.first_run(ctx, 0, 60) == dict(ref=False, k=None, dir=0)
    assert NC.judas_gate(ctx, Params(news_judas="wait"), ctx.day, dict(R=0), S._idx_at(ctx, 510), 510) == (0, False)


def test_judas_blocks_the_losing_side_in_the_engine():
    d = date(2026, 5, 12)                                          # CPI 08:30
    rows = _news_rows("up") + [(101.0, 101.2, 100.4, 100.5), (100.5, 100.9, 100.3, 100.8), (100.8, 101.0, 100.6, 100.9)]
    df = day(A_ROWS, d=d, spike=True)
    pre = day(rows, d=d, start="08:30").iloc[102:106]                                           # 08:30-08:45
    df.loc[pre.index] = pre
    p = Params(**BASE)
    run = lambda **kw: S.run_day(df.copy(), history(d), "ES", replace(p, **kw), 5, bias_by_cut=A_LOCK)
    assert len(run()) == 1                                                                      # the long is allowed
    assert run(news_judas="block") == []                                                        # the buy side was taken first
    assert run(news_judas="wait") == []


def test_fomc_judas_gate_and_held_order():
    d = FOMC_ONLY
    rows = [(100.0, 101.5, 99.9, 101.0), (101.0, 101.2, 100.5, 100.8)] * 4
    ctx = ctx_for(rows, start="14:00", d=d)
    p = Params(fomc_judas=True)
    fr = NC.first_run(ctx, 840, 60, end=870)
    assert fr["k"] is not None and fr["dir"] == 1
    i = S._idx_at(ctx, 870)
    assert NC.judas_gate(ctx, p, d, dict(R=840), i, 870) == (1, False)                       # the first run up was the Judas
    assert NC.judas_gate(ctx, p, d, dict(R=840), i - 3, 855) == (0, False)                   # before fomc_judas_end
    assert NC.judas_gate(ctx, p, d, dict(R=840), i + 3, 890)[0] == 0                         # past fomc_pm_from (885)
    assert NC.judas_gate(ctx, replace(p, fomc_stage2_cont=True), d, dict(R=840), i + 3, 890)[0] == 1
    assert NC.judas_gate(ctx, Params(), d, dict(R=840), i, 870) == (0, False)
    # the held order
    sd = S.Side(1, ctx.o, ctx.h, ctx.l, ctx.c, 1, 0.0)
    k0 = S._idx_at(ctx, 840)
    held = dict(i=k0 + 1, entry=95.0, t1=120.0)
    assert NC.held_valid(ctx, sd, held, k0 + 5, Params(fomc_observe="defer"))
    assert not NC.held_valid(ctx, sd, dict(held, entry=100.6), k0 + 5, Params(fomc_observe="defer"))   # price came back
    assert not NC.held_valid(ctx, sd, dict(held, t1=101.0), k0 + 5, Params(fomc_observe="defer"))      # ran to the target
    assert not NC.held_valid(ctx, sd, held, k0 + 5, Params(fomc_observe="judas"))                      # a long vs the Judas up
    ssd = S.Side(-1, ctx.o, ctx.h, ctx.l, ctx.c, 1, 0.0)
    assert NC.held_valid(ctx, ssd, dict(i=k0 + 1, entry=-120.0, t1=-80.0), k0 + 5, Params(fomc_observe="judas"))
    assert NC.observing(Params(fomc_observe="defer"), d, "PM", 850) and not NC.observing(Params(fomc_observe="defer"), d, "PM", 890)
    assert not NC.observing(Params(), d, "PM", 850) and not NC.observing(Params(fomc_observe="defer"), NORMAL, "PM", 850)
    assert not NC.observing(Params(fomc_observe="defer"), d, "AM", 850)


def test_fomc_observe_holds_the_order_until_the_first_allowed_bar():
    rows = A_ROWS[:4] + [(100.7, 101.0, 100.4, 100.6)] + [(100.6, 100.7, 100.5, 100.6)] * 5 + \
        [(100.6, 100.7, 99.9, 100.5), (100.5, 103.0, 100.4, 102.9), (102.9, 108.5, 102.8, 108.4)]
    kw = dict(start="14:00", news_wait="off")
    assert go(FOMC_ONLY, rows, **kw) == []                                                     # the PM is closed until 14:45
    for mode, armed in (("defer", "14:40"), ("judas", "14:25")):
        t = go(FOMC_ONLY, rows, fomc_observe=mode, **kw)
        assert len(t) == 1 and str(t[0].entry_time)[11:16] == "14:50"                          # filled 14:50
        assert str(t[0].armed)[11:16] == armed       # armed on the bar before fomc_pm_from (14:45; "judas": 14:30)
    # the PM is not touched on other days
    a, b = go(NORMAL, rows, **kw), go(NORMAL, rows, fomc_observe="defer", **kw)
    assert [(t.entry_time, t.entry) for t in a] == [(t.entry_time, t.entry) for t in b]
    # an order whose entry was retraced to during the observation is not held (it would have filled)
    bad = A_ROWS[:5] + [(100.3, 100.9, 99.9, 100.2)] * 5 + [(100.6, 100.7, 99.9, 100.5)]
    assert go(FOMC_ONLY, bad, fomc_observe="defer", **kw) == []


def test_calendar_blocks_apply_to_the_silver_bullet_and_ma_deuce_windows():
    assert NC.sb_start(Params(), FOMC_ONLY, "PM", 840, 900) == 840                              # off: the old build skips the day
    assert NC.sb_start(Params(sb_fomc_pm=True), FOMC_ONLY, "PM", 840, 900) == 885
    assert NC.sb_start(Params(sb_fomc_pm=True, fomc_judas=True), FOMC_ONLY, "PM", 840, 900) == 870
    assert NC.sb_start(Params(sb_fomc_pm=True), FOMC_ONLY, "AM", 600, 660) == 600
    assert NC.sb_start(Params(sb_fomc_pm=True), NORMAL, "PM", 840, 900) == 840
    ctx = ctx_for(A_ROWS)
    ctx.bias_row = None
    assert NC.sb_gate(ctx, Params(fomc_am="recipe"), FOMC_ONLY, "AM", 600) is True
    ctx.bias_row = dict(react=1, draw=1)
    assert NC.sb_gate(ctx, Params(fomc_am="recipe"), FOMC_ONLY, "AM", 600) is False
    assert NC.sb_gate(ctx, Params(fomc_am="recipe"), NORMAL, "AM", 600) is False
    assert NC.sb_gate(ctx, Params(), FOMC_ONLY, "AM", 600) is False


def test_carry_lock_and_draw_done_skip():
    lk = dict(px=100.0, side=-1, target=95.0, kind="pool", name="pdl1")
    am = dict(side=1, target=108.0, kind="pool", name="pdh1", delivered=False)
    ctx = SimpleNamespace(lock={"AM": am})
    out = NC.carry_lock(ctx, Params(pm_carry_draw=True), "PM", dict(lk))
    assert (out["side"], out["target"], out["name"], out["carried"]) == (1, 108.0, "pdh1", True)
    assert NC.carry_lock(ctx, Params(), "PM", dict(lk)) == lk
    assert NC.carry_lock(ctx, Params(pm_carry_draw=True), "AM", dict(lk)) == lk
    ctx.lock["AM"] = dict(am, delivered=True)
    assert NC.carry_lock(ctx, Params(pm_carry_draw=True), "PM", dict(lk)) == lk              # delivered: not carried
    ctx.lock["AM"] = dict(am, target=99.0)                                                    # lies behind the price now
    assert NC.carry_lock(ctx, Params(pm_carry_draw=True), "PM", dict(lk)) == lk
    ctx.lock["AM"] = dict(am, side=0)
    assert NC.carry_lock(ctx, Params(pm_carry_draw=True), "PM", dict(lk)) == lk
    c2 = ctx_for(A_ROWS)
    c2.lock = {"AM": dict(delivered=True, delivered_i=c2.start + 5)}
    assert NC.gate(c2, Params(draw_done_skip=True), NORMAL, "PM", 820, c2.start + 6, 950, []) == "x_draw_done"
    assert NC.gate(c2, Params(draw_done_skip=True), NORMAL, "LUNCH", 720, c2.start + 6, 810, []) == "x_draw_done"
    assert NC.gate(c2, Params(draw_done_skip=True), NORMAL, "PM", 820, c2.start + 4, 950, []) is None
    assert NC.gate(c2, Params(), NORMAL, "PM", 820, c2.start + 6, 950, []) is None
    assert NC.gate(c2, Params(draw_done_skip=True), NORMAL, "AM", 600, c2.start + 6, 660, []) is None
    assert NC.gate(c2, Params(fomc_am="recipe"), FOMC_ONLY, "AM", 600, c2.start + 6, 660, []) == "x_fomc_recipe"
    assert NC.gate(c2, Params(), TWO_DRV, "PRE9", 540, c2.start + 6, 570, []) == "x_two_driver"
    assert NC.gate(c2, Params(), TWO_DRV, "AM", 600, c2.start + 6, 660, []) is None                   # the news gate holds it
    assert NC.gate(c2, Params(two_driver_gate=False), TWO_DRV, "PRE9", 540, c2.start + 6, 570, []) is None


def test_pm_carry_draw_in_the_engine():
    a = go(NORMAL, A_ROWS, start="13:30", pm_carry_draw=True)
    b = go(NORMAL, A_ROWS, start="13:30")
    assert len(a) in (0, 1) and len(b) == 1


def test_trade_news_tags_and_funnel_keys():
    t = go(EVE)[0]
    assert t.news_tags == "fomc_eve"
    assert go(NORMAL)[0].news_tags == ""
    S.FUNNEL = __import__("collections").Counter()
    try:
        go(NORMAL, A_ROWS, macro_gate=True)
        assert S.FUNNEL["x_macro_gate"] >= 1
        go(FOMC_ONLY, fomc_am="recipe")
        assert S.FUNNEL["x_fomc_recipe"] >= 1
    finally:
        S.FUNNEL = None


# --- no look-ahead: full run vs truncated runs --------------------------------------------------------------------

COLS = ["entry_time", "entry", "stop", "t1", "shares", "entry_kind", "lv_tags", "setup", "swept", "session"]
CMP = ["entry_time", "entry", "shares", "session", "lv_tags", "net", "stop"]
# three synthetic windows (seeds picked for trades on the FOMC eve / FOMC day; the two-driver / jobs / CPI days)
WINDOWS = {"W0": ("2026-04-20", "2026-05-01", 37), "W1": ("2026-04-27", "2026-05-13", 6),
           "W2": ("2026-04-27", "2026-05-13", 5)}
LA = {   # name -> (window, switches); each set trades in its window and changes the engine there (test below)
    "fomc_day": ("W0", dict(fomc_am="recipe", fomc_only_am="scalp", fomc_eve_risk=0.5, pre_fomc_risk=0.8, fomc_flat=840,
                            fomc_observe="judas", fomc_judas=True, fomc_stage2_cont=True, fomc_pm_block_from=840,
                            sb_fomc_pm=True, fomc_no_reentry=True, pre_cpi="small")),
    "fomc_b": ("W0", dict(fomc_only_am="scalp", fomc_eve_risk=0.5, fomc_observe="defer", sb_fomc_pm=True,
                          skip_post_fomc_am=True, fomc_no_reentry=True)),
    "news_judas": ("W2", dict(news_judas="wait", news_judas_ref_min=45, news_claims=True, news_minutes=True)),
    "news_judas_b": ("W2", dict(news_judas="block", wait_0945=False)),
    "or_family": ("W0", dict(or_no_entry=True, or_deep=True, or_deep_pd=0.5, or_bias="judas", or_wide=True, or_wide_adr=0.2,
                             or_no_entry_news1000=True, or_end=630)),
    "or_b": ("W0", dict(or_bias="close", or_wide=True, or_wide_adr=0.1, or_wide_end=600, or_no_entry=True, or_end=630)),
    "windows": ("W0", dict(pre_0820=True, am_from_0830=True, ny_kz_futures=True, london_kz=True, london_kz_start=240,
                           lunch=True, pm_carry_draw=True, draw_done_skip=True)),
    "windows_b": ("W0", dict(pre_0820=True, lunch=True, lunch_exit=780, pm_carry_draw=True)),
    "pm_macro": ("W1", dict(pm_skip_after=870, pm_bad_am_start=825, pm_continue_am="filter", pm_ob_entry="tag",
                            macro_gate=True, macro_by="start", macro_done_skip=True, moc_htf_done=True, run_done_adr=0.7)),
    "pm_macro_b": ("W1", dict(macro_only="all", pm_skip_lh=True, pm_skip_after=840, pm_continue_am="tag", pm_ob_entry="tag",
                              macro_done_skip=True)),
    "pm_macro_c": ("W1", dict(macro_only="all", pm_ob_entry="require", moc_htf_done=True)),
    "skips": ("W2", dict(skip_pre_cpi=True, skip_auction_am=True, nfp_day_from=600, nfp_first_hour=True, pre_0900=True,
                         post_news=True, fed_chair_skip_am=True)),
    "fomc_c": ("W0", dict(fomc_flat_before=825, fomc_judas=True, fomc_judas_end=865, fomc_observe="judas",
                          pre_cpi="small", pre_cpi_risk=0.3, fomc_whipsaw_skip_london=True, london_kz=True,
                          fomc_no_reentry=True)),
    "gates_c": ("W0", dict(news_conf_board=True, two_driver_gate=False, pre_0900=True, or_no_entry=True, or_deep=True, or_deep_win=(580, 600),
                           or_bias="close", or_bias_filter=False, lunch=True, lunch_win=(700, 800), lunch_exit=790)),
    "macro_0950": ("W1", dict(macro_only="0950", fomc_only_am="tag", pm_ob_entry="tag")),
    "skips_b": ("W2", dict(skip_two_drivers=True, skip_pre_fomc=True, pre_cpi="skip", fomc_after_am_block=True,
                           fomc_am="skip")),
}
_RUNS = {}


def _syn_run(wname, **kw):
    key = (wname, tuple(sorted(kw.items(), key=lambda kv: kv[0])))
    if key not in _RUNS:
        win = WINDOWS[wname]
        x, y = B.synthetic(start=win[0], end=win[1], tf=5, seed=win[2])
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            _RUNS[key] = (x, y, B.run(x, 5, "ES", Params(**SYN, sb_model=True, ma_deuce=True, **kw), y))
    return _RUNS[key]


@pytest.mark.parametrize("name", list(LA))
def test_look_ahead_synthetic(name):
    wname, kw = LA[name]
    x, y, full = _syn_run(wname, **kw)
    assert len(full) >= 1, f"{name}: no trades in window {wname}"
    _no_look_ahead(x, 5, "ES", Params(**SYN, sb_model=True, ma_deuce=True, **kw), COLS,
                   every=max(1, len(full) // 3), partner=y, exits=True, min_trades=1)


def test_look_ahead_sets_are_not_vacuous():
    """Each set changes the engine in its window (the switches act on the synthetic days)."""
    for name, (wname, kw) in LA.items():
        _, _, base = _syn_run(wname)
        _, _, t = _syn_run(wname, **kw)
        same = len(t) == len(base) and (not len(t) or t[CMP].reset_index(drop=True).equals(base[CMP].reset_index(drop=True)))
        assert not same, name


def test_default_runs_are_untouched_by_the_new_switches_off():
    """With every new switch off (the old defaults pinned), the engine is exactly the same as with the new defaults on a
    window that has no FOMC loss / jobs-day pre-open window / chair day."""
    x, y = B.synthetic(start="2026-06-01", end="2026-06-19", tf=5, seed=5)
    off = dict(fomc_no_reentry=False, nfp_first_hour=False, fed_chair_skip_am=False, fomc_flat=0)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        a = B.run(x, 5, "RW", Params(**SYN), y)
        b = B.run(x, 5, "RW", Params(**SYN, **off), y)
    cols = ["entry_time", "entry", "stop", "t1", "shares", "net"]
    pd.testing.assert_frame_equal(a[cols].reset_index(drop=True), b[cols].reset_index(drop=True))


@pytest.mark.skipif(not ES, reason="no ES data")
@pytest.mark.parametrize("window", [("2023-10-30", "2023-11-10"), ("2023-10-09", "2023-10-16")])
def test_look_ahead_es_news_days(window):
    """FOMC eve 10-31, FOMC 11-01 (14:00), the day after, NFP 11-03; and a CPI week. Silver Bullet and Ma Deuce on."""
    es = B.load("ES", 5, source="databento")
    df = es[(es.index >= window[0]) & (es.index < window[1])]
    meta = B.load_meta("ES", 5)
    p = Params(**FUT, htf_resist_cap=False, draw_lock="off", leg_pd=0, min_draw_pts=0, use_bias=False, ob_entry="post_mss",
               sb_model=True, ma_deuce=True, fomc_observe="defer", fomc_judas=True, news_judas="block", or_no_entry=True,
               pre_0820=True, lunch=True, pm_continue_am="tag", fomc_eve_risk=0.5, pre_fomc_risk=0.5, sb_fomc_pm=True,
               fomc_am="recipe", skip_auction_am=True, london_kz=True, ny_kz_futures=True, nfp_first_hour=True,
               pre_0900=True, pre_flat_0830=True)
    _no_look_ahead(df, 5, "ES", p, COLS, every=1, meta=meta, exits=True)


def _fomc_session(d, wide):
    """A regular session whose 13:00-14:00 range is 99.5-100.5 and whose 14:00-15:00 reaction takes both sides (wide) or one."""
    idx = pd.date_range(pd.Timestamp(f"{d} 09:30", tz=B.NY), periods=78, freq="5min")
    rows = np.tile([100.0, 100.1, 99.9, 100.0], (78, 1))
    m = idx.hour * 60 + idx.minute
    rows[(m >= 780) & (m < 840), 1], rows[(m >= 780) & (m < 840), 2] = 100.5, 99.5
    k = int(np.flatnonzero(m == 845)[0])
    rows[k, 1] = 101.0
    if wide:
        rows[k + 1, 2] = 99.0
    return pd.DataFrame({"open": rows[:, 0], "high": rows[:, 1], "low": rows[:, 2], "close": rows[:, 3], "volume": 1.0}, index=idx)


def test_fomc_whipsaw_skips_the_next_london_open():
    p = Params(fomc_whipsaw_skip_london=True, london_kz=True)
    for wide, want in ((True, True), (False, False)):
        ctx = ctx_for(A_ROWS, d=AFTER)
        ctx.hist = history(AFTER)[:-1] + [_fomc_session(C.prev_trading_day(AFTER), wide)]
        assert NC.fomc_whipsaw(ctx, AFTER, p) is want
        assert bool(NC.extra_windows(p, ctx, AFTER, "ES")) is (not want)
        assert NC.fomc_whipsaw(ctx, AFTER, Params()) is False             # off by default
    assert NC.fomc_whipsaw(ctx_for(A_ROWS, d=NORMAL), NORMAL, p) is False     # only the day after FOMC
    t = go(AFTER, A_ROWS, start="02:00", london_kz=True, hist=history(AFTER)[:-1] + [_fomc_session(C.prev_trading_day(AFTER), True)],
           fomc_whipsaw_skip_london=True)
    assert t == []
    t = go(AFTER, A_ROWS, start="02:00", london_kz=True, hist=history(AFTER)[:-1] + [_fomc_session(C.prev_trading_day(AFTER), False)],
           fomc_whipsaw_skip_london=True)
    assert len(t) == 1 and t[0].session == "LON"


def test_am_from_0830_leaves_no_double_scan_with_the_pre9_window():
    kw = dict(start="09:00", pre_0900=True, news_wait="off")
    assert go(NORMAL, A_ROWS, **kw)[0].session == "PRE9"
    t = go(NORMAL, A_ROWS, am_from_0830=True, **kw)
    assert len(t) == 1 and t[0].session == "AM"                                   # the AM covers 09:00-09:30 itself


@pytest.mark.skipif(not ES, reason="no ES data")
def test_ma_deuce_is_flat_before_an_0830_release_on_real_bars():
    """N4: the 08:29 flat covers Ma Deuce (2024-03-14, PPI 08:30: the golden window's Ma Deuce short was stopped at 08:30 in the
    first build and is now out at the close of the 08:20 bar)."""
    df = B.load("ES", 5, source="databento")
    df = df[(df.index >= "2024-03-01") & (df.index < "2024-03-16")]
    p = replace(Params(**FUT, leg_pd=0, min_draw_pts=0, sb_model=True, ma_deuce=True), **study.PRE_OWNER)
    old = B.run(df, 5, "ES", p)
    new = B.run(df, 5, "ES", replace(p, flat_0830_extras=True))
    o, n = old[old.setup == "ma_deuce"], new[new.setup == "ma_deuce"]
    d = pd.Timestamp("2024-03-14").date()
    assert len(o[o.date == d]) == 1 and len(n[n.date == d]) == 1
    assert o[o.date == d].exit_reason.iloc[0] == "stop" and str(o[o.date == d].exit_time.iloc[0])[11:16] == "08:30"
    assert n[n.date == d].exit_reason.iloc[0] == "pre_0830" and str(n[n.date == d].exit_time.iloc[0])[11:16] == "08:25"
    assert len(old) == len(new)                                                                # nothing else moves


# --- review fixes: calendar, windows, tags ---------------------------------------------------------
def test_consumer_confidence_last_tuesday_and_auction_overlay():
    assert C.is_consumer_confidence(date(2025, 3, 25)) and C.is_consumer_confidence(date(2024, 12, 31)) is True
    assert not C.is_consumer_confidence(date(2025, 3, 18))
    assert 600 in C.release_times(date(2025, 3, 25), conf=True) and 600 not in C.release_times(date(2025, 3, 25))
    d = date(2026, 4, 29)
    assert not C.is_auction_day(d)
    C.AUCTIONS.add(d)
    try:
        assert C.is_auction_day(d)                                   # no cache: edits take effect at once
    finally:
        C.AUCTIONS.discard(d)
    assert not C.is_auction_day(d)


def test_judas_not_on_minutes_day_and_or_bias_tag():
    mn = sorted(C.FOMC_MINUTES)[-1]
    assert not C.fomc_info(mn)["fomc"]
    import inspect
    assert 'CAL.fomc_info(day)["fomc"]' in inspect.getsource(NC.judas_gate)
    assert "or_bias_with" in inspect.getsource(NC.post_order)


def test_fill_ok_window_reads_bar_close():
    o = dict(fill_from=600, fill_win=((577, 586),))
    assert [NC.fill_ok(o, t, 5) for t in (575, 580, 585, 590)] == [True, True, False, False]


def test_nfp_week_comments_cases():
    assert S.blocked(date(2025, 7, 4), "AM", Params(nfp_week_block=True)) is None              # holiday after a Thursday NFP: not an NFP-week day
    assert S.blocked(date(2025, 7, 2), "AM", Params(nfp_week_block=True, nfp_thu=False)) == "nfp_week_thu_fri"
    assert S.blocked(date(2025, 12, 18), "AM", Params(nfp_week_block=True)) is None           # jobs date on a Tuesday: no Thu / Fri block


def test_london_kz_start_validated():
    with pytest.raises(ValueError):
        Params(london_kz=True, london_kz_start=123)


def test_nfp_first_hour_floors_pre8_and_am_from_0830():
    """N1: on a jobs day with nfp_first_hour no entry window opens before 09:30 (PRE8 dropped, AM floored)."""
    for kw in (dict(ny_kz_futures=True), dict(am_from_0830=True), dict(ny_kz_futures=True, am_from_0830=True)):
        for start in ("08:20", "09:30"):
            t = go(NFP_ONLY, start=start, nfp_first_hour=True, **kw)
            assert all(x.entry_time.hour * 60 + x.entry_time.minute >= 570 for x in t), (kw, start)


def test_pre8_order_cut_at_release_on_0830_days():
    """N4: on an 08:30 release day PRE8 orders are cancelled at 08:30 like PRE7 (cut 510), not 09:30."""
    for start in ("08:20",):
        t = go(NFP_ONLY, start=start, ny_kz_futures=True, pre_flat_0830=True, nfp_first_hour=False)
        assert all(not (x.session == "PRE8" and x.entry_time.hour * 60 + x.entry_time.minute >= 510) for x in t)
