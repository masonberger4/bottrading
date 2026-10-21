"""Caption-gap pass, package setups_models #2/7, part B: the study variants of the chunk and the no-look-ahead runs (full vs truncated) that put every new switch of
the chunk on small date windows - a synthetic 5-week book (the engine's gates, tags and setups on random walks) and a 2.5-week ES window with the Confluence object and
the HTF table. Tests that need local market data (ES) skip cleanly when it is absent; no platform-specific paths."""
import warnings

import pandas as pd
import pytest

from mentorship import backtest as B, sm2, study
from mentorship.strategy import Params

from test_levels_detectors import ES
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
    "turtle_cc": ("reswept", "ts_next_array", "itl_context"),
    "setups": ("state", "consol_fade", "gap_edge"),
}
SEED_REQUIRED_HITS = {("turtle", 3): ("reswept",), ("turtle", 5): ("smt_three_point",)}        # (the random walks differ: each seed reaches one of the two paths)
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


def test_every_new_switch_is_in_a_look_ahead_run():
    """Every behaviour switch of this chunk is on in one of the no-look-ahead runs (the synthetic / ES groups)."""
    cover = str(GROUPS)
    tuning = {"dfvg_large_pts", "nwog_sr_stop_pts", "ts_min_beyond_pts", "org_sig_adr", "raid_level", "micro_range_adr", "tails_tol_ticks", "consol_bars", "consol_adr",
              "daily_first_days", "or_rb_from", "or_rb_bear", "reclaimed_def"}
    for s_ in NEW_SWITCHES:
        if s_ in tuning:
            continue
        assert s_ in cover, s_
