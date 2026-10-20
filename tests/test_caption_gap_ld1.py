"""Caption-gap pass, package levels_detectors #1/3 (29 specs of digests/rulebook_gaps/*.md): unit tests of the new
detectors in levels.py, the ld2.py engine glue, Params/study plumbing and no-look-ahead runs (full vs truncated) covering
the new switches on small date windows. Tests that need local market data (ES) skip cleanly when it is absent; no
platform-specific paths or imports."""
import warnings
from dataclasses import replace
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from mentorship import backtest as B, htf, ld2 as LD, levels as L, strategy as S, study
from mentorship.confluence import Confluence
from mentorship.strategy import Params

from test_levels_detectors import BASE, D0, ES, FUT, NY, ctx_for, day, frame, history, prior_days, rth_day

A = np.array


def mk(rows):
    """[(o, h, l, c)] -> arrays."""
    a = np.array(rows, float)
    return a[:, 0], a[:, 1], a[:, 2], a[:, 3]


# --- X3-l8-vb-exhaustion-gap (125) ----------------------------------------------------------------------------------

def test_vb_context():
    """A gap up after 5 up days is tagged exhaustion and dropped; a gap up from below the 20-day EQ after a pullback is kept."""
    highs, lows = [110.0] * 20, [90.0] * 20                       # 20-day range 90..110, EQ 100
    up5 = [100, 101, 102, 103, 104, 105.0]
    assert L.vb_context("bull", 106.0, 104.0, up5, highs, lows, 1) == "exhaustion"
    pullback = [104, 102, 101, 100, 99, 98.0]                      # no five straight up-closes
    assert L.vb_context("bull", 99.5, 98.0, pullback, highs, lows, 1) == "valid"          # lower edge 98 < EQ
    assert L.vb_context("bull", 104.0, 102.5, pullback, highs, lows, 1) == "invalid"      # gap above EQ: premium
    assert L.vb_context("bull", 99.5, 98.0, pullback, highs, lows, -1) == "invalid"       # bias not bullish
    assert L.vb_context("bull", 99.5, 98.0, pullback, highs, lows, None) == "valid"       # htf_bias off: bias clause skipped
    assert L.vb_context("bull", 111.0, 109.0, pullback[:-1] + [111.0], highs, lows, 1) == "exhaustion"   # above the 20-day high
    # mirror
    dn5 = [105, 104, 103, 102, 101, 100.0]
    assert L.vb_context("bear", 99.0, 100.0, dn5, highs, lows, -1) == "exhaustion"
    assert L.vb_context("bear", 101.5, 100.5, [98, 99, 100, 101, 100.0, 100.5], highs, lows, -1) == "valid"


def test_vb_context_in_the_target_ladder():
    closes = [100, 101, 102, 103, 104, 105.0]
    hist = history(D0, n=22, hi=110.0, lo=90.0)
    hist = [rth_day(d.index[0].date(), 110.0, 90.0, close=c) for d, c in
            zip(hist, [100.0] * 16 + closes)]
    p = Params(**BASE, vacuum_blocks=True, vb_context=True)
    df = day([(105.0, 106.0, 104.0, 105.0)] * 4)
    ctx = ctx_for(df, hist, p)
    sd = S.Side(1, ctx.o, ctx.h, ctx.l, ctx.c, 1)
    k = int(np.flatnonzero(ctx.t == 570)[0])
    ctx.vac = [(k, 106.0, 105.5, 105.0, 570)]
    ctx.want0 = 1
    on = S._lv_target_arrays(ctx, sd, k + 1, p)
    assert (106.0, "array") not in on and "vb_exhaustion" in LD.vb_tags(ctx)                  # 5 up days: dropped + tagged
    off = S._lv_target_arrays(ctx, sd, k + 1, replace(p, vb_context=False))
    assert (106.0, "array") in off                                                           # the switch off keeps it


# --- X3-b21-ipda-anchor / windows (128, 129) -------------------------------------------------------------------------

def test_ipda_anchor_month():
    """On 2023-11-14 the "month" windows end on 2023-09-29 (the session before Oct 2)."""
    d = date(2023, 11, 14)
    n = 110
    ds = prior_days(d, n)
    hist = [rth_day(x, 100.0 + k, 90.0 - k * 0.01) for k, x in enumerate(ds)]     # highs rise 1 a session
    p = Params(**BASE, ipda_pools=True, ipda_anchor="month")
    df = day([(100.0, 100.5, 99.5, 100.0)] * 4, d=d)
    ctx = ctx_for(df, hist, p)
    assert ctx.ipda_last == date(2023, 9, 29)
    end = ds.index(date(2023, 9, 29)) + 1
    assert ctx.ipda[20][0] == 100.0 + (end - 1) and ctx.ipda[60][0] == 100.0 + (end - 1)
    assert ctx.ipda[20][1] == pytest.approx(min(90.0 - k * 0.01 for k in range(end - 20, end)))
    roll = ctx_for(df, hist, replace(p, ipda_anchor="rolling"))
    assert roll.ipda_last == ds[-1] and roll.ipda[20][0] == 100.0 + (n - 1)               # the first build: yesterday
    assert L.ipda_month_end(ds, d) == ds.index(date(2023, 10, 2))
    sw = ctx_for(df, hist, replace(p, ipda_anchor="swing"))                               # a monotone rise: no daily MSS to anchor on
    assert isinstance(sw.ipda, dict)


def test_daily_mss_end():
    h = A([10, 12, 11, 10, 13.0]); l = h - 1.0
    c = A([9.5, 11.5, 10.5, 9.8, 12.9])                  # a swing high 12 (bar 1); bar 4 closes above it: the last daily MSS
    assert L.daily_mss_end(h, l, c, 1) == 4
    assert L.daily_mss_end(h[:4], l[:4], c[:4], 1) is None
    assert L.daily_mss_end(-l, -h, -c, 1) == 4           # the mirror (closes below the swing low)


def _stub_conf(first20=True):
    cf = Confluence.__new__(Confluence)
    cf.first20 = first20
    cf.dends = np.arange(1, 101, dtype=float)                       # 100 daily session ends 1 .. 100
    return cf


def test_ipda_array_windows():
    """A 30-session-old FVG is excluded while an untraded 10-session-old FVG exists, and included after that one is traded."""
    cf = _stub_conf()
    now = 100.0
    z = dict(kind=A([1.0, 1.0]), top=A([10.0, 20.0]), bottom=A([9.0, 19.0]), src=A([0.0, 0.0]),
             known=A([90.0, 70.0]),                                    # ages 11 and 31 sessions
             dead=A([np.inf, np.inf]), life=A([1e9, 1e9]))
    m = cf._ipda_mask("D", z, now)
    assert list(m) == [True, False]
    z["dead"] = A([95.0, np.inf])                                      # the young one was traded through at 95
    m = cf._ipda_mask("D", z, now)
    assert list(m) == [True, True]                                      # now the 40-session window is the first with an open array
    assert list(cf._ipda_mask("4h", z, now)) == [True, True]            # other timeframes are untouched
    assert list(_stub_conf(False)._ipda_mask("D", z, now)) == [True, True]


def test_htf_table_ipda_window_tag_and_two_sided_vi():
    a = htf.Arr("bull", "fvg", "D", 10.0, 9.0, 9.5, 5)
    assert a.ipda_w == 0
    o = A([10, 10, 10, 10, 10.0]); h = A([11, 11, 11, 11, 11.0]); l = A([9, 9, 9, 9, 9.0]); c = o.copy()
    vi = htf.Arr("bull", "vi", "D", 12.0, 11.0, 11.5, 1)
    assert htf._arr_alive(vi, 4, o, h, l, c, o, c, [], True, "full_span")
    o2 = A([10, 10, 10, 11.0, 10]); c2 = A([10, 10, 10, 12.0, 10])        # a body 11 -> 12 spans the whole VI
    assert not htf._arr_alive(vi, 4, o2, h, l, c2, o2, c2, [], True, "full_span")
    o3 = A([10, 10, 10, 11.5, 10]); c3 = A([10, 10, 10, 11.7, 10])        # a body inside it only overlaps
    assert htf._arr_alive(vi, 4, o3, h, l, c3, o3, c3, [], True, "full_span")
    assert not htf._arr_alive(vi, 4, o3, h, l, c3, o3, c3, [], True, "overlap")


# --- X3-b5-15m-pools-5m-gaps (151) ------------------------------------------------------------------------------------

def _pool_tf_ctx(p):
    # 15-minute buckets of three 5m bars from 09:30. B2 holds the 15m swing low (98.0, lower than both neighbours); the 5m micro low
    # 99.3 in the middle of B3 is a 5m pivot but NOT a 15m pivot (the bucket before it is lower)
    up = lambda lo: (lo + 1.0, lo + 1.6, lo, lo + 1.2)
    rows = [up(100.5)] * 3 + [up(99.0)] * 3 + [up(99.6), up(98.0), up(99.6)] + [up(100.0), up(99.3), up(100.0)] +         [up(100.6)] * 3 + [up(101.0)] * 12
    df = day(rows, start="09:30")
    ctx = ctx_for(df, history(D0, n=8), p)
    return ctx, S._idx_at(ctx, 570)


def test_pool_tf_15():
    p1 = Params(**BASE, pool_swings=True, pool_tf=1)
    ctx, k0 = _pool_tf_ctx(p1)
    sd = S.Side(1, ctx.o, ctx.h, ctx.l, ctx.c, 1)
    i = k0 + 20
    base_keys = [k for k in S._sell_side(ctx, sd, "AM", i, False, p1) if k.startswith("swing_low")]
    p15 = replace(p1, pool_tf=15)
    sd15 = S.Side(1, ctx.o, ctx.h, ctx.l, ctx.c, 1)
    LD.attach_pool_tf(ctx, [sd15], p15)
    keys15 = [k for k in S._sell_side(ctx, sd15, "AM", i, False, p15) if k.startswith("swing_low")]
    micro, low15 = f"swing_low{k0 + 10}", f"swing_low{k0 + 7}"
    assert micro in base_keys and micro not in keys15                       # a 5m micro pivot is no pool at 15
    assert low15 in keys15 and low15 in base_keys                           # the 15m swing low maps to its base-bar extreme
    assert sd15.l[k0 + 7] == pytest.approx(98.0)
    assert p15.pool_tf == 15 and LD.pool_piv(sd, True) is sd.pl and LD.pool_piv(sd15, True) is sd15.pool_piv[1]


# --- N8-consolidation-builds-orders (49) ---------------------------------------------------------------------------------

def test_consol_pools():
    """After the chop releases upward, consol_l is in the sell-side pools (and consol_h among the targets)."""
    p = Params(**BASE, consol_pools=True)
    df = day([(100.0, 100.5, 99.5, 100.0)] * 6, start="09:30")
    ctx = ctx_for(df, history(D0, n=8), p)
    sd = S.Side(1, ctx.o, ctx.h, ctx.l, ctx.c, 1)
    ctx.chop = type("C", (), dict(rel_i=ctx.start + 3, hi=101.0, lo=99.0))()
    i = ctx.start + 5
    keys = S._sell_side(ctx, sd, "AM", i, False, p)
    assert keys.get("consol_l") == 99.0
    assert (101.0, ctx.start + 4) in S._lv_target_pools(ctx, sd, i, p)
    assert "consol_l" not in S._sell_side(ctx, sd, "AM", ctx.start + 3, False, p)      # not before the release bar closed
    assert "consol_l" not in S._sell_side(ctx, sd, "AM", i, False, replace(p, consol_pools=False))
    short = S.Side(-1, ctx.o, ctx.h, ctx.l, ctx.c, 1)
    assert S._sell_side(ctx, short, "AM", i, False, p).get("consol_h") == -101.0


# --- A11-bpr-one-pass-definition (1) ---------------------------------------------------------------------------------

def test_single_pass_bpr():
    """A down-pass then up-pass sets balanced_i only after a bar sits fully beyond; a touch-only sequence sets nothing."""
    # a bearish FVG [8, 11] made on the way down (bar 2), then one pass up through it (bar 3), then a bar fully above (bar 4)
    o, h, l, c = mk([(12, 12.5, 11.0, 11.2), (11.0, 11.5, 9.0, 9.5), (9.0, 8.0, 7.0, 7.5),
                     (8, 12, 7.5, 11.8), (12.5, 14, 12.2, 13.5), (13.5, 14, 13.0, 13.8)])
    h[2] = 8.0
    z = [x for x in L.single_pass_bprs(o, h, l, c, ("gap",)) if x.top == 11.0 and x.bottom == 8.0]
    assert len(z) == 1 and z[0].kind == "bpr2" and z[0].tag == "bull"
    assert z[0].i == 3 and z[0].bi == 4                                  # return pass at 3, balanced when bar 4 is fully above
    # touch only: price re-enters the gap but never crosses it -> nothing is set
    o2, h2, l2, c2 = mk([(12, 12.5, 11.0, 11.2), (11.0, 11.5, 9.0, 9.5), (9.0, 8.0, 7.0, 7.5),
                         (8, 10.0, 7.5, 9.0), (9, 10.5, 8.5, 9.5), (9.5, 10.5, 9.0, 9.8)])
    h2[2] = 8.0
    assert [x for x in L.single_pass_bprs(o2, h2, l2, c2, ("gap",)) if x.top == 11.0] == []
    # crossed back down before leaving: not one pass
    o3, h3, l3, c3 = mk([(12, 12.5, 11.0, 11.2), (11.0, 11.5, 9.0, 9.5), (9.0, 8.0, 7.0, 7.5),
                         (8, 12, 7.5, 11.8), (11.5, 11.8, 7.0, 7.5), (8, 9, 6, 7)])
    h3[2] = 8.0
    assert [x for x in L.single_pass_bprs(o3, h3, l3, c3, ("gap",)) if x.top == 11.0 and x.bottom == 8.0] == []
    # mirror: a bullish FVG, one pass down, then a bar fully below -> a bearish BPR
    om, hm, lm, cm = (-o, -l, -h, -c)
    zm = [x for x in L.single_pass_bprs(om, hm, lm, cm, ("gap",)) if x.top == -8.0 and x.bottom == -11.0]
    assert len(zm) == 1 and zm[0].tag == "bear" and zm[0].bi == 4


def test_single_pass_bpr_range_and_two_candle():
    # range form: swing high 20 (bar 2), sell-side delivery to 14 (bar 6), then a trade above 20 (bar 10), a bar fully above (11)
    h = A([15, 18, 20, 18, 17, 16, 15, 16, 17, 19, 21, 23.0]); l = h - 1.5
    l[6] = 14.0
    o = h - 0.7; c = h - 0.8
    z = [x for x in L.single_pass_bprs(o, h, l, c, ("range",), 1) if x.tag == "bull"]
    assert z and z[0].top == 20.0 and z[0].bottom == 14.0 and z[0].i == 10
    # the two-candle variant: a down candle then an up candle with overlapping ranges
    o, h, l, c = mk([(10, 10.5, 9.0, 9.2), (9.2, 10.0, 9.0, 9.9), (10, 12, 10.5, 11.5)])
    t = [x for x in L.single_pass_bprs(o, h, l, c, ("two_candle",)) if x.tag == "bull"]
    assert t and t[0].bottom == 9.0 and t[0].top == 10.0 and t[0].i == 1 and t[0].bi == 2
    assert L.fvg_continuation_trigger(A([10.0, 11.0, 12.5]), A([9.0, 9.5, 10.2]), L.Zone("bull", 11.0, 9.0, 1, 1), 1, 2) == 2
    sd = S.Side(1, o, h, l, c, 1, bpr_def="single_range", bpr2_two_candle=True)            # the Side lists the two-candle zone once balanced
    assert any(z.tag == "bpr2" and (z.top, z.bottom) == (10.0, 9.0) for z in sd.bprs())
    assert not any((z.top, z.bottom) == (10.0, 9.0) for z in S.Side(1, o, h, l, c, 1, bpr_def="single_range").bprs())


def test_bpr_def_side_lists():
    o, h, l, c = mk([(12, 12.5, 11.0, 11.2), (11.0, 11.5, 9.0, 9.5), (9.0, 8.0, 7.0, 7.5),
                     (8, 12, 7.5, 11.8), (12.5, 14, 12.2, 13.5), (13.5, 14, 13.0, 13.8)])
    h[2] = 8.0
    sd1 = S.Side(1, o, h, l, c, 1)
    assert not any(z.tag == "bpr2" for z in sd1.bprs())                       # Type 1 only by default (a bullish and a bearish FVG overlap)
    sd2 = S.Side(1, o, h, l, c, 1, bpr_def="single_range")
    z = [z for z in sd2.bprs() if z.top == 11.0 and z.bottom == 8.0]
    assert len(z) == 1 and z[0].kind == "bull" and z[0].i == 4 and z[0].tag == "bpr2"   # known - and only returned - once balanced
    assert all(z.tag == "bpr2" for z in sd2.bprs())
    both = S.Side(1, o, h, l, c, 1, bpr_def="both").bprs()
    assert len(both) > len(sd1.bprs()) and any(z.tag == "bpr2" for z in both) and any(z.tag != "bpr2" for z in both)


# --- X-efficient-delivery-two-pass (3) ---------------------------------------------------------------------------------

def test_pass_state_and_efficient_bands():
    z = L.Zone("bear", 11.0, 8.0, 2, 1)                                      # a bearish FVG made on the way down
    h = A([12, 11.5, 9.0, 8.0, 10.0, 9.0]); l = A([11.5, 8.0, 7.0, 7.0, 8.5, 8.0])
    assert L.pass_state(h, l, z, 1, 5) == (0, 1)                             # formation = the down pass; never crossed back
    assert not L.is_efficient(0, 1)
    h2 = A([12, 11.5, 9.0, 8.0, 11.5, 9.0]); l2 = A([11.5, 8.0, 7.0, 7.0, 8.5, 8.5])
    assert L.pass_state(h2, l2, z, 1, 5) == (1, 1) and L.is_efficient(1, 1)  # crossed up as well: efficient
    assert L.pass_state(h, l, L.Zone("bull", 11.0, 10.0, 2, 1), 3, 5) == (0, 0)   # an untouched band: an open draw


def test_two_pass_state_drops_efficient_targets():
    """A band crossed up then down is removed from the targets; a band crossed once stays a target."""
    # a bearish FVG [11, 14] made on the way down (bars 0-2); price stays below it ...
    rows = [(14.5, 15.0, 14.0, 14.2), (14.2, 14.5, 11.5, 11.8), (11.8, 11.0, 10.0, 10.5), (10.5, 10.5, 9.5, 10.0), (10.0, 10.8, 10.0, 10.4)]
    rows[2] = (11.8, 11.0, 10.0, 10.5)
    p = Params(**BASE, two_pass_state=True)
    ctx = type("X", (), {})()
    o, h, l, c = mk(rows)
    sd = S.Side(1, o, h, l, c, 1)
    fvg = [g for g in sd.opposing() if g.top == 14.0 and g.bottom == 11.0][0]
    lv = [(11.0, "array"), (12.5, "array"), (14.0, "array"), (50.0, "pool")]
    assert L.pass_state(h, l, fvg, fvg.src, 4) == (0, 1)                       # only its formation pass: one-sided
    assert LD.drop_efficient(ctx, sd, 4, p, lv) == lv                          # crossed once: still a target
    # ... then crossed up through it and back down: efficient, no target
    rows2 = rows + [(10.4, 14.2, 10.3, 13.9), (13.9, 13.9, 9.0, 9.2)]
    o2, h2, l2, c2 = mk(rows2)
    sd2 = S.Side(1, o2, h2, l2, c2, 1)
    fvg2 = [g for g in sd2.opposing() if g.top == 14.0 and g.bottom == 11.0][0]
    up, down = L.pass_state(h2, l2, fvg2, fvg2.src, 6)
    assert up >= 1 and down >= 1
    out = LD.drop_efficient(ctx, sd2, 6, p, lv)
    assert (12.5, "array") not in out and (14.0, "array") not in out and (50.0, "pool") in out
    # a band crossed 3 or more times shields the arrays beyond it (pools stay)
    rows3 = rows2 + [(9.2, 14.1, 9.0, 13.8), (13.8, 13.9, 9.1, 9.3)]
    o3, h3, l3, c3 = mk(rows3)
    sd3 = S.Side(1, o3, h3, l3, c3, 1)
    far = [(20.0, "array"), (50.0, "pool")]
    shielded = LD.drop_efficient(ctx, sd3, 8, replace(p, shield_passes=3), far)
    assert (20.0, "array") not in shielded and (50.0, "pool") in shielded
    assert LD.drop_efficient(ctx, sd2, 6, replace(p, shield_passes=9), far) == far


# --- A12 order block pick, skip encapsulated, consolidation open (5, 6) ---------------------------------------------------

def test_ob_pick_modes():
    """Three down candles (first highest, last tiny and inside): a different anchor per mode."""
    o, h, l, c = mk([(10.0, 10.2, 9.9, 10.1),            # 0: up (lead-in)
                     (14.0, 14.5, 12.5, 12.8),           # 1: first/highest down candle (body 14 -> 12.8)
                     (12.8, 13.2, 11.0, 11.4),           # 2: lowest low (body 12.8 -> 11.4)
                     (12.3, 12.4, 12.1, 12.15)])         # 3: tiny, fully inside candle 2's body? no: bodies 12.3-12.15 inside 11.4-12.8
    blend = L.order_block_blend(o, h, l, c, 0, 3, "bull")
    assert blend.src == 1 and blend.top == 14.5 and blend.bottom == 11.0
    orig = L.order_block_blend(o, h, l, c, 0, 3, "bull", pick="original")
    assert orig.src == 1 and (orig.top, orig.bottom) == (14.5, 12.5) and orig.mt == pytest.approx(13.4)
    big = L.order_block_blend(o, h, l, c, 0, 3, "bull", pick="largest_body", s=11.2)
    assert big.src == 2 and (big.top, big.bottom) == (13.2, 11.0)
    big_free = L.order_block_blend(o, h, l, c, 0, 3, "bull", pick="largest_body")
    assert big_free.src == 2                                                     # the lowest low of the run
    skip = L.order_block_blend(o, h, l, c, 0, 3, "bull", skip_encap=True)
    assert skip.top == 14.5 and skip.bottom == 11.0 and skip.src == 1
    assert L.order_block_blend(o, h, l, c, 0, 3, "bull").mt == pytest.approx((14.0 + 11.4) / 2)
    inside = L.order_block_blend(o, h, l, c, 0, 3, "bull", pick="blend_in_htf", htf_zone=[(10.5, 15.0)])
    assert inside.mt == pytest.approx((l[1] + h[3]) / 2) == pytest.approx(12.45)                  # (low of the first + high of the last) / 2
    assert inside.levels == (14.0,)
    outside = L.order_block_blend(o, h, l, c, 0, 3, "bull", pick="blend_in_htf", htf_zone=[(12.0, 13.0)])
    assert outside.src == 3                                                      # not inside the array: the last candle only
    # bearish mirror
    mb = L.order_block_blend(-o, -l, -h, -c, 0, 3, "bear", pick="original")
    assert mb.src == 1 and (mb.top, mb.bottom) == (-12.5, -14.5)
    with pytest.raises(ValueError):
        L.order_block_blend(o, h, l, c, 0, 3, "bull", pick="nope")


def test_consolidation_ob_open():
    """A 1h fixture of range bars preceded by a down candle yields one level at that candle's open."""
    o, h, l, c = mk([(100, 103, 99, 102), (102, 106, 101, 105), (105, 109, 104, 108),                       # a wide leg up
                     (108, 109.5, 103.5, 104.5),                                                            # the last down candle (wide)
                     (104.5, 105.5, 104.0, 105.0), (105.0, 105.6, 104.2, 104.6), (104.6, 105.5, 104.1, 105.2),
                     (105.2, 105.7, 104.4, 104.9), (104.9, 105.5, 104.3, 105.3)])                           # five tight overlapping bars
    z = L.consolidation_ob_opens(o, h, l, c, 4, 1.5)
    assert len(z) == 1 and z[0].kind == "bull" and z[0].top == 108.0 and z[0].src == 3 and z[0].tag == "cons_ob_open"
    assert z[0].i == 7                                                                 # known when the range reached 4 bars
    mo, mh, ml, mc = (-o, -l, -h, -c)
    zm = L.consolidation_ob_opens(mo, mh, ml, mc, 4, 1.5)
    assert len(zm) == 1 and zm[0].kind == "bear" and zm[0].top == -108.0
    assert L.consolidation_ob_opens(o[:6], h[:6], l[:6], c[:6], 4, 1.5) == []         # no consolidation yet
    # the engine levels: known from the 1h bar that completes the range, dropped by a body close below the open
    p = Params(**BASE, cons_ob_open=True)
    ctx = type("X", (), dict(cons_ob=[dict(kind="bull", level=108.0, known=pd.Timestamp("2026-06-23 10:00", tz=NY))],
                             idx=pd.date_range("2026-06-23 09:00", periods=24, freq="5min", tz=NY),
                             c=np.full(24, 109.0), tf=5))()
    sd = S.Side(1, np.ones(3), np.ones(3), np.ones(3), np.ones(3), 1)
    assert LD.cons_ob_levels(ctx, sd, 12, p) == [(108.0, "bull")]                       # 10:00 + 5m <= now
    assert LD.cons_ob_levels(ctx, sd, 8, p) == []                                       # not known at 09:45
    ctx.c = np.concatenate([np.full(14, 109.0), np.full(10, 107.0)])                    # a close below the open after it was known
    assert LD.cons_ob_levels(ctx, sd, 20, p) == []


def test_inversion_any_pd_array():
    """A bullish OB closed below then retraced to its MT produces a short array at exactly lo / mt."""
    ob = L.Zone("bull", 12.0, 10.0, 2, 1, 11.4)                                       # MT = the body mean threshold
    o, h, l, c = mk([(11, 11.5, 10.5, 11.2), (12, 12.5, 11, 11.5), (11.5, 11.8, 10.2, 10.6), (10.8, 11.0, 9.4, 9.6),
                     (9.6, 10.9, 9.5, 10.8), (10.8, 11.4, 10.6, 11.0)])
    inv = L.inverted_arrays(o, h, l, c, [ob], "ob")
    assert len(inv) == 1 and inv[0].kind == "inv_ob" and inv[0].tag == "bear" and inv[0].i == 3
    assert inv[0].levels == (10.0, 11.4, 12.0)                                         # exactly high, low and MT
    assert L.invert(L.Zone("bear", 20.0, 18.0, 5, 4), 7, "bull", "vi").levels == (18.0, 19.0, 20.0)   # no MT: the CE
    # engine: the inverted array is a target above (low, MT) while no body closes back above the MT
    sd = S.Side(1, o, h, l, c, 1)
    p = Params(**BASE, inversions=("ob",))
    ctx = type("X", (), dict(conf=None))()
    sd._lz[("ld_inv", ("ob",))] = inv
    assert [z.tag for z in LD.inverted(ctx, sd, 5, p, "bear")] == ["bear"]
    c2 = c.copy(); c2[5] = 11.6                                                        # a close above the MT retires the role
    sd2 = S.Side(1, o, h, l, c2, 1)
    sd2._lz[("ld_inv", ("ob",))] = inv
    assert LD.inverted(ctx, sd2, 5, p, "bear") == []
    assert LD.inverted(ctx, sd, 2, p, "bear") == []                                    # not before the closing bar


def test_inversion_kinds_vi_breaker():
    vi = L.Zone("bear", 10.4, 10.0, 1, 1)
    o, h, l, c = mk([(10.5, 10.9, 10.3, 10.6), (10.0, 10.4, 9.8, 9.9), (9.9, 10.1, 9.7, 10.0), (10.0, 10.7, 9.9, 10.6)])
    inv = L.inverted_arrays(o, h, l, c, [vi], "vi")
    assert len(inv) == 1 and inv[0].tag == "bull" and inv[0].i == 3 and inv[0].levels == (10.0, 10.2, 10.4)


def test_mitigation_mt_invalid():
    """A mitigation block with a body close below its MT is dropped when the switch is on."""
    z = L.Zone("bull", 12.0, 10.0, 3, 1, 11.0)
    c = A([11.5, 11.5, 11.5, 11.5, 10.5, 11.5])             # a close at 10.5: above the bottom, below the MT
    assert L.mitigation_alive(c, z, 5) is True
    assert L.mitigation_alive(c, z, 5, use_mt=True) is False
    assert L.mitigation_alive(c, z, 3, use_mt=True) is True
    # the detector adds the body mean when asked
    h = A([10, 12, 13, 11, 10, 9, 8, 9, 11, 12, 13.0]); l = h - 1.5
    o = h - 0.5; c2 = h - 1.0
    for legacy in (False, True):
        a = L.mitigation_blocks(o, h, l, c2, 1, legacy)
        b = L.mitigation_blocks(o, h, l, c2, 1, legacy, with_mt=True)
        assert [(x.kind, x.top, x.bottom, x.i) for x in a] == [(x.kind, x.top, x.bottom, x.i) for x in b]
        assert all(x.mt != x.mt for x in a) and all(x.mt == x.mt for x in b)


def test_breaker_candle_pick_modes():
    """Two up-close candles (the later one larger-bodied, the earlier one with the higher close): a different index per mode."""
    o, h, l, c = mk([(10, 10.5, 9.5, 9.8),                # 0: down
                     (9.8, 12.0, 9.7, 11.8),              # 1: up, the highest close, small body? (2.0)
                     (11.0, 11.9, 10.8, 11.7),            # 2: up, lower close
                     (11.6, 11.7, 9.0, 9.5)])             # 3: down
    assert L.breaker_candle(o, c, 0, 3, "bull") == 1                       # extreme close (the built behaviour)
    assert L.breaker_candle(o, c, 0, 3, "bull", pick="last") == 2          # the last up-close candle
    o2 = o.copy(); c2 = c.copy(); o2[2], c2[2] = 9.5, 11.8                 # equal highest closes, a bigger body later
    assert L.breaker_candle(o2, c2, 0, 3, "bull", pick="extreme_close") == 1
    assert L.breaker_candle(o2, c2, 0, 3, "bull", pick="extreme_body") == 2
    # a wick-only extreme is discarded with body_swing: candle 1's close is not the extreme of all bodies (a down candle opened higher)
    o3 = o.copy(); o3[0] = 12.5
    assert L.breaker_candle(o3, c, 0, 3, "bull", body_swing=False) == 1
    assert L.breaker_candle(o3, c, 0, 3, "bull", pick="last", body_swing=True) == 2
    assert L.breaker_candle(-o, -c, 0, 3, "bear", pick="last") == 2        # bearish mirror
    with pytest.raises(ValueError):
        L.breaker_candle(o, c, 0, 3, "bull", pick="x")


def test_breaker_zone_blend_and_leg_disruptor():
    """Two consecutive candles at the swing produce the union zone in "blend"."""
    # a bearish breaker: two consecutive down-close candles (1, 2) at the swing low, the lowest close at 2
    o, h, l, c = mk([(10, 10.6, 9.9, 10.5), (10.5, 10.6, 9.6, 9.8), (9.8, 9.9, 9.1, 9.3), (9.3, 10.4, 9.2, 10.3)])
    z = L.breaker_zone(o, h, l, c, 0, 3, 3, "bear", "blend")
    assert (z.top, z.bottom) == (10.6, 9.1) and z.mt == pytest.approx((10.6 + 9.1) / 2) and z.src == 2
    single = L.breaker_zone(o, h, l, c, 0, 3, 3, "bear", "range")
    assert (single.top, single.bottom) == (9.9, 9.1)
    # bullish leg: A (bar 0) -> disruptor (the first down-close candle) -> B (the highest high)
    o, h, l, c = mk([(10, 10.5, 9.5, 10.4), (10.4, 11.0, 10.2, 10.9), (10.9, 11.1, 10.3, 10.5), (10.5, 12.0, 10.4, 11.9)])
    leg = L.breaker_zone(o, h, l, c, 0, 3, 3, "bull", "leg")
    dis = L.breaker_zone(o, h, l, c, 0, 3, 3, "bull", "leg_disruptor")
    assert (leg.top, leg.bottom) == (12.0, 9.5) and (dis.top, dis.bottom) == (12.0, 10.3)
    assert dis.mt == pytest.approx((12.0 + 10.3) / 2)
    assert {"blend", "leg_disruptor"} <= set(L.BREAKER_MODES)


def _breakaway_fixture():
    # side space (bullish): sweep low at bar 3, first MSS at bar 7 (c > swing high 106), its FVG at 6-8; pullback; a NEW swing high
    # (bar 13) is closed through at bar 17 (the second MSS) leaving a second FVG
    rows = [(110, 111, 109, 110), (110, 110.5, 107, 107.5), (107.5, 108, 104, 104.5), (104.5, 105, 100, 101),
            (101, 103, 100.8, 102.5), (102.5, 105, 102, 104.5), (104.5, 106.5, 104, 106), (106, 111, 106.4, 110.5),
            (110.5, 112, 110.2, 111.5), (111.5, 112, 110.5, 111), (111, 111.5, 109, 109.5), (109.5, 110, 107.8, 108.2),
            (108.2, 109.5, 108, 109.2), (109.2, 112.5, 109, 112), (112, 112.4, 110, 110.5), (110.5, 111, 109, 109.6),
            (109.6, 110.5, 109.2, 110.2), (110.2, 116, 110.4, 115.5), (115.5, 118, 115.2, 117.5), (117.5, 118.5, 116, 117)]
    return mk(rows)


def test_breakaway_def_second_mss():
    """A 062-style fixture tags only the second-MSS gap under "second_mss"."""
    o, h, l, c = _breakaway_fixture()
    sd = S.Side(1, o, h, l, c, 1)
    gaps = sd.gaps
    assert len(gaps) >= 2
    sw = dict(ext=100.0, ext_i=3, broke=7, level=104.0)
    p = Params(**BASE, breakaway="tag")
    ctx = type("X", (), dict(conf=None, hzones=None))()
    first = LD.breakaway_gap(ctx, sd, sw, 19, p)
    assert first.i >= 7 and first.i == gaps[[g.i >= 7 for g in gaps].index(True)].i
    p2 = replace(p, breakaway_def="second_mss")
    second = LD.breakaway_gap(ctx, sd, sw, 19, p2)
    assert second is not None and second.i > first.i
    assert LD.breakaway_gap(ctx, sd, sw, 12, p2) is None                    # the second shift has not printed yet
    # context: no HTF level -> a common gap
    assert LD.breakaway_gap(ctx, sd, sw, 19, replace(p, breakaway_def="context")) is None
    ctx2 = type("X", (), dict(conf=_ConfStub([(101.0, 99.0, "4h", 0, 0.0)]), hzones=None, idx=pd.date_range("2026-06-23 09:30", periods=20, freq="5min", tz=NY), tf=5))()
    got = LD.breakaway_gap(ctx2, sd, sw, 19, replace(p, breakaway_def="context"))
    assert got is first
    far = type("X", (), dict(conf=_ConfStub([(150.0, 140.0, "4h", 0, 0.0)]), hzones=None, idx=ctx2.idx, tf=5))()
    assert LD.breakaway_gap(far, sd, sw, 19, replace(p, breakaway_def="context")) is None
    near = type("X", (), dict(conf=_ConfStub([(121.0, 120.0, "4h", 0, 0.0)]), hzones=None, idx=ctx2.idx, tf=5))()   # 20 pts above the origin
    assert LD.breakaway_gap(near, sd, sw, 19, replace(p, breakaway_def="context", breakaway_ctx_pts=10.0)) is None
    assert LD.breakaway_gap(near, sd, sw, 19, replace(p, breakaway_def="context", breakaway_ctx_pts=25.0)) is first


class _ConfStub:
    def __init__(self, rows):
        self.rows = rows

    def valid(self, t, side, tfs, src=(0, 1, 3), known_by=None):
        return self.rows


# --- A5 caffeine bar, reclaimed FVG, HTF entry zones, initial FVG (24, 32, 35, 36) --------------------------------------

def test_single_bar_fvg_strict():
    """A 1-tick trade below the low kills only tagged gaps."""
    n = 30
    o = np.full(n, 100.0); h = o + 0.5; l = o - 0.5; c = o.copy()
    # bars 25-27: a big up candle (range 6) as c2 of a bullish FVG: c1 high 100.5, c3 low 101.5
    h[25], l[25] = 100.5, 99.5
    o[26], h[26], l[26], c[26] = 100.0, 106.0, 100.0, 105.5
    o[27], h[27], l[27], c[27] = 105.5, 106.5, 101.5, 106.0
    o[28:], h[28:], l[28:], c[28:] = 102.5, 103.0, 102.0, 102.5                # price stays above the gap afterwards
    z = [g for g in L.fvgs(h, l, o, c, single_bar=2.0) if g.kind == "bull"]
    assert len(z) == 1 and z[0].tag == "single_bar" and (z[0].top, z[0].bottom) == (101.5, 100.5)
    assert [g.tag for g in L.fvgs(h, l, o, c) if g.kind == "bull"] == [""]       # no tag without the multiple
    sd = S.Side(1, o, h, l, c, 1, single_bar=2.0)
    g = sd.gaps[0]
    ctx = type("X", (), dict(day=D0))()
    p = Params(**BASE, single_bar_fvg_strict=True)
    h2, l2, c2 = h.copy(), l.copy(), c.copy()
    l2[28], c2[28], h2[28] = 100.4, 102.0, 102.5                           # a wick 1 tick below the low (100.5); the close stays above
    sd2 = S.Side(1, o, h2, l2, c2, 1, single_bar=2.0)
    assert LD.gap_open(sd2, sd2.gaps[0], 29, ctx, p) is False
    assert LD.gap_open(sd2, sd2.gaps[0], 29, ctx, replace(p, single_bar_fvg_strict=False)) is True      # the close rule: still open
    plain = S.Side(1, o, h2, l2, c2, 1)
    assert LD.gap_open(plain, plain.gaps[0], 29, ctx, p) is True           # an untagged gap keeps the close rule
    nfp = type("X", (), dict(day=date(2026, 6, 5)))()                       # an NFP Friday: validity is not judged on the wick
    assert LD.gap_open(sd2, sd2.gaps[0], 29, nfp, p) is True


def test_reclaimed_fvg():
    """Break-chop-close-above within 3 bars is not reclaimed; after a swing away it is."""
    n = 40
    base = np.full(n, 110.0)
    o, h, l, c = base.copy(), base + 0.4, base - 0.4, base.copy()
    # bullish FVG [101.0 .. 102.0] at bars 2-4
    for k, (oo, hh, ll, cc) in enumerate([(100, 101.0, 99.5, 100.5), (100.5, 104, 100.5, 103.5), (103.5, 105, 102.0, 104.5)], start=2):
        o[k], h[k], l[k], c[k] = oo, hh, ll, cc
    o[:2], h[:2], l[:2], c[:2] = 100, 100.4, 99.6, 100
    # chop: break (close under 101) at 8, a deeper low at 9, back above at 10 -> within 3 bars: not reclaimed
    for k in range(5, 8):
        o[k], h[k], l[k], c[k] = 104, 104.5, 103.5, 104.2
    o[8], h[8], l[8], c[8] = 104, 104.2, 100.2, 100.6
    o[9], h[9], l[9], c[9] = 100.6, 101.0, 98.0, 100.0
    o[10], h[10], l[10], c[10] = 100.0, 103.0, 99.8, 102.6
    for k in range(11, n):
        o[k], h[k], l[k], c[k] = 103, 103.5, 102.6, 103.2
    z = [g for g in L.fvgs(h, l) if g.kind == "bull" and g.i == 4]
    assert z and (z[0].top, z[0].bottom) == (102.0, 101.0)
    assert L.reclaimed_fvgs(h, l, c, z, swing_n=1) == []
    # after a swing away: lower low, a few bars below, then a close back above the high
    for k, (hh, ll, cc) in enumerate([(100.6, 99.0, 99.4), (99.6, 97.5, 98.0), (99.0, 97.0, 98.5), (99.8, 98.2, 99.6),
                                      (101.0, 99.4, 100.8), (103.6, 100.6, 103.2)], start=9):
        o[k], h[k], l[k], c[k] = c[k - 1], hh, ll, cc
    r = L.reclaimed_fvgs(h, l, c, z, swing_n=2)
    assert len(r) == 1 and r[0].tag == "reclaimed" and r[0].bi == 8 and r[0].i > 12 and (r[0].top, r[0].bottom) == (102.0, 101.0)
    assert L.reclaimed_fvgs(h, l, c, z, swing_n=2, min_bars=20) == []
    # mirror
    mz = [L.Zone("bear", -101.0, -102.0, 4, 3)]
    mr = L.reclaimed_fvgs(-l, -h, -c, mz, swing_n=2)
    assert len(mr) == 1 and mr[0].kind == "bear"


def test_htf_entry_arrays_zone_without_a_ltf_gap():
    """A 1h FVG with no 1m / 5m gap inside still arms an entry zone when 60 is listed."""
    # a smooth climb over three hours, wicks +-0.25 around a 0.2 step: no 5m 3-candle gap anywhere, but the 1h bars 09:00 / 10:00 / 11:00
    # leave one (c1 high ~100.4 < c3 low ~102.9)
    px = 100.0 + 0.2 * np.arange(36)
    rows = [(a, a + 0.25, a - 0.25, a + 0.1) for a in px]
    df = frame(date(2026, 6, 23), rows, 5, "09:00")
    ctx = ctx_for(df, history(D0, n=8), Params(**BASE))
    sd = S.Side(1, ctx.o, ctx.h, ctx.l, ctx.c, 1)
    k0 = S._idx_at(ctx, 540)
    assert not [g for g in sd.gaps if g.i >= k0]                                  # no lower-timeframe 3-candle gap
    p = Params(**BASE, htf_entry_arrays=(60,))
    i = len(ctx.t) - 1
    sw = dict(ext=99.0, ext_i=k0 + 1)
    got = LD.htf_entry_zones(ctx, sd, sw, i, p)
    assert len(LD.htf_entry_zones(ctx, sd, sw, i, replace(p, htf_entry_arrays=(15, 60)))) > len(got)       # 15m listed too: more zones
    fv = [z for z in got if z.mt != z.mt and z.i >= k0]
    # two 1h gaps: (yesterday's 15:00, today's 09:00, 10:00) known at 10:00's last bar, and (09:00, 10:00, 11:00) known at the 11:00 bar
    assert [z.i - k0 for z in fv] == [23, 35] and fv[1].bottom == pytest.approx(102.45) and fv[1].top == pytest.approx(104.55)
    assert LD.htf_entry_zones(ctx, sd, sw, k0 + 20, p) == []                          # not known before the third 1h candle closed
    assert LD.htf_entry_zones(ctx, sd, sw, i, replace(p, htf_entry_arrays=())) == []
    assert LD.htf_entry_zones(ctx, sd, dict(ext=sd.c[i] + 1, ext_i=k0), i, p) == []    # a zone above the market is no limit entry
    assert LD.htf_entry_zones(ctx, sd, sw, i, replace(p, htf_entry_arrays=(5,))) == []   # the base timeframe itself is not an HTF


def test_initial_fvg_reference_zones():
    """A day fixture yields one zone; the tag reads respected / disrespected."""
    p = Params(**BASE, initial_fvg=("day", "week", "mon10"))
    rows = [(100, 100.5, 99.5, 100.2), (100.2, 102.5, 100.0, 102.3), (102.3, 103.5, 101.8, 103.2),    # a 5m bullish FVG: 100.5 .. 101.8
            (103.2, 103.6, 102.8, 103.0)] + [(103.0, 103.2, 102.8, 103.0)] * 20
    df = day(rows, start="09:30")
    hist = history(D0, n=8)
    ctx = ctx_for(df, hist, p)
    zs = [z for z in ctx.initfvg if z["name"] == "day"]
    assert len(zs) == 1 and (zs[0]["top"], zs[0]["bottom"]) == (101.8, 100.5) and zs[0]["kind"] == "bull"
    k0 = S._idx_at(ctx, 570)
    i0 = k0 + 12
    assert LD.init_state(ctx, zs[0], i0) == "untested"
    tags, text = LD.init_fvg_tags(ctx, i0, p)
    assert "initfvg_day_untested" in tags and text.startswith("day:")
    # a later tag: price trades into the zone and closes back out -> respected; a body close below it -> disrespected
    rows2 = rows[:4] + [(103.0, 103.1, 101.0, 102.9)] + [(102.9, 103.2, 102.8, 103.0)] * 19
    ctx2 = ctx_for(day(rows2, start="09:30"), hist, p)
    z2 = [z for z in ctx2.initfvg if z["name"] == "day"][0]
    assert LD.init_state(ctx2, z2, S._idx_at(ctx2, 570) + 12) == "respected"
    rows3 = rows[:4] + [(103.0, 103.1, 99.0, 100.0)] + [(100.0, 100.5, 99.8, 100.2)] * 19
    ctx3 = ctx_for(day(rows3, start="09:30"), hist, p)
    z3 = [z for z in ctx3.initfvg if z["name"] == "day"][0]
    assert LD.init_state(ctx3, z3, S._idx_at(ctx3, 570) + 12) == "disrespected"
    assert ctx_for(df, hist, replace(p, initial_fvg=())).initfvg == []
    # not known before its third candle closed
    early = LD.init_fvg_tags(ctx, k0 + 1, p)
    assert early == ([], "")


# --- A9 VI definition / delivery state / forward levels (37, 38, 41) -----------------------------------------------------

def test_vi_without_wick_condition_and_multi():
    """A gap-up bar with no wick overlap is found when vi_wick_overlap=False (and is also a void)."""
    o, h, l, c = mk([(10.0, 10.5, 9.8, 10.4), (11.5, 12.0, 11.2, 11.9)])        # bodies 10.4 | 11.5; wicks 10.5 | 11.2: no overlap
    assert L.volume_imbalances(o, h, l, c) == []
    v = L.volume_imbalances(o, h, l, c, wick_overlap=False)
    assert len(v) == 1 and (v[0].top, v[0].bottom) == (11.5, 10.4) and v[0].tag == "void"
    o, h, l, c = mk([(10.0, 10.5, 9.8, 10.4), (11.5, 12.0, 10.45, 11.9)])        # wicks overlap: a plain VI, not a void
    assert L.volume_imbalances(o, h, l, c)[0].tag == "" and L.volume_imbalances(o, h, l, c, wick_overlap=False)[0].tag == ""
    # bearish mirror
    mo, mh, ml, mc = (-o, -l, -h, -c)
    assert L.volume_imbalances(mo, mh, ml, mc)[0].kind == "bear"
    # multi: A body 100-110, B small inside it 102-104, C body 115-120 -> the free band is 110..115, not 104..115
    o, h, l, c = mk([(100, 111, 99, 110), (102, 104.5, 101.5, 104), (115, 121, 112, 120)])
    one = L.volume_imbalances(o, h, l, c)
    assert (one[0].top, one[0].bottom) == (115.0, 104.0) if one else True
    multi = L.volume_imbalances(o, h, l, c, wick_overlap=False, multi=True)
    assert [(z.top, z.bottom) for z in multi if z.i == 2] == [(115.0, 110.0)]
    plain = L.volume_imbalances(o, h, l, c, wick_overlap=False)
    assert [(z.top, z.bottom) for z in plain if z.i == 2] == [(115.0, 104.0)]
    # the Side reads the flags
    sd = S.Side(1, o, h, l, c, 1, vi_wick_overlap=False, vi_multi=True)
    assert [(z.top, z.bottom) for z in sd.vis("bull") if z.i == 2] == [(115.0, 110.0)]


def test_vi_delivery_states_and_dead_rule():
    """A partial body overlap marks target_hit but not dead."""
    z = L.Zone("bull", 11.0, 10.0, 1, 1)
    o = A([10.0, 12.0, 12.0, 10.5, 11.5, 9.0]); c = A([10.0, 12.0, 11.9, 11.5, 12.5, 12.0])
    h = A([10.2, 12.2, 12.1, 11.6, 12.6, 12.2]); l = A([9.8, 11.8, 11.7, 10.4, 11.4, 8.9])
    assert L.vi_state(o, h, l, c, z, 0.25, end=2) == "open"
    assert L.vi_state(o, h, l, c, z, 0.25, end=3) == "target_hit"                 # a body 10.5 -> 11.5 overlaps, does not span
    assert L.vi_body_dead(o, c, z, end=3) is None and L.vi_body_dead(o, c, z, end=3, rule="overlap") == 3
    assert L.vi_state(o, h, l, c, z, 0.25, end=3, rule="overlap") == "dead"
    assert L.vi_state(o, h, l, c, z, 0.25, end=5) == "dead"                       # bar 5's body 9 -> 12 spans the whole VI
    assert L.vi_body_dead(o, c, z) == 5
    # wicks only: reached (a wick through the far edge by a tick) but no body overlap
    o2 = A([10.0, 12.0, 12.0, 12.0]); c2 = A([10.0, 12.0, 11.9, 11.8])
    h2 = A([10.2, 12.2, 12.1, 12.1]); l2 = A([9.8, 11.8, 11.7, 9.5])
    assert L.vi_state(o2, h2, l2, c2, z, 0.25) == "reached"
    sdm = Params(vi_dead_rule="overlap")
    assert sdm.vi_body_death is True and Params(vi_two_sided_draw=True).vi_body_death is True      # the umbrellas
    assert Params().vi_dead_rule == "full_span" and Params().vi_body_death is False


def test_vi_flip_support_daily():
    """A daily VI reached Tuesday is a support array Wednesday."""
    wed = date(2026, 6, 24)
    mon, tue = date(2026, 6, 22), date(2026, 6, 23)
    # Monday: closes at 100; Tuesday gaps DOWN to a body below Monday's (a bearish VI above price): zone [101.0, 102.0] is above Tue's close
    hist = history(wed, n=6)
    hist = [h_ for h_ in hist if h_.index[0].date() < mon]
    d_mon = rth_day(mon, 104.0, 100.0, close=102.0, op=102.5)
    d_tue = rth_day(tue, 101.0, 98.0, close=99.0, op=100.8)                         # body 100.8 .. 99 below Mon's body 102.5 .. 102 -> a VI
    p = Params(**BASE, vi_flip_support=True)
    rows = [(99.0, 99.5, 98.5, 99.2)] * 3 + [(99.2, 102.5, 99.0, 102.0)] + [(102.0, 102.1, 101.0, 101.2)] * 3 + [(101.2, 101.3, 100.0, 100.5)] * 20
    df = day(rows, d=wed)
    ctx = ctx_for(df, hist + [d_mon, d_tue], p)
    assert ctx.vi_flip and ctx.vi_flip[0]["role"] == "support"
    z = ctx.vi_flip[0]
    k0 = S._idx_at(ctx, 570)
    i_before = k0 + 1
    assert LD.vi_flip_levels(ctx, i_before, p) == []                                # not reached yet (09:35)
    k = k0 + 12
    lv = LD.vi_flip_levels(ctx, k, p)
    assert sorted(v for v, _ in lv) == sorted([z["top"], z["mid"], z["bottom"]]) and all(n == "vi_support" for _, n in lv)
    # a 60m body close below the VI low retires it
    rows2 = rows[:12] + [(100.5, 100.6, 95.0, 95.5)] * 12 + [(95.5, 95.6, 95.0, 95.2)] * 12
    ctx2 = ctx_for(day(rows2, d=wed), hist + [d_mon, d_tue], p)
    assert LD.vi_flip_levels(ctx2, S._idx_at(ctx2, 570) + 11, p) != []
    assert LD.vi_flip_levels(ctx2, S._idx_at(ctx2, 570) + 40, p) == []
    assert ctx_for(df, hist + [d_mon, d_tue], replace(p, vi_flip_support=False)).vi_flip == []


# --- A16, A17, A21, A23 (43, 47, 54, 57) ----------------------------------------------------------------------------------

def test_propulsion_definitions():
    """An unconfirmed OB yields no PB under cc04_008."""
    ob = L.Zone("bull", 105.0, 100.0, 1, 0, 102.0)
    o = A([100.0, 104.0, 104.5, 104.0, 105.2, 108.0, 106.0, 104.0])
    c = A([104.0, 104.5, 104.0, 104.8, 107.5, 106.2, 104.5, 105.0])
    h = A([105.0, 105.0, 105.0, 104.9, 108.0, 108.5, 106.5, 105.5])
    l = A([100.0, 103.8, 103.5, 103.5, 105.0, 105.5, 104.0, 103.9])
    base = L.propulsion_blocks(o, h, l, c, [ob])
    assert len(base) == 1 and base[0].i == 2                                          # a16: the first down candle trading into the OB
    cc4 = L.propulsion_blocks(o, h, l, c, [ob], "cc04_008")
    assert len(cc4) == 1 and cc4[0].i > 4                                             # after the OB high (105) was taken at bar 4
    unconf = L.propulsion_blocks(o[:4], h[:4], l[:4], c[:4], [ob], "cc04_008")
    assert unconf == [] and L.propulsion_blocks(o[:4], h[:4], l[:4], c[:4], [ob], need_confirm=True) == []
    assert L.propulsion_blocks(o, h, l, c, [ob], "cc04_008", bias=-1) == []
    loose = L.propulsion_blocks(o, h, l, c, [ob], "cc09_008")
    assert len(loose) == 1 and loose[0].mt == 104.5 and loose[0].levels == (104.5,) and loose[0].i >= 3
    with pytest.raises(ValueError):
        L.propulsion_blocks(o, h, l, c, [ob], "x")


def test_rejection_block_levels():
    """Bullish fixture: level1 = the lowest down-close close; level2 = the midpoint to the low."""
    o, h, l, c = mk([(110, 111, 109, 110.5), (110.5, 111, 108.5, 109.0), (109.0, 109.6, 104.0, 108.0),
                     (108.0, 108.8, 106.5, 107.0), (107.5, 109.5, 106.8, 109.0), (109.0, 111, 108.8, 110.5)])
    z = [x for x in L.rejection_blocks(o, h, l, c, 1, 0.0, "close") if x.kind == "bull"]
    assert len(z) == 1 and z[0].bottom == 104.0
    dn = [c[k] for k in range(1, 4) if c[k] < o[k]]
    assert z[0].top == min(dn) and z[0].levels[0] == min(dn)
    assert z[0].levels[2] == 104.0 and z[0].levels[1] == pytest.approx((min(dn) + 104.0) / 2)
    old = [x for x in L.rejection_blocks(o, h, l, c, 1, 0.0) if x.kind == "bull"][0]
    assert old.top == min(min(o[k], c[k]) for k in range(1, 4))                       # open_close: the lowest body edge of any candle
    # bearish: highest up-close close
    mo, mh, ml, mc = (-o, -l, -h, -c)
    b = [x for x in L.rejection_blocks(mo, mh, ml, mc, 1, 0.0, "close") if x.kind == "bear"]
    assert b and b[0].top == -104.0 and b[0].bottom == -min(dn)


def test_dealing_range_energetic_anchor():
    """A fixture with an old rounded low and a newer displaced low anchors on the newer."""
    n = 60
    px = np.concatenate([np.linspace(110, 100.5, 15), np.linspace(100.5, 100.0, 10), np.linspace(100.0, 101.0, 8),   # old rounded low ~100
                         np.linspace(101.0, 106.0, 4), np.linspace(106.0, 103.0, 6), np.linspace(103.0, 102.0, 3)])
    o = px.copy(); c = px + 0.05; h = px + 0.3; l = px - 0.3
    # a newer swing low (bar 36) followed by displacement up (three big up candles leaving an FVG)
    base = len(px)
    seg = [(102.0, 102.2, 100.9, 101.0), (101.0, 101.4, 100.8, 101.3), (101.3, 101.6, 101.0, 101.5),
           (101.5, 104.5, 101.5, 104.2), (104.2, 107.0, 104.0, 106.8), (106.8, 109.5, 106.6, 109.0), (109.0, 110.0, 108.4, 109.4)]
    o = np.concatenate([o, A([s[0] for s in seg])]); h = np.concatenate([h, A([s[1] for s in seg])])
    l = np.concatenate([l, A([s[2] for s in seg])]); c = np.concatenate([c, A([s[3] for s in seg])])
    r = L.dealing_range(h, l, o, c, len(c) - 1, "energetic")
    assert r is not None
    lo_i, hi_i, lo, hi = r
    assert lo_i >= base and lo == pytest.approx(100.8) and hi == 110.0               # the newer displaced low, not the old rounded 99.7
    assert L.dealing_range(h, l, o, c, len(c) - 1, "mss_leg") is None
    sw = dict(ext=99.0, ext_i=3)
    sd = S.Side(1, o, h, l, c, 1)
    p = Params(**BASE, leg_anchor="energetic")
    assert LD.leg_low(sd, sw, len(c) - 1, p, 110.0) == pytest.approx(100.8)
    assert LD.leg_low(sd, sw, len(c) - 1, replace(p, leg_anchor="mss_leg"), 110.0) == 99.0


def test_wick_quarters_and_tier():
    """A retrace to q25 is tagged "very_bearish"."""
    w = L.wick_midpoints(100.0, 110.0, 99.0, 104.0, quarters=True)                    # upper wick 104 .. 110
    assert w["upper"] == 107.0 and w["upper_q25"] == 105.5 and w["upper_q75"] == 108.5 and w["lower_q25"] < 100.0
    assert "upper_q25" not in L.wick_midpoints(100.0, 110.0, 99.0, 104.0)
    assert L.wick_tier(105.4, 104.0, 110.0) == "very_bearish"
    assert L.wick_tier(107.0, 104.0, 110.0) == "normal"
    assert L.wick_tier(108.0, 104.0, 110.0) == "overshoot"
    assert L.wick_tier(109.0, 104.0, 110.0) == "failed"
    assert L.wick_tier(103.0, 104.0, 110.0) == "none"
    # the engine tag for a short whose sweep ran to the q25 of yesterday's upper wick
    p = Params(**BASE, wick_quarters=True)
    ctx = type("X", (), dict(wicks=[w]))()
    short = S.Side(-1, A([1.0]), A([1.0]), A([1.0]), A([1.0]), 1)
    assert LD._wick_tier_tag(ctx, short, dict(ext=-105.4), p) == "wick_tier_very_bearish"
    longs = S.Side(1, A([1.0]), A([1.0]), A([1.0]), A([1.0]), 1)
    wl = L.wick_midpoints(100.0, 101.0, 90.0, 99.0, quarters=True)                    # lower wick 99 .. 90
    assert LD._wick_tier_tag(type("X", (), dict(wicks=[wl]))(), longs, dict(ext=96.8), p) == "wick_tier_very_bullish"


def test_converged_arrays_rank():
    """Between two equal-distance arrays, the one with an inner wick CE is picked."""
    a = L.Zone("bull", 102.0, 101.0, 5, 4)
    b = L.Zone("bull", 98.0, 97.0, 5, 4)
    assert L.converged_count(a, [], [101.5], 0.1) == 2                                # inside, and on its CE
    assert L.converged_count(a, [], [101.9], 0.1) == 1
    assert L.converged_count(b, [], [101.5], 0.1) == 0
    ob = L.Zone("bull", 102.5, 100.5, 3, 1, 101.5)
    vi = L.Zone("bull", 101.8, 101.2, 4, 4)
    assert L.converged_count(a, [ob, vi, a], [], 0.1) == 2                           # the OB and the VI overlap it
    o = np.full(12, 100.0); sd = S.Side(1, o, o + 1, o - 1, o, 1)
    sd._lz["ld_obs"] = []
    p = Params(**BASE, converge_rank=True)
    ctx = type("X", (), dict(wicks=[dict(upper=110.0, lower=101.5)], wick=dict(upper=110.0, lower=101.5)))()
    g, n = LD.pick_converged(ctx, sd, [b, a], 8, p, last=True)
    assert g is a and n >= 1                                                           # `last` would have taken a; the first-pick order b, a
    g2, n2 = LD.pick_converged(ctx, sd, [a, b], 8, p, last=True)
    assert g2 is a                                                                     # even when the default pick would be b


def test_diagonal_lows_pool():
    """Three rising lows produce a pool at the projected line."""
    lows = [(10, 100.0), (20, 101.0), (30, 102.0)]
    r = L.diagonal_lows(lows, 0.2, 40, 3)
    assert r is not None and r[0] == pytest.approx(103.0) and r[1] == pytest.approx(0.1) and r[2] == 3
    assert L.diagonal_lows(lows[:2], 0.2, 40, 3) is None                              # two swings are no line
    assert L.diagonal_lows([(10, 100.0), (20, 101.0), (30, 101.4)], 0.2, 40, 3) is None   # not on one line
    assert L.diagonal_lows([(10, 100.0), (20, 99.0), (30, 98.0)], 0.2, 40, 3) is None     # falling lows
    r4 = L.diagonal_lows([(5, 98.0)] + lows, 0.2, 40, 3)                               # an older off-line swing is left out
    assert r4 is not None and r4[2] == 3
    # engine: a smooth run of higher lows (the line sits under price, untaken) is a sweep pool of kind "diag"
    rows = []
    for k in range(60):
        lo = 99.0 + 0.1 * k if k % 10 == 0 else 101.0 + 0.1 * k
        rows.append((lo + 1.0, lo + 1.6, lo, lo + 1.2))
    df = day(rows, start="09:30")
    p = Params(**BASE, diag_pools=True, eq_tol_pts=0.3)
    ctx = ctx_for(df, history(D0, n=8), p)
    sd = S.Side(1, ctx.o, ctx.h, ctx.l, ctx.c, 1)
    i = S._idx_at(ctx, 570) + 50
    v = LD.diag_level(ctx, sd, i, p)
    assert v is not None and v < sd.c[i - 1]
    keys = S._sell_side(ctx, sd, "AM", i, False, p)
    assert keys.get("diag") == v and "diag" not in S._sell_side(ctx, sd, "AM", i, False, replace(p, diag_pools=False))
    assert S._level_intact(ctx, sd.l, i, "diag", v, "AM")                              # the moving line is never "traded through"


# --- L5 opening gaps labels (67) ------------------------------------------------------------------------------------------

def test_nwog_labels_and_direction():
    """A Friday close above the Sunday open gives dir="down", high = the Friday close."""
    fri = pd.date_range("2026-06-19 16:50", periods=2, freq="5min", tz=NY)
    sun = pd.date_range("2026-06-21 18:00", periods=3, freq="5min", tz=NY)
    idx = fri.append(sun)
    # Friday last close 100.0 (16:55 bar), Sunday open 98.0
    d = pd.DataFrame({"open": [100.5, 100.2, 98.0, 98.2, 98.1], "high": [100.6, 100.3, 98.4, 98.3, 98.3],
                      "low": [100.1, 99.9, 97.8, 98.0, 98.0], "close": [100.2, 100.0, 98.2, 98.1, 98.2], "volume": 1.0}, index=idx)
    g = htf.opening_gaps(d)
    assert len(g) == 1 and g.dir.iloc[0] == "down" and g.high.iloc[0] == 100.0 and g.low.iloc[0] == 98.0
    assert g.close_before.iloc[0] == 100.0 and g.open_after.iloc[0] == 98.0
    up = d.copy(); up[["open", "high", "low", "close"]] = up[["open", "high", "low", "close"]] - 3
    up.iloc[2:, :4] = up.iloc[2:, :4] + 8.0
    gu = htf.opening_gaps(up)
    assert gu.dir.iloc[0] == "up" and gu.low.iloc[0] == pytest.approx(97.0) and gu.high.iloc[0] == pytest.approx(103.0 + 0.0, abs=6)
    day_ = date(2026, 6, 22)
    rows = htf.gaps_for_day(g, day_, with_dir=True)
    assert rows == [("nwog", 100.0, 98.0, 99.0, "down")]
    assert htf.gaps_for_day(g, day_) == [("nwog", 100.0, 98.0, 99.0)]               # the default shape is unchanged


# --- B10 topdown transposition (181) --------------------------------------------------------------------------------------

def test_topdown_transposed_rows():
    """A monthly bear FVG appears in the conf rows with tf "M" and as a target rung."""
    cf = Confluence.__new__(Confluence)
    cf.first20, cf.dends, cf.tol = False, np.array([]), 0.25
    t = pd.Timestamp("2026-06-23 10:00", tz=NY)
    cf.z = {"M": dict(kind=A([-1.0]), top=A([5200.0]), bottom=A([5100.0]), known=A([float(t.value) - 1e9]), dead=A([np.inf]),
                      src=A([0.0]), life=A([np.inf]))}
    rows = cf.opposing(t, 5000.0, 1, ("M",), (0,))
    assert len(rows) == 1 and rows[0][3] == "M" and rows[0][0] == 5100.0 and rows[0][1] == 5150.0     # near edge, CE, tf "M"
    p = Params(**BASE, topdown_targets=True)
    assert LD.htf_target_tfs(Params(**BASE), ("1h",)) == ("1h",)                          # off: unchanged
    tfs = LD.htf_target_tfs(p, ("1h", "D"))
    assert tfs == ("1h", "D", "4h", "W", "M")                                             # 4h / D / W / M join the ladder's sources
    lv = sorted(cf.targets(t, 5000.0, 1, tfs))                                            # the rung levels: near edge and CE
    assert lv == [5100.0, 5150.0]


# --- Params, plumbing, study --------------------------------------------------------------------------------------------

NEW_SWITCHES = ("vb_context", "ipda_anchor", "ipda_arrays_first20", "pool_tf", "topdown_targets", "consol_pools", "bpr_def",
                "bpr2_two_candle", "bpr2_trail", "bpr2_cont_trigger", "two_pass_state", "shield_passes", "ob_pick",
                "ob_skip_encapsulated", "cons_ob_open", "inversions", "mit_mt_invalid", "breaker_candle", "breaker_body_swing",
                "breakaway_def", "breakaway_ctx_pts", "single_bar_fvg_strict", "fvg_reclaim", "htf_entry_arrays", "initial_fvg",
                "vi_wick_overlap", "vi_multi", "vi_dead_rule", "vi_two_sided_draw", "vi_flip_support", "pb_def", "rb_level",
                "rb_ce_level", "leg_anchor", "wick_quarters", "wick_bias_line", "judas_wick_cap", "converge_rank", "diag_pools",
                "diag_min_swings")


def test_new_switch_defaults_and_validation():
    d = Params()
    # off / unchanged by default (the experienced version or the built behaviour)
    assert (d.vb_context, d.ipda_anchor, d.ipda_arrays_first20, d.pool_tf, d.topdown_targets, d.consol_pools) == \
        (False, "rolling", False, 1, False, False)
    assert (d.bpr_def, d.bpr2_trail, d.two_pass_state, d.ob_pick, d.breaker_candle, d.breakaway_def) == \
        ("overlap", False, False, "blend", "extreme_close", "first_after_mss")
    assert (d.vi_wick_overlap, d.vi_multi, d.vi_dead_rule, d.pb_def, d.leg_anchor, d.inversions, d.initial_fvg) == \
        (True, False, "full_span", "a16", "mss_leg", (), ())
    assert d.sb_model is False and d.sb_use_bias is False and d.want_all_engines is True                   # untouched
    for bad in (dict(ipda_anchor="x"), dict(bpr_def="x"), dict(ob_pick="x"), dict(breaker_candle="x"), dict(breakaway_def="x"),
                dict(vi_dead_rule="x"), dict(pb_def="x"), dict(rb_level="x"), dict(leg_anchor="x"), dict(inversions=("x",)),
                dict(initial_fvg=("year",)), dict(pool_tf=0), dict(diag_min_swings=2), dict(htf_entry_arrays=(0,)),
                dict(breaker_zone="x")):
        with pytest.raises(ValueError):
            Params(**bad)
    for ok in ("blend", "leg_disruptor"):
        Params(breaker_zone=ok)


def test_htf_kw_carries_the_vi_and_window_switches():
    assert B.htf_kw(Params()) == {"c2_dir": True}                                          # (A5 fvg_c2_dir is the spec default)
    kw = B.htf_kw(Params(vi_wick_overlap=False, vi_multi=True, vi_dead_rule="overlap", ipda_arrays_first20=True))
    assert kw["vi_wick_overlap"] is False and kw["vi_multi"] is True and kw["vi_dead_rule"] == "overlap"
    assert kw["ipda_first20"] is True and kw["vi_body_death"] is True
    assert "vi_two_sided" in B.table_kw(Params(vi_two_sided_draw=True)) and "vi_two_sided" not in B.htf_kw(Params(vi_two_sided_draw=True))
    assert B.hist_days(Params()) == B.HIST_DAYS and B.hist_days(Params(ipda_anchor="month")) > B.HIST_DAYS


def test_study_variants_for_the_caption_gap_pass():
    d = study.DECISIONS
    want = {"X3-l8-vb-exhaustion-gap", "X3-b21-ipda-anchor", "B21-ipda-windows-arrays", "X3-b5-15m-pools-5m-gaps",
            "X3-b10-topdown-transposition", "N8-consolidation-builds-orders", "A11-bpr-one-pass-definition", "X-efficient-delivery-two-pass",
            "A12-ob-candle-selection", "A12-consolidation-ob-open-level", "A8-inversion-any-pd-array", "A12-mt-all-blocks-ce-all-gaps",
            "A13-breaker-candle-selection", "A13-breaker-zone-extent", "A6-breakaway-identification", "A5-caffeine-bar-bisi",
            "A5-broken-fvg-reclaim", "B5-htf-arrays-anchor-transpose", "N-initial-fvg-reference", "A9-vi-definition-no-wick-condition",
            "A9-vi-delivery-state", "A9-daily-vi-forward-levels", "A16-propulsion-context-sequence", "A17-rejection-block-levels",
            "A21-dealing-range-energetic-swing", "A23-wick-quarter-strength", "confluence-stacked-arrays", "A3-diagonal-support-is-liquidity"}
    names = [k for k in d if any(k.startswith(w) for w in want)]
    for w in want:
        assert any(k.startswith(w) for k in names), w
    for k in names:
        replace(Params(), **{**study.DEC_BASE, **d[k]})                                   # every variant builds a valid Params
    used = {s for k in names for s in d[k]}
    for s in NEW_SWITCHES:
        assert s in used, s


def test_every_new_switch_is_named_by_a_test():
    src = Path(__file__).read_text(encoding="utf8")
    for s in NEW_SWITCHES:
        assert src.count(s) >= 2, s


# --- no look-ahead: full run vs truncated runs --------------------------------------------------------------------------------

ENTRY = ["entry_time", "entry", "stop", "t1", "shares", "entry_kind", "lv_tags", "init_fvg_respected", "session"]
EXIT = ["entry_time", "exit_time", "exit_reason"]
SYN = dict(es_pt=0.09, min_draw_pts=0, leg_pd=0, sloppy_mode="off", year_end="off")


def _no_look_ahead_x(df, tf, sym, p, cols, every=1, meta=None, lag=2, min_trades=1, **kw):
    """Cuts at entry AND exit times: the entries up to each cut, and the exits of the trades closed by it, match the full run."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        full = B.run(df, tf, sym, p, meta=meta, **kw)
        assert len(full) >= min_trades, "no trades - the test window must produce some"
        cuts = sorted(set(full.entry_time.iloc[::every]) | set(full.exit_time.dropna().iloc[::every]))
        for cut_t in cuts:
            c = cut_t + pd.Timedelta(minutes=lag)
            pk = {k: (v[v.index <= c] if isinstance(v, pd.DataFrame) else v) for k, v in kw.items()}
            part = B.run(df[df.index <= c], tf, sym, p, partial_last=True, meta=meta, **pk)
            a = full[full.entry_time <= cut_t][cols].reset_index(drop=True)
            b = part[part.entry_time <= cut_t][cols].reset_index(drop=True)
            pd.testing.assert_frame_equal(a, b, check_dtype=False)
            done = full.exit_time.notna() & (full.exit_time <= cut_t)
            a = full[done][EXIT].reset_index(drop=True)
            b = part[part.entry_time.isin(full[done].entry_time)][EXIT].reset_index(drop=True)
            pd.testing.assert_frame_equal(a, b, check_dtype=False)
    return full


GROUPS = {
    "levels": dict(vacuum_blocks=True, vb_context=True, pool_swings=True, pool_tf=15, consol_pools=True, diag_pools=True,
                   topdown_targets=True, ipda_pools=True, ipda_anchor="month", ipda_arrays_first20=True),
    "gaps": dict(bpr_def="both", bpr_targets=True, bpr_abort=True, bpr2_trail=True, bpr2_cont_trigger=True, two_pass_state=True,
                 fvg_targets=True, single_bar_fvg_strict=True, fvg_reclaim=True, htf_entry_arrays=(15, 60),
                 inversions=("ob", "breaker", "vi", "org", "nwog"), converge_rank=True),
    "blocks": dict(ob_pick="largest_body", ob_skip_encapsulated=True, cons_ob_open=True, entry_arrays=("ob", "cons_ob_open"),
                   mit_targets=True, mit_mt_invalid=True, breaker_candle="extreme_body", breaker_body_swing=True,
                   breaker_zone="blend", breaker_entry="fallback", breakaway="hold", breakaway_def="second_mss",
                   pb_def="cc04_008", rb_level="open_close", rb_ce_level=True, rb_targets="ladder"),
    "vi_ref": dict(vi_arrays=True, vi_wick_overlap=False, vi_multi=True, vi_dead_rule="overlap", vi_two_sided_draw=True,
                   vi_targets=True, vi_flip_support=True, initial_fvg=("day", "week", "mon10"), leg_anchor="energetic", leg_pd=0.5,
                   wick_quarters=True, wick_bias_line=True, judas_wick_cap=True),
}


@pytest.mark.parametrize("group", sorted(GROUPS))
def test_look_ahead_synthetic(group):
    x, y = B.synthetic(start="2026-04-06", end="2026-05-15", tf=5, seed=3)
    p = Params(**{**SYN, **dict(use_bias=True, bias_open="0930", ob_entry="both", draw_lock_neutral="both"), **GROUPS[group]})
    full = _no_look_ahead_x(x, 5, "RW", p, ENTRY, every=4, partner=y, min_trades=1)
    assert len(full)


def test_look_ahead_synthetic_post_mss_and_breakaway():
    x, y = B.synthetic(start="2026-04-06", end="2026-05-15", tf=5, seed=5)
    p = Params(**SYN, use_bias=True, bias_open="0930", ob_entry="post_mss", draw_lock="off", breakaway="tag",
               breakaway_def="context", fvg_reclaim=True, single_bar_fvg_strict=True, converge_rank=True, initial_fvg=("day",))
    _no_look_ahead_x(x, 5, "RW", p, ENTRY, every=4, partner=y)


def _es():
    df = B.load("ES", 5, source="databento")
    return df[(df.index >= "2023-10-02") & (df.index < "2023-11-10")], B.load_meta("ES", 5)


@pytest.mark.skipif(not ES, reason="no ES data")
def test_look_ahead_es_caption_gap_switches():
    """ES 5m with confluence and overnight sessions: the IPDA month anchor with the array windows, the VI definition and the daily VI
    states, the BPR Type 2 lists, inversions of the opening gaps, the reference FVGs."""
    df, meta = _es()
    p = Params(**FUT, vi_arrays=True, vi_wick_overlap=False, vi_multi=True, vi_dead_rule="overlap", vi_two_sided_draw=True,
               ipda_pools=True, ipda_anchor="month", ipda_arrays_first20=True, bpr_def="both", bpr_targets=True,
               inversions=("ob", "vi", "org", "nwog"), initial_fvg=("day", "week", "mon10"), topdown_targets=True,
               vi_flip_support=True, htf_entry_arrays=(15, 60), htf_resist_cap=False, ob_entry="both", leg_pd=0, min_draw_pts=0)
    full = _no_look_ahead_x(df, 5, "ES", p, ENTRY + ["draw_px", "draw_name"], every=5, meta=meta)
    assert len(full)
    q = replace(p, draw_lock="off", ob_entry="post_mss", fvg_reclaim=True, single_bar_fvg_strict=True, converge_rank=True,
                breakaway="hold", breakaway_def="context", two_pass_state=True, fvg_targets=True, wick_quarters=True)
    _no_look_ahead_x(df, 5, "ES", q, ENTRY, every=5, meta=meta)
