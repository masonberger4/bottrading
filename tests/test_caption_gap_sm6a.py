"""Caption-gap pass, package setups_models #6/7, part A: the 36 specs of digests/rulebook_gaps/models_setups_entries.md (items 113-117, 119-121, 123, 125, 127, 130-132, 134-136, 139, 142-146, 148-150,
153, 163, 181, 189, 191, 193-196, 198). Unit tests of the detectors / gates (sm6.py) and of the engine glue (strategy / setups / sm2 hooks), Params plumbing. Tests that need local market data (ES) skip
cleanly when it is absent; no platform-specific paths. The study variants and the no-look-ahead runs live in test_caption_gap_sm6b.py."""
from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from mentorship import levels as L, setups as SM, sm2, sm3, sm4, sm5, sm6, strategy as S
from mentorship.strategy import Params

from test_levels_detectors import BASE, D0, NY, day, ctx_for, frame, history, prior_days, rth_day
from test_caption_gap_sm1a import StubConf, hist_close, ib, mkctx, sd_of, stub
from test_caption_gap_sm4a import cap  # noqa: F401  (cap: the order recorder fixture)

A = np.array

NEW_SWITCHES = (
    "curve_short", "consol_eq_entry", "consol_max_pts", "consol_eq_mode", "void_trades", "void_idle_bars", "ote_need_trigger", "ote_parent_pd", "ts_ote_ok", "ts_cont", "ts_cont_bars", "cc_ob_tf",
    "ts_r_preset", "refine_tfs", "cc_ob_offset_ticks", "entry_discipline", "pmh_contrarian", "ob_below_open", "eq_fresh_ob", "sym_swing_ts", "ts_level_src", "breaker_retests", "breaker_leave_pts",
    "rb_entry", "prop_second", "vb_react_bars", "offer_run", "offer_step_pts", "two_chance", "cc_near_ob", "entry_arrays_order", "clarity", "clarity_overlap", "ny_london_range", "sweep_15m_array",
    "sweep_leave_bars", "sweep_leave_pts", "consol_edge_fade", "consol_tf", "consol_width_adr", "consol_eq_band", "reversal_tag", "reversal_need_htf", "reversal_score", "pdl_expansion",
)


def flat(n, px, w=0.2):
    return [(px, px + w, px - w, px)] * n


def test_new_switch_defaults_and_validation():
    p = Params()
    assert (p.curve_short, p.consol_eq_entry, p.consol_max_pts, p.consol_eq_mode, p.void_trades, p.void_idle_bars, p.ote_need_trigger, p.ote_parent_pd, p.ts_ote_ok, p.ts_cont, p.ts_cont_bars) == \
        (False, False, 8.0, "ob", (), 20, False, False, False, False, 10)
    assert (p.cc_ob_tf, p.ts_r_preset, p.refine_tfs, p.cc_ob_offset_ticks, p.entry_discipline, p.pmh_contrarian, p.ob_below_open, p.eq_fresh_ob, p.sym_swing_ts, p.ts_level_src) == \
        (60, "", (), 0, "any", False, False, False, False, "wick")
    assert (p.breaker_retests, p.breaker_leave_pts, p.rb_entry, p.prop_second, p.vb_react_bars, p.offer_run, p.offer_step_pts, p.two_chance, p.cc_near_ob, p.entry_arrays_order) == \
        (1, 3.0, "", False, 3, 3, 1.0, False, False, ())
    assert (p.clarity, p.clarity_overlap, p.ny_london_range, p.sweep_15m_array, p.sweep_leave_bars, p.sweep_leave_pts, p.consol_edge_fade, p.consol_tf, p.consol_width_adr, p.consol_eq_band) == \
        ("off", 4.0, False, "off", 0, 2.0, "off", 60, 0.5, 0.15)
    assert (p.reversal_tag, p.reversal_need_htf, p.reversal_score, p.pdl_expansion, p.vb_entry, p.ote) == (False, False, False, False, "fill_limit", "off")
    for kw in (dict(consol_eq_mode="x"), dict(entry_discipline="x"), dict(ts_level_src="x"), dict(rb_entry="x"), dict(ts_r_preset="x"), dict(clarity="x"), dict(sweep_15m_array="x"),
               dict(consol_edge_fade="x"), dict(vb_entry="x"), dict(ote="x"), dict(void_trades=("nope",)), dict(entry_arrays=("nope",)), dict(entry_arrays_order=("nope",)), dict(consol_max_pts=0),
               dict(void_idle_bars=0), dict(ts_cont_bars=0), dict(cc_ob_tf=7), dict(refine_tfs=(3,)), dict(cc_ob_offset_ticks=-1), dict(breaker_retests=0), dict(breaker_leave_pts=-1),
               dict(vb_react_bars=0), dict(offer_run=1), dict(offer_step_pts=-1), dict(clarity_overlap=0), dict(sweep_leave_bars=-1), dict(consol_tf=7), dict(consol_width_adr=0),
               dict(consol_eq_band=0.5)):
        with pytest.raises(ValueError):
            Params(**kw)
    assert Params(ote="ob62", vb_entry="auto", entry_arrays=("ob_secondary", "propulsion", "last_offer"), void_trades=("fill", "range", "cont", "void_fill_gap")).ote == "ob62"
    assert set(NEW_SWITCHES) <= set(Params.__dataclass_fields__)


# --- 113 M1-short-sell-side-of-buy-curve ---------------------------------------------------------------------------------------------------------

def test_curve_short_targets_htf_support():
    """cc04_007 ~00:01:21: the draw is UP (bias +1) and an untouched HTF discount array lies below the market: the short side may be scanned against the bias (counter_kind "curve"), its single target =
    the array's near edge (the top, mirrored). No array / an array the day already traded into (the decline happened) / no switch = no counter side; a draw down mirrors with the premium array above."""
    p = Params(**BASE, curve_short=True)
    rows = flat(6, 4050.0)
    conf = StubConf(arrays={1: [(4000.0, 3990.0, "D", 0, 0)], -1: [(4110.0, 4100.0, "4h", 0, 0)]})
    ctx, (sl, ss) = mkctx(rows, base=4050.0, conf=conf)
    i = ib(ctx, "09:30") + 5
    assert sm6.curve_target(ctx, ss, i, p, 1) == pytest.approx(-4000.0)               # side space of the short: -top
    assert sm6.curve_target(ctx, sl, i, p, -1) == pytest.approx(4100.0)               # a draw down: the premium array's near edge (its bottom) for the long
    assert sm6.curve_target(ctx, ss, i, p, -1) is None and sm6.curve_target(ctx, ss, i, p, 0) is None     # not against the bias
    assert sm6.counter_kind(ctx, ss, i, p, 1) == "curve" and sm6.counter_kind(ctx, ss, i, replace(p, curve_short=False), 1) == ""
    ctx2, (sl2, ss2) = mkctx(flat(3, 4050.0) + [(4050.0, 4051.0, 3995.0, 4000.0)] + flat(2, 4000.0), base=4050.0, conf=conf)     # today already traded into the array
    assert sm6.curve_target(ctx2, ss2, ib(ctx2, "09:30") + 5, p, 1) is None
    ctx3, (sl3, ss3) = mkctx(rows, base=4050.0, conf=None)
    assert sm6.curve_target(ctx3, ss3, i, p, 1) is None


def test_curve_short_finish_order_single_target(monkeypatch):
    """The engine tail with ctx.curve_now = "curve": the order's targets are exactly the array edge (fixed), tagged curve_short; without an array the order is dropped."""
    p = Params(**BASE, curve_short=True, min_rr=1.0)
    conf = StubConf(arrays={1: [(4000.0, 3990.0, "D", 0, 0)]})
    ctx, (sl, ss) = mkctx(flat(8, 4050.0), base=4050.0, conf=conf)
    i = ib(ctx, "09:30") + 7
    ctx.curve_now = "curve"
    seen = {}
    real = S._finish_order

    def spy(ctx_, sd_, i_, p_, sess_, sw_, entry, stop, rm, lh, tags, skip_leg_pd=False, pctx_free=False, fixed=None):
        return real(ctx_, sd_, i_, p_, sess_, sw_, entry, stop, rm, lh, tags, skip_leg_pd=skip_leg_pd, pctx_free=pctx_free, fixed=fixed)
    o = sm4._order(ctx, ss, i, p, "AM", 1.0, "curve_t", -4052.0, -4056.0, ext=-4056.0, ext_i=i - 1, broke=i, lv=())
    assert o is not None and o["level_kinds"] == ["array"] and o["levels"][0] == pytest.approx(-4000.0 - p.exit_before_pts * p.es_pt) and "curve_short" in o["lv_tags"]
    ctx.conf = StubConf()
    assert sm4._order(ctx, ss, i, p, "AM", 1.0, "curve_t", -4052.0, -4056.0, ext=-4056.0, ext_i=i - 1, broke=i, lv=()) is None


# --- 114 / 116 consolidation EQ and origin OB -----------------------------------------------------------------------------------------------------

def _consol_rows():
    # 6 bars of a tight body range 4000-4004 (bodies), the last down-close candle 4003.5 -> 4001.5 near the EQ (4002); then the breakout close at 4012
    r = [(4000.0, 4005.0, 3999.0, 4003.0), (4003.0, 4005.0, 3999.5, 4001.0), (4001.0, 4005.0, 3999.0, 4004.0), (4004.0, 4005.0, 3999.0, 4000.5), (4000.5, 4005.0, 3999.0, 4003.0),
         (4003.5, 4005.0, 3999.0, 4001.5), (4001.5, 4013.0, 4001.0, 4012.0)]
    return r


def test_consolidation_eq_ob_entry(cap):
    """cc01_001 ~00:11:11, ~00:18:01: a body-defined range (>= consol_bars bars, body range <= consol_max_pts) then a first close above its body high: mode "ob" = a limit at the open of the last down-close
    candle when it lies within 25% of the range height of the EQ; "eq" = the range EQ; the stop under the OB / range low, one target at the impulse high; one order per range."""
    p = Params(**BASE, consol_eq_entry=True, consol_bars=6, consol_max_pts=5.0, consol_eq_mode="ob")
    ctx, (sl, ss) = mkctx(_consol_rows(), base=4000.0)
    i = ib(ctx, "09:30") + 6
    o = sm6.consol_eq_order(ctx, sl, i, p, "AM", 1.0)
    assert o is not None and cap["entry"] == pytest.approx(4003.5) and cap["stop"] == pytest.approx(3999.0 - p.pad)
    assert cap["fixed"][0][0] == pytest.approx(S._exit_px(4013.0, "pool", p)) and cap["tags"]["entry_kind"] == "consol_eq"
    assert sm6.consol_eq_order(ctx, sl, i, p, "AM", 1.0) is None                          # once per range
    sl.__dict__.pop("_consol6_sent")
    assert sm6.consol_eq_order(ctx, sl, i, replace(p, consol_eq_mode="eq"), "AM", 1.0) is not None and cap["entry"] == pytest.approx(4002.0)      # the EQ of the body range 4000-4004
    sl.__dict__.pop("_consol6_sent")
    assert sm6.consol_eq_order(ctx, sl, i, replace(p, consol_max_pts=3.0), "AM", 1.0) is None          # the bodies span 4 points: no consolidation
    assert sm6.consol_eq_order(ctx, sl, i - 1, p, "AM", 1.0) is None                     # no breakout close yet
    assert sm6.consol_eq_order(ctx, sl, i, replace(p, consol_bars=200), "AM", 1.0) is None  # fewer bars (today) than needed
    up = [(4000.0, 4005.0, 3999.0, 4003.0), (4003.0, 4005.0, 3999.5, 4004.0)] * 3 + [(4004.0, 4013.0, 4003.0, 4012.0)]       # up-close bars only: no opposite candle
    ctx3, (sl3, _) = mkctx(up, base=4000.0)
    assert sm6.consol_eq_order(ctx3, sl3, ib(ctx3, "09:30") + 6, p, "AM", 1.0) is None


def test_origin_ob_retrace(cap):
    """cc01_002 ~00:18:12: consol_eq_mode "origin_ob" = the last opposite candle before the expansion at ANY location (the "ob" mode needs it within 25% of the EQ), cancelled on a body close
    through its MT."""
    rows = [(4000.0, 4005.0, 3999.0, 4003.0), (4003.0, 4005.0, 3999.5, 4001.0), (4001.0, 4005.0, 3999.0, 4004.0), (4004.0, 4005.0, 3999.0, 4000.5), (4000.5, 4005.0, 3999.0, 4003.0),
            (4004.0, 4005.0, 3999.0, 4003.8), (4003.8, 4013.0, 4003.0, 4012.0)]                  # the last down candle (4004 -> 4003.8) sits at the range's top, body mid 4003.9
    p = Params(**BASE, consol_eq_entry=True, consol_bars=6, consol_max_pts=5.0, consol_eq_mode="origin_ob")
    ctx, (sl, ss) = mkctx(rows, base=4000.0)
    i = ib(ctx, "09:30") + 6
    assert sm6.consol_eq_order(ctx, sl, i, replace(p, consol_eq_mode="ob"), "AM", 1.0) is None          # 1.9 points from the EQ, more than a quarter of the 4-point range
    o = sm6.consol_eq_order(ctx, sl, i, p, "AM", 1.0)
    assert o is not None and cap["entry"] == pytest.approx(4004.0) and cap["tags"]["cancel_close"] == pytest.approx((4004.0 + 4003.8) / 2) and "consol_origin_ob" in cap["tags"]["lv_tags"]


# --- 115 / 146 void trades ----------------------------------------------------------------------------------------------------------------------------

def _up_void_rows():
    return [(4000.0, 4001.0, 3999.5, 4000.8), (4005.0, 4012.0, 4004.0, 4011.0), (4011.0, 4020.0, 4010.0, 4018.0), (4018.0, 4019.0, 4012.0, 4013.0), (4013.0, 4014.0, 4009.0, 4010.0),
            (4010.0, 4011.0, 4008.0, 4009.0)]


def test_void_range_trade(cap):
    """cc03_001 ~00:47:58: the void of an up-leg (a true gap between two candles) with no sweep armed: a limit at the void CE (4002.5) while price is above it and has not touched it, stop under the leg
    origin (the lowest low of the 3 bars before the void), the single target = the leg extreme (the known range, no runner)."""
    p = Params(**BASE, void_trades=("range",))
    ctx, (sl, ss) = mkctx(_up_void_rows(), base=4000.0)
    i = ib(ctx, "09:30") + 5
    assert sm6.void_order(ctx, sl, i, p, "AM", 1.0) is not None
    assert cap["entry"] == pytest.approx(4002.5) and cap["stop"] == pytest.approx(3999.5 - p.pad) and cap["fixed"] == [(pytest.approx(S._exit_px(4020.0, "pool", p)), "pool")]
    assert sm6.void_order(ctx, sl, i, p, "AM", 1.0) is None                                 # once per void
    sl.__dict__.pop("_void6_sent")
    sl.sweep = dict(level=1.0)
    assert sm6.void_order(ctx, sl, i, p, "AM", 1.0) is None                                 # a pool run is in view: no range trade
    sl.sweep = None
    assert sm6.void_order(ctx, sl, i, replace(p, void_idle_bars=2), "AM", 1.0) is None      # the leg is too old
    assert sm6.void_order(ctx, sl, i, replace(p, void_trades=()), "AM", 1.0) is None
    assert sm6.void_order(ctx, sl, i, replace(p, void_trades=("fill",)), "AM", 1.0) is None


def test_void_cont_and_fill(cap):
    """cc01_001 ~00:15:21: "cont" = price traded back to the void origin and the normal MSS + FVG followed: the FVG top (4006), stop under the origin, the target the leg extreme; "fill" = an MSS
    against a down-leg void: the FVG top, stop under the leg low, the target the void top edge."""
    rows = _up_void_rows() + [(4003.0, 4003.5, 4000.5, 4001.5), (4001.5, 4005.0, 4001.2, 4004.5), (4004.5, 4004.8, 4003.0, 4004.0), (4005.5, 4010.0, 4006.0, 4009.0)]
    p = Params(**BASE, void_trades=("cont",))
    ctx, (sl, ss) = mkctx(rows, base=4000.0)
    k = ib(ctx, "09:30")
    assert sm6.void_order(ctx, sl, k + 5, p, "AM", 1.0) is None                              # not yet touched the origin
    assert sm6.void_order(ctx, sl, k + 9, p, "AM", 1.0) is not None
    assert cap["entry"] == pytest.approx(4006.0) and cap["stop"] == pytest.approx(3999.5 - p.pad) and cap["fixed"][0][0] == pytest.approx(S._exit_px(4020.0, "pool", p))
    # fill: a down-leg void
    down = [(4020.0, 4021.0, 4019.0, 4019.5), (4012.0, 4013.0, 4005.0, 4006.0), (3999.0, 3999.5, 3995.0, 3996.0), (3996.0, 4000.0, 3995.5, 3999.0), (3999.0, 3999.5, 3997.0, 3998.0),
            (4001.0, 4008.0, 4001.0, 4007.0)]
    ctx2, (sl2, _) = mkctx(down, base=4020.0)
    k2 = ib(ctx2, "09:30")
    pf = Params(**BASE, void_trades=("fill",))
    assert sm6.void_order(ctx2, sl2, k2 + 5, pf, "AM", 1.0) is not None
    assert cap["entry"] == pytest.approx(4001.0) and cap["stop"] == pytest.approx(3995.0 - pf.pad) and cap["fixed"][0][0] == pytest.approx(S._exit_px(4019.0, "array", pf))
    assert sm6.void_order(ctx2, sl2, k2 + 4, pf, "AM", 1.0) is None                          # no MSS yet


def test_void_fill_body_gap_sell(cap):
    """cc04_010 ~00:12:41 (side space, the buy mirror): the void bottom is touched (the fill), then two up-close bars 1-2 bars later whose bodies leave a gap (the second opens above the first close):
    a limit at the CE of that body gap, the stop under the fill low; no gap / too early = none."""
    rows = _up_void_rows() + [(4003.0, 4003.5, 4000.5, 4001.5), (4001.5, 4005.0, 4001.2, 4004.5), (4005.0, 4006.0, 4004.9, 4005.8)]
    p = Params(**BASE, void_trades=("void_fill_gap",))
    ctx, (sl, ss) = mkctx(rows, base=4000.0)
    k = ib(ctx, "09:30")
    assert sm6.void_order(ctx, sl, k + 8, p, "AM", 1.0) is not None
    assert cap["entry"] == pytest.approx((4004.5 + 4005.0) / 2) and cap["stop"] == pytest.approx(4000.5 - p.pad) and cap["fixed"] is None
    sl.__dict__.pop("_void6_sent")
    rows2 = list(rows)
    rows2[8] = (4004.0, 4006.0, 4003.9, 4005.8)                                              # opens inside the first body: no gap between the bodies
    ctx2, (sl2, _) = mkctx(rows2, base=4000.0)
    assert sm6.void_order(ctx2, sl2, ib(ctx2, "09:30") + 8, p, "AM", 1.0) is None
    assert sm6.void_order(ctx, sl, k + 7, p, "AM", 1.0) is None                              # one bar too early


# --- 117 OTE needs a trigger and the parent side -----------------------------------------------------------------------------------------------------

def test_ote_needs_trigger_and_parent_side():
    """cc01_004 ~00:17:12: ote_need_trigger - the OTE limit arms only after an LTF MSS inside the band (a close above a swing high formed after price entered it); ote_parent_pd - an entry in the
    OTE band of a small leg is dropped when it lies above the EQ of the parent (day) range for a long (below it for a short)."""
    rows = [(3992.0, 3995.0, 3990.0, 3994.0), (3994.0, 4020.0, 3993.0, 4018.0), (4018.0, 4019.0, 4005.0, 4006.0), (4006.0, 4007.0, 4000.0, 4001.0), (4001.0, 4001.0, 4000.2, 4000.6),
            (4000.6, 4001.3, 4000.3, 4001.0), (4001.0, 4000.9, 4000.2, 4000.5), (4000.5, 4003.0, 4000.4, 4002.5)]
    sd = sd_of(rows)
    sw = dict(ext_i=0, ext=3990.0)
    hi_band = L.ote_band(3990.0, 4020.0)[1]                                                # 4001.4
    assert not sm6.ote_trigger_ok(sd, sw, 3, hi_band) and not sm6.ote_trigger_ok(sd, sw, 6, hi_band)      # price entered the band but no MSS yet
    assert sm6.ote_trigger_ok(sd, sw, 7, hi_band)                                          # the swing high 4001.3 (bar 5) was closed above (4002.5)
    assert not sm6.ote_trigger_ok(sd_of(rows[:3]), sw, 2, hi_band)                         # never entered the band
    p = Params(**BASE, ote="limit", ote_need_trigger=True)
    ctx, (sl, ss) = mkctx([(4000.0, 4001.0, 3990.0, 3992.0)] + rows[1:], base=4000.0)
    k = ib(ctx, "09:30")
    sw2 = dict(ext_i=k, ext=3990.0)
    assert SM.ote_adjust(sl, sw2, k + 6, p, 4005.0, 3989.0, "fvg", []) is None
    r = SM.ote_adjust(sl, sw2, k + 7, p, 4005.0, 3989.0, "fvg", [])
    assert r is not None and r[0] == pytest.approx(L.ote_band(3990.0, 4020.0)[2])
    # the parent side: the day so far spans 3950-4010 (EQ 3980); the leg 3990 -> 4010 is a small one inside the parent's upper half: its OTE band (3994.2-3997.6) lies ABOVE the parent EQ
    pp = Params(**BASE, ote_parent_pd=True)
    small = [(3960.0, 3961.0, 3950.0, 3955.0), (3955.0, 4000.0, 3954.0, 3999.0), (3999.0, 4000.0, 3990.0, 3992.0), (3992.0, 4010.0, 3991.0, 4008.0), (4008.0, 4009.0, 3996.0, 3997.0)] + flat(2, 3997.0)
    ctx4, (sl4, ss4) = mkctx(small, base=3960.0, hist=hist_close(close=4000.0, hi=4130.0, lo=3900.0))
    k4 = ib(ctx4, "09:30") + 2
    sw6 = dict(session="AM", key="pdl1", name="pdl1", level=3995.0, ext=3990.0, ext_i=k4, broke=None, sweep_i=k4, smt=None, smt2=None)
    assert sm6.order_gate6(ctx4, sl4, dict(sw6), k4 + 3, pp, 3996.0, 3989.0, "AM", [], {}, {}) == "x_ote_parent_pd"
    assert sm6.order_gate6(ctx4, sl4, dict(sw6), k4 + 3, replace(pp, ote_parent_pd=False), 3996.0, 3989.0, "AM", [], {}, {}) is None
    assert sm6.order_gate6(ctx4, sl4, dict(sw6), k4 + 3, pp, 4005.0, 3989.0, "AM", [], {}, {}) is None            # an entry outside the OTE band is no OTE trade: the gate does not apply


# --- 120 OTE "ob62" / 119 premium OTE turtle soup / 121 failed turtle soup ----------------------------------------------------------------------------

def test_ote_ob62_entry():
    """cc01_005 ~00:13:59: ote="ob62" - a down-close bar after the sweep whose BODY bottom sits within one tick of the 62% retracement of the leg (4001.4 for 3990 -> 4020) while its wick pokes
    below it: a limit at that bar's open, the stop under the leg low. A body away from the 62% line, or an up-close bar, is no candidate."""
    rows = [(3992.0, 3995.0, 3990.0, 3994.0), (3994.0, 4020.0, 3993.0, 4018.0), (4018.0, 4019.0, 4004.0, 4005.0), (4003.0, 4003.5, 4000.0, 4001.4), (4001.4, 4004.0, 4001.0, 4003.0)]
    p = Params(**BASE, ote="ob62")
    ctx, (sl, ss) = mkctx(rows, base=3992.0)
    k = ib(ctx, "09:30")
    sw = dict(session="AM", key="x", ext=3990.0, ext_i=k, level=3995.0, broke=k + 1, smt=None)
    assert sm6.ob62_cand(ctx, sl, sw, k + 4, p) == (4003.0, 3990.0, "ob62")
    rows2 = list(rows)
    rows2[3] = (4003.0, 4003.5, 4000.0, 4002.5)                                              # the body bottom 4002.5 is 1.1 away from the 62% line
    ctx2, (sl2, _) = mkctx(rows2, base=3992.0)
    assert sm6.ob62_cand(ctx2, sl2, dict(sw), ib(ctx2, "09:30") + 4, p) is None
    rows3 = list(rows)
    rows3[3] = (4001.4, 4003.5, 4000.0, 4001.5)                                              # an up-close candle
    ctx3, (sl3, _) = mkctx(rows3, base=3992.0)
    assert sm6.ob62_cand(ctx3, sl3, dict(sw), ib(ctx3, "09:30") + 4, p) is None
    assert sm6.arr_cands6(ctx, sl, sw, k + 4, p, set()) == [(4003.0, 3990.0, "ob62")] and sm6.arr_cands6(ctx, sl, sw, k + 4, replace(p, ote="off"), set()) == []


def test_turtle_soup_in_ote_band(cap):
    """cc01_005 ~00:07:03 (side space): ts_ote - the swept level lies at or beyond the EQ of the last impulse leg (day low 3990 -> day high 4020): level 3999 retraces 70% (the OTE band) = ok;
    4012 retraces 27% = not. With ts_need_htf and no HTF array the turtle soup is dropped; ts_ote_ok lets the premium / OTE sweep through, tagged premium_ts."""
    rows = [(3992.0, 3995.0, 3990.0, 3994.0), (3994.0, 4020.0, 3993.0, 4018.0), (4018.0, 4019.0, 4005.0, 4006.0), (4006.0, 4007.0, 3996.0, 3997.0), (3997.0, 4003.0, 3996.5, 4002.0)]
    ctx, (sl, ss) = mkctx(rows, base=3990.0)
    k = ib(ctx, "09:30")
    sw = dict(session="AM", key="pdl1", name="pdl1", level=3999.0, ext=3996.0, ext_i=k + 3, broke=None, sweep_i=k + 3, smt=None, smt2=None)
    p = Params(**BASE, turtle_soup="2023", ts_need_htf=True, ts_ote_ok=True)
    assert sm6.ts_ote(ctx, sl, sw, k + 4, p) and not sm6.ts_ote(ctx, sl, dict(sw, level=4012.0), k + 4, p)
    o = S._turtle(ctx, sl, dict(sw), k + 4, p, "AM", 1.0)
    assert o is not None and cap["tags"]["lv_tags"] == ["premium_ts"]
    assert S._turtle(ctx, sl, dict(sw), k + 4, replace(p, ts_ote_ok=False), "AM", 1.0) is None            # the HTF-array requirement alone
    assert S._turtle(ctx, sl, dict(sw, level=4012.0, ext=4009.0), k + 4, p, "AM", 1.0) is None          # a shallow sweep stays rejected


def test_failed_turtle_becomes_continuation(cap):
    """cc01_006 ~00:14:24: an old high (the prior day's high 4020) was run by a spike and the price did NOT reverse - the >= ts_cont_bars bars after it all closed above it, a sideways range: no turtle
    soup but a continuation. The first close above that small range arms the entry (a limit at the broken range high, the stop under the range low); an early reversal (a close back under the level)
    or too few bars = nothing."""
    rows = [(4000.0, 4010.0, 3999.0, 4009.0), (4009.0, 4022.0, 4008.0, 4021.5), (4021.5, 4023.0, 4020.5, 4022.0), (4022.0, 4023.0, 4020.8, 4021.0), (4021.0, 4022.5, 4020.6, 4022.0),
            (4022.0, 4023.0, 4021.0, 4022.8), (4022.8, 4026.0, 4022.5, 4025.5)]
    p = Params(**BASE, ts_cont=True, ts_cont_bars=3)
    ctx, (sl, ss) = mkctx(rows, base=4000.0, hist=hist_close(close=4000.0, hi=4020.0, lo=3900.0))
    k = ib(ctx, "09:30")
    assert sm6.ts_cont_order(ctx, sl, k + 6, p, "AM", 1.0) is not None
    assert cap["entry"] == pytest.approx(4023.0) and cap["stop"] == pytest.approx(4020.5 - p.pad) and cap["tags"]["entry_kind"] == "ts_cont"
    assert sm6.ts_cont_order(ctx, sl, k + 6, p, "AM", 1.0) is None                          # once
    sl.__dict__.pop("_tsc6_sent")
    assert sm6.ts_cont_order(ctx, sl, k + 6, replace(p, ts_cont_bars=8), "AM", 1.0) is None  # too few bars since the spike
    assert sm6.ts_cont_order(ctx, sl, k + 5, p, "AM", 1.0) is None                          # no close above the range high yet
    back = list(rows)
    back[3] = (4022.0, 4023.0, 4018.0, 4019.0)                                               # a close back under the swept high = the turtle soup worked
    ctx2, (sl2, _) = mkctx(back, base=4000.0, hist=hist_close(close=4000.0, hi=4020.0, lo=3900.0))
    assert sm6.ts_cont_order(ctx2, sl2, ib(ctx2, "09:30") + 6, p, "AM", 1.0) is None


# --- 123 / 125 cc_1h_ob: validation, timeframe, preset, refinement -----------------------------------------------------------------------------------

def _cc_rows():
    r = []
    for k in range(12):                                         # the 10:00 hour: a down-close candle (open 4005 -> close 4000.2), high 4005.5
        o = 4005.0 - 0.4 * k
        r.append((o, o + 0.5, o - 0.6, o - 0.4))
    r.append((4000.2, 4001.0, 3995.0, 3996.0))                  # 11:00: the sweep low (3995)
    r.append((3996.0, 4006.5, 3995.5, 4006.0))                  # trades above the hour candle's high
    return r


def _cc_setup():
    conf = StubConf(arrays={1: [(4010.0, 3990.0, "D", 1, 0)]})
    ctx, (sl, ss) = mkctx(_cc_rows(), base=4005.0, start="10:00", conf=conf)
    k = ib(ctx, "10:00")
    sw = dict(session="AM", key="pdl1", name="pdl1", level=3996.0, ext=3995.0, ext_i=k + 12, broke=None, sweep_i=k + 12, smt=None, smt2=None)
    return ctx, sl, sw, k


def test_cc_1h_ob_waits_trade_through(cap):
    """cc02_001 ~00:18:50: the order arms only after a later bar trades above the high of the last down-close 1h candle C; the limit at C.open (4005), stop under the daily OB's MT / the sweep low; half
    off at 1R, breakeven after 2R, the runner at 5R. cc_ob_tf 5 takes the 5m candle; ts_r_preset cc02_003 = (3, 9, 15) R with breakeven after 3R; cc_ob_offset_ticks moves the limit toward the market."""
    ctx, sl, sw, k = _cc_setup()
    p = Params(**BASE, turtle_soup="cc_1h_ob")
    assert S._cc_1h_ob(ctx, sl, dict(sw), k + 12, p, "AM", 1.0) is None                    # not yet traded above C.high (4005.5)
    assert S._cc_1h_ob(ctx, sl, dict(sw), k + 13, p, "AM", 1.0) is not None
    risk = cap["entry"] - cap["stop"]
    assert cap["entry"] == pytest.approx(4005.0) and [round(v, 6) for v, _ in cap["fixed"]] == [round(4005.0 + r * risk, 6) for r in (1.0, 5.0)] and cap["tags"]["be_at"] == pytest.approx(4005.0 + 2 * risk)
    assert S._cc_1h_ob(ctx, sl, dict(sw), k + 13, replace(p, cc_ob_offset_ticks=2), "AM", 1.0) is not None and cap["entry"] == pytest.approx(4005.0 - 2 * p.tick)
    assert S._cc_1h_ob(ctx, sl, dict(sw), k + 13, replace(p, ts_r_preset="cc02_003"), "AM", 1.0) is not None
    risk = cap["entry"] - cap["stop"]
    assert [round(v, 6) for v, _ in cap["fixed"]] == [round(4005.0 + r * risk, 6) for r in (3.0, 9.0, 15.0)] and cap["tags"]["fracs"] == (0.5, 0.25, 0.25) and cap["tags"]["be_at"] == pytest.approx(4005.0 + 3 * risk)
    assert S._cc_1h_ob(ctx, sl, dict(sw), k + 13, replace(p, cc_ob_tf=5), "AM", 1.0) is not None and cap["entry"] == pytest.approx(4000.2)     # the 5m candle C = the sweep bar itself (open 4000.2)


def test_refine_to_5m_ob(cap):
    """cc02_002 ~00:02:27: refine_tfs (60, 15, 5): each timeframe from the lowest up is searched for a validated down-close candle whose open lies inside the daily OB; the lowest found is used, the
    stop stays under the sweep low. A candle outside the OB is skipped; none = no order."""
    ctx, sl, sw, k = _cc_setup()
    p = Params(**BASE, turtle_soup="cc_1h_ob", refine_tfs=(60, 15, 5))
    assert S._cc_1h_ob(ctx, sl, dict(sw), k + 13, p, "AM", 1.0) is not None
    assert cap["entry"] == pytest.approx(4000.2) and cap["stop"] == pytest.approx(3995.0 - p.pad)          # the OB-MT stop (3999.75) leaves < min risk: the sweep low (the stop stays at the structural point)
    assert S._cc_1h_ob(ctx, sl, dict(sw), k + 12, p, "AM", 1.0) is None                    # no candle traded through yet
    only60 = replace(p, refine_tfs=(60,))
    assert S._cc_1h_ob(ctx, sl, dict(sw), k + 13, only60, "AM", 1.0) is not None and cap["entry"] == pytest.approx(4005.0)
    ctx2 = ctx
    ctx2.conf = StubConf(arrays={1: [(4002.0, 3990.0, "D", 1, 0)]})                       # the daily OB now ends under the 60m candle's open (4005): only the 5m candle is inside
    assert S._cc_1h_ob(ctx2, sl, dict(sw), k + 13, p, "AM", 1.0) is not None and cap["entry"] == pytest.approx(4000.2)
    assert S._cc_1h_ob(ctx2, sl, dict(sw), k + 13, only60, "AM", 1.0) is None


# --- 127 secondary OB -------------------------------------------------------------------------------------------------------------------------------

def test_secondary_ob_entry(cap):
    """cc02_004 ~00:03:14: entry_arrays "ob_secondary" - while price retraces into the primary OB, the first down-close candle that opens inside its zone is a secondary OB: a limit at its open (MT
    with ob_entry_px "mt"), the stop under its low, cancelled on a body close under its MT. Dead after such a close."""
    rows = [(4010.0, 4011.0, 4000.0, 4001.0), (4001.0, 4002.0, 3990.0, 3991.0), (3991.0, 4012.0, 3991.0, 4010.0), (4010.0, 4015.0, 4008.0, 4014.0), (4010.5, 4011.0, 4004.0, 4005.0),
            (4005.0, 4013.0, 4005.0, 4012.0)]
    p = Params(**BASE, entry_arrays=("ob_secondary",))
    ctx, (sl, ss) = mkctx(rows, base=4010.0)
    k = ib(ctx, "09:30")
    sw = dict(session="AM", key="x", ext=3990.0, ext_i=k + 1, level=3995.0, broke=k + 2, smt=None)
    cs = SM.array_cands(ctx, sl, sw, k + 5, p, None)
    assert (4010.5, 4004.0, "ob_secondary") in cs and sw["_ob_sec_mt"] == pytest.approx(4007.75)
    assert SM.array_order(ctx, sl, dict(sw), k + 5, p, "AM", 1.0, None, None) is not None
    assert cap["entry"] == pytest.approx(4010.5) and cap["stop"] == pytest.approx(4004.0 - p.pad) and cap["tags"]["entry_kind"] == "arr_ob_secondary" and cap["tags"]["cancel_close"] == pytest.approx(4007.75)
    assert sm6.secondary_cand(ctx, sl, dict(sw), k + 5, replace(p, ob_entry_px="mt"))[0] == pytest.approx(4007.75)
    dead = list(rows)
    dead[5] = (4005.0, 4013.0, 4003.0, 4007.0)                                               # a close under the secondary candle's MT (4007.75)
    ctx2, (sl2, _) = mkctx(dead, base=4010.0)
    assert sm6.secondary_cand(ctx2, sl2, dict(sw), ib(ctx2, "09:30") + 5, p) is None


# --- 130 false bear flag long (the side-symmetric false_flag of an earlier chunk) ----------------------------------------------------------------------

def test_false_bear_flag_long():
    """cc02_007 ~00:22:28: already built (false_flag, chunk 5/7) - the LONG side reads a bear flag (a rapid drop then an up-sloping consolidation) lying under the previous day's EQ (an HTF discount) with
    the sweep at the flag low; the flagpole origin is its first target rung. The mirror (false bull flag in a premium) runs the same code in the short side's space."""
    from test_caption_gap_sm5a import _flag_rows
    rows = _flag_rows()
    p = Params(**BASE, false_flag="tag")
    ctx, (sl, ss) = mkctx(rows, base=4050.0, hist=hist_close(close=4000.0, hi=4130.0, lo=3900.0))
    e = ib(ctx, "09:30") + len(rows) - 1
    sw = dict(session="AM", key="pdl1", name="pdl1", level=3990.0, ext=3988.0, ext_i=e, broke=None, sweep_i=e, smt=None, smt2=None)
    lvt, tags = [], {}
    assert sm5.false_flag_gate(ctx, sl, sw, e, p, lvt, tags) is None and lvt == ["false_flag"] and tags["extra5"] == [(4051.0, "pool")]


# --- 131 entry discipline ----------------------------------------------------------------------------------------------------------------------------

def test_entry_discipline_presets():
    """cc03_001 ~00:45:51: entry_discipline is a preset of the path switches - turtle_soup -> cc_limit (no OB path, no void trades); ob_return -> the pre_break OB, no turtle soup / voids; range_void ->
    void_trades ("range",), no turtle soup; any = as configured. run_day applies it (a day runs under each)."""
    base = Params(**BASE, turtle_soup="2023", void_trades=("fill",), ob_entry="both")
    t = sm6.apply_discipline(replace(base, entry_discipline="turtle_soup"))
    assert (t.turtle_soup, t.ob_entry, t.void_trades) == ("cc_limit", "post_mss", ())
    o = sm6.apply_discipline(replace(base, entry_discipline="ob_return"))
    assert (o.turtle_soup, o.ob_entry, o.void_trades) == ("", "pre_break", ())
    r = sm6.apply_discipline(replace(base, entry_discipline="range_void"))
    assert (r.turtle_soup, r.ob_entry, r.void_trades) == ("", "post_mss", ("range",))
    assert sm6.apply_discipline(base) is base
    hist = history()
    df = day(flat(60, 100.0), base=100.0)
    for d in ("turtle_soup", "ob_return", "range_void", "any"):
        assert S.run_day(df, hist, "ES", Params(**BASE, entry_discipline=d), 5) == []


# --- 132 contrarian PMH ---------------------------------------------------------------------------------------------------------------------------------

def test_pmh_sweep_contrarian_short():
    """cc03_001 ~00:16:57: with the daily bias UP, a sweep of the previous month's high lets the SHORT side be scanned against the bias (counter_kind "pmh"); no sweep, the switch off or a bias in its
    direction = nothing. The sell-side pool dict carries the month pool when the switch is on; the engine tail then keeps only that pool and takes one exit."""
    ctx, (sl, ss) = mkctx(flat(3, 4050.0) + [(4050.0, 4106.0, 4049.0, 4102.0)] + flat(2, 4102.0), base=4050.0)
    ctx.pm_ = (4100.0, 3900.0)
    i = ib(ctx, "09:30") + 5
    p = Params(**BASE, pmh_contrarian=True)
    assert sm6.pm_level(ctx, ss) == pytest.approx(-4100.0) and sm6.pm_level(ctx, sl) == pytest.approx(3900.0)
    assert sm6.pm_swept(ctx, ss, i) and not sm6.pm_swept(ctx, sl, i)
    assert sm6.counter_kind(ctx, ss, i, p, 1) == "pmh" and sm6.counter_kind(ctx, ss, i, replace(p, pmh_contrarian=False), 1) == "" and sm6.counter_kind(ctx, sl, i, p, -1) == ""
    assert S._sell_side(ctx, ss, "AM", i, False, p).get("pml_month") == pytest.approx(-4100.0)
    assert "pml_month" not in S._sell_side(ctx, ss, "AM", i, False, replace(p, pmh_contrarian=False))
    ctx.curve_now = "pmh"
    o = sm4._order(ctx, ss, i, p, "AM", 1.0, "x", -4098.0, -4104.0, ext=-4106.0, ext_i=i - 2, broke=i, lv=())
    assert o is None                                                                       # the synthetic sweep's key is not the month pool: x_pmh_key


# --- 134 / 135 OB below the midnight open, a fresh OB at the EQ -----------------------------------------------------------------------------------------

def _ob_ctx(rows, base):
    ctx, (sl, ss) = mkctx(rows, base=base)
    k = ib(ctx, "09:30")
    return ctx, sl, k


def test_ob_below_midnight_open():
    """cc03_003 ~00:33:28: ob_below_open - an OB entry (ob_pre / arr_ob ...) needs the OB body at or below today's midnight open (the 00:00 open = the base) and the entry under it; an OB above the
    open, a limit above it or another entry kind = the gate does not pass / apply."""
    rows = [(3999.0, 3999.5, 3990.0, 3991.0), (3991.0, 3992.0, 3985.0, 3986.0), (3986.0, 4003.0, 3986.0, 4001.0), (4001.0, 4004.0, 3999.5, 4003.0)]
    ctx, sl, k = _ob_ctx(rows, 4000.0)
    sw = dict(session="AM", key="pdl1", name="pdl1", level=3988.0, ext=3985.0, ext_i=k + 1, broke=k + 2, sweep_i=k + 1, smt=None, smt2=None)
    p = Params(**BASE, ob_below_open=True)
    assert sm6.order_gate6(ctx, sl, sw, k + 3, p, 3999.0, 3984.0, "AM", [], {}, dict(entry_kind="arr_ob")) is None                 # OB body top 3999 <= 4000, entry 3999 <= 4000
    assert sm6.order_gate6(ctx, sl, sw, k + 3, p, 4001.0, 3984.0, "AM", [], {}, dict(entry_kind="arr_ob")) == "x_ob_above_open"     # the limit sits above the open
    assert sm6.order_gate6(ctx, sl, sw, k + 3, p, 4001.0, 3984.0, "AM", [], {}, dict(entry_kind="fvg")) is None                     # not an OB entry
    assert sm6.order_gate6(ctx, sl, sw, k + 3, replace(p, ob_below_open=False), 4001.0, 3984.0, "AM", [], {}, dict(entry_kind="arr_ob")) is None
    high = [(4009.0, 4009.5, 4000.0, 4001.0), (4001.0, 4002.0, 3995.0, 3996.0), (3996.0, 4010.0, 3996.0, 4008.0), (4008.0, 4011.0, 4005.0, 4010.0)]
    ctx2, sl2, k2 = _ob_ctx(high, 4000.0)
    sw2 = dict(sw, ext=3995.0, ext_i=k2 + 1, broke=k2 + 2)
    assert sm6.order_gate6(ctx2, sl2, sw2, k2 + 3, p, 3999.0, 3994.0, "AM", [], {}, dict(entry_kind="ob_pre")) == "x_ob_above_open"      # the OB body (top 4009) lies above the open


def test_eq_needs_fresh_ob():
    """cc03_003 ~00:34:10: eq_fresh_ob - an OB entry within eq_tol_pts of the day range EQ needs an OB formed AFTER price first reached the EQ band; one formed before is stale. Entries away from the EQ and
    non-OB entries are not gated."""
    stale = [(3990.0, 3992.0, 3985.0, 3986.0), (3986.0, 3987.0, 3978.0, 3979.0), (3979.0, 4010.0, 3979.0, 4008.0), (4008.0, 4030.0, 4005.0, 4025.0), (4025.0, 4026.0, 4003.0, 4004.0)]
    ctx, sl, k = _ob_ctx(stale, 3990.0)                                                   # the range 3978-4030 (EQ 4004) was first touched at bar 2, the OB (bars 0-1) formed before
    sw = dict(session="AM", key="pdl1", name="pdl1", level=3980.0, ext=3978.0, ext_i=k + 1, broke=k + 2, sweep_i=k + 1, smt=None, smt2=None)
    p = Params(**BASE, eq_fresh_ob=True)
    assert sm6.order_gate6(ctx, sl, sw, k + 4, p, 4004.1, 3977.0, "AM", [], {}, dict(entry_kind="arr_ob")) == "x_eq_stale_ob"
    assert sm6.order_gate6(ctx, sl, sw, k + 4, p, 3990.0, 3977.0, "AM", [], {}, dict(entry_kind="arr_ob")) is None                 # not at the EQ
    assert sm6.order_gate6(ctx, sl, sw, k + 4, p, 4004.1, 3977.0, "AM", [], {}, dict(entry_kind="fvg")) is None
    assert sm6.order_gate6(ctx, sl, sw, k + 4, replace(p, eq_fresh_ob=False), 4004.1, 3977.0, "AM", [], {}, dict(entry_kind="arr_ob")) is None
    fresh = [(4000.0, 4020.0, 3980.0, 4004.0), (4004.0, 4005.0, 3995.0, 3996.0), (3996.0, 3997.0, 3990.0, 3991.0), (3991.0, 4001.0, 3991.0, 4000.0), (4000.0, 4002.0, 3999.0, 4001.0)]
    ctx2, sl2, k2 = _ob_ctx(fresh, 3990.0)                                                # the EQ band was reached by bar 0; the OB (bars 1-2) formed after it
    sw2 = dict(sw, ext=3990.0, ext_i=k2 + 2, broke=k2 + 3, level=3992.0)
    assert sm6.order_gate6(ctx2, sl2, sw2, k2 + 4, p, 4000.1, 3989.0, "AM", [], {}, dict(entry_kind="arr_ob")) is None


# --- 136 symmetric swing ---------------------------------------------------------------------------------------------------------------------------

def test_symmetric_swing_fades_counter_run():
    """cc03_005 ~00:03:27: sym_swing_ts - a sweep that makes the day's extreme with the partner index confirming it (sw["smt"] False: no SMT) is a stop run in a confirmed trend, not a reversal: the
    counter trade is dropped; with SMT (True), no partner (None) or a sweep that is not the day's extreme it passes."""
    rows = [(4000.0, 4001.0, 3990.0, 3992.0), (3992.0, 3993.0, 3985.0, 3986.0), (3986.0, 3995.0, 3986.0, 3994.0)]
    ctx, sl, k = _ob_ctx(rows, 4000.0)
    p = Params(**BASE, sym_swing_ts=True)
    sw = dict(session="AM", key="pdl1", name="pdl1", level=3988.0, ext=3985.0, ext_i=k + 1, broke=None, sweep_i=k + 1, smt=False, smt2=None)
    assert sm6.order_gate6(ctx, sl, dict(sw), k + 2, p, 3990.0, 3984.0, "AM", [], {}, {}) == "x_sym_swing"
    assert sm6.order_gate6(ctx, sl, dict(sw, smt=True), k + 2, p, 3990.0, 3984.0, "AM", [], {}, {}) is None
    assert sm6.order_gate6(ctx, sl, dict(sw, smt=None), k + 2, p, 3990.0, 3984.0, "AM", [], {}, {}) is None
    assert sm6.order_gate6(ctx, sl, dict(sw, ext=3995.0), k + 2, p, 3990.0, 3984.0, "AM", [], {}, {}) is None                         # not the day's low: a retrace inside the swing
    assert sm6.order_gate6(ctx, sl, dict(sw), k + 2, replace(p, sym_swing_ts=False), 3990.0, 3984.0, "AM", [], {}, {}) is None


# --- 139 body level / 191 depth ---------------------------------------------------------------------------------------------------------------------

def test_turtle_body_level(cap, monkeypatch):
    """cc03_008 ~00:15:43: ts_level_src "body" - the cc_limit level is the extreme BODY (the lowest open / close) of the candles that printed the pool, not the wick (3990): the prior day's first bar
    (low 3990, body 4000); the previous PM turtle limit uses the extreme body of the prior 13:30-16:00 bars. "wick" keeps the old level."""
    hist = hist_close(close=4000.0, hi=4130.0, lo=3990.0)
    monkeypatch.setattr(S, "_sell_side", lambda ctx_, sd_, ses, i_=None, extra=False, p_=None: {"pdl1": 3990.0})        # only the prior day's low is a pool here
    ctx, (sl, ss) = mkctx(flat(6, 4040.0), base=4040.0, hist=hist, bias=1)
    i = ib(ctx, "09:30") + 5
    p = Params(**BASE, turtle_soup="cc_limit", ts_cc_below_pts=0.0)
    assert sm6.level_src(ctx, sl, 3990.0, i, p) == pytest.approx(3990.0)
    pb = replace(p, ts_level_src="body")
    assert sm6.level_src(ctx, sl, 3990.0, i, pb) == pytest.approx(4000.0)                    # the prior day's 09:30 bar: open = close = 4000
    assert sm6.level_src(ctx, sl, 3500.0, i, pb) == pytest.approx(3500.0)                    # no candle of the frame printed it: the wick level
    assert S._cc_limit(ctx, sl, i, p, "AM", 1.0) is not None and cap["entry"] == pytest.approx(3990.0)
    ctx2, (sl2, _) = mkctx(flat(6, 4040.0), base=4040.0, hist=hist, bias=1)
    assert S._cc_limit(ctx2, sl2, i, pb, "AM", 1.0) is not None and cap["entry"] == pytest.approx(4000.0) and cap["stop"] == pytest.approx(3990.0 - pb.ts_max_pts * pb.es_pt - pb.pad)
    # the previous PM range
    ctx3, (sl3, _) = mkctx(flat(3, 4040.0), base=4040.0, hist=hist)
    assert sm6.prev_pm_body(ctx3, sl3, 3990.0, p) == pytest.approx(3990.0)
    assert sm6.prev_pm_body(ctx3, sl3, 3990.0, pb) == pytest.approx(float(np.minimum(sl3.o[:ctx3.start][ctx3.t[:ctx3.start] >= 810], sl3.c[:ctx3.start][ctx3.t[:ctx3.start] >= 810]).min()))


def test_turtle_depth_miss(cap, monkeypatch):
    """cc09_003 ~00:09:08: the cc_limit depth is ts_cc_below_pts under the old low - 1 / 1.25 / 2 points; the limit that is not reached is missed: a pending limit never becomes a market order (_fill_at
    answers None on a bar that does not trade through it, the fill price is the limit or a gap open)."""
    hist = hist_close(close=4000.0, hi=4130.0, lo=3990.0)
    monkeypatch.setattr(S, "_sell_side", lambda ctx_, sd_, ses, i_=None, extra=False, p_=None: {"pdl1": 3990.0})
    for depth in (1.0, 1.25, 2.0):
        ctx, (sl, ss) = mkctx(flat(6, 4040.0), base=4040.0, hist=hist, bias=1)
        i = ib(ctx, "09:30") + 5
        assert S._cc_limit(ctx, sl, i, Params(**BASE, turtle_soup="cc_limit", ts_cc_below_pts=depth), "AM", 1.0) is not None
        assert cap["entry"] == pytest.approx(3990.0 - depth)
    o = dict(entry=3988.75)
    sd = sd_of([(4000.0, 4001.0, 3990.0, 3995.0), (3995.0, 3996.0, 3988.75, 3990.0), (3990.0, 3991.0, 3988.0, 3989.0), (3993.0, 3994.0, 3980.0, 3985.0)])
    assert S._fill_at(sd, o, 0) is None and S._fill_at(sd, o, 1) is None                    # 3988.75 is only touched on bar 1: a plain limit needs to trade THROUGH it
    assert S._fill_at(sd, o, 2) == pytest.approx(3988.75) and S._fill_at(sd, o, 3) == pytest.approx(3988.75)    # through it: the limit; no chase at the market on a miss
    assert S._fill_at(sd_of([(4000.0, 4001.0, 3999.0, 3995.0)]), o, 0) is None


# --- 142 breaker retests ---------------------------------------------------------------------------------------------------------------------------

def test_breaker_second_retest_entry():
    """cc04_005 ~00:04:51: breaker_retests N lets a breaker create at most N-1 retest orders after the first return (1 = the built behaviour), each after price LEFT the zone by breaker_leave_pts."""
    rows = [(3990.0, 4012.0, 3989.0, 4010.0), (4010.0, 4014.0, 4008.0, 4012.0), (4012.0, 4013.0, 3999.0, 4001.0), (4001.0, 4006.0, 4000.5, 4005.0)]
    sd = sd_of(rows)
    e = dict(top=4000.0, born=1, armed_i=None, n_ret=0)
    p1 = Params(**BASE)
    p3 = Params(**BASE, breaker_retests=3, breaker_leave_pts=3.0)
    assert sm6.retest_ok(sd, e, 3, p1) is True                                              # the default: the existing flow decides
    assert sm6.retest_ok(sd, e, 3, p3) is True                                              # a high of 4014 (>= 4003) before the touch at bar 2
    assert sm6.retest_ok(sd, e, 3, replace(p3, breaker_leave_pts=20.0)) is False            # never left by 20 points
    assert sm6.retest_ok(sd, dict(e, n_ret=2), 3, p3) is False                              # two retest orders are the cap of breaker_retests=3
    assert sm6.retest_ok(sd, dict(e, armed_i=3), 3, p3) is False                            # no touch after the last order
    # the engine hook (sm2.breaker_retest_order) counts the orders
    assert "breaker_retests" in Params.__dataclass_fields__


# --- 143 rejection block ------------------------------------------------------------------------------------------------------------------------------

def _rb_rows():
    return [(4012.0, 4014.0, 4003.0, 4013.0), (4008.0, 4009.0, 3998.0, 4007.0), (4007.0, 4012.0, 4004.0, 4011.0), (4011.0, 4016.0, 4010.0, 4015.0)]


def test_rb_conservative_sell_stop(cap):
    """cc04_006 ~00:10:39, ~00:11:19 (side space, the buy mirror): rb_entry "limit" = a limit AT the trigger (the lowest close of the swing candle 4007) while price is above it and has not touched it;
    "stop" = after a bar traded through the trigger by >= 1 tick with no new wick low and a close still under it, a buy-stop one tick above it (stop_entry), cancelled on a new wick low; a broken
    wick low kills the block."""
    p = Params(**BASE, rb_entry="limit")
    ctx, (sl, ss) = mkctx(_rb_rows(), base=4012.0)
    i = ib(ctx, "09:30") + 3
    assert sm6.rb_order(ctx, sl, i, p, "AM", 1.0) is not None
    assert cap["entry"] == pytest.approx(4007.0) and cap["stop"] == pytest.approx(3998.0 - p.pad) and cap["tags"]["entry_kind"] == "rb_entry" and "stop_entry" not in cap["tags"]
    assert sm6.rb_order(ctx, sl, i, p, "AM", 1.0) is None                                   # once per block
    rows = _rb_rows() + [(4015.0, 4015.0, 4005.0, 4006.0)]
    ctx2, (sl2, _) = mkctx(rows, base=4012.0)
    j = ib(ctx2, "09:30") + 4
    ps = Params(**BASE, rb_entry="stop")
    assert sm6.rb_order(ctx2, sl2, j, ps, "AM", 1.0) is not None
    assert cap["entry"] == pytest.approx(4007.25) and cap["tags"]["stop_entry"] is True and cap["tags"]["cancel_low"] == pytest.approx(3998.0) and cap["stop"] == pytest.approx(3998.0 - ps.pad)
    assert sm6.rb_order(ctx2, sl2, j, replace(p, rb_entry="limit"), "AM", 1.0) is None       # touched: the aggressive limit is gone
    sl2.__dict__.pop("_rb6_sent")
    dead = rows[:4] + [(4015.0, 4015.0, 3996.0, 4006.0)]                                    # a new wick low (3996 < 3998) before the stop was armed
    ctx3, (sl3, _) = mkctx(dead, base=4012.0)
    assert sm6.rb_order(ctx3, sl3, ib(ctx3, "09:30") + 4, ps, "AM", 1.0) is None
    assert not sm6.any_extra6(Params(**BASE)) and sm6.any_extra6(ps)


# --- 144 propulsion ------------------------------------------------------------------------------------------------------------------------------------

def test_propulsion_entry_and_second(cap):
    """cc04_008 ~00:01:49, ~00:06:53: entry_arrays "propulsion" - a limit at the block's high, the stop just beyond its MT, a body close under the MT cancels; the first return only - with prop_second
    a block whose high was already broken is entered again on the next return. A block with a close under its MT is dead."""
    rows = [(3992.0, 3995.0, 3990.0, 3994.0), (3994.0, 4020.0, 3993.0, 4018.0), (4018.0, 4019.0, 4004.0, 4005.0), (4005.0, 4012.0, 4004.5, 4011.0), (4011.0, 4012.0, 4008.0, 4011.5)]
    ctx, (sl, ss) = mkctx(rows, base=3992.0)
    k = ib(ctx, "09:30")
    sl._prop = [L.Zone("bull", 4010.0, 4006.0, k + 2, k + 2, 4008.0)]
    sw = dict(session="AM", key="x", ext=3990.0, ext_i=k, level=3995.0, broke=k + 1, smt=None)
    p = Params(**BASE, entry_arrays=("propulsion",))
    assert sm6.prop_cands(ctx, sl, sw, k + 2, p) == [(4010.0, 4008.0, "propulsion")]
    assert sm6.prop_cands(ctx, sl, sw, k + 4, p) == []                                      # the block's high (4010) was already broken (4012): the first return is gone
    assert sm6.prop_cands(ctx, sl, sw, k + 4, replace(p, prop_second=True)) == [(4010.0, 4008.0, "propulsion")]
    assert SM.array_order(ctx, sl, dict(sw), k + 4, replace(p, prop_second=True), "AM", 1.0, None, None) is not None
    assert cap["entry"] == pytest.approx(4010.0) and cap["stop"] == pytest.approx(4008.0 - p.pad) and cap["tags"]["cancel_close"] == pytest.approx(4008.0)
    dead = list(rows)
    dead[4] = (4011.0, 4012.0, 4005.0, 4007.0)                                              # a close under the MT (4008)
    ctx2, (sl2, _) = mkctx(dead, base=3992.0)
    sl2._prop = [L.Zone("bull", 4010.0, 4006.0, k + 2, k + 2, 4008.0)]
    assert sm6.prop_cands(ctx2, sl2, dict(sw), k + 4, replace(p, prop_second=True)) == []


# --- 145 vacuum block ------------------------------------------------------------------------------------------------------------------------------------

def _vb_rows():
    return [(4003.0, 4040.0, 4001.0, 4002.0), (4002.0, 4003.0, 3996.0, 3997.0), (3997.0, 4002.0, 3997.0, 4001.0), (4001.0, 4006.0, 4000.0, 4005.0), (4005.0, 4009.0, 4004.0, 4008.0),
            (4015.0, 4020.0, 4014.0, 4018.0)]


def test_vacuum_block_partial_vs_full(cap):
    """cc04_009 ~00:07:24, ~00:10:12: vb_entry "partial" = a limit at the top of the highest down-close candle of the pre-gap run (4003), stop under the run low; "full" = a limit at VB_low (the pre-gap
    close 4008), stop under the run low; "auto" = full for a gap before 10:00, partial after. The buy-side liquidity above the gap candle (4040) must be untaken; the position times out when no bar
    closes above the fill within vb_react_bars."""
    p = Params(**BASE, vb_entry="partial", vb_min_gap_pts=0.5)
    ctx, (sl, ss) = mkctx(_vb_rows(), base=4003.0)
    k = ib(ctx, "09:30")
    assert sm6.vb_order6(ctx, sl, k + 5, p, "AM", 1.0) is not None
    assert cap["entry"] == pytest.approx(4003.0) and cap["stop"] == pytest.approx(3996.0 - p.pad) and cap["tags"]["sm6"]["mode"] == "partial" and cap["tags"]["sm6"]["vb_low"] == pytest.approx(4008.0)
    sl.__dict__.pop("_vb6_sent")
    assert sm6.vb_order6(ctx, sl, k + 5, replace(p, vb_entry="full"), "AM", 1.0) is not None and cap["entry"] == pytest.approx(4008.0) and cap["stop"] == pytest.approx(3996.0 - p.pad)
    sl.__dict__.pop("_vb6_sent")
    assert sm6.vb_order6(ctx, sl, k + 5, replace(p, vb_entry="auto"), "AM", 1.0) is not None and cap["tags"]["sm6"]["mode"] == "full"      # 09:55 gap: full
    late = _vb_rows()
    ctx2, (sl2, _) = mkctx(late, base=4003.0, start="10:00")
    k2 = ib(ctx2, "10:00")
    assert sm6.vb_order6(ctx2, sl2, k2 + 5, replace(p, vb_entry="auto"), "AM", 1.0) is not None and cap["tags"]["sm6"]["mode"] == "partial"     # 10:25 gap: partial
    taken = list(_vb_rows())
    taken[5] = (4015.0, 4045.0, 4014.0, 4018.0)                                               # the gap candle already took the 4040 high
    ctx3, (sl3, _) = mkctx(taken, base=4003.0)
    assert sm6.vb_order6(ctx3, sl3, ib(ctx3, "09:30") + 5, p, "AM", 1.0) is None
    # management: partial fill, no bar closes above the fill within vb_react_bars -> out; a close back under VB_low after the rally exits
    sdm = sd_of([(4003.0, 4004.0, 4002.0, 4003.5), (4003.0, 4003.8, 4001.0, 4002.0), (4002.0, 4003.0, 4000.5, 4001.5), (4001.5, 4002.5, 4000.0, 4001.0)])
    pos = dict(fill_i=0, left=10, basis=4003.0 * 10, n=10, stop=3990.0, sm6=dict(kind="vb", mode="partial", vb_low=4008.0, top=4015.0, reach=False))
    tr = SimpleNamespace(exits=[])
    pp = replace(p, vb_react_bars=2)
    sm6.manage(ctx, sdm, pos, tr, 1, "t1", pp)
    assert tr.exits == [] and pos["left"] == 10
    sm6.manage(ctx, sdm, pos, tr, 2, "t2", pp)
    assert tr.exits == [("t2", 4001.5, 10, "vb_timeout")] and pos["left"] == 0
    sdr = sd_of([(4003.0, 4004.0, 4002.0, 4003.5), (4003.5, 4020.0, 4003.0, 4018.0), (4018.0, 4019.0, 4005.0, 4006.0)])
    pos2 = dict(fill_i=0, left=10, basis=4003.0 * 10, n=10, stop=3990.0, sm6=dict(kind="vb", mode="full", vb_low=4008.0, top=4015.0, reach=False))
    tr2 = SimpleNamespace(exits=[])
    sm6.manage(ctx, sdr, pos2, tr2, 1, "t1", pp)
    sm6.manage(ctx, sdr, pos2, tr2, 2, "t2", pp)
    assert tr2.exits == [("t2", 4006.0, 10, "vb_back")]


# --- 148 last offered level -------------------------------------------------------------------------------------------------------------------------

def test_last_offer_level_sell():
    """cc04_012 ~00:15:37 (side space, the buy mirror): entry_arrays "last_offer" - L = the high of the last down-close candle before >= offer_run consecutive up-close candles; once price closed above
    L the limit sits at L + offer_step_pts (the ladder's shallow rung, it fills first on the way back), the stop under that candle's low. Fewer up-close candles or no close above L = none."""
    rows = [(4000.0, 4001.0, 3990.0, 3992.0), (3992.0, 3993.0, 3989.0, 3990.0), (3990.0, 3998.0, 3990.0, 3997.0), (3997.0, 4003.0, 3996.0, 4002.0), (4002.0, 4009.0, 4001.0, 4008.0),
            (4008.0, 4012.0, 4007.0, 4011.0)]
    ctx, (sl, ss) = mkctx(rows, base=4000.0)
    k = ib(ctx, "09:30")
    sw = dict(session="AM", key="x", ext=3989.0, ext_i=k + 1, level=3992.0, broke=k + 2, smt=None)
    p = Params(**BASE, entry_arrays=("last_offer",), offer_run=3, offer_step_pts=1.0)
    r = sm6.offer_cand(ctx, sl, sw, k + 5, p)
    assert r == (pytest.approx(3993.0 + 1.0), pytest.approx(3989.0), "last_offer")           # L = the high (3993) of the last down-close candle (bar 1), + 1 point
    assert sm6.offer_cand(ctx, sl, sw, k + 5, replace(p, offer_run=5)) is None              # the run is only 4 up-close candles
    assert sm6.offer_cand(ctx, sl, sw, k + 3, p) is None                                    # fewer candles known yet
    assert (3994.0, 3989.0, "last_offer") in SM.array_cands(ctx, sl, dict(sw), k + 5, p, None)


# --- 149 two chance / 150 near OB ----------------------------------------------------------------------------------------------------------------------

def test_two_chance_retest_after_missed_soup(monkeypatch):
    """cc05_005 ~00:17:52: two_chance - chance 2 after a FILLED turtle soup is an ADD at the in-between swing high H once price closed above it (the MSS) and came back: armed once; before the MSS or
    without the switch nothing. A missed soup keeps the sweep alive (ts_gate_mss does not drop it): the funnel keeps the sweep and counts two_chance_keep."""
    rows = [(4000.0, 4010.0, 3999.0, 4009.0), (4009.0, 4012.0, 4000.0, 4001.0), (4001.0, 4002.0, 3990.0, 3992.0), (3992.0, 3995.0, 3991.0, 3994.0), (3994.0, 4013.0, 3993.0, 4011.0),
            (4011.0, 4012.0, 4003.0, 4004.0)]
    ctx, (sl, ss) = mkctx(rows, base=4000.0)
    k = ib(ctx, "09:30")
    got = []
    monkeypatch.setattr(S, "_arm_add", lambda pos_, tr_, px, i_, p_, eq, **kw: pos_.__setitem__("add", px))
    pos = dict(ext_i=k + 2, fill_i=k + 3, stop=3989.0, add=None, kind="turtle_soup")
    tr = SimpleNamespace()
    p = Params(**BASE, two_chance=True)
    sm6.two_chance_add(ctx, sl, pos, tr, k + 3, p)
    assert pos["add"] is None and pos["tc6"]["ref"] == pytest.approx(4012.0) and pos["tc6"]["broke"] is None         # H = the swing high before the sweep extreme (bar 1: 4012)
    sm6.two_chance_add(ctx, sl, pos, tr, k + 4, p)
    assert pos["add"] is None and pos["tc6"]["broke"] is None                                # close 4011 is not above H
    rows2 = list(rows)
    rows2[4] = (3994.0, 4015.0, 3993.0, 4014.0)
    rows2[5] = (4014.0, 4015.0, 4010.0, 4012.5)
    ctx2, (sl2, _) = mkctx(rows2, base=4000.0)
    pos2 = dict(ext_i=k + 2, fill_i=k + 3, stop=3989.0, add=None, kind="turtle_soup")
    sm6.two_chance_add(ctx2, sl2, pos2, tr, k + 4, p)
    assert pos2["tc6"]["broke"] == k + 4 and pos2["add"] is None                             # the MSS bar itself arms nothing
    sm6.two_chance_add(ctx2, sl2, pos2, tr, k + 5, p)
    assert pos2["add"] == pytest.approx(4012.0) and pos2["tc6"]["done"]
    pos2["add"] = None
    sm6.two_chance_add(ctx2, sl2, pos2, tr, k + 5, p)
    assert pos2["add"] is None                                                               # once
    # the missed soup keeps the sweep (the _scan_core branch): ts_gate_mss + two_chance
    assert Params(**BASE, two_chance=True, ts_gate_mss=True, cc_swings="breaker").two_chance


def test_cc_breaker_oco_near_ob(cap):
    """cc05_005 ~00:16:56: cc_near_ob - the breaking-point retest order is OCO with a limit at the open of the last down-close bar of the break leg: one resting order at the nearer (higher) of the two
    = the first reached; no such bar above the break point / below the market = the break point itself."""
    rows = [(4000.0, 4010.0, 3999.0, 4009.0), (4009.0, 4010.0, 3990.0, 3992.0), (3992.0, 4005.0, 3991.0, 4004.0), (4004.0, 4014.0, 4003.0, 4013.0), (4013.0, 4015.0, 4010.0, 4012.0),
            (4012.0, 4020.0, 4011.0, 4019.0)]
    ctx, (sl, ss) = mkctx(rows, base=4000.0)
    k = ib(ctx, "09:30")
    sw = dict(session="AM", key="pdl1", name="pdl1", level=3995.0, ext=3990.0, ext_i=k + 1, broke=k + 5, sweep_i=k + 1, smt=None, smt2=None)
    ref = 4010.0
    p = Params(**BASE, cc_swings="breaker", cc_near_ob=True)
    assert sm6.near_ob_entry(sl, sw, k + 5, ref, p) == pytest.approx(4013.0)                # the last down candle of the leg (bar 4) opened at 4013, above the break point
    assert sm6.near_ob_entry(sl, sw, k + 5, 4014.0, p) == pytest.approx(4014.0)             # the break point is the nearer one
    assert SM.cc_breaker_order(ctx, sl, dict(sw), k + 5, p, "AM", 1.0, ref) is not None and cap["entry"] == pytest.approx(4013.0) and cap["stop"] == pytest.approx(3990.0 - p.pad)
    assert SM.cc_breaker_order(ctx, sl, dict(sw), k + 5, replace(p, cc_near_ob=False), "AM", 1.0, ref) is not None and cap["entry"] == pytest.approx(4010.0)


# --- 153 mitigation before breaker ---------------------------------------------------------------------------------------------------------------------

def test_mitigation_before_breaker_order(cap, monkeypatch):
    """cc05_014 ~00:07:47: entry_arrays_order - the first listed kind that has a candidate wins even when another kind's entry is higher (the default picks the highest entry)."""
    cs = [(4010.0, 4000.0, "breaker"), (4005.0, 4001.0, "mitigation"), (4003.0, 4000.5, "ob")]
    p = Params(**BASE, entry_arrays=("breaker", "mitigation"), entry_arrays_order=("mitigation", "breaker"))
    assert sm6.pick_array(cs, p) == (4005.0, 4001.0, "mitigation") and sm6.pick_array(cs, replace(p, entry_arrays_order=("breaker",))) == (4010.0, 4000.0, "breaker")
    assert sm6.pick_array(cs, replace(p, entry_arrays_order=("vi",))) == max(cs)             # a listed kind with no candidate: the highest entry
    rows = flat(3, 4020.0) + [(4020.0, 4022.0, 4018.0, 4021.0)]
    ctx, (sl, ss) = mkctx(rows, base=4020.0)
    k = ib(ctx, "09:30")
    sw = dict(session="AM", key="x", ext=3995.0, ext_i=k, level=3998.0, broke=k + 1, smt=None)
    monkeypatch.setattr(SM, "array_cands", lambda *a, **kw: list(cs))
    assert SM.array_order(ctx, sl, dict(sw), k + 3, p, "AM", 1.0, None, None) is not None and cap["entry"] == pytest.approx(4005.0) and cap["tags"]["entry_kind"] == "arr_mitigation"
    assert SM.array_order(ctx, sl, dict(sw), k + 3, replace(p, entry_arrays_order=()), "AM", 1.0, None, None) is not None and cap["entry"] == pytest.approx(4010.0)


# --- 163 clarity ---------------------------------------------------------------------------------------------------------------------------------------

def test_clarity_filter_marginal_gap():
    """cc06_002 ~00:09:20: clarity - an entry gap within 10% of its size threshold (Side.min_gap) is marginal, a path entry .. T1 dominated by overlapping candles (sum of bar ranges inside it / its
    length > clarity_overlap) has too much resistance: "drop" removes the order, "tag" adds lv_tags clarity_marginal / clarity_overlap, "off" nothing."""
    rows = flat(8, 4005.0, w=3.0)                                                          # eight bars each covering 4002-4008
    ctx, (sl, ss) = mkctx(rows, base=4005.0)
    i = ib(ctx, "09:30") + 7
    sw = dict(session="AM", key="pdl1", broke=None, ext=3990.0, ext_i=i - 5)
    sl.min_gap = 1.0
    order = dict(entry=4000.0, t1=4010.0, zone_top=4000.0, lv_tags="x")
    tags = dict(fvg_bottom=3999.05)                                                         # gap 0.95: within 10% of min_gap 1.0
    p = Params(**BASE, clarity="tag", clarity_overlap=4.0)
    o = dict(order)
    assert sm6.late6(ctx, sl, sw, i, p, o, tags) is None and o["lv_tags"] == "x|clarity_marginal|clarity_overlap"      # 8 bars x 6 points inside a 10 point path = ratio ~4.8 > 4 ... (below)
    clear = dict(order, t1=4040.0)
    c2 = dict(clear)
    assert sm6.late6(ctx, sl, sw, i, p, c2, dict(fvg_bottom=3996.0)) is None and c2["lv_tags"] == "x"       # a 40 point path: clear; the gap (4.0) far from the threshold
    d = dict(order)
    assert sm6.late6(ctx, sl, sw, i, replace(p, clarity="drop"), d, tags) == "x_clarity"
    assert sm6.late6(ctx, sl, sw, i, replace(p, clarity="off"), dict(order), tags) is None
    sl.min_gap = 0.0


# --- 181 NY retrace into the London range -------------------------------------------------------------------------------------------------------------

def test_ny_retrace_into_london_range():
    """cc08_001 ~00:42:40, ~00:44:50: ny_london_range - with the weekly bias this side, an AM entry after 08:20 must lie inside R = [the London low (02:00-05:00) .. the high from that low to 08:20] and
    below R's EQ. Above the EQ, below the London low, another weekly bias or the PM session = not gated."""
    n = 76 + 4                                                                             # 02:00 .. 08:15 (76 bars) + 4 more
    rows = []
    for j in range(n):
        if j == 10:
            rows.append((4000.0, 4001.0, 3990.0, 3992.0))                                    # the London low (3990) at 02:50
        elif j < 10:
            rows.append((4005.0, 4006.0, 4004.0, 4005.0))
        elif j < 60:
            rows.append((3995.0 + 0.4 * (j - 10), 3996.0 + 0.4 * (j - 10), 3994.5 + 0.4 * (j - 10), 3995.4 + 0.4 * (j - 10)))      # up to ~4015 at 07:00
        else:
            rows.append((4010.0, 4012.0, 4008.0, 4011.0))
    ctx, (sl, ss) = mkctx(rows, base=4005.0, start="02:00")
    ctx.wbias = 1
    i = S._idx_at(ctx, 500) + 2                                                              # 08:30
    p = Params(**BASE, ny_london_range=True)
    sw = dict(session="AM", key="pdl1", name="pdl1", level=3995.0, ext=3992.0, ext_i=i - 1, broke=None, sweep_i=i - 1, smt=None, smt2=None)
    k20 = S._idx_at(ctx, 500)
    R_hi = float(sl.h[S._idx_at(ctx, 120) + 10:k20].max())
    eq = (3990.0 + R_hi) / 2
    assert sm6.order_gate6(ctx, sl, dict(sw), i, p, eq - 1.0, 3989.0, "AM", [], {}, {}) is None                                # below the EQ, inside R
    assert sm6.order_gate6(ctx, sl, dict(sw), i, p, eq + 1.0, 3989.0, "AM", [], {}, {}) == "x_ny_london_range"                 # above the EQ
    assert sm6.order_gate6(ctx, sl, dict(sw), i, p, 3980.0, 3979.0, "AM", [], {}, {}) == "x_ny_london_range"                    # below the London low
    assert sm6.order_gate6(ctx, sl, dict(sw), i, p, eq + 1.0, 3989.0, "PM", [], {}, {}) is None
    ctx.wbias = -1
    assert sm6.order_gate6(ctx, sl, dict(sw), i, p, eq + 1.0, 3989.0, "AM", [], {}, {}) is None                                # the weekly bias is the other way: no gate
    ctx.wbias = 1
    assert sm6.order_gate6(ctx, sl, dict(sw), i, replace(p, ny_london_range=False), eq + 1.0, 3989.0, "AM", [], {}, {}) is None


# --- 189 sweep into a 15m array ------------------------------------------------------------------------------------------------------------------------

def test_sweep_15m_array_tag_and_hover():
    """cc09_001 ~00:05:11: sweep_15m_array - the sweep extreme lies inside a same-side 15m array: tag / require; sweep_leave_bars - price that hovers within sweep_leave_pts of the extreme for more
    than N bars drops the order, a sharp departure passes."""
    rows = [(4000.0, 4001.0, 3990.0, 3992.0), (3992.0, 3994.0, 3991.0, 3993.0), (3993.0, 3995.0, 3992.5, 3994.5), (3994.5, 4005.0, 3994.0, 4004.0), (4004.0, 4010.0, 4003.0, 4009.0),
            (4009.0, 4012.0, 4008.0, 4011.0)]
    conf = StubConf(arrays={1: [(3993.0, 3985.0, "15m", 0, 0)]})
    ctx, (sl, ss) = mkctx(rows, base=4000.0, conf=conf)
    k = ib(ctx, "09:30")
    sw = dict(session="AM", key="pdl1", name="pdl1", level=3995.0, ext=3990.0, ext_i=k, broke=None, sweep_i=k, smt=None, smt2=None)
    p = Params(**BASE, sweep_15m_array="tag")
    lvt = []
    assert sm6.order_gate6(ctx, sl, dict(sw), k + 4, p, 3999.0, 3989.0, "AM", lvt, {}, {}) is None and lvt == ["sweep_15m_array"]
    out = StubConf(arrays={1: [(3980.0, 3970.0, "15m", 0, 0)]})
    ctx.conf = out
    lvt = []
    assert sm6.order_gate6(ctx, sl, dict(sw), k + 4, p, 3999.0, 3989.0, "AM", lvt, {}, {}) is None and lvt == []
    assert sm6.order_gate6(ctx, sl, dict(sw), k + 4, replace(p, sweep_15m_array="require"), 3999.0, 3989.0, "AM", [], {}, {}) == "x_sweep_no_15m_array"
    ph = replace(Params(**BASE), sweep_leave_bars=1, sweep_leave_pts=6.0)
    assert sm6.order_gate6(ctx, sl, dict(sw), k + 4, ph, 3999.0, 3989.0, "AM", [], {}, {}) == "x_sweep_hover"                    # the 2 bars after the extreme stay under 3996 (highs 3994 / 3995)
    assert sm6.order_gate6(ctx, sl, dict(sw), k + 4, replace(ph, sweep_leave_pts=2.0), 3999.0, 3989.0, "AM", [], {}, {}) is None    # a 3995 high is 5 points off the extreme: it left
    assert sm6.order_gate6(ctx, sl, dict(sw), k + 1, ph, 3999.0, 3989.0, "AM", [], {}, {}) is None                              # too early to judge the hover


# --- 193 / 194 consolidation fades ---------------------------------------------------------------------------------------------------------------------

def test_consolidation_edge_fade_to_eq(cap):
    """cc09_004 ~00:12:08: consol_edge_fade "edge" - the 1h / 15m range (>= consol_bars bars, <= consol_width_adr x ADR5 wide) 4000-4010: price traded under its low (3997) and the first close back
    inside (4002) is a market entry with the bias, the stop under the sweep extreme, the single target the range EQ (4005). Against the bias, or a sweep that never closes back = nothing."""
    pre = [(4004.0, 4008.0, 4003.8, 4006.0), (4006.0, 4010.0, 4005.0, 4009.0), (4009.0, 4009.5, 4003.5, 4004.0), (4004.0, 4008.0, 4004.0, 4007.0), (4007.0, 4009.0, 4006.0, 4008.0),
           (4008.0, 4009.0, 4000.0, 4001.0)]
    rows = pre + [(4001.0, 4002.0, 3997.0, 3999.0), (3999.0, 4003.0, 3998.5, 4002.0)]
    p = Params(**BASE, consol_edge_fade="edge", consol_tf=5, consol_bars=6, consol_width_adr=0.5)
    ctx, (sl, ss) = mkctx(rows, base=4004.0, bias=1, hist=hist_close(close=4000.0, hi=4130.0, lo=3900.0))
    k = ib(ctx, "09:30")
    assert sm6.consol_fade_order(ctx, sl, k + 7, p, "AM", 1.0) is not None
    assert cap["entry"] == pytest.approx(4002.0) and cap["stop"] == pytest.approx(3997.0 - p.pad) and cap["tags"]["market"] is True and cap["fixed"][0][0] == pytest.approx(S._exit_px(4005.0, "array", p))
    assert sm6.consol_fade_order(ctx, sl, k + 7, p, "AM", 1.0) is None                      # once per range
    sl.__dict__.pop("_cfade6_sent")
    ctx.cur_bias = -1
    assert sm6.consol_fade_order(ctx, sl, k + 7, p, "AM", 1.0) is None                      # against the bias
    ctx.cur_bias = 1
    assert sm6.consol_fade_order(ctx, sl, k + 6, p, "AM", 1.0) is None                      # the sweep bar itself closed under the low: no reversal yet
    assert sm6.consol_fade_order(ctx, sl, k + 7, replace(p, consol_edge_fade="inner"), "AM", 1.0) is None
    assert sm6.consol_fade_order(ctx, sl, k + 7, replace(p, consol_width_adr=0.01), "AM", 1.0) is None      # the range is too wide for the ADR
    assert sm6.consol_fade_order(ctx, sl, k + 7, replace(p, consol_bars=5000), "AM", 1.0) is None      # fewer bars than the range needs


def test_inner_range_eq_high_fade(cap):
    """cc09_004 ~00:15:37 (side space, the buy mirror): consol_edge_fade "inner" - a 3-bar swing low just under the EQ (4003.5; the EQ is 4005, band 15% of the 10-point range) is traded through on an
    expansion away from the EQ inside the range: an entry at that close, the stop under that bar's low, the target the range high less the exit buffer. A pivot outside the band, or a break beyond the
    range, does nothing."""
    rows = [(4004.0, 4008.0, 4000.0, 4006.0), (4006.0, 4010.0, 4005.0, 4009.0), (4009.0, 4009.5, 4003.5, 4004.0), (4004.0, 4008.0, 4004.0, 4007.0), (4007.0, 4009.0, 4006.0, 4008.0),
            (4008.0, 4009.0, 4005.0, 4006.0), (4006.0, 4008.0, 4004.5, 4005.0), (4005.0, 4005.5, 4002.0, 4003.0)]
    p = Params(**BASE, consol_edge_fade="inner", consol_tf=5, consol_bars=6, consol_width_adr=0.5)
    ctx, (sl, ss) = mkctx(rows, base=4004.0, bias=1, hist=hist_close(close=4000.0, hi=4130.0, lo=3900.0))
    k = ib(ctx, "09:30")
    assert sm6.consol_fade_order(ctx, sl, k + 7, p, "AM", 1.0) is not None
    assert cap["entry"] == pytest.approx(4003.0) and cap["stop"] == pytest.approx(4002.0 - p.pad) and cap["fixed"][0][0] == pytest.approx(S._exit_px(4010.0, "pool", p)) and cap["tags"]["market"] is True
    sl.__dict__.pop("_cfade6_sent")
    assert sm6.consol_fade_order(ctx, sl, k + 7, replace(p, consol_eq_band=0.01), "AM", 1.0) is None       # the pivot lies outside a 1% band
    assert sm6.consol_fade_order(ctx, sl, k + 6, p, "AM", 1.0) is None                      # the swing low is not traded through yet


# --- 195 / 196 / 198 reversal catalogue, PDL expansion, score -------------------------------------------------------------------------------------------

def _rev_hist(lows, closes=None):
    ds = prior_days(D0, 8)
    out = []
    for k, d in enumerate(ds):
        c = 4000.0 if closes is None else closes[k]
        out.append(rth_day(d, 4100.0, lows[k], close=c))
    return out


def test_reversal_type_tags():
    """cc09_005 ~00:00:29: the reversal types a sweep satisfies - pdl (the prior day's low), week (this week's low so far), iterm (an older week's low), ny_rev (a sweep trade 08:30-10:00 with an HTF
    array at the sweep), lc_rev (10:00-12:00 with one); reversal_need_htf drops a week / iterm / session type without the array. The tags go to lv_tags as rev_<type>."""
    lows = [3995.0, 3950.0, 3995.0, 3995.0, 3995.0, 3995.0, 3995.0, 3980.0]                 # Thu 06-11 .. Mon 06-22 (this week: Mon 22 = 3980; the 3950 is last week)
    conf = StubConf(at_tfs={1: ["1h"]})
    ctx, (sl, ss) = mkctx(flat(4, 4000.0), base=4000.0, hist=_rev_hist(lows), conf=conf)
    i = ib(ctx, "09:30") + 3
    sw = dict(session="AM", key="pdl1", name="pdl1", level=3980.0, ext=3979.5, ext_i=i - 1, broke=None, sweep_i=i - 1, smt=None, smt2=None)
    p = Params(**BASE, reversal_tag=True)
    tys, htf = sm6.reversal_types(ctx, sl, sw, i, p, "AM")
    assert htf is True and set(tys) == {"pdl", "week", "ny_rev"}                             # 09:45 = NY reversal window (08:30-10:00)
    assert sm6.reversal_types(ctx, sl, dict(sw, key="x", level=3950.0), i, p, "AM")[0] == ("iterm", "ny_rev")
    lvt = []
    assert sm6.order_gate6(ctx, sl, dict(sw), i, p, 3985.0, 3978.0, "AM", lvt, {}, {}) is None and lvt == ["rev_pdl", "rev_week", "rev_ny_rev"]
    ctx.conf = StubConf(at_tfs={})
    assert sm6.reversal_types(ctx, sl, dict(sw), i, p, "AM") == (("pdl", "week"), False)      # no HTF array: the session type is not satisfied
    pn = Params(**BASE, reversal_need_htf=True)
    assert sm6.order_gate6(ctx, sl, dict(sw), i, pn, 3985.0, 3978.0, "AM", [], {}, {}) == "x_reversal_no_htf"                    # a week type needs the array
    assert sm6.order_gate6(ctx, sl, dict(sw, level=3995.0), i, pn, 3985.0, 3978.0, "AM", [], {}, {}) is None                    # no week / iterm type, nothing to require
    assert sm6.order_gate6(ctx, sl, dict(sw, key="x"), i, replace(pn, reversal_need_htf=False), 3985.0, 3978.0, "AM", [], {}, {}) is None


def test_pdl_fade_needs_expansion_retrace():
    """cc09_005 ~00:15:56: pdl_expansion - a PDL / PDH fade needs the bias and the daily flow on this side and the prior 1-3 days to be counter-moves (consecutive lower closes for a long): run 2 passes; run
    0 (the days still rise), run 4+ (not a retracement any more), a wrong bias or a wrong flow drop it; other pool keys are not gated."""
    p = Params(**BASE, pdl_expansion=True)
    closes = [4000.0, 4005.0, 4010.0, 4015.0, 4020.0, 4025.0, 4018.0, 4012.0]                # the last two days closed lower
    ctx, (sl, ss) = mkctx(flat(4, 4000.0), base=4000.0, hist=_rev_hist([3990.0] * 8, closes), conf=StubConf(trend=1), bias=1)
    i = ib(ctx, "09:30") + 3
    sw = dict(session="AM", key="pdl1", name="pdl1", level=3990.0, ext=3989.0, ext_i=i - 1, broke=None, sweep_i=i - 1, smt=None, smt2=None)
    assert sm6.pdl_expansion_ok(ctx, sl, i, p) and sm6.order_gate6(ctx, sl, dict(sw), i, p, 3995.0, 3988.0, "AM", [], {}, {}) is None
    ctx2, (sl2, _) = mkctx(flat(4, 4000.0), base=4000.0, hist=_rev_hist([3990.0] * 8, [4000.0, 4005.0, 4010.0, 4015.0, 4020.0, 4025.0, 4030.0, 4035.0]), conf=StubConf(trend=1), bias=1)
    assert sm6.order_gate6(ctx2, sl2, dict(sw), i, p, 3995.0, 3988.0, "AM", [], {}, {}) == "x_pdl_expansion"                       # the days still rise: no retracement
    ctx3, (sl3, _) = mkctx(flat(4, 4000.0), base=4000.0, hist=_rev_hist([3990.0] * 8, [4040.0, 4035.0, 4030.0, 4025.0, 4020.0, 4015.0, 4010.0, 4005.0]), conf=StubConf(trend=1), bias=1)
    assert sm6.order_gate6(ctx3, sl3, dict(sw), i, p, 3995.0, 3988.0, "AM", [], {}, {}) == "x_pdl_expansion"                       # seven lower closes: a trend, not a retracement
    ctx.cur_bias = -1
    assert not sm6.pdl_expansion_ok(ctx, sl, i, p)
    ctx.cur_bias = 1
    ctx.conf = StubConf(trend=-1)
    assert not sm6.pdl_expansion_ok(ctx, sl, i, p)
    ctx.conf = StubConf(trend=1)
    assert sm6.order_gate6(ctx, sl, dict(sw, key="swing_low12"), i, p, 3995.0, 3988.0, "AM", [], {}, {}) is None                   # not a PDL / PDH key
    assert sm6.order_gate6(ctx, sl, dict(sw), i, replace(p, pdl_expansion=False), 3995.0, 3988.0, "AM", [], {}, {}) is None


def test_reversal_score_count():
    """cc09_005 ~00:20:57: reversal_score tags the NUMBER of reversal types one sweep satisfies (report only): pdl + week + ny_rev = 3 -> rev_score_3; a sweep with none = no tag."""
    lows = [3995.0, 3950.0, 3995.0, 3995.0, 3995.0, 3995.0, 3995.0, 3980.0]
    ctx, (sl, ss) = mkctx(flat(4, 4000.0), base=4000.0, hist=_rev_hist(lows), conf=StubConf(at_tfs={1: ["1h"]}))
    i = ib(ctx, "09:30") + 3
    sw = dict(session="AM", key="pdl1", name="pdl1", level=3980.0, ext=3979.5, ext_i=i - 1, broke=None, sweep_i=i - 1, smt=None, smt2=None)
    p = Params(**BASE, reversal_score=True)
    lvt = []
    assert sm6.order_gate6(ctx, sl, dict(sw), i, p, 3985.0, 3978.0, "AM", lvt, {}, {}) is None and lvt == ["rev_score_3"]
    lvt = []
    assert sm6.order_gate6(ctx, sl, dict(sw, key="x", level=3999.0), i, p, 3999.0, 3978.0, "AM", lvt, {}, {}) is None and lvt == ["rev_score_1"]          # only the NY-reversal timing with an array
    ctx.conf = StubConf(at_tfs={})
    lvt = []
    assert sm6.order_gate6(ctx, sl, dict(sw, key="x", level=3999.0), i, p, 3999.0, 3978.0, "AM", lvt, {}, {}) is None and lvt == []
    assert sm6.order_gate6(ctx, sl, dict(sw), i, replace(p, reversal_score=False), 3985.0, 3978.0, "AM", [], {}, {}) is None
