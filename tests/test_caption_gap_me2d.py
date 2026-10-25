"""Caption-gap pass, package management_exits #2/3, part D: the defaults / validation of the 34 specs (management_partials_trailing_exits.md 20 .. 108), their study variants and the no-look-ahead runs
(full vs truncated runs, cut at entry AND exit times) that put every new switch on small date windows - synthetic random-walk books (with a partner index), short ES windows (5m, one 1m) with the
Confluence object and the HTF table, and forced hand-made days for the hooks of the ladder loop. Every behaviour switch has a run in which its code path EXECUTED (the sm2.HITS counters me2.py
bumps; "eval_*" = the switch's code was evaluated on real data where the situation itself is rare). Tests that need local market data (ES) skip cleanly when it is absent; no platform-specific
paths. The generic one-variant-per-run look-ahead test (test_bias_htf_lookahead.py) covers every study variant too."""
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from mentorship import backtest as B, me1, me2, sm2, strategy as S, study
from mentorship.strategy import Params

from test_levels_detectors import ES
from test_caption_gap_ld1 import ENTRY, SYN
from test_caption_gap_sm2b import _check_ran, _es_tf, _la, ES_B, ES_NB, SYN_BASE, TAG_COLS
from test_caption_gap_tp1b import _forced, _fp

COLS = ENTRY + TAG_COLS
NEW_SWITCHES = ("trail_after_pool", "raise_on_vi", "raise_on_sth_break", "raise_need_5m_fvg", "trail_swing_at_array", "ob_stop_to_mt_after_run", "rde_partials", "peel_singles", "pm_macro_runner",
                "hh_low_hold", "marginal_ext_warn", "marginal_exit", "stall_exits", "wick_ce_close_test", "gap_q_hold", "ref_speed_check", "opp_tear_check", "edge_bump_add", "edge_bump_guard",
                "late_fvg_flip", "sister_breaker_hold", "stall_at_htf", "chop_close", "upclose_pair_guard", "urgency_runner", "pool_lock_day_done")
GAP_IDS = (
    "X5-tight-stop-under-swept-pool-near-target", "X5-no-trail-into-new-inefficiency", "X5-raise-stop-conditional-structure", "X5-trail-swing-low-at-intermediate-level", "X5-071-trail-anchors",
    "X5-ob-open-after-retests", "X5-structure-trail-and-cap", "X5-roll-after-wick-ce-cleared", "X5-stop-to-ob-mt-after-run", "X3-htf-target-bank-partial", "X3-running-down-equity-trigger",
    "X3-020-runner-peel-singles", "X3-027-pm-runner-macro", "X3-runner-swing-low-must-hold", "X3-marginal-lower-lows-warning", "X3-runner-stall-exits", "X3-nfp-wick-ce-ladder-close-test",
    "L16-adr5-60-80-closed", "M13-ote-leave-discount-fast", "X7-three-array-exit-trigger", "X8-hold-above-broken-session-highs", "X8-nwog-ce-pullback-hold", "X8-fast-through-next-reference",
    "X8-opposing-array-torn-through", "X8-broken-fvg-edge-bump-once", "X8-late-day-fvg-lost-hod-in", "X8-sister-index-breaker-hold", "X8-profitable-stall-exit", "X9-lethargic-or-choppy-trade",
    "X9-071-move-away-from-up-close-pair", "X9-speed-after-fulcrum-break", "A13-breaker-far-edge-partial", "new-small-fvg-last-line", "new-no-down-close-urgency",
)


def test_new_switch_defaults_and_validation():
    p = Params()
    assert all(getattr(p, k) is False for k in NEW_SWITCHES), "behaviour switches default off"
    assert (p.pool_lock_after, p.pool_lock_pts, p.ob_retests, p.trail_wick_gate, p.htf_bank, p.rde_arm, p.rde_frac, p.hh_low_frac, p.marginal_pts, p.marginal_n, p.stall_bars, p.adr_closed_min,
            p.ote_leave_bars, p.three_array_mode, p.pd3_close_frac, p.pd3_near_pts, p.held_hi_action, p.speed_k, p.ref_speed_bars, p.speed_pare, p.stall_at_htf_bars, p.after_chop_exit,
            p.fulcrum_speed_bars, p.breaker_far_partial, p.small_fvg_linger, p.urgency_stop_pts) == (0.8, 1.5, 0, "", 0.0, 0.75, 0.2, 1.0, 1.0, 2, 10, 0.0, 0, "", 0.5, 0.0, "", 1.5, 3, 0.5, 30,
                                                                                                      "end_session", 0, 0.0, 0, 1.0)
    assert me2.any_on(p) and not me2.any_on(Params(pool_lock_pts=0.0)) and p.ladder_trail == "fvg"      # (the spec's default 1.5-pt pool lock is the one switch that is on)
    for kw in (dict(trail_wick_gate="x"), dict(three_array_mode="x"), dict(held_hi_action="x"), dict(after_chop_exit="x"), dict(ladder_trail="x"), dict(pool_lock_pts=-1), dict(pool_lock_after=1.5),
               dict(ob_retests=-1), dict(htf_bank=1.0), dict(rde_arm=0), dict(rde_frac=0), dict(hh_low_frac=0), dict(marginal_n=0), dict(stall_bars=0), dict(adr_closed_min=1.0),
               dict(pd3_close_frac=0), dict(pd3_near_pts=-1), dict(speed_k=0), dict(ref_speed_bars=0), dict(speed_pare=0), dict(stall_at_htf_bars=0), dict(fulcrum_speed_bars=-1),
               dict(breaker_far_partial=1.0), dict(small_fvg_linger=-1), dict(urgency_stop_pts=-1)):
        with pytest.raises(ValueError):
            Params(**kw)
    for ok in ("candle_mt", "eq_pause", "rej_block", "071", "structure"):
        assert me2.any_on(Params(ladder_trail=ok))
    assert me2.any_on(Params(htf_bank=0.5)) and me2.any_on(Params(three_array_mode="close")) and me2.any_on(Params(pool_lock_pts=1.5))
    # the Silver Bullet bias switches are untouched by this chunk
    assert Params().sb_model is False and "sb_use_bias" in Params.__dataclass_fields__ and "want_all_engines" in Params.__dataclass_fields__
    assert "speed_bars" in Params.__dataclass_fields__ and "ref_speed_bars" in Params.__dataclass_fields__          # (the M1.3 sweep speed check keeps its name)


def test_study_variants_are_the_specified_ones():
    assert len(GAP_IDS) == 34
    D = study.DECISIONS
    for g in GAP_IDS:
        assert any(k == g or k.startswith(g + "_") for k in D), g                       # a variant per gap id (name prefix = the gap id)
    assert D["X5-tight-stop-under-swept-pool-near-target"]["pool_lock_pts"] == 1.5 and D["X5-071-trail-anchors"]["ladder_trail"] == "071"
    assert D["X7-three-array-exit-trigger_into"]["three_array_mode"] == "into" and D["X9-lethargic-or-choppy-trade_reentry"]["after_chop_exit"] == "reentry_allowed"
    assert D["X5-structure-trail-and-cap"]["ladder_trail"] == "structure" and D["A13-breaker-far-edge-partial_25"]["breaker_far_partial"] == 0.25
    names = list(study._ME2_DECISIONS)
    assert len(names) == len(set(names)) and all(D[k] is study._ME2_DECISIONS[k] for k in names)       # no variant name collides with an earlier one
    for k, v in D.items():
        if any(k == g or k.startswith(g + "_") for g in GAP_IDS):
            Params(**v)                                                                 # every variant is a valid Params set


def test_engine_wiring_markers():
    """The hooks the specs name are wired into the engine (a regression guard for the call sites)."""
    import inspect
    src = inspect.getsource(S)
    for marker in ("_ME2.on_fill(", "_ME2.manage(", "_ME2.rung_taken(", "_ME2.after_close(", "_ME2.chop_close(", "_ME2.order_block(", "_ME2.capv(", 'not pos.get("levels_frozen")'):
        assert marker in src, marker
    from mentorship import newscal
    assert "pm_macro_runner" in inspect.getsource(newscal.macro_wins)


# --- synthetic books (a random-walk book has no confluence arrays and no overnight session: the switches that read them run in the ES windows) ---------------------------------------------------------

OFF = dict(draw_lock="off", ob_entry="post_mss", htf_resist_cap=False)
SYN_CASES = {
    # name: (seed, switches, the sm2.HITS counters the full run must have bumped)
    "trails": (3, dict(ladder_trail="071", trail_wick_gate="trade", raise_on_vi=True, raise_on_sth_break=True, trail_swing_at_array=True, ob_retests=3, **OFF), ("eval_sth_break", "eval_ob_retests", "wick_gate_set")),
    "anchors": (3, dict(ladder_trail="071", **OFF), ("trail_candle_mt",)),
    "trails_b": (5, dict(ladder_trail="structure", trail_after_pool=True, ob_stop_to_mt_after_run=True, mt_mode="range", pool_lock_pts=1.5, entry_arrays=("ob",), **{**OFF, "ob_entry": "both"}), ("eval_structure", "eval_ob_mt")),
    "partials": (3, dict(rde_partials=True, hh_low_hold=True, marginal_ext_warn=True, stall_exits=True, adr_closed_min=0.7, htf_bank=0.5, peel_singles=True, **OFF), ("eval_rde", "eval_marginal", "eval_stall_exits")),
    "exits": (5, dict(three_array_mode="trade", pd3_near_pts=1.0, held_hi_action="partial", ref_speed_check=True, opp_tear_check=True, upclose_pair_guard=True, breaker_far_partial=0.5, **OFF),
              ("eval_held_hi", "eval_ref_speed", "eval_pair")),
    "late": (5, dict(late_fvg_flip=True, small_fvg_linger=2, urgency_runner=True, edge_bump_add=True, edge_bump_guard=True, gap_q_hold=True, pm_macro_runner=True, pm=(780, 950), **OFF),
             ("eval_late_fvg",)),
    "exits_b": (5, dict(three_array_mode="close", chop_close=True, wick_ce_close_test=True, fulcrum_speed_bars=5, sd_anchor="fulcrum", pm_macro_runner=True, pm=(780, 950), trail_wick_gate="close",
                        ladder_trail="candle_mt", **OFF), ("eval_pd3_mode", "pm_macro_exit", "wick_gate_set")),
    "exits_c": (5, dict(three_array_mode="into", stall_exits=True, stall_reh_against=True, ref_speed_check=True, **OFF), ("eval_stall_exits", "eval_ref_speed")),
}


@pytest.mark.parametrize("case", sorted(SYN_CASES))
def test_look_ahead_synthetic(case):
    seed, kw, need = SYN_CASES[case]
    x, y = B.synthetic(start="2026-04-06", end="2026-05-08", tf=5, seed=seed)
    p = Params(**{**SYN, **SYN_BASE, **kw})
    full, added = _la(x, 5, "RW", p, COLS, every=4, partner=y)
    _check_ran(case, full, added, need)


def test_look_ahead_synthetic_sister():
    """sister_breaker_hold with the partner index of the synthetic book (the sister's close under its breaker adds to the warn count): the code runs, truncated runs agree."""
    x, y = B.synthetic(start="2026-04-06", end="2026-05-08", tf=5, seed=3)
    p = Params(**{**SYN, **SYN_BASE, **OFF, "sister_breaker_hold": True, "three_array_mode": "trade"})
    full, added = _la(x, 5, "RW", p, COLS, every=4, partner=y)
    assert len(full) >= 1
    assert added.get("eval_sister"), f"the sister-breaker code never ran with the partner index (ran: {sorted(added)})"


# --- forced-path books (hand-made days): scenario C through run_day, full run vs runs truncated at every bar of the book -----------------------------------------------------------------------

def test_forced_urgency_and_pool_lock(monkeypatch):
    from test_caption_gap_es1a import C_ROWS
    # scenario C is an all up-close leg to T1: the urgency runner keeps 20 % (the rest is bulked at T1) on a stop 1 pt under the close
    tr = _forced(_fp(urgency_runner=True), ("urgency_runner",), rows=list(C_ROWS))
    assert [e[3] for e in tr[0].exits][:2] == ["t1", "t2"] or [e[3] for e in tr[0].exits][:1] == ["t1"]
    assert "urgency" in tr[0].mgmt_tags
    tr = _forced(_fp(urgency_runner=True, urgency_bulk=True), ("urgency_runner",), rows=list(C_ROWS))
    assert [e[3] for e in tr[0].exits][:2] == ["t1", "urgency_bulk"]
    # the pool lock of a two-rung ladder (the rungs relabelled 'pool'): the first rung is the last pool before the final one; 50 % closed is enough with pool_lock_after 0.4, the stop goes 1.5 pts under it
    orig = me2.on_fill

    def relabel(ctx, sd, pos, tr, o, i, p, fill):
        pos["level_kinds"] = ["pool", "pool"]
        return orig(ctx, sd, pos, tr, o, i, p, fill)
    monkeypatch.setattr(me2, "on_fill", relabel)
    rows = list(C_ROWS[:6]) + [(100.5, 103.6, 100.4, 103.4), (103.4, 103.5, 101.0, 101.2)]
    tr = _forced(_fp(pool_lock_pts=1.5, pool_lock_after=0.4), ("pool_lock", "pool_lock_no_reentry"), rows=rows)
    assert [e[3] for e in tr[0].exits] == ["t1", "be"] and tr[0].exits[1][1] == pytest.approx(102.0)


def test_forced_gap_q_and_peel(monkeypatch):
    """The NWOG CE rung (T1 103.5 = the CE of a 101-106 NWOG): the gap's lower quarter (102.25) is the hold line; with an 80 % first rung the single-lot peel runs above the CE."""
    from test_caption_gap_es1a import C_ROWS
    monkeypatch.setattr(me1, "_nwog_zone", lambda ctx, sd, i: (101.0, 106.0))
    rows = list(C_ROWS[:6]) + [(100.5, 103.6, 100.4, 103.6), (103.6, 103.7, 102.0, 103.4), (103.4, 103.5, 103.2, 103.4)]
    tr = _forced(_fp(gap_q_hold=True), ("gap_q_set", "gap_q_exit"), rows=rows)
    assert [e[3] for e in tr[0].exits][:2] == ["t1", "gap_q"]
    rows2 = list(C_ROWS[:6]) + [(100.5, 103.6, 100.4, 103.6), (103.6, 104.0, 103.3, 103.9), (103.9, 104.6, 103.7, 104.5), (104.5, 104.6, 104.2, 104.4)]
    tr = _forced(_fp(peel_singles=True, ladder_fracs=(0.8, 0.2)), ("peel",), rows=rows2)
    assert [e[3] for e in tr[0].exits][:2] == ["t1", "peel"]


def test_forced_wick_ce_close_test_and_htf_bank(monkeypatch):
    """The first rung relabelled 'wick' (scenario C has no wick-CE rung): the 10 % rung, BE + pad, and the 5m close test (a close above W = 103.5, then one under it, funds 30 %); and the HTF
    bank at a draw array 103.4-106 (monkeypatched: scenario C has no HTF confluence)."""
    from test_caption_gap_es1a import C_ROWS
    orig = me2.on_fill

    def relabel(ctx, sd, pos, tr, o, i, p, fill):
        pos["level_kinds"] = ["wick", "pool"]
        return orig(ctx, sd, pos, tr, o, i, p, fill)
    monkeypatch.setattr(me2, "on_fill", relabel)
    rows = list(C_ROWS[:6]) + [(100.5, 103.6, 100.4, 103.6), (103.6, 103.7, 103.0, 103.3), (103.3, 103.4, 103.0, 103.2)]
    tr = _forced(_fp(wick_ce_close_test=True), ("wick_ce_first", "wick_ce_fund"), rows=rows)
    assert [e[3] for e in tr[0].exits][:2] == ["t1", "fund"]
    assert tr[0].exits[0][2] == pytest.approx(0.1 * tr[0].shares, abs=1) and tr[0].exits[1][2] == pytest.approx(0.3 * tr[0].shares, abs=1)
    monkeypatch.setattr(me2, "on_fill", orig)
    monkeypatch.setattr(me2, "_htf_draw", lambda ctx, sd, pos, fill, i, p: (103.4, 106.0))
    rows = list(C_ROWS[:6]) + [(100.5, 103.6, 100.4, 103.6), (103.6, 103.7, 103.0, 103.3)]
    tr = _forced(_fp(htf_bank=0.5), ("htf_bank",), rows=rows)
    assert [e[3] for e in tr[0].exits][:2] == ["t1", "htf_bank"] and tr[0].exits[1][2] == pytest.approx(tr[0].shares / 4, abs=1)      # T1 first, then half of what is left


def test_forced_fulcrum_speed_and_chop_close(monkeypatch):
    """Review round 1: forced runs (full vs truncated at every bar) of the two paths no random book reaches. fulcrum_speed_bars: the two rungs relabelled pool / sd on a fulcrum-anchored trade - the
    pool break (the T1 bar) is followed by two bars short of the SD rung; chop_close: the intraday Chop turns on (monkeypatched) while the position is open."""
    from test_caption_gap_es1a import C_ROWS
    orig = me2.on_fill

    def relabel(ctx, sd, pos, tr, o, i, p, fill):
        pos["level_kinds"] = ["pool", "sd"]
        return orig(ctx, sd, pos, tr, o, i, p, fill)
    monkeypatch.setattr(me2, "on_fill", relabel)
    rows = list(C_ROWS[:6]) + [(100.5, 103.6, 100.4, 103.4), (103.4, 103.6, 103.0, 103.2), (103.2, 103.4, 103.0, 103.1), (103.1, 103.3, 102.9, 103.0)]
    tr = _forced(_fp(fulcrum_speed_bars=2, sd_anchor="fulcrum"), ("eval_fulcrum_speed", "fulcrum_slow"), rows=rows)
    assert "fulcrum_slow" in [e[3] for e in tr[0].exits]
    monkeypatch.setattr(me2, "on_fill", orig)
    upd = S.Chop.update

    def chop_on(self, i):
        r = upd(self, i)
        if self.ctx.t[i] == 610 and not self.on:
            self.on, self.on_at, self.hi, self.lo = True, i, float(self.ctx.h[i]), float(self.ctx.l[i])
            self.state[i] = True
        return self.on
    monkeypatch.setattr(S.Chop, "update", chop_on)
    tr = _forced(_fp(chop_close=True, sloppy_tests=("chop",)), ("chop_close", "eval_chop_on"), rows=rows)
    assert "chop_close" in [e[3] for e in tr[0].exits]


# --- ES windows (5m): the full run must have EXECUTED the code paths named ------------------------------------------------------------------------------------------------------

SMP = dict(study.SM_POST)
W8 = ("2023-02-06", "2023-04-03")
W3 = ("2023-09-05", "2023-11-10")
HTW = ("1h", "4h", "D", "W")
ES_CASES = {
    # name: (window, base, switches, counters)
    "a": (W8, ES_NB, dict(SMP, pool_lock_pts=1.5, pool_lock_day_done=True, raise_on_vi=True, raise_on_sth_break=True, trail_swing_at_array=True, ladder_trail="071", ob_retests=3),
          ("eval_pool_lock", "raise_on_vi", "raise_on_sth_break", "trail_candle_mt")),
    "b": (W8, ES_NB, dict(SMP, ladder_trail="structure", trail_wick_gate="trade", trail_after_pool=True, ob_stop_to_mt_after_run=True, mt_mode="range", ob_retests=3, entry_arrays=("ob",)),
          ("structure_step1", "wick_gate_set", "eval_trail_after_pool", "eval_ob_mt", "eval_ob_retests")),
    "c": (W8, ES_NB, dict(SMP, rde_partials=True, hh_low_hold=True, marginal_ext_warn=True, marginal_exit=True, stall_exits=True, adr_closed_min=0.7, three_array_mode="trade", pd3_near_pts=1.0),
          ("rde_armed", "hh_low_exit", "eval_marginal", "eval_stall_exits", "adr_true_up", "pd3_trade")),
    "d": (W8, ES_NB, dict(SMP, held_hi_action="partial", ref_speed_check=True, opp_tear_check=True, edge_bump_add=True, edge_bump_guard=True, upclose_pair_guard=True, breaker_far_partial=0.5),
          ("held_hi_lost", "ref_speed_fail", "opp_tear_warn", "edge_bump_guard", "pair_stall", "eval_bz_far")),
    "e": (W8, ES_NB, dict(SMP, late_fvg_flip=True, small_fvg_linger=2, urgency_runner=True, pm_macro_runner=True, pm=(780, 950), htf_bank=0.5, htf_targets=HTW, gap_q_hold=True, held_hi_action="tighten"),
          ("eval_late_fvg", "eval_small_fvg", "urgency_runner", "pm_macro_first", "eval_htf_bank")),
    "f": (W3, ES_NB, dict(SMP, peel_singles=True, gap_q_hold=True, stall_at_htf=True, htf_targets=HTW, ote_leave_bars=3, entry_arrays=("ote",), chop_close=True, sloppy_tests=("chop",),
                          wick_ce_close_test=True, wick_partials=True),
          ("eval_stall_htf_week", "ote_slow")),                 # (the peel itself is armed by a target NWOG / a rung at its CE: test_forced_gap_q_and_peel runs it)
    "g": (W3, ES_NB, dict(SMP, ladder_trail="eq_pause", raise_on_vi=True, ob_retests=2, rde_partials=True, ref_speed_check=True, fulcrum_speed_bars=5, sd_anchor="fulcrum", sd_targets=True,
                          sister_breaker_hold=True, three_array_mode="close", edge_bump_guard=True, fulcrum_exit="ladder"),
          ("eval_ob_retests", "eval_rde", "eval_ref_speed")),
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


@pytest.mark.skipif(not (ES and Path("data/mentorship/ES_1min_db.csv").exists()), reason="no ES 1m data")
def test_look_ahead_es_1m():
    """The one-minute book: the 5m aggregation of raise_need_5m_fvg / small_fvg_linger runs on 1m bars (a short window); every run is compared with its truncations."""
    df, meta = _es_tf(1, "2023-03-06", "2023-03-24")
    p = Params(**{**ES_NB, **SMP, "raise_on_vi": True, "raise_on_sth_break": True, "raise_need_5m_fvg": True, "small_fvg_linger": 2, "ladder_trail": "candle_mt", "ob_retests": 3})
    full, added = _la(df, 1, "ES", p, COLS, every=3, meta=meta, lag=2)
    _check_ran("1m", full, added, ("eval_sth_break", "eval_small_fvg"))
