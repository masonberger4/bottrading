"""Caption-gap pass, package setups_models #6/7, part B: the study variants of the chunk and the no-look-ahead runs (full vs truncated, cut at entry AND exit times) that put every new switch on small
date windows - synthetic random-walk books (with a partner index) and short ES windows with the Confluence object and the HTF table. Every behaviour switch has a run in which its code path EXECUTED
(the sm2.HITS counters that sm6.py / the hooks bump), or an explicit entry in EXCEPTIONS with the reason data cannot reach it (its unit test is in test_caption_gap_sm6a.py). Tests that need local
market data (ES) skip cleanly when it is absent; no platform-specific paths."""
import numpy as np
import pandas as pd
import pytest

from mentorship import backtest as B, sm2, study, strategy as S
from mentorship.strategy import Params

from test_levels_detectors import ES, NY
from test_caption_gap_ld1 import ENTRY, EXIT, SYN
from test_caption_gap_sm2b import _check_ran, _es_tf, _la, ES_B, ES_NB, SYN_BASE, TAG_COLS
from test_caption_gap_sm6a import NEW_SWITCHES

GAP_IDS = (
    "M1-short-sell-side-of-buy-curve", "A12-ob-at-consolidation-eq-and-eq-retest", "A10-void-retrace-trades", "new-retrace-to-origin-ob", "M13-ote-needs-bias-trigger-structure",
    "M13-premium-ote-turtle-soup", "M13-bodies-stall-62-ob", "M12-quick-rejection-required", "M12-cc-daily-ob-turtle-soup", "B5-topdown-entry-refinement", "A12-secondary-ob",
    "new-false-bear-flag-long", "M12-setup-selection-order", "M12-contrarian-pmh", "B12-ob-below-midnight-open", "new-eq-wait-fresh-ob", "M12-counter-run-in-confirmed-trend",
    "E2-body-extreme-entry", "A13-breaker-reentries-and-wait", "A17-rejection-block-entries", "A16-propulsion-entries", "L8-vacuum-block-entries", "new-post-void-fill-gap-sell",
    "new-last-buyside-offered-level", "M4-two-chance-aggressive-vs-mss-retest", "M4-retest-nearer-ob-or-none", "A15-mitigation-block-sell-entry", "new-clarity-filter-pass-if-arguing",
    "new-bullish-week-daily-routine-london-ny", "M0-judas-ends-in-15m-array", "M12-turtle-soup-entry-depth", "new-consolidation-outer-edge-fade", "new-inside-range-expansion-fade",
    "new-eight-reversal-catalogue", "L2-pdh-pdl-fade-only-in-expansion-retrace", "new-overlapping-reversal-score",
)
# the tuning knobs: they change a number (or pick a mode of a switch that is on anyway), not a code path
TUNING = {"consol_max_pts", "void_idle_bars", "ts_cont_bars", "cc_ob_offset_ticks", "breaker_leave_pts", "vb_react_bars", "offer_run", "offer_step_pts", "clarity_overlap", "sweep_leave_pts",
          "consol_tf", "consol_width_adr", "consol_eq_band", "consol_eq_mode", "ts_r_preset", "cc_ob_tf"}


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
    assert D["A12-ob-at-consolidation-eq-and-eq-retest"]["consol_eq_mode"] == "ob" and D["new-retrace-to-origin-ob"]["consol_eq_mode"] == "origin_ob"
    assert D["M12-setup-selection-order_range_void"]["entry_discipline"] == "range_void" and D["L8-vacuum-block-entries"]["vb_entry"] == "auto"
    assert D["A17-rejection-block-entries_stop"]["rb_entry"] == "stop" and D["M12-cc-daily-ob-turtle-soup_5m"]["ts_r_preset"] == "cc02_003"
    assert D["B5-topdown-entry-refinement"]["refine_tfs"] == (60, 15, 5) and D["A15-mitigation-block-sell-entry"]["entry_arrays_order"] == ("mitigation", "breaker")
    assert D["new-inside-range-expansion-fade"]["consol_edge_fade"] == "inner" and D["new-clarity-filter-pass-if-arguing_tag"]["clarity"] == "tag"


# --- no look-ahead: full run vs truncated runs --------------------------------------------------------------------------------------

# every behaviour switch of the chunk that a window can reach, on at once (the ES windows below are short, an all-on book has a handful of trades and runs in seconds)
ALL_ON = dict(curve_short=True, consol_eq_entry=True, consol_bars=8, consol_max_pts=12.0, consol_eq_mode="origin_ob", void_trades=("fill", "range", "cont", "void_fill_gap"), ote="ob62",
              ote_need_trigger=True, ote_parent_pd=True, turtle_soup="2023", ts_need_htf=True, ts_ote_ok=True, ts_cont=True, ts_cont_bars=4, entry_arrays=("ob", "ob_secondary", "propulsion",
              "last_offer", "mitigation", "breaker"), prop_second=True, entry_arrays_order=("mitigation", "breaker"), pmh_contrarian=True, ob_below_open=True, eq_fresh_ob=True, sym_swing_ts=True,
              breaker_entry="fallback", breaker_retests=3, rb_entry="limit", two_chance=True, ts_gate_mss=True, cc_swings="breaker", cc_near_ob=True, clarity="tag", ny_london_range=True,
              weekly_bias=True, sweep_15m_array="tag", sweep_leave_bars=2, consol_edge_fade="both", consol_tf=15, reversal_tag=True, reversal_need_htf=True, reversal_score=True,
              pdl_expansion=True, daily_level_needs_array=True, vb_entry="auto", vb_min_gap_pts=0.5, adds=(0.5, 0.5))
W1, W2, W3, W4, W5, W6, W7 = (("2023-03-06", "2023-03-27"), ("2023-10-02", "2023-10-23"), ("2024-02-19", "2024-03-11"), ("2024-05-13", "2024-06-03"), ("2024-09-16", "2024-10-07"),
                              ("2024-11-04", "2024-11-25"), ("2023-11-06", "2023-11-22"))
ES_CASES = {
    # name: (window, tf, base, switches, the sm2.HITS counters the full run must have bumped)
    "all_a": (W3, 5, ES_B, ALL_ON, ("consol_eq", "curve_short", "ote_parent_pd", "ts_cont", "rb_limit", "reversal_types", "sweep_15m_array", "clarity", "two_chance_keep", "consol_inner", "premium_ts")),
    "all_b": (W4, 5, ES_B, ALL_ON, ("curve_short", "two_chance_add", "ote_parent_pd", "consol_edge", "rb_limit", "reversal_types", "premium_ts")),
    "all_c": (W6, 5, ES_B, ALL_ON, ("ny_london_range", "last_offer", "entry_arrays_order", "consol_edge", "consol_inner")),
    "void": (W3, 5, ES_B, dict(void_trades=("cont", "range", "fill", "void_fill_gap")), ("void_cont",)),
    "ote": (("2022-02-14", "2022-03-07"), 5, ES_B, dict(ote="limit", ote_need_trigger=True, ob_below_open=True, eq_fresh_ob=True, entry_arrays=("ob",)), ("ote_trigger_eval", "ob_below_open")),
    "ob62": (W1, 5, ES_B, dict(ote="ob62"), ("ote_ob62",)),
    "tscont": (W3, 5, ES_B, dict(ts_cont=True, ts_cont_bars=3), ("ts_cont",)),
    "curve": (W1, 5, ES_B, dict(curve_short=True), ("curve_short",)),
    "two": (W4, 5, ES_B, dict(breaker_entry="fallback", breaker_retests=3, two_chance=True, ts_gate_mss=True, cc_swings="breaker", turtle_soup="2023"), ("two_chance_keep", "two_chance_add")),
    "retests": (W1, 5, ES_B, dict(breaker_entry="fallback", breaker_retests=3, breaker_leave_pts=1.0), ("breaker_retest",)),
    "ccob": (W3, 5, ES_B, dict(turtle_soup="cc_1h_ob", refine_tfs=(60, 15, 5), ts_r_preset="cc02_003", cc_ob_offset_ticks=1), ("refine_tf_15", "cc_ob_variant")),
    "ccob60": (W4, 5, ES_B, dict(turtle_soup="cc_1h_ob", refine_tfs=(60, 15, 5)), ("refine_tf_60",)),
    "tsote": (W1, 5, ES_B, dict(turtle_soup="2023", ts_need_htf=True, ts_ote_ok=True), ("premium_ts",)),
    "tsbody": (W1, 5, ES_B, dict(turtle_soup="cc_limit", ts_level_src="body", ts_cc_below_pts=1.25), ("ts_body_level",)),
    "rev": (W4, 5, ES_B, dict(reversal_tag=True, reversal_need_htf=True, reversal_score=True, pdl_expansion=True, daily_level_needs_array=True), ("reversal_types", "pdl_expansion")),
    "order": (W3, 5, ES_B, dict(entry_arrays=("mitigation", "breaker", "propulsion"), entry_arrays_order=("mitigation", "breaker"), breaker_entry="fallback"), ("entry_arrays_order",)),
    "arrays": (W1, 5, ES_B, dict(entry_arrays=("ob_secondary", "propulsion", "last_offer"), prop_second=True, offer_run=2), ("ob_secondary", "last_offer", "prop_second")),
    "disc": (W2, 5, ES_B, dict(entry_discipline="range_void"), ("entry_discipline_range_void",)),
    # review windows found by scanning every 21-day ES 5m window of 2022-2025 for the counters
    "pmh": (("2023-02-27", "2023-03-20"), 5, ES_B, dict(pmh_contrarian=True), ("pmh_contrarian",)),
    "nylon": (("2023-02-27", "2023-03-20"), 5, ES_B, dict(ny_london_range=True, weekly_bias=True), ("ny_london_range",)),
}
SYN_CASES = {
    # name: (seed, switches, the HITS counters the full run must have bumped)
    "consol": (3, dict(consol_eq_entry=True, consol_bars=6, consol_max_pts=30.0, consol_eq_mode="origin_ob", ob_entry="post_mss"), ("consol_eq",)),
    "arrays": (6, dict(entry_arrays=("ob_secondary", "propulsion", "last_offer"), prop_second=True, offer_run=2, ob_entry="post_mss"), ("ob_secondary", "last_offer", "propulsion")),
    "rb": (3, dict(rb_entry="limit", ob_entry="post_mss"), ("rb_limit",)),
    "rb_stop": (5, dict(rb_entry="stop", ob_entry="post_mss"), ("rb_stop",)),
    "gates": (5, dict(ob_below_open=True, sym_swing_ts=True, sweep_15m_array="tag", sweep_leave_bars=2, reversal_tag=True, reversal_score=True, reversal_need_htf=True, clarity="tag",
                      entry_arrays=("ob",)), ("ob_below_open", "sym_swing", "sweep_15m_array", "reversal_types", "clarity", "sweep_hover")),
    "fade": (5, dict(consol_edge_fade="both", consol_tf=5, consol_bars=6, consol_width_adr=2.0, ob_entry="post_mss"), ("consol_edge", "consol_inner")),
    "keep": (6, dict(breaker_entry="fallback", breaker_retests=3, breaker_leave_pts=1.0, two_chance=True, cc_swings="breaker", cc_near_ob=True, turtle_soup="2023", ts_gate_mss=True), ("two_chance_keep",)),
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
    full, added = _la(df, tf, "ES", p, ENTRY + TAG_COLS, every=4, meta=meta, lag=2)               # (no draw_px column: with the session lock on a subset of trades may hold only None, a nan vs None artefact)
    _check_ran(case, full, added, need)
    _HITS.setdefault(case, set()).update(added)


# --- every switch of the chunk has an executed-path case -------------------------------------------------------------------------------

# the sm2.HITS counter that proves a switch's code path RAN (an outcome counter where a window reaches it, else the counter of the evaluation that precedes the outcome - the outcome is then unit-tested)
SWITCH_HIT = {
    "curve_short": "curve_short", "consol_eq_entry": "consol_eq", "void_trades": "void_cont", "ote_need_trigger": "ote_trigger_eval", "ote_parent_pd": "ote_parent_pd", "ts_ote_ok": "premium_ts",
    "ts_cont": "ts_cont", "refine_tfs": "refine_tf_15", "entry_discipline": "entry_discipline_range_void", "pmh_contrarian": "pmh_contrarian", "ob_below_open": "ob_below_open",
    "sym_swing_ts": "sym_swing", "ts_level_src": "ts_body_level", "breaker_retests": "breaker_retest", "rb_entry": "rb_limit", "prop_second": "prop_second",
    "two_chance": "two_chance_add", "entry_arrays_order": "entry_arrays_order", "clarity": "clarity", "ny_london_range": "ny_london_range",
    "sweep_15m_array": "sweep_15m_array", "sweep_leave_bars": "sweep_hover", "consol_edge_fade": "consol_edge", "reversal_tag": "reversal_types", "reversal_need_htf": "reversal_types",
    "reversal_score": "reversal_types", "pdl_expansion": "pdl_expansion",
}
# the values of EXISTING Params fields this chunk added: (field, value) -> the counter
EXTRA_VALUES = {("ote", "ob62"): "ote_ob62", ("entry_arrays", "ob_secondary"): "ob_secondary", ("entry_arrays", "propulsion"): "propulsion", ("entry_arrays", "last_offer"): "last_offer"}
EXCEPTIONS = {
    "eq_fresh_ob": "needs an OB entry within eq_tol_pts of the day range EQ: a scan of every 21-day ES 5m window of 2022-01..2023-02 (the ob_below_open / OTE configuration) never bumped it; test_eq_needs_fresh_ob covers the gate",
    "cc_near_ob": "needs a cc_swings breaker order whose break leg has a down-close bar opening above the breaking point: a scan of every 21-day ES 5m window of 2022-2025 never bumped it; test_cc_breaker_oco_near_ob covers it",
    "vb_entry": "the 5m / 1m continuous ES frame has no event gap (the first bar of a session opens at the last close): no window reaches vb_gaps; test_vacuum_block_partial_vs_full covers the entries and the management",
}
_RUN_KW = {}
for _c, (_s, _kw, _need) in SYN_CASES.items():
    _RUN_KW["syn_" + _c] = (_kw, _need)
for _c, (_w, _tf, _b, _kw, _need) in ES_CASES.items():
    _RUN_KW["es_" + _c] = (_kw, _need)


def _on(kw, switch):
    d = Params.__dataclass_fields__[switch].default
    return switch in kw and kw[switch] != d


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
    for (field, value), hit_ in EXTRA_VALUES.items():
        assert any(field in kw and (value in kw[field] if isinstance(kw[field], tuple) else kw[field] == value) and hit_ in need for kw, need in _RUN_KW.values()), (field, value)
