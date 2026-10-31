"""Caption-gap pass, package bias_htf#7/7: the ENGINE hooks (bh7e.py) on hand-made days built with the real DayCtx and DayPlan (the London confirmation, the NY-continues-London gate, the sub-range
exception and the top skip, the 15m %R tag, the PO3 Judas tag, the London breaker side, the array-lost flip, the late-entry target cut, the CC day-trade preset, the weekly-flip premise arrays), the table with
every new column and its row-level no-look-ahead cut, the no-look-ahead runs (full vs truncated; synthetic windows, hand-made days; ES windows skip without the data) and the check that every new switch is
live in an executed run (second file of tests/test_caption_gap_bh7.py). Nothing here needs market data except the ES windows; no file outside the repo is written."""
import warnings
from datetime import date

import numpy as np
import pandas as pd
import pytest

from mentorship import backtest as B, bh2 as BH2, bh2e, bh5e, bh7 as BH7, bh7e as E7, bias_day as BD, daycontext as DW, htf, strategy as S
from mentorship.strategy import Params
from dataclasses import dataclass as _oa_dc


@_oa_dc
class Params(Params):   # OA1029 Q92: these tests exercise other rules; the order-block narrative gate (default on) leaves them no trades
    ob_need_narrative: bool = False

from test_review_fixes import BASE, history, frame  # noqa: E402
from test_entries_stops import _no_look_ahead  # noqa: E402
from test_caption_gap_dwc1 import mk, at, COLS, FUT, ES, Conf  # noqa: E402
from test_caption_gap_bh1 import BR  # noqa: E402
from test_caption_gap_bh1f import LA, IM, _walks  # noqa: E402
from test_caption_gap_bh3b import order  # noqa: E402

D1 = date(2026, 3, 10)                          # a Tuesday


def p7(**kw):
    return Params(**BASE, htf_bias="combo", bias_neutral="both", **kw)


def mkd(p, rows, bias=None, hist=None, d=D1, base=100.0, start="09:30", **kw):
    ctx = mk(d, hist if hist is not None else history(d), p, rows=rows, bias_row=bias, start=start, base=base, **kw)
    ctx.intermarket = {}
    return ctx


def rth(d, o, h, l, c):
    """A regular-session day (09:30-16:00, 5m) with the given open / high / low / close."""
    rows = [(o, h, l, (o + c) / 2.0)] + [(c, c + 0.05, c - 0.05, c)] * 77
    return frame(d, rows, 5, "09:30")


def outside_hist(d=D1):
    """Eight prior sessions: a bullish daily FVG [101, 103] (sessions 0-2) and, yesterday, a down-close OUTSIDE day (105 -> 101.5, high 108, low 100.5) that traded into it."""
    base = history(d, 8)
    ohlc = [(100, 101, 99, 100), (100, 106, 100, 105), (105, 107, 103, 106), (106, 107, 104, 105), (105, 106.5, 104, 105.5), (105.5, 106.8, 104.5, 105.2), (105.2, 107, 104.2, 105.0), (105, 108, 100.5, 101.5)]
    return [rth(f.index[0].date(), *r) for f, r in zip(base, ohlc)]


CONFIRMED = [(101.5, 101.6, 100.2, 100.4), (100.4, 101.3, 100.3, 100.9), (100.9, 101.0, 100.0, 100.2)] + [(100.2, 100.3, 100.1, 100.2)] * 110
CONSOL = [(100.5, 100.7, 100.3, 100.5)] * 113


# --- new-london-confirm-after-daily-signal -------------------------------------------------------------------------------------------

def test_outside_bisi_reading():
    ob = E7.outside_bisi(outside_hist(), p7())
    assert ob == (-1, 108.0, 100.5, 101.0, 103.0)
    quiet = history(D1, 8)
    assert E7.outside_bisi(quiet, p7()) is None
    assert E7.outside_bisi(quiet[:3], p7()) is None
    # an up-close outside day into a bearish FVG is the mirror
    mir = [rth(f.index[0].date(), *(200 - x for x in (r[0], r[2], r[1], r[3]))) for f, r in zip(history(D1, 8), [(100, 101, 99, 100), (100, 106, 100, 105), (105, 107, 103, 106), (106, 107, 104, 105),
                                                                                                                       (105, 106.5, 104, 105.5), (105.5, 106.8, 104.5, 105.2), (105.2, 107, 104.2, 105.0), (105, 108, 100.5, 101.5)])]
    mo = E7.outside_bisi(mir, p7())
    assert mo is not None and mo[0] == 1 and mo[3:] == (97.0, 99.0)


def test_london_confirm():
    """Outside-day setup, London trades below the BISI low and rejects: the AM short is allowed. London inside: blocked."""
    p = p7(london_confirm="block")
    ok = mkd(p, CONFIRMED, BR(combo=-1), hist=outside_hist(), start="02:00")
    i = at(ok, "09:50")
    assert E7.london_state(ok, p, -1, "AM", i) == "ok"
    assert E7.side_ok(ok, p, -1, "AM", i) is None
    bad = mkd(p, CONSOL, BR(combo=-1), hist=outside_hist(), start="02:00")
    assert E7.london_state(bad, p, -1, "AM", i) == "unconfirmed"
    assert E7.side_ok(bad, p, -1, "AM", i) == "x_bh7_london_confirm"
    assert E7.side_ok(bad, p, 1, "AM", i) is None                                   # only the short side of a down-close outside day
    assert E7.side_ok(bad, p, -1, "PM", at(bad, "13:40")) is None                    # the NY morning only
    assert E7.side_ok(bad, p, -1, "AM", at(bad, "04:00")) is None                    # London is not complete yet
    assert E7.side_ok(bad, p7(), -1, "AM", i) is None                                # off
    assert DW.side_ok(bad, p, -1, "AM", i) == "x_bh7_london_confirm"                 # wired through the side_ok chain
    # the retrace but no close back under: unconfirmed
    no_close = [(101.5, 101.6, 100.2, 100.4), (100.4, 101.3, 100.3, 101.1)] + [(101.1, 101.2, 101.0, 101.1)] * 111
    nc = mkd(p, no_close, BR(combo=-1), hist=outside_hist(), start="02:00")
    assert E7.london_state(nc, p, -1, "AM", i) == "unconfirmed"
    # no trade below the BISI low at all: unconfirmed
    high = mkd(p, [(102.0, 102.2, 101.6, 102.0)] * 113, BR(combo=-1), hist=outside_hist(), start="02:00")
    assert E7.london_state(high, p, -1, "AM", i) == "unconfirmed"
    # the invalidation: the outside day's high (108) trades - the short is blocked whatever London did
    spike = CONFIRMED[:40] + [(100.2, 108.5, 100.1, 100.4)] + CONFIRMED[41:]
    inv = mkd(p, spike, BR(combo=-1), hist=outside_hist(), start="02:00")
    assert E7.london_state(inv, p, -1, "AM", at(inv, "09:50")) == "invalid"
    assert E7.side_ok(inv, p, -1, "AM", at(inv, "09:50")) == "x_bh7_london_invalid"
    # no London bars in the frame (a day starting at 09:30 only is a different frame; here the bars exist): the engine does not judge a frame without London
    # the half-size mode
    ph = p7(london_confirm="half")
    sd = bad.sides_map[-1]
    lvt: list = []
    assert E7.size_mult(bad, sd, i, ph, lvt) == 0.5 and lvt == ["size_london_confirm"]
    assert E7.side_ok(bad, ph, -1, "AM", i) is None                                  # half does not block
    assert E7.side_ok(inv, ph, -1, "AM", at(inv, "09:50")) == "x_bh7_london_invalid"
    assert E7.size_mult(ok, ok.sides_map[-1], i, ph, []) == 1.0 and E7.size_mult(bad, bad.sides_map[1], i, ph, []) == 1.0
    assert BD.size_mult(bad, sd, i, ph, []) == 0.5                                   # wired through the size_mult chain
    assert E7.size_mult(bad, sd, i, p, []) == 1.0


# --- new-ny-continues-london ------------------------------------------------------------------------------------------------------------

LON_DOWN = [(100.0, 100.0, 98.0, 98.0)] + [(98.0, 98.1, 97.9, 98.0)] * 120


def test_london_dir_gate():
    """London down, no HTF array reached: an AM long is blocked. London down into a 4h BISI: an AM long is allowed."""
    p = p7(london_dir_gate=True)
    no_arr = mkd(p, LON_DOWN, BR(combo=0), start="02:00", conf=Conf(at_tfs=()))
    i = at(no_arr, "09:50")
    assert E7.london_dir(no_arr, i) == -1
    assert E7.side_ok(no_arr, p, 1, "AM", i) == "x_bh7_london_dir"
    assert E7.side_ok(no_arr, p, -1, "AM", i) is None                               # NY continues London's direction
    arr = mkd(p, LON_DOWN, BR(combo=0), start="02:00", conf=Conf(at_tfs=("4h",)))
    assert E7.side_ok(arr, p, 1, "AM", i) is None and E7.side_ok(arr, p, -1, "AM", i) is None             # at the array both sides are allowed
    low_only = mkd(p, LON_DOWN, BR(combo=0), start="02:00", conf=Conf(at_tfs=("15m",)))
    assert E7.side_ok(low_only, p, 1, "AM", i) == "x_bh7_london_dir"                                      # a 15m array is no HTF array
    nocf = mkd(p, LON_DOWN, BR(combo=0), start="02:00")
    assert E7.side_ok(nocf, p, 1, "AM", i) is None                                                        # no arrays to read: inert
    assert E7.side_ok(no_arr, p, 1, "PM", at(no_arr, "13:40")) is None                                     # AM only
    assert E7.side_ok(no_arr, p7(), 1, "AM", i) is None
    assert DW.side_ok(no_arr, p, 1, "AM", i) == "x_bh7_london_dir"
    flat = mkd(p, [(100.0, 100.1, 99.9, 100.0)] * 121, BR(combo=0), start="02:00", conf=Conf(at_tfs=()))
    assert E7.london_dir(flat, i) == 0 and E7.side_ok(flat, p, 1, "AM", i) is None                          # no London direction: no gate
    # the tag (written only with london_dir_tag)
    pt = p7(london_dir_tag=True)
    for ctx, sign, want in ((no_arr, -1, "nyl_cont"), (no_arr, 1, "nyl_rev_noarray"), (arr, 1, "nyl_rev")):
        o = dict(order())
        E7.order_ok(ctx, ctx.sides_map[sign], o, "AM", i, pt)
        assert want in o["lv_tags"].split("|"), (want, o["lv_tags"])
    o = dict(order())
    E7.order_ok(no_arr, no_arr.sides_map[1], o, "AM", i, p)
    assert "nyl" not in o["lv_tags"]                                                                          # the gate alone writes no tag


# --- new-london-breaker-precursor ----------------------------------------------------------------------------------------------------------

BREAKER = [(100.0, 100.6, 99.6, 100.2), (100.2, 100.4, 99.2, 99.4), (99.4, 99.5, 98.5, 98.7), (98.7, 99.6, 98.9, 99.5), (99.5, 100.5, 99.4, 100.4), (100.4, 101.5, 100.3, 101.3),
           (101.3, 101.2, 100.2, 100.4), (100.4, 100.6, 99.6, 99.8), (99.8, 100.0, 97.8, 98.0), (98.0, 98.6, 97.9, 98.5), (98.5, 99.4, 98.4, 99.3), (99.3, 102.2, 99.2, 102.0),
           (102.0, 102.4, 101.8, 102.2), (102.2, 102.5, 101.9, 102.3)] + [(102.3, 102.6, 102.0, 102.4)] * 110


def test_london_breaker_sets_am_side():
    p = p7(london_breaker_bias=True)
    ctx = mkd(p, BREAKER, BR(combo=0), start="02:00")
    i = at(ctx, "09:50")
    assert E7.london_breaker(ctx, p, i) == 1
    assert BD.want_at(ctx, p, "AM", i) == 1                                          # neutral daily bias: the bullish London breaker sets the AM side
    agree = mkd(p, BREAKER, BR(combo=1), start="02:00")
    assert BD.want_at(agree, p, "AM", i) == 1
    opposed = mkd(p, BREAKER, BR(combo=-1), start="02:00")
    assert BD.want_at(opposed, p, "AM", i) == -1                                     # an opposing daily bias stays
    iof = mkd(p, BREAKER, BR(combo=0, iof=-1), start="02:00")
    assert BD.want_at(iof, p, "AM", i) == 0                                          # the daily order flow is against the cue
    assert BD.want_at(ctx, p7(), "AM", i) == 0                                       # off
    assert BD.want_at(ctx, p, "PM", at(ctx, "13:40")) == 0                           # the AM side only
    assert E7.london_breaker(ctx, p, at(ctx, "04:00")) == 0                          # London is not complete
    mir = [(200 - o, 200 - l, 200 - h, 200 - c) for o, h, l, c in BREAKER]
    mc = mkd(p, mir, BR(combo=0), start="02:00")
    assert E7.london_breaker(mc, p, i) == -1 and BD.want_at(mc, p, "AM", i) == -1     # the bearish mirror
    plain = mkd(p, [(100.0, 100.2, 99.8, 100.0)] * 124, BR(combo=0), start="02:00")
    assert E7.london_breaker(plain, p, i) == 0 and BD.want_at(plain, p, "AM", i) == 0


# --- new-stopout-at-planned-array-next-day-flip -------------------------------------------------------------------------------------------

def test_array_lost_next_day_short():
    """The day after a close through the planned daily support: shorts against the bullish daily bias toward the next lower array; longs again once it traded."""
    p = p7(array_lost_flip=True)
    row = BR(combo=1, array_lost=1, array_lost_tgt=95.0)
    flat = [(100.0, 100.3, 99.7, 100.0)] * 60
    ctx = mkd(p, flat, row)
    i = at(ctx, "09:50")
    assert BD.want_at(ctx, p, "AM", i) == -1                                         # against the +1 bias
    touched = mkd(p, flat[:5] + [(100.0, 100.1, 94.8, 95.2)] + flat[6:], row)
    assert BD.want_at(touched, p, "AM", at(touched, "10:05")) == 1                   # the target array traded: longs again
    assert BD.want_at(touched, p, "AM", at(touched, "09:50")) == -1                  # (before that bar it had not)
    assert BD.want_at(ctx, p7(), "AM", i) == 1                                       # off: the daily bias stands
    notgt = mkd(p, flat, BR(combo=1, array_lost=1, array_lost_tgt=float("nan")))
    assert BD.want_at(notgt, p, "AM", i) == 1                                        # no next array: no flip
    mirror = mkd(p, flat[:5] + [(100.0, 105.4, 99.9, 105.0)] + flat[6:], BR(combo=-1, array_lost=-1, array_lost_tgt=105.0))
    assert BD.want_at(mirror, p, "AM", at(mirror, "10:05")) == -1 and BD.want_at(mirror, p, "AM", at(mirror, "09:50")) == 1       # the bearish mirror
    pre = E7.lock_prefs(ctx, p, row, 570, "AM", 0, 100.0, 10)
    assert pre == [(95.0, "array", "array_lost_tgt", 0, 0)] and E7.lock_prefs(ctx, p7(), row, 570, "AM", 0, 100.0, 10) == []
    assert E7.lock_prefs(ctx, p, BR(combo=1), 570, "AM", 0, 100.0, 10) == []
    o = dict(order())
    E7.order_ok(ctx, ctx.sides_map[-1], o, "AM", i, p)
    assert "array_lost" in o["lv_tags"].split("|")


# --- new-after-of-shift-sell-any-premium-array ---------------------------------------------------------------------------------------------

def test_post_flip_4h_array_short(monkeypatch):
    """With the stateful bias turned bearish mid-week, shorts take the 4h premium arrays below the week's high as the sweep array."""
    p = p7(weekly_flip_follow=True)
    ctx = mkd(p, [(100.0, 100.3, 99.7, 100.0)] * 40, BR(combo=0, flip=-1, flip_turn=-1))
    i = at(ctx, "09:50")
    sd, su = ctx.sides_map[-1], ctx.sides_map[1]
    assert E7.premise_extra(ctx, p, sd, i, "AM") == ("4h",) and E7.premise_extra(ctx, p, su, i, "AM") == ()
    assert E7.premise_extra(ctx, p7(), sd, i, "AM") == ()
    plain = mkd(p, [(100.0, 100.3, 99.7, 100.0)] * 40, BR(combo=0, flip=-1, flip_turn=0))
    assert E7.premise_extra(plain, p, sd, i, "AM") == ()
    from mentorship import sm3
    seen = []

    def fake(ctx_, sd_, i_, kb, names, *a, **k):
        seen.append(tuple(names))
        return [(-99.0, -101.0, kb)] if "4h" in names else []
    monkeypatch.setattr(S, "_ts_arrays", fake)
    # a bar that reaches the array (side space: the array [-101, -99] is reached from above)
    bar = ctx.idx[i]
    ctx.l[i] = 99.9
    sd.l[i] = -ctx.h[i]
    r = sm3.premise_sweep(ctx, sd, i, p, "AM")
    assert seen and "4h" in seen[0] and "15m" not in seen[0] and "1h" not in seen[0]               # only the flip's 4h arrays (the 15m / 60m premise stays off)
    assert r is None or r["key"] == "htf_array"
    seen.clear()
    assert sm3.premise_sweep(plain, plain.sides_map[-1], i, p, "AM") is None                           # no flip: no premise, the arrays are not even asked for
    assert not seen
    allow = p7(weekly_flip_follow=True, allow_htf_array_premise=True)
    sm3.premise_sweep(plain, plain.sides_map[-1], i, allow, "AM")
    assert seen and "15m" in seen[0] and "1h" in seen[0] and "4h" not in seen[0]                       # the built premise path is untouched without the flip
    assert bar is not None


# --- A21-longs-above-eq-subrange-discount -------------------------------------------------------------------------------------------------

def test_long_above_eq_in_subrange_discount():
    """The pd_two_level gate blocks a long above the 20-session EQ; with pd_subrange it passes in the lower half of quadrant 3 / 4 of the 60-day body range at an HTF array with a target; the upper half of
    quadrant 4 is skipped."""
    p = p7(pd_two_level=True, pd_subrange=True)
    row = BR(combo=1, eq20_body=100.0, range_lo=90.0, range_hi=110.0, range_q=3)
    ctx = mkd(p, [(100.0, 100.3, 99.7, 100.0)] * 40, row)
    i = at(ctx, "09:50")
    sd = ctx.sides_map[1]

    def ok(entry, htf_=True, t1=None, p_=p, ctx_=ctx, sd_=sd):
        o = dict(order(entry=entry, t1=entry + 4.0 if t1 is None else t1), htf=True)     # the intraday 15m / 60m tag is set either way: it must not matter
        ctx_.conf = Conf(["D"] if htf_ else ["15m", "4h"])                              # review fix: a live DAILY array at the entry, not the intraday tag
        return bh2e.order_ok(ctx_, sd_, o, "AM", i, p_), o
    assert ok(102.0)[0] is None and "pd_subrange" in ok(102.0)[1]["lv_tags"].split("|")           # quadrant 3, lower half, at a daily array
    assert ok(107.0)[0] is None                                                                      # quadrant 4, lower half
    assert ok(103.0)[0] == "x_bh2_pd_two_level"                                                      # quadrant 3, upper half
    assert ok(102.0, htf_=False)[0] == "x_bh2_pd_two_level"                                          # no DAILY array (a 4h / 15m one does not count)
    ctx.conf = None
    assert bh2e.order_ok(ctx, sd, dict(order(entry=102.0, t1=106.0), htf=True), "AM", i, p) == "x_bh2_pd_two_level"   # no Confluence arrays: no exception
    assert E7.at_daily_array(ctx, sd, 102.0, i) is False
    ctx.conf = Conf(["W"])
    assert E7.at_daily_array(ctx, sd, 102.0, i) is True
    assert ok(102.0, t1=101.0)[0] == "x_bh2_pd_two_level"                                            # no premium target left
    assert ok(98.0)[0] is None                                                                       # below the EQ: the gate never blocks it
    assert ok(102.0, p_=p7(pd_two_level=True))[0] == "x_bh2_pd_two_level"                            # switch off: the built gate
    assert E7.order_ok(ctx, sd, dict(order(entry=109.0, t1=113.0), htf=True), "AM", i, p) == "x_bh7_pd_top"       # the top of the overall range
    assert E7.order_ok(ctx, sd, dict(order(entry=107.0, t1=113.0), htf=True), "AM", i, p) is None
    assert E7.order_ok(ctx, sd, dict(order(entry=109.0, t1=113.0), htf=True), "AM", i, p7(pd_subrange=True, pd_top_skip=False)) is None
    assert DW.order_ok(ctx, sd, dict(order(entry=109.0, t1=113.0), htf=True), "AM", i, p7(pd_subrange=True)) == "x_bh7_pd_top"
    # the short mirror: the entry 98.0 is quadrant 3 in side terms (lower half), 91.0 is the bottom of the range's upper... top-skip
    ds = ctx.sides_map[-1]
    sh_row = BR(combo=-1, eq20_body=100.0, range_lo=90.0, range_hi=110.0)
    c2 = mkd(p, [(100.0, 100.3, 99.7, 100.0)] * 40, sh_row)
    c2.conf = Conf(["D"])
    o = dict(order(entry=ds.x(98.0), t1=ds.x(90.0)), htf=True)
    assert bh2e.order_ok(c2, ds, o, "AM", i, p) is None
    assert E7.order_ok(c2, ds, dict(order(entry=ds.x(91.0), t1=ds.x(85.0)), htf=True), "AM", i, p) == "x_bh7_pd_top"
    assert E7.side_frac(ds, 98.0, 90.0, 110.0) == pytest.approx(0.6) and E7.side_frac(sd, 98.0, 90.0, 110.0) == pytest.approx(0.4)
    assert E7.side_frac(sd, 98.0, 100.0, 100.0) != E7.side_frac(sd, 98.0, 100.0, 100.0)


# --- B20-15m-williams-r-entry -----------------------------------------------------------------------------------------------------------

def test_wr15_extreme_tag():
    """The 15m Williams %R(10) at the order is the lowest of its last wr_lookback readings after a steady decline; a bounce is not."""
    p = p7(wr15_tag=True)
    down = [(100.0 - 0.1 * k, 100.05 - 0.1 * k, 99.9 - 0.1 * k, 99.95 - 0.1 * k) for k in range(48)]
    ctx = mkd(p, down, BR(combo=0))
    i = at(ctx, "12:20")
    sl = ctx.sides_map[1]
    assert E7.wr15_extreme(ctx, sl, i, 20) is True
    o = dict(order())
    E7.order_ok(ctx, sl, o, "AM", i, p)
    assert "wr15_extreme" in o["lv_tags"].split("|")
    bounce = down[:30] + [(97.0 + 0.2 * k, 97.3 + 0.2 * k, 96.9 + 0.2 * k, 97.25 + 0.2 * k) for k in range(18)]
    c2 = mkd(p, bounce, BR(combo=0))
    assert E7.wr15_extreme(c2, c2.sides_map[1], i, 20) is False
    o2 = dict(order())
    E7.order_ok(c2, c2.sides_map[1], o2, "AM", i, p)
    assert "wr15" not in o2["lv_tags"]
    assert E7.wr15_extreme(ctx, ctx.sides_map[-1], i, 20) is False                       # for a short the same decline is the %R high of its mirrored prices
    up = mkd(p, [(100.0 + 0.1 * k, 100.1 + 0.1 * k, 99.95 + 0.1 * k, 100.05 + 0.1 * k) for k in range(48)], BR(combo=0))
    assert E7.wr15_extreme(up, up.sides_map[-1], i, 20) is True                        # a steady rally: the mirrored %R of a short is at its extreme
    off = dict(order())
    E7.order_ok(ctx, sl, off, "AM", i, p7())
    assert "wr15" not in off["lv_tags"]


# --- T13-po3-breaker-regime (the reaction-based regime, htf_bias "breaker") ---------------------------------------------------------------

def test_breaker_regime_sets_the_side_and_the_judas_tag():
    p = p7()
    p = Params(**BASE, htf_bias="breaker", bias_neutral="both")
    rally = [(100.0, 100.0, 99.9, 100.0)] * 12 + [(100.0, 101.2, 99.95, 101.0)] * 20 + [(100.8, 100.9, 100.4, 100.5)] * 100
    ctx = mkd(p, rally, BR(brk_react=-1), start="01:00")
    i = at(ctx, "09:50")
    assert BD.want_at(ctx, p, "AM", i) == -1                                          # the regime is the want
    o = dict(order())
    E7.order_ok(ctx, ctx.sides_map[-1], o, "AM", i, p)
    assert "po3_judas" in o["lv_tags"].split("|")                                       # London rallied above the midnight open against the bearish regime
    drop = [(100.0, 100.0, 99.0, 99.2)] * 20
    c2 = mkd(p, [(100.0, 100.0, 99.9, 100.0)] * 12 + drop + [(99.2, 99.4, 99.1, 99.3)] * 100, BR(brk_react=-1), start="01:00")
    o2 = dict(order())
    E7.order_ok(c2, c2.sides_map[-1], o2, "AM", i, p)
    assert "po3_judas" not in o2["lv_tags"]                                              # a London drop is not a Judas against a bearish regime
    c3 = mkd(p, [(100.0, 100.0, 99.9, 100.0)] * 12 + drop + [(99.2, 99.4, 99.1, 99.3)] * 100, BR(brk_react=1), start="01:00")
    o3 = dict(order())
    E7.order_ok(c3, c3.sides_map[1], o3, "AM", i, p)
    assert "po3_judas" in o3["lv_tags"].split("|")                                       # the bullish regime: a London drop below the open is the Judas
    assert BD.want_at(c3, p, "AM", i) == 1
    o4 = dict(order())
    E7.order_ok(ctx, ctx.sides_map[-1], o4, "AM", at(ctx, "04:00"), p)
    assert "po3_judas" not in o4["lv_tags"]                                              # London is not complete before 05:00
    assert E7.po3_judas(ctx, 0, i) is False


# --- new-ipda-true-day ------------------------------------------------------------------------------------------------------------------------

def test_late_obj_k():
    """A 10:05 entry with rungs at 0.3 and 0.8 ADR5 keeps only the first with 0.5."""
    p = p7(late_obj_k=0.5)
    ctx = mkd(p, [(100.0, 100.3, 99.7, 100.0)] * 60, BR(combo=0))
    i = at(ctx, "10:05")
    a5 = bh5e._adr5(ctx, p)
    assert a5 and a5 > 0
    lv = [(100.0 + 0.3 * a5, "array"), (100.0 + 0.8 * a5, "array")]
    assert E7.targets_post(ctx, ctx.sides_map[1], i, p, 100.0, lv) == [lv[0]]
    assert E7.targets_post(ctx, ctx.sides_map[1], i, p7(late_obj_k=1.0), 100.0, lv) == lv
    assert E7.targets_post(ctx, ctx.sides_map[1], at(ctx, "09:25"), p, 100.0, lv) == lv                  # only entries after the NY open
    far = [(100.0 + 0.9 * a5, "array"), (100.0 + 1.5 * a5, "array")]
    assert E7.targets_post(ctx, ctx.sides_map[1], i, p, 100.0, far) == [far[0]]                          # the nearest rung is always kept
    assert E7.targets_post(ctx, ctx.sides_map[1], i, p, 100.0, []) == []
    assert E7.targets_on(p) and not E7.targets_on(p7())


def test_cc_daytrade_preset():
    p = p7(cc_daytrade=True)
    q = E7.day_params(p, set())
    assert q.pm == (0, 0) and q.am_exit == 720
    f = E7.day_params(p, {"fomc"})
    assert f.pm == (840, 900) and f.am_exit == 720
    off = p7()
    assert E7.day_params(off, {"fomc"}) is off
    assert off.pm == (810, 950)


# --- the table with every new column -----------------------------------------------------------------------------------------------------

TABLE_ALL = dict(htf_bias="h1_sponsor", pd_subrange=True, weekly_flip_follow=True, array_lost_flip=True)
NEW_COLS = ("range_q", "range_lo", "range_hi", "flip_turn", "h1_sponsor", "array_lost", "array_lost_tgt")


@pytest.fixture(scope="module")
def walk():
    from test_caption_gap_bh1c import fut_walk
    return fut_walk("2024-09-02", "2026-03-27", seed=7, vol=0.9)


def _build(p, df):
    return htf.table(df, p.es_pt, vi=p.vi_arrays, flip_triggers=p.flip_triggers, **B.table_kw(p))


def test_table_builds_every_column_and_default_is_unchanged(walk):
    BH2.HITS.clear()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        t = _build(Params(**FUT, htf_bias="combo", pd_subrange=True, weekly_flip_follow=True, array_lost_flip=True), walk)
        th = _build(Params(**FUT, htf_bias="h1_sponsor"), walk)
        t0 = _build(Params(**FUT, htf_bias="combo"), walk)
        t1 = _build(Params(**FUT, htf_bias="breaker"), walk)
    for c in ("range_q", "range_lo", "range_hi", "flip_turn", "array_lost", "array_lost_tgt"):
        assert c in t.columns and c not in t0.columns, c
    assert "h1_sponsor" in th.columns and "h1_sponsor" not in t0.columns
    base_cols = list(t0.columns)
    pd.testing.assert_frame_equal(t0[base_cols], t[base_cols])                       # a column switch changes no existing column
    pd.testing.assert_frame_equal(t0[base_cols], th[base_cols])
    assert t.range_q.isin([0, 1, 2, 3, 4]).all() and t.flip_turn.isin([-1, 0, 1]).all() and th.h1_sponsor.isin([-1, 0, 1]).all() and t.array_lost.isin([-1, 0, 1]).all()
    assert (t.range_lo.dropna() <= t.range_hi.dropna()).all()
    assert t.flip_turn.abs().sum() > 0 and th.h1_sponsor.abs().sum() > 0 and t.array_lost.abs().sum() > 0, "the synthetic walk shows no flip turn / sponsorship / lost array"
    wd = pd.Series([pd.Timestamp(x).weekday() for x in th.index], index=th.index)
    assert (th.h1_sponsor[wd < 2] == 0).all()                                         # Wed-Fri only
    assert (t.array_lost_tgt[t.array_lost == 0].isna()).all()
    assert t1.brk_react.isin([-1, 0, 1]).all() and t1.brk_react.abs().sum() > 0 and "brk_regime" not in t1.columns
    assert all(BH2.HITS["sw_" + k] > 0 for k in ("pd_subrange", "weekly_flip_follow", "h1_sponsor", "array_lost_flip", "htf_bias_breaker"))


def test_table_rows_do_not_look_ahead():
    from test_caption_gap_bh1c import fut_walk
    from test_caption_gap_bh1f import _same
    df = fut_walk("2025-03-03", "2026-03-27", seed=11, vol=0.9)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        p = Params(**FUT, **TABLE_ALL, true_day="session")
        pb = Params(**FUT, htf_bias="breaker")
        full, fb = _build(p, df), _build(pb, df)
        cols = list(NEW_COLS) + ["draw", "pd", "flip"]
        dates = list(full.index)
        for pos in (len(dates) - 3, len(dates) // 2 + 4):
            d = dates[pos]
            cut = pd.Timestamp(d, tz=B.NY) + pd.Timedelta(hours=9, minutes=30)
            part, pbt = _build(p, df[df.index < cut]), _build(pb, df[df.index < cut])
            assert d in part.index
            for x in dates[:pos + 1]:
                a, b = full.loc[x, cols], part.loc[x, cols]
                bad = [c for c in cols if not _same(a[c], b[c])]
                assert not bad, (str(x), bad, [(a[c], b[c]) for c in bad])
                assert fb.loc[x, "brk_react"] == pbt.loc[x, "brk_react"], str(x)


def _raw_pair(df, roll):
    """(raw frame, adj Series, meta) for a synthetic series with a +10 roll at `roll`: engine = raw + adj."""
    adj = pd.Series(np.where(df.index < roll, 10.0, 0.0), index=df.index)
    raw = df.copy()
    for k in ("open", "high", "low", "close"):
        raw[k] = df[k] - adj
    return raw, adj, pd.DataFrame({"adj": adj})


def test_raw_table_rows_do_not_look_ahead():
    """review fix (other#5): the raw-series table (htf_series 'raw' + the raw monthly arrays) row by row: a table built on the data cut at a session's open equals the full table's rows up to it."""
    from test_caption_gap_bh1c import fut_walk
    from test_caption_gap_bh1f import _same
    df = fut_walk("2025-03-03", "2026-03-27", seed=11, vol=0.9)
    raw, adj, _ = _raw_pair(df, pd.Timestamp("2025-11-03", tz=B.NY))
    p = Params(**FUT, htf_bias="combo", htf_series="raw", htf_monthly=True, htf_monthly_series="raw")

    def build(d_, r_):
        return htf.table(d_, p.es_pt, vi=p.vi_arrays, flip_triggers=p.flip_triggers, **B.table_kw(p, r_, adj))
    BH2.HITS.clear()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        full = build(df, raw)
        assert BH2.HITS["sw_htf_series_raw"] > 0 and "adj_map" in full
        cols = [c for c in ("px", "draw_up", "draw_dn", "adj_map", "draw", "pd", "flip") if c in full]
        dates = list(full.index)
        for pos in (len(dates) - 3, len(dates) // 2 + 4):
            d = dates[pos]
            cut = pd.Timestamp(d, tz=B.NY) + pd.Timedelta(hours=9, minutes=30)
            part = build(df[df.index < cut], raw[raw.index < cut])
            assert d in part.index
            for x in dates[:pos + 1]:
                a, b = full.loc[x, cols], part.loc[x, cols]
                bad = [c for c in cols if not _same(a[c], b[c])]
                assert not bad, (str(x), bad, [(a[c], b[c]) for c in bad])


@pytest.mark.parametrize("name", ["raw", "monthly_raw"])
def test_look_ahead_synthetic_raw_series(name, monkeypatch):
    """review fix (other#5): the engine with the raw-series switches, full vs truncated runs (the raw frame is clipped to the engine frame's span, so a truncated run never sees raw bars after its cut)."""
    x, y = _walks()
    raw, adj, meta = _raw_pair(x, x.index[len(x) // 2].normalize())
    monkeypatch.setattr(B, "load_raw", lambda sym, minutes: raw)
    kw = dict(htf_series="raw") if name == "raw" else dict(htf_monthly=True, htf_monthly_series="raw")
    p = Params(**dict(LA, htf_bias="combo", bias_neutral="both", **kw))
    BH2.HITS.clear()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        full = B.run(x, 5, "ES", p, partner=y, intermarket=IM, meta=meta)
    assert len(full) >= 1, f"{name}: no trade in the synthetic window"
    if name == "raw":
        assert BH2.HITS["sw_htf_series_raw"] > 0
    _no_look_ahead(x, 5, "ES", p, COLS, every=max(1, len(full) // 2), meta=meta, partner=y, intermarket=IM, exits=True, min_trades=1)


def test_raw_series_clips_to_the_engine_span_and_contract_falls_back(monkeypatch):
    from test_caption_gap_bh1c import fut_walk
    df = fut_walk("2026-02-02", "2026-03-06", seed=2, vol=0.7)
    long_ = fut_walk("2025-06-02", "2026-06-05", seed=2, vol=0.7)
    raw, adj, meta = _raw_pair(long_, pd.Timestamp("2026-02-20", tz=B.NY))
    monkeypatch.setattr(B, "load_raw", lambda sym, minutes: raw)
    r, a = B.raw_series(Params(**FUT, htf_series="raw"), "ES", 5, meta, df)
    assert r.index[0] >= df.index[0] and r.index[-1] <= df.index[-1] and len(r) < len(raw) / 3
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        q = B.series_fallback(Params(**FUT, htf_series="contract"), "SPX", None)
    assert q.htf_series == "adjusted" and any("adjusted frame" in str(m.message) for m in w)
    assert B.series_fallback(Params(**FUT, htf_series="contract"), "ES", meta).htf_series == "contract"      # databento data keeps the NotImplementedError of htf.table
    assert B.series_fallback(Params(**FUT), "SPX", None).htf_series == "adjusted"


# --- the engine on synthetic and ES windows -------------------------------------------------------------------------------------------------

LA_SETS = {   # name -> switches (the draw lock stays on); each leaves trades on its windows
    "gates": dict(htf_bias="combo", bias_neutral="both", weekly_flip_follow=True, pd_two_level=True, pd_subrange=True, wr15_tag=True, london_dir_gate=True, london_dir_tag=True),
    "sides": dict(htf_bias="combo", bias_neutral="both", array_lost_flip=True, london_breaker_bias=True, london_confirm="half", late_obj_k=0.5, cc_daytrade=True),
    "breaker": dict(htf_bias="breaker", bias_neutral="both", true_day="ipda", london_confirm="block"),
    "sponsor": dict(htf_bias="h1_sponsor", bias_neutral="both"),
}
LA_HITS = {"gates": ("pd_subrange", "weekly_flip_follow", "wr15_tag", "london_dir_gate", "london_dir_tag"), "sides": ("array_lost_flip", "london_breaker_bias", "late_obj_k", "cc_daytrade"),
           "breaker": ("true_day", "htf_bias_breaker"), "sponsor": ("h1_sponsor",)}


@pytest.mark.parametrize("name", list(LA_SETS))
def test_look_ahead_synthetic_bh7(name):
    x, y = _walks()
    p = Params(**dict(LA, **LA_SETS[name]))
    BH2.HITS.clear()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        full = B.run(x, 5, "ES", p, partner=y, intermarket=IM)
    assert len(full) >= 1, f"{name}: the switches leave no trade in the synthetic window"
    for k in LA_HITS[name]:
        assert BH2.HITS["sw_" + k] > 0, f"{name}: {k} never acted in the full run"
    _no_look_ahead(x, 5, "ES", p, COLS, every=max(1, len(full) // 2), partner=y, intermarket=IM, exits=True, min_trades=1)


ES_WIN = {"gates": ("2023-03-06", "2023-03-24"), "sides": ("2023-03-06", "2023-03-24"), "breaker": ("2023-03-06", "2023-03-24"), "sponsor": ("2023-03-06", "2023-03-24")}


@pytest.mark.skipif(not ES, reason="no ES data")
@pytest.mark.parametrize("name", list(ES_WIN))
def test_look_ahead_es_bh7(name):
    es = B.load("ES", 5, source="databento")
    a, b = ES_WIN[name]
    df = es[(es.index >= pd.Timestamp(a, tz=B.NY)) & (es.index < pd.Timestamp(b, tz=B.NY))]
    if not len(df):
        pytest.skip("the ES file does not cover the window")
    meta = B.load_meta("ES", 5)
    p = Params(**dict(LA, **LA_SETS[name]))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        n = len(B.run(df, 5, "ES", p, meta=meta, intermarket=IM))
    if n < 1:
        pytest.skip("no trades in the window with this data file")
    _no_look_ahead(df, 5, "ES", p, COLS, every=max(1, n // 2), meta=meta, intermarket=IM, exits=True, min_trades=1)


def test_look_ahead_hand_made_day():
    from test_caption_gap_bh4c import la_day4
    for kw, bias in ((dict(pd_two_level=True, pd_subrange=True), BR(combo=1, eq20_body=1000.0, range_lo=90.0, range_hi=108.0)), (dict(array_lost_flip=True), BR(combo=1, array_lost=-1, array_lost_tgt=130.0)),
                     (dict(london_breaker_bias=True, wr15_tag=True), BR(combo=1)), (dict(weekly_flip_follow=True), BR(combo=1, flip=1, flip_turn=1)), (dict(late_obj_k=0.5), BR(combo=1))):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            la_day4(p7(**kw), bias=bias, min_trades=1)


def test_london_poison_is_causal():
    """The London confirmation reads only bars <= i: poisoning every later bar leaves the answer unchanged."""
    p = p7(london_confirm="block")
    junk = [(500.0, 600.0, 1.0, 550.0)] * 8
    a = mkd(p, CONFIRMED[:115] + junk, BR(combo=-1), hist=outside_hist(), start="02:00")
    b = mkd(p, CONFIRMED + [(100.2, 100.3, 100.1, 100.2)] * 8, BR(combo=-1), hist=outside_hist(), start="02:00")
    i = at(a, "09:30")
    assert E7.london_state(a, p, -1, "AM", i) == E7.london_state(b, p, -1, "AM", i) == "ok"
    assert E7.london_dir(a, i) == E7.london_dir(b, i)


# --- every new switch is LIVE in an executed run -----------------------------------------------------------------------------------------------

SW_OF = {"weekly_flip_follow": "weekly_flip_follow", "pd_subrange": "pd_subrange", "wr15_tag": "wr15_tag", "array_lost_flip": "array_lost_flip", "london_breaker_bias": "london_breaker_bias",
         "london_confirm": "london_confirm", "true_day": "true_day", "late_obj_k": "late_obj_k", "cc_daytrade": "cc_daytrade", "london_dir_gate": "london_dir_gate", "london_dir_tag": "london_dir_tag",
         "htf_series": "htf_series_raw", "htf_monthly_series": "htf_monthly_series_raw"}


def test_every_switch_is_covered(walk):
    """Execution, not names: a `sw_<switch>` count in bh2.HITS (written by bh7.sw / bh7e.sw where the switch acts) must exist for every rule switch after the table with every table switch, the
    hand-made days, the raw-series tables and the per-path cases."""
    from test_caption_gap_bh7 import test_htf_series_raw_maps_by_adj, test_true_day_in_the_table_changes_the_daily_candle, test_h1_sponsorship_column
    BH2.HITS.clear()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        _build(Params(**FUT, **TABLE_ALL, true_day="ipda"), walk)
        _build(Params(**FUT, htf_bias="breaker"), walk)
        test_true_day_in_the_table_changes_the_daily_candle()
        test_htf_series_raw_maps_by_adj()
        test_london_confirm()
        test_london_dir_gate()
        test_london_breaker_sets_am_side()
        test_array_lost_next_day_short()
        test_long_above_eq_in_subrange_discount()
        test_wr15_extreme_tag()
        test_late_obj_k()
        test_cc_daytrade_preset()
        test_breaker_regime_sets_the_side_and_the_judas_tag()
        import pytest as _pt
        mp = _pt.MonkeyPatch()
        try:
            test_post_flip_4h_array_short(mp)
        finally:
            mp.undo()
        # htf_monthly_series 'raw' through the table (the monthly arrays on the raw series)
        from test_caption_gap_bh1c import fut_walk
        df = fut_walk("2025-09-01", "2026-03-27", seed=9, vol=1.2)
        roll = pd.Timestamp("2026-01-05", tz=B.NY)
        adj = pd.Series(np.where(df.index < roll, 10.0, 0.0), index=df.index)
        raw = df.copy()
        for k in ("open", "high", "low", "close"):
            raw[k] = df[k] - adj
        pm = Params(**FUT, htf_bias="combo", htf_monthly=True, htf_monthly_series="raw")
        htf.table(df, pm.es_pt, vi=pm.vi_arrays, flip_triggers=pm.flip_triggers, **B.table_kw(pm, raw, adj))
    live = {k[3:] for k in BH2.HITS if k.startswith("sw_")}
    missing = sorted(v for k, v in SW_OF.items() if v not in live)
    assert not missing, f"never live in an executed run: {missing}"
    assert "h1_sponsor" in live and "htf_bias_breaker" in live
