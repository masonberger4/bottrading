"""Package levels_detectors (rule_coverage.md section 3, 36 items): unit tests for the new detectors
and helpers, small run_day scenarios, and no-look-ahead runs (full vs truncated) covering every new
switch. The databento tests skip when the ES data is missing."""
import warnings
from dataclasses import replace
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from mentorship import backtest as B, calendar as C, htf, levels as L, strategy as S, study
from mentorship.strategy import Params

NY = "America/New_York"
ES = Path("data/mentorship/ES_5min_db.csv").exists()
FUT = dict(es_pt=1.0, lot=1, max_notional=1e12, cost_per_share=0.1)
D0 = date(2026, 6, 23)                     # a Tuesday: no release, no NFP / FOMC week
BASE = dict(es_pt=1.0, lot=1, max_notional=1e12, cost_per_share=0.0, use_bias=False, adds=(),
            ladder_by_day=False, session_close=975, slow_frac=0.0)


def frame(d, rows, tf=5, start="00:00"):
    idx = pd.date_range(pd.Timestamp(f"{d} {start}", tz=NY), periods=len(rows), freq=f"{tf}min")
    a = np.array(rows, float)
    return pd.DataFrame({"open": a[:, 0], "high": a[:, 1], "low": a[:, 2], "close": a[:, 3],
                         "volume": 1.0}, index=idx)


def rth_day(d, hi, lo, close=100.0, op=None, tf=5):
    n = 390 // tf
    op = close if op is None else op
    rows = [(op, hi, lo, close)] + [(close, close + 0.1, close - 0.1, close)] * (n - 1)
    return frame(d, rows, tf, "09:30")


def prior_days(d, n):
    out, x = [], pd.Timestamp(d)
    while len(out) < n:
        x -= pd.Timedelta(days=1)
        if C.is_trading_day(x.date()):
            out.append(x.date())
    return out[::-1]


def history(d=D0, n=8, hi=108.0, lo=90.0, highs=None, lows=None):
    ds = prior_days(d, n)
    return [rth_day(x, highs[k] if highs else hi, lows[k] if lows else lo) for k, x in enumerate(ds)]


def day(rows, d=D0, start="09:30", base=100.0, w=0.2):
    m0 = int(start[:2]) * 60 + int(start[3:])
    out, last = [], base
    for k in range(975 // 5):
        j = (5 * k - m0) // 5
        if 0 <= j < len(rows):
            out.append(rows[j]); last = rows[j][3]
        elif 5 * k < m0:
            out.append((base, base + w, base - w, base))
        else:
            out.append((last, last + 0.1, last - 0.1, last))
    return frame(d, out)


def run(df, hist, p, rows=None, **kw):
    locks, log, skips = [], [], []
    tr = S.run_day(df, hist, "ES", p, 5, locks=locks, log=log, skips=skips, bias_by_cut=rows or {}, **kw)
    return tr, locks, log


def ctx_for(df, hist, p, **kw):
    ctx = S.DayCtx(df, df.index[0].date(), hist, 5, or_minutes=p.or_minutes)
    ctx.gaps = kw.get("gaps")
    S._setup_news(ctx, ctx.day, p)
    S._extra_levels(ctx, df, hist, p, kw.get("eth"), kw.get("closes"))
    return ctx


# --- levels.py detectors --------------------------------------------------------------------

def test_fvg_c2_direction_and_quadrants():
    h = np.array([10.0, 12.0, 14.0]); l = np.array([9.0, 10.5, 11.0])
    o = np.array([9.5, 11.5, 12.0]); c = np.array([9.8, 11.0, 13.5])          # c2 down-close
    assert len(L.fvgs(h, l)) == 1 and L.fvgs(h, l, o, c, c2_dir=True) == []
    c2 = c.copy(); c2[1] = 11.9
    z = L.fvgs(h, l, o, c2, c2_dir=True)[0]
    assert (z.top, z.bottom) == (11.0, 10.0) and z.q(0.25) == 10.25 and z.q(0.75) == 10.75 and z.q(0.5) == z.mid
    # bearish: c2 must close down
    hb, lb = -l[::1], -h[::1]
    ob, cb = -o, -c2
    assert L.fvgs(hb, lb, ob, cb, c2_dir=True)[0].kind == "bear"


def test_vi_min_gap_and_body_death():
    o = np.array([10.0, 10.6, 10.7, 10.9]); c = np.array([10.5, 10.9, 10.8, 10.2])
    h = np.array([10.7, 11.0, 11.0, 11.0]); l = np.array([9.9, 10.4, 10.6, 10.1])
    v = L.volume_imbalances(o, h, l, c)
    assert [(z.kind, z.top, z.bottom, z.i) for z in v] == [("bull", 10.6, 10.5, 1)]
    assert L.volume_imbalances(o, h, l, c, min_gap=0.2) == []
    # bar 3's body (10.9 -> 10.2) spans the VI 10.5-10.6: dead at 3; bar 2's body does not
    assert L.vi_body_dead(o, c, v[0]) == 3
    assert L.vi_body_dead(o, c, v[0], end=2) is None


def test_swing_tiers_itl_ltl_known_with_right_neighbour():
    # STL lows at bars 2 (5), 4 (3), 6 (6), 8 (2), 10 (7), 12 (4), 14 (8): ITL lows at 4 and 8; LTL at 8
    l = np.array([9, 8, 5, 8, 3, 8, 6, 8, 2, 8, 7, 8, 4, 8, 4.5, 9], float)
    h = l + 1.0
    t = L.swing_tiers(h, l, 1)
    stl = [q.i for q in t["stl"][1]]
    assert stl == [2, 4, 6, 8, 10, 12, 14]
    itl = t["itl"][1]
    assert [q.i for q in itl] == [4, 8, 12] and itl[0].known == 7      # right neighbour (6) known at 7
    ltl = t["ltl"][1]
    assert [q.i for q in ltl] == [8] and ltl[0].known == 15            # right ITL (12) known at 15


def test_immediate_rebalance_vacuum_block_session_block():
    o = np.array([10.0, 10.2, 11.0, 11.5]); c = np.array([10.2, 11.0, 11.6, 11.8])
    h = np.array([10.3, 11.1, 11.7, 11.9]); l = np.array([9.9, 10.1, 10.3, 11.4])
    assert (2, "bull") in L.immediate_rebalances(o, h, l, c, 0.25)       # l[2] 10.3 == h[0] 10.3
    l2 = l.copy(); l2[2] = 10.6                                         # a gap: deferred rebalance
    assert (2, "bull") not in L.immediate_rebalances(o, h, l2, c, 0.25)
    # bearish mirror
    assert (2, "bear") in L.immediate_rebalances(-o, -l, -h, -c, 0.25)
    z = L.vacuum_block(np.array([10.0, 12.0]), np.array([10.5, 12.5]), 1)
    assert (z.kind, z.top, z.bottom, z.mid) == ("bull", 12.0, 10.5, 11.25)
    assert L.vacuum_block(np.array([10.0, 10.5]), np.array([10.5, 11.0]), 1, 0.25) is None
    assert [L.session_block(m) for m in (60, 180, 570, 750, 900, 1100)] == [0, 1, 2, 3, 4, 0]


def test_equal_clusters_bpr_window_and_mitigation_order():
    assert L.equal_clusters([10.0, 10.2, 12.0, 10.4, 12.1], 0.5) == [[0, 1, 3], [2, 4]]
    h = np.array([10, 12, 13, 11, 10, 9, 8, 9, 11, 12, 13.0])
    l = h - 1.5
    full = L.balanced_ranges(h, l)
    assert all(z.i - z.src <= 20 for z in full)
    assert L.balanced_ranges(h, l, max_gap_bars=1) == [z for z in full if z.i - z.src <= 1]
    # A15 fixed order: swing low A (bar 1, 4.0), swing high X (bar 3, 8.0), higher low B (bar 5, 5.0),
    # close above X at bar 7; the zone is the last up-close candle at X (bar 3)
    h2 = np.array([6, 5, 7, 8, 7, 6, 7.5, 9, 9.5]); l2 = np.array([5, 4, 6, 7, 6, 5, 6.5, 7.5, 9])
    o2 = np.array([5.5, 4.5, 6.2, 7.2, 6.8, 5.5, 6.6, 7.6, 9.1]); c2 = np.array([5.2, 4.8, 6.8, 7.8, 6.2, 5.8, 7.2, 8.8, 9.4])
    m = L.mitigation_blocks(o2, h2, l2, c2, 1)
    assert m and m[0].kind == "bull" and m[0].i == 7 and m[0].src == 3
    l3 = l2.copy(); l3[5] = 3.5                                        # B below A: a run on A's stops
    assert not [z for z in L.mitigation_blocks(o2, h2, l3, c2, 1) if z.kind == "bull"]
    assert L.mitigation_alive(c2, m[0], 8) and not L.mitigation_alive(np.r_[c2, 6.0], m[0], 9)


def test_tick_helpers_and_equal_levels_bodies_rank():
    assert S._thru(99.75, 100.0, 0.25) and not S._thru(99.9, 100.0, 0.25) and S._thru(99.9, 100.0, 0.0)
    assert not S._spent_up(100.0, 100.0, 0.25) and S._spent_up(100.0, 100.0, 0.0) and S._spent_up(100.25, 100.0, 0.25)
    # three swing highs: two with equal bodies (wicks 105 / 105.9), one far away
    o = np.array([100, 102, 103.0, 102, 101, 102, 103.0, 102, 100, 101, 100.5, 100, 99.0])
    c = np.array([101, 103, 104.0, 103, 102, 103, 104.0, 102, 101, 102, 100.2, 99.5, 99.0])
    h = np.array([101.5, 103.5, 105.0, 103.5, 102.5, 103.5, 105.9, 103, 101.5, 102.5, 101, 100, 99.5])
    lo = np.minimum(o, c) - 0.5
    sd = S.Side(1, o, h, lo, c, 1)
    p0 = Params(eq_tol_pts=0.5)
    assert S._eq_levels(sd, 12, 0.5, False, p0) == []                  # wicks 105 / 105.9 differ
    pb = replace(p0, eq_bodies=True)
    assert S._eq_levels(sd, 12, 0.5, False, pb) == [105.9]             # bodies equal; line at the wick
    with pytest.raises(ValueError):
        Params(eq_pref="best")


def test_gaps_for_day_trading_days_and_holiday_skip():
    rows = []
    for d in pd.bdate_range("2024-01-01", "2024-04-30"):
        if d.weekday() == 0:          # one NWOG per week, known Sunday 18:00
            k = pd.Timestamp(d.date(), tz=NY) - pd.Timedelta(hours=6)
            rows.append(dict(kind="nwog", high=100.0 + d.dayofyear, low=99.0 + d.dayofyear, ce=99.5 + d.dayofyear,
                             up=True, known=k, week=(k + pd.Timedelta(hours=7)).normalize().tz_localize(None).to_period("W-FRI")))
    g = pd.DataFrame(rows)
    day = date(2024, 4, 26)
    a = htf.gaps_for_day(g, day, nwog_days=20, trading_days=True)
    d0 = C.prev_trading_day(day, 20)
    assert all(pd.Timestamp(d0, tz=NY) - pd.Timedelta(hours=6) <= g.known[g.high == x[1]].iloc[0] for x in a)
    old = htf.gaps_for_day(g, day, nwog_days=20)
    assert len(old) >= len(a) - 1
    # New Year (Jan 1), MLK (Jan 15) and Presidents' Day (Feb 19 2024) weeks are holiday-shortened
    allg = htf.gaps_for_day(g, date(2024, 3, 1), nwog_days=60, trading_days=True)
    skip = htf.gaps_for_day(g, date(2024, 3, 1), nwog_days=60, trading_days=True, skip_holiday=True)
    assert len(allg) - len(skip) == 3                                 # + the New Year week


# --- strategy helpers on hand-made days -------------------------------------------------------

def test_ipda_ranges_next_and_eq_day():
    n = 61
    highs = [100.0 + (k % 7) for k in range(n)]
    lows = [90.0 - (k % 5) for k in range(n)]
    highs[n - 30] = 115.0                                             # the 40-day high (not in the last 20)
    highs[n - 50] = 120.0                                             # the 60-day high
    hist = history(n=n, highs=highs, lows=lows)
    p = Params(**BASE, ipda_pools=True)
    df = day([(100.0, 100.5, 99.5, 100.0)] * 6 + [(100.0, 107.5, 99.9, 107.0)] + [(107.0, 107.2, 106.8, 107.0)] * 10)
    ctx = ctx_for(df, hist, p)
    assert ctx.ipda[20][0] == max(highs[-20:]) == 106.0 and ctx.ipda[40][0] == 115.0 and ctx.ipda[60][0] == 120.0
    sd = S.Side(1, ctx.o, ctx.h, ctx.l, ctx.c, 1)
    i = S._idx_at(ctx, 630)
    pools = [v for v, _ in S._lv_target_pools(ctx, sd, i, replace(p, ipda_next=True))]
    assert pools == [115.0]                                           # the 20-day high is taken -> 40
    out = {}
    S._lv_sell_side(ctx, sd, "AM", i, p, out, True)
    assert out["ipda20"] == min(lows[-20:]) and out["ipda60"] == min(lows)
    assert not S._ipda_eq(ctx, p, i)                                  # 09:30 open far from the 60-day EQ
    with pytest.raises(ValueError):
        Params(ipda_eq_day="maybe")


def test_session_priority_prev_am_org_state_and_today_pools():
    hist = history(n=8, hi=104.0, lo=96.0)
    hist[-1] = frame(hist[-1].index[0].date(), [(100.0, 101.0, 99.0, 100.0)] * 30 + [(100.0, 103.0, 99.5, 102.0)] * 48, 5, "09:30")
    # today: London 02:00-05:00 range 100.6-99.6, 09:30 open 104 (above the prior PM range 99.5-103 by > 25%)
    rows = [(104.0, 104.2, 103.6, 103.8)] * 12
    df = day(rows)
    for k in range(24, 36):
        df.iloc[k] = [100.0, 100.6, 99.6, 100.0, 1.0]
    p = Params(**BASE, session_priority=True, prev_am_pool=True, org_pools=True, pool_today_hl=True,
               am_range_end=720, org_draw="draw", org_q_hold=True, org_half_draw=True)
    ctx = ctx_for(df, hist, p, closes={hist[-1].index[0].date(): 102.0})
    sd = S.Side(1, ctx.o, ctx.h, ctx.l, ctx.c, 1)
    i = S._idx_at(ctx, 600)
    assert S._session_pick(ctx, i) == "london"
    out = S._sell_side(ctx, sd, "AM", i, True, p)
    assert "london" in out and "prev_pm" not in out and "prev_am" not in out
    assert out["org_close"] == 102.0 and out["today_low"] == 99.6
    assert ctx.prev_am == (101.0, 99.0)                               # previous 09:30-12:00 range
    sh = S.Side(-1, ctx.o, ctx.h, ctx.l, ctx.c, 1)
    st = S._org_state(ctx, sh, i, p)                                   # short side: prior close 102 below
    assert st["up"] and st["pcx"] == -102.0 and st["breakaway"] is True  # 09:30-10:00 never reached 103.5
    assert S._org_state(ctx, sd, i, p)["up"] is False


def test_nwog_half_and_vacuum_and_wicks():
    hist = history(n=8)
    rows = [(100.0, 100.2, 99.8, 100.0)] * 4 + [(100.0, 103.2, 99.9, 103.0)] + [(103.0, 103.1, 102.9, 103.0)] * 5
    df = day(rows)
    gaps = [("nwog", 98.0, 97.0, 97.5), ("nwog", 110.0, 108.0, 109.0)]
    p = Params(**BASE, nwog_halfway=True, wick_days=3, wick_weekly=True, wick_both=True)
    ctx = ctx_for(df, hist, p, gaps=gaps)
    sd = S.Side(1, ctx.o, ctx.h, ctx.l, ctx.c, 1)
    i = S._idx_at(ctx, 600)
    assert S._nwog_half(ctx, sd, i) == 108.0                           # half of 98 -> 108 = 103 reached
    assert S._nwog_half(ctx, sd, S._idx_at(ctx, 580)) is None
    assert len(ctx.wicks) == 3 and ctx.wick_wk
    lv = S._targets(ctx, sd, i, 103.3, [], p, None, i - 1)
    assert (104.0, "array") in lv                                     # the upper wick CE (100 -> 108)
    lo = S._targets(ctx, sd, i, 80.0, [], p, None, i - 1)
    assert (95.0, "array") in lo                                      # wick_both: the lower wick CE
    # L8: a vacuum block at an 08:30 release (synthetic: monkeypatched release list)
    S_rel = S.release_times
    try:
        S.release_times = lambda d: [510]
        dfv = day([], start="09:30")
        dfv.iloc[101] = [101.0, 101.2, 100.9, 101.0, 1.0]             # 08:25 bar? (index 101 = 08:25)
        dfv.iloc[102] = [102.0, 102.2, 101.9, 102.0, 1.0]             # 08:30 opens 1.0 above
        pv = Params(**BASE, vacuum_blocks=True)
        cv = ctx_for(dfv, hist, pv)
        assert cv.vac and cv.vac[0][1:4] == (102.0, 101.5, 101.0)
    finally:
        S.release_times = S_rel


# --- run_day scenarios (scenario B of test_review_fixes: L1 98.6, H 101.0, sweep 98.0, MSS 10:05) ---

B_ROWS = [(101.0, 101.2, 99.0, 99.2), (99.2, 99.3, 98.6, 98.8), (98.8, 100.4, 98.7, 100.3),
          (100.3, 101.0, 100.1, 100.4), (100.4, 100.5, 99.3, 99.4), (99.4, 99.5, 98.0, 98.2),
          (98.2, 100.0, 98.1, 99.9), (99.9, 101.6, 99.0, 101.5), (101.5, 102.5, 101.3, 102.3)]
B_POST = dict(BASE, ob_entry="post_mss", draw_lock="off", htf_resist_cap=False, news_wait="off",
              min_draw_pts=0.0, leg_pd=0.0)


def _b(after, **kw):
    """Scenario B, longs only (an htf "react" bias of +1: the short side's own breaker would trade first)."""
    hist = history(hi=112.0, lo=88.0)
    tr, locks, log = run(day(B_ROWS + after), hist, Params(**{**B_POST, "htf_bias": "react", **kw}),
                         bias=dict(react=1, draw=1, pd=1))
    return tr


def test_breaker_entry_prefer_ll_time_and_tags():
    after = [(102.3, 102.4, 100.3, 101.0)]
    base = _b(after)
    assert base and base[0].unicorn and base[0].entry == 101.3
    assert base[0].fvg_state == "open"
    tr = _b(after, breaker_entry="prefer")
    assert tr and tr[0].entry_kind == "breaker" and tr[0].entry == 101.0 and tr[0].stop == pytest.approx(97.75)
    assert _b(after, breaker_ll=True)[0].unicorn                       # real L1/H, L2 < L1, close above H
    assert _b(after, breaker_time="all")[0].unicorn                    # all in the NY AM block
    assert _b(after, unicorn_pref=False)[0].entry == 101.3
    tr = _b(after, breakaway="tag")
    assert "breakaway" in tr[0].lv_tags                                # the first FVG after the MSS
    assert _b(after, breakaway="next_fvg") == []                       # no later FVG here
    tr = _b(after + [(101.0, 101.1, 100.8, 100.9)], fvg_q_hold=True)   # 100.9 < 100.975 (75% of 100.0-101.3)
    assert [(e[3], e[1]) for e in tr[0].exits] == [("q_close", 100.9)]
    assert _b(after + [(101.0, 101.1, 100.8, 100.9)])[0].exits[-1][3] != "q_close"
    tr = _b(after + [(101.0, 101.1, 100.5, 100.6)], breakaway="hold")    # body close below its CE 100.65
    assert [(e[3], e[1]) for e in tr[0].exits] == [("breakaway_ce", 100.6)]


def test_breaker_ll_rejects_a_higher_low():
    hist = history(hi=112.0, lo=88.0)
    df = day(B_ROWS + [(102.3, 102.4, 100.3, 101.0)])
    p = Params(**B_POST, breaker_ll=True)
    ctx = ctx_for(df, hist, p)
    sd = S.Side(1, ctx.o, ctx.h, ctx.l, ctx.c, 1)
    k0 = S._idx_at(ctx, 570)
    sw = dict(ext=98.9, ext_i=k0 + 5, broke=k0 + 7)                   # an extreme above L1 (98.6)
    assert S._breaker(ctx, sd, sw, k0 + 3, True, k0 + 8, p) is None
    sw["ext"] = 98.0
    assert S._breaker(ctx, sd, sw, k0 + 3, True, k0 + 8, p) is not None
    assert S._breaker(ctx, sd, sw, k0 + 3, False, k0 + 8, p) is None   # H not a real pivot


def test_sweep_ticks_a_touch_is_not_a_sweep():
    hist = history(hi=112.0, lo=88.0)
    df = day([(100.0, 100.1, 99.7, 99.9)])                             # overnight low 99.8: 0.1 through
    p = Params(**B_POST)
    ctx = ctx_for(df, hist, p)
    sd = S.Side(1, ctx.o, ctx.h, ctx.l, ctx.c, 1)
    i = S._idx_at(ctx, 570)
    S._scan(ctx, sd, i, p, "AM", 570, None, None, None)
    assert sd.sweep is None                                           # < 1 ES tick through
    sd2 = S.Side(1, ctx.o, ctx.h, ctx.l, ctx.c, 1)
    S._scan(ctx, sd2, i, replace(p, sweep_ticks=0.0), "AM", 570, None, None, None)
    assert sd2.sweep is not None and sd2.sweep["key"] == "premarket"


def test_mss_ref_tiers_and_params_validation():
    with pytest.raises(ValueError):
        Params(mss_ref="big")
    with pytest.raises(ValueError):
        Params(fvg_state_filter=("closed",))
    tr = _b([(102.3, 102.4, 100.3, 101.0)], mss_ref="itl", mss_ref_fallback="none")
    assert tr == []                                                    # no ITL high before the sweep
    tr = _b([(102.3, 102.4, 100.3, 101.0)], mss_ref="itl")             # falls back to the STL
    assert tr and tr[0].entry == 101.3


def test_study_has_a_variant_for_every_new_switch():
    names = " ".join(str(v) for v in study.DECISIONS.values())
    for f in ("ipda_pools", "ipda_next", "ipda_eq_day", "mss_ref", "mss_ref_fallback", "sweep_ticks",
              "sb_draw_pools_only", "fvg_c2_dir", "fvg_quadrants", "fvg_vi_extend", "fvg_skip_above_pool",
              "htf_ce_draw", "fvg_q_hold", "fvg_state_filter", "fvg_keep_filled", "vi_targets", "wick_days",
              "no_draw", "skip_no_draw", "am_range_end", "prev_am_pool", "session_priority", "org_pools",
              "daily_level_needs_array", "daily_level_needs_flow", "pd_hl_session", "pool_today_hl",
              "matrix_full", "matrix_days", "gap_quarters", "nwog_quarters", "nwog_skip_holiday",
              "nwog_halfway", "gap_run_stop", "nwog_trading_days", "monday_ce", "org_sweep", "org_draw",
              "org_half_draw", "org_q_hold", "wick_weekly", "wick_both", "wick_session", "wick_invalidate",
              "wick_partial", "wick_react", "daily_fvg_exact", "pool_gaps", "gap_pool_edge", "release_open",
              "release_open_stop", "bias_open", "breakaway", "breaker_ll", "breaker_cand_to", "breaker_time",
              "breaker_entry", "breaker_levels", "vi_min_gap_pts", "vi_body_death", "vi_stop", "vi_porous_n",
              "vi_htf_draw", "vi_news_draw", "eq_pref", "eq_bodies", "eq_rank", "imm_rebalance_disp",
              "bpr_max_gap_bars", "bpr_targets", "bpr_abort", "bpr_rule", "mit_targets", "mit_body_respect",
              "unicorn_pref", "or_extra", "pw_pm_full_session", "vacuum_blocks"):
        assert f"'{f}'" in names or f in names, f
    assert B.HIST_DAYS >= 61


# --- no look-ahead ----------------------------------------------------------------------------

def _no_look_ahead(df, tf, sym, p, cols, every=1, meta=None, lag=2, min_trades=1, **kw):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        full = B.run(df, tf, sym, p, meta=meta, **kw)
        assert len(full) >= min_trades, "no trades - the test window must produce some"
        for cut_t in full.entry_time.iloc[::every]:
            c = cut_t + pd.Timedelta(minutes=lag)
            pk = {k: (v[v.index <= c] if isinstance(v, pd.DataFrame) else v) for k, v in kw.items()}
            part = B.run(df[df.index <= c], tf, sym, p, partial_last=True, meta=meta, **pk)
            a = full[full.entry_time <= cut_t][cols].reset_index(drop=True)
            b = part[part.entry_time <= cut_t][cols].reset_index(drop=True)
            pd.testing.assert_frame_equal(a, b)
    return full


COLS = ["entry_time", "entry", "stop", "t1", "shares", "entry_kind", "lv_tags", "fvg_state", "imm_rebal"]
SYN = dict(es_pt=0.09, use_bias=False, min_draw_pts=0, leg_pd=0)


def _set_a():
    return dict(ipda_pools=True, ipda_next=True, ipda_eq_day="tag", mss_ref="itl", sweep_ticks=2.0,
                fvg_quadrants=True, fvg_quad_min_pts=2.0, fvg_vi_extend=True, fvg_skip_above_pool=True,
                fvg_state_filter=("open", "repriced", "rebalanced"), fvg_keep_filled=True, vi_targets=True,
                wick_days=3, no_draw=True, am_range_end=720, prev_am_pool=True, session_priority=True,
                org_pools=True, pool_today_hl=True, gap_quarters=True, monday_ce=True, nwog_quarters=True,
                nwog_halfway=True, org_draw="draw", org_half_draw=True, org_q_hold=True, wick_weekly=True,
                wick_both=True, wick_invalidate=True, wick_partial=True, wick_react="tag", pool_gaps=True,
                gap_pool_edge="ce", release_open=True, release_open_stop="wick_ce", bias_open="0930",
                breakaway="hold", breaker_ll=True, breaker_cand_to="h", breaker_time="all", ob_entry="both",
                breaker_levels=True, vi_stop=True, vi_porous_n=4, vi_min_gap_pts=0.25, eq_pref="rank",
                eq_bodies=True, eq_rank=True, imm_rebalance_disp="or", displacement_mult=1.0,
                bpr_targets=True, bpr_abort=True, bpr_rule=True, bpr_max_gap_bars=20, mit_targets=True,
                mit_body_respect=True, unicorn_pref=False, org_sweep=True, org_days=20, or_extra=True,
                vacuum_blocks=True, matrix_days="ict", fvg_q_hold=True, gap_mode="monday")


def test_look_ahead_synthetic_levels_a():
    """IPDA (61 sessions of history from June on), tiers, booking tick 2, FVG / VI / BPR / mitigation /
    wick / ORG / session-pool switches, matrix "ict", breaker rules, eq rank - with the #9 lock (OB
    entries) and without it (post-MSS FVG entries: breakaway hold, upper-quarter hold, VI extension)."""
    x, y = B.synthetic(start="2026-03-02", end="2026-07-17", tf=5, seed=3)
    full = _no_look_ahead(x, 5, "RW", Params(**SYN, **_set_a()), COLS, every=4, partner=y)
    assert full.lv_tags.str.contains("bpr_cap").any()
    x, y = B.synthetic(start="2026-04-01", end="2026-07-31", tf=5, seed=3)
    p = Params(**SYN, **{**_set_a(), "ob_entry": "post_mss", "draw_lock": "off", "bpr_rule": False,
                         "release_open": False, "breaker_time": "off", "breaker_ll": False})
    full = _no_look_ahead(x, 5, "RW", p, COLS, every=1, partner=y)
    assert full.lv_tags.str.contains("breakaway").any() and (full.fvg_state == "open").any()


def test_look_ahead_synthetic_levels_b():
    """No-lock draw overrides (HTF CE, NWOG halfway, ORG far edge / half, rel-eq rank), breaker
    fallback entries, LTL reference with fallback, ipda_eq skip; then breaker prefer + IR require +
    skip_no_draw with the Silver Bullet's pools-only draw."""
    x, y = B.synthetic(start="2026-04-01", end="2026-07-31", tf=5, seed=3)
    p = Params(**SYN, draw_lock="off", htf_ce_draw=True, nwog_halfway=True, org_draw="draw",
               org_half_draw=True, eq_pref="rank", breaker_entry="fallback", ob_entry="post_mss",
               mss_ref="ltl", mss_ref_fallback="lower", ipda_eq_day="skip", pool_today_hl=True,
               wick_react="tag", gap_mode="monday", pool_gaps=True, max_risk_pts=40)
    full = _no_look_ahead(x, 5, "RW", p, COLS, every=2, partner=y)
    assert (full.entry_kind == "breaker").any() and full.lv_tags.str.contains("draw_").any()
    p2 = Params(**SYN, breaker_entry="prefer", ob_entry="post_mss", imm_rebalance_disp="require",
                skip_no_draw=True, sb_model=True, sb_draw_pools_only=True, max_risk_pts=40, draw_lock="off")
    _no_look_ahead(x, 5, "RW", p2, COLS + ["setup"], every=15, partner=y)


ES_COLS = ["entry_time", "entry", "stop", "t1", "lv_tags", "entry_kind", "fvg_state", "swept"]


def _es():
    df = B.load("ES", 5, source="databento")
    return df[(df.index >= "2023-09-01") & (df.index < "2024-01-20")], B.load_meta("ES", 5)


@pytest.mark.skipif(not ES, reason="no ES data")
def test_look_ahead_es_levels_lock_and_overnight_switches():
    """With the #9 lock: ETH matrix / wicks / week-month pools, VI wiring (min gap, body death, news
    draw), daily FVG exact, the lock preferences (HTF CE, NWOG halfway, ORG far edge, VI news draw),
    gaps as pools, holiday-week NWOG skip, gap quarters, vacuum blocks, release open, IPDA pools,
    wick rungs, previous AM / today pools, keep-filled and quadrant targets. Then without the lock:
    the HTF VI draw, daily level needs an array, VI stop, breakaway next_fvg, the BPR rule."""
    df, meta = _es()
    p = Params(**FUT, pd_hl_session="eth", matrix_full=True, wick_session="eth", pw_pm_full_session=True,
               pool_prev_week=True, pool_prev_month=True, vi_arrays=True, vi_min_gap_pts=0.25,
               vi_body_death=True, vi_news_draw=True, vi_htf_draw=True, daily_fvg_exact=True, htf_ce_draw=True,
               nwog_halfway=True, pool_gaps=True, nwog_skip_holiday=True, gap_quarters=True, vacuum_blocks=True,
               release_open=True, ipda_pools=True, org_draw="draw", wick_partial=True, prev_am_pool=True,
               pool_today_hl=True, htf_resist_cap=False, fvg_keep_filled=True, fvg_quadrants=True)
    full = _no_look_ahead(df, 5, "ES", p, ES_COLS + ["draw_px", "draw_name"], every=6, meta=meta)
    assert set(full.draw_name) & {"vi_news", "htf_ce", "nwog_half", "org_far"}
    p2 = replace(p, draw_lock="off", daily_level_needs_array=True, ob_entry="both", vi_stop=True,
                 breakaway="next_fvg", bpr_rule=True, bpr_max_gap_bars=30, leg_pd=0, min_draw_pts=0)
    full = _no_look_ahead(df, 5, "ES", p2, ES_COLS, every=6, meta=meta)
    assert full.lv_tags.str.contains("draw_htf_").any()


@pytest.mark.skipif(not ES, reason="no ES data")
def test_look_ahead_es_levels_entry_filters_and_exits():
    """No lock / cap, both entries, no bias: rel-eq rank (bodies, ranked), daily level needs array +
    flow, breakaway hold, wick react / invalidate, ITL reference, no-draw skip, FVG state / pool /
    VI-extension / quarter-hold, VI porous, IR "or", mitigation / BPR / VI targets, BPR abort, matrix
    "ict", ORG sweep (20 days) / pools, session priority, release-open stop, 08:30 bias open, OR extra;
    then the gap-run stop, IPDA next, breaker fallback with LL / time / L1->H candle / levels, no
    unicorn preference, 12:00 AM range, ORG half draw, wick days / weekly / both, NWOG quarters and
    gap CE pools; and eq_pref require."""
    df, meta = _es()
    base = dict(**FUT, draw_lock="off", htf_resist_cap=False, ob_entry="both", leg_pd=0, min_draw_pts=0,
                use_bias=False)
    p3 = Params(**base, eq_pref="rank", eq_bodies=True, eq_rank=True, daily_level_needs_flow=True,
                daily_level_needs_array=True, breakaway="hold", wick_react="tag", wick_invalidate=True,
                mss_ref="itl", no_draw=True, skip_no_draw=True, fvg_state_filter=("open", "repriced"),
                fvg_skip_above_pool=True, fvg_vi_extend=True, fvg_q_hold=True, vi_porous_n=3,
                imm_rebalance_disp="or", displacement_mult=1.0, mit_targets=True, bpr_targets=True,
                bpr_abort=True, vi_targets=True, matrix_days="ict", org_sweep=True, org_days=20, org_pools=True,
                session_priority=True, release_open_stop="wick_ce", bias_open="0830", or_extra=True)
    full = _no_look_ahead(df, 5, "ES", p3, ES_COLS, every=10, meta=meta)
    assert full.swept.str.startswith("org").any()
    p4 = Params(**base, gap_run_stop=True, gap_run_tol_pts=4.0, ipda_next=True, breaker_entry="fallback",
                breaker_ll=True, breaker_time="hl2", breaker_cand_to="h", breaker_levels=True, unicorn_pref=False,
                am_range_end=720, org_half_draw=True, wick_both=True, wick_weekly=True, wick_days=3,
                nwog_quarters=True, gap_pool_edge="ce", pool_gaps=True)
    full = _no_look_ahead(df, 5, "ES", p4, ES_COLS, every=6, meta=meta)
    assert full.lv_tags.str.contains("gap_stop").all() and (full.entry_kind == "breaker").any()
    _no_look_ahead(df, 5, "ES", replace(p4, eq_pref="require", ipda_eq_day="skip", monday_ce=True), ES_COLS,
                   meta=meta)
