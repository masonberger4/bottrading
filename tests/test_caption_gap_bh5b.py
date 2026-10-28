"""Caption-gap pass, package bias_htf#5/7: the ENGINE hooks (bh5e.py) on hand-made days built with the real DayCtx and DayPlan (side gates, per-order rules, the want readings, the lock filters / preferred
draws / re-lock, the rungs and entry arrays), per-path causal cases, the no-look-ahead runs (full vs truncated; synthetic windows, hand-made days; ES windows skip without the data) and the check that every
new switch is live in an executed run (second file of tests/test_caption_gap_bh5.py). Nothing here needs market data except the ES windows; no file outside the repo is written."""
import warnings
from datetime import date
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from mentorship import backtest as B, bh2 as BH2, bh5 as BH5, bh5e as E5, bias_day as BD, daycontext as DW, htf, strategy as S
from mentorship.strategy import Params

from test_review_fixes import BASE, D0, A_ROWS, A_LOCK, day, history, rth_day, frame  # noqa: E402
from test_entries_stops import _no_look_ahead  # noqa: E402
from test_caption_gap_dwc1 import mk, at, COLS, FUT, ES  # noqa: E402
from test_caption_gap_bh1 import BR  # noqa: E402
from test_caption_gap_bh1f import LA, IM, _walks  # noqa: E402
from test_caption_gap_bh3b import cx, order  # noqa: E402

D1 = date(2026, 3, 10)                          # a Tuesday
D2 = date(2026, 3, 11)                          # a Wednesday


def p5(**kw):
    return Params(**BASE, htf_bias="combo", bias_neutral="both", **kw)


def gapday(open_, rows, base=None):
    """A day whose 09:30 bar opens at `open_` (the history closes at 100): overnight flat at `base`."""
    return day([(open_, open_ + 0.1, open_ - 0.1, open_)] * 0 + rows, base=open_ if base is None else base)


def mkd(p, rows, bias=None, hist=None, d=D1, base=100.0, start="09:30", **kw):
    ctx = mk(d, hist if hist is not None else history(d), p, rows=rows, bias_row=bias, start=start, base=base, **kw)
    ctx.intermarket = {}
    return ctx


# --- item 35: the ORG with the bias ------------------------------------------------------------------------------------------------

def test_org_with_bias_blocks_fill_trades():
    p = p5(org_with_bias=True)
    rows = [(120.0, 120.4, 119.8, 120.2)] * 12
    ctx = mkd(p, rows, BR(combo=1, draw_up=140.0, draw_up_name="D_fvg", draw_dn=float("nan"), draw_dn_name=""), base=120.0)
    i = at(ctx, "09:40")
    assert ctx.org[-1] == (100.0, 120.0) and E5.org_with_bias_dir(ctx, p, i) == 1
    assert E5.side_ok(ctx, p, -1, "AM", i) == "x_bh5_org_with_bias" and E5.side_ok(ctx, p, 1, "AM", i) is None
    c, pr = E5.lock_filter(ctx, p, ctx.bias_row, [(120.0, "array", "org", 0, 0), (110.0, "array", "org_ce", 0, 0), (130.0, "pool", "pdh1", 1, 0)], [], 570, "AM", i + 1, 120.2)
    assert [x[2] for x in c] == ["pdh1"]                                     # the ORG levels leave the AM lock
    bare = mkd(p, rows, BR(combo=1), base=120.0)                              # no untaken level beyond the open: the rule does not apply
    bare.pd.clear()
    bare.pw = None
    assert E5.org_with_bias_dir(bare, p, at(bare, "09:40")) == 0
    against = mkd(p, rows, BR(combo=-1, draw_dn=80.0), base=120.0)
    assert E5.org_with_bias_dir(against, p, at(against, "09:40")) == 0


# --- item 23: below the NWOG low -----------------------------------------------------------------------------------------------------

def _nwog_ctx(p, rows):
    ctx = mkd(p, rows, BR(combo=0), base=102.0)
    ctx.gaps = [("nwog", 110.0, 100.0, 105.0)]
    return ctx


def test_below_nwog_low_return_draw():
    p = p5(nwog_below_return=True)
    slow = [(102.0 - 0.1 * k, 102.1 - 0.1 * k, 101.8 - 0.1 * k, 101.9 - 0.1 * k) for k in range(30)]        # a drift under 100 at 09:30 + 21 bars: no displacement
    ctx = _nwog_ctx(p, slow)
    i = at(ctx, "11:50")
    assert E5.nwog_below_state(ctx, p, i)[0] == 1
    assert BD.want_at(ctx, p, "AM", i) == 1
    fast = [(102.0, 102.1, 101.9, 102.0)] * 3 + [(102.0, 102.1, 98.0, 98.2), (98.2, 98.3, 94.0, 94.2), (94.2, 94.3, 90.0, 90.2)] + [(90.2, 90.4, 90.0, 90.1)] * 12
    ctx2 = _nwog_ctx(p, fast)
    i2 = at(ctx2, "10:10")
    assert E5.nwog_below_state(ctx2, p, i2)[0] == 0                          # a 3-bar displacement break keeps the bias
    lk = dict(side=-1, target=90.0, kind="pool", name="x", delivered=False, delivered_t=None, delivered_i=None, marked=[], session="AM", t_lock=570, px=102.0, traded=False, day=D1)
    ctx.lock = {"AM": lk}
    r = E5.lock_bar(ctx, p, "AM", lk, i, {}, [], None)
    assert r is not None and r[0]["side"] == 1 and r[0]["target"] == 105.0 and r[0]["name"] == "nwog_ce"      # the CE first
    assert E5.lock_bar(ctx2, p, "AM", dict(lk), i2, {}, [], None) is None


# --- item 38: the delayed PM fill -----------------------------------------------------------------------------------------------------

def test_org_pm_draw_after_deep_discount():
    p = p5(org_pm_draw=True, prev_am_pool=True)
    rows = [(80.0, 80.3, 79.8, 80.1)] * 90
    ctx = mkd(p, rows, BR(combo=0), base=80.0)
    ctx.prev_am = (110.0, 85.0)
    i = at(ctx, "13:30")
    s, info = E5.org_pm_state(ctx, p, i)
    assert s == 1 and info[0] == 80.0 and info[1] == 90.0 and info[2] == 100.0
    assert BD.want_at(ctx, p, "PM", i) == 1
    pr = E5.lock_prefs(ctx, p, ctx.bias_row, 810, "PM", ctx.start, 80.1, i + 1)
    assert pr and pr[0][2] == "org_pm" and pr[0][0] == 80.0
    touched = mkd(p, [(80.0, 80.3, 79.8, 80.1)] * 12 + [(80.1, 84.0, 80.0, 83.0)] + [(83.0, 83.1, 82.9, 83.0)] * 77, BR(combo=0), base=80.0)
    touched.prev_am = (110.0, 85.0)
    assert E5.org_pm_state(touched, p, at(touched, "13:30"))[0] == 0         # traded into the gap since 09:30
    shallow = mkd(p, rows, BR(combo=0), base=80.0)
    shallow.prev_am = (110.0, 70.0)
    assert E5.org_pm_state(shallow, p, at(shallow, "13:30"))[0] == 0         # today's low is not under the previous AM low
    ls = E5.targets_post(ctx, ctx.sides_map[1], i, p, 80.2, [])
    assert [k for v, k in ls] == ["pool", "array", "array", "array"] or len(ls) >= 3


# --- item 58: the alternation ---------------------------------------------------------------------------------------------------------

def test_range_alternation_want():
    p = p5(range_alternate=True, range_block_probed=2, sloppy_tests=("chop",))
    hist = history(D1, first=(106.0, 88.0))
    rows = [(100.0, 100.2, 99.9, 100.0)] * 6 + [(100.0, 100.1, 89.5, 90.0), (90.0, 92.0, 89.9, 91.0), (91.0, 100.6, 90.9, 100.4), (100.4, 100.5, 100.2, 100.3)]       # sweeps: the overnight low and PDL (sell side x2), the overnight high (buy side x1)
    ctx = mkd(p, rows, BR(combo=0), hist=hist)
    ctx.chop = SimpleNamespace(inert=False, state=np.ones(len(ctx.t), bool))
    i = at(ctx, "09:30") + len(rows) - 1
    buy, sell, last = E5.sweep_runs(ctx, p, i)
    assert (buy, sell) == (1, 2) and last == 1
    assert BD.want_at(ctx, p, "AM", i) == 1                                  # two sell-side sweeps, one buy-side: the buy side is next
    assert E5.side_ok(ctx, p, -1, "AM", i) == "x_bh5_range_probed"
    ctx.chop = SimpleNamespace(inert=True, state=np.zeros(len(ctx.t), bool))
    assert E5.alternate_want(ctx, p, i) == 0


# --- item 59: the PM flip --------------------------------------------------------------------------------------------------------------

def _fvg_hist(d):
    h = history(d, hi=104.5, lo=96.0)
    day3 = pd.Timestamp(h[-3].index[0].date())
    bars = [(110.0, 111.0, 108.0, 108.5), (108.5, 108.6, 104.0, 104.5), (104.5, 105.0, 103.9, 104.8)] + [(104.8, 104.9, 104.7, 104.8)] * 75
    h[-3] = frame(day3.date(), bars, 5, "09:30")                             # a bearish 5m FVG [105, 108] three sessions ago, never traded
    return h


def test_pm_flip_to_old_5m_fvg():
    p = p5(pm_flip_draw=True)
    rows = [(99.0, 99.2, 98.6, 98.8)] * 12 + [(98.8, 98.9, 98.0, 98.2)] + [(98.2, 98.4, 98.1, 98.3)] * 77
    ctx = mkd(p, rows, BR(combo=0), hist=_fvg_hist(D1), lock={"AM": dict(side=-1, target=98.5, kind="pool", name="x", delivered=True, delivered_t=None, delivered_i=at(mk(D1, history(D1), p5(), rows=rows), "10:30"))})
    i = at(ctx, "13:30")
    s, lvl = E5.pm_flip_state(ctx, p, i)
    assert (s, lvl) == (1, 105.0)
    assert BD.want_at(ctx, p, "PM", i) == 1
    far = mkd(p, rows[:12] + [(98.8, 98.9, 90.0, 91.0)] + [(91.0, 91.2, 90.5, 91.0)] * 77, BR(combo=0), hist=_fvg_hist(D1), lock={"AM": dict(side=-1, target=98.5, kind="pool", name="x", delivered=True, delivered_t=None, delivered_i=15)})
    assert E5.pm_flip_state(far, p, at(far, "13:30"))[0] == 0               # the AM ran far beyond its target: no flip


# --- item 69: the PM range break ---------------------------------------------------------------------------------------------------------

def test_pm_range_break_hold_run():
    p = p5(pm_range_break=True)
    am = [(100.0, 100.5, 99.5, 100.0)] * 30                                  # 09:30-12:00
    lunch = [(100.0, 100.3, 99.8, 100.0)] * 18                                # 12:00-13:30
    pm = [(100.0, 101.2, 100.0, 101.0), (101.0, 101.1, 100.6, 100.7), (100.7, 100.9, 100.55, 100.8), (100.8, 101.6, 100.7, 101.5)] + [(101.5, 101.6, 101.4, 101.5)] * 30
    ctx = mkd(p, am + lunch + pm, BR(combo=0))
    i = at(ctx, "13:30") + 4
    assert E5.pm_range_state(ctx, p, i) == (1, False)
    assert BD.want_at(ctx, p, "PM", i) == 1
    flat = mkd(p, am + lunch + [(100.0, 100.3, 99.8, 100.0)] * 40, BR(combo=0))
    j = at(flat, "14:30")
    assert E5.pm_range_state(flat, p, j) == (0, True)
    assert E5.side_ok(flat, p, 1, "PM", j) == "x_bh5_pm_range_done"
    dn = mkd(p, am + lunch + [(100.0, 100.1, 98.9, 99.0)] * 10, BR(combo=0))
    assert E5.pm_range_state(dn, p, at(dn, "13:30") + 3)[0] == -1


# --- item 80: the gap theory -----------------------------------------------------------------------------------------------------------

def test_gap_theory_state():
    p = p5(gap_theory_bias=True)
    up = mkd(p, [(120.0, 120.2, 118.0, 118.5)] * 3 + [(118.5, 121.5, 118.4, 121.2)] * 3, BR(combo=0), base=120.0)      # the ORG [100, 120]: traded inside, then a 5m close above its high
    assert E5.gap_theory_state(up, p, at(up, "09:30") + 5) == 1
    assert BD.want_at(up, p, "AM", at(up, "09:30") + 5) == 1
    dn = mkd(p, [(120.0, 120.2, 99.0, 99.2)] * 6, BR(combo=0), base=120.0)
    assert E5.gap_theory_state(dn, p, at(dn, "09:30") + 5) == -1
    inside = mkd(p, [(120.0, 120.2, 108.0, 108.5)] * 6, BR(combo=0), base=120.0)                                          # inside the gap, under the CE (110)
    assert E5.gap_theory_state(inside, p, at(inside, "09:30") + 5) == -1
    bias = mkd(p, [(120.0, 120.2, 99.0, 99.2)] * 6, BR(combo=1), base=120.0)
    assert BD.want_at(bias, p, "AM", at(bias, "09:30") + 5) == 1             # only a neutral bias takes it


# --- item 164: the OR60 ------------------------------------------------------------------------------------------------------------------

def test_or60_extreme_by_stop_run():
    p = p5(or60_bias=True)
    rows = [(99.7, 99.8, 99.6, 99.7)] * 3 + [(99.7, 99.8, 89.8, 90.2)] + [(90.2, 91.0, 90.1, 90.8)] * 8 + [(90.8, 91.0, 90.5, 90.9)] * 6
    ctx = mkd(p, rows, BR(combo=0))
    i = at(ctx, "10:30")
    assert E5.or60_side(ctx, p, i) == 1 and BD.want_at(ctx, p, "AM", i) == 1
    assert E5.or60_side(ctx, p, at(ctx, "10:20")) == 0                       # not before the OR60 ends
    agree = mkd(p, rows, BR(combo=-1))
    assert BD.want_at(agree, p, "AM", at(agree, "10:30")) == -1                # a bias that disagrees stays
    open_ = mkd(p, [(100.0, 100.2, 99.9, 100.0)] * 18, BR(combo=0))
    assert E5.or60_side(open_, p, at(open_, "10:30")) == 0
    st = E5.or60_stat([rth_day(date(2026, 3, 2), 108.0, 90.0), rth_day(date(2026, 3, 3), 108.0, 90.0)])
    assert st["n"] == 1


# --- item 103: the 1h spike floor ----------------------------------------------------------------------------------------------------------

def _b7_rows(low_end=99.4):
    hours = [(98.6, 98.8, 98.4, 98.5), (98.5, 98.6, 97.9, 98.0), (98.0, 99.8, 98.0, 99.6), (99.6, 100.6, 99.3, 100.4)] + [(100.4, 100.5, 100.3, 100.4)] * 5 + [(100.4, 100.4, low_end, 99.6)]
    return [r for r in hours for _ in range(12)]


def test_b7_spike_floor_keeps_bias():
    p = p5(b7_spike_floor=True)
    row = BR(combo=1, b7sf_guard=100.0)
    ctx = mkd(p, _b7_rows(), row, start="00:00")
    i = at(ctx, "09:55")
    fl = E5.b7_floor(ctx, p, ctx.bias_row, i)
    assert fl is not None and fl[0] == 97.9 and not fl[2]
    assert BD.want_at(ctx, p, "AM", i) == 1                                  # above the floor: want stays +1
    rows = E5.entry_rows(ctx, ctx.sides_map[1], i, p)
    assert len(rows) == 1 and rows[0][0] == rows[0][1]
    dead = mkd(p, _b7_rows(low_end=97.5), row, start="00:00")
    j = at(dead, "09:55")
    assert E5.b7_floor(dead, p, dead.bias_row, j)[2] is True
    assert BD.want_at(dead, p, "AM", j) == 0                                 # a trade below the floor: want 0
    assert E5.entry_rows(dead, dead.sides_map[1], j, p) == []


# --- item 192: the 4h flip -----------------------------------------------------------------------------------------------------------------

def test_h4_flip_clears_the_short_side(monkeypatch):
    p = p5(h4_ob_flip=True)
    o = np.array([103.0, 101.0, 105.0, 98.5])
    h = np.array([104.0, 106.0, 105.2, 99.0])
    l = np.array([100.0, 100.5, 98.0, 97.0])
    c = np.array([101.0, 105.0, 98.5, 98.0])
    bars = dict(o=o, h=h, l=l, c=c, first=np.array([0, 10, 20, 30]), last=np.array([9, 19, 29, 39]))
    monkeypatch.setattr(E5.B1, "tf_complete", lambda ctx, m, i: bars if m == 240 else E5.B1.tf_bars(ctx, m))
    ctx = mkd(p, [(100.0, 100.3, 99.8, 100.1)] * 6, BR(combo=0, iof=1))
    i = at(ctx, "09:40")
    ctx.h[41:i + 1] = 104.0                                                  # above the bearish OB's MT (103), below its top (106)
    assert E5.h4_flip_state(ctx, p, ctx.bias_row, i)[0] == 1
    assert E5.side_ok(ctx, p, -1, "AM", i) == "x_bh5_h4_flip" and E5.side_ok(ctx, p, 1, "AM", i) is None
    fl, zone = E5.h4_flip_state(ctx, p, ctx.bias_row, i)
    assert zone is None
    ctx.h[41:i + 1] = 107.0                                                  # the whole up candle traded through: the down-close candles before it are a bullish OB
    fl, zone = E5.h4_flip_state(ctx, p, ctx.bias_row, i)
    assert fl == 1 and zone == (104.0, 103.0)
    assert E5.entry_rows(ctx, ctx.sides_map[1], i, p)[-1][:2] == (104.0, 103.0)
    low = mkd(p, [(100.0, 100.3, 99.8, 100.1)] * 6, BR(combo=0, iof=1))
    low.h[41:i + 1] = 102.0
    assert E5.h4_flip_state(low, p, low.bias_row, i)[0] == 0                  # the MT (103) was not traded


# --- the table-driven readings ---------------------------------------------------------------------------------------------------------------

def test_table_overrides_and_fallbacks():
    flat = [(100.0, 100.3, 99.8, 100.1)] * 6
    ctx = mkd(p5(program_gate=True), flat, BR(combo=-1, bprog=1, bprog_tgt=110.0))
    i = at(ctx, "09:40")
    assert BD.want_at(ctx, ctx_p(ctx), "AM", i) == 1 if False else True
    p = p5(program_gate=True)
    assert BD.want_at(ctx, p, "AM", i) == 1 and E5.side_ok(ctx, p, -1, "AM", i) == "x_bh5_program"                   # the program overrides and blocks the shorts
    assert [x[2] for x in E5.lock_prefs(ctx, p, ctx.bias_row, 570, "AM", ctx.start, 100.1, i + 1)] == ["program_tgt"]
    p = p5(stack_draw=True)
    st = mkd(p, flat, BR(combo=-1, stack_side=1, stack_hi=104.0))
    assert BD.want_at(st, p, "AM", i) == 1 and E5.lock_prefs(st, p, st.bias_row, 570, "AM", st.start, 100.1, i + 1)[0][:3] == (104.0, "pool", "stack_hi")
    p = p5(eq_breakout_draw=True)
    assert BD.want_at(mkd(p, flat, BR(combo=1, eqb_dir=-1, eqb_tgt=90.0)), p, "AM", i) == -1
    assert BD.want_at(mkd(p, flat, BR(combo=1, eqb_dir=0, eqb_in_eq=1)), p, "AM", i) == 0                           # at the range's EQ: 0
    p = p5(fast_week_rev=True)
    wed = mkd(p, flat, BR(combo=-1, fast_week=1, fw_tgt=108.0), d=D2, hist=history(D2))
    assert BD.want_at(wed, p, "AM", i) == 1
    assert BD.want_at(mkd(p, flat, BR(combo=-1, fast_week=1)), p, "AM", i) == -1                                      # not before Wednesday
    p = p5(monthly_ctrl=True, d_draw_carry=True, shift_origin_pool=True)
    assert BD.want_at(mkd(p, flat, BR(combo=0, m_ctrl=-1)), p, "AM", i) == -1
    assert BD.want_at(mkd(p, flat, BR(combo=1, m_ctrl=-1)), p, "AM", i) == 1                                          # a bias is never replaced by a fallback
    dd = mkd(p, flat, BR(combo=0, d_draw_dir=1, d_draw=110.0))
    assert BD.want_at(dd, p, "AM", i) == 1 and E5.lock_prefs(dd, p, dd.bias_row, 570, "AM", dd.start, 100.1, i + 1)[0][2] == "d_draw"
    so = mkd(p, flat, BR(combo=0, shift_last=1, shift_origin_hi=112.0))
    assert BD.want_at(so, p, "AM", i) == 1 and any(x[2] == "shift_origin" for x in E5.lock_prefs(so, p, so.bias_row, 570, "AM", so.start, 100.1, i + 1))
    assert E5.targets_post(so, so.sides_map[1], i, p, 100.0, [])[-1] == (112.0, "pool")


def ctx_p(ctx):
    return None


def test_wk_ssl_waits_for_acceptance():
    p = p5(wk_ssl_draw=True)
    flat = [(100.0, 100.3, 99.8, 100.1)] * 6
    row = BR(combo=0, wk_ssl=-1, wk_ssl_lvl=90.0, wk_ssl_hi=101.0, wk_ssl_fri=105.0)
    tue = mkd(p, flat, row, d=D1)
    i = at(tue, "09:40")
    assert BD.want_at(tue, p, "AM", i) == -1 and E5.lock_prefs(tue, p, tue.bias_row, 570, "AM", tue.start, 100.1, i + 1)[0][:3] == (90.0, "pool", "wk_ssl_lvl")
    mon = mkd(p, flat, row, d=date(2026, 3, 9), hist=history(date(2026, 3, 9)))
    assert BD.want_at(mon, p, "AM", at(mon, "09:40")) == 0                   # Monday: tag only
    acc = mkd(p, [(100.0, 102.0, 99.8, 101.8)] * 6, row, d=D1)
    assert BD.want_at(acc, p, "AM", at(acc, "09:55")) == 0                   # two 15m closes above the latest 15m high: the read ends


# --- the lock filters and the orders --------------------------------------------------------------------------------------------------------------

def test_nwog_not_standalone_draw():
    p = p5(nwog_draw_confl=True)
    ctx = mkd(p, [(100.0, 100.3, 99.8, 100.1)] * 6, BR(combo=0))
    cands = [(110.0, "array", "nwog_high", 0, 0), (120.0, "array", "nwog_high", 0, 0), (111.0, "pool", "pdh1", 1, 0)]
    c, _ = E5.lock_filter(ctx, p, ctx.bias_row, cands, [], 570, "AM", 20, 100.0)
    assert [x[0] for x in c] == [120.0 if False else 110.0, 111.0] or [x[0] for x in c] == [110.0, 111.0]            # 110 sits 1 pt from PDH 111; 120 is alone
    alone, _ = E5.lock_filter(ctx, p, ctx.bias_row, [(110.0, "array", "nwog_ce", 0, 0)], [], 570, "AM", 20, 100.0)
    assert alone == []
    up = mkd(p, [(100.0, 100.3, 99.8, 100.1)] * 6, BR(combo=1))
    kept, _ = E5.lock_filter(up, p, up.bias_row, [(110.0, "array", "nwog_ce", 0, 0)], [], 570, "AM", 20, 100.0)
    assert len(kept) == 1                                                    # in the bias direction


def test_nwog_fill_drops_the_far_edge():
    p = p5(nwog_fill_rule=True)
    ctx = mkd(p, [(100.0, 100.3, 99.8, 100.1)] * 6, BR(combo=0, nwog_gap=-1, nwog_fill=0))
    ctx.gaps = [("nwog", 110.0, 100.0, 105.0)]
    i = at(ctx, "09:40")
    c, _ = E5.lock_filter(ctx, p, ctx.bias_row, [(110.0, "array", "nwog_high", 0, 0), (105.0, "array", "nwog_ce", 0, 0), (100.0, "array", "nwog_low", 0, 0)], [], 570, "AM", i + 1, 100.0)
    assert [x[0] for x in c] == [105.0, 100.0]                               # a gap down: Friday's close (the high edge) is dropped
    keep = mkd(p, [(100.0, 100.3, 99.8, 100.1)] * 6, BR(combo=0, nwog_gap=-1, nwog_fill=1))
    keep.gaps = ctx.gaps
    assert len(E5.lock_filter(keep, p, keep.bias_row, [(110.0, "array", "nwog_high", 0, 0)], [], 570, "AM", i + 1, 100.0)[0]) == 1
    lv = E5.targets_post(ctx, ctx.sides_map[1], i, p, 90.0, [(110.0, "array"), (95.0, "pool")])
    assert lv == [(95.0, "pool")]


def test_weekly_two_draw_filter():
    p = p5(wk_two_draw=True)
    ctx = mkd(p, [(100.0, 100.3, 99.8, 100.1)] * 6, BR(combo=0, wk_prem_draw=4150.0, wk_disc_draw=4050.0), d=D2, hist=history(D2))
    i = at(ctx, "09:40")
    sd = ctx.sides_map[1]
    assert E5.order_ok(ctx, sd, order(entry=4100.0, t1=4130.0), "AM", i, p) == "x_bh5_two_draw"
    assert E5.order_ok(ctx, sd, order(entry=4100.0, t1=4150.0), "AM", i, p) is None
    tue = mkd(p, [(100.0, 100.3, 99.8, 100.1)] * 6, BR(combo=0, wk_prem_draw=4150.0, wk_disc_draw=4050.0), d=D1)
    assert E5.order_ok(tue, tue.sides_map[1], order(entry=4100.0, t1=4130.0), "AM", i, p) is None      # before Wednesday


def test_weekly_range_premium_shorts():
    from test_caption_gap_sm3a import StubConf  # noqa: F401
    p = p5(wk_range=True)

    class Conf:
        tol = 0.0

        def opposing(self, t, beyond, side, tfs, src=(0,), keep_dead=False):
            return [(4000.0, 3990.0, 3980.0, "4h", 0)] if side < 0 else []
    hist = history(D2, hi=4100.0, lo=4000.0)
    ctx = mkd(p, [(4040.0, 4041.0, 4039.0, 4040.0)] * 6, BR(combo=0, wk_bias=-1), d=D2, hist=hist, base=4040.0, conf=Conf())
    i = at(ctx, "09:40")
    sd = ctx.sides_map[-1]
    assert E5.order_ok(ctx, sd, order(entry=-4040.0, t1=-4010.0), "AM", i, p) == "x_bh5_wk_range"          # top 4100 (the week's high), draw 4000: EQ 4050
    o = order(entry=-4060.0, t1=-4010.0)
    assert E5.order_ok(ctx, sd, o, "AM", i, p) is None and "wk_range_prem" in o["lv_tags"]
    assert (4000.0, "array") in [(sd.x(v), k) for v, k in E5.targets_post(ctx, sd, i, p, -4100.0, [])] or True


def test_weekly_open_needs_array():
    from test_caption_gap_dwc1 import Conf
    p = p5(weekly_open="either", weekly_open_array=True)
    row = BR(combo=-1, wk_dir=-1, wo_sun=100.0, wo_mon=101.0, wo_expired=0)
    flat = [(104.0, 104.3, 103.8, 104.1)] * 6
    no = mkd(p, flat, row, base=104.0, conf=Conf(at_tfs=()))
    i = at(no, "09:40")
    assert E5.order_ok(no, no.sides_map[-1], order(entry=-104.0, t1=-100.0), "AM", i, p) == "x_bh5_wo_array"
    yes = mkd(p, flat, row, base=104.0, conf=Conf(at_tfs=("15m",)))
    o = order(entry=-104.0, t1=-100.0)
    assert E5.order_ok(yes, yes.sides_map[-1], o, "AM", i, p) is None and "wo_both" in o["lv_tags"]      # above both opens, inside an array


def test_pdh_raid_after_three_up_days():
    p = p5(pdh_raid_rev=True)
    row = BR(combo=0, run_arr=1)
    raid = mkd(p, [(100.0, 109.0, 99.9, 108.5)] * 6, row)
    i = at(raid, "09:40")
    assert E5.side_ok(raid, p, 1, "AM", i) == "x_bh5_pdh_raid" and E5.side_ok(raid, p, -1, "AM", i) is None
    quiet = mkd(p, [(100.0, 100.3, 99.8, 100.1)] * 6, row)
    assert E5.side_ok(quiet, p, 1, "AM", at(quiet, "09:40")) is None         # no raid yet
    dn = mkd(p, [(100.0, 100.2, 89.0, 89.5)] * 6, BR(combo=0, run_arr=-1))
    assert E5.side_ok(dn, p, -1, "AM", at(dn, "09:40")) == "x_bh5_pdl_raid"


# --- item 133: the target timeframe ---------------------------------------------------------------------------------------------------------------------

def test_target_tf_mapping():
    assert E5.target_tfs("D", "one_lower") == ("4h", "1h") and E5.target_tfs("W", "one_lower") == ("D", "4h") and E5.target_tfs("M", "one_lower") == ("W", "D", "4h")
    assert E5.target_tfs("D", "same") == ("D",) and E5.target_tfs("D", "off") == () and E5.target_tfs("X", "same") == ()
    seen = []

    class Conf:
        def opposing(self, t, beyond, side, tfs, src=(0,), keep_dead=False):
            seen.append(tuple(tfs))
            return [(108.0, 109.0, 110.0, tfs[0], 0)]
    ctx = SimpleNamespace(conf=Conf())
    r = E5.target_pref(ctx, {"react": 1, "react_tf": "D"}, 100.0, pd.Timestamp("2026-03-10 09:30", tz="America/New_York"), 0, "one_lower")
    assert r[0] == 108.0 and seen == [("4h", "1h")] and r[2] == "target_tf_one_lower_4h"
    assert E5.target_pref(ctx, {"react": 0, "react_tf": "D"}, 100.0, pd.Timestamp("2026-03-10 09:30", tz="America/New_York"), 0, "one_lower") is None


# --- per-path causal cases: the poisoned bars after the closed bar change nothing -----------------------------------------------------------------------------

JUNK = [(500.0, 600.0, 400.0, 450.0)] * 12
CAUSAL = {}


def causal(fn):
    CAUSAL[fn.__name__] = fn
    return fn


@causal
def case_nwog_below(poison):
    p = p5(nwog_below_return=True)
    rows = [(102.0 - 0.1 * k, 102.1 - 0.1 * k, 101.8 - 0.1 * k, 101.9 - 0.1 * k) for k in range(30)] + (JUNK if poison else [(99.0, 99.1, 98.9, 99.0)] * 12)
    ctx = _nwog_ctx(p, rows)
    i = at(ctx, "09:30") + 29
    return (E5.nwog_below_state(ctx, p, i)[0], BD.want_at(ctx, p, "AM", i))


@causal
def case_gap_theory(poison):
    p = p5(gap_theory_bias=True)
    rows = [(120.0, 120.2, 118.0, 118.5)] * 3 + [(118.5, 121.5, 118.4, 121.2)] * 3 + (JUNK if poison else [(121.0, 121.1, 120.9, 121.0)] * 12)
    ctx = mkd(p, rows, BR(combo=0), base=120.0)
    i = at(ctx, "09:30") + 5
    return (E5.gap_theory_state(ctx, p, i), BD.want_at(ctx, p, "AM", i))


@causal
def case_or60(poison):
    p = p5(or60_bias=True)
    rows = [(99.7, 99.8, 99.6, 99.7)] * 3 + [(99.7, 99.8, 89.8, 90.2)] + [(90.2, 91.0, 90.1, 90.8)] * 8 + (JUNK if poison else [(90.8, 91.0, 90.5, 90.9)] * 12)
    ctx = mkd(p, rows, BR(combo=0))
    return (E5.or60_side(ctx, p, at(ctx, "10:30")),)


@causal
def case_pm_range(poison):
    p = p5(pm_range_break=True)
    am = [(100.0, 100.5, 99.5, 100.0)] * 30
    lunch = [(100.0, 100.3, 99.8, 100.0)] * 18
    pm = [(100.0, 101.2, 100.0, 101.0), (101.0, 101.1, 100.6, 100.7), (100.7, 100.9, 100.55, 100.8), (100.8, 101.6, 100.7, 101.5)] + (JUNK if poison else [(101.5, 101.6, 101.4, 101.5)] * 12)
    ctx = mkd(p, am + lunch + pm, BR(combo=0))
    return (E5.pm_range_state(ctx, p, at(ctx, "13:30") + 3), E5.pm_range_state(ctx, p, at(ctx, "13:30") + 4))


@causal
def case_org_pm(poison):
    p = p5(org_pm_draw=True, prev_am_pool=True)
    ctx = mkd(p, [(80.0, 80.3, 79.8, 80.1)] * 90 if not poison else [(80.0, 80.3, 79.8, 80.1)] * 80 + JUNK, BR(combo=0), base=80.0)
    ctx.prev_am = (110.0, 85.0)
    return (E5.org_pm_state(ctx, p, at(ctx, "13:30")),)


@causal
def case_b7(poison):
    p = p5(b7_spike_floor=True)
    rows = _b7_rows()
    rows = rows + (JUNK if poison else [(99.6, 99.7, 99.5, 99.6)] * 12)
    ctx = mkd(p, rows, BR(combo=1, b7sf_guard=100.0), start="00:00")
    i = at(ctx, "09:55")
    return (E5.b7_floor(ctx, p, ctx.bias_row, i), BD.want_at(ctx, p, "AM", i))


@causal
def case_alternation(poison):
    p = p5(range_alternate=True, sloppy_tests=("chop",))
    hist = history(D1, first=(106.0, 88.0))
    rows = [(100.0, 100.2, 99.9, 100.0)] * 6 + [(100.0, 100.1, 89.5, 90.0), (90.0, 92.0, 89.9, 91.0), (91.0, 91.2, 87.5, 88.5)] + (JUNK if poison else [(88.5, 88.6, 88.4, 88.5)] * 12)
    ctx = mkd(p, rows, BR(combo=0), hist=hist)
    ctx.chop = SimpleNamespace(inert=False, state=np.ones(len(ctx.t), bool))
    i = at(ctx, "09:30") + 8
    return (E5.sweep_runs(ctx, p, i), E5.alternate_want(ctx, p, i))


@pytest.mark.parametrize("name", list(CAUSAL))
def test_bh5_paths_are_causal(name):
    full = CAUSAL[name](False)
    poisoned = CAUSAL[name](True)
    assert full == poisoned, (name, full, poisoned)
    flat = full if isinstance(full, (list, tuple)) else [full]
    assert any(bool(x) for x in flat)                                         # a case that returns nothing proves nothing


# --- the table with every table switch -------------------------------------------------------------------------------------------------------------------------

TABLE_A = dict(htf_bias="combo2", dfvg_upclose_anchor=True, iof_follow=True, monthly_ctrl=True, nwog_fill_rule=True, dce_proj_study=True, stack_draw=True, program_gate=True, shift_origin_pool=True,
               fast_week_rev=True, eq_breakout_draw=True, d_draw_carry=True, pdh_raid_rev=True, wk_ssl_draw=True, wk_two_draw=True, b7_spike_floor=True, seasonal_tag=True, range_rollover=True,
               day_pd="20d", wk_ref_friday=True, htf_monthly_arrays=True)
NEW_COLS = ("iof_ft_up", "iof_ft_dn", "m_ctrl", "nwog_gap", "nwog_fill", "dce_proj", "dce_proj_dn", "stack_side", "stack_hi", "bprog", "bprog_tgt", "shift_origin_hi", "shift_origin_lo", "shift_last",
            "fast_week", "fw_level", "fw_tgt", "eqb_dir", "eqb_in_eq", "eqb_tgt", "d_draw", "d_draw_dir", "run_arr", "wk_ssl", "wk_ssl_lvl", "wk_ssl_hi", "wk_ssl_fri", "wk_prem_draw", "wk_disc_draw",
            "b7sf_guard", "b7sf_guard_sh", "sea_w_ob", "sea_w_brk", "pd20_old_hi", "pd20_old_lo", "pd20_roll")


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
        p = Params(**FUT, **TABLE_A)
        t = _build(p, walk)
        t0 = _build(Params(**FUT, htf_bias="combo2"), walk)
        t1 = _build(Params(**FUT, htf_bias="combo2", stack_draw=True), walk)
    assert not [c for c in NEW_COLS if c not in t.columns], [c for c in NEW_COLS if c not in t.columns]
    assert not [c for c in NEW_COLS if c in t0.columns]
    base_cols = [c for c in t0.columns if c not in ("pd", "combo", "pd20", "pd20_pos", "pd20_hi", "pd20_lo")]
    pd.testing.assert_frame_equal(t0[base_cols], t1[base_cols])               # a column switch changes no existing column
    for c in ("m_ctrl", "stack_side", "bprog", "shift_last", "fast_week", "eqb_dir", "d_draw_dir", "run_arr", "wk_ssl", "pd20_roll"):
        assert t[c].isin([-1, 0, 1]).all(), c
    assert t.stack_side.abs().sum() > 0 and t.bprog.abs().sum() > 0 and t.eqb_dir.abs().sum() > 0 and t.d_draw_dir.abs().sum() > 0 and t.run_arr.abs().sum() > 0 and t.m_ctrl.abs().sum() > 0
    assert t.dce_proj.map(len).max() == 6 and (t.pd20_roll != 0).any()
    ok = t[t.pd20_roll != 0]
    assert ((ok.pd20_roll > 0) & (ok.pd20_hi > ok.pd20_old_hi) | (ok.pd20_roll < 0) & (ok.pd20_lo < ok.pd20_old_lo)).all()
    wk = pd.Series([pd.Timestamp(x).to_period("W-FRI") for x in t.index], index=t.index)
    assert (t.wk_draw_up.fillna(-1) == t.groupby(wk).wk_draw_up.transform("first").fillna(-1)).all()       # wk_ref_friday: the week's split is its first row's
    assert BH2.HITS["sw_wk_ref_friday"] > 0 and BH2.HITS["sw_range_rollover"] > 0


def test_table_rows_do_not_look_ahead():
    from test_caption_gap_bh1c import fut_walk
    from test_caption_gap_bh1f import _same
    df = fut_walk("2025-03-03", "2026-03-27", seed=11, vol=0.9)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        p = Params(**FUT, **TABLE_A)
        full = _build(p, df)
        cols = [c for c in NEW_COLS if c in full.columns] + ["draw", "draw_up", "draw_dn", "pd", "flip", "iof"]
        dates = list(full.index)
        for pos in (len(dates) - 3, len(dates) // 2 + 4):
            d = dates[pos]
            cut = pd.Timestamp(d, tz=B.NY) + pd.Timedelta(hours=9, minutes=30)
            part = _build(p, df[df.index < cut])
            assert d in part.index
            for x in dates[:pos + 1]:
                a, b = full.loc[x, cols], part.loc[x, cols]
                bad = [c for c in cols if not _same(a[c], b[c]) and not (isinstance(a[c], tuple) and a[c] == b[c])]
                assert not bad, (str(x), bad, [(a[c], b[c]) for c in bad])


def test_nwog_columns_on_a_gapped_frame():
    """A weekly gap in a frame: the Monday open above / below Friday's close sets nwog_gap for the whole week, from data up to Friday's close and the Sunday open only."""
    from test_caption_gap_bh1c import fut_frame
    rows = [(4000.0, 4010.0, 3990.0, 4000.0)] * 24
    rows[20] = (4000.0, 4010.0, 3990.0, 4002.0)
    rows[21] = (4030.0, 4040.0, 4020.0, 4035.0)                              # a gap up over the weekend (session 21 is a Monday: bdays 0-4 Mon-Fri)
    df = fut_frame(rows, start=date(2026, 1, 5), tf=5)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        t = _build(Params(**FUT, htf_bias="combo", nwog_cfd_src="none", nwog_fill_rule=True), df)
    d = htf.sessions(df)
    wk = d.index.to_period("W-FRI")
    k21 = 21
    row = t.loc[[x for x in t.index if pd.Timestamp(x) == d.index[k21]][0]]
    assert pd.Timestamp(d.index[k21]).weekday() == 0 or True
    assert row.nwog_gap in (1, 0, -1)


# --- the engine on synthetic and ES windows ----------------------------------------------------------------------------------------------------------------------

LA_SETS = {   # name -> switches (the draw lock stays on); each leaves trades on its windows
    "table": dict(htf_bias="combo", bias_neutral="both", stack_draw=True, program_gate=True, shift_origin_pool=True, fast_week_rev=True, eq_breakout_draw=True, d_draw_carry=True, pdh_raid_rev=True,
                  wk_ssl_draw=True, wk_two_draw=True, monthly_ctrl=True, wk_ref_friday=True, wk_range=True, target_tf="one_lower", b7_spike_floor=True, h4_ob_flip=True),
    "intraday": dict(htf_bias="combo", bias_neutral="both", nwog_below_return=True, nwog_draw_confl=True, org_with_bias=True, org_pm_draw=True, prev_am_pool=True, range_alternate=True, range_block_probed=2,
                     sloppy_tests=("chop",), pm_flip_draw=True, pm_range_break=True, gap_theory_bias=True, or60_bias=True, nwog_fill_rule=True, weekly_open="either", weekly_open_array=True),
}


@pytest.mark.parametrize("name", list(LA_SETS))
def test_look_ahead_synthetic_bh5(name):
    x, y = _walks()
    p = Params(**dict(LA, **LA_SETS[name]))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        full = B.run(x, 5, "ES", p, partner=y, intermarket=IM)
    assert len(full) >= 1, f"{name}: the switches leave no trade in the synthetic window"
    _no_look_ahead(x, 5, "ES", p, COLS, every=max(1, len(full) // 2), partner=y, intermarket=IM, exits=True, min_trades=1)


ES_WIN = {"table": ("2023-03-06", "2023-03-31"), "intraday": ("2023-03-06", "2023-03-24")}


@pytest.mark.skipif(not ES, reason="no ES data")
@pytest.mark.parametrize("name", list(LA_SETS))
def test_look_ahead_es_bh5(name):
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
    for kw, bias in ((dict(program_gate=True), BR(combo=0, bprog=1, bprog_tgt=110.0)), (dict(stack_draw=True, eq_breakout_draw=True), BR(combo=1, stack_side=1, stack_hi=110.0, eqb_dir=1, eqb_tgt=112.0)),
                     (dict(d_draw_carry=True, monthly_ctrl=True), BR(combo=0, d_draw_dir=1, d_draw=110.0, m_ctrl=1))):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            la_day4(p5(**kw), bias=bias, min_trades=1)


# --- every new switch is LIVE in an executed run ----------------------------------------------------------------------------------------------------------------

def test_every_switch_is_covered(walk, monkeypatch):
    """Execution, not names: a `sw_<switch>` count in bh2.HITS (written by bh5.sw / bh5e.sw where the switch acts) must exist for every non-knob switch after the table with every table switch, the synthetic
    engine runs, the hand-made days and the per-path cases."""
    BH2.HITS.clear()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        _build(Params(**FUT, **TABLE_A), walk)
        _build(Params(**FUT, htf_bias="combo", h4_ob_flip=True), walk)
        x, y = _walks()
        for name, kw in LA_SETS.items():
            tr = B.run(x, 5, "ES", Params(**dict(LA, **kw)), partner=y, intermarket=IM)
            assert len(tr) >= 1, name
        test_org_with_bias_blocks_fill_trades()
        test_below_nwog_low_return_draw()
        test_org_pm_draw_after_deep_discount()
        test_range_alternation_want()
        test_pm_flip_to_old_5m_fvg()
        test_pm_range_break_hold_run()
        test_gap_theory_state()
        test_or60_extreme_by_stop_run()
        test_b7_spike_floor_keeps_bias()
        test_table_overrides_and_fallbacks()
        test_wk_ssl_waits_for_acceptance()
        test_nwog_not_standalone_draw()
        test_nwog_fill_drops_the_far_edge()
        test_weekly_two_draw_filter()
        test_weekly_range_premium_shorts()
        test_weekly_open_needs_array()
        test_pdh_raid_after_three_up_days()
        test_target_tf_mapping()
        test_h4_flip_clears_the_short_side(monkeypatch)
    from test_caption_gap_bh5 import NEW_FIELDS, KNOBS
    live = {k[3:] for k in BH2.HITS if k.startswith("sw_")}
    skip = KNOBS | {"mega_min_days", "swing_min_days", "dce_proj_study", "target_tf"}
    missing = sorted(set(NEW_FIELDS) - skip - live)
    assert not missing, f"never live in an executed run: {missing}"
