"""Caption-gap pass, package targets_partials #3/4, part B: the study variants of the chunk and the no-look-ahead runs (full vs truncated runs, cut at entry AND exit times) that put every new switch on small date
windows - synthetic random-walk books (with a partner index, with and without event gaps, one across an FOMC day), short ES windows (5m) with the Confluence object and the HTF table, and forced hand-made days for
the ladder modes. Every behaviour switch has a run in which its code path EXECUTED (the sm2.HITS counters tp3.py bumps: "eval_*" = the switch's code was evaluated on real data where the situation itself is rare).
Tests that need local market data (ES) skip cleanly when it is absent; no platform-specific paths. The generic one-variant-per-run look-ahead test (test_bias_htf_lookahead.py) covers every study variant too."""
from datetime import date

import pandas as pd
import pytest

from mentorship import backtest as B, sm2, strategy as S, study, tp3
from mentorship.strategy import Params

from test_levels_detectors import ES
from test_caption_gap_ld1 import ENTRY, SYN
from test_caption_gap_sm2b import _check_ran, _es_tf, _la, ES_B, ES_NB, SYN_BASE, TAG_COLS
from test_caption_gap_sm6c import _gappy
from test_caption_gap_tp1a import _tp_run
from test_caption_gap_tp1b import _forced, _fp
from test_caption_gap_tp3a import GAP_IDS, KNOBS, NEW_SWITCHES

COLS = ENTRY + TAG_COLS + ["draw_px", "resist", "swing_grade", "near_miss"]


def test_study_variants_are_the_specified_ones():
    assert len(GAP_IDS) == 33
    D = study.DECISIONS
    assert D["L15-min-3r-final-draw"]["min_rr_final"] == 3.0 and D["X3-new-vs-experienced-partials"]["partial_mode"] == "new"
    assert D["X3-gradient-ladder-htf-target"]["partial_mode"] == "quarters" and D["D13-speed-bump-ladder-004"]["ladder_preset"] == "004" and D["X3-037-three-unit-ladder_ce"]["ladder037_ce"]
    assert D["X3-five-handle-first-partial-before-draw"]["fixed_partials"] == (5.25, 10.0) and D["L13-cc-extension-projections_midweek"]["proj_ext2"] == 1.68
    assert D["X2-pool-exit-at-or-before"]["pool_exit"] == "before" and D["X2-pdarray-exit-at-or-inside-edge_deep"]["fvg_target_level"] == "deep"
    assert len(study.exit_buffer_grid()) == 8
    # the SB bias switches are untouched by this chunk
    assert Params().sb_model is False and "sb_use_bias" in Params.__dataclass_fields__ and "want_all_engines" in Params.__dataclass_fields__


# --- synthetic books ---------------------------------------------------------------------------------------------------------------------------------------
# (a random-walk book has no confluence arrays and no overnight session: the switches that read them run in the ES windows)

SYN_CASES = {
    # name: (seed, switches, the sm2.HITS counters the full run must have bumped)
    "exits": (3, dict(pool_exit="before", pool_exit_fomc_before=True, fvg_target_level="deep", proj_kind=True, sd_targets=True, adr_target=True, adr_frac=1.0, adr_before_frac=0.15, adr_t2_htf=True,
                      adr_ext=True), ("eval_late3", "adr_before", "eval_exit_post")),
    "exits_b": (5, dict(pool_exit="at", fvg_target_level="at_edge", proj_kind=True, sd_targets=True, adr_target=True, adr_frac=1.0, adr_before_frac=0.15), ("adr_before",)),
    "targets_a": (3, dict(void_legs=True, mm_targets=True, mm_anchor="reanchor", dt_proj=True, grades60=True, daily_breaker_cap=True, weekly_beyond_mode="tag", min_rr_final=1.5, pool_prev_week=True,
                          pool_prev_month=True, target_past_eq60=True, proj_ext_anchor="stop_run", adr_conv_target=True, sd_targets=True), ("void_legs", "weekly_beyond", "mm_reanchor")),
    "targets_a5": (5, dict(void_legs=True, mm_targets=True, mm_anchor="reanchor", weekly_beyond_mode="tag", pool_prev_week=True, pool_prev_month=True), ("void_legs", "weekly_beyond", "monthly_beyond")),
    "impulse": (3, dict(mm_targets=True, mm_anchor="impulse"), ("mm_impulse",)),
    "ob_order": (3, dict(ob_target_order=True), ("ob_target_order",)),
    "pm_leg": (3, dict(pm_am_leg=True, pm_am_rb=True, pm_launch_filter=True), ("pm_am_leg",)),
    "consol": (3, dict(consol_overnight_targets=True, consol_day_rules="tag", wide_or_draw=True), ("consol_overnight",)),
    "new": (3, dict(partial_mode="new", energy_split=True, fixed_partials=(2.0, 4.0), no_collapse_htf=True, pool_milestone=0.5), ("partial_new", "fixed_partials", "energy_no_room")),
    "new_b": (5, dict(partial_mode="new", energy_split=True, fixed_partials=(2.0, 4.0), no_collapse_htf=True), ("partial_new", "fixed_partials", "energy_poke")),
    "pay": (5, dict(exit_mode2="pay_first", speed_skip=True), ("exit_pay_first",)),
    "ladder_004": (3, dict(ladder_preset="004"), ("ladder_004",)),
    "ladder_037": (3, dict(ladder_preset="037"), ("ladder_037",)),
    "quarters": (5, dict(partial_mode="quarters"), ("partial_quarters",)),
    "hold": (3, dict(exit_mode2="hold_runner"), ("exit_hold_runner",)),
    "full": (3, dict(exit_mode2="full_pull"), ("exit_full_pull",)),
    "terminus": (3, dict(partial_mode="terminus"), ("partial_terminus",)),
    "session_obj": (3, dict(session_obj_tf=True, draw_lock="session"), ("eval_late3",)),
}


@pytest.mark.parametrize("case", sorted(SYN_CASES))
def test_look_ahead_synthetic(case):
    seed, kw, need = SYN_CASES[case]
    x, y = B.synthetic(start="2026-04-06", end="2026-05-08", tf=5, seed=seed)
    p = Params(**{**SYN, **SYN_BASE, **kw})
    full, added = _la(x, 5, "RW", p, COLS, every=4, partner=y)
    _check_ran(case, full, added, need)


@pytest.mark.parametrize("seed", [3, 5])
def test_look_ahead_gappy_synthetic(seed):
    """Books WITH event gaps and the partner index: the target switches and a ladder mode at once, cuts at entry AND exit times."""
    x, y = _gappy(seed)
    p = Params(**{**SYN, **SYN_BASE, **dict(void_legs=True, mm_targets=True, mm_anchor="reanchor", weekly_beyond_mode="tag", pool_prev_week=True, partial_mode="new", energy_split=True,
                                            fixed_partials=(2.0,)), "ob_entry": "post_mss"})
    full, added = _la(x, 5, "RW", p, COLS, every=3, partner=y)
    assert len(full) >= 1, full
    assert added.get("partial_new")


def test_look_ahead_across_an_fomc_day():
    """2024-01-31 is an FOMC day: pool_exit_fomc_before switches the day to the 'before' exits - the days before and after run the usual ones."""
    x, y = B.synthetic(start="2024-01-22", end="2024-02-09", tf=5, seed=3)
    p = Params(**{**SYN, **SYN_BASE, **dict(pool_exit_fomc_before=True, pool_exit="beyond", partial_mode="new")})
    full, added = _la(x, 5, "RW", p, COLS, every=2, partner=y)
    assert len(full) >= 1 and added.get("pool_exit_fomc")


# --- ES windows (5m): the full run must have EXECUTED the code paths named ---------------------------------------------------------------------------------

W2, WL = ("2023-03-06", "2023-03-20"), ("2023-01-09", "2023-03-06")             # WL: ~40 sessions (the 60-day range, the daily breakers and the OR60 median need history)
SMP = dict(study.SM_POST)
SDX = dict(sd_targets=True, sd_levels=(1.0, 1.5, 2.0, 2.5, 3.0))
HT = ("15m", "1h", "4h", "D")
HTW = ("1h", "4h", "D", "W")
ES_CASES = {
    # name: (window, base, switches, counters)
    "void_mm": (W2, ES_NB, dict(SMP, void_legs=True, mm_targets=True, mm_anchor="reanchor", min_rr_final=2.0), ("void_legs", "mm_reanchor")),
    "ob_order": (W2, dict(ES_NB, ob_entry="both"), dict(ob_target_order=True, htf_targets=("1h", "4h", "D")), ("ob_target_order",)),
    "weekly_beyond": (W2, ES_NB, dict(SMP, weekly_beyond_mode="tag", pool_prev_week=True, pool_prev_month=True, dt_proj=True), ("weekly_beyond", "eval_dt")),
    "grades": (WL, ES_NB, dict(SMP, grades60=True, target_past_eq60=True, htf_targets=HTW), ("eval_grades60", "eval_past_eq")),
    "daily_breaker": (WL, ES_NB, dict(SMP, daily_breaker_cap=True), ("eval_daily_breaker",)),
    "ext_stop_run": (W2, ES_NB, dict(SMP, proj_ext_anchor="stop_run", htf_targets=HT), ("proj_ext_stop_run",)),
    "ext_midweek": (W2, ES_NB, dict(SMP, proj_ext_anchor="midweek", htf_targets=HT), ("eval_ext_levels",)),
    "adr": (W2, ES_NB, dict(SMP, adr_conv_target=True, adr_target=True, adr_frac=1.0, adr_t2_htf=True, adr_ext=True, adr_before_frac=0.15, **SDX, htf_targets=HT), ("adr_t2_htf", "adr_ext", "adr_before", "eval_adr_conv")),
    "pm": (W2, ES_NB, dict(SMP, pm_am_leg=True, pm_am_rb=True, pm_launch_filter=True), ("pm_am_leg", "eval_launch")),
    "session_obj": (W2, dict(ES_NB, draw_lock="session"), dict(session_obj_tf=True), ("eval_obj_lock", "session_obj_lock_rank")),
    "wide_or": (WL, dict(ES_NB, htf_bias="combo", use_bias=True), dict(SMP, wide_or_draw=True), ("eval_wide_or",)),
    "exits": (W2, ES_NB, dict(SMP, fvg_target_level="deep", pool_exit="before", pool_exit_fomc_before=True, proj_kind=True, htf_targets=HTW, **SDX), ("fvg_deep", "eval_exit_post")),
    "milestone": (W2, ES_B, dict(SMP, pool_milestone=0.5, no_collapse_htf=True, htf_targets=HT), ("pool_milestone", "no_collapse")),
    "quarters": (W2, ES_NB, dict(SMP, partial_mode="quarters", htf_targets=HTW), ("partial_quarters",)),
    "ladder_004": (W2, ES_NB, dict(SMP, ladder_preset="004", htf_targets=HT), ("ladder_004",)),
    "ladder_037": (W2, ES_NB, dict(SMP, ladder_preset="037", htf_targets=HT), ("ladder_037",)),
    "pay_first": (W2, ES_NB, dict(SMP, exit_mode2="pay_first", speed_skip=True), ("exit_pay_first",)),
    "energy": (W2, ES_NB, dict(SMP, energy_split=True, fixed_partials=(5.25, 10.0)), ("eval_energy", "fixed_partials")),
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
    tr = _forced(_fp(partial_mode="terminus"), ("partial_terminus",))
    assert len(tr[0].exits) == 1 and tr[0].exits[0][3] == "t1"
    tr = _forced(_fp(exit_mode2="hold_runner"), ("exit_hold_runner",))
    assert len(tr[0].exits) == 1
    tr = _forced(_fp(min_rr_final=5.0), ("eval_late3",))
    assert len(tr) == 1
    tr = _forced(_fp(fixed_partials=(1.0, 2.0), fixed_partial_fracs=(0.2, 0.2)), ("fixed_partials",))
    assert len(tr[0].exits) >= 3


def test_forced_projection_and_exit_switches():
    tr = _forced(_fp(proj_kind=True, mm_targets=True, pool_exit="at", fvg_target_level="at_edge"), ("eval_late3", "eval_exit_post"))
    assert len(tr) == 1


def test_defaults_do_not_change_a_run():
    ref = _tp_run()
    assert len(ref) == 1
    on = _tp_run(**{k: getattr(Params(), k) for k in KNOBS})
    assert [(t.entry, t.t1, t.t2, t.lv_tags, t.exits) for t in on] == [(t.entry, t.t1, t.t2, t.lv_tags, t.exits) for t in ref]
    assert not tp3.any_on(Params())
