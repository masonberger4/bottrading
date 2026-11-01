"""Caption-gap pass, package setups_models #5/7, part B: the study variants of the chunk and the no-look-ahead runs (full vs truncated, cut at entry AND exit times) that put every new switch on small
date windows - synthetic random-walk books (with a partner index) and short ES windows with the Confluence object and the HTF table. Every behaviour switch has a run in which its code path
EXECUTED (the sm2.HITS counters that sm5.py / the hooks bump), or an explicit entry in EXCEPTIONS with the reason data cannot reach it (its unit test is in test_caption_gap_sm5a.py). Tests that need
local market data (ES) skip cleanly when it is absent; no platform-specific paths."""
import numpy as np
import pandas as pd
import pytest

from mentorship import backtest as B, sm2, study, strategy as S
from mentorship.strategy import Params
from dataclasses import dataclass as _oa_dc


@_oa_dc
class Params(Params):   # OA1029: these tests were written for the pre-build engine and exercise other rules - every OA1029 default back at its old value
    __annotations__ = {k: object for k in __import__('mentorship.study', fromlist=['OA1029_OLD']).OA1029_OLD}
    locals().update(__import__('mentorship.study', fromlist=['OA1029_OLD']).OA1029_OLD)
    news_cal: str = "legacy"                # coverage gap 1: these tests were written for the legacy news calendar


@pytest.fixture(autouse=True)
def _legacy_news_calendar():   # coverage gap 1: direct calendar calls in this file read the legacy calendar too
    from mentorship import calendar as _C
    _C.use("legacy")
    yield

from test_levels_detectors import ES, NY
from test_caption_gap_ld1 import ENTRY, EXIT, SYN
from test_caption_gap_sm2b import _check_ran, _es_tf, _la, ES_B, ES_NB, SYN_BASE, TAG_COLS
from test_caption_gap_sm5a import NEW_SWITCHES

GAP_IDS = (
    "M10-ifvg-fvg-signature-full", "new-false-bull-flag-short", "M9-news-judas-full-sequence", "new-15m-candle-po3-upper-half", "M12-new-trader-no-turtle-soup", "M12-turtle-soup-prev-pm-low",
    "M7-second-dip-into-rejection-block", "M8-org-repricing-full-conditions", "M0-all-nearby-pools-run-first", "M7-lunch-reprice-org-ce-moc", "D15-dual-dealing", "M4-1m-last-upclose-finetune",
    "M4-two-pool-breaker-near-miss", "M4-unfinished-high-keep-ab-leg", "M11-cisd-ob-stop-skip-rearm", "M10-ifvg-footholds-buy-program", "A4-bodies-hold-prev-day-50",
    "new-overshoot-ltf-fvg-into-htf-level", "new-open-returns-into-bearish-ob", "B5-ltf-at-htf-array", "M2-htf-ob-precondition", "M2-three-drives-breaker-fallback", "A15-mitigation-block-entry",
    "A15-stair-step-mitigation", "new-next-day-or-reh-short", "M2-skip-filter", "A14-unicorn-standalone", "M13-max-depth-79", "M10-ifvg-open-dependent", "M0-htf-array-not-reached",
    "M1-original-consolidation-entry", "M1-consolidate-at-discount-array", "M1-accumulation-stages", "M1-distribution-stages-lowrisk-short", "A18-curve-arrays-reverse-ladder", "M1-one-segment",
)
# the tuning knobs: they change a number, not a code path
TUNING = {"flag_min_bars", "flag_max_frac", "po3_15m_n", "all_pools_names", "all_pools_pts", "overshoot_pts", "td_level_pts", "ifvg_gap_pts", "mm_accum_frac", "mm_oc_frac", "reclaim_bounce_bars",
          "pd50_tf", "mb_order", "unicorn_tf"}


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
    assert D["M10-ifvg-fvg-signature-full"]["ifvg_061_entry"] == "iofed" and D["M12-turtle-soup-prev-pm-low"]["turtle_soup"] == "prev_pm" and D["D15-dual-dealing"]["dual_deal"] == "split"
    assert D["D15-dual-dealing_full"]["dual_deal"] == "full" and D["M4-1m-last-upclose-finetune"]["breaker_pref"] == "last_1m" and 1440 in D["M2-htf-ob-precondition"]["premise_tfs"]
    assert D["A15-mitigation-block-entry_daily"]["mit_entry_tf"] == "D" and D["A15-stair-step-mitigation_stop"]["mb_order"] == "stop" and D["B5-ltf-at-htf-array"]["entry_arrays"] == ("htf",)
    assert D["A4-bodies-hold-prev-day-50_5m"]["pd50_tf"] == 5 and D["A14-unicorn-standalone_60m"]["unicorn_tf"] == 60 and D["new-false-bull-flag-short_require"]["false_flag"] == "require"


# --- no look-ahead: full run vs truncated runs --------------------------------------------------------------------------------------

# every behaviour switch of the chunk on at once (the ES windows below are short, an all-on book has a handful of trades and runs in seconds)
ALL_ON = dict(ifvg_entries=True, ifvg_061=True, ifvg_061_entry="iofed", false_flag="tag", news_two_sided=True, po3_15m=True, turtle_soup="prev_pm", rb_second_dip=True, org_reprice=True,
              org_reprice_full=True, all_pools_first="tag", lunch_org_ce_short=True, breaker_entry="fallback", breaker_tf=5, breaker_pref="last_1m", near_miss_pts=3.0, adv_breaker=True,
              ab_anchor_lock=True, cisd_ob_entries=True, cisd_need_htf=True, cisd_rearm=True, max_stop_pts=12.0, ifvg_targets=True, ifvg_need_hunt=True, pd50_bodies=True,
              htf_overshoot_short=True, open_ob_min=10, htf_entry_array="tag", entry_arrays=("htf", "mitigation", "ob", "reclaimed_ob"), allow_htf_array_premise=True, premise_tfs=(15, 60, 1440),
              three_drives="tag", td_same_level=True, td_fallback=True, mit_stair=True, prev_reh_plan=True, stop_zone_pool=True, unicorn_standalone=True, unicorn_tf=5, max_retrace=0.79,
              fvg_pick="2022", ifvg_open_mode=True, array_fallback_breaker=True, mm_oc_entry=True, mm_accum_bars=3, mm_stages=True, mm_lowrisk=True, mmxm_ctx=True, reclaimed_ladder=True,
              reclaimed_ob=True, mm_flip=True, adds=(0.5, 0.5), draw_lock="session")
# the group configurations (one behaviour family each: the same dicts the window search ran)
G_IFVG = dict(ifvg_entries=True, ifvg_061=True, ifvg_061_entry="iofed", ifvg_targets=True, ifvg_need_hunt=True)
G_ORG = dict(org_reprice=True, org_reprice_full=True, all_pools_first="tag", near_miss_pts=3.0, pd50_bodies=True)
G_CISD = dict(cisd_ob_entries=True, cisd_need_htf=True, cisd_rearm=True, max_stop_pts=8.0)
G_ARR = dict(open_ob_min=15, htf_entry_array="tag", entry_arrays=("htf", "mitigation"), mit_entry_tf="D")
G_TD = dict(three_drives="tag", td_same_level=True, td_level_pts=3.0, td_fallback=True, ifvg_entries=True)
G_MM = dict(mm_oc_entry=True, mm_accum_bars=2, mm_stages=True, mm_lowrisk=True, mmxm_ctx=True, reclaimed_ladder=True, adds=(0.5, 0.5))
G_FLIP = dict(mm_stages=True, mm_flip=True, mmxm_ctx=True, draw_lock="session", htf_resist_cap=False)
G_MISC = dict(prev_reh_plan=True, stop_zone_pool=True, max_retrace=0.7, fvg_pick="2022", ifvg_open_mode=True, ifvg_gap_pts=2.0)
W1, W2, W3, W4, W5, W6, W7 = (("2023-03-06", "2023-03-27"), ("2023-10-02", "2023-10-23"), ("2024-02-19", "2024-03-11"), ("2024-05-13", "2024-06-03"), ("2024-09-16", "2024-10-07"),
                              ("2024-11-04", "2024-11-25"), ("2023-11-06", "2023-11-22"))
ES_CASES = {
    # name: (window, tf, base, switches, the sm2.HITS counters the full run must have bumped)
    "all_a": (W1, 5, ES_B, ALL_ON, ("lunch_org_ce_short", "htf_entry_array", "po3_15m", "unicorn_standalone", "mit_stair", "stop_too_wide", "premise_array", "cisd_htf_ok", "mm_oc_entry",
                                    "array_fallback_breaker", "ifvg_targets")),
    "all_b": (W3, 5, ES_B, ALL_ON, ("lunch_org_ce_short", "htf_overshoot", "mit_stair", "po3_15m", "array_fallback_breaker", "ifvg_open_unchanged")),
    "all_c": (W4, 5, ES_B, ALL_ON, ("cisd_rearm", "mit_stair_add", "ifvg_targets", "htf_overshoot", "lunch_org_ce_short")),
    "all_d": (W5, 5, ES_B, ALL_ON, ("all_pools", "near_miss", "pd50_hold", "false_flag_eval", "cisd_rearm")),
    "all_e": (W6, 5, ES_B, ALL_ON, ("reclaim_ladder", "reclaim_add", "pd50_fail", "near_miss", "mit_stair_add", "false_flag_eval", "stop_too_wide")),
    "ifvg": (W1, 5, ES_B, G_IFVG, ("ifvg_targets",)),
    "news": (W1, 5, ES_NB, dict(news_two_sided=True), ("news_two_sided_eval",)),
    "prev_pm": (W1, 5, ES_NB, dict(turtle_soup="prev_pm"), ("prev_pm_limit",)),
    "dip": (W3, 5, ES_B, dict(rb_second_dip=True), ("second_dip",)),
    "org": (W5, 5, ES_NB, G_ORG, ("org_reprice_full", "all_pools", "near_miss", "pd50_hold")),
    "flag": (W3, 5, ES_NB, dict(false_flag="tag"), ("false_flag",)),
    "cisd": (W1, 5, ES_B, G_CISD, ("cisd_htf_ok", "cisd_rearm", "stop_too_wide")),
    "arr": (W3, 5, ES_NB, G_ARR, ("open_into_ob", "htf_entry_array", "mit_entry_array")),
    "td": (W3, 5, ES_B, G_TD, ("td_note", "td_fallback")),
    "depth": (W3, 5, ES_NB, dict(max_retrace=0.7, fvg_pick="2022"), ("max_retrace_drop",)),
    "mm": (W1, 5, ES_B, G_MM, ("mm_oc_entry", "mm_stage_breaker", "mm_stage_bisi", "mm_stage_add_breaker", "reclaim_ladder", "reclaim_add")),
    "mm_lr": (W5, 5, ES_B, G_MM, ("mm_stage_add_bisi", "mm_lowrisk")),
    "flip": (W3, 5, ES_NB, G_FLIP, ("mm_flip",)),
    "ovs": (W3, 5, ES_B, dict(htf_overshoot_short=True, po3_15m=True), ("htf_overshoot", "po3_15m")),
    "fb": (W3, 5, ES_B, dict(array_fallback_breaker=True, draw_lock="session"), ("array_fallback_breaker",)),
    "prem": (W1, 5, ES_B, dict(allow_htf_array_premise=True, premise_tfs=(1440,)), ("premise_array",)),
    "accum": (W3, 5, ES_B, dict(mm_accum_bars=1, mm_accum_frac=6.0, mmxm_ctx=True), ("mm_accum",)),
    "zone": (("2023-01-16", "2023-02-06"), 5, ES_B, dict(stop_zone_pool=True, stop_mode="sweep"), ("stop_zone_pool",)),
    # review round (chunk 5/7): the windows were found by scanning 21-day windows of 2022-2025 for the counters
    "hunt": (("2023-01-16", "2023-02-06"), 5, ES_B, dict(ifvg_entries=True, ifvg_need_hunt=True), ("ifvg_hunt",)),
    "mm_s2": (("2022-07-11", "2022-08-01"), 5, ES_B, dict(G_MM, mm_stage2=True, mm_lowrisk_reentry="extreme"), ("mm_stage2", "mm_lowrisk_reentry")),
    "uni_ind": (("2022-01-03", "2022-01-24"), 5, dict(ES_B, ob_entry="pre_break"), dict(unicorn_standalone=True, unicorn_independent=True, unicorn_tf=5), ("unicorn_standalone",)),
    "gate": (W3, 5, ES_B, dict(mm_accum_bars=1, mm_accum_frac=6.0, mm_accum_gate=True, mm_stages=True, mm_oc_entry=True, mmxm_ctx=True, adds=(0.5, 0.5)), ("mm_accum_gate_open",)),
}
SYN_CASES = {
    # name: (seed, switches, the HITS counters the full run must have bumped)
    "flag": (5, dict(false_flag="tag", ob_entry="post_mss"), ("false_flag",)),
    "arrays": (3, dict(open_ob_min=60, entry_arrays=("htf", "mitigation"), ob_entry="post_mss"), ("htf_cands", "mit_entry_array")),
    "td": (5, dict(three_drives="tag", td_same_level=True, td_level_pts=30.0, td_fallback=True, ifvg_entries=True, ob_entry="post_mss"), ("td_note",)),
    "depth_open": (5, dict(max_retrace=0.5, fvg_pick="2022", ifvg_open_mode=True, ifvg_gap_pts=0.5, ob_entry="post_mss"), ("max_retrace_drop", "ifvg_open_limit")),
    "mm": (6, dict(mm_accum_bars=2, mm_accum_frac=3.0, mm_stages=True, mm_lowrisk=True, mmxm_ctx=True, reclaimed_ladder=True, adds=(0.5, 0.5), ob_entry="post_mss"),
           ("mm_stage_breaker", "mm_stage_add_bisi", "mm_stage_add_breaker", "reclaim_ladder")),
    "mm_b": (4, dict(mm_accum_bars=2, mm_accum_frac=3.0, mm_stages=True, mm_lowrisk=True, mmxm_ctx=True, reclaimed_ladder=True, adds=(0.5, 0.5), ob_entry="post_mss"), ("mm_stage_bisi", "mm_lowrisk")),
    "mm_c": (5, dict(mm_accum_bars=2, mm_accum_frac=3.0, mm_stages=True, mm_lowrisk=True, mmxm_ctx=True, reclaimed_ladder=True, adds=(0.5, 0.5), ob_entry="post_mss"), ("reclaim_add",)),
}
TAG5 = TAG_COLS + ["entry_style"]
_HITS = {}


@pytest.mark.parametrize("case", sorted(SYN_CASES))
def test_look_ahead_synthetic(case):
    seed, kw, need = SYN_CASES[case]
    x, y = B.synthetic(start="2026-04-06", end="2026-05-08", tf=5, seed=seed)
    p = Params(**{**SYN, **SYN_BASE, **kw})
    full, added = _la(x, 5, "RW", p, ENTRY + TAG5, every=3, partner=y)
    _check_ran(case, full, added, need)
    _HITS.setdefault(case, set()).update(added)


@pytest.mark.skipif(not ES, reason="no ES data")
@pytest.mark.parametrize("case", sorted(ES_CASES))
def test_look_ahead_es(case):
    (a, b), tf, base, kw, need = ES_CASES[case]
    df, meta = _es_tf(tf, a, b)
    p = Params(**{**base, **kw})
    full, added = _la(df, tf, "ES", p, ENTRY + TAG5, every=4, meta=meta, lag=1 if tf == 1 else 2)           # (no draw_px column: with the session lock on a subset of trades may hold only None, a nan vs None artefact)
    _check_ran(case, full, added, need)
    _HITS.setdefault(case, set()).update(added)


# the tf=1 window: the 5m breaker zone and the last 1m up-close block need 1m base bars
ES_CASES_1M = {
    "brk_1m": (W7, 1, ES_NB, dict(breaker_entry="fallback", breaker_tf=5, breaker_pref="last_1m"), ("breaker_zone_tf", "breaker_last_1m")),
}


@pytest.mark.skipif(not ES, reason="no ES data")
@pytest.mark.parametrize("case", sorted(ES_CASES_1M))
def test_look_ahead_es_1m(case):
    (a, b), tf, base, kw, need = ES_CASES_1M[case]
    df, meta = _es_tf(tf, a, b)
    p = Params(**{**base, **kw})
    full, added = _la(df, tf, "ES", p, ENTRY + TAG5, every=4, meta=meta, lag=1)
    _check_ran(case, full, added, need)
    _HITS.setdefault(case, set()).update(added)


# --- every switch of the chunk has an executed-path case -------------------------------------------------------------------------------

# the sm2.HITS counter that proves a switch's code path RAN (an outcome counter where a window reaches it, else the counter of the evaluation that precedes the outcome - the outcome is then unit-tested)
SWITCH_HIT = {
    "false_flag": "false_flag", "news_two_sided": "news_two_sided_eval", "po3_15m": "po3_15m", "rb_second_dip": "second_dip", "org_reprice_full": "org_reprice_full", "all_pools_first": "all_pools",
    "lunch_org_ce_short": "lunch_org_ce_short", "breaker_tf": "breaker_zone_tf", "breaker_pref": "breaker_last_1m", "near_miss_pts": "near_miss", "cisd_need_htf": "cisd_htf_ok",
    "cisd_rearm": "cisd_rearm", "max_stop_pts": "stop_too_wide", "ifvg_targets": "ifvg_targets", "pd50_bodies": "pd50_hold", "htf_overshoot_short": "htf_overshoot", "open_ob_min": "open_into_ob",
    "htf_entry_array": "htf_entry_array", "td_same_level": "td_note", "td_fallback": "td_fallback", "mit_entry_tf": "mit_entry_array", "mit_stair": "mit_stair", "stop_zone_pool": "stop_zone_pool",
    "unicorn_standalone": "unicorn_standalone", "max_retrace": "max_retrace_drop", "ifvg_open_mode": "ifvg_open_limit", "array_fallback_breaker": "array_fallback_breaker",
    "mm_oc_entry": "mm_oc_entry", "mm_stages": "mm_stage_bisi", "mm_lowrisk": "mm_lowrisk", "mm_flip": "mm_flip", "reclaimed_ladder": "reclaim_ladder", "mm_accum_bars": "mm_accum",
    "ifvg_need_hunt": "ifvg_hunt", "mm_lowrisk_reentry": "mm_lowrisk_reentry", "mm_stage2": "mm_stage2", "mm_accum_gate": "mm_accum_gate_open", "unicorn_independent": "unicorn_standalone",
}
# the values of EXISTING Params fields this chunk added: (field, value) -> the counter
EXTRA_VALUES = {("turtle_soup", "prev_pm"): "prev_pm_limit", ("entry_arrays", "htf"): "htf_cands", ("entry_arrays", "mitigation"): "mit_entry_array", ("premise_tfs", 1440): "premise_array"}
EXCEPTIONS = {
    "dual_deal": "a backtest.combine option (two books), not an engine path: test_combine_dual_deal_split covers it",
    "ifvg_061_entry": "needs an IFVG with a normal FVG below it and a body close at the FVG CE-top zone after a sweep: no ES window / synthetic seed reached the outcome; test_ifvg_061_iofed_limit covers it",
    "prev_reh_plan": "needs the prior session to close in the lower half of a daily FVG of the Confluence object while the overnight held the prior low (a 3-week window hits the context on about one day in ten, and then no REH pool was swept); the context gate ran in 18 side-days of two windows; a review-round scan of all 21-day windows 2022-2025 (ES 5m) never bumped prev_reh_pools either; test_prev_day_reh_plan covers pools, targets and the cancels and test_prev_reh_levels_truncation (sm5c) checks the full-vs-truncated day at every bar",
    "ab_anchor_lock": "needs a FILLED advanced-breaker order followed by another one in the same session: no window did (a review-round scan of all 21-day windows 2022-2025 never bumped ab_anchor_kept); test_ab_leg_not_reanchored covers it and test_ab_anchor_truncation (sm5c) checks the full-vs-truncated day at every bar",
}
_RUN_KW = {}
for _c, (_s, _kw, _need) in SYN_CASES.items():
    _RUN_KW[_c] = (_kw, _need)
for _c, (_w, _tf, _b, _kw, _need) in {**ES_CASES, **ES_CASES_1M}.items():
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
