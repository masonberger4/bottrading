"""Caption-gap pass, package setups_models #1/7, part A: the 23 specs of digests/rulebook_gaps/bias_htf_intermarket.md (items 2, 3, 19, 23, 42, 48, 49, 50, 51,
54, 67, 69, 89, 92, 98, 113, 123, 124, 126, 192, 199, 206, 207). Unit tests of the new detectors / picks (levels.py, backtest.combine) and of the engine glue
(sm2.py), small run_day scenarios, Params plumbing. Tests that need local market data (ES) skip cleanly when it is absent; no platform-specific paths.
The no-look-ahead runs live in test_caption_gap_sm1b.py."""
import warnings
from dataclasses import replace
from datetime import date
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from mentorship import backtest as B, levels as L, report_decisions as RD, sm2, strategy as S, study
from mentorship.strategy import Params

from test_levels_detectors import BASE, D0, NY, day, ctx_for, history, prior_days, rth_day
from test_review_fixes import B_POST, B_ROWS, run as rf_run

A = np.array

NEW_SWITCHES = (
    "open_tol_pts", "wk_open_side", "po3_seq", "po3_seq_below_pts", "ifvg_narrative", "gap_premium_arm", "compressed_hh", "compressed_k", "compressed_n",
    "laggard_consol_only", "markets", "pool_runs_max", "far_edge_trap", "smt_win_a", "smt_win_b", "smt_open_points", "lod_zone_first", "smt_with_bias",
    "mature_flag_block", "mature_pd", "mit_needs_bias", "touch_tag", "judas_max_adr", "lc_tag", "lc_reentry", "smt_pm_points",
)


def hist_close(d=D0, n=8, hi=108.0, lo=90.0, close=100.0):
    return [rth_day(x, hi, lo, close=close) for x in prior_days(d, n)]


def mkctx(rows, p=None, base=100.0, start="09:30", hist=None, bias=0, conf=None, d=D0, w=0.2):
    """A real DayCtx over a hand-made day (flat at `base` before `start`) with both live Sides in ctx.sides_map."""
    p = p or Params(**BASE)
    df = day(rows, d=d, start=start, base=base, w=w)
    ctx = ctx_for(df, hist if hist is not None else history(d), p)
    ctx.cur_bias, ctx.conf = bias, conf
    ctx.equity, ctx.symbol, ctx.lock = p.account_equity, "ES", {}
    sides = (S.Side(1, ctx.o, ctx.h, ctx.l, ctx.c, p.pivot_n), S.Side(-1, ctx.o, ctx.h, ctx.l, ctx.c, p.pivot_n))
    ctx.sides_map = {1: sides[0], -1: sides[1]}
    return ctx, sides


def ib(ctx, hhmm):
    """The bar of today that STARTS at hh:mm."""
    return S._idx_at(ctx, int(hhmm[:2]) * 60 + int(hhmm[3:]))


def sd_of(rows, sign=1, n=1):
    a = A(rows, float)
    return S.Side(sign, a[:, 0], a[:, 1], a[:, 2], a[:, 3], n)


def stub(n, **kw):
    idx = pd.date_range("2026-06-23 09:30", periods=n, freq="5min", tz=NY)
    d = dict(idx=idx, tf=5, start=0, cur_bias=0, t=(idx.hour * 60 + idx.minute).values, day=D0, hist=history(D0, n=8))
    d.update(kw)
    return SimpleNamespace(**d)


class StubConf:
    """A minimal Confluence stand-in for run_day scenarios and unit tests: `arrays` {side: [(top, bottom, tf, src, known_ns)]} answers valid(); `at_tfs`
    {side: [tf]} answers at() (the timeframes holding any price); everything else is empty."""

    def __init__(self, arrays=None, at_tfs=None, trend=0):
        self.arrays, self.at_tfs, self._trend = arrays or {}, at_tfs or {}, trend

    def at(self, t, price, side, known_by=None): return list(self.at_tfs.get(side, []))
    def trend(self, t, tf): return self._trend
    def targets(self, *a, **k): return []
    def resistance(self, *a, **k): return None
    def support(self, *a, **k): return None
    def opposing(self, *a, **k): return []
    def opposing_ext(self, *a, **k): return []
    def valid(self, t, side, tfs, src=(0, 1, 3), known_by=None): return [z for z in self.arrays.get(side, []) if z[2] in tfs]




# --- new switches: defaults / validation ---------------------------------------------------------------------------------------

def test_new_switch_defaults_and_validation():
    p = Params()
    assert (p.open_tol_pts, p.po3_seq, p.po3_seq_below_pts, p.ifvg_narrative, p.gap_premium_arm, p.compressed_hh) == (0.0, "off", 3.0, "off", False, False)
    assert (p.compressed_k, p.compressed_n, p.pool_runs_max, p.far_edge_trap, p.smt_win_a, p.smt_win_b) == (0.1, 3, 0, False, 300, 570)
    assert (p.mature_flag_block, p.mature_pd, p.mit_needs_bias, p.judas_max_adr, p.smt_with_bias, p.markets) == (False, 0.62, False, 0.0, False, ("ES",))
    assert (p.lod_zone_first, p.smt_open_points, p.smt_pm_points, p.lc_reentry, p.lc_tag, p.touch_tag, p.wk_open_side) == (False,) * 7
    for kw in (dict(po3_seq="x"), dict(ifvg_narrative="x"), dict(open_tol_pts=-1), dict(compressed_n=1), dict(compressed_k=0), dict(smt_win_a=600, smt_win_b=500),
               dict(mature_pd=1.0), dict(judas_max_adr=-0.1), dict(markets=())):
        with pytest.raises(ValueError):
            Params(**kw)
    for pick in ("first", "leader", "laggard", "trend", "laggard_objective", "middle", "clean_swing", "depth", "swept", "fixed_es"):
        assert Params(smt_pick=pick).smt_pick == pick
    with pytest.raises(ValueError):
        Params(smt_pick="nope")
    assert set(NEW_SWITCHES) <= set(Params.__dataclass_fields__)


# --- BH-B12-midnight-open-tolerance (2) ------------------------------------------------------------------------------------------

AFTER = [(102.3, 102.4, 100.3, 101.0), (101.0, 109.0, 100.9, 108.8)]


def scen_b(shift=0.0, **kw):
    """Scenario B + a retrace into the FVG limit (101.3) and a run to the draw; the midnight open is 100.0 (the rows can be shifted down)."""
    rows = [(o + shift, h + shift, l + shift, c + shift) for o, h, l, c in B_ROWS + AFTER]
    tr, *_ = rf_run(day(rows), history(hi=112.0, lo=88.0), Params(**{**B_POST, "adds": (0.5,), **kw}), {})
    return tr


def test_open_tolerance_grade():
    """Entry 101.3 is 1.3 points on the wrong side of the 100.0 open (a long): strict mode and a too-small tolerance reject it, 2 points allow it ('allowed') because
    the open was traded through (low 98.0) and an MSS followed; an entry under the open is 'best'."""
    assert scen_b(use_bias=True) == []
    assert scen_b(use_bias=True, open_tol_pts=1.0) == []
    t = scen_b(use_bias=True, open_tol_pts=2.0)
    assert len(t) == 1 and t[0].open_grade == "allowed" and t[0].entry == 101.3
    t2 = scen_b(shift=-2.0, use_bias=True, open_tol_pts=2.0)
    assert len(t2) == 1 and t2[0].open_grade == "best" and t2[0].entry == pytest.approx(99.3)
    assert scen_b(shift=-2.0, use_bias=True)[0].open_grade == ""                       # the grade is only tagged while open_tol_pts is on
    # no Judas (the open was never traded through before the MSS): the tolerance does not apply
    ctx, (sl, ss) = mkctx(B_ROWS, base=100.0)
    sw = dict(broke=ib(ctx, "10:05"), ext=99.5, ext_i=ib(ctx, "09:45"))
    p = Params(**BASE, open_tol_pts=2.0)
    i = ib(ctx, "10:10")
    assert not sm2.open_tol_ok(ctx, sl, dict(sw, broke=None), i, p, "AM", 101.3, 100.0)       # no MSS yet
    assert sm2.open_tol_ok(ctx, sl, sw, i, p, "AM", 101.3, 100.0)
    assert not sm2.open_tol_ok(ctx, sl, sw, i, p, "AM", 102.5, 100.0)                           # beyond the tolerance


def test_wk_open_side_tag_uses_the_sunday_open():
    ctx = stub(10, sunday_open=4005.0)
    assert S._open_known(ctx, "sunday", 3) == 4005.0
    assert S._open_known(stub(10), "sunday", 3) is None


# --- BH-B12-po3-sequence (3) -----------------------------------------------------------------------------------------------------

def test_po3_sequence():
    """Scenario B: the open (100.0) was traded under, a later bar closed back over it, the MSS followed, the entry (101.3) is within 3 points of the open: po3_seq True;
    with the 'just below' allowance cut to 0.5 points it is False and the filter rejects the order."""
    t = scen_b(po3_seq="tag")
    assert len(t) == 1 and t[0].po3_seq is True and "po3_seq" in t[0].lv_tags
    t = scen_b(po3_seq="tag", po3_seq_below_pts=0.5)
    assert len(t) == 1 and t[0].po3_seq is False
    assert scen_b(po3_seq="filter", po3_seq_below_pts=0.5) == []
    assert len(scen_b(po3_seq="filter")) == 1
    assert scen_b()[0].po3_seq is False                                                          # off: untagged
    # a day that never traded under the open gives False
    ctx, (sl, ss) = mkctx([(101.0, 101.5, 100.5, 101.2)] * 10, w=0.0)
    sw = dict(broke=ib(ctx, "10:05"), ext=100.5, ext_i=ib(ctx, "09:35"))
    assert sm2.po3_seq_state(ctx, sl, sw, ib(ctx, "10:10"), Params(**BASE, po3_seq="tag"), "AM", 101.3) is False
    # mirror: a short on the bearish version
    rows = [(200.0 - o, 200.0 - l, 200.0 - h, 200.0 - c) for o, h, l, c in B_ROWS]
    ctx, (sl, ss) = mkctx(rows, base=100.0)
    sw = dict(broke=ib(ctx, "10:05"), ext=-102.0, ext_i=ib(ctx, "09:45"))
    assert sm2.po3_seq_state(ctx, ss, sw, ib(ctx, "10:10"), Params(**BASE, po3_seq="tag"), "AM", -98.7) is True


# --- BH-A8-opposing-FVG-inversion-confirms (19) -----------------------------------------------------------------------------------

SIBI = [(4013.0, 4014.0, 4012.0, 4012.5), (4012.5, 4012.8, 4009.0, 4009.5), (4009.5, 4010.0, 4008.0, 4009.0),    # a bearish FVG 4010-4012
        (4009.0, 4016.0, 4008.8, 4015.0),                                                                          # closed through upward at 4015
        (4015.0, 4015.5, 4011.0, 4014.0),                                                                          # retest: low 4011, close above 4012
        (4014.0, 4020.0, 4013.0, 4019.0)]


def test_ifvg_narrative():
    ctx, (sl, ss) = mkctx(SIBI, base=4000.0)
    k0 = ib(ctx, "09:30")
    i = k0 + 4
    p = Params(**BASE, ifvg_narrative="block")
    ctx.cur_bias = 1                                                                                          # a bullish draw, unmet
    assert any(abs(g.bottom + 4012) < 1e-9 and abs(g.top + 4010) < 1e-9 for g in ss.gaps)                      # the real bear FVG, mirrored
    assert sm2.ifvg_gate(ctx, ss, dict(broke=None), i, p, -4011.0) == "x_inverted_against_draw"                   # a short at 4011 is blocked
    assert sm2.ifvg_gate(ctx, ss, dict(broke=None), i, p, -4030.0) is None                                      # an entry away from the closed-through gap is not
    assert sm2.ifvg_gate(ctx, ss, dict(broke=None), k0 + 2, p, -4011.0) is None                                 # before the close through
    assert sm2.ifvg_gate(ctx, ss, dict(broke=None), i, replace(p, ifvg_narrative="off"), -4011.0) is None
    ctx.cur_bias = 0
    assert sm2.ifvg_gate(ctx, ss, dict(broke=None), i, p, -4011.0) is None                                      # no draw, no narrative
    # "require": the long needs the closed-through gap retested and held before the MSS
    pr = replace(p, ifvg_narrative="require")
    ctx.cur_bias = 1
    brk = k0 + 5
    assert sm2.ifvg_gate(ctx, sl, dict(broke=brk), brk, pr, 4012.5) is None
    assert sm2.ifvg_confirmed(ctx, sl, dict(broke=brk), brk, pr)
    no_retest = [r for r in SIBI]
    no_retest[4] = (4015.0, 4015.5, 4013.0, 4014.0)                                                             # no bar back into the gap
    ctx2, (sl2, _) = mkctx(no_retest, base=4000.0)
    ctx2.cur_bias = 1
    assert sm2.ifvg_gate(ctx2, sl2, dict(broke=k0 + 5), k0 + 5, pr, 4012.5) == "x_ifvg_narrative"
    lost = [r for r in SIBI]
    lost[5] = (4014.0, 4014.5, 4008.0, 4009.5)                                                                  # then a close back under the gap bottom: not held
    ctx3, (sl3, _) = mkctx(lost, base=4000.0)
    ctx3.cur_bias = 1
    assert not sm2.ifvg_confirmed(ctx3, sl3, dict(broke=k0 + 6), k0 + 5, pr)


# --- BH-B12-gap-up-short-below-0930 (23) -----------------------------------------------------------------------------------------

def test_gap_premium_arm():
    """Gap up to an old NWOG CE (HTF bear array 4095-4101, the CE 4098) with a 09:30 open of 4098: a short before any trade below 4098 waits; after one it is
    allowed; longs are never taken."""
    rows = [(4098.0, 4099.0, 4098.0, 4098.5), (4098.5, 4099.5, 4098.2, 4099.0), (4099.0, 4099.2, 4096.0, 4096.5), (4096.5, 4097.0, 4095.5, 4096.0)]
    conf = SimpleNamespace(valid=lambda t, side, tfs, src, known_by=None: [(4101.0, 4095.0, "W", 2, 0.0)] if side == -1 else [])
    ctx, (sl, ss) = mkctx(rows, base=4098.0, hist=hist_close(close=4080.0, hi=4110.0, lo=4070.0), conf=conf)
    p = Params(**BASE, gap_premium_arm=True)
    k0 = ib(ctx, "09:30")
    lvt = []
    assert sm2.gap_premium_gate(ctx, sl, dict(smt=None), k0 + 1, p, lvt) == "x_gap_premium_long"
    assert sm2.gap_premium_gate(ctx, ss, dict(smt=True), k0 + 1, p, lvt) == "x_gap_premium_wait"      # no bar has traded under 4098 yet
    assert sm2.gap_premium_gate(ctx, ss, dict(smt=True), k0 + 2, p, lvt) is None                       # bar 3 low 4096.0
    assert lvt == ["gap_premium_smt"]
    # no HTF array at the open: nothing is gated
    ctx2, (sl2, ss2) = mkctx(rows, base=4098.0, hist=hist_close(close=4080.0, hi=4110.0, lo=4070.0),
                             conf=SimpleNamespace(valid=lambda *a, **k: []))
    assert sm2.gap_premium_gate(ctx2, sl2, dict(smt=None), k0 + 1, p, []) is None
    # no gap (open at the prior close): nothing is gated
    ctx3, (sl3, _) = mkctx(rows, base=4098.0, hist=hist_close(close=4098.0, hi=4110.0, lo=4070.0), conf=conf)
    assert sm2.gap_premium_gate(ctx3, sl3, dict(smt=None), k0 + 1, p, []) is None


# --- BH-compressed-higher-highs (42) ---------------------------------------------------------------------------------------------

def _pivot_highs(vals):
    h = []
    for v in vals:
        h += [v - 3.0, v]
    h.append(vals[-1] - 3.0)
    h = A(h, float)
    return h, L.pivots(h, h - 1.0, 1)[0]


def test_compressed_highs():
    h, ph = _pivot_highs([4010.0, 4011.0, 4012.5])
    assert L.compressed_highs(h, ph, 40.0, 0.1, 3) == ph[-1].i                                    # 1.0 and 1.5 < 0.1 x 40
    h2, ph2 = _pivot_highs([4010.0, 4020.0, 4035.0])
    assert L.compressed_highs(h2, ph2, 40.0, 0.1, 3) is None                                      # 10 and 15 are real extensions
    assert L.compressed_highs(h, ph, 40.0, 0.1, 3, eq=4011.5) is None                             # the run must sit above the dealing-range EQ
    assert L.compressed_highs(h, ph, 40.0, 0.1, 4) is None
    assert L.compressed_highs(h, ph, 0.0, 0.1, 3) is None                                         # no ADR
    assert L.compressed_highs(h, ph, 40.0, 0.1, 3, end=ph[1].known) is None                       # the third high is not confirmed yet
    h3, ph3 = _pivot_highs([4000.0, 4010.0, 4011.0, 4012.5, 4013.0])
    assert [q.price for q in L.compressed_run(ph3, 40.0, 0.1, 3)] == [4010.0, 4011.0, 4012.5, 4013.0]    # the run is as long as it stays compressed


def test_compressed_highs_gate_and_leg_low_target():
    """A long whose MSS reference is one of the compressed highs is rejected; the short after an MSS below the run is tagged and targets the leg low."""
    rows = [(4018.0, 4020.0, 4012.0, 4013.0), (4013.0, 4014.0, 3990.0, 3992.0), (3992.0, 4003.0, 3991.0, 4002.0), (4002.0, 4010.0, 4001.0, 4006.0),
            (4006.0, 4006.5, 4003.0, 4004.0), (4004.0, 4011.0, 4003.5, 4010.0), (4010.0, 4010.5, 4007.0, 4008.0), (4008.0, 4012.5, 4007.5, 4012.0),
            (4012.0, 4012.2, 4009.0, 4010.0), (4010.0, 4010.5, 3995.0, 3996.0)]
    hs = hist_close(close=4000.0, hi=4040.0, lo=4000.0)                                          # ADR5 = 40
    ctx, (sl, ss) = mkctx(rows, base=4000.0, hist=hs)
    p = Params(**BASE, compressed_hh=True)
    k0 = ib(ctx, "09:30")
    oth = [q for q in sl.ph if q.i >= ctx.start]
    run = L.compressed_run(oth, 40.0, 0.1, 3, sm2.dealing_eq(ctx, sl, k0 + 9), k0 + 9)
    assert [q.price for q in run] == [4010.0, 4011.0, 4012.5]
    lvt = []
    assert sm2.compressed_gate(ctx, sl, dict(ref_i=run[1].i, broke=None), k0 + 9, p, lvt) == "x_compressed_hh"
    assert sm2.compressed_gate(ctx, sl, dict(ref_i=run[0].i - 3, broke=None), k0 + 9, p, lvt) is None
    lvt = []
    assert sm2.compressed_gate(ctx, ss, dict(ref_i=0, broke=k0 + 9), k0 + 9, p, lvt) is None
    assert lvt == ["compressed_hh"]                                                              # the short after the MSS below the run
    leg_low = sm2.compressed_leg_low(ctx, ss, dict(broke=k0 + 9), k0 + 9, p)
    assert leg_low == pytest.approx(-3990.0)                                                      # the leg low, in the short Side's space
    assert sm2.compressed_leg_low(ctx, ss, dict(broke=None), k0 + 9, p) is None


# --- BH-D15-sick-sister-laggard (48) / middle-index (49) / clean-swing-point (50) / depth (51) / D15 contradiction (206) -------------

def _book(rows):
    cols = ["date", "session", "setup", "symbol", "entry_time", "exit_time", "exit_reason", "smt", "final_hit", "day_tags", "dw_tags", "ext_px", "leg_hi_px",
            "move_pct", "clean_swing", "array_depth", "array_respect"]
    df = pd.DataFrame(rows, columns=cols)
    for c in ("entry_time", "exit_time"):
        df[c] = pd.to_datetime(df[c]).dt.tz_localize(NY)
    return df


def _row(sym, entry, exit_, **kw):
    d = dict(date="2026-06-23", session="AM", setup="am_mm", symbol=sym, entry_time=f"2026-06-23 {entry}", exit_time=f"2026-06-23 {exit_}", exit_reason="t1",
             smt=False, final_hit=False, day_tags="", dw_tags="", ext_px=100.0, leg_hi_px=101.0, move_pct=np.nan, clean_swing=None, array_depth=np.nan,
             array_respect=np.nan)
    d.update(kw)
    return d


def test_smt_pick_laggard_objective():
    """NQ met its draw (a trade reached its last level) and exited at 10:00; ES fills after that stay, NQ's later fills go."""
    nq = _book([_row("NQ", "09:40", "10:00", final_hit=True), _row("NQ", "10:30", "10:40", session="PM")])
    es = _book([_row("ES", "10:20", "10:50")])
    out = B.combine(nq, es, pick="laggard_objective")
    assert list(out.symbol) == ["NQ"]                                                              # the AM slot goes to the first fill (NQ 09:40), as 'first'
    # the same-slot later ES fill is the "first" winner only if NQ's earlier fill is gone: put NQ's met trade in the AM and ES's fill in the PM slot
    es_pm = _book([_row("ES", "13:40", "14:10", session="PM")])
    nq2 = _book([_row("NQ", "09:40", "10:00", final_hit=True), _row("NQ", "13:35", "14:00", session="PM")])
    out = B.combine(nq2, es_pm, pick="laggard_objective").sort_values("entry_time")
    assert list(out.symbol) == ["NQ", "ES"]                                                        # NQ's 13:35 PM fill (after its own objective) is dropped; ES's 13:40 stays
    assert list(B.combine(nq2, es_pm, pick="first").sort_values("entry_time").symbol) == ["NQ", "NQ"]
    # consolidation-only: on a trend day the pick reverts to 'first'
    out = B.combine(nq2, es_pm, pick="laggard_objective", laggard_consol_only=True).sort_values("entry_time")
    assert list(out.symbol) == ["NQ", "NQ"]
    nq3 = nq2.assign(day_tags="inside_day")
    out = B.combine(nq3, es_pm, pick="laggard_objective", laggard_consol_only=True).sort_values("entry_time")
    assert list(out.symbol) == ["NQ", "ES"]
    assert Params(laggard_consol_only=True).laggard_consol_only


def test_smt_pick_middle():
    mk3 = lambda sym, mv: _book([_row(sym, "09:40", "10:00", move_pct=mv)])
    out = B.combine(mk3("ES", 0.012), mk3("NQ", 0.008), mk3("YM", 0.003), pick="middle")
    assert list(out.symbol) == ["NQ"]                                                               # +0.8% is the middle of +1.2 / +0.8 / +0.3
    with pytest.raises(ValueError):
        B.combine(mk3("ES", 0.012), mk3("NQ", 0.008), pick="middle")
    assert study.study_pick("middle") == "first" and study.study_pick("middle", 3) == "middle" and study.study_pick("depth") == "depth"
    # a slot without three instruments' fills keeps the first
    out = B.combine(mk3("ES", 0.012), mk3("NQ", 0.008), _book([]), pick="middle")
    assert list(out.symbol) == ["ES"] or list(out.symbol) == ["NQ"]


def test_pick_clean_swing():
    a = _book([_row("ES", "09:40", "10:00", clean_swing=False)])
    b = _book([_row("NQ", "09:45", "10:05", clean_swing=True)])
    assert list(B.combine(a, b, pick="clean_swing").symbol) == ["NQ"]
    assert list(B.combine(a, b, pick="first").symbol) == ["ES"]
    c = _book([_row("NQ", "09:45", "10:05", clean_swing=False)])
    assert list(B.combine(a, c, pick="clean_swing").symbol) == ["ES"]                                # neither has one: the first
    # the tag: a 15m pivot (n=2) between the entry and T1 (side space: a pivot HIGH)
    lv = [4000.0, 4004.0, 4010.0, 4006.0, 4003.0, 4008.0, 4015.0, 4020.0]
    px = np.repeat(lv, 15)
    n = len(px)
    ctx = stub(n)
    sd = S.Side(1, px, px, px, px, 1)
    ctx.idx = pd.date_range("2026-06-23 09:30", periods=n, freq="1min", tz=NY)
    ctx.tf = 1
    assert sm2.clean_swing(ctx, sd, n - 1, 4006.0, 4012.0)                                           # the 15m swing high near 4010
    assert not sm2.clean_swing(ctx, sd, n - 1, 4011.5, 4012.0)                                       # none between 4011.5 and 4012
    assert not sm2.clean_swing(ctx, sd, 10, 4006.0, 4012.0)                                          # too few closed 15m bars


def test_pick_depth():
    nq = _book([_row("NQ", "09:41", "10:00", array_depth=0.95, array_respect=0.9, smt=False)])
    es = _book([_row("ES", "09:40", "10:00", array_depth=0.5, array_respect=1.0, smt=True)])
    assert list(B.combine(nq, es, pick="depth").symbol) == ["NQ"]                                    # deeper into its SIBI, although ES printed the SMT extreme
    tie = _book([_row("ES", "09:40", "10:00", array_depth=0.95, array_respect=0.5)])
    assert list(B.combine(nq, tie, pick="depth").symbol) == ["NQ"]                                   # the tie goes to the cleaner respect
    # the tag: the sweep's depth in the highest HTF array holding it (side space) and the respect of the 15m bodies inside it
    n = 60
    px = np.full(n, 4012.0)
    px[10:30] = 4016.0
    ctx = stub(n)
    ctx.idx = pd.date_range("2026-06-23 09:30", periods=n, freq="1min", tz=NY)
    ctx.tf = 1
    known = float(ctx.idx[0].value)
    ctx.conf = SimpleNamespace(valid=lambda t, side, tfs, src, known_by=None: [(4020.0, 4010.0, "1h", 0, known)])
    sd = S.Side(-1, px, px + 0.5, px - 0.5, px, 1)
    sw = dict(ext=-4019.0, ext_i=20)
    d, r = sm2.array_depth(ctx, sd, sw, n - 1, Params(**BASE))
    assert d == pytest.approx(0.9)                                                                    # a short whose sweep high 4019 ran 90% of the 4010-4020 zone: (4019 - 4010) / 10
    assert r is not None and 0.0 <= r <= 1.0
    ctx.conf = None
    assert sm2.array_depth(ctx, sd, sw, n - 1, Params(**BASE)) == (None, None)


# --- BH-M3-scan-all-indices (54) -------------------------------------------------------------------------------------------------

def test_m3_scan_report():
    es = _book([_row("ES", "09:40", "10:00", date="2026-06-22", entry_time="2026-06-22 09:40", exit_time="2026-06-22 10:00"),
                _row("ES", "09:40", "10:00", date="2026-06-23")])
    nq = _book([_row("NQ", "09:41", "10:01", date="2026-06-23"), _row("NQ", "09:42", "10:02", date="2026-06-24", entry_time="2026-06-24 09:42",
                                                                       exit_time="2026-06-24 10:02")])
    both = B.combine(es, nq)
    assert sorted(both.date.astype(str)) == ["2026-06-22", "2026-06-23", "2026-06-24"]                # the union of the days
    rep = RD.m3_scan(es, nq)
    assert rep["days"] == 3 and rep["one_market_days"] == 2 and rep["both_days"] == 1
    assert rep["share_one_market"] == pytest.approx(2 / 3) and rep["setups_per_day"] == pytest.approx(4 / 3)
    assert RD.m3_scan(es.iloc[:0], nq.iloc[:0])["days"] == 0
    assert Params(markets=("ES", "NQ")).markets == ("ES", "NQ")


# --- BH-three-pool-runs-exhaustion (67) ------------------------------------------------------------------------------------------

def test_pool_runs_exhausted():
    """Three sell-side pools (the previous three sessions' lows 90 / 92 / 94, none taken since) are run by the leg since the last bullish MSS: a short is rejected
    with pool_runs_max 3, allowed with 0 or 4."""
    d = prior_days(D0, 8)
    hs = [rth_day(x, 108.0, lo) for x, lo in zip(d, [91, 91, 91, 91, 91, 90, 92, 94])]
    rows = [(100.0, 100.5, 99.5, 100.2), (100.2, 101.0, 99.5, 100.8), (100.8, 100.9, 100.6, 100.7), (100.7, 103.0, 100.6, 102.5),         # a bullish break at the 4th bar
            (102.5, 102.6, 99.0, 99.5), (99.5, 99.6, 93.5, 93.8), (93.8, 94.0, 91.5, 91.8), (91.8, 92.0, 89.0, 89.5), (89.5, 90.5, 89.2, 90.2)]
    ctx, (sl, ss) = mkctx(rows, hist=hs)
    p = Params(**BASE, pool_runs_max=3)
    i = ib(ctx, "09:30") + 8
    assert sm2.pool_runs(ctx, ss, i, p, "AM") == 3
    assert sm2.pool_runs_gate(ctx, ss, i, p, "AM") == "x_pool_runs_exhausted"
    assert sm2.pool_runs_gate(ctx, ss, i, replace(p, pool_runs_max=4), "AM") is None
    assert sm2.pool_runs_gate(ctx, ss, i, replace(p, pool_runs_max=0), "AM") is None
    assert sm2.pool_runs(ctx, ss, ib(ctx, "09:30") + 5, p, "AM") == 1                                  # only 94 had been taken by the 6th bar... (93.5 < 94)
    # the buy-side mirror: a long after a leg that ran three buy-side pools
    mir = [(200.0 - o, 200.0 - l, 200.0 - h, 200.0 - c) for o, h, l, c in rows]
    hs2 = [rth_day(x, 200.0 - lo, 92.0) for x, lo in zip(d, [91, 91, 91, 91, 91, 90, 92, 94])]
    hs2 = [rth_day(x, 200.0 - lo, 92.0 if False else 200.0 - 109.0) for x, lo in zip(d, [91, 91, 91, 91, 91, 90, 92, 94])]
    ctx2, (sl2, ss2) = mkctx(mir, hist=hs2)
    assert sm2.pool_runs(ctx2, sl2, ib(ctx2, "09:30") + 8, p, "AM") >= 1


# --- BH-premium-FVG-CE-vs-far-edge-trap (69) -------------------------------------------------------------------------------------

def test_far_edge_trap():
    """60m SIBI 4010-4020: a retrace to 4014 (under the CE 4015) then a short is allowed with ce_hold; a retrace to 4019.75 (within 10% of the top) is the trap."""
    def ctx_with(peak):
        rows = [(4005.0, 4006.0, 4004.0, 4005.5), (4005.5, peak, 4005.0, peak - 1.0), (peak - 1.0, peak - 0.5, 4008.0, 4009.0)]
        known = float(pd.Timestamp("2026-06-23 04:00", tz=NY).value)
        conf = SimpleNamespace(valid=lambda t, side, tfs, src, known_by=None: [(4020.0, 4010.0, "1h", 0, known)] if side == -1 and "1h" in tfs else [])
        return mkctx(rows, base=4005.0, conf=conf)
    p = Params(**BASE, far_edge_trap=True)
    ctx, (sl, ss) = ctx_with(4014.5)
    i = ib(ctx, "09:30") + 2
    lvt = []
    assert sm2.far_edge_gate(ctx, ss, dict(entry_ref=-4013.0), i, p, lvt) is None and lvt == ["ce_hold"]
    ctx, (sl, ss) = ctx_with(4019.75)
    assert sm2.far_edge_gate(ctx, ss, dict(entry_ref=-4013.0), i, p, []) == "x_far_edge_trap"
    ctx, (sl, ss) = ctx_with(4017.0)                                                                    # past the CE but short of the far edge: neither tag nor trap
    lvt = []
    assert sm2.far_edge_gate(ctx, ss, dict(entry_ref=-4013.0), i, p, lvt) is None and lvt == []
    assert sm2.far_edge_gate(ctx, ss, dict(entry_ref=-4030.0), i, p, []) is None                       # the entry is not inside the HTF FVG


# --- B18-am-smt-window-points (89) -----------------------------------------------------------------------------------------------

def test_smt_window_points():
    """A 02:00 low vs a 10:50 low counts only with the window 120 / 660."""
    p = Params(**BASE, smt_windows=((720, 900),), smt_pre=True)       # (smt_pre adds the AM window to the other windows; alone it narrows nothing)
    assert not S._smt_window_ok(p, 650) and S._smt_window_ok(p, 400)                                    # 10:50 is outside 05:00-09:30; 06:40 inside
    assert not S._smt_window_ok(p, 120)                                                                  # 02:00 is outside too
    q = replace(p, smt_win_a=120, smt_win_b=660)
    assert S._smt_window_ok(q, 650) and S._smt_window_ok(q, 120) and not S._smt_window_ok(q, 660)
    # the opens as candidate points: pools open_0830 / open_0930, the bar after the open is their first
    rows = [(100.0, 100.4, 99.8, 100.2)] * 6
    ctx, (sl, ss) = mkctx(rows)
    out = {}
    sm2.open_pools(ctx, sl, ib(ctx, "09:40"), replace(p, smt_open_points=True), out)
    assert out["open_0930"] == 100.0 and "open_0830" in out
    out2 = {}
    sm2.open_pools(ctx, sl, ib(ctx, "09:40"), p, out2)
    assert out2 == {}
    assert sm2.created(ctx, "open_0930") == ib(ctx, "09:30") + 1 and sm2.created(ctx, "pdl1") is None
    assert "open_0930" in S._sell_side(ctx, sl, "AM", ib(ctx, "09:40"), False, replace(p, smt_open_points=True))
    assert "open_0930" not in S._sell_side(ctx, sl, "AM", ib(ctx, "09:40"), False, p)


# --- NEW-low-of-day-zone-tag-first (92) ------------------------------------------------------------------------------------------

def _lod_bars():
    """15010 flat; the 06:00 hour candle (bars 72-83) has a lower tail (low 14960, body bottom 15000: CE 14980) and a 5m bull FVG 14979-14983 inside it."""
    bars = [(15010.0, 15010.5, 15009.5, 15010.0)] * 195
    bars = list(bars)
    for k in range(72, 84):
        bars[k] = (15000.0, 15001.0, 14999.0, 15000.0)
    bars[74] = (14962.0, 14979.0, 14960.0, 14978.0)
    bars[75] = (14978.0, 14992.0, 14977.0, 14991.0)
    bars[76] = (14991.0, 14997.0, 14983.0, 14996.0)
    return bars


def _lod_ctx(bars, p):
    df = pd.DataFrame(bars, columns=["open", "high", "low", "close"])
    df["volume"] = 1.0
    df.index = pd.date_range(pd.Timestamp(f"{D0} 00:00", tz=NY), periods=len(df), freq="5min")
    ctx = ctx_for(df, hist_close(close=15010.0, hi=15040.0, lo=14990.0), p)
    sl = S.Side(1, ctx.o, ctx.h, ctx.l, ctx.c, p.pivot_n)
    ctx.sides_map = {1: sl}
    return ctx, sl


def test_lod_zone_first():
    """Zone 14980 (the CE of the 06:00 hour's tail with a 5m discount FVG): a long before any trade down to 14980.5 is rejected and allowed after one (with an SMT sweep)."""
    p = Params(**BASE, lod_zone_first=True, eq_tol_pts=0.5)
    ctx, sl = _lod_ctx(_lod_bars(), p)
    i = ib(ctx, "08:35")
    assert sm2.lod_zone(ctx, sl, i, p) == pytest.approx(14980.0)
    assert sm2.lod_zone(ctx, sl, ib(ctx, "08:20"), p) is None                                          # before 08:30 nothing is defined
    assert sm2.lod_gate(ctx, sl, dict(smt=True), i, p) == "x_lod_zone_first"                            # no trade down to the zone yet
    bars = _lod_bars()
    bars[104] = (15010.0, 15010.5, 14980.5, 15008.0)                                                    # 08:40 trades down to 14980.5 (the zone + 2 ticks)
    ctx2, sl2 = _lod_ctx(bars, p)
    j = ib(ctx2, "08:45")
    assert sm2.lod_gate(ctx2, sl2, dict(smt=True), j, p) is None
    assert sm2.lod_gate(ctx2, sl2, dict(smt=False), j, p) == "x_lod_no_smt"                             # then the sweep needs the SMT tag
    assert sm2.lod_gate(ctx2, sl2, dict(smt=None), j, p) == "x_lod_no_smt"
    bars = _lod_bars()
    bars[104] = (15010.0, 15010.5, 14981.5, 15008.0)                                                    # a tick short of the zone + 2 ticks: still waiting
    ctx3, sl3 = _lod_ctx(bars, p)
    assert sm2.lod_gate(ctx3, sl3, dict(smt=True), ib(ctx3, "08:45"), p) == "x_lod_zone_first"
    # no FVG at the tail's CE: no zone, nothing is gated
    bars = _lod_bars()
    bars[76] = (14991.0, 14997.0, 14975.0, 14996.0)
    ctx4, sl4 = _lod_ctx(bars, p)
    assert sm2.lod_zone(ctx4, sl4, ib(ctx4, "08:35"), p) is None and sm2.lod_gate(ctx4, sl4, dict(smt=None), ib(ctx4, "08:35"), p) is None


# --- B18-smt-only-with-bias (98) -------------------------------------------------------------------------------------------------

def test_smt_with_bias():
    sd = SimpleNamespace(sign=1)
    sw = dict(smt=True, smt2=None)
    sm2.smt_bias_gate(SimpleNamespace(cur_bias=-1), sd, sw, Params())                                    # want -1, a bullish SMT on a long: the laggard
    assert sw["smt"] is False and sw["smt_laggard"] is True
    sw = dict(smt=True, smt2=True)
    sm2.smt_bias_gate(SimpleNamespace(cur_bias=1), sd, sw, Params())                                     # want +1: qualified
    assert sw["smt"] is True and sw["smt2"] is True and "smt_laggard" not in sw
    sw = dict(smt=True)
    sm2.smt_bias_gate(SimpleNamespace(cur_bias=0), sd, sw, Params())                                     # no bias: untouched here ...
    assert sw["smt"] is True
    # ... the order is rejected at completion (no clear daily IOF - do not trade the SMT)
    p = Params(**BASE, smt_with_bias=True)
    ctx = stub(5)
    assert sm2.order_gate(ctx, sd, dict(smt=True), 3, p, 100.0, 99.0, "AM", None, None, [], {}, {}) == "x_smt_no_bias"
    assert sm2.order_gate(ctx, sd, dict(smt=False), 3, p, 100.0, 99.0, "AM", None, None, [], {}, {}) is None
    ctx.cur_bias = 1
    assert sm2.order_gate(ctx, sd, dict(smt=True), 3, p, 100.0, 99.0, "AM", None, None, [], {}, {}) is None


# --- B5-mature-trend-continuation (113) ------------------------------------------------------------------------------------------

def test_mature_flag_block():
    d = prior_days(D0, 20)
    closes = np.linspace(82.0, 114.0, 20)                                                               # an uptrend that ends at 85% of the 80-120 range
    hs = [rth_day(x, 120.0, 80.0, close=float(c)) for x, c in zip(d, closes)]
    ctx = stub(5, hist=hs)
    sd = SimpleNamespace(sign=1)
    p = Params(**BASE, mature_flag_block=True)
    assert sm2.mature_flag_gate(ctx, sd, 3, p) == "x_mature_flag"
    hs2 = [rth_day(x, 120.0, 80.0, close=float(c)) for x, c in zip(d, np.linspace(70.0, 100.0, 20))]       # ends at 50%
    assert sm2.mature_flag_gate(stub(5, hist=hs2), sd, 3, p) is None
    assert sm2.mature_flag_gate(ctx, SimpleNamespace(sign=-1), 3, p) is None                              # not a with-trend order
    # inside an opposing daily array
    ctx3 = stub(5, hist=hs2, conf=SimpleNamespace(at=lambda t, price, side: ["D"] if side == -1 else []))
    assert sm2.mature_flag_gate(ctx3, sd, 3, p) == "x_mature_flag"
    # the mirror: a downtrend that ends at 15% of the range
    hs4 = [rth_day(x, 120.0, 80.0, close=float(c)) for x, c in zip(d, np.linspace(118.0, 86.0, 20))]
    assert sm2.mature_flag_gate(stub(5, hist=hs4), SimpleNamespace(sign=-1), 3, p) == "x_mature_flag"


# --- M12-classic-patterns-fade (123): already built as hs_fade ---------------------------------------------------------------------

def test_hs_fade_level():
    """The spec's fixture: a 15m head and shoulders with the neckline at 4000 and the head at 4030 - the built detector (levels.head_shoulders, used by hs_fade)."""
    h = A([4012, 4020, 4010, 4030, 4012, 4021, 4005], float)
    l = A([4004, 4008, 4000, 4010, 4000, 4010, 3995], float)
    r = L.head_shoulders(h, l, 1, 1.0)
    assert r is not None and r["neck"] == 4000.0 and r["head"].price == 4030.0
    assert Params(hs_fade=True, hs_tf=15).hs_fade


# --- X3-a15-mitblock-bear-context (124) and A15-mitigation-block-entry (46, tested in part B) --------------------------------------

BEAR_MB = [(100.0, 101.0, 99.0, 100.5), (100.5, 106.0, 100.0, 105.0), (105.0, 105.5, 100.0, 101.0), (101.0, 101.5, 94.0, 95.0), (95.0, 99.5, 96.0, 99.0),
           (99.0, 103.0, 98.5, 102.0), (102.0, 102.5, 97.0, 97.5), (97.5, 98.0, 92.0, 92.5), (92.5, 96.0, 92.2, 95.5), (95.5, 100.5, 95.0, 100.0)]


def test_mit_needs_bias(monkeypatch):
    """A bearish mitigation block (the last down-close candle at the failed low) is an entry only with the bias its way and an untaken daily pool beyond - then the
    target is that pool (the previous day's low)."""
    got = []
    monkeypatch.setattr(S, "_finish_order", lambda *a, **k: got.append((a, k)) or "order")
    hs = hist_close(close=100.0, hi=110.0, lo=88.0)                                                      # PDL 88 is untaken
    ctx, (sl, ss) = mkctx(BEAR_MB, hist=hs)
    ctx.cur_bias = 0
    assert [z for z in ss.mitigations() if z.i >= ctx.start], "the fixture must produce a bear mitigation block"
    p = Params(**BASE, mitigation_entry=True, mit_needs_bias=True)
    i = ib(ctx, "09:30") + 7                                                                                  # the break bar: the block is known, price (92.5) is under it
    assert sm2.mit_order(ctx, ss, i, p, "AM", 1.0) is None                                                 # want 0: no order
    ctx.cur_bias = -1
    assert sm2.mit_order(ctx, ss, i, p, "AM", 1.0) == "order"
    a, k = got[0]
    assert k["fixed"] == [(S._exit_px(-88.0, "pool", p), "pool")]                                          # T = the previous day's low (side space)
    assert a[5]["key"] == "mitigation" and a[6] == -94.0 and a[7] == pytest.approx(-101.5 - p.pad)        # a sell limit at the block's near edge (real 94), the stop above its high (real 101.5)
    # no untaken daily pool beyond: nothing
    got.clear()
    hs_low = hist_close(close=100.0, hi=110.0, lo=96.0)
    ctx2, (sl2, ss2) = mkctx(BEAR_MB, hist=hs_low)
    ctx2.cur_bias = -1
    ctx2.pd = {}
    assert sm2.mit_order(ctx2, ss2, ib(ctx2, "09:30") + 7, p, "AM", 1.0) is None


# --- X3-graduated-pricing-second-touch (126) -------------------------------------------------------------------------------------

def test_touch_count_tag():
    """A level touched at 09:40 and swept at 10:05: touch_n = 2."""
    rows = [(100.5, 101.0, 100.4, 100.8), (100.8, 101.0, 100.4, 100.6), (100.6, 100.9, 100.05, 100.5), (100.5, 100.9, 100.3, 100.7), (100.7, 101.0, 100.4, 100.8),
            (100.8, 101.0, 100.4, 100.9), (100.9, 101.0, 100.5, 100.8), (100.8, 100.9, 100.4, 100.5), (100.5, 100.8, 100.4, 100.5), (100.5, 100.6, 100.3, 100.5),
            (100.5, 100.6, 100.4, 100.5), (100.5, 100.6, 100.4, 100.5), (100.5, 100.6, 99.5, 99.8)]
    ctx, (sl, ss) = mkctx(rows, base=100.5)
    p = Params(**BASE, touch_tag=True, eq_tol_pts=0.05)                                                       # touches within 4 x 0.05 = 0.2 above the level
    j = ib(ctx, "10:30")
    sw = dict(key="premarket", level=100.0, ext=99.5, ext_i=j, sweep_i=j)
    assert sm2.touch_count(ctx, sl, sw, j, p, "AM") == 2                                                     # the 09:40 touch (low 100.05) + the sweep
    far = dict(sw, level=99.0, sweep_i=j)
    assert sm2.touch_count(ctx, sl, far, j, p, "AM") == 1
    tags = {}
    sm2.order_gate(ctx, sl, sw, j, p, 100.5, 99.0, "AM", None, None, [], {}, tags)
    assert tags["touch_n"] == 2
    tags = {}
    sm2.order_gate(ctx, sl, sw, j, replace(p, touch_tag=False), 100.5, 99.0, "AM", None, None, [], {}, tags)
    assert "touch_n" not in tags


# --- B12-judas-depth-adr (192) ---------------------------------------------------------------------------------------------------

def test_judas_depth():
    """Open 4000, low 3985, ADR5 40: depth 0.375 - rejected with max 0.33, allowed with 0.4 (tagged either way)."""
    rows = [(4000.0, 4001.0, 3985.0, 3990.0)] + [(3990.0, 3992.0, 3989.0, 3991.0)] * 3
    hs = hist_close(close=4000.0, hi=4040.0, lo=4000.0)
    ctx, (sl, ss) = mkctx(rows, base=4000.0, hist=hs)
    i = ib(ctx, "09:40")
    sw = dict(ext=3985.0, ext_i=ib(ctx, "09:30"))
    p = Params(**BASE, judas_max_adr=0.33)
    assert sm2.judas_depth(ctx, sl, sw, i, p, "AM") == pytest.approx(0.375, rel=0.01)
    tags = {}
    assert sm2.order_gate(ctx, sl, sw, i, p, 3992.0, 3984.0, "AM", None, None, [], {}, tags) == "x_judas_too_deep"
    tags = {}
    assert sm2.order_gate(ctx, sl, sw, i, replace(p, judas_max_adr=0.4), 3992.0, 3984.0, "AM", None, None, [], {}, tags) is None
    assert tags["judas_depth"] == pytest.approx(0.375, rel=0.01)
    assert sm2.judas_depth(ctx, sl, dict(ext=4001.0), i, p, "AM") == 0.0                                      # not beyond the open
    # the mirror: a short, the Judas above the open
    rows_s = [(4000.0, 4015.0, 3999.0, 4010.0)] + [(4010.0, 4011.0, 4008.0, 4009.0)] * 3
    ctx2, (_, ss2) = mkctx(rows_s, base=4000.0, hist=hs)
    assert sm2.judas_depth(ctx2, ss2, dict(ext=-4015.0, ext_i=ib(ctx2, "09:30")), ib(ctx2, "09:40"), p, "AM") == pytest.approx(0.375, rel=0.01)


# --- T3-london-close-multiday-reversal (199) -------------------------------------------------------------------------------------

def test_lc_reentry():
    """A 09:45 reversal long stopped at 10:20, then a 10:40 sweep of a lower low inside the same daily FVG: a second long is allowed (only that one while the slot
    is re-opened)."""
    from types import SimpleNamespace as NS
    ctx, (sl, ss) = mkctx([(100.0, 100.5, 99.0, 99.5)] * 3 + [(99.5, 100.0, 98.0, 98.5)] * 8, base=100.0)
    p = Params(**BASE, lc_reentry=True)
    k = ib(ctx, "10:40")
    cf = ["D"]
    # tagging: 10:00-12:00, the sweep extreme under the 09:30 open (100.0) and at an HTF array
    assert sm2.lc_reversal(ctx, sl, dict(ext=98.0), k, p, cf, True)
    assert not sm2.lc_reversal(ctx, sl, dict(ext=98.0), ib(ctx, "09:45"), p, cf, True)                          # before 10:00
    assert not sm2.lc_reversal(ctx, sl, dict(ext=100.5), k, p, cf, True)                                         # not against the morning
    assert not sm2.lc_reversal(ctx, sl, dict(ext=98.0), k, p, [], False)                                         # no HTF array
    tags, lvt = {}, []
    sm2.order_gate(ctx, sl, dict(ext=98.0, smt=None), k, p, 99.0, 97.5, "AM", cf, True, lvt, {}, tags)
    assert tags["lc_reversal"] is True and "lc_reversal" in lvt
    # the stopped-out trade re-opens the slot
    tr = NS(side="long", ext_px=98.5, session="AM")
    done, state = {"AM": True}, {}
    sm2.lc_reopen(ctx, tr, done, "AM", state)
    assert done["AM"] is False and state["lc_done"] is True
    assert sm2.order_gate(ctx, sl, dict(ext=98.0, smt=None), k, p, 99.0, 97.5, "AM", cf, True, [], {}, {}) is None            # beyond the first extreme 98.5, at the array
    assert sm2.order_gate(ctx, sl, dict(ext=99.0, smt=None), k, p, 99.0, 97.5, "AM", cf, True, [], {}, {}) == "x_lc_retry"   # not beyond it
    assert sm2.order_gate(ctx, ss, dict(ext=-98.0, smt=None), k, p, -99.0, -97.5, "AM", cf, True, [], {}, {}) == "x_lc_retry"  # the other side
    # the switch off: the stopped-out trade does not re-open anything (strategy._after_close)
    assert not Params().lc_reentry and not Params().lc_tag


# --- D15-which-index-contradiction (206) -----------------------------------------------------------------------------------------

def test_smt_pick_fixed_es():
    """An NQ-only divergence with an ES fill: the ES fill is kept (and qualified); an NQ fill is dropped."""
    es = _book([_row("ES", "09:40", "10:00", smt=False)])
    nq = _book([_row("NQ", "09:41", "10:01", smt=True)])
    out = B.combine(es, nq, pick="fixed_es")
    assert list(out.symbol) == ["ES"] and bool(out.smt.iloc[0]) is True
    assert B.combine(nq, pick="fixed_es").empty
    out = B.combine(es, _book([_row("NQ", "09:41", "10:01", smt=False)]), pick="fixed_es")
    assert list(out.symbol) == ["ES"] and bool(out.smt.iloc[0]) is False
    # swept = the laggard alias (the SMT-tagged fill)
    both = B.combine(_book([_row("ES", "09:40", "10:00", smt=False)]), _book([_row("NQ", "09:41", "10:01", smt=True)]), pick="swept")
    assert list(both.symbol) == ["NQ"]
    assert list(B.combine(es, nq, pick="laggard").symbol) == ["NQ"]


# --- B18-pm-smt-reference-points (207) -------------------------------------------------------------------------------------------

def _pm_ctx(lunch_low, post_low, base):
    rows = {}
    bars = [(base, base + 1, base - 1, base)] * 195
    bars = list(bars)
    for k in range(144, 156):                        # 12:00-13:00
        bars[k] = (base, base + 1, lunch_low if k == 150 else base - 0.5, base)
    bars[156] = (base, base + 1, base - 0.5, base)   # 13:00
    bars[157] = (base, base + 0.5, post_low + 1.0, base - 1)
    bars[158] = (base - 1, base, post_low, base - 0.5)       # the first pivot low after 13:00
    bars[159] = (base - 0.5, base + 1, post_low + 1.5, base)
    bars[160] = (base, base + 1, base - 0.2, base)
    df = pd.DataFrame(bars, columns=["open", "high", "low", "close"])
    df["volume"] = 1.0
    df.index = pd.date_range(pd.Timestamp(f"{D0} 00:00", tz=NY), periods=len(df), freq="5min")
    p = Params(**BASE)
    ctx = ctx_for(df, history(D0), p)
    return ctx, S.Side(1, ctx.o, ctx.h, ctx.l, ctx.c, 1)


def test_smt_pm_points():
    """ES lunch low 4000 and a post-13:00 low 3998; NQ lunch low 13000 and a post-13:00 low 13005: ES made the lower low, NQ did not - SMT True."""
    es, es_sd = _pm_ctx(4000.0, 3998.0, 4004.0)
    nq, nq_sd = _pm_ctx(13000.0, 13005.0, 13010.0)
    i = ib(es, "13:30")
    assert sm2.lunch_post(es, es_sd, i) == (4000.0, 3998.0)
    assert sm2.lunch_post(nq, nq_sd, i) == (13000.0, 13005.0)
    assert sm2.pm_points(es, es_sd, i, nq, nq_sd, i) is True
    nq2, nq2_sd = _pm_ctx(13000.0, 12990.0, 13010.0)                                                          # both made the lower low: no divergence
    assert sm2.pm_points(es, es_sd, i, nq2, nq2_sd, i) is False
    assert sm2.lunch_post(es, es_sd, ib(es, "12:55")) is None                                                  # before the 13:00 pivot is confirmed
    # the divergence the other way (ES fails, NQ makes the low) also qualifies the PM long in ES
    es3, es3_sd = _pm_ctx(4000.0, 4002.0, 4004.0)
    nq3, nq3_sd = _pm_ctx(13000.0, 12990.0, 13010.0)
    assert sm2.pm_points(es3, es3_sd, i, nq3, nq3_sd, i) is True
    # wired into _smt for the PM only (the generic sweep pair is not used)
    p = Params(**BASE, smt_pm_points=True)
    pctx = nq
    psides = {1: nq_sd, -1: S.Side(-1, nq.o, nq.h, nq.l, nq.c, 1)}
    ppos = pd.Series(np.arange(len(nq.idx)), index=nq.idx)
    assert S._smt(es, es_sd, i, "lunch", 4000.0, "PM", pctx, psides, ppos, p) is True
