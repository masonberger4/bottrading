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
from dataclasses import dataclass as _oa_dc


@_oa_dc
class Params(Params):   # OA1029: these tests were written for the pre-build engine and exercise other rules - every OA1029 default back at its old value
    __annotations__ = {k: object for k in __import__('mentorship.study', fromlist=['OA1029_OLD']).OA1029_OLD}
    locals().update(__import__('mentorship.study', fromlist=['OA1029_OLD']).OA1029_OLD)

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
       "md_second", "md_ladder", "md_need_news", "md_eth", "md_blocked",
       # review pass
       "ob_pre_gate", "synth_po3", "lh_no_lock", "pm_ep01_adds", "sick_depth", "mmxm_rel_eq", "implied_fvg",
       "adv_breaker_pre", "cc_profile")


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
                                          "candle_draw_bias", "ob_pre_gate", "sick_depth", "cc_profile") for f in NEW)
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
                "Ep08.16", "A14", "A18", "A24.2", "M0", "M0.5", "M15", "A24.1", "D10"):
        assert rid in ids, rid


# --- no look-ahead -----------------------------------------------------------------------------

XCOLS = ["entry_time", "exit_time", "exit_reason", "n_adds", "net"]   # exits / adds (review fix)


def _no_look_ahead(df, tf, sym, p, cols, every=1, meta=None, lag=2, min_trades=1, exits=False, **kw):
    """Full run vs runs truncated just after each entry (every `every`-th): the entries up to the
    cut must be identical. exits=True (review fix: the exit / add switches were never compared)
    also cuts just after exit times and compares, for every trade CLOSED by the cut, its exit
    time, reasons, number of adds and net P&L."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        full = B.run(df, tf, sym, p, meta=meta, **kw)
        assert len(full) >= min_trades, "no trades - the test window must produce some"
        if not len(full):
            return full
        cuts = list(full.entry_time.iloc[::every])
        if exits:
            cuts = sorted(set(cuts) | set(pd.to_datetime(full.exit_time).iloc[::every]))
        for cut_t in cuts:
            c = cut_t + pd.Timedelta(minutes=lag)
            pk = {k: (v[v.index <= c] if isinstance(v, pd.DataFrame) else v) for k, v in kw.items()}
            part = B.run(df[df.index <= c], tf, sym, p, partial_last=True, meta=meta, **pk)
            fa = full[full.entry_time <= cut_t].reset_index(drop=True)
            pa_ = part[part.entry_time <= cut_t].reset_index(drop=True) if len(part) else part
            pd.testing.assert_frame_equal(fa[cols], pa_[cols] if len(pa_) else fa[cols].iloc[:0])
            if exits:
                done = (pd.to_datetime(fa.exit_time) <= cut_t).values
                xa = fa[done][XCOLS].astype({"exit_time": str}).reset_index(drop=True)
                xb = pa_[done][XCOLS].astype({"exit_time": str}).reset_index(drop=True)
                pd.testing.assert_frame_equal(xa, xb)
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


# setups_models review pass: the MSS gates on the default OB order, the new switches
SETS_SYN.update({
    "ob_hold": dict(draw_lock="off", ob_pre_gate="hold", disp_mult=2.0, mss_on_side="tag", mss_ref="origin"),
    "ob_cancel": dict(draw_lock="off", disp_mult=2.0, speed_check=True, mss_max_bars=8, clean_leg=6),
    "review_post": dict(POST, implied_fvg=True, mmxm_ctx=True, cc_swings="failure", unicorn_only=False,
                        moc_run=True, max_risk_pts=40),
    "review_pre": dict(adv_breaker_pre=True, cc_profile="gate", smt_entry=True, smt_entry_syms=("RW",),
                       smt_pre=True),
})
EXIT_SETS = ("m4", "arr", "ifvg", "pm", "lock", "smt", "smt_t", "review_post", "review_pre")


@pytest.mark.parametrize("name", list(SETS_SYN))
def test_look_ahead_synthetic(name):
    x, y = _syn()
    every = 3 if name in ("lock", "arr", "m4", "smt_t") else 1
    _no_look_ahead(x, 5, "RW", Params(**SYN, **SETS_SYN[name]), COLS, every=every, partner=y,
                   exits=name in EXIT_SETS)   # review fix: exits / adds compared where those switches act


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




def _kinds(t):
    return set(t.entry_kind) if len(t) else set()


def _has_tag(t, tag):
    return bool(len(t)) and t.lv_tags.fillna("").str.contains(tag).any()


@pytest.mark.skipif(not ES, reason="no ES / NQ data")
def test_look_ahead_es_confluence_switches():
    """Switches that read the confluence table / htf table / overnight bars: nested FVGs, the Ep 01
    last hour (own slot, 4h CE hold, the Ep 01 add sequence), daily VI targets, the MM context,
    turtle soup with order flow, the SMT array gate, profile tags, the 13:30 Judas into an array,
    IFVG after an HTF array. Entries AND exits / adds compared; the switches must fire."""
    df, pa, meta = _es()
    p = Params(**ES_BASE, ob_entry="both", nest_tfs=("15m",), pm_ep01=True, pm_4h_ce=True, last_hour_own_slot=True,
               pm_ep01_adds=True, vi_arrays=True, daily_vi_targets=True, mm_context="tag", ts_need_flow=True,
               turtle_soup="2023", smt_need_array=True, profile_tags=True, pm_judas_array=True, ifvg_entries=True,
               ifvg_after_htf=True)
    full = _no_look_ahead(df, 5, "ES", p, ES_COLS, every=2, meta=meta, partner=pa, exits=True)
    assert full.lv_tags.str.contains("profile_").all()
    assert {"pm_ep01", "turtle_soup", "ifvg"} <= _kinds(full) and _has_tag(full, "mm_ctx")


@pytest.mark.skipif(not ES, reason="no ES / NQ data")
def test_look_ahead_es_smt_entry_and_context():
    """M16.1 SMT entry (buy stop, 11:00 time exit) with the M1 context gates; the SMT stop order must
    arm and fill on ES with NQ as the sister (review: it was inert - PO3 filter, OB-order replacement,
    no re-arm after a new low). M16.2 sick sister with B18.2 smt_pre."""
    df, pa, meta = _es()
    p = Params(**ES_BASE, smt_entry=True, mm_context="tag", am_htf_draw=True)
    full = _no_look_ahead(df, 5, "ES", p, ES_COLS, every=2, meta=meta, partner=pa, exits=True)
    assert "smt_stop" in _kinds(full) and _has_tag(full, "mm_ctx")
    p2 = Params(**ES_BASE, sick_sister=True, sick_depth=0.5, smt_pre=True)
    full = _no_look_ahead(df, 5, "ES", p2, ES_COLS, every=1, meta=meta, partner=pa, exits=True)
    assert len(full)


@pytest.mark.skipif(not ES, reason="no ES / NQ data")
def test_look_ahead_es_ob_pre_gates():
    """Owner #11 x the MSS gates (review fix): "hold" fills the OB order only after the gated MSS,
    "cancel" (default) drops it when the break fails the gates - both without look-ahead, both
    acting on the default OB entry."""
    df, pa, meta = _es()
    p = Params(**ES_BASE, ob_pre_gate="hold", disp_mult=0.5, disp_follow=True, mss_ref="origin",
               mss_on_side="tag", clean_leg=4)
    full = _no_look_ahead(df, 5, "ES", p, ES_COLS, every=1, meta=meta, partner=pa, exits=True)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        base = B.run(df, 5, "ES", Params(**ES_BASE), pa, meta=meta)
    assert len(full) < len(base) and _kinds(full) == {"ob_pre"}
    S.FUNNEL = __import__("collections").Counter()
    try:
        p2 = Params(**ES_BASE, disp_mult=3.0, speed_check=True, mss_max_bars=6)
        _no_look_ahead(df, 5, "ES", p2, ES_COLS, every=2, meta=meta, partner=pa)
        assert S.FUNNEL["x_ob_pre_gate"] > 0
    finally:
        S.FUNNEL = None


@pytest.mark.skipif(not ES, reason="no ES / NQ data")
def test_look_ahead_es_review_new_switches():
    """M4.3 adv_breaker_pre and T13 cc_profile (gate) under the #9 lock; turtle-soup adds."""
    df, pa, meta = _es()
    p = Params(**dict(ES_BASE, draw_lock="session"), adv_breaker_pre=True, cc_profile="gate", turtle_soup="2023",
               ts_adds_breakers=True, ts_breaker_pyramid=True)
    full = _no_look_ahead(df, 5, "ES", p, ES_COLS, every=2, meta=meta, partner=pa, exits=True)
    assert "adv_breaker_pre" in _kinds(full) and _has_tag(full, "cc_")


@pytest.mark.skipif(not ES, reason="no ES / NQ data")
def test_look_ahead_es_fvg_exits_and_adds():
    """FVG-path exits / adds: A8 ifvg_hold exit, Ep05.8 mmxm (the ce_hold rule), Ep05.4 add_on_vi,
    M4 breaker_retest_add - exits and adds compared."""
    df, pa, meta = _es()
    p = Params(**ES_BASE, ob_entry="post_mss", ifvg_entries=True, ifvg_hold=True, mmxm_ctx=True, add_on_vi=True,
               breaker_retest_add=True)
    full = _no_look_ahead(df, 5, "ES", p, ES_COLS, every=1, meta=meta, partner=pa, exits=True)
    assert full.exit_reason.str.contains("ce_close").any() and _has_tag(full, "draw_mmxm")


@pytest.mark.skipif(not ES, reason="no ES / NQ data")
def test_look_ahead_es_smt_pick_combine():
    """Ep03.11 smt_pick: the combined book picked from runs truncated at each fill equals the full
    book's picks up to that fill (the pick uses only fields known at the sweep)."""
    df, pa, meta = _es("2023-10-02", "2023-10-28")
    p = Params(**ES_BASE, smt_pick="leader")
    q = replace(p, es_pt=round(float(pa.close.median() / df.close.median()), 2))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        a, b = B.run(df, 5, "ES", p, pa, meta=meta), B.run(pa, 5, "NQ", q, df)
        full = B.combine(a, b, pick="leader")
        assert len(full) and full.symbol.nunique() == 2
        for cut_t in full.entry_time.iloc[::3]:
            c = cut_t + pd.Timedelta(minutes=2)
            a2 = B.run(df[df.index <= c], 5, "ES", p, pa[pa.index <= c], partial_last=True, meta=meta)
            b2 = B.run(pa[pa.index <= c], 5, "NQ", q, df[df.index <= c], partial_last=True)
            part = B.combine(a2, b2, pick="leader")
            x = full[full.entry_time <= cut_t][["entry_time", "symbol", "entry"]].reset_index(drop=True)
            y = part[part.entry_time <= cut_t][["entry_time", "symbol", "entry"]].reset_index(drop=True)
            pd.testing.assert_frame_equal(x, y)


@pytest.mark.skipif(not ES, reason="no ES / NQ data")
def test_pm_ep01_trades_the_ep01_day():
    """M5.1 on its own example (Ep 01, ES Dec 30 2022, ~15:25 long at the 1m FVG top inside the
    nested 1h / 4h FVGs): the review found pm_ep01 inert on ES; with owner #1's window and the
    nested-pair search it buys the last hour that day (lock / cap off: the 15:00 LH lock that day
    is the AM low below)."""
    df, pa, meta = _es("2022-11-15", "2023-01-04")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        t = B.run(df, 5, "ES", Params(**FUT, draw_lock="off", htf_resist_cap=False, pm_ep01=True,
                                      last_hour_own_slot=True, pm_ep01_adds=True), pa, meta=meta)
    ep = t[(t.entry_kind == "pm_ep01") & (t.date.astype(str) == "2022-12-30")]
    assert len(ep) == 1 and ep.side.iloc[0] == "long" and ep.setup.iloc[0] == "pm_last_hour"
    m = ep.entry_time.iloc[0].hour * 60 + ep.entry_time.iloc[0].minute
    assert 900 <= m < 950


@pytest.mark.skipif(not ES, reason="no ES / NQ data")
def test_last_hour_own_slot_locks_its_own_draw():
    """Owner #9 x M5.2 / Ep01.13 (review fix): the own LH slot locks its draw at 15:00 and trades
    only toward it; lh_no_lock restores the first build."""
    df, pa, meta = _es("2023-10-02", "2023-11-17")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        t = B.run(df, 5, "ES", Params(**FUT, last_hour_own_slot=True), pa, meta=meta)
    lh = [lk for lk in t.attrs["locks"] if lk["session"] == "LH"]
    assert lh and all(lk["t_lock"] == 900 for lk in lh)
    by_day = {lk["day"]: lk for lk in lh}
    for r in t[t.setup == "pm_last_hour"].itertuples() if len(t) else []:
        lk = by_day.get(r.date)
        if lk is not None and lk["side"] and r.draw_name:
            assert r.draw_name == lk["name"] and (r.side == "long") == (lk["side"] > 0)
    assert 900 in B.lock_cuts(Params(last_hour_own_slot=True))
    assert 900 not in B.lock_cuts(Params(last_hour_own_slot=True, lh_no_lock=True))


@pytest.mark.skipif(not ES, reason="no ES / NQ data")
def test_md_eth_builds_eth_dailies():
    """M15 md_eth (review fix): prepare builds the ETH sessions when md_eth is the only ETH switch,
    and the Ma Deuce dailies then differ from the RTH ones."""
    from mentorship import pre_open as PO
    df, _, meta = _es("2023-09-05", "2023-10-20")
    p = Params(**FUT, ma_deuce=True, md_eth=True)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        pr = B.prepare(df, 5, "ES", p, meta=meta)
        assert pr.eth and B.prepare(df, 5, "ES", Params(**FUT, ma_deuce=True), meta=meta).eth is None
    kw = B.day_kwargs(pr, len(pr.ds) - 1)
    ctx = type("C", (), dict(eth=pr.eth))()
    d = kw["df"].index[0].date()
    eth = PO._dailies(ctx, kw["hist"], p, d, 4)
    rth = PO._dailies(ctx, kw["hist"], replace(p, md_eth=False), d, 4)
    assert not (np.allclose(eth[1], rth[1]) and np.allclose(eth[2], rth[2]))


# --- unit tests: review fixes ----------------------------------------------------------------------

class _Side:
    def __init__(self, o, h, l_, c, ph=(), pl=()):
        self.o, self.h, self.l, self.c = (np.array(x, float) for x in (o, h, l_, c))
        self.ph, self.pl, self.gaps, self._lz, self.c2_dir, self.sign = list(ph), list(pl), [], {}, False, 1

    def x(self, v):
        return v


def test_break_ok_measures_the_ob_at_the_sweep_low():
    """A20 / M0.4 review fix: a small pullback down-close candle in the up-leg after the low is not
    the OB - the displacement is measured against the OB at the sweep low."""
    o = [101.0, 100.2, 99.1, 100.5, 100.3]
    c = [100.0, 99.0, 100.5, 100.3, 103.0]           # bars 0-1 = the OB at the low (body 99-101)
    h = [101.2, 100.3, 100.7, 100.6, 103.1]
    l_ = [99.8, 98.8, 99.0, 100.1, 100.2]
    sd = _Side(o, h, l_, c)
    sw = dict(ext_i=1, ext=98.8, level=99.5)
    assert SM.ob_low(sd, 1)[1:] == (101.0, 99.0)
    assert not SM.break_ok(None, sd, sw, 4, Params(disp_mult=1.5), 101.5, {}, 0.0, 0.0)   # 2 < 1.5 x 2
    assert SM.break_ok(None, sd, sw, 4, Params(disp_mult=0.9), 101.5, {}, 0.0, 0.0)       # 2 >= 1.8


def test_disp_ok_sb_takes_the_first_breaking_close_that_displaces():
    o = [101.0, 100.2, 99.1, 101.6, 101.5, 101.7]
    c = [100.0, 99.0, 100.5, 101.7, 101.6, 106.0]    # bar 3 breaks weakly, bar 5 with displacement
    h = [101.2, 100.3, 100.7, 101.8, 101.8, 106.1]
    l_ = [99.8, 98.8, 99.0, 101.5, 101.4, 101.6]
    sd = _Side(o, h, l_, c)
    ok, k = SM.disp_ok_sb(sd, 1, 5, 101.5, Params(disp_mult=1.5))
    assert ok and k == 5
    ok, k = SM.disp_ok_sb(sd, 1, 4, 101.5, Params(disp_mult=1.5))
    assert not ok and k == 3


def test_leg_origin_walks_back_to_the_start_of_the_down_leg():
    P = L.Pivot
    # swing highs 110 (bar 2), 108 (bar 6), 105 (bar 10); swing lows 104 (bar 4), 101 (bar 8)
    c = np.full(14, 100.0)
    sd = _Side(c, c, c, c, ph=[P(2, 110.0, 3), P(6, 108.0, 7), P(10, 105.0, 11)], pl=[P(4, 104.0, 5), P(8, 101.0, 9)])
    assert SM.leg_origin(sd, 12, 13).i == 2           # lower highs, lower lows: one leg from bar 2
    sd.pl = [P(4, 104.0, 5), P(8, 106.0, 9)]          # a higher low after bar 6: the leg starts at 6
    assert SM.leg_origin(sd, 12, 13).i == 6
    sd.pl = [P(4, 104.0, 5), P(8, 101.0, 9)]
    sd.c[7] = 108.5                                   # a close above the bar-6 high: the leg starts at 10
    assert SM.leg_origin(sd, 12, 13).i == 10
    assert SM.leg_origin(sd, 12, 10) is None or SM.leg_origin(sd, 12, 10).i < 10   # bar 10 not known by 10


def test_on_side_wait_times_the_fvg_from_the_second_break():
    """Ep04.7 review fix: once the second MSS printed, fvg_wait runs from it (a leg-2 FVG formed
    1-2 bars after the second break is still taken), and the first leg's FVG must stay open."""
    P = L.Pivot
    c = np.full(20, 100.8)
    sd = _Side(c, c + 0.2, c - 0.2, c, pl=[P(8, 100.5, 9)])
    sd.h[3] = 102.0                                   # the high before the higher low
    sd.c[10] = 102.5                                  # the second break (bar 10)
    sd.gaps = [L.Zone("bull", 101.0, 100.6, 4, 3)]    # the first leg's FVG (known at 4)
    sw = dict(ext_i=1, ext=99.0, broke=3)
    p = Params(fvg_wait=2, pending_minutes=60)
    ctx = type("C", (), dict(tf=5))()
    assert SM.on_side_wait(ctx, sd, sw, 9, p, 2) == "wait"
    assert SM.on_side_wait(ctx, sd, sw, 10, p, 2) is None and sw["broke2"] == 10 and sw["leg2_from"] == 8
    assert S._fvg_wait_from(sw) == 10                 # 11 - 10 < fvg_wait: not timed out on bar 11
    assert SM.on_side_wait(ctx, sd, sw, 11, p, 2) is None
    sd.c[12] = 100.5                                  # a close below the first leg's FVG bottom
    assert SM.on_side_wait(ctx, sd, sw, 12, p, 2) == "drop"


def test_reaper_confirm_takes_a_close_between_ce_and_top(monkeypatch):
    """A24.2 review fix: the reaction candle wicks into the Reaper and closes between its CE and
    top - that is the confirmation (market entry); a close below the CE kills it; else wait."""
    P = L.Pivot
    seen = {}
    monkeypatch.setattr(S, "_finish_order", lambda *a, **k: seen.setdefault("o", (a[6], a[10])))
    c = np.full(12, 106.0)
    sd = _Side(c, c + 0.5, c - 0.5, c, pl=[P(0, 100.0, 1)])
    z = L.Zone("bull", 105.0, 103.0, 4, 3)
    ctx = type("C", (), dict(tf=5))()
    mk = lambda: dict(ext=99.0, ext_i=8, broke=9, reaper=z, reaper_e=8)
    p = Params(reaper=True, reaper_confirm=True, fvg_wait=2)
    sd.l[10], sd.c[10] = 104.5, 104.4                 # wick in, close between CE 104 and top 105
    assert SM.reaper_order(ctx, sd, mk(), 10, p, "AM", 1.0, 6, True, 2) is not None
    assert seen["o"][0] == 104.4 and seen["o"][1]["market"] and seen["o"][1]["entry_kind"] == "reaper"
    sw = mk()
    sd.c[10] = 103.5                                  # a body close below the CE: failed
    assert SM.reaper_order(ctx, sd, sw, 10, p, "AM", 1.0, 6, True, 2) is None and sw["reaper_dead"]
    sd.l[10], sd.c[10] = 105.5, 106.0                 # no reaction yet
    assert SM.reaper_order(ctx, sd, mk(), 10, p, "AM", 1.0, 6, True, 2) == "wait"


def test_smt_windows_and_lh_window():
    assert S._smt_window_ok(Params(smt_pre=True), 700)              # () = any time, smt_pre adds only
    assert not S._smt_window_ok(Params(smt_windows=((720, 900),)), 700)
    assert S._smt_window_ok(Params(smt_windows=((720, 900),), smt_pre=True), 400)
    assert SM.lh_window(Params()) == (900, 950)                     # owner #1
    assert SM.lh_window(Params(last_hour_strict=True)) == (915, 945)


def test_implied_fvgs():
    # bullish: candle 1 upper wick 100 -> 101 (CE 100.5), candle 3 lower wick 100.8 -> 102 (CE 101.4):
    # the wicks overlap (no real FVG); implied gap = 100.5 .. 101.4
    o = np.array([99.0, 100.2, 102.5])
    c = np.array([100.0, 102.4, 102.0])
    h = np.array([101.0, 102.6, 103.0])
    l_ = np.array([98.8, 100.1, 100.8])
    z = L.implied_fvgs(o, h, l_, c)
    assert len(z) == 1 and z[0].kind == "bull" and (round(z[0].bottom, 2), round(z[0].top, 2)) == (100.5, 101.4)
    assert L.implied_fvgs(o, h, np.array([98.8, 100.1, 101.2]), c) == []    # a real FVG: not implied


def test_review_params_validate_and_default_off():
    for kw in (dict(ob_pre_gate="x"), dict(cc_profile="y"), dict(mss_ref="origin2")):
        with pytest.raises(ValueError):
            Params(**kw)
    d = Params()
    assert (d.ob_pre_gate, d.synth_po3, d.lh_no_lock, d.pm_ep01_adds, d.mmxm_rel_eq, d.implied_fvg,
            d.adv_breaker_pre, d.cc_profile) == ("cancel", False, False, False, False, False, False, "off")


def test_synthetic_review_switches_fire():
    x, y = _syn()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        run = lambda kw: B.run(x, 5, "RW", Params(**SYN, **kw), y)
        assert "adv_breaker_pre" in _kinds(run(dict(adv_breaker_pre=True)))
        assert "implied_fvg" in _kinds(run(dict(POST, implied_fvg=True)))
        assert "cc_failure_swing" in _kinds(run(dict(POST, cc_swings="failure")))
        t = run(dict(POST, unicorn_only=True, max_risk_pts=40))
        assert len(t) and t.unicorn.all()
        base, hold = run(dict(draw_lock="off")), run(dict(draw_lock="off", disp_mult=2.0, ob_pre_gate="hold"))
        assert 0 < len(hold) < len(base)
        t = run(dict(draw_lock="off", cc_profile="tag"))
        assert t[t.session == "PM"].lv_tags.str.contains("cc_").all()


@pytest.mark.skipif(not ES, reason="no ES / NQ data")
def test_look_ahead_es_ma_deuce_and_sb_displacement():
    """M15 Ma Deuce switches (ETH dailies, ladder, 2nd entry, blocked routing; then big candle + news)
    and the A20 displacement rules inside the Silver Bullet. Review fix: Ma Deuce must actually trade
    in the window (Feb-Mar 2020: 02-24 / 03-11; it is rare on ES - see build_log for the gate
    funnel), exits / adds compared."""
    df, pa, meta = _es("2020-02-03", "2020-03-20")
    p = Params(**ES_BASE, ma_deuce=True, md_eth=True, md_ladder=True, md_second=True, md_blocked=True,
               sb_model=True, disp_follow=True, disp_fvg_after_break=True, disp_through_pts=0.25, disp_mult=0.5,
               am=(0, 0), pm=(0, 0))
    full = _no_look_ahead(df, 5, "ES", p, ES_COLS, every=1, meta=meta, exits=True)
    assert "ma_deuce" in set(full.setup) and set(full.setup) & {"sb_am", "sb_pm"}
    p2 = replace(p, md_big_candle=1.0, md_need_news=True, md_eth=False, sb_model=False)
    full = _no_look_ahead(df, 5, "ES", p2, ES_COLS, every=1, meta=meta, exits=True)
    assert list(full.setup) == ["ma_deuce"] and str(full.date.iloc[0]) == "2020-03-11"
