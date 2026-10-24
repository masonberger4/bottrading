"""Caption-gap pass, package entries_stops_sizing #1/3, part B: the study variants of the chunk and the no-look-ahead runs (full vs truncated runs, cut at entry AND exit times) that put every new switch on small date
windows - synthetic random-walk books (with a partner index, with and without event gaps) and short ES windows (5m and 1m) with the Confluence object and the HTF table. Every behaviour switch has a run in which its code
path EXECUTED (the sm2.HITS counters that es1.py / the hooks bump), or an explicit entry in EXCEPTIONS with the reason data cannot reach it (its unit test is in test_caption_gap_es1a.py). Tests that need local market data
(ES) skip cleanly when it is absent; no platform-specific paths."""
from pathlib import Path

import pytest

from mentorship import backtest as B, htf, sm2, study
from mentorship.strategy import Params

from test_levels_detectors import ES
from test_caption_gap_ld1 import ENTRY, SYN
from test_caption_gap_sm2b import _check_ran, _es_tf, _la, ES_B, ES_NB, SYN_BASE, TAG_COLS
from test_caption_gap_sm6c import _gappy
from test_caption_gap_es1a import NEW_SWITCHES

COLS = ENTRY + TAG_COLS + ["draw_px"]
ES1M = Path("data/mentorship/ES_1min_db.csv").exists()

GAP_IDS = (
    "NEW-no-return-to-origin-ob", "B5-prior-day-ny-range-retracement", "A12-ob-requires-signatures", "A12-cisd-open-buy-level", "A12-ob-overshoot-to-vi", "D4-mt-source-tally", "A13-breaker-fvg-refinement",
    "E2-iofed-full-definition", "A5-ob-in-vi-over-newer-fvg", "A5-mtf-gap-refinement", "A9-vi-retest-tolerance", "A16-propulsion-block-full", "A16-propulsion-depth-grade", "A15-mitigation-definition-and-iofed",
    "A21-implied-range-to-target", "A23-broken-wick-ce-inversion", "A5-far-edge-reach-conditions", "A5-partial-reprice-shrink", "A12-ob-edge-at-fvg-ce", "A21-intraday-fib-bodies", "A8-htf-gap-resistance-grade",
    "A12-ob-requires-narrative", "A12-ob-open-anchor-ltf-wick", "A12-ob-anchor-level", "new-multi-tf-scan", "new-2m-fvg-ce", "A5-skip-fvg-near-stop-pool", "A5-multitf-hold-test", "A21-post-cisd-range-retrace",
    "M13-swing-confirm-gate", "M13-reanchor-parent", "M13-nested-ranges", "M13-short-ote-mirror", "A12-ltf-ob-upper-half", "A12-ob-reached-body",
)
# the tuning knobs: they change a number (or pick a mode of a switch that is on anyway), not a code path
TUNING = {"vi_tol_small_pts", "prop_deep_cut", "ob_ce_tol_pts", "ob_need_htf_array", "broken_wick_stop"}


def test_every_gap_id_has_a_study_variant_that_builds():
    assert len(GAP_IDS) == 35
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
    assert D["B5-prior-day-ny-range-retracement_any"]["entry_pd_frame"] == "any" and D["A12-cisd-open-buy-level_adds"]["cisd_adds"] and D["A21-post-cisd-range-retrace"]["leg_pd_anchor"] == "retrace_range"
    assert D["A5-mtf-gap-refinement_widen"]["gap_tf_mode"] == "widen_up" and D["A9-vi-retest-tolerance_adjacent"]["vi_tol"] == "adjacent_extreme" and D["A23-broken-wick-ce-inversion_swing"]["broken_wick_stop"] == "swing"
    assert D["D4-mt-source-tally_blended_warn"]["mt_break"] == "warn" and D["A12-ob-reached-body"]["ob_reach"] == "body" and D["A12-ltf-ob-upper-half"]["ob_mt_range"] == "range"
    # the variants sit after the earlier packages' and are all reached by the generic look-ahead test (test_bias_htf_lookahead._variants)
    names = list(D)
    assert names.index("A12-ob-reached-body") > names.index("new-ny-runs-london-extreme-news")


# --- no look-ahead: full run vs truncated runs --------------------------------------------------------------------------------------

PD = dict(leg_pd=0.5, entry_pd_frame="prev_day", leg_fib="body")
OB_PRE = dict(ob_entry="pre_break", ob_need_fvg=True, ob_vi_overshoot=True, mt_mode="sensitive", mt_break="close")
OB_NARR = dict(ob_entry="pre_break", ob_need_narrative=True, mt_break="warn", mt_mode="body_single_range_blended", htf_bias="react")
OB_MT = dict(ob_entry="pre_break", ob_entry_px="mt", ob_mt_range="range", ob_entries="prefer", ob_need_fvg=True)
CISD = dict(cisd_ob_entries=True, cisd_ob_px="open", cisd_adds=True, adds=(0.5, 0.33))
OTE_A = dict(ote="limit", ote_gate_4th=True, ote_reanchor=True, ote_cancel=True)
OTE_B = dict(ote="limit", ote_nested=True, ote_parent_third=True)
FVG_A = dict(fvg_edge="remaining", ob_ce_confluence=True, ob_ce_tol_pts=2.0, mit_iofed_edge=True, entry="ce")
FVG_B = dict(entry="iofed", iofed_strict=True, fvg_skip_below_pool_short=True, fvg_pool_gap_pts=2.0, vi_stop=True, vi_tol="ce", vi_arrays=True)
FVG_C = dict(gap_tf_mode="widen_up", fvg_targets=True, breaker_entry="fallback", breaker_refine=True, add_pref_ob_in_vi=True, adds=(0.5, 0.33))
HTF_A = dict(htf_entry_arrays=(15, 60), gap_tf_mode="refine_down", far_edge_reach=True, ob_wick_ltf_entry=True, htf_depth_mult=(1.0, 1.0, 0.5))
HTF_B = dict(htf_ob_anchor="open", htf_targets=("15m", "1h", "4h", "D"), htf_depth_mult=(1.0, 1.0, 0.5), entry_arrays=("broken_wick_ce",))
PROP = dict(prop_entry=True, prop_mt_exit=True, prop_mt_test="wick", prop_fail_flip=True, prop_deep_mult=0.5, prop_deep_cut=0.3)
ORIGIN = dict(no_origin_retest=True, turtle_soup="2023", eq_tol_pts=4.0)
ORIGIN_CC = dict(no_origin_retest=True, turtle_soup="cc_limit", eq_tol_pts=4.0, htf_bias="react")
SCAN = dict(scan_tfs=(1, 15), fvg_skip_below_pool_short=True)
M1 = dict(two_min_ce=True, mtf_hold=True, entry_tf="5m", scan_tfs=(1, 2, 3, 4, 5))
REACH = dict(ob_reach="body", allow_htf_array_premise=True, htf_bias="react")
ALL_ON = {**PD, **OTE_A, **FVG_A, **PROP, **SCAN, **CISD, "ob_need_fvg": True, "ob_vi_overshoot": True, "mt_break": "close", "fvg_skip_below_pool_short": True, "htf_ob_anchor": "open",
          "gap_tf_mode": "widen_up", "fvg_targets": True, "breaker_entry": "fallback", "breaker_refine": True, "far_edge_reach": True, "htf_entry_arrays": (15,), "htf_depth_mult": (1.0, 1.0, 0.5),
          "no_origin_retest": True, "turtle_soup": "2023", "ob_reach": "body", "ob_mt_range": "range", "ob_entry_px": "mt", "vi_stop": True, "vi_tol": "adjacent_extreme", "vi_arrays": True,
          "entry_arrays": ("broken_wick_ce",), "iofed_strict": False, "add_pref_ob_in_vi": True, "ob_wick_ltf_entry": True}

W1, W2, W3, W4, W5, W6, W7 = (("2022-03-07", "2022-03-28"), ("2022-08-01", "2022-08-22"), ("2023-03-06", "2023-03-27"), ("2023-06-05", "2023-06-26"), ("2023-10-02", "2023-10-23"),
                              ("2024-02-19", "2024-03-11"), ("2024-09-16", "2024-10-07"))
ES_CASES = {
    # name: (window, tf, base, switches, the sm2.HITS counters the full run must have bumped, symbol)
    "pd_a": (W1, 5, ES_NB, PD, ("pd_frame_prev_day", "pd_body"), "ES"),
    "pd_b": (W1, 5, ES_NB, dict(leg_pd=0.5, leg_pd_anchor="target"), ("pd_target",), "ES"),
    "pd_c": (W1, 5, ES_NB, dict(leg_pd=0.9, leg_pd_anchor="retrace_range"), ("pd_retrace_range",), "ES"),
    "pd_d": (W3, 5, ES_NB, dict(leg_pd=0.5, entry_pd_frame="any"), ("pd_frame_any",), "ES"),
    "pd_e": (W3, 5, ES_NB, dict(leg_pd=0.5, entry_pd_frame="prev_ny"), ("pd_frame_prev_ny",), "ES"),
    "ob_pre": (W1, 5, ES_NB, OB_PRE, ("ob_potential",), "ES"),
    "ob_narr": (W1, 5, ES_NB, OB_NARR, ("ob_narrative", "mt_warn_traded"), "ES"),
    "ob_mt": (W1, 5, ES_NB, OB_MT, ("ob_potential", "ob_mt_range"), "ES"),
    "cisd": (W4, 5, ES_NB, CISD, ("cisd_open", "cisd_add"), "ES"),
    "ote_a": (W1, 5, ES_NB, OTE_A, ("ote_gate_wait", "ote_gate_open", "ote_reanchor"), "ES"),
    "ote_b": (W3, 5, ES_NB, OTE_B, ("ote_child", "ote_third_eval"), "ES"),
    "fvg_a": (W1, 5, ES_NB, FVG_A, ("mit_iofed_edge", "ob_ce_confluence", "fvg_remaining"), "ES"),
    "fvg_b": (W1, 5, ES_NB, FVG_B, ("iofed_strict", "iofed_ce_exit", "vi_tol", "fvg_near_pool"), "ES"),
    "fvg_b2": (W5, 5, ES_NB, FVG_B, ("iofed_swing_ok",), "ES"),
    "fvg_c": (W3, 5, ES_NB, FVG_C, ("gap_widen_up", "breaker_refine"), "ES"),
    "fvg_c2": (W7, 5, ES_NB, FVG_C, ("add_ob_vi_eval",), "ES"),
    "htf_a": (W2, 5, ES_NB, HTF_A, ("htf_depth_near", "htf_depth_ce", "htf_ob_open", "far_edge_protected", "gap_refine_down", "ob_wick_eval"), "ES"),
    "htf_a2": (W4, 5, ES_NB, HTF_A, ("htf_depth_far",), "ES"),
    "htf_b": (W1, 5, ES_B, HTF_B, ("broken_wick_ce", "htf_depth_far"), "ES"),
    "prop": (W4, 5, ES_NB, PROP, ("prop_depth_eval",), "ES"),
    "origin": (W6, 5, ES_B, ORIGIN, ("no_origin_drop",), "ES"),
    "origin_cc": (W4, 5, ES_B, ORIGIN_CC, ("no_origin_level",), "ES"),
    "scan": (W7, 5, ES_NB, SCAN, ("scan_tfs", "fvg_near_pool"), "ES"),
    "reach": (W5, 5, ES_B, REACH, ("ob_reach_body",), "ES"),
    "m1": (("2022-03-07", "2022-03-18"), 1, ES_NB, M1, ("scan_tfs", "mtf_hold_eval", "two_min_ce"), "ES"),
}
SYN_CASES = {
    # name: (seed, switches, the HITS counters the full run must have bumped)
    "all_a": (3, {**ALL_ON, "ob_entry": "post_mss"}, ()),
    "all_b": (5, {**ALL_ON, "ob_entry": "post_mss", "leg_pd": 0.0}, ()),
    "ob": (3, {**OB_PRE, "ob_entry": "both", "ob_entry_px": "mt", "ob_mt_range": "range", "ob_entries": "prefer"}, ()),
}
_HITS = {}


@pytest.mark.parametrize("case", sorted(SYN_CASES))
def test_look_ahead_synthetic(case):
    seed, kw, need = SYN_CASES[case]
    x, y = B.synthetic(start="2026-04-06", end="2026-05-08", tf=5, seed=seed)
    p = Params(**{**SYN, **SYN_BASE, **kw})
    full, added = _la(x, 5, "RW", p, COLS, every=3, partner=y)
    _check_ran(case, full, added, need)
    _HITS.setdefault("syn_" + case, set()).update(added)


@pytest.mark.parametrize("seed", [3, 5])
def test_look_ahead_gappy_synthetic(seed):
    """Books WITH event gaps (the continuous ES frame has none) and the partner index: every switch of the chunk on at once, cuts at entry AND exit times."""
    x, y = _gappy(seed)
    p = Params(**{**SYN, **SYN_BASE, **ALL_ON, "ob_entry": "post_mss"})
    full, added = _la(x, 5, "RW", p, COLS, every=2, partner=y)
    assert len(full) >= 1, full
    _HITS.setdefault("gappy%d" % seed, set()).update(added)


@pytest.mark.skipif(not ES, reason="no ES data")
@pytest.mark.parametrize("case", sorted(ES_CASES))
def test_look_ahead_es(case):
    (a, b), tf, base, kw, need, sym = ES_CASES[case]
    if tf == 1 and not ES1M:
        pytest.skip("no ES 1m data")
    df, meta = _es_tf(tf, a, b)
    p = Params(**{**base, **kw})
    full, added = _la(df, tf, sym, p, COLS, every=4, meta=meta, lag=1 if tf == 1 else 2)
    _check_ran(case, full, added, need)
    _HITS.setdefault(case, set()).update(added)


@pytest.mark.skipif(not ES, reason="no ES data")
@pytest.mark.parametrize("window", [W3])
def test_ob_reach_changes_the_real_table(window):
    """A12-ob-reached-body: the HTF table of a real ES window reads the OB reactions on bodies instead of wicks (some react_score differs); the wick table is the built one, the same index and columns."""
    df, _ = _es_tf(5, *window)
    w, bd = htf.table(df, 1.0), htf.table(df, 1.0, ob_reach="body")
    assert list(w.index) == list(bd.index) and list(w.columns) == list(bd.columns)
    assert (w.react_score != bd.react_score).any()
    import pandas as pd
    pd.testing.assert_frame_equal(w, htf.table(df, 1.0, ob_reach="wick"))


# --- every switch of the chunk has an executed-path case -------------------------------------------------------------------------------

# the sm2.HITS counter that proves a switch's code path RAN (an outcome counter where a window reaches it, else the counter of the evaluation that precedes the outcome - the outcome is then unit-tested)
SWITCH_HIT = {
    "no_origin_retest": "no_origin_drop", "entry_pd_frame": "pd_frame_prev_day", "ob_need_fvg": "ob_potential", "cisd_ob_px": "cisd_open", "cisd_adds": "cisd_add", "mt_break": "mt_warn_traded",
    "breaker_refine": "breaker_refine", "iofed_strict": "iofed_ce_exit", "add_pref_ob_in_vi": "add_ob_vi_eval", "gap_tf_mode": "gap_widen_up", "vi_tol": "vi_tol", "prop_mt_test": "prop_depth_eval",
    "prop_fail_flip": "prop_depth_eval", "prop_deep_mult": "prop_depth_eval", "mit_iofed_edge": "mit_iofed_edge", "leg_pd_anchor": "pd_target", "far_edge_reach": "far_edge_protected",
    "fvg_edge": "fvg_remaining", "ob_ce_confluence": "ob_ce_confluence", "leg_fib": "pd_body", "htf_depth_mult": "htf_depth_near", "ob_need_narrative": "ob_narrative", "ob_wick_ltf_entry": "ob_wick_eval",
    "htf_ob_anchor": "htf_ob_open", "scan_tfs": "scan_tfs", "two_min_ce": "two_min_ce", "fvg_skip_below_pool_short": "fvg_near_pool", "mtf_hold": "mtf_hold_eval", "ote_gate_4th": "ote_gate_open",
    "ote_reanchor": "ote_reanchor", "ote_nested": "ote_child", "ote_parent_third": "ote_third_eval", "ob_mt_range": "ob_mt_range", "ob_vi_overshoot": "ob_potential", "ob_reach": "ob_reach_body",
}
# switches whose OUTCOME path (the wick entry found, the strict-IOFED swing confirmed, the deep PB skipped, the PB-wick exit / flip, the OB-in-VI add armed, the VI overshoot stop) no data window reaches: the
# evaluation counters run in the full-vs-truncated cases; the outcome code is unit-tested in test_caption_gap_es1a.py (test_vi_far_edge_and_overshoot_engine, test_prop_depth_and_wick_exit_and_flip,
# test_add_prefers_the_ob_that_traded_into_a_vi, test_htf_ob_anchor_and_the_ltf_wick_entry, test_iofed_strict_arm_gate_and_ce_stop)
OUTCOME_UNREACHED = {"ob_vi_overshoot": "ob_potential", "ob_wick_ltf_entry": "ob_wick_eval", "add_pref_ob_in_vi": "add_ob_vi_eval", "prop_mt_test": "prop_depth_eval", "prop_fail_flip": "prop_depth_eval",
                     "prop_deep_mult": "prop_depth_eval"}
EXTRA_VALUES = {("entry_arrays", "broken_wick_ce"): "broken_wick_ce", ("entry_pd_frame", "prev_ny"): "pd_frame_prev_ny", ("entry_pd_frame", "any"): "pd_frame_any", ("leg_pd_anchor", "retrace_range"): "pd_retrace_range",
                ("gap_tf_mode", "refine_down"): "gap_refine_down", ("mt_mode", "sensitive"): "ob_potential", ("htf_depth_mult", (1.0, 1.0, 0.5)): "htf_depth_far"}
# (ob_reach also reads the htf.table reaction column - no counter there: test_ob_reach_body_in_the_htf_table / test_ob_reach_changes_the_real_table; the executed path of the run is the premise sweep in sm3)
EXCEPTIONS = {}
_RUN_KW = {}
for _c, (_w, _tf, _b, _kw, _need, _sym) in ES_CASES.items():
    _RUN_KW["es_" + _c] = (_kw, _need)
for _c, (_s, _kw, _need) in SYN_CASES.items():
    _RUN_KW["syn_" + _c] = (_kw, _need)


DEFAULT_ON = {"htf_ob_anchor"}                       # the switch whose DEFAULT is the new rule ("open", the A12 2023 level; "extreme" is the earlier build): every run executes it


def _on(kw, switch):
    d = Params.__dataclass_fields__[switch].default
    return switch in DEFAULT_ON or (switch in kw and kw[switch] != d)


def _ran_by(switch, hit_):
    return [c for c, (kw, need) in _RUN_KW.items() if _on(kw, switch) and hit_ in need]


def test_every_switch_of_the_chunk_has_an_executed_path_case():
    """Every behaviour switch is ON in a no-look-ahead run that must have EXECUTED its code path (its counter is in that run's required hits), or it is in EXCEPTIONS with the reason."""
    missing = []
    for s_ in NEW_SWITCHES:
        if s_ in TUNING or s_ in EXCEPTIONS:
            continue
        if s_ not in SWITCH_HIT or not _ran_by(s_, SWITCH_HIT[s_]):
            missing.append(s_)
    assert not missing, missing
    assert all(SWITCH_HIT[k] == v for k, v in OUTCOME_UNREACHED.items())
    for (field, value), hit_ in EXTRA_VALUES.items():
        assert any(field in kw and (value in kw[field] if (isinstance(kw[field], tuple) and not isinstance(value, tuple)) else kw[field] == value) and hit_ in need for kw, need in _RUN_KW.values()), (field, value)
