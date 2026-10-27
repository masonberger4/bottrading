"""Caption-gap pass, package bias_htf#1/7 (35 specs from digests/rulebook_gaps/bias_htf_intermarket.md): focused tests of the new switches - the daily / weekly columns and flip triggers (bh1.py) on hand-made
daily books, the engine hooks (bh1e.py) on the real DayCtx of hand-made days, and no-look-ahead runs (full vs truncated; ES windows skip without the data). Nothing here needs market data except the ES windows;
nothing is platform specific; no file outside the repo is written (the manual invalidation file is monkeypatched to a pytest tmp_path)."""
import warnings
from dataclasses import fields, replace
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from mentorship import backtest as B, bh1 as BH, bh1e as BE, bias_day as BD, bias_htf as BX, daycontext as DW, htf, levels as L, study, strategy as S
from mentorship.strategy import Params

from test_review_fixes import BASE, D0, A_ROWS, A_LOCK, day, frame, history  # noqa: E402  (shared scenario builders)
from test_entries_stops import _no_look_ahead  # noqa: E402
from test_day_week_context import daily  # noqa: E402
from test_caption_gap_dwc1 import mk, at, hm, COLS, SYN, FUT, ES, _day_la  # noqa: E402

NAN = float("nan")

NEW_FIELDS = (
    "drange_scalp", "drange_n", "drange_break", "drange_t1_pts", "drange_day_pts", "b7_mode", "wk_high_in_gate", "bisi60_draw", "neutral_lean", "lean_n", "lean_tol_pts", "wk_bisi_ce_neutral",
    "ceiling_ladder", "bpr_lean", "nwog_ref", "nwog_bias_basis", "raid_gap_guard", "inval_src", "bellwether_tf", "org_gap_filter", "org_tell_seq", "org_attempt_frac", "org_tell_skip_min",
    "org_tell_end", "org_consol_case", "dxy_filter", "dxy_soft_risk", "low_in_relock", "low_in_min_highs", "low_in_ratio", "fifty_rel", "iof_tf", "allow_counter_trend", "draw_order",
    "wick_ce_draw", "stack_far", "no_htf_top_pick", "min_criteria", "wk_po3", "run_extreme_lean", "pwh_giveback_draw", "giveback_frac", "htf_monthly", "bisi60_hold", "wk_dc_joint", "b9_persist")
KNOBS = {"drange_n", "drange_break", "drange_t1_pts", "drange_day_pts", "lean_n", "lean_tol_pts", "org_attempt_frac", "org_tell_skip_min", "org_tell_end", "dxy_soft_risk", "low_in_min_highs",
         "low_in_ratio", "giveback_frac", "nwog_ref", "nwog_bias_basis"}
OFF = {"drange_scalp": False, "b7_mode": "mt_close", "wk_high_in_gate": False, "bisi60_draw": False, "neutral_lean": False, "wk_bisi_ce_neutral": False, "ceiling_ladder": False, "bpr_lean": False,
       "raid_gap_guard": False, "inval_src": "off", "bellwether_tf": 0, "org_gap_filter": False, "org_tell_seq": False, "org_consol_case": False, "dxy_filter": "off", "low_in_relock": False,
       "fifty_rel": False, "iof_tf": 0, "allow_counter_trend": False, "draw_order": "nearest", "wick_ce_draw": False, "stack_far": False, "no_htf_top_pick": False, "min_criteria": False,
       "wk_po3": False, "run_extreme_lean": False, "pwh_giveback_draw": False, "htf_monthly": False, "bisi60_hold": "off", "wk_dc_joint": False, "b9_persist": False}


# --- hand-made daily books ----------------------------------------------------------------------------------------------

def dsess(ohlc, start=date(2026, 3, 2)):
    """A daily book (the shape of htf.sessions) of consecutive Monday-Friday sessions from `start` (a Monday)."""
    idx = pd.bdate_range(start, periods=len(ohlc))
    return pd.DataFrame([list(map(float, r)) for r in ohlc], columns=["open", "high", "low", "close"], index=idx)


def arr(kind, typ, top, bottom, known, tf="D", ce=None):
    return htf.Arr(kind, typ, tf, float(top), float(bottom), float((top + bottom) / 2 if ce is None else ce), int(known))


def flip_of(d, arrs, triggers, cfg=None):
    w = htf.weeks(d)
    fl = htf._flip(d, w, arrs, tuple(triggers), cfg)
    return [fl[t] for t in d.index]               # the state known BEFORE each session


# --- defaults and validation --------------------------------------------------------------------------------------------

def test_defaults_and_validation():
    p = Params()
    for f in NEW_FIELDS:
        assert f in Params.__dataclass_fields__, f
    for k, v in OFF.items():
        assert getattr(p, k) == v, k
    assert (p.drange_n, p.drange_break, p.drange_t1_pts, p.drange_day_pts, p.lean_n, p.lean_tol_pts) == (5, "close", 5.0, 10.0, 2, 5.0)
    assert (p.org_attempt_frac, p.org_tell_skip_min, p.org_tell_end, p.dxy_soft_risk, p.low_in_min_highs, p.low_in_ratio, p.giveback_frac) == (0.25, 3, 600, 0.5, 3, 2.0, 0.5)
    assert p.nwog_ref == "current" and p.nwog_bias_basis == "px" and p.nwog_bias_reclaim == "low"          # the built edge default stays (owner question: the spec says 'high')
    assert p.bx == "" and not BE.on(p)
    # the owner-fixed switches are untouched by this chunk
    assert p.sb_model is False and "sb_use_bias" in Params.__dataclass_fields__ and p.want_all_engines is True
    for bad in (dict(drange_break="x"), dict(b7_mode="x"), dict(nwog_ref="x"), dict(nwog_bias_basis="x"), dict(inval_src="x"), dict(dxy_filter="x"), dict(draw_order="x"), dict(bisi60_hold="x"),
                dict(bellwether_tf=30), dict(iof_tf=7), dict(drange_n=2), dict(drange_t1_pts=0), dict(lean_n=0), dict(org_attempt_frac=0), dict(org_tell_end=900), dict(dxy_soft_risk=0),
                dict(low_in_min_highs=0), dict(low_in_ratio=0), dict(giveback_frac=1.0), dict(flip_triggers=("x",))):
        with pytest.raises(ValueError):
            Params(**bad)
    q = Params(htf_monthly=True)
    assert q.htf_monthly_arrays is True                               # BH-A5-HTF-FVG-own-timeframe: the named alias of the built monthly arrays
    Params(flip_triggers=("ob_mt", "wk_dc", "wk_bisi", "inv3", "ob_low_touch", "wk_rb", "d_breaker"), dxy_filter="soft", draw_order="nearest_tb", bellwether_tf=15, iof_tf=60)


def test_every_new_switch_has_a_study_variant():
    used = set()
    for v in study._BH1_DECISIONS.values():
        used |= set(v)
    for f in NEW_FIELDS:
        assert f in used or f in KNOBS, f
    for k, v in study._BH1_DECISIONS.items():
        assert k in study.DECISIONS
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            replace(Params(), **v)
    for gid in ("BH-B17-daily-range-scalp-regime", "BH-B7-last-daily-OB-guard", "BH-A8-60m-BISI-loss-draw", "BH-B17-neutral-lean", "BH-weekly-BISI-CE-and-full-close", "BH-B8-draw-flip-via-inversion",
                "BH-B1-imbalance-ceiling-ladder", "BH-A11-BPR-lean", "BH-B14-NWOG-flip-edge", "BH-B14-protective-gap-and-low", "BH-B8-pre-stated-invalidation-price", "BH-B9-HTF-OB-low-trade-through",
                "BH-B5-bellwether", "BH-B15-gap-down-ORG-no-shorts", "BH-B15-ORG-tell-details", "BH-B15-ORG-consolidation-case", "BH-B19-DXY-soft-filter-for-indices", "BH-failed-sweeps-low-in",
                "BH-B17-REL-REH-both-intact", "BH-B6-intraday-iof", "BH-B3-counter-bias-modes", "BH-B2-draw-by-proximity", "BH-B2-wick-CE-draw", "BH-B2-two-HTF-FVGs-farther", "BH-no-HTF-top-picking",
                "BH-B4-HTF-bias-minimum-criteria", "BH-B13-weekly-PO3", "BH-consolidation-takes-run-high", "BH-PWH-run-giveback-weekly-gap", "BH-A5-HTF-FVG-own-timeframe",
                "BH-weekly-rejection-block-range-proof", "BH-B8-1h-BISI-CE-hold", "BH-B8-daily-breaker-bias", "B8-weekly-ith-both-indices-close", "B9-retrace-above-swing-low"):
        assert any(k.startswith(gid) for k in study.DECISIONS), gid


def test_table_configuration_names_what_the_switches_need():
    import json
    x = json.loads(Params(drange_scalp=True, neutral_lean=True, wk_po3=True, b9_persist=True, wick_ce_draw=True, flip_triggers=("ob_mt", "ob_low_touch")).bx)
    assert set(x["b1"]) >= {"dr", "lean", "wpo3", "fl", "wick"} and x["b1"]["fl"] == {"persist": 1} and x["obj"] == 1 and x["ord"] == 1
    y = json.loads(Params(nwog_bias="tag", nwog_ref="previous", nwog_bias_basis="close").bx)
    assert y["nwog"][5:] == ["previous", "close"]
    assert json.loads(Params(nwog_bias="tag").bx)["nwog"][5:] == []                 # the default configuration is unchanged


# --- item 1: the daily consolidation regime ---------------------------------------------------------------------------------

def test_drange_scalp_regime():
    # sessions 0-4 close inside session 0's 4000-4040; session 5 closes at 4045 (a close beyond), session 6 a wick only
    h = np.array([4040, 4030, 4035, 4032, 4038, 4046, 4050], float)
    l = np.array([4000, 4010, 4005, 4012, 4008, 4030, 4040], float)
    c = np.array([4020, 4025, 4015, 4030, 4020, 4045, 4048], float)
    inn, st, rhi, rlo = BH.drange_states(h, l, c, 5, "close")
    assert list(inn[:6]) == [0, 0, 0, 0, 1, 0] and list(st[:6]) == [0, 0, 0, 0, 0, 1]            # in range after the 5th close; +1 after the close at 4045
    assert (rhi[4], rlo[4]) == (4040.0, 4000.0)
    assert list(st[6:]) == [1]                                                                      # the breakout stays set
    h2 = h.copy()
    h2[3] = 4041.0                                                                                  # a wick beyond the range on session 3 (closes inside)
    assert list(BH.drange_states(h2, l, c, 5, "close")[0][:5]) == [0, 0, 0, 0, 1]
    inn_w, st_w, *_ = BH.drange_states(h2[:5], l[:5], c[:5], 5, "wick")
    assert inn_w[4] == 1                                                                            # the range only forms at session 4, the wick on session 3 came before it
    h3 = np.array([4040, 4030, 4035, 4032, 4038, 4041, 4050], float)
    inn_w, st_w, *_ = BH.drange_states(h3, l, np.array([4020, 4025, 4015, 4030, 4020, 4035, 4048], float), 5, "wick")
    assert st_w[5] == 1                                                                             # a wick beyond (close still inside) breaks it under 'wick'
    assert BH.drange_states(h3, l, np.array([4020, 4025, 4015, 4030, 4020, 4035, 4048], float), 5, "close")[1][5] == 0
    # the table rows: the row of session k reads the state after session k-1
    d = dsess(list(zip(c - 5, h, l, c)))
    out = pd.DataFrame(index=[t.date() for t in d.index[5:]])
    BH.add_columns(out, {"dr": [5, "close"]}, d, htf.weeks(d), [], np.arange(5, 7), np.array([4040.0, 4045.0]), 1.0)
    assert list(out.drange_in) == [1, 0] and list(out.drange) == [0, 1]
    # the engine: scalps, the opposite side after a win, the day stop, the breakout side
    p = Params(**BASE, drange_scalp=True, htf_bias="combo")
    ctx = mk(D0, history(D0), p, rows=[], bias_row=dict(drange_in=1, drange=0))
    i = at(ctx, "10:00")
    ctx.state7 = {}
    assert BE.side_ok(ctx, p, 1, "AM", i) is None and BE.side_ok(ctx, p, -1, "AM", i) is None
    assert BE.scalp_now(ctx, p, "AM", i, 1) == "bh1_drange"
    sd = SimpleNamespace(x=lambda v: v)
    assert BE.scalp_cap(ctx, sd, i, p, "bh1_drange", 100.0, 110.0) == 105.0 and BE.scalp_cap(ctx, sd, i, p, "bh1_drange", 100.0, 102.0) == 102.0
    tr = SimpleNamespace(shares=1, adds=[], side="long")
    done = {"AM": False, "PM": False}
    st_ = {}
    BE.after_close(ctx, tr, done, st_, p, 4.0)                                                    # one win of 4 pts: the opposite pool next
    assert st_["bh1_dr_side"] == -1 and not st_.get("bh1_dr_done") and not done["AM"]
    ctx.state7 = st_
    assert BE.side_ok(ctx, p, 1, "AM", i) == "x_bh1_drange_side" and BE.side_ok(ctx, p, -1, "AM", i) is None
    BE.after_close(ctx, SimpleNamespace(shares=1, adds=[], side="short"), done, st_, p, 3.0)       # the second win ends the day
    assert st_["bh1_dr_done"] and done["AM"] and done["PM"]
    assert BE.side_ok(ctx, p, -1, "AM", i) == "x_bh1_drange_done"
    st2 = {}
    BE.after_close(ctx, SimpleNamespace(shares=1, adds=[], side="long"), {"AM": False}, st2, p, 11.0)   # 11 pts >= the 10-pt budget
    assert st2["bh1_dr_done"]
    ctx2 = mk(D0, history(D0), p, rows=[], bias_row=dict(drange_in=0, drange=1))                  # after the breakout: the breakout side only, no scalp
    ctx2.state7 = {}
    assert BE.side_ok(ctx2, p, -1, "AM", i) == "x_bh1_drange_break" and BE.side_ok(ctx2, p, 1, "AM", i) is None and BE.scalp_now(ctx2, p, "AM", i, 1) == ""
    # through run_day: the order of a range day is a scalp
    tr0, *_ = _run_rows(Params(**BASE), bias=BR(drange_in=1, drange=0))
    tr_, *_ = _run_rows(Params(**BASE, drange_scalp=True), bias=BR(drange_in=1, drange=0))
    assert tr0 and tr_ and not any("scalp_" in (t.lv_tags or "") for t in tr0) and all("scalp_bh1_drange" in (t.lv_tags or "") for t in tr_)


def BR(**kw):
    """An htf-table row dict with the columns run_day always reads (react / draw / pd) plus the given ones."""
    return dict(dict(react=0, draw=0, pd=0, combo=0, flip=0), **kw)


def _run_rows(p, rows=None, d=D0, bias=None, hist=None, intermarket=None, lock_rows=None, start="09:30", spike=True):
    """One scenario day (A_ROWS by default) through run_day with the htf row `bias` (the 09:30 table row) and `lock_rows` (the lock-time rows)."""
    locks, log, skips = [], [], []
    tr = S.run_day(day(A_ROWS if rows is None else rows, d=d, start=start, spike=spike), hist or history(d), "ES", p, 5, locks=locks, log=log, skips=skips,
                   bias_by_cut=A_LOCK if lock_rows is None else lock_rows, bias=bias, intermarket=intermarket)
    return tr, locks, log, skips


# --- item 4: the last daily OB's guard -------------------------------------------------------------------------------------------

K = 8000.0                                           # mirror constant for the daily books


def mirror_book(ohlc):
    return [(K - o, K - l, K - h, K - c) for o, h, l, c in ohlc]


def mirror_arr(a):
    return arr("bear" if a.kind == "bull" else "bull", a.typ, K - a.bottom, K - a.top, a.known, a.tf, K - a.ce)


def test_b7_guard_modes():
    #           open  high  low   close
    book = [(4000, 4010, 3990, 4005), (4005, 4030, 4000, 4025), (4025, 4040, 4020, 4035), (4035, 4045, 4025, 4030), (4030, 4040, 4020, 4028),     # week 1 (sessions 0-4)
            (4028, 4035, 4012, 4015), (4015, 4020, 4005, 4012), (4012, 4015, 4000, 4008), (4008, 4012, 4003, 4009), (4009, 4015, 4005, 4010),    # week 2: Mon close 4015, Tue wick 4005 / close 4012, Wed close 4008
            (4010, 4020, 4008, 4015)]                                                                                                             # week 3 Monday (session 10)
    ob = arr("bull", "ob", 4020, 4000, 1, ce=4010)                       # the last bullish daily OB: 4000-4020, MT 4010
    for bk, a in ((book, ob), (mirror_book(book), mirror_arr(ob))):
        d = dsess(bk)
        r = lambda mode, ks: BH.b7_columns(ks, d, [a], mode)
        up = bk is book
        hi, lo = ("wk_high_in", "wk_low_in") if up else ("wk_low_in", "wk_high_in")
        assert r("mt_close", [7, 8])[hi] == [0, 1]                       # Wed: only a wick under the MT (close 4012) - no change; Thu: the Wed close 4008 broke it
        assert r("mt_trade", [7, 8])[hi] == [1, 1]                       # any trade under the MT (the Tuesday wick to 4005)
        assert r("ob_close", [7, 8, 9])[hi] == [0, 0, 0]                 # a close under the OB's low 4000 never came
        assert r("mt_close", [7])[lo] == [0]
        g = r("mt_close", [8, 10])
        assert g["ob_guard" if up else "ob_guard_sh"] == [4010.0 if up else K - 4010.0] * 2           # carried into the next week: not reset on Monday
        assert r("mt_close", [10])[hi] == [0]                           # cleared at the next weekly open
    # the ob_mt flip trigger takes the level from b7_mode
    d = dsess(book)
    w = htf.weeks(d)
    bear = arr("bear", "ob", 3990, 3980, 0, ce=3985)                    # a bearish OB far below: the state turns up when price crosses its MT from below ... (closes 4005 on session 0 are above it: no cross)
    fl_close = htf._flip(d, w, [ob], ("ob_mt",), None)
    fl_trade = htf._flip(d, w, [ob], ("ob_mt",), {"b7": "mt_trade"})
    fl_obc = htf._flip(d, w, [ob], ("ob_mt",), {"b7": "ob_close"})
    t = list(d.index)
    assert fl_close[t[8]] == -1 and fl_close[t[7]] == 0                  # the Wed close 4008 < 4010 <= the Tue close: the state is -1 from Thursday
    assert fl_trade[t[7]] == -1 and fl_trade[t[6]] == 0                  # the Tue wick through the MT: from Wednesday
    assert all(fl_obc[x] == 0 for x in t)
    # the in-week gate: the engine drops every long target above the week's high once the week's high is in
    p = Params(**BASE, wk_high_in_gate=True, htf_bias="combo")
    ctx = mk(D0, history(D0), p, rows=[], bias_row=BR(wk_high_in=1, wk_low_in=0))
    i = at(ctx, "10:00")
    ctx.cur_session = "AM"
    long_ = S.Side(1, ctx.o, ctx.h, ctx.l, ctx.c, 1)
    wkh = BE._week_extreme(ctx, 1, i)
    lv = [(wkh - 1.0, "pool"), (wkh + 5.0, "pool")]
    assert BE.targets_post(ctx, long_, i, p, wkh - 10.0, lv) == [(wkh - 1.0, "pool")]
    ctx2 = mk(D0, history(D0), p, rows=[], bias_row=BR(wk_high_in=0, wk_low_in=0))
    assert BE.targets_post(ctx2, long_, i, p, wkh - 10.0, lv) == lv
    short_ = S.Side(-1, ctx.o, ctx.h, ctx.l, ctx.c, 1)
    ctx3 = mk(D0, history(D0), p, rows=[], bias_row=BR(wk_high_in=0, wk_low_in=1))
    wkl = BE._week_extreme(ctx3, -1, i)
    lv_s = [(-(wkl + 1.0), "pool"), (-(wkl - 5.0), "pool")]
    assert BE.targets_post(ctx3, short_, i, p, -(wkl + 10.0), lv_s) == [(-(wkl + 1.0), "pool")]


# --- item 7: the weekly BISI ladder ---------------------------------------------------------------------------------------------

def week_book(weekly):
    """Daily book of consecutive weeks: each (o, h, l, c) is the WEEK's candle (Mon open, Tue high, Wed low, Fri close)."""
    rows = []
    for o, h, l, c in weekly:
        rows += [(o, o, o, o), (o, h, o, o), (o, o, l, o), (o, o, o, o), (o, max(o, c), min(o, c), c)]
    return dsess(rows)


def weekly_arrs(d):
    """The weekly FVGs / OBs exactly as htf.table builds them."""
    w = htf.weeks(d)
    pos = {t: k for k, t in enumerate(d.index)}
    wl = [pos[t] + 1 for t in w["last"]]
    return htf._arrays(*(w[k].values.astype(float) for k in ("open", "high", "low", "close")), "W", lambda i: wl[i])


def test_flip_wk_bisi():
    # W0 down-close (high 4010); W1 3950-3990; W2 big up; W3 low 4040 -> a weekly BISI 4000-4040 (CE 4020); W2's close above W0's high turns the state up
    wk = [(4000, 4010, 3930, 3950), (3950, 4000, 3940, 3990), (3990, 4080, 3985, 4075), (4110, 4120, 4040, 4100)]
    for last, expect_close, expect_ce in ((4015, 0, 0), (3990, -1, -1)):
        d = week_book(wk + [(4100, 4105, min(last, 4010), last)])
        d = pd.concat([d, dsess([(last, last + 1, last - 1, last)], start=date(2026, 4, 6))])             # the Monday after (the state known before it)
        arrs = weekly_arrs(d)
        assert any(a.kind == "bull" and a.tf == "W" and (a.bottom, a.top) == (4000.0, 4040.0) for a in arrs)
        base = flip_of(d, arrs, ("wk_dc",))
        assert base[-1] == 1                                                                                  # wk_dc alone stays up (the close 4015 / 3990 is above W0's high)... until proven otherwise
        full = flip_of(d, arrs, ("wk_dc", "wk_bisi"))
        assert full[-1] == (-1 if last == 3990 else 1)                                                         # a weekly close through the BISI's low: very bearish; one into it (above the low): unchanged
        ce = flip_of(d, arrs, ("wk_dc", "wk_bisi"), {"ce": 1})
        assert ce[-1] == (-1 if last == 3990 else 0)                                                           # with wk_bisi_ce_neutral a close under the CE (above the low) is neutral
    # the mirror: a weekly SIBI above price, a weekly close through its top turns the state up
    wkm = mirror_book_weeks(wk + [(4100, 4105, 4010, 3990)])
    dm = week_book(wkm)
    arrs_m = weekly_arrs(dm)
    assert any(a.kind == "bear" and a.tf == "W" for a in arrs_m)
    assert flip_of(pd.concat([dm, dsess([(4010, 4011, 4009, 4010)], start=date(2026, 4, 6))]), arrs_m, ("wk_dc", "wk_bisi"))[-1] == 1


def mirror_book_weeks(weekly):
    return [(K - o, K - l, K - h, K - c) for o, h, l, c in weekly]
