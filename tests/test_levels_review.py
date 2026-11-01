"""Review fixes to package levels_detectors (build_log.md "Review pass: levels_detectors"): unit tests
for the fixed helpers and gates, and no-look-ahead runs (full vs truncated) for every switch the
review touched - with the entry fields AND the exits (exit_time / exit_reason) of trades closed
before each cut, since lvx exits (q_close, breakaway_ce, wick_inv, bpr_abort, release_open) are
not entry fields. The databento tests skip when the ES data is missing."""
import warnings
from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from mentorship import backtest as B, levels as L, paper, strategy as S, study
from mentorship.strategy import Params
from dataclasses import dataclass as _oa_dc


@_oa_dc
class Params(Params):   # OA1029 Q92: these tests exercise other rules; the order-block narrative gate (default on) leaves them no trades
    ob_need_narrative: bool = False

from test_levels_detectors import BASE, ES, FUT, day, frame, history, ctx_for, prior_days

NY = "America/New_York"


# --- T2 bias_open: an open is used only once its bar is in -----------------------------------

def test_open_known_only_from_its_bar():
    df = day([(104.0, 104.2, 103.6, 103.8)] * 4)
    ctx = ctx_for(df, history(), Params(**BASE))
    k = S._idx_at(ctx, 570)
    assert S._open_known(ctx, "0930", k - 1) is None                   # 09:25: the 09:30 open is not in yet
    assert S._open_known(ctx, "0930", k) == 104.0
    assert S._open_known(ctx, "midnight", ctx.start) == 100.0
    assert S._open_known(ctx, "0830", S._idx_at(ctx, 510) - 1) is None


def test_monday_nwog_only_from_0930():
    # found by the pre-09:30 look-ahead test: a Monday's own NWOG (Friday close -> 09:30 open) was a
    # PRE7 / PRE9 target before the 09:30 open printed; before 09:30 the 4 prior NWOGs are used
    d = pd.Timestamp("2026-06-22").date()                             # a Monday
    hist = history(d=d, n=30)
    df = day([(104.0, 104.2, 103.6, 103.8)] * 4, d=d)
    ctx = ctx_for(df, hist, Params(**BASE))
    k = S._idx_at(ctx, 570)
    assert ctx.nwog_today and ctx.nwog[-1] == (100.0, 104.0)
    assert S._nwogs(ctx, k) == ctx.nwog and (100.0, 104.0) not in S._nwogs(ctx, k - 1)
    assert S._nwogs(ctx, k - 1) == ctx.nwog_prev and len(ctx.nwog_prev) == 4
    assert S._nwogs(ctx, None) == ctx.nwog_prev


# --- L2: only HTF arrays satisfy daily_level_needs_array ----------------------------------------

def test_daily_level_array_needs_an_htf_timeframe():
    p = Params(daily_level_needs_array=True)
    assert not S._htf_array(["5m"], p) and not S._htf_array(["1m", "5m"], p) and not S._htf_array([], p)
    assert S._htf_array(["5m", "15m"], p) and S._htf_array(["D"], p)
    assert S._htf_array(["5m"], replace(p, daily_level_array_tfs=("5m",)))
    with pytest.raises(ValueError):
        Params(daily_level_array_tfs=("2h",))


# --- Ep08.1 daily_fvg_exact: the exact edge replaces its "array" twin -------------------------

def test_daily_fvg_exact_ladder_holds_only_the_exact_level():
    p = Params(daily_fvg_exact=True, exit_before_pts=0.5, es_pt=1.0)
    lv = sorted({(100.0, "array"), (100.0, "exact"), (101.0, "array"), (100.1, "array"), (100.0, "pool")})
    out = S._drop_near_exact(lv, 0.25)
    assert out == [(100.0, "exact"), (100.0, "pool"), (101.0, "array")]
    ladder = [S._exit_px(v, k, p) for v, k in out if k != "pool"]
    assert ladder == [100.0, 100.5]                                   # v itself, no v - exit_before rung
    assert S._drop_near_exact([(100.0, "array")], 0.25) == [(100.0, "array")]


# --- L7: the ORG far edge in the #9 lock from 09:30, dropped on breakaway ----------------------

def _org_day(rows_0930):
    hist = history(n=8, hi=110.0, lo=90.0)
    df = day(rows_0930)
    return df, hist, {hist[-1].index[0].date(): 94.0}                 # prior close 94 (ORG 94 -> open)


def test_org_draw_in_the_0930_lock_and_breakaway_relock():
    df, hist, closes = _org_day([(104.0, 104.2, 101.6, 103.8)] * 24)   # gap up: never reaches 101.5 (25%)
    p = Params(**BASE, org_draw="draw", draw_lock="session", org_days=6)   # org_days > 5: closes used
    ctx = ctx_for(df, hist, p, closes=closes)
    lk = S.mark_levels(ctx, None, 570, "AM", p)
    assert lk["name"] == "org_far" and lk["target"] == 94.0
    assert S.mark_levels(ctx, None, 570, "AM", replace(p, org_draw="off"))["name"] != "org_far"
    assert S._org_break(ctx, p, S._idx_at(ctx, 590)) is None           # not known before 10:00
    assert S._org_break(ctx, p, S._idx_at(ctx, 600)) is True
    ctx.lock = {"AM": lk}
    done, spent = {"AM": False}, []
    S._lock_step(ctx, p, {"AM": 570}, S._idx_at(ctx, 590), 590, None, done, spent, [], None)
    assert ctx.lock["AM"]["name"] == "org_far"
    S._lock_step(ctx, p, {"AM": 570}, S._idx_at(ctx, 600), 600, None, done, spent, [], None)
    assert ctx.lock["AM"]["name"] != "org_far" and ctx.lock["AM"]["org_break_i"] == S._idx_at(ctx, 600)
    # an attempt into the gap (101.4 <= 101.5) by 10:00: no breakaway, the lock keeps the far edge
    df2, hist2, closes2 = _org_day([(104.0, 104.2, 101.4, 103.8)] + [(103.8, 104.0, 103.6, 103.8)] * 23)
    ctx2 = ctx_for(df2, hist2, p, closes=closes2)
    assert S._org_break(ctx2, p, S._idx_at(ctx2, 600)) is False


def test_org_half_draw_in_a_later_lock():
    # 09:30-10:00: CE (99) reached, far edge (94) not -> the unfilled half's far edge at a 10:00 lock
    df, hist, closes = _org_day([(104.0, 104.2, 98.9, 100.0)] + [(100.0, 100.2, 99.8, 100.0)] * 23)
    p = Params(**BASE, org_half_draw=True, draw_lock="session", org_days=6)
    ctx = ctx_for(df, hist, p, closes=closes)
    lk = S.mark_levels(ctx, None, 600, "AM", p)
    assert lk["name"] == "org_half" and lk["target"] == 94.0
    assert S.mark_levels(ctx, None, 570, "AM", p)["name"] != "org_half"   # nothing traded by 09:30


# --- Ep01.6 / A13.1 breaker defaults ------------------------------------------------------------

def test_breaker_defaults_follow_ep01_6_and_baselines_pin_the_old_rule():
    p = Params()
    assert p.breaker_ll is True and p.breaker_cand_to == "h"
    for base in (study.PRE_OWNER, study.CURRENT):
        assert base["breaker_ll"] is False and base["breaker_cand_to"] == "ext"
    assert "A13.1_breaker_ll_off" in study.DECISIONS and "Ep01.6_breaker_cand_ext" in study.DECISIONS


# --- B21: IPDA ranges from full sessions ----------------------------------------------------------

def test_ipda_from_eth_sessions_with_rth_fallback():
    n = 61
    hist = history(n=n, hi=104.0, lo=96.0)
    dates = [x.index[0].date() for x in hist]
    eth = {d: (100.0, 104.0, 96.0, 100.0) for d in dates}
    eth[dates[-5]] = (100.0, 112.0, 96.0, 100.0)                       # an overnight high: the 20-day high
    eth[dates[-45]] = (100.0, 104.0, 85.0, 100.0)                      # an overnight low: the 60-day low
    del eth[dates[-2]]                                                 # no ETH candle -> its RTH session
    df = day([(100.0, 100.2, 99.8, 100.0)] * 4)
    p = Params(**BASE, ipda_pools=True)
    ctx = ctx_for(df, hist, p, eth=eth)
    assert ctx.ipda[20] == (112.0, 96.0) and ctx.ipda[40] == (112.0, 96.0) and ctx.ipda[60] == (112.0, 85.0)
    ctx_r = ctx_for(df, hist, replace(p, ipda_session="rth"), eth=eth)
    assert ctx_r.ipda[60] == (104.0, 96.0)
    assert ctx.ipda_days[-5] == (112.0, 96.0)                          # _ipda_eq reads the same candles
    with pytest.raises(ValueError):
        Params(ipda_session="globex")


# --- B1 no_draw / L1 am_range_end ------------------------------------------------------------------

def test_no_draw_lock_time_never_past_the_current_bar(monkeypatch):
    df = day([(100.0, 100.2, 99.8, 100.0)] * 4)
    p = Params(**BASE, am=(540, 660), no_draw=True)
    ctx = ctx_for(df, history(), p)
    seen = []
    real = S.mark_levels
    monkeypatch.setattr(S, "mark_levels", lambda c, r, t, s, p_, *a, **k: seen.append(t) or real(c, r, t, s, p_, *a, **k))
    S._no_draw(ctx, p, "AM", S._idx_at(ctx, 540), None)
    S._no_draw(ctx, p, "AM", S._idx_at(ctx, 600), None)
    assert seen == [540, 570]


def test_am_range_end_validated_and_pool_from_its_end():
    with pytest.raises(ValueError):
        Params(am_range_end=840)
    with pytest.raises(ValueError):
        Params(am_range_end=570)
    rows = [(100.0, 100.2, 99.8, 100.0)] * 6 + [(100.0, 103.0, 99.9, 102.0)] + [(102.0, 102.2, 101.8, 102.0)] * 60
    df = day(rows)
    p = Params(**BASE, am_range_end=720)
    ctx = ctx_for(df, history(), p)
    sd = S.Side(1, ctx.o, ctx.h, ctx.l, ctx.c, 1)
    assert ctx.am_hl[0] == 103.0
    lv = lambda m: [v for v, _ in S._targets(ctx, sd, S._idx_at(ctx, m), 102.5, [], p, None, S._idx_at(ctx, m) - 1)]
    assert 103.0 not in lv(715) and 103.0 in lv(720)                 # from 12:00, not 13:30


# --- A2 booking tick in the lock -------------------------------------------------------------------

def test_lock_intact_uses_the_booking_tick():
    df = day([(100.0, 100.2, 99.8, 100.0)] * 2, start="09:30")
    df.iloc[60] = [100.0, 100.1, 95.75, 99.0, 1.0]                     # 05:00: 1 tick under PDL 96
    hist = history(n=8, hi=104.0, lo=96.0)
    p = Params(**BASE, draw_lock="session", sweep_ticks=2.0)
    names = lambda q: [n for _, _, n, _ in S.mark_levels(ctx_for(df, hist, q), None, 570, "AM", q)["marked"]]
    assert "pdl1" in names(p)                                          # 0.25 through < 2 ticks: intact
    assert "pdl1" not in names(replace(p, sweep_ticks=1.0))
    assert "pdl1" not in names(replace(p, sweep_ticks=0.0))            # the old rule: any print below


# --- Ep08.10 matrix "ict" in the lock ---------------------------------------------------------------

def test_matrix_ict_in_the_lock():
    hist = history(n=8, highs=[100, 100, 100, 100, 100, 110, 108, 106], lows=[90] * 8)
    df = day([(100.0, 100.2, 99.8, 100.0)] * 2)
    p = Params(**BASE, draw_lock="session")
    lk = S.mark_levels(ctx_for(df, hist, p), None, 570, "AM", p)
    assert "pdh3" in [n for _, _, n, _ in lk["marked"]]
    q = replace(p, matrix_days="ict")
    lk = S.mark_levels(ctx_for(df, hist, q), None, 570, "AM", q)
    marked = [(v, n) for v, _, n, _ in lk["marked"]]
    assert "pdh3" not in [n for _, n in marked] and (110.0, "pdh3") not in marked
    assert 108.0 in [v for v, _ in marked]                             # m3h (= pdh2 here) is marked


# --- SMT: the partner gets the new pool keys ---------------------------------------------------------

def test_smt_partner_has_the_new_pool_keys():
    n = 25
    hist = history(n=n, hi=104.0, lo=96.0)
    df = day([(100.0, 100.2, 99.8, 100.0)] * 12)
    p = Params(**BASE, ipda_pools=True, pool_today_hl=True)
    ctx, pctx = ctx_for(df, hist, p), ctx_for(df, hist, p)
    ps = {1: S.Side(1, pctx.o, pctx.h, pctx.l, pctx.c, 1), -1: S.Side(-1, pctx.o, pctx.h, pctx.l, pctx.c, 1)}
    ppos = pd.Series(np.arange(len(pctx.idx)), index=pctx.idx)
    sd = S.Side(1, ctx.o, ctx.h, ctx.l, ctx.c, 1)
    i = S._idx_at(ctx, 600)
    out = S._sell_side(pctx, ps[1], "AM", i, True, p)
    assert "ipda20" in out and "today_low" in out
    assert S._smt(ctx, sd, i, "ipda20", 96.0, "AM", pctx, ps, ppos, p) is True        # partner kept 96
    assert S._smt(ctx, sd, i, "today_low", out["today_low"], "AM", pctx, ps, ppos, p) is True
    assert S._smt(ctx, sd, i, "ipda20", 96.0, "AM", pctx, ps, ppos) is None          # the old call: no twin
    assert S._smt(ctx, sd, i, "swing_low5", 96.0, "AM", pctx, ps, ppos, p) is None


# --- A5 / A11 BPRs, A9 VI body death, A15 legacy order, L8 vacuum far edge ----------------------------

def test_bpr_c2_rule_and_untouched_targets():
    h = np.array([10, 12, 13, 11, 10, 9, 8, 9, 11, 12, 13.0]); l = h - 1.5
    o, c = h - 0.2, l + 0.2                                            # all down-closes: no bullish gap passes c2
    assert L.balanced_ranges(h, l) and L.balanced_ranges(h, l, 0, o, c, True) == []
    assert L.balanced_ranges(h, l, 0, o, c, False) == L.balanced_ranges(h, l)
    sd = S.Side(1, (h + l) / 2, h, l, (h + l) / 2, 1)
    p = Params(bpr_targets=True, es_pt=1.0)
    out = S._lv_finish_targets(SimpleNamespace(conf=None), sd, 10, 7.0, p, ())
    assert sorted(out) == [(11.0, "array"), (11.25, "array")]          # only the BPR of bar 10 is untouched


def test_vi_body_death_for_intraday_vis_and_mit_legacy_switch():
    o = np.array([10.0, 10.6, 10.7, 10.9]); c = np.array([10.5, 10.9, 10.8, 10.2])
    h = np.array([10.7, 11.0, 11.0, 11.0]); l = np.array([9.9, 10.4, 10.6, 10.1])
    sd = S.Side(1, o, h, l, c, 1)
    z = sd.vis("bull")[0]
    assert S._vi_alive(sd, z, 2) and not S._vi_alive(sd, z, 3)
    h2 = np.array([6, 5, 7, 8, 7, 6, 7.5, 9, 9.5]); l2 = np.array([5, 4, 6, 7, 6, 5, 6.5, 7.5, 9])
    o2 = np.array([5.5, 4.5, 6.2, 7.2, 6.8, 5.5, 6.6, 7.6, 9.1]); c2 = np.array([5.2, 4.8, 6.8, 7.8, 6.2, 5.8, 7.2, 8.8, 9.4])
    old = [zz for zz in L.mitigation_blocks(o2, h2, l2, c2, 1, legacy=True) if zz.kind == "bull"]
    assert S.Side(1, o2, h2, l2, c2, 1, mit_legacy=True).mitigations() == old
    assert S.Side(1, o2, h2, l2, c2, 1).mitigations() == [zz for zz in L.mitigation_blocks(o2, h2, l2, c2, 1)
                                                         if zz.kind == "bull"]
    assert "A15_legacy_order" in study.DECISIONS


def test_vacuum_far_edge_only_at_0830():
    sd = S.Side(1, np.zeros(3), np.ones(3), np.zeros(3), np.zeros(3), 1)
    ctx = SimpleNamespace(vac=[(0, 102.0, 101.5, 101.0, 585)])
    assert S._lv_target_arrays(ctx, sd, 2, Params()) == [(102.0, "array"), (101.5, "array")]
    ctx.vac = [(0, 102.0, 101.5, 101.0, 510)]
    assert S._lv_target_arrays(ctx, sd, 2, Params())[-1] == (101.0, "array")


# --- inert switch warnings, paper history, study variants -------------------------------------------

def test_inert_switch_warnings():
    with pytest.warns(UserWarning, match="vi_news_draw"):
        Params(vi_news_draw=True, vi_arrays=True, draw_lock="off")
    with pytest.warns(UserWarning, match="vi_arrays"):
        Params(vi_htf_draw=True)
    with pytest.warns(UserWarning, match="eq_pref"):
        Params(eq_pref="rank")
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        Params(vi_htf_draw=True, vi_arrays=True)                      # now a lock preference too
        Params(org_half_draw=True)


def test_paper_history_covers_hist_days():
    assert paper.history_days(5) >= (B.HIST_DAYS + 1) * 7 // 5
    assert paper.history_days(1) == paper.SCHWAB_1M_DAYS
    assert paper.short_history(30, Params(ipda_pools=True))
    assert paper.short_history(61, Params(ipda_pools=True)) is None
    assert paper.short_history(5, Params()) is None
    assert paper.short_history(10, Params(org_days=20))


def test_study_variants_for_the_review():
    d = study.DECISIONS
    for k in ("B21_ipda_session_rth", "L2_daily_needs_array_any_tf", "A13.1_breaker_ll_off",
              "Ep01.6_breaker_cand_ext", "A15_legacy_order", "L7_org_half_draw_lock", "A9_vi_htf_draw_lock",
              "B21_ipda_eq_frac_010", "B21_ipda_eq_days_20", "A5_fvg_quad_min_8", "A5_fvg_pool_gap_2",
              "B1_no_draw_adr_05", "L7_org_break_15", "L5_gap_run_tol_4", "A11_bpr_targets_any_pair",
              "A11_bpr_abort_gap12"):
        assert k in d, k
    assert d["A1_mss_ref_fallback_highest"]["ob_entry"] == "post_mss"


# --- no look-ahead, entries AND exits -----------------------------------------------------------------

ENTRY = ["entry_time", "entry", "stop", "t1", "shares", "entry_kind", "lv_tags", "fvg_state", "session"]
EXIT = ["entry_time", "exit_time", "exit_reason"]


def _no_look_ahead_x(df, tf, sym, p, cols, every=1, meta=None, lag=2, min_trades=1, **kw):
    """Cuts at entry AND exit times: the entries up to each cut, and the exits of the trades
    closed by it, must match the full run."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        full = B.run(df, tf, sym, p, meta=meta, **kw)
        assert len(full) >= min_trades, "no trades - the test window must produce some"
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
    return full


SYN = dict(es_pt=0.09, min_draw_pts=0, leg_pd=0, sloppy_mode="off", year_end="off")   # owner #3 / #10 pinned: the window keeps its trades


def test_look_ahead_bias_open_in_pre_0930_windows():
    """The review's reproduction: synthetic RW 5m 2026-04..06, pre_0900 + bias_open 0930 + use_bias,
    no lock (the 09:20 entry on 2026-04-22); then post_news + pre_0700 with the 08:30 open, and the
    lock on with a 09:00 AM window (B1 no_draw at a 09:00 session start, L1 12:00 AM range)."""
    x, y = B.synthetic(start="2026-04-01", end="2026-06-30", tf=5, seed=3)
    p = Params(**SYN, use_bias=True, bias_open="0930", pre_0900=True, draw_lock="off")
    full = _no_look_ahead_x(x, 5, "RW", p, ENTRY, every=2, partner=y)
    assert (full.session == "PRE9").any()
    p2 = replace(p, pre_0900=False, post_news=True, pre_0700=True, bias_open="0830")
    _no_look_ahead_x(x, 5, "RW", p2, ENTRY, every=2, partner=y)
    p3 = Params(**SYN, use_bias=True, bias_open="0930", am=(540, 660), no_draw=True, am_range_end=720,
                draw_lock="session", draw_lock_neutral="both")
    _no_look_ahead_x(x, 5, "RW", p3, ENTRY, every=3, partner=y)


def test_look_ahead_review_switches_synthetic():
    """The lock with the ORG far edge / half draw (breakaway re-lock), matrix "ict", booking tick 2,
    VI body death on intraday VIs (targets / stop / porous / extension), untouched BPR targets and the
    BPR abort, legacy mitigation order, release-open hold (cancel + exit), SMT on the new pool keys
    (IPDA from the ETH dict, today's pools), daily level needs an HTF array, vacuum blocks."""
    x, y = B.synthetic(start="2026-03-02", end="2026-05-29", tf=5, seed=3)
    p = Params(**SYN, org_draw="draw", org_half_draw=True, matrix_days="ict", sweep_ticks=2.0,
               vi_body_death=True, vi_targets=True, vi_stop=True, vi_porous_n=4, fvg_vi_extend=True,
               bpr_targets=True, bpr_abort=True, mit_targets=True, mit_legacy_order=True, release_open=True,
               ipda_pools=True, pool_today_hl=True, daily_level_needs_array=True, vacuum_blocks=True,
               use_bias=True, bias_open="0930", ob_entry="both", draw_lock_neutral="both")
    full = _no_look_ahead_x(x, 5, "RW", p, ENTRY + ["smt"], every=3, partner=y)
    assert full.smt.notna().any()
    q = replace(p, draw_lock="off", ob_entry="post_mss", org_break_min=15, wick_invalidate=True,
                fvg_q_hold=True, breakaway="hold")
    _no_look_ahead_x(x, 5, "RW", q, ENTRY + ["smt"], every=3, partner=y)


def _es():
    df = B.load("ES", 5, source="databento")
    return df[(df.index >= "2023-10-02") & (df.index < "2023-12-16")], B.load_meta("ES", 5)


@pytest.mark.skipif(not ES, reason="no ES data")
def test_look_ahead_es_review_switches():
    """ES 5m with confluence: the HTF VI draw and the ORG far edge / half draw as lock preferences,
    daily FVG exact (deduplicated ladder), daily level needs an HTF array, IPDA from ETH sessions,
    matrix "ict" in the lock, booking tick 2; then use_bias with the 09:30 open and a 09:00 window."""
    df, meta = _es()
    p = Params(**FUT, vi_arrays=True, vi_htf_draw=True, org_draw="draw", org_half_draw=True,
               daily_fvg_exact=True, daily_level_needs_array=True, ipda_pools=True, ipda_eq_day="tag",
               matrix_days="ict", sweep_ticks=2.0, htf_resist_cap=False, release_open=True)
    full = _no_look_ahead_x(df, 5, "ES", p, ENTRY + ["draw_px", "draw_name"], every=4, meta=meta)
    assert len(full)
    p2 = replace(p, draw_lock="off", use_bias=True, bias_open="0930", pre_0900=True, post_news=True,
                 ob_entry="both", leg_pd=0, min_draw_pts=0)
    _no_look_ahead_x(df, 5, "ES", p2, ENTRY, every=4, meta=meta)
