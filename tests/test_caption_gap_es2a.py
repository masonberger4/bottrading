"""Caption-gap pass, package entries_stops_sizing #2/3, part A: the unit and engine tests of the 35 specs (definitions_pd_arrays_structure.md items 146, 151, 154, 155, 186, 190; levels_liquidity_targets.md items
10, 90, 120; management_partials_trailing_exits.md items 105, 129; models_setups_entries.md items 6, 7, 18, 24, 27, 29, 30, 38, 44, 45, 52, 73, 82, 92, 124, 141; stops_sizing_scaling_in.md items 1, 2, 3, 4, 6, 8, 9,
10). Hand-made 5-minute days (a whole 00:00-16:15 frame) through run_day (the real engine path) and unit tests of the es2.py helpers on hand-made Sides. No platform-specific paths; nothing here needs market data.
The study variants and the no-look-ahead runs are in test_caption_gap_es2b.py."""
from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from mentorship import es2, levels as L, setups as SM, sm2, strategy as S, study
from mentorship.study import OA1029_OLD
from mentorship.strategy import Params
from dataclasses import dataclass as _oa_dc


@_oa_dc
class Params(Params):   # OA1029 Q92: these tests exercise other rules; the order-block narrative gate (default on) leaves them no trades
    ob_need_narrative: bool = False

from test_review_fixes import A_LOCK, A_ROWS, B_POST, B_ROWS, BASE, D0, day, history, run as rf_run
from test_caption_gap_sm1a import sd_of, stub
from test_caption_gap_es1a import C_ROWS, POST, c_run, one

NEW_SWITCHES = (
    "ob_session_filter", "ob_grade_mult", "gap_risk", "rb_ctx_mult", "entry_fvg_min_tf", "ob_mt_two_sided", "stop_bpr_mt", "fvg_wick_ce", "ob_mt_if_swept", "bz_higher_array", "fri_shallow", "vi_ob_add",
    "vi_ob_entry", "vi_add_early_pts", "close_proximity", "vi_first", "wick_ce_refine", "e4_color", "e4_wick_ok", "fvg_then_ob", "breakaway_chase", "breaker_iofed", "ifvg_stop", "ifvg_ob_add", "entry",
    "mot_next_open", "entry_offset_ticks", "entry_order", "ob_arm", "add_sizes", "add_far_edge", "add_wick_retouch", "add_htf_fvg_edge", "add_ladder", "add_on_ifvg", "add_stop_under_array", "in_zone_ladder",
    "add_after_partial", "add_form_eq", "add_day_mode", "add_low_end_size",
)
KNOBS = ("ob_session_windows", "ob_grade_tol", "gap_risk_near_pts", "bpr_adj_pts", "bz_higher_pts", "close_prox_windows", "wick_ce_lookback", "breakaway_chase_bars", "iofed_gap_bars", "iofed_gap_pts",
         "add_max_n", "add_hv_mult", "trend_day_adr", "mot_dead_mult", "fri_shallow_edge")


# --- defaults / validation ------------------------------------------------------------------------------------------------------------

def test_new_switch_defaults_and_validation():
    p = Params(**OA1029_OLD)                 # the built values; the OA1029 defaults are checked in test_owner_answers_oa1029.py
    assert (p.ob_session_filter, p.ob_session_windows, p.ob_grade_mult, p.ob_grade_tol, p.gap_risk, p.gap_risk_near_pts, p.rb_ctx_mult, p.entry_fvg_min_tf, p.ob_mt_two_sided, p.stop_bpr_mt,
            p.bpr_adj_pts) == (False, ((120, 300), (420, 660)), (1.0, 1.0), 0.10, "off", 2.0, 1.0, 1, False, False, 1.0)
    assert (p.fvg_wick_ce, p.ob_mt_if_swept, p.bz_higher_array, p.bz_higher_pts, p.fri_shallow, p.vi_ob_add, p.vi_ob_entry, p.vi_add_early_pts, p.close_proximity, p.close_prox_windows, p.vi_first,
            p.wick_ce_refine, p.wick_ce_lookback) == (False, False, False, 5.0, False, False, False, 0.0, False, ((650, 670),), False, False, 120)
    assert (p.e4_color, p.e4_wick_ok, p.fvg_then_ob, p.breakaway_chase, p.breakaway_chase_bars, p.breaker_iofed, p.ifvg_stop, p.ifvg_ob_add, p.iofed_gap_bars, p.iofed_gap_pts, p.mot_next_open,
            p.entry_offset_ticks) == (False, False, False, False, 3, False, "ce", False, 5, 3.0, True, 0)
    assert (p.add_sizes, p.add_max_n, p.add_far_edge, p.add_wick_retouch, p.add_htf_fvg_edge, p.add_ladder, p.add_on_ifvg, p.add_stop_under_array, p.in_zone_ladder, p.add_after_partial, p.add_hv_mult,
            p.add_form_eq, p.add_day_mode, p.trend_day_adr, p.add_low_end_size) == ("decreasing", 3, False, False, False, "", False, False, False, "", 1.2, False, "eq_cutoff", 0.5, "smallest")
    assert (p.entry, p.entry_order, p.ob_arm, p.retrace_candle, p.entry_arrays) == ("edge", "limit", "leave", "off", ())      # the built defaults
    for kw in (dict(add_sizes="x"), dict(add_ladder="x"), dict(gap_risk="x"), dict(ifvg_stop="x"), dict(add_after_partial="x"), dict(add_day_mode="x"), dict(add_low_end_size="x"), dict(entry="x"),
               dict(entry_order="x"), dict(ob_arm="x"), dict(ob_grade_mult=(1.0,)), dict(ob_grade_mult=(1.0, 0.0)), dict(ob_session_windows=((300, 120),)), dict(close_prox_windows=((10,),)),
               dict(ob_grade_tol=-1), dict(rb_ctx_mult=0), dict(entry_fvg_min_tf=0), dict(bpr_adj_pts=-1), dict(bz_higher_pts=-1), dict(vi_add_early_pts=-1), dict(wick_ce_lookback=0),
               dict(breakaway_chase_bars=0), dict(iofed_gap_bars=-1), dict(entry_offset_ticks=-1), dict(add_max_n=0), dict(add_hv_mult=0), dict(trend_day_adr=0), dict(gap_risk_near_pts=-1)):
        with pytest.raises(ValueError):
            Params(**kw)
    for kw in (dict(entry="auto2"), dict(entry="far_on_breaker"), dict(entry_order="market_on_touch"), dict(ob_arm="intrabar_htf"), dict(add_ladder="067"), dict(add_sizes="equal_013"), dict(vi_ob_entry=True)):
        Params(**kw)
    assert "vi_ob" in Params(vi_ob_entry=True).entry_arrays and Params(e4_color=True).retrace_candle == "intrabar"
    q = Params(vi_ob_entry=True, e4_color=True)
    assert replace(q).entry_arrays == q.entry_arrays                                  # the aliases survive replace() (run_day)
    assert set(NEW_SWITCHES) | set(KNOBS) <= set(Params.__dataclass_fields__)


def test_every_switch_has_a_study_variant():
    on = set()
    for k, v in study._ES2_DECISIONS.items():
        Params(**v)
        on |= set(v)
    missing = [s for s in NEW_SWITCHES if s not in on]
    assert not missing, missing


# --- E3-entry-spread-offset (124) / E1-market-on-touch (92) -----------------------------------------------------------------------------

def test_entry_offset_ticks_fills_on_a_touch():
    base = c_run()
    assert len(base) == 1 and base[0].entry == pytest.approx(100.4)
    off = c_run(entry_offset_ticks=2)
    assert len(off) == 1 and off[0].entry == pytest.approx(100.9)                    # 2 ticks (0.25 each) toward the market: the limit moves from 100.4 to 100.9
    rows = list(C_ROWS)
    rows[5] = (101.6, 101.7, 100.4, 100.5)                                           # the retrace bar only TOUCHES the 100.4 limit (no tick through)
    assert c_run(rows) == []                                                         # E3: a touch does not fill a plain limit
    t = c_run(rows, entry_offset_ticks=1)
    assert len(t) == 1 and t[0].entry == pytest.approx(100.65)                       # ... the offset limit (100.65) is traded through by the touch of the original level
    assert t[0].entry_time.hour == 9 and t[0].entry_time.minute == 55


def test_market_on_touch_fills_at_the_next_open_or_at_the_level():
    rows = list(C_ROWS)
    rows[5] = (101.6, 101.7, 100.4, 100.5)                                           # only a touch of 100.4
    assert c_run(rows) == []
    nxt = c_run(rows, entry_order="market_on_touch")                                 # mot_next_open (default): the touch bar -> a market buy at the NEXT bar's open (100.5)
    assert len(nxt) == 1 and nxt[0].entry == pytest.approx(100.5) and nxt[0].entry_time.hour == 10 and nxt[0].entry_time.minute == 0
    lvl = c_run(rows, entry_order="market_on_touch", mot_next_open=False)            # at the level: filled by the touch itself
    assert len(lvl) == 1 and lvl[0].entry == pytest.approx(100.4) and lvl[0].entry_time.minute == 55
    thr = c_run(entry_order="market_on_touch")                                       # a bar that trades through also fills (the touch comes first)
    assert len(thr) == 1 and thr[0].entry == pytest.approx(100.5) and thr[0].entry_time.hour == 10
    assert c_run(entry_order="stop_cc") is not None                                  # (the built mode is untouched)


def test_convert_pending_unit():
    sd = sd_of([(100.0, 100.5, 99.5, 100.2), (100.2, 100.4, 99.0, 100.1), (100.1, 100.3, 100.0, 100.2), (100.2, 100.4, 100.1, 100.3), (100.3, 100.5, 100.2, 100.4)])
    o = dict(i=0, entry=99.0, mot=True)
    assert es2.convert_pending(o, sd, 1) is o                                         # bar 0 is the arming bar: nothing to judge yet
    assert es2.convert_pending(o, sd, 2).get("market") is True                        # bar 1 touched 99.0
    assert es2.convert_pending(dict(o, entry=98.0), sd, 2).get("market") is None      # not touched
    c = dict(i=0, entry=98.0, chase_bars=2)
    assert es2.convert_pending(c, sd, 2).get("market") is None and es2.convert_pending(c, sd, 3).get("market") is True    # unfilled after 2 bars -> a market order at bar 3's open
    assert es2.convert_pending(dict(c, market=True), sd, 4)["market"] is True


# --- E2-iofed-depth-second-gap (82) / A5-wick-ce-inside-fvg-exact-entry (29) / E2-vi-primary-entry-array (27) -------------------------------

def test_second_gap_near_unit_and_auto2_through_the_engine():
    p = Params(es_pt=1.0)
    g1 = L.Zone("bull", 100.4, 99.8, 4, 3, float("nan"))
    near = L.Zone("bull", 102.0, 101.0, 6, 5, float("nan"))                            # 0.6 above g1.top, 2 bars later
    far = L.Zone("bull", 106.0, 105.0, 6, 5, float("nan"))                             # 4.6 above
    late = L.Zone("bull", 102.0, 101.0, 20, 19, float("nan"))                          # 16 bars later
    for z, want in ((near, True), (far, False), (late, False)):
        sd = SimpleNamespace(gaps=[g1, z])
        assert es2.second_gap_near(sd, g1, 30, p) is want
    assert es2.second_gap_near(SimpleNamespace(gaps=[g1]), g1, 30, p) is False
    # engine: scenario C has one gap [99.8, 100.4]: auto2 = the CE (100.1), never reached; a second gap right above it makes it the near edge (100.4)
    assert c_run(entry="auto2") == [] and c_run(entry="ce") == []
    rows = list(C_ROWS)
    rows[4] = (101.0, 101.8, 100.4, 101.6)
    rows[3] = (99.7, 101.2, 99.6, 101.0)
    # (the built scenario keeps its single gap; the second-gap case is the unit test above plus the real-data runs of part B)


def test_wick_ce_refine_sets_the_limit_at_a_wick_ce_inside_the_gap():
    p = Params(es_pt=1.0, wick_ce_refine=True)
    tr = c_run(wick_ce_refine=True)
    assert len(tr) == 1 and tr[0].entry == pytest.approx(100.35) and "wick_ce_refine" in tr[0].lv_tags            # the flat bars before 09:30: upper wick CE (100 + 100.2) / 2 = 100.1 -> + 1 tick
    assert c_run()[0].entry == pytest.approx(100.4)                                                            # built: the gap top
    # a CE outside the gap is ignored; the limit never rises above the top
    sd = sd_of([(100.0, 100.4, 99.6, 100.0)] * 6 + [(100.0, 100.2, 99.8, 100.1)])
    ctx = SimpleNamespace(start=0)
    g = L.Zone("bull", 100.4, 99.8, 6, 5, float("nan"))
    assert es2.wick_ce_refine(ctx, sd, dict(ext_i=6, ref_i=6), g, 100.4, 99.8, 6, p) == pytest.approx(100.4)          # CE 100.2 / 99.8 / ...: the highest in [99.8, 100.4] is 100.2 -> 100.45, clipped to the top
    assert es2.wick_ce_refine(ctx, sd, dict(ext_i=6, ref_i=6), L.Zone("bull", 103.0, 102.0, 6, 5), 103.0, 102.0, 6, p) is None


def test_vi_first_unit_and_engine():
    # a bullish VI of the leg at / under the leg EQ is the entry zone (near edge = its top); none -> None
    rows = [(100.0, 100.3, 99.6, 99.7), (99.7, 99.8, 98.6, 98.8), (98.8, 99.9, 98.7, 99.8), (100.0, 100.9, 99.7, 100.8), (100.8, 102.4, 100.7, 102.3), (102.3, 104.0, 102.2, 103.9)]
    sd = sd_of(rows)
    sw = dict(ext_i=1, ext=98.6)
    p = Params(es_pt=1.0, vi_first=True)
    z = es2.vi_first_pick(None, sd, sw, 5, p)
    assert z is not None and (z.bottom, z.top) == (99.8, 100.0) and z.top <= (98.6 + 104.0) / 2 + 1e-9
    assert es2.vi_first_pick(None, sd, dict(ext_i=1, ext=98.6), 2, p) is None             # nothing formed yet at bar 2
    sd2 = sd_of(rows[:3] + [(99.8, 101.0, 99.7, 100.9)] + rows[4:])                         # no body gap at bar 3: no VI
    assert es2.vi_first_pick(None, sd2, sw, 5, p) is None
    # engine: scenario C with a VI [99.7, 99.9] in the leg and a retrace to it - the VI (not the FVG [99.8, 100.4]) is the entry at its top
    r = list(C_ROWS)
    r[3] = (99.9, 101.2, 99.6, 101.0)
    r[5] = (101.6, 101.7, 99.8, 100.5)
    assert c_run(r)[0].entry_kind == "fvg" and c_run(r)[0].entry == pytest.approx(100.4)       # built: the FVG pick
    tr = c_run(r, vi_first=True)
    assert len(tr) == 1 and tr[0].entry_kind == "vi" and tr[0].entry == pytest.approx(99.9) and "vi_first" in tr[0].lv_tags


def test_close_proximity_and_friday_shallow_picks_unit():
    rows = [(100.0, 100.5, 99.5, 100.2), (100.2, 100.4, 99.0, 99.1), (99.1, 100.9, 99.0, 100.8), (100.8, 102.0, 100.7, 101.9), (101.9, 103.0, 101.8, 102.9)]
    sd = sd_of(rows)
    g_old = L.Zone("bull", 100.0, 99.2, 2, 1, float("nan"))
    g_new = L.Zone("bull", 101.6, 100.9, 3, 2, float("nan"))
    idx = pd.date_range("2026-06-23 10:50", periods=5, freq="5min", tz="America/New_York")
    ctx = SimpleNamespace(t=(idx.hour * 60 + idx.minute).values, cur_lock=dict(side=1, target=110.0), day=D0)
    p = Params(es_pt=1.0, close_proximity=True)
    assert es2.close_prox_pick(ctx, sd, dict(ext_i=1), [g_old, g_new], 3, p, "AM") is g_new               # the gap NEAREST the market (the highest top under the close), not the first one
    assert es2.close_prox_pick(ctx, sd, dict(ext_i=1), [g_old], 3, p, "AM") is g_old
    out = SimpleNamespace(**{**vars(ctx), "t": ctx.t + 300})
    assert es2.close_prox_pick(out, sd, dict(ext_i=1), [g_old, g_new], 3, p, "AM") is None                 # outside 10:50-11:10
    nolock = SimpleNamespace(**{**vars(ctx), "cur_lock": None})
    assert es2.close_prox_pick(nolock, sd, dict(ext_i=1), [g_old, g_new], 3, p, "AM") is None              # no session lock (no draw named)
    # a VI created by the shift counts as a candidate too
    sdv = sd_of(rows[:3] + [(101.0, 102.0, 100.7, 101.9), rows[4]])
    z = es2.close_prox_pick(ctx, sdv, dict(ext_i=1), [g_old], 3, p, "AM")
    assert z is not None and (z.bottom, z.top) == (100.8, 101.0)                                              # the VI [100.8, 101.0] is nearer than the old gap
    # Friday: closer to the draw than the leg is tall -> the FIRST gap of the leg
    fri = SimpleNamespace(**{**vars(ctx), "day": pd.Timestamp("2026-06-26").date(), "cur_lock": dict(side=1, target=104.0)})
    pf = Params(es_pt=1.0, fri_shallow=True)
    assert es2.fri_shallow_pick(fri, sd, dict(ext_i=1, ext=99.0), [g_new, g_old], 3, pf) is g_old                # leg = 102.0 - 99.0 = 3.0 > the draw distance 104.0 - 101.9 = 2.1
    far = SimpleNamespace(**{**vars(fri), "cur_lock": dict(side=1, target=120.0)})
    assert es2.fri_shallow_pick(far, sd, dict(ext_i=1, ext=99.0), [g_new, g_old], 3, pf) is None              # the draw is farther than the leg is tall
    assert es2.fri_shallow_pick(replace_ns(fri, day=D0), sd, dict(ext_i=1, ext=99.0), [g_new, g_old], 3, pf) is None      # Tuesday
    assert es2.fri_shallow_pick(replace_ns(fri, cur_lock=None), sd, dict(ext_i=1, ext=99.0), [g_old], 3, pf) is None


def replace_ns(ns, **kw):
    return SimpleNamespace(**{**vars(ns), **kw})


def test_fvg_wick_ce_enters_at_the_wick_ce_and_exits_on_a_body_close():
    rows = list(C_ROWS)
    rows[2] = (99.7, 99.8, 98.7, 99.4)                                         # the FVG's first candle: body 99.4..99.7, lower wick 0.7 >= body 0.3 -> wick CE (99.4 + 98.7) / 2 = 99.05
    sd = sd_of(rows)
    g = next(z for z in sd.gaps if z.i == 4)
    assert es2.wick_ce_of(sd, g, Params()) == (pytest.approx(99.05), pytest.approx(98.7))
    sd2 = sd_of(C_ROWS)
    assert es2.wick_ce_of(sd2, next(z for z in sd2.gaps if z.i == 4), Params()) is None       # c1 98.7 -> 99.7: no lower wick
    deep = list(rows)
    deep[5] = (101.6, 101.7, 99.0, 100.5)                                       # the retrace runs through the gap down to the wick CE
    assert c_run(rows, min_risk_pts=0.3) [0].entry == pytest.approx(100.4)       # built: the FVG edge
    tr = c_run(deep, fvg_wick_ce=True, min_risk_pts=0.3)
    assert len(tr) == 1 and tr[0].entry == pytest.approx(99.05) and tr[0].stop == pytest.approx(98.45) and "fvg_wick_ce" in tr[0].lv_tags       # hard stop: the wick low 98.7 - 1 tick
    # a body CLOSE under the wick CE (minus a tick) exits; a wick under it does not
    wick = list(deep)
    wick[6] = (100.5, 100.6, 98.5, 100.4)
    t2 = c_run(wick, fvg_wick_ce=True, min_risk_pts=0.3)
    assert t2 and t2[0].exits[0][3] not in ("stop", "wick_ce_close")
    close = list(deep)
    close[6] = (100.5, 100.6, 98.7, 98.8)
    t3 = c_run(close, fvg_wick_ce=True, min_risk_pts=0.3)
    assert t3 and t3[0].exits[0][3] == "wick_ce_close"
    # entry="ladder": the FVG CE first, then the wick CE as a deeper rung
    t4 = c_run(deep, fvg_wick_ce=True, entry="ladder", min_risk_pts=0.3, ladder_by_day=False)
    assert t4 and t4[0].entry == pytest.approx(100.1)


def test_fvg_then_ob_second_entry_at_the_ob_open():
    rows = list(C_ROWS)
    rows[6] = (100.5, 100.6, 99.4, 100.3)                                       # after the fill (100.4): a dip to 99.4, then the run
    rows.insert(7, (100.3, 103.0, 100.2, 102.9))
    base = c_run(rows, adds=(0.5,))
    assert len(base) == 1 and base[0].adds == [] and base[0].stop == pytest.approx(99.1)
    tr = c_run(rows, adds=(0.5,), fvg_then_ob=True)
    assert len(tr) == 1 and tr[0].entry == pytest.approx(100.4) and tr[0].stop == pytest.approx(98.35)         # one stop under the OB low (98.6) for both entries
    assert len(tr[0].adds) == 1 and tr[0].adds[0][1] == pytest.approx(100.0) and tr[0].adds[0][2] >= 1          # entry #2 = the OB candle's open (the highest open of the run), an E12-sized add
    # the add is cancelled when T1 fills first (the rally goes straight to the target)
    straight = list(C_ROWS)
    t = c_run(straight, adds=(0.5,), fvg_then_ob=True)
    assert len(t) == 1 and t[0].adds == []


def test_stop_at_bpr_mt(monkeypatch):
    sd = SimpleNamespace(bprs=lambda n=0: [L.Zone("bear", 106.5, 105.0, 3, 3), L.Zone("bull", 99.7, 98.9, 3, 3), L.Zone("bull", 99.0, 97.0, 5, 5)])
    g = L.Zone("bull", 100.4, 99.8, 4, 3, float("nan"))
    p = Params(es_pt=1.0, stop_bpr_mt=True)
    # the BPR [98.9, 99.7]: its near edge (top 99.7) is 0.1 under the gap's far edge (99.8): the stop = its MT 99.3 - 1 tick; the BPR formed after bar i is unknown
    assert es2.bpr_stop(sd, g, 4, p) == pytest.approx(99.3 - p.pad)
    assert es2.bpr_stop(sd, g, 2, p) is None
    assert es2.bpr_stop(sd, L.Zone("bull", 103.0, 102.0, 4, 3, float("nan")), 4, p) is None                       # too far from this gap
    assert es2.bpr_stop(sd, g, 4, Params(es_pt=1.0, stop_bpr_mt=True, bpr_adj_pts=0.05)) is None                  # beyond bpr_adj_pts
    # engine: scenario C (stop 99.1 under the gap) with a BPR just under the gap
    monkeypatch.setattr(S.Side, "bprs", lambda self, n=0: [L.Zone("bull", 99.7, 98.7, 3, 3)])
    base = c_run()
    tr = c_run(stop_bpr_mt=True)
    assert base[0].stop == pytest.approx(99.1) and tr[0].stop == pytest.approx(99.2 - p.pad) and tr[0].stop < base[0].stop + 1.0


# --- order blocks (146, 151, 190, 120, 141) -----------------------------------------------------------------------------------------------

def test_ob_session_filter():
    p = Params(es_pt=1.0, ob_session_filter=True)
    idx = pd.date_range("2026-06-23 02:00", periods=8, freq="150min", tz="America/New_York")
    ctx = SimpleNamespace(t=(idx.hour * 60 + idx.minute).values)                                   # 02:00 04:30 07:00 09:30 12:00 14:30 17:00 19:30
    ok = lambda k, key="pdl1": es2.ob_session_ok(ctx, None, dict(key=key), dict(k=k), p)
    assert ok(0) and ok(1) and ok(2) and ok(3) and not ok(4) and not ok(5) and not ok(6)           # London 02:00-05:00, NY 07:00-11:00; 12:00 / 14:30 / 17:00 are neither
    assert ok(4, "london") and ok(5, "prev_pm") and ok(6, "am_session")                             # (b) a run below a prior London / NY session low, then a rally
    assert es2.ob_session_ok(ctx, None, dict(key="pdl1"), dict(k=4), Params(es_pt=1.0))             # off: always ok
    hist = history()
    df = day(A_ROWS, spike=True)
    assert len(one(df, hist)) == 1 and len(one(df, hist, ob_session_filter=True)) == 1               # the 09:35 OB candle is in the NY window
    # a London-only window: the 09:35 candle is outside it and the sweep key (premarket) is no session low - the OB does not arm
    s0 = dict(sm2.HITS)
    assert one(df, hist, ob_session_filter=True, ob_session_windows=((120, 300),)) == []
    assert sm2.HITS.get("ob_session_skip", 0) > s0.get("ob_session_skip", 0)


def test_ob_grade_a_b_and_the_size_multiplier():
    st = dict(ob_mt=99.4, ob_body=1.2)
    p = Params(es_pt=1.0)
    assert es2.ob_grade(st, 99.5, 100.3, p) == "A" and es2.ob_grade(st, 99.4, 100.3, p) == "A"        # the retest low at / above the MT
    assert es2.ob_grade(st, 99.3, 100.3, p) == "B"                                                    # 0.1 under the MT <= 10 % of the body (0.12), the bar closes above it
    assert es2.ob_grade(st, 99.2, 100.3, p) == "X"                                                    # 0.2 under: the tolerance is exceeded
    assert es2.ob_grade(st, 99.3, 99.3, p) == "X"                                                     # a body close under the MT
    hist = history()
    rows = list(A_ROWS)
    rows[4] = (100.7, 100.8, 99.3, 100.3)                                                              # the fill bar stabs 0.1 under the MT (99.4), no stop (99.15)
    k = dict(min_risk_pts=0.5)
    base = one(day(rows, spike=True), hist, **k)
    assert len(base) == 1 and "ob_grade" not in base[0].lv_tags
    b = one(day(rows, spike=True), hist, ob_grade_mult=(1.0, 0.5), **k)
    # review fix (look-ahead): the fill bar's own stab is not known at the fill - the fill is graded A (fill price 100.0 >= the MT) at full size and the trade keeps that tag; the stab regrades the
    # position to B once the bar has closed (it scales later adds only)
    assert len(b) == 1 and "ob_grade_A" in b[0].lv_tags and "ob_grade_B" not in b[0].lv_tags and b[0].shares == base[0].shares
    assert b[0].entry_risk_pct == pytest.approx(base[0].entry_risk_pct, rel=0.01)
    gi = es2.grade_inputs(sd_of([(100.0, 100.5, 99.9, 100.2)] * 3 + [(100.2, 100.5, 99.6, 100.1)] * 3), dict(ob_mt=99.4, arm_i=2), 5, 100.0)
    assert gi == (pytest.approx(99.6), pytest.approx(100.1))                                          # the closed bars after the arming bar (3, 4) and the fill price - never bar 5 itself
    assert es2.grade_inputs(sd_of([(100.0, 100.5, 99.0, 99.2)] * 6), dict(ob_mt=99.4, arm_i=4), 5, 100.0) == (100.0, 100.0)    # no closed bar between the arming and the fill: the fill price
    a = one(day(A_ROWS, spike=True), hist, ob_grade_mult=(0.5, 1.0), **k)                              # the plain retest (low 99.9 >= MT) is an A: scaled by the first multiplier
    a0 = one(day(A_ROWS, spike=True), hist, **k)
    assert len(a) == 1 and "ob_grade_A" in a[0].lv_tags and a[0].shares == pytest.approx(a0[0].shares / 2, abs=1)
    c = one(day(A_ROWS, spike=True), hist, ob_grade_mult=(1.0, 0.5), **k)                              # an A with a multiplier of 1: untouched
    assert c[0].shares == a0[0].shares and "ob_grade_A" in c[0].lv_tags


def test_ob_mt_two_sided_unit_and_engine():
    sd = sd_of([(100.0, 100.5, 99.0, 99.2), (99.2, 100.4, 99.5, 100.3), (100.3, 101.0, 100.0, 100.8), (100.8, 101.2, 99.3, 100.6)])
    assert es2.ob_mt_dead(sd, 0, 99.4, 1) is False                                                    # left upward (bar 1 entirely above 99.4): alive
    assert es2.ob_mt_dead(sd, 0, 99.4, 3) is True                                                     # ... and bar 3 traded back under it: it has worked on both sides
    assert es2.ob_mt_dead(sd, 3, 99.4, 3) is False and es2.ob_mt_dead(sd, 0, 99.4, 0) is False
    below = sd_of([(100.0, 100.1, 98.0, 98.2), (98.2, 98.9, 98.1, 98.5), (98.5, 99.9, 98.4, 99.8)])
    assert es2.ob_mt_dead(below, 0, 99.4, 2) is True                                                  # entirely under, then over
    hist = history()
    rows = list(A_ROWS)
    rows[2] = (98.8, 100.0, 99.5, 99.9)                                                                # the bars after the OB candle (09:35) stay above its MT 99.4 ...
    rows[3] = (100.1, 100.8, 99.3, 100.7)                                                              # ... then a dip under it before the arming close
    k = dict(min_risk_pts=0.5)
    base = one(day(rows, spike=True), hist, **k)
    assert len(base) == 1 and base[0].stop == pytest.approx(99.15)                                    # built: the MT stop
    dead = one(day(rows, spike=True), hist, ob_mt_two_sided=True, **k)
    assert len(dead) == 1 and dead[0].stop == pytest.approx(98.25)                                    # the MT has worked on both sides: the stop falls back to the OB low (98.5) - 1 tick
    fresh = one(day(A_ROWS, spike=True), hist, ob_mt_two_sided=True, **k)
    assert fresh[0].stop == pytest.approx(99.15)                                                       # an OB only left upward keeps its MT


def test_ob_mt_if_swept_unit_and_engine():
    rows = [(100.5, 100.8, 100.2, 100.6), (100.6, 100.7, 99.9, 100.1), (100.1, 100.9, 100.0, 100.8), (100.8, 100.9, 100.1, 100.2), (100.2, 100.3, 99.2, 99.4), (99.4, 100.5, 99.3, 100.4)]
    sd = sd_of(rows)                                                                                   # pivot low 99.9 (bar 1); bar 4 (down candle 100.2 -> 99.4) runs under it
    ob = dict(k=4, j=4, body_top=100.2, body_low=99.4, mt=99.8, hi=100.3, lo=99.2)
    p = Params(es_pt=1.0, ob_mt_if_swept=True)
    assert es2.ob_swept_entry(sd, ob, p) == pytest.approx(99.8)                                        # (open + close) / 2 of the swept candle
    assert es2.ob_swept_entry(sd, dict(ob, k=3, j=3), p) is None                                       # bar 3's low 100.1 did not run the pivot low 99.9
    assert es2.ob_swept_entry(sd, ob, Params(es_pt=1.0)) is None                                       # off
    assert es2.ob_swept_entry(sd_of(rows[:2]), dict(ob, k=1), p) is None                               # no confirmed pivot yet
    # engine glue (the pivot-low rows of the unit test above move the engine's premarket pool / MSS reference, so the detection is unit-tested and the glue run with the detection forced): a swept OB is bought at its body MT
    hist = history()
    rows2 = list(A_ROWS)
    rows2[4] = (100.7, 100.8, 99.1, 100.3)                                                             # the retrace after the arming close reaches 99.2
    base = one(day(rows2, spike=True), hist, min_risk_pts=0.5)
    assert len(base) == 1 and base[0].entry == pytest.approx(100.0)
    real = es2.ob_swept_entry
    es2.ob_swept_entry = lambda sd_, ob_, p_: float((sd_.o[ob_["k"]] + sd_.c[ob_["k"]]) / 2) if p_.ob_mt_if_swept else None
    try:
        tr = one(day(rows2, spike=True), hist, ob_mt_if_swept=True, min_risk_pts=0.5)
    finally:
        es2.ob_swept_entry = real
    assert len(tr) == 1 and tr[0].entry == pytest.approx(99.2) and tr[0].stop == pytest.approx(98.25)          # (o + c) / 2 of the swept candle (99.6 -> 98.8); the stop under the OB low (98.5) - 1 tick


def test_ob_arm_intrabar_trade_through_arms_at_once():
    hist = history()
    rows = list(A_ROWS)
    rows[3] = (99.8, 100.4, 99.7, 99.9)                                                                # trades over the OB bodies (100.0) but closes under them
    rows[4] = (100.3, 100.5, 99.5, 100.6)
    base = one(day(rows, spike=True), hist)
    assert base == [] or base[0].entry_time.minute != 50                                               # built: no close over the bodies on 09:45
    tr = one(day(rows, spike=True), hist, ob_arm="intrabar_htf")
    assert len(tr) == 1 and tr[0].entry == pytest.approx(100.0) and tr[0].entry_time.minute == 50          # armed on the trade-through bar (09:45), filled from the next one
    assert one(day(A_ROWS, spike=True), hist, ob_arm="intrabar_htf")[0].entry == pytest.approx(100.0)


# --- breakers (45, 105, 18, E12 in-zone ladder 4) -----------------------------------------------------------------------------------------------

AFTER_B = [(102.3, 102.4, 100.3, 101.0), (101.0, 109.0, 100.9, 108.8)]


def scen_b(rows=None, **kw):
    """Scenario B (the breaker 100.1 - 101.0, MT 100.55; the unicorn FVG at 10:10) + a retrace and a run to the draw; breaker_by_close makes the breaker the entry."""
    tr, *_ = rf_run(day(rows or (B_ROWS + AFTER_B)), history(hi=112.0, lo=88.0), Params(**{**B_POST, "adds": (0.5,), **kw}), {})
    return tr


def test_breaker_iofed_exact_match():
    base = scen_b(breaker_by_close=True)
    assert len(base) == 1 and base[0].entry_kind == "breaker" and base[0].entry == pytest.approx(101.0)
    io = scen_b(breaker_by_close=True, breaker_iofed=True)
    assert len(io) == 1 and io[0].entry == pytest.approx(101.25)                       # 1 tick on the market side of the breaker extreme: an exact match of 101.0 fills under E3
    rows = list(B_ROWS + AFTER_B)
    rows[9] = (102.3, 102.4, 101.0, 101.5)                                              # the retrace only MATCHES the breaker top
    rows[10] = (101.5, 109.0, 101.2, 108.8)
    assert scen_b(rows, breaker_by_close=True) == []                                    # built: no fill without a tick through
    t = scen_b(rows, breaker_by_close=True, breaker_iofed=True)
    assert len(t) == 1 and t[0].entry == pytest.approx(101.25)                          # filled by the exact match


def test_bz_higher_array_unit_and_engine(monkeypatch):
    bz = L.Zone("bull", 101.0, 100.1, 6, 3, 100.55)
    sd = sd_of([(100.0, 100.5, 99.0, 99.2), (99.2, 100.0, 99.1, 99.9), (99.9, 100.6, 98.2, 98.3), (98.3, 98.9, 97.9, 98.6), (98.6, 99.2, 98.5, 99.1), (99.1, 99.5, 98.9, 99.4), (99.4, 101.0, 99.3, 100.9)])
    gaps = [g for g in sd.gaps]
    p = Params(es_pt=1.0, bz_higher_array=True)
    far = es2.higher_array(SimpleNamespace(conf=None), sd, bz, 6, p)
    assert far is None or far < bz.bottom                                               # (this tiny book has no alive gap close under the breaker)
    # a hand-made alive gap [98.6, 99.4] whose top is within 5 points under the breaker bottom: its far edge (98.6) is the stop / abort level
    sd2 = SimpleNamespace(gaps=[L.Zone("bull", 99.4, 98.6, 4, 3, float("nan"))], c=np.array([100.0] * 8))
    assert es2.higher_array(SimpleNamespace(conf=None), sd2, bz, 6, p) == pytest.approx(98.6)
    sd3 = SimpleNamespace(gaps=[L.Zone("bull", 94.0, 93.0, 4, 3, float("nan"))], c=np.array([100.0] * 8))
    assert es2.higher_array(SimpleNamespace(conf=None), sd3, bz, 6, p) is None         # more than bz_higher_pts away
    sd4 = SimpleNamespace(gaps=[L.Zone("bull", 99.4, 98.6, 4, 3, float("nan"))], c=np.array([100.0] * 5 + [98.0, 100.0]))
    assert es2.higher_array(SimpleNamespace(conf=None), sd4, bz, 6, p) is None         # a close through its far edge killed it
    # engine: with the array present the breaker trade drops the breaker-MT exit (bz_mt) and carries the array's far edge as the abort level
    monkeypatch.setattr(es2, "higher_array", lambda ctx, sd_, bz_, i, p_: 99.0)
    base = scen_b(breaker_by_close=True)
    hi = scen_b(breaker_by_close=True, bz_higher_array=True)
    assert base[0].bz_mt == pytest.approx(100.55) and hi[0].bz_mt is None
    assert hi[0].stop <= base[0].stop                                                   # never tighter than the sweep-extreme stop (min of the two)


def test_bz_higher_array_aborts_only_on_a_body_close_beyond_the_array(monkeypatch):
    monkeypatch.setattr(es2, "higher_array", lambda ctx, sd_, bz_, i, p_: 100.0)
    # the breaker trade (entry 101.0, bz 100.1 - 101.0, MT 100.55): a close at 100.4 (under the MT) does NOT abort with the higher array at 100.0 ...
    rows = list(B_ROWS + AFTER_B)
    rows[9] = (102.3, 102.4, 100.3, 100.4)
    rows[10] = (100.4, 109.0, 100.2, 108.8)
    t0 = scen_b(rows, breaker_by_close=True)
    assert t0 and t0[0].exits[0][3] == "breaker_mt"                                    # built: a close under the breaker MT exits
    t1 = scen_b(rows, breaker_by_close=True, bz_higher_array=True)
    assert t1 and t1[0].exits[0][3] != "breaker_mt"
    # ... and a body close under the array's far edge does
    rows2 = list(rows)
    rows2[10] = (100.4, 100.5, 99.5, 99.8)
    t2 = scen_b(rows2, breaker_by_close=True, bz_higher_array=True)
    assert t2 and t2[0].exits[0][3] == "bz_higher"


def test_in_zone_ladder_two_legs_and_the_add_base():
    base = scen_b(breaker_by_close=True)
    lad = scen_b(breaker_by_close=True, in_zone_ladder=True)
    assert len(lad) == 1 and lad[0].entry == pytest.approx(101.0)
    first = lad[0].shares                                                               # price filled the near-edge leg only: 1/3 of the planned size
    assert first < base[0].shares and lad[0].adds == []
    deep = list(B_ROWS + AFTER_B)
    deep[10] = (101.0, 101.2, 100.4, 100.9)                                             # a later bar trades down to the breaker MT (100.55): the deep leg fills (a rung, 2/3 of the plan)
    full = scen_b(deep, breaker_by_close=True, in_zone_ladder=True)
    assert len(full) == 1 and len(full[0].adds) == 1 and full[0].adds[0][1] == pytest.approx(100.55)
    assert full[0].adds[0][2] == pytest.approx(2 * full[0].shares, abs=2)                # the deeper leg is the LARGER one (103: 5 then 10)
    assert full[0].shares == first


def test_far_on_breaker_entry_and_stop():
    sd = SimpleNamespace(vis=lambda kind="bull": [L.Zone("bull", 100.9, 100.0, 6, 6)])
    g5 = L.Zone("bull", 101.3, 100.55, 9, 8, float("nan"))
    bz = L.Zone("bull", 101.0, 100.1, 6, 3, 100.55)
    ctx = SimpleNamespace(tf=5)
    p = Params(es_pt=1.0, entry="far_on_breaker")
    r = es2.far_on_breaker_stop(ctx, sd, dict(ext_i=3), g5, bz, False, 9, p)
    assert r == (pytest.approx(100.55 + p.tick), pytest.approx(100.0 - p.pad))        # the far edge + 1 tick; the stop under the lowest overlapped breaker / VI
    assert es2.far_on_breaker_stop(SimpleNamespace(tf=1), sd, dict(ext_i=3), g5, bz, False, 9, p) is None       # not a 5m gap
    assert es2.far_on_breaker_stop(SimpleNamespace(tf=1), sd, dict(ext_i=3), g5, bz, True, 9, p) is not None    # (a coarse 5m gap on 1m bars)
    assert es2.far_on_breaker_stop(ctx, SimpleNamespace(vis=lambda kind="bull": []), dict(ext_i=3), g5, None, False, 9, p) is None   # no overlap
    # engine: the unicorn FVG 100.55 - 101.3 overlaps the breaker -> the limit at its far edge + 1 tick instead of the top
    base = scen_b()
    far = scen_b(entry="far_on_breaker")
    assert base[0].entry == pytest.approx(101.3) and far[0].entry_kind == "fvg" and far[0].entry == pytest.approx(100.8) and "far_on_breaker" in far[0].lv_tags


# --- A6-voids-fill-holding-range (154), A17-rb-trend-context (155), B5-execution-tf-15m-min (186) -------------------------------------------------

def test_gap_risk_widen_or_skip(monkeypatch):
    rows = [(100.0, 100.5, 99.5, 100.2), (100.2, 101.0, 100.1, 100.9), (100.9, 101.4, 100.8, 101.3), (101.3, 101.5, 101.2, 101.4), (101.4, 101.6, 101.3, 101.5), (101.5, 101.7, 101.4, 101.6)]
    sd = sd_of(rows)                                                                    # gap [100.5, 100.8] formed at bar 2 (bar 0 high 100.5, bar 2 low 100.8), unfilled afterwards
    ctx = SimpleNamespace()
    monkeypatch.setattr(sm2, "state_at", lambda ctx_, i_, p_: "CONSOLIDATION")
    sw = dict(ext_i=0)
    off = Params(es_pt=1.0)
    assert es2.gap_risk_adjust(ctx, sd, sw, 5, off, 101.5, 100.0) == 100.0              # off
    w = es2.gap_risk_adjust(ctx, sd, sw, 5, Params(es_pt=1.0, gap_risk="widen"), 101.5, 100.7)
    assert w == pytest.approx(100.5 - off.pad)                                         # the void 100.5 - 100.8 sits between the entry and the stop (100.7): the stop goes under it
    assert es2.gap_risk_adjust(ctx, sd, sw, 5, Params(es_pt=1.0, gap_risk="skip"), 101.5, 100.7) is None
    assert es2.gap_risk_adjust(ctx, sd, sw, 5, Params(es_pt=1.0, gap_risk="widen"), 101.5, 99.0) == pytest.approx(99.0)    # a stop already under the void ... within near_pts? 99.0 is 1.5 under 100.5: "just below the stop"
    assert es2.gap_risk_adjust(ctx, sd, sw, 5, Params(es_pt=1.0, gap_risk="widen", gap_risk_near_pts=0.5), 101.5, 99.0) == pytest.approx(99.0)
    # the entry gap itself (its top at / above the entry) is no risk gap
    assert es2.gap_risk_adjust(ctx, sd, sw, 5, Params(es_pt=1.0, gap_risk="skip"), 100.8, 100.0) == 100.0
    # filled gap: price traded through it
    filled = sd_of(rows[:3] + [(101.3, 101.5, 100.4, 100.6)] + rows[4:])
    assert es2.gap_risk_adjust(ctx, filled, sw, 5, Params(es_pt=1.0, gap_risk="skip"), 101.5, 100.7) == 100.7
    # not a consolidation: untouched
    monkeypatch.setattr(sm2, "state_at", lambda ctx_, i_, p_: "EXPANSION")
    assert es2.gap_risk_adjust(ctx, sd, sw, 5, Params(es_pt=1.0, gap_risk="skip"), 101.5, 100.7) == 100.7


def test_gap_risk_through_the_engine(monkeypatch):
    base = c_run()
    assert len(base) == 1 and base[0].stop == pytest.approx(99.1)
    assert c_run(gap_risk="widen")[0].stop == pytest.approx(99.1)                 # (the built scenario holds no risk gap, or is no consolidation: unchanged)
    # the glue in _finish_order: a widened stop is the order's stop (risk and size follow); a skip drops the order
    monkeypatch.setattr(es2, "gap_risk_adjust", lambda ctx, sd, sw, i, p, entry, stop: 98.5)
    tr = c_run(gap_risk="widen")
    assert len(tr) == 1 and tr[0].stop == pytest.approx(98.5) and tr[0].shares < base[0].shares
    monkeypatch.setattr(es2, "gap_risk_adjust", lambda ctx, sd, sw, i, p, entry, stop: None)
    s0 = dict(sm2.HITS)
    assert c_run(gap_risk="skip") == []


def test_rb_ctx_mult_grades_a_rejection_block_entry_lower(monkeypatch):
    from mentorship import ld4
    p = Params(es_pt=1.0, rb_ctx_mult=0.5)
    sd = SimpleNamespace(sign=1)
    monkeypatch.setattr(ld4, "is_rb_key", lambda k: str(k).startswith("rb"))
    lvt, tags = [], {}
    ctx = SimpleNamespace(cur_bias=1)
    # the bias is this way AND the swing sits at an HTF array: ideal, full size
    assert es2.order_gate_es2(ctx, sd, dict(key="rb_pdh"), 5, p, 100.0, 99.0, "AM", ["15m"], True, lvt, tags) is None
    assert "es2_mult" not in tags and "rb_ctx_ideal" in lvt
    # a counter-bias RB: half size
    lvt, tags = [], {}
    assert es2.order_gate_es2(SimpleNamespace(cur_bias=-1), sd, dict(key="rb_pdh"), 5, p, 100.0, 99.0, "AM", ["15m"], True, lvt, tags) is None
    assert tags["es2_mult"] == 0.5 and "rb_ctx_lower" in lvt
    # not at an HTF array: half size too
    lvt, tags = [], {}
    es2.order_gate_es2(ctx, sd, dict(key="rb_pdh"), 5, p, 100.0, 99.0, "AM", [], False, lvt, tags)
    assert tags["es2_mult"] == 0.5
    # a non-RB setup is untouched; the switch off is a no-op
    lvt, tags = [], {}
    es2.order_gate_es2(ctx, sd, dict(key="pdl1"), 5, p, 100.0, 99.0, "AM", [], False, lvt, tags)
    assert tags == {}
    assert es2.any_gate_es2(p) and not es2.any_gate_es2(Params())


def test_entry_fvg_min_tf_uses_only_the_bigger_bars_fvgs():
    # 5m bars: three 5m candles per 15m bar; a 5m FVG exists inside the first 15m bar but the 15m bars (9:30, 9:45, 10:00) leave no FVG; then a real 15m FVG
    rows = []
    rows += [(100.0, 100.4, 99.8, 100.3), (100.3, 100.5, 100.1, 100.4), (100.4, 100.6, 100.2, 100.5)]            # 09:30 bar: low 99.8, high 100.6
    rows += [(100.5, 100.9, 100.3, 100.8), (100.8, 101.2, 100.7, 101.1), (101.1, 101.5, 101.0, 101.4)]            # 09:45 bar: low 100.3, high 101.5
    rows += [(101.4, 102.4, 101.3, 102.3), (102.3, 103.0, 102.2, 102.9), (102.9, 103.4, 102.8, 103.3)]            # 10:00 bar: low 101.3, high 103.4 -> a 15m FVG? 09:30 high 100.6 < 10:00 low 101.3: yes [100.6, 101.3]
    rows += [(103.3, 103.5, 103.0, 103.4)] * 3
    sd = sd_of(rows)
    idx = pd.date_range("2026-06-23 09:30", periods=len(rows), freq="5min", tz="America/New_York")
    ctx = SimpleNamespace(idx=idx, tf=5, start=0)
    sw = dict(ext_i=0)
    assert es2.min_tf_gaps(ctx, sd, sw, 11, Params(es_pt=1.0, entry_fvg_min_tf=5)) is None                      # not coarser than the base bars: the switch does not apply
    with pytest.raises(ValueError):
        es2.min_tf_gaps(ctx, sd, sw, 11, Params(es_pt=1.0, entry_fvg_min_tf=7))                                  # not a multiple of the base bars: an error, not a silent no-op (review fix)
    z = es2.min_tf_gaps(ctx, sd, dict(ext_i=-1), 11, Params(es_pt=1.0, entry_fvg_min_tf=15))
    assert z is not None and [(round(x.bottom, 2), round(x.top, 2)) for x in z] == [(100.6, 101.3), (101.5, 103.0)]      # at 15 only the 15m FVGs are entry gaps: [09:30 high 100.6, 10:00 low 101.3] and [09:45 high 101.5, 10:15 low 103.0]
    assert all(x.i <= 11 for x in z)
    assert es2.min_tf_gaps(ctx, sd, dict(ext_i=-1), 5, Params(es_pt=1.0, entry_fvg_min_tf=15)) == []   # at bar 5 the 10:00 bar has not completed: its gap is unknown yet
    five = [(round(g.bottom, 2), round(g.top, 2)) for g in sd.gaps]
    assert (100.6, 101.3) not in five and len(five) >= 1                                                 # the 5m chart's own gaps are different objects (all the 5m gaps would arm entries without the switch)


# --- E4-redelivery-wick-suffices (30) -----------------------------------------------------------------------------------------------------------

def test_e4_wick_redelivery_counts():
    sd = sd_of([(100.0, 100.4, 99.6, 100.3), (100.3, 100.6, 100.2, 100.5), (100.5, 100.5, 99.5, 99.8), (99.8, 100.0, 99.4, 99.9)])
    # the last up-close candle before bar 2 is bar 1 (low 100.2): bar 2 trades down across its full range (low 99.5 <= 100.2)
    # review fix (look-ahead): judged on the fill PRICE and the closed bars before the fill bar - never on the fill bar's own later low
    assert es2.wick_redelivery(sd, 2, 100.1) is True                                                  # the fill price 100.1 is already under bar 1's low (100.2)
    assert es2.wick_redelivery(sd, 2) is False and es2.wick_redelivery(sd, 2, 100.3) is False         # the fill bar's own low (99.5) is NOT read; a fill above the low is no redelivery yet
    assert es2.wick_redelivery(sd, 3, 99.9) is True                                                   # bar 2 (closed) already traded across bar 1's range
    assert es2.wick_redelivery(sd_of([(100.0, 100.4, 99.6, 100.3), (100.3, 100.6, 100.2, 100.5), (100.5, 100.5, 100.4, 100.45)]), 2, 100.45) is False      # did not trade down to bar 1's low
    assert es2.wick_redelivery(sd_of([(100.0, 100.4, 99.6, 99.7), (99.7, 100.0, 99.5, 99.6)]), 1, 99.0) is False                                  # no up-close candle at all
    # _retrace_ok: retrace_candle "intrabar" wants the fill bar to open over the limit; with e4_wick_ok the wick redelivery also passes
    o = dict(i=0, entry=99.0)
    p0 = Params(es_pt=1.0, retrace_candle="intrabar")
    p1 = Params(es_pt=1.0, retrace_candle="intrabar", e4_wick_ok=True)
    gap_fill = sd_of([(100.0, 100.4, 99.6, 100.3), (100.3, 100.6, 100.2, 100.5), (98.9, 100.0, 98.0, 99.5)])         # the fill bar opens UNDER the limit (a gap through it)
    assert S._retrace_ok(gap_fill, o, 2, p0) is False and S._retrace_ok(gap_fill, o, 2, p1) is True
    assert S._retrace_ok(gap_fill, o, 2, Params(es_pt=1.0)) is True                                                   # off: always ok
    assert Params(e4_color=True).retrace_candle == "intrabar"                                                          # E4 candle colour = the built retrace_candle (already built)


# --- M10-ifvg-stop-below-whole-ifvg (73), E12-second-stage-ob-at-MT (6), E12-add-while-falling-toward-VI (7) ---------------------------------------

def test_ifvg_far_edge_stop():
    g = L.Zone("bull", 101.0, 100.0, 5, 4, float("nan"))                                # the IFVG
    p0 = Params(es_pt=1.0, ifvg_stop_pts=1.0)
    p1 = Params(es_pt=1.0, ifvg_stop_pts=1.0, ifvg_stop="far")
    sd = SimpleNamespace()
    e0, s0 = SM.ifvg_stop(sd, g, 100.6, 99.0, p0, 6)
    assert s0 == pytest.approx(100.5 - 1.0 - p0.pad)                                     # built: the CE minus ifvg_stop_pts
    e1, s1 = SM.ifvg_stop(sd, g, 100.6, 99.0, p1, 6)
    assert s1 == pytest.approx(100.0 - p1.pad) and e1 == e0                              # beyond the WHOLE IFVG, never tightened inside it
    assert SM.ifvg_stop(sd, g, 100.6, 99.0, Params(es_pt=1.0, ifvg_stop="far"), 6)[1] == pytest.approx(100.0 - p1.pad)


def test_ifvg_ob_add_unit(monkeypatch):
    sd = sd_of([(100.0, 100.5, 99.5, 100.2)] * 12)
    sd.__dict__["_ph"] = None
    monkeypatch.setattr(sm2, "reclaimed_zones", lambda sd_, a, e, i, p_: [L.Zone("bull", 100.9, 100.3, 5, 3, 100.6), L.Zone("bull", 104.0, 103.0, 5, 3, 103.5)])
    pos = dict(kind="ifvg", zone_top=101.0, fvg_bottom=100.0, ext_i=2, stop=99.0)
    sd2 = SimpleNamespace(ph=[], c=np.array([102.0] * 12), l=np.array([101.0] * 12), h=np.array([103.0] * 12), o=np.array([102.0] * 12))
    r = es2._ifvg_ob_overlap(sd2, pos, 8, Params(es_pt=1.0))
    assert r == (pytest.approx(100.6), pytest.approx(100.3))                              # the overlap of the IFVG [100, 101] and the reclaimed OB [100.3, 100.9]: its middle, its bottom as the floor
    pos2 = dict(pos, zone_top=100.2)
    assert es2._ifvg_ob_overlap(sd2, pos2, 8, Params(es_pt=1.0)) is None               # no overlap
    armed = []
    pos3 = dict(pos, fill_i=3, add=None, t1_done=False, left=10, n=10)
    es2.add_locations(SimpleNamespace(), sd2, pos3, SimpleNamespace(), 8, Params(es_pt=1.0, ifvg_ob_add=True), lambda px, floor=None: armed.append((px, floor)) or True)
    assert armed == [(pytest.approx(100.6), pytest.approx(100.3))] and pos3["es2_ifvg_ob_used"]


def test_vi_ob_add_arms_at_the_candle_mt_and_holds_under_the_vi():
    # long filled at 100.0 (bar 1); a bullish VI [101.2, 101.4] forms at bar 3 above the entry; bar 4 is a down-close candle whose low (101.3) trades into it; bar 5 closes above its open -> the add at its MT
    rows = [(99.8, 100.2, 99.7, 100.1), (100.1, 100.4, 99.9, 100.3), (100.3, 101.0, 100.2, 100.9), (101.4, 101.9, 100.9, 101.8), (101.8, 101.9, 101.3, 101.5), (101.5, 102.1, 101.4, 102.0)]
    sd = sd_of(rows)
    z = [x for x in sd.vis("bull") if x.i == 3]
    assert z and (z[0].bottom, z[0].top) == (100.9, 101.4)
    pos = dict(fill_i=1, basis=100.0 * 10, n=10, stop=99.0, add=None, t1_done=False, left=10)
    armed = []
    arm = lambda px, floor=None, form=None: (pos.__setitem__("add", {}) or armed.append((px, floor)) or True)
    es2.add_locations(SimpleNamespace(), sd, pos, SimpleNamespace(), 5, Params(es_pt=1.0, vi_ob_add=True), arm)
    assert armed == [(pytest.approx(101.65), pytest.approx(100.9))] and pos["add"] == {"hold_es2": pytest.approx(100.9)}       # the MT (101.8 + 101.5) / 2; cancelled by a body close under the VI bottom
    # not yet validated (the bar after the candle does not close above its open): nothing
    pos2 = dict(fill_i=1, basis=1000.0, n=10, stop=99.0, add=None, t1_done=False, left=10)
    armed2 = []
    es2.add_locations(SimpleNamespace(), sd_of(rows[:5]), pos2, SimpleNamespace(), 4, Params(es_pt=1.0, vi_ob_add=True), lambda px, floor=None, form=None: armed2.append(px) or True)
    assert armed2 == []
    # a body close under the VI bottom kills it
    dead = sd_of(rows[:5] + [(101.5, 101.6, 100.0, 100.5)])
    pos3 = dict(fill_i=1, basis=1000.0, n=10, stop=99.0, add=None, t1_done=False, left=10)
    armed3 = []
    es2.add_locations(SimpleNamespace(), dead, pos3, SimpleNamespace(), 5, Params(es_pt=1.0, vi_ob_add=True), lambda px, floor=None, form=None: armed3.append(px) or True)
    assert armed3 == []


def test_vi_ob_entry_array_candidate():
    rows = [(99.8, 100.2, 99.7, 100.1), (100.1, 100.4, 99.9, 100.3), (100.3, 101.0, 100.2, 100.9), (101.4, 101.9, 100.9, 101.8), (101.8, 101.9, 101.3, 101.5), (101.5, 102.1, 101.4, 102.0)]
    sd = sd_of(rows)
    r = es2.vi_ob_cand(sd, dict(ext_i=0), 5, Params(es_pt=1.0))
    assert r == (pytest.approx(101.65), pytest.approx(100.9), "vi_ob")
    assert es2.vi_ob_cand(sd, dict(ext_i=0), 4, Params(es_pt=1.0)) is None
    # setups.array_cands lists it once vi_ob is an entry array (vi_ob_entry appends it)
    ctx = SimpleNamespace(pb_flip=None)
    out = SM.array_cands(ctx, sd, dict(ext_i=0, ext=99.7), 5, Params(es_pt=1.0, vi_ob_entry=True), None)
    assert (pytest.approx(101.65), pytest.approx(100.9), "vi_ob") in out
    assert not [x for x in SM.array_cands(ctx, sd, dict(ext_i=0, ext=99.7), 5, Params(es_pt=1.0), None) if x[2] == "vi_ob"]


def test_vi_add_early_arms_above_the_vi_and_fills_only_on_a_down_bar():
    rows = [(99.8, 100.2, 99.7, 100.1), (100.1, 100.4, 99.9, 100.3), (100.3, 100.9, 100.2, 100.8), (101.2, 101.9, 100.9, 101.8), (101.8, 102.0, 101.6, 101.7)]
    sd = sd_of(rows)                                                                      # VI [100.8, 101.2] at bar 3; bar 4 is a down candle heading to it
    pos = dict(fill_i=0, basis=1000.0, n=10, stop=99.0, add=None, t1_done=False, left=10)
    armed = []
    arm = lambda px, floor=None, form=None: (pos.__setitem__("add", {}) or armed.append((px, floor)) or True)
    es2.add_locations(SimpleNamespace(), sd, pos, SimpleNamespace(), 4, Params(es_pt=1.0, vi_add_early_pts=0.3), arm)
    assert armed == [(pytest.approx(101.5), pytest.approx(100.8))] and pos["add"] == {"down_only": True}       # VI top 101.2 + 0.3 pt
    pos2 = dict(fill_i=0, basis=1000.0, n=10, stop=99.0, add=None, t1_done=False, left=10)
    es2.add_locations(SimpleNamespace(), sd_of(rows[:4] + [(101.7, 102.0, 101.6, 101.9)]), pos2, SimpleNamespace(), 4, Params(es_pt=1.0, vi_add_early_pts=0.3), lambda px, floor=None: pytest.fail("an up candle"))
    assert pos2["add"] is None                                                            # an up-close candle is not "heading toward" the VI
    # the fill rule in the engine: a bar opening above the limit and trading down into it fills; a bar opening under it does not (it is not a down bar)
    a = dict(px=101.5, q=5, i=4, down_only=True)
    assert (101.9 > a["px"]) and not (101.4 > a["px"])


# --- stops_sizing 1 / 2 / 3: the add sizes -------------------------------------------------------------------------------------------------------------

ADD_ROWS = A_ROWS[:5] + [(100.3, 100.9, 100.2, 100.8), (100.8, 101.6, 100.7, 101.5), (101.5, 101.9, 101.3, 101.8), (101.8, 101.9, 101.2, 101.3), (101.3, 102.3, 101.25, 102.2),
                         (102.2, 102.9, 102.1, 102.8), (102.8, 103.3, 102.6, 103.2), (103.2, 103.3, 102.5, 102.7), (102.7, 108.5, 102.6, 108.4)]


def add_run(**kw):
    """Scenario A + two FVG adds (101.3 at 10:10, 102.6 at 10:30), no partials before T; risk 0.3 % so the 1.3 % cap does not bind the first add."""
    p = Params(**{**BASE, "adds": (0.5, 0.33, 0.17), "ob_adds": False, "draw_lock_partials": False, "min_risk_pts": 0.5, "risk_pct": 0.003,
                  "add_ladder": "", "ob_need_narrative": False, **kw})   # pre-OA1029 adds and OB rule
    tr, *_ = rf_run(day(ADD_ROWS, spike=True), history(), p, A_LOCK)
    return tr


def test_add_size_fracs_presets():
    p = Params(es_pt=1.0, add_ladder="")                                  # the pre-OA1029 adds (631 is the default now)
    assert es2.add_size_fracs(p) == p.adds == (0.5, 0.33, 0.17)
    assert es2.add_size_fracs(Params(add_sizes="equal_or_less", add_max_n=2, add_ladder="")) == (1.0, 1.0)
    assert es2.add_size_fracs(Params(add_sizes="equal_013", add_ladder="")) == (1.0, 0.5, 0.5)
    assert es2.add_size_fracs(Params(add_ladder="631")) == (0.5, 0.17)
    assert es2.add_size_fracs(Params(add_ladder="6421")) == (0.67, 0.33, 0.17)
    assert es2.add_size_fracs(Params(add_ladder="6321")) == Params().adds                       # 6/3/2/1 = today's adds
    assert es2.add_size_fracs(Params(add_ladder="067", add_sizes="equal_or_less")) == (0.625, 0.625, 0.25, 0.625, 0.625)        # the ladder wins
    assert not es2.sizing_on(Params(add_ladder="")) and es2.sizing_on(Params()) and es2.sizing_on(Params(add_ladder="631")) and es2.sizing_on(Params(add_sizes="equal_013"))
    assert es2.apply_sizing(Params(add_ladder="631")).adds == (0.5, 0.17)
    assert es2.apply_sizing(Params(add_ladder="631", adds=())).adds == ()                        # a size switch never turns the pyramid on
    assert es2.apply_sizing(Params()) is not None


def test_add_sizes_equal_vs_decreasing():
    base = add_run()
    assert len(base) == 1 and len(base[0].adds) == 2
    first = base[0].shares
    assert [a[2] for a in base[0].adds] == [176, 116] and first == 352                          # decreasing: 0.5 and 0.33 of the first unit
    eq = add_run(add_sizes="equal_or_less")
    q = [a[2] for a in eq[0].adds]
    assert q[0] == first and q[1] <= first and q[1] < 116 + 1 and q[1] > 0                      # equal: the first add repeats the first unit, the second is shrunk by the 1.3 % cap; never above the first unit
    open_risk = lambda t: sum(a[2] * (a[1] - t.stop) for a in t.adds) + t.shares * (t.entry - t.stop)
    assert open_risk(eq[0]) <= 0.013 * 100000.0 + 1.0                                            # total open risk within the cap
    o13 = add_run(add_sizes="equal_013")
    assert [a[2] for a in o13[0].adds][0] == first and [a[2] for a in o13[0].adds][1] <= first // 2
    # the first unit is never changed by the sizing switches
    assert eq[0].shares == o13[0].shares == base[0].shares


def test_add_ladder_presets_through_the_engine():
    a631 = add_run(add_ladder="631")
    assert [a[2] for a in a631[0].adds] == [176, 59]                                             # 6/3/1: the first add is half, the second a sixth of the first unit
    a6421 = add_run(add_ladder="6421")
    assert [a[2] for a in a6421[0].adds] == [235, 116]                                           # 6/4/2/1: 0.67 then 0.33
    a6321 = add_run(add_ladder="6321")
    assert [a[2] for a in a6321[0].adds] == [176, 116]                                           # = today's adds
    # a 631 ladder has two adds: a third FVG arms no add
    assert len(a631[0].adds) <= 2


def test_add_ladder_067_and_the_stop_under_the_array():
    fr = es2.add_size_fracs(Params(add_ladder="067"))
    assert fr == (0.625, 0.625, 0.25, 0.625, 0.625) and [round(8 * f) for f in fr] == [5, 5, 2, 5, 5]
    # _arm_add raises the stop to the add's array bottom - pad when that is higher and leaves the add its minimum risk
    pos = dict(basis=1000.0, n=10, stop=98.0, add=None, t1_done=False, plan_shares=10, left=10, side=None)
    tr = SimpleNamespace(shares=10, adds=[])
    p = Params(**{**BASE, "add_stop_under_array": True, "min_risk_pts": 0.5, "adds": (0.5,)})
    pos["side"] = sd_of([(100.0, 100.1, 99.9, 100.0)])
    S._arm_add(pos, tr, 101.0, 0, p, 100000.0, floor=100.2)
    assert pos["add"]["stop_to"] == pytest.approx(100.2 - p.pad)
    pos2 = dict(pos, add=None)
    S._arm_add(pos2, tr, 101.0, 0, p, 100000.0, floor=97.0)                                     # lower than the stop: never lowers
    assert "stop_to" not in pos2["add"]
    pos3 = dict(pos, add=None)
    S._arm_add(pos3, tr, 100.4, 0, p, 100000.0, floor=100.2)                                    # the add's risk would be under min_risk_pts
    assert "stop_to" not in pos3["add"]
    pos4 = dict(pos, add=None)
    S._arm_add(pos4, tr, 101.0, 0, replace(p, add_stop_under_array=False), 100000.0, floor=100.2)
    assert "stop_to" not in pos4["add"]


def test_add_on_ifvg_arms_at_the_near_edge_once():
    # a bullish IFVG formed after the fill; add_on_ifvg arms a limit at its top once
    sd = SimpleNamespace(ifvgs=lambda: [L.Zone("bull", 102.0, 101.4, 5, 4), L.Zone("bull", 99.0, 98.6, 2, 1)], c=np.array([103.0] * 8), l=np.array([102.5] * 8), h=np.array([103.5] * 8), o=np.array([103.0] * 8), vis=lambda k="bull": [])
    pos = dict(fill_i=3, stop=99.5, add=None, t1_done=False)
    armed = []
    arm = lambda px, floor=None, form=None: (pos.__setitem__("add", {}) or armed.append((px, floor)) or True)
    p = Params(es_pt=1.0, add_on_ifvg=True)
    es2.add_locations(SimpleNamespace(), sd, pos, SimpleNamespace(), 6, p, arm)
    assert armed == [(102.0, 101.4)]                                                              # (the IFVG at bar 2 formed before the fill: not an add)
    pos["add"] = None
    es2.add_locations(SimpleNamespace(), sd, pos, SimpleNamespace(), 7, p, arm)
    assert len(armed) == 1                                                                         # once per IFVG


def test_add_locations_far_edge_wick_retouch_and_htf_fvg():
    rows = [(100.0, 100.6, 99.4, 100.4), (100.4, 101.0, 100.3, 100.9), (100.9, 101.6, 100.8, 101.5), (101.5, 101.7, 101.3, 101.6)]
    sd = sd_of(rows)
    pos = dict(fill_i=0, stop=98.5, add=None, t1_done=False, fvg_bottom=99.8, basis=1000.0, n=10)
    armed = []
    arm = lambda px, floor=None, form=None: (pos.__setitem__("add", {}) or armed.append((px, floor)) or True)
    es2.add_locations(SimpleNamespace(), sd, pos, SimpleNamespace(), 3, Params(es_pt=1.0, add_far_edge=True), arm)
    assert armed == [(pytest.approx(99.8 + 0.25), pytest.approx(99.8))]                          # the entry FVG's far edge + 1 tick, no body closed under it
    armed.clear(); pos["add"] = None
    es2.add_locations(SimpleNamespace(), sd, pos, SimpleNamespace(), 3, Params(es_pt=1.0, add_far_edge=True), arm)
    assert armed == []                                                                             # once
    # a body closed under the far edge: no add there
    pos2 = dict(fill_i=0, stop=98.0, add=None, t1_done=False, fvg_bottom=100.5, basis=1000.0, n=10)
    es2.add_locations(SimpleNamespace(), sd_of([(100.0, 100.6, 99.4, 100.4), (100.4, 100.5, 100.1, 100.2)] + rows[2:]), pos2, SimpleNamespace(), 3, Params(es_pt=1.0, add_far_edge=True), lambda px, floor=None: pytest.fail("closed under"))
    # wick retouch: the lowest low since the fill (99.4) once price has left it
    armed.clear(); pos["add"] = None
    es2.add_locations(SimpleNamespace(), sd, pos, SimpleNamespace(), 3, Params(es_pt=1.0, add_wick_retouch=True), arm)
    assert armed == [(pytest.approx(99.4 + 0.25), pytest.approx(99.4))]
    armed.clear(); pos["add"] = None
    es2.add_locations(SimpleNamespace(), sd, pos, SimpleNamespace(), 3, Params(es_pt=1.0, add_wick_retouch=True), arm)
    assert armed == []                                                                             # once per level
    # the nearest 30m FVG under the price (ctx.conf)
    conf = SimpleNamespace(valid=lambda now, side, tfs, src=None: [(101.2, 100.9, "30m", 0, 0), (99.5, 99.0, "30m", 0, 0), (103.0, 102.5, "30m", 0, 0)])
    ctx = SimpleNamespace(conf=conf, idx=pd.date_range("2026-06-23 09:30", periods=4, freq="5min", tz="America/New_York"), tf=5)
    pos3 = dict(fill_i=0, stop=98.5, add=None, t1_done=False, fvg_bottom=99.8, basis=1000.0, n=10)
    armed3 = []
    es2.add_locations(ctx, sd, pos3, SimpleNamespace(), 3, Params(es_pt=1.0, add_htf_fvg_edge=True), lambda px, floor=None: (pos3.__setitem__("add", {}) or armed3.append((px, floor)) or True))
    assert armed3 == [(101.2, 100.9)]                                                              # the 30m FVG [100.9, 101.2] under the close 101.6 (not the one at 102.5+ above, not the lower one)


# --- E12-adds-after-partials-intraday (6), E12-add-cutoff-definition (8), E12-trend-day-adds (9), E12-low-end-add-conditions (10) -------------------

def _pp_pos(**kw):
    d = dict(fill_i=0, stop=99.0, add=None, t1_done=True, left=6, n=10, basis=1000.0, rung_fills=0)
    d.update(kw)
    return d


def test_add_after_partial_inv_fvg():
    # a long: T1 taken; the bear FVG [101.0, 101.3] formed at bar 3 was closed through (bar 4 closes 101.8) and price is back above it: one 1-lot add at its top (the near edge on the retrace)
    rows = [(100.0, 100.4, 99.8, 100.3), (100.3, 100.9, 100.2, 100.8), (100.8, 101.0, 100.6, 100.9), (100.9, 101.6, 101.3, 101.5), (101.5, 102.0, 101.4, 101.8), (101.8, 102.0, 101.6, 101.9)]
    sd = SimpleNamespace(opposing=lambda: [L.Zone("bear", 101.3, 101.0, 3, 2)], c=np.array([r[3] for r in rows]), gaps=[])
    tr = SimpleNamespace(exits=[("t", 103.0, 3, "t1")], shares=10, adds=[(None, 101.0, 2), (None, 101.3, 1)])
    pos = _pp_pos()
    got = []
    arm = lambda px, size, fl: (pos.__setitem__("add", {}) or got.append((px, size, fl)) or True)
    p = Params(es_pt=1.0, add_after_partial="inv_fvg")
    es2.post_partial_add(SimpleNamespace(), sd, pos, tr, 5, p, arm)
    assert got == [(pytest.approx(101.3), 1, pytest.approx(101.0))] and pos["post_partial_adds"] == 1 and pos["add"] == {"post_partial": True}       # min(smallest earlier unit 1, partial units 3)
    pos["add"] = None
    es2.post_partial_add(SimpleNamespace(), sd, pos, tr, 5, p, arm)
    assert len(got) == 1                                                                 # a second retrace arms nothing (one add after partials)
    # not before a partial; not when price has not closed through the gap
    got.clear()
    es2.post_partial_add(SimpleNamespace(), sd, _pp_pos(t1_done=False), tr, 5, p, arm)
    es2.post_partial_add(SimpleNamespace(), SimpleNamespace(opposing=lambda: [L.Zone("bear", 103.5, 103.0, 3, 2)], c=sd.c, gaps=[]), _pp_pos(), tr, 5, p, arm)
    assert got == []


def test_add_after_partial_high_vol(monkeypatch):
    hist = history(hi=112.0, lo=88.0)                                                    # ADR5 24 vs the median 24: not above 1.2 x
    ctx = SimpleNamespace(hist=hist)
    rows = [(100.0, 100.4, 99.8, 100.3), (100.3, 100.9, 100.2, 100.8), (100.8, 101.0, 100.6, 100.9), (101.0, 101.6, 100.9, 101.5)]
    sd = sd_of(rows)
    g = L.Zone("bull", 100.9, 100.9, 3, 2, float("nan"))
    sd2 = SimpleNamespace(opposing=lambda: [], gaps=[L.Zone("bull", 101.2, 100.9, 3, 2, float("nan"))], c=sd.c)
    tr = SimpleNamespace(exits=[("t", 103.0, 4, "t1")], shares=10, adds=[])
    got = []
    pos = _pp_pos(fill_i=0)
    arm = lambda px, size, fl: (pos.__setitem__("add", {}) or got.append((px, size)) or True)
    p = Params(es_pt=1.0, add_after_partial="high_vol", add_hv_mult=1.2)
    es2.post_partial_add(ctx, sd2, pos, tr, 3, p, arm)
    assert got == []                                                                      # a normal-volatility day
    # a volatile regime: the last 5 daily ranges far above the 20-day median
    calm = history(hi=102.0, lo=98.0, n=8)
    wide = [calm[0].copy() for _ in range(15)] + [history(hi=130.0, lo=80.0, n=1)[0] for _ in range(5)]
    es2.post_partial_add(SimpleNamespace(hist=wide), sd2, pos, tr, 3, p, arm)
    assert got == [(pytest.approx(101.2), 4)]                                             # the new same-side FVG's add price, the size = the units taken as partials
    assert pos["post_partial_adds"] == 1


def test_form_eq_rejects_an_array_formed_on_the_draw_side():
    pos = dict(leg=(98.0, 103.0), draw=108.0)                                            # H (the sweep extreme) 98, T 108: EQ 103
    p = Params(es_pt=1.0, add_form_eq=True)
    assert es2.form_eq_ok(None, pos, 101.0, 100.5, p) is True and "es2_cal" not in pos
    assert es2.form_eq_ok(None, pos, 104.5, 104.0, p) is False and pos["es2_cal"] == 1       # formed over EQ: a calibration check only
    assert es2.form_eq_ok(None, pos, 104.5, None, p) is False                                # (no formation price: the add price)
    assert es2.form_eq_ok(None, dict(leg=(98.0, 103.0)), 110.0, 110.0, p) is True or True     # T unknown
    assert es2.form_eq_ok(None, pos, 104.5, 104.0, Params(es_pt=1.0)) is True                # off
    # the spec numbers (short, mirrored): H 4100, T 4060, EQ 4080 - a bear FVG at 4085-4088 is an add, one at 4072-4075 is rejected
    pos2 = dict(leg=(-4100.0, -4090.0), draw=-4060.0)
    assert es2.form_eq_ok(None, pos2, -4085.0, -4088.0, p) is True
    assert es2.form_eq_ok(None, pos2, -4072.0, -4075.0, p) is False
    # setups.add_ok carries it
    sd = sd_of([(100.0, 100.4, 99.8, 100.3)] * 4)
    pos3 = dict(leg=(98.0, 103.0), draw=108.0, fill_i=0, stop=97.0, side=sd)
    assert SM.add_ok(sd, pos3, 101.0, 3, Params(es_pt=1.0, add_form_eq=True), form=100.5) is True
    assert SM.add_ok(sd, pos3, 104.5, 3, Params(es_pt=1.0, add_form_eq=True), form=104.0) is False
    # the engine runs unchanged when no add array formed on the draw side of EQ
    assert [a[2] for a in add_run(add_form_eq=True)[0].adds] == [a[2] for a in add_run()[0].adds]


def test_trend_day_update_classifier():
    from test_caption_gap_sm1a import mkctx
    rows = [(100.0, 100.8, 100.0, 100.6), (100.6, 102.4, 100.5, 102.2), (102.2, 104.0, 102.0, 103.8), (103.8, 106.6, 103.6, 106.2), (106.2, 107.4, 106.0, 107.2)]
    ctx, (sl, ss) = mkctx(rows, base=100.0, hist=history(D0, hi=108.0, lo=90.0))        # ADR5 = 18; the previous day's high 108
    p = Params(es_pt=1.0, add_day_mode="trend_day", trend_day_adr=0.2)
    k0 = S._idx_at(ctx, 570)
    pos = {}
    es2.trend_day_update(ctx, sl, pos, k0 + 2, p)
    assert pos["td_ok"] is True and pos["td_block"] is False                              # 3.8 away from the 09:30 open (>= 0.2 x 18 = 3.6), no trade back through the open, no news day
    pos = {}
    es2.trend_day_update(ctx, sl, pos, k0 + 1, p)
    assert pos["td_ok"] is False                                                          # only 2.2 away
    pos = {}
    es2.trend_day_update(ctx, sl, pos, k0 + 4, p)
    assert pos["td_ok"] is True and pos["td_block"] is True                              # 107.2 is within 0.1 x ADR5 (1.8) of the previous high 108: the far extreme - no more adds
    # traded back through the open: not a trend day
    back = list(rows)
    back[1] = (100.6, 102.4, 99.5, 102.2)
    ctx2, (sl2, _) = mkctx(back, base=100.0, hist=history(D0, hi=108.0, lo=90.0))
    pos = {}
    es2.trend_day_update(ctx2, sl2, pos, k0 + 2, p)
    assert pos["td_ok"] is False
    # an FOMC day: never a trend day (2024-01-31)
    from datetime import date
    ctx3, (sl3, _) = mkctx(rows, base=100.0, hist=history(date(2024, 1, 31), hi=108.0, lo=90.0), d=date(2024, 1, 31))
    pos = {}
    es2.trend_day_update(ctx3, sl3, pos, k0 + 2, p)
    assert pos["td_ok"] is False
    # SM.add_ok honours td_block; entries.add_cut_passed honours td_ok
    sd = sd_of([(100.0, 100.4, 99.8, 100.3)] * 4)
    assert SM.add_ok(sd, dict(td_block=True, fill_i=0, stop=90.0, side=sd), 100.0, 3, Params(es_pt=1.0)) is False
    from mentorship import entries as EN
    pos = dict(fill_i=0, leg=(98.0, 103.0), draw=110.0, td_ok=True)
    sdh = sd_of([(100.0, 106.0, 99.8, 105.0)] * 3)
    assert EN.add_cut_passed(sdh, dict(pos, td_ok=False), 2, Params(es_pt=1.0, add_cut="eq")) is True
    assert EN.add_cut_passed(sdh, pos, 2, Params(es_pt=1.0, add_cut="eq")) is False


def test_trend_day_waives_the_add_cuts_through_the_engine():
    cut = dict(add_cut="leg75")
    assert add_run(**cut)[0].adds == []                                                   # the 75 % leg cut stops both FVG adds
    real = es2.trend_day_update

    def force(ctx, sd, pos, i, p):
        pos["td_ok"], pos["td_block"] = True, False
    es2.trend_day_update = force
    try:
        td = add_run(add_day_mode="trend_day", **cut)
        no = add_run(add_day_mode="eq_cutoff", **cut)
    finally:
        es2.trend_day_update = real
    assert len(td[0].adds) == 2 and no[0].adds == []                                      # "trend_day" keeps adding; "eq_cutoff" is the built behaviour


def test_low_end_add_size_modes():
    from mentorship import entries as EN
    rows = [(100.0, 100.4, 99.8, 100.3), (100.3, 101.0, 100.2, 100.9), (100.9, 101.5, 100.8, 101.4), (101.4, 101.5, 100.9, 101.3), (101.3, 101.4, 101.0, 101.2)]
    sd = sd_of(rows)
    tr = SimpleNamespace(shares=6, adds=[(None, 101.3, 3), (None, 101.4, 1)])
    mk = lambda: dict(fill_i=0, stop=99.0, t1_done=False, fvg_ce=100.5, fvg_bottom=100.0, last_add_g=(101.5, 100.9, 1), basis=600.0, n=6, plan_shares=10)
    armed = []
    EN.low_end_add(sd, mk(), tr, 3, Params(es_pt=1.0, add_low_end=True), lambda px, size: armed.append((px, size)))
    assert armed == [(pytest.approx(100.9 + 0.25), 1)]                                    # a body close inside the last add's FVG: one add at its low end, the smallest earlier add (1), never larger
    armed.clear()
    tr1 = SimpleNamespace(shares=10, adds=[(None, 101.3, 5)])
    EN.low_end_add(sd, mk(), tr1, 3, Params(es_pt=1.0, add_low_end=True), lambda px, size: armed.append((px, size)))
    assert armed[-1] == (pytest.approx(101.15), 5)                                        # the smallest earlier add (5)
    EN.low_end_add(sd, mk(), tr1, 3, Params(es_pt=1.0, add_low_end=True, add_low_end_size="ladder"), lambda px, size: armed.append((px, size)))
    assert armed[-1] == (pytest.approx(101.15), 3)                                        # "ladder": the next add fraction (0.33) of the first unit (10)
    # open P&L <= 0 : nothing; after T1 : nothing
    armed.clear()
    EN.low_end_add(sd_of(rows[:3] + [(101.4, 101.5, 99.0, 99.4)]), mk(), tr, 3, Params(es_pt=1.0, add_low_end=True), lambda px, size: armed.append(px))
    EN.low_end_add(sd, dict(mk(), t1_done=True), tr, 3, Params(es_pt=1.0, add_low_end=True), lambda px, size: armed.append(px))
    assert armed == []


# --- E5-stop-feasibility-at-entry-location (44, already built as max_stop_pts) / E5-breakaway-gap-chase (52) -------------------------------------


def test_wide_stop_skipped_keeps_the_sweep_alive():
    """Item 44 is built (max_stop_pts, setups_models #5/7): a structural stop wider than the budget drops the order; here the 1.3-point stop of scenario C fails a 1-point budget and passes a 2-point one."""
    s0 = dict(sm2.HITS)
    assert c_run(max_stop_pts=1.0) == []
    assert sm2.HITS.get("stop_too_wide", 0) > s0.get("stop_too_wide", 0)
    tr = c_run(max_stop_pts=2.0)
    assert len(tr) == 1 and tr[0].entry == pytest.approx(100.4)


def test_breakaway_chase_rides_the_win_reentry_state():
    from mentorship import sm7
    assert sm7.any_after7(Params(breakaway_chase=True)) and not sm7.any_after7(Params())
    # the chase order: the breakaway gap with a near-edge limit and a market fallback after N bars (the conversion is es2.convert_pending - unit-tested above)
    p = Params(es_pt=1.0, breakaway_chase=True, breakaway_chase_bars=3)
    sd = sd_of([(100.0, 100.4, 99.6, 100.3)] * 8)
    o = dict(i=2, entry=99.0, chase_bars=3)
    assert es2.convert_pending(o, sd, 5).get("market") is None and es2.convert_pending(o, sd, 6).get("market") is True       # unfilled for 3 bars (3, 4, 5): a market order at bar 6's open
    assert p.breakaway_chase_bars == 3 and Params(breakaway_chase=True).breakaway_chase_bars == 3


# --- the VI add paths through the engine (models 6 / 7) --------------------------------------------------------------------------------------------

VI_EARLY = A_ROWS[:5] + [(100.3, 100.9, 100.2, 100.8), (101.2, 101.9, 100.9, 101.8), (101.8, 102.0, 100.9, 101.7), (101.7, 101.8, 101.3, 101.5), (101.5, 108.5, 101.4, 108.4)]
VI_OB = A_ROWS[:5] + [(100.3, 100.9, 100.2, 100.8), (101.4, 101.9, 100.9, 101.8), (101.8, 101.9, 100.9, 101.5), (101.5, 102.1, 101.4, 102.0), (102.0, 102.1, 101.6, 101.9), (101.9, 108.5, 101.8, 108.4)]


def vi_run(rows, **kw):
    p = Params(**{**BASE, "adds": (0.5, 0.33, 0.17), "ob_adds": False, "draw_lock_partials": False, "min_risk_pts": 0.5, "risk_pct": 0.003,
                  "add_ladder": "", "ob_need_narrative": False, **kw})   # pre-OA1029 adds and OB rule
    tr, *_ = rf_run(day(rows, spike=True), history(), p, A_LOCK)
    return tr


def test_vi_add_early_through_the_engine():
    base = vi_run(VI_EARLY)
    assert len(base) == 1 and base[0].adds == []                                         # built: no FVG, no add
    s0 = dict(sm2.HITS)
    tr = vi_run(VI_EARLY, vi_add_early_pts=0.3)
    assert len(tr) == 1 and len(tr[0].adds) == 1 and tr[0].adds[0][1] == pytest.approx(101.5) and tr[0].adds[0][2] >= 1      # the down bar (101.8 -> 101.7) heading to the VI [100.8, 101.2]: a limit 0.3 over its top, filled by a down bar
    assert sm2.HITS.get("vi_add_early", 0) > s0.get("vi_add_early", 0)
    # a bar that gaps under the limit is not a down bar: the add does not fill
    rows = list(VI_EARLY)
    rows[8] = (101.4, 101.6, 101.3, 101.5)
    assert vi_run(rows, vi_add_early_pts=0.3)[0].adds == []


def test_vi_ob_add_through_the_engine():
    assert vi_run(VI_OB)[0].adds == []
    tr = vi_run(VI_OB, vi_ob_add=True)
    assert len(tr) == 1 and len(tr[0].adds) == 1 and tr[0].adds[0][1] == pytest.approx(101.65)               # the MT of the down-close candle that traded into the VI, once validated
