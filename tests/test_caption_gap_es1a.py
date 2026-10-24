"""Caption-gap pass, package entries_stops_sizing #1/3, part A: the unit tests of the 35 specs (bias_htf_intermarket.md items 118, 196; definitions_pd_arrays_structure.md items 4, 7, 9, 11, 14, 23, 26, 34, 39, 42, 44, 45,
55, 59, 76, 77, 78, 79, 84, 87, 88, 89, 92, 97, 100, 102, 109, 129, 130, 131, 132, 136, 141). Hand-made 5-minute days (a whole 00:00-16:15 frame) through run_day (the real engine path) and unit tests of the es1.py
helpers on hand-made Sides. No platform-specific paths; nothing here needs market data. The study variants and the no-look-ahead runs are in test_caption_gap_es1b.py."""
from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from mentorship import backtest as B, es1, htf, levels as L, sm2, strategy as S, study
from mentorship.strategy import Params

from test_levels_detectors import NY
from test_review_fixes import A_LOCK, A_ROWS, BASE, D0, day, history, mirror, run as rf_run
from test_caption_gap_sm1a import StubConf, mkctx, sd_of, stub

A = np.array

NEW_SWITCHES = (
    "no_origin_retest", "entry_pd_frame", "ob_need_fvg", "cisd_ob_px", "cisd_adds", "ob_vi_overshoot", "mt_break", "breaker_refine", "iofed_strict", "add_pref_ob_in_vi", "gap_tf_mode", "vi_tol", "vi_tol_small_pts",
    "prop_mt_test", "prop_fail_flip", "prop_deep_mult", "prop_deep_cut", "mit_iofed_edge", "leg_pd_anchor", "broken_wick_stop", "far_edge_reach", "fvg_edge", "ob_ce_confluence", "ob_ce_tol_pts", "leg_fib",
    "htf_depth_mult", "ob_need_narrative", "ob_need_htf_array", "ob_wick_ltf_entry", "htf_ob_anchor", "scan_tfs", "two_min_ce", "fvg_skip_below_pool_short", "mtf_hold", "ote_gate_4th", "ote_reanchor", "ote_nested",
    "ote_parent_third", "ob_mt_range", "ob_reach",
)


def one(df, hist, **kw):
    tr, *_ = rf_run(df, hist, Params(**{**BASE, **kw}), A_LOCK)
    return tr


# --- defaults / validation ---------------------------------------------------------------------------------------------------------

def test_new_switch_defaults_and_validation():
    p = Params()
    assert (p.no_origin_retest, p.entry_pd_frame, p.ob_need_fvg, p.cisd_ob_px, p.cisd_adds, p.ob_vi_overshoot, p.mt_break, p.breaker_refine, p.iofed_strict, p.add_pref_ob_in_vi, p.gap_tf_mode, p.vi_tol,
            p.vi_tol_small_pts) == (False, "leg", False, "eq", False, False, "off", False, False, False, "", "none", 2.0)
    assert (p.prop_mt_test, p.prop_fail_flip, p.prop_deep_mult, p.prop_deep_cut, p.mit_iofed_edge, p.leg_pd_anchor, p.broken_wick_stop, p.far_edge_reach, p.fvg_edge, p.ob_ce_confluence, p.ob_ce_tol_pts,
            p.leg_fib, p.htf_depth_mult) == ("close", False, 1.0, 0.5, False, "displacement_leg", "body_edge", False, "original", False, 1.0, "wick", (1.0, 1.0, 1.0))
    assert (p.ob_need_narrative, p.ob_need_htf_array, p.ob_wick_ltf_entry, p.htf_ob_anchor, p.scan_tfs, p.two_min_ce, p.fvg_skip_below_pool_short, p.mtf_hold, p.ote_gate_4th, p.ote_reanchor, p.ote_nested,
            p.ote_parent_third, p.ob_mt_range, p.ob_reach, p.mt_mode) == (False, True, False, "extreme", (1,), False, False, False, False, False, False, False, "body", "wick", "body")
    for kw in (dict(entry_pd_frame="x"), dict(cisd_ob_px="x"), dict(mt_break="x"), dict(gap_tf_mode="x"), dict(vi_tol="x"), dict(prop_mt_test="x"), dict(leg_pd_anchor="x"), dict(broken_wick_stop="x"),
               dict(fvg_edge="x"), dict(leg_fib="x"), dict(htf_ob_anchor="x"), dict(ob_mt_range="x"), dict(ob_reach="x"), dict(mt_mode="x"), dict(prop_deep_cut=1.0), dict(prop_deep_mult=-1),
               dict(htf_depth_mult=(1, 1)), dict(htf_depth_mult=(1, 1, -1)), dict(scan_tfs=()), dict(scan_tfs=(0,)), dict(ob_ce_tol_pts=-1), dict(vi_tol_small_pts=-1), dict(entry_arrays=("nope",))):
        with pytest.raises(ValueError):
            Params(**kw)
    for kw in (dict(mt_mode="sensitive"), dict(mt_mode="body_single_range_blended"), dict(entry_arrays=("broken_wick_ce",)), dict(entry_arrays_order=("broken_wick_ce",)), dict(scan_tfs=(1, 2, 3, 4, 5, 120))):
        Params(**kw)


def test_every_switch_has_a_study_variant():
    on = set()
    for k, v in study._ES1_DECISIONS.items():
        Params(**v)
        on |= set(v)
    missing = [s for s in NEW_SWITCHES if s not in on and s not in ("vi_tol_small_pts", "prop_deep_cut", "ob_ce_tol_pts", "ob_need_htf_array")]
    assert not missing, missing


# --- D4-mt-source-tally (11): the MT modes and mt_break -----------------------------------------------------------------------------

def test_mt_modes_on_a_blended_block_and_a_single_candle():
    # two down candles: (101 -> 100) and (100 -> 98.2): highest open 101, lowest close 98.2, range 98.0 .. 101.5
    rows = [(101.0, 101.5, 99.5, 100.0), (100.0, 100.5, 98.0, 98.2), (98.2, 100.0, 98.1, 99.9)]
    sd = sd_of(rows)
    blk = L.order_block_blend(sd.o, sd.h, sd.l, sd.c, 0, 1, "bull")
    one_c = L.order_block_blend(sd.o, sd.h, sd.l, sd.c, 1, 1, "bull")
    mt = lambda mode, ob: es1.mt_of(Params(mt_mode=mode), sd, ob)
    assert mt("body", blk) == pytest.approx(99.6) and mt("range", blk) == pytest.approx(99.75)
    assert mt("sensitive", blk) == pytest.approx((101.5 + 101.0) / 2)                 # (high + open of the first candle) / 2
    assert mt("body_single_range_blended", blk) == pytest.approx(99.75)               # a multi-candle block: the range mid
    assert mt("body_single_range_blended", one_c) == pytest.approx(99.1) and mt("body", one_c) == pytest.approx(99.1)   # a single candle: the body mean
    d = dict(j=0, k=1, hi=101.5, lo=98.0)
    assert es1.dict_mt(Params(mt_mode="sensitive"), sd, d, 99.6) == pytest.approx(101.25)
    assert es1.dict_mt(Params(mt_mode="body_single_range_blended"), sd, d, 99.6) == pytest.approx(99.75)
    assert es1.dict_mt(Params(mt_mode="body_single_range_blended"), sd, dict(d, k=0), 99.6) == pytest.approx(99.6)
    assert es1.dict_mt(Params(mt_mode="range"), sd, d, 99.6) == pytest.approx(99.75)   # review fix: "range" is the full range mid on the dict path too
    assert es1.candle_mt(Params(mt_mode="sensitive"), 100.0, 103.0, 99.0, 102.0) == 101.5 and es1.candle_mt(Params(), 100.0, 103.0, 99.0, 102.0) == 101.0
    assert es1.candle_mt(Params(mt_mode="range"), 100.0, 103.0, 99.0, 102.0) == 101.0
    # a mean threshold from a Side mirrored to a short
    sds = sd_of([(-r[0], -r[2], -r[1], -r[3]) for r in rows], sign=-1)
    assert sds.o[0] == 101.0 and sds.h[0] == 101.5                                       # (the mirror of a mirror: the same bullish Side)


WICK = [(100.3, 101.0, 99.0, 100.9)]                                                       # scenario A with a wick under the MT (99.4) and the stop (99.15) on the 09:55 bar


def _a_rows(wick=True):
    return A_ROWS[:5] + (WICK if wick else [A_ROWS[5]]) + A_ROWS[6:]


def test_mt_break_close_trade_warn():
    hist = history()
    df = day(_a_rows(), spike=True)
    k = dict(min_risk_pts=0.5)                                                              # (the MT stop 99.15 is 0.85 under the 100.0 limit: not the sweep-extreme fallback)
    base = one(df, hist, **k)                                                               # built: the MT stop (99.15) is traded under on the wick
    assert len(base) == 1 and base[0].exits[0][3] == "stop" and base[0].stop == pytest.approx(99.15)
    close = one(df, hist, mt_break="close", **k)
    assert len(close) == 1 and close[0].exits[0][3] != "stop" and "mt_close" in close[0].lv_tags and close[0].stop == pytest.approx(98.25) and not close[0].mt_warn   # the wick holds (far-edge stop), a body CLOSE under the MT would exit
    warn = one(df, hist, mt_break="warn", **k)
    assert len(warn) == 1 and warn[0].exits[0][3] != "stop" and "mt_warn" in warn[0].lv_tags and warn[0].mt_warn   # a tag only
    trade = one(df, hist, mt_break="trade", **k)
    assert len(trade) == 1 and trade[0].exits[0][3] == "stop" and trade[0].stop == pytest.approx(99.15)   # any trade under the MT stops
    # a body close under the MT exits under "close"
    rows = A_ROWS[:5] + [(100.3, 100.4, 98.9, 99.0)] + A_ROWS[6:]
    cl = one(day(rows, spike=True), hist, mt_break="close", **k)
    assert cl and cl[0].exits[0][3] == "ob_mt_close"


# --- A12-ltf-ob-upper-half (136) ----------------------------------------------------------------------------------------------------

def test_ob_mt_entry_under_range_is_the_candle_midpoint():
    ob = dict(j=0, k=1, body_top=100.0, body_low=98.8, mt=99.4, hi=100.1, lo=98.5)
    sd = sd_of([(100.0, 100.1, 99.5, 99.6), (99.6, 99.7, 98.5, 98.8)])
    from mentorship import entries as EN
    assert EN.ob_entry_price(ob, sd, Params(ob_entry_px="mt"), None) == pytest.approx(99.4)
    assert EN.ob_entry_price(ob, sd, Params(ob_entry_px="mt", ob_mt_range="range"), None) == pytest.approx(99.3)
    assert EN.ob_entry_price(ob, sd, Params(ob_entry_px="body_top", ob_mt_range="range"), None) == 100.0       # only the "mt" entry follows it
    # through the engine: scenario A with the limit at the OB midpoint (99.3 instead of the body top 100.0)
    rows = A_ROWS[:4] + [(100.7, 100.8, 99.2, 100.3)] + A_ROWS[5:]                         # the retrace bar dips to 99.2
    tr = one(day(rows, spike=True), history(), ob_entry_px="mt", ob_mt_range="range")
    assert tr and tr[0].entry_kind == "ob_pre" and tr[0].entry == pytest.approx(99.3)
    assert one(day(rows, spike=True), history(), ob_entry_px="mt")[0].entry == pytest.approx(99.4)


# --- A12-ob-requires-signatures (4) ----------------------------------------------------------------------------------------------

FVG_ROWS = A_ROWS[:3] + [(100.2, 100.9, 100.1, 100.8)] + A_ROWS[4:]                           # an FVG [99.7, 100.1] whose first candle is the OB candle (09:35)


def test_ob_needs_an_fvg_before_it_arms():
    hist = history()
    sd = sd_of(FVG_ROWS)
    assert es1.ob_fvg_ok(sd, 1, 3) and not es1.ob_fvg_ok(sd, 1, 2) and es1.ob_fvg_ok(sd, 0, 3) and not es1.ob_fvg_ok(sd, 3, 3)     # the third candle must have closed; c1 must be the OB candle (k) or the next
    plain = sd_of(A_ROWS)
    assert not es1.ob_fvg_ok(plain, 1, 7)                                                           # A_ROWS: no gap starts at the OB candle / the one after it
    base = one(day(A_ROWS, spike=True), hist)
    assert len(base) == 1 and base[0].entry_kind == "ob_pre"                                       # built: the OB arms at the first close above its bodies
    s0 = dict(sm2.HITS)
    assert one(day(A_ROWS, spike=True), hist, ob_need_fvg=True) == []                               # a down-close candle without the displacement / FVG is only a potential OB
    assert sm2.HITS.get("ob_potential", 0) > s0.get("ob_potential", 0)
    tr = one(day(FVG_ROWS, spike=True), hist, ob_need_fvg=True)
    assert len(tr) == 1 and tr[0].entry_kind == "ob_pre" and tr[0].entry == 100.0                    # the same OB arms once the gap printed (c3 = the 09:45 bar)
    assert one(day(FVG_ROWS, spike=True), hist)[0].entry == 100.0


# --- A12-ob-requires-narrative (87) ------------------------------------------------------------------------------------------------

def test_narrative_conditions():
    rows = [(100.0, 100.1, 99.5, 99.6), (99.6, 99.7, 98.5, 98.8), (98.8, 99.9, 98.7, 99.8), (99.8, 100.8, 99.7, 100.7), (100.7, 100.8, 99.9, 100.3)]
    arr = {1: [(100.5, 98.0, "1h", 1, 0.0)]}
    ob = dict(k=1, j=0, body_top=100.0, body_low=98.8)
    sw = dict(key="pdl", ext_i=1, sweep_i=0)
    p = Params(**BASE, ob_need_narrative=True)

    def ok(bias=1, conf=None, sw_=sw, p_=p, ob_=ob):
        ctx, (sd, _) = mkctx(rows, p_, bias=bias, conf=conf if conf is not None else StubConf(arrays=arr), start="09:30")
        return es1.narrative_ok(ctx, sd, dict(sw_, ext_i=S._idx_at(ctx, 570) + sw_["ext_i"], sweep_i=S._idx_at(ctx, 570) + sw_["sweep_i"]), dict(ob_, k=S._idx_at(ctx, 570) + ob_["k"]),
                                S._idx_at(ctx, 570) + 4, p_)
    assert ok()                                                                                      # bias this way, a pool swept by the OB candle, the OB bodies in the HTF array
    assert not ok(bias=0) and not ok(bias=-1)                                                        # (1) the session bias must agree
    assert not ok(conf=StubConf())                                                                   # (2) no HTF array holds the OB
    assert ok(conf=StubConf(), p_=replace(p, ob_need_htf_array=False))                               # ... unless the array requirement is off
    assert not ok(conf=StubConf(arrays={1: [(99.0, 98.0, "1h", 1, 0.0)]}))                           # an array that does not contain the bodies (top 99.0 < 100.0 - tolerance)
    assert not ok(sw_=dict(sw, sweep_i=3))                                                           # (3) the pool was swept AFTER the OB candle: no transitional event before it
    assert ok(sw_=dict(sw, sweep_i=3, key="htf_array"))                                              # an HTF-array premise is itself the transition


def test_narrative_gates_the_engine_order():
    hist = history()
    base = one(day(A_ROWS, spike=True), hist)
    assert len(base) == 1
    assert one(day(A_ROWS, spike=True), hist, ob_need_narrative=True, ob_need_htf_array=False)[0].entry == 100.0      # the locked draw is the bias (+1); the pool sweep precedes the OB
    assert one(day(A_ROWS, spike=True), hist, ob_need_narrative=True) == []                          # no HTF array in the frame: the OB is "just a candle"


# --- A12-ob-overshoot-to-vi (9) -----------------------------------------------------------------------------------------------------

VI_ROWS = [(100.0, 100.1, 99.5, 99.6), (99.6, 99.7, 98.9, 99.0), (98.2, 98.5, 98.0, 98.4), (98.7, 100.5, 98.1, 100.4), (100.4, 100.5, 99.9, 100.2),
           (100.2, 100.6, 98.5, 100.4), (100.4, 104.0, 100.3, 103.9), (103.9, 108.5, 103.8, 108.4)]


def test_vi_far_edge_and_overshoot_engine():
    sd = sd_of(VI_ROWS)
    p = Params(es_pt=1.0)
    assert es1.vi_far_edge(sd, 98.9, 100.0, 0, 3, p) == pytest.approx(98.4)                           # the VI [98.4, 98.7] touches the OB's far side (low 98.9) and reaches below it
    assert es1.vi_far_edge(sd, 98.9, 100.0, 0, 2, p) is None                                          # not formed yet at bar 2
    assert es1.vi_far_edge(sd, 99.6, 100.0, 0, 3, p) is None                                          # a VI whose top (98.7) is more than the tolerance under the OB low
    hist = history()
    k = dict(min_risk_pts=0.5)
    base = one(day(VI_ROWS, spike=True), hist, **k)
    assert len(base) == 1 and base[0].stop == pytest.approx(99.25) and base[0].exits[0][3] == "stop"      # built: the OB MT stop is hit by the wick into the VI
    tr = one(day(VI_ROWS, spike=True), hist, ob_vi_overshoot=True, **k)
    assert len(tr) == 1 and tr[0].stop == pytest.approx(98.15) and tr[0].exits[0][3] != "stop"            # a wick into the VI keeps the trade (stop = far edge - 1 tick)
    rows = VI_ROWS[:5] + [(100.2, 100.3, 98.2, 98.3)] + VI_ROWS[6:]                                   # a CLOSE under the VI far edge exits
    cl = one(day(rows, spike=True), hist, ob_vi_overshoot=True, **k)
    assert cl and cl[0].exits[0][3] == "ob_vi_close"


# --- scenario C: a sweep of the overnight low (99.8), the MSS close 101.0 (> 100.2) at 09:45 and an FVG [99.8, 100.4] ending at 09:50; the retrace to 100.4 fills at 09:55 ------------

C_ROWS = [(100.0, 100.1, 99.4, 99.5), (99.5, 99.6, 98.6, 98.7), (98.7, 99.8, 98.7, 99.7), (99.7, 101.2, 99.6, 101.0), (101.0, 101.8, 100.4, 101.6),
          (101.6, 101.7, 100.3, 100.5), (100.5, 103.0, 100.4, 102.9), (102.9, 108.5, 102.8, 108.4)]
POST = dict(ob_entry="post_mss", draw_lock="off", htf_resist_cap=False, min_risk_pts=0.5, leg_pd=0.0, news_wait="off", min_draw_pts=0.0)


def c_run(rows=None, hist=None, **kw):
    tr, *_ = rf_run(day(rows or C_ROWS), hist or history(), Params(**{**BASE, **POST, **kw}), {})
    return tr


def test_scenario_c_base():
    tr = c_run()
    assert len(tr) == 1 and tr[0].entry_kind == "fvg" and tr[0].entry == pytest.approx(100.4) and tr[0].stop < 99.6


# --- B5-prior-day-ny-range-retracement (196), A21-implied-range-to-target (55), A21-post-cisd-range-retrace (109), A21-intraday-fib-bodies (79) -------------------------------------

def test_entry_pd_frame_prev_day_ny_any():
    # leg_pd 0.5: the displacement leg (98.6 .. 101.8) puts the line at 100.2: the 100.4 limit is in its premium and waits; the previous day 98 .. 104 puts it at 101: in discount
    assert c_run(leg_pd=0.5) == []
    hist = history(hi=104.0, lo=98.0)
    assert c_run(hist=hist, leg_pd=0.5) == []
    tr = c_run(hist=hist, leg_pd=0.5, entry_pd_frame="prev_day")
    assert len(tr) == 1 and tr[0].entry == pytest.approx(100.4)
    assert len(c_run(hist=hist, leg_pd=0.5, entry_pd_frame="any")) == 1 and len(c_run(hist=hist, leg_pd=0.5, entry_pd_frame="prev_ny")) == 1
    assert c_run(leg_pd=0.5, entry_pd_frame="leg") == []                                      # "leg" = the built check
    # a previous day whose range puts the line under the entry (90 .. 108: line 99) rejects it; "any" still takes the leg line (also failing here)
    assert c_run(leg_pd=0.5, entry_pd_frame="prev_day") == [] and c_run(leg_pd=0.5, entry_pd_frame="any") == []
    # unit: the frames (real prices -> side space), prev_full (08:30 on) vs the RTH-only history
    ctx = stub(5)
    ctx.prev_full = pd.DataFrame({"open": [97.0, 100.0, 100.0], "high": [106.0, 104.0, 103.0], "low": [96.0, 99.0, 98.0], "close": [100.0, 100.0, 100.0]},
                                 index=pd.DatetimeIndex(["2026-06-22 08:30", "2026-06-22 09:30", "2026-06-22 15:55"]).tz_localize(NY))
    assert es1.prev_range(ctx, "prev_day") == (98.0, 104.0) and es1.prev_range(ctx, "prev_ny") == (96.0, 106.0)
    sd = SimpleNamespace(x=lambda v: v)
    assert es1.frame_line(ctx, sd, Params(leg_pd=0.5, entry_pd_frame="prev_ny"), 100.0) == pytest.approx(101.0)       # 96 + 0.5 x (106 - 96)
    assert es1.frame_line(ctx, sd, Params(leg_pd=0.5, entry_pd_frame="any"), 102.0) == pytest.approx(102.0)           # the highest line wins
    sdm = SimpleNamespace(x=lambda v: -v)
    assert es1.frame_line(ctx, sdm, Params(leg_pd=0.5, entry_pd_frame="prev_day"), 0.0) == pytest.approx(-101.0)       # a short: the mirrored range -104 .. -98 -> -101
    ctx2 = stub(5)
    ctx2.hist = []
    assert es1.frame_line(ctx2, sd, Params(leg_pd=0.5, entry_pd_frame="prev_day"), 77.0) == 77.0                      # no data: the leg line


def test_leg_pd_anchor_target_and_retrace_range():
    # target: the range runs from the sweep extreme (98.6) to the first target (the 108 previous-day high): line 103.3 > the 100.4 limit
    assert c_run(leg_pd=0.5) == []
    tr = c_run(leg_pd=0.5, leg_pd_anchor="target")
    assert len(tr) == 1 and tr[0].entry == pytest.approx(100.4)
    # retrace_range: the swing high the decline began from (100.2) .. the sweep low (98.6): leg_pd 0.9 puts the line at 100.04 < 100.4 (the displacement leg's line is 101.48)
    assert len(c_run(leg_pd=0.9)) == 1
    assert c_run(leg_pd=0.9, leg_pd_anchor="retrace_range") == []
    sw = dict(ext=98.6, ref_px=100.2)
    assert es1.pd_top_fixed(None, sw, 5, Params(leg_pd_anchor="retrace_range")) == 100.2 and es1.pd_top_fixed(None, sw, 5, Params()) is None
    assert es1.pd_top_fixed(None, dict(ext=98.6, ref_px=98.0), 5, Params(leg_pd_anchor="retrace_range")) is None      # (a reference under the low: not a range)


def test_leg_fib_body_uses_the_bodies():
    sd = sd_of(C_ROWS)
    lo, hi = es1.body_leg(sd, dict(ext_i=1), 4)
    assert (lo, hi) == (pytest.approx(98.7), pytest.approx(101.6))                           # lowest min(o, c) .. highest max(o, c) since the sweep extreme
    assert len(c_run(leg_pd=0.58)) == 1                                                       # wicks: line 98.6 + 0.58 x 3.2 = 100.456 >= 100.4
    assert c_run(leg_pd=0.58, leg_fib="body") == []                                           # bodies: line 98.7 + 0.58 x 2.9 = 100.382 < 100.4
    assert len(c_run(leg_pd=0.6, leg_fib="body")) == 1


# --- M13: the OTE gate (129), the re-anchor (130), nested ranges (131), the short mirror (132) ------------------------------------------------------------------------------

D_ROWS = C_ROWS[:5] + [(101.6, 101.7, 99.4, 99.6), (99.6, 100.2, 99.6, 100.0), (100.0, 103.0, 99.9, 102.9), (102.9, 108.5, 102.8, 108.4)]      # a dip to the sweet spot on candle h+1
E_ROWS = C_ROWS[:6] + [(100.5, 103.0, 100.4, 102.9), (102.9, 102.95, 102.0, 102.1), (102.1, 102.2, 99.85, 100.0), (100.0, 108.5, 99.9, 108.4)]  # a new swing high (103.0) above H


def test_ote_gate_4th_candle():
    # unit: bar h is the highest high (index 4); bar 5 and bar 6 must be lower - the arming candle is the 4th (h+2)
    sd = sd_of(C_ROWS[:6] + [(100.5, 101.0, 100.2, 100.6)])
    p = Params(ote="limit", ote_gate_4th=True)
    sw = dict(ext_i=1)
    assert not es1.ote_gate_ok(sd, sw, 4, p) and not es1.ote_gate_ok(sd, sw, 5, p) and es1.ote_gate_ok(sd, sw, 6, p)
    assert not es1.ote_gate_ok(sd_of(C_ROWS[:7]), sw, 6, p)                                   # bar 6 makes a new extreme (103.0): the gate is redone (a new far extreme before EQ)
    # engine: the dip to the 70.5% sweet spot (99.544) on candle h+1 is ignored - without the gate the limit is filled there, with it the order waits for the 4th candle
    ote = dict(ote="limit")
    t0 = c_run(D_ROWS, **ote)
    assert len(t0) == 1 and t0[0].entry == pytest.approx(99.544) and t0[0].entry_time.minute == 55
    t1 = c_run(D_ROWS, ote_gate_4th=True, **ote)
    assert t1 == []                                                                          # the ignored dip filled nothing; the order armed on the 4th candle never gets its retrace
    # a retrace AFTER the gate opened fills at the same sweet spot
    rows = D_ROWS[:5] + [(101.6, 101.7, 100.9, 101.0), (101.0, 101.2, 100.6, 100.9), (100.9, 101.0, 99.4, 99.6), (99.6, 108.5, 99.5, 108.4)]
    t2 = c_run(rows, ote_gate_4th=True, **ote)
    assert len(t2) == 1 and t2[0].entry == pytest.approx(99.544) and t2[0].entry_time.minute == 5 and t2[0].entry_time.hour == 10


def test_ote_reanchor_moves_the_pending_limit():
    ote = dict(ote="limit")
    assert c_run(E_ROWS, **ote) == []                                                        # the 99.544 limit is never reached
    tr = c_run(E_ROWS, ote_reanchor=True, **ote)
    assert len(tr) == 1 and tr[0].entry == pytest.approx(103.0 - 0.705 * (103.0 - 98.6))      # H moved to the new swing high, the band was recomputed with L kept
    # unit
    sd = sd_of(E_ROWS)
    o = dict(ext_i=1, ext=98.6, leg_hi0=101.8, stop=98.35, entry=99.544, shares=100, zone_top=100.4, i=4)
    assert es1.ote_reprice(sd, o, 6, Params(ote="limit")) is None                              # the swing high at bar 6 is not confirmed before bar 7
    o2 = es1.ote_reprice(sd, o, 7, Params(ote="limit"))
    assert o2["leg_hi0"] == 103.0 and o2["i"] == 7 and o2["leg"] == (98.6, 103.0) and o2["shares"] < 100          # (a deeper entry -> the same dollar risk: fewer shares ... here a shallower one: smaller risk)
    lo_, hi_, sweet = L.ote_band(98.6, 103.0)
    assert o2["entry"] == pytest.approx(sweet)
    o3 = dict(o, ext=98.6)
    sd2 = sd_of(E_ROWS[:3] + [(99.5, 99.9, 98.0, 98.2)] + E_ROWS[4:])
    assert es1.ote_reprice(sd2, o3, 7, Params(ote="limit")) is None                          # a trade under L invalidates the leg


def test_ote_nested_children_and_parent_third():
    # parent ext 98.0 (bar 0); a child low 99.0 (bar 3, a 3-candle swing low) that held; the high 103.0
    rows = [(100.0, 100.5, 98.0, 98.5), (98.5, 100.0, 98.4, 99.9), (99.9, 101.0, 99.5, 100.8), (100.8, 100.9, 99.0, 99.2), (99.2, 101.5, 99.1, 101.3), (101.3, 103.0, 101.0, 102.9),
            (102.9, 103.0, 101.5, 101.8)]
    sd = sd_of(rows)
    sw = dict(ext_i=0, ext=98.0)
    kids = es1.ote_children(sd, sw, 6)
    assert kids == [99.0]
    p = Params(ote="filter", ote_nested=True)
    lo_p, hi_p, _ = L.ote_band(98.0, 103.0)
    lo_c, hi_c, sweet_c = L.ote_band(99.0, 103.0)
    assert hi_c > hi_p
    inside_child_only = (hi_p + hi_c) / 2 + 0.2
    assert not lo_p <= inside_child_only <= hi_p and lo_c <= inside_child_only <= hi_c
    assert es1.ote_band_for(sd, sw, 6, p, inside_child_only, 98.0, 103.0) == 99.0              # the entry is in the CHILD's band
    assert es1.ote_band_for(sd, sw, 6, p, (lo_p + hi_p) / 2, 98.0, 103.0) in (98.0, 99.0)
    assert es1.ote_band_for(sd, sw, 6, p, 104.0, 98.0, 103.0) is None
    assert es1.ote_band_for(sd, sw, 6, replace(p, ote_nested=False), inside_child_only, 98.0, 103.0) is None
    # a child stopped out (a trade under its low) is dropped: back to the parent
    rows2 = rows[:6] + [(102.9, 103.0, 98.9, 99.0)]
    assert es1.ote_children(sd_of(rows2), sw, 6) == []
    # parent_third: the lower third of the parent swing (98.0 .. 103.0 -> up to 99.67) AND under the EQ of the small range (99.0 .. 103.0 -> 101)
    assert es1.parent_third_ok(sd, sw, 6, p, 99.5, 103.0, 98.0) and not es1.parent_third_ok(sd, sw, 6, p, 100.2, 103.0, 98.0)
    sw2 = dict(ext_i=0, ext=98.0)
    assert not es1.parent_third_ok(sd, sw2, 6, p, 99.8, 103.0, 98.0)                           # 99.8 is above 98 + 5/3
    # engine: nested and parent_third run end to end
    assert len(c_run(E_ROWS[:6], ote="limit", ote_nested=True)) >= 0
    c_run(C_ROWS, ote="filter", ote_nested=True, ote_parent_third=True)


def test_short_ote_mirror_bands_are_above_the_eq():
    """M13-short-ote-mirror: for a short the 62-79% band / the 70.5% sweet spot lie ABOVE the EQ of the leg (the mirror of the long band) - already built (the engine runs shorts as mirrored longs)."""
    rows = D_ROWS
    long_ = c_run(rows, ote="limit")
    assert len(long_) == 1 and long_[0].entry == pytest.approx(99.544)
    mir = mirror(day(rows))
    tr, *_ = rf_run(mir, history(), Params(**{**BASE, **POST, "ote": "limit"}), {})
    sh = [t for t in tr if t.side == "short"]
    assert len(sh) == 1 and sh[0].entry == pytest.approx(300.0 - 99.544)
    hi_, lo_ = 300.0 - 98.6, 300.0 - 101.8                                                      # the real swing high / low of the short's leg
    eq = (hi_ + lo_) / 2
    assert sh[0].entry > eq and lo_ + 0.62 * (hi_ - lo_) <= sh[0].entry <= lo_ + 0.79 * (hi_ - lo_)
    assert sh[0].entry == pytest.approx(lo_ + 0.705 * (hi_ - lo_))                              # L + 0.705 R


# --- A12-cisd-open-buy-level (7) ----------------------------------------------------------------------------------------------------

CISD_ROWS = [(100.4, 100.5, 99.9, 100.0), (100.0, 100.1, 99.4, 99.5), (99.5, 99.6, 98.6, 98.7), (98.7, 99.8, 98.7, 99.7), (99.7, 100.7, 99.6, 100.5),
             (100.5, 100.6, 100.1, 100.4), (100.4, 100.5, 100.0, 100.1), (100.1, 100.2, 99.6, 99.8), (99.8, 100.7, 99.7, 100.5), (100.5, 100.6, 100.3, 100.4),
             (100.4, 103.0, 100.3, 102.9), (102.9, 108.5, 102.8, 108.4)]


def test_cisd_open_level_entry_and_adds():
    kw = dict(cisd_ob_entries=True, ob_entry="pre_break", min_risk_pts=0.5)
    eq = c_run(CISD_ROWS, **kw)
    assert len(eq) == 1 and eq[0].entry_kind == "cisd_ob" and eq[0].entry == pytest.approx(99.65)           # built: min(the EQ of the post-CISD range, the OB top)
    op = c_run(CISD_ROWS, cisd_ob_px="open", **kw)
    assert len(op) == 1 and op[0].entry_kind == "cisd_ob" and op[0].entry == pytest.approx(100.4)           # the open of the first candle of the down-close run
    assert op[0].entry_time.hour == 9 and op[0].entry_time.minute == 55 and op[0].stop == pytest.approx(98.35)
    # the CISD needs high >= open_ref + 1 tick: a high of 100.6 (< 100.65) arms nothing
    rows = CISD_ROWS[:4] + [(99.7, 100.6, 99.6, 100.4)] + CISD_ROWS[5:8] + [(99.8, 100.6, 99.7, 100.4)] + CISD_ROWS[9:]       # (no close over the OB body top either: no plain OB order)
    assert c_run(rows, cisd_ob_px="open", **kw) == []
    # adds: the later down-close run (100.4 -> 99.8) with its own CISD (the 100.7 high) gives a new open_ref (100.4) for an add
    add_kw = dict(adds=(0.5,), **kw)
    no_add = c_run(CISD_ROWS, cisd_ob_px="open", **add_kw)
    assert len(no_add) == 1 and no_add[0].adds == []
    ad = c_run(CISD_ROWS, cisd_ob_px="open", cisd_adds=True, **add_kw)
    assert len(ad) == 1 and len(ad[0].adds) == 1 and ad[0].adds[0][1] == pytest.approx(100.4)
    # unit: the runs
    sd = sd_of(CISD_ROWS)
    assert es1.cisd_runs(sd, 5, 9) == [(6, 7)]


# --- A13-breaker-fvg-refinement (14) ---------------------------------------------------------------------------------------------

def test_breaker_refine_picks_the_inner_fvg_or_vi():
    rows = [(100.0, 100.2, 99.0, 99.1), (99.1, 100.4, 99.0, 100.3), (100.3, 101.2, 100.3, 101.1), (101.1, 101.5, 100.6, 101.3), (101.3, 101.6, 101.0, 101.4)]
    sd = sd_of(rows)
    sw = dict(ext_i=0, ext=99.0)
    bz = L.Zone("bull", 101.0, 100.0, 4, 0, 100.5)
    p = Params(es_pt=1.0)
    assert (100.6, 100.4) in [(round(g.top, 2), round(g.bottom, 2)) for g in sd.gaps]
    assert es1.breaker_refine(sd, sw, bz, 4, p) == (pytest.approx(100.6), pytest.approx(100.4))          # the near edge of the FVG inside the breaker zone, cancelled under its low
    assert es1.breaker_refine(sd, sw, L.Zone("bull", 99.2, 99.0, 4, 0, 99.1), 4, p) is None            # no gap inside this zone
    assert es1.breaker_refine(sd, sw, bz, 2, p) == (pytest.approx(100.3), pytest.approx(100.2))              # (at bar 2 only the earlier gap exists - the one at bar 3 is not known yet)
    sd2 = sd_of(rows[:4] + [(101.3, 101.4, 100.2, 100.3)])                                                    # a close under the gap low kills it
    assert es1.breaker_refine(sd2, sw, bz, 4, p) == (pytest.approx(100.3), pytest.approx(100.2))                # (the 100.4-100.6 gap is closed through; the earlier one stays)


# --- E2-iofed-full-definition (23) ---------------------------------------------------------------------------------------------------

def test_iofed_strict_arm_gate_and_ce_stop():
    sd = sd_of(C_ROWS)
    g = [z for z in sd.gaps if z.i == 4][0]
    assert (round(g.bottom, 2), round(g.top, 2), round(g.mid, 2)) == (99.8, 100.4, 100.1)
    p = Params(entry="iofed", iofed_strict=True)
    assert es1.iofed_check(sd, g, 100.15, 4, p)                                                              # nothing traded yet since the gap formed
    assert not es1.iofed_check(sd, g, 100.05, 4, p)                                                          # a limit at / under the CE is no IOFED
    assert not es1.iofed_check(sd_of(C_ROWS[:5] + [(101.6, 101.7, 100.05, 100.5)]), g, 100.15, 5, p)        # the retrace already reached the CE
    kw = dict(entry="iofed")
    ok_rows = C_ROWS[:5] + [(101.6, 101.7, 100.12, 100.5)] + C_ROWS[6:]
    tr = c_run(ok_rows, iofed_strict=True, **kw)
    assert len(tr) == 1 and tr[0].entry == pytest.approx(100.15) and all(e[3] != "iofed_ce" for e in tr[0].exits)       # a 3-candle swing low (100.12) inside the gap, above the CE: kept
    bad = C_ROWS[:5] + [(101.6, 101.7, 100.05, 100.5)] + C_ROWS[6:]                                           # the fill bar itself traded to the CE
    tb = c_run(bad, iofed_strict=True, **kw)
    assert len(tb) == 1 and tb[0].exits[0][3] == "iofed_ce" and tb[0].exits[0][1] == pytest.approx(100.1)
    assert all(e[3] != "iofed_ce" for e in c_run(bad, **kw)[0].exits)                                         # the built entry keeps it
    # the CE is hit AFTER the fill, before a swing low confirmed: out at the CE
    later = C_ROWS[:5] + [(101.6, 101.7, 100.12, 100.6), (100.6, 100.7, 100.0, 100.2)] + C_ROWS[7:]
    tl = c_run(later, iofed_strict=True, **kw)
    assert len(tl) == 1 and tl[0].exits[0][3] == "iofed_ce" and tl[0].exits[0][1] == pytest.approx(100.1)


# --- A5-ob-in-vi-over-newer-fvg (26) -----------------------------------------------------------------------------------------------------

def test_add_prefers_the_ob_that_traded_into_a_vi():
    rows = [(100.0, 100.2, 99.9, 100.1), (99.6, 99.9, 99.5, 99.8), (100.2, 100.8, 99.7, 100.6), (100.9, 101.0, 100.1, 100.3), (100.3, 101.2, 100.2, 101.0)]
    sd = sd_of(rows)
    assert [(round(z.bottom, 2), round(z.top, 2)) for z in sd.vis("bull")] == [(99.8, 100.2)]
    pos = dict(fill_i=0)
    p = Params(es_pt=1.0)
    r = es1.ob_in_vi_add(sd, pos, 4, p)
    assert r[:2] == (pytest.approx(100.6), pytest.approx(99.8)) and r[2] == pytest.approx(100.3)                                                   # the MT of the down-close OB (100.9 -> 100.3) that traded into the VI; the VI bottom = the floor
    assert es1.ob_in_vi_add(sd, pos, 3, p) is None                                                            # the OB candle is bar 3: it needs a later bar to be judged
    rows2 = rows[:3] + [(100.9, 101.0, 99.7, 100.3)] + rows[4:]                                               # the OB pierced the VI bottom: not an add
    assert es1.ob_in_vi_add(sd_of(rows2), pos, 4, p) is None
    assert es1.ob_in_vi_add(sd, dict(fill_i=3), 4, p) is None                                                 # (the pullback begins after the fill)


# --- A5-mtf-gap-refinement (34) ---------------------------------------------------------------------------------------------------------

def test_refine_down_and_widen_up():
    # refine_down: an HTF zone (not a base-bar gap) is replaced by the LTF FVG of the same displacement inside it
    rows = [(100.0, 100.5, 99.5, 100.2), (100.2, 101.5, 100.1, 101.4), (101.4, 102.0, 100.9, 101.8), (101.8, 102.2, 101.5, 102.0), (102.0, 102.3, 101.2, 101.5)]
    sd = sd_of(rows)
    assert [(round(z.bottom, 2), round(z.top, 2), z.i) for z in sd.gaps] == [(100.5, 100.9, 2)]
    htf_z = L.Zone("bull", 101.2, 100.2, 4, 0)                                                                # a "15m" zone around the displacement (no mt: a FVG-type zone)
    ctx = SimpleNamespace(tf=5)
    sw = dict(ext=99.5, ext_i=0)
    b = es1.refine_down(ctx, sd, sw, htf_z, 4, Params(es_pt=1.0))
    assert b is sd.gaps[0]
    assert es1.refine_down(ctx, sd, dict(sw, ext=100.8), htf_z, 4, Params(es_pt=1.0)) is None                  # the LTF gap lies under the swept liquidity (ext 100.8 > its bottom)
    assert es1.refine_down(ctx, sd, sw, sd.gaps[0], 4, Params(es_pt=1.0)) is None                              # a base-bar gap is not refined
    # widen_up: the target FVG (5m) overlapping a 15m opposing FVG of the same move extends to the 15m far edge
    w_rows = [(110.0, 110.2, 109.6, 109.7), (109.7, 109.8, 109.0, 109.1), (109.1, 109.2, 108.5, 108.6), (108.6, 108.7, 106.0, 106.2), (106.2, 106.3, 104.0, 104.2),
              (104.2, 104.5, 103.0, 103.2), (103.2, 103.5, 102.0, 102.5), (102.5, 102.9, 101.5, 102.0), (102.0, 102.4, 101.0, 101.2)]
    ctx2, (sdw, _) = mkctx(w_rows, Params(**BASE), base=110.0)
    i8 = S._idx_at(ctx2, 570) + 8
    out = es1.widen_targets(ctx2, sdw, i8, 100.0, Params(**BASE))
    assert 108.5 in [round(v, 2) for v, _ in out] and all(k == "array" for _, k in out)                      # the 15m bearish FVG [103.5, 108.5]: its far edge (the flat pre-open bars add a second 15m gap)
    assert 108.5 not in [round(v, 2) for v, _ in es1.widen_targets(ctx2, sdw, i8, 106.5, Params(**BASE))]    # the 5m gap [104.5, 106.0] lies at / under the entry-side threshold


# --- A9-vi-retest-tolerance (39) --------------------------------------------------------------------------------------------------------

def test_vi_stop_level_modes():
    rows = [(99.0, 99.6, 98.6, 99.2), (99.6, 100.5, 98.8, 100.2)]                                                 # candle 0 body top 99.2; candle 1 body bottom 99.6: VI [99.2, 99.6]; lows 98.6 / 98.8
    sd = sd_of(rows)
    z = sd.vis("bull")[0]
    assert (round(z.bottom, 2), round(z.top, 2)) == (99.2, 99.6)
    assert es1.vi_stop_level(sd, z, Params(es_pt=1.0)) is None                                                    # built: the VI own bottom
    assert es1.vi_stop_level(sd, z, Params(es_pt=1.0, vi_tol="ce")) == pytest.approx(98.6)                         # the marked low of the two candles
    assert es1.vi_stop_level(sd, z, Params(es_pt=1.0, vi_tol="adjacent_extreme")) == pytest.approx(98.6)          # a small VI (0.4 <= 2 pts) may overshoot to the adjacent candle extreme
    assert es1.vi_stop_level(sd, z, Params(es_pt=1.0, vi_tol="adjacent_extreme", vi_tol_small_pts=0.2)) is None    # a larger one is strict
    assert es1.vi_stop_level(sd, z, Params(es_pt=1.0, vi_tol="ce", vi_tol_small_pts=0.2)) == pytest.approx(98.6)   # "ce": any size


# --- A16-propulsion-block-full (42), A16-propulsion-depth-grade (44) -------------------------------------------------------------------

PB_ROWS = [(101.0, 101.2, 100.0, 100.2), (100.2, 101.5, 100.1, 101.4), (101.4, 102.5, 101.3, 102.4), (102.4, 102.6, 101.1, 101.2), (101.2, 102.0, 101.1, 101.9)]


def test_prop_depth_and_wick_exit_and_flip():
    sw = dict(ext_i=0, ext=99.0)
    sd = sd_of(PB_ROWS)
    z, depth = es1.prop_depth(sd, sw, 103.0, 4)
    assert (round(z.bottom, 2), round(z.top, 2)) == (101.1, 102.6) and depth == pytest.approx((101.2 - 101.1) / (101.2 - 100.0))      # a clean block: 0.08 of the OB
    deep = [PB_ROWS[0], PB_ROWS[1], PB_ROWS[2], (102.4, 102.6, 100.4, 101.2), PB_ROWS[4]]
    z2, depth2 = es1.prop_depth(sd_of(deep), sw, 103.0, 4)
    assert depth2 == pytest.approx((101.2 - 100.4) / 1.2) and depth2 > 0.5                                  # deep: more prone to fail
    assert es1.prop_depth(sd, sw, 100.5, 4) is None                                                          # no block under the entry gap top
    # the order gate: a deep block halves the risk (prop_deep_mult 0.5), 0 skips
    tags = {"es1_prop_depth": depth2}
    lvt = []
    assert es1.order_gate_es1(None, None, None, 4, Params(prop_deep_mult=0.5), 0, 0, "AM", lvt, {}, tags) is None
    assert tags["es1_mult"] == 0.5 and "prop_deep" in lvt
    assert es1.order_gate_es1(None, None, None, 4, Params(prop_deep_mult=0.0), 0, 0, "AM", [], {}, {"es1_prop_depth": depth2}) == "x_prop_deep"
    t_ok = {"es1_prop_depth": depth}
    assert es1.order_gate_es1(None, None, None, 4, Params(prop_deep_mult=0.5), 0, 0, "AM", [], {}, t_ok) is None and "es1_mult" not in t_ok
    # the wick test: any trade through the PB MT exits at that level (the close variant would not)
    sdl = sd_of([(100.0, 101.0, 99.0, 100.5)] * 3 + [(100.5, 101.0, 98.9, 100.6)])
    pos = dict(left=10, fill_i=1, es1=dict(prop_wick=99.0), basis=1000.0, n=10)
    tr = SimpleNamespace(exits=[], lv_tags="")
    es1.manage(None, sdl, pos, tr, 2, "t2", Params(es_pt=1.0))
    assert pos["left"] == 10 and tr.exits == []                                                              # a low of 99.0 is not a trade THROUGH 99.0
    es1.manage(None, sdl, pos, tr, 3, "t3", Params(es_pt=1.0))
    assert pos["left"] == 0 and tr.exits == [("t3", 99.0, 10, "prop_wick")]
    # prop_fail_flip: the long failed on the block - the session slot re-opens for shorts only
    done, state = {"AM": True}, {}
    trd = SimpleNamespace(exits=[("t", 99.0, 10, "prop_wick")], side="long", session="AM")
    es1.after_close(None, None, trd, done, "AM", state, Params(prop_fail_flip=True))
    assert done["AM"] is False and state["only_side"]["AM"] == -1
    # (review fix) an only_side already set the other way (a flipped leg) is overridden, and the failed block is kept as the flipped side's array
    d3, s3 = {"AM": True}, {"only_side": {"AM": 1}}
    es1.after_close(None, dict(fill_i=3, es1=dict(prop_zone=(98.0, 99.5))), trd, d3, "AM", s3, Params(prop_fail_flip=True))
    assert d3["AM"] is False and s3["only_side"]["AM"] == -1 and s3["pb_flip"]["AM"] == dict(sign=-1, lo=98.0, hi=99.5, i=3)
    d2, s2 = {"AM": True}, {}
    es1.after_close(None, None, trd, d2, "AM", s2, Params())
    assert d2["AM"] is True and not s2


# --- A15-mitigation-definition-and-iofed (45) ------------------------------------------------------------------------------------------

def test_mitigation_context_for_the_iofed_edge():
    g = L.Zone("bull", 100.4, 99.8, 4, 3)
    sw = dict(ext_i=1)
    mk = lambda z: SimpleNamespace(mitigations=lambda: [z])
    assert es1.mit_context(mk(L.Zone("bull", 101.5, 100.8, 4, 2)), sw, g, 4)                                  # a mitigation block above the FVG, known since the sweep
    assert es1.mit_context(mk(L.Zone("bull", 100.6, 100.0, 4, 2)), sw, g, 4)                                  # one that overlaps it
    assert not es1.mit_context(mk(L.Zone("bull", 99.5, 99.0, 4, 2)), sw, g, 4)                                # below the gap: not the arming context
    assert not es1.mit_context(mk(L.Zone("bull", 101.5, 100.8, 0, 0)), sw, g, 4)                              # formed before the sweep
    assert not es1.mit_context(mk(L.Zone("bull", 101.5, 100.8, 6, 5)), sw, g, 4)                              # not known yet at bar 4


# --- A23-broken-wick-ce-inversion (59) ---------------------------------------------------------------------------------------------------

def test_broken_wick_ce_candidate():
    rows = [(99.0, 99.2, 98.0, 98.3), (98.3, 101.0, 98.2, 100.2), (100.2, 100.8, 99.0, 99.3)]                  # bar 1 = the broken swing high: body top 100.2, high 101.0
    sd = sd_of(rows)
    sw = dict(ref_i=1, ext=98.0)
    p = Params(es_pt=1.0)
    c = es1.broken_wick_cand(sd, sw, 2, p)
    assert c == (pytest.approx(100.6), pytest.approx(100.2), "broken_wick_ce") and sw["_bwc_edge"] == pytest.approx(100.2)          # CE = (max(o, c) + high) / 2; the stop under the body edge
    assert es1.broken_wick_cand(sd, dict(sw), 2, replace(p, broken_wick_stop="swing"))[1] == 98.0
    assert es1.broken_wick_cand(sd_of([(99.0, 99.2, 98.0, 98.3), (98.3, 100.2, 98.2, 100.2)]), dict(ref_i=1, ext=98.0), 1, p) is None   # no upper wick: no CE


# --- A5-far-edge-reach-conditions (76) ------------------------------------------------------------------------------------------------------

def _fe(rows, **kw):
    sd = sd_of(rows)
    g = L.Zone("bull", 102.0, 100.0, 0, 0)
    return es1.far_edge(SimpleNamespace(tf=5), sd, g, 102.0, 100.0, len(rows) - 1, Params(es_pt=1.0, **kw))


def test_far_edge_reach_cases():
    zig = [(101.9, 102.0, 101.4, 101.5), (101.5, 101.6, 101.0, 101.2), (101.2, 102.0, 101.1, 101.8), (101.8, 101.9, 101.0, 101.3), (101.3, 102.0, 101.2, 101.9), (101.9, 101.95, 101.4, 101.5)]
    # (1) layering: >= 3 back-and-forth swings near the near edge, plus a small nested LTF FVG
    entry, tags = _fe(zig + [(101.4, 101.45, 101.3, 101.4), (101.4, 101.6, 101.5, 101.55), (101.6, 101.9, 101.6, 101.8)])
    assert "far_edge_protected" in tags and "far_edge_layered" in tags and entry is not None          # the CE of the most recent nested gap
    # (2) an inner BPR: the band was crossed one pass each way, no layering
    cross = [(101.5, 101.6, 100.9, 101.0), (101.0, 101.1, 99.8, 99.9), (99.9, 102.1, 99.8, 102.0), (102.0, 102.2, 101.9, 102.1)]
    e2, t2 = _fe(cross)
    assert t2 == ["far_edge_protected"] and e2 is None
    # (3) a residual untraded sub-gap at the far edge
    sub = [(100.2, 100.3, 100.0, 100.1), (100.1, 100.9, 100.1, 100.8), (100.8, 101.0, 100.5, 100.9), (100.9, 101.5, 100.9, 101.4), (101.4, 101.6, 101.3, 101.5)]
    e3, t3 = _fe(sub)
    assert "far_edge_subgap" in t3 and e3 is None
    # (4) none: the nested LTF FVG near edge
    e4, t4 = _fe([(101.9, 102.0, 101.8, 101.9), (101.9, 101.9, 101.3, 101.4), (101.4, 101.45, 101.3, 101.4), (101.5, 101.8, 101.45, 101.7), (101.7, 101.9, 101.6, 101.8)])
    assert t4 == ["far_edge_nested"] and e4 == pytest.approx(101.6)


# --- A5-partial-reprice-shrink (77) -------------------------------------------------------------------------------------------------------

def test_remaining_top_after_a_wick_into_the_gap():
    sd = sd_of(C_ROWS[:5] + [(101.6, 101.7, 100.1, 100.5)] + C_ROWS[6:7])                                      # a wick 0.3 into the gap [99.8, 100.4] from above
    g = [z for z in sd.gaps if z.i == 4][0]
    p = Params(es_pt=1.0, tick_pts=0.25)
    assert es1.remaining_top(sd, g, g.top, g.bottom, 5, p) == pytest.approx(100.1)
    assert es1.remaining_top(sd, g, g.top, g.bottom, 4, p) == pytest.approx(g.top)                              # nothing traded into it yet
    deep = sd_of(C_ROWS[:5] + [(101.6, 101.7, 99.85, 100.5)])
    assert es1.remaining_top(deep, g, g.top, g.bottom, 5, p) == pytest.approx(g.top)                            # (a wick to within a tick of the bottom: left alone)


# --- A12-ob-edge-at-fvg-ce (78), new-multi-tf-scan (92) -------------------------------------------------------------------------

M15_ROWS = [(101.0, 101.2, 100.6, 100.8), (100.8, 101.0, 100.3, 100.5), (100.5, 100.7, 100.0, 100.2),                       # 15m A: a down candle (the OB), high 101.2
            (100.2, 101.5, 100.2, 101.4), (101.4, 102.5, 101.3, 102.4), (102.4, 102.8, 102.3, 102.7),                       # 15m B: the displacement
            (102.7, 103.0, 102.0, 102.8), (102.8, 103.2, 102.1, 103.0), (103.0, 103.5, 102.2, 103.4)]                      # 15m C: low 102.0 > A high 101.2 -> a 15m FVG [101.2, 102.0]


def test_ob_ce_confluence_and_scan_tfs():
    ctx, (sd, _) = mkctx(M15_ROWS, Params(**BASE), base=101.0)
    i8 = S._idx_at(ctx, 570) + 8
    sw = dict(ext_i=S._idx_at(ctx, 570), ext=100.0)
    z15 = [z for z in sd.zones_tf(ctx.idx, 5, 15) if z.mt == z.mt]
    assert (101.2, 100.0) in [(round(z.top, 2), round(z.bottom, 2)) for z in z15]                                             # the 15m OB: the high-to-low of the down candle
    g = L.Zone("bull", 101.4, 100.6, i8, i8 - 1)
    p = Params(**BASE, ob_ce_confluence=True)                                                                         # CE of g = 101.0; the 15m OB high 101.2 is 0.2 away (tol 1.0)
    assert es1.ob_ce_entry(ctx, sd, sw, g, 101.4, 100.6, i8, p) == pytest.approx(101.2)
    assert es1.ob_ce_entry(ctx, sd, sw, g, 101.4, 100.6, i8, replace(p, ob_ce_tol_pts=0.1)) is None
    assert es1.ob_ce_entry(ctx, sd, sw, g, 101.4, 100.6, i8 - 3, p) is None                                           # the 15m candle C is not complete yet
    assert es1.ob_ce_entry(ctx, sd, sw, L.Zone("bull", 101.9, 101.1, i8, i8 - 1), 101.9, 101.1, i8, replace(p, ob_ce_tol_pts=0.25)) is None   # the CE (101.5) is too far from the OB high
    assert es1.ob_ce_entry(SimpleNamespace(tf=15), sd, sw, g, 101.4, 100.6, i8, p) is None                            # the parent bars must be coarser than the base bars
    # new-multi-tf-scan: the 15m FVG joins the entry gaps (formed after the sweep, complete, not closed through); 1m..5m smaller than the base bars are skipped
    sw2 = dict(ext_i=S._idx_at(ctx, 570) - 1, ext=100.0)
    zs = es1.scan_gaps(ctx, sd, sw2, i8, Params(**BASE, scan_tfs=(1, 2, 3, 5, 15)))
    assert [(round(z.bottom, 2), round(z.top, 2)) for z in zs] == [(101.2, 102.0)] and sw2["_scan_tf"][id(zs[0])] == 15
    assert es1.scan_gaps(ctx, sd, sw2, i8, Params(**BASE)) == []                                                        # scan_tfs (1,): the base bars only
    assert es1.scan_gaps(ctx, sd, dict(sw2, ext_i=S._idx_at(ctx, 570) + 4), i8, Params(**BASE, scan_tfs=(15,))) == []   # formed before the sweep extreme: not an entry gap


# --- A8-htf-gap-resistance-grade (84) ----------------------------------------------------------------------------------------------

def test_htf_gap_reaction_depth_tiers_and_multiplier():
    conf = StubConf(arrays={1: [(104.0, 100.0, "1h", 0, 0.0)], -1: [(-100.0, -104.0, "1h", 0, 0.0)]})
    ctx, (sd, sd_s) = mkctx([(101.0, 101.2, 100.6, 100.8)] * 3, Params(**BASE), conf=conf)
    k0 = S._idx_at(ctx, 570)
    tier = lambda ext, sd_=sd: es1.htf_depth_tier(ctx, sd_, dict(ext=ext, ext_i=k0), k0 + 2, Params(**BASE))
    assert tier(103.5) == "near" and tier(101.9) == "ce" and tier(100.2) == "far" and tier(106.0) is None          # the reaction at the near edge, at the CE, down to the far edge, no gap there
    assert es1.htf_depth_tier(SimpleNamespace(conf=None), sd, dict(ext=1, ext_i=0), 2, Params(**BASE)) is None
    # a short: the same gap seen in the mirrored side space (the far edge is the real top)
    ctx2, (sd_l, sd_s2) = mkctx([(101.0, 101.2, 100.6, 100.8)] * 3, Params(**BASE), conf=StubConf(arrays={-1: [(104.0, 100.0, "1h", 0, 0.0)]}))
    assert es1.htf_depth_tier(ctx2, sd_s2, dict(ext=-103.9, ext_i=k0), k0 + 2, Params(**BASE)) == "far"
    assert es1.htf_depth_tier(ctx2, sd_s2, dict(ext=-100.1, ext_i=k0), k0 + 2, Params(**BASE)) == "near"
    # the gate: (1, 1, 0.5) halves the risk of a far-edge entry only
    tags, lvt = {}, []
    sw = dict(ext=100.2, ext_i=k0)
    assert es1.order_gate_es1(ctx, sd, sw, k0 + 2, Params(**BASE, htf_depth_mult=(1.0, 1.0, 0.5)), 0, 0, "AM", lvt, {}, tags) is None
    assert tags["es1_mult"] == 0.5 and "htf_depth_far" in lvt
    t2, l2 = {}, []
    es1.order_gate_es1(ctx, sd, dict(ext=103.5, ext_i=k0), k0 + 2, Params(**BASE, htf_depth_mult=(1.0, 1.0, 0.5)), 0, 0, "AM", l2, {}, t2)
    assert "es1_mult" not in t2 and l2 == ["htf_depth_near"]
    assert not es1.any_gate_es1(Params()) and es1.any_gate_es1(Params(htf_depth_mult=(1, 1, 0.5)))


# --- A12-ob-open-anchor-ltf-wick (88), A12-ob-anchor-level (89) -----------------------------------------------------------------------

def test_htf_ob_anchor_and_the_ltf_wick_entry():
    rows = [(100.0, 100.1, 99.5, 99.8), (99.8, 101.0, 99.7, 100.9), (100.9, 101.85, 100.8, 101.8), (101.8, 102.4, 101.8, 102.3), (102.3, 102.5, 101.95, 102.4)]
    sd = sd_of(rows)
    assert [(round(g.bottom, 2), round(g.top, 2)) for g in sd.gaps if g.i == 4] == [(101.85, 101.95)]
    g = L.Zone("bull", 102.0, 100.0, 4, 0, 101.0, levels=(101.8,))                                                   # an HTF OB: range 100 .. 102, open 101.8 (a stubby upper wick: 0.2 < 25 % of 2.0)
    sw = dict(ext_i=0, ext=99.5)
    p = Params(es_pt=1.0, ob_wick_ltf_entry=True)
    assert es1.wick_ltf_entry(None, sd, g, sw, 4, p) == (pytest.approx(101.95), pytest.approx(101.85))             # the LTF FVG inside [open, high]
    assert es1.wick_ltf_entry(None, sd, L.Zone("bull", 102.0, 100.0, 4, 0, 101.0, levels=(100.5,)), sw, 4, p) is None   # a long wick: not stubby
    assert es1.wick_ltf_entry(None, sd, L.Zone("bull", 102.0, 100.0, 4, 0), sw, 4, p) is None                       # not an OB zone (no mt / open)
    assert es1.wick_ltf_entry(None, sd, g, sw, 3, p) is None                                                           # the FVG is not complete at bar 3
    # htf_ob_anchor: an HTF OB enters at its open under "open" (the A12 2023 default) and at its candle extreme under "extreme"
    assert es1.htf_open_top(g, Params(htf_ob_anchor="open")) == pytest.approx(101.8) and es1.htf_open_top(g, Params()) == pytest.approx(102.0)
    assert es1.htf_open_top(L.Zone("bull", 102.0, 100.0, 4, 0), Params(htf_ob_anchor="open")) == 102.0                                  # a plain FVG zone: its top
    # the Confluence target level of an HTF OB: the open, or the extreme of the candle
    from mentorship import confluence as CF
    cf = CF.Confluence.__new__(CF.Confluence)
    cf.z = {"4h": dict(kind=np.array([-1.0, -1.0]), top=np.array([110.0, 120.0]), bottom=np.array([106.0, 116.0]), known=np.array([0.0, 0.0]), dead=np.array([np.inf, np.inf]),
                       src=np.array([1.0, 0.0]), open=np.array([107.5, np.nan]), life=np.full(2, 1e30))}
    cf.window, cf.first20, cf.dends, cf.tol = None, False, np.array([]), 0.25
    now = pd.Timestamp("2026-06-23 10:00", tz=NY)
    cf.ob_anchor = "extreme"
    assert sorted(cf.targets(now, 100.0, 1, ("4h",))) == sorted([106.0, 108.0, 116.0, 118.0])                 # built: the near edge (the candle extreme) and the CE of each array
    cf.ob_anchor = "open"
    assert sorted(cf.targets(now, 100.0, 1, ("4h",))) == sorted([107.5, 108.0, 116.0, 118.0])                   # the OB near edge is its open; the FVG row (nan open) keeps its near edge
    # the zones carry the HTF open: zones_tf (15m)
    ctx, (sd5, _) = mkctx(M15_ROWS, Params(**BASE), base=101.0)
    z15 = [z for z in sd5.zones_tf(ctx.idx, 5, 15) if z.mt == z.mt]
    assert z15 and z15[0].levels == (pytest.approx(101.0),)                                                          # the open of the 15m down candle


# --- new-2m-fvg-ce (97) --------------------------------------------------------------------------------------------------------

M1_ROWS = [(100.0, 100.2, 99.8, 100.1), (100.1, 100.3, 100.0, 100.2), (100.2, 100.9, 100.2, 100.8), (100.8, 101.4, 100.7, 101.3), (101.3, 101.6, 101.0, 101.5), (101.5, 101.8, 101.2, 101.7)]


def _m1(rows):
    ctx = stub(len(rows))
    ctx.idx = pd.date_range("2026-06-23 09:30", periods=len(rows), freq="1min", tz=NY)
    ctx.tf, ctx.start = 1, 0
    ctx.t = (ctx.idx.hour * 60 + ctx.idx.minute).values
    return ctx, sd_of(rows)


def test_two_minute_fvg_ce():
    ctx, sd = _m1(M1_ROWS)
    g = [z for z in sd.gaps if z.i == 3][0]
    assert (round(g.bottom, 2), round(g.top, 2), g.src) == (100.3, 100.7, 2)                                         # the 1m FVG, CE 100.5
    p = Params(es_pt=1.0, two_min_ce=True)
    assert es1.two_min_ce(ctx, sd, g, 5, p) == pytest.approx(100.65)                                                  # the 2m FVG [100.3, 101.0] holding the same displacement: CE 100.65
    assert es1.two_min_ce(ctx, sd, g, 4, p) is None                                                                   # the third 2m candle (09:34-09:35) is not complete at 09:34
    down = [M1_ROWS[0], (100.2, 100.3, 100.0, 100.1), M1_ROWS[2], (100.8, 101.4, 100.7, 100.75)] + M1_ROWS[4:]          # both neighbours of the middle candle close down: not two same-direction candles
    sd2 = sd_of(down)
    g2 = [z for z in sd2.gaps if z.src == 2]
    assert not g2 or es1.two_min_ce(ctx, sd2, g2[0], 5, p) is None
    one_nb = M1_ROWS[:3] + [(100.8, 101.4, 100.7, 100.75)] + M1_ROWS[4:]                                              # one neighbour (the earlier candle) is also up-close: that is two consecutive candles
    sd3 = sd_of(one_nb)
    g3 = [z for z in sd3.gaps if z.src == 2]
    assert not g3 or es1.two_min_ce(ctx, sd3, g3[0], 5, p) is not None
    assert es1.two_min_ce(SimpleNamespace(tf=5), sd, g, 5, p) is None                                                 # 1m base bars only


# --- A5-skip-fvg-near-stop-pool (100), A5-multitf-hold-test (102) ----------------------------------------------------------------------

def test_skip_fvg_near_an_untaken_short_term_extreme():
    rows = [(99.0, 99.2, 98.0, 98.5), (98.5, 100.0, 98.4, 99.8), (99.8, 100.6, 99.9, 100.4), (100.4, 100.9, 99.5, 100.8), (100.8, 101.5, 100.6, 101.4), (101.4, 101.6, 100.9, 101.2)]
    sd = sd_of(rows)
    sw = dict(ext_i=0, ext=98.0)
    g = L.Zone("bull", 101.0, 100.3, 5, 4)
    p = Params(es_pt=1.0, fvg_pool_gap_pts=1.0)
    assert [(q.i, q.price) for q in sd.pl if q.i > 0] == [(3, 99.5)]
    assert es1.near_stop_pool(sd, sw, g, 5, p)                                                                         # the swing low 99.5 is 0.8 under the gap, above the protective low 98.0
    assert not es1.near_stop_pool(sd, sw, L.Zone("bull", 101.5, 100.8, 5, 4), 5, p)                                    # 1.3 away: not too close
    assert not es1.near_stop_pool(sd, dict(sw, ext=99.6), g, 5, p)                                                    # a pool under the protective low is no concern
    taken = sd_of(rows + [(101.2, 101.3, 99.0, 99.2)])
    assert not es1.near_stop_pool(taken, sw, g, 6, p)                                                                  # taken since: gone
    assert not es1.near_stop_pool(sd, sw, g, 3, p)                                                                     # not confirmed at bar 3 (known at 4)
    # a short: the mirrored book gives the same answer
    sdm = sd_of([(-r[0], -r[2], -r[1], -r[3]) for r in rows], sign=-1)
    assert es1.near_stop_pool(sdm, sw, g, 5, p) and (sdm.o == sd.o).all()                                             # the same side-space book: the same answer


def test_mtf_hold_counts_closes_inside_on_the_1_to_4m_charts():
    rows = [(100.0, 100.2, 99.8, 100.0)] * 2 + [(102.5, 102.9, 102.3, 102.6), (102.6, 102.7, 101.2, 102.5), (102.5, 102.6, 101.1, 102.5), (102.5, 102.8, 101.0, 102.6),
                                                (102.6, 102.7, 101.2, 102.4), (102.4, 102.6, 101.3, 102.5)]
    ctx, sd = _m1(rows)
    g = L.Zone("bull", 102.0, 101.0, 1, 0)                                                                            # a 5m gap (not a base-bar gap), formed at bar 1
    p = Params(es_pt=1.0, mtf_hold=True)
    assert es1.mtf_closes_inside(ctx, sd, g, 7, p) == 0 and es1.mtf_hold_ok(ctx, sd, g, 7, p)                          # wicks entering the gap, bodies staying above its high: holding
    rows2 = rows[:4] + [(102.5, 102.6, 101.1, 101.5), (101.5, 101.6, 101.1, 101.6)] + rows[6:]                          # two closes inside the gap
    ctx2, sd2 = _m1(rows2)
    assert es1.mtf_closes_inside(ctx2, sd2, g, 7, p) == 2 and not es1.mtf_hold_ok(ctx2, sd2, g, 7, p)
    rows3 = rows[:4] + [(102.5, 102.6, 101.1, 101.5)] + rows[5:]                                                       # one close inside: still a hold
    ctx3, sd3 = _m1(rows3)
    assert es1.mtf_closes_inside(ctx3, sd3, g, 7, p) == 1 and es1.mtf_hold_ok(ctx3, sd3, g, 7, p)
    base_gap = L.Zone("bull", 102.0, 101.0, 1, 0)
    sd3.gaps.append(base_gap)
    assert es1.mtf_hold_ok(ctx2, sd3, base_gap, 7, p)                                                                  # a base-bar gap is not judged here
    assert es1.mtf_hold_ok(SimpleNamespace(tf=5), sd2, g, 7, p)                                                        # judged on the 1-4m charts only


# --- NEW-no-return-to-origin-ob (118) ----------------------------------------------------------------------------------------------

def _hist_days(ohlc, d=D0):
    from test_levels_detectors import prior_days, rth_day
    return [rth_day(x, h_, l_, close=c_) for x, (h_, l_, c_) in zip(prior_days(d, len(ohlc)), ohlc)]


ORIGIN = [(4060, 4020, 4040), (4050, 4000, 4010), (4040, 4015, 4030), (4045, 4001.5, 4040), (4070, 4035, 4065), (4055, 4040, 4050), (4090, 4045, 4085), (4095, 4070, 4090)]


def test_no_return_to_origin():
    ctx = stub(5)
    ctx.hist, ctx.no_origin = _hist_days(ORIGIN), 2.0
    sd = SimpleNamespace(sign=1, x=lambda v: v)
    info = es1.origin_info(ctx, sd)
    assert info == dict(L0=4000.0, H=4095.0)                                                                           # the low tested twice (4000, 4001.5), a pivot high 4070 and a later daily close above it
    arrs = [(4003.0, 3997.0, 0), (4012.0, 4008.0, 0), (4033.0, 4027.0, 0), (4060.0, 4056.0, 0)]
    keep = es1.drop_origin(ctx, sd, 5, arrs)
    assert keep == [(4033.0, 4027.0, 0), (4060.0, 4056.0, 0)]                                                          # the origin OB goes; the deeper array too (a 25-50 % array exists); the shallower one stays
    assert es1.drop_origin(ctx, sd, 5, [(4003.0, 3997.0, 0), (4012.0, 4008.0, 0)]) == [(4012.0, 4008.0, 0)]            # without a 25-50 % array only the origin array goes
    assert es1.is_origin(ctx, sd, 5, 4000.5) and es1.is_origin(ctx, sd, 5, 3990.0) and not es1.is_origin(ctx, sd, 5, 4030.0)
    # no confirmed reversal: a single test of the low, or no later close above the pivot high
    c1 = stub(5)
    c1.hist, c1.no_origin = _hist_days(ORIGIN[:3] + [(4045, 4015, 4040)] + ORIGIN[4:]), 2.0
    assert es1.origin_info(c1, sd) is None
    c2 = stub(5)
    c2.hist, c2.no_origin = _hist_days(ORIGIN[:6] + [(4069, 4045, 4066), (4069, 4070, 4065)]), 2.0
    assert es1.origin_info(c2, sd) is None
    c3 = stub(5)
    c3.hist = _hist_days(ORIGIN)
    assert es1.origin_info(c3, sd) is None and es1.drop_origin(c3, sd, 5, arrs) == arrs                                # (no_origin unset: the switch is off)
    # a short: the same structure mirrored (a high tested twice) - prices shifted by -8000 in side space
    sdm = SimpleNamespace(sign=-1, x=lambda v: -v)
    cm = stub(5)
    cm.hist, cm.no_origin = _hist_days([(8000 - l_, 8000 - h_, 8000 - c_) for h_, l_, c_ in ORIGIN]), 2.0
    im = es1.origin_info(cm, sdm)
    assert im == dict(L0=4000.0 - 8000.0, H=4095.0 - 8000.0)
    # through strategy._ts_arrays: the HTF array holding the origin is gone
    cx = stub(5)
    cx.hist, cx.no_origin = _hist_days(ORIGIN), 2.0
    cx.conf = StubConf(arrays={1: [(4003.0, 3997.0, "D", 1, 0.0), (4033.0, 4027.0, "D", 0, 0.0)]})
    out = S._ts_arrays(cx, sd, 3, pd.Timestamp("2026-06-23 09:30", tz=NY))
    assert [(a, b) for a, b, _ in out] == [(4033.0, 4027.0)]
    cx.no_origin = None
    assert len(S._ts_arrays(cx, sd, 3, pd.Timestamp("2026-06-23 09:30", tz=NY))) == 2


# --- A12-ob-reached-body (141) ----------------------------------------------------------------------------------------------------

def test_ob_reach_body_in_the_htf_table():
    from test_caption_gap_ld2 import daily_df
    ohlc = [(106, 107, 105, 106), (105, 105.5, 101.5, 102), (102, 110, 101.8, 109), (109, 112, 106, 111), (111, 113, 107, 112), (112, 112.5, 101.0, 111), (111, 112, 110, 111.5), (111.5, 113, 111, 112),
            (112, 113.5, 111.5, 113), (113, 114, 112, 113.5)]
    df = daily_df(ohlc)
    wick = htf.table(df, 1.0)
    body = htf.table(df, 1.0, ob_reach="body")
    assert list(wick.index) == list(body.index)
    d = wick.react_score - body.react_score
    hit_days = [x for x in d.index if abs(d[x]) > 1e-9]
    assert [str(x)[:10] for x in hit_days] == ["2026-03-10", "2026-03-11"] and all(d[x] == 1.0 for x in hit_days)   # the two sessions after the wick-only pierce (react_days = 2): the OB counts on a wick, not on bodies
    pd.testing.assert_frame_equal(wick, htf.table(df, 1.0, ob_reach="wick"))                                           # "wick" is the built table
