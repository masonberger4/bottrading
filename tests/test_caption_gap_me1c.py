"""Caption-gap pass, package management_exits #1/3, review fixes: the tests of the round-1 review findings (PRE8 cut under hold_through_0830, add_missed only for a pure time-out while price ran,
the T9 PM-entry extension / event flat / AM-leg low, the full-pull opposing-FVG breakeven and the BE caps, the IFVG heavy array, the strict IOF, the rip CE trade-through / wick objects, the
best-case recompute / resting check, the Thursday block for the rest of the day). Same stub harness as test_caption_gap_me1a.py; nothing here needs market data."""
from datetime import date

import pytest

from mentorship import me1, strategy as S, study
from mentorship.strategy import Params
from dataclasses import dataclass as _oa_dc


@_oa_dc
class Params(Params):   # OA1029 Q92: these tests exercise other rules; the order-block narrative gate (default on) leaves them no trades
    ob_need_narrative: bool = False

from test_caption_gap_me1a import D0, fill, flatrows, mkctx, mkpos, pk, reasons, step
from test_caption_gap_me1a2 import _opp_gap_rows
from test_caption_gap_me1a3 import _opp_book


# --- N5-hold-through-0830: the PRE8 cut ------------------------------------------------------------------------------------------------------------------

def test_pre8_cut_stays_at_the_release_even_when_the_position_is_held():
    from claude_hf.daytypes import events
    ppi = next(d for d in (date(2023, 5, 11), date(2023, 6, 14), date(2023, 7, 14)) if "ppi" in events(d))
    for kw in ({}, dict(hold_through_0830=True), dict(hold_through_0830=True, no_entry_0825=False)):
        assert me1.pre8_cut(ppi, pk(**kw)) == 510                                  # nothing fills on or after the 08:30 bar, held position or not
    assert me1.pre8_cut(D0, pk(hold_through_0830=True)) == 570                    # no release: the old 09:30 cut
    assert me1.pre8_cut(ppi, pk(pre_flat_0830=False, hold_through_0830=False)) == 570      # (OA1029 Q142: the default holds through)
    assert me1.pre8_cut(ppi, pk(pre_flat_0830=False, am_from_0830=True)) == 510
    assert me1.flat_0830(ppi, pk(hold_through_0830=True)) is False                # ... while the open position is held (the Ma Deuce / SB path)
    assert Params().hold_through_0830 is True                                      # OA1029 Q142: the experienced hold is the default (pre-09:30 test models only; no_entry_0825 stays)


# --- A6-breakaway-by-refusal -----------------------------------------------------------------------------------------------------------------------------

def test_add_missed_counts_only_a_time_out_while_price_ran_away():
    ctx = mkctx(flatrows(8))
    p = pk(refusal_breakaway=True)
    pos, tr, sd = mkpos(ctx, 1, 1, 4000.0, 3990.0, levels=(4100.0,))
    fill(ctx, sd, pos, tr, p)
    a = {"px": 3996.0, "q": 2, "i": 2}
    pos["best"] = 4001.0
    me1.add_missed(pos, p, a)                                                       # price did not run (best 4001 < entry + 4): not a refusal
    me1.add_missed(pos, p, a)
    assert pos["me1"]["miss"] == 0 and me1.trail_ok(pos)
    pos["best"] = 4005.0                                                            # ran 5 pts away from an add 4 pts below the entry
    me1.add_missed(pos, p, a)
    assert pos["me1"]["miss"] == 1 and me1.trail_ok(pos)
    me1.add_missed(pos, p, a)
    assert pos["breakaway_refusal"] and not me1.trail_ok(pos)


def test_strategy_passes_only_a_pure_time_out():
    import inspect
    src = inspect.getsource(S)
    assert "a_time_ and not a_oth_" in src                                          # the hold-break / chop / partial / cut / late-cutoff cancels never reach add_missed


# --- T9-strong-am-no-lunch-retrace ---------------------------------------------------------------------------------------------------------------------

def _day_rows(lunch_low=4032.0, pm_break=True, overnight=None):
    """Optional overnight bars, a 09:30 -> 12:00 rally 4000 -> 4040, a lunch (12:00-13:00) around 4036 with the given low, then PM bars (13:00 on) that break the lunch high or not."""
    rows = []
    if overnight is not None:
        rows += [(overnight, overnight + 0.5, overnight - 0.5, overnight)] * 5
    for k in range(150):
        v = 4000 + 40 * (k / 150)
        rows.append((v, v + 0.5, v - 0.5, v))
    for k in range(60):
        rows.append((4036, 4036.5, lunch_low if k == 30 else 4035.5, 4036))
    for k in range(20):
        v = 4037 if (pm_break and k >= 5) else 4036
        rows.append((v, v + (1.5 if pm_break and k == 5 else 0.5), v - 0.5, v))
    return rows


def test_lunch_ext_pm_entry_after_the_lunch_high_break():
    p = pk(no_lunch_retrace_hold=True)
    rows = _day_rows()
    ctx = mkctx(rows)
    sd = ctx.sides_map[1]
    n = len(rows)
    assert me1.lunch_ext(ctx, sd, n - 1, p) is True                                 # lunch low retraced 10 %, the PM broke the lunch high
    assert me1.lunch_ext(ctx, sd, 150 + 61, p) is False                             # right after 13:00: no break yet
    assert me1.lunch_ext(ctx, sd, n - 1, pk()) is False                             # switch off
    ctx2 = mkctx(_day_rows(lunch_low=4010.0))
    assert me1.lunch_ext(ctx2, ctx2.sides_map[1], len(ctx2.o) - 1, p) is False     # a 75 % lunch retrace
    ctx3 = mkctx(_day_rows(pm_break=False))
    assert me1.lunch_ext(ctx3, ctx3.sides_map[1], len(ctx3.o) - 1, p) is False     # the lunch high is never broken
    # the mirror: a falling day, the short side
    sdn = ctx.sides_map[-1]
    assert me1.lunch_ext(ctx, sdn, n - 1, p) is False                               # side space: no rally for the short side


def test_am_leg_is_the_0930_leg_not_the_overnight_low():
    """An overnight low far below the 09:30 low must not enlarge the leg (the lunch retrace is measured against the 09:30 -> 12:00 leg: 50 % here, not 14 %)."""
    p = pk(no_lunch_retrace_hold=True)
    rows = _day_rows(lunch_low=4020.0, overnight=3900.0)
    ctx = mkctx(rows, t0=570 - 5)
    sd = ctx.sides_map[1]
    pos, tr, _ = mkpos(ctx, 1, 8, 4001.0, 3995.0, levels=(4100.0,))
    fill(ctx, sd, pos, tr, p)
    i = 5 + 150 + 60 - 1
    assert me1.am_exit_hold(ctx, sd, pos, tr, 5 + 149, ctx.idx[5 + 149], p, 720) is True      # the 12:00 close: waits
    assert me1.am_exit_hold(ctx, sd, pos, tr, i, ctx.idx[i], p, 720) is False and pos["me1"]["lunch"] == "no"


def test_am_exit_hold_never_overrides_an_event_flat():
    p = pk(no_lunch_retrace_hold=True)
    rows = _day_rows()
    ctx = mkctx(rows)
    sd = ctx.sides_map[1]
    pos, tr, _ = mkpos(ctx, 1, 2, 4001.0, 3995.0, levels=(4100.0,))
    fill(ctx, sd, pos, tr, p)
    assert me1.am_exit_hold(ctx, sd, pos, tr, 149, ctx.idx[149], p, 690, ev_flat=True) is False
    assert me1.am_exit_hold(ctx, sd, pos, tr, 149, ctx.idx[149], p, 720) is True


# --- X4-be-without-partials / BE caps ---------------------------------------------------------------------------------------------------------------------

def test_full_pull_uses_the_opposing_fvg_breakeven():
    assert me1.bemode(pk()) == "partial" and me1.bemode(pk(exit_mode2="full_pull")) == "through_opposing_fvg"
    assert me1.bemode(pk(exit_mode2="full_pull", be_mode="adr_frac")) == "adr_frac" and me1.any_on(pk(exit_mode2="full_pull"))
    p = pk(exit_mode2="full_pull")
    ctx = mkctx(_opp_book() + [(4100, 4106.5, 4099.9, 4106.0), (4106.0, 4107.5, 4105.5, 4107.2), (4107.2, 4108, 4106.5, 4107.5)])
    pos, tr, sd = mkpos(ctx, 1, 3, 4100.0, 4098.0, levels=(4115.0,))
    fill(ctx, sd, pos, tr, p)
    step(ctx, sd, pos, tr, p, 4)
    assert pos["stop"] == 4098.0
    step(ctx, sd, pos, tr, p, 5)
    assert pos["stop"] == pytest.approx(4100.0)


def test_be_raise_is_capped_under_the_close():
    # the print through the far edge reverses and closes BELOW the entry: the stop may not sit above the market
    rows = _opp_book() + [(4100, 4107.5, 4098.5, 4099.0)]
    ctx = mkctx(rows)
    p = pk(be_mode="through_opposing_fvg")
    pos, tr, sd = mkpos(ctx, 1, 3, 4100.0, 4097.0, levels=(4115.0,))
    fill(ctx, sd, pos, tr, p)
    step(ctx, sd, pos, tr, p, 4)
    assert pos["stop"] <= 4099.0 - p.tick + 1e-9 and pos["stop"] > 4097.0
    ctx2 = mkctx(flatrows(3) + [(4000, 4003, 3999.6, 4002.0)])
    p2 = pk(be_mode="adr_frac", be_adr=0.1)
    pos2, tr2, sd2 = mkpos(ctx2, 1, 1, 4000.0, 3990.0, levels=(4100.0,))
    fill(ctx2, sd2, pos2, tr2, p2, me1_data=None)
    pos2["me1"]["adr"] = 20.0
    step(ctx2, sd2, pos2, tr2, p2, 3)
    assert pos2["stop"] == pytest.approx(4000.0) and tr2.exits == []             # avg itself (no pad / cost), under the close


# --- B6-untouched-premium-arrays-heavy: the IFVG counts; the partial goes at the CE touch ------------------------------------------------------------------

def test_heavy_partial_at_the_ce_touch_and_the_entry_gap_is_not_an_array():
    rows = [(4020, 4021, 4019, 4020), (4020, 4021, 4012, 4013), (4013, 4014, 4009, 4010), (4010, 4010.5, 4009.5, 4010)]
    ctx = mkctx(rows)
    pos, tr, sd = mkpos(ctx, 1, 3, 4010.0, 4000.0, levels=(4040.0,), fracs=(1.0,))
    p = pk(heavy_gauge=True)
    fill(ctx, sd, pos, tr, p)
    d = pos["me1"]
    assert all(not (abs(b - pos["fvg_bottom"]) < 1e-9 and abs(t - pos["fvg_top"]) < 1e-9) for b, t, _ in d["arrs"])      # the entry gap is excluded by its own edges
    d["arrs"] = [(4012.0, 4016.0, 4014.0)]
    ctx.o = ctx.o                                                                    # (stub)
    rows2 = rows + [(4015.0, 4016, 4013.0, 4015.5)]
    ctx2 = mkctx(rows2)
    pos2, tr2, sd2 = mkpos(ctx2, 1, 3, 4010.0, 4000.0, levels=(4040.0,), fracs=(1.0,))
    fill(ctx2, sd2, pos2, tr2, p)
    pos2["me1"]["arrs"] = [(4012.0, 4016.0, 4014.0)]
    step(ctx2, sd2, pos2, tr2, p, 4)
    assert tr2.exits and tr2.exits[0][3] == "heavy_scale" and tr2.exits[0][1] == pytest.approx(4014.0)        # at the CE (the open 4015 is above it), not at the 4015.5 close


# --- B6-intraday-iof strict ----------------------------------------------------------------------------------------------------------------------------------

def test_iof_strict_support_must_lead_to_a_new_high():
    rows = [(4000, 4001, 3999, 4000.5), (4000.5, 4006, 4000.4, 4005.5), (4005.5, 4006, 4003, 4003.5), (4003.5, 4005.5, 4003.4, 4005.6), (4005.6, 4005.9, 4005.5, 4005.6),
            (4005.6, 4005.9, 4005.5, 4005.7), (4005.7, 4005.9, 4005.5, 4005.6)]
    ctx = mkctx(rows)
    p = pk(iof_intraday_exit=True, iof_strict=True, iof_tol_bars=3)
    pos, tr, sd = mkpos(ctx, 1, 0, 4000.0, 3990.0, levels=(4100.0,))
    fill(ctx, sd, pos, tr, p)
    step(ctx, sd, pos, tr, p, 1, 6)
    assert reasons(tr) == ["iof_fail"] and tr.exits[0][0] == ctx.idx[5]             # the support (bar 2, high 4006) led to no new high within 3 bars
    # the same book without the strict switch holds
    pos, tr, sd = mkpos(ctx, 1, 0, 4000.0, 3990.0, levels=(4100.0,))
    fill(ctx, sd, pos, tr, pk(iof_intraday_exit=True))
    step(ctx, sd, pos, tr, pk(iof_intraday_exit=True), 1, 6)
    assert pos["left"] == 10
    # a new high within the tolerance keeps it
    rows2 = rows[:4] + [(4005.6, 4007.0, 4005.5, 4006.8)] + rows[5:]
    ctx2 = mkctx(rows2)
    pos, tr, sd = mkpos(ctx2, 1, 0, 4000.0, 3990.0, levels=(4100.0,))
    fill(ctx2, sd, pos, tr, p)
    step(ctx2, sd, pos, tr, p, 1, 6)
    assert pos["left"] == 10
    # a minimum body: a one-tick down-close is no support
    rows3 = [(4000, 4001, 3999, 4000.5), (4000.5, 4006, 4000.4, 4005.5), (4005.5, 4006, 4005.0, 4005.25), (4005.25, 4007, 4005.2, 4006.8)]
    ctx3 = mkctx(rows3)
    q = pk(iof_intraday_exit=True, iof_min_body_ticks=4)
    pos, tr, sd = mkpos(ctx3, 1, 0, 4000.0, 3990.0, levels=(4100.0,))
    fill(ctx3, sd, pos, tr, q)
    step(ctx3, sd, pos, tr, q, 1, 3)
    assert pos["me1"]["iof_open"] is None


# --- A8-rip-through-ce-signature ------------------------------------------------------------------------------------------------------------------------

def test_rip_needs_a_candle_through_the_ce_and_knows_large_wicks():
    gap_over = [(4100, 4105.5, 4099.9, 4105.2), (4108.5, 4110.0, 4108.2, 4109.5)]          # a gap over the whole opposing FVG (4105-4107, CE 4106): no candle traded through the CE
    ctx = mkctx(_opp_gap_rows() + gap_over)
    p = pk(rip_through=True)
    pos, tr, sd = mkpos(ctx, 1, 3, 4100.0, 4096.0, levels=(4115.0,))
    fill(ctx, sd, pos, tr, p)
    step(ctx, sd, pos, tr, p, 4, 5)
    assert "rip" not in (tr.mgmt_tags or "")
    # a large upper wick in the path is a rip object when rip_wick_mult > 0
    rows = [(4100, 4101, 4099, 4100.5)] * 8 + [(4100.5, 4106.0, 4100.4, 4101.0), (4101.0, 4101.5, 4100.2, 4100.8), (4100.8, 4101.2, 4100.0, 4100.5),
                                               (4100.5, 4105.0, 4100.3, 4104.8), (4104.8, 4106.5, 4104.0, 4106.2)]
    ctx = mkctx(rows)
    q = pk(rip_through=True, rip_wick_mult=2.0)
    pos, tr, sd = mkpos(ctx, 1, 10, 4100.5, 4096.0, levels=(4115.0,))
    fill(ctx, sd, pos, tr, q)
    wk = pos["me1"]["rip_gap"]
    assert wk[1] == pytest.approx(4106.0) and wk[0] == pytest.approx(4101.0)           # the wick over bar 8's body: 4101 .. 4106
    pos0, tr0, sd0 = mkpos(ctx, 1, 10, 4100.5, 4096.0, levels=(4115.0,))
    fill(ctx, sd0, pos0, tr0, pk(rip_through=True))
    assert pos0["me1"].get("rip_gap") is None


# --- X2-best-case-resting-limit ------------------------------------------------------------------------------------------------------------------------

def test_best_case_resting_limit_checked_on_every_bar():
    ctx = mkctx(flatrows(3) + [(4000, 4003, 3999.8, 4001), (4001, 4041, 4000.5, 4040.5)])
    p = pk(best_case_limit=True)
    pos, tr, sd = mkpos(ctx, 1, 1, 4000.0, 3990.0, levels=(4030.0,))
    fill(ctx, sd, pos, tr, p)
    assert pos["me1"]["best_case"] == pytest.approx(4060.0)
    pos["me1"]["bc_hold"] = True
    pos["me1"]["best_case"] = 4040.0
    step(ctx, sd, pos, tr, p, 4)                                                    # the hold bar printed 4041 (>= 4040): the resting limit fills in manage
    assert reasons(tr) == ["best_case"] and tr.exits[0][1] == pytest.approx(4040.0)


# --- N10-thursday-caps-week: the block lasts the rest of the day ------------------------------------------------------------------------------------------

def test_thu_week_extreme_blocks_the_whole_afternoon():
    import pandas as pd
    thu = date(2026, 6, 25)
    rows = [(4040, 4041, 4039, 4040)] * 5 + [(4040, 4060, 4040, 4059)] + [(4059, 4059.5, 4058, 4058.5)] * 300
    prev = pd.DataFrame({"open": 4000.0, "high": 4050.0, "low": 3990.0, "close": 4040.0}, index=pd.date_range("2026-06-23 09:30", periods=3, freq="5min", tz="America/New_York"))
    ctx = mkctx(rows, t0=570, d=thu, hist=[prev])

    class Conf:
        def at(self, t, price, side):
            return ["D"] if (side == -1 and 4055 <= price <= 4065) else []
    ctx.conf = Conf()
    p = pk(thu_cap=True)
    sd = ctx.sides_map[1]
    assert me1.thu_block(ctx, sd, 8, p, "AM") == "x_thu_week_ext"
    pm = next(i for i in range(len(rows)) if ctx.t[i] >= 800)
    assert ctx.t[pm] >= 780 and me1.thu_block(ctx, sd, pm, p, "PM") == "x_thu_week_ext"       # a 13:20 order is blocked too
    # an extreme made AFTER 12:00 is not a Thursday-morning extreme
    rows2 = [(4040, 4041, 4039, 4040)] * 200 + [(4040, 4060, 4040, 4059)] + [(4059, 4059.5, 4058, 4058.5)] * 5
    ctx2 = mkctx(rows2, t0=570, d=thu, hist=[prev])
    ctx2.conf = Conf()
    assert me1.thu_block(ctx2, ctx2.sides_map[1], len(rows2) - 1, p, "PM") is None


# --- bookkeeping: the 63 / 196 / 111 / 79 / 62 items ----------------------------------------------------------------------------------------------------

def test_study_variants_of_the_review_fixes():
    D = study.DECISIONS
    assert D["X9-entry-fvg-immediate-rejection_forming_stop"]["stop_mode"] == "fvg_candle" and D["B6-intraday-iof_strict"]["iof_strict"] is True
    assert D["A8-rip-through-ce-signature_wick"]["rip_wick_mult"] > 0 and D["T9-strong-am-no-lunch-retrace_pm_ext"]["no_lunch_retrace_hold"] is True
    for k in ("X9-entry-fvg-immediate-rejection_forming_stop", "B6-intraday-iof_strict", "A8-rip-through-ce-signature_wick", "X4-be-without-partials_full_pull"):
        Params(**D[k])
    assert D["X4-be-without-partials_full_pull"]["exit_mode2"] == "full_pull"
    p = Params(be_mode="adr_frac")
    assert me1.eff_params(p) is me1.eff_params(p)                                    # built once per Params, not per day
