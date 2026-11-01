"""Caption-gap pass, package levels_detectors #2/3 (29 specs of digests/rulebook_gaps/definitions_pd_arrays_structure.md and
levels_liquidity_targets.md): unit tests of the new detectors in levels.py / htf.py, the ld3.py engine glue, Params / study
plumbing and no-look-ahead runs (full vs truncated) covering the new switches on small date windows. Tests that need local market
data (ES) skip cleanly when it is absent; no platform-specific paths or imports."""
import warnings
from dataclasses import replace
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from mentorship import backtest as B, entries as EN, htf, ld2 as LD, ld3 as L3, levels as L, strategy as S, study, targets as TP
from mentorship.study import OA1029_OLD
from mentorship.strategy import Params
from dataclasses import dataclass as _oa_dc


@_oa_dc
class Params(Params):   # OA1029 Q92: these tests exercise other rules; the order-block narrative gate (default on) leaves them no trades
    ob_need_narrative: bool = False
    bk_depth: str = "ce"                    # OA1029 Q11 / Q113 / Q171: the pre-build values these path tests were written for
    bk_bpr_ce: bool = False
    htf_gap_final: str = "ce"
    objective_done_pm: str = "off"

from test_levels_detectors import BASE, D0, ES, FUT, NY, ctx_for, day, frame, history, prior_days, rth_day

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


def daily_df(ohlc, first=date(2026, 3, 2), tf=15):
    """A futures-style frame (evening reopen to the 16:55 close) with one controlled session per (o, h, l, c): the path open -> low -> high -> close
    (or open -> high -> low -> close for a down day) through the session's bars, so its extremes are exact. Consecutive weekdays."""
    frames, d = [], pd.Timestamp(first)
    n = (23 * 60) // tf - 1
    for (o_, h_, l_, c_) in ohlc:
        while d.weekday() >= 5:
            d += pd.Timedelta(days=1)
        start = (d - pd.Timedelta(days=1)).replace(hour=18)                                 # (Monday: the Sunday 18:00 reopen)
        pts = [o_, l_, h_, c_] if c_ >= o_ else [o_, h_, l_, c_]
        path = np.interp(np.arange(n + 1), [0, n // 3, 2 * n // 3, n], pts)
        idx = pd.date_range(start, periods=n, freq=f"{tf}min", tz=NY)
        frames.append(pd.DataFrame({"open": path[:-1], "high": np.maximum(path[:-1], path[1:]), "low": np.minimum(path[:-1], path[1:]),
                                    "close": path[1:], "volume": 1.0}, index=idx))
        d += pd.Timedelta(days=1)
    return pd.concat(frames)


# --- A2-which-old-high (levels_liquidity_targets 1) ------------------------------------------------------------------------

def test_first_old_high_beyond_today():
    """Daily pivots 4100, 4080, 4060 (newest last): today's high 4070 -> 4080; 4085 -> 4100; above all -> None."""
    piv = [L.Pivot(1, 4100.0, 2), L.Pivot(3, 4080.0, 4), L.Pivot(5, 4060.0, 6)]
    assert L.first_old_beyond(piv, 4070.0) == 4080.0
    assert L.first_old_beyond(piv, 4085.0) == 4100.0
    assert L.first_old_beyond(piv, 4100.0) is None
    assert L.first_old_beyond([4100.0, 4080.0, 4060.0], 4055.0) == 4060.0         # plain prices work too
    assert L.first_old_beyond([], 1.0) is None


def _old_pool_ctx(p, today_rows):
    # daily highs 100, 112, 102, 109, 101, 100.8, 100.6, 100.5: pivot highs 112 and 109 (the newest last); the last three days (the
    # PDH1-3 pools) are all under 101; lows vary
    hist = history(D0, n=8, highs=[100, 112, 102, 109, 101, 100.8, 100.6, 100.5], lows=[95, 90, 97, 93, 98, 94, 99, 96])
    df = day(today_rows, start="09:30")
    return ctx_for(df, hist, p)


def test_active_old_pool_walks_back_newest_to_oldest():
    p = Params(**BASE, active_old_pool=True)
    rows = ([(100.0, 100.4, 99.6, 100.0)] * 4 + [(100.0, 109.5, 99.8, 109.0)] + [(109.0, 109.2, 108.8, 109.0)] * 6
            + [(109.0, 113.0, 108.9, 112.5)] + [(112.0, 112.2, 111.8, 112.0)] * 20)
    ctx = _old_pool_ctx(p, rows)
    sd = S.Side(1, ctx.o, ctx.h, ctx.l, ctx.c, 1)
    k0 = S._idx_at(ctx, 570)
    assert L3.old_pool(ctx, sd, k0 + 3, p, True) == 109.0                       # today's high 100.4: the newest pivot above it
    assert L3.old_pool(ctx, sd, k0 + 4, p, True) == 112.0                       # a 109.5 high on bar 4: 109 is behind us -> 112
    assert L3.old_pool(ctx, sd, k0 + 11, p, True) is None                       # 113 > every older high
    # the bar being tested is not in the sell-side low (no look-ahead) - and the low pool is the first older swing low below it
    lo = L3.old_pool(ctx, sd, k0 + 3, p, False)
    assert lo is not None and lo < 99.6
    # a target of _targets with the switch (created at the day start), absent without it
    tg = S._targets(ctx, sd, k0 + 3, 100.5, [], p, ext_i=k0 + 3)
    assert (109.0, "pool") in tg
    assert (109.0, "pool") not in S._targets(ctx, sd, k0 + 3, 100.5, [], replace(p, active_old_pool=False), ext_i=k0 + 3)
    # the sell-side key and the lock candidates
    assert "old_lo" in S._sell_side(ctx, sd, "AM", k0 + 3, False, p)
    assert S._level_created(ctx, "old_lo", "AM") == ctx.start
    lk = L3.lock_cands(ctx, p, 570, k0 + 1)
    assert {c[2] for c in lk} >= {"old_hi", "old_lo"} and dict((c[2], c[0]) for c in lk)["old_hi"] == 109.0
    short = S.Side(-1, ctx.o, ctx.h, ctx.l, ctx.c, 1)
    assert L3.old_pool(ctx, short, k0 + 3, p, True) is not None                  # the mirror: an older swing LOW below today's low, in side space
    mk_ = S.mark_levels(ctx, None, 570, "AM", p)                                 # the session lock marks the old high as a candidate too
    assert (109.0, "pool", "old_hi", 1) in mk_["marked"]
    assert not [m for m in S.mark_levels(ctx, None, 570, "AM", replace(p, active_old_pool=False))["marked"] if m[2] == "old_hi"]


# --- A2-round-number-pool (2) -----------------------------------------------------------------------------------------------

def test_round_pool_confluence_mode():
    p = Params(es_pt=1.0, round_pool_mode="confluence", round_conf_pts=1.0)
    assert L3.round_filter([3900.0, 3950.0], [3900.5, 3800.0], p) == [3900.0]          # 3950 has nothing within 1 pt
    assert L3.round_filter([3900.0, 3950.0], [3900.5], replace(p, round_pool_mode="tag_only")) == []
    assert L3.round_filter([3900.0, 3950.0], [], replace(p, round_pool_mode="pool")) == [3900.0, 3950.0]
    # the tag: a swept level at a handle (real prices via the front-month step) and a surviving handle itself
    ctx = type("C", (), dict(round_step=50.0, adj=np.zeros(10)))()
    sd = S.Side(1, np.ones(10), np.ones(10), np.ones(10), np.ones(10), 1)
    assert L3.round_tag(ctx, sd, dict(level=3900.4, ext_i=3, key="pdl1"), p) == "round_conf"
    assert L3.round_tag(ctx, sd, dict(level=3910.0, ext_i=3, key="pdl1"), p) == ""
    assert L3.round_tag(ctx, sd, dict(level=3910.0, ext_i=3, key="round"), p) == "round_conf"
    assert L3.round_tag(ctx, sd, dict(level=3900.0, ext_i=3, key="pdl1"), replace(p, round_pool_mode="pool")) == ""
    # the lock candidates: a round handle is marked only with a pool at it in "confluence" mode, never in "tag_only"
    pb = Params(**BASE, round_pool_mode="confluence", round_conf_pts=1.0)
    c2 = ctx_for(day([(102.0, 102.4, 101.6, 102.0)] * 20, start="09:30", base=102.0), history(D0, n=8, highs=[108.0] * 7 + [100.4]), pb)
    c2.round_step, c2.adj, c2.round_from = 50.0, np.zeros(len(c2.idx)), "session"
    names = lambda pp: [m[2] for m in S.mark_levels(c2, None, 570, "AM", pp)["marked"]]
    assert "round" in names(replace(pb, round_pool_mode="pool"))
    assert "round" in names(pb)                                                      # PDH1 100.4 is within a point of the 100 handle
    assert "round" not in names(replace(pb, round_pool_mode="tag_only"))
    assert "round" not in names(replace(pb, round_conf_pts=0.1))


# --- A3-engineered-liquidity (5) --------------------------------------------------------------------------------------------

def test_engineered_pool_detect():
    hi = [L.Pivot(10, 4100.0, 11), L.Pivot(40, 4098.0, 41)]
    lo = [L.Pivot(50, 4090.0, 51)]
    r = L.engineered_pools(hi, lo, 100, 3.0)
    assert r == [(4100.0, 30.0, 51, 40)]                                                # price H1, score 30 bars, created at the low's known bar
    assert L.engineered_pools(hi, lo, 100, 1.0) == []                                   # falls short by 2 > 1
    assert L.engineered_pools(hi, lo, 50, 3.0) == []                                    # the low is not yet known
    assert L.engineered_pools(hi, [], 100, 3.0) == []                                   # price never dropped away
    assert L.engineered_pools([hi[0], L.Pivot(40, 4101.0, 41)], lo, 100, 3.0) == []     # a HIGHER second high is no falling-short
    # a swing low between the highs: the drop must go below it
    mid = [L.Pivot(25, 4092.0, 26)]
    assert L.engineered_pools(hi, mid + [L.Pivot(50, 4093.0, 51)], 100, 3.0) == []
    assert len(L.engineered_pools(hi, mid + lo, 100, 3.0)) == 1
    # an FVG bottom just above H1 adds a point; the pool is dropped once the highs trade through H1
    assert L.engineered_pools(hi, lo, 100, 3.0, fvg_bottoms=[4100.5])[0][1] == 31.0
    h = np.full(120, 4090.0)
    h[60] = 4101.0
    assert L.engineered_pools(hi, lo, 100, 3.0, h=h) == []
    assert len(L.engineered_pools(hi, lo, 55, 3.0, h=h)) == 1


def _eng_frame():
    # 15m candles (3 five-minute bars each) from 09:30: H1 103 (c1), the between-low 96 (c3), H2 102 (c4), the drop to 94 (c5)
    cand = [(98.0, 99.0), (98.5, 103.0), (98.0, 100.0), (96.0, 99.0), (97.5, 102.0), (94.0, 98.0), (95.0, 99.0), (96.0, 99.5),
            (96.5, 99.0), (97.0, 99.0), (97.0, 99.0), (97.0, 99.0), (97.0, 99.0), (97.0, 99.0)]
    rows = []
    for lo, hi in cand:
        rows += [(lo + 0.2, hi, lo, hi - 0.2)] * 3
    return day(rows, start="09:30")


def test_engineered_pool_in_the_engine():
    p = Params(**BASE, engineered_pools=True, eng_short_pts=3.0, eq_pref="rank", draw_lock="off")
    ctx = ctx_for(_eng_frame(), history(D0, n=8), p)
    sd = S.Side(1, ctx.o, ctx.h, ctx.l, ctx.c, 1)
    k0 = S._idx_at(ctx, 570)
    early, late = k0 + 12, k0 + 30
    assert not L3.eng_pools(ctx, sd, early, p, True)                                    # the dropping low is not known yet
    pools = L3.eng_pools(ctx, sd, late, p, True)
    assert any(abs(v - 103.0) < 1e-9 for v, *_ in pools)
    tg = S._targets(ctx, sd, late, 97.0, [], p, ext_i=late)
    assert (103.0, "pool_eq") in tg                                                     # ranked like a rel-eq pool (eq_pref)
    assert not [x for x in S._targets(ctx, sd, late, 97.0, [], replace(p, engineered_pools=False), ext_i=late) if abs(x[0] - 103.0) < 1e-9
                and x[1] != "pool"]
    # sell-side mirror exists as a named sweep pool with its creation bar
    short = S.Side(-1, ctx.o, ctx.h, ctx.l, ctx.c, 1)
    L3.sell_pools(ctx, short, late, p, {})
    assert isinstance(L3.eng_all(ctx, sd, p, True), list)


# --- L1-rth-session-pools (12) ----------------------------------------------------------------------------------------------

def _pm_day(d, pm_hi, pm_lo):
    """An RTH day whose 13:30 bar holds the PM range (hi, lo) - the rest flat at 100."""
    rows = [(100.0, 100.2, 99.8, 100.0)] * 48 + [(100.0, pm_hi, pm_lo, 100.0)] + [(100.0, 100.2, 99.8, 100.0)] * 29
    return frame(d, rows, 5, "09:30")


def test_prev_pm_low_survives_overnight_break():
    hist = history(D0, n=8)
    hist[-1] = _pm_day(prior_days(D0, 1)[0], 104.0, 96.0)
    rows = [(99.5, 99.7, 94.0, 99.5)] + [(99.5, 99.7, 99.4, 99.5)] * 5                  # 03:00: an overnight low 94 under the PM low 96
    rows = rows + [(100.0, 100.5, 99.9, 100.2)] * 60
    pre = frame(D0, [(100.0, 100.2, 99.8, 100.0)] * 36 + rows, 5, "00:00")             # 00:00-03:00 flat, then the break, then RTH from 09:30
    # build one frame: 00:00..09:25 pre (114 bars), RTH after
    pre_n = (570 // 5)
    allrows = [(100.0, 100.2, 99.8, 100.0)] * pre_n
    allrows[36] = (99.5, 99.7, 94.0, 99.5)
    allrows[40] = (100.0, 106.0, 99.9, 100.0)                                           # an overnight HIGH 106 over the PM high 104
    allrows += [(100.0, 100.5, 99.9, 100.2)] * 40
    df = frame(D0, allrows, 5, "00:00")
    p = Params(**BASE, extra_pools=True)
    ctx = ctx_for(df, hist, p)
    sd = S.Side(1, ctx.o, ctx.h, ctx.l, ctx.c, 1)
    i = S._idx_at(ctx, 600)                                                             # 10:00
    v = ctx.sess["prev_pm"][1]
    tk = S._tick(p)
    assert not S._level_intact(ctx, sd.l, i, "prev_pm", v, "AM", tk)                    # the overnight break spent it (the old rule)
    p2 = replace(p, rth_pool_spent=True)
    ctx2 = ctx_for(df, hist, p2)
    assert S._level_intact(ctx2, sd.l, i, "prev_pm", v, "AM", tk)                       # RTH low 99.9 > 96: still a pool at 10:00
    assert S._level_created(ctx2, "prev_pm", "AM") == S._idx_at(ctx2, 570)
    # the buy side: the PM high 104 is a target only with the switch (an overnight 106 print spent it otherwise)
    ext = i
    old = S._targets(ctx, sd, i, 100.5, [], p, ext_i=ext)
    new = S._targets(ctx2, sd, i, 100.5, [], p2, ext_i=ext)
    assert all(abs(x[0] - 104.0) > 1e-9 for x in old)
    assert any(abs(x[0] - 104.0) < 1e-9 for x in new)
    # an RTH print through it spends it in both modes
    allrows2 = list(allrows)
    allrows2[S._idx_at(ctx, 570) - ctx.start + 3] = (100.0, 105.0, 99.9, 100.0)
    ctx3 = ctx_for(frame(D0, allrows2, 5, "00:00"), hist, p2)
    sd3 = S.Side(1, ctx3.o, ctx3.h, ctx3.l, ctx3.c, 1)
    assert all(abs(x[0] - 104.0) > 1e-9 for x in S._targets(ctx3, sd3, i, 100.5, [], p2, ext_i=i))


# --- L3-midnight-session-opening-ranges (13) --------------------------------------------------------------------------------

def test_midnight_or_pools():
    p = Params(**BASE, session_ors=((0, 30), (0, 60)))
    rows = [(100.0, 101.0, 99.5, 100.5)] * 6 + [(100.5, 103.0, 99.0, 102.0)] * 6 + [(102.0, 102.2, 101.8, 102.0)] * 30
    df = day(rows, start="00:00")
    ctx = ctx_for(df, history(D0, n=8), p)
    assert [(n, h, l) for n, h, l, _ in ctx.sors] == [("sor_0_30", 101.0, 99.5), ("sor_0_60", 103.0, 99.0)]
    sd = S.Side(1, ctx.o, ctx.h, ctx.l, ctx.c, 1)
    s0 = ctx.start
    t8 = S._lv_target_pools(ctx, sd, s0 + 8, p)                                         # after 00:30, before 01:00
    assert (101.0, s0 + 6) in t8 and not any(v == 103.0 for v, _ in t8)
    t14 = S._lv_target_pools(ctx, sd, s0 + 14, p)
    assert (103.0, s0 + 12) in t14
    k8 = S._sell_side(ctx, sd, "AM", s0 + 8, False, p)
    k14 = S._sell_side(ctx, sd, "AM", s0 + 14, False, p)
    assert k8.get("sor_0_30") == 99.5 and "sor_0_60" not in k8 and k14.get("sor_0_60") == 99.0
    assert S._level_created(ctx, "sor_0_60", "AM") == s0 + 12
    assert not S._lv_target_pools(ctx, sd, s0 + 14, replace(p, session_ors=()))
    short = S.Side(-1, ctx.o, ctx.h, ctx.l, ctx.c, 1)
    assert S._sell_side(ctx, short, "AM", s0 + 14, False, p).get("sor_0_60") == -103.0           # the mirror: the HIGH is the sell-side pool of a short
    assert {c[2] for c in L3.lock_cands(ctx, p, 570, s0 + 14)} >= {"sor_0_30_h", "sor_0_60_l"}
    with pytest.raises(ValueError):
        Params(session_ors=((0,),))
    with pytest.raises(ValueError):
        Params(session_ors=((1500, 30),))


# --- L5-partial-redelivery (18) ---------------------------------------------------------------------------------------------

def _nwog_bars():
    """Open (near) 98, Friday close (far) 100, tick 0.25: far hit, back through to 98, a return to the CE 99 that closes back out, then a
    bearish FVG whose top (98.4) sits within a point of the gap edge 98."""
    rows = [
        (98.0, 98.4, 97.8, 98.2),     # 0 Sunday open
        (98.2, 100.1, 98.1, 99.9),    # 1 far edge reached
        (99.9, 99.95, 97.9, 98.0),    # 2 back through to the open side
        (98.0, 99.2, 97.95, 98.7),    # 3 returns to the CE 99, closes below it
        (98.7, 98.8, 98.4, 98.5),     # 4  c1 of the exit FVG (low 98.4)
        (98.5, 98.5, 97.2, 97.3),     # 5
        (97.3, 98.0, 97.0, 97.5),     # 6  high 98.0 < low[4] 98.4: a bearish FVG [98.0, 98.4]
    ]
    o, h, l, c = mk(rows)
    return o, h, l, c


def test_nwog_redelivery_state_machine():
    o, h, l, c = _nwog_bars()
    r = L.nwog_redelivery(o, h, l, c, 0, 98.0, 100.0, 0.25)
    assert r == (6, 98.4, None)                                                               # rebalanced at bar 6's close, the exit FVG's near edge 98.4
    assert L.nwog_redelivery(o, h, l, c, 0, 98.0, 100.0, 0.25, end=5) is None            # causal: not before the FVG formed
    # the far edge never reached: not rebalanced
    h2 = h.copy(); h2[1] = 99.0; h2[2] = 99.2
    assert L.nwog_redelivery(o, h2, l, c, 0, 98.0, 100.0, 0.25) is None
    # the return runs all the way back to the far edge: a full redelivery restarts the sequence
    h3 = h.copy(); h3[3] = 100.2
    assert L.nwog_redelivery(o, h3, l, c, 0, 98.0, 100.0, 0.25) is None
    # an exit FVG far from the gap edge (> 1 pt) does not count
    assert L.nwog_redelivery(o, h, l, c, 0, 98.0, 100.0, 0.25, pts=0.2) is None
    # mirror: a gap with the far edge below the open
    assert L.nwog_redelivery(-o, -l, -h, -c, 0, -98.0, -100.0, 0.25) == (6, -98.4, None)


def test_nwog_rebalanced_drops_far_edge():
    """Synthetic week following the four steps: the CE and the Friday close are missing from the ladder; the near edge and the exit FVG's edge stay."""
    p = Params(**BASE, nwog_rebalanced=True, gap_mode="ict")
    df = day([(100.0, 100.3, 99.7, 100.0)] * 30, start="09:30")
    ctx = ctx_for(df, history(D0, n=8), p)
    gl = htf.GapList([("nwog", 120.0, 114.0, 117.0)])
    known = pd.Timestamp(D0, tz=NY) + pd.Timedelta(hours=1)
    gl.reb = {(120.0, 114.0): (known, 114.0, 116.0)}
    ctx.gaps = gl
    sd = S.Side(1, ctx.o, ctx.h, ctx.l, ctx.c, 1)
    k0 = S._idx_at(ctx, 570)
    i = k0 + 10                                                                        # 09:30 + 50 min, after `known`
    lv = [v for v, _ in S._targets(ctx, sd, i, 97.0, [], p, ext_i=i)]
    assert 114.0 in lv and 116.0 in lv and 117.0 not in lv and 120.0 not in lv
    plain = [v for v, _ in S._targets(ctx, sd, i, 97.0, [], replace(p, nwog_rebalanced=False), ext_i=i)]
    assert 114.0 in plain and 117.0 in plain and 120.0 in plain and 116.0 not in plain
    # before the sequence completed (known later than the bar) the usual ladder applies - no look-ahead
    gl2 = htf.GapList([("nwog", 120.0, 114.0, 117.0)])
    gl2.reb = {(120.0, 114.0): (pd.Timestamp(D0, tz=NY) + pd.Timedelta(hours=12), 114.0, 116.0)}
    ctx.gaps = gl2
    lv2 = [v for v, _ in S._targets(ctx, sd, i, 97.0, [], p, ext_i=i)]
    assert 117.0 in lv2 and 120.0 in lv2
    assert htf.gaps_for_day(pd.DataFrame(), D0) == []


def test_htf_nwog_rebalanced_table():
    fri = pd.date_range("2026-06-19 16:45", periods=2, freq="5min", tz=NY)
    sun = pd.date_range("2026-06-21 18:00", periods=7, freq="5min", tz=NY)
    o, h, l, c = _nwog_bars()
    idx = fri.append(sun)
    rows = [(100.5, 100.6, 100.1, 100.2), (100.2, 100.3, 99.9, 100.0)] + list(zip(o, h, l, c))
    a = np.array(rows, float)
    df = pd.DataFrame({"open": a[:, 0], "high": a[:, 1], "low": a[:, 2], "close": a[:, 3], "volume": 1.0}, index=idx)
    og = htf.opening_gaps(df)
    assert len(og) == 1 and og.high.iloc[0] == 100.0 and og.low.iloc[0] == 98.0
    reb = htf.nwog_rebalanced(df, og, 0.25)
    assert list(reb) == [(100.0, 98.0)]
    when, near, exit_, until = reb[(100.0, 98.0)]
    assert near == 98.0 and exit_ == 98.4 and until is None and when == idx[-1] + pd.Timedelta(minutes=5)           # the close of the FVG-completing bar
    g = htf.gaps_for_day(og, date(2026, 6, 22), reb=reb)
    assert g == [("nwog", 100.0, 98.0, 99.0)] and g.reb == reb
    assert htf.nwog_rebalanced(df, None, 0.25) == {}
    # causal: the table of the data up to a bar equals the full table where it is known by then, and has nothing before the sequence completed
    assert htf.nwog_rebalanced(df.iloc[:-1], og, 0.25) == {}
    assert htf.nwog_rebalanced(df, og, 0.25) == reb


# --- L5-cfd-nwog-mapping (68) -----------------------------------------------------------------------------------------------

def test_cfd_nwog_without_sunday_bars():
    """A CFD feed with no Sunday-evening bars: NaN / unavailable under "sunday_bars", the Monday 09:30 variant is an explicit choice."""
    fri = pd.date_range("2026-06-19 15:50", periods=4, freq="5min", tz=NY)                # last print 16:05
    mon = pd.date_range("2026-06-22 04:00", periods=140, freq="5min", tz=NY)               # no Sunday bars: Monday 04:00 onwards
    idx = fri.append(mon)
    n = len(idx)
    px = np.full(n, 100.0)
    px[4:] = 98.0
    df = pd.DataFrame({"open": px, "high": px + 0.2, "low": px - 0.2, "close": px, "volume": 1.0}, index=idx)
    g = htf.opening_gaps(df, nwog_src="sunday_bars")
    assert len(g) == 0 and g.attrs["nwog_unavailable"] == [mon[0]]                      # flagged unavailable, never guessed
    assert len(htf.opening_gaps(df)) == 0                                               # "auto" = the built behaviour (no Sunday bars -> no NWOG)
    m = htf.opening_gaps(df, nwog_src="monday_0930")
    assert len(m) == 1 and m.kind.iloc[0] == "nwog" and m.high.iloc[0] == 100.0 and m.low.iloc[0] == 98.0
    assert m.known.iloc[0] == pd.Timestamp("2026-06-22 09:35", tz=NY)                   # known when the 09:30 bar has closed
    assert htf.gaps_for_day(m, date(2026, 6, 23)) == [("nwog", 100.0, 98.0, 99.0)]
    with pytest.raises(ValueError):
        htf.opening_gaps(df, nwog_src="x")
    # a feed WITH Sunday bars: "none" drops the NWOGs, the others keep them
    sun = pd.date_range("2026-06-21 18:00", periods=5, freq="5min", tz=NY)
    idx2 = fri.append(sun)
    p2 = np.array([100, 100, 100, 100, 98, 98, 98, 98, 98], float)
    d2 = pd.DataFrame({"open": p2, "high": p2 + 0.2, "low": p2 - 0.2, "close": p2, "volume": 1.0}, index=idx2)
    assert len(htf.opening_gaps(d2)) == 1 and len(htf.opening_gaps(d2, nwog_src="sunday_bars")) == 1
    assert len(htf.opening_gaps(d2, nwog_src="none")) == 0
    assert htf.opening_gaps(d2, nwog_src="sunday_bars").attrs["nwog_unavailable"] == []


# --- A2-open-float (definitions 72) -----------------------------------------------------------------------------------------

def _hl_rows(hl):
    return [((h + l) / 2, h, l, (h + l) / 2) for h, l in hl]


_FLOAT_HL = [(101, 99), (102, 100), (103, 101), (105, 102), (104, 101), (103, 100), (102, 99), (102.5, 99.5), (103, 100.5),
             (101, 98), (100, 97), (99.5, 96), (99, 96.5), (99.8, 96.2), (99.5, 95.5), (99, 95.2), (98, 95.1), (97.5, 95.05),
             (97, 95.02), (96.5, 95.0)] + [(96.0, 95.2)] * 40


def test_open_float_pools_after_a_denied_continuation():
    p = Params(**BASE, open_float_pools=True)
    df = day(_hl_rows(_FLOAT_HL), start="09:30")
    ctx = ctx_for(df, history(D0, n=8), p)
    sd = S.Side(1, ctx.o, ctx.h, ctx.l, ctx.c, 1)
    k0 = S._idx_at(ctx, 570)
    i = k0 + 55
    fl = L3.float_pools(ctx, sd, i, p, True)
    assert sorted(round(v, 1) for v, _ in fl) == [99.8, 103.0]                         # the short-term highs formed during the decline
    assert (103.0, k0 + 9) in fl
    # not denied yet (the low was made 6 bars ago): no float pools
    assert L3.float_pools(ctx, sd, k0 + 25, p, True) == []
    assert L3.float_pools(ctx, sd, i, replace(p, float_denied_bars=50), True) == []
    assert L3.float_pools(ctx, sd, i, replace(p, float_denied_adr=0.01), True) == []     # the chop is wider than the tolerance
    tg = S._targets(ctx, sd, i, 97.0, [], p, ext_i=i)
    assert (103.0, "pool") in tg and (103.0, "pool") not in S._targets(ctx, sd, i, 97.0, [], replace(p, open_float_pools=False), ext_i=i)
    # the mirror (a rally, no new high): the swing lows formed during the rally are the sell-side float
    up = day(_hl_rows([(200 - l, 200 - h) for h, l in _FLOAT_HL]), start="09:30")
    ctx2 = ctx_for(up, history(D0, n=8), p)
    sd2 = S.Side(1, ctx2.o, ctx2.h, ctx2.l, ctx2.c, 1)
    j = S._idx_at(ctx2, 570) + 55
    lows = L3.float_pools(ctx2, sd2, j, p, False)
    assert sorted(round(v, 1) for v, _ in lows) == [97.0, 100.2]
    keys = S._sell_side(ctx2, sd2, "AM", j, False, p)
    assert sum(1 for k in keys if k.startswith("float_lo")) == 2


# --- A11-htf-gap-own-tf (75) ------------------------------------------------------------------------------------------------

def test_balance_tf_own_vs_lower():
    """A weekly FVG is balanced only by weekly closes under "own" (the daily back-and-forth inside it is ignored); the legacy build judged it
    on the daily closes; "next_lower" judges a daily array on its 4h closes."""
    o = np.full(15, 105.0); h = np.full(15, 112.0); l = np.full(15, 101.0)
    c = np.full(15, 108.0); c[7] = 98.0                                                   # one daily close under the gap bottom (100)
    wo = np.array([105.0, 105.0, 105.0]); wc = np.array([105.0, 112.0, 111.0]); wl = [5, 10, 15]
    a = htf.Arr("bull", "fvg", "W", 110.0, 100.0, 105.0, 5)
    assert not htf._arr_alive(a, 14, o, h, l, c, wo, wc, wl, False)                     # legacy: the daily close at 98 killed it
    assert htf._arr_alive(a, 14, o, h, l, c, wo, wc, wl, False, bal="own")              # own: only completed weekly closes (112) count
    # a weekly close under the bottom does kill it
    wc2 = np.array([105.0, 99.0, 111.0])
    assert not htf._arr_alive(a, 14, o, h, l, c, wo, wc2, wl, False, bal="own")
    d = htf.Arr("bull", "fvg", "D", 110.0, 100.0, 105.0, 3)
    c2 = np.full(15, 108.0)
    lcl = [np.array([])] * 15
    lcl[5] = np.array([99.5, 101.0])                                                    # 4h bodies dip under the gap bottom inside day 5
    assert htf._arr_alive(d, 14, o, h, l, c2, wo, wc, wl, False, bal="own")             # a daily FVG with 4h bodies inside stays open under "own"
    assert not htf._arr_alive(d, 14, o, h, l, c2, wo, wc, wl, False, bal="next_lower", lcl=lcl)
    # the table runs with each mode; "own" is the default (review fix #75: the spec default), "legacy" the earlier behaviour
    x, _ = B.synthetic(start="2026-04-06", end="2026-05-15", tf=5, seed=3)
    base = htf.table(x, 1.0)
    pd.testing.assert_frame_equal(base, htf.table(x, 1.0, balance_tf="own"))
    for mode in ("legacy", "next_lower"):
        assert len(htf.table(x, 1.0, balance_tf=mode)) == len(base)


# --- A7-immediate-rebalance-definition (85) ---------------------------------------------------------------------------------

_IR_DAILY = [(98, 100, 97, 99), (105, 110, 105, 109), (109, 112, 108, 111), (110, 111, 100.2, 106)]


def test_immediate_rebalance_definitions():
    # Mon high 100, Tue / Wed print higher (Wed the up-close displacement), Thursday opens 110 and trades down to Monday's high
    o, h, l, c = mk(_IR_DAILY)
    assert L.immediate_rebalances(o, h, l, c, 0.25) == []                               # a7: yesterday's (Tuesday's) high 110 is far from the low
    r = L.immediate_rebalances(o, h, l, c, 0.25, "open_space")
    assert r == [(3, "bull")]                                                           # found only under open_space: the candle that bounds the open space
    # stopping short is a breakaway gap, not this
    l2 = l.copy(); l2[3] = 101.0
    assert L.immediate_rebalances(o, h, l2, c, 0.25, "open_space") == []
    # through the level by more than the overshoot, or a body close through it
    l3 = l.copy(); l3[3] = 99.0
    assert L.immediate_rebalances(o, h, l3, c, 0.25, "open_space") == []
    c4 = c.copy(); c4[3] = 99.8
    assert L.immediate_rebalances(o, h, l, c4, 0.25, "open_space") == []
    assert L.immediate_rebalances(o, h, l3, c, 0.25, "open_space", overshoot_ticks=8) == [(3, "bull")]
    # the bearish mirror
    assert L.immediate_rebalances(-o, -l, -h, -c, 0.25, "open_space") == [(3, "bear")]
    # zero width: a large c2 and low[c3] == high[c1] to the tick
    flat = [(100.0, 101.0, 99.5, 100.5)] * 22
    rows = flat + [(100.0, 101.0, 99.5, 100.5), (100.5, 105.0, 100.4, 104.5), (104.5, 106.0, 101.0, 105.5)]
    assert L.immediate_rebalances(*mk(rows), 0.25, "zero_width") == [(24, "bull")]
    rows[-1] = (104.5, 106.0, 101.4, 105.5)
    assert L.immediate_rebalances(*mk(rows), 0.25, "zero_width") == []                   # 0.4 off: not to the tick
    rows[-1] = (104.5, 106.0, 101.0, 105.5)
    rows[-2] = (100.5, 101.9, 100.4, 100.9)                                              # c2 is no large candle
    assert L.immediate_rebalances(*mk(rows), 0.25, "zero_width") == []
    with pytest.raises(ValueError):
        L.immediate_rebalances(o, h, l, c, 0.25, "x")
    # Side.irs reads the configured definition
    assert S.Side(1, *mk(_IR_DAILY), 1, ir_cfg=("open_space", 2.0, 1.5)).irs(0.25) == [3]
    assert S.Side(1, *mk(_IR_DAILY), 1).irs(0.25) == []


# --- A12-open-vs-wick-gap-criterion / A5-twice-traded-not-fvg (90 / 167) ----------------------------------------------------

def test_ob_anchor_gap_presence():
    ob_c = (10.4, 11.5, 9.5, 9.6)              # the down-close OB candle with an upper wick (open 10.4, high 11.5)
    # (a) the prior bar's wick overlaps the wick area -> traded through twice, closed in: anchor on the open
    closed = [(10.0, 11.0, 9.8, 10.2), ob_c, (9.6, 10.5, 9.4, 10.3), (10.3, 11.0, 10.2, 10.9)]
    assert L.ob_anchor_state(*mk(closed), 1, 1, 3) == "closed_in"
    # (b) nothing overlaps the wick area and the displacement left an FVG above the block: the wick extreme / the gap
    gap = [(10.0, 10.3, 9.8, 10.2), ob_c, (9.6, 12.5, 9.6, 12.4), (12.4, 13.5, 12.0, 13.4)]
    assert L.ob_anchor_state(*mk(gap), 1, 1, 3) == "gap"
    # (c) neither: the A12 rule decides
    rule = [(10.0, 10.3, 9.8, 10.2), ob_c, (9.6, 11.0, 9.5, 10.9), (10.9, 11.2, 10.6, 11.0)]
    assert L.ob_anchor_state(*mk([(10.0, 10.3, 9.8, 10.2), ob_c, (9.6, 10.2, 9.5, 10.1), (10.1, 10.3, 9.9, 10.2)]), 1, 1, 3) == "rule"
    # no upper wick at all
    assert L.ob_anchor_state(*mk([(10.0, 10.3, 9.8, 10.2), (10.4, 10.4, 9.5, 9.6)]), 1, 1, 1) == "closed_in"
    # the entry price follows it (and the default rule is untouched)
    ob = dict(j=1, k=1, body_top=10.4, body_low=9.6, mt=10.0, hi=11.5, lo=9.5)
    p = Params(**BASE, ob_anchor_rule="gap_presence", ob_zone="range")
    sd = S.Side(1, *mk(closed), 1)
    assert EN.ob_entry_price(ob, sd, p, 3) == 10.4                                     # closed in -> the open, even with ob_zone="range"
    sd2 = S.Side(1, *mk(gap), 1)
    assert EN.ob_entry_price(ob, sd2, replace(p, ob_zone=""), 3) == 11.5               # an untraded gap keeps the wick extreme
    assert EN.ob_entry_price(ob, sd, replace(p, ob_anchor_rule="wick_len"), 3) == 11.5  # the old rule (ob_zone="range")
    assert EN.ob_entry_price(ob, sd, p) == 11.5                                        # without the bar (no i) the old rule applies


# --- A12-tf-relative-ob (91) ------------------------------------------------------------------------------------------------

def test_htf_ob_ltf_drill():
    # a bearish FVG (bar 4 high 97 < bar 2 low 103); the swing-high candle (bar 2) is a DOWN-close daily candle - the wrong colour
    o, h, l, c = mk([(100, 101, 99, 100.5), (100, 105, 99.5, 104), (106, 110, 103, 104), (103, 103.5, 94.5, 95), (95, 97, 92, 93), (93, 94, 90, 91)])
    sub = mk([(104, 107, 103.5, 106), (106, 110, 105.5, 107), (107, 108, 103, 103.5)])        # 1h bars inside bar 2: the high is on bar 1, an up-close
    assert not [a for a in htf._arrays(o, h, l, c, "D", lambda i: i + 1) if a.typ == "ob" and a.top == 110.0]
    arrs = htf._arrays(o, h, l, c, "D", lambda i: i + 1, drill=lambda j: sub if j == 2 else None)
    ob = [a for a in arrs if a.typ == "ob" and a.kind == "bear"]
    assert ob and all((a.top, a.bottom, a.ce) == (110.0, 106.0, 106.5) for a in ob)         # the open .. the high of the last up-close 1h bar, MT = its body midpoint
    # no LTF bars -> the standard block
    arrs0 = htf._arrays(o, h, l, c, "D", lambda i: i + 1, drill=lambda j: None)
    assert [(a.typ, a.top) for a in arrs0] == [(a.typ, a.top) for a in htf._arrays(o, h, l, c, "D", lambda i: i + 1)]
    # the table builds the provider from the bars (1h per session)
    x, _ = B.synthetic(start="2026-04-06", end="2026-05-15", tf=5, seed=3)
    assert len(htf.table(x, 1.0, htf_ob_ltf_drill=True)) == len(htf.table(x, 1.0))


# --- A6-breakaway-depth-qualification (93) ----------------------------------------------------------------------------------

def _bk_bars(retrace_low):
    # a bullish gap [100, 110] formed at bar 2 (high of bar 0 = 100, low of bar 2 = 110); bar 3 retraces to `retrace_low`; bar 4 makes a new high
    return mk([(97, 100, 96, 99), (99.5, 114, 99, 113), (112, 116, 110, 115), (114, 114.5, retrace_low, 112), (112, 118, 111, 117)])


def test_breakaway_state_machine_and_depth():
    o, h, l, c = _bk_bars(101.0)
    z = L.fvgs(h, l)[0]
    assert (z.top, z.bottom, z.i) == (110.0, 100.0, 2)
    assert L.bk_state(h, l, z, 2) == ("candidate", -1)
    assert L.bk_state(h, l, z, 3, "any_open") == ("retraced", 3)
    assert L.bk_state(h, l, z, 4, "any_open") == ("qualified", 4)                       # a 90% fill followed by a new high qualifies under any_open
    assert L.bk_state(h, l, z, 4, "ce") == ("dead", 3)                                  # ... not under ce (past the 50%)
    # a full fill is never breakaway
    o2, h2, l2, c2 = _bk_bars(99.0)
    assert L.bk_state(h2, l2, z, 4, "any_open")[0] == "dead"
    # a shallow retrace qualifies under both
    o3, h3, l3, c3 = _bk_bars(106.0)
    assert L.bk_state(h3, l3, z, 4, "ce") == ("qualified", 4)
    # no new high after the retrace: stays retraced
    h4 = h.copy(); h4[4] = 115.0
    assert L.bk_state(h4, l, z, 4, "any_open")[0] == "retraced"
    # a BPR directly beyond the far edge limits the retrace to the CE even under any_open
    bpr = L.Zone("bull", 101.0, 98.0, 3, 0)
    assert L.bk_state(h, l, z, 4, "any_open", [bpr], True)[0] == "dead"
    assert L.bk_state(h, l, z, 4, "any_open", [bpr], False)[0] == "qualified"
    with pytest.raises(ValueError):
        L.bk_state(h, l, z, 4, "x")
    # targets.breakaway_gap: the default (ce, no state machine) is the old test; bk_depth / bk_state change it
    sd = S.Side(1, o, h, l, c, 1)
    p = Params(**BASE)
    assert TP.breakaway_gap(sd, 0, 4) is None and TP.breakaway_gap(sd, 0, 4, p) is None             # past the CE
    assert TP.breakaway_gap(sd, 0, 4, replace(p, bk_depth="any_open", breakaway="tag")) is not None                    # any portion left open
    assert TP.breakaway_gap(sd, 0, 4, replace(p, bk_depth="any_open", bk_state=True, breakaway="tag")) is not None      # qualified
    assert TP.breakaway_gap(sd, 0, 3, replace(p, bk_depth="any_open", bk_state=True, breakaway="tag")) is None          # retraced only: not yet a trail level
    assert TP.breakaway_gap(sd, 0, 3, replace(p, bk_depth="any_open", breakaway="tag")) is not None


# --- A9-vi-breakaway (95) ---------------------------------------------------------------------------------------------------

def _vi_cons():
    flat = [(100.0, 100.5, 99.8, 100.3)] * 8
    return mk(flat + [(100.3, 104.6, 100.2, 104.5), (105.0, 107.2, 104.5, 107.0)])


def test_vi_breakaway_context():
    o, h, l, c = _vi_cons()
    z = [v for v in L.volume_imbalances(o, h, l, c) if v.i == 9][0]
    assert (z.bottom, z.top) == (104.5, 105.0)
    assert L.vi_breakaway(o, h, l, c, z) == "consolidation"                              # the candles leaving a flat range
    trend = [(100.0 + 1.5 * k, 101.6 + 1.5 * k, 99.9 + 1.5 * k, 101.4 + 1.5 * k) for k in range(8)]
    o2, h2, l2, c2 = mk(trend + [(111.0, 115.2, 110.9, 115.0), (115.5, 117.2, 115.0, 117.0)])
    z2 = [v for v in L.volume_imbalances(o2, h2, l2, c2) if v.i == 9][0]
    assert L.vi_breakaway(o2, h2, l2, c2, z2) == ""                                      # a trend is no consolidation
    assert L.vi_breakaway(o2, h2, l2, c2, z2, broke=9) == "mss"
    assert L.vi_breakaway(o2, h2, l2, c2, z2, broke=8) == "mss"
    assert L.vi_breakaway(o2, h2, l2, c2, z2, broke=4) == ""
    # inside the displacement leg beyond its 50% (sweep extreme 99, leg high 118)
    assert L.vi_breakaway(o2, h2, l2, c2, z2, ext=99.0, ext_i=2, leg_hi=118.0) == "leg"
    assert L.vi_breakaway(o2, h2, l2, c2, z2, ext=99.0, ext_i=8, leg_hi=118.0) == ""
    # the engine: a breakaway VI is no entry zone (vi_entries); without the switch it is
    sd = S.Side(1, o, h, l, c, 1)
    sw = dict(ext_i=1, ext=99.8, broke=None)
    p = Params(**BASE, vi_entries=True)
    assert [z_.i for z_ in EN.extra_entry_zones(sd, sw, 9, p)] == [9]
    assert EN.extra_entry_zones(sd, sw, 9, replace(p, vi_breakaway=True)) == []
    # an opposing (bearish) VI that left a consolidation is no retrace target for a long
    sdb = S.Side(1, -o, -l, -h, -c, 1)
    zb = [v for v in sdb.vis("bear") if v.i == 9][0]
    assert L3.opp_vi_is_breakaway(sdb, zb, 9)
    ctx0 = type("C", (), {})()
    pt = replace(p, vi_targets=True)
    assert (zb.bottom, "array") in S._lv_finish_targets(ctx0, sdb, 9, -200.0, pt, ())
    assert (zb.bottom, "array") not in S._lv_finish_targets(ctx0, sdb, 9, -200.0, replace(pt, vi_breakaway=True), ())
    # a later body laid fully across it: it was not breakaway after all
    o3, h3, l3, c3 = mk(list(zip(o, h, l, c)) + [(106.0, 106.2, 103.9, 104.0)])
    sd3 = S.Side(1, o3, h3, l3, c3, 1)
    assert [z_.i for z_ in EN.extra_entry_zones(sd3, sw, 10, replace(p, vi_breakaway=True))] == [9]


# --- A6-gap-hierarchy-common (96) -------------------------------------------------------------------------------------------

def test_gap_classes_and_cc_common():
    # a leg from the sweep extreme 95 (bar 1) to 115: g1 the first gap (breakaway), g2 near the middle (measuring), g3 high up (common)
    n = 40
    o = np.full(n, 105.0); h = o + 1; l = o - 1; c = o + 0.5
    h[1], l[1] = 100.0, 95.0
    sd = S.Side(1, o, h, l, c, 1)
    g1 = L.Zone("bull", 101.5, 101.0, 3, 2)
    g2 = L.Zone("bull", 106.0, 104.0, 12, 11)
    g3 = L.Zone("bull", 113.0, 112.0, 20, 19)
    sd.gaps = [g1, g2, g3]
    p = Params(**BASE)
    assert L3.gap_class(sd, 1, 95.0, g1, 30, p, leg_hi=115.0) == "breakaway"
    assert L3.gap_class(sd, 1, 95.0, g2, 30, p, leg_hi=115.0) == "measuring"
    assert L3.gap_class(sd, 1, 95.0, g3, 30, p, leg_hi=115.0) == "common"
    # under bk_state an unqualified first gap is no breakaway
    ps = replace(p, bk_state=True, bk_depth="any_open", breakaway="tag")
    assert L3.gap_class(sd, 1, 95.0, g1, 30, ps, leg_hi=115.0) == "common"
    # trail_skip_common
    pos = dict(ext_i=1, ext=95.0, leg=(95.0, 115.0))
    assert L3.trail_ok(sd, pos, g3, 30, p) and not L3.trail_ok(sd, pos, g3, 30, replace(p, trail_skip_common=True))
    assert L3.trail_ok(sd, pos, g2, 30, replace(p, trail_skip_common=True))
    # the CC body gap (cc04_010): open below the prior close with the whole candle under it
    z = L.common_gaps_cc(*mk([(100.0, 101.5, 99.5, 101.0), (99.5, 100.4, 98.8, 99.0)]))
    assert [(g.kind, g.top, g.bottom, g.tag) for g in z] == [("bear", 101.0, 99.5, "cc_common")]
    assert L.common_gaps_cc(*mk([(100.0, 101.5, 99.5, 101.0), (99.5, 101.4, 98.8, 99.0)])) == []     # a range closes the space
    sdc = S.Side(1, *mk([(100.0, 100.6, 99.5, 99.0), (99.5, 100.9, 99.2, 100.8), (101.0, 102.0, 100.95, 101.8)]), 1)
    assert L3.cc_common_tag(sdc, 100.97, 2) and not L3.cc_common_tag(sdc, 100.97, 1)


# --- L7-org-close-and-direction (105) ---------------------------------------------------------------------------------------

def test_org_close_and_direction():
    # the ORG closes on the last RTH bar before the session close: for ES (session_close 975) the 16:10 5m bar (it holds the 16:14 1m bar)
    n = (16 * 60 + 30 - 570) // 5                                                       # 09:30 .. 16:25, the closes count up
    rows = [(100.0 + k, 100.5 + k, 99.5 + k, 100.0 + k) for k in range(n)]
    x = frame(D0, rows, 5, "09:30")
    pr = B.prepare(x, 5, "ES", Params(**FUT, session_close=975, price_frame="raw"))
    last_es = float(x.close[x.index.strftime("%H:%M") == "16:10"].iloc[0])
    assert pr.closes[D0] == last_es                                                     # the 16:10 bar holds the 16:14 1m bar; 16:15+ is settlement time
    pr2 = B.prepare(x, 5, "SPY", Params(**FUT, session_close=960, price_frame="raw"))
    assert pr2.closes[D0] == float(x.close[x.index.strftime("%H:%M") == "15:55"].iloc[0])      # SPX / SPY: the 15:59 1m bar = the 15:55 5m bar
    # discount: the open below the prior close (ORG high = the prior close, low = the open); premium above
    p = Params(**BASE)
    for op, want in ((98.0, "discount"), (102.0, "premium"), (100.0, "")):
        hist = history(D0, n=8)
        df = day([(op, op + 0.3, op - 0.3, op)] * 5, start="09:30", base=op)
        ctx = ctx_for(df, hist, p, closes={hist[-1].index[0].date(): 100.0})
        i = S._idx_at(ctx, 570) + 2
        assert L3.org_dir(ctx, i) == want
        if want:
            assert (max(ctx.org[-1]), min(ctx.org[-1])) == (max(100.0, op), min(100.0, op))
        assert L3.org_dir(ctx, i - 4) == ""                                              # before 09:30 the ORG is not known


# --- new-single-candle-daily-inefficiency (116) -----------------------------------------------------------------------------

def _spr_bars():
    flat = [(100.0, 101.0, 99.0, 100.2)] * 12
    return flat + [(103.0, 112.0, 105.0 - 2.0, 111.5)]                 # a large up candle: low 103 > every earlier high (101)


def test_single_pass_range_zone_and_draw():
    o, h, l, c = mk(_spr_bars() + [(111.0, 111.5, 109.0, 110.0), (110.0, 110.5, 108.5, 109.0)])
    zs = L.single_pass_ranges(o, h, l, c)
    assert len(zs) == 1
    z = zs[0]
    assert (z.kind, z.bottom, z.top, z.i, z.tag) == ("bull", 103.0, 112.0, 12, "spr")
    assert z.levels == pytest.approx((103.0, 105.25, 107.5, 109.75, 112.0)) and z.mid == 107.5       # 0 / 25 / 50 / 75 / 100% and the CE
    # one of the five bars before it printed above its low: it was traded through before - no single pass
    rows = _spr_bars()
    rows[9] = (100.0, 103.5, 99.0, 100.2)
    assert L.single_pass_ranges(*mk(rows)) == []
    # a small candle is no large candle
    rows = _spr_bars()
    rows[-1] = (103.0, 104.0, 102.5, 103.6)
    assert L.single_pass_ranges(*mk(rows)) == []
    # bearish mirror
    mo, mh, ml, mc = mk(_spr_bars())
    zb = L.single_pass_ranges(-mo, -ml, -mh, -mc)
    assert len(zb) == 1 and zb[0].kind == "bear" and zb[0].levels[0] == pytest.approx(-103.0)
    # the daily arrays carry it as typ "spr"; the table is unchanged without the switch and gains a draw below with it
    arrs = htf._arrays(o, h, l, c, "D", lambda i: i + 1, spr=True)
    sp = [a for a in arrs if a.typ == "spr"]
    assert len(sp) == 1 and sp[0].ce == 107.5 and sp[0].known == 13 and sp[0].levels[1] == pytest.approx(105.25)
    assert not [a for a in htf._arrays(o, h, l, c, "D", lambda i: i + 1) if a.typ == "spr"]
    # the draw ladder: CE, then the lower quadrant (25%), then the candle low; mirrored for a down candle; nothing once traded through
    a_ = sp[0]
    assert htf.spr_target(a_, 108.0, 111.0) == 107.5                                     # untouched: the CE
    assert htf.spr_target(a_, 107.0, 111.0) == pytest.approx(105.25)                     # the CE traded: the lower quadrant
    assert htf.spr_target(a_, 104.0, 111.0) == 103.0                                     # the quadrant traded: the candle low
    assert htf.spr_target(a_, 103.0, 111.0) is None                                      # traded back down through it
    assert htf.spr_target(a_, 108.0, 106.0) == pytest.approx(105.25)                     # price already under the CE: the next level down
    mirror = htf._arrays(-o, -l, -h, -c, "D", lambda i: i + 1, spr=True)
    sb = [a for a in mirror if a.typ == "spr"][0]
    assert sb.kind == "bear" and htf.spr_target(sb, -108.0, -111.0) == -107.5 and htf.spr_target(sb, -107.0, -111.0) == pytest.approx(-105.25)
    # the table is unchanged without the switch, has the same shape with it (the daily FVG of the same candle is usually the nearer draw)
    flat = [(100.0, 101.0, 99.0, 100.2)] * 9
    days_ = flat + [(103.0, 112.0, 102.5, 111.5)] + [(110.0, 111.5, 105.0, 111.0)] * 3
    df = daily_df(days_)
    off = htf.table(df, 1.0)
    on = htf.table(df, 1.0, single_pass_draw=True)
    assert list(on.index) == list(off.index) and list(on.columns) == list(off.columns)
    assert not any("spr" in str(x) for x in off.draw_dn_name)


# --- A5-vi-extended-ce (117) ------------------------------------------------------------------------------------------------

def test_vi_link_extends_the_zone_and_its_ce():
    g = L.Zone("bull", 105.0, 103.0, 5, 4)
    n = 10
    p = Params(**BASE, fvg_vi_extend=True)
    h = np.full(n, 107.0); l = np.full(n, 100.0); o = np.full(n, 104.0); c = np.full(n, 104.5)
    sd = S.Side(1, o, h, l, c, 1)
    inside = L.Zone("bull", 104.0, 103.5, 5, 5)
    assert L3.vi_link(sd, g, inside, 0.25, p) == "inside"
    up = L.Zone("bull", 108.0, 105.6, 6, 6)                                          # a VI 0.6 above the gap top: not joined by the bodies ...
    l[5] = 105.1                                                                     # ... but the candle under it reaches the gap top (a wick link)
    assert L3.vi_link(sd, g, up, 0.25, p) == "up"
    assert L3.vi_link(sd, g, up, 0.25, replace(p, fvg_vi_extend_ce=False)) == ""      # the old build needed a body link
    down = L.Zone("bull", 102.0, 100.5, 7, 7)
    h[7] = 100.0
    assert L3.vi_link(sd, g, down, 0.25, p) == ""
    h[7] = 102.9                                                                     # the VI's upper candle reaches the gap bottom
    assert L3.vi_link(sd, g, down, 0.25, p) == "down"
    body = L.Zone("bull", 105.2, 105.0, 6, 6)                                        # body-joined (within a tick): both builds extend
    assert L3.vi_link(sd, g, body, 0.25, replace(p, fvg_vi_extend_ce=False)) == "up"
    # the CE of the extended zone = (near edge + far edge) / 2: the engine stores (top + bottom) / 2 of the extended zone
    top, bottom = max(g.top, up.top), min(g.bottom, g.bottom)
    assert (top + bottom) / 2 == pytest.approx(105.5)


# --- A11-balanced-range-body-filled (118) -----------------------------------------------------------------------------------

_BAL = [(100.2, 101.0, 100.0, 100.8), (100.8, 101.2, 100.3, 100.5), (100.5, 101.1, 100.1, 100.9), (100.9, 101.2, 100.4, 100.6),
        (100.6, 104.5, 100.5, 104.2)]


def test_balanced_range_body_filled():
    zs = L.balanced_bodies(*mk(_BAL))
    assert len(zs) == 1
    z = zs[0]
    assert (z.kind, z.bottom, z.top, z.i, z.tag) == ("bull", 100.2, 100.9, 4, "balanced_range")
    assert z.mid == pytest.approx(100.55) and z.levels == (pytest.approx(100.55),)       # bodies cover the zone height: an EQ
    assert L.balanced_bodies(*mk(_BAL[:4])) == []                                        # not left by displacement yet
    assert L.balanced_bodies(*mk(_BAL[:2] + [_BAL[4]])) == []                            # two candles are no range
    assert len(L.balanced_bodies(*mk(_BAL[:3] + [_BAL[4]]))) == 1                        # three overlapping candles, both ways, then the departure
    up_only = [(100.2, 101.0, 100.0, 100.8), (100.8, 101.2, 100.3, 101.0), (101.0, 101.1, 100.4, 100.9 + 0.2), _BAL[4]]
    assert L.balanced_bodies(*mk(up_only)) == []                                         # it never traded both ways
    mirror = L.balanced_bodies(*(-x for x in (mk(_BAL)[0], mk(_BAL)[2], mk(_BAL)[1], mk(_BAL)[3])))
    assert len(mirror) == 1 and mirror[0].kind == "bear"
    # the target ladder: nothing past the EQ of a redelivered range above price; its near edge and EQ are targets
    p = Params(**BASE, balanced_range=True)
    far = [(100.0, 100.3, 99.7, 100.0)] * 3 + [(100.1, 100.3, 99.9, 100.0)] * 12
    ctx = ctx_for(day(far, start="09:30"), history(D0, n=8), p)
    k0 = S._idx_at(ctx, 570)
    o, h, l, c = ctx.o.copy(), ctx.h.copy(), ctx.l.copy(), ctx.c.copy()
    # overwrite the range into the day: bodies 108.2 .. 108.9 (shifted by +8), then the departure up
    sh = np.array(_BAL, float) + 8.0
    for j in range(5):
        o[k0 + j], h[k0 + j], l[k0 + j], c[k0 + j] = sh[j]
    sd = S.Side(1, o, h, l, c, 1)
    i = k0 + 8
    out = L3.balanced_filter(sd, i, 100.0, [(120.0, "pool"), (110.0, "pool"), (108.0, "array")], p)
    assert (120.0, "pool") not in out and (110.0, "pool") not in out                      # beyond the EQ: not targeted without fresh displacement
    assert (108.0, "array") in out and any(abs(v - 108.55) < 1e-9 for v, _ in out)       # the near edge (108.2 body low ... EQ 108.55) stay
    assert L3.balanced_filter(sd, i, 100.0, [(120.0, "pool")], replace(p, balanced_range=False)) == [(120.0, "pool")]
    # fresh displacement (a close above the top since it formed): the range is behind us
    c2 = c.copy(); c2[k0 + 6] = 112.0
    sd2 = S.Side(1, o, h, l, c2, 1)
    assert (120.0, "pool") in L3.balanced_filter(sd2, i, 100.0, [(120.0, "pool")], p)


# --- M1-original-consolidation (123) ----------------------------------------------------------------------------------------

def test_smooth_edge_range_original_consolidation():
    # three bodies topping at 105.0 (the smooth edge) with wicks poking a bit higher; the range's lowest low is the other bound
    rows = [(103.0, 105.2, 102.0, 105.0), (104.0, 104.6, 101.5, 102.0), (102.0, 105.1, 101.0, 105.0), (103.0, 104.0, 100.5, 101.0),
            (101.0, 105.3, 100.0, 105.0), (103.0, 103.8, 102.0, 103.2)]
    o, h, l, c = mk(rows)
    r = L.smooth_edge_range(o, h, l, c, 0.5, 3)
    assert r is not None and r[0] == 105.0 and r[1] == 100.0 and r[2] >= 3
    assert L.smooth_edge_range(o, h, l, c, 0.5, 5) is None                                  # not enough touches
    assert L.smooth_edge_range(o, h, l, c, 0.05, 3)[0] == 105.0                              # exactly equal body tops need no tolerance
    # a body well above the candidate level means it is not the upper bound
    rows2 = list(rows)
    rows2[1] = (104.0, 108.0, 101.5, 107.0)
    assert L.smooth_edge_range(*mk(rows2), 0.5, 3) is None
    # the engine helper: around the parent swing high
    sd = S.Side(1, o, h, l, c, 1)
    p = Params(**BASE, orig_consol=True)
    q = L.Pivot(4, 105.3, 5)
    assert L3.orig_consol_level(sd, q, 5, 5, p) == 105.0
    assert L3.orig_consol_level(sd, q, 5, 5, replace(p, orig_consol_touches=5)) is None


# --- A21-consolidation-range-def (127) --------------------------------------------------------------------------------------

def test_consolidation_box_bodies_and_eq_touches():
    rows = [(100.0, 103.0, 99.0, 101.0), (101.0, 102.5, 99.5, 100.0), (100.0, 102.0, 99.0, 101.0), (101.0, 103.0, 99.2, 100.0),
            (100.0, 102.8, 99.1, 101.0), (101.0, 102.9, 99.0, 100.0)]
    o, h, l, c = mk(rows)
    b = L.consolidation_box(o, h, l, c, True, 2)
    assert (b["high"], b["low"], b["eq"]) == (101.0, 100.0, 100.5)                       # the max / min BODY, not the 103 / 99 wicks
    assert b["up"] >= 2 and b["down"] >= 2 and b["valid"]
    w = L.consolidation_box(o, h, l, c, False)
    assert (w["high"], w["low"]) == (103.0, 99.0)
    # one-sided: the EQ is never touched from below -> not a consolidation
    up_only = [(101.0 + 0.1 * k, 102.0 + 0.1 * k, 100.9 + 0.1 * k, 101.5 + 0.1 * k) for k in range(6)]
    assert L.consolidation_box(*mk(up_only), True, 2)["valid"] is False
    assert L.consolidation_box(*mk(up_only), True, 0)["valid"] is True
    # N8 consol_pools: the range high / low are the BODY edges of the bars up to the chop switching on
    p = Params(**BASE, consol_pools=True, consol_body_range=True)
    assert Params().consol_body_range is False                                           # review fix #127: opt-in, N8 as built by default
    df = day(rows * 2, start="09:30")
    ctx = ctx_for(df, history(D0, n=8), p)
    sd = S.Side(1, ctx.o, ctx.h, ctx.l, ctx.c, 1)
    k0 = S._idx_at(ctx, 570)
    ctx.chop = type("C", (), dict(rel_i=k0 + 9, hi=103.0, lo=99.0, on_at=k0 + 5))()
    i = k0 + 11
    assert LD.consol_pool(ctx, sd, i, True, p) == (101.0, k0 + 10)
    assert LD.consol_pool(ctx, sd, i, False, p) == (100.0, k0 + 10)
    assert LD.consol_pool(ctx, sd, i, True, replace(p, consol_body_range=False)) == (103.0, k0 + 10)
    assert LD.consol_pool(ctx, sd, i, True) == (103.0, k0 + 10)                          # no Params: the wick range of the chop test (the old call)
    ctx.chop = type("C", (), dict(rel_i=k0 + 9, hi=103.0, lo=99.0, on_at=k0 + 1))()
    assert LD.consol_pool(ctx, sd, i, True, p) is None                                    # too few EQ touches by then: no consolidation
    # the daily consolidations: one 6-day box in a 60-day trend gives its EQ
    N = 60
    o = np.zeros(N); h = np.zeros(N); l = np.zeros(N); c = np.zeros(N)
    for k in range(N):
        if 30 <= k <= 35:
            o[k], c[k] = (1300.0, 1301.0) if k % 2 == 0 else (1301.0, 1300.0)
            h[k], l[k] = 1302.0, 1299.0
        else:
            base = 1000.0 + 10.0 * k if k < 30 else 1300.0 + 10.0 * (k - 35)
            o[k], c[k], h[k], l[k] = base, base + 8.0, base + 9.0, base - 1.0
    boxes = L.daily_consolidations(o, h, l, c)
    assert [(b_["a"], b_["b"], b_["eq"]) for b_ in boxes] == [(30, 35, 1300.5)]


# --- A3-clean-high (128) ----------------------------------------------------------------------------------------------------

def test_equal_levels_need_separated_swings():
    assert L.equal_levels([100.0, 100.1], 0.2) == [100.1]                                # the old rule
    assert L.equal_levels([100.0, 100.1], 0.2, [10, 11], 3) == []                        # two adjacent equal bars: one swing, no pool at 3
    assert L.equal_levels([100.0, 100.1], 0.2, [10, 14], 3) == [100.1]                   # "slightly above" allowed: the pool is the higher one
    assert L.equal_clusters([100.0, 100.1, 105.0], 0.2, [10, 11, 30], 3) == []
    assert L.equal_clusters([100.0, 100.1, 105.0], 0.2, [10, 14, 30], 3) == [[0, 1]]
    # the engine's rel-eq list honours eq_min_sep_bars
    h = np.full(40, 99.0); l = h - 1.0
    h[10], h[13] = 100.0, 100.1
    o = c = (h + l) / 2
    sd = S.Side(1, o, h, l, c, 1)
    p = Params(**BASE)
    assert S._eq_levels(sd, 30, 0.3, False, p) == []                                       # the slightly higher second high took the first one (old rule)
    assert S._eq_levels(sd, 30, 0.3, False, replace(p, eq_min_sep_bars=4)) == []
    assert S._eq_levels(sd, 30, 0.3, False, replace(p, eq_min_sep_bars=3)) == [100.1]


# --- A1-impulse-swing-unit (134) --------------------------------------------------------------------------------------------

def test_impulse_legs_exclude_overlapping_legs():
    rows = [(101, 101.5, 100.5, 101.2), (101.2, 101.4, 100.2, 100.6), (100.6, 100.9, 100.0, 100.3),
            (100.4, 102.5, 100.4, 102.3), (102.4, 104.5, 102.4, 104.3), (104.4, 106.5, 104.4, 106.3), (106.4, 108.5, 106.4, 108.3),
            (108.4, 110.5, 108.4, 110.2), (110.2, 110.4, 109.0, 109.3), (109.3, 109.8, 108.7, 109.5), (109.5, 109.9, 108.9, 109.1),
            (109.1, 109.7, 108.8, 109.6), (109.6, 109.9, 109.0, 109.2), (109.2, 109.6, 109.0, 109.4), (109.4, 109.7, 109.1, 109.3)]
    o, h, l, c = mk(rows)
    legs = L.impulse_legs(h, l, o, c, 1)
    assert legs[0][:5] == (2, 7, 100.0, 110.5, True)                                      # the clear one-directional leg is kept
    assert all(lg[0] < 9 for lg in legs)                                                  # the overlapping chop that follows is not
    assert L.leg_is_impulsive(o, h, l, c, 2, 7, True, 1.4) and not L.leg_is_impulsive(o, h, l, c, 9, 12, True, 1.4)
    assert legs[0][5] == 8                                                                # known when the end swing is confirmed (n bars later)


# --- A12-void-up-down-ob (140) ----------------------------------------------------------------------------------------------

def _void_rt_bars():
    up = [(100.0, 103.0, 99.5, 102.8), (104.0, 107.0, 103.5, 106.8), (108.0, 111.0, 107.5, 110.8)]            # a void up: each low above the prior high
    dn = [(109.0, 109.5, 106.0, 106.5), (105.0, 105.5, 102.0, 102.5), (101.0, 101.5, 98.0, 98.5)]             # a void down through the same range
    return mk([(100.0, 100.5, 99.8, 100.2)] * 2 + up + dn + [(98.5, 99.5, 98.0, 99.0)])


def test_void_round_trip_order_block():
    o, h, l, c = _void_rt_bars()
    zs = L.void_round_trip_obs(o, h, l, c)
    assert len(zs) == 1
    z = zs[0]
    assert (z.kind, z.top, z.bottom, z.i, z.src, z.tag) == ("bear", 111.0, 99.5, 7, 2, "void_rt")
    assert z.top == 111.0 and z.bottom == 99.5 and z.mt == pytest.approx(105.25) and z.mid == pytest.approx(105.25)       # one bearish OB, MT = 50%
    # not one-sided (overlapping bars) or not back through the range: nothing
    o2, h2, l2, c2 = _void_rt_bars()
    l2[3] = 102.0
    assert L.void_round_trip_obs(o2, h2, l2, c2) == []
    o3, h3, l3, c3 = _void_rt_bars()
    l3[7] = 100.0; h3[7] = 100.5
    assert L.void_round_trip_obs(o3, h3, l3, c3) == []                                    # the drop stays above the rally's low: not the same range
    # causal: the zone is known at the bar the drop reaches the rally's low - more bars (or fewer after it) never change it
    cut = L.void_round_trip_obs(*(x[:8] for x in (o, h, l, c)))
    assert [(q.top, q.bottom, q.i) for q in cut] == [(111.0, 99.5, 7)]
    assert [q.i for q in L.void_round_trip_obs(*(x[:7] for x in (o, h, l, c)))] == []
    # bullish mirror
    zb = L.void_round_trip_obs(-o, -l, -h, -c)
    assert len(zb) == 1 and zb[0].kind == "bull" and zb[0].bottom == -111.0
    # the daily arrays carry it as an OB (ce = MT) only with the switch
    arrs = htf._arrays(o, h, l, c, "D", lambda i: i + 1, void_rt=True)
    ob = [a for a in arrs if a.typ == "ob" and a.kind == "bear" and a.top == 111.0 and a.bottom == 99.5]
    assert len(ob) == 1 and ob[0].ce == pytest.approx(105.25)
    assert not [a for a in htf._arrays(o, h, l, c, "D", lambda i: i + 1) if a.top == 111.0 and a.bottom == 99.5]


# --- A15-stoprun-variant (142) ----------------------------------------------------------------------------------------------

_STOPRUN = [(10.0, 11.0, 9.5, 10.5), (10.5, 11.5, 9.0, 9.2), (9.2, 10.5, 9.4, 10.3), (10.3, 12.0, 10.2, 11.8), (11.8, 11.9, 10.0, 10.1),
            (10.1, 10.3, 8.0, 8.4), (8.4, 9.5, 8.2, 9.4), (9.4, 12.6, 9.3, 12.4)]


def test_mitigation_stoprun_variant():
    o, h, l, c = mk(_STOPRUN)
    z = L.mitigation_blocks(o, h, l, c, 1, variant="stoprun")
    assert len(z) == 1
    assert (z[0].kind, z[0].top, z[0].bottom, z[0].src, z[0].i) == ("bull", 12.0, 11.8, 3, 7)      # U's upper wick: U.high .. U's body top
    assert L.mitigation_blocks(o, h, l, c, 1) == []                                                # the a15 failure swing needs a HIGHER low (the stops were run)
    zm = L.mitigation_blocks(o, h, l, c, 1, with_mt=True, variant="stoprun")
    assert zm[0].mt == pytest.approx((11.8 + 10.3) / 2)
    # no stop run (the low after the high holds above the prior low): not this variant
    rows = list(_STOPRUN)
    rows[5] = (10.1, 10.3, 9.6, 9.8)
    rows[6] = (9.8, 10.0, 9.7, 9.9)
    assert L.mitigation_blocks(*mk(rows), 1, variant="stoprun") == []
    # price must trade back above U
    assert L.mitigation_blocks(*mk(_STOPRUN[:7] + [(9.4, 11.0, 9.3, 10.9)]), 1, variant="stoprun") == []
    # the bearish mirror
    zb = L.mitigation_blocks(-o, -l, -h, -c, 1, variant="stoprun")
    assert len(zb) == 1 and zb[0].kind == "bear" and zb[0].bottom == -12.0 and zb[0].top == -11.8
    with pytest.raises(ValueError):
        L.mitigation_blocks(o, h, l, c, 1, variant="x")
    # Side.mitigations reads the variant
    sd = S.Side(1, o, h, l, c, 1, mit_def="stoprun")
    assert [(m.top, m.bottom) for m in sd.mitigations()] == [(12.0, 11.8)]
    assert S.Side(1, o, h, l, c, 1).mitigations() == []


# --- M4-failure-swing-no-new-extreme (156) ----------------------------------------------------------------------------------

def test_failure_swing_no_new_extreme():
    # key support K = 100: the first swing low 98 traded THROUGH it, the bounce high 105, then a higher low B = 99 (still below K)
    lows = [L.Pivot(5, 98.0, 6), L.Pivot(15, 99.0, 16)]
    highs = [L.Pivot(10, 105.0, 11)]
    assert L.failure_swing(highs, lows, 100.0, 2.0, 30) is None                            # m4: B must sit ABOVE the level (it failed to reach it)
    r = L.failure_swing(highs, lows, 100.0, 2.0, 30, 0, "no_new_extreme")
    assert r is not None and r[0].price == 99.0 and r[1].price == 105.0
    # K above B or below B: irrelevant
    assert L.failure_swing(highs, lows, 97.0, 2.0, 30, 0, "no_new_extreme") is not None
    # B makes a NEW extreme (lower than the first swing low): no failure swing
    assert L.failure_swing(highs, [L.Pivot(5, 98.0, 6), L.Pivot(15, 97.0, 16)], 100.0, 2.0, 30, 0, "no_new_extreme") is None
    # the first swing never reached K
    assert L.failure_swing(highs, [L.Pivot(5, 103.5, 6), L.Pivot(15, 104.0, 16)], 100.0, 2.0, 30, 0, "no_new_extreme") is None
    # the m4 definition is unchanged
    assert L.failure_swing(highs, [L.Pivot(15, 101.5, 16)], 100.0, 2.0, 30) is not None
    with pytest.raises(ValueError):
        L.failure_swing(highs, lows, 100.0, 2.0, 30, 0, "x")
    # the bearish case in the engine's side space is the mirror (negated prices)
    hs = [L.Pivot(5, 102.0, 6), L.Pivot(15, 101.0, 16)]          # key resistance 100: H1 102 traded through it, the drop to 95, H2 101 < H1
    ls = [L.Pivot(10, 95.0, 11)]
    r = L.failure_swing([L.Pivot(q.i, -q.price, q.known) for q in ls], [L.Pivot(q.i, -q.price, q.known) for q in hs], -100.0, 2.0, 30, 0, "no_new_extreme")
    assert r is not None and r[0].price == -101.0 and r[1].price == -95.0


# --- B21-data-range-fv-eq (161) ---------------------------------------------------------------------------------------------

def test_ipda_data_range_gaps_and_consolidation_eq():
    # 25 sessions: a rally with an FVG, then a 6-day box
    rows = []
    for k in range(10):
        b = 100.0 + 6.0 * k
        rows.append((b, b + 4.0, b - 0.5, b + 3.5))
    for k in range(7):
        rows.append((160.0, 162.0, 159.0, 161.0) if k % 2 == 0 else (161.0, 162.0, 159.0, 160.0))
    rows += [(160.0, 161.0, 150.0, 151.0)]
    hist = hist_from(rows, D0)
    dates = [x.index[0].date() for x in hist]
    p = Params(**BASE, ipda_pools=True, ipda_fv=True, ipda_consol_eq=True)
    ctx = type("C", (), dict(ipda_last=dates[-1]))()
    gaps, eqs = L3.build_ipda_x(ctx, hist, dates, None, p)
    assert eqs and abs(eqs[0][0] - 160.5) < 1e-9 and eqs[0][1] == 1.0
    assert gaps == [] or all(t_ > b_ for t_, b_ in gaps)
    # the engine: array targets (side space) and the range-day test
    c2 = ctx_for(day([(160.5, 160.8, 160.2, 160.5)] * 6, start="09:30", base=160.5), history(D0, n=8), p)
    c2.ipda_gaps, c2.ipda_ceq = [(150.0, 140.0)], [(160.5, 1.0)]
    sd = S.Side(1, c2.o, c2.h, c2.l, c2.c, 1)
    arr = L3.ipda_arrays(c2, sd, p)
    assert (140.0, "array") in arr and (145.0, "array") in arr and (160.5, "array") in arr
    i = S._idx_at(c2, 570) + 2
    assert L3.consol_eq_day(c2, p, i)                                                       # price hangs at the consolidation's EQ, no news
    c2.ipda_ceq = [(150.0, 1.0)]
    assert not L3.consol_eq_day(c2, p, i)
    c2.ipda_ceq = [(160.5, 1.0)]
    assert S._ipda_eq(c2, replace(p, ipda_eq_day="tag"), i)                                 # ipda_consol_eq reroutes the EQ day test
    # a day with a driver (CPI) is not a range day
    from claude_hf.daytypes import events
    cpi = next((d for d in (date(2026, 7, 14), date(2026, 6, 10), date(2026, 8, 12)) if "cpi" in events(d)), None)
    if cpi is not None:
        c2.day = cpi
        assert not L3.consol_eq_day(c2, p, i)


# --- Params, plumbing, study --------------------------------------------------------------------------------------------

NEW_SWITCHES = ("active_old_pool", "round_pool_mode", "round_conf_pts", "engineered_pools", "eng_short_pts", "rth_pool_spent", "session_ors",
                "nwog_rebalanced", "nwog_cfd_src", "open_float_pools", "float_denied_bars", "float_denied_adr", "balance_tf", "ir_def",
                "ir_overshoot_ticks", "ir_body_mult", "ob_anchor_rule", "ob_anchor_passes", "htf_ob_ltf_drill", "bk_depth", "bk_state",
                "bk_bpr_ce", "vi_breakaway", "gap_classes", "trail_skip_common", "single_pass_draw", "fvg_vi_extend_ce", "balanced_range",
                "orig_consol", "orig_consol_touches", "orig_consol_tol_pts", "consol_body_range", "consol_eq_touches", "eq_min_sep_bars",
                "void_rt_ob", "mit_def", "fs_def", "ipda_fv", "ipda_consol_eq")


def test_new_switch_defaults_and_validation():
    d = Params(**OA1029_OLD)                 # the built values; the OA1029 defaults are checked in test_owner_answers_oa1029.py
    # new switches default off / to the built behaviour
    assert (d.active_old_pool, d.round_pool_mode, d.engineered_pools, d.rth_pool_spent, d.session_ors, d.nwog_rebalanced, d.nwog_cfd_src,
            d.open_float_pools) == (False, "pool", False, False, (), False, "auto", False)
    assert (d.balance_tf, d.ir_def, d.ob_anchor_rule, d.htf_ob_ltf_drill, d.bk_depth, d.bk_state, d.bk_bpr_ce, d.vi_breakaway,
            d.gap_classes, d.trail_skip_common) == ("own", "a7", "wick_len", False, "ce", False, False, False, False, False)
    assert (d.single_pass_draw, d.fvg_vi_extend_ce, d.balanced_range, d.orig_consol, d.consol_body_range, d.eq_min_sep_bars, d.void_rt_ob,
            d.mit_def, d.fs_def, d.ipda_fv, d.ipda_consol_eq) == (False, True, False, False, False, 0, False, "a15", "m4", False, False)
    assert (d.orig_consol_touches, d.orig_consol_tol_pts, d.consol_eq_touches, d.float_denied_bars, d.eng_short_pts, d.round_conf_pts) == \
        (3, 0.5, 2, 20, 3.0, 1.0)
    assert d.sb_model is False and d.sb_use_bias is False and d.want_all_engines is True                   # untouched
    for bad in (dict(round_pool_mode="x"), dict(nwog_cfd_src="x"), dict(balance_tf="x"), dict(ir_def="x"), dict(ob_anchor_rule="x"),
                dict(bk_depth="x"), dict(mit_def="x"), dict(fs_def="x"), dict(session_ors=((0,),)), dict(session_ors=((0, 0),)),
                dict(float_denied_bars=0), dict(ob_anchor_passes=0), dict(orig_consol_touches=1), dict(eq_min_sep_bars=-1),
                dict(ir_body_mult=0.0), dict(consol_eq_touches=-1)):
        with pytest.raises(ValueError):
            Params(**bad)
    for ok in (dict(balance_tf="own"), dict(balance_tf="next_lower"), dict(ir_def="open_space", ir_entries=True), dict(ir_def="zero_width", ir_entries=True),
               dict(nwog_cfd_src="monday_0930"), dict(session_ors=((0, 30), (1200, 60)))):
        Params(**ok)


def test_htf_kw_carries_the_array_switches():
    assert B.htf_kw(Params()) == {"c2_dir": True, "vi_wick_overlap": False}                # unchanged at the built values (cache keys!); bodies-only VI default
    assert B.table_kw(Params()) == {"c2_dir": True, "balance_tf": "own", "vi_wick_overlap": False}
    kw = B.htf_kw(Params(nwog_cfd_src="monday_0930", void_rt_ob=True))
    assert kw["nwog_cfd_src"] == "monday_0930" and kw["void_rt_ob"] is True
    tk = B.table_kw(Params(single_pass_draw=True, htf_ob_ltf_drill=True, balance_tf="own"))
    assert tk["single_pass_draw"] and tk["htf_ob_ltf_drill"] and tk["balance_tf"] == "own"
    assert "balance_tf" not in B.htf_kw(Params(balance_tf="own")) and "single_pass_draw" not in B.htf_kw(Params(single_pass_draw=True))


def test_study_variants_for_the_caption_gap_pass_2():
    d = study.DECISIONS
    want = {"A2-which-old-high", "A2-round-number-pool", "A3-engineered-liquidity", "L1-rth-session-pools", "L3-midnight-session-opening-ranges",
            "L5-partial-redelivery", "L5-cfd-nwog-mapping", "A2-open-float", "A11-htf-gap-own-tf", "A7-immediate-rebalance-definition",
            "A12-open-vs-wick-gap-criterion", "A5-twice-traded-not-fvg", "A12-tf-relative-ob", "A6-breakaway-depth-qualification",
            "A9-vi-breakaway", "A6-gap-hierarchy-common", "new-single-candle-daily-inefficiency", "A5-vi-extended-ce",
            "A11-balanced-range-body-filled", "M1-original-consolidation", "A21-consolidation-range-def", "A3-clean-high",
            "A12-void-up-down-ob", "A15-stoprun-variant", "M4-failure-swing-no-new-extreme", "B21-data-range-fv-eq"}
    names = [k for k in d if any(k.startswith(w) for w in want)]
    for w in want:
        assert any(k.startswith(w) for k in names), w
    for k in study._LD2_DECISIONS:
        replace(Params(), **{**study.DEC_BASE, **d[k]})                                   # every variant builds a valid Params
    used = {s for k in study._LD2_DECISIONS for s in d[k]}
    # every switch that has a behaviour (not a pure tuning number) is used by a variant
    for s in NEW_SWITCHES:
        if s in ("round_conf_pts", "eng_short_pts", "float_denied_bars", "float_denied_adr", "ir_overshoot_ticks", "ir_body_mult", "ob_anchor_passes",
                 "orig_consol_touches", "orig_consol_tol_pts"):
            continue
        assert s in used, s
    order = list(d)
    assert order.index("A2-which-old-high") > order.index("X16_journal_tags_off")             # tested by the per-variant ES look-ahead run


# --- no look-ahead: full run vs truncated runs --------------------------------------------------------------------------------

from test_caption_gap_ld1 import ENTRY, EXIT, SYN, _no_look_ahead_x                           # noqa: E402  (shared helper)

SYN_BASE = dict(use_bias=True, bias_open="0930", ob_entry="both", draw_lock_neutral="both")
GROUPS = {
    "pools": dict(active_old_pool=True, round_pool_mode="confluence", engineered_pools=True, rth_pool_spent=True, extra_pools=True,
                  session_ors=((0, 30), (0, 60), (120, 30), (810, 30)), open_float_pools=True, eq_min_sep_bars=3, balanced_range=True,
                  consol_pools=True, ipda_pools=True, ipda_fv=True, ipda_consol_eq=True, ipda_eq_day="tag"),
    "gaps": dict(bk_depth="any_open", bk_state=True, bk_bpr_ce=True, breakaway="tag", ladder_trail="breakaway", vi_entries=True,
                 vi_breakaway=True, gap_classes=True, trail_skip_common=True, trail_first_fvg=True, fvg_vi_extend=True, vi_arrays=True,
                 ob_anchor_rule="gap_presence", ob_entries="fallback", mit_def="stoprun", mit_targets=True, fs_def="no_new_extreme",
                 cc_swings="failure", cc_fail_pts=5.0, mmxm_ctx=True, orig_consol=True, ir_def="open_space", ir_entries=True),
}


@pytest.mark.parametrize("group", sorted(GROUPS))
def test_look_ahead_synthetic(group):
    x, y = B.synthetic(start="2026-04-06", end="2026-05-08", tf=5, seed=3)
    p = Params(**{**SYN, **SYN_BASE, **GROUPS[group]})
    full = _no_look_ahead_x(x, 5, "RW", p, ENTRY + ["org_dir"], every=4, partner=y, min_trades=1)
    assert len(full)


def test_look_ahead_synthetic_post_mss():
    x, y = B.synthetic(start="2026-04-06", end="2026-05-08", tf=5, seed=5)
    p = Params(**SYN, use_bias=True, bias_open="0930", ob_entry="post_mss", draw_lock="off", breakaway="tag", bk_depth="any_open", bk_state=True,
               gap_classes=True, vi_entries=True, vi_breakaway=True, fvg_vi_extend=True, ob_anchor_rule="gap_presence",
               active_old_pool=True, engineered_pools=True, open_float_pools=True)
    _no_look_ahead_x(x, 5, "RW", p, ENTRY, every=4, partner=y)


def _es(a="2023-10-16", b="2023-11-10"):
    df = B.load("ES", 5, source="databento")
    return df[(df.index >= a) & (df.index < b)], B.load_meta("ES", 5)


@pytest.mark.skipif(not ES, reason="no ES data")
def test_look_ahead_es_htf_switches():
    """ES 5m with confluence and overnight sessions: the HTF array definitions (balance_tf, single-pass range, 1h order-block drill, void
    round trip), the rebalanced-NWOG ladder, the Monday-09:30 NWOG, the session opening ranges and the IPDA data range."""
    df, meta = _es()
    p = Params(**FUT, balance_tf="own", single_pass_draw=True, htf_ob_ltf_drill=True, void_rt_ob=True, nwog_rebalanced=True, nwog_cfd_src="monday_0930",
               session_ors=((0, 30), (810, 30)), ipda_pools=True, ipda_fv=True, ipda_consol_eq=True, vi_arrays=True, active_old_pool=True,
               ob_entry="both", leg_pd=0, min_draw_pts=0, htf_resist_cap=False)
    full = _no_look_ahead_x(df, 5, "ES", p, ENTRY + ["draw_px", "draw_name"], every=5, meta=meta)
    assert len(full)
    q = replace(p, balance_tf="next_lower", nwog_cfd_src="auto", draw_lock="off", ob_entry="post_mss", rth_pool_spent=True, extra_pools=True, engineered_pools=True,
                open_float_pools=True, round_pool_mode="confluence", ir_def="zero_width", ir_entries=True, bk_state=True, bk_depth="any_open",
                breakaway="hold")
    _no_look_ahead_x(df, 5, "ES", q, ENTRY, every=5, meta=meta)


def test_every_new_switch_is_named_by_a_test():
    """Every switch of this package appears in at least one test body (not only in the NEW_SWITCHES list)."""
    src = Path(__file__).read_text(encoding="utf-8")
    body = src.replace(src[src.index("NEW_SWITCHES = ("):src.index("def test_new_switch_defaults_and_validation")], "")
    for s_ in NEW_SWITCHES:
        assert body.count(s_) >= 1, s_
