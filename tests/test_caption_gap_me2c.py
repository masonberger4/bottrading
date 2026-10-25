"""Caption-gap pass, package management_exits #2/3, part C: the unit tests of the warning / exit specs (management_partials_trailing_exits.md 90, 91, 93, 94, 95, 96, 98, 99, 100, 102, 103, 104, 107) -
the harness of test_caption_gap_me2a.py (hand-made one-minute books, the me2.py hooks called bar by bar). No platform-specific paths; nothing here needs market data."""
from datetime import date
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from mentorship import me1, me2, strategy as S
from mentorship.strategy import Params

from test_caption_gap_me1a import NY, flatrows, mkctx, mkpos, pk, reasons
from test_caption_gap_me2a import fill2, rung, step2


def A(level, top, bottom, kind="fvg"):
    return SimpleNamespace(level=level, top=top, bottom=bottom, kind=kind)


# --- X7-three-array-exit-trigger (90) -------------------------------------------------------------------------------------------------------------

PD3 = [A(4100.0, 4101.0, 4100.0, "vi"), A(4098.0, 4099.0, 4098.0), A(4095.0, 4096.0, 4094.5, "ob")]


def _pd3_run(mode, rows, arrays=PD3, **kw):
    ctx = mkctx([(4104, 4105, 4103, 4104)] + rows)
    p = pk(three_array_mode=mode, **kw)
    pos, tr, sd = mkpos(ctx, 1, 0, 4104.0, 4090.0, levels=(4140.0,))
    fill2(ctx, sd, pos, tr, p, pd3=list(arrays))
    step2(ctx, sd, pos, tr, p, 1, len(rows))
    return pos, tr


def test_three_array_modes():
    low = [(4104, 4104.5, 4095.5, 4097)]                                                   # a low of 4095.5 (into the OB body, above its far edge), the close above the MT
    assert reasons(_pd3_run("into", low)[1]) == ["pd3_into"]
    assert reasons(_pd3_run("trade", low)[1]) == [] and reasons(_pd3_run("close", low)[1]) == []
    close = [(4104, 4104.5, 4094.6, 4094.75)]                                              # a body close under the OB MT, no trade under the far edge
    pos, tr = _pd3_run("close", close)
    assert reasons(tr) == ["pd3_close"] and pos["left"] == 5                               # half off, once
    assert reasons(_pd3_run("into", close)[1]) == ["pd3_into"] and reasons(_pd3_run("trade", close)[1]) == []
    deep = [(4104, 4104.5, 4094.0, 4095.5)]                                                # a low of 4094 under the far edge 4094.5
    assert reasons(_pd3_run("trade", deep)[1]) == ["pd3_trade"]
    assert reasons(_pd3_run("", deep)[1]) == []
    # A3 close above A2 (078): the trigger moves to A2
    near = [A(4100.0, 4101.0, 4100.0, "vi"), A(4098.0, 4099.0, 4098.0), A(4097.5, 4098.5, 4096.5, "ob")]
    prox = [(4104, 4104.5, 4098.0, 4099)]
    assert reasons(_pd3_run("into", prox, near)[1]) == ["pd3_into"]                          # A3's body top 4098.5 is reached too; check the near switch decides on a bar that only reaches A2
    far_rows = [(4104, 4104.5, 4098.8, 4099.5)]
    assert reasons(_pd3_run("into", far_rows, near)[1]) == []                                # 4098.8 is above A3's top 4098.5 and A2's top 4099 is... not the trigger yet
    assert reasons(_pd3_run("into", far_rows, near, pd3_near_pts=1.0)[1]) == ["pd3_near"]    # with pd3_near_pts=1 the trigger is A2 (top 4099): price reaching A2 closes everything
    # the spec's own numbers: A3 at 4097.5, near=1, a low of 4098 exits - in every mode (the proximity exception is "close everything when price reaches A2")
    spec_near = [A(4100.0, 4101.0, 4100.0, "vi"), A(4098.0, 4099.0, 4098.0), A(4097.5, 4098.5, 4097.0, "ob")]
    for mode in ("trade", "close", "into"):
        assert reasons(_pd3_run(mode, [(4104, 4104.5, 4098.0, 4099)], spec_near, pd3_near_pts=1.0)[1]) == ["pd3_near"]
        assert reasons(_pd3_run(mode, [(4104, 4104.5, 4099.5, 4100)], spec_near, pd3_near_pts=1.0)[1]) == []        # A2 not reached
    # a warning when A2 is traded into
    pos, tr = _pd3_run("trade", [(4104, 4104.5, 4098.5, 4099)])
    assert "pd3_warn" in tr.mgmt_tags and not tr.exits
    # the sister index counts as one array already broken (item 98)
    pos, tr = _pd3_run("trade", [(4104, 4104.5, 4097.0, 4098)], arrays=PD3)
    assert not tr.exits
    ctx = mkctx([(4104, 4105, 4103, 4104), (4104, 4104.5, 4097.0, 4098)])
    p = pk(three_array_mode="trade")
    pos, tr, sd = mkpos(ctx, 1, 0, 4104.0, 4090.0, levels=(4140.0,))
    fill2(ctx, sd, pos, tr, p, pd3=list(PD3))
    pos["warn"] = 1                                                                        # #94's opposing-array warn is no sister breach (review fix: the sister counter is pos["sis_warn"])
    step2(ctx, sd, pos, tr, p, 1)
    assert reasons(tr) == []
    ctx = mkctx([(4104, 4105, 4103, 4104), (4104, 4104.5, 4097.0, 4098)])
    pos, tr, sd = mkpos(ctx, 1, 0, 4104.0, 4090.0, levels=(4140.0,))
    fill2(ctx, sd, pos, tr, p, pd3=list(PD3))
    pos["sis_warn"] = 1
    step2(ctx, sd, pos, tr, p, 1)
    assert reasons(tr) == ["pd3_trade"]


def test_pd3_arrays_from_the_bars():
    """The arrays are read from the bars at the fill: gaps / VIs / OB MTs between the stop and the fill, nearest first."""
    rows = [(4000, 4001, 3999, 4000.5), (4000.5, 4003, 4000, 4002), (4002, 4010, 4002.5, 4009), (4009, 4012, 4008, 4011), (4011, 4013, 4010, 4012), (4012, 4014, 4011, 4013)]
    ctx = mkctx(rows)
    sd = ctx.sides_map[1]
    pos, tr, sd = mkpos(ctx, 1, 5, 4013.0, 3995.0, levels=(4040.0,))
    out = me2._pd3_arrays(sd, pos, 4, pk(), 4013.0)
    assert len(out) <= 3 and all(a.bottom <= a.top for a in out) and [a.level for a in out] == sorted([a.level for a in out], reverse=True)


# --- X8-hold-above-broken-session-highs (91) -------------------------------------------------------------------------------------------------------

def _held_book(close):
    rows = [(4015, 4016, 4014, 4015)] * 40
    rows[0] = (4015, 4020, 4014, 4015)                                                    # the 09:30 bar's high 4020
    rows[23] = (4016, 4022, 4015, 4021)                                                    # the 09:53 swing high 4022
    for k in range(24, 30):
        rows[k] = (4021, 4021.5, 4020.5, 4021)                                              # price stays above the 09:30 high
    rows[30] = (4021, 4023, 4020.8, 4022.8)                                                # price trades above both
    rows[31] = (4022.8, 4023, 4021, close)
    return rows


@pytest.mark.parametrize("action", ["partial", "tighten"])
@pytest.mark.parametrize("close,acts", [(4021.5, True), (4022.25, False)])
def test_held_hi(action, close, acts):
    ctx = mkctx(_held_book(close))
    p = pk(held_hi_action=action)
    pos, tr, sd = mkpos(ctx, 1, 5, 4017.0, 4010.0, levels=(4040.0,))
    fill2(ctx, sd, pos, tr, p)
    step2(ctx, sd, pos, tr, p, 6, 31)
    assert pos["me2"].get("bh") == 4022.0
    if action == "partial":
        assert (reasons(tr) == ["lost_hi"] and pos["left"] == 5) == acts
    else:
        assert (pos["stop"] > 4010.0) == acts
        if acts:
            assert pos["stop"] == pytest.approx(min(4021.0 - p.pad, 4021.5 - p.tick)) and pos["stop_log"][-1][0] == "lost_hi"


# --- X8-fast-through-next-reference (93) -----------------------------------------------------------------------------------------------------------

REF_BASE = [(4030, 4031, 4029, 4030), (4030, 4036, 4029.5, 4035), (4035, 4039.5, 4034.5, 4039.2)]


def _ref_run(third, t1_done=False):
    ctx = mkctx(REF_BASE + [third, (4040, 4042, 4039, 4041)])
    p = pk(ref_speed_check=True)
    pos, tr, sd = mkpos(ctx, 1, 0, 4030.0, 4020.0, levels=(4038.75, 4060.0), fracs=(0.5, 0.5), kinds=["pool", "pool"])
    pos["t1_done"] = t1_done
    fill2(ctx, sd, pos, tr, p)
    step2(ctx, sd, pos, tr, p, 1, 4)
    return pos, tr


def test_ref_speed():
    pos, tr = _ref_run((4040, 4043, 4037, 4042))                                              # a break of 4038.75 with a gap above it (the next low 4037 is over the high 4036 of 2 bars back)
    assert not tr.exits and pos["left"] == 10
    pos, tr = _ref_run((4039, 4039.2, 4035, 4036.5))                                          # a break followed by a close back under it within 2 bars: halves before T1
    assert reasons(tr) == ["slow_ref_pare"] and pos["left"] == 5 and "slow_ref" in tr.mgmt_tags
    pos, tr = _ref_run((4039, 4039.2, 4035, 4036.5), t1_done=True)                              # ... and closes all after T1
    assert reasons(tr) == ["slow_ref"] and pos["left"] == 0


def test_ref_speed_fast_range():
    # a break whose range is >= 1.5 x the median of the last ranges is "ok" at once
    ctx = mkctx([(4030, 4031, 4029, 4030), (4030, 4031, 4029, 4030.5), (4030.5, 4031.5, 4029.5, 4031), (4031, 4045, 4030.5, 4044), (4044, 4045, 4034, 4036)])
    p = pk(ref_speed_check=True)
    pos, tr, sd = mkpos(ctx, 1, 0, 4030.0, 4020.0, levels=(4038.75, 4060.0), fracs=(0.5, 0.5), kinds=["pool", "pool"])
    fill2(ctx, sd, pos, tr, p)
    step2(ctx, sd, pos, tr, p, 1, 4)
    assert not tr.exits


# --- X8-opposing-array-torn-through (94) -----------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("second,ok", [((4104, 4107, 4103, 4106), True), ((4104, 4105, 4100.5, 4101), False)])
def test_opp_tear(second, ok):
    ctx = mkctx([(4100, 4101, 4099, 4100), (4100, 4105.5, 4101, 4104), second, (4106, 4107, 4105, 4106)])
    p = pk(opp_tear_check=True)
    pos, tr, sd = mkpos(ctx, 1, 0, 4100.0, 4090.0, levels=(4130.0,))
    fill2(ctx, sd, pos, tr, p, opp=[dict(near=4105.0, ce=4106.5, far=4108.0)], opp_done=set(), opp_win=None)
    step2(ctx, sd, pos, tr, p, 1, 3)
    assert pos["no_adds"] != ok and (pos.get("warn", 0) == 0) == ok
    assert not tr.exits                                                                    # the stop stays below the entry FVG


# --- X8-broken-fvg-edge-bump-once (95) -------------------------------------------------------------------------------------------------------------

def test_edge_bump():
    rows = [(4402, 4403, 4401, 4402.5), (4402.5, 4403, 4399.75, 4401), (4401, 4406, 4401, 4405), (4405, 4406, 4399.75, 4403), (4403, 4408, 4402.5, 4407)]
    ctx = mkctx(rows)
    ctx.equity = 100000.0
    p = pk(edge_bump_add=True, edge_bump_guard=True)
    pos, tr, sd = mkpos(ctx, 1, 0, 4402.0, 4390.0, levels=(4440.0,))
    fill2(ctx, sd, pos, tr, p, edge=4400.0, bumps=0, bump_on=False)
    step2(ctx, sd, pos, tr, p, 1)
    assert pos["me2"]["bumps"] == 1 and pos["me2"]["edge_add_armed"] and not pos["no_adds"]       # the first bump (4399.75) is an add location
    assert pos["add"] is not None and pos["add"]["px"] == 4400.0                                   # ... armed through the engine's add rules (setups.add_ok)
    pos2, tr2, sd2 = mkpos(ctx, 1, 0, 4402.0, 4390.0, levels=(4440.0,), no_adds=True)            # an add the engine would refuse (no_adds): armed nothing
    fill2(ctx, sd2, pos2, tr2, p, edge=4400.0, bumps=0, bump_on=False)
    step2(ctx, sd2, pos2, tr2, p, 1)
    assert pos2["add"] is None
    step2(ctx, sd, pos, tr, p, 2)
    assert not pos["no_adds"]
    step2(ctx, sd, pos, tr, p, 3)
    assert pos["me2"]["bumps"] == 2 and pos["no_adds"] and pos.get("levels_frozen")       # the second bump blocks the adds and freezes the ladder
    assert not tr.exits                                                                    # no exit: the stop is accepted
    # the add switch off: the first bump arms nothing
    pos, tr, sd = mkpos(ctx, 1, 0, 4402.0, 4390.0, levels=(4440.0,))
    pg = pk(edge_bump_guard=True)
    fill2(ctx, sd, pos, tr, pg, edge=4400.0, bumps=0, bump_on=False)
    step2(ctx, sd, pos, tr, pg, 1)
    assert not pos["me2"].get("edge_add_armed")


# --- X8-late-day-fvg-lost-hod-in (96) --------------------------------------------------------------------------------------------------------------

def _late_book(reclaim):
    t0 = 14 * 60 + 55
    rows = [(4095, 4096, 4094, 4095.5), (4095.5, 4108, 4095, 4107)] + [(4107, 4107.5, 4104, 4105)] * 4
    rows += [(4103, 4104, 4101, 4101.5), (4101.5, 4101.8, 4099.5, 4100), (4099.5, 4100.0, 4098.5, 4099)]         # a bearish gap 4100-4101 forms on the pullback from the highs (bar 8, 15:08)
    rows += [(4099.5, 4102, 4099, 4101.5 if reclaim else 4100.5)]
    rows += [(4101.5, 4101.8, 4099.2, 4099.75)]
    return mkctx(rows, t0=t0)


def test_late_fvg_flip():
    ctx = _late_book(True)
    p = pk(late_fvg_flip=True)
    pos, tr, sd = mkpos(ctx, 1, 0, 4095.0, 4085.0, levels=(4130.0,))
    fill2(ctx, sd, pos, tr, p)
    step2(ctx, sd, pos, tr, p, 1, 9)
    assert pos["me2"]["lf_sup"] and not tr.exits                                           # a close above the gap's top (4101): support
    step2(ctx, sd, pos, tr, p, 10)
    assert reasons(tr) == ["hod_in"] and pos["left"] == 0                                  # a close at 4099.75 under its bottom: the high of day is in
    # without the reclaim nothing exits
    ctx = _late_book(False)
    pos, tr, sd = mkpos(ctx, 1, 0, 4095.0, 4085.0, levels=(4130.0,))
    fill2(ctx, sd, pos, tr, p)
    step2(ctx, sd, pos, tr, p, 1, 10)
    assert not tr.exits
    # entries in the trade direction are blocked while price is under the gap
    assert me2.order_block(ctx, sd, 9, p, "PM", 4098.0) == "x_late_fvg"
    assert me2.order_block(ctx, sd, 9, pk(), "PM", 4098.0) is None
    short = ctx.sides_map[-1]
    assert me2.order_block(ctx, short, 9, p, "PM", short.x(4098.0)) is None
    # before last_hour[0] (15:00) the rule is silent
    ctx2 = _late_book(True)
    ctx2.t = ctx2.t - 60
    pos, tr, sd = mkpos(ctx2, 1, 0, 4095.0, 4085.0, levels=(4130.0,))
    fill2(ctx2, sd, pos, tr, p)
    step2(ctx2, sd, pos, tr, p, 1, 10)
    assert not tr.exits and "lf_sup" not in pos["me2"]


# --- X8-sister-index-breaker-hold (98) -------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("nq_close,warn", [(14999.0, 1), (15001.0, 0)])
def test_sister_breaker(nq_close, warn):
    es = [(4100, 4101, 4099, 4100.5), (4100.5, 4102, 4100, 4101), (4101, 4102, 4100.5, 4101.5)]
    ctx = mkctx(es)
    nq = [(15020, 15025, 15015, 15022), (15022, 15030, 15018, 15025), (15025, 15028, 15012, nq_close)]
    o, h, l, c = [np.array(x, float) for x in zip(*nq)]
    ps = S.Side(1, o, h, l, c, 1, 0.0)
    pctx = SimpleNamespace(start=0)
    ppos = pd.DataFrame({"x": 0}, index=ctx.idx)
    p = pk(sister_breaker_hold=True)
    pos, tr, sd = mkpos(ctx, 1, 0, 4100.0, 4090.0, levels=(4130.0,))
    fill2(ctx, sd, pos, tr, p, sis=(15000.0, 15010.0), sis_below=False)
    step2(ctx, sd, pos, tr, p, 1, 2, pctx=pctx, psides={1: ps}, ppos=ppos)
    assert pos.get("warn", 0) == warn
    # without sister data the switch is a no-op
    pos, tr, sd = mkpos(ctx, 1, 0, 4100.0, 4090.0, levels=(4130.0,))
    fill2(ctx, sd, pos, tr, p, sis=(15000.0, 15010.0), sis_below=False)
    step2(ctx, sd, pos, tr, p, 1, 2)
    assert pos.get("warn", 0) == 0


# --- X8-profitable-stall-exit (99) -----------------------------------------------------------------------------------------------------------------

def _hist(rng, monday=None):
    fr = [pd.DataFrame({"high": [4100.0], "low": [4100.0 - rng]}, index=pd.DatetimeIndex([pd.Timestamp(f"2026-06-{10 + k} 09:30", tz=NY)])) for k in range(4)]
    fr.append(pd.DataFrame({"high": [4095.0], "low": [4030.0]}, index=pd.DatetimeIndex([pd.Timestamp("2026-06-22 09:30", tz=NY)])))      # Monday of the week of D0 (2026-06-23, a Tuesday)
    return fr


def test_stall_at_htf():
    rows = [(4050, 4051, 4049, 4050), (4050, 4100, 4049.5, 4095)] + [(4095, 4096, 4094, 4095)] * 31
    cf = SimpleNamespace(at=lambda now, price, side: ["D"])
    ctx = mkctx(rows, hist=_hist(40.0), conf=cf)
    p = pk(stall_at_htf=True, stall_at_htf_bars=30)
    pos, tr, sd = mkpos(ctx, 1, 0, 4050.0, 4040.0, levels=(4150.0,))
    fill2(ctx, sd, pos, tr, p)
    step2(ctx, sd, pos, tr, p, 1, 31)
    assert not tr.exits
    step2(ctx, sd, pos, tr, p, 32)                                                          # 30 bars (2..31) without a new high, in profit, inside a daily array
    assert reasons(tr) == ["htf_stall"] and pos["left"] == 0
    # not inside an HTF array: nothing
    ctx = mkctx(rows, hist=_hist(40.0), conf=SimpleNamespace(at=lambda now, price, side: ["1h"]))
    pos, tr, sd = mkpos(ctx, 1, 0, 4050.0, 4040.0, levels=(4150.0,))
    fill2(ctx, sd, pos, tr, p)
    step2(ctx, sd, pos, tr, p, 1, 32)
    assert not tr.exits
    # a Wednesday, or a week range under 1.5 x ADR5: inactive
    ctx = mkctx(rows, hist=_hist(80.0), conf=cf)
    pos, tr, sd = mkpos(ctx, 1, 0, 4050.0, 4040.0, levels=(4150.0,))
    fill2(ctx, sd, pos, tr, p)
    step2(ctx, sd, pos, tr, p, 1, 32)
    assert not tr.exits
    ctx = mkctx(rows, hist=_hist(40.0), conf=cf, d=date(2026, 6, 24))
    pos, tr, sd = mkpos(ctx, 1, 0, 4050.0, 4040.0, levels=(4150.0,))
    fill2(ctx, sd, pos, tr, p)
    step2(ctx, sd, pos, tr, p, 1, 32)
    assert not tr.exits


def test_reversal_watch_week_state():
    from mentorship import backtest as B
    tue, wed, thu = date(2026, 6, 23), date(2026, 6, 24), date(2026, 6, 25)
    rows = [dict(date=tue, side="long", exit_reason="htf_stall", net=1.0)]
    assert me2.week_watch(rows, wed) == []                                                  # the next session is still running
    assert me2.week_watch(rows, thu) == ["long"]                                            # no new long by Wednesday close: Thursday longs are blocked
    assert me2.week_watch(rows + [dict(date=wed, side="long", exit_reason="t1", net=1.0)], thu) == []
    assert me2.week_watch(rows + [dict(date=wed, side="short", exit_reason="t1", net=1.0)], thu) == ["long"]
    assert B.week_state(rows, thu)["reversal_watch"] == ["long"] and "reversal_watch" not in B.week_state([dict(date=tue, side="long", exit_reason="t1", net=1.0)], thu)
    ctx = mkctx([(4100, 4101, 4099, 4100)], week={"reversal_watch": ["long"]})
    p = pk(stall_at_htf=True)
    assert me2.order_block(ctx, ctx.sides_map[1], 0, p, "AM", 4100.0) == "x_reversal_watch"
    assert me2.order_block(ctx, ctx.sides_map[-1], 0, p, "AM", -4100.0) is None
    assert Params(stall_at_htf=True).dw_needs_week and not Params().dw_needs_week


# --- X9-lethargic-or-choppy-trade (100) ------------------------------------------------------------------------------------------------------------

def test_chop_close():
    ctx = mkctx(flatrows(4, 4000.0, 1.0))
    p = pk(chop_close=True)
    pos, tr, sd = mkpos(ctx, 1, 0, 4000.0, 3990.0, levels=(4030.0,))
    fill2(ctx, sd, pos, tr, p)
    off = SimpleNamespace(on=False, on_at=None)
    assert not me2.chop_close(pos, tr, sd, ctx.idx[1], 4000.0, off, p, 0) and pos["left"] == 10
    before = SimpleNamespace(on=True, on_at=-1)                                             # turned on before the fill: not this trade's chop
    assert not me2.chop_close(pos, tr, sd, ctx.idx[1], 4000.0, before, p, 0)
    on = SimpleNamespace(on=True, on_at=1)
    assert me2.chop_close(pos, tr, sd, ctx.idx[2], 4000.0, on, p, 0) and reasons(tr) == ["chop_close"] and pos["left"] == 0
    # the session rule after the exit
    done, state = {"AM": False, "PM": False}, dict(reentered={})
    me2.after_close(pos, tr, done, "AM", state, p)
    assert done["AM"] is True and not state["reentered"]                                    # end_session
    done, state = {"AM": False, "PM": False}, dict(reentered={})
    pr = pk(chop_close=True, after_chop_exit="reentry_allowed")
    me2.after_close(pos, tr, done, "AM", state, pr)
    assert done["AM"] is False and state["reentered"]["AM"] is True                         # the next same-side setup is armed at the X13b half risk
    with pytest.raises(ValueError):
        Params(after_chop_exit="x")


# --- X9-071-move-away-from-up-close-pair (102) -----------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("after,block", [([(4010.8, 4010.9, 4010, 4010.5), (4010.5, 4010.9, 4009.8, 4010.2)], True), ([(4010.8, 4012, 4010, 4011.5), (4011.5, 4011.9, 4010.5, 4011)], False)])
def test_upclose_pair(after, block):
    rows = [(4010, 4010.5, 4008, 4008.5), (4009, 4009.5, 4006, 4006.5), (4006.5, 4007.5, 4006, 4007), (4007, 4011, 4006.8, 4010.8)] + after
    ctx = mkctx(rows)
    p = pk(upclose_pair_guard=True)
    pos, tr, sd = mkpos(ctx, 1, 2, 4007.0, 4000.0, levels=(4040.0,))
    fill2(ctx, sd, pos, tr, p)
    assert pos["me2"]["pair_ref"] == 4010.0                                                # the higher open of the last two consecutive down-close candles (the mirror of a short's lower candle)
    step2(ctx, sd, pos, tr, p, 3, 5)
    assert pos["no_adds"] is block and not tr.exits                                         # a stall only blocks adds - no exit, no widening


# --- X9-speed-after-fulcrum-break (103) ------------------------------------------------------------------------------------------------------------

def _fulcrum_run(rows):
    ctx = mkctx([(4010, 4011, 4009, 4010)] + rows)
    p = pk(fulcrum_speed_bars=5, sd_anchor="fulcrum")
    pos, tr, sd = mkpos(ctx, 1, 0, 4010.0, 4000.0, levels=(4020.0, 4030.0, 4050.0), fracs=(0.3, 0.4, 0.3), kinds=["pool", "sd_half", "sd_mm"])
    fill2(ctx, sd, pos, tr, p)
    step2(ctx, sd, pos, tr, p, 1, len(rows))
    return pos, tr


def test_fulcrum_speed():
    fast = [(4010, 4021, 4009.5, 4020.5), (4020.5, 4024, 4020, 4023), (4023, 4031, 4022, 4030.5), (4030.5, 4032, 4029, 4031), (4031, 4033, 4030, 4032), (4032, 4034, 4031, 4033)]
    pos, tr = _fulcrum_run(fast)                                                            # -0.5 SD (4030) reached on bar 3 does nothing extra
    assert not tr.exits
    slow = [(4010, 4021, 4009.5, 4020.5), (4020.5, 4024, 4020, 4023), (4023, 4025, 4022, 4024), (4024, 4026, 4023, 4025), (4025, 4027, 4024, 4026), (4026, 4028, 4025, 4026.5)]
    pos, tr = _fulcrum_run(slow)                                                            # five bars without reaching it close the first fraction (30 % of 10)
    assert reasons(tr) == ["fulcrum_slow"] and tr.exits[0][2] == 3 and pos["left"] == 7
    assert pos["stop"] == pytest.approx(4009.5 - pk().pad)                              # the stop under the break bar
    back = [(4010, 4021, 4009.5, 4020.5), (4020.5, 4022, 4018, 4019)]                       # a close back under the broken pool first
    pos, tr = _fulcrum_run(back)
    assert reasons(tr) == ["fulcrum_slow"]


# --- A13-breaker-far-edge-partial (104) ------------------------------------------------------------------------------------------------------------

def test_breaker_far_partial():
    rows = [(4403, 4404, 4402, 4403), (4403, 4407, 4402.5, 4406), (4406, 4410.25, 4405, 4409)]
    ctx = mkctx(rows)
    short = ctx.sides_map[-1]
    p = pk(breaker_far_partial=0.5)
    pos, tr, sd = mkpos(ctx, -1, 0, 4403.0, 4415.0, levels=(4380.0,))
    tr.bz_top, tr.bz_bottom = 4410.0, 4400.0
    fill2(ctx, sd, pos, tr, p)
    assert sd is short
    step2(ctx, sd, pos, tr, p, 1)
    assert not tr.exits
    step2(ctx, sd, pos, tr, p, 2)                                                           # a bar to 4410.25 closes 50 %, the stop stays at 4415
    assert reasons(tr) == ["bz_far"] and pos["left"] == 5 and pos["stop"] == sd.x(4415.0) and pos["no_adds"]
    assert tr.exits[0][1] == pytest.approx(4410.0)
    pos, tr, sd = mkpos(ctx, -1, 0, 4403.0, 4415.0, levels=(4380.0,))
    tr.bz_top, tr.bz_bottom = 4410.0, 4400.0
    fill2(ctx, sd, pos, tr, pk(breaker_far_partial=0.25))
    step2(ctx, sd, pos, tr, pk(breaker_far_partial=0.25), 1, 2)
    assert pos["left"] == 8                                                                # 25 % (2 of 10 units, lot-rounded down: 2)
    with pytest.raises(ValueError):
        Params(breaker_far_partial=1.0)


# --- new-small-fvg-last-line (107) -----------------------------------------------------------------------------------------------------------------

def test_small_fvg_linger():
    rows = [(4100, 4102, 4099, 4101), (4101, 4112, 4100.5, 4111), (4111, 4115, 4105, 4114), (4114, 4114.5, 4104, 4104.5), (4104.5, 4105, 4103, 4104), (4104, 4104.8, 4103.2, 4104.2), (4104.2, 4105.2, 4103.5, 4104.5)]
    ctx = mkctx(rows, tf=5)
    p = pk(small_fvg_linger=2)
    pos, tr, sd = mkpos(ctx, 1, 0, 4100.0, 4090.0, levels=(4150.0,))
    pos["t1_done"] = True
    fill2(ctx, sd, pos, tr, p, htf_hi=4123.0)
    step2(ctx, sd, pos, tr, p, 1, 4)
    assert "stop_cap" not in pos and not pos["no_adds"]                                    # two 5m bars inside the gap [4102, 4105]
    step2(ctx, sd, pos, tr, p, 5)                                                           # the third
    assert pos["no_adds"] and pos["stop_cap"] == 4123.0 and "small_fvg_linger" in tr.mgmt_tags
    assert me2.raise_to(pos, 4130.0, "trail", 4140.0, p) is False                          # a trail above the 4h FVG high is refused
    assert me2.capv(pos, 4130.0) == pos["stop"] and me2.capv(pos, 4120.0) == 4120.0
    assert me2.raise_to(pos, 4120.0, "trail", 4140.0, p) is True
    # a 5m close under the gap does it at once
    rows2 = rows[:4] + [(4104.5, 4104.6, 4100.5, 4101)]
    ctx = mkctx(rows2, tf=5)
    pos, tr, sd = mkpos(ctx, 1, 0, 4100.0, 4090.0, levels=(4150.0,))
    pos["t1_done"] = True
    fill2(ctx, sd, pos, tr, p, htf_hi=4123.0)
    step2(ctx, sd, pos, tr, p, 1, 4)
    assert pos["no_adds"] and pos["stop_cap"] == 4123.0
    # before T1 nothing
    pos, tr, sd = mkpos(ctx, 1, 0, 4100.0, 4090.0, levels=(4150.0,))
    fill2(ctx, sd, pos, tr, p, htf_hi=4123.0)
    step2(ctx, sd, pos, tr, p, 1, 4)
    assert not pos["no_adds"]
