"""Package day_week_context (rule_coverage.md section 3, 49 items): unit tests for the calendar and the daycontext
helpers, one-day scenarios through run_day (the real engine path, Silver Bullet and Ma Deuce included) and
no-look-ahead runs (full vs truncated) covering every new switch. The ES tests skip when the data is missing."""
import warnings
from dataclasses import fields, replace
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from mentorship import backtest as B, calendar as C, daycontext as DW, study, strategy as S
from mentorship.strategy import Params
from dataclasses import dataclass as _oa_dc


@_oa_dc
class Params(Params):   # OA1029 Q92: these tests exercise other rules; the order-block narrative gate (default on) leaves them no trades
    ob_need_narrative: bool = False

from test_review_fixes import A_LOCK, A_ROWS, BASE, D0, day, frame, history  # noqa: E402  (shared scenario builders)
from test_entries_stops import _no_look_ahead  # noqa: E402

ES = Path("data/mentorship/ES_5min_db.csv").exists()
FUT = dict(es_pt=1.0, lot=1, max_notional=1e12, cost_per_share=0.1)
SYN = dict(es_pt=0.09, use_bias=False, min_draw_pts=0, leg_pd=0)
NORMAL = D0                                          # Tuesday 2026-06-23: nothing special about it


def go(d, rows=A_ROWS, start="09:30", tail=None, hist=None, week=None, eve=None, **kw):
    """One scenario day through run_day: the A_ROWS sweep / MSS / FVG order (filled 09:50) on date `d`."""
    p = Params(**{**BASE, **kw})
    locks, log, skips = [], [], []
    tr = S.run_day(day(rows, d=d, start=start, spike=True, tail=tail), hist or history(d), "ES", p, 5, locks=locks,
                   log=log, skips=skips, bias_by_cut=A_LOCK, week=week, eve=eve)
    return tr, skips


def funnel(d, **kw):
    import collections
    S.FUNNEL = collections.Counter()
    try:
        tr, sk = go(d, **kw)
        return tr, sk, dict(S.FUNNEL)
    finally:
        S.FUNNEL = None


def ctx_for(rows=A_ROWS, d=NORMAL, start="09:30", hist=None, p=None, week=None, eve=None, **kw):
    hist = hist or history(d)
    ctx = S.DayCtx(day(rows, d=d, start=start, **kw), d, hist, 5)
    ctx.hist = hist
    ctx.lock = {}
    ctx.eth = None
    ctx.dplan = DW.plan(ctx, hist, p or Params(**BASE), week, eve)
    return ctx


def daily(d, o, h, l, c):
    """A one-session frame with exactly this open / high / low / close."""
    return frame(d, [(o, h, l, o), (o, max(o, c), min(o, c), c)], 5, "09:30")


def sessions(start, ohlc):
    """Consecutive trading-day frames from `start` (one OHLC tuple each)."""
    out, d = [], start
    for o in ohlc:
        while not C.is_trading_day(d):
            d += timedelta(days=1)
        out.append(daily(d, *o))
        d += timedelta(days=1)
    return out


# --- defaults, validation, study variants -----------------------------------------------------------------------

def _block():
    n = [f.name for f in fields(Params)]
    return n[n.index("b11_inside_week"):n.index("journal_tags") + 1]


# tuning knobs of another switch (the variant of the main switch uses them) - checked in the variants below
KNOBS = set()


def test_defaults_and_validation():
    p = Params()
    assert (p.skip_post_holiday_am, p.london_adr_skip, p.friday_slow_split, p.early_close_flat) == (True, 0.8, True, True)
    assert (p.be_counts_as_win, p.journal_tags, p.consol_skip, p.sd_week_news) == (True, True, True, True)
    assert p.skip_holiday_eve is False and p.monday_mode == "trade" and p.roll_week_src == "calendar"
    assert p.consol_pm_pools == ("pd", "london", "draw") and p.tgif_model_skip == ()
    assert p.london_adr_win == (120, 300) and p.daily_range_regime == "off" and p.sunday_no_gap_trade is False
    assert p.year_end == "december" and p.year_end_map == "squaring" and p.sloppy_mode == "stand_aside" and p.sloppy_tests == ("big_prev", "chop")
    assert p.week_done_on_draw == "off" and p.friday_week_done == "off" and p.tue_off_monday == "off"
    for kw in (dict(b11_inside_week="x"), dict(outside_day_rule="x"), dict(org_tell="x"), dict(org_bias_gap="x"),
               dict(sunday_scenario="x"), dict(low_vol_inside="x"), dict(adr_basis="x"), dict(trend_recipe="x"),
               dict(consol_day_rules="x"), dict(monday_mode="x"), dict(tue_off_monday="x"), dict(thu_fri_break="x"),
               dict(friday_week_done="x"), dict(week_done_on_draw="x"), dict(roll_week_src="x"), dict(nr_tags=("x",)),
               dict(consol_pm_pools=("x",)), dict(tgif_model_skip=("x",)), dict(seasonal_map=("bull",)),
               dict(roll_risk=0.0), dict(london_adr_skip=-1.0), dict(org_tell_level=0.0), dict(macro_no_move_wins=((700, 600),)),
               dict(tgif_timing=((600,),)), dict(london_adr_win=(500, 400)), dict(b11_inside_week_days=0),
               dict(daily_range_regime="x"), dict(drr_days=2), dict(drr_tests=("x",)), dict(drr_net_frac=0.0), dict(drr_range_mult=0.0)):
        with pytest.raises(ValueError):
            Params(**kw)


def test_tgif_model_is_an_umbrella_with_exceptions():
    p = Params(tgif_model=True)
    assert p.tgif and p.tgif_zone and p.tgif_htf_array and p.tgif_week_sweep and p.tgif_timing
    q = Params(tgif_model=True, tgif_model_skip=("tgif_zone", "tgif_timing"))
    assert q.tgif and q.tgif_htf_array and q.tgif_week_sweep and not q.tgif_zone and not q.tgif_timing
    r = replace(q, tgif_htf_array=False)                       # replace() re-runs the umbrella: the skip list is the way out
    assert r.tgif_htf_array
    r = replace(Params(tgif_model=True, tgif_model_skip=("tgif_htf_array",)), tgif_htf_array=False)
    assert not r.tgif_htf_array and r.tgif_week_sweep


def test_every_new_switch_has_a_study_variant():
    used = set()
    for k, v in study.DECISIONS.items():
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            replace(Params(), **v)                              # every variant builds
        used |= set(v)
    missing = [f for f in _block() if f not in used and f not in KNOBS]
    assert not missing, missing
    # the old build pins the new defaults back
    for preset in (study.CURRENT, study.PRE_OWNER):
        assert preset["skip_post_holiday_am"] is False and preset["london_adr_skip"] == 0.0
        assert preset["friday_slow_split"] is False


# --- the calendar -----------------------------------------------------------------------------------------------

def test_holiday_eve_and_post_holiday():
    assert C.is_holiday_eve(date(2026, 5, 22)) and C.is_post_holiday(date(2026, 5, 26))     # Memorial Day (Monday)
    assert C.is_holiday_eve(date(2026, 4, 2)) and not C.is_trading_day(date(2026, 4, 3))    # Good Friday
    assert C.is_post_holiday(date(2026, 4, 6))
    assert C.is_holiday_eve(date(2026, 12, 24)) and C.is_holiday_eve(date(2026, 12, 31))
    assert not C.is_holiday_eve(date(2026, 6, 23)) and not C.is_post_holiday(date(2026, 6, 23))
    assert not C.is_holiday_eve(date(2026, 4, 3))                                           # a holiday is not a trading day
    assert C.is_post_holiday(date(2026, 11, 27))                                            # the Friday after Thanksgiving
    # Columbus / Veterans Day are bank holidays: the market is open, only the opt-in counts the eve
    assert C.bank_holiday(date(2026, 10, 12)) and C.bank_holiday(date(2026, 11, 11)) and not C.bank_holiday(date(2026, 10, 19))
    assert not C.is_holiday_eve(date(2026, 11, 10)) and C.is_holiday_eve(date(2026, 11, 10), True)
    assert C.bank_holiday(date(2020, 11, 11)) and not C.bank_holiday(date(2020, 11, 12))
    assert C.bank_holiday(date(2022, 11, 11))                                                # Veterans Day on a Friday
    assert C.bank_holiday(date(2023, 11, 10))                                                # Nov 11 2023 is a Saturday: observed Friday


def test_week_helpers():
    assert C.week_dates(date(2026, 6, 25)) == [date(2026, 6, 22) + timedelta(days=k) for k in range(5)]
    assert C.holiday_in_week(date(2026, 5, 27)) and not C.holiday_in_week(date(2026, 6, 23))
    assert C.week_day_index(date(2026, 5, 26)) == 1 and C.week_day_index(date(2026, 5, 29)) == 4   # Monday holiday
    assert C.week_day_index(date(2026, 6, 22)) == 1 and C.week_day_index(date(2026, 6, 26)) == 5
    assert C.is_week_start(date(2026, 5, 26)) and C.is_week_start(date(2026, 6, 22)) and not C.is_week_start(date(2026, 6, 23))
    assert C.after_monday_holiday(date(2026, 5, 27)) and not C.after_monday_holiday(date(2026, 6, 23))
    assert C.prev_weekday(date(2026, 6, 22)) == date(2026, 6, 19) and C.next_weekday(date(2026, 6, 19)) == date(2026, 6, 22)
    assert C.is_market_holiday(date(2026, 4, 3)) and not C.is_market_holiday(date(2026, 4, 4))


def test_year_boundaries_and_early_close():
    assert C.first_trading_day_of_year(date(2027, 1, 4)) and not C.first_trading_day_of_year(date(2027, 1, 5))
    assert C.last_trading_day_of_year(date(2026, 12, 31)) and not C.last_trading_day_of_year(date(2026, 12, 30))
    assert C.early_close_min(date(2026, 11, 27)) == 780 and C.early_close_min(date(2026, 12, 24)) == 780
    assert C.early_close_min(date(2026, 6, 23)) == 0 and C.early_close_min(date(2026, 12, 25)) == 0
    assert C.early_close_min(date(2025, 7, 3)) == 780                                      # July 4 is a Friday: July 3 is short
    assert C.early_close_min(date(2026, 7, 3)) == 0                                        # 2026: July 3 is the observed holiday itself


def test_roll_week_and_month_counts():
    assert C.roll_week(date(2026, 3, 9)) and C.roll_week(date(2026, 3, 13)) and not C.roll_week(date(2026, 3, 6))
    assert not C.roll_week(date(2026, 3, 16)) and not C.roll_week(date(2026, 4, 8))        # April is not a quarterly month
    assert C.month_trading_day(date(2026, 6, 1)) == 1 and C.month_trading_day(date(2026, 6, 23)) == 16
    assert C.trading_days_between(date(2026, 6, 19), date(2026, 6, 23)) == 2               # Juneteenth is closed
    assert C.trading_days_between(date(2026, 6, 23), date(2026, 6, 23)) == 0


# --- candle patterns, ADR, weekly patterns (B11 / B11b / B11c / N8.5) -----------------------------------------------

def test_day_range_and_adr_follow_the_basis():
    h = sessions(date(2026, 6, 1), [(100, 110, 90, 105)] * 6)
    eth = {x.index[0].date(): (100, 130, 80, 105) for x in h}
    p, pe = Params(), Params(adr_basis="eth")
    assert DW.day_range(h[0], eth, p) == 20 and DW.day_range(h[0], eth, pe) == 50
    assert DW.day_range(h[0], None, pe) == 20                                # no eth data: the regular session
    assert DW.adr(h, p, eth, 5) == 20 and DW.adr(h, pe, eth, 5) == 50 and DW.adr(h[:4], p, None, 5) is None
    assert DW.adr(h, p, None, 5, offset=1) == 20 and DW.adr(h[:5], p, None, 5, offset=1) is None


def test_strong_day():
    up = daily(date(2026, 6, 4), 100, 120, 99, 119)
    dn = daily(date(2026, 6, 4), 119, 120, 99, 100)
    mid = daily(date(2026, 6, 4), 100, 120, 99, 110)
    assert DW.strong_day(up, 15.0, 1.0, 0.25) == 1 and DW.strong_day(dn, 15.0, 1.0, 0.25) == -1
    assert DW.strong_day(mid, 15.0, 1.0, 0.25) == 0                          # closes mid-range
    assert DW.strong_day(up, 30.0, 1.0, 0.25) == 0 and DW.strong_day(up, None, 1.0, 0.25) == 0   # range under ADR5


def test_candle_patterns_inside_outside_nr_and_the_eth_basis():
    p = Params(nr_tags=("nr3", "nr7", "inside_body"))
    h = sessions(date(2026, 6, 1), [(100, 110, 90, 105), (100, 112, 92, 99), (101, 105, 95, 100)])
    cp = DW.candle_patterns(h, p)
    assert cp["inside_day"] and cp["outside"] is None and cp["nr3"]
    h = sessions(date(2026, 6, 1), [(100, 110, 95, 105), (105, 115, 90, 92)])
    cp = DW.candle_patterns(h, p)
    assert cp["outside"] == "down" and (cp["out_hi"], cp["out_lo"]) == (115.0, 90.0) and not cp["inside_day"]
    h = sessions(date(2026, 6, 1), [(100, 110, 95, 105), (95, 120, 90, 118)])
    assert DW.candle_patterns(h, p)["outside"] == "up"
    # body inside the previous body although the range is not inside (inside_body)
    h = sessions(date(2026, 6, 1), [(100, 110, 90, 108), (103, 125, 80, 106)])
    cp = DW.candle_patterns(h, p)
    assert cp["inside_body"] and not cp["inside_day"]
    # NR7: yesterday the smallest of the last seven; the eth basis ranks the full sessions instead
    base = [(100, 110, 90, 105)] * 6 + [(100, 104, 98, 103)]
    h = sessions(date(2026, 6, 1), base)
    assert DW.candle_patterns(h, p)["nr7"]
    eth = {x.index[0].date(): (100, 130, 70, 105) for x in h[:6]}
    eth[h[6].index[0].date()] = (100, 150, 50, 103)                          # all-hours range: yesterday is the widest
    assert DW.candle_patterns(h, Params(adr_basis="eth"), eth)["nr7"] is False
    assert DW.candle_patterns(h, Params(adr_basis="rth"), eth)["nr7"] is True


def test_inside_week_expansion_and_scalp():
    p = Params(b11_inside_week="scalp", b11_inside_week_days=2)
    # three Monday-Friday weeks: wide, inside, then the target week
    w1 = sessions(date(2026, 6, 1), [(100, 120, 80, 100)] * 5)
    w2 = sessions(date(2026, 6, 8), [(100, 110, 90, 100)] * 5)
    d = date(2026, 6, 15)
    out = DW.week_patterns(w1 + w2, d, p)
    assert out["inside"] and out["waiting"] and not out["scalp"] and out["k"] == 0
    # Monday and Tuesday close inside the inside week's range: no expansion by candle 2 -> scalp only
    w3 = sessions(d, [(100, 105, 95, 100)] * 2)
    out = DW.week_patterns(w1 + w2 + w3, date(2026, 6, 17), p)
    assert out["inside"] and out["scalp"] and not out["expanded"] and out["k"] == 2
    w3 = sessions(d, [(100, 130, 95, 125)])                                    # Monday closes outside it: expanded
    out = DW.week_patterns(w1 + w2 + w3, date(2026, 6, 16), p)
    assert out["expanded"] and not out["scalp"] and not out["waiting"]
    assert not DW.week_patterns(w2 + w1, d, p)["inside"]                        # wide after narrow: not an inside week
    assert DW.week_patterns(w1[:3], d, p) == dict(inside=False, k=0, expanded=False, waiting=False, scalp=False)


def test_plan_tags_for_candle_patterns():
    hist = sessions(date(2026, 6, 10), [(100, 110, 90, 105), (100, 112, 92, 99), (101, 105, 95, 100)])
    p = Params(**BASE, nr_tags=("nr3",), nr_expansion="no_chop_skip", b11_inside_expansion="tag", outside_day_rule="tag")
    ctx = S.DayCtx(day(A_ROWS, d=NORMAL), NORMAL, hist, 5)
    P = DW.plan(ctx, hist, p)
    assert {"inside_day", "b11_inside_expansion", "nr3", "nr_expansion"} <= P.tags and P.expansion == {"inside_day", "nr"}
    hist = sessions(date(2026, 6, 10), [(100, 110, 95, 105), (105, 115, 90, 92)])
    P = DW.plan(ctx, hist, replace(p, outside_day_rule="block"))
    assert "outside_down" in P.tags and "outside_day_rule" in P.tags and P.info["outside_day"][0] == "down"
    P = DW.plan(ctx, hist, replace(p, outside_day_rule="block", outside_day_mirror=False))
    hist_up = sessions(date(2026, 6, 10), [(100, 110, 95, 105), (95, 120, 90, 118)])
    P = DW.plan(ctx, hist_up, replace(p, outside_day_rule="block", outside_day_mirror=False))
    assert "outside_up" in P.tags and "outside_day" not in P.info              # the mirror is a switch


def test_expansion_due_tag_and_adr_columns():
    hist = history(NORMAL, n=8)
    hist[-1] = daily(hist[-1].index[0].date(), 100, 101, 99, 100)               # a tiny range yesterday
    p = Params(**BASE, expansion_due=True, expansion_frac=1.0)
    ctx = S.DayCtx(day(A_ROWS, d=NORMAL), NORMAL, hist, 5)
    P = DW.plan(ctx, hist, p)
    assert "expansion_due" in P.tags and P.info["expansion_due"] and P.info["adr_prev"] < 0.2
    assert P.info["adr5_prev"] == pytest.approx(np.mean([DW.day_range(x, None, p) for x in hist[-5:]]))
    P = DW.plan(S.DayCtx(day(A_ROWS, d=NORMAL), NORMAL, history(NORMAL), 5), history(NORMAL), p)
    assert "expansion_due" not in P.tags                                         # yesterday was a normal range


# --- the plan: calendar rules (N7) ---------------------------------------------------------------------------------

def _plan(d, p=None, hist=None, rows=A_ROWS, **kw):
    hist = hist or history(d)
    ctx = S.DayCtx(day(rows, d=d), d, hist, 5)
    ctx.hist = hist
    ctx.lock = {}
    ctx.eth = kw.pop("eth", None)
    P = DW.plan(ctx, hist, p or Params(**BASE), **kw)
    return ctx, P


def test_calendar_tags():
    _, P = _plan(date(2026, 5, 22))
    assert "holiday_eve" in P.tags and not (P.tags & {"post_holiday", "holiday_week"})
    _, P = _plan(date(2026, 5, 26))
    assert {"post_holiday", "holiday_week", "monday_like"} <= P.tags and P.info["week_idx"] == 1
    _, P = _plan(date(2026, 5, 27))
    assert "wed_reversal" in P.tags
    _, P = _plan(date(2026, 5, 29))
    assert "holiday_week_thu_fri" in P.tags
    _, P = _plan(date(2026, 12, 31))
    assert {"last_day", "holiday_eve"} <= P.tags
    _, P = _plan(date(2027, 1, 4))
    assert {"first_day", "post_holiday"} <= P.tags
    _, P = _plan(date(2026, 8, 12))
    assert "august" in P.tags
    _, P = _plan(date(2026, 3, 11))
    assert "roll_week" in P.tags
    _, P = _plan(date(2026, 11, 27))
    assert "early_close" in P.tags
    _, P = _plan(NORMAL)
    assert not (P.tags & {"holiday_eve", "post_holiday", "holiday_week", "first_day", "last_day", "august", "roll_week"})


def test_holiday_eve_and_post_holiday_blocks_are_the_ny_am_only():
    eve = date(2026, 5, 22)
    _, P = _plan(eve, Params(**BASE, skip_holiday_eve=True))
    assert P.static_reason("AM", 600) == "holiday_eve" and P.static_reason("PM", 820) == "holiday_eve"
    assert P.static_reason("LON", 200) == "holiday_eve"                              # the whole day is skipped
    _, P = _plan(eve, Params(**BASE))
    assert P.static_reason("AM", 600) is None                                         # off by default
    post = date(2026, 5, 26)
    _, P = _plan(post)
    for s_ in ("AM", "PRE9", "NEWS"):
        assert P.static_reason(s_, 560) == "post_holiday_am"
    for s_ in ("PM", "LUNCH", "LON", "PRE7", "PRE8"):                                 # N7.2: the NY AM family only
        assert P.static_reason(s_, 500) is None, s_
    _, P = _plan(post, Params(**BASE, skip_post_holiday_am=False))
    assert P.static_reason("AM", 600) is None


def test_post_holiday_am_blocks_the_main_engine_but_not_london_or_ma_deuce():
    post = date(2026, 5, 26)
    tr, sk, fn = funnel(post)
    assert not tr and fn.get("x_dw_post_holiday_am", 0) >= 1
    tr2, _, _ = funnel(post, skip_post_holiday_am=False)
    assert len(tr2) == 1 and tr2[0].session == "AM"
    # the same Tuesday as an ordinary day: untouched
    assert len(go(NORMAL)[0]) == 1


def test_holiday_eve_skips_the_whole_day_and_first_day_rules():
    tr, sk = go(date(2026, 5, 22), skip_holiday_eve=True)
    assert not tr and sk and sk[0][2:] == ("day_week", "holiday_eve")
    assert len(go(date(2026, 5, 22))[0]) == 1
    # first trading day of the year: wait / skip the AM (Jan 4 2027 is also post-holiday: switch that block off)
    d = date(2027, 1, 4)                                                                    # (an ISM day: the order is armed after 10:00)
    kw = dict(start="10:00", news_wait="off", skip_post_holiday_am=False)
    tr, _ = go(d, **kw)
    assert len(tr) == 1
    tr, _, fn = funnel(d, first_day_skip_am=True, **kw)
    assert not tr and fn["x_dw_first_day_am"] >= 1
    tr, _, fn = funnel(d, first_day_wait=630, **kw)                                        # no AM entry before 10:30
    assert not tr and fn["x_dw_first_day_wait"] >= 1
    tr, _, fn = funnel(d, year_first_am_from=630, **kw)
    assert not tr and fn["x_dw_first_day_wait"] >= 1
    assert len(go(d, first_day_wait=600, **kw)[0]) == 1                                    # a wait that ends before the order


def test_low_vol_last_day_august_and_roll_week():
    d = date(2026, 12, 31)
    _, P = _plan(d, Params(**BASE, low_vol_inside="skip"))
    assert "low_vol_inside" in P.tags and P.static_reason("AM", 600) == "low_vol_inside"
    _, P = _plan(d, Params(**BASE, low_vol_inside="scalp"))
    assert P.scalp == {"low_vol_inside": None} and DW.scalp_now(SimpleNamespace(dplan=P), Params(), "AM") == "low_vol_inside"
    _, P = _plan(date(2026, 12, 24), Params(**BASE, low_vol_inside="skip", low_vol_holiday_adj=True))
    assert P.static_reason("AM", 600) == "low_vol_inside"                                    # the days next to a holiday too
    _, P = _plan(date(2026, 12, 24), Params(**BASE, low_vol_inside="skip"))
    assert P.static_reason("AM", 600) is None
    # August: skip from the day; risk multiplier from the day
    ctx, P = _plan(date(2026, 8, 12), Params(**BASE, skip_august=True, august_from_day=15))
    assert P.static_reason("AM", 600) is None
    _, P = _plan(date(2026, 8, 17), Params(**BASE, skip_august=True, august_from_day=15))
    assert P.static_reason("AM", 600) == "august"
    # roll week: skip; risk
    _, P = _plan(date(2026, 3, 11), Params(**BASE, skip_roll_week=True))
    assert P.static_reason("AM", 600) == "roll_week"
    ctx, P = _plan(date(2026, 3, 11), Params(**BASE, roll_risk=0.5))
    lvt = []
    assert DW.day_risk(ctx, Params(roll_risk=0.5), lvt) == 0.5 and lvt == ["size_roll_week"]
    ctx, P = _plan(date(2026, 8, 17), Params(**BASE, august_risk=0.5, august_from_day=15))
    assert DW.day_risk(ctx, Params(august_risk=0.5, august_from_day=15)) == 0.5
    ctx, P = _plan(date(2026, 8, 12), Params(**BASE, august_risk=0.5, august_from_day=15))
    assert DW.day_risk(ctx, Params(august_risk=0.5, august_from_day=15)) == 1.0
    assert DW.day_risk(ctx, Params()) == 1.0


def test_roll_week_from_the_data_flag():
    d = date(2026, 6, 23)                                                                       # not a calendar roll week
    ctx = S.DayCtx(day(A_ROWS, d=d), d, history(d), 5)
    assert "roll_week" not in DW._calendar_tags(d, Params(roll_week_src="calendar"), ctx)
    ctx.roll_at = ctx.start                                                                     # the roll flag is known from the first bar
    assert {"roll_week", "roll_day"} <= DW._calendar_tags(d, Params(roll_week_src="data"), ctx)
    assert {"roll_week", "roll_day"} <= DW._calendar_tags(d, Params(roll_week_src="either"), ctx)
    assert "roll_week" not in DW._calendar_tags(d, Params(roll_week_src="calendar"), ctx)
    ctx.roll_at = ctx.start + 100                                                               # known only mid-day: not a static tag
    assert "roll_week" not in DW._calendar_tags(d, Params(roll_week_src="data"), ctx)
    ctx.roll_at = None
    assert "roll_week" not in DW._calendar_tags(d, Params(roll_week_src="data"), ctx)
    cal = date(2026, 3, 11)                                                                     # a calendar roll week without a flag
    ctx = S.DayCtx(day(A_ROWS, d=cal), cal, history(cal), 5)
    assert "roll_week" in DW._calendar_tags(cal, Params(roll_week_src="either"), ctx)
    assert "roll_week" not in DW._calendar_tags(cal, Params(roll_week_src="data"), ctx)


def test_early_close_flat_and_the_flat_helper():
    p = Params()
    assert DW.flat_for(date(2026, 11, 27), p, 975) == 780 and DW.flat_for(NORMAL, p, 975) == 975
    assert DW.flat_for(date(2026, 11, 27), Params(early_close_flat=False), 975) == 975
    assert DW.flat_for(date(2026, 11, 27), p, 700) == 700
    # the engine: a trade on the early-close day is flat at 13:00 (the day is built to 16:15, a custom frame)
    tr, _ = go(date(2026, 11, 27), rows=A_ROWS[:6], skip_post_holiday_am=False, london_adr_skip=0.0, tail=100.5)
    assert tr and all(t.exits[-1][0].hour * 60 + t.exits[-1][0].minute <= 775 for t in tr)


# --- the week: budget (D19 / X15), objective (X15d), Friday week-done (N10.4) -------------------------------------

I930 = 114                                                    # the 09:30 bar of a 5m day frame that starts at 00:00


def _wk_ctx(d, hist, p, rows=A_ROWS, base=100.0, eth=None, eve=None, week=None):
    ctx = S.DayCtx(day(rows, d=d, base=base), d, hist, 5)
    ctx.hist, ctx.lock, ctx.eth = hist, {}, eth
    ctx.dplan = DW.plan(ctx, hist, p, week, eve)
    return ctx


def test_week_budget_block_and_week_left():
    p = Params(**BASE, max_trades_week=3)
    _, P = _plan(NORMAL, p, week=dict(n=1))
    assert P.info["week_left"] == 2 and P.static_reason("AM", 600) is None
    _, P = _plan(NORMAL, p, week=dict(n=3))
    assert P.info["week_left"] == 0 and P.static_reason("PM", 820) == "week_cap"
    _, P = _plan(NORMAL, Params(**BASE), week=dict(n=3))
    assert "week_left" not in P.info
    tr, sk = go(NORMAL, max_trades_week=3, week=dict(n=3))
    assert not tr and sk[0][2:] == ("day_week", "week_cap")
    assert len(go(NORMAL, max_trades_week=3, week=dict(n=2))[0]) == 1


def test_budget_full_counts_only_trades_filled_by_then():
    ctx = SimpleNamespace(dplan=SimpleNamespace(info=dict(week_left=2)))
    ts = pd.Timestamp("2026-06-23 10:00", tz="America/New_York")
    mk = lambda m: SimpleNamespace(entry_time=ts + pd.Timedelta(minutes=m))
    a, b, c = mk(-30), mk(0), mk(30)
    assert not DW.budget_full(ctx, ts, [a], [c])                  # c fills later: not counted
    assert DW.budget_full(ctx, ts, [a], [b])                      # a filled earlier, b on this bar
    assert not DW.budget_full(ctx, ts, [a], [a])                  # the same trade twice counts once
    assert DW.budget_full(ctx, ts + pd.Timedelta(minutes=30), [a, c], [b])
    assert not DW.budget_full(SimpleNamespace(dplan=SimpleNamespace(info={})), ts, [a, b, c], [])
    assert not DW.budget_full(SimpleNamespace(), ts, [a, b, c], [])


def test_week_state_from_the_trade_rows_and_paper_files(tmp_path):
    rows = [dict(date=date(2026, 6, 22), net=100.0, final_hit=True), dict(date=date(2026, 6, 23), net=-40.0, final_hit=False),
            dict(date=date(2026, 6, 24), net=10.0, final_hit=True), dict(date=date(2026, 6, 15), net=999.0, final_hit=True)]
    st = B.week_state(rows, date(2026, 6, 24))                    # the trades before Wednesday, this week only
    assert st == dict(n=2, net=60.0, final_hits=1, all_final=False)
    assert B.week_state([rows[0]], date(2026, 6, 23))["all_final"] is True
    assert B.week_state([], date(2026, 6, 23)) == dict(n=0, net=0.0, final_hits=0, all_final=False)
    from mentorship import paper
    hdr = "entry_time,net,final_hit\n"
    (tmp_path / "paper_ES_20260622.csv").write_text(hdr + "2026-06-22 09:50,100.0,True\n2026-06-22 09:50,100.0,True\n")
    (tmp_path / "paper_ES_20260623.csv").write_text(hdr + "2026-06-23 10:00,-40.0,False\n")
    (tmp_path / "paper_ES_20260615.csv").write_text(hdr + "2026-06-15 10:00,5.0,True\n")
    (tmp_path / "paper_NQ_20260622.csv").write_text(hdr + "2026-06-22 10:00,5.0,True\n")
    st = paper.week_state(tmp_path, "ES", date(2026, 6, 24))
    assert st == dict(n=2, net=60.0, final_hits=1, all_final=False)           # a re-logged trade counts once, other weeks / symbols out
    assert paper.week_state(tmp_path, "ES", date(2026, 6, 22))["n"] == 0


def test_weekly_objective_levels_and_delivery():
    p = Params(**BASE, week_done_on_draw="skip")
    prior = sessions(date(2026, 6, 8), [(100, 110, 90, 100)] * 5)                   # the prior week: 110 / 90, last close 100
    # Wednesday: Monday / Tuesday of this week completed (no gap; flat inside the prior week's range)
    cur = sessions(date(2026, 6, 15), [(100, 105, 95, 100), (100, 108, 96, 100)])
    hist = prior + cur
    d = date(2026, 6, 17)
    ctx = _wk_ctx(d, hist, p)
    lv = DW._week_objective_levels(ctx, hist, d, p, None)
    assert lv["pwh"] == (110.0, "high") and lv["pwl"] == (90.0, "low")
    assert DW.objective_delivered(ctx, hist, d, p, None, None) == []
    assert "week_done" not in ctx.dplan.tags
    # today's bars trade through the prior week's high: delivered by the closed bar, not before
    rows = [(100, 100.1, 99.9, 100)] * 3 + [(100, 111, 100, 110)]
    ctx = _wk_ctx(d, hist, p, rows=rows)
    assert DW.objective_delivered(ctx, hist, d, p, None, ctx.start + I930 + 2) == []
    assert DW.objective_delivered(ctx, hist, d, p, None, ctx.start + I930 + 3) == ["pwh"]
    assert DW.week_range_so_far(ctx, hist, d, p, None, ctx.start + I930 + 3)[0] == 111.0
    assert DW.gate(ctx, p, "AM", ctx.start + I930 + 3, 585) == "x_dw_week_done"
    assert DW.gate(ctx, p, "AM", ctx.start + I930 + 2, 580) is None
    # the completed sessions already delivered it: the day is skipped by the plan (a static block)
    hist2 = prior + sessions(date(2026, 6, 15), [(100, 111, 95, 100)])
    ctx = _wk_ctx(d, hist2, p)
    assert ctx.dplan.static_reason("AM", 600) == "week_done" and "week_done" in ctx.dplan.tags
    ctx = _wk_ctx(d, hist2, replace(p, week_done_on_draw="tag"))
    assert ctx.dplan.static_reason("AM", 600) is None and "week_done" in ctx.dplan.tags
    # nearest: only the objective nearest to the week's first open counts (the low is nearer than the high)
    hist3 = prior + sessions(date(2026, 6, 15), [(94, 111, 93, 100)])
    pn = replace(p, week_done_pick="nearest", week_done_levels=("pwh", "pwl"))
    ctx = _wk_ctx(d, hist3, pn)
    assert DW.objective_delivered(ctx, hist3, d, pn, None, None) == []                 # pwl (90) is the nearest and untouched


def test_nwog_ce_objective_on_the_first_day_of_the_week_and_later():
    p = Params(**BASE, week_done_on_draw="tag", week_done_levels=("nwog_ce",))
    hist = sessions(date(2026, 6, 8), [(100, 110, 90, 100)] * 5)                      # Friday close 100
    mon = date(2026, 6, 15)
    # the Sunday open 103: the gap's CE is 101.5 and it is delivered once price trades down to it (ce_up)
    ctx = _wk_ctx(mon, hist, p, eve=(103.0, 103.5, 102.5, 103.0), base=105.0, rows=[(105, 105.1, 104.9, 105)] * 3)
    lv = DW._week_objective_levels(ctx, hist, mon, p, None)
    assert lv["nwog_ce"] == (101.5, "ce_up") and lv["_nwog"] == (100.0, 103.0)
    assert DW.objective_delivered(ctx, hist, mon, p, None, ctx.start + I930) == []    # base 105: never back to the CE
    ctx = _wk_ctx(mon, hist, p, eve=(103.0, 103.5, 102.5, 103.0), base=100.0)         # the day's bars trade through it
    assert DW.objective_delivered(ctx, hist, mon, p, None, ctx.start + I930) == ["nwog_ce"]
    # no evening data on the first day: nothing to measure the gap from
    ctx = _wk_ctx(mon, hist, p, eve=None)
    assert "nwog_ce" not in DW._week_objective_levels(ctx, hist, mon, p, None)
    # Wednesday: the first session's all-hours open from eth is the Sunday open; the Friday close is the 17:00 close
    wed = date(2026, 6, 17)
    h2 = hist + sessions(mon, [(100, 105, 99, 101), (101, 106, 100, 102)])
    eth = {date(2026, 6, 12): (100.0, 111.0, 89.0, 102.0), mon: (96.0, 105.0, 95.0, 101.0)}
    ctx = _wk_ctx(wed, h2, p, eth=eth, base=100.0)
    lv = DW._week_objective_levels(ctx, h2, wed, p, eth)
    assert lv["_nwog"] == (102.0, 96.0) and lv["nwog_ce"] == (99.0, "ce_dn")           # the eth close, not the 16:00 close
    lv = DW._week_objective_levels(ctx, h2, wed, p, None)                              # regular sessions only: no gap (100 -> 100)
    assert "nwog_ce" not in lv


def test_friday_week_done_and_friday_objective():
    prior = sessions(date(2026, 6, 8), [(100, 110, 90, 100)] * 5)
    fri = date(2026, 6, 26)
    thu_hi = sessions(date(2026, 6, 22), [(100, 111, 95, 100)] * 4)
    ctx = _wk_ctx(fri, prior + thu_hi, Params(**BASE, friday_week_done="draw"))
    assert ctx.dplan.static_reason("AM", 600) == "friday_week_done" and "friday_week_done" in ctx.dplan.tags
    hist = prior + sessions(date(2026, 6, 22), [(100, 105, 95, 100)] * 4)
    assert _wk_ctx(fri, hist, Params(**BASE, friday_week_done="draw")).dplan.static_reason("AM", 600) is None   # nothing delivered
    # "trades": the week traded and every trade hit its last target
    p = Params(**BASE, friday_week_done="trades")
    assert _wk_ctx(fri, hist, p, week=dict(n=2, all_final=True)).dplan.static_reason("AM", 600) == "friday_week_done"
    assert _wk_ctx(fri, hist, p, week=dict(n=2, all_final=False)).dplan.static_reason("AM", 600) is None
    assert _wk_ctx(fri, hist, p, week=dict(n=0, all_final=False)).dplan.static_reason("AM", 600) is None
    assert _wk_ctx(NORMAL, hist, p, week=dict(n=2, all_final=True)).dplan.static_reason("AM", 600) is None   # Fridays only
    hist_hi = prior + thu_hi
    for mode in ("skip", "scalp", "tag"):
        ctx = _wk_ctx(fri, hist_hi, Params(**BASE, friday_objective=mode))
        assert "friday_objective_met" in ctx.dplan.tags
        assert (ctx.dplan.static_reason("AM", 600) == "friday_objective") == (mode == "skip")
        assert ("friday_objective" in ctx.dplan.scalp) == (mode == "scalp")


def test_final_hit_is_set_by_every_engine_for_the_week_state():
    """N10.4 friday_week_done="trades" needs final_hit on Silver Bullet and Ma Deuce trades too."""
    import inspect
    from mentorship import sb_model, pre_open
    assert "final_hit" in inspect.getsource(sb_model) and "final_hit" in inspect.getsource(pre_open.run_ma_deuce)


# (the no-look-ahead runs of every switch - one variant per run, 5m and 1m with Silver Bullet / Ma Deuce - are in
#  test_day_week_lookahead.py)
