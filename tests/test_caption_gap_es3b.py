"""Caption-gap pass, package entries_stops_sizing #3/3, part B: the study variants of the chunk and the no-look-ahead runs (full vs truncated runs, cut at entry AND exit times) that put every new switch on small date
windows - synthetic random-walk books (with a partner index, with and without event gaps), short ES windows (5m) with the Confluence object and the HTF table, and forced hand-made days for the paths no data window
reaches. Every behaviour switch has a run in which its code path EXECUTED (the sm2.HITS counters that es3.py / the hooks bump), or an explicit entry in EXCEPTIONS with the reason. Tests that need local market data
(ES) skip cleanly when it is absent; no platform-specific paths. The generic one-variant-per-run look-ahead test (test_bias_htf_lookahead.py) covers every study variant of the chunk as well."""
from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from mentorship import backtest as B, es3, sm2, strategy as S, study
from mentorship.strategy import Params

from test_levels_detectors import ES
from test_caption_gap_ld1 import ENTRY, SYN
from test_caption_gap_sm2b import _check_ran, _es_tf, _la, ES_B, ES_NB, SYN_BASE, TAG_COLS
from test_caption_gap_sm6c import _gappy
from test_caption_gap_sm1a import StubConf
from test_caption_gap_es2c import _cmp_trades
from test_review_fixes import A_LOCK, A_ROWS, BASE, D0, day, history, run as rf_run
from test_caption_gap_es3a import GAP_IDS, KNOBS, NEW_SWITCHES, NY

COLS = ENTRY + TAG_COLS + ["draw_px"]
ALL_STUDY = {**study._ES3_DECISIONS}


def test_every_gap_id_has_a_study_variant_that_builds():
    assert len(GAP_IDS) == 34
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
    assert D["E8-new-trader-drill"]["stop_fixed_pts"] == 5.0 and D["E6-bpr-75-stop_lower"]["bpr75_ref"] == "lower" and D["E6-nwog-stop_all"]["stop_gap_edge"] == "all"
    names = list(D)
    assert names.index("E12-repeat-dig-smaller-add") > names.index("E12-low-end-add-conditions")                        # after the earlier chunk's variants; all reached by the generic look-ahead test
    assert not [v for v in study._ES3_DECISIONS if v not in D]
    assert [round(q.risk_pct, 3) for q in study.risk_grid()] == [0.01, 0.012, 0.015, 0.02]


# --- synthetic books ---------------------------------------------------------------------------------------------------------------------

ADDS_ON = dict(add_dig_mult=0.67, add_on="retest", add_wick_ce=True, add_void=True, add_gate_wick=True, add_reclaimed_ob=True, vi_ladder=True, add_ladder="631", add_momentum=True, add_mom_r=0.1,
               ob_adds=True, ifvg_entries=True, ifvg_mohawk_add=True)
SIZE_ON = dict(alloc_frac=0.5, class_risk={"scalp": 0.005, "day": 0.01}, htf_near_risk_pct=0.03, max_lev=3.0, deep_run_mult=0.5, deep_run_weeks=2, freq_ref=1.0, daily_loss_pct=0.03, trader_mode="new", grad_block=2)
STOPS_ON = dict(stop_old_low_body=True, stop_gap_edge="own", stop_htf_anchor=True, ob_stop_kind="body", ob_anchor="last_open", mit_entries=True, prop_entry=True, prop_stop="mt", trail_wick_ce=True)
SYN_CASES = {
    # name: (seed, switches)
    "adds": (3, {**ADDS_ON, "ob_entry": "both"}),
    "adds_b": (4, {**ADDS_ON, "ob_entry": "post_mss"}),
    "size": (3, {**SIZE_ON, "ob_entry": "both"}),
    "size_b": (3, dict(alloc_frac=0.5, htf_near_risk_pct=0.03, max_lev=3.0, deep_run_mult=0.5, freq_ref=1.0, daily_loss_pct=0.03, ob_entry="both")),
    "stops": (4, {**STOPS_ON, "ob_entry": "both"}),
    "stop_wick": (3, dict(stop_mode="wick_ce", ob_entry="post_mss", trail_wick_ce=True)),
    "stop_m2": (3, dict(stop_mode="m2_auto", fvg_pick="2022", ob_entry="post_mss", max_risk_pts=100.0)),
    "stop_three": (3, dict(stop_mode="three_pd", ob_entry="post_mss")),
    "stop_next": (3, dict(stop_mode="next_pd", ob_entry="post_mss", trader_mode="new", stop_widen_new=True, new_max_risk_pts=100.0)),
    "stop_bpr": (3, dict(stop_mode="bpr75", bpr75_ref="lower", ob_entry="post_mss")),
    "drill": (3, dict(stop_mode="fixed", stop_fixed_pts=5.0, t1_fixed_pts=5.0, t1_fixed_all=True, fixed_units=1, entry="edge_1tick", adds=(), ob_entry="post_mss")),
    "reentry": (3, dict(reentry_half=True, reentry_stop="ob_low", ob_entry="post_mss", t1_fixed_r=1.0, t1_fixed_all=True)),
}


@pytest.mark.parametrize("case", sorted(SYN_CASES))
def test_look_ahead_synthetic(case):
    seed, kw = SYN_CASES[case]
    x, y = B.synthetic(start="2026-04-06", end="2026-05-08", tf=5, seed=seed)
    p = Params(**{**SYN, **SYN_BASE, **kw})
    full, added = _la(x, 5, "RW", p, COLS, every=3, partner=y)
    assert len(full) >= 1, full


@pytest.mark.parametrize("seed", [3, 4])
def test_look_ahead_gappy_synthetic(seed):
    """Books WITH event gaps (the continuous ES frame has none) and the partner index: the switches of the chunk that can stand together on at once, cuts at entry AND exit times."""
    x, y = _gappy(seed)
    size = {k: v for k, v in SIZE_ON.items() if k not in ("trader_mode", "grad_block")}                              # (trader_mode fixes the size at 1 contract: the other sizing rules would never bite)
    p = Params(**{**SYN, **SYN_BASE, **ADDS_ON, **size, "ob_entry": "post_mss"})
    full, added = _la(x, 5, "RW", p, COLS, every=2, partner=y)
    assert len(full) >= 1, full


# --- ES windows (5m): the full run must have EXECUTED the code paths named (the sm2.HITS counters es3.py and the hooks bump) ---------------------------------

W0, W1, W2, W3, W4, W5, W13, WD = (("2022-03-07", "2022-03-28"), ("2022-08-01", "2022-08-22"), ("2023-03-06", "2023-03-27"), ("2023-06-05", "2023-06-26"), ("2023-10-02", "2023-10-23"),
                                    ("2024-02-19", "2024-03-11"), ("2022-10-03", "2022-10-24"), ("2023-11-20", "2024-01-05"))
SMP = dict(study.SM_POST)
OBPRE = dict(ob_entry="pre_break")
ES_CASES = {
    # name: (window, base, switches, the sm2.HITS counters the full run must have bumped)
    "dig": (W0, ES_NB, dict(SMP, add_dig_mult=0.67, add_on="retest"), ("add_dig_mult",)),
    "wick_add": (W0, ES_NB, dict(SMP, add_wick_ce=True), ("add_wick_ce",)),
    "vi_ladder": (W4, ES_NB, dict(SMP, vi_ladder=True, add_ladder="631"), ("vi_ladder_vi",)),
    "vi_ladder_exit": (W13, ES_NB, dict(SMP, vi_ladder=True, vi_ladder_exit=True, add_ladder="631"), ("exit_ob_mt_inval",)),
    "gate": (W4, ES_NB, dict(SMP, add_gate_wick=True), ("add_gate_wick",)),
    "mohawk": (W0, ES_NB, dict(SMP, ifvg_entries=True, ifvg_mohawk_add=True), ("ifvg_mohawk_add",)),
    "reclaimed": (W5, ES_NB, dict(SMP, add_reclaimed_ob=True), ("add_reclaimed_ob",)),
    "alloc": (W0, ES_NB, dict(SMP, alloc_frac=0.3), ("alloc_frac",)),
    "near": (W0, ES_NB, dict(SMP, htf_near_risk_pct=0.05), ("htf_near",)),
    "class": (W0, ES_NB, dict(SMP, class_risk={"scalp": 0.005, "day": 0.012}, t1_fixed_r=1.0, t1_fixed_all=True), ("class_risk",)),
    "lev": (W0, ES_NB, dict(SMP, max_lev=3.0, account_equity=20000.0), ("max_lev",)),
    "drill": (W0, ES_NB, dict(SMP, stop_mode="fixed", stop_fixed_pts=5.0, t1_fixed_pts=5.0, t1_fixed_all=True, fixed_units=1, entry="edge_1tick", adds=()), ("stop_fixed",)),
    "grad": (W0, ES_NB, dict(SMP, trader_mode="new", grad_block=3), ("trader_mode_new",)),
    "deep": (WD, ES_NB, dict(SMP, deep_run_mult=0.5, deep_run_weeks=2), ("deep_run",)),
    "freq": (W0, ES_NB, dict(SMP, freq_ref=1.0), ("freq_ref",)),
    "wick_stop": (W0, ES_NB, dict(SMP, stop_mode="wick_ce", trail_wick_ce=True), ("stop_wick_ce", "trail_wick_ce")),
    "m2": (W0, ES_NB, dict(SMP, stop_mode="m2_auto", fvg_pick="2022"), ("m2_auto_conf", "m2_auto_plain")),
    "old_low": (W0, ES_NB, dict(SMP, stop_old_low_body=True), ("stop_old_low_body",)),
    "gap_own": (W2, ES_NB, dict(SMP, stop_gap_edge="own", gap_mode="ict"), ("stop_gap_edge",)),
    "gap_all": (W2, ES_NB, dict(SMP, stop_gap_edge="all", gap_mode="ict"), ("stop_gap_edge",)),
    "three": (W0, ES_NB, dict(SMP, stop_mode="three_pd"), ("stop_three_pd",)),
    "next": (W0, ES_NB, dict(SMP, stop_mode="next_pd"), ("stop_next_pd",)),
    "bpr": (W0, ES_NB, dict(SMP, stop_mode="bpr75"), ("stop_bpr75",)),
    "bpr_lower": (W0, ES_NB, dict(SMP, stop_mode="bpr75", bpr75_ref="lower"), ("stop_bpr75",)),
    "wide": (W0, ES_NB, dict(SMP, trader_mode="new", stop_widen_new=True, reentry_half=True), ("stop_widen_new",)),
    "htf_anchor": (W0, ES_NB, dict(SMP, stop_htf_anchor=True), ("stop_htf_anchor",)),
    "ob_low": (W0, ES_NB, dict(SMP, reentry_half=True, reentry_stop="ob_low"), ("reentry_ob_low",)),
    "mit": (W0, ES_NB, dict(SMP, mit_entries=True), ("mit_entries",)),
    "prop": (W4, ES_NB, dict(SMP, prop_entry=True, prop_stop="mt"), ("prop_stop_mt",)),
    "daily": (W1, ES_NB, dict(SMP, daily_loss_pct=0.015), ("daily_loss_block",)),
    "probe": (W1, dict(ES_NB, htf_bias="react"), dict(SMP, probe_mult=0.25, probe_t=600), ("probe", "exit_probe_cut")),
    "momentum": (W0, ES_NB, dict(OBPRE, add_momentum=True, add_mom_r=0.25, ob_adds=True), ("add_momentum",)),
    "ob_body": (W0, ES_NB, dict(OBPRE, ob_stop_kind="body"), ("ob_stop_body",)),
    "ob_wick": (W0, ES_NB, dict(OBPRE, ob_stop_kind="wick"), ("ob_stop_wick",)),
    "ob_anchor": (W0, ES_NB, dict(OBPRE, ob_anchor="last_open", ob_adds=True), ("ob_anchor_last_open",)),
}
_RUN_KW = {"es_" + c: (kw, need) for c, (w, b, kw, need) in ES_CASES.items()}
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


# --- forced-path books (hand-made days): the paths no ES window reaches ------------------------------------------------------------------------------

def _added(h0):
    return {k: v - h0.get(k, 0) for k, v in sm2.HITS.items() if v - h0.get(k, 0)}


def _forced(rows, p, need, conf=None, lock=A_LOCK, mon=None):
    """A full run of a hand-made day vs runs on the data truncated at EVERY bar of the book; the full run must have executed the code paths in `need`."""
    df = day(rows, spike=True)
    hist = history(D0)
    kw = dict(conf=conf) if conf is not None else {}
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
    return Params(**{**BASE, "adds": (0.5, 0.33, 0.17), "ob_adds": False, "draw_lock_partials": False, "min_risk_pts": 0.5, "risk_pct": 0.003, **kw})


VOID_ROWS = A_ROWS[:5] + [(100.3, 102.0, 100.2, 101.9), (102.6, 103.5, 102.4, 103.4), (103.4, 103.8, 103.0, 103.6), (103.6, 108.5, 103.5, 108.4)]
VI_ROWS = A_ROWS[:5] + [(100.3, 100.9, 100.2, 100.8), (101.2, 101.9, 100.9, 101.8), (101.8, 102.0, 100.9, 101.7), (101.7, 101.8, 101.3, 101.5), (101.5, 108.5, 101.4, 108.4)]


def test_look_ahead_forced_add_void():
    """A 1m liquidity void (low 102.4 over the previous high 102.0) after the fill, overlapping the 5m FVG CE band (101.5-103.0, CE 102.25) and above the OB MT: the add at the void bottom + 1 tick."""
    conf = StubConf(arrays={1: [(103.0, 101.5, "5m", 0, 0.0)]})
    tr = _forced(VOID_ROWS, _fp(add_void=True), ("add_void",), conf=conf)
    assert tr[0].adds == [] or len(tr[0].adds) <= 1


def test_look_ahead_forced_vi_ladder_wick_rung():
    """026: rung 1 = the VI formed after the fill (101.2), rung 2 = the lower-wick CE of the next candle (101.7 - 100.9 -> 101.3), both only beyond the entry zone."""
    tr = _forced(VI_ROWS, _fp(vi_ladder=True, add_ladder="631"), ("vi_ladder_vi", "vi_ladder_wick"))
    assert len(tr[0].adds) >= 1


def test_look_ahead_forced_daily_loss_flatten(monkeypatch):
    """The open position is flattened at the close that takes the day's realized + open P&L to the limit (a tiny limit; the order gate is waived so the position exists at all)."""
    monkeypatch.setattr(es3, "dl_blocks_order", lambda *a, **k: False)
    rows = list(__import__("test_caption_gap_es1a").C_ROWS)
    rows[6] = (100.5, 100.6, 99.9, 100.2)                                             # bar 6 closes under the 100.4 fill by 0.2 -> a marked loss of ~184
    df = day(rows)
    hist = history(D0)
    p = Params(**{**BASE, **__import__("test_caption_gap_es1a").POST, "daily_loss_pct": 0.0015})
    h0 = dict(sm2.HITS)
    full, *_ = rf_run(df, hist, p, {})
    assert _added(h0).get("daily_loss_flat") and full[0].exits[0][3] == "daily_loss" and full[0].exits[0][1] == pytest.approx(100.2)
    k0 = int(np.flatnonzero(df.index.hour * 60 + df.index.minute == 570)[0])
    for j in range(k0, k0 + len(rows) + 3):
        part, *_ = rf_run(df.iloc[:j + 1], hist, p, {})
        _cmp_trades(full, part, df.index[j])


# --- E11-portfolio-exposure-cap: the filter only uses what is known at each trade's entry --------------------------------------------------------------

def test_exposure_filter_is_causal():
    d = pd.Timestamp("2026-06-23").date()
    t0 = pd.Timestamp("2026-06-23 09:30", tz=NY)
    rng = np.random.default_rng(3)
    rows = []
    for k in range(12):
        en = t0 + pd.Timedelta(minutes=int(rng.integers(0, 300)))
        rows.append([d, ("AM", "PM", "LUNCH")[k % 3], "x%d" % k, "ES", None, en, en + pd.Timedelta(minutes=int(rng.integers(5, 120))), 0.012, 0.012])
    book = pd.DataFrame(rows, columns=["date", "session", "setup", "symbol", "smt", "entry_time", "exit_time", "entry_risk_pct", "peak_risk_pct"])
    full = es3.exposure_filter(book, 0.02)
    assert len(full) < len(book)
    for cut in sorted(book.entry_time)[3:]:
        part = es3.exposure_filter(book[book.entry_time <= cut], 0.02)
        assert set(part.setup) == set(full[full.entry_time <= cut].setup), cut                # the decisions up to a time never depend on later trades


# --- every switch of the chunk has an executed-path case ----------------------------------------------------------------------------------------------

SWITCH_HIT = {
    "add_dig_mult": "add_dig_mult", "add_momentum": "add_momentum", "add_wick_ce": "add_wick_ce", "vi_ladder": "vi_ladder_vi", "vi_ladder_exit": "exit_ob_mt_inval", "add_gate_wick": "add_gate_wick",
    "ifvg_mohawk_add": "ifvg_mohawk_add", "add_reclaimed_ob": "add_reclaimed_ob", "daily_loss_pct": "daily_loss_block", "alloc_frac": "alloc_frac", "htf_near_risk_pct": "htf_near", "class_risk": "class_risk",
    "max_lev": "max_lev", "stop_fixed_pts": "stop_fixed", "fixed_units": "stop_fixed", "t1_fixed_r": "class_risk", "trader_mode": "trader_mode_new", "deep_run_mult": "deep_run", "freq_ref": "freq_ref",
    "probe_mult": "probe", "trail_wick_ce": "trail_wick_ce", "stop_old_low_body": "stop_old_low_body", "stop_gap_edge": "stop_gap_edge", "bpr75_ref": "stop_bpr75", "stop_widen_new": "stop_widen_new", "stop_htf_anchor": "stop_htf_anchor",
    "ob_stop_kind": "ob_stop_body", "ob_anchor": "ob_anchor_last_open", "mit_entries": "mit_entries", "prop_stop": "prop_stop_mt", "stop_mode": "stop_three_pd", "reentry_stop": "reentry_ob_low",
}
# switches whose outcome path no ES window reaches: a forced hand-made book above (a full run vs runs truncated at every bar) or a causal argument
EXCEPTIONS = {
    "add_void": "no 1m void inside a 5m FVG CE band above the entry OB MT in 14 ES windows: test_look_ahead_forced_add_void (counter add_void)",
    "max_exposure_pct": "backtest.combine post-processing of the finished books (no engine path): test_exposure_cap_combine + test_exposure_filter_is_causal",
}
HIT_FORCED = {"daily_loss_flat": "test_look_ahead_forced_daily_loss_flatten", "vi_ladder_wick": "test_look_ahead_forced_vi_ladder_wick_rung"}


def _on(kw, switch):
    d = Params.__dataclass_fields__[switch].default
    return switch in kw and kw[switch] != d and kw[switch] != {}


def test_every_switch_of_the_chunk_has_an_executed_path_case():
    """Every behaviour switch is ON in a no-look-ahead run that must have EXECUTED its code path (its counter is in that run's required hits), or it is in EXCEPTIONS with the reason."""
    missing = []
    for s_ in NEW_SWITCHES:
        if s_ in EXCEPTIONS:
            continue
        if s_ not in SWITCH_HIT or not [c for c, (kw, need) in _RUN_KW.items() if _on(kw, s_) and SWITCH_HIT[s_] in need]:
            missing.append(s_)
    assert not missing, missing
    assert set(EXCEPTIONS) <= set(NEW_SWITCHES)
