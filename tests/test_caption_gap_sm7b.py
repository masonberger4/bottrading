"""Caption-gap pass, package setups_models #7/7, part B: the study variants of the chunk and the no-look-ahead runs (full vs truncated, cut at entry AND exit times) that put every new switch on small date
windows - synthetic random-walk books (with a partner index, with and without event gaps) and short ES windows with the Confluence object and the HTF table. Every behaviour switch has a run in which its
code path EXECUTED (the sm2.HITS counters that sm7.py / the hooks bump), or an explicit entry in EXCEPTIONS with the reason data cannot reach it (its unit test is in test_caption_gap_sm7a.py). Tests that
need local market data (ES) skip cleanly when it is absent; no platform-specific paths."""
import pandas as pd
import pytest

from mentorship import backtest as B, sm2, study, strategy as S
from mentorship.strategy import Params

from test_levels_detectors import ES, NY
from test_caption_gap_ld1 import ENTRY, EXIT, SYN
from test_caption_gap_sm2b import _check_ran, _es_tf, _la, ES_B, ES_NB, SYN_BASE, TAG_COLS
from test_caption_gap_sm6c import _gappy
from test_caption_gap_sm7a import NEW_SWITCHES

COLS7 = ENTRY + TAG_COLS + ["cc09", "state"]

GAP_IDS = (
    "T3-london-close-counter-trend-scalp", "M17-london-close-asia-only-reversal-profile", "E5-missed-entry-5m-retrace", "B12-dip-below-open-into-converging-15m-array",
    "new-or-reference-arrays-reused", "new-am-trend-definition-and-start", "T9-pm-reversal-turtle-soup-am-high", "T13-two-session-close-profile", "T13-am-move-pm-reversal-htf-nesting",
    "T13-consolidation-profiles", "M13-pattern1-full-sequence-ote-fvg", "M4-pattern3-breaker-half-size-add-ltf", "OT-D15-default-instrument", "OT-max-two-correlated-markets",
    "OT-M17-cc09_001-checklist", "OT-M17-cc09_003-ny-expansion", "OT-one-state-tool-pairing", "X14-reentry-after-winning-exit", "X13-reentry-after-trail-stop-in-profit",
    "X13-reentry-after-loss-conditions", "X13-reverse-after-failure-switch", "X14-opposite-second-trade-after-win", "E12-070-rung-order", "X13-reentry-turtle-soup", "E6-breakaway-gap-stop",
    "M12-ts-stop-midpoint", "T7-0950-reversal-or-continuation", "T7-1050-macro-setup", "T10-lasthour-ob-pullback", "T7-lasthour-after-target", "T7-lasthour-consolidation-direction",
    "T7-lunch-macro-htf-program", "new-ny-runs-london-extreme-news", "new-london-close-scalp-large-range",
)
# the tuning knobs: they change a number (or pick a mode of a switch that is on anyway), not a code path
TUNING = {"lc_mode", "lc_adr_mult", "lc_adr_k", "lc_stop_pts", "lc_retrace", "lc_retrace_mss", "london_close", "lc_fs_win", "lc_oneside", "missed_leave_pts", "or_ref_reuse", "or_ref_near_pts",
          "pm_nest_tfs", "consol_exit_min", "ts_breaker_add_mult", "reentry_win_max", "trail_reentry_entry", "trail_reentry_max", "reentry_risk_mult", "reentry_stop", "reverse_risk_mult",
          "offside_frac", "lod_conf_pts", "adv_rung_fracs", "reentry_max", "reentry_mult", "m1050_cut", "lunch_macro_win", "lunch_first_rung_only", "cc09_room_pts", "cc09_scalp_pts",
          "cc09_depart_bars", "nyx_start", "nyx_target_pct", "nyx_stop_pct", "nyx_max", "nyx_counts_session", "skip_pm_adr_k", "reentry_need_sister", "lunch_long_win", "missed_kz", "missed_lon_ratio"}


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
    assert D["T3-london-close-counter-trend-scalp"]["lc_mode"] == "failure_swing" and D["new-london-close-scalp-large-range"]["lc_mode"] == "mss"
    assert D["OT-D15-default-instrument"]["combine_prefer"] == "es" and D["OT-D15-default-instrument_nq2"]["nq_overshoot_mult"] == 2.0
    assert D["X13-reentry-after-loss-conditions_sibi"]["reentry_trigger"] == "sibi_return" and D["X13-reverse-after-failure-switch_at_stop"]["reverse_after_failure"] == "at_stop"
    assert D["OT-one-state-tool-pairing_expansion_ob"]["pairing"] == "expansion_ob" and D["M12-ts-stop-midpoint"]["ts_stop"] == "mid"
    assert D["X13-reentry-after-trail-stop-in-profit_breaker"]["trail_reentry_entry"] == "breaker" and D["E12-070-rung-order"]["adv_rungs"]


def test_study_passes_the_combine_switches_through():
    """OT-D15-default-instrument / OT-max-two-correlated-markets: the study's combine calls carry exec_exclude / prefer / max_exec from Params, and a combine_prefer run builds the partner book."""
    import inspect
    src = inspect.getsource(study)
    assert src.count("exec_exclude=p.combine_exec_exclude, prefer=p.combine_prefer, max_exec=p.max_exec_markets") == 2 and 'p.combine_prefer != "none"' in src


# --- no look-ahead: full run vs truncated runs --------------------------------------------------------------------------------------

LC = dict(lc_scalp=True, lc_adr_mult=0.7, lc_rev_need_htf=True, lc_tag=True)
LC_MSS = dict(lc_scalp=True, lc_mode="mss", lc_adr_k=0.9, lc_oneside=0.3)
ARR = dict(missed_5m=True, htf_converge=True, entry_arrays=("or_ref",), am_array_open=True)
PM = dict(two_session_smt=True, profile_two_session=True, smt_windows=((720, 810),), pm_nest_reversal=True, pm_reversal=True, profile_consol=True, profile_consol_pm=True, no_pm_after_am_win=True,
          allow_opposite_after_target="split")
OTE = dict(ote="limit", ote_fvg_overlap=True, ote_need_s=True)
TS = dict(turtle_soup="2023", ts_stop="mid", ts_breaker_pyramid=True, ts_breaker_ltf=True, ts_sessions=("PM",), reentry_ts=True)
RE = dict(reentry_after_win=True, reentry_win_max=2, reentry_need_sister=True, reentry_after_trail_win=True, trail=True, reentry_half=True, reentry_gate=True, reentry_idea_gate=True,
          reentry_trigger="sibi_return", reverse_after_failure="all", allow_opposite_after_target="both")
ADV = dict(adv_breaker=True, adv_rungs=True, breakaway_reentry=True)
TIME = dict(m0950_branch="both", m1050=True, protect_macro_ext=True, lh_ob_pullback=True, lh_after_target=True, last_hour_setup=True, moc_run=True, moc_range_dir=True, moc_no_chase_hod=True,
            lunch_macro_entry=True, lunch_htf_program=True, htf_bias="combo", london_ext_guard=True, cc09_gate="tag", nyx_model=True)
PAIR = dict(pairing="reversal_pool")
ALL_ON = {**LC, **ARR, **OTE, **TS, **RE, **ADV, **TIME, "entry_arrays": ("or_ref", "ob"), "allow_opposite_after_target": "both"}

ES_CASES = {
    # name: (window, tf, base, switches, the sm2.HITS counters the full run must have bumped, symbol)
    "lc": (("2022-03-07", "2022-03-28"), 5, ES_NB, LC, ("lc_scalp", "lc_rev_need_htf"), "ES"),
    "lc_mss": (("2023-10-02", "2023-10-23"), 5, ES_B, LC_MSS, ("lc_scalp",), "ES"),
    "arr": (("2023-06-05", "2023-06-26"), 5, ES_B, ARR, ("missed_5m", "htf_converge", "or_ref", "am_array_open"), "ES"),
    "pm": (("2024-09-16", "2024-10-07"), 5, ES_NB, PM, ("pm_nest_reversal", "profile_consol", "consol_pm", "two_session_smt_eval"), "ES"),
    "ote": (("2024-11-04", "2024-11-25"), 5, ES_NB, OTE, ("ote_overlap_sweet", "ote_overlap_edge", "ote_s"), "ES"),
    "ts": (("2023-06-05", "2023-06-26"), 5, ES_NB, TS, ("ts_session_drop", "reentry_ts", "ts_stop_mid", "ts_breaker_add", "ts_re_eval"), "ES"),
    "re_a": (("2022-06-20", "2022-07-11"), 5, ES_B, RE, ("reentry_idea_eval", "sibi_return", "reverse_at_stop", "offside_rev", "reverse_eval", "opposite_eval"), "ES"),
    "re_b": (("2022-03-07", "2022-03-28"), 5, ES_NB, RE, ("reverse_inversion", "sibi_return"), "ES"),
    "re_c": (("2024-02-19", "2024-03-11"), 5, ES_B, RE, ("reentry_after_trail_win", "trail_win_eval", "reentry_win_eval"), "ES"),
    "lod": (("2022-09-12", "2022-10-03"), 5, ES_B, RE, ("lod_short",), "ES"),
    "adv": (("2022-03-07", "2022-03-28"), 5, ES_B, ADV, ("adv_rungs", "breakaway_eval"), "ES"),
    "time_a": (("2022-08-01", "2022-08-22"), 5, ES_B, TIME, ("m1050", "protect_macro_ext", "moc_no_chase", "moc_range_eval", "lunch_macro", "lunch_program", "cc09_eval", "m0950_cont"), "ES"),
    "time_b": (("2022-01-03", "2022-01-24"), 5, ES_NB, TIME, ("lh_after_target", "london_ext_guard"), "ES"),
    "time_c": (("2023-03-06", "2023-03-27"), 5, ES_B, TIME, ("lh_ob_pullback",), "ES"),
    "pair": (("2022-03-07", "2022-03-28"), 5, ES_NB, PAIR, ("pairing_reversal_pool",), "ES"),
    "nq": (("2023-03-06", "2023-03-27"), 5, ES_B, dict(nq_overshoot_mult=2.0, mohawk_ticks=1.0), ("nq_overshoot",), "NQ"),
    # review-fix cases: the OUTCOME counters (a re-entry / reversal / London-lunch order that was armed AND filled, the 09:50 reversal's target), not only the evaluation counters
    "lon": (("2023-03-06", "2023-03-27"), 5, ES_NB, dict(missed_5m=True, missed_lon=True, london_kz=True, state_tag=True), ("missed_5m_lon", "missed_htf_target", "state_tag"), "ES"),
    "rev_inv": (("2022-05-30", "2022-06-20"), 5, ES_NB, dict(reverse_after_failure="inversion"), ("reverse_inversion", "re7_fill_reverse"), "ES"),
    "rev_prop": (("2022-08-01", "2022-08-22"), 5, ES_NB, dict(reverse_after_failure="prop_fail", entry_arrays=("propulsion",), prop_mt_exit=True), ("reverse_prop_fail", "re7_fill_reverse"), "ES"),
    "ts_re": (("2023-03-06", "2023-03-27"), 5, ES_NB, TS, ("reentry_ts", "re7_fill_ts_re"), "ES"),
    "time_d": (("2023-10-02", "2023-10-23"), 5, ES_B, TIME, ("m0950_rev_target", "m0950_cont"), "ES"),
    "time_f": (("2023-08-21", "2023-09-11"), 5, ES_B, TIME, ("nyx",), "ES"),
    "time_e": (("2022-02-14", "2022-03-07"), 5, ES_B, TIME, ("m0950_rev", "m0950_cont", "lunch_program"), "ES"),
}
SYN_CASES = {
    # name: (seed, switches, the HITS counters the full run must have bumped)
    "all_a": (3, {**ALL_ON, "ob_entry": "post_mss"}, ()),
    "all_b": (5, {**ALL_ON, "ob_entry": "post_mss"}, ()),
    "arr": (3, {**ARR, **PAIR, "ob_entry": "post_mss"}, ()),
}
_HITS = {}


@pytest.mark.parametrize("case", sorted(SYN_CASES))
def test_look_ahead_synthetic(case):
    seed, kw, need = SYN_CASES[case]
    x, y = B.synthetic(start="2026-04-06", end="2026-05-08", tf=5, seed=seed)
    p = Params(**{**SYN, **SYN_BASE, **kw})
    full, added = _la(x, 5, "RW", p, COLS7, every=3, partner=y)
    _check_ran(case, full, added, need)
    _HITS.setdefault(case, set()).update(added)


@pytest.mark.parametrize("seed", [3, 5])
def test_look_ahead_gappy_synthetic(seed):
    """Books WITH event gaps (the continuous ES frame has none) and the partner index: every switch of the chunk on at once, cuts at entry AND exit times."""
    x, y = _gappy(seed)
    p = Params(**{**SYN, **SYN_BASE, **ALL_ON, "ob_entry": "post_mss"})
    full, added = _la(x, 5, "RW", p, COLS7, every=2, partner=y)
    assert len(full) >= 1, full
    _HITS.setdefault("gappy%d" % seed, set()).update(added)


@pytest.mark.skipif(not ES, reason="no ES data")
@pytest.mark.parametrize("case", sorted(ES_CASES))
def test_look_ahead_es(case):
    (a, b), tf, base, kw, need, sym = ES_CASES[case]
    df, meta = _es_tf(tf, a, b)
    p = Params(**{**base, **kw})
    full, added = _la(df, tf, sym, p, COLS7, every=4, meta=meta, lag=2)
    _check_ran(case, full, added, need)
    _HITS.setdefault(case, set()).update(added)


# --- every switch of the chunk has an executed-path case -------------------------------------------------------------------------------

# the sm2.HITS counter that proves a switch's code path RAN (an outcome counter where a window reaches it, else the counter of the evaluation that precedes the outcome - the outcome is then unit-tested)
SWITCH_HIT = {
    "nq_overshoot_mult": "nq_overshoot", "lc_scalp": "lc_scalp", "lc_rev_need_htf": "lc_rev_need_htf", "missed_5m": "missed_5m", "htf_converge": "htf_converge", "am_array_open": "am_array_open",
    "ts_sessions": "ts_session_drop", "two_session_smt": "two_session_smt_eval", "pm_nest_reversal": "pm_nest_reversal", "profile_consol": "profile_consol", "ote_fvg_overlap": "ote_overlap_sweet",
    "ote_need_s": "ote_s", "ts_breaker_ltf": "ts_breaker_add", "reentry_after_win": "reentry_win_eval", "reentry_after_trail_win": "reentry_after_trail_win", "reentry_trigger": "sibi_return",
    "reentry_idea_gate": "reentry_idea_eval", "reverse_after_failure": "re7_fill_reverse", "allow_opposite_after_target": "opposite_eval", "adv_rungs": "adv_rungs", "reentry_ts": "re7_fill_ts_re",
    "breakaway_reentry": "breakaway_eval", "m0950_branch": "m0950_rev_target", "m1050": "m1050", "protect_macro_ext": "protect_macro_ext", "lh_ob_pullback": "lh_ob_pullback",
    "lh_after_target": "lh_after_target", "moc_range_dir": "moc_range_eval", "moc_no_chase_hod": "moc_no_chase", "lunch_macro_entry": "lunch_macro", "lunch_htf_program": "lunch_program",
    "london_ext_guard": "london_ext_guard", "cc09_gate": "cc09_eval", "nyx_model": "nyx", "pairing": "pairing_reversal_pool", "missed_lon": "missed_5m_lon", "state_tag": "state_tag",
}
# switches whose OUTCOME path (the win re-entry armed / the breakaway order created) no data window reaches: ES 2022-01 .. 2024-06 (3-week windows, ES_B / ES_NB bases) and 24 synthetic seeds never produced a
# reentry_after_win arming (a trade that closes on a non-final target with the draw untouched) or a breakaway_reentry order (two same-direction MSSs, a missed session and a retrace into the gap); their evaluation
# counters run in the full-vs-truncated cases, the outcome code is unit-tested (test_reentry_after_win, test_reentry_after_trail_win, test_breakaway_reentry_stop in test_caption_gap_sm7a.py)
OUTCOME_UNREACHED = {"reentry_after_win": "reentry_win_eval", "breakaway_reentry": "breakaway_eval"}
EXTRA_VALUES = {("entry_arrays", "or_ref"): "or_ref", ("ts_stop", "mid"): "ts_stop_mid"}
EXCEPTIONS = {
    "combine_prefer": "backtest.combine, not B.run: tested in test_combine_excludes_ym_and_prefers_es (test_caption_gap_sm7a.py)",
    "combine_exec_exclude": "backtest.combine, not B.run: tested in test_combine_excludes_ym_and_prefers_es / test_combine_caps_two_markets",
    "max_exec_markets": "backtest.combine, not B.run: tested in test_combine_caps_two_markets",
}
_RUN_KW = {}
for _c, (_w, _tf, _b, _kw, _need, _sym) in ES_CASES.items():
    _RUN_KW["es_" + _c] = (_kw, _need)
for _c, (_s, _kw, _need) in SYN_CASES.items():
    _RUN_KW["syn_" + _c] = (_kw, _need)


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
    assert all(SWITCH_HIT[k] == v for k, v in OUTCOME_UNREACHED.items())          # the two documented switches are covered by their evaluation counters
    for (field, value), hit_ in EXTRA_VALUES.items():
        assert any(field in kw and (value in kw[field] if isinstance(kw[field], tuple) else kw[field] == value) and hit_ in need for kw, need in _RUN_KW.values()), (field, value)
