"""Caption-gap pass, package setups_models #3/7, part B: the study variants of the chunk and the no-look-ahead runs (full vs truncated, cut at entry AND exit times) that put every new
switch on small date windows - synthetic random-walk books (the engine's gates, tags and setups) and short ES windows with the Confluence object and the HTF table. Every behaviour switch
has a run in which its code path EXECUTED (the sm2.HITS counters that sm3.py bumps), or an explicit entry in EXCEPTIONS with the reason data cannot reach it. Tests that need local market
data (ES) skip cleanly when it is absent; no platform-specific paths."""
import numpy as np
import pandas as pd
import pytest

from mentorship import backtest as B, sm2, study
from mentorship.strategy import Params

from test_levels_detectors import ES, NY
from test_caption_gap_ld1 import ENTRY, EXIT, SYN
from test_caption_gap_sm2b import _check_ran, _es_tf, _la, ES_B, ES_NB, SYN_BASE, TAG_COLS
from test_caption_gap_sm3a import NEW_SWITCHES

GAP_IDS = (
    "A23-1h-wick-ce-sweep-depth", "new-shallow-rel-sweep-one-more-drive", "new-leg-grading-quadrants", "L7-org-later-day-entry-array", "new-eq-stop-hunt-entry",
    "new-prev-day-range-eq-long", "new-retrace-to-recapitalized-ob", "M1-turning-level-types", "new-vb-target", "L2-raid-level-rolls", "B1-nearby-unrun-high-trap",
    "L13-weekly-high-london-swing", "M4-swept-low-age", "LLT3-equal-highs-fade-condition", "LLT3-judas-depth-third-adr", "LLT3-consolidation-lunch-vs-am-extreme",
    "LLT3-lunch-hl-raid-not-target", "X3-hs-fade-targets", "M11-immediate-rebalance-management", "M14-tgif-draw-hit-first-sd-depth", "M15-ma-deuce-ladder",
    "M16-sick-sister-exit-ladder", "A15-mitigation-block-targets", "A15-mitigation-block-body-hold", "new-vb-post-fill-management", "new-counter-bias-scalp-exit",
    "M4-immediate-response-swept-extreme", "X9-repeated-array-taps", "M5-lasthour-draw-frozen-noon", "M1-three-entry-plans", "M4-unicorn-sequence-preopen-breaker",
    "M4-accumulate-in-breaker-needs-bias-draw", "M1-sell-model-fail-to-reach-CE", "M1-inside-fvg-expansion-only", "M7-pm-1330-judas-full", "M1M2-htf-array-replaces-sweep",
)
TUNING = {"wick_depth_bars", "shallow_ticks", "leg_grade_tol", "org_confl_ticks", "org_entry_windows", "eq_hunt_band", "vb_min_gap_pts", "near_pool_adr", "wk_proj_k", "wk_proj_size",
          "ss_t1_frac", "lh_freeze_t", "unicorn_back_bars", "expansion_bulk", "premise_tfs", "leg_origin", "org_entry_confl"}


def test_every_gap_id_has_a_study_variant_that_builds():
    on = set()
    for g in GAP_IDS:
        vs = [v for v in study.DECISIONS if v == g or v.startswith(g + "_")]
        assert vs, g
        for v in vs:
            Params(**study.DECISIONS[v])                                                                              # validates
            on |= set(study.DECISIONS[v])
    missing = [s for s in NEW_SWITCHES if s not in on and s not in TUNING]
    assert not missing, missing
    assert study.DECISIONS["new-leg-grading-quadrants"]["leg_grade_gate"] == "require"
    assert study.DECISIONS["M1-three-entry-plans_pyramid"]["mm_plan"] == "pyramid"
    assert study.DECISIONS["new-vb-target_close_above"]["vb_entry"] == "close_above" and study.DECISIONS["new-retrace-to-recapitalized-ob_nearest"]["unfulfilled_nearest"]
    assert study.DECISIONS["L7-org-later-day-entry-array_confl"].get("org_entry_confl", True) is True and study.DECISIONS["M16-sick-sister-exit-ladder"]["ss_ladder"]


# --- no look-ahead: full run vs truncated runs --------------------------------------------------------------------------------------

SYN_CASES = {
    # name: (seed, switches, the sm2.HITS counters the full run must have bumped)
    "sweeps": (3, dict(sweep_max_linger=6, turtle_soup="2023", eq_hunt="prefer", pool_swings=True, ts_age_rank="prefer", allow_htf_array_premise=True),
               ("sweep_linger", "eq_hunt", "eq_hunt_prefer", "ts_age", "ts_age_prefer", "premise_array")),
    "ts_linger": (3, dict(ts_linger_bars=2, turtle_soup="2023"), ("ts_linger",)),                  # (the smaller limit drops the sweep first: a separate case from sweep_max_linger)
    "mitigation": (7, dict(mitigation_entry=True, mb_targets=True, mb_done_at_htf=True, mb_body_exit=True), ("mb_targets", "mb_body_exit", "mb_done")),
    "lh_freeze": (5, dict(last_hour_own_slot=True, lh_draw_freeze=True), ("lh_freeze", "lh_freeze_am")),
    "sick_sister": (5, dict(sick_sister=True, ss_ladder=True), ("ss_ladder",)),
    "ir": (7, dict(ir_entries=True, ir_filters=True), ("ir_filters",)),
    "plan_pyramid": (3, dict(mm_plan="pyramid"), ("mm_plan_pyramid",)),
    "plan_full": (3, dict(mm_plan="full"), ("mm_plan_full",)),
    "plan_scalp": (3, dict(mm_plan="mss_scalp"), ("mm_plan_mss_scalp",)),
    "expansion": (5, dict(expansion_ce_entry=True, draw_lock="session"), ("expansion_ce",)),
    "gates": (5, dict(leg_grade_gate="tag", near_pool_block=True, prev_eq_long=True), ("leg_grade", "near_pool", "prev_eq_long")),
    "pm": (5, dict(pm_judas_array=True, pm_need_htf_target=True), ("pm_need_htf",)),
    "ma_deuce": (3, dict(ma_deuce=True, ma_deuce_ladder=True, md_second=True), ("ma_deuce_far",)),
    "leg_session_low": (3, dict(leg_grade_gate="tag", leg_origin="session_low"), ("leg_grade",)),
}
# a synthetic book with two strong trend weeks (Monday-Thursday ramps of +25 %, the Friday after them) so the TGIF day tag fires: seed 7 reaches the draw gate and the SD level
TGIF_CASES = {
    "tgif_draw": (7, dict(tgif=True, tgif_window="off", tgif_min_adr=0.0, tgif_need_htf_array=False, tgif_zone=True, tgif_need_draw=True), ("tgif_draw",)),
    "tgif_sd": (7, dict(tgif=True, tgif_window="off", tgif_min_adr=0.0, tgif_need_htf_array=False, tgif_zone=True, tgif_sd_exit=True), ("tgif_sd_eval", "tgif_sd")),
}


def _tgif_book(seed, start="2026-03-02", end="2026-05-29", weeks=(3, 7), up=0.25):
    x, y = B.synthetic(start=start, end=end, tf=5, seed=seed)
    out = []
    for df in (x, y):
        df = df.copy()
        dd = df.index.date
        fac = np.ones(len(df))
        for wk in weeks:
            mon = (pd.Timestamp(start) + pd.Timedelta(days=7 * wk)).date()
            thu = (pd.Timestamp(mon) + pd.Timedelta(days=3)).date()
            fri = (pd.Timestamp(mon) + pd.Timedelta(days=4)).date()
            m = (dd >= mon) & (dd <= thu)
            fac[np.flatnonzero(m)] *= 1 + np.linspace(0, up, int(m.sum()))
            fac[dd >= fri] *= 1 + up
        for c in ("open", "high", "low", "close"):
            df[c] = (df[c].values * fac).round(2)
        out.append(df)
    return out
W_A, W_C, W_L, W_W = ("2023-10-02", "2023-10-23"), ("2024-02-19", "2024-03-11"), ("2024-09-16", "2024-10-07"), ("2024-05-13", "2024-06-03")
ES_CASES = {
    # name: (window, tf, base, switches, the HITS counters the full run must have bumped)
    "setups": (W_A, 5, ES_B, dict(vb_trade=True, vb_min_gap_pts=0.3, turtle_soup="cc_limit", raid_roll=True, ts_cc_below_pts=0.25, ir_entries=True, ir_filters=True,
                                 ir_accel_hold=True, mitigation_entry=True, mb_targets=True, mb_body_exit=True),
               ("vb_trade", "raid_roll", "ir_accel", "ir_decel", "ir_filters", "mb_targets", "mb_body_exit")),
    "vb_manage": (W_C, 5, ES_B, dict(vb_trade=True, vb_min_gap_pts=0.3), ("vb_trade", "vb_stall", "vb_back")),
    "ce_fail": (("2023-10-23", "2023-11-13"), 5, ES_B, dict(ce_fail_entry=True, counter_scalp=True), ("ce_fail", "counter_scalp", "counter_mo")),
    "breakers": (("2024-09-02", "2024-09-23"), 5, ES_B, dict(breaker_need_bias_draw=True, breaker_max_taps_for_entry=2, breaker_entry="fallback", unicorn_pref=True, unicorn_preopen=True,
                                                         leg_grade_gate="tag", near_pool_block=True, prev_eq_long=True, recap_ob_entry=True, unfulfilled_nearest=True),
                 ("breaker_bias_draw", "breaker_taps", "unicorn_preopen", "leg_grade", "prev_eq_long", "recap_ob", "unfulfilled")),
    "turn_types": (W_C, 5, ES_B, dict(am_discount_array=True, mm_turn_types=("ob", "fvg", "old_high", "old_low", "void"), leg_grade_gate="tag", near_pool_block=True, prev_eq_long=True,
                                      recap_ob_entry=True, breaker_need_bias_draw=True, breaker_max_taps_for_entry=2, breaker_entry="fallback", unicorn_pref=True, unicorn_preopen=True,
                                      org_entry_array=True, org_entry_confl=False, reh_fade_gate=True), ("mm_turn_type",)),
    "wick_shallow": (W_C, 5, ES_B, dict(wick_sweep_depth=True, shallow_sweep_wait=True), ("wick_depth", "shallow_wait", "shallow_cleared")),
    "pm_lunch": (W_C, 5, ES_B, dict(pm_lunch_raid=True, pm_judas_array=True, pm_lunch_fvg_array=True, pm_need_htf_target=True), ("pm_lunch_fvg",)),
    "expansion": (("2024-11-04", "2024-11-25"), 5, ES_B, dict(expansion_ce_entry=True, draw_lock="session"), ("expansion_ce",)),
    # the review-fix cases: every switch that had only unit tests now runs in a full-vs-truncated window
    "vb_close_above": (("2024-02-26", "2024-03-18"), 5, ES_NB, dict(vb_trade=True, vb_min_gap_pts=0.3, vb_entry="close_above", vb_back_full=True), ("vb_trade", "vb_back_full")),
    "fs_sweep": (W_A, 5, ES_NB, dict(cc_swings="failure", cc_fail_pts=8.0, fs_def="no_new_extreme", fs_sweep_close=True), ("fs_sweep_close",)),
    "recap_nearest": (W_A, 5, ES_B, dict(recap_ob_entry=True, unfulfilled_nearest=True), ("recap_ob", "unfulfilled")),
    "tgif_week": (("2024-11-04", "2024-12-30"), 5, ES_NB, dict(tgif=True, tgif_window="off", tgif_min_adr=0.0, tgif_need_htf_array=False, tgif_zone=True, tgif_need_draw=True, tgif_sd_exit=True, wk_high_proj=True, weekly_gate="tag"),
                  ("tgif_draw", "tgif_sd_eval", "wk_proj_eval", "wk_proj")),
    "reh_fade": (("2023-01-23", "2023-02-13"), 5, ES_NB, dict(reh_fade_gate=True), ("reh_fade_gate", "reh_fade")),
    "ma_deuce": (("2023-01-02", "2023-01-23"), 5, ES_NB, dict(ma_deuce=True, ma_deuce_ladder=True, md_second=True), ("ma_deuce_far",)),
    "lunch_raid": (("2023-01-02", "2023-01-23"), 5, ES_B, dict(pm_lunch_raid=True, counter_scalp=True), ("pm_lunch_raid",)),
    "org_array": (W_A, 5, ES_B, dict(org_entry_array=True, org_confl_ticks=40), ("org_eval", "org_cand", "org_confl")),
}
_HITS = {}


@pytest.mark.parametrize("case", sorted(SYN_CASES))
def test_look_ahead_synthetic(case):
    seed, kw, need = SYN_CASES[case]
    x, y = B.synthetic(start="2026-04-06", end="2026-05-08", tf=5, seed=seed)
    p = Params(**{**SYN, **SYN_BASE, **kw})
    full, added = _la(x, 5, "RW", p, ENTRY + TAG_COLS, every=3, partner=y)
    _check_ran(case, full, added, need)
    _HITS.setdefault(case, set()).update(added)


@pytest.mark.parametrize("case", sorted(TGIF_CASES))
def test_look_ahead_synthetic_tgif(case):
    seed, kw, need = TGIF_CASES[case]
    x, y = _tgif_book(seed)
    p = Params(**{**SYN, **SYN_BASE, **kw})
    full, added = _la(x, 5, "RW", p, ENTRY + TAG_COLS, every=3, partner=y)
    _check_ran(case, full, added, need)


@pytest.mark.skipif(not ES, reason="no ES data")
@pytest.mark.parametrize("case", sorted(ES_CASES))
def test_look_ahead_es(case):
    (a, b), tf, base, kw, need = ES_CASES[case]
    df, meta = _es_tf(tf, a, b)
    p = Params(**{**base, **kw})
    full, added = _la(df, tf, "ES", p, ENTRY + ["draw_px"] + TAG_COLS, every=4, meta=meta, lag=1 if tf == 1 else 2)
    _check_ran(case, full, added, need)
    _HITS.setdefault(case, set()).update(added)


# --- every switch of the chunk has an executed-path case -------------------------------------------------------------------------------

# the sm2.HITS counter that proves a switch's code path RAN
SWITCH_HIT = {
    "wick_sweep_depth": "wick_depth", "shallow_sweep_wait": "shallow_cleared", "leg_grade_gate": "leg_grade", "org_entry_array": "org_confl", "eq_hunt": "eq_hunt_prefer",
    "prev_eq_long": "prev_eq_long", "recap_ob_entry": "recap_ob", "mm_turn_types": "mm_turn_type", "vb_trade": "vb_trade", "raid_roll": "raid_roll", "near_pool_block": "near_pool",
    "wk_high_proj": "wk_proj", "ts_age_rank": "ts_age_prefer", "ts_linger_bars": "ts_linger", "reh_fade_gate": "reh_fade_gate", "pm_lunch_raid": "pm_lunch_raid",
    "ir_filters": "ir_filters", "ir_accel_hold": "ir_accel", "tgif_need_draw": "tgif_draw", "tgif_sd_exit": "tgif_sd", "ma_deuce_ladder": "ma_deuce_far", "ss_ladder": "ss_ladder",
    "mb_targets": "mb_targets", "mb_done_at_htf": "mb_done", "mb_body_exit": "mb_body_exit", "counter_scalp": "counter_scalp", "sweep_max_linger": "sweep_linger",
    "breaker_max_taps_for_entry": "breaker_taps", "lh_draw_freeze": "lh_freeze", "mm_plan": "mm_plan_pyramid", "unicorn_preopen": "unicorn_preopen",
    "breaker_need_bias_draw": "breaker_bias_draw", "ce_fail_entry": "ce_fail", "expansion_ce_entry": "expansion_ce", "pm_need_htf_target": "pm_need_htf",
    "pm_lunch_fvg_array": "pm_lunch_fvg", "allow_htf_array_premise": "premise_array",
    "vb_entry": "vb_trade", "vb_back_full": "vb_back_full", "unfulfilled_nearest": "unfulfilled", "fs_sweep_close": "fs_sweep_close",
}
# no data window reaches these: none left (review fix - every switch of the chunk runs in a full-vs-truncated case; the unit tests stay in test_caption_gap_sm3a.py)
EXCEPTIONS = {}
_RUN_KW = {}
for _c, (_s, _kw, _need) in SYN_CASES.items():
    _RUN_KW[_c] = (_kw, _need)
for _c, (_w, _tf, _b, _kw, _need) in ES_CASES.items():
    _RUN_KW[_c] = (_kw, _need)
for _c, (_s, _kw, _need) in TGIF_CASES.items():
    _RUN_KW[_c] = (_kw, _need)


def _ran_by(switch):
    hit_ = SWITCH_HIT[switch]
    return [c for c, (kw, need) in _RUN_KW.items() if switch in kw and hit_ in need]


def test_every_switch_of_the_chunk_has_an_executed_path_case():
    """Every behaviour switch is ON in a no-look-ahead run that must have EXECUTED its code path (its counter is in that run's required hits), or it is in EXCEPTIONS with the reason."""
    missing = []
    for s_ in NEW_SWITCHES:
        if s_ in TUNING or s_ in EXCEPTIONS:
            continue
        if s_ not in SWITCH_HIT or not _ran_by(s_):
            missing.append(s_)
    assert not missing, missing
    assert not (set(EXCEPTIONS) & {s for s in SWITCH_HIT if _ran_by(s)}), "an excepted switch is covered after all - drop it from EXCEPTIONS"
    assert all(len(v) > 25 for v in EXCEPTIONS.values())
