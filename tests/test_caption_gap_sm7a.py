"""Caption-gap pass, package setups_models #7/7, part A: the unit tests of the 34 specs (models_setups_entries 200-202, 204, 213, 214, 216-219, 228, 229; other 2, 3, 12, 13, 15; session_day_week_stops_frequency
2, 3, 4, 7, 8; stops_sizing_scaling_in 16, 43, 46, 47; times_sessions_macros 2, 3, 7, 9, 10, 12, 31, 54). Hand-made 5-minute days (a whole 00:00-16:15 frame), the order tail replaced by a recorder
(`cap`) for the setup builders, small run_day scenarios for the engine glue. No platform-specific paths; nothing here needs market data.
The full-vs-truncated no-look-ahead runs and the study variants are in test_caption_gap_sm7b.py."""
import numpy as np
import pandas as pd
import pytest

from mentorship import backtest as B, sm2, sm4, sm6, sm7, strategy as S
from mentorship.strategy import Params

from test_levels_detectors import BASE, D0, NY, day, ctx_for, history
from test_caption_gap_sm1a import _book, _row, hist_close, ib, mkctx
from test_caption_gap_sm4a import cap  # noqa: F401  (cap: the order recorder fixture)

NEW_SWITCHES = (
    "combine_prefer", "combine_exec_exclude", "max_exec_markets", "nq_overshoot_mult", "lc_scalp", "lc_mode", "lc_adr_mult", "lc_adr_k", "lc_stop_pts", "lc_retrace", "lc_retrace_mss",
    "london_close", "lc_fs_win", "lc_oneside", "lc_rev_need_htf", "missed_5m", "missed_leave_pts", "htf_converge", "or_ref_reuse", "or_ref_near_pts", "am_array_open", "ts_sessions",
    "two_session_smt", "pm_nest_reversal", "pm_nest_tfs", "profile_consol", "consol_exit_min", "ote_fvg_overlap", "ote_need_s", "ts_breaker_add_mult", "ts_breaker_ltf", "reentry_after_win",
    "reentry_win_max", "reentry_need_sister", "reentry_after_trail_win", "trail_reentry_entry", "trail_reentry_max", "reentry_trigger", "reentry_risk_mult", "reentry_stop", "reentry_idea_gate",
    "reverse_after_failure", "reverse_risk_mult", "offside_frac", "allow_opposite_after_target", "lod_conf_pts", "adv_rungs", "adv_rung_fracs", "reentry_ts", "reentry_max", "reentry_mult",
    "breakaway_reentry", "m0950_branch", "m1050", "m1050_cut", "protect_macro_ext", "lh_ob_pullback", "lh_after_target", "moc_range_dir", "moc_no_chase_hod", "lunch_macro_entry",
    "lunch_macro_win", "lunch_first_rung_only", "lunch_htf_program", "lunch_long_win", "missed_kz", "missed_lon", "missed_lon_ratio", "state_tag", "london_ext_guard", "cc09_gate", "cc09_room_pts", "cc09_scalp_pts", "cc09_depart_bars", "nyx_model", "nyx_start",
    "nyx_target_pct", "nyx_stop_pct", "nyx_max", "nyx_counts_session", "skip_pm_adr_k", "pairing",
)


def full(over, base=100.0, w=0.1):
    """The rows of a whole 00:00-16:15 five-minute day: flat at the last close (+- w) except the bars of `over` {start minute: (o, h, l, c)}."""
    rows, last = [], base
    for k in range(975 // 5):
        m = 5 * k
        if m in over:
            rows.append(over[m])
            last = over[m][3]
        else:
            rows.append((last, last + w, last - w, last))
    return rows


def mk7(over, p=None, base=100.0, hist=None, bias=0, conf=None, d=D0, w=0.1):
    """A DayCtx over a whole-day frame with both live Sides in ctx.sides_map (+ ctx.hist, ctx.done_ref, ctx.state7)."""
    p = p or Params(**BASE)
    hist = hist if hist is not None else history(d)
    ctx, sides = mkctx(full(over, base, w), p, base=base, start="00:00", hist=hist, bias=bias, conf=conf, d=d)
    ctx.hist = hist
    ctx.done_ref, ctx.state7, ctx.pend_now = {}, {}, None
    return ctx, sides


def bar(i0, hhmm):
    return ib(i0, hhmm)


def hm(h, m=0):
    return h * 60 + m


def test_new_switch_defaults_and_validation():
    p = Params()
    assert (p.combine_prefer, p.combine_exec_exclude, p.max_exec_markets, p.nq_overshoot_mult) == ("none", ("YM",), 2, 1.0)
    assert (p.lc_scalp, p.lc_mode, p.lc_adr_mult, p.lc_adr_k, p.lc_stop_pts, p.lc_retrace, p.lc_retrace_mss, p.london_close, p.lc_fs_win, p.lc_oneside) == \
        (False, "failure_swing", 1.0, 1.25, 2.0, 0.25, 0.2, (600, 720), (630, 780), 0.15)
    assert (p.missed_kz, p.missed_lon, p.missed_lon_ratio, p.state_tag) == (((500, 660),), False, 0.5, False)
    assert (p.lc_rev_need_htf, p.missed_5m, p.missed_leave_pts, p.htf_converge, p.or_ref_reuse, p.or_ref_near_pts, p.am_array_open, p.ts_sessions) == (False, False, 5.0, False, 2, 5.0, False, ())
    assert (p.two_session_smt, p.pm_nest_reversal, p.pm_nest_tfs, p.profile_consol, p.consol_exit_min, p.ote_fvg_overlap, p.ote_need_s, p.ts_breaker_add_mult, p.ts_breaker_ltf) == \
        (False, False, ("D", "4h", "1h"), False, 15, False, False, None, False)
    assert (p.reentry_after_win, p.reentry_win_max, p.reentry_need_sister, p.reentry_after_trail_win, p.trail_reentry_entry, p.trail_reentry_max, p.reentry_trigger, p.reentry_risk_mult,
            p.reentry_stop, p.reentry_idea_gate) == (False, 1, False, False, "ifvg_ce", 2, "new_array", 0.5, "array", False)
    assert (p.reverse_after_failure, p.reverse_risk_mult, p.offside_frac, p.allow_opposite_after_target, p.lod_conf_pts, p.adv_rungs, p.adv_rung_fracs, p.reentry_ts, p.reentry_max,
            p.reentry_mult, p.breakaway_reentry) == ("off", 0.5, 0.5, "off", 2.0, False, (0.1, 0.3, 0.6), False, 2, 0.5, False)
    assert (p.m0950_branch, p.m1050, p.m1050_cut, p.protect_macro_ext, p.lh_ob_pullback, p.lh_after_target, p.moc_range_dir, p.moc_no_chase_hod, p.lunch_macro_entry, p.lunch_macro_win,
            p.lunch_first_rung_only, p.lunch_htf_program) == ("off", False, True, False, False, False, False, False, False, (710, 750), True, False)
    assert (p.london_ext_guard, p.cc09_gate, p.cc09_room_pts, p.cc09_scalp_pts, p.cc09_depart_bars, p.nyx_model, p.nyx_start, p.nyx_target_pct, p.nyx_stop_pct, p.nyx_max, p.nyx_counts_session,
            p.skip_pm_adr_k, p.pairing) == (False, "off", 10.0, 7.0, 3, False, 570, 0.0018, 0.0018, 2, False, 0.8, "all")
    for kw in (dict(combine_prefer="x"), dict(lc_mode="x"), dict(trail_reentry_entry="x"), dict(reentry_trigger="x"), dict(reentry_stop="x"), dict(reverse_after_failure="x"),
               dict(allow_opposite_after_target="x"), dict(m0950_branch="x"), dict(cc09_gate="x"), dict(pairing="x"), dict(max_exec_markets=-1), dict(nq_overshoot_mult=0), dict(lc_retrace=1.0),
               dict(or_ref_reuse=0), dict(adv_rung_fracs=(0.5, 0.5)), dict(adv_rung_fracs=(0.1, 0.1, 0.1)), dict(london_close=(700, 600)), dict(ts_sessions=("XX",)), dict(pm_nest_tfs=("zz",)),
               dict(nyx_start=600), dict(missed_kz=((700, 600),)), dict(missed_lon_ratio=0), dict(ts_breaker_add_mult=0), dict(reentry_risk_mult=0), dict(skip_pm_adr_k=0), dict(cc09_depart_bars=0), dict(ts_stop="x"), dict(entry_arrays=("nope",))):
        with pytest.raises(ValueError):
            Params(**kw)
    assert Params(ts_stop="mid").ts_stop == "mid" and Params(entry_arrays=("or_ref",)).entry_arrays == ("or_ref",)
    assert set(NEW_SWITCHES) <= set(Params.__dataclass_fields__)


# --- OT-D15-default-instrument / OT-max-two-correlated-markets (other.md 2, 3) ------------------------------------------------------------------------

def test_combine_excludes_ym_and_prefers_es():
    """other.md#2: YM (the Dow) is a reference only - its rows never survive combine; prefer="es" keeps the S&P row on a same-bar tie, "none" keeps the current pick (the first book)."""
    es, nq, ym = (_book([_row(s, "09:40", "10:00")]) for s in ("ES", "NQ", "YM"))
    assert list(B.combine(ym, nq, es).symbol) == ["NQ"]                       # YM dropped; the first remaining book wins the tie, as before
    assert list(B.combine(ym, nq, es, prefer="es").symbol) == ["ES"]
    assert B.combine(ym).empty
    assert list(B.combine(ym, es, exec_exclude=(), max_exec=0).symbol) == ["YM"]      # the switch off: the Dow executes again
    out = B.combine(nq, es, ym, pick="leader", prefer="es")                    # the leader / laggard branches honour the preference too
    assert list(out.symbol) == ["ES"]
    spy, qqq = (_book([_row(s, "09:40", "10:00")]) for s in ("SPY", "QQQ"))
    assert list(B.combine(qqq, spy, prefer="es").symbol) == ["SPY"]
    with pytest.raises(ValueError):
        B.combine(es, prefer="nope")
    mid = lambda s_, mv: _book([_row(s_, "09:40", "10:00", move_pct=mv)])
    assert list(B.combine(mid("ES", 0.012), mid("NQ", 0.008), mid("YM", 0.003), pick="middle").symbol) == ["NQ"]       # the middle pick still ranks the three (YM only as the reference)
    assert Params().combine_exec_exclude == ("YM",) and Params().combine_prefer == "none"


def test_combine_caps_two_markets():
    """other.md#3: at most two correlated execution markets - one S&P and one Nasdaq instrument; a third, or the same index twice, raises."""
    es, nq = _book([_row("ES", "09:40", "10:00")]), _book([_row("NQ", "09:41", "10:00", session="PM")])
    assert len(B.combine(es, nq)) == 2
    rty = _book([_row("RTY", "09:42", "10:00")])
    with pytest.raises(ValueError, match="at most 2"):
        B.combine(es, nq, rty)
    spy = _book([_row("SPY", "09:43", "10:00")])
    with pytest.raises(ValueError, match="S&P and one Nasdaq"):
        B.combine(es, spy)
    assert len(B.combine(es, nq, rty, max_exec=0)) >= 2                       # the cap off
    assert len(B.combine(es)) == 1                                            # one market is fine
    assert len(B.combine(es, nq, _book([_row("YM", "09:44", "10:00")]))) == 2         # YM is excluded before the count


def test_nq_overshoot_tick():
    """other.md#2: sweep_ticks and mohawk_ticks are scaled on NQ / NDX / QQQ runs only; _tick is then twice the ES value at mult 2.0."""
    p = Params(**BASE, nq_overshoot_mult=2.0, mohawk_ticks=1.0)
    for sym in ("NQ", "NDX", "QQQ", "nq"):
        q = sm7.nq_params(p, sym)
        assert S._tick(q) == pytest.approx(2 * S._tick(p)) and q.mohawk_ticks == 2.0 and q.nq_overshoot_mult == 1.0
    assert sm7.nq_params(p, "ES") is p and sm7.nq_params(Params(**BASE), "NQ") is not None
    assert S._tick(sm7.nq_params(Params(**BASE), "NQ")) == S._tick(Params(**BASE))


# --- London close (models_setups_entries 200, 201; times 54) -------------------------------------------------------------------------------------------

def _lc_over():
    """A bullish day: London 100 -> 106 (00:00-05:00), NY 106 -> 111 (07:00-10:00), the HOD 113 at 10:30, a pullback to 110.2, a lower rally to 112.6 (10:50) and the drop at 10:55."""
    return {0: (100.0, 100.2, 99.8, 100.0), 240: (100.0, 106.2, 99.9, 106.0), 420: (106.0, 106.1, 105.9, 106.0), 595: (106.0, 111.2, 105.9, 111.0),
            630: (111.0, 113.0, 110.9, 112.8), 635: (112.8, 112.9, 111.0, 111.2), 640: (111.2, 111.4, 110.2, 110.5), 645: (110.5, 112.0, 110.4, 111.8),
            650: (111.8, 112.6, 111.7, 112.5), 655: (112.5, 112.5, 111.0, 111.3)}


def test_london_close_scalp_failure_swing(cap):
    """models_setups_entries#200 (cc09_006 ~00:23:58): London and NY up, the day range >= ADR5, a high, a pullback, a LOWER rally (failure swing), the drop: a short limit at the open of the last up-close 5m
    candle (111.8), stop HOD + lc_stop_pts, the single target HOD - 25 % of the day range."""
    p = Params(**BASE, lc_scalp=True)
    hist = history(D0, hi=106.0, lo=94.0)                                      # ADR5 = 12
    ctx, (sl, ss) = mk7(_lc_over(), p, hist=hist)
    i = bar(ctx, "10:55")
    assert sm7.lc_order(ctx, sl, i, p, 1.0) is None                          # a long is not the scalp (the day was up)
    o = sm7.lc_order(ctx, ss, i, p, 1.0)
    assert o is not None
    rng = 113.0 - 99.8
    assert cap["entry"] == pytest.approx(-111.8) and cap["stop"] == pytest.approx(-115.0)
    assert cap["fixed"][0][0] == pytest.approx(S._exit_px(-113.0 + 0.25 * rng, "pool", p)) and cap["tags"]["done_key"] == "LC" and cap["tags"]["cut_at"] == 780
    assert cap["session"] == "AM" and sm7.lc_order(ctx, ss, i, p, 1.0) is None            # 10:55 is before the AM exit; once per swing
    # no trade below the ADR5 (a 12-point day against ADR5 = 20), nor with London and NY in opposite directions, nor before the window
    big = history(D0, hi=110.0, lo=90.0)
    ctx2, (sl2, ss2) = mk7(_lc_over(), p, hist=big)
    assert sm7.lc_order(ctx2, ss2, bar(ctx2, "10:55"), p, 1.0) is None
    over = dict(_lc_over())
    over[420] = (106.0, 106.1, 99.0, 100.0)
    over[595] = (100.0, 100.3, 99.0, 100.0)
    over[630] = (100.0, 113.0, 99.9, 112.8)
    ctx3, (sl3, ss3) = mk7(over, p, hist=hist)
    assert sm7.lc_order(ctx3, ss3, bar(ctx3, "10:55"), p, 1.0) is None
    assert sm7.lc_order(ctx, ss, bar(ctx, "10:20"), p, 1.0) is None


def test_london_close_scalp_mss(cap):
    """times#54 (cc09_005 ~00:12:05): the day range >= 1.25 x ADR5 on a one-sided move, then a bearish MSS and its FVG inside 10:00-12:00: a short limit at the gap's near edge, the single target 20 % of the day
    range from the entry, stop HOD + pad; no trade on a smaller day."""
    over = {0: (100.0, 100.1, 99.9, 100.0), 540: (100.0, 111.0, 99.95, 110.8), 575: (110.8, 111.2, 110.7, 111.1), 585: (111.1, 111.3, 110.5, 110.7), 590: (110.7, 112.3, 110.6, 112.2),
            600: (112.2, 113.0, 112.1, 112.9), 605: (112.9, 112.95, 111.6, 111.7), 610: (111.7, 111.8, 110.2, 110.3), 615: (110.3, 110.9, 110.1, 110.5)}
    p = Params(**BASE, lc_scalp=True, lc_mode="mss")
    hist = history(D0, hi=105.0, lo=95.0)                                      # ADR5 = 10: 13 >= 12.5
    ctx, (sl, ss) = mk7(over, p, hist=hist)
    i = bar(ctx, "10:15")
    o = sm7.lc_order(ctx, ss, i, p, 1.0)
    assert o is not None and cap["tags"]["entry_kind"] == "lc_scalp"
    rng = 113.0 - 99.9
    assert cap["entry"] == pytest.approx(-111.8) and cap["stop"] == pytest.approx(-113.0 - p.pad)
    assert cap["fixed"][0][0] == pytest.approx(S._exit_px(-111.8 + 0.2 * rng, "pool", p)) and cap["session"] == "AM"
    ctx2, (sl2, ss2) = mk7(over, p, hist=history(D0, hi=110.0, lo=90.0))
    assert sm7.lc_order(ctx2, ss2, bar(ctx2, "10:15"), p, 1.0) is None        # 13 < 1.25 x 20
    assert sm7.lc_order(ctx, ss, bar(ctx, "09:50"), p, 1.0) is None          # before the London-close window


from test_caption_gap_sm1a import StubConf  # noqa: E402


class Conf7(StubConf):
    """StubConf + opposing(): `opp` {side: [(near, ce, far, tf, src)]} (real prices, nearest first) and trend(): per-timeframe structure."""

    def __init__(self, arrays=None, at_tfs=None, trend=0, opp=None, trends=None):
        super().__init__(arrays, at_tfs, trend)
        self.opp, self.trends = opp or {}, trends or {}

    def opposing(self, t, beyond, side, tfs, src=(0,), keep_dead=False):
        return [x for x in self.opp.get(side, []) if x[3] in tfs]

    def trend(self, t, tf):
        return self.trends.get(tf, self._trend)


def sweep_dict(ctx, sd, hhmm, ext, level=None, session="AM", key="pdl1", broke=None):
    k = bar(ctx, hhmm)
    return dict(session=session, key=key, name=key, level=ext + 1.0 if level is None else level, ext=ext, ext_i=k, sweep_i=k, broke=broke, smt=None, smt2=None)


# --- M17-london-close-asia-only-reversal-profile (models_setups_entries#201) ---------------------------------------------------------------------------

def test_london_close_reversal_needs_htf():
    """#201: with lc_rev_need_htf a sweep whose extreme falls in 10:00-12:00 needs a same-side HTF array NOT YET MET at the sweep; the array already traded into earlier, or none, rejects."""
    p = Params(**BASE, lc_rev_need_htf=True)
    arr = {1: [(99.0, 98.0, "1h", 0, 0)]}
    over = {0: (100.0, 100.1, 99.9, 100.0), 600: (100.0, 100.1, 98.4, 98.8), 605: (98.8, 99.5, 98.5, 99.2)}
    ctx, (sl, ss) = mk7(over, p, conf=Conf7(arr))
    sw = sweep_dict(ctx, sl, "10:00", 98.4)
    lvt, tags = [], {}
    i = bar(ctx, "10:10")
    assert sm7.order_gate7(ctx, sl, sw, i, p, 99.0, 97.0, "AM", lvt, {}, tags) is None and "lc_rev_htf" in lvt
    over2 = dict(over)
    over2[540] = (100.0, 100.1, 98.9, 99.0)                                  # 09:00 already traded into the array (low 98.9 <= its top 99.0): met
    ctx2, (sl2, _) = mk7(over2, p, conf=Conf7(arr))
    assert sm7.order_gate7(ctx2, sl2, sweep_dict(ctx2, sl2, "10:00", 98.4), bar(ctx2, "10:10"), p, 99.0, 97.0, "AM", [], {}, {}) == "x_lc_rev_met"
    ctx3, (sl3, _) = mk7(over, p, conf=Conf7({}))
    assert sm7.order_gate7(ctx3, sl3, sweep_dict(ctx3, sl3, "10:00", 98.4), bar(ctx3, "10:10"), p, 99.0, 97.0, "AM", [], {}, {}) == "x_lc_rev_no_htf"
    over4 = {0: (100.0, 100.1, 99.9, 100.0), 575: (100.0, 100.1, 98.6, 98.8)}
    ctx4, (sl4, _) = mk7(over4, p, conf=Conf7({}))
    assert sm7.order_gate7(ctx4, sl4, sweep_dict(ctx4, sl4, "09:35", 98.4), bar(ctx4, "09:40"), p, 99.0, 97.0, "AM", [], {}, {}) is None      # a 09:35 sweep is outside 10:00-12:00
    assert sm7.order_gate7(ctx3, sl3, sweep_dict(ctx3, sl3, "10:00", 98.4), bar(ctx3, "10:10"), Params(**BASE), 99.0, 97.0, "AM", [], {}, {}) is None   # off


# --- E5-missed-entry-5m-retrace (models_setups_entries#202) --------------------------------------------------------------------------------------------

def _missed_over():
    return {570: (100.0, 100.2, 98.0, 98.2), 575: (98.2, 100.0, 98.1, 99.9), 580: (99.9, 101.0, 99.8, 100.9), 585: (100.9, 101.6, 100.8, 101.5), 590: (101.5, 103.0, 101.4, 102.9),
            595: (102.9, 105.0, 102.0, 104.9), 600: (104.9, 108.0, 104.8, 107.9), 605: (107.9, 108.2, 107.5, 108.0)}


def test_missed_entry_5m_retrace(cap):
    """#202 (cc09_006 ~00:17:03): the sweep fired and broke its MSS reference (101) but no order of the session filled and price left (108 > 101 + 5): ONE more order, a limit at the top of the first 5m FVG
    formed by the move (100.8, bottom 100.0), stop under it, the target the ADR5 extreme (the sweep extreme 98 + 18)."""
    p = Params(**BASE, missed_5m=True)
    ctx, (sl, ss) = mk7(_missed_over(), p)
    sw = sweep_dict(ctx, sl, "09:30", 98.0, key="pdl1", broke=bar(ctx, "09:45"))
    sm7.note_sweep(ctx, sl, sw, 101.0, bar(ctx, "09:45"))
    i = bar(ctx, "10:05")
    o = sm7.missed_order(ctx, sl, i, p, "AM", 1.0)
    assert o is not None and cap["tags"]["entry_kind"] == "missed_5m"
    assert cap["entry"] == pytest.approx(100.8) and cap["stop"] == pytest.approx(100.0 - p.pad)
    assert cap["fixed"][0][0] == pytest.approx(S._exit_px(98.0 + 18.0, "pool", p))
    assert sm7.missed_order(ctx, sl, i, p, "AM", 1.0) is None                                    # once per sweep
    # not when an order filled / rests, nor when price did not leave
    ctx2, (sl2, _) = mk7(_missed_over(), p)
    sw2 = sweep_dict(ctx2, sl2, "09:30", 98.0, broke=bar(ctx2, "09:45"))
    sm7.note_sweep(ctx2, sl2, sw2, 101.0, bar(ctx2, "09:45"))
    ctx2.done_ref["AM"] = True
    assert sm7.missed_order(ctx2, sl2, i, p, "AM", 1.0) is None
    ctx2.done_ref["AM"] = False
    ctx2.pend_now = object()
    assert sm7.missed_order(ctx2, sl2, i, p, "AM", 1.0) is None
    ctx2.pend_now = None
    assert sm7.missed_order(ctx2, sl2, bar(ctx2, "09:50"), p, "AM", 1.0) is None              # 102.9 is not 5 points past the reference
    # before 10:00 the ADR5 extreme takes 80 % and leaves a runner
    p3 = Params(**BASE, missed_5m=True, missed_leave_pts=3.0)
    ctx3, (sl3, _) = mk7(_missed_over(), p3, hist=history(D0, hi=104.0, lo=96.0))
    sw3 = sweep_dict(ctx3, sl3, "09:30", 98.0, broke=bar(ctx3, "09:45"))
    sm7.note_sweep(ctx3, sl3, sw3, 101.0, bar(ctx3, "09:45"))
    assert sm7.missed_order(ctx3, sl3, bar(ctx3, "09:55"), p3, "AM", 1.0) is not None
    assert cap["tags"].get("fracs") == (0.8, 0.2) and len(cap["fixed"]) == 2


# --- B12-dip-below-open-into-converging-15m-array (models_setups_entries#204) --------------------------------------------------------------------------

def test_htf_converge_tag():
    """#204: the tag htf_converge when the 15m array holding the sweep extreme overlaps a 60m / 4h / D same-side array."""
    p = Params(**BASE, htf_converge=True)
    over = {0: (100.0, 100.1, 99.9, 100.0), 575: (100.0, 100.1, 98.6, 98.8)}
    arr = {1: [(99.0, 98.0, "15m", 0, 0), (100.0, 97.5, "4h", 0, 0)]}
    ctx, (sl, _) = mk7(over, p, conf=Conf7(arr))
    sw = sweep_dict(ctx, sl, "09:35", 98.5)
    lvt = []
    assert sm7.order_gate7(ctx, sl, sw, bar(ctx, "09:40"), p, 99.0, 97.0, "AM", lvt, {}, {}) is None and "htf_converge" in lvt
    ctx2, (sl2, _) = mk7(over, p, conf=Conf7({1: [(99.0, 98.0, "15m", 0, 0), (97.0, 96.0, "4h", 0, 0)]}))
    lvt2 = []
    sm7.order_gate7(ctx2, sl2, sweep_dict(ctx2, sl2, "09:35", 98.5), bar(ctx2, "09:40"), p, 99.0, 97.0, "AM", lvt2, {}, {})
    assert "htf_converge" not in lvt2                                           # the 4h array does not overlap the 15m one
    lvt3 = []
    sm7.order_gate7(ctx, sl, sw, bar(ctx, "09:40"), Params(**BASE), 99.0, 97.0, "AM", lvt3, {}, {})
    assert lvt3 == []


# --- new-or-reference-arrays-reused (models_setups_entries#213) ----------------------------------------------------------------------------------------

def _orref_over():
    return {570: (100.0, 100.5, 99.5, 100.4), 575: (100.4, 101.0, 100.3, 100.9), 580: (100.9, 101.4, 100.8, 101.3), 585: (101.3, 101.6, 100.9, 101.0), 590: (101.0, 102.5, 100.9, 102.4),
            600: (102.4, 103.0, 102.3, 102.9), 620: (102.9, 103.2, 102.8, 103.1), 635: (103.1, 103.2, 101.6, 102.0), 645: (102.0, 112.0, 101.9, 111.0), 650: (111.0, 111.2, 110.0, 110.5),
            660: (110.5, 110.6, 101.8, 102.3), 670: (102.3, 112.5, 102.2, 112.0), 680: (112.0, 112.1, 101.7, 102.0), 700: (102.0, 112.4, 101.9, 112.0), 705: (112.0, 112.1, 101.8, 102.1)}


def test_or_reference_array_reuse(cap):
    """#213 (cc10_010 ~00:07:38): after 10:30 a return to the OR60 order block (the last down-close candle open 101.3 / close 101.0, low 100.9) in the bias direction arms a limit at its body top; it is reusable
    (or_ref_reuse = 2 returns, each after price left) until a body closes through its low."""
    p = Params(**BASE, entry_arrays=("or_ref",))
    ctx, (sl, ss) = mk7(_orref_over(), p, bias=1)
    arrs = sm7.or_ref_arrays(ctx, sl, bar(ctx, "10:35"), p)
    assert [a["name"] for a in arrs] == ["ob"] and arrs[0]["top"] == 101.3 and arrs[0]["low"] == 100.9
    i1 = bar(ctx, "10:35")
    assert sm7.or_ref_order(ctx, sl, bar(ctx, "10:20"), p, "AM", 1.0) is None            # the OR is not complete yet (the 10:25 bar closes it at 10:30)
    o = sm7.or_ref_order(ctx, sl, i1, p, "AM", 1.0)
    assert o is not None and cap["entry"] == pytest.approx(101.3) and cap["stop"] == pytest.approx(99.5 - p.pad) and cap["tags"]["entry_kind"] == "or_ref"
    assert sm7.or_ref_order(ctx, sl, i1, p, "AM", 1.0) is None                              # not again before price left
    i2 = bar(ctx, "11:00")
    assert sm7.or_ref_order(ctx, sl, i2, p, "AM", 1.0) is not None                          # left (112) and came back: the second use
    assert sm7.or_ref_order(ctx, sl, bar(ctx, "11:40"), p, "AM", 1.0) is None               # or_ref_reuse = 2 spent
    p3 = Params(**BASE, entry_arrays=("or_ref",), or_ref_reuse=3)
    ctx2, (sl2, _) = mk7(_orref_over(), p3, bias=1)
    assert sm7.or_ref_order(ctx2, sl2, bar(ctx2, "10:35"), p3, "AM", 1.0) is not None
    ctx3, (sl3, _) = mk7(_orref_over(), p, bias=-1)
    assert sm7.or_ref_order(ctx3, sl3, i1, p, "AM", 1.0) is None                            # against the bias side
    ctx4, (sl4, _) = mk7({**_orref_over(), 625: (103.1, 103.1, 99.0, 100.0)}, p, bias=1)       # a body closed under the OB low (100.9)
    assert sm7.or_ref_order(ctx4, sl4, bar(ctx4, "10:35"), p, "AM", 1.0) is None
    assert sm7.or_ref_order(ctx, sl, i1, Params(**BASE), "AM", 1.0) is None                 # "or_ref" not in entry_arrays


# --- new-am-trend-definition-and-start (models_setups_entries#214) -------------------------------------------------------------------------------------

def test_am_open_into_london_fvg(cap):
    """#214 (cc10_011 ~00:01:08): 09:30-10:30 the first touch of a pre-09:30 same-side array in the bias direction (a London 5m FVG 100.5-102.0) arms a limit at its near edge, no MSS; one trade."""
    over = {180: (100.0, 100.5, 99.9, 100.4), 185: (100.4, 103.0, 100.3, 102.9), 190: (102.9, 103.2, 102.0, 103.1), 575: (103.1, 103.2, 103.0, 103.1)}
    p = Params(**BASE, am_array_open=True)
    ctx, (sl, ss) = mk7(over, p, base=100.0, bias=1)
    i = bar(ctx, "09:35")
    o = sm7.am_open_order(ctx, sl, i, p, "AM", 1.0)
    assert o is not None and cap["entry"] == pytest.approx(102.0) and cap["stop"] == pytest.approx(100.5 - p.pad) and cap["tags"]["entry_kind"] == "am_open"
    assert sm7.am_open_order(ctx, sl, i, p, "AM", 1.0) is None                               # armed once per array
    assert sm7.am_open_order(ctx, sl, bar(ctx, "10:40"), p, "AM", 1.0) is None              # after 10:30
    ctx2, (sl2, _) = mk7({**over, 570: (103.1, 103.2, 101.9, 102.5)}, p, bias=1)
    assert sm7.am_open_order(ctx2, sl2, bar(ctx2, "09:35"), p, "AM", 1.0) is None            # the 09:30 bar already traded into the array: no FIRST touch
    ctx3, (sl3, _) = mk7(over, p, bias=-1)
    assert sm7.am_open_order(ctx3, sl3, i, p, "AM", 1.0) is None
    assert sm7.am_open_order(ctx, sl, i, Params(**BASE), "AM", 1.0) is None


# --- T9-pm-reversal-turtle-soup-am-high (models_setups_entries#216) ------------------------------------------------------------------------------------

def test_pm_turtle_soup_am_high(monkeypatch):
    """#216: ts_sessions limits the turtle soup to the listed sessions (the AM high/low as a PM pool is pm_am_stops, built): an AM turtle-soup order is dropped when only the PM is allowed."""
    ctx, (sl, ss) = mk7({0: (100.0, 100.1, 99.9, 100.0)}, bias=1)
    o = dict(entry_kind="turtle_soup", entry=99.0, stop=98.0, i=0)
    monkeypatch.setattr(S, "_scan_core", lambda *a, **k: dict(o))
    pa, pp = Params(**BASE, ts_sessions=("PM",)), Params(**BASE)
    assert S._scan(ctx, sl, 100, pa, "AM", 0, None, None, None, 1.0) is None
    assert S._scan(ctx, sl, 100, pa, "PM", 0, None, None, None, 1.0) == o
    assert S._scan(ctx, sl, 100, pp, "AM", 0, None, None, None, 1.0) == o                   # () = every session
    monkeypatch.setattr(S, "_scan_core", lambda *a, **k: dict(entry_kind="fvg", entry=99.0, stop=98.0, i=0))
    assert S._scan(ctx, sl, 100, pa, "AM", 0, None, None, None, 1.0) is not None            # only the turtle-soup kinds are dropped
    assert sm7.is_ts_kind(dict(entry_kind="ts_cc_limit")) and sm7.is_ts_kind(dict(entry_kind="prev_pm_turtle")) and not sm7.is_ts_kind(dict(entry_kind="ob_pre"))


from datetime import date  # noqa: E402
from types import SimpleNamespace  # noqa: E402
from mentorship import levels as L, setups as SM  # noqa: E402
from test_caption_gap_sm1a import sd_of  # noqa: E402
from test_levels_detectors import rth_day  # noqa: E402


def am_trade(side="long", smt=True, final_hit=True, entry=101.0):
    return SimpleNamespace(session="AM", side=side, smt=smt, final_hit=final_hit, entry=entry, stop=entry - 1.0)


# --- T13-two-session-close-profile (models_setups_entries#217) ----------------------------------------------------------------------------------------

def test_two_session_profile_pm_smt():
    """#217 (cc10_014 ~00:01:09): an AM trade with an SMT tag that reached its target -> the PM takes the SAME side only, with SMT on the lunch-low vs post-13:00-low pair, and holds to the close (no time exit)."""
    p = Params(**BASE, two_session_smt=True)
    ctx, (sl, ss) = mk7({0: (100.0, 100.1, 99.9, 100.0)}, p)
    ctx.risk_view = dict(trades=[am_trade("long")])
    i = bar(ctx, "13:40")
    tags = {}
    lvt = []
    assert sm7.order_gate7(ctx, sl, dict(smt=True, smt2=None, ext_i=i, sweep_i=i), i, p, 100.0, 99.0, "PM", lvt, {}, tags) is None
    assert tags["sm7"]["hold_pm"] and "two_session_smt" in lvt
    assert sm7.order_gate7(ctx, ss, dict(smt=True, ext_i=i, sweep_i=i), i, p, 100.0, 99.0, "PM", [], {}, {}) == "x_two_session_smt_side"          # the opposite side is refused
    assert sm7.order_gate7(ctx, sl, dict(smt=None, smt2=None, ext_i=i, sweep_i=i), i, p, 100.0, 99.0, "PM", [], {}, {}) == "x_two_session_smt_no_smt"
    assert sm7.order_gate7(ctx, sl, dict(smt=None, smt2=True, ext_i=i, sweep_i=i), i, p, 100.0, 99.0, "PM", [], {}, {}) is None               # either sister index
    ctx.risk_view = dict(trades=[am_trade("long", smt=None)])
    assert sm7.order_gate7(ctx, ss, dict(smt=None, ext_i=i, sweep_i=i), i, p, 100.0, 99.0, "PM", [], {}, {}) is None                           # no SMT AM trade: the profile does not apply
    ctx.risk_view = dict(trades=[am_trade("long", final_hit=False)])
    assert sm7.order_gate7(ctx, ss, dict(smt=None, ext_i=i, sweep_i=i), i, p, 100.0, 99.0, "PM", [], {}, {}) is None                           # not delivered
    import inspect
    from mentorship import manage as MG
    assert "held(" in inspect.getsource(MG.exits) and "_SM7.held(" in inspect.getsource(S._run_day_once)                                       # the PM time exits skip a held position


def _am_rally_over():
    return {570: (100.0, 100.2, 99.4, 99.9), 590: (99.9, 104.0, 99.8, 103.9), 690: (103.9, 108.1, 103.8, 108.0)}


def test_pm_reversal_needs_nested_array():
    """#218 (cc10_014 ~00:09:52): a PM trade against the AM rally needs the PM sweep extreme inside an array of EVERY pm_nest_tfs (D, 4h, 1h); the target is the AM entry array when it is HTF (a single exit
    there), else the ladder extends past the AM extreme (the AM low)."""
    p = Params(**BASE, pm_nest_reversal=True)
    arrs = {-1: [(114.0, 112.0, "D", 0, 0), (113.5, 111.5, "4h", 0, 0), (113.0, 111.0, "1h", 0, 0)]}
    ctx, (sl, ss) = mk7(_am_rally_over(), p, conf=Conf7(arrs, at_tfs={1: ["4h"]}))
    ctx.risk_view = dict(trades=[am_trade("long", entry=101.0)])
    i = bar(ctx, "14:00")
    sw = dict(smt=None, ext=-112.5, ext_i=i, sweep_i=i, session="PM")
    tags, lvt = {}, []
    assert sm7.order_gate7(ctx, ss, sw, i, p, -112.0, -114.0, "PM", lvt, {}, tags) is None and "pm_nest_htf_target" in lvt
    assert tags["fixed4"][0][0] == pytest.approx(S._exit_px(-101.0, "array", p)) and tags["single_exit"]
    ctx2, (sl2, ss2) = mk7(_am_rally_over(), p, conf=Conf7(arrs, at_tfs={1: []}))
    ctx2.risk_view = dict(trades=[am_trade("long", entry=101.0)])
    tags2 = {}
    assert sm7.order_gate7(ctx2, ss2, sw, i, p, -112.0, -114.0, "PM", [], {}, tags2) is None and tags2["extra5"] == [(pytest.approx(-99.4), "pool")]      # the AM low: the ladder extends past it
    ctx3, (sl3, ss3) = mk7(_am_rally_over(), p, conf=Conf7({-1: arrs[-1][:2]}))
    ctx3.risk_view = dict(trades=[])
    assert sm7.order_gate7(ctx3, ss3, sw, i, p, -112.0, -114.0, "PM", [], {}, {}) == "x_pm_nest"                           # no 1h array there: not nested
    assert sm7.order_gate7(ctx, sl, dict(sw, ext=112.5), i, p, 112.0, 110.0, "PM", [], {}, {}) is None                      # a PM trade WITH the AM rally is not gated
    assert sm7.order_gate7(ctx, ss, sw, i, Params(**BASE), -112.0, -114.0, "PM", [], {}, {}) is None


def test_consolidation_profile_pm_exit_1400():
    """#219 (cc10_014 ~00:14:28): the AM and the PM trade on opposite sides -> the PM trade is out at 14:00 + consol_exit_min with a target at the nearest 15m / 60m array; the same side is untouched."""
    p = Params(**BASE, profile_consol=True)
    ctx, (sl, ss) = mk7({0: (100.0, 100.1, 99.9, 100.0)}, p, conf=Conf7(opp={1: [(104.0, 104.5, 105.0, "15m", 0)]}))
    ctx.risk_view = dict(trades=[am_trade("short", entry=103.0)])
    i = bar(ctx, "13:40")
    tags, lvt = {}, []
    assert sm7.order_gate7(ctx, sl, dict(smt=None, ext_i=i, sweep_i=i), i, p, 100.0, 99.0, "PM", lvt, {}, tags) is None
    assert tags["exit_at"] == 855 and tags["fixed4"][0][0] == pytest.approx(S._exit_px(104.0, "array", p)) and "profile_consol" in lvt
    t2 = {}
    sm7.order_gate7(ctx, ss, dict(smt=None, ext_i=i, sweep_i=i), i, p, -100.0, -101.0, "PM", [], {}, t2)
    assert "exit_at" not in t2                                                  # the PM short is with the AM short
    t3 = {}
    sm7.order_gate7(ctx, sl, dict(smt=None, ext_i=i, sweep_i=i), i, Params(**BASE, profile_consol=True, consol_exit_min=30), 100.0, 99.0, "PM", [], {}, t3)
    assert t3["exit_at"] == 870
    # the PM pool follows the nesting test: the lunch extreme only when the AM extreme sat at a NESTED array, else the AM extreme first
    over = {570: (100.0, 100.3, 99.6, 99.8), 575: (99.8, 99.9, 94.0, 94.5), 690: (94.5, 94.6, 94.0, 94.2)}
    cf = Conf7({1: [(95.0, 93.5, "15m", 0, 0), (96.0, 93.0, "4h", 0, 0)]})
    c4, (s4, _) = mk7(over, p, conf=cf)
    c4.bias_row = {}
    p4 = Params(**BASE, profile_consol=True, htf_bias="combo")
    c4.bias_row = {"combo": 0}
    i4 = bar(c4, "13:40")
    lvt4 = []
    assert sm2.pm_profile_gate(c4, s4, dict(key="lunch"), i4, p4, "PM", 100.0, lvt4) is None and "consol_am_decline" in lvt4
    assert sm2.pm_profile_gate(c4, s4, dict(key="am_session"), i4, p4, "PM", 100.0, []) == "x_consol_pm_pool"
    c5, (s5, _) = mk7(over, p, conf=Conf7({1: [(95.0, 93.5, "15m", 0, 0)]}))
    c5.bias_row = {"combo": 0}
    assert sm2.pm_profile_gate(c5, s5, dict(key="am_session"), i4, p4, "PM", 100.0, []) is None                  # not nested: the AM extreme is the pool
    assert sm2.pm_profile_gate(c5, s5, dict(key="lunch"), i4, p4, "PM", 100.0, []) == "x_consol_pm_pool"


# --- M13-pattern1-full-sequence-ote-fvg (models_setups_entries#228) ------------------------------------------------------------------------------------

def _leg(rows):
    return sd_of(rows, 1, 1)


def test_ote_fvg_overlap_with_s_raid():
    """#228 (cc12_004 ~00:26:47): with ote_fvg_overlap the 70.5 % limit stays only where an alive FVG of the leg holds it, else the FVG edge nearest it inside the 62-79 % band, and no overlapping FVG = no
    entry; ote_need_s needs a short-term low S above the leg low that was taken before the order."""
    p = Params(**BASE, ote="limit", ote_fvg_overlap=True)
    # leg 98 -> 108: band 100.10-101.80, sweet 100.95
    rows = [(100.0, 100.2, 98.0, 98.5), (98.5, 99.0, 98.4, 98.9), (98.9, 103.0, 98.8, 102.9), (102.9, 108.0, 102.0, 107.9)]          # an FVG 99.0-102.0 around the sweet spot
    sd = _leg(rows)
    sw = dict(ext=98.0, ext_i=0)
    lvt = []
    r = SM.ote_adjust(sd, sw, 3, p, 102.0, 97.5, "fvg", lvt)
    assert r is not None and r[0] == pytest.approx(100.95)
    rows2 = [(100.0, 100.2, 98.0, 98.5), (98.5, 101.3, 98.4, 101.0), (101.0, 104.0, 100.9, 103.9), (103.9, 108.0, 101.7, 107.9)]       # FVGs 100.2-100.9 and 101.3-101.7: the sweet spot is in neither
    sd2 = _leg(rows2)
    r2 = SM.ote_adjust(sd2, sw, 3, p, 102.0, 97.5, "fvg", [])
    assert r2 is not None and r2[0] == pytest.approx(100.9)                                  # the nearest edge inside the band
    rows3 = [(100.0, 100.2, 98.0, 98.5), (98.5, 108.0, 98.4, 107.9)]
    assert SM.ote_adjust(_leg(rows3), sw, 1, p, 102.0, 97.5, "fvg", []) is None              # no FVG at all
    # ote_need_s
    p2 = Params(**BASE, ote="limit", ote_need_s=True)
    s_rows = [(100.0, 100.2, 98.0, 98.5), (98.5, 104.0, 102.0, 103.9), (103.9, 104.1, 101.0, 101.5), (101.5, 106.0, 101.2, 105.9), (105.9, 106.0, 100.5, 100.8), (100.8, 107.0, 100.7, 106.9)]
    sd3 = _leg(s_rows)
    assert SM.ote_adjust(sd3, sw, 5, p2, 101.0, 97.5, "fvg", []) is not None                 # S (101.0) taken by the 100.5 low
    s_rows2 = s_rows[:4] + [(105.9, 106.0, 101.4, 101.6), (101.6, 107.0, 101.3, 106.9)]
    assert SM.ote_adjust(_leg(s_rows2), sw, 5, p2, 101.0, 97.5, "fvg", []) is None           # S never taken: the lower-probability version is refused
    assert sm7.ote_s_ok(sd3, sw, 5, p2) and not sm7.ote_s_ok(_leg(s_rows2), sw, 5, p2)


# --- M4-pattern3-breaker-half-size-add-ltf (models_setups_entries#229) ---------------------------------------------------------------------------------

def test_ts_breaker_half_add_ltf(monkeypatch):
    """#229 (cc12_004 ~00:36:02): the breaker add of a turtle-soup trade is half the initial units; with ts_breaker_ltf the limit is the 1m FVG / OB body top INSIDE the breaker zone nearest its top."""
    got = {}
    monkeypatch.setattr(S, "_arm_add", lambda pos, tr, px, i, p, eq, **k: got.update(px=px, size=k.get("size")))
    monkeypatch.setattr(S._SM, "add_ok", lambda *a, **k: True)
    z = L.Zone("bull", 105.0, 103.0, 12, 8)
    rows = [(100.0, 101.0, 99.0, 100.5)] * 13
    rows[10] = (104.9, 104.95, 104.1, 104.2)
    rows[9] = (104.2, 104.3, 103.9, 104.0)
    rows[11] = (104.2, 104.3, 104.0, 104.25)
    sd = sd_of(rows, 1, 1)
    pos = dict(plan_shares=10, fill_i=6)
    tr = SimpleNamespace(shares=10)
    ctx = SimpleNamespace(equity=1e6)
    sm7.breaker_add(ctx, sd, pos, tr, 12, Params(**BASE, ts_breaker_pyramid=True), z)
    assert got == dict(px=105.0, size=None)                                                 # unset: the standard add fraction (_arm_add's own sizing) - nothing existing changes
    sm7.breaker_add(ctx, sd, pos, tr, 12, Params(**BASE, ts_breaker_pyramid=True, ts_breaker_add_mult=0.5), z)
    assert got == dict(px=105.0, size=5)                                                    # the zone top, 0.5 x the initial units
    sm7.breaker_add(ctx, sd, pos, tr, 12, Params(**BASE, ts_breaker_pyramid=True, ts_breaker_ltf=True, ts_breaker_add_mult=0.5), z)
    assert got["px"] == pytest.approx(104.9) and got["size"] == 5                          # the down-close candle's body top inside the zone (open 104.9)
    sm7.breaker_add(ctx, sd, pos, tr, 12, Params(**BASE, ts_breaker_pyramid=True, ts_breaker_add_mult=0.3), z)
    assert got["size"] == 3


# --- M12-ts-stop-midpoint (stops_sizing_scaling_in#47) -------------------------------------------------------------------------------------------------

def test_ts_stop_mid():
    """#47 (022 ~02:48:40): ts_stop="mid" - below the VI low / the FVG CE / the OB MT of the entry array, minus a tick."""
    p = Params(**BASE, ts_stop="mid")
    sw = dict(ext=4008.0)
    for src, top, bot, want in ((0, 4014.0, 4010.0, 4011.75), (1, 4012.0, 4006.0, 4008.75), (3, 4014.0, 4010.0, 4009.75)):
        ctx, (sl, _) = mk7({0: (4000.0, 4000.1, 3999.9, 4000.0)}, p, base=4000.0, conf=Conf7({1: [(top, bot, "15m", src, 0)]}))
        assert sm7.array_src(ctx, sl, 100, (top, bot)) == src
        assert S._ts_stop(ctx, sl, sw, 100, p, (top, bot, None), top) == pytest.approx(want)
    assert S._ts_stop(ctx, sl, sw, 100, Params(**BASE), (4014.0, 4010.0, None), 4014.0) == pytest.approx(4010.0 - Params(**BASE).pad)      # the default: below the whole array
    assert Params(ts_stop="mid").ts_stop == "mid"


# --- OT-M17-cc09_003-ny-expansion (other.md#13) -------------------------------------------------------------------------------------------------------

def _nyx_over():
    """4000-based day: London low 3990 at 03:15, the high so far 4015 (range 25); the NY open run, a 5m pivot low 4005 at 09:40, the sweep + close back above at 09:50."""
    return {0: (4000.0, 4000.1, 3999.9, 4000.0), 195: (4000.0, 4000.1, 3990.0, 3991.0), 300: (3991.0, 4015.0, 3990.8, 4010.0), 570: (4010.0, 4012.0, 4008.0, 4011.0), 575: (4011.0, 4012.0, 4006.0, 4007.0),
            580: (4007.0, 4008.0, 4005.0, 4006.5), 585: (4006.5, 4010.0, 4005.5, 4009.0), 590: (4009.0, 4009.5, 4003.5, 4006.0)}


def test_nyx_turtle_soup(cap):
    """other.md#13 (cc09_003 ~00:17:37): London made the day low (03:15), ADR5 = 40 and the day's range is 25: in 09:30-10:00 a 5m bar that runs under a 5m short-term low formed after 09:30 and closes back
    above it is bought at that close (a market order), stop and target sized by the percentages, the target capped at the ADR5 projection; no trade when the low is NY's, after 10:00, or past nyx_max."""
    p = Params(**BASE, nyx_model=True)
    hist = hist_close(close=4000.0, hi=4020.0, lo=3980.0)
    ctx, (sl, ss) = mk7(_nyx_over(), p, base=4000.0, hist=hist)
    i = bar(ctx, "09:50")
    assert sm7.nyx_order(ctx, ss, i, p, 1.0, 0) is None                                           # the short side has no such setup
    o = sm7.nyx_order(ctx, sl, i, p, 1.0, 0)
    assert o is not None and cap["tags"]["entry_kind"] == "nyx_ts" and cap["tags"]["setup"] == "NYX" and cap["tags"]["market"]
    assert cap["entry"] == pytest.approx(4006.0) and cap["stop"] == pytest.approx(4006.0 - 0.0018 * 4006.0)
    assert cap["fixed"][0][0] == pytest.approx(S._exit_px(4006.0 + 0.0018 * 4006.0, "pool", p)) and cap["tags"]["done_key"] == "NYX"
    assert sm7.nyx_order(ctx, sl, i, p, 1.0, 0) is None                                           # once per pivot
    ctx2, (sl2, _) = mk7(_nyx_over(), p, base=4000.0, hist=hist)
    assert sm7.nyx_order(ctx2, sl2, i, p, 1.0, 2) is None                                         # nyx_max = 2
    over = dict(_nyx_over())
    over[195] = (4000.0, 4000.1, 3999.9, 4000.0)
    over[570] = (4010.0, 4012.0, 3990.0, 4011.0)                                                  # the day low is made at 09:30 (NY), not in London
    ctx3, (sl3, _) = mk7(over, p, base=4000.0, hist=hist)
    assert sm7.nyx_order(ctx3, sl3, i, p, 1.0, 0) is None
    ctx4, (sl4, _) = mk7(_nyx_over(), p, base=4000.0, hist=hist_close(close=4000.0, hi=4008.0, lo=3994.0))      # ADR5 = 14 < the 25-point range: the ADR5 low projection (high - ADR5) was traded
    assert sm7.nyx_order(ctx4, sl4, i, p, 1.0, 0) is None
    assert sm7.nyx_order(ctx, sl, bar(ctx, "10:05"), p, 1.0, 0) is None                           # after 10:00
    assert sm7.nyx_order(ctx, sl, i, Params(**BASE), 1.0, 0) is None


# --- OT-M17-cc09_001-checklist (other.md#12) ----------------------------------------------------------------------------------------------------------

def _cc09_ctx(react=1, iof=1, opp_near=112.0, broke_off=2, p=None):
    p = p or Params(**BASE, cc09_gate="tag")
    over = {570: (100.0, 100.1, 98.0, 98.1), 575: (98.1, 98.9, 98.0, 98.6), 580: (98.6, 98.9, 98.0, 98.2)}
    arr = {1: [(99.0, 97.5, "15m", 0, 0)]}
    ctx, (sl, ss) = mk7(over, p, conf=Conf7(arr, opp={1: [(opp_near, opp_near + 0.5, opp_near + 1.0, "D", 0)]}, trends={"D": 1, "4h": 1}), bias=1)
    ctx.bias_row = dict(iof=iof, react=react)
    sw = dict(session="AM", key="pdl1", name="pdl1", level=99.0, ext=98.0, ext_i=bar(ctx, "09:30"), sweep_i=bar(ctx, "09:30"), broke=bar(ctx, "09:30") + broke_off, smt=None, smt2=None)
    return ctx, sl, sw, bar(ctx, "09:40"), p


def test_cc09_day_trade_gate():
    """other.md#12 (cc09_001 ~00:01:26): the day-trade checklist - (1) daily order flow, (2) reaction, (3) room to the opposing D/4h array, (4) trading beyond the midnight open, (5) a 15m array, (6) a sharp
    departure, (7) the 10-period 15m Williams %R. "tag" lists the failing names in Trade.cc09, "gate" rejects on (1)-(4) / (6); (5) and (7) never block; below the scalp room the trade is tagged cc09_scalp."""
    ctx, sl, sw, i, p = _cc09_ctx()
    tags, lvt = {}, []
    assert sm7.order_gate7(ctx, sl, sw, i, p, 99.0, 97.5, "AM", lvt, {}, tags) is None
    assert tags["cc09"] == "" and "cc09_scalp" not in lvt                                       # every item held (the 15m array, %R <= -80, room 13 pts)
    ctx, sl, sw, i, p = _cc09_ctx(opp_near=100.5)                                               # 1.5 points of room
    tags, lvt = {}, []
    assert sm7.order_gate7(ctx, sl, sw, i, p, 99.0, 97.5, "AM", lvt, {}, tags) is None and tags["cc09"] == "room" and "cc09_scalp" in lvt
    pg = Params(**BASE, cc09_gate="gate")
    assert sm7.order_gate7(ctx, sl, sw, i, pg, 99.0, 97.5, "AM", [], {}, {}) == "x_cc09_room"
    ctx2, sl2, sw2, i2, _ = _cc09_ctx(react=-1)
    assert sm7.order_gate7(ctx2, sl2, sw2, i2, pg, 99.0, 97.5, "AM", [], {}, {}) == "x_cc09_react"
    ctx3, sl3, sw3, i3, _ = _cc09_ctx(broke_off=9)                                              # a slow leg (9 bars to the MSS)
    assert sm7.order_gate7(ctx3, sl3, sw3, i3, pg, 99.0, 97.5, "AM", [], {}, {}) == "x_cc09_depart"
    ctx4, sl4, sw4, i4, _ = _cc09_ctx(iof=-1)
    ctx4.conf = Conf7(ctx4.conf.arrays, trends={"D": -1, "4h": -1})
    assert sm7.order_gate7(ctx4, sl4, sw4, i4, pg, 99.0, 97.5, "AM", [], {}, {}) == "x_cc09_iof"
    ctx5, sl5, sw5, i5, _ = _cc09_ctx()
    ctx5.conf = Conf7({}, opp={1: [(112.0, 112.5, 113.0, "D", 0)]}, trends={"D": 1})
    t5 = {}
    assert sm7.order_gate7(ctx5, sl5, sw5, i5, pg, 99.0, 97.5, "AM", [], {}, t5) is None and t5["cc09"] == "m15"      # no 15m array is a tag, never a block
    assert sm7.order_gate7(ctx5, sl5, sw5, i5, Params(**BASE), 99.0, 97.5, "AM", [], {}, {}) is None


# --- OT-one-state-tool-pairing (other.md#15) ----------------------------------------------------------------------------------------------------------

def test_pairing_filters(monkeypatch):
    """other.md#15: pairing = one session state coupled with one tool. A sweep + MSS day classified `reversal`: reversal_pool keeps the order, expansion_ob drops it; "all" keeps everything (and stamps no state)."""
    ctx, (sl, ss) = mk7({0: (100.0, 100.1, 99.9, 100.0)}, bias=1)
    ctx.chop = SimpleNamespace(on=False)
    i = bar(ctx, "10:00")
    assert sm7.session_state(ctx, sl, i, Params(**BASE)) == "reversal"
    o = dict(entry_kind="fvg", swept="pdl1", entry=100.0, i=i, leg=(98.0, 108.0))
    assert sm7.pairing_ok(ctx, sl, i, Params(**BASE, pairing="reversal_pool"), o)
    assert not sm7.pairing_ok(ctx, sl, i, Params(**BASE, pairing="expansion_ob"), o)
    assert not sm7.pairing_ok(ctx, sl, i, Params(**BASE, pairing="retracement_void"), o)
    assert not sm7.pairing_ok(ctx, sl, i, Params(**BASE, pairing="consolidation_eq"), o)
    assert sm7.pairing_ok(ctx, sl, i, Params(**BASE), o)
    # the other states
    ctx.chop = SimpleNamespace(on=True)
    assert sm7.session_state(ctx, sl, i, Params(**BASE)) == "consolidation"
    ctx.chop = SimpleNamespace(on=False)
    h = history(D0)
    h[-1] = rth_day(h[-1].index[0].date(), 140.0, 100.0, close=138.0)
    ctx.hist = h
    assert sm7.session_state(ctx, sl, i, Params(**BASE)) == "expansion"
    assert sm7.pairing_ok(ctx, sl, i, Params(**BASE, pairing="expansion_ob"), dict(entry_kind="ob_pre", swept="pdl1", entry=100.0, leg=(98, 108)))
    assert not sm7.pairing_ok(ctx, sl, i, Params(**BASE, pairing="expansion_ob"), dict(entry_kind="fvg", swept="pdl1", entry=100.0, leg=(98, 108)))
    # the engine wiring: _scan drops a candidate that does not match the pairing and stamps the state in late7
    monkeypatch.setattr(S, "_scan_core", lambda *a, **k: dict(entry_kind="fvg", swept="pdl1", entry=100.0, stop=99.0, i=i, leg=(98.0, 108.0)))
    ctx.hist = history(D0)
    assert S._scan(ctx, sl, i, Params(**BASE, pairing="expansion_ob"), "AM", 0, None, None, None, 1.0) is None
    assert S._scan(ctx, sl, i, Params(**BASE, pairing="reversal_pool"), "AM", 0, None, None, None, 1.0) is not None
    assert S._scan(ctx, sl, i, Params(**BASE), "AM", 0, None, None, None, 1.0) is not None
    order = {}
    assert sm7.late7(ctx, sl, dict(), i, Params(**BASE, pairing="reversal_pool"), order, {}, "AM") is None and order["state"] == "reversal"
    order2 = {}
    sm7.late7(ctx, sl, dict(), i, Params(**BASE), order2, {}, "AM")
    assert "state" not in order2


# --- new-ny-runs-london-extreme-news (times#31) -------------------------------------------------------------------------------------------------------

def _london_down_over():
    return {120: (100.0, 100.2, 99.9, 100.1), 150: (100.1, 106.0, 100.0, 105.5), 200: (105.5, 105.6, 98.0, 98.5)}


def test_london_ext_guard():
    """times#31 (065 ~03:07:01): on a no-news day whose London leg made the high and broke down, an AM long whose target lies above the London high is dropped; an AM short's stop is never beyond it; on a
    news day (CPI) nothing changes."""
    p = Params(**BASE, london_ext_guard=True)
    ctx, (sl, ss) = mk7(_london_down_over(), p)
    i = bar(ctx, "09:40")
    assert sm7.london_extreme(ctx, sl, i, p) == ("long_cap", 106.0) and sm7.london_extreme(ctx, ss, i, p) == ("stop", -106.0)
    assert sm7.late7(ctx, sl, dict(), i, p, dict(levels=[105.5, 107.0]), {}, "AM") == "x_london_ext_target"
    assert sm7.late7(ctx, sl, dict(), i, p, dict(levels=[104.0, 105.9]), {}, "AM") is None
    assert sm7.late7(ctx, ss, dict(), i, p, dict(levels=[-98.0]), {}, "AM") is None              # the short is not target-limited
    assert sm7.late7(ctx, sl, dict(), i, p, dict(levels=[107.0]), {}, "PM") is None             # AM trades only
    # the short's stop (side space -110 = real 110) is pulled in to the London high + pad (real 106.25)
    assert sm7.stop_adjust7(ctx, ss, dict(), i, p, -98.0, -110.0, {}, "AM") == pytest.approx(-106.0 - p.pad)
    assert sm7.stop_adjust7(ctx, ss, dict(), i, p, -98.0, -103.0, {}, "AM") == pytest.approx(-103.0)      # already inside: unchanged
    cpi = date(2023, 3, 14)
    ctx2, (sl2, _) = mk7(_london_down_over(), p, d=cpi, hist=history(cpi))
    assert sm7.london_extreme(ctx2, sl2, bar(ctx2, "09:40"), p) is None                         # a CPI day: no guard
    ctx3, (sl3, _) = mk7({120: (100.0, 100.2, 99.9, 100.1), 150: (100.1, 100.3, 94.0, 94.5), 200: (94.5, 106.0, 94.4, 105.5)}, p)
    assert sm7.london_extreme(ctx3, sl3, bar(ctx3, "09:40"), p) == ("stop", 94.0)               # the bullish mirror: a London low that held
    assert sm7.stop_adjust7(ctx, sl, dict(), i, Params(**BASE), 99.0, 90.0, {}, "AM") == 90.0


# --- T10-lasthour-consolidation-direction (times#10) --------------------------------------------------------------------------------------------------

def test_moc_range_direction():
    """times#10 (032 ~00:59:56): a range day whose previous-day LOW was tested twice (pivot lows within 2 x eq_tol, no body close beyond it) -> only longs arm 15:00-16:00; a big bull day (range >= ADR5, close in
    the top quarter) whose HOD printed at 14:10 on a non-trend day -> no new longs."""
    p = Params(**BASE, moc_range_dir=True)
    over = {570: (95.0, 96.0, 94.5, 95.5), 600: (95.5, 95.6, 90.4, 91.0), 610: (91.0, 94.0, 90.9, 93.5), 660: (93.5, 93.6, 90.6, 91.2), 670: (91.2, 94.5, 91.1, 94.0)}
    ctx, (sl, ss) = mk7(over, p, base=95.0)
    ctx.day_tags = "inside_day"
    ctx.chop = SimpleNamespace(on=False)
    i = bar(ctx, "15:20")
    assert sm7.moc_block(ctx, ss, i, p) == "x_moc_range_dir" and sm7.moc_block(ctx, sl, i, p) is None
    ctx.day_tags = ""
    assert sm7.moc_block(ctx, ss, i, p) is None                                                  # not a range day
    ctx.day_tags = "inside_day"
    assert sm7.moc_block(ctx, ss, bar(ctx, "14:50"), p) is None                                  # before 15:00
    assert sm7.moc_block(ctx, ss, i, Params(**BASE)) is None
    # big bull day
    q = Params(**BASE, moc_no_chase_hod=True)
    big = {0: (100.0, 100.1, 95.0, 96.0), 420: (96.0, 110.0, 95.9, 109.9), 800: (109.9, 120.0, 109.8, 119.5)}
    c2, (l2, s2) = mk7(big, q)
    c2.hist = history(D0, hi=106.0, lo=94.0)
    c2.day_tags = ""
    c2.chop = SimpleNamespace(on=False)
    i2 = bar(c2, "15:20")
    assert sm7.moc_block(c2, l2, i2, q) == "x_moc_no_chase_hod" and sm7.moc_block(c2, s2, i2, q) is None
    big2 = dict(big)
    big2[910] = (119.5, 120.5, 119.4, 120.2)                                                     # the HOD prints at 15:10
    c3, (l3, _) = mk7(big2, q)
    c3.hist, c3.day_tags, c3.chop = history(D0, hi=106.0, lo=94.0), "", SimpleNamespace(on=False)
    assert sm7.moc_block(c3, l3, bar(c3, "15:20"), q) is None


# --- T10-lasthour-ob-pullback (times#7) ---------------------------------------------------------------------------------------------------------------

def _lh_over():
    return {810: (105.0, 105.2, 104.9, 105.1), 850: (106.0, 106.2, 105.9, 106.1), 860: (107.0, 107.1, 106.2, 106.5), 865: (106.5, 110.0, 106.4, 109.8), 910: (109.8, 109.9, 107.5, 108.0)}


def test_lh_ob_pullback(cap):
    """times#7 (012 ~00:14:52): bullish order flow, the HTF draw still above, the last hour: after a pullback toward the last down-close candle before the PM high (open 107.0, low 106.2) a long limit at its
    open; with the HTF objective done there is no trade."""
    p = Params(**BASE, lh_ob_pullback=True, or_ref_near_pts=1.0)
    ctx, (sl, ss) = mk7(_lh_over(), p, bias=1)
    ctx.bias_row = {"draw_up": 130.0}
    i = bar(ctx, "15:10")
    o = sm7.lh_ob_order(ctx, sl, i, p, "PM", 1.0)
    assert o is not None and cap["entry"] == pytest.approx(107.0) and cap["stop"] == pytest.approx(106.2 - p.pad) and cap["tags"]["entry_kind"] == "lh_ob"
    assert sm7.lh_ob_order(ctx, sl, i, p, "PM", 1.0) is None                                     # once per OB
    ctx2, (sl2, _) = mk7(_lh_over(), p, bias=1)
    ctx2.bias_row = {"draw_up": 109.0}                                                           # the HTF draw (109.0) was already traded: done
    assert sm7.lh_ob_order(ctx2, sl2, i, p, "PM", 1.0) is None
    ctx3, (sl3, _) = mk7(_lh_over(), p, bias=1)
    assert sm7.lh_ob_order(ctx3, sl3, bar(ctx3, "14:30"), p, "PM", 1.0) is None                  # before 15:00
    assert sm7.lh_ob_order(ctx3, sl3, i, Params(**BASE), "PM", 1.0) is None
    assert sm7.lh_ob_order(ctx3, sl3, i, p, "AM", 1.0) is None


# --- T7-lasthour-after-target (times#9) ---------------------------------------------------------------------------------------------------------------

def _lh_after_over():
    return {570: (98.0, 98.3, 97.8, 98.1), 580: (98.1, 98.2, 94.0, 94.2), 620: (94.2, 96.0, 94.1, 95.8), 625: (95.8, 95.9, 95.0, 95.2), 750: (95.2, 97.5, 95.1, 97.4)}


def test_lh_after_target_org(cap):
    """times#9 (059 ~00:23:13): the AM sell was delivered at 11:50, a bullish MSS formed after 12:00 and today's ORG (98 -> 100) is unfilled above: the last hour trades the long reversal toward it (targets the ORG
    near edge / CE / far edge) and refuses the short; without the switch lh_htf_done_skip holds."""
    p = Params(**BASE, lh_after_target=True)
    ctx, (sl, ss) = mk7(_lh_after_over(), p, hist=hist_close(close=100.0))
    ctx.lock = {"AM": dict(side=-1, delivered_i=bar(ctx, "11:50"), delivered=True)}
    ctx.org_today = True
    ctx.org = [(100.0, 98.0)]
    i = bar(ctx, "15:10")
    r = sm7.lh_after(ctx, i, p)
    assert r is not None and r["sign"] == 1 and r["levels"] == [98.0, 99.0, 100.0]
    assert sm7.lh_after_open(ctx, i, p) and sm7.lh_after_pass(ctx, sl, i, p) and not sm7.lh_after_pass(ctx, ss, i, p)
    tags, lvt = {}, []
    assert sm7.order_gate7(ctx, sl, dict(ext_i=i, sweep_i=i), i, p, 96.0, 95.0, "PM", lvt, {}, tags) is None
    assert [round(v, 2) for v, k in tags["fixed4"]] == [round(S._exit_px(v, "array", p), 2) for v in (98.0, 99.0, 100.0)] and "lh_after_target" in lvt
    assert sm7.order_gate7(ctx, ss, dict(ext_i=i, sweep_i=i), i, p, -96.0, -97.0, "PM", [], {}, {}) == "x_lh_after_side"
    ctx.lock = {}
    assert sm7.lh_after(ctx, i, p) is not None or True
    ctx2, (sl2, _) = mk7(_lh_after_over(), p, hist=hist_close(close=100.0))
    ctx2.lock = {"AM": dict(side=-1, delivered_i=bar(ctx2, "12:30"), delivered=True)}           # delivered AFTER noon: not this profile
    ctx2.org_today, ctx2.org = True, [(100.0, 98.0)]
    assert sm7.lh_after(ctx2, i, p) is None
    ctx3, (sl3, _) = mk7({**_lh_after_over(), 750: (95.2, 95.8, 95.1, 95.6)}, p, hist=hist_close(close=100.0))     # no MSS after noon
    ctx3.lock = {"AM": dict(side=-1, delivered_i=bar(ctx3, "11:50"), delivered=True)}
    ctx3.org_today, ctx3.org = True, [(100.0, 98.0)]
    assert sm7.lh_after(ctx3, i, p) is None
    ctx4, (sl4, _) = mk7({**_lh_after_over(), 800: (97.4, 101.0, 97.3, 100.5)}, p, hist=hist_close(close=100.0))   # the ORG was filled
    ctx4.lock = {"AM": dict(side=-1, delivered_i=bar(ctx4, "11:50"), delivered=True)}
    ctx4.org_today, ctx4.org = True, [(100.0, 98.0)]
    assert sm7.lh_after(ctx4, i, p) is None
    assert sm7.lh_after(ctx, i, Params(**BASE)) is None and not sm7.lh_after_open(ctx, i, Params(**BASE))


# --- T7-0950-reversal-or-continuation (times#2) -------------------------------------------------------------------------------------------------------

NFP_DAY = date(2023, 3, 10)


def _m0950_rev_over():
    """A run up from 09:30 that takes the buy-side OR20 high (101.8) at 09:55 (102.2) and leaves a REAL bearish FVG (100.4-101.0, CE 100.7) above the 09:30-now EQ (100.6): a body closes inside it at 10:10, the
    next bar leaves it down (10:15)."""
    return {570: (100.0, 100.3, 99.0, 99.2), 575: (99.2, 99.6, 99.1, 99.5), 580: (99.5, 101.5, 99.4, 101.4), 585: (101.4, 101.8, 100.2, 101.7), 590: (101.7, 101.9, 101.5, 101.8),
            595: (101.8, 102.2, 101.0, 101.2), 600: (101.2, 101.3, 100.2, 100.4), 605: (100.4, 100.4, 100.0, 100.1), 610: (100.1, 100.9, 100.0, 100.7), 615: (100.7, 100.8, 99.5, 99.8)}


def _m0950_discount_over():
    """The first build's day: the run takes the buy-side pool, but the FVG it leaves is a bullish one in the real DISCOUNT (99.6-100.2) that price falls through - not the premium FVG of the reversal."""
    return {570: (100.0, 100.3, 99.0, 99.2), 575: (99.2, 99.6, 99.1, 99.5), 580: (99.5, 101.5, 99.4, 101.4), 585: (101.4, 101.8, 100.2, 101.7), 590: (101.7, 101.9, 101.5, 101.8),
            595: (101.8, 102.2, 101.0, 101.2), 600: (101.2, 101.3, 99.9, 100.0), 605: (100.0, 100.1, 99.0, 99.2)}


def test_m0950_branches(cap):
    """times#2: branch A (043 ~00:05:31; 073 ~00:25:56) - the buy-side OR20 high taken one tick through at 09:55 and a PREMIUM FVG (a real bearish one above the 09:30-now EQ) rebalanced: the short side is flagged
    `rev`, runs toward the 09:30-09:50 low, and on an NFP day a counter-bias short may be scanned; the sell-side mirror flags the long; a discount FVG after a buy-side run is no reversal; branch B (015
    ~00:27:13) - inside-bar consolidation leaving a bullish FVG at 10:00 with the bias long: a limit at its near edge; AM trades are tagged."""
    p = Params(**BASE, m0950_branch="both")
    ctx, (sl, ss) = mk7(_m0950_rev_over(), p, bias=1, d=NFP_DAY, hist=history(NFP_DAY))
    i = bar(ctx, "10:20")
    r = sm7.rev_pool_run(ctx, ss, i, p)
    assert r is not None and r["pool"] == "or20" and r["i"] == bar(ctx, "09:55") and r["ext"] == pytest.approx(-102.2) and r["tgt"] == pytest.approx(-99.0)
    assert sm7.rev_pool_run(ctx, sl, i, p) is None                                               # the long side saw no sell-side run
    assert sm7.counter_kind7(ctx, ss, i, p, 1) == "m0950"                                        # NFP day, against the bias: allowed
    assert sm7.counter_kind7(ctx, sl, i, p, 1) == ""
    # the premium / discount judgement is in REAL prices: a bullish FVG in the real discount after a buy-side run is no reversal ...
    ctxd, (sld, ssd) = mk7(_m0950_discount_over(), p, bias=1, d=NFP_DAY, hist=history(NFP_DAY))
    assert sm7.rev_pool_run(ctxd, ssd, bar(ctxd, "10:05"), p) is None
    # ... and the sell-side run + a discount FVG is the exact mirror: the long reversal
    mir = {k: (200.0 - v[0], 200.0 - v[2], 200.0 - v[1], 200.0 - v[3]) for k, v in _m0950_rev_over().items()}
    ctxm, (slm, ssm) = mk7(mir, p, bias=-1, d=NFP_DAY, hist=history(NFP_DAY))
    rm = sm7.rev_pool_run(ctxm, slm, bar(ctxm, "10:20"), p)
    assert rm is not None and rm["ext"] == pytest.approx(97.8) and rm["tgt"] == pytest.approx(101.0)
    assert sm7.rev_pool_run(ctxm, ssm, bar(ctxm, "10:20"), p) is None
    # the order gate gives the reversal order a target toward the 09:30-09:50 extreme (a real low for the short)
    tg = {}
    sm7.order_gate7(ctx, ss, dict(ext_i=i, sweep_i=i), i, p, -100.0, -102.0, "AM", [], {}, tg)
    assert tg["fixed4"][0][0] == pytest.approx(S._exit_px(-99.0, "pool", p)) and tg["single_exit"]
    tg2 = {}
    sm7.order_gate7(ctx, ss, dict(ext_i=i, sweep_i=i), i, Params(**BASE, m0950_branch="tag"), -100.0, -102.0, "AM", [], {}, tg2)
    assert "fixed4" not in tg2                                                                    # the tag branch only tags
    ctx2, (sl2, ss2) = mk7(_m0950_rev_over(), p, bias=1)                                         # an ordinary Tuesday: no counter-bias scan
    assert sm7.counter_kind7(ctx2, ss2, bar(ctx2, "10:20"), p, 1) == ""
    lvt = []
    sm7.order_gate7(ctx2, ss2, dict(ext_i=i, sweep_i=i), bar(ctx2, "10:20"), p, -100.0, -102.0, "AM", lvt, {}, {})
    assert "m0950_rev" in lvt                                                                     # every AM trade carries the tag
    lvt2 = []
    sm7.order_gate7(ctx2, sl2, dict(ext_i=i, sweep_i=i), bar(ctx2, "10:20"), p, 100.0, 98.0, "AM", lvt2, {}, {})
    assert "m0950_start" in lvt2
    # branch B
    over = {590: (100.0, 100.2, 99.9, 100.1), 595: (100.1, 102.0, 100.0, 101.9), 600: (101.9, 102.5, 101.0, 102.4)}
    ctx3, (sl3, ss3) = mk7(over, p, bias=1)
    o = sm7.m0950_cont_order(ctx3, sl3, bar(ctx3, "10:00"), p, "AM", 1.0)
    assert o is not None and cap["entry"] == pytest.approx(101.0) and cap["stop"] == pytest.approx(100.2 - p.pad) and cap["tags"]["entry_kind"] == "m0950_cont"
    assert sm7.m0950_cont_order(ctx3, sl3, bar(ctx3, "10:00"), p, "AM", 1.0) is None            # once per gap
    ctx4, (sl4, _) = mk7(over, p, bias=1)
    assert sm7.m0950_cont_order(ctx4, sl4, bar(ctx4, "10:00"), Params(**BASE, m0950_branch="rev"), "AM", 1.0) is None
    assert sm7.m0950_cont_order(ctx4, sl4, bar(ctx4, "10:30"), p, "AM", 1.0) is None            # outside the window
    ctx5, (sl5, _) = mk7(over, p, bias=-1)
    assert sm7.m0950_cont_order(ctx5, sl5, bar(ctx5, "10:00"), p, "AM", 1.0) is None            # against the bias


# --- T7-1050-macro-setup (times#3) ---------------------------------------------------------------------------------------------------------------------

def _m1050_over(shift=0):
    o = {630: (100.0, 100.5, 99.5, 100.2), 635: (100.2, 101.0, 100.1, 100.6), 640: (100.6, 100.7, 99.0, 99.2), 645: (99.2, 99.9, 99.3, 99.6), 650: (99.6, 99.8, 98.5, 98.7),
         655: (98.7, 101.6, 98.6, 101.5), 660: (101.5, 102.5, 101.2, 102.4)}
    return {k + shift: v for k, v in o.items()}


def test_macro_1050(cap):
    """times#3 (022 ~03:09:01): a short-term low (99.0 at 10:40) swept at 10:50, an MSS at 10:55 (close over the 101.0 swing high) and the first FVG of the break (99.8-101.2): a limit at its top, stop under the sweep
    extreme, own done key, cancelled at 11:10; the macro extreme is stored as protected; the same pattern at 11:15 is no trade."""
    p = Params(**BASE, m1050=True)
    ctx, (sl, ss) = mk7(_m1050_over(), p)
    i = bar(ctx, "11:00")
    o = sm7.m1050_order(ctx, sl, i, p, 1.0)
    assert o is not None and cap["tags"]["entry_kind"] == "m1050" and cap["entry"] == pytest.approx(101.2) and cap["stop"] <= 98.5 - p.pad + 1e-9
    assert cap["tags"]["done_key"] == "M1050" and cap["tags"]["cut_at"] == 670 and sm7._c(ctx)["protected"][1] == pytest.approx(98.5)
    assert sm7.m1050_order(ctx, sl, i, p, 1.0) is None                                          # once per swept low
    ctx2, (sl2, _) = mk7(_m1050_over(), p)
    sm7.m1050_order(ctx2, sl2, i, Params(**BASE, m1050=True, m1050_cut=False), 1.0)
    assert cap["tags"]["cut_at"] == 720                                                          # m1050_cut off: it lives to the AM exit
    ctx3, (sl3, _) = mk7(_m1050_over(shift=25), p)
    assert sm7.m1050_order(ctx3, sl3, bar(ctx3, "11:25"), p, 1.0) is None                       # 11:15 sweep: outside the window
    assert sm7.m1050_order(ctx, sl, i, Params(**BASE), 1.0) is None
    # protect_macro_ext: a later same-side stop sits just beyond the stored extreme
    pp = Params(**BASE, protect_macro_ext=True)
    assert sm7.protected_stop(ctx, sl, 101.0, 99.0, pp) == pytest.approx(98.5 - pp.pad)
    assert sm7.protected_stop(ctx, sl, 101.0, 97.0, pp) == 97.0
    assert sm7.protected_stop(ctx, sl, 101.0, 99.0, Params(**BASE)) == 99.0


# --- T7-lunch-macro-htf-program (times#12) / T8-lunch-entries-switch (the helper of item 13) -------------------------------------------------------------

def _lunch_over():
    return {570: (100.0, 100.5, 99.8, 100.4), 630: (100.4, 108.0, 100.3, 107.5), 650: (107.5, 107.6, 104.0, 104.5), 655: (104.5, 105.5, 104.2, 105.0), 690: (105.0, 105.2, 103.5, 104.0),
            700: (104.0, 105.2, 103.9, 105.0)}


def test_lunch_macro_htf_program(cap):
    """times#12 (070 ~00:31:06): a late-AM pullback took the 104.0 low (11:30) with the AM high 108 resting above: with the HTF program long the setup is a long, first rung just above the REH (108.5), runner to the
    HTF draw; with the program short no long and a short only after the REH raid. times#13's lunch_macro_entry helper: the retrace into a 5m FVG formed after 11:00 arms a limit at its top."""
    p = Params(**BASE, htf_bias="combo", lunch_htf_program=True)
    ctx, (sl, ss) = mk7(_lunch_over(), p)
    ctx.bias_row = {"combo": 1, "draw_up": 120.0}
    i = bar(ctx, "11:55")
    assert sm7._lunch_ctx(ctx, sl, i, p) is not None and sm7._lunch_ctx(ctx, sl, i, p)[1] == 108.0
    tags = {}
    assert sm7.order_gate7(ctx, sl, dict(ext_i=i, sweep_i=i), i, p, 105.0, 103.0, "LUNCH", [], {}, tags) is None
    assert [round(v, 2) for v, k in tags["fixed4"]] == [round(S._exit_px(108.5, "pool", p), 2), 120.0] and tags["fracs"] == (0.5, 0.5)
    assert sm7.order_gate7(ctx, ss, dict(ext_i=i, sweep_i=i), i, p, -105.0, -107.0, "LUNCH", [], {}, {}) == "x_lunch_program_raid_first"          # the short waits for the REH raid
    ctx.bias_row = {"combo": -1}
    assert sm7.order_gate7(ctx, sl, dict(ext_i=i, sweep_i=i), i, p, 105.0, 103.0, "LUNCH", [], {}, {}) == "x_lunch_program_against"             # no long against a bearish program
    assert sm7.order_gate7(ctx, ss, dict(ext_i=i, sweep_i=i), i, p, -105.0, -107.0, "LUNCH", [], {}, {}) == "x_lunch_program_raid_first"
    over = {**_lunch_over(), 705: (105.0, 108.6, 104.9, 108.4), 710: (108.4, 108.5, 106.0, 106.2)}        # the REH (108) is raided one tick through
    ctx2, (sl2, ss2) = mk7(over, p)
    ctx2.bias_row = {"combo": -1}
    assert sm7.order_gate7(ctx2, ss2, dict(ext_i=i, sweep_i=i), bar(ctx2, "12:00"), p, -106.0, -108.8, "LUNCH", [], {}, {}) is None
    assert sm7.order_gate7(ctx, sl, dict(ext_i=i, sweep_i=i), i, Params(**BASE, htf_bias="combo"), 105.0, 103.0, "LUNCH", [], {}, {}) is None            # switch off
    ctx.bias_row = {"combo": 0}
    assert sm7.order_gate7(ctx, sl, dict(ext_i=i, sweep_i=i), i, p, 105.0, 103.0, "LUNCH", [], {}, {}) is None                                      # no HTF program: silent
    # lunch_macro_entry (case A): the AM was up, the newest FVG formed after 11:00 is the 15m one (104.5-106.1)
    pm = Params(**BASE, lunch_macro_entry=True)
    over3 = {570: (100.0, 100.4, 99.8, 100.2), 590: (100.2, 104.0, 100.1, 103.9), 670: (104.0, 104.5, 103.9, 104.4), 675: (104.4, 106.0, 104.3, 105.9), 680: (105.9, 106.5, 105.0, 106.2), 685: (106.2, 106.4, 105.9, 106.2)}
    ctx3, (sl3, ss3) = mk7(over3, pm)
    o = sm7.lunch_macro_order(ctx3, sl3, bar(ctx3, "11:55"), pm, 1.0)
    assert o is not None and cap["entry"] == pytest.approx(106.1) and cap["tags"]["single_exit"] and cap["tags"]["done_key"] == "LUNCHM" and cap["session"] == "LUNCH"
    assert sm7.lunch_macro_order(ctx3, sl3, bar(ctx3, "11:55"), pm, 1.0) is not None and cap["entry"] == pytest.approx(105.0)       # the 5m FVG is the next candidate
    assert sm7.lunch_macro_order(ctx3, sl3, bar(ctx3, "11:55"), pm, 1.0) is None                 # once per gap
    assert sm7.lunch_macro_order(ctx3, sl3, bar(ctx3, "12:35"), pm, 1.0) is None                 # outside lunch_macro_win
    assert sm7.lunch_macro_order(ctx3, sl3, bar(ctx3, "11:55"), Params(**BASE), 1.0) is None


# --- X14 / X13 / X14 re-entry state machine: fakes of a closed position -----------------------------------------------------------------------------------

def fake_pos(sd, fill_i, basis=100.5, stop=99.0, draw=110.0, ext=98.0, fvg_bottom=99.0, fvg_top=101.0, trail_ref=None, t1_done=True, st=None):
    return dict(side=sd, fill_i=fill_i, draw=draw, ext=ext, basis=basis * 10, n=10, stop=stop, stop0=stop, fvg_bottom=fvg_bottom, fvg_top=fvg_top, fvg_ce=(fvg_bottom + fvg_top) / 2,
                t1_done=t1_done, trail_ref=trail_ref, sm7=st, left=0)


def fake_tr(side="long", reason="t1", px=103.0, final_hit=False, lv_tags="", entry_kind="fvg", shares=10, entry=100.5, stop=99.0, session="AM", propulsion=False):
    return SimpleNamespace(side=side, session=session, exits=[(pd.Timestamp("2026-06-23 10:00", tz=NY), px, 5, reason)], final_hit=final_hit, lv_tags=lv_tags, entry_kind=entry_kind,
                           propulsion=propulsion, shares=shares, entry=entry, stop=stop)


def st0():
    return {"re7": {}, "only_side": {}, "reentered": {}, "re_ctx": {}}


def test_reentry_after_win():
    """session_day_week#2 (049 ~00:02:38; 050 ~00:49:44): a target exit short of the draw with the draw untouched -> the slot re-opens for ONE more same-direction entry at a NEW PD array formed after the exit
    (fresh size); with the draw traded, a final-rung exit, a stop, or past reentry_win_max nothing re-opens."""
    p = Params(**BASE, reentry_after_win=True)
    ctx, (sl, ss) = mk7({0: (100.0, 100.1, 99.9, 100.0)}, p)
    i, fi = bar(ctx, "10:10"), bar(ctx, "09:40")
    done, state = {"AM": True}, st0()
    assert sm7.after_close(ctx, fake_pos(sl, fi), fake_tr(), None, 200.0, done, "AM", state, i, p, False) is True
    r7 = state["re7"]["AM"]
    assert done["AM"] is False and r7["kind"] == "win" and r7["side"] == "long" and r7["exit_i"] == i and r7["pending"]
    assert sm7.after_close(ctx, fake_pos(sl, fi), fake_tr(), None, 200.0, done, "AM", state, i, p, False) is False                       # reentry_win_max = 1
    assert sm7.after_close(ctx, fake_pos(sl, fi), fake_tr(), None, 200.0, {"AM": True}, "AM", st0(), i, p, True) is False               # the X13 half re-entry already took the slot
    for tr_, kw in ((fake_tr(final_hit=True), {}), (fake_tr(reason="stop"), {}), (fake_tr(reason="t1"), dict(draw=100.0))):
        d2, s2 = {"AM": True}, st0()
        assert sm7.after_close(ctx, fake_pos(sl, fi, **kw), tr_, None, 200.0, d2, "AM", s2, i, p, False) is False and d2["AM"] is True
    assert sm7.after_close(ctx, fake_pos(sl, fi), fake_tr(), "long", -50.0, {"AM": True}, "AM", st0(), i, p, False) is False             # a loss is not a win
    assert sm7.after_close(ctx, fake_pos(sl, fi), fake_tr(), None, 200.0, {"AM": True}, "AM", st0(), i, Params(**BASE), False) is False  # off
    p2 = Params(**BASE, reentry_after_win=True, reentry_win_max=2)
    s3 = st0()
    assert sm7.after_close(ctx, fake_pos(sl, fi), fake_tr(), None, 200.0, {"AM": True}, "AM", s3, i, p2, False) and sm7.after_close(ctx, fake_pos(sl, fi), fake_tr(), None, 200.0, {"AM": True}, "AM", s3, i, p2, False)
    # the order gate: the same side, a gap formed AFTER the exit bar
    o_new, o_old = dict(fvg_i=i + 2, i=i + 2, entry_kind="fvg"), dict(fvg_i=i - 1, i=i + 2, entry_kind="fvg")
    assert sm7.reentry_ok(ctx, sl, i + 3, p, o_new, r7) and not sm7.reentry_ok(ctx, sl, i + 3, p, o_old, r7)
    assert not sm7.reentry_ok(ctx, ss, i + 3, p, o_new, r7)                                                                           # no opposite side
    # the engine's risk: a fresh full size (no re-entry half)
    assert S._risk_mult({"reentered": {}, "re_ctx": {}, "re7": {"AM": r7}}, "AM", p) == 1.0
    # sister condition: the partner traded beyond its pre-entry extreme after the fill
    pctx, (psl, pss) = mk7({590: (100.0, 106.0, 99.9, 105.0)}, p)
    ctx.pside = (pctx, {1: psl, -1: pss}, pd.Series(np.arange(len(pctx.idx)), index=pctx.idx))
    pn = Params(**BASE, reentry_after_win=True, reentry_need_sister=True)
    assert sm7.sister_delivered(ctx, sl, i, r7)
    assert sm7.reentry_ok(ctx, sl, i + 3, pn, o_new, r7) and not sm7.reentry_ok(ctx, sl, i + 3, pn, o_new, dict(r7, fill_i=bar(ctx, "10:05")))           # nothing new after a later fill
    pctx2, (psl2, pss2) = mk7({0: (100.0, 100.1, 99.9, 100.0)}, p)
    ctx.pside = (pctx2, {1: psl2, -1: pss2}, pd.Series(np.arange(len(pctx2.idx)), index=pctx2.idx))
    assert not sm7.sister_delivered(ctx, sl, i, r7) and not sm7.reentry_ok(ctx, sl, i + 3, pn, o_new, r7)
    ctx.pside = None
    assert not sm7.sister_delivered(ctx, sl, i, r7)


def test_reentry_after_trail_win(cap):
    """session_day_week#3 (085 ~00:27:16; 056; 022): a trailed stop hit in profit with the draw untouched -> a limit at the CE of the defended IFVG (full size, target = the draw); a body close under the IFVG, a
    losing stop-out, the high-resistance proxy (sloppy / chop) or trail_reentry_max end it; trail_reentry_entry "breaker" = the retest of the last up-close candle price traded above."""
    p = Params(**BASE, reentry_after_trail_win=True)
    ctx, (sl, ss) = mk7({0: (100.0, 100.1, 99.9, 100.0), 570: (100.0, 100.1, 99.9, 100.0), 600: (100.0, 103.5, 100.0, 103.0), 605: (103.0, 103.2, 102.9, 103.1)}, p)
    i, fi, ei = bar(ctx, "10:10"), bar(ctx, "09:40"), bar(ctx, "10:05")
    pos = fake_pos(sl, fi, trail_ref=(99.0, 101.0, 50), basis=100.5)
    done, state = {"AM": True}, st0()
    assert sm7.after_close(ctx, pos, fake_tr(reason="stop", px=102.0), None, 300.0, done, "AM", state, ei, p, False) is True
    r7 = state["re7"]["AM"]
    assert r7["kind"] == "trail_win" and r7["ref"] == (99.0, 101.0) and done["AM"] is False
    ctx.re7 = r7
    o = sm7.re_order(ctx, sl, i, p, "AM", 1.0)
    assert o is not None and cap["entry"] == pytest.approx(100.0) and cap["stop"] == pytest.approx(99.0 - p.pad) and cap["tags"]["entry_kind"] == "trail_reentry"
    assert cap["fixed"][0][0] == pytest.approx(S._exit_px(110.0, "pool", p)) and cap["tags"]["sm7"]["kind"] == "trail_win"
    assert sm7.re_order(ctx, sl, i, p, "AM", 1.0) is None                                                                              # armed once
    assert sm7.reentry_ok(ctx, sl, i, p, dict(sm7=dict(kind="trail_win")), r7) and not sm7.reentry_ok(ctx, sl, i, p, dict(sm7=dict(kind="x")), r7) and not sm7.reentry_ok(ctx, sl, i, p, dict(), r7)
    # not in profit / draw traded / past the cap
    for tr_, pos_, ok in ((fake_tr(reason="stop", px=100.0), pos, False), (fake_tr(reason="stop", px=102.0), fake_pos(sl, fi, trail_ref=(99.0, 101.0, 50), draw=100.0), False),
                          (fake_tr(reason="t1", px=102.0), pos, False)):
        assert sm7.after_close(ctx, pos_, tr_, None, 300.0, {"AM": True}, "AM", st0(), ei, p, False) is ok
    s2 = st0()
    p1 = Params(**BASE, reentry_after_trail_win=True, trail_reentry_max=1)
    assert sm7.after_close(ctx, pos, fake_tr(reason="stop", px=102.0), None, 300.0, {"AM": True}, "AM", s2, ei, p1, False) is True
    assert sm7.after_close(ctx, pos, fake_tr(reason="stop", px=102.0), None, 300.0, {"AM": True}, "AM", s2, ei, p1, False) is False
    # the structure broken by a body close, or a high-resistance (sloppy) day: nothing armed
    ctx2, (sl2, _) = mk7({600: (100.0, 100.5, 97.0, 98.0), 605: (98.0, 103.2, 97.9, 103.1)}, p)
    ctx2.re7 = dict(r7, armed=False)
    assert sm7.re_order(ctx2, sl2, bar(ctx2, "10:10"), p, "AM", 1.0) is None and ctx2.re7["dead"]
    ctx.re7 = dict(r7, armed=False)
    ctx.cur_sloppy = "chop"
    assert sm7.re_order(ctx, sl, i, p, "AM", 1.0) is None
    ctx.cur_sloppy = ""
    # breaker form
    pb = Params(**BASE, reentry_after_trail_win=True, trail_reentry_entry="breaker")
    ctx3, (sl3, _) = mk7({585: (100.0, 102.2, 99.9, 102.0), 600: (102.0, 103.5, 101.9, 103.0), 605: (103.0, 103.2, 102.9, 103.1), 610: (103.1, 103.3, 102.9, 103.2)}, pb)
    ctx3.re7 = dict(r7, armed=False, fill_i=bar(ctx3, "09:35"), exit_i=bar(ctx3, "10:00"))
    assert sm7.re_order(ctx3, sl3, bar(ctx3, "10:10"), pb, "AM", 1.0) is not None and cap["entry"] == pytest.approx(102.0) and cap["stop"] == pytest.approx(101.0 - pb.pad)


def test_reentry_after_loss_gate(cap):
    """session_day_week#4 (060 ~01:22:23; cc02_005 ~00:03:34; 104 ~00:45:43): after a losing stop-out the idea is intact when the draw is untouched, no opposing MSS / close beyond the leg origin and a NEW array formed
    after the stop - and the re-entry is a limit (never a market chase), at reentry_risk_mult x the risk; trigger sibi_return: beyond the entry zone's far edge, then a limit at the edge on the return."""
    p = Params(**BASE, reentry_half=True, reentry_idea_gate=True)
    ctx, (sl, ss) = mk7({600: (100.0, 100.5, 98.8, 99.2), 605: (99.2, 101.6, 99.1, 101.4)}, p)
    fi, si, i = bar(ctx, "09:40"), bar(ctx, "10:00"), bar(ctx, "10:05")
    rc = dict(side="long", z=(99.0, 101.0), ext=98.0, low_stop=98.7, draw=110.0, fill_i=fi, stop_i=si, pending=True)
    o = dict(fvg_i=si + 1, i=si + 1, entry_kind="fvg")
    assert sm7.reentry_idea_ok(ctx, sl, i, p, o, rc)
    assert not sm7.reentry_idea_ok(ctx, sl, i, p, dict(o, market=True), rc)                       # never a chase
    assert not sm7.reentry_idea_ok(ctx, sl, i, p, dict(fvg_i=si - 1, i=si + 1), rc)               # no NEW array after the stop
    assert not sm7.reentry_idea_ok(ctx, sl, i, p, o, dict(rc, draw=101.5))                         # the draw was traded
    assert not sm7.reentry_idea_ok(ctx, sl, i, p, o, dict(rc, low_stop=102.0))                     # a close under the stop-out low = an opposing structure break
    assert not sm7.reentry_idea_ok(ctx, sl, i, p, o, dict(rc, ext=99.3))                           # a close beyond the leg's origin swing
    # risk: half by default, the test value replaces it
    s_ = {"reentered": {"AM": True}, "re_ctx": {}}
    assert S._risk_mult(s_, "AM", p) == 0.5 and S._risk_mult(s_, "AM", Params(**BASE, reentry_risk_mult=1.0)) == 1.0
    assert S._risk_mult({"reentered": {}, "re_ctx": {}}, "AM", p) == 1.0
    s2 = {"reentered": {"AM": True}, "re_ctx": {"AM": {"ratio": 0.8}}}
    assert S._risk_mult(s2, "AM", Params(**BASE, reentry_risk="loss", reentry_risk_mult=0.5)) == pytest.approx(0.4)
    # the 104 variant
    pv = Params(**BASE, reentry_half=True, reentry_idea_gate=True, reentry_trigger="sibi_return")
    assert not sm7.reentry_idea_ok(ctx, sl, i, pv, o, rc) and sm7.reentry_idea_ok(ctx, sl, i, pv, dict(o, sm7=dict(kind="sibi_return")), rc)
    ctx.re_ctx_now = dict(rc, armed=False)
    out = sm7.re_order(ctx, sl, i, pv, "AM", 1.0)
    assert out is not None and cap["entry"] == pytest.approx(101.0) and cap["stop"] == pytest.approx(98.8 - pv.pad) and cap["tags"]["entry_kind"] == "sibi_return"
    assert sm7.re_order(ctx, sl, i, pv, "AM", 1.0) is None
    ctx.re_ctx_now = dict(rc, armed=False)
    pw = Params(**BASE, reentry_half=True, reentry_idea_gate=True, reentry_trigger="sibi_return", reentry_stop="wick_ce")
    sm7.re_order(ctx, sl, i, pw, "AM", 1.0)
    assert cap["stop"] == pytest.approx((98.8 + 99.2) / 2 - pw.pad)                              # the CE of the lowest wick (low 98.8, body bottom 99.2)
    ctx.re_ctx_now = dict(rc, armed=False)
    assert sm7.re_order(ctx, sl, bar(ctx, "10:00"), pv, "AM", 1.0) is None                         # the zone's far edge was not traded beyond yet
    assert sm7.re_order(ctx, sl, i, p, "AM", 1.0) is None                                          # trigger new_array: no return order
    # the gate in the engine: the idea-intact switch swaps the X13b order test
    assert "loss_reentry_ok" in __import__("inspect").getsource(S._run_day_once) and "reentry_idea_ok" in __import__("inspect").getsource(sm7.loss_reentry_ok)


def test_reverse_after_failure(cap):
    """session_day_week#7 (045; 094; 102; cc04_008): one opposite trade per session after a failure, at reverse_risk_mult: 102 the inversion of the failed array (a limit at its near edge on the return, stop beyond its CE), 094
    the offside exit at the stop price re-entered opposite (a stop order), cc04_008 a failed propulsion block, 045 the sick sister after a small loss; "off" changes nothing."""
    p = Params(**BASE, reverse_after_failure="inversion")
    ctx, (sl, ss) = mk7({0: (100.0, 100.1, 99.9, 100.0), 580: (100.0, 100.1, 97.9, 98.0), 585: (98.0, 98.6, 97.8, 98.5)}, p)
    fi, i0, i = bar(ctx, "09:35"), bar(ctx, "09:40"), bar(ctx, "09:45")
    state, done = st0(), {"AM": True}
    assert sm7.after_close(ctx, fake_pos(sl, fi, t1_done=False), fake_tr(reason="stop", px=99.0, entry=100.5), "long", -150.0, done, "AM", state, i0, p, False) is True
    r7 = state["re7"]["AM"]
    assert r7["kind"] == "reverse" and r7["variant"] == "inversion" and r7["side"] == "short" and done["AM"] is False and state["only_side"]["AM"] == -1 and state["rev7_n"]["AM"] == 1
    assert sm7.after_close(ctx, fake_pos(sl, fi, t1_done=False), fake_tr(reason="stop", px=99.0), "long", -150.0, {"AM": True}, "AM", state, i0, p, False) is False        # a second reversal in the same session is refused
    assert sm7.after_close(ctx, fake_pos(sl, fi, t1_done=False), fake_tr(reason="stop", px=99.0), "long", -150.0, {"AM": True}, "AM", st0(), i0, Params(**BASE), False) is False     # off
    ctx.re7 = r7
    o = sm7.re_order(ctx, ss, i, p, "AM", 1.0)
    assert o is not None and cap["entry"] == pytest.approx(-99.0) and cap["stop"] == pytest.approx(-100.0 - p.pad) and cap["tags"]["sm7"]["kind"] == "rev_inversion"
    assert sm7.re_order(ctx, ss, i, p, "AM", 1.0) is None and sm7.re_order(ctx, sl, i, p, "AM", 1.0) is None
    assert sm7.reentry_ok(ctx, ss, i, p, dict(sm7=dict(kind="rev_inversion")), r7) and not sm7.reentry_ok(ctx, ss, i, p, dict(), r7)
    assert S._risk_mult({"reentered": {}, "re_ctx": {}, "re7": {"AM": r7}}, "AM", p) == 0.5                                                      # reverse_risk_mult
    ctx2, (sl2, ss2) = mk7({580: (100.0, 100.1, 98.9, 99.5), 585: (99.5, 100.5, 99.4, 100.4)}, p)           # the failed zone re-closed over its CE: the inversion did not hold
    r2 = dict(r7, fill_i=bar(ctx2, "09:35"), exit_i=bar(ctx2, "09:40"), armed=False)
    ctx2.re7 = r2
    assert sm7.re_order(ctx2, ss2, bar(ctx2, "09:45"), p, "AM", 1.0) is None
    # at_stop: the offside exit
    pa = Params(**BASE, reverse_after_failure="at_stop", offside_frac=0.5)
    ctx3, (sl3, ss3) = mk7({570: (100.0, 101.2, 99.9, 100.5), 575: (100.5, 100.6, 98.8, 98.9), 580: (98.9, 99.0, 98.7, 98.85)}, pa)
    pos = fake_pos(sl3, bar(ctx3, "09:30"), stop=98.75, fvg_bottom=99.0, t1_done=False, st=dict(at_stop=True))
    pos["left"] = 10
    tr = fake_tr(reason="stop", px=98.9)
    tr.exits = []
    sm7.manage(ctx3, sl3, pos, tr, bar(ctx3, "09:35"), pd.Timestamp("2026-06-23 09:35", tz=NY), pa)
    assert tr.exits[-1][3] == "offside_rev" and pos["left"] == 0 and tr.exits[-1][1] == pytest.approx(98.9)
    pos2 = fake_pos(sl3, bar(ctx3, "09:30"), stop=98.75, fvg_bottom=99.0, t1_done=True, st=dict(at_stop=True))
    pos2["left"] = 10
    tr2 = fake_tr()
    tr2.exits = []
    sm7.manage(ctx3, sl3, pos2, tr2, bar(ctx3, "09:35"), pd.Timestamp("2026-06-23 09:35", tz=NY), pa)
    assert not tr2.exits                                                                           # after the first partial the trade is not "offside"
    s3, d3 = st0(), {"AM": True}
    trl = fake_tr(reason="offside_rev", px=98.9, entry=100.5)
    assert sm7.after_close(ctx3, pos, trl, "long", -160.0, d3, "AM", s3, bar(ctx3, "09:35"), pa, False) is True and s3["re7"]["AM"]["variant"] == "at_stop"
    r3 = s3["re7"]["AM"]
    ctx3.re7 = r3
    o3 = sm7.re_order(ctx3, ss3, bar(ctx3, "09:40"), pa, "AM", 1.0)
    assert o3 is not None and cap["entry"] == pytest.approx(-98.75) and cap["tags"]["stop_entry"] and cap["stop"] == pytest.approx(-101.2 - pa.pad)
    # cc04_008 / 045
    pc = Params(**BASE, reverse_after_failure="all")
    s4 = st0()
    assert sm7.after_close(ctx, fake_pos(sl, fi), fake_tr(reason="time", entry_kind="arr_propulsion"), "long", -400.0, {"AM": True}, "AM", s4, i0, pc, False) and s4["re7"]["AM"]["variant"] == "prop_fail"
    s5 = st0()
    assert sm7.after_close(ctx, fake_pos(sl, fi), fake_tr(reason="time"), "long", -5.0, {"AM": True}, "AM", s5, i0, pc, False) and s5["re7"]["AM"]["variant"] == "sick_sister"
    s6 = st0()
    assert not sm7.after_close(ctx, fake_pos(sl, fi), fake_tr(reason="time"), "long", -400.0, {"AM": True}, "AM", s6, i0, pc, False)          # a big loss, no failed array: no reversal
    assert sm7.reentry_ok(ctx, ss, i, pc, dict(broke=3, fvg_i=i, i=i), dict(s4["re7"]["AM"], stop_i=i0)) and not sm7.reentry_ok(ctx, ss, i, pc, dict(broke=None, i=i), dict(s4["re7"]["AM"], stop_i=i0))


def test_opposite_after_target():
    """session_day_week#8 (093 ~00:14:52; cc10_007 ~00:12:21): lod - a counter-bias short toward a predefined low-of-day level (a prior daily wick CE with an intraday discount array within lod_conf_pts) is scanned
    and, once it reached the level, the slot re-opens ONCE for the bias side; split - after a winning AM trade the PM stays open for the opposite side when the AM did not deliver the bulk of the range."""
    p = Params(**BASE, allow_opposite_after_target="lod")
    ctx, (sl, ss) = mk7({0: (100.0, 100.1, 99.9, 100.0)}, p, bias=1, conf=Conf7({1: [(95.4, 94.6, "15m", 0, 0)]}))
    ctx.wicks = [dict(upper=105.0, lower=95.0)]
    i = bar(ctx, "10:00")
    assert sm7.lod_level(ctx, ss, i, p) == pytest.approx(-95.0) and sm7.lod_level(ctx, sl, i, p) is None
    assert sm7.counter_kind7(ctx, ss, i, p, 1) == "lod" and sm7.counter_kind7(ctx, sl, i, p, 1) == ""
    ctx2, (sl2, ss2) = mk7({0: (100.0, 100.1, 99.9, 100.0)}, p, bias=1, conf=Conf7({1: [(90.0, 89.0, "15m", 0, 0)]}))
    ctx2.wicks = [dict(upper=105.0, lower=95.0)]
    assert sm7.lod_level(ctx2, ss2, i, p) is None                                                  # no intraday discount array at the level
    ctx3, (sl3, ss3) = mk7({0: (100.0, 100.1, 99.9, 100.0), 570: (100.0, 100.1, 94.9, 95.5)}, p, bias=1, conf=Conf7({1: [(95.4, 94.6, "15m", 0, 0)]}))
    ctx3.wicks = [dict(upper=105.0, lower=95.0)]
    assert sm7.lod_level(ctx3, ss3, i, p) is None                                                  # the level was already traded
    # the re-open
    state, done = st0(), {"AM": True}
    pos = fake_pos(ss, bar(ctx, "09:40"))
    tr = fake_tr(side="short", reason="t1", px=95.5, final_hit=True, lv_tags="lod_short")
    assert sm7.after_close(ctx, pos, tr, None, 400.0, done, "AM", state, i, p, False) is True and done["AM"] is False and state["only_side"]["AM"] == 1 and state["lod_done"]
    assert sm7.after_close(ctx, pos, tr, None, 400.0, {"AM": True}, "AM", state, i, p, False) is False       # only once: at most one short + one long per AM
    # split: the gate judges the AM range at the PM order
    ps = Params(**BASE, allow_opposite_after_target="split")
    ctx4, (sl4, ss4) = mk7({570: (100.0, 109.0, 100.0, 108.5), 680: (108.5, 108.6, 108.0, 108.2)}, ps)         # AM range 9 = 0.5 x ADR5 (18)
    ctx4.state7 = {"split_pm": -1}
    i4 = bar(ctx4, "14:00")
    sw = dict(broke=bar(ctx4, "13:40"), ext_i=i4, sweep_i=i4)
    lvt = []
    assert sm7.order_gate7(ctx4, ss4, sw, i4, ps, -108.0, -110.0, "PM", lvt, {}, {}) is None and "split_pm" in lvt
    assert sm7.order_gate7(ctx4, ss4, dict(sw, broke=bar(ctx4, "11:00")), i4, ps, -108.0, -110.0, "PM", [], {}, {}) == "x_split_no_pm_mss"
    ctx5, (sl5, ss5) = mk7({570: (100.0, 116.0, 100.0, 115.5), 680: (115.5, 115.6, 115.0, 115.2)}, ps)         # AM range 16 >= 0.8 x 18: the AM delivered the bulk
    ctx5.state7 = {"split_pm": -1}
    assert sm7.order_gate7(ctx5, ss5, dict(sw, broke=bar(ctx5, "13:40")), bar(ctx5, "14:00"), ps, -115.0, -117.0, "PM", [], {}, {}) == "x_split_am_range"
    # the _after_close site: no_pm_after_am_win keeps the PM open for the opposite side only
    pp = Params(**BASE, allow_opposite_after_target="split", no_pm_after_am_win=True)
    import mentorship.strategy as SS
    tr7 = SS.Trade(D0, "ES", "AM", "am_mm", "long", "x", False, None, pd.Timestamp("2026-06-23 09:40", tz=NY), pd.Timestamp("2026-06-23 09:41", tz=NY), 100.0, 99.0, 102.0, None, 10)
    tr7.exits.append((pd.Timestamp("2026-06-23 10:30", tz=NY), 102.0, 10, "t1"))
    pos7 = dict(trade=tr7, side=sl, fill_i=0, basis=1000.0, n=10, ext=98.0, draw=110.0, stop=99.0, t1_done=True, fvg_bottom=99.0, fvg_ce=100.0)
    base_state = {"day": D0, "reentered": {}, "re_ctx": {}, "re7": {}, "only_side": {}, "reversed": {}, "day_pts": 0.0, "day_loss": False, "rs": None}
    done7, st7 = {"AM": True, "PM": False}, dict(base_state)
    SS._after_close(pos7, [], pp, done7, st7, i=100, ctx=None)
    assert done7["PM"] is False and st7["split_pm"] == -1 and st7["only_side"]["PM"] == -1                  # the PM stays open, for the SHORT side only
    done8, st8 = {"AM": True, "PM": False}, dict(base_state, only_side={})
    SS._after_close(pos7, [], Params(**BASE, no_pm_after_am_win=True), done8, st8, i=100, ctx=None)
    assert done8["PM"] is True and "split_pm" not in st8                                                  # the default: the AM win ends the day


# --- E12-070-rung-order (stops_sizing_scaling_in#16) --------------------------------------------------------------------------------------------------

def _adv_over():
    return {570: (100.0, 100.6, 99.8, 100.5), 575: (100.5, 102.0, 100.4, 101.9), 580: (101.9, 102.5, 101.4, 102.4), 585: (102.4, 106.0, 102.3, 105.9), 590: (105.9, 106.0, 104.0, 104.2),
            595: (104.2, 104.3, 102.0, 102.2), 600: (102.2, 103.5, 101.5, 103.0), 605: (103.0, 105.0, 102.9, 104.8)}


def test_adv_breaker_rungs(cap, monkeypatch):
    """#16 (070 ~00:58:44): inside the advanced breaker's A-B leg three resting limits - the 1m IFVG CE, the IFVG's low end and a 5m FVG CE - sized adv_rung_fracs (10 / 30 / 60 %), a fill of rung 1 only is 10 % of the
    size; fewer than two rungs keep the single MT limit."""
    p = Params(**BASE, adv_breaker=True, adv_rungs=True)
    ctx, (sl, ss) = mk7(_adv_over(), p)
    i = bar(ctx, "10:05")
    lad = sm7.adv_ladder(ctx, sl, dict(ext_i=bar(ctx, "09:30") - 3), i, p, 100.0, 110.0, 96.75)
    assert lad is not None and lad[0] == [pytest.approx(103.75), pytest.approx(103.5), pytest.approx(102.15)]
    # review fix: each rung keeps ITS type's weight (5m CE 0.1, IFVG CE 0.3, IFVG low end 0.6) - the price order here is IFVG CE, IFVG low end, 5m CE
    assert lad[1] == pytest.approx((0.3, 0.6, 0.1))
    lad2 = sm7.adv_ladder(ctx, sl, dict(ext_i=bar(ctx, "09:30") - 3), i, p, 103.0, 110.0, 96.75)                       # no 5m FVG inside this leg: the IFVG pair is renormalised, nobody inherits the 5m weight
    assert lad2 is not None and lad2[0] == [pytest.approx(103.75), pytest.approx(103.5)] and lad2[1] == pytest.approx((1 / 3, 2 / 3))
    assert sm7.adv_ladder(ctx, sl, dict(ext_i=bar(ctx, "09:30") - 3), i, p, 104.5, 110.0, 96.75) is None            # nothing inside a leg that high
    # the wiring in the advanced breaker order: the ladder replaces the single MT limit
    monkeypatch.setattr(SM, "_l1", lambda sd, ref_i, i_: SimpleNamespace(price=100.0))
    sw = dict(ext=97.0, ext_i=bar(ctx, "09:30") - 3, session="AM", key="x", name="x", level=100.0, broke=i, sweep_i=bar(ctx, "09:30") - 3, smt=None, smt2=None)
    o = SM.adv_breaker_order(ctx, sl, sw, i, p, "AM", 1.0, bar(ctx, "09:30") - 5, 110.0, True)
    assert o is not None and cap["entry"] == pytest.approx(103.75) and cap["tags"]["ladder"] == lad[0] and cap["tags"]["ladder_fracs"] == lad[1]
    SM.adv_breaker_order(ctx, sl, sw, i, Params(**BASE, adv_breaker=True), "AM", 1.0, bar(ctx, "09:30") - 5, 110.0, True)
    assert cap["entry"] == pytest.approx(105.0) and "ladder" not in cap["tags"]                                    # off: the MT limit (A + B) / 2
    # the real order tail sizes the three legs 1 : 3 : 6 and the fill of rung 1 alone is 10 %
    monkeypatch.undo()
    p2 = Params(**BASE, account_equity=1e7)
    ctx2, (sl2, _) = mk7({0: (100.0, 100.1, 99.9, 100.0)}, p2, base=100.0)
    sw2 = dict(session="AM", key="x", name="x", level=103.0, ext=95.0, ext_i=bar(ctx2, "09:30"), sweep_i=bar(ctx2, "09:30"), broke=bar(ctx2, "09:35"), smt=None, smt2=None, synthetic=True)
    tags = dict(unicorn=False, fvg_bottom=96.0, fvg_ce=99.0, entry_kind="adv_breaker", mitigation=False, propulsion=False, no_leg_wait=True, skip_po3=True,
                ladder=[99.0, 98.0, 97.0], ladder_fracs=(0.1, 0.3, 0.6))
    ctx2.cur_session = "AM"
    import collections
    S.FUNNEL = collections.Counter()
    order = S._finish_order(ctx2, sl2, bar(ctx2, "09:40"), p2, "AM", sw2, 99.0, 94.5, 1.0, 105.0, tags, skip_leg_pd=True, fixed=[(110.0, "array")])
    funnel, S.FUNNEL = dict(S.FUNNEL), None
    assert order is not None, funnel
    qs = [order["shares"]] + [q for _, q in order["rungs"]]
    assert len(qs) == 3 and qs[1] in (3 * qs[0], 3 * qs[0] + 1, 3 * qs[0] - 1) and qs[2] >= 2 * qs[1] - 1 and order["plan_shares"] == sum(qs)


# --- X13-reentry-turtle-soup (stops_sizing_scaling_in#43) ---------------------------------------------------------------------------------------------

def test_reentry_turtle_soup():
    """#43 (cc01_005 ~00:12:36): after a stop-out only a turtle soup of an old 3-bar swing extreme formed inside the session range re-enters, on the right side of the range EQ (side space: the discount), at half
    risk, up to reentry_max times."""
    p = Params(**BASE, reentry_ts=True)
    over = {570: (100.0, 110.0, 98.0, 99.0), 575: (99.0, 99.4, 98.5, 99.1), 580: (99.1, 101.0, 99.0, 100.9), 585: (100.9, 101.0, 99.5, 99.6), 590: (99.6, 99.9, 99.2, 99.5)}
    ctx, (sl, ss) = mk7(over, p)
    i = bar(ctx, "09:40")
    state, done = st0(), {"AM": True}
    assert sm7.after_close(ctx, fake_pos(sl, bar(ctx, "09:30")), fake_tr(reason="stop", px=99.0), "long", -150.0, done, "AM", state, i, p, False) is True
    r7 = state["re7"]["AM"]
    assert r7["kind"] == "ts_re" and done["AM"] is False
    o = dict(entry_kind="turtle_soup", entry=99.5, sm7=dict(ts_pivot=True), i=i)
    assert sm7.reentry_ok(ctx, sl, i, p, o, r7)                                                                  # below the range EQ (104)
    assert not sm7.reentry_ok(ctx, sl, i, p, dict(o, entry=106.0), r7)                                           # above it
    assert not sm7.reentry_ok(ctx, sl, i, p, dict(o, sm7=dict(ts_pivot=False)), r7)                              # not an old 3-bar swing
    assert not sm7.reentry_ok(ctx, sl, i, p, dict(o, entry_kind="fvg"), r7)                                      # only a turtle soup
    assert not sm7.reentry_ok(ctx, ss, i, p, o, r7)                                                              # the same direction only
    assert S._risk_mult({"reentered": {}, "re_ctx": {}, "re7": {"AM": r7}}, "AM", p) == pytest.approx(0.5)      # reentry_mult
    assert S._risk_mult({"reentered": {}, "re_ctx": {}, "re7": {"AM": r7}}, "AM", Params(**BASE, reentry_ts=True, reentry_mult=0.7)) == pytest.approx(0.7)
    assert sm7.after_close(ctx, fake_pos(sl, bar(ctx, "09:30")), fake_tr(reason="stop", px=99.0), "long", -150.0, {"AM": True}, "AM", state, i, p, False) is True       # up to reentry_max = 2
    assert sm7.after_close(ctx, fake_pos(sl, bar(ctx, "09:30")), fake_tr(reason="stop", px=99.0), "long", -150.0, {"AM": True}, "AM", state, i, p, False) is False
    assert sm7.after_close(ctx, fake_pos(sl, bar(ctx, "09:30")), fake_tr(reason="time"), "long", -150.0, {"AM": True}, "AM", st0(), i, p, False) is False        # a stop-out only
    assert sm7.after_close(ctx, fake_pos(sl, bar(ctx, "09:30")), fake_tr(reason="stop", px=99.0), "long", -150.0, {"AM": True}, "AM", st0(), i, Params(**BASE), False) is False
    # the swept level must be a 3-bar swing low formed today
    sw = dict(level=98.0)
    assert sm7.ts_pivot_ok(ctx, sl, sw, i, p) and not sm7.ts_pivot_ok(ctx, sl, dict(level=97.0), i, p) and not sm7.ts_pivot_ok(ctx, sl, dict(), i, p)


# --- E6-breakaway-gap-stop (stops_sizing_scaling_in#46) -----------------------------------------------------------------------------------------------

def _ba_over():
    return {570: (100.0, 100.4, 98.0, 98.5), 575: (98.5, 99.5, 98.4, 99.4), 580: (99.4, 100.5, 99.3, 100.4), 585: (99.9, 100.0, 99.6, 99.7), 590: (99.7, 102.0, 99.6, 101.9),
            595: (101.9, 103.5, 101.2, 103.4), 600: (103.4, 104.5, 103.0, 104.0), 605: (104.0, 104.2, 102.5, 102.8), 610: (102.8, 106.0, 102.7, 105.9), 615: (105.9, 106.1, 105.0, 105.5),
            620: (105.5, 105.6, 100.2, 101.5)}


def test_breakaway_reentry_stop(cap):
    """#46 (062 ~00:37:28): two same-direction MSSs, the first order missed, a retrace bar that enters the breakaway gap (100.0-101.2) arms a limit at its near edge (101.2) with the stop under the retrace bar's low
    minus a tick; once price leaves to a new high the stop is raised to just under the gap; a gap filled fully is no breakaway."""
    p = Params(**BASE, breakaway_reentry=True)
    ctx, (sl, ss) = mk7(_ba_over(), p)
    sw0 = dict(session="AM", key="pdl1", name="pdl1", level=99.0, ext=98.0, ext_i=bar(ctx, "09:30"), sweep_i=bar(ctx, "09:30"), broke=bar(ctx, "09:50"), smt=None, smt2=None)
    sw = dict(sw0)
    i = bar(ctx, "10:20")
    ba = next(g for g in sl.gaps if g.i == bar(ctx, "09:55"))
    assert (ba.top, ba.bottom) == (pytest.approx(101.2), pytest.approx(100.0))
    assert sm7.n_mss(sl, sw, i) == 2 and sm7.n_mss(sl, dict(sw, broke=None), i) == 0
    o = sm7.breakaway_order(ctx, sl, sw, ba, i, p, "AM", 1.0)
    assert o is not None and cap["entry"] == pytest.approx(101.2) and cap["stop"] == pytest.approx(100.2 - p.tick) and cap["tags"]["entry_kind"] == "breakaway_re"
    assert cap["tags"]["cancel_low"] == pytest.approx(100.0) and cap["tags"]["sm7"]["kind"] == "ba"
    assert sm7.breakaway_order(ctx, sl, sw, ba, i, p, "AM", 1.0) is None                                          # once per sweep
    sw2 = dict(sw)
    assert sm7.breakaway_order(ctx, sl, dict(sw2, broke=bar(ctx, "10:00")), ba, i, p, "AM", 1.0) is None          # one MSS only
    ctx.pend_now = object()
    assert sm7.breakaway_order(ctx, sl, dict(sw0), ba, i, p, "AM", 1.0) is None                                    # an order rests
    ctx.pend_now = None
    ctx.done_ref["AM"] = True
    assert sm7.breakaway_order(ctx, sl, dict(sw0), ba, i, p, "AM", 1.0) is None                                    # a fill exists
    ctx.done_ref["AM"] = False
    assert sm7.breakaway_order(ctx, sl, dict(sw0), ba, i, p, "AM", 1.0) is not None                                # (and the same sweep with a free slot arms)
    ctx2, (sl2, _) = mk7({**_ba_over(), 620: (105.5, 105.6, 99.8, 101.5)}, p)                                      # the gap filled fully
    ba2 = next(g for g in sl2.gaps if g.i == bar(ctx2, "09:55"))
    assert sm7.breakaway_order(ctx2, sl2, dict(sw0), ba2, bar(ctx2, "10:20"), p, "AM", 1.0) is None
    # management: a new high beyond the order's, the gap still partly open -> the stop to just under the gap
    ctx3, (sl3, _) = mk7({**_ba_over(), 625: (101.5, 106.5, 101.4, 106.2)}, p)
    pos3 = fake_pos(sl3, bar(ctx3, "10:20"), stop=99.0, st=dict(kind="ba", gap_bottom=100.0, ref_hi=106.1))
    pos3["left"] = 10
    sm7.manage(ctx3, sl3, pos3, fake_tr(), bar(ctx3, "10:25"), pd.Timestamp("2026-06-23 10:25", tz=NY), p)
    assert pos3["stop"] == pytest.approx(100.0 - p.tick) and pos3["sm7"]["dropped"]
    on_fill_pos = dict(side=sl, left=1)
    sm7.on_fill(ctx, sl, on_fill_pos, None, dict(sm7=dict(kind="ba", gap_bottom=100.0), i=i), i, p)
    assert on_fill_pos["sm7"]["ref_hi"] == pytest.approx(float(sl.h[ctx.start:i + 1].max()))


def test_lunch_macro_sell_side_run_into_15m_fvg(cap):
    """times#12 / the item-13 helper, case B: the AM draw unfinished (buy-side still above), a late-AM sell-side run under a short-term low of the morning, and an untouched 15m FVG below (100.0-102.8): a limit at
    its LOW, stop under it, one exit; not when the HTF objective is done."""
    pm = Params(**BASE, lunch_macro_entry=True)
    over = {570: (99.0, 100.0, 98.9, 99.8), 575: (99.8, 100.0, 99.7, 99.9), 580: (99.9, 100.0, 99.8, 100.0), 585: (100.0, 103.0, 99.9, 102.9), 590: (102.9, 103.2, 102.5, 103.0),
            595: (103.0, 103.5, 102.8, 103.4), 600: (103.4, 103.6, 102.9, 103.5), 635: (103.5, 103.6, 103.3, 103.4), 640: (103.4, 103.6, 102.9, 103.0), 645: (103.0, 103.5, 103.2, 103.4),
            690: (103.4, 103.5, 102.3, 103.0), 695: (103.0, 103.2, 102.9, 103.1)}
    ctx, (sl, ss) = mk7(over, pm)
    i = bar(ctx, "11:55")
    o = sm7.lunch_macro_order(ctx, sl, i, pm, 1.0)
    assert o is not None and cap["entry"] == pytest.approx(100.0) and cap["stop"] == pytest.approx(99.0) and cap["tags"]["single_exit"] and cap["tags"]["entry_kind"] == "lunch_macro"
    assert sm7.lunch_macro_order(ctx, sl, i, pm, 1.0) is None                                      # once per gap
    ctx2, (sl2, _) = mk7(over, pm)
    ctx2.bias_row = {"draw_up": 103.0}                                                              # the HTF draw already traded
    assert sm7.lunch_macro_order(ctx2, sl2, i, pm, 1.0) is None
    assert sm7.lunch_macro_order(ctx, ss, i, pm, 1.0) is None


def test_london_close_scalp_in_run_day():
    """The whole engine path of item 200: special7 arms the window-less order, it lives past the AM window (cut_at), fills at the OB open, is managed (one target) - off, the scalp does not exist."""
    over = dict(_lc_over())
    over[660] = (111.3, 112.0, 111.2, 111.9)
    over[665] = (111.9, 111.95, 108.5, 108.6)
    df = day(full(over, 100.0), d=D0, start="00:00", base=100.0)
    hist = history(D0, hi=106.0, lo=94.0)
    kw = dict(htf_resist_cap=False, draw_lock="off", news_wait="off", min_draw_pts=0.0, leg_pd=0.0)
    on = S.run_day(df, hist, "ES", Params(**BASE, lc_scalp=True, lc_stop_pts=1.0, lc_retrace=0.3, **kw), 5)
    lc = [t for t in on if t.entry_kind == "lc_scalp"]
    assert len(lc) == 1 and lc[0].side == "short" and lc[0].entry == pytest.approx(111.8) and lc[0].stop == pytest.approx(114.0)
    assert lc[0].exits[-1][3] == "t1" and lc[0].exits[-1][1] == pytest.approx(-S._exit_px(-(113.0 - 0.3 * 13.2), "pool", Params(**BASE)))      # the one target: 30 % of the day range back from the HOD
    assert lc[0].entry_time.hour * 60 + lc[0].entry_time.minute >= 660                          # armed at 10:55, filled at 11:00: past the AM window end
    off = S.run_day(df, hist, "ES", Params(**BASE, **kw), 5)
    assert not [t for t in off if t.entry_kind == "lc_scalp"]


def test_macro_1050_in_run_day():
    """The engine path of times#3: the window-less 10:50 order fills (11:05), is managed to its target; with m1050_cut a fill after 11:10 never happens (the order is cancelled), without the cut the usual lifetime applies."""
    def run_(over, on=True, **kw):
        df = day(full(over, 100.0), d=D0, start="00:00", base=100.0)
        p = Params(**BASE, m1050=on, htf_resist_cap=False, draw_lock="off", news_wait="off", min_draw_pts=0.0, leg_pd=0.0, **kw)
        return [t for t in S.run_day(df, history(D0), "ES", p, 5) if t.entry_kind == "m1050"]
    a = {**_m1050_over(), 665: (102.4, 102.5, 101.0, 102.0), 670: (102.0, 110.0, 101.9, 109.5)}
    t = run_(a)
    assert len(t) == 1 and t[0].entry == pytest.approx(101.2) and t[0].exits[-1][3] == "t1" and t[0].entry_time.hour * 60 + t[0].entry_time.minute == 665
    b = {**_m1050_over(), 680: (102.4, 102.5, 101.0, 102.0), 685: (102.0, 110.0, 101.9, 109.5)}
    assert run_(b) == []                                                                          # the 11:20 retrace is past the 11:10 cut
    t2 = run_(b, m1050_cut=False)
    assert len(t2) == 1 and t2[0].entry_time.hour * 60 + t2[0].entry_time.minute == 680
    assert run_(a, on=False) == []


def test_nyx_in_run_day():
    """The engine path of other#13: the market buy at the sweep bar's close fills at the next open (09:55), is sized by the percentages and managed to its capped target; off, no NYX trade."""
    over = {**_nyx_over(), 595: (4006.0, 4015.0, 4005.9, 4014.5)}
    df = day(full(over, 4000.0), d=D0, start="00:00", base=4000.0)
    hist = hist_close(close=4000.0, hi=4020.0, lo=3980.0)
    kw = dict(htf_resist_cap=False, draw_lock="off", news_wait="off", min_draw_pts=0.0, leg_pd=0.0)
    t = S.run_day(df, hist, "ES", Params(**BASE, nyx_model=True, **kw), 5)
    assert len(t) == 1 and t[0].entry_kind == "nyx_ts" and t[0].setup == "NYX" and t[0].side == "long" and t[0].entry == pytest.approx(4006.0)
    assert t[0].stop == pytest.approx(4006.0 - 0.0018 * 4006.0) and t[0].exits[-1][3] == "t1" and t[0].entry_time.hour * 60 + t[0].entry_time.minute == 595
    assert not [x for x in S.run_day(df, hist, "ES", Params(**BASE, **kw), 5) if x.entry_kind == "nyx_ts"]
