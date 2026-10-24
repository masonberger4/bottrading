"""Caption-gap pass, package entries_stops_sizing #2/3, part B: the study variants of the chunk and the no-look-ahead runs (full vs truncated runs, cut at entry AND exit times) that put every new switch on small date
windows - synthetic random-walk books (with a partner index, with and without event gaps) and short ES windows (5m) with the Confluence object and the HTF table. Every behaviour switch has a run in which its code
path EXECUTED (the sm2.HITS counters that es2.py / the hooks bump), or an explicit entry in EXCEPTIONS with the reason data cannot reach it (its unit test is in test_caption_gap_es2a.py). Tests that need local market
data (ES) skip cleanly when it is absent; no platform-specific paths. The generic one-variant-per-run look-ahead test (test_bias_htf_lookahead.py) covers every study variant of the chunk as well."""
from pathlib import Path

import pytest

from mentorship import backtest as B, sm2, study
from mentorship.strategy import Params

from test_levels_detectors import ES
from test_caption_gap_ld1 import ENTRY, SYN
from test_caption_gap_sm2b import _check_ran, _es_tf, _la, ES_B, ES_NB, SYN_BASE, TAG_COLS
from test_caption_gap_sm6c import _gappy
from test_caption_gap_es2a import KNOBS, NEW_SWITCHES

COLS = ENTRY + TAG_COLS + ["draw_px"]

GAP_IDS = (
    "new-ob-session-filter", "A12-mt-grading", "A6-voids-fill-holding-range", "A17-rb-trend-context", "B5-execution-tf-15m-min", "A12-mt-worked-both-sides",
    "A11-bpr-mt-overshoot-cap", "new-fvg-wick-ce", "A12-mt-retrace-after-stop-run",
    "A13-breaker-close-beyond-higher-array", "new-friday-near-draw-shallow-entry",
    "E12-second-stage-ob-at-MT", "E12-add-while-falling-toward-VI", "E2-far-edge-fvg-over-breaker", "E1-close-proximity-entries", "E2-vi-primary-entry-array", "A5-wick-ce-inside-fvg-exact-entry",
    "E4-redelivery-wick-suffices", "E2-fvg-first-then-ob-open", "E5-stop-feasibility-at-entry-location", "E2-iofed-breaker-exact-match", "E5-breakaway-gap-chase", "M10-ifvg-stop-below-whole-ifvg",
    "E2-iofed-depth-second-gap", "E1-market-on-touch", "E3-entry-spread-offset", "A12-same-candle-retrace",
    "E12-equal-size-adds", "E12-ladder-631", "E12-067-citation-wrong", "E12-in-zone-larger-second", "E12-adds-after-partials-intraday", "E12-add-cutoff-definition", "E12-trend-day-adds",
    "E12-low-end-add-conditions",
)


def test_every_gap_id_has_a_study_variant_that_builds():
    assert len(GAP_IDS) == 35
    on = set()
    for g in GAP_IDS:
        vs = [v for v in study.DECISIONS if v == g or v.startswith(g + "_")]
        assert vs, g
        for v in vs:
            Params(**study.DECISIONS[v])                                                                              # validates
            on |= set(study.DECISIONS[v])
    missing = [s for s in NEW_SWITCHES if s not in on]
    assert not missing, missing
    D = study.DECISIONS
    assert D["B5-execution-tf-15m-min"]["entry_fvg_min_tf"] == 15 and D["E12-ladder-631_6421"]["add_ladder"] == "6421" and D["E1-market-on-touch_level"]["mot_next_open"] is False
    assert D["A6-voids-fill-holding-range_skip"]["gap_risk"] == "skip" and D["E12-adds-after-partials-intraday_high_vol"]["add_after_partial"] == "high_vol"
    # the variants sit after the earlier packages' and are all reached by the generic look-ahead test (test_bias_htf_lookahead._variants)
    names = list(D)
    assert names.index("new-ob-session-filter") > names.index("A12-ob-reached-body")
    assert not [v for v in study._ES2_DECISIONS if v not in D]


# --- no look-ahead: full run vs truncated runs --------------------------------------------------------------------------------------

# every behaviour switch of the chunk at once (the synthetic books): the order-block family, the entry-price family, the add family
OB_ON = dict(ob_session_filter=True, ob_grade_mult=(1.0, 0.5), mt_break="close", ob_mt_if_swept=True, ob_mt_two_sided=True, ob_arm="intrabar_htf")
ENTRY_ON = dict(entry="auto2", entry_order="market_on_touch", entry_offset_ticks=1, wick_ce_refine=True, fvg_wick_ce=True, vi_first=True, stop_bpr_mt=True, bpr_adj_pts=3.0, gap_risk="widen",
                fvg_then_ob=True, breaker_entry="fallback", breaker_iofed=True, bz_higher_array=True, bz_higher_pts=10.0, in_zone_ladder=True, ifvg_entries=True, ifvg_stop="far", ifvg_ob_add=True,
                e4_wick_ok=True, retrace_candle="intrabar", rb_ctx_mult=0.5, rb_pools=True, entry_fvg_min_tf=15)
ADD_ON = dict(add_sizes="equal_or_less", add_far_edge=True, add_wick_retouch=True, add_htf_fvg_edge=True, add_on_ifvg=True, add_stop_under_array=True, vi_ob_add=True, vi_add_early_pts=0.5, add_low_end=True,
              add_low_end_size="ladder", add_after_partial="inv_fvg", add_form_eq=True, add_day_mode="trend_day", trend_day_adr=0.2, add_leg_cut=True, close_proximity=True, close_prox_windows=((570, 720),),
              fri_shallow=True, breakaway_chase=True, reentry_win_max=2, vi_ob_entry=True)
ALL_ON = {**OB_ON, **ENTRY_ON, **ADD_ON}

SYN_CASES = {
    # name: (seed, switches, the HITS counters the full run must have bumped)
    "all_a": (4, {**ALL_ON, "ob_entry": "both"}, ()),
    "all_b": (4, {**ALL_ON, "ob_entry": "post_mss", "leg_pd": 0.0}, ()),
    "ob": (3, {**OB_ON, "ob_entry": "both", "ob_entry_px": "mt", "entry_arrays": ("ob", "vi_ob")}, ()),
    "adds": (3, {**ADD_ON, "ob_entry": "post_mss", "adds": (0.5, 0.33, 0.17)}, ()),
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


@pytest.mark.parametrize("seed", [3, 4])
def test_look_ahead_gappy_synthetic(seed):
    """Books WITH event gaps (the continuous ES frame has none) and the partner index: every switch of the chunk on at once, cuts at entry AND exit times."""
    x, y = _gappy(seed)
    p = Params(**{**SYN, **SYN_BASE, **ALL_ON, "ob_entry": "post_mss"})
    full, added = _la(x, 5, "RW", p, COLS, every=2, partner=y)
    assert len(full) >= 1, full
    _HITS.setdefault("gappy%d" % seed, set()).update(added)


# --- ES windows (5m): the full run must have EXECUTED the code paths named (the sm2.HITS counters es2.py and the hooks bump) -------------------------------

W0, W1, W2, W3, W4, W5, W6 = (("2022-03-07", "2022-03-28"), ("2022-08-01", "2022-08-22"), ("2023-03-06", "2023-03-27"), ("2023-06-05", "2023-06-26"), ("2023-10-02", "2023-10-23"),
                              ("2024-02-19", "2024-03-11"), ("2024-09-16", "2024-10-07"))
W9, W13 = ("2022-02-21", "2022-03-14"), ("2022-10-03", "2022-10-24")
SMP = dict(study.SM_POST)
ES_LOCK = dict(ES_NB, draw_lock="session", htf_resist_cap=False)
ES_OBPRE = dict(ES_NB, ob_entry="pre_break")
OBPRE_ALL = dict(ob_session_filter=True, ob_grade_mult=(1.0, 0.5), mt_break="close", ob_mt_if_swept=True, ob_mt_two_sided=True, ob_arm="intrabar_htf")
ADDS_A = dict(SMP, add_after_partial="inv_fvg", vi_ob_add=True, vi_add_early_pts=0.5, add_low_end=True, add_low_end_size="ladder", add_wick_retouch=True, add_far_edge=True, add_on_vi=True)
ES_CASES = {
    # name: (window, base, switches, the sm2.HITS counters the full run must have bumped)
    "obpre_a": (W0, ES_OBPRE, OBPRE_ALL, ("ob_session_ok", "ob_session_skip", "ob_mt_if_swept", "ob_arm_intrabar", "ob_grade_X", "ob_mt_dead")),
    "obpre_b": (W2, ES_OBPRE, OBPRE_ALL, ("ob_grade_A", "ob_grade_B")),
    "ob_arr_session": (W1, ES_NB, dict(entry_arrays=("ob",), ob_session_filter=True, **SMP), ("ob_session_ok", "ob_session_skip")),
    "ob_arr_grade": (W0, ES_NB, dict(entry_arrays=("ob",), ob_grade_mult=(0.5, 1.0), **SMP), ("ob_grade_A",)),
    "ob_arr_swept": (W0, ES_NB, dict(entry_arrays=("ob",), ob_mt_if_swept=True, **SMP), ("ob_mt_if_swept",)),
    "fvg_a": (W0, ES_NB, dict(SMP, stop_bpr_mt=True, bpr_adj_pts=3.0, fvg_wick_ce=True, wick_ce_refine=True, entry="auto2", entry_offset_ticks=1, entry_order="market_on_touch"),
              ("stop_bpr_mt", "fvg_wick_ce", "wick_ce_refine", "auto2_ce", "entry_offset", "mot_order", "mot_market")),
    "fvg_b": (W0, ES_NB, dict(SMP, entry="far_on_breaker", breaker_entry="fallback"), ("far_on_breaker",)),
    "fvg_b2": (W0, ES_B, dict(SMP, entry_fvg_min_tf=15, ifvg_entries=True, ifvg_stop="far"), ("entry_fvg_min_tf", "ifvg_stop_far")),
    "fvg_c": (W6, ES_NB, dict(SMP, entry="auto2"), ("auto2_edge",)),
    "fvg_d": (W3, ES_NB, dict(SMP, gap_risk="widen"), ("gap_risk_widen",)),
    "fvg_e": (W0, ES_NB, dict(SMP, fvg_then_ob=True), ("fvg_then_ob_add",)),
    "mot_level": (W0, ES_NB, dict(SMP, entry_order="market_on_touch", mot_next_open=False), ("mot_order",)),
    "ifvg_ob": (W4, ES_NB, dict(SMP, ifvg_entries=True, ifvg_stop="far", ifvg_ob_add=True), ("ifvg_ob_add", "ifvg_stop_far")),
    "breaker_iofed": (W1, ES_NB, dict(SMP, breaker_entry="fallback", breaker_iofed=True), ("breaker_iofed",)),
    "breaker_higher": (W1, ES_NB, dict(SMP, breaker_entry="fallback", bz_higher_array=True, bz_higher_pts=10.0), ("bz_higher_array",)),
    "breaker_zone": (W1, ES_NB, dict(SMP, breaker_entry="fallback", in_zone_ladder=True), ("in_zone_ladder",)),
    "lock_a": (W1, ES_LOCK, dict(close_proximity=True, close_prox_windows=((570, 720),), vi_first=True), ("close_proximity", "vi_first")),
    "lock_b": (W9, ES_LOCK, dict(fri_shallow=True), ("fri_shallow",)),
    "adds_a": (W0, ES_NB, dict(SMP, add_sizes="equal_or_less", add_far_edge=True, add_htf_fvg_edge=True), ("add_sizes", "add_far_edge", "add_htf_fvg_edge")),
    "adds_a2": (W0, ES_NB, dict(SMP, add_wick_retouch=True), ("add_wick_retouch",)),
    "adds_b": (W2, ES_NB, dict(SMP, add_ladder="067", add_on_ifvg=True, add_stop_under_array=True, ifvg_entries=True), ("add_sizes", "add_on_ifvg", "add_stop_under_array")),
    "adds_c": (W2, ES_NB, dict(SMP, add_form_eq=True), ("add_form_eq_cal",)),
    "adds_d": (W6, ES_NB, ADDS_A, ("add_low_end_ladder",)),
    "adds_e": (W9, ES_NB, ADDS_A, ("add_after_partial_inv_fvg",)),
    "voe": (W5, ES_NB, dict(SMP, vi_ob_entry=True, vi_entries=True), ("vi_ob_cand",)),
    "chase": (W3, ES_NB, dict(SMP, breakaway_chase=True), ("reentry_win_eval",)),
    "wide": (W0, ES_B, dict(SMP, max_stop_pts=6.0, stop_mode="ce2", evolve_fvg=True), ("stop_too_wide",)),
}
ES1M = Path("data/mentorship/ES_1min_db.csv").exists()
ES_CASES_1M = {
    # the 1m book: the E4 wick redelivery (a fill bar that gaps under the limit) is only reached on 1m bars
    "e4_1m": (("2023-03-06", "2023-03-18"), ES_NB, dict(SMP, retrace_candle="intrabar", e4_wick_ok=True), ("e4_wick_ok",)),
}
_RUN_KW = {}
for _c, (_w, _b, _kw, _need) in ES_CASES.items():
    _RUN_KW["es_" + _c] = (_kw, _need)
for _c, (_w, _b, _kw, _need) in ES_CASES_1M.items():
    _RUN_KW["es1m_" + _c] = (_kw, _need)
for _c, (_s, _kw, _need) in SYN_CASES.items():
    _RUN_KW["syn_" + _c] = (_kw, _need)


@pytest.mark.skipif(not ES, reason="no ES data")
@pytest.mark.parametrize("case", sorted(ES_CASES))
def test_look_ahead_es(case):
    (a, b), base, kw, need = ES_CASES[case]
    df, meta = _es_tf(5, a, b)
    p = Params(**{**base, **kw})
    full, added = _la(df, 5, "ES", p, COLS, every=4, meta=meta, lag=2)
    _check_ran(case, full, added, need)
    _HITS.setdefault(case, set()).update(added)


@pytest.mark.skipif(not (ES and ES1M), reason="no ES 1m data")
@pytest.mark.parametrize("case", sorted(ES_CASES_1M))
def test_look_ahead_es_1m(case):
    (a, b), base, kw, need = ES_CASES_1M[case]
    df, meta = _es_tf(1, a, b)
    p = Params(**{**base, **kw})
    full, added = _la(df, 1, "ES", p, COLS, every=3, meta=meta, lag=1)
    _check_ran(case, full, added, need)
    _HITS.setdefault(case, set()).update(added)


# --- every switch of the chunk has an executed-path case -------------------------------------------------------------------------------

# the sm2.HITS counter that proves a switch's code path RAN (an outcome counter where a window reaches it, else the counter of the evaluation that precedes the outcome - the outcome is then unit-tested)
SWITCH_HIT = {
    "ob_session_filter": "ob_session_skip", "ob_grade_mult": "ob_grade_A", "gap_risk": "gap_risk_widen", "entry_fvg_min_tf": "entry_fvg_min_tf", "ob_mt_two_sided": "ob_mt_dead", "stop_bpr_mt": "stop_bpr_mt",
    "fvg_wick_ce": "fvg_wick_ce", "ob_mt_if_swept": "ob_mt_if_swept", "bz_higher_array": "bz_higher_array", "fri_shallow": "fri_shallow", "vi_ob_entry": "vi_ob_cand", "close_proximity": "close_proximity",
    "vi_first": "vi_first", "wick_ce_refine": "wick_ce_refine", "fvg_then_ob": "fvg_then_ob_add", "breakaway_chase": "reentry_win_eval", "breaker_iofed": "breaker_iofed", "ifvg_stop": "ifvg_stop_far",
    "ifvg_ob_add": "ifvg_ob_add", "entry": "auto2_ce", "entry_order": "mot_order", "mot_next_open": "mot_order", "entry_offset_ticks": "entry_offset", "ob_arm": "ob_arm_intrabar", "add_sizes": "add_sizes",
    "add_far_edge": "add_far_edge", "add_wick_retouch": "add_wick_retouch", "add_htf_fvg_edge": "add_htf_fvg_edge", "add_ladder": "add_sizes", "add_on_ifvg": "add_on_ifvg",
    "add_stop_under_array": "add_stop_under_array", "in_zone_ladder": "in_zone_ladder", "add_after_partial": "add_after_partial_inv_fvg", "add_form_eq": "add_form_eq_cal", "add_low_end_size": "add_low_end_ladder",
    "e4_wick_ok": "e4_wick_ok",
}
# switches whose OUTCOME path no data window reaches (their evaluation runs in the cases above or the synthetic books; the outcome code is unit-tested in test_caption_gap_es2a.py)
EXCEPTIONS = {
    "e4_color": "an alias of retrace_candle='intrabar' (built): covered by test_e4_wick_redelivery_counts",
    "rb_ctx_mult": "no rejection-block sweep (rb_pools) with a trade in 14 ES windows (5m and 1m) - the gate runs in the synthetic books; test_rb_ctx_mult_grades_a_rejection_block_entry_lower",
    "vi_ob_add": "an intact VI formed after the fill with a down-close candle trading into it before T1 is not reached in 14 ES windows (small VIs are closed through at once); test_vi_ob_add_through_the_engine",
    "vi_add_early_pts": "same (a down candle heading to an intact VI above the stop); test_vi_add_early_through_the_engine",
    "add_day_mode": "a clean trend day (no FOMC / CPI / jobs, away from the open without a retrace) with an open position before T1 is not reached in 14 ES windows; test_trend_day_update_classifier / test_trend_day_waives_the_add_cuts_through_the_engine",
}
EXTRA_VALUES = {("entry", "auto2"): "auto2_ce", ("entry", "far_on_breaker"): "far_on_breaker", ("entry_order", "market_on_touch"): "mot_market", ("add_ladder", "067"): "add_sizes",
                ("ifvg_stop", "far"): "ifvg_stop_far", ("ob_arm", "intrabar_htf"): "ob_arm_intrabar"}


def _on(kw, switch):
    d = Params.__dataclass_fields__[switch].default
    return switch in kw and kw[switch] != d


def _ran_by(switch, hit_):
    return [c for c, (kw, need) in _RUN_KW.items() if _on(kw, switch) and hit_ in need]


def test_every_switch_of_the_chunk_has_an_executed_path_case():
    """Every behaviour switch is ON in a no-look-ahead run that must have EXECUTED its code path (its counter is in that run's required hits), or it is in EXCEPTIONS with the reason."""
    missing = []
    for s_ in NEW_SWITCHES:
        if s_ in EXCEPTIONS:
            continue
        if s_ not in SWITCH_HIT or not _ran_by(s_, SWITCH_HIT[s_]):
            missing.append(s_)
    assert not missing, missing
    for (field, value), hit_ in EXTRA_VALUES.items():
        assert any(field in kw and kw[field] == value and hit_ in need for kw, need in _RUN_KW.values()), (field, value)
