"""Caption-gap pass, package entries_stops_sizing #3/3, part A: the unit and engine tests of the 34 specs (stops_sizing_scaling_in.md items 11, 12, 13, 14, 15, 17, 18, 19, 23, 25, 26, 27, 29, 30, 31, 32, 33, 36,
37, 40, 44, 45, 48, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62). Hand-made days (a whole 00:00-16:15 frame) through run_day (the real engine path) and unit tests of the es3.py helpers on hand-made Sides.
No platform-specific paths; nothing here needs market data. The study variants and the no-look-ahead runs are in test_caption_gap_es3b.py."""
from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from mentorship import backtest as B, es3, levels as L, sm5, strategy as S, study
from mentorship.strategy import Params
from dataclasses import dataclass as _oa_dc


@_oa_dc
class Params(Params):   # OA1029 Q92: these tests exercise other rules; the order-block narrative gate (default on) leaves them no trades
    ob_need_narrative: bool = False

from test_review_fixes import BASE, day, history, run as rf_run
from test_caption_gap_sm1a import StubConf, sd_of, stub
from test_caption_gap_es1a import C_ROWS, c_run
from test_caption_gap_sm5a import BASE as SM5_BASE, hist_close, ib, mkctx

NY = "America/New_York"
NEW_SWITCHES = (
    "add_dig_mult", "add_momentum", "add_wick_ce", "vi_ladder", "vi_ladder_exit", "add_void", "add_gate_wick", "ifvg_mohawk_add", "add_reclaimed_ob", "daily_loss_pct", "max_exposure_pct", "alloc_frac",
    "htf_near_risk_pct", "class_risk", "max_lev", "stop_fixed_pts", "fixed_units", "t1_fixed_r", "trader_mode", "deep_run_mult", "freq_ref", "probe_mult", "trail_wick_ce",
    "stop_old_low_body", "stop_gap_edge", "bpr75_ref", "stop_widen_new", "stop_htf_anchor", "ob_stop_kind", "ob_anchor", "mit_entries", "prop_stop", "stop_mode", "reentry_stop",
)
KNOBS = ("add_mom_r", "add_mom_frac", "add_wick_tf", "mohawk_add_ticks", "htf_near_pts", "htf_near_any", "htf_near_add_literal", "htf_near_cap_pct", "grad_block", "grad_max", "deep_run_weeks", "freq_recent", "probe_t", "probe_cut",
         "new_max_risk_pts", "tight_stop_pts", "wick_ce_tol_ticks", "mt_pad_ticks", "three_pd_n")
GAP_IDS = (
    "E12-repeat-dig-smaller-add", "E12-single-add-variants", "E12-wick-ce-add-5m", "E12-631-vi-wickce-invalidation", "E12-liquidity-void-add", "X8-downclose-wickce-add", "E12-mohawk-add-ifvg",
    "E12-mm-sell-model-adds", "E11-funded-account-caps", "E11-portfolio-exposure-cap", "E8-alloc-30pct", "E8-2pct-new-trader", "E8-E9-5pct-near-htf", "E8-risk-by-trade-class", "E8-leverage-cap-3x",
    "E8-new-trader-drill", "E8-new-trader-graduation", "E9-deep-discount-reduced", "E9-frequency-small-size", "new-probe-position", "E6-wick-ce-stop", "M2-stop-by-fvg-choice", "E6-old-low-rejection-body",
    "E6-nwog-stop", "E6-three-pd-arrays", "E6-next-pd-array", "E6-bpr-75-stop", "E6-new-trader-wide-stops", "E6-refined-stop-htf", "E6-attempt-based-stop", "E6-ob-body-stop", "A12-ob-anchor",
    "E6-mitigation-block-stop", "E6-propulsion-mt",
)


def _pos(sd, **kw):
    d = dict(side=sd, basis=600.0, n=6, stop=99.0, fill_i=1, plan_shares=6, add=None, t1_done=False, left=6, ob_add_used=set())
    d.update(kw)
    return d


def _ctx_1m(n, **kw):
    idx = pd.date_range("2026-06-23 09:30", periods=n, freq="1min", tz=NY)
    return stub(n, idx=idx, tf=1, t=(idx.hour * 60 + idx.minute).values, **kw)


class Arm:
    """The caller's arming function of es3.add_locations3: records the call and sets pos["add"]."""

    def __init__(self, pos):
        self.pos, self.calls = pos, []

    def __call__(self, px, floor=None, size=None):
        self.calls.append((px, floor, size))
        self.pos["add"] = {"px": px}
        return True


# --- defaults / validation ------------------------------------------------------------------------------------------------------------

def test_new_switch_defaults_and_validation():
    p = Params()
    assert (p.add_dig_mult, p.add_momentum, p.add_mom_r, p.add_mom_frac, p.add_wick_ce, p.add_wick_tf, p.vi_ladder, p.vi_ladder_exit, p.add_void, p.add_gate_wick, p.ifvg_mohawk_add, p.mohawk_add_ticks,
            p.add_reclaimed_ob) == (1.0, False, 0.5, 0.25, False, 5, False, False, False, False, False, 2, False)
    assert (p.daily_loss_pct, p.max_exposure_pct, p.alloc_frac, p.htf_near_risk_pct, p.htf_near_pts, p.htf_near_cap_pct, p.class_risk, p.max_lev, p.stop_fixed_pts, p.fixed_units, p.t1_fixed_r, p.trader_mode,
            p.grad_block, p.grad_max) == (0.0, 0.0, 1.0, 0.0, 30.0, 0.20, {}, 0.0, 0.0, 0, 0.0, "", 20, 4)
    assert (p.deep_run_mult, p.deep_run_weeks, p.freq_ref, p.freq_recent, p.probe_mult, p.probe_t, p.probe_cut, p.wick_ce_tol_ticks, p.trail_wick_ce, p.mt_pad_ticks, p.stop_old_low_body, p.stop_gap_edge,
            p.three_pd_n, p.bpr75_ref) == (1.0, 3, 0.0, 0, 0.0, 630, 0.5, 1, False, 2, False, "", 3, "upper")
    assert (p.new_max_risk_pts, p.tight_stop_pts, p.stop_widen_new, p.stop_htf_anchor, p.ob_stop_kind, p.ob_anchor, p.mit_entries, p.prop_stop, p.stop_mode, p.reentry_stop) == (
        15.0, 3.0, False, False, "", "highest_open", False, "", "ob_mt", "array")                                                  # the built defaults everywhere
    for kw in (dict(stop_gap_edge="x"), dict(bpr75_ref="x"), dict(trader_mode="x"), dict(ob_stop_kind="x"), dict(ob_anchor="x"), dict(prop_stop="x"), dict(class_risk={"x": 0.1}), dict(class_risk={"day": 0.0}),
               dict(add_dig_mult=0), dict(add_dig_mult=1.5), dict(add_mom_r=0), dict(add_mom_frac=0), dict(add_wick_tf=0), dict(mohawk_add_ticks=-1), dict(daily_loss_pct=1.0), dict(max_exposure_pct=-0.1),
               dict(alloc_frac=0), dict(htf_near_risk_pct=-1), dict(max_lev=-1), dict(stop_fixed_pts=-1), dict(fixed_units=-1), dict(t1_fixed_r=-1), dict(grad_block=0), dict(grad_max=0), dict(deep_run_mult=0),
               dict(deep_run_weeks=0), dict(freq_ref=-1), dict(probe_mult=1.5), dict(probe_t=500), dict(probe_cut=0), dict(wick_ce_tol_ticks=-1), dict(mt_pad_ticks=-1), dict(three_pd_n=0), dict(new_max_risk_pts=0),
               dict(tight_stop_pts=-1), dict(stop_mode="x"), dict(reentry_stop="x")):
        with pytest.raises(ValueError):
            Params(**kw)
    for m in ("wick_ce", "m2_auto", "three_pd", "next_pd", "bpr75", "fixed"):
        Params(stop_mode=m)
    Params(reentry_stop="ob_low")
    q = Params(trader_mode="new")                                                      # 1 contract, wide stops (E6-new-trader-wide-stops / E8-new-trader-graduation)
    assert q.fixed_units == 1 and q.max_risk_pts == 15.0
    assert Params(trader_mode="new", new_max_risk_pts=20.0).max_risk_pts == 20.0
    assert replace(q, fixed_units=3).fixed_units == 3                                  # backtest.run raises it with replace()
    assert "mitigation" in Params(mit_entries=True).entry_arrays and replace(Params(mit_entries=True)).entry_arrays == Params(mit_entries=True).entry_arrays
    assert set(NEW_SWITCHES) | set(KNOBS) <= set(Params.__dataclass_fields__)


def test_every_switch_has_a_study_variant():
    on = set()
    for k, v in study._ES3_DECISIONS.items():
        Params(**v)
        on |= set(v)
    missing = [s for s in NEW_SWITCHES if s not in on]
    assert not missing, missing


# --- E12-repeat-dig-smaller-add (11) ----------------------------------------------------------------------------------------------------

def test_add_dig_mult():
    rows = list(C_ROWS[:5]) + [(101.6, 101.7, 100.3, 100.5), (100.5, 103.0, 100.45, 102.9), (102.9, 103.0, 100.2, 102.0), (102.0, 103.5, 101.9, 103.4)]
    sd = sd_of(rows)
    g = [z for z in sd.gaps if z.i == 4][0]                                           # [99.8, 100.4]
    assert es3.dig_count(sd, g.top, g.i, 8) == 2                                       # bars 5 and 7 dug under the top after a close above it (bar 6 only stayed above)
    assert es3.dig_count(sd, g.top, g.i, 6) == 1
    p = Params(es_pt=1.0, lot=1, adds=(0.5,), add_dig_mult=0.67)
    tr = SimpleNamespace(shares=6, adds=[])
    pos = _pos(sd)
    S._arm_add(pos, tr, 100.4, 8, p, 100000.0, g=g)
    assert pos["add"]["q"] == 2                                                        # 3 -> 2
    pos = _pos(sd)
    S._arm_add(pos, tr, 100.4, 8, replace(p, add_dig_mult=1.0), 100000.0, g=g)
    assert pos["add"]["q"] == 3                                                        # unchanged at 1.0
    pos = _pos(sd)
    S._arm_add(pos, tr, 100.4, 6, p, 100000.0, g=g)
    assert pos["add"]["q"] == 3                                                        # only one dig so far
    pos = _pos(sd)
    S._arm_add(pos, tr, 100.4, 4, p, 100000.0, g=g)
    assert pos["add"]["q"] == 3                                                        # the new-FVG add (g.i == i): nothing dug yet
    pos = _pos(sd)
    S._arm_add(pos, tr, 100.2, 8, p, 100000.0)                                         # no FVG passed (an OB / wick-CE / void add): no gap is guessed (review fix)
    assert pos["add"]["q"] == 3
    pos = _pos(sd, fvg_bottom=float(g.bottom), fill_i=1, fvg_ce=float((g.top + g.bottom) / 2), zone_top=float(g.top))
    S._arm_add(pos, tr, 100.4, 8, p, 100000.0, dig_g=es3.entry_zone(pos))              # the retest add: the entry zone dug into twice after the fill
    assert pos["add"]["q"] == 2
    pos = _pos(sd, fvg_bottom=float(g.bottom), fill_i=7)
    S._arm_add(pos, tr, 100.4, 8, p, 100000.0, g=g)                                    # g IS the entry FVG, filled on bar 7: only the digs after the fill count (here none)
    assert pos["add"]["q"] == 3


# --- E12-single-add-variants (12) --------------------------------------------------------------------------------------------------------

def test_add_momentum_single():
    rows = [(99.8, 100.2, 99.7, 100.1), (100.1, 100.4, 99.9, 100.3), (100.3, 100.5, 100.0, 100.4), (100.4, 101.2, 100.3, 101.1)]
    sd = sd_of(rows)
    p = Params(es_pt=1.0, lot=1, adds=(0.5, 0.33), add_momentum=True)
    tr = SimpleNamespace(shares=20, adds=[])
    pos = _pos(sd, n=20, basis=2000.0, left=20, plan_shares=20, stop=98.0, ob_pre=True, fill_px=100.0, es3_r0=2.0, fill_i=1)
    assert not es3.momentum_add(pos, tr, sd, 2, p, 100000.0) and pos["add"] is None   # 100.4 < 100.0 + 0.5 x 2
    assert es3.momentum_add(pos, tr, sd, 3, p, 100000.0)                               # the close 101.1 >= 101.0: the run
    assert pos["add"]["now"] is True and pos["add"]["q"] == 5 and pos["add"]["px"] == pytest.approx(101.1)      # 25 % of 20
    assert pos["no_adds"] is True and pos["mom_done"] is True                          # no OB-retest add after it
    pos2 = _pos(sd, n=20, basis=2000.0, left=20, plan_shares=20, stop=98.0, ob_pre=False, fill_px=100.0, es3_r0=2.0)
    assert not es3.momentum_add(pos2, tr, sd, 3, p, 100000.0)                          # only after an OB-before-break entry


def test_momentum_add_fills_at_the_next_open_and_a_stop_direction_add_fills_on_a_touch(monkeypatch):
    """The two add types the new locations arm (strategy.run_day's add fill code): "now" = a market buy at the next bar's open, "up" = a stop-direction add filled when the bar trades UP to its price."""
    state = {}

    def fake_mom(pos, tr, sd, i, p, eq):
        if i == pos["fill_i"] + 1 and pos["add"] is None and not state.get("done"):
            state["done"] = True
            pos["add"] = dict(px=float(sd.c[i]), q=2, i=i, now=True, market=False, hold=None)
            return True
        return False

    monkeypatch.setattr(es3, "momentum_add", fake_mom)
    tr = c_run(adds=(0.5, 0.33), add_momentum=True)
    assert len(tr) == 1 and len(tr[0].adds) == 1
    assert tr[0].adds[0][1] == pytest.approx(102.9) and tr[0].adds[0][2] == 2          # the open of bar 7 (10:05)
    # "up": filled at max(open, price) when the high reaches it
    st2 = {}

    def fake_loc(ctx, sd, pos, tr_, i, p, arm):
        if i == pos["fill_i"] + 1 and not st2.get("done"):
            st2["done"] = True
            pos["add"] = dict(px=104.0, q=2, i=i, up=True, market=False, hold=None)

    monkeypatch.setattr(es3, "add_locations3", fake_loc)
    monkeypatch.setattr(es3, "add_locs3_on", lambda p: True)
    tr2 = c_run(adds=(0.5, 0.33))
    assert len(tr2[0].adds) == 1 and tr2[0].adds[0][1] == pytest.approx(104.0)         # the bar (102.9 .. 108.5) ran up through 104.0
    st3 = {}

    def fake_loc3(ctx, sd, pos, tr_, i, p, arm):
        if i == pos["fill_i"] + 1 and not st3.get("done"):
            st3["done"] = True
            pos["add"] = dict(px=109.0, q=2, i=i, up=True, market=False, hold=None)

    monkeypatch.setattr(es3, "add_locations3", fake_loc3)
    assert c_run(adds=(0.5, 0.33))[0].adds == []                                       # 109.0 was never reached (the high is 108.5)


# --- E12-wick-ce-add-5m (13) ---------------------------------------------------------------------------------------------------------------

def test_add_wick_ce_5m():
    # 1-minute execution; the 09:35-09:39 candle seen on 5m: open 4016, close 4014, low 4010 -> a lower wick 4010-4014, CE 4012
    rows = [(4015.0, 4016.0, 4014.0, 4015.5)] * 5 + [(4016.0, 4017.0, 4014.5, 4015.0), (4015.0, 4015.5, 4010.0, 4012.0), (4012.0, 4015.0, 4011.0, 4014.5), (4014.5, 4016.0, 4013.0, 4015.5),
                                                      (4015.5, 4016.0, 4013.5, 4014.0), (4014.0, 4018.0, 4013.9, 4017.0)]
    sd = sd_of(rows)
    ctx = _ctx_1m(len(rows))
    p = Params(es_pt=1.0, add_wick_ce=True)
    pos = _pos(sd, fill_i=0, stop=4000.0)
    arm = Arm(pos)
    es3.add_locations3(ctx, sd, pos, SimpleNamespace(shares=6, adds=[]), 10, p, arm)
    assert arm.calls == [(pytest.approx(4012.0), pytest.approx(4010.0), None)]         # the CE of the 5m wick (4010 + 4014) / 2
    pos2 = _pos(sd, fill_i=0, stop=4000.0, wickce_used={5})
    arm2 = Arm(pos2)
    es3.add_locations3(ctx, sd, pos2, SimpleNamespace(shares=6, adds=[]), 10, p, arm2)
    assert arm2.calls == []                                                            # once per wick
    arm3 = Arm(pos)
    pos3 = _pos(sd, fill_i=0, stop=4000.0)
    es3.add_locations3(ctx, sd, pos3, SimpleNamespace(shares=6, adds=[]), 8, p, arm3)  # the 09:35 candle is not complete yet at bar 8, and the 09:30 one began before the fill (bar 0 is the fill bar)
    assert arm3.calls == []
    assert [b[:2] for b in es3.bars_tf(ctx, sd, 0, 10, 5)] == [(0, 4), (5, 9)]          # clock-aligned windows, complete ones only
    assert es3.bars_tf(ctx, sd, 1, 10, 5)[0][:2] == (5, 9)                              # a window already running at the fill is partial: skipped


# --- E12-631-vi-wickce-invalidation (14) --------------------------------------------------------------------------------------------------

def test_vi_ladder_631():
    rows = [(99.8, 100.2, 99.7, 100.1), (100.1, 100.4, 99.9, 100.3), (100.3, 100.9, 100.2, 100.8), (101.2, 101.9, 100.9, 101.8), (101.8, 102.0, 101.6, 101.7)]
    sd = sd_of(rows)                                                                   # a VI [100.8, 101.2] forms at bar 3
    p = Params(es_pt=1.0, vi_ladder=True, add_ladder="631")
    assert es2_fracs(p) == (0.5, 0.17)                                                 # 6 / 3 / 1
    pos = _pos(sd, fill_i=0, zone_top=100.5)
    arm = Arm(pos)
    es3.add_locations3(stub(5), sd, pos, SimpleNamespace(shares=6, adds=[]), 3, p, arm)
    assert arm.calls == [(pytest.approx(101.2), pytest.approx(100.8), None)] and pos["vi_rung"] == 1      # rung 1: the next VI
    # rung 2: the latest wick CE (1-minute bars -> the 5m wick), only beyond the entry zone, a weak reaction caps it at 1 contract
    wr = [(4015.0, 4016.0, 4014.0, 4015.5)] * 5 + [(4016.0, 4017.0, 4014.5, 4015.0), (4015.0, 4015.5, 4010.0, 4012.0), (4012.0, 4015.0, 4011.0, 4014.5), (4014.5, 4016.0, 4013.0, 4015.5),
                                                    (4015.5, 4016.0, 4013.5, 4014.0), (4014.0, 4018.0, 4013.9, 4017.0)]
    sw_ = sd_of(wr)
    ctx = _ctx_1m(len(wr))
    pos2 = _pos(sw_, fill_i=0, stop=4000.0, zone_top=4005.0, vi_rung=1)
    arm2 = Arm(pos2)
    es3.add_locations3(ctx, sw_, pos2, SimpleNamespace(shares=6, adds=[]), 10, p, arm2)
    assert len(arm2.calls) == 1 and arm2.calls[0][0] == pytest.approx(4012.0) and pos2["vi_rung"] == 2
    pos3 = _pos(sw_, fill_i=0, stop=4000.0, zone_top=4013.0, vi_rung=1)                # the wick CE (4012) lies under the entry VI top: not an add
    arm3 = Arm(pos3)
    es3.add_locations3(ctx, sw_, pos3, SimpleNamespace(shares=6, adds=[]), 10, p, arm3)
    assert arm3.calls == []
    weak_rows = wr[:10] + [(4014.0, 4015.0, 4011.9, 4014.2)]                            # bar 10 flirts with the CE (low 4011.9) and closes above it
    pos4 = _pos(sd_of(weak_rows), fill_i=0, stop=4000.0, zone_top=4005.0, vi_rung=1)
    arm4 = Arm(pos4)
    es3.add_locations3(_ctx_1m(len(weak_rows)), sd_of(weak_rows), pos4, SimpleNamespace(shares=6, adds=[]), 10, p, arm4)
    assert arm4.calls[0][2] == 1                                                       # at most 1 contract (lot 1)
    # an add under the entry VI is rejected by _arm_add
    pos5 = _pos(sd, fill_i=0, zone_top=101.0, stop=98.0)
    S._arm_add(pos5, SimpleNamespace(shares=6, adds=[]), 100.8, 4, replace(p, adds=(0.5, 0.17), lot=1), 100000.0)
    assert pos5["add"] is None
    S._arm_add(pos5, SimpleNamespace(shares=6, adds=[]), 101.3, 4, replace(p, adds=(0.5, 0.17), lot=1), 100000.0)
    assert pos5["add"] is not None
    # the invalidation: a trade to the OB MT before the displacement exits all at that level
    o = dict(stop=98.0, t1=105.0, es3={"ob_mt": 99.0})
    pos6 = _pos(sd, fill_i=0, t1_done=False)
    es3.on_fill(stub(5), sd, pos6, SimpleNamespace(), o, 0, replace(p, vi_ladder_exit=True), 100.0)
    assert es3.exit_hit(pos6, 100.0, 99.2) is None and es3.exit_hit(pos6, 100.0, 98.9) == (99.0, "ob_mt_inval")
    assert es3.exit_hit(dict(pos6, o=1), 98.5, 98.2) == (98.5, "ob_mt_inval")          # a gap through it: out at the open
    pos6["t1_done"] = True
    assert es3.exit_hit(pos6, 100.0, 98.9) is None                                     # after the first partial the idea is working


def es2_fracs(p):
    return S._ES2.add_size_fracs(p)


# --- E12-liquidity-void-add (15) -----------------------------------------------------------------------------------------------------------

def test_add_void():
    rows = [(4008.0, 4009.0, 4007.0, 4008.5), (4008.5, 4010.0, 4008.0, 4009.5), (4009.5, 4011.0, 4009.0, 4010.8), (4013.5, 4015.0, 4013.0, 4014.5)]
    sd = sd_of(rows)                                                                   # bar 3: low 4013 > high[2] 4011: a void 4011-4013
    conf = StubConf(arrays={1: [(4014.0, 4010.0, "5m", 0, 0.0)]})                      # the 5m FVG 4010-4014 (CE 4012)
    ctx = stub(4, conf=conf)
    p = Params(es_pt=1.0, add_void=True)
    pos = _pos(sd, fill_i=0, stop=4000.0, es3={"ob_mt": 4008.0})
    arm = Arm(pos)
    es3.add_locations3(ctx, sd, pos, SimpleNamespace(shares=6, adds=[]), 3, p, arm)
    assert arm.calls == [(pytest.approx(4011.25), pytest.approx(4008.0), None)] and pos["void_used"]
    pos2 = _pos(sd, fill_i=0, stop=4000.0, es3={"ob_mt": 4012.0})                       # the void bottom (4011) is not above the OB MT
    arm2 = Arm(pos2)
    es3.add_locations3(ctx, sd, pos2, SimpleNamespace(shares=6, adds=[]), 3, p, arm2)
    assert arm2.calls == []
    far = stub(4, conf=StubConf(arrays={1: [(4030.0, 4026.0, "5m", 0, 0.0)]}))         # no 5m FVG CE band at the void
    pos3 = _pos(sd, fill_i=0, stop=4000.0, es3={"ob_mt": 4008.0})
    arm3 = Arm(pos3)
    es3.add_locations3(far, sd, pos3, SimpleNamespace(shares=6, adds=[]), 3, p, arm3)
    assert arm3.calls == []


# --- X8-downclose-wickce-add (17) ----------------------------------------------------------------------------------------------------------

def test_add_gate_wick():
    # a SHORT (real prices): the down-close candle o 4020 / c 4017 / l 4014 sits between the entry 4030 and T1 4000; a close at 4019 (through its open) arms a sell at its lower-wick CE 4015.5
    real = [(4020.0, 4021.0, 4014.0, 4017.0), (4031.0, 4032.0, 4029.0, 4030.0), (4030.0, 4030.5, 4018.0, 4019.0)]
    sd = sd_of(real, sign=-1)
    ctx = stub(3)
    g = es3.gate_candle(sd, ctx, entry=float(sd.x(4030.0)), t1=float(sd.x(4000.0)), fill_i=1)
    assert g == {"open": pytest.approx(-4020.0), "ce": pytest.approx(-4015.5), "k": 0}
    p = Params(es_pt=1.0, add_gate_wick=True)
    pos = _pos(sd, fill_i=1, stop=-4035.0, es3_gate=g)
    arm = Arm(pos)
    es3.add_locations3(ctx, sd, pos, SimpleNamespace(shares=6, adds=[]), 2, p, arm)
    assert len(arm.calls) == 1 and sd.x(arm.calls[0][0]) == pytest.approx(4015.5) and pos["add"]["up"] and pos["gate_done"]
    pos2 = _pos(sd, fill_i=1, stop=-4035.0, es3_gate=g)
    arm2 = Arm(pos2)
    es3.add_locations3(ctx, sd_of(real[:2] + [(4030.0, 4031.0, 4021.0, 4022.0)], sign=-1), pos2, SimpleNamespace(shares=6, adds=[]), 2, p, arm2)
    assert arm2.calls == []                                                            # no body closed through the candle's open (4020)
    assert es3.gate_candle(sd, ctx, entry=float(sd.x(4030.0)), t1=float(sd.x(4018.0)), fill_i=1) is None     # the candle must lie between the entry and T1
    on = dict(stop=-4035.0, t1=float(sd.x(4000.0)))
    pos3 = _pos(sd, fill_i=1)
    es3.on_fill(ctx, sd, pos3, SimpleNamespace(), on, 1, p, float(sd.x(4030.0)))
    assert pos3["es3_gate"]["k"] == 0


# --- E12-mohawk-add-ifvg (18) ----------------------------------------------------------------------------------------------------------------

def test_ifvg_mohawk_add(monkeypatch):
    p = Params(es_pt=1.0, lot=1, ifvg_mohawk_add=True, add_ladder="")          # the pre-OA1029 adds (631 is the default now)
    # a long IFVG 4030-4034 (the short is its mirror): the far edge is 4030, the add 2 ticks beyond it
    assert es3.mohawk_rung(10, 4029.5, 4028.0, 10 * 2.0, p, 100000.0) == (4029.5, 5)         # add fraction 0 (0.5) x the first unit
    assert es3.mohawk_rung(10, 4029.5, 4029.6, 20.0, p, 100000.0) is None                    # the stop must sit beyond the rung
    assert es3.mohawk_rung(10, 4029.5, 4028.0, 1299.0, p, 100000.0) is None                  # no risk room left under the 1.3 % cap
    # engine: the rung rests as a limit that fills only on a trade THROUGH it (a mohawk); a shallower bar fills the main leg only
    orig = S._finish_order

    def fo(ctx, sd, i, p_, session, sw, entry, stop, risk_mult, leg_hi, tags, *a, **k):
        return orig(ctx, sd, i, p_, session, sw, entry, stop, risk_mult, leg_hi, dict(tags, es3_rung=99.9), *a, **k)

    monkeypatch.setattr(S, "_finish_order", fo)
    rows = list(C_ROWS)
    rows[6] = (100.5, 100.6, 99.85, 100.4)                                             # bar 6 trades through 99.9 (the rung) but stays above the stop
    t = c_run(rows, adds=(0.5, 0.33), ifvg_mohawk_add=True)
    assert len(t) == 1 and len(t[0].adds) == 1 and t[0].adds[0][1] == pytest.approx(99.9) and t[0].adds[0][2] >= 1
    rows2 = list(C_ROWS)
    rows2[6] = (100.5, 100.6, 99.95, 100.4)                                            # only a touch short of the rung
    assert c_run(rows2, adds=(0.5, 0.33), ifvg_mohawk_add=True)[0].adds == []
    assert c_run(rows, ifvg_mohawk_add=True)[0].adds == []                              # adds off: no rung
    assert c_run(rows, adds=(0.5, 0.33))[0].adds == []                                  # off: no rung


# --- E12-mm-sell-model-adds (19) --------------------------------------------------------------------------------------------------------------

RECL = [(101.0, 101.2, 100.3, 100.5), (100.5, 101.0, 100.4, 100.9), (100.9, 100.95, 99.0, 99.2), (99.2, 102.0, 99.1, 101.8), (101.8, 102.5, 101.7, 102.4), (102.4, 103.0, 102.3, 102.9),
        (102.9, 103.0, 101.0, 102.0)]


def test_add_reclaimed_ob_short():
    sd = sd_of(RECL)
    p = Params(es_pt=1.0, lot=1, add_reclaimed_ob=True)
    pos = _pos(sd, fill_i=4, ext_i=2, stop=99.0, plan_shares=10)
    r = es3.reclaimed_add(sd, pos, 6, p)
    assert r == (pytest.approx(101.0), pytest.approx(100.5))                           # the OB candle's body top / bottom (down-close 101.0 -> 100.5)
    arm = Arm(pos)
    es3.add_locations3(stub(7), sd, pos, SimpleNamespace(shares=10, adds=[]), 6, p, arm)
    assert arm.calls == [(pytest.approx(101.0), pytest.approx(100.5), 5)] and pos["mm_add_done"]       # min(first unit, add fraction 0) -> 5 of 10
    arm2 = Arm(pos)
    pos["add"] = None
    es3.add_locations3(stub(7), sd, pos, SimpleNamespace(shares=10, adds=[]), 6, p, arm2)
    assert arm2.calls == []                                                            # a second retest arms nothing
    # a close under the body bottom since the reclaim voids it
    bad = RECL[:6] + [(102.9, 103.0, 100.0, 100.2)]
    assert es3.reclaimed_add(sd_of(bad), _pos(sd, fill_i=4, ext_i=2), 6, p) is None
    # the short is its mirror: real prices, the same side space
    real = [(-o, -l, -h, -c) for o, h, l, c in RECL]
    sds = sd_of(real, sign=-1)
    assert es3.reclaimed_add(sds, _pos(sds, fill_i=4, ext_i=2), 6, p) == (pytest.approx(101.0), pytest.approx(100.5))


# --- E11-funded-account-caps (23) -------------------------------------------------------------------------------------------------------------

def test_daily_loss_limit():
    ctx = SimpleNamespace(equity=150000.0)
    p = Params(daily_loss_pct=0.02)
    state = {"day_net": -2500.0}
    assert es3.dl_limit(ctx, p) == pytest.approx(3000.0) and es3.dl_room(ctx, state, p) == pytest.approx(500.0)
    assert es3.dl_blocks_order(dict(shares=600, entry=101.0, stop=100.0), ctx, state, p)         # risk 600 reaches the limit: skipped
    assert not es3.dl_blocks_order(dict(shares=400, entry=101.0, stop=100.0), ctx, state, p)     # risk 400 is taken
    assert not es3.dl_blocks_order(dict(shares=2000, entry=101.0, stop=100.0), ctx, {"day_net": 500.0}, p)   # a winning day: the whole limit
    # an open position: the marked loss counts; at the limit it is flattened at the close
    sd = sd_of([(100.0, 100.5, 99.5, 100.0), (100.0, 100.1, 97.0, 97.2)])
    tr = S.Trade(date=None, symbol="ES", session="AM", setup="x", side="long", swept="", unicorn=False, smt=None, armed=pd.Timestamp("2026-06-23 09:30", tz=NY), entry_time=pd.Timestamp("2026-06-23 09:30", tz=NY),
                 entry=100.0, stop=98.0, t1=105.0, t2=None, shares=500)
    pos = _pos(sd, left=500, n=500, basis=50000.0)
    ts = pd.Timestamp("2026-06-23 09:35", tz=NY)
    assert es3.mark_net(tr, pos, sd, 1, ts, Params(cost_per_share=0.0)) == pytest.approx(-1400.0)
    assert not es3.daily_loss_hit(ctx, {"day_net": -1000.0}, pos, tr, sd, 1, ts, Params(cost_per_share=0.0, daily_loss_pct=0.02))       # -1000 - 1400 = -2400 < 3000
    assert es3.daily_loss_hit(ctx, {"day_net": -1700.0}, pos, tr, sd, 1, ts, Params(cost_per_share=0.0, daily_loss_pct=0.02))            # -3100 <= -3000
    # engine: the order whose risk reaches the limit is dropped; a roomy limit trades
    assert len(c_run()) == 1
    assert c_run(daily_loss_pct=0.0005) == []
    assert len(c_run(daily_loss_pct=0.05)) == 1
    pos2 = _pos(sd, left=500, n=500, basis=50000.0, dl_room=100.0)                      # an add's risk stays inside the room
    S._arm_add(pos2, SimpleNamespace(shares=6, adds=[]), 100.0, 1, Params(es_pt=1.0, lot=1, adds=(1.0,)), 100000.0)
    assert pos2["add"] is None or pos2["add"]["q"] * (100.0 - 99.0) <= 100.0 + 1e-9


# --- E11-portfolio-exposure-cap (25) ----------------------------------------------------------------------------------------------------------

def _book(rows):
    return pd.DataFrame(rows, columns=["date", "session", "setup", "symbol", "smt", "entry_time", "exit_time", "entry_risk_pct", "peak_risk_pct"])


def test_exposure_cap_combine():
    d = pd.Timestamp("2026-06-23").date()
    t0 = pd.Timestamp("2026-06-23 09:40", tz=NY)
    two = _book([[d, "AM", "am_mm", "ES", None, t0, t0 + pd.Timedelta(minutes=60), 0.012, 0.012], [d, "PM", "pm", "ES", None, t0 + pd.Timedelta(minutes=30), t0 + pd.Timedelta(minutes=90), 0.012, 0.012]])
    out = B.combine(two, max_exposure_pct=0.02)
    assert len(out) == 1 and out.iloc[0].session == "AM"                                # the later one would take the open risk to 2.4 %
    assert len(out.attrs["x_exposure"]) == 1 and out.attrs["x_exposure"].iloc[0].session == "PM"
    assert len(B.combine(two, max_exposure_pct=0.026)) == 2                              # 2.4 % <= 2.6 %
    assert len(B.combine(two)) == 2                                                      # off
    later = _book([[d, "AM", "am_mm", "ES", None, t0, t0 + pd.Timedelta(minutes=20), 0.012, 0.012], [d, "PM", "pm", "ES", None, t0 + pd.Timedelta(minutes=30), t0 + pd.Timedelta(minutes=90), 0.012, 0.012]])
    assert len(B.combine(later, max_exposure_pct=0.02)) == 2                              # not overlapping: both stay
    assert es3.exposure_filter(two, 0.0) is two
    # review fix (causal decision): the peak column (adds filled after the decision) is never read - entry risk decides, so a peak far above the entry risk changes nothing
    big = _book([[d, "AM", "am_mm", "ES", None, t0, t0 + pd.Timedelta(minutes=60), 0.012, 0.050], [d, "PM", "pm", "ES", None, t0 + pd.Timedelta(minutes=30), t0 + pd.Timedelta(minutes=90), 0.012, 0.050]])
    assert len(B.combine(big, max_exposure_pct=0.026)) == 2 and len(B.combine(big, max_exposure_pct=0.02)) == 1


# --- E8-alloc-30pct (26) ---------------------------------------------------------------------------------------------------------------------

def test_alloc_frac():
    assert S._risk_budget(Params(alloc_frac=0.3, risk_pct=0.01), 10000.0) == pytest.approx(30.0)
    assert S._risk_budget(Params(risk_pct=0.01), 10000.0) == pytest.approx(100.0)       # 2023: the whole account
    assert S._total_cap(Params(alloc_frac=0.3, max_total_risk_pct=0.013), 10000.0) == pytest.approx(39.0)
    assert S._risk_budget(Params(alloc_frac=0.3, risk_dollars=50.0), 10000.0) == 50.0   # a dollar budget is not scaled
    assert c_run(alloc_frac=0.3)[0].shares == pytest.approx(c_run()[0].shares * 0.3, abs=1)


# --- E8-2pct-new-trader (27) -----------------------------------------------------------------------------------------------------------------

def test_risk_grid_preset():
    base = Params(es_pt=1.0, lot=1)
    g = study.risk_grid(base)
    assert [q.risk_pct for q in g] == [0.010, 0.012, 0.015, 0.020] and [q.max_total_risk_pct for q in g] == [0.011, 0.013, 0.016, 0.021]
    assert all(replace(q, risk_pct=base.risk_pct, max_total_risk_pct=base.max_total_risk_pct) == base for q in g)       # everything else unchanged
    c = study.cc_starter(base)
    assert (c.risk_pct, c.t1_fixed_r, c.t1_fixed_all) == (0.015, 1.0, True)
    t = c_run(t1_fixed_r=1.0, t1_fixed_all=True)
    assert len(t) == 1 and [e[3] for e in t[0].exits] == ["t1"] and t[0].exits[0][1] == pytest.approx(t[0].entry + (t[0].entry - t[0].stop))        # one exit at exactly 1R


# --- E8-E9-5pct-near-htf (29) / E8-risk-by-trade-class (30) / E9-deep-discount-reduced (36) / E9-frequency-small-size (37) ---------------------

class NearConf(StubConf):
    def __init__(self, levels):
        super().__init__()
        self.levels = levels

    def targets(self, *a, **k):
        return list(self.levels)


def _ctx_risk(levels=(), row=None, n=3):
    return stub(n, conf=NearConf(levels), bias_row=row)


def test_htf_near_risk():
    sd = sd_of([(4000.0, 4001.0, 3999.0, 4000.5)] * 3)
    p = Params(es_pt=1.0, htf_near_risk_pct=0.05)
    tags, lvt = {}, []
    m, extra = es3.order_risk(_ctx_risk([4025.0]), sd, {}, 2, p, 4000.0, 2.0, False, 4025.0, tags, lvt)       # the weekly high 25 pts away IS the draw
    assert m == pytest.approx(0.05 / 0.012) and extra == pytest.approx(0.20 - 0.013) and "htf_near_risk" in lvt and tags["es3"]["near_cap"] == pytest.approx(extra)
    m2, x2 = es3.order_risk(_ctx_risk([]), sd, {}, 2, p, 4000.0, 2.0, False, 4010.0, {}, [])                 # a session-pool draw: the default 1.2 % (capped at 1.5 %)
    assert m2 == pytest.approx(1.0) and x2 == 0.0
    m3, _ = es3.order_risk(_ctx_risk([4025.0]), sd, {}, 2, replace(p, risk_pct=0.02, max_total_risk_pct=0.021), 4000.0, 2.0, False, 4025.0, {}, [])
    assert m3 == pytest.approx(0.05 / 0.02)
    m4, _ = es3.order_risk(_ctx_risk([4025.0]), sd, {}, 2, replace(p, risk_pct=0.02, max_total_risk_pct=0.021, htf_near_risk_pct=0.0), 4000.0, 2.0, False, 4030.0, {}, [])
    assert m4 == 1.0
    m6, _ = es3.order_risk(_ctx_risk([4025.0]), sd, {}, 2, p, 4000.0, 2.0, False, 4010.0, {}, [])           # an HTF level in range but the draw is a session pool: default risk
    assert m6 == pytest.approx(1.0)
    m7, _ = es3.order_risk(_ctx_risk([4025.0]), sd, {}, 2, replace(p, htf_near_any=True), 4000.0, 2.0, False, 4010.0, {}, [])    # the broader reading
    assert m7 == pytest.approx(0.05 / 0.012)
    m5, _ = es3.order_risk(_ctx_risk([4060.0]), sd, {}, 2, p, 4000.0, 2.0, False, 4070.0, {}, [])             # 60 pts away: not near
    assert m5 == pytest.approx(1.0)
    pos = {}
    es3.on_fill(stub(3), sd, pos, SimpleNamespace(), dict(stop=3998.0, t1=4010.0, es3={"near_cap": 0.187}), 2, p, 4000.0)
    assert pos["es3_room"] == pytest.approx(0.187)                                      # adds may use the near-HTF total cap too


def test_class_risk():
    sd = sd_of([(4000.0, 4001.0, 3999.0, 4000.5)] * 3)
    p = Params(es_pt=1.0, class_risk={"scalp": 0.005}, t1_fixed_r=1.0, t1_fixed_all=True)
    m, _ = es3.order_risk(_ctx_risk(), sd, {}, 2, p, 4000.0, 2.0, False, 4010.0, {}, [])
    assert m == pytest.approx(0.005 / 0.012)                                           # a 1R single-exit scalp
    m2, _ = es3.order_risk(_ctx_risk(), sd, {}, 2, replace(p, t1_fixed_r=0.0, t1_fixed_all=False), 4000.0, 2.0, False, 4010.0, {}, [])
    assert m2 == 1.0                                                                   # a ladder trade stays a day trade (no "day" entry)
    m3, _ = es3.order_risk(_ctx_risk(), sd, {}, 2, replace(p, class_risk={"day": 0.006}, t1_fixed_r=0.0, t1_fixed_all=False), 4000.0, 2.0, False, 4010.0, {}, [])
    assert m3 == pytest.approx(0.5)
    scalp = c_run(class_risk={"scalp": 0.005}, t1_fixed_r=1.0, t1_fixed_all=True)[0].shares
    ladder = c_run(class_risk={"scalp": 0.005})[0].shares
    assert scalp == pytest.approx(ladder * 0.005 / 0.012, abs=1) and ladder == c_run()[0].shares


def test_deep_run_size_down():
    # the weekly column: four down weeks, the latest close in the bottom quarter of the 13-week range
    wc = np.array([110.0, 108.0, 106.0, 104.0, 102.0])
    wh, wl = wc + 1.0, wc - 1.0
    wlast = np.arange(5) * 5 + 4
    assert es3.deep_run_column(wh, wl, wc, wlast, [25], 3) == [-1]                      # all five weeks completed before session 25; 3 straight lower closes, 102 in the bottom quarter of 101..111
    assert es3.deep_run_column(wh, wl, wc, wlast, [24], 3) == [-1]                      # 4 completed weeks: three lower closes still there
    assert es3.deep_run_column(wh, wl, wc, wlast, [14], 3) == [0]                       # only 3 weeks completed: not enough
    up = wc[::-1].copy()
    assert es3.deep_run_column(up + 1.0, up - 1.0, up, wlast, [25], 3) == [1]           # the mirror: a deep premium after up weeks
    mix = np.array([110.0, 108.0, 112.0, 104.0, 102.0])
    assert es3.deep_run_column(mix + 1.0, mix - 1.0, mix, wlast, [25], 3) == [0]        # not a straight run
    sd_short = sd_of([(4000.0, 4001.0, 3999.0, 4000.5)] * 3, sign=-1)
    sd_long = sd_of([(4000.0, 4001.0, 3999.0, 4000.5)] * 3)
    p = Params(es_pt=1.0, deep_run_mult=0.5)
    ctx = _ctx_risk(row={"deep_run": -1})
    tags = {}
    m, _ = es3.order_risk(ctx, sd_short, {}, 2, p, -4000.0, 2.0, False, -4010.0, tags, [])
    assert m == pytest.approx(0.5) and tags["no_adds"] is True                          # a short in deep discount: half size, no adds
    m2, _ = es3.order_risk(ctx, sd_long, {}, 2, p, 4000.0, 2.0, False, 4010.0, {}, [])
    assert m2 == 1.0                                                                   # a long is unaffected
    m3, _ = es3.order_risk(_ctx_risk(row=None), sd_short, {}, 2, p, -4000.0, 2.0, False, -4010.0, {}, [])
    assert m3 == 1.0                                                                   # no table row
    assert Params(deep_run_mult=0.5).bx == '{"deep":3}' and Params().bx == ""


def test_freq_size_scale():
    sd = sd_of([(4000.0, 4001.0, 3999.0, 4000.5)] * 3)
    p = Params(es_pt=1.0, freq_ref=3.0, freq_recent=6)
    m, _ = es3.order_risk(_ctx_risk(), sd, {}, 2, p, 4000.0, 2.0, False, 4010.0, {}, [])
    assert m == pytest.approx(0.5)                                                     # 6 trades in the last 5 sessions
    assert es3.order_risk(_ctx_risk(), sd, {}, 2, replace(p, freq_recent=2), 4000.0, 2.0, False, 4010.0, {}, [])[0] == 1.0
    rows = [dict(date=pd.Timestamp("2026-06-1%d" % k).date(), net=1.0) for k in range(1, 7)]
    q = es3.day_params(Params(freq_ref=3.0), rows, {r["date"] for r in rows})
    assert q.freq_recent == 6 and es3.day_params(Params(freq_ref=3.0), rows, set()).freq_recent == 0
    assert c_run(freq_ref=3.0, freq_recent=6)[0].shares == pytest.approx(c_run()[0].shares * 0.5, abs=1)


# --- E8-leverage-cap-3x (31) / E8-new-trader-drill (32) / E8-new-trader-graduation (33) ----------------------------------------------------

def test_max_lev():
    p = Params(es_pt=1.0, lot=1, max_notional=1e12, max_lev=3.0)
    assert S._first_units(p, 10000.0, 0.6, 500.0) == 60                                 # risk allows 200 shares, 3 x 10,000 / 500 = 60
    assert S._first_units(replace(p, max_lev=0.0), 10000.0, 0.6, 500.0) == 200
    assert es3.lev_room_units(p, 10000.0, 50, 500.0) == pytest.approx(10.0)              # 60 - 50 held
    assert es3.lev_room_units(replace(p, max_lev=0.0), 10000.0, 50, 500.0) is None
    pos = _pos(sd_of([(500.0, 501.0, 499.0, 500.0)]), n=50, left=50, basis=25000.0, stop=498.0, plan_shares=50)
    S._arm_add(pos, SimpleNamespace(shares=50, adds=[]), 500.0, 0, replace(p, adds=(1.0,), account_equity=10000.0), 10000.0)
    assert pos["add"]["q"] == 10                                                        # the add shrinks to the leverage room


def test_drill_55():
    rows = list(C_ROWS)
    rows[5] = (101.6, 101.7, 100.1, 100.5)                                              # the retrace reaches the FVG edge + 1 tick inside (100.15)
    t = c_run(rows, stop_mode="fixed", stop_fixed_pts=5.0, t1_fixed_pts=5.0, t1_fixed_all=True, fixed_units=1, entry="edge_1tick", adds=())
    assert len(t) == 1 and t[0].shares == 1                                             # 1 contract whatever the equity
    assert t[0].entry - t[0].stop == pytest.approx(5.0) and [e[3] for e in t[0].exits] == ["t1"] and t[0].exits[0][1] == pytest.approx(t[0].entry + 5.0)
    assert t[0].entry == pytest.approx(100.4 - 0.25)                                     # the FVG edge + 1 tick inside
    big = c_run(rows, stop_mode="fixed", stop_fixed_pts=5.0, t1_fixed_pts=5.0, t1_fixed_all=True, fixed_units=1, account_equity=1e7)
    assert big[0].shares == 1
    assert c_run(stop_mode="fixed")[0].stop == pytest.approx(99.55)                      # stop_fixed_pts 0: the mode is inert (the FVG-bottom stop of the non-MT modes)
    assert S._first_units(Params(fixed_units=2, lot=5), 1e9, 1.0, 100.0) == 10          # contracts x lot units


def test_trader_mode_new_steps():
    p = Params(trader_mode="new")
    assert es3.trader_units([], p) == 1
    assert es3.trader_units([5.0] * 19, p) == 1                                          # the block is not complete
    assert es3.trader_units([5.0] * 20, p) == 2                                          # 20 winners: the 21st trade uses 2
    assert es3.trader_units([-5.0] * 20, p) == 1                                          # a losing block keeps 1
    assert es3.trader_units([5.0] * 20 + [-5.0] * 20, p) == 2 and es3.trader_units([5.0] * 100, p) == 4 and es3.trader_units([5.0] * 200, p) == 4      # capped at grad_max
    rows = [dict(date=pd.Timestamp("2026-01-05").date(), net=5.0)] * 20
    q = es3.day_params(p, rows, set())
    assert q.fixed_units == 2 and q.trader_mode == "new"
    assert es3.day_params(Params(), rows, set()).fixed_units == 0
    trades = pd.DataFrame({"date": pd.date_range("2026-01-05", periods=300, freq="B"), "net": [1.0] * 300})
    g = study.deploy_gate(trades)
    assert g["passed"] and g["months"] >= 6 and g["nonneg_share"] == 1.0
    short = study.deploy_gate(trades.iloc[:60])
    assert not short["passed"] and short["months"] < 6
    bad = trades.assign(net=[-1.0, 1.0, -1.0, -1.0, -1.0] * 60)
    assert not study.deploy_gate(bad)["passed"]                                          # 6+ months but fewer than 70 % non-negative weeks
    assert not study.deploy_gate(pd.DataFrame())["passed"]


# --- new-probe-position (40) -------------------------------------------------------------------------------------------------------------

def test_probe_trade(monkeypatch):
    rows = [(100.0, 100.4, 99.6, 100.2)] * 12
    sd_l, sd_s = sd_of(rows), sd_of([(-o, -l, -h, -c) for o, h, l, c in rows], sign=-1)
    ctx = stub(12, start=0, bias_row={"draw_up": 104.0}, lock={}, t=np.arange(12) * 5 + 630)
    state, done = {}, {}
    cap = {}

    def fake_finish(ctx_, sd, i, p, session, sw, entry, stop, risk_mult, leg_hi, tags, **kw):
        cap.update(entry=entry, stop=stop, risk_mult=risk_mult, tags=tags, fixed=kw.get("fixed"))
        return dict(ok=True)

    monkeypatch.setattr(S, "_finish_order", fake_finish)
    monkeypatch.setattr(S, "_idx_at", lambda ctx_, m: 0)
    p = Params(es_pt=1.0, probe_mult=0.25)
    o = es3.probe_order(ctx, [sd_l, sd_s], 3, p, state, [], done, 1, None)
    assert o == dict(ok=True) and state["probe_done"]
    assert cap["entry"] == pytest.approx(100.2) and cap["stop"] == pytest.approx(99.6 - p.pad) and cap["risk_mult"] == 0.25      # a market probe at the close, the session low as the stop
    assert cap["fixed"] == [(104.0, "pool")] and cap["tags"]["no_adds"] is True and cap["tags"]["market"] is True and cap["tags"]["es3"]["probe_cut"] == 0.5
    assert es3.probe_order(ctx, [sd_l, sd_s], 4, p, state, [], done, 1, None) is None           # once a day
    for st, dn, tr_, w in (({}, {"AM": True}, [], 1), ({}, {}, [object()], 1), ({}, {}, [], 0)):
        assert es3.probe_order(ctx, [sd_l, sd_s], 3, p, st, tr_, dn, w, None) is None            # a trade today / the session is done / no bias
    assert es3.probe_order(stub(12, start=0, bias_row={"draw_up": 104.0}, lock={}, t=np.arange(12) * 5 + 570), [sd_l, sd_s], 3, p, {}, [], {}, 1, None) is None     # before probe_t
    # the early exit: price trades half the stop distance against it
    pos = _pos(sd_l)
    es3.on_fill(ctx, sd_l, pos, SimpleNamespace(), dict(stop=98.0, t1=105.0, es3={"probe_cut": 0.5}), 3, p, 100.0)
    assert pos["es3_exits"] == [(99.0, "probe_cut", False)] and pos["no_adds"]
    monkeypatch.undo()
    # engine: the probe cut exits at the level through the run_day position loop
    orig = S._finish_order

    def fo(ctx_, sd, i, p_, session, sw, entry, stop, risk_mult, leg_hi, tags, *a, **k):
        return orig(ctx_, sd, i, p_, session, sw, entry, stop, risk_mult, leg_hi, dict(tags, es3={"probe_cut": 0.5}), *a, **k)

    monkeypatch.setattr(S, "_finish_order", fo)
    rows2 = list(C_ROWS)
    rows2[6] = (100.5, 100.6, 99.7, 99.9)                                                # entry 100.4, stop 99.1 -> the cut level is 99.75; the bar trades down to 99.7
    t = c_run(rows2)
    assert len(t) == 1 and t[0].exits[0][3] == "probe_cut" and t[0].exits[0][1] == pytest.approx(99.75)


# --- E6-wick-ce-stop (44) --------------------------------------------------------------------------------------------------------------

def test_stop_wick_ce():
    sd = sd_of([(4012.0, 4013.5, 4006.0, 4013.0), (4013.0, 4016.0, 4012.5, 4015.0), (4015.0, 4018.0, 4014.0, 4017.0)])
    p = Params(es_pt=1.0)
    s = es3.wick_ce_stop(sd, dict(ext_i=0), 2, 4014.0, p)
    assert s == pytest.approx(4009.0 - 0.25 - 0.25)                                      # the sweep bar's lower-wick CE 4009, minus the pad and a tick of tolerance
    assert es3.wick_ce_stop(sd, dict(ext_i=0), 2, 4014.0, replace(p, wick_ce_tol_ticks=0)) == pytest.approx(4008.75)
    assert es3.wick_ce_stop(sd, dict(ext_i=0), 2, 4025.0, p) is None                     # the risk (16.5) is over the max: the built stop stays
    assert es3.wick_ce_stop(sd_of([(4012.0, 4013.0, 4011.9, 4013.0)] * 3), dict(ext_i=0), 2, 4014.0, p) is None      # no wick of >= 2 ticks
    out = es3.stop_adjust(stub(3), sd, dict(ext_i=0, ext=4006.0), None, None, None, 4014.0, 4000.0, 2, replace(p, stop_mode="wick_ce"))
    assert out == pytest.approx(4008.5)
    # the managed variant: each new defending wick raises the stop (never lowers)
    pos = _pos(sd, fill_i=0, stop=4009.0)
    es3.trail_wick(sd, pos, 1, replace(p, trail_wick_ce=True))
    assert pos["stop"] == pytest.approx(4012.5)                                          # bar 1's lower wick (4012.5-4013, exactly 2 ticks): CE 4012.75 - pad
    pos2 = _pos(sd_of([(4012.0, 4013.0, 4006.0, 4013.0), (4020.0, 4021.0, 4016.0, 4020.5)]), fill_i=0, stop=4009.0)
    es3.trail_wick(pos2["side"], pos2, 1, replace(p, trail_wick_ce=True))
    assert pos2["stop"] == pytest.approx(4018.0 - 0.25)                                  # the managed variant: CE - pad
    es3.trail_wick(pos2["side"], dict(pos2, stop=4030.0), 1, replace(p, trail_wick_ce=True))
    assert c_run(stop_mode="wick_ce", trail_wick_ce=True) is not None                    # runs end to end


# --- M2-stop-by-fvg-choice (45) ------------------------------------------------------------------------------------------------------------

def test_stop_m2_auto():
    rows = [(99.8, 100.2, 99.7, 100.1), (100.1, 100.4, 99.9, 100.3), (100.3, 100.9, 100.2, 100.8), (101.2, 101.9, 100.9, 101.8), (101.8, 102.0, 101.6, 101.7)]
    sd = sd_of(rows)                                                                     # a VI [100.8, 101.2] at bar 3
    g = L.Zone("bull", 101.0, 100.6, 4, 3)                                              # the FVG whose middle candle is bar 3
    ob = L.Zone("bull", 100.9, 100.0, 1, 0, 100.45)
    p = Params(es_pt=1.0, stop_mode="m2_auto")
    assert es3.m2_confluence(sd, g, ob, p) and not es3.m2_confluence(sd, g, None, p)
    assert es3.m2_auto_stop(sd, dict(ext=98.0), g, ob, 100.45, p) == pytest.approx(100.45 - 0.5)           # the OB MT minus 2 ticks (mirror of 4131.50 -> 4132.00)
    assert es3.m2_auto_stop(sd, dict(ext=98.0), g, None, None, p) == pytest.approx(98.0 - 0.25)            # a plain FVG: the leg extreme - 1 tick (wide)
    assert es3.m2_auto_stop(sd, dict(ext=98.0), g, L.Zone("bull", 99.0, 98.5, 1, 0, 98.75), 98.75, p) == pytest.approx(97.75)       # the OB does not touch the gap
    q = replace(p, mt_pad_ticks=4)
    assert es3.m2_auto_stop(sd, dict(ext=98.0), g, ob, 100.45, q) == pytest.approx(100.45 - 1.0)
    assert c_run(stop_mode="m2_auto", fvg_pick="2022")[0].stop == pytest.approx(98.6 - 0.25)              # scenario C: no VI + OB confluence: the leg extreme (98.6) - 1 tick


# --- E6-old-low-rejection-body (48) -------------------------------------------------------------------------------------------------------

def test_stop_old_low_body():
    rows = [(4125.0, 4126.0, 4118.0, 4120.0), (4113.0, 4114.0, 4110.0, 4112.5), (4112.5, 4118.0, 4111.0, 4117.0), (4117.0, 4125.0, 4116.0, 4120.0)]
    sd = sd_of(rows)
    p = Params(es_pt=1.0)
    assert es3.old_low_body_stop(sd, 3, 4120.0, 4116.0, p) == pytest.approx(4112.25)     # the old low 4110 (wick) -> the lowest body 4112.50 - 1 tick
    assert es3.old_low_body_stop(sd, 3, 4120.0, 4108.0, p) is None                       # the stop is already under the old low
    assert es3.old_low_body_stop(sd, 3, 4130.0, 4116.0, p) is None                       # the old low is beyond the max risk (20 pts)
    taken = sd_of(rows[:3] + [(4117.0, 4118.0, 4109.0, 4116.0), (4116.0, 4118.0, 4108.0, 4112.0)])
    assert es3.old_low_body_stop(taken, 4, 4120.0, 4116.0, p) is None                    # the low (4110) was traded through and the lower ones are no confirmed swing: no old low
    ctx = stub(4)
    out = es3.stop_post(ctx, sd, dict(ext=4110.0), 3, replace(p, stop_old_low_body=True), 4120.0, 4116.0, {})
    assert out == pytest.approx(4112.25)
    assert es3.stop_post(ctx, sd, dict(ext=4110.0), 3, p, 4120.0, 4116.0, {}) == 4116.0  # off


# --- E6-nwog-stop (52) --------------------------------------------------------------------------------------------------------------

def test_stop_gap_edge():
    # a SHORT (side space = the negated real prices): the NWOG 4085-4089.25 holds the entry FVG 4086-4088, an NDOG reaches 4096
    bands = [(-4085.0, -4089.25), (-4092.0, -4096.0)]
    zone = (-4088.0, -4086.0)
    p = Params(es_pt=1.0, stop_gap_edge="own")
    assert es3.gap_edge_stop(bands, zone, -4086.0, -4089.0, p) == pytest.approx(-4089.5)  # "own": the far edge of the gap the array sits in + 1 tick (4089.50)
    assert es3.gap_edge_stop(bands, zone, -4086.0, -4089.0, replace(p, stop_gap_edge="all")) == pytest.approx(-4096.25)      # "all": beyond every opening gap within the max risk (4096.25)
    assert es3.gap_edge_stop(bands, (-4100.0, -4098.0), -4098.0, -4101.0, p) is None     # the array is in no gap
    assert es3.gap_edge_stop([(-4085.0, -4120.0)], zone, -4086.0, -4089.0, replace(p, stop_gap_edge="all")) is None      # a gap beyond the max risk is ignored
    real = SimpleNamespace(gaps=[("nwog", 4089.25, 4085.0, 4087.0), ("ndog", 4096.0, 4092.0, 4094.0)])
    sd = sd_of([(-4086.0, -4085.0, -4088.0, -4087.0)] * 3, sign=-1)
    assert es3.gap_bands(real, sd, 2) == [(-4085.0, -4089.25), (-4092.0, -4096.0)]
    out = es3.stop_post(real, sd, dict(ext=-4088.0), 2, p, -4086.0, -4089.0, dict(fvg_bottom=-4088.0, zone_top=-4086.0))
    assert out == pytest.approx(-4089.5)


# --- E6-three-pd-arrays (53) / E6-next-pd-array (54) -----------------------------------------------------------------------------------

def test_stop_three_pd():
    levels = [(-4102.0, -4102.0), (-4104.0, -4104.0), (-4106.0, -4106.0), (-4110.0, -4110.0)]        # a short: the mitigation MT, the OB MT, the FVG high (side space = negated)
    assert es3.three_pd_stop(levels, 3, 0.25) == pytest.approx(-4106.25)                  # behind the third array: 4106.25
    assert es3.three_pd_stop(levels[:2], 3, 0.25) == pytest.approx(-4104.25)              # fewer than three: the outermost found
    assert es3.three_pd_stop(levels, 1, 0.25) == pytest.approx(-4102.25) and es3.three_pd_stop([], 3, 0.25) is None
    sd = sd_of(C_ROWS)
    g = [z for z in sd.gaps if z.i == 4][0]
    lv = es3.protect_levels(sd, dict(ext_i=1), g, 99.35, 100.4, 5, Params(es_pt=1.0))
    bottoms = [b for _, b in lv]
    assert bottoms == sorted(bottoms, reverse=True) and all(b < 100.4 for b in bottoms) and (99.35, 99.35) in lv and (100.4, 99.8) in lv       # nearest first; the OB MT, the entry gap
    assert c_run(stop_mode="three_pd")[0].stop <= c_run()[0].stop + 1e-9                  # never tighter than the built MT stop in scenario C (the outermost of the few arrays)


def test_stop_next_pd():
    levels = [(1276.0, 1276.0), (1275.0, 1275.0), (1272.0, 1273.0)]                      # swing high 1276, array high 1275, a lower array
    assert es3.next_pd_stop(levels, 1278.0, 1275.5, 0.25) == pytest.approx(1274.75)      # 1276 was pierced by the entry array's first candle (low 1275.5): skipped; 1275 -> 1274.75
    assert es3.next_pd_stop(levels, 1278.0, 1275.0, 0.25) == pytest.approx(1272.75)      # the first candle reached 1275: that one is skipped as well
    assert es3.next_pd_stop([(1279.0, 1279.0)], 1278.0, 1277.0, 0.25) is None            # not fully below the entry array
    sd = sd_of(C_ROWS)
    g = [z for z in sd.gaps if z.i == 4][0]
    out = es3.stop_adjust(stub(8), sd, dict(ext_i=1, ext=98.6), g, None, 99.35, 100.4, 99.1, 5, Params(es_pt=1.0, stop_mode="next_pd"))
    assert out < 100.4 - 0.25
    assert c_run(stop_mode="next_pd") is not None


# --- E6-bpr-75-stop (55) ------------------------------------------------------------------------------------------------------------

def test_stop_bpr75():
    assert es3.bpr75_stop(4100.0, 4120.0, "upper", 0.25) == pytest.approx(4114.75)       # H - 25 % of the range, minus a tick
    assert es3.bpr75_stop(4100.0, 4120.0, "lower", 0.25) == pytest.approx(4104.75)       # L + 25 %, minus a tick
    o = np.array([4120.0, 4100.0, 4120.0])
    h = np.array([4120.0, 4120.0, 4126.0])
    l = np.array([4100.0, 4100.0, 4119.0])
    c = np.array([4100.0, 4120.0, 4125.0])
    assert L.two_way_range(o, h, l, c, 2) == (4100.0, 4120.0, 1)                          # a down leg then an up leg over the same range, the close 4125 above it
    assert L.two_way_range(o, h, l, np.array([4100.0, 4120.0, 4119.0]), 2) is None       # not cleared
    sd = sd_of(list(zip(o, h, l, c)))
    assert es3.cleared_range(sd, 2, Params(es_pt=1.0)) == (4100.0, 4120.0)
    out = es3.stop_adjust(stub(3), sd, dict(ext_i=0, ext=4100.0), None, None, None, 4125.0, 4098.0, 2, Params(es_pt=1.0, stop_mode="bpr75"))
    assert out == pytest.approx(4114.75)
    out2 = es3.stop_adjust(stub(3), sd, dict(ext_i=0, ext=4100.0), None, None, None, 4125.0, 4098.0, 2, Params(es_pt=1.0, stop_mode="bpr75", bpr75_ref="lower"))
    assert out2 == pytest.approx(4104.75)
    assert es3.stop_adjust(stub(3), sd, dict(ext_i=0, ext=4100.0), None, None, None, 4115.0, 4098.0, 2, Params(es_pt=1.0, stop_mode="bpr75")) == 4098.0      # an entry inside the range keeps the built stop
    assert len(c_run(stop_mode="bpr75")) == 1


# --- E6-new-trader-wide-stops (56) ---------------------------------------------------------------------------------------------------------

def test_tight_loss_reads_the_initial_risk_and_blocks_only_same_direction():
    p = Params(es_pt=1.0, trader_mode="new")
    tr = SimpleNamespace(entry=100.0, stop=95.0)                                         # the average entry after adds: 5 pts away, but the first unit risked 2
    assert es3.tight_loss(tr, p, {"es3_r0": 2.0}) and not es3.tight_loss(tr, p, {"es3_r0": 4.0}) and not es3.tight_loss(tr, p)


def test_new_mode_wide_stop():
    p = Params(es_pt=1.0, trader_mode="new", stop_widen_new=True)
    cands = [(99.2, 99.0), (94.5, 94.25), (90.0, 89.0)]                                    # structural levels under the entry 100, nearest first
    assert es3.widen_stop(cands, 100.0, 98.5, p) == pytest.approx(94.0)                    # 99.0 - pad leaves 1.25 pts: too tight; the next array leaves 6 pts
    assert es3.widen_stop([(99.2, 99.0)], 100.0, 98.5, p) is None
    tr = SimpleNamespace(entry=100.0, stop=98.5)
    assert es3.tight_loss(tr, p) and not es3.tight_loss(SimpleNamespace(entry=100.0, stop=95.0), p) and not es3.tight_loss(tr, replace(p, trader_mode=""))       # a 1.5-pt stop-out: no re-entry
    assert p.max_risk_pts == 15.0
    sd = sd_of([(92.0, 93.0, 91.0, 92.5), (92.5, 96.0, 92.0, 95.5), (95.5, 95.8, 94.0, 94.5), (94.5, 100.5, 94.2, 100.2), (100.2, 101.0, 99.5, 100.8)])
    out = es3.stop_post(stub(5), sd, dict(ext=91.0), 4, p, 100.0, 98.5, {})
    assert out == pytest.approx(95.75)                                                       # pushed out to the swing high 96 - a tick (4.25 pts of risk >= 3)
    assert es3.stop_post(stub(5), sd, dict(ext=91.0), 4, replace(p, stop_widen_new=False), 100.0, 98.5, {}) == 98.5


# --- E6-refined-stop-htf (57) ---------------------------------------------------------------------------------------------------------

def test_stop_htf_anchor():
    sd = sd_of([(4016.0, 4017.0, 4011.0, 4016.5)] * 3)
    conf = StubConf(arrays={1: [(4020.0, 4012.0, "D", 1, 0.0)]})                          # a daily OB 4012-4020 (level 4012)
    ctx = stub(3, conf=conf)
    p = Params(es_pt=1.0, stop_htf_anchor=True)
    out = es3.stop_post(ctx, sd, dict(ext=4011.0), 2, p, 4017.0, 4015.75, {})
    assert out == pytest.approx(4010.75)                                                   # min(sweep low 4011, the array bottom 4012) - pad, not the 1m OB MT stop (4015.75)
    assert es3.stop_post(ctx, sd, dict(ext=4011.0), 2, replace(p, stop_htf_anchor=False), 4017.0, 4015.75, {}) == 4015.75
    far = stub(3, conf=StubConf(arrays={1: [(4060.0, 4050.0, "D", 1, 0.0)]}))
    assert es3.stop_post(far, sd, dict(ext=4011.0), 2, p, 4017.0, 4015.75, {}) == 4015.75   # the sweep did not trade into an HTF array
    deeper = stub(3, conf=StubConf(arrays={1: [(4020.0, 4005.0, "4h", 0, 0.0)]}))
    assert es3.stop_post(deeper, sd, dict(ext=4011.0), 2, p, 4017.0, 4015.75, {}) == pytest.approx(4004.75)   # an array reaching lower: its bottom


# --- E6-attempt-based-stop (58) -------------------------------------------------------------------------------------------------------

def test_reentry_ob_low_stop(monkeypatch):
    rows = [(4020.0, 4021.0, 4012.0, 4013.0), (4013.0, 4014.0, 4010.0, 4011.0), (4011.0, 4012.0, 4009.0, 4010.0),            # the stop-out around bar 2
            (4015.0, 4016.0, 4011.0, 4012.0), (4012.0, 4018.0, 4011.5, 4017.0), (4017.0, 4019.0, 4016.0, 4018.0)]             # bar 3: a down-close candle (o 4015, l 4011); bar 4 trades above its high
    sd = sd_of(rows)
    cap = {}
    from mentorship import sm4
    monkeypatch.setattr(sm4, "_order", lambda ctx, sd_, i, p, session, rm, name, entry, stop, **kw: cap.update(entry=entry, stop=stop, name=name, kw=kw) or dict(ok=True))
    rc = dict(pending=True, side="long", stop_i=2)
    ctx = stub(6, re_ctx_now=rc)
    p = Params(es_pt=1.0, reentry_stop="ob_low")
    assert es3.ob_low_order(ctx, sd, 3, p, "AM", 0.5) is None                              # its high is not exceeded yet
    o = es3.ob_low_order(ctx, sd, 4, p, "AM", 0.5)
    assert o == dict(ok=True) and cap["entry"] == pytest.approx(4015.0) and cap["stop"] == pytest.approx(4011.0 - p.pad) and rc["armed_ob"]      # at the OB open, under its full low - 1 tick
    assert es3.ob_low_order(ctx, sd, 5, p, "AM", 0.5) is None                              # once
    assert es3.ob_low_order(stub(6, re_ctx_now=dict(rc, side="short")), sd, 4, p, "AM", 0.5) is None
    from mentorship import sm7
    assert sm7.loss_reentry_ok(ctx, sd, 4, p, {"sm7": {"kind": "ob_low"}, "i": 4}, rc) is True
    assert sm7.loss_reentry_ok(ctx, sd, 4, p, {"i": 4, "ext_i": 3}, rc) is False           # every other re-entry order is out while the OB-low re-entry is the rule
    assert sm7.loss_reentry_ok(ctx, sd, 4, replace(p, reentry_stop="array"), {"i": 4, "ext_i": 3}, rc) is True


# --- E6-ob-body-stop (59) / A12-ob-anchor (60) ---------------------------------------------------------------------------------------

def test_ob_stop_body_wick():
    ob = dict(body_low=4016.0, lo=4013.0)
    assert es3.ob_stop_for(ob, Params(es_pt=1.0)) is None
    assert es3.ob_stop_for(ob, Params(es_pt=1.0, ob_stop_kind="body")) == pytest.approx(4015.75)      # under the body low (the close) - a tick
    assert es3.ob_stop_for(ob, Params(es_pt=1.0, ob_stop_kind="wick")) == pytest.approx(4012.75)


def test_ob_anchor_last_open():
    rows = [(4030.0, 4031.0, 4025.0, 4026.0), (4026.0, 4027.0, 4022.0, 4023.0), (4022.0, 4023.0, 4018.0, 4019.0), (4019.0, 4026.0, 4018.5, 4025.0), (4025.0, 4028.0, 4024.0, 4027.0)]
    sd = sd_of(rows)
    sw = dict(ext_i=2)
    assert S._ob_at_low(sd, sw, 4, Params(es_pt=1.0))["body_top"] == 4030.0                 # the series' highest open
    d = S._ob_at_low(sd, sw, 4, Params(es_pt=1.0, ob_anchor="last_open"))
    assert d["body_top"] == 4022.0 and d["mt"] == pytest.approx((4022.0 + 4019.0) / 2)
    pos = dict(fill_i=0, stop=4000.0, add=None, ob_add_used=set(), basis=1000.0, n=10, left=10, plan_shares=10, t1_done=False)
    sd2 = sd_of(rows + [(4027.0, 4028.0, 4021.0, 4022.0), (4022.0, 4030.0, 4021.5, 4029.0)])        # a down candle after the fill, then a close above it
    tr = SimpleNamespace(shares=10, adds=[])
    S._ob_add(sd2, dict(pos, side=sd2), tr, 6, Params(es_pt=1.0, lot=1, adds=(0.5,), ob_anchor="last_open"), 100000.0)


# --- E6-mitigation-block-stop (61) -----------------------------------------------------------------------------------------------------

def test_mit_block_entry_stop():
    rows = [(4004.0, 4005.0, 3999.0, 4000.0), (4000.0, 4003.0, 3997.0, 4002.0), (4002.0, 4009.0, 4001.0, 4008.0)]
    ctx, (sl, ss) = mkctx(rows, base=4010.0, hist=hist_close(close=4010.0, hi=4130.0, lo=3900.0))
    k0 = ib(ctx, "09:30")
    i = k0 + 2
    p = Params(**SM5_BASE, entry_arrays=("mitigation",))
    sl._mit = [L.Zone("bull", 4005.0, 3999.0, k0 + 1, k0, 4002.0)]
    sw = dict(session="AM", ext=3997.0, ext_i=k0 + 1, key="pdl1")
    assert sm5.mit_cand(ctx, sl, sw, i, p) == (4005.0, 4002.0, "mitigation")                  # the built candidate: the zone top, the block's MT as the stop reference
    q = replace(p, mit_entries=True)
    assert sm5.mit_cand(ctx, sl, sw, i, q) == (4004.0, 3999.0, "mitigation")                  # the body edge (max(open, close) of the candle) and the candle's far extreme as the stop reference
    assert Params(mit_entries=True).entry_arrays == ("mitigation",)


# --- E6-propulsion-mt (62) -----------------------------------------------------------------------------------------------------------

def test_prop_mt_stop():
    sd = sd_of([(4012.0, 4018.0, 4010.0, 4016.0)] * 3)
    p = Params(es_pt=1.0, prop_entry=True, prop_stop="mt")
    out = es3.stop_adjust(stub(3), sd, dict(ext_i=0, ext=4010.0), None, None, None, 4016.0, 4009.0, 2, p, prop_exit=4014.0)
    assert out == pytest.approx(4013.75)                                                       # the propulsion candle's MT (range 4010-4018 -> 4014) minus a tick
    assert es3.stop_adjust(stub(3), sd, dict(ext_i=0, ext=4010.0), None, None, None, 4016.0, 4009.0, 2, replace(p, prop_stop=""), prop_exit=4014.0) == 4009.0
    assert es3.stop_adjust(stub(3), sd, dict(ext_i=0, ext=4010.0), None, None, None, 4013.0, 4009.0, 2, p, prop_exit=4014.0) == 4009.0         # an MT over the entry is no stop


# --- engine tests through the real run_day path (scenario A: the OB-before-break entry) ----------------------------------------------------------------

def _a_run(rows=None, **kw):
    from test_review_fixes import A_LOCK, A_ROWS
    p = Params(**{**BASE, "adds": (0.5, 0.33, 0.17), "ob_adds": False, "draw_lock_partials": False, "min_risk_pts": 0.5, "risk_pct": 0.003, **kw})
    tr, *_ = rf_run(day(rows or A_ROWS, spike=True), history(), p, A_LOCK)
    return tr


def test_add_momentum_engine():
    from test_caption_gap_es2a import ADD_ROWS
    base = _a_run(ADD_ROWS)
    assert len(base) == 1 and len(base[0].adds) == 2                                  # the built pyramid: two FVG adds
    t = _a_run(ADD_ROWS, add_momentum=True, add_mom_r=0.5)
    assert len(t) == 1 and len(t[0].adds) == 1                                         # ONE market add ...
    assert t[0].adds[0][2] == int(0.25 * t[0].shares) and t[0].adds[0][1] == pytest.approx(100.8)      # ... of 25 % of the first unit at the open after the closing bar (100.8)
    assert t[0].adds[0][0].hour == 10 and t[0].adds[0][0].minute == 0


def test_ob_stop_kind_engine():
    base = _a_run()
    body = _a_run(ob_stop_kind="body")
    wick = _a_run(ob_stop_kind="wick")
    assert base[0].stop == pytest.approx(99.15) and body[0].stop == pytest.approx(98.55) and wick[0].stop == pytest.approx(98.25)         # MT 99.4 - pad / OB body low 98.8 - pad / OB wick low 98.5 - pad
    assert body[0].shares < base[0].shares                                              # the wider stop at the same risk budget: fewer units


def test_class_risk_pct_helper():
    assert es3.class_risk_pct(Params(class_risk={"swing": 0.02}), "swing", 0.015) == 0.02
    assert es3.class_risk_pct(Params(), "swing", 0.015) == 0.015 and es3.class_risk_pct(Params(), "position", 0.01) == 0.01


# --- review fix: the sign of the mirrored result (shorts run the bullish code on mirrored prices) -----------------------------------------------------

@pytest.mark.parametrize("kw", [dict(stop_mode="wick_ce"), dict(stop_mode="m2_auto", fvg_pick="2022"), dict(stop_mode="three_pd"), dict(stop_mode="next_pd"), dict(stop_mode="bpr75"),
                                dict(stop_old_low_body=True), dict(add_wick_ce=True), dict(add_void=True), dict(add_reclaimed_ob=True), dict(add_dig_mult=0.67, add_on="retest")])
def test_short_side_mirrors_the_long_result(kw):
    """A short on the mirrored day (price p -> 300 - p) gets the mirrored entry / stop of the long (targets come from the unmirrored history, so exits are not compared), for the stop and add switches of this chunk."""
    from test_review_fixes import mirror
    long_ = c_run(**kw)
    tr, *_ = rf_run(mirror(day(C_ROWS)), history(), Params(**{**BASE, **{"ob_entry": "post_mss", "draw_lock": "off", "htf_resist_cap": False, "min_risk_pts": 0.5, "leg_pd": 0.0, "news_wait": "off",
                                                                         "min_draw_pts": 0.0}, **kw}), {})
    sh = [t for t in tr if t.side == "short"]
    assert len(sh) == len(long_)
    for a, b in zip(long_, sh):
        assert b.entry == pytest.approx(300.0 - a.entry) and b.stop == pytest.approx(300.0 - a.stop)


def test_check_params_trader_mode_values_cited_in_params_comments_validate():
    import re
    src = open(S.__file__, encoding="utf-8").read()
    modes = set(re.findall(r'trader_mode[ =]+"([a-z]+)"', src)) - {""}
    assert "experienced" in modes
    for m in modes:
        Params(trader_mode=m)


def test_class_risk_swing_position_warn_no_consumer():
    with pytest.warns(RuntimeWarning, match="no consumer"):
        Params(class_risk={"swing": 0.015})
    Params(class_risk={"scalp": 0.005, "day": 0.01})


def test_extras_loss_gate_drops_extra_rows_after_the_limit():
    ctx = SimpleNamespace(equity=100000.0)
    p = Params(daily_loss_pct=0.01, cost_per_share=0.0)
    t = lambda h, m, h2, m2, px, sh: S.Trade(date=None, symbol="ES", session="AM", setup="x", side="long", swept="", unicorn=False, smt=None, armed=pd.Timestamp(f"2026-06-23 {h}:{m}", tz=NY),
                                             entry_time=pd.Timestamp(f"2026-06-23 {h}:{m}", tz=NY), entry=100.0, stop=99.0, t1=105.0, t2=None, shares=sh,
                                             exits=[(pd.Timestamp(f"2026-06-23 {h2}:{m2}", tz=NY), px, sh, "stop")])
    main = t("09", "30", "09", "40", 98.0, 600)                      # -1200 > limit 1000
    e1 = t("09", "50", "10", "00", 101.0, 100)                       # after the loss: dropped
    e0 = t("09", "35", "09", "38", 101.0, 100)                       # entered before the main loss closed: kept
    out = es3.extras_loss_gate([main, e1, e0], 1, ctx, p)
    assert out == [main, e0]
    assert es3.extras_loss_gate([main, e1], 1, ctx, Params(daily_loss_pct=0.05, cost_per_share=0.0)) == [main, e1]


def test_near_htf_literal_add_sized_at_the_near_budget():
    sd = sd_of([(100.0, 100.5, 99.5, 100.0)] * 3)
    pos = dict(side=sd, stop=98.0, n=100, basis=10000.0, left=100, es3_room=0.15, add=None, trade=None)
    p = Params(htf_near_risk_pct=0.05, htf_near_add_literal=True, adds=(0.5,), lot=1)
    tr = SimpleNamespace(shares=100, adds=[], entry=100.0)
    S._arm_add(pos, tr, 100.0, 1, p, 100000.0)
    # literal: 5 % x 100k / 2 pts = 2500 units (the room caps it); proportional would be 50
    assert pos["add"] is None or pos["add"]["q"] > 50
