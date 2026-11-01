"""Caption-gap pass, package management_exits #1/3, part A3: the ladder-loop and stop-lock specs - levels_liquidity_targets.md 3, 47, 57, 84; management_partials_trailing_exits.md 5, 6, 10, 11, 12, 14, 16,
17, 18, 19 (same stub harness as test_caption_gap_me1a.py; scenario C and A through run_day for the loop hooks)."""
from datetime import date
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from mentorship import me1, strategy as S, targets as TP, tp3
from mentorship.strategy import Params
from dataclasses import dataclass as _oa_dc


@_oa_dc
class Params(Params):   # OA1029 Q92: these tests exercise other rules; the order-block narrative gate (default on) leaves them no trades
    ob_need_narrative: bool = False

from test_review_fixes import A_ROWS, BASE, day, history, run as rf_run
from test_caption_gap_es1a import C_ROWS, POST
from test_caption_gap_me1a import fill, flatrows, mkctx, mkpos, pk, reasons, step


def crun(rows, **kw):
    tr, *_ = rf_run(day(rows), history(), Params(**{**BASE, **POST, **kw}), {})
    return tr


# --- A2-quick-run-through (3) ----------------------------------------------------------------------------------------------------------------------

def test_tap_and_stall_rung():
    # scenario C: T1 = 103.5, the fill bar is 09:55; the touch bar (10:00) taps 103.5, the next bars stay under it, then a body closes under the rung
    tap = [(100.5, 103.5, 100.4, 103.4), (103.4, 103.45, 102.9, 103.0), (103.0, 103.1, 102.4, 102.6), (102.6, 102.7, 102.2, 102.5)] + [(102.5, 102.6, 102.4, 102.5)] * 3
    for n, expect in ((3, ["t1", "rt_stall_exit"]), (0, ["t1"])):
        tr = crun(list(C_ROWS[:6]) + tap, run_through_bars=n)
        assert [e[3] for e in tr[0].exits][:len(expect)] == expect and (n == 0 or "rt_stall" in tr[0].mgmt_tags)
        if n:
            assert tr[0].exits[1][1] == pytest.approx(102.5)                                  # out at the close of the bar that closed back through the rung
    cont = [(100.5, 103.5, 100.4, 103.4), (103.4, 104.6, 103.3, 104.5)] + [(104.5, 104.6, 104.3, 104.5)] * 4
    tr = crun(list(C_ROWS[:6]) + cont, run_through_bars=3)
    assert "rt_stall" not in tr[0].mgmt_tags and [e[3] for e in tr[0].exits][:1] == ["t1"] and "rt_stall_exit" not in [e[3] for e in tr[0].exits]


def test_run_through_ticks_and_bars_unit():
    rows = [(4099, 4100.25, 4098.5, 4099.5), (4099.5, 4100.0, 4099.0, 4099.2), (4099.2, 4099.75, 4098.9, 4099.0), (4099.0, 4099.2, 4098.5, 4099.5)]
    ctx = mkctx(rows)
    p = pk(run_through_bars=3)
    pos, tr, sd = mkpos(ctx, 1, 0, 4090.0, 4085.0, levels=(4100.0, 4120.0), fracs=(0.5, 0.5))
    fill(ctx, sd, pos, tr, p)
    pos["left"] = 5
    pos["k"] = 1
    me1.rung_taken(ctx, sd, pos, tr, 0, 4100.0, 0, p)
    step(ctx, sd, pos, tr, p, 1, 3)
    assert reasons(tr) == ["rt_stall_exit"] and pos["stall_at"] == 4100.0 and tr.exits[0][1] == 4099.5


# --- L12-sd-step-to-time-window (47) ---------------------------------------------------------------------------------------------------------------

def _sd_pos(kinds=("proj", "proj"), levels=(4100.0, 4110.0), fracs=(0.5, 0.5)):
    ctx = mkctx(flatrows(40, 4095.0), t0=585)                                     # from 09:45
    p = pk(sd_time_roll=True)
    pos, tr, sd = mkpos(ctx, 1, 1, 4090.0, 4085.0, levels=levels, fracs=fracs, kinds=list(kinds))
    fill(ctx, sd, pos, tr, p)
    return ctx, sd, pos, tr, p


def test_sd_roll_until_window():
    ctx, sd, pos, tr, p = _sd_pos()
    # SD1 (4100) hit at 09:50 (before 10:00): not an exit, its share rolls to the next SD level
    i = 5
    assert ctx.t[i] == 590
    assert me1.rung_hook(ctx, sd, pos, tr, 0, pos["levels"], 4100.5, 4099.0, i, ctx.idx[i], p, 590, 1) == "skip" and pos["fracs"] == (0.0, 1.0)
    # SD1.5 (4110) closed beyond it at 10:15 (inside the window): all out at the close
    j = 30
    assert ctx.t[j] == 615
    assert me1.rung_hook(ctx, sd, pos, tr, 1, pos["levels"], 4111.0, 4110.5, j, ctx.idx[j], p, 615, 1) == "break"
    assert reasons(tr) == ["sd_window"] and pos["left"] == 0 and tr.exits[0][1] == 4110.5 and tr.final_hit
    # inside the window a wick above the level (the close below it) is not an exit
    ctx, sd, pos, tr, p = _sd_pos()
    assert me1.rung_hook(ctx, sd, pos, tr, 0, pos["levels"], 4101.0, 4099.0, j, ctx.idx[j], p, 615, 1) == "break" and not tr.exits and pos["left"] == 10
    # after the window (12:00) and for a non-SD kind the ladder is the built one; the last SD rung before the window is kept (nothing to roll to)
    ctx, sd, pos, tr, p = _sd_pos(kinds=("pool", "proj"))
    assert me1.rung_hook(ctx, sd, pos, tr, 0, pos["levels"], 4101.0, 4100.5, 5, ctx.idx[5], p, 590, 1) is None
    assert me1.rung_hook(ctx, sd, pos, tr, 1, pos["levels"], 4111.0, 4110.5, 5, ctx.idx[5], p, 590, 1) is None
    assert me1.rung_hook(ctx, sd, pos, tr, 1, pos["levels"], 4111.0, 4110.5, 5, ctx.idx[5], p, 725, 1) is None


# --- L14-hold-above-reached-objective (57) -------------------------------------------------------------------------------------------------------------

def test_lose_reached_objective_exits():
    # scenario C: T1 (103.5) passed on the 10:00 bar; a 5m body close back under it at 10:05 exits the rest
    rows = list(C_ROWS[:6]) + [(100.5, 103.6, 100.4, 103.6), (103.6, 103.7, 102.0, 103.4), (103.4, 103.5, 103.2, 103.4)]
    on = crun(rows, hold_reached=True)
    assert [e[3] for e in on[0].exits][:2] == ["t1", "hold_lost"] and on[0].exits[1][1] == pytest.approx(103.4) and "hold_lost" in on[0].mgmt_tags
    off = crun(rows)
    assert "hold_lost" not in [e[3] for e in off[0].exits]


def test_hold_reached_marks_the_session_done():
    pos = dict(me1=dict(side_done=True))
    done = {"AM": False}
    me1.after_close(pos, SimpleNamespace(resist_speed=""), done, "AM")
    assert done["AM"] is True
    me1.after_close(dict(me1={}), SimpleNamespace(resist_speed=""), done2 := {"AM": False}, "AM")
    assert done2["AM"] is False


# --- L12-bodies-hold-sd-continuation (84) -------------------------------------------------------------------------------------------------------

def test_sd_bodies_hold_keeps_runner():
    # rung 4496.5 reached; the 5m bodies close beyond it (4497-4499): no partial; the 5m close at 4495 takes the partial and arms the body trail
    rows = [(4490, 4491, 4489, 4490)] + [(4490, 4497.5, 4489.5, 4497.2)] + [(4497.2, 4499.5, 4496.8, 4498.5)] * 7 + [(4498.5, 4498.7, 4494.8, 4495.0)] + [(4495.0, 4495.5, 4494.5, 4495.0)] * 3
    ctx = mkctx(rows, t0=575)                           # 09:35: the 5m candles close at minutes ...
    p = pk(sd_body_hold=True)
    pos, tr, sd = mkpos(ctx, 1, 0, 4490.0, 4480.0, levels=(4496.5, 4520.0), fracs=(0.5, 0.5), kinds=["proj", "proj"])
    fill(ctx, sd, pos, tr, p)
    assert me1.rung_hook(ctx, sd, pos, tr, 0, pos["levels"], 4497.5, 4497.2, 1, ctx.idx[1], p, int(ctx.t[1]), 1) == "break" and not tr.exits      # deferred
    for i in range(2, 9):
        assert me1.rung_hook(ctx, sd, pos, tr, 0, pos["levels"], float(ctx.h[i]), float(ctx.c[i]), i, ctx.idx[i], p, int(ctx.t[i]), 1) == "break"
        step(ctx, sd, pos, tr, p, i)
    assert not tr.exits and pos["left"] == 10
    i = 9
    assert ctx.c[i] == 4495.0 and (ctx.t[i] + 1) % 5 == 0
    step(ctx, sd, pos, tr, p, i)
    assert reasons(tr) == ["t1"] and tr.exits[0][2] == 5 and tr.exits[0][1] == 4495.0 and pos["k"] == 1 and pos["trail_now"] and pos["me1"]["trail_body"]
    # the next rung printing first releases the deferral (the draw beyond is reached)
    ctx2 = mkctx(rows, t0=575)
    pos, tr, sd = mkpos(ctx2, 1, 0, 4490.0, 4480.0, levels=(4496.5, 4498.0), fracs=(0.5, 0.5), kinds=["proj", "proj"])
    fill(ctx2, sd, pos, tr, p)
    assert me1.rung_hook(ctx2, sd, pos, tr, 0, pos["levels"], 4499.0, 4498.5, 2, ctx2.idx[2], p, int(ctx2.t[2]), 1) is None


# --- X2-best-case-resting-limit (5) --------------------------------------------------------------------------------------------------------------

def test_best_case_limit():
    # scenario C: avg 100.4, O (T2) 108.25 -> best case 116.1; the displacement bar to 108.5 closes beyond O: 65 % of what is left goes at O, the rest keeps the stop at the previous rung and the limit
    after = [(108.4, 108.5, 103.0, 103.2)]                                                       # the next bar drops to the stop (the previous rung 103.5)
    tr = crun(list(C_ROWS) + after, best_case_limit=True)
    ex = [(e[3], round(e[1], 2), e[2]) for e in tr[0].exits]
    assert ex[0][0] == "t1" and ex[1][0] == "bulk_O" and ex[1][1] == pytest.approx(108.25) and ex[1][2] == int(0.65 * (tr[0].shares - ex[0][2]))
    assert ex[2][0] in ("be", "stop") and ex[2][1] == pytest.approx(103.5)
    assert tr[0].exits[1][2] + tr[0].exits[2][2] + tr[0].exits[0][2] == tr[0].shares
    # a weak bar: it prints beyond O (108.3) but closes under it: the rest goes at the close
    weak = list(C_ROWS)
    weak[7] = (102.9, 108.3, 102.8, 108.2)
    tr = crun(weak, best_case_limit=True)
    assert [e[3] for e in tr[0].exits] == ["t1", "bulk_O", "bulk_O"] and tr[0].exits[2][1] == pytest.approx(108.2)
    # off: the built ladder takes everything at T2
    tr = crun(list(C_ROWS), best_case_limit=False)
    assert [e[3] for e in tr[0].exits] == ["t1", "t2"]


def test_best_case_limit_fills_at_the_best_case():
    rows = list(C_ROWS) + [(108.4, 117.0, 108.3, 116.5)]                                          # then price runs on to the best case 116.1
    tr = crun(rows, best_case_limit=True)
    assert [e[3] for e in tr[0].exits] == ["t1", "bulk_O", "best_case"] and tr[0].exits[2][1] == pytest.approx(116.1)


# --- E1-manual-touch-exits (6) ------------------------------------------------------------------------------------------------------------------

def test_exit_fill_modes():
    pos = dict(level_kinds=[])
    res = {}
    for mode in ("touch", "limit_through", "touch_1tick"):
        p = pk(exit_fill=mode, tick_pts=0.25)
        res[mode] = [TP.rung_hit(pos, 0, 4100.0, h, 4099.0, 570, 1, p, 0.0) for h in (4099.75, 4100.0, 4100.25)]
    assert [x[0] for x in res["touch"]] == [False, True, True] and all(x[1] == 4100.0 for x in res["touch"])
    assert [x[0] for x in res["limit_through"]] == [False, False, True]
    assert [x[0] for x in res["touch_1tick"]] == [True, True, True] and all(x[1] == 4099.75 for x in res["touch_1tick"])
    assert TP.rung_hit(pos, 0, 4100.0, 4099.8, 4099.0, 570, 1, pk(exit_fill="touch_1tick", exit_slip_ticks=2), 0.0) == (True, 4099.5)
    assert me1.rung_px(4100.0, pk(exit_fill="touch_1tick", exit_slip_ticks=2)) == 4099.5


def test_exit_fill_through_the_engine():
    rows = list(C_ROWS[:6]) + [(100.5, 103.25, 100.4, 103.2), (103.2, 103.3, 103.0, 103.1)] + [(103.1, 103.2, 103.0, 103.1)] * 2
    on = crun(rows, exit_fill="touch_1tick")
    off = crun(rows)
    assert on[0].exits[0][3] == "t1" and on[0].exits[0][1] == pytest.approx(103.25)               # the bar high 103.25 is within a tick of T1 (103.5): filled at the level minus the slip
    assert off[0].exits[0][3] != "t1"


# --- X4-be-vi-then-new-ssl (10) ---------------------------------------------------------------------------------------------------------------

def _vi_book():
    return [(4000, 4001, 3999, 4000.5), (4000.5, 4004, 4000.2, 4003.5), (4003.5, 4004.5, 4003, 4004), (4006, 4008, 4004.5, 4007.5), (4007.5, 4008, 4003, 4003.5), (4003.5, 4004, 4001.5, 4002.0)]


def test_be_vi_then_new_ssl():
    p = pk(be_mode="vi_then_new_ssl", stop_tick_pts=0.25)
    pad = p.pad

    def run(after):
        ctx = mkctx(_vi_book() + after)
        pos, tr, sd = mkpos(ctx, 1, 5, 4002.0, 4000.0, levels=(4030.0,), ext=3999.0)
        pos["ext_i"] = 0
        tr.bz_top, tr.bz_bottom = 4002.5, 4001.0                                              # the breaker (real prices)
        fill(ctx, sd, pos, tr, p)
        return ctx, sd, pos, tr
    # a bar through the VI top (4006) followed by a close beyond it moves the stop to the breaker's far edge (the bottom) minus the pad
    ctx, sd, pos, tr = run([(4002, 4006.5, 4002, 4006.0), (4006.0, 4007.5, 4005.5, 4007.0)])
    assert pos["me1"]["vi"] == (4004.0, 4006.0) and pos["me1"]["bz_far"] == 4001.0
    step(ctx, sd, pos, tr, p, 6, 7)
    assert pos["stop"] == pytest.approx(4001.0 - pad) and pos["me1"]["vi_done"] and not pos["me1"].get("ssl_done")
    # a later print above the most recent swing high formed after the entry moves it to entry
    ctx, sd, pos, tr = run([(4002, 4006.5, 4002, 4006.0), (4006.0, 4007.5, 4005.5, 4007.0), (4007.0, 4009.0, 4006.5, 4008.0), (4008.0, 4008.5, 4007.0, 4007.5), (4007.5, 4010.0, 4007.2, 4009.5)])
    step(ctx, sd, pos, tr, p, 6, 10)
    assert pos["stop"] == pytest.approx(4002.0) and pos["me1"]["ssl_done"]
    # a wick through the VI whose next close falls back leaves the stop unchanged
    ctx, sd, pos, tr = run([(4002, 4006.5, 4002, 4005.0), (4005.0, 4005.5, 4003.0, 4004.0), (4004.0, 4004.5, 4003.0, 4003.5)])
    step(ctx, sd, pos, tr, p, 6, 8)
    assert pos["stop"] == pytest.approx(4000.0) and not pos["me1"].get("vi_done")


# --- X4-be-without-partials (11) --------------------------------------------------------------------------------------------------------------

def _opp_book():
    return [(4112, 4113, 4107, 4108), (4108, 4108, 4100, 4101), (4101, 4105, 4099, 4104.5), (4104.5, 4104.6, 4099.8, 4100.0)]


def test_be_through_opposing_fvg():
    p = pk(be_mode="through_opposing_fvg")
    ctx = mkctx(_opp_book() + [(4100, 4106.5, 4099.9, 4106.0), (4106.0, 4107.5, 4105.5, 4107.2), (4107.2, 4108, 4106.5, 4107.5)])
    pos, tr, sd = mkpos(ctx, 1, 3, 4100.0, 4098.0, levels=(4115.0,))
    fill(ctx, sd, pos, tr, p)
    opp = pos["me1"]["opp"]
    assert (opp.bottom, opp.top) == (4105.0, 4107.0)
    step(ctx, sd, pos, tr, p, 4)
    assert pos["stop"] == 4098.0                                          # the high 4106.5 has not exceeded the far edge (4107)
    step(ctx, sd, pos, tr, p, 5)
    assert pos["stop"] == pytest.approx(4100.0)                          # entry + be_pad_pts (0)
    ctx2 = mkctx(_opp_book() + [(4100, 4106.5, 4099.9, 4106.0)])
    pos2, tr2, sd2 = mkpos(ctx2, 1, 3, 4100.0, 4098.0, levels=(4115.0,))
    fill(ctx2, sd2, pos2, tr2, pk(be_mode="through_opposing_fvg", be_pad_pts=0.5))
    step(ctx2, sd2, pos2, tr2, pk(be_mode="through_opposing_fvg", be_pad_pts=0.5), 4)
    assert pos2["stop"] == 4098.0
    # no opposing FVG: the first new bullish FVG above the entry moves it
    flat = [(4100, 4101, 4099, 4100.5)] * 3 + [(4100.5, 4100.8, 4099.8, 4100.0)]
    rows = flat + [(4100, 4102, 4099.9, 4101.8), (4101.8, 4106, 4101.7, 4105.5), (4105.5, 4108, 4103.0, 4107.5)]          # a bullish FVG 4102-4103 after the fill
    ctx3 = mkctx(rows)
    pos3, tr3, sd3 = mkpos(ctx3, 1, 3, 4100.0, 4098.0, levels=(4115.0,))
    fill(ctx3, sd3, pos3, tr3, p)
    assert pos3["me1"].get("opp") is None
    step(ctx3, sd3, pos3, tr3, p, 4, 5)
    assert pos3["stop"] == 4098.0
    step(ctx3, sd3, pos3, tr3, p, 6)
    assert pos3["stop"] == pytest.approx(4100.0) and pos3["me1"]["opp_done"]


# --- X4-be-plus-cap-htf (12) --------------------------------------------------------------------------------------------------------------------

def test_be_cap_htf():
    rows = flatrows(2, 4553.0) + [(4553, 4570, 4552, 4569), (4569, 4571, 4560, 4562), (4562, 4568, 4560, 4565), (4565, 4580, 4564, 4572), (4572, 4573, 4568, 4570), (4570, 4585, 4569, 4584)]
    ctx = mkctx(rows)
    p = pk(be_cap_htf=True)
    pos, tr, sd = mkpos(ctx, 1, 1, 4559.9, 4545.0, levels=(4570.0, 4580.0, 4590.0), fracs=(0.3, 0.3, 0.4))
    fill(ctx, sd, pos, tr, p)
    pos["me1"]["htf_hi"] = 4560.0
    # partial #1 at 4570: the stop = BE + pad, never above the 4h array's top less the pad (4560 - 0.25)
    tr.exits.append((ctx.idx[2], 4570.0, 3, "t1")); pos["left"] -= 3; pos["t1_done"] = True
    step(ctx, sd, pos, tr, p, 2)
    assert pos["stop"] == pytest.approx(4560.0 - p.pad) and not me1.trail_ok(pos)                 # capped; no FVG trailing until partial #2
    step(ctx, sd, pos, tr, p, 3, 4)
    assert pos["stop"] == pytest.approx(4560.0 - p.pad)                                           # a newer LTF FVG / nothing moves it before partial #2
    # partial #2 (4580): 1 tick under the CE of the upper wick of the highest bar between the partials (bar 3: body top 4569, high 4571 -> CE 4570)
    tr.exits.append((ctx.idx[5], 4580.0, 3, "t2")); pos["left"] -= 3
    step(ctx, sd, pos, tr, p, 5)
    assert pos["stop"] == pytest.approx(4570.0 - p.tick) and me1.trail_ok(pos)
    # partial #3: the HTF top (4560) is lower - the stop never goes down
    tr.exits.append((ctx.idx[7], 4590.0, 1, "t3")); pos["left"] -= 1
    step(ctx, sd, pos, tr, p, 7)
    assert pos["stop"] == pytest.approx(4570.0 - p.tick)


def test_be_cap_htf_no_htf_array_is_plain_be():
    ctx = mkctx(flatrows(2, 4553.0) + [(4553, 4570, 4552, 4569)])
    p = pk(be_cap_htf=True)
    pos, tr, sd = mkpos(ctx, 1, 1, 4553.0, 4545.0, levels=(4570.0, 4590.0), fracs=(0.5, 0.5))
    fill(ctx, sd, pos, tr, p)
    assert pos["me1"]["htf_hi"] is None
    tr.exits.append((ctx.idx[2], 4570.0, 5, "t1")); pos["left"] -= 5
    step(ctx, sd, pos, tr, p, 2)
    assert pos["stop"] == pytest.approx(4553.0)


# --- D14-be-after-adr-fraction (14) ---------------------------------------------------------------------------------------------------------------

def test_be_adr_frac():
    hist = [pd.DataFrame({"open": 4000.0, "high": 4040.0, "low": 4000.0, "close": 4020.0}, index=pd.date_range(f"2026-06-{10 + k} 09:30", periods=3, freq="5min", tz="America/New_York")) for k in range(5)]
    ctx = mkctx([(4000, 4001, 3999, 4000.5), (4000.5, 4008, 4000, 4007.5), (4007.5, 4015.9, 4007, 4015.0), (4015.0, 4016.5, 4014.0, 4016.0)], hist=hist)
    p = pk(be_mode="adr_frac", be_adr=0.4)
    pos, tr, sd = mkpos(ctx, 1, 0, 4000.0, 3990.0, levels=(4100.0,))
    fill(ctx, sd, pos, tr, p)
    assert pos["me1"]["adr"] == pytest.approx(40.0)
    step(ctx, sd, pos, tr, p, 1, 2)
    assert pos["stop"] == 3990.0                                          # +8 (a partial would be here) and +15.9: not yet 0.4 x ADR5 = 16
    step(ctx, sd, pos, tr, p, 3)
    assert pos["stop"] == 4000.0 and pos["me1"]["adr_done"]


# --- X5-runner-stop-half-open-profit (16) ----------------------------------------------------------------------------------------------------------

def test_runner_leg_eq():
    ctx = mkctx(flatrows(3, 4077.0) + [(4077, 4078, 4076, 4077.0), (4077.0, 4079, 4072, 4078.0)])
    for kind, expect in (("leg_eq", 4068.75), ("half_profit", 4065.0 + 0.5 * (4077.0 - 4065.0))):
        p = pk(runner_stop=kind)
        pos, tr, sd = mkpos(ctx, 1, 0, 4065.0, 4058.0, levels=(4077.0, 4090.0), fracs=(0.8, 0.2), ext=4060.0)
        fill(ctx, sd, pos, tr, p)
        tr.exits.append((ctx.idx[3], 4077.0, 8, "t1")); pos["left"] = 2; pos["t1_done"] = True
        step(ctx, sd, pos, tr, p, 3)
        assert pos["stop"] == pytest.approx(expect) and pos["no_trail"] and not me1.trail_ok(pos)         # a later new FVG does not move it
        step(ctx, sd, pos, tr, p, 4)
        assert pos["stop"] == pytest.approx(expect)                                                        # once only
    # below the threshold (50 % off) nothing happens
    p = pk(runner_stop="leg_eq")
    pos, tr, sd = mkpos(ctx, 1, 0, 4065.0, 4058.0, levels=(4077.0, 4090.0), fracs=(0.5, 0.5), ext=4060.0)
    fill(ctx, sd, pos, tr, p)
    tr.exits.append((ctx.idx[3], 4077.0, 5, "t1")); pos["left"] = 5
    step(ctx, sd, pos, tr, p, 3)
    assert pos["stop"] == 4058.0


# --- X5-day-trade-stop-no-trail (17) --------------------------------------------------------------------------------------------------------------

def test_day_mode_stop(monkeypatch):
    pre = A_ROWS[:5]
    rows = pre + [(100.3, 103.0, 100.2, 102.9), (102.9, 103.0, 99.8, 100.1), (100.1, 100.5, 99.0, 99.5)]

    def go(**kw):
        tr, *_ = rf_run(day(rows, spike=True), history(), Params(**BASE, min_risk_pts=0.3, **kw), {570: dict(draw_up=104.0, draw_up_name="D_fvg", draw_dn=float("nan"), draw_dn_name="")})
        return tr[0]
    ref = go(trade_type="day", day_stop="wick_ce", be_on="t1")
    monkeypatch.setattr(me1, "day_pick", lambda ctx, sd, i, p, entry: True)
    auto = go(day_mode_auto=True, be_on="t1")
    pad = Params(**BASE).pad
    assert "day_trade" in auto.lv_tags and "day_auto" in auto.lv_tags
    assert auto.stop == pytest.approx(99.8 - pad) and auto.stop < ref.stop             # below the 08:30 wick CE (99.9) AND beyond the pre-release low (99.8), swept before the fill
    assert auto.exits[0][3] == "t1" and auto.exits[1][1] == pytest.approx(auto.stop)   # no breakeven, no trail: the initial stop
    full = go(day_mode_auto=True, be_on="t1", day_mode_size=1.0)
    assert full.stop == auto.stop and auto.shares in (full.shares // 2, full.shares // 2 + 1) and auto.shares < full.shares      # half the session size for the same stop distance
    monkeypatch.setattr(me1, "day_pick", lambda ctx, sd, i, p, entry: False)
    off = go(day_mode_auto=True, be_on="t1")
    assert "day_trade" not in off.lv_tags


def test_day_pick_conditions(monkeypatch):
    hist = [pd.DataFrame({"open": 4000.0, "high": 4040.0, "low": 4000.0, "close": 4020.0}, index=pd.date_range(f"2026-06-{10 + k} 09:30", periods=3, freq="5min", tz="America/New_York")) for k in range(5)]
    ctx = mkctx([(4000, 4004, 3999, 4003)] * 10, hist=hist, bias_row={"draw": 1})
    sd = ctx.sides_map[1]
    p = pk(htf_bias="draw")
    monkeypatch.setattr(tp3, "htf_draw", lambda ctx, sd, i, p, above, st: 4040.0)
    assert me1.day_pick(ctx, sd, 9, p, 4003.0) is True                                  # bias agrees, range 5 < 20, the draw is 37 away >= 30
    monkeypatch.setattr(tp3, "htf_draw", lambda ctx, sd, i, p, above, st: 4020.0)
    assert me1.day_pick(ctx, sd, 9, p, 4003.0) is False                                 # the draw is only 17 away (< 0.75 x ADR5 = 30)
    monkeypatch.setattr(tp3, "htf_draw", lambda ctx, sd, i, p, above, st: None)
    assert me1.day_pick(ctx, sd, 9, p, 4003.0) is False
    monkeypatch.setattr(tp3, "htf_draw", lambda ctx, sd, i, p, above, st: 4040.0)
    ctx.bias_row = {"draw": -1}
    assert me1.day_pick(ctx, sd, 9, p, 4003.0) is False                                 # the bias disagrees
    ctx2 = mkctx([(4000, 4030, 3999, 4003)] * 10, hist=hist, bias_row={"draw": 1})
    assert me1.day_pick(ctx2, ctx2.sides_map[1], 9, p, 4003.0) is False                 # the day has already moved 31 >= 0.5 x ADR5


def test_day_level_beyond_the_swept_pre_release_low():
    # 08:00-08:29 range low 3995; the 08:30 candle opens 4000 (low 3999); price swept 3995 before the fill: the stop goes beyond it
    rows = [(4000, 4001, 3995.5, 4000)] * 30 + [(4000, 4002, 3999, 4001)] + [(4001, 4001.5, 3994.0, 4000.5)] + [(4000.5, 4002, 4000, 4001.5)] * 3
    ctx = mkctx(rows, t0=480)
    sd = ctx.sides_map[1]
    assert ctx.t[30] == 510
    lvl_unswept = me1.day_level(ctx, sd, 30, 30, pk())
    assert lvl_unswept == pytest.approx(min(4000.0, (4000.0 + 3999.0) / 2))                       # min(open, the wick CE of the 08:30 candle)
    assert me1.day_level(ctx, sd, 30, 33, pk()) == pytest.approx(3995.5)                         # the pre-release low 3995.5 was swept (3994.0) before the fill: the stop level goes beyond that low


# --- X5-event-tight-lock-020 (18) ---------------------------------------------------------------------------------------------------------------

def test_event_eve_lock():
    from claude_hf.daytypes import events
    eve = next(d for d in (date(2023, 5, 2), date(2023, 6, 13), date(2023, 7, 25)) if "fomc" in events(d + pd.Timedelta(days=1)))
    rows = [(4105, 4106, 4104, 4105), (4105, 4108, 4104.5, 4107.5), (4107.5, 4110, 4107, 4109.5), (4109.5, 4116, 4109, 4115.5), (4115.5, 4118.5, 4112, 4118), (4118, 4119, 4117, 4118)]
    for d, expect in ((eve, True), (date(2023, 5, 23), False)):
        ctx = mkctx(rows, d=d)
        p = pk(event_eve_lock=True, stop_tick_pts=0.25)
        pos, tr, sd = mkpos(ctx, 1, 0, 4105.0, 4100.0, levels=(4118.0, 4140.0), fracs=(0.8, 0.2))
        fill(ctx, sd, pos, tr, p)
        tr.exits.append((ctx.idx[4], 4118.0, 8, "t1")); pos["left"] = 2; pos["t1_done"] = True
        step(ctx, sd, pos, tr, p, 4)
        if expect:
            assert pos["stop"] == pytest.approx(4112.0 + p.pad) and pos["no_trail"] and "event_lock" in tr.mgmt_tags      # above the nearest fresh FVG (4110-4112), not under it
        else:
            assert pos["stop"] == 4100.0 and not pos.get("no_trail")


# --- X5-trail-after-protected-gap-confirmed (19) --------------------------------------------------------------------------------------------

def _p_book(after):
    gap = [(4098, 4100, 4096, 4099.8), (4099.8, 4106, 4099.0, 4105), (4105, 4112, 4102, 4111)]                # the gap 4100-4102 (c1 high 4100, c3 low 4102); the post-gap swing high 4112
    return gap + [(4111, 4111.5, 4101, 4101.5)] + after


def test_trail_confirm():
    p = pk(trail_confirm=True)

    def run(after, stop=4090.0):
        ctx = mkctx(_p_book(after))
        pos, tr, sd = mkpos(ctx, 1, 3, 4101.0, stop, levels=(4130.0,), fvg_bottom=4100.0, fvg_top=4102.0, fvg_ce=4101.0)
        fill(ctx, sd, pos, tr, p)
        assert pos["me1"]["P"] == (4100.0, 4102.0, 2)
        step(ctx, sd, pos, tr, p, 4, len(ctx.t) - 1)
        return pos, tr
    # (a) a new gap 4104-4105 beyond P (no new extreme past 4112): the stop goes under P
    pos, tr = run([(4101.5, 4104.0, 4101.2, 4103.5), (4103.5, 4108.0, 4103.4, 4107.5), (4107.5, 4109.0, 4105.0, 4108.5)])
    assert pos["stop"] == pytest.approx(4100.0 - pk().pad) and pos["me1"]["P_ok"] and me1.trail_ok(pos)
    # (b) a run to a new extreme (4113 > 4112) with 4101 untouched: also confirmed
    pos, tr = run([(4101.5, 4103.0, 4101.2, 4102.5), (4102.5, 4106.0, 4102.0, 4105.5), (4105.5, 4113.0, 4105.0, 4112.5)])
    assert pos["stop"] == pytest.approx(4100.0 - pk().pad) and pos["me1"]["P_ok"]
    # a dip to 4099.75 first leaves the stop initial and disables P
    pos, tr = run([(4101.5, 4101.8, 4099.75, 4100.5), (4100.5, 4106.0, 4100.2, 4105.5), (4105.5, 4113.0, 4105.0, 4112.5)])
    assert pos["stop"] == 4090.0 and pos["me1"]["P"] is None and not pos["me1"]["P_ok"] and not me1.trail_ok(pos)
    # off: nothing
    ctx = mkctx(_p_book([(4101.5, 4104.0, 4101.2, 4103.5), (4103.5, 4108.0, 4103.4, 4107.5), (4107.5, 4109.0, 4105.0, 4108.5)]))
    pos, tr, sd = mkpos(ctx, 1, 3, 4101.0, 4090.0, levels=(4130.0,), fvg_bottom=4100.0, fvg_top=4102.0)
    fill(ctx, sd, pos, tr, pk())
    step(ctx, sd, pos, tr, pk(), 4, 6)
    assert pos["stop"] == 4090.0
