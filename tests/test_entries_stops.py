"""Package entries_stops_sizing (rule_coverage.md section 3, 45 items): unit tests for the new
helpers, hand-made one-day scenarios through run_day (the real engine path) and no-look-ahead
runs (full vs truncated) covering every new switch. The ES tests skip when the data is missing."""
import warnings
from dataclasses import fields, replace
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from mentorship import backtest as B, entries as EN, levels as L, strategy as S, study
from mentorship.strategy import Params
from dataclasses import dataclass as _oa_dc


@_oa_dc
class Params(Params):   # OA1029: these tests were written for the pre-build engine and exercise other rules - every OA1029 default back at its old value
    __annotations__ = {k: object for k in __import__('mentorship.study', fromlist=['OA1029_OLD']).OA1029_OLD}
    locals().update(__import__('mentorship.study', fromlist=['OA1029_OLD']).OA1029_OLD)

from test_review_fixes import A_LOCK, A_ROWS, BASE, D0, day, history, mirror, run  # noqa: E402  (shared scenario builders)

ES = Path("data/mentorship/ES_5min_db.csv").exists()
FUT = dict(es_pt=1.0, lot=1, max_notional=1e12, cost_per_share=0.1)
SYN = dict(es_pt=0.09, use_bias=False, min_draw_pts=0, leg_pd=0)
POST = dict(ob_entry="post_mss", draw_lock="off")
B_POST = dict(BASE, ob_entry="post_mss", draw_lock="off", htf_resist_cap=False, news_wait="off",
              min_draw_pts=0.0, leg_pd=0.0)
B_ROWS = [(101.0, 101.2, 99.0, 99.2), (99.2, 99.3, 98.6, 98.8), (98.8, 100.4, 98.7, 100.3),
          (100.3, 101.0, 100.1, 100.4), (100.4, 100.5, 99.3, 99.4), (99.4, 99.5, 98.0, 98.2),
          (98.2, 100.0, 98.1, 99.9), (99.9, 101.6, 99.0, 101.5), (101.5, 102.5, 101.3, 102.3),
          (102.3, 102.6, 100.5, 100.8), (100.8, 103.0, 100.2, 102.9), (102.9, 108.0, 102.8, 107.9)]
ADD_ROWS = A_ROWS[:5] + [(100.3, 100.9, 100.2, 100.8), (100.8, 101.5, 101.0, 101.4),
                         (101.4, 101.8, 101.3, 101.7), (101.7, 101.8, 100.95, 101.5),
                         (101.5, 103.0, 101.4, 102.9), (102.9, 104.0, 102.8, 103.9),
                         (103.9, 108.5, 103.8, 108.4)]

NEW_FIELDS = (
    "tick_pts", "stop_tick_pts", "stop_pad_ticks", "ce_stop_pad_pts", "nfp_stop_wide", "mohawk_ticks",
    "sweep_body", "stop_all_ineff", "stop_ineff_wick", "mt_close_stop", "ob_zone", "ob_stub_frac",
    "ob_disp_mult", "ob_cisd", "ob_targets_1m", "opp_ob_mt", "vi_hold", "engage_range_pts", "iofed_ref",
    "entry_ladder_fracs", "sb_entry", "run_cancel", "entry_order", "add_order", "fill_through",
    "exit_fill_through", "retrace_candle", "no_new_extreme", "evolve_fvg", "wait_structural", "mo_tol_pts",
    "leg_pd_min", "ote_cancel", "leg_depth_tag", "prop_entry", "prop_mt_exit", "prop_zone", "ob_entries",
    "vi_entries", "irl_entries", "erl_range_swings", "erl_exits_only", "size_rules", "size_down",
    "size_up_rules", "size_up", "htf_target_pts", "low_prob_tests", "loss_halving", "halving_floor",
    "winback_frac", "no_max_after_loss", "after_loss_mult", "after_loss_adds", "max_contracts_initial",
    "max_contracts_total", "units_per_contract", "add_points", "add_arrays", "add_hold", "add_htf_tfs",
    "add_low_end", "add_fvg_low_end", "add_fvg_low", "add_cutoff", "add_cut", "add_cut_ref", "nfp_no_adds",
    "no_adds_nfp", "decoupled_no_adds", "low_prob_no_adds", "add_on", "add_retest_away_pts", "add_body_stop",
    "ob_mt_pure_pad_pts", "trail_ref", "htf_add_extra_risk_pct", "add_cutoff_read", "size_up_cap_pct")
# fields that are tuning knobs of another switch (the study variant of the main switch uses them)
KNOBS = {"tick_pts", "stop_ineff_wick", "ob_stub_frac", "entry_ladder_fracs", "htf_target_pts", "size_down",
         "size_up", "low_prob_tests", "halving_floor", "winback_frac", "add_htf_tfs", "add_retest_away_pts",
         "ob_mt_pure_pad_pts", "iofed_ref", "add_cut_ref", "units_per_contract"}


def one(df, hist, **kw):
    tr, *_ = run(df, hist, Params(**{**BASE, **kw}), A_LOCK)
    return tr


def scen_a(rows=None, **kw):
    """Scenario A (OB bodies 100 armed 09:45, filled 09:50, run into the locked draw 108)."""
    return one(day(rows or A_ROWS, spike=True), history(), **kw)


def scen_b(**kw):
    tr, *_ = run(day(B_ROWS), history(), Params(**{**B_POST, "adds": (0.5,), **kw}), {})
    return tr


# --- defaults / validation ---------------------------------------------------------------------

def test_defaults_and_validation():
    p = Params()
    assert p.stop_tick_pts == 0.25 and p.nfp_no_adds is True        # the two spec defaults
    assert p.pad == 0.25 * p.es_pt and Params(es_pt=1.0).pad == 0.25
    assert Params(es_pt=1.0, stop_pad_ticks=3).pad == 0.75          # E6f replaces the pad by N ticks
    assert Params(es_pt=1.0, stop_tick_pts=0.0).pad == 0.01         # the old stop_buffer
    assert Params(es_pt=1.0, mohawk_ticks=2).trail_pad == 0.75
    for kw in (dict(entry="mid"), dict(trail_ref="x"), dict(sb_entry="ladder"), dict(stop_mode="wide"), dict(iofed_ref="x"),
               dict(run_cancel="x"), dict(entry_order="x"), dict(add_order="x"), dict(retrace_candle="x"),
               dict(ob_zone="x"), dict(ob_cisd="x"), dict(ob_entries="x"), dict(add_points="x"),
               dict(add_cut="x"), dict(add_on="x"), dict(ob_entry_px="x"), dict(irl_entries=("x",)),
               dict(size_rules=("x",)), dict(size_up_rules=("x",)), dict(add_arrays=("x",)),
               dict(low_prob_tests=("x",)), dict(entry_ladder_fracs=(1.0,)), dict(entry_ladder_fracs=(0.5, 0.4))):
        with pytest.raises(ValueError):
            Params(**kw)
    for m in S.ENTRY_MODES:
        Params(entry=m)
    for m in S.STOP_MODES:
        Params(stop_mode=m)
    Params(**S.PRESET_EP07)


def test_study_has_a_variant_for_every_new_switch():
    names = " ".join(str(v) for v in study.DECISIONS.values())
    for f in NEW_FIELDS:
        if f in KNOBS:
            continue
        assert f"'{f}'" in names, f
    ids = {k.split("_")[0] for k in study.DECISIONS}
    for rid in ("E6", "E6c", "A4", "A12", "A13.4", "M1.4", "M2.4", "E2", "E5", "E6b", "E6d", "E6f", "E9", "E10",
                "E12", "E12e", "D11", "D12", "Ep02.2", "Ep02.3", "Ep01.20", "Ep07.2", "Ep07.4", "Ep08.5",
                "Ep08.17", "L14b", "A16", "A21.3", "M2.5", "E1", "E3", "E4", "E11", "E12b", "E12c", "E12f",
                "Ep01.18", "Ep01.19", "Ep03.9", "Ep04.6", "Ep04.10", "Ep05.5", "Ep08.12"):
        assert rid in ids, rid
    assert set(NEW_FIELDS) <= {f.name for f in fields(Params)}
    for k in ("current", "D0_pre_owner_directives"):                 # the legacy presets pin the old pad / adds
        d = study.DECISIONS[k]
        assert d["stop_tick_pts"] == 0.0 and d["nfp_no_adds"] is False


# --- unit tests: entry prices (E2 / D11) -------------------------------------------------------

def _sd(o, h, l, c):
    return SimpleNamespace(o=np.array(o, float), h=np.array(h, float), l=np.array(l, float), c=np.array(c, float))


def test_entry_px_modes_and_ladder():
    p = Params(es_pt=1.0)
    g = SimpleNamespace(top=101.3, bottom=100.0, src=1, i=2)
    sd = _sd([100, 100.2, 101.6], [100.5, 101.9, 102.0], [99.9, 100.1, 101.3], [100.4, 101.8, 101.9])
    assert EN.entry_px(sd, g, g.top, g.bottom, p, "edge") == 101.3
    assert EN.entry_px(sd, g, g.top, g.bottom, p, "ce") == 100.65
    assert EN.entry_px(sd, g, g.top, g.bottom, p, "edge_1tick") == 101.05
    # IOFED: the FVG-forming candle's high clipped to one tick inside the edge, never past the CE
    assert EN.entry_px(sd, g, g.top, g.bottom, p, "iofed") == 101.05
    g2 = SimpleNamespace(top=101.3, bottom=100.0, src=0, i=2)             # candle high 100.5 < CE 100.65
    assert EN.entry_px(sd, g2, g2.top, g2.bottom, p, "iofed") == 100.65
    assert EN.entry_px(sd, g, g.top, g.bottom, replace(p, iofed_ref="q75"), "iofed") == pytest.approx(100.975)
    assert EN.entry_px(sd, g, g.top, g.bottom, replace(p, iofed_ref="tick"), "iofed") == 101.05
    assert EN.entry_px(sd, g, g.top, g.bottom, p, "ladder") == 101.3          # the first rung
    assert EN.ladder_rungs(101.3, 100.0, p) == pytest.approx([101.3, 100.975, 100.65])
    assert EN.ladder_rungs(101.3, 100.0, replace(p, entry_ladder_fracs=(0.6, 0.4))) == pytest.approx([101.3, 100.65])
    assert len(EN.ladder_rungs(101.3, 100.0, replace(p, entry_ladder_fracs=(0.4, 0.3, 0.2, 0.1)))) == 4
    with pytest.raises(ValueError):
        EN.entry_px(sd, g, g.top, g.bottom, p, "bogus")


def test_scenario_entry_modes_and_ladder_sizing():
    base = scen_b()[0]
    assert (base.entry, round(base.stop, 2), base.shares) == (101.3, 99.05, 533)
    assert scen_b(entry="edge_1tick")[0].entry == 101.05
    assert scen_b(entry="iofed")[0].entry == 101.05
    lad = scen_b(entry="ladder", max_risk_pts=40)[0]
    # one order: the first rung 50% at the edge, then 30% at 75% and 20% at the CE as later fills; the
    # risk of the whole ladder (average distance to the stop) stays at the budget
    assert lad.entry == 101.3 and [round(a[1], 2) for a in lad.adds] == [100.8, 100.65]
    risk = lad.shares * (lad.entry - lad.stop) + sum(a[2] * (a[1] - lad.stop) for a in lad.adds)
    assert risk <= 1.2 * 1000 + 100_000 * 0.012 + 1                       # <= 1.2% of 100k (+ rounding)
    assert lad.shares < base.shares


# --- unit tests: stops (E6 family) -----------------------------------------------------------------

def test_gap_stop_modes():
    p = Params(es_pt=1.0)
    o = [100.0, 100.4, 101.2, 101.5]
    h = [100.6, 101.6, 101.9, 102.0]
    l_ = [99.8, 100.3, 101.1, 101.4]
    c = [100.5, 101.5, 101.8, 101.9]
    sd = _sd(o, h, l_, c)
    g = SimpleNamespace(top=101.1, bottom=100.6, src=2, i=3)      # candles 1-3 = bars 1, 2, 3
    assert EN.gap_stop(sd, g, {"ext": 99.0}, 3, p, None, "sweep") == 98.75
    assert EN.gap_stop(sd, g, {"ext": 99.0}, 3, p, None, "fvg_c1_low") == 100.3 - 0.25         # candle 1 = bar 1
    assert EN.gap_stop(sd, g, {"ext": 99.0}, 3, p, None, "fvg_bodies") == 100.4 - 0.25         # lowest body of bars 1-3
    assert EN.gap_stop(sd, g, {"ext": 99.0}, 3, p, None, "fvg_open") == 101.2 - 0.25           # open of the middle candle (bar 2)
    ob = L.Zone("bull", 100.6, 99.8, 1, 0, 100.1)
    assert EN.gap_stop(sd, g, {"ext": 99.0}, 3, p, ob, "ob_mt_pure") == pytest.approx(100.1 - 2.0)
    assert EN.gap_stop(sd, g, {"ext": 99.0}, 3, p, None, "ob_mt_pure") is None
    assert EN.gap_stop(sd, g, {"ext": 99.0}, 3, p, None, "ob_mt") is None


def test_stop_modes_in_scenario():
    st = lambda **kw: round(scen_b(**kw)[0].stop, 2)
    assert st() == 99.05 and st(stop_mode="fvg") == 99.75
    assert st(stop_mode="fvg_c1_low") < 99.05 < st(stop_mode="fvg_open") + 0.7
    assert st(stop_mode="fvg_bodies") == 97.95 and st(stop_mode="fvg_c1_low") == 97.85
    assert st(stop_mode="fvg_open") == 99.65
    assert st(stop_mode="sweep") == 97.75                       # sweep extreme 98.0 - one tick
    assert st(stop_mode="ob_mt_pure") == 97.3                   # OB MT 99.3 - 2 pts
    assert st(stop_all_ineff=True) == 97.85 and "stop_ineff" in scen_b(stop_all_ineff=True)[0].lv_tags
    assert st(stop_all_ineff=True, stop_ineff_wick=False) <= 99.05
    assert st(mohawk_ticks=4.0) == 98.05                        # 4 ticks (1.0) beyond the padded level
    assert st(entry="ce", ce_stop_pad_pts=3.0) == st(entry="ce") - 3.0
    assert st(stop_pad_ticks=3.0) == 99.05 - 0.5               # a 3-tick pad instead of 1
    assert st(stop_tick_pts=0.0) == 99.29                       # the old 0.01 pad


def test_mt_close_stop_hard_stop_at_the_far_edge_and_body_close_exit():
    # a wide down-close OB (bodies 101.0..98.6, MT 99.8): stop = MT - pad = 99.55; mt_close_stop moves the hard
    # stop to the OB low - pad (98.25) and exits on a body CLOSE below the MT
    rows = [(101.0, 101.1, 99.9, 100.0), (100.0, 100.1, 98.5, 98.6), (98.6, 99.5, 98.55, 99.4),
            (99.4, 101.6, 99.3, 101.5), (101.5, 101.7, 100.9, 101.2), (101.2, 101.3, 99.6, 99.7),
            (99.7, 99.8, 99.5, 99.55), (99.55, 99.6, 99.4, 99.5)]
    a = scen_a(rows)[0]
    b = scen_a(rows, mt_close_stop=True)[0]
    assert (a.entry, round(a.stop, 2)) == (101.0, 99.55)
    assert [e[3] for e in a.exits][:1] == ["stop"] and round(a.exits[0][1], 2) == 99.55
    assert round(b.stop, 2) == 98.25 and "mt_close" in b.lv_tags
    assert b.exits[0][3] == "ob_mt_close" and b.exits[0][1] == 99.7        # the close below the MT
    assert b.shares < a.shares                                            # sized off the wider hard stop


def test_mohawk_body_close_exit_and_wick_poke():
    p = dict(mohawk_ticks=4.0)
    # default stop 98.25; mohawk: stop 97.25 and a body CLOSE beyond the raw 98.25 exits at the close
    rows = A_ROWS[:5] + [(100.3, 100.4, 98.0, 98.1)]
    t = scen_a(rows, **p)[0]
    assert round(t.stop, 2) == 97.25 and t.exits[0][3] == "mohawk" and t.exits[0][1] == 98.1
    rows = A_ROWS[:5] + [(100.3, 100.4, 98.0, 99.0)]                      # a wick poke through, body back above
    t = scen_a(rows, **p)[0]
    assert not t.exits or t.exits[0][3] != "stop"
    t0 = scen_a(rows)[0]
    assert t0.exits[0][3] == "stop"                                       # without mohawk the wick stops it out


# --- orders: fills, cancels, hygiene -----------------------------------------------------------------

def test_fill_through_and_retrace_candle_and_stop_cc():
    assert len(scen_a()) == 1 and scen_a()[0].entry == 100.0
    assert scen_a(fill_through=1.0) == []                                 # low 99.9 is not a full tick through 100
    assert len(scen_a(fill_through=0.4)) == 1                             # 0.1 through is enough
    assert scen_a(retrace_candle="closed") == []                          # no down-close candle between arm and fill
    assert len(scen_a(retrace_candle="intrabar")) == 1
    assert scen_a(entry_order="stop_cc") == []                            # a buy stop above the market is a chase: refused


def test_exit_fill_through_needs_the_tick():
    t = scen_a()[0]
    assert [e[3] for e in t.exits] == ["t1", "t2", "t3"]
    t2 = scen_a(exit_fill_through=1.0)[0]
    assert t2.exits[0][1] == 102.75                                       # the bar traded 0.25 through 102.75
    far = scen_a(exit_fill_through=100.0)[0]
    assert [e[3] for e in far.exits] == ["am_exit"]                      # no target ever prints 100 ticks through


def test_run_cancel_loosened():
    # price runs to the first target without the pending order ever filling (a limit far below)
    rows = [(100.0, 100.1, 99.5, 99.6), (99.6, 99.7, 98.5, 98.8), (98.8, 99.9, 98.7, 99.8),
            (99.8, 100.8, 99.7, 100.7), (100.7, 108.5, 100.4, 108.4)]
    # the bar runs to the first target without touching the limit (low 100.4 > 100.0): "t1" drops the order,
    # "off" keeps it, and a later dip (low 99.0, gap-free) fills it at 100.0
    rows2 = rows + [(108.4, 108.5, 99.0, 99.1)]
    free = dict(draw_lock="off", htf_resist_cap=False, min_draw_pts=0.0)
    assert scen_a(rows2, run_cancel="t1", **free) == []
    t = scen_a(rows2, run_cancel="off", **free)
    assert len(t) == 1 and t[0].entry == 100.0


def test_no_new_extreme_cancels_a_delayed_order():
    rows = A_ROWS[:4] + [(100.7, 100.8, 98.4, 98.9), (98.9, 100.2, 98.8, 100.1), (100.1, 100.3, 99.9, 100.2)]
    base = dict(retrace_candle="closed")                                  # delays the first possible fill by a bar
    a = scen_a(rows, **base)
    b = scen_a(rows, no_new_extreme=True, **base)
    assert [round(t.entry, 2) for t in a] != [round(t.entry, 2) for t in b] or len(a) != len(b)
    assert all(t.exits for t in b)


def test_evolve_fvg_replaces_the_order_with_a_newer_untouched_gap():
    """E5 (057): the first FVG (100.0-101.3) arms a limit at 101.3 that price never reaches; a newer
    untouched FVG (102.5-103.0) then replaces it when evolve_fvg keeps the sweep alive."""
    rows = B_ROWS[:9] + [(102.3, 103.5, 102.2, 103.4), (103.4, 104.2, 103.0, 104.0), (104.0, 104.1, 102.9, 103.0),
                         (103.0, 108.0, 102.95, 107.9)]
    run_ = lambda **kw: run(day(rows), history(), Params(**{**B_POST, "adds": (0.5,), **kw}), {})[0]
    assert run_() == []                                                      # the old order at 101.3 is never touched
    t = run_(evolve_fvg=True)
    assert len(t) == 1 and t[0].entry == 103.0                               # replaced by the newer gap's top
    t2 = run_(wait_structural=True)
    assert t2 == []                                                           # wait_structural alone only matters after a rejection
    # a too-wide stop first (gap 1: risk 1.55 > max 1.2), then a newer structural entry (gap 2: risk 0.85)
    rows_w = B_ROWS[:9] + [(102.3, 102.9, 102.2, 102.8), (102.8, 103.0, 102.0, 102.1), (102.1, 108.0, 102.05, 107.9)]
    kw = dict(stop_mode="fvg", max_risk_pts=1.2, min_risk_pts=0.5)
    rw = lambda **k: run(day(rows_w), history(), Params(**{**B_POST, "adds": (0.5,), **kw, **k}), {})[0]
    assert rw() == []                                                        # the rejected setup is dropped
    t3 = rw(wait_structural=True)
    assert len(t3) == 1 and t3[0].entry == 102.2                             # ... or waits for the newer gap


def test_engage_range_wait():
    assert len(scen_a()) == 1
    assert scen_a(engage_range_pts=500.0) == []                           # the 00:00.. range never reaches 500 pts
    assert len(scen_a(engage_range_pts=1.0)) == 1


def test_mo_tol_pts_allows_an_entry_above_the_open():
    rows = [(99.5, 99.6, 98.8, 98.9), (98.9, 99.0, 97.5, 97.7), (97.7, 98.9, 97.6, 98.8),
            (98.8, 100.1, 98.7, 100.0), (100.0, 100.2, 99.0, 99.9), (99.9, 103.0, 99.8, 102.9)]
    # reference open 100.0 (midnight, flat overnight): an OB entry at 100.5 is above it
    t_off = scen_a(rows, use_bias=True)
    t_tol = scen_a(rows, use_bias=True, mo_tol_pts=1.0)
    assert len(t_tol) >= len(t_off)


# --- order blocks (A12 / Ep03.9 / Ep08.5) --------------------------------------------------------------

def test_ob_entry_price_modes():
    ob = dict(j=0, k=1, body_top=101.0, body_low=98.6, mt=99.8, hi=101.4, lo=98.5)
    sd = _sd([101.2, 100.0], [101.4, 100.1], [99.9, 98.5], [100.0, 98.6])
    p = Params(es_pt=1.0)
    px = lambda **kw: EN.ob_entry_price(ob, sd, replace(p, **kw))
    assert px() == 101.0 and px(ob_entry_px="mt") == 99.8
    assert px(ob_entry_px="range_top") == 101.4 == px(ob_entry_px="high")
    assert px(ob_entry_px="open") == 101.2                                # Ep03.9: the FIRST candle's open
    assert px(ob_zone="range") == 101.4
    assert px(ob_zone="sensitive") == 101.0                               # stubby wick (0.4 of a 2.9 range <= 25%)
    assert px(ob_zone="sensitive", ob_stub_frac=0.05) == pytest.approx(101.2)   # long wick: the wick CE


def test_ob_zone_scenario_and_ob_entries_flag():
    a = scen_a()[0]
    assert a.entry == 100.0
    r = scen_a(ob_zone="range")
    assert r == [] or r[0].entry >= a.entry - 1e-9                         # the range high is never below the body top
    # Ep03.9 'open' = the first candle's open (here 100.0 = the highest open as well)
    assert scen_a(ob_entry_px="open")[0].entry == 100.0


def test_ob_quality_cisd_helpers():
    o = [101.0, 100.0, 98.6, 99.4, 100.0]
    h = [101.1, 100.1, 99.5, 101.6, 101.7]
    l_ = [99.9, 98.5, 98.55, 99.3, 100.9]
    c = [100.0, 98.6, 99.4, 101.5, 101.6]
    sd = _sd(o, h, l_, c)
    ob = L.order_block_blend(sd.o, sd.h, sd.l, sd.c, 0, 1, "bull")
    assert ob is not None and ob.src == 0
    p = Params(es_pt=1.0, ob_disp_mult=0.5)
    assert EN.ob_quality_ok(sd, {}, ob, 4, p)                              # moved 0.6 above the OB top vs a 1.0 body
    assert not EN.ob_quality_ok(sd, {}, ob, 4, replace(p, ob_disp_mult=0.7))
    assert not EN.ob_quality_ok(sd, {}, ob, 4, replace(p, ob_disp_mult=50.0))
    assert EN.ob_quality_ok(sd, {}, ob, 4, replace(p, ob_disp_mult=0.0))
    assert EN.ob_cisd_ok(sd, ob, 4, p)                                    # a close above the series' highest open (101.0)
    assert not EN.ob_cisd_ok(sd, ob, 2, p)


def test_ob_cisd_and_disp_in_scenario():
    assert "ob_cisd" in scen_b(ob_cisd="tag")[0].lv_tags
    assert scen_b(ob_disp_mult=20.0) == [] and len(scen_b(ob_disp_mult=2.0)) == 1


def test_opposing_obs_and_targets():
    # a bearish OB above a long: the up-close run (bars 0-2) before the displacement down (bar 3) that
    # leaves a SIBI (bars 2-4); bars 5-6 retrace up into it
    def side(extra):
        o = [100.0, 100.4, 100.9, 101.9, 99.8, 99.0] + [e[0] for e in extra]
        h = [100.5, 101.0, 102.0, 102.0, 99.9, 99.7] + [e[1] for e in extra]
        l_ = [99.8, 100.3, 100.8, 99.5, 98.8, 98.9] + [e[2] for e in extra]
        c = [100.4, 100.9, 101.9, 99.8, 99.0, 99.5] + [e[3] for e in extra]
        return S.Side(1, np.array(o), np.array(h), np.array(l_), np.array(c), 1, 0.0)
    p = Params(es_pt=1.0, ob_targets_1m=True)
    sd = side([])
    z = EN.opposing_obs(sd, 5, p)
    assert len(z) == 1 and (z[0].bottom, z[0].top) == (99.8, 102.0) and z[0].mt == pytest.approx(100.95)
    assert EN.opposing_obs(sd, 3, p) == []                                    # not known before bar 4
    assert EN.ob_target_levels(sd, 5, 99.0, p) == [(99.8, "array"), (100.95, "array")]
    assert EN.ob_target_levels(sd, 5, 100.0, p) == [(100.95, "array")]        # only levels above the entry
    # price traded into the lower half (high 100.5) but not its MT: only opp_ob_mt keeps the MT
    sd2 = side([(99.5, 100.5, 99.4, 100.3)])
    assert EN.ob_target_levels(sd2, 6, 99.0, p) == []
    assert EN.ob_target_levels(sd2, 6, 99.0, replace(p, opp_ob_mt=True)) == [(100.95, "array")]
    # price traded through the MT (high 101.2): spent in both modes
    sd3 = side([(99.5, 101.2, 99.4, 101.0)])
    assert EN.ob_target_levels(sd3, 6, 99.0, replace(p, opp_ob_mt=True)) == []


# --- sizing (E9 / E10 / E11 / Ep08.12) ---------------------------------------------------------------

def test_risk_state_halves_and_steps_back():
    p = Params(loss_halving=True, halving_floor=0.25, winback_frac=0.5)
    rs = EN.new_risk_state()
    EN.risk_state_update(rs, -100.0, p)
    assert rs["m"] == 0.5
    EN.risk_state_update(rs, -100.0, p)
    EN.risk_state_update(rs, -100.0, p)
    assert rs["m"] == 0.25 and rs["deficit"] == 300.0                      # floor
    EN.risk_state_update(rs, 100.0, p)
    assert rs["m"] == 0.25 and rs["deficit"] == 200.0                      # not yet 50% won back
    EN.risk_state_update(rs, 60.0, p)
    assert rs["m"] == 1.0 and rs["peak"] == 0.0                            # >= 50% won back: full size again
    EN.risk_state_update(rs, 500.0, p)
    assert rs["m"] == 1.0                                                  # a win never raises above full


def test_loss_halving_carries_across_days_in_backtest_run():
    x, y = B.synthetic(start="2026-04-01", end="2026-04-17", tf=5, seed=3)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        a = B.run(x, 5, "RW", Params(**SYN), y)
        b = B.run(x, 5, "RW", Params(**SYN, loss_halving=True), y)
    assert len(a) and len(a) == len(b)
    assert (b.shares.values <= a.shares.values).all()
    assert (b.shares.values < a.shares.values).any()                       # a loss halved a later trade (also next day)


def test_after_loss_mult_and_contract_caps():
    p = Params(es_pt=1.0, max_contracts_initial=6, max_contracts_total=16, units_per_contract=1)
    assert EN.cap_initial(10, p) == 6 and EN.cap_initial(4, p) == 4
    assert EN.cap_add(5, 6, p) == 5 and EN.cap_add(5, 14, p) == 2 and EN.cap_add(5, 16, p) == 0
    q = Params(es_pt=1.0, lot=5, max_contracts_initial=2, units_per_contract=5)
    assert EN.cap_initial(25, q) == 10                                    # 2 contracts of 5 units
    assert EN.cap_initial(25, Params(es_pt=1.0)) == 25                    # off
    t = scen_a(max_contracts_initial=6, units_per_contract=1)[0]
    assert t.shares == 6
    st = {"reentered": {}, "day_loss": True, "rs": None}
    assert S._risk_mult(st, "AM", Params(after_loss_mult=0.5)) == 0.5
    st["rs"] = {"m": 0.5}
    assert S._risk_mult(st, "AM", Params(after_loss_mult=0.5, loss_halving=True)) == 0.25
    assert S._risk_mult({"reentered": {"AM": 1}, "day_loss": False, "rs": None}, "AM", Params()) == 0.5


def test_size_rules_scenarios():
    base = scen_a()[0].shares
    d = lambda **kw: scen_a(**kw)[0].shares
    assert d(size_rules=("august",)) == base                               # D0 is June
    tr, *_ = run(day(A_ROWS, spike=True, d=date(2026, 8, 18)), history(date(2026, 8, 18)),
                 Params(**BASE, size_rules=("august",)), A_LOCK)
    tr0, *_ = run(day(A_ROWS, spike=True, d=date(2026, 8, 18)), history(date(2026, 8, 18)), Params(**BASE), A_LOCK)
    assert tr[0].shares < tr0[0].shares and "size_august" in tr[0].lv_tags
    assert tr[0].shares == pytest.approx(tr0[0].shares * 0.5, abs=1)
    # the day before a FOMC / NFP / CPI: 2026-06-04 is the Thursday before the June NFP
    day_ = date(2026, 6, 4)
    t1, *_ = run(day(A_ROWS, spike=True, d=day_), history(day_), Params(**BASE, size_rules=("news_eve",)), A_LOCK)
    t0, *_ = run(day(A_ROWS, spike=True, d=day_), history(day_), Params(**BASE), A_LOCK)
    assert t1 and t0 and t1[0].shares < t0[0].shares
    # size-up is capped by the 1.3% total: 1.2% x 1.5 -> at most 1.3%
    up = scen_a(size_up_rules=("bpr",))
    assert up and up[0].shares >= base


# --- adds (E12 family) ----------------------------------------------------------------------------------

def add_a(**kw):
    tr = one(day(ADD_ROWS, spike=True), history(), adds=(0.5,), ob_adds=False, max_total_risk=5000.0, **kw)
    return tr[0]


def test_add_points_cut_and_order_market():
    assert [round(a[1], 2) for a in add_a().adds] == [101.3]
    assert [round(a[1], 2) for a in add_a(add_points="ce").adds] == [101.1]
    assert [round(a[1], 2) for a in add_a(add_points="q75").adds] == [101.2]
    assert add_a(add_order="market").adds[0][1] == 101.5                    # the open after the retest bar
    # progress at the add: (101.8 - 98.5) / (108.25 - 98.5) = 34% of the range
    assert len(add_a(add_cut="eq").adds) == 1
    assert add_a(add_cutoff=0.75).adds == []                                # past the 25% line already
    assert add_a(add_cut="eq", add_cutoff=0.75).adds == []
    assert len(add_a(add_cut="leg75").adds) == 1 or add_a(add_cut="leg75").adds == []


def test_add_hold_cancels_a_failing_market_add():
    rows = ADD_ROWS[:8] + [(101.7, 101.8, 100.95, 100.5), (100.5, 103.0, 100.4, 102.9)] + ADD_ROWS[10:]
    t = one(day(rows, spike=True), history(), adds=(0.5,), ob_adds=False, max_total_risk=5000.0, add_order="market")[0]
    assert len(t.adds) == 1                                                  # bought at the open after the retest bar
    t = one(day(rows, spike=True), history(), adds=(0.5,), ob_adds=False, max_total_risk=5000.0, add_order="market", add_hold=True)[0]
    assert t.adds == []                                                      # the retest bar closed below the gap: no add


def test_add_low_end_after_a_close_into_the_gap():
    rows = ADD_ROWS[:8] + [(101.7, 101.8, 100.95, 101.2), (101.2, 103.0, 101.1, 102.9)] + ADD_ROWS[10:]
    t = one(day(rows, spike=True), history(), adds=(0.5,), ob_adds=False, max_total_risk=5000.0)[0]
    assert len(t.adds) == 1
    for name in ("add_low_end", "add_fvg_low_end", "add_fvg_low"):
        t = one(day(rows, spike=True), history(), adds=(0.5,), ob_adds=False, max_total_risk=5000.0, **{name: True})[0]
        assert [round(a[1], 2) for a in t.adds] == [101.3, 101.15]            # + the final add at the gap bottom + 1 tick
        assert t.adds[1][2] == t.adds[0][2]                                   # the smallest earlier add


def test_add_body_stop_moves_the_stop_under_the_gap_bodies():
    rows = ADD_ROWS[:9] + [(101.5, 101.6, 100.0, 100.1), (100.1, 103.0, 100.0, 102.9)] + ADD_ROWS[11:]
    a = one(day(rows, spike=True), history(), adds=(0.5,), ob_adds=False, max_total_risk=5000.0)[0]
    b = one(day(rows, spike=True), history(), adds=(0.5,), ob_adds=False, max_total_risk=5000.0, add_body_stop=True)[0]
    assert all(e[3] != "stop" for e in a.exits)                              # stop 98.25 never touched
    assert b.exits[0][3] in ("stop", "be") and round(b.exits[0][1], 2) == 100.05    # under the bodies 100.3 - pad


def test_nfp_no_adds_and_add_blockers():
    nfp = date(2026, 6, 5)                                                   # the June NFP Friday
    df = day(ADD_ROWS, spike=True, d=nfp)
    for flag, n in ((True, 0), (False, 1)):
        tr, *_ = run(df, history(nfp), Params(**{**BASE, "adds": (0.5,), "ob_adds": False, "max_total_risk": 5000.0, "nfp_no_adds": flag,
                                                  "news_wait": "off"}), A_LOCK)
        if tr:
            assert len(tr[0].adds) == n
    tr, *_ = run(df, history(nfp), Params(**{**BASE, "adds": (0.5,), "ob_adds": False, "max_total_risk": 5000.0, "no_adds_nfp": True,
                                              "nfp_no_adds": False, "news_wait": "off"}), A_LOCK)
    assert not tr or tr[0].adds == []
    assert not EN.decoupled(SimpleNamespace(pside=(None, None, None)), 0, Params())


def test_add_cut_passed_helper():
    sd = _sd([0] * 8, [100, 101, 102, 103, 104, 105, 106, 107], [0] * 8, [0] * 8)
    pos = dict(fill_i=0, leg=(100.0, 108.0), draw=110.0)
    p = Params(es_pt=1.0)
    cut = lambda i, **kw: EN.add_cut_passed(sd, pos, i, replace(p, **kw))
    # the highest high since the fill: bar 7 -> 107 = 70% of 100..110 (draw); bar 4 -> 104 = 40%
    assert not cut(7)                                                         # no cut configured
    assert cut(7, add_cut="eq") and not cut(4, add_cut="eq")                  # past EQ of the range
    assert cut(6, add_cutoff=0.5) and not cut(4, add_cutoff=0.5)              # 60% / 40% vs the 50% line
    assert not cut(7, add_cutoff=0.25)                                        # 70% has not reached the 75% line yet
    assert cut(7, add_cutoff=0.35)
    assert cut(7, add_cut="leg75") is True                                    # 107 is 87.5% of the 100..108 leg
    pos["leg"] = (100.0, 130.0)
    assert cut(7, add_cut="leg75") is False                                   # 23% of a 100..130 leg
    assert not cut(4, add_cut="leg75", add_cut_ref="leg")                     # 40% of the leg
    pos["leg"] = (100.0, 112.0)
    assert cut(7, add_cut="eq", add_cut_ref="leg")                            # 58% of the leg itself: past its EQ


def test_low_end_and_retest_helpers():
    sd = _sd([0] * 6, [0] * 6, [0] * 6, [100.0, 101.0, 102.0, 103.0, 101.2, 101.2])
    tr = SimpleNamespace(adds=[("t", 101.3, 33)], shares=100)
    pos = dict(fill_i=0, t1_done=False, stop=98.0, basis=100.0 * 100, n=100, last_add_g=(101.3, 100.9, 0), fvg_ce=100.0,
               fvg_bottom=99.0)
    got = []
    p = Params(es_pt=1.0, adds=(0.5,), lot=1)
    EN.low_end_add(sd, pos, tr, 4, p, lambda px, size: got.append((round(px, 2), size)))
    assert got == [(101.15, 33)] and pos["low_end_used"]
    EN.low_end_add(sd, pos, tr, 5, p, lambda px, size: got.append("again"))
    assert got == [(101.15, 33)]                                              # once only
    pos2 = dict(pos, low_end_used=False, basis=102.0 * 100)
    EN.low_end_add(sd, pos2, tr, 4, p, lambda px, size: got.append("loss"))   # earlier units not in profit
    assert got == [(101.15, 33)]


# --- shared small helpers --------------------------------------------------------------------------------

def test_leg_depth_tags_and_pd_high():
    assert EN.leg_depth_tags(108.0, 100.0, 110.0) == ["leg_shallow", "leg_third_1"]      # 20% retrace, top third
    assert EN.leg_depth_tags(104.0, 100.0, 110.0) == ["leg_shallow", "leg_third_2"]      # 60% retrace: not yet OTE
    assert EN.leg_depth_tags(103.0, 100.0, 110.0) == ["leg_ote", "leg_third_3"]          # 70%: the OTE band
    assert EN.leg_depth_tags(102.0, 100.0, 110.0)[0] == "leg_deep"
    assert EN.leg_depth_tags(110.0, 100.0, 110.0)[1] == "leg_third_1"
    assert EN.leg_depth_tags(104.0, 100.0, 100.0) == []
    sd = S.Side(1, np.array([1.0] * 8), np.array([1, 3, 2, 5, 3, 4, 3, 3.0]), np.array([0.5, 2.5, 1.5, 4, 2.5, 3.5, 2.5, 2.5]),
                np.array([1.0] * 8), 1, 0.0)
    p = Params(es_pt=1.0)
    assert EN.pd_high(sd, {"ext_i": 0}, 7, 9.0, p) == 9.0
    assert EN.pd_high(sd, {"ext_i": 0}, 7, 9.0, replace(p, erl_range_swings=True)) == 5.0


def test_leg_pd_min_ote_tag_and_cancel_in_scenario():
    assert scen_b(leg_pd_min=0.9) == []                                       # the entry is far above 0.9 of the leg? no: too deep
    assert "leg_shallow" in scen_b(leg_depth_tag=True)[0].lv_tags


def test_study_leg_062_is_the_ote_band():
    d = study.DECISIONS["D12_leg_062"]
    assert (d["leg_pd"], d["leg_pd_min"]) == (0.38, 0.21)


def test_irl_entries_and_erl_exits_in_scenario():
    assert len(scen_b(irl_entries=("fvg", "ob", "void"), max_risk_pts=40)) >= 1
    assert scen_b(irl_entries=("void",), max_risk_pts=40) == []               # no void in the scenario, FVG not allowed
    t = scen_b(erl_exits_only=True)
    assert t == [] or t[0].exits                                              # only external liquidity: may leave no trade


# --- no look-ahead (full vs truncated runs) ------------------------------------------------------------------

COLS = ["entry_time", "entry", "stop", "t1", "shares", "entry_kind", "lv_tags", "setup", "swept"]
XCOLS = ["entry_time", "exit_time", "exit_reason", "n_adds", "net"]


def _no_look_ahead(df, tf, sym, p, cols, every=1, meta=None, lag=2, min_trades=1, exits=False, **kw):
    """Full run vs runs truncated just after each entry (every `every`-th, and just after exits when
    exits=True): the entries (and for closed trades the exits / adds / net) must be identical."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        full = B.run(df, tf, sym, p, meta=meta, **kw)
        assert len(full) >= min_trades, "no trades - the test window must produce some"
        cuts = list(full.entry_time.iloc[::every])
        if exits:
            cuts = sorted(set(cuts) | set(pd.to_datetime(full.exit_time).iloc[::every]))
        for cut_t in cuts:
            c = cut_t + pd.Timedelta(minutes=lag)
            pk = {k: (v[v.index <= c] if isinstance(v, pd.DataFrame) else v) for k, v in kw.items()}
            part = B.run(df[df.index <= c], tf, sym, p, partial_last=True, meta=meta, **pk)
            fa = full[full.entry_time <= cut_t].reset_index(drop=True)
            pa_ = part[part.entry_time <= cut_t].reset_index(drop=True) if len(part) else part
            pd.testing.assert_frame_equal(fa[cols], pa_[cols] if len(pa_) else fa[cols].iloc[:0])
            if exits:
                done = (pd.to_datetime(fa.exit_time) <= cut_t).values
                xa = fa[done][XCOLS].astype({"exit_time": str}).reset_index(drop=True)
                xb = pa_[done][XCOLS].astype({"exit_time": str}).reset_index(drop=True)
                pd.testing.assert_frame_equal(xa, xb)
    return full


def _syn(start="2026-04-06", end="2026-04-24", seed=3):
    return B.synthetic(start=start, end=end, tf=5, seed=seed)


SETS = {
    "stops": dict(POST, stop_mode="fvg_bodies", stop_all_ineff=True, mohawk_ticks=2.0, ce_stop_pad_pts=1.0,
                  nfp_stop_wide=True, stop_pad_ticks=2.0, max_risk_pts=60, sweep_body=True, vi_hold=True, vi_stop=True),
    "stops_b": dict(POST, stop_mode="sweep", mt_close_stop=True, ob_disp_mult=0.5, ob_cisd="cancel",
                    prop_entry=True, prop_mt_exit=True, prop_zone="body", max_risk_pts=60),
    "stops_ob": dict(mt_close_stop=True, ob_zone="sensitive", ob_cisd="tag", ob_entry_px="open", mohawk_ticks=2.0,
                     stop_all_ineff=True, max_risk_pts=60),
    "entry": dict(POST, entry="iofed", evolve_fvg=True, no_new_extreme=True, retrace_candle="closed",
                  fill_through=1.0, run_cancel="last", leg_pd_min=0.1, leg_depth_tag=True, erl_range_swings=True),
    "entry_b": dict(POST, entry="ladder", wait_structural=True, vi_entries=True, irl_entries=("fvg", "ob", "void"),
                    ob_entries="fallback", exit_fill_through=1.0, max_risk_pts=60),
    "entry_c": dict(POST, entry="edge_1tick", ob_entries="prefer", engage_range_pts=2.0, mo_tol_pts=1.0,
                    max_risk_pts=60),
    "entry_d": dict(POST, entry="edge_1tick", erl_exits_only=True, ote="limit", ote_cancel=True,
                    irl_entries=("ob",), ob_entries="fallback", max_risk_pts=60),
    "sb": dict(sb_model=True, sb_entry="iofed", fill_through=1.0, exit_fill_through=1.0, ma_deuce=True,
               stop_pad_ticks=2.0),
    "size": dict(loss_halving=True, size_rules=("news_eve", "fomc_week", "august", "against_macro", "decoupled",
                                                "low_prob"), size_up_rules=("bpr", "htf_target"),
                 after_loss_mult=0.5, max_contracts_initial=6, max_contracts_total=16, units_per_contract=1,
                 no_max_after_loss=True),
    "adds": dict(POST, add_points="ce", add_arrays=("vi", "ifvg", "ob", "breaker"), ifvg_entries=True, add_hold=True,
                 add_low_end=True, add_cutoff=0.25, add_cut="eq", add_on="retest", add_body_stop=True,
                 add_order="market", trail=True, trail_ref="body", decoupled_no_adds=True, low_prob_no_adds=True, add_fvg_low=True, max_risk_pts=60),
}


@pytest.mark.parametrize("name", list(SETS))
def test_look_ahead_synthetic(name):
    x, y = _syn()
    every = 3
    _no_look_ahead(x, 5, "RW", Params(**SYN, **SETS[name]), COLS, every=every, partner=y, exits=True, min_trades=1)


@pytest.mark.skipif(not ES, reason="no ES data")
def test_look_ahead_es_adds_and_htf_add_zone():
    es = B.load("ES", 5, source="databento")
    df = es[(es.index >= "2023-10-02") & (es.index < "2023-11-03")]
    meta = B.load_meta("ES", 5)
    p = Params(**FUT, draw_lock="off", htf_resist_cap=False, leg_pd=0, min_draw_pts=0, use_bias=False,
               ob_entry="post_mss", add_arrays=("htf_fvg", "vi"), add_hold=True, add_low_end=True,
               add_body_stop=True, add_cut="eq", entry="edge_1tick", max_risk_pts=40)
    _no_look_ahead(df, 5, "ES", p, COLS, every=2, meta=meta, exits=True)


def test_stop_cc_never_chases_on_the_synthetic_window():
    x, y = _syn()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        t = B.run(x, 5, "RW", Params(**SYN, **POST, entry_order="stop_cc", max_risk_pts=60), y)
    assert len(t) == 0                                  # price is always above the array top when the order is armed


def test_synthetic_switches_fire():
    """The families above actually change the engine on the synthetic window (not inert)."""
    x, y = _syn()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        run_ = lambda **kw: B.run(x, 5, "RW", Params(**SYN, **kw), y)
        base = run_(**POST)
        assert len(base)
        assert run_(**POST, entry="iofed").entry.tolist() != base.entry.tolist()
        assert run_(**POST, stop_all_ineff=True, max_risk_pts=60).lv_tags.str.contains("stop_ineff").any()
        assert run_(**POST, stop_mode="sweep", max_risk_pts=60).stop.tolist() != base.stop.tolist()
        lad = run_(**POST, entry="ladder", max_risk_pts=60)
        assert lad.n_adds.sum() > 0
        assert run_(**POST, retrace_candle="closed").entry_time.tolist() != base.entry_time.tolist()
        assert run_(**POST, leg_depth_tag=True).lv_tags.str.contains("leg_").all()
        sz = run_(size_rules=("news_eve", "fomc_week", "august"), size_up_rules=("bpr",))
        assert sz.lv_tags.str.contains("size").any()


# --- owner #7 (revised): the HTF FVG behind the trade is an ADD zone ------------------------------------------

class _Conf:
    def __init__(self, zones):
        self.zones = zones

    def valid(self, now, side, tfs, src=(0,)):
        return [z for z in self.zones if z[2] in tfs]


def _ctx(conf):
    return SimpleNamespace(conf=conf, idx=pd.date_range("2026-06-23 09:30", periods=10, freq="5min", tz="America/New_York"),
                           tf=5)


def test_htf_fvg_behind_the_trade_is_an_add_zone_and_never_a_target():
    p = Params(es_pt=1.0)
    assert p.add_arrays == ("htf_fvg",)                                      # the owner #7 default
    long_sd = S.Side(1, np.full(10, 103.0), np.full(10, 103.5), np.full(10, 102.5), np.full(10, 103.0), 1, 0.0)
    pos = dict(stop=98.0, basis=100.0 * 10, n=10, fill_i=0)
    # a bullish 15m FVG 100-101 under the price (entry at 100.0 traded up through it), a 1h one above the price
    ctx = _ctx(_Conf([(101.0, 100.0, "15m", 0, 0.0), (106.0, 105.0, "1h", 0, 0.0), (101.2, 100.9, "4h", 0, 0.0)]))
    zs = EN.htf_add_zones(ctx, long_sd, pos, 5, p)
    assert [(z[0], z[2]) for z in zs] == [(101.0, "15m")]                     # only tfs in add_htf_tfs, only behind the price
    armed = []
    tr = SimpleNamespace(adds=[])
    pos.update(add=None, t1_done=False)
    ok = EN.more_add_arrays(ctx, long_sd, pos, tr, 5, p, lambda px, floor=None, extra=0.0: armed.append((px, floor)) or True)
    assert ok and armed == [(101.0, 100.0)] and pos["htf_add_used"]
    assert not EN.more_add_arrays(ctx, long_sd, pos, tr, 5, p, lambda px, floor=None, extra=0.0: True)       # one shot
    # an entry ABOVE the zone top never traded up through it: no add zone
    pos2 = dict(stop=98.0, basis=102.0 * 10, n=10, fill_i=0, add=None, t1_done=False)
    assert not EN.more_add_arrays(ctx, long_sd, pos2, tr, 5, p, lambda px, floor=None, extra=0.0: True)
    # a short mirrors it: a bearish 15m FVG 99-100 ABOVE a short entered at 101 ... in side space below the price
    short_sd = S.Side(-1, np.full(10, 103.0), np.full(10, 103.5), np.full(10, 102.5), np.full(10, 103.0), 1, 0.0)
    assert EN.htf_add_zones(_ctx(None), short_sd, pos, 5, p) == []             # no confluence table: no zones


def test_built_by_other_packages_are_wired_and_still_work():
    """A13.4 / Ep05.5 breaker entries, M1.4 OB-before-break default, Ep02.2 entry_arrays, round pools."""
    p = Params()
    assert p.ob_entry == "pre_break" and p.round_pools and p.risk_pct == 0.012 and p.max_total_risk_pct == 0.013
    kinds = lambda **kw: [t.entry_kind for t in scen_b(**kw)]
    assert kinds(breaker_entry="prefer") == ["breaker"]                       # A13.4: a limit at the breaker top
    t = scen_b(breaker_entry="prefer")[0]
    assert t.entry == 101.0 and round(t.stop, 2) == 97.75                      # stop beyond the sweep extreme 98.0
    assert kinds(entry_arrays=("ob", "breaker")) in (["fvg"], ["arr_ob"], ["arr_breaker"])
    assert kinds(irl_entries=("ob",)) == ["arr_ob"]                            # L14b: the OB as an IRL entry
    assert kinds(ob_entries="prefer") == ["ob_anchor"]                         # Ep08.5: the anchor open
    assert scen_b(ob_entries="prefer")[0].entry == 100.4
    assert kinds(ob_entries="fallback") == ["fvg"]                             # an FVG follows the break: no fallback
    assert [t.entry_kind for t in scen_a()] == ["ob_pre"]                      # M1.4 default


def test_trail_ref_body_vs_gap():
    rows = ADD_ROWS[:8] + [(101.7, 101.8, 100.5, 101.5)] + ADD_ROWS[9:]
    kw = dict(trail=True, adds=())
    a = one(day(rows, spike=True), history(), **kw)[0]
    b = one(day(rows, spike=True), history(), trail_ref="body", **kw)[0]
    assert a.exits[0][3] == "stop" and round(a.exits[0][1], 2) == 100.65     # under the gap bottom 100.9 - a tick
    assert all(e[3] != "stop" for e in b.exits)                              # bodies 100.3 - a tick = 100.05: a wick to 100.5 is fine


def test_propulsion_block_helper_and_vi_hold_scenario():
    o = [100.4, 99.5, 98.2, 99.9, 101.5, 102.3, 100.8, 100.9]
    h = [100.5, 99.6, 100.0, 101.6, 102.5, 102.6, 101.0, 102.6]
    l_ = [99.4, 98.0, 98.1, 99.0, 101.3, 100.5, 100.6, 100.8]
    c = [99.5, 98.2, 99.9, 101.5, 102.3, 100.8, 100.9, 102.5]
    sd = S.Side(1, np.array(o), np.array(h), np.array(l_), np.array(c), 1, 0.0)
    sw = {"ext_i": 1, "ext": 98.0}
    props = [z for z in sd.propulsions()]
    assert len(props) == 1 and props[0].src == 5 and props[0].mt == pytest.approx(101.55)
    p = Params(es_pt=1.0)
    assert EN.prop_block(sd, sw, 101.3, 7, p) == (102.6, pytest.approx(101.55))
    assert EN.prop_block(sd, sw, 101.3, 4, p) is None                         # not known before bar 5
    assert EN.prop_block(sd, sw, 101.3, 7, replace(p, prop_zone="body")) == (102.3, pytest.approx(101.55))
    # vi_hold: a VI 99.9-100.1 under the entry (bar 7 opens above bar 6's body top); a body close under it exits
    rows = B_ROWS[:7] + [(100.1, 101.6, 99.0, 101.5)] + B_ROWS[8:9] + [(102.3, 102.6, 100.5, 100.8),
                                                                         (100.8, 100.9, 99.4, 99.5),
                                                                         (99.5, 108.0, 99.4, 107.9)]
    tr, *_ = run(day(rows), history(), Params(**{**B_POST, "adds": (0.5,), "vi_hold": True, "breaker_mt_respect": False}), {})
    t0, *_ = run(day(rows), history(), Params(**{**B_POST, "adds": (0.5,), "breaker_mt_respect": False}), {})
    assert tr and tr[0].exits[0][3] == "vi_hold" and tr[0].exits[0][1] == 99.5
    assert t0 and t0[0].exits[0][3] != "vi_hold"


def test_prints_through_helper():
    p = Params(es_pt=1.0)
    assert S._prints_through(99.99, 100.0, p) and not S._prints_through(100.0, 100.0, p)    # strict print below
    q = replace(p, fill_through=1.0)
    assert not S._prints_through(99.9, 100.0, q) and S._prints_through(99.75, 100.0, q)     # a full tick through


# =====================================================================================================
# Review fixes, second pass (entries_stops_sizing): the owner #7 add zone, ladder sizing, the SB / Ma Deuce
# hooks, stop_cc, mohawk coverage, the E12e reading switch, paper-mode risk state
# =====================================================================================================

def _zone_patch(monkeypatch, top=102.0, bot=101.6):
    """Replace htf_add_zones by one fixed 15m zone in SIDE space (scenario days have no confluence table)."""
    def zones(ctx, sd, pos, i, p):
        off = 0.0 if sd.sign > 0 else -300.0
        return [(top + off, bot + off, "15m")] if pos["stop"] < top + off < sd.c[i] else []
    monkeypatch.setattr(EN, "htf_add_zones", zones)


ADD_TAIL = B_ROWS[:11] + [(102.9, 103.0, 101.8, 102.5), (102.5, 108.0, 102.4, 107.9)]


def _sbt(rows=ADD_TAIL, mirror_=False, **kw):
    df, hist = day(rows), history()
    if mirror_:
        df, hist = mirror(df), [mirror(x) for x in hist]
    p = Params(**{**B_POST, "adds": (0.5,), "max_risk_pts": 40, **kw})
    return run(df, hist, p, {})[0]


def _adds(t):
    return [(round(float(a[1]), 2), int(a[2])) for a in t.adds]


def test_htf_add_zone_one_shot_is_spent_only_when_an_add_is_armed():
    p = Params(es_pt=1.0)
    sd = S.Side(1, np.full(10, 103.0), np.full(10, 103.5), np.full(10, 102.5), np.full(10, 103.0), 1, 0.0)
    ctx = _ctx(_Conf([(101.0, 100.0, "15m", 0, 0.0)]))
    pos = dict(stop=98.0, basis=100.0 * 10, n=10, fill_i=0, add=None, t1_done=False)
    tr = SimpleNamespace(adds=[])
    seen = []
    fail = lambda px, floor=None, extra=0.0: seen.append(extra) or False
    assert not EN.more_add_arrays(ctx, sd, pos, tr, 5, p, fail)               # no risk room under the cap: not armed
    assert not pos.get("htf_add_used")                                         # ... so the shot is NOT burned
    assert EN.more_add_arrays(ctx, sd, pos, tr, 5, replace(p, htf_add_extra_risk_pct=0.004),
                              lambda px, floor=None, extra=0.0: seen.append(extra) or True)
    assert pos["htf_add_used"] and seen == [0.0, 0.004]                        # the extra-risk switch reaches the arm call


def test_htf_add_zones_short_side_mirrors_the_long():
    p = Params(es_pt=1.0)
    short = S.Side(-1, np.full(10, 97.0), np.full(10, 97.5), np.full(10, 96.5), np.full(10, 97.0), 1, 0.0)
    # real prices: a bearish 15m FVG 100.4-101.0 ABOVE a short (entered at 100.6, inside it); noise zones that
    # must not count: a 4h one (not in add_htf_tfs), one under the price and one beyond the stop (102)
    conf = _Conf([(101.0, 100.4, "15m", 0, 0.0), (101.2, 100.9, "4h", 0, 0.0), (95.0, 94.0, "15m", 0, 0.0),
                  (104.0, 103.0, "30m", 0, 0.0)])
    pos = dict(stop=-102.0, basis=-100.6 * 10, n=10, fill_i=0, add=None, t1_done=False)
    assert EN.htf_add_zones(_ctx(conf), short, pos, 5, p) == [(-100.4, -101.0, "15m")]
    armed = []
    tr = SimpleNamespace(adds=[])
    assert EN.more_add_arrays(_ctx(conf), short, pos, tr, 5, p,
                              lambda px, floor=None, extra=0.0: armed.append((px, floor)) or True)
    assert armed == [(-100.4, -101.0)]                                         # side space: the add rests at real 100.4
    # a short filled BELOW the zone (real 100.0) never traded down through it: no add zone
    pos2 = dict(stop=-102.0, basis=-100.0 * 10, n=10, fill_i=0, add=None, t1_done=False)
    assert not EN.more_add_arrays(_ctx(conf), short, pos2, tr, 5, p, lambda px, floor=None, extra=0.0: True)


def test_htf_add_zone_arms_and_fills_in_the_engine_long_and_short(monkeypatch):
    _zone_patch(monkeypatch)
    for mir, px in ((False, 102.0), (True, 198.0)):                           # the short is the long on K - p
        assert _sbt(mirror_=mir, add_arrays=())[0].adds == []                  # switched off: no add
        # default: the 1.2% entry risk leaves ~0.1% under the 1.3% cap - the add arms, but tiny (documented)
        assert _adds(_sbt(mirror_=mir)[0]) == [(px, 34)]
        # the explicit extra-risk switch gives the add its full adds[0] size
        assert _adds(_sbt(mirror_=mir, htf_add_extra_risk_pct=0.01)[0]) == [(px, 266)]


def test_ladder_adds_use_the_full_plan_and_the_caps_scale_the_whole_ladder(monkeypatch):
    _zone_patch(monkeypatch)
    a = _sbt(entry="ladder", htf_add_extra_risk_pct=0.01)[0]
    plan = a.shares + a.adds[0][2] + a.adds[1][2]                              # rung 0 + the two later rungs
    assert a.adds[2][2] == int(plan * 0.5) and a.adds[2][2] > int(a.shares * 0.5)   # half the PLAN, not half of rung 0
    c = _sbt(entry="ladder", max_contracts_initial=300, units_per_contract=1, htf_add_extra_risk_pct=0.01)[0]
    assert (c.shares, c.adds[0][2], c.adds[1][2]) == (150, 90, 60)             # 300 contracts = 50 / 30 / 20 %
    assert c.adds[2][2] == 150
    d = _sbt(entry="ladder", max_contracts_total=400, units_per_contract=1)[0]
    held = d.shares + sum(x[2] for x in d.adds)
    assert held == 400 and len(d.adds) == 1                                    # rung 1 shrank to the room, rung 2 dropped


def test_stop_cc_fills_and_is_sized_at_the_shifted_price():
    lim = scen_a(ob_arm="touch")[0]
    cc = scen_a(ob_arm="touch", entry_order="stop_cc")[0]
    assert cc.entry == 100.25 and cc.shares < lim.shares                       # OB top 100.0 + one tick
    assert cc.shares == 600 and cc.shares * (cc.entry - cc.stop) <= 1200 + 1e-6    # 1.2% of 100k at the REAL fill price
    assert scen_a(entry_order="stop_cc") == []                                 # armed above the market: still refused


def test_engage_range_keeps_the_sweep_alive_until_the_range_has_formed():
    rows = B_ROWS[:9] + [(102.3, 102.9, 102.2, 102.8), (102.8, 103.0, 102.5, 102.9), (102.9, 103.0, 101.0, 101.5),
                         (101.5, 108.0, 101.4, 107.9)]
    run_ = lambda **kw: run(day(rows), history(), Params(**{**B_POST, "adds": (0.5,), "max_risk_pts": 40, **kw}), {})[0]
    assert len(run_()) == 1
    t = run_(engage_range_pts=4.7)           # 4.5 pts at the FVG bar, 5.0 two bars later: waits, then fills
    assert len(t) == 1 and t[0].entry == 101.3
    assert run_(engage_range_pts=9.0) == []


def test_ote_cancel_level_is_set_only_in_the_band_and_never_loosens():
    p = Params(es_pt=1.0, ote="limit", ote_cancel=True)
    lo = lambda **kw: EN.ote_cancel_level(kw.pop("entry"), 100.0, 110.0, kw.pop("existing", None), p)
    assert lo(entry=103.0) == pytest.approx(102.1)                              # 79% retrace of 100..110 = 102.1
    assert lo(entry=108.0) is None                                              # a shallow entry: no OTE cancel
    assert lo(entry=108.0, existing=101.0) == 101.0                             # ... and the other cancel is kept
    assert lo(entry=103.0, existing=102.5) == 102.5                             # the higher (more protective) wins
    assert lo(entry=103.0, existing=101.0) == pytest.approx(102.1)
    assert EN.ote_cancel_level(103.0, 100.0, 110.0, 101.0, replace(p, ote_cancel=False)) == 101.0


def test_add_cutoff_read_progress_vs_covered():
    sd = _sd([0] * 8, [100, 101, 102, 103, 104, 105, 106, 107], [0] * 8, [0] * 8)
    pos = dict(fill_i=0, leg=(100.0, 108.0), draw=110.0)
    p = Params(es_pt=1.0, add_cutoff=0.25)
    cut = lambda i, **kw: EN.add_cut_passed(sd, pos, i, replace(p, **kw))
    assert not cut(4) and cut(7) is False                                       # "covered": 75% of 100..110 needed
    assert cut(3, add_cutoff_read="progress") and not cut(2, add_cutoff_read="progress")   # 25% up from the low
    with pytest.raises(ValueError):
        Params(add_cutoff_read="x")
    assert study.DECISIONS["E12e_add_cutoff25_progress"]["add_cutoff_read"] == "progress"


def test_retest_add_uses_the_entry_zone_top():
    p = Params(es_pt=1.0, add_on="retest")
    sd = S.Side(1, np.full(10, 110.0), np.full(10, 110.5), np.full(10, 109.5), np.full(10, 110.0), 1, 0.0)
    got = []
    mk = lambda **kw: dict(stop=98.0, t1_done=False, fvg_ce=100.0, fvg_bottom=99.0, fill_i=0, basis=1000.0, n=10,
                           add=None, **kw)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(S._SM, "add_ok", lambda *a, **k: True)
        tr = SimpleNamespace(adds=[])
        EN.retest_add(sd, mk(zone_top=105.0), tr, 5, p, lambda px: got.append(px))
        EN.retest_add(sd, mk(), tr, 5, p, lambda px: got.append(px))            # no stored top: the old 2 * CE - bottom
    assert got == [105.0, 101.0]


def test_stop_pad_default_warns_about_a_dead_stop_buffer():
    with pytest.warns(UserWarning, match="stop_buffer is ignored"):
        Params(stop_buffer=0.05)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        Params(stop_buffer=0.05, stop_tick_pts=0.0)          # the old pad asked for: fine
        Params(stop_buffer=0.05, stop_pad_ticks=2.0)
        Params()
    assert Params(es_pt=0.10).pad == pytest.approx(0.025)    # SPY: a tick is 0.025, not 0.01


def test_size_up_cap_lets_the_size_up_exceed_the_total_cap():
    kw = dict(size_up_rules=("bpr", "htf_target"), htf_target_pts=100.0)
    base = scen_b()[0]
    up = scen_b(**kw)[0]
    wide = scen_b(size_up_cap_pct=0.01, **kw)[0]
    assert "size_up" in up.lv_tags and "size_up" in wide.lv_tags               # the size-up fired
    assert up.shares <= base.shares * 1.3 / 1.2 + 1                             # clamped by the 1.3% total cap
    assert wide.shares > up.shares                                              # the explicit cap switch lets it go further
    assert study.DECISIONS["E9_size_up_cap"]["size_up_cap_pct"] == 0.005


# --- Silver Bullet / Ma Deuce reach the same risk, stop and sizing hooks ------------------------------------------

def _fake_trade(t_exit, net):
    """A closed trade with one exit at `t_exit` and a net P&L of `net` (long, 1 share, no costs)."""
    return SimpleNamespace(exits=[(t_exit, 100.0 + net, 1, "stop")], adds=[], pnl=lambda cost: (net, 0.0))


def test_extras_risk_mult_replays_only_trades_closed_before_the_order():
    p = Params(es_pt=1.0, loss_halving=True, after_loss_mult=0.5, halving_floor=0.125)
    t0 = pd.Timestamp("2026-06-23 09:30", tz="America/New_York")
    at = lambda m: t0 + pd.Timedelta(minutes=m)
    loss, loss2 = _fake_trade(at(10), -5.0), _fake_trade(at(60), -5.0)
    ctx = SimpleNamespace(risk_view=dict(rs0=EN.new_risk_state(), trades=[loss, loss2]))
    assert EN.extras_risk_mult(ctx, p, at(5)) == 1.0                              # nothing closed yet
    assert EN.extras_risk_mult(ctx, p, at(10)) == 0.25                            # one loss: E10 half x after-loss half
    assert EN.extras_risk_mult(ctx, p, at(30)) == 0.25
    assert EN.extras_risk_mult(ctx, p, at(61)) == pytest.approx(0.125)            # the 60-min loss counts only afterwards
    win = _fake_trade(at(20), +50.0)
    assert EN.extras_risk_mult(ctx, p, at(61), extra=[win]) == 0.5 * 0.5          # the extras' own win ends the E10 halving
    assert EN.extras_risk_mult(SimpleNamespace(), p, at(5)) == 1.0               # no view (paper / unit): neutral
    rs = EN.new_risk_state()
    EN.replay_risk_state(rs, EN.new_risk_state(), [loss2, loss, win], p)          # exit-time order, not list order
    ref = EN.new_risk_state()
    for tr in (loss, win, loss2):
        EN.risk_state_update(ref, tr.pnl(0)[0], p)
    assert rs == ref


ES1 = Path("data/mentorship/ES_1min_db.csv").exists()


@pytest.mark.skipif(not ES1, reason="no ES 1m data")
def test_silver_bullet_gets_the_stop_modifiers_sizing_and_loss_hooks():
    es = B.load("ES", 1, source="databento")
    df = es[(es.index >= "2024-01-02") & (es.index < "2024-01-26")]
    kw = dict(FUT, sb_model=True, sb_runner=True, draw_lock="off", htf_resist_cap=False, leg_pd=0, min_draw_pts=0,
              use_bias=False)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        run_ = lambda **k: B.run(df, 1, "ES", Params(**kw, **k))
        base = run_()
        sb = base.setup.isin(["sb_am", "sb_pm"])
        assert sb.sum() >= 4
        cap = run_(max_contracts_initial=6, units_per_contract=1)                 # E11
        assert (cap[cap.setup.isin(["sb_am", "sb_pm"])].shares <= 6).all()
        mk = run_(mohawk_ticks=2.0)                                               # A4: 2 ticks further out
        m = base[sb].merge(mk, on=["entry_time", "setup"], suffixes=("", "_n"))
        assert len(m) >= 4 and ((m.stop - m.stop_n).abs().round(6) == 0.5).all()      # shorts report real prices
        hal = run_(loss_halving=True, after_loss_mult=0.5)                        # E10 / Ep08.12
        h = base[sb].merge(hal, on=["entry_time", "setup"], suffixes=("", "_n"))
        assert (h.shares_n <= h.shares).all() and (h.shares_n < h.shares).any()
        sz = run_(size_rules=("august", "fomc_week", "news_eve", "low_prob"))     # E9
        z = base[sb].merge(sz, on=["entry_time", "setup"], suffixes=("", "_n"))
        assert (z.shares_n <= z.shares).all() and (z.shares_n < z.shares).any()


@pytest.mark.skipif(not ES1, reason="no ES 1m data")
def test_ma_deuce_gets_the_stop_modifiers_and_caps():
    es = B.load("ES", 1, source="databento")
    df = es[(es.index >= "2022-01-10") & (es.index < "2022-02-25")]
    kw = dict(FUT, sb_model=False, am=(0, 0), pm=(0, 0), pre_0700=True, pre_0900=True, post_news=True, ma_deuce=True,
              leg_pd=0)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        run_ = lambda **k: B.run(df, 1, "ES", Params(**kw, **k), confluence=False)
        base = run_()
        md = base.setup == "ma_deuce"
        assert md.sum() >= 2
        cap = run_(max_contracts_initial=6, units_per_contract=1)
        assert (cap[cap.setup == "ma_deuce"].shares <= 6).all()
        mk = run_(mohawk_ticks=2.0)
        m = base[md].merge(mk, on=["entry_time", "setup"], suffixes=("", "_n"))
        assert len(m) >= 1 and ((m.stop - m.stop_n).abs().round(6) == 0.5).all()
        sz = run_(size_rules=("august", "fomc_week", "news_eve", "low_prob"), loss_halving=True, after_loss_mult=0.5)
        z = base[md].merge(sz, on=["entry_time", "setup"], suffixes=("", "_n"))
        assert (z.shares_n <= z.shares).all()


# --- paper mode carries the E10 state ------------------------------------------------------------------------

def test_paper_risk_state_load_and_save(tmp_path):
    from datetime import date as _d
    from mentorship import paper
    p = Params(loss_halving=True)
    f = tmp_path / "rs.json"
    day1, day2 = _d(2026, 6, 23), _d(2026, 6, 24)
    assert paper.load_risk_state(f, day1, p) == EN.new_risk_state()               # no file: a fresh state
    assert paper.load_risk_state(f, day1, Params()) is None                       # switch off: nothing carried
    start, end = EN.new_risk_state(), dict(m=0.5, deficit=10.0, peak=10.0)
    paper.save_risk_state(f, day1, start, end)
    assert paper.load_risk_state(f, day2, p) == end                               # next day starts from the end state
    assert paper.load_risk_state(f, day1, p) == start                             # a restart the same day re-simulates it
    paper.save_risk_state(f, day1, None, end)                                     # nothing to save when off
    assert paper.load_risk_state(f, day2, p) == end


# --- look-ahead for the new switches -------------------------------------------------------------------------

EXTRA_SETS = {
    "extras_main": dict(POST, entry="ladder", add_cutoff=0.5, add_cutoff_read="progress", add_arrays=("htf_fvg", "vi"),
                        htf_add_extra_risk_pct=0.004, size_up_rules=("bpr", "htf_target"), size_up_cap_pct=0.005,
                        ote="limit", ote_cancel=True, ob_cisd="cancel", engage_range_pts=1.0, add_on="retest",
                        max_contracts_initial=400, max_contracts_total=900, units_per_contract=1, max_risk_pts=60),
    "extras_stop_cc": dict(ob_entry="pre_break", draw_lock="off", entry_order="stop_cc", ob_arm="touch", max_risk_pts=60, mohawk_ticks=2.0,
                           trail=True, add_body_stop=True),
}


@pytest.mark.parametrize("name", list(EXTRA_SETS))
def test_look_ahead_review_fix_switches(name):
    x, y = _syn()
    _no_look_ahead(x, 5, "RW", Params(**SYN, **EXTRA_SETS[name]), COLS, every=3, partner=y, exits=True, min_trades=1)


@pytest.mark.skipif(not ES1, reason="no ES 1m data")
def test_look_ahead_silver_bullet_and_ma_deuce_hooks():
    es = B.load("ES", 1, source="databento")
    df = es[(es.index >= "2022-01-10") & (es.index < "2022-02-25")]
    p = Params(**FUT, am=(0, 0), pm=(0, 0), pre_0700=True, pre_0900=True, post_news=True, ma_deuce=True, sb_model=True,
               leg_pd=0, loss_halving=True, after_loss_mult=0.5, size_rules=("august", "low_prob"), mohawk_ticks=2.0,
               stop_all_ineff=True, nfp_stop_wide=True, max_contracts_initial=900, units_per_contract=1)
    full = _no_look_ahead(df, 1, "ES", p, COLS, every=2, exits=True, confluence=False)
    assert full.setup.isin(["ma_deuce", "sb_am", "sb_pm"]).any()
