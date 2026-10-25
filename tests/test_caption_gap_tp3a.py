"""Caption-gap pass, package targets_partials #3/4, part A: the unit and engine tests of the 33 specs (levels_liquidity_targets.md 106, 107, 109, 110, 119, 126, 131, 132, 134, 140, 156, 159, 168, 169, 170,
171, 172, 175, 178; management_partials_trailing_exits.md 1, 2, 3, 4, 7, 34, 35, 37, 38, 39, 40, 41, 42, 43). Hand-made bars and stub confluence tables (as test_caption_gap_tp2a.py), the tp3.py helpers called
directly, scenario C through run_day for the order-level switches. No platform-specific paths; nothing here needs market data. The study variants and the no-look-ahead runs are in test_caption_gap_tp3b.py."""
from dataclasses import replace
from datetime import date
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from mentorship import levels as L, sm2, strategy as S, targets as TP, tp3, study
from mentorship.strategy import Params

from test_targets_partials import bar_ctx, conf
from test_caption_gap_tp2a import D0, P, flat, hist_days, mk, side
from test_caption_gap_tp1a import _tp_run
from test_caption_gap_tp1b import _forced, _fp

NY = "America/New_York"
NEW_SWITCHES = (
    "min_rr_final", "void_legs", "ob_target_order", "weekly_beyond_mode", "dt_proj", "grades60", "target_past_eq60", "proj_ext_anchor", "daily_breaker_cap", "adr_conv_target", "adr_t2_htf", "adr_ext",
    "adr_anchor", "pm_am_leg", "consol_overnight_targets", "wide_or_draw", "pm_am_rb", "pm_launch_filter", "session_obj_tf", "fvg_target_level", "pool_exit", "pool_exit_fomc_before", "proj_kind",
    "adr_before_frac", "partial_mode", "exit_mode2", "speed_skip", "pool_milestone", "no_collapse_htf", "ladder_preset", "ladder037_ce", "energy_split", "fixed_partials", "mm_anchor",
    "grades60_range_only", "proj_ext_sym",
)
KNOBS = ("void_leg_mult", "void_max_opp", "grades60_src", "proj_ext2", "adr_conv_pts", "adr_conv_last", "wide_or_mult", "fvg_deep_frac", "pool_before_ticks", "proj_before_pts", "new_first", "no_collapse_keep",
         "energy_room_pts", "fixed_partial_fracs")
GAP_IDS = (
    "L15-min-3r-final-draw", "new-void-fill-target", "L13-sweep-low-measured-move", "X1-bullish-objective-order", "L3-daily-target-weekly-beyond", "new-double-top-projection", "new-60day-range-grades",
    "L14-target-past-eq", "L13-cc-extension-projections", "new-swing-target-breaker-cap", "LLT3-target-confluence-projection-adr-array", "LLT3-adr5-target-ladder", "LLT3-pm-measured-move-am-leg",
    "LLT3-consolidation-day-overnight-targets", "LLT3-wide-or-bias-end", "LLT3-pm-target-am-rejection-block", "LLT3-pm-reversal-launch-array-filter", "LLT3-session-targets-15m-60m",
    "LLT3-impulse-retrace-expansion", "X2-pdarray-exit-at-or-inside-edge", "X2-pool-exit-at-or-before", "X2-projection-target-1tick-before", "X2-exit-buffer-range", "X2-exit-buffer-before-day-extreme",
    "X3-new-vs-experienced-partials", "X3-full-pull-vs-mandatory-partial", "X3-pool-below-untraded-htf-partial", "X3-no-collapse-intermediate-pools", "D13-speed-bump-ladder-004",
    "X3-partial-size-by-energy", "X3-five-handle-first-partial-before-draw", "X3-gradient-ladder-htf-target", "X3-037-three-unit-ladder",
)


def mk_at(rows, start="2026-06-23 09:30", **kw):
    """Like tp2a.mk but the bars start at `start` (overnight bars for the consolidation-day test)."""
    o, h, l, c = [np.array(x, float) for x in zip(*rows)]
    idx = pd.date_range(start, periods=len(o), freq="5min", tz=NY)
    base = dict(pd={}, sess={}, org=[], org_today=False, or_hl=None, or_end=600, am_hl=None, day=D0, hist=hist_days(), wicks=[], wick=None, wbias=0, pw=None, pm_=None, gaps=None, opens={})
    base.update(kw)
    return SimpleNamespace(conf=base.pop("conf", None), idx=idx, tf=5, start=0, o=o, h=h, l=l, c=c, t=(idx.hour * 60 + idx.minute).values, **base)


def sd_of(ctx, sign=1):
    return S.Side(sign, ctx.o, ctx.h, ctx.l, ctx.c, 1, 0.0)


def pk(**kw):
    return Params(**{**P, **kw})


def _walk(prices, w=0.4):
    """5m bars walking the given closes: o = previous close, a small wick."""
    rows, prev = [], prices[0]
    for c in prices:
        rows.append((prev, max(prev, c) + w, min(prev, c) - w, c))
        prev = c
    return rows


# --- defaults / validation / study variants -------------------------------------------------------------------------------------------------------

def test_new_switch_defaults_and_validation():
    p = Params()
    assert (p.min_rr_final, p.void_legs, p.void_leg_mult, p.void_max_opp, p.ob_target_order, p.weekly_beyond_mode, p.dt_proj, p.grades60, p.grades60_src, p.target_past_eq60, p.proj_ext_anchor, p.proj_ext2,
            p.daily_breaker_cap, p.adr_conv_target, p.adr_conv_pts, p.adr_conv_last, p.adr_t2_htf, p.adr_ext, p.adr_anchor, p.pm_am_leg) == (
        0.0, False, 1.5, 1, False, "off", False, False, "body", False, "leg", 1.62, False, False, 1.0, 690, False, False, "day_low", False)
    assert (p.consol_overnight_targets, p.wide_or_draw, p.wide_or_mult, p.pm_am_rb, p.pm_launch_filter, p.session_obj_tf, p.fvg_target_level, p.fvg_deep_frac, p.pool_exit, p.pool_before_ticks,
            p.pool_exit_fomc_before, p.proj_kind, p.proj_before_pts, p.adr_before_frac, p.partial_mode, p.new_first, p.exit_mode2, p.speed_skip, p.pool_milestone, p.no_collapse_htf, p.no_collapse_keep,
            p.ladder_preset, p.ladder037_ce, p.energy_split, p.energy_room_pts, p.fixed_partials, p.fixed_partial_fracs) == (
        False, False, 1.5, False, False, False, "before_edge", 0.75, "beyond", 2, False, False, 0.25, 0.15, "", 0.8, "", False, 0.0, False, 0.2, "", False, False, 5.0, (), (0.25, 0.25))
    assert p.pool_beyond_pts == 0.25 and p.mm_anchor == "leg" and p.sd_htf_tol == 1.0                              # the built defaults stay
    assert not tp3.any_on(p) and not tp3.raw_on(p) and not tp3.exit_on(p)
    for kw in (dict(fvg_target_level="x"), dict(pool_exit="x"), dict(partial_mode="x"), dict(exit_mode2="x"), dict(ladder_preset="x"), dict(weekly_beyond_mode="x"), dict(grades60_src="x"),
               dict(proj_ext_anchor="x"), dict(adr_anchor="x"), dict(mm_anchor="x"), dict(min_rr_final=-1), dict(void_leg_mult=0), dict(void_max_opp=-1), dict(fvg_deep_frac=1.5), dict(pool_before_ticks=-1),
               dict(proj_before_pts=-1), dict(adr_conv_pts=-1), dict(adr_conv_last=2000), dict(wide_or_mult=0), dict(adr_before_frac=-1), dict(proj_ext2=1.0), dict(new_first=0), dict(pool_milestone=1.0),
               dict(no_collapse_keep=1.0), dict(energy_room_pts=-1), dict(fixed_partials=(0.0,)), dict(fixed_partials=(5.0, 10.0), fixed_partial_fracs=(0.25,)), dict(fixed_partials=(5.0,), fixed_partial_fracs=(1.0,)),
               dict(ladder_preset="004", exit_mode2="full_pull"), dict(partial_mode="new", ladder_preset="037"), dict(exit_mode2="pay_first", partial_mode="quarters")):
        with pytest.raises(ValueError):
            Params(**kw)
    Params(partial_mode="experienced", exit_mode2="pay_first")                                                       # "experienced" is today's ladder: no conflict
    assert set(NEW_SWITCHES) | set(KNOBS) <= set(Params.__dataclass_fields__)


def test_inert_switch_note():
    with pytest.warns(UserWarning, match="inert switches \\(targets_partials #3/4\\)"):
        Params(speed_skip=True, ladder037_ce=True, adr_ext=True, mm_anchor="impulse")


def test_every_switch_has_a_study_variant():
    on = set()
    for g in GAP_IDS:
        vs = [v for v in study.DECISIONS if v == g or v.startswith(g + "_")]
        assert vs, g
        for v in vs:
            Params(**study.DECISIONS[v])
            on |= set(study.DECISIONS[v])
    missing = [s for s in NEW_SWITCHES if s not in on]
    assert not missing, missing
    assert all(v in study.DECISIONS for v in study._TP3_DECISIONS)
    names = list(study.DECISIONS)
    assert names.index("L15-min-3r-final-draw") > names.index("new-defended-level")


# --- L15-min-3r-final-draw (106) ------------------------------------------------------------------------------------------------------------------

def test_min_rr_final_draw():
    ctx = mk(flat(12))
    sd = side(ctx)
    keep = [(4110.0, "pool")]                                              # risk 4 (entry 4100), final 10 pts away = 2.5 R
    kw = dict(ctx=ctx, sd=sd, sw=dict(ext=4096.0, ext_i=2), i=8, session="AM", entry=4100.0, risk=4.0, keep=keep, keep_full=keep, draw=4110.0, final_T=False, lvt=[], tags={}, st={}, locked=False, fixed=None)
    assert tp3.late(p=pk(min_rr_final=3.0), **kw)[0] == "x_min_rr_final"
    assert tp3.late(p=pk(min_rr_final=2.0), **kw)[0] is None
    assert tp3.late(p=pk(), **kw)[0] is None
    # a locked draw counts, not the last inner rung
    kw2 = dict(kw, keep=[(4102.0, "array"), (4120.0, "pool")], keep_full=[(4102.0, "array"), (4120.0, "pool")], draw=4120.0, final_T=True, locked=True)
    assert tp3.late(p=pk(min_rr_final=4.0), **kw2)[0] is None and tp3.late(p=pk(min_rr_final=6.0), **kw2)[0] == "x_min_rr_final"


def test_min_rr_final_engine():
    base = _tp_run()
    assert len(base) == 1                                                  # scenario C: entry 100.4, stop 99.1, final 108.25 = 6.0 R
    assert len(_tp_run(min_rr_final=5.0)) == 1 and len(_tp_run(min_rr_final=7.0)) == 0


# --- new-void-fill-target (107) -------------------------------------------------------------------------------------------------------------------

def _leg_rows():
    quiet = [(4104.0, 4105.0, 4103.0, 4104.5), (4104.5, 4105.5, 4103.5, 4104.0)] * 4
    up = [(4101.0, 4108.0, 4100.0, 4106.0)]                                # the last up-close candle before the drop: low 4100
    big = [(4106.0, 4106.0, 4092.0, 4094.0), (4094.0, 4094.0, 4082.0, 4084.0), (4084.0, 4084.0, 4070.0, 4072.0)]
    after = [(4072.0, 4074.0, 4071.0, 4073.0)] * 3
    return quiet + up + big + after


def test_one_sided_leg_void_target():
    o, h, l, c = [np.array(x, float) for x in zip(*_leg_rows())]
    zs = L.one_sided_legs(o, h, l, c, 1.5, 1)
    assert len(zs) == 1 and zs[0].kind == "bear" and zs[0].top == 4100.0 and zs[0].bottom == 4070.0 and zs[0].mid == 4085.0 and zs[0].i == 12 and zs[0].src == 8
    assert L.one_sided_legs(o, h, l, c, 6.0, 1) == []                      # no candle is that large
    ctx = mk(_leg_rows())
    sd = side(ctx)
    p = pk(void_legs=True)
    st = {}
    out = tp3.void_levels(ctx, sd, 14, p, 4060.0, st)
    assert out == [(4085.0, "array"), (4100.0, "array")] and st["void_final"] == 4100.0
    assert tp3.void_levels(ctx, sd, 14, p, 4090.0, {}) == [(4100.0, "array")]          # the CE is behind the entry: only the top
    # one bar of the leg is an up-close: allowed once (void_max_opp=1), not with 0
    rows = _leg_rows()
    rows = rows[:10] + [(4093.0, 4095.0, 4091.0, 4094.5)] + rows[10:]       # an up-close inside the leg
    o2, h2, l2, c2 = [np.array(x, float) for x in zip(*rows)]
    z1 = L.one_sided_legs(o2, h2, l2, c2, 1.5, 1)
    assert len(z1) == 1 and z1[0].top == 4100.0 and z1[0].bottom == 4070.0
    assert len(L.one_sided_legs(o2, h2, l2, c2, 1.5, 0)) == 2               # without the allowance the leg splits in two
    # the void is filled by the price after it: no rung
    rows3 = _leg_rows() + [(4073.0, 4101.0, 4072.0, 4100.5)]
    ctx3 = mk(rows3)
    assert tp3.void_levels(ctx3, side(ctx3), 15, p, 4060.0, {}) == []
    assert sm2.HITS["void_legs"] >= 1


# --- L13-sweep-low-measured-move (109) + LLT3-impulse-retrace-expansion (178) -----------------------------------------------------------------------

def _mm_ctx(cf=None):
    # L1 4000 (a swing low), H1 4030, retrace to the higher low L2 4010 (the sweep), back up
    closes = [4008, 4004, 4001, 4000.5, 4006, 4015, 4024, 4030, 4024, 4016, 4011, 4010.5, 4016, 4020, 4022]
    rows = _walk(closes, 0.3)
    rows[3] = (4001.0, 4002.0, 4000.0, 4000.5)
    rows[7] = (4024.0, 4030.0, 4023.5, 4029.0)
    rows[8] = (4029.0, 4029.5, 4023.0, 4024.0)
    rows[11] = (4011.0, 4012.0, 4010.0, 4010.5)
    return mk(rows, cf)


def test_measured_move_reanchor():
    ctx = _mm_ctx()
    sd = side(ctx)
    p = pk(mm_targets=True, mm_anchor="reanchor")
    sw = dict(ext=4010.0, ext_i=11)
    out = tp3.mm_levels(ctx, sd, 14, p, sw, 4022.0, 4013.0, 4013.0)
    assert out == [(4040.0, "proj")]                                       # L1 4000, H1 4030, L2 4010: T = 4010 + 30
    assert sm2.HITS["mm_reanchor"] >= 1


def test_measured_move_reanchor_htf_kind_and_guards():
    ctx = _mm_ctx(conf([(-1, 4043.0, 4039.5, np.inf, 0, "1h")], tfs=("1h",)))
    sd = side(ctx)
    p = pk(mm_targets=True, mm_anchor="reanchor")
    assert tp3.mm_levels(ctx, sd, 14, p, dict(ext=4010.0, ext_i=11), 4022.0, 4013.0, 4013.0) == [(4040.0, "proj_htf")]     # within 1 pt of an HTF array
    # no earlier lower low: no re-anchored move
    assert tp3.mm_levels(ctx, sd, 14, p, dict(ext=3999.0, ext_i=11), 4022.0, 4013.0, 4013.0) == []
    # the built anchors are untouched by the new values
    assert Params(mm_targets=True, mm_anchor="leg").mm_anchor == "leg"


def test_impulse_expansion_target():
    ctx = _mm_ctx()
    sd = side(ctx)
    p = pk(mm_targets=True, mm_anchor="impulse")
    out = tp3.mm_levels(ctx, sd, 14, p, dict(ext=4000.0, ext_i=3), 4020.0, 4010.0, 4005.0)       # A 4000, B 4020, C = the entry 4010
    assert out == [(4030.0, "proj")]
    assert tp3.mm_levels(ctx, sd, 14, p, dict(ext=4000.0, ext_i=3), 3999.0, 4010.0, 4005.0) == []


# --- X1-bullish-objective-order (110) -------------------------------------------------------------------------------------------------------------

def test_ob_entry_objective_order():
    rows = [(4100.0, 4102.0, 4098.0, 4101.0), (4101.0, 4104.0, 4100.0, 4103.0), (4103.0, 4107.0, 4102.0, 4106.0), (4106.0, 4109.0, 4105.0, 4108.0),
            (4111.0, 4116.0, 4110.0, 4115.0), (4114.0, 4114.5, 4108.0, 4109.0), (4109.0, 4111.0, 4104.0, 4105.0), (4105.0, 4107.0, 4101.0, 4102.0), (4102.0, 4104.0, 4099.0, 4100.0)]
    cf = conf([(-1, 4135.0, 4130.0, np.inf, 1, "1h"), (-1, 4140.0, 4136.0, np.inf, 0, "1h")], tfs=("1h",))
    ctx = mk(rows, cf)
    sd = side(ctx)
    p = pk(ob_target_order=True)
    out = tp3.ob_order_levels(ctx, sd, 8, p, 4100.0, dict(entry_kind="ob_pre"))
    assert out == [(4110.0, "array"), (4116.25, "exact"), (4130.0, "array")]
    assert tp3.ob_order_levels(ctx, sd, 8, p, 4100.0, dict(entry_kind="fvg")) == []                       # an FVG entry keeps its own targets
    # the candle is behind the entry / already taken: nothing
    assert tp3.ob_order_levels(ctx, sd, 8, p, 4112.0, dict(entry_kind="ob_pre")) == []
    # exit prices: T1 early by exit_before_pts, the buy stops exactly
    assert S._exit_px(4116.25, "exact", p) == 4116.25 and S._exit_px(4110.0, "array", p) == 4109.5


# --- L3-daily-target-weekly-beyond (119) ----------------------------------------------------------------------------------------------------------

def test_weekly_beyond_tag():
    ctx = mk(flat(12), pw=(4140.0, 4000.0), pm_=(4300.0, 3900.0))
    sd = side(ctx)
    p = pk(weekly_beyond_mode="tag")
    keep = [(4100.25, "pool")]                                              # PDH 4100 is T1
    assert tp3.weekly_beyond(ctx, sd, 8, p, 4090.0, keep) == (True, True)
    assert tp3.weekly_beyond(ctx, sd, 8, p, 4090.0, [(4150.25, "pool")]) == (False, True)          # the PWH is not beyond a T1 of 4150
    ctx2 = mk(flat(12), pw=None, pm_=None)
    assert tp3.weekly_beyond(ctx2, side(ctx2), 8, p, 4090.0, keep) == (False, False)
    # a weekly array beyond T1 also counts
    cf = conf([(-1, 4160.0, 4150.0, np.inf, 0, "W")], tfs=("W",))
    ctx3 = mk(flat(12), cf)
    assert tp3.weekly_beyond(ctx3, side(ctx3), 8, p, 4090.0, keep)[0] is True
    kw = dict(ctx=ctx, sd=sd, sw=dict(ext=4096.0, ext_i=2), i=8, session="AM", entry=4090.0, risk=4.0, keep=keep, keep_full=keep, draw=4100.25, final_T=False, tags={}, st={}, locked=False, fixed=None)
    lvt = []
    assert tp3.late(p=p, lvt=lvt, **kw)[0] is None and "weekly_beyond" in lvt and "monthly_beyond" in lvt
    lvt2 = []
    assert tp3.late(p=pk(weekly_beyond_mode="require"), **dict(kw, ctx=ctx2, sd=side(ctx2), lvt=lvt2))[0] == "x_no_weekly_beyond"
    assert tp3.late(p=pk(weekly_beyond_mode="require"), **dict(kw, lvt=[]))[0] is None


# --- new-double-top-projection (126) --------------------------------------------------------------------------------------------------------------

def _dt_rows(extra=None):
    """5m bars 09:30 -> 14:00: 1h highs 4090 / 4100 / 4085 / 4099.75 / 4082 (the lowest low between the peaks 4080)."""
    peaks = [4090.0, 4100.0, 4085.0, 4099.75, 4082.0]
    rows = []
    for hr, pk_ in enumerate(peaks):
        base = pk_ - 5.0
        for m in range(12):
            top = pk_ if m == 5 else base + 1.0
            low = base
            rows.append((base, top, low, base))
    return rows + (extra or [])


def test_double_top_projection():
    pool, proj = L.double_top_proj(np.array([4100.0, 4090.0, 4099.75]), np.array([4090.0, 4080.0, 4090.0]), (0, 2))
    assert (pool, proj) == (4100.0, 4120.0)
    rows = _dt_rows()
    ctx = mk(rows)
    sd = side(ctx)
    p = pk(dt_proj=True)
    i = len(rows) - 1
    # 09:30-09:55 is the 09:00 bucket, 10:00.. the next hours: five completed buckets
    assert [x[:2] for x in tp3.double_tops(ctx, sd, i, p, 4050.0)] == [(4100.0, 4120.0)]
    st = {}
    out = tp3.dt_levels(ctx, sd, i, p, 4050.0, st)
    assert (4120.0, "proj") in out and (4100.0, "pool_eq") in out and not st.get("dt_reached")
    # the pool traded one tick through: booked, the projection stays live
    rows_b = _dt_rows([(4085.0, 4100.5, 4084.0, 4090.0)])
    ctx_b = mk(rows_b)
    out_b = tp3.dt_levels(ctx_b, side(ctx_b), len(rows_b) - 1, p, 4050.0, {})
    assert out_b == [(4120.0, "proj")]
    # the projection reached: no rung, the same-direction side is done
    rows_r = _dt_rows([(4085.0, 4121.0, 4084.0, 4119.0), (4119.0, 4119.5, 4110.0, 4112.0)])
    ctx_r = mk(rows_r)
    st_r = {}
    assert tp3.dt_levels(ctx_r, side(ctx_r), len(rows_r) - 1, p, 4050.0, st_r) == [] and st_r["dt_reached"]
    kw = dict(ctx=ctx_r, sd=side(ctx_r), sw=dict(ext=4096.0, ext_i=2), i=len(rows_r) - 1, session="AM", entry=4100.0, risk=4.0, keep=[(4130.0, "pool")], keep_full=[(4130.0, "pool")], draw=4130.0, final_T=False,
              lvt=[], tags={}, st=st_r, locked=False, fixed=None)
    assert tp3.late(p=p, **kw)[0] == "x_dt_done" and tp3.late(p=pk(), **kw)[0] is None
    # a short (double bottom) is the same code on mirrored prices
    ctx_s = mk([(-a, -c, -b, -d) for a, b, c, d in rows])
    assert tp3.dt_levels(ctx_s, side(ctx_s, -1), len(rows) - 1, p, 4050.0, {}) == out


# --- new-60day-range-grades (131) + L14-target-past-eq (132) -------------------------------------------------------------------------------------

def _range_hist(lo=4000.0, hi=4800.0, n=60, wick=0.0):
    out = []
    for k in range(n):
        d = pd.Timestamp("2026-04-01", tz=NY) + pd.Timedelta(days=k)
        idx = pd.date_range(d + pd.Timedelta(hours=9, minutes=30), periods=3, freq="5min")
        o_, c_ = (lo, lo + 100.0) if k == 0 else ((hi - 100.0, hi) if k == 1 else (4400.0, 4400.0))
        out.append(pd.DataFrame({"open": [o_, o_, o_], "high": [max(o_, c_) + wick] * 3, "low": [min(o_, c_) - wick] * 3, "close": [c_, c_, c_]}, index=idx))
    return out


def test_60day_grades():
    ctx = mk(flat(12, 4410.0), hist=_range_hist())
    sd = side(ctx)
    p = pk(grades60=True)
    assert tp3.range60(ctx, p) == (4000.0, 4800.0)
    assert tp3.range60(ctx, replace(p, grades60_src="wick")) == (4000.0, 4800.0)
    assert tp3.range60(mk(flat(3), hist=_range_hist(n=10)), p) is None
    assert tp3.range60(mk(flat(3), hist=_range_hist(wick=30.0)), replace(p, grades60_src="wick")) == (3970.0, 4830.0)
    assert tp3.grade_levels(4000.0, 4800.0) == [4000.0, 4100.0, 4200.0, 4300.0, 4400.0, 4500.0, 4600.0, 4700.0, 4800.0]
    lvt, st = [], {}
    out = tp3.grade_rungs(ctx, sd, 8, p, 4410.0, 4410.0, st, lvt)
    assert [v for v, _ in out] == [4500.0, 4600.0, 4700.0, 4800.0] and all(k == "grade" for _, k in out) and "grade4" in lvt
    # an entry outside the range gets nothing
    ctx2 = mk(flat(12, 4900.0), hist=_range_hist())
    assert tp3.grade_rungs(ctx2, side(ctx2), 8, p, 4900.0, 4900.0, {}, []) == []
    # sitting above the 4400 grade from the start is not a crossing: the grades stay stepping stones (no final); a close above it after one at or below it is
    assert not st.get("grade_through")
    rows_x = [(4395.0, 4396.0, 4394.0, 4395.0)] * 6 + [(4396.0, 4412.0, 4395.0, 4410.0)] + [(4410.0, 4412.0, 4408.0, 4410.0)] * 5
    ctx_x = mk(rows_x, hist=_range_hist())
    st_x, lvt_x = {}, []
    tp3.grade_rungs(ctx_x, side(ctx_x), 11, p, 4410.0, 4410.0, st_x, lvt_x, dict(ext=4394.0, ext_i=2))
    assert st_x["grade_through"] and "sub_disc" in lvt_x and "top_seg" not in lvt_x
    rows_b = rows_x[:6] + [(4396.0, 4412.0, 4395.0, 4410.0), (4410.0, 4411.0, 4390.0, 4396.0)] + [(4396.0, 4397.0, 4395.0, 4396.0)] * 4        # closed back below: a reaction
    ctx_b = mk(rows_b, hist=_range_hist())
    st_b = {}
    tp3.grade_rungs(ctx_b, side(ctx_b), 11, p, 4410.0, 4410.0, st_b, [], dict(ext=4394.0, ext_i=2))
    assert not st_b.get("grade_through")
    # range-bound gate: the fixture's 60 sessions net moved 400 of an 800 range (drr_net_frac 0.6: range-bound); a trending history is not
    p6 = replace(p, drr_net_frac=0.6)
    assert tp3.range_bound60(ctx_x, p6) and tp3.grade_rungs(ctx_x, side(ctx_x), 11, replace(p6, grades60_range_only=True), 4410.0, 4410.0, {}, [])
    hs = _range_hist()
    hs[-1] = hs[-1].assign(close=4790.0)
    ctx_t = mk(rows_x, hist=hs)
    assert not tp3.range_bound60(ctx_t, p6) and tp3.grade_rungs(ctx_t, side(ctx_t), 11, replace(p6, grades60_range_only=True), 4410.0, 4410.0, {}, []) == []
    st = dict(st, grade_through=True)
    # the final target is the next grade unless a nearer pool exists
    kw = dict(ctx=ctx, sd=sd, sw=dict(ext=4400.0, ext_i=2), i=8, session="AM", entry=4410.0, risk=4.0, keep_full=[], draw=4700.0, final_T=False, lvt=[], tags={}, locked=False, fixed=None)
    keep = [(4455.0, "array"), (4560.0, "array"), (4650.0, "array")]
    why, k2, draw, _ = tp3.late(p=p, keep=keep, st=dict(st), **kw)
    assert why is None and k2[-1] == (S._exit_px(4500.0, "grade", p), "grade") and draw == 4499.5 and k2[0] == (4455.0, "array")
    keep_p = [(4455.0, "array"), (4480.25, "pool"), (4650.0, "array")]
    why, k3, draw, _ = tp3.late(p=p, keep=keep_p, st=dict(st), **dict(kw, lvt=[]))
    assert k3 == keep_p                                                   # the pool at 4480 is nearer than the 4500 grade


def test_target_first_array_below_eq60():
    # a short (side space: mirrored) from the premium: entry 4430 above the EQ 4400, a weekly BISI 4380-4390 below
    rows = [(4430.0, 4431.0, 4429.0, 4430.0)] * 12
    cf = conf([(1, 4390.0, 4380.0, np.inf, 0, "W"), (1, 4295.0, 4285.0, np.inf, 0, "W")], tfs=("W",))
    ctx = mk(rows, cf, hist=_range_hist())
    sd = side(ctx, -1)
    p = pk(target_past_eq60=True)
    v = tp3.past_eq_final(ctx, sd, 8, p, sd.x(4430.0), {})
    assert v == -4390.0                                                    # final 4390 in real prices
    # an array that holds a quadrant / eighth 50% line (4350 = 43.75 % of 4000-4800) outranks the nearer one
    cf_q = conf([(1, 4390.0, 4380.0, np.inf, 0, "W"), (1, 4355.0, 4345.0, np.inf, 0, "W")], tfs=("W",))
    ctx_q = mk(rows, cf_q, hist=_range_hist())
    h0 = dict(sm2.HITS)
    assert tp3.past_eq_final(ctx_q, side(ctx_q, -1), 8, p, sd.x(4430.0), {}) == -4355.0 and sm2.HITS.get("past_eq_quad_priority", 0) > h0.get("past_eq_quad_priority", 0)
    # a long from the discount side mirrors it: entry 4370, a bearish weekly array 4410-4420 above the EQ
    rows_l = [(4370.0, 4371.0, 4369.0, 4370.0)] * 12
    cf_l = conf([(-1, 4420.0, 4410.0, np.inf, 0, "W")], tfs=("W",))
    ctx_l = mk(rows_l, cf_l, hist=_range_hist())
    assert tp3.past_eq_final(ctx_l, side(ctx_l), 8, p, 4370.0, {}) == 4410.0
    # an entry on the other side of the EQ: no pick
    assert tp3.past_eq_final(ctx_l, side(ctx_l), 8, p, 4450.0, {}) is None
    # it is the final target in the ladder
    kw = dict(ctx=ctx_l, sd=side(ctx_l), sw=dict(ext=4360.0, ext_i=2), i=8, session="AM", entry=4370.0, risk=4.0, keep=[(4380.0, "array"), (4440.0, "array")], keep_full=[], draw=4440.0, final_T=False,
              lvt=[], tags={}, st={}, locked=False, fixed=None)
    why, keep, draw, _ = tp3.late(p=p, **kw)
    assert why is None and keep[-1] == (4409.5, "array") and keep[0] == (4380.0, "array") and "past_eq60_final" in kw["lvt"]


# --- L13-cc-extension-projections (134) -----------------------------------------------------------------------------------------------------------

def test_cc_extension_levels():
    out = tp3.ext_multiples(4100.0, 4060.0, (1.27, 1.68))
    assert out == pytest.approx([4049.2, 4032.8])
    assert tp3.ext_multiples(4100.0, 4060.0, (1.27, 1.62)) == pytest.approx([4049.2, 4035.2])
    # stop_run: the swing high before the sweep -> the sweep low, extensions kept only at an opposing array of a lower timeframe
    rows = _walk([4050, 4054, 4060, 4056, 4046, 4041, 4040.5, 4046, 4052, 4058], 0.3)
    rows[2] = (4056.0, 4060.0, 4055.0, 4059.0)                              # the swing high 4060
    rows[3] = (4059.0, 4059.5, 4054.0, 4056.0)
    cf = conf([(-1, 4068.0, 4064.0, np.inf, 0, "15m")], tfs=("15m",))
    ctx = mk(rows, cf)
    sd = side(ctx)
    p = pk(proj_ext_anchor="stop_run", sd_htf_tol=1.0)
    sw = dict(ext=4040.0, ext_i=6)
    out = tp3.ext_levels(ctx, sd, 9, p, sw, 4045.0)
    assert [(round(v, 2), k) for v, k in out] == [(4065.4, "proj")]          # 4040 + 1.27 x 20 sits in the array; 1.62 (4072.4) does not
    p2 = replace(p, proj_ext2=1.68)
    assert tp3.ext_levels(ctx, sd, 9, p2, sw, 4045.0) == out
    ctx_n = mk(rows)                                                         # no confluence table -> nothing
    assert tp3.ext_levels(ctx_n, side(ctx_n), 9, p, sw, 4045.0) == []


def test_cc_extension_midweek_anchor():
    wed = date(2026, 6, 24)
    mon = pd.date_range("2026-06-22 09:30", periods=3, freq="5min", tz=NY)
    hist = [pd.DataFrame({"open": [4090.0] * 3, "high": [4100.0, 4100.0, 4098.0], "low": [4085.0] * 3, "close": [4090.0] * 3}, index=mon)]       # Monday: the week's high 4100
    rows = [(4075.0, 4076.0, 4070.0, 4072.0), (4072.0, 4073.0, 4060.0, 4061.0), (4061.0, 4064.0, 4060.5, 4063.0), (4063.0, 4066.0, 4062.0, 4065.0)]
    cf = conf([(-1, 4054.0, 4050.0, np.inf, 0, "1h")], tfs=("1h",))
    # a bullish day-mirror: the template of the spec in side space is its mirror; here the up version: Wednesday's LOW 4060 (start), the week's high 4100 (end)
    ctx = mk(rows, cf, day=wed, hist=hist)
    sd = side(ctx)
    p = pk(proj_ext_anchor="midweek", proj_ext2=1.68, sd_htf_tol=1.0)
    out = tp3.ext_levels(ctx, sd, 3, p, dict(ext=4060.0, ext_i=1), 4065.0)
    # start 4060, end 4100: 4060 + 1.27 x 40 = 4110.8; 4060 + 1.68 x 40 = 4127.2 - neither sits in the 4050-4054 array
    assert out == []
    cf2 = conf([(-1, 4128.0, 4126.0, np.inf, 0, "1h")], tfs=("1h",))
    ctx2 = mk(rows, cf2, day=wed, hist=hist)
    out2 = tp3.ext_levels(ctx2, side(ctx2), 3, p, dict(ext=4060.0, ext_i=1), 4065.0)
    assert [(round(v, 1), k) for v, k in out2] == [(4127.2, "proj")]
    # Tuesday: not yet (the Wednesday anchor needs Wednesday)
    ctx3 = mk(rows, cf2, day=date(2026, 6, 23), hist=hist)
    assert tp3.ext_levels(ctx3, side(ctx3), 3, p, dict(ext=4060.0, ext_i=1), 4065.0) == []


# --- new-swing-target-breaker-cap (140) -----------------------------------------------------------------------------------------------------------

def _daily_hist(closes):
    out = []
    for k, c_ in enumerate(closes):
        d = pd.Timestamp("2026-05-01", tz=NY) + pd.Timedelta(days=k)
        idx = pd.date_range(d + pd.Timedelta(hours=9, minutes=30), periods=2, freq="5min")
        out.append(pd.DataFrame({"open": [c_ - 1.0] * 2, "high": [c_ + 2.0] * 2, "low": [c_ - 3.0] * 2, "close": [c_] * 2}, index=idx))
    return out


def test_daily_breaker_caps_ladder(monkeypatch):
    zone = L.Zone("bear", 4170.0, 4150.0, 5, 4)
    monkeypatch.setattr(tp3.L, "breakers", lambda o, h, l, c, n=2, mode="range": [zone])
    closes = [4100, 4105, 4120, 4130, 4140, 4150, 4120, 4125, 4130, 4128]
    ctx = mk(flat(12), hist=_daily_hist(closes))
    sd = side(ctx)
    p = pk(daily_breaker_cap=True)
    assert tp3.daily_breaker(ctx, sd, 8, p, 4000.0) == 4150.0
    # the raw ladder: rungs above 4150 removed, the breaker's low is the final target
    lvt, st = [], {}
    out = tp3.raw_post(ctx, sd, 8, p, "AM", 4100.0, 4.0, 4100.0, dict(ext=4096.0, ext_i=2), 4105.0, [(4120.0, "pool"), (4160.0, "array"), (4200.0, "pool")], lvt, {}, st)
    assert out == [(4120.0, "pool"), (4150.0, "array")] and st["db_cap"] == 4150.0 and "daily_breaker_cap" in lvt
    # a daily close above the breaker: restored
    ctx2 = mk(flat(12), hist=_daily_hist(closes[:7] + [4172, 4130, 4128]))
    assert tp3.daily_breaker(ctx2, side(ctx2), 8, p, 4000.0) is None
    out2 = tp3.raw_post(ctx2, side(ctx2), 8, p, "AM", 4100.0, 4.0, 4100.0, dict(ext=4096.0, ext_i=2), 4105.0, [(4120.0, "pool"), (4160.0, "array"), (4200.0, "pool")], [], {}, {})
    assert [v for v, _ in out2] == [4120.0, 4160.0, 4200.0]
    # a breaker already behind the entry / too little history: none
    assert tp3.daily_breaker(ctx, sd, 8, p, 4160.0) is None
    assert tp3.daily_breaker(mk(flat(12), hist=_daily_hist(closes[:4])), sd, 8, p, 4000.0) is None
    assert tp3.cap_post(ctx, sd, 8, p, 4000.0, {}) == 4150.0 and tp3.cap_post(ctx, sd, 8, pk(), 4000.0, {}) is None


def test_daily_breaker_real_detector_runs():
    rng = np.random.default_rng(3)
    c = np.cumsum(rng.normal(0, 8, 60)) + 4100
    ctx = mk(flat(12), hist=_daily_hist(list(c)))
    out = tp3.daily_breaker(ctx, side(ctx), 8, pk(daily_breaker_cap=True), 3000.0)
    assert out is None or out > 3000.0


# --- LLT3-target-confluence-projection-adr-array (156) + LLT3-adr5-target-ladder (159) -------------------------------------------------------------

def _adr_ctx(cf, last_high=4041.0, **kw):
    rows = [(4010.0, 4012.0, 4000.0, 4008.0)] + [(4008.0, 4015.0, 4006.0, 4012.0)] * 5 + [(4012.0, last_high, 4010.0, 4030.0)] * 2
    kw.setdefault('opens', {})
    return mk(rows, cf, hist=hist_days(n=6, rng=40.0), **kw)


def test_adr_projection_array_convergence():
    cf = conf([(-1, 4044.0, 4038.0, np.inf, 0, "1h")], tfs=("1h",))
    ctx = _adr_ctx(cf)
    sd = side(ctx)
    p = pk(adr_conv_target=True)
    st, lvt = {}, []
    lv = [(4020.0, "pool"), (4040.0, "sd"), (4065.0, "array")]
    out = tp3.raw_post(ctx, sd, 7, p, "AM", 4020.0, 4.0, 4015.0, dict(ext=4001.0, ext_i=0), 4030.0, lv, lvt, {}, st)
    assert st["adr_final"] == 4040.0 and (4040.0, "proj_htf") in out
    kw = dict(ctx=ctx, sd=sd, sw=dict(ext=4001.0, ext_i=0), i=7, session="AM", entry=4020.0, risk=4.0, keep_full=[], lvt=lvt, tags={}, locked=False, fixed=None)
    keep = [(4025.0, "pool"), (4039.75, "sd"), (4064.5, "array")]
    why, k2, draw, _ = tp3.late(p=p, keep=keep, draw=4064.5, final_T=False, st=st, **kw)
    assert why is None and k2[-1][1] == "proj_htf" and abs(TP._raw(k2[-1][0], "proj_htf", p) - 4040.0) < 1e-9 and k2[:1] == [(4025.0, "pool")] and "adr_conv_final" in lvt
    # no SD level at the array: nothing; after adr_conv_last: nothing
    st2 = {}
    tp3.raw_post(ctx, sd, 7, p, "AM", 4020.0, 4.0, 4015.0, dict(ext=4001.0, ext_i=0), 4030.0, [(4020.0, "pool"), (4052.0, "sd")], [], {}, st2)
    assert "adr_final" not in st2
    st3 = {}
    tp3.raw_post(ctx, sd, 7, replace(p, adr_conv_last=500), "AM", 4020.0, 4.0, 4015.0, dict(ext=4001.0, ext_i=0), 4030.0, lv, [], {}, st3)
    assert "adr_final" not in st3
    # the array must hold the projected ADR high
    cf2 = conf([(-1, 4064.0, 4058.0, np.inf, 0, "1h")], tfs=("1h",))
    st4 = {}
    ctx4 = _adr_ctx(cf2)
    tp3.raw_post(ctx4, side(ctx4), 7, p, "AM", 4020.0, 4.0, 4015.0, dict(ext=4001.0, ext_i=0), 4030.0, lv, [], {}, st4)
    assert "adr_final" not in st4


def test_adr_ladder_ext():
    cf = conf([(-1, 4055.0, 4051.0, np.inf, 0, "1h")], tfs=("1h",))
    ctx = _adr_ctx(cf, last_high=4041.0)
    sd = side(ctx)
    p = pk(adr_target=True, adr_frac=1.0, adr_t2_htf=True, adr_ext=True)
    out = tp3.adr_levels(ctx, sd, 7, p, 4020.0, 4020.0, {})
    vals = {(round(v, 2), k) for v, k in out}
    assert (4051.0, "array") in vals and (4050.8, "proj") in vals                      # T2 = the 1h array; ADR_lo + 1.27 x 40 within 1 pt of its near edge
    assert not any(abs(v - 4064.8) < 0.01 for v, _ in out)                              # 1.62 x 40 = 4064.8: no array there
    # before price traded beyond the ADR level (4040) there is no extension
    ctx0 = _adr_ctx(cf, last_high=4030.0)
    out0 = tp3.adr_levels(ctx0, side(ctx0), 7, p, 4020.0, 4020.0, {})
    assert (4050.8, "proj") not in {(round(v, 2), k) for v, k in out0}
    # the London-low anchor
    ctxl = _adr_ctx(cf, sess={"london": (4030.0, 3990.0, 300)})
    assert tp3.adr_low(ctxl, side(ctxl), 7, replace(p, adr_anchor="london_low")) == 3990.0 and tp3.adr_low(ctxl, side(ctxl), 7, p) == 4000.0
    assert tp3.adr_low(ctxl, side(ctxl, -1), 7, replace(p, adr_anchor="london_low")) == -4030.0
    # the built adr_target rung uses the anchor and the kind that carries the ADR buffer
    ctx2 = _adr_ctx(None, sess={"london": (4030.0, 3990.0, 300)})
    got = TP.extra_sources(ctx2, side(ctx2), 7, replace(p, adr_before_frac=0.15, adr_anchor="london_low"), dict(ext=4001.0, ext_i=0), 4020.0, 4.0, 4030.0, 4010.0, [], [], None)
    assert (4030.0, "adr") in got


# --- LLT3-pm-measured-move-am-leg (168) -----------------------------------------------------------------------------------------------------------

def _day_rows(am=(4000.0, 4030.0), lunch_low=4012.0, pm_low=4020.0, pm_end=14.0):
    """5m bars 09:30 -> pm_end: AM (09:30-12:00) low/high am, lunch low `lunch_low`, a PM low `pm_low` at 13:35."""
    rows = []
    n = int((pm_end * 60 - 570) / 5)
    for k in range(n):
        m = 570 + 5 * k
        if m < 720:
            v = am[0] + (am[1] - am[0]) * (k / 29.0)
            rows.append((v, v + 1.0, v - 1.0, v) if k not in (0, 29) else (v, am[1] if k == 29 else v + 1.0, am[0] if k == 0 else v - 1.0, v))
        elif m < 810:
            rows.append((lunch_low + 8.0, lunch_low + 9.0, lunch_low if m == 750 else lunch_low + 6.0, lunch_low + 8.0))
        else:
            rows.append((pm_low + 6.0, pm_low + 7.0, pm_low if m == 815 else pm_low + 5.0, pm_low + 6.0))
    return rows


def test_pm_equal_leg_target():
    rows = _day_rows()
    ctx = mk(rows)
    sd = side(ctx)
    p = pk(pm_am_leg=True)
    i = len(rows) - 1
    k_pm = S._idx_at(ctx, 810)
    sw = dict(ext=4020.0, ext_i=k_pm + 1)
    assert tp3.pm_leg_levels(ctx, sd, i, p, sw, 4030.0, "PM") == [(4050.0, "proj")]
    assert tp3.pm_leg_levels(ctx, sd, i, p, sw, 4030.0, "AM") == []
    # a lunch low under the AM low: the AM leg was not held
    ctx2 = mk(_day_rows(lunch_low=3995.0))
    assert tp3.pm_leg_levels(ctx2, side(ctx2), i, p, sw, 4030.0, "PM") == []
    # no sweep in the PM: the PM swing low stands in
    out = tp3.pm_leg_levels(ctx, sd, i, p, dict(ext=3990.0, ext_i=3), 4030.0, "PM")
    assert out == [(4050.0, "proj")]
    # a short mirrors it
    ctx_s = mk([(-a, -c, -b, -d) for a, b, c, d in rows])
    assert tp3.pm_leg_levels(ctx_s, side(ctx_s, -1), i, p, dict(ext=4020.0, ext_i=k_pm + 1), 4030.0, "PM") == [(4050.0, "proj")]


# --- LLT3-consolidation-day-overnight-targets (169) -----------------------------------------------------------------------------------------------

def _overnight_rows():
    """04:00 -> 10:00: an overnight range 4000-4012 (a 5m pivot high 4012 at 05:30), London 4015 / 3998, the open at 4005 rallying into 10:00."""
    rows = []
    for k in range((600 - 240) // 5 + 1):
        m = 240 + 5 * k
        if m < 570:
            hi = 4012.0 if m == 330 else 4005.0 + (1.0 if k % 7 == 3 else 0.0)
            rows.append((4003.0, hi, 4000.0 if m == 420 else 4001.5, 4003.5))
        else:
            rows.append((4005.0, 4006.5 + 0.02 * (k - 66), 4004.5, 4006.0))
    return rows


def test_consol_day_overnight_pools_only():
    rows = _overnight_rows()
    dplan = SimpleNamespace(tags=("consol_day",), info={})
    ctx = mk_at(rows, start="2026-06-23 04:00", dplan=dplan, sess={"london": (4015.0, 3998.0, 300)})
    sd = sd_of(ctx)
    i = len(rows) - 1
    p = pk(consol_overnight_targets=True)
    keep = [(4009.0, "array"), (4030.25, "pool"), (4045.0, "array")]
    kw = dict(ctx=ctx, sd=sd, sw=dict(ext=4004.0, ext_i=60), i=i, session="AM", entry=4006.0, risk=1.0, keep=keep, keep_full=keep, draw=4030.25, final_T=False, lvt=[], st={}, locked=False, fixed=None)
    tags = {}
    why, k2, draw, _ = tp3.late(p=p, tags=tags, **kw)
    assert why is None and k2 == [(4012.25, "pool")] and tags["single_exit"] and draw == 4012.25          # the nearest overnight pool: the 05:30 pivot / overnight high 4012
    # not a consolidation day: untouched
    ctx_n = mk_at(rows, start="2026-06-23 04:00", dplan=SimpleNamespace(tags=(), info={}), sess={"london": (4015.0, 3998.0, 300)})
    why, k3, _, _ = tp3.late(p=p, tags={}, **dict(kw, ctx=ctx_n, sd=sd_of(ctx_n), lvt=[]))
    assert why is None and k3 == keep
    # PM / after 11:00: no trade
    assert tp3.late(p=p, tags={}, **dict(kw, session="PM", lvt=[]))[0] == "x_consol_am_only"
    # the pools are taken: no target
    rows2 = rows[:-1] + [(4005.0, 4016.0, 4004.5, 4015.0)]
    ctx2 = mk_at(rows2, start="2026-06-23 04:00", dplan=dplan, sess={"london": (4015.0, 3998.0, 300)})
    assert tp3.late(p=p, tags={}, **dict(kw, ctx=ctx2, sd=sd_of(ctx2), lvt=[]))[0] == "x_consol_no_overnight"


# --- LLT3-wide-or-bias-end (170) ------------------------------------------------------------------------------------------------------------------

def _or_rows(hi=4040.0, lo=4000.0):
    rows = [(4030.0, hi, 4020.0, 4025.0)] + [(4025.0, 4030.0, 4015.0, 4018.0)] * 4 + [(4018.0, 4022.0, lo, 4003.0)] + [(4003.0, 4008.0, 4001.0, 4005.0)] * 5     # 09:30-10:25: it opened up, ended down
    return rows + [(4005.0, 4009.0, 4002.0, 4006.0)] * 3


def test_wide_or_bias_end(monkeypatch):
    rows = _or_rows()
    hist = hist_days(n=20, rng=12.0)
    ctx = mk(rows, hist=hist)
    sd = side(ctx)
    p = pk(wide_or_draw=True, htf_bias="draw")
    i = 11
    assert tp3.or_wide(ctx, sd, i, p) == (4040.0, 4000.0)
    assert tp3.or_wide(ctx, sd, 9, p) is None                                  # the OR is not complete
    narrow = mk([(4005.0, 4012.0, 4000.0, 4006.0)] * 14, hist=hist)
    assert tp3.or_wide(narrow, side(narrow), i, p) is None                      # 12 pts is no wider than the median
    assert tp3.or_wide(mk(rows, hist=hist_days(n=6)), sd, i, p) is None       # < 10 sessions of history
    monkeypatch.setattr(S._BD, "want_at", lambda ctx_, p_, session, i_: 1)
    keep = [(4012.0, "array"), (4090.0, "array")]
    kw = dict(ctx=ctx, sd=sd, sw=dict(ext=4001.0, ext_i=5), i=i, session="AM", entry=4006.0, risk=2.0, keep=keep, keep_full=keep, draw=4090.0, final_T=False, lvt=[], tags={}, st={}, locked=False, fixed=None)
    why, k2, draw, _ = tp3.late(p=p, **kw)
    assert why is None and k2[-1] == (4040.25, "pool") and draw == 4040.25 and k2[0] == (4012.0, "array")
    monkeypatch.setattr(S._BD, "want_at", lambda ctx_, p_, session, i_: -1)
    assert tp3.late(p=p, **dict(kw, lvt=[]))[2] == 4090.0                      # a bearish bias: not this side's draw
    monkeypatch.setattr(S._BD, "want_at", lambda ctx_, p_, session, i_: 0)
    assert tp3.late(p=p, **dict(kw, lvt=[]))[2] == 4090.0                      # no bias, no target from this rule


# --- LLT3-pm-target-am-rejection-block (171) ------------------------------------------------------------------------------------------------------

def test_pm_first_target_am_rejection_block():
    rows = _day_rows(pm_end=14.0)
    k0 = 0
    # AM high 4060 early (bar 6), a lower swing high with a long upper wick later: body 4050, wick 4056
    rows = list(rows)
    for k in range(29):
        rows[k] = (4040.0, 4042.0, 4038.0, 4040.0)
    rows[6] = (4040.0, 4060.0, 4039.0, 4041.0)
    rows[20] = (4048.0, 4056.0, 4047.0, 4050.0)
    for k in (18, 19, 21, 22):
        rows[k] = (4040.0, 4044.0, 4038.0, 4041.0)
    ctx = mk(rows)
    sd = side(ctx)
    p = pk(pm_am_rb=True)
    i = len(rows) - 1
    out = tp3.pm_rb_levels(ctx, sd, i, p, 4045.0, "PM")
    assert out == [(4050.0, "array"), (4056.0, "pool")]
    assert tp3.pm_rb_levels(ctx, sd, i, p, 4045.0, "AM") == []
    assert tp3.pm_rb_levels(ctx, sd, i, p, 4053.0, "PM") == []                  # the body edge is behind the entry
    rows[40] = (4041.0, 4051.0, 4040.0, 4049.0)                                 # traded through the block's body after it formed
    ctx2 = mk(rows)
    assert tp3.pm_rb_levels(ctx2, side(ctx2), i, p, 4045.0, "PM") == []


# --- LLT3-pm-reversal-launch-array-filter (172) ---------------------------------------------------------------------------------------------------

def _launch_ctx(tf):
    # AM rally from 4000 to 4050, the PM decline back to 4040
    rows = []
    for k in range(54):
        m = 570 + 5 * k
        v = 4000.0 + (50.0 * min(k, 29) / 29.0) if m < 720 else (4050.0 - (10.0 * (k - 30) / 23.0))
        rows.append((v, v + 1.0, (4000.0 if k == 0 else v - 1.0), v))
    cf = conf([(1, 4005.0, 3995.0, np.inf, 0, tf)], tfs=(tf,))
    return mk(rows, cf)


@pytest.mark.parametrize("tf,htf", [("D", True), ("4h", True), ("15m", False), ("1h", False)])
def test_pm_reversal_launch_tf(tf, htf):
    ctx = _launch_ctx(tf)
    sd = side(ctx, -1)
    p = pk(pm_launch_filter=True)
    i = len(ctx.c) - 1
    entry = sd.x(4041.0)
    keep = [(sd.x(4020.0), "pool")]
    keep_full = keep + [(sd.x(3980.0), "pool")]
    r = tp3.launch_target(ctx, sd, i, p, entry, 3.0, keep, keep_full)
    assert r is not None
    if htf:
        assert r[1] == pytest.approx(-4005.5) and r[0][-1] == (r[1], "array")           # the array's near edge (the discount array's top 4005)
    else:
        assert r[1] == -3980.0 and r[0][-1] == (-3980.0, "pool")                         # traded through: the ladder runs on to the next pool
    # no array holds the AM low: nothing
    ctx2 = mk([(4000.0 + k, 4001.0 + k, 3999.0 + k, 4000.0 + k) for k in range(54)], conf([(1, 3900.0, 3890.0, np.inf, 0, "D")], tfs=("D",)))
    assert tp3.launch_target(ctx2, side(ctx2, -1), 53, p, -4041.0, 3.0, keep, keep_full) is None


# --- LLT3-session-targets-15m-60m (175) -----------------------------------------------------------------------------------------------------------

def test_session_draw_prefers_15m_60m_array():
    cf = conf([(-1, 4056.0, 4050.0, np.inf, 0, "1h"), (-1, 4200.0, 4190.0, np.inf, 0, "D")], tfs=("1h", "D"))
    ctx = mk(flat(12), cf, day=D0)
    p = pk(session_obj_tf=True)
    got = tp3.lock_cands(ctx, p, 570, 8)
    assert got == [(4050.0, "array", "obj_1h", 0, 0)]                           # the 1h array only (the daily one is not a session objective)
    assert tp3.lock_cands(ctx, pk(), 570, 8) == []
    # a traded-through array is no objective
    ctx2 = mk(flat(8) + [(4000.0, 4052.0, 3999.0, 4001.0)] + flat(3), cf)
    assert tp3.lock_cands(ctx2, p, 570, 11) == []
    lst = [(5.0, 4045.0, "pool", "lunch_high", 1), (10.0, 4050.0, "array", "obj_1h", 0), (12.0, 4052.0, "pool", "pdh1", 1)]
    assert tp3.lock_obj_rank(lst)[0][3] == "obj_1h" and tp3.lock_obj_rank(lst)[1:] == [lst[0], lst[2]]
    # the lock itself (scenario: a 1h SIBI at 4050 and a pool at 4045): see test_caption_gap_tp3b for the engine run


# --- X2-pdarray-exit-at-or-inside-edge (1) --------------------------------------------------------------------------------------------------------

def test_fvg_target_level():
    cf = conf([(-1, 4110.0, 4100.0, np.inf, 0, "4h")], tfs=("4h",))
    ctx = mk(flat(12), cf)
    sd = side(ctx)
    base = pk()
    assert S._exit_px(4100.0, "array", base) == 4099.5                           # before_edge: 0.5 pt before the near edge
    st = {}
    for mode, want in (("before_edge", 4099.5), ("at_edge", 4100.0), ("deep", 4100.0)):
        p = pk(fvg_target_level=mode)
        raw, kinds = [4100.0], ["array"]
        lv = [S._exit_px(4100.0, "array", p)]
        out = tp3.exit_post(ctx, sd, 8, p, 4090.0, raw, kinds, lv, {}) if tp3.exit_on(p) else lv
        assert out == [want], mode
    # a non-gap array level keeps the early exit
    assert tp3.exit_post(ctx, sd, 8, pk(fvg_target_level="at_edge"), 4090.0, [4105.0], ["array"], [4104.5], {}) == [4104.5]
    # the deep runner: a 3-rung ladder, the last rung near + 0.75 x height (7.5)
    p = pk(fvg_target_level="deep")
    keep = [(4092.0, "array"), (4096.0, "pool"), (4100.0, "array")]
    kw = dict(ctx=ctx, sd=sd, sw=dict(ext=4086.0, ext_i=2), i=8, session="AM", entry=4090.0, risk=2.0, keep=keep, keep_full=keep, draw=4100.0, final_T=False, lvt=[], tags={}, locked=False, fixed=None)
    why, k2, draw, _ = tp3.late(p=p, st={}, **kw)
    assert why is None and k2[:2] == keep[:2] and k2[-1] == (4107.5, "array") and draw == 4107.5
    # before_edge / at_edge leave the last rung where it is
    for mode in ("before_edge", "at_edge"):
        assert tp3.late(p=pk(fvg_target_level=mode), st={}, **dict(kw, lvt=[]))[1] == keep
    # E3: with exit_fill_through a bar whose high equals the near edge does not fill an at-edge limit
    pos = dict(level_kinds=["array"])
    q = pk(fvg_target_level="at_edge", exit_fill_through=1.0)
    assert TP.rung_hit(pos, 0, 4100.0, 4100.0, 4099.0, 600, 5, q, q.exit_fill_through * q.tick)[0] is False
    assert TP.rung_hit(pos, 0, 4100.0, 4100.25, 4099.0, 600, 5, q, q.exit_fill_through * q.tick)[0] is True
    # the registry carries an NWOG-like gap and the own-timeframe FVGs
    rows = [(4118.0, 4120.0, 4110.0, 4112.0), (4112.0, 4112.5, 4100.0, 4101.0), (4101.0, 4105.0, 4096.0, 4097.0)] + [(4096.0, 4097.0, 4093.0, 4095.0)] * 6        # a bearish FVG 4105-4110
    ctx_g = mk(rows)
    reg = tp3.gap_registry(ctx_g, side(ctx_g), 8, pk(), 4090.0, {})
    assert reg == [(4105.0, 4107.5, 4110.0)]
    assert tp3.gap_of(4105.0, reg, pk()) == reg[0] and tp3.gap_of(4104.5, reg, pk()) == reg[0] and tp3.gap_of(4100.0, reg, pk()) is None
    out_g = tp3.exit_post(ctx_g, side(ctx_g), 8, pk(fvg_target_level="at_edge"), 4090.0, [4105.0], ["array"], [4104.5], {})
    assert out_g == [4105.0]                                                    # the own-timeframe FVG is a registered gap too


# --- X2-pool-exit-at-or-before (2) ----------------------------------------------------------------------------------------------------------------

def test_pool_exit_modes():
    got = {m: S._exit_px(4290.5, "pool", pk(pool_exit=m)) for m in ("beyond", "at", "before")}
    assert got == {"beyond": 4290.75, "at": 4290.5, "before": 4290.0}
    assert S._exit_px(4290.5, "pool", pk(pool_exit="before", pool_before_ticks=1)) == 4290.25
    assert S._exit_px(4290.5, "pool_eq", pk(pool_exit="at")) == 4290.5
    assert pk(pool_exit="before").pool_beyond_pts == -0.5 and pk(pool_exit="beyond", pool_beyond_pts=1.25).pool_beyond_pts == 1.25        # 006: 1.25 pts beyond is the same switch
    assert TP._raw(4290.0, "pool", pk(pool_exit="before")) == 4290.5
    # the REH cluster: every sub-high exits AT its own price, the highest exits short of its high
    p = pk(pool_exit="before")
    raw, kinds = [4290.5, 4291.0], ["pool_eq", "pool_eq"]
    lv = [S._exit_px(v, k, p) for v, k in zip(raw, kinds)]
    ctx = mk(flat(12))
    out = tp3.exit_post(ctx, side(ctx), 8, p, 4280.0, raw, kinds, lv, {})
    assert out == [4290.5, 4290.5]
    p_at = pk(pool_exit="at")
    assert tp3.exit_post(ctx, side(ctx), 8, p_at, 4280.0, raw, kinds, [S._exit_px(v, k, p_at) for v, k in zip(raw, kinds)], {}) == [4290.5, 4291.0]      # 'at': the highest exits at its own price too
    # FOMC days
    from claude_hf.daytypes import events
    assert "fomc" in events(date(2024, 1, 31)) and "fomc" not in events(date(2024, 1, 30))


def test_pool_exit_fomc_day_runs_before(monkeypatch):
    from mentorship import backtest as B
    x, y = B.synthetic(start="2024-01-29", end="2024-02-02", tf=5, seed=2)
    seen = []
    orig = S._run_day_once

    def spy(df, hist, symbol, p, tf, *a, **k):
        seen.append((df.index[0].date(), p.pool_exit, p.pool_beyond_pts))
        return orig(df, hist, symbol, p, tf, *a, **k)

    monkeypatch.setattr(S, "_run_day_once", spy)
    p = Params(es_pt=0.09, use_bias=False, min_draw_pts=0, leg_pd=0, pool_exit_fomc_before=True)
    hist = []
    for d, df in x.groupby(x.index.date):
        if hist:
            S.run_day(df, hist[-60:], "RW", p, 5)
        hist.append(df)
    by_day = {d: (e, b) for d, e, b in seen}
    assert by_day[date(2024, 1, 31)] == ("before", -0.5) and by_day[date(2024, 1, 30)] == ("beyond", 0.25)
    assert sm2.HITS.get("pool_exit_fomc", 0) >= 1


# --- X2-projection-target-1tick-before (3) --------------------------------------------------------------------------------------------------------

def test_proj_before():
    p = pk(proj_kind=True)
    # a short mirrored: an SD target at 3962.50 exits at 3962.75 (side space: 0.25 before)
    assert S._exit_px(-3962.5, "sd", p) == -3962.75
    assert S._exit_px(4100.0, "proj", p) == 4099.75 and S._exit_px(4100.0, "sd_mm", p) == 4099.75 and S._exit_px(4100.0, "proj_htf", p) == 4099.75
    assert S._exit_px(4100.0, "sd", pk()) == 4099.5                                  # off: exit_before_pts
    assert S._exit_px(4100.0, "array", p) == 4099.5 and S._exit_px(4100.0, "pool", p) == 4100.25
    assert TP._raw(4099.75, "sd", p) == 4100.0
    p1 = pk(proj_kind=True, proj_exit_ticks=1)
    assert S._exit_px(4100.0, "proj", p1) == 4099.75 and S._exit_px(4100.0, "sd", p1) == 4099.75
    assert Params(proj_kind=True, proj_before_pts=0.5, es_pt=1.0).proj_before_pts == 0.5
    # the measured move is a projection when proj_kind is on
    ctx = _mm_ctx()
    got = TP.extra_sources(ctx, side(ctx), 14, pk(mm_targets=True, proj_kind=True), dict(ext=4010.0, ext_i=11), 4013.0, 3.0, 4030.0, 4013.0, [], [], None)
    assert (4050.0, "proj") in got
    # a bar whose low (high, in side space) reaches the exit price fills (touch); one tick short does not
    pos = dict(level_kinds=["sd"])
    assert TP.rung_hit(pos, 0, 4099.75, 4099.75, 4099.0, 600, 5, pk(), 0.0)[0] is True


def test_near_miss_report():
    tr = SimpleNamespace(near_miss=False)
    pos = dict(levels=[4103.0, 4110.0], level_kinds=["array", "sd"], k=1, best=4109.5)
    tp3.near_miss(pos, tr, pk(proj_kind=True))
    assert tr.near_miss is True
    tr2 = SimpleNamespace(near_miss=False)
    tp3.near_miss(dict(pos, best=4105.0), tr2, pk(proj_kind=True))
    assert tr2.near_miss is False
    tr3 = SimpleNamespace(near_miss=False)
    tp3.near_miss(dict(pos, k=2, best=4109.9), tr3, pk(proj_kind=True))                  # every rung filled: no miss
    assert tr3.near_miss is False
    assert "near_miss" in S.Trade.__dataclass_fields__


# --- X2-exit-buffer-range (4) ---------------------------------------------------------------------------------------------------------------------

def test_exit_buffer_grid_preset():
    g = study.exit_buffer_grid()
    assert len(g) == 8 and {(p.exit_before_pts, p.exit_mode) for p in g} == {(b, m) for b in (0.25, 0.5, 1.0, 1.5) for m in ("split", "before")}
    assert all(isinstance(p, Params) for p in g)
    assert study.exit_buffer_grid(Params(risk_pct=0.015))[0].risk_pct == 0.015
    # mode "before": the buffer also hits the pools (070's target was a pool)
    g1 = study.exit_buffer_grid(Params(es_pt=1.0))
    assert S._exit_px(4290.5, "pool", g1[4]) == 4290.25 and S._exit_px(4290.5, "pool", g1[0]) == 4290.75


# --- X2-exit-buffer-before-day-extreme (7) --------------------------------------------------------------------------------------------------------

def test_adr_before():
    cf = conf([(-1, 4040.0, 4033.0, np.inf, 0, "1h")], tfs=("1h",))
    ctx = _adr_ctx(cf, last_high=4020.0)
    sd = side(ctx)
    p = pk(adr_target=True, adr_frac=1.0, adr_before_frac=0.15)
    raw, kinds = [4040.0], ["adr"]
    lv = [S._exit_px(4040.0, "adr", p)]
    out = tp3.exit_post(ctx, sd, 7, p, 4020.0, raw, kinds, lv, {})
    assert out == [4032.5]                                                          # ADR5 40: 6 pts early = 4034; the 60m array edge 4033 minus 0.5 is nearer to price
    ctx2 = _adr_ctx(None, last_high=4020.0)
    assert tp3.exit_post(ctx2, side(ctx2), 7, p, 4020.0, raw, kinds, lv, {}) == [4034.0]
    assert tp3.exit_post(ctx, sd, 7, replace(p, adr_before_frac=0.0), 4020.0, raw, kinds, lv, {}) == lv       # off
    # an array edge outside the buffer's reach is ignored
    cf3 = conf([(-1, 4075.0, 4060.0, np.inf, 0, "1h")], tfs=("1h",))
    ctx3 = _adr_ctx(cf3, last_high=4020.0)
    assert tp3.exit_post(ctx3, side(ctx3), 7, p, 4020.0, raw, kinds, lv, {}) == [4034.0]


# --- X3-new-vs-experienced-partials (34) ----------------------------------------------------------------------------------------------------------

def test_partial_mode_new():
    p = pk(partial_mode="new")
    keep = [(4105.0, "array"), (4110.25, "pool"), (4120.25, "pool")]
    k, fr = tp3.new_trader(p, keep, False)
    assert k == [(4105.0, "array"), (4110.25, "pool")] and fr == pytest.approx([0.8, 0.2])
    assert tp3.new_trader(p, [(4110.25, "pool"), (4120.25, "pool")], False) == ([(4110.25, "pool")], [1.0])
    ctx = mk(flat(12))
    sd = side(ctx)
    tags, lvt = {}, []
    kw = dict(ctx=ctx, sd=sd, sw=dict(ext=4096.0, ext_i=2), i=8, session="AM", entry=4100.0, risk=2.0, keep=keep, keep_full=keep, draw=4110.25, final_T=False, lvt=lvt, st={}, locked=False, fixed=None)
    why, k2, draw, _ = tp3.late(p=p, tags=tags, **kw)
    assert why is None and k2 == keep[:2] and tags["fracs"] == pytest.approx((0.8, 0.2)) and tags["tp3_ladder"] and "partial_new" in lvt
    tags2 = {}
    why, k3, draw, _ = tp3.late(p=pk(partial_mode="terminus"), tags=tags2, **dict(kw, lvt=[]))
    assert k3 == [(4120.25, "pool")] and tags2["fracs"] == (1.0,)
    tags3 = {}
    assert tp3.late(p=pk(partial_mode="experienced"), tags=tags3, **dict(kw, lvt=[]))[1] == keep and "fracs" not in tags3
    # no pool at all: the ladder stays
    only_arrays = [(4105.0, "array"), (4108.0, "array")]
    assert tp3.new_trader(p, only_arrays, False)[0] == only_arrays
    # a locked draw keeps its first rung and the draw
    k4, fr4 = tp3.new_trader(p, [(4102.0, "array"), (4105.0, "array"), (4130.0, "pool")], True)
    assert k4 == [(4102.0, "array"), (4130.0, "pool")] and fr4 == pytest.approx([0.8, 0.2])


def test_partial_mode_engine():
    base = _tp_run()
    assert len(base[0].exits) >= 2
    term = _tp_run(partial_mode="terminus")
    assert len(term) == 1 and len(term[0].exits) == 1 and term[0].exits[0][3] == "t1" and term[0].exits[0][1] == 108.25
    new = _tp_run(partial_mode="new")
    assert len(new) == 1 and new[0].t1 == 103.5


# --- X3-full-pull-vs-mandatory-partial (35) -------------------------------------------------------------------------------------------------------

def test_exit_mode2():
    keep = [(4105.0, "array"), (4110.25, "pool"), (4120.25, "pool")]
    p = pk(exit_mode2="pay_first")
    k, fr = tp3.pay_first(p, keep)
    assert k == keep and fr[1] == pytest.approx(0.5) and sum(fr) == pytest.approx(1.0)
    assert tp3.pay_first(p, [(4105.0, "array")]) is None and tp3.pay_first(p, [(4105.0, "array"), (4107.0, "array")]) is None
    # a pool rung already above half keeps its share
    p2 = pk(exit_mode2="pay_first", ladder_fracs=(0.7, 0.2, 0.1))
    assert tp3.pay_first(p2, [(4110.25, "pool"), (4120.25, "pool")])[1] == pytest.approx([0.7, 0.3])
    ctx = mk(flat(12))
    kw = dict(ctx=ctx, sd=side(ctx), sw=dict(ext=4096.0, ext_i=2), i=8, session="AM", entry=4100.0, risk=2.0, keep=keep, keep_full=keep, draw=4110.25, final_T=False, st={}, locked=False, fixed=None)
    tags, lvt = {}, []
    tp3.late(p=pk(exit_mode2="pay_first", speed_skip=True), tags=tags, lvt=lvt, **kw)
    assert tags["tp3_speed"] and "exit_pay_first" in lvt and tags["fracs"][1] >= 0.5
    tags = {}
    why, k_, draw, _ = tp3.late(p=pk(exit_mode2="full_pull"), tags=tags, lvt=[], **kw)
    assert k_ == [(4110.25, "pool")] and tags["fracs"] == (1.0,)
    tags = {}
    why, k_, draw, _ = tp3.late(p=pk(exit_mode2="hold_runner"), tags=tags, lvt=[], **kw)
    assert k_ == [(4120.25, "pool")] and tags["fracs"] == (1.0,) and tags["day_trade"] and tags["no_adds"] and tags["exit_at"] == 900


def _speed_sd(big_touch=True, big_next=True, close_beyond=True):
    """30 quiet bars (range 1); the touch bar is 28, the bar after it 29."""
    n = 30
    o = np.full(n, 4100.0)
    h, l, c = o + 0.5, o - 0.5, o.copy()
    if big_touch:
        h[28], l[28], c[28] = 4112.0, 4099.0, 4111.0                         # range 13 >= 1.5 x 1
    if big_next:
        h[29], l[29], c[29] = 4116.0, 4108.0, 4115.0 if close_beyond else 4104.0
    return S.Side(1, o, h, l, c, 1, 0.0)


def _two_step(sd, p, pos=None, k=0):
    pos = pos or dict(fracs=(0.5, 0.5), level_kinds=["pool", "pool"], tp3=dict(speed=True), k=0)
    lv = [4110.0, 4120.0]
    assert tp3.speed_hold(pos, k, 28, sd, p) is True and pos["tp3"]["pend"] == (k, 28)     # the touch bar: nothing is decided on its own close
    assert tp3.speed_state(pos, k, lv, 28, sd, p) is None                                 # still the touch bar
    return pos, tp3.speed_state(pos, k, lv, 29, sd, p)


def test_speed_skip_defers_the_first_pool():
    p = pk(exit_mode2="pay_first", speed_skip=True)
    pos, r = _two_step(_speed_sd(), p)
    assert r == "skip" and pos["fracs"] == (0.0, 1.0) and pos["tp3"]["pend"] is None
    # the same rung is not held twice
    assert tp3.speed_hold(pos, 0, 28, _speed_sd(), p) is False
    # one small bar / a close back below the pool: paid at the pool
    for kw in (dict(big_touch=False), dict(big_next=False), dict(close_beyond=False)):
        pos, r = _two_step(_speed_sd(**kw), p)
        assert r == "pay" and pos["fracs"] == (0.5, 0.5), kw
    # the final rung and non-pool rungs are never held; a position without the flag is untouched; too little history
    sd = _speed_sd()
    assert tp3.speed_hold(dict(fracs=(0.5, 0.5), level_kinds=["pool", "pool"], tp3=dict(speed=True), k=1), 1, 28, sd, p) is False
    assert tp3.speed_hold(dict(fracs=(0.5, 0.5), level_kinds=["array", "pool"], tp3=dict(speed=True), k=0), 0, 28, sd, p) is False
    assert tp3.speed_hold(dict(fracs=(0.5, 0.5), level_kinds=["pool", "pool"], k=0), 0, 28, sd, p) is False
    assert tp3.speed_hold(dict(fracs=(0.5, 0.5), level_kinds=["pool", "pool"], tp3=dict(speed=True), k=0), 0, 15, sd, p) is False


def test_speed_skip_short_side_is_mirrored():
    """Side space: a short runs the same code on mirrored prices (the Side object holds the mirrored bars), so the mirrored book gives the same decision."""
    p = pk(exit_mode2="pay_first", speed_skip=True)
    sd = _speed_sd()
    m = S.Side(-1, -sd.o, -sd.l, -sd.h, -sd.c, 1, 0.0)           # raw short bars whose mirror is sd
    assert (m.h == sd.h).all()
    pos, r = _two_step(m, p)
    assert r == "skip"


def test_exit_mode2_engine():
    full = _tp_run(exit_mode2="full_pull")
    assert len(full) == 1 and len(full[0].exits) == 1 and full[0].exits[0][1] == 108.25            # scenario C has no pool: the last level
    hold = _tp_run(exit_mode2="hold_runner")
    assert len(hold) == 1 and len(hold[0].exits) == 1
    pay = _tp_run(exit_mode2="pay_first", speed_skip=True)
    assert len(pay) == 1


# --- X3-pool-below-untraded-htf-partial (37) ------------------------------------------------------------------------------------------------------

def test_pool_milestone():
    cf = conf([(-1, 4140.0, 4130.0, np.inf, 0, "D")], tfs=("D",))
    ctx = mk(flat(12), cf)
    sd = side(ctx)
    p = pk(pool_milestone=0.5)
    keep = [(4120.25, "pool")]
    k, fr = tp3.milestone(ctx, sd, 8, p, 4100.0, 4.0, keep)
    assert k == [(4120.25, "pool"), (4129.5, "array")] and fr == pytest.approx([0.5, 0.5])
    keep2 = [(4108.0, "array"), (4120.25, "pool")]
    k2, fr2 = tp3.milestone(ctx, sd, 8, p, 4100.0, 4.0, keep2)
    assert k2 == [(4108.0, "array"), (4120.25, "pool"), (4129.5, "array")] and fr2 == pytest.approx([0.25, 0.5, 0.25])
    # no pool short of the array / no array: untouched
    assert tp3.milestone(ctx, sd, 8, p, 4100.0, 4.0, [(4135.0, "pool")]) is None
    assert tp3.milestone(mk(flat(12)), side(mk(flat(12))), 8, p, 4100.0, 4.0, keep) is None
    # an array that price already traded to is no milestone target
    ctx_t = mk(flat(8) + [(4100.0, 4131.0, 4099.0, 4101.0)] + flat(3), cf)
    assert tp3.milestone(ctx_t, side(ctx_t), 11, p, 4100.0, 4.0, keep) is None
    kw = dict(ctx=ctx, sd=sd, sw=dict(ext=4096.0, ext_i=2), i=8, session="AM", entry=4100.0, risk=2.0, keep=keep, keep_full=keep, draw=4120.25, final_T=False, lvt=[], st={}, locked=False, fixed=None)
    tags = {}
    why, k3, draw, _ = tp3.late(p=p, tags=tags, **kw)
    assert why is None and k3[-1] == (4129.5, "array") and draw == 4129.5 and tags["fracs"] == pytest.approx((0.5, 0.5))


def test_pool_milestone_blocks_the_reversal_sweep():
    cf = conf([(-1, 4140.0, 4130.0, np.inf, 0, "D")], tfs=("D",))
    rows = [(4115.0, 4121.0, 4114.0, 4118.0)] * 12                              # a sweep of the 4120 pool, the daily FVG 4130 untouched above
    ctx = mk(rows, cf)
    sd_short = side(ctx, -1)
    sw = dict(level=-4120.0, ext=-4121.0, ext_i=4, name="rel_eq")
    p = pk(pool_milestone=0.5)
    assert tp3.sweep_gate(ctx, sd_short, sw, 8, p, "AM", want=1) == "x_htf_untraded"
    assert tp3.sweep_gate(ctx, sd_short, sw, 8, p, "AM", want=-1) is None           # the short follows the bias
    assert tp3.sweep_gate(ctx, sd_short, sw, 8, p, "AM", want=0) is None
    assert tp3.sweep_gate(ctx, sd_short, sw, 8, pk(), "AM", want=1) is None          # switch off
    assert tp3.sweep_gate(mk(rows), side(mk(rows), -1), sw, 8, p, "AM", want=1) is None      # no HTF array above
    assert tp3.sweep_gate(ctx, side(ctx), dict(level=4110.0, ext=4109.0, ext_i=4), 8, p, "AM", want=1) is None       # a long with the bias: not a reversal
    ctx_t = mk(rows[:6] + [(4118.0, 4132.0, 4117.0, 4119.0)] + rows[7:], cf)
    assert tp3.sweep_gate(ctx_t, side(ctx_t, -1), sw, 8, p, "AM", want=1) is None   # the array was traded to: the reversal is allowed


# --- X3-no-collapse-intermediate-pools (38) -------------------------------------------------------------------------------------------------------

def test_no_collapse():
    cf = conf([(-1, 4160.0, 4150.0, np.inf, 0, "D")], tfs=("D",))
    ctx = mk(flat(12), cf)
    sd = side(ctx)
    p = pk(no_collapse_htf=True)
    keep = [(4105.0, "array"), (4110.25, "pool")]
    k, fr = tp3.no_collapse(ctx, sd, 8, p, 4100.0, keep, [0.5, 0.5], {})
    assert k == keep + [(4149.5, "array")] and fr == pytest.approx([0.4, 0.4, 0.2])
    # the last rung IS the HTF draw but would take everything: 20 % must come from the earlier rungs... here the last rung already holds more
    k2, fr2 = tp3.no_collapse(ctx, sd, 8, p, 4100.0, [(4105.0, "array"), (4149.5, "array")], [0.95, 0.05], {})
    assert fr2 == pytest.approx([0.8, 0.2])
    assert tp3.no_collapse(mk(flat(12)), side(mk(flat(12))), 8, p, 4100.0, keep, [0.5, 0.5], {}) is None          # no HTF draw: nothing
    # the draw was already traded to: nothing
    ctx_t = mk(flat(8) + [(4100.0, 4152.0, 4099.0, 4101.0)] + flat(3), cf)
    assert tp3.no_collapse(ctx_t, side(ctx_t), 11, p, 4100.0, keep, [0.5, 0.5], {}) is None
    tags = {}
    kw = dict(ctx=ctx, sd=sd, sw=dict(ext=4096.0, ext_i=2), i=8, session="AM", entry=4100.0, risk=2.0, keep=keep, keep_full=keep, draw=4110.25, final_T=False, lvt=[], st={}, locked=False, fixed=None)
    why, k3, draw, _ = tp3.late(p=p, tags=tags, **kw)
    assert why is None and len(k3) == 3 and tags["fracs"][-1] == pytest.approx(0.2) and draw == 4149.5


# --- D13-speed-bump-ladder-004 (39) ---------------------------------------------------------------------------------------------------------------

def test_ladder_004():
    ctx = mk(flat(12))
    sd = side(ctx)
    p = pk(ladder_preset="004")
    keep = [(4098.0, "array"), (4118.0, "array"), (4148.25, "pool"), (4160.0, "vi")]
    r = tp3.ladder_004(ctx, sd, 8, p, keep[:3], keep, 4148.25, {})
    assert r[0] == [(4098.0, "speed"), (4118.0, "array"), (4148.25, "pool"), (4160.0, "vi")] and r[1] == pytest.approx([2 / 9, 1 / 3, 1 / 3, 1 / 9])
    n = 9
    assert [int(n * f) for f in r[1]] == [2, 3, 3, 1]                           # the engine's fills for 9 units: 2 / 3 / 3 / 1
    # no HTF array beyond the draw: three rungs, the shares renormalised
    r3 = tp3.ladder_004(ctx, sd, 8, p, keep[:3], keep[:3], 4148.25, {})
    assert len(r3[0]) == 3 and sum(r3[1]) == pytest.approx(1.0)
    # the HTF array comes from the confluence table when keep_full has none
    cf = conf([(-1, 4180.0, 4170.0, np.inf, 0, "D")], tfs=("D",))
    ctx_c = mk(flat(12), cf)
    r4 = tp3.ladder_004(ctx_c, side(ctx_c), 8, p, keep[:3], keep[:3], 4148.25, {})
    assert r4[0][-1] == (4169.5, "array") and len(r4[0]) == 4
    tags = {}
    why, k2, draw, _ = tp3.late(p=p, ctx=ctx, sd=sd, sw=dict(ext=4090.0, ext_i=2), i=8, session="AM", entry=4090.0, risk=2.0, keep=keep[:3], keep_full=keep, draw=4148.25, final_T=False, lvt=[], tags=tags, st={},
                                locked=False, fixed=None)
    assert len(k2) == 4 and tags["fracs"] == pytest.approx((2 / 9, 1 / 3, 1 / 3, 1 / 9)) and tags["tp3_ladder"]


def test_ladder_004_bump_fill_keeps_the_stop():
    """A 'speed' rung (the 004 bump) is a small partial: no break-even, no done flag - run through the real management loop on scenario C."""
    base = _tp_run(ladder_preset="004", be_on="t1")
    assert len(base) == 1
    tr = base[0]
    assert tr.entry == 100.4


# --- X3-partial-size-by-energy (40) ---------------------------------------------------------------------------------------------------------------

def test_energy_split():
    # a gapless poke through the 09:30 candle's high (4100): overlapping candles, no FVG
    rows = [(4096.0, 4100.0, 4094.0, 4097.0), (4097.0, 4099.0, 4095.0, 4098.0), (4098.0, 4101.0, 4096.0, 4099.0), (4099.0, 4102.0, 4097.0, 4100.0), (4100.0, 4101.0, 4096.0, 4097.0), (4097.0, 4099.0, 4095.0, 4096.0)]
    ctx = mk(rows)
    sd = side(ctx)
    p = pk(energy_split=True)
    keep = [(4105.0, "array"), (4125.0, "pool")]
    assert tp3.energy_first(ctx, sd, 5, p, keep, keep) == 0.5
    # with a gap on the crossing bars the poke has energy: no 0.5; then the room test
    rows2 = [(4096.0, 4100.0, 4094.0, 4097.0), (4097.0, 4099.0, 4095.0, 4098.0), (4098.0, 4101.0, 4096.0, 4099.0), (4103.0, 4108.0, 4102.0, 4107.0), (4107.0, 4109.0, 4106.0, 4108.0), (4107.0, 4108.0, 4104.0, 4105.0)]
    ctx2 = mk(rows2)
    sd2 = side(ctx2)
    assert any(z.i in (2, 3, 4) for z in sd2.gaps)
    assert tp3.energy_first(ctx2, sd2, 5, p, keep, keep) == 0.65                      # no pool / array within 5 pts beyond T1
    near = [(4105.0, "array"), (4108.0, "array"), (4125.0, "pool")]
    assert tp3.energy_first(ctx2, sd2, 5, p, near, near) is None                       # a level 3 pts beyond T1: today's split
    ctx3 = mk(rows[:1] + [(4096.0, 4099.0, 4094.0, 4097.0)] * 5)                      # never crossed the 09:30 high
    assert tp3.energy_first(ctx3, side(ctx3), 5, p, keep, keep) == 0.65
    tags = {}
    kw = dict(ctx=ctx, sd=sd, sw=dict(ext=4094.0, ext_i=1), i=5, session="AM", entry=4097.0, risk=2.0, keep=keep, keep_full=keep, draw=4125.0, final_T=False, lvt=[], st={}, locked=False, fixed=None)
    why, k2, draw, _ = tp3.late(p=p, tags=tags, **kw)
    assert why is None and tags["fracs"] == pytest.approx((0.5, 0.5)) and "energy_split" in kw["lvt"]
    t2 = {}
    tp3.late(p=pk(), tags=t2, **dict(kw, lvt=[]))
    assert "fracs" not in t2


# --- X3-five-handle-first-partial-before-draw (41) ------------------------------------------------------------------------------------------------

def test_fixed_partials():
    p = pk(fixed_partials=(5.25, 10.0))
    keep = [(4069.5, "array")]
    k, fr = tp3.fixed_rungs(p, 4054.0, keep, None)
    assert k == [(4059.25, "fixed"), (4064.0, "fixed"), (4069.5, "array")] and fr == pytest.approx([0.25, 0.25, 0.5])
    # the fixed rungs sit in price order among the ladder rungs, which share the rest
    k2, fr2 = tp3.fixed_rungs(p, 4062.0, [(4070.0, "pool"), (4080.0, "pool")], None)
    assert k2 == [(4067.25, "fixed"), (4070.0, "pool"), (4072.0, "fixed"), (4080.0, "pool")] and fr2 == pytest.approx([0.25, 0.25, 0.25, 0.25])
    # a rung at or beyond the last level is dropped
    k3, fr3 = tp3.fixed_rungs(p, 4062.0, [(4070.0, "pool")], None)
    assert k3 == [(4067.25, "fixed"), (4070.0, "pool")] and fr3 == pytest.approx([0.25, 0.75])
    assert tp3.fixed_rungs(p, 4062.0, [(4068.0, "pool")], None) == ([(4068.0, "pool")], None)          # within a point of the last level: no separate partial
    assert tp3.fixed_rungs(p, 4054.0, [(4056.0, "array")], None) == ([(4056.0, "array")], None)
    assert S._exit_px(4059.25, "fixed", p) == 4059.25 and TP._raw(4059.25, "fixed", p) == 4059.25
    # the draw alone decides min_draw_pts: the order tag and the engine run
    tr = _tp_run(fixed_partials=(1.0, 2.0), fixed_partial_fracs=(0.2, 0.2))
    assert len(tr) == 1 and "fixed_partials" in tr[0].lv_tags and len(tr[0].exits) >= 3
    pxs = sorted(round(e[1], 2) for e in tr[0].exits)
    assert 101.4 in pxs and 102.4 in pxs


# --- X3-gradient-ladder-htf-target (42) -----------------------------------------------------------------------------------------------------------

def test_quarters_ladder():
    cf = conf([(-1, 4520.0, 4500.0, np.inf, 0, "W")], tfs=("W",))
    ctx = mk(flat(12, 4400.0), cf)
    sd = side(ctx)
    p = pk(partial_mode="quarters")
    r = tp3.quarters(ctx, sd, 8, p, 4400.0, 4.0, [(4499.5, "array")], {})
    assert [v for v, _ in r[0]] == [4499.5, 4504.5, 4509.5, 4514.5] and r[1] == [0.25] * 4
    r2 = tp3.quarters(ctx, sd, 8, p, 4400.0, 4.0, [(4480.25, "pool"), (4499.5, "array")], {})
    assert [v for v, _ in r2[0]] == [4480.25, 4485.0, 4490.0, 4495.0, 4499.5] and r2[1] == pytest.approx([0.2] * 5)
    r3 = tp3.quarters(ctx, sd, 8, p, 4400.0, 4.0, [(4440.25, "pool"), (4480.25, "pool")], {})
    assert [v for v, _ in r3[0]] == [4450.0, 4460.0, 4470.0, 4480.25]
    assert tp3.quarters(ctx, sd, 8, p, 4400.0, 4.0, [(4480.25, "pool")], {}) is None
    # ladder_max_levels caps the rungs (the last one stays)
    r4 = tp3.quarters(ctx, sd, 8, replace(p, ladder_max_levels=3), 4400.0, 4.0, [(4480.25, "pool"), (4499.5, "array")], {})
    assert len(r4[0]) == 3 and r4[0][-1] == (4499.5, "array")
    tags = {}
    kw = dict(ctx=ctx, sd=sd, sw=dict(ext=4396.0, ext_i=2), i=8, session="AM", entry=4400.0, risk=4.0, keep=[(4499.5, "array")], keep_full=[(4499.5, "array")], draw=4499.5, final_T=False, lvt=[], st={}, locked=False, fixed=None)
    why, k5, draw, _ = tp3.late(p=p, tags=tags, **kw)
    assert why is None and len(k5) == 4 and tags["fracs"] == pytest.approx((0.25,) * 4) and draw == 4514.5


# --- X3-037-three-unit-ladder (43) ----------------------------------------------------------------------------------------------------------------

def test_ladder_037():
    cf = conf([(-1, 4029.0, 4025.0, np.inf, 0, "15m")], tfs=("15m",))
    ctx = mk(flat(12, 4010.0), cf)
    sd = side(ctx)
    p = pk(ladder_preset="037")
    keep = [(4022.25, "pool"), (4040.0, "array")]
    r = tp3.ladder_037(ctx, sd, 8, p, 4010.0, keep, {})
    assert r[0] == [(4022.0, "exact"), (4025.25, "fixed"), (4028.75, "fixed")] and r[1] == pytest.approx([1 / 3] * 3)
    r2 = tp3.ladder_037(ctx, sd, 8, pk(ladder_preset="037", ladder037_ce=True), 4010.0, keep, {})
    assert r2[0][-1] == (4027.0, "fixed")
    assert tp3.ladder_037(ctx, sd, 8, p, 4010.0, [(4040.0, "array")], {}) is None                      # no old high
    assert tp3.ladder_037(mk(flat(12, 4010.0)), side(mk(flat(12, 4010.0))), 8, p, 4010.0, keep, {}) is None      # no FVG above
    # news ahead: (0.4, 0.4, 0.2)
    ctx_n = mk(flat(12, 4010.0), cf, day=date(2023, 6, 1))                                              # the day before the NFP
    assert tp3.news_ahead(ctx_n, p, 8) is True and tp3.news_ahead(ctx, p, 8) is False
    assert tp3.ladder_037(ctx_n, side(ctx_n), 8, p, 4010.0, keep, {})[1] == [0.4, 0.4, 0.2]
    # the exit prices: exact for the pool at its price (pool_exit "at" for this rung) and the ticks inside the gap
    assert S._exit_px(4022.0, "exact", p) == 4022.0 and S._exit_px(4025.25, "fixed", p) == 4025.25
    tags = {}
    why, k2, draw, _ = tp3.late(p=p, ctx=ctx, sd=sd, sw=dict(ext=4006.0, ext_i=2), i=8, session="AM", entry=4010.0, risk=2.0, keep=keep, keep_full=keep, draw=4022.25, final_T=False, lvt=[], tags=tags, st={},
                                locked=False, fixed=None)
    assert len(k2) == 3 and tags["fracs"] == pytest.approx((1 / 3,) * 3)
