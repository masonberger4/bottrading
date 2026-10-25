"""Caption-gap pass, package setups_models #4/7, part B: the study variants of the chunk and the no-look-ahead runs (full vs truncated, cut at entry AND exit times) that put every new switch
on small date windows - synthetic random-walk books (with a partner index: the sick sister, the symmetry skip, the Silver Bullet counter) and short ES windows with the Confluence object and the
HTF table (the evening bars for the Asian scalp). Every behaviour switch has a run in which its code path EXECUTED (the sm2.HITS counters that sm4.py / the hooks bump), or an explicit entry
in EXCEPTIONS with the reason data cannot reach it. Tests that need local market data (ES) skip cleanly when it is absent; no platform-specific paths."""
import numpy as np
import pandas as pd
import pytest

from mentorship import backtest as B, sm2, study
from mentorship.strategy import Params

from test_levels_detectors import ES, NY
from test_caption_gap_ld1 import ENTRY, EXIT, SYN
from test_caption_gap_sm2b import _check_ran, _es_tf, _la, ES_B, ES_NB, SYN_BASE, TAG_COLS
from test_caption_gap_sm4a import NEW_SWITCHES

GAP_IDS = (
    "new-falling-dagger-upper-half-buy", "M12-0930-htf-fvg-stab-no-mss", "B12-po3-low-after-0830-into-old-low", "new-po3-midnight-open-resting-order",
    "M5-lasthour-first-unit-at-old-low", "M6-pm-continuation-long-at-old-high", "M6-ifvg-must-stay-partly-open", "new-pm-retracement-short-after-draw-delivered", "M1-ob-entry-after-mss",
    "B5-multi-tf-fvg-scan", "M2-leg-eq-after-low-prints", "M2-pyramid-runup-leg-eq", "M2-implied-range-eq-gate", "M7-pm-short-after-lunch-run-of-am-stops", "M5-lasthour-short-sequence",
    "B16-nwog-gapup-return-then-mss", "M11-wick-ce-fade-short", "M5-lasthour-shallowest-unused-array", "new-nwog-edge-to-ce-cookie-cutter", "M8-short-after-reprice-to-prior-close",
    "A12-entry-array-at-key-level", "M4-breaker-needs-fvg-inside", "A13-breaker-inversion-against", "new-sweep-wick-ce-failure-swing-long", "M16-sick-sister-ob-open-entry",
    "new-lunch-macro-long-nwog", "A8-symmetry-skip-ifvg-confirmation", "A8-ifvg-5m-to-1m-handoff", "new-short-top-of-htf-discount-fvg", "new-ndog-asian-scalp",
    "M16-trending-divergence-continuation", "M16-sick-sister-discount-confluence", "M2-three-drives-conditions", "M4-complete-model-breaker-ote-ob", "M5-lasthour-reversal-into-org",
    "D15-one-clean-gap-instrument",
)
TUNING = {"stab_tfs", "po3_rest_off_pts", "po3_rest_mgmt", "lh_add2_mult", "lh_old_low_stop_pts", "pm_old_high_bars", "pm_rev_first_only", "pm_after_room_pts", "nwog_fill_tol_pts",
          "wick_ce_pad_pts", "wick_ce_need_pool", "ob_key_ticks", "sick_units", "ifvg_sym_bars", "dagger_level", "lh_array_sd_k", "wick_ce_precursor"}


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
    D = study.DECISIONS
    assert D["B12-po3-low-after-0830-into-old-low_require"]["po3_ideal"] == "require" and D["M12-0930-htf-fvg-stab-no-mss"]["turtle_soup"] == "htf_stab"
    assert D["M1-ob-entry-after-mss"]["entry_arrays"] == ("ob_post",) and D["D15-one-clean-gap-instrument"]["smt_pick"] == "clean"
    assert D["M11-wick-ce-fade-short_retrace"]["wick_ce_mode"] == "retrace" and D["new-falling-dagger-upper-half-buy_ltf"]["dagger_level"] == "ltf"
    assert D["new-pm-retracement-short-after-draw-delivered_sb"]["sb_counter_after_draw"] and D["M4-complete-model-breaker-ote-ob_require"]["complete_model"] == "require"
    assert D["A12-entry-array-at-key-level_require"]["ob_at_key"] == "require"


# --- no look-ahead: full run vs truncated runs --------------------------------------------------------------------------------------

G1 = dict(dagger_entry=True, po3_ideal="tag", po3_resting=True, lh_old_low_entry=True, pm_old_high_fvg=True, pm_reversal=True, pm_rev_partial=True, pm_after_draw=True,
          entry_arrays=("ob_post",), m2_live_eq=True, fvg_pick="2022", implied_range_gate=True, draw_lock="session")
G2 = dict(turtle_soup="htf_stab", leg_tfs=(15,), m2_anchor="runup", fvg_pick="2022", pm_am_stops=True, lh_array_short=True, nwog_fill_long=True, wick_ce_entries=True,
          wick_ce_mode="intrabar", entry_arrays=("ob", "vi", "breaker"), entry_pick="shallowest_unused")
G3 = dict(wick_ce_entries=True, wick_ce_tf=15, nwog_edge_ce=True, org_fill_reverse=True, ob_at_key="tag", breaker_entry="fallback", breaker_low_invalidate=True, breaker_block_counter=True,
          unicorn_pref=True, complete_model="tag")
G4 = dict(sick_entry="ob_open", lunch_nwog_long=True, ifvg_entries=True, ifvg_symmetry_skip=True, ifvg_hold=True, htf_fvg_top_short=True, smt_trend_ignore=True, sick_sister=True,
          smt_bias="filter", three_drives_htf=True, lh_org_fill=True, last_hour_own_slot=True, smt_pick="clean", wick_ce_mode="retrace")
SYN_CASES = {
    # name: (seed, switches, the sm2.HITS counters the full run must have bumped)
    "stack_a": (5, G1, ("pm_after_draw", "pm_rev_partial", "po3_ideal", "lh_old_low", "implied_range", "ob_post", "m2_live_eq_drop")),
    "pm_old_high": (3, dict(pm_old_high_fvg=True, pm_reversal=True), ("pm_old_high",)),
    "stack_b": (5, G2, ("wick_ce_intrabar", "pm_am_stops_targets", "m2_runup_fvg", "unused_drop")),
    "stab": (7, dict(turtle_soup="htf_stab"), ("htf_stab",)),
    "gates": (7, G3, ("wick_ce_tf", "org_fill_reverse", "breaker_counter", "ob_at_key", "breaker_low", "nwog_edge_pool")),
    "complete": (5, dict(complete_model="tag", breaker_entry="fallback", unicorn_pref=True), ("complete_eval",)),     # (the outcome is covered by es_cm)
    "misc": (3, G4, ("gap_count", "sick_ob_open", "wick_ce_retrace", "lunch_nwog_long")),
    "trend": (4, dict(smt_trend_ignore=True, smt_bias="filter", sick_sister=True), ("trend_eval", "trend_day", "trend_waive")),
    "ifvg": (5, dict(ifvg_entries=True, ifvg_tf=5, ifvg_symmetry_skip=True, ifvg_hold=True), ("ifvg_5m", "ifvg_sym_eval")),     # (the symmetry SKIP outcome is in EXCEPTIONS)
    "sb_counter": (3, dict(sb_model=True, sb_counter_after_draw=True), ("sb_counter_after_draw",)),
    "sick_ote": (5, dict(sick_entry="ote_stack", sick_units=2, draw_lock="off"), ("sick_ote_eval", "sick_ote_stack")),
}
ES_CASES = {
    # name: (window, tf, base, switches, the HITS the full run must have bumped)
    "es_stack": (("2023-03-06", "2023-03-27"), 5, ES_B, dict(dagger_entry=True, po3_resting=True, turtle_soup="htf_stab", lh_array_short=True, last_hour_own_slot=True, lh_array_target="sd3", leg_tfs=(15,), fvg_pick="2022",
                                                               lh_old_low_entry=True, pm_old_high_fvg=True, pm_after_draw=True, pm_reversal=True, pm_rev_partial=True),
                 ("dagger", "po3_rest_fill", "htf_stab", "lh_array_short", "lh_array_sd", "lh_old_low", "pm_old_high", "pm_after_draw", "pm_rev_partial")),
    "es_arrays": (("2023-10-02", "2023-10-23"), 5, ES_B, dict(entry_arrays=("ob", "vi", "breaker"), entry_pick="shallowest_unused", ob_at_key="tag", breaker_entry="fallback",
                                                                breaker_low_invalidate=True, complete_model="tag", unicorn_pref=True),
                  ("unused_drop", "ob_at_key", "breaker_low")),
    "es_implied": (("2024-11-04", "2024-11-25"), 5, dict(ES_B, draw_lock="session"), dict(implied_range_gate=True), ("implied_range",)),
    "es_m2": (("2024-11-04", "2024-11-25"), 5, ES_B, dict(m2_live_eq=True, fvg_pick="2022"), ("m2_live_eq_drop",)),
    "es_breaker": (("2024-05-13", "2024-06-03"), 5, ES_B, dict(breaker_block_counter=True, breaker_entry="fallback"), ("breaker_counter",)),
    "es_org": (("2024-09-16", "2024-10-07"), 5, ES_NB, dict(org_fill_reverse=True, nwog_edge_ce=True), ("org_fill_reverse", "nwog_edge_pool")),
    "es_gates": (("2023-03-06", "2023-03-27"), 5, ES_B, dict(htf_fvg_top_short=True, three_drives_htf=True, nwog_fill_long=True, wick_ce_entries=True, wick_ce_mode="intrabar"),
                 ("top_short_eval", "td_htf_eval", "wick_ce_intrabar")),
    "es_nwog": (("2024-11-04", "2024-11-25"), 5, ES_NB, dict(nwog_fill_long=True), ("nwog_fill",)),
    "es_leg": (("2024-02-19", "2024-03-11"), 5, ES_NB, dict(leg_tfs=(5, 15, 3), fvg_pick="2022"), ("leg_tf",)),                  # (an ascending tuple on purpose: the order does not matter)
    "es_cm": (("2024-07-01", "2024-07-22"), 5, ES_NB, dict(complete_model="tag", breaker_entry="fallback", unicorn_pref=True), ("complete_eval", "complete_model")),
    "es_ndog": (("2024-05-13", "2024-06-03"), 5, ES_B, dict(ndog_scalp=True, asia_session=True), ("ndog_eval", "ndog_scalp")),
    "es_lh_org": (("2024-02-19", "2024-03-11"), 5, ES_B, dict(lh_org_fill=True, last_hour_own_slot=True), ("lh_org_fill",)),
    "es_wick": (("2023-03-06", "2023-03-27"), 5, ES_B, dict(wick_ce_entries=True, wick_ce_tf=15, entry_arrays=("ob_post",), wick_ce_mode="retrace"),
                ("wick_ce_tf", "ob_post", "wick_ce_retrace")),
    "es_lh_draw": (("2023-10-02", "2023-10-23"), 5, ES_B, dict(lh_array_short=True, last_hour_own_slot=True, lh_array_need_draw=True, draw_lock="session"), ("lh_array_short",)),
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
    "dagger_entry": "dagger", "po3_ideal": "po3_ideal", "po3_resting": "po3_rest_fill", "lh_old_low_entry": "lh_old_low", "pm_old_high_fvg": "pm_old_high", "pm_rev_partial": "pm_rev_partial",
    "pm_after_draw": "pm_after_draw", "sb_counter_after_draw": "sb_counter_after_draw", "leg_tfs": "leg_tf", "m2_live_eq": "m2_live_eq_drop", "m2_anchor": "m2_runup_fvg",
    "implied_range_gate": "implied_range", "pm_am_stops": "pm_am_stops_targets", "lh_array_short": "lh_array_short", "nwog_fill_long": "nwog_fill", "lh_array_target": "lh_array_sd", "lh_array_iofed": "lh_array_iofed", "lh_array_need_draw": "lh_array_short", "lunch_nwog_entry": "lunch_nwog_ob", "wick_ce_mode": "wick_ce_intrabar",
    "wick_ce_tf": "wick_ce_tf", "entry_pick": "unused_drop", "nwog_edge_ce": "nwog_edge_pool", "org_fill_reverse": "org_fill_reverse", "ob_at_key": "ob_at_key",
    "breaker_low_invalidate": "breaker_low", "breaker_block_counter": "breaker_counter", "sick_entry": "sick_ob_open", "lunch_nwog_long": "lunch_nwog_long",
    "ifvg_symmetry_skip": "ifvg_symmetry", "ifvg_tf": "ifvg_5m", "htf_fvg_top_short": "htf_fvg_top_short", "ndog_scalp": "ndog_scalp", "asia_session": "ndog_scalp",
    "smt_trend_ignore": "trend_waive", "three_drives_htf": "td_htf_eval", "complete_model": "complete_model", "lh_org_fill": "lh_org_fill",
}
# the values of EXISTING Params fields this chunk added: (field, value) -> the counter
EXTRA_VALUES = {("turtle_soup", "htf_stab"): "htf_stab", ("entry_arrays", "ob_post"): "ob_post", ("smt_pick", "clean"): "gap_count", ("wick_ce_mode", "retrace"): "wick_ce_retrace",
                ("sick_entry", "ote_stack"): "sick_ote_stack"}
# no data window reaches these: none left (every switch of the chunk runs in a full-vs-truncated case; the unit tests stay in test_caption_gap_sm4a.py)
EXCEPTIONS = {
    "htf_fvg_top_short": "needs a daily FVG of the other kind, a 5m breaker whose zone holds its near edge and a swing high between entry and the far edge, inside the morning: no ES window of 15 tried reached the outcome; its evaluation counter runs (top_short_eval) and test_short_top_of_daily_bisi covers the outcome",
    "ifvg_symmetry_skip": "needs the two books to be symmetric AND an opposing bearish FVG of the leg that price already sits in: 56 synthetic runs reached the evaluation (ifvg_sym_eval) but never the skip; test_ifvg_skipped_when_symmetric covers the outcome",
    "lh_array_iofed": "the add needs a down-close bar into the first new gap after a lh_array_short fill: no ES window reached it (lh_array_short itself runs in es_stack); test_lh_array_sd3_target_iofed_and_draw covers it",
    "lunch_nwog_entry": "needs a down AM and price inside the NWOG zone at 11:40-12:10: lunch_nwog_long itself runs (misc, es_lunch) but no window held a down-close OB inside the zone; test_lunch_nwog_ob_entry_and_long_only covers it",
}
_RUN_KW = {}
for _c, (_s, _kw, _need) in SYN_CASES.items():
    _RUN_KW[_c] = (_kw, _need)
for _c, (_w, _tf, _b, _kw, _need) in ES_CASES.items():
    _RUN_KW[_c] = (_kw, _need)


def _on(kw, switch):
    d = Params.__dataclass_fields__[switch].default
    return switch in kw and kw[switch] != d


def _ran_by(switch):
    hit_ = SWITCH_HIT[switch]
    return [c for c, (kw, need) in _RUN_KW.items() if _on(kw, switch) and hit_ in need]


def test_every_switch_of_the_chunk_has_an_executed_path_case():
    """Every behaviour switch is ON in a no-look-ahead run that must have EXECUTED its code path (its counter is in that run's required hits), or it is in EXCEPTIONS with the reason."""
    missing = []
    for s_ in NEW_SWITCHES:
        if s_ in TUNING or s_ in EXCEPTIONS:
            continue
        if s_ not in SWITCH_HIT or not _ran_by(s_):
            missing.append(s_)
    assert not missing, missing
    for (field, value), hit_ in EXTRA_VALUES.items():
        assert any(field in kw and (value in kw[field] if isinstance(kw[field], tuple) else kw[field] == value) and hit_ in need for kw, need in _RUN_KW.values()), (field, value)
    assert not (set(EXCEPTIONS) & {s for s in SWITCH_HIT if _ran_by(s)}), "an excepted switch is covered after all - drop it from EXCEPTIONS"
    assert all(len(v) > 25 for v in EXCEPTIONS.values())
