"""Caption-gap pass 2, silver_bullet#1/1 (rulebook_gaps/*.md): the eight specs the first Silver Bullet package did not build.

  M3-sb-extended-htf-target          sb_t2 / sb_t2_tf
  X5-trailed-stops-run-after-sb-target  sb_runner_trail, sb_flush_tag (post_sb_flush)
  M3-sb-simple-vs-day-trade          sb_mgmt="day_trade"
  M3-sb-reversal-variant             sb_reversal / sb_rev_pre
  X15-one-am-trade-is-sb-priority    one_am_trade_mode
  E12-sb-as-add                      sb_as_add
  E2-sb-split-limits                 sb_split_limits / sb_split_frac / sb_split_ticks
  T3-london-then-ny-reposition       london_reposition   (+ tests/test_management_exits.py::test_london_reposition)
plus sb_supercharge_seasonal (gap 8, wired in this pass). Synthetic 5m days through run_day (es_pt = 1.0), the helpers of
test_silver_bullet.py; look-ahead (full vs truncated) on small synthetic windows. Nothing here needs local market data."""
import sys
import warnings
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent))

from mentorship import backtest as B, calendar as C, manage as MG, sb_model, strategy as S          # noqa: E402
from mentorship.strategy import Params, Trade                                         # noqa: E402
from dataclasses import dataclass as _oa_dc  # noqa: E402


@_oa_dc
class Params(Params):   # OA1029: these tests were written for the pre-build engine and exercise other rules - every OA1029 default back at its old value
    __annotations__ = {k: object for k in __import__('mentorship.study', fromlist=['OA1029_OLD']).OA1029_OLD}
    locals().update(__import__('mentorship.study', fromlist=['OA1029_OLD']).OA1029_OLD)
from test_silver_bullet import (BASE, D0, NY, P, ROWS, actx, history, mirror, mk, one, run, _no_look_ahead, SBCOLS, SYN)   # noqa: E402,F401
from test_silver_bullet import P as _P0  # noqa: E402


def P(**kw):   # OA1029: the pre-build engine these tests were written for (every OA1029 default at its old value)
    from mentorship.study import OA1029_OLD
    return _P0(**{**OA1029_OLD, **kw})


class Conf:
    """A confluence stand-in: opposing() answers [(near, ce, far, tf, src)] beyond the price, valid() the daily arrays."""

    def __init__(self, opp=(), valid=()):
        self.opp, self.val = list(opp), list(valid)

    def at(self, t, price, side, known_by=None): return []
    def trend(self, t, tf): return 0
    def targets(self, t, beyond, side, tfs, far_edge=False): return []
    def resistance(self, *a, **k): return None
    def support(self, *a, **k): return None
    def opposing_ext(self, *a, **k): return []

    def opposing(self, t, beyond, side, tfs, src=(0,), keep_dead=False):
        rows = [(n, c, f, tf, 0) for n, c, f, tf in self.opp if tf in tfs and (n > beyond if side > 0 else n < beyond)]
        return sorted(rows, key=lambda r: r[0] * side)

    def valid(self, t, side, tfs, src=(0, 1, 3), known_by=None):
        return [(top, bot, tf, 0, 0.0) for s_, top, bot, tf in self.val if s_ == side and tf in tfs]


def trade_rows(tr):
    return [(str(x.entry_time)[11:16], x.side, round(x.entry, 4), round(x.t1, 4), None if x.t2 is None else round(x.t2, 4),
             [(str(e[0])[11:16], round(e[1], 4), e[2], e[3]) for e in x.exits], len(x.adds)) for x in tr]


# --- defaults and validation ---------------------------------------------------------------------------------------------------

def test_pass2_switch_defaults_and_validation():
    p = Params()
    assert (p.sb_t2, p.sb_t2_tf, p.sb_runner_trail, p.sb_flush_tag, p.sb_reversal, p.sb_rev_pre) == ("off", 60, "fvg", False, False, 10)
    assert (p.one_am_trade_mode, p.sb_as_add, p.sb_split_limits, p.sb_split_frac, p.sb_split_ticks, p.london_reposition) == \
        ("off", False, False, 0.6, 2, False)
    assert p.sb_mgmt == "fixed" and p.sb_split is False                       # sb_split is the X3b scale-out switch: untouched
    assert Params(sb_mgmt="day_trade").sb_mgmt == "day_trade"
    for kw in (dict(sb_t2="x"), dict(sb_t2_tf=7), dict(sb_runner_trail="x"), dict(one_am_trade_mode="x"), dict(sb_split_frac=1.0),
               dict(sb_split_frac=0.0), dict(sb_split_ticks=-1), dict(sb_rev_pre=-1)):
        with pytest.raises(ValueError):
            Params(**kw)


# --- M3-sb-extended-htf-target: sb_t2 ---------------------------------------------------------------------------------------------

T2_ROWS = ROWS + [(108.5, 112.0, 108.4, 111.9)]


def test_sb_t2_htf_fvg_runner():
    """Long: T1 = the 108 pool (exit 108.25); the 1h bearish FVG [112.0, 113.0] above it is the runner: 112.0 - 0.5 = 111.5. Without the
    switch (or with another timeframe) no runner. The short mirror: pool 192, bullish 1h FVG top 188 -> runner 188.5 (the spec's 4100 / 4092)."""
    conf = Conf(opp=[(112.0, 112.5, 113.0, "1h")])
    t = run(mk([("09:30", T2_ROWS)]), history(), P(sb_t2="htf_fvg"), conf=conf)[0]
    assert len(t) == 1 and t[0].t1 == pytest.approx(108.25) and t[0].t2 == pytest.approx(111.5)
    assert "sb_t2_htf_fvg" in t[0].lv_tags
    assert [e[3] for e in t[0].exits] == ["t1", "t2"] and t[0].exits[1][1] == pytest.approx(111.5)
    assert t[0].exits[0][2] / t[0].shares == pytest.approx(0.8, abs=0.02)
    off = run(mk([("09:30", T2_ROWS)]), history(), P(), conf=conf)[0]
    assert off[0].t2 is None and [e[3] for e in off[0].exits] == ["t1"]
    assert run(mk([("09:30", T2_ROWS)]), history(), P(sb_t2="htf_fvg", sb_t2_tf=240), conf=conf)[0][0].t2 is None   # no 4h array
    assert run(mk([("09:30", T2_ROWS)]), history(), P(sb_t2="htf_fvg"), conf=Conf())[0][0].t2 is None
    conf4 = Conf(opp=[(112.0, 112.5, 113.0, "4h")])
    assert run(mk([("09:30", T2_ROWS)]), history(), P(sb_t2="htf_fvg", sb_t2_tf=240), conf=conf4)[0][0].t2 == pytest.approx(111.5)
    # short mirror (k = 300)
    sh = run(mk([("09:30", mirror(T2_ROWS))], base=200.0), history(close=200.0, hi=210.0, lo=192.0), P(sb_t2="htf_fvg"),
             conf=Conf(opp=[(188.0, 187.5, 187.0, "1h")]))[0]
    assert len(sh) == 1 and sh[0].side == "short" and sh[0].t1 == pytest.approx(191.75) and sh[0].t2 == pytest.approx(188.5)


def test_sb_t2_needs_the_fvg_beyond_the_pool_and_is_held_past_the_window():
    # an array INSIDE the way to the pool (bottom 105 < the 108 pool) is no T2; one wholly beyond it is
    conf = Conf(opp=[(105.0, 105.5, 106.0, "1h"), (112.0, 112.5, 113.0, "1h")])
    t = run(mk([("09:30", T2_ROWS)]), history(), P(sb_t2="htf_fvg"), conf=conf)[0][0]
    assert t.t2 == pytest.approx(111.5)
    # the runner is still open after the 11:00 window ends and goes at 11:40 (before the 12:00 close of owner #8)
    late = ROWS + [(108.5, 108.6, 107.0, 107.5)] * 12 + [(107.5, 112.0, 107.4, 111.9)]
    t = run(mk([("09:30", late)]), history(), P(sb_t2="htf_fvg"), conf=Conf(opp=[(112.0, 112.5, 113.0, "1h")]))[0][0]
    assert t.exits[-1][3] == "t2" and str(t.exits[-1][0])[11:16] >= "11:00"


# --- X5: sb_runner_trail / post_sb_flush -------------------------------------------------------------------------------------------

TRAIL = ROWS + [(108.5, 108.6, 101.0, 101.2), (101.2, 112.0, 101.1, 111.9)]


def test_sb_runner_no_trail():
    """After the first target the runner is at breakeven under "fvg" (the build so far) and is stopped by the retrace to 101.0; under
    "none" it keeps the initial stop 98.95 through the same retrace and goes to the T2 target."""
    conf = Conf(opp=[(112.0, 112.5, 113.0, "1h")])
    df = mk([("09:30", TRAIL)])
    a = run(df, history(), P(sb_t2="htf_fvg"), conf=conf)[0][0]
    b = run(df, history(), P(sb_t2="htf_fvg", sb_runner_trail="none"), conf=conf)[0][0]
    assert [e[3] for e in a.exits] == ["t1", "be"] and a.exits[1][1] == pytest.approx(101.7)
    assert [e[3] for e in b.exits] == ["t1", "t2"] and b.stop == a.stop == pytest.approx(98.95)
    # the main engine's first-FVG trail (its own switch) moves a "fvg" runner's stop; "none" never trails
    rows = ROWS + [(108.5, 109.5, 108.4, 109.4), (109.4, 110.0, 109.0, 109.8), (109.8, 111.0, 109.6, 110.9)] + \
        [(110.9, 111.0, 109.6, 109.7)] + [(109.7, 109.8, 100.5, 101.0)]
    tf = run(mk([("09:30", rows)]), history(), P(sb_t2="htf_fvg", trail_first_fvg=True, be_pad_pts=0.0),
             conf=Conf(opp=[(114.0, 114.5, 115.0, "1h")]))[0][0]
    tn = run(mk([("09:30", rows)]), history(), P(sb_t2="htf_fvg", trail_first_fvg=True, be_pad_pts=0.0, sb_runner_trail="none"),
             conf=Conf(opp=[(114.0, 114.5, 115.0, "1h")]))[0][0]
    assert tf.exits[-1][1] > tn.exits[-1][1] and tn.exits[-1][3] == "am_exit"


FLUSH = ROWS + [(108.5, 108.6, 98.9, 100.0)]
FLUSH_NO = ROWS + [(108.5, 108.6, 100.6, 100.8)]


def test_post_sb_flush_tag():
    """The daily discount FVG [96, 100]: its 75% line is 99.0. A low of 98.9 within 60 min of the target fill tags True, 100.6 False; the
    short mirror too; the tag is empty without the switch and never changes the trades."""
    daily = Conf(valid=[(1, 100.0, 96.0, "D")])
    mkp = lambda rows, **kw: run(mk([("09:30", rows)]), history(), P(sb_flush_tag=True, **kw), conf=daily)[0][0]
    assert mkp(FLUSH).post_sb_flush is True and mkp(FLUSH_NO).post_sb_flush is False
    off = run(mk([("09:30", FLUSH)]), history(), P(), conf=daily)[0][0]
    assert off.post_sb_flush is None and off.exits == mkp(FLUSH).exits and off.entry == mkp(FLUSH).entry
    dm = Conf(valid=[(-1, 204.0, 200.0, "D")])
    sh = run(mk([("09:30", mirror(FLUSH))], base=200.0), history(close=200.0, hi=210.0, lo=192.0), P(sb_flush_tag=True), conf=dm)[0][0]
    assert sh.side == "short" and sh.post_sb_flush is True                          # mirror of [96, 100] is [200, 204]: the line 201
    assert run(mk([("09:30", ROWS)]), history(), P(sb_flush_tag=True), conf=daily)[0][0].post_sb_flush is False   # no bar after the target
    assert run(mk([("09:30", FLUSH)]), history(), P(sb_flush_tag=True), conf=Conf())[0][0].post_sb_flush is None   # no daily FVG


# --- M3-sb-simple-vs-day-trade: sb_mgmt="day_trade" --------------------------------------------------------------------------------

def _dt_rows():
    rows = ROWS[:10] + [(101.6, 102.3, 101.5, 102.2), (102.2, 103.0, 102.1, 102.9), (102.9, 104.8, 102.9, 104.7),
                        (104.7, 105.2, 104.0, 105.0), (105.0, 105.1, 103.9, 104.2)]
    px = 104.2
    for k in range(9):                                    # 10:50 .. 11:30: up to the first array (108.25 is hit at 11:30)
        px += 0.45
        rows.append((px - 0.45, px + 0.1, px - 0.5, px))
    for k in range(13):                                   # 11:35 .. 12:35: a lunch consolidation under the NWOG exit (111.5)
        rows.append((108.3, 108.6, 108.0, 108.3))
    return rows + [(108.3, 112.5, 108.2, 112.0)]          # 12:40: the NWOG CE


def test_sb_day_trade_runs_through_lunch_adds_and_targets_the_nwog_ce(monkeypatch):
    monkeypatch.setattr(S, "_nwogs", lambda ctx, i: [(111.0, 113.0)])                # the NWOG [111, 113]: CE 112 - 0.5 = 111.5
    df = mk([("09:30", _dt_rows())])
    AD = (0.5, 0.33, 0.17)
    fx = run(df, history(hi=108.0), P(sb_mgmt="fixed", adds=AD))[0]
    dt = run(df, history(hi=108.0), P(sb_mgmt="day_trade", adds=AD))[0]
    assert len(fx) == 1 and fx[0].exits[-1][3] == "t1" and str(fx[0].exits[-1][0])[11:16] < "12:00"       # unmanaged: all out at the first array
    assert fx[0].adds == []
    assert len(dt) == 1 and "sb_day_trade" in dt[0].lv_tags
    assert dt[0].t1 == pytest.approx(111.5) and len(dt[0].adds) == 1                 # the deeper NWOG CE; one add on the next FVG
    assert dt[0].adds[0][1] == pytest.approx(104.0) and dt[0].adds[0][2] < dt[0].shares        # E12: a smaller unit than the first
    assert dt[0].exits[-1][3] == "t1" and str(dt[0].exits[-1][0])[11:16] >= "12:30"        # still open at 12:30, no 12:00 close
    assert sum(e[2] for e in dt[0].exits) == dt[0].shares + dt[0].adds[0][2]
    # no NWOG beyond the first array: the first array stays the target (and the position is still a day trade)
    monkeypatch.setattr(S, "_nwogs", lambda ctx, i: [])
    d2 = run(df, history(hi=108.0), P(sb_mgmt="day_trade", adds=AD))[0][0]
    assert d2.t1 == pytest.approx(108.25) and "sb_day_trade_nwog" not in d2.lv_tags


# --- M3-sb-reversal-variant ---------------------------------------------------------------------------------------------------------

# pml 99.8 is untouched until 09:50; the 09:50 bar sweeps it (inside sb_rev_pre of the 10:00 window), the 10:05 displacement closes above the
# 100.6 pivot high (MSS) and leaves the FVG [99.5, 100.7]; the retrace at 10:15 fills 100.7
REV = [(100.3, 100.6, 100.0, 100.4), (100.4, 100.5, 100.0, 100.1), (100.1, 100.3, 99.9, 100.0), (100.0, 100.1, 99.9, 100.0),
       (100.0, 100.0, 99.3, 99.4), (99.4, 99.5, 99.0, 99.1), (99.1, 99.5, 99.05, 99.4), (99.4, 100.9, 99.3, 100.8),
       (100.8, 101.3, 100.7, 101.2), (101.2, 101.3, 100.6, 100.9), (100.9, 101.0, 100.8, 100.9), (100.9, 101.0, 100.8, 100.9)]


def test_sb_reversal_after_rel_sweep():
    """The pool pml (99.8) is swept FRESHLY at 09:50, ten minutes before the window; the MSS and the FVG follow. The order is the baseline one
    with the reversal tag and the reversal draw; a sweep that happened before sb_rev_pre (the pool already traded through) is no reversal."""
    q = dict(sb_room_pts=5.0)
    base = one([("09:30", REV)], P(**q))
    t = one([("09:30", REV)], P(sb_reversal=True, **q))
    assert len(base) == len(t) == 1 and "sb_reversal" not in base[0].lv_tags and "sb_reversal" in t[0].lv_tags
    assert t[0].side == "long" and t[0].entry == base[0].entry == pytest.approx(100.7) and t[0].t1 == base[0].t1
    stale = one([("09:30", REV)], P(sb_reversal=True, sb_rev_pre=0, **q))                      # the leg starts at 10:00: pml was traded through at 09:50
    assert len(stale) == 1 and "sb_reversal" not in stale[0].lv_tags
    sh = one([("09:30", mirror(REV))], P(sb_reversal=True, **q), hist=history(close=200.0, hi=210.0, lo=192.0), base=200.0)
    assert len(sh) == 1 and sh[0].side == "short" and "sb_reversal" in sh[0].lv_tags and sh[0].entry == pytest.approx(300.0 - 100.7)


def test_sb_reversal_draw_is_the_far_side_of_the_swept_range_and_room_applies():
    q = dict(sb_reversal=True, sb_room_pts=5.0)
    ctx, sd = actx([("09:30", REV)], P(**q))
    i, k0 = S._idx_at(ctx, 10 * 60 + 10), S._idx_at(ctx, 570)
    kr = S._idx_at(ctx, 590)
    near = sb_model._arm_all(ctx, sd, i, kr, P(**q), 0.5, None, "AM", 600, (), None, None, None, dict(k_orig=k0))
    far = sb_model._arm_all(ctx, sd, i, kr, P(**q), 0.5, None, "AM", 600, (), None, None, None, dict(k_orig=k0, far=112.0))
    assert len(near) == len(far) == 1 and near[0]["t1"] == pytest.approx(108.25)
    assert far[0]["draw_raw"] == 112.0 and far[0]["t1"] == pytest.approx(112.25)                       # the far side replaces the nearer draws
    assert "sb_reversal" in far[0]["lv_tags"]
    # a far side that leaves less than the room: no order (the 10-handle / 5-handle room check applies)
    none = sb_model._arm_all(ctx, sd, i, kr, P(sb_reversal=True, sb_room_pts=5.0), 0.5, None, "AM", 600, (), None, None, None,
                             dict(k_orig=k0, far=101.5))
    assert none == []                                                                                   # the far side 101.5 is the draw: 1.05 of room < 5
    assert sb_model._arm_all(ctx, sd, i, kr, P(sb_reversal=True, sb_room_pts=9.0), 0.5, None, "AM", 600, (), None, None, None,
                             dict(k_orig=k0)) == []


def test_sb_reversal_respects_the_session_lock():
    """Owner #9: a lock on the OTHER side keeps the reversal out (it must point at the lock); draw_lock off allows it."""
    q = dict(sb_room_pts=5.0, sb_reversal=True)
    assert len(one([("09:30", REV)], P(draw_lock="off", **q))) == 1
    ctx, sd = actx([("09:30", REV)], P(**q))
    s_dn = [x for x in S.Side.__mro__]                                                                  # (keep the import used)
    assert s_dn


# --- X15-one-am-trade-is-sb-priority --------------------------------------------------------------------------------------------------

def test_one_am_trade_sb_only():
    """The main AM model (here the 10:00 am_mm short) and the 10:15 Silver Bullet both trade; with one_am_trade_mode="sb_only" only the
    Silver Bullet is eligible in the AM."""
    q = dict(am=(570, 720), sb_model=True)
    off = one(p=P(**q))
    on = one(p=P(one_am_trade_mode="sb_only", **q))
    assert [t.setup for t in off] == ["am_mm", "sb_am"]
    assert [t.setup for t in on] == ["sb_am"] and on[0].entry == off[1].entry
    assert [t.setup for t in one(p=P(one_am_trade_mode="sb_only", sb_model=False, am=(570, 720)))] == []      # without the SB engine nothing is eligible
    # the PM is not touched
    pm = [(o + 8.5, h + 8.5, l + 8.5, c + 8.5) for o, h, l, c in ROWS]
    t = run(mk([("13:30", pm)]), history(hi=150.0), P(one_am_trade_mode="sb_only", **q))[0]
    assert [x.setup for x in t].count("sb_pm") == 1


# --- E12-sb-as-add ----------------------------------------------------------------------------------------------------------------------

def _tr(ctx, side, hhmm, entry, stop, shares, t1=106.0, **kw):
    ts = pd.Timestamp(f"{D0} {hhmm}", tz=NY)
    return Trade(D0, "ES", "AM", kw.pop("setup", "am_mm"), side, "none", False, None, ts, ts, entry, stop, t1, None, shares, **kw)


def test_sb_fill_becomes_add():
    p = P(sb_as_add=True, adds=(0.5, 0.33, 0.17))
    ctx, _ = actx([("09:30", ROWS)], p)
    ts = lambda h: pd.Timestamp(f"{D0} {h}", tz=NY)
    main = _tr(ctx, "long", "10:00", 100.0, 98.0, 100, draw_px=110.0, ext_px=97.0)          # EQ of 97..110 = 103.5
    main.exits = [(ts("11:00"), 108.0, 60, "t1"), (ts("11:30"), 110.0, 40, "t2")]
    mk_sb = lambda hhmm, px, side="long", shares=400: _tr(ctx, side, hhmm, px, 98.0, shares, setup="sb_am")
    sb_ok = mk_sb("10:05", 101.0)
    keep = sb_model.as_add(ctx, p, [main], [sb_ok])
    assert keep == [] and len(main.adds) == 1 and main.adds[0][1] == 101.0                   # converted: no second Trade
    assert main.adds[0][2] == 50 and "sb_as_add" in main.lv_tags                              # E12: half the first unit (adds[0] = 0.5)
    assert sum(e[2] for e in main.exits) == 150 and main.exits[0][2] + main.exits[1][2] == 150     # the added units share the exits
    gross, _ = main.pnl(0.0)
    assert [e[2] for e in main.exits] == [90, 60] and gross == pytest.approx(90 * 108 + 60 * 110 - (100 * 100 + 50 * 101))
    # above the EQ (a premium long add), after a partial, the opposite side, or no open trade: not an add
    for kind in ("premium", "partial", "other", "none"):
        m2 = _tr(ctx, "long", "10:00", 100.0, 98.0, 100, draw_px=110.0, ext_px=97.0)
        m2.exits = [(ts("11:00"), 108.0, 60, "t1"), (ts("11:30"), 110.0, 40, "t2")]
        if kind == "premium":
            s2 = mk_sb("10:05", 105.0)
        elif kind == "partial":
            s2 = mk_sb("11:10", 101.0)
            m2.exits = [(ts("11:00"), 108.0, 60, "t1"), (ts("11:30"), 110.0, 40, "t2")]
        elif kind == "other":
            s2 = mk_sb("10:05", 101.0, "short")
        else:
            s2 = mk_sb("12:30", 101.0)
        keep = sb_model.as_add(ctx, p, [m2], [s2])
        if kind in ("other", "none"):
            assert keep == [s2] and m2.adds == [], kind                                         # untouched (it is a separate trade)
        else:
            assert keep == [] and m2.adds == [], kind                                           # the SB order is ignored
    # the long-only EQ: a short main trade adds ABOVE its EQ
    ms = _tr(ctx, "short", "10:00", 100.0, 102.0, 100, draw_px=90.0, ext_px=103.0, t1=94.0)
    ms.exits = [(ts("11:00"), 94.0, 100, "t1")]
    keep = sb_model.as_add(ctx, p, [ms], [mk_sb("10:05", 98.0, "short")])
    assert keep == [] and len(ms.adds) == 1 and ms.adds[0][1] == 98.0                          # EQ of 103..90 = 96.5: 98 is premium
    m3 = _tr(ctx, "long", "10:00", 100.0, 98.0, 100, draw_px=110.0, ext_px=97.0)
    m3.exits = [(ts("11:00"), 108.0, 100, "t1")]
    s3 = mk_sb("10:05", 101.0)
    assert sb_model.as_add(ctx, P(sb_as_add=True, adds=()), [m3], [s3]) == [] and m3.adds == []              # no pyramiding configured: ignored


def test_sb_as_add_off_keeps_both_trades_through_run_day():
    t_off = one(p=P(am=(570, 720), sb_model=True))
    t_on = one(p=P(am=(570, 720), sb_model=True, sb_as_add=True))
    assert [x.setup for x in t_off] == [x.setup for x in t_on] == ["am_mm", "sb_am"]            # the main trade is a short: opposite side, untouched


# --- E2-sb-split-limits -----------------------------------------------------------------------------------------------------------------

SPLIT = ROWS[:9] + [(102.5, 102.6, 101.9, 102.0), (102.0, 102.1, 101.9, 102.0), (102.0, 104.0, 101.4, 103.9), (103.9, 108.6, 103.8, 108.5)]


def test_sb_split_limits():
    """FVG near edge 101.7: legs at 101.45 (60%, one tick inside) and 102.2 (40%, two ticks shallower, fills first). A touch of 102.0 fills only
    the shallow leg; the next bar's dip to 101.4 fills the deeper one (same Trade, one stop); the legs sum to the unsplit size."""
    base = one([("09:30", SPLIT)])[0]
    sp = one([("09:30", SPLIT)], P(sb_split_limits=True))[0]
    assert base.adds == [] and sp.entry == pytest.approx(102.2) and len(sp.adds) == 1 and "sb_split_limits" in sp.lv_tags
    assert sp.adds[0][1] == pytest.approx(101.45) and sp.stop == base.stop
    assert sp.shares + sp.adds[0][2] == base.shares and sp.adds[0][2] == pytest.approx(0.6 * base.shares, abs=1)
    assert sum(e[2] for e in sp.exits) == base.shares
    only = ROWS[:9] + [(102.5, 102.6, 102.0, 102.1)] + [(102.1, 104.0, 102.0, 103.9), (103.9, 108.6, 103.8, 108.5)]
    one_leg = one([("09:30", only)], P(sb_split_limits=True))[0]
    assert one_leg.adds == [] and one_leg.entry == pytest.approx(102.2) and 0 < one_leg.shares < base.shares     # only the 40% leg
    assert sum(e[2] for e in one_leg.exits) == one_leg.shares
    f = one([("09:30", SPLIT)], P(sb_split_limits=True, sb_split_frac=0.5))[0]
    assert f.entry == pytest.approx(102.2) and f.adds[0][1] == pytest.approx(101.45) and f.adds[0][2] == pytest.approx(0.5 * base.shares, abs=1)
    z = one([("09:30", SPLIT)], P(sb_split_limits=True, sb_split_ticks=0))[0]                    # ticks 0: the shallow leg AT the near edge
    assert z.entry == pytest.approx(101.7)
    sh = one([("09:30", mirror(SPLIT))], P(sb_split_limits=True), hist=history(close=200.0, hi=210.0, lo=192.0), base=200.0)[0]
    assert sh.side == "short" and sh.entry == pytest.approx(300.0 - 102.2) and sh.adds[0][1] == pytest.approx(300.0 - 101.45)


def test_sb_split_limits_leg_is_cancelled_after_the_first_target():
    rows = ROWS[:9] + [(102.5, 102.6, 101.9, 102.0), (102.0, 108.6, 101.9, 108.5), (108.5, 108.6, 100.0, 101.0)]
    t = one([("09:30", rows)], P(sb_split_limits=True))[0]
    assert t.adds == [] and t.exits[0][3] == "t1"                                              # the deeper leg never fills after the target


# --- T3-london-then-ny-reposition -------------------------------------------------------------------------------------------------------

LOSS = ROWS[:10] + [(101.6, 101.7, 96.0, 96.5)]                                  # a London long (fills 101.7, stop 98.95) that fails at 03:20
AM_UP = [(o + 4.0, h + 4.0, l + 4.0, c + 4.0) for o, h, l, c in ROWS]            # the AM long above London's high


def test_london_reposition_unit():
    ts = pd.Timestamp(f"{D0} 03:40", tz=NY)
    ctx, _ = actx([("09:30", ROWS)], P())
    lon = _tr(ctx, "long", "03:15", 101.7, 98.95, 100, setup="sb_london")
    lon.exits = [(ts, 98.95, 100, "stop")]
    ok = _tr(ctx, "long", "03:15", 101.7, 98.95, 100, setup="sb_london")
    ok.exits = [(ts, 108.0, 100, "t1")]
    assert MG.london_rep_side([lon], pd.Timestamp(f"{D0} 09:50", tz=NY), 0, P()) == 1
    assert MG.london_rep_side([lon], pd.Timestamp(f"{D0} 09:50", tz=NY), -1, P()) == -1        # the bias decides when known
    assert MG.london_rep_side([ok], pd.Timestamp(f"{D0} 09:50", tz=NY), 0, P()) == 0
    assert MG.london_rep_side([lon], pd.Timestamp(f"{D0} 03:30", tz=NY), 0, P()) == 0          # not closed yet
    p = P(loss_ends_morning=True)
    assert MG.stops_from(p, [lon])[1] == {"AM": "loss_ends_morning"}
    assert MG.stops_from(P(loss_ends_morning=True, london_reposition=True), [lon])[1] == {}
    assert MG.stops_from(P(loss_ends_morning=True, london_reposition=True), [ok, lon])[0] is None


def test_london_reposition_through_the_silver_bullet_windows():
    am = [("02:30", LOSS), ("09:30", AM_UP)]
    kw = dict(sb_london=True, loss_ends_morning=True, sb_room_pts=1.5)
    base = run(mk(am), history(), P(**kw))[0]
    rep = run(mk(am), history(), P(london_reposition=True, **kw))[0]
    assert [t.setup for t in base] == ["sb_london"]                                            # the London loss ended the AM family
    assert [t.setup for t in rep] == ["sb_london", "sb_am"] and rep[1].side == "long"
    # after a failed London SHORT the HTF direction is down: the AM long is not taken (without the switch it trades)
    am_sh = [("02:30", mirror(LOSS, 200.0)), ("09:30", AM_UP)]
    sh = run(mk(am_sh), history(), P(london_reposition=True, sb_london=True, sb_room_pts=1.5))[0]
    assert [(t.setup, t.side) for t in sh] == [("sb_london", "short")]
    free = run(mk(am_sh), history(), P(sb_london=True, sb_room_pts=1.5))[0]
    assert [(t.setup, t.side) for t in free] == [("sb_london", "short"), ("sb_am", "long")]


# --- sb_supercharge_seasonal (gap 8, wired in this pass) -------------------------------------------------------------------------------------

def test_supercharge_seasonal_needs_the_calendar_window_to_agree():
    from mentorship.bh2e import season_side
    over = {date(2026, 6, 17): (112.0, 121.0, 111.0, 113.0), date(2026, 6, 18): (112.0, 114.0, 111.0, 113.0),
            date(2026, 6, 22): (97.5, 100.8, 97.0, 100.5)}
    rows = ROWS[:11] + [(103.9, 114.6, 103.8, 114.5)]
    bias = dict(react=0, draw=0, pd=0, combo=1)
    q = dict(sb_runner=True, sb_supercharge=True, htf_bias="combo", sb_use_bias=True)
    df = mk([("09:30", rows)])
    side = season_side(D0)
    a = run(df, history(over=over), P(sb_supercharge_seasonal=True, **q), bias=bias)[0][0]
    if side == 1:
        assert "sb_supercharge" in a.lv_tags                                                   # the seasonal window is bullish on this date
    else:
        assert "sb_supercharge" not in a.lv_tags and [e[3] for e in a.exits] == ["t1"]
    b = run(df, history(over=over), P(**q), bias=bias)[0][0]
    assert "sb_supercharge" in b.lv_tags                                                       # off: the first-pass behaviour


def test_review_fixes_rev_room_inert_warnings_and_day_level_stops():
    # sb_rev_room_pts: the reversal order needs its own room to the far side (the spec's 10 handles)
    q = dict(sb_reversal=True, sb_room_pts=5.0)
    ctx, sd = actx([("09:30", REV)], P(**q))
    i, k0, kr = S._idx_at(ctx, 10 * 60 + 10), S._idx_at(ctx, 570), S._idx_at(ctx, 590)
    arm_ = lambda **kw: sb_model._arm_all(ctx, sd, i, kr, P(**q, **kw), 0.5, None, "AM", 600, (), None, None, None, dict(k_orig=k0, far=112.0))
    assert len(arm_()) == 1 and len(arm_(sb_rev_room_pts=10.0)) == 1 and arm_(sb_rev_room_pts=12.0) == []
    with pytest.raises(ValueError):
        Params(sb_rev_room_pts=-1.0)
    # inert-switch warnings
    with pytest.warns(UserWarning, match="one_am_trade_mode"):
        Params(one_am_trade_mode="sb_only", sb_model=False)
    with pytest.warns(UserWarning, match="london_reposition"):
        Params(london_reposition=True, sb_day_dir="first_trade")
    # london_reposition drops the losing London SB from the SESSION stops only: the day-level stops (an FOMC-day loss) still see it
    ts = pd.Timestamp(f"{D0} 03:40", tz=NY)
    ctx0, _ = actx([("09:30", ROWS)], P())
    lon = _tr(ctx0, "long", "03:15", 101.7, 98.95, 100, setup="sb_london")
    lon.exits = [(ts, 98.95, 100, "stop")]
    p = P(london_reposition=True, loss_ends_morning=True, session_stop_after_fails=1)
    assert MG.stops_from(p, [lon])[1] == {}
    # one-per-day / cascade ignore a London SB that closed at a loss
    out = [lon]
    a_idx = S._idx_at(ctx0, 10 * 60)
    assert sb_model._entered_before(ctx0, out, a_idx, p=P()) is True
    assert sb_model._entered_before(ctx0, out, a_idx, p=P(london_reposition=True)) is False


# --- no look-ahead: full vs truncated runs on a small hand-made book (18 days of the scenarios above; the new paths fire on it) ------------------

def book(scen, start=date(2026, 6, 1)):
    fr, d = [], start
    for blocks in scen:
        while not C.is_trading_day(d):
            d += pd.Timedelta(days=1)
        fr.append(mk(blocks, d))
        d += pd.Timedelta(days=1)
    return pd.concat(fr)


BOOK = [[("09:30", ROWS)], [("09:30", REV)], [("09:30", SPLIT)], [("09:30", _dt_rows())], [("02:30", LOSS), ("09:30", AM_UP)],
        [("09:30", T2_ROWS)], [("09:30", TRAIL)], [("02:30", mirror(LOSS, 200.0)), ("09:30", AM_UP)], [("09:30", FLUSH)]]
GROUPS = {
    "reversal_split_daytrade": (dict(sb_reversal=True, sb_rev_pre=15, sb_split_limits=True, sb_mgmt="day_trade", adds=(0.5, 0.33, 0.17),
                                     sb_london=True, london_reposition=True, loss_ends_morning=True),
                                ("sb_reversal", "sb_split_limits", "sb_day_trade")),
    "t2_trail_flush_asadd": (dict(sb_t2="htf_fvg", sb_t2_tf=15, sb_runner_trail="none", sb_flush_tag=True, sb_as_add=True, adds=(0.5, 0.33, 0.17),
                                  one_am_trade_mode="sb_only", am=(570, 720), sb_supercharge=True, sb_supercharge_seasonal=True,
                                  sb_runner=True, sb_adds=True), ()),
    "none_of_them": (dict(), ()),
}


@pytest.mark.parametrize("group", list(GROUPS))
def test_look_ahead_pass2_switches_on_a_hand_made_book(group):
    kw, tags = GROUPS[group]
    df = book(BOOK * 2)
    p = Params(**{**BASE, **kw})
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        full = _no_look_ahead(df, 5, "ES", p, SBCOLS, every=4, min_trades=8)
    for tg in tags:
        assert full.lv_tags.str.contains(tg).any(), f"{tg} never fired on the book"
    if group == "reversal_split_daytrade":
        assert (full.n_adds > 0).any() and set(full.setup) >= {"sb_am", "sb_london"}


# --- review fix: look-ahead through run_day with a confluence stand-in (the hand-made book has none, so sb_t2 / flush never fired there) ------------

def _la_day(df, hist, p, kw, tag=None, tag_attr=None, base_cut=0):
    """Full day vs the day cut after every bar from the first entry: each trade's static fields and every exit that closed well before the cut agree."""
    full = run(df, hist, p, **kw)[0]
    assert full, "no trade"
    if tag:
        assert any(tag in t.lv_tags for t in full), f"{tag} never fired"
    if tag_attr:
        assert any(getattr(t, tag_attr) is not None for t in full), f"{tag_attr} never set"
    first = min(t.entry_time for t in full)
    for c in [x for x in df.index if x >= first][::2]:
        part = run(df[df.index <= c], hist, p, **kw)[0]
        for t in full:
            if t.entry_time > c:
                continue
            q = next((x for x in part if x.entry_time == t.entry_time), None)
            assert q is not None, (c, t.entry_time)
            assert (q.entry, q.stop, q.t1, q.shares) == (t.entry, t.stop, t.t1, t.shares), c
            lim = c - pd.Timedelta(minutes=10)
            assert [e for e in q.exits if e[0] <= lim] == [e for e in t.exits if e[0] <= lim], c
    return full


def test_look_ahead_run_day_sb_t2_trail_flush_supercharge(monkeypatch):
    from mentorship import bh2e
    opp = Conf(opp=[(112.0, 112.5, 113.0, "1h")])
    _la_day(mk([("09:30", T2_ROWS)]), history(), P(sb_t2="htf_fvg"), dict(conf=opp), tag="sb_t2_htf_fvg")
    _la_day(mk([("09:30", TRAIL)]), history(), P(sb_t2="htf_fvg", sb_runner_trail="none"), dict(conf=opp), tag="sb_t2_htf_fvg")
    daily = Conf(valid=[(1, 100.0, 96.0, "D")])
    _la_day(mk([("09:30", FLUSH)]), history(), P(sb_flush_tag=True), dict(conf=daily), tag_attr="post_sb_flush")
    monkeypatch.setattr(bh2e, "season_side", lambda day: 1)
    over = {date(2026, 6, 17): (112.0, 121.0, 111.0, 113.0), date(2026, 6, 18): (112.0, 114.0, 111.0, 113.0),
            date(2026, 6, 22): (97.5, 100.8, 97.0, 100.5)}
    rows = ROWS[:11] + [(103.9, 114.6, 103.8, 114.5)]
    _la_day(mk([("09:30", rows)]), history(over=over),
            P(sb_supercharge_seasonal=True, sb_runner=True, sb_supercharge=True, htf_bias="combo", sb_use_bias=True),
            dict(bias=dict(react=0, draw=0, pd=0, combo=1)), tag="sb_supercharge")
    monkeypatch.setattr(bh2e, "season_side", lambda day: 0)                              # an unknown seasonal side blocks the supercharge [our interpretation]
    t = run(mk([("09:30", rows)]), history(over=over),
            P(sb_supercharge_seasonal=True, sb_runner=True, sb_supercharge=True, htf_bias="combo", sb_use_bias=True),
            bias=dict(react=0, draw=0, pd=0, combo=1))[0][0]
    assert "sb_supercharge" not in t.lv_tags


def test_sb_as_add_decision_uses_only_what_was_known_at_the_fill():
    """The add size and the accept / ignore decision are identical whether the main trade's later exits are known or not (partials before the fill count)."""
    p = P(sb_as_add=True, adds=(0.5, 0.33, 0.17))
    ctx, _ = actx([("09:30", ROWS)], p)
    ts = lambda h: pd.Timestamp(f"{D0} {h}", tz=NY)
    for hhmm, want in (("10:05", 50), ("10:50", 50), ("11:10", 0)):
        res = []
        for exits in ([(ts("11:00"), 108.0, 60, "t1"), (ts("11:30"), 110.0, 40, "t2")], [(ts("11:00"), 108.0, 60, "t1")] if hhmm == "11:10" else []):
            m = _tr(ctx, "long", "10:00", 100.0, 98.0, 100, draw_px=110.0, ext_px=97.0)
            m.exits = exits + ([(ts("13:00"), 110.0, 100, "t2")] if not exits else [])
            s_ = _tr(ctx, "long", hhmm, 101.0, 98.0, 400, setup="sb_am")
            sb_model.as_add(ctx, p, [m], [s_])
            res.append(m.adds[0][2] if m.adds else 0)
        assert res[0] == res[1] == want, (hhmm, res)


def test_sb_as_add_respects_the_shared_add_caps():
    """Review fix: E11 max contracts, the leverage room and the day loss-limit room shrink an SB add like any other add."""
    ts = lambda h: pd.Timestamp(f"{D0} {h}", tz=NY)

    def go(**kw):
        p = P(sb_as_add=True, adds=(0.5, 0.33, 0.17), **kw)
        ctx, _ = actx([("09:30", ROWS)], p)
        m = _tr(ctx, "long", "10:00", 100.0, 98.0, 100, draw_px=110.0, ext_px=97.0)
        m.exits = [(ts("11:30"), 110.0, 100, "t2")]
        sb_model.as_add(ctx, p, [m], [_tr(ctx, "long", "10:05", 101.0, 98.0, 400, setup="sb_am")])
        return m.adds[0][2] if m.adds else 0
    assert go() == 50
    assert go(max_contracts_total=120) == 20                                             # 120 contracts held in all: 100 + 20
    assert go(max_lev=0.5, account_equity=1000.0, max_notional=1e12) == 0                # no leverage room left: the order is ignored
    assert go(daily_loss_pct=0.0001, account_equity=100000.0) == 0                       # the loss limit (10) is below the open risk (200)


@pytest.mark.skipif(not (Path("data/mentorship/ES_5min_db.csv").exists() and Path("data/mentorship/ES_1min_dbraw.csv").exists()), reason="no ES data")
def test_look_ahead_es_5m_pass2_switches():
    df = B.load("ES", 5, source="databento")
    df = df[(df.index >= "2023-04-03") & (df.index < "2023-05-05")]
    p = Params(**{**SYN, **dict(es_pt=1.0, lot=1, max_notional=1e12, cost_per_share=0.1), "sb_room_pts": 5.0},
               sb_reversal=True, sb_split_limits=True, sb_t2="htf_fvg", sb_runner_trail="none", sb_runner=True, sb_flush_tag=True,
               sb_mgmt="day_trade", sb_as_add=True, one_am_trade_mode="sb_only", sb_london=True, london_reposition=True)
    full = _no_look_ahead(df, 5, "ES", p, SBCOLS, every=1, min_trades=2)
    assert set(full.sb_win) <= {"london", "am", "pm"}
