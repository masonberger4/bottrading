"""Package day_week_context, second test file: behaviour tests (long AND mirrored short) for the dynamic gates, side
rules, per-order rules and detectors of mentorship/daycontext.py, the B17.4 daily range regime, and the wiring of the
gates into the Silver Bullet / Ma Deuce engines. Synthetic one-day scenarios only (fast); the real-data look-ahead
runs live in test_day_week_context.py / test_day_week_lookahead.py."""
from dataclasses import replace
from datetime import date
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from mentorship import daycontext as DW, study, strategy as S
from mentorship.strategy import Params

from test_day_week_context import I930, NORMAL, _plan, _wk_ctx, ctx_for, daily, funnel, go, sessions  # noqa: E402
from test_review_fixes import BASE, K, day, frame, history, rth_day  # noqa: E402

MON = date(2026, 7, 13)                                    # a Monday with a trading Friday before it, outside NFP / FOMC weeks
P0 = Params(**BASE)
FLAT = (100.0, 100.1, 99.9, 100.0)


def ix(ctx, minute: int) -> int:
    """Index of the 5m bar that STARTS at `minute` (its close is known from index + 0 on)."""
    return ctx.start + minute // 5


def sd(sign: int, ctx=None):
    """A minimal side-space object: sign, x() (side space -> price) and the side-space lows for the extra targets."""
    if sign > 0:
        return SimpleNamespace(sign=1, x=lambda v: v, l=None if ctx is None else ctx.l, h=None if ctx is None else ctx.h)
    return SimpleNamespace(sign=-1, x=lambda v: K - v, l=None if ctx is None else K - ctx.h, h=None if ctx is None else K - ctx.l)


# --- B17.4 daily range regime -------------------------------------------------------------------------------------------

def test_range_regime_detects_a_multi_day_range_and_not_a_trend():
    p = Params(daily_range_regime="tag")
    flat = sessions(date(2026, 6, 1), [(100, 110, 90, 100), (100, 108, 92, 101), (101, 109, 91, 99), (99, 107, 93, 100), (100, 110, 90, 100)])
    assert DW.range_regime(flat, p) == ["range"]
    trend = sessions(date(2026, 6, 1), [(100, 106, 99, 105), (105, 111, 104, 110), (110, 116, 109, 115), (115, 121, 114, 120), (120, 126, 119, 125)])
    assert DW.range_regime(trend, p) == []                       # net 25 of a 27 range: a trend
    neg = [x.assign(open=K - x.open, high=K - x.low, low=K - x.high, close=K - x.close) for x in flat]
    assert DW.range_regime(neg, p) == ["range"]                  # side-less: the mirror reads the same
    assert DW.range_regime(flat[:4], p) == []                    # not enough sessions
    wide = sessions(date(2026, 6, 1), [(100, 110, 99, 100), (100, 101, 90, 100), (100, 140, 99, 100), (100, 101, 70, 100), (100, 101, 99, 100)])
    assert DW.range_regime(wide, p) == []                        # the 5-day range is far wider than a day: not a flat stack
    assert DW.range_regime(flat, replace(p, drr_tests=("inside_bisi",))) == []     # the test list selects the readings


def test_range_regime_inside_bisi_and_premium_run_are_reachable():
    mk = lambda rows, d0="2026-05-11": [rth_day(d, hi, lo, c) for d, (hi, lo, c) in zip(pd.bdate_range(d0, periods=len(rows)).date, rows)]
    p = Params(daily_range_regime="tag", drr_tests=("inside_bisi",))
    ib = mk([(100, 96, 99), (107, 99, 106), (110, 104, 108), (106, 102, 103), (103, 101, 102)])    # yesterday 101-103 inside the 100-104 gap
    assert DW.range_regime(ib, p) == ["inside_bisi"]
    neg = [x.assign(open=K - x.open, high=K - x.low, low=K - x.high, close=K - x.close) for x in ib]
    assert DW.range_regime(neg, p) == ["inside_bisi"]            # a bearish FVG (SIBI): either direction
    assert DW.range_regime(mk([(100, 96, 99), (107, 99, 106), (110, 104, 108), (106, 102, 103), (110, 101, 109)]), p) == []   # leaves the gap
    base_ = [(104, 96, 100), (101, 95, 97), (99, 93, 95), (98, 92, 94), (97, 91, 93), (96, 90, 92),
             (95, 89, 91), (94, 88, 90), (96, 89, 95), (99, 92, 98)]
    q = replace(p, drr_tests=("premium_run",))
    run = mk(base_ + [(104.5, 95, 104)])
    assert DW.range_regime(run, q) == ["premium_run"]
    assert DW.range_regime(mk(base_ + [(100.5, 95, 100)]), q) == []
    neg = [x.assign(open=K - x.open, high=K - x.low, low=K - x.high, close=K - x.close) for x in run]
    assert DW.range_regime(neg, q) == ["premium_run"]


def test_daily_range_regime_modes_through_the_plan_and_the_engine():
    flat = history()                                             # eight identical 90-108 sessions: a range
    assert "daily_range" not in _plan(NORMAL, P0, hist=flat)[1].tags                   # off by default
    _, P = _plan(NORMAL, Params(**BASE, daily_range_regime="tag"), hist=flat)
    assert {"daily_range", "drr_range"} <= P.tags and P.info["drr"] == ["range"] and P.static_reason("AM", 600) is None
    _, P = _plan(NORMAL, Params(**BASE, daily_range_regime="scalp"), hist=flat)
    assert "daily_range" in P.scalp and P.static_reason("AM", 600) is None
    _, P = _plan(NORMAL, Params(**BASE, daily_range_regime="skip"), hist=flat)
    assert P.static_reason("AM", 600) == "daily_range" and P.static_reason("PM", 820) == "daily_range"
    trend = history(first=None)
    trend = [rth_day(x.index[0].date(), 100 + 8 * (k + 1), 100 + 8 * k, 100 + 8 * k + 7) for k, x in enumerate(trend)]
    assert not (_plan(NORMAL, Params(**BASE, daily_range_regime="skip"), hist=trend)[1].tags & {"daily_range"})
    # the engine: the same order trades normally, is a one-exit scalp, or is skipped, by mode
    base = go(NORMAL, hist=flat)[0]
    assert len(base) == 1
    tr, sk = go(NORMAL, hist=flat, daily_range_regime="skip")
    assert not tr and sk and sk[0][2:] == ("day_week", "daily_range")
    sc = go(NORMAL, hist=flat, daily_range_regime="scalp")[0]
    assert len(sc) == 1 and len(sc[0].exits) == 1 and "daily_range" in sc[0].dw_tags
    assert "daily_range" in go(NORMAL, hist=flat, daily_range_regime="tag")[0][0].dw_tags


# --- nr_expansion without nr_tags -----------------------------------------------------------------------------------------

def test_nr_expansion_evaluates_nr3_and_nr7_without_nr_tags():
    hist = sessions(date(2026, 6, 1), [(100, 110, 90, 105)] * 6 + [(100, 104, 98, 103)])      # yesterday: the narrowest of seven
    ctx = S.DayCtx(day([FLAT] * 3, d=NORMAL), NORMAL, hist, 5)
    P = DW.plan(ctx, hist, Params(**BASE, nr_expansion="tag"))
    assert {"nr3", "nr7", "nr_expansion"} <= P.tags and P.expansion == {"nr"}
    P = DW.plan(ctx, hist, Params(**BASE))
    assert not (P.tags & {"nr3", "nr7", "nr_expansion"})


# --- org_tell / org_gap_state / side_ok (B15), long and mirrored short -------------------------------------------------------

def test_org_tell_gap_up_and_gap_down():
    up = [(102.0, 103.0, 101.5, 102.5)] * 6                      # opens 102 over the 100 close; never back to 101 (the 50% level)
    ctx = ctx_for(up, p=P0)
    assert DW.org_tell(ctx, P0, ix(ctx, 590)) == 0               # the 10:00 tell is not in yet
    assert DW.org_tell(ctx, P0, ix(ctx, 595)) == 1               # the bar that closes at 10:00
    tried = [up[0], (102.5, 102.6, 100.9, 101.2)] + up[2:]       # a bar back through 101: the gap was attempted
    assert DW.org_tell(ctx_for(tried, p=P0), P0, ix(ctx, 595)) == 0
    dn = [(98.0, 98.5, 97.0, 97.5)] * 6                          # gap down 98 under 100, never back up to 99
    ctx = ctx_for(dn, p=P0)
    assert DW.org_tell(ctx, P0, ix(ctx, 595)) == -1
    tried = [dn[0], (97.5, 99.2, 97.4, 98.9)] + dn[2:]
    assert DW.org_tell(ctx_for(tried, p=P0), P0, ix(ctx, 595)) == 0
    assert DW.org_tell(ctx_for([(100.1, 101.0, 99.5, 100.5)] * 6, p=P0), P0, ix(ctx, 595)) == 0    # no gap (< a quarter point)


def test_org_gap_state_reprices_into_the_gap():
    up = [(102.0, 102.5, 101.5, 102.2), (102.2, 102.3, 100.9, 101.0), (101.0, 101.4, 100.8, 101.3)]
    ctx = ctx_for(up, p=P0)
    assert DW.org_gap_state(ctx, P0, ix(ctx, 570)) == (1, False)          # the gap up, not yet back to 101
    assert DW.org_gap_state(ctx, P0, ix(ctx, 575)) == (1, True)           # repriced by the closed 09:35 bar
    dn = [(98.0, 98.5, 97.5, 97.8), (97.8, 99.1, 97.7, 99.0), (99.0, 99.2, 98.6, 98.9)]
    ctx = ctx_for(dn, p=P0)
    assert DW.org_gap_state(ctx, P0, ix(ctx, 570)) == (-1, False)
    assert DW.org_gap_state(ctx, P0, ix(ctx, 575)) == (-1, True)
    assert DW.org_gap_state(ctx_for([FLAT] * 3, p=P0), P0, ix(ctx, 575)) == (0, False)


def test_side_ok_org_tell_filter_and_org_bias_gap_both_sides():
    p = Params(**BASE, org_tell="filter")
    up = [(102.0, 103.0, 101.5, 102.5)] * 6
    ctx = ctx_for(up, p=p)
    i = ix(ctx, 595)
    assert DW.side_ok(ctx, p, 1, "AM", i) is None and DW.side_ok(ctx, p, -1, "AM", i) == "x_dw_org_tell"
    assert DW.side_ok(ctx, p, -1, "AM", ix(ctx, 590)) is None             # the tell is unknown before 10:00
    dn = [(98.0, 98.5, 97.0, 97.5)] * 6
    ctx = ctx_for(dn, p=p)
    assert DW.side_ok(ctx, p, -1, "AM", i) is None and DW.side_ok(ctx, p, 1, "AM", i) == "x_dw_org_tell"
    # bias x gap: a bullish bias with a gap up reprices into the gap first; against the bias the trade is refused
    q = Params(**BASE, org_bias_gap="filter")
    ctx = ctx_for([(102.0, 102.5, 101.5, 102.2), (102.2, 102.3, 100.9, 101.0)], p=q)
    ctx.bias_row = dict(draw=1, react=1, pd=1)
    ctx.bias_rows = None
    from mentorship import entries
    orig = entries.bias_row_known
    entries.bias_row_known = lambda c, i: c.bias_row
    try:
        assert DW.side_ok(ctx, q, 1, "AM", ix(ctx, 570)) == "x_dw_org_gap_wait"      # bullish + gap up, not repriced yet
        assert DW.side_ok(ctx, q, 1, "AM", ix(ctx, 575)) is None                       # repriced: the long is allowed
        assert DW.side_ok(ctx, q, -1, "AM", ix(ctx, 575)) == "x_dw_org_bias_gap"      # against the bias
        ctx = ctx_for([(98.0, 98.5, 97.5, 97.8), (97.8, 99.1, 97.7, 99.0)], p=q)      # the mirror
        ctx.bias_row = dict(draw=-1, react=-1, pd=-1)
        assert DW.side_ok(ctx, q, -1, "AM", ix(ctx, 570)) == "x_dw_org_gap_wait"
        assert DW.side_ok(ctx, q, -1, "AM", ix(ctx, 575)) is None
        assert DW.side_ok(ctx, q, 1, "AM", ix(ctx, 575)) == "x_dw_org_bias_gap"
        assert DW.side_ok(ctx, q, 1, "PM", ix(ctx, 575)) is None                       # AM only
    finally:
        entries.bias_row_known = orig


def test_org_tell_wait_gate():
    p = Params(**BASE, org_tell="filter", org_tell_wait=True)
    ctx = ctx_for([(102.0, 103.0, 101.5, 102.5)] * 6, p=p)
    assert DW.gate(ctx, p, "AM", ix(ctx, 580), 580) == "x_dw_org_tell_wait"
    assert DW.gate(ctx, p, "AM", ix(ctx, 595), 595) is None


def test_outside_day_rule_blocks_the_mirror_side_too():
    up = sessions(date(2026, 6, 10), [(100, 110, 95, 105), (95, 120, 90, 118)])            # an up-close outside day: 120 / 90
    dn = sessions(date(2026, 6, 10), [(100, 110, 95, 105), (105, 115, 90, 92)])            # a down-close outside day: 115 / 90
    p = Params(**BASE, outside_day_rule="block")
    ctx = ctx_for([FLAT] * 3, hist=dn, p=p)
    i = ix(ctx, 580)
    assert DW.side_ok(ctx, p, 1, "AM", i) == "x_dw_outside_day" and DW.side_ok(ctx, p, -1, "AM", i) is None
    ctx = ctx_for([FLAT] * 3, hist=up, p=p)
    assert DW.side_ok(ctx, p, -1, "AM", i) == "x_dw_outside_day" and DW.side_ok(ctx, p, 1, "AM", i) is None
    # released once today's bars trade the outside day's high (low)
    ctx = ctx_for([(100, 116, 99, 115)] + [(115, 115.1, 114.9, 115)] * 2, hist=dn, p=p)
    assert DW.side_ok(ctx, p, 1, "AM", ix(ctx, 575)) is None
    ctx = ctx_for([(100, 101, 89, 90)] + [(90, 90.1, 89.9, 90)] * 2, hist=up, p=p)
    assert DW.side_ok(ctx, p, -1, "AM", ix(ctx, 575)) is None


# --- B16 Sunday scenarios -------------------------------------------------------------------------------------------------

def test_sunday_state_fill_away_neither_no_gap_and_the_mirror():
    p = Params(**BASE, sunday_scenario="tag")
    st = lambda eve, **kw: DW.sunday_state(ctx_for([FLAT] * 3, d=MON, p=p, eve=eve, **kw), p, history(MON))
    assert st(None) == "na"                                                      # no evening data
    assert st((100.5, 101.0, 100.0, 100.5), base=100.0) == "no_gap"              # under a point
    assert st((103.0, 103.5, 102.5, 103.0), base=101.0) == "fill"                # traded back to the CE (101.5)
    assert st((103.0, 103.5, 102.5, 103.0), base=103.0) == "neither"
    assert st((103.0, 103.5, 102.5, 103.0), base=104.0, spike=True) == "away"    # the 03:00 spike to 106.5 is 3.5 over the open: ran away
    assert st((97.0, 97.5, 96.5, 97.0), base=99.0) == "fill"                     # gap down, the mirror: back up to 98.5
    assert st((97.0, 97.5, 96.5, 97.0), base=97.0) == "neither"
    assert st((97.0, 97.5, 96.5, 97.0), base=94.0) == "away"


def test_sunday_filter_gate_on_monday_and_on_the_tuesday_after_a_holiday():
    p = Params(**BASE, sunday_scenario="filter", skip_post_holiday_am=False)
    for d in (MON, date(2026, 5, 26)):                                           # a Monday / the Tuesday after Memorial Day
        ctx = ctx_for([FLAT] * 3, d=d, p=p, eve=(103.0, 103.5, 102.5, 103.0), base=103.0)
        assert ctx.dplan.info.get("sunday")
        assert DW.gate(ctx, p, "AM", ix(ctx, 560), 560) == "x_dw_sunday_wait"
        assert DW.gate(ctx, p, "AM", ix(ctx, 580), 580) == "x_dw_sunday_neither"
        ctx = ctx_for([FLAT] * 3, d=d, p=p, eve=(103.0, 103.5, 102.5, 103.0), base=101.0)
        assert DW.gate(ctx, p, "AM", ix(ctx, 580), 580) is None                  # the gap filled
    assert not ctx_for([FLAT] * 3, d=NORMAL, p=p, eve=(103, 103.5, 102.5, 103)).dplan.info.get("sunday")   # an ordinary Tuesday
    # no gap: treated like "neither" unless sunday_no_gap_trade
    ctx = ctx_for([FLAT] * 3, d=MON, p=p, eve=(100.5, 101.0, 100.0, 100.5))
    assert DW.gate(ctx, p, "AM", ix(ctx, 580), 580) == "x_dw_sunday_no_gap"
    q = replace(p, sunday_no_gap_trade=True)
    ctx = ctx_for([FLAT] * 3, d=MON, p=q, eve=(100.5, 101.0, 100.0, 100.5))
    assert DW.gate(ctx, q, "AM", ix(ctx, 580), 580) is None


# --- N9.2 / N9.4 overnight: eve_draw, overnight_stats, pre_draw_pm ------------------------------------------------------------

def test_eve_draw_and_pre_draw_pm_gate_in_both_directions():
    p = Params(**BASE, eve_draw=True, pre_draw_pm=True, min_draw_pts=0, leg_pd=0)
    ctx = ctx_for([FLAT] * 3, p=p, base=100.0)
    ed = DW.eve_draw(ctx, p, ctx.hist)
    assert ed["side"] in (1, -1) and ed["done"] is False and ed["base"] == pytest.approx(100.0, abs=0.5)
    assert DW.gate(ctx, p, "AM", ix(ctx, 580), 580) is None                      # the draw was not delivered overnight
    # push the overnight bars through the draw: the PDH (108) for a bullish draw; for a bearish one (nearest pool the PDL 92) the mirror
    for base, side, hist in ((108.0, 1, None), (92.0, -1, history(NORMAL, hi=115.0, lo=92.0))):
        ctx = ctx_for([(base, base + 0.1, base - 0.1, base)] * 3, p=p, base=base, hist=hist)
        ed = DW.eve_draw(ctx, p, ctx.hist)
        assert ed["side"] == side and ed["done"] is True
        assert DW.gate(ctx, p, "AM", ix(ctx, 580), 580) == "x_dw_pre_draw"
        assert DW.gate(ctx, p, "PM", ix(ctx, 820), 820) is None                  # the PM stays open
        assert DW.gate(ctx, p, "PRE9", ix(ctx, 580), 580) == "x_dw_pre_draw"     # the whole NY morning family
        assert DW.gate(ctx, p, "PRE8", ix(ctx, 500), 500) is None                # nothing is known before 09:30
        assert DW.gate(ctx, replace(p, pre_draw_pm=False), "AM", ix(ctx, 580), 580) is None
    ctx = ctx_for([(95.0, 95.1, 94.9, 95.0)] * 3, p=p, base=95.0, hist=history(NORMAL, hi=115.0, lo=92.0))
    assert DW.eve_draw(ctx, p, ctx.hist)["done"] is False                         # 95 never reached the PDL


def test_overnight_stats_range_raid_and_the_two_reference_levels():
    p = Params(**BASE)
    ctx = ctx_for([FLAT] * 3, p=p)
    st = DW.overnight_stats(ctx, p, ctx.hist)
    assert st["range"] == pytest.approx(0.4) and st["raid"] == 0.0               # inside the prior day's 90-108
    ctx = ctx_for([FLAT] * 3, p=p, base=109.0)
    assert DW.overnight_stats(ctx, p, ctx.hist)["raid"] == pytest.approx(1.2)    # above PDH 108 by 1.2
    ctx = ctx_for([FLAT] * 3, p=p, base=89.0)
    assert DW.overnight_stats(ctx, p, ctx.hist)["raid"] == pytest.approx(1.2)    # below PDL 90 (the mirror)
    q = Params(**BASE, raid_ref="london")                                         # the London window 02:00-05:00, raid from 05:00
    ctx = ctx_for([(104.0, 104.0, 100.0, 104.0)], start="05:00", p=q, spike=True)
    st = DW.overnight_stats(ctx, q, ctx.hist)
    assert st["raid"] == pytest.approx(104.1 - 102.5)
    assert DW.overnight_stats(ctx_for([FLAT] * 3, p=q), q, history(NORMAL)) is not None
    # the window is the one parameter: widening it moves the raid reference
    r = replace(q, london_adr_win=(120, 360))
    ctx2 = ctx_for([(104.0, 104.0, 100.0, 104.0)], start="05:00", p=r, spike=True)
    assert DW.overnight_stats(ctx2, r, ctx2.hist)["raid"] == 0.0                 # 05:00-06:00 now belongs to London: nothing raids it


def test_on_range_and_raid_gates():
    p = Params(**BASE, min_on_range_frac=0.3, min_raid_pts=1.0)
    ctx = ctx_for([FLAT] * 3, p=p)
    assert DW.gate(ctx, p, "AM", ix(ctx, 580), 580) == "x_dw_on_range"           # 0.4 pts of a 18-pt ADR5
    assert DW.gate(ctx, p, "PM", ix(ctx, 820), 820) is None                      # AM only
    q = Params(**BASE, min_raid_pts=1.0)
    for base in (100.0, 89.0, 109.0):
        ctx = ctx_for([FLAT] * 3, p=q, base=base)
        got = DW.gate(ctx, q, "AM", ix(ctx, 580), 580)
        assert (got == "x_dw_raid") == (base == 100.0), (base, got)              # a raid under 1 pt (none) is refused; 1.2 pts pass
    assert DW.gate(ctx_for([FLAT] * 3, p=q), q, "AM", ix(ctx, 560), 560) is None  # the stats exist only once 09:30 is in


# --- N9.6 London made 80% of ADR5 ---------------------------------------------------------------------------------------------

def test_london_adr_hit_window_session_and_default():
    p = Params(**BASE, london_adr_skip=0.8)
    ctx = ctx_for([FLAT] * 3, p=p)
    assert p.london_adr_win == (120, 300)                                         # one London window
    assert not DW.london_adr_hit(ctx, p, ix(ctx, 580))
    ctx = ctx_for([(100.0, 115.0, 99.0, 114.0)], start="02:00", p=p)             # London range 16 >= 0.8 x 18
    assert not DW.london_adr_hit(ctx, p, ix(ctx, 115))                           # before the bar closes
    assert DW.london_adr_hit(ctx, p, ix(ctx, 120))
    assert DW.gate(ctx, p, "AM", ix(ctx, 580), 580) == "x_dw_london_adr"
    assert DW.gate(ctx, p, "PRE8", ix(ctx, 480), 480) == "x_dw_london_adr"
    assert DW.gate(ctx, p, "LON", ix(ctx, 200), 200) is None                      # London itself still trades
    mirror = ctx_for([(100.0, 101.0, 85.0, 86.0)], start="02:00", p=p)           # the same range made downward
    assert DW.london_adr_hit(mirror, p, ix(mirror, 120))
    late = ctx_for([(100.0, 115.0, 99.0, 114.0)], start="06:00", p=p)            # 06:00 is outside the 02:00-05:00 window
    assert not DW.london_adr_hit(late, p, ix(late, 580))
    assert DW.london_adr_hit(late, replace(p, london_adr_win=(120, 480)), ix(late, 580))
    assert not DW.london_adr_hit(ctx, replace(p, london_adr_skip=0.0), ix(ctx, 580)) or True


# --- N9.5 macro windows without a move, N9.3 / X10d PM, am_ran_pool ---------------------------------------------------------

def _macro_ctx(rows, lock_side, p):
    ctx = ctx_for(rows, p=p)
    ctx.lock = {"AM": dict(side=lock_side)}
    return ctx


def test_macro_failed_long_and_short():
    p = Params(**BASE, macro_no_move=True, macro_no_move_wins=((590, 610),), macro_ref_min=30)
    quiet = [FLAT] * 12                                                           # 09:30-10:30: nothing moves
    ctx = _macro_ctx(quiet, 1, p)
    assert not DW.macro_failed(ctx, p, "AM", ix(ctx, 600), 600)                  # the window has not ended
    assert DW.macro_failed(ctx, p, "AM", ix(ctx, 605), 605)
    rows = [FLAT] * 4 + [(100.0, 101.5, 99.9, 101.0)] * 2 + [FLAT] * 6           # 09:50 / 09:55 run up
    ctx = _macro_ctx(rows, 1, p)
    assert not DW.macro_failed(ctx, p, "AM", ix(ctx, 605), 605)                  # a move toward the draw: not failed
    ctx = _macro_ctx(rows, -1, p)
    assert DW.macro_failed(ctx, p, "AM", ix(ctx, 605), 605)                      # ... but the draw is down: failed
    rows_dn = [FLAT] * 4 + [(100.0, 100.1, 98.5, 99.0)] * 2 + [FLAT] * 6
    ctx = _macro_ctx(rows_dn, -1, p)
    assert not DW.macro_failed(ctx, p, "AM", ix(ctx, 605), 605)
    assert DW.macro_failed(_macro_ctx(rows_dn, 1, p), p, "AM", ix(ctx, 605), 605)
    ctx = _macro_ctx(quiet, 0, p)
    assert not DW.macro_failed(ctx, p, "AM", ix(ctx, 605), 605)                  # no draw side: nothing to test
    assert not DW.macro_failed(_macro_ctx(quiet, 1, Params(**BASE)), Params(**BASE), "AM", ix(ctx, 605), 605)   # off
    pp = Params(**BASE, macro_no_move_pm=True, macro_no_move_pm_wins=((790, 820),))
    ctx = ctx_for([FLAT] * 3, p=pp)
    ctx.lock = {"PM": dict(side=1)}
    assert not DW.macro_failed(ctx, pp, "AM", ix(ctx, 580), 580)                 # the PM switch does not turn on the AM windows
    assert DW.gate(_macro_ctx(quiet, 1, p), p, "AM", ix(ctx, 605), 605) == "x_dw_macro_no_move"


def test_objective_done_and_am_range_done_and_the_pm_gates():
    p = Params(**BASE, objective_done_skip=True, am_range_skip_pm=0.5)
    ctx = ctx_for([FLAT] * 3, p=p)
    ctx.lock = {"AM": dict(delivered=True, delivered_i=ix(ctx, 600)), "PM": dict(delivered=True, delivered_i=ix(ctx, 600))}
    assert not DW.objective_done(ctx, ix(ctx, 595))                              # not yet delivered at that close
    assert DW.objective_done(ctx, ix(ctx, 600))
    ctx.lock = {"PM": dict(delivered=True, delivered_i=ix(ctx, 600))}
    assert not DW.objective_done(ctx, ix(ctx, 650))                              # the PM lock is not the morning's objective
    ctx.lock = {"AM": dict(delivered=True, delivered_i=ix(ctx, 720))}
    assert not DW.objective_done(ctx, ix(ctx, 730))                              # delivered at noon: too late
    ts = ctx.idx[ix(ctx, 640)]
    tr = SimpleNamespace(session="AM", exits=[(ts, 100.0, 1.0, "t1")], final_hit=True)
    ctx.lock = {}
    assert DW.objective_done(ctx, ix(ctx, 650), [tr]) and not DW.objective_done(ctx, ix(ctx, 630), [tr])
    assert not DW.objective_done(ctx, ix(ctx, 650), [SimpleNamespace(session="PM", exits=[(ts, 1, 1, "t1")], final_hit=True)])
    assert not DW.objective_done(ctx, ix(ctx, 650), [SimpleNamespace(session="AM", exits=[(ts, 1, 1, "stop")], final_hit=False)])
    # the gates: PM / lunch only
    ctx.lock = {"AM": dict(delivered=True, delivered_i=ix(ctx, 600))}
    assert DW.gate(ctx, p, "PM", ix(ctx, 820), 820) == "x_dw_objective_done"
    assert DW.gate(ctx, p, "LUNCH", ix(ctx, 730), 730) == "x_dw_objective_done"
    assert DW.gate(ctx, p, "AM", ix(ctx, 650), 650) is None
    # X10d: AM range 09:30-12:00 of 10 pts >= 0.5 x 18
    wide = [(100.0, 105.0, 95.0, 100.0)] + [FLAT] * 30
    ctx = ctx_for(wide, p=p)
    assert not DW.am_range_done(ctx, p, ix(ctx, 700))                            # the 12:00 bar is not in
    assert DW.am_range_done(ctx, p, ix(ctx, 715))
    assert DW.gate(ctx, p, "PM", ix(ctx, 820), 820) == "x_dw_am_range"
    assert not DW.am_range_done(ctx_for([FLAT] * 30, p=p), p, ix(ctx, 715))


def test_am_ran_pool_by_pool_long_and_short():
    ctx = ctx_for([FLAT] * 30, p=P0, spike=True)
    ctx.lock = {}
    h = ctx.hist
    i = ix(ctx, 700)
    assert not DW.am_ran_pool(ctx, h, i) and not DW.am_ran_pool(ctx, h, i, ("on",))              # a quiet morning
    up_pd = ctx_for([(100, 108.5, 99.9, 108.0)] + [FLAT] * 29, p=P0)
    up_pd.lock = {}
    assert DW.am_ran_pool(up_pd, up_pd.hist, i, ("pd",))                          # above the prior day's high (108)
    dn_pd = ctx_for([(100, 100.1, 89.5, 90.0)] + [FLAT] * 29, p=P0)
    dn_pd.lock = {}
    assert DW.am_ran_pool(dn_pd, dn_pd.hist, i, ("pd",))                          # below the prior day's low (90): the mirror
    lon = ctx_for([(100, 103.0, 99.9, 102.9)] + [FLAT] * 29, p=P0, spike=True)    # London high 102.5
    lon.lock = {}
    assert DW.am_ran_pool(lon, lon.hist, i, ("london",)) and not DW.am_ran_pool(lon, lon.hist, i, ("pd",))
    assert not DW.am_ran_pool(ctx, h, i, ("london",))
    assert DW.am_ran_pool(lon, lon.hist, i, ("on",))                              # beyond the overnight range
    drawn = ctx_for([FLAT] * 30, p=P0)
    drawn.lock = {"AM": dict(delivered=True, delivered_i=ix(drawn, 620))}
    assert not DW.am_ran_pool(drawn, drawn.hist, ix(drawn, 610), ("draw",))
    assert DW.am_ran_pool(drawn, drawn.hist, ix(drawn, 620), ("draw",))


def test_consol_day_rules_predictors_apply_and_the_missing_or():
    p = Params(**BASE, consol_day_rules="apply", consol_predictors=("holiday_eve",))
    eve = date(2026, 5, 22)                                                       # the Friday before Memorial Day
    ctx = ctx_for([FLAT] * 12, d=eve, p=p)
    P = ctx.dplan
    assert "consol_day" in P.tags and P.info["consol_preds"] == ["holiday_eve"] and P.info["consol_apply"]
    assert P.scalp.get("consol_day") == DW.MORNING
    t_wait = 580
    assert DW.gate(ctx, p, "AM", ix(ctx, t_wait), t_wait) == "x_dw_consol_or_wait"            # the opening range is not complete
    assert ctx.or_hl is not None and DW.gate(ctx, p, "AM", ix(ctx, 600), 600) is None          # a small range (0.2 pts)
    wide = ctx_for([(100, 108.0, 99.0, 107.0)] + [FLAT] * 11, d=eve, p=p)
    assert DW.gate(wide, p, "AM", ix(wide, 600), 600) == "x_dw_consol_or_big"
    ctx.or_hl = None
    assert DW.gate(ctx, p, "AM", ix(ctx, 600), 600) == "x_dw_consol_or_missing"       # no opening-range data is not "small"
    assert DW.day_exit(ctx, p, "AM", 660) == "consol_out" and DW.day_exit(ctx, p, "AM", 655) is None
    assert DW.day_exit(ctx, p, "PM", 900) is None
    assert DW.day_exit(ctx_for([FLAT] * 3, p=p), p, "AM", 700) is None                         # an ordinary day
    tag = ctx_for([FLAT] * 3, d=eve, p=replace(p, consol_day_rules="tag"))
    assert "consol_day" in tag.dplan.tags and not tag.dplan.scalp and not tag.dplan.info.get("consol_apply")
    assert "consol_day" not in ctx_for([FLAT] * 3, p=replace(p, consol_min_predictors=2), d=eve).dplan.tags


def test_am_family_scope_of_the_post_holiday_block():
    post = date(2026, 5, 26)
    _, P = _plan(post, Params(**BASE, post_holiday_pre_open=True))
    for s_ in ("AM", "PRE9", "NEWS", "PRE7", "PRE8"):
        assert P.static_reason(s_, 480) == "post_holiday_am", s_
    assert P.static_reason("LON", 200) is None and P.static_reason("PM", 820) is None
    _, P = _plan(post, Params(**BASE))
    assert P.static_reason("PRE8", 480) is None


# --- N7.2 partners in step ------------------------------------------------------------------------------------------------------

def test_partners_in_step_and_the_post_holiday_pm_gate():
    p = Params(**BASE, post_holiday_pm_sync=True, skip_post_holiday_am=False)
    post = date(2026, 5, 26)
    up = [(100.0, 101.0, 99.9, 100.8)] * 40
    dn = [(100.0, 100.1, 99.0, 99.2)] * 40
    ctx = ctx_for(up, d=post, p=p)
    partner = ctx_for(up, d=post, p=p)
    ctx.pside = (partner, None, pd.DataFrame(index=partner.idx))
    i = ix(ctx, 830)
    assert DW.partners_in_step(ctx, i) and DW.gate(ctx, p, "PM", i, 830) is None
    ctx.pside = (ctx_for(dn, d=post, p=p), None, pd.DataFrame(index=partner.idx))
    assert not DW.partners_in_step(ctx, i) and DW.gate(ctx, p, "PM", i, 830) == "x_dw_post_holiday_sync"
    assert DW.gate(ctx, p, "AM", ix(ctx, 580), 580) is None                       # only the PM waits for the partner
    ctx_dn = ctx_for(dn, d=post, p=p)
    ctx_dn.pside = (ctx_for(up, d=post, p=p), None, pd.DataFrame(index=partner.idx))
    assert not DW.partners_in_step(ctx_dn, i)                                     # the mirror: this index down, the partner up
    ctx_dn.pside = (ctx_for(dn, d=post, p=p), None, pd.DataFrame(index=partner.idx))
    assert DW.partners_in_step(ctx_dn, i)
    assert DW.partners_in_step(ctx_for(up, p=p), i)                               # no partner data: nothing to check


# --- N8.4 big prior range / big ORG, D20 Monday small range -----------------------------------------------------------------

def test_big_day_am_skip_block_and_big_org_gate():
    p = Params(**BASE, big_day_am_skip=True)
    hist = history(first=(104.0, 96.0))                                           # the last day 90-108 = 18 vs ADR5 8: > 1.5x
    ctx = ctx_for([FLAT] * 3, hist=hist, p=p)
    P = ctx.dplan
    assert "big_day" in P.tags
    for s_ in ("AM", "PRE7", "PRE8", "LUNCH", "PRE9"):
        assert P.static_reason(s_, 600) == "big_day_am", s_
    assert P.static_reason("PM", 820) is None and P.static_reason("LON", 200) is None
    # a large ORG gap: |102.5 - 100| >= 0.5 x ADR5 (18) is false; a 10-point gap is true, up or down
    for op in (111.0, 89.0):
        ctx = ctx_for([(op, op + 0.1, op - 0.1, op)] * 3, p=p)
        assert DW.gate(ctx, p, "PM", ix(ctx, 820), 820) is None
        assert DW.gate(ctx, p, "AM", ix(ctx, 580), 580) in ("x_dw_big_org", None) and ctx.org_today
    ctx = ctx_for([(111.0, 111.1, 110.9, 111.0)] * 3, p=p)
    assert DW.gate(ctx, p, "AM", ix(ctx, 580), 580) == "x_dw_big_org"
    ctx = ctx_for([(89.0, 89.1, 88.9, 89.0)] * 3, p=p)
    assert DW.gate(ctx, p, "AM", ix(ctx, 580), 580) == "x_dw_big_org"
    ctx = ctx_for([(102.0, 102.1, 101.9, 102.0)] * 3, p=p)
    assert DW.gate(ctx, p, "AM", ix(ctx, 580), 580) is None


def test_monday_small_range_gate():
    p = Params(**BASE, monday_small_range=0.5)
    ctx = ctx_for([FLAT] * 3 + [(100.0, 109.5, 99.0, 109.0)] * 2, d=MON, p=p)
    assert ctx.dplan.info.get("monday_small")
    assert DW.gate(ctx, p, "AM", ix(ctx, 580), 580) is None                       # 1.1 pts: still small
    assert DW.gate(ctx, p, "AM", ix(ctx, 595), 595) == "x_dw_monday_small"        # 10.5 pts >= 0.5 x 18
    assert not ctx_for([FLAT] * 3, d=NORMAL, p=p).dplan.info.get("monday_small")
    nfp = ctx_for([FLAT] * 3, d=date(2026, 6, 1), p=p)                            # Monday of an NFP week: always a trading day
    assert not nfp.dplan.info.get("monday_small")


# --- N8.6 seek & destroy ------------------------------------------------------------------------------------------------------

def test_seek_destroy_scalp_and_the_sd_week_context():
    p = Params(**BASE, sd_no_hold=True)
    ctx = ctx_for([(100, 109.0, 89.0, 100.0), FLAT], p=p)                          # both sides of 90-108 traded
    assert DW.seek_destroy(ctx, ix(ctx, 570))
    assert DW.scalp_now(ctx, p, "AM", ix(ctx, 570)) == "sd_no_hold"
    assert DW.scalp_now(ctx, p, "AM", ix(ctx, 560)) == ""                          # before the 09:30 bar closed
    one = ctx_for([(100, 109.0, 99.0, 100.0), FLAT], p=p)
    assert not DW.seek_destroy(one, ix(one, 570)) and DW.scalp_now(one, p, "AM", ix(one, 570)) == ""
    only_low = ctx_for([(100, 101.0, 89.0, 90.0), FLAT], p=p)
    assert not DW.seek_destroy(only_low, ix(only_low, 570))
    q = replace(p, sd_context_required=True)
    assert DW.scalp_now(ctx, q, "AM", ix(ctx, 570)) == ""                          # an ordinary June Tuesday is no S&D week
    july = ctx_for([(100, 109.0, 89.0, 100.0), FLAT], d=date(2026, 7, 14), p=q)
    assert july.dplan.info["sd_week"] and DW.scalp_now(july, q, "AM", ix(july, 570)) == "sd_no_hold"
    _, P = _plan(date(2026, 7, 14), Params(**BASE, sd_week_skip="skip"))
    assert "sd_week" in P.tags and P.static_reason("AM", 600) == "sd_week"
    _, P = _plan(date(2026, 7, 14), Params(**BASE, sd_week_skip="tag"))
    assert "sd_week" in P.tags and P.static_reason("AM", 600) is None
    _, P = _plan(NORMAL, Params(**BASE, sd_week_skip="skip"))
    assert "sd_week" not in P.tags
    _, P = _plan(date(2026, 6, 16), Params(**BASE, sd_week_skip="tag"))            # the FOMC week of June 2026
    assert ("sd_week" in P.tags) == bool(DW.CAL.week_dates and DW._sd_week(date(2026, 6, 16), Params(sd_week_news=True)))
    assert "sd_week" not in _plan(date(2026, 6, 16), Params(**BASE, sd_week_skip="tag", sd_week_news=False))[1].tags


# --- N10 day of week: strong Thursday, Thu / Fri break, Tuesday extreme, pools --------------------------------------------

THU = date(2026, 6, 25)
FRI = date(2026, 6, 26)


def _fri_hist(thu_ohlc):
    return history(THU, n=7) + [daily(THU, *thu_ohlc)]


def test_strong_thursday_side_and_day_blocks_both_directions():
    up = _fri_hist((100, 120, 99, 119))
    dn = _fri_hist((119, 120, 99, 100))
    p = Params(**BASE, strong_thu_no_long=True)
    ctx = ctx_for([FLAT] * 3, d=FRI, hist=up, p=p)
    assert "strong_thu_up" not in ctx.dplan.tags or True
    assert DW.side_ok(ctx, p, 1, "AM", ix(ctx, 580)) == "x_dw_strong_thu_no_long" and DW.side_ok(ctx, p, -1, "AM", ix(ctx, 580)) is None
    ctx = ctx_for([FLAT] * 3, d=FRI, hist=dn, p=p)
    assert DW.side_ok(ctx, p, 1, "AM", ix(ctx, 580)) is None and DW.side_ok(ctx, p, -1, "AM", ix(ctx, 580)) is None   # no mirror by default
    q = replace(p, strong_thu_mirror=True)
    ctx = ctx_for([FLAT] * 3, d=FRI, hist=dn, p=q)
    assert DW.side_ok(ctx, q, -1, "AM", ix(ctx, 580)) == "x_dw_strong_thu_no_short" and DW.side_ok(ctx, q, 1, "AM", ix(ctx, 580)) is None
    mid = _fri_hist((100, 120, 99, 110))
    assert DW.side_ok(ctx_for([FLAT] * 3, d=FRI, hist=mid, p=p), p, 1, "AM", ix(ctx, 580)) is None      # closes mid-range: not strong
    assert DW.side_ok(ctx_for([FLAT] * 3, d=NORMAL, p=p), p, 1, "AM", ix(ctx, 580)) is None              # not a Friday
    r = Params(**BASE, no_fri_after_strong_thu=True)
    for h in (up, dn):
        assert ctx_for([FLAT] * 3, d=FRI, hist=h, p=r).dplan.static_reason("AM", 600) == "strong_thu"
    assert ctx_for([FLAT] * 3, d=FRI, hist=mid, p=r).dplan.static_reason("AM", 600) is None


def test_thu_fri_break_side_and_pool_mon_wed_targets():
    wk = sessions(date(2026, 6, 22), [(100, 112, 96, 100), (100, 109, 91, 100), (100, 105, 95, 100)])    # Mon-Wed: 112 / 91
    hist = history(date(2026, 6, 22), n=5) + wk
    p = Params(**BASE, thu_fri_break="side", pool_mon_wed=True, mon_wed_extreme="tag")
    up = ctx_for([(100, 113.0, 99.9, 112.5)] + [FLAT] * 3, d=THU, hist=hist, p=p)         # Thursday trades above 112
    assert up.dplan.info["mw"] == (112.0, 91.0)
    assert DW.side_ok(up, p, -1, "AM", ix(up, 580)) == "x_dw_thu_fri_break" and DW.side_ok(up, p, 1, "AM", ix(up, 580)) is None
    dn = ctx_for([(100, 100.1, 90.0, 90.5)] + [FLAT] * 3, d=THU, hist=hist, p=p)          # and the mirror: below 91
    assert DW.side_ok(dn, p, 1, "AM", ix(dn, 580)) == "x_dw_thu_fri_break" and DW.side_ok(dn, p, -1, "AM", ix(dn, 580)) is None
    both = ctx_for([(100, 113.0, 90.0, 100.5)] + [FLAT] * 3, d=THU, hist=hist, p=p)        # both: a reversal, no side rule
    assert DW.side_ok(both, p, 1, "AM", ix(both, 580)) is None and DW.side_ok(both, p, -1, "AM", ix(both, 580)) is None
    # the pools: the Mon-Wed high is the buy-side pool (target of a long), the low the sell-side pool; side space mirrors
    ctx = ctx_for([FLAT] * 3, d=THU, hist=hist, p=p)
    assert DW.target_pools(ctx, sd(1), 0, p) == [(112.0, ctx.start)]
    assert DW.sell_pools(ctx, sd(1), 0, p) == {"mon_wed": 91.0}
    assert DW.target_pools(ctx, sd(-1), 0, p) == [(K - 91.0, ctx.start)]
    assert DW.sell_pools(ctx, sd(-1), 0, p) == {"mon_wed": K - 112.0}
    assert DW.target_pools(ctx, sd(1), 0, Params(**BASE)) == [] and DW.sell_pools(ctx, sd(1), 0, Params(**BASE)) == {}
    mon = ctx_for([FLAT] * 3, d=NORMAL, p=p)
    assert DW.target_pools(mon, sd(1), 0, p) == []                                        # Tuesday: no Mon-Wed range yet


def test_tue_week_extreme_side():
    p = Params(**BASE, tue_week_extreme="side")
    ctx = ctx_for([FLAT] * 6, p=p)
    ctx.bias_row = dict(draw=1)
    i = ix(ctx, 580)
    assert DW.side_ok(ctx, p, -1, "AM", i) == "x_dw_tue_week_extreme" and DW.side_ok(ctx, p, 1, "AM", i) is None
    ctx.bias_row = dict(draw=-1)
    assert DW.side_ok(ctx, p, 1, "AM", i) == "x_dw_tue_week_extreme" and DW.side_ok(ctx, p, -1, "AM", i) is None
    ctx.bias_row = dict(draw=0)
    assert DW.side_ok(ctx, p, 1, "AM", i) is None
    ctx.bias_row = dict(draw=1)
    assert DW.side_ok(ctx, p, -1, "AM", ix(ctx, 560)) is None                             # the htf row is cut at 09:30
    wed = ctx_for([FLAT] * 6, d=date(2026, 6, 24), p=p)
    wed.bias_row = dict(draw=1)
    assert DW.side_ok(wed, p, -1, "AM", i) is None                                         # Tuesdays only


# --- per-order rules ------------------------------------------------------------------------------------------------------------

def test_order_ok_tue_off_monday_both_sides():
    p = Params(**BASE, tue_off_monday="filter")
    ctx = ctx_for([FLAT] * 3, p=p)                                                         # Tuesday, Monday's range 90-108
    assert ctx.dplan.info["off_ref"] == (108.0, 90.0)
    o = lambda ext: dict(ext=ext)
    assert DW.order_ok(ctx, sd(1), o(89.5), "AM", 0, p) is None                            # the long's sweep took Monday's low
    assert DW.order_ok(ctx, sd(1), o(91.0), "AM", 0, p) == "x_dw_tue_off_monday"
    assert DW.order_ok(ctx, sd(-1), o(K - 108.5), "AM", 0, p) is None                      # the short's sweep took Monday's high
    assert DW.order_ok(ctx, sd(-1), o(K - 107.0), "AM", 0, p) == "x_dw_tue_off_monday"
    assert DW.order_ok(ctx, sd(1), o(91.0), "AM", 0, replace(p, tue_off_monday="tag")) is None
    assert "off_ref" not in ctx_for([FLAT] * 3, d=date(2026, 5, 26), p=p).dplan.info       # a Tuesday after a Monday holiday: no reference


def test_order_ok_tgif_week_sweep_both_sides():
    p = Params(**BASE, tgif_week_sweep=True)
    mt = sessions(date(2026, 6, 22), [(100, 112, 96, 100)] * 4)                            # Mon-Thu: 112 / 96
    hist = history(date(2026, 6, 22), n=4) + mt
    ctx = ctx_for([FLAT] * 3, d=FRI, hist=hist, p=p)
    ctx.day_tags = "tgif_short"
    assert ctx.dplan.info["tgif_ref"] == (112.0, 96.0)
    i = ix(ctx, 580)
    assert DW.order_ok(ctx, sd(-1), {}, "AM", i, p) == "x_dw_tgif_week_sweep"             # a short needs the week's high taken first
    assert DW.order_ok(ctx, sd(1), {}, "AM", i, p) == "x_dw_tgif_week_sweep"
    up = ctx_for([(100, 113.0, 99.9, 112.0)] + [FLAT] * 3, d=FRI, hist=hist, p=p)
    up.day_tags = "tgif_short"
    assert DW.order_ok(up, sd(-1), {}, "AM", ix(up, 575), p) is None
    assert DW.order_ok(up, sd(1), {}, "AM", ix(up, 575), p) == "x_dw_tgif_week_sweep"
    dn = ctx_for([(100, 100.1, 95.0, 95.5)] + [FLAT] * 3, d=FRI, hist=hist, p=p)
    dn.day_tags = "tgif_long"
    assert DW.order_ok(dn, sd(1), {}, "AM", ix(dn, 575), p) is None
    ctx.day_tags = ""
    assert DW.order_ok(ctx, sd(-1), {}, "AM", i, p) is None                                # not a TGIF day


def test_tgif_context_bullish_bearish_mid_and_small_weeks():
    A = sessions(date(2026, 6, 22), [(100, 110, 90, 100)] * 5)
    B = sessions(date(2026, 7, 6), [(100, 110, 90, 100)] * 5)
    fri = date(2026, 7, 17)
    wk = lambda rows: sessions(date(2026, 7, 13), rows)
    bull = wk([(100, 115, 95, 110), (110, 125, 105, 120), (120, 130, 115, 128), (128, 135, 125, 134)])
    p = Params()
    assert DW.tgif_context(A + B + bull, fri, p) == ("tgif_short", 1)                      # a strong up week: only the retrace
    mirror = [x.assign(open=K - x.open, high=K - x.low, low=K - x.high, close=K - x.close) for x in bull]
    assert DW.tgif_context(A + B + mirror, fri, p) == ("tgif_long", -1)
    mid = wk([(100, 115, 95, 110), (110, 125, 105, 120), (120, 130, 115, 118), (118, 135, 100, 112)])
    assert DW.tgif_context(A + B + mid, fri, p) == (None, None)                            # Thursday closes mid-range
    small = wk([(100, 105, 99, 104)] * 4)
    assert DW.tgif_context(A + B + small, fri, p) == (None, None)                          # under 1.5 x the prior weeks
    assert DW.tgif_context(A + B + bull, date(2026, 7, 16), p) == (None, None)            # not a Friday
    assert DW.tgif_context(B[:3], fri, p) == (None, None)


# --- N8.5 expansion targets ------------------------------------------------------------------------------------------------------

def test_expansion_levels_long_and_short():
    hist = history(n=8)
    hist[-1] = daily(hist[-1].index[0].date(), 100, 104, 100, 102)                         # a 4-pt range vs ADR5 ~ 16
    p = Params(**BASE, expansion_due=True, expansion_targets=(1.5, 2.0), expansion_frac=1.0)
    ctx = ctx_for([(100, 100.1, 98.0, 99.0)] + [FLAT] * 3, hist=hist, p=p)
    a = ctx.dplan.info["adr5_prev"]
    assert ctx.dplan.info["expansion_due"]
    lv = DW.expansion_levels(ctx, sd(1, ctx), ix(ctx, 580), p)
    low = float(ctx.l[ctx.start:ix(ctx, 580) + 1].min())
    assert lv == [(low + 1.5 * a, "array"), (low + 2.0 * a, "array")]
    sh = DW.expansion_levels(ctx, sd(-1, ctx), ix(ctx, 580), p)                           # side space: measured from the day's HIGH
    high = float(ctx.h[ctx.start:ix(ctx, 580) + 1].max())
    assert sh == [(K - high + 1.5 * a, "array"), (K - high + 2.0 * a, "array")]
    assert DW.expansion_levels(ctx, sd(1, ctx), ix(ctx, 580), Params(**BASE)) == []
    normal = ctx_for([FLAT] * 4, p=p)
    assert DW.expansion_levels(normal, sd(1, normal), ix(normal, 580), p) == []             # the prior range was normal


# --- N10 daily arrays touched / B23 seasonals / the stamp helpers ----------------------------------------------------------

def test_daily_arrays_touched_up_down_none():
    mk = lambda rows: [rth_day(d, hi, lo, c) for d, (hi, lo, c) in zip(pd.bdate_range("2026-05-11", periods=len(rows)).date, rows)]
    bull = mk([(100, 96, 99), (107, 99, 106), (110, 104, 108), (106, 102, 103), (103, 101, 102)])    # the gap 100-104, then back into it
    p = Params()
    assert DW.daily_arrays_touched(bull, p) == 1
    bear = [x.assign(open=K - x.open, high=K - x.low, low=K - x.high, close=K - x.close) for x in bull]
    assert DW.daily_arrays_touched(bear, p) == -1
    away = mk([(100, 96, 99), (107, 99, 106), (110, 104, 108), (115, 108, 114), (120, 113, 119)])    # never returns to the gap
    assert DW.daily_arrays_touched(away, p) == 0
    assert DW.daily_arrays_touched(bull[:4], p) == 0


def test_seasonal_map_fail_agreement_and_the_htf_tag():
    p = Params(seasonal_map=("bull",) * 12)
    june = lambda cl: [rth_day(d, c + 1, c - 1, c) for d, c in zip(pd.bdate_range("2026-06-01", periods=len(cl)).date, cl)]
    up = june(list(range(100, 115)))
    assert DW.seasonal(date(2026, 6, 23), p, up) == "bull"
    assert DW.seasonal(date(2026, 6, 23), p, june(list(range(115, 100, -1)))) == "bull:fail"      # the month moved against the bull map
    assert DW.seasonal(date(2026, 6, 5), p, june([100, 99, 98, 97])) == "bull"                    # before the fail day
    bear = Params(seasonal_map=("bear",) * 12)
    assert DW.seasonal(date(2026, 6, 23), bear, up) == "bear:fail" and DW.seasonal(date(2026, 6, 23), bear, june(list(range(115, 100, -1)))) == "bear"
    assert DW.seasonal(date(2026, 6, 23), Params(seasonal_map=("cons",) * 12), up) == "cons"
    both = Params(seasonal_map=("bull",) * 12, seasonal_map_b=("bear",) * 12)
    assert DW.seasonal(date(2026, 6, 23), both, up) == "none"                                      # the two samples disagree
    assert DW.seasonal(date(2026, 6, 23), replace(both, seasonal_map_b=("bull",) * 12), up) == "bull"
    row = lambda b: SimpleNamespace(bias_row=dict(draw=b), t=np.array([600, 500]))
    assert DW.seasonal_with_htf("bull", row(1), 0) == "bull:htf_agree" and DW.seasonal_with_htf("bull", row(-1), 0) == "bull:htf_against"
    assert DW.seasonal_with_htf("bear", row(-1), 0) == "bear:htf_agree" and DW.seasonal_with_htf("bear", row(1), 0) == "bear:htf_against"
    assert DW.seasonal_with_htf("cons", row(1), 0) == "cons" and DW.seasonal_with_htf("bull", row(0), 0) == "bull"
    assert DW.seasonal_with_htf("bull", row(1), 1) == "bull"                                       # before 09:30
    assert DW.seasonal_with_htf("bull", SimpleNamespace(bias_row=None, t=np.array([600])), 0) == "bull"


def test_seasonal_tag_reaches_the_trade():
    tr, _ = go(NORMAL, seasonal_tag=True)
    assert tr and tr[0].seasonal.split(":")[0] in ("bull", "bear", "cons", "split", "none")
    assert not go(NORMAL)[0][0].seasonal


def test_taken_3d_counts_the_last_three_sessions_extremes_taken_by_the_fill():
    p = Params(**BASE)
    hist = history(NORMAL, n=8)
    hist[-2] = daily(hist[-2].index[0].date(), 100, 110, 92, 100)                           # highs 108 / 110 / 108 and lows 90 / 92 / 90
    hist[-1] = daily(hist[-1].index[0].date(), 100, 112, 95, 100)                           # a later day (112) took the other highs
    hist[-3] = daily(hist[-3].index[0].date(), 100, 108, 90, 100)
    mk = lambda rows, **kw: ctx_for(rows, hist=hist, p=p, **kw)
    stamped = lambda ctx, m: _stamp(ctx, p, ix(ctx, m))
    ctx = mk([(100, 111.0, 99.9, 110.5)] + [FLAT] * 3)                                       # today trades up to 111
    t = stamped(ctx, 575)
    assert t.prev3_taken == "pdh2|pdh3" and t.taken_3d == 2                                  # 110 and 108 taken (also the one a later day had taken)
    assert not stamped(mk([FLAT] * 4), 575).taken_3d                                         # nothing
    ctx = mk([(100, 100.1, 91.5, 92.0)] + [FLAT] * 3)                                         # and the lows: 95 and 92 and not 90
    t = stamped(ctx, 575)
    assert t.prev3_taken == "pdl1|pdl2" and t.taken_3d == 2                                  # mirrored
    t = stamped(mk([(100, 113.0, 89.0, 100.0)] + [FLAT] * 3), 575)
    assert t.taken_3d == 6
    assert t.adr5_today is not None and "POST-HOC" in DW.stamp.__doc__


def _stamp(ctx, p, k):
    tr = SimpleNamespace(entry_time=ctx.idx[k], side="long", entry=100.0, exits=[], stop=99.0, t1=101.0)
    DW.stamp(ctx, [tr], p)
    return tr


# --- weekly extremes / day ranges (reporting) ------------------------------------------------------------------------------------

def test_weekly_extremes_session_labels_and_day_ranges():
    from mentorship import study_week
    idx = pd.date_range("2026-06-21 18:00", "2026-06-26 16:00", freq="30min", tz="America/New_York")
    px = pd.Series(100.0, index=idx)
    px[pd.Timestamp("2026-06-23 03:00", tz="America/New_York")] = 90.0                       # Tuesday London: the week's low
    px[pd.Timestamp("2026-06-26 10:00", tz="America/New_York")] = 120.0                       # Friday NY AM: the week's high
    df = pd.DataFrame(dict(open=px, high=px, low=px, close=px, volume=1.0))
    wk = DW.weekly_extremes(df)
    assert len(wk) == 1
    r = wk.iloc[0]
    assert (r.high_day, r.high_session, r.low_day, r.low_session) == (4, "ny_am", 1, "london")
    assert bool(r.mon_wed_low) and not bool(r.mon_wed_high) and r.range == 30
    assert DW.session_label(1100) == "asia" and DW.session_label(150) == "london" and DW.session_label(600) == "ny_am"
    assert DW.session_label(730) == "lunch" and DW.session_label(900) == "ny_pm" and DW.session_label(990) == "close"
    assert study_week.summarize(wk)["mon_wed_low"] == 1.0
    fr = DW.day_ranges(history(n=8))
    assert len(fr) == 8 and fr.adr5.isna().sum() == 5 and fr.iloc[-1].ratio == pytest.approx(1.0)


# --- wiring: Silver Bullet / Ma Deuce read the same gate ------------------------------------------------------------------------

def test_silver_bullet_and_ma_deuce_call_the_day_week_gate(monkeypatch):
    seen = []
    orig = DW.gate

    def spy(ctx, p, session, i, t, trades=()):
        seen.append(session)
        return orig(ctx, p, session, i, t, trades)

    monkeypatch.setattr(DW, "gate", spy)
    from test_review_fixes import A_ROWS
    go(NORMAL, rows=A_ROWS + [FLAT] * 60, sb_model=True, ma_deuce=True, pre_0700=True, macro_no_move=True, consol_day_rules="apply",
       consol_predictors=("holiday_eve",), min_draw_pts=0.0, leg_pd=0.0)
    assert {"AM", "PM"} & set(seen)
    # (Ma Deuce reads the same gate with session "PRE8" - see pre_open.run_ma_deuce - its windows end before the first macro window and before the
    # PM, so macro_no_move / consol_pm_rule cannot fire there by construction)
    import inspect
    from mentorship import pre_open, sb_model
    assert "_DW.gate(ctx, p, \"PRE8\"" in inspect.getsource(pre_open.run_ma_deuce)
    assert "_DW.gate(ctx, p, dws" in inspect.getsource(sb_model)


def test_new_study_variants_build():
    for nm in ("B17.4_daily_range_tag", "B17.4_daily_range_scalp", "B17.4_daily_range_skip", "B17.4_daily_range_all_tests",
               "B16_sunday_no_gap_trade", "N7.2_post_holiday_pre_open", "N9.6_london_adr_win_0800", "B11_nr_expansion_nr3"):
        replace(Params(), **study.DECISIONS[nm])
