"""Caption-gap pass, package setups_models #3/7, part A: the 36 specs of digests/rulebook_gaps/levels_liquidity_targets.md (items 44, 77, 79, 82, 91, 92, 111, 121, 123, 124, 125, 137, 141,
158, 162, 173, 174), management_partials_trailing_exits.md (64, 74, 76, 77, 78, 82, 83, 85, 86, 88, 101) and models_setups_entries.md (1, 2, 3, 4, 5, 8, 9, 10).
Unit tests of the detectors / gates (sm3.py) and of the engine glue (strategy / setups / sm2 hooks), small run_day scenarios, Params plumbing. Tests that need local market data (ES)
skip cleanly when it is absent; no platform-specific paths. The study variants and the no-look-ahead runs live in test_caption_gap_sm3b.py."""
from dataclasses import replace
from datetime import date
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from mentorship import backtest as B, levels as L, setups as SM, sm2, sm3, strategy as S, study
from mentorship.strategy import Params

from test_levels_detectors import BASE, D0, NY, day, ctx_for, frame, history, prior_days, rth_day
from test_caption_gap_sm1a import AFTER, StubConf, hist_close, ib, mkctx, sd_of, stub
from test_review_fixes import B_POST, B_ROWS, run as rf_run

A = np.array

NEW_SWITCHES = (
    "wick_sweep_depth", "wick_depth_bars", "shallow_sweep_wait", "shallow_ticks", "leg_grade_gate", "leg_origin", "leg_grade_tol", "org_entry_array", "org_entry_confl",
    "org_confl_ticks", "org_entry_windows", "eq_hunt", "eq_hunt_band", "prev_eq_long", "recap_ob_entry", "mm_turn_types", "vb_trade", "vb_min_gap_pts", "raid_roll",
    "near_pool_block", "near_pool_adr", "wk_high_proj", "wk_proj_k", "wk_proj_size", "ts_age_rank", "ts_linger_bars", "reh_fade_gate", "pm_lunch_raid", "ir_filters",
    "ir_accel_hold", "tgif_need_draw", "tgif_sd_exit", "ma_deuce_ladder", "ss_ladder", "ss_t1_frac", "mb_targets", "mb_done_at_htf", "mb_body_exit", "counter_scalp",
    "sweep_max_linger", "breaker_max_taps_for_entry", "lh_draw_freeze", "lh_freeze_t", "mm_plan", "unicorn_preopen", "unicorn_back_bars", "breaker_need_bias_draw",
    "ce_fail_entry", "expansion_ce_entry", "expansion_bulk", "pm_need_htf_target", "pm_lunch_fvg_array", "allow_htf_array_premise", "premise_tfs",
)


def test_new_switch_defaults_and_validation():
    p = Params()
    assert (p.wick_sweep_depth, p.wick_depth_bars, p.shallow_sweep_wait, p.shallow_ticks, p.leg_grade_gate, p.leg_origin, p.leg_grade_tol) == (False, 12, False, 4, "off", "mss_low", 0.05)
    assert (p.org_entry_array, p.org_entry_confl, p.org_confl_ticks, p.org_entry_windows) == (False, True, 4, ((180, 240), (600, 660), (840, 900), (900, 960)))
    assert (p.eq_hunt, p.eq_hunt_band, p.prev_eq_long, p.recap_ob_entry, p.mm_turn_types, p.vb_trade, p.raid_roll) == ("off", 0.10, False, False, ("ob", "fvg"), False, False)
    assert (p.near_pool_block, p.near_pool_adr, p.wk_high_proj, p.wk_proj_k, p.wk_proj_size, p.ts_age_rank, p.ts_linger_bars, p.reh_fade_gate, p.pm_lunch_raid) == \
        (False, 0.25, False, (1.27, 1.62), 0.5, "off", 0, False, False)
    assert (p.ir_filters, p.ir_accel_hold, p.tgif_need_draw, p.tgif_sd_exit, p.ma_deuce_ladder, p.ss_ladder, p.ss_t1_frac, p.mb_targets, p.mb_done_at_htf, p.mb_body_exit) == \
        (False, False, False, False, False, False, 0.8, False, False, False)
    assert (p.counter_scalp, p.sweep_max_linger, p.breaker_max_taps_for_entry, p.lh_draw_freeze, p.lh_freeze_t, p.mm_plan, p.unicorn_preopen, p.unicorn_back_bars) == \
        (False, 0, 0, False, 720, "", False, 15)
    assert (p.breaker_need_bias_draw, p.ce_fail_entry, p.expansion_ce_entry, p.expansion_bulk, p.pm_need_htf_target, p.pm_lunch_fvg_array, p.allow_htf_array_premise, p.premise_tfs) == \
        (False, False, False, 0.65, False, False, False, (15, 60))
    for kw in (dict(leg_grade_gate="x"), dict(leg_origin="x"), dict(eq_hunt="x"), dict(ts_age_rank="x"), dict(mm_plan="x"), dict(mm_turn_types=("nope",)), dict(wick_depth_bars=0),
               dict(shallow_ticks=-1), dict(eq_hunt_band=0.9), dict(wk_proj_size=0), dict(wk_proj_k=()), dict(ss_t1_frac=0), dict(expansion_bulk=1.5), dict(premise_tfs=(7,)),
               dict(org_entry_windows=((10, 5),)), dict(lh_freeze_t=1440), dict(unicorn_back_bars=0), dict(near_pool_adr=-1)):
        with pytest.raises(ValueError):
            Params(**kw)
    assert set(NEW_SWITCHES) <= set(Params.__dataclass_fields__)


# --- A23-1h-wick-ce-sweep-depth (44) ----------------------------------------------------------------------------------------------------------------

def _hour(hi, lo, c=None, o=None):
    o = hi if o is None else o
    c = o if c is None else c
    first = (o, max(o, c, hi), lo, c)
    return [first] + [(c, c + 0.2, c - 0.2, c)] * 11


def test_rel_sweep_needs_1h_wick_ce():
    """063 ~24:04: the REL 4100; a 1h bar (08:00) with a lower wick down to 4092 on a 4100 body has its CE at 4096. A sweep that only reached 4098 waits; one that reached 4096.25
    (within 2 ticks) is armed; a 1h body that closes under the CE cancels the sweep; with no wick under the pool the sweep is dropped; the stop sits under min(extreme, CE)."""
    rows = _hour(4100.5, 4092.0, c=4100.0, o=4100.0) + _hour(4101.0, 4099.5, c=4100.5) + [(4100.5, 4101.0, 4100.0, 4100.5)] * 6
    p = Params(**BASE, wick_sweep_depth=True, pivot_n=1)
    ctx, (sl, ss) = mkctx(rows, base=4100.0, start="08:00", p=p, hist=hist_close(close=4100.0, hi=4130.0, lo=4040.0))
    i = ib(ctx, "09:30") + 1
    assert sm3.wick_ce_for(ctx, sl, 4100.0, i, p) == pytest.approx(4096.0)
    assert sm3.wick_ce_for(ctx, sl, 3990.0, i, p) is None                       # no wick reaches under a pool that deep
    sw = dict(session="AM", key="rel_eq_lows0", level=4100.0, ext=4098.0, ext_i=i - 3, sweep_i=i - 3, broke=None)
    assert sm3.sweep_init(ctx, sl, sw, i, p, "AM") is None and sw["wick_ce"] == pytest.approx(4096.0)
    assert sm3.sweep_step(ctx, sl, sw, i, p) == "wait"                          # 4098 is 2 points above the CE
    sw["ext"] = 4096.25
    assert sm3.sweep_step(ctx, sl, sw, i, p) is None                            # within 2 ticks of the CE
    assert sm3.stop_adjust(ctx, sl, sw, i, p, 4101.0, 4099.0, {}) == pytest.approx(4096.0 - p.pad)     # under min(sweep low 4096.25, CE 4096)
    sw2 = dict(session="AM", key="rel_eq_lows0", level=3990.0, ext=3980.0, ext_i=i - 3, sweep_i=i - 3, broke=None)
    assert sm3.sweep_init(ctx, sl, sw2, i, p, "AM") == "drop"
    assert sm3.sweep_init(ctx, sl, dict(sw2, key="pdl1"), i, p, "AM") is None   # only relative equal lows are judged
    # a later 1h bar whose body closes under the CE: the run is a real decline
    rows2 = _hour(4100.5, 4092.0, c=4100.0, o=4100.0) + [(4100.0, 4100.5, 4094.0, 4095.0)] * 12 + [(4095.0, 4096.0, 4094.0, 4095.0)] * 6
    ctx2, (sl2, ss2) = mkctx(rows2, base=4100.0, start="08:00", p=p, hist=hist_close(close=4100.0, hi=4130.0, lo=4040.0))
    sw3 = dict(session="AM", key="rel_eq_lows0", level=4100.0, ext=4096.0, ext_i=ib(ctx2, "08:55"), sweep_i=ib(ctx2, "08:55"), broke=None, wick_ce=4096.0)
    assert sm3.sweep_step(ctx2, sl2, sw3, ib(ctx2, "10:05"), p) == "drop"
    assert sm2.HITS.get("wick_depth") and sm2.HITS.get("wick_depth_cancel")


# --- new-shallow-rel-sweep-one-more-drive (77) ------------------------------------------------------------------------------------------------------

def test_shallow_rel_sweep_needs_second_drive():
    """060 ~59:18: a REL sweep of 2 ticks (< shallow_ticks = 4) arms nothing; a later, deeper low (2 points) clears the wait and the sweep arms normally. Off = armed at once."""
    rows = [(4100.0, 4101.0, 4099.0, 4100.5)] * 8
    p = Params(**BASE, shallow_sweep_wait=True)
    ctx, (sl, ss) = mkctx(rows, base=4100.0, p=p, hist=hist_close(close=4100.0, hi=4130.0, lo=4040.0))
    i = ib(ctx, "09:30") + 5
    sw = dict(session="AM", key="rel_eq_lows0", level=4100.0, ext=4099.5, ext_i=i - 2, sweep_i=i - 2, broke=None)
    sm3.sweep_init(ctx, sl, sw, i, p, "AM")
    assert sw["shallow"] and sm3.sweep_step(ctx, sl, sw, i, p) == "wait"        # 2 ticks: one more drive is expected
    sw["ext"] = 4098.0                                                          # the second drive: 2 points under the pool
    assert sm3.sweep_step(ctx, sl, sw, i, p) is None and not sw["shallow"]
    assert sm3.sweep_step(ctx, sl, sw, i, p) is None
    sw_off = dict(session="AM", key="rel_eq_lows0", level=4100.0, ext=4099.5, ext_i=i - 2, sweep_i=i - 2, broke=None)
    sm3.sweep_init(ctx, sl, sw_off, i, replace(p, shallow_sweep_wait=False), "AM")
    assert "shallow" not in sw_off
    # engine: scenario B (the sweep takes the pre-market low): the premarket pool is not a REL, so the trade is unchanged
    base = rf_run(day(B_ROWS + AFTER), history(hi=112.0, lo=88.0), Params(**{**B_POST, "adds": (0.5,)}), {})[0]
    on = rf_run(day(B_ROWS + AFTER), history(hi=112.0, lo=88.0), Params(**{**B_POST, "adds": (0.5,), "shallow_sweep_wait": True}), {})[0]
    assert len(base) == len(on) == 1


# --- new-leg-grading-quadrants (79) -----------------------------------------------------------------------------------------------------------------

def test_leg_grade_entry_zone():
    """061 ~2:07:40: O 4000 (the sweep extreme), D 4100 (the locked draw): 4040 is grade 2 and fine, 4070 is grade 3 and rejected in require mode (tag mode keeps it); require arms the
    cancel on a close under O; the session_low origin reads the day's low."""
    rows = [(4020.0, 4021.0, 4000.5, 4020.0)] * 6
    ctx, (sl, ss) = mkctx(rows, base=4020.0, bias=1, hist=hist_close(close=4020.0, hi=4130.0, lo=3900.0))
    ctx.cur_lock = dict(side=1, target=4100.0, kind="pool", name="pdh1", marked=[])
    i = ib(ctx, "09:30") + 4
    sw = dict(session="AM", key="x", level=4000.0, ext=4000.0, ext_i=i - 2, sweep_i=i - 2, broke=i - 1)
    req = Params(**BASE, leg_grade_gate="require")
    lvt, tags = [], {}
    assert sm3.order_gate3(ctx, sl, sw, i, req, 4040.0, 4030.0, "AM", lvt, {}, tags) is None
    assert "grade_q2" in lvt and tags["cancel_close"] == 4000.0
    assert sm3.order_gate3(ctx, sl, sw, i, req, 4070.0, 4060.0, "AM", [], {}, {}) == "x_leg_grade"
    lvt2 = []
    assert sm3.order_gate3(ctx, sl, sw, i, replace(req, leg_grade_gate="tag"), 4070.0, 4060.0, "AM", lvt2, {}, {}) is None and "grade_q3" in lvt2
    assert sm3.leg_grade(ctx, sl, sw, i, replace(req, leg_origin="session_low"), 4040.0, "AM")[1] == pytest.approx(4000.5)
    assert sm3.order_gate3(ctx, sl, sw, i, replace(req, leg_grade_tol=0.0), 4050.0, 4040.0, "AM", [], {}, {}) is None          # exactly the half way
    ctx.cur_lock = None
    assert sm3.leg_grade(ctx, sl, sw, i, req, 4040.0, "AM") is None                                                             # no draw: nothing to grade


# --- L7-org-later-day-entry-array (82) --------------------------------------------------------------------------------------------------------------

def test_prior_org_entry_needs_confluence():
    """092 ~1:59:32: Friday's ORG 4480 -> 4500 (gap up), unfilled (the days since never traded under 4500): its top 4500 is an entry level at Monday 10:15 for a long with the bias,
    but only with another array within 4 ticks (a 4500.0-4501.0 FVG); without the FVG no entry (confl on), with org_entry_confl off the ORG level alone (080)."""
    mon = date(2026, 6, 22)
    hs = [rth_day(x, 4560.0, 4505.0, close=4530.0) for x in prior_days(mon, 8)]
    rows = [(4510.0, 4511.0, 4505.0, 4510.0)] * 4 + [(4510.0, 4511.0, 4502.0, 4503.0)] * 8
    p = Params(**BASE, org_entry_array=True)
    ctx, (sl, ss) = mkctx(rows, base=4520.0, bias=1, hist=hs, d=mon, p=p)
    ctx.org, ctx.org_today, ctx.org_dates = [(4480.0, 4500.0)], False, [hs[-1].index[0].date()]
    i = ib(ctx, "10:15")
    sw = dict(session="AM", key="x", level=4499.0, ext=4498.0, ext_i=i - 2, sweep_i=i - 2, broke=i - 1)
    assert SM.array_cands(ctx, sl, sw, i, p, None) == []                         # no second array: never the ORG level alone
    sl.gaps = [L.Zone("bull", 4501.0, 4500.0, i - 3, i - 4)]
    assert SM.array_cands(ctx, sl, sw, i, p, None) == [(4500.0, 4480.0, "org")]
    assert [x[0] for x in SM.array_cands(ctx, sl, dict(sw, ext=4485.0), i, replace(p, org_confl_ticks=0, org_entry_confl=False), None)] == [4500.0, 4495.0, 4490.0]   # 080: the high, 75% and CE
    ctx.cur_bias = -1
    assert SM.array_cands(ctx, sl, sw, i, p, None) == []                         # the bias must agree
    ctx.cur_bias = 1
    sw3 = dict(sw)
    ctx9, (sl9, _) = mkctx(rows, base=4520.0, bias=1, hist=hs, d=mon, p=p, start="12:00")
    ctx9.org, ctx9.org_today, ctx9.org_dates = [(4480.0, 4500.0)], False, [hs[-1].index[0].date()]
    i9 = ib(ctx9, "12:30")
    sl9.gaps = [L.Zone("bull", 4501.0, 4500.0, i9 - 3, i9 - 4)]
    assert SM.array_cands(ctx9, sl9, dict(sw3, ext_i=i9 - 2, broke=i9 - 1), i9, p, None) == []      # 12:30 is outside the 03-04 / 10-11 / 14-15 / 15-16 windows


# --- new-eq-stop-hunt-entry (91) --------------------------------------------------------------------------------------------------------------------

def test_eq_stop_hunt_tag():
    """075 ~1:31:00: range 4000-4100 (EQ 4050): a swept short-term low at 4049 is a stop hunt (tag; prefer ranks it first; the stop sits under the sweep extreme); one at 4020 or a
    non-swing pool is not."""
    hs = [rth_day(x, 4100.0, 4000.0, close=4050.0) for x in prior_days(D0, 8)]
    rows = [(4050.0, 4051.0, 4049.5, 4050.0)] * 6
    p = Params(**BASE, eq_hunt="prefer")
    ctx, (sl, ss) = mkctx(rows, base=4050.0, p=p, hist=hs)
    i = ib(ctx, "09:30") + 4
    assert sm3.eq_hunt_level(ctx, sl, i, p, "swing_low3", 4049.0)
    assert not sm3.eq_hunt_level(ctx, sl, i, p, "swing_low3", 4020.0)
    assert not sm3.eq_hunt_level(ctx, sl, i, p, "pdl1", 4049.0)
    hits = [("pdl1", 4040.0), ("swing_low3", 4049.0)]
    assert sm3.prefer_hits(ctx, sl, i, p, hits) == [("swing_low3", 4049.0)]
    assert sm3.prefer_hits(ctx, sl, i, replace(p, eq_hunt="tag"), hits) == hits
    sw = dict(session="AM", key="swing_low3", level=4049.0, ext=4048.0, ext_i=i - 1, sweep_i=i - 1, broke=None)
    sm3.sweep_init(ctx, sl, sw, i, p, "AM")
    assert sw["eq_hunt"] and sm3.stop_adjust(ctx, sl, sw, i, p, 4050.0, 4049.0, {}) == pytest.approx(4048.0 - p.pad)
    lvt = []
    sm3.order_gate3(ctx, sl, sw, i, p, 4050.0, 4047.0, "AM", lvt, {}, {})
    assert "eq_hunt" in lvt


# --- new-prev-day-range-eq-long (92) ----------------------------------------------------------------------------------------------------------------

def test_prev_day_eq_long_gate():
    """076 ~20:09: yesterday opened 4000 (00:00) and ran to 4100, taking a key high (the day before's 4040 and the week's); R = 4000-4100, EQ 4050: a long at 4060 is blocked, 4045 is
    allowed. A Reaper under EQ (an FVG in the discount half of yesterday's leg) moves the floor to its CE: 4005 is then blocked. No key high taken: n/a."""
    ds = prior_days(D0, 6)
    hs = [rth_day(x, 4040.0, 3990.0, close=4020.0) for x in ds[:-1]]
    leg = [(4000.0, 4005.0, 3999.0, 4004.0), (4004.0, 4010.0, 4003.0, 4009.0), (4009.0, 4020.0, 4008.0, 4019.0), (4019.0, 4030.0, 4015.0, 4029.0), (4029.0, 4045.0, 4028.0, 4044.0),
           (4044.0, 4060.0, 4043.0, 4059.0), (4059.0, 4080.0, 4058.0, 4079.0), (4079.0, 4100.0, 4078.0, 4099.0)]
    hs.append(frame(ds[-1], leg, 5, "09:30"))
    rows = [(4050.0, 4051.0, 4040.0, 4045.0)] * 6
    p = Params(**BASE, prev_eq_long=True)
    ctx, (sl, ss) = mkctx(rows, base=4050.0, p=p, hist=hs)
    i = ib(ctx, "09:30") + 4
    assert sm3.prev_range_eq(ctx, sl, i, p, 4060.0) is False
    assert sm3.prev_range_eq(ctx, sl, i, p, 4045.0) is True
    z = sm3.prev_reaper(hs[-1], 1)
    assert z is not None and z[0] < 4050.0                                      # the 4010-4015 gap is in the discount half of the leg
    assert sm3.prev_range_eq(ctx, sl, i, p, 4005.0) is False                    # under the Reaper's CE: no support left
    flat = [rth_day(x, 4040.0, 3990.0, close=4020.0) for x in ds]
    flat[-1] = rth_day(ds[-1], 4030.0, 3990.0, close=4020.0)
    ctx2, (sl2, _) = mkctx(rows, base=4050.0, p=p, hist=flat)
    assert sm3.prev_range_eq(ctx2, sl2, i, p, 4060.0) is None                    # no key high taken yesterday
    # the gate in order_gate3 and the mirror (a short at the discount side of a down day)
    assert sm3.order_gate3(ctx, sl, dict(session="AM", key="x", level=0, ext=4040.0, ext_i=i - 1, sweep_i=i - 1, broke=i), i, p, 4060.0, 4050.0, "AM", [], {}, {}) == "x_prev_eq"


# --- new-retrace-to-recapitalized-ob (111) ----------------------------------------------------------------------------------------------------------

def test_retrace_to_recapitalized_ob(monkeypatch):
    """cc03_003 ~38:17: a bullish OB (4050-4056) re-bought on the prior leg, the intermediate high 4058 swept, the HTF high 4120 untaken: a long limit at the OB's open 4056 (stop under
    its low), target 4120.25; shorts against the objective are blocked (tag unfulfilled) while it stands."""
    rows = [(4056.0, 4056.0, 4050.0, 4051.0), (4051.0, 4054.5, 4050.5, 4054.0), (4054.0, 4055.0, 4040.0, 4042.0), (4042.0, 4060.0, 4041.0, 4059.0), (4059.0, 4061.0, 4057.5, 4058.0)]
    hs = history(hi=4058.0, lo=3950.0)
    p = Params(**BASE, recap_ob_entry=True)
    ctx, (sl, ss) = mkctx(rows, base=4056.0, bias=1, p=p, hist=hs)
    ctx.cur_lock = dict(side=1, target=4120.0, kind="pool", name="htf_PDH", marked=[])
    cap = {}
    monkeypatch.setattr(S, "_finish_order", lambda ctx_, sd_, i_, p_, sess_, sw_, entry, stop, rm, lh, tags, **k: cap.update(entry=entry, stop=stop, fixed=k.get("fixed"), tags=tags) or "ORDER")
    i = ib(ctx, "09:30") + 4
    assert sm3.recap_ob_order(ctx, sl, i, p, "AM", 1.0) == "ORDER"
    assert cap["entry"] == 4056.0 and cap["stop"] == pytest.approx(4050.0 - p.pad) and cap["fixed"] == [(4120.25, "pool")]
    assert sm3.recap_ob_order(ctx, sl, i, p, "AM", 1.0) is None                 # once per OB
    ctx.cur_lock = None
    sl2 = sm2.other_side(ctx, sl)
    ctx.bias_row = dict(draw_up=4120.0, draw_up_name="D_swing_high", draw_dn=3950.0, draw_dn_name="D_swing_low")
    # a short (side -1) against the untaken HTF high above is blocked: here the NEAREST draw is the high, 62 pts away vs 108 below
    lvt = []
    sw = dict(session="AM", key="x", level=0, ext=-4060.0, ext_i=i - 1, sweep_i=i - 1, broke=i)
    assert sm3.order_gate3(ctx, sl2, sw, i, p, -4058.0, -4070.0, "AM", lvt, {}, {}) == "x_unfulfilled" and "unfulfilled" in lvt
    assert sm3.order_gate3(ctx, sl, dict(sw, ext=4040.0), i, p, 4056.0, 4050.0, "AM", [], {}, {}) is None          # the long toward it is fine
    assert sm3.order_gate3(ctx, sl2, sw, i, replace(p, recap_ob_entry=False), -4058.0, -4070.0, "AM", [], {}, {}) is None


# --- M1-turning-level-types (121) -------------------------------------------------------------------------------------------------------------------

def _rows_hours(highs):
    out = []
    for hi in highs:
        out += [(hi - 10.0, hi, hi - 12.0, hi - 10.0)] * 12
    return out


def test_mm_turn_at_old_high_support():
    """cc04_007 ~1:04: a sweep low at an old 1h high (4050, now support) passes the discount-array check with "old_high" only; the default types (ob, fvg) do not; a void (a true gap
    between candles) is a turning level with "void"."""
    p0 = Params(**BASE, pivot_n=1)
    p1 = replace(p0, mm_turn_types=("ob", "fvg", "old_high"))
    rows = _rows_hours([4040.0, 4050.0, 4040.0, 4030.0]) + [(4030.0, 4031.0, 4029.0, 4030.0)] * 6
    ctx, (sl, ss) = mkctx(rows, base=4030.0, start="08:00", p=p0, hist=hist_close(close=4030.0, hi=4130.0, lo=3900.0))
    e = ib(ctx, "12:00")
    sw = dict(ext=4050.0, ext_i=e)
    tol = p0.eq_tol_pts * p0.es_pt
    assert SM._discount_array(ctx, sl, sw, tol, p0) is False
    assert SM._discount_array(ctx, sl, sw, tol, p1) is True
    assert SM._discount_array(ctx, sl, dict(ext=4062.0, ext_i=e), tol, p1) is False
    assert SM._discount_array(ctx, sl, sw, tol) is False                         # (the default argument keeps the first build)
    # a void: bar 3's low is above bar 2's high
    vrows = [(100.0, 100.5, 99.5, 100.0), (100.0, 100.4, 99.6, 100.1), (100.1, 100.3, 99.9, 100.2), (101.5, 102.0, 101.0, 101.8), (101.8, 102.0, 100.9, 101.0), (101.0, 101.2, 100.9, 101.1)]
    ctx2, (sl2, _) = mkctx(vrows, base=100.0, p=p0, hist=hist_close(close=100.0))
    e2 = ib(ctx2, "09:30") + 5
    pv = replace(p0, mm_turn_types=("void",))
    assert SM._discount_array(ctx2, sl2, dict(ext=101.2, ext_i=e2), tol, pv) is True
    assert SM._discount_array(ctx2, sl2, dict(ext=101.2, ext_i=e2), tol, replace(p0, mm_turn_types=("old_low",))) is False


# --- L8 vacuum block trade (123, 85) ----------------------------------------------------------------------------------------------------------------

def _vb_ctx(p, after=()):
    rows = [(4105.0, 4110.0, 4104.5, 4109.0), (4109.0, 4109.5, 4099.0, 4101.0)] + list(after)
    ctx, (sl, ss) = mkctx(rows, base=4100.0, bias=1, p=p, hist=hist_close(close=4100.0, hi=4250.0, lo=3990.0))
    return ctx, sl


def test_vacuum_block_trade_target(monkeypatch):
    """cc04_009 ~12:42: the gap 4100-4105 (pre-gap close 4100) fully filled (low 4099) and the close back above it: a limit at 4100, stop under the fill's low, T1 = the gap-opening high
    4110 + 1 tick = 4110.25 (and a runner to the next pool)."""
    p = Params(**BASE, vb_trade=True, vb_min_gap_pts=0.5)
    ctx, sl = _vb_ctx(p)
    cap = {}
    monkeypatch.setattr(S, "_finish_order", lambda ctx_, sd_, i_, p_, sess_, sw_, entry, stop, rm, lh, tags, **k: cap.update(entry=entry, stop=stop, fixed=k.get("fixed"), tags=tags) or "ORDER")
    k0 = ib(ctx, "09:30")
    assert sm3.vb_order(ctx, sl, k0, p, "AM", 1.0) is None                       # the gap is not filled yet
    assert sm3.vb_order(ctx, sl, k0 + 1, p, "AM", 1.0) == "ORDER"
    assert cap["entry"] == 4100.0 and cap["stop"] == pytest.approx(4099.0 - p.pad) and cap["fixed"][0] == (4110.25, "pool")
    assert cap["tags"]["sm3"]["vb"]["hi"] == 4110.0 and cap["tags"]["sm3"]["vb"]["pre"] == 4100.0
    assert sm3.vb_order(ctx, sl, k0 + 1, p, "AM", 1.0) is None                   # once per gap
    assert sm3.vb_gaps(ctx, sl, replace(p, vb_min_gap_pts=6.0)) == []             # a 5 point gap is under the minimum


def test_vb_trade():
    """cc04_009 ~11:48 / ~14:09: once price has traded through the gap candle's high, two closes under it take 50% (vb_stall); a later close under the pre-gap close 4100 takes 50% of the
    rest (vb_back) and a lower close closes all (vb_back2). The counts are the position's: 100 -> 50 -> 25 -> 0."""
    after = [(4101.0, 4111.0, 4100.5, 4109.0), (4109.0, 4110.5, 4107.0, 4108.0), (4108.0, 4108.5, 4098.0, 4099.0), (4099.0, 4099.5, 4096.0, 4097.0)]
    p = Params(**BASE, vb_trade=True)
    ctx, sl = _vb_ctx(p, after)
    k0 = ib(ctx, "09:30")
    fill = k0 + 2
    pos = dict(left=100, fill_i=fill - 1, k=0, last_partial_i=-1, sm3=dict(vb=dict(hi=4110.0, pre=4100.0, stall=0, reached=False, above=False, traded_above=False, back=0, back_c=None, done_stall=False)))
    tr = SimpleNamespace(exits=[])
    ts = ctx.idx[0]
    out = []
    for i in range(fill, fill + 4):
        sm3.manage(ctx, sl, pos, tr, i, ts, p)
        out.append((tr.exits[-1][3] if tr.exits else None, pos["left"]))
    assert out == [(None, 100), ("vb_stall", 50), ("vb_back", 25), ("vb_back2", 0)]
    assert [e[2] for e in tr.exits] == [50, 25, 25]
    # no stall when a bar closes above the gap candle's high
    pos2 = dict(left=100, fill_i=fill - 1, k=0, last_partial_i=-1, sm3=dict(vb=dict(hi=4110.0, pre=4100.0, stall=0, reached=False, above=False, traded_above=False, back=0, back_c=None, done_stall=False)))
    ctx2, sl2 = _vb_ctx(p, [(4101.0, 4113.0, 4100.5, 4112.0), (4112.0, 4113.0, 4111.0, 4112.5), (4112.5, 4113.0, 4111.5, 4112.0)])
    tr2 = SimpleNamespace(exits=[])
    for i in range(fill, fill + 3):
        sm3.manage(ctx2, sl2, pos2, tr2, i, ts, p)
    assert tr2.exits == [] and pos2["left"] == 100


# --- L2-raid-level-rolls (124) ----------------------------------------------------------------------------------------------------------------------

def test_raid_level_rolls_to_new_low(monkeypatch):
    """cc04_011 ~13:57: the raid level PDL 4000 traded (3998) and bounced with no 15m MSS, then a new 15m pivot low printed at 3995: the cc_limit moves to 3995 - 0.25 = 3994.75; without
    raid_roll the traded level offers no limit at all."""
    hs = [rth_day(x, 4040.0, 4000.0, close=4010.0) for x in prior_days(D0, 8)]
    b0 = [(4005.0, 4006.0, 4003.0, 4004.0)] * 3
    b1 = [(4004.0, 4004.5, 3998.0, 3999.0), (3999.0, 4001.0, 3998.5, 4000.5), (4000.5, 4002.0, 4000.0, 4001.0)]
    b2 = [(4001.0, 4001.5, 3995.0, 3996.0), (3996.0, 3999.0, 3995.5, 3998.0), (3998.0, 3999.5, 3997.5, 3999.0)]
    b3 = [(3999.0, 4001.0, 3998.5, 4000.5)] * 3
    b4 = [(4000.5, 4003.0, 4000.0, 4002.0)] * 3
    p = Params(**BASE, turtle_soup="cc_limit", raid_roll=True, ts_cc_below_pts=0.25, pivot_n=1, extra_pools=False)
    ctx, (sl, ss) = mkctx(b0 + b1 + b2 + b3 + b4, base=4005.0, bias=1, p=p, hist=hs)
    got = []
    monkeypatch.setattr(S, "_finish_order", lambda ctx_, sd_, i_, p_, sess_, sw_, entry, stop, *a, **k: got.append((entry, sw_["level"])) or "ORDER")
    i = ib(ctx, "09:30") + 13
    assert S._cc_limit(ctx, sl, i, p, "AM", 1.0) == "ORDER" and got[-1] == (pytest.approx(3994.75), pytest.approx(3995.0))
    assert S._cc_limit(ctx, sl, i, p, "AM", 1.0) is None                         # once per level
    got.clear()
    sl.__dict__.pop("_cc_sent", None)
    assert S._cc_limit(ctx, sl, i, replace(p, raid_roll=False), "AM", 1.0) is None and not got


# --- B1-nearby-unrun-high-trap (125) ----------------------------------------------------------------------------------------------------------------

def test_short_blocked_under_near_reh():
    """cc04_013 ~6:11: an untaken high (PDH 4100) 3 points over a short's entry 4097 with ADR5 20 (X = 0.25 x 20 = 5): rejected; a high 8 points away or one the sweep took is fine."""
    hs = [rth_day(x, 4100.0, 4080.0, close=4090.0) for x in prior_days(D0, 8)]
    rows = [(4095.0, 4096.0, 4094.0, 4095.5)] * 8
    p = Params(**BASE, near_pool_block=True)
    ctx, (sl, ss) = mkctx(rows, base=4095.0, p=p, hist=hs)
    i = ib(ctx, "09:30") + 6
    assert sm2.adr5(ctx) == pytest.approx(20.0)
    sw = dict(session="AM", key="rel_eq_lows0", level=-4096.0, ext=-4097.0, ext_i=i - 1, sweep_i=i - 1, broke=i)
    assert sm3.near_pool(ctx, ss, sw, i, p, "AM", -4097.0) == pytest.approx(-4100.0)
    assert sm3.order_gate3(ctx, ss, sw, i, p, -4097.0, -4100.5, "AM", [], {}, {}) == "x_near_pool"
    assert sm3.near_pool(ctx, ss, sw, i, p, "AM", -4090.0) is None                # 10 points away
    assert sm3.near_pool(ctx, ss, dict(sw, ext=-4101.0), i, p, "AM", -4097.0) is None      # the sweep ran under it (took it)
    assert sm3.order_gate3(ctx, ss, sw, i, replace(p, near_pool_block=False), -4097.0, -4100.5, "AM", [], {}, {}) is None


# --- L13-weekly-high-london-swing (137) -------------------------------------------------------------------------------------------------------------

def test_monday_weekly_high_projection(monkeypatch):
    """cc07_008 ~30:29: Monday of a bearish week, London high 4100, the 05:00-09:30 low 4090: the projection 4100 + 1.2 x 10 = 4112 sits in a weekly bearish OB (4110-4114): a short limit
    shaded one tick toward price at 4111.75, half size; other weekdays, a bullish week, a level away from every weekly array: nothing."""
    mon = date(2026, 6, 22)
    lon = [(4095.0, 4095.2, 4094.8, 4095.0)] * 36
    lon[10] = (4095.0, 4100.0, 4094.8, 4096.0)
    mid = [(4096.0, 4096.5, 4095.0, 4096.0)] * 20 + [(4096.0, 4096.5, 4090.0, 4091.0)] + [(4091.0, 4092.0, 4090.5, 4091.5)] * 33          # 05:00-09:30
    ny = [(4091.5, 4095.0, 4091.0, 4094.0), (4094.0, 4108.0, 4093.0, 4107.5), (4107.5, 4109.0, 4106.0, 4108.0)]
    rows = lon + mid + ny
    arr = {-1: [(4114.0, 4110.0, "W", 1, 0)]}
    p = Params(**BASE, wk_high_proj=True, wk_proj_k=(1.2,))
    ctx, (sl, ss) = mkctx(rows, base=4095.0, p=p, d=mon, start="02:00", conf=StubConf(arrays=arr), hist=hist_close(d=mon, close=4095.0, hi=4130.0, lo=4040.0))
    ctx.wbias = -1
    cap = {}
    monkeypatch.setattr(S, "_finish_order", lambda ctx_, sd_, i_, p_, sess_, sw_, entry, stop, rm, lh, tags, **k: cap.update(entry=entry, stop=stop, rm=rm) or "ORDER")
    i = ib(ctx, "09:35")
    assert sm3.wk_proj_levels(ctx, -1, p) == [(1.2, pytest.approx(4112.0))]
    assert sm3.wk_proj_order(ctx, ss, i, p, "AM", 1.0) == "ORDER"
    assert sm3.wk_proj_order(ctx, ss, i, p, "AM", 1.0) is None                    # once per level
    assert cap["entry"] == pytest.approx(-4111.75) and cap["rm"] == 0.5 and cap["stop"] == pytest.approx(-4114.0 - p.pad)
    ss.__dict__.pop("_wkp_sent")
    assert sm3.wk_proj_order(ctx, sl, i, p, "AM", 1.0) is None                    # the long side of a bearish week
    ctx.wbias = 0
    assert sm3.wk_proj_order(ctx, ss, i, p, "AM", 1.0) is None
    ctx.wbias = -1
    ctx_t, (_, ss_t) = mkctx(rows, base=4095.0, p=p, d=date(2026, 6, 23), start="02:00", conf=StubConf(arrays=arr), hist=hist_close(close=4095.0, hi=4130.0, lo=4040.0))
    ctx_t.wbias = -1
    assert sm3.wk_proj_order(ctx_t, ss_t, i, p, "AM", 1.0) is None                # not a Monday
    ctx_f, (_, ss_f) = mkctx(rows, base=4095.0, p=p, d=mon, start="02:00", conf=StubConf(arrays={-1: [(4130.0, 4125.0, "W", 1, 0)]}), hist=hist_close(d=mon, close=4095.0))
    ctx_f.wbias = -1
    assert sm3.wk_proj_order(ctx_f, ss_f, i, p, "AM", 1.0) is None                # the level is away from every weekly array


# --- M4-swept-low-age (141) -------------------------------------------------------------------------------------------------------------------------

def test_turtle_soup_any_age_prefer_recent():
    """cc05_005 ~13:24: two candidate lows (pdl3 = 3 sessions old, ipda40 = 40 sessions old) are both eligible; prefer picks the recent one (<= 5 sessions); tag mode records the age;
    ts_linger_bars cancels the turtle after more closes under the level than allowed."""
    ctx = stub(10)
    p = Params(**BASE, ts_age_rank="prefer")
    hits = [("ipda40", 3900.0), ("pdl3", 3990.0)]
    assert sm3.pool_age(ctx, "pdl3") == 3 and sm3.pool_age(ctx, "ipda40") == 40 and sm3.pool_age(ctx, "round") is None
    assert sm3.prefer_hits(ctx, None, 5, p, hits) == [("pdl3", 3990.0)]
    assert sm3.prefer_hits(ctx, None, 5, replace(p, ts_age_rank="tag"), hits) == hits
    assert sm3.prefer_hits(ctx, None, 5, p, [("ipda40", 3900.0), ("ipda60", 3800.0)]) == [("ipda40", 3900.0), ("ipda60", 3800.0)]     # none recent: both stay eligible
    sw = dict(session="AM", key="pdl3", level=3990.0, ext=3989.0, ext_i=2, sweep_i=2, broke=None)
    sm3.sweep_init(ctx, None, sw, 5, p, "AM")
    assert sw["ts_age"] == 3
    rows = [(3991.0, 3992.0, 3990.5, 3991.0)] * 6
    ctxm, (slm, ssm) = mkctx(rows, base=3991.0, hist=hist_close(close=3991.0, hi=4130.0, lo=3900.0))
    lvt = []
    sm3.order_gate3(ctxm, slm, sw, ib(ctxm, "09:30") + 4, Params(**BASE, ts_age_rank="tag"), 3991.0, 3988.0, "AM", lvt, {}, {})
    assert "ts_age_3" in lvt                                                     # the tag records the age
    sd = sd_of([(3991.0, 3992.0, 3990.5, 3991.0), (3991.0, 3991.5, 3988.0, 3989.0), (3989.0, 3990.0, 3988.5, 3989.5), (3989.5, 3990.0, 3988.5, 3989.0), (3989.0, 3991.5, 3988.9, 3991.0)])
    ctx5 = stub(5)
    sw2 = dict(session="AM", key="pdl3", level=3990.0, ext=3988.0, ext_i=1, sweep_i=1, broke=None)
    assert sm3.sweep_step(ctx5, sd, sw2, 3, Params(**BASE, turtle_soup="2023", ts_linger_bars=3)) is None and not sw2.get("ts_sent")      # 3 closes under the level: allowed
    assert sm3.sweep_step(ctx5, sd, sw2, 3, Params(**BASE, turtle_soup="2023", ts_linger_bars=2)) is None and sw2.get("ts_sent") is True  # ... more than 2: the turtle is cancelled
    sw3 = dict(session="AM", key="pdl3", level=3990.0, ext=3988.0, ext_i=1, sweep_i=1, broke=None)
    assert sm3.sweep_step(ctx5, sd, sw3, 3, Params(**BASE, ts_linger_bars=2)) is None and not sw3.get("ts_sent")                  # (only with turtle_soup on)


# --- LLT3-equal-highs-fade-condition (158) ----------------------------------------------------------------------------------------------------------

def test_reh_fade_needs_context():
    """cc09_005 ~20:04: want +1 and the REH swept: the fade short (side -1) is not armed (the pool is a continuation target); with the order flow this way (-1) it needs the sweep to be
    in a same-side HTF array; neutral (0) it needs an HTF array just beyond the pool."""
    rows = [(4100.0, 4101.0, 4099.0, 4100.0)] * 6
    ctx, (sl, ss) = mkctx(rows, base=4100.0, hist=hist_close(close=4100.0, hi=4130.0, lo=4040.0), conf=StubConf())
    i = ib(ctx, "09:30") + 4
    p = Params(**BASE, reh_fade_gate=True, ts_max_pts=5.0)
    sw = dict(session="AM", key="rel_eq_lows0", level=-4101.0, ext=-4102.0, ext_i=i - 1, sweep_i=i - 1, broke=i)
    ctx.cur_bias = 1
    assert sm3.reh_fade_ok(ctx, ss, sw, i, p, "AM") is False
    assert sm3.order_gate3(ctx, ss, sw, i, p, -4100.0, -4105.0, "AM", [], {}, {}) == "x_reh_fade"
    ctx.cur_bias = -1
    assert sm3.reh_fade_ok(ctx, ss, sw, i, p, "AM") is False                      # no array under the sweep extreme
    ctx.conf = StubConf(at_tfs={-1: ["1h"]})
    assert sm3.reh_fade_ok(ctx, ss, sw, i, p, "AM") is True
    ctx.cur_bias = 0
    ctx.conf = StubConf(arrays={-1: [(4105.0, 4103.0, "1h", 0, 0)]})              # a bearish 1h array 2-4 points above the REH 4101
    assert sm3.reh_fade_ok(ctx, ss, sw, i, p, "AM") is True
    ctx.conf = StubConf(arrays={-1: [(4120.0, 4118.0, "1h", 0, 0)]})
    assert sm3.reh_fade_ok(ctx, ss, sw, i, p, "AM") is False                      # 17 points above: not "just above"
    assert sm3.order_gate3(ctx, ss, dict(sw, key="pdh1"), i, p, -4100.0, -4105.0, "AM", [], {}, {}) is None      # only relative equal highs / lows are judged


# --- LLT3-lunch-hl-raid-not-target (174) ------------------------------------------------------------------------------------------------------------

def test_pm_lunch_low_is_sweep_pool():
    """cc10_013 ~1:50: with the PM bias up the lunch LOW is the entry sweep pool (a raid) - it is a pool even with extra_pools off - and it leaves the target ladder of the counter side;
    the lunch high stays a long target. Off: the lunch extremes keep both roles."""
    am = [(4005.0, 4008.0, 3995.0, 4005.0)] * 30                                  # the AM range reaches under the lunch range
    lunch = [(4005.0, 4010.0, 4000.0, 4005.0)] * 18
    pm = [(4005.0, 4006.0, 4004.0, 4005.0)] * 8
    p = Params(**BASE, pm_lunch_raid=True, extra_pools=False)
    ctx, (sl, ss) = mkctx(am + lunch + pm, base=4005.0, bias=1, start="09:30", p=p, hist=hist_close(close=4005.0, hi=4130.0, lo=3900.0))
    i = ib(ctx, "13:45")
    ctx.cur_session = "PM"
    assert S._sell_side(ctx, sl, "PM", i, False, p).get("lunch") == 4000.0
    assert "lunch" not in S._sell_side(ctx, sl, "PM", i, False, replace(p, pm_lunch_raid=False))
    p2 = replace(p, extra_pools=True)
    tl = [v for v, k in S._targets(ctx, sl, i, 4005.5, [], p2, None, None)]
    assert any(abs(v - 4010.0) < 0.01 for v in tl)                                   # the lunch high: a long target
    ts_on = [v for v, k in S._targets(ctx, ss, i, -4005.5, [], p2, None, None)]
    ts_off = [v for v, k in S._targets(ctx, ss, i, -4005.5, [], replace(p2, pm_lunch_raid=False), None, None)]
    assert any(abs(v + 4000.0) < 0.01 for v in ts_off) and not any(abs(v + 4000.0) < 0.01 for v in ts_on)      # the lunch low: gone from the counter side's targets
    assert sm3.lunch_not_target(ctx, ss) is True and sm3.lunch_not_target(ctx, sl) is False


# --- M11-immediate-rebalance-management (74) --------------------------------------------------------------------------------------------------------

def _ism_day():
    from claude_hf.daytypes import events
    d = date(2025, 1, 2)
    while d < date(2025, 12, 31):
        if d.weekday() in (0, 1, 2, 3) and events(d) & S.NEWS_1000:
            return d
        d = d + pd.Timedelta(days=1)
        d = d.date() if hasattr(d, "date") else d
    return None


def test_ir_mgmt():
    """092 ~1:41:37 / 100 ~1:36:14: ir_filters rejects an immediate rebalance on a Friday and on a Tuesday-style morning while a 10:00 release is still ahead (09:45), accepts it at 10:15; the
    first rung is the nearest pivot (just beyond); the rest is held only if the rung-1 bar's range is >= 1.5 x the median of the last 20 (else out at that close)."""
    rows = [(100.0, 100.3, 99.9, 100.1)] * 40
    p = Params(**BASE, ir_entries=True, ir_filters=True)
    d = _ism_day()
    if d is None:
        pytest.skip("no 10:00 release day in the calendar")
    ctx, (sl, ss) = mkctx(rows, base=100.0, bias=1, d=d, p=p)
    assert sm2.ir_gates_ok(ctx, sl, ib(ctx, "09:45"), p, "AM") is False
    assert sm2.ir_gates_ok(ctx, sl, ib(ctx, "10:15"), p, "AM") is True
    assert sm2.ir_gates_ok(ctx, sl, ib(ctx, "09:45"), replace(p, ir_filters=False), "AM") is True
    fri = date(2026, 6, 26)
    ctx2, (sl2, _) = mkctx(rows, base=100.0, bias=1, d=fri, p=p)
    assert sm2.ir_gates_ok(ctx2, sl2, ib(ctx2, "10:15"), p, "AM") is False
    assert sm2.ir_gates_ok(ctx2, sl2, ib(ctx2, "10:15"), replace(p, ir_filters=False), "AM") is True
    # rung 1: the nearest pivot high above the entry, plus a tick
    swing = [(100.0, 100.5, 99.5, 100.2), (100.2, 101.5, 100.1, 101.0), (101.0, 101.2, 100.0, 100.4), (100.4, 100.6, 99.8, 100.0), (100.0, 100.4, 99.9, 100.2)]
    ctx3, (sl3, _) = mkctx(swing + rows, base=100.0, bias=1, p=replace(p, pivot_n=1))
    i3 = ib(ctx3, "09:30") + 4
    r = sm3.ir_rungs(ctx3, sl3, i3, p, 100.2, [101.9, 103.0, 104.0], ["array", "array", "pool"])
    assert r == ([pytest.approx(101.75), 103.0], ["pool", "array"])                  # the existing target within a point of rung 1 is folded into it
    # the acceleration hold
    big = [(100.0, 100.3, 99.9, 100.1)] * 25 + [(100.1, 103.0, 100.0, 102.8)]
    small = [(100.0, 100.3, 99.9, 100.1)] * 25 + [(100.1, 100.5, 100.0, 100.4)]
    for rws, exits in ((big, 0), (small, 1)):
        ctx4, (sl4, _) = mkctx(rws, base=100.0, bias=1, p=p)
        i4 = ib(ctx4, "09:30") + 25
        pos = dict(left=10, fill_i=i4 - 3, k=1, last_partial_i=i4, sm3=dict(ir_accel=True))
        tr = SimpleNamespace(exits=[])
        sm3.manage(ctx4, sl4, pos, tr, i4, ctx4.idx[i4], p)
        assert len(tr.exits) == exits and (pos["left"] == 0) == bool(exits)
        if exits:
            assert tr.exits[0][3] == "ir_decel" and tr.exits[0][1] == 100.4


# --- M14-tgif-draw-hit-first-sd-depth (76) ----------------------------------------------------------------------------------------------------------

def test_tgif_draw_sd(monkeypatch):
    """070 ~50:36: a Friday that never reached the weekly draw (PWH 4500) gives no TGIF; with the draw hit, the first bearish breaker after the high (A 4500 / B 4492) projects
    B - 2 (A - B) = 4476, which lies inside the earlier bullish FVG 4475-4478: the final rung."""
    hs = [rth_day(x, 4510.0, 4440.0, close=4480.0) for x in prior_days(D0, 8)]
    p = Params(**BASE, tgif_need_draw=True, tgif_sd_exit=True)
    quiet = [(4480.0, 4490.0, 4478.0, 4488.0)] * 10
    ctx, (sl, ss) = mkctx(quiet, base=4480.0, p=p, hist=hs)
    ctx.bias_row = dict(draw_up=4500.0, draw_up_name="PWH", draw_dn=4400.0, draw_dn_name="PWL")
    i = ib(ctx, "09:30") + 9
    assert sm3.tgif_draw_ok(ctx, ss, i, p, "AM") is False
    hit_rows = quiet[:3] + [(4488.0, 4500.5, 4486.0, 4492.0)] + quiet[4:]
    ctx, (sl, ss) = mkctx(hit_rows, base=4480.0, p=p, hist=hs)
    ctx.bias_row = dict(draw_up=4500.0, draw_up_name="PWH", draw_dn=4400.0, draw_dn_name="PWL")
    k0 = ib(ctx, "09:30")
    assert sm3.tgif_draw_ok(ctx, ss, k0 + 3, p, "AM") is True and sm3.tgif_draw_ok(ctx, ss, k0 + 2, p, "AM") is False      # not before the bar that touched it
    # side space of the short: the breaker [4492, 4500] is -4500..-4492, the earlier bullish FVG 4475-4478 is -4478..-4475
    monkeypatch.setattr(L, "breakers", lambda *a, **k: [L.Zone("bull", -4492.0, -4500.0, k0 + 5, k0 + 4, -4496.0)])
    ss.opposing = lambda: [L.Zone("bear", -4475.0, -4478.0, k0 + 1, k0)]
    v = sm3.tgif_sd_level(ctx, ss, k0 + 9, p, -4490.0)
    assert v == pytest.approx(-4476.0)
    ss.opposing = lambda: [L.Zone("bear", -4455.0, -4458.0, k0 + 1, k0)]          # no earlier array holds either level
    assert sm3.tgif_sd_level(ctx, ss, k0 + 9, p, -4490.0) is None


# --- M15-ma-deuce-ladder (77) -----------------------------------------------------------------------------------------------------------------------

def test_ma_deuce_ladder():
    """091 ~23:31: md_ladder's rungs are the daily BISI's CE, its lower quadrant and the nearest 1h BISI low; ma_deuce_ladder adds the BISI's far edge (the best case) as the final rung
    when there is no 1h array: 4400 for a short on a 4400-4440 BISI (side space -4400), 4440 for the mirror - and the CE / quadrant stay the earlier rungs."""
    z = L.Zone("bull", 4440.0, 4400.0, 3, 2)
    assert sm3.md_far_edge(-1, z) == -4400.0
    assert sm3.md_far_edge(1, L.Zone("bear", 4440.0, 4400.0, 3, 2)) == 4440.0
    from test_management_exits import MD_ES, _md_run
    if not MD_ES:
        pytest.skip("no ES / NQ data")
    base = _md_run()
    lad = _md_run(ma_deuce_ladder=True)
    assert len(base) == len(lad) == 1 and base.entry.iloc[0] == lad.entry.iloc[0]
    assert lad.t1.iloc[0] == base.t1.iloc[0]                                  # the first rung (the CE) is the same


# --- M16-sick-sister-exit-ladder (78) ---------------------------------------------------------------------------------------------------------------

def test_sick_sister_ladder():
    """053 ~6:21: the highs 4100 / 4110 give T1 = 4100.25 (80% of the position) and T2 = the midpoint 4105 (the rest); the farther high 4110 is no rung; one high = one rung (100%).
    The sick-sister setup returns that ladder with ss_ladder, and the old list of every untaken high above the entry (kind array) without it."""
    p = Params(**BASE, ss_ladder=True)
    assert sm3.ss_ladder([4110.0, 4100.0], p) == [(4100.25, "pool"), (4105.0, "exact")]
    assert sm3.ss_fracs(2, p) == pytest.approx((0.8, 0.2)) and sm3.ss_fracs(1, p) == (1.0,)
    assert sm3.ss_ladder([4100.0], p) == [(4100.25, "pool")]
    ds = prior_days(D0, 8)
    hs = [rth_day(x, 4110.0 if k == 6 else 4100.0, 4000.0, close=4050.0) for k, x in enumerate(ds)]
    ps = Params(**BASE, sick_sister=True, sick_depth=0.5)
    rows = [(4090.0, 4090.5, 4089.5, 4090.0)] * 8
    ctx, (sl, ss) = mkctx(rows, base=4090.0, p=ps, hist=hs)
    sis, (sl2, ss2) = mkctx(rows, base=4090.0, p=ps, hist=hs)
    k = int(np.flatnonzero(sis.t[sis.start:] == 60)[0]) + sis.start
    sis.h[k] = 4101.5                                                           # the sister traded over PDH 4100 in the evening (the Side shares the array)
    ctx.pside = (sis, {1: sl2, -1: ss2}, None)
    i = ib(ctx, "09:30") + 3
    old = SM.sick_sister(ctx, sl, i, ps, "AM", 4089.9)
    on = SM.sick_sister(ctx, sl, i, replace(ps, ss_ladder=True), "AM", 4089.9)
    assert old is not None and on is not None and len(old) >= 2 and all(k_ == "array" for _, k_ in old)
    nearer, farther = old[0][0] + p.exit_before_pts, old[-1][0] + p.exit_before_pts      # (every old rung sits exit_before_pts under its high)
    assert len(on) == 2 and on[0][1] == "pool" and on[0][0] == pytest.approx(nearer + p.pool_beyond_pts)
    assert on[1][0] == pytest.approx((nearer + farther) / 2)                      # the farther high itself is no rung


# --- A15-mitigation-block-targets (82) / body hold (83) ---------------------------------------------------------------------------------------------

MB_ROWS = [(100.0, 101.0, 99.0, 100.5), (100.5, 100.8, 98.0, 98.5), (98.5, 103.0, 98.6, 102.5), (102.5, 104.0, 102.0, 103.0), (103.0, 103.2, 100.5, 101.0),
           (101.0, 101.5, 99.5, 101.2), (101.2, 105.0, 101.0, 104.8), (104.8, 105.5, 104.0, 105.0)]


class _OppConf(StubConf):
    """A Confluence stand-in with one daily array above (near edge 108) for sm2.daily_beyond / sm3.htf_level_beyond."""

    def opposing(self, t, beyond, side, tfs, src=(0,), keep_dead=False):
        return [(108.0, 109.0, 110.0, "D", 0)] if "D" in tfs and 108.0 > beyond else []


def _mb(p, conf=None):
    ctx, (sl, ss) = mkctx(MB_ROWS, base=100.0, bias=1, p=p, conf=conf, hist=hist_close(close=100.0, hi=104.5, lo=80.0))
    return ctx, sl


def test_mb_targets(monkeypatch):
    """cc04_004 ~8:13 (the long mirror of the short example): the mitigation block 102-104, the post-break extreme C 105.5 -> rung 1 = C + a tick (105.75, pool); the nearest HTF level
    (the daily array at 108) is the final rung (107.5, array); the session is done after the final fill (mb_done_at_htf)."""
    p = Params(**BASE, mitigation_entry=True, mb_targets=True, mb_done_at_htf=True)
    ctx, sl = _mb(p, _OppConf())
    cap = {}
    monkeypatch.setattr(S, "_finish_order", lambda ctx_, sd_, i_, p_, sess_, sw_, entry, stop, rm, lh, tags, **k: cap.update(entry=entry, stop=stop, fixed=k.get("fixed"), tags=tags) or "ORDER")
    i = ib(ctx, "09:30") + 7
    assert sm2.mit_order(ctx, sl, i, p, "AM", 1.0) == "ORDER"
    assert cap["entry"] == 104.0 and cap["fixed"] == [(105.75, "pool"), (107.5, "array")] and cap["tags"]["sm3"] == {"mb_done": True}
    cap.clear()
    ctx2, sl2 = _mb(p)                                                           # no HTF level beyond: the extreme is the only rung and nothing is "done"
    assert sm2.mit_order(ctx2, sl2, i, p, "AM", 1.0) == "ORDER"
    assert cap["fixed"] == [(105.75, "pool")] and "sm3" not in cap["tags"]
    cap.clear()
    ctx3, sl3 = _mb(replace(p, mb_targets=False), _OppConf())
    assert sm2.mit_order(ctx3, sl3, i, replace(p, mb_targets=False), "AM", 1.0) == "ORDER" and cap["fixed"] is None
    # the session closes with the final rung
    done = {}
    tr = SimpleNamespace(final_hit=True, session="AM")
    sm3.after_close(dict(sm3=dict(mb_done=True)), tr, done)
    assert done == {"AM": True}
    done2 = {}
    sm3.after_close(dict(sm3=dict(mb_done=True)), SimpleNamespace(final_hit=False, session="AM"), done2)
    sm3.after_close(dict(sm3=None), tr, done2)
    assert done2 == {}


def test_mb_body_hold(monkeypatch):
    """cc04_004 ~14:29: with mb_body_exit the order carries the exit level 'a body close beyond the candle body before T1' (side space: under the candle's body low 102.5), pre-T1 only;
    off: nothing. The stop is the candle's far extreme (102 - the pad) as built."""
    cap = {}
    monkeypatch.setattr(S, "_finish_order", lambda ctx_, sd_, i_, p_, sess_, sw_, entry, stop, rm, lh, tags, **k: cap.update(entry=entry, stop=stop, tags=tags) or "ORDER")
    for flag in (True, False):
        p = Params(**BASE, mitigation_entry=True, mb_body_exit=flag)
        ctx, sl = _mb(p)
        assert sm2.mit_order(ctx, sl, ib(ctx, "09:30") + 7, p, "AM", 1.0) == "ORDER"
        assert (cap["tags"].get("lvx") == {"mb_body": (102.5, True)}) is flag
        assert cap["stop"] == pytest.approx(102.0 - p.pad)


# --- new-counter-bias-scalp-exit (86) ---------------------------------------------------------------------------------------------------------------

def test_counter_scalp():
    """013 ~15:07: a bearish-bias day (htf combo -1) with the long order of scenario B (shifted so it fills under the midnight open 100.0): blocked without the switch; with it a half-risk
    scalp (tag counter_scalp) with ONE exit that is flat at the midnight open when it trades through it."""
    bias = dict(combo=-1, draw_up=float("nan"), draw_up_name="", draw_dn=90.0, draw_dn_name="PDL", react=-1, draw=-1, pd=-1)
    rows = [(o - 2.0, h - 2.0, l - 2.0, c - 2.0) for o, h, l, c in B_ROWS + AFTER]

    def go(**kw):
        p = Params(**{**B_POST, "adds": (0.5,), **kw})
        return rf_run(day(rows), history(hi=112.0, lo=88.0), p, {}, bias=bias)[0]
    assert go(htf_bias="combo") == []
    t = go(htf_bias="combo", counter_scalp=True)
    plain = rf_run(day(rows), history(hi=112.0, lo=88.0), Params(**{**B_POST, "adds": (0.5,)}), {})[0]
    assert len(t) == 1 and "counter_scalp" in t[0].lv_tags and t[0].shares == plain[0].shares // 2
    assert [(e[3], e[1]) for e in t[0].exits] == [("counter_mo", 100.0)]
    assert t[0].entry < 100.0
    # the manage rule on its own: a bar trading through the MO exits at max(open, MO) in side space; a bar that opens beyond it exits at the open
    ctx, (sl, ss) = mkctx([(99.0, 99.5, 98.5, 99.0), (99.0, 100.6, 98.9, 100.4), (100.4, 101.0, 100.0, 100.8)], base=99.0, bias=1)
    k0 = ib(ctx, "09:30")
    pos = dict(left=10, fill_i=k0, k=0, last_partial_i=-1, sm3=dict(counter_mo=100.0))
    tr = SimpleNamespace(exits=[])
    sm3.manage(ctx, sl, pos, tr, k0 + 1, ctx.idx[k0 + 1], Params(**BASE))
    assert [(e[3], e[1], e[2]) for e in tr.exits] == [("counter_mo", 100.0, 10)] and pos["left"] == 0
    pos2 = dict(left=10, fill_i=k0, k=0, last_partial_i=-1, sm3=dict(counter_mo=100.0))
    tr2 = SimpleNamespace(exits=[])
    sm3.manage(ctx, sl, pos2, tr2, k0 + 2, ctx.idx[k0 + 2], Params(**BASE))
    assert tr2.exits[0][1] == 100.4                                              # opened above the MO: out at the open


# --- M4-immediate-response-swept-extreme (88) -------------------------------------------------------------------------------------------------------

def test_sweep_linger():
    """cc05_005 ~14:40: three closes under the swept level L1 before the MSS void the setup (sweep_max_linger 2); one close under and a reclaim keep it; the scenario-B sweep (4 closes under
    the pre-market low before its MSS) is dropped at 3 and kept at 4 / off."""
    sd3 = sd_of([(100.5, 101.0, 99.0, 99.5), (99.5, 100.0, 98.5, 99.0), (99.0, 99.5, 98.0, 99.2), (99.2, 100.5, 99.1, 100.4)])
    sw = dict(session="AM", key="pdl1", level=100.0, ext=98.0, ext_i=2, sweep_i=0, broke=None)
    p = Params(**BASE, sweep_max_linger=2)
    swv = dict(sw)
    assert sm3.sweep_step(stub(4), sd3, swv, 2, p) == "drop" and swv["ob_void"] is True          # closes at 99.5, 99.0, 99.2; a pending OB order dies with it
    assert sm3.sweep_step(stub(4), sd3, dict(sw), 1, p) is None                                  # two closes so far
    sd1 = sd_of([(100.5, 101.0, 99.0, 99.5), (99.5, 101.5, 99.4, 101.2), (101.2, 101.5, 100.5, 101.0)])
    assert sm3.sweep_step(stub(3), sd1, dict(sw), 2, p) is None                                  # one close under, then a reclaim
    assert sm3.sweep_step(stub(4), sd3, dict(sw, broke=3), 2, p) is None                         # after the MSS the count no longer applies
    assert sm3.sweep_step(stub(4), sd3, dict(sw), 2, replace(p, sweep_max_linger=0)) is None
    base = dict(B_POST, adds=(0.5,))
    for n, want_n in ((0, 1), (4, 1), (3, 0), (1, 0)):
        t = rf_run(day(B_ROWS + AFTER), history(hi=112.0, lo=88.0), Params(**{**base, "sweep_max_linger": n}), {})[0]
        assert len(t) == want_n, n


# --- X9-repeated-array-taps (101) -------------------------------------------------------------------------------------------------------------------

TAP_ROWS = [(100.5, 103.0, 100.4, 102.8), (102.8, 103.0, 100.5, 101.5), (101.5, 102.5, 101.2, 102.0), (102.0, 102.6, 101.5, 102.2), (102.2, 102.4, 100.8, 101.3),
            (101.3, 102.9, 101.2, 102.8), (102.8, 104.0, 102.5, 103.8), (103.8, 104.0, 100.9, 101.2), (101.2, 102.0, 101.1, 101.8), (101.8, 102.2, 101.5, 102.0)]


def test_breaker_taps():
    """048 ~32:51: the entry breaker 100-101 (MSS bar 0): taps are bars that enter it whose next bar closes above it. Tap 2 starts a 2-bar window that must trade above the nearest opposing FVG
    (103.6) without a low under the tap-2 low (100.8): satisfied at bar 6, not yet at bar 5; a 3rd tap marks the breaker worn (no entry). breaker_max_taps_for_entry 0 = no gate."""
    p = Params(**BASE, breaker_max_taps_for_entry=2)
    ctx, (sl, ss) = mkctx(TAP_ROWS, base=100.5, bias=1, p=p)
    k0 = ib(ctx, "09:30")
    sl.opposing = lambda: [L.Zone("bear", 103.6, 103.5, k0, k0)]
    sw = dict(session="AM", key="x", level=99.0, ext=99.0, ext_i=k0, sweep_i=k0, broke=k0)
    assert sm3.breaker_taps(ctx, sl, sw, k0 + 5, p, 101.0, 100.0) == (2, False)
    assert sm3.breaker_taps(ctx, sl, sw, k0 + 6, p, 101.0, 100.0) == (2, True)
    assert sm3.breaker_taps(ctx, sl, sw, k0 + 9, p, 101.0, 100.0)[0] == 3
    assert sm3.breaker_taps(ctx, sl, sw, k0 + 3, p, 101.0, 100.0) == (1, None)
    tags = dict(entry_kind="breaker", bz_side=(101.0, 100.0))
    sw1 = dict(sw, ext_i=k0 + 1)
    assert sm3.order_gate3(ctx, sl, sw1, k0 + 5, p, 101.0, 99.0, "AM", [], {}, dict(tags)) == "x_breaker_tap2"
    assert sm3.order_gate3(ctx, sl, sw1, k0 + 6, p, 101.0, 99.0, "AM", [], {}, dict(tags)) is None
    lvt = []
    assert sm3.order_gate3(ctx, sl, sw1, k0 + 9, p, 101.0, 99.0, "AM", lvt, {}, dict(tags)) == "x_breaker_worn" and "breaker_worn" in lvt
    assert sm3.order_gate3(ctx, sl, sw1, k0 + 9, replace(p, breaker_max_taps_for_entry=0), 101.0, 99.0, "AM", [], {}, dict(tags)) is None
    assert sm3.order_gate3(ctx, sl, sw1, k0 + 9, p, 101.0, 99.0, "AM", [], {}, dict(entry_kind="fvg")) is None        # not a breaker entry


# --- M5-lasthour-draw-frozen-noon (1) ---------------------------------------------------------------------------------------------------------------

def test_lh_draw_frozen_at_noon():
    """001 ~28:39: with lh_draw_freeze the own last-hour slot locks at 12:00 (the AM lock while it stands). An LH draw frozen at 4010 stays 4010 when a nearer high forms at 13:40 (the 15:20
    long targets 4010); when 4010 trades at 14:30 the slot is done (no LH trade); an AM draw already delivered before noon is not carried (the noon mark-up is)."""
    p = Params(**BASE, last_hour_own_slot=True, lh_draw_freeze=True, draw_lock="session")
    assert S._lock_times(p, D0, [])["LH"] == 720 and S._lock_times(replace(p, lh_draw_freeze=False), D0, [])["LH"] == 900
    assert 720 in B.lock_cuts(p) and 900 not in B.lock_cuts(p) and 900 in B.lock_cuts(replace(p, lh_draw_freeze=False))
    hs = [rth_day(x, 4010.0, 3900.0, close=3995.0) for x in prior_days(D0, 8)]

    def lock_run(bar_hi=None):
        rows = [(3995.0, 3996.0, 3994.0, 3995.0)] * 4 * 12 + [(3995.0, 3996.0, 3994.0, 3995.0)] * 90          # 09:30 .. 17:00 flat
        ctx, (sl, ss) = mkctx(rows, base=3995.0, p=p, hist=hs)
        for hhmm, hi in (bar_hi or {}).items():
            ctx.h[ib(ctx, hhmm)] = hi
        lock_t = S._lock_times(p, D0, [])
        done, spent, allk = {"AM": False, "PM": False, "LH": False}, [], []
        out = {}
        marks = {ib(ctx, hhmm): hhmm for hhmm in ("09:30", "12:00", "13:40", "14:30", "15:20")}
        for j in range(ib(ctx, "09:30"), ib(ctx, "15:20") + 1):                              # every closed bar goes through _lock_step in the engine
            S._lock_step(ctx, p, lock_t, j, int(ctx.t[j]), {}, done, spent, allk, None)
            if j in marks:
                out[marks[j]] = dict(ctx.lock["LH"]) if "LH" in ctx.lock else None
        return ctx, done, out
    ctx, done, out = lock_run({"13:40": 4004.0})
    assert out["09:30"] is None and ctx.lock["AM"]["target"] == 4010.0
    assert out["12:00"]["target"] == 4010.0 and out["13:40"]["target"] == 4010.0 and out["15:20"]["target"] == 4010.0      # frozen at noon
    assert out["15:20"]["session"] == "LH" and not out["15:20"]["delivered"] and done["LH"] is False
    ctx2, done2, out2 = lock_run({"14:30": 4010.5})
    assert out2["13:40"]["target"] == 4010.0 and out2["14:30"]["delivered"] and done2["LH"] is True                           # traded before 15:00: the slot is done
    ctx3, done3, out3 = lock_run({"11:00": 4010.5})
    assert ctx3.lock["AM"]["delivered"] and out3["12:00"]["target"] != 4010.0 or out3["12:00"]["side"] == 0                   # the delivered AM draw is not carried over
    # a run_day day reports the LH lock at 12:00
    rows = [(o, h, l, c) for o, h, l, c in [(100.0, 100.3, 99.9, 100.1)] * 40]
    tr, locks, log, skips = rf_run(day(rows), history(hi=112.0, lo=88.0), Params(**BASE, last_hour_own_slot=True, lh_draw_freeze=True), {})
    assert [lk["t_lock"] for lk in locks if lk["session"] == "LH"] == [720]


# --- M1-three-entry-plans (2) -----------------------------------------------------------------------------------------------------------------------

def test_mm_plan_variants():
    """003 ~1:28:27: mm_plan forces the paths it names (full: OB before the break + the MM draw; mss_scalp: after the MSS; pyramid: OB before the break + adds on each imbalance); one exit
    at the draw (full) / at the first relative equal highs (mss_scalp) / pool rungs only (pyramid); one synthetic day run three times differs by entry kind and exit count."""
    f, m, y = Params(**BASE, mm_plan="full"), Params(**BASE, mm_plan="mss_scalp"), Params(**BASE, mm_plan="pyramid")
    assert (f.ob_entry, f.mmxm_ctx, m.ob_entry, y.ob_entry, y.add_on_vi) == ("pre_break", True, "post_mss", "pre_break", True)
    assert replace(m, ob_entry="both").ob_entry == "post_mss"                       # replace() re-runs the umbrella
    with pytest.raises(ValueError):
        Params(mm_plan="x")
    keep = [(101.0, "array"), (102.0, "pool"), (104.0, "pool_eq"), (106.0, "array")]
    assert sm3.mm_plan_exit(f, keep, [104.0], 100.0, 1.0, 106.0) == (True, 106.0, keep)
    se, draw, k2 = sm3.mm_plan_exit(m, keep, [104.0, 105.0], 100.0, 1.0, 106.0)
    assert se is True and draw == pytest.approx(104.25) and k2 == keep
    assert sm3.mm_plan_exit(m, keep, [], 100.0, 1.0, 106.0)[0] is False             # no equal highs above: the normal ladder
    assert sm3.mm_plan_exit(y, keep, [], 100.0, 1.0, 106.0)[2] == [(102.0, "pool"), (104.0, "pool_eq")]
    assert sm3.mm_plan_exit(Params(), keep, [], 100.0, 1.0, 106.0)[0] is False
    out = {}
    for plan in ("full", "mss_scalp", "pyramid"):
        t = rf_run(day(B_ROWS + AFTER), history(hi=112.0, lo=88.0), Params(**{**B_POST, "adds": (0.5,), "mm_plan": plan}), {})[0]
        out[plan] = [(x.entry_kind, len(x.exits)) for x in t]
    assert out["full"] == [("ob_pre", 1)] and out["pyramid"][0][0] == "ob_pre" and out["mss_scalp"][0][0] == "fvg"


# --- M4-unicorn-sequence-preopen-breaker (3) --------------------------------------------------------------------------------------------------------

PRE_ROWS = [(100.0, 100.6, 99.8, 100.4), (100.4, 100.5, 99.0, 99.2), (99.4, 100.2, 99.3, 100.0), (100.0, 101.0, 99.9, 100.2), (100.2, 100.8, 99.5, 99.7),
            (99.7, 99.9, 98.0, 98.3), (98.3, 99.5, 98.2, 99.4), (99.4, 101.8, 99.3, 101.6)]


def test_unicorn_preopen_back_inside():
    """007 ~15:27 / ~11:34: the bullish breaker formed on the 5m chart before 09:30 (the up-close candle's range) is the unicorn's breaker after the open; the sweep at 09:30 under it, then a
    bar trading back inside the zone within unicorn_back_bars (09:40) - only then does a gap overlapping the zone arm. No reclaim in 15 bars: no unicorn."""
    p = Params(**BASE, unicorn_preopen=True, pivot_n=1)
    flat = [(101.6, 101.7, 101.5, 101.6)] * 16

    def mk(post):
        ctx, (sl, ss) = mkctx(PRE_ROWS + flat + post, base=100.0, start="07:30", p=p, hist=hist_close(close=100.0, hi=130.0, lo=90.0))
        return ctx, sl
    reclaim = [(101.0, 101.2, 98.5, 98.9), (98.9, 99.0, 98.6, 98.8), (98.8, 100.9, 98.7, 100.6), (100.6, 100.8, 100.2, 100.5)]
    ctx, sl = mk(reclaim)
    i, k930 = ib(ctx, "09:40"), ib(ctx, "09:30")
    z = sm3.preopen_zone(ctx, sl, i, p)
    assert z is not None and z.bottom > 99.0 and z.top <= 101.8
    sw = dict(session="AM", key="rel_eq_lows0", level=99.0, ext=98.5, ext_i=k930, sweep_i=k930, broke=None)
    g = L.Zone("bull", z.top + 0.1, z.bottom + 0.05, i, i - 2)
    zz, uni = sm3.preopen_unicorn(ctx, sl, sw, i, p, [g])
    assert zz is z and uni == [g]
    assert sm3.preopen_unicorn(ctx, sl, sw, i, p, [L.Zone("bull", z.top + 0.1, z.bottom + 0.05, k930 + 1, k930 - 1)])[1] == []        # formed before the reclaim
    assert sm3.preopen_unicorn(ctx, sl, dict(sw, ext=z.bottom + 0.5), i, p, [g])[1] == []                                              # the sweep must run under the zone
    ctx2, sl2 = mk([(101.0, 101.2, 98.5, 98.9)] + [(98.9, 99.0, 98.6, 98.8)] * 20)
    i2 = ib(ctx2, "09:30") + 18
    sw2 = dict(sw, ext_i=ib(ctx2, "09:30"), sweep_i=ib(ctx2, "09:30"))
    assert sm3.preopen_unicorn(ctx2, sl2, sw2, i2, p, [g])[1] == []                                                                  # no reclaim in 15 bars
    assert sm3.preopen_unicorn(ctx2, sl2, sw2, i2, replace(p, unicorn_back_bars=40), [L.Zone("bull", z.top + 0.1, z.bottom + 0.05, i2, i2 - 2)])[1] == []        # (still under the zone)


# --- M4-accumulate-in-breaker-needs-bias-draw (4) ---------------------------------------------------------------------------------------------------

def test_breaker_entry_needs_lock():
    """007 ~21:34: an entry inside a breaker (100-101) needs the session bias with it AND a named draw beyond it: no lock / no draw = no order; a bullish lock above (or the htf.table
    draw) = the order; an entry above the breaker is not an 'inside' entry; the add path honours the same flag."""
    p = Params(**BASE, breaker_need_bias_draw=True)
    ctx, (sl, ss) = mkctx(TAP_ROWS, base=100.5, bias=1, p=p)
    k0 = ib(ctx, "09:30")
    sw = dict(session="AM", key="x", level=99.0, ext=99.0, ext_i=k0, sweep_i=k0, broke=k0)
    tags = lambda: dict(entry_kind="breaker", bz_top=101.0, bz_bottom=100.0)
    assert sm3.order_gate3(ctx, sl, sw, k0 + 5, p, 100.5, 99.0, "AM", [], {}, tags()) == "x_breaker_no_draw"
    ctx.cur_lock = dict(side=1, target=106.0, kind="pool", name="pdh1", marked=[])
    t1 = tags()
    assert sm3.order_gate3(ctx, sl, sw, k0 + 5, p, 100.5, 99.0, "AM", [], {}, t1) is None and t1["sm3"]["bd_ok"] is True
    ctx.cur_lock = dict(side=1, target=100.9, kind="pool", name="x", marked=[])        # a draw that is not above the zone
    assert sm3.order_gate3(ctx, sl, sw, k0 + 5, p, 100.5, 99.0, "AM", [], {}, tags()) == "x_breaker_no_draw"
    ctx.cur_lock = None
    ctx.bias_row = dict(draw_up=106.0, draw_up_name="D_fvg", draw_dn=float("nan"), draw_dn_name="")
    assert sm3.order_gate3(ctx, sl, sw, k0 + 5, p, 100.5, 99.0, "AM", [], {}, tags()) is None
    ctx.cur_bias = 0
    assert sm3.order_gate3(ctx, sl, sw, k0 + 5, p, 100.5, 99.0, "AM", [], {}, tags()) == "x_breaker_no_draw"                      # no session bias
    ctx.cur_bias = 1
    ctx.bias_row = None
    assert sm3.order_gate3(ctx, sl, sw, k0 + 5, p, 102.0, 99.0, "AM", [], {}, tags()) is None                                      # above the breaker: not an accumulation
    assert sm3.order_gate3(ctx, sl, sw, k0 + 5, replace(p, breaker_need_bias_draw=False), 100.5, 99.0, "AM", [], {}, tags()) is None
    pos = dict(bz_side=(101.0, 100.0), sm3=dict(bd_ok=False))
    assert SM.add_ok(sl, pos, 100.5, k0 + 6, p) is False and SM.add_ok(sl, dict(pos, sm3=dict(bd_ok=True)), 100.5, k0 + 6, p) is True
    assert SM.add_ok(sl, pos, 100.5, k0 + 6, replace(p, breaker_need_bias_draw=False)) is True


# --- M1-sell-model-fail-to-reach-CE (5) -------------------------------------------------------------------------------------------------------------

CE_ROWS = [(97.0, 97.1, 96.0, 96.2), (96.2, 97.4, 96.1, 97.3), (96.9, 97.0, 96.8, 96.9), (96.9, 97.0, 96.5, 96.7), (96.7, 98.2, 96.6, 98.0), (98.0, 99.5, 98.0, 99.3),
           (99.3, 99.4, 98.6, 98.8), (98.8, 98.9, 98.2, 98.3), (98.3, 100.2, 98.2, 100.0), (100.0, 100.1, 98.8, 99.3)]


def test_ce_fail_sell(monkeypatch):
    """007 ~20:36 (the long mirror of the sell model): two MSS up from the low 96.0 leave the BISI 98.2-98.6 (CE 98.4); the pullback candle that reaches 0.4 of it (low 98.5) and closes up is
    the entry at market on that candle (fill = the next open, stop under the BISI); a candle that reaches the CE (98.35) is not; once per imbalance."""
    p = Params(**BASE, ce_fail_entry=True, pivot_n=1)
    cap = {}
    monkeypatch.setattr(S, "_finish_order", lambda ctx_, sd_, i_, p_, sess_, sw_, entry, stop, rm, lh, tags, **k: cap.update(entry=entry, stop=stop, tags=tags) or "ORDER")
    for low, want in ((98.5, "ORDER"), (98.35, None)):
        ctx, (sl, ss) = mkctx(CE_ROWS + [(98.8, 99.4, low, 99.1)], base=97.0, bias=1, p=p)
        i = ib(ctx, "09:30") + 10
        assert sm3.mss_breaks(ctx, sl, ctx.start + int(np.argmin(sl.l[ctx.start:i + 1])), i) == [ib(ctx, "09:30") + 4, ib(ctx, "09:30") + 8]
        assert sm3.ce_fail_order(ctx, sl, i, p, "AM", 1.0) == want
        if want:
            assert cap["entry"] == pytest.approx(99.1) and cap["stop"] == pytest.approx(98.2 - p.pad) and cap["tags"]["market"] is True
            assert sm3.ce_fail_order(ctx, sl, i, p, "AM", 1.0) is None                       # once per imbalance
    ctx, (sl, ss) = mkctx(CE_ROWS[:8] + [(98.8, 99.4, 98.5, 99.1)], base=97.0, bias=1, p=p)    # only one MSS so far
    assert sm3.ce_fail_order(ctx, sl, ib(ctx, "09:30") + 8, p, "AM", 1.0) is None
    ctx, (sl, ss) = mkctx(CE_ROWS + [(98.8, 99.4, 98.5, 99.1)], base=97.0, bias=1, p=p, conf=StubConf())     # no 1h+ array at the leg origin
    assert sm3.ce_fail_order(ctx, sl, ib(ctx, "09:30") + 10, p, "AM", 1.0) is None
    ctx, (sl, ss) = mkctx(CE_ROWS + [(98.8, 99.4, 98.5, 99.1)], base=97.0, bias=1, p=p, conf=StubConf(at_tfs={1: ["1h"]}))
    assert sm3.ce_fail_order(ctx, sl, ib(ctx, "09:30") + 10, p, "AM", 1.0) == "ORDER"


# --- M1-inside-fvg-expansion-only (8) ---------------------------------------------------------------------------------------------------------------

def test_expansion_ce_entry():
    """009 ~3:49: a single-expansion day (the locked draw is the prior high 112, 12 points from the open, inside ADR5): the entry is the FVG CE (lower than the edge entry) and 65% exits at
    the draw, the rest at the next level (the day-before high 118); off: the edge entry and one exit at the draw."""
    ext = [(108.8, 113.0, 108.5, 112.8), (112.8, 119.0, 112.5, 118.5)]
    hs = history(highs=[112.0] * 6 + [118.0, 112.0], lows=[80.0] * 8)

    def go(**kw):
        p = Params(**{**B_POST, "adds": (0.5,), "draw_lock": "session", **kw})
        return rf_run(day(list(B_ROWS + AFTER) + ext), hs, p, {})[0]
    off, on = go(), go(expansion_ce_entry=True)
    assert len(off) == len(on) == 1 and on[0].entry < off[0].entry
    assert [(e[3], e[1]) for e in off[0].exits] == [("t1", 112.25)]
    assert [(e[3], e[1]) for e in on[0].exits] == [("t1", 112.25), ("t2", 118.25)]
    n = on[0].shares
    assert on[0].exits[0][2] == int(n * 0.65) or abs(on[0].exits[0][2] - 0.65 * n) <= 1
    assert sm3.single_expansion(SimpleNamespace(cur_lock=None, opens={}), None) is False
    ctx = SimpleNamespace(cur_lock=dict(side=1, name="pdh1", target=112.0), opens={"0930": 100.0}, hist=hs)
    assert sm3.single_expansion(ctx, None) is True
    ctx.cur_lock = dict(side=1, name="pdh1", target=140.0)
    assert sm3.single_expansion(ctx, None) is False                                   # farther than ADR5 (24)
    ctx.cur_lock = dict(side=1, name="org_far", target=105.0)
    assert sm3.single_expansion(ctx, None) is False                                   # an array, not a daily level


# --- M7-pm-1330-judas-full (9) ----------------------------------------------------------------------------------------------------------------------

def test_pm_judas_lunch_fvg():
    """010 ~57:47: a 5m bullish FVG formed in the lunch hour (12:35-12:45: 4001-4002) under the 13:30 open is one more array pm_judas_array accepts (its top 4002 becomes the PM Judas pool)
    with pm_lunch_fvg_array; a closed-through one is not. pm_need_htf_target: the PM order needs an undelivered daily-level target (htf.table) beyond the entry."""
    lunch = [(4000.0, 4000.5, 3999.5, 4000.0)] * 7 + [(4000.0, 4001.0, 3999.0, 4000.5), (4000.5, 4004.0, 4000.4, 4003.8), (4003.8, 4005.0, 4002.0, 4004.0)] + [(4004.0, 4004.5, 4003.0, 4004.0)] * 8
    pm = [(4010.0, 4011.0, 4009.0, 4010.0)] * 4 + [(4010.0, 4010.5, 4004.5, 4005.0)] * 4
    p = Params(**BASE, pm_judas_array=True)
    ctx, (sl, ss) = mkctx(lunch + pm, base=4000.0, bias=1, start="12:00", p=p, hist=hist_close(close=4000.0, hi=4130.0, lo=3900.0))
    i = ib(ctx, "13:50")
    ref = float(ctx.opens["1330"])
    assert sm3.lunch_fvg_tops(ctx, sl, i - 1, ref) == [4002.0]
    out0, out1 = {}, {}
    SM.extra_pools(ctx, sl, "PM", i, p, out0)
    SM.extra_pools(ctx, sl, "PM", i, replace(p, pm_lunch_fvg_array=True), out1)
    assert "pm_judas_array" not in out0 and out1["pm_judas_array"] == 4002.0
    ctx2, (sl2, _) = mkctx(lunch[:9] + [(4003.8, 4003.9, 3999.0, 4000.0)] + lunch[10:] + pm, base=4000.0, bias=1, start="12:00", p=p, hist=hist_close(close=4000.0, hi=4130.0, lo=3900.0))
    assert sm3.lunch_fvg_tops(ctx2, sl2, ib(ctx2, "13:50") - 1, float(ctx2.opens["1330"])) == []                       # closed through
    # the HTF target gate
    pn = replace(p, pm_need_htf_target=True)
    ctx.bias_row = dict(draw_up=4100.0, draw_up_name="D_fvg", draw_dn=3950.0, draw_dn_name="D_swing_low")
    assert sm3.pm_htf_target_ok(ctx, sl, i, pn, "PM", 4005.0) is True and sm3.pm_htf_target_ok(ctx, ss, i, pn, "PM", -4005.0) is True
    sw = dict(session="PM", key="lunch", level=4000.0, ext=3999.0, ext_i=i - 2, sweep_i=i - 2, broke=i - 1)
    assert sm3.order_gate3(ctx, sl, sw, i, pn, 4005.0, 4000.0, "PM", [], {}, {}) is None
    ctx.bias_row = dict(draw_up=4100.0, draw_up_name="4h_fvg", draw_dn=3950.0, draw_dn_name="4h_fvg")                     # not a daily-level target
    assert sm3.order_gate3(ctx, sl, sw, i, pn, 4005.0, 4000.0, "PM", [], {}, {}) == "x_pm_no_htf_target"
    ctx.bias_row = dict(draw_up=4005.0, draw_up_name="D_fvg", draw_dn=3950.0, draw_dn_name="D_swing_low")                  # the target was reached already
    assert sm3.order_gate3(ctx, sl, sw, i, pn, 4003.0, 4000.0, "PM", [], {}, {}) == "x_pm_no_htf_target"
    ctx.bias_row = None
    assert sm3.order_gate3(ctx, sl, sw, i, pn, 4005.0, 4000.0, "PM", [], {}, {}) == "x_pm_no_htf_target"
    assert sm3.order_gate3(ctx, sl, sw, i, pn, 4005.0, 4000.0, "AM", [], {}, {}) is None                                   # the AM is not gated


# --- M1M2-htf-array-replaces-sweep (10) -------------------------------------------------------------------------------------------------------------

def test_htf_array_premise_no_sweep():
    """011 ~8:49: price taps a 60m array (4040-4050) with its bodies holding and no pool taken: a pseudo-sweep (key htf_array) once per array; a body closing under the array voids it. Off: no
    sweep. The 15m / 60m arrays are the ones read."""
    arr = {1: [(4050.0, 4040.0, "1h", 0, 0)]}
    rows = [(4062.0, 4063.0, 4060.0, 4061.0)] * 3 + [(4061.0, 4061.5, 4049.0, 4052.0)] + [(4052.0, 4053.0, 4051.0, 4052.5)] * 2 + [(4052.0, 4052.5, 4036.0, 4038.0)]
    p = Params(**BASE, allow_htf_array_premise=True)
    ctx, (sl, ss) = mkctx(rows, base=4062.0, p=p, conf=StubConf(arrays=arr), hist=hist_close(close=4062.0, hi=4130.0, lo=3900.0))
    k0 = ib(ctx, "09:30")
    assert sm3.premise_sweep(ctx, sl, k0 + 2, p, "AM") is None                                  # the bar above the array
    sw = sm3.premise_sweep(ctx, sl, k0 + 3, p, "AM")
    assert sw is not None and sw["key"] == "htf_array" and sw["level"] == 4050.0 and sw["ext"] == 4049.0 and sw["arr_bot"] == 4040.0
    assert sm3.premise_sweep(ctx, sl, k0 + 3, p, "AM") is None                                  # once per array
    assert sm3.sweep_step(ctx, sl, dict(sw), k0 + 4, p) is None
    assert sm3.sweep_step(ctx, sl, dict(sw), k0 + 6, p) == "drop"                                 # a body closed under the array
    ctx2, (sl2, _) = mkctx(rows, base=4062.0, p=p, conf=StubConf(arrays={1: [(4050.0, 4040.0, "4h", 0, 0)]}), hist=hist_close(close=4062.0))
    assert sm3.premise_sweep(ctx2, sl2, k0 + 3, replace(p, premise_tfs=(15, 60)), "AM") is None    # a 4h array is not one of the premise timeframes
    lvt = []
    sm3.order_gate3(ctx, sl, sw, k0 + 5, p, 4052.0, 4040.0, "AM", lvt, {}, {})
    assert "premise_array" in lvt


# --- the specs that were already built --------------------------------------------------------------------------------------------------------------

def test_already_built_specs_have_their_switches_and_variants():
    """X3-hs-fade-targets (64: levels_detectors#3 hs_fade, T1 = the right shoulder, T2 above the head), LLT3-judas-depth-third-adr (162: judas_max_adr / judas_depth_tag),
    LLT3-consolidation-lunch-vs-am-extreme (173: profile_consol_pm) need no new switch; the study variants name them."""
    f = Params.__dataclass_fields__
    assert {"hs_fade", "judas_max_adr", "judas_depth_tag", "profile_consol_pm", "md_ladder"} <= set(f)
    for g in ("X3-hs-fade-targets", "LLT3-judas-depth-third-adr", "LLT3-consolidation-lunch-vs-am-extreme"):
        Params(**study.DECISIONS[g])
    assert study.DECISIONS["LLT3-judas-depth-third-adr"]["judas_max_adr"] == 0.33
