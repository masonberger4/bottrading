"""Caption-gap pass, package setups_models #2/7, part B: the study variants of the chunk and the no-look-ahead runs (full vs truncated) that put every new switch of
the chunk on small date windows - a synthetic 5-week book (the engine's gates, tags and setups on random walks) and a 2.5-week ES window with the Confluence object and
the HTF table. Tests that need local market data (ES) skip cleanly when it is absent; no platform-specific paths."""
import warnings

import pandas as pd
import pytest

from mentorship import backtest as B, sm2, study
from mentorship.strategy import Params

from test_levels_detectors import ES, NY
from test_caption_gap_ld1 import ENTRY, EXIT, SYN
from test_caption_gap_sm2a import NEW_SWITCHES

GAP_IDS = (
    "A5-premium-half-daily-fvg", "L5-nwog-sr-levels", "new-stop-run-overshoot-next-array", "L5-quarter-level-no-imbalance", "L6-ndog-nwog-primary-entry",
    "L7-gap-up-premium-template", "A18-reclaimed-ob-codeable", "A18-traded-through-ok", "A19-mss-when-raid-missing", "A19-mss-no-rel-sweep-with-htf-draw",
    "A19-reh-short-term-low-trap", "N-micro-structure-regime", "M12-second-takeout-turtle-soup", "A21-pre-trigger-dealing-range", "A8-ifvg-narrative-liquidity-run",
    "A8-ifvg-stacked-tails-exclusion", "A7-immediate-rebalance-gates", "A11-bpr-levels-ce-rejection", "A12-range-internal-ignore", "A19-second-mss-no-new-low",
    "A24-reaper-definition", "A4-wick-poke-vi-invalidation", "A8-ifvg-before-pool", "A8-ifvg-depth-tolerances", "A2-delivery-vs-liquidity", "A4-ltf-body-qualification",
    "new-state-to-array-map", "A4-sweep-body-cluster", "B18-smt-accum-distrib", "new-divergence-types", "A17-index-or-rejection-block", "A22-htf-definition-nested-arrays",
    "new-consolidation-exit-direction", "new-price-engine-models", "new-intermediate-term-hl-fade", "B18-smt-three-point-swing",
)


def test_every_gap_id_has_a_study_variant_that_builds():
    on = set()
    for g in GAP_IDS:
        vs = [v for v in study.DECISIONS if v == g or v.startswith(g + "_")]
        assert vs, g
        for v in vs:
            Params(**study.DECISIONS[v])                                                                              # validates
            on |= set(study.DECISIONS[v])
    tuning = {"dfvg_large_pts", "nwog_sr_stop_pts", "ts_min_beyond_pts", "org_sig_adr", "raid_level", "micro_range_adr", "tails_tol_ticks", "consol_bars", "consol_adr",
              "daily_first_days", "or_rb_from", "or_rb_bear", "ts_skip_reswept", "ir_need_draw", "ir_need_window", "state_machine_helper"}
    missing = [s for s in NEW_SWITCHES if s not in on and s not in tuning]
    assert not missing, missing
    assert study.DECISIONS["A8-ifvg-depth-tolerances"]["ifvg_depth"] == "w_cap"
    assert study.DECISIONS["B18-smt-three-point-swing"]["smt_mode"] == "three_point"


# --- no look-ahead: full run vs truncated runs --------------------------------------------------------------------------------------

SYN_BASE = dict(use_bias=True, bias_open="0930", ob_entry="both", draw_lock_neutral="both")
GROUPS = {
    "gates": dict(dfvg_half="tag", reh_trap=True, org_two_rally=True, poke_high_cancel=True, state_machine=True, state_tool_map=True, div_tag=True,
                  daily_first_return=True, micro_regime=True, mss_ref_raid=True, mss_eq_wait=True, mss_eq_wait_unless_draw=True, sweep_ref="body",
                  ir_entries=True, ir_need_draw=True, ir_need_window=True, mmxm_ctx=True, mm_ssl_target=True),
    "arrays": dict(ifvg_entries=True, ifvg_need_run=True, ifvg_over_pool_pref=True, ifvg_tails_block=True, ifvg_pool_intact=True, ifvg_depth="w_cap",
                   reclaimed_ob=True, reclaimed_def="loose", entry_arrays=("bpr_ce", "reclaimed_ob"), range_lock=True, mss_rearm_lower_high=True,
                   reaper=True, reaper_def="ob_overlap", breaker_entry="fallback", breaker_range_hold=True, htf_entry_arrays=(15, 60), htf_body_qual=True),
    "turtle": dict(turtle_soup="2023", ts_next_array=True, ts_skip_reswept=True, ts_need_smt=True, ts_itl_context=True, second_break_partial=True, smt_mode="three_point",
                   smt_pre=True, smt_windows=((570, 660),), smt_min=0),
    "turtle_cc": dict(turtle_soup="cc_limit", ts_next_array=True, ts_skip_reswept=True, ts_itl_context=True, second_break_partial=True),
    "setups": dict(nwog_sr_entries=True, gap_edge_entry=True, gap_quarter_retrace=True, or_rb=True, consol_fade=True, org_two_rally=True, state_machine=True,
                   pm_reversal=True, pm_rev_nested=True),
}
# the code paths each group's switches must have RUN in its full run (sm2.HITS counts the calls of the function that carries them); the rest are unit-tested
REQUIRED_HITS = {
    "gates": ("raid_ref", "div_tag", "state", "ir_gates", "eq_wait_waived"),
    "arrays": ("bpr_ce", "reaper_ob", "htf_body_qual", "reclaimed_loose"),
    "turtle": (),
    "turtle_cc": ("ts_next_array", "itl_context"),
    "setups": ("state", "consol_fade", "gap_edge"),
}
SEED_REQUIRED_HITS = {("turtle", 5): ("smt_three_point",)}        # (the random walks differ: each seed reaches one of the two paths)
ES_REQUIRED_HITS = {
    "gates": ("raid_ref", "dfvg_half", "org_two_rally", "poke_cancel", "div_tag", "ir_gates"),
    "arrays": ("bpr_ce", "reaper_ob", "htf_body_qual", "reclaimed_loose"),
    "turtle": ("reswept",),
    "setups": ("nwog_sr", "or_rb", "consol_fade", "gap_edge", "gap_quarter", "pm_rev_nested", "org_two_rally"),
}
_HITS = {}


def _la(df, tf, sym, p, cols, every=3, meta=None, lag=2, **kw):
    """Cuts at entry AND exit times (as test_caption_gap_sm1b._la), tolerant of a run without trades; returns (full, the sm2.HITS the full run added)."""
    h0 = dict(sm2.HITS)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        full = B.run(df, tf, sym, p, meta=meta, **kw)
        added = {k: v - h0.get(k, 0) for k, v in sm2.HITS.items() if v - h0.get(k, 0)}
        if not len(full):
            return full, added
        cuts = sorted(set(full.entry_time.iloc[::every]) | set(full.exit_time.dropna().iloc[::every]))
        for cut_t in cuts:
            c = cut_t + pd.Timedelta(minutes=lag)
            pk = {k: (v[v.index <= c] if isinstance(v, pd.DataFrame) else v) for k, v in kw.items()}
            part = B.run(df[df.index <= c], tf, sym, p, partial_last=True, meta=meta, **pk)
            a = full[full.entry_time <= cut_t][cols].reset_index(drop=True)
            b = part[part.entry_time <= cut_t][cols].reset_index(drop=True)
            pd.testing.assert_frame_equal(a, b, check_dtype=False)
            done = full.exit_time.notna() & (full.exit_time <= cut_t)
            a = full[done][EXIT].reset_index(drop=True)
            b = part[part.entry_time.isin(full[done].entry_time)][EXIT].reset_index(drop=True)
            pd.testing.assert_frame_equal(a, b, check_dtype=False)
    return full, added


TAG_COLS = ["lv_tags", "setup_model", "delivery", "div_type"]


@pytest.mark.parametrize("group", sorted(GROUPS))
@pytest.mark.parametrize("seed", [3, 5])
def test_look_ahead_synthetic(group, seed):
    """Full run vs truncated runs (cut at entry AND exit times) on a short synthetic window; every group's switches are on."""
    x, y = B.synthetic(start="2026-04-06", end="2026-05-08", tf=5, seed=seed)
    p = Params(**{**SYN, **SYN_BASE, **GROUPS[group]})
    full, added = _la(x, 5, "RW", p, ENTRY + TAG_COLS, every=3, partner=y)
    _HITS.setdefault(group, {}).update(added)
    missing = [h for h in REQUIRED_HITS[group] + SEED_REQUIRED_HITS.get((group, seed), ()) if not added.get(h)]
    assert not missing, (group, missing, added)


def _es(a="2023-09-05", b="2023-11-10"):
    df = B.load("ES", 5, source="databento")
    return df[(df.index >= a) & (df.index < b)], B.load_meta("ES", 5)


@pytest.mark.skipif(not ES, reason="no ES data")
@pytest.mark.parametrize("group", ["gates", "arrays", "turtle", "setups"])
def test_look_ahead_es_switches(group):
    """ES 5m with confluence, the HTF table and the overnight sessions (a 10 week window): the order gates that need the Confluence object and the day tables."""
    df, meta = _es()
    base = dict(es_pt=1.0, lot=1, max_notional=1e12, cost_per_share=0.1, ob_entry="post_mss", leg_pd=0, min_draw_pts=0, htf_resist_cap=False, draw_lock="off",
                htf_bias="combo", nwog_regime="tag")
    p = Params(**{**base, **GROUPS[group]})
    full, added = _la(df, 5, "ES", p, ENTRY + ["draw_px"] + TAG_COLS, every=6, meta=meta)
    missing = [h for h in ES_REQUIRED_HITS[group] if not added.get(h)]
    assert not missing, (group, missing, added)                                                              # the new code ran


# --- executed-path cases: every switch of the chunk has a no-look-ahead run in which its code RAN, or an explicit reason it cannot be reached by data -----------------
# (as test_caption_gap_sm1c): each case names the sm2.HITS counters that must have RUN in its full run, the run must hold a trade, and the truncated runs must agree.
SYN_S = dict(SYN)
SYN_CASES = {
    "tails": (7, dict(ifvg_entries=True, ifvg_tails_block=True, tails_tol_ticks=6), ("ifvg_tails",)),
    "range": (5, dict(range_lock=True), ("range_lock", "range_locked")),
    "reswept": (4, dict(turtle_soup="2023", ts_skip_reswept=True), ("reswept",)),
    "ts_smt": (4, dict(turtle_soup="2023", ts_need_smt=True, smt_min=0), ("ts_need_smt",)),
    "ts_next": (4, dict(turtle_soup="2023", ts_next_array=True), ("ts_next_array_turtle",)),
    "brk_hold": (5, dict(breaker_range_hold=True, breaker_entry="fallback"), ("breaker_hold",)),
    "sweep_body": (3, dict(sweep_ref="body"), ("sweep_body",)),
    "w_cap": (5, dict(ifvg_entries=True, ifvg_depth="w_cap", ifvg_entry="quadrant"), ("ifvg_w_cap", "ifvg_quadrant")),
    "ifvg_run": (5, dict(ifvg_entries=True, ifvg_need_run=True), ("ifvg_run",)),
    "ifvg_pool": (5, dict(ifvg_entries=True, ifvg_pool_intact=True), ("ifvg_pool",)),
}
ES_B = dict(es_pt=1.0, lot=1, max_notional=1e12, cost_per_share=0.1, ob_entry="post_mss", leg_pd=0, min_draw_pts=0, htf_resist_cap=False, draw_lock="off", htf_bias="combo")
ES_NB = dict(ES_B, htf_bias="off", use_bias=False)                       # (no bias filter: more trades)
W_A, W_D, W_C, W_L = ("2023-10-02", "2023-10-23"), ("2024-05-13", "2024-06-03"), ("2024-02-19", "2024-03-11"), ("2024-09-16", "2024-10-07")
ES_CASES = {
    "rearm": (W_A, 5, ES_B, dict(mss_rearm_lower_high=True, mmxm_ctx=True, mm_ssl_target=True, entry_arrays=("bpr_ce",), bpr_left_far_edge=True, turtle_soup="external",
                                 htf_body_qual=True), ("mss_rearm", "mm_ssl", "bpr_far_edge", "htf_body_qual_zone")),
    "late": (W_L, 5, ES_NB, dict(mss_rearm_lower_high=True, ifvg_entries=True, ifvg_far_edge_tag=True), ("mss_rearm_ce2", "ifvg_far_edge")),
    "trigger": (W_D, 5, ES_B, dict(breaker_range_trigger=True, breaker_entry="fallback"), ("breaker_trigger_order",)),
    "waive": (W_C, 5, dict(ES_B, draw_lock="session"), dict(mss_eq_wait=True, mss_eq_wait_unless_draw=True), ("eq_wait_waived",)),
    "micro": (("2023-11-06", "2023-11-22"), 1, ES_NB, dict(micro_regime=True, micro_range_adr=0.5), ("micro_regime",)),
}
_ESC = {}


def _es_tf(tf, a, b):
    if tf not in _ESC:
        _ESC[tf] = (B.load("ES", tf, source="databento"), B.load_meta("ES", tf))
    raw, meta = _ESC[tf]
    return raw[(raw.index >= pd.Timestamp(a, tz=NY)) & (raw.index < pd.Timestamp(b, tz=NY))], meta


def _check_ran(name, full, added, need):
    assert len(full) >= 1, f"{name}: the window made no trade"
    missing = [h for h in need if not added.get(h)]
    assert not missing, f"{name}: these paths did not run: {missing} (ran: {sorted(added)})"


@pytest.mark.parametrize("case", sorted(SYN_CASES))
def test_look_ahead_synthetic_executed_paths(case):
    seed, kw, need = SYN_CASES[case]
    x, y = B.synthetic(start="2026-04-06", end="2026-05-08", tf=5, seed=seed)
    p = Params(**{**SYN_S, **SYN_BASE, **kw})
    full, added = _la(x, 5, "RW", p, ENTRY + TAG_COLS, every=3, partner=y)
    _check_ran(case, full, added, need)


@pytest.mark.skipif(not ES, reason="no ES data")
@pytest.mark.parametrize("case", sorted(ES_CASES))
def test_look_ahead_es_executed_paths(case):
    (a, b), tf, base, kw, need = ES_CASES[case]
    df, meta = _es_tf(tf, a, b)
    p = Params(**{**base, **kw})
    full, added = _la(df, tf, "ES", p, ENTRY + ["draw_px"] + TAG_COLS, every=4, meta=meta, lag=1 if tf == 1 else 2)
    _check_ran(case, full, added, need)


NEW_SWITCHES_B = ("bpr_left_far_edge", "ifvg_far_edge_tag", "breaker_range_trigger", "daily_first_ltf")
# the sm2.HITS counter that proves a switch's code path RAN
SWITCH_HIT = {
    "dfvg_half": "dfvg_half", "nwog_sr_entries": "nwog_sr", "ts_next_array": "ts_next_array_turtle", "gap_quarter_retrace": "gap_quarter", "gap_edge_entry": "gap_edge",
    "org_two_rally": "org_two_rally", "reclaimed_def": "reclaimed_loose", "mss_ref_raid": "raid_ref", "mss_eq_wait_unless_draw": "eq_wait_waived", "micro_regime": "micro_regime",
    "ts_skip_reswept": "reswept", "breaker_range_hold": "breaker_hold", "ifvg_need_run": "ifvg_run", "ifvg_tails_block": "ifvg_tails", "range_lock": "range_locked",
    "mss_rearm_lower_high": "mss_rearm", "reaper_def": "reaper_ob", "poke_high_cancel": "poke_cancel", "ifvg_pool_intact": "ifvg_pool", "mm_ssl_target": "mm_ssl",
    "htf_body_qual": "htf_body_qual", "state_tool_map": "state", "state_machine": "state", "sweep_ref": "sweep_body", "ts_need_smt": "ts_need_smt", "div_tag": "div_tag",
    "or_rb": "or_rb", "pm_rev_nested": "pm_rev_nested", "consol_fade": "consol_fade", "ts_itl_context": "itl_context", "smt_mode": "smt_three_point",
    "bpr_left_far_edge": "bpr_far_edge", "ifvg_far_edge_tag": "ifvg_far_edge", "breaker_range_trigger": "breaker_trigger_order", "ifvg_depth": "ifvg_w_cap",
    "ir_need_draw": "ir_gates", "ir_need_window": "ir_gates",
}
# no data window reaches these (the test of each is a unit test in test_caption_gap_sm2a.py, the gates' wiring is checked by the order_gate2 / run_day fixtures there)
EXCEPTIONS = {
    "reh_trap": "the gate needs an AGAINST-bias order to reach order completion; the main loop's side filter drops those sides in every bias-filtered run, and without a bias reading the gate is n/a",
    "second_break_partial": "targets are untraded pools by construction: a target pool already traded before the fill does not occur in real or random data (unit + run_day tests)",
    "daily_first_return": "needs a rel-eq sweep that is the first return to a daily body cluster in 30+ sessions: ~50 sweeps over 2022-2024 ES never met the cluster test",
    "daily_first_ltf": "as daily_first_return",
    "daily_first_days": "tuning of daily_first_return",
    "ifvg_over_pool_pref": "the preference branch needs two IFVGs after one sweep with a taken pool outside the first: 12 random-walk seeds never produced it",
}
TUNING = {"dfvg_large_pts", "nwog_sr_stop_pts", "ts_min_beyond_pts", "org_sig_adr", "raid_level", "micro_range_adr", "tails_tol_ticks", "consol_bars", "consol_adr", "or_rb_from",
          "or_rb_bear", "state_machine_helper"}


def _ran_by(name_switch):
    """The cases / groups whose run puts `name_switch` ON and whose REQUIRED hits include the counter that proves its code path ran."""
    hit_ = SWITCH_HIT[name_switch]
    out = []
    for g, kw in GROUPS.items():
        need = set(REQUIRED_HITS.get(g, ())) | set(ES_REQUIRED_HITS.get(g, ())) | {h for (gg, _), hs in SEED_REQUIRED_HITS.items() if gg == g for h in hs}
        if name_switch in kw and hit_ in need:
            out.append(g)
    for c, (_, kw, need) in SYN_CASES.items():
        if name_switch in kw and hit_ in need:
            out.append(c)
    for c, (_, _, _, kw, need) in ES_CASES.items():
        if name_switch in kw and hit_ in need:
            out.append(c)
    return out


def test_every_switch_of_the_chunk_has_an_executed_path_case():
    """Every behaviour switch of the chunk is ON in a no-look-ahead run that must have EXECUTED its code path (its sm2.HITS counter is in that run's required hits), or it
    is listed in EXCEPTIONS with the reason data cannot reach it (not a string search of the group dicts)."""
    missing = []
    for s_ in NEW_SWITCHES + NEW_SWITCHES_B + ("ifvg_depth", "ir_need_draw", "ir_need_window"):
        if s_ in TUNING or s_ in EXCEPTIONS:
            continue
        if s_ not in SWITCH_HIT or not _ran_by(s_):
            missing.append(s_)
    assert not missing, missing
    assert not set(EXCEPTIONS) & {s_ for s_ in SWITCH_HIT}, "an excepted switch has a hit mapping"
    assert all(len(v) > 15 for v in EXCEPTIONS.values())
