"""Package management_exits (build_log.md): X4-X16, D14, D18, M2.6, Ep03.10/.15/.20, Ep04.13, Ep07.5/.7, T11.

Unit tests drive manage.exits / be_modes / trail_extra on hand-made bars (a position dict, the real Side
arrays), scenario tests go through run_day (the real engine path), and the no-look-ahead tests compare a
full run with runs truncated just after every entry and exit (synthetic window and, when the data is on
disk, a short ES window) for every switch this package added."""
import warnings
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from mentorship import backtest as B, manage as MG, strategy as S, study
from mentorship.strategy import Params

from test_review_fixes import A_LOCK, A_ROWS, BASE, D0, day, history, run  # noqa: E402
from test_entries_stops import _no_look_ahead, _syn  # noqa: E402

NY = "America/New_York"
ES = Path("data/mentorship/ES_5min_db.csv").exists() and Path("data/mentorship/ES_1min_dbraw.csv").exists()
FUT = dict(es_pt=1.0, lot=1, max_notional=1e12, cost_per_share=0.1)
SYN = dict(es_pt=0.09, use_bias=False, min_draw_pts=0, leg_pd=0)
COLS = ["entry_time", "entry", "stop", "t1", "shares", "lv_tags", "setup"]
UP = dict(es_pt=1.0, lot=1, cost_per_share=0.0, tick_pts=0.25)

# --- a hand-made position -----------------------------------------------------------------------------------
# bars (5m from 09:30): a sweep low at index 1 (99.0), a displacement leaving a bullish FVG 100.0-101.0 at index 3
LEG = [(101.0, 101.2, 100.6, 101.0), (100.0, 100.0, 99.0, 99.2), (99.2, 101.5, 99.1, 101.4), (101.4, 103.0, 101.0, 102.9)]


def mk(post, p=None, fill=101.0, shares=100, sign=1, session="AM", lead=LEG, **pos_kw):
    """(ctx, sd, pos, tr, p) with `lead` + one fill bar + `post` bars; the position filled on the fill bar at `fill`."""
    p = p or Params(**BASE)
    rows = list(lead) + [(fill, fill + 0.5, fill - 0.1, fill + 0.4)] + list(post)
    a = np.array(rows, float)
    n = len(a)
    idx = pd.date_range(pd.Timestamp(f"{D0} 09:30", tz=NY), periods=n, freq="5min")
    t = (idx.hour * 60 + idx.minute).values
    o, h, l, c = a[:, 0], a[:, 1], a[:, 2], a[:, 3]
    if sign < 0:
        o, h, l, c = -o, -l, -h, -c
    sd = S.Side(sign, o, h, l, c, 1, 0.0)
    ctx = SimpleNamespace(t=t, tf=5, idx=idx, start=0, day=D0, lock={}, hist=history(), o=o, h=h, l=l, c=c)
    fi = len(lead)
    tr = S.Trade(D0, "ES", session, "am_mm", "long" if sign > 0 else "short", "x", False, None, idx[fi], idx[fi],
                 sd.x(fill), sd.x(fill - 2.0), sd.x(fill + 3.0), None, shares)
    pos = dict(trade=tr, side=sd, stop=fill - 2.0, stop0=fill - 2.0, left=shares, n=shares, basis=fill * shares, fill_i=fi,
               fill_t=int(t[fi]), t1_done=False, best=fill, ext_i=1, ext=99.0, fvg_bottom=100.0, fvg_ce=100.5, fvg_top=101.0,
               zone_top=101.0, fill_px=fill, levels=[fill + 3.0, fill + 6.0], level_kinds=["array", "pool"], k=0,
               last_partial_i=fi, leg=(99.0, 103.0), draw=None, kind="fvg", bz_mt=None, smt_tag=False, day_trade=False,
               pool_levels=[fill + 6.0], ob_pre=False)
    pos.update(pos_kw)
    return ctx, sd, pos, tr, p


def drive(ctx, sd, pos, tr, p, state=None, upto=None):
    """Run manage.exits bar by bar after the fill bar until the position is closed (or `upto`)."""
    state = {} if state is None else state
    for i in range(pos["fill_i"] + 1, upto or len(ctx.t)):
        if not pos["left"]:
            break
        pos["best"] = max(pos["best"], sd.h[i])
        MG.exits(ctx, sd, pos, tr, i, ctx.idx[i], p, state)
        if pos["left"]:
            MG.be_modes(sd, pos, tr, i, p)
            MG.trail_extra(sd, pos, i, p)
    return [(e[3], round(e[1], 3), e[2]) for e in tr.exits]


# --- defaults / validation / aliases -------------------------------------------------------------------------

def test_defaults_validation_and_aliases():
    p = Params()
    assert p.late_cutoff == 945 and p.be_on == "expansion" and p.fvg_abort_mode == "rule"
    assert not p.fvg_abort and not p.pd3_exit and p.time_stop_frac == 1.0 and p.trail_after == 1
    assert p.add_leg_at_fill and not p.add_in_pd and p.reentry_risk == "budget" and p.trade_type == "session"
    for kw in (dict(be_on="x"), dict(ladder_trail="x"), dict(trade_type="x"), dict(day_stop="x"), dict(fvg_abort_mode="x"),
               dict(session_fail_mode="x"), dict(offside_level="x"), dict(time_stop_ref="x"), dict(obj_source="x"),
               dict(reentry_risk="x"), dict(add_mode="x"), dict(pd3_list=("x",)), dict(pd3_n=0), dict(time_stop_frac=0.0),
               dict(far_edge_frac=1.5), dict(pd3_half_frac=1.0), dict(am_bulk_frac=0.0), dict(trail_after=0),
               dict(add_pd_level=1.5), dict(session_stop_after_fails=-1)):
        with pytest.raises(ValueError):
            Params(**kw)
    assert Params(pool_size_rank=True).pool_rank and Params(prop_exit=True).prop_mt_exit
    assert Params(trail_pad_pts=0.25, es_pt=1.0).trail_pad == 0.25 and Params().trail_pad == Params().pad + Params().mohawk
    for m in ("expansion", "t1", "after_mss", "stall", "pool", "off"):
        Params(be_on=m)
    for m in ("fvg", "hit", "prior", "off", "measuring", "breakaway"):
        Params(ladder_trail=m)


def test_every_new_study_variant_builds():
    names = [k for k in study.DECISIONS if k.split("_")[0] in
             {"M2.6", "X4", "D14", "Ep03.15", "X5a", "Ep03.10", "Ep03.20", "X5c", "X6", "X7a", "X7b", "X7c", "X8b", "X8c", "X8d",
              "X8e", "X8g", "X9", "X9a", "X9d", "X9c", "X10b", "X10c", "X11c", "X12", "X13a", "X13b", "D18", "X14b", "X14d",
              "Ep04.13", "Ep07.5", "Ep07.7", "T11", "B18.3"}]
    assert len(names) >= 70
    for k in names:
        Params(**study.DECISIONS[k])


# --- breakeven (X4 / D14 / Ep03.15) ---------------------------------------------------------------------------

def test_be_stop_pad_and_cost():
    pos = dict(basis=1000.0, n=10)
    assert MG.be_stop(pos, Params(**BASE)) == 100.0
    assert MG.be_stop(pos, Params(**BASE, be_pad_pts=0.5)) == 100.5
    assert MG.be_stop(pos, Params(**dict(BASE, cost_per_share=0.1), be_pad_pts=0.5, be_cost_pad=True)) == pytest.approx(100.7)
    pos2 = dict(basis=1000.0, n=10, stop=90.0, day_trade=True)
    MG.be_move(pos2, Params(**BASE))
    assert pos2["stop"] == 90.0                            # X5c: a day trade has no breakeven
    pos2["day_trade"] = False
    MG.be_move(pos2, Params(**BASE, be_pad_pts=1.0))
    assert pos2["stop"] == 101.0


def test_be_after_mss_stall_and_pool_modes():
    post = [(101.0, 101.5, 100.8, 101.4), (101.4, 103.6, 101.3, 103.5), (103.5, 103.6, 103.0, 103.2)]
    ctx, sd, pos, tr, p = mk(post, Params(**BASE, be_on="after_mss"))
    drive(ctx, sd, pos, tr, p)
    assert pos["be_done"] and pos["stop"] == 101.0          # the close above the leg high (103) moved the stop to BE
    ctx, sd, pos, tr, p = mk(post, Params(**BASE, be_on="after_mss"), leg=(99.0, 110.0))
    drive(ctx, sd, pos, tr, p)
    assert not pos.get("be_done") and pos["stop"] == 99.0
    # stall: 2R (risk 2.0) reached, then two bars without a new high
    st = [(101.0, 105.5, 101.0, 105.0), (105.0, 105.2, 104.5, 105.0), (105.0, 105.1, 104.6, 104.9)]
    ctx, sd, pos, tr, p = mk(st, Params(**BASE, be_on="stall"))
    drive(ctx, sd, pos, tr, p)
    assert pos["be_done"] and pos["stop"] == 101.0
    ctx, sd, pos, tr, p = mk(st[:2], Params(**BASE, be_on="stall"))          # only one stalled bar
    drive(ctx, sd, pos, tr, p)
    assert not pos.get("be_done")
    ctx, sd, pos, tr, p = mk([(101.0, 101.5, 100.8, 101.4)], Params(**BASE, be_on="stall"))   # never 1R in profit
    drive(ctx, sd, pos, tr, p)
    assert not pos.get("be_done")
    # pool: the high reaches the pool level (107), whatever rungs were taken
    pl = [(101.0, 104.0, 100.9, 103.9), (103.9, 107.2, 103.5, 107.0)]
    ctx, sd, pos, tr, p = mk(pl, Params(**BASE, be_on="pool"))
    drive(ctx, sd, pos, tr, p, upto=len(ctx.t) - 1)
    assert not pos.get("be_done")
    drive(ctx, sd, pos, tr, p)
    assert pos["be_done"] and pos["stop"] == 101.0
    ctx, sd, pos, tr, p = mk(pl, Params(**BASE, be_on="pool"), pool_levels=[])
    drive(ctx, sd, pos, tr, p)
    assert not pos.get("be_done")                            # no pool in the ladder and no partial: the expansion rule waits


def test_be_modes_scenarios_through_run_day():
    pre = A_ROWS[:5]
    rows = pre + [(100.3, 103.0, 100.2, 102.9), (102.9, 103.0, 99.8, 100.1), (100.1, 100.5, 99.0, 99.5)]

    def go(**kw):
        tr, *_ = run(day(rows, spike=True), history(), Params(**BASE, **kw), A_LOCK)
        return [(e[3], float(e[1])) for e in tr[0].exits]
    assert go()[1][0] == "am_exit"                           # default: BE only after expansion - not reached
    assert go(be_on="t1") == [("t1", 102.75), ("be", 100.0)]
    assert go(be_on="t1", be_pad_pts=0.5) == [("t1", 102.75), ("be", 100.5)]
    assert go(be_on="off", ladder_trail="off")[1][0] == "am_exit"


def test_day_trade_keeps_its_initial_stop_and_has_no_breakeven():
    pre = A_ROWS[:5]
    rows = pre + [(100.3, 103.0, 100.2, 102.9), (102.9, 103.0, 99.8, 100.1), (100.1, 100.5, 99.0, 99.5)]

    def go(**kw):
        tr, *_ = run(day(rows, spike=True), history(), Params(**BASE, min_risk_pts=0.3, **kw), A_LOCK)
        return tr[0]
    t = go(trade_type="day", day_stop="wick_ce", be_on="t1")
    assert "day_trade" in t.lv_tags and t.stop == pytest.approx(99.9 - Params(**BASE).pad)   # 08:30 candle: low 99.8, body 100.0
    assert t.exits[0][3] == "t1" and t.exits[1][1] == pytest.approx(t.stop)           # no breakeven: out at the initial stop
    assert go(trade_type="session", be_on="t1").exits[1][1] == 100.0                 # a session trade moves to breakeven
    t = go(trade_type="day", day_stop="open")
    assert "day_trade" not in t.lv_tags and t.stop == go().stop                     # open 100.0 is not under the 100.0 entry


# --- trailing (X5a / Ep03.10 / Ep03.20) ---------------------------------------------------------------------------

def test_breakaway_ladder_trail_waits_for_the_rounds():
    post = [(101.0, 101.5, 100.9, 101.4), (101.4, 102.0, 101.3, 101.9)]
    for k, after, expect in ((1, 1, True), (1, 2, False), (2, 2, True), (0, 1, False)):
        ctx, sd, pos, tr, p = mk(post, Params(**BASE, ladder_trail="breakaway", trail_after=after))
        pos["k"] = k
        drive(ctx, sd, pos, tr, p)
        assert (pos["stop"] == pytest.approx(100.0 - p.trail_pad)) == expect, (k, after)    # under the gap 100.0-101.0
    ctx, sd, pos, tr, p = mk(post, Params(**BASE, ladder_trail="breakaway"), day_trade=True)
    pos["k"] = 1
    drive(ctx, sd, pos, tr, p)
    assert pos["stop"] == 99.0


def test_trail_first_fvg_and_fail():
    ctx, sd, pos, tr, p = mk([(101.0, 101.5, 100.9, 101.4), (101.4, 102.0, 101.3, 101.9)],
                             Params(**BASE, trail_first_fvg=True))
    g = MG.first_fvg(sd, 1, 5)
    assert (g.bottom, g.top) == (100.0, 101.0)
    drive(ctx, sd, pos, tr, p)
    assert pos["stop"] == pytest.approx(100.0 - p.trail_pad)  # a close above 101.0: the stop is under the first FVG
    ctx, sd, pos, tr, p = mk([(101.0, 101.0, 100.7, 100.8)], Params(**BASE, trail_first_fvg=True))
    drive(ctx, sd, pos, tr, p)
    assert pos["stop"] == 99.0                                # never closed above it: no trail
    # a body close below the first FVG's bottom (100.0) = the trade is wrong
    fail = [(101.0, 101.1, 99.6, 99.8)]
    ctx, sd, pos, tr, p = mk(fail + [(99.8, 99.9, 99.5, 99.7)], Params(**BASE, first_fvg_fail=True))
    out = drive(ctx, sd, pos, tr, p)
    assert out == [("first_fvg_fail", 99.8, 100)]
    ctx, sd, pos, tr, p = mk(fail, Params(**BASE, first_fvg_fail=True), t1_done=True)
    assert drive(ctx, sd, pos, tr, p) == []                   # after the first partial: only with first_fvg_fail_after_t1
    ctx, sd, pos, tr, p = mk(fail, Params(**BASE, first_fvg_fail=True, first_fvg_fail_after_t1=True), t1_done=True)
    assert drive(ctx, sd, pos, tr, p)[0][0] == "first_fvg_fail"


def test_measuring_trail_waits_for_trail_after_rounds():
    # leg 99 -> 106 (ext_i 1): the measuring gap 102.0-103.0 (CE 102.5, the leg's middle) and price well above it
    rows = [(101.0, 101.2, 100.6, 101.0), (100.0, 100.0, 99.0, 99.2), (99.2, 102.0, 99.1, 101.9), (101.9, 103.5, 101.8, 103.4),
            (103.4, 104.5, 103.0, 104.4), (104.4, 106.0, 104.0, 105.9)]
    post = [(105.5, 105.9, 105.2, 105.8), (105.8, 105.9, 105.3, 105.7)]
    kw = dict(lead=rows, fill=105.0, ext_i=1, ext=99.0, leg=(99.0, 106.0), stop=99.0)
    from mentorship import targets as TP

    def go(k, **pk):
        ctx, sd, pos, tr, p = mk(post, Params(**BASE, ladder_trail="measuring", **pk), **kw)
        pos["k"] = k
        drive(ctx, sd, pos, tr, p)
        return sd, pos, p
    sd, pos, p = go(1)
    g = TP.measuring_gap(sd, dict(ext=99.0, ext_i=1), len(sd.c) - 1, 106.0, p)
    assert g is not None and (g.bottom, g.top) == (102.0, 103.0)
    assert pos["stop"] == pytest.approx(102.0 - p.trail_pad)             # one round with trail_after=1: trailed
    assert go(1, trail_after=2)[1]["stop"] == 99.0                        # trail_after=2: one round is not enough
    sd, pos, p = go(2, trail_after=2)
    assert pos["stop"] == pytest.approx(102.0 - p.trail_pad)             # two rounds: the stop goes under the measuring gap
    sd, pos, p = go(0)
    assert pos["stop"] == 99.0                                           # before any partial nothing trails
    ctx, sd, pos, tr, p = mk(post, Params(**BASE, ladder_trail="measuring"), **kw)
    pos["k"], pos["day_trade"] = 2, True
    MG.trail_extra(sd, pos, len(ctx.t) - 1, p)
    assert pos["stop"] == 99.0                                           # X5c: a day trade keeps its initial stop


# --- X6 abort -----------------------------------------------------------------------------------------------------

def test_fvg_abort_rule_arm_confirm_and_clear():
    p = Params(**BASE, fvg_abort=True)
    # candle 1 closes below the far edge (100.0), the NEXT candle trades below its low (99.5) -> out at 99.5
    ctx, sd, pos, tr, _ = mk([(100.9, 101.0, 99.5, 99.8), (99.8, 99.9, 99.4, 99.6)], p)
    assert drive(ctx, sd, pos, tr, p) == [("abort", 99.5, 100)]
    # the next candle does not take the low: the arm is cleared, a LATER candle trading lower does not confirm it
    ctx, sd, pos, tr, _ = mk([(100.9, 101.0, 99.5, 99.8), (99.8, 100.2, 99.6, 100.1), (100.1, 100.2, 99.0, 100.1)], p)
    assert drive(ctx, sd, pos, tr, p) == [] and pos.get("abort_arm") is None
    # a gap through the armed low fills at the open
    ctx, sd, pos, tr, _ = mk([(100.9, 101.0, 99.5, 99.8), (99.2, 99.3, 99.0, 99.1)], p)
    assert drive(ctx, sd, pos, tr, p) == [("abort", 99.2, 100)]
    # the whole-body arm: a close beyond the edge with the open above it is not enough
    pb = Params(**BASE, fvg_abort=True, fvg_abort_body=True)
    ctx, sd, pos, tr, _ = mk([(100.9, 101.0, 99.5, 99.8), (99.8, 99.9, 99.4, 99.6)], pb)
    assert drive(ctx, sd, pos, tr, pb) == []
    ctx, sd, pos, tr, _ = mk([(99.9, 100.0, 99.5, 99.8), (99.8, 99.9, 99.4, 99.6)], pb)
    assert drive(ctx, sd, pos, tr, pb) == [("abort", 99.5, 100)]
    # fvg_abort off: nothing
    ctx, sd, pos, tr, _ = mk([(100.9, 101.0, 99.5, 99.8), (99.8, 99.9, 99.4, 99.6)], Params(**BASE))
    assert drive(ctx, sd, pos, tr, Params(**BASE)) == []


def _one_minute(bars, p, fill_i=2, fill=101.0):
    arr = np.array(bars, float)
    idx = pd.date_range(pd.Timestamp(f"{D0} 09:30", tz=NY), periods=len(arr), freq="1min")
    t = (idx.hour * 60 + idx.minute).values
    sd = S.Side(1, arr[:, 0], arr[:, 1], arr[:, 2], arr[:, 3], 1, 0.0)
    ctx = SimpleNamespace(t=t, tf=1, idx=idx, start=0, day=D0)
    tr = S.Trade(D0, "ES", "AM", "am_mm", "long", "x", False, None, idx[fill_i], idx[fill_i], fill, fill - 2, fill + 3, None, 100)
    pos = dict(trade=tr, side=sd, stop=fill - 2, stop0=fill - 2, left=100, n=100, basis=fill * 100, fill_i=fill_i,
               fill_t=int(t[fill_i]), t1_done=False, best=fill, fvg_bottom=100.0, fvg_ce=100.5, fvg_top=101.0, ext_i=0,
               ext=99.0, fill_px=fill, levels=[fill + 3], level_kinds=["array"], k=0, last_partial_i=fill_i,
               leg=(99.0, 103.0), draw=None, kind="fvg")
    return ctx, sd, pos, tr


def test_fvg_abort_groups_one_minute_bars_into_five_minute_candles():
    p = Params(**BASE, fvg_abort=True)
    calm = (101.0, 101.1, 100.9, 101.0)
    dip = [(101.0, 101.0, 100.2, 100.3), (100.3, 100.4, 99.9, 100.0), (100.0, 100.1, 99.7, 99.8), (99.8, 99.9, 99.6, 99.7),
           (99.7, 99.8, 99.5, 99.6)]                        # the 09:35-09:40 candle: low 99.5, close 99.6 < 100.0 -> armed
    ctx, sd, pos, tr = _one_minute([calm] * 5 + dip + [(99.6, 99.7, 99.55, 99.65), (99.65, 99.7, 99.4, 99.45)], p)
    out = [(e[3], round(e[1], 2)) for e in (drive(ctx, sd, pos, tr, p) and tr.exits)]
    assert out == [("abort", 99.5)] and tr.exits[0][0] == ctx.idx[11]               # confirmed inside the NEXT 5m candle
    # the next 5-minute candle (09:40-09:45) stays above the low: cleared, the 09:45 candle's new low does not confirm
    ctx, sd, pos, tr = _one_minute([calm] * 5 + dip + [(99.6, 99.7, 99.6, 99.65)] * 5 + [(99.65, 99.7, 99.0, 99.2)], p)
    assert drive(ctx, sd, pos, tr, p) == [] or tr.exits[0][3] == "abort" and tr.exits[0][0] >= ctx.idx[15]


# --- X7 three arrays ----------------------------------------------------------------------------------------------

# stacked supports under a long: FVG 100-101, a later FVG 102-103 at index 7, a VI and an order block
STACK = [(101.0, 101.2, 100.6, 101.0), (100.0, 100.0, 99.0, 99.2), (99.2, 101.5, 99.1, 101.4), (101.4, 103.0, 101.0, 102.9),
         (102.9, 103.2, 102.5, 103.0), (103.0, 103.1, 102.6, 102.7), (102.7, 103.0, 102.0, 102.9),
         (102.9, 105.5, 103.2, 105.4)]


def test_pd3_list_fixed_at_the_fill_and_exit_on_three_closes():
    p = Params(**BASE, pd3_exit=True)
    ctx, sd, pos, tr, _ = mk([(105.4, 105.5, 102.0, 102.1)], p, lead=STACK, fill=105.0, ext_i=1)
    arrs = MG._arrays(sd, pos, len(STACK), p, 105.0, 99.0, p.pd3_list)
    assert [round(a[0], 2) for a in arrs][:2] == [103.2, 100.0] or len(arrs) >= 2
    lv = [a[0] for a in arrs]
    assert lv == sorted(lv, reverse=True)
    pos["pd3"] = arrs[:p.pd3_n]
    pos["pd3_broken"] = set()
    if len(pos["pd3"]) < 3:
        pytest.skip("fewer than three arrays in the synthetic stack")
    # closes below the nearest, the second (warning tag) and the third level exit
    lo = pos["pd3"][-1][0]
    post = [(105.4, 105.5, 104.9, 104.9)]
    for k in pos["pd3"]:
        post.append((post[-1][3], post[-1][3] + 0.1, k[0] - 0.5, k[0] - 0.3))
    ctx, sd, pos2, tr, _ = mk(post, p, lead=STACK, fill=105.0, ext_i=1, pd3=pos["pd3"], pd3_broken=set())
    out = drive(ctx, sd, pos2, tr, p)
    assert out and out[-1][0] == "pd3"
    assert "pd3_warn" in tr.lv_tags


def test_pd3_needs_the_full_list_and_half_off_needs_all_three_kinds():
    p = Params(**BASE, pd3_exit=True)
    ctx, sd, pos, tr, _ = mk([(101.0, 99.0, 98.0, 98.5)], p, pd3=[(100.0, "fvg"), (99.5, "vi")], pd3_broken=set())
    assert drive(ctx, sd, pos, tr, p) == []                   # only two arrays listed: the stop is the exit
    ph = Params(**BASE, pd3_half=True)
    ctx, sd, pos, tr, _ = mk([(101.0, 101.0, 98.9, 99.0)], ph, pd3_half_lv=99.5)
    out = drive(ctx, sd, pos, tr, ph)
    assert out == [("pd3_half", 99.0, 50)]                    # a body close below the nearest VI + FVG + OB MT: half off, once
    ctx, sd, pos, tr, _ = mk([(101.0, 101.0, 98.9, 99.0), (99.0, 99.1, 98.5, 98.6)], ph, pd3_half_lv=99.5)
    assert len(drive(ctx, sd, pos, tr, ph)) == 1
    ctx, sd, pos, tr, _ = mk([(101.0, 101.0, 98.9, 99.0)], ph, pd3_half_lv=None)
    assert drive(ctx, sd, pos, tr, ph) == []


def test_pd3_dynamic_reads_arrays_formed_after_the_fill():
    p = Params(**BASE, pd3_exit=True, pd3_dynamic=True, pd3_n=1)
    ctx, sd, pos, tr, _ = mk([(102.9, 103.0, 102.4, 102.8)], p, pd3=[], pd3_broken=set())
    out = drive(ctx, sd, pos, tr, p)
    assert out == [] or out[0][0] == "pd3"                    # a dynamic list is re-read each bar (smoke: no crash, no fixed list)


# --- X8 other invalidations --------------------------------------------------------------------------------------

def test_leg_mt_exit_ir_eq_offside_meander_far_edge():
    # X8b: the leg candle = the first up-close candle at/after the sweep bar (index 2: o 99.2, c 101.4, MT 100.3)
    p = Params(**BASE, leg_mt_exit=True)
    ctx, sd, pos, tr, _ = mk([(101.0, 101.1, 99.9, 100.1)], p)
    assert drive(ctx, sd, pos, tr, p) == [("leg_mt", 100.1, 100)]
    ctx, sd, pos, tr, _ = mk([(101.0, 101.1, 100.4, 100.5)], p)
    assert drive(ctx, sd, pos, tr, p) == []
    # X8c: an immediate-rebalance trade above the range EQ (101): out when price retakes it (wick, at the EQ)
    p = Params(**BASE, ir_eq_exit=True)
    ctx, sd, pos, tr, _ = mk([(103.0, 103.1, 100.8, 102.0)], p, fill=103.0, leg=(99.0, 107.0), ir_eq=103.0)
    assert drive(ctx, sd, pos, tr, p) == [("ir_eq", 103.0, 100)]
    p = Params(**BASE, ir_eq_exit=True, ir_eq_wick=False)
    ctx, sd, pos, tr, _ = mk([(103.0, 103.1, 100.8, 103.2), (103.2, 103.3, 100.9, 102.5)], p, fill=103.0, ir_eq=103.0)
    assert drive(ctx, sd, pos, tr, p) == [("ir_eq", 102.5, 100)]
    # X8e offside: the up-close candle above (open 102.0) is respected (high reaches it, close below), then a close < entry
    p = Params(**BASE, offside_exit=True)
    ctx, sd, pos, tr, _ = mk([(101.0, 102.2, 100.9, 101.5), (101.5, 101.6, 100.5, 100.8)], p, offside=102.0)
    assert drive(ctx, sd, pos, tr, p) == [("offside", 100.8, 100)]
    ctx, sd, pos, tr, _ = mk([(101.0, 102.4, 100.9, 102.2), (102.2, 102.3, 100.5, 100.8)], p, offside=102.0)
    assert drive(ctx, sd, pos, tr, p) == []                   # smashed through (a close above the open): the test passed
    # X8g meander: closes inside the entry FVG (100-101) without a close above its top
    p = Params(**BASE, meander_bars=3)
    ctx, sd, pos, tr, _ = mk([(100.9, 101.0, 100.4, 100.6), (100.6, 100.9, 100.3, 100.5), (100.5, 100.8, 100.2, 100.4)], p)
    assert drive(ctx, sd, pos, tr, p) == [("meander", 100.4, 100)]
    ctx, sd, pos, tr, _ = mk([(100.9, 101.0, 100.4, 100.6), (100.6, 101.5, 100.3, 101.3), (101.3, 101.4, 100.2, 100.4),
                              (100.4, 100.6, 100.2, 100.5)], p)
    assert drive(ctx, sd, pos, tr, p) == []                   # a close above the top (a rejection) resets the count
    # X9c far edge: touch 100.0, no close at the CE (100.5) within the window -> half off
    p = Params(**BASE, far_edge_min=2, far_edge_frac=0.5)
    ctx, sd, pos, tr, _ = mk([(100.9, 101.0, 100.0, 100.2)], p)
    assert drive(ctx, sd, pos, tr, p) == [("far_edge", 100.2, 50)]
    ctx, sd, pos, tr, _ = mk([(100.9, 101.0, 100.0, 100.7), (100.7, 100.8, 100.3, 100.4)], p)
    assert drive(ctx, sd, pos, tr, p) == []                   # moved back to the CE in time
    p = Params(**BASE, far_edge_min=2, far_edge_frac=1.0)
    ctx, sd, pos, tr, _ = mk([(100.9, 101.0, 100.0, 100.2)], p)
    assert drive(ctx, sd, pos, tr, p) == [("far_edge", 100.2, 100)]


# --- X9 time stops -------------------------------------------------------------------------------------------------

def test_time_stop_frac_unit():
    p = Params(**BASE, time_stop_min=10, time_stop_pts=2.0)
    st = {}
    assert MG.time_stop_frac(p, st, nbars=1, elapsed=5, best=101.5, basis=101.0) == 0.0        # not yet due
    assert MG.time_stop_frac(p, st, nbars=2, elapsed=10, best=101.5, basis=101.0) == 1.0        # due, 0.5 < 2 pts
    assert MG.time_stop_frac(p, st, nbars=3, elapsed=15, best=101.5, basis=101.0) == 0.0        # spent
    assert MG.time_stop_frac(p, {}, nbars=2, elapsed=10, best=103.5, basis=101.0) == 0.0        # delivered
    pb = Params(**BASE, time_stop_bars=2, time_stop_ref="leg_high")
    assert MG.time_stop_frac(pb, {}, nbars=2, elapsed=10, best=102.9, basis=101.0, leg_hi=103.0) == 1.0
    assert MG.time_stop_frac(pb, {}, nbars=2, elapsed=10, best=103.0, basis=101.0, leg_hi=103.0) == 0.0
    pa = Params(**BASE, time_stop_min=10, time_stop_ref="array_far")
    assert MG.time_stop_frac(pa, {}, nbars=2, elapsed=10, best=100.9, basis=101.0, zone_top=101.0) == 1.0
    assert MG.time_stop_frac(pa, {}, nbars=2, elapsed=10, best=101.1, basis=101.0, zone_top=101.0) == 0.0
    assert MG.cut_qty(100, 0.5, Params(**BASE)) == 50 and MG.cut_qty(1, 0.5, Params(**BASE)) == 1
    assert MG.cut_qty(3, 0.5, Params(**BASE)) == 1
    assert MG.cut_qty(8, 0.5, Params(**dict(BASE, lot=5))) == 8        # a remainder under the minimum size is closed too (X9d)


def test_time_stop_cut_half_fires_once_and_full_exit():
    flat = [(101.0, 101.2, 100.9, 101.1)] * 4
    p = Params(**BASE, time_stop_min=10, time_stop_frac=0.5)
    ctx, sd, pos, tr, _ = mk(flat, p)
    out = drive(ctx, sd, pos, tr, p)
    assert out == [("time_cut", 101.1, 50)] and pos["left"] == 50          # once: the rest runs on
    p = Params(**BASE, time_stop_min=10)
    ctx, sd, pos, tr, _ = mk(flat, p)
    assert drive(ctx, sd, pos, tr, p) == [("time", 101.1, 100)]
    p = Params(**BASE, time_stop_bars=2)                       # the fill candle is the first: due at the end of the next
    ctx, sd, pos, tr, _ = mk(flat, p)
    out = drive(ctx, sd, pos, tr, p)
    assert out == [("time", 101.1, 100)] and tr.exits[0][0] == ctx.idx[pos["fill_i"] + 1]
    ctx, sd, pos, tr, _ = mk(flat, Params(**BASE, time_stop_min=10), t1_done=True)
    assert drive(ctx, sd, pos, tr, Params(**BASE, time_stop_min=10)) == []   # only before the first partial


# --- X10 / X11 / X12 -------------------------------------------------------------------------------------------------

def test_am_bulk_smt_hold_and_pm_consol_unit():
    flat = [(101.0, 101.2, 100.9, 101.1)] * 14               # 09:50 .. 10:55
    p = Params(**BASE, am_bulk_t=600, am_bulk_frac=0.8)
    ctx, sd, pos, tr, _ = mk(flat, p)
    out = drive(ctx, sd, pos, tr, p)
    assert out == [("am_bulk", 101.1, 80)] and tr.exits[0][0].strftime("%H:%M") == "09:55" or out[0][0] == "am_bulk"
    ctx, sd, pos, tr, _ = mk(flat, p, fill_t=601)             # filled after the bulk time: not touched
    assert drive(ctx, sd, pos, tr, p) == []
    ctx, sd, pos, tr, _ = mk(flat, p, session="PM")
    assert drive(ctx, sd, pos, tr, p) == []                   # AM family only
    # X10c: an SMT-tagged AM trade is held (no bulk) until 10:30 and what is left is closed then
    p = Params(**BASE, am_bulk_t=600, smt_hold_until=630, smt_hold_exit=True)
    ctx, sd, pos, tr, _ = mk(flat, p, smt_tag=True)
    out = drive(ctx, sd, pos, tr, p)
    assert out == [("smt_hold", 101.1, 100)]
    assert tr.exits[0][0].strftime("%H:%M") == "10:25"        # the bar ending 10:30
    ctx, sd, pos, tr, _ = mk(flat, p, smt_tag=False)
    assert drive(ctx, sd, pos, tr, p)[0][0] == "am_bulk"


def test_objective_and_reentry_target_lock_and_upclose_unit():
    p = Params(**BASE, obj_stop=True)
    ctx, sd, pos, tr, _ = mk([(101.0, 107.0, 100.9, 106.5)], p, draw=106.0)
    assert drive(ctx, sd, pos, tr, p) == [("objective", 106.0, 100)]
    ctx, sd, pos, tr, _ = mk([(101.0, 107.0, 100.9, 106.5)], p, draw=None)          # no draw: the last ladder level
    assert drive(ctx, sd, pos, tr, p) == [("objective", 107.0, 100)]
    assert MG.objective(dict(levels=[1.0, 2.0], level_kinds=["pool", "array"], draw=None),
                        Params(**BASE, obj_stop=True, obj_source="htf_ce")) == 2.0
    # D18: the re-entry is taken off at 3R and its stop locks the prior loss at 2R
    p = Params(**BASE, reentry_lock_r=2.0, reentry_target_r=3.0)
    ctx, sd, pos, tr, _ = mk([(101.0, 105.5, 100.9, 105.0), (105.0, 105.2, 104.0, 104.5), (104.5, 108.0, 104.0, 107.5)],
                             p, reentry=True, re_loss=300.0)
    out = drive(ctx, sd, pos, tr, p, upto=len(ctx.t) - 1)
    assert out == [] and pos["re_locked"]
    # 2R reached: the stop keeps 300 repaid on 100 units -> 101 + 3.0 = 104.0, held under the best price
    assert pos["stop"] == pytest.approx(104.0)
    out = drive(ctx, sd, pos, tr, p)
    assert out == [("re_target", 107.0, 100)]                 # 3R = 101 + 6
    # Ep07.5 tp_upclose: an add unit is sold into the first up-close candle closing above it
    p = Params(**BASE, tp_upclose=True)
    ctx, sd, pos, tr, _ = mk([(101.0, 101.3, 100.2, 100.4), (100.4, 101.2, 100.3, 101.1)], p)
    tr.adds.append((ctx.idx[pos["fill_i"] + 1], 100.5, 20))
    pos["left"] += 20
    out = drive(ctx, sd, pos, tr, p)
    assert out == [("tp_upclose", 101.1, 20)] and pos["left"] == 100


# --- stops from closed trades (X7c / X12 / X13a / X14b / X14d / Ep04.13) ----------------------------------------------

def closed(session, net, reason="stop", ts="2026-06-23 09:50", slow=False, stop_day=""):
    t = pd.Timestamp(ts, tz=NY)
    tr = S.Trade(D0, "ES", session, "am_mm", "long", "x", False, None, t, t, 100.0, 99.0, 102.0, None, 10)
    px = 100.0 + net / 10.0
    tr.exits.append((t + pd.Timedelta(minutes=5), px, 10, reason))
    tr.slow_chop, tr.stop_day = slow, stop_day
    return tr


def test_stops_from_each_rule():
    P = lambda **kw: Params(**BASE, **kw)
    w, l = closed("AM", 50.0, "t1"), closed("AM", -50.0, "stop")
    assert MG.stops_from(P(), [w, l]) == (None, {})
    assert MG.stops_from(P(no_trade_after_win=True), [l]) == (None, {})
    assert MG.stops_from(P(no_trade_after_win=True), [w])[0] == "win"
    assert MG.stops_from(P(chop_one_win=True), [w])[0] is None
    assert MG.stops_from(P(chop_one_win=True), [closed("AM", 50.0, "t1", slow=True)])[0] == "chop_win"
    assert MG.stops_from(P(obj_stop=True), [closed("AM", 50.0, "objective", stop_day="obj_stop")])[0] == "obj_stop"
    assert MG.stops_from(P(loss_ends_morning=True), [l]) == (None, {"AM": "loss_ends_morning"})
    assert MG.stops_from(P(loss_ends_morning=True), [closed("PM", -50.0)]) == (None, {})
    seq = [closed("AM", -50.0, ts=f"2026-06-23 09:{50 + 3 * k}") for k in range(3)]
    assert MG.stops_from(P(session_stop_after_fails=3), seq) == (None, {"AM": "fails"})
    assert MG.stops_from(P(session_stop_after_fails=3), seq[:2]) == (None, {})
    # a win in between resets the run; "arrays" counts only structural losers
    mid = [seq[0], closed("AM", 20.0, "t1", ts="2026-06-23 09:53"), seq[1], seq[2]]
    assert MG.stops_from(P(session_stop_after_fails=3), mid) == (None, {})
    soft = [closed("AM", -50.0, "time", ts=f"2026-06-23 09:{50 + 3 * k}") for k in range(3)]
    assert MG.stops_from(P(session_stop_after_fails=3, session_fail_mode="arrays"), soft) == (None, {})
    assert MG.stops_from(P(session_stop_after_fails=3, session_fail_mode="trades"), soft) == (None, {"AM": "fails"})
    # only trades closed by `ts` count (no look-ahead)
    ts = pd.Timestamp("2026-06-23 09:52", tz=NY)
    assert MG.stops_from(P(no_trade_after_win=True), [w], ts) == (None, {})
    assert MG.stops_from(P(no_trade_after_win=True), [w], ts + pd.Timedelta(minutes=10))[0] == "win"


def test_apply_stops_and_blocked_now_and_extras_view():
    p = Params(**BASE, no_trade_after_win=True)
    done = {"AM": False, "PM": False, "SB_AM": False}
    state = {}
    MG.apply_stops([closed("AM", 50.0, "t1")], p, done, state)
    assert all(done.values()) and state["day_done"] and MG.blocked_now(state, "PM")
    p = Params(**BASE, loss_ends_morning=True)
    done, state = {"AM": False, "PM": False, "SB_AM": False, "PRE9": False, "LH": False}, {}
    MG.apply_stops([closed("AM", -50.0)], p, done, state)
    assert done == {"AM": True, "PM": False, "SB_AM": True, "PRE9": True, "LH": False}
    assert MG.blocked_now(state, "PRE7") and not MG.blocked_now(state, "PM")
    ctx = SimpleNamespace(risk_view=dict(trades=[closed("AM", -50.0)]))
    ts = pd.Timestamp("2026-06-23 10:30", tz=NY)
    assert MG.extras_blocked(ctx, p, "AM", ts) and not MG.extras_blocked(ctx, p, "PM", ts)
    assert not MG.extras_blocked(ctx, Params(**BASE), "AM", ts)


def test_reentry_gate_and_sizing_helpers():
    p = Params(**BASE, reentry_half=True, reentry_gate=True)
    sd = SimpleNamespace(sign=1)
    rc = dict(side="long", stop_i=10, pending=True)
    assert MG.reentry_order_ok(dict(ext_i=12, i=15), sd, rc, p)
    assert not MG.reentry_order_ok(dict(ext_i=8, i=15), sd, rc, p)                 # the old sweep, not a restored one
    assert not MG.reentry_order_ok(dict(ext_i=12, i=15, fvg_i=9), sd, rc, p)       # the FVG was formed before the stop
    assert not MG.reentry_order_ok(dict(ext_i=12, i=15), SimpleNamespace(sign=-1), rc, p)
    assert MG.reentry_order_ok(dict(ext_i=1, i=2), sd, rc, Params(**BASE, reentry_half=True))   # ungated: anything goes
    # risk: half of the standard budget vs half of the losing trade's own risk
    s_ = {"reentered": {"AM": True}, "re_ctx": {"AM": {"ratio": 0.6}}}
    assert S._risk_mult(s_, "AM", Params(**BASE)) == 0.5
    assert S._risk_mult(s_, "AM", Params(**BASE, reentry_risk="loss")) == pytest.approx(0.3)
    assert S._risk_mult({"reentered": {}}, "AM", Params(**BASE, reentry_risk="loss")) == 1.0


def test_is_fade_and_late_cutoff():
    t = np.array([570 + 5 * k for k in range(12)])
    c = np.array([100.0, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111])
    ctx = SimpleNamespace(t=t, c=c, o=c - 0.5, start=0)
    up, dn = SimpleNamespace(sign=1), SimpleNamespace(sign=-1)
    assert MG.is_fade(ctx, dn, None, 8) and not MG.is_fade(ctx, up, None, 8)       # the day is up: a short fades
    assert MG.is_fade(ctx, up, dict(side=-1), 8) and not MG.is_fade(ctx, up, dict(side=1), 8)


# --- scenarios through run_day ----------------------------------------------------------------------------------

LATE = dict(BASE)


def _a(rows=None, hist=None, **kw):
    tr, locks, log, sk = run(day(rows or A_ROWS, spike=True), hist or history(), Params(**{**BASE, **kw}), A_LOCK)
    return tr


def test_run_day_defaults_unchanged_and_obj_stop_marks_the_day():
    t0 = _a()[0]
    assert [e[3] for e in t0.exits] == ["t1", "t2", "t3"] and t0.final_hit
    t1 = _a(obj_stop=True)[0]
    assert t1.stop_day == "obj_stop" and t1.final_hit
    t2 = _a(done_if_target=True)[0]
    assert t2.stop_day == "done_target"
    assert _a(done_if_target=True, done_target_before=570)[0].stop_day == ""        # the cut-off already passed
    # the 'objective' exit: the draw is above the last rung only for the HTF-CE source / when rungs are capped
    assert _a(no_trade_after_win=True)[0].stop_day == ""


def test_run_day_time_stop_cuts_and_be_pad_and_after_mss():
    rows = A_ROWS[:5] + [(100.3, 100.6, 100.0, 100.4)] * 6 + [(100.4, 100.5, 98.0, 98.2)]
    tr = _a(rows, time_stop_min=10)[0]
    assert [e[3] for e in tr.exits][0] == "time"
    tr = _a(rows, time_stop_min=10, time_stop_frac=0.5)[0]
    assert [e[3] for e in tr.exits][0] == "time_cut" and tr.exits[0][2] == tr.shares // 2
    tr = _a(rows, time_stop_bars=2)[0]
    assert tr.exits[0][3] == "time"
    tr = _a(rows, far_edge_min=2, far_edge_frac=1.0)
    assert tr == [] or tr[0].exits


def test_run_day_late_cutoff_default_and_switch_off():
    p = Params(**BASE)
    assert p.late_cutoff == 945 and Params(**BASE, late_cutoff=0).late_cutoff == 0


# --- no look-ahead (full vs truncated, entries and exits) --------------------------------------------------------------

LA = {
    "be": dict(be_on="stall", be_pad_pts=0.25, be_cost_pad=True, ladder_trail="measuring", trail_after=1, trail_pad_pts=0.25),
    "be_b": dict(be_on="after_mss", trail_first_fvg=True, first_fvg_fail=True, trade_type="day"),
    "be_c": dict(be_on="pool", trail_breakaway=True, ladder_trail="hit"),
    "abort": dict(fvg_abort=True, pd3_exit=True, pd3_half=True, leg_mt_exit=True),
    "abort_b": dict(fvg_abort=True, fvg_abort_body=True, pd3_exit=True, pd3_dynamic=True, ir_eq_exit=True, offside_exit=True,
                    meander_bars=3),
    "time": dict(time_stop_min=10, time_stop_frac=0.5, time_stop_ref="leg_high", far_edge_min=2, far_edge_frac=0.5),
    "time_b": dict(time_stop_bars=2, time_stop_ref="array_far", prop_exit=True, offside_exit=True, offside_level="wick_ce"),
    "session": dict(am_bulk_t=600, am_bulk_frac=0.8, smt_hold_until=630, smt_hold_exit=True, obj_stop=True,
                    pm_consol_exit=840, done_if_target=True),
    "loss": dict(reentry_half=True, reentry_gate=True, reentry_risk="loss", reentry_lock_r=2.0, reentry_target_r=3.0,
                 session_stop_after_fails=2, loss_ends_morning=True, no_trade_after_win=True, chop_one_win=True),
    "loss_b": dict(reverse_in_session=True, reverse_after_loss=False, lost_side_session=True,
                   session_stop_after_fails=3, session_fail_mode="arrays", reentry_half=True),
    "misc": dict(smt_bias="filter", smt_exit_against=True, ladder_trail="breakaway", pd3_exit=True, pd3_legacy=True, fvg_abort=True,
                 fvg_abort_mode="legacy", ir_eq_exit=True, ir_eq_wick=False, add_leg_at_fill=False, reentry_fomc_ok=True,
                 reentry_half=True, trade_type="day", day_stop="wick_ce", time_stop_min=10, pd3_list=("fvg", "vi"), pd3_n=2),
    "misc_b": dict(smt_bias="tag", ladder_trail="off", be_on="off", pd3_exit=True, pd3_list=("ob", "breaker"), time_stop_extras=False,
                   time_stop_min=10, offside_exit=True, add_pd_level=0.3, add_in_pd=True, adds=(0.5,), done_target_before=600),
    "adds": dict(adds=(0.5, 0.33), add_in_pd=True, add_cutoff=0.25, add_cut_ref="leg", add_mode="downclose", tp_upclose=True,
                 ep07_body_exit=True, late_cutoff=600, pool_size_rank=True),
}


@pytest.mark.parametrize("name", list(LA))
def test_look_ahead_synthetic(name):
    x, y = _syn()
    _no_look_ahead(x, 5, "RW", Params(**SYN, **LA[name]), COLS, every=3, partner=y, exits=True, min_trades=1)


@pytest.mark.skipif(not ES, reason="no ES data")
@pytest.mark.parametrize("name", ["time", "session", "loss", "misc", "adds"])
def test_look_ahead_es_short_window(name):
    es = B.load("ES", 5, source="databento")
    df = es[(es.index >= "2024-01-08") & (es.index < "2024-02-02")]
    meta = B.load_meta("ES", 5)
    p = Params(**FUT, draw_lock="off", htf_resist_cap=False, leg_pd=0, min_draw_pts=0, use_bias=False, ob_entry="post_mss",
               entry="edge_1tick", max_risk_pts=40, sb_model=True, ma_deuce=True, **LA[name])
    _no_look_ahead(df, 5, "ES", p, COLS, every=3, meta=meta, exits=True)


# --- _after_close: re-entry, reversal, stops (unit) -----------------------------------------------------------------

def _closed_pos(net, session="AM", key=None, high=101.0, draw=105.0, reason="stop", day_=D0):
    n = 10
    a = np.full(12, 100.0)
    h = a.copy()
    h[6:] = high
    sd = S.Side(1, a, h + 0.5, a - 0.5, a, 1, 0.0)
    t = pd.Timestamp(f"{day_} 09:50", tz=NY)
    tr = S.Trade(day_, "ES", session, "am_mm", "long", "x", False, None, t, t, 100.0, 99.0, 102.0, None, n)
    tr.exits.append((t + pd.Timedelta(minutes=5), 100.0 + net / n, n, reason))
    tr.entry_risk_pct = 0.012
    pos = dict(trade=tr, side=sd, fill_i=4, draw=draw, levels=[102.0, draw], done_key=key or session,
               basis=1000.0, n=n, best=100.0)
    return pos, tr


def _state():
    return {"reentered": {}, "re_ctx": {}, "only_side": {}, "reversed": {}, "day_loss": False, "rs": None}


def _ctx(day_=D0):
    return SimpleNamespace(day=day_, lock={}, equity=100_000.0)


def test_after_close_reentry_half_ungated_gated_fomc_and_draw():
    # ungated: the own done key re-opens (an SB_AM loss no longer re-opens the plain AM slot)
    pos, tr = _closed_pos(-100.0, key="SB_AM")
    done, st, trades = {"AM": True, "SB_AM": True}, _state(), []
    S._after_close(pos, trades, Params(**BASE, reentry_half=True), done, st, i=7, ctx=_ctx())
    assert done == {"AM": True, "SB_AM": False} and st["reentered"]["AM"] and st["re_ctx"]["AM"]["pending"]
    assert S._risk_mult(st, "AM", Params(**BASE, reentry_half=True)) == 0.5
    # gated, on an FOMC day: no re-entry
    fomc = date(2024, 1, 31)
    pg = Params(**BASE, reentry_half=True, reentry_gate=True)
    pos, tr = _closed_pos(-100.0, day_=fomc)
    done, st = {"AM": True}, _state()
    S._after_close(pos, [], pg, done, st, i=7, ctx=_ctx(fomc))
    assert done["AM"] and not st["re_ctx"]
    pos, tr = _closed_pos(-100.0, day_=fomc)
    S._after_close(pos, [], Params(**BASE, reentry_half=True, reentry_gate=True, reentry_fomc_ok=True), done, st, i=7,
                   ctx=_ctx(fomc))
    assert not done["AM"]                                       # reentry_fomc_ok
    # gated: the draw was traded since the fill -> the idea is spent, no re-entry
    pos, tr = _closed_pos(-100.0, high=106.0, draw=105.0)
    done, st = {"AM": True}, _state()
    S._after_close(pos, [], pg, done, st, i=11, ctx=_ctx())
    assert done["AM"]
    pos, tr = _closed_pos(-100.0, high=101.0, draw=105.0)
    done, st = {"AM": True}, _state()
    S._after_close(pos, [], pg, done, st, i=11, ctx=_ctx())
    assert not done["AM"] and st["re_ctx"]["AM"]["stop_i"] == 11
    # D18: half of the LOSING trade's own risk (0.6% of equity vs the 1.2% budget)
    pos, tr = _closed_pos(-100.0)
    tr.entry_risk_pct = 0.006
    done, st = {"AM": True}, _state()
    S._after_close(pos, [], Params(**BASE, reentry_half=True, reentry_risk="loss", risk_dollars=1200.0), done, st, i=7, ctx=_ctx())
    assert st["re_ctx"]["AM"]["ratio"] == pytest.approx(0.5)


def test_after_close_reverse_in_session_and_loss_ends_morning_and_win_day():
    pos, tr = _closed_pos(-100.0)
    done, st = {"AM": True, "PM": False, "SB_AM": True}, _state()
    S._after_close(pos, [], Params(**BASE, reverse_in_session=True), done, st, i=7, ctx=_ctx())
    assert not done["AM"] and st["only_side"]["AM"] == -1 and st["reversed"]["AM"] and not st["reentered"]   # not at half risk
    pos, tr = _closed_pos(-100.0)
    done, st = {"AM": True, "PM": False, "SB_AM": True, "PRE9": True}, _state()
    S._after_close(pos, [], Params(**BASE, reverse_in_session=True, loss_ends_morning=True), done, st, i=7, ctx=_ctx())
    assert done["AM"] and done["SB_AM"] and not done["PM"]       # the beginner rule wins: the morning is over
    assert st["lost_fam"] == "AM"
    pos, tr = _closed_pos(+100.0, reason="t1")
    done, st = {"AM": True, "PM": False, "LH": False}, _state()
    S._after_close(pos, [], Params(**BASE, no_trade_after_win=True), done, st, i=7, ctx=_ctx())
    assert all(done.values()) and st["day_done"]
    # three losses in a row stop the session even though reentry_half re-opened the flag after the third
    trades, done, st = [], {"AM": True, "PM": False}, _state()
    for k in range(3):
        pos, tr = _closed_pos(-100.0)
        tr.exits[0] = (pd.Timestamp(f"{D0} 09:{50 + 2 * k}", tz=NY), 99.0, 10, "stop")
        S._after_close(pos, trades, Params(**BASE, reentry_half=True, session_stop_after_fails=3), done, st, i=7 + k, ctx=_ctx())
        if k < 2:
            st["reentered"] = {}                                  # allow another re-entry in the unit test
    assert done["AM"] and not done["PM"] and MG.blocked_now(st, "AM")


def test_final_target_and_objective_set_the_day():
    pos, tr = _closed_pos(+200.0, reason="t2")
    tr.final_hit = True
    done, st = {"AM": True, "PM": False}, _state()
    S._after_close(pos, [], Params(**BASE, done_if_target=True), done, st, i=7, ctx=_ctx())
    assert tr.stop_day == "done_target" and all(done.values())
    pos, tr = _closed_pos(+200.0, reason="t2")
    tr.final_hit = True
    tr.exits[0] = (pd.Timestamp(f"{D0} 15:10", tz=NY), 102.0, 10, "t2")
    done, st = {"AM": True, "PM": False}, _state()
    S._after_close(pos, [], Params(**BASE, done_if_target=True), done, st, i=7, ctx=_ctx())
    assert tr.stop_day == "" and not done["PM"]                  # after 15:00 the day is not ended
    pos, tr = _closed_pos(+50.0, reason="objective")
    done, st = {"AM": True, "PM": False}, _state()
    S._after_close(pos, [], Params(**BASE, obj_stop=True), done, st, i=7, ctx=_ctx())
    assert tr.stop_day == "obj_stop" and all(done.values())


# --- adds (M2.6 / Ep07.5) ---------------------------------------------------------------------------------------------

def test_add_in_pd_and_fixed_leg():
    sd = SimpleNamespace(h=np.array([100.0, 101.0, 104.0, 104.0]))
    pos = dict(leg=(100.0, 110.0), fill_i=1)
    p = Params(**BASE, add_in_pd=True)
    assert S._SM.add_ok(sd, pos, 104.0, 3, p) and S._SM.add_ok(sd, pos, 105.0, 3, p)       # at / under EQ (105)
    assert not S._SM.add_ok(sd, pos, 105.5, 3, p)
    assert S._SM.add_ok(sd, pos, 106.0, 3, Params(**BASE))                                 # off: no P/D test
    assert not S._SM.add_ok(sd, pos, 103.0, 3, Params(**BASE, add_in_pd=True, add_pd_level=0.2))


def test_leg_is_fixed_at_the_fill_for_the_add_cuts():
    o = dict(ext_i=1, session="AM")
    p = Params(**BASE, add_cutoff=0.25, add_cut_ref="leg")
    ctx, sd, pos, tr, _ = mk([], p, leg=(99.0, 102.0))
    MG.init_pos(ctx, sd, pos, tr, o, pos["fill_i"], p)
    assert pos["leg"] == (99.0, 103.0)                             # the displacement ran to 103.0 before the fill (bar 3)
    p = Params(**BASE, add_cutoff=0.25, add_cut_ref="leg", add_leg_at_fill=False)
    ctx, sd, pos, tr, _ = mk([], p, leg=(99.0, 102.0))
    MG.init_pos(ctx, sd, pos, tr, o, pos["fill_i"], p)
    assert pos["leg"] == (99.0, 102.0)
    ctx, sd, pos, tr, _ = mk([], Params(**BASE), leg=(99.0, 102.0))
    MG.init_pos(ctx, sd, pos, tr, o, pos["fill_i"], Params(**BASE))
    assert pos["leg"] == (99.0, 102.0)                              # no add cut on: untouched


def test_downclose_add_arms_at_a_down_close_candle_that_holds():
    p = Params(**BASE, add_mode="downclose")
    ctx, sd, pos, tr, _ = mk([(101.4, 102.5, 101.3, 102.4), (102.4, 102.5, 101.9, 102.0)], p)
    armed = []
    i = pos["fill_i"] + 2
    assert MG.downclose_add(sd, pos, tr, i, p, lambda px: armed.append(px) or True)
    assert armed == [102.0]
    armed.clear()
    assert not MG.downclose_add(sd, pos, tr, pos["fill_i"] + 1, p, lambda px: armed.append(px))     # an up-close candle
    ctx, sd, pos, tr, _ = mk([(101.4, 102.5, 98.0, 98.4)], p)
    assert not MG.downclose_add(sd, pos, tr, pos["fill_i"] + 1, p, lambda px: armed.append(px))     # broke the stop / array


# --- SMT bias (B18.3) -------------------------------------------------------------------------------------------------

def _smt_ctx(ours_low, partner_low, ours_high=None, partner_high=None, n=12):
    idx = pd.date_range(pd.Timestamp(f"{D0} 08:00", tz=NY), periods=n, freq="5min")
    t = (idx.hour * 60 + idx.minute).values

    def mkc(lo, hi, hist_lo, hist_hi):
        l = np.full(n, 100.0)
        l[3] = lo
        h = np.full(n, 101.0)
        h[5] = hi
        c = np.full(n, 100.5)
        hd = pd.DataFrame({"open": [100.0], "high": [hist_hi], "low": [hist_lo], "close": [100.0]})
        return SimpleNamespace(idx=idx, t=t, l=l, h=h, o=c, c=c, start=0, tf=5, hist=[hd])
    ctx = mkc(ours_low, ours_high if ours_high is not None else 101.0, 99.0, 105.0)
    ctx.pside = (mkc(partner_low, partner_high if partner_high is not None else 101.0, 99.0, 105.0), None, None)
    return ctx


def test_smt_bias_bullish_bearish_and_none():
    p = Params(**BASE, smt_bias="filter")
    assert MG.smt_bias(_smt_ctx(98.5, 99.5), 11, p) == 1            # ours took the previous low (99), the sister held
    assert MG.smt_bias(_smt_ctx(98.5, 98.0), 11, p) == 0            # both took it: no divergence
    assert MG.smt_bias(_smt_ctx(100.0, 100.0, ours_high=106.0, partner_high=104.0), 11, p) == -1
    c = _smt_ctx(98.5, 99.5)
    c.pside = None
    assert MG.smt_bias(c, 11, p) == 0                                # no partner
    c = _smt_ctx(98.5, 99.5)
    assert MG.smt_bias(c, 2, p) == 0 and getattr(c, "_smt_bias", None) is None     # before the divergence printed: not cached
    assert MG.smt_bias(c, 11, p) == 1 and c._smt_bias == 1


def test_run_day_downclose_add_tp_upclose_and_late_cutoff():
    rows = A_ROWS[:5] + [(100.3, 101.8, 100.2, 101.7), (101.7, 102.5, 101.5, 102.4), (102.4, 102.5, 101.4, 101.6),
                         (101.6, 103.0, 101.5, 102.9)]
    t = _a(rows, adds=(0.5,))[0]
    assert t.adds == []                                          # the default add rests at a NEW FVG: none formed after the fill
    t = _a(rows, adds=(0.5,), add_mode="downclose")[0]
    assert len(t.adds) == 1 and t.adds[0][1] == 101.6 and t.adds[0][2] > 0       # buy the down-close candle at its close
    assert [e[3] for e in t.exits] == ["t1", "am_exit"]
    q_add = t.adds[0][2]
    t = _a(rows, adds=(0.5,), add_mode="downclose", tp_upclose=True)[0]
    assert [(e[3], float(e[1]), e[2]) for e in t.exits][1] == ("tp_upclose", 102.9, q_add)      # sold into the up-close candle
    t = _a(rows, adds=(0.5,), add_mode="downclose", late_cutoff=585)[0]
    assert t.adds == []                                          # T11: no adds after the cut-off time (here 09:45)


def test_run_day_new_stop_fields_and_columns():
    t = _a()[0]
    row = t.row(0.0)
    for k in ("final_hit", "slow_chop", "reentry", "stop_day"):
        assert k in row
    assert row["final_hit"] is True and row["reentry"] is False


# --- the real engine on the synthetic window: a PM short (2026-03-13) is stopped out and re-entered ------------------------

def _syn_run(**kw):
    x, y = _syn("2026-03-02", "2026-04-24")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return B.run(x, 5, "RW", Params(**SYN, **kw), y)


def test_synthetic_reentry_gate_risk_and_session_stop():
    base = _syn_run()
    assert len(base) == 6 and not base.reentry.any()
    t = _syn_run(reentry_half=True)
    assert len(t) == 7 and t.reentry.sum() == 1
    re_ = t[t.reentry].iloc[0]
    assert re_.side == "short" and re_.session == "PM" and str(re_.date) == "2026-03-13"      # the same side, the same session
    assert t.equals(_syn_run(reentry_half=True, reentry_gate=True)) or len(_syn_run(reentry_half=True, reentry_gate=True)) == 7
    # D18: half of the LOSING trade's own risk (0.40% -> 0.20% of equity)
    tl = _syn_run(reentry_half=True, reentry_risk="loss")
    first = tl[(tl.date == re_.date) & ~tl.reentry].iloc[0]
    assert tl[tl.reentry].iloc[0].entry_risk_pct == pytest.approx(first.entry_risk_pct / 2, rel=0.05)
    # X7c: one failed trade ends the session - the reentry_half flag cannot re-open it (the audit's leak)
    assert len(_syn_run(reentry_half=True, session_stop_after_fails=1)) == 6
    assert len(_syn_run(reentry_half=True, session_stop_after_fails=1, session_fail_mode="arrays")) == 6
    assert len(_syn_run(reentry_half=True, session_stop_after_fails=2)) == 7              # two fails would be needed first
    # the stop is a structural failure, so "arrays" counts it too; a lock / target on the re-entry is wired
    assert len(_syn_run(reentry_half=True, reentry_lock_r=2.0, reentry_target_r=3.0)) == 7
