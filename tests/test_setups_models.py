"""Package setups_models (rule_coverage.md section 3, 75 items): unit tests for the new detectors
and helpers, and no-look-ahead runs (full vs truncated) covering every new switch. The ES / NQ
tests skip when the databento data is missing."""
import warnings
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from mentorship import backtest as B, levels as L, setups as SM, strategy as S, study
from mentorship.strategy import Params

ES = Path("data/mentorship/ES_5min_db.csv").exists() and Path("data/mentorship/NQ_5min_db.csv").exists()
SYN = dict(es_pt=0.09, use_bias=False, min_draw_pts=0, leg_pd=0)
POST = dict(ob_entry="post_mss", draw_lock="off")
FUT = dict(es_pt=1.0, lot=1, max_notional=1e12, cost_per_share=0.1)
COLS = ["entry_time", "entry", "stop", "t1", "shares", "entry_kind", "lv_tags", "setup", "swept"]
NEW = ("mss_eq_wait", "mss_on_side", "disp_mult", "disp_body_mult", "disp_follow", "disp_through_pts",
       "disp_fvg_after_break", "mss_max_bars", "mss_disp", "mss_ref_sibi", "mss_ref_tf", "am_htf_draw",
       "am_discount_array", "mm_context", "daily_vi_targets", "speed_check", "speed_bars", "body_low_cancel",
       "no_breakout_fvg", "add_leg_cut", "m2_target", "three_drives", "unicorn_open_min", "unicorn_open_only",
       "unicorn_only", "unicorn_entry", "unicorn_rules", "add_on_vi", "adds_in_breaker", "breaker_retest_add",
       "adv_breaker", "ts_breaker_pyramid", "cc_swings", "cc_fail_pts", "last_hour_own_slot",
       "pm_last_hour_model", "pm_ep01", "last_hour_setup", "lh_unengaged", "lh_htf_done_skip", "pm_4h_ce",
       "lh_start_by", "moc_run", "moc_cap_pts", "moc_pool_exit", "pm_reversal", "pm_lunch_target",
       "pm_lunch_org", "pm_judas_array", "ifvg_entry", "ifvg_stop_pts", "ifvg_min_risk_pts", "ifvg_depth",
       "ifvg_061", "ifvg_hold", "ifvg_after_htf", "ir_entries", "cisd_ob_entries", "wick_ce_entries",
       "ts_need_flow", "ts_adds_breakers", "ts_max_run", "ote", "leg_pd_strict", "ote_leg_stop", "ote_stack_tag",
       "smt_entry", "smt_turtle", "smt_exit", "smt_entry_syms", "sick_sister", "smt_pick", "smt_min_gap_pts",
       "smt_need_array", "smt_rel_eq", "smt_windows", "smt_pre", "news_profile", "news_ce_target",
       "news_no_unicorn", "require_judas", "judas_window", "po3_runner", "po3_require_bias", "po3_inclusive",
       "po3_hold", "profile_tags", "nfp_sd", "nest_tfs", "mmxm_ctx", "mmxm_breaker", "clean_leg", "clean_body",
       "reclaimed_ob", "reaper", "reaper_confirm", "candle_draw_bias", "entry_arrays", "md_big_candle",
       "md_second", "md_ladder", "md_need_news", "md_eth", "md_blocked")


# --- unit tests: detectors ---------------------------------------------------------------------

def test_ote_band_and_wick_ce():
    lo, hi, sweet = L.ote_band(100.0, 110.0)
    assert (round(lo, 3), round(hi, 3), round(sweet, 3)) == (102.1, 103.8, 102.95)
    o, l_, c = np.array([10.0]), np.array([8.0]), np.array([11.0])
    assert L.wick_ce(o, l_, c, 0) == 9.0                          # body low 10, low 8


def test_three_drives_needs_failing_lower_lows():
    P = L.Pivot
    lows = [P(2, 100.0, 3), P(6, 96.0, 7)]
    assert L.three_drives(lows, 94.0, 10, 10)                       # 4 then 2: failing
    assert not L.three_drives(lows, 90.0, 10, 10)                   # 4 then 6: extending
    assert not L.three_drives(lows, 97.0, 10, 10)                   # not a lower low
    assert not L.three_drives([P(6, 96.0, 11)], 94.0, 10, 10)       # second drive not known yet


def test_leg_sibi_and_ifvg_passes():
    h = np.array([10, 9.0, 7.0, 6.5, 6.0]); l_ = np.array([9.5, 8.0, 6.0, 5.5, 5.0])
    o = c = (h + l_) / 2
    z = L.leg_sibi(h, l_, o, c, 0, 4)
    assert z is not None and z.kind == "bear" and z.i == 3 and (z.top, z.bottom) == (8.0, 6.5)   # the last SIBI
    hh = np.array([5.0, 5.0, 6.0, 7.5, 5.0])
    assert L.ifvg_passes(hh, hh - 1, 7.0, 6.5, 0, 4) == "both"
    assert L.ifvg_passes(np.array([5.0, 6.6, 5, 5]), np.zeros(4), 7.0, 6.5, 0, 3) == "partial"
    assert L.ifvg_passes(np.array([5.0, 5.0, 5, 5]), np.zeros(4), 7.0, 6.5, 0, 3) == "none"


def test_reaper_and_reclaimed_ob():
    # leg L1 (bar 0, low 100) -> H (bar 6, high 110) with a BISI low in the leg (bars 1-3), then a
    # decline that closes below that gap on the way to the lower low (bar 9)
    h = np.array([101, 102, 103, 105, 107, 109, 110, 108, 104, 100.0])
    l_ = np.array([100, 101, 102.5, 104, 106, 108, 109, 103, 99, 98.0])
    o = np.array([100.5, 101, 102.6, 104, 106, 108, 109.5, 108, 104, 100.0])
    c = np.array([101, 102, 103, 105, 107, 109, 109.6, 103.5, 99.5, 99.0])
    z = L.reaper(o, h, l_, c, 0, 6, 9)
    # gaps (101-102.5), (102-104), (103-106) have their CE in the leg's discount half (<= 105), (105-108)
    # does not; all were closed through on the way down -> the newest discount one
    assert z is not None and (z.bottom, z.top) == (103.0, 106.0) and z.mid <= 105
    assert L.reaper(o, h, l_, c, 0, 6, 6) is None                      # nothing closed through it yet
    # down candle at bar 7 followed by an up close at bar 8? (no: bar 8 closes down) -> not an OB
    o2 = np.array([105, 104, 103.5, 101, 101.5, 103]); c2 = np.array([104, 103, 104, 100, 103, 106])
    h2 = np.maximum(o2, c2) + 0.2; l2 = np.minimum(o2, c2) - 0.2
    rs = L.reclaimed_obs(o2, h2, l2, c2, 0, 3, 5)
    assert [r.src for r in rs] == [1] and rs[0].i == 5               # bar 1 (bounce at 2), reclaimed at 5


def test_tf_pivots_known_only_when_the_bucket_is_complete():
    idx = pd.date_range("2026-06-23 09:30", periods=30, freq="1min", tz="America/New_York")
    h = np.array([1.0] * 5 + [3.0] * 5 + [2.0] * 5 + [1.0] * 5 + [0.5] * 10)
    hs, _ = L.tf_pivots(idx, h, h - 0.5, 1, 5, 1)
    assert len(hs) == 1 and hs[0].price == 3.0 and hs[0].i == 5 and hs[0].known == 14   # 09:40-09:44 confirms
    hs2, _ = L.tf_pivots(idx[:14], h[:14], h[:14] - 0.5, 1, 5, 1)
    assert hs2 == []                                                 # the confirming bucket is incomplete


def test_failure_swing():
    P = L.Pivot
    highs, lows = [P(3, 105.0, 4)], [P(1, 99.0, 2), P(5, 101.0, 6)]
    r = L.failure_swing(highs, lows, 100.0, 2.0, 8)
    assert r is not None and r[0].price == 101.0 and r[1].price == 105.0
    assert L.failure_swing(highs, lows, 100.0, 0.5, 8) is None       # too far above the level
    assert L.failure_swing(highs, lows, 101.5, 2.0, 8) is None       # it reached the level


# --- unit tests: engine helpers ------------------------------------------------------------------

class _Sd:
    def __init__(self, o, h, l_):
        self.o, self.h, self.l = np.array(o, float), np.array(h, float), np.array(l_, float)


def test_fill_at_order_types():
    sd = _Sd([10, 10.5], [11, 12], [9, 10.2])
    assert S._fill_at(sd, dict(entry=10.0, market=True), 1) == 10.5
    assert S._fill_at(sd, dict(entry=11.5, stop_entry=True), 1) == 11.5
    assert S._fill_at(sd, dict(entry=12.5, stop_entry=True), 1) is None
    assert S._fill_at(sd, dict(entry=10.3), 1) == 10.3
    assert S._fill_at(sd, dict(entry=10.3, through=0.25), 1) is None   # 10.2 > 10.3 - 0.25
    assert S._fill_at(sd, dict(entry=10.5, through=0.25), 1) == 10.5


def test_params_validation_for_new_switches():
    for kw in (dict(mss_on_side="x"), dict(ote="band"), dict(fvg_pick="best"), dict(stop_mode="wide"),
               dict(entry_arrays=("fib",)), dict(nest_tfs=("2h",)), dict(cc_swings="all"), dict(smt_pick="x"),
               dict(mss_ref="big")):
        with pytest.raises(ValueError):
            Params(**kw)
    p = Params(mss_ref="parent", breaker_entry="classic", fvg_pick="2022", stop_mode="ce2")
    assert p.mss_ref == "parent"
    d = Params()
    assert all(not getattr(d, f) or f in ("speed_bars", "unicorn_open_min", "cc_fail_pts", "moc_cap_pts",
                                          "smt_exit", "smt_entry_syms", "judas_window", "unicorn_entry",
                                          "ifvg_entry", "smt_pick", "clean_leg", "mss_on_side", "mm_context",
                                          "three_drives", "cc_swings", "ote", "news_profile", "nfp_sd",
                                          "candle_draw_bias") for f in NEW)
    assert (d.mss_on_side, d.ote, d.cc_swings, d.clean_leg, d.smt_pick) == ("off", "off", "off", -1, "first")


def test_combine_smt_pick_leader_and_laggard():
    t = lambda sym, et, smt: dict(date=pd.Timestamp(et).date(), session="AM", entry_time=pd.Timestamp(et),
                                  symbol=sym, smt=smt, setup="am_mm", ext_px=100.0, leg_hi_px=101.0, net=1.0)
    a = pd.DataFrame([t("ES", "2026-06-23 10:00", True)])
    b = pd.DataFrame([t("NQ", "2026-06-23 10:05", False)])
    assert list(B.combine(a, b).symbol) == ["ES"]                    # first fill
    assert list(B.combine(a, b, pick="leader").symbol) == ["NQ"]     # ES's sister held stronger
    assert list(B.combine(a, b, pick="laggard").symbol) == ["ES"]
    with pytest.raises(ValueError):
        B.combine(a, b, pick="x")


def test_break_ok_displacement_and_clean_leg():
    # bullish side space: OB body 99.5-100 at bars 1-2, sweep extreme bar 2, break bar 5
    o = np.array([100.0, 100.0, 99.8, 99.5, 100.2, 100.6])
    c = np.array([100.5, 99.6, 99.5, 100.1, 100.6, 102.0])
    h = np.maximum(o, c) + 0.1; l_ = np.minimum(o, c) - 0.1
    sd = type("Sd", (), dict(o=o, h=h, l=l_, c=c))()
    sw = dict(ext_i=2, ext=float(l_[2]), level=99.7)
    p = Params(disp_mult=2.0)
    assert SM.break_ok(None, sd, sw, 5, p, 100.7, {}, 0.0, 0.0)       # 102 - 100 >= 2 x 0.5
    assert not SM.break_ok(None, sd, sw, 5, Params(disp_mult=5.0), 100.7, {}, 0.0, 0.0)
    assert not SM.break_ok(None, sd, sw, 5, Params(disp_through_pts=20.0, es_pt=0.1), 100.7, {}, 0.0, 0.0)
    assert SM.break_ok(None, sd, sw, 5, Params(clean_leg=0), 100.7, {}, 0.0, 0.0)   # bars 3-5 all up-close
    assert not SM.break_ok(None, sd, dict(sw, ext_i=0), 5, Params(clean_leg=0), 100.7, {}, 0.0, 0.0)
    assert not SM.break_ok(None, sd, sw, 5, Params(mss_eq_wait=True), 100.7, {"rel_eq_lows0": 99.3}, 0.5, 0.0)
    assert SM.break_ok(None, sd, sw, 5, Params(mss_eq_wait=True), 100.7, {"rel_eq_lows0": 99.5}, 0.5, 0.0)


def test_study_has_a_variant_for_every_new_switch():
    names = " ".join(str(v) for v in study.DECISIONS.values())
    for f in NEW:
        assert f"'{f}'" in names, f
    ids = [k.split("_")[0] for k in study.DECISIONS]
    for rid in ("A19", "A19.2", "A19.4", "A20", "M0.4", "M1", "M1.1", "M1.3", "M2", "M2.3", "M2.7", "M4",
                "M4.1", "M4.2", "M4.3", "M4.4", "M4.5", "M5", "M5.1", "M5.2", "M6", "M7", "M7.2", "M7.3",
                "M10", "A8", "M11a", "M11b", "M11c", "M12", "M12.2", "M13", "M16.1", "M16.2", "Ep03.11",
                "B18.1", "B18.2", "N6", "T10", "T13", "Ep01.13", "Ep01.15", "Ep01.16", "Ep01.17", "Ep01.22",
                "Ep04.3", "Ep04.4", "Ep04.7", "Ep05.4", "Ep05.6", "Ep05.8", "Ep07.6", "Ep08.4", "Ep08.15",
                "Ep08.16", "A14", "A18", "A24.2", "M0", "M0.5", "M15"):
        assert rid in ids, rid


# --- no look-ahead -----------------------------------------------------------------------------

def _no_look_ahead(df, tf, sym, p, cols, every=1, meta=None, lag=2, min_trades=1, **kw):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        full = B.run(df, tf, sym, p, meta=meta, **kw)
        assert len(full) >= min_trades, "no trades - the test window must produce some"
        if not len(full):
            return full
        for cut_t in full.entry_time.iloc[::every]:
            c = cut_t + pd.Timedelta(minutes=lag)
            pk = {k: (v[v.index <= c] if isinstance(v, pd.DataFrame) else v) for k, v in kw.items()}
            part = B.run(df[df.index <= c], tf, sym, p, partial_last=True, meta=meta, **pk)
            a = full[full.entry_time <= cut_t][cols].reset_index(drop=True)
            b = part[part.entry_time <= cut_t][cols].reset_index(drop=True)
            pd.testing.assert_frame_equal(a, b)
    return full


def _syn(start="2026-04-01", end="2026-05-29", seed=3):
    return B.synthetic(start=start, end=end, tf=5, seed=seed)


SETS_SYN = {
    # sweep / MSS rules on the FVG path (A19, A19.2, A19.4, A20, M0.4, Ep07.6, Ep08.4, Ep01.22, M1.3)
    "mss_a": dict(POST, mss_ref="parent", mss_eq_wait=True, mss_on_side="tag", disp_mult=0.5, disp_body_mult=0.2,
                  disp_through_pts=0.25, disp_fvg_after_break=True, clean_leg=6, clean_body=3.0),
    "mss_b": dict(POST, mss_ref="origin", disp_follow=True, mss_max_bars=8, mss_disp=0.5, mss_ref_sibi=True,
                  speed_check=True, speed_bars=6, body_low_cancel=True),
    "mss_c": dict(POST, mss_on_side="require", max_risk_pts=40),
    "mss_d": dict(POST, mss_ref_tf=15, max_risk_pts=40),
    # 2022 model, unicorns, breakers, arrays (M2, M2.3, M2.7, M4, M4.1-4.3, M4.5, A14, Ep05.4, M0.5, A18)
    "m2": dict(POST, fvg_pick="2022", no_breakout_fvg=True, stop_mode="ce2", add_leg_cut=True, m2_target=True,
               three_drives="tag", ote_stack_tag=True, leg_pd_strict=True),
    "m4": dict(POST, breaker_entry="classic", unicorn_open_only=True, unicorn_entry="overlap", unicorn_rules=True,
               add_on_vi=True, adds_in_breaker=True, breaker_retest_add=True, adv_breaker=True, cc_swings="both",
               max_risk_pts=40),
    "arr": dict(POST, entry_arrays=("ob", "breaker", "ote", "wick_ce", "vi"), reclaimed_ob=True, stop_mode="ob_near",
                mmxm_ctx=True, reaper=True, reaper_confirm=True, ote="limit", ote_leg_stop=True),
    "uni_only": dict(POST, unicorn_only=True, mmxm_breaker=True, stop_mode="fvg_candle", max_risk_pts=40),
    "drives": dict(POST, three_drives="require", max_risk_pts=40),
    "ote_f": dict(POST, ote="filter", entry="ce", fvg_pick="first", max_risk_pts=40),
    "ote_arr": dict(POST, ote="filter", entry_arrays=("ote",), max_risk_pts=40),
    # IFVG (M10, A8)
    "ifvg": dict(POST, ifvg_entries=True, ifvg_entry="ce", ifvg_stop_pts=3.0, ifvg_min_risk_pts=2.0, ifvg_depth=True,
                 ifvg_hold=True, ifvg_061=True, ifvg_after_htf=True, max_risk_pts=40),
    # PM / last hour (M5, M5.2, M6, M7, M7.2, Ep01.13, Ep01.17, T10)
    "pm": dict(POST, last_hour_setup=True, pm_last_hour_model=True, lh_start_by=925, moc_pool_exit=True,
               pm_lunch_target=True, pm_judas_array=True),
    "lock": dict(pm_reversal=True, moc_run=True, moc_cap_pts=8.0, ir_entries=True, cisd_ob_entries=True,
                 wick_ce_entries=True, last_hour_own_slot=True, lh_unengaged=True, lh_htf_done_skip=True,
                 pm_lunch_org=True),
    # SMT / PO3 / news / templates (M16.1, M16.2, B18.1, B18.2, N6, T13, Ep04.3, Ep04.4, M0)
    "smt": dict(POST, smt_entry=True, smt_entry_syms=("RW",), smt_exit=650, smt_min_gap_pts=0.5, smt_rel_eq=True,
                smt_windows=((300, 960),), smt_pre=True, sick_sister=True, require_judas=True, judas_window=120,
                po3_runner=True, po3_require_bias=False, po3_inclusive=True, po3_hold=True, nfp_sd="tag",
                news_profile="tag", news_ce_target=True, news_no_unicorn=True, candle_draw_bias="daily",
                max_risk_pts=40),
    "smt_t": dict(smt_entry=True, smt_turtle=True, smt_entry_syms=("RW",), draw_lock="off", turtle_soup="2023",
                  ts_adds_breakers=True, ts_breaker_pyramid=True, ts_max_run=20),
    "bias": dict(po3_require_bias=True, candle_draw_bias="weekly", smt_need_array=True),
}


@pytest.mark.parametrize("name", list(SETS_SYN))
def test_look_ahead_synthetic(name):
    x, y = _syn()
    every = 3 if name in ("lock", "arr", "m4", "smt_t") else 1
    _no_look_ahead(x, 5, "RW", Params(**SYN, **SETS_SYN[name]), COLS, every=every, partner=y)


def test_synthetic_switches_change_the_engine():
    """Each family above actually fires on the synthetic window (not inert)."""
    x, y = _syn()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        run = lambda kw: B.run(x, 5, "RW", Params(**SYN, **kw), y)
        k = run(SETS_SYN["lock"]).entry_kind
        assert {"pm_reversal", "ir", "wick_ce"} <= set(k)
        assert "cisd_ob" in set(run(dict(POST, cisd_ob_entries=True, draw_lock="session")).entry_kind)
        assert "adv_breaker" in set(run(dict(POST, adv_breaker=True, max_risk_pts=40)).entry_kind)
        assert "cc_breaker_swing" in set(run(dict(POST, cc_swings="both", max_risk_pts=40)).entry_kind)
        k = run(dict(POST, entry_arrays=("ob", "breaker", "wick_ce"), reclaimed_ob=True)).entry_kind
        assert k.str.startswith("arr_").any()
        t = run(dict(POST, mss_on_side="require"))
        assert len(t) and t.lv_tags.str.contains("on_side").all()
        t = run(dict(POST, fvg_pick="2022", three_drives="tag", m2_target=True))
        assert t.lv_tags.str.contains("three_drives").any() and t.lv_tags.str.contains("draw_m2").any()


def _es(a="2023-10-02", b="2023-11-17"):
    es = B.load("ES", 5, source="databento")
    nq = B.load("NQ", 5, source="databento")
    return (es[(es.index >= a) & (es.index < b)], nq[(nq.index >= a) & (nq.index < b)], B.load_meta("ES", 5))


ES_BASE = dict(FUT, draw_lock="off", htf_resist_cap=False, leg_pd=0, min_draw_pts=0, use_bias=False)
ES_COLS = ["entry_time", "entry", "stop", "t1", "lv_tags", "entry_kind", "setup", "swept"]


@pytest.mark.skipif(not ES, reason="no ES / NQ data")
def test_look_ahead_es_confluence_switches():
    """Switches that read the confluence table / htf table / overnight bars: nested FVGs, the Ep 01
    last hour (own slot, 4h CE hold), daily VI targets, the MM context, turtle soup with order flow,
    the SMT array gate, profile tags, the 13:30 Judas into an array, IFVG after an HTF array."""
    df, pa, meta = _es()
    p = Params(**ES_BASE, ob_entry="both", nest_tfs=("15m",), pm_ep01=True, pm_4h_ce=True, last_hour_own_slot=True,
               vi_arrays=True, daily_vi_targets=True, am_htf_draw=False, mm_context="tag", am_discount_array=False,
               ts_need_flow=True, turtle_soup="2023", smt_need_array=True, profile_tags=True, pm_judas_array=True,
               ifvg_entries=True, ifvg_after_htf=True)
    full = _no_look_ahead(df, 5, "ES", p, ES_COLS, every=1, meta=meta, partner=pa)
    assert full.lv_tags.str.contains("profile_").all()
    p2 = Params(**ES_BASE, ob_entry="post_mss", am_htf_draw=True, am_discount_array=True, mm_context="require",
                sick_sister=True, smt_entry=True, smt_turtle=False, smt_pick="leader", max_risk_pts=25)
    _no_look_ahead(df, 5, "ES", p2, ES_COLS, every=1, meta=meta, partner=pa, min_trades=0)


@pytest.mark.skipif(not ES, reason="no ES / NQ data")
def test_look_ahead_es_ma_deuce_and_sb_displacement():
    """M15 Ma Deuce switches (ETH dailies, big candle, ladder, 2nd entry, news / blocked routing) and
    the A20 displacement rules inside the Silver Bullet."""
    df, pa, meta = _es("2023-09-05", "2023-12-22")
    p = Params(**ES_BASE, ma_deuce=True, md_eth=True, md_ladder=True, md_second=True, md_blocked=True,
               sb_model=True, disp_follow=True, disp_fvg_after_break=True, disp_through_pts=0.25, disp_mult=0.5,
               am=(0, 0), pm=(0, 0))
    full = _no_look_ahead(df, 5, "ES", p, ES_COLS, every=1, meta=meta)
    assert set(full.setup) & {"ma_deuce", "sb_am", "sb_pm"}
    p2 = replace(p, md_big_candle=1.0, md_need_news=True, md_eth=False, sb_model=False)
    _no_look_ahead(df, 5, "ES", p2, ES_COLS, every=1, meta=meta, min_trades=0)
