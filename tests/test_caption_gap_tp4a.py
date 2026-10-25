"""Caption-gap pass, package targets_partials #4/4, part A: the unit and engine tests of the 33 specs (management_partials_trailing_exits.md 44, 45, 46, 47, 48, 51, 56, 59, 60, 61, 62, 63, 65, 66, 75, 79,
80, 81, 84, 106, 125; models_setups_entries.md 46, 71, 122, 126, 140, 147; other.md 8; session_day_week_stops_frequency.md 22; stops_sizing_scaling_in.md 28, 70; times_sessions_macros.md 6, 19).
Hand-made bars and stub confluence tables (as test_caption_gap_tp3a.py), the tp4.py helpers called directly, scenario C through run_day for the order-level hooks. No platform-specific paths; nothing
here needs market data. The study variants and the no-look-ahead runs are in test_caption_gap_tp4b.py."""
from datetime import date
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from mentorship import levels as L, newscal, sm2, sm5, strategy as S, targets as TP, tp3, tp4, study
from mentorship.strategy import Params

from test_targets_partials import conf
from test_caption_gap_tp2a import D0, P, flat, hist_days, mk, side
from test_caption_gap_tp1a import _tp_run

NY = "America/New_York"
NEW_SWITCHES = (
    "weekly_hl_rung", "collapse_adr_frac", "runner_frac", "capture_zone", "runner_at_half", "runner_htf", "runner_htf_steps", "gap_speed_bump_partial", "partial_trigger", "eq60_rung", "subrange_first",
    "confluence_weight", "confluence_only", "void_ladder", "mm_first", "fulcrum_exit", "tgif_exits", "tgif_reentry_pm", "tgif_last_hour_cover", "proj_breaker_multi", "lrlr_ceiling", "lrlr_allow_beyond",
    "ob_target_tod", "consol_eq_target", "strength_hold", "consol_no_runner", "pm_ladder_am", "same_range_t1", "tf_target_cap", "void_draw", "void_rearm", "target_stage", "stage_drop", "rr_month_gate",
    "ladder_kind", "m1450_targets", "pm_carry_erase", "skip_balanced", "ladder_preset", "min_rr_final", "lrlr_zone",
)
KNOBS = ("capture_n", "runner_htf_pts", "bump_max_pts", "r_ladder", "r_be", "eq60_frac", "proj_k_max", "ob_pt_windows", "consol_eq_bars", "consol_adr_frac", "pm_sd_mult", "tf_cap_pts", "stage_targets",
         "stage_weeks", "rr_big", "rr_n_big", "rr_relaxed", "m1450_mid_open")
GAP_IDS = (
    "X3-041-projection-first-then-nwog", "X3-resting-1lot-partials-vi-final", "X3-layered-pool-ladder-runner", "X3-best-case-80-85-capture", "X3-half-range-runner-success", "X3-runner-htf-target",
    "X3-gap-speed-bump-before-pool", "X3-r-multiple-partials", "X3-partial-60m-eq", "X3-first-profit-premium-subrange", "X3-scaleout-skip-and-confluence", "X3-scale-through-void",
    "X3-mm-model-target", "X3-fulcrum-exit-modes", "M14-tgif-management", "L13-multi-sd-breaker-confluence", "L4-lrlr-ceiling", "A12-opposing-ob-time-of-day", "X1-consol-sweep-target-eq",
    "new-strength-no-return-discount-array", "B17-consolidation-no-runners", "M7-pm-mss-after-1300-targets", "M0-target-opposite-extreme-same-range", "L4-lrlr-repeated-buys", "L15-min-3R-prefer-5R",
    "new-tf-matches-objective", "new-sellstop-run-before-void-fill", "OT-target-progression", "new-rr-month-gate", "E8-2pct-split-experienced", "L15-min-rr-3", "T7-1450-targets",
    "T8-pm-carry-condition",
)


def pk(**kw):
    return Params(**{**P, **kw})


def kwl(ctx, sd, keep, **o):
    """The arguments of tp4.late for a long at 4100 with risk 4 (the ladder `keep` of exit prices)."""
    base = dict(ctx=ctx, sd=sd, sw=dict(ext=4090.0, ext_i=2, name="x"), i=8, session="AM", entry=4100.0, risk=4.0, keep=list(keep), keep_full=list(keep), draw=keep[-1][0], final_T=False, lvt=[], tags={},
                st={}, locked=False, fixed=None, leg_hi=4120.0)
    base.update(o)
    return base


def L4(p, ctx, sd, keep, **o):
    kw = kwl(ctx, sd, keep, **o)
    out = tp4.late(p=p, **kw)
    return out, kw


# --- defaults / validation / study variants ---------------------------------------------------------------------------------------------------------------

def test_new_switch_defaults_and_validation():
    p = Params()
    assert (p.weekly_hl_rung, p.collapse_adr_frac, p.runner_frac, p.capture_zone, p.capture_n, p.runner_at_half, p.runner_htf, p.runner_htf_pts, p.runner_htf_steps, p.gap_speed_bump_partial, p.bump_max_pts,
            p.partial_trigger, p.r_ladder, p.r_be, p.eq60_rung, p.eq60_frac, p.subrange_first, p.confluence_weight, p.confluence_only, p.void_ladder, p.mm_first, p.fulcrum_exit, p.tgif_exits,
            p.tgif_reentry_pm, p.tgif_last_hour_cover) == (False, 0.0, 0.0, False, 3, False, False, 2.0, False, 0.0, 2.0, "", (), 0.0, False, 0.25, False, False, False, False, 0.0, "", False, False, False)
    assert (p.proj_breaker_multi, p.proj_k_max, p.lrlr_ceiling, p.lrlr_allow_beyond, p.ob_target_tod, p.ob_pt_windows, p.consol_eq_target, p.consol_eq_bars, p.consol_adr_frac, p.strength_hold,
            p.consol_no_runner, p.pm_ladder_am, p.pm_sd_mult, p.same_range_t1, p.tf_target_cap, p.tf_cap_pts, p.void_draw, p.void_rearm, p.target_stage, p.stage_targets, p.stage_weeks, p.stage_drop,
            p.rr_month_gate, p.rr_big, p.rr_n_big, p.rr_relaxed, p.ladder_kind, p.m1450_targets, p.m1450_mid_open, p.pm_carry_erase, p.skip_balanced) == (
        False, 7.5, False, False, False, ((600, 660), (690, 720), (900, 960)), False, 60, 0.35, False, False, False, 1.5, False, False, ((1, 10.0), (5, 20.0), (15, 40.0)), False, False, False,
        (10.0, 15.0, 20.0), 4, False, False, 5.0, 1, 2.0, "", False, True, False, False)
    assert p.consol_bars == 20 and p.min_rr_final == 0.0 and p.ladder_preset == "" and not p.lrlr_zone         # the built defaults stay
    assert not tp4.any_on(p) and not tp4.raw_on(p) and not tp4.late_on(p)
    for kw in (dict(ladder_kind="x"), dict(fulcrum_exit="x"), dict(partial_trigger="x"), dict(tgif_exits="x"), dict(collapse_adr_frac=-1), dict(runner_frac=1.0), dict(capture_n=0), dict(runner_htf_pts=-1),
               dict(gap_speed_bump_partial=1.0), dict(bump_max_pts=0), dict(eq60_frac=1.0), dict(mm_first=1.0), dict(proj_k_max=0.5), dict(consol_eq_bars=2), dict(consol_adr_frac=0), dict(pm_sd_mult=0),
               dict(stage_weeks=0), dict(rr_big=0), dict(rr_n_big=0), dict(rr_relaxed=-1), dict(ob_pt_windows=((700, 600),)), dict(tf_cap_pts=((0, 5.0),)), dict(stage_targets=()), dict(stage_targets=(0.0,)),
               dict(partial_trigger="r_multiple"), dict(partial_trigger="r_multiple", r_ladder=((3.0, 1.0),)), dict(r_ladder=((0.0, 0.5),)), dict(ladder_preset="x"),
               dict(ladder_kind="half_3r", mm_first=0.8), dict(fulcrum_exit="ladder", partial_trigger="cc02_003"), dict(ladder_kind="half_3r", partial_mode="new"), dict(mm_first=0.8, ladder_preset="004")):
        with pytest.raises(ValueError):
            Params(**kw)
    for v in ("041", "096", "004", "037"):
        Params(ladder_preset=v)
    q = Params(partial_trigger="cc02_001")                               # the presets fill r_ladder / r_be
    assert q.r_ladder == ((1.0, 0.5), (3.0, 0.25)) and q.r_be == 2.0
    assert Params(partial_trigger="cc02_003").r_ladder == ((3.0, 0.5),) and Params(partial_trigger="cc02_003").r_be == 0.0
    assert Params(partial_trigger="r_multiple", r_ladder=((2.0, 0.4),), r_be=1.0).r_ladder == ((2.0, 0.4),)
    assert Params(tgif_exits="066").tgif_exits == "066" and Params(tgif_exits=True).tgif_exits is True
    assert set(NEW_SWITCHES) | set(KNOBS) <= set(Params.__dataclass_fields__)
    # the Silver Bullet bias switches and the default sb_model are untouched
    assert Params().sb_model is False and "sb_use_bias" in Params.__dataclass_fields__ and "want_all_engines" in Params.__dataclass_fields__


def test_inert_switch_note():
    with pytest.warns(UserWarning, match="inert switches \\(targets_partials #4/4\\)"):
        Params(runner_htf_steps=True, fulcrum_exit="ladder", confluence_only=True, lrlr_allow_beyond=True, tgif_last_hour_cover=True)


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
    assert all(v in study.DECISIONS for v in study._TP4_DECISIONS) and len(GAP_IDS) == 33
    names = list(study.DECISIONS)
    assert names.index("X3-041-projection-first-then-nwog") > names.index("X3-037-three-unit-ladder_ce")


# --- X3-041-projection-first-then-nwog (44) / X3-resting-1lot-partials-vi-final (45) ------------------------------------------------------------------------

def test_ladder_041():
    ctx = mk(flat(12), gaps=[("nwog", 4025.0, 4015.0, 4020.0)])
    sd = side(ctx)
    p = pk(ladder_preset="041")
    keep = [(4009.5, "sd"), (4040.0, "pool")]
    rungs, fr = tp4.ladder_041(ctx, sd, 8, p, 4000.0, 4.0, keep, {})
    assert [v for v, _ in rungs] == [4009.5, 4014.5, 4019.5, 4022.5] and fr == [0.33, 0.27, 0.2, 0.2]
    assert round(15 * fr[0]) == 5                                              # 5 of 15 units at rung 1
    # through tp3.late: the preset reaches the order (tags['fracs'])
    kw = dict(ctx=ctx, sd=sd, sw=dict(ext=3995.0, ext_i=2), i=8, session="AM", entry=4000.0, risk=4.0, keep=keep, keep_full=keep, draw=4040.0, final_T=False, lvt=[], tags={}, st={}, locked=False, fixed=None)
    why, k2, draw, _ = tp3.late(p=p, **kw)
    assert why is None and [v for v, _ in k2] == [4009.5, 4014.5, 4019.5, 4022.5] and kw["tags"]["fracs"] == pytest.approx((0.33, 0.27, 0.2, 0.2)) and "ladder_041" in kw["lvt"]
    # no projection below the NWOG / no NWOG above the entry: today's ladder
    assert tp4.ladder_041(ctx, sd, 8, p, 4000.0, 4.0, [(4040.0, "pool")], {}) is None
    assert tp4.ladder_041(mk(flat(12), gaps=[("nwog", 3990.0, 3980.0, 3985.0)]), sd, 8, p, 4000.0, 4.0, keep, {}) is None


def _vi_side(ctx):
    sd = side(ctx)
    sd.vis = lambda kind="bull": [L.Zone("bear", 4109.0, 4108.0, 5)] if kind == "bear" else []
    return sd


def test_ladder_096():
    ctx = mk(flat(12))
    sd = _vi_side(ctx)
    p = pk(ladder_preset="096")
    ex = lambda v, k: S._exit_px(v, k, p)
    keep = [(ex(4101.0, "pool"), "pool"), (4103.5, "array"), (ex(4112.0, "pool"), "pool")]            # pivot high 4101, next level 4104, the 4112 pool (exit prices)
    rungs, fr = tp4.ladder_096(ctx, sd, 8, p, 4090.0, 4.0, keep, {})
    assert [v for v, _ in rungs] == [4101.25, 4103.5, 4107.5] and fr == [0.2, 0.2, 0.6]
    assert all(abs(v - 4112.0) > 1 and abs(v - 4111.5) > 1 for v, _ in rungs)       # the pool itself is no rung
    # without a VI: today's ladder
    sd2 = side(ctx)
    sd2.vis = lambda kind="bull": []
    assert tp4.ladder_096(ctx, sd2, 8, p, 4090.0, 4.0, keep, {}) is None
    kw = dict(ctx=ctx, sd=sd, sw=dict(ext=4085.0, ext_i=2), i=8, session="AM", entry=4090.0, risk=4.0, keep=keep, keep_full=keep, draw=4111.5, final_T=False, lvt=[], tags={}, st={}, locked=False, fixed=None)
    why, k2, *_ = tp3.late(p=p, **kw)
    assert [v for v, _ in k2] == [4101.25, 4103.5, 4107.5] and "ladder_096" in kw["lvt"]


# --- X3-layered-pool-ladder-runner (46) ---------------------------------------------------------------------------------------------------------------------

def test_weekly_hl_rung():
    ctx = mk(flat(12), pw=(4120.0, 3900.0), hist=hist_days(rng=40.0))
    sd = side(ctx)
    assert tp4.weekly_hl_levels(ctx, sd, 8, pk(), 4001.0) == [(4120.0, "pool")]
    assert tp4.weekly_hl_levels(mk(flat(12), pw=(4000.1, 3900.0)), sd, 8, pk(), 4001.0) == []        # not above the price
    assert tp4.weekly_hl_levels(mk(flat(12), pw=None), sd, 8, pk(), 4001.0) == []
    ctx_t = mk(flat(12) + [(4000.0, 4125.0, 3999.0, 4000.0)], pw=(4120.0, 3900.0))                 # today's bars traded it: untaken only
    assert tp4.weekly_hl_levels(ctx_t, side(ctx_t), 12, pk(), 4001.0) == []
    sds = side(ctx, -1)                                                                          # a short: the prior week's LOW (side space)
    ctx2 = mk(flat(12), pw=(4120.0, 3990.0))
    assert tp4.weekly_hl_levels(ctx2, side(ctx2, -1), 8, pk(), -4001.0) == [(-3990.0, "pool")]
    lv = tp4.raw_post(ctx, sd, 8, pk(weekly_hl_rung=True), "AM", 4001.0, 4.0, 4001.0, dict(ext=3995.0, ext_i=2), 4005.0, [(4010.0, "pool")], [], {}, {})
    assert (4120.0, "pool") in lv and (4010.0, "pool") in lv


def test_collapse_and_runner():
    ctx = mk(flat(12), hist=hist_days(rng=40.0))                                                # ADR5 = 40
    sd = side(ctx)
    sw = dict(ext=4000.0, ext_i=2)
    p = pk(collapse_adr_frac=1.0, runner_frac=0.2)
    keep = [(4044.5, "pool"), (4060.0, "pool")]                                                 # a 45-pt move to the first pool (raw 4045)
    assert tp4.collapse_runner(ctx, sd, sw, 8, p, keep, None) == ([(4044.5, "pool")], [1.0])
    keep = [(4019.5, "pool"), (4060.0, "pool")]                                                 # a 20-pt move: the runner remains
    k2, fr = tp4.collapse_runner(ctx, sd, sw, 8, p, keep, None)
    assert k2 == keep and fr == pytest.approx([0.8, 0.2])
    k3, fr3 = tp4.collapse_runner(ctx, sd, sw, 8, pk(runner_frac=0.1), keep + [(4070.0, "pool")], None)
    assert len(k3) == 3 and fr3[-1] == pytest.approx(0.1) and sum(fr3) == pytest.approx(1.0)
    assert tp4.collapse_runner(ctx, sd, sw, 8, pk(collapse_adr_frac=1.0), [(4019.5, "pool")], None) is None
    # through late: the tags carry the shares
    (why, k4, *_), kw = L4(p, ctx, sd, [(4104.5, "pool"), (4110.0, "pool")], sw=dict(ext=4090.0, ext_i=2))
    assert why is None and kw["tags"]["fracs"] == pytest.approx((0.8, 0.2)) and "collapse_runner" in kw["lvt"]


# --- X3-best-case-80-85-capture (47) ------------------------------------------------------------------------------------------------------------------------

def test_capture_zone():
    p = pk(capture_zone=True)
    d4 = {}
    k2, fr = tp4.capture_cut(p, 4000.0, [(4040.0, "array")], None, d4)
    assert [round(v, 6) for v, _ in k2] == [4034.0, 4037.0, 4040.0] and fr == pytest.approx([1 / 3] * 3) and d4["capture_B"] == 4040.0
    # the last capture_n of a longer ladder: the earlier rungs and their shares stay
    k3, fr3 = tp4.capture_cut(pk(capture_zone=True, capture_n=2), 4000.0, [(4010.0, "pool"), (4020.0, "pool"), (4040.0, "pool")], [0.5, 0.25, 0.25], {})
    assert [round(v, 6) for v, _ in k3] == [4010.0, 4034.0, 4040.0] and fr3 == pytest.approx([0.5, 0.25, 0.25])
    # capture_b on a full fill: (37 / 40) = 0.925
    sdl = SimpleNamespace(sign=1, x=lambda v: v)
    tr = SimpleNamespace(shares=3, entry=4000.0, adds=[], exits=[(None, 4034.0, 1, "t1"), (None, 4037.0, 1, "t2"), (None, 4040.0, 1, "t3")], half_range_ok=None, capture_b=None, strength="")
    tp4.close_note(dict(tp4={"capture_B": 4040.0, "final": 4040.0}, side=sdl), tr, p)
    assert tr.capture_b == pytest.approx(0.925) and tr.half_range_ok is True


# --- X3-half-range-runner-success (48) ------------------------------------------------------------------------------------------------------------------------

def test_runner_at_half():
    ctx = mk(flat(12))
    sd = side(ctx)
    p = pk(runner_at_half=True)
    (why, k2, *_), kw = L4(p, ctx, sd, [(4020.0, "pool"), (4060.0, "pool")], entry=4000.0, risk=4.0)
    assert why is None and [v for v, _ in k2] == [4020.0, 4030.0] and kw["tags"]["tp4"]["final"] == 4060.0
    (_, k3, *_), _ = L4(p, ctx, sd, [(4035.0, "pool"), (4060.0, "pool")], entry=4000.0, risk=4.0)
    assert [v for v, _ in k3] == [4035.0, 4060.0]                                         # the previous rung is beyond the half: unchanged
    (_, k4, *_), _ = L4(p, ctx, sd, [(4060.0, "pool")], entry=4000.0, risk=4.0)
    assert [v for v, _ in k4] == [4060.0]
    # the report flag: a runner exit at 4030 of a 4060 final counts; at 4025 does not
    sdl = SimpleNamespace(sign=1, x=lambda v: v)
    for px, ok in ((4030.0, True), (4025.0, False)):
        tr = SimpleNamespace(shares=2, entry=4000.0, adds=[], exits=[(None, 4020.0, 1, "t1"), (None, px, 1, "t2")], half_range_ok=None, capture_b=None, strength="")
        tp4.close_note(dict(tp4={"final": 4060.0}, side=sdl), tr, p)
        assert tr.half_range_ok is ok


# --- X3-runner-htf-target (51) --------------------------------------------------------------------------------------------------------------------------

def test_runner_htf(monkeypatch):
    ctx = mk(flat(12))
    sd = side(ctx)
    monkeypatch.setattr(tp4, "tf_pools", lambda ctx, sd, i, above: [(4110.0, 15), (4120.0, 60)])
    keep = [(4105.0, "pool")]
    d4 = {}
    k2, fr = tp4.runner_htf_cut(ctx, sd, 8, pk(runner_htf=True, runner_frac=0.2), 4100.0, keep, None, d4)
    assert [v for v, _ in k2] == [4105.0, 4122.0] and fr == pytest.approx([0.8, 0.2]) and d4["runner_k"] == 1
    d5 = {}
    k3, fr3 = tp4.runner_htf_cut(ctx, sd, 8, pk(runner_htf=True, runner_htf_steps=True, runner_frac=0.2), 4100.0, keep, None, d5)
    assert [round(v, 2) for v, _ in k3] == [4105.0, 4110.25, 4122.0] and fr3 == pytest.approx([0.8, 0.1, 0.1])     # the 15m pool takes half of the runner only with steps
    # the runner's stop: once the rung before it filled, the stop is the previous rung - the stop pad
    ctx2 = mk(flat(12))
    pos = dict(left=2, k=1, levels=[4105.0, 4122.0], stop=4096.0, tp4=dict(runner_k=1), fill_i=3, fracs=(0.8, 0.2), level_kinds=["pool", "fixed"], day_trade=False)
    tp4.manage(ctx2, side(ctx2), pos, SimpleNamespace(strength=""), 8, None, pk())
    assert pos["stop"] == pytest.approx(4105.0 - pk().pad) and "runner_stop" in sm2.HITS
    pos["k"] = 0
    pos["stop"] = 4096.0
    tp4.manage(ctx2, side(ctx2), pos, SimpleNamespace(strength=""), 8, None, pk())
    assert pos["stop"] == 4096.0                                                           # before that rung filled: untouched
    # no HTF pool beyond: inert
    monkeypatch.setattr(tp4, "tf_pools", lambda ctx, sd, i, above: [(4110.0, 15)])
    assert tp4.runner_htf_cut(ctx, sd, 8, pk(runner_htf=True), 4100.0, keep, None, {}) is None


def test_tf_pools_ranks_the_swings():
    # a 5m book with a clear 60m swing high at 4150 (hour 10) and a 15m high at 4130, a prior-day high 4160 untaken
    rows = []
    for h_ in range(8, 13):
        for m in range(0, 60, 5):
            base = 4100.0 + (50.0 if (h_ == 10 and m == 25) else 0.0) + (30.0 if (h_ == 9 and m == 40) else 0.0)
            rows.append((4100.0, base + 1.0, 4099.0, 4100.0))
    o, h, l, c = [np.array(x, float) for x in zip(*rows)]
    idx = pd.date_range("2026-06-23 08:00", periods=len(o), freq="5min", tz=NY)
    ctx = SimpleNamespace(conf=None, idx=idx, tf=5, start=0, o=o, h=h, l=l, c=c, t=(idx.hour * 60 + idx.minute).values, pd={"pdh1": 4160.0}, pw=(4170.0, 4000.0), hist=hist_days())
    sd = S.Side(1, o, h, l, c, 1, 0.0)
    out = tp4.tf_pools(ctx, sd, len(o) - 1, 4101.0)
    ranks = {v: r for v, r in out}
    assert ranks.get(4160.0) == 1440 and ranks.get(4170.0) == 10080
    assert any(r == 60 and abs(v - 4151.0) < 1e-9 for v, r in out) and any(r == 15 for v, r in out)


# --- X3-gap-speed-bump-before-pool (56) -------------------------------------------------------------------------------------------------------------------

def test_gap_bump_rung():
    ctx = mk(flat(12, v=4000.0))
    sd = side(ctx)
    sd.opposing = lambda: [L.Zone("bear", 4104.0, 4103.0, 3)]
    keep = [(4109.5, "pool")]
    p = pk(gap_speed_bump_partial=0.25)
    assert tp4.bump_rung(ctx, sd, 8, p, 4100.0, keep) == 4104.25
    (why, k2, *_), kw = L4(p, ctx, sd, keep)
    assert why is None and k2 == [(4104.25, "speed"), (4109.5, "pool")] and kw["tags"]["fracs"] == pytest.approx((0.25, 0.75)) and "gap_speed_bump" in kw["lvt"]
    sd.opposing = lambda: [L.Zone("bear", 4106.0, 4103.0, 3)]                                    # a 3-pt gap is no speed bump
    assert tp4.bump_rung(ctx, sd, 8, p, 4100.0, keep) is None
    sd.opposing = lambda: [L.Zone("bear", 4104.0, 4103.0, 3)]
    sd.gaps = [L.Zone("bull", 4105.0, 4104.5, 3)]                                                # either polarity: the nearest gap first
    assert tp4.bump_rung(ctx, sd, 8, p, 4100.0, keep) == 4104.25
    sd.opposing = lambda: [L.Zone("bear", 4104.0, 4103.0, 3)]
    ctx2 = mk(flat(8) + [(4000.0, 4103.5, 3999.0, 4000.0)] + flat(3))                          # the gap was traded into after it formed: filled
    sd2 = side(ctx2)
    sd2.opposing = lambda: [L.Zone("bear", 4104.0, 4103.0, 3)]
    assert tp4.bump_rung(ctx2, sd2, 11, p, 4100.0, keep) is None


# --- X3-r-multiple-partials (59) ----------------------------------------------------------------------------------------------------------------------------

def test_r_ladder():
    ctx = mk(flat(12))
    sd = side(ctx)
    p = pk(partial_trigger="cc02_001")
    (why, k2, *_), kw = L4(p, ctx, sd, [(4120.0, "pool")], entry=4100.0, risk=4.0)
    assert why is None and [v for v, _ in k2] == [4104.0, 4112.0, 4120.0] and kw["tags"]["fracs"] == pytest.approx((0.5, 0.25, 0.25))
    assert kw["tags"]["be_at"] == 4108.0                                                  # break-even at 2R
    p3 = pk(partial_trigger="cc02_003")
    (_, k3, *_), kw3 = L4(p3, ctx, sd, [(4116.0, "pool")], entry=4100.0, risk=4.0)
    assert [v for v, _ in k3] == [4112.0, 4116.0] and kw3["tags"]["fracs"] == pytest.approx((0.5, 0.5)) and "be_at" not in kw3["tags"]      # a rung at 3R even with a pool at 4R
    # a rung beyond the final level is dropped
    (_, k4, *_), kw4 = L4(p, ctx, sd, [(4106.0, "pool")], entry=4100.0, risk=4.0)
    assert [v for v, _ in k4] == [4104.0, 4106.0]


# --- X3-partial-60m-eq (60) -----------------------------------------------------------------------------------------------------------------------------------

def test_eq60_rung(monkeypatch):
    ctx = mk(flat(12))
    sd = side(ctx)
    monkeypatch.setattr(tp4, "p60_bracket", lambda ctx, sd, i: (4080.0, 4120.0))
    p = pk(eq60_rung=True)
    keep = [(4114.5, "pool")]
    k2, fr = tp4.eq60_insert(ctx, sd, 8, p, 4090.0, keep, None)
    assert k2 == [(4099.5, "array"), (4114.5, "pool")] and fr == pytest.approx([0.25, 0.75])
    assert tp4.eq60_insert(ctx, sd, 8, p, 4105.0, keep, None) is None                       # the EQ is behind price
    assert tp4.eq60_insert(ctx, sd, 8, p, 4090.0, [(4098.0, "pool")], None) is None          # beyond the final level


def test_p60_bracket_uses_confirmed_pivots():
    rows = []
    for h_ in range(8, 14):
        for m in range(0, 60, 5):
            lo_ = 4080.0 if (h_ == 9) else 4100.0
            hi_ = 4120.0 if (h_ == 11) else 4105.0
            rows.append((4100.0, hi_, lo_, 4100.0))
    o, h, l, c = [np.array(x, float) for x in zip(*rows)]
    idx = pd.date_range("2026-06-23 08:00", periods=len(o), freq="5min", tz=NY)
    ctx = SimpleNamespace(conf=None, idx=idx, tf=5, start=0, o=o, h=h, l=l, c=c, t=(idx.hour * 60 + idx.minute).values)
    sd = S.Side(1, o, h, l, c, 1, 0.0)
    assert tp4.p60_bracket(ctx, sd, len(o) - 1) == (4080.0, 4120.0)
    assert tp4.p60_bracket(ctx, sd, 40) is None                                                  # at 11:20 the 11:00 high is not confirmed yet


# --- X3-first-profit-premium-subrange (61) -----------------------------------------------------------------------------------------------------------

def test_subrange_first(monkeypatch):
    cf = conf([(-1, 4028.0, 4026.0, np.inf, 0, "1h")], tfs=("1h",))
    ctx = mk(flat(12), cf=cf)
    sd = side(ctx)
    monkeypatch.setattr(tp3, "range60", lambda ctx, p, src=None: (3960.0, 4120.0))              # quarters of 40: 3960 / 4000 / 4040 / 4080 / 4120
    p = pk(subrange_first=True)
    keep = [(4014.5, "array"), (4015.0, "pool"), (4059.5, "array")]
    r = tp4.subrange_cut(ctx, sd, 8, p, 4010.0, 2.0, keep, None)
    assert r is not None and r[0][0] == (4025.5, "array") and (4015.0, "pool") not in r[0] and (4014.5, "array") not in r[0] and r[0][-1] == (4059.5, "array")
    assert tp4.subrange_cut(ctx, sd, 8, p, 4030.0, 2.0, keep, None) is None                    # the entry is already in the premium half of its quarter (4020 .. 4040)
    cf2 = conf([(-1, 4070.0, 4065.0, np.inf, 0, "1h")], tfs=("1h",))                              # the only array lies beyond the final level
    assert tp4.subrange_cut(mk(flat(12), cf=cf2), sd, 8, p, 4010.0, 2.0, keep, None) is None


# --- X3-scaleout-skip-and-confluence (62) --------------------------------------------------------------------------------------------------------------

def test_confluence_weight(monkeypatch):
    ctx = mk(flat(12))
    sd = side(ctx)
    score = {4110.0: 2, 4115.0: 0, 4120.0: 1}
    monkeypatch.setattr(tp4, "conf_score", lambda ctx, sd, i, p, entry, ext, leg_hi, px, st: score[px])
    keep = [(4110.0, "array"), (4115.0, "pool"), (4120.0, "pool")]
    p = pk(confluence_weight=True)
    sw = dict(ext=4090.0, ext_i=2)
    k2, fr = tp4.confluence_cut(ctx, sd, sw, 8, p, 4100.0, 4120.0, keep, [1 / 3] * 3, {})
    assert k2 == keep and fr == pytest.approx([3 / 6, 1 / 6, 2 / 6])
    k3, fr3 = tp4.confluence_cut(ctx, sd, sw, 8, pk(confluence_weight=True, confluence_only=True), 4100.0, 4120.0, keep, [1 / 3] * 3, {})
    assert k3 == [keep[0], keep[2]] and fr3 == pytest.approx([3 / 5, 2 / 5])
    monkeypatch.setattr(tp4, "conf_score", lambda *a: 0)
    assert tp4.confluence_cut(ctx, sd, sw, 8, p, 4100.0, 4120.0, keep, None, {}) is None


def test_conf_score_reads_the_edges_and_extensions():
    cf = conf([(-1, 4114.0, 4110.0, np.inf, 0, "1h")], tfs=("1h",))
    ctx = mk(flat(12), cf=cf)
    sd = side(ctx)
    p = pk()
    # leg 4090 -> 4110 (range 20): the 1.27 extension is 4115.4; the 100 % measured move from the entry 4100 is 4120
    assert tp4.conf_score(ctx, sd, 8, p, 4100.0, 4090.0, 4110.0, 4109.5, {}) == 1              # an array edge (the exit buffer short of 4110)
    assert tp4.conf_score(ctx, sd, 8, p, 4100.0, 4090.0, 4110.0, 4119.5, {}) == 1              # the measured move
    assert tp4.conf_score(ctx, sd, 8, p, 4100.0, 4090.0, 4110.0, 4105.0, {}) == 0
    assert tp4.conf_score(ctx, sd, 8, p, 4100.0, 4090.0, 4090.0, 4109.5, {}) == 1              # no leg: only the array edge scores


# --- X3-scale-through-void (63) ---------------------------------------------------------------------------------------------------------------------------------

def test_void_ladder(monkeypatch):
    ctx = mk(flat(12))
    sd = side(ctx)
    monkeypatch.setattr(tp4, "void_registry", lambda ctx, sd, i, p, above: [(4100.0, 4110.0, 4120.0)])
    p = pk(void_ladder=True)
    k2, fr = tp4.void_ladder_cut(ctx, sd, 8, p, 4090.0, [(4099.5, "array")], None, {})
    assert [v for v, _ in k2] == [4099.5, 4109.5, 4119.5] and fr == pytest.approx([1 / 3] * 3)
    # the near edge AND the CE already were rungs (void_targets): they are replaced; an earlier rung keeps its share
    k3, fr3 = tp4.void_ladder_cut(ctx, sd, 8, p, 4090.0, [(4095.0, "pool"), (4099.5, "array"), (4109.5, "array")], [0.4, 0.3, 0.3], {})
    assert [v for v, _ in k3] == [4095.0, 4099.5, 4109.5, 4119.5] and fr3 == pytest.approx([0.4, 0.2, 0.2, 0.2])
    monkeypatch.setattr(tp4, "void_registry", lambda ctx, sd, i, p, above: [(4200.0, 4210.0, 4220.0)])
    assert tp4.void_ladder_cut(ctx, sd, 8, p, 4090.0, [(4099.5, "array")], None, {}) is None      # the final level is no void


# --- X3-mm-model-target (65) ----------------------------------------------------------------------------------------------------------------------------------

def test_mm_first(monkeypatch):
    ctx = mk(flat(12))
    sd = side(ctx)
    monkeypatch.setattr(sm5, "_mm", lambda sd, ctx, session: dict(ext_i=2, broke=5, session=session))
    monkeypatch.setattr(sm5, "orig_consolidation", lambda sd, m, i, p: (4110.0, 4100.0, 4105.0))
    p = pk(mm_first=0.8)
    r = tp4.mm_first_ladder(ctx, sd, 8, p, "AM", 4090.0, 4.0, [(4111.5, "pool"), (4150.0, "pool")])
    assert r == ([(4099.5, "array"), (4111.5, "pool")], [0.8, pytest.approx(0.2)])
    monkeypatch.setattr(sm5, "_mm", lambda sd, ctx, session: None)
    assert tp4.mm_first_ladder(ctx, sd, 8, p, "AM", 4090.0, 4.0, [(4111.5, "pool")]) is None   # not an MM-model trade
    monkeypatch.setattr(sm5, "_mm", lambda sd, ctx, session: dict(ext_i=2, broke=5, session=session))
    assert tp4.mm_first_ladder(ctx, sd, 8, p, "AM", 4101.0, 4.0, [(4111.5, "pool")]) is None   # the boundary pays less than min_rr
    assert sm5.need_note(pk(mm_first=0.8)) is True


# --- X3-fulcrum-exit-modes (66) ---------------------------------------------------------------------------------------------------------------------------------

def test_fulcrum_exit(monkeypatch):
    ctx = mk(flat(12), day_tags="")
    sd = side(ctx)
    monkeypatch.setattr(TP, "sd_ranges", lambda ctx, sd, i, p, sw, leg_hi, rr: [("fulcrum", 4000.0, 4010.0)])
    p = pk(fulcrum_exit="ladder", sd_anchor="fulcrum", sd_targets=True)
    rungs, fr, trail = tp4.fulcrum_ladder(ctx, sd, dict(ext=3990.0, ext_i=2), 8, p, "AM", 3995.0, 4.0, 4010.0)
    assert [round(v, 3) for v, _ in rungs] == [4010.25, 4014.5, 4019.5] and fr == pytest.approx([0.33, 0.33, 0.34]) and trail is False
    pt = pk(fulcrum_exit="trail", sd_anchor="fulcrum", sd_targets=True, htf_bias="draw")
    monkeypatch.setattr(tp4, "bias_dir", lambda ctx, p, session, i: 1)
    rungs, fr, trail = tp4.fulcrum_ladder(ctx, sd, dict(ext=3990.0, ext_i=2), 8, pt, "AM", 3995.0, 4.0, 4010.0)
    assert [round(v, 3) for v, _ in rungs] == [4019.5] and fr == [1.0] and trail is True
    monkeypatch.setattr(tp4, "bias_dir", lambda ctx, p, session, i: 0)                          # no bias: the ladder
    assert tp4.fulcrum_ladder(ctx, sd, dict(ext=3990.0, ext_i=2), 8, pt, "AM", 3995.0, 4.0, 4010.0)[2] is False
    monkeypatch.setattr(tp4, "bias_dir", lambda ctx, p, session, i: 1)
    ctx_h = mk(flat(12), day_tags="post_holiday|tgif")                                           # a post-holiday day: the ladder
    assert tp4.fulcrum_ladder(ctx_h, sd, dict(ext=3990.0, ext_i=2), 8, pt, "AM", 3995.0, 4.0, 4010.0)[2] is False
    assert tp4.fulcrum_ladder(ctx, sd, dict(ext=3990.0, ext_i=2), 8, pk(fulcrum_exit="ladder"), "AM", 3995.0, 4.0, 4010.0) is None     # sd_anchor != fulcrum
    # through late: trail = one rung + the trail flag; on_fill puts the flag on the position
    (why, k2, *_), kw = L4(pt, ctx, sd, [(4030.0, "pool")], entry=3995.0, risk=4.0, sw=dict(ext=3990.0, ext_i=2), leg_hi=4010.0)
    assert why is None and [round(v, 3) for v, _ in k2] == [4019.5] and kw["tags"]["tp4"]["fulcrum_trail"] and "fulcrum_trail" in kw["lvt"]
    pos, tr = {}, SimpleNamespace(lv_tags="", rr_final=None, stage_pts=0.0)
    tp4.on_fill(ctx, sd, pos, tr, dict(tp4=kw["tags"]["tp4"], ext_i=2), 5, pt, 3995.0)
    assert pos["trail_now"] is True


# --- M14-tgif-management (75) -------------------------------------------------------------------------------------------------------------------------------

def _tgif_ctx(whi=4600.0, wlo=4500.0, today=None):
    day = date(2026, 6, 26)                                                                       # a Friday
    frames = []
    for k, d in enumerate((date(2026, 6, 22), date(2026, 6, 23), date(2026, 6, 24), date(2026, 6, 25))):
        idx = pd.date_range(pd.Timestamp(d, tz=NY) + pd.Timedelta(hours=9, minutes=30), periods=3, freq="5min")
        hi, lo = (whi, wlo + 20.0) if k == 2 else (whi - 30.0 - 5 * k, wlo)
        frames.append(pd.DataFrame({"open": lo + 10, "high": [hi, lo + 30, lo + 30], "low": [lo, lo + 5, lo + 5], "close": lo + 10}, index=idx))
    rows = today or [(4572.0, 4574.0, 4570.0, 4572.0)] * 12
    o, h, l, c = [np.array(x, float) for x in zip(*rows)]
    idx = pd.date_range("2026-06-26 09:30", periods=len(o), freq="5min", tz=NY)
    return SimpleNamespace(conf=None, idx=idx, tf=5, start=0, o=o, h=h, l=l, c=c, t=(idx.hour * 60 + idx.minute).values, day=day, hist=frames, day_tags="tgif_short", eth={})


def test_tgif_066_levels_and_fractions():
    ctx = _tgif_ctx()
    sd = S.Side(-1, ctx.o, ctx.h, ctx.l, ctx.c, 1, 0.0)
    p = pk(tgif_zone=True, tgif_exits="066")
    tg = TP.tgif_info(ctx, sd, 8, p, -4592.0)
    assert tg is not None and tg["levels"] == pytest.approx([-4580.0, -4577.5, -4575.0, -4572.5, -4570.0]) and tg["held"] is True
    assert len(TP.tgif_info(ctx, sd, 8, pk(tgif_zone=True, tgif_exits=True), -4592.0)["levels"]) == 4        # the built zone levels are unchanged
    rp = TP.plan(ctx, sd, 8, p, -4592.0, 3.0, -4590.0, [(-4560.0, "pool")], False, [], tg, [], [])
    lv, kd, fr = TP.fill_plan(dict(rung_plan=rp["rungs"], fracs_fixed=rp["fracs_fixed"], final_T=False, run_local=False), (0.5, 0.25, 0.25), p)
    assert lv == pytest.approx([-4580.0, -4577.5, -4575.0, -4572.5, -4570.0]) and fr == [0.15, 0.15, 0.5, 0.1, 0.1] and set(kd) == {"exact"}
    # the week's high no longer holds once Friday traded above it
    ctx_b = _tgif_ctx(today=[(4590.0, 4620.0, 4588.0, 4590.0)] * 12)
    assert TP.tgif_info(ctx_b, S.Side(-1, ctx_b.o, ctx_b.h, ctx_b.l, ctx_b.c, 1, 0.0), 8, p, -4592.0)["held"] is False


def test_tgif_066_roll_and_last_hour_cover():
    ctx = _tgif_ctx()
    # side space (a short mirrored): ascending levels L20 .. L30; a swing high (real) = a swing low here
    sd = S.Side(-1, ctx.o, ctx.h, ctx.l, ctx.c, 1, 0.0)
    lv066 = [-4580.0, -4577.5, -4575.0, -4572.5, -4570.0]
    sd.pl = [L.Pivot(5, -4585.0, 7)]                                                              # the latest swing low (side): the short's latest swing high 4585
    pos = dict(left=5, k=3, levels=list(lv066), stop=-4600.0, fills=3, fracs=(0.15, 0.15, 0.5, 0.1, 0.1), level_kinds=["exact"] * 5, fill_i=2, tp4=dict(tgif066=lv066, tgif_l25_k=2))
    pos["trade"] = tr = SimpleNamespace(strength="")
    p = pk(tgif_exits="066", tgif_zone=True)
    tp4.manage(ctx, sd, pos, tr, 8, None, p)
    assert pos["stop"] == pytest.approx(-4585.0 - p.tick)                                         # raise_stop(pos, last pivot + tick) in side space
    pos2 = dict(pos, k=2, stop=-4600.0, tp4=dict(tgif066=lv066, tgif_l25_k=2))
    tp4.manage(ctx, sd, pos2, tr, 8, None, p)
    assert pos2["stop"] == -4600.0                                                                 # the L25 rung has not filled
    # from 15:00 a swing inside the 20 .. 30 % band: one resting cover just short of it for everything left
    rows = [(4590.0, 4592.0, 4588.0, 4590.0)] * 12
    ctx2 = _tgif_ctx(today=rows)
    ctx2.idx = pd.date_range("2026-06-26 14:30", periods=12, freq="5min", tz=NY)
    ctx2.t = (ctx2.idx.hour * 60 + ctx2.idx.minute).values
    sd2 = S.Side(-1, ctx2.o, ctx2.h, ctx2.l, ctx2.c, 1, 0.0)
    sd2.ph = [L.Pivot(8, -4574.0, 10)]                                                            # a real pivot low at 4574 (side -4574)
    sd2.pl = []
    pos3 = dict(left=4, k=3, levels=list(lv066), stop=-4600.0, fracs=(0.15, 0.15, 0.5, 0.1, 0.1), level_kinds=["exact"] * 5, fill_i=2, tp4=dict(tgif066=lv066, tgif_roll=True), final_T=False)
    pp = pk(tgif_exits="066", tgif_zone=True, tgif_last_hour_cover=True)
    ctx2.start = 0
    tp4.manage(ctx2, sd2, pos3, tr, 10, None, pp)                                                  # 15:20 (bar 10)
    assert pos3["levels"] == pytest.approx([-4580.0, -4577.5, -4575.0, -4574.5]) and pos3["tp4"]["cover"] == pytest.approx(-4574.5)       # the cover at the pivot - exit_before_pts (4574.5 real)
    assert pos3["fracs"][-1] == pytest.approx(1.0 - 0.8)
    pos4 = dict(pos3, levels=list(lv066), tp4=dict(tgif066=lv066, tgif_roll=True), fracs=(0.15, 0.15, 0.5, 0.1, 0.1))
    ctx3 = ctx2
    ctx3.idx = pd.date_range("2026-06-26 13:00", periods=12, freq="5min", tz=NY)
    ctx3.t = (ctx3.idx.hour * 60 + ctx3.idx.minute).values
    tp4.manage(ctx3, sd2, pos4, tr, 10, None, pp)
    assert "cover" not in pos4["tp4"]                                                              # before 15:00 nothing


def test_tgif_pm_slot_and_after_close():
    ctx = SimpleNamespace(day=date(2026, 6, 26), day_tags="tgif_short")
    p = pk(tgif_reentry_pm=True, tgif_zone=True)
    assert tp4.tgif_pm_slot(ctx, p, "PM", 850) and not tp4.tgif_pm_slot(ctx, p, "PM", 780) and not tp4.tgif_pm_slot(ctx, p, "AM", 850) and not tp4.tgif_pm_slot(ctx, pk(), "PM", 850)
    assert not tp4.tgif_pm_slot(SimpleNamespace(day=date(2026, 6, 25), day_tags="tgif_short"), p, "PM", 850)


# --- L13-multi-sd-breaker-confluence (79) --------------------------------------------------------------------------------------------------------------------

def test_proj_breaker_multi(monkeypatch):
    ctx = mk(flat(12))
    sd = side(ctx)
    # two bullish breaker legs (A, B): (4090, 4100) and (4087.5, 4100)... k=6.5 of the first and k=4.0 of the second land at 4165.0 / 4165.0 +- 0.75
    legs = [(4090.0, 4100.0, 6), (4095.0, 4100.0, 7)]
    monkeypatch.setattr(tp4, "breaker_legs", lambda ctx, sd, i, p: legs)
    p = pk(proj_breaker_multi=True, sd_cluster_ticks=4)
    lv = [(4110.0, "pool")]
    st = {}
    out = tp4.proj_breaker_multi_levels(ctx, sd, 8, p, 4101.0, lv, st)
    # k x (B-A): leg 1 (range 10): 4100 + 10k; leg 2 (range 5): 4100 + 5k  -> 4150 (k=5.0 | k=10 beyond the cap): the clusters need >= 2 legs inside 1 pt
    assert all(k == "proj" for _, k in out) and all(v > 4110.0 for v, _ in out) and len(out) >= 1
    # two legs whose 6.5 and 4.0 projections land 0.75 pt apart produce ONE proj rung; a single-leg level none
    legs2 = [(4090.0, 4100.0, 6), (4083.75, 4100.0, 7)]            # leg 1: 4100 + 6.5 x 10 = 4165 | leg 2 (range 16.25): 4100 + 4 x 16.25 = 4165
    monkeypatch.setattr(tp4, "breaker_legs", lambda ctx, sd, i, p: legs2)
    out2 = tp4.proj_breaker_multi_levels(ctx, sd, 8, p, 4101.0, lv, {})
    assert [round(v, 2) for v, _ in out2 if abs(v - 4165.0) < 1.0] == [4165.0]
    legs3 = [(4090.0, 4100.0, 6), (4083.5, 4100.0, 7)]             # 4165 vs 4165.0 + 0.25 x ... = 6.5/4.0 -> 4165 and 4165.0 (+0.75): within the 1-pt tolerance
    monkeypatch.setattr(tp4, "breaker_legs", lambda ctx, sd, i, p: [legs3[0]])
    assert tp4.proj_breaker_multi_levels(ctx, sd, 8, p, 4101.0, lv, {}) == []                      # a single-leg level produces none
    # a cluster within 1 pt of a pool confirms it (report tag)
    monkeypatch.setattr(tp4, "breaker_legs", lambda ctx, sd, i, p: legs2)
    st2 = {}
    tp4.proj_breaker_multi_levels(ctx, sd, 8, p, 4101.0, [(4110.0, "pool"), (4165.5, "pool")], st2)
    assert st2.get("conf_pools") == [4165.5]


def test_breaker_legs_find_a_bullish_breaker():
    # swing low 4000 (bar 2), swing high 4020 (bar 6), the sweep to 3990 (bar 9), then a body close over 4020 (bar 12)
    rows = [(4010.0, 4012.0, 4008.0, 4010.0), (4005.0, 4006.0, 4001.0, 4003.0), (4003.0, 4004.0, 4000.0, 4002.0), (4003.0, 4008.0, 4002.5, 4007.0), (4007.0, 4012.0, 4006.0, 4011.0),
            (4011.0, 4016.0, 4010.0, 4015.0), (4015.0, 4020.0, 4014.0, 4018.0), (4018.0, 4017.0, 4010.0, 4012.0), (4012.0, 4013.0, 4003.0, 4004.0), (4004.0, 4005.0, 3990.0, 3992.0),
            (3992.0, 3999.0, 3991.0, 3998.0), (3998.0, 4008.0, 3997.0, 4006.0), (4006.0, 4024.0, 4005.0, 4022.0), (4022.0, 4026.0, 4020.0, 4025.0), (4025.0, 4027.0, 4023.0, 4026.0),
            (4026.0, 4028.0, 4024.0, 4027.0)]
    ctx = mk(rows)
    sd = side(ctx)
    legs = tp4.breaker_legs(ctx, sd, len(rows) - 1, pk())
    assert any(abs(A - 3990.0) < 1e-9 and abs(B - 4020.0) < 1e-9 for A, B, _ in legs), legs


# --- L4-lrlr-ceiling (80) / L4-lrlr-repeated-buys (122) ------------------------------------------------------------------------------------------------------

def _lrlr_rows():
    # an old low (4050) formed, price fell through it (a close below), swept 4030, now rallying: U = 4050
    rows = [(4070.0, 4071.0, 4069.0, 4070.0), (4066.0, 4067.0, 4060.0, 4062.0), (4062.0, 4064.0, 4050.0, 4055.0), (4056.0, 4062.0, 4054.0, 4060.0), (4060.0, 4066.0, 4059.0, 4064.0)]
    rows += [(4064.0, 4065.0, 4046.0, 4048.0), (4048.0, 4049.0, 4040.0, 4042.0), (4042.0, 4043.0, 4030.0, 4034.0), (4034.0, 4040.0, 4033.0, 4039.0), (4039.0, 4044.0, 4038.0, 4043.0)]
    return rows + flat(3, v=4043.0)


def test_lrlr_ceiling():
    ctx = mk(_lrlr_rows())
    sd = side(ctx)
    sw = dict(ext=4030.0, ext_i=7)
    assert tp4.lrlr_ceiling_level(ctx, sd, sw, 12, pk(), 4040.0) == (4050.0, 4050.0)
    assert tp4.lrlr_ceiling_level(ctx, sd, sw, 12, pk(), 4055.0) == (None, 4050.0)
    assert tp4.lrlr_ceiling_level(mk(flat(12)), side(mk(flat(12))), dict(ext=3990.0, ext_i=7), 11, pk(), 4000.0) == (None, None)           # no broken old low: no ceiling
    p = pk(lrlr_ceiling=True)
    keep = [(4049.0, "array"), (4060.0, "pool")]
    lvt = []
    why, k2 = tp4.lrlr_cap(ctx, sd, sw, 12, p, 4040.0, 4.0, keep, lvt)
    assert why is None and k2 == [(4049.0, "array")]                                          # the 4049 rung is within a point of the cap (U - exit_before_pts): no extra rung
    assert "hrlr" in lvt                                                                         # 4060 is high resistance (dropped)
    why, k3 = tp4.lrlr_cap(ctx, sd, sw, 12, pk(lrlr_ceiling=True, lrlr_allow_beyond=True), 4040.0, 4.0, keep, [])
    assert why is None and k3 == keep
    why, _ = tp4.lrlr_cap(ctx, sd, sw, 12, p, 4049.0, 2.0, keep, [])                            # no room left to the ceiling: no order
    assert why == "x_lrlr_ceiling"
    why, _ = tp4.lrlr_cap(ctx, sd, sw, 12, p, 4055.0, 3.0, keep, [])                            # price at / past the ceiling: no new long (L4-lrlr-repeated-buys)
    assert why == "x_lrlr_ceiling"
    assert tp4.lrlr_cap(ctx, sd, sw, 12, pk(lrlr_ceiling=True, lrlr_allow_beyond=True), 4055.0, 3.0, keep, [])[0] is None
    assert tp4.lrlr_cap(ctx, sd, sw, 12, p, 4075.0, 3.0, keep, [])[0] is None                    # review fix: far above the broken low is not 'at the ceiling'
    # the targets 4040 / 4060 of the spec: the ladder ends at 4049.5
    why, k4 = tp4.lrlr_cap(ctx, sd, sw, 12, p, 4035.0, 4.0, [(4040.0, "array"), (4060.0, "array")], [])
    assert [v for v, _ in k4] == [4040.0, 4049.5]
    # through late
    (why5, k5, *_), kw = L4(p, ctx, sd, [(4040.0, "array"), (4060.0, "array")], entry=4035.0, risk=4.0, sw=sw, i=12)
    assert why5 is None and [v for v, _ in k5] == [4040.0, 4049.5] and "lrlr_ceiling" in kw["lvt"]


def test_lrlr_zone_is_already_built():
    assert Params(lrlr_zone=True).lrlr_zone is True and callable(__import__("mentorship.tp1", fromlist=["lrlr_zone"]).lrlr_zone)


# --- A12-opposing-ob-time-of-day (81) ------------------------------------------------------------------------------------------------------------------------

def test_ob_target_tod():
    from mentorship import entries as EN
    ctx = mk(flat(12))
    sd = side(ctx)
    p = pk(ob_target_tod=True, ob_targets_1m=True)
    sd2 = side(ctx)
    z = L.Zone("bear", 4112.0, 4110.0, 3, 2, 4111.0)
    import mentorship.entries as E2
    orig = E2.opposing_obs
    E2.opposing_obs = lambda sd, i, p: [z]
    try:
        assert [k for _, k in EN.ob_target_levels(sd2, 8, 4100.0, p)] == ["ob", "ob"]
        assert {k for _, k in EN.ob_target_levels(sd2, 8, 4100.0, pk(ob_targets_1m=True))} == {"array"}
    finally:
        E2.opposing_obs = orig
    pos = dict(level_kinds=["ob", "pool"], fracs=(0.5, 0.5), tp4=dict(ob_tod=True), k=0)
    assert tp4.ob_skip(pos, 0, 620, 5, p) is False                                                # 10:20 inside 10:00-11:00: fills
    assert tp4.ob_skip(pos, 0, 820, 5, p) is True and pos["fracs"] == (0.0, 1.0)                  # 13:40: skipped, the share moves to the next rung
    assert tp4.ob_skip(dict(level_kinds=["pool"], fracs=(1.0,), tp4=dict(ob_tod=True)), 0, 820, 5, p) is False      # only OB rungs
    assert tp4.ob_skip(dict(level_kinds=["ob"], fracs=(1.0,), tp4={}), 0, 820, 5, p) is False


# --- X1-consol-sweep-target-eq (84) --------------------------------------------------------------------------------------------------------------------------

def test_consol_eq_target(monkeypatch):
    rows = [(4105.0, 4110.0, 4100.0, 4105.0)] * 60 + [(4100.0, 4101.0, 4099.0, 4100.5)] + flat(3, v=4101.0)
    ctx = mk(rows, hist=hist_days(rng=40.0))
    sd = side(ctx)
    sw = dict(ext=4099.0, ext_i=60, level=4100.0)
    monkeypatch.setattr(tp4, "bias_dir", lambda ctx, p, session, i: 1)
    p = pk(consol_eq_target=True, htf_bias="draw")
    keep = [(4105.0, "array"), (4109.5, "pool"), (4130.0, "pool")]
    r = tp4.consol_eq_cut(ctx, sd, sw, 62, p, "AM", 4101.0, 1.0, keep)
    assert r is not None and [v for v, _ in r[0]] == [4104.5] and r[1] is None                    # the final rung = EQ - exit_before_pts, 4110 is no rung
    r2 = tp4.consol_eq_cut(ctx, sd, sw, 62, pk(consol_eq_target=True, htf_bias="draw", runner_frac=0.2), "AM", 4101.0, 1.0, keep)
    assert [v for v, _ in r2[0]] == [4104.5, 4130.0] and r2[1] == pytest.approx([0.8, 0.2])        # or kept as a runner
    monkeypatch.setattr(tp4, "bias_dir", lambda ctx, p, session, i: 0)
    assert tp4.consol_eq_cut(ctx, sd, sw, 62, p, "AM", 4101.0, 1.0, keep) is None                  # needs the HTF bias
    monkeypatch.setattr(tp4, "bias_dir", lambda ctx, p, session, i: 1)
    wide = [(4105.0, 4130.0, 4090.0, 4105.0)] * 60 + [(4100.0, 4101.0, 4085.0, 4100.5)] + flat(3, v=4101.0)
    assert tp4.consol_range(mk(wide, hist=hist_days(rng=40.0)), side(mk(wide)), dict(ext=4085.0, ext_i=60), 62, p) is None      # a 40-pt range is no consolidation (< 0.35 x ADR5)


# --- new-strength-no-return-discount-array (106) ------------------------------------------------------------------------------------------------------------

def test_strength_hold():
    ctx = mk(flat(14, v=4560.0))
    sd = side(ctx)
    p = pk(strength_hold=True)
    pos = dict(left=4, k=0, levels=[4565.0, 4570.0, 4580.0], level_kinds=["array", "pool", "pool"], fracs=(0.5, 0.25, 0.25), stop=4540.0, fill_i=3,
               tp4=dict(ob1=(4550.0, 4553.0), hi0=4575.0, strength=True))
    tr = SimpleNamespace(strength="")
    sd.h = np.array(sd.h, float)
    sd.l = np.array(sd.l, float)
    sd.h[8], sd.l[8] = 4576.0, 4560.0                                                              # a new high, no low inside OB1's body (4550-4553)
    tp4.manage(ctx, sd, pos, tr, 8, None, p)
    assert tr.strength == "strong" and pos["levels"] == [4570.0, 4580.0] and pos["level_kinds"] == ["pool", "pool"] and pos["fracs"] == pytest.approx((0.5, 0.5))
    pos2 = dict(left=4, k=0, levels=[4565.0, 4570.0, 4580.0], level_kinds=["array", "pool", "pool"], fracs=(0.5, 0.25, 0.25), stop=4540.0, fill_i=3,
                tp4=dict(ob1=(4550.0, 4553.0), hi0=4575.0, strength=True))
    tr2 = SimpleNamespace(strength="")
    sd.l[6] = 4552.0                                                                                # a dip into OB1's body
    sd.l[7] = 4552.0
    tp4.manage(ctx, sd, pos2, tr2, 7, None, p)
    tp4.manage(ctx, sd, pos2, tr2, 8, None, p)
    assert tr2.strength == "normal" and pos2["levels"] == [4565.0, 4570.0, 4580.0] and pos2["fracs"] == (0.5, 0.25, 0.25)         # the ladder is unchanged
    # OB1 at the fill: the nearest bullish OB body under the fill price
    rows = flat(4) + [(4556.0, 4557.0, 4549.0, 4550.0)] + [(4551.0, 4562.0, 4550.0, 4561.0)] + flat(3, v=4561.0)
    ctx3 = mk(rows)
    sd3 = side(ctx3)
    assert tp4.ob1_body(ctx3, sd3, dict(ext_i=2), 6, 4561.0) == (4550.0, 4556.0)


def test_strength_off_without_an_ob1():
    ctx = mk(flat(8))
    sd = side(ctx)
    pos, tr = {}, SimpleNamespace(lv_tags="", rr_final=None, stage_pts=0.0)
    tp4.on_fill(ctx, sd, pos, tr, dict(tp4=dict(strength=True, final=4100.0), ext_i=2, leg_hi0=4005.0), 5, pk(strength_hold=True), 4001.0)
    assert "strength" not in pos["tp4"] and "ob1" not in pos["tp4"]


# --- B17-consolidation-no-runners (125) ----------------------------------------------------------------------------------------------------------------

def test_consol_no_runner():
    cf = conf([(-1, 4210.0, 4205.0, np.inf, 0, "W")], tfs=("W",))
    ctx = mk(flat(12), cf=cf, day_tags="consol_day")
    sd = side(ctx)
    p = pk(consol_no_runner=True)
    keep = [(4110.0, "pool"), (4120.0, "pool"), (4204.5, "array")]                                 # the last rung is the weekly array
    (why, k2, *_), kw = L4(p, ctx, sd, keep, entry=4100.0, risk=4.0)
    assert why is None and k2 == [(4110.0, "pool"), (4120.0, "pool")] and kw["tags"]["fracs"] == pytest.approx((0.8, 0.2)) and "consol_no_runner" in kw["lvt"]
    ctx2 = mk(flat(12), cf=cf, day_tags="", hist=[])                                              # an untagged day: unchanged
    (_, k3, *_), kw3 = L4(p, ctx2, side(ctx2), keep, entry=4100.0, risk=4.0)
    assert k3 == keep and not kw3["tags"].get("fracs")
    assert tp4.b17_consolidation(ctx, p) and not tp4.b17_consolidation(ctx2, p)
    (_, k4, *_), kw4 = L4(pk(consol_no_runner=True, runner_frac=0.3), ctx, side(ctx), keep, entry=4100.0, risk=4.0)      # no runner on such a day, whatever runner_frac says
    assert kw4["tags"]["fracs"] == pytest.approx((0.8, 0.2))


# --- M7-pm-mss-after-1300-targets (models 46) ---------------------------------------------------------------------------------------------------------------

def test_pm_ladder_includes_am_highs():
    idx = pd.date_range("2026-06-23 09:30", "2026-06-23 14:00", freq="5min", tz=NY)
    n = len(idx)
    t = (idx.hour * 60 + idx.minute).values
    h = np.full(n, 4003.0)
    l = np.full(n, 3999.0)
    h[6] = 4009.0                                          # an AM swing high at 10:00 (untaken)
    h[12] = 4007.0                                         # a second one at 10:30, TAKEN by the 11:30 bar
    h[24] = 4008.0
    h[36] = 4005.0                                         # the lunch high (12:30)
    o = (h + l) / 2
    ctx = SimpleNamespace(conf=None, idx=idx, tf=5, start=0, o=o, h=h, l=l, c=o.copy(), t=t, day=D0, hist=hist_days(), pd={}, sess={"lunch": (4005.0, 3998.0, 810)}, pw=None)
    sd = S.Side(1, ctx.o, ctx.h, ctx.l, ctx.c, 1, 0.0)
    i = int(np.flatnonzero(t >= 820)[0])
    p = pk(pm_ladder_am=True)
    out = tp4.pm_am_ladder_levels(ctx, sd, i, p, "PM", 3995.0, 4010.0, 4001.0)
    vals = sorted(v for v, _ in out)
    assert 4005.0 in vals and 4009.0 in vals                                          # the lunch high and an untaken AM swing high
    assert 4010.0 + 1.5 * (4010.0 - 3995.0) in vals                                   # then the SD projection of the MSS leg (pm_sd_mult)
    assert 4008.0 in vals and 4007.0 not in vals                                       # the 11:30 swing high is untaken, the 10:30 one was taken by it
    assert tp4.pm_am_ladder_levels(ctx, sd, i, p, "AM", 3995.0, 4010.0, 4001.0) == []   # PM orders only
    assert [v for v, _ in tp4.pm_am_ladder_levels(ctx, sd, i, p, "PM", 3995.0, 4010.0, 4006.0)] == [4009.0, 4008.0, 4032.5] or sorted(v for v, _ in tp4.pm_am_ladder_levels(ctx, sd, i, p, "PM", 3995.0, 4010.0, 4006.0)) == [4008.0, 4009.0, 4032.5]       # above 4006 the lunch high is gone
    lv = tp4.raw_post(ctx, sd, i, p, "PM", 4001.0, 4.0, 4001.0, dict(ext=3995.0, ext_i=2), 4010.0, [(4020.0, "pool")], [], {}, {})
    assert (4005.0, "pool") in lv and (4020.0, "pool") in lv


# --- M0-target-opposite-extreme-same-range (models 71) ------------------------------------------------------------------------------------------------

def test_t1_is_opposite_extreme_of_raided_range():
    ctx = mk(flat(12))
    ctx.sess = {"prev_pm": (4150.0, 4080.0, 0), "london": (4140.0, 4070.0, 300)}
    sd = side(ctx)
    p = pk(same_range_t1=True)
    keep = [(4110.0, "array"), (4149.5, "pool"), (4170.0, "pool")]
    r = tp4.range_session_t1(ctx, sd, dict(name="prev_pm"), 8, p, 4090.0, 4.0, keep)
    assert r[0][0] == pytest.approx(S._exit_px(4150.0, "pool", p)) and r[-1] == (4170.0, "pool") and (4110.0, "array") not in r      # the other end of the raided range comes first
    assert tp4.range_session_t1(ctx, sd, dict(name="pdl1"), 8, p, 4090.0, 4.0, keep) is None        # not a session range
    assert tp4.range_session_t1(ctx, sd, dict(name="prev_pm"), 8, p, 4149.0, 4.0, keep) is None       # beyond min_rr only
    (_, k2, *_), kw = L4(p, ctx, sd, keep, entry=4090.0, risk=4.0, sw=dict(name="london", ext=4085.0, ext_i=2))
    assert k2[0][0] == pytest.approx(S._exit_px(4140.0, "pool", p)) and "same_range_t1" in kw["lvt"]


# --- L15-min-3R-prefer-5R (models 126) / L15-min-rr-3 (stops 70) ------------------------------------------------------------------------------------------

def test_min_rr_final_filter_tag_and_record():
    ctx = mk(flat(12))
    sd = side(ctx)
    p3 = pk(min_rr_final=3.0)
    (why, _, *_), kw = L4(p3, ctx, sd, [(4104.0, "pool")], entry=4100.0, risk=2.0)                  # +4 / 2 = 2R
    assert why == "x_min_rr_final"
    (why, _, *_), kw = L4(p3, ctx, sd, [(4106.0, "pool")], entry=4100.0, risk=2.0)                  # +6 / 2 = 3R
    assert why is None and kw["tags"]["tp4"]["rr_final"] == pytest.approx(3.0) and "rr5" not in kw["lvt"]
    (why, _, *_), kw = L4(p3, ctx, sd, [(4112.0, "pool")], entry=4100.0, risk=2.0)                  # 6R: tagged rr5
    assert why is None and "rr5" in kw["lvt"]
    # risk 2, final rung +5 -> rejected at 3.0 (2.5R); +7 -> accepted
    (w5, _, *_), _ = L4(p3, ctx, sd, [(4105.0, "pool")], entry=4100.0, risk=2.0)
    (w7, _, *_), _ = L4(p3, ctx, sd, [(4107.0, "pool")], entry=4100.0, risk=2.0)
    assert (w5, w7) == ("x_min_rr_final", None)
    # the trade carries the value
    pos, tr = {}, SimpleNamespace(lv_tags="", rr_final=None, stage_pts=0.0)
    tp4.on_fill(ctx, sd, pos, tr, dict(tp4=dict(rr_final=3.0)), 5, p3, 4100.0)
    assert tr.rr_final == 3.0


def test_min_rr_final_engine_records_rr_final():
    base = _tp_run()
    assert len(base) == 1 and base[0].rr_final is None                                               # scenario C: entry 100.4 .. 108.25
    tr = _tp_run(min_rr_final=5.0)
    assert len(tr) == 1 and tr[0].rr_final == pytest.approx(6.04, abs=0.05) and "rr5" in tr[0].lv_tags
    assert len(_tp_run(min_rr_final=7.0)) == 0


# --- new-tf-matches-objective (models 140) ---------------------------------------------------------------------------------------------------------------

def test_tf_target_cap():
    ctx = mk(flat(12))                                                                                # a 5m run: the cap is 20 pts
    p = pk(tf_target_cap=True)
    assert tp4.tf_cap(ctx, p, 4000.0, [(4010.0, "pool"), (4030.0, "pool")]) == [(4010.0, "pool"), (4020.0, "fixed")]
    assert tp4.tf_cap(ctx, p, 4000.0, [(4010.0, "pool"), (4015.0, "pool")]) == [(4010.0, "pool"), (4015.0, "pool")]
    assert tp4.tf_cap(ctx, p, 4000.0, [(4025.0, "pool")]) is None                                      # T1 beyond the cap needs a higher timeframe
    ctx1 = mk(flat(12))
    ctx1.tf = 1
    assert tp4.tf_cap(ctx1, p, 4000.0, [(4010.0, "pool"), (4030.0, "pool")]) == [(4010.0, "pool")] or tp4.tf_cap(ctx1, p, 4000.0, [(4009.0, "pool"), (4030.0, "pool")])[-1] == (4010.0, "fixed")
    ctx60 = mk(flat(12))
    ctx60.tf = 60                                                                                     # no entry for 60m: unlimited
    assert tp4.tf_cap(ctx60, p, 4000.0, [(4030.0, "pool")]) == [(4030.0, "pool")]
    (why, *_), _ = L4(p, ctx, side(ctx), [(4125.0, "pool")], entry=4100.0, risk=4.0)
    assert why == "x_tf_cap"


# --- new-sellstop-run-before-void-fill (models 147) ------------------------------------------------------------------------------------------------------

def test_void_draw_and_second_raid(monkeypatch):
    ctx = mk(flat(12), hist=hist_days(rng=40.0))
    sd = side(ctx)
    monkeypatch.setattr(tp4, "void_registry", lambda ctx, sd, i, p, above: [(4120.0, 4125.0, 4130.0), (4300.0, 4305.0, 4310.0)])
    p = pk(void_draw=True)
    (why, k2, *_), kw = L4(p, ctx, sd, [(4110.0, "pool"), (4150.0, "pool")], entry=4100.0, risk=4.0)
    assert why is None and k2[-1] == (S._exit_px(4130.0, "array", p), "array") and (4150.0, "pool") not in k2 and "void_draw" in kw["lvt"]       # the void top is the final target
    (_, k3, *_), _ = L4(pk(void_draw=True), ctx, sd, [(4110.0, "pool"), (4150.0, "pool")], entry=4100.0, risk=4.0, locked=True, final_T=True, draw=4150.0)
    (_, k3, d3, _f3), kw3 = L4(pk(void_draw=True), ctx, sd, [(4110.0, "pool"), (4150.0, "pool")], entry=4100.0, risk=4.0, locked=True, final_T=True, draw=4150.0)
    assert k3[-1] == (S._exit_px(4130.0, "array", p), "array") and d3 == k3[-1][0] and "void_draw_lock" in kw3["lvt"]     # review fix (owner q. 8): a nearer void replaces the LOCKED draw
    (_, k3b, d3b, _f), _ = L4(pk(void_draw=True), ctx, sd, [(4110.0, "pool"), (4125.0, "pool")], entry=4100.0, risk=4.0, locked=True, final_T=True, draw=4125.0)
    assert k3b[-1] == (4125.0, "pool") and d3b == 4125.0                                            # the locked draw nearer than the void stays
    # the stop-out re-arms once; the next order must sweep the same lows
    state = {}
    ctx.state7 = state
    done = {"AM": True}
    tr = SimpleNamespace(lv_tags="void_draw", exits=[(None, 4095.0, 1, "stop")], session="AM", swept="pdl1", side="long")
    pr = pk(void_draw=True, void_rearm=True)
    tp4.after_close(ctx, {}, tr, "long", done, "AM", state, pr)
    assert done["AM"] is False and state["void_rearm"]["swept"] == "pdl1" and state["void_rearmed"] is True
    (why, *_), _ = L4(pr, ctx, sd, [(4110.0, "pool")], entry=4100.0, risk=4.0, sw=dict(name="pdl2", ext=4090.0, ext_i=2))
    assert why == "x_void_rearm_other"
    (why, *_), kw = L4(pr, ctx, sd, [(4110.0, "pool")], entry=4100.0, risk=4.0, sw=dict(name="pdl1", ext=4090.0, ext_i=2))
    assert why is None and "void_rearm" in kw["lvt"]
    done2, state2 = {"AM": True}, dict(state)
    tp4.after_close(ctx, {}, tr, "long", done2, "AM", state2, pr)
    assert done2["AM"] is True                                                                       # only once
    tr_ok = SimpleNamespace(lv_tags="void_draw", exits=[(None, 4110.0, 1, "t1")], session="AM", swept="pdl1", side="long")
    done3 = {"AM": True}
    tp4.after_close(ctx, {}, tr_ok, None, done3, "AM", {}, pr)
    assert done3["AM"] is True                                                                       # a winner does not re-arm


def test_void_registry_unfilled_voids():
    rows = flat(4, v=4000.0) + [(4000.0, 4001.0, 3999.0, 4000.5), (3990.0, 3992.0, 3988.0, 3990.0)] + flat(4, v=3990.0)       # a gap down: low[4] > ... (a bearish void above a long)
    ctx = mk(rows)
    sd = side(ctx)
    zs = tp4.void_registry(ctx, sd, 9, pk(), 3990.0)
    assert any(abs(z[0] - 3992.0) < 1e-9 and abs(z[2] - 3999.0) < 1e-9 for z in zs), zs
    assert tp4.void_registry(ctx, sd, 9, pk(), 4000.0) == []                                          # the void is below the price it starts from: no target above


# --- OT-target-progression (other 8) ----------------------------------------------------------------------------------------------------------------

def _wk_rows(nets, start=date(2026, 6, 1)):
    from datetime import timedelta
    return [dict(date=start + timedelta(days=7 * k + 1), net=n) for k, n in enumerate(nets)]


def test_target_stage_steps():
    p = pk(target_stage=True)
    d = date(2026, 6, 1)
    from datetime import timedelta

    def stage_at(rows, week):
        return tp4.stage_for(rows, d + timedelta(days=7 * week), p)

    rows = _wk_rows([1.0] * 9)
    assert stage_at(rows, 3) == (0, 3) and stage_at(rows, 4) == (1, 0) and stage_at(rows, 8) == (2, 0) and stage_at(rows, 9) == (2, 1)       # 10 -> 15 after 4 weeks, 15 -> 20 after 8
    assert tp4.stage_params(rows, d + timedelta(days=7 * 4), p).t1_fixed_pts == 15.0 and tp4.stage_params(rows, d + timedelta(days=7 * 8), p).t1_fixed_pts == 20.0
    assert tp4.stage_params(rows, d + timedelta(days=7 * 3), p).t1_fixed_pts == 10.0
    assert tp4.stage_params(rows, d, pk()).t1_fixed_pts == 0.0                                           # off: p unchanged
    rows2 = _wk_rows([1.0, 1.0, -1.0, 1.0, 1.0, 1.0, 1.0, 1.0])                                         # a losing week at week 3 resets the count
    assert stage_at(rows2, 6) == (0, 3) and stage_at(rows2, 7) == (1, 0)
    pd_ = pk(target_stage=True, stage_drop=True)
    rows3 = _wk_rows([1.0] * 4 + [-1.0])
    assert tp4.stage_for(rows3, d + timedelta(days=7 * 4), pd_) == (1, 0) and tp4.stage_for(rows3, d + timedelta(days=7 * 5), pd_) == (0, 0)       # stage_drop steps one back after the losing week
    assert tp4.stage_for(rows3, d + timedelta(days=7 * 5), p) == (1, 0)                                  # without stage_drop the stage stays
    # the size never changes with the stage (same stop -> same shares)
    from mentorship.strategy import _first_units
    a = _first_units(tp4.stage_params(rows, d + timedelta(days=7 * 3), p), 100000.0, 2.0, 4000.0, 1.0, 0.0)
    b = _first_units(tp4.stage_params(rows, d + timedelta(days=7 * 8), p), 100000.0, 2.0, 4000.0, 1.0, 0.0)
    assert a == b
    # the weeks without a trade are skipped; the current week and later days do not count
    assert tp4.stage_for(_wk_rows([1.0, 1.0]) + [dict(date=d + timedelta(days=7 * 5 + 1), net=1.0)], d + timedelta(days=7 * 6), p) == (0, 3)


def test_stage_in_a_backtest_run():
    """backtest.run swaps the staged target per day and the trades carry stage_pts (a synthetic book)."""
    from mentorship import backtest as B
    x, y = B.synthetic(start="2026-04-06", end="2026-05-08", tf=5, seed=3)
    p = Params(**{**P, "target_stage": True, "stage_weeks": 1, "t1_fixed_pts": 10.0, "stage_targets": (10.0, 15.0, 20.0), "ob_entry": "post_mss", "draw_lock": "off", "htf_resist_cap": False})
    from test_caption_gap_ld1 import SYN
    from test_caption_gap_sm2b import SYN_BASE
    p = Params(**{**SYN, **SYN_BASE, "target_stage": True, "stage_weeks": 1, "t1_fixed_pts": 10.0})
    t = B.run(x, 5, "RW", p, partner=y)
    assert len(t) >= 2 and set(t.stage_pts.unique()) <= {10.0, 15.0, 20.0} and (t.stage_pts > 0).all()      # (the seed's trades all lose: the stage stays 10; the stepping is the unit test's)


# --- new-rr-month-gate (session 22) ----------------------------------------------------------------------------------------------------------------

def test_rr_month_gate():
    ctx = mk(flat(12))
    sd = side(ctx)
    p = pk(rr_month_gate=True)
    ctx.week = {}
    (why, *_), _ = L4(p, ctx, sd, [(4106.0, "pool")], entry=4100.0, risk=2.0)                          # a 3R setup early in the month: skipped
    assert why == "x_rr_month"
    (why, *_), kw = L4(p, ctx, sd, [(4110.0, "pool")], entry=4100.0, risk=2.0)                         # 5R: allowed
    assert why is None and kw["tags"]["tp4"]["rr_final"] == pytest.approx(5.0)
    ctx.week = {"month_big": 1}                                                                          # after a 5R winner closed: the identical 3R setup trades
    (why, *_), _ = L4(p, ctx, sd, [(4106.0, "pool")], entry=4100.0, risk=2.0)
    assert why is None
    (why, *_), _ = L4(p, ctx, sd, [(4102.0, "pool")], entry=4100.0, risk=2.0)                          # 1R still below the relaxed 2R
    assert why == "x_rr_month"
    (why, *_), _ = L4(pk(rr_month_gate=True, rr_n_big=2), ctx, sd, [(4106.0, "pool")], entry=4100.0, risk=2.0)      # two are needed
    assert why == "x_rr_month"
    # the counter: the closed trades of the calendar month with R >= rr_big; resets on the 1st
    rows = [dict(date=date(2026, 5, 29), R=6.0), dict(date=date(2026, 6, 2), R=5.0), dict(date=date(2026, 6, 3), R=2.0), dict(date=date(2026, 6, 10), R=7.0)]
    assert tp4.month_big(rows, date(2026, 6, 9), p) == 1 and tp4.month_big(rows, date(2026, 6, 11), p) == 2 and tp4.month_big(rows, date(2026, 7, 1), p) == 0 and tp4.month_big(rows, date(2026, 6, 1), p) == 1 - 1


# --- E8-2pct-split-experienced (stops 28) --------------------------------------------------------------------------------------------------------------------

def test_ladder_half_3r(monkeypatch):
    ctx = mk(flat(12))
    sd = side(ctx)
    monkeypatch.setattr(tp3, "htf_draw", lambda ctx, sd, i, p, above, st: 4140.0)
    p = pk(ladder_kind="half_3r", risk_pct=0.02, max_total_risk_pct=0.02, adds=())
    (why, k2, *_), kw = L4(p, ctx, sd, [(4110.0, "pool"), (4125.0, "pool")], entry=4100.0, risk=2.0)
    assert why is None and k2[0] == (4106.0, "fixed") and k2[1][0] == pytest.approx(S._exit_px(4140.0, "array", p)) and kw["tags"]["fracs"] == pytest.approx((0.5, 0.5))      # risk 2: entry + 6 for half, the HTF level for the rest
    (_, k3, *_), _ = L4(p, ctx, sd, [(4110.0, "pool"), (4125.0, "pool")], entry=4100.0, risk=2.0, locked=True, final_T=True, draw=4150.0)
    assert k3[-1][0] == 4150.0                                                                           # the locked HTF draw is the second rung
    monkeypatch.setattr(tp3, "htf_draw", lambda ctx, sd, i, p, above, st: None)
    (_, k4, *_), _ = L4(p, ctx, sd, [(4110.0, "pool"), (4125.0, "pool")], entry=4100.0, risk=2.0)
    assert k4[-1] == (4125.0, "pool")                                                                    # no HTF array: the last rung
    (_, k5, *_), kw5 = L4(p, ctx, sd, [(4105.0, "pool")], entry=4100.0, risk=2.0)
    assert k5 == [(4105.0, "pool")]                                                                      # the final level is inside 3R: one rung


# --- T7-1450-targets (times 6) ----------------------------------------------------------------------------------------------------------------------------

def _m1450_ctx():
    """09:30 .. 15:05 on 5m bars (side space = long/discount mirror): a PM leg down from 4080 to 4020 after 13:30; AM 09:30-11:00 high 4060 (untaken), 08:30 high 4075, 07:00 high 4070."""
    idx = pd.date_range("2026-06-23 04:00", "2026-06-23 15:05", freq="5min", tz=NY)
    n = len(idx)
    t = (idx.hour * 60 + idx.minute).values
    o = np.full(n, 4050.0)
    h = o + 1.0
    l = o - 1.0
    c = o.copy()
    for k in range(n):
        if 420 <= t[k] < 510:
            h[k] = 4070.0 if t[k] == 450 else 4052.0
        if 510 <= t[k] < 570:
            h[k] = 4075.0 if t[k] == 530 else 4052.0
        if 570 <= t[k] < 660:
            h[k] = 4060.0 if t[k] == 600 else 4052.0
        if 660 <= t[k] < 810:
            h[k], l[k] = 4053.0, 4047.0
        if t[k] >= 810:
            j = (t[k] - 810) // 5
            base = 4080.0 - 2.0 * j if t[k] <= 870 else 4056.0 + (t[k] - 870) * 0.0 - 0.3 * (t[k] - 870) / 5
            o[k], c[k] = base + 1.0, base
            h[k], l[k] = base + 2.0, base - 1.0
    ctx = SimpleNamespace(conf=None, idx=idx, tf=5, start=0, o=o, h=h, l=l, c=c, t=t, day=D0, hist=hist_days(rng=40.0), pd={}, sess={}, pw=None, opens={"midnight": 4060.0}, day_tags="")
    return ctx


def test_m1450_ladder_targets_and_gate():
    """A long mirror in side space: 13:30 PM leg DOWN to a macro low in the discount, untaken 07:00 / 08:30 / 09:30-11:00 highs above, a swing high above the leg's EQ."""
    idx = pd.date_range("2026-06-23 07:00", "2026-06-23 15:05", freq="5min", tz=NY)
    n = len(idx)
    t = (idx.hour * 60 + idx.minute).values
    base = np.full(n, 4050.0)
    h, l = base + 1.0, base - 1.0
    for k in range(n):
        if t[k] == 450:
            h[k] = 4070.0                       # the 07:00 session high
        if t[k] == 530:
            h[k] = 4066.0                       # the 08:30 session high
        if t[k] == 600:
            h[k] = 4062.0                       # the 09:30-11:00 high
        if t[k] >= 810:
            j = (t[k] - 810) // 5
            lvl = 4056.0 - 1.2 * j if j < 25 else 4026.0
            h[k], l[k] = lvl + 1.0, lvl - 1.0
            if t[k] == 830:
                h[k] = 4058.5                   # a PM swing high above the leg's EQ (EQ ~ (4057 + 4025)/2)
    o = (h + l) / 2
    c = o.copy()
    ctx = SimpleNamespace(conf=None, idx=idx, tf=5, start=0, o=o, h=h, l=l, c=c, t=t, day=D0, hist=hist_days(rng=40.0), pd={}, sess={}, pw=None, opens={"midnight": 4050.0}, day_tags="")
    sd = S.Side(1, o, h, l, c, 1, 0.0)
    i = int(np.flatnonzero(t >= 890)[0])
    p = pk(m1450_targets=True)
    why, rungs = tp4.m1450_ladder(ctx, sd, dict(ext=4025.0, ext_i=0), i, p, 4028.0, 2.0, 4040.0, None)
    assert why is None and rungs, (why, rungs)
    vals = [v for v, _ in rungs]
    assert vals == sorted(vals) and any(abs(v - S._exit_px(4070.0, "pool", p)) < 1e-9 for v in vals) and any(abs(v - S._exit_px(4066.0, "pool", p)) < 1e-9 for v in vals) \
        and any(abs(v - S._exit_px(4062.0, "pool", p)) < 1e-9 for v in vals)
    assert vals[0] < min(S._exit_px(x, "pool", p) for x in (4062.0, 4066.0, 4070.0))                  # the leg's swing high (above the EQ) is the first rung
    # the macro low above the 50 % line: no order from this branch (the premium gate, mirrored)
    h2, l2 = h.copy(), l.copy()
    for k in range(n):
        if t[k] >= 810:
            h2[k], l2[k] = h[k] + 30.0, l[k] + 30.0
    sd2 = S.Side(1, (h2 + l2) / 2, h2, l2, (h2 + l2) / 2, 1, 0.0)
    ctx2 = SimpleNamespace(**dict(vars(ctx), o=(h2 + l2) / 2, h=h2, l=l2, c=(h2 + l2) / 2))
    assert tp4.m1450_ladder(ctx2, sd2, dict(ext=4055.0, ext_i=0), i, p, 4060.0, 2.0, 4070.0, None)[0] == "x_m1450_not_premium"
    # through late: only a PM order armed 14:50 - 15:10
    (why, k2, *_), kw = L4(p, ctx, sd, [(4040.0, "pool")], entry=4028.0, risk=2.0, sw=dict(ext=4025.0, ext_i=0), i=i, session="PM", leg_hi=4040.0)
    assert why is None and "m1450" in kw["lvt"] and k2[0][0] != 4040.0
    (_, k3, *_), kw3 = L4(p, ctx, sd, [(4040.0, "pool")], entry=4028.0, risk=2.0, sw=dict(ext=4025.0, ext_i=0), i=i, session="AM", leg_hi=4040.0)
    assert "m1450" not in kw3["lvt"] and k3 == [(4040.0, "pool")]


# --- T8-pm-carry-condition (times 19) ---------------------------------------------------------------------------------------------------------------

def _carry_ctx(lunch_low):
    idx = pd.date_range("2026-06-23 09:30", "2026-06-23 13:25", freq="5min", tz=NY)
    n = len(idx)
    t = (idx.hour * 60 + idx.minute).values
    base = np.full(n, 4020.0)
    h, l = base.copy(), base.copy()
    for k in range(n):
        if t[k] < 600:
            h[k], l[k] = 4000.0 + 20.0 * (t[k] - 570) / 30 + 1.0, 4000.0 + 20.0 * (t[k] - 570) / 30 - 1.0       # the AM rally 4000 -> 4020
        elif t[k] < 690:
            h[k], l[k] = 4021.0, 4017.0
        else:
            h[k], l[k] = 4021.0, lunch_low if 720 <= t[k] < 750 else 4017.0
    return SimpleNamespace(h=h, l=l, o=base, c=base, t=t, start=0, tf=5, idx=idx)


def test_pm_carry_not_erased():
    am = dict(side=1, target=4030.0, kind="pool", name="x", delivered=False)
    for lunch_low, carried in ((4010.0, True), (3998.0, False)):
        ctx = _carry_ctx(lunch_low)
        ctx.lock = {"AM": am}
        lk = dict(px=4018.0, target=4040.0, kind="pool", name="pm", side=1, t_lock=810)
        out = newscal.carry_lock(ctx, pk(pm_carry_draw=True, pm_carry_erase=True), "PM", dict(lk))
        assert (out.get("carried") is True) == carried, lunch_low
        assert (newscal.carry_lock(ctx, pk(pm_carry_draw=True), "PM", dict(lk)).get("carried") is True)         # without pm_carry_erase the draw carries whatever happened
    # the down mirror
    ctxd = _carry_ctx(4010.0)
    ctxd.lock = {"AM": dict(am, side=-1, target=4000.0)}
    assert newscal.carry_lock(ctxd, pk(pm_carry_draw=True, pm_carry_erase=True), "PM", dict(px=4018.0, target=3990.0, kind="pool", name="pm", side=-1, t_lock=810)) is not None


def test_skip_balanced_drops_crossed_levels():
    rows = [(4000.0, 4002.0, 3999.0, 4001.0), (4001.0, 4012.0, 4000.0, 4011.0), (4011.0, 4013.0, 3996.0, 3997.0), (3997.0, 3999.0, 3995.0, 3998.0)] + flat(4, v=3998.0)
    ctx = mk(rows)
    sd = side(ctx)
    lv = [(4005.0, "array"), (4020.0, "array"), (4005.5, "pool"), (3990.0, "array")]
    out = tp4.balanced_drop(ctx, sd, 7, pk(skip_balanced=True), lv)
    assert (4005.0, "array") not in out and (4020.0, "array") in out and (4005.5, "pool") in out          # 4005: a close above (4011) and below (3997); pools keep their own spent rule
    res = tp4.raw_post(ctx, sd, 7, pk(skip_balanced=True), "AM", 3998.0, 4.0, 3998.0, dict(ext=3995.0, ext_i=3), 4001.0, lv, [], {}, {})
    assert (4005.0, "array") not in res and (4020.0, "array") in res and (4005.5, "pool") in res


# --- the engine: scenario C through run_day ------------------------------------------------------------------------------------------------------------------

def test_defaults_do_not_change_a_run():
    ref = _tp_run()
    assert len(ref) == 1
    on = _tp_run(**{k: getattr(Params(), k) for k in KNOBS})
    assert [(t.entry, t.t1, t.t2, t.lv_tags, t.exits) for t in on] == [(t.entry, t.t1, t.t2, t.lv_tags, t.exits) for t in ref]
    assert not tp4.any_on(Params())


def test_engine_runner_at_half_and_capture():
    tr = _tp_run(runner_at_half=True)
    assert len(tr) == 1 and tr[0].t2 == pytest.approx(100.4 + 0.5 * (108.25 - 100.4), abs=0.3) and "runner_at_half" in tr[0].lv_tags
    assert tr[0].half_range_ok in (True, False)
    tr = _tp_run(capture_zone=True)
    assert len(tr) == 1 and "capture_zone" in tr[0].lv_tags and tr[0].capture_b is not None


def test_engine_r_ladder_sets_the_break_even_trigger():
    tr = _tp_run(partial_trigger="cc02_003")
    assert len(tr) == 1 and "r_ladder" in tr[0].lv_tags
    r = tr[0].entry - tr[0].stop
    assert tr[0].t2 == pytest.approx(tr[0].entry + 3 * r, abs=0.02) or tr[0].t1 == pytest.approx(tr[0].entry + 3 * r, abs=0.02)


# --- the review fixes -----------------------------------------------------------------------------------------------------------------------------------------

def test_review_ob_skip_never_skips_the_last_rung():
    p = pk(ob_target_tod=True, ob_targets_1m=True)
    pos = dict(level_kinds=["pool", "ob"], fracs=(0.5, 0.5), tp4=dict(ob_tod=True), k=1)
    assert tp4.ob_skip(pos, 1, 820, 5, p) is False and pos["fracs"] == (0.5, 0.5)                  # the last rung has no next rung: it fills, the units are not lost


def test_review_final_gates_judge_the_placed_final(monkeypatch):
    ctx = mk(flat(12), hist=hist_days(rng=40.0))
    sd = side(ctx)
    keep = [(4110.0, "pool"), (4160.0, "pool")]
    # the tf cap cuts the final to 4100 + 20 pts: 20 pts / risk 4 = 5R passes; with risk 6 the cut final is 3.3R < 3 R? (min_rr_final 4 -> reject)
    p = pk(tf_target_cap=True, tf_cap_pts=((int(ctx.tf), 20.0),), min_rr_final=4.0)
    (why, *_), kw = L4(p, ctx, sd, keep, risk=6.0)
    assert why == "x_min_rr_final"                                                                   # judged on the CUT final (4120), not the 4160 pre-cut one (6.7R)
    (why, *_), kw = L4(pk(min_rr_final=4.0), ctx, sd, keep, risk=6.0)
    assert why is None and kw["tags"]["tp4"]["rr_final"] == pytest.approx(10.0)
    # a scalp / fixed-target order records rr_final too and meets the same gates
    (why, *_), kw = L4(pk(min_rr_final=4.0), ctx, sd, keep, risk=6.0, tags={"single_exit": True}, draw=4110.0)
    assert why == "x_min_rr_final" and kw["tags"]["tp4"]["rr_final"] == pytest.approx(1.667, abs=1e-3)
    ctx.week = {"month_big": 0}
    (why, *_), _ = L4(pk(rr_month_gate=True, rr_big=5.0), ctx, sd, keep, risk=6.0, tags={"single_exit": True}, draw=4110.0)
    assert why == "x_rr_month"


def test_review_lrlr_zone_alone_rejects_at_the_ceiling(monkeypatch):
    from mentorship import tp1
    ctx = mk(flat(12))
    sd = side(ctx)
    monkeypatch.setattr(tp1, "lrlr_zone", lambda ctx, sd, i, p: (4090.0, 4100.0))
    keep = [(4110.0, "pool")]
    (why, *_), _ = L4(pk(lrlr_zone=True), ctx, sd, keep, entry=4100.5, sw=dict(ext=4095.0, ext_i=2, name="x"))
    assert why == "x_lrlr_ceiling"                                                                   # at the ceiling L_b: no new long (lrlr_zone alone)
    (why, *_), _ = L4(pk(lrlr_zone=True), ctx, sd, keep, entry=4098.0, sw=dict(ext=4095.0, ext_i=2, name="x"))
    assert why is None                                                                               # inside the zone: the order stands
    (why, *_), _ = L4(pk(lrlr_zone=True), ctx, sd, keep, entry=4100.5, sw=dict(ext=4080.0, ext_i=2, name="x"))
    assert why is None                                                                               # the sweep lay below the zone: not a repeated buy


def test_review_balanced_drop_counts_from_the_formation():
    rows = [(4000.0, 4002.0, 3999.0, 4001.0), (4001.0, 4012.0, 4000.0, 4011.0), (4011.0, 4013.0, 3996.0, 3997.0), (3997.0, 3999.0, 3995.0, 3998.0)] + flat(4, v=3998.0)
    ctx = mk(rows)
    sd = side(ctx)
    sd.ph = [L.Pivot(5, 4005.0, 6)]                                                                   # the 4005 level formed at bar 5/6: the crosses at bars 1-2 came before it
    out = tp4.balanced_drop(ctx, sd, 7, pk(skip_balanced=True), [(4005.0, "array")])
    assert out == [(4005.0, "array")]
    sd.ph = []
    assert tp4.balanced_drop(ctx, sd, 7, pk(skip_balanced=True), [(4005.0, "array")]) == []         # no formation bar known: from the day start


def test_review_ladder_096_needs_three_rungs():
    ctx = mk(flat(12))
    sd = _vi_side(ctx)
    p = pk(ladder_preset="096")
    keep = [(S._exit_px(4101.0, "pool", p), "pool"), (S._exit_px(4112.0, "pool", p), "pool")]
    assert tp4.ladder_096(ctx, sd, 8, p, 4090.0, 4.0, keep, {}) is None


def test_review_tgif_roll_by_index_and_after_the_fill():
    ctx = _tgif_ctx()
    sd = S.Side(-1, ctx.o, ctx.h, ctx.l, ctx.c, 1, 0.0)
    lv066 = [-4580.0, -4577.5, -4575.0, -4572.5, -4570.0]
    sd.pl = [L.Pivot(1, -4585.0, 3)]                                                                  # a swing formed BEFORE the fill
    pos = dict(left=5, k=3, levels=list(lv066), stop=-4600.0, fills=3, fracs=(0.15, 0.15, 0.5, 0.1, 0.1), level_kinds=["exact"] * 5, fill_i=2, tp4=dict(tgif066=lv066, tgif_l25_k=2))
    pos["trade"] = tr = SimpleNamespace(strength="")
    tp4.manage(ctx, sd, pos, tr, 8, None, pk(tgif_exits="066", tgif_zone=True))
    assert pos["stop"] == -4600.0                                                                    # no roll from a pre-fill swing
    pos["tp4"]["tgif_l25_k"] = 4
    sd.pl = [L.Pivot(5, -4585.0, 7)]
    tp4.manage(ctx, sd, pos, tr, 8, None, pk(tgif_exits="066", tgif_zone=True))
    assert pos["stop"] == -4600.0                                                                    # the L25 rung (index 4) has not filled: no roll


def test_review_level_intact_offers_the_swept_lows_again():
    ctx = mk(flat(12))
    ctx.state7 = {"void_rearm": dict(session="AM", swept="pdl1", sign=1)}
    l = np.array([4000.0, 3990.0, 4000.0, 4000.0])
    assert S._level_intact(ctx, l, 3, "pdl1", 3995.0, "AM") is True and S._level_intact(ctx, l, 3, "pdl2", 3995.0, "AM") is False
