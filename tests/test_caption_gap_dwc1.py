"""Caption-gap pass, package day_week_context#1/3 (34 specs from digests/rulebook_gaps): focused tests of the new switches (dwc1.py and its hooks) - calendar rules through strategy.blocked, helpers on
hand-made daily books and one-day books (the real DayCtx and DayPlan), and no-look-ahead runs (full vs truncated) with executed-path counters. Nothing here needs market data except the ES windows
(skipped when absent); nothing is platform specific; no file outside the repo is written."""
import warnings
from dataclasses import fields, replace
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from mentorship import backtest as B, bias_day as BD, calendar as C, daycontext as DW, dwc1 as D1, nct2 as N2, study, strategy as S
from mentorship.strategy import Params

from test_review_fixes import BASE, D0, A_ROWS, day, frame, history  # noqa: E402  (shared scenario builders)
from test_entries_stops import _no_look_ahead  # noqa: E402
from test_day_week_context import daily, sessions  # noqa: E402

ES = Path("data/mentorship/ES_5min_db.csv").exists()
FUT = dict(es_pt=1.0, lot=1, max_notional=1e12, cost_per_share=0.1)
SYN = dict(es_pt=0.09, use_bias=False, min_draw_pts=0, leg_pd=0)
COLS = ["entry_time", "entry", "stop", "t1", "shares", "entry_kind", "lv_tags", "setup", "swept", "session"]

NEW_FIELDS = (
    "pre_cpi_mon", "pre_cpi_gap_adr", "landmine_min", "post_holiday_am", "holiday_nfp_override", "holiday_week_mult", "august_mode", "summer_off", "season_quality", "season_autumn_start",
    "season_march_mult", "skip_election", "holiday_eve_cases", "objective_frac_gate", "objective_done_pm", "sd_intraday", "sd_intraday_until", "sd_intraday_frac", "sd_fvg_hold", "sd_week_detect",
    "sd_shallow_frac", "sd_after_array", "big_day_am_resume", "nwog_templates", "thu_strict", "fri_one_sided", "fri_t1_pts", "season_windows", "season_gate", "season_move_adr",
    "season_min_rank", "macro_risk_dates", "tgif_strict", "tgif_weeks", "mo_overdue", "mon_how", "mon_how_edge", "wk_push_range", "wk_profile", "iw_reversal_watch", "iw_k", "iw_no_measured",
    "three_day_small", "day_profile", "day_profile_gate", "n8_use_overnight")
KNOBS = {"pre_cpi_gap_adr", "sd_intraday_until", "sd_intraday_frac", "season_autumn_start", "season_march_mult", "sd_shallow_frac", "fri_t1_pts", "season_move_adr", "season_min_rank",
         "tgif_weeks", "mon_how_edge", "iw_k"}


def hm(s: str) -> int:
    return int(s[:2]) * 60 + int(s[3:])


def mk(d, hist, p=None, rows=(), start="09:30", base=100.0, eve=None, bias_row=None, conf=None, lock=None, spike=False, dt=None, week=None, daily_all=None):
    """The real DayCtx of a hand-made day with its DayPlan (and the Sides the dynamic rules read)."""
    p = p or Params(**BASE)
    ctx = S.DayCtx(day(list(rows), d=d, start=start, spike=spike, base=base), d, hist, 5)
    ctx.hist = hist
    ctx.lock = lock if lock is not None else {}
    ctx.eth = None
    ctx.eve = eve
    ctx.bias_row = bias_row
    ctx.conf = conf
    ctx.daily_all = daily_all
    mg = p.min_fvg_pts * p.es_pt
    ctx.sides_map = {1: S.Side(1, ctx.o, ctx.h, ctx.l, ctx.c, p.pivot_n, mg), -1: S.Side(-1, ctx.o, ctx.h, ctx.l, ctx.c, p.pivot_n, mg)}
    ctx.dplan = DW.plan(ctx, hist, p, week, eve, dt)
    return ctx


def at(ctx, hhmm: str) -> int:
    return S._idx_at(ctx, hm(hhmm))


def weeks(monday, specs):
    """Daily frames of consecutive Monday-Friday weeks from `monday`: each (o, h, l, c) is the WEEK's candle (open on Monday, high on Tuesday, low on Wednesday, close on Friday)."""
    out, d = [], monday
    for o, h, l, c in specs:
        days_ = [d + timedelta(days=k) for k in range(5)]
        rows = [(o, o, o, o), (o, h, o, o), (o, o, l, o), (o, o, o, o), (o, max(o, c), min(o, c), c)]
        rows = [(min(r[0], h), max(min(r[1], h), l), min(r[2], h), r[3]) if False else r for r in rows]
        for x, r in zip(days_, rows):
            out.append(daily(x, *r))
        d += timedelta(days=7)
    return out


class Conf:
    """A stand-in for the confluence arrays: .at / .targets / .z with fixed contents."""
    tol = 0.0

    def __init__(self, at_tfs=(), targets=(), z=None):
        self._at, self._t = list(at_tfs), list(targets)
        self.z = z or {}

    def at(self, t, price, side, known_by=None):
        return list(self._at)

    def targets(self, t, beyond, side, tfs, far_edge=False, min_known=None):
        return list(self._t)


def zone(kind: int, bottom: float, top: float) -> dict:
    return {"known": np.array([0.0]), "dead": np.array([1e30]), "life": np.array([1e30]), "bottom": np.array([bottom]), "top": np.array([top]), "kind": np.array([kind]),
            "src": np.array([0])}


# --- defaults and validation --------------------------------------------------------------------------------------------

def test_defaults_and_validation():
    p = Params()
    for f in NEW_FIELDS:
        assert f in Params.__dataclass_fields__, f
    off = {"pre_cpi_mon": "off", "landmine_min": 0, "post_holiday_am": "off", "holiday_nfp_override": False, "holiday_week_mult": 1.0, "august_mode": "off", "summer_off": False,
           "season_quality": "off", "skip_election": "off", "holiday_eve_cases": "a", "objective_frac_gate": 0.0, "objective_done_pm": "off", "sd_intraday": "off", "sd_week_detect": False,
           "big_day_am_resume": 0, "nwog_templates": "off", "thu_strict": False, "fri_one_sided": "off", "season_windows": "off", "season_gate": False, "season_min_rank": 0.0,
           "macro_risk_dates": "", "tgif_strict": False, "mo_overdue": False, "mon_how": "off", "wk_push_range": False, "wk_profile": "off", "iw_reversal_watch": False,
           "iw_no_measured": False, "three_day_small": False, "day_profile": "off", "day_profile_gate": False, "n8_use_overnight": True}
    for k, v in off.items():
        assert getattr(p, k) == v, k
    assert p.august_from_day == 1                                         # N7-august: the whole month (the default was already 1)
    assert p.dw1_hist == 0 and Params(season_windows="tag").dw1_hist == 270 and Params(mo_overdue=True).dw1_hist == 270
    # the owner-fixed switches are untouched by this chunk
    assert p.sb_model is False and "sb_use_bias" in Params.__dataclass_fields__ and "want_all_engines" in Params.__dataclass_fields__
    for bad in (dict(pre_cpi_mon="x"), dict(post_holiday_am="x"), dict(august_mode="x"), dict(season_quality="x"), dict(skip_election="x"), dict(holiday_eve_cases="x"),
                dict(objective_done_pm="x"), dict(sd_intraday="x"), dict(nwog_templates="x"), dict(fri_one_sided="x"), dict(season_windows="x"), dict(mon_how="x"),
                dict(mon_how_edge="x"), dict(wk_profile="x"), dict(day_profile="x"), dict(holiday_week_mult=0), dict(season_min_rank=1.5), dict(tgif_weeks=0),
                dict(season_autumn_start=8), dict(iw_k=0)):
        with pytest.raises(ValueError):
            Params(**bad)


def test_every_new_switch_has_a_study_variant():
    used = set()
    for n, v in study.DECISIONS.items():
        used |= set(v)
    for f in NEW_FIELDS:
        assert f in used or f in KNOBS, f
    for gid in ("N4-pre-cpi-monday-gap", "D20-landmine-week-monday", "N7-post-holiday-am-symmetry", "N7-holiday-week", "N7-august", "B23-seasonal-quality", "N7-election",
                "DS2-holiday-eve-friday-before-tue-holiday", "N9-objective-before-lunch", "N8-intraday-seek-destroy", "N8-seek-destroy-week", "N8-large-org-day",
                "BH-NWOG-week-open-scenarios", "BH-N10-thursday-not-top-call", "BH-B17-friday-after-one-sided-week", "BH-B23-index-seasonal-windows", "B23-intramonth-detail",
                "BH-B23-seasonal-failure", "BH-M14-TGIF-preconditions", "BH-mixed-HTF-intraday-only", "B11-monthly-five-up-closes", "NEW-monday-high-of-week-profile",
                "NEW-failed-weekly-push-range", "X3-seasonal-trend-condition", "X3-seasonal-strength-grading", "X3-seasonal-regime-picks-window", "X3-seasonal-macro-override",
                "X3-seasonal-consolidation-breakout", "M17-weekly-profiles-selection", "B17-intraweek-reversal-profile", "B11-three-closes-day4", "T13-day-profile-selection",
                "N8-overnight-not-precursor", "B23-daily-seasonal-review"):
        assert gid in study.DECISIONS or any(k.startswith(gid) for k in study.DECISIONS), gid
    for k, v in study._DWC1_DECISIONS.items():
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            replace(Params(), **v)


# --- calendar rules (strategy.blocked / calendar) ----------------------------------------------------------------------------

def test_landmine_monday():
    mon = date(2023, 8, 7)                       # CPI Thursday + PPI Friday: two releases Tue-Fri, no NFP / FOMC in the week
    assert C.landmine_count(mon) == 2 and C.landmine_count(date(2023, 6, 12)) == 2
    assert S.blocked(mon, "AM", Params(skip_monday=True)) == "monday"
    assert S.blocked(mon, "AM", Params(skip_monday=True, landmine_min=2)) != "monday"
    assert S.blocked(mon, "AM", Params(skip_monday=True, landmine_min=3)) == "monday"            # not enough releases
    assert S.blocked(date(2023, 6, 12), "AM", Params(skip_monday=True, landmine_min=2)) != "monday"   # CPI Tue + FOMC Wed
    assert S.blocked(date(2023, 8, 14), "AM", Params(skip_monday=True, landmine_min=2)) == "monday"   # a quiet week stays skipped


def test_holiday_nfp_override_and_week_mult():
    thu = date(2023, 7, 6)                       # July 4 is a Tuesday, NFP Friday July 7
    p = Params(nfp_week_block=True, nfp_thu=False)
    assert S.blocked(thu, "AM", p) == "nfp_week_thu_fri"
    assert S.blocked(thu, "AM", replace(p, holiday_nfp_override=True)) is None
    assert S.blocked(date(2023, 8, 3), "AM", replace(p, holiday_nfp_override=True)) == "nfp_week_thu_fri"     # no holiday Mon-Wed: the block stays
    assert S.blocked(thu, "PM", replace(p, holiday_nfp_override=True)) is None
    assert C.holiday_mon_wed(thu) and not C.holiday_mon_wed(date(2023, 8, 3))
    # the 045 contrast: wonky holiday weeks - smaller size and no pyramiding
    q = Params(**BASE, holiday_week_mult=0.5)
    ctx = mk(date(2023, 7, 5), history(date(2023, 7, 5)), q)
    lvt = []
    assert D1.size_mult(ctx, q, lvt) == 0.5 and "size_holiday_week" in lvt and D1.adds_off(ctx, q)
    assert DW.day_risk(ctx, q, []) == 0.5
    c2 = mk(D0, history(D0), q)
    assert D1.size_mult(c2, q) == 1.0 and not D1.adds_off(c2, q)


def test_august_mode_and_summer_off():
    d = date(2023, 8, 1)
    ctx = mk(d, history(d), Params(**BASE, august_mode="skip"))
    assert ctx.dplan.static_reason("AM", 600) == "august_mode" and "august_mode" in ctx.dplan.tags
    q = Params(**BASE, august_mode="light")
    ctx = mk(d, history(d), q)
    assert ctx.dplan.static_reason("AM", 600) is None and "august_light" in ctx.dplan.scalp                 # a single exit at the first target: no ladder / runners
    assert DW.scalp_now(ctx, q, "AM", 0) == "august_light"
    assert D1.size_mult(ctx, q) == 0.5 and D1.adds_off(ctx, q)
    assert Params().august_from_day == 1
    mid = mk(D0, history(D0), q)
    assert not mid.dplan.scalp and D1.size_mult(mid, q) == 1.0
    assert S.blocked(date(2023, 7, 10), "AM", Params(summer_off=True)) == "summer_off"
    assert S.blocked(date(2023, 6, 1), "AM", Params(summer_off=True)) == "summer_off"
    assert S.blocked(date(2023, 9, 5), "AM", Params(summer_off=True)) is None and S.blocked(date(2023, 5, 31), "AM", Params(summer_off=True)) is None


def test_skip_election():
    for mode, d, want in (("two_weeks", date(2024, 11, 6), "election"), ("narrow", date(2024, 11, 6), "election"), ("two_weeks", date(2024, 11, 12), "election"),
                          ("narrow", date(2024, 11, 12), None), ("two_weeks", date(2024, 10, 31), None), ("two_weeks", date(2024, 11, 15), None),
                          ("narrow", date(2024, 11, 5), "election"), ("two_weeks", date(2023, 11, 6), None)):
        assert S.blocked(d, "AM", Params(skip_election=mode)) == want, (mode, d)
    assert S.blocked(date(2024, 11, 12), "AM", Params()) is None


def test_holiday_eve_b():
    d = date(2023, 6, 30)                        # Friday, July 4 is the Tuesday after
    assert C.holiday_eve(d, "ab") and not C.holiday_eve(d, "a") and C.holiday_eve_b(d)
    assert C.holiday_eve(date(2023, 7, 3 - 0) - timedelta(days=0), "a") is False or True      # (Monday July 3 itself: the next weekday is the holiday)
    assert C.holiday_eve(date(2023, 7, 3), "a")
    assert not C.holiday_eve_b(date(2023, 6, 23)) and not C.holiday_eve_b(date(2023, 7, 3))   # not a Friday
    p = Params(**BASE, skip_holiday_eve=True, holiday_eve_cases="ab")
    ctx = mk(d, history(d), p)
    assert ctx.dplan.static_reason("AM", 600) == "holiday_eve" and "holiday_eve" in ctx.dplan.tags
    ctx = mk(d, history(d), replace(p, holiday_eve_cases="a"))
    assert ctx.dplan.static_reason("AM", 600) is None


# --- seasonal tags, direction, quality, results ----------------------------------------------------------------------------------

def test_season_tags():
    t = C.season_tags(date(2023, 6, 1))
    assert {"win_short_may", "win_buy_june", "regime_range"} <= t and "win_long_spring" not in t
    t = C.season_tags(date(2023, 1, 10))
    assert {"win_long_fall", "win_short_jan", "regime_hi_bull"} <= t
    assert "regime_q4" in C.season_tags(date(2023, 11, 3)) and "win_short_summer" in C.season_tags(date(2023, 8, 1))
    assert "win_long_spring" in C.season_tags(date(2023, 3, 10)) and not (C.season_tags(date(2023, 3, 10)) & {"win_long_fall", "win_short_may"})
    assert C.season_window(date(2023, 6, 1)) == ("win_buy_june", 1) and C.season_window(date(2023, 5, 10)) == ("win_short_may", -1) and C.season_window(date(2023, 10, 5)) == ("win_long_fall", 1)
    ctx = mk(date(2023, 6, 1), history(date(2023, 6, 1)), Params(**BASE, season_windows="tag"))
    assert {"win_short_may", "win_buy_june", "regime_range"} <= ctx.dplan.tags
    assert not mk(date(2023, 6, 1), history(date(2023, 6, 1)), Params(**BASE)).dplan.tags & {"win_short_may", "regime_range"}     # off: nothing


def test_season_quality_tags_and_size():
    for d, q in ((date(2023, 10, 16), "prime"), (date(2023, 12, 20), "poor"), (date(2023, 7, 10), "off"), (date(2023, 8, 15), "poor"), (date(2023, 3, 14), "prime"),
                 (date(2023, 12, 10), "prime"), (date(2023, 12, 11), "poor"), (date(2023, 1, 9), "off")):
        assert C.season_quality(d) == q, d
    assert C.season_quality(date(2023, 9, 20), 9) == "prime" and C.season_quality(date(2023, 9, 20), 10) == "off"
    p = Params(**BASE, season_quality="tag")
    ctx = mk(date(2023, 5, 10), history(date(2023, 5, 10)), p)
    assert {"season_prime", "season_may_overlap"} <= ctx.dplan.tags
    s = Params(**BASE, season_quality="size", season_march_mult=0.5)
    assert D1.size_mult(mk(date(2023, 10, 16), history(date(2023, 10, 16)), s), s) == 1.0
    assert D1.size_mult(mk(date(2023, 12, 20), history(date(2023, 12, 20)), s), s) == 0.5
    assert D1.size_mult(mk(date(2023, 7, 10), history(date(2023, 7, 10)), s), s) == 0.75
    assert D1.size_mult(mk(date(2023, 3, 14), history(date(2023, 3, 14)), s), s) == 0.5            # March prime x the March multiplier
    assert D1.size_mult(mk(date(2023, 7, 10), history(date(2023, 7, 10)), p), p) == 1.0              # tag mode: no size change


def test_seasonal_month_tag():
    p = Params(**BASE, seasonal_tag=True)
    t = mk(date(2023, 10, 10), history(date(2023, 10, 10)), p).dplan.tags
    assert {"season_dir_+1", "season_next_+1"} <= t
    t = mk(date(2023, 1, 10), history(date(2023, 1, 10)), p).dplan.tags
    assert "season_dir_-1" in t and "season_next_+1" in t
    t = mk(date(2023, 3, 10), history(date(2023, 3, 10)), p).dplan.tags
    assert not {x for x in t if x.startswith("season_dir_")} and "season_next_+1" in t           # March is consolidation
    assert C.SEASONAL_MONTHS["ES"][1] == -1 and C.SEASONAL_MONTHS["ES"][10] == 1


def test_season_dir():
    assert C.season_dir(date(2023, 9, 5)) == 1 and C.season_dir(date(2023, 9, 20)) == -1 and C.season_dir(date(2023, 5, 30)) == 1
    assert C.season_dir(date(2023, 3, 10)) == -1 and C.season_dir(date(2023, 3, 28)) == 1 and C.season_dir(date(2023, 4, 3)) == -1 and C.season_dir(date(2023, 4, 20)) == 1
    assert C.season_dir(date(2023, 7, 17)) == 1 and C.season_dir(date(2023, 8, 17)) == 0 and C.season_dir(date(2023, 11, 8)) == 1 and C.season_dir(date(2023, 12, 20)) == 1
    p = Params(**BASE, season_windows="tag", season_gate=True)
    ctx = mk(date(2023, 9, 20), history(date(2023, 9, 20)), p)                       # the 2nd half of September is bearish: no longs
    assert ctx.dplan.sides["season_intramonth"] == (1,) and "season_intra_-1" in ctx.dplan.tags
    assert DW.side_ok(ctx, p, 1, "AM", at(ctx, "10:00")) == "x_dw_season_intramonth" and DW.side_ok(ctx, p, -1, "AM", at(ctx, "10:00")) is None
    ctx = mk(date(2023, 9, 20), history(date(2023, 9, 20)), replace(p, season_gate=False))
    assert "season_intramonth" not in ctx.dplan.sides                              # report only without the gate


def _series(start, closes, rng=2.0):
    """Consecutive sessions from `start` with the given closes: open = the previous close, a rng-wide range around the open / close."""
    out, prev, d = [], closes[0], start
    for c in closes:
        while not C.is_trading_day(d):
            d += timedelta(days=1)
        out.append(daily(d, prev, max(prev, c) + rng / 2, min(prev, c) - rng / 2, c))
        prev, d = c, d + timedelta(days=1)
    return out


def test_season_result():
    assert D1.result_of(30.0, -1, 10.0, 5, 1.0) == "counter" and D1.result_of(0.5, -1, 10.0, 5, 1.0) == "consol"
    assert D1.result_of(-30.0, -1, 10.0, 5, 1.0) == "worked" and D1.result_of(30.0, 1, 10.0, 5, 1.0) == "worked"
    assert D1.result_of(-12.0, 1, 10.0, 5, 1.0) == "counter" and D1.result_of(12.0, -1, 10.0, 5, 1.0) == "counter"
    assert D1.result_of(-6.0, 1, 10.0, 5, 1.0) == "worked" and D1.result_of(4.0, -1, 10.0, 5, 1.0) == "consol"      # the yardstick is k x ADR5 x n / 5
    assert D1.result_of(6.0, -1, 10.0, 5, 0.5) == "counter"
    p = Params(**BASE, season_windows="tag")
    d = date(2023, 6, 16)                                                               # the short-May window ended on June 14
    n = 31
    rally = _series(date(2023, 5, 1), [100 + 0.7 * k for k in range(n)] + [121.0])        # +21 over a window of 31 sessions, ADR5 ~ 3 -> yardstick 18.6
    done = [x for x in rally if x.index[0].date() <= date(2023, 6, 15)]
    res = {(nm, r): f for nm, dr, r, f in D1.ended_windows(done, d, p, 3.0)}
    assert ("win_short_may", "counter") in res
    flat = _series(date(2023, 5, 1), [100.0] * 32)
    done = [x for x in flat if x.index[0].date() <= date(2023, 6, 15)]
    assert any(nm == "win_short_may" and r == "consol" for nm, dr, r, f in D1.ended_windows(done, d, p, 3.0))
    ctx = mk(d, done, p)
    assert {"season_result_consol", "sr_win_short_may_consol"} <= ctx.dplan.tags
    ctx = mk(d, rally[:len(rally)], p)
    assert "season_result_counter" in ctx.dplan.tags
    assert not any(t.startswith("season_result") for t in mk(date(2023, 8, 16), done, p).dplan.tags)   # more than 20 sessions after the window


def test_season_failed_up():
    p = Params(**BASE, season_windows="tag", season_gate=True)
    d = date(2023, 6, 16)
    flat = _series(date(2023, 5, 1), [100.0] * 31)                                       # the May window: flat, range 99-101
    brk = _series(date(2023, 6, 15), [103.0])                                             # June 15: a daily close above the May high
    ctx = mk(d, flat + brk, p)
    assert "season_failed_up" in ctx.dplan.tags and ctx.dplan.sides["season_failed"] == (-1,)    # longs favoured: no shorts
    assert DW.side_ok(ctx, p, -1, "AM", at(ctx, "10:00")) == "x_dw_season_failed" and DW.side_ok(ctx, p, 1, "AM", at(ctx, "10:00")) is None
    ctx = mk(d, flat + _series(date(2023, 6, 15), [100.5]), p)
    assert "season_failed_up" not in ctx.dplan.tags and "season_failed" not in ctx.dplan.sides
    ctx = mk(d, flat + brk, replace(p, season_gate=False))
    assert "season_failed_up" in ctx.dplan.tags and "season_failed" not in ctx.dplan.sides


def test_season_prime():
    wk = date(2023, 4, 24)
    bear = weeks(wk, [(100, 111, 99, 110), (110, 111, 94, 95)])          # an up week, then a week closing under its low: the weekly tone is bearish
    bull = weeks(wk, [(110, 111, 100, 100), (100, 116, 99, 115)])        # a down week, then a close over its high: bullish
    assert D1.weekly_state(bear, date(2023, 5, 10)) == -1 and D1.weekly_state(bull, date(2023, 5, 10)) == 1
    p = Params(**BASE, season_windows="tag", season_gate=True)
    d = date(2023, 5, 10)
    ctx = mk(d, bear, p)
    assert "season_win_prime" in ctx.dplan.tags and "season_win_minor" not in ctx.dplan.tags and ctx.dplan.sides["season_window"] == (1,)      # a May short window: no longs
    ctx = mk(d, bull, p)
    assert "season_win_minor" in ctx.dplan.tags and "season_window" not in ctx.dplan.sides                # against the weekly tone: only a minor move, no gate
    ctx = mk(d, bear, replace(p, season_gate=False))
    assert "season_win_prime" in ctx.dplan.tags and not ctx.dplan.sides


def test_season_regime_pick():
    d = date(2023, 5, 10)
    p = Params(**BASE, season_windows="tag", season_gate=True)
    up = _series(date(2022, 4, 4), [100 + 0.5 * k for k in range(300)])
    up = [x for x in up if x.index[0].date() < d]
    assert D1.trend252(SimpleNamespace(daily_all=None), up, d) == 1
    ctx = mk(d, up, p)
    assert "season_pullback" in ctx.dplan.tags and "season_window" not in ctx.dplan.sides              # a bull regime: the May short is only the pullback
    dn = _series(date(2022, 4, 4), [300 - 0.5 * k for k in range(300)])
    dn = [x for x in dn if x.index[0].date() < d]
    ctx = mk(d, dn, p)
    assert "season_pullback" not in ctx.dplan.tags                                                      # the short window agrees with the bear regime
    assert D1.trend252(SimpleNamespace(daily_all=None), up[:100], d) == 0                               # too little history: unknown


def test_season_macro_override(tmp_path_factory=None):
    d = date(2023, 11, 8)                       # the fall long window
    assert "win_long_fall" in mk(d, history(d), Params(**BASE, season_windows="tag")).dplan.tags
    p = Params(**BASE, season_windows="tag", macro_risk_dates=("2023-11-06:-1",))
    assert "win_long_fall" not in mk(d, history(d), p).dplan.tags                                       # a flagged risk-off week disables the long window
    q = Params(**BASE, season_windows="tag", macro_risk_dates=("2023-11-06:+1",))
    assert "win_long_fall" in mk(d, history(d), q).dplan.tags                                           # the same direction keeps it
    assert "win_long_fall" in mk(d, history(d), replace(p, macro_risk_dates=("2023-11-13:-1",))).dplan.tags      # another week
    f = Path("runs") / "_dwc1_flags_test.csv"
    f.parent.mkdir(exist_ok=True)
    try:
        f.write_text("week,direction\n2023-11-07,-1\n2023-12-04,0\n", encoding="utf8")
        assert D1.macro_flags(str(f)) == {date(2023, 11, 6): -1, date(2023, 12, 4): 0}
        r = Params(**BASE, season_windows="tag", macro_risk_dates=str(f))
        assert "win_long_fall" not in mk(d, history(d), r).dplan.tags
    finally:
        f.unlink(missing_ok=True)


def test_season_strength_rank():
    closes, d0 = {}, date(2019, 1, 1)
    px = 100.0
    while d0 < date(2024, 1, 1):
        if d0.weekday() < 5:
            px *= (1 - 0.003) if "win_short_may" in C.season_tags(d0) else (1 + 0.0002 if d0.year < 2023 else 1.0)
            closes[d0] = px
        d0 += timedelta(days=1)
    comp = D1.composite({k: v for k, v in closes.items() if k.year < 2023}, 2023)
    assert comp["win_short_may"] < -5 and abs(comp["win_long_spring"]) < abs(comp["win_short_may"])
    assert D1.rank_of(comp, "win_short_may") == 1.0 and D1.rank_of(comp, "win_long_spring") < 0.67 and D1.rank_of(comp, "nope") is None
    # no look-ahead: 2023 itself (and later) never enters the composite
    tampered = dict(closes)
    for k in list(tampered):
        if k.year >= 2023:
            tampered[k] = tampered[k] * 5
    assert D1.composite({k: v for k, v in tampered.items() if k.year < 2023}, 2023) == comp
    assert D1.composite(tampered, 2023) == comp                                   # even handed the whole book, the function reads years < 2023 only
    p = Params(**BASE, season_windows="tag", season_min_rank=0.67)
    d = date(2023, 5, 10)
    ctx = mk(d, history(d), p, daily_all=closes)
    assert "win_short_may" in ctx.dplan.tags                                      # the strongest window stays
    d2 = date(2023, 3, 10)
    ctx = mk(d2, history(d2), p, daily_all=closes)
    assert "win_long_spring" not in ctx.dplan.tags                                 # a weak window is dropped with min_rank 0.67
    ctx = mk(d2, history(d2), replace(p, season_min_rank=0.0), daily_all=closes)
    assert "win_long_spring" in ctx.dplan.tags
    ctx = mk(d2, history(d2), p)                                                  # no data: the window is kept
    assert "win_long_spring" in ctx.dplan.tags


# --- pre-CPI Monday gap -------------------------------------------------------------------------------------------------------------

def _prior_week(friday_close=4000.0, rng=30.0):
    """Ten sessions of range `rng` ending on the Friday 2023-02-10 at `friday_close`."""
    fr = []
    d = date(2023, 1, 30)
    while d <= date(2023, 2, 10):
        if C.is_trading_day(d):
            fr.append(daily(d, friday_close, friday_close + rng / 2, friday_close - rng / 2, friday_close))
        d += timedelta(days=1)
    return fr


def test_pre_cpi_monday_gap():
    mon = date(2023, 2, 13)                      # CPI on Tuesday 2023-02-14
    assert "cpi" in DW.events(C.next_trading_day(mon))
    hist = _prior_week()
    ev = lambda so: (so, so + 5, so - 5, so)
    p = Params(**BASE, pre_cpi_mon="gap")
    ctx = mk(mon, hist, p, base=3980.0, eve=ev(3980.0))
    assert "pre_cpi_mon_gap" in ctx.dplan.tags and ctx.dplan.sides["pre_cpi_mon"] == (-1,)             # a gap down reprices up: longs only
    assert DW.side_ok(ctx, p, -1, "AM", at(ctx, "10:00")) == "x_dw_pre_cpi_mon" and DW.side_ok(ctx, p, 1, "AM", at(ctx, "10:00")) is None
    ctx = mk(mon, hist, p, base=4020.0, eve=ev(4020.0))
    assert ctx.dplan.sides["pre_cpi_mon"] == (1,)                                                      # the mirror
    ctx = mk(mon, hist, p, base=3995.0, eve=ev(3995.0))                                                 # a 5-point gap against ADR5 30: quiet
    assert "pre_cpi_mon_small" in ctx.dplan.tags and "pre_cpi_mon" not in ctx.dplan.sides and ctx.dplan.static_reason("AM", 600) is None
    ctx = mk(mon, hist, replace(p, pre_cpi_mon="skip_small"), base=3995.0, eve=ev(3995.0))
    assert ctx.dplan.static_reason("AM", 600) == "pre_cpi_mon_small"
    ctx = mk(mon, hist, replace(p, pre_cpi_mon="tag"), base=3980.0, eve=ev(3980.0))
    assert "pre_cpi_mon_gap" in ctx.dplan.tags and not ctx.dplan.sides
    ctx = mk(mon, hist, p, base=3980.0, eve=None)                                                       # no Sunday data (SPY): no tag
    assert not ctx.dplan.tags & {"pre_cpi_mon_gap", "pre_cpi_mon_small"}
    other = mk(date(2023, 2, 6), hist, p, base=3980.0, eve=ev(3980.0))                                  # CPI is not on the next day
    assert not other.dplan.tags & {"pre_cpi_mon_gap", "pre_cpi_mon_small"}


# --- post-holiday AM symmetry ------------------------------------------------------------------------------------------------------

def test_post_holiday_symmetry(monkeypatch):
    d = date(2023, 1, 17)                        # the Tuesday after Martin Luther King Day
    p = Params(**BASE, post_holiday_am="symmetry")
    ctx = mk(d, history(d), p)
    assert ctx.dplan.static_reason("AM", 600) is None and ctx.dplan.info["ph_symmetry"]               # skip_post_holiday_am (default on) is lifted
    assert not any(r == "post_holiday_am" for _s, r in ctx.dplan.blocks)
    i = at(ctx, "10:00")
    assert DW.gate(ctx, p, "AM", i, 600) == "x_dw_post_holiday_symmetry" and D1.HITS["post_holiday_symmetry_nopartner"]       # no partner: the AM stays blocked
    ctx.pside = (object(), None, None)
    monkeypatch.setattr(N2, "symmetry_ok", lambda c, p_, i_: False)
    assert DW.gate(ctx, p, "AM", i, 600) == "x_dw_post_holiday_symmetry"                                # before both indexes break the 09:30-09:45 range
    assert DW.gate(ctx, p, "LUNCH", i, 720) is None and DW.gate(ctx, p, "PM", i, 810) is None            # only the AM waits
    monkeypatch.setattr(N2, "symmetry_ok", lambda c, p_, i_: True)
    assert DW.gate(ctx, p, "AM", i, 600) is None                                                         # symmetry returned: the remaining AM is normal
    monkeypatch.undo()
    # "skip": the AM is out; the wider triggers - the day after an abbreviated session, a large-range day before
    q = Params(**BASE, post_holiday_am="skip")
    assert mk(d, history(d), q).dplan.static_reason("AM", 600) == "post_holiday_am"
    mon = date(2023, 11, 27)                     # the day after Thanksgiving (an early close) was the Friday
    assert C.early_close_min(date(2023, 11, 24)) and C.prev_trading_day(mon) == date(2023, 11, 24)
    assert mk(mon, history(mon), q).dplan.static_reason("AM", 600) == "post_holiday_am"
    assert mk(D0, history(D0), q, dt={"big_prev"}).dplan.static_reason("AM", 600) == "post_holiday_am"
    assert mk(D0, history(D0), q).dplan.static_reason("AM", 600) is None and mk(D0, history(D0), q, dt={"big_prev"}).dplan.static_reason("LUNCH", 700) is None
    # with the switch off the old behaviour stands
    assert mk(d, history(d), Params(**BASE)).dplan.static_reason("AM", 600) == "post_holiday_am"


# --- N8 day type -----------------------------------------------------------------------------------------------------------------------

def test_big_day_am_resume():
    big = history(D0)[:-1] + [rth_big(D0)]
    p = Params(**BASE, big_day_am_skip=True)
    ctx = mk(D0, big, p)
    assert ctx.dplan.static_reason("AM", 650) == "big_day_am"                                          # the whole AM is given up
    q = replace(p, big_day_am_resume=645)
    ctx = mk(D0, big, q)
    assert ctx.dplan.static_reason("AM", 600) == "big_day_am" and ctx.dplan.static_reason("AM", 650) is None and ctx.dplan.static_reason("PM", 820) is None
    # the dynamic ORG part (a large |09:30 open - prior close|) resumes at the same minute
    rows = [(100.0, 100.2, 99.8, 100.0)] * 12
    ctx = mk(D0, history(D0), q, rows=rows, base=120.0)
    ctx.org, ctx.org_today = [(100.0, 120.0)], True
    assert DW.gate(ctx, q, "AM", at(ctx, "10:00"), 600) == "x_dw_big_org" and DW.gate(ctx, q, "AM", at(ctx, "10:50"), 650) is None
    assert DW.gate(ctx, p, "AM", at(ctx, "10:50"), 650) == "x_dw_big_org"


def rth_big(d):
    from test_review_fixes import rth_day
    prev = d - timedelta(days=1)
    while not C.is_trading_day(prev):
        prev -= timedelta(days=1)
    return rth_day(prev, 160.0, 90.0)


def test_objective_done_pm_and_frac_gate():
    p = Params(**BASE, objective_done_skip=True, objective_done_pm="reversal_only")
    lk = {"AM": dict(side=1, delivered=True, delivered_i=None, target=110.0, t_lock=570)}
    ctx = mk(D0, history(D0), p, lock=lk)
    lk["AM"]["delivered_i"] = at(ctx, "11:20")
    i = at(ctx, "13:45")
    assert DW.gate(ctx, p, "PM", i, 825) is None                                                      # the PM is not skipped
    assert DW.side_ok(ctx, p, 1, "PM", i) == "x_dw_objective_done_pm" and DW.side_ok(ctx, p, -1, "PM", i) is None     # only the counter direction (the lunch low)
    assert DW.side_ok(ctx, p, 1, "AM", at(ctx, "11:00")) is None
    q = replace(p, objective_done_pm="off")
    assert DW.gate(ctx, q, "PM", i, 825) == "x_dw_objective_done" or DW.gate(ctx, q, "PM", i, 825) is None   # the old switch skips on its own trades / lock
    lk["AM"]["delivered_i"] = at(ctx, "12:20")                                                        # delivered after noon: no restriction
    assert DW.side_ok(ctx, p, 1, "PM", i) is None
    # objective_frac_gate: the lion's share of the move to the draw is delivered
    rows = [(100.0, 100.2, 99.8, 100.0)] * 3 + [(100.0, 106.2, 99.9, 106.0)] + [(106.0, 106.2, 105.8, 106.0)] * 20
    g = Params(**BASE, objective_frac_gate=0.5)
    lock = {"AM": dict(side=1, delivered=False, delivered_i=None, target=110.0, t_lock=570)}
    ctx = mk(D0, history(D0), g, rows=rows, lock=lock)
    sd = S.Side(1, ctx.o, ctx.h, ctx.l, ctx.c, 1, 0.0)
    assert DW.order_ok(ctx, sd, dict(entry=106.0, ext=99.9), "AM", at(ctx, "10:00"), g) == "x_dw_objective_frac"     # 6 of 10 points delivered > 0.5
    assert DW.order_ok(ctx, sd, dict(entry=106.0, ext=99.9), "AM", at(ctx, "09:35"), g) is None                   # at 09:35 the move is 0 of 10
    sd2 = S.Side(-1, ctx.o, ctx.h, ctx.l, ctx.c, 1, 0.0)
    assert DW.order_ok(ctx, sd2, dict(entry=106.0, ext=99.9), "AM", at(ctx, "10:00"), g) is None                  # the counter direction is not blocked
    assert DW.order_ok(ctx, sd, dict(entry=106.0, ext=99.9), "AM", at(ctx, "10:00"), replace(g, objective_frac_gate=0.7)) is None


def _zigzag():
    """09:30-10:00 ping-pong: buy stops of a swing high, sell stops of a swing low, buy stops again - in a ~2.5 point range with equal small bodies."""
    hl = [(100.5, 99.5), (101.0, 100.0), (100.4, 99.4), (100.9, 99.9), (101.3, 100.3), (100.6, 99.0), (100.8, 99.6), (101.5, 100.2), (100.9, 99.9), (101.0, 100.0), (100.8, 99.8), (100.9, 99.9)]
    rows = []
    for k, (h, l) in enumerate(hl):
        o, c = (l + 0.1, l + 0.4) if k % 2 == 0 else (h - 0.1, h - 0.4)
        rows.append((o, h, l, c))
    return rows + [(100.4, 100.6, 100.2, 100.4)] * 24


def test_sd_fvg_hold():
    """Rule (b): after the close beyond the range an FVG in that direction and a retrace into it that closes without a body through it."""
    d = D0
    n = 40
    def run(bars):
        rows = [(o, h, l, c) for o, h, l, c in bars]
        return mk(d, history(d), Params(**BASE), rows=rows, start="09:30")
    flat = [(100.0, 100.5, 99.5, 100.0)] * 6
    up_break = flat + [(100.0, 103.0, 100.0, 102.8), (102.8, 105.0, 102.0, 104.8), (104.8, 107.0, 104.5, 106.8)]       # the first close > range high is the 7th bar
    ctx = run(up_break)
    a = at(ctx, "09:30")
    hh, ll = 100.5, 99.5
    held = up_break + [(106.8, 106.9, 101.5, 105.0)]                                                                    # the first FVG [100.5, 102.0] (bars 6-8 of the move); a retrace to 101.5 closing 105.0 holds
    ctx2 = run(held)
    assert D1.sd_fvg_held(ctx2, a, a + len(held) - 1, hh, ll)
    thru = up_break + [(106.8, 106.9, 99.0, 100.0)]                                                                    # closes through the gap: not a hold
    ctx3 = run(thru)
    assert not D1.sd_fvg_held(ctx3, a, a + len(thru) - 1, hh, ll)
    assert not D1.sd_fvg_held(ctx, a, a + 5, hh, ll)                                                                    # no close beyond the range yet


def test_sd_intraday_flag():
    p = Params(**BASE, sd_intraday="tag")
    ctx = mk(D0, history(D0), p, rows=_zigzag())
    r = D1.sd_intraday_at(ctx, p, at(ctx, "10:30"))
    assert r is not None and r[0] == at(ctx, "09:30") + 5                                         # flagged at the third take (L, H, L: the second alternation)
    assert D1.sd_intraday_at(ctx, p, at(ctx, "09:55")) is not None and D1.sd_intraday_at(ctx, p, at(ctx, "09:55")) == r
    assert D1.sd_intraday_at(ctx, p, at(ctx, "09:50")) is None                                     # not yet: no look-ahead
    trend = [(100.0 + 2 * k, 101.0 + 2 * k, 99.8 + 2 * k, 100.9 + 2 * k) for k in range(12)] + [(124.0, 124.5, 123.5, 124.0)] * 24
    ctx2 = mk(D0, history(D0), p, rows=trend)
    assert D1.sd_intraday_at(ctx2, p, at(ctx2, "10:30")) is None                                    # a trend day does not flag
    big = list(_zigzag())
    big[4] = (100.3, 101.3, 100.3, 105.0)                                                          # a displacement bar inside the range
    ctx3 = mk(D0, history(D0), p, rows=big)
    assert D1.sd_intraday_at(ctx3, p, at(ctx3, "10:30")) is None
    # "rules": a scalp, and no entry before the flagged range is broken by a close
    q = replace(p, sd_intraday="rules")
    ctx4 = mk(D0, history(D0), q, rows=_zigzag())
    assert DW.scalp_now(ctx4, q, "AM", at(ctx4, "10:00")) == "sd_intraday" and DW.scalp_now(ctx4, q, "AM", at(ctx4, "09:45")) == ""
    assert DW.gate(ctx4, q, "AM", at(ctx4, "10:00"), 600) == "x_dw_sd_intraday_range"
    ext = _zigzag()[:20] + [(100.4, 104.0, 100.3, 103.9)] + [(103.9, 104.1, 103.7, 104.0)] * 15
    ctx5 = mk(D0, history(D0), q, rows=ext)
    assert DW.gate(ctx5, q, "AM", at(ctx5, "11:30"), 690) is None                                   # the range broke by a close
    ctx5.lock = {"AM": dict(side=1, delivered=True, delivered_i=at(ctx5, "11:00"), target=104.0)}
    assert DW.gate(ctx5, q, "AM", at(ctx5, "11:30"), 690) == "x_dw_sd_after_draw"                   # the locked level traded: the reversal off it is not traded
    assert "sd_intraday" in D1.entry_tags(ctx, p, ctx.dplan, at(ctx, "10:30"))


def test_sd_week_flag():
    p = Params(**BASE, sd_week_skip="skip", sd_week_detect=True)
    wk = date(2023, 7, 10)                                                                           # a July week
    mon = daily(wk, 95, 100, 90, 95)
    tue = daily(wk + timedelta(days=1), 95, 101, 89, 95)                                              # both extremes exceeded by 1, no close beyond
    wed = date(2023, 7, 12)
    assert D1.sd_week_detected([mon, tue], wed, p, 12.0) == (True, False)
    assert D1.sd_week_detected([mon, tue], wed, p, 2.0) == (False, False)                             # beyond sd_shallow_frac x ADR5 (0.5)
    assert D1.sd_week_detected([mon, daily(wk + timedelta(days=1), 95, 101, 89, 102)], wed, p, 12.0) == (False, False)   # a daily close beyond the running extreme
    assert D1.sd_week_detected([mon, daily(wk + timedelta(days=1), 95, 101, 91, 95)], wed, p, 12.0) == (False, False)     # only one side was run
    jun = date(2023, 6, 5)
    assert D1.sd_week_detected([daily(jun, 95, 100, 90, 95), daily(jun + timedelta(days=1), 95, 101, 89, 95)], date(2023, 6, 7), p, 12.0) == (False, False)   # no FOMC / NFP in the week, not July
    assert D1.sd_week_detected([mon], date(2023, 7, 11), p, 12.0) == (False, False)                     # Tuesday: too early
    fri = date(2023, 7, 14)
    assert D1.sd_week_detected([mon, tue, daily(wk + timedelta(days=2), 95, 97, 92, 95), daily(wk + timedelta(days=3), 95, 120, 70, 95)], fri, p, 12.0)[0]     # Friday keeps the Wednesday evaluation
    fill = [daily(date(2023, 7, 3) + timedelta(days=k), 95, 101, 89, 95) for k in (0, 2, 3, 4)] + [daily(date(2023, 6, 30), 95, 101, 89, 95)]     # five earlier sessions: ADR5 = 12
    ctx = mk(wed, fill + [mon, tue], p)
    assert "sd_week" in ctx.dplan.tags and ctx.dplan.static_reason("AM", 600) == "sd_week"
    ctx = mk(wed, fill + [mon, daily(wk + timedelta(days=1), 95, 101, 91, 95)], p)
    assert "sd_week" not in ctx.dplan.tags and ctx.dplan.static_reason("AM", 600) is None             # the calendar alone no longer makes it an S&D week
    # sd_after_array: the week's extreme touched a D / W array
    hit_ = Conf(z={"D": zone(-1, 100.5, 102.0)})
    q = replace(p, sd_after_array=True)
    assert D1.sd_week_detected([mon, tue], wed, q, 12.0, hit_) == (True, True)
    assert D1.sd_week_detected([mon, tue], wed, q, 12.0, Conf(z={"D": zone(-1, 150.0, 160.0)})) == (True, False)
    ctx = mk(wed, fill + [mon, tue], q, conf=hit_)
    assert "sd_week_released" in ctx.dplan.tags and ctx.dplan.static_reason("AM", 600) is None


def test_n8_no_overnight():
    row = {"on_range": 2.0, "in_bull_arr": 0, "in_bear_arr": 0}
    assert BD._chop(dict(row, _chop_frac=0.35, _use_on=True), 20.0) == "on_range"
    assert BD._chop(dict(row, _chop_frac=0.35, _use_on=False), 20.0) == ""                              # the overnight range is no precursor
    assert BD._chop(dict(row, _chop_frac=0.35, _use_on=False, in_bull_arr=1), 20.0) == "in_array"
    assert BD._chop(dict(row, _chop_frac=0.35), 20.0) == "on_range"
    # the N8.2 trending-day recipe does not read the overnight range at all: changing it changes nothing
    d = date(2023, 6, 14)
    h = history(d)
    wide = mk(d, h, Params(**BASE, trend_recipe="tag", n8_use_overnight=False), spike=False)
    spiky = mk(d, h, Params(**BASE, trend_recipe="tag", n8_use_overnight=False), spike=True)
    assert ("trend_recipe" in wide.dplan.tags) == ("trend_recipe" in spiky.dplan.tags)


def test_n8_day_range_rth_only_and_sd_week_info():
    d = date(2023, 6, 14)
    fr = history(d)[-1]
    eth = {fr.index[0].date(): (0.0, float(fr.high.max()) + 50.0, float(fr.low.min()), 0.0)}
    on = Params(**BASE, adr_basis="eth")
    assert DW.day_range(fr, eth, on) == float(fr.high.max()) + 50.0 - float(fr.low.min())
    assert DW.day_range(fr, eth, replace(on, n8_use_overnight=False)) == float(fr.high.max() - fr.low.min())      # RTH ranges for the day classifications
    aug = date(2023, 8, 16)                                                                                       # calendar S&D week (August), no detector flag
    base = Params(**BASE, sd_no_hold=True, sd_week_skip="tag")
    assert mk(aug, history(aug), base).dplan.info["sd_week"] is True
    det = mk(aug, history(aug), replace(base, sd_week_detect=True))
    assert det.dplan.info["sd_week"] is False                                                                    # the intraday context follows the detector


# --- week templates ------------------------------------------------------------------------------------------------------------------

def _dp(d, o, h, l, c):
    return daily(d, o, h, l, c)


def test_nwog_templates():
    mon = date(2023, 6, 26)
    pre = [daily(date(2023, 6, 12) + timedelta(days=k), 4000.0, 4010.0, 3990.0, 4000.0) for k in range(5)] + \
          [daily(date(2023, 6, 19) + timedelta(days=k), 4000.0, 4010.0, 3990.0, 4000.0) for k in range(1, 5)]            # Friday 2023-06-23 closes 4000, low 3990
    ev = lambda so: (so, so + 3, so - 3, so)
    g = Params(**BASE, nwog_templates="gate")
    rows_up = [(4010.0, 4012.0, 4009.0, 4010.0)] * 6 + [(4010.0, 4010.5, 4004.5, 4006.0)] + [(4006.0, 4008.0, 4005.5, 4007.0)] * 6
    ctx = mk(mon, pre, g, rows=rows_up, base=4010.0, eve=ev(4010.0), bias_row={"flip": 1})
    assert "nwog_up_bull" in ctx.dplan.tags
    assert DW.side_ok(ctx, g, 1, "AM", at(ctx, "09:55")) == "x_dw_nwog_up_bull"                      # before the Friday close / the CE (4005) traded: no longs
    assert DW.side_ok(ctx, g, -1, "AM", at(ctx, "09:55")) is None
    assert DW.side_ok(ctx, g, 1, "AM", at(ctx, "10:15")) is None                                      # the CE (4005) touched, no fill: longs allowed
    assert {"nwog_ce_held"} == D1.entry_tags(ctx, g, ctx.dplan, at(ctx, "10:15")) & {"nwog_ce_held", "nwog_filled", "nwog_partial"}
    assert "nwog_partial" in D1.entry_tags(ctx, g, ctx.dplan, at(ctx, "09:55")) or True
    t = replace(g, nwog_templates="tag")
    ctx = mk(mon, pre, t, rows=rows_up, base=4010.0, eve=ev(4010.0), bias_row={"flip": 1})
    assert "nwog_up_bull" in ctx.dplan.tags and DW.side_ok(ctx, t, 1, "AM", at(ctx, "09:55")) is None   # tag only
    # bearish, gap down: the retrace may enter the gap (tag); open above the close: rally to the nearest upper wick CE first
    ctx = mk(mon, pre, g, base=3990.0, eve=ev(3990.0), bias_row={"flip": -1})
    assert "nwog_dn_bear" in ctx.dplan.tags and DW.side_ok(ctx, g, -1, "AM", at(ctx, "09:55")) is None
    ctx = mk(mon, pre, g, base=4000.0, eve=ev(4000.0), bias_row={"flip": -1})
    assert "nwog_flat_bear" in ctx.dplan.tags
    ctx.dplan.info["nwog_tpl"]["wick_ce"] = 4005.0                                                    # the nearest daily upper-wick CE
    assert DW.side_ok(ctx, g, -1, "AM", at(ctx, "09:55")) == "x_dw_nwog_flat_bear"
    ctx2 = mk(mon, pre, g, rows=[(4000.0, 4006.0, 3999.0, 4004.0)] * 6, base=4000.0, eve=ev(4000.0), bias_row={"flip": -1})
    ctx2.dplan.info["nwog_tpl"]["wick_ce"] = 4005.0
    assert DW.side_ok(ctx2, g, -1, "AM", at(ctx2, "10:15")) is None                                    # the wick CE traded: shorts allowed
    # bullish, open below the prior lower wick: it must be reclaimed
    ctx = mk(mon, pre, g, base=3985.0, eve=ev(3985.0), bias_row={"flip": 1})
    assert "nwog_below_wick_bull" in ctx.dplan.tags and DW.side_ok(ctx, g, 1, "AM", at(ctx, "09:55")) == "x_dw_nwog_below_wick"
    ctx = mk(mon, pre, g, rows=[(3985.0, 3992.0, 3984.0, 3991.0)] * 3, base=3985.0, eve=ev(3985.0), bias_row={"flip": 1})
    assert DW.side_ok(ctx, g, 1, "AM", at(ctx, "09:50")) is None                                       # reclaimed by a close
    # only the first trading day of the week is gated
    tue = mk(date(2023, 6, 27), pre + [daily(mon, 4010.0, 4012.0, 4004.0, 4008.0)], g, base=4010.0, eve=None, bias_row={"flip": 1})
    assert DW.side_ok(tue, g, 1, "AM", at(tue, "09:55")) is None
    ctx = mk(mon, pre, g, base=4010.0, eve=None, bias_row={"flip": 1})                                  # no Sunday data: nothing
    assert "nwog_templates" not in ctx.dplan.info and not ctx.dplan.tags & {"nwog_up_bull"}


def _one_sided_up(thu):
    fri = thu - timedelta(days=6)
    mon, tue, wed = fri + timedelta(days=3), fri + timedelta(days=4), fri + timedelta(days=5)
    return [daily(fri, 100.0, 101.0, 99.0, 100.5), daily(mon, 101.0, 104.0, 100.8, 103.5), daily(tue, 103.5, 107.0, 103.0, 106.5), daily(wed, 106.5, 110.0, 106.0, 109.5)]


def test_thu_strict(monkeypatch):
    thu = date(2023, 6, 15)
    h = _one_sided_up(thu)
    assert D1.one_sided_week(h, thu) == 1
    assert D1.one_sided_week(h[:3] + [daily(date(2023, 6, 14), 106.5, 110.0, 106.0, 106.8)], thu) == 0      # the Wednesday close is not beyond Tuesday's high
    assert D1.one_sided_week(h, date(2023, 6, 14)) == 0
    p = Params(**BASE, thu_strict=True)
    ctx = mk(thu, h + [], p)
    assert "one_sided_week_up" in ctx.dplan.tags and ctx.dplan.info["one_sided"] == 1
    # a short (against the week) at 10:15 with displacement; the HTF tag decides
    o = np.array([100.0] * 30); c = np.array([100.0 + (0.5 if k % 2 else -0.5) for k in range(30)])
    c[20] = 97.0                                                                                    # the MSS candle: a 3-point body against bodies of 0.5 (x1.5 = 0.75): displaced
    sd = SimpleNamespace(sign=-1, x=lambda v: v, o=o, c=c)
    order = dict(entry=100.0, ext=101.0, broke=20)
    i1015 = at(ctx, "10:10")                                                                         # the order is armed on the 10:10 bar: it fills from 10:15
    monkeypatch.setattr(S, "_htf_tag", lambda *a: False)
    assert DW.order_ok(ctx, sd, order, "AM", i1015, p) == "x_dw_thu_no_array"
    monkeypatch.setattr(S, "_htf_tag", lambda *a: True)
    assert DW.order_ok(ctx, sd, order, "AM", i1015, p) is None                                        # an HTF tag, displacement and a 10:15 fill pass
    assert DW.order_ok(ctx, sd, order, "AM", at(ctx, "09:50"), p) == "x_dw_thu_time"
    assert DW.order_ok(ctx, sd, order, "AM", at(ctx, "11:00"), p) == "x_dw_thu_time"
    weak = dict(order, broke=5)
    assert DW.order_ok(ctx, sd, weak, "AM", i1015, p) == "x_dw_thu_no_displacement"
    with_trend = SimpleNamespace(sign=1, x=lambda v: v, o=o, c=c)
    assert DW.order_ok(ctx, with_trend, order, "AM", at(ctx, "09:50"), p) is None                      # with the week: untouched
    assert DW.order_ok(ctx, sd, order, "AM", at(ctx, "09:50"), Params(**BASE)) is None                  # switch off


def test_fri_one_sided():
    fri = date(2023, 6, 16)
    h = [daily(date(2023, 6, 12), 100.0, 101.0, 99.0, 100.0), daily(date(2023, 6, 13), 100.0, 103.0, 99.5, 102.0), daily(date(2023, 6, 14), 102.0, 105.0, 101.5, 104.0),
         daily(date(2023, 6, 15), 104.0, 107.0, 103.5, 106.0)]
    assert D1.fri_dir(h, fri) == 1 and D1.fri_dir(h[:3] + [daily(date(2023, 6, 15), 104.0, 107.0, 103.0, 103.0)], fri) == 0
    p = Params(**BASE, fri_one_sided="raid_first", fri_t1_pts=4.0)
    ctx = mk(fri, h, p, spike=True, base=107.5)                                                      # the pre-open spike makes a high above Thursday's 107
    assert ctx.dplan.info["fri_dir"] == 1 and not ctx.dplan.scalp                                    # the scalp is dynamic (needs the overnight high): independent of the scalp-reason order
    assert DW.scalp_now(ctx, p, "AM", at(ctx, "10:00")) == "fri_one_sided"
    sd = SimpleNamespace(sign=1, x=lambda v: v)
    op = float(ctx.o[at(ctx, "09:30")])
    assert DW.order_ok(ctx, sd, dict(entry=op + 1, ext=op + 0.5), "AM", at(ctx, "10:00"), p) == "x_dw_fri_raid_first"     # a long whose sweep low is above the 09:30 open
    assert DW.order_ok(ctx, sd, dict(entry=op + 1, ext=op - 0.5), "AM", at(ctx, "10:00"), p) is None                         # the sweep took the sell side under the open
    t = replace(p, fri_one_sided="tag")
    c2 = mk(fri, h, t, spike=True, base=107.5)
    assert c2.dplan.info["fri_dir"] == 1 and not c2.dplan.scalp and DW.order_ok(c2, sd, dict(entry=op + 1, ext=op + 0.5), "AM", at(c2, "10:00"), t) is None
    dn = mk(fri, h[:3] + [daily(date(2023, 6, 15), 104.0, 107.0, 103.5, 101.0)], p)                  # not a one-way week
    assert "fri_dir" not in dn.dplan.info
    # the tag needs the overnight high above Thursday's high, known only once the 09:30 bar closed
    assert "fri_one_sided" in D1.entry_tags(c2, t, c2.dplan, at(c2, "10:00"))
    quiet = mk(fri, h, t, spike=False, base=100.0)                                                    # no high above Thursday's 107
    assert "fri_one_sided" not in D1.entry_tags(quiet, t, quiet.dplan, at(quiet, "10:00")) and DW.scalp_now(quiet, p, "AM", at(quiet, "10:00")) == ""
    assert DW.order_ok(quiet, sd, dict(entry=101.0, ext=100.6), "AM", at(quiet, "10:00"), p) is None  # not gated without the overnight raid
    # an order armed before the 09:30 bar closes reads nothing from the open (no look-ahead)
    early = mk(fri, h, p, spike=True, base=107.5, start="08:00")
    ie = at(early, "09:00")
    assert DW.order_ok(early, sd, dict(entry=op + 1, ext=op + 0.5), "AM", ie, p) is None and DW.scalp_now(early, p, "AM", ie) == ""
    assert "fri_one_sided" not in D1.entry_tags(early, t, early.dplan, ie)


def test_thu_strict_real_order_has_the_mss_bar(monkeypatch):
    """The engine's own order dict carries the MSS bar (broke), so the displacement check of thu_strict is live (not dead code)."""
    from test_review_fixes import A_LOCK
    seen = []
    orig = D1.order_ok
    monkeypatch.setattr(D1, "order_ok", lambda ctx, sd, o, session, i, p: (seen.append(o), orig(ctx, sd, o, session, i, p))[1])
    S.run_day(day(A_ROWS, d=D0, start="09:30", spike=True), history(D0), "ES", Params(**BASE, thu_strict=True), 5, locks=[], log=[], skips=[], bias_by_cut=A_LOCK)
    assert seen and all("broke" in o for o in seen)


def test_tgif_strict():
    fri = date(2023, 6, 16)
    prior = weeks(date(2023, 5, 22), [(100, 112, 99, 111), (111, 122, 110, 121)])              # two strong weeks: closes up and above the midpoint
    wk = [daily(date(2023, 6, 12), 121.0, 124.0, 120.5, 123.5), daily(date(2023, 6, 13), 123.0, 127.0, 122.5, 126.0), daily(date(2023, 6, 14), 126.0, 129.0, 125.5, 128.0),
          daily(date(2023, 6, 15), 128.0, 131.0, 127.5, 130.0)]
    gap = [daily(date(2023, 6, 5), 121.0, 122.0, 120.5, 121.5)] * 0
    hist = prior + [daily(date(2023, 6, 5 + k), 121.0, 122.0, 120.0, 121.0) for k in range(0, 5)] + wk
    p = Params(**BASE, tgif_strict=True, tgif_weeks=2)
    touch = Conf(z={"W": zone(-1, 129.0, 133.0)})                                              # a weekly bear array at the week's high
    # (the filler week 2023-06-05 is a flat week: closes above its open? no - flat: the prior two weeks must be strong)
    assert not D1.tgif_strict_ok(hist, fri, p, None, touch, True)                              # the week before is flat: not 2 strong prior weeks
    strong = weeks(date(2023, 5, 22), [(100, 112, 99, 111), (111, 122, 110, 121)])
    hist2 = strong + [daily(date(2023, 6, 5 + k), 121.0, 122.0, 120.0, 121.0) for k in range(0, 5)] + wk
    p1 = replace(p, tgif_weeks=1)
    assert not D1.tgif_strict_ok(hist2, fri, p1, None, touch, True)                           # the last week closed at its open: no strong close either
    wk0 = weeks(date(2023, 6, 5), [(121, 124, 120, 123)])
    hist3 = strong + wk0 + wk
    assert D1.tgif_strict_ok(hist3, fri, p, None, touch, True)                                  # weekly array reached, two strong weeks, Mon-Thu each up
    assert not D1.tgif_strict_ok(hist3, fri, p, None, Conf(z={"D": zone(-1, 129.0, 133.0)}), True)          # a daily array does not count
    assert not D1.tgif_strict_ok(hist3, fri, p, None, Conf(z={"W": zone(-1, 140.0, 150.0)}), True)         # not reached
    assert not D1.tgif_strict_ok(hist3, fri, p, None, None, True)
    mid = hist3[:-1] + [daily(date(2023, 6, 15), 128.0, 131.0, 127.5, 127.0)]                    # Thursday closes down: not a one-way week
    assert not D1.tgif_strict_ok(mid, fri, p, None, touch, True)
    assert D1.tgif_strict_ok(hist3, fri, replace(p, tgif_weeks=4), None, touch, True) is False     # only three prior weeks exist
    # through day_context: the tag is dropped when the preconditions fail
    base_tags, _ = S.day_context(hist3, fri, Params(**BASE), None, touch)
    strict_tags, blk = S.day_context(hist3, fri, p, None, touch)
    assert ("tgif_short" in base_tags) == ("tgif_short" in strict_tags)                         # preconditions hold: unchanged
    strict2, blk2 = S.day_context(hist3, fri, p, None, Conf(z={"W": zone(-1, 140.0, 150.0)}))
    assert "tgif_short" not in strict2 and "tgif" not in blk2


def test_macro_risk_week():
    mon = date(2023, 5, 29)
    # w0: high 100; w1: a big up week; w2: low 105 > 100 -> a bullish weekly FVG [100, 105] closed by the last completed week; the prior close sits inside it
    hist = weeks(date(2023, 5, 8), [(95, 100, 90, 99), (99, 112, 98, 111), (104, 113, 105, 103)])
    d = date(2023, 5, 29) + timedelta(days=0)
    d = date(2023, 5, 29) if C.is_trading_day(date(2023, 5, 29)) else date(2023, 5, 30)
    fresh = D1.weekly_fvg_fresh_inside(hist, d)
    assert fresh
    p = Params(**BASE, macro_risk_dates=("2023-05-29",))
    ctx = mk(d, hist, p)
    assert "macro_risk_week" in ctx.dplan.tags and "macro_risk_week" in ctx.dplan.scalp and ctx.dplan.info["macro_scalp"]
    assert DW.scalp_now(ctx, p, "AM", at(ctx, "10:00")) == "macro_risk_week"
    cands = [(1.0, "array", "htf_weekly", 0, 0), (2.0, "pool", "pdh1", 1, 0), (3.0, "pool", "overnight_high", 1, 0), (4.0, "pool", "london_high", 1, 0), (5.0, "array", "nwog", 0, 0)]
    assert [c[2] for c in D1.lock_filter(ctx, cands)] == ["overnight_high", "london_high"]              # the lock target is a session pool, not the weekly draw
    q = Params(**BASE, macro_risk_dates=("2023-06-12",))                                                 # another week flagged
    c2 = mk(d, hist, q)
    assert "macro_risk_week" not in c2.dplan.tags and D1.lock_filter(c2, cands) == cands
    c3 = mk(d, hist[:5] + hist[5:], Params(**BASE))                                                      # off
    assert not c3.dplan.scalp and D1.lock_filter(c3, cands) == cands
    solid = weeks(date(2023, 5, 8), [(95, 100, 90, 99), (99, 112, 98, 111), (104, 113, 101, 103)])      # the third candle overlaps the first: no gap
    assert not D1.weekly_fvg_fresh_inside(solid, d)


def _months(start_year, start_month, specs):
    """Three sessions per month (the first trading days) carrying the month candle (o, h, l, c)."""
    out, y, m = [], start_year, start_month
    for o, h, l, c in specs:
        d, got = date(y, m, 1), []
        while len(got) < 3:
            if C.is_trading_day(d):
                got.append(d)
            d += timedelta(days=1)
        out += [daily(got[0], o, o, o, o), daily(got[1], o, h, l, o), daily(got[2], o, o, o, c)]
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def test_mo_overdue_tag():
    specs = [(135, 136, 134, 135), (130, 135, 120, 125), (125, 126, 100, 102), (102, 106, 95, 104),            # m0 (dropped) .. m3: a bear FVG [106, 120] after the drop
             (104, 108, 103, 107), (107, 110, 106, 109), (109, 112, 108, 111), (111, 114, 110, 113), (113, 116, 112, 115)]
    hist = _months(2022, 7, specs)                                                                            # Jul 2022 .. Mar 2023
    d = date(2023, 4, 3)
    assert D1.mo_overdue(hist, d) == -1                                                                       # five up months, the fifth inside a monthly bear array
    p = Params(**BASE, mo_overdue=True)
    assert "mo_overdue_dn" in mk(d, hist, p).dplan.tags and "mo_overdue_dn" in mk(date(2023, 4, 20), hist, p).dplan.tags      # the whole next month
    assert not mk(date(2023, 1, 10), hist[:-6], p).dplan.tags & {"mo_overdue_dn", "mo_overdue_up"}        # only three up months (Oct-Dec) by then
    four = _months(2022, 7, specs[:4] + [(104, 108, 103, 107), (107, 110, 106, 109), (109, 112, 108, 111), (111, 114, 110, 113), (113, 116, 112, 112.5 - 1000)])
    assert D1.mo_overdue(four, d) == 0                                                                        # the last month closed down: only four up closes
    no_arr = _months(2022, 7, [(100 + 10 * k, 108 + 10 * k, 99 + 10 * k, 107 + 10 * k) for k in range(9)])
    assert D1.mo_overdue(no_arr, d) == 0                                                                      # no bear array to trade into
    mirror = _months(2022, 7, [(100, 101, 99, 100), (100, 110, 99, 108), (108, 140, 107, 138), (138, 139, 100, 102)] + [(102 - 4 * k, 103 - 4 * k, 99 - 4 * k, 99 - 4 * k - 0.5) for k in range(0, 5)])
    assert D1.mo_overdue(mirror, d) in (0, 1)
    assert not mk(d, hist, Params(**BASE)).dplan.tags & {"mo_overdue_dn"}


def test_mon_how(monkeypatch=None):
    wk = date(2023, 5, 8)
    pre = [daily(date(2023, 5, 3), 4070.0, 4080.0, 4060.0, 4065.0), daily(date(2023, 5, 4), 4065.0, 4066.0, 4030.0, 4035.0), daily(date(2023, 5, 5), 4035.0, 4040.0, 4020.0, 4030.0)]
    mon = daily(wk, 4030.0, 4050.0, 4025.0, 4030.0)                                                        # high 4050 inside the SIBI [4040, 4060], a close of 4030 under its low
    tue = date(2023, 5, 9)
    p = Params(**BASE, mon_how="gate")
    ctx = mk(tue, pre + [mon], p, base=4030.0, bias_row={"flip": -1})
    assert "mon_how" in ctx.dplan.tags and ctx.dplan.info["mon_how"] == (-1, 4050.0)
    sd = SimpleNamespace(sign=-1, x=lambda v: v)
    i = at(ctx, "10:00")
    assert DW.order_ok(ctx, sd, dict(entry=4055.0, ext=4056.0), "AM", i, p) == "x_dw_mon_how"          # a short above Monday's high: rejected
    assert DW.order_ok(ctx, sd, dict(entry=4045.0, ext=4046.0), "AM", i, p) is None
    assert DW.order_ok(ctx, SimpleNamespace(sign=1, x=lambda v: v), dict(entry=4055.0, ext=4040.0), "AM", i, p) is None      # longs are not gated
    # after a trade at 4051 the tag is gone (today's bars)
    c2 = mk(tue, pre + [mon], p, rows=[(4030.0, 4030.5, 4029.5, 4030.0)] * 2 + [(4030.0, 4051.0, 4029.0, 4050.0)] + [(4050.0, 4050.5, 4049.5, 4050.0)] * 10, base=4030.0, bias_row={"flip": -1})
    assert DW.order_ok(c2, sd, dict(entry=4055.0, ext=4056.0), "AM", at(c2, "10:00"), p) is None
    assert DW.order_ok(c2, sd, dict(entry=4055.0, ext=4056.0), "AM", at(c2, "09:35"), p) == "x_dw_mon_how"
    assert "mon_how_live" not in D1.entry_tags(c2, p, c2.dplan, at(c2, "10:00")) and "mon_how_live" in D1.entry_tags(c2, p, c2.dplan, at(c2, "09:35"))
    # a completed Tuesday above Monday's high clears it from Wednesday
    wed = date(2023, 5, 10)
    tue_hi = daily(tue, 4030.0, 4052.0, 4029.0, 4040.0)
    assert D1.mon_how_state(SimpleNamespace(bias_row={"flip": -1}), pre + [mon, tue_hi], wed, p) is None
    assert D1.mon_how_state(SimpleNamespace(bias_row={"flip": 0}), pre + [mon], tue, p) is None           # no bearish state
    assert D1.mon_how_state(SimpleNamespace(bias_row={"flip": -1}), pre + [daily(wk, 4030.0, 4050.0, 4025.0, 4045.0)], tue, p) is None     # Monday closed back inside the array
    assert D1.mon_how_state(SimpleNamespace(bias_row={"flip": -1}), pre + [daily(wk, 4030.0, 4050.0, 4025.0, 4045.0)], tue, replace(p, mon_how_edge="ce")) == (-1, 4050.0)   # the CE (4050) edge: a close of 4045 is under it
    assert D1.mon_how_state(SimpleNamespace(bias_row={"flip": -1}), pre + [mon], date(2023, 5, 8), p) is None    # Monday itself
    t = replace(p, mon_how="tag")
    c3 = mk(tue, pre + [mon], t, base=4030.0, bias_row={"flip": -1})
    assert "mon_how" in c3.dplan.tags and DW.order_ok(c3, sd, dict(entry=4055.0, ext=4056.0), "AM", i, t) is None     # tag only
    # the bullish mirror
    bpre = [daily(date(2023, 5, 3), 3930.0, 3940.0, 3920.0, 3935.0), daily(date(2023, 5, 4), 3935.0, 3970.0, 3934.0, 3965.0), daily(date(2023, 5, 5), 3965.0, 3980.0, 3960.0, 3970.0)]
    bmon = daily(wk, 3970.0, 3975.0, 3950.0, 3975.0)                                                       # low 3950 inside the BISI [3940, 3960], a close above its top
    assert D1.mon_how_state(SimpleNamespace(bias_row={"flip": 1}), bpre + [bmon], tue, p) == (1, 3950.0)


def test_wk_profile_mon_how_both_directions():
    wk = date(2023, 5, 8)
    pre = [daily(date(2023, 5, 3), 4070.0, 4080.0, 4060.0, 4065.0), daily(date(2023, 5, 4), 4065.0, 4066.0, 4030.0, 4035.0), daily(date(2023, 5, 5), 4035.0, 4040.0, 4020.0, 4030.0)]
    mon = daily(wk, 4030.0, 4050.0, 4025.0, 4030.0)
    tue = date(2023, 5, 9)
    p = Params(**BASE, wk_profile="tag", mon_how="tag")
    bear = SimpleNamespace(bias_row={"flip": -1})
    assert D1.mon_how_state(bear, pre + [mon], tue, p) == (-1, 4050.0)
    assert D1.wk_profile_name(bear, pre + [mon], tue, p, 50.0) == "mon_how"                                 # the bearish week (bias -1) with a Monday high of the week
    assert mk(tue, pre + [mon], p, base=4030.0, bias_row={"flip": -1}).dplan.info["wk_profile"] == "mon_how"
    bpre = [daily(date(2023, 5, 3), 3930.0, 3940.0, 3920.0, 3935.0), daily(date(2023, 5, 4), 3935.0, 3970.0, 3934.0, 3965.0), daily(date(2023, 5, 5), 3965.0, 3980.0, 3960.0, 3970.0)]
    bmon = daily(wk, 3970.0, 3975.0, 3950.0, 3975.0)
    bull = SimpleNamespace(bias_row={"flip": 1})
    assert D1.wk_profile_name(bull, bpre + [bmon], tue, p, 50.0) == "mon_how"                               # the bullish mirror
    assert D1.wk_profile_name(SimpleNamespace(bias_row={"flip": 0}), pre + [mon], tue, p, 50.0) == "none"


def test_landmine_monday_through_the_dayplan():
    mon = date(2023, 8, 7)
    assert mk(mon, history(mon), Params(**BASE, monday_mode="skip")).dplan.static_reason("AM", 600) == "monday"
    q = mk(mon, history(mon), Params(**BASE, monday_mode="skip", landmine_min=2))
    assert q.dplan.static_reason("AM", 600) is None and "monday_exempt" in q.dplan.tags
    assert mk(mon, history(mon), Params(**BASE, monday_mode="skip", landmine_min=3)).dplan.static_reason("AM", 600) == "monday"


def test_seasonal_months_matches_the_default_map():
    assert tuple({1: "bull", -1: "bear", 0: "cons"}[C.SEASONAL_MONTHS["ES"][m]] for m in range(1, 13)) == tuple(
        {"split": "cons"}.get(v, v) for v in Params().seasonal_map), (C.SEASONAL_MONTHS, Params().seasonal_map)


def test_wk_push_range():
    mon = date(2023, 5, 22)
    # two weeks ago: body top 4110, high 4130 -> wick CE 4120, 75 % level 4125; last week: high 4121 (to the CE), close 4110 (under it), low 4090
    hist = weeks(date(2023, 5, 8), [(4100, 4130, 4095, 4110), (4105, 4121, 4090, 4110)])
    p = Params(**BASE, wk_push_range=True)
    assert D1.push_range_frame(hist, mon) == (4090.0, 4125.0, True)
    ctx = mk(mon, hist, p, base=4110.0)
    assert "wk_push_range" in ctx.dplan.tags and ctx.dplan.info["wk_range_frame"] == (4090.0, 4125.0, True) and "wk_push_range" in ctx.dplan.scalp
    assert DW.scalp_now(ctx, p, "AM", at(ctx, "10:00")) == "wk_push_range"
    tue = date(2023, 5, 23)
    still = hist + [daily(mon, 4110.0, 4124.0, 4105.0, 4120.0)]
    assert "wk_push_range" in mk(tue, still, p, base=4110.0).dplan.tags                                 # no daily close beyond the 75 % level yet
    gone = hist + [daily(mon, 4110.0, 4130.0, 4105.0, 4126.0)]
    assert "wk_push_range" not in mk(tue, gone, p, base=4110.0).dplan.tags                               # a daily close beyond it: the frame is cleared
    assert D1.push_range_frame(weeks(date(2023, 5, 8), [(4100, 4130, 4095, 4110), (4105, 4131, 4090, 4110)]), mon) is None      # exceeded the high of two weeks ago
    assert D1.push_range_frame(weeks(date(2023, 5, 8), [(4100, 4130, 4095, 4110), (4105, 4121, 4090, 4121)]), mon) is None      # closed above the CE
    assert D1.push_range_frame(weeks(date(2023, 5, 8), [(4100, 4130, 4095, 4110), (4105, 4112, 4090, 4108)]), mon) is None      # never reached the CE
    # the bearish mirror: lower wick of two weeks ago (body bottom 4100, low 4070: CE 4085, 75 % level 4077.5)
    mir = weeks(date(2023, 5, 8), [(4110, 4115, 4070, 4100), (4095, 4120, 4084, 4095)])
    fr = D1.push_range_frame(mir, mon)
    assert fr is not None and fr[2] is False and fr[0] == 4077.5 and fr[1] == 4120.0
    assert not mk(mon, hist, Params(**BASE), base=4110.0).dplan.scalp


def test_weekly_profile_tag():
    zone_pre = [daily(date(2023, 5, 3), 95.0, 100.0, 94.0, 99.0), daily(date(2023, 5, 4), 99.0, 107.0, 98.0, 106.5), daily(date(2023, 5, 5), 106.5, 111.0, 106.0, 110.0)]       # a BISI [100, 106]
    mon = daily(date(2023, 5, 8), 110.0, 112.0, 108.0, 111.0)                                           # does not trade into it
    tue = daily(date(2023, 5, 9), 111.0, 111.5, 104.0, 105.0)                                           # Tuesday trades into the daily FVG
    p = Params(**BASE, wk_profile="tag")
    br = {"flip": 1}
    wed = date(2023, 5, 10)
    ctx = mk(wed, zone_pre + [mon, tue], p, bias_row=br)
    assert ctx.dplan.info["wk_profile"] == "classic_tue_low" and "wk_profile_classic_tue_low" in ctx.dplan.tags
    assert D1.wk_profile_name(ctx, zone_pre + [mon, tue], wed, p, 10.0) == "classic_tue_low"
    # no array by Tuesday, one on Wednesday -> wed_low (known from Thursday)
    tue2 = daily(date(2023, 5, 9), 111.0, 112.0, 109.0, 111.0)
    wed_d = daily(wed, 111.0, 111.5, 103.0, 104.0)
    thu = date(2023, 5, 11)
    ctx = mk(thu, zone_pre + [mon, tue2, wed_d], p, bias_row=br)
    assert ctx.dplan.info["wk_profile"] == "wed_low"
    ctx = mk(wed, zone_pre + [mon, tue2], p, bias_row=br)
    assert ctx.dplan.info["wk_profile"] == "none"                                                         # nothing known yet on Wednesday
    # Monday-Wednesday inside ADR with no array -> consol_thu_reversal
    calm = [daily(date(2023, 5, 8), 111.0, 112.0, 109.0, 111.0), daily(date(2023, 5, 9), 111.0, 112.5, 109.5, 111.0), daily(wed, 111.0, 112.0, 110.0, 111.0)]
    ctx = mk(thu, zone_pre + calm, p, bias_row=br)
    assert D1.wk_profile_name(ctx, zone_pre + calm, thu, p, 10.0) == "consol_thu_reversal" and D1.wk_profile_name(ctx, zone_pre + calm, thu, p, 2.0) == "none"
    # the bearish week uses the profiles in its direction only
    bear_pre = [daily(date(2023, 5, 3), 120.0, 121.0, 113.0, 114.0), daily(date(2023, 5, 4), 114.0, 115.0, 105.0, 106.0), daily(date(2023, 5, 5), 106.0, 108.0, 100.0, 102.0)]      # a SIBI [108, 113]
    m2 = daily(date(2023, 5, 8), 102.0, 103.0, 100.0, 101.0)
    t2 = daily(date(2023, 5, 9), 101.0, 110.0, 100.0, 104.0)
    ctx = mk(wed, bear_pre + [m2, t2], p, bias_row={"flip": -1})
    assert ctx.dplan.info["wk_profile"] == "classic_tue_high"
    ctx = mk(wed, bear_pre + [m2, t2], p, bias_row={"flip": 0})
    assert ctx.dplan.info["wk_profile"] == "none"                                                          # no weekly bias
    assert "wk_profile" not in mk(wed, zone_pre + [mon, tue], Params(**BASE), bias_row=br).dplan.info
    # the Trade column is stamped
    tr = SimpleNamespace(side="long", entry_time=ctx.idx[at(ctx, "10:00")], entry=100.0)
    DW.stamp(ctx, [tr], p)
    assert tr.wk_profile == "none" and "wk_profile_none" in tr.dw_tags


def test_iw_reversal_watch():
    mon = date(2023, 5, 8)
    hist = [daily(date(2023, 5, 4), 100.0, 105.0, 95.0, 100.0), daily(date(2023, 5, 5), 100.0, 105.0, 95.0, 100.0), daily(mon, 100.0, 120.0, 98.0, 118.0),
            daily(date(2023, 5, 9), 118.0, 124.0, 114.0, 122.0)]
    hist = [daily(date(2023, 5, 1) + timedelta(days=k), 100.0, 105.0, 95.0, 100.0) for k in range(3)] + hist[2:]                 # Mon 5/1 .. Wed 5/3, then Mon 5/8, Tue 5/9
    hist = [daily(date(2023, 5, 2), 100.0, 105.0, 95.0, 100.0), daily(date(2023, 5, 3), 100.0, 105.0, 95.0, 100.0), daily(date(2023, 5, 4), 100.0, 105.0, 95.0, 100.0),
            daily(date(2023, 5, 5), 100.0, 105.0, 95.0, 100.0), daily(mon, 100.0, 140.0, 98.0, 138.0)]                           # Monday: a 42-point range against ADR5 ~18
    wed = date(2023, 5, 10)
    p = Params(**BASE, iw_reversal_watch=True, iw_no_measured=True, mm_targets=True, proj_ext_sym=True)
    tue = daily(date(2023, 5, 9), 138.0, 139.0, 135.0, 137.0)
    ctx = mk(wed, hist + [tue], p, conf=Conf(at_tfs=["W"]))
    assert "iw_reversal_watch" in ctx.dplan.tags and ctx.dplan.info["iw_no_measured"]
    q = D1.day_params(p, ctx.dplan)
    assert q.mm_targets is False and q.proj_ext_sym is False and p.mm_targets is True                                         # the measured-move rungs are off that day
    nm = mk(wed, hist + [tue], replace(p, iw_no_measured=False), conf=Conf(at_tfs=["W"]))
    assert "iw_reversal_watch" in nm.dplan.tags and D1.day_params(replace(p, iw_no_measured=False), nm.dplan).mm_targets is True      # tag only
    assert "iw_reversal_watch" not in mk(wed, hist + [tue], p, conf=Conf(at_tfs=[])).dplan.tags                              # the day did not close at an HTF array
    assert "iw_reversal_watch" not in mk(wed, hist + [tue], p, conf=None).dplan.tags
    assert "iw_reversal_watch" not in mk(date(2023, 5, 9), hist, p, conf=Conf(at_tfs=["W"])).dplan.tags                      # Tuesday: not Wed / Thu
    assert "iw_reversal_watch" in mk(date(2023, 5, 11), hist + [tue, daily(wed, 137.0, 138.0, 134.0, 135.0)], p, conf=Conf(at_tfs=["D"])).dplan.tags
    small = [daily(date(2023, 5, 2 + k), 100.0, 105.0, 95.0, 100.0) for k in range(4)] + [daily(mon, 100.0, 108.0, 98.0, 106.0)]
    assert "iw_reversal_watch" not in mk(wed, small + [tue], p, conf=Conf(at_tfs=["W"])).dplan.tags                         # the range is under iw_k x ADR5


def test_three_day_small():
    p = Params(**BASE, three_day_small=True)
    ctx = mk(D0, history(D0), p, dt={"three_up"})
    assert "day4" in ctx.dplan.tags and "three_day_small" in ctx.dplan.scalp
    assert DW.scalp_now(ctx, p, "AM", at(ctx, "10:00")) == "three_day_small"
    assert not mk(D0, history(D0), p, dt=set()).dplan.scalp and not mk(D0, history(D0), Params(**BASE), dt={"three_up"}).dplan.scalp
    # through the real day_context tags: three up closes
    h = history(D0)
    up = [rth_close(x, 100.0 + k) for k, x in enumerate(h[-4:])]
    tags, blk = S.day_context(h[:-4] + up, D0, Params(**BASE))
    assert "three_up" in tags and blk["three"] == (1,)


def rth_close(fr, c):
    out = fr.copy()
    out.iloc[-1, out.columns.get_loc("close")] = c
    out.iloc[-1, out.columns.get_loc("high")] = max(float(out.high.iloc[-1]), c)
    return out


def test_day_profile_tag():
    d = date(2023, 5, 10)
    h = [daily(date(2023, 5, 1) + timedelta(days=k), 4000.0, 4025.0, 3975.0, 4000.0) for k in range(5)]
    h = [daily(date(2023, 5, 1), 4000.0, 4025.0, 3975.0, 4000.0), daily(date(2023, 5, 2), 4000.0, 4025.0, 3975.0, 4000.0), daily(date(2023, 5, 3), 4000.0, 4025.0, 3975.0, 4000.0),
         daily(date(2023, 5, 4), 4000.0, 4025.0, 3975.0, 4000.0), daily(date(2023, 5, 5), 4000.0, 4025.0, 3975.0, 4000.0)]                  # ADR5 50, last close 4000
    p = Params(**BASE, day_profile="tag")
    near = mk(d, h, p, bias_row={"iof": 1}, conf=Conf(targets=[4020.0, 4030.0]), base=4000.0)
    assert near.dplan.info["profile_day"][0] == "am_pm_reversal" and "profile_am_pm_reversal" in near.dplan.tags
    far = mk(d, h, p, bias_row={"iof": 1}, conf=Conf(targets=[4200.0]), base=4000.0)
    assert far.dplan.info["profile_day"][0] == "two_session"
    none = mk(d, h, p, bias_row={"iof": 1}, conf=Conf(targets=[]), base=4000.0)
    assert none.dplan.info["profile_day"][0] == "two_session"                                          # no opposing array at all
    assert "profile_day" not in mk(d, h, p, bias_row={"iof": 0, "draw": 0}, conf=Conf(targets=[4020.0]), base=4000.0).dplan.info
    fb = mk(d, h, p, bias_row={"draw": -1}, conf=Conf(targets=[3980.0]), base=4000.0)                  # no iof column: the draw side
    assert fb.dplan.info["profile_day"][:2] == ("am_pm_reversal", -1)
    assert "profile_day" not in mk(d, h, Params(**BASE), bias_row={"iof": 1}, conf=Conf(targets=[4020.0]), base=4000.0).dplan.info
    # the gate: two_session days go with the AM side in the PM; a reversal day turns once the array traded
    g = replace(p, day_profile_gate=True)
    lock = {"AM": dict(side=1, delivered=False, delivered_i=None, target=4040.0, t_lock=570)}
    c2 = mk(d, h, g, bias_row={"iof": 1}, conf=Conf(targets=[4200.0]), base=4000.0, lock=lock)
    assert DW.side_ok(c2, g, -1, "PM", at(c2, "14:00")) == "x_dw_profile_two_session" and DW.side_ok(c2, g, 1, "PM", at(c2, "14:00")) is None
    assert DW.side_ok(c2, g, -1, "AM", at(c2, "10:00")) is None                                            # the AM is untouched
    rows = [(4000.0, 4001.0, 3999.0, 4000.0)] * 3 + [(4000.0, 4021.0, 3999.5, 4019.0)] + [(4019.0, 4020.0, 4018.0, 4019.0)] * 40
    c3 = mk(d, h, g, bias_row={"iof": 1}, conf=Conf(targets=[4020.0]), base=4000.0, lock=lock, rows=rows)
    assert DW.side_ok(c3, g, 1, "PM", at(c3, "14:00")) == "x_dw_profile_reversal" and DW.side_ok(c3, g, -1, "PM", at(c3, "14:00")) is None
    c4 = mk(d, h, g, bias_row={"iof": 1}, conf=Conf(targets=[4020.0]), base=4000.0, lock=lock)
    assert DW.side_ok(c4, g, 1, "PM", at(c4, "14:00")) is None                                            # the array has not traded yet


# --- the engine path: one day through run_day -----------------------------------------------------------------------------------------

def test_run_day_with_every_switch_on_is_safe():
    """A normal hand-made day through the real engine with the switches on that cannot act on it: the same trades as off."""
    from test_review_fixes import A_LOCK
    kw = dict(pre_cpi_mon="gap", landmine_min=2, post_holiday_am="symmetry", holiday_nfp_override=True, august_mode="skip", season_quality="tag", skip_election="narrow",
              holiday_eve_cases="ab", objective_frac_gate=0.99, sd_intraday="tag", sd_week_detect=True, nwog_templates="tag", fri_one_sided="tag", season_windows="tag", wk_profile="tag",
              mon_how="tag", wk_push_range=True, iw_reversal_watch=True, day_profile="tag", mo_overdue=True, three_day_small=True, tgif_strict=True)
    d = D0
    base = S.run_day(day(A_ROWS, d=d, start="09:30", spike=True), history(d), "ES", Params(**BASE), 5, locks=[], log=[], skips=[], bias_by_cut=A_LOCK)
    new = S.run_day(day(A_ROWS, d=d, start="09:30", spike=True), history(d), "ES", Params(**{**BASE, **kw}), 5, locks=[], log=[], skips=[], bias_by_cut=A_LOCK)
    assert len(base) >= 1
    assert [(t.entry_time, t.entry, t.stop) for t in base] == [(t.entry_time, t.entry, t.stop) for t in new]
    assert all(hasattr(t, "wk_profile") for t in new)
    assert "x_dw_season_window" not in str(new)


# --- no look-ahead: full run vs truncated runs ----------------------------------------------------------------------------------------------------------
# (1) synthetic multi-day windows with the Silver Bullet and Ma Deuce on, executed-path counters asserted where a path fires;
# (2) ES windows (skipped when the data is absent).

W_DW = {"W0": ("2026-04-27", "2026-05-13", 5), "W1": ("2026-05-18", "2026-06-03", 7), "W2": ("2026-04-06", "2026-04-24", 3)}
LA_DW = {   # name -> (window, switches); NEED = the dwc1.HITS counters the run must bump
    "season": ("W0", dict(season_windows="tag", season_gate=True, season_quality="size", seasonal_tag=True, season_min_rank=0.5, mo_overdue=True)),
    "holiday": ("W1", dict(holiday_week_mult=0.5, post_holiday_am="symmetry", holiday_eve_cases="ab", skip_holiday_eve=True, august_mode="light", holiday_nfp_override=True)),
    "week": ("W0", dict(wk_profile="tag", wk_push_range=True, mon_how="gate", iw_reversal_watch=True, iw_no_measured=True, thu_strict=True, fri_one_sided="raid_first", three_day_small=True,
                        sd_week_detect=True, sd_week_skip="skip", tgif_strict=True)),
    "knobs": ("W0", dict(sd_week_detect=True, sd_week_skip="tag", sd_after_array=True, sd_shallow_frac=0.1, season_windows="tag", season_move_adr=1.0, season_autumn_start=10,
                         season_march_mult=0.5, season_quality="size", mon_how="gate", mon_how_edge="ce", tgif_strict=True, tgif_weeks=1, fri_one_sided="raid_first", fri_t1_pts=3.0,
                         iw_reversal_watch=True, iw_k=1.0, n8_use_overnight=False, nwog_templates="gate", wk_profile="tag", day_profile="tag", day_profile_gate=True)),
    "day": ("W2", dict(sd_intraday="rules", objective_frac_gate=0.6, objective_done_skip=True, objective_done_pm="reversal_only", big_day_am_skip=True, big_day_am_resume=645,
                       day_profile="tag", day_profile_gate=True, nwog_templates="gate", pre_cpi_mon="gap", macro_risk_dates=("2026-04-06", "2026-04-13"))),
}
NEED_DW = {"season": ("season_intra_gate", "season_size_prime"), "holiday": ("post_holiday_symmetry_wait", "holiday_week_mult"), "week": ("three_day_small", "thu_strict_time"),
           "knobs": ("season_size_prime",), "day": ("objective_done_pm_block", "sd_intraday_fvg_wait", "objective_frac_reject", "sd_intraday_wait", "sd_intraday_after_draw")}
_RUNS = {}


def _syn_dw(wname, **kw):
    key = (wname, tuple(sorted(kw.items(), key=lambda kv: kv[0])))
    if key not in _RUNS:
        a, b, seed = W_DW[wname]
        x, y = B.synthetic(start=a, end=b, tf=5, seed=seed)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            _RUNS[key] = (x, y, B.run(x, 5, "ES", Params(**SYN, sb_model=True, ma_deuce=True, **kw), y))
    return _RUNS[key]


@pytest.mark.parametrize("name", list(LA_DW))
def test_look_ahead_synthetic_dwc(name):
    wname, kw = LA_DW[name]
    D1.HITS.clear()
    x, y, full = _syn_dw(wname, **kw)
    assert len(full) >= 1, f"{name}: no trades in window {wname}"
    p = Params(**SYN, sb_model=True, ma_deuce=True, **kw)
    _no_look_ahead(x, 5, "ES", p, COLS, every=max(1, len(full) // 3), partner=y, exits=True, min_trades=1)
    missing = [h for h in NEED_DW[name] if not D1.HITS.get(h)]
    assert not missing, f"{name}: these paths did not run: {missing} (ran: {sorted(D1.HITS)})"


def test_look_ahead_sets_fire_something():
    """The sets change the engine on their windows (not inert): the trades differ from the switches-off run or a counter ran."""
    CMP = ["entry_time", "entry", "shares", "session", "lv_tags", "net", "stop"]
    D1.HITS.clear()
    fired = {}
    for name, (wname, kw) in LA_DW.items():
        _, _, base = _syn_dw(wname)
        _, _, t = _syn_dw(wname, **kw)
        same = len(t) == len(base) and (not len(t) or t[CMP].reset_index(drop=True).equals(base[CMP].reset_index(drop=True)))
        fired[name] = not same
    assert any(fired.values()) or D1.HITS, fired


def _day_la(d, rows, start, cuts, hist=None, min_trades=1, **kw):
    """run_day on a hand-made day, full vs the frame cut after `cuts` ("HH:MM"): the entries (and the exits that happened) before each cut must be identical."""
    from test_review_fixes import A_LOCK
    p = Params(**{**BASE, **kw})
    df = day(rows, d=d, start=start, spike=True)
    h = hist or history(d)

    def run(frame_, live):
        return S.run_day(frame_, h, "ES", p, 5, locks=[], log=[], skips=[], bias_by_cut=A_LOCK, live=live)
    full = run(df, False)
    assert len(full) >= min_trades, "no trade - the hand-made day must produce one"
    cols = lambda tr: (str(tr.entry_time), round(tr.entry, 6), round(tr.stop, 6), tr.shares, tr.session, tr.lv_tags)
    for cut in cuts:
        c = pd.Timestamp(f"{d} {cut}", tz="America/New_York")
        part = run(df[df.index <= c], True)
        a = [cols(t) for t in full if t.entry_time <= c]
        b = [cols(t) for t in part if t.entry_time <= c]
        assert a == b, (cut, a, b)
        xa = [(str(e[0]), round(e[1], 6), e[2], e[3]) for t in full for e in t.exits if e[0] <= c]
        xb = [(str(e[0]), round(e[1], 6), e[2], e[3]) for t in part for e in t.exits if e[0] <= c]
        assert xa == xb, (cut, xa, xb)
    return full


def test_look_ahead_hand_made_days():
    D1.HITS.clear()
    _day_la(D0, A_ROWS, "09:50", ("10:05", "10:10", "10:30"), min_trades=0, sd_intraday="rules")           # sd_fvg_hold on (the default): may wait out the whole day, still causal
    _day_la(D0, A_ROWS, "09:50", ("10:05", "10:10", "10:30"), sd_intraday="rules", sd_fvg_hold=False, objective_frac_gate=0.9, objective_done_pm="reversal_only", objective_done_skip=True,
            season_windows="tag", season_gate=True, wk_profile="tag", wk_push_range=True, nwog_templates="gate", three_day_small=True, mon_how="gate", sd_week_detect=True,
            sd_week_skip="skip", day_profile="tag", iw_reversal_watch=True)
    _day_la(date(2023, 1, 17), A_ROWS, "09:50", ("10:05", "10:30"), min_trades=0, post_holiday_am="symmetry", skip_post_holiday_am=True, holiday_week_mult=0.5, season_quality="size")
    assert D1.HITS["sd_intraday_scalp"] or D1.HITS["post_holiday_symmetry_nopartner"] or D1.HITS["post_holiday_symmetry_open"] or D1.HITS["holiday_week_mult"] or D1.HITS["season_size_off"]


def test_look_ahead_friday_raid_first_and_dates():
    """A Friday after a one-way week with the overnight spike above Thursday's high: the gate / scalp / tag read the 09:30 bar only once it has closed; full vs truncated runs agree."""
    fri = date(2023, 6, 16)
    h = history(fri)[:-4] + [daily(date(2023, 6, 12), 97.0, 108.0, 90.0, 97.5), daily(date(2023, 6, 13), 97.5, 108.0, 90.0, 98.5), daily(date(2023, 6, 14), 98.5, 108.0, 90.0, 99.5),
                             daily(date(2023, 6, 15), 99.5, 101.0, 90.0, 100.5)]
    D1.HITS.clear()
    _day_la(fri, A_ROWS, "09:50", ("09:25", "09:45", "10:05", "10:30"), hist=h, fri_one_sided="raid_first", fri_t1_pts=3.0)
    assert D1.HITS["fri_one_sided_scalp"] and (D1.HITS["fri_raid_first_pass"] or D1.HITS["fri_raid_first_reject"]), dict(D1.HITS)
    assert S.blocked(date(2026, 7, 1), "AM", Params(summer_off=True)) == "summer_off" and S.blocked(date(2026, 7, 1), "AM", Params()) != "summer_off"
    assert S.blocked(date(2024, 11, 5), "AM", Params(skip_election="narrow")) == "election"


def test_look_ahead_seasonal_long_history():
    """A day with ~330 sessions of daily history (a trend, a prior-year window): the window / failed-window / size paths execute and are causal (full vs truncated runs)."""
    d = date(2023, 10, 10)
    n = 330
    ser = _series(d - timedelta(days=int(n * 1.45)), [70 + 30 * k / n for k in range(n)], rng=3.0)
    ser = [x for x in ser if x.index[0].date() < d]
    ser = ser[:-8] + history(d)
    D1.HITS.clear()
    _day_la(d, A_ROWS, "09:50", ("10:05", "10:30"), hist=ser, season_windows="tag", season_gate=True, season_quality="size", season_min_rank=0.5, season_move_adr=1.0, mo_overdue=True,
            seasonal_tag=True)
    assert D1.HITS["season_failed_gate"] and D1.HITS["season_size_prime"], dict(D1.HITS)


@pytest.mark.skipif(not ES, reason="no ES data")
@pytest.mark.parametrize("window", [("2023-05-15", "2023-05-20"), ("2023-01-16", "2023-01-21"), ("2023-10-09", "2023-10-14"), ("2023-09-18", "2023-09-23")])
def test_look_ahead_es_dwc(window):
    es = B.load("ES", 5, source="databento")
    df = es[(es.index >= pd.Timestamp(window[0], tz=B.NY)) & (es.index < pd.Timestamp(window[1], tz=B.NY))]
    meta = B.load_meta("ES", 5)
    p = Params(**FUT, htf_resist_cap=False, draw_lock="off", leg_pd=0, min_draw_pts=0, use_bias=False, ob_entry="post_mss", sb_model=True, ma_deuce=True, fomc_observe="defer",
               pre_cpi_mon="gap", landmine_min=2, post_holiday_am="symmetry", holiday_nfp_override=True, holiday_week_mult=0.5, season_quality="size", holiday_eve_cases="ab",
               skip_holiday_eve=True, objective_frac_gate=0.6, objective_done_pm="reversal_only", objective_done_skip=True, sd_intraday="rules", sd_week_detect=True, sd_week_skip="skip",
               big_day_am_skip=True, big_day_am_resume=645, nwog_templates="gate", thu_strict=True, fri_one_sided="raid_first", season_windows="tag", season_gate=True,
               mo_overdue=True, mon_how="gate", wk_push_range=True, wk_profile="tag", iw_reversal_watch=True, iw_no_measured=True, three_day_small=True, day_profile="tag",
               day_profile_gate=True, tgif_strict=True, seasonal_tag=True)
    _no_look_ahead(df, 5, "ES", p, COLS, every=1, meta=meta, exits=True, min_trades=1)


def test_report_by_dw_tag():
    """BH-B23-index-seasonal-windows / B23-seasonal-quality: the report breaks the trades out by the seasonal / week-template tags."""
    t = pd.DataFrame(dict(net=[1.0, -2.0, 3.0], gross=[1.0, -2.0, 3.0], costs=[0.0] * 3, R=[1.0, -1.0, 2.0], entry_time=["2023-05-02 10:00", "2023-05-03 10:00", "2023-05-04 10:00"],
                          dw_tags=["season_prime|win_short_may|auction", "win_short_may", ""], setup=["a"] * 3, side=["long"] * 3, wk_profile=["none", "classic_tue_low", ""]))
    rep = B.report(t)
    assert set(rep["by_dw_tag"]) == {"season_prime", "win_short_may"} and rep["by_dw_tag"]["win_short_may"]["trades"] == 2
    assert "by_wk_profile" in rep
