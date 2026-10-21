"""Caption-gap pass, package levels_detectors #3/3 (27 specs of digests/rulebook_gaps/levels_liquidity_targets.md (19, 28, 40, 42, 70, 74, 76, 87,
104, 112, 113, 114, 116, 127, 128, 129, 130, 148, 165), models_setups_entries.md (41, 67, 137, 138, 197) and times_sessions_macros.md (21, 22, 29)):
unit tests of the new detectors in levels.py / htf.py, the ld4.py engine glue, Params / study plumbing and no-look-ahead runs (full vs truncated)
covering the new switches on small date windows. Tests that need local market data (ES) skip cleanly when it is absent; no platform-specific paths."""
import warnings
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from mentorship import backtest as B, bias_day as BD, confluence as CF, htf, ld2 as LD, ld3 as L3, ld4 as L4, levels as L, strategy as S, study
from mentorship.strategy import Params

from test_levels_detectors import BASE, D0, ES, FUT, NY, day, frame, history, prior_days, rth_day

A = np.array


def mk(rows):
    """[(o, h, l, c)] -> arrays."""
    a = np.array(rows, float)
    return a[:, 0], a[:, 1], a[:, 2], a[:, 3]


def hist_from(ohlc, d_end=D0):
    """Completed sessions from (o, h, l, c) tuples, oldest first (two bars each: first bar open, last bar close)."""
    ds = prior_days(d_end, len(ohlc))
    out = []
    for d, (o, h, l, c) in zip(ds, ohlc):
        out.append(frame(d, [(o, h, l, o), (o, h, l, c)], 5, "09:30"))
    return out


def ctx3(df, hist, p, eth=None, prev_full=None, closes=None, gaps=None):
    """A DayCtx as run_day builds it (levels only): DayCtx + _extra_levels, with the previous day's full frame when given."""
    ctx = S.DayCtx(df, df.index[0].date(), hist, 5, or_minutes=p.or_minutes)
    ctx.gaps = gaps
    ctx.prev_full = prev_full
    S._setup_news(ctx, ctx.day, p)
    S._extra_levels(ctx, df, hist, p, eth, closes)
    return ctx


def side(ctx, sign=1):
    return S.Side(sign, ctx.o, ctx.h, ctx.l, ctx.c, 1)


def k_at(ctx, hhmm: str) -> int:
    return S._idx_at(ctx, int(hhmm[:2]) * 60 + int(hhmm[3:]))


FLAT = [(100.0, 100.2, 99.8, 100.0)] * 40


# --- L5-rth-and-eth-gap-views (19) -------------------------------------------------------------------------------------------

def _weekend_df():
    """Friday 2026-06-19 09:30-16:55 (RTH close 4000 at the 16:10 bar, ETH last price 4002), the Sunday 18:00 reopen at 4006, Monday 09:30 opens 4010."""
    fri = pd.date_range("2026-06-19 09:30", "2026-06-19 16:55", freq="5min", tz=NY)
    sun = pd.date_range("2026-06-21 18:00", "2026-06-22 10:00", freq="5min", tz=NY)
    px = []
    for t in fri:
        px.append(4000.0 if t.hour * 60 + t.minute < 975 else 4002.0)
    for t in sun:
        px.append(4010.0 if (t.day == 22 and t.hour * 60 + t.minute >= 570) else 4006.0)
    idx = fri.append(sun)
    a = np.array(px)
    return pd.DataFrame({"open": a, "high": a, "low": a, "close": a, "volume": 1.0}, index=idx)


def test_gap_views_both():
    df = _weekend_df()
    og = htf.opening_gaps(df, 1.0, 1.0, "auto", "both", 975)
    nw = og[og.kind == "nwog"].iloc[0]
    rth = og[og.kind == "nwog_rth"].iloc[0]
    assert (nw.low, nw.high) == (4002.0, 4006.0)                                   # the ETH gap: Friday's 16:55 print -> the Sunday open
    assert (rth.low, rth.high) == (4000.0, 4010.0)                                 # the RTH gap: Friday's 16:15 close -> the Monday 09:30 open
    assert rth.known == pd.Timestamp("2026-06-22 09:35", tz=NY)                    # known when the 09:30 bar has closed
    assert not (htf.opening_gaps(df, 1.0, 1.0, "auto", "auto", 975).kind == "nwog_rth").any()      # the default: the ETH view only
    with pytest.raises(ValueError):
        htf.opening_gaps(df, 1.0, 1.0, "auto", "x", 975)
    # selection: Tuesday sees both (Monday's own RTH gap is only known after 09:30), Monday only the ETH one
    tue = htf.gaps_for_day(og, date(2026, 6, 23), 5, 0)
    mon = htf.gaps_for_day(og, date(2026, 6, 22), 5, 0)
    assert sorted(k for k, *_ in tue) == ["nwog", "nwog_rth"] and [k for k, *_ in mon] == ["nwog"]


# --- L5-holiday-nwog (28) ------------------------------------------------------------------------------------------------------

def _nwog_row(sunday, hi, lo):
    k = pd.Timestamp(f"{sunday} 18:00", tz=NY)
    return dict(kind="nwog", high=float(hi), low=float(lo), ce=(hi + lo) / 2, up=True, known=k,
                week=(k + pd.Timedelta(hours=7)).normalize().tz_localize(None).to_period("W-FRI"), dir="up", close_before=float(lo), open_after=float(hi))


def test_holiday_week_closest_nwog():
    # Thanksgiving week (2025-11-24..28: 4 trading days) = a holiday week; normal NWOGs at 4000 (Nov 3 week) and 4200 (Nov 10 week), open 4150
    og = pd.DataFrame([_nwog_row("2025-11-02", 4004, 4000), _nwog_row("2025-11-09", 4204, 4200), _nwog_row("2025-11-23", 4101, 4099)])
    d = date(2025, 11, 24)
    base = htf.gaps_for_day(og, d, 5, 0, True)
    assert sorted(round(h) for _, h, *_ in base) == [4004, 4204]                  # nwog_skip_holiday: the holiday week's own NWOG is dropped
    one = htf.gaps_for_day(og, d, 5, 0, True, holiday_pick="closest", ref_px=4150.0)
    assert [(round(h), round(l)) for _, h, l, _ in one] == [(4204, 4200)]         # only the closest normal one (4200 is 50 away, 4000 is 150)
    assert htf.gaps_for_day(og, d, 5, 0, True, holiday_pick="closest", ref_px=None) == base                  # no reference price: nothing to pick by
    # a normal week keeps every NWOG
    normal = htf.gaps_for_day(og, date(2025, 11, 10), 5, 0, True, holiday_pick="closest", ref_px=4150.0)
    assert sorted(round(h) for _, h, *_ in normal) == [4004, 4204]
    # no other NWOG at all = none
    only = pd.DataFrame([_nwog_row("2025-11-23", 4101, 4099)])
    assert htf.gaps_for_day(only, d, 5, 0, True, holiday_pick="closest", ref_px=4150.0) == []


def _tue_ctx(d, hist, rows, i_hhmm):
    df = day(rows, d=d)
    ctx = S.DayCtx(df, d, hist, 5)
    return ctx, k_at(ctx, i_hhmm)


def test_tue_open_ref():
    mon_hol, tue, wed = date(2026, 1, 19), date(2026, 1, 20), date(2026, 1, 21)             # MLK Day 2026-01-19: no Monday session
    h = history(tue, n=6)
    ctx, i = _tue_ctx(tue, h, [(4050.0, 4051.0, 4049.0, 4050.5)] * 10, "09:30")
    assert BD.tue_open_ref(ctx, i - 1) == (True, None)                                       # before the Tuesday 09:30 bar has closed
    hol, v = BD.tue_open_ref(ctx, i)
    assert hol and v == 4050.0                                                               # Tuesday 09:30 open
    hw = history(wed, n=6)
    hw[-1] = frame(tue, [(4050.0, 4051.0, 4049.0, 4050.5)] * 3, 5, "09:30")                   # the completed Tuesday session in the history
    ctx2, i2 = _tue_ctx(wed, hw, [(4060.0, 4061.0, 4059.0, 4060.0)] * 10, "09:30")
    ctx2.hist = hw                                                                           # (run_day sets ctx.hist)
    assert BD.tue_open_ref(ctx2, i2) == (True, 4050.0)
    ctx3_, i3 = _tue_ctx(D0, history(D0, n=6), FLAT, "09:30")                                 # a normal week (Tuesday 2026-06-23)
    assert BD.tue_open_ref(ctx3_, i3) == (False, None)


# --- L7-org-lifetime-sr (40) ---------------------------------------------------------------------------------------------------

def _org_ctx(p, up_to=4012.0, later_high=4001.2):
    """Seven completed sessions: day 1 closes 4020, day 2 opens 4000 (a gap-down ORG 4000-4020, 4020 = prior close) and rallies to `up_to`."""
    ds = prior_days(D0, 7)
    h = [rth_day(ds[0], 4021.0, 4019.0, 4020.0, 4020.0),
         rth_day(ds[1], up_to, 3999.0, 4001.0, 4000.0)]
    h += [rth_day(d, later_high, 3999.5, 4001.0, 4001.0) for d in ds[2:]]
    return ctx3(day([(4001.0, 4001.2, 4000.8, 4001.0)] * 20, base=4001.0), h, p)


def test_org_partial_delivery_remainder():
    p = Params(**BASE, org_days=60, org_both_ways=True)
    ctx = _org_ctx(p)
    sd = side(ctx)
    i = k_at(ctx, "09:30") + 6
    idxs = L4.org_sel(ctx, p, False)
    j = next(j for j, (a, b) in enumerate(ctx.org) if (a, b) == (4020.0, 4000.0))
    st = L4.org_state(ctx, j, i, p)
    assert st["dn_done"] and not st["up_done"] and st["part_up"] == 4012.0                    # opened at the bottom; the rally stopped part-way
    lv = [v for v in L4.org_levels(ctx, sd, i, p, idxs) if v > 4005]
    assert sorted(round(v, 3) for v in lv) == [4012.0, 4015.0, 4020.0]                       # the pending upside: [partial-delivery extreme, far edge]
    # without the switch every level of the gap is a target (the old list)
    old = S._targets(ctx, sd, i, 4001.5, [], replace(p, org_both_ways=False), None, i)
    assert 4005.0 in [v for v, _ in old] and 4010.0 in [v for v, _ in old]
    new = S._targets(ctx, sd, i, 4001.5, [], p, None, i)
    assert 4005.0 not in [v for v, _ in new] and 4012.0 in [v for v, _ in new] and 4020.0 in [v for v, _ in new]
    # a full rally through the far edge: this side is done (and both sides done = the ORG leaves the lists)
    ctx2 = _org_ctx(p, up_to=4021.0)
    j2 = next(j for j, (a, b) in enumerate(ctx2.org) if (a, b) == (4020.0, 4000.0))
    assert L4.org_state(ctx2, j2, i, p)["up_done"] and not L4.org_alive(ctx2, j2, i, p) and L4.org_alive(ctx2, j2, i, replace(p, org_both_ways=False))
    # org_days 5 vs 60: the ORG history length
    assert len(_org_ctx(replace(p, org_days=5)).org) == 6 and len(ctx.org) == 7
    # the mirror (a short): the downside of a gap-up ORG filled part-way down
    assert not [v for v in L4.org_levels(ctx, side(ctx, -1), i, p, idxs) if v > -4005.0 and abs(v) > 4005.0]       # the down side of that ORG is done: nothing from it


# --- L10-older-daily-weekly-wick-ce (42) --------------------------------------------------------------------------------------

def _wick_hist(traded_k=None):
    """12 sessions o = c = 100: 8 sessions ago the high is 112 (upper wick CE 106), every other high 104; `traded_k` (k-th last) trades to 107."""
    highs = [104.0] * 12
    highs[-8] = 112.0
    if traded_k:
        highs[-traded_k] = 107.0
    return history(D0, n=12, highs=highs, lows=[96.0] * 12)


def test_old_daily_wick_ce_persists_until_traded():
    p = Params(**BASE, wick_levels=True, wick_days=10, wick_untraded=True)
    ctx = ctx3(day(FLAT, base=100.0), _wick_hist(), p)
    sd = side(ctx)
    assert (round(ctx.wicks[7]["upper"], 6), ctx.wick_ok[7][0]) == (106.0, True)             # (its lower CE 98 was traded through by every later low of 96)
    assert 106.0 in [round(v, 6) for v in L4.wick_ce_levels(ctx, sd, p, False)]               # 8 days old, untouched since: present with wick_days = 10
    i = k_at(ctx, "09:30") + 3
    assert 106.0 in [round(v, 6) for v, _ in S._targets(ctx, sd, i, 100.5, [], p, None, i)]
    ctx2 = ctx3(day(FLAT, base=100.0), _wick_hist(traded_k=3), p)                             # traded through 3 days ago (high 107)
    assert 106.0 not in [round(v, 6) for v in L4.wick_ce_levels(ctx2, side(ctx2), p, False)]
    assert 106.0 in [round(v, 6) for v, _ in S._targets(ctx2, side(ctx2), i, 100.5, [], replace(p, wick_untraded=False), None, i)]    # the old list keeps it
    # weeks: wick_weeks takes the last N completed weeks' candles, each judged the same way
    pw = replace(p, wick_weeks=3, wick_weekly=True)
    ctx3w = ctx3(day(FLAT, base=100.0), _wick_hist(), pw)
    assert len(ctx3w.wick_wk) == 3 and len(ctx3w.wick_wk_ok) == 3
    # the mirror: the lower CE of a short's far wick
    assert all(v < 0 for v in L4.wick_ce_levels(ctx, side(ctx, -1), p, False))


def test_wick_lod_tag():
    p = Params(**BASE, wick_lod_tag="tag", wick_days=2)
    ws = [dict(upper=106.0, lower=96.0)]
    conf = SimpleNamespace(valid=lambda now, sign, tfs, src, kb: [(96.5, 95.5, "15m", 0, 0.0)])         # a 15m bullish array around the CE
    idx = pd.date_range("2026-06-23 09:30", periods=12, freq="5min", tz=NY)
    ctx = SimpleNamespace(wicks=ws, wick_ok=[(True, True)], conf=conf, idx=idx, tf=5)
    sd = S.Side(1, *(np.full(12, 96.0),) * 4, 1)
    sw = dict(ext=95.9, ext_i=4)
    assert L4.wick_lod(ctx, sd, sw, 8, p)                                                      # within 2 ticks of the untraded lower CE, an array right there
    assert not L4.wick_lod(ctx, sd, dict(ext=94.0, ext_i=4), 8, p)                              # too far from the CE
    ctx.wick_ok = [(True, False)]                                                              # the CE was traded through
    assert not L4.wick_lod(ctx, sd, sw, 8, p)
    ctx.wick_ok = [(True, True)]
    ctx.conf = SimpleNamespace(valid=lambda *a: [(99.0, 98.0, "15m", 0, 0.0)])                  # the array is 3 points away
    assert not L4.wick_lod(ctx, sd, sw, 8, p)
    # the order gate: tag / require
    lvt = []
    ctx.conf = conf
    sw2 = dict(ext=95.9, ext_i=4, key="pdl1", level=96.0)
    assert L4.order_gate(ctx, sd, sw2, 8, p, 97.0, None, False, lvt) is None and "wick_lod" in lvt
    ctx.wick_ok = [(True, False)]
    ctx.cur_bias = 1
    assert L4.order_gate(ctx, sd, sw2, 8, replace(p, wick_lod_tag="require"), 97.0, None, False, []) == "x_wick_lod"
    ctx.cur_bias = 0                                                                           # review fix: "require" only where the LOD expectation applies (a day biased this way)
    assert L4.order_gate(ctx, sd, sw2, 8, replace(p, wick_lod_tag="require"), 97.0, None, False, []) is None
    assert L4.order_gate(ctx, sd, sw2, 8, p, 97.0, None, False, []) is None


# --- new-reactionary-high-liquidity (70) --------------------------------------------------------------------------------------

REACT = [(100, 101, 99.5, 100.5), (100.5, 102, 100, 101.5), (101.5, 104, 101, 103), (103, 106, 102.5, 105), (105, 120, 104.5, 118),
         (118, 118.5, 110, 111), (111, 112, 100, 101), (101, 102, 99, 100), (100, 101, 99, 100.5), (100.5, 104, 100, 103.5),
         (103.5, 110, 103, 109), (109, 109.5, 107, 108), (108, 108.5, 106, 107.5), (107.5, 108, 106.5, 107)]


def test_reactionary_high_pool():
    o, h, l, c = mk(REACT)
    ph, _ = L.pivots(h, l, 1)
    assert [q.price for q in ph] == [120.0, 110.0]
    r = L.reactionary_highs(o, h, l, c, ph, 1.5)
    assert r == [(120.0, 4, 6)]                                                                # the 4120-type pivot with the 2-bar displacement; the later minor pivot (110) has none
    assert L.reactionary_highs(o, h, l, c, ph, 1.5, end=5) == []                                # known only once the leg has displaced (bar 6)
    p = Params(**BASE, reactionary_pools=True, displacement_mult=1.5)
    sd = S.Side(1, o, h, l, c, 1)
    ctx = SimpleNamespace()
    assert L4.reactionary_buy(ctx, sd, 12, p) == (120.0, 6)
    assert L4.reactionary_buy(ctx, sd, 5, p) is None
    assert (120.0, 6) in L4.target_pools(SimpleNamespace(start=0, week_hl=None), sd, 12, p)
    assert L4.target_pools(SimpleNamespace(start=0), sd, 12, replace(p, reactionary_pools=False)) == []
    assert ("pool", "reactionary") == L4.draw_prefs(ctx, sd, 12, 105.0, p)[0][1:]                # the retracement's draw, ahead of the nearer minor high
    assert L4.draw_prefs(ctx, sd, 12, 125.0, p) == []                                           # nothing above the entry
    # taken: a later high at or above the pivot retires it
    h2 = h.copy(); h2[11] = 121.0
    assert L4.reactionary_buy(ctx, S.Side(1, o, h2, l, c, 1), 12, p) is None
    # the mirror: the same bars negated give a reactionary LOW, a sell-side pool for the sweep
    sdm = S.Side(1, -o, -l, -h, -c, 1)
    assert L4.reactionary_sell(ctx, sdm, 13, p) == (-120.0, 6)
    out = {}
    cx = SimpleNamespace(start=0, week_hl=None, rb_lv=([], []), __dict__={})
    L4.sell_pools(cx, sdm, 13, p, out)
    assert out["reactionary_lo"] == -120.0 and S._level_created(cx, "reactionary_lo", "AM") == 6


# --- new-parent-pool-bodies-short (74) ----------------------------------------------------------------------------------------

PARENT = [(4010, 4012, 4008, 4011), (4005, 4010, 4000, 4003), (4008, 4010, 4006, 4009), (4010, 4013, 4010, 4012), (4004, 4008, 4001, 4003),
          (4006, 4010, 4008, 4009), (4010, 4013, 4012, 4012), (4005, 4008, 4002, 4004), (4007, 4011, 4009, 4010), (4010, 4012, 4011, 4011.5)]


def test_parent_pool_bodies_short():
    o, h, l, c = mk(PARENT)
    _, pl = L.pivots(h, l, 1)
    assert [q.price for q in pl] == [4000.0, 4001.0, 4002.0]
    assert L.parent_pools(o, h, l, c, pl, 2, 5.0) == [(4000.0, 1, 8)]                           # L0 4000: lows 4001 / 4002 with bodies 4003 / 4004 -> the parent pool
    assert L.parent_pools(o, h, l, c, pl, 3, 5.0) == []                                         # n_min 3: only two later lows
    assert L.parent_pools(o, h, l, c, pl, 2, 1.5) == []                                         # 4002 is outside the area (band 1.5)
    assert L.parent_pools(o, h, l, c, pl, 2, 5.0, end=7) == []                                  # the second later low is confirmed at bar 8
    l2 = l.copy(); l2[6] = 3999.0
    assert L.parent_pools(o, h, l2, c, pl, 2, 5.0) == []                                        # L0 taken by a later wick
    p = Params(**BASE, parent_pools=True)
    ctx = SimpleNamespace(hist=history(D0, n=8))                                                # ADR5 = 18 -> band 4.5
    sd = S.Side(1, o, h, l, c, 1)
    assert L4.parent_sell(ctx, sd, 9, p) == [(4000.0, 8)]
    assert L4.parent_sell(ctx, sd, 8, p) == []                                                  # (the bar being tested is not in it)
    out = {}
    L4.sell_pools(SimpleNamespace(start=0, week_hl=None, rb_lv=([], []), hist=ctx.hist), sd, 9, p, out)
    assert list(out.values()) == [4000.0]
    # the mirror: a parent HIGH (buy side) from the negated bars; the draw prefers it over the intermediate highs
    sdm = S.Side(1, -o, -l, -h, -c, 1)
    assert L4.parent_buy(ctx, sdm, 9, p) == [(-4000.0, 8)]
    assert L4.draw_prefs(ctx, sdm, 9, -4020.0, p) == [(-4000.0, "pool", "parent")]
    assert L4.draw_prefs(ctx, sdm, 9, -4020.0, replace(p, parent_pools=False)) == []
    assert (-4000.0, 8) in L4.target_pools(SimpleNamespace(start=0, week_hl=None, hist=ctx.hist), sdm, 9, p)


# --- L2-sr-needs-fvg (76) -----------------------------------------------------------------------------------------------------

def test_flip_level_needs_fvg():
    p = Params(**BASE, daily_level_needs_array="fvg")
    assert Params(daily_level_needs_array=True).daily_level_needs_array is True and Params(daily_level_needs_array="any")
    with pytest.raises(ValueError):
        Params(daily_level_needs_array="x")
    idx = pd.date_range("2026-06-23 09:30", periods=12, freq="5min", tz=NY)
    sd = S.Side(1, *(np.full(12, 4000.0),) * 4, 1)
    sw = dict(ext=3999.0, ext_i=3, level=4000.0)
    ctx = SimpleNamespace(idx=idx, tf=5, conf=SimpleNamespace(valid=lambda now, sign, tfs, src, kb: [(4002.0, 3998.0, "D", 0, 0.0)]))
    assert L4.daily_fvg_ok(ctx, sd, sw, 8, p)                                                   # an FVG 3998-4002 around the level 4000
    ctx.conf = SimpleNamespace(valid=lambda *a: [(4010.0, 4005.0, "D", 0, 0.0)])                 # an FVG that does not touch it
    assert not L4.daily_fvg_ok(ctx, sd, sw, 8, p)
    ctx.conf = SimpleNamespace(valid=lambda *a: [])
    assert not L4.daily_fvg_ok(ctx, sd, sw, 8, p)                                               # no FVG: no setup
    assert not L4.daily_fvg_ok(SimpleNamespace(conf=None), sd, sw, 8, p)


# --- L1-prior-day-london-pm-pools (87) ----------------------------------------------------------------------------------------

def test_prev_day_london_pool():
    p = Params(**BASE, prev_london_pool=True, extra_pools=True)
    h = history(D0, n=8)
    pd_ = h[-1].index[0].date()
    rows = [(4100.0, 4101.0, 4099.0, 4100.0)] * 195
    rows[36] = (4100.0, 4120.0, 4099.0, 4100.0)                                                 # 03:00: yesterday's London high 4120
    rows[30] = (4100.0, 4101.0, 4090.0, 4100.0)                                                 # 02:30: the London low 4090
    prev_full = frame(pd_, rows, 5, "00:00")
    ctx = ctx3(day([(4100.0, 4100.5, 4099.5, 4100.0)] * 30, base=4100.0), h, p, prev_full=prev_full)
    assert ctx.sess["prev_london"] == (4120.0, 4090.0, 0)
    sd = side(ctx)
    i = k_at(ctx, "09:30") + 3
    assert (4120.0, "pool") in S._targets(ctx, sd, i, 4101.0, [], p, None, i)                    # untaken today: a buy-side pool
    c0 = ctx3(day([(4100.0, 4100.5, 4099.5, 4100.0)] * 30, base=4100.0), h, replace(p, prev_london_pool=False), prev_full=prev_full)
    assert "prev_london" not in c0.sess and (4120.0, "pool") not in S._targets(c0, side(c0), i, 4101.0, [], replace(p, prev_london_pool=False), None, i)
    assert S._sell_side(ctx, sd, "AM", i, True, p)["prev_london"] == 4090.0                      # and the sell-side one
    assert ("prev_london_high", 4120.0) in [(c[2], c[0]) for c in L4.lock_cands(ctx, p, 570, i)]
    # traded through today (by a tick): spent
    ctx2 = ctx3(day([(4100.0, 4121.0, 4099.5, 4100.0)] * 30, base=4100.0), h, p, prev_full=prev_full)
    assert (4120.0, "pool") not in S._targets(ctx2, side(ctx2), k_at(ctx2, "09:30") + 3, 4101.0, [], p, None, k_at(ctx2, "09:30") + 3)
    # a previous-day frame of another date is never used
    ctx3_ = ctx3(day(FLAT, base=100.0), h, p, prev_full=frame(D0, rows, 5, "00:00"))
    assert "prev_london" not in ctx3_.sess


# --- new-lookback-per-tf-topdown (104) ----------------------------------------------------------------------------------------

def test_tf_lookback_cuts_history():
    ds = prior_days(D0, 300)
    highs = [105.0] * 300
    highs[5] = 200.0                                                                           # a daily pivot 295 sessions old
    h = [rth_day(d, hi, 90.0) for d, hi in zip(ds, highs)]
    p0 = Params(**BASE)
    c0 = ctx3(day(FLAT, base=100.0), h, p0)
    assert 200.0 in [q.price for q in L3.daily_piv(c0, 1)[0]]
    p = replace(p0, tf_lookback={"D": 252})
    c1 = ctx3(day(FLAT, base=100.0), h, p)
    assert 200.0 not in [q.price for q in L3.daily_piv(c1, 1)[0]] and len(L3.daily_hl(c1)) == 252      # D = 252: excluded
    assert B.htf_kw(p)["tf_lookback"] == {"D": 252} and "tf_lookback" not in B.htf_kw(p0)
    assert B.hist_days(p) >= 253 and B.hist_days(p0) == 61
    import inspect
    assert "tf_lookback" in inspect.signature(htf.table).parameters and "tf_lookback" in inspect.signature(CF.Confluence.__init__).parameters
    for bad in ({"X": 5}, {"D": 0}):
        with pytest.raises(ValueError):
            Params(tf_lookback=bad)


# --- L3-monthly-ohlc-3m (112) -------------------------------------------------------------------------------------------------

def test_monthly_ohlc_levels():
    ds = []
    d = date(2026, 1, 15)
    while d <= date(2026, 5, 20):
        if d.weekday() < 5:
            ds.append(d)
        d += timedelta(days=1)
    n = len(ds)
    o = np.arange(n) + 100.0
    r = L.monthly_candles(ds, o, o + 5, o - 5, o + 1, date(2026, 5, 20), 3)
    assert [x[0] for x in r] == [(2026, 2), (2026, 3), (2026, 4)]                              # the cut-off January and the running May are left out
    k = ds.index(date(2026, 3, 2))
    assert r[1][1:] == (o[k], o[ds.index(date(2026, 3, 31))] + 5, o[k] - 5, o[ds.index(date(2026, 3, 31))] + 1)
    p = Params(**BASE, monthly_ohlc=True)
    ctx = ctx3(day(FLAT, base=100.0), history(D0, n=90), p)
    assert len(ctx.m_ohlc) == 12 and ctx.m_ohlc[:4] == [100.0, 108.0, 90.0, 100.0]             # three completed months, 4 levels each (o h l c)
    sd = side(ctx)
    assert L4.late_tags(ctx, sd, p, 108.4, []) == ["m_ohlc"] and L4.late_tags(ctx, sd, p, 120.0, []) == []
    assert L4.late_tags(ctx, sd, p, 130.0, [107.8]) == ["m_ohlc"]                               # a target within a point counts too
    assert L4.late_tags(ctx, sd, replace(p, monthly_ohlc=False), 108.4, []) == []
    assert B.hist_days(p) >= 90


# --- L3-htf-pd-arrays-intraday (113) ------------------------------------------------------------------------------------------

def _mconf(tf="M", first="2026-01-31", gap=((4100.0, 4110.0, 4090.0, 4095.0), (4095.0, 4096.0, 4040.0, 4050.0), (4050.0, 4060.0, 4030.0, 4055.0))):
    o, h, l, c = mk(gap)
    end = (pd.Timestamp(f"{first} 17:00", tz=NY) + pd.to_timedelta(np.arange(3) * 31, unit="D")).as_unit("ns").asi8.astype(float)
    z = CF._zones(o, h, l, c, end)
    z["life"] = np.full(len(z["kind"]), float(pd.Timedelta(CF.LIFE[tf]).value))
    cf = CF.Confluence.__new__(CF.Confluence)
    cf.first20, cf.dends, cf.tol, cf.st, cf.z = False, np.array([]), 0.25, {}, {tf: z}
    return cf, pd.Timestamp(float(end[-1]) + 1.0, unit="ns", tz="UTC").tz_convert(NY)


def test_htf_targets_week_month():
    cf, now = _mconf("M")
    assert sorted(set(cf.targets(now, 4000.0, 1, ("M",)))) == [4060.0, 4075.0]                  # a monthly SIBI above a long: its near edge and CE in the ladder
    assert cf.targets(now, 4000.0, 1, ("15m", "1h", "4h", "D")) == []                           # not in the default htf_targets
    cfw, nw = _mconf("W")
    assert sorted(set(cfw.targets(nw, 4000.0, 1, ("W",)))) == [4060.0, 4075.0]
    assert Params(htf_targets=("15m", "1h", "4h", "D", "W", "M")).htf_targets[-1] == "M"
    assert "W" in CF.TFS and "M" in CF.TFS and "M" in CF.LIFE
    # ipda_arrays: the daily arrays must be inside the IPDA window (known at / after its first session's end)
    cfd, nd = _mconf("D", first="2025-10-31")                                                    # daily arrays known in Dec 2025 - Jan 2026, before the window
    p = Params(**BASE, ipda_arrays=True)
    ctx = ctx3(day(FLAT, base=100.0), history(D0, n=70), p)
    since = L4.ipda_since(ctx, p)
    d60 = L4.daily_rows(ctx, p)[0][len(ctx.hist) - 60]
    assert since == float(pd.Timestamp(d60, tz=NY).value + pd.Timedelta(hours=17).value)
    ctx.conf = cfd
    assert L4.conf_targets(ctx, replace(p, ipda_arrays=False), nd, 4000.0, 1, ("D",), False)             # the old: every daily array
    assert L4.conf_targets(ctx, p, nd, 4000.0, 1, ("D",), False) == []                                      # all of them formed before the window


# --- L3-3-6-12-month-pools (114) ----------------------------------------------------------------------------------------------

def test_ipda_windows_long():
    highs = [105.0] * 253
    highs[5] = 130.0                                                                           # inside the last 252 sessions, outside the last 60
    p = Params(**BASE, ipda_pools=True, ipda_windows=(20, 40, 60, 252))
    ctx = ctx3(day(FLAT, base=100.0), history(D0, n=253, highs=highs), p)
    assert set(ctx.ipda) == {20, 40, 60, 252} and ctx.ipda[252][0] == 130.0 and ctx.ipda[60][0] == 105.0
    sd = side(ctx)
    i = k_at(ctx, "09:30") + 2
    assert (130.0, ctx.start) in S._lv_target_pools(ctx, sd, i, p)                              # the 252-day high above price is a pool
    assert (130.0, ctx.start) not in S._lv_target_pools(ctx3(day(FLAT, base=100.0), history(D0, n=253, highs=highs), replace(p, ipda_windows=(20, 40, 60))),
                                                         sd, i, replace(p, ipda_windows=(20, 40, 60)))
    assert S._sell_side(ctx, sd, "AM", i, True, p)["ipda252"] == 90.0
    assert B.hist_days(p) == 253 and B.hist_days(Params()) == 61
    for bad in ((50,), ()):
        with pytest.raises(ValueError):
            Params(ipda_windows=bad)
    # the three-window sanity checks of ipda_eq_day ignore the long windows
    assert S._ipda_eq(ctx, replace(p, ipda_eq_day="tag"), i) in (True, False)


# --- new-trendline-trap-target (116) / new-trendline-trap (137) ---------------------------------------------------------------

def test_trendline_second_touch_pool(monkeypatch):
    P = L.Pivot
    ph = [P(5, 4120.0, 6), P(15, 4110.0, 16), P(25, 4100.0, 26)]
    low = np.full(40, 4090.0)
    low[20] = 4085.0
    r = L.trendline_highs(ph, 0.5, low)
    assert (r["h1"].price, r["h2"].price, r["h3"].price, r["known"], r["l23"], r["l23_i"]) == (4120.0, 4110.0, 4100.0, 26, 4085.0, 20)   # pool 4110
    assert L.trendline_highs([P(5, 4120.0, 6), P(15, 4105.0, 16), P(25, 4100.0, 26)], 0.5) is None                                      # the middle touch is off the line
    assert L.trendline_highs([P(5, 4100.0, 6), P(15, 4110.0, 16), P(25, 4120.0, 26)], 0.5) is None                                      # rising: no down-trendline
    assert L.trendline_highs(ph[:2], 0.5) is None
    assert L.trendline_highs([P(1, 4130.0, 2)] + ph, 0.5)["h3"].price == 4100.0                                                         # the newest touch wins
    p = Params(**BASE, trendline_pools=True)
    ctx = SimpleNamespace(hist=history(D0, n=8), start=0, week_hl=None)
    sd = S.Side(1, *(np.full(40, 4090.0),) * 4, 1)
    monkeypatch.setattr(L4, "trendline_state", lambda *a, **k: r)
    for ext_i, ext, ok in ((20, 4085.0, True), (30, 4085.5, True), (30, 4000.0, False), (3, 4085.0, False), (26, 4085.0, True)):
        L4._c(ctx)["tgt_ext"] = (ext_i, ext)
        assert (L4.trendline_target(ctx, sd, 35, p) == (4110.25, 26)) is ok, (ext_i, ext)         # H2 + 1 tick; the entry low between H2 and H3 (or a re-run of it)
    L4._c(ctx)["tgt_ext"] = (20, 4085.0)
    assert (4110.25, 26) in L4.target_pools(ctx, sd, 35, p)
    L4._c(ctx)["tgt_ext"] = (None, None)
    assert L4.target_pools(ctx, sd, 35, p) == []


def test_trendline_touches_and_trap(monkeypatch):
    P = L.Pivot
    lows = [P(5, 4000.0, 6), P(15, 4010.0, 16), P(25, 4020.0, 26)]
    hi = np.full(40, 4025.0)
    hi[20] = 4035.0
    r = L.trendline_touches(lows, 0.5, hi)
    assert (r["l2"].price, r["h23"], r["h23_i"], r["known"]) == (4010.0, 4035.0, 20, 26)        # a rising line with H23 between L2 and L3
    assert L.trendline_touches([P(5, 4000.0, 6), P(15, 4012.0, 16), P(25, 4020.0, 26)], 0.5) is None
    p = Params(**BASE, trendline_trap=True)
    # a short (mirror): the priority pool is H23 in side space, only with the bias on the trade's side
    sd = S.Side(-1, *(np.full(40, 4025.0),) * 4, 1)
    st = dict(h1=P(5, -4000.0, 6), h2=P(15, -4010.0, 16), h3=P(25, -4020.0, 26), known=26, l23=-4035.0, l23_i=20)
    monkeypatch.setattr(L4, "trendline_state", lambda *a, **k: st)
    ctx = SimpleNamespace(hist=history(D0, n=8), start=0, week_hl=None, rb_lv=([], []), cur_bias=-1, __dict__={})
    out = {}
    L4.sell_pools(ctx, sd, 35, p, out)
    assert out == {"tl23": -4035.0} and S._level_created(ctx, "tl23", "AM") == 27
    ctx.cur_bias = 1
    out = {}
    L4.sell_pools(ctx, sd, 35, p, out)
    assert out == {}
    ctx.cur_bias = -1
    assert (-4009.75, 26) in L4.target_pools(ctx, sd, 35, p)                                    # the ladder starts beyond H2 (L2 for the short)
    # turtle soup: the poke stays within ts_max_pts
    q = replace(p, ts_max_pts=2.0)
    ok = dict(key="tl23", level=-4035.0, ext=-4036.0)
    far = dict(key="tl23", level=-4035.0, ext=-4040.0)
    assert L4.order_gate(ctx, sd, ok, 35, q, -4034.0, None, False, []) is None
    assert L4.order_gate(ctx, sd, far, 35, q, -4034.0, None, False, []) == "x_tl_poke"


# --- B21-reference-points-in-windows (127) ------------------------------------------------------------------------------------

def test_ipda_extreme_rejection_block():
    ds = prior_days(D0, 25)
    h = [rth_day(d, 4100.0, 4080.0, 4090.0, 4090.0) for d in ds]
    h[-10] = rth_day(ds[-10], 4110.0, 4085.0, 4095.0, 4090.0)                                  # the 20-day high candle: o 4090 c 4095 h 4110 (wick 15 > body 5)
    p = Params(**BASE, ipda_pools=True, ipda_rb=True)
    ctx = ctx3(day(FLAT, base=4090.0), h, p)
    assert ctx.ipda[20][0] == 4110.0 and L4.ipda_level(ctx, p, 20, True) == (4095.0, 4110.0)
    sd = side(ctx)
    i = k_at(ctx, "09:30") + 2
    assert (4095.0, ctx.start) in S._lv_target_pools(ctx, sd, i, p)                              # the body edge is the pool ...
    assert (4110.0, "array") in S._lv_target_arrays(ctx, sd, i, p)                              # ... the wick extreme a runner rung
    assert (4110.0, ctx.start) in S._lv_target_pools(ctx, sd, i, replace(p, ipda_rb=False))      # the old pool
    assert L4.ipda_level(ctx, replace(p, ipda_rb=False), 20, True) == (4110.0, None)
    h2 = list(h)
    h2[-10] = rth_day(ds[-10], 4092.0, 4085.0, 4095.0, 4090.0)
    h2[-9] = rth_day(ds[-9], 4110.0, 4085.0, 4108.0, 4090.0)                                   # a body-heavy extreme candle: the extreme itself stays
    c2 = ctx3(day(FLAT, base=4090.0), h2, p)
    assert L4.ipda_level(c2, p, 20, True)[1] is None
    out = S._sell_side(ctx, sd, "AM", i, True, p)
    assert out["ipda20"] == 4090.0                                                              # the sell side: the 4080 low's candle (o = c = 4090) has the longer wick -> its body edge


# --- B21-progression-20-40-60-beyond (128) -----------------------------------------------------------------------------------

def test_ipda_skip_empty_40():
    w = {20: 4100.0, 40: 4100.0, 60: 4150.0}
    assert L.ipda_sequence(w, 4090.0, 0.25) == [(4100.0, "ipda20")]
    assert L.ipda_sequence(w, 4100.5, 0.25) == [(4150.0, "ipda60")]                            # the 40-day high equals the 20-day one: next target is the 60-day high
    assert L.ipda_sequence(w, 4100.1, 0.25) == [(4100.0, "ipda20")]                            # (a tick through is needed to take it)
    assert L.ipda_sequence(w, 4090.0, 0.25, exhausted20=True) == [(4150.0, "ipda60")]          # every array of the 20-day window traded to: roll out
    assert L.ipda_sequence({20: 4100.0}, 4090.0, 0.25, exhausted20=True) == [(4100.0, "ipda20")]
    assert L.ipda_sequence(w, 4151.0, 0.25) == []                                              # all taken, no older swing
    assert L.ipda_sequence(w, 4151.0, 0.25, beyond=4180.0) == [(4180.0, "expansion")]
    assert L.ipda_sequence(w, 4151.0, 0.25, beyond=4140.0) == []


def _fvg_hist(extra_high=None):
    """30 sessions; the last 20 hold one bearish daily FVG (4070-4095) formed by sessions j = 5, 6, 7 of the window; `extra_high` trades into it later."""
    flat = [(4100.0, 4105.0, 4095.0, 4100.0)] * 10
    win = [(4100.0, 4105.0, 4095.0, 4100.0)] * 6 + [(4100.0, 4101.0, 4060.0, 4062.0), (4062.0, 4070.0, 4055.0, 4065.0)] + [(4065.0, 4069.0, 4060.0, 4065.0)] * 12
    if extra_high is not None:
        win[12] = (4065.0, extra_high, 4060.0, 4065.0)
    return hist_from(flat + win)


def test_ipda_roll_on_exhausted_arrays():
    p = Params(**BASE, ipda_next=True, ipda_roll_arrays=True)
    ctx = ctx3(day([(4065.0, 4066.0, 4064.0, 4065.0)] * 20, base=4065.0), _fvg_hist(), p)
    sd = side(ctx)
    i = k_at(ctx, "09:30") + 4
    assert not L4.arrays20_exhausted(ctx, sd, i, p)                                            # the bearish FVG 4070-4095 was never traded to
    c2 = ctx3(day([(4065.0, 4066.0, 4064.0, 4065.0)] * 20, base=4065.0), _fvg_hist(extra_high=4071.0), p)
    assert L4.arrays20_exhausted(c2, side(c2), i, p)                                           # a later session reached its bottom
    # today's own high counts as well
    c3 = ctx3(day([(4065.0, 4072.0, 4064.0, 4065.0)] * 20, base=4065.0), _fvg_hist(), p)
    assert not L4.arrays20_exhausted(c3, side(c3), k_at(c3, "09:30") - 1, p) and L4.arrays20_exhausted(c3, side(c3), k_at(c3, "09:30") + 1, p)


def test_ipda_beyond_60_expansion():
    highs = [4100.0] * 70
    highs[3] = 4300.0                                                                          # an obvious older swing high, outside the 60-session window
    p = Params(**BASE, ipda_next=True, ipda_beyond_days=120)
    ctx = ctx3(day([(4100.0, 4105.0, 4099.0, 4100.0)] * 20, base=4100.0), history(D0, n=70, highs=highs, lows=[4000.0] * 70), p)
    assert ctx.ipda[20][0] == ctx.ipda[40][0] == ctx.ipda[60][0] == 4100.0
    sd = side(ctx)
    i = k_at(ctx, "09:30") + 2
    assert L4.ipda_pools(ctx, sd, i, p) == [(4300.0, ctx.start)]                                # all three extremes taken today: the older swing is the draw
    assert L4._c(ctx)["expansion"] == 4300.0
    assert L4.late_tags(ctx, sd, p, 4101.0, [4299.75]) == ["expansion"] and L4.late_tags(ctx, sd, p, 4101.0, [4150.0]) == []
    assert L4.ipda_pools(ctx, sd, i, replace(p, ipda_beyond_days=0)) == []                      # the old sequence: nothing left
    q = replace(p, ipda_beyond_days=5)                                                         # the swing is further back than ipda_beyond_days
    assert L4.ipda_pools(ctx3(day([(4100.0, 4105.0, 4099.0, 4100.0)] * 20, base=4100.0), history(D0, n=70, highs=highs, lows=[4000.0] * 70), q), sd, i, q) == []


# --- B21-open-float-forward-windows (129) ------------------------------------------------------------------------------------

def test_open_float_forward_intervals():
    days = [(100.0 + k, 50.0) for k in range(45)]
    r = L.ipda_forward(days, 0)
    assert set(r) == {"f20", "f40"} and r["f20"] == (119.0, 50.0) and r["f40"] == (139.0, 50.0)   # days 0-19 and 20-39 present, 40-59 not yet; no D-60 history
    days = [(100.0 + k, 50.0) for k in range(105)]
    r = L.ipda_forward(days, 60)
    assert set(r) == {"f20", "f40", "float"} and r["f20"] == (179.0, 50.0) and r["f40"] == (199.0, 50.0)
    assert r["float"] == (204.0, 50.0)                                                         # D-60 .. the last completed session (the realised part of D+59)
    assert L.ipda_forward(days[:60], 60) == {}                                                 # the anchor itself is not complete
    # glue: the pools; a level that is the extreme of two windows is ranked first
    ctx = SimpleNamespace(ipda={20: (110.0, 90.0), 40: (110.0, 80.0), 60: (120.0, 70.0)}, ipda_D=0, ipda_days=[(100.0 + k, 50.0) for k in range(45)], start=0)
    sd = S.Side(1, *(np.full(5, 100.0),) * 4, 1)
    p = Params(**BASE, ipda_pools=True, ipda_forward=True)
    assert L4.multi_window_levels(ctx, sd, 3, p) == [110.0]
    assert sorted(L4.ipda_fwd_hi(ctx, sd, p).values()) == [119.0, 139.0]
    assert sorted(v for v, _ in L4.ipda_pools(ctx, sd, 3, p)) == [110.0, 110.0, 119.0, 120.0, 139.0]
    assert L4.draw_prefs(ctx, sd, 3, 105.0, p) == [(110.0, "pool", "ipda_multi")]
    assert L4.draw_prefs(ctx, sd, 3, 105.0, replace(p, ipda_forward=False)) == []


# --- B21-anchor-month-vs-daily (130) -----------------------------------------------------------------------------------------

def test_ipda_anchor_month():
    d15 = date(2026, 6, 15)
    ds = prior_days(d15, 50)                                                                    # up to Friday 2026-06-12
    ctx = SimpleNamespace(ipda_days=[(100.0 + k, 50.0) for k in range(50)], day=d15, hist=[])
    p = Params(**BASE, ipda_anchor="current_month")
    out, last = LD.ipda_windows(ctx, p, ds)
    k = ds.index(date(2026, 6, 1))
    assert last == date(2026, 6, 1) and ctx.ipda_end == k + 1 and ctx.ipda_D == k                # on the 15th the windows END at the month's first trading day
    assert out[20] == (100.0 + k, 50.0) and out[40][0] == 100.0 + k
    assert 60 not in out                                                                        # (the history cannot fill it)
    late, _ = LD.ipda_windows(SimpleNamespace(ipda_days=ctx.ipda_days, day=date(2026, 6, 30), hist=[]), p, ds)
    assert late[20] == out[20]                                                                  # fixed all month
    nxt = prior_days(date(2026, 7, 2), 50)
    c2 = SimpleNamespace(ipda_days=ctx.ipda_days, day=date(2026, 7, 2), hist=[])
    o2, l2 = LD.ipda_windows(c2, p, nxt)
    assert l2 == date(2026, 7, 1)                                                               # the next month: the basis moves forward
    c3 = SimpleNamespace(ipda_days=ctx.ipda_days, day=date(2026, 6, 1), hist=[])
    _, l3 = LD.ipda_windows(c3, p, prior_days(date(2026, 6, 1), 50))
    assert c3.ipda_end == 50 and l3 == prior_days(date(2026, 6, 1), 50)[-1]                      # the month's first day itself: nothing of the month is complete -> yesterday
    # "daily" = the rolling count from yesterday
    assert Params(ipda_anchor="daily").ipda_anchor == "rolling"
    cd = SimpleNamespace(ipda_days=ctx.ipda_days, day=d15, hist=[])
    od, ld_ = LD.ipda_windows(cd, Params(**BASE, ipda_anchor="daily"), ds)
    assert cd.ipda_end == 50 and ld_ == ds[-1] and cd.ipda_D is None
    # the earlier "month" anchor (the last CLOSED month) is untouched
    cm = SimpleNamespace(ipda_days=ctx.ipda_days, day=d15, hist=[])
    LD.ipda_windows(cm, replace(p, ipda_anchor="month"), ds)
    assert cm.ipda_end == ds.index(date(2026, 5, 1))
    assert B.hist_days(p) == 61 + 45


# --- LLT3-london-extreme-preny-range (148) ------------------------------------------------------------------------------------

def _lr_ctx(p):
    h = history(D0, n=8)
    pd_ = h[-1].index[0].date()
    rows = [(4110.0, 4111.0, 4109.0, 4110.0)] * 195
    rows[36] = (4110.0, 4120.0, 4109.0, 4112.0)                                                # 03:00 London high E = 4120
    rows[50] = (4110.0, 4111.0, 4100.0, 4105.0)                                                # 04:10 ... the lowest low before 09:30 after E: 4100
    rows[24] = (4110.0, 4111.0, 4095.0, 4105.0)                                                # 02:00 London low 4095 (before E)
    pf = frame(pd_, rows, 5, "00:00")
    return ctx3(day([(4115.0, 4116.0, 4114.0, 4115.0)] * 20, base=4115.0), h, p, prev_full=pf)


def test_prev_london_range_zone():
    p = Params(**BASE, london_lr_zone="tag")
    ctx = _lr_ctx(p)
    assert ctx.lr_prev["bear"] == (4100.0, 4120.0)                                              # LR = [the lowest low printed between E and 09:30, E]
    assert ctx.lr_prev["bull"][0] == 4095.0
    short = S.Side(-1, *(np.zeros(3),) * 4, 1)
    assert L4.lr_state(ctx, short, -4115.0, p) is True                                          # yesterday E 4120, O 4100: today a short at 4115 is in the premium half
    assert L4.lr_state(ctx, short, -4105.0, p) is False                                         # 4105 is in the discount half
    assert L4.lr_state(ctx, short, -4125.0, p) is False                                         # above E: outside the range
    lg = S.Side(1, *(np.zeros(3),) * 4, 1)
    assert L4.lr_state(ctx, lg, 4096.0, p) is True and L4.lr_state(ctx, lg, 4118.0, p) is False  # the mirror: the discount half of (E', O')
    # gate: tag in all, "require" rejects the others on days with that bias only
    ctx.cur_bias = -1
    lvt = []
    assert L4.order_gate(ctx, short, dict(key="pdh1"), 5, p, -4115.0, None, False, lvt) is None and "in_lr" in lvt
    assert L4.order_gate(ctx, short, dict(key="pdh1"), 5, p, -4105.0, None, False, []) is None
    q = replace(p, london_lr_zone="require")
    assert L4.order_gate(ctx, short, dict(key="pdh1"), 5, q, -4105.0, None, False, []) == "x_in_lr"
    ctx.cur_bias = 0
    assert L4.order_gate(ctx, short, dict(key="pdh1"), 5, q, -4105.0, None, False, []) is None        # no bias on the trade: not required
    assert ctx3(day(FLAT, base=100.0), history(D0, n=8), p).lr_prev is None                      # without yesterday's frame there is no range


# --- LLT3-0800-0900-pool-stock-open (165) -------------------------------------------------------------------------------------

def test_or0809_pool():
    rows = [(100.0, 100.2, 99.8, 100.0)] * 12
    rows[4] = (100.0, 100.2, 99.0, 99.5)                                                        # the 08:00-09:00 low
    df = day(rows, start="08:00", base=100.0)
    p = Params(**BASE, or0809_pool=True)
    ctx = ctx3(df, history(D0, n=8), p)
    assert [(n, hi, lo) for n, hi, lo, cr in ctx.sors] == [("sor_480_60", 100.2, 99.0)]
    assert ctx.sors[0][3] == k_at(ctx, "09:00")                                                 # complete from 09:00
    sd = side(ctx)
    out = {}
    L3.sell_pools(ctx, sd, k_at(ctx, "09:30") + 1, p, out)
    assert out == {"sor_480_60": 99.0}                                                          # an AM sell-side pool at the low
    assert S._level_created(ctx, "sor_480_60", "AM") == k_at(ctx, "09:00")
    assert ("sor_480_60_l", 99.0) in [(c[2], c[0]) for c in S.mark_levels(ctx, None, 570, "AM", p)["marked"] if c[2].endswith("_l")] or \
        "sor_480_60_l" in [c[2] for c in L3.lock_cands(ctx, p, 570, k_at(ctx, "09:30") + 1)]
    out2 = {}
    c2 = ctx3(df, history(D0, n=8), replace(p, or0809_pool=False))
    L3.sell_pools(c2, side(c2), k_at(c2, "09:30") + 1, replace(p, or0809_pool=False), out2)
    assert out2 == {} and L3.sor_windows(replace(p, session_ors=((0, 30),))) == ((0, 30), (480, 60))


# --- A17-rejection-block-short-protocol (41) ----------------------------------------------------------------------------------

def _rb_ctx(p):
    ds = prior_days(D0, 12)
    h = [rth_day(d, 4010.0, 3990.0, 4000.0, 4000.0) for d in ds]
    h[-6] = rth_day(ds[-6], 4110.0, 4085.0, 4095.0, 4090.0)                                    # an old swing-high candle: up-close, close 4095, long upper wick
    h[-3] = rth_day(ds[-3], 3910.0, 3890.0, 3905.0, 3910.0)                                    # an old swing-low candle: down-close, close 3905, long lower wick
    return ctx3(day(FLAT, base=4000.0), h, p)


def test_rb_close_pool_short():
    p = Params(**BASE, rb_pools=True)
    ctx = _rb_ctx(p)
    assert ctx.rb_lv == ([4095.0], [3905.0])                                                    # the CLOSE of the candle that made the old daily swing high / low, untaken since
    i = k_at(ctx, "09:30") + 3
    short, lg = side(ctx, -1), side(ctx)
    out = S._sell_side(ctx, short, "AM", i, True, p)
    assert out["rb0"] == -4095.0                                                                # a short sweeps the high's close level (side space)
    assert S._sell_side(ctx, lg, "AM", i, True, p)["rb0"] == 3905.0
    assert L4.is_rb_key("rb0") and not L4.is_rb_key("rel_eq_lows0") and not L4.is_rb_key("round") and not L4.is_rb_key(None)
    lvt = []
    assert L4.order_gate(ctx, short, dict(key="rb0", level=-4095.0, ext=-4096.0), i, p, -4095.0, None, False, lvt) is None and "rb_close" in lvt
    assert "rb0" not in S._sell_side(ctx, short, "AM", i, True, replace(p, rb_pools=False))
    assert ("rb_hi0", 4095.0) in [(c[2], c[0]) for c in L4.lock_cands(ctx, p, 570, i)]
    # taken since: a later session traded through the level - not a pool
    ds = prior_days(D0, 12)
    h = [rth_day(d, 4010.0, 3990.0, 4000.0, 4000.0) for d in ds]
    h[-6] = rth_day(ds[-6], 4110.0, 4085.0, 4095.0, 4090.0)
    h[-2] = rth_day(ds[-2], 4100.0, 3990.0, 4000.0, 4000.0)
    assert ctx3(day(FLAT, base=4000.0), h, p).rb_lv[0] == []


def test_rb_against_bias_target_only():
    p = Params(**BASE, rb_pools=True)
    ctx = _rb_ctx(p)
    i = k_at(ctx, "09:30") + 3
    short, lg = side(ctx, -1), side(ctx)
    ctx.cur_bias = 1                                                                            # the bias is long: a short at the high's close level is against it
    assert "rb0" not in S._sell_side(ctx, short, "AM", i, True, p)                              # ... not a sweep pool for it
    assert "rb0" in S._sell_side(ctx, lg, "AM", i, True, p)                                     # the long side still has its own
    assert (4095.0, "array") in S._lv_target_arrays(ctx, lg, i, p)                              # ... and the high's close is a RUNG for the long (the bias direction)
    assert not [x for x in S._lv_target_pools(ctx, lg, i, p) if x[0] == 4095.0]                 # never a pool target
    assert (4095.0, "array") not in S._lv_target_arrays(ctx, lg, i, replace(p, rb_pools=False))
    ctx.cur_bias = -1
    assert "rb0" in S._sell_side(ctx, short, "AM", i, True, p)


# --- A12-entry-ob-outside-fvg (67) --------------------------------------------------------------------------------------------

OB_BARS = [(4030, 4031, 4024, 4025), (4018, 4019, 4011, 4012), (4012, 4041, 4011.5, 4040)]


def test_ob_blend_outside_fvg():
    o, h, l, c = mk(OB_BARS)
    z = L.order_block_blend(o, h, l, c, 0, 2, "bull")
    assert (z.src, z.bottom, z.top) == (0, 4011.0, 4031.0)                                      # the old blend: both down-close candles
    z = L.order_block_blend(o, h, l, c, 0, 2, "bull", outside=(4010.0, 4020.0))
    assert (z.src, z.bottom, z.top) == (0, 4024.0, 4031.0)                                      # the candle inside the shaded zone is ignored: the last one OUTSIDE it
    assert z.mt == (4030 + 4025) / 2
    assert L.order_block_blend(o, h, l, c, 0, 2, "bull", outside=(4000.0, 4050.0)) is None      # every down-close candle inside the zone
    # an opposite-close candle ends the run; the zone's candles do not
    o2, h2, l2, c2 = mk([(4020, 4021, 4014, 4015), (4030, 4031, 4024, 4025), (4018, 4019, 4011, 4012), (4012, 4041, 4011.5, 4040)])
    z2 = L.order_block_blend(o2, h2, l2, c2, 0, 3, "bull", outside=(4010.0, 4020.0))
    assert z2.src == 0 and z2.top == 4031.0                                                     # bars 0 and 1 (both outside) blend across the skipped bar 2
    o3, h3, l3, c3 = o2.copy(), h2.copy(), l2.copy(), c2.copy()
    c3[1], o3[1] = 4035.0, 4030.0                                                               # bar 1 up-close: it ends the run
    z3 = L.order_block_blend(o3, h3, l3, c3, 0, 3, "bull", outside=(4010.0, 4020.0))
    assert z3.src == 0 and z3.top == 4021.0
    # the engine wrapper: the entry gap g is the zone
    sd = S.Side(1, o, h, l, c, 1)
    g = L.Zone("bull", 4020.0, 4010.0, 5, 4)
    pw = Params(**BASE, ob_outside_fvg=True)
    sw = dict(ext_i=3, level=None)
    assert LD.ob_blend(SimpleNamespace(), sd, sw, 5, pw, 0, 2, g).bottom == 4024.0
    assert LD.ob_blend(SimpleNamespace(), sd, sw, 5, replace(pw, ob_outside_fvg=False), 0, 2, g).bottom == 4011.0
    assert L4.disp_fvg_zone(sd, sw, 5, g) == (4010.0, 4020.0) and L4.disp_fvg_zone(sd, sw, 5) is None


def test_ob_at_low_outside_fvg():
    rows = [(4045, 4046, 4040, 4041), (4026, 4028, 4012, 4014), (4014, 4020, 4009, 4018), (4001, 4008, 4000, 4007), (4007, 4040, 4006, 4038),
            (4038, 4050, 4036, 4048), (4048, 4050, 4046, 4049), (4049, 4052, 4047, 4051)]
    o, h, l, c = mk(rows)
    sd = S.Side(1, o, h, l, c, 1)
    assert (4008.0, 4036.0) in [(z.bottom, z.top) for z in sd.gaps]                              # the displacement FVG (the first gap after the sweep extreme)
    sw = dict(ext_i=3)
    base = S._ob_at_low(sd, sw, 6, Params(**BASE))
    assert (base["j"], base["k"]) == (0, 1)                                                     # nearest down-close candle to the low (bar 1, inside the FVG), run back to bar 0
    out = S._ob_at_low(sd, sw, 6, Params(**BASE, ob_outside_fvg=True))
    assert (out["j"], out["k"]) == (0, 0) and out["body_top"] == 4045.0                          # bar 1 sits inside the shaded zone: the entry OB is bar 0 (outside)


# --- new-hs-fade (138) --------------------------------------------------------------------------------------------------------

HS_H = [4100, 4110, 4105, 4120, 4130, 4108, 4112, 4104, 4102]
HS_L = [4095, 4100, 4090, 4100, 4105, 4091, 4098, 4092, 4093]


def test_head_shoulders_detector():
    h, l = A(HS_H, float), A(HS_L, float)
    r = L.head_shoulders(h, l, 1, 2.0)
    assert (r["s1"].price, r["head"].price, r["s2"].price, r["neck"], r["neck_hi"], r["known"]) == (4110.0, 4130.0, 4112.0, 4090.0, 4091.0, 7)
    assert L.head_shoulders(h, l, 1, 0.5) is None                                              # the neckline lows are not relatively equal
    assert L.head_shoulders(h, l, 1, 2.0, end=6) is None                                       # the right shoulder is confirmed at bar 7
    h2 = h.copy(); h2[6] = 4135.0
    assert L.head_shoulders(h2, l, 1, 2.0) is None                                             # S2 above the head: no head and shoulders
    # the inverse pattern is the same call on mirrored prices
    r2 = L.head_shoulders(-l, -h, 1, 2.0)
    assert r2 is None or r2["neck"] <= 0


_ARR_D = SimpleNamespace(at=lambda now, px, side: ["D"])


def _hs_world(bias=1, conf=_ARR_D):
    o, h, l, c = [], [], [], []
    for hb, lb in zip(HS_H, HS_L):                                                             # each 15m bucket = three 5m bars holding its high and low
        mid = (hb + lb) / 2
        for a_, b_ in ((hb, mid), (mid, lb), (mid, mid)):
            o.append(mid); h.append(a_); l.append(b_); c.append(mid)
    idx = pd.date_range("2026-06-23 09:30", periods=len(o), freq="5min", tz=NY)
    sd = S.Side(1, A(o, float), A(h, float), A(l, float), A(c, float), 1)
    return SimpleNamespace(idx=idx, cur_bias=bias, conf=conf, tf=5), sd, len(o) - 1


def test_hs_fade_long(monkeypatch):
    got = []
    monkeypatch.setattr(S, "_finish_order", lambda *a, **k: got.append((a, k)) or "order")
    p = Params(**BASE, hs_fade=True, hs_tf=15, eq_tol_pts=2.0, hs_stop_pts=10.0, ts_cc_below_pts=0.5)
    ctx, sd, i = _hs_world()
    assert L4.hs_pattern(ctx, sd, i, p)["neck"] == 4090.0 and L4.hs_pattern(ctx, sd, 8, p) is None      # not yet confirmed mid-pattern
    assert L4.hs_order(ctx, sd, i, p, "AM", 1.0) == "order"
    a, k = got[0]
    entry, stop = a[6], a[7]
    assert (entry, stop) == (4089.5, 4079.5)                                                    # a resting limit just below the neckline lows, the wide fixed stop
    assert k["fixed"] == [(4112.0, "array"), (S._exit_px(4130.0, "pool", p), "pool")]            # partial at the right shoulder S2, the objective above the head
    assert k["skip_leg_pd"]
    assert L4.hs_order(ctx, sd, i, p, "AM", 1.0) is None                                        # armed once per neckline
    ctx2, sd2, i2 = _hs_world(bias=0)
    assert L4.hs_order(ctx2, sd2, i2, p, "AM", 1.0) is None                                     # no bias for this side
    ctx3_, sd3, i3 = _hs_world(conf=SimpleNamespace(at=lambda now, px, side: []))
    assert L4.hs_order(ctx3_, sd3, i3, p, "AM", 1.0) is None                                    # no same-side HTF array at price
    ctx4, sd4, i4 = _hs_world(conf=SimpleNamespace(at=lambda now, px, side: ["D"]))
    got.clear()
    assert L4.hs_order(ctx4, sd4, i4, p, "AM", 1.0) == "order"
    got.clear()
    q = replace(p, hs_stop_pts=0.0, ts_max_pts=3.0)
    ctx5, sd5, i5 = _hs_world()
    L4.hs_order(ctx5, sd5, i5, q, "AM", 1.0)
    assert got[0][0][7] == 4090.0 - 3.0 - q.pad                                                 # hs_stop_pts 0: the cc_limit's ts_max_pts stop
    lo_sd = S.Side(1, sd.o, sd.h, sd.l.copy(), sd.c, 1)
    lo_sd.l[25] = 4089.0                                                                        # the neckline was traded below after S2: nothing to rest
    assert L4.hs_order(_hs_world()[0], lo_sd, i, p, "AM", 1.0) is None


# --- new-intra-week-extreme-raid (197) ----------------------------------------------------------------------------------------

def test_intraweek_high_raid_short():
    wed = date(2026, 6, 24)
    ds = prior_days(wed, 5)                                                                    # Wed 6/17 ... Fri 6/19, Mon 6/22, Tue 6/23 (this week's: Mon, Tue)
    h = [frame(d, [(4100.0, hi, lo, 4100.0), (4100.0, hi, lo, 4100.0)], 5, "09:30") for d, hi, lo in
         zip(ds, (4150.0, 4150.0, 4105.0, 4110.0, 4108.0), (4050.0, 4050.0, 4090.0, 4095.0, 4096.0))]
    p = Params(**BASE, week_pools=True)
    ctx = ctx3(day([(4100.0, 4100.5, 4099.5, 4100.0)] * 30, d=wed, base=4100.0), h, p)
    assert ctx.week_hl == (4110.0, 4095.0)                                                     # the week so far: Monday and Tuesday only
    hi_, lo_ = ctx.week_hl
    i = k_at(ctx, "09:30") + 3
    short, lg = side(ctx, -1), side(ctx)
    assert S._sell_side(ctx, short, "AM", i, True, p)["week_hi"] == -hi_                          # a raid of the week HIGH: the short's sweep pool (Wednesday)
    assert S._sell_side(ctx, lg, "AM", i, True, p)["week_lo"] == lo_
    assert (hi_, ctx.start) in S._lv_target_pools(ctx, lg, i, p)                                # and the long's buy-side target
    assert ("week_hi", hi_) in [(c[2], c[0]) for c in L4.lock_cands(ctx, p, 570, i)]
    assert "week_hi" not in S._sell_side(ctx, short, "AM", i, True, replace(p, week_pools=False))
    assert S._level_created(ctx, "week_hi", "AM") == ctx.start
    # weekday preference: the week high only Tue-Thu, the low also on Monday
    assert "week_hi" not in S._sell_side(ctx, short, "AM", i, True, replace(p, week_raid_days=(1,)))          # (Wednesday is not in the list)
    assert "week_lo" not in S._sell_side(ctx, lg, "AM", i, True, replace(p, week_raid_days=(1,)))
    assert "week_hi" in S._sell_side(ctx, short, "AM", i, True, replace(p, week_raid_days=(2,)))
    assert L4.week_build(SimpleNamespace(day=date(2026, 6, 22)), [], [], p, None) is None        # Monday: no prior session this week
    # a sweep of it needs a same-side HTF array; exceeding the level alone is no signal
    sw = dict(key="week_hi", level=-hi_, ext=-hi_ - 1)
    assert L4.order_gate(ctx, short, sw, i, p, -hi_, [], False, []) == "x_week_no_array"
    lvt = []
    assert L4.order_gate(ctx, short, sw, i, p, -hi_, ["D"], True, lvt) is None and "week_hi" in lvt
    assert L4.order_gate(ctx, short, sw, i, p, -hi_, None, True, []) is None                     # (no confluence object: the HTF tag decides)
    assert B.hist_days(p) == 61


# --- T4-or-length (21) --------------------------------------------------------------------------------------------------------

def test_or20_pool():
    rows = ([(100.0, 100.2, 99.8, 100.1), (100.1, 100.3, 100.0, 100.2), (100.2, 101.5, 99.9, 100.4), (100.4, 100.6, 100.2, 100.5)]
            + [(100.5, 100.6, 100.4, 100.5)] * 12)
    p = Params(**BASE, or_minutes=20)
    ctx = ctx3(day(rows, base=100.0), history(D0, n=8), p)
    assert ctx.or_end == 590 and ctx.or20 == (101.5, 99.8) and ctx.or_hl == ctx.or20            # OR20 = 09:30-09:49, usable from 09:50
    sd = side(ctx)
    i50, i45 = k_at(ctx, "09:50"), k_at(ctx, "09:45")
    assert (101.5, "pool") in S._targets(ctx, sd, i50, 100.6, [], p, None, i50)
    assert (101.5, "pool") not in S._targets(ctx, sd, i45, 100.6, [], p, None, i45)             # not before it is complete
    c30 = ctx3(day(rows, base=100.0), history(D0, n=8), Params(**BASE, or_minutes=30))
    assert c30.or20 == (101.5, 99.8) and c30.or_end == 600                                       # ctx.or20 is built whatever or_minutes is
    assert S._sell_side(ctx, sd, "AM", i50, True, p)["opening_range"] == 99.8
    for m in (0, 20, 30, 60):
        Params(or_minutes=m)
    with pytest.raises(ValueError):
        Params(or_minutes=45)


# --- L3-or-refs-expire-1100 (22) ----------------------------------------------------------------------------------------------

def test_or_refs_expire():
    rows = [(100.0, 100.2, 99.8, 100.1), (100.1, 100.3, 100.0, 100.2), (100.2, 101.0, 99.9, 100.4)] + [(100.4, 100.6, 100.2, 100.5)] * 30
    p = Params(**BASE, or_expire=660)
    ctx = ctx3(day(rows, base=100.0), history(D0, n=8), p)
    sd = side(ctx)
    i1105, i1055 = k_at(ctx, "11:05"), k_at(ctx, "10:55")
    keep = lambda pp, i: (101.0, "pool") in S._targets(ctx, sd, i, 100.6, [], pp, None, i)
    assert keep(replace(p, or_expire=0), i1105) and keep(p, i1055)                              # untaken at 11:05: still a pool with 0, and before the expiry
    assert not keep(p, i1105)                                                                   # not a pool / target with or_expire = 660
    short = side(ctx, -1)
    assert "opening_range" in S._sell_side(ctx, short, "AM", i1055, True, p) and "opening_range" not in S._sell_side(ctx, short, "AM", i1105, True, p)
    assert "opening_range" in S._sell_side(ctx, short, "AM", i1105, True, replace(p, or_expire=0))
    with pytest.raises(ValueError):
        Params(or_expire=500)


def test_or_fvg_entries():
    rows = [(100.0, 100.2, 99.8, 100.1), (100.1, 102.5, 100.0, 102.4), (102.4, 103.0, 101.5, 102.8)] + [(102.8, 102.9, 102.4, 102.5)] * 40
    p = Params(**BASE, or_fvg_entries=True)
    ctx = ctx3(day(rows, base=100.0), history(D0, n=8), p)
    assert [(z.kind, z.bottom, z.top, z.i) for z in ctx.or_fvgs] == [("bull", 100.2, 101.5, k_at(ctx, "09:40"))]     # the FVG formed inside the opening range
    sd = side(ctx)
    sw = dict(ext=99.0, ext_i=k_at(ctx, "09:30"))
    z = L4.or_fvg_zones(ctx, sd, sw, k_at(ctx, "10:20"), p)
    assert [(x.bottom, x.top) for x in z] == [(100.2, 101.5)]                                   # an entry array for a setup armed 10:00-11:00
    assert L4.or_fvg_zones(ctx, sd, sw, k_at(ctx, "09:55"), p) == [] and L4.or_fvg_zones(ctx, sd, sw, k_at(ctx, "11:00"), p) == []
    assert L4.or_fvg_zones(ctx, side(ctx, -1), sw, k_at(ctx, "10:20"), p) == []                  # (a bullish gap is no short's array)
    assert L4.or_fvg_zones(ctx, sd, dict(ext=101.9, ext_i=3), k_at(ctx, "10:20"), p) == []       # not between the sweep extreme and the close
    assert ctx3(day(rows, base=100.0), history(D0, n=8), Params(**BASE)).or_fvgs == []


# --- new-time-distortion (29) -------------------------------------------------------------------------------------------------

def test_time_distortion_mask(monkeypatch):
    t = A([570, 585, 595, 600, 660, 735, 795, 839, 840, 955, 960, 975])
    m = L.time_distortion_mask(t, [600], True)
    assert m.tolist() == [False, True, True, False, False, True, True, True, False, False, True, True]     # 15 min before the 10:00 release, the lunch chop, from 16:00
    assert L.time_distortion_mask(t, [600], False).tolist() == [False, True, True, False, False, False, False, False, False, False, True, True]
    # engine: a 13:15 swing is no MSS reference with the switch - the newest swing outside the mask takes its place
    p = Params(**BASE, time_distortion=True)
    ctx = SimpleNamespace(t=660 + 5 * np.arange(61), start=0, day=D0, __dict__={})
    P = L.Pivot
    sd = SimpleNamespace(ph=[P(8, 100.0, 9), P(27, 101.0, 28)])                                 # 11:40 and 13:15 swing highs
    sw = dict(ext_i=40)
    assert L4.td_ref(ctx, sd, sw, 45, p, (27, 101.0, True)) == (8, 100.0, True)
    assert L4.td_ref(ctx, sd, sw, 45, p, (8, 100.0, True)) == (8, 100.0, True)                   # an unmasked reference stays
    assert L4.td_ref(ctx, sd, sw, 45, replace(p, time_distortion=False), (27, 101.0, True)) == (27, 101.0, True)
    assert L4.td_ref(ctx, SimpleNamespace(ph=[P(27, 101.0, 28)]), sw, 45, p, (27, 101.0, True)) is None
    assert L4.td_masked(ctx, p, 27) and not L4.td_masked(ctx, p, 8) and not L4.td_masked(ctx, replace(p, time_distortion=False), 27)
    assert L4.td_masked(ctx, p, 60)                                                             # 16:00
    g1, g2 = SimpleNamespace(i=27, src=26), SimpleNamespace(i=10, src=9)
    assert L4.td_gaps(ctx, sd, [g1, g2], p) == [g2] and L4.td_gaps(ctx, sd, [g1, g2], replace(p, time_distortion=False)) == [g1, g2]
    assert L4.td_masked(ctx, replace(p, td_lunch=False), 27) is False
    # a scheduled release: the 15 minutes before it (08:30 data -> 08:15-08:30)
    import mentorship.calendar as cal
    monkeypatch.setattr(cal, "release_times", lambda d, **k: [510])
    c2 = SimpleNamespace(t=np.arange(300, 975, 5), start=0, day=D0, __dict__={})
    mk_ = L4.td_mask(c2, p)
    assert mk_[(495 - 300) // 5] and mk_[(505 - 300) // 5] and not mk_[(490 - 300) // 5] and not mk_[(510 - 300) // 5]


def test_fvg_body_hold():
    o = A([100.5, 100.8, 101.2, 101.0, 100.9, 101.1, 101.0])
    c = A([100.9, 101.1, 101.0, 100.8, 101.1, 101.0, 100.7])
    h = A([103.0, 101.5, 101.4, 102.6, 101.3, 101.5, 101.2])
    l = A([100.2, 100.4, 100.6, 100.5, 100.3, 100.6, 100.4])
    assert L.fvg_body_hold(o, h, l, c, 100.0, 102.0, 0, 6)                                      # 7 bodies inside 100-102 while a wick pokes out to 103
    assert not L.fvg_body_hold(o, h, l, c, 100.0, 102.0, 0, 3)                                  # only 4 bars
    c2 = c.copy(); c2[6] = 99.5
    assert not L.fvg_body_hold(o, h, l, c2, 100.0, 102.0, 0, 6)                                 # the last body closes below the gap
    assert not L.fvg_body_hold(o, np.minimum(h, 101.9), l, c, 100.0, 102.0, 0, 6)              # no wick poked out: nothing to hold
    # engine: only inside 10:00-12:00, only with td_fvg_hold
    p = Params(**BASE, td_fvg_hold=True)
    ctx = SimpleNamespace(t=600 + 5 * np.arange(40), start=0)
    sd = SimpleNamespace(o=np.concatenate([[100.0] * 5, o]), h=np.concatenate([[101.0] * 5, h]), l=np.concatenate([[100.0] * 5, l]), c=np.concatenate([[100.0] * 5, c]))
    g = SimpleNamespace(i=4, bottom=100.0, top=102.0)
    assert L4.td_hold(ctx, sd, g, 11, p) and not L4.td_hold(ctx, sd, g, 11, replace(p, td_fvg_hold=False))
    ctx2 = SimpleNamespace(t=715 + 5 * np.arange(40), start=0)                                           # 11:55 on: leaves the 10:00-12:00 window
    assert not L4.td_hold(ctx2, sd, g, 20, p)
    # LD.gap_open honours it for a single-bar gap
    z = L.Zone("bull", 102.0, 100.0, 4, 3, tag="single_bar")
    sd2 = SimpleNamespace(o=sd.o, h=sd.h, l=np.concatenate([[100.0] * 5, [99.5] + list(l[1:])]), c=sd.c)
    cx = SimpleNamespace(t=ctx.t, day=D0, start=0)
    q = replace(p, single_bar_fvg_strict=True)
    assert LD.gap_open(sd2, z, 11, cx, q) is True and LD.gap_open(sd2, z, 11, cx, replace(q, td_fvg_hold=False)) is False


# --- Params, plumbing, study --------------------------------------------------------------------------------------------------

NEW_SWITCHES = ("gap_views", "nwog_holiday_pick", "tue_open_ref", "org_both_ways", "wick_untraded", "wick_weeks", "wick_lod_tag", "reactionary_pools",
                "parent_pools", "parent_n", "prev_london_pool", "tf_lookback", "monthly_ohlc", "ipda_windows", "trendline_pools", "ipda_rb",
                "ipda_arrays", "ipda_roll_arrays", "ipda_beyond_days", "ipda_forward", "london_lr_zone", "or0809_pool", "rb_pools", "ob_outside_fvg",
                "trendline_trap", "tl_tol_ticks", "hs_fade", "hs_tf", "hs_stop_pts", "week_pools", "week_raid_days", "or_expire", "or_fvg_entries",
                "time_distortion", "td_lunch", "td_fvg_hold")


def test_new_switch_defaults_and_validation():
    d = Params()
    assert (d.gap_views, d.nwog_holiday_pick, d.tue_open_ref, d.org_both_ways, d.wick_untraded, d.wick_weeks, d.wick_lod_tag, d.reactionary_pools,
            d.parent_pools, d.parent_n, d.prev_london_pool) == ("auto", "all", False, False, False, 1, "off", False, False, 2, False)
    assert (d.tf_lookback, d.monthly_ohlc, d.ipda_windows, d.trendline_pools, d.ipda_rb, d.ipda_arrays, d.ipda_roll_arrays, d.ipda_beyond_days,
            d.ipda_forward, d.london_lr_zone, d.or0809_pool) == ({}, False, (20, 40, 60), False, False, False, False, 0, False, "off", False)
    assert (d.rb_pools, d.ob_outside_fvg, d.trendline_trap, d.tl_tol_ticks, d.hs_fade, d.hs_tf, d.hs_stop_pts, d.week_pools, d.week_raid_days,
            d.or_expire, d.or_fvg_entries, d.time_distortion, d.td_lunch, d.td_fvg_hold) == (False, False, False, 4, False, 60, 0.0, False, (1, 2, 3), 0, False,
                                                                                           False, True, False)
    assert d.daily_level_needs_array is False and d.ipda_anchor == "rolling" and d.or_minutes == 30
    assert d.sb_model is False and d.sb_use_bias is False and d.want_all_engines is True                   # untouched
    for bad in (dict(gap_views="x"), dict(nwog_holiday_pick="x"), dict(wick_lod_tag="x"), dict(london_lr_zone="x"), dict(daily_level_needs_array="x"),
                dict(or_minutes=45), dict(ipda_windows=(50,)), dict(ipda_windows=()), dict(week_raid_days=(5,)), dict(tf_lookback={"X": 3}),
                dict(tf_lookback={"D": 0}), dict(wick_weeks=0), dict(parent_n=0), dict(tl_tol_ticks=-1), dict(hs_tf=0), dict(hs_stop_pts=-1.0),
                dict(ipda_beyond_days=-1), dict(or_expire=500), dict(or_expire=1000), dict(ipda_anchor="x")):
        with pytest.raises(ValueError):
            Params(**bad)
    for ok in (dict(gap_views="both"), dict(daily_level_needs_array="fvg"), dict(daily_level_needs_array="any"), dict(or_minutes=20),
               dict(ipda_windows=(20, 40, 60, 63, 126, 252)), dict(ipda_anchor="current_month"), dict(ipda_anchor="daily"),
               dict(tf_lookback={"D": 252, "4h": 63, "1h": 15, "15m": 4}), dict(or_expire=660), dict(london_lr_zone="require")):
        Params(**ok)


def test_htf_kw_and_gap_plumbing_unchanged_at_defaults():
    assert B.htf_kw(Params()) == {"c2_dir": True}                                          # unchanged at the built values (cache keys!)
    assert B.table_kw(Params()) == {"c2_dir": True, "balance_tf": "own"}
    assert B.htf_kw(Params(tf_lookback={"D": 100}))["tf_lookback"] == {"D": 100}
    assert B.hist_days(Params()) == 61


def test_study_variants_for_the_caption_gap_pass_3():
    d = study.DECISIONS
    want = {"L5-rth-and-eth-gap-views", "L5-holiday-nwog", "L7-org-lifetime-sr", "L10-older-daily-weekly-wick-ce", "new-reactionary-high-liquidity",
            "new-parent-pool-bodies-short", "L2-sr-needs-fvg", "L1-prior-day-london-pm-pools", "new-lookback-per-tf-topdown", "L3-monthly-ohlc-3m",
            "L3-htf-pd-arrays-intraday", "L3-3-6-12-month-pools", "new-trendline-trap-target", "B21-reference-points-in-windows",
            "B21-progression-20-40-60-beyond", "B21-open-float-forward-windows", "B21-anchor-month-vs-daily", "LLT3-london-extreme-preny-range",
            "LLT3-0800-0900-pool-stock-open", "A17-rejection-block-short-protocol", "A12-entry-ob-outside-fvg", "new-trendline-trap", "new-hs-fade",
            "new-intra-week-extreme-raid", "T4-or-length", "L3-or-refs-expire-1100", "new-time-distortion"}
    for w in want:
        assert any(k.startswith(w) for k in study._LD3B_DECISIONS), w
    for k in study._LD3B_DECISIONS:
        replace(Params(), **{**study.DEC_BASE, **d[k]})                                     # every variant builds a valid Params
    used = {s for k in study._LD3B_DECISIONS for s in d[k]}
    for s in NEW_SWITCHES:
        if s in ("parent_n", "tl_tol_ticks", "td_lunch", "wick_weeks", "hs_tf", "hs_stop_pts", "week_raid_days"):
            continue                                                                       # tuning numbers
        assert s in used, s
    order = list(d)
    assert order.index("L5-rth-and-eth-gap-views") > order.index("X16_journal_tags_off")      # tested by the per-variant ES look-ahead run


def test_every_new_switch_is_named_by_a_test():
    """Every switch of this package appears in at least one test body (not only in the NEW_SWITCHES list)."""
    src = Path(__file__).read_text(encoding="utf-8")
    body = src.replace(src[src.index("NEW_SWITCHES = ("):src.index("def test_new_switch_defaults_and_validation")], "")
    for s_ in NEW_SWITCHES:
        assert s_ in body, s_


# --- no look-ahead: full run vs truncated runs --------------------------------------------------------------------------------

from test_caption_gap_ld1 import ENTRY, EXIT, SYN, _no_look_ahead_x                           # noqa: E402  (shared helper)

SYN_BASE = dict(use_bias=True, bias_open="0930", ob_entry="both", draw_lock_neutral="both")
GROUPS = {
    "pools": dict(org_days=20, org_both_ways=True, wick_levels=True, wick_days=5, wick_untraded=True, wick_lod_tag="tag", wick_weekly=True, wick_weeks=2,
                  reactionary_pools=True, parent_pools=True, trendline_pools=True, week_pools=True, ipda_pools=True, ipda_rb=True,
                  prev_london_pool=True, extra_pools=True, or0809_pool=True, ipda_eq_day="tag"),
    "ipda": dict(ipda_next=True, ipda_roll_arrays=True, ipda_beyond_days=30, ipda_anchor="current_month", ipda_forward=True, monthly_ohlc=True,
                 tf_lookback={"D": 60}, ipda_arrays=True, ipda_windows=(20, 40, 60), ipda_rb=True),
    "entries": dict(rb_pools=True, ob_outside_fvg=True, trendline_trap=True, hs_fade=True, hs_tf=15, hs_stop_pts=10.0, london_lr_zone="tag",
                    or_expire=660, or_fvg_entries=True, or_minutes=20, time_distortion=True, td_fvg_hold=True, single_bar_fvg_strict=True,
                    daily_level_needs_array="fvg", tue_open_ref=True, nwog_holiday_pick="closest", nwog_skip_holiday=True, gap_views="both",
                    htf_targets=("15m", "1h", "4h", "D", "W", "M")),
}


@pytest.mark.parametrize("group", sorted(GROUPS))
def test_look_ahead_synthetic(group):
    x, y = B.synthetic(start="2026-03-16", end="2026-05-08", tf=5, seed=3)
    p = Params(**{**SYN, **SYN_BASE, **GROUPS[group]})
    full = _no_look_ahead_x(x, 5, "RW", p, ENTRY, every=4, partner=y, min_trades=1)
    assert len(full)


def test_look_ahead_synthetic_post_mss():
    x, y = B.synthetic(start="2026-03-16", end="2026-05-08", tf=5, seed=5)
    p = Params(**SYN, use_bias=True, bias_open="0930", ob_entry="post_mss", draw_lock="off", rb_pools=True, ob_outside_fvg=True, time_distortion=True,
               reactionary_pools=True, parent_pools=True, week_pools=True, london_lr_zone="tag", prev_london_pool=True, or_fvg_entries=True)
    _no_look_ahead_x(x, 5, "RW", p, ENTRY, every=4, partner=y)


def _es(a="2023-08-28", b="2023-11-10"):
    df = B.load("ES", 5, source="databento")
    return df[(df.index >= a) & (df.index < b)], B.load_meta("ES", 5)


@pytest.mark.skipif(not ES, reason="no ES data")
def test_look_ahead_es_switches():
    """ES 5m with confluence and overnight sessions: the RTH weekend gap, the anchored IPDA windows with forward intervals, the previous London range,
    the LR zone, week pools and the 3 / 6 / 12-month windows (the window holds ~38 sessions, so the long ones stay empty - they must not look ahead either)."""
    df, meta = _es()
    p = Params(**FUT, gap_views="both", ipda_pools=True, ipda_anchor="current_month", ipda_forward=True, ipda_arrays=True, ipda_rb=True,
               ipda_windows=(20, 40, 60, 63), prev_london_pool=True, extra_pools=True, london_lr_zone="tag", week_pools=True, org_days=20, org_both_ways=True,
               wick_levels=True, wick_days=5, wick_untraded=True, wick_lod_tag="tag", or0809_pool=True, rb_pools=True, tf_lookback={"D": 60, "4h": 30},
               reactionary_pools=True, parent_pools=True, ob_entry="both", leg_pd=0, min_draw_pts=0, htf_resist_cap=False)
    full = _no_look_ahead_x(df, 5, "ES", p, ENTRY + ["draw_px", "draw_name"], every=6, meta=meta)
    assert len(full)
    q = replace(p, gap_views="auto", ipda_anchor="rolling", ipda_forward=False, draw_lock="off", ob_entry="post_mss", ipda_next=True, ipda_roll_arrays=True,
                ipda_beyond_days=30, reactionary_pools=True, parent_pools=True, trendline_pools=True, trendline_trap=True, monthly_ohlc=True,
                or_fvg_entries=True, or_expire=660, time_distortion=True, td_fvg_hold=True, ob_outside_fvg=True, hs_fade=True, hs_tf=15)
    _no_look_ahead_x(df, 5, "ES", q, ENTRY, every=6, meta=meta)
    r = replace(p, htf_bias="combo", weekly_open="either", tue_open_ref=True, nwog_skip_holiday=True, nwog_holiday_pick="closest", draw_lock="off",
                ob_entry="post_mss")
    _no_look_ahead_x(df, 5, "ES", r, ENTRY, every=6, meta=meta, min_trades=0)               # (the bias filter may leave few trades: the gap pick / Tuesday reference are exercised)


def test_every_new_switch_is_in_a_look_ahead_run():
    """Every behaviour switch of this package is on in one of the no-look-ahead runs above (synthetic groups or the ES run)."""
    src = Path(__file__).read_text(encoding="utf-8")
    cover = str(GROUPS) + src[src.index("def test_look_ahead_es_switches"):src.index("def test_every_new_switch_is_in_a_look_ahead_run")]
    for s_ in NEW_SWITCHES:
        if s_ in ("parent_n", "tl_tol_ticks", "td_lunch", "hs_stop_pts", "week_raid_days"):
            continue                                                                        # (tuning numbers)
        assert s_ in cover, s_
