"""Caption-gap pass, package management_exits #1/3, part B: the study variants of the chunk and the no-look-ahead runs (full vs truncated runs, cut at entry AND exit times) that put every new switch
on small date windows - synthetic random-walk books (with a partner index), short ES windows (5m, one 1m) with the Confluence object and the HTF table, and forced hand-made days for the mid-trade hooks.
Every behaviour switch has a run in which its code path EXECUTED (the sm2.HITS counters me1.py bumps; "eval_*" = the switch's code was evaluated on real data where the situation itself is rare).
Tests that need local market data (ES) skip cleanly when it is absent; no platform-specific paths. The generic one-variant-per-run look-ahead test (test_bias_htf_lookahead.py) covers every study
variant too."""
from datetime import date

import numpy as np
import pandas as pd
import pytest

from mentorship import backtest as B, me1, sm2, strategy as S, study
from mentorship.strategy import Params

from test_levels_detectors import ES
from test_caption_gap_ld1 import ENTRY, SYN
from test_caption_gap_sm2b import _check_ran, _es_tf, _la, ES_B, ES_NB, SYN_BASE, TAG_COLS
from test_caption_gap_tp1b import _forced, _fp
from test_review_fixes import A_ROWS
from test_caption_gap_me1a import GAP_IDS, KNOBS, MODES, NEW_SWITCHES

COLS = ENTRY + TAG_COLS


def test_study_variants_are_the_specified_ones():
    assert len(GAP_IDS) == 34
    D = study.DECISIONS
    for g in GAP_IDS:
        assert any(k == g or k.startswith(g + "_") for k in D), g                       # a variant per gap id (name prefix = the gap id)
    assert D["A11-bpr-retrace-allowance_far_edge"]["bpr_limit"] == "far_edge" and D["A13-breaker-mt-trade-test"]["breaker_mt_test"] == "trade"
    assert D["E1-manual-touch-exits"]["exit_fill"] == "touch_1tick" and D["X4-be-vi-then-new-ssl"]["be_mode"] == "vi_then_new_ssl" and D["D14-be-after-adr-fraction_05"]["be_adr"] == 0.5
    assert D["X5-runner-stop-half-open-profit_half_profit"]["runner_stop"] == "half_profit" and D["A8-ifvg-15m-body-failure"]["ifvg_fail_tf"] == 15
    assert D["N5-hold-through-0830_off"]["no_entry_0825"] is False and D["new-position-trade-grading-fib"]["pos_switch_frac"] == 0.5
    for k, v in D.items():
        if any(k == g or k.startswith(g + "_") for g in GAP_IDS):
            Params(**v)                                                                 # every variant is a valid Params set
    # the SB bias switches are untouched by this chunk
    assert Params().sb_model is False and "sb_use_bias" in Params.__dataclass_fields__ and "want_all_engines" in Params.__dataclass_fields__


# --- synthetic books ---------------------------------------------------------------------------------------------------------------------------------------
# (a random-walk book has no confluence arrays and no overnight session: the switches that read them run in the ES windows)

OFF = dict(draw_lock="off", ob_entry="post_mss", htf_resist_cap=False)
SYN_CASES = {
    # name: (seed, switches, the sm2.HITS counters the full run must have bumped)
    "stops": (3, dict(be_mode="adr_frac", be_adr=0.3, runner_stop="leg_eq", runner_eq_after=0.5, trail_confirm=True, **OFF), ("eval_be_adr_frac", "eval_runner_lock", "eval_trail_confirm")),
    "stops_b": (5, dict(be_mode="through_opposing_fvg", event_eve_lock=True, be_cap_htf=True, **OFF), ("eval_be_through_opposing_fvg", "eval_be_cap")),
    "exits": (3, dict(run_through_bars=2, run_through_ticks=8.0, hold_reached=True, iof_intraday_exit=True, vi_mid_exit=True, **OFF), ("iof_exit",)),
    "tags": (5, dict(nwog_traverse_hold=True, heavy_gauge=True, far_half_no_adds=True, rip_through=True, resistance_def="speed", resistance_mode="low_full", **OFF), ("rip", "far_half_block")),
    "fill": (3, dict(exit_fill="touch_1tick", best_case_limit=True, fvg_full_fill_void=True, ce_exit="trade", ce_hold=True, breaker_mt_test="trade", **OFF), ()),
    "mode": (5, dict(be_mode="vi_then_new_ssl", refusal_breakaway=True, no_lunch_retrace_hold=True, thu_cap=True, **OFF), ("eval_be_vi_then_new_ssl",)),
}


@pytest.mark.parametrize("case", sorted(SYN_CASES))
def test_look_ahead_synthetic(case):
    seed, kw, need = SYN_CASES[case]
    x, y = B.synthetic(start="2026-04-06", end="2026-05-08", tf=5, seed=seed)
    p = Params(**{**SYN, **SYN_BASE, **kw})
    full, added = _la(x, 5, "RW", p, COLS, every=4, partner=y)
    _check_ran(case, full, added, need)


# --- ES windows (5m): the full run must have EXECUTED the code paths named ---------------------------------------------------------------------------------

SMP = dict(study.SM_POST)
W8 = ("2023-02-06", "2023-04-03")
HTW = ("1h", "4h", "D", "W")
ES_CASES = {
    # name: (window, base, switches, counters)
    "a": (W8, ES_NB, dict(SMP, nwog_traverse_hold=True, heavy_gauge=True, far_half_no_adds=True, rip_through=True, refusal_breakaway=True, iof_intraday_exit=True, run_through_bars=3, hold_reached=True),
          ("eval_nwog", "nwog_traverse", "eval_heavy", "heavy_scale", "heavy_t1_skip", "hold_reached_exit", "hold_reached_done", "iof_exit", "rip")),
    "b": (W8, ES_NB, dict(SMP, best_case_limit=True, exit_fill="touch_1tick", be_mode="vi_then_new_ssl"),
          ("eval_best_case", "best_case_hold", "best_case_weak", "eval_be_vi_then_new_ssl", "be_vi", "be_new_ssl")),
    "c": (W8, ES_NB, dict(SMP, be_mode="through_opposing_fvg", runner_stop="leg_eq", event_eve_lock=True, trail_confirm=True),
          ("eval_be_through_opposing_fvg", "be_opp_fvg", "eval_runner_lock", "runner_lock_leg_eq", "eval_trail_confirm", "trail_confirmed", "trail_confirm_void")),
    "d": (W8, ES_NB, dict(SMP, be_mode="adr_frac", be_cap_htf=True, htf_targets=HTW, fvg_full_fill_void=True, resistance_def="speed", resistance_mode="low_full", vi_mid_exit=True),
          ("eval_be_adr_frac", "eval_be_cap", "be_cap_1", "fvg_void_fill", "resist_speed", "resist_speed_full")),
    "e": (W8, ES_NB, dict(SMP, bpr_abort=True, bpr_limit="far_edge", breaker_mt_test="trade", ce_hold=True, ce_exit="trade", fvg_bpr_backstop=True, fvg_abort=True),
          ("bpr_limit_exit", "breaker_mt_trade", "ce_trade")),
    "f": (W8, ES_NB, dict(SMP, ifvg_fail_tf=15, ifvg_entries=True, ifvg_hold=True), ("ifvg15_exit",)),
    "g": (W8, ES_NB, dict(SMP, run_through_bars=3, run_through_ticks=12.0, be_mode="adr_frac", be_adr=0.2, runner_stop="leg_eq", runner_eq_after=0.5, event_eve_lock=True),
          ("rt_stall", "rt_stall_exit", "be_adr_frac", "runner_lock_leg_eq")),
    "h": (W8, ES_NB, dict(SMP, fvg_bpr_backstop=True, fvg_abort=True, bpr_abort=True, refusal_breakaway=True, far_half_no_adds=True), ("fvg_bpr_backstop",)),
    "i": (W8, ES_NB, dict(SMP, sd_time_roll=True, sd_targets=True, sd_window=(600, 720), sd_anchor="entry_low"), ()),
    "j": (W8, ES_NB, dict(SMP, sd_body_hold=True, sd_targets=True), ()),
    "k": (W8, ES_B, dict(SMP, no_lunch_retrace_hold=True, thu_cap=True, pre_0700=True, day_mode_auto=True, hold_through_0830=True, ma_deuce=True), ()),
}


@pytest.mark.skipif(not ES, reason="no ES data")
@pytest.mark.parametrize("case", sorted(ES_CASES))
def test_look_ahead_es(case):
    (a, b), base, kw, need = ES_CASES[case]
    df, meta = _es_tf(5, a, b)
    p = Params(**{**base, **kw})
    full, added = _la(df, 5, "ES", p, COLS, every=6, meta=meta, lag=2)
    if need:
        _check_ran(case, full, added, need)


@pytest.mark.skipif(not ES, reason="no ES data")
def test_look_ahead_es_1m_tick_match():
    """tick_match_hold reads the 3m candles of one-minute bars: a short 1m window (the candles are evaluated; the tick-matched BPR itself is rare)."""
    df, meta = _es_tf(1, "2023-03-06", "2023-03-24")
    p = Params(**{**ES_NB, **SMP, "tick_match_hold": True, "nwog_traverse_hold": True, "heavy_gauge": True})
    full, added = _la(df, 1, "ES", p, COLS, every=3, meta=meta, lag=2)
    _check_ran("tick_match", full, added, ("eval_tick_match",))


@pytest.mark.skipif(not ES, reason="no ES data")
def test_hold_through_0830_ma_deuce_on_real_bars():
    """N5-hold-through-0830: 2024-03-14 (PPI 08:30): the Ma Deuce short is out at the close of the 08:20 bar by default (pre_0830, flat_0830_extras); with hold_through_0830 it is held through the
    release (the unmanaged first build was stopped at 08:30)."""
    from dataclasses import replace
    df = B.load("ES", 5, source="databento")
    df = df[(df.index >= "2024-03-01") & (df.index < "2024-03-16")]
    p = replace(Params(es_pt=1.0, lot=1, max_notional=1e12, cost_per_share=0.1, leg_pd=0, min_draw_pts=0, sb_model=True, ma_deuce=True), **{**study.PRE_OWNER, "flat_0830_extras": True})
    d = pd.Timestamp("2024-03-14").date()
    a = B.run(df, 5, "ES", p)
    b = B.run(df, 5, "ES", replace(p, hold_through_0830=True))
    ma, mb = a[(a.setup == "ma_deuce") & (a.date == d)], b[(b.setup == "ma_deuce") & (b.date == d)]
    assert len(ma) == 1 and ma.exit_reason.iloc[0] == "pre_0830"
    assert len(mb) == 1 and mb.exit_reason.iloc[0] != "pre_0830"                               # held through the release (stopped or targeted later)


# --- forced-path books (hand-made days): scenario C through run_day, full run vs runs truncated at every bar of the book -----------------------------------

C_BASE = dict(ob_entry="post_mss")


def test_forced_ladder_hooks():
    from test_caption_gap_es1a import C_ROWS
    rows = list(C_ROWS)
    tr = _forced(_fp(best_case_limit=True), ("best_case_hold",), rows=rows + [(108.4, 108.5, 103.0, 103.2)])
    assert [e[3] for e in tr[0].exits][:2] == ["t1", "bulk_O"]
    weak = list(C_ROWS)
    weak[7] = (102.9, 108.3, 102.8, 108.2)
    tr = _forced(_fp(best_case_limit=True), ("best_case_weak",), rows=weak)
    assert [e[3] for e in tr[0].exits] == ["t1", "bulk_O", "bulk_O"]
    tap = [(100.5, 103.5, 100.4, 103.4), (103.4, 103.45, 102.9, 103.0), (103.0, 103.1, 102.4, 102.6), (102.6, 102.7, 102.2, 102.5)] + [(102.5, 102.6, 102.4, 102.5)] * 3
    tr = _forced(_fp(run_through_bars=3), ("rt_stall", "rt_stall_exit"), rows=list(C_ROWS[:6]) + tap)
    assert [e[3] for e in tr[0].exits][:2] == ["t1", "rt_stall_exit"]
    rows2 = list(C_ROWS[:6]) + [(100.5, 103.6, 100.4, 103.6), (103.6, 103.7, 102.0, 103.4), (103.4, 103.5, 103.2, 103.4)]
    tr = _forced(_fp(hold_reached=True), ("hold_reached_exit", "hold_reached_done"), rows=rows2)
    assert [e[3] for e in tr[0].exits][:2] == ["t1", "hold_lost"]
    tr = _forced(_fp(exit_fill="touch_1tick"), (), rows=list(C_ROWS[:6]) + [(100.5, 103.25, 100.4, 103.2), (103.2, 103.3, 103.0, 103.1)] + [(103.1, 103.2, 103.0, 103.1)] * 2)
    assert tr[0].exits[0][3] == "t1"
    rows3 = list(C_ROWS)
    rows3[5] = (101.6, 101.7, 99.7, 100.5)
    tr = _forced(_fp(fvg_full_fill_void=True), ("fvg_void_fill",), rows=rows3)
    assert [e[3] for e in tr[0].exits] == ["fvg_void"]
    tr = _forced(_fp(resistance_def="speed", resistance_mode="low_full"), ("resist_speed",))
    assert tr[0].resist_speed == "low"


def test_forced_sd_rungs(monkeypatch):
    """The SD rung hooks of the ladder loop with the rung kinds relabelled 'proj' (scenario C has no SD levels): a roll before the window, the window exit, and the body-hold deferral."""
    from test_caption_gap_es1a import C_ROWS
    orig = me1.on_fill

    def relabel(ctx, sd, pos, tr, o, i, p, fill):
        pos["level_kinds"] = ["proj"] * len(pos["levels"])
        return orig(ctx, sd, pos, tr, o, i, p, fill)
    monkeypatch.setattr(me1, "on_fill", relabel)
    tr = _forced(_fp(sd_time_roll=True, sd_window=(615, 720)), ("sd_roll",))
    assert [e[3] for e in tr[0].exits] == ["t2"]                                           # T1 (10:05) is before the window: it rolls; the last rung is the final exit
    tr = _forced(_fp(sd_time_roll=True, sd_window=(600, 720)), ("sd_window_exit",))
    assert [e[3] for e in tr[0].exits] == ["sd_window"] and tr[0].final_hit
    rows = list(C_ROWS[:7]) + [(102.9, 104.0, 102.8, 103.8), (103.8, 104.2, 103.6, 104.0), (104.0, 104.1, 103.0, 103.2)]
    tr = _forced(_fp(sd_body_hold=True), ("sd_body_hold", "sd_body_release"), rows=rows)
    assert tr[0].exits[0][3] == "t1" and tr[0].exits[0][1] == pytest.approx(103.2)


def test_forced_lunch_hold():
    """A long from 09:55 that rallies slowly to 103.4 by noon (T1 103.5 is not reached) and holds the lunch above 102.5: with no_lunch_retrace_hold it stays to 15:50, else out at 12:00."""
    from test_caption_gap_es1a import C_ROWS
    rows = list(C_ROWS[:6])
    px = 100.5
    for k in range(6, 42):                                   # 10:00 .. 12:55: climb to 103.4 by 11:55, then the lunch holds above 102.6
        m = 570 + 5 * k
        px = min(103.4, px + 0.09) if m < 720 else 103.2
        rows.append((px, px + 0.05, px - 0.1 if m >= 720 else px - 0.05, px))
    on = _forced(_fp(no_lunch_retrace_hold=True), ("lunch_hold",), rows=rows)
    off = _forced(_fp(no_lunch_retrace_hold=False), (), rows=rows)
    assert [e[3] for e in off[0].exits] == ["am_exit"]
    assert [e[3] for e in on[0].exits] == ["lunch_hold_exit"] and str(on[0].exits[0][0])[11:16] == "15:45"


def test_forced_day_mode_auto(monkeypatch):
    from test_review_fixes import A_LOCK, BASE
    monkeypatch.setattr(me1, "day_pick", lambda ctx, sd, i, p, entry: True)
    rows = A_ROWS[:5] + [(100.3, 103.0, 100.2, 102.9), (102.9, 103.0, 99.8, 100.1), (100.1, 100.5, 99.0, 99.5)]
    tr = _forced(Params(**BASE, min_risk_pts=0.3, day_mode_auto=True, be_on="t1"), (), rows=rows, spike=True, lock=A_LOCK)
    assert "day_auto" in tr[0].lv_tags and "day_trade" in tr[0].lv_tags
