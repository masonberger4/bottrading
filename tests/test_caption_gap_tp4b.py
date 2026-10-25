"""Caption-gap pass, package targets_partials #4/4, part B: the study variants of the chunk and the no-look-ahead runs (full vs truncated runs, cut at entry AND exit times) that put every new switch on small
date windows - synthetic random-walk books (with a partner index), short ES windows (5m) with the Confluence object and the HTF table, and forced hand-made days for the mid-trade hooks. Every behaviour
switch has a run in which its code path EXECUTED (the sm2.HITS counters tp4.py bumps: "eval_*" = the switch's code was evaluated on real data where the situation itself is rare). Tests that need local
market data (ES) skip cleanly when it is absent; no platform-specific paths. The generic one-variant-per-run look-ahead test (test_bias_htf_lookahead.py) covers every study variant too."""
from datetime import date

import pandas as pd
import pytest

from mentorship import backtest as B, entries as EN, sm2, strategy as S, study, tp4
from mentorship.strategy import Params

from test_levels_detectors import ES
from test_caption_gap_ld1 import ENTRY, SYN
from test_caption_gap_sm2b import _check_ran, _es_tf, _la, ES_B, ES_NB, SYN_BASE, TAG_COLS
from test_caption_gap_tp1a import _tp_run
from test_caption_gap_tp1b import _forced, _fp
from test_caption_gap_tp4a import GAP_IDS, KNOBS, NEW_SWITCHES

COLS = ENTRY + TAG_COLS + ["draw_px", "rr_final", "stage_pts"]


def test_study_variants_are_the_specified_ones():
    assert len(GAP_IDS) == 33
    D = study.DECISIONS
    assert D["X3-041-projection-first-then-nwog"]["ladder_preset"] == "041" and D["X3-resting-1lot-partials-vi-final"]["ladder_preset"] == "096"
    assert D["X3-layered-pool-ladder-runner_collapse"]["collapse_adr_frac"] == 1.0 and D["X3-runner-htf-target_steps"]["runner_htf_steps"]
    assert D["X3-r-multiple-partials"]["partial_trigger"] == "cc02_001" and D["X3-r-multiple-partials_cc02_003"]["partial_trigger"] == "cc02_003"
    assert D["M14-tgif-management"]["tgif_exits"] == "066" and D["E8-2pct-split-experienced"]["ladder_kind"] == "half_3r" and D["E8-2pct-split-experienced"]["risk_pct"] == 0.02
    assert D["X3-mm-model-target"]["mm_first"] == 0.8 and D["X3-fulcrum-exit-modes_trail"]["fulcrum_exit"] == "trail"
    assert D["L15-min-3R-prefer-5R"]["min_rr_final"] == 5.0 and D["L15-min-rr-3"]["min_rr_final"] == 3.0 and D["OT-target-progression"]["stage_targets"] == (10.0, 15.0, 20.0)
    assert D["new-rr-month-gate"]["rr_big"] == 5.0 and D["T7-1450-targets"]["m1450_mid_open"]
    # the SB bias switches are untouched by this chunk
    assert Params().sb_model is False and "sb_use_bias" in Params.__dataclass_fields__ and "want_all_engines" in Params.__dataclass_fields__


# --- synthetic books ---------------------------------------------------------------------------------------------------------------------------------------
# (a random-walk book has no confluence arrays and no overnight session: the switches that read them run in the ES windows)

OFF = dict(draw_lock="off", ob_entry="post_mss", htf_resist_cap=False)          # (a locked draw is one exact target: the ladder cuts need it off)
SYN_CASES = {
    # name: (seed, switches, the sm2.HITS counters the full run must have bumped)
    "layered": (3, dict(weekly_hl_rung=True, pool_prev_week=True, runner_frac=0.2, collapse_adr_frac=1.0), ("weekly_hl_rung", "eval_late4")),
    "layered_b": (5, dict(weekly_hl_rung=True, pool_prev_week=True, runner_frac=0.2, **OFF), ("weekly_hl_rung", "runner_frac")),
    "bump": (3, dict(gap_speed_bump_partial=0.25), ("gap_speed_bump",)),
    "rladder": (3, dict(partial_trigger="cc02_001"), ("r_ladder",)),
    "r3": (5, dict(partial_trigger="cc02_003"), ("r_ladder",)),
    "eq60": (3, dict(eq60_rung=True), ("eq60_rung",)),
    "half3r": (3, dict(ladder_kind="half_3r"), ("ladder_half_3r",)),
    "pm": (3, dict(pm_ladder_am=True, m1450_targets=True, extra_pools=True), ("pm_ladder_am",)),
    "stage": (3, dict(target_stage=True, stage_drop=True, stage_weeks=1, t1_fixed_pts=10.0, rr_month_gate=True, rr_big=1.5), ("target_stage", "eval_rr_month")),
    "stage_only": (5, dict(target_stage=True, stage_weeks=1, t1_fixed_pts=10.0), ("target_stage",)),
    "carry": (3, dict(pm_carry_draw=True, pm_carry_erase=True, skip_balanced=True, draw_lock="session"), ("skip_balanced", "eval_pm_carry")),
    "bmulti": (5, dict(proj_breaker_multi=True, proj_k_max=7.5), ("proj_breaker_multi",)),
    "consol_nr": (3, dict(consol_no_runner=True), ("consol_no_runner",)),
    "strength": (5, dict(strength_hold=True), ("strength_hold",)),
    "conf": (5, dict(confluence_weight=True), ("confluence_weight",)),
    "capture": (3, dict(capture_zone=True, runner_at_half=True, **OFF), ("eval_capture_zone", "eval_runner_at_half", "capture_zone")),
    "tfcap": (5, dict(tf_target_cap=True, tf_cap_pts=((5, 300.0),), lrlr_ceiling=True, same_range_t1=True, extra_pools=True, **OFF), ("eval_tf_cap", "eval_lrlr_ceiling", "eval_same_range")),
    "void": (5, dict(void_draw=True, void_rearm=True, void_ladder=True, void_targets=True, ob_target_tod=True, ob_targets_1m=True, **OFF), ("eval_void_draw", "eval_ob_tod")),
}


@pytest.mark.parametrize("case", sorted(SYN_CASES))
def test_look_ahead_synthetic(case):
    seed, kw, need = SYN_CASES[case]
    x, y = B.synthetic(start="2026-04-06", end="2026-05-08", tf=5, seed=seed)
    p = Params(**{**SYN, **SYN_BASE, **kw})
    full, added = _la(x, 5, "RW", p, COLS, every=4, partner=y)
    _check_ran(case, full, added, need)
    if "stage" in case and len(full):
        assert set(full.stage_pts.unique()) <= {10.0, 15.0, 20.0}


# --- ES windows (5m): the full run must have EXECUTED the code paths named ---------------------------------------------------------------------------------

SMP = dict(study.SM_POST)
W2 = ("2023-03-06", "2023-03-20")
W8 = ("2023-02-06", "2023-04-03")
WL = ("2023-01-09", "2023-03-06")
HTW = ("1h", "4h", "D", "W")
ES_CASES = {
    # name: (window, base, switches, counters)
    "a": (W8, ES_NB, dict(SMP, weekly_hl_rung=True, pool_prev_week=True, runner_frac=0.2, capture_zone=True, runner_at_half=True, gap_speed_bump_partial=0.25, eq60_rung=True, htf_targets=HTW),
          ("eval_capture_zone", "capture_zone", "eval_runner_at_half", "weekly_hl_rung", "eq60_rung", "gap_speed_bump")),
    "b": (W8, ES_NB, dict(SMP, partial_trigger="cc02_001", lrlr_ceiling=True, tf_target_cap=True, same_range_t1=True, extra_pools=True, strength_hold=True),
          ("eval_tf_cap", "eval_lrlr_ceiling", "lrlr_ceiling", "hrlr_dropped", "eval_same_range", "same_range_t1", "eval_strength", "r_ladder")),
    "b2": (W8, ES_NB, dict(SMP, lrlr_ceiling=True, lrlr_allow_beyond=True), ("eval_lrlr_ceiling",)),
    "c": (W8, ES_NB, dict(SMP, void_draw=True, void_rearm=True, void_ladder=True, void_targets=True, ob_target_tod=True, ob_targets_1m=True, htf_targets=HTW), ("eval_void_draw", "eval_ob_tod")),
    "d": (W8, ES_NB, dict(SMP, runner_htf=True, runner_htf_steps=True, runner_frac=0.2, subrange_first=True, confluence_weight=True, confluence_only=True, proj_breaker_multi=True, htf_targets=HTW, sd_cluster_ticks=4),
          ("eval_runner_htf", "runner_htf", "eval_subrange", "subrange_first", "confluence_weight", "proj_breaker_multi")),
    "e": (W2, dict(ES_NB, htf_bias="combo", use_bias=True), dict(SMP, consol_eq_target=True, consol_no_runner=True, htf_targets=HTW), ("eval_consol_eq",)),      # (the rare paths consol_eq_target / consol_no_runner / tgif_roll / tgif_cover / void_rearm fire in no short real or synthetic window: unit tests in test_caption_gap_tp4a.py)
    "f": (W8, ES_NB, dict(SMP, m1450_targets=True, pm_ladder_am=True, extra_pools=True, skip_balanced=True, ladder_kind="half_3r", htf_targets=HTW), ("eval_m1450", "m1450_ladder", "pm_ladder_am", "ladder_half_3r", "skip_balanced")),
    "g": (W2, ES_NB, dict(SMP, mm_first=0.8, mm_targets=True, mm_oc_entry=True, mmxm_ctx=True, mm_lowrisk=True), ("eval_mm_first", "mm_first")),
    "h": (W2, ES_NB, dict(SMP, fulcrum_exit="ladder", sd_anchor="fulcrum", sd_targets=True), ("eval_fulcrum", "fulcrum_ladder")),
    "h2": (W8, ES_B, dict(SMP, fulcrum_exit="trail", sd_anchor="fulcrum", sd_targets=True), ("eval_fulcrum", "fulcrum_trail")),
    "j": (W8, ES_NB, dict(SMP, ladder_preset="096", vi_arrays=True, sd_targets=True, sd_levels=(1.0, 1.5, 2.0, 2.5, 3.0)), ("ladder_096",)),
    "i": (W2, ES_NB, dict(SMP, ladder_preset="041", sd_targets=True, htf_targets=HTW), ("ladder_041",)),
    "l": (WL, dict(ES_NB, draw_lock="session"), dict(pm_carry_draw=True, pm_carry_erase=True, skip_balanced=True), ("eval_pm_carry", "pm_carry_erased", "skip_balanced")),
    "k": (("2023-11-20", "2024-02-27"), ES_NB, dict(SMP, tgif=True, tgif_zone=True, tgif_exits="066", tgif_reentry_pm=True, tgif_last_hour_cover=True), ("eval_tgif066",)),     # (the TGIF tag needs ~13 weeks of history)
}


@pytest.mark.skipif(not ES, reason="no ES data")
@pytest.mark.parametrize("case", sorted(ES_CASES))
def test_look_ahead_es(case):
    (a, b), base, kw, need = ES_CASES[case]
    df, meta = _es_tf(5, a, b)
    p = Params(**{**base, **kw})
    full, added = _la(df, 5, "ES", p, COLS, every=6, meta=meta, lag=2)
    _check_ran(case, full, added, need)


# --- forced-path books (hand-made days): scenario C through run_day, full run vs runs truncated at every bar of the book -----------------------------------

def test_forced_ladder_modes():
    tr = _forced(_fp(runner_at_half=True), ("runner_at_half",))
    assert "runner_at_half" in tr[0].lv_tags and tr[0].half_range_ok in (True, False)
    tr = _forced(_fp(capture_zone=True), ("capture_zone",))
    assert tr[0].capture_b is not None
    tr = _forced(_fp(partial_trigger="cc02_003"), ("r_ladder",))
    assert "r_ladder" in tr[0].lv_tags
    tr = _forced(_fp(ladder_kind="half_3r", risk_pct=0.02, max_total_risk_pct=0.02), ("ladder_half_3r",))
    assert tr[0].t1 == pytest.approx(tr[0].entry + 3 * (tr[0].entry - tr[0].stop), abs=0.02)
    tr = _forced(_fp(min_rr_final=5.0), ("rr5",))
    assert tr[0].rr_final > 5.0


def test_forced_strength_hold_and_runner_htf():
    tr = _forced(_fp(strength_hold=True), ("strength_hold",))
    assert tr[0].strength == "strong" and len(tr[0].exits) == 1                  # the array rung is dropped: one exit at the pool
    tr = _forced(_fp(runner_htf=True, runner_frac=0.2), ("runner_htf",))
    assert "runner_htf" in tr[0].lv_tags


def test_forced_ob_time_of_day(monkeypatch):
    """A touched OB rung outside the profit-taking windows is a pause: skipped, its share goes on (the bar-by-bar loop of run_day)."""
    monkeypatch.setattr(EN, "ob_target_levels", lambda sd, i, above, p: [(105.0, "ob" if p.ob_target_tod else "array")])
    on = _forced(_fp(ob_targets_1m=True, ob_target_tod=True, ob_pt_windows=((700, 720),)), ("ob_tod_skip",))
    off = _forced(_fp(ob_targets_1m=True, ob_target_tod=True), ())
    ref = _forced(_fp(ob_targets_1m=True), ())
    assert [e[3] for e in on[0].exits] == ["t1", "t3"] and [e[3] for e in off[0].exits] == [e[3] for e in ref[0].exits] == ["t1", "t2", "t3"]


def test_defaults_do_not_change_a_run():
    ref = _tp_run()
    assert len(ref) == 1
    on = _tp_run(**{k: getattr(Params(), k) for k in KNOBS})
    assert [(t.entry, t.t1, t.t2, t.lv_tags, t.exits) for t in on] == [(t.entry, t.t1, t.t2, t.lv_tags, t.exits) for t in ref]
    assert not tp4.any_on(Params())
