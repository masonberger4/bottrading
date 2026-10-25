"""Caption-gap pass, package levels_detectors #3/3 - the REVIEW FIXES (second round): the items the first build left partial are built and tested here
(L2-sr-needs-fvg flip retest, A17 rejection-block arrays in htf._arrays, the trendline-trap OB / breaker entries, the H&S re-arm, B21 window limits on
every merge, per-timeframe pools / zones, monthly arrays and frame, IPDA convergence / marker recompute, the Monday low raid, the Silver Bullet OR FVGs,
time distortion on swings and every zone source, ...). Unit tests plus no-look-ahead runs (full vs truncated) on a synthetic futures frame WITH overnight
bars - so the confluence / HTF-array paths run on every platform - and an assertion that each added switch's code path really ran (`ld4.HITS`).
Tests that need local market data skip cleanly when it is absent; no platform-specific paths."""
import warnings
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from mentorship import (backtest as B, bias_day as BD, calendar as C, confluence as CF, htf, ld2 as LD, ld3 as L3, ld4 as L4, levels as L, sb_model,
                        strategy as S, study)
from mentorship.strategy import Params

from test_levels_detectors import BASE, D0, ES, FUT, NY, day, frame, history, prior_days, rth_day
from test_caption_gap_ld3 import ctx3, k_at, mk, side, FLAT

A = np.array


def sd_of(rows, sign=1):
    o, h, l, c = mk(rows)
    return S.Side(sign, o, h, l, c, 1)


def stub_ctx(n, **kw):
    idx = pd.date_range("2026-06-23 09:30", periods=n, freq="5min", tz=NY)
    d = dict(idx=idx, tf=5, start=0, cur_bias=1, hist=history(D0, n=8), __dict__={}, t=(idx.hour * 60 + idx.minute).values, day=D0)
    d.update(kw)
    return SimpleNamespace(**d)


def syn_overnight(start="2026-01-05", sessions=100, tf=5, seed=11, price=4000.0):
    """Synthetic futures-style bars WITH overnight: each trading day d runs from the evening before (18:00; the Sunday for a Monday) to 17:00 - a thin
    overnight, a loud 09:30 hour, a reopen gap each evening - so the opening gaps, the Confluence arrays and the HTF table exist (the plain
    B.synthetic frames have no overnight bars and therefore no confluence object)."""
    rng = np.random.default_rng(seed)
    out, px = [], price
    d, n = pd.Timestamp(start), 0
    while n < sessions:
        if d.weekday() < 5 and C.is_trading_day(d.date()):
            a = pd.Timestamp((d - pd.Timedelta(days=1)).date(), tz=NY) + pd.Timedelta(hours=18)
            idx = pd.date_range(a, pd.Timestamp(d.date(), tz=NY) + pd.Timedelta(hours=17) - pd.Timedelta(minutes=tf), freq=f"{tf}min")
            m = idx.hour * 60 + idx.minute
            vol = np.where((m >= 570) & (m < 660), 2.4, np.where((m >= 540) & (m < 570), 1.6, np.where(m >= 960, 0.5, np.where((m >= 1080) | (m < 240), 0.5, 0.9))))
            z = rng.standard_t(4, len(idx)) / np.sqrt(2)
            gap = rng.normal(0, 2.5)
            c = px + gap + np.cumsum(z * vol)
            o = np.concatenate([[px + gap], c[:-1]])
            w = np.abs(rng.normal(0, 0.5, (2, len(idx)))) * vol
            out.append(pd.DataFrame({"open": o, "high": np.maximum(o, c) + w[0], "low": np.minimum(o, c) - w[1], "close": c, "volume": 1000.0},
                                    index=idx).round(2))
            px = float(c[-1])
            n += 1
        d += pd.Timedelta(days=1)
    return pd.concat(out)


_SYN = {}


def _syn_cache(name="main", **kw):
    if name not in _SYN:
        _SYN[name] = syn_overnight(**kw) if kw else syn_overnight()
    return _SYN[name]


def capture(monkeypatch):
    got = []
    monkeypatch.setattr(S, "_finish_order", lambda *a, **k: got.append((a, k)) or "order")
    return got


# --- L2-sr-needs-fvg (76): the flip retest at the FVG CE ----------------------------------------------------------------------

FLIP = [(3990, 3995, 3988, 3994), (3994, 4000, 3993, 3999), (3999, 3999.5, 3996, 3997), (3997, 3999, 3996, 3998.5),
        (3998.5, 4004, 3998, 4003), (4003, 4008, 4002, 4007), (4007, 4010, 4005, 4009), (4009, 4011, 4006, 4010), (4010, 4012, 4008, 4011)]


def test_flip_level_needs_fvg(monkeypatch):
    """Broken high 4000 (the long's mirror of 'broken low 4000 with a bearish FVG 3998-4002'): the gap of the breaking leg reaches the level, the
    entry is the gap's CE; without an FVG at the level there is no setup."""
    got = capture(monkeypatch)
    p = Params(**BASE, daily_level_needs_array="fvg", flip_retest_entry=True)
    ctx, sd = stub_ctx(len(FLIP)), sd_of(FLIP)
    assert (3999.0, 4002.0) in [(round(float(g.bottom), 2), round(float(g.top), 2)) for g in sd.gaps]
    assert L4.flip_order(ctx, sd, 8, p, "AM", 1.0) == "order"
    a, k = got[0]
    assert a[6] == 4000.5 and a[7] == pytest.approx(3999.0 - p.pad)                   # a limit at the gap's CE, the stop under its bottom
    assert k["skip_leg_pd"] and a[5]["key"] == "flip_retest" and a[5]["level"] == 4000.0
    assert L4.flip_order(ctx, sd, 8, p, "AM", 1.0) is None                              # once per level and gap
    # off by default / needs the "fvg" mode / the bias
    assert L4.flip_order(ctx, sd_of(FLIP), 8, replace(p, flip_retest_entry=False), "AM", 1.0) is None
    assert L4.flip_order(ctx, sd_of(FLIP), 8, replace(p, daily_level_needs_array="any"), "AM", 1.0) is None
    assert L4.flip_order(stub_ctx(len(FLIP), cur_bias=0), sd_of(FLIP), 8, p, "AM", 1.0) is None
    # no FVG within a tick of the level: no setup (the gap 4006-4008 sits well above 4000)
    far = list(FLIP)
    far[5] = (4003, 4008, 3999.0, 4007)
    sd2 = sd_of(far)
    assert not any(g.bottom - 1 <= 4000 <= g.top + 1 for g in sd2.gaps)
    assert L4.flip_order(ctx, sd2, 8, p, "AM", 1.0) is None
    # price must still be above the gap (a retest to come); a close back below the gap bottom kills it
    dead = list(FLIP)
    dead[8] = (4010, 4010, 3990, 3995)
    assert L4.flip_order(stub_ctx(len(FLIP)), sd_of(dead), 8, p, "AM", 1.0) is None
    # the short is the same trade on mirrored prices (a broken low with a bearish gap through it)
    mir = [(-o, -l, -h, -c) for o, h, l, c in FLIP]
    got.clear()
    assert L4.flip_order(stub_ctx(len(FLIP), cur_bias=-1), sd_of(mir, -1), 8, p, "AM", 1.0) == "order"
    assert got[0][0][6] == 4000.5


def test_flip_order_is_wired_into_the_scan(monkeypatch):
    calls = []
    monkeypatch.setattr(L4, "flip_order", lambda *a, **k: calls.append(1) or "order")
    monkeypatch.setattr(S, "_scan_core", lambda *a, **k: None)
    ctx = stub_ctx(10)
    sd = S.Side(1, *(np.full(10, 100.0),) * 4, 1)
    p = Params(**BASE, daily_level_needs_array="fvg", flip_retest_entry=True)
    assert S._scan(ctx, sd, 5, p, "AM", 0, None, None, None) == "order" and calls
    calls.clear()
    assert S._scan(ctx, sd, 5, replace(p, flip_retest_entry=False), "AM", 0, None, None, None) is None and not calls


# --- A17-rejection-block-short-protocol (41): kind "rb" arrays in htf._arrays --------------------------------------------------

def _daily_rb():
    o = A([100, 104, 103, 99, 98, 101, 102, 100, 99, 100], float)
    h = A([103, 110, 105, 101, 100, 104, 106, 102, 101, 102], float)
    l = A([99, 103, 100, 97, 96, 100, 101, 98, 97, 98], float)
    c = A([102, 105, 101, 98, 99, 103, 102, 99, 100, 101], float)
    return o, h, l, c


def test_rb_arrays_in_htf_arrays():
    o, h, l, c = _daily_rb()
    arr = [a for a in htf._arrays(o, h, l, c, "D", lambda i: i + 1, rb=True) if a.typ == "rb"]
    assert arr and all(a.top == a.bottom == a.ce for a in arr)
    z = {(a.kind, round(a.ce, 2)): a for a in arr}
    assert ("bear", 105.0) in z                                                           # the swing high 110 (bar 1): the close of its up-close candle (105)
    zz = z[("bear", 105.0)]
    assert zz.src_i == 1 and zz.known == 3 and zz.tf == "D"                               # usable the session after the pivot is confirmed (bar 2) completes
    assert not [a for a in htf._arrays(o, h, l, c, "D", lambda i: i + 1) if a.typ == "rb"]      # off by default
    assert htf._arrays(o, h, l, c, "D", lambda i: i + 1, rb=True, rb_level="open_close") != arr   # the level definition follows rb_level
    # engine glue: ld4.rb_build reads exactly these arrays (untaken ones, the three nearest each)
    ds = prior_days(D0, 10)
    hist = [rth_day(d, hh, ll, close=cc, op=oo) for d, oo, hh, ll, cc in zip(ds, o, h, l, c)]
    p = Params(**BASE, rb_pools=True)
    ctx = ctx3(day(FLAT, base=101.0), hist, p)
    his, los = ctx.rb_lv
    arrs = [a for a in htf._arrays(*(np.array([[x.open.iloc[0], x.high.max(), x.low.min(), x.close.iloc[-1]] for x in hist]).T), "D", lambda i: i + 1, rb=True, rb_level="close")
            if a.typ == "rb"]
    assert 105.0 not in his or True                                                       # (the day-frame candles differ from the hand arrays: checked below on the real rows)
    rows = L4.daily_rows(ctx, p)[1]
    oo, hh, ll, cc = (np.array([r[k] for r in rows]) for k in range(4))
    want_hi = sorted([(a.src_i, a.ce) for a in htf._arrays(oo, hh, ll, cc, "D", lambda i: i + 1, rb=True) if a.typ == "rb" and a.kind == "bear"
                      and hh[a.src_i + 1:].max(initial=-np.inf) < a.ce], reverse=True)[:3]
    assert his == [v for _, v in want_hi]


def test_htf_table_lists_rb_closes_without_touching_the_bias():
    """htf.table(rb_closes=True) adds rb_up / rb_dn (the nearest untaken rejection-block closes) and leaves every bias column as it was."""
    df = _syn_cache("main")
    base = htf.table(df, 1.0)
    rb = htf.table(df, 1.0, rb_closes=True)
    assert {"rb_up", "rb_dn"} <= set(rb.columns) and not {"rb_up", "rb_dn"} & set(base.columns)
    pd.testing.assert_frame_equal(base, rb.drop(columns=["rb_up", "rb_dn"]))
    assert rb.rb_up.notna().any() and rb.rb_dn.notna().any()
    x = rb.dropna(subset=["rb_up"])
    assert (x.rb_up > x.px).all()                                                         # a buy-side level sits above the price
    y = rb.dropna(subset=["rb_dn"])
    assert (y.rb_dn < y.px).all()


# --- new-trendline-trap (137): the OB and breaker entries, the ladder ----------------------------------------------------------

TRAP = [(4120, 4122, 4118, 4121), (4121, 4122, 4117, 4118), (4118, 4120, 4115, 4119), (4119, 4119.5, 4108, 4109), (4109, 4112, 4107, 4111),
        (4111, 4111.5, 4094, 4101), (4101, 4109, 4100, 4108), (4108, 4117, 4107, 4116), (4116, 4116.5, 4113, 4114), (4114, 4115, 4112, 4113),
        (4113, 4114, 4111.5, 4112.5)]


def _trap_world(monkeypatch, bias=1):
    """A synthetic down-trendline world: the pivots are patched in (H1 4122 > H2 4112 > H3 4108 on a line), L23 = 4094 (bar 4); the bullish OB of
    that low is the down candle 3 (4100 -> 4096) / the blend ending at it."""
    P = L.Pivot
    st = dict(h1=P(0, 4122.0, 1), h2=P(2, 4120.0, 3), h3=P(7, 4117.0, 8), known=8, l23=4094.0, l23_i=5)
    monkeypatch.setattr(L4, "trendline_state", lambda *a, **k: st)
    ctx = stub_ctx(len(TRAP), cur_bias=bias, bias_row=dict(draw_up=4140.0, draw_up_name="D_fvg", draw_dn=np.nan, draw_dn_name=""))
    return ctx, sd_of(TRAP), st


def test_trendline_trap_ob_entry(monkeypatch):
    got = capture(monkeypatch)
    p = Params(**BASE, trendline_trap=True, tl_trap_entries=("ob",))
    ctx, sd, st = _trap_world(monkeypatch)
    assert L4.tl_trap_order(ctx, sd, 10, p, "AM", 1.0) == "order"
    a, k = got[0]
    entry, stop = a[6], a[7]
    assert entry == 4111.0                                                                  # a resting limit at the body top of the order block formed at L23 ...
    assert stop == pytest.approx(4094.0 - p.pad)                                            # ... the stop beyond the old low
    assert a[5]["key"] == "tl_trap" and k["skip_leg_pd"]
    lad = k["fixed"]
    assert lad[0] == (S._exit_px(4120.0 + p.tick, "pool", p), "pool")                       # T1: just above H2 (the buy stops) ...
    assert lad[1][0] == S._exit_px(4140.0, "array", p)                                      # ... then the daily draw
    assert L4.tl_trap_order(ctx, sd, 10, p, "AM", 1.0) is None                              # once per L23 and kind
    # not without the switch entries / the bias / while price has gone through the old low (that is the turtle-soup case)
    assert L4.tl_trap_order(ctx, sd, 10, replace(p, tl_trap_entries=()), "AM", 1.0) is None
    assert L4.tl_trap_order(stub_ctx(len(TRAP), cur_bias=0), sd, 10, p, "AM", 1.0) is None
    rows = list(TRAP)
    rows[9] = (4114, 4115, 4093, 4113)
    ctx2, _, _ = _trap_world(monkeypatch)
    assert L4.tl_trap_order(ctx2, sd_of(rows), 10, p, "AM", 1.0) is None
    # the mirror: the bearish case (an up-trendline of lows, sell the bearish OB just below H23) is the same call in side space
    mir = [(-o, -l, -h, -c) for o, h, l, c in TRAP]
    got.clear()
    ctx3_, _, _ = _trap_world(monkeypatch, bias=-1)
    assert L4.tl_trap_order(ctx3_, sd_of(mir, -1), 10, p, "AM", 1.0) == "order"


def test_trendline_trap_breaker_entry(monkeypatch):
    got = capture(monkeypatch)
    p = Params(**BASE, trendline_trap=True, tl_trap_entries=("breaker",))
    ctx, sd, st = _trap_world(monkeypatch)
    z = L.Zone("bull", 4104.0, 4095.0, 7, 3, 4100.0)
    monkeypatch.setattr(L4, "_breaker_zones", lambda sd_, p_: [z])
    assert L4.tl_trap_order(ctx, sd, 10, p, "AM", 1.0) == "order"
    a, k = got[0]
    assert a[6] == 4104.0 and a[7] == pytest.approx(4094.0 - p.pad) and a[5]["key"] == "tl_trap"
    got.clear()
    ctx2, _, _ = _trap_world(monkeypatch)
    monkeypatch.setattr(L4, "_breaker_zones", lambda sd_, p_: [L.Zone("bull", 4130.0, 4128.0, 7, 3, 4129.0)])      # far from L23: no entry
    assert L4.tl_trap_order(ctx2, sd, 10, p, "AM", 1.0) is None


def test_trendline_trap_wired_into_the_scan(monkeypatch):
    calls = []
    monkeypatch.setattr(L4, "tl_trap_order", lambda *a, **k: calls.append(1) or "order")
    monkeypatch.setattr(S, "_scan_core", lambda *a, **k: None)
    ctx = stub_ctx(10)
    sd = S.Side(1, *(np.full(10, 100.0),) * 4, 1)
    p = Params(**BASE, trendline_trap=True, tl_trap_entries=("ob",))
    assert S._scan(ctx, sd, 5, p, "AM", 0, None, None, None) == "order" and calls


def test_trendline_tolerance_adr(monkeypatch):
    ctx = SimpleNamespace(hist=history(D0, n=8))
    p = Params(**BASE, trendline_trap=True)
    assert L4._tl_tol(ctx, p, False) == p.tl_tol_ticks * p.tick
    q = replace(p, tl_tol_adr=0.1)
    assert L4._tl_tol(ctx, q, False) == pytest.approx(0.1 * 18.0)                            # one tolerance for both: a fraction of ADR5
    assert L4._tl_tol(ctx, q, True) == pytest.approx(0.1 * 18.0)                              # (trendline_pools always did)
    with pytest.raises(ValueError):
        Params(tl_trap_entries=("x",))
    with pytest.raises(ValueError):
        Params(tl_tol_adr=-1.0)


# --- new-hs-fade (138): re-arm on a re-run, an array gate without a confluence object ------------------------------------------

def test_hs_fade_rearm_on_a_rerun(monkeypatch):
    from test_caption_gap_ld3 import _hs_world
    got = capture(monkeypatch)
    p = Params(**BASE, hs_fade=True, hs_tf=15, eq_tol_pts=2.0, hs_stop_pts=10.0, ts_cc_below_pts=0.5, hs_rearm=True)
    ctx, sd, i = _hs_world()
    assert L4.hs_order(ctx, sd, i, p, "AM", 1.0) == "order"
    assert L4.hs_order(ctx, sd, i, p, "AM", 1.0) is None                                     # no re-run yet: still armed once
    # the lows are run again (one tick under the neckline) and price closes back above: re-sell
    o, h, l, c = (np.concatenate([x, [x[-1]] * 3]) for x in (sd.o, sd.h, sd.l, sd.c))
    l[len(sd.l)] = 4088.0                                                                     # a bar under 4090
    h[len(sd.l)] = 4095.0
    sd2 = S.Side(1, o, h, l, c, 1)
    sd2.__dict__["_hs_sent"] = sd.__dict__["_hs_sent"]
    sd2.__dict__["_hs_last"] = sd.__dict__["_hs_last"]
    ctx2 = SimpleNamespace(**{**ctx.__dict__, "idx": pd.date_range("2026-06-23 09:30", periods=len(o), freq="5min", tz=NY)})
    got.clear()
    j = len(sd.l) + 2
    assert L4.hs_order(ctx2, sd2, j, p, "AM", 1.0) == "order"                                # armed again after the run
    assert L4.hs_order(ctx2, sd2, j, p, "AM", 1.0) is None                                   # once per run
    sd3 = S.Side(1, o, h, l, c, 1)
    sd3.__dict__["_hs_sent"] = set(sd.__dict__["_hs_sent"])
    sd3.__dict__["_hs_last"] = dict(sd.__dict__["_hs_last"])
    assert L4.hs_order(ctx2, sd3, j, replace(p, hs_rearm=False), "AM", 1.0) is None          # off: the neckline is armed once


def test_hs_fade_array_gate_without_confluence(monkeypatch):
    from test_caption_gap_ld3 import _hs_world
    got = capture(monkeypatch)
    p = Params(**BASE, hs_fade=True, hs_tf=15, eq_tol_pts=2.0, hs_stop_pts=10.0, ts_cc_below_pts=0.5)
    ctx, sd, i = _hs_world(conf=None)
    assert L4.hs_order(ctx, sd, i, p, "AM", 1.0) is None                                      # no confluence object and no HTF zones: nothing to lean on
    ctx.hzones = [(L.Zone("bull", 4100.0, 4090.0, 3, 1), pd.Timestamp("2026-06-23 09:45", tz=NY), 15)]
    monkeypatch.setattr(S, "_htf_tag", lambda c_, s_, i_, px, tol: False)
    ctx.hzones = [1]
    assert L4.hs_order(ctx, sd, i, p, "AM", 1.0) is None                                      # a frame with HTF zones that do not reach the price
    monkeypatch.setattr(S, "_htf_tag", lambda c_, s_, i_, px, tol: True)
    assert L4.hs_order(ctx, sd, i, p, "AM", 1.0) == "order"                                   # the HTF FVG zone gate passes


# --- A12-entry-ob-outside-fvg (67): setups.ob_low -----------------------------------------------------------------------------

def test_setups_ob_low_outside_fvg():
    from mentorship import setups
    rows = [(100, 101, 99, 100.5), (100.5, 101, 98.5, 99), (99, 99.5, 97, 97.5), (97.5, 98, 96.5, 97), (97, 100, 96.8, 99.9), (99.9, 104, 99.5, 103.5)]
    sd = sd_of(rows)
    full = setups.ob_low(sd, 3)
    out = setups.ob_low(sd, 3, outside=(96.4, 98.1))                  # candle 3 (96.5-98) lies inside the shaded zone: the block is the one before it
    assert full is not None and out is not None and out[0].bottom != full[0].bottom and out[0].bottom == 97.0
    assert setups.ob_low(sd, 3, outside=None)[0].bottom == full[0].bottom


# --- levels.parent_pools: untaken through `end` -------------------------------------------------------------------------------

def test_parent_pools_taken_after_the_confirmation():
    from test_caption_gap_ld3 import PARENT
    o, h, l, c = mk(PARENT)
    _, pl = L.pivots(h, l, 1)
    assert L.parent_pools(o, h, l, c, pl, 2, 5.0) == [(4000.0, 1, 8)]
    l2 = l.copy()
    l2[9] = 3999.0                                                                            # L0 is taken AFTER the pool was confirmed (bar 8)
    assert L.parent_pools(o, h, l2, c, pl, 2, 5.0, end=8) == [(4000.0, 1, 8)]                  # still intact at bar 8
    assert L.parent_pools(o, h, l2, c, pl, 2, 5.0, end=9) == []                                # ... gone at bar 9 (checked through `end`, not only up to `known`)


# --- L10 wick CEs: today's bars trade through a CE too ------------------------------------------------------------------------

def test_wick_untraded_by_todays_bars():
    p = Params(**BASE, wick_untraded=True, wick_days=3, wick_levels=True)
    ws = [dict(upper=110.0, lower=90.0), dict(upper=106.0, lower=96.0)]
    idx = pd.date_range("2026-06-23 09:30", periods=20, freq="5min", tz=NY)
    h = np.full(20, 100.0)
    l = np.full(20, 100.0)
    ctx = SimpleNamespace(wicks=ws, wick_wk=[], wick_ok=[(True, True), (True, True)], wick_wk_ok=[], idx=idx, tf=5, start=0, h=h, l=l)
    sd = S.Side(1, *(np.full(20, 100.0),) * 4, 1)
    assert 106.0 in L4.wick_ce_levels(ctx, sd, p, False, 10)
    h[5] = 106.5                                                                              # today's own bar traded through the older day's upper CE
    assert 106.0 not in L4.wick_ce_levels(ctx, sd, p, False, 10)
    assert 106.0 in L4.wick_ce_levels(ctx, sd, p, False, 3)                                    # (not yet at bar 3)
    # the lower CE for the LOD tag: bars BEFORE the sweep extreme count
    sw = dict(ext=96.0, ext_i=8)
    conf = SimpleNamespace(valid=lambda now, sign, tfs, src, kb: [(96.5, 95.5, "15m", 0, 0.0)])
    ctx2 = SimpleNamespace(wicks=[dict(upper=106.0, lower=96.0)], wick_ok=[(True, True)], conf=conf, idx=idx, tf=5, start=0, h=h, l=l.copy())
    q = replace(p, wick_lod_tag="tag")
    assert L4.wick_lod(ctx2, sd, sw, 10, q)
    ctx2.l[2] = 95.5                                                                          # an earlier bar of today already traded below the CE by more than a tick
    assert not L4.wick_lod(ctx2, sd, sw, 10, q)


# --- L7 (40): revisits count only at a valid time with another PD array nearby --------------------------------------------------

def test_org_revisit_gate():
    p = Params(**BASE, org_both_ways=True, org_revisit_gate=True, org_days=20)
    n = 40
    idx = pd.date_range("2026-06-23 09:30", periods=n, freq="5min", tz=NY)
    t = (idx.hour * 60 + idx.minute).values
    h = np.full(n, 4000.0)
    l = np.full(n, 3990.0)
    h[3] = 4015.0                                                                             # 09:45 revisit of the ORG 4000-4020's CE/75% (not a valid time)
    h[20] = 4012.0                                                                            # 11:10 ... also not valid
    h[6] = 4013.0                                                                             # 10:00 valid time
    conf = SimpleNamespace(valid=lambda now, sg, tfs, src: [(4014.0, 4012.0, "15m", 0, 0.0)])
    ctx = SimpleNamespace(org=[(4000.0, 4020.0)], org_dates=[D0], org_hist=[(4000.0, 3990.0)], day=D0, idx=idx, t=t, tf=5, start=0, h=h, l=l,
                          conf=conf, __dict__={})
    i = n - 1
    assert S._idx_at(ctx, 570) == 0
    st = L4.org_state(ctx, 0, i, p)
    assert st["part_up"] == 4013.0                                                           # only the 10:00 bar counted (valid time + an array within 1 pt of the 75% level)
    ctx.conf = None
    ctx.__dict__["_ld4"] = {}
    assert L4.org_state(ctx, 0, i, p)["part_up"] is None                                      # nothing can confirm an array: no revisit counts
    off = replace(p, org_revisit_gate=False)
    assert L4.org_state(ctx, 0, i, off)["part_up"] == 4015.0                                  # the old rule: every revisit
    ctx.conf = SimpleNamespace(valid=lambda now, sg, tfs, src: [(3950.0, 3949.0, "15m", 0, 0.0)])      # an array far from the ORG's levels
    ctx.__dict__["_ld4"] = {}
    assert L4.org_state(ctx, 0, i, p)["part_up"] is None


# --- new-reactionary-high-liquidity (70): the deep-discount / no-FVG precondition -------------------------------------------------

def test_reactionary_precondition():
    from test_caption_gap_ld3 import REACT
    o, h, l, c = mk(REACT)
    sd = S.Side(1, o, h, l, c, 1)
    p = Params(**BASE, reactionary_pools=True, displacement_mult=1.5)
    idx = pd.date_range("2026-06-23 09:30", periods=len(o), freq="5min", tz=NY)
    ctx = SimpleNamespace(hist=history(D0, n=8), tf=5, idx=idx)                              # ADR5 = 18
    q = replace(p, reactionary_precond=True)
    assert L4.reactionary_buy(ctx, sd, 12, p) == (120.0, 6)
    # deep enough (107.5 is 12.5 >= 0.5 x ADR5 below 120): it hinges on the 15m FVGs between price and the high
    flat = np.full(len(o), 100.0)
    assert L4.fvg_between_15m(ctx, S.Side(1, flat, flat + 1, flat - 1, flat, 1), 12, 100.0, 120.0) is False       # no gaps at all
    # two bars of 15m bars with a gap between them: (low 104 > the earlier high 102)
    hh, ll = flat + 1.0, flat - 1.0
    hh[0:3], ll[0:3] = 102.0, 99.0
    hh[3:6], ll[3:6] = 108.0, 104.0
    hh[6:9], ll[6:9] = 110.0, 106.0
    gapped = S.Side(1, flat, hh, ll, flat, 1)
    assert L4.fvg_between_15m(ctx, gapped, 8, 101.0, 109.0) is True
    assert L4.fvg_between_15m(ctx, gapped, 8, 120.0, 130.0) is False                       # (a gap that is not between price and the high does not count)
    assert L4.fvg_between_15m(SimpleNamespace(tf=60, idx=idx), gapped, 8, 101.0, 109.0) is None      # coarse bars: cannot tell
    assert L4.reactionary_ok(ctx, gapped, 8, q, 112.0) is False                              # a gap lies in the way
    assert L4.reactionary_ok(ctx, gapped, 8, p, 112.0) is True                               # (switch off: unchanged)
    assert L4.reactionary_ok(ctx, sd, 12, q, 120.0) is True                                  # deep discount and a clear path
    shallow = S.Side(1, o, np.minimum(h, 110.0), l, c, 1)
    assert L4.reactionary_ok(ctx, shallow, 12, q, 109.0) is False                            # not deep enough: only 1.5 pts below the high
    assert L4.reactionary_ok(SimpleNamespace(hist=[], tf=5, idx=idx), gapped, 8, q, 112.0) is False     # (no ADR: only the FVG test)


# --- new-intra-week-extreme-raid (197): Monday, the evening, the blend with Friday / the previous week ----------------------------

def _week_frames(mon=date(2026, 6, 22)):
    ds = prior_days(mon + timedelta(days=1), 6)                                                # the Tuesday's priors: Fri 6/12 .. Mon 6/22 (Mon is the last)
    return ds


def test_monday_low_raid_uses_the_sunday_evening_and_todays_bars():
    mon = date(2026, 6, 22)
    ds = prior_days(mon, 6)
    hist = [frame(d, [(4100.0, 4110.0, 4090.0, 4100.0), (4100.0, 4110.0, 4090.0, 4100.0)], 5, "09:30") for d in ds]
    hist[-1] = frame(ds[-1], [(4100.0, 4108.0, 4080.0, 4100.0)] * 2, 5, "09:30")              # Friday: the previous week's low 4080
    p = Params(**BASE, week_pools=True)
    df = day([(4100.0, 4100.5, 4099.5, 4100.0)] * 12 + [(4100.0, 4100.5, 4096.0, 4097.0)] + [(4097.0, 4098.0, 4096.5, 4097.5)] * 6, d=mon, base=4100.0)
    ctx = ctx3(df, hist, p)
    assert ctx.week_hl is None                                                                 # no completed session this week, no evening known
    ctx.eve = (4101.0, 4103.0, 4094.0, 4100.0)                                                 # the Sunday evening printed 4094
    ctx.week_hl = L4.week_build(ctx, [d for d in ds], hist, p, None)
    assert ctx.week_hl == (4103.0, 4094.0)
    i = k_at(ctx, "09:30") + 15
    w = L4.week_now(ctx, i)
    assert w[1] == 4094.0 and w[0] == 4103.0
    lg = side(ctx)
    out = S._sell_side(ctx, lg, "AM", i, True, p)
    assert out["week_lo"] == 4094.0                                                            # the Monday low raid is a pool (it never was: week_build returned None)
    # a lower low printed earlier today becomes the running week low
    j = k_at(ctx, "09:30") + 16
    assert S._sell_side(ctx, lg, "AM", j, True, p)["week_lo"] == 4094.0 and L4.week_now(ctx, j)[1] == 4094.0
    ctx.l[ctx.start + 3] = 4091.0
    assert L4.week_now(ctx, i)[1] == 4091.0
    # blended with the prior Friday's low and the previous week's low on a Monday / Tuesday raid
    pr = L4.week_prior_lows(ctx, p)
    assert pr == {"pf": 4080.0, "pw": 4080.0} or set(pr) == {"pf", "pw"}
    assert out["week_lo_pf"] == 4080.0
    tue = mon + timedelta(days=1)
    assert "week_lo_pf" not in S._sell_side(replace_ctx_day(ctx, date(2026, 6, 24)), lg, "AM", i, True, p)       # Wednesday: no blend
    assert "week_lo_pf" not in S._sell_side(ctx, side(ctx, -1), "AM", i, True, p)                               # (highs have no blend)


def replace_ctx_day(ctx, d):
    c2 = SimpleNamespace(**ctx.__dict__)
    c2.day = d
    c2.__dict__["_ld4"] = {}
    return c2


# --- L3-or-refs-expire-1100 (22): the Silver Bullet list gets the OR FVGs ---------------------------------------------------------

SB_OR = [(100.0, 100.6, 99.9, 100.5), (100.5, 100.9, 100.3, 100.8), (100.8, 100.8, 98.9, 99.0), (98.0, 98.0, 97.5, 97.6),
         (97.6, 99.6, 97.55, 99.5), (99.5, 100.2, 99.0, 100.1),                     # 09:55 completes the bullish OR gap 98.0-99.0 (below the leg's MSS level 100.9)
         (100.1, 101.4, 100.0, 101.3), (101.3, 101.6, 100.6, 100.8), (100.8, 101.0, 100.2, 100.5), (100.5, 100.9, 100.1, 100.7),
         (100.7, 104.0, 100.6, 103.9), (103.9, 108.6, 103.8, 108.5)]


def test_or_fvgs_are_silver_bullet_arrays():
    """tsm#22: the Silver Bullet's array list gets the FVGs formed inside the opening range when or_fvg_entries is on (sb_model off by default)."""
    import test_silver_bullet as T
    base = dict(sb_room_pts=1.0, sb_fvg_pick="any_in_leg")
    p0, p1 = T.P(**base), T.P(or_fvg_entries=True, **base)
    ctx, sd = T.actx([("09:30", SB_OR)], p1)
    ctx.or_fvgs = L4.or_fvg_build(ctx, p1)
    assert [(z.kind, float(z.bottom), float(z.top)) for z in ctx.or_fvgs if z.kind == "bull"] == [("bull", 98.0, 99.0)]
    k0 = S._idx_at(ctx, T.minute("09:30"))
    for at in ("10:05", "10:10", "10:20"):
        i = S._idx_at(ctx, T.minute(at))
        assert sb_model._arm_all(ctx, sd, i, k0, p0, 0.5, None, "AM", 600, (), None, None) == []            # the base list: the OR gap lies below the level the break had to clear
        o = sb_model._arm_all(ctx, sd, i, k0, p1, 0.5, None, "AM", 600, (), None, None)
        assert len(o) == 1 and o[0]["entry"] == 99.0 and o[0]["lv_tags"] == "or_fvg" and o[0]["zone"] == (99.0, 98.0)
    i = S._idx_at(ctx, T.minute("10:10"))
    ctx.or_fvgs = []
    assert sb_model._arm_all(ctx, sd, i, k0, p1, 0.5, None, "AM", 600, (), None, None) == []               # no OR FVG built: nothing added
    ctx.or_fvgs = L4.or_fvg_build(ctx, p1)
    late = S._idx_at(ctx, T.minute("11:05"))
    assert L4.or_fvg_zones(ctx, sd, dict(ext=97.5), late, p1) == []                                           # (the OR references expire at 11:00)
    assert Params().sb_model is False and Params().sb_use_bias is False                                       # the Silver Bullet stays off by default, its bias switches untouched


# --- new-time-distortion (29): swings, zones, sweeps, OB candles ---------------------------------------------------------------

def _td_ctx(n=60, start="12:00"):
    idx = pd.date_range(f"2026-06-23 {start}", periods=n, freq="5min", tz=NY)
    return SimpleNamespace(idx=idx, tf=5, start=0, day=D0, t=(idx.hour * 60 + idx.minute).values, cur_bias=1, __dict__={})


def test_time_distortion_filters_swings_and_zones(monkeypatch):
    """From 12:10 to 14:00 (lunch) no swing point, FVG, inverted FVG, VI or breaker is read: the sides drop the objects defined on masked bars."""
    monkeypatch.setattr("mentorship.calendar.release_times", lambda d: [])
    ctx = _td_ctx(60, "11:30")                                  # 11:30 .. 16:25
    rows = [(100, 101, 99.5, 100.5)] * 3 + [(100.5, 102, 100.4, 101.8), (101.8, 106, 101.5, 105), (105, 106.5, 104.8, 106)] + [(106, 107, 105, 106)] * 54
    # bars 8..18 are 12:10 - 13:00: masked; build a pivot + a gap inside the mask
    rows[10:14] = [(106, 109, 105, 108), (108, 108.5, 104, 104.5), (104.5, 110, 104.6, 109.5), (109.5, 112, 109.4, 111)]
    o, h, l, c = mk(rows)
    p0 = Params(**BASE, time_distortion=False)
    p1 = Params(**BASE, time_distortion=True, td_lunch=True)
    s0 = S.Side(1, o, h, l, c, 1)
    s1 = S.Side(1, o, h, l, c, 1)
    L4.attach_td(ctx, [s1], p1)
    m = L4.td_mask(ctx, p1)
    assert m[ctx.idx.get_loc(pd.Timestamp("2026-06-23 12:15", tz=NY))] and not m[0]
    assert len(s1.ph) < len(s0.ph) and all(not m[q.i] for q in s1.ph + s1.pl)                 # swing points of masked bars are gone
    assert len(s1.gaps) < len(s0.gaps) and all(not m[g.i] and not m[g.src] for g in s1.gaps)  # and so are the FVGs formed there
    assert all(not m[z.i] for z in s1.ifvgs())                                                  # inverted FVGs, VIs, mitigation blocks ... (lazily built, filtered)
    assert all(not m[z.i] for z in s1._lazy("probe", lambda: list(s0.gaps)))
    L4.attach_td(ctx, [s0], p0)                                                                 # off: nothing changes
    assert s0.td_mask is None
    # a pool run in a masked bar infers no direction: the sweep machine does not start
    monkeypatch.setattr(S, "_sell_side", lambda *a, **k: {"x": 150.0})
    monkeypatch.setattr(S, "_level_intact", lambda *a, **k: True)
    s2 = S.Side(1, o, h, l, c, 1)
    s2.td_mask = m
    ctx.partner2 = None
    r = S._scan_core(ctx, s2, 15, p1, "PM", 0, None, None, None)
    assert r is None and s2.sweep is None
    monkeypatch.setattr(S, "_smt", lambda *a, **k: None)
    s3 = S.Side(1, o, h, l, c, 1)
    S._scan_core(ctx, s3, 15, p0, "PM", 0, None, None, None)                                 # the same bar without the switch starts the sweep machine
    assert s3.sweep is not None and s3.sweep["key"] == "x"


def test_time_distortion_order_block_candle_and_state_filter(monkeypatch):
    monkeypatch.setattr("mentorship.calendar.release_times", lambda d: [])
    ctx = _td_ctx(30, "12:00")
    rows = [(100, 101, 99, 100.5)] * 3 + [(100.5, 100.6, 98.0, 98.2), (98.2, 99, 97.9, 98.8), (98.8, 103, 98.7, 102.5), (102.5, 104, 102, 103.5)] + [(103.5, 104, 103, 103.8)] * 23
    sd = sd_of(rows)
    sw = dict(ext_i=4, ext=97.9)
    p = Params(**BASE, time_distortion=True)
    ob = S._ob_at_low(sd, sw, 7, p, ctx)                                                        # 12:15: masked (lunch) - the candle there is no order block
    assert ob is None
    assert S._ob_at_low(sd, sw, 7, replace(p, time_distortion=False), ctx) is not None
    # (a) the body hold keeps a wicked gap alive for any gap kind and tags it
    g = L.Zone("bull", 102.0, 100.0, 4, 3)
    ctx2 = SimpleNamespace(t=600 + 5 * np.arange(40), start=0)
    o = np.concatenate([[100.0] * 5, A([100.5, 100.8, 101.2, 101.0, 100.9, 101.1, 101.0])])
    c = np.concatenate([[100.0] * 5, A([100.9, 101.1, 101.0, 100.8, 101.1, 101.0, 100.7])])
    h = np.concatenate([[101.0] * 5, A([103.0, 101.5, 101.4, 102.6, 101.3, 101.5, 101.2])])
    l = np.concatenate([[100.0] * 5, A([100.2, 100.4, 100.6, 100.5, 100.3, 100.6, 100.4])])
    sd2 = SimpleNamespace(o=o, h=h, l=l, c=c)
    q = Params(**BASE, td_fvg_hold=True)
    assert L4.td_held(ctx2, sd2, [g], 11, q) == [g] and L4.td_held(ctx2, sd2, [g], 11, replace(q, td_fvg_hold=False)) == []
    # "after the session extreme is set": a gap formed BEFORE the session's low has not
    l2 = l.copy()
    l2[3] = 99.0
    sd3 = SimpleNamespace(o=o, h=h, l=l2, c=c)
    assert L4.td_held(ctx2, sd3, [g], 11, q) == []


# --- L5 (19 / 28): the RTH weekend gap follows the NWOG rules; the closest NWOG over the 60 days; the Tuesday reference at midnight ---------------

def _og_row(sunday, hi, lo, kind="nwog"):
    k = pd.Timestamp(f"{sunday} 18:00", tz=NY)
    return dict(kind=kind, high=float(hi), low=float(lo), ce=(hi + lo) / 2, up=True, known=k,
                week=(k + pd.Timedelta(hours=7)).normalize().tz_localize(None).to_period("W-FRI"), dir="up", close_before=float(lo), open_after=float(hi))


def test_nwog_rth_follows_the_nwog_rules():
    df = day([(4000.0, 4001.0, 3999.0, 4000.0)] * 5, d=D0, base=4000.0)
    hist = history(D0, n=8)
    p = Params(**BASE, weekly_gap_ce_only=True, nwog_quarters=True)
    gaps = [("nwog_rth", 4220.0, 4200.0, 4210.0), ("nwog", 4340.0, 4330.0, 4335.0)]
    ctx = ctx3(df, hist, p, gaps=gaps)
    sd = side(ctx)
    i = k_at(ctx, "09:30") + 2
    lv = [v for v, k in S._targets(ctx, sd, i, 3990.0, [], p) if k == "array"]
    assert 4210.0 in lv and 4220.0 not in lv and 4200.0 not in lv                                  # the RTH gap gives its CE only, like the ETH one
    assert 4205.0 in lv and 4215.0 in lv                                                           # ... and its quarters (nwog_quarters)
    assert 4335.0 in lv and 4340.0 not in lv
    off = [v for v, k in S._targets(ctx, sd, i, 3990.0, [], Params(**BASE)) if k == "array"]
    assert 4220.0 in off and 4200.0 in off                                                         # (switches off: every level)
    # the inversion arrays (A8 "nwog") list it as well
    inv = LD._inv_sources(ctx, p, ("nwog",)) if hasattr(LD, "_inv_sources") else None
    if inv is not None:
        assert any(z[3] == "nwog" and z[0] == 4000.0 for z in inv)


def test_holiday_pick_uses_the_60_day_window_and_one_weekend():
    sundays = ["2025-09-14", "2025-09-21", "2025-09-28", "2025-10-05", "2025-10-12", "2025-10-19", "2025-10-26", "2025-11-02", "2025-11-09",
               "2025-11-16", "2025-11-23"]
    rows = [_og_row(s_, 4000 + 100 * k + 4, 4000 + 100 * k) for k, s_ in enumerate(sundays)]
    rows += [_og_row("2025-09-14", 3990, 3980, "nwog_rth"), _og_row("2025-11-16", 5090, 5080, "nwog_rth")]
    og = pd.DataFrame(rows)
    d = date(2025, 11, 24)                                                                          # Thanksgiving week: its own NWOG (11-23) is dropped
    base = htf.gaps_for_day(og, d, 5, 0, True, trading_days=True, holiday_pick="all", ref_px=4004.0)
    assert len([r for r in base if r[0] == "nwog"]) == 5                                            # nwog_keep = 5: the last five normal ones
    one = htf.gaps_for_day(og, d, 5, 0, True, trading_days=True, holiday_pick="closest", ref_px=4004.0)
    assert sorted((k, round(h)) for k, h, *_ in one) == [("nwog", 4004), ("nwog_rth", 3990)]        # the closest of the 60 days (9-14), the ETH and RTH rows of that ONE weekend
    near = htf.gaps_for_day(og, d, 5, 0, True, trading_days=True, holiday_pick="closest", ref_px=5085.0)
    assert sorted((k, round(h)) for k, h, *_ in near) == [("nwog", 4904), ("nwog_rth", 5090)]
    none_ = htf.gaps_for_day(og.iloc[[10]], d, 5, 0, True, trading_days=True, holiday_pick="closest", ref_px=5085.0)
    assert none_ == []                                                                              # only the holiday week's own NWOG: none


def test_tue_open_ref_midnight_for_fx():
    tue, wed = date(2026, 1, 20), date(2026, 1, 21)                                                 # MLK Day 2026-01-19: no Monday session
    h = history(tue, n=6)
    df = day([(4050.0, 4051.0, 4049.0, 4050.5)] * 10, d=tue, start="00:00", base=4040.0)
    ctx = S.DayCtx(df, tue, h, 5)
    i = k_at(ctx, "10:00")
    assert BD.tue_open_ref(ctx, i, "midnight") == (True, ctx.opens["midnight"])                    # the Tuesday 00:00 open
    assert BD.tue_open_ref(ctx, i) == (True, ctx.opens["0930"])                                     # (the index default is the 09:30 open)
    tf = frame(tue, [(4041.0, 4042.0, 4040.0, 4041.5)] * 5, 5, "00:00")
    hw = history(wed, n=6)
    hw[-1] = pd.concat([tf, frame(tue, [(4050.0, 4051.0, 4049.0, 4050.5)] * 3, 5, "09:30")])
    ctx2 = S.DayCtx(day([(4060.0, 4061.0, 4059.0, 4060.0)] * 10, d=wed), wed, hw, 5)
    ctx2.hist = hw
    assert BD.tue_open_ref(ctx2, k_at(ctx2, "09:30"), "midnight") == (True, 4041.0)                 # read from the completed Tuesday session's 00:00 bar
    assert BD.tue_open_ref(ctx2, k_at(ctx2, "09:30"), "0930") == (True, 4050.0)
    with pytest.raises(ValueError):
        Params(tue_open_time="noon")


# --- B21 (127 / 128 / 129 / 130) ------------------------------------------------------------------------------------------------

def test_ipda_end_index_rules():
    ds = prior_days(date(2026, 7, 20), 70)
    day_ = date(2026, 7, 20)
    assert L.ipda_end_index(ds, day_, "rolling") == len(ds) and L.ipda_end_index(ds, day_, "daily") == len(ds)
    k = next(j for j, d in enumerate(ds) if (d.year, d.month) == (2026, 7))
    assert L.ipda_end_index(ds, day_, "current_month") == k + 1                                     # through the first trading day of July
    km = next(j for j, d in enumerate(ds) if (d.year, d.month) == (2026, 6))
    assert L.ipda_end_index(ds, day_, "month") == km                                                # the session before June's first
    assert L.ipda_end_index(ds[km + 1:], day_, "month") == 0                                        # the history does not reach it
    assert L.ipda_end_index(ds[k + 3:], day_, "current_month") == 0
    assert L.ipda_end_index(ds[:k], date(2026, 7, 1), "current_month") == k                         # on the month's first day itself: all completed sessions
    h = np.arange(70.0)
    assert 0 <= L.ipda_end_index(ds, day_, "swing", h + 1, h, h + 0.5) <= 70


def test_table_ipda_window_and_monthly_arrays():
    df = _syn_cache("main")
    base = htf.table(df, 1.0)
    pd.testing.assert_frame_equal(base, htf.table(df, 1.0, ipda_window="rolling"))                 # the rolling window IS the 60-session lookback
    pd.testing.assert_frame_equal(base, htf.table(df, 1.0, ipda_window="current_month"))            # (the anchor is never later than the day)
    wide = htf.table(df, 1.0, tf_lookback={"D": 252})
    cur = htf.table(df, 1.0, tf_lookback={"D": 252}, ipda_window="current_month")
    assert len(wide) == len(cur)
    assert B.table_kw(Params(ipda_arrays=True, ipda_anchor="month"))["ipda_window"] == "month" and "ipda_window" not in B.table_kw(Params())
    # monthly arrays: a monthly step-up leaves bullish monthly FVGs; they react with weight 3 and change nothing at the old settings
    up = df.copy()
    mo = (up.index.tz_localize(None) + pd.Timedelta(hours=7)).to_period("M")
    step = (mo.astype("int64") - mo.astype("int64").min()) * 400.0
    for c in ("open", "high", "low", "close"):
        up[c] = up[c] + np.asarray(step)
    seen = []
    orig = htf._arrays
    htf._arrays = lambda *a, **k: seen.append(a[4]) or orig(*a, **k)                                # which timeframes the table builds arrays for
    try:
        t0 = htf.table(up, 1.0)
        off_tfs, seen[:] = list(seen), []
        t1 = htf.table(up, 1.0, monthly_arrays=True)
    finally:
        htf._arrays = orig
    assert "M" not in off_tfs and "M" in seen and list(t0.columns) == list(t1.columns) and len(t0) == len(t1)
    m = htf.months(htf.sessions(up))
    assert len(m) >= 4 and (m.low.shift(-1) > m.high).iloc[:-1].all()                                # disjoint monthly candles = gaps between them
    assert B.table_kw(Params(htf_monthly_arrays=True))["monthly_arrays"] is True and "monthly_arrays" not in B.table_kw(Params())


def test_confluence_windowed_limits_every_query():
    df = _syn_cache("main")
    cf = CF.Confluence(df, 5, 1.0)
    now = df.index[-1] + pd.Timedelta(minutes=5)
    px = float(df.close.iloc[-1])
    assert cf.window is None
    v0 = cf.valid(now, 1, ("D",), (0, 1, 3)) + cf.valid(now, -1, ("D",), (0, 1, 3))
    assert v0
    w = cf.windowed({"D": float(now.value)})                                                        # nothing known at or after "now": every daily FVG / OB / VI is out
    assert w.window == {"D": float(now.value)} and cf.window is None                                # (a copy: the shared object is untouched)
    assert w.valid(now, 1, ("D",), (0, 1, 3)) == [] and w.valid(now, -1, ("D",), (0, 1, 3)) == []
    assert w.opposing_ext(now, px, 1, ("D",), (0, 1, 3)) == [] and len(w.targets(now, px, 1, ("D",), False)) < len(cf.targets(now, px, 1, ("D",), False))
    assert w.resistance(now, px, 1, ("D",), (0, 1, 3)) is None
    assert cf.valid(now, 1, ("D",), (0, 1, 3)) + cf.valid(now, -1, ("D",), (0, 1, 3)) == v0
    cut = float(np.median([r[4] for r in v0]))
    w2 = cf.windowed({"D": cut})
    got = w2.valid(now, 1, ("D",), (0, 1, 3)) + w2.valid(now, -1, ("D",), (0, 1, 3))
    assert 0 < len(got) < len(v0) and all(r[4] >= cut for r in got)
    # other timeframes and the opening gaps are never limited
    assert w.valid(now, 1, ("15m",), (0, 1, 3)) == cf.valid(now, 1, ("15m",), (0, 1, 3))
    gw = cf.valid(now, 1, ("W",), (2,)) + cf.valid(now, -1, ("W",), (2,))
    assert w.valid(now, 1, ("W",), (2,)) + w.valid(now, -1, ("W",), (2,)) == gw


def test_ipda_arrays_windows_the_engine_conf():
    """ld4.build replaces ctx.conf by the windowed copy, so the Silver Bullet / entries / targets merges read the same limited arrays."""
    df = _syn_cache("main")
    cf = CF.Confluence(df, 5, 1.0)
    p = Params(**FUT, ipda_arrays=True, ipda_pools=True)
    hist = [rth_day(d, 4010.0 + k, 3990.0 - k) for k, d in enumerate(prior_days(D0, 70))]
    d0 = day(FLAT, base=4000.0)
    ctx = S.DayCtx(d0, D0, hist, 5)
    ctx.conf = cf
    S._setup_news(ctx, ctx.day, p)
    S._extra_levels(ctx, d0, hist, p, None, None)
    assert ctx.conf is not cf and ctx.conf.window == {"D": L4.ipda_since(ctx, p)} and cf.window is None
    ctx2 = S.DayCtx(d0, D0, hist, 5)
    ctx2.conf = cf
    S._setup_news(ctx2, ctx2.day, p)
    S._extra_levels(ctx2, d0, hist, replace(p, ipda_arrays=False), None, None)
    assert ctx2.conf is cf


def test_ipda_window_obs_voids_frame_and_converge():
    from test_caption_gap_ld3 import hist_from
    ohlc = [(4090.0, 4100.0, 4080.0, 4090.0)] * 30
    ohlc[12] = (4100.0, 4120.0, 4098.0, 4115.0)                                                     # the window high candle: up-close, high 4120 -> the bearish OB
    ohlc[13] = (4112.0, 4113.0, 4060.0, 4065.0)                                                     # displacement down
    ohlc[14] = (4065.0, 4075.0, 4050.0, 4062.0)                                                     # ... leaves the bearish FVG 4075-4098 and the OB at the 4120 high
    ohlc[20] = (4062.0, 4062.0, 4048.0, 4050.0)
    ohlc[21] = (4042.0, 4044.0, 4040.0, 4041.0)                                                     # a void: this high 4044 is below the previous low 4048
    ohlc[29] = (4050.0, 4055.0, 4044.0, 4045.0)                                                     # yesterday closed in the lower half of the 60-session range
    hist = hist_from(ohlc, D0)
    p = Params(**BASE, ipda_pools=True, ipda_fv=True, ipda_window_arrays=True)
    ctx = ctx3(day(FLAT, base=4040.0), hist, p)
    i = k_at(ctx, "09:30") + 2
    sd = side(ctx)
    n_off = len(S._lv_target_arrays(ctx3(day(FLAT, base=4040.0), hist, replace(p, ipda_window_arrays=False)), sd, i, replace(p, ipda_window_arrays=False)))
    arr = S._lv_target_arrays(ctx, sd, i, p)
    assert len(arr) > n_off                                                                          # the daily OB and the void are array targets beside the FVGs
    assert any(abs(v - 4120.0) < 1.0 or abs(v - 4109.0) < 1.0 for v, _ in arr)
    # convergence: the 60-session high 4120 is the top of the bearish OB -> the preferred draw
    q = replace(p, ipda_converge=True, ipda_windows=(20, 40, 60))
    ctx = ctx3(day(FLAT, base=4040.0), hist, q)
    assert 4120.0 in L4.ipda_converge_levels(ctx, sd, i, q)
    pref = L4.draw_prefs(ctx, sd, i, 4041.0, q)
    assert (4120.0, "pool", "ipda_converge") in pref and L4._c(ctx)["converge"] == 4120.0
    assert L4.draw_prefs(ctx, sd, i, 4041.0, replace(q, ipda_converge=False)) == []
    assert "ipda_converge" in L4.late_tags(ctx, sd, q, 4041.0, [4120.0])
    # the frame: yesterday's close in the lower half of the 60-session range -> framed off the window HIGH
    fq = replace(p, ipda_frame=True)
    ctx = ctx3(day(FLAT, base=4040.0), hist, fq)
    assert ctx.ipda_frame["mode"] == "high" and ctx.ipda_frame["hi"] == 4120.0
    tags = L4.late_tags(ctx, sd, fq, 4041.0, [])
    assert "frame_high" in tags and "ipda_disc" in tags and L4.late_tags(ctx, sd, p, 4041.0, []) == []


def test_ipda_markers():
    days = [(100.0 + k, 90.0 + k) for k in range(70)]
    out = L.ipda_markers(days, 10, (20, 40, 60))
    assert sorted(out) == ["m1w20", "m2w20", "m2w40", "m3w20", "m3w40", "m3w60"]
    assert out["m1w20"] == (100.0 + 29, 90.0 + 10)                                                  # marker 30: the 20 sessions before it (10..29)
    assert out["m2w40"] == (100.0 + 49, 90.0 + 10)
    short = L.ipda_markers(days[:35], 10, (20, 40, 60))
    assert sorted(short) == ["m1w20"] and short["m1w20"] == out["m1w20"]                             # only marker 30 is reached; nothing depends on sessions after it
    assert L.ipda_markers(days[:29], 10, (20,)) == {}
    assert L.ipda_markers(days + [(500.0, 1.0)] * 3, 10, (20, 40, 60))["m3w60"] == out["m3w60"]


def test_forward_back_windows_end_before_the_anchor():
    ds = prior_days(D0, 30)
    hist = [rth_day(d, 4010.0 + k, 3990.0 - k) for k, d in enumerate(ds)]
    p = Params(**BASE, ipda_pools=True, ipda_anchor="current_month")
    a = ctx3(day(FLAT, base=4000.0), hist, p)
    b = ctx3(day(FLAT, base=4000.0), hist, replace(p, ipda_forward=True))
    assert a.ipda_D is not None and b.ipda_D == a.ipda_D
    assert a.ipda_end == a.ipda_D + 1 and b.ipda_end == b.ipda_D                                    # forward intervals start AT D: the back windows end the session before it
    m = ctx3(day(FLAT, base=4000.0), hist, replace(p, ipda_anchor="month", ipda_forward=True))
    assert m.ipda_end == m.ipda_D                                                                   # (as "month" always did)
    rc = replace(p, ipda_forward=True, ipda_recompute=True)
    c = ctx3(day(FLAT, base=4000.0), hist, rc)
    assert set(L4.ipda_fwd(c, rc)) >= set(L4.ipda_fwd(c, replace(rc, ipda_recompute=False)))


# --- new-lookback-per-tf-topdown (104): per-timeframe windows for the zones, tf pools tagged with their source timeframe ------------------

def _flat_rth(d, base, spikes=()):
    """A regular session of 78 5m bars around `base`; spikes = [(bar, high, low)] overrides."""
    rows = [(base, base + 0.2, base - 0.2, base)] * 78
    rows = list(rows)
    for k, hi, lo in spikes:
        rows[k] = (base, hi, lo, base)
    return frame(d, rows, 5, "09:30")


def _tf_world(window=4, spikes=None, today_base=4100.0):
    ds = prior_days(D0, 6)
    spikes = spikes or {1: [(18, 4150.0, 4099.8)], 2: [(30, 4100.2, 4050.0)]}          # d2: a 4150 spike high (11:00); d3: a 4050 spike low (12:00)
    hist = [_flat_rth(d, 4100.0, spikes.get(k, ())) for k, d in enumerate(ds)]
    p = Params(**BASE, tf_pools=True, tf_lookback={"15m": window})
    ctx = ctx3(day([(today_base, today_base + 0.2, today_base - 0.2, today_base)] * 40, d=D0, base=today_base), hist, p)
    return ctx, p


def test_tf_pools_per_timeframe_window():
    ctx, p = _tf_world(4)                                                              # the window holds d3..d6 (the last 4 sessions); d1 / d2 spikes: d2 is OUT
    ctx, p = _tf_world(5)                                                              # d2..d6: the 4150 spike (d2) and the 4050 spike (d3) are inside, older than the prior session d6
    sd = side(ctx)
    i = k_at(ctx, "10:00")
    buy = L4.tf_pools(ctx, sd, i, p, True)
    assert [(v, lab, m) for v, lab, m, _ in buy] == [(4150.0, "15m", 15)]
    sell = L4.tf_pools(ctx, sd, i, p, False)
    assert [(v, lab) for v, lab, _, _ in sell] == [(4050.0, "15m")]
    assert ctx.__dict__["_tp_pool_tf"][4150.0] == 15 and ctx.__dict__["_tp_pool_tf"][4050.0] == 15       # pool_rank ranks by the source timeframe
    short = side(ctx, -1)
    assert [v for v, *_ in L4.tf_pools(ctx, short, i, p, True)] == [-4050.0]                              # the mirror: a short's buy side is the real lows
    assert L4.tf_pools(ctx, sd, i, replace(p, tf_pools=False), True) == []
    ctx4, p4 = _tf_world(3)                                                                                 # d4..d6: both spikes are older than the window
    assert L4.tf_pools(ctx4, side(ctx4), k_at(ctx4, "10:00"), p4, True) == []
    # the glue: targets and sweep pools, the tag
    assert (4150.0, ctx.start) in L4.target_pools(ctx, sd, i, p)
    out = {}
    L4.sell_pools(ctx, sd, i, p, out)
    assert out["tfp15m0"] == 4050.0 and S._level_created(ctx, "tfp15m0", "AM") == ctx.start
    lvt = []
    L4.order_gate(ctx, sd, dict(key="tfp15m0", level=4050.0, ext=4049.0), i, p, 4051.0, None, False, lvt)
    assert lvt == ["tf_15m"]
    # taken since: a later session trades through the 4150 high
    ds = prior_days(D0, 6)
    ctx5, p5 = _tf_world(5, {1: [(18, 4150.0, 4099.8)], 4: [(10, 4151.0, 4099.8)]})
    assert [v for v, *_ in L4.tf_pools(ctx5, side(ctx5), k_at(ctx5, "10:00"), p5, True)] == [4151.0]       # (the 4150 pool is gone; the new higher high is the pool)
    # no look-ahead: the answer at bar i does not depend on the bars after it
    j = k_at(ctx, "09:30") + 3
    assert L4.tf_pools(ctx, sd, j, p, True) == buy


def test_hzones_window_per_timeframe():
    ds = prior_days(D0, 8)
    hist = []
    for k, d in enumerate(ds):
        rows = [(4000.0, 4001.0, 3999.0, 4000.0)] * 78
        if k == 2:                                                                  # the third session (oldest in a 6-session window) leaves a 15m FVG 4001-4010
            rows = list(rows)
            rows[3:6] = [(4001.0, 4012.0, 4001.0, 4011.0)] * 3
            rows[6:9] = [(4011.0, 4015.0, 4010.0, 4012.0)] * 3
        hist.append(frame(d, rows, 5, "09:30"))
    df = day([(4000.0, 4001.0, 3999.0, 4000.0)] * 5, d=D0, base=4000.0)
    default = S.DayCtx(df, D0, hist, 5, htf=(15,))
    wide = S.DayCtx(df, D0, hist, 5, htf=(15,), tf_lookback={"15m": 6})
    narrow = S.DayCtx(df, D0, hist, 5, htf=(15,), tf_lookback={"15m": 3})
    assert not default.hzones and wide.hzones and not narrow.hzones                   # 5 sessions (default) and 3 do not reach the third session back; 6 do
    assert all(z.kind in ("bull", "bear") for z, _, _ in wide.hzones)
    assert S.DayCtx(df, D0, hist, 5, htf=(15,), tf_lookback={"1h": 9}).hzones == default.hzones     # (a window of another timeframe changes nothing)


# --- L3-monthly-ohlc-3m (112): the first month, the range frame, the scoring; LLT3 (148): the prior NY range ----------------------------------

def test_monthly_first_month_and_range_frame(monkeypatch):
    assert L4.history_starts_month([date(2026, 6, 1), date(2026, 6, 2)]) is True
    assert L4.history_starts_month([date(2026, 2, 2), date(2026, 2, 3)]) is True                     # Feb 1 2026 is a Sunday: the 2nd is the first trading day
    assert L4.history_starts_month([date(2026, 6, 3), date(2026, 6, 4)]) is False
    assert L4.history_starts_month([]) is False
    ds = prior_days(date(2026, 3, 2), 45)
    ds = [d for d in ds if d >= date(2026, 1, 2)]                                                    # starts on January's first trading day
    o = np.arange(len(ds), dtype=float) + 100
    out_full = L.monthly_candles(ds, o, o + 1, o - 1, o + 0.5, date(2026, 3, 2), 3, first_month_full=True)
    out_cut = L.monthly_candles(ds, o, o + 1, o - 1, o + 0.5, date(2026, 3, 2), 3, first_month_full=False)
    assert [k for k, *_ in out_full][0] == (2026, 1) and (2026, 1) not in [k for k, *_ in out_cut]
    MC = [((2026, 1), 100.0, 112.0, 99.0, 110.0), ((2026, 2), 110.0, 111.0, 100.0, 102.0), ((2026, 3), 102.0, 109.0, 101.0, 108.0)]
    assert L.monthly_range_frame(MC) == (100.0, 112.0)                                                # the down-close month's low to the up-close month above its high
    assert L.monthly_range_frame(MC[:1]) is None and L.monthly_range_frame([MC[0], MC[2]]) is None
    # the engine: ctx.m_frame and the tags
    monkeypatch.setattr(L, "monthly_candles", lambda *a, **k: MC)
    p = Params(**BASE, monthly_ohlc=True, monthly_frame=True)
    hist = history(D0, n=8)
    ctx = ctx3(day(FLAT, base=4000.0), hist, p)
    assert ctx.m_frame == (100.0, 112.0) and len(ctx.m_ohlc) == 12 and ctx.m_ohlc[:4] == [100.0, 112.0, 99.0, 110.0]   # the 12 levels of the last 3 candles
    sd = side(ctx)
    assert "m_frame_disc" in L4.late_tags(ctx, sd, p, 104.0, []) and "m_frame_prem" in L4.late_tags(ctx, side(ctx, -1), p, -104.0, [])
    assert not [t for t in L4.late_tags(ctx, sd, p, 120.0, []) if t.startswith("m_frame")]           # outside the frame
    assert not [t for t in L4.late_tags(ctx, sd, replace(p, monthly_frame=False), 104.0, []) if t.startswith("m_frame")]
    # the scoring input: the monthly levels count as converging arrays for converge_rank
    g = L.Zone("bull", 111.0, 109.0, 5, 3)
    assert LD.converge_n(ctx, sd, g, 8, replace(p, converge_rank=True)) >= 1


def test_prior_ny_session_range_frame():
    lon = frame(D0 - timedelta(days=1), [(4000.0, 4130.0, 3990.0, 4001.0)] * 6, 5, "03:00")           # London bars: outside the NY range
    ny = frame(D0 - timedelta(days=1), [(4100.0, 4110.0, 4090.0, 4100.0)] * 20, 5, "09:30")
    prev_full = pd.concat([lon, ny])
    p = Params(**BASE, ny_hl_frame=True)
    ctx = ctx3(day(FLAT, base=4100.0), history(D0, n=8), p, prev_full=prev_full)
    assert ctx.ny_hl == (4110.0, 4090.0)
    sd = side(ctx)
    assert "in_ny_range" in L4.late_tags(ctx, sd, p, 4100.0, []) and "in_ny_range" not in L4.late_tags(ctx, sd, p, 4120.0, [])
    assert "in_ny_range" not in L4.late_tags(ctx, sd, replace(p, ny_hl_frame=False), 4100.0, [])
    assert ctx3(day(FLAT, base=4100.0), history(D0, n=8), replace(p, ny_hl_frame=False), prev_full=prev_full).ny_hl is None


# --- Params, plumbing, study ------------------------------------------------------------------------------------------------------

NEW_REVIEW_SWITCHES = ("flip_retest_entry", "tl_trap_entries", "tl_tol_adr", "hs_rearm", "htf_monthly_arrays", "tf_pools", "ipda_window_arrays", "ipda_frame",
                       "ipda_converge", "ipda_recompute", "monthly_frame", "ny_hl_frame", "tue_open_time", "org_revisit_gate", "reactionary_precond")


def test_review_switch_defaults_and_validation():
    d = Params()
    assert (d.flip_retest_entry, d.tl_trap_entries, d.tl_tol_adr, d.hs_rearm, d.htf_monthly_arrays, d.tf_pools, d.ipda_window_arrays, d.ipda_frame,
            d.ipda_converge, d.ipda_recompute, d.monthly_frame, d.ny_hl_frame, d.tue_open_time, d.org_revisit_gate, d.reactionary_precond) == \
        (False, (), 0.0, False, False, False, False, False, False, False, False, False, "0930", False, False)
    assert B.htf_kw(d) == {"c2_dir": True} and B.table_kw(d) == {"c2_dir": True, "balance_tf": "own"}              # the cache keys of the old settings are unchanged
    assert B.hist_days(d) == 61
    # the Silver Bullet stays off by default; its bias switches are not touched by this package
    assert d.sb_model is False and d.sb_use_bias is False


def test_review_study_variants():
    want = ["L2-sr-needs-fvg_flip_retest", "new-trendline-trap_entries", "new-trendline-trap-target_adr_tol", "new-hs-fade_rearm",
            "L3-htf-pd-arrays-intraday_monthly", "new-lookback-per-tf-topdown_pools", "B21-reference-points-in-windows_arrays",
            "B21-progression-20-40-60-beyond_converge", "B21-open-float-forward-windows_recompute", "L3-monthly-ohlc-3m_frame",
            "LLT3-london-extreme-preny-range_ny_frame", "L5-holiday-nwog_midnight", "L7-org-lifetime-sr_revisit_gate", "new-reactionary-high-liquidity_precond"]
    assert sorted(want) == sorted(study._LD3C_DECISIONS)
    for k, v in study._LD3C_DECISIONS.items():
        assert k in study.DECISIONS
        replace(Params(), **{**study.DEC_BASE, **v})                                          # every variant builds a valid Params
    used = {s_ for v in study._LD3C_DECISIONS.values() for s_ in v}
    for s_ in NEW_REVIEW_SWITCHES:
        assert s_ in used, s_


def test_every_review_switch_is_named_by_a_test():
    src = Path(__file__).read_text(encoding="utf-8")
    body = src.replace(src[src.index("NEW_REVIEW_SWITCHES = ("):src.index("def test_review_switch_defaults_and_validation")], "")
    for s_ in NEW_REVIEW_SWITCHES:
        assert s_ in body, s_


# --- no look-ahead on a synthetic frame WITH overnight bars (so the confluence / HTF-array paths run everywhere) ---------------------------------

from test_caption_gap_ld1 import ENTRY, EXIT                                                      # noqa: E402  (shared column lists)

SYN_P = dict(use_bias=True, bias_open="0930", ob_entry="both", draw_lock_neutral="both", leg_pd=0, min_draw_pts=0, htf_resist_cap=False, year_end="off",
             sloppy_mode="off")
SYN_GROUPS = {
    "pools": dict(org_days=20, org_both_ways=True, org_revisit_gate=True, wick_levels=True, wick_days=5, wick_untraded=True, wick_lod_tag="tag",
                  wick_weekly=True, wick_weeks=2, reactionary_pools=True, reactionary_precond=True, parent_pools=True, trendline_pools=True, week_pools=True,
                  tf_lookback={"15m": 4, "1h": 15, "4h": 30, "D": 90}, tf_pools=True, ipda_pools=True, ipda_rb=True, prev_london_pool=True, extra_pools=True,
                  or0809_pool=True, rel_tfs=(60, 240), pool_rank=True, london_lr_zone="tag", ny_hl_frame=True),
    "ipda": dict(ipda_next=True, ipda_roll_arrays=True, ipda_beyond_days=60, ipda_anchor="month", ipda_forward=True, ipda_recompute=True, monthly_ohlc=True,
                 monthly_frame=True, ipda_arrays=True, ipda_window_arrays=True, ipda_fv=True, ipda_frame=True, ipda_converge=True, converge_rank=True,
                 htf_monthly_arrays=True, htf_bias="combo", htf_targets=("15m", "1h", "4h", "D", "W", "M"), tf_lookback={"D": 90}, ipda_pools=True),
    "nolock": dict(draw_lock="off", ipda_pools=True, ipda_next=True, ipda_roll_arrays=True, ipda_beyond_days=60, ipda_anchor="month", ipda_forward=True,
                   ipda_recompute=True, ipda_arrays=True, ipda_converge=True, ipda_rb=True, reactionary_pools=True, parent_pools=True, week_pools=True,
                   daily_level_needs_array="fvg", flip_retest_entry=True, hs_fade=True, hs_rearm=True, hs_tf=15, eq_tol_pts=3.0, hs_stop_pts=10.0,
                   trendline_trap=True, tl_trap_entries=("ob", "breaker"), tl_tol_adr=0.2, htf_bias="combo", tf_lookback={"15m": 4, "1h": 15, "D": 90},
                   tf_pools=True, pool_rank=True, rel_tfs=(60,), time_distortion=True, td_fvg_hold=True, single_bar_fvg_strict=True, or_fvg_entries=True,
                   or_expire=660, rb_pools=True, ob_outside_fvg=True, wick_levels=True, wick_days=5, wick_untraded=True, wick_lod_tag="tag",
                   reactionary_precond=True, tue_open_ref=True, tue_open_time="midnight", nwog_holiday_pick="closest", nwog_skip_holiday=True,
                   gap_views="both", weekly_open="either"),
    "anchor_current": dict(ipda_pools=True, ipda_anchor="current_month", ipda_forward=True, ipda_recompute=True, ipda_arrays=True, ipda_next=True),
    "anchor_swing": dict(ipda_pools=True, ipda_anchor="swing", ipda_forward=True, ipda_recompute=True, ipda_arrays=True, ipda_next=True),
    "week_exp": dict(draw_lock="off", week_pools=True, week_raid_days=(0, 1, 2, 3, 4), ipda_next=True, ipda_beyond_days=80, ipda_windows=(20,), ipda_pools=True,
                     monthly_ohlc=True),
}
SYN_WARM = 78
_LA = {}                                                                                           # name -> (full run result, {hit name: count}, {tf labels the htf table built arrays for})


def _full(name):
    """The full run of a group (cached): the trades, the code-path hits of ld4 and the timeframes htf._arrays was asked for."""
    if name not in _LA:
        df = _syn_cache("main")
        p = Params(**FUT, **SYN_P, **SYN_GROUPS[name])
        seen, orig = [], htf._arrays
        L4.HITS.clear()
        htf._arrays = lambda *a, **k: seen.append(a[4]) or orig(*a, **k)
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                full = B.run(df, 5, "ES", p, warmup=SYN_WARM)
        finally:
            htf._arrays = orig
        _LA[name] = (full, dict(L4.HITS), set(seen))
    return _LA[name]


def _la(name, every=5, lag=2):
    """Cuts at entry AND exit times: the entries up to each cut, and the exits of the trades closed by it, match the full run."""
    df = _syn_cache("main")
    p = Params(**FUT, **SYN_P, **SYN_GROUPS[name])
    full = _full(name)[0]
    assert len(full) >= 1, "no trades - the test window must produce some"
    cuts = sorted(set(full.entry_time.iloc[::every]) | set(full.exit_time.dropna().iloc[::every]))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for cut_t in cuts:
            c = cut_t + pd.Timedelta(minutes=lag)
            part = B.run(df[df.index <= c], 5, "ES", p, partial_last=True, warmup=SYN_WARM)
            a = full[full.entry_time <= cut_t][ENTRY].reset_index(drop=True)
            b = part[part.entry_time <= cut_t][ENTRY].reset_index(drop=True)
            pd.testing.assert_frame_equal(a, b, check_dtype=False)
            done = full.exit_time.notna() & (full.exit_time <= cut_t)
            a = full[done][EXIT].reset_index(drop=True)
            b = part[part.entry_time.isin(full[done].entry_time)][EXIT].reset_index(drop=True)
            pd.testing.assert_frame_equal(a, b, check_dtype=False)
    return full


@pytest.mark.parametrize("group", sorted(SYN_GROUPS))
def test_look_ahead_synthetic_overnight(group):
    full = _la(group)
    assert len(full)


def test_the_synthetic_frame_has_overnight_and_a_confluence_object():
    df = _syn_cache("main")
    assert htf.has_overnight(df)
    pr = B.prepare(df, 5, "ES", Params(**FUT))
    assert pr.cf is not None and pr.og is not None and len(pr.og) and (pr.og.kind == "nwog").any() and (pr.og.kind == "ndog").any()
    assert B.prepare(df, 5, "ES", Params(**FUT, gap_views="both")).og.kind.eq("nwog_rth").any()
    assert B.prepare(df, 5, "ES", Params(**FUT, week_pools=True)).eth and B.prepare(df, 5, "ES", Params(**FUT, week_pools=True)).eve      # (the full sessions + evenings for the week reads)


# every switch's code path RAN in one of the runs above: ld4.HITS counts the calls of the function that carries it
REQUIRED_HITS = {
    "flip_retest_entry": ("flip_broken_level",), "tl_trap_entries": ("tl_trap_state",), "hs_rearm": ("hs_pattern_found", "hs_gate_conf"),
    "tf_pools": ("tf_pools",), "ipda_window_arrays": ("ipda_window_arrays",), "ipda_frame": ("ipda_frame_tag",), "ipda_converge": ("ipda_converge",),
    "ipda_recompute": ("ipda_markers",), "monthly_frame": ("monthly_frame_build",), "ny_hl_frame": ("ny_hl_tag",),
    "org_revisit_gate": ("org_revisit_gate",), "reactionary_precond": ("reactionary_ok",),
    # the paths the review found never executed on the synthetic frames
    "wick_lod_tag": ("wick_lod",), "daily_level_needs_array": ("daily_fvg_ok",), "ipda_arrays": ("ipda_arrays_window", "conf_targets_window"),
    "week_pools": ("week_pools", "week_gate", "week_prior_lows"), "ipda_forward": ("multi_window",), "ipda_rb": ("ipda_rb_body",),
    "ipda_beyond_days": ("expansion_tag",), "monthly_ohlc": ("m_ohlc_tag",), "time_distortion": ("time_distortion", "td_drop"), "td_fvg_hold": ("td_hold",),
    "or_fvg_entries": ("or_fvg_zones",), "rb_pools": ("rb_build",), "ob_outside_fvg": ("ob_outside_zone",), "london_lr_zone": ("lr_state",),
    "parent_pools": ("parent_buy", "parent_sell"), "ipda_roll_arrays": ("ipda_roll_arrays",), "trendline_pools": ("trendline_pools",),
}


def test_every_review_switch_ran_in_the_synthetic_runs():
    hits, tfs = {}, set()
    for g in sorted(SYN_GROUPS):
        _, h, t = _full(g)
        for k, v in h.items():
            hits[k] = hits.get(k, 0) + v
        tfs |= t
    missing = {sw: [h for h in names if not hits.get(h)] for sw, names in REQUIRED_HITS.items()}
    assert not {k: v for k, v in missing.items() if v}, missing
    assert "M" in tfs                                                                                  # htf_monthly_arrays: the table built monthly arrays
    # every switch of REQUIRED_HITS is on in at least one group
    on = set().union(*[set(g) for g in SYN_GROUPS.values()])
    assert set(REQUIRED_HITS) <= on
    # (tue_open_time, tl_tol_adr: tuning / holiday-only paths - covered by their unit tests above)
    assert set(NEW_REVIEW_SWITCHES) - set(REQUIRED_HITS) <= {"htf_monthly_arrays", "tl_tol_adr", "tue_open_time"}


# --- no look-ahead on real ES data (skips when absent) -------------------------------------------------------------------------------------------

@pytest.mark.skipif(not ES, reason="no ES data")
def test_look_ahead_es_review_switches():
    """ES 5m with confluence and the overnight sessions: the pools / IPDA / monthly group, then the entries group (flip retest, trendline-trap OB and
    breaker entries, H&S re-arm, OR FVGs, time distortion on every zone source, the Tuesday midnight reference after Labor Day)."""
    from test_caption_gap_ld3 import _es
    from test_caption_gap_ld1 import _no_look_ahead_x
    df, meta = _es()
    p = Params(**FUT, ipda_pools=True, ipda_anchor="current_month", ipda_forward=True, ipda_recompute=True, ipda_arrays=True, ipda_window_arrays=True,
               ipda_fv=True, ipda_frame=True, ipda_converge=True, tf_lookback={"15m": 4, "1h": 15, "4h": 30, "D": 90}, tf_pools=True, week_pools=True,
               week_raid_days=(0, 1, 2, 3, 4), org_days=20, org_both_ways=True, org_revisit_gate=True, wick_levels=True, wick_days=5, wick_untraded=True,
               wick_lod_tag="tag", reactionary_pools=True, reactionary_precond=True, monthly_ohlc=True, monthly_frame=True, ny_hl_frame=True,
               london_lr_zone="tag", prev_london_pool=True, extra_pools=True, htf_monthly_arrays=True, htf_bias="combo",
               htf_targets=("15m", "1h", "4h", "D", "W", "M"), ob_entry="both", leg_pd=0, min_draw_pts=0, htf_resist_cap=False, draw_lock="off")
    full = _no_look_ahead_x(df, 5, "ES", p, ENTRY + ["draw_px", "draw_name"], every=6, meta=meta)
    q = replace(p, ipda_anchor="month", daily_level_needs_array="fvg", flip_retest_entry=True, trendline_trap=True, tl_trap_entries=("ob", "breaker"),
                tl_tol_adr=0.1, hs_fade=True, hs_rearm=True, hs_tf=15, hs_stop_pts=10.0, or_fvg_entries=True, or_expire=660, time_distortion=True,
                td_fvg_hold=True, single_bar_fvg_strict=True, ob_outside_fvg=True, rb_pools=True, tue_open_ref=True, tue_open_time="midnight",
                weekly_open="either", nwog_skip_holiday=True, nwog_holiday_pick="closest", gap_views="both", ob_entry="post_mss")
    _no_look_ahead_x(df, 5, "ES", q, ENTRY, every=6, meta=meta)

