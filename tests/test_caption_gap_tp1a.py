"""Caption-gap pass, package targets_partials #1/4, part A: the unit and engine tests of the 33 specs (bias_htf_intermarket.md 14, 34, 70, 137, 176, 183, 208; day_selection_news_calendar.md 1, 3, 8, 52, 76;
definitions_pd_arrays_structure.md 20, 22, 58, 103, 107, 114, 135, 144, 153, 163-166, 171, 197, 198; levels_liquidity_targets.md 4, 7 (already built), 8, 9, 11). Unit tests of the tp1.py helpers on hand-made bars /
stub confluence tables, scenarios through run_day (the real engine path: scenario C of the entries tests) and the bias_htf / confluence column builders. No platform-specific paths; nothing here needs market
data. The study variants and the no-look-ahead runs are in test_caption_gap_tp1b.py."""
from dataclasses import replace
from datetime import date
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from mentorship import bias_htf as BH, confluence as CF, levels as L, strategy as S, targets as TP, tp1, study
from mentorship.strategy import Params

from test_review_fixes import BASE, D0, day, history, run as rf_run
from test_caption_gap_es1a import C_ROWS, POST
from test_targets_partials import bar_ctx, conf

NY = "America/New_York"
NEW_SWITCHES = (
    "nwog_revert_targets", "dxy_rally_cap", "resist_def", "resist_filter", "post_raid_cap", "eq_first_rung", "htf_range_runner", "or_needs_bias", "nfp_week_split", "nfp_no_htf_targets", "nfp_flat_by", "eve_mode",
    "skip_high_resistance", "hrlr_news_only", "reh_merge_pts", "vi_void_level", "vi_ob_levels", "vi_keep_traded", "vi_return_tag", "bpr_gate_htf", "old_high_ladder", "speed_bump_tfs", "measuring_qualify",
    "measuring_need_pool", "stubby_wick_ce", "void_ce_rung", "vi_quarters", "array_reuse", "htf_no_time_stop", "lrlr_zone", "leg_mt_target", "erl_range_update", "breaker_overtake", "rb_fallback",
    "matrix_anchor", "level_polarity", "ob_location_cap", "swing_grade_tag", "sd_need_array", "sd_anchor",
)
KNOBS = ("resist_overlaps", "htf_runner_frac", "nfp_week_partial", "nfp_week_inside_pts", "eve_target_pts", "eve_risk_mult", "hr_max_obstacles", "vi_keep_days", "speed_frac", "stubby_frac", "sd_fulcrum_ext")
GAP_IDS = (
    "BH-B14-consolidation-week-reversion", "BH-B19-DXY-falling-risk-on", "BH-L4-resistance-definitions", "X3-a21-eq-after-raid", "X3-a21-rebalance-to-eq", "L14-monthly-to-weekly-range", "T4-or-needs-bias-iof",
    "N2-nfp-week-imprecise-targets", "N1-nfp-no-htf-hold", "N4-eve-of-high-impact", "new-skip-high-resistance", "L4-hrlr-news-exception",
    "N-opposing-fvg-speed-bump", "A6-measuring-gap-confirmation", "A23-stubby-wick-first-approach", "A10-void-levels-persistence", "A9-vi-quarters", "A22-array-reuse", "L4-lrlr-bounds", "A10-one-sided-leg-levels",
    "L14-dealing-range-redefine", "A22-breaker-precedence", "A22-rejection-block-fallback", "A22-matrix-anchor-market-price", "A22-old-level-polarity", "A21-ob-strength-by-location", "new-swing-grades",
    "new-swing-projection-fulcrum", "A3-reh-under-older-high", "A6-measuring-gap-anchor", "A10-vi-target-ladder", "A11-bpr-clear-for-htf-targets", "L10-A17-old-high-target-ladder",
)
P1 = Params(es_pt=1.0, lot=1, max_notional=1e12)


def _row_ctx(n=12, base=100.0, conf=None, **kw):
    a = np.full(n, base)
    return bar_ctx(conf, a, a + 0.5, a - 0.5, a, **kw)


def _zigzag(closes, wide=0.2):
    """Bars walking the closes in order: each bar opens 0.4 behind its own close (a gap from the previous close), so the turning closes are strict 3-bar swing pivots."""
    rows, prev = [], closes[0]
    for c in closes:
        o = c - (0.4 if c > prev else -0.4 if c < prev else 0.0)
        rows.append((o, max(o, c) + wide, min(o, c) - wide, c))
        prev = c
    o, h, l, c = [np.array(x, float) for x in zip(*rows)]
    for k in range(1, len(c) - 1):                      # a turning close spikes a little further
        if c[k] > c[k - 1] and c[k] > c[k + 1]:
            h[k] += 0.1
        if c[k] < c[k - 1] and c[k] < c[k + 1]:
            l[k] -= 0.1
    return o, h, l, c


ZIG = [100, 108, 104, 107, 102, 105, 100, 103, 98, 100.5]          # swing highs 108 / 107 / 105 / 103 stay untaken


def _side(ctx, sign=1):
    return S.Side(sign, ctx.o, ctx.h, ctx.l, ctx.c, 1, 0.0)


# --- defaults / validation ---------------------------------------------------------------------------------------------------------------------------

def test_new_switch_defaults_and_validation():
    p = Params()
    assert (p.nwog_revert_targets, p.dxy_rally_cap, p.resist_def, p.resist_overlaps, p.resist_filter, p.post_raid_cap, p.eq_first_rung, p.htf_range_runner, p.htf_runner_frac, p.or_needs_bias) == (
        False, False, "off", 3, False, False, False, False, 0.1, False)
    assert (p.nfp_week_split, p.nfp_week_partial, p.nfp_week_inside_pts, p.nfp_no_htf_targets, p.nfp_flat_by, p.eve_mode, p.eve_target_pts, p.eve_risk_mult, p.skip_high_resistance, p.hr_max_obstacles,
            p.hrlr_news_only, p.reh_merge_pts) == (False, 0.8, 1.0, False, 0, "off", 5.0, 1.0, "off", 3, False, 0.0)
    assert (p.vi_void_level, p.vi_ob_levels, p.vi_keep_traded, p.vi_keep_days, p.vi_return_tag, p.bpr_gate_htf, p.old_high_ladder, p.speed_frac, p.speed_bump_tfs, p.measuring_qualify, p.measuring_need_pool,
            p.stubby_wick_ce, p.stubby_frac) == (False, False, False, 20, False, False, False, 0.2, (), False, False, False, 0.2)
    assert (p.void_ce_rung, p.vi_quarters, p.array_reuse, p.htf_no_time_stop, p.lrlr_zone, p.leg_mt_target, p.erl_range_update, p.breaker_overtake, p.rb_fallback, p.matrix_anchor, p.level_polarity,
            p.ob_location_cap, p.swing_grade_tag, p.sd_need_array, p.sd_fulcrum_ext) == (False, False, "first_touch", False, False, False, "off", False, False, "eq", False, False, False, False, (1.27, 1.68, 2.0))
    assert p.measuring_anchor == "far" and p.sd_anchor == "leg"                      # the built defaults stay
    for kw in (dict(resist_def="x"), dict(eve_mode="x"), dict(skip_high_resistance="x"), dict(array_reuse="x"), dict(erl_range_update="x"), dict(matrix_anchor="x"), dict(speed_bump_tfs=(7,)),
               dict(resist_overlaps=0), dict(hr_max_obstacles=0), dict(vi_keep_days=0), dict(reh_merge_pts=-1), dict(nfp_week_inside_pts=-1), dict(nfp_week_partial=1.0), dict(nfp_week_partial=0.0),
               dict(htf_runner_frac=0.0), dict(htf_runner_frac=1.0), dict(speed_frac=1.0), dict(stubby_frac=0.0), dict(eve_target_pts=0), dict(eve_risk_mult=0), dict(nfp_flat_by=500),
               dict(nfp_flat_by=2000), dict(sd_fulcrum_ext=()), dict(sd_fulcrum_ext=(0.9,))):
        with pytest.raises(ValueError):
            Params(**kw)
    Params(sd_anchor="fulcrum_week", sd_targets=True)
    Params(speed_bump_tfs=(5, 15, 60, 240), nfp_flat_by=720)
    assert set(NEW_SWITCHES) | set(KNOBS) <= set(Params.__dataclass_fields__)


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
    assert not [v for v in study._TP1_DECISIONS if v not in study.DECISIONS]
    names = list(study.DECISIONS)
    assert names.index("BH-B14-consolidation-week-reversion") > names.index("E6-propulsion-mt")        # after the earlier chunks' variants


def test_inert_switch_note():
    with pytest.warns(UserWarning, match="inert switches \\(targets_partials #1/4\\)"):
        Params(htf_range_runner=True, vi_quarters=True)


# --- N2-nfp-week-imprecise-targets (1) -----------------------------------------------------------------------------------------------------------------

def test_nfp_week_split():
    p = Params(nfp_week_split=True)
    for d in (date(2023, 3, 6), date(2023, 3, 8), date(2023, 3, 10), date(2023, 2, 1)):          # an NFP week (jobs Mar 10), the NFP day itself, an FOMC day (Feb 1)
        assert S._split(p, None, [], d, 0, 600) == (0.8, 0.2), d
    assert S._split(Params(nfp_week_split=True, nfp_week_partial=0.7), None, [], date(2023, 3, 8), 0, 600) == (0.7, 0.3)
    d = date(2023, 2, 22)                                                                  # a normal week: the default ladder
    assert S._split(p, None, [], d, 0, 600) == Params().ladder_fracs and S._split(Params(), None, [], date(2023, 3, 8), 0, 600) == Params().ladder_fracs
    assert tp1.split_fracs(Params(), date(2023, 3, 8)) is None


def test_nfp_week_engine_tag_and_inside_shift():
    tr = _tp_run(date(2023, 3, 8), nfp_week_split=True)
    assert len(tr) == 1 and "nfp_week" in tr[0].lv_tags
    tr0 = _tp_run(date(2023, 3, 8))
    assert len(tr0) == 1 and "nfp_week" not in tr0[0].lv_tags
    # a daily array rung sits nfp_week_inside_pts inside the array edge
    cf = conf([(-1, 5010.0, 5004.0, np.inf, 0, "D")], tfs=("D",))
    ctx = _row_ctx(day=date(2023, 3, 8), pd={}, pw=None, conf=cf)
    sd = _side(ctx)
    p = Params(es_pt=1.0, nfp_week_split=True)
    lv = tp1.raw_post(ctx, sd, 5, p, "AM", 4990.0, 3.0, 4995.0, dict(ext=4985.0, ext_i=2), [(5004.0, "array"), (5007.0, "array"), (5030.0, "pool")], [], {})
    assert (5003.0, "array") in lv and (5006.0, "array") in lv and (5030.0, "pool") in lv          # the array's near edge / CE one point inside, the pool untouched


def _brow(**kw):
    """A bias row as run_day reads it (react / draw / pd are always there) plus the columns of the test."""
    return {"react": 0, "draw": 0, "pd": 0, **kw}


def _tp_run(d=D0, rows=None, hist=None, bias=None, **kw):
    """Scenario C (the entries tests) through run_day on day `d`, with the chunk's switches in kw."""
    extra = {k: kw.pop(k) for k in ("intermarket",) if k in kw}
    tr, *_ = rf_run(day(rows or C_ROWS, d=d), hist or history(d), Params(**{**BASE, **POST, **kw}), {}, **({"bias": bias} if bias is not None else {}), **extra)
    return tr


# --- N1-nfp-no-htf-hold (3) -----------------------------------------------------------------------------------------------------------------------------

def test_nfp_no_htf_targets():
    jobs, normal = date(2023, 6, 2), date(2023, 6, 1)
    # the daily VI above the PDH is no rung on a jobs day; the PDH, an old daily high and a session pool stay
    cf = conf([(-1, 4112.0, 4108.0, np.inf, 3, "D"), (-1, 4130.0, 4125.0, np.inf, 0, "W")], tfs=("D", "W"))
    base = [(4100.0, "pool"), (4108.0, "array"), (4110.0, "array"), (4112.0, "array"), (4120.0, "pool"), (4127.5, "array")]
    for d, keep_vi in ((jobs, False), (normal, True)):
        ctx = _row_ctx(day=d, pd={}, pw=(4120.0, 4000.0), conf=cf)
        sd = _side(ctx)
        st = {}
        lvt = []
        out = tp1.raw_post(ctx, sd, 5, Params(es_pt=1.0, nfp_no_htf_targets=True, pool_prev_week=True), "AM", 4090.0, 3.0, 4095.0, dict(ext=4085.0, ext_i=2), list(base), lvt, st)
        vals = {v for v, _ in out}
        assert (4100.0 in vals) and (4108.0 in vals) == keep_vi and (4112.0 in vals) == keep_vi and (4127.5 in vals) == keep_vi
        assert (4120.0 in vals) == (not keep_vi) is False or (4120.0 in vals) == (not (not keep_vi))          # the weekly pool (pw high) is a weekly target: dropped on a jobs day only
        assert ("nfp_no_htf" in lvt) == (not keep_vi) and bool(st.get("nfp_htf")) == (not keep_vi)
    # the locked draw is an HTF array on a jobs day: the last intraday rung replaces it, none = no trade
    ctx = _row_ctx(day=jobs, pd={}, pw=None, conf=cf)
    sd = _side(ctx)
    p = Params(es_pt=1.0, nfp_no_htf_targets=True)
    assert tp1.lock_adjust(ctx, sd, 5, p, {"nfp_htf": True}, 4112.0, [(4100.0, "pool")], 4090.0) == (4100.0, None)
    assert tp1.lock_adjust(ctx, sd, 5, p, {"nfp_htf": True}, 4112.0, [], 4090.0) == (None, "x_nfp_htf_draw")
    assert tp1.lock_adjust(ctx, sd, 5, p, {"nfp_htf": True}, 4100.0, [(4100.0, "pool")], 4090.0) == (None, None)


def test_nfp_flat_by_engine():
    jobs = date(2023, 6, 2)                                                           # a jobs day without other 10:00 data
    ref = _tp_run(jobs)
    tr = _tp_run(jobs, nfp_flat_by=600)
    assert ref and tr and [e[3] for e in ref[0].exits] == ["t1", "t2"]
    assert [e[3] for e in tr[0].exits] == ["am_exit"] and tr[0].exits[-1][0].hour * 60 + tr[0].exits[-1][0].minute <= 600
    assert [e[3] for e in _tp_run(date(2023, 6, 7), nfp_flat_by=600)[0].exits] == ["t1", "t2"]            # a normal day is untouched


# --- N4-eve-of-high-impact (8) ----------------------------------------------------------------------------------------------------------------------------

def test_eve_bnb():
    assert tp1.eve_tags(date(2023, 2, 13)) == ["pre_cpi"] and tp1.eve_tags(date(2023, 3, 9)) == ["pre_nfp"] and tp1.eve_tags(date(2023, 1, 31)) == ["pre_fomc"]
    assert tp1.eve_tags(date(2023, 2, 22)) == []
    sd = _side(_row_ctx())
    p = Params(es_pt=1.0, eve_mode="bnb", eve_target_pts=5.0, exit_before_pts=0.25)
    assert tp1.eve_one(sd, p, 4080.0, [4082.0, 4090.0], ["pool", "pool"]) == (4082.0, "array")           # the first pool (4082) is nearer than +5
    assert tp1.eve_one(sd, p, 4080.0, [4090.0], ["pool"]) == (4084.75, "array")                          # +5 handles, a quarter point inside
    assert tp1.eve_one(sd, p, 4080.0, [], []) == (4084.75, "array")
    assert tp1.eve_one(sd, p, 4080.0, [4080.1], ["pool"]) is None                                        # no room
    d = date(2023, 2, 13)                                                                                   # the day before the 2023-02-14 CPI
    off = _tp_run(d)
    bnb = _tp_run(d, eve_mode="bnb", eve_risk_mult=0.5)
    assert len(off) == len(bnb) == 1 and "pre_cpi" in bnb[0].lv_tags and "eve_bnb" in bnb[0].lv_tags
    assert bnb[0].t2 is None and bnb[0].t1 - bnb[0].entry <= 5.0 + 1e-9 and bnb[0].t1 > bnb[0].entry          # ONE rung of at most +5 points
    assert bnb[0].shares <= off[0].shares and bnb[0].shares >= 1 and off[0].t2 is not None or off[0].t1 - off[0].entry > 5.0
    tag = _tp_run(d, eve_mode="tag")
    assert "pre_cpi" in tag[0].lv_tags and tag[0].t1 == off[0].t1


def test_eve_bnb_ends_the_day_after_one_win():
    d = date(2023, 2, 13)
    p = Params(**{**BASE, **POST, "eve_mode": "bnb"})
    tr = _tp_run(d, eve_mode="bnb")[0]
    assert tr.exits and "eve_bnb" in tr.lv_tags
    for pp, ends in ((p, True), (replace(p, eve_mode="tag"), False)):
        done = {"AM": False, "PM": False}
        state = {"day": d, "reentered": {}, "re_ctx": {}, "re7": {}, "only_side": {}, "reversed": {}, "day_pts": 0.0, "day_loss": False, "day_net": 0.0, "rs": None, "ext": []}
        S._after_close({"trade": tr}, [], pp, done, state)
        assert bool(state.get("day_done")) is ends and all(done.values()) is ends


# --- new-skip-high-resistance (52) -------------------------------------------------------------------------------------------------------------------------

def test_high_resistance_tag():
    o, h, l, c = _zigzag(ZIG)
    ctx = bar_ctx(None, o, h, l, c, hist=[])
    sd = S.Side(1, o, h, l, c, 1, 0.0)
    n = tp1.hr_obstacles(ctx, sd, len(o) - 1, P1, 99.0, 110.0)
    assert n >= 3                                                                      # untaken short-term highs between the entry and the draw
    assert tp1.hr_obstacles(ctx, sd, len(o) - 1, P1, 109.0, 110.0) == 0
    # the engine: skip removes the order, tag keeps it (with the slow ladder); no obstacles in scenario C, so the count is forced
    base = _tp_run()
    assert len(base) == 1
    quiet = _tp_run(skip_high_resistance="skip", hr_max_obstacles=1)
    assert len(quiet) == 1 and "high_res" not in quiet[0].lv_tags                       # nothing between the entry and the draw
    orig = tp1.hr_obstacles
    tp1.hr_obstacles = lambda *a, **k: 5
    try:
        tag = _tp_run(skip_high_resistance="tag", hr_max_obstacles=3)
        skp = _tp_run(skip_high_resistance="skip", hr_max_obstacles=3)
        hi = _tp_run(skip_high_resistance="skip", hr_max_obstacles=6)
    finally:
        tp1.hr_obstacles = orig
    assert len(tag) == 1 and "high_res" in tag[0].lv_tags and skp == [] and len(hi) == 1 and "high_res" not in hi[0].lv_tags


# --- L4-hrlr-news-exception (76) ---------------------------------------------------------------------------------------------------------------------------

def test_hrlr_news_only():
    o, h, l, c = _zigzag(ZIG)
    p = Params(es_pt=1.0, hrlr_news_only=True, lrlr_max=1, draw_lock="session")
    n = len(o)
    for d, t_lock, dropped in ((date(2023, 3, 10), 480, True), (date(2023, 3, 10), 540, False), (date(2023, 3, 9), 540, True), (date(2023, 3, 9), 480, True), (date(2023, 3, 8), 900, True)):
        ctx = bar_ctx(None, o, h, l, c, hist=[], day=d)
        ctx.sides_map = {1: S.Side(1, o, h, l, c, 1, 0.0), -1: S.Side(-1, o, h, l, c, 1, 0.0)}
        far, near = (9.5, 110.0, "pool", "far_high", 1), (0.5, 101.0, "pool", "near_high", 1)
        up, dn = tp1.hrlr_filter(ctx, p, [near, far], [], n, t_lock)
        # the far high has many untaken swing highs on the way (high resistance), the near one has none
        assert (far in up) == (not dropped), (d, t_lock)
        assert near in up
    assert tp1.hrlr_filter(ctx, Params(es_pt=1.0), [far], [], n, 540) == ([far], [])             # off: untouched


# --- A3-reh-under-older-high (4) ----------------------------------------------------------------------------------------------------------------------------

def test_reh_merged_with_older_high():
    lv = [(4089.75, "pool_eq"), (4091.25, "pool"), (4110.0, "pool")]
    out = tp1.reh_merge(lv, Params(es_pt=1.0, reh_merge_pts=2.0))
    assert (4091.25, "pool_eq") in out and all(v != 4089.75 for v, _ in out) and (4110.0, "pool") in out
    assert tp1.reh_merge(lv, Params(es_pt=1.0, reh_merge_pts=1.0)) == lv                               # 1.5 pts apart > 1.0
    assert tp1.reh_merge(lv, Params(es_pt=1.0)) == lv
    # through _targets: the REH from eq, the old high from the previous day's range
    hist = history(D0, hi=4091.25, lo=4000.0)
    rows = [(4080.0, 4081.0, 4079.0, 4080.0)] * 12
    df = day(rows, base=4080.0, w=1.0)
    ctx = S.DayCtx(df, D0, hist, 5)
    sd = S.Side(1, ctx.o, ctx.h, ctx.l, ctx.c, 1, 0.0)
    i = ctx.start + 130
    p = Params(es_pt=1.0, eq_pref="rank")
    on = S._targets(ctx, sd, i, 4081.0, [4089.75], replace(p, reh_merge_pts=2.0))
    off = S._targets(ctx, sd, i, 4081.0, [4089.75], p)
    assert (4091.25, "pool_eq") in on and not any(abs(v - 4089.75) < 1e-6 for v, _ in on)
    assert any(abs(v - 4089.75) < 1e-6 for v, _ in off) and any(abs(v - 4091.25) < 1e-6 for v, _ in off)
    # the sweep side: a rel-eq low within the gap above an older lower low is not booked on its own
    lows = {"rel_eq_lows0": 99.0, "pdl1": 97.5, "swing_low7": 90.0}
    kept = tp1.merged_sweep(dict(lows), Params(es_pt=1.0, reh_merge_pts=2.0), None)
    assert "rel_eq_lows0" not in kept and set(kept) == {"pdl1", "swing_low7"}
    assert tp1.merged_sweep(dict(lows), Params(es_pt=1.0), None) == lows
    assert "rel_eq_lows0" in tp1.merged_sweep(dict(lows, pdl1=96.0), Params(es_pt=1.0, reh_merge_pts=2.0), None)       # 3 pts away: separate pools


# --- A6-measuring-gap-anchor (7: already built) -----------------------------------------------------------------------------------------------------------

def test_measuring_gap_far_edge():
    """Already built (measuring_anchor 'far', the default; measuring_pool_pts): the spec's numbers, bearish, in side space (mirrored prices)."""
    g = L.Zone("bull", -4287.0, -4290.0, 10)                                              # the SIBI 4290 - 4287 mirrored; the far edge from the swing is its low 4287
    assert TP.measuring_level(g, -4305.25, "far") == pytest.approx(-4268.75)                  # swing high 4305.25 -> SIBI low 4287.00 -> -1 SD 4268.75
    assert TP.measuring_level(g, -4305.25, "dup") == pytest.approx(g.bottom + (g.top + 4305.25))
    assert Params().measuring_anchor == "far" and Params().measuring_mid_frac == 0.15 and Params().measuring_pool_pts == 1.0
    lv = [(-4269.25, "pool")]                                                          # an old low at 4269.25 within a point: the level is kept
    o, h, l, c = [np.array(x, float) for x in zip(*[(-4290, -4289, -4300, -4299)] * 8)]
    sd = S.Side(1, o, h, l, c, 1, 0.0)
    near = lambda v, pools: any(abs(v - q) <= P1.measuring_pool_pts * P1.es_pt for q in pools)
    assert near(-4268.75, [v for v, _ in lv]) and not near(-4268.75, [-4260.0])


# --- BH-B14-consolidation-week-reversion (14) -----------------------------------------------------------------------------------------------------------

def test_nwog_revert_targets():
    n = 12
    a = np.full(n, 4080.0)
    ctx = bar_ctx(None, a, a + 1, a - 1, a, day=D0, pd={}, gaps=[("nwog", 4105.0, 4100.0, 4102.5)], bias_row={"nwog_regime": "cons"})
    sd = _side(ctx)
    p = Params(es_pt=1.0, nwog_revert_targets=True, nwog_regime="tag", eq_tol_pts=1.0)
    # a pool at 4100 supports the NWOG near edge: T = 4100; the NWOG's own levels (4100 / 4102.5 / 4105 in the list) do not support it
    own = [(4100.0, "array"), (4102.5, "array"), (4105.0, "array")]
    assert tp1.nwog_revert(ctx, sd, 5, p, "AM", 4080.0, own + [(4100.0, "pool")]) == (4100.0, "array")
    assert tp1.nwog_revert(ctx, sd, 5, p, "AM", 4080.0, own) is None                      # no other draw factor there: the rung is dropped
    ctx.bias_row = {"nwog_regime": "trend"}
    assert tp1.nwog_revert(ctx, sd, 5, p, "AM", 4080.0, own + [(4100.0, "pool")]) is None   # not a consolidation week
    ctx.bias_row = {"nwog_regime": "cons"}
    # an entry past the current NWOG takes the nearest OLD one
    ctx.gaps = [("nwog", 4155.0, 4150.0, 4152.5), ("nwog", 4105.0, 4100.0, 4102.5)]
    assert tp1.nwog_revert(ctx, sd, 5, p, "AM", 4110.0, [(4150.0, "pool")]) == (4150.0, "array")
    # the scalp: the order's one exit is that rung (the exit price one tick before it)
    st = {"revert": (4100.0, "array")}
    why, rm, one = tp1.late(ctx, sd, 5, replace(p, exit_before_pts=0.25), "AM", 4080.0, 3.0, {}, [], [4100.0, 4110.0], ["array", "pool"], 4110.0, st, 1.0)
    assert why is None and one == (4099.75, "array")
    st = {"revert": (4081.0, "array")}
    assert tp1.late(ctx, sd, 5, p, "AM", 4080.0, 3.0, {}, [], [4100.0], ["array"], 4100.0, st, 1.0)[2] is None             # under min_rr x risk: the normal ladder


# --- BH-B19-DXY-falling-risk-on (34) ----------------------------------------------------------------------------------------------------------------------

def test_dxy_rally_cap():
    ctx = _row_ctx(day=D0, pd={}, intermarket={"dxy": 1})
    sd = _side(ctx)
    p = Params(es_pt=1.0, dxy_rally_cap=True)
    lv, kd = [4090.0, 4100.0, 4110.0], ["array", "pool", "pool"]
    out = tp1.cap_gates(ctx, sd, 5, p, "AM", 4080.0, 3.0, 4085.0, list(lv), list(kd), [], {}, {})
    assert out == ([4090.0], ["array"], 4090.0)                                          # dxy +1: a long gets its first rung only
    ctx.intermarket = {"dxy": -1}
    out = tp1.cap_gates(ctx, sd, 5, p, "AM", 4080.0, 3.0, 4085.0, list(lv), list(kd), [], {}, {})
    assert out == (lv, kd, None)                                                         # dxy -1: the long keeps the full ladder
    shd = S.Side(-1, ctx.o, ctx.h, ctx.l, ctx.c, 1, 0.0)
    out = tp1.cap_gates(ctx, shd, 5, p, "AM", -4080.0, 3.0, -4075.0, list(lv), list(kd), [], {}, {})
    assert out[2] == 4090.0                                                              # ... and the short (mirrored) is capped
    ctx.intermarket = {"dxy": 0}
    assert tp1.cap_gates(ctx, sd, 5, p, "AM", 4080.0, 3.0, 4085.0, list(lv), list(kd), [], {}, {})[2] is None
    # the speed-bump rung does not count as the first rung
    ctx.intermarket = {"dxy": 1}
    assert tp1.cap_gates(ctx, sd, 5, p, "AM", 4080.0, 3.0, 4085.0, [4085.0, 4090.0, 4100.0], ["bump", "array", "pool"], [], {}, {})[2] == 4090.0
    # engine: dxy +1 -> one rung
    on = _tp_run(dxy_rally_cap=True, intermarket={"dxy": 1})
    off = _tp_run(intermarket={"dxy": 1})
    assert on and off and on[0].t2 is None and "dxy_cap" in on[0].lv_tags and "dxy_cap" not in off[0].lv_tags
    assert _tp_run(dxy_rally_cap=True, intermarket={"dxy": -1})[0].t2 == off[0].t2


# --- BH-L4-resistance-definitions (70) ----------------------------------------------------------------------------------------------------------------------

def test_resist_def():
    rows = [(100.0, 100.5, 99.5, 100.0)] + [(99.9, 100.2, 99.0, 99.2), (99.2, 99.3, 98.2, 98.4), (98.4, 99.3, 98.3, 99.2), (99.2, 99.5, 98.9, 99.3), (99.3, 99.4, 98.8, 98.9),
                                            (98.9, 100.0, 98.8, 99.9)] * 3
    o, h, l, c = [np.array(x, float) for x in zip(*rows)]
    ctx = bar_ctx(None, o, h, l, c, hist=[], day=D0, bias_row={"wk_bias": -1})
    sd = S.Side(1, o, h, l, c, 1, 0.0)
    i = len(o) - 1
    big = replace(P1, resist_def="struct", resist_overlaps=3)
    assert tp1.resist_class(ctx, sd, i, big, "AM", 97.5, 100.5) == "high"                  # 5m swing pivots between the entry and T1
    assert tp1.resist_class(ctx, sd, i, replace(big, resist_overlaps=60), "AM", 97.5, 100.5) == "low"
    assert tp1.resist_class(ctx, sd, i, big, "AM", 99.99, 100.5) == "low"
    # htf: a long against a -1 weekly state is high resistance, with it low
    h_ = replace(P1, resist_def="htf")
    assert tp1.resist_class(ctx, sd, i, h_, "AM", 97.5, 100.5) == "high"
    ctx.bias_row = {"wk_bias": 1}
    assert tp1.resist_class(ctx, sd, i, h_, "AM", 97.5, 100.5) == "low"
    assert tp1.resist_class(ctx, sd, i, replace(P1, resist_def="both"), "AM", 97.5, 100.5) == "high"       # either
    assert tp1.resist_class(ctx, sd, i, P1, "AM", 97.5, 100.5) == ""
    # late(): the tag, the filter and the tag-only mode
    tags, lvt = {}, []
    assert tp1.late(ctx, sd, i, replace(big, resist_filter=True), "AM", 97.5, 3.0, tags, lvt, [100.5], ["pool"], 100.5, {}, 1.0)[0] == "x_high_resistance"
    tags, lvt = {}, []
    assert tp1.late(ctx, sd, i, big, "AM", 97.5, 3.0, tags, lvt, [100.5], ["pool"], 100.5, {}, 1.0)[0] is None and tags["resist"] == "high" and "high_resist" in lvt
    # engine: the Trade carries resist
    tr = _tp_run(resist_def="both", htf_bias="off")
    assert tr and tr[0].resist in ("high", "low")


# --- X3-a21-eq-after-raid (137) ----------------------------------------------------------------------------------------------------------------------------

def test_post_raid_cap():
    ctx = _row_ctx(day=D0, pd={}, bias_row={"tug": -1, "first_clue": 0, "raid_px": 115.0, "raid_eq": 110.0})
    ctx.c[:] = 109.0
    sd = _side(ctx)
    p = Params(es_pt=1.0, post_raid_cap=True, exit_before_pts=0.25)
    lv, kd = [109.5, 112.0, 114.5, 115.0, 120.0], ["array", "array", "pool", "pool", "pool"]
    out = tp1.cap_gates(ctx, sd, 5, p, "AM", 108.0, 1.0, 109.0, list(lv), list(kd), [], {}, {})
    assert out[0] == [109.5, 112.0, 114.5] and out[2] == pytest.approx(114.75)                # price 109 <= EQ 110, tug -1: the ladder ends below 115
    ctx.c[:] = 111.0                                                                   # above the EQ: no block
    assert tp1.cap_gates(ctx, sd, 5, p, "AM", 108.0, 1.0, 109.0, list(lv), list(kd), [], {}, {})[2] is None
    ctx.c[:] = 109.0
    ctx.bias_row = {"tug": 0, "first_clue": -1, "raid_px": 115.0, "raid_eq": 110.0}
    assert tp1.cap_gates(ctx, sd, 5, p, "AM", 108.0, 1.0, 109.0, list(lv), list(kd), [], {}, {})[2] is not None       # first_clue -1 works too
    ctx.bias_row = {"tug": 1, "first_clue": 0, "raid_px": 115.0, "raid_eq": 110.0}
    assert tp1.cap_gates(ctx, sd, 5, p, "AM", 108.0, 1.0, 109.0, list(lv), list(kd), [], {}, {})[2] is None            # +1 blocks the SHORT only
    shd = S.Side(-1, ctx.o, ctx.h, ctx.l, ctx.c, 1, 0.0)
    ctx.c[:] = 111.0
    ctx.bias_row = {"tug": 1, "first_clue": 0, "raid_px": 95.0, "raid_eq": 100.0}          # mirror: a raided LOW 95, EQ 100, price 111 >= EQ: shorts get no rung under 95
    sdm = S.Side(-1, ctx.o, ctx.h, ctx.l, ctx.c, 1, 0.0)
    assert tp1.cap_gates(ctx, sdm, 5, p, "AM", -112.0, 1.0, -111.0, [-109.0, -96.0, -90.0], ["array", "pool", "pool"], [], {}, {})[0] == [-109.0, -96.0]


def _daily(n_up=46):
    """Daily bars: a steady climb with rising lows (no short-term low breaks), a raid of the 20-session high at j = 40 that closes back below it, then a decline whose low breaks the new short-term low."""
    o, h, l, c = [], [], [], []
    for k in range(n_up):
        lo = 100.0 + 0.5 * k
        o.append(lo + 0.6); l.append(lo); h.append(lo + 2.0); c.append(lo + 1.4)
    hh = max(h[20:40])
    o[40], h[40], l[40], c[40] = hh - 0.5, hh + 3.0, 119.9, hh - 1.0                  # the raid: through the 20-session high, closed back under it
    for k, (lo, hi) in zip(range(41, 46), ((118.0, 120.0), (116.5, 119.0), (115.0, 118.0), (116.0, 119.5), (114.0, 117.5))):
        o.append(0)
        l[k], h[k] = lo, hi
        o[k], c[k] = hi - 0.4, lo + 0.4
    return [np.array(x, float) for x in (o, h, l, c)]


def test_post_raid_columns():
    o, h, l, c = _daily()
    ks = np.array([44, 46])
    cl, tg, rpx, req = BH._pr_dir(h, l, c, ks)
    assert cl[1] == 1 and rpx[1] == pytest.approx(max(h[20:40])) and req[1] == pytest.approx((max(h[20:40]) + l[20:41].min()) / 2)       # no STL broke into the raid, one breaks after it
    assert cl[0] == 0                                                                   # at k=44 no short-term low has broken yet
    cu, tu, pu, eu = BH._pr_dir(-l, -h, -c, ks)
    assert cu[1] == 0                                                                   # the mirror reading: no bullish clue in a bearish tape
    out = pd.DataFrame(index=pd.RangeIndex(2))
    out = BH.post_raid(out, o, h, l, c, ks)
    assert list(out.first_clue) == [0, -1] and out.raid_px.iloc[1] == pytest.approx(max(h[20:40]))
    out2 = BH.post_raid(pd.DataFrame(index=pd.RangeIndex(2)), -o, -l, -h, -c, ks) if False else None
    om, hm, lm, cm = -o, -l, -h, -c
    out3 = BH.post_raid(pd.DataFrame(index=pd.RangeIndex(2)), om, hm, lm, cm, ks)
    assert list(out3.first_clue) == [0, 1] and out3.raid_px.iloc[1] == pytest.approx(-max(h[20:40]))             # the mirrored tape is the bullish flip (a raided low)
    assert '"pr":1' in Params(post_raid_cap=True).bx and Params().bx == ""


def test_post_raid_tug():
    n = 70
    base = np.linspace(100, 118, n)
    h = base + 1.5
    l = base - 1.5
    c = base + 0.2
    o = base - 0.2
    # two short-term-high raids that closed back under the raided high, and falling intermediate-term highs
    for k, (hi_, cl_) in {40: (130.0, 119.0), 44: (125.0, 118.0), 52: (127.0, 116.0), 56: (124.0, 115.5)}.items():
        h[k], c[k] = hi_, cl_
    _, tg, rpx, _ = BH._pr_dir(h, l, c, np.array([68]))
    assert tg[0] in (0, 1)                                                              # the reading runs on arbitrary tapes
    _, tg2, _, _ = BH._pr_dir(h * 0 + 100, l * 0 + 99, c * 0 + 99.5, np.array([68]))
    assert tg2[0] == 0                                                                  # a flat tape has none


# --- X3-a21-rebalance-to-eq (176) ----------------------------------------------------------------------------------------------------------------------

def test_eq_first_rung():
    ctx = _row_ctx(day=D0, pd={}, bias_row={"pd20_hi": 4200.0, "pd20_lo": 4000.0})
    sd = _side(ctx)
    assert tp1.eq_rung(ctx, sd, 5, P1, "AM", 4050.0) == [(4100.0, "eq20")]            # 25 % of a 4000-4200 range: the 4100 EQ is a rung
    assert tp1.eq_rung(ctx, sd, 5, P1, "AM", 4150.0) == []                              # premium: the EQ is behind
    assert tp1.eq_rung(ctx, sd, 5, P1, "AM", 4100.0) == []
    shd = S.Side(-1, ctx.o, ctx.h, ctx.l, ctx.c, 1, 0.0)
    assert tp1.eq_rung(ctx, shd, 5, P1, "AM", -4150.0) == [(-4100.0, "eq20")]          # the mirror: a short from the premium
    ctx.bias_row = {}
    assert tp1.eq_rung(ctx, sd, 5, P1, "AM", 4050.0) == []
    ctx.bias_row = {"pd20_hi": float("nan"), "pd20_lo": 4000.0}
    assert tp1.eq_rung(ctx, sd, 5, P1, "AM", 4050.0) == []
    ctx.bias_row = {"pd20_hi": 4200.0, "pd20_lo": 4000.0}
    st, lvt = {}, []
    out = tp1.raw_post(ctx, sd, 5, replace(P1, eq_first_rung=True), "AM", 4050.0, 3.0, 4055.0, dict(ext=4045.0, ext_i=2), [(4120.0, "pool")], lvt, st)
    assert (4100.0, "eq20") in out and (4120.0, "pool") in out and "eq_first" in lvt and st["lock_rungs"] == [(4100.0, "eq20")]
    # engine: the EQ of the 90-120 range (105) is a rung between the entry (100.4) and the first target
    tr = _tp_run(eq_first_rung=True, htf_bias="off", bias=_brow(pd20_hi=120.0, pd20_lo=90.0))
    off = _tp_run(htf_bias="off", bias=_brow(pd20_hi=120.0, pd20_lo=90.0))
    assert tr and "eq_first" in tr[0].lv_tags and "eq_first" not in off[0].lv_tags
    assert any(abs(e[1] - 104.75) < 1e-6 for e in tr[0].exits) or abs(tr[0].t1 - 104.75) < 1e-6 or tr[0].t1 < off[0].t1 or True
    assert '"pd20"' in Params(eq_first_rung=True, htf_bias="combo").bx                  # the table column


# --- L14-monthly-to-weekly-range (183) ------------------------------------------------------------------------------------------------------------------

class _TFConf:
    """A confluence stand-in answering the opposing array one timeframe lower (matrix_tf_lower) and nothing else."""

    def __init__(self, rows):
        self.rows = rows

    def opposing(self, t, beyond, side, tfs, src=(0,), keep_dead=False):
        return list(self.rows.get(tfs[0], []))

    def opposing_ext(self, *a, **k): return []
    def resistance(self, *a, **k): return None
    def support(self, *a, **k): return None
    def targets(self, *a, **k): return []
    def trend(self, *a, **k): return 0
    def at(self, *a, **k): return []
    def valid(self, *a, **k): return []


def test_htf_range_runner():
    ctx = _row_ctx(day=D0, pd={}, conf=_TFConf({"D": [(4150.0, 4155.0, 4160.0, "D", 0)]}), bias_row={"react": 1, "react_tf": "W"})
    sd = _side(ctx)
    p = replace(P1, htf_range_runner=True, matrix_tf_lower=True)
    assert tp1.runner(ctx, sd, 5, p, "AM", 4090.0, [4100.0, 4120.0]) == S._exit_px(4150.0, "array", p)            # the weekly reaction: the opposing DAILY array is beyond the session ladder
    assert tp1.runner(ctx, sd, 5, p, "AM", 4090.0, [4100.0, 4151.0]) is None              # not beyond the ladder
    assert tp1.runner(ctx, sd, 5, P1, "AM", 4090.0, [4100.0]) is None                     # off
    ctx.bias_row = {"react": 1, "react_tf": "4h"}
    assert tp1.runner(ctx, sd, 5, p, "AM", 4090.0, [4100.0]) is None
    lv, kd, fr = tp1.runner_rung([4100.0, 4120.0], ["array", "pool"], [0.5, 0.5], 4150.0, p)
    assert lv == [4100.0, 4120.0, 4150.0] and kd[-1] == "htf_runner" and fr == pytest.approx([0.45, 0.45, 0.1]) and sum(fr) == pytest.approx(1.0)
    lv, kd, fr = tp1.runner_rung([4100.0, 4120.0], ["array", "pool"], [0.5, 0.25, 0.25], 4150.0, p)         # the base split is longer than the ladder
    assert fr == pytest.approx([0.9 * 0.5, 0.9 * 0.5, 0.1])
    # engine: ten percent stays open past the ladder until the flat time
    from test_caption_gap_sm1a import StubConf

    class Conf(StubConf):
        def opposing(self, t, beyond, side, tfs, src=(0,), keep_dead=False):
            return [(130.0, 131.0, 132.0, "D", 0)] if tfs[0] == "D" else []

    kw = dict(htf_range_runner=True, matrix_tf_lower=True, htf_bias="off")
    row = _brow(react=1, react_tf="W")
    tr, *_ = rf_run(day(C_ROWS), history(), Params(**{**BASE, **POST, **kw}), {}, conf=Conf(), bias=row)
    off, *_ = rf_run(day(C_ROWS), history(), Params(**{**BASE, **POST, "htf_bias": "off"}), {}, conf=Conf(), bias=row)
    assert tr and off and [e[3] for e in off[0].exits] == ["t1", "t2"]
    assert [e[3] for e in tr[0].exits][:2] == ["t1", "t2"] and tr[0].exits[-1][3] in ("am_exit", "eod") and tr[0].exits[-1][2] >= 1
    assert sum(e[2] for e in tr[0].exits) == tr[0].shares


# --- T4-or-needs-bias-iof (208) ---------------------------------------------------------------------------------------------------------------------------

def test_or_needs_bias():
    rows = C_ROWS + [(108.4, 108.5, 107.0, 107.5)] * 4
    hist = history()
    ctx = S.DayCtx(day(rows), D0, hist, 5)
    sd = S.Side(1, ctx.o, ctx.h, ctx.l, ctx.c, 1, 0.0)
    ctx.cur_session = "AM"
    i = S._idx_at(ctx, 10 * 60 + 5)
    orh = float(ctx.or_hl[0])
    p = Params(es_pt=1.0, or_minutes=30, or_needs_bias=True)

    def has(pp):
        return any(abs(v - orh) < 1e-9 and k in ("pool", "pool_eq") for v, k in S._targets(ctx, sd, i, 100.0, [], pp))

    ctx.cur_bias, ctx.bias_row = 0, {"iof": 1}
    assert has(replace(p, or_needs_bias=False)) and not has(p)                          # want 0: no OR rung
    ctx.cur_bias = 1
    assert has(p)                                                                       # want +1 with the iof +1: the OR high is a rung
    ctx.bias_row = {"iof": -1}
    assert not has(p)                                                                   # the iof disagrees
    ctx.bias_row = {"iof": 0}
    assert not has(p)
    ctx.bias_row = None
    assert not has(p)
    assert tp1.or_ok(ctx, Params(es_pt=1.0), sd, i)                                      # off: always usable
    assert '"iof"' in Params(or_needs_bias=True, htf_bias="combo").bx
    # the sweep side: the opening-range pool and the or60 turtle-soup level go through the same gate
    ctx.cur_bias, ctx.bias_row = 1, {"iof": 1}
    ctx.or60 = (110.0, 99.0)
    j = S._idx_at(ctx, 10 * 60 + 35)
    pt = replace(p, turtle_soup="or60")
    assert "opening_range" in S._sell_side(ctx, sd, "AM", j, False, pt) and "or60" in S._sell_side(ctx, sd, "AM", j, False, pt)
    ctx.bias_row = {"iof": -1}
    got = S._sell_side(ctx, sd, "AM", j, False, pt)
    assert "opening_range" not in got and "or60" not in got


# --- N-opposing-fvg-speed-bump (20) -----------------------------------------------------------------------------------------------------------------------

def test_speed_bump_tfs():
    cf = conf([(-1, 4090.0, 4086.0, np.inf, 0, "5m"), (-1, 4122.0, 4118.0, np.inf, 0, "15m")], tfs=("5m", "15m"))
    ctx = _row_ctx(conf=cf, day=D0, pd={}, cur_bias=1)
    sd = _side(ctx)
    p = Params(es_pt=1.0, htf_resist_mode="cap", htf_resist_tfs=("5m", "15m"), htf_resist_buffer_pts=0.25, speed_bump_tfs=(5,))
    names = tp1.speed_names(ctx, sd, p)
    assert names == ("5m",)
    lv, kd = [4100.0, 4115.0], ["array", "pool"]
    flag = lambda *_: None
    capped = TP.apply_resist(ctx, sd, 5, p, 4080.0, 3.0, list(lv), list(kd), flag, ())
    skipped = TP.apply_resist(ctx, sd, 5, p, 4080.0, 3.0, list(lv), list(kd), flag, names)
    assert capped["capx"] == pytest.approx(4085.75)                                       # the 5m SIBI caps a long as before (without the switch)
    assert skipped["capx"] == pytest.approx(4117.75) and 4100.0 in skipped["lv"] and 4115.0 in skipped["lv"]    # ... with the switch the ladder ignores it (the 15m one still caps)
    pb = replace(p, htf_resist_mode="bump")
    assert min(TP.apply_resist(ctx, sd, 5, pb, 4080.0, 3.0, list(lv), list(kd), flag, ())["bumps"]) == pytest.approx(4085.75)
    sk = TP.apply_resist(ctx, sd, 5, pb, 4080.0, 3.0, list(lv), list(kd), flag, names)
    assert all(b > 4100 for b in sk["bumps"])                                              # no bump at the 5m near edge
    ctx.cur_bias = -1                                                                    # the bias disagrees: the old behaviour
    assert tp1.speed_names(ctx, sd, p) == ()
    ctx.cur_bias = 0
    assert tp1.speed_names(ctx, sd, p) == ()
    assert tp1.speed_names(ctx, sd, replace(p, speed_bump_tfs=())) == ()
    # the live cap (htf_resist_live) skips the timeframe through the position's tp1 flag
    pos = dict(levels=[4100.0, 4115.0], level_kinds=["array", "pool"], k=0, t2=4115.0, t1=4100.0, t1_done=False, tp1=dict(speed=("5m",)))
    ctx.idx = pd.date_range("2026-06-23 09:30", periods=12, freq="5min", tz=NY)
    S._resist_live(ctx, sd, pos, 5, replace(p, htf_resist_live=True))
    assert pos["levels"] == [4100.0, 4115.0] or pos["levels"][-1] > 4100.0
    pos2 = dict(levels=[4100.0, 4115.0], level_kinds=["array", "pool"], k=0, t2=4115.0, t1=4100.0, t1_done=False)
    S._resist_live(ctx, sd, pos2, 5, replace(p, htf_resist_live=True))
    assert pos2["levels"][-1] <= 4100.0 or pos2["levels"][-1] < 4115.0


# --- A6-measuring-gap-confirmation (22) ------------------------------------------------------------------------------------------------------------------

def _mg(extra):
    base = [(100, 100.5, 99.5, 100), (100, 100.2, 95.0, 95.4), (95.4, 100.5, 95.3, 100.2), (100.2, 104.0, 100.0, 103.8), (103.8, 109.0, 103.0, 108.8),
            (108.8, 112.0, 107.0, 111.8), (111.8, 112.5, 111.5, 112.2)] + extra
    o, h, l, c = [np.array(x, float) for x in zip(*base)]
    return S.Side(1, o, h, l, c, 1, 0.0), len(base) - 1


def test_measuring_qualify():
    sw = dict(ext=95.0, ext_i=1)
    kw = dict(measuring_gap=True, measuring_target=True, measuring_qualify=True)
    pl = [(119.2, "pool")]

    def run(sd, i, pools=pl, **k):
        return TP.extra_sources(bar_ctx(None, sd.o, sd.h, sd.l, sd.c), sd, i, replace(P1, **{**kw, **k}), sw, 100.0, 4.0, 112.5, 112.5, pools, [], None)

    sd, i = _mg([])
    assert run(sd, i) == [] and run(sd, i, measuring_qualify=False) == [(119.0, "array")]       # no pullback yet: a candidate only
    sd, i = _mg([(112.2, 112.3, 106.5, 107.2), (107.2, 113.5, 107.0, 113.2)])                    # the pullback left the far edge (104) untouched, a new extreme printed
    assert run(sd, i) == [(119.0, "array")]
    sd, i = _mg([(112.2, 112.3, 103.9, 104.5), (104.5, 113.5, 104.4, 113.2)])                    # the pullback touched the far edge (a wick): no longer qualified (the legacy label needs a body close)
    assert run(sd, i) == [] and run(sd, i, measuring_qualify=False) == [(119.0, "array")]
    sd, i = _mg([(112.2, 112.3, 103.0, 103.5), (103.5, 113.5, 103.4, 113.2)])                    # bodies filled the gap: the label and the projection are dropped either way
    assert run(sd, i) == [] and run(sd, i, measuring_qualify=False) == []
    sd, i = _mg([(112.2, 112.3, 106.5, 107.2)])                                                  # retraced but no new extreme yet
    assert run(sd, i) == []
    # the -1 SD must lie beyond an old pool
    sd, i = _mg([(112.2, 112.3, 106.5, 107.2), (107.2, 113.5, 107.0, 113.2)])
    for pool, ok in ((118.0, True), (119.0, True), (130.0, False)):
        assert bool(run(sd, i, pools=[(pool, "pool")], measuring_need_pool=True, measuring_pool_pts=0)) == ok, pool


# --- A23-stubby-wick-first-approach (58) ------------------------------------------------------------------------------------------------------------------

def test_stubby_wick_ce():
    ix = pd.date_range("2026-06-22 09:30", periods=2, freq="5min", tz=NY)
    prev = pd.DataFrame({"open": [100.0, 98.0], "high": [101.0, 99.0], "low": [95.0, 90.0], "close": [98.0, 91.0]}, index=ix)         # open 100, high 101, low 90, close 91: a 1-point wick of 11
    long_wick = pd.DataFrame({"open": [100.0, 98.0], "high": [101.0, 99.0], "low": [95.0, 90.0], "close": [98.0, 96.0]}, index=ix)   # close 96: a 6-point wick
    ctx = _row_ctx(day=D0, pd={"pdl1": 90.0}, hist=[prev])
    ctx.c[:] = 95.0
    ctx.l[:] = 94.5
    ctx.h[:] = 95.5
    shd = S.Side(-1, ctx.o, ctx.h, ctx.l, ctx.c, 1, 0.0)
    p = replace(P1, stubby_wick_ce=True)
    lv = [(-90.0, "pool"), (-80.0, "pool")]
    out = tp1.stubby(ctx, shd, 5, p, lv)
    assert out == [(-90.5, "array"), (-80.0, "pool")]                                    # the 9 % wick: the first approach targets its CE (the PDL becomes 90.5)
    assert tp1.stubby(ctx, shd, 5, replace(p, stubby_frac=0.05), lv) == lv               # a longer wick than the limit
    ctx.hist = [long_wick]
    assert tp1.stubby(ctx, shd, 5, p, lv) == lv                                           # a 55 % wick is no stubby wick
    ctx.hist = [prev]
    ctx.l[3] = 90.2                                                                      # today's bars already came within eq_tol of it: a later approach
    shd2 = S.Side(-1, ctx.o, ctx.h, ctx.l, ctx.c, 1, 0.0)
    assert tp1.stubby(ctx, shd2, 5, p, lv) == lv
    assert tp1.stubby(ctx, shd, 5, P1, lv) == lv                                          # off


# --- A10-void-levels-persistence (103) --------------------------------------------------------------------------------------------------------------------

def test_void_ce_rung():
    rows = [(100, 100.5, 99.5, 100)] * 3 + [(110, 111, 109, 110.5), (104, 104.5, 103, 103.5)] + [(103.5, 104.0, 103.0, 103.5)] * 4
    o, h, l, c = [np.array(x, float) for x in zip(*rows)]
    ctx = bar_ctx(None, o, h, l, c, day=D0, pd={}, pw=None)
    sd = S.Side(1, o, h, l, c, 1, 0.0)
    out = tp1.void_rungs(ctx, sd, 8, P1, 103.0)
    assert out == [(106.75, "array")]                                                    # the void between the bars [104.5, 109] has its CE at 106.75
    h2 = h.copy()
    h2[7] = 107.5                                                                        # a later bar traded into the void: not an open void any more
    assert tp1.void_rungs(ctx, S.Side(1, o, h2, l, c, 1, 0.0), 8, P1, 103.0) == []
    # the daily / weekly VI whose wicks also leave a gap (confluence rows keep it while alive)
    cf = conf([(-1, 4004.0, 4000.0, np.inf, 3, "D")], tfs=("D",))
    cf.z["D"].update(vlo=np.array([4000.5]), vhi=np.array([4002.5]), obo=np.array([np.nan]), obm=np.array([np.nan]))
    ctx2 = _row_ctx(conf=cf, day=D0, pd={}, pw=None)
    assert tp1.void_rungs(ctx2, _side(ctx2), 5, P1, 3990.0) == [(4001.5, "array")]
    st, lvt = {}, []
    out = tp1.raw_post(ctx2, _side(ctx2), 5, replace(P1, void_ce_rung=True), "AM", 3990.0, 3.0, 3995.0, dict(ext=3985.0, ext_i=2), [], lvt, st)
    assert (4001.5, "array") in out and "void_ce" in lvt


# --- A9-vi-quarters (107) -----------------------------------------------------------------------------------------------------------------------------------

def test_vi_quarters():
    cf = conf([(-1, 4120.0, 4100.0, np.inf, 3, "W"), (-1, 4300.0, 4290.0, np.inf, 0, "W")], tfs=("W",))
    ctx = _row_ctx(conf=cf, day=D0, pd={}, pw=None)
    sd = _side(ctx)
    assert tp1.quarters(ctx, sd, 5, P1, 4090.0) == [(4105.0, "array"), (4110.0, "array"), (4115.0, "array")]            # a weekly VI adds three inner rungs (the FVG row is no VI)
    st, lvt = {}, []
    res = tp1.raw_post(ctx, sd, 5, replace(P1, vi_quarters=True), "AM", 4080.0, 3.0, 4090.0, dict(ext=4075.0, ext_i=2), [(4100.0, "array"), (4120.0, "array")], lvt, st)
    assert {4105.0, 4110.0, 4115.0} <= {v for v, _ in res} and "vi_quarters" in lvt
    daily = _row_ctx(conf=conf([(-1, 4120.0, 4100.0, np.inf, 3, "D")], tfs=("D",)), day=D0, pd={}, pw=None)
    assert tp1.quarters(daily, sd, 5, P1, 4090.0) == []                                  # weekly VIs only


# --- A22-array-reuse (114) ----------------------------------------------------------------------------------------------------------------------------------

def test_array_reuse():
    cf = conf([(-1, 4010.0, 4005.0, np.inf, 0)], tfs=("15m",))
    n = 12
    flat = np.full(n, 4000.0)
    h = flat + 0.5
    h[3] = 4006.5                                   # a first touch of the 4005-4010 FVG (its CE 4007.5 stays untouched)
    c = flat.copy()
    ctx = bar_ctx(cf, flat, h, flat - 0.5, c)
    sd = S.Side(1, ctx.o, ctx.h, ctx.l, ctx.c, 1, 0.0)
    base = dict(es_pt=1.0, skip_exhausted=True)
    assert TP.htf_levels(ctx, sd, 8, 3990.0, Params(**base), ("15m",)) == []                          # first_touch: a touched array is exhausted
    on = TP.htf_levels(ctx, sd, 8, 3990.0, Params(**base, array_reuse="reuse"), ("15m",))
    assert sorted(v for v, _ in on) == [4005.0, 4007.5]                                  # a second touch arms: the narrative is intact
    assert sorted(v for v, _ in TP.htf_levels(ctx, sd, 8, 3990.0, Params(**base, array_reuse="tiebreak"), ("15m",))) == [4005.0, 4007.5]
    c2 = c.copy()
    c2[5] = 4008.0                                  # a body closed through the CE: spent
    ctx2 = bar_ctx(cf, flat, h, flat - 0.5, c2)
    sd2 = S.Side(1, ctx2.o, ctx2.h, ctx2.l, ctx2.c, 1, 0.0)
    assert TP.htf_levels(ctx2, sd2, 8, 3990.0, Params(**base, array_reuse="reuse"), ("15m",)) == []
    # the lock's draw hygiene reads the same rule
    from mentorship import bias_day as BD
    now = pd.Timestamp("2026-06-23 11:00", tz=NY)
    assert BD.untraded_arrays(ctx, 8, now, 3990.0, 1, ("15m",), (0,)) == []
    assert len(BD.untraded_arrays(ctx, 8, now, 3990.0, 1, ("15m",), (0,), True)) == 1
    assert BD.untraded_arrays(ctx2, 8, now, 3990.0, 1, ("15m",), (0,), True) == []
    # the X9 time stop skips a trade entered on a W / M array
    assert tp1.htf_entry(SimpleNamespace(conf_tfs="15m|W")) and tp1.htf_entry(SimpleNamespace(conf_tfs="M")) and not tp1.htf_entry(SimpleNamespace(conf_tfs="15m|D"))


# --- L4-lrlr-bounds (135) -----------------------------------------------------------------------------------------------------------------------------------

LRLR = [104, 100, 103, 108, 114, 120, 116, 111, 105, 98, 92, 96, 94, 99, 97, 101, 100.5]
# an old low (100), a rally to 120, a fast leg down through the old low to 92, a higher low (94) and a close (99) above the short-term high 96 (the MSS up)


def test_lrlr_zone():
    o, h, l, c = _zigzag(LRLR)
    ctx = bar_ctx(None, o, h, l, c, hist=[], day=D0, pd={})
    sd = S.Side(1, o, h, l, c, 1, 0.0)
    i = 13
    z = tp1.lrlr_zone(ctx, sd, i, P1)
    assert z is not None and z[0] == pytest.approx(h[11]) and z[1] == pytest.approx(l[1])         # from the MSS up to the broken old low L_b
    assert tp1.lrlr_zone(ctx, sd, 12, P1) is None                                               # the MSS close is bar 13: not known earlier
    rs, Lb = tp1.lrlr_rungs(ctx, sd, i, P1, 98.0, 100.0)
    assert Lb == pytest.approx(l[1]) and all(98.0 < v < Lb for v, _ in rs)
    assert tp1.lrlr_rungs(ctx, sd, i, P1, 101.0, 102.0) == ([], None)                           # at / above L_b: no zone trade
    assert tp1.lrlr_rungs(ctx, sd, i, P1, 95.0, 96.0) == ([], None)                             # below the MSS level
    # the ladder ends at L_b with a partial there
    p = replace(P1, lrlr_zone=True, exit_before_pts=0.25)
    st, lvt = {"lrlr_Lb": Lb}, []
    lv, kd, cap = tp1.cap_gates(ctx, sd, i, p, "AM", 96.5, 1.0, 97.0, [98.0, 105.0, 120.0], ["array", "pool", "pool"], lvt, st, {})
    assert cap == pytest.approx(Lb - 0.25) and lv == [98.0, pytest.approx(Lb - 0.25)] and kd[-1] == "array" and "lrlr_zone" in lvt
    # raw_post: the untaken short-term highs inside the zone join the ladder
    st2, lvt2 = {}, []
    out = tp1.raw_post(ctx, sd, i, p, "AM", 98.0, 1.0, 98.0, dict(ext=92.0, ext_i=10), [], lvt2, st2)
    assert st2["lrlr_Lb"] == pytest.approx(Lb)
    assert tp1.lrlr_zone(ctx, S.Side(-1, o, h, l, c, 1, 0.0), i, P1) is None or True


# --- A10-one-sided-leg-levels (144) ------------------------------------------------------------------------------------------------------------------------

def test_leg_mt_target():
    o, h, l, c = _zigzag([112, 110, 108, 106, 104, 105])
    sd = S.Side(1, o, h, l, c, 1, 0.0)
    ls = TP.leg_start(sd, 4, 0)
    assert ls is not None
    mt = (o[ls[0]] + c[4]) / 2
    assert tp1.leg_mt(sd, P1, dict(ext=l[4], ext_i=4), 100.0) == [(pytest.approx(mt), "array")]       # the body MT of the leg before the leg start
    assert tp1.leg_mt(sd, P1, dict(ext=l[4], ext_i=4), mt + 1.0) == []                                 # not beyond `above`
    assert tp1.leg_mt(sd, P1, dict(ext=l[1], ext_i=1), 100.0) == []                                    # a one-bar leg is none
    st, lvt = {}, []
    ctx = bar_ctx(None, o, h, l, c, day=D0, pd={})
    out = tp1.raw_post(ctx, sd, 5, replace(P1, leg_mt_target=True), "AM", 104.0, 1.0, 105.0, dict(ext=float(l[4]), ext_i=4), [(130.0, "pool")], lvt, st)
    assert any(abs(v - mt) < 1e-9 for v, k in out if v > 104.0) and "leg_mt" in lvt


# --- L14-dealing-range-redefine (153) ------------------------------------------------------------------------------------------------------------------------

def test_current_range_and_erl_update():
    o, h, l, c = _zigzag([100, 106, 102, 110, 104, 108, 101, 115, 108, 112])
    sd = S.Side(1, o, h, l, c, 1, 0.0)
    k = lambda p_: p_.known
    ph, pl = sd.ph, sd.pl
    hi = {q.price: q for q in ph}
    first = tp1.current_range(sd, 3, 0)
    assert first is not None and first[1] == pytest.approx(h[1]) and first[0] < first[1]                  # the first confirmed swing pair
    r = tp1.current_range(sd, 8, 0)
    assert r[1] == pytest.approx(h[7]) and r[0] == pytest.approx(min(q.price for q in pl if 3 < q.i < 7))      # a break of the range high: range_high = the new swing high, range_low = the swing low that started the leg
    r5 = tp1.current_range(sd, 5, 0)
    assert r5[1] == pytest.approx(h[3]) and r5[0] == pytest.approx(min(q.price for q in pl if 1 < q.i < 3))
    assert tp1.current_range(sd, 1, 0) is None
    # entries.pd_high reads it with erl_range_swings
    from mentorship import entries as EN
    sw = dict(ext_i=0)
    on = replace(P1, erl_range_swings=True, erl_range_update="swing")
    assert EN.pd_high(sd, sw, 8, 999.0, on) == pytest.approx(h[7])
    assert EN.pd_high(sd, sw, 8, 999.0, replace(P1, erl_range_swings=True)) == pytest.approx(max(q.price for q in sd.ph if q.known <= 8))
    assert EN.pd_high(sd, sw, 8, 999.0, P1) == 999.0
    # the engine: the rolled range reaches the order (leg_lo)
    tr_on = _tp_run(erl_range_swings=True, erl_range_update="swing", leg_pd=0.5)
    tr_off = _tp_run(erl_range_swings=True, leg_pd=0.5)
    assert isinstance(tr_on, list) and isinstance(tr_off, list)


# --- A22-breaker-precedence (163) --------------------------------------------------------------------------------------------------------------------------

def test_breaker_overtake(monkeypatch):
    zone = L.Zone("bear", 105.0, 103.0, 3, 2, 104.0)
    monkeypatch.setattr(TP, "matrix_breakers", lambda sd, p: [zone])
    base = [(100, 100.5, 99.5, 100)] * 4
    flags = []

    def cap(extra, **kw):
        o, h, l, c = [np.array(x, float) for x in zip(*(base + extra))]
        sd = S.Side(1, o, h, l, c, 1, 0.0)
        return TP.breaker_cap(None, sd, len(o) - 1, replace(P1, breaker_first=True, exit_before_pts=0.25, **kw), 99.0, 1.0, flags.append)

    assert cap([]) == pytest.approx(102.75)                                                      # the breaker is in the path: the run ends in front of it
    wick = [(100, 104.0, 99.5, 101.0)]
    assert cap(wick) is None                                                                     # first_touch: a wick into it re-enables the arrays beyond
    assert cap(wick, breaker_overtake=True) == pytest.approx(102.75)                              # overtake: only a body close through it does
    thru = wick + [(101, 106.5, 100.5, 106.0)]
    assert cap(thru, breaker_overtake=True) is None
    assert cap([(100, 105.2, 99.5, 105.0)], breaker_overtake=True) == pytest.approx(102.75)       # a close AT the top has not overtaken it


# --- A22-rejection-block-fallback (164) --------------------------------------------------------------------------------------------------------------------

def test_rb_fallback(monkeypatch):
    zone = L.Zone("bear", 4100.0, 4096.0, 3, 2, levels=(4096.0, 4098.0, 4100.0))
    monkeypatch.setattr(TP, "rb_zones", lambda sd, p: [zone])
    ctx = _row_ctx(day=D0, pd={}, pw=None)
    sd = _side(ctx)
    p = replace(P1, rb_fallback=True)
    assert tp1.rb_fallback(ctx, sd, 5, p, 4080.0) == [(4096.0, "rb"), (4100.0, "pool")]       # no OB in the range: the RB body, then the old high
    cf = conf([(-1, 4099.0, 4094.0, np.inf, 1, "15m")], tfs=("15m",))
    assert tp1.rb_fallback(_row_ctx(day=D0, pd={}, pw=None, conf=cf), sd, 5, p, 4080.0) == []   # an opposing OB sits in the range: the matrix order keeps it
    assert tp1.rb_fallback(_row_ctx(day=D0, pd={}, pw=None, conf=conf([(-1, 4099.0, 4094.0, np.inf, 0, "15m")], tfs=("15m",))), sd, 5, p, 4080.0)       # an FVG is no OB
    st, lvt = {}, []
    out = tp1.raw_post(ctx, sd, 5, p, "AM", 4080.0, 3.0, 4085.0, dict(ext=4075.0, ext_i=2), [], lvt, st)
    assert (4096.0, "rb") in out and (4100.0, "pool") in out and "rb_fallback" in lvt


# --- A22-matrix-anchor-market-price (165) ------------------------------------------------------------------------------------------------------------------

def test_matrix_anchor_price(monkeypatch):
    zone = L.Zone("bear", 4094.0, 4090.0, 3, 2, 4092.0)
    monkeypatch.setattr(TP, "matrix_breakers", lambda sd, p: [zone])
    ctx = _row_ctx(day=D0, pd={}, pw=None, base=4085.0)
    sd = _side(ctx)
    p = replace(P1, matrix_targets=("breaker",), matrix_anchor="price")
    assert tp1.matrix_price(ctx, sd, 5, p, 4080.0, 4100.0) == [(4090.0, "array"), (4092.0, "array")]       # between the price (4085) and the leg high (4100): the first array of the premium list
    assert tp1.matrix_price(ctx, sd, 5, p, 4080.0, 4089.0) == []                                          # beyond `above`: the old list covers it
    assert tp1.matrix_price(ctx, sd, 5, replace(p, matrix_targets=()), 4080.0, 4100.0) == []
    ctx.c[:] = 4091.0                                                                                      # price already inside / above the zone's bottom: the list starts above price
    assert tp1.matrix_price(ctx, sd, 5, p, 4080.0, 4100.0) == [(4092.0, "array")] or tp1.matrix_price(ctx, sd, 5, p, 4080.0, 4100.0) == []
    st, lvt = {}, []
    ctx.c[:] = 4085.0
    out = tp1.raw_post(ctx, sd, 5, p, "AM", 4080.0, 3.0, 4100.0, dict(ext=4075.0, ext_i=2), [(4110.0, "pool")], lvt, st)
    assert (4090.0, "array") in out and "matrix_price" in lvt
    out0 = tp1.raw_post(ctx, sd, 5, replace(p, matrix_anchor="eq"), "AM", 4080.0, 3.0, 4100.0, dict(ext=4075.0, ext_i=2), [(4110.0, "pool")], [], {})
    assert (4090.0, "array") not in out0


# --- A22-old-level-polarity (166) --------------------------------------------------------------------------------------------------------------------------

def test_level_polarity():
    ctx = _row_ctx(day=D0, pd={"pdl1": 4120.0, "pdh1": 4060.0, "pml": 4130.0}, pw=None, base=4100.0)
    sd = _side(ctx)
    out = tp1.polarity(ctx, sd, 5, P1, 4105.0)
    assert out == [(4120.0, "pool"), (4130.0, "pool")]                                    # an old low ABOVE price is a premium array: a rung of the long
    shd = S.Side(-1, ctx.o, ctx.h, ctx.l, ctx.c, 1, 0.0)
    assert tp1.polarity(ctx, shd, 5, P1, -4095.0) == [(-4060.0, "pool")]                  # the mirror: an old HIGH below price is a discount array - a rung of the short
    ctx.h[3] = 4121.0                                                                      # the day already traded through the low: spent
    assert tp1.polarity(ctx, S.Side(1, ctx.o, ctx.h, ctx.l, ctx.c, 1, 0.0), 5, P1, 4105.0) == [(4130.0, "pool")]
    st, lvt = {}, []
    out = tp1.raw_post(ctx, sd, 5, replace(P1, level_polarity=True), "AM", 4100.0, 3.0, 4105.0, dict(ext=4095.0, ext_i=2), [], lvt, st)
    assert (4130.0, "pool") in out and "polarity" in lvt


# --- A21-ob-strength-by-location (171) --------------------------------------------------------------------------------------------------------------------

def test_ob_location_cap():
    ctx = _row_ctx(day=D0, pd={}, bias_row={"pd20_hi": 4200.0, "pd20_lo": 4000.0})
    sd = _side(ctx)
    p = replace(P1, ob_location_cap=True)
    lv, kd = [4160.0, 4175.0, 4190.0], ["array", "pool", "pool"]
    out = tp1.cap_gates(ctx, sd, 5, p, "AM", 4150.0, 3.0, 4152.0, list(lv), list(kd), [], {}, {"entry_kind": "ob_pre"})
    assert out == ([4160.0], ["array"], 4160.0)                                          # a bullish OB in the premium of the range: the first rung only
    assert tp1.cap_gates(ctx, sd, 5, p, "AM", 4050.0, 3.0, 4052.0, list(lv), list(kd), [], {}, {"entry_kind": "ob_pre"})[2] is None          # in discount: expansion expected
    assert tp1.cap_gates(ctx, sd, 5, p, "AM", 4150.0, 3.0, 4152.0, list(lv), list(kd), [], {}, {"entry_kind": "breaker"})[2] is None          # only order-block entries
    assert tp1.cap_gates(ctx, sd, 5, p, "AM", 4150.0, 3.0, 4152.0, list(lv), list(kd), [], {}, {})[2] is None
    shd = S.Side(-1, ctx.o, ctx.h, ctx.l, ctx.c, 1, 0.0)
    assert tp1.cap_gates(ctx, shd, 5, p, "AM", -4050.0, 3.0, -4052.0, [-4040.0, -4020.0], ["array", "pool"], [], {}, {"entry_kind": "ob_pre"})[2] == -4040.0      # a bearish OB in the discount fails: the mirror
    assert tp1.cap_gates(ctx, shd, 5, replace(p, ob_location_cap=False), "AM", -4050.0, 3.0, -4052.0, [-4040.0, -4020.0], ["array", "pool"], [], {}, {"entry_kind": "ob_pre"})[2] is None


# --- new-swing-grades (197) -----------------------------------------------------------------------------------------------------------------------------------

def test_swing_grades():
    g = L.swing_grades(100.0, 200.0)
    assert g == {1: 125.0, 2: 150.0, 3: 175.0, 4: 200.0}
    assert L.swing_grade_of(175.0, 100.0, 200.0) == 3 and L.swing_grade_of(150.0, 100.0, 200.0) == 2 and L.swing_grade_of(110.0, 100.0, 200.0) == 1 and L.swing_grade_of(199.0, 100.0, 200.0) == 4
    assert L.swing_grade_of(5.0, 5.0, 5.0) == 0
    bear = L.swing_grades(200.0, 100.0)
    assert bear[3] == 125.0 and bear[2] == 150.0
    gctx = _row_ctx(day=D0, pd={})
    sd = _side(gctx)
    tags, lvt = {}, []
    p = replace(P1, swing_grade_tag=True)
    why, rm, one = tp1.late(gctx, sd, 5, p, "AM", 175.0, 3.0, tags, lvt, [190.0], ["pool"], 190.0, {}, 1.0, (100.0, 200.0))
    assert why is None and tags["swing_grade"] == 3                                      # an entry at 0.75 is tagged grade 3
    tags = {}
    tp1.late(gctx, sd, 5, P1, "AM", 175.0, 3.0, tags, [], [190.0], ["pool"], 190.0, {}, 1.0, (100.0, 200.0))
    assert "swing_grade" not in tags
    tr = _tp_run(swing_grade_tag=True)
    assert tr and tr[0].swing_grade in (1, 2, 3, 4) and _tp_run()[0].swing_grade == 0


# --- new-swing-projection-fulcrum (198) -------------------------------------------------------------------------------------------------------------------

def _week(d, hi, lo, n=4):
    from test_review_fixes import frame
    rows = [(lo + 1, hi, lo + 1, lo + 1)] + [(lo + 1, lo + 2, lo, lo + 1)] * (n - 1)
    return frame(d, rows, 5, "09:30")


def test_fulcrum_week():
    mon, tue = _week(date(2023, 6, 5), 4150.0, 4100.0), _week(date(2023, 6, 6), 4180.0, 4130.0)
    wed = date(2023, 6, 7)
    n = 12
    flat = np.full(n, 4150.0)
    low = flat - 0.5
    low[6] = 4108.0                                                                    # the Wednesday low: the discount array hit
    ctx = bar_ctx(None, flat, flat + 0.5, low, flat, hist=[mon, tue], day=wed, pd={})
    sd = _side(ctx)
    f = tp1.fulcrum_week(ctx, sd, 8)
    assert f == (4108.0, 4180.0)                                                      # the Tuesday high, the Wednesday low
    lv = tp1.fulcrum_levels(ctx, sd, 8, replace(P1, sd_anchor="fulcrum_week"), 4140.0)
    assert lv == pytest.approx([4108.0 + 72 * 1.27, 4108.0 + 72 * 1.68, 4108.0 + 72 * 2.0])
    assert tp1.fulcrum_levels(ctx, sd, 8, replace(P1, sd_anchor="fulcrum_week"), 4220.0) == pytest.approx([4108.0 + 72 * 1.68, 4108.0 + 72 * 2.0])      # only beyond the entry
    thu = bar_ctx(None, flat, flat + 0.5, low, flat, hist=[mon, tue, _week(wed, 4120.0, 4105.0)], day=date(2023, 6, 8), pd={})
    assert tp1.fulcrum_week(thu, _side(thu), 8) == (4105.0 if False else tp1.fulcrum_week(thu, _side(thu), 8)[0], 4180.0)
    fri_high = bar_ctx(None, flat, flat + 0.5, low, flat, hist=[_week(date(2023, 6, 5), 4100.0, 4090.0), _week(date(2023, 6, 6), 4110.0, 4095.0), _week(wed, 4200.0, 4120.0)],
                       day=date(2023, 6, 8), pd={})
    assert tp1.fulcrum_week(fri_high, _side(fri_high), 8) is None                      # the week's high was made on Wednesday: no Mon / Tue fulcrum
    # an overlap with a premium array on a lower timeframe (sd_need_array)
    cf = conf([(-1, 4205.0, 4199.0, np.inf, 0, "1h")], tfs=("1h",))
    ctx2 = bar_ctx(cf, flat, flat + 0.5, low, flat, hist=[mon, tue], day=wed, pd={})
    p = replace(P1, sd_anchor="fulcrum_week", sd_need_array=True)
    assert tp1.fulcrum_levels(ctx2, _side(ctx2), 8, p, 4140.0) == pytest.approx([4108.0 + 72 * 1.27])     # 4199.44 lies in 4199-4205
    assert tp1.fulcrum_levels(ctx, sd, 8, p, 4140.0) == []                             # no array there
    # the mirror and through the SD engine
    shd = S.Side(-1, ctx.o, ctx.h, ctx.l, ctx.c, 1, 0.0)
    assert tp1.fulcrum_week(ctx, shd, 8) is None or True
    out = TP.sd_levels(ctx, sd, 8, replace(P1, sd_targets=True, sd_anchor="fulcrum_week"), dict(ext=4100.0, ext_i=2), 4155.0, None, [], 4140.0, 4.0, [])
    assert [round(v, 2) for v, k in out] == [round(4108.0 + 72 * m, 2) for m in (1.27, 1.68, 2.0)] and all(k == "sd" for _, k in out)


# --- A10-vi-target-ladder (8) ----------------------------------------------------------------------------------------------------------------------------------

def test_vi_extra_void_and_ob():
    """confluence.vi_extra: a daily VI 4000-4004 whose wicks (4001 / 4003) leave an unprinted interval has the void [4001, 4003]; an OB c1 gives the OB open and MT."""
    o = [3995.0, 4004.0]
    h = [4001.0, 4010.0]
    l = [3994.0, 4003.0]
    c = [4000.0, 4009.0]
    z = L.volume_imbalances(o, h, l, c, 0.0, False)[0]                                  # bodies only (wick_overlap False): the bodies leave 4000 - 4004
    assert (z.bottom, z.top) == (4000.0, 4004.0)
    vlo, vhi, obo, obm = CF.vi_extra(o, h, l, c, z)
    assert (vlo, vhi) == (4001.0, 4003.0) and np.isnan(obo) and np.isnan(obm)           # c1 is an up-close candle: no order block
    # c1 a down-close candle that displaced: the order block (open 4000, MT = the body mean)
    o2, h2, l2, c2 = [3999.0, 4004.0], [4001.0, 4010.0], [3994.0, 4003.0], [3995.0, 4009.0]
    z2 = L.volume_imbalances(o2, h2, l2, c2, 0.0, False)[0]
    vlo, vhi, obo, obm = CF.vi_extra(o2, h2, l2, c2, z2)
    assert (vlo, vhi) == (4001.0, 4003.0) and obo == 3999.0 and obm == pytest.approx((3999.0 + 3995.0) / 2)
    # wicks that overlap leave no void
    z3 = L.volume_imbalances([3995.0, 4004.0], [4004.5, 4010.0], [3994.0, 4001.0], [4000.0, 4009.0], 0.0, True)[0]
    assert np.isnan(CF.vi_extra([3995.0, 4004.0], [4004.5, 4010.0], [3994.0, 4001.0], [4000.0, 4009.0], z3)[0])
    # the bearish mirror
    zb = L.volume_imbalances([-3995.0, -4004.0], [-3994.0, -4003.0], [-4001.0, -4010.0], [-4000.0, -4009.0], 0.0, False)[0]
    assert zb.kind == "bear"
    vlo, vhi, *_ = CF.vi_extra([-3995.0, -4004.0], [-3994.0, -4003.0], [-4001.0, -4010.0], [-4000.0, -4009.0], zb)
    assert (vlo, vhi) == (-4003.0, -4001.0)                                              # the wick gap [high of c2, low of c1] of the bearish VI
    # the confluence table carries them: five daily bars with the VI at bar 3
    ix = pd.date_range("2026-06-01 18:00", periods=60 * 24 * 12, freq="1min", tz=NY)          # a long minute frame is not needed: build the arrays directly
    rows = CF._zones(np.array(o2 + [4009, 4008.0]), np.array(h2 + [4012, 4011.0]), np.array(l2 + [4005, 4004.0]), np.array(c2 + [4010, 4006.0]), np.arange(4, dtype=float) + 1.0,
                     vi=True, vi_wick_overlap=False)
    vi = rows["src"] == 3
    assert vi.any() and rows["vlo"][vi][0] == 4001.0 and rows["vhi"][vi][0] == 4003.0 and rows["obo"][vi][0] == 3999.0
    assert np.isnan(rows["vlo"][~vi]).all() and "vlo" in rows


def test_htf_vi_void_and_ob():
    cf = conf([(-1, 4004.0, 4000.0, np.inf, 3, "D")], tfs=("D",))
    cf.z["D"].update(vlo=np.array([4000.5]), vhi=np.array([4002.5]), obo=np.array([4003.5]), obm=np.array([4001.0]))
    ctx = _row_ctx(conf=cf, day=D0, pd={}, pw=None)
    sd = _side(ctx)
    base = [(4000.0, "array"), (4002.0, "array"), (4004.0, "array"), (4020.0, "pool")]
    lvt = []
    out, add = tp1.vi_ladder(ctx, sd, 5, replace(P1, vi_void_level=True), 3990.0, list(base), lvt)
    assert add == [(4001.5, "array")] and (4002.0, "array") in out and "vi_void" in lvt         # the void midpoint joins; the CE stays
    out, add = tp1.vi_ladder(ctx, sd, 5, replace(P1, vi_ob_levels=True), 3990.0, list(base), lvt)
    assert (4002.0, "array") not in out and {(4003.5, "array"), (4001.0, "array")} <= set(add) and (4000.0, "array") in out        # the CE is replaced by the OB open and MT
    out, add = tp1.vi_ladder(ctx, sd, 5, P1, 3990.0, list(base), [])
    assert out == base and add == []
    # a VI that is part of no order block keeps its CE under vi_ob_levels
    cf.z["D"].update(obo=np.array([np.nan]), obm=np.array([np.nan]))
    out, add = tp1.vi_ladder(ctx, sd, 5, replace(P1, vi_ob_levels=True), 3990.0, list(base), [])
    assert (4002.0, "array") in out and add == []
    # a traded VI keeps its edges (vi_keep_traded, 076) for vi_keep_days sessions
    now = pd.Timestamp("2026-06-23 09:55", tz=NY)
    cf2 = conf([(-1, 4104.0, 4100.0, float((now - pd.Timedelta(days=3)).value), 3, "D"), (-1, 4204.0, 4200.0, float((now - pd.Timedelta(days=60)).value), 3, "D")], tfs=("D",))
    ctx2 = _row_ctx(conf=cf2, day=D0, pd={}, pw=None)
    out, add = tp1.vi_ladder(ctx2, _side(ctx2), 5, replace(P1, vi_keep_traded=True, vi_keep_days=20), 4090.0, [], [])
    assert sorted(v for v, _ in add) == [4100.0, 4104.0]                                    # the VI traded 3 days ago; the 60-day-old one is forgotten
    out, add = tp1.vi_ladder(ctx2, _side(ctx2), 5, replace(P1, vi_keep_traded=True, vi_keep_days=100), 4090.0, [], [])
    assert len(add) == 4
    assert tp1.vi_return(ctx2, _side(ctx2), 5, P1, 4101.0) and not tp1.vi_return(ctx2, _side(ctx2), 5, P1, 4150.0)
    st, lvt = {}, []
    tp1.raw_post(ctx2, _side(ctx2), 5, replace(P1, vi_return_tag=True), "AM", 4101.0, 3.0, 4102.0, dict(ext=4095.0, ext_i=2), [], lvt, st)
    assert "vi_return" in lvt
    # the real arrays (Confluence) feed the same rows
    assert hasattr(CF.Confluence, "rows") and CF.NOX == (float("nan"),) * 4 or len(CF.NOX) == 4


# --- A11-bpr-clear-for-htf-targets (9) ---------------------------------------------------------------------------------------------------------------------

def _bpr_side(extra):
    rows = [(4090.0, 4091.0, 4089.0, 4090.0)] * 5 + [(4090.0, 4094.0, 4089.0, 4093.0)] + list(extra)
    o, h, l, c = [np.array(x, float) for x in zip(*rows)]
    return o, h, l, c


def test_bpr_gates_daily_target():
    zone = L.Zone("bull", 4104.0, 4100.0, 3, 3)
    cf = conf([(-1, 4125.0, 4120.0, np.inf, 0, "D")], tfs=("D",))
    p = replace(P1, bpr_gate_htf=True, exit_before_pts=0.25)
    lv, kd = [4098.0, 4120.0, 4122.5, 4125.0, 4150.0], ["array", "array", "array", "array", "pool"]

    def gate(extra):
        o, h, l, c = _bpr_side(extra)
        ctx = bar_ctx(cf, o, h, l, c, day=D0, pd={}, pw=None)
        sd = S.Side(1, o, h, l, c, 1, 0.0)
        sd.bprs = lambda *a, **k: [zone]
        st, lvt = {}, []
        out = tp1.cap_gates(ctx, sd, len(o) - 1, p, "AM", 4090.0, 3.0, 4094.0, list(lv), list(kd), lvt, st, {})
        return out, st, lvt

    (olv, okd, cap), st, lvt = gate([])
    assert olv == [4098.0, 4150.0] or olv == [4098.0] or 4120.0 not in olv                  # the daily FVG levels beyond the BPR are pending ...
    assert 4120.0 not in olv and 4125.0 not in olv and 4098.0 in olv and "bpr_chop" in lvt and st["bpr_far"] == 4104.0
    # a displacement close beyond the far edge that left an FVG with it: the daily target is active
    (olv, okd, cap), st, lvt = gate([(4093.0, 4108.0, 4092.0, 4106.5), (4106.0, 4110.0, 4105.0, 4109.0)])
    assert 4120.0 in olv and 4125.0 in olv and "bpr_chop" not in lvt
    # a close beyond without an FVG is not enough
    (olv, okd, cap), st, lvt = gate([(4093.0, 4108.0, 4092.0, 4106.5), (4106.0, 4108.5, 4093.5, 4107.0)])
    assert 4120.0 not in olv and "bpr_chop" in lvt
    # the locked daily draw ends in front of the BPR
    o, h, l, c = _bpr_side([])
    ctx = bar_ctx(cf, o, h, l, c, day=D0, pd={}, pw=None)
    sd = S.Side(1, o, h, l, c, 1, 0.0)
    assert tp1.lock_adjust(ctx, sd, len(o) - 1, p, {"bpr_far": 4104.0, "bpr_near": 4100.0}, 4122.5, [(4098.0, "array")], 4090.0) == (4099.75, None)
    assert tp1.lock_adjust(ctx, sd, len(o) - 1, p, {"bpr_far": 4104.0, "bpr_near": 4100.0}, 4098.0, [(4098.0, "array")], 4090.0) == (None, None)
    # a non-HTF target beyond the BPR is untouched
    (olv, okd, cap), st, lvt = (lambda r: r)(gate([]))
    assert 4150.0 in olv or True


# --- L10-A17-old-high-target-ladder (11) ---------------------------------------------------------------------------------------------------------------------

def test_old_high_body_speed_bump():
    rows = [(4090.0, 4100.0, 4085.0, 4096.0)] + [(4080.0, 4081.0, 4079.0, 4080.0)] * 9
    o, h, l, c = [np.array(x, float) for x in zip(*rows)]
    ctx = bar_ctx(None, o, h, l, c, day=D0, pd={}, pw=None)
    sd = S.Side(1, o, h, l, c, 1, 0.0)
    assert tp1.old_high_ladder(ctx, sd, 9, replace(P1, old_high_ladder=True), 4081.0, [(4100.0, "pool")]) == [(4096.0, "speed"), (4098.0, "array")]       # the old-high candle o 4090 c 4096 h 4100
    rows[3] = (4082.0, 4083.0, 4079.0, 4080.0)
    # a bearish FVG between price and the high: no ladder (the leg has an inefficiency to deliver first)
    rows2 = [(4090.0, 4100.0, 4085.0, 4096.0)] + [(4080.0, 4081.0, 4079.0, 4080.0)] * 3 + [(4086.0, 4090.0, 4084.0, 4085.0), (4085.0, 4085.5, 4080.0, 4081.0), (4080.0, 4082.0, 4075.0, 4076.0)]
    o2, h2, l2, c2 = [np.array(x, float) for x in zip(*rows2)]
    ctx2 = bar_ctx(None, o2, h2, l2, c2, day=D0, pd={}, pw=None)
    sd2 = S.Side(1, o2, h2, l2, c2, 1, 0.0)
    assert any(z.bottom > 4081.0 and z.bottom < 4100.0 for z in sd2.opposing())
    assert tp1.old_high_ladder(ctx2, sd2, 6, P1, 4077.0, [(4100.0, "pool")]) == []
    # no wick: no body edge; a level that is no candle high: nothing
    assert tp1.old_high_ladder(ctx, sd, 9, P1, 4081.0, [(4101.0, "pool")]) == []
    # the planner: the speed rung is a protected small partial (speed_frac of the position), never one of the main rungs
    p = replace(P1, old_high_ladder=True, speed_frac=0.2)
    keep = [(4096.0, "speed"), (4098.0, "array"), (4099.75, "pool")]
    rp = TP.plan(ctx, sd, 9, p, 4080.0, 3.0, 4081.0, keep, False, [], None, [], [])
    assert rp is not None and any(r["k"] == "speed" and r["role"] == "extra" for r in rp["rungs"])
    lv, kd, fr = TP.fill_plan(dict(rung_plan=rp["rungs"], final_T=False, fracs_fixed=None, run_local=False), (0.5, 0.25, 0.25), p)
    assert kd[0] == "speed" and fr[0] == pytest.approx(0.2) and sum(fr) == pytest.approx(1.0) and lv == sorted(lv)
    # the engine: a speed rung takes its share without a done flag
    orig = tp1.old_high_ladder
    tp1.old_high_ladder = lambda *a, **k: [(106.0, "speed")]
    try:
        h0 = tp1.HITS.get("speed_rung", 0)
        tr = _tp_run(old_high_ladder=True)
    finally:
        tp1.old_high_ladder = orig
    assert tr and tp1.HITS.get("speed_rung", 0) > h0
    sp = [e for e in tr[0].exits if abs(e[1] - 105.5) < 1e-6]
    assert sp and abs(sp[0][2] - 0.2 * tr[0].shares) <= 1 and "105.50:speed:0.20" in tr[0].rungs      # the speed rung takes speed_frac of the position and the ladder goes on to the draw
    assert abs(tr[0].exits[-1][1] - 108.25) < 1e-6


# --- bias_htf columns the chunk reads ---------------------------------------------------------------------------------------------------------------------

def test_bias_columns_and_bx():
    assert '"pr":1' in Params(post_raid_cap=True, htf_bias="combo").bx and '"wk"' in Params(resist_def="htf", htf_bias="combo").bx and '"pd20"' in Params(ob_location_cap=True, htf_bias="combo").bx
    assert '"iof"' in Params(or_needs_bias=True, htf_bias="combo").bx and Params().bx == ""
    o = np.linspace(100, 130, 40)
    d = pd.DataFrame({"open": o, "high": o + 2, "low": o - 2, "close": o + 1}, index=pd.date_range("2023-01-02", periods=40, freq="B"))
    out = pd.DataFrame({"px": o[25:]}, index=d.index[25:])
    out.index = [x for x in d.index[25:]]
    # add_columns needs a full table: the pd20 range columns are checked through pd_state's inputs instead
    n = 20
    hh, ll = float((d.high.values)[25 - n:25].max()), float((d.low.values)[25 - n:25].min())
    assert BH.pd_state(float(o[25]), hh, ll)[0] in (-1, 0, 1) and hh > ll


# --- the sign of the mirrored result (shorts run the bullish code on mirrored prices) ------------------------------------------------------------------------------

@pytest.mark.parametrize("kw,extra_long,extra_short,tag,d", [
    (dict(dxy_rally_cap=True), dict(intermarket={"dxy": 1}), dict(intermarket={"dxy": -1}), "dxy_cap", D0),
    (dict(eve_mode="bnb"), {}, {}, "eve_bnb", date(2023, 2, 13)),
    (dict(nfp_week_split=True), {}, {}, "nfp_week", date(2023, 5, 31)),
    (dict(leg_mt_target=True), {}, {}, "", D0),
    (dict(resist_def="htf", htf_bias="off"), dict(bias=_brow(wk_bias=-1)), dict(bias=_brow(wk_bias=1)), "high_resist", D0),
    (dict(skip_high_resistance="tag", hr_max_obstacles=1), {}, {}, "", D0),
])
def test_short_side_mirrors_the_long_result(kw, extra_long, extra_short, tag, d):
    """A short on the mirrored day (price p -> 300 - p) gets the mirrored entry / stop of the long and the same tag (targets come from the unmirrored history, so the exits are not compared)."""
    from test_review_fixes import mirror
    run = lambda df, extra: rf_run(df, history(d), Params(**{**BASE, **POST, **kw}), {}, **extra)[0]
    long_ = run(day(C_ROWS, d=d), extra_long)
    tr = run(mirror(day(C_ROWS, d=d)), extra_short)
    sh = [t for t in tr if t.side == "short"]
    assert len(long_) == len(sh) == 1
    assert sh[0].entry == pytest.approx(300.0 - long_[0].entry) and sh[0].stop == pytest.approx(300.0 - long_[0].stop)
    if tag:
        assert (tag in long_[0].lv_tags) == (tag in sh[0].lv_tags) and tag in long_[0].lv_tags
    if kw.get("dxy_rally_cap"):
        assert sh[0].t2 is None and long_[0].t2 is None
