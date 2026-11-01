"""Caption-gap pass, package targets_partials #1/4, part B: the study variants of the chunk and the no-look-ahead runs (full vs truncated runs, cut at entry AND exit times) that put every new switch on small date
windows - synthetic random-walk books (with a partner index, with and without event gaps), short ES windows (5m) with the Confluence object and the HTF table, and forced hand-made days for the paths no data window
reaches. Every behaviour switch has a run in which its code path EXECUTED (the sm2.HITS counters that tp1.py / the hooks bump), or an explicit entry in EXCEPTIONS with the reason. Tests that need local market data
(ES) skip cleanly when it is absent; no platform-specific paths. The generic one-variant-per-run look-ahead test (test_bias_htf_lookahead.py) covers every study variant of the chunk as well."""
from dataclasses import replace
from datetime import date

import numpy as np
import pandas as pd
import pytest

from mentorship import backtest as B, bias_htf as BH, sm2, strategy as S, study, tp1
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

from test_levels_detectors import ES
from test_caption_gap_ld1 import ENTRY, SYN
from test_caption_gap_sm2b import _check_ran, _es_tf, _la, ES_B, ES_NB, SYN_BASE, TAG_COLS
from test_caption_gap_sm6c import _gappy
from test_caption_gap_es2c import _cmp_trades
from test_review_fixes import A_LOCK, A_ROWS, BASE, D0, day, frame, history, run as rf_run
from test_caption_gap_tp1a import GAP_IDS, KNOBS, NEW_SWITCHES, POST, C_ROWS, _tp_run, _brow

NY = "America/New_York"
COLS = ENTRY + TAG_COLS + ["draw_px", "resist", "swing_grade"]


def test_every_gap_id_has_a_study_variant_that_builds():
    assert len(GAP_IDS) == 33
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
    assert D["N2-nfp-week-imprecise-targets"]["nfp_week_partial"] == 0.8 and D["N4-eve-of-high-impact_bnb"]["eve_mode"] == "bnb" and D["A22-array-reuse_tiebreak"]["array_reuse"] == "tiebreak"
    assert D["new-swing-projection-fulcrum"]["sd_anchor"] == "fulcrum_week" and D["L4-hrlr-news-exception"]["hrlr_news_only"]
    assert all(v in D for v in study._TP1_DECISIONS)


# --- synthetic books ---------------------------------------------------------------------------------------------------------------------------------------
# (a random-walk book has no overnight session, so the switches that read the htf table row - eq_first_rung, post_raid_cap, ob_location_cap, or_needs_bias, resist_def "htf", the lock - run in the ES windows)

LEVELS_ON = dict(old_high_ladder=True, void_ce_rung=True, vi_quarters=True, leg_mt_target=True, rb_fallback=True, rb_targets="ladder", level_polarity=True,
                 matrix_targets=("breaker", "mitigation", "rejection"), matrix_anchor="price", reh_merge_pts=2.0, eq_pref="rank", stubby_wick_ce=True, lrlr_zone=True, vi_arrays=True, vi_void_level=True,
                 vi_ob_levels=True, vi_keep_traded=True, vi_return_tag=True, daily_vi_targets=True, void_targets=True, leg_start_target=True)
GATES_ON = dict(dxy_rally_cap=True, bpr_gate_htf=True, breaker_first=True, breaker_overtake=True, resist_def="struct", skip_high_resistance="tag", hr_max_obstacles=2, swing_grade_tag=True,
                measuring_gap=True, measuring_target=True, measuring_qualify=True, measuring_need_pool=True, array_reuse="reuse", skip_exhausted=True, nfp_week_split=True, nfp_no_htf_targets=True,
                eve_mode="bnb", speed_bump_tfs=(5,), fvg_targets=True, htf_resist_cap=True, htf_resist_tfs=("5m", "15m", "1h"))
SYN_CASES = {
    # name: (seed, switches)
    "levels": (3, {**LEVELS_ON, "ob_entry": "both"}),
    "levels_b": (5, {**LEVELS_ON, "ob_entry": "both"}),
    "gates": (3, {**GATES_ON, "ob_entry": "both"}),
    "gates_b": (5, {**GATES_ON, "ob_entry": "both", "resist_filter": True, "resist_overlaps": 40}),
    "sd": (3, dict(sd_targets=True, sd_anchor="fulcrum_week", sd_need_array=True, ob_entry="post_mss", erl_range_swings=True, erl_range_update="swing")),
    "tail": (3, dict(nfp_flat_by=720, htf_no_time_stop=True, time_stop_min=10, eve_mode="tag", eve_risk_mult=0.5, ob_entry="post_mss")),
}


@pytest.mark.parametrize("case", sorted(SYN_CASES))
def test_look_ahead_synthetic(case):
    seed, kw = SYN_CASES[case]
    x, y = B.synthetic(start="2026-04-06", end="2026-05-08", tf=5, seed=seed)
    p = Params(**{**SYN, **SYN_BASE, **kw})
    full, added = _la(x, 5, "RW", p, COLS, every=3, partner=y)
    assert len(full) >= 1, full


@pytest.mark.parametrize("seed", [3, 5])
def test_look_ahead_gappy_synthetic(seed):
    """Books WITH event gaps (the continuous ES frame has none) and the partner index: the level and gate switches that can stand together on at once, cuts at entry AND exit times."""
    x, y = _gappy(seed)
    p = Params(**{**SYN, **SYN_BASE, **LEVELS_ON, **{k: v for k, v in GATES_ON.items() if k not in ("measuring_qualify",)}, "ob_entry": "post_mss"})
    full, added = _la(x, 5, "RW", p, COLS, every=2, partner=y)
    assert len(full) >= 1, full


# --- ES windows (5m): the full run must have EXECUTED the code paths named (the sm2.HITS counters tp1.py and the hooks bump) ---------------------------------

WC = ("2024-02-19", "2024-03-11")
W2, W3, WN, WE = ("2023-03-06", "2023-03-27"), ("2023-06-05", "2023-06-26"), ("2023-05-01", "2023-05-22"), ("2023-02-06", "2023-02-27")
SMP = dict(study.SM_POST)
TBL = dict(htf_bias="combo", draw_lock="off", htf_resist_cap=False, ob_entry="post_mss")
ES_CASES = {
    # name: (window, base, switches, the sm2.HITS counters the full run must have bumped: outcome counters where the window reaches them, "eval_*" (the switch's code was evaluated on real data) where the situation is rare)
    "nfp_week": (W2, ES_NB, dict(SMP, nfp_week_split=True, ladder_by_day=True), ("nfp_week_split",)),
    "eve_tag": (W2, ES_NB, dict(SMP, eve_mode="tag", eve_risk_mult=0.5), ("eve_tag",)),
    "eve_bnb": (WE, ES_NB, dict(SMP, eve_mode="bnb", eve_target_pts=5.0), ("eve_bnb",)),
    "high_res": (W2, ES_NB, dict(SMP, skip_high_resistance="tag", hr_max_obstacles=1), ("high_res",)),
    "reh": (W2, ES_NB, dict(SMP, reh_merge_pts=3.0, eq_pref="rank"), ("reh_merge",)),
    "resist": (W2, ES_NB, dict(SMP, resist_def="struct", resist_overlaps=2), ("resist_high",)),
    "post_raid": (W2, ES_B, dict(post_raid_cap=True), ("eval_post_raid",)),
    "eq_first": (W2, ES_B, dict(eq_first_rung=True), ("eval_eq_first",)),
    "polarity": (W2, ES_NB, dict(SMP, level_polarity=True), ("eval_polarity",)),
    "leg_mt": (W2, ES_NB, dict(SMP, leg_mt_target=True), ("eval_leg_mt",)),
    "void": (W2, ES_NB, dict(SMP, void_ce_rung=True, void_persist_days=3), ("eval_void_ce",)),
    "stubby": (W2, ES_NB, dict(SMP, stubby_wick_ce=True), ("stubby_wick_ce",)),
    "old_high": (W2, ES_NB, dict(SMP, old_high_ladder=True), ("old_high_ladder",)),
    "lrlr": (W2, ES_NB, dict(SMP, lrlr_zone=True), ("eval_lrlr",)),
    "ob_loc": (W2, ES_B, dict(ob_location_cap=True, ob_entry="pre_break"), ("eval_ob_location",)),
    "bpr": (W2, ES_NB, dict(SMP, bpr_gate_htf=True, htf_targets=("1h", "4h", "D")), ("bpr_gate_htf",)),
    "swing_grade": (W2, ES_NB, dict(SMP, swing_grade_tag=True), ("swing_grade",)),
    "or_bias": (W2, ES_B, dict(or_needs_bias=True, or_extra=True), ("or_needs_bias_block",)),
    "rb": (W2, ES_NB, dict(SMP, rb_fallback=True, rb_targets="ladder"), ("rb_fallback",)),
    "matrix_price": (W2, ES_NB, dict(SMP, matrix_anchor="price", matrix_targets=("breaker", "mitigation", "rejection")), ("matrix_price",)),
    "runner": (W2, dict(ES_B, htf_bias="react"), dict(htf_range_runner=True, matrix_tf_lower=True, draw_lock="session"), ("eval_runner",)),
    "hrlr": (WC, ES_B, dict(hrlr_news_only=True, lrlr_max=8, draw_lock="session"), ("eval_hrlr",)),
    "vi_ladder": (W2, ES_NB, dict(SMP, vi_arrays=True, vi_wick_overlap=False, daily_vi_targets=True, vi_void_level=True, vi_ob_levels=True, vi_keep_traded=True, vi_quarters=True), ("eval_vi_ladder", "eval_vi_quarters")),
    "speed": (W2, ES_NB, dict(SMP, speed_bump_tfs=(5, 15), htf_resist_cap=True, htf_resist_tfs=("5m", "15m", "1h"), htf_bias="react", fvg_targets=True), ("speed_bump_tfs",)),
    "measuring": (W2, ES_NB, dict(SMP, measuring_gap=True, measuring_target=True, measuring_qualify=True, measuring_need_pool=True), ("measuring_unqualified",)),
    "reuse": (W2, ES_NB, dict(SMP, array_reuse="reuse", skip_exhausted=True, htf_targets=("1h", "4h", "D"), htf_no_time_stop=True, time_stop_min=10), ("array_reuse",)),
    "fulcrum": (W3, ES_NB, dict(SMP, sd_targets=True, sd_anchor="fulcrum_week", sd_need_array=True), ()),
    "range": (W2, ES_NB, dict(SMP, erl_range_swings=True, erl_range_update="swing"), ("erl_range_update",)),
    "range_irl": (W2, ES_NB, dict(SMP, erl_range_swings=True, erl_range_update="swing", irl_entries=("fvg", "ob", "void")), ("irl_outside_range",)),
    "nfp_no_htf": (W2, ES_NB, dict(SMP, nfp_no_htf_targets=True, nfp_flat_by=720, htf_targets=("1h", "4h", "D"), vi_arrays=True, daily_vi_targets=True), ("eval_raw_post",)),     # (the drop itself needs a trade on a jobs day with a daily rung above: test_forced_jobs_day_drops_the_htf_array_rung)
    "breaker": (W2, ES_NB, dict(SMP, breaker_first=True, breaker_overtake=True), ("breaker_overtake",)),
    "nwog": (W2, dict(ES_B, gap_mode="ict", nwog_regime="tag"), dict(nwog_revert_targets=True), ("eval_nwog_revert",)),
}
_HITS = {}


@pytest.mark.skipif(not ES, reason="no ES data")
@pytest.mark.parametrize("case", sorted(ES_CASES))
def test_look_ahead_es(case):
    (a, b), base, kw, need = ES_CASES[case]
    df, meta = _es_tf(5, a, b)
    p = Params(**{**base, **kw})
    full, added = _la(df, 5, "ES", p, COLS, every=4, meta=meta, lag=2)
    _check_ran(case, full, added, need)
    _HITS.setdefault(case, set()).update(added)


# --- forced-path books (hand-made days): the paths no ES window reaches, full run vs runs truncated at every bar ----------------------------------------------------

def _added(h0):
    return {k: v - h0.get(k, 0) for k, v in sm2.HITS.items() if v - h0.get(k, 0)}


def _forced(p, need, rows=None, d=D0, hist=None, lock=None, spike=False, **kw):
    """A full run of a hand-made day vs runs on the data truncated at EVERY bar of the book; the full run must have executed the code paths in `need`."""
    rows = rows or C_ROWS
    lock = lock or {}
    df = day(rows, d=d, spike=spike)
    hist = hist if hist is not None else history(d)
    h0 = dict(sm2.HITS)
    full, *_ = rf_run(df, hist, p, lock, **kw)
    added = _added(h0)
    assert len(full) >= 1, "the book made no trade"
    missing = [h for h in need if not added.get(h)]
    assert not missing, (missing, sorted(added))
    k0 = int(np.flatnonzero(df.index.hour * 60 + df.index.minute == 570)[0])
    for j in range(k0, min(len(df), k0 + len(rows) + 3)):
        part, *_ = rf_run(df.iloc[:j + 1], hist, p, lock, **kw)
        _cmp_trades(full, part, df.index[j])
    return full


def _fp(**kw):
    return Params(**{**BASE, **POST, **kw})


def test_forced_eq_first_and_post_raid_rows():
    row = _brow(pd20_hi=120.0, pd20_lo=90.0, first_clue=-1, tug=0, raid_px=104.0, raid_eq=102.0)
    tr = _forced(_fp(eq_first_rung=True, post_raid_cap=True, htf_bias="off"), ("eq_first", "eval_post_raid"), bias=row)
    assert "eq_first" in tr[0].lv_tags
    row = _brow(pd20_hi=120.0, pd20_lo=90.0, first_clue=-1, tug=0, raid_px=104.0, raid_eq=103.0)
    tr = _forced(_fp(post_raid_cap=True, htf_bias="off"), ("post_raid_cap",), bias=row, rows=[(a, b, c, d) for a, b, c, d in C_ROWS])
    assert "post_raid_cap" in tr[0].lv_tags and tr[0].t2 is None or tr[0].t1 < 104.0


def test_forced_dxy_and_ob_location():
    tr = _forced(_fp(dxy_rally_cap=True), ("dxy_rally_cap",), intermarket={"dxy": 1})
    assert tr[0].t2 is None and "dxy_cap" in tr[0].lv_tags
    # scenario A (the OB-before-break entry, entry ~100) in the premium of a 90-101 range: the first rung only
    row = _brow(pd20_hi=101.0, pd20_lo=90.0, draw=0)
    off = _forced(_fp(htf_bias="off", ob_entry="pre_break", draw_lock="off"), (), rows=A_ROWS, spike=True, bias=row)
    on = _forced(_fp(ob_location_cap=True, htf_bias="off", ob_entry="pre_break", draw_lock="off"), ("ob_location_cap",), rows=A_ROWS, spike=True, bias=row)
    assert "ob_loc_cap" in on[0].lv_tags and "ob" in on[0].entry_kind and on[0].t2 is None and off[0].t2 is not None


def _hist_low(lo=103.7, hi=110.0, d=D0):
    """History whose last session lives at 104-110: its low (103.7) lies ABOVE the next morning's prices."""
    h = history(d)
    last = h[-1].index[0].date()
    rows = [(105.0, hi, lo, 105.0)] + [(105.0, 105.1, 104.9, 105.0)] * 77
    return h[:-1] + [frame(last, rows, 5, "09:30")]


def test_forced_polarity_and_leg_mt():
    tr = _forced(_fp(level_polarity=True), ("polarity",), hist=_hist_low())
    assert "polarity" in tr[0].lv_tags
    tr = _forced(_fp(leg_mt_target=True), ("eval_leg_mt",))            # (the MT of scenario C's down leg lies under its leg high: price has already traded to it - the outcome is the unit test's)


def test_forced_resist_eve_nfp_week():
    tr = _forced(_fp(resist_def="htf", htf_bias="off"), ("resist_high",), bias=_brow(wk_bias=-1))
    assert tr[0].resist == "high"
    tr = _forced(_fp(resist_def="htf", htf_bias="off"), (), bias=_brow(wk_bias=1))
    assert tr[0].resist == "low"
    tr = _forced(_fp(eve_mode="bnb"), ("eve_bnb",), d=date(2023, 2, 13))
    assert tr[0].t2 is None and "pre_cpi" in tr[0].lv_tags
    tr = _forced(_fp(nfp_week_split=True), ("nfp_week_split",), d=date(2023, 5, 31))
    assert "nfp_week" in tr[0].lv_tags


def test_forced_jobs_day_flat_by_and_htf_filter():
    tr = _forced(_fp(nfp_flat_by=600, nfp_no_htf_targets=True), (), d=date(2023, 6, 2))
    assert [e[3] for e in tr[0].exits] == ["am_exit"]


def test_forced_jobs_day_drops_the_htf_array_rung():
    """N1-nfp-no-htf-hold on a hand-made jobs day with a daily FVG above the entry (a stub Confluence): the rung is dropped (nfp_no_htf_drop executed),
    the same book on an ordinary day keeps the rung (and trades differently); full run vs runs truncated at every bar."""
    from test_targets_partials import conf
    cf = conf([(-1, 103.0, 102.0, np.inf, 0, "D")], tfs=("D",), t0=pd.Timestamp("2023-05-31 02:00", tz="America/New_York"))
    kw = dict(htf_targets=("D",), vi_arrays=True, htf_bias="off")
    on = _forced(_fp(nfp_no_htf_targets=True, **kw), ("nfp_no_htf_drop",), d=date(2023, 6, 2), conf=cf)
    assert "nfp_no_htf" in on[0].lv_tags
    ordinary = rf_run(day(C_ROWS, d=date(2023, 6, 1)), history(date(2023, 6, 1)), _fp(nfp_no_htf_targets=True, **kw), {}, conf=cf)[0]
    assert all("nfp_no_htf" not in t.lv_tags for t in ordinary)                    # (an ordinary day: the rung stays, so the 102-103 FVG caps the run and the book makes no trade)
