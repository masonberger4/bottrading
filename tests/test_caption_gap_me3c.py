"""Caption-gap pass, package management_exits #3/3, part C: the defaults / validation of the 33 specs (management_partials_trailing_exits.md 109 .. 132, models_setups_entries.md 57 / 65 / 118 / 128 / 199,
session_day_week_stops_frequency.md 1 .. 30, stops_sizing_scaling_in.md 41 / 42, times_sessions_macros.md 8 / 16 / 25), their study variants, the engine wiring markers and the no-look-ahead runs (full vs
truncated runs, cut at entry AND exit times) that put every new switch on small date windows - synthetic random-walk books (with a partner index) and short ES windows (5m). Every behaviour switch has a
run in which its code path EXECUTED (the sm2.HITS counters me3.py bumps; "eval_*" = the switch's code was evaluated on real data where the situation itself is rare). Tests that need local market data
(ES) skip cleanly when it is absent; no platform-specific paths. The generic one-variant-per-run look-ahead test (test_bias_htf_lookahead.py) covers every study variant too."""
import inspect

import pytest

from mentorship import backtest as B, manage, me3, paper, strategy as S, study
from mentorship.strategy import Params
from dataclasses import dataclass as _oa_dc


@_oa_dc
class Params(Params):   # OA1029: these tests were written for the pre-build engine and exercise other rules - every OA1029 default back at its old value
    __annotations__ = {k: object for k in __import__('mentorship.study', fromlist=['OA1029_OLD']).OA1029_OLD}
    locals().update(__import__('mentorship.study', fromlist=['OA1029_OLD']).OA1029_OLD)

from test_levels_detectors import ES
from test_caption_gap_ld1 import ENTRY, SYN
from test_caption_gap_sm2b import _check_ran, _es_tf, _la, ES_NB, SYN_BASE, TAG_COLS

COLS = ENTRY + TAG_COLS
NEW_SWITCHES = ("implied_range", "vol_div_exit", "explosive_runner", "last_hour_target_done", "pm_two_stage", "london_tod_partials", "abort_blocks_side", "open_reclaim_runner",
                "reentry_breakaway", "ote_fail_ts", "lc_second_swipe", "am_idea_fail", "runner_stop_no_reentry", "session_fail_flatten", "pd3_pm_window", 
                "beginner_template", "late_week_flat", "recover_trail", "offside_flip", "lh_pool_timing", "am_exit_trend_hold", "pre_hold_open")
GAP_IDS = (
    "new-implied-range-behaviour", "new-rolling-bpr-ceiling", "new-laggard-slow-delivery", "new-volume-divergence-exit", "D16-am-trade-held-into-pm", "D16-big-range-day-runner-past-noon",
    "X11-last-hour-target-hit-done", "X11-two-stage-pm-delivery", "X10-cc-day-trade-exit-1400", "X10-london-time-of-day-scaleouts", "new-scalp-fixed-1to1-2h", "new-no-close-to-reenter",
    "new-no-working-stop-close-exit", "new-drawdown-recovery-exit", "T13-reclaim-0930-open-expansion", "new-reentry-after-breakaway-fill", "M12-ote-failure-turtle-soup", "X13-reentry-mechanics",
    "new-london-close-second-swipe-reentry", "X13-am-fail-no-reverse-pm-reset", "D18-reentry-count-max-2", "N3-021-citation-misread", "L15-chop-micro-scalps", "X7-three-failures-flatten-open-trade",
    "X14-new-trader-stop-when-day-positive", "X14-beginner-template-numbers", "X14-conflicted-htf-one-entry", "new-late-week-close-flat", "E7-reduce-size", "X8-offside-flip", "T10-1550-pool-timing",
    "T8-lunch-trending-days", "new-hold-pre0930-through-open",
)


def test_new_switch_defaults_and_validation():
    p = Params()
    assert all(getattr(p, k) is False for k in NEW_SWITCHES), "behaviour switches default off"
    assert (p.laggard_mult, p.vol_div_ratio, p.am_runner_hold_to, p.explosive_frac, p.explosive_until, p.cc_day_exit, p.london_tod_frac, p.scalp_mode, p.scalp_max_min, p.stop_ack_sec, p.recovery_exit,
            p.reentry_mode, p.reentry_cc_entry, p.lost_side_scope, p.pm_reset_t, p.reentry_count_max, p.reentry_ob_stop, p.runner_frac_done, p.chop_scalp_pts, p.chop_scalp_max, p.chop_scalp_day_pts,
            p.pm_after_am_win, p.beginner_target_pts, p.conflicted_mode, p.late_flat_t, p.abort_mode, p.abort_frac, p.lh_keep_frac, p.lh_late_ext_pts) == (
        1.0, 1.0, 0, 1.25, 900, 0, 0.25, "", 120, 0, "", "", "high", "day", 810, 1, "mt", 0.75, 0.0, 2, 5.0, "off", 12.5, "off", 900, "full", 0.5, 0.1, 3.0)
    assert p.day_mode_no_am_exit is True and p.new_day_stops is True                                   # (the two spec-implied defaults: day mode exempts itself from the 12:00 close; trader_mode "new" implies the day stops)
    assert not me3.any_on(p) and not me3.order_on(p)                    # the defaults leave the engine alone
    assert p.reentry_max == 2 and p.ladder_trail == "fvg" and p.sloppy_mode == "stand_aside" and p.trader_mode == ""     # the names / defaults that already existed are untouched
    assert p.sb_model is False and p.sb_use_bias == Params().sb_use_bias and p.want_all_engines == Params().want_all_engines
    for bad in (dict(lost_side_scope="week"), dict(abort_mode="third"), dict(scalp_mode="2to1"), dict(recovery_exit="pro"), dict(reentry_mode="x"), dict(reentry_cc_entry="mid"),
                dict(conflicted_mode="two"), dict(pm_after_am_win="yes"), dict(reentry_ob_stop="body"), dict(reentry_count_max=0), dict(lh_keep_frac=1.0), dict(runner_frac_done=0.0),
                dict(abort_frac=0.0), dict(laggard_mult=0.0), dict(vol_div_ratio=0.0), dict(london_tod_frac=1.5), dict(scalp_max_min=0), dict(chop_scalp_max=0), dict(pm_reset_t=2000),
                dict(late_flat_t=-1), dict(cc_day_exit=-5), dict(beginner_target_pts=0.0), dict(explosive_frac=0.0), dict(stop_ack_sec=-1), dict(ladder_trail="rolling_ceiling")):
        with pytest.raises(ValueError):
            Params(**bad)
    assert Params(ladder_trail="rolling_bpr").ladder_trail == "rolling_bpr" and me3.any_on(Params(ladder_trail="rolling_bpr"))
    for k in ("implied_range", "last_hour_target_done", "cc_day_exit", "scalp_mode", "abort_blocks_side"):
        assert me3.any_on(Params(**{k: (True if k != "cc_day_exit" else 840) if k != "scalp_mode" else "fixed_1to1"})), k


def test_study_variants_are_the_specified_ones():
    for g in GAP_IDS:
        names = [n for n in study.DECISIONS if n == g or n.startswith(g + "_")]
        assert names, g
        for n in names:
            Params(**study.DECISIONS[n])                                                       # every variant is a valid Params
    assert study.DECISIONS["new-rolling-bpr-ceiling"]["ladder_trail"] == "rolling_bpr"
    assert study.DECISIONS["D18-reentry-count-max-2"]["reentry_count_max"] == 2 and study.DECISIONS["X13-reentry-mechanics"]["reentry_mode"] == "cc_ob"
    assert study.DECISIONS["new-laggard-slow-delivery"]["laggard_mult"] == 2.0 and study.DECISIONS["L15-chop-micro-scalps"]["chop_scalp_pts"] == 2.5
    assert study.DECISIONS["X14-beginner-template-numbers"]["beginner_template"] is True and study.DECISIONS["E7-reduce-size"]["abort_mode"] == "half"


def test_engine_wiring_markers():
    """The hooks the specs name are wired into the engine (a regression guard for the call sites)."""
    src = inspect.getsource(S)
    for marker in ("_ME3.on_fill(", "_ME3.manage(", "_ME3.rung_pre(", "_ME3.rung_taken(", "_ME3.lh_all(", "_ME3.am_skip(", "_ME3.noon_exempt(", "_ME3.pre_close(", "_ME3.after_close(", "_ME3.bar(",
                   "_ME3.order_block(", "_ME3.re_order(", "_ME3.lost_side_holds(", "_ME3.risk_count(", "_ME3.eff_p(", "_ME3.conflicted_day(", "_ME3.flip_order(", "_ME3.count_reentry(", "_ME3.more_reentries("):
        assert marker in src, marker
    assert "ts_off" in inspect.getsource(manage.exits) and "abort_half" in inspect.getsource(manage._abort) and "flip_req" in inspect.getsource(manage.exits)
    assert "stall_off" in inspect.getsource(__import__("mentorship.me2", fromlist=["x"])._stall_exits)
    assert hasattr(paper, "StopAckWatch")
    assert "flat_week" in inspect.getsource(B.week_state)


def test_defaults_do_not_change_the_rows():
    """The new Trade column `laggard` is False everywhere while the switch is off."""
    x, y = B.synthetic(start="2026-04-06", end="2026-04-17", tf=5, seed=3)
    out = B.run(x, 5, "RW", Params(**{**SYN, **SYN_BASE}), partner=y)
    assert len(out) and "laggard" in out.columns and not out.laggard.any()


# --- synthetic books (a random-walk book has a partner index: laggard, the CC exit, the two-stage PM, the trend-day hold run here) ---------------------------------------------------------------------

OFF = dict(draw_lock="off", ob_entry="post_mss", htf_resist_cap=False)
NOON = dict(day_mode_auto=True, day_mode_no_am_exit=True, am_runner_hold_to=900, explosive_runner=True, am_exit_trend_hold=True, lh_pool_timing=True, last_hour_target_done=True, pm_two_stage=True,
            cc_day_exit=840, turtle_soup="cc_limit", pre_hold_open=True, pre_0900=True, pm=(780, 950), last_hour_own_slot=True, pm_last_hour_model=True, london_kz=True, london_tod_partials=True,
            pre_0700=True, time_stop_min=10, laggard_mult=2.0)
SYN_CASES = {
    # name: (seed, switches, the sm2.HITS counters the full run must have bumped)
    "noon_a": (3, NOON, ("laggard", "laggard_params", "cc_day_exit", "two_stage_hold", "eval_pre_hold_open")),
    "noon_b": (7, dict(NOON, trade_type="day"), ("trend_hold", "eval_trend_hold", "eval_explosive", "eval_am_runner_hold", "cc_day_exit", "laggard")),
    "range": (5, dict(implied_range=True, time_stop_min=10, vol_div_exit=True, ladder_trail="rolling_bpr", open_reclaim_runner=True, be_on="t1", **OFF), ("eval_implied_range", "eval_vol_div", "eval_open_reclaim", "eval_rolling_bpr", "bpr_roll")),
    "reentry": (3, dict(reentry_half=True, abort_blocks_side=True, fvg_abort=True, abort_mode="half", reentry_count_max=2, reentry_mode="cc_ob", reentry_breakaway=True, ote_fail_ts=True, ote="limit",
                        lc_second_swipe=True, lc_tag=True, recovery_exit="new", late_week_flat=True, recover_trail=True, offside_exit=True, offside_flip=True, runner_stop_no_reentry=True, reentry_ob_stop="full"),
                 ("reentry_count", "reentry_ob_low", "lc_second_swipe", "eval_abort_half", "eval_recovery", "eval_late_week_flat")),
    "stops": (5, dict(session_fail_flatten=True, session_stop_after_fails=3, pd3_pm_window=True, trader_mode="new", new_day_stops=True, pm_after_am_win="draw_open", conflicted_mode="one_win",
                      reverse_after_loss=False, lost_side_scope="session", am_idea_fail=True, chop_scalp_pts=2.5, sloppy_mode="scalp", scalp_mode="fixed_1to1", stop_ack_sec=10, **OFF), ("trader_mode_new", "eval_pm_window", "eval_session_fail", "new_day_positive")),
}


@pytest.mark.parametrize("case", sorted(SYN_CASES))
def test_look_ahead_synthetic(case):
    seed, kw, need = SYN_CASES[case]
    x, y = B.synthetic(start="2026-04-06", end="2026-06-05" if case == "noon_b" else "2026-05-08", tf=5, seed=seed)
    p = Params(**{**SYN, **SYN_BASE, **kw})
    full, added = _la(x, 5, "RW", p, COLS, every=4, partner=y)
    _check_ran(case, full, added, need)


# --- ES windows (5m): the full run must have EXECUTED the code paths named ------------------------------------------------------------------------------------------------------

SMP = dict(study.SM_POST)
W8 = ("2023-02-06", "2023-04-03")
W3 = ("2023-09-05", "2023-11-10")
ES_CASES = {
    # name: (window, base, switches, counters)
    "range": (W8, ES_NB, dict(SMP, implied_range=True, time_stop_min=10, laggard_mult=2.0, meander_bars=5, vol_div_exit=True, ladder_trail="rolling_bpr", open_reclaim_runner=True, be_on="t1"),
              ("eval_implied_range", "eval_rolling_bpr", "bpr_roll", "eval_open_reclaim", "open_reclaim", "reclaim_be_wait", "eval_vol_div", "vol_div", "eval_ir_top_raid")),
    "reentry": (W8, ES_NB, dict(SMP, reentry_half=True, abort_blocks_side=True, fvg_abort=True, abort_mode="half", reentry_count_max=2, reentry_mode="cc_ob", reentry_breakaway=True, ote_fail_ts=True,
                                lc_second_swipe=True, lc_tag=True, recovery_exit="new", late_week_flat=True, recover_trail=True, offside_exit=True, offside_flip=True, runner_stop_no_reentry=True,
                                reentry_after_trail_win=True, trail=True),
                ("abort_half", "reentry_count", "flat_week", "runner_stop", "abort_blocks_side", "eval_recovery", "eval_late_week_flat")),
    "stops": (W8, ES_NB, dict(SMP, session_fail_flatten=True, session_stop_after_fails=3, pd3_pm_window=True, trader_mode="new", pm_after_am_win="draw_open", conflicted_mode="one_win",
                              reverse_after_loss=False, lost_side_scope="session", am_idea_fail=True, chop_scalp_pts=2.5, sloppy_mode="scalp", scalp_mode="fixed_1to1"),
              ("conflicted_one_win", "new_day_positive", "scalp_1to1", "new_am_or_pm", "eval_session_fail", "eval_pm_window")),
    "stops_bias": (W8, ES_NB, dict(SMP, am_idea_fail=True, htf_bias="combo", session_fail_flatten=True, session_stop_after_fails=3, pd3_pm_window=True, reverse_after_loss=False,
                                   lost_side_scope="session"), ("eval_am_idea_fail", "eval_session_fail")),
    "ote": (W8, ES_NB, dict(SMP, reentry_half=True, ote="limit", ote_fail_ts=True, reentry_breakaway=True, offside_exit=True, offside_flip=True, breakaway="tag"),
            ("eval_breakaway_arm", "breakaway_fill_arm")),            # (the OTE turtle soup and the offside flip are rare on real data: the forced scenario-C look-ahead runs of test_caption_gap_me3d.py cover them)
    "lh": (W3, ES_NB, dict(SMP, lh_pool_timing=True, last_hour_target_done=True, pm=(780, 950), last_hour_own_slot=True, pm_last_hour_model=True, moc_run=True, pre_hold_open=True, pre_0900=True,
                           am_runner_hold_to=900, explosive_runner=True, am_exit_trend_hold=True, pm_two_stage=True),
           ("eval_lh_target",)),
    "noon": (W3, ES_NB, dict(SMP, **{k: v for k, v in NOON.items() if k not in ("cc_day_exit", "turtle_soup")}),
             ("eval_london_tod", "lon_0500")),
}


@pytest.mark.skipif(not ES, reason="no ES data")
@pytest.mark.parametrize("case", sorted(ES_CASES))
def test_look_ahead_es(case):
    (a, b), base, kw, need = ES_CASES[case]
    df, meta = _es_tf(5, a, b)
    p = Params(**{**base, **kw})
    full, added = _la(df, 5, "ES", p, COLS, every=6, meta=meta, lag=2)
    _check_ran(case, full, added, need)
