"""Review fixes for package owner_directives_and_bugs (2026-10-18) and the items built after it.

Synthetic one-day scenarios run through run_day (the real engine path), unit tests for the new
helpers, and no-look-ahead runs (full vs truncated) covering every switch the review listed as
uncovered plus every switch added here. The databento tests skip when the ES data is missing."""
import warnings
from collections import Counter
from dataclasses import replace
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from mentorship import backtest as B, calendar as C, htf, levels as L, paper, sb_model, strategy as S
from mentorship.strategy import Params
from dataclasses import dataclass as _oa_dc


@_oa_dc
class Params(Params):   # OA1029 Q92: these tests exercise other rules; the order-block narrative gate (default on) leaves them no trades
    ob_need_narrative: bool = False

NY = "America/New_York"
ES = Path("data/mentorship/ES_5min_db.csv").exists() and Path("data/mentorship/ES_1min_dbraw.csv").exists()
ES1 = Path("data/mentorship/ES_1min_db.csv").exists()
FUT = dict(es_pt=1.0, lot=1, max_notional=1e12, cost_per_share=0.1)
D0 = date(2026, 6, 23)                     # a Tuesday: no release, no NFP / FOMC week
K = 300.0                                  # mirror constant: price p -> K - p

# engine settings that keep a hand-made day readable (each test switches what it checks back on)
BASE = dict(es_pt=1.0, lot=1, max_notional=1e12, cost_per_share=0.0, use_bias=False, adds=(),
            ladder_by_day=False, session_close=975, slow_frac=0.0)


def frame(d, rows, tf=5, start="00:00"):
    idx = pd.date_range(pd.Timestamp(f"{d} {start}", tz=NY), periods=len(rows), freq=f"{tf}min")
    a = np.array(rows, float)
    return pd.DataFrame({"open": a[:, 0], "high": a[:, 1], "low": a[:, 2], "close": a[:, 3],
                         "volume": 1.0}, index=idx)


def rth_day(d, hi, lo, close=100.0, tf=5):
    n = 390 // tf
    rows = [(close, hi, lo, close)] + [(close, close + 0.1, close - 0.1, close)] * (n - 1)
    return frame(d, rows, tf, "09:30")


def history(d=D0, n=8, hi=108.0, lo=90.0, first=None):
    """n prior regular sessions (oldest first); `first` = (hi, lo) for all but the last day."""
    out, x = [], pd.Timestamp(d)
    while len(out) < n:
        x -= pd.Timedelta(days=1)
        if C.is_trading_day(x.date()):
            out.append(x.date())
    out = out[::-1]
    return [rth_day(x, *(first if (first and k < n - 1) else (hi, lo))) for k, x in enumerate(out)]


def day(rows, d=D0, start="09:30", spike=False, base=100.0, w=0.2, tail=None):
    """00:00-16:15 5m bars: flat at `base` (+-w) except `rows` from `start` (and an overnight
    spike to base+2.5 at 03:00 if asked); after the rows, flat at the last close."""
    m0 = int(start[:2]) * 60 + int(start[3:])
    n = 975 // 5
    out = []
    last = base
    for k in range(n):
        m = 5 * k
        j = (m - m0) // 5
        if 0 <= j < len(rows):
            out.append(rows[j])
            last = rows[j][3]
        elif m < m0:
            out.append((base, base + w, base - w, base))
        else:
            t = tail if tail is not None else last
            out.append((t, t + 0.1, t - 0.1, t))
    if spike:
        out[36] = (base, base + 2.5, base - 0.1, base)          # 03:00
    return frame(d, out)


def mirror(df):
    return df.assign(open=K - df.open, high=K - df.low, low=K - df.high, close=K - df.close)


def run(df, hist, p, rows=None, **kw):
    locks, log, skips = [], [], []
    tr = S.run_day(df, hist, "ES", p, 5, locks=locks, log=log, skips=skips, bias_by_cut=rows or {}, **kw)
    return tr, locks, log, skips


# Scenario A: a sweep of the overnight low at 09:30-09:35, the order-block bodies (100) armed at
# 09:45, filled at 09:50, then a run through 102.75 / 103.5 into the locked draw (PDH 108).
A_ROWS = [(100.0, 100.1, 99.5, 99.6), (99.6, 99.7, 98.5, 98.8), (98.8, 99.9, 98.7, 99.8),
          (99.8, 100.8, 99.7, 100.7), (100.7, 100.8, 99.9, 100.3), (100.3, 103.0, 100.2, 102.9),
          (102.9, 104.0, 102.8, 103.9), (103.9, 108.5, 103.8, 108.4)]
A_LOCK = {570: dict(draw_up=104.0, draw_up_name="D_fvg", draw_dn=float("nan"), draw_dn_name="")}

# Scenario B (bodies of the first down candles up to 101: no early OB entry): L1 98.6, H 101.0 (breaker candle 09:45: 100.1-101.0, MT 100.55), sweep to 98.0,
# MSS close 101.5 at 10:05, FVG 100.0-101.3 at 10:10 overlapping the breaker -> unicorn.
B_ROWS = [(101.0, 101.2, 99.0, 99.2), (99.2, 99.3, 98.6, 98.8), (98.8, 100.4, 98.7, 100.3),
          (100.3, 101.0, 100.1, 100.4), (100.4, 100.5, 99.3, 99.4), (99.4, 99.5, 98.0, 98.2),
          (98.2, 100.0, 98.1, 99.9), (99.9, 101.6, 99.0, 101.5), (101.5, 102.5, 101.3, 102.3)]
B_POST = dict(BASE, ob_entry="post_mss", draw_lock="off", htf_resist_cap=False, news_wait="off",
              min_draw_pts=0.0, leg_pd=0.0)


# --- #9 frozen rungs (review: the rung list was always empty) ------------------------------

def test_lock_marked_keeps_both_sides_and_frozen_rungs_scale_out():
    hist = history()
    df = day(A_ROWS, spike=True)
    tr, locks, log, _ = run(df, hist, Params(**BASE), A_LOCK)
    am = [lk for lk in locks if lk["session"] == "AM"][0]
    assert (am["side"], am["target"], am["name"]) == (1, 108.0, "pdh1")
    ctx = S.DayCtx(df, D0, hist, 5)
    lk = S.mark_levels(ctx, A_LOCK[570], 570, "AM", Params(**BASE))
    vals = {v for v, *_ in lk["marked"]}
    assert {104.0, 102.5, 108.0, 99.8, 90.0} <= vals                    # both sides, near ones too
    assert len(tr) == 1
    t = tr[0]
    assert t.entry_kind == "ob_pre" and t.entry == 100.0
    assert [(e[3], e[1]) for e in t.exits] == [("t1", 102.75), ("t2", 103.5), ("t3", 108.25)]
    q = [e[2] for e in t.exits]
    assert q == [t.shares // 2, t.shares // 4, t.shares - t.shares // 2 - t.shares // 4]   # 50/25/25
    assert t.exits[-1][1] == 108.25                                     # still ends at T (pool +1 tick)
    # partials off: everything at T; live rungs: the current levels below T
    tr2, *_ = run(df, hist, Params(**BASE, draw_lock_partials=False), A_LOCK)
    assert [(e[3], e[1]) for e in tr2[0].exits] == [("t1", 108.25)]
    tr3, *_ = run(df, hist, Params(**BASE, draw_lock_levels="live"), A_LOCK)
    assert tr3[0].exits[-1][1] == 108.25


def test_lock_final_exit_is_T_in_both_exit_modes_and_adds_close_there():
    hist = history()
    rows = A_ROWS[:5] + [(100.3, 100.9, 100.2, 100.8), (100.8, 101.5, 101.0, 101.4),
                         (101.4, 101.8, 101.3, 101.7), (101.7, 101.8, 100.95, 101.5),
                         (101.5, 103.0, 101.4, 102.9), (102.9, 104.0, 102.8, 103.9),
                         (103.9, 108.5, 103.8, 108.4)]
    df = day(rows, spike=True)
    p = Params(**dict(BASE, adds=(0.5,)), ob_adds=False)
    tr, *_ = run(df, hist, p, A_LOCK)
    t = tr[0]
    assert len(t.adds) == 1 and t.adds[0][1] == 101.3
    assert t.exits[-1][1] == 108.25 and sum(e[2] for e in t.exits) == t.shares + t.adds[0][2]
    tb, *_ = run(df, hist, replace(p, exit_mode="before"), A_LOCK)
    assert tb[0].exits[-1][1] == 107.5                                  # pool - exit_before


def test_lock_delivered_before_entry_no_trade_and_spent_in_pm():
    hist = history()
    rows = [(100.0, 108.1, 99.5, 99.6)] + A_ROWS[1:]
    tr, locks, *_ = run(day(rows, spike=True), hist, Params(**BASE), A_LOCK)
    am = [lk for lk in locks if lk["session"] == "AM"][0]
    assert tr == [] and am["delivered"] and am["delivered_i"] is not None
    # delivered by the trade (scenario A): no re-arm, and 108 is not the PM lock
    tr, locks, *_ = run(day(A_ROWS, spike=True), hist, Params(**BASE), A_LOCK)
    am = [lk for lk in locks if lk["session"] == "AM"][0]
    pm = [lk for lk in locks if lk["session"] == "PM"][0]
    assert len(tr) == 1 and am["delivered"] and am["traded"]
    assert pm["target"] is None or abs(pm["target"] - 108.0) > 1.0


def test_neutral_am_still_allows_pm():
    hist = history(hi=110.0, lo=90.0)
    pm_rows = [(r[0], r[1], r[2], r[3]) for r in A_ROWS]
    df = day(pm_rows, start="13:30")
    rows = {810: dict(draw_up=106.0, draw_up_name="D_fvg", draw_dn=float("nan"), draw_dn_name="")}
    tr, locks, *_ = run(df, hist, Params(**BASE), rows)
    am = [lk for lk in locks if lk["session"] == "AM"][0]
    assert am["side"] == 0
    assert len(tr) == 1 and tr[0].session == "PM" and tr[0].draw_px == 106.0
    assert tr[0].exits[-1][1] == 105.5                                  # array: exit_before


def test_pm_lock_can_pick_untaken_lunch_high_below_the_am_high():
    """Review (M7.1 reintroduced in mark_levels): the lunch high is the PM draw although the AM
    high above it was made earlier the same day."""
    hist = history(hi=120.0, lo=80.0)
    rows = [(100.0, 100.2, 99.8, 100.0)] * 6 + [(100.0, 108.0, 99.9, 100.0)] + [(100.0, 100.2, 99.8, 100.0)] * 23
    rows += [(100.0, 105.5, 99.0, 100.0)] + [(100.0, 100.2, 99.8, 100.0)] * 17
    df = day(rows)                                             # 09:30-13:30; AM high 108 at 10:00
    ctx = S.DayCtx(df, D0, hist, 5)
    lk = S.mark_levels(ctx, None, 810, "PM", Params(**BASE))
    assert ctx.am_hl[0] == 108.0 and ctx.sess["lunch"][0] == 105.5
    assert (lk["side"], lk["name"], lk["target"]) == (1, "lunch_high", 105.5)


# --- bug fixes M1.2 / M7.1 -----------------------------------------------------------------

def test_m12_swing_low_on_its_own_bar_is_intact_and_sweepable():
    """M1.2: intact() starts at the swing low's bar + 1, so an earlier lower low today (02:00
    spike to 97) does not hide a later swing low (98.5 at 09:40)."""
    hist = history()
    rows = [(100.0, 100.2, 99.5, 99.6), (99.6, 99.7, 99.0, 99.1), (99.1, 99.3, 98.5, 99.0),
            (99.0, 99.6, 99.2, 99.5), (99.5, 99.8, 99.4, 99.7), (99.7, 99.9, 99.5, 99.8),
            (99.8, 99.9, 98.0, 98.2)]
    df = day(rows)
    df.iloc[24] = [100.0, 100.1, 97.0, 99.9, 1.0]              # 02:00 overnight low 97
    p = Params(**BASE, pool_swings=True, or_minutes=0)
    ctx = S.DayCtx(df, D0, hist, 5, or_minutes=0)
    S._setup_news(ctx, D0, p)
    sd = S.Side(1, ctx.o, ctx.h, ctx.l, ctx.c, 1, 0.25)
    i = S._idx_at(ctx, 600)                                    # the 10:00 bar trades to 98.0
    k = S._idx_at(ctx, 580)                                    # the 09:40 swing low
    assert any(q.i == k for q in sd.pl)
    assert S._level_intact(ctx, sd.l, i, f"swing_low{k}", 98.5, "AM")
    for j in range(S._idx_at(ctx, 570), i + 1):
        S._scan(ctx, sd, j, p, "AM", 570, None, None, None)
    assert sd.sweep is not None and sd.sweep["key"] == f"swing_low{k}" and sd.sweep["level"] == 98.5
    # the old start (midnight) would have called it spent by the 97 low
    assert ctx.l[ctx.start:i].min() < 98.5


def test_m71_lunch_high_is_a_pm_target_and_the_old_rule_drops_it():
    hist = history(hi=120.0, lo=80.0)
    rows = [(100.0, 100.2, 99.8, 100.0)] * 6 + [(100.0, 108.0, 99.9, 100.0)] + [(100.0, 100.2, 99.8, 100.0)] * 23
    rows += [(100.0, 105.5, 99.0, 100.0)] + [(100.0, 100.2, 99.8, 100.0)] * 20
    df = day(rows)
    ctx = S.DayCtx(df, D0, hist, 5)
    sd = S.Side(1, ctx.o, ctx.h, ctx.l, ctx.c, 1)
    i = S._idx_at(ctx, 840)
    p = Params(**BASE, wick_levels=False, org_days=0)
    lv = S._targets(ctx, sd, i, 101.0, [], p, None, i - 1)
    assert (105.5, "pool") in lv and (108.0, "pool") in lv
    old = S._targets(ctx, sd, i, 101.0, [], replace(p, seen_from_created=False), None, i - 1)
    assert (105.5, "pool") not in old                           # the bug: spent by the AM high


def test_m71_london_pool_hidden_before_0500():
    # (the bar is at 04:30, after the 04:00 overnight-so-far snapshot: a 02:30 bar would show up in pre_at[180])
    hist = history(hi=120.0, lo=80.0)
    df = day([])
    df.iloc[54] = [100.0, 101.7, 99.9, 100.0, 1.0]              # 04:30: London high 101.7
    ctx = S.DayCtx(df, D0, hist, 5)
    sd = S.Side(1, ctx.o, ctx.h, ctx.l, ctx.c, 1)
    p = Params(**BASE, wick_levels=False, org_days=0)
    i3, i5 = S._idx_at(ctx, 295), S._idx_at(ctx, 330)
    assert (101.7, "pool") not in S._targets(ctx, sd, i3, 100.5, [], p, None, i3 - 1)
    assert (101.7, "pool") in S._targets(ctx, sd, i5, 100.5, [], p, None, i5 - 1)
    sh = S.Side(-1, ctx.o, ctx.h, ctx.l, ctx.c, 1)
    df.iloc[55] = [100.0, 100.1, 98.3, 100.0, 1.0]
    ctx = S.DayCtx(df, D0, hist, 5)
    sh = S.Side(-1, ctx.o, ctx.h, ctx.l, ctx.c, 1)
    assert (-98.3, "pool") not in S._targets(ctx, sh, i3, -99.5, [], p, None, i3 - 1)
    assert (-98.3, "pool") in S._targets(ctx, sh, i5, -99.5, [], p, None, i5 - 1)


# --- #6 breaker MT, #5 mirror, #14 zone modes ---------------------------------------------

def b_day(rows):
    """Scenario B frame (the 09:30 swing high 101.2 keeps the 09:40 bounce from counting as the
    structure shift)."""
    return day(rows)


def _b(rows_after, p=None, mirror_=False, **kw):
    hist = history(hi=112.0, lo=88.0)
    df = b_day(B_ROWS + rows_after)
    if mirror_:
        hist, df = [mirror(x) for x in hist], mirror(df)
    tr, locks, log, _ = run(df, hist, p or Params(**B_POST), **kw)
    return tr, log


def test_breaker_mt_wick_below_holds_and_close_below_exits():
    tr, _ = _b([(102.3, 102.4, 100.3, 101.0)])                  # wick to 100.3 < MT, close above
    t = tr[0]
    assert t.unicorn and t.unicorn_side == "bull" and t.entry == 101.3 and t.bz_mt == 100.55
    assert "breaker_mt" not in "+".join(e[3] for e in t.exits)
    tr, _ = _b([(102.3, 102.4, 100.0, 100.2)])                  # fill bar closes below the MT
    assert [(e[3], e[1]) for e in tr[0].exits] == [("breaker_mt", 100.2)]
    tr, _ = _b([(102.3, 102.4, 100.3, 101.0), (101.0, 101.1, 100.3, 100.4)])   # the next bar
    assert [(e[3], e[1]) for e in tr[0].exits] == [("breaker_mt", 100.4)]
    off = replace(Params(**B_POST), breaker_mt_respect=False)
    tr, _ = _b([(102.3, 102.4, 100.0, 100.2)], off)
    assert tr[0].exits[0][3] != "breaker_mt"


def test_breaker_mt_close_below_cancels_and_floor_drops_only_the_unicorn_pick():
    rows8 = [(101.5, 102.0, 100.4, 101.8)]                       # FVG 100.0-100.4: below the MT
    after = [(101.8, 101.9, 100.45, 100.5), (100.5, 100.6, 100.0, 100.2)]
    base = B_ROWS[:8] + rows8
    hist = history(hi=112.0, lo=88.0)
    df = b_day(base + after)
    p = Params(**B_POST, breaker_mt_entry_floor=False)
    tr, *_ = run(df, hist, p)
    assert tr == []                                             # cancelled by the 100.5 close
    tr, *_ = run(df, hist, replace(p, breaker_mt_respect=False))
    assert len(tr) == 1 and tr[0].entry == 100.4 and tr[0].unicorn
    tr, *_ = run(df, hist, replace(p, breaker_mt_entry_floor=True))       # spec 6b: plain FVG
    assert len(tr) == 1 and tr[0].entry == 100.4 and not tr[0].unicorn and tr[0].bz_mt is None
    tr, *_ = run(df, hist, replace(p, breaker_mt_entry_floor=True, breaker_mt_floor_strict=True))
    assert tr == []


@pytest.mark.parametrize("zone", ["range", "body"])
def test_unicorn_exact_price_mirror(zone):
    """#5: the bearish unicorn is the bullish one on mirrored prices (K - p), to the cent."""
    p = replace(Params(**B_POST), breaker_zone=zone)
    after = [(102.3, 102.4, 100.3, 101.0)]
    lg, _ = _b(after, p)
    sh, _ = _b(after, p, mirror_=True)
    a, b = lg[0], sh[0]
    assert (a.side, b.side) == ("long", "short") and (a.unicorn_side, b.unicorn_side) == ("bull", "bear")
    assert b.entry == pytest.approx(K - a.entry) and b.stop == pytest.approx(K - a.stop)
    assert b.bz_top == pytest.approx(K - a.bz_bottom) and b.bz_bottom == pytest.approx(K - a.bz_top)
    assert b.bz_mt == pytest.approx(K - a.bz_mt) and b.shares == a.shares
    assert [x[1] for x in b.exits] == pytest.approx([K - x[1] for x in a.exits])
    with pytest.raises(ValueError):
        Params(unicorn_sides="up")
    lo, _ = _b(after, replace(p, unicorn_sides="long"), mirror_=True)
    assert not lo or not lo[0].unicorn


def test_breaker_zone_leg_and_last_modes():
    o, h, l, c = (np.array(x, float) for x in zip(*B_ROWS))
    z = L.breaker_zone(o, h, l, c, 1, 5, 8, mode="leg")
    assert (z.top, z.bottom, z.src) == (101.0, 98.6, 3) and z.mt == pytest.approx(99.8)
    z = L.breaker_zone(o, h, l, c, 1, 5, 8, mode="last")
    assert (z.top, z.bottom, z.src) == (101.0, 100.1, 3)
    o2 = o.copy(); c2 = c.copy(); o2[3], c2[3] = 100.4, 100.35        # 09:45 now a down close
    z = L.breaker_zone(o2, h, l, c2, 1, 5, 8, mode="last")
    assert z.src == 2 and (z.top, z.bottom) == (100.4, 98.7)          # the last up-close candle
    bb = L.breaker_zone(-o, -l, -h, -c, 1, 5, 8, kind="bear", mode="leg")
    assert (bb.top, bb.bottom) == (-98.6, -101.0)
    assert Params(breaker_zone="leg").breaker_zone == "leg"
    tr, _ = _b([(102.3, 102.4, 100.3, 101.0)], replace(Params(**B_POST), breaker_zone="leg"))
    assert tr[0].unicorn and tr[0].bz_mt == pytest.approx(99.8)


@pytest.mark.skipif(not ES, reason="no ES data")
def test_es_2023_01_03_breaker_mt_is_the_candle_range_midpoint():
    """#6 Ep02 replay on front-month data: every unicorn's breaker MT is its candle's (h+l)/2."""
    df = B.load("ES", 5, source="databento")
    df = df[(df.index >= "2022-12-01") & (df.index < "2023-01-21")]
    t = B.run(df, 5, "ES", Params(**FUT, ob_entry="post_mss", draw_lock="off", htf_resist_cap=False),
              meta=B.load_meta("ES", 5))
    uni = t[t.unicorn & t.bz_mt.notna()]
    assert len(uni)
    assert np.allclose(uni.bz_mt, (uni.bz_top + uni.bz_bottom) / 2)


# --- #11 OB entry before the break ------------------------------------------------------

def test_ob_pre_break_fills_next_bar_no_fvg_after_mss_no_resend():
    hist = history()
    tr, _, log, _ = run(day(A_ROWS, spike=True), hist, Params(**BASE), A_LOCK)
    t = tr[0]
    assert t.entry_kind == "ob_pre" and str(t.armed)[11:16] == "09:45" and str(t.entry_time)[11:16] == "09:50"
    assert t.stop == pytest.approx(98.25)                         # MT stop < 1 pt -> sweep extreme - one tick (Ep 08 pad)
    assert len(log) == 1                                          # armed once, no FVG order after MSS
    # scenario B (MSS at 10:05): the OB order arms at the MSS bar, the FVG never replaces it
    tr, log = _b([(102.3, 102.4, 100.3, 101.0)], Params(**dict(B_POST, ob_entry="pre_break")))
    assert len(log) == 1 and tr[0].entry_kind == "ob_pre" and tr[0].entry == 100.4


def test_ob_pre_violation_on_fill_bar_does_not_cancel_and_bearish_mirror():
    hist = history()
    rows = A_ROWS[:4] + [(100.7, 100.8, 98.6, 98.7)] + A_ROWS[5:]    # fill bar closes below the bodies
    tr, *_ = run(day(rows, spike=True), hist, Params(**BASE), A_LOCK)
    assert len(tr) == 1 and tr[0].entry == 100.0
    lg, *_ = run(day(A_ROWS, spike=True), hist, Params(**BASE), A_LOCK)
    mrow = {570: dict(draw_dn=K - 104.0, draw_dn_name="D_fvg", draw_up=float("nan"), draw_up_name="")}
    sh, locks, *_ = run(mirror(day(A_ROWS, spike=True)), [mirror(x) for x in hist], Params(**BASE), mrow)
    a, b = lg[0], sh[0]
    assert b.side == "short" and b.entry_kind == "ob_pre"
    assert b.entry == pytest.approx(K - a.entry) and b.stop == pytest.approx(K - a.stop)
    assert [(e[3], e[1]) for e in b.exits] == [(e[3], pytest.approx(K - e[1])) for e in a.exits]


def test_ob_both_keeps_the_lower_entry_unless_cancel_on_mss():
    both = Params(**dict(B_POST, ob_entry="both"))
    tr, log = _b([(102.3, 102.4, 100.3, 101.0)], both)
    assert tr[0].entry_kind == "ob_pre" and tr[0].entry == 100.4 and len(log) == 1
    tr, log = _b([(102.3, 102.4, 100.3, 101.0)], replace(both, ob_entry_cancel_on_mss=True))
    assert tr[0].entry_kind == "fvg" and tr[0].unicorn and tr[0].entry == 101.3 and len(log) == 2


# --- #2 five handles = minimum room ------------------------------------------------------

def test_room_minimum_and_fixed_first_rung():
    rows = [(100.5, 100.6, 99.5, 99.6)] + A_ROWS[1:]              # bodies top 100.5 -> entry 100.5
    df = day(rows, spike=True)
    S.FUNNEL = Counter()
    try:
        tr, *_ = run(df, history(hi=105.0), Params(**BASE), A_LOCK)     # T 105.25: room 4.75
        assert tr == [] and S.FUNNEL["x_room_lt_min"] >= 1
    finally:
        S.FUNNEL = None
    tr, *_ = run(df, history(hi=105.25), Params(**BASE), A_LOCK)         # T 105.5: room 5.0
    assert len(tr) == 1 and tr[0].entry == 100.5
    # lock off, one draw at +12: t1 = draw - 0.5, no +5 rung; t1_fixed_pts switch adds it
    df = day(A_ROWS)
    p = Params(**BASE, draw_lock="off", exit_mode="before", wick_levels=False, org_days=0)
    hist = history(hi=112.0)
    t = run(df, hist, p)[0][0]
    assert (t.t1, t.t2) == (111.5, None)
    t = run(df, hist, replace(p, t1_fixed_pts=5.0))[0][0]
    assert (t.t1, t.t2) == (105.0, 111.5)
    t = run(df, hist, replace(p, t1_fixed_pts=5.0, t1_fixed_all=True))[0][0]
    assert (t.t1, t.t2) == (105.0, None)
    t = run(df, history(hi=105.6), replace(p, t1_fixed_pts=5.0))[0][0]
    assert t.t1 == pytest.approx(105.1)                            # draw within +6: no +5 rung


def _sb_ctx(rows, p):
    hist = history(hi=112.0, lo=88.0)
    ctx = S.DayCtx(day(rows), D0, hist, 5)
    S._setup_news(ctx, D0, p)
    ctx.equity, ctx.conf = p.account_equity, None
    return ctx


def test_sb_draw_mode_vs_fixed_and_rebalance_ext():
    p = replace(Params(**B_POST), wick_levels=False)
    ctx = _sb_ctx(B_ROWS + [(102.3, 102.4, 102.0, 102.2)], p)
    sd = S.Side(1, ctx.o, ctx.h, ctx.l, ctx.c, 1, 0.25)
    k0, i = S._idx_at(ctx, 570), S._idx_at(ctx, 610)
    o = sb_model._arm(ctx, sd, i, k0, p, 0.5, None, "AM", 600)
    assert o["entry"] == 101.3 and o["t1"] == 112.25 and o["levels"] == [112.25]    # exit AT the draw
    f = sb_model._arm(ctx, sd, i, k0, replace(p, sb_target_mode="fixed"), 0.5, None, "AM", 600)
    assert f["t1"] == pytest.approx(106.3) and f["levels"] == [pytest.approx(106.3), 112.0]
    assert sb_model._arm(ctx, sd, i, k0, replace(p, sb_room_pts=11.0), 0.5, None, "AM", 600) is None
    # M3.10: no immediate rebalance here, so the extension does not apply
    assert not sb_model.immediate_rebalance(sd, k0, i, 0.25)
    assert sb_model._arm(ctx, sd, i, k0, replace(p, sb_rebalance_ext=20.0), 0.5, None, "AM", 600)["t1"] == 112.25
    # A7: the 10:10 candle trades straight back to the 10:00 high (no gap) -> expect > 5 handles
    rows = B_ROWS[:6] + [(98.2, 100.0, 98.1, 99.9), (99.9, 101.6, 99.4, 101.5), (101.5, 102.5, 100.0, 102.3),
                         (102.3, 102.4, 102.0, 102.2)]
    ctx = _sb_ctx(rows, p)
    sd = S.Side(1, ctx.o, ctx.h, ctx.l, ctx.c, 1, 0.25)
    i = S._idx_at(ctx, 615)
    assert sb_model.immediate_rebalance(sd, S._idx_at(ctx, 600), i, 0.25)
    # caption-gap A7-immediate-rebalance-gates (ir_need_draw, default True): the extension acts only when the draw / bias was known beforehand and points this way
    assert sb_model._arm(ctx, sd, i, k0, replace(p, sb_rebalance_ext=20.0), 0.5, None, "AM", 600)["entry"] == 102.0            # no bias row: no extension
    assert sb_model._arm(ctx, sd, i, k0, replace(p, sb_rebalance_ext=20.0, ir_need_draw=False), 0.5, None, "AM", 600) is None    # the gate off: the old behaviour
    ctx.bias_row = dict(combo=1)
    assert sb_model._arm(ctx, sd, i, k0, replace(p, sb_rebalance_ext=10.0), 0.5, None, "AM", 600)["t1"] == 112.25
    assert sb_model._arm(ctx, sd, i, k0, replace(p, sb_rebalance_ext=20.0), 0.5, None, "AM", 600) is None
    assert sb_model._arm(ctx, sd, i, k0, p, 0.5, None, "AM", 600)["entry"] == 102.0


# --- #8 close before noon --------------------------------------------------------------

def test_am_exit_close_hold_tighten_and_widened_window():
    hist = history(hi=130.0)
    rows = A_ROWS[:5] + [(101.0, 101.2, 100.8, 101.0)] * 26 + [(101.0, 101.1, 100.5, 100.9)]
    df = day(rows, spike=True)
    q = Params(**BASE, draw_lock="off", min_draw_pts=0.0)
    t = run(df, hist, q)[0][0]
    assert t.exits[-1][3] == "am_exit" and str(t.exits[-1][0])[11:16] == "11:55"
    t = run(df, hist, replace(q, am_exit=0))[0][0]
    assert t.exits[-1][3] == "eod" and str(t.exits[-1][0])[11:16] == "16:10"
    t = run(df, hist, replace(q, am_exit_mode="tighten"))[0][0]
    assert t.exits[-1][3] == "stop" and t.exits[-1][1] == pytest.approx(100.55)   # set once at 11:55 (bar low 100.8 - one tick)
    # AM window widened to 12:30: the order armed at 11:50 is not filled into 12:00
    late = day(A_ROWS, start="11:35", spike=True)
    p = Params(**BASE, draw_lock="off", am=(570, 750), min_draw_pts=0.0)
    assert run(late, hist, p)[0] == []
    assert len(run(late, hist, replace(p, am_exit=0))[0]) == 1


# --- #10 sloppy days ---------------------------------------------------------------------

def test_sloppy_scalp_stand_aside_and_alias():
    hist = history(first=(104.0, 96.0))                            # last day 18 > 2 x 8: big_prev
    df = day(A_ROWS, spike=True)
    t = run(df, hist, Params(**BASE, sloppy_mode="scalp"), A_LOCK)[0][0]
    assert t.sloppy == "big_prev" and [(e[3], e[1]) for e in t.exits] == [("t1", 102.75)]
    tr, _, _, skips = run(df, hist, Params(**BASE, sloppy_mode="stand_aside", sb_model=True, ma_deuce=True), A_LOCK)
    assert tr == [] and skips and skips[0][2:] == ("sloppy", "big_prev")
    tr, _, _, skips = run(df, hist, Params(**BASE, neutral_skip=True), A_LOCK)
    assert tr == [] and skips[0][3] == "big_prev"
    tr, _, _, skips = run(df, hist, Params(**BASE), A_LOCK)        # owner default: stand aside
    assert tr == [] and skips and skips[0][2:] == ("sloppy", "big_prev")
    t = run(df, hist, Params(**BASE, sloppy_mode="off"), A_LOCK)[0][0]
    assert t.sloppy == "big_prev"                                  # "off": tag only


def test_sloppy_nfp_week_fomc_week_premium_run_inside_bisi():
    p = Params(sloppy_tests=("nfp_week", "fomc_week"))
    h = history(date(2026, 6, 3))
    assert S.sloppy_day(h, date(2026, 6, 3), p) == {"nfp_week:PM"}          # Wed PM only
    assert S.sloppy_day(h, date(2026, 6, 4), p) == set()                    # nfp_thu kept
    assert S.sloppy_day(h, date(2026, 6, 4), replace(p, nfp_thu=False)) == {"nfp_week"}
    assert "fomc_week" in S.sloppy_day(h, date(2023, 5, 2), p)              # FOMC + NFP week (Ep 03)
    assert "fomc_week" not in S.sloppy_day(h, date(2026, 6, 16), p)         # FOMC without NFP
    assert "fomc_week" in S.sloppy_day(h, date(2026, 6, 16), replace(p, sloppy_fomc_nfp=False))
    with pytest.raises(ValueError):
        Params(sloppy_tests=("bogus",))
    # premium run: 3 sessions up with higher lows, the last into an old high (101, 9 days back)
    base_ = [(104, 96, 100), (101, 95, 97), (99, 93, 95), (98, 92, 94), (97, 91, 93), (96, 90, 92),
             (95, 89, 91), (94, 88, 90), (96, 89, 95), (99, 92, 98)]
    mk = lambda rows: [rth_day(d, hi, lo, c) for d, (hi, lo, c) in zip(pd.bdate_range("2026-05-11", periods=11).date, rows)]
    q = Params(sloppy_tests=("premium_run",))
    days_ = mk(base_ + [(104.5, 95, 104)])
    assert S.sloppy_day(days_, date(2026, 5, 26), q) == {"premium_run"}
    assert S.sloppy_day(mk(base_ + [(100.5, 95, 100)]), date(2026, 5, 26), q) == set()   # short of it
    assert S.sloppy_day(mk(base_ + [(104.5, 91, 104)]), date(2026, 5, 26), q) == set()   # a lower low
    neg = [x.assign(open=K - x.open, high=K - x.low, low=K - x.high, close=K - x.close) for x in days_]
    assert S.sloppy_day(neg, date(2026, 5, 26), q) == {"premium_run"}       # discount run mirror
    # inside a daily FVG: gap 100-104 left by day 2, yesterday 101-103 inside it
    ib = [rth_day(d, hi, lo, c) for d, (hi, lo, c) in zip(
        pd.bdate_range("2026-05-11", periods=5).date,
        [(100, 96, 99), (107, 99, 106), (110, 104, 108), (106, 102, 103), (103, 101, 102)])]
    assert S.sloppy_day(ib, date(2026, 5, 18), Params(sloppy_tests=("inside_bisi",))) == {"inside_bisi"}


# --- #12 risk on SPY -------------------------------------------------------------------

@pytest.mark.skipif(not Path("data/mentorship/SPY_5min.csv").exists(), reason="no SPY data")
def test_spy_peak_open_risk_within_1_3_pct():
    df = B.load("SPY", 5)
    df = df[df.index >= df.index[-1] - pd.Timedelta(days=60)]
    t = B.run(df, 5, "SPY", Params(draw_lock="off", htf_resist_cap=False))
    if len(t):
        assert (t.entry_risk_pct <= 0.0121).all() and (t.peak_risk_pct <= 0.0131).all()


# --- #13 front-month frame ---------------------------------------------------------------

def test_load_meta_synthetic_roll_and_causal_roll_tag(tmp_path, monkeypatch):
    idx = pd.date_range(pd.Timestamp("2026-06-08 09:00", tz=NY), pd.Timestamp("2026-06-09 16:14", tz=NY), freq="1min")
    raw = pd.DataFrame({"open": 100.0, "high": 100.5, "low": 99.5, "close": 100.0, "volume": 1.0,
                        "instrument_id": np.where(idx < pd.Timestamp("2026-06-08 19:00", tz=NY), 1, 2)}, index=idx)
    adj = raw.copy()
    pre = idx < pd.Timestamp("2026-06-08 19:00", tz=NY)
    for k in ("open", "high", "low", "close"):
        adj.loc[pre, k] += 20.0
    adj.index = adj.index.tz_convert("UTC"); raw.index = raw.index.tz_convert("UTC")
    adj.to_csv(tmp_path / "XX_1min_db.csv"); raw.to_csv(tmp_path / "XX_1min_dbraw.csv")
    monkeypatch.setattr(B, "DATA", tmp_path)
    monkeypatch.setattr(B, "_META", {})
    m = B.load_meta("XX", 1)
    assert (m.adj[m.index < pd.Timestamp("2026-06-08 19:00", tz=NY)] == 20.0).all()
    assert (m.adj[m.index >= pd.Timestamp("2026-06-08 19:00", tz=NY)] == 0.0).all()
    assert bool(m.roll[pd.Timestamp("2026-06-08 19:00", tz=NY)])
    # roll_day is known from the roll's bar on (a mid-day roll does not tag earlier fills)
    m2 = m.copy()
    m2["roll"] = False
    m2.loc[pd.Timestamp("2026-06-09 10:00", tz=NY), "roll"] = True
    m2["instrument_id"] = 2
    ctx = SimpleNamespace(idx=pd.date_range(pd.Timestamp("2026-06-09 00:00", tz=NY), periods=975, freq="1min"),
                          day=date(2026, 6, 9))
    S._attach_meta(ctx, m2, Params(), "ES")
    tr = SimpleNamespace(adj=0.0, contract=None, roll_day=False)
    S._stamp_frame(ctx, tr, 599)
    assert not tr.roll_day
    S._stamp_frame(ctx, tr, 600)
    assert tr.roll_day


@pytest.mark.skipif(not ES, reason="no ES data")
def test_es_2023_01_03_round_pool_3900():
    """#13 spec test (c), Ep 02 ~2:37 "the buy side is nice round number 3 900": at the 09:30
    open the untaken round handle above is a real 3900.00 (overnight traded 3906.75, which is why
    round_pool_from="session" is the reading); with "midnight" it would be 3950."""
    df = B.load("ES", 5, source="databento")
    df = df[(df.index >= "2022-12-01") & (df.index < "2023-01-04")]
    meta = B.load_meta("ES", 5)
    ds = B.days(df, 5, close=975)
    g, hist = ds[-1], [B.rth(x) for x in ds[:-1]]
    assert g.index[0].date() == date(2023, 1, 3)
    for frame_p, want in ((Params(es_pt=1.0), 3900.0), (Params(es_pt=1.0, round_pool_from="midnight"), 3950.0)):
        ctx = S.DayCtx(g, g.index[0].date(), hist, 5)
        S._attach_meta(ctx, meta, frame_p, "ES")
        i = S._idx_at(ctx, 570)
        up = S._round_levels(ctx, S.Side(1, ctx.o, ctx.h, ctx.l, ctx.c, 1), i, True, 2)
        assert up[0] - ctx.adj[i] == want
        if want == 3900.0:                                    # the short's sweep pool too
            sh = S._round_levels(ctx, S.Side(-1, ctx.o, ctx.h, ctx.l, ctx.c, 1), i, False)
            assert -sh[0] - ctx.adj[i - 1] == 3900.0


def test_round_pools_inert_warns_and_params_validate():
    x, _ = B.synthetic(start="2026-06-01", end="2026-06-12", tf=5, seed=1)
    with pytest.warns(UserWarning, match="round_pools"):
        B.prepare(x, 5, "ES", Params(es_pt=0.09))
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        B.prepare(x, 5, "SPY", Params(es_pt=0.09))
    for bad in (dict(htf_resist_src=("fvgs",)), dict(htf_resist_tfs=("2h",)), dict(htf_resist_tfs=()),
                dict(turtle_soup="cc"), dict(ts_stop="x"), dict(stop_flip="always"),
                dict(flip_triggers=("stop_flip",)), dict(round_pool_from="week")):
        with pytest.raises(ValueError):
            Params(**bad)


def test_round_step_rounds_targets_down_entries_up():
    ctx = SimpleNamespace(adj=np.array([3.0]))
    p = Params(es_pt=1.0, round_step_pts=5.0)
    sd, sh = SimpleNamespace(sign=1), SimpleNamespace(sign=-1)
    assert S._round_px(ctx, sd, 0, 104.0, p, up=False) == 103.0          # real 101 -> 100 (+3)
    assert S._round_px(ctx, sd, 0, 104.0, p, up=True) == 108.0           # real 101 -> 105
    assert S._round_px(ctx, sh, 0, -104.0, p, up=False) == -108.0        # short target: real 101 -> 105
    assert S._round_px(SimpleNamespace(adj=None), sd, 0, 101.0, p, up=False) == 100.0


# --- B8 flip triggers --------------------------------------------------------------------

def _daily(rows, start="2026-03-02"):
    ds = pd.bdate_range(start, periods=len(rows))
    return pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=ds)


FLIP_ROWS = [
    # week 1: a down-close week (high 101)
    (100, 101, 99, 100), (100, 100.5, 98, 98.5), (98.5, 99, 97, 97.5), (97.5, 98, 96, 96.5), (96.5, 97, 95, 95.5),
    # week 2: up with four daily BISIs, closes above week 1's high -> +1 (wk_dc) from week 3
    (95.5, 97, 95.4, 96.8), (96.8, 99, 97.5, 98.8), (98.8, 101, 99.2, 100.8), (100.8, 103, 101.5, 102.8),
    (102.8, 104, 103.2, 103.8),
    # week 3: closes through the BISI bottoms 101, 99, 97 (pd3 by Wednesday); ends below week 2's low
    (103.8, 104, 100.5, 100.8), (100.8, 101, 98.5, 98.6), (98.6, 98.8, 96.5, 96.6), (96.6, 97, 95, 95.5),
    (95.5, 96, 94, 94.5),
    # week 4: Tue closes above Monday's upper-wick CE; Thu body closes back above the week's open
    (94.5, 95, 93, 93.5), (93.5, 97, 93.4, 96.8), (96.8, 97, 94, 94.2), (94.2, 96, 94.0, 95.5),
    (95.5, 96, 95, 95.8)]


def test_flip_triggers_pd3_close_above_thu_wopen():
    d = _daily(FLIP_ROWS)
    w = htf.weeks(d)
    arrs = htf._arrays(*(d[k].values.astype(float) for k in ("open", "high", "low", "close")), "D", lambda i: i + 1)
    day_ = lambda k: d.index[k]
    base = htf._flip(d, w, arrs, ("wk_dc",))
    assert base[day_(10)] == 1 and base[day_(14)] == 1 and base[day_(15)] == -1     # week ends only
    pd3 = htf._flip(d, w, arrs, ("wk_dc", "flip_pd3"))
    assert pd3[day_(10)] == 1 and pd3[day_(14)] == -1                               # 3 BISIs broken
    ca = htf._flip(d, w, arrs, ("wk_dc", "flip_close_above"))
    assert ca[day_(16)] == -1 and ca[day_(17)] == 0                                 # Tue close -> neutral
    tw = htf._flip(d, w, arrs, ("wk_dc", "flip_thu_wopen"))
    assert tw[day_(18)] == -1 and tw[day_(19)] == 1                                 # Thu back above 94.5
    assert htf._flip(d, w, arrs, ("flip_pd3",))[day_(19)] == 0                      # pd3 needs a state
    with pytest.raises(ValueError):
        htf._flip(d, w, arrs, ("stop_flip",))
    with pytest.raises(ValueError):
        htf._flip(d, w, arrs, ("bogus",))


def test_flip_column_no_look_ahead_on_synthetic_overnight():
    """Every B8 trigger (table column `flip`) only uses completed sessions."""
    rng = np.random.default_rng(5)
    idx = pd.date_range(pd.Timestamp("2026-01-04 18:00", tz=NY), pd.Timestamp("2026-04-30 16:00", tz=NY), freq="15min")
    idx = idx[(idx.weekday < 5) | ((idx.weekday == 6) & (idx.hour >= 18))]
    idx = idx[~((idx.hour == 17) | ((idx.weekday == 4) & (idx.hour >= 17)))]
    c = 100 + np.cumsum(rng.normal(0, 0.25, len(idx)))
    df = pd.DataFrame({"open": c, "high": c + 0.3, "low": c - 0.3, "close": c + rng.normal(0, 0.1, len(idx)),
                       "volume": 1.0}, index=idx)
    trig = ("ob_mt", "wk_dc", "flip_pd3", "flip_close_above", "flip_thu_wopen")
    full = htf.table(df, flip_triggers=trig)
    assert set(full.flip.unique()) <= {-1, 0, 1} and (full.flip != 0).sum() >= 5
    assert (full.flip != htf.table(df).flip).any()                     # the new triggers act
    for d in list(full.index)[-40::7]:
        cut = pd.Timestamp(d, tz=NY) + pd.Timedelta(hours=9, minutes=30)
        part = htf.table(df[df.index < cut], flip_triggers=trig)
        assert part.loc[d].flip == full.loc[d].flip


# --- M12 turtle-soup variants ----------------------------------------------------------

def test_turtle_variant_helpers():
    # cc_1h_ob: the last DOWN 1h candle that started at or before the extreme, complete by bar i
    idx = pd.date_range(pd.Timestamp("2026-06-09 09:00", tz=NY), periods=36, freq="5min")
    o = np.r_[np.full(12, 101.0), np.full(12, 100.0), np.full(12, 99.0)]
    c = np.r_[np.full(12, 100.5), np.full(12, 100.5), np.full(12, 98.0)]
    sd = SimpleNamespace(o=o, h=np.maximum(o, c) + 0.2, l=np.minimum(o, c) - 0.2, c=c, __dict__={})
    sd = S.Side(1, o, np.maximum(o, c) + 0.2, np.minimum(o, c) - 0.2, c, 1)
    ctx = SimpleNamespace(idx=idx, tf=5)
    assert S._hour_down_candle(ctx, sd, 20, 23) == (101.0, 101.2, 11)    # 09:00 hour: down close
    assert S._hour_down_candle(ctx, sd, 20, 10) is None                  # not complete yet
    assert S._hour_down_candle(ctx, sd, 30, 35)[2] == 35                 # 11:00 hour, done at 11:55
    # turtle soup core depth / back (M12.5)
    l = np.array([10, 9.5, 9.0, 9.8, 9.9, 10.2]); cc = np.array([10.2, 9.7, 9.3, 10.1, 10.0, 10.4])
    assert L.turtle_soup(l, cc, 9.4, 2, 3, 1.0, 3) and not L.turtle_soup(l, cc, 9.4, 2, 3, 0.3, 3)


def test_ts_gate_mss_blocks_deep_sweeps():
    hist = history()
    df = day(A_ROWS, spike=True)
    assert len(run(df, hist, Params(**BASE), A_LOCK)[0]) == 1
    S.FUNNEL = Counter()
    try:
        tr = run(df, hist, Params(**BASE, ts_gate_mss=True, ts_max_pts=0.5), A_LOCK)[0]
        assert tr == [] and S.FUNNEL["x_ts_gate"] >= 1                      # 1.3 pts deep > 0.5
    finally:
        S.FUNNEL = None


def test_stop_flip_after_a_breaker_stop_out():
    rows = B_ROWS + [(102.3, 102.4, 100.6, 101.0), (101.0, 101.1, 99.0, 99.2)]   # held, then stopped
    p = Params(**B_POST, breaker_mt_respect=False, stop_flip="breaker")
    hist = history(hi=112.0, lo=88.0)
    tr, *_ = run(b_day(rows), hist, p)
    assert tr[0].exits[-1][3] == "stop" and tr[0].stop < tr[0].bz_bottom
    ctx_state = {}
    lost = S._after_close(dict(trade=tr[0]), [], p, {"AM": True}, ctx_state.setdefault("s", {"reentered": {}}))
    assert lost == "long" and ctx_state["s"]["flip"] == -1


# --- #9 test (i): paper lock == backtest lock -----------------------------------------------

@pytest.mark.skipif(not ES, reason="no ES data")
def test_paper_lock_equals_backtest_lock():
    df = B.load("ES", 5, source="databento")
    now = pd.Timestamp("2024-03-14 14:00", tz=NY)
    df = df[(df.index >= "2024-01-20") & (df.index < now)]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        p = Params(**FUT)
        bt = B.run(df, 5, "ES", p, partial_last=True)
        trades, log, locks = paper.evaluate(df, "ES", 5, p, now)
    want = [(lk["session"], lk["side"], lk["target"], lk["name"]) for lk in bt.attrs["locks"] if lk["day"] == now.date()]
    got = [(lk["session"], lk["side"], lk["target"], lk["name"]) for lk in locks]
    assert want and got == want
    a = bt[bt.date == now.date()]
    assert len(trades) == len(a)


# --- no look-ahead: every switch the review listed, plus the new ones ----------------------

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


COLS = ["entry_time", "entry", "stop", "t1", "shares", "entry_kind", "sloppy", "draw_px", "lh_sweet"]
SYN = dict(es_pt=0.09, use_bias=False, min_draw_pts=0, leg_pd=0)


def test_look_ahead_synthetic_review_switches_a():
    x, y = B.synthetic(start="2026-06-01", end="2026-07-31", tf=5, seed=3)
    p = Params(**SYN, turtle_soup="2023", ts_stop="gap", price_frame="raw", round_pool_step_pts=10.0,
               round_step_pts=5.0, breaker_mt_floor_strict=True, breaker_zone="leg", stop_flip="breaker",
               draw_lock_partials=False, ob_adds=False, ob_entry="both", news_range_pd=True,
               news_range_target=False, year_end="long", last_hour_sweet=(905, 940),
               sloppy_mode="stand_aside", sloppy_tests=("big_prev", "premium_run", "fomc_week", "inside_bisi"),
               sloppy_run_days=2, sloppy_fomc_nfp=False, breaker_mt_entry_floor=False,
               breaker_mt_respect=True, draw_lock_pick="nearest", round_pool_from="midnight")
    _no_look_ahead(x, 5, "RW", p, COLS, partner=y)


def test_look_ahead_synthetic_review_switches_b():
    x, y = B.synthetic(start="2026-06-01", end="2026-07-31", tf=5, seed=3)
    p = Params(**SYN, turtle_soup="or60", ts_entry="level", breaker_zone="last", year_end="tag",
               stop_flip="smt", sb_model=True, sb_target_mode="fixed", sb_rebalance_ext=6.0,
               am_exit_extras=False, ob_entry="post_mss", ts_gate_mss=True)
    _no_look_ahead(x, 5, "RW", p, COLS + ["setup"], partner=y)


def test_look_ahead_synthetic_turtle_cc_limit_and_year_end_with():
    x, y = B.synthetic(start="2026-06-01", end="2026-07-31", tf=5, seed=3)
    p = Params(**SYN, turtle_soup="cc_limit", ts_cc_below_pts=0.5, year_end="december", year_end_map="with")
    full = _no_look_ahead(x, 5, "RW", p, COLS, every=2, partner=y)
    assert (full.entry_kind == "ts_cc_limit").any()


def test_look_ahead_synthetic_turtle_external():
    x, y = B.synthetic(start="2026-06-01", end="2026-07-31", tf=5, seed=3)
    p = Params(**SYN, turtle_soup="external", ts_stop="ext", ob_entry="post_mss")
    full = _no_look_ahead(x, 5, "RW", p, COLS, every=3, partner=y)
    assert (full.entry_kind == "ts_external").any()


def test_look_ahead_synthetic_turtle_2023_arrays_and_sb_lock():
    x, y = B.synthetic(start="2026-06-01", end="2026-07-31", tf=5, seed=3)
    p = Params(**SYN, turtle_soup="2023", ts_need_htf=True, draw_lock="off")
    full = _no_look_ahead(x, 5, "RW", p, COLS, every=4, partner=y)
    assert (full.entry_kind == "turtle_soup").any()


@pytest.mark.skipif(not ES, reason="no ES data")
def test_look_ahead_es_cap_lock_and_flip_switches():
    df = B.load("ES", 5, source="databento")
    df = df[(df.index >= "2023-08-01") & (df.index < "2023-11-15")]
    meta = B.load_meta("ES", 5)
    p = Params(**FUT, draw_lock_near_cap=True, htf_resist_min_room=5.0, htf_resist_buffer_pts=1.0,
               htf_bias="flip", bias_neutral="both",
               flip_triggers=("ob_mt", "wk_dc", "flip_pd3", "flip_close_above", "flip_thu_wopen"),
               round_step_pts=5.0, ob_entry="both", draw_lock_levels="frozen")
    _no_look_ahead(df, 5, "ES", p, ["entry_time", "entry", "stop", "t1", "draw_px", "capped", "lock_capped",
                                    "entry_kind"], meta=meta)


@pytest.mark.skipif(not ES, reason="no ES data")
def test_look_ahead_es_turtle_cc_1h_ob():
    """M12.3 cc_1h_ob (a daily OB at the sweep: rare - 2 trades in ES 2023-01..2024-06)."""
    df = B.load("ES", 5, source="databento")
    df = df[(df.index >= "2022-12-01") & (df.index < "2023-01-21")]
    meta = B.load_meta("ES", 5)
    p = Params(**FUT, turtle_soup="cc_1h_ob", ts_r_mults=(1.0, 4.0), ts_be_r=1.5, draw_lock="off",
               htf_resist_cap=False)
    full = _no_look_ahead(df, 5, "ES", p, ["entry_time", "entry", "stop", "t1", "t2", "entry_kind"],
                          every=4, meta=meta)
    cc = full[full.entry_kind == "ts_cc_1h_ob"]
    assert len(cc) == 1 and str(cc.entry_time.iloc[0])[:16] == "2023-01-19 10:15"
    r = cc.iloc[0]
    R = (r.t1 - r.stop) / 2                     # limit L: t1 = L + R, stop = L - R (the fill may be lower)
    assert r.t2 - r.t1 == pytest.approx(3 * R, abs=1e-6)                       # runner 4R (switch)
    assert r.entry <= r.t1 - R + 1e-6


@pytest.mark.skipif(not ES1, reason="no ES 1m data")
def test_look_ahead_es_london_sb_lock_and_rebalance_ext():
    es = B.load("ES", 1, source="databento")
    es = es[(es.index >= "2024-01-02") & (es.index < "2024-02-10")]
    p = Params(**FUT, am=(0, 0), pm=(0, 0), sb_model=True, sb_london=True, sb_rebalance_ext=8.0,
               am_exit_extras=False, sloppy_mode="off")   # owner's sloppy stand-aside skips this window's only trade
    full = _no_look_ahead(es, 1, "ES", p, ["entry_time", "entry", "stop", "t1", "setup", "draw_px"], lag=1)
    assert 120 in B.lock_cuts(p)
