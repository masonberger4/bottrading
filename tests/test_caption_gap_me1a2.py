"""Caption-gap pass, package management_exits #1/3, part A2: the unit and engine tests of the definitions_pd_arrays_structure.md specs 2, 17, 25, 30, 31, 40, 62, 63, 65, 83, 94, 106, 111, 196 (same
stub harness as test_caption_gap_me1a.py). The ladder / stop-lock specs are in test_caption_gap_me1a3.py."""
from types import SimpleNamespace

import numpy as np
import pytest

from mentorship import me1, strategy as S
from mentorship.strategy import Params

from test_review_fixes import BASE, day, history, run as rf_run
from test_caption_gap_es1a import C_ROWS, POST
from test_caption_gap_me1a import fill, flatrows, mkctx, mkpos, pk, reasons, step


# --- A11-bpr-retrace-allowance (2) --------------------------------------------------------------------------------------------------------------------

def _bpr_path():
    """026 style: a long at 4100, the BPR under it 4090-4096 (MT 4093): a wick to the MT (bar 3), then a wick on to the far edge (bar 4, low 4089.9), the bodies stay above."""
    return [(4100, 4101, 4099, 4100.5), (4100.5, 4102, 4099.5, 4101), (4101, 4102, 4099.8, 4100.8), (4100.8, 4101, 4093, 4099), (4099, 4100, 4089.9, 4098), (4098, 4099, 4097, 4098.5)]


@pytest.mark.parametrize("mode,expect", [("mt_body_close_abort", None), ("no_reentry", 3), ("ce_touch", 3), ("mt_warn_far_exit", 4), ("far_edge", 4)])
def test_bpr_limit_modes(mode, expect):
    ctx = mkctx(_bpr_path())
    p = pk(bpr_abort=True, bpr_limit=mode)
    pos, tr, sd = mkpos(ctx, 1, 1, 4100.0, 4088.0, levels=(4120.0,))
    fill(ctx, sd, pos, tr, p, me1_data=None if mode == "mt_body_close_abort" else dict(bpr=(4090.0, 4096.0, 4093.0)))
    step(ctx, sd, pos, tr, p, 2, 5)
    if expect is None:
        assert pos["left"] == 10 and not tr.exits                       # the built rule (a body close through the MT, the lvx exit in strategy) is not touched by me1
    else:
        assert reasons(tr) == ["bpr_" + mode] and tr.exits[0][0] == ctx.idx[expect]
    if mode == "mt_warn_far_exit":
        assert "bpr_warn" in tr.mgmt_tags


def test_bpr_limit_default_keeps_the_lvx_exit():
    import inspect
    src = inspect.getsource(S)
    assert 'if p.bpr_limit == "mt_body_close_abort":' in src and '_ME1.mark_tags(tags, "bpr"' in src


# --- A13-breaker-mt-trade-test (17) ------------------------------------------------------------------------------------------------------------------

def test_breaker_mt_trade_test():
    pos = dict(bz_mt=4053.25)
    assert me1.mt_exit_px(pk(), pos, 4054.0, 4053.0, 4054.5) is None                       # a wick two ticks under the MT, the body closes above: "close" does not exit
    assert me1.mt_exit_px(pk(), pos, 4054.0, 4053.0, 4053.0) == 4053.0                      # a body close under: the close
    assert me1.mt_exit_px(pk(breaker_mt_test="trade"), pos, 4054.0, 4052.75, 4054.5) == pytest.approx(4053.25)      # the print under the MT exits at the MT
    assert me1.mt_exit_px(pk(breaker_mt_test="trade"), pos, 4054.0, 4053.25, 4054.5) is None          # a touch is not a break
    assert me1.mt_exit_px(pk(breaker_mt_test="trade", mohawk_ticks=2), pos, 4054.0, 4052.9, 4054.5) is None      # the A4 tolerance (2 ticks)
    assert me1.mt_exit_px(pk(breaker_mt_test="trade", mohawk_ticks=2), pos, 4054.0, 4052.5, 4054.5) == pytest.approx(4052.75)


# --- A5-partial-fill-strength-read (25) --------------------------------------------------------------------------------------------------------------

def test_far_half_no_adds():
    # after the entry a BISI 4010-4014 forms; price then trades into its lower (far) half - past the CE 4012 - and the next add is blocked
    rows = [(4005, 4006, 4004, 4005), (4005, 4010, 4005, 4009), (4009, 4012, 4008, 4011), (4011, 4018, 4011, 4017), (4017, 4020, 4014, 4019), (4019, 4019.5, 4013.5, 4014), (4014, 4014.5, 4012.5, 4013)]
    ctx = mkctx(rows)
    p = pk(far_half_no_adds=True)
    pos, tr, sd = mkpos(ctx, 1, 0, 4005.0, 4000.0, levels=(4030.0,))
    fill(ctx, sd, pos, tr, p)
    assert any(g.i == 4 and g.bottom == 4012.0 and g.top == 4014.0 for g in sd.gaps)
    step(ctx, sd, pos, tr, p, 1, 5)
    assert not pos["no_adds"]                                                                  # the retrace stopped above the CE (4013)
    pos["add"] = {"px": 4011.0}
    step(ctx, sd, pos, tr, p, 6)
    assert pos["no_adds"] and pos["add"] is None and "strength_read" in tr.mgmt_tags


# --- A5-quadrants-any-gap-ladder (30) ----------------------------------------------------------------------------------------------------------------

def test_ce_exit_trade_vs_close():
    rows = list(C_ROWS[:6]) + [(100.5, 100.9, 100.0, 100.7), (100.7, 101.2, 100.6, 101.0)]
    out = {}
    for mode in ("close", "trade"):
        tr, *_ = rf_run(day(rows), history(), Params(**{**BASE, **POST, "ce_hold": True, "ce_exit": mode}), {})
        out[mode] = [(e[3], round(e[1], 2)) for e in tr[0].exits]
    assert out["close"][0][0] != "ce_trade" and out["trade"][0] == ("ce_trade", 100.1)         # the wick under the CE (100.1) exits only in "trade"; the close stayed above


# --- A5-reclaimed-fvg-full-revisit (31) ---------------------------------------------------------------------------------------------------------------

def test_fvg_bpr_backstop(monkeypatch):
    from mentorship import manage as MG
    rows = [(100, 100.5, 99.5, 100.2)] * 4 + [(100.2, 100.4, 99.2, 99.4), (99.4, 99.5, 98.8, 99.0), (99.0, 99.4, 98.7, 99.3), (99.3, 99.6, 99.0, 99.5)] + [(99.5, 99.8, 99.4, 99.7)] * 3
    ctx = mkctx(rows, tf=5)
    for backstop in (False, True):
        p = pk(fvg_abort=True, fvg_abort_mode="rule", fvg_bpr_backstop=backstop, fvg_abort_tf=5)
        pos, tr, sd = mkpos(ctx, 1, 3, 100.0, 98.0, levels=(110.0,), fvg_bottom=99.7, fvg_ce=99.85, fvg_top=100.0)
        monkeypatch.setattr(sd, "bprs", lambda *a, **k: [SimpleNamespace(i=1, bottom=99.2, top=99.7, mid=99.45)])
        fill(ctx, sd, pos, tr, p)
        for i in range(4, len(rows)):
            if pos["left"]:
                pos["best"] = max(pos["best"], float(sd.h[i]))
                MG.exits(ctx, sd, pos, tr, i, ctx.idx[i], p, {})
        if backstop:
            assert pos["me1"].get("bpr_back") == pytest.approx(99.45) and pos["lvx"]["bpr_abort"] == (pytest.approx(99.45), False) and "abort" not in reasons(tr)
        else:
            assert "abort" in reasons(tr)                                                       # the FVG far-edge rule exits (a close under 99.7, then a print under the armed low)


# --- A9-broken-vi-retrace-midpoint (40) --------------------------------------------------------------------------------------------------------------

def test_vi_mid_exit():
    base = [(4002, 4003, 4001, 4002.5)] * 2

    def run(after):
        ctx = mkctx(base + after)
        p = pk(vi_mid_exit=True)
        pos, tr, sd = mkpos(ctx, 1, 1, 4002.0, 3994.0, levels=(4020.0,), leg=(3995.0, 4005.0), kind="vi")
        fill(ctx, sd, pos, tr, p)
        step(ctx, sd, pos, tr, p, 2, len(ctx.t) - 1)
        return tr
    stay = [(4001, 4001.5, 3999.5, 4000.2), (4000.2, 4000.4, 3999.6, 4000.0), (4000.0, 4000.3, 3999.7, 4000.1), (4000.1, 4000.3, 3999.8, 4000.0)]       # a touch of the midpoint (4000)... no close back above it?
    stay = [(4001, 4001.5, 3999.5, 3999.8), (3999.8, 4000.0, 3999.4, 3999.6), (3999.6, 3999.9, 3999.3, 3999.7), (3999.7, 3999.9, 3999.5, 3999.8)]            # ... closes stay under the midpoint
    assert reasons(run(stay)) == ["vi_mid"]
    back = [(4001, 4001.5, 3999.5, 3999.8), (3999.8, 4001.8, 3999.7, 4001.5), (4001.5, 4002.0, 4001.0, 4001.8)]           # the next bar closes back above: rejected immediately
    assert reasons(run(back)) == []
    assert reasons(run([(4001, 4003, 3999.5, 4002.0)] + stay)) == []                                       # the touch candle itself rejects (closes above)


# --- A8-rip-through-ce-signature (62) ----------------------------------------------------------------------------------------------------------------

def _opp_gap_rows():
    """A long at 4100 with a bearish FVG 4105-4107 (CE 4106) above it, formed before the fill."""
    return [(4112, 4113, 4107, 4108), (4108, 4108, 4100, 4101), (4101, 4105, 4099, 4104.5), (4104.5, 4104.6, 4099.8, 4100.0)]


def test_rip_through_stall_and_rip():
    stall = [(4100, 4105.7, 4099.9, 4105.6), (4105.6, 4106.5, 4105.4, 4106.2), (4106.2, 4106.6, 4105.5, 4106.0), (4106.0, 4106.4, 4105.6, 4106.1)]
    ctx = mkctx(_opp_gap_rows() + stall)
    p = pk(rip_through=True)
    pos, tr, sd = mkpos(ctx, 1, 3, 4100.0, 4096.0, levels=(4115.0,))
    fill(ctx, sd, pos, tr, p)
    assert pos["me1"]["rip_gap"] == (4105.0, 4107.0, 4106.0)
    pos["add"] = {"px": 4102.0}
    step(ctx, sd, pos, tr, p, 4, 7)
    assert "stall" in tr.mgmt_tags and pos["no_adds"] and pos["add"] is None and reasons(tr) == ["stall_partial"] and tr.exits[0][2] == 5
    rip = [(4100, 4105.5, 4099.9, 4105.2), (4105.2, 4108.0, 4105.0, 4107.8)]
    ctx = mkctx(_opp_gap_rows() + rip)
    pos, tr, sd = mkpos(ctx, 1, 3, 4100.0, 4096.0, levels=(4115.0,))
    fill(ctx, sd, pos, tr, p)
    step(ctx, sd, pos, tr, p, 4, 5)
    assert "rip" in tr.mgmt_tags and not tr.exits and not pos["no_adds"]


# --- X9-entry-fvg-immediate-rejection (63) ------------------------------------------------------------------------------------------------------------

def test_fvg_full_fill_void_helpers():
    ctx = mkctx([(100, 100.5, 99.5, 100.2)] * 4 + [(100.2, 100.3, 99.6, 99.8)] + [(99.8, 100.1, 99.7, 100.0)])
    sd = ctx.sides_map[1]
    pend = dict(entry_kind="fvg", fvg_bottom=99.7, i=3)
    assert me1.void_pending(pend, sd, 6) is True                        # bar 4 (after the arming bar 3) printed 99.6 < 99.7: the order is void
    assert me1.void_pending(dict(pend, i=4), sd, 6) is False            # only bars after the arming bar count
    assert me1.void_pending(dict(pend, entry_kind="ob_pre"), sd, 6) is False and me1.void_pending(dict(pend, fvg_bottom=99.5), sd, 6) is False


def test_fvg_full_fill_void_through_the_engine():
    rows = list(C_ROWS)
    rows[5] = (101.6, 101.7, 99.7, 100.5)                                # the fill bar also trades through the FVG's far edge (99.8)
    on, off = [rf_run(day(rows), history(), Params(**{**BASE, **POST, "fvg_full_fill_void": f}), {})[0] for f in (True, False)]
    assert [e[3] for e in on[0].exits] == ["fvg_void"] and on[0].exits[0][1] == pytest.approx(99.8)
    assert off and "fvg_void" not in [e[3] for e in off[0].exits]


def test_fvg_full_fill_void_after_the_fill_bar():
    rows = [(100, 100.5, 99.5, 100.2)] * 3 + [(100.2, 100.3, 100.0, 100.1), (100.1, 100.4, 100.0, 100.3), (100.3, 100.4, 99.6, 100.2), (100.2, 100.4, 100.0, 100.3)]
    ctx = mkctx(rows)
    p = pk(fvg_full_fill_void=True)
    pos, tr, sd = mkpos(ctx, 1, 3, 100.1, 98.0, levels=(110.0,), fvg_bottom=99.7, fvg_ce=99.9, fvg_top=100.1)
    fill(ctx, sd, pos, tr, p)
    step(ctx, sd, pos, tr, p, 4, 6)
    assert reasons(tr) == ["fvg_void"] and tr.exits[0][1] == 99.7 and tr.exits[0][0] == ctx.idx[5]
    pos, tr, sd = mkpos(ctx, 1, 3, 100.1, 98.0, levels=(110.0,), fvg_bottom=99.7, fvg_ce=99.9, fvg_top=100.1)
    fill(ctx, sd, pos, tr, pk())
    step(ctx, sd, pos, tr, pk(), 4, 6)
    assert not tr.exits


# --- L4-resistance-is-delivery-speed (65) -----------------------------------------------------------------------------------------------------------

def test_resistance_speed_tag():
    fast = rf_run(day(C_ROWS), history(), Params(**{**BASE, **POST, "resistance_def": "speed"}), {})[0]
    assert fast[0].resist_speed == "low"                              # T1 (103.5) printed on the 3rd bar of the trade (fill bar 09:55, T1 at 10:05)
    slow = rf_run(day(C_ROWS), history(), Params(**{**BASE, **POST, "resistance_def": "speed", "resist_speed_bars": 2}), {})[0]
    assert slow[0].resist_speed == "high"
    plain = rf_run(day(C_ROWS), history(), Params(**{**BASE, **POST}), {})[0]
    assert plain[0].resist_speed == ""


# --- A8-ifvg-15m-body-failure (83) ------------------------------------------------------------------------------------------------------------------

def test_ifvg_fail_tf():
    # a 1m body close under the IFVG's edge (100) at bar 5 keeps the trade at 15; the 15m candle (09:30-09:45) closes below it at bar 14 and exits
    rows = [(100.5, 100.8, 100.2, 100.6)] * 5 + [(100.6, 100.7, 99.5, 99.8)] + [(99.8, 100.4, 99.7, 100.2)] * 8 + [(100.2, 100.3, 99.4, 99.7)] + [(99.7, 99.9, 99.5, 99.8)] * 3
    ctx = mkctx(rows, t0=570)
    p = pk(ifvg_fail_tf=15)
    pos, tr, sd = mkpos(ctx, 1, 1, 100.5, 99.0, levels=(110.0,))
    fill(ctx, sd, pos, tr, p, me1_data=dict(ifvg15=100.0))
    step(ctx, sd, pos, tr, p, 2, 13)
    assert pos["left"] == 10                                           # the 1m closes under 100 at bar 5 do not count
    step(ctx, sd, pos, tr, p, 14)
    assert reasons(tr) == ["ifvg_fail"] and ctx.t[14] + 1 == 585


# --- A6-breakaway-by-refusal (94) -------------------------------------------------------------------------------------------------------------------

def test_refusal_breakaway():
    ctx = mkctx(flatrows(8))
    p = pk(refusal_breakaway=True)
    pos, tr, sd = mkpos(ctx, 1, 1, 4000.0, 3990.0, levels=(4100.0,))
    fill(ctx, sd, pos, tr, p)
    assert me1.trail_ok(pos)
    me1.add_missed(pos, p)
    assert me1.trail_ok(pos) and not pos.get("breakaway_refusal")
    me1.add_missed(pos, p)
    assert not me1.trail_ok(pos) and pos["breakaway_refusal"] and "breakaway_refusal" in tr.mgmt_tags         # two missed adds switch the trail off
    pos2, tr2, sd2 = mkpos(ctx, 1, 1, 4000.0, 3990.0, levels=(4100.0,))
    fill(ctx, sd2, pos2, tr2, pk())
    me1.add_missed(pos2, pk())
    me1.add_missed(pos2, pk())
    assert me1.trail_ok(pos2)


# --- new-ignore-dojis (106) -------------------------------------------------------------------------------------------------------------------------

def test_dojis_against_the_position_do_not_exit():
    dojis = [(101.0, 101.3, 100.7, 101.0), (101.0, 101.2, 100.8, 100.95), (100.95, 101.3, 100.7, 101.05)] * 4         # indecision candles around the entry: no body, both wicks
    tr = rf_run(day(list(C_ROWS[:6]) + dojis, tail=101.0), history(), Params(**{**BASE, **POST}), {})[0]
    assert len(tr) == 1 and [e[3] for e in tr[0].exits][-1] in ("eod", "am_exit") and not any(e[3] in ("stop", "stop_gap", "be", "reverse") for e in tr[0].exits)      # no exit and no flip on a doji


# --- B6-intraday-iof (111) --------------------------------------------------------------------------------------------------------------------------

def test_iof_intraday_exit():
    rows = [(4000, 4001, 3999, 4000.5), (4000.5, 4006, 4000.4, 4005.5), (4005.5, 4006, 4003, 4003.5), (4003.5, 4007, 4003.4, 4006.5), (4006.5, 4006.8, 4004, 4005.0)]
    ctx = mkctx(rows)
    p = pk(iof_intraday_exit=True)
    pos, tr, sd = mkpos(ctx, 1, 0, 4000.0, 3990.0, levels=(4100.0,))
    fill(ctx, sd, pos, tr, p)
    step(ctx, sd, pos, tr, p, 1, 3)
    assert pos["left"] == 10 and pos["me1"]["iof_open"] == 4005.5                         # the support: the open of the newest down-close candle (bar 2 opened 4005.5)
    step(ctx, sd, pos, tr, p, 4)                                                              # bar 4 closes 4005.0 < 4005.5: a body close under the open of the down-close candle
    assert reasons(tr) == ["iof_fail"]
    pos, tr, sd = mkpos(ctx, 1, 0, 4000.0, 3990.0, levels=(4100.0,))
    fill(ctx, sd, pos, tr, pk())
    step(ctx, sd, pos, tr, pk(), 1, 4)
    assert pos["left"] == 10                                                                  # off: nothing


# --- new-position-trade-grading-fib (196, spec only) ---------------------------------------------------------------------------------------------------

def test_pos_trail_40_20():
    lows = list(np.arange(100.0, 160.0))             # 60 rising daily lows
    highs = [x + 3 for x in lows]
    assert me1.pos_trail(lows, highs, 1, 100.0, 200.0, 120.0) == min(lows[-40:])           # before 50 % of the way: the 40-day low
    assert me1.pos_trail(lows, highs, 1, 100.0, 200.0, 160.0) == min(lows[-20:])           # past it: the 20-day low
    assert me1.pos_trail(lows, highs, -1, 100.0, 0.0, 40.0) == max(highs[-20:])             # a short mirrors it
    assert me1.pos_trail(lows, highs, 1, 100.0, 200.0, 140.0, switch_frac=0.3) == min(lows[-20:])
