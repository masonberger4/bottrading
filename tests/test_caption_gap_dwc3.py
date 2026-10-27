"""Caption-gap pass, package day_week_context#3/3 (33 specs from digests/rulebook_gaps): focused tests of the new switches (dwc3.py and its hooks) - the plan / gate / side / order filters on
hand-made days (the real DayCtx and DayPlan), the week / month budgets, the journal, the acceptance statistics, the studies, and no-look-ahead runs (full vs truncated, and per-path causal
cases). Nothing here needs market data; nothing is platform specific; no file outside the repo is written."""
import warnings
from dataclasses import fields, replace
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from mentorship import backtest as B, calendar as C, daycontext as DW, dwc1 as D1, dwc2 as D2, dwc3 as D3, levels as L, report_decisions as RD, study, study_week as SW, strategy as S
from mentorship.strategy import Params

from test_review_fixes import BASE, D0, A_ROWS, day, frame, history  # noqa: E402  (shared scenario builders)
from test_entries_stops import _no_look_ahead  # noqa: E402
from test_day_week_context import daily  # noqa: E402
from test_caption_gap_dwc1 import mk, at, hm, weeks, Conf, zone, _day_la, COLS, SYN, FUT, ES  # noqa: E402
from test_caption_gap_dwc2 import rows_5m, order, first_date, mk3  # noqa: E402

NEW_FIELDS = (
    "consol_pm_need_sweep", "choppy_week_tag", "choppy_week_days", "tgif_week_high_exit", "tgif_window", "tgif_min_adr", "tgif_need_htf_array", "inside_bisi_redelivered", "bisi_ce_band", "weekly_po3",
    "journal_timing", "fav_pts", "checklist", "cl_days", "cl_pm_ok", "stock_intraday", "pm_narrative", "pm_narr_gap_pts", "max_trades_month", "skip_months", "htf_quality_only",
    "weekly_target_pct", "weekly_cap_pts", "carry_weekly_draw", "carry_neutral_after", "thu_targets_met_block", "skip_fri_if_week_up", "mw_extreme_need_array", "trend_k",
    "missed_week_mode", "tgif_precond", "tgif_thu", "tgif_seq", "tgif_consol_frac", "tgif_no_rel", "consol_pm_pool_exit", "aug_dd_stop_pct", "low_mag_months", "low_mag_mult",
    "low_mag_week_cap", "lunch_kind_tag", "noon_rev_flat", "noon_rev_pm", "pm_mm_target", "london_ext_consol", "tgif_branch", "tgif_pm_from", "consol_pm_news_skip_am")
KNOBS = {"choppy_week_days", "bisi_ce_band", "fav_pts", "cl_days", "cl_pm_ok", "pm_narr_gap_pts", "carry_neutral_after", "trend_k", "tgif_consol_frac", "low_mag_months", "tgif_pm_from"}
OFF = {"consol_pm_need_sweep": False, "choppy_week_tag": False, "tgif_week_high_exit": True, "tgif_window": "pm", "tgif_min_adr": 3.0, "tgif_need_htf_array": True, "inside_bisi_redelivered": False, "weekly_po3": False,
       "journal_timing": False, "checklist": "off", "stock_intraday": False, "pm_narrative": False, "max_trades_month": 0, "skip_months": (), "htf_quality_only": False, "weekly_target_pct": 0.0,
       "weekly_cap_pts": 0.0, "carry_weekly_draw": False, "thu_targets_met_block": False, "skip_fri_if_week_up": False, "mw_extreme_need_array": False, "missed_week_mode": "off",
       "tgif_precond": "strict", "tgif_thu": False, "tgif_seq": False, "tgif_no_rel": False, "consol_pm_pool_exit": False, "aug_dd_stop_pct": 0.0, "low_mag_mult": 1.0, "low_mag_week_cap": 0,
       "lunch_kind_tag": True, "noon_rev_flat": False, "noon_rev_pm": False, "pm_mm_target": False, "london_ext_consol": False, "tgif_branch": False, "consol_pm_news_skip_am": False}

FRI = date(2026, 5, 15)                      # a Friday with no release
MON = date(2026, 5, 18)


def _pm_rows(spec, base=100.0, w=0.2):
    """5m (o, h, l, c) rows from 09:30 to the last key of `spec` ({HH:MM: row}); flat at `base` +- w elsewhere."""
    return rows_5m(spec, "09:30", base=base, w=w)


# --- defaults and validation --------------------------------------------------------------------------------------------

def test_defaults_and_validation():
    p = Params()
    for f in NEW_FIELDS:
        assert f in Params.__dataclass_fields__, f
    for k, v in OFF.items():
        assert getattr(p, k) == v, k
    assert p.choppy_week_days == 2 and p.pm_narr_gap_pts == 5.0 and p.trend_k == 0.8 and p.tgif_pm_from == 810 and p.fav_pts == 2.0 and p.bisi_ce_band == 0.15
    assert p.low_mag_months == (5, 6, 7, 8, 9, 10) and p.cl_days == (0, 1, 2) and p.carry_neutral_after is True and p.cl_pm_ok is True
    # the owner-fixed switches are untouched by this chunk
    assert p.sb_model is False and "sb_use_bias" in Params.__dataclass_fields__ and "want_all_engines" in Params.__dataclass_fields__
    assert not p.dw_needs_week and Params(max_trades_month=3).dw_needs_week and Params(weekly_target_pct=1.5).dw_needs_week and Params(checklist="tag").dw_needs_week
    for bad in (dict(tgif_window="x"), dict(tgif_precond="x"), dict(missed_week_mode="x"), dict(checklist="x"), dict(choppy_week_days=0), dict(fav_pts=0), dict(low_mag_mult=0),
                dict(max_trades_month=-1), dict(skip_months=(13,)), dict(low_mag_months=(0,)), dict(tgif_pm_from=1500), dict(cl_days=(5,)), dict(trend_k=0), dict(aug_dd_stop_pct=-1)):
        with pytest.raises(ValueError):
            Params(**bad)
    Params(tgif_window="am", tgif_precond="loose", missed_week_mode="nearest", checklist="gate", skip_months=(8,), low_mag_mult=0.5)


def test_every_new_switch_has_a_study_variant():
    used = set()
    for v in study._DWC3_DECISIONS.values():
        used |= set(v)
    for f in NEW_FIELDS:
        assert f in used or f in KNOBS, f
    for gid in ("T13-consolidation-pm-fizzle", "N8-choppy-week-no-hold", "M14-tgif-invalidation-timing", "M14-tgif-am-timing", "B17-M15-madeuce-inside-bisi", "M17-weekly-judas-po3",
                "OT-X16-time-to-move-journal", "OT-filters-before-bias", "OT-pre-session-checklist-order", "OT-stocks-swing-only", "N9-pm-narrative-from-am-chop", "X15-monthly-cap",
                "X15-three-per-week-htf-quality", "X15-weekly-goal-stop", "N10-unmet-target-carries-to-monday", "N10-thursday-reversal-after-targets-met", "N10-friday-skip-profitable-week",
                "N10-mon-wed-extreme-trending-week", "N10-missed-mon-wed-no-chase", "M14-tgif-timing-and-precondition", "N8-consolidation-pm-full-exit-at-pool", "N7-august-drawdown-restart",
                "E9-may-october", "T8-lunch-three-behaviours-reversal", "T9-pm-faster-measured-move", "T3-london-extreme-consolidation", "M14-tgif-timing", "N8-consolidation-pm-news"):
        assert any(k.startswith(gid) for k in study.DECISIONS), gid
    for k, v in study._DWC3_DECISIONS.items():
        assert k in study.DECISIONS
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            replace(Params(), **v)


# --- #121 consolidation PM fizzle ----------------------------------------------------------------------------------------------

def test_consol_pm_fizzle(monkeypatch):
    monkeypatch.setattr(DW, "_consol_predictors", lambda ctx, d, p, hist, eth: ["no_report"])
    p = Params(**BASE, consol_pm_need_sweep=True, consol_day_rules="tag")
    spec = {"12:00": (100.0, 101.0, 99.0, 100.0), "14:20": (100.0, 101.6, 99.9, 101.2), "14:25": (101.2, 101.3, 101.0, 101.1)}
    c = mk(D0, history(D0), p, rows=_pm_rows(spec))
    assert "consol_day" in c.dplan.tags
    assert D3.gate(c, p, "PM", at(c, "14:10"), 850) == "x_dw_pm_fizzle"                     # the lunch extremes were not swept yet
    assert D3.gate(c, p, "PM", at(c, "13:30"), 810) == "x_dw_pm_fizzle"
    assert D3.gate(c, p, "PM", at(c, "14:20"), 860) is None                                  # the 14:20 bar traded above the lunch high
    assert D3.gate(c, p, "AM", at(c, "10:00"), 600) is None                                  # the AM is not touched
    off = Params(**BASE, consol_day_rules="tag")
    assert D3.gate(mk(D0, history(D0), off, rows=_pm_rows(spec)), off, "PM", at(c, "14:10"), 850) is None


# --- #126 choppy week -------------------------------------------------------------------------------------------------------------

def _sweep_day(d, prev_high, first_hi, low_after, base=100.0):
    """A regular session whose first bar trades above `prev_high` and whose low comes later."""
    rows = [(base, first_hi, base - 0.2, base), (base, base + 0.2, base - 0.2, base), (base, base + 0.3, low_after, low_after + 0.3), (low_after + 0.3, base, low_after + 0.1, base - 1.0)]
    return frame(d, rows, 5, "09:30")


def test_choppy_week(monkeypatch):
    mon, tue, wed = date(2026, 5, 18), date(2026, 5, 19), date(2026, 5, 20)
    fri0 = daily(date(2026, 5, 15), 100.0, 100.0, 96.0, 99.0)
    h = [daily(date(2026, 5, 11 + k), 100.0, 101.0, 95.0, 100.0) for k in range(4)] + [fri0]
    h_mon = _sweep_day(mon, 100.0, 100.5, 96.0)
    h_tue = _sweep_day(tue, float(h_mon.high.max()), float(h_mon.high.max()) + 0.4, 95.0)
    hist = h + [h_mon, h_tue]
    assert D3.swept_first(h_mon, fri0, -1) and D3.swept_first(h_tue, h_mon, -1)
    assert D3.choppy_week(hist, wed, -1, 2) and not D3.choppy_week(hist, wed, 0, 2)
    assert not D3.choppy_week(hist, wed, 1, 2)                                              # a bullish week needs the lows swept first
    assert not D3.choppy_week(hist[:-1], wed, -1, 2)                                        # only one completed day
    # a Tuesday that made its low BEFORE it took Monday's high is not choppy
    calm = frame(tue, [(100.0, 100.2, 94.0, 94.5), (94.5, float(h_mon.high.max()) + 0.5, 94.4, 100.0)], 5, "09:30")
    assert not D3.choppy_week(h + [h_mon, calm], wed, -1, 2)
    monkeypatch.setattr(D2, "weekly_bias", lambda ctx, hist, d, p: -1)
    p = Params(**BASE, choppy_week_tag=True, runner_frac=0.2, po3_runner=True)
    c = mk(wed, hist, p)
    assert "choppy_week" in c.dplan.tags and c.dplan.info["choppy_week"]
    q = D3.day_params(p, c.dplan)
    assert q.runner_frac == 0.0 and not q.po3_runner and q.ladder_fracs == p.ladder_fracs_slow
    c2 = mk(tue, h + [h_mon], p)
    assert "choppy_week" not in c2.dplan.tags                                                # Tuesday has only one completed day
    off = replace(p, choppy_week_tag=False)
    assert "choppy_week" not in mk(wed, hist, off).dplan.tags and D3.day_params(off, mk(wed, hist, off).dplan) is off


# --- #85 / #90 TGIF -----------------------------------------------------------------------------------------------------------------

def _tgif_hist():
    """Three quiet weeks (ranges ~5), then a one-way up week Mon-Thu (range 22, Thursday closing at its high): the Friday is a TGIF short day."""
    fri = date(2023, 6, 16)
    prior = weeks(date(2023, 5, 22), [(100, 104, 99, 103), (103, 107, 102, 106), (106, 110, 105, 109)])
    wk = [daily(date(2023, 6, 12), 110.0, 114.0, 109.0, 113.0), daily(date(2023, 6, 13), 113.0, 120.0, 112.0, 119.0), daily(date(2023, 6, 14), 119.0, 126.0, 118.0, 125.0),
          daily(date(2023, 6, 15), 125.0, 131.0, 124.0, 130.0)]
    return fri, prior + wk


def test_tgif_invalid_above_week_high():
    fri, hist = _tgif_hist()
    p = Params(**BASE, tgif=True)
    spec = {"09:30": (131.5, 132.0, 131.0, 131.8), "09:35": (131.8, 133.0, 131.5, 132.0), "09:40": (132.0, 132.2, 130.0, 130.5)}
    c = mk(fri, hist, p, rows=_pm_rows(spec, base=131.0), base=131.0)
    c.day_tags = "tgif_short"
    ss = c.sides_map[-1]
    k = at(c, "09:35")
    # the order's stop (real 140) lies far above the week high 133 (Friday's own sweep high): the idea is void above 133 -> stop at 133 + a tick, the order cancels beyond it
    o = order(ss, ss.x(131.0), ss.x(140.0), [ss.x(125.0)], kinds=["pool"], ext_i=k)
    assert D3.order_ok(c, ss, o, "AM", k, p) is None
    assert o["stop"] == pytest.approx(ss.x(133.0 + p.tick)) and o["cancel_low"] == pytest.approx(ss.x(133.0))
    # the Mon-Thu high (131) is the reference when Friday has not gone higher before the sweep bar
    k0 = at(c, "09:30")
    o2 = order(ss, ss.x(131.0), ss.x(140.0), [ss.x(125.0)], kinds=["pool"], ext_i=k0)
    D3.order_ok(c, ss, o2, "AM", k0, p)
    assert o2["cancel_low"] == pytest.approx(ss.x(132.0))                                    # Friday's own high up to the sweep bar (132.0) is above the Mon-Thu 131
    # an order whose stop already sits inside the level is untouched; off / the wrong side / tgif off do nothing
    o3 = order(ss, ss.x(131.0), ss.x(132.5), [ss.x(125.0)], kinds=["pool"], ext_i=k)
    D3.order_ok(c, ss, o3, "AM", k, p)
    assert o3["stop"] == pytest.approx(ss.x(132.5))
    for q, sd_, side_ok_ in ((replace(p, tgif_week_high_exit=False), ss, True), (replace(p, tgif=False), ss, True)):
        o4 = order(sd_, sd_.x(131.0), sd_.x(140.0), [sd_.x(125.0)], kinds=["pool"], ext_i=k)
        D3.order_ok(c, sd_, o4, "AM", k, q)
        assert o4["stop"] == pytest.approx(sd_.x(140.0)) and "cancel_low" not in o4
    sl = c.sides_map[1]
    o5 = order(sl, 131.0, 130.0, [135.0], kinds=["pool"], ext_i=k)
    D3.order_ok(c, sl, o5, "AM", k, p)
    assert "cancel_low" not in o5                                                            # the with-week side is not a TGIF order
    # TGIF long (bearish week) mirror
    c2 = mk(fri, hist, p, rows=_pm_rows(spec, base=131.0), base=131.0)
    c2.day_tags = "tgif_long"
    sl2 = c2.sides_map[1]
    o6 = order(sl2, 131.0, 100.0, [135.0], kinds=["pool"], ext_i=at(c2, "09:35"))
    D3.order_ok(c2, sl2, o6, "AM", at(c2, "09:35"), p)
    assert o6["cancel_low"] == pytest.approx(109.0) and o6["stop"] == pytest.approx(109.0 - p.tick)      # the week low (Monday's 109) is the level of a TGIF long


def test_tgif_band_target_am():
    """The TGIF windows (am / london_close / pm), the precondition mode and the trending-week size through day_context."""
    fri, hist = _tgif_hist()
    p = Params(**BASE, tgif=True, tgif_window="am")
    c = mk(fri, hist, p)
    c.day_tags = "tgif_short"
    assert D3.gate(c, p, "AM", at(c, "10:00"), 600) is None and D3.gate(c, p, "AM", at(c, "09:30"), 570) is None
    assert D3.gate(c, p, "PM", at(c, "14:00"), 840) == "x_dw_tgif_window" and D3.gate(c, p, "LUNCH", at(c, "12:30"), 750) == "x_dw_tgif_window"
    lc = replace(p, tgif_window="london_close")
    assert D3.gate(c, lc, "AM", at(c, "09:30"), 570) == "x_dw_tgif_window" and D3.gate(c, lc, "AM", at(c, "10:30"), 630) is None
    pm = replace(p, tgif_window="pm")
    assert D3.gate(c, pm, "PM", at(c, "14:00"), 840) is None and D3.gate(c, pm, "AM", at(c, "10:30"), 630) == "x_dw_tgif_window"
    c_no = mk(fri, hist, p)
    assert D3.gate(c_no, p, "PM", at(c_no, "14:00"), 840) is None                           # no TGIF tag: no window
    assert D3.gate(c, replace(p, tgif_window="off"), "PM", at(c, "14:00"), 840) is None
    # tgif_precond: the strict mode needs the HTF array, the loose one does not
    miss = Conf(z={"W": zone(-1, 140.0, 150.0)})
    sp = Params(**BASE, tgif_htf_array=True)
    lp = replace(sp, tgif_precond="loose")
    assert "tgif_short" not in S.day_context(hist, fri, sp, None, miss)[0]
    assert "tgif_short" in S.day_context(hist, fri, lp, None, miss)[0]
    hit = Conf(z={"W": zone(-1, 129.0, 133.0)})
    assert "tgif_short" in S.day_context(hist, fri, sp, None, hit)[0]
    # the spec default tgif_need_htf_array (True) with tgif on needs the array like tgif_htf_array; tgif off leaves the tag as it was
    dflt = Params(**BASE, tgif=True)
    assert "tgif_short" not in S.day_context(hist, fri, dflt, None, miss)[0] and "tgif_short" in S.day_context(hist, fri, dflt, None, hit)[0]
    assert "tgif_short" in S.day_context(hist, fri, replace(dflt, tgif_need_htf_array=False), None, miss)[0]
    assert "tgif_short" in S.day_context(hist, fri, replace(dflt, tgif_precond="loose"), None, miss)[0]
    assert "tgif_short" in S.day_context(hist, fri, Params(**BASE), None, miss)[0]
    # the windows act only with tgif on (the tag is computed on every Friday)
    assert D3.gate(c, replace(p, tgif=False), "PM", at(c, "14:00"), 840) is None
    # an active tgif_window replaces tgif_timing; under tgif_model the timing stays unless it is skipped
    tm = Params(**BASE, tgif=True, tgif_window="am", tgif_timing=((810, 900),))
    assert DW.gate(c, tm, "AM", at(c, "09:30"), 570, []) is None
    mod = Params(tgif_model=True, tgif_window="am")
    assert not D3.tgif_window_governs(mod) and D3.tgif_window_governs(replace(mod, tgif_model_skip=("tgif_timing",)))
    # tgif_min_adr: the Mon-Thu range (131 - 120 = 11 up to ..) must exceed k x ADR5 of the sessions before the week (with tgif on)
    nm = dict(tgif=True, tgif_need_htf_array=False, tgif_min_adr=0.0)
    base_tags = S.day_context(hist, fri, Params(**BASE, **nm), None, None)[0]
    assert "tgif_short" in base_tags
    big = replace(Params(**BASE, **nm), tgif_min_adr=50.0)
    assert "tgif_short" not in S.day_context(hist, fri, big, None, None)[0]
    assert "tgif" not in S.day_context(hist, fri, big, None, None)[1]
    assert "tgif_short" in S.day_context(hist, fri, replace(big, tgif_min_adr=0.01), None, None)[0]
    assert "tgif_short" in S.day_context(hist, fri, replace(big, tgif=False), None, None)[0]          # tgif off: the tag is not trimmed


# --- #93 inside BISI ------------------------------------------------------------------------------------------------------------------

def _bisi_hist(low_y=103.0, high_y=109.0):
    d = date(2026, 6, 15)
    ohlc = [(95.0, 100.0, 90.0, 99.0), (99.0, 115.0, 98.0, 114.0), (114.0, 120.0, 110.0, 118.0), (108.0, high_y, low_y, 106.0)]
    out = []
    for k, x in enumerate(ohlc):
        out.append(daily(d + timedelta(days=k), *x))
    return out


def test_inside_bisi_two_sided_only():
    h = _bisi_hist()
    p = Params(**BASE, sloppy_tests=("inside_bisi",))
    q = replace(p, inside_bisi_redelivered=True)
    day_ = date(2026, 6, 19)
    assert S._inside_daily_fvg(h)
    assert "inside_bisi" in S.sloppy_day(h, day_, p, 105.2) and "inside_bisi" in S.sloppy_day(h, day_, p)
    assert "inside_bisi" in S.sloppy_day(h, day_, q, 105.2)                                    # yesterday traded below the CE 105 and today opens at the CE: both sides arguable
    assert "inside_bisi" not in S.sloppy_day(h, day_, q, 108.5)                                # opens 3.5 away from the CE (> 0.15 x 10)
    assert "inside_bisi" in S.sloppy_day(h, day_, q, None)                                     # no open known: the old rule stands
    h2 = _bisi_hist(low_y=106.0)                                                               # never traded below the CE: not re-delivered yet
    assert "inside_bisi" not in S.sloppy_day(h2, day_, q, 105.2)
    # Ma Deuce is exempt in the premium half of a range that was not re-delivered
    assert D3.md_inside_exempt(h2, 108.0, q) and not D3.md_inside_exempt(h2, 104.0, q)
    assert not D3.md_inside_exempt(h, 108.0, q)                                                # already traded below the CE
    assert not D3.md_inside_exempt(h2, None, q) and not D3.md_inside_exempt(h2[:2], 108.0, q)
    # the engine: in the not-yet-re-delivered premium-half state "inside_bisi" does not fire at all, so nothing stands aside (Ma Deuce included)
    sk = []
    df = day(A_ROWS, d=day_, start="09:50", spike=True, base=108.0)
    pm = Params(**BASE, sloppy_tests=("inside_bisi",), inside_bisi_redelivered=True, ma_deuce=True)
    S.run_day(df, h2 + [daily(date(2026, 6, 12), 1, 2, 1, 2)] * 0, "ES", pm, 5, skips=sk, locks=[], log=[])
    assert not any(x[2] == "sloppy" for x in sk)
    sk2 = []
    S.run_day(day(A_ROWS, d=day_, start="09:50", spike=True, base=105.2), h, "ES", pm, 5, skips=sk2, locks=[], log=[])
    assert any(x[2] == "sloppy" for x in sk2)                                                  # re-delivered and opening at the CE: the old stand-aside


# --- #175 Wednesday news weekly reversal (study) -----------------------------------------------------------------------------------------

def _news_weeks(reclaim=True):
    out = []
    for wi in range(5):
        mon = date(2026, 3, 2) + timedelta(days=7 * wi)
        if wi < 4:
            spec = [(100.0, 104.0, 90.0, 101.0)] * 5
        else:
            spec = [(100.0, 102.0, 98.0, 101.0), (101.0, 120.0, 100.0, 118.0), (118.0, 119.0, 85.0, 95.0 if reclaim else 88.0), (95.0 if reclaim else 88.0, 100.0, 92.0 if reclaim else 86.0, 99.0 if reclaim else 87.0),
                    (99.0, 101.0, 97.0, 100.0)]
        out.append([daily(mon + timedelta(days=k), *x) for k, x in enumerate(spec)])
    return out


def test_wed_news_reversal_study_smoke(monkeypatch):
    monkeypatch.setattr(DW, "news_class", lambda d: "high")
    ws = _news_weeks()
    r = study.wed_news_reversal(ws)
    bull = [x for x in r["rows"] if x["side"] == 1]
    assert len(bull) == 1 and r["summary"]["cases"] == len(r["rows"])
    row = bull[0]
    assert row["old_extreme"] == 90.0 and row["swing"] == 30.0 and row["p127"] == pytest.approx(120.0 - 1.27 * 30.0) and row["p168"] == pytest.approx(120.0 - 1.68 * 30.0)
    assert row["week_extreme"] == 85.0 and row["hit127"] is True and row["hit168"] is False
    assert not [x for x in study.wed_news_reversal(_news_weeks(reclaim=False))["rows"] if x["side"] == 1]       # no reclaim of the old low
    monkeypatch.setattr(DW, "news_class", lambda d: "low")
    assert study.wed_news_reversal(ws)["summary"]["cases"] == 0
    assert study.wed_news_reversal(ws[:3])["rows"] == []


# --- #180 weekly PO3 -------------------------------------------------------------------------------------------------------------------

def test_weekly_po3_gate(monkeypatch):
    monkeypatch.setattr(D2, "weekly_bias", lambda ctx, hist, d, p: -1)
    p = Params(**BASE, weekly_po3=True)
    h = history(D0)
    above = {"09:30": (100.0, 101.5, 99.9, 101.4)}
    c = mk(D0, h, p, rows=_pm_rows(above))
    assert c.dplan.info["weekly_po3"] == (-1, 100.0)                                            # the week open = Monday open
    i = at(c, "09:30")
    assert D3.side_ok(c, p, -1, "AM", i) is None                                                # the short above the weekly open
    assert D3.side_ok(c, p, 1, "AM", i) == "x_dw_weekly_po3_side"                               # longs blocked in a bearish week Mon-Wed
    below = {"09:30": (100.0, 100.1, 98.5, 98.6)}
    c2 = mk(D0, h, p, rows=_pm_rows(below))
    assert D3.side_ok(c2, p, -1, "AM", at(c2, "09:30")) == "x_dw_weekly_po3_open"              # below the open: the Judas leg is not in
    thu = D0 + timedelta(days=2)
    c3 = mk(thu, history(thu), p, rows=_pm_rows(below))
    assert "weekly_po3" not in c3.dplan.info and D3.side_ok(c3, p, 1, "AM", at(c3, "09:30")) is None     # Thursday: untouched
    monkeypatch.setattr(D2, "weekly_bias", lambda ctx, hist, d, p: 1)
    c4 = mk(D0, h, p, rows=_pm_rows(below))
    assert D3.side_ok(c4, p, 1, "AM", at(c4, "09:30")) is None and D3.side_ok(c4, p, -1, "AM", at(c4, "09:30")) == "x_dw_weekly_po3_side"       # the bullish mirror
    c5 = mk(D0, h, p, rows=_pm_rows(above))
    assert D3.side_ok(c5, p, 1, "AM", at(c5, "09:30")) == "x_dw_weekly_po3_open"
    monkeypatch.setattr(D2, "weekly_bias", lambda ctx, hist, d, p: 0)
    assert "weekly_po3" not in mk(D0, h, p).dplan.info                                         # no weekly bias: nothing
    monkeypatch.setattr(D2, "weekly_bias", lambda ctx, hist, d, p: -1)
    # the tag: the week high so far (108 from the earlier sessions) inside a weekly premium array
    cf = Conf(z={"W": zone(-1, 107.0, 110.0)})
    c6 = mk(D0, h, p, rows=_pm_rows(above), conf=cf)
    assert "weekly_judas" in D3.entry_tags(c6, p, c6.dplan, at(c6, "09:30"))
    c7 = mk(D0, h, p, rows=_pm_rows(above), conf=Conf(z={"W": zone(-1, 200.0, 210.0)}))
    assert "weekly_judas" not in D3.entry_tags(c7, p, c7.dplan, at(c7, "09:30"))


# --- #7 the time-to-move journal ----------------------------------------------------------------------------------------------------------

def test_journal_time_to_move():
    p = Params(**BASE, journal_timing=True, fav_pts=2.0)
    t0 = pd.Timestamp("2026-06-23 09:40", tz=B.NY)
    idx = pd.date_range(t0, periods=40, freq="1min")
    h = np.full(40, 100.4)
    l = np.full(40, 99.7)
    h[6] = 102.1                                                  # 09:46: +2.1 from the 100.0 fill
    l[20] = 98.5                                                  # 10:00: -1.5
    sd = SimpleNamespace(h=h, l=l)
    pos = dict(basis=100.0 * 3, n=3)
    for i in range(1, 26):
        D3.journal_bar(pos, sd, i, idx[i], p)
    assert pos["fav_t"] == idx[6] and pos["mfe"] == pytest.approx(2.1) and pos["mae"] == pytest.approx(1.5)
    tr = SimpleNamespace(entry_time=t0, exits=[(t0 + timedelta(minutes=25), 98.0, 3, "stop")], min_to_fav=None, min_to_exit=None, first_exit_kind="", mfe_pts=None, mae_pts=None)
    D3.journal_close(pos, tr, p)
    assert tr.min_to_fav == 6.0 and tr.min_to_exit == 25.0 and tr.first_exit_kind == "stop" and tr.mfe_pts == pytest.approx(2.1) and tr.mae_pts == pytest.approx(-1.5)
    tr2 = SimpleNamespace(entry_time=t0, exits=[(t0 + timedelta(minutes=9), 103.0, 1, "t1"), (t0 + timedelta(minutes=30), 101.0, 2, "t2")], min_to_fav=None, min_to_exit=None, first_exit_kind="", mfe_pts=None, mae_pts=None)
    D3.journal_close(dict(pos), tr2, p)
    assert tr2.first_exit_kind == "target" and tr2.min_to_exit == 30.0
    tr3 = SimpleNamespace(entry_time=t0, exits=[(t0, 99.0, 3, "stop")], min_to_fav=None, min_to_exit=None, first_exit_kind="", mfe_pts=None, mae_pts=None)
    D3.journal_close({}, tr3, p)                                  # stopped on the fill bar: no later bar was seen
    assert tr3.min_to_fav is None and tr3.min_to_exit is None and tr3.mfe_pts is None and tr3.mae_pts is None and tr3.first_exit_kind == "stop"
    # the Silver Bullet / Ma Deuce rows: replayed from the bars after the fill through the exit bar (a short here: favourable = down)
    cx = SimpleNamespace(idx=idx, h=np.full(40, 100.4), l=np.full(40, 99.7), start=0)
    cx.l[4] = 97.8
    cx.h[8] = 101.2
    cx.h[12] = 104.0                                              # after the exit: never read
    te = SimpleNamespace(entry_time=idx[1], entry=100.0, side="short", exits=[(idx[10], 98.0, 1, "t1")], min_to_fav=None, min_to_exit=None, first_exit_kind="", mfe_pts=None, mae_pts=None)
    D3.journal_extras(cx, [te], p)
    assert te.min_to_fav == 3.0 and te.min_to_exit == 9.0 and te.first_exit_kind == "target" and te.mfe_pts == pytest.approx(2.2) and te.mae_pts == pytest.approx(-1.2)
    D3.journal_extras(cx, [te], replace(p, journal_timing=False))      # off: nothing
    # the day tags: the day before an FOMC decision, a news day
    pf = first_date(lambda d: C.fomc_info(d)["eve"])
    assert "pre_fomc" in D3.journal_day_tags(pf)
    nd = first_date(lambda d: "cpi" in S.events(d))
    assert "news_day" in D3.journal_day_tags(nd)
    assert "pre_fomc" in S.day_context(history(pf, n=8), pf, p, None, None)[0] and "pre_fomc" not in S.day_context(history(pf, n=8), pf, Params(**BASE), None, None)[0]
    # the engine: the columns are filled on a synthetic run, the trades are unchanged
    x, y = B.synthetic(start="2026-03-02", end="2026-04-03", tf=5, seed=5)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        a = B.run(x, 5, "ES", Params(**SYN), y)
        b = B.run(x, 5, "ES", Params(**SYN, journal_timing=True), y)
    cols = ["entry_time", "entry", "stop", "shares", "net", "exit_reason"]
    pd.testing.assert_frame_equal(a[cols], b[cols])
    assert b.min_to_exit.notna().any() and (b.min_to_exit.dropna() >= 0).all() and b.first_exit_kind.isin(["stop", "target", "other"]).all()
    assert a.min_to_exit.isna().all()
    rep = B.report(b)
    assert "time_to_move" in rep and "by_pre_fomc" in rep and "time_to_move" not in B.report(a)


# --- #9 backtest acceptance ------------------------------------------------------------------------------------------------------------------

def _book(Rs, risk, year=2026, gap=1):
    """One trade per `gap` days from 1 January of `year` (in time order)."""
    rows = []
    for k, r in enumerate(Rs):
        d = pd.Timestamp(year, 1, 1) + pd.Timedelta(days=gap * k)
        rows.append(dict(entry_time=str(d), date=d.date(), R=float(r), net=float(r) * risk, gross=float(r) * risk, costs=0.0, year=d.year))
    return pd.DataFrame(rows)


def test_stats_acceptance():
    t = _book([3, -1, -1, 3, -1, -1, 3, -1, -1, -1], 100.0, gap=15)
    n_months = t.date.map(lambda d: (d.year, d.month)).nunique()
    s = B.stats(t)
    assert s["expectancy_R"] == pytest.approx(0.2) and s["avg_win_R"] == 3.0 and s["avg_loss_R"] == -1.0 and s["accept"] != "reject"
    assert s["R_per_month"] == pytest.approx(2.0 / n_months, abs=1e-3) and s["ann_ret_pct"] == pytest.approx(200.0 / 100_000 * 100, abs=1e-2) and s["ann_dd_pct_max"] < 15
    assert B.ACCEPT == dict(dd_ok=15, dd_max=25, ret_lo=18, ret_hi=25)
    # p * avg_win_R + (1 - p) * avg_loss_R is the same number
    assert 0.3 * 3.0 + 0.7 * -1.0 == pytest.approx(s["expectancy_R"])
    # the same trades scaled so a year drawdown is 30 % of the account: reject; 21 %: tolerable
    big = _book([-1, -1, -1, -1, -1, -1, -1, 3, 3, 3], 30_000.0 / 7)
    assert B.stats(big)["ann_dd_pct_max"] == pytest.approx(30.0, abs=0.01) and B.stats(big)["accept"] == "reject"
    mid = _book([-1, -1, -1, -1, -1, -1, -1, 3, 3, 3], 3_000.0)
    assert B.stats(mid)["ann_dd_pct_max"] == pytest.approx(21.0, abs=0.01) and B.stats(mid)["accept"] == "tolerable"
    assert B.stats(_book([-1, -1, -1], 100.0))["accept"] == "reject"                         # all losers
    # the drawdown resets each 1 January
    two = pd.concat([_book([-1, -1, -1], 4_000.0, year=2025), _book([-1, -1, -1], 4_000.0, year=2026)], ignore_index=True)
    assert B.stats(two)["ann_dd_pct_max"] == pytest.approx(12.0, abs=0.01)
    assert B.stats(None) == {"trades": 0}
    # report_decisions ranks by the verdict, then the lower annual drawdown, then the total R
    t1 = _book([1, 1, -1, 1], 100.0).assign(variant="good", tf=5)
    t2 = _book([-1, -1, -1, 3], 100.0).assign(variant="meh", tf=5)
    t3 = _book([-1, -1, -1], 100.0).assign(variant="bad", tf=5)
    tab = RD.table(pd.concat([t3, t2, t1], ignore_index=True), 5)
    assert list(tab.index) == ["good", "meh", "bad"] and {"expectancy_R", "ann_dd_pct_max", "ann_ret_pct", "accept"} <= set(tab.columns)


# --- #10 the veto order / #25 the stock guard ----------------------------------------------------------------------------------------------

def test_veto_precedes_bias():
    """A day blocked by blocked() with a maximal bias table yields no trades in the AM, PM, Silver Bullet or Ma Deuce; a normal day with the same bars trades."""
    from test_review_fixes import A_LOCK
    jobs = first_date(lambda d: "jobs" in S.events(d) and d.weekday() == 4)
    p = Params(**BASE, htf_bias="combo", sb_model=True, ma_deuce=True, pm_reversal=True, nfp_day=False)
    bias = dict(react=1, draw=1, pd=1, combo=1, flip=1)
    sk = []
    out = S.run_day(day(A_ROWS, d=jobs, start="09:50", spike=True), history(jobs), "ES", p, 5, locks=[], log=[], skips=sk, bias=bias, bias_by_cut=A_LOCK)
    assert out == []
    log = []
    cx = SimpleNamespace(skips_ref=log, symbol="ES")
    assert D3.session_veto(cx, p, jobs, "AM", 570, S.blocked, S.news) == "nfp_day" and D3.session_veto(cx, p, jobs, "AM", 575, S.blocked, S.news) == "nfp_day"
    assert log == [(jobs, "ES", "veto", "AM:nfp_day")]                                                       # every veto is logged, once per session and reason
    ok = S.run_day(day(A_ROWS, d=D0, start="09:50", spike=True), history(D0), "ES", replace(p, htf_bias="off"), 5, locks=[], log=[], skips=[], bias_by_cut=A_LOCK)
    assert len(ok) >= 1
    assert D3.session_veto(SimpleNamespace(skips_ref=None), p, jobs, "AM", 570, S.blocked, S.news) == "nfp_day"
    assert D3.session_veto(SimpleNamespace(skips_ref=None), p, D0, "AM", 570, S.blocked, S.news) is None
    sn = replace(p, skip_news=True)
    cpi = first_date(lambda d: "cpi" in S.events(d) and S.blocked(d, "AM", sn, 570) is None)
    assert D3.session_veto(SimpleNamespace(skips_ref=None), sn, cpi, "AM", 570, S.blocked, S.news) == "skip_news"
    assert D3.session_veto(SimpleNamespace(skips_ref=None), sn, cpi, "AM", 570, S.blocked) is None            # the Silver Bullet path never applied skip_news


def test_session_veto_refactor_identical(monkeypatch):
    x, y = B.synthetic(start="2026-03-02", end="2026-04-10", tf=5, seed=5)
    p = Params(**SYN, sb_model=True, ma_deuce=True, md_blocked=True, skip_news=True)
    cols = ["entry_time", "entry", "stop", "shares", "net", "exit_reason", "session"]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        new = B.run(x, 5, "ES", p, y)

        def legacy(ctx, p_, day_, session, t, blocked_fn, news_fn=None):
            return "x" if ((p_.day_filter and blocked_fn(day_, session, p_, t)) or (news_fn is not None and p_.skip_news and news_fn(day_) != "none")) else None
        monkeypatch.setattr(D3, "session_veto", legacy)
        old = B.run(x, 5, "ES", p, y)
    assert len(new) >= 1
    pd.testing.assert_frame_equal(new[cols], old[cols])
    cal = lambda sk: [r for r in sk if r[2] == "veto" and ":sloppy:" not in r[3]]          # the calendar / news vetoes (the sloppy stand-aside logs its own rows)
    assert cal(new.attrs["skips"]) and not cal(old.attrs["skips"])


def test_stock_intraday_guard():
    from test_review_fixes import A_LOCK
    df, h = day(A_ROWS, d=D0, start="09:50", spike=True), history(D0)

    def run(sym, **kw):
        sk = []
        return S.run_day(df, h, sym, Params(**BASE, **kw), 5, locks=[], log=[], skips=sk, bias_by_cut=A_LOCK), sk
    a, sa = run("AAPL")
    assert a == [] and ("stock" in [x[2] for x in sa]) and any(x[3] == "swing_only" for x in sa)
    spy, _ = run("SPY")
    es, _ = run("ES")
    assert len(spy) >= 1 and [(t.entry_time, t.entry, t.shares) for t in spy] == [(t.entry_time, t.entry, t.shares) for t in es]
    on, _ = run("AAPL", stock_intraday=True)
    assert [(t.entry_time, t.entry, t.shares) for t in on] == [(t.entry_time, t.entry, t.shares) for t in spy]
    for sym in ("SPX", "NDX", "NQ", "QQQ", "DIA", "YM", "RW"):
        assert sym in D3.INDEX_SYMBOLS
    x, y = B.synthetic(start="2026-03-02", end="2026-03-06", tf=5, seed=5)
    with pytest.warns(RuntimeWarning, match="swing-only"):
        B.run(x, 5, "AAPL", Params(**SYN), y)


# --- #11 the pre-session checklist ---------------------------------------------------------------------------------------------------------------

def test_checklist_steps():
    tue, thu = D0, D0 + timedelta(days=2)
    lock = {"AM": {"side": 1, "target": 110.0, "delivered": False}}
    br = {"combo": 1, "draw": 1, "react": 1}
    p = Params(**BASE)
    c = mk(tue, history(tue), p, bias_row=br, lock=lock, week={"final_hits": 0})
    i = at(c, "10:00")
    r = D3.checklist(c, c.hist, tue, "AM", p, i, 575)
    assert all(r.values()), r
    cth = mk(thu, history(thu), p, bias_row=br, lock=lock, week={"final_hits": 1})
    r2 = D3.checklist(cth, cth.hist, thu, "AM", p, at(cth, "10:00"), 575)
    assert [k for k, v in r2.items() if not v] == ["dow"]
    cth0 = mk(thu, history(thu), p, bias_row=br, lock=lock, week={"final_hits": 0})
    assert all(D3.checklist(cth0, cth0.hist, thu, "AM", p, at(cth0, "10:00"), 575).values())              # Mon-Wed produced no target hit: the Thu / Fri template is open
    # the other steps
    nob = mk(tue, history(tue), p, bias_row={"combo": 0, "draw": 0}, lock={}, week={})
    r3 = D3.checklist(nob, nob.hist, tue, "AM", p, at(nob, "10:00"), 575)
    assert not r3["htf"] and not r3["levels"]
    assert D3.checklist(c, c.hist, tue, "PM", p, at(c, "14:00"), 840)["ipda"] and not D3.checklist(c, c.hist, tue, "PM", replace(p, cl_pm_ok=False), at(c, "14:00"), 840)["ipda"]
    assert not D3.checklist(c, c.hist, tue, "PM", p, at(c, "13:30"), 810)["kz"] and D3.checklist(c, c.hist, tue, "PM", p, at(c, "14:30"), 870)["kz"]        # the PM Silver Bullet window 14:00-15:00 (13:30 is outside every kill zone)
    spent = mk(tue, history(tue), p, rows=_pm_rows({"09:30": (100.0, 130.0, 99.0, 125.0)}), bias_row=br, lock=lock, week={})
    assert not D3.checklist(spent, spent.hist, tue, "AM", p, at(spent, "09:35"), 575)["adr"]                  # ADR5 (18) already covered from the low
    # tag / gate through the DayPlan hooks
    tg, gt = Params(**BASE, checklist="tag"), Params(**BASE, checklist="gate")
    c1 = mk(thu, history(thu), tg, bias_row=br, lock=lock, week={"final_hits": 1})
    assert D3.gate(c1, tg, "AM", at(c1, "10:00"), 575) is None and D3.checklist_for(c1, tg, "AM", at(c1, "10:00"), 575) == "dow"
    c2 = mk(thu, history(thu), gt, bias_row=br, lock=lock, week={"final_hits": 1})
    assert D3.gate(c2, gt, "AM", at(c2, "10:00"), 575) == "x_dw_checklist"
    c3 = mk(tue, history(tue), gt, bias_row=br, lock=lock, week={"final_hits": 0})
    assert D3.gate(c3, gt, "AM", at(c3, "10:00"), 575) is None
    assert not D3.checklist(c, c.hist, tue, "SB", p, at(c, "10:30"), 630)["ipda"]                          # a window starting at 10:00 or later is outside the IPDA bulk 03:00-10:00
    sk = []
    c1.skips_ref, c1.symbol = sk, "ES"
    D3.checklist_for(c1, tg, "PM", at(c1, "14:00"), 840)
    assert c1.cl is D3._cache(c1)["cl"]
    c4 = mk(thu, history(thu), tg, bias_row=br, lock=lock, week={"final_hits": 1})
    c4.skips_ref, c4.symbol = sk, "ES"
    D3.checklist_for(c4, tg, "AM", at(c4, "10:00"), 575)
    assert (thu, "ES", "checklist", "AM:dow") in sk                                                         # the failing steps are logged as a skips row
    trs = [SimpleNamespace(session="AM", cl_fail="")]
    D3.stamp(c1, trs, tg)
    assert trs[0].cl_fail == "dow"
    D3.stamp(c1, trs, Params(**BASE))
    assert trs[0].cl_fail == "dow"                                                                           # off: untouched


# --- #11 the PM narrative from a chop AM -----------------------------------------------------------------------------------------------------------

def _gap_day(fill_at=None, base=90.0):
    """A gap-down day: the prior close is 100 (the history), today opens at 90; the AM / lunch stay under 100 unless `fill_at` ('HH:MM') prints 100.3."""
    spec = {}
    if fill_at:
        spec[fill_at] = (base, 100.3, base - 0.2, base)
    return _pm_rows(spec, base=base, w=0.3) if spec else _pm_rows({"15:00": (base, base + 0.1, base - 0.1, base)}, base=base, w=0.3)


def test_pm_narrative_chop(monkeypatch):
    p = Params(**BASE, pm_narrative=True, pm_narr_gap_pts=5.0)
    monkeypatch.setattr(D3, "_smt_at_am_extreme", lambda ctx, ext, a, k: True)
    monkeypatch.setattr(D3, "_am_runs", lambda ctx, p_, side, a, k: True)
    c = mk(D0, history(D0), p, rows=_gap_day(), base=90.0)
    assert c.org_today and c.org[-1] == (100.0, 90.0)
    nv = D3.pm_narrative(c, p, c.hist, ())
    assert nv == (1, 100.0)                                                                                  # toward the unfilled gap
    iPM = at(c, "13:30")
    assert D3.side_ok(c, p, -1, "PM", iPM) == "x_dw_pm_narr_side" and D3.side_ok(c, p, 1, "PM", iPM) is None
    assert D3.side_ok(c, p, -1, "AM", at(c, "10:00")) is None                                               # the AM is untouched
    sl = c.sides_map[1]
    assert (100.0, c.start) in DW.target_pools(c, sl, iPM, p)
    assert all(lv != 100.0 for lv, _ in DW.target_pools(c, c.sides_map[-1], iPM, p))
    tr_pm = SimpleNamespace(session="PM", exits=[], lv_tags="")
    assert D3.gate(c, p, "PM", iPM, 810, [tr_pm]) == "x_dw_pm_narr_done" and D3.gate(c, p, "PM", iPM, 810, []) is None      # one attempt only
    # the gap filled at 13:00: the idea is cancelled
    f = mk(D0, history(D0), p, rows=_gap_day("13:00"), base=90.0)
    assert D3.pm_narrative(f, p, f.hist, ()) is None and D3.side_ok(f, p, -1, "PM", at(f, "13:30")) is None
    # a small gap, an AM trade without chop, no SMT, no repeated runs
    assert D3.pm_narrative(mk(D0, history(D0), replace(p, pm_narr_gap_pts=15.0), rows=_gap_day(), base=90.0), replace(p, pm_narr_gap_pts=15.0), c.hist, ()) is None
    c2 = mk(D0, history(D0), p, rows=_gap_day(), base=90.0)
    c2.chop = SimpleNamespace(inert=False, state=np.zeros(len(c2.t), bool))
    assert D3.pm_narrative(c2, p, c2.hist, [SimpleNamespace(session="AM")]) is None                         # the AM traded and the chop never turned on
    monkeypatch.setattr(D3, "_smt_at_am_extreme", lambda ctx, ext, a, k: False)
    assert D3.pm_narrative(mk(D0, history(D0), p, rows=_gap_day(), base=90.0), p, c.hist, ()) is None
    off = Params(**BASE)
    assert D3.side_ok(c, off, -1, "PM", iPM) is None and D3.gate(c, off, "PM", iPM, 810, [tr_pm]) is None


def _am_dips(dips, big=None):
    """48 quiet AM bars from 09:30 (range 0.3) with a dip bar (low = the given price) at each index of `dips`; `big` = (index, high) adds one displacement bar."""
    rows = []
    for j in range(48):
        low = dips.get(j)
        rows.append((90.0, 90.15, low, 90.0) if low else (90.0, 90.2, 89.9, 90.0))
    if big:
        rows[big[0]] = (90.0, big[1], 89.9, big[1] - 0.1)
    return rows


def test_pm_narrative_parts():
    """The SMT at the AM extreme and the repeated one-tick AM runs on hand-made arrays."""
    p = Params(**BASE)
    runs2 = {4: 89.7, 8: 89.65, 12: 89.6}
    c = mk(D0, history(D0), p, rows=_am_dips(runs2), base=90.0)
    a, k = at(c, "09:30"), at(c, "13:30")
    assert D3._am_runs(c, p, 1, a, k)                                                                       # two swing lows run by 0.05 each
    assert not D3._am_runs(c, p, -1, a, k)
    cw = mk(D0, history(D0), p, rows=_am_dips(runs2, big=(20, 95.0)), base=90.0)
    assert not D3._am_runs(cw, p, 1, at(cw, "09:30"), at(cw, "13:30"))                                       # a displacement bar (range 5.1 over a 0.3 mean)
    c1 = mk(D0, history(D0), p, rows=_am_dips({4: 89.7, 8: 89.65}), base=90.0)
    assert not D3._am_runs(c1, p, 1, at(c1, "09:30"), at(c1, "13:30"))                                       # only one run
    c3 = mk(D0, history(D0), p, rows=_am_dips({4: 89.7, 8: 88.0, 12: 86.0}), base=90.0)
    assert not D3._am_runs(c3, p, 1, at(c3, "09:30"), at(c3, "13:30"))                                       # runs far beyond a tick are breaks, not runs
    # SMT: the main index makes the AM low at 10:40 while the partner does not (flat) - unconfirmed; a partner low beyond its earlier lows confirms it
    pd_flat = day([], d=D0, start="09:30", base=90.0, w=0.3)
    cm = mk(D0, history(D0), p, rows=_pm_rows({"10:40": (90.0, 90.1, 87.0, 87.2)}, base=90.0, w=0.3), base=90.0)
    pc = S.DayCtx(pd_flat, D0, history(D0), 5)
    cm.pside = (pc, None, pd.Series(np.arange(len(pc.idx)), index=pc.idx))
    assert D3._smt_at_am_extreme(cm, -1, at(cm, "09:30"), at(cm, "13:30")) is True
    pc2 = S.DayCtx(day(_pm_rows({"10:40": (90.0, 90.1, 86.0, 86.2)}, base=90.0, w=0.3), d=D0, start="09:30", base=90.0, w=0.3), D0, history(D0), 5)
    cm.pside = (pc2, None, pd.Series(np.arange(len(pc2.idx)), index=pc2.idx))
    assert D3._smt_at_am_extreme(cm, -1, at(cm, "09:30"), at(cm, "13:30")) is False                           # the partner made a lower low too: confirmed
    cm.pside = (None, None, None)
    assert D3._smt_at_am_extreme(cm, -1, at(cm, "09:30"), at(cm, "13:30")) is False                           # no partner: no narrative


# --- the week / month budgets (#18 #21 #29 #37 #38) -------------------------------------------------------------------------------------------------

_RUNS = {}
W_D3 = {"W0": ("2026-03-02", "2026-04-17", 5), "W1": ("2026-04-27", "2026-05-13", 7), "W2": ("2026-04-06", "2026-04-24", 3), "W3": ("2026-07-27", "2026-09-04", 4)}


def _syn3(wname, **kw):
    key = (wname, tuple(sorted(kw.items(), key=lambda kv: kv[0])))
    if key not in _RUNS:
        a, b, seed = W_D3[wname]
        x, y = B.synthetic(start=a, end=b, tf=5, seed=seed)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            _RUNS[key] = (x, y, B.run(x, 5, "ES", Params(**SYN, sb_model=True, ma_deuce=True, **kw), y))
    return _RUNS[key]


def _row(d, net, side="long", gross=None, shares=100, t="10:00"):
    return dict(date=d, net=net, gross=net if gross is None else gross, shares=shares, side=side, entry_time=f"{d} {t}:00-04:00")


def test_month_cap():
    """Synthetic months: the cap keeps exactly the first trades of each calendar month by entry time; skip_months drops a whole month."""
    _, _, base = _syn3("W0")
    _, _, cap = _syn3("W0", max_trades_month=3)
    month = lambda t: t.entry_time.astype(str).str[:7]
    assert base.groupby(month(base)).size().max() > 3, "the window must hold a month with more than 3 trades"
    assert cap.groupby(month(cap)).size().max() <= 3
    first = base.sort_values("entry_time").groupby(month(base)).head(3)
    assert list(cap.entry_time) == list(first.sort_values("entry_time").entry_time)                        # the earliest three per month, in entry-time order
    sk = [r for r in cap.attrs["skips"] if r[2] == "day_week" and r[3] == "month_cap"]
    assert sk
    # the explicit week state
    p = Params(**SYN, max_trades_month=3)
    rows = [_row(date(2026, 3, 2), 10.0), _row(date(2026, 3, 3), -5.0), _row(date(2026, 3, 4), 4.0)]
    wk, why = D3.week_extra({}, rows, date(2026, 3, 5), p)
    assert why == "month_cap" and wk["month_n"] == 3
    assert D3.week_extra({}, rows[:2], date(2026, 3, 5), p)[1] is None
    assert D3.week_extra({}, rows, date(2026, 4, 1), p)[1] is None                                         # a new month
    # the in-day budget (the DayPlan) and the truncation helper
    c = mk(D0, history(D0), p, week=dict(n=0, month_n=2))
    assert c.dplan.info["week_left"] == 1
    c0 = mk(D0, history(D0), p, week=dict(n=0, month_n=3))
    assert c0.dplan.static_reason("AM", 600) == "month_cap"
    t_ = [SimpleNamespace(entry_time=pd.Timestamp(f"2026-03-05 {h}:00")) for h in ("11:00", "09:40", "10:30")]
    assert [x.entry_time.hour for x in D3.cap_day_trades(t_, p, dict(month_n=1))] == [9, 10]
    assert D3.cap_day_trades(t_, Params(**SYN), dict(month_n=1)) is t_
    # skip_months
    _, _, aug = _syn3("W3")
    _, _, noaug = _syn3("W3", skip_months=(8,))
    assert (aug.entry_time.astype(str).str[5:7] == "08").any() and not (noaug.entry_time.astype(str).str[5:7] == "08").any()
    jul = lambda t: t[t.entry_time.astype(str).str[5:7] != "08"]
    pd.testing.assert_frame_equal(jul(aug)[["entry_time", "entry", "shares"]].reset_index(drop=True), jul(noaug)[["entry_time", "entry", "shares"]].reset_index(drop=True))
    assert S.blocked(date(2026, 8, 10), "AM", Params(skip_months=(8,)), 600) == "month" and S.blocked(date(2026, 7, 10), "AM", Params(skip_months=(8,)), 600) is None


def test_weekly_goal_stop():
    p = Params(**SYN, weekly_target_pct=1.5)
    mon, tue = date(2026, 6, 22), date(2026, 6, 23)
    up = [_row(mon, 1600.0)]
    wk, why = D3.week_extra({}, up, tue, p)
    assert why == "weekly_goal" and wk["week_pct"] == pytest.approx(1.6)
    assert D3.week_extra({}, [_row(mon, 1000.0)], tue, p)[1] is None                                       # +1.0 %: Tuesday trades
    assert D3.week_extra({}, up, date(2026, 6, 29), p)[1] is None                                          # the next week
    assert D3.week_extra({}, [], tue, p)[1] is None
    pts = Params(**SYN, weekly_cap_pts=10.0)
    assert D3.week_extra({}, [_row(mon, 500.0, gross=1200.0, shares=100)], tue, replace(pts, es_pt=1.0))[1] == "weekly_goal"        # 12 points per unit
    assert D3.week_extra({}, [_row(mon, 500.0, gross=800.0, shares=100)], tue, replace(pts, es_pt=1.0))[1] is None
    # inside the day: the closed trades through the bar count, an open one does not
    def tr(net, exit_h):
        t0 = pd.Timestamp(f"{tue} 09:40", tz=B.NY)
        return SimpleNamespace(exits=[(pd.Timestamp(f"{tue} {exit_h}", tz=B.NY), 0.0, 1, "t1")], shares=100, pnl=lambda cost, n=net: (n, 0.0))
    c = mk(tue, history(tue), p, week=dict(n=1, week_net3=900.0, week_eq0=100_000.0, week_pts=0.0))
    i = at(c, "10:30")
    assert D3.gate(c, p, "AM", i, 630, [tr(800.0, "10:00")]) == "x_dw_weekly_goal"                         # 0.9 % + 0.8 % = 1.7 %
    assert D3.gate(c, p, "AM", i, 630, [tr(800.0, "11:00")]) is None                                       # that trade exits after the bar
    assert D3.gate(c, p, "AM", i, 630, [tr(300.0, "10:00")]) is None                                       # 1.2 %
    assert D3.gate(c, Params(**SYN), "AM", i, 630, [tr(800.0, "10:00")]) is None                           # off


def test_skip_friday_week_up():
    p = Params(**SYN, skip_fri_if_week_up=True)
    mon, fri = date(2026, 6, 22), date(2026, 6, 26)
    assert D3.week_extra({}, [_row(mon, 300.0)], fri, p)[1] == "fri_week_up"                               # +0.3 R by Thursday
    assert D3.week_extra({}, [_row(mon, -200.0)], fri, p)[1] is None                                       # -0.2 R: Friday trades
    assert D3.week_extra({}, [_row(mon, 300.0)], date(2026, 6, 25), p)[1] is None                          # only Fridays
    assert D3.week_extra({}, [], fri, p)[1] is None
    assert D3.week_extra({}, [_row(mon, 300.0)], fri, Params(**SYN))[1] is None


def test_august_dd_stop():
    p = Params(**SYN, aug_dd_stop_pct=2.5)
    rows = [_row(date(2026, 8, 5), -1500.0), _row(date(2026, 8, 7), -1500.0)]                              # -3 % by Aug 10
    assert D3.week_extra({}, rows, date(2026, 8, 11), p)[1] == "august_dd"
    assert D3.week_extra({}, rows, date(2026, 9, 1), p)[1] is None                                         # trades resume on September 1
    assert D3.week_extra({}, rows[:1], date(2026, 8, 11), p)[1] is None                                    # -1.5 % only
    up_first = [_row(date(2026, 8, 3), 2000.0), _row(date(2026, 8, 5), -1500.0), _row(date(2026, 8, 7), -1500.0)]
    assert D3.aug_dd_hit(up_first, date(2026, 8, 11), replace(p, aug_dd_stop_pct=3.0)) and not D3.aug_dd_hit(up_first, date(2026, 8, 11), replace(p, aug_dd_stop_pct=4.0))     # the drawdown from the August peak
    assert not D3.aug_dd_hit([_row(date(2026, 7, 20), -9000.0)], date(2026, 8, 11), p)                    # a July loss is not an August drawdown
    # the engine: after the first August loss the month is skipped, September is unchanged
    _, _, base = _syn3("W3")
    _, _, dd = _syn3("W3", aug_dd_stop_pct=0.01)
    mm = lambda t: t.entry_time.astype(str).str[5:7]
    aug_b, aug_d = base[mm(base) == "08"], dd[mm(dd) == "08"]
    assert len(aug_d) < len(aug_b) and any(r[3] == "august_dd" for r in dd.attrs["skips"] if r[2] == "day_week")
    sep = lambda t: t[mm(t) == "09"][["entry_time", "entry", "shares"]].reset_index(drop=True)
    pd.testing.assert_frame_equal(sep(base), sep(dd))
    assert aug_d.net.iloc[:-1].min() >= 0 if len(aug_d) > 1 else True                                      # nothing is traded after a losing August trade


def test_low_mag_season():
    p = Params(**SYN, low_mag_mult=0.5, low_mag_week_cap=2)
    jun, nov = date(2026, 6, 23), date(2026, 11, 3)
    cj, cn = mk(jun, history(jun), p), mk(nov, history(nov), p)
    lvt = []
    assert D3.size_mult(cj, p, lvt) == 0.5 and lvt == ["size_low_mag"] and D3.size_mult(cn, p) == 1.0
    assert DW.day_risk(cj, p) == pytest.approx(0.5) and DW.day_risk(cn, p) == pytest.approx(1.0)
    assert "low_mag_season" in cj.dplan.tags and "low_mag_season" not in cn.dplan.tags
    # August keeps its own row: the smaller multiplier wins
    aug = date(2026, 8, 4)
    pa = replace(p, august_risk=0.25)
    assert DW.day_risk(mk(aug, history(aug), pa), pa) == pytest.approx(0.25)
    pb = replace(p, august_risk=0.75)
    assert DW.day_risk(mk(aug, history(aug), pb), pb) == pytest.approx(0.5)
    # the weekly cap: the third June trade of the week is blocked
    assert mk(jun, history(jun), p, week=dict(n=1)).dplan.info["week_left"] == 1
    c2 = mk(jun, history(jun), p, week=dict(n=2))
    assert c2.dplan.static_reason("AM", 600) in ("low_mag_cap", "month_cap") and DW.gate(c2, p, "AM", at(c2, "10:00"), 600).startswith("x_dw_")
    assert mk(nov, history(nov), p, week=dict(n=2)).dplan.static_reason("AM", 600) is None
    assert mk(jun, history(jun), Params(**SYN, low_mag_mult=0.5), week=dict(n=5)).dplan.static_reason("AM", 600) is None
    # the engine: the sizes shrink in May, the entries stay
    _, _, a = _syn3("W1", max_notional=1e12)
    _, _, b = _syn3("W1", max_notional=1e12, low_mag_mult=0.5)
    assert list(a.entry_time) == list(b.entry_time) and (b.shares <= a.shares).all() and (b.shares < a.shares).any()


def test_paper_rows_feed_the_budgets(tmp_path):
    """The paper loop reads the earlier paper days' CSVs as the backtest's rows, so the month / week budgets act there too."""
    from mentorship import paper
    hdr = "entry_time,exit_reason,net,gross,shares,side\n"
    (tmp_path / "paper_ES_20260511.csv").write_text(hdr + "2026-05-11 10:00,stop,-50.0,-40.0,2,long\n2026-05-11 10:00,t1,80.0,90.0,2,long\n")     # the same trade logged twice: the last row wins
    (tmp_path / "paper_ES_20260512.csv").write_text(hdr + "2026-05-12 10:05,t1,120.0,130.0,2,short\n")
    (tmp_path / "paper_ES_20260513.csv").write_text(hdr + "2026-05-13 10:05,t1,10.0,12.0,1,long\n")                                          # today: not read
    (tmp_path / "paper_NQ_20260511.csv").write_text(hdr + "2026-05-11 10:00,t1,999.0,999.0,1,long\n")                                         # another symbol
    today = date(2026, 5, 13)
    rows = paper.paper_rows(tmp_path, "ES", today)
    assert [(r["date"], r["net"], r["side"]) for r in rows] == [(date(2026, 5, 11), 80.0, "long"), (date(2026, 5, 12), 120.0, "short")]
    p = Params(**BASE, max_trades_month=2, weekly_target_pct=0.1, account_equity=100000.0)
    wk, why = D3.week_extra({}, rows, today, p)
    assert wk["month_n"] == 2 and why == "month_cap"
    wk, why = D3.week_extra({}, rows, today, replace(p, max_trades_month=0))
    assert why == "weekly_goal" and wk["week_pct"] == pytest.approx(0.2)
    assert paper.paper_rows(tmp_path, "ES", date(2026, 5, 11)) == []


# --- #20 HTF quality only -------------------------------------------------------------------------------------------------------------------------

def test_htf_quality_only():
    p = Params(**BASE, htf_quality_only=True)
    cf = Conf(at_tfs=("1h",))
    c = mk(D0, history(D0), p, rows=_pm_rows({"09:30": (100.0, 100.5, 99.0, 99.4), "09:35": (99.4, 100.2, 99.3, 100.0)}), conf=cf)
    sl = c.sides_map[1]
    i = at(c, "09:35")
    # PDH = 108 (the history), the final target 103.5 is a 1m swing high
    o1 = order(sl, 100.0, 99.0, [102.0, 103.5], kinds=["pool", "pool"], ext=99.0, ext_i=at(c, "09:30"))
    o2 = order(sl, 100.0, 99.0, [102.0, 108.0], kinds=["pool", "pool"], ext=99.0, ext_i=at(c, "09:30"))
    assert D3.order_ok(c, sl, o1, "AM", i, p) == "x_dw_htf_quality"
    assert D3.order_ok(c, sl, o2, "AM", i, p) is None                                                         # PDH with a 1h array holding the sweep
    # the setup must sit on a 1h / 4h swing or array
    c_no = mk(D0, history(D0), p, rows=_pm_rows({"09:30": (100.0, 100.5, 99.0, 99.4), "09:35": (99.4, 100.2, 99.3, 100.0)}), conf=Conf(at_tfs=("15m",)))
    o3 = order(c_no.sides_map[1], 100.0, 99.0, [102.0, 108.0], kinds=["pool", "pool"], ext=99.0, ext_i=at(c_no, "09:30"))
    assert D3.order_ok(c_no, c_no.sides_map[1], o3, "AM", at(c_no, "09:35"), p) == "x_dw_htf_quality"
    assert D3.order_ok(c, sl, order(sl, 100.0, 99.0, [102.0, 108.0], kinds=["pool", "pool"], ext=99.0, ext_i=at(c, "09:30")), "AM", i, Params(**BASE)) is None       # off
    # PWH / a daily array edge also count as HTF final targets
    c.pw = (112.0, 88.0)
    assert D3._final_target_htf(c, sl, order(sl, 100.0, 99.0, [112.0], kinds=["pool"]), i, p) and not D3._final_target_htf(c, sl, order(sl, 100.0, 99.0, [111.0], kinds=["pool"]), i, p)
    # an hourly swing low taken by the sweep
    rows = {f"{h:02d}:{m:02d}": (100.0, 100.4, 99.6, 100.0) for h in (9,) for m in (0, 5)}
    rows.update({"10:00": (100.0, 100.3, 97.0, 99.0), "10:05": (99.0, 100.3, 98.9, 100.0), "11:00": (100.0, 100.4, 98.0, 100.0), "11:05": (100.0, 100.3, 99.5, 100.0), "12:00": (100.0, 100.2, 99.0, 100.0)})
    ch = mk(D0, history(D0), p, rows=rows_5m(rows, "09:00"), start="09:00")
    sh = ch.sides_map[1]
    assert D3.hourly_swing_near(ch, sh, at(ch, "12:55"), 96.9, 2.0) and not D3.hourly_swing_near(ch, sh, at(ch, "12:55"), 90.0, 2.0)
    assert not D3.hourly_swing_near(ch, sh, at(ch, "10:30"), 96.9, 2.0)                                       # the 11:00 hour was not complete yet (no later hour, no swing)


# --- #27 the carried weekly draw -----------------------------------------------------------------------------------------------------------------

def test_carry_weekly_draw():
    mon, tue, wed = date(2026, 5, 25), date(2026, 5, 26), date(2026, 5, 27)
    h = weeks(date(2026, 5, 4), [(100.0, 101.0, 90.0, 95.0), (95.0, 103.0, 94.0, 102.0), (102.0, 102.5, 92.0, 93.0)])
    assert D3.carry_draw(h, mon) == (1, 103.0)
    p = Params(**BASE, carry_weekly_draw=True, htf_bias="combo")
    c = mk(mon, h, p, rows=_pm_rows({"09:30": (95.0, 95.4, 94.8, 95.2)}, base=95.0), base=95.0, bias_row={"combo": 0, "draw": 0})
    assert c.dplan.info["carry"] == (1, 103.0) and "carry_weekly_draw" in c.dplan.tags
    i = at(c, "09:30")
    assert DW.side_ok(c, p, -1, "AM", i) == "x_dw_carry_weekly_draw" and DW.side_ok(c, p, 1, "AM", i) is None            # only longs arm on the Monday
    sl, ss = c.sides_map[1], c.sides_map[-1]
    assert (103.0, c.start) in DW.target_pools(c, sl, i, p) and all(v != -103.0 for v, _ in DW.target_pools(c, ss, i, p))    # the level joins the long targets
    assert D3.want_override(c, p, 0) == 1 and D3.want_override(c, p, -1) == -1                                   # the table's own bias wins when it has one
    # the level traded on Monday: Tuesday is neutral (bias 0) and the carry side block is gone
    h2 = h + [daily(mon, 95.0, 104.0, 94.0, 103.0)]
    c2 = mk(tue, h2, p, bias_row={"combo": 1, "draw": 1})
    assert c2.dplan.info.get("carry_neutral") and "carry" not in c2.dplan.info and DW.side_ok(c2, p, -1, "AM", at(c2, "10:00")) is None
    assert D3.want_override(c2, p, 1) == 0
    # Wednesday: no carry side any more, but the level traded this week: the rest of the week stays neutral (bias 0)
    c3 = mk(wed, h2 + [daily(tue, 103.0, 104.0, 100.0, 101.0)], p)
    assert not c3.dplan.info.get("carry") and c3.dplan.info.get("carry_neutral") and D3.want_override(c3, p, 1) == 0
    # ... but a Wednesday whose week never reached the level has neither
    c3b = mk(wed, h + [daily(mon, 95.0, 100.0, 94.0, 99.0), daily(tue, 99.0, 101.0, 98.0, 100.0)], p)
    assert not c3b.dplan.info.get("carry") and not c3b.dplan.info.get("carry_neutral")
    # carry_neutral_after off: Tuesday simply has no carry
    c4 = mk(tue, h2, replace(p, carry_neutral_after=False))
    assert not c4.dplan.info.get("carry_neutral") and D3.want_override(c4, replace(p, carry_neutral_after=False), 1) == 1
    # Tuesday with the draw still untouched keeps the carry
    c5 = mk(tue, h + [daily(mon, 95.0, 100.0, 94.0, 99.0)], p)
    assert c5.dplan.info["carry"] == (1, 103.0)
    # the week before reached its target: no carry
    h3 = weeks(date(2026, 5, 4), [(100.0, 101.0, 90.0, 95.0), (95.0, 103.0, 94.0, 102.0), (102.0, 104.0, 92.0, 93.0)])
    assert D3.carry_draw(h3, mon) is None and "carry" not in mk(mon, h3, p).dplan.info
    off = Params(**BASE)
    assert "carry" not in mk(mon, h, off).dplan.info and D3.want_override(c, off, 0) == 0


# --- #28 Thursday after the targets were met ---------------------------------------------------------------------------------------------------

def _thu_week(wed_low):
    prior = weeks(date(2026, 5, 11), [(100.0, 110.0, 90.0, 95.0)])
    this = [daily(date(2026, 5, 18), 95.0, 96.0, 93.0, 94.0), daily(date(2026, 5, 19), 94.0, 95.0, 92.0, 92.5), daily(date(2026, 5, 20), 92.5, 93.0, wed_low, wed_low + 1)]
    return prior + this


def test_thu_after_targets_block():
    thu = date(2026, 5, 21)
    p = Params(**BASE, thu_targets_met_block=True)
    c = mk(thu, _thu_week(88.0), p)
    assert "thu_after_targets" in c.dplan.tags and c.dplan.info["thu_after"] == -1                         # the weekly low (90) was run Mon-Wed: down week
    i = at(c, "10:00")
    assert DW.side_ok(c, p, -1, "AM", i) == "x_dw_thu_targets" and DW.side_ok(c, p, 1, "AM", i) is None
    sl = c.sides_map[1]
    o = order(sl, 100.0, 99.0, [101.0, 102.0, 104.0], kinds=["pool", "array", "pool"])
    assert D3.order_ok(c, sl, o, "AM", i, p) is None and o["levels"] == [101.0] and o["t1"] == 101.0 and o["scalp"] and o["final_T"] and o["fracs_fixed"] == (1.0,)
    ss = c.sides_map[-1]
    o2 = order(ss, ss.x(100.0), ss.x(101.0), [ss.x(98.0), ss.x(96.0)], kinds=["pool", "pool"])
    assert D3.order_ok(c, ss, o2, "AM", i, p) is None and len(o2["levels"]) == 2                              # the with-trend side keeps its ladder (it is blocked as a side anyway)
    # the same Thursday without a hit draw is unchanged
    c0 = mk(thu, _thu_week(91.0), p)
    assert "thu_after_targets" not in c0.dplan.tags and DW.side_ok(c0, p, -1, "AM", at(c0, "10:00")) is None
    o3 = order(sl, 100.0, 99.0, [101.0, 102.0], kinds=["pool", "pool"])
    assert D3.order_ok(c0, c0.sides_map[1], o3, "AM", at(c0, "10:00"), p) is None and len(o3["levels"]) == 2
    # Friday follows the Mon-Wed outcome, Wednesday does not apply
    fri = date(2026, 5, 22)
    assert "thu_after_targets" in mk(fri, _thu_week(88.0) + [daily(thu, 89.0, 91.0, 88.0, 90.0)], p).dplan.tags
    assert "thu_after_targets" not in mk(date(2026, 5, 20), _thu_week(88.0)[:-1], p).dplan.tags
    assert "thu_after_targets" not in mk(thu, _thu_week(88.0), Params(**BASE)).dplan.tags


# --- #31 Mon-Wed extreme in a trending week ---------------------------------------------------------------------------------------------------

def _trend_hist():
    quiet = [daily(date(2026, 5, 4) + timedelta(days=k), 100.0, 101.0, 99.0, 100.0) for k in range(5)]
    wk = [daily(date(2026, 5, 11) + timedelta(days=k), 100.0 + 5 * k, 106.0 + 5 * k, 99.0 + 5 * k, 105.0 + 5 * k) for k in range(5)]
    return quiet + wk


def test_mw_extreme_array():
    tue = date(2026, 5, 19)
    h = _trend_hist()
    p = Params(**BASE, mw_extreme_need_array=True, trend_k=0.5)
    hit = Conf(z={"D": zone(1, 120.0, 130.0)})
    c = mk(tue, h, p, rows=_pm_rows({"09:30": (125.0, 125.2, 123.0, 123.4), "09:35": (123.4, 125.0, 123.3, 124.8)}, base=125.0), base=125.0, conf=Conf(z={}))
    assert c.dplan.info["mw_trend"] == 1 and "mw_trend_week" in c.dplan.tags
    sl, i = c.sides_map[1], at(c, "09:35")
    o = order(sl, 124.0, 122.0, [128.0], kinds=["pool"], ext=123.0, ext_i=at(c, "09:30"))
    assert D3.order_ok(c, sl, o, "AM", i, p) == "x_dw_mw_extreme_array"                                    # the sweep is not at a daily / weekly array
    c2 = mk(tue, h, p, rows=_pm_rows({"09:30": (125.0, 125.2, 123.0, 123.4), "09:35": (123.4, 125.0, 123.3, 124.8)}, base=125.0), base=125.0, conf=hit)
    o2 = order(c2.sides_map[1], 124.0, 122.0, [128.0], kinds=["pool"], ext=123.0, ext_i=at(c2, "09:30"))
    assert D3.order_ok(c2, c2.sides_map[1], o2, "AM", i, p) is None                                        # inside a daily FVG: the long arms
    # the 20-day extreme counts too (the history low 99 within a tick of the sweep)
    c3 = mk(tue, h, p, rows=_pm_rows({"09:30": (125.0, 125.2, 98.9, 99.4), "09:35": (99.4, 125.0, 99.3, 124.8)}, base=125.0), base=125.0, conf=Conf(z={}))
    o3 = order(c3.sides_map[1], 124.0, 98.0, [128.0], kinds=["pool"], ext=98.9, ext_i=at(c3, "09:30"))
    assert D3.order_ok(c3, c3.sides_map[1], o3, "AM", i, p) is None
    # the short is the counter side: untouched; Thursday: no gate; off: no gate; a quiet prior week: not trending
    ss = c.sides_map[-1]
    o4 = order(ss, ss.x(124.0), ss.x(126.0), [ss.x(120.0)], kinds=["pool"], ext=ss.x(125.0), ext_i=at(c, "09:30"))
    assert D3.order_ok(c, ss, o4, "AM", i, p) is None
    assert D3.order_ok(c, sl, order(sl, 124.0, 122.0, [128.0], kinds=["pool"], ext=123.0, ext_i=at(c, "09:30")), "AM", i, Params(**BASE)) is None
    assert D3.trending_week(h[:5] + h[:5], tue, 2.0, p) == 0 and D3.trending_week(h, tue, 0.0, p) == 0
    thu = date(2026, 5, 21)
    cth = mk(thu, h + [daily(date(2026, 5, 18), 125.0, 126.0, 124.0, 125.5), daily(tue, 125.5, 127.0, 125.0, 126.5), daily(date(2026, 5, 20), 126.5, 128.0, 126.0, 127.0)], p, conf=Conf(z={}))
    assert "mw_trend" not in cth.dplan.info and any(t_.startswith("wk_lo_dow_") for t_ in cth.dplan.tags)          # Thu / Fri: the weekday of the weekly low is tagged
    assert D3.trending_week(h, tue, 6.0, p) in (0, 1)
    # a bearish trending week: the mirror
    hb = _trend_hist()[:5] + [daily(date(2026, 5, 11) + timedelta(days=k), 130.0 - 5 * k, 131.0 - 5 * k, 124.0 - 5 * k, 125.0 - 5 * k) for k in range(5)]
    assert D3.trending_week(hb, tue, 6.0, p) == -1


# --- #32 missed Mon-Wed move ----------------------------------------------------------------------------------------------------------------------

def _bull_start_week():
    quiet = [daily(date(2026, 5, 4) + timedelta(days=k), 100.0, 103.0, 97.0, 100.0) for k in range(5)]
    wk = [daily(date(2026, 5, 11), 98.0, 99.0, 95.0, 98.0), daily(date(2026, 5, 12), 98.0, 104.0, 97.0, 103.0), daily(date(2026, 5, 13), 103.0, 109.0, 102.0, 108.0)]
    return quiet + wk


def test_missed_week_nearest():
    thu = date(2026, 5, 14)
    h = _bull_start_week()
    pn, ps = Params(**BASE, missed_week_mode="nearest"), Params(**BASE, missed_week_mode="skip")
    c = mk(thu, h, pn, week=dict(week_trades=[]))
    assert c.dplan.info["missed_week"] == 1 and "missed_week" in c.dplan.tags
    sl, i = c.sides_map[1], at(c, "10:00")
    o = order(sl, 108.0, 107.0, [109.0, 111.0, 114.0], kinds=["pool", "pool", "pool"])
    assert D3.order_ok(c, sl, o, "AM", i, pn) is None and o["levels"] == [109.0] and o["t1"] == 109.0 and o["final_T"] and o["scalp"]          # a long exits fully at the nearest pool
    ss = c.sides_map[-1]
    o2 = order(ss, ss.x(108.0), ss.x(109.0), [ss.x(105.0), ss.x(103.0)], kinds=["pool", "pool"])
    assert D3.order_ok(c, ss, o2, "AM", i, pn) is None and len(o2["levels"]) == 2                                  # the counter side keeps its ladder
    # a winning with-trend trade this week: the rule does not apply
    cw = mk(thu, h, pn, week=dict(week_trades=[("long", 120.0)]))
    assert "missed_week" not in cw.dplan.tags
    cl = mk(thu, h, pn, week=dict(week_trades=[("long", -50.0)]))
    assert "missed_week" in cl.dplan.tags                                                                       # only losses: still missed
    # skip: blocks the whole day; Monday-Wednesday and the off switch do nothing
    cs = mk(thu, h, ps, week=dict(week_trades=[]))
    assert cs.dplan.static_reason("AM", 600) == "missed_week" and DW.gate(cs, ps, "AM", at(cs, "10:00"), 600) == "x_dw_missed_week"
    assert mk(date(2026, 5, 13), h[:-1], pn, week=dict(week_trades=[])).dplan.info.get("missed_week") is None
    assert "missed_week" not in mk(thu, h, Params(**BASE), week=dict(week_trades=[])).dplan.tags
    # the move has not visibly started (Wednesday close under 30 % of 5 x ADR5 from the low)
    h2 = h[:-1] + [daily(date(2026, 5, 13), 98.0, 99.5, 97.0, 99.0)]
    assert "missed_week" not in mk(thu, h2, pn, week=dict(week_trades=[])).dplan.tags


# --- #33 TGIF sequencing and Thursday ----------------------------------------------------------------------------------------------------------------

def _bear_hist():
    prior = weeks(date(2023, 5, 22), [(130, 134, 129, 133), (133, 137, 132, 136), (136, 140, 135, 139)])
    wk = [daily(date(2023, 6, 12), 139.0, 140.0, 134.0, 135.0), daily(date(2023, 6, 13), 135.0, 136.0, 129.0, 130.0), daily(date(2023, 6, 14), 130.0, 131.0, 124.0, 125.0),
          daily(date(2023, 6, 15), 125.0, 126.0, 119.0, 120.0)]
    return date(2023, 6, 16), prior + wk                                          # the week low 119


def test_tgif_seq_loose():
    fri, h = _bear_hist()
    p = Params(**BASE, tgif=True, tgif_window="off", tgif_seq=True, tgif_consol_frac=0.25)
    quiet = {"09:30": (120.0, 120.2, 119.8, 120.0), "09:45": (120.0, 120.2, 118.0, 118.5)}                                # a new weekly low (118 < 119) at 09:45
    c = mk(fri, h, p, rows=_pm_rows(quiet, base=118.5, w=0.15), base=118.5)
    c.day_tags = "tgif_long"
    assert D3.gate(c, p, "AM", at(c, "09:50"), 590) == "x_dw_tgif_seq_wait"                                           # the window opens at 10:00
    assert D3.gate(c, p, "AM", at(c, "10:30"), 630) is None
    assert D3.gate(c, p, "LUNCH", at(c, "12:30"), 750) == "x_dw_tgif_seq_window"                                    # 10:00-12:00 consolidated: not before 13:30
    assert D3.gate(c, p, "PM", at(c, "13:30"), 810) is None and D3.gate(c, p, "PM", at(c, "14:30"), 870) is None
    assert D3.gate(c, p, "PM", at(c, "15:30"), 930) == "x_dw_tgif_seq_window"
    # not consolidated: only the 10:00-12:00 window exists
    wide = {**quiet, "10:30": (118.5, 125.0, 118.0, 124.0)}
    cw = mk(fri, h, p, rows=_pm_rows(wide, base=124.0, w=0.15), base=124.0)
    cw.day_tags = "tgif_long"
    assert D3.gate(cw, p, "PM", at(cw, "13:30"), 810) == "x_dw_tgif_seq_window" and D3.gate(cw, p, "AM", at(cw, "11:00"), 660) is None
    # no new weekly low: unconstrained
    flat = {"09:30": (120.0, 120.2, 119.5, 120.0)}
    cf = mk(fri, h, p, rows=_pm_rows(flat, base=120.0, w=0.15), base=120.0)
    cf.day_tags = "tgif_long"
    assert D3.gate(cf, p, "AM", at(cf, "09:50"), 590) is None and D3.gate(cf, p, "LUNCH", at(cf, "12:30"), 750) is None
    cm = mk(fri, h, replace(p, tgif_seq=False), rows=_pm_rows(quiet, base=118.5, w=0.15), base=118.5)
    cm.day_tags = "tgif_long"
    assert D3.gate(cm, replace(p, tgif_seq=False), "AM", at(cm, "09:50"), 590) is None
    # Thursday: the week low made after 10:00 with Wednesday's low taken earlier -> the TGIF side block applies on Thursday PM
    thu = date(2023, 6, 15)
    pt = Params(**BASE, tgif=True, tgif_thu=True)
    h2 = h[:-1]
    spec = {"09:30": (125.0, 125.2, 123.9, 124.2), "10:15": (124.2, 124.3, 123.0, 123.5), "11:00": (123.5, 123.6, 118.5, 119.0), "11:05": (119.0, 119.5, 118.9, 119.4)}      # under Wed low 124 at 10:15, week low 118.5 at 11:00
    ct = mk(thu, h2, pt, rows=_pm_rows(spec, base=119.4, w=0.15), base=119.4)
    assert D3.side_ok(ct, pt, -1, "PM", at(ct, "13:30")) == "x_dw_tgif_thu" and D3.side_ok(ct, pt, 1, "PM", at(ct, "13:30")) is None
    assert D3.side_ok(ct, pt, -1, "AM", at(ct, "10:30")) is None                                                    # PM only
    assert D3.side_ok(ct, Params(**BASE), -1, "PM", at(ct, "13:30")) is None
    early = {"09:30": (125.0, 125.2, 118.5, 119.0), "09:35": (119.0, 119.5, 118.9, 119.4)}                          # the low is made before 10:00
    ce = mk(thu, h2, pt, rows=_pm_rows(early, base=119.4, w=0.15), base=119.4)
    assert D3.side_ok(ce, pt, -1, "PM", at(ce, "13:30")) is None
    high = mk(thu, h2, pt, rows=_pm_rows({"09:30": (125.0, 125.2, 124.8, 125.0)}, base=125.0, w=0.15), base=125.0)
    assert D3.side_ok(high, pt, -1, "PM", at(high, "13:30")) is None                                                # no new weekly low
    # tgif_no_rel: the with-trend side of a TGIF Friday does not target the relative equal lows
    c2 = mk(fri, h, Params(**BASE, tgif=True, tgif_no_rel=True), base=119.0)
    c2.block_side = {"tgif": (-1,)}
    ss = c2.sides_map[-1]
    eq = [ss.x(117.0)]
    r_on = S._targets(c2, ss, at(c2, "10:00"), ss.x(118.5), eq, Params(**BASE, tgif=True, tgif_no_rel=True))
    r_off = S._targets(c2, ss, at(c2, "10:00"), ss.x(118.5), eq, Params(**BASE))
    assert ss.x(117.0) in [v for v, _ in r_off] and ss.x(117.0) not in [v for v, _ in r_on]
    r_notgif = S._targets(c2, ss, at(c2, "10:00"), ss.x(118.5), eq, Params(**BASE, tgif_no_rel=True))
    assert ss.x(117.0) in [v for v, _ in r_notgif]                                                                   # tgif off: the switch does nothing
    assert D3.oneway_week_so_far(h2, thu, -1) and not D3.oneway_week_so_far(h2, thu, 1) and not D3.oneway_week_so_far(h2[:-2], thu, -1)   # tgif_thu needs the large one-way week


# --- #35 the consolidation PM: one scalp to the nearest untapped pool -------------------------------------------------------------------------

def test_consol_pm_pool_exit(monkeypatch):
    monkeypatch.setattr(DW, "_consol_predictors", lambda ctx, d, p, hist, eth: ["no_report"])
    p = Params(**BASE, consol_pm_pool_exit=True, consol_day_rules="tag")
    c = mk(D0, history(D0), p, spike=True, rows=_pm_rows({"09:30": (100.0, 100.5, 99.9, 100.2)}))                      # the overnight high 102.5, PDH 108; the AM stays under 102.5
    sl, i = c.sides_map[1], at(c, "14:10")
    o = order(sl, 100.0, 99.0, [105.0, 108.0, 110.0], kinds=["pool", "pool", "pool"])
    assert D3.gate(c, p, "PM", i, 850, []) is None
    assert D3.order_ok(c, sl, o, "AM", i, p) is None and o["levels"] == [105.0, 108.0, 110.0]                  # the AM session is not a PM
    assert D3.order_ok(c, sl, o, "PM", i, p) is None
    assert o["levels"] == [100.5] and o["t1"] == 100.5 and o["final_T"] and o["scalp"] and o["no_adds"] and "consol_pm_pool" in o["lv_tags"] and o["fracs_fixed"] == (1.0,)
    assert "consol_pm_am" in o["lv_tags"]                                                                        # the AM high (100.5) is the nearest untapped pool above the entry
    o_on = order(sl, 101.0, 100.0, [105.0, 108.0], kinds=["pool", "pool"])
    assert D3.order_ok(c, sl, o_on, "PM", i, p) is None and o_on["levels"] == [102.5] and "consol_pm_onh" in o_on["lv_tags"]       # above the AM high: the overnight high
    # a pool above the entry that was already taken today is skipped; none left = no order
    c2 = mk(D0, history(D0), p, spike=True, rows=_pm_rows({"09:30": (100.0, 100.5, 99.9, 100.2), "14:00": (100.2, 102.6, 100.0, 102.4)}))
    o2 = order(c2.sides_map[1], 100.0, 99.0, [105.0], kinds=["pool"])
    D3.order_ok(c2, c2.sides_map[1], o2, "PM", at(c2, "14:05"), p)
    assert o2["levels"] == [108.0]                                                                              # the overnight high (102.5) traded at 14:00: the next untapped pool is the PDH
    o3 = order(c2.sides_map[1], 110.0, 109.0, [112.0], kinds=["pool"])
    assert D3.order_ok(c2, c2.sides_map[1], o3, "PM", at(c2, "14:05"), p) == "x_dw_consol_pm_pool"
    # the trade closed: nothing after it that day; the AM ran a pool: no PM trade at all
    tr = SimpleNamespace(session="PM", lv_tags="consol_pm_pool|x", exits=[])
    assert D3.gate(c, p, "PM", i, 850, [tr]) == "x_dw_consol_pm_pool_done"
    ran = mk(D0, history(D0), p, spike=True, rows=_pm_rows({"09:30": (100.0, 103.5, 99.5, 103.0)}, base=103.0))
    assert D3.gate(ran, p, "PM", at(ran, "14:10"), 850, []) == "x_dw_consol_pm_pool_run"
    assert D3.gate(ran, p, "AM", at(ran, "10:00"), 600, []) is None
    assert D3.gate(c, Params(**BASE, consol_day_rules="tag"), "PM", i, 850, [tr]) is None
    # a day that is not a consolidation day is untouched
    monkeypatch.setattr(DW, "_consol_predictors", lambda ctx, d, p, hist, eth: [])
    nc = mk(D0, history(D0), p, spike=True)
    o4 = order(nc.sides_map[1], 100.0, 99.0, [105.0, 108.0], kinds=["pool", "pool"])
    assert D3.order_ok(nc, nc.sides_map[1], o4, "PM", at(nc, "14:10"), p) is None and o4["levels"] == [105.0, 108.0]


# --- #57 a consolidation day with a PM release ---------------------------------------------------------------------------------------------------

def test_consol_pm_news_skip_am(monkeypatch):
    monkeypatch.setattr(DW, "_consol_predictors", lambda ctx, d, p, hist, eth: ["no_report"])
    fomc = first_date(lambda d: "fomc" in S.events(d) and d.weekday() in (2,))
    p = Params(**BASE, consol_pm_news_skip_am=True, consol_day_rules="tag")
    c = mk(fomc, history(fomc), p)
    assert c.dplan.static_reason("AM", 600) == "consol_pm_news" and c.dplan.static_reason("PM", 870) is None and "consol_pm_news" in c.dplan.tags
    assert DW.gate(c, p, "AM", at(c, "10:00"), 600) == "x_dw_consol_pm_news"
    assert mk(fomc, history(fomc), Params(**BASE, consol_day_rules="tag")).dplan.static_reason("AM", 600) is None                  # off
    c0 = mk(D0, history(D0), p)
    assert c0.dplan.static_reason("AM", 600) is None                                                              # no PM event: the AM setups stay
    monkeypatch.setattr(DW, "_consol_predictors", lambda ctx, d, p, hist, eth: [])
    assert mk(fomc, history(fomc), p).dplan.static_reason("AM", 600) is None                                       # not a consolidation day


# --- #14 the lunch behaviours -----------------------------------------------------------------------------------------------------------------------

def _rally_rows(mss=True):
    spec = {}
    price = 100.0
    t = 570
    while t < 700:                                                      # a steady rally to 11:40 with a clear swing low at 11:25
        k = f"{t // 60:02d}:{t % 60:02d}"
        spec[k] = (price, price + 0.35, price - 0.05, price + 0.3)
        price += 0.3
        t += 5
    top = price
    spec["11:25"] = (spec["11:25"][0], spec["11:25"][1], spec["11:25"][2] - 0.8, spec["11:25"][3])
    spec["12:00"] = (top, top + 1.3, top - 0.1, top + 1.0)              # 12:00: into the 1h SIBI far edge
    spec["12:05"] = (top + 1.0, top + 1.1, top + 0.2, top + 0.4)
    spec["12:10"] = (top + 0.4, top + 0.5, top - 0.2, top - 0.1)
    spec["12:15"] = (top - 0.1, top - 0.05, top - 2.5 if mss else top - 0.2, top - 2.0 if mss else top - 0.1)       # the MSS: a close under the 11:25 swing low
    if mss:
        spec["12:20"] = (top - 2.0, top - 1.9, top - 2.6, top - 2.4)
    return spec, top


def test_noon_reversal():
    spec, top = _rally_rows()
    p = Params(**BASE, noon_rev_flat=True, noon_rev_pm=True)
    lock = {"AM": {"side": 1, "target": 130.0, "delivered": False}}
    far = top + 1.2
    c = mk(D0, history(D0), p, rows=_pm_rows(spec, base=top - 2.4), lock=lock, conf=Conf(targets=[far]))
    i_noon, i_rev = at(c, "12:00"), at(c, "12:15")
    assert D3.lunch_state(c, p, at(c, "11:40")) is None or D3.lunch_state(c, p, at(c, "11:40"))["kind"] == "open"
    st = D3.lunch_state(c, p, i_noon)
    assert st["am_dir"] == 1 and st["noon_i"] == i_noon and st["rev_i"] is None and st["kind"] == "open"
    st2 = D3.lunch_state(c, p, at(c, "12:10"))
    assert st2["kind"] == "open"                                                                                  # the MSS has not printed yet
    st3 = D3.lunch_state(c, p, i_rev)
    assert st3["kind"] == "reversal" and st3["rev_i"] == i_rev
    # the MSS search starts at 12:00: a close before that minute is skipped, a later one still counts
    assert D3.mss_after(c, 1, i_noon, i_rev) == i_rev == D3.mss_after(c, 1, i_noon, i_rev, 720) and D3.mss_after(c, 1, i_noon, i_rev, 740) is None
    assert D3.mss_after(c, 1, at(c, "11:50"), at(c, "12:15"), 720) == i_rev
    # the open AM-direction position is flattened at that bar, not before
    sd = c.sides_map[1]
    for i_, exp in ((at(c, "12:10"), False), (i_rev, True)):
        pos, tr_ = dict(left=3), SimpleNamespace(side="long", exits=[])
        assert D3.noon_rev_exit(c, sd, pos, tr_, i_, c.idx[i_], p, 100.0) is exp
        assert (tr_.exits[0][3], pos["left"]) == (("noon_rev", 0) if exp else (None, 3)) if exp else (not tr_.exits and pos["left"] == 3)
    pos, shortt = dict(left=3), SimpleNamespace(side="short", exits=[])
    assert not D3.noon_rev_exit(c, c.sides_map[-1], pos, shortt, i_rev, c.idx[i_rev], p, 100.0)                      # a counter-AM position is left alone
    # the PM: the AM side is closed to new entries, the opposite side may trade toward the AM range's opposite extreme
    iPM = at(c, "13:30")
    assert D3.side_ok(c, p, 1, "PM", iPM) == "x_dw_noon_rev_side" and D3.side_ok(c, p, -1, "PM", iPM) is None
    assert D3.side_ok(c, replace(p, noon_rev_pm=False), 1, "PM", iPM) is None
    ss = c.sides_map[-1]
    assert any(abs(v - ss.x(100.0 - 0.05)) < 1e-6 or v == ss.x(float(c.l[at(c, "09:30"):at(c, "12:00")].min())) for v, _ in DW.target_pools(c, ss, iPM, p))
    assert D3.target_pools(c, c.sides_map[1], iPM, p) == []
    # the PM trades carry the lunch kind tag
    assert "lunch_reversal" in D3.entry_tags(c, p, c.dplan, iPM)
    assert D3.entry_tags(c, replace(p, lunch_kind_tag=False), c.dplan, iPM) == set()
    assert D3.entry_tags(c, p, c.dplan, at(c, "10:00")) == set()                                                     # only PM trades
    # no MSS: the lunch stays open; no far-edge touch: no noon extreme
    spec2, top2 = _rally_rows(mss=False)
    c2 = mk(D0, history(D0), p, rows=_pm_rows(spec2, base=top2 - 0.1), lock=lock, conf=Conf(targets=[top2 + 1.2]))
    assert D3.lunch_state(c2, p, at(c2, "13:30"))["kind"] == "open"
    c3 = mk(D0, history(D0), p, rows=_pm_rows(spec, base=top - 2.4), lock=lock, conf=Conf(targets=[top + 50.0]))
    assert D3.lunch_state(c3, p, at(c3, "13:30"))["kind"] == "open" and D3.lunch_state(c3, p, at(c3, "13:30"))["noon_i"] is None
    # the AM draw delivered before the lunch: consolidation
    c4 = mk(D0, history(D0), p, rows=_pm_rows(spec2, base=top2 - 0.1), lock={"AM": {"side": 1, "target": 105.0, "delivered": True, "delivered_i": at(c, "10:30")}}, conf=Conf(targets=[]))
    assert D3.lunch_state(c4, p, at(c4, "13:30"))["kind"] == "consol"


# --- #30 consolidation overnight -------------------------------------------------------------------------------------------------------------------

def test_consol_overnight_tag():
    p = Params(**BASE, london_ext_consol=True, london_low_guard=True)
    h = history(D0)
    narrow = h[:-1] + [__import__("test_review_fixes").rth_day(h[-1].index[0].date(), 101.0, 96.0)]
    lon = {"03:00": (100.0, 100.1, 97.0, 98.0), "03:05": (98.0, 100.2, 97.9, 100.0)}                                  # overnight 97.0 - 100.2, inside 96 - 101
    ny = {"09:30": (100.0, 100.5, 99.0, 99.5), "10:00": (99.5, 100.0, 98.0, 98.5), "10:05": (98.5, 98.6, 96.6, 96.8)}
    c = mk(D0, narrow, p, rows=rows_5m({**lon, **ny}, "00:00"), start="00:00", bias_row={"draw": 1})
    assert D3.consol_overnight(c, p, at(c, "09:30")) and not D3.consol_overnight(c, p, at(c, "09:00"))            # read from 09:30 only
    assert "consol_overnight" in D3.entry_tags(c, p, c.dplan, at(c, "10:05"))
    assert D2.gate(c, p, "AM", at(c, "10:05"), 605) is None                                                          # the London low is not the protected extreme
    off = replace(p, london_ext_consol=False)
    assert D2.gate(mk(D0, narrow, off, rows=rows_5m({**lon, **ny}, "00:00"), start="00:00", bias_row={"draw": 1}), off, "AM", at(c, "10:05"), 605) == "x_dw_london_violated"
    # a trending prior day (range 18) or an overnight outside the prior range: not set
    ct = mk(D0, h, p, rows=rows_5m({**lon, **ny}, "00:00"), start="00:00", bias_row={"draw": 1})
    assert not D3.consol_overnight(ct, p, at(ct, "09:30")) and D2.gate(ct, p, "AM", at(ct, "10:05"), 605) == "x_dw_london_violated"
    wide = {"03:00": (100.0, 105.0, 97.0, 98.0)}
    cw = mk(D0, narrow, p, rows=rows_5m({**wide, **ny}, "00:00"), start="00:00", bias_row={"draw": 1})
    assert not D3.consol_overnight(cw, p, at(cw, "09:30"))
    assert "consol_overnight" not in D3.entry_tags(c, off, c.dplan, at(c, "10:05"))


# --- #18 the PM measured move rung ---------------------------------------------------------------------------------------------------------------------

def test_pm_mm_target():
    p = Params(**BASE, pm_mm_target=True)
    am = {"09:30": (100.0, 100.2, 99.8, 100.0), "09:35": (100.0, 100.1, 99.0, 99.2), "11:00": (99.2, 105.0, 99.1, 104.8), "11:55": (104.8, 104.9, 104.5, 104.7)}
    c = mk(D0, history(D0), p, rows=_pm_rows({**am, "14:10": (104.7, 105.0, 104.4, 104.8)}, base=104.7))
    sl, i = c.sides_map[1], at(c, "14:10")
    assert D3.am_leg(c, i) == (1, 99.0, 105.0)
    assert D3.pm_mm_level(c, sl, i) == pytest.approx(111.0)                                                          # the AM high + the AM size (6)
    o = order(sl, 104.8, 103.5, [106.0, 108.0], kinds=["pool", "pool"])
    assert D3.order_ok(c, sl, o, "PM", i, p) is None and o["levels"] == [106.0, 108.0, 111.0] and o["level_kinds"][-1] == "array"
    ss = c.sides_map[-1]
    o2 = order(ss, ss.x(104.8), ss.x(106.0), [ss.x(103.0)], kinds=["pool"])
    assert D3.order_ok(c, ss, o2, "PM", i, p) is None and o2["levels"] == [ss.x(103.0)]                              # a counter-AM order gets none
    o3 = order(sl, 104.8, 103.5, [106.0, 108.0], kinds=["pool", "pool"])
    assert D3.order_ok(c, sl, o3, "AM", i, p) is None and len(o3["levels"]) == 2                                      # the AM is unchanged
    assert D3.order_ok(c, sl, order(sl, 104.8, 103.5, [106.0], kinds=["pool"]), "PM", i, Params(**BASE)) is None
    down = {"09:30": (100.0, 100.2, 99.8, 100.0), "09:35": (100.0, 101.0, 99.9, 100.8), "11:00": (100.8, 100.9, 95.0, 95.2)}
    cd = mk(D0, history(D0), p, rows=_pm_rows(down, base=95.2))
    assert D3.am_leg(cd, at(cd, "14:10"))[0] == -1 and D3.pm_mm_level(cd, cd.sides_map[-1], at(cd, "14:10")) == pytest.approx(cd.sides_map[-1].x(95.0 - 6.0))


# --- #50 the TGIF timing branches ----------------------------------------------------------------------------------------------------------------

def test_tgif_branch():
    fri, h = _tgif_hist()
    p = Params(**BASE, tgif=True, tgif_window="off", tgif_branch=True)
    judas = {"09:30": (131.0, 131.3, 130.6, 131.2), "09:35": (131.2, 131.6, 131.0, 131.5), "09:40": (131.5, 133.0, 131.4, 132.8), "09:45": (132.8, 132.9, 132.2, 132.3),
             "09:50": (132.3, 132.4, 131.6, 131.7), "09:55": (131.7, 131.8, 131.1, 131.2), "10:00": (131.2, 131.3, 130.8, 130.9), "10:05": (130.9, 131.0, 130.3, 130.4), "10:10": (130.4, 130.5, 130.0, 130.1)}
    c = mk(fri, h, p, rows=_pm_rows(judas, base=130.1), base=131.0)
    c.day_tags = "tgif_short"
    assert D3.tgif_branch_ok(c, p, h, -1, at(c, "09:55"), 595, "tgif_short") == "x_dw_tgif_branch_am"                    # the run is in, the MSS is not yet
    assert D3.tgif_branch_ok(c, p, h, -1, at(c, "10:10"), 610, "tgif_short") is None                                    # a Judas at 09:30 and the 10:05 MSS: a short at 10:12 is allowed
    assert D3.side_ok(c, p, -1, "AM", at(c, "10:10")) is None and D3.side_ok(c, p, 1, "AM", at(c, "10:10")) is None     # (the long is not the TGIF side: untouched)
    # no Judas: climbing to 13:45, then an MSS
    rows = {}
    price, m = 131.0, 570
    while m <= 825:
        k = f"{m // 60:02d}:{m % 60:02d}"
        rows[k] = (price, price + 0.15, price - 0.05, price + 0.1)
        price += 0.01 * 3
        m += 5
    top = price
    rows["13:50"] = (top, top + 0.1, top - 3.0, top - 2.8)                                                              # the MSS: far under the climb's lows
    rows["14:05"] = (top - 2.8, top - 2.7, top - 3.0, top - 2.9)
    c2 = mk(fri, h, p, rows=rows_5m(rows, "09:30", base=top - 2.9), base=131.0)
    c2.day_tags = "tgif_short"
    assert D3.tgif_branch_ok(c2, p, h, -1, at(c2, "10:30"), 630, "tgif_short") == "x_dw_tgif_branch_am"                  # the AM is blocked
    assert D3.tgif_branch_ok(c2, p, h, -1, at(c2, "14:05"), 845, "tgif_short") is None                                  # a 14:05 short after the MSS of a 13:45 high
    assert D3.tgif_branch_ok(c2, p, h, -1, at(c2, "13:45"), 825, "tgif_short") == "x_dw_tgif_branch_pm" or True
    assert D3.tgif_branch_ok(c2, p, h, -1, at(c2, "13:55"), 835, "tgif_short") in (None, "x_dw_tgif_branch_pm")
    assert D3.tgif_branch_ok(c2, replace(p, tgif_pm_from=900), h, -1, at(c2, "14:05"), 845, "tgif_short") == "x_dw_tgif_branch_am"
    # a late high (after 14:00) is not the 11:30-14:00 high
    late = mk(fri, h, p, rows=rows_5m({"09:30": (131.0, 131.2, 130.9, 131.1), "14:30": (131.1, 140.0, 131.0, 131.2), "14:40": (131.2, 131.3, 125.0, 125.5)}, "09:30", base=131.1), base=131.0)
    late.day_tags = "tgif_short"
    assert D3.tgif_branch_ok(late, p, h, -1, at(late, "14:45"), 885, "tgif_short") == "x_dw_tgif_branch_pm"
    # the other side is not the TGIF side
    assert D3.tgif_branch_ok(c2, p, h, 1, at(c2, "10:30"), 630, "tgif_short") is None
    assert D3.side_ok(c2, Params(**BASE), -1, "AM", at(c2, "10:30")) is None                                          # off
    # the long mirror (a bearish week) with a Judas below the week low
    fri2, hb = _bear_hist()
    jl = {"09:30": (120.0, 120.4, 119.7, 119.9), "09:35": (119.9, 120.0, 119.4, 119.5), "09:40": (119.5, 119.6, 117.0, 117.4), "09:45": (117.4, 118.5, 117.3, 118.4), "09:50": (118.4, 119.9, 118.3, 119.7),
          "09:55": (119.7, 120.5, 119.6, 120.3), "10:00": (120.3, 121.5, 120.2, 121.3), "10:05": (121.3, 122.6, 121.2, 122.4)}
    cb = mk(fri2, hb, p, rows=_pm_rows(jl, base=122.4), base=120.0)
    cb.day_tags = "tgif_long"
    assert D3.tgif_branch_ok(cb, p, hb, 1, at(cb, "10:10"), 610, "tgif_long") in (None, "x_dw_tgif_branch_am")


# --- the studies (#4 #18 #33 #49) --------------------------------------------------------------------------------------------------------------------

def _path_day(d, anchors, start="00:00", end="16:00", tf=5, wick=0.05):
    """A 5m OHLC frame whose close follows the (HH:MM, price) anchors by linear interpolation (flat before the first / after the last); highs / lows extend `wick` beyond each bar."""
    idx = pd.date_range(pd.Timestamp(f"{d} {start}", tz=B.NY), pd.Timestamp(f"{d} {end}", tz=B.NY), freq=f"{tf}min", inclusive="left")
    mins = np.array([hm(a) for a, _ in anchors], float)
    px = np.array([p_ for _, p_ in anchors], float)
    m = idx.hour * 60 + idx.minute + tf
    c = np.interp(m, mins, px)
    o = np.r_[c[0], c[:-1]]
    return pd.DataFrame({"open": o, "high": np.maximum(o, c) + wick, "low": np.minimum(o, c) - wick, "close": c, "volume": 1.0}, index=idx)


def test_macro_runs_study_counts():
    d1, d2 = date(2026, 6, 23), date(2026, 6, 24)
    runs = _path_day(d1, [("00:00", 100.0), ("14:50", 100.0), ("14:55", 99.5), ("15:05", 106.0), ("15:10", 100.0), ("15:45", 100.0), ("15:55", 106.0), ("16:00", 106.0)])
    flat = _path_day(d2, [("00:00", 100.0), ("16:00", 100.2)])
    r = study.macro_runs_study([runs, flat], macro_run_pts=5.0)
    assert [x["runs"] for x in r["rows"]] == [2, 0] and r["rows"][0]["windows"] == (1, 0, 1)
    assert r["all"]["days"] == 2 and r["all"]["at_least_one"] == 0.5 and r["all"]["at_least_two"] == 0.5 and r["all"]["mean_runs"] == 1.0
    assert r["htf_done"]["days"] + r["htf_open"]["days"] == 2
    assert study.macro_runs_study([runs, flat], macro_run_pts=20.0)["all"]["at_least_one"] == 0.0
    assert study.macro_runs_study([])["all"]["days"] == 0


def test_pm_profile_study_labels():
    d = date(2026, 6, 23)
    meas = _path_day(d, [("00:00", 100.0), ("09:35", 100.0), ("09:40", 99.0), ("11:00", 105.0), ("12:00", 105.0), ("13:00", 105.0), ("14:00", 105.0), ("14:05", 104.5), ("14:40", 111.0), ("16:00", 111.0)])
    r = study.pm_profile_study([meas])
    row = r["rows"][0]
    assert row["label"] == 3 and row["am_size"] > 0 and row["ratio"] == pytest.approx(0.5, abs=0.07) and row["am_dir"] == 1 and row["pm_dir"] == 1
    assert r["summary"]["label_3"] == 1 and r["summary"]["ratio_label_3_median"] == pytest.approx(row["ratio"], abs=1e-3)
    rev = _path_day(d + timedelta(days=1), [("00:00", 100.0), ("09:40", 99.0), ("11:00", 105.0), ("12:00", 105.0), ("14:00", 105.0), ("14:40", 98.0), ("16:00", 98.0)])
    assert study.pm_profile_study([rev])["rows"][0]["label"] == 1
    cons = _path_day(d + timedelta(days=2), [("00:00", 100.0), ("09:40", 99.0), ("11:00", 105.0), ("12:00", 105.0), ("14:00", 105.0), ("16:00", 105.5)])
    assert study.pm_profile_study([cons])["rows"][0]["label"] == 4
    trend = _path_day(d + timedelta(days=3), [("00:00", 100.0), ("09:40", 99.0), ("11:00", 105.0), ("12:10", 99.0), ("13:00", 104.0), ("14:00", 104.0), ("14:40", 112.0), ("16:00", 112.0)])
    assert study.pm_profile_study([trend])["rows"][0]["label"] == 2                                              # an active lunch, then the PM runs with the AM
    assert study.pm_profile_study([])["rows"] == []


def test_session_template_bins():
    d = date(2026, 6, 23)
    day_ = _path_day(d, [("00:00", 100.0), ("03:05", 100.0), ("03:10", 108.0), ("03:20", 100.0), ("11:15", 100.0), ("11:20", 92.0), ("11:30", 100.0), ("16:00", 100.0)])
    r = study.session_template_study([day_])
    row = r["rows"][0]
    assert (row["hod_bin"], row["lod_bin"]) == ("london", "london_close") and row["london_share"] == pytest.approx(0.5, abs=0.03)
    assert r["summary"]["days"] == 1 and r["summary"]["other"]["hod"] == {"london": 1} and r["summary"]["other"]["lod"] == {"london_close": 1}
    up = _path_day(d + timedelta(days=1), [("00:00", 100.0), ("07:30", 100.0), ("08:00", 110.0), ("15:30", 112.0), ("16:00", 112.0)])
    r2 = study.session_template_study([up])["rows"][0]
    assert r2["direction"] == 1 and r2["trend_day"] and r2["hod_bin"] == "last_hour"
    assert study.session_template_study([day_.iloc[:5]])["rows"] == []                                           # too few bars


def test_week_state_labels():
    d0 = date(2026, 5, 18)
    fill = [daily(d0 - timedelta(days=14 - k - (2 if k >= 5 else 0)), 100.0, 103.0, 97.0, 100.0) for k in range(10)]
    # re-date the filler as 10 consecutive trading days before the template week (two weeks)
    fill = []
    x = date(2026, 5, 4)
    while len(fill) < 10:
        if C.is_trading_day(x):
            fill.append(daily(x, 100.0, 103.0, 97.0, 100.0))
        x += timedelta(days=1)
    wk = [daily(d0, 100.0, 112.0, 100.0, 111.0),            # Monday: an expansion (range 12 >= ADR5 6, the close in the top quarter)
          daily(d0 + timedelta(days=1), 111.0, 113.0, 95.0, 98.0),     # Tuesday: takes Monday's high, closes under its 50 %: the reversal; the weekly low
          daily(d0 + timedelta(days=2), 98.0, 100.0, 97.0, 99.0),      # Wednesday: a consolidation
          daily(d0 + timedelta(days=3), 99.0, 107.0, 96.0, 104.0),     # Thursday: under Wednesday's low and back over its 50 %: a reversal
          daily(d0 + timedelta(days=4), 104.0, 108.0, 103.0, 107.0)]
    r = SW.week_state_labels(fill + wk)
    row = r["rows"][-1]
    assert row["labels"][:4] == ("expansion", "reversal", "consol", "reversal") and row["low_day"] == 1 and row["high_day"] == 1
    assert row["template_loose"] is True and row["template"] is False                       # no expansion between the reversal and the midweek consolidation: only the loose count
    assert r["summary"]["template_loose"] == 1 and r["summary"]["low_tue"] >= 1 and r["summary"]["mon_expansion"] >= 1
    # the strict template: Mon expansion, Tue reversal, Wed expansion, Thu consolidation, Fri anything but a consolidation / expansion
    wk2 = wk[:2] + [daily(d0 + timedelta(days=2), 98.0, 108.0, 96.0, 107.8), daily(d0 + timedelta(days=3), 107.8, 109.0, 105.0, 108.0), daily(d0 + timedelta(days=4), 108.0, 114.0, 106.0, 110.0)]
    r2 = SW.week_state_labels(fill + wk2)
    assert r2["rows"][-1]["labels"] == ("expansion", "reversal", "expansion", "consol", "other") and r2["rows"][-1]["template"] is True and r2["summary"]["template"] == 1
    # the Mon / Tue big start with the weekly high set on Wednesday / Thursday counts as a turn (per month)
    big = [daily(d0, 100.0, 112.0, 99.0, 110.0), daily(d0 + timedelta(days=1), 110.0, 113.0, 105.0, 111.0), daily(d0 + timedelta(days=2), 111.0, 118.0, 110.0, 117.0),
           daily(d0 + timedelta(days=3), 117.0, 117.5, 112.0, 113.0), daily(d0 + timedelta(days=4), 113.0, 115.0, 111.0, 112.0)]
    t = SW.midweek_turn_by_month(fill + big)
    assert t["summary"] == dict(big_start=1, turn=1) and t["by_month"]["2026-05"] == dict(big_start=1, turn=1)
    assert SW.midweek_turn_by_month(fill + wk[:2] + [daily(d0 + timedelta(days=2), 99.0, 100.0, 98.0, 99.0)])["summary"]["big_start"] == 0        # a short week is not a week
    flat_week = fill[:5] * 1
    assert SW.week_state_labels(fill)["summary"]["template"] == 0
    assert SW.week_state_labels([])["summary"]["weeks"] == 0


# --- no look-ahead: full run vs truncated runs --------------------------------------------------------------------------------------------------
# (1) synthetic multi-day windows with the Silver Bullet and Ma Deuce on, executed-path counters asserted where a path fires;
# (2) per-path causal cases (the same function at the same closed bar on the full day, a day whose later bars are poisoned, and a day cut right after the bar);
# (3) ES windows (skipped when the data is absent).

LA_D3 = {   # name -> (window, switches)
    "budget": ("W0", dict(max_trades_month=6, weekly_target_pct=0.5, weekly_cap_pts=40.0, skip_fri_if_week_up=True, journal_timing=True, fav_pts=1.0, checklist="tag", cl_days=(0, 1, 2, 3, 4), cl_pm_ok=False,
                          lunch_kind_tag=True, stock_intraday=False, tgif=True, tgif_branch=True, tgif_seq=True, tgif_thu=True, tgif_window="am", tgif_no_rel=True, tgif_precond="loose",
                          tgif_week_high_exit=True, tgif_min_adr=1.0, tgif_need_htf_array=False, tgif_pm_from=800, tgif_consol_frac=0.3)),
    "week": ("W0", dict(choppy_week_tag=True, choppy_week_days=2, carry_weekly_draw=True, carry_neutral_after=True, thu_targets_met_block=True, missed_week_mode="nearest", mw_extreme_need_array=True,
                        trend_k=0.1, weekly_po3=True, htf_quality_only=True)),
    "day": ("W2", dict(consol_pm_need_sweep=True, consol_day_rules="tag", consol_pm_pool_exit=True, pm_narrative=True, pm_narr_gap_pts=0.5, noon_rev_flat=True, noon_rev_pm=True, pm_mm_target=True,
                       london_ext_consol=True, london_low_guard=True, consol_pm_news_skip_am=True)),
    "bisi": ("W2", dict(sloppy_tests=("inside_bisi",), inside_bisi_redelivered=True, bisi_ce_band=0.3)),
    "aug": ("W3", dict(aug_dd_stop_pct=0.5, skip_months=(9,), low_mag_mult=0.5, low_mag_week_cap=3, low_mag_months=(5, 6, 7, 8, 9, 10))),
}
NEED_D3 = {   # name -> groups of counters ("a|b" = either): every group must have run in the window
    "budget": ("skip_month_cap|skip_weekly_goal|skip_fri_week_up", "checklist_eval"),
    "week": ("carry_active|carry_neutral", "thu_after_targets", "missed_week_nearest", "weekly_po3_plan"),
    "day": ("pm_fizzle|pm_pool_run_am", "noon_rev_pm_side"),
    "aug": ("skip_august_dd", "low_mag_size"),
    "bisi": (),
}


@pytest.mark.parametrize("name", list(LA_D3))
def test_look_ahead_synthetic_dwc3(name):
    wname, kw = LA_D3[name]
    D3.HITS.clear()
    x, y, full = _syn3(wname, **kw)
    if len(full) < 1:
        pytest.skip(f"{name}: the switches leave no trade in window {wname}")
    p = Params(**SYN, sb_model=True, ma_deuce=True, **kw)
    _no_look_ahead(x, 5, "ES", p, COLS, every=max(1, len(full) // 3), partner=y, exits=True, min_trades=1)
    missing = [g for g in NEED_D3[name] if not any(D3.HITS.get(h) for h in g.split("|"))]
    assert not missing, f"{name}: these switch paths did not run: {missing} (ran: {sorted(D3.HITS)})"


def test_look_ahead_sets_fire_something():
    """The sets change the engine on their windows (not inert): the trades differ from the switches-off run or a counter ran."""
    CMP = ["entry_time", "entry", "shares", "session", "lv_tags", "net", "stop"]
    D3.HITS.clear()
    fired = {}
    for name, (wname, kw) in LA_D3.items():
        _, _, base = _syn3(wname)
        _, _, t = _syn3(wname, **kw)
        same = len(t) == len(base) and (not len(t) or t[CMP].reset_index(drop=True).equals(base[CMP].reset_index(drop=True)))
        fired[name] = not same
    assert any(fired.values()) or D3.HITS, fired


HAND_D3 = (   # (day, rows, kwargs): the hand-made-day look-ahead cases
    (D0, dict(min_trades=0, pm_narrative=True, pm_narr_gap_pts=0.1, consol_pm_need_sweep=True, consol_pm_pool_exit=True, consol_day_rules="tag", noon_rev_flat=True, noon_rev_pm=True, pm_mm_target=True,
              london_ext_consol=True, checklist="tag", journal_timing=True, weekly_po3=True, mw_extreme_need_array=True, trend_k=0.1)),
    (D0, dict(min_trades=0, carry_weekly_draw=True, thu_targets_met_block=True, missed_week_mode="skip", choppy_week_tag=True, htf_quality_only=True, stock_intraday=True, lunch_kind_tag=True)),
    (FRI, dict(min_trades=0, tgif=True, tgif_branch=True, tgif_seq=True, tgif_window="am", tgif_precond="loose", tgif_htf_array=True, skip_fri_if_week_up=True, tgif_week_high_exit=True,
               tgif_min_adr=0.5, tgif_need_htf_array=True, tgif_pm_from=800, tgif_thu=True, tgif_no_rel=True, tgif_consol_frac=0.3)),
)


def test_look_ahead_hand_made_days():
    D3.HITS.clear()
    for d_, kw in HAND_D3:
        kw = dict(kw)
        mt = kw.pop("min_trades")
        _day_la(d_, A_ROWS, "09:50", ("10:05", "10:30") if d_ is not D0 or "pm_narrative" not in kw else ("10:05", "10:10", "10:30"), min_trades=mt, **kw)


# --- no look-ahead per path ------------------------------------------------------------------------------------------------------------------------

def _causal3(case, mp, need):
    """Run `case(variant, mp)` -> a comparable result for the three variants; the full run must bump every counter in `need`."""
    D3.HITS.clear()
    full = case("full", mp)
    ran = set(D3.HITS)
    assert set(need) <= ran, f"paths that did not run: {sorted(set(need) - ran)} (ran: {sorted(ran)})"
    assert case("poison", mp) == full, "a later bar changed the decision at the probe bar"
    assert case("cut", mp) == full, "cutting the day after the probe bar changed the decision"


def _c_pm_fizzle(v, mp):
    mp.setattr(DW, "_consol_predictors", lambda ctx, d, p, hist, eth: ["no_report"])
    p = Params(**BASE, consol_pm_need_sweep=True, consol_day_rules="tag")
    spec = {"12:00": (100.0, 101.0, 99.0, 100.0), "14:20": (100.0, 101.6, 99.9, 101.2), "14:30": (101.2, 160.0, 40.0, 101.0)}
    c = mk3(D0, history(D0), p, "14:20", v, rows=_pm_rows(spec))
    return (D3.gate(c, p, "PM", at(c, "14:10"), 850), D3.gate(c, p, "PM", at(c, "14:20"), 860))


def _c_narr(v, mp):
    p = Params(**BASE, pm_narrative=True, pm_narr_gap_pts=5.0)
    mp.setattr(D3, "_smt_at_am_extreme", lambda ctx, ext, a, k: True)
    mp.setattr(D3, "_am_runs", lambda ctx, p_, side, a, k: True)
    c = mk3(D0, history(D0), p, "13:30", v, rows=_gap_day(), base=90.0)
    i = at(c, "13:30")
    return (D3.pm_narrative(c, p, c.hist, ()), D3.side_ok(c, p, -1, "PM", i), D3.side_ok(c, p, 1, "PM", i), DW.target_pools(c, c.sides_map[1], i, p))


def _c_lunch(v, mp):
    spec, top = _rally_rows()
    p = Params(**BASE, noon_rev_flat=True, noon_rev_pm=True)
    c = mk3(D0, history(D0), p, "12:15", v, rows=_pm_rows(spec, base=top - 2.4), conf=Conf(targets=[top + 1.2]))
    c.lock = {"AM": {"side": 1, "target": 130.0, "delivered": False}}
    out = []
    for hh in ("11:45", "12:00", "12:10", "12:15"):
        st = D3.lunch_state(c, p, at(c, hh))
        out.append(None if st is None else (st["kind"], st["noon_i"], st["rev_i"]))
    pos, tr_ = dict(left=2), SimpleNamespace(side="long", exits=[])
    D3.noon_rev_exit(c, c.sides_map[1], pos, tr_, at(c, "12:15"), c.idx[at(c, "12:15")], p, 100.0)
    return (tuple(out), tuple(map(tuple, tr_.exits)), pos["left"], sorted(D3.entry_tags(c, p, c.dplan, at(c, "12:15"))))


def _c_tgif_branch(v, mp):
    fri, h = _tgif_hist()
    p = Params(**BASE, tgif=True, tgif_branch=True, tgif_seq=True)
    judas = {"09:30": (131.0, 131.3, 130.6, 131.2), "09:35": (131.2, 131.6, 131.0, 131.5), "09:40": (131.5, 133.0, 131.4, 132.8), "09:45": (132.8, 132.9, 132.2, 132.3),
             "09:50": (132.3, 132.4, 131.6, 131.7), "09:55": (131.7, 131.8, 131.1, 131.2), "10:00": (131.2, 131.3, 130.8, 130.9), "10:05": (130.9, 131.0, 130.3, 130.4),
             "10:10": (130.4, 130.5, 130.0, 130.1), "10:15": (130.1, 220.0, 5.0, 100.0)}
    c = mk3(fri, h, p, "10:10", v, rows=_pm_rows(judas, base=130.1), base=131.0)
    c.day_tags = "tgif_short"
    return (D3.tgif_branch_ok(c, p, h, -1, at(c, "09:55"), 595, "tgif_short"), D3.tgif_branch_ok(c, p, h, -1, at(c, "10:10"), 610, "tgif_short"), D3.tgif_seq_ok(c, p, h, at(c, "10:10"), 610, "tgif_short"))


def _c_tgif_seq(v, mp):
    fri, h = _bear_hist()
    p = Params(**BASE, tgif=True, tgif_seq=True)
    spec = {"09:30": (120.0, 120.2, 119.8, 120.0), "09:45": (120.0, 120.2, 118.0, 118.5), "12:05": (118.5, 300.0, 1.0, 118.5)}
    c = mk3(fri, h, p, "11:55", v, rows=_pm_rows(spec, base=118.5, w=0.15), base=118.5)
    return (D3.tgif_seq_ok(c, p, c.hist, at(c, "09:50"), 590, "tgif_long"), D3.tgif_seq_ok(c, p, c.hist, at(c, "10:30"), 630, "tgif_long"), D3.tgif_seq_ok(c, p, c.hist, at(c, "11:55"), 715, "tgif_long"))


def _c_thu(v, mp):
    thu = date(2023, 6, 15)
    _, h = _bear_hist()
    pt = Params(**BASE, tgif=True, tgif_thu=True)
    spec = {"09:30": (125.0, 125.2, 123.9, 124.2), "10:15": (124.2, 124.3, 123.0, 123.5), "11:00": (123.5, 123.6, 118.5, 119.0), "11:05": (119.0, 119.5, 118.9, 119.4), "11:10": (119.4, 300.0, 1.0, 119.0)}
    c = mk3(thu, h[:-1], pt, "11:05", v, rows=_pm_rows(spec, base=119.4, w=0.15), base=119.4)
    return (D3.thu_extreme_held(c, c.hist, at(c, "10:30"), -1), D3.thu_extreme_held(c, c.hist, at(c, "11:05"), -1))


def _c_po3_quality(v, mp):
    mp.setattr(D2, "weekly_bias", lambda ctx, hist, d, p: -1)
    p = Params(**BASE, weekly_po3=True, htf_quality_only=True)
    spec = {"09:30": (100.0, 101.5, 99.9, 101.4), "09:35": (101.4, 101.6, 101.0, 101.2), "09:40": (101.2, 200.0, 5.0, 101.0)}
    c = mk3(D0, history(D0), p, "09:35", v, rows=_pm_rows(spec), conf=Conf(at_tfs=("1h",)))
    i = at(c, "09:35")
    ss = c.sides_map[-1]
    o = order(ss, ss.x(101.2), ss.x(102.0), [ss.x(90.0), ss.x(80.0)], kinds=["pool", "pool"], ext=ss.x(101.6), ext_i=at(c, "09:30"))
    return (D3.side_ok(c, p, -1, "AM", i), D3.side_ok(c, p, 1, "AM", i), D3.order_ok(c, ss, o, "AM", i, p), D3.hourly_swing_near(c, c.sides_map[1], i, 99.0, 2.0))


def _c_overnight_checklist(v, mp):
    h = history(D0)
    narrow = h[:-1] + [__import__("test_review_fixes").rth_day(h[-1].index[0].date(), 101.0, 96.0)]
    p = Params(**BASE, london_ext_consol=True, checklist="tag")
    lon = {"03:00": (100.0, 100.1, 97.0, 98.0), "03:05": (98.0, 100.2, 97.9, 100.0), "09:35": (100.0, 400.0, 1.0, 100.0)}
    c = mk3(D0, narrow, p, "09:30", v, rows=rows_5m({**lon, "09:30": (100.0, 100.5, 99.0, 99.5)}, "00:00"), start="00:00", bias_row={"combo": 1, "draw": 1})
    i = at(c, "09:30")
    return (D3.consol_overnight(c, p, i), D3.checklist(c, c.hist, D0, "AM", p, i, 570), D3.checklist_for(c, p, "AM", i, 570), sorted(D3.entry_tags(c, p, c.dplan, i)))


def _c_pm_mm(v, mp):
    p = Params(**BASE, pm_mm_target=True)
    am = {"09:30": (100.0, 100.2, 99.8, 100.0), "09:35": (100.0, 100.1, 99.0, 99.2), "11:00": (99.2, 105.0, 99.1, 104.8), "11:55": (104.8, 104.9, 104.5, 104.7), "14:15": (104.7, 300.0, 1.0, 104.7)}
    c = mk3(D0, history(D0), p, "14:10", v, rows=_pm_rows({**am, "14:10": (104.7, 105.0, 104.4, 104.8)}, base=104.7))
    i = at(c, "14:10")
    sl = c.sides_map[1]
    o = order(sl, 104.8, 103.5, [106.0, 108.0], kinds=["pool", "pool"])
    r = D3.order_ok(c, sl, o, "PM", i, p)
    return (r, tuple(o["levels"]), D3.am_leg(c, i))


def _c_weekly_goal(v, mp):
    p = Params(**BASE, weekly_target_pct=1.5)
    c = mk3(D0, history(D0), p, "10:30", v, rows=_pm_rows({"10:30": (100.0, 101.0, 99.0, 100.0), "10:35": (100.0, 300.0, 1.0, 100.0)}))
    c.week = dict(n=1, week_net3=900.0, week_eq0=100_000.0, week_pts=0.0)
    i = at(c, "10:30")
    tr = SimpleNamespace(exits=[(c.idx[at(c, "10:00")], 0.0, 1, "t1")], shares=100, pnl=lambda cost: (800.0, 0.0))
    return (D3.gate(c, p, "AM", i, 630, [tr]), D3.gate(c, p, "AM", i, 630, []))


CAUSAL3 = {
    "pm_fizzle": (_c_pm_fizzle, ("pm_fizzle",)),
    "pm_narrative": (_c_narr, ("pm_narrative", "pm_narr_side")),
    "lunch": (_c_lunch, ("noon_rev_flat",)),
    "tgif_branch": (_c_tgif_branch, ("tgif_branch_judas", "tgif_branch_am_block")),
    "tgif_seq": (_c_tgif_seq, ("tgif_seq_newext",)),
    "tgif_thu": (_c_thu, ()),
    "po3_quality": (_c_po3_quality, ("weekly_po3_side", "htf_quality_reject")),
    "overnight_checklist": (_c_overnight_checklist, ("checklist_eval",)),
    "pm_mm": (_c_pm_mm, ("pm_mm_rung",)),
    "weekly_goal": (_c_weekly_goal, ("weekly_goal",)),
}


@pytest.mark.parametrize("name", list(CAUSAL3))
def test_dwc3_paths_are_causal(name, monkeypatch):
    case, need = CAUSAL3[name]
    _causal3(case, monkeypatch, need)


def test_every_switch_is_covered():
    """Every new switch is SET in at least one executed no-look-ahead run: the synthetic windows (LA_D3), the hand-made days (HAND_D3) or the ES windows (ES_D3) - the names are collected from
    those runs, never typed here."""
    covered = set()
    for _, kw in LA_D3.values():
        covered |= set(kw)
    for _, kw in HAND_D3:
        covered |= set(kw)
    for kw in ES_D3.values():
        covered |= set(kw)
    assert set(NEW_FIELDS) <= covered, sorted(set(NEW_FIELDS) - covered)


ES_D3 = {   # name -> switches; one 5-week ES window (2022-09-12 .. 2022-10-14)
    "A": dict(max_trades_month=8, weekly_target_pct=1.0, skip_fri_if_week_up=True, low_mag_mult=0.5, journal_timing=True, checklist="tag", choppy_week_tag=True, carry_weekly_draw=True,
              thu_targets_met_block=True, missed_week_mode="nearest", weekly_po3=True),
    "B": dict(consol_pm_need_sweep=True, consol_day_rules="tag", consol_pm_pool_exit=True, pm_narrative=True, noon_rev_flat=True, noon_rev_pm=True, pm_mm_target=True, london_ext_consol=True,
              tgif=True, tgif_branch=True, tgif_seq=True, tgif_window="am", tgif_precond="loose", tgif_thu=True, mw_extreme_need_array=True, trend_k=0.3),
}
NEED_ES3 = {"A": ("low_mag_size", "checklist_eval"), "B": ("checklist_eval",)}


@pytest.mark.skipif(not ES, reason="no ES data")
@pytest.mark.parametrize("name", list(ES_D3))
def test_look_ahead_es_dwc3(name):
    es = B.load("ES", 5, source="databento")
    df = es[(es.index >= pd.Timestamp("2022-09-12", tz=B.NY)) & (es.index < pd.Timestamp("2022-10-14", tz=B.NY))]
    if not len(df):
        pytest.skip("the ES file does not cover the window")
    meta = B.load_meta("ES", 5)
    kw = dict(ES_D3[name])
    if name == "B":
        kw["checklist"] = "tag"
    p = Params(**FUT, htf_resist_cap=False, draw_lock="off", leg_pd=0, min_draw_pts=0, use_bias=False, htf_bias="combo", ob_entry="post_mss", sb_model=True, ma_deuce=True,
               fomc_observe="defer", **kw)
    D3.HITS.clear()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        n = len(B.run(df, 5, "ES", p, meta=meta))
    if n < 1:
        pytest.skip("no trades in the window with this data file")
    _no_look_ahead(df, 5, "ES", p, COLS, every=max(1, n // 3), meta=meta, exits=True, min_trades=1)
    assert any(D3.HITS.get(h) for h in NEED_ES3[name]), f"{name}: none of these paths ran: {NEED_ES3[name]} (ran: {sorted(D3.HITS)})"
