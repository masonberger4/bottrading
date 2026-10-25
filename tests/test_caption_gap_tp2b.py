"""Caption-gap pass, package targets_partials #2/4, part B: the study variants of the chunk and the no-look-ahead runs (full vs truncated runs, cut at entry AND exit times) that put every new switch on small date
windows - synthetic random-walk books (with a partner index, with and without event gaps), short ES windows (5m) with the Confluence object and the HTF table, and forced hand-made days for the paths no window
reaches. Every behaviour switch has a run in which its code path EXECUTED (the sm2.HITS counters tp2.py / the hooks bump: "eval_*" = the switch's code was evaluated on real data where the situation itself is rare).
Tests that need local market data (ES) skip cleanly when it is absent; no platform-specific paths. The generic one-variant-per-run look-ahead test (test_bias_htf_lookahead.py) covers every study variant too."""
from dataclasses import replace
from datetime import date

import numpy as np
import pandas as pd
import pytest

from mentorship import backtest as B, sm2, strategy as S, study, tp2
from mentorship.strategy import Params

from test_levels_detectors import ES
from test_caption_gap_ld1 import ENTRY, SYN
from test_caption_gap_sm2b import _check_ran, _es_tf, _la, ES_B, ES_NB, SYN_BASE, TAG_COLS
from test_caption_gap_sm6c import _gappy
from test_review_fixes import BASE, D0, history
from test_caption_gap_tp1a import C_ROWS, POST, _tp_run
from test_caption_gap_tp1b import _forced, _fp
from test_caption_gap_tp2a import GAP_IDS, KNOBS, NEW_SWITCHES

NY = "America/New_York"
COLS = ENTRY + TAG_COLS + ["draw_px", "resist", "swing_grade"]


def test_every_gap_id_has_a_study_variant_that_builds():
    assert len(GAP_IDS) == 33
    on = set()
    for g in GAP_IDS:
        vs = [v for v in study.DECISIONS if v == g or v.startswith(g + "_")]
        assert vs, g
        for v in vs:
            Params(**study.DECISIONS[v])
            on |= set(study.DECISIONS[v])
    missing = [s for s in NEW_SWITCHES if s not in on]
    assert not missing, missing
    D = study.DECISIONS
    assert D["L14-session-pools-only_rank"]["session_pools_mode"] == "rank" and D["D23-inception-fulcrum-anchor"]["sd_fulcrum_def"] == "inception"
    assert D["L12-minus3-sd-last-hour"]["sd_anchor"] == "mss_leg" and D["L12-projection-exit-1tick"]["sd_anchor"] == "entry_low"


# --- synthetic books ---------------------------------------------------------------------------------------------------------------------------------------
# (a random-walk book has no confluence arrays and no overnight session: the switches that read them run in the ES windows)

TARGETS_ON = dict(defended_filter=True, defended_touches=2, defended_band_adr=0.2, break_accel_gate=True, swept_pool_targets=True, session_pools_mode="extended", event_horizon_target=True,
                  t1_skip_near=True, min_draw_pts=1.0, confl_rank=True, beyond_pool_final=True, hrlr_time_k=3.0, nwog_magnet=True, nwog_ladder=True, wick_tfs=("1h",), wick_long_only=True, min_obj_frac=0.2,
                  room_ref="htf_far", overnight_5m_fvgs=True, htf_ob_open=True, htf_gap_gate=True, keep_traded_wfvg=True, org_draw="draw", org_beyond=True, org_ce_if_flow=True, org_breaker_stop=True)
SD_ON = dict(sd_targets=True, sd_arm="close", sd_ref_roll=True, sd_cap_htf=True, sd_deep_conv=True, sd_multi_tiers=("itl", "ltl"), proj_exit_ticks=1, sd_levels=(1.0, 1.5, 2.0, 2.5, 3.0))
SYN_CASES = {
    # name: (seed, switches, the sm2.HITS counters the full run must have bumped)
    "targets": (3, TARGETS_ON, ("eval_late", "eval_defended", "eval_break_accel", "eval_swept")),
    "targets_b": (5, {**TARGETS_ON, "ob_entry": "both", "session_pools_mode": "rank", "session_pool_first": True, "eq_pref": "rank"}, ("eval_late", "eval_defended")),
    "sd_broken": (3, dict(SD_ON, sd_anchor="broken", sd_premium_consol=True), ("eval_sd_arm", "eval_tiers")),
    "sd_broken_b": (5, dict(SD_ON, sd_anchor="broken", sd_premium_consol=True), ("eval_sd_arm",)),
    "sd_m15": (3, dict(SD_ON, sd_anchor="m15_leg", sd_htf_extreme=True, sd_htf_tol=2.0), ("eval_m15_leg",)),
    "sd_last_hour": (3, dict(SD_ON, sd_anchor="mss_leg", sd_last_hour_k=2.0), ("eval_sd_arm",)),
    "sd_entry_low": (3, dict(SD_ON, sd_anchor="entry_low"), ("eval_entry_low",)),
    "sd_inception": (3, dict(SD_ON, sd_anchor="fulcrum", sd_fulcrum_def="inception"), ("eval_inception",)),
    "sd_inception_b": (5, dict(SD_ON, sd_anchor="fulcrum", sd_fulcrum_def="inception"), ("eval_inception",)),
}


@pytest.mark.parametrize("case", sorted(SYN_CASES))
def test_look_ahead_synthetic(case):
    seed, kw, need = SYN_CASES[case]
    x, y = B.synthetic(start="2026-04-06", end="2026-05-08", tf=5, seed=seed)
    p = Params(**{**SYN, **SYN_BASE, **kw})
    h0 = dict(sm2.HITS)
    full, added = _la(x, 5, "RW", p, COLS, every=3, partner=y)
    _check_ran(case, full, added, need)


@pytest.mark.parametrize("seed", [3, 5])
def test_look_ahead_gappy_synthetic(seed):
    """Books WITH event gaps and the partner index: both groups of switches at once, cuts at entry AND exit times."""
    x, y = _gappy(seed)
    p = Params(**{**SYN, **SYN_BASE, **TARGETS_ON, "hrlr_time_k": 0.0, "ob_entry": "post_mss"})
    full, added = _la(x, 5, "RW", p, COLS, every=2, partner=y)
    assert len(full) >= 1, full
    q = Params(**{**SYN, **SYN_BASE, **dict(SD_ON, sd_anchor="broken", proj_org_reprice=True, proj_org_kmax=4, proj_breaker=True, proj_breaker_k=(1.0, 2.0)), "ob_entry": "post_mss"})
    full, added = _la(x, 5, "RW", q, COLS, every=2, partner=y)
    assert len(full) >= 1, full


# --- ES windows (5m): the full run must have EXECUTED the code paths named ---------------------------------------------------------------------------------

W2, W3, WN, WE, WC = ("2023-03-06", "2023-03-20"), ("2023-06-05", "2023-06-19"), ("2023-05-01", "2023-05-15"), ("2023-02-06", "2023-02-20"), ("2024-02-19", "2024-03-04")
SMP = dict(study.SM_POST)
SDX = dict(sd_targets=True, sd_levels=(1.0, 1.5, 2.0, 2.5, 3.0))
ES_CASES = {
    # name: (window, base, switches, counters)
    "defended": (W2, ES_NB, dict(SMP, defended_filter=True, defended_touches=2, defended_band_adr=0.2), ("eval_defended",)),
    "break_accel": (W2, ES_NB, dict(SMP, break_accel_gate=True), ("eval_break_accel",)),
    "swept": (W2, ES_B, dict(swept_pool_targets=True), ("eval_swept",)),
    "session_only": (WC, ES_NB, dict(SMP, session_pools_mode="only"), ("session_pools_filter",)),
    "session_ext": (W2, ES_NB, dict(SMP, session_pools_mode="extended"), ("eval_late",)),
    "session_rank": (W2, ES_NB, dict(SMP, session_pools_mode="rank"), ("session_pools_rank",)),
    "event_horizon": (W2, dict(ES_B, gap_mode="ict"), dict(event_horizon_target=True), ("eval_event_horizon",)),
    "magnet": (W2, dict(ES_B, gap_mode="ict"), dict(nwog_magnet=True), ("eval_magnet",)),
    "overnight": (W2, ES_NB, dict(SMP, overnight_5m_fvgs=True), ("eval_on_fvg",)),
    "overnight_lock": (WC, dict(ES_NB, draw_lock="session"), dict(overnight_5m_fvgs=True), ("eval_on_fvg_lock",)),
    "htf_ob": (W2, ES_NB, dict(SMP, htf_ob_open=True, htf_ob_open_final=True, htf_targets=("1h", "4h", "D", "W")), ("eval_htf_ob",)),
    "htf_gap": (W2, ES_NB, dict(SMP, htf_gap_gate=True, fvg_quadrants=True, htf_far_edge=True, htf_targets=("15m", "1h", "4h", "D")), ("eval_htf_gap",)),
    "htf_gap_far": (W2, ES_NB, dict(SMP, htf_gap_gate=True, htf_gap_final="far_edge", fvg_quadrants=True, htf_far_edge=True, htf_targets=("15m", "1h", "4h", "D")), ("eval_htf_gap",)),
    "wfvg": (W2, ES_NB, dict(SMP, keep_traded_wfvg=True, weekly_bisi_ts_block=True, turtle_soup="2023"), ("eval_wfvg",)),
    "wick": (W2, ES_NB, dict(SMP, wick_tfs=("1h", "4h"), wick_long_only=True, min_obj_frac=0.2), ("eval_min_obj",)),
    "room": (W2, dict(ES_NB, min_draw_pts=5.0), dict(SMP, room_ref="htf_far"), ("eval_room_htf",)),
    "skip_near": (W2, dict(ES_NB, min_draw_pts=5.0), dict(SMP, t1_skip_near=True), ("t1_skip_near",)),
    "hrlr": (W2, ES_B, dict(hrlr_time_k=3.0, clear_path=True, lrlr_max=6), ("eval_hrlr_time", "eval_clear_path")),
    "beyond_pool": (W2, ES_NB, dict(SMP, beyond_pool_final=True), ("eval_beyond_pool",)),
    "confl": (W2, ES_NB, dict(SMP, confl_rank=True, htf_targets=("15m", "1h", "4h", "D")), ("eval_confl",)),
    "org": (W2, ES_NB, dict(SMP, org_draw="draw", org_ce_if_flow=True, org_breaker_stop=True), ("eval_org_flow", "eval_org_breaker")),
    "org_beyond": (W2, ES_NB, dict(SMP, org_draw="draw", org_beyond=True), ("eval_org_beyond",)),
    "nwog_ladder": (W2, dict(ES_B, gap_mode="ict"), dict(nwog_ladder=True, nwog_halfway=True), ("eval_nwog_ladder",)),
    "session_first": (W2, ES_NB, dict(SMP, session_pool_first=True, eq_pref="rank"), ("eval_session_first",)),
    "eq_leg": (W2, ES_NB, dict(SMP, draw_below_eq=True, eq_leg="rally", eq_beyond_imb=True), ("eq_leg_rally",)),
    "sd_close": (W2, ES_NB, dict(SMP, **SDX, sd_anchor="broken", sd_arm="close", sd_ref_roll=True, sd_cap_htf=True, sd_deep_conv=True, htf_targets=("15m", "1h", "4h", "D")), ("eval_sd_arm",)),
    "sd_tiers": (W2, ES_NB, dict(SMP, **SDX, sd_multi_tiers=("itl", "ltl"), sd_ref_roll=True, sd_cluster_ticks=2), ("eval_tiers",)),
    "sd_m15": (W2, ES_NB, dict(SMP, **SDX, sd_anchor="m15_leg", sd_htf_extreme=True, sd_htf_tol=2.0), ("eval_m15_leg",)),
    "sd_last_hour": (W2, ES_NB, dict(SMP, **SDX, sd_anchor="mss_leg", sd_last_hour_k=2.0), ("eval_last_hour",)),
    "sd_entry_low": (W2, ES_NB, dict(SMP, **SDX, sd_anchor="entry_low", proj_exit_ticks=1), ("eval_entry_low",)),
    "sd_inception": (W2, ES_NB, dict(SMP, **SDX, sd_anchor="fulcrum", sd_fulcrum_def="inception", sd_arm="close"), ("eval_inception",)),
    "sd_premium": (W2, ES_NB, dict(SMP, **SDX, sd_premium_consol=True, consol_day_rules="tag"), ("eval_sd_premium",)),
    "proj_org": (W2, ES_B, dict(proj_org_reprice=True, proj_org_kmax=4), ("eval_org_reprice",)),
    "proj_breaker": (W2, ES_NB, dict(SMP, proj_breaker=True, proj_breaker_k=(1.0, 2.0)), ("eval_proj_breaker_k",)),
}


@pytest.mark.skipif(not ES, reason="no ES data")
@pytest.mark.parametrize("case", sorted(ES_CASES))
def test_look_ahead_es(case):
    (a, b), base, kw, need = ES_CASES[case]
    df, meta = _es_tf(5, a, b)
    p = Params(**{**base, **kw})
    full, added = _la(df, 5, "ES", p, COLS, every=6, meta=meta, lag=2)
    _check_ran(case, full, added, need)


# --- forced-path books (hand-made days): the paths no ES window reaches, full run vs runs truncated at every bar of the book --------------------------------

def _hist_pdh(hi_last=102.0):
    return history(D0, hi=hi_last, lo=90.0, first=(108.0, 90.0))


def test_forced_t1_skip_near_engine():
    """Scenario C with the previous day's high 2 points over the entry: min_draw_pts 5 rejects the order (the nearest pool is the draw); t1_skip_near skips that pool and takes the next one."""
    off = _tp_run(hist=_hist_pdh(), min_draw_pts=5.0)
    assert off == []
    on = _forced(_fp(min_draw_pts=5.0, t1_skip_near=True), ("t1_skip_near",), hist=_hist_pdh())
    assert on[0].t1 == pytest.approx(108.25) and on[0].t2 is None
    base = _tp_run(hist=_hist_pdh())
    assert base and base[0].t1 < 108.0                                                      # without min_draw_pts the near pool is T1 (the built behaviour)


def test_forced_defended_and_confluence_tags():
    tr = _forced(_fp(defended_filter=True, defended_touches=1, defended_band_adr=0.2), ("defended",))
    assert "defended" in tr[0].lv_tags and tr[0].t2 is None
    tr = _forced(_fp(confl_rank=True), ("confl_final",))
    assert "confl_final" in tr[0].lv_tags
    tr = _forced(_fp(break_accel_gate=True), ("eval_break_accel",))
    assert "break_accel" in tr[0].lv_tags


def test_forced_minimum_objective_and_hrlr_time():
    tr = _forced(_fp(wick_tfs=("1h",), min_obj_frac=0.2, hrlr_time_k=50.0), ("eval_hrlr_time",))
    assert "min_obj" in tr[0].lv_tags and tr[0].entry < tr[0].t1                            # the long 1h wick CE is the protected minimum-objective rung
    tr = _forced(_fp(hrlr_time_k=0.001), ("eval_hrlr_time",))
    assert tr and "min_obj" not in tr[0].lv_tags and tr[0].t2 == pytest.approx(108.25)     # (no swing high lies between the entry and the targets of this book: the time factor has nothing to drop)


def test_defaults_do_not_change_a_run():
    ref = _tp_run()
    assert len(ref) == 1
    on = _tp_run(**{k: getattr(Params(), k) for k in KNOBS})
    assert [(t.entry, t.t1, t.t2, t.lv_tags) for t in on] == [(t.entry, t.t1, t.t2, t.lv_tags) for t in ref]
