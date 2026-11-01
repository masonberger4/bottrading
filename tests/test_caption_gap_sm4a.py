"""Caption-gap pass, package setups_models #4/7, part A: the 36 specs of digests/rulebook_gaps/models_setups_entries.md (items 11-17, 19-23, 26, 28, 31-37, 39, 40, 43, 47-50, 53-56, 58-60, 62).
Unit tests of the detectors / gates (sm4.py) and of the engine glue (strategy / setups / sm2 / sb_model hooks), small run_day scenarios, Params plumbing. Tests that need local market data (ES)
skip cleanly when it is absent; no platform-specific paths. The study variants and the no-look-ahead runs live in test_caption_gap_sm4b.py."""
from dataclasses import replace
from datetime import date
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from mentorship import backtest as B, levels as L, setups as SM, sm2, sm3, sm4, strategy as S
from mentorship.study import OA1029_OLD
from mentorship.strategy import Params
from dataclasses import dataclass as _oa_dc


@_oa_dc
class Params(Params):   # OA1029 Q92: these tests exercise other rules; the order-block narrative gate (default on) leaves them no trades
    ob_need_narrative: bool = False
    sick_count_at: int = 570                # coverage gap 3c: the pre-build sick sister (the 09:30 count, the built reference set, any day)
    sick_refs: str = "built"
    sick_consol_only: bool = False

from test_levels_detectors import BASE, D0, NY, day, ctx_for, frame, history, prior_days, rth_day
from test_caption_gap_sm1a import StubConf, hist_close, ib, mkctx, sd_of, stub

A = np.array

NEW_SWITCHES = (
    "dagger_entry", "dagger_level", "stab_tfs", "po3_ideal", "po3_resting", "po3_rest_off_pts", "po3_rest_mgmt", "lh_old_low_entry", "lh_add2_mult", "lh_old_low_stop_pts", "pm_old_high_fvg",
    "pm_old_high_bars", "pm_rev_partial", "pm_rev_first_only", "pm_after_draw", "pm_after_room_pts", "sb_counter_after_draw", "leg_tfs", "m2_live_eq", "m2_anchor", "implied_range_gate",
    "pm_am_stops", "lh_array_short", "nwog_fill_long", "nwog_fill_tol_pts", "wick_ce_mode", "wick_ce_pad_pts", "wick_ce_tf", "wick_ce_need_pool", "entry_pick", "nwog_edge_ce",
    "org_fill_reverse", "ob_at_key", "ob_key_ticks", "breaker_low_invalidate", "breaker_block_counter", "sick_entry", "sick_units", "lunch_nwog_long", "ifvg_symmetry_skip", "ifvg_sym_bars",
    "ifvg_tf", "htf_fvg_top_short", "ndog_scalp", "asia_session", "smt_trend_ignore", "three_drives_htf", "complete_model", "lh_org_fill",
    "lh_array_target", "lh_array_sd_k", "lh_array_iofed", "lh_array_need_draw", "lunch_nwog_entry", "wick_ce_precursor",
)


@pytest.fixture
def cap(monkeypatch):
    """Replace the engine's order tail with a recorder: the setup's entry / stop / fixed targets / tags / synthetic sweep are what the tests judge."""
    got = {}

    def fake(ctx_, sd_, i_, p_, sess_, sw_, entry, stop, rm, lh, tags, **k):
        got.update(entry=entry, stop=stop, fixed=k.get("fixed"), tags=tags, sw=sw_, session=sess_, lh=lh)
        return dict(entry=entry, stop=stop, tags=tags, shares=7, plan_shares=7)
    monkeypatch.setattr(S, "_finish_order", fake)
    return got


def test_new_switch_defaults_and_validation():
    p = Params(**OA1029_OLD)                 # the built values; the OA1029 defaults are checked in test_owner_answers_oa1029.py
    assert (p.dagger_entry, p.dagger_level, p.stab_tfs, p.po3_ideal, p.po3_resting, p.po3_rest_off_pts, p.po3_rest_mgmt) == (False, "ce", (15, 60), "off", False, 0.25, "none")
    assert (p.lh_old_low_entry, p.lh_add2_mult, p.lh_old_low_stop_pts, p.pm_old_high_fvg, p.pm_old_high_bars, p.pm_rev_partial, p.pm_rev_first_only) == (False, 1.0, 3.0, False, 6, False, True)
    assert (p.pm_after_draw, p.pm_after_room_pts, p.sb_counter_after_draw, p.leg_tfs, p.m2_live_eq, p.m2_anchor, p.implied_range_gate, p.pm_am_stops) == \
        (False, 10.0, False, (), False, "leg", False, False)
    assert (p.lh_array_short, p.nwog_fill_long, p.nwog_fill_tol_pts, p.wick_ce_mode, p.wick_ce_pad_pts, p.wick_ce_tf, p.wick_ce_need_pool, p.entry_pick) == \
        (False, False, 2.0, "close", 1.0, 0, True, "first")
    assert (p.nwog_edge_ce, p.org_fill_reverse, p.ob_at_key, p.ob_key_ticks, p.breaker_low_invalidate, p.breaker_block_counter, p.sick_entry, p.sick_units) == \
        (False, False, "off", 2, False, False, "discount", 1)
    assert (p.lunch_nwog_long, p.ifvg_symmetry_skip, p.ifvg_sym_bars, p.ifvg_tf, p.htf_fvg_top_short, p.ndog_scalp, p.asia_session, p.smt_trend_ignore) == \
        (False, False, 30, 0, False, False, False, False)
    assert (p.three_drives_htf, p.complete_model, p.lh_org_fill, p.turtle_soup, p.smt_pick) == (False, "off", False, "", "first")
    for kw in (dict(dagger_level="x"), dict(po3_ideal="x"), dict(m2_anchor="x"), dict(wick_ce_mode="x"), dict(entry_pick="x"), dict(ob_at_key="x"), dict(sick_entry="x"), dict(complete_model="x"),
               dict(po3_rest_off_pts=-1), dict(lh_add2_mult=0), dict(lh_old_low_stop_pts=0), dict(pm_old_high_bars=0), dict(wick_ce_tf=7), dict(ifvg_tf=3), dict(leg_tfs=(1,)), dict(stab_tfs=()),
               dict(stab_tfs=(7,)), dict(sick_units=0), dict(ifvg_sym_bars=0), dict(turtle_soup="x"), dict(smt_pick="x"), dict(entry_arrays=("nope",))):
        with pytest.raises(ValueError):
            Params(**kw)
    assert Params(turtle_soup="htf_stab").turtle_soup == "htf_stab" and Params(smt_pick="clean").smt_pick == "clean" and Params(entry_arrays=("ob_post",)).entry_arrays == ("ob_post",)
    assert Params(ndog_scalp=True).asia_session is True                      # the scalp needs the evening window
    assert set(NEW_SWITCHES) <= set(Params.__dataclass_fields__)


# --- 11 new-falling-dagger-upper-half-buy -----------------------------------------------------------------------------------------------------------

DAG_ROWS = [(4020.0, 4021.0, 4012.0, 4013.0), (4013.0, 4014.0, 4009.0, 4010.0), (4010.0, 4011.0, 4007.5, 4008.0)]
DAILY_FVG = {1: [(4010.0, 4000.0, "D", 0, 0)]}


def test_dagger_limit_at_daily_ce(cap):
    """012 ~00:20:06: bias +1, a bullish daily FVG 4000-4010 (CE 4005), price falling into its upper half (close 4008): a buy limit at the CE, the stop under it (floored at min_risk_pts), the
    order cancelled by a trade under the CE; once per FVG; no bias / a close under the CE / a filled lower-half hourly FVG = nothing; `ltf` takes the highest 15m FVG low above the CE."""
    p = Params(**BASE, dagger_entry=True, dagger_level="ce")                     # the CE limit (OA1029 Q47: "ltf" is the default; tested below)
    ctx, (sl, ss) = mkctx(DAG_ROWS, base=4020.0, bias=1, conf=StubConf(arrays=DAILY_FVG), hist=hist_close(close=4020.0, hi=4130.0, lo=3900.0))
    i = ib(ctx, "09:30") + 2
    o = sm4.dagger_order(ctx, sl, i, p, "AM", 1.0)
    assert o is not None and cap["entry"] == pytest.approx(4005.0) and cap["stop"] == pytest.approx(4004.0) and cap["tags"]["cancel_low"] == pytest.approx(4005.0)
    assert sm4.dagger_order(ctx, sl, i, p, "AM", 1.0) is None                                           # once per FVG
    sl.__dict__.pop("_dag_sent")
    ctx.cur_bias = 0
    assert sm4.dagger_order(ctx, sl, i, p, "AM", 1.0) is None                                           # no bias
    ctx.cur_bias = 1
    assert sm4.dagger_order(ctx, ss, i, p, "AM", 1.0) is None                                           # the short Side: no bullish daily FVG for it
    low_rows = DAG_ROWS[:2] + [(4010.0, 4011.0, 4003.0, 4004.0)]
    ctx2, (sl2, _) = mkctx(low_rows, base=4020.0, bias=1, conf=StubConf(arrays=DAILY_FVG), hist=hist_close(close=4020.0, hi=4130.0, lo=3900.0))
    assert sm4.dagger_order(ctx2, sl2, i, p, "AM", 1.0) is None                                         # the close is in the lower half
    z = lambda top, bot, k: L.Zone("bull", top, bot, k, k - 1)
    orig = sm4._tf_fvgs
    sm4._tf_fvgs = lambda ctx_, sd_, m: [z(4009.0, 4007.0, 1)] if m == 15 else []
    try:
        sl.__dict__.pop("_dag_sent", None)
        assert sm4.dagger_order(ctx, sl, i, p, "AM", 1.0) is not None and cap["entry"] == pytest.approx(4005.0)       # ce (the default level)
        sl.__dict__.pop("_dag_sent", None)
        assert sm4.dagger_order(ctx, sl, i, replace(p, dagger_level="ltf"), "AM", 1.0) is not None and cap["entry"] == pytest.approx(4007.0)   # the 15m FVG low above the CE
        sm4._tf_fvgs = lambda ctx_, sd_, m: [z(4004.0, 4002.0, 0)] if m == 60 else []
        sl.__dict__.pop("_dag_sent", None)
        assert sm4.dagger_order(ctx, sl, i, p, "AM", 1.0) is not None                                   # a lower-half hourly FVG still open: fine
        filled = DAG_ROWS[:1] + [(4013.0, 4014.0, 4001.5, 4010.0), (4010.0, 4011.0, 4007.5, 4008.0)]
        ctx3, (sl3, _) = mkctx(filled, base=4020.0, bias=1, conf=StubConf(arrays=DAILY_FVG), hist=hist_close(close=4020.0, hi=4130.0, lo=3900.0))
        assert sm4.dagger_order(ctx3, sl3, i, p, "AM", 1.0) is None                                     # price already filled the lower-half imbalance today
    finally:
        sm4._tf_fvgs = orig


# --- 12 M12-0930-htf-fvg-stab-no-mss -----------------------------------------------------------------------------------------------------------------

def test_htf_stab_entry(cap, monkeypatch):
    """015 ~00:16:57: rel-eq lows 4000 run, a 15m FVG 3992-3995 below the pool: the limit at its near edge (3995), the stop under its far edge, no MSS / SMT; the limit fills on a bar to 3994 and
    not on a run that stops at 3998; an FOMC day, a pool that is not a relative equal low, a close under the FVG and no FVG give nothing."""
    p = Params(**BASE, turtle_soup="htf_stab")
    rows = [(4001.0, 4002.0, 3999.0, 3999.5)] * 4
    ctx, (sl, ss) = mkctx(rows, base=4001.0, hist=hist_close(close=4001.0, hi=4130.0, lo=3900.0))
    i = ib(ctx, "09:30") + 3
    monkeypatch.setattr(S, "_ts_arrays", lambda ctx_, sd_, i_, kb, tfs=None, src=None: [(3995.0, 3992.0, None)] if tfs == ("15m", "1h") and src == (0,) else [])
    sw = dict(session="AM", name="rel_eq_lows", level=4000.0, key="rel_eq_lows0", ext=3999.0, ext_i=i - 1, broke=None, sweep_i=i - 1)
    assert sm4.stab_order(ctx, sl, sw, i, p, "AM", 1.0) is not None
    assert cap["entry"] == pytest.approx(3995.0) and cap["stop"] == pytest.approx(3992.0 - p.pad) and sw["ts_sent"]
    o = dict(entry=3995.0)
    sd_hit = sd_of([(3999.0, 3999.5, 3994.0, 3996.0)])
    sd_miss = sd_of([(3999.0, 3999.5, 3998.0, 3999.0)])
    assert S._fill_at(sd_hit, o, 0) == pytest.approx(3995.0) and S._fill_at(sd_miss, o, 0) is None
    assert sm4.stab_order(ctx, sl, dict(sw, key="pdl1"), i, p, "AM", 1.0) is None                          # only relative equal lows
    monkeypatch.setattr(S, "_ts_arrays", lambda *a, **k: [])
    assert sm4.stab_order(ctx, sl, dict(sw), i, p, "AM", 1.0) is None                                      # no HTF FVG beyond the pool
    monkeypatch.setattr(S, "_ts_arrays", lambda *a, **k: [(3995.0, 3992.0, None)])
    ctx_f, (sl_f, _) = mkctx(rows, base=4001.0, d=date(2026, 6, 17), hist=hist_close(d=date(2026, 6, 17), close=4001.0, hi=4130.0, lo=3900.0))
    assert sm4.stab_order(ctx_f, sl_f, dict(sw), i, p, "AM", 1.0) is None                                  # an FOMC day
    low = [(4001.0, 4002.0, 3999.0, 3999.5)] * 3 + [(3999.5, 3999.6, 3990.0, 3991.0)]
    ctx_c, (sl_c, _) = mkctx(low, base=4001.0, hist=hist_close(close=4001.0, hi=4130.0, lo=3900.0))
    assert sm4.stab_order(ctx_c, sl_c, dict(sw, ext=3990.0), i, p, "AM", 1.0) is None                      # the bodies closed through the FVG
    assert S._turtle(ctx, sl, dict(sw), i, p, "AM", 1.0) is not None                                       # the engine's turtle branch dispatches to it


# --- 13 B12-po3-low-after-0830-into-old-low -----------------------------------------------------------------------------------------------------------

def test_po3_ideal_tag():
    """013 ~00:04:52: bullish day, a sweep at / after 08:30 under the midnight open that took an old low under it = the ideal PO3 low (tag po3_ideal); a sweep before 08:30, one that stays above
    the open or one that took no old low under it is not; require drops the others."""
    rows = [(4100.0, 4101.0, 4099.0, 4100.0)] * 8
    ctx, (sl, ss) = mkctx(rows, base=4100.0, start="08:30", hist=hist_close(close=4100.0, hi=4130.0, lo=3900.0))
    i = ib(ctx, "08:30") + 6
    p = Params(**BASE, po3_ideal="tag")
    tags, lvt = {}, []
    sw = dict(session="AM", key="pdl1", level=4095.0, ext=4093.0, ext_i=ib(ctx, "08:35"), sweep_i=ib(ctx, "08:35"), broke=i - 1)
    assert sm4.order_gate4(ctx, sl, sw, i, p, 4097.0, 4090.0, "AM", lvt, {}, tags) is None and "po3_ideal" in lvt
    for kw in (dict(ext_i=ib(ctx, "08:00")), dict(level=4102.0), dict(ext=4101.0)):
        lvt2 = []
        assert sm4.order_gate4(ctx, sl, dict(sw, **kw), i, p, 4097.0, 4090.0, "AM", lvt2, {}, {}) is None and "po3_ideal" not in lvt2
        assert sm4.order_gate4(ctx, sl, dict(sw, **kw), i, replace(p, po3_ideal="require"), 4097.0, 4090.0, "AM", [], {}, {}) == "x_po3_ideal"
    assert sm4.order_gate4(ctx, sl, sw, i, replace(p, po3_ideal="require"), 4097.0, 4090.0, "AM", [], {}, {}) is None


# --- 14 new-po3-midnight-open-resting-order ------------------------------------------------------------------------------------------------------------

def test_po3_resting_order(cap, monkeypatch):
    """013 ~00:09:46: at the 00:00 close with the bias of the night before (+1): a minimum-size limit 0.25 under the midnight open, the stop under the nearest old low (PDL), no adds, a day trade
    (no breakeven / trail), target 2 = the HTF objective; the fill rewrites the ladder to [the day's high formed before the fill, the objective]. No bias / no old low under the limit = nothing."""
    p = Params(**BASE, po3_resting=True)
    rows = [(4100.0, 4101.0, 4099.0, 4100.0)] * 4
    ctx, sides = mkctx(rows, base=4100.0, start="00:00", conf=StubConf(trend=1), hist=hist_close(close=4100.0, hi=4130.0, lo=4040.0))
    monkeypatch.setattr(sm3, "htf_level_beyond", lambda *a, **k: 4130.0)
    o = sm4.po3_rest_order(ctx, sides, ctx.start, p, 1.0)
    assert o is not None and cap["entry"] == pytest.approx(4099.75) and cap["stop"] == pytest.approx(4040.0 - p.pad) and cap["session"] == "PO3R"
    assert cap["tags"]["day_trade"] and cap["tags"]["no_expire"] and cap["fixed"] == [(4130.0 - p.exit_before_pts * p.es_pt, "array")]
    assert o["shares"] == 1 and o["plan_shares"] == 1 and o["no_adds"] is True
    assert sm4.po3_rest_order(ctx, sides, ctx.start, replace(p, po3_rest_mgmt="normal"), 1.0) is not None and cap["tags"]["day_trade"] is False       # "normal" management: breakeven / trail allowed
    ctx0, sides0 = mkctx(rows, base=4100.0, start="00:00", conf=StubConf(trend=0), hist=hist_close(close=4100.0, hi=4130.0, lo=4040.0))
    assert sm4.po3_rest_order(ctx0, sides0, ctx0.start, p, 1.0) is None                                 # no bias the night before
    ctx1, sides1 = mkctx(rows, base=4100.0, start="00:00", conf=StubConf(trend=1), hist=hist_close(close=4100.0, hi=4130.0, lo=4040.0))
    assert sm4.po3_rest_order(ctx1, sides1, ctx1.start + 1, p, 1.0) is None                             # only on the 00:00 bar
    # the fill rewrites the ladder: T1 = the day's high so far, T2 = the objective
    sd = sides[0]
    ctx.h[ctx.start + 2] = 4108.0
    sd2 = S.Side(1, ctx.o, ctx.h, ctx.l, ctx.c, p.pivot_n)
    pos = dict(basis=4099.75, n=1, stop=4040.0, levels=[4125.0], level_kinds=["array"], fracs=(1.0,), t1=4125.0, t2=None, final_T=False)
    tr = SimpleNamespace(t1=0.0, t2=None)
    sm4.on_fill(ctx, sd2, pos, tr, dict(sm4=dict(kind="po3_rest", obj=4129.5)), ctx.start + 3, p)
    assert pos["levels"] == [4108.0, 4129.5] and pos["fracs"] == (0.5, 0.5) and tr.t1 == 4108.0 and tr.t2 == 4129.5 and pos["sm4"]["kind"] == "po3_rest"


# --- 15 M5-lasthour-first-unit-at-old-low ---------------------------------------------------------------------------------------------------------------

def test_lh_old_low_first_unit(cap, monkeypatch):
    """013 ~00:26:58: 15:05, bias +1: the nearest untaken old low under the close (lunch low 4090 beats the AM low 4080) = a limit filled on a 1-tick print through, no MSS yet, the stop 3 pts under it;
    the first bullish FVG of the rally arms a same-size second unit on a down-close bar into it. Outside the last hour or without the bias nothing."""
    p = Params(**BASE, lh_old_low_entry=True)
    rows = [(4100.0, 4101.0, 4099.0, 4100.0)] * 72
    ctx, (sl, ss) = mkctx(rows, base=4100.0, bias=1, hist=hist_close(close=4100.0, hi=4130.0, lo=3900.0))
    monkeypatch.setattr(S, "_sell_side", lambda *a, **k: {"lunch": 4090.0, "am_session": 4080.0})
    monkeypatch.setattr(S, "_level_intact", lambda *a, **k: True)
    i = ib(ctx, "15:05")
    assert sm4.lh_old_low_order(ctx, sl, i, p, "PM", 1.0) is not None
    assert cap["entry"] == pytest.approx(4090.0) and cap["stop"] == pytest.approx(4087.0) and cap["tags"]["through"] == p.tick and cap["tags"]["sm4"]["kind"] == "lh_old_low"
    assert sm4.lh_old_low_order(ctx, sl, i, p, "PM", 1.0) is None                                       # once per pool
    sl.__dict__.pop("_lhol_sent")
    assert sm4.lh_old_low_order(ctx, sl, ib(ctx, "14:30"), p, "PM", 1.0) is None                        # before 15:00
    ctx.cur_bias = 0
    assert sm4.lh_old_low_order(ctx, sl, i, p, "PM", 1.0) is None                                       # no bias
    # the second unit: after the fill a bullish FVG forms on the rally; a down-close bar trading into it arms the same-size add
    r2 = [(4091.0, 4091.5, 4090.0, 4091.0), (4092.0, 4093.0, 4091.0, 4092.5), (4092.5, 4097.0, 4092.4, 4096.5), (4096.5, 4099.0, 4095.5, 4098.0), (4098.0, 4098.5, 4094.0, 4095.0)]
    sd = sd_of(r2)
    armed = []
    monkeypatch.setattr(S, "_arm_add", lambda pos, tr, px, i_, p_, eq, **k: armed.append((px, k.get("size"), k.get("floor"))))
    pos = dict(fill_i=0, left=10, add=None, stop=4087.0, plan_shares=10, sm4=dict(kind="lh_old_low", add2=None))
    sm4.manage(ctx, sd, pos, SimpleNamespace(), 4, None, p)
    assert armed == [(4095.5, 10, 4093.0)] and pos["sm4"]["add2"] == 3
    sm4.manage(ctx, sd, pos, SimpleNamespace(), 4, None, p)
    assert len(armed) == 1                                                                             # one second unit


# --- 16 M6-pm-continuation-long-at-old-high -------------------------------------------------------------------------------------------------------------

def test_pm_old_high_fvg_long(cap, monkeypatch):
    """015 ~00:31:57: PM, bias +1, the AM high 4106 just traded above, a bullish 1m FVG 4105.2-4106.5 spanning it: a buy limit at the FVG top (candle-3 low), the stop under it, the single target
    the HTF objective; the add is the open of the first down-close candle that retraces into it; the target fill arms the M6 reversal (done flag)."""
    p = Params(**{**BASE, "adds": (0.5,)}, pm_old_high_fvg=True)
    am = [(4100.0, 4106.0, 4099.0, 4100.0)] + [(4100.0, 4100.5, 4099.5, 4100.0)] * 40
    pm_ = [(4104.0, 4105.2, 4103.5, 4105.0), (4105.0, 4109.0, 4104.9, 4108.8), (4108.8, 4110.0, 4106.5, 4109.0)]
    ctx, (sl, ss) = mkctx(am + [(4100.0, 4100.5, 4099.5, 4100.0)] * 7 + pm_, base=4100.0, bias=1, hist=hist_close(close=4100.0, hi=4130.0, lo=3900.0))
    monkeypatch.setattr(sm3, "htf_level_beyond", lambda *a, **k: 4120.0)
    i = ib(ctx, "13:30") + 2
    assert ctx.am_hl[0] == 4110.0 or ctx.am_hl[0] >= 4106.0
    ctx.am_hl = (4106.0, ctx.am_hl[1])                                                                   # the AM high the test is about
    assert sm4.pm_old_high_order(ctx, sl, i, p, "PM", 1.0) is not None
    assert cap["entry"] == pytest.approx(4106.5) and cap["stop"] == pytest.approx(4105.2 - p.pad) and cap["fixed"] == [(4120.0 - p.exit_before_pts * p.es_pt, "array")]
    assert cap["tags"]["sm4"]["kind"] == "pm_old_high"
    assert sm4.pm_old_high_order(ctx, sl, i, p, "PM", 1.0) is None                                      # once per gap
    sl.__dict__.pop("_pmoh_sent")
    ctx.cur_bias = 0
    assert sm4.pm_old_high_order(ctx, sl, i, p, "PM", 1.0) is None                                      # no bias
    ctx.cur_bias = 1
    ctx.am_hl = (4120.0, ctx.am_hl[1])
    assert sm4.pm_old_high_order(ctx, sl, i, p, "PM", 1.0) is None                                      # the FVG does not span an old high
    assert sm4.pm_old_high_order(ctx, sl, ib(ctx, "11:00"), p, "AM", 1.0) is None                       # not the PM
    # the add at the open of the first down-close retrace candle; the target fill arms the reversal
    armed = []
    monkeypatch.setattr(S, "_arm_add", lambda pos, tr, px, i_, p_, eq, **k: armed.append((px, k.get("size"))))
    sd = sd_of([(4107.0, 4108.0, 4106.8, 4107.5), (4107.5, 4107.9, 4105.8, 4106.0)])
    pos = dict(fill_i=0, left=10, add=None, stop=4105.0, plan_shares=10, sm4=dict(kind="pm_old_high", gap=(4106.5, 4105.2), added=False))
    sm4.manage(ctx, sd, pos, SimpleNamespace(), 1, None, p)
    assert armed == [(4107.5, 5)]
    done = {}
    sm4.after_close(pos, SimpleNamespace(final_hit=False), done)
    assert "PM_REV_ARMED" not in done
    sm4.after_close(pos, SimpleNamespace(final_hit=True), done)
    assert done["PM_REV_ARMED"] is True


# --- 17 M6-ifvg-must-stay-partly-open -----------------------------------------------------------------------------------------------------------------

def test_pm_rev_gap_full_refill_exits():
    """015 ~00:33:56: with pm_rev_partial the reversal's gap must stay partly open - a trade through its far edge exits at once (reason gap_refill), at the open on a gap; the lunch relative equal
    pools (12:00-13:00 pivot highs within the tolerance, side space) join the ladder."""
    p = Params(**BASE, pm_rev_partial=True)
    ctx, (sl, ss) = mkctx([(4100.0, 4100.5, 4099.5, 4100.0)] * 5, base=4100.0, hist=hist_close(close=4100.0, hi=4130.0, lo=3900.0))
    sd = sd_of([(4100.0, 4101.0, 4099.0, 4100.5), (4100.5, 4101.0, 4098.0, 4099.0), (4099.0, 4099.5, 4094.5, 4095.0)])
    pos = dict(fill_i=0, left=10, add=None, stop=4094.0, plan_shares=10, sm4=dict(kind="pm_rev_partial", far=4095.0))
    tr = SimpleNamespace(exits=[])
    sm4.manage(ctx, sd, pos, tr, 1, "t1", p)
    assert not tr.exits and pos["left"] == 10                                                           # the gap's far edge 4095 was not traded
    sm4.manage(ctx, sd, pos, tr, 2, "t2", p)
    assert tr.exits == [("t2", 4095.0, 10, "gap_refill")] and pos["left"] == 0
    # lunch rel-eq pools: two pivot highs at 4110.0 / 4110.2 formed 12:20-12:40, untraded since 13:00
    rows = [(4100.0, 4101.0, 4099.0, 4100.0)] * 3 + [(4100.0, 4110.0, 4099.0, 4105.0)] + [(4104.0, 4105.0, 4103.0, 4104.0)] * 2 + [(4104.0, 4110.2, 4103.0, 4105.0)] + [(4104.0, 4105.0, 4103.0, 4104.0)] * 8
    ctx2, (sl2, _) = mkctx(rows, base=4100.0, start="12:15", hist=hist_close(close=4100.0, hi=4130.0, lo=3900.0))
    i2 = ib(ctx2, "12:15") + len(rows) - 1
    eq = sm4.lunch_eq_highs(ctx2, sl2, i2, p)
    assert len(eq) == 1 and eq[0] == pytest.approx(4110.2)
    ctx2.conf = None
    assert (4110.2, "pool") in sm4.pm_rev_extra_targets(ctx2, sl2, i2, p, 4100.0)


# --- 19 new-pm-retracement-short-after-draw-delivered -------------------------------------------------------------------------------------------------

def _after_rows():
    am = [(4090.0, 4091.0, 4089.0, 4090.5), (4090.5, 4098.0, 4090.4, 4097.5), (4097.5, 4099.0, 4094.0, 4098.0), (4098.0, 4112.0, 4097.0, 4111.0)]
    am += [(4111.0, 4111.5, 4110.5, 4111.0)] * 44                                                      # to 13:30
    pm_ = [(4111.0, 4112.0, 4108.0, 4109.0), (4109.0, 4109.5, 4100.0, 4101.0), (4101.0, 4102.0, 4092.0, 4090.5),
           (4090.5, 4091.0, 4089.0, 4089.5), (4089.5, 4089.8, 4087.0, 4087.5), (4087.5, 4087.8, 4085.0, 4085.5)]
    return am + pm_


def test_pm_after_draw_short(cap, monkeypatch):
    """019 ~00:20:53: the AM draw (up) is delivered; a 5m bullish FVG (4091-4094) served as AM support and a body closes under it (4090.5): a bearish gap forming at / under that resistance
    (4087.8-4089) is the entry - a sell limit at its lower edge, stop above it, targets the day's low (AM origin side) - 13:20-15:00 only, with the 10-handle room rule; (b) a displacement that
    breaks a short-term swing and leaves a SIBI when no flip exists."""
    p = Params(**BASE, pm_after_draw=True)
    rows = _after_rows()
    ctx, (sl, ss) = mkctx(rows, base=4090.0, hist=hist_close(close=4090.0, hi=4130.0, lo=3900.0))
    i = ib(ctx, "13:30") + 5
    monkeypatch.setattr(sm4, "delivered_bar", lambda ctx_, b, i_: ib(ctx_, "09:45") if b == 1 else None)
    assert sm4.pm_after_order(ctx, ss, i, p, "PM", 1.0) is not None
    assert cap["entry"] == pytest.approx(-4087.8) and cap["stop"] == pytest.approx(-4089.0 - p.pad) and cap["tags"]["done_key"] == "PMA"
    assert cap["fixed"][0][0] > cap["entry"] and "pm_after_flip" in cap["tags"]["lv_tags"]
    sm4.pm_after_order(ctx, ss, i, p, "PM", 1.0)
    assert cap["entry"] != pytest.approx(-4087.8)                                                       # once per gap (the next call arms an older one, never the same)
    ss.__dict__.pop("_pma_sent")
    assert sm4.pm_after_order(ctx, sl, i, p, "PM", 1.0) is None                                        # the long Side: the draw it would run (down) was not delivered
    assert sm4.pm_after_order(ctx, ss, ib(ctx, "13:15"), p, "PM", 1.0) is None                         # before 13:20
    assert sm4.pm_after_order(ctx, ss, ib(ctx, "15:05"), p, "PM", 1.0) is None                         # after 15:00 (nothing armed that late)
    monkeypatch.setattr(sm4, "delivered_bar", lambda *a: None)
    assert sm4.pm_after_order(ctx, ss, i, p, "PM", 1.0) is None                                        # the objective is not delivered
    monkeypatch.setattr(sm4, "delivered_bar", lambda ctx_, b, i_: ib(ctx_, "09:45") if b == 1 else None)
    ss._opp = [L.Zone("bear", -4080.0, -4084.8, i, i - 1)]                                             # a gap 3 points ahead of the entry: no room
    assert sm4.pm_after_order(ctx, ss, i, p, "PM", 1.0) is None
    # (b) no AM FVG to flip: the displacement through a swing low that leaves a SIBI
    monkeypatch.setattr(sm4, "_tf_fvgs", lambda ctx_, sd_, m: [])
    ss._opp = None
    monkeypatch.setattr(sm4, "mss_gap", lambda *a: True)
    assert sm4.pm_after_order(ctx, ss, i, p, "PM", 1.0) is not None and "pm_after_sibi" in cap["tags"]["lv_tags"]
    # mss_gap itself: a close above the confirmed swing high of the (mirrored) leg
    monkeypatch.undo()
    sd = sd_of([(10.0, 10.5, 9.5, 10.0), (10.0, 11.0, 9.8, 10.8), (10.8, 10.9, 10.2, 10.3), (10.3, 12.5, 10.2, 12.4), (12.4, 13.0, 11.8, 12.9)])
    g = [z for z in sd.gaps if z.i == 4][0]
    assert sm4.mss_gap(sd, g, 0) is True
    sd2 = sd_of([(10.0, 10.5, 9.5, 10.0), (10.0, 11.0, 9.8, 10.8), (10.8, 10.9, 10.2, 10.3), (10.3, 10.95, 10.2, 10.9), (10.9, 13.0, 11.8, 12.9)])
    g2 = [z for z in sd2.gaps if z.i == 4][0]
    assert sm4.mss_gap(sd2, g2, 0) is False                                                            # the middle candle did not close above the swing high (11.0)


def test_sb_counter_after_draw():
    """060 ~01:09:30: with sb_counter_after_draw the room rule of the Silver Bullet's opposite side (14:00-15:00, draw delivered) is the 10-handle rule: no gap / void within pm_after_room_pts
    beyond the entry; `sm4.room_ok` is the rule the main engine's after-draw retracement uses too. (The window / lock wiring is covered by the run in test_caption_gap_sm4b.)"""
    p = Params(**BASE)
    sd = sd_of([(10.0, 10.5, 9.5, 10.0)] * 4)
    assert sm4.room_ok(sd, 10.0, 3, p) is True
    sd._opp = [L.Zone("bear", 25.0, 15.0, 2, 1)]
    assert sm4.room_ok(sd, 10.0, 3, replace(p, pm_after_room_pts=4.0)) is True                       # the gap is 5 points away: a 4-point room is fine
    assert sm4.room_ok(sd, 10.0, 3, replace(p, pm_after_room_pts=6.0)) is False


# --- 20 M1-ob-entry-after-mss --------------------------------------------------------------------------------------------------------------------------

def test_entry_arrays_ob_post(cap):
    """020 ~00:06:14: after the MSS the first down-close candle of the pullback is the OB: the limit at its open (ob_entry_px body_top), cancelled by a body close under its MT; a later close under
    the MT invalidates the candidate."""
    p = Params(**BASE, entry_arrays=("ob_post",))
    rows = [(4010.0, 4011.0, 4000.0, 4001.0), (4001.0, 4006.0, 4000.5, 4005.0), (4005.0, 4012.0, 4004.5, 4011.0), (4011.0, 4012.0, 4005.5, 4006.0), (4006.0, 4012.5, 4005.9, 4012.0)]
    ctx, (sl, ss) = mkctx(rows, base=4010.0, hist=hist_close(close=4010.0, hi=4130.0, lo=3900.0))
    e = ib(ctx, "09:30")
    sw = dict(session="AM", key="pdl1", name="pdl1", level=4001.0, ext=4000.0, ext_i=e, broke=e + 2, sweep_i=e, smt=None, smt2=None)
    i = e + 4
    c = sm4.ob_post_cand(ctx, sl, sw, i, p)
    assert c == (pytest.approx(4011.0), pytest.approx(4006.0), "ob_post") and sw["_ob_post_mt"] == pytest.approx(4008.5)
    assert [x for x in SM.array_cands(ctx, sl, sw, i, p, None) if x[2] == "ob_post"] == [c]
    assert SM.array_order(ctx, sl, sw, i, p, "AM", 1.0, None, None) is not None
    assert cap["entry"] == pytest.approx(4011.0) and cap["tags"]["cancel_close"] == pytest.approx(4008.5) and cap["tags"]["entry_kind"] == "arr_ob_post"
    assert sm4.ob_post_cand(ctx, sl, dict(sw, broke=None), i, p) is None                                  # no MSS yet
    rows2 = rows[:4] + [(4006.0, 4007.0, 4003.0, 4004.0)]
    ctx2, (sl2, _) = mkctx(rows2, base=4010.0, hist=hist_close(close=4010.0, hi=4130.0, lo=3900.0))
    assert sm4.ob_post_cand(ctx2, sl2, sw, ib(ctx2, "09:30") + 4, p) is None                              # a body closed under the MT
    assert not [x for x in SM.array_cands(ctx, sl, sw, i, replace(p, entry_arrays=("ob",)), None) if x[2] == "ob_post"]    # not without the switch value


# --- 21 B5-multi-tf-fvg-scan ---------------------------------------------------------------------------------------------------------------------------

def test_leg_tf_fallback_3m(monkeypatch):
    """022 ~00:43:05: no gap of the leg at / under the EQ on the base bars: the scan walks `leg_tfs` in order and takes the first timeframe that has a qualifying gap; a narrower gap of a later
    (lower) timeframe inside it supplies the edges; a base gap under the EQ means no scan. (5m base bars here: the 15m bucket is the higher timeframe; 1m / 3m use the same zones_tf code.)"""
    rows = [(4000.0, 4001.0, 3990.0, 4000.0)] * 3 + [(4000.0, 4020.0, 3999.0, 4019.0)] * 3 + [(4019.0, 4025.0, 4005.0, 4024.0)] * 3
    ctx, (sl, ss) = mkctx(rows, base=4000.0, hist=hist_close(close=4000.0, hi=4130.0, lo=3900.0))
    e = ib(ctx, "09:30")
    i = e + 8
    sw = dict(session="AM", ext=3990.0, ext_i=e, key="x", broke=e + 3)
    p = Params(**BASE, leg_tfs=(15,))
    z15 = L.Zone("bull", 4005.0, 4000.0, e + 8, e + 3)
    inner = L.Zone("bull", 4004.0, 4002.0, e + 7, e + 5)
    real = sm4._tf_fvgs
    monkeypatch.setattr(sm4, "_tf_fvgs", lambda ctx_, sd_, m: {15: [z15], 5: [inner]}.get(m, []))
    g, added = sm4.leg_tf_gaps(ctx, sl, sw, [], i, p)
    assert added == [z15] and g == [z15] and sw["leg_tf"] == 15                                         # EQ = 4007.5: the 15m gap 4000-4005 is in the discount
    g, added = sm4.leg_tf_gaps(ctx, sl, dict(sw), [], i, replace(p, leg_tfs=(15, 5)))
    assert added == [inner]                                                                            # the narrower 5m gap inside the 15m one
    below = L.Zone("bull", 4006.0, 4003.0, e + 6, e + 4)
    g, added = sm4.leg_tf_gaps(ctx, sl, dict(sw), [below], i, p)
    assert added == [] and g == [below]                                                                # a base gap under the EQ exists: no scan
    hi_z = L.Zone("bull", 4015.0, 4010.0, e + 8, e + 3)
    monkeypatch.setattr(sm4, "_tf_fvgs", lambda ctx_, sd_, m: [hi_z] if m == 15 else [])
    assert sm4.leg_tf_gaps(ctx, sl, dict(sw), [], i, p) == ([], [])                                    # above the EQ: not qualifying
    # the real zones_tf on 5m bars: m == the base tf returns the base gaps, a 15m bucket is built from three bars
    monkeypatch.setattr(sm4, "_tf_fvgs", real)
    assert sm4._tf_fvgs(ctx, sl, 5) == [z for z in sl.gaps] and sm4._tf_fvgs(ctx, sl, 7) == [] and sm4._tf_fvgs(ctx, sl, 1) == []
    z15s = sm4._tf_fvgs(ctx, sl, 15)
    assert any(z.top == 4005.0 and z.bottom == 4001.0 for z in z15s), [(z.top, z.bottom) for z in z15s]


# --- 22 M2-leg-eq-after-low-prints ----------------------------------------------------------------------------------------------------------------------

def test_m2_eq_moves_with_new_low():
    """022 ~00:47:17: the EQ of the leg moves with every new extreme: a gap with its top at 4012 is no entry while the leg high is 4020 (EQ 4010) and qualifies once the leg runs to 4030 (EQ 4015);
    a pending order whose gap top lies above the current EQ is cancelled."""
    sw = dict(ext=4000.0, ext_i=0)
    g = L.Zone("bull", 4012.0, 4008.0, 2, 1)
    sd = sd_of([(4001.0, 4003.0, 4000.0, 4002.0), (4002.0, 4020.0, 4001.5, 4019.0), (4019.0, 4020.0, 4017.0, 4018.0)])
    assert sm4.m2_discount_gaps(sd, sw, [g], 2) == []
    sd2 = sd_of([(4001.0, 4003.0, 4000.0, 4002.0), (4002.0, 4020.0, 4001.5, 4019.0), (4019.0, 4030.0, 4017.0, 4029.0)])
    assert sm4.m2_discount_gaps(sd2, sw, [g], 2) == [g]
    o = dict(ext=4000.0, ext_i=0, zone_top=4012.0, entry=4012.0)
    assert sm4.m2_order_dead(sd, o, 2) is True and sm4.m2_order_dead(sd2, o, 2) is False
    assert sm4.m2_eq(sd, sw, 2) == pytest.approx(4010.0)


# --- 23 M2-pyramid-runup-leg-eq -------------------------------------------------------------------------------------------------------------------------

def test_m2_runup_anchor():
    """022 ~01:03:28: m2_anchor "runup" - the EQ is taken from the swing the run into the swept pool started from (4030) to the sweep extreme (4000): 4015. A VI at / under it in the
    displacement wins over the FVG; with no VI the FVG there; nothing under the EQ = the leg-EQ pick stands (None)."""
    rows = [(4020.0, 4025.0, 4018.0, 4024.0), (4024.0, 4030.0, 4023.0, 4028.0), (4028.0, 4029.0, 4015.0, 4016.0), (4016.0, 4017.0, 4001.0, 4002.0), (4002.0, 4003.0, 4000.0, 4001.5),
            (4001.5, 4008.0, 4001.2, 4007.0), (4008.0, 4012.0, 4006.5, 4011.0)]
    ctx, (sl, ss) = mkctx(rows, base=4020.0, hist=hist_close(close=4020.0, hi=4130.0, lo=3900.0))
    e0 = ib(ctx, "09:30")
    i = e0 + 6
    sw = dict(session="AM", ext=4000.0, ext_i=e0 + 4, key="x", broke=e0 + 6)
    p = Params(**BASE, m2_anchor="runup", fvg_pick="2022")
    fv = [g for g in sl.gaps if g.i == e0 + 6]
    assert fv and fv[0].top == 4006.5
    vi = sm4.runup_pick(ctx, sl, sw, fv, i, p)
    assert vi is not None and vi.top == 4008.0 and vi in sl.vis("bull")                                   # the VI first
    rows_nvi = rows[:6] + [(4007.0, 4012.0, 4006.5, 4011.0)]
    ctx2, (sl2, _) = mkctx(rows_nvi, base=4020.0, hist=hist_close(close=4020.0, hi=4130.0, lo=3900.0))
    fv2 = [g for g in sl2.gaps if g.i == e0 + 6]
    assert sm4.runup_pick(ctx2, sl2, sw, fv2, i, p) == fv2[-1]                                            # no VI: the FVG
    assert sm4.runup_pick(ctx2, sl2, dict(sw), [L.Zone("bull", 4026.0, 4020.0, i, i - 1)], i, p) is None  # nothing under the EQ
    assert SM.pick_2022(ctx2, sl2, sw, fv2, i, p) == fv2[-1]                                              # pick_2022 delegates (the runup answer is the FVG)


# --- 26 M2-implied-range-eq-gate ------------------------------------------------------------------------------------------------------------------------

def test_implied_range_needs_discount_first():
    """025 ~00:46:41: the implied range = the sweep extreme H (4000) .. the session objective (4040), EQ 4020. Until price trades into the discount (side space: a high at / over 4020 after the
    extreme) the order waits; then only the gaps at / under the EQ are entries; no objective = the gate is n/a; the adds stay on the entry side of the EQ."""
    p = Params(**BASE, implied_range_gate=True)
    rows = [(4001.0, 4003.0, 4000.0, 4002.0), (4002.0, 4010.0, 4001.0, 4009.0), (4009.0, 4012.0, 4008.0, 4011.0)]
    ctx, (sl, ss) = mkctx(rows, base=4001.0, hist=hist_close(close=4001.0, hi=4130.0, lo=3900.0))
    ctx.cur_lock = dict(side=1, target=4040.0, kind="pool", name="pdh1", marked=[])
    e = ib(ctx, "09:30")
    sw = dict(session="AM", ext=4000.0, ext_i=e, key="x", broke=e + 1)
    g_lo, g_hi = L.Zone("bull", 4015.0, 4012.0, e + 2, e + 1), L.Zone("bull", 4026.0, 4022.0, e + 2, e + 1)
    assert sm4.implied_eq(ctx, sl, sw, e + 2, p, "AM") == pytest.approx(4020.0)
    assert sm4.implied_gate(ctx, sl, sw, [g_lo, g_hi], e + 2, p, "AM") == ("wait", [g_lo, g_hi])        # price has not traded to the EQ yet
    rows2 = rows + [(4011.0, 4021.0, 4010.0, 4020.5), (4020.5, 4021.0, 4014.0, 4015.0)]
    ctx2, (sl2, _) = mkctx(rows2, base=4001.0, hist=hist_close(close=4001.0, hi=4130.0, lo=3900.0))
    ctx2.cur_lock = ctx.cur_lock
    eq, gs = sm4.implied_gate(ctx2, sl2, sw, [g_lo, g_hi], e + 4, p, "AM")
    assert eq == pytest.approx(4020.0) and gs == [g_lo]
    ctx2.cur_lock = None
    assert sm4.implied_gate(ctx2, sl2, sw, [g_lo, g_hi], e + 4, p, "AM") == (None, [g_lo, g_hi])        # no objective: n/a
    pos = dict(fill_i=0, leg=(4000.0, 4030.0), sm4=dict(kind="implied", implied_eq=4020.0))
    assert SM.add_pd_ok(pos, 4018.0, p) is True and SM.add_pd_ok(pos, 4022.0, p) is False


# --- 28 M7-pm-short-after-lunch-run-of-am-stops ----------------------------------------------------------------------------------------------------------

def test_pm_am_last_high_sweep_targets_am_low():
    """025 ~01:05:57: a bearish AM (side space of the short: mirrored) whose last swing high before noon (4092) is untraded at 12:00 is the PM pool `am_last_high`; a sweep of it enters at the FVG CE
    and targets the relative equal pools between, then the AM low; the pool exists from 12:00; no pool after an up AM."""
    am = [(4100.0 - k * 2.0, 4101.0 - k * 2.0, 4099.0 - k * 2.0, 4099.5 - k * 2.0) for k in range(10)] + [(4082.0, 4092.0, 4081.0, 4090.0), (4090.0, 4090.5, 4078.0, 4079.0)] + [(4079.0, 4080.0, 4078.5, 4079.5)] * 20
    ctx, (sl, ss) = mkctx(am + [(4079.5, 4080.0, 4079.0, 4079.5)] * 20, base=4100.0, hist=hist_close(close=4100.0, hi=4130.0, lo=3900.0))
    p = Params(**BASE, pm_am_stops=True)
    i = ib(ctx, "12:30")
    assert sm4.am_last_pool(ctx, ss, i, p) == pytest.approx(-4092.0)
    assert sm4.am_last_pool(ctx, ss, ib(ctx, "11:30"), p) is None                                      # not before noon
    assert sm4.am_last_pool(ctx, sl, i, p) is None                                                     # the long Side: the AM did not rise
    out = S._sell_side(ctx, ss, "PM", i, True, p)
    assert out.get("am_last_high") == pytest.approx(-4092.0)
    assert "am_last_high" not in S._sell_side(ctx, ss, "PM", i, True, replace(p, pm_am_stops=False))
    assert S._level_created(ctx, "am_last_high", "PM") == ib(ctx, "12:00")
    top, bot = -4085.0, -4087.0
    assert sm4.entry_adjust(dict(key="am_last_high"), top, top, bot, p) == pytest.approx(-4086.0)       # the CE
    assert sm4.entry_adjust(dict(key="pdl1"), top, top, bot, p) == top
    fx = sm4.am_stops_fixed(ctx, ss, i, p, -4086.0)
    assert fx[-1][1] == "pool" and fx[-1][0] == pytest.approx(S._exit_px(-float(ctx.am_hl[1]), "pool", p))


# --- 31 M5-lasthour-short-sequence ----------------------------------------------------------------------------------------------------------------------

LH_ROWS = [(4100.0, 4101.0, 4099.0, 4100.5), (4100.5, 4108.0, 4100.4, 4107.5), (4107.5, 4109.0, 4103.0, 4108.0)] + [(4108.0, 4108.3, 4107.7, 4108.0)] * 3 + \
    [(4108.0, 4108.5, 4102.5, 4106.0), (4106.0, 4109.0, 4105.0, 4108.5), (4108.0, 4108.8, 4106.0, 4107.0), (4108.5, 4110.5, 4106.5, 4110.0)]


def _mirror(rows, k=8200.0):
    return [(k - o, k - l, k - h, k - c) for o, h, l, c in rows]


def test_lh_array_short_sequence(cap):
    """026 ~01:35:33 (side space; long here, the short is the mirror): a bullish FVG 4101-4103 marked before 15:00; the 15:00 bar's low respects it (the rejection bar R, low 4102.5); the next
    bar makes no lower low and stays off the array, then its high is taken (early confirmation); the swing high formed after R (4109) is pierced by a tick (the MSS); the entry is the VI the
    displacement left (top 4108.5), the stop under R's low. 15:00-15:50 only; a trade under R's low invalidates; no MSS = nothing; the bearish mirror gives the mirrored order."""
    p = Params(**BASE, lh_array_short=True)
    ctx, (sl, ss) = mkctx(LH_ROWS, base=4100.0, start="14:30", hist=hist_close(close=4100.0, hi=4130.0, lo=3900.0))
    i = ib(ctx, "14:30") + len(LH_ROWS) - 1
    assert sm4.lh_array_order(ctx, sl, i, p, "PM", 1.0) is not None
    assert cap["entry"] == pytest.approx(4108.5) and cap["stop"] == pytest.approx(4102.5 - p.pad) and "lh_array_vi" in cap["tags"]["lv_tags"] and "lh_early_conf" in cap["tags"]["lv_tags"]
    assert sm4.lh_array_order(ctx, sl, i, p, "PM", 1.0) is None                                          # once per array / rejection bar
    sl.__dict__.pop("_lharr_sent")
    assert sm4.lh_array_order(ctx, sl, i - 1, p, "PM", 1.0) is None                                      # the MSS bar has not printed yet
    assert sm4.lh_array_order(ctx, sl, i, p, "AM", 1.0) is None
    assert sm4.lh_array_order(ctx, sl, ib(ctx, "14:55"), p, "PM", 1.0) is None                           # before 15:00
    bad = LH_ROWS[:7] + [(4106.0, 4108.8, 4102.0, 4103.0)] + LH_ROWS[8:]
    ctx2, (sl2, _) = mkctx(bad, base=4100.0, start="14:30", hist=hist_close(close=4100.0, hi=4130.0, lo=3900.0))
    assert sm4.lh_array_order(ctx2, sl2, i, p, "PM", 1.0) is None                                        # a trade under R's low invalidates
    ctxm, (slm, ssm) = mkctx(_mirror(LH_ROWS), base=4100.0, start="14:30", hist=hist_close(close=4100.0, hi=4130.0, lo=3900.0))
    ctxm.cur_bias = -1
    assert sm4.lh_array_order(ctxm, ssm, i, p, "PM", 1.0) is not None
    assert cap["entry"] == pytest.approx(-(8200.0 - 4108.5)) and cap["stop"] == pytest.approx(-(8200.0 - 4102.5) - p.pad)      # the short (mirrored prices)


# --- 32 B16-nwog-gapup-return-then-mss -----------------------------------------------------------------------------------------------------------------

def test_nwog_fill_then_mss_long():
    """028 ~01:22:36: a gap-up week (Friday close 4000, Monday open 4020): a long needs price to have traded back to 4000 since the week began and the sweep within 2 pts of it; no return, or a
    sweep away from the Friday close, = x_nwog_fill; a gap-down week is left alone (it needs no return); shorts are not judged."""
    mon, fri = date(2026, 6, 22), date(2026, 6, 18)                       # (06-19 is a holiday: the prior week ends on the Thursday)
    p = Params(**BASE, nwog_fill_long=True)
    rows = [(4010.0, 4011.0, 4009.0, 4010.0)] * 6

    def hist_for(fri_close, mon_low):
        out = []
        for x in prior_days(D0, 8):
            if x == fri:
                out.append(rth_day(x, 4045.0, 3990.0, close=fri_close))
            elif x == mon:
                out.append(rth_day(x, 4030.0, mon_low, close=4025.0, op=4020.0))
            else:
                out.append(rth_day(x, 4045.0, 3990.0, close=4020.0))
        return out
    ctx, (sl, ss) = mkctx(rows, base=4010.0, hist=hist_for(4000.0, 3995.0))
    ctx.hist = hist_for(4000.0, 3995.0)
    i = ib(ctx, "09:30") + 5
    sw = dict(session="AM", ext=4000.5, ext_i=i - 2, key="pdl1", level=4001.0, broke=i - 1)
    lvt = []
    assert sm4.nwog_fill_gate(ctx, sl, sw, i, p, lvt) is None and "nwog_fill" in lvt
    assert sm4.nwog_fill_gate(ctx, sl, dict(sw, ext=3990.0), i, p, []) == "x_nwog_fill"                  # the sweep is not at the Friday close
    assert sm4.nwog_fill_gate(ctx, ss, sw, i, p, []) is None                                              # shorts are not judged
    ctx2, (sl2, _) = mkctx(rows, base=4010.0, hist=hist_for(4000.0, 4015.0))
    ctx2.hist = hist_for(4000.0, 4015.0)
    assert sm4.nwog_fill_gate(ctx2, sl2, sw, i, p, []) == "x_nwog_fill"                                   # price never traded back to 4000 this week
    ctx3, (sl3, _) = mkctx(rows, base=4010.0, hist=hist_for(4040.0, 4015.0))
    ctx3.hist = hist_for(4040.0, 4015.0)
    assert sm4.nwog_fill_gate(ctx3, sl3, sw, i, p, []) is None                                            # a gap-down week
    assert sm4.order_gate4(ctx, sl, sw, i, p, 4005.0, 4000.0, "AM", [], {}, {}) is None                  # the same gate through the engine's order tail
    assert sm4.order_gate4(ctx2, sl2, sw, i, p, 4005.0, 4000.0, "AM", [], {}, {}) == "x_nwog_fill"
    assert sm4.order_gate4(ctx2, sl2, sw, i, replace(p, nwog_fill_long=False), 4005.0, 4000.0, "AM", [], {}, {}) is None


# --- 33 M11-wick-ce-fade-short ----------------------------------------------------------------------------------------------------------------------------

def test_wick_ce_short_intrabar(cap):
    """028 ~00:18:38 (the short side, mirrored prices): the upper-wick CE of the reference candle (high 4108, body top 4100.5) = 4104.25; wick_ce_mode "intrabar" arms on the sweep candle's close
    a limit one tick under it (sell 4104.0) with the stop wick_ce_pad_pts over the CE (4105.25), no close confirmation; "close" (the built behaviour) arms nothing here; a close at / under the
    limit price is no order."""
    p = Params(**BASE, wick_ce_entries=True, wick_ce_mode="intrabar", wick_ce_precursor=False)
    real = [(4100.0, 4108.0, 4099.0, 4100.5)] * 2
    ctx, (sl, ss) = mkctx(real, base=4100.0, hist=hist_close(close=4100.0, hi=4130.0, lo=3900.0))
    e = ib(ctx, "09:30")
    sw = dict(session="AM", key="pdh1", name="pdh1", level=4107.0, ext=-4108.0, ext_i=e, broke=None, sweep_i=e, smt=None, smt2=None)
    assert sm4.wick_ce_entry(ctx, ss, sw, e, p, "AM", 1.0, 0.0) is not None
    assert cap["entry"] == pytest.approx(-4104.0) and cap["stop"] == pytest.approx(-4105.25) and sw["wce_sent"] and cap["tags"]["entry_kind"] == "wick_ce"
    assert sm4.wick_ce_entry(ctx, ss, sw, e, p, "AM", 1.0, 0.0) is None                                  # once per sweep
    assert sm4.wick_ce_entry(ctx, ss, dict(sw, wce_sent=False), e + 1, p, "AM", 1.0, 0.0) is None        # only on the sweep candle itself
    assert sm4.wick_ce_entry(ctx, ss, dict(sw, wce_sent=False), e, replace(p, wick_ce_mode="close"), "AM", 1.0, 0.0) is None
    flat = [(4100.0, 4100.1, 4099.9, 4100.0)] + [(4100.0, 4100.1, 4099.9, 4100.0)]
    ctx2, (sl2, ss2) = mkctx([(4100.0, 4100.3, 4099.0, 4100.1)] * 2, base=4100.0, hist=hist_close(close=4100.0, hi=4130.0, lo=3900.0))
    sw2 = dict(sw, ext=-4100.3, wce_sent=False)
    assert sm4.wick_ce_entry(ctx2, ss2, sw2, e, p, "AM", 1.0, 0.0) is None                                # a wick of two tenths: the limit would sit at / above the close - no limit under the market
    # the pre_break dispatch
    assert SM.pre_break(ctx, ss, dict(sw, wce_sent=False), e, p, "AM", 1.0, 0.0) is not None
    # review fix (028 ~00:18:38): the wick follows a precursor that closed with the trade (a down-close for the short)
    pp = replace(p, wick_ce_precursor=True)
    ctx3, (sl3, ss3) = mkctx([(4106.0, 4106.5, 4098.0, 4099.0), (4100.0, 4108.0, 4099.0, 4100.5)], base=4100.0, hist=hist_close(close=4100.0, hi=4130.0, lo=3900.0))
    e3 = ib(ctx3, "09:30") + 1
    assert sm4.wick_ce_entry(ctx3, ss3, dict(sw, ext_i=e3, wce_sent=False), e3, pp, "AM", 1.0, 0.0) is not None
    ctx4, (sl4, ss4) = mkctx([(4098.0, 4106.5, 4097.0, 4105.0), (4100.0, 4108.0, 4099.0, 4100.5)], base=4100.0, hist=hist_close(close=4100.0, hi=4130.0, lo=3900.0))
    assert sm4.wick_ce_entry(ctx4, ss4, dict(sw, ext_i=e3, wce_sent=False), e3, pp, "AM", 1.0, 0.0) is None            # an up-close precursor for the short: no


def test_wick_ce_retrace_no_fvg(cap):
    """042 ~00:33:56: wick_ce_mode "retrace" - after an MSS that left no FVG the sweep candle's wick CE joins the fallback arrays (only there: `_nofvg`), the limit at the CE; without the mode or
    before the no-FVG fallback nothing."""
    p = Params(**BASE, wick_ce_mode="retrace")
    rows = [(4010.0, 4011.0, 4000.0, 4008.0), (4008.0, 4009.0, 4007.0, 4008.5), (4008.5, 4012.0, 4008.0, 4011.0)]
    ctx, (sl, ss) = mkctx(rows, base=4010.0, hist=hist_close(close=4010.0, hi=4130.0, lo=3900.0))
    e = ib(ctx, "09:30")
    sw = dict(session="AM", key="pdl1", name="pdl1", level=4001.0, ext=4000.0, ext_i=e, broke=e + 2, sweep_i=e, smt=None, smt2=None)
    assert SM.array_cands(ctx, sl, sw, e + 2, p, None) == []                                              # not in the normal flow
    sw["_nofvg"] = True
    assert SM.array_cands(ctx, sl, sw, e + 2, p, None) == [(4004.0, 4000.0, "wick_ce")]
    assert SM.array_order(ctx, sl, sw, e + 2, p, "AM", 1.0, None, None) is not None and cap["entry"] == pytest.approx(4004.0)
    assert SM.array_cands(ctx, sl, sw, e + 2, replace(p, wick_ce_mode="close"), None) == []


# --- 34 M5-lasthour-shallowest-unused-array ----------------------------------------------------------------------------------------------------------

def test_shallowest_unused_array_pick(cap, monkeypatch):
    """030 ~00:21:36: after the MSS the arrays of the leg are listed, the ones price already traded back into dropped, the most sensitive (highest) one left is the entry: the VI at 4010 was
    traded into before the MSS and goes, the OB at 4005 (untouched) wins over nothing higher; without the switch the highest (the used VI) wins."""
    rows = [(4003.0, 4004.0, 4000.0, 4002.0), (4002.0, 4005.0, 3999.0, 4004.5), (4004.5, 4009.0, 4003.0, 4008.0), (4008.0, 4015.0, 4009.0, 4014.0), (4014.0, 4015.0, 4007.0, 4010.0),
            (4010.0, 4018.0, 4009.5, 4017.0), (4017.0, 4019.0, 4015.5, 4018.0)]
    ctx, (sl, ss) = mkctx(rows, base=4003.0, hist=hist_close(close=4003.0, hi=4130.0, lo=3900.0))
    e = ib(ctx, "09:30")
    sw = dict(session="AM", key="pdl1", name="pdl1", level=4000.0, ext=3999.0, ext_i=e + 1, broke=e + 5, sweep_i=e + 1, smt=None, smt2=None)
    i = e + 6
    monkeypatch.setattr(S, "_ob_at_low", lambda *a, **k: dict(k=e + 2, j=e + 2, body_top=4005.0, body_low=4003.0, mt=4004.0, hi=4005.5, lo=4002.5))
    monkeypatch.setattr(type(sl), "vis", lambda self, kind="bull": [L.Zone("bull", 4010.0, 4009.0, e + 3, e + 3)])
    p = Params(**BASE, entry_arrays=("ob", "vi"))
    cs = SM.array_cands(ctx, sl, sw, i, p, None)
    assert {x[2] for x in cs} == {"ob", "vi"}
    assert SM.array_order(ctx, sl, sw, i, p, "AM", 1.0, None, None) is not None and cap["entry"] == pytest.approx(4010.0)
    p2 = replace(p, entry_pick="shallowest_unused")
    kept = sm4.unused_cands(ctx, sl, sw, i, p2, None, cs)
    assert [x[2] for x in kept] == ["ob"]
    assert SM.array_order(ctx, sl, sw, i, p2, "AM", 1.0, None, None) is not None and cap["entry"] == pytest.approx(4005.0)


# --- 35 new-nwog-edge-to-ce-cookie-cutter ------------------------------------------------------------------------------------------------------------

def test_nwog_edge_to_ce():
    """030 ~01:09:40: the NWOG far edge is a sweep pool (only with the switch; NDOGs excluded), the target is the NWOG CE less exit_before_pts, at least 5 pts of room, not on a choppy day."""
    p = Params(**BASE, nwog_edge_ce=True)
    rows = [(4092.0, 4093.0, 4090.0, 4091.0)] * 6
    ctx, (sl, ss) = mkctx(rows, base=4092.0, hist=hist_close(close=4092.0, hi=4130.0, lo=3900.0))
    ctx.gaps = [("nwog", 4100.0, 4090.0, 4095.0), ("ndog", 4120.0, 4110.0, 4115.0)]
    i = ib(ctx, "09:30") + 5
    out = S._sell_side(ctx, sl, "AM", i, True, p)
    assert out.get("gap_nwog0") == pytest.approx(4090.0) and not any(k.startswith("gap_ndog") for k in out)
    assert not any(k.startswith("gap_") for k in S._sell_side(ctx, sl, "AM", i, True, replace(p, nwog_edge_ce=False)))
    assert sm4.nwog_ce_for_key(ctx, sl, i, "gap_nwog0") == pytest.approx(4095.0)
    sw = dict(session="AM", key="gap_nwog0", ext=4089.0, ext_i=i - 1, level=4090.0, broke=i)
    tags = {}
    assert sm4.nwog_edge_adjust(ctx, sl, sw, i, p, 4088.0, tags) is None and tags["fixed4"] == [(4095.0 - p.exit_before_pts * p.es_pt, "array")]
    assert sm4.nwog_edge_adjust(ctx, sl, sw, i, p, 4091.0, {}) == "x_nwog_edge_room"                      # only 3.5 pts to the CE
    ctx.chop = SimpleNamespace(active_before=lambda k: True)
    assert sm4.nwog_edge_adjust(ctx, sl, sw, i, p, 4088.0, {}) == "x_nwog_edge_chop"
    assert sm4.nwog_edge_adjust(ctx, sl, dict(sw, key="pdl1"), i, p, 4088.0, {}) is None                  # other pools are untouched


# --- 36 M8-short-after-reprice-to-prior-close -----------------------------------------------------------------------------------------------------------

def test_org_fill_then_short():
    """030 ~01:47:48 (gap down, the short; side space mirrored): the prior close (4020) above the 09:30 open (4000) is the ORG far edge - with the switch it is a sweep pool of the short Side (and
    not of the long); a sweep of it targets the session extreme, entries only before 12:00."""
    p = Params(**BASE, org_fill_reverse=True)
    rows = [(4000.0, 4001.0, 3990.0, 3995.0)] * 4 + [(3995.0, 4021.0, 3994.0, 4018.0)]
    ctx, (sl, ss) = mkctx(rows, base=4000.0, hist=hist_close(close=4000.0, hi=4130.0, lo=3900.0))
    ctx.org, ctx.org_today = [(4020.0, 4000.0)], True
    i = ib(ctx, "09:30") + 4
    out = S._sell_side(ctx, ss, "AM", i, True, p)
    assert out.get("org_close") == pytest.approx(-4020.0)
    assert "org_close" not in S._sell_side(ctx, sl, "AM", i, True, p)
    assert "org_close" not in S._sell_side(ctx, ss, "AM", i, True, replace(p, org_fill_reverse=False))
    sw = dict(session="AM", key="org_close", ext=-4021.0, ext_i=i, level=-4020.0, broke=i + 1)
    tags = {}
    ss_hi = float(ss.h[ib(ctx, "09:30"):i + 1].max())
    assert sm4.org_reverse_adjust(ctx, ss, sw, i, p, -4019.0, tags) is None
    assert tags.get("fixed4") is None or tags["fixed4"][0][0] == pytest.approx(S._exit_px(ss_hi, "pool", p))
    assert sm4.org_reverse_adjust(ctx, ss, dict(sw, key="pdl1"), i, p, -4019.0, {}) is None
    ctx_late, (_, ss_late) = mkctx([(4000.0, 4001.0, 3990.0, 3995.0)] * 4 + [(3995.0, 4021.0, 3994.0, 4018.0)], base=4000.0, start="12:10", hist=hist_close(close=4000.0, hi=4130.0, lo=3900.0))
    assert sm4.org_reverse_adjust(ctx_late, ss_late, sw, ib(ctx_late, "12:10") + 4, p, -4019.0, {}) == "x_org_fill_late"


# --- 37 A12-entry-array-at-key-level ----------------------------------------------------------------------------------------------------------------------

def test_ob_at_key_level(monkeypatch):
    """032 ~00:21:34: the OB candle's extreme must lie within ob_key_ticks (2 ticks = 0.5 pt) of a key level - here the NWOG low 4090 (and its CE / high, ORG edges, the session pools): an OB low of
    4090.4 is at the level (tag), 4092 is mid-leg (require drops it); with no OB the sweep extreme stands in."""
    p = Params(**BASE, ob_at_key="tag")
    rows = [(4092.0, 4093.0, 4090.0, 4091.0)] * 6
    ctx, (sl, ss) = mkctx(rows, base=4092.0, hist=hist_close(close=4092.0, hi=4130.0, lo=3900.0))
    ctx.gaps = [("nwog", 4100.0, 4090.0, 4095.0)]
    i = ib(ctx, "09:30") + 5
    sw = dict(session="AM", key="pdl1", ext=4090.2, ext_i=i - 2, level=4091.0, broke=i - 1)
    monkeypatch.setattr(S, "_ob_at_low", lambda *a, **k: dict(k=i - 2, lo=4090.4, body_low=4091.0, body_top=4092.0, mt=4091.5, hi=4092.5, j=i - 2))
    lvt = []
    assert sm4.ob_key_gate(ctx, sl, sw, i, p, "AM", lvt) is None and "ob_at_key" in lvt
    monkeypatch.setattr(S, "_ob_at_low", lambda *a, **k: dict(k=i - 2, lo=4097.5, body_low=4098.0, body_top=4098.5, mt=4098.2, hi=4099.0, j=i - 2))
    lvt2 = []
    assert sm4.ob_key_gate(ctx, sl, sw, i, p, "AM", lvt2) is None and "ob_at_key" not in lvt2
    assert sm4.ob_key_gate(ctx, sl, sw, i, replace(p, ob_at_key="require"), "AM", []) == "x_ob_key"
    monkeypatch.setattr(S, "_ob_at_low", lambda *a, **k: None)
    assert sm4.ob_key_gate(ctx, sl, sw, i, replace(p, ob_at_key="require"), "AM", []) is None               # no OB: the sweep extreme 4090.2 is at the level
    assert sm4.ob_key_gate(ctx, sl, dict(sw, ext=4097.5), i, replace(p, ob_at_key="require"), "AM", []) == "x_ob_key"
    assert any(abs(v - 4095.0) < 1e-9 for v in sm4.key_levels(ctx, sl, i, p, "AM"))                         # the CE is a key level too


# --- 39 M4-breaker-needs-fvg-inside -------------------------------------------------------------------------------------------------------------------

def test_breaker_body_close_below_low_cancels():
    """032 ~00:42:02: a breaker / unicorn order carries a cancel on a body close under the breaker candle's far extreme (not its MT) and an exit on the same close once filled; other orders and the
    default are untouched; an existing higher cancel level stays."""
    p = Params(**BASE, breaker_low_invalidate=True)
    sd = sd_of([(10.0, 11.0, 9.0, 10.0)] * 3)
    tags, lvx = dict(entry_kind="breaker", bz_side=(4010.0, 4000.0)), {}
    sm4.breaker_low_guard(sd, tags, lvx)
    assert lvx["breaker_low"] == (4000.0, False) and tags["cancel_close"] == 4000.0
    tags2, lvx2 = dict(entry_kind="fvg", unicorn=True, bz_top=4010.0, bz_bottom=4001.0, cancel_close=4005.0), {}
    sm4.breaker_low_guard(sd, tags2, lvx2)
    assert lvx2["breaker_low"] == (4001.0, False) and tags2["cancel_close"] == 4001.0
    tags3, lvx3 = dict(entry_kind="fvg"), {}
    sm4.breaker_low_guard(sd, tags3, lvx3)
    assert not lvx3 and "cancel_close" not in tags3
    ctx, (sl, _) = mkctx([(4010.0, 4011.0, 4009.0, 4010.0)] * 3, base=4010.0, hist=hist_close(close=4010.0, hi=4130.0, lo=3900.0))
    sw = dict(session="AM", key="pdl1", ext=4000.0, ext_i=ib(ctx, "09:30"), level=4001.0, broke=ib(ctx, "09:30") + 1)
    t4, x4 = dict(entry_kind="breaker", bz_side=(4010.0, 4000.0)), {}
    assert sm4.order_gate4(ctx, sl, sw, ib(ctx, "09:30") + 2, p, 4008.0, 3999.0, "AM", [], x4, t4) is None and x4["breaker_low"] == (4000.0, False)
    t5, x5 = dict(entry_kind="breaker", bz_side=(4010.0, 4000.0)), {}
    assert sm4.order_gate4(ctx, sl, sw, ib(ctx, "09:30") + 2, replace(p, breaker_low_invalidate=False), 4008.0, 3999.0, "AM", [], x5, t5) is None and not x5


# --- 40 A13-breaker-inversion-against ---------------------------------------------------------------------------------------------------------------

BRK_ROWS = [(4012.0, 4013.0, 4010.0, 4011.0), (4011.0, 4012.0, 4004.0, 4005.0), (4005.0, 4016.0, 4008.0, 4015.0), (4015.0, 4022.0, 4014.0, 4021.0), (4021.0, 4021.5, 4003.0, 4004.0),
            (4004.0, 4012.0, 4003.5, 4011.0), (4011.0, 4025.0, 4010.0, 4024.0)]


def test_breaker_blocks_counter_shorts():
    """033 ~00:49:43: a bullish breaker (zone 4014-4022, formed on the 15:... bar 6) that holds on a body-close basis blocks the shorts; the long side is free; off = nothing."""
    p = Params(**BASE, breaker_block_counter=True)
    ctx, (sl, ss) = mkctx(BRK_ROWS, base=4012.0, hist=hist_close(close=4012.0, hi=4130.0, lo=3900.0))
    i = ib(ctx, "09:30") + 6
    own = sm4._own_breakers(ctx, sl, i, p)
    assert own is not None and (own[0].top, own[0].bottom) == (4022.0, 4014.0) and own[2] is None
    assert sm4.breaker_counter_gate(ctx, ss, i, p, "AM") == "x_breaker_counter"
    assert sm4.breaker_counter_gate(ctx, sl, i, p, "AM") is None
    sw = dict(session="AM", key="pdh1", ext=-4030.0, ext_i=i - 1, level=-4025.0, broke=i)
    assert sm4.order_gate4(ctx, ss, sw, i, p, -4020.0, -4025.0, "AM", [], {}, {}) == "x_breaker_counter"
    assert sm4.order_gate4(ctx, ss, sw, i, replace(p, breaker_block_counter=False), -4020.0, -4025.0, "AM", [], {}, {}) is None


def test_breaker_inversion_stands_aside():
    """048 ~01:54:11: a body close under the breaker (4012 < 4014) inverts it: the longs are blocked for the session and the shorts wait (no automatic reversal) until price retraces into the zone and
    a bar closes back under it; then the counter side may trade."""
    p = Params(**BASE, breaker_block_counter=True)
    inv = BRK_ROWS + [(4024.0, 4024.0, 4010.0, 4012.0)]
    ret = inv + [(4012.0, 4015.0, 4011.0, 4013.0)]
    rej = ret + [(4013.0, 4013.5, 4009.0, 4010.0)]
    res = []
    for rows in (inv, ret, rej):
        ctx, (sl, ss) = mkctx(rows, base=4012.0, hist=hist_close(close=4012.0, hi=4130.0, lo=3900.0))
        i = ib(ctx, "09:30") + len(rows) - 1
        res.append((sm4.breaker_counter_gate(ctx, sl, i, p, "AM"), sm4.breaker_counter_gate(ctx, ss, i, p, "AM")))
    assert res == [("x_breaker_inverted", "x_breaker_counter"), ("x_breaker_inverted", "x_breaker_counter"), ("x_breaker_inverted", None)]


# --- 43 new-sweep-wick-ce-failure-swing-long -----------------------------------------------------------------------------------------------------------

def test_15m_sweep_wick_ce_long(cap):
    """038 ~00:50:59: the 15m sweep candle (low 4000, body low 4005: CE 4002.5), price bounces (closes above the CE), later a bar retraces to within a tick of the CE with the sweep low intact: a limit
    at the CE, the stop under the sweep low, cancelled by a trade under it; not on an FOMC day, not for an array premise, not after the sweep low traded."""
    p = Params(**BASE, wick_ce_entries=True, wick_ce_tf=15)
    rows = [(4010.0, 4011.0, 4009.0, 4010.0), (4010.0, 4010.5, 4000.0, 4001.0), (4001.0, 4006.0, 4000.5, 4005.0), (4005.0, 4012.0, 4004.5, 4011.0), (4011.0, 4012.0, 4010.0, 4011.5),
            (4011.5, 4012.0, 4002.7, 4003.0)]
    ctx, (sl, ss) = mkctx(rows, base=4010.0, hist=hist_close(close=4010.0, hi=4130.0, lo=3900.0))
    e = ib(ctx, "09:30")
    sw = dict(session="AM", key="rel_eq_lows0", name="rel_eq_lows", level=4002.0, ext=4000.0, ext_i=e + 1, broke=None, sweep_i=e + 1, smt=None, smt2=None)
    i = e + 5
    assert sm4.wick_ce_entry(ctx, sl, sw, i, p, "AM", 1.0, 0.0) is not None
    assert cap["entry"] == pytest.approx(4002.5) and cap["stop"] == pytest.approx(4000.0 - p.pad) and cap["tags"]["cancel_low"] == 4000.0 and sw["wce_sent"]
    assert sm4.wick_ce_entry(ctx, sl, sw, i, p, "AM", 1.0, 0.0) is None                                   # once
    assert sm4.wick_ce_entry(ctx, sl, dict(sw, wce_sent=False, key="htf_array"), i, p, "AM", 1.0, 0.0) is None
    assert sm4.wick_ce_entry(ctx, sl, dict(sw, wce_sent=False, key="htf_array"), i, replace(p, wick_ce_need_pool=False), "AM", 1.0, 0.0) is not None
    assert sm4.wick_ce_entry(ctx, sl, dict(sw, wce_sent=False), i - 1, p, "AM", 1.0, 0.0) is None          # no retrace to the CE yet
    ctx_f, (sl_f, _) = mkctx(rows, base=4010.0, d=date(2026, 6, 17), hist=hist_close(d=date(2026, 6, 17), close=4010.0, hi=4130.0, lo=3900.0))
    assert sm4.wick_ce_entry(ctx_f, sl_f, dict(sw, wce_sent=False), i, p, "AM", 1.0, 0.0) is None          # FOMC
    low = rows[:5] + [(4011.5, 4012.0, 3999.0, 4003.0)]
    ctx_l, (sl_l, _) = mkctx(low, base=4010.0, hist=hist_close(close=4010.0, hi=4130.0, lo=3900.0))
    assert sm4.wick_ce_entry(ctx_l, sl_l, dict(sw, wce_sent=False), i, p, "AM", 1.0, 0.0) is None          # the sweep low traded back: no failure swing


# --- 47 M16-sick-sister-ob-open-entry / 56 M16-sick-sister-discount-confluence ----------------------------------------------------------------------------

def _sisters(me_rows, partner_rows=None, me_hist_hi=4110.0, partner_hist_hi=4095.0, base=4100.0):
    """Two instruments of one day: ours (previous-day highs 4110, untaken) and the partner's (previous-day highs 4095, taken in the pre-market): the partner made the higher high, we are the sick sister."""
    ctx, sides = mkctx(me_rows, base=base, hist=hist_close(close=min(base, me_hist_hi - 5.0), hi=me_hist_hi, lo=3900.0))
    pctx, psides = mkctx(partner_rows or me_rows, base=base, hist=hist_close(close=min(base, partner_hist_hi - 5.0), hi=partner_hist_hi, lo=3900.0))
    ppos = pd.Series(np.arange(len(pctx.idx)), index=pctx.idx)
    ctx.pside = (pctx, {1: psides[0], -1: psides[1]}, ppos)
    return ctx, sides


def test_sick_sister_ob_open(cap):
    """045 ~01:41:00: the partner index took the previous-day high (4095) that we (the laggard, previous-day high 4110) did not: the first down-close bar of ours arms a buy limit at that bar's open
    (4104), the stop under its low, the target the matching old high (4110); one per session; an index that is not the sick one gets nothing; an up-close bar gets nothing."""
    p = Params(**BASE, sick_entry="ob_open")
    rows = [(4101.0, 4103.0, 4100.5, 4102.5), (4104.0, 4104.5, 4101.0, 4102.0)]
    ctx, (sl, ss) = _sisters(rows)
    i = ib(ctx, "09:30") + 1
    assert sm4.sick_ob_open_order(ctx, sl, i, p, "AM", 1.0) is not None
    assert cap["entry"] == pytest.approx(4104.0) and cap["stop"] == pytest.approx(4101.0 - p.pad) and cap["fixed"] == [(S._exit_px(4110.0, "pool", p), "pool")]
    assert sm4.sick_ob_open_order(ctx, sl, i, p, "AM", 1.0) is None                                      # once a session
    sl.__dict__.pop("_sickob_sent")
    assert sm4.sick_ob_open_order(ctx, sl, ib(ctx, "09:30"), p, "AM", 1.0) is None                      # an up-close bar
    ctx2, (sl2, _) = _sisters(rows, me_hist_hi=4095.0)
    assert sm4.sick_ob_open_order(ctx2, sl2, i, p, "AM", 1.0) is None                                    # we took the same highs: not the sick sister
    ctx3, (sl3, _) = _sisters(rows)
    ctx3.pside = None
    assert sm4.sick_ob_open_order(ctx3, sl3, i, p, "AM", 1.0) is None                                    # no partner data


def test_sick_sister_ote_ob_fvg_overlap(cap):
    """053 ~00:05:17, ~00:10:51 (consolidation only): the leg from the day's swing low (4090) to the high the laggard failed to exceed (4108): the OTE band 4093.78-4096.84 overlaps the bullish OB
    (the down-close series 4090-4099) and the FVG (4095-4097): the entry zone 4095-4096.84; price below the EQ and not rallying; up to sick_units limits spread over the zone; the target the
    buy-side the sister took; with a bias the setup stays out."""
    p = Params(**BASE, sick_entry="ote_stack", sick_units=2)
    rows = [(4098.0, 4099.0, 4093.0, 4094.0), (4094.0, 4095.0, 4090.0, 4091.0), (4091.0, 4101.0, 4090.9, 4100.0), (4100.0, 4108.0, 4097.0, 4107.0), (4107.0, 4108.0, 4100.0, 4101.0),
            (4101.0, 4101.5, 4098.0, 4098.5)]
    ctx, (sl, ss) = _sisters(rows)
    i = ib(ctx, "09:30") + 5
    assert sm4.sick_ote_stack_order(ctx, sl, i, p, "AM", 1.0) is not None
    assert cap["entry"] == pytest.approx(4096.84) and cap["tags"]["ladder"] == [pytest.approx(4096.84), pytest.approx(4095.0)] and cap["stop"] == pytest.approx(4095.0 - p.pad)
    assert cap["fixed"] == [(S._exit_px(4100.1, "pool", p), "pool")]                                    # the matching old high: the previous PM high the partner took
    assert sm4.sick_ote_stack_order(ctx, sl, i, p, "AM", 1.0) is None                                    # once per zone
    sl.__dict__.pop("_sickote_sent")
    ctx.cur_bias = 1
    assert sm4.sick_ote_stack_order(ctx, sl, i, p, "AM", 1.0) is None                                    # not a consolidating market
    ctx.cur_bias = 0
    one = replace(p, sick_units=1)
    assert sm4.sick_ote_stack_order(ctx, sl, i, one, "AM", 1.0) is not None and "ladder" not in cap["tags"]
    ctx2, (sl2, _) = _sisters(rows[:5] + [(4101.0, 4106.0, 4100.5, 4105.5)])
    assert sm4.sick_ote_stack_order(ctx2, sl2, ib(ctx2, "09:30") + 5, p, "AM", 1.0) is None              # above the EQ (4099)


# --- 48 new-lunch-macro-long-nwog ---------------------------------------------------------------------------------------------------------------------

def test_lunch_nwog_long(cap):
    """046 ~02:07:16 (experimental): after a down AM, 11:45, price (4093) inside [the NWOG low 4090, the NWOG CE 4095] with nothing traded under the low: a limit at / under the CE with the stop
    under the NWOG low (session LUNCH, out by 13:30); the run_day hook (special4) arms it in the window only, once, with the switch; a break of the NWOG low = nothing."""
    p = Params(**BASE, lunch_nwog_long=True)
    rows = [(4110.0 - k * 0.63, 4110.5 - k * 0.63, 4109.0 - k * 0.63, 4109.4 - k * 0.63) for k in range(28)]
    ctx, sides = mkctx(rows, base=4110.0, hist=hist_close(close=4110.0, hi=4130.0, lo=3900.0))
    ctx.gaps = [("nwog", 4100.0, 4090.0, 4095.0)]
    i = ib(ctx, "11:45")
    assert ctx.c[i] < 4095.0
    assert sm4.lunch_nwog_order(ctx, sides[0], i, p, 1.0) is not None
    assert cap["entry"] <= 4095.0 and cap["entry"] > 4090.0 and cap["stop"] == pytest.approx(4090.0 - p.pad) and cap["session"] == "LUNCH" and cap["tags"]["exit_at"] == 810
    assert sm4.lunch_nwog_order(ctx, sides[0], i, p, 1.0) is None                                        # once per NWOG
    assert sm4.lunch_nwog_order(ctx, sides[0], ib(ctx, "12:15"), p, 1.0) is None                         # the window ends at 12:10
    sides[0].__dict__.pop("_lnw_sent")
    state, done = {}, {}
    o = sm4.special4(ctx, sides, i, p, state, None, None, 1.0, done)
    assert o is not None and o["done_key"] == "LNW" and "lnw" in state["sm4_sent"]
    assert sm4.special4(ctx, sides, i, p, state, None, None, 1.0, done) is None                           # once a day
    assert sm4.special4(ctx, sides, i, replace(p, lunch_nwog_long=False), {}, None, None, 1.0, {}) is None
    assert sm4.special4(ctx, sides, i, p, {}, "pos", None, 1.0, {}) is None                               # a position is open
    low = rows[:20] + [(4097.0, 4097.5, 4089.0, 4097.0)] + rows[21:]
    ctx2, sides2 = mkctx(low, base=4110.0, hist=hist_close(close=4110.0, hi=4130.0, lo=3900.0))
    ctx2.gaps = [("nwog", 4100.0, 4090.0, 4095.0)]
    assert sm4.lunch_nwog_order(ctx2, sides2[0], i, p, 1.0) is None                                      # price traded under the NWOG low


# --- 49 A8-symmetry-skip-ifvg-confirmation ----------------------------------------------------------------------------------------------------------------

def test_ifvg_skipped_when_symmetric(monkeypatch):
    """048 ~00:38:07: when both indices printed the same higher high in the window (no SMT) the inversion steps (ifvg_hold) are skipped and an opposing FVG of the leg is a buy-inside zone; with a
    diverging partner (it did not take the high) the full A8 protocol holds."""
    p = Params(**BASE, ifvg_entries=True, ifvg_symmetry_skip=True, ifvg_hold=True, ifvg_sym_bars=3)
    up = [(4000.0, 4002.0, 3999.0, 4001.0), (4001.0, 4010.0, 4000.5, 4009.0), (4009.0, 4011.0, 4005.0, 4010.0)] + [(4010.0, 4012.0, 4009.0, 4011.0)] * 4
    ctx, (sl, ss) = _sisters(up, up, base=4000.0)
    i = ib(ctx, "09:30") + 6
    assert sm4.symmetric(ctx, sl, i, p) is True
    div = [(4000.0, 4002.0, 3999.0, 4001.0), (4001.0, 4010.0, 4000.5, 4009.0), (4009.0, 4011.0, 4005.0, 4010.0)] + [(4010.0, 4009.0, 4008.0, 4008.5)] * 4
    ctx2, (sl2, _) = _sisters(up, div, base=4000.0)
    assert sm4.symmetric(ctx2, sl2, i, p) is False                                                       # the partner did not make the high with us
    g_native = sl.gaps[0]
    inv = L.Zone("bull", 4005.0, 4003.0, 2, 1)
    sw = dict(session="AM", ext=3999.0, ext_i=0, key="x")
    sl._lz.pop("implied", None)
    assert inv in SM.ifvg_filter(ctx, sl, sw, [g_native, inv], i, p)                                       # symmetric: kept although a close sits under its top
    assert inv not in SM.ifvg_filter(ctx2, sl2, sw, [sl2.gaps[0], inv], i, p)                              # diverging: the hold test drops it (closes under 4005 after it formed? none -> use a low close)
    # the opposing FVG zones of the leg: a bearish FVG formed after the sweep with the market already at it
    bear = sd_of([(10.0, 10.5, 9.5, 10.0), (10.0, 11.0, 9.8, 10.8), (10.8, 10.9, 10.2, 10.3), (10.3, 10.4, 9.0, 9.2), (9.2, 9.8, 8.0, 9.5), (9.5, 9.9, 9.4, 9.8)])
    zs = sm4.sym_zones(ctx, bear, dict(ext_i=0), 5, p)
    assert all(z.kind == "bull" for z in zs)


# --- 50 A8-ifvg-5m-to-1m-handoff -------------------------------------------------------------------------------------------------------------------------

def test_ifvg_5m_ref_1m_confirm():
    """048 ~00:21:30: ifvg_tf = 5 - the reference gap is the 5m SIBI (4015-4018). Ideal: a 5m candle CLOSES above it and the next 5m candle trades back into it and holds -> the inversion zone is
    known at that candle. If a 5m candle only trades above it (no close) the base-bar checks run: a body close above, a NEW candle opening above and trading back into it, a hold."""
    p = Params(**BASE, ifvg_entries=True, ifvg_tf=5)
    ideal = [(4020.0, 4021.0, 4018.0, 4019.0), (4019.0, 4019.5, 4010.0, 4011.0), (4011.0, 4015.0, 4009.0, 4014.0), (4014.0, 4020.0, 4013.5, 4019.0), (4019.0, 4019.5, 4017.5, 4018.6)]
    ctx, (sl, ss) = mkctx(ideal, base=4020.0, hist=hist_close(close=4020.0, hi=4130.0, lo=3900.0))
    i = ib(ctx, "09:30") + 4
    sw = dict(session="AM", ext=4009.0, ext_i=ib(ctx, "09:30") + 2, key="x")
    zs = sm4.ifvg_tf_zones(ctx, sl, dict(sw, ext_i=ib(ctx, "09:30")), i, p)
    assert len(zs) == 1 and (zs[0].top, zs[0].bottom, zs[0].kind) == (4018.0, 4015.0, "bull") and zs[0].i == i
    zs2 = sm4.ifvg_tf_zones(ctx, sl, dict(sw, ext_i=ib(ctx, "09:30")), i - 1, p)
    assert zs2 == []                                                                                      # before the retrace candle closed there is no inversion
    # the 1m hand-off: the 5m candle only traded above the gap (wick); a later body close above, then a new candle opening above and trading back in
    wick = [(4020.0, 4021.0, 4018.0, 4019.0), (4019.0, 4019.5, 4010.0, 4011.0), (4011.0, 4015.0, 4009.0, 4014.0), (4014.0, 4018.5, 4013.5, 4017.0), (4017.0, 4019.5, 4016.8, 4019.2),
            (4019.4, 4020.0, 4017.8, 4019.0)]
    ctx2, (sl2, _) = mkctx(wick, base=4020.0, hist=hist_close(close=4020.0, hi=4130.0, lo=3900.0))
    zs3 = sm4.ifvg_tf_zones(ctx2, sl2, dict(sw, ext_i=ib(ctx2, "09:30")), ib(ctx2, "09:30") + 5, p)
    assert len(zs3) == 1 and zs3[0].i == ib(ctx2, "09:30") + 5
    close_under = wick[:5] + [(4019.4, 4020.0, 4014.0, 4014.5)]
    ctx3, (sl3, _) = mkctx(close_under, base=4020.0, hist=hist_close(close=4020.0, hi=4130.0, lo=3900.0))
    assert sm4.ifvg_tf_zones(ctx3, sl3, dict(sw, ext_i=ib(ctx3, "09:30")), ib(ctx3, "09:30") + 5, p) == []   # no hold: a body closed back through the gap


# --- 53 new-short-top-of-htf-discount-fvg --------------------------------------------------------------------------------------------------------------

def _top_rows():
    k = 8104.0
    brk = [(4012.0, 4013.0, 4010.0, 4011.0), (4011.0, 4012.0, 4004.0, 4005.0), (4005.0, 4016.0, 4008.0, 4015.0), (4015.0, 4018.0, 4014.0, 4017.0), (4017.0, 4017.5, 4003.0, 4004.0),
           (4004.0, 4012.0, 4003.5, 4011.0), (4011.0, 4025.0, 4010.0, 4024.0), (4024.0, 4027.0, 4023.0, 4026.0), (4026.0, 4026.5, 4020.0, 4021.0)]
    return [(k - o, k - l, k - h, k - c) for o, h, l, c in brk]


def test_short_top_of_daily_bisi(cap):
    """050 ~00:51:08: bias -1; the top (4090) of a bullish daily FVG (4075-4090) was traded today; a 5m bearish breaker (4086-4090) touches it: a sell limit at the breaker's lower edge (4086), the
    stop over it, the target 1 pt beyond the nearest swing inside the FVG (never past its far edge), out by 12:00; no bias, a daily FVG top not yet traded, or an expired window gives nothing."""
    p = Params(**BASE, htf_fvg_top_short=True)
    rows = _top_rows()
    conf = StubConf(arrays={1: [(4090.0, 4075.0, "D", 0, 0)]})
    ctx, (sl, ss) = mkctx(rows, base=4096.0, bias=-1, conf=conf, hist=hist_close(close=4096.0, hi=4130.0, lo=3900.0))
    i = ib(ctx, "09:30") + len(rows) - 1
    assert sm4.top_short_order(ctx, ss, i, p, "AM", 1.0) is not None
    assert cap["entry"] == pytest.approx(-4086.0) and cap["stop"] == pytest.approx(-4090.0 - p.pad) and cap["tags"]["exit_at"] == 720
    assert cap["fixed"][0][0] == pytest.approx(-4076.0) and cap["fixed"][0][0] > cap["entry"]
    assert sm4.top_short_order(ctx, ss, i, p, "AM", 1.0) is None                                          # once per breaker
    ss.__dict__.pop("_top_sent")
    ctx.cur_bias = 0
    assert sm4.top_short_order(ctx, ss, i, p, "AM", 1.0) is None                                          # no bias
    ctx.cur_bias = -1
    far = StubConf(arrays={1: [(4140.0, 4130.0, "D", 0, 0)]})
    ctx.conf = far
    assert sm4.top_short_order(ctx, ss, i, p, "AM", 1.0) is None                                          # that FVG's top was never traded today
    ctx.conf = conf
    assert sm4.top_short_order(ctx, sl, i, p, "AM", 1.0) is None                                          # the long Side: bias is -1


# --- 54 new-ndog-asian-scalp ----------------------------------------------------------------------------------------------------------------------------

def _evening(rows):
    """The first row is the 16:55 bar (the 17:00 close), the rest are the bars from the 18:00 reopen."""
    idx = pd.DatetimeIndex([pd.Timestamp(f"{D0} 16:55", tz=NY)]).append(pd.date_range(pd.Timestamp(f"{D0} 18:00", tz=NY), periods=len(rows) - 1, freq="5min"))
    a = np.array(rows, float)
    return pd.DataFrame({"open": a[:, 0], "high": a[:, 1], "low": a[:, 2], "close": a[:, 3], "volume": 1.0}, index=idx)


def test_ndog_asian_scalp():
    """052 ~00:08:18: the 17:00 close 4100, the 18:00 reopen 4095 (a gap down of 5 pts, the NDOG high 4100 untraded): the first 5m close back above the NDOG low after trading at it is a market long
    (filled at the next open), the stop under the post-open low, the target the NDOG high less exit_before_pts, flat at midnight; the gap up is the mirror; a gap of a handle or less, the NDOG high
    traded first, or a trade-through of the low (a body close under it before the trigger) gives nothing."""
    p = Params(**BASE, ndog_scalp=True)
    ctx = SimpleNamespace(equity=100000.0, tf=5)
    rows = [(4100.0, 4100.5, 4099.5, 4100.0), (4095.0, 4096.0, 4094.0, 4095.5), (4095.5, 4097.0, 4095.2, 4096.5), (4096.5, 4098.0, 4096.0, 4097.5), (4097.5, 4100.0, 4097.0, 4099.8)]
    ev = _evening(rows)
    tt = ev.index.hour * 60 + ev.index.minute
    assert list(tt) == [1015, 1080, 1085, 1090, 1095]
    out = sm4.ndog_scalp(ctx, ev, p, D0, "ES", {})
    assert len(out) == 1
    tr = out[0]
    assert tr.side == "long" and tr.session == "ASIA" and tr.entry == pytest.approx(4096.5) and tr.stop == pytest.approx(4094.0 - p.pad) and tr.t1 == pytest.approx(4100.0 - p.exit_before_pts)
    assert tr.exits[-1][3] == "t1" and tr.exits[-1][1] == pytest.approx(4099.5) and tr.final_hit and tr.entry_time == ev.index[3]
    up = [(4100.0, 4100.5, 4099.5, 4100.0), (4105.0, 4106.0, 4104.0, 4104.5), (4104.5, 4104.8, 4103.0, 4103.5), (4103.5, 4104.0, 4102.0, 4102.5), (4102.5, 4103.0, 4100.2, 4100.4)]
    s = sm4.ndog_scalp(ctx, _evening(up), p, D0, "ES", {})
    assert len(s) == 1 and s[0].side == "short" and s[0].entry == pytest.approx(4103.5)
    small = [(4100.0, 4100.5, 4099.5, 4100.0), (4099.5, 4099.8, 4098.9, 4099.4)] + rows[2:]
    assert sm4.ndog_scalp(ctx, _evening(small), p, D0, "ES", {}) == []                                   # a gap of half a point
    first = [rows[0], (4095.0, 4101.0, 4094.0, 4095.5)] + rows[2:]
    assert sm4.ndog_scalp(ctx, _evening(first), p, D0, "ES", {}) == []                                   # the NDOG high traded first
    below = [rows[0], (4095.0, 4096.0, 4094.0, 4095.5), (4095.5, 4095.8, 4093.0, 4094.0), (4094.0, 4096.0, 4093.5, 4095.9), (4095.9, 4100.5, 4095.5, 4100.2)]
    assert sm4.ndog_scalp(ctx, _evening(below), p, D0, "ES", {}) == []                     # (a close under the low resets the touch; the last bar then trades the NDOG high first)
    assert sm4.ndog_scalp(ctx, ev.iloc[:0], p, D0, "ES", {}) == []
    pe = sm4.post_evening(pd.concat([ev]), D0)
    assert len(pe) == len(ev) and pe.index.max() < pd.Timestamp(D0, tz=NY) + pd.Timedelta(days=1)
    short_ev = ev.iloc[:3]
    assert sm4.ndog_scalp(ctx, short_ev, p, D0, "ES", {}) == []                                           # not triggered yet by the bars known so far


# --- 55 M16-trending-divergence-continuation -----------------------------------------------------------------------------------------------------------

def test_smt_ignored_on_trend_day(monkeypatch):
    """053 ~00:08:20: a trending day = the bias and the locked draw this way, the session's first MSS went this way, no opposing HTF premium array reached: then an SMT against the trend blocks
    nothing and the sick sister needs no deep discount; a bear MSS first, a reached premium array, another lock side or no lock = not a trend day."""
    rows = [(4000.0, 4002.0, 3999.0, 4001.0), (4001.0, 4005.0, 4000.5, 4004.0), (4004.0, 4004.5, 4002.0, 4003.0), (4003.0, 4008.0, 4002.8, 4007.0), (4007.0, 4009.0, 4006.0, 4008.0)]
    p = Params(**BASE, smt_trend_ignore=True)
    ctx, (sl, ss) = mkctx(rows, base=4000.0, bias=1, conf=StubConf(), hist=hist_close(close=4000.0, hi=4130.0, lo=3900.0))
    ctx.cur_lock, ctx.cur_session = dict(side=1, target=4040.0), "AM"
    i = ib(ctx, "09:30") + 4
    assert sm4.trend_day(ctx, sl, i, p) is True
    ctx.cur_lock = dict(side=-1, target=3950.0)
    assert sm4.trend_day(ctx, sl, i, p) is False
    ctx.cur_lock = None
    assert sm4.trend_day(ctx, sl, i, p) is False
    ctx.cur_lock = dict(side=1, target=4040.0)
    ctx.conf = StubConf()
    monkeypatch.setattr(StubConf, "opposing", lambda self, *a, **k: [(4007.0, 4010.0, 4012.0, "4h", 0)])
    assert sm4.trend_day(ctx, sl, i, p) is False                                                          # a 4h premium array was reached (its near edge 4007 <= the day's high 4009)
    monkeypatch.undo()
    down = [(4000.0, 4001.0, 3997.0, 3998.0), (3998.0, 3999.0, 3993.0, 3994.0), (3994.0, 3996.0, 3993.5, 3995.0), (3995.0, 3995.5, 3990.0, 3991.0), (3991.0, 3992.0, 3990.5, 3991.5)]
    ctx2, (sl2, _) = mkctx(down, base=4000.0, bias=1, conf=StubConf(), hist=hist_close(close=4000.0, hi=4130.0, lo=3900.0))
    ctx2.cur_lock, ctx2.cur_session = dict(side=1, target=4040.0), "AM"
    assert sm4.trend_day(ctx2, sl2, ib(ctx2, "09:30") + 4, p) is False                                    # the first break went down
    # the sick-sister gate: a shallow entry is out, unless the trend waiver applies
    srows = [(4101.0, 4103.0, 4100.5, 4102.5), (4104.0, 4108.0, 4101.0, 4106.0)]
    ctx3, (sl3, _) = _sisters(srows)
    ps = Params(**BASE, sick_sister=True, smt_trend_ignore=True)
    j = ib(ctx3, "09:30") + 1
    assert SM.sick_sister(ctx3, sl3, j, ps, "AM", 4106.0) is None                                         # near the top of the range: not the deep discount
    monkeypatch.setattr(sm4, "trend_day", lambda *a: True)
    assert SM.sick_sister(ctx3, sl3, j, ps, "AM", 4106.0) is not None                                     # a trending day: no discount needed
    assert SM.sick_sister(ctx3, sl3, j, replace(ps, smt_trend_ignore=False), "AM", 4106.0) is None


# --- 58 M2-three-drives-conditions -------------------------------------------------------------------------------------------------------------------------

TD_ROWS = [(4030.0, 4032.0, 4026.0, 4028.0), (4028.0, 4029.0, 4020.0, 4021.0), (4021.0, 4026.0, 4024.0, 4025.0), (4025.0, 4026.0, 4010.0, 4011.0), (4011.0, 4018.0, 4012.0, 4017.0),
           (4017.0, 4018.0, 4007.0, 4008.0), (4008.0, 4015.0, 4009.0, 4014.0)]


def test_three_drives_scalp_when_htf_up():
    """056 ~00:08:47: three drives down into the sweep (4020, 4010, 4007) is a reversal only with the HTF bias this way or the original-direction objective delivered; otherwise a retracement: one
    exit at the nearest pool (single_exit), no adds, tag td_scalp. (Side space: the long reversal of three drives down; the short mirror of three drives up.)"""
    p = Params(**BASE, three_drives_htf=True)
    ctx, (sl, ss) = mkctx(TD_ROWS, base=4030.0, hist=hist_close(close=4030.0, hi=4130.0, lo=3900.0))
    e = ib(ctx, "09:30") + 5
    i = e + 1
    sw = dict(session="AM", key="pdl1", ext=4007.0, ext_i=e, level=4010.0, broke=i)
    ctx.cur_bias = 0
    tags, lvt = {}, []
    assert sm4.order_gate4(ctx, sl, sw, i, p, 4014.0, 4006.0, "AM", lvt, {}, tags) is None
    assert tags.get("single_exit") and tags.get("no_adds") and "td_scalp" in lvt
    ctx.cur_bias = 1
    tags2, lvt2 = {}, []
    sm4.order_gate4(ctx, sl, sw, i, p, 4014.0, 4006.0, "AM", lvt2, {}, tags2)
    assert not tags2 and "td_reversal" in lvt2                                                            # the HTF bias is this way: a real reversal
    ctx.cur_bias = 0
    ctx.lock = {"AM": dict(side=-1, delivered_i=e, target=4000.0)}
    tags3, lvt3 = {}, []
    sm4.order_gate4(ctx, sl, sw, i, p, 4014.0, 4006.0, "AM", lvt3, {}, tags3)
    assert not tags3 and "td_reversal" in lvt3                                                            # the down objective was delivered
    tags4, lvt4 = {}, []
    sm4.order_gate4(ctx, sl, sw, i, replace(p, three_drives_htf=False), 4014.0, 4006.0, "AM", lvt4, {}, tags4)
    assert not tags4 and not lvt4
    sw_no = dict(sw, ext=3995.0)                                                                           # not three drives (the third drive is longer)
    ctx.lock = {}
    tags5, lvt5 = {}, []
    sm4.order_gate4(ctx, sl, sw_no, i, p, 4014.0, 4006.0, "AM", lvt5, {}, tags5)
    assert not tags5


# --- 59 M4-complete-model-breaker-ote-ob ----------------------------------------------------------------------------------------------------------------

def test_complete_model_tag():
    """056 ~00:12:24: a breaker entry is a `complete_model` when the breaker comes from a parent swing (an ITL / LTL high), its zone lies in the leg's 62-79% band and a down-close candle sits inside
    it; tag mode records it, require drops the breaker entries without it; a plain FVG entry is never touched."""
    rows = [(4010.0, 4011.0, 4000.0, 4006.0), (4006.0, 4009.0, 3999.5, 4007.5), (4007.5, 4020.0, 4007.0, 4019.0), (4019.0, 4020.5, 4015.0, 4018.0)]
    ctx, (sl, ss) = mkctx(rows, base=4010.0, hist=hist_close(close=4010.0, hi=4130.0, lo=3900.0))
    e = ib(ctx, "09:30") + 1
    i = ib(ctx, "09:30") + 3
    sw = dict(session="AM", key="pdl1", ext=3999.5, ext_i=e, level=4000.0, broke=i, ref_i=ib(ctx, "09:30") + 2)
    P = L.Pivot
    sl._lz["tiers"] = {"stl": ([], []), "itl": ([P(sw["ref_i"], 4020.0, i)], []), "ltl": ([], [])}
    tags = dict(entry_kind="breaker", bz_side=(4012.0, 4004.0))
    lvt = []
    assert sm4.complete_model_tag(ctx, sl, sw, i, Params(**BASE, complete_model="tag"), tags, lvt) is True and "complete_model" in lvt
    assert sm4.complete_model_tag(ctx, sl, dict(sw, ref_i=ib(ctx, "09:30")), i, Params(**BASE), dict(tags), []) is False                 # not a parent swing
    assert sm4.complete_model_tag(ctx, sl, sw, i, Params(**BASE), dict(entry_kind="breaker", bz_side=(4030.0, 4025.0)), []) is False        # outside the OTE band
    assert sm4.complete_model_tag(ctx, sl, sw, i, Params(**BASE), dict(entry_kind="breaker", bz_side=(4012.0, 4008.5)), []) is False         # no down-close candle inside
    assert sm4.complete_model_tag(ctx, sl, sw, i, Params(**BASE), dict(entry_kind="fvg"), []) is False                                    # not a breaker entry
    req = Params(**BASE, complete_model="require")
    assert sm4.order_gate4(ctx, sl, sw, i, req, 4008.0, 3999.0, "AM", [], {}, dict(tags)) is None
    assert sm4.order_gate4(ctx, sl, dict(sw, ref_i=ib(ctx, "09:30")), i, req, 4008.0, 3999.0, "AM", [], {}, dict(tags)) == "x_complete_model"
    assert sm4.order_gate4(ctx, sl, dict(sw, ref_i=ib(ctx, "09:30")), i, req, 4008.0, 3999.0, "AM", [], {}, dict(entry_kind="fvg")) is None


# --- 60 M5-lasthour-reversal-into-org --------------------------------------------------------------------------------------------------------------------

def test_lh_org_fill_targets(monkeypatch):
    """059 ~00:24:09: the gap-down ORG (prior close 4020, open 4000) is unfilled all day (the day's high 4003 never reached 4020) and the downside objective was delivered: in the last hour the long
    (toward the ORG) is judged with the ladder [near edge 4000, CE 4010, prior close 4020] (those above the entry), run_day's delivered-draw gate may be bypassed (lh_org_open); a filled ORG, an
    objective not delivered, or outside the last hour = none."""
    p = Params(**BASE, lh_org_fill=True)
    rows = [(4000.0, 4003.0, 3990.0, 3992.0)] * 72
    ctx, (sl, ss) = mkctx(rows, base=4000.0, hist=hist_close(close=4000.0, hi=4130.0, lo=3900.0))
    ctx.org, ctx.org_today = [(4020.0, 4000.0)], True
    ctx.lock = {"AM": dict(side=-1, delivered_i=ctx.start + 10, target=3980.0)}
    i = ib(ctx, "15:05")
    assert sm4.org_fill_ctx(ctx, sl, i, p) == (4000.0, 4010.0, 4020.0)
    assert sm4.org_fill_ctx(ctx, ss, i, p) is None                                                        # the short Side: the ORG is behind it
    assert sm4.lh_org_open(ctx, i, p) is True
    tags = {}
    assert sm4.lh_org_adjust(ctx, sl, dict(key="x"), i, p, "PM", 3995.0, tags) is None
    assert [round(v, 2) for v, k in tags["fixed4"]] == [round(S._exit_px(x, "array", p), 2) for x in (4000.0, 4010.0, 4020.0)]
    tags2 = {}
    assert sm4.lh_org_adjust(ctx, sl, dict(key="x"), i, p, "PM", 4005.0, tags2) is None and len(tags2["fixed4"]) == 2           # the near edge is already behind the entry
    assert sm4.lh_org_adjust(ctx, sl, dict(key="x"), i, p, "PM", 4025.0, {}) == "x_lh_org_room"
    assert sm4.lh_org_adjust(ctx, sl, dict(key="x"), ib(ctx, "14:00"), p, "PM", 3995.0, {}) is None      # not the last hour
    ctx.lock = {}
    assert sm4.org_fill_ctx(ctx, sl, i, p) is None                                                        # the objective is not delivered
    assert sm4.lh_org_open(ctx, i, p) is False
    ctx.lock = {"AM": dict(side=-1, delivered_i=ctx.start + 10, target=3980.0)}
    ctx.h[ib(ctx, "10:00")] = 4021.0
    assert sm4.org_fill_ctx(ctx, sl, i, p) is None                                                        # the day's high reached the prior close: filled


# --- 62 D15-one-clean-gap-instrument ---------------------------------------------------------------------------------------------------------------------

def test_combine_prefers_single_gap():
    """061 ~01:49:01: when both instruments fill the same slot the one whose entry area is ONE clean gap (gap_count == 1) is kept, else the first; the tag counts the FVGs of the leg between the EQ
    and the leg extreme (smt_pick "clean")."""
    from test_caption_gap_sm1a import _book, _row
    mk = lambda sym, t, n: _book([dict(_row(sym, t, "10:00"), gap_count=n)]).assign(gap_count=n)
    a, b = mk("ES", "09:40", 3), mk("NQ", "09:45", 1)
    assert list(B.combine(a, b, pick="clean").symbol) == ["NQ"]
    assert list(B.combine(a, b, pick="first").symbol) == ["ES"]
    assert list(B.combine(mk("ES", "09:40", 3), mk("NQ", "09:45", 2), pick="clean").symbol) == ["ES"]      # neither is clean: the first
    assert list(B.combine(mk("ES", "09:40", 1), mk("NQ", "09:45", 1), pick="clean").symbol) == ["ES"]
    sd = sd_of([(4001.0, 4003.0, 4000.0, 4002.0), (4002.0, 4010.0, 4001.5, 4009.0), (4009.0, 4012.0, 4005.0, 4011.0), (4011.0, 4016.0, 4010.0, 4015.0), (4015.0, 4030.0, 4014.0, 4029.0),
               (4029.0, 4031.0, 4020.0, 4025.0)])
    sw = dict(ext=4000.0, ext_i=0)
    assert sm4.gap_count(sd, sw, 5) == len([g for g in sd.gaps if g.top <= sm4.m2_eq(sd, sw, 5)])
    assert Params(smt_pick="clean").smt_pick == "clean"
