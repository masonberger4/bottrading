"""Caption-gap pass, package day_week_context#2/3 (34 specs from digests/rulebook_gaps): focused tests of the new switches (dwc2.py, study_week.py and their hooks) - the plan / gate / side / order
filters on hand-made days (the real DayCtx and DayPlan), the position-loop helpers, the reporting fields, the weekly profile classifier, and no-look-ahead runs (full vs truncated). Nothing here
needs market data except the ES windows (skipped when absent); nothing is platform specific; no file outside the repo is written."""
import warnings
from dataclasses import fields, replace
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from mentorship import backtest as B, calendar as C, daycontext as DW, dwc1 as D1, dwc2 as D2, levels as L, nct2 as N2, study, study_week as SW, strategy as S, targets as T
from mentorship.strategy import Params
from dataclasses import dataclass as _oa_dc


@_oa_dc
class Params(Params):   # OA1029 Q92: these tests exercise other rules; the order-block narrative gate (default on) leaves them no trades
    ob_need_narrative: bool = False

from test_review_fixes import BASE, D0, A_ROWS, day, frame, history  # noqa: E402  (shared scenario builders)
from test_entries_stops import _no_look_ahead  # noqa: E402
from test_day_week_context import daily  # noqa: E402
from test_caption_gap_dwc1 import mk, at, hm, weeks, Conf, zone, _day_la, COLS, SYN, FUT, ES  # noqa: E402

NEW_FIELDS = (
    "consolidation_mode", "consol_range_days", "expansion_strict", "expansion_judas_adr", "expansion_mode", "trend_side_rule", "fri_delivered_stop", "fri_pool_choice", "mon_big_frac", "mw_break_bias", "mw_carry",
    "thu_reversal_tag", "thu_reversal_trade", "wed_week_extreme", "days_mode", "late_week_fallback", "no_long_after_thu_noon", "ny_cont_gate", "adr_news_exempt", "london_low_guard",
    "london_filters", "po3_adr_invalid", "tgif_reversal_pct", "tgif_fvg_cap", "adr_close_runner", "fri_trail_from", "adr_met_runner", "adr_runner_until", "adr_contracted_tag")
KNOBS = {"consol_range_days", "mon_big_frac", "adr_runner_until", "expansion_judas_adr"}
OFF = {"consolidation_mode": "skip", "expansion_strict": False, "expansion_mode": "off", "trend_side_rule": False, "fri_delivered_stop": False, "fri_pool_choice": False, "mw_break_bias": False,
       "mw_carry": False, "thu_reversal_tag": False, "thu_reversal_trade": False, "wed_week_extreme": False, "days_mode": "all", "late_week_fallback": False, "no_long_after_thu_noon": False,
       "ny_cont_gate": False, "adr_news_exempt": False, "london_low_guard": False, "london_filters": False, "po3_adr_invalid": False, "tgif_fvg_cap": False, "adr_close_runner": False,
       "fri_trail_from": 0, "adr_met_runner": False, "adr_contracted_tag": False, "tgif_reversal_pct": None, "monday_mode": "trade", "tue_off_monday": "off"}


def first_date(pred, start=date(2023, 1, 2), n=900):
    d = start
    for _ in range(n):
        if C.is_trading_day(d) and pred(d):
            return d
        d += timedelta(days=1)
    raise AssertionError("no such date")


def rows_5m(spec, start="00:00", base=100.0, w=0.2):
    """5m (o, h, l, c) rows from `start` through the end of `spec` ({HH:MM: (o, h, l, c)}); flat at `base` elsewhere."""
    m0 = hm(start)
    last = max(hm(k) for k in spec)
    out = []
    for m in range(m0, last + 5, 5):
        k = f"{m // 60:02d}:{m % 60:02d}"
        out.append(spec.get(k, (base, base + w, base - w, base)))
    return out


def order(sd, entry, stop, levels, kinds=None, **kw):
    o = dict(side=sd, entry=entry, stop=stop, shares=100, plan_shares=100, rungs=[], levels=list(levels), level_kinds=list(kinds or ["pool"] * len(levels)), t1=levels[0],
             t2=levels[1] if len(levels) > 1 else None, final_T=True, ext=stop, ext_i=0, swept="x", entry_kind="", smt=None, leg=None)
    o.update(kw)
    return o


# --- defaults and validation --------------------------------------------------------------------------------------------

def test_defaults_and_validation():
    p = Params()
    for f in NEW_FIELDS:
        assert f in Params.__dataclass_fields__, f
    for k, v in OFF.items():
        assert getattr(p, k) == v, k
    assert p.mon_big_frac == 0.5 and p.consol_range_days == 3 and p.adr_runner_until == 840
    assert p.dw2_hist == 0 and Params(adr_contracted_tag=True).dw2_hist == 66 and Params(trend_side_rule=True).dw2_hist == 66
    # the owner-fixed switches are untouched by this chunk
    assert p.sb_model is False and "sb_use_bias" in Params.__dataclass_fields__ and "want_all_engines" in Params.__dataclass_fields__
    assert p.state_machine is False and p.consol_bars == 20 and p.consol_adr == 0.3                    # item 125 was already built (state_machine)
    for bad in (dict(consolidation_mode="x"), dict(expansion_mode="x"), dict(days_mode="x"), dict(monday_mode="x"), dict(tue_off_monday="x"), dict(tgif_reversal_pct=0.0),
                dict(tgif_reversal_pct=1.0), dict(consol_range_days=0), dict(mon_big_frac=-1), dict(fri_trail_from=-1), dict(adr_runner_until=0), dict(tgif_zone=True, tgif_reversal_pct=0.2)):
        with pytest.raises(ValueError):
            Params(**bad)
    Params(monday_mode="big_into_array", tue_off_monday="ote", consolidation_mode="scalp", days_mode="tue_wed", tgif_zone=True, tgif_reversal_pct=0.30)


def test_every_new_switch_has_a_study_variant():
    used = set()
    for v in study._DWC2_DECISIONS.values():
        used |= set(v)
    for f in NEW_FIELDS:
        assert f in used or f in KNOBS, f
    for gid in ("N8-consolidation-tradeable", "N8-expansion-day-conditions", "DS2-contraction-precedes-expansion", "DS2-trending-day-direction", "N10-friday-preopen-delivered",
                "N10-friday-pool-choice", "N10-monday-weekly-extreme", "N10-mon-wed-range-break", "T14-wednesday-weekly-extreme", "new-consolidation-thursday-reversal",
                "DS2-monday-ideal-day", "DS2-mon-wed-fallback-thu-fri", "DS2-weekly-template-sequence", "DS2-tue-to-thu-horizon", "DS2-ny-continuation-adr-pending",
                "DS2-adr-filled-news-extends", "new-london-low-violated", "N8-london-filters-gate-london", "T13-po3-small-open-wick", "M14-reversal-threshold",
                "M14-tgif-daily-fvg-ce-cap", "LLT3-adr-fib-close-zone", "X5-friday-tight-trail", "L16-adr-contraction-runner"):
        assert any(k.startswith(gid) for k in study.DECISIONS), gid
    for k, v in study._DWC2_DECISIONS.items():
        assert k in study.DECISIONS
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            replace(Params(), **v)


# --- item 125: already built ----------------------------------------------------------------------------------------------------

def test_state_machine_was_already_built():
    """definitions_pd_arrays_structure #125: levels.delivery_state + state_machine (sm2) exist: a flat 30-bar fixture is CONSOLIDATION (no duplicate switch is added by this chunk)."""
    n = 30
    o = np.full(n, 100.0); h = o + 0.5; l = o - 0.5; c = o.copy()
    assert L.delivery_state(o, h, l, c, n - 1, 10.0, 20, 0.3) == "CONSOLIDATION"
    assert "state_machine" in Params.__dataclass_fields__


# --- item 48: consolidation modes ------------------------------------------------------------------------------------------------------

def test_consolidation_mode_routes(monkeypatch):
    monkeypatch.setattr(DW, "_consol_predictors", lambda ctx, d, p, hist, eth: ["no_report"])
    d = D0
    h = history(d)
    i_ = lambda c: at(c, "10:00")
    # skip (the default): untouched
    c0 = mk(d, h, Params(**BASE))
    assert "consol_mode" not in c0.dplan.info and "consol_nochop" not in c0.dplan.info
    # fade_with_htf: bias +1 -> only a long turtle-soup order
    p = Params(**BASE, consolidation_mode="fade_with_htf")
    c = mk(d, h, p, bias_row={"draw": 1})
    assert "consol_day" in c.dplan.tags and c.dplan.info["consol_mode"] == "fade_with_htf" and c.dplan.info.get("consol_nochop")
    sl, ss = c.sides_map[1], c.sides_map[-1]
    assert D2.order_ok(c, sl, order(sl, 100.0, 99.0, [102.0], entry_kind="ts_cc_limit"), "AM", i_(c), p) is None
    assert D2.order_ok(c, sl, order(sl, 100.0, 99.0, [102.0], entry_kind="ifvg"), "AM", i_(c), p) == "x_dw_consol_fade"
    assert D2.order_ok(c, ss, order(ss, ss.x(100.0), ss.x(101.0), [ss.x(98.0)], entry_kind="ts_cc_limit"), "AM", i_(c), p) == "x_dw_consol_fade"
    cc = mk(d, h, p, bias_row={"draw": 0, "combo": 1})                                          # the table's bias (combo) is the one read, not the draw
    assert D2.order_ok(cc, cc.sides_map[1], order(cc.sides_map[1], 100.0, 99.0, [102.0], entry_kind="ts_cc_limit"), "AM", i_(cc), p) is None
    c_nob = mk(d, h, p)
    assert D2.order_ok(c_nob, c_nob.sides_map[1], order(c_nob.sides_map[1], 100.0, 99.0, [102.0], entry_kind="ts_cc_limit"), "AM", i_(c_nob), p) == "x_dw_consol_fade_bias"
    # range_trade: turtle soup / OTE / sick sister only, targets inside the 3-session range
    p = Params(**BASE, consolidation_mode="range_trade")
    c = mk(d, h, p)
    assert c.dplan.info["consol_range"] == (108.0, 90.0)
    sl = c.sides_map[1]
    o = order(sl, 100.0, 99.0, [105.0, 110.0, 112.0], entry_kind="turtle_soup", runner=True)
    assert D2.order_ok(c, sl, o, "AM", i_(c), p) is None and o["levels"] == [105.0, 108.0] and o["level_kinds"][-1] == "pool" and not o["final_T"] and "runner" not in o       # capped at the range high, which becomes the last rung
    o3 = order(sl, 100.0, 99.0, [106.0], entry_kind="turtle_soup", runner=True)
    c.conf = Conf(z={})
    c.conf.arrays_any = lambda now, side, tfs: [(104.0, 105.0), (109.0, 110.0)]          # an open bearish 4h array inside the range, one beyond it
    assert D2.order_ok(c, sl, o3, "AM", i_(c), p) is None and o3["levels"] == [104.0, 106.0, 108.0] and o3["t1"] == 104.0              # the opposite open FVG and the range high as rungs
    c.conf = None
    assert D2.order_ok(c, sl, order(sl, 100.0, 99.0, [105.0], entry_kind="ifvg"), "AM", i_(c), p) == "x_dw_consol_range_setup"
    ote = order(sl, 95.0, 94.0, [105.0], entry_kind="ifvg", leg=(90.0, 108.0))                   # 95 sits in 93.78-96.84 (62-79 % of the 90-108 leg)
    assert D2.order_ok(c, sl, ote, "AM", i_(c), p) is None
    assert D2.order_ok(c, sl, order(sl, 100.0, 99.0, [110.0], entry_kind="turtle_soup"), "AM", i_(c), p) == "x_dw_consol_range_target"
    assert D2.order_ok(c, sl, order(sl, 100.0, 99.0, [105.0], entry_kind="ifvg", smt=True), "AM", i_(c), p) is None                       # the sick sister (the partner failed to confirm)
    # scalp: AM scalps flat by 11:00, the opening range gate (consol_apply)
    p = Params(**BASE, consolidation_mode="scalp")
    c = mk(d, h, p)
    assert c.dplan.info["consol_apply"] and DW.scalp_now(c, p, "AM", i_(c)) == "consol_day" and DW.scalp_now(c, p, "PM", i_(c)) == ""
    q = D2.day_params(replace(p, consol_am_out=0), c.dplan)
    assert q.consol_am_out == 660
    # no consolidation predictor: nothing, and the intraday chop stand-aside stays ON for the day (it is switched off only on the days the mode applies to)
    monkeypatch.setattr(DW, "_consol_predictors", lambda ctx, d, p, hist, eth: [])
    cn = mk(d, h, Params(**BASE, consolidation_mode="range_trade", drr_tests=()))
    assert "consol_mode" not in cn.dplan.info and "consol_nochop" not in cn.dplan.info


# --- items 50 / 53: expansion -------------------------------------------------------------------------------------------------

def test_expansion_due_conditions():
    d = D0
    h = history(d, first=(120.0, 80.0), hi=102.0, lo=98.0)                                    # the prior range 4 << ADR5 (40)
    base = dict(**BASE, expansion_due=True, expansion_targets=(1.5,))
    plain = mk(d, h, Params(**base))
    assert "expansion_due" in plain.dplan.tags and plain.dplan.info["expansion_due"]
    p = Params(**base, expansion_strict=True)
    c = mk(d, h, p, bias_row={"draw": 1})
    a = c.dplan.info["adr5_prev"]
    assert "expansion_due" not in c.dplan.tags and c.dplan.info["expansion_pending"]
    # static conditions: a big_prev / three-close day drops the tag for good
    assert "expansion_pending" not in mk(d, h, p, dt={"big_prev"}).dplan.info and "expansion_due" not in mk(d, h, p, dt={"three_up"}).dplan.tags
    # dynamic: the manipulation leg (a low under the midnight open, then the rally) is opposite the bias
    spec = {"09:30": (100.0, 100.1, 95.0, 95.2), "09:35": (95.2, 99.0, 95.0, 98.9), "09:40": (98.9, 100.5, 98.8, 100.4), "09:45": (100.4, 101.0, 100.3, 100.9)}
    c = mk(d, h, p, rows=rows_5m(spec, "09:30"), bias_row={"draw": 1})
    i = at(c, "09:45")
    sd = c.sides_map[1]
    assert D2.expansion_live(c, p, i) == 1
    lv = DW.expansion_levels(c, sd, i, p)
    ext = float(sd.l[c.start:i + 1].min())
    assert lv == [(ext + 1.5 * a, "array")]
    ent = D2.entry_tags(c, p, c.dplan, i)
    assert "expansion_due" in ent
    # no bias, or the leg with the bias (no manipulation under the open): no rung
    assert D2.expansion_live(mk(d, h, p, rows=rows_5m(spec, "09:30")), p, i) == 0
    up = {"09:30": (100.0, 101.0, 99.9, 100.9), "09:35": (100.9, 102.0, 100.8, 101.9)}
    cu = mk(d, h, p, rows=rows_5m(up, "09:30"), bias_row={"draw": 1})
    assert D2.expansion_live(cu, p, at(cu, "09:35")) == 0 and DW.expansion_levels(cu, cu.sides_map[1], at(cu, "09:35"), p) == []


def test_expansion_candidate():
    d = first_date(lambda x: 510 in C.release_times(x) and x.weekday() in (1, 2))
    h = history(d, first=(120.0, 80.0), hi=102.0, lo=98.0)
    p = Params(**BASE, expansion_mode="tag")
    c = mk(d, h, p)
    assert "expansion_candidate" in c.dplan.tags
    assert "expansion_candidate" not in mk(d, h, Params(**BASE)).dplan.tags                                # off
    wide = history(d)                                                                                    # a normal-range prior session: not a contraction
    assert "expansion_candidate" not in mk(d, wide, p).dplan.tags
    quiet = first_date(lambda x: not [r for r in C.release_times(x) if 510 <= r <= 600] and x.weekday() == 1)
    assert "expansion_candidate" not in mk(quiet, history(quiet, first=(120.0, 80.0), hi=102.0, lo=98.0), p).dplan.tags      # no release 08:30-10:00
    f = Params(**BASE, expansion_mode="full")
    cf = mk(d, h, f)
    q = D2.day_params(f, cf.dplan)
    assert q.ladder_fracs_slow == f.ladder_fracs and q.po3_runner is True
    assert D2.day_params(f, mk(d, wide, f).dplan) is f                                                      # untagged day: unchanged
    assert D2.day_params(p, c.dplan).po3_runner is False                                                    # "tag" does not change the ladder


# --- item 54: trending-day direction -----------------------------------------------------------------------------------------

def test_trend_recipe_side(monkeypatch):
    d = D0
    monkeypatch.setattr(DW, "news_class", lambda x: "high")
    h = history(d, n=25)                                                                                   # ranges all 18: the last is the smallest of 5 (<=); the 60-day EQ needs >= 20 sessions
    bull = SimpleNamespace(i=10, top=95.0, bottom=93.0, kind="bull")
    monkeypatch.setattr(D1, "_alive_zones", lambda hist, kind, end=None: [bull] if kind == "bull" else [])
    p = Params(**BASE, trend_recipe="side", trend_side_rule=True)
    c = mk(d, h, p, bias_row={"draw": 1})
    assert c.dplan.info["trend_side"] == 1 and "trend_side_up" in c.dplan.tags and c.dplan.sides["trend_recipe"] == (-1,)
    assert D2.side_ok(c, p, 1, "AM", at(c, "09:00")) == "x_dw_trend_wait"                                  # the table is cut at 09:30
    assert D2.side_ok(c, p, 1, "AM", at(c, "10:00")) is None
    cm = mk(d, h, p, bias_row={"draw": -1})
    assert D2.side_ok(cm, p, 1, "AM", at(cm, "10:00")) == "x_dw_trend_draw"                                 # the matrix does not agree
    # a premium array above the EQ: the mirror; both kinds at once: no side
    bear = SimpleNamespace(i=10, top=106.0, bottom=104.0, kind="bear")
    monkeypatch.setattr(D1, "_alive_zones", lambda hist, kind, end=None: [bear] if kind == "bear" else [])
    cb = mk(d, h, p, bias_row={"draw": -1})
    assert cb.dplan.info["trend_side"] == -1 and cb.dplan.sides["trend_recipe"] == (1,)
    monkeypatch.setattr(D1, "_alive_zones", lambda hist, kind, end=None: [bull] if kind == "bull" else [bear])
    assert "trend_side" not in mk(d, h, p, bias_row={"draw": 1}).dplan.info
    # the array is above the 60-day EQ: not a discount array
    hi_bull = SimpleNamespace(i=10, top=107.0, bottom=105.0, kind="bull")
    monkeypatch.setattr(D1, "_alive_zones", lambda hist, kind, end=None: [hi_bull] if kind == "bull" else [])
    assert "trend_side" not in mk(d, h, p, bias_row={"draw": 1}).dplan.info
    # no 08:30 news: no recipe
    monkeypatch.setattr(DW, "news_class", lambda x: "none")
    monkeypatch.setattr(D1, "_alive_zones", lambda hist, kind, end=None: [bull] if kind == "bull" else [])
    assert "trend_side" not in mk(d, h, p, bias_row={"draw": 1}).dplan.info
    # contraction over 3 days is "small" too; a larger last range is not
    monkeypatch.setattr(DW, "news_class", lambda x: "high")
    big_last = history(d, first=(108.0, 90.0), hi=112.0, lo=88.0)
    assert "trend_side" not in mk(d, big_last, p, bias_row={"draw": 1}).dplan.info


# --- item 55: Friday delivered before the open --------------------------------------------------------------------------------------

def test_fri_delivered_stop(monkeypatch):
    fri = first_date(lambda x: x.weekday() == 4 and not C.nfp_date(x), start=date(2026, 6, 1))
    h = history(fri)
    p = Params(**BASE, fri_delivered_stop=True)
    monkeypatch.setattr(DW, "eve_draw", lambda ctx, p, hist: dict(done=True, side=1, px=105.0))
    monkeypatch.setattr(D2, "_smt_extreme", lambda ctx, side, k, win=12: True)
    c = mk(fri, h, p)
    assert D2.side_ok(c, p, 1, "AM", at(c, "10:30")) is None                                                # before 11:00 the AM continuation is allowed
    assert D2.side_ok(c, p, 1, "AM", at(c, "11:00")) == "x_dw_fri_delivered"
    assert D2.side_ok(c, p, 1, "PM", at(c, "14:00")) == "x_dw_fri_delivered"
    assert D2.side_ok(c, p, -1, "PM", at(c, "14:00")) is None                                               # the counter side is left to pm_reversal
    monkeypatch.setattr(D2, "_smt_extreme", lambda ctx, side, k, win=12: False)
    assert D2.side_ok(mk(fri, h, p), p, 1, "PM", at(c, "14:00")) is None                                    # no SMT at the extreme
    monkeypatch.setattr(D2, "_smt_extreme", lambda ctx, side, k, win=12: True)
    monkeypatch.setattr(DW, "eve_draw", lambda ctx, p, hist: dict(done=False, side=1, px=105.0))
    assert D2.side_ok(mk(fri, h, p), p, 1, "PM", at(c, "14:00")) is None                                    # not delivered before 09:30
    thu = first_date(lambda x: x.weekday() == 3 and not C.nfp_date(x), start=date(2026, 6, 1))
    monkeypatch.setattr(DW, "eve_draw", lambda ctx, p, hist: dict(done=True, side=1, px=105.0))
    assert D2.side_ok(mk(thu, history(thu), p), p, 1, "PM", at(c, "14:00")) is None                         # Fridays only
    assert D2.side_ok(mk(fri, h, Params(**BASE)), Params(**BASE), 1, "PM", at(c, "14:00")) is None          # off


def test_smt_at_the_preopen_extreme():
    d = D0
    h = history(d)
    main = mk(d, h, Params(**BASE), spike=True)
    pc = S.DayCtx(day([], d=d, start="09:30"), d, h, 5)
    main.pside = (pc, None, pd.Series(np.arange(len(pc.idx)), index=pc.idx))
    k = DW._k570(main)
    assert D2._smt_extreme(main, 1, k) is True                                                             # the main index spiked at 03:00, the partner did not
    pc2 = S.DayCtx(day([], d=d, start="09:30", spike=True), d, h, 5)
    main.pside = (pc2, None, pd.Series(np.arange(len(pc2.idx)), index=pc2.idx))
    assert D2._smt_extreme(main, 1, k) is False                                                            # both spiked: confirmed
    main.pside = (None, None, None)
    assert D2._smt_extreme(main, 1, k) is None


# --- item 56: Friday pool choice ------------------------------------------------------------------------------------------------

def test_friday_pool_choice():
    fri = first_date(lambda x: x.weekday() == 4 and not C.nfp_date(x), start=date(2026, 6, 1))
    h = history(fri, first=(102.0, 98.0), hi=102.0, lo=98.0)                                               # PDL 98, PDH 102, this week's high 102
    spec = {"08:00": (100.0, 100.1, 97.0, 97.5), "08:05": (97.5, 100.3, 97.4, 100.2)}                      # the sell-side pool (PDL 98) ran before the lock
    c = mk(fri, h, Params(**BASE), rows=rows_5m(spec, "08:00"), start="08:00")
    p = Params(**BASE, fri_pool_choice=True)
    kl = at(c, "09:30")
    up = [(0.5, 100.7, "pool", "overnight_high", 1), (1.9, 101.9, "pool", "pdh1", 1), (4.0, 104.0, "pool", "far_pool", 1)]
    dn = [(2.0, 98.0, "pool", "pdl1", -1), (3.0, 97.0, "array", "x", 0)]
    r = D2.fri_pool_pick(c, p, up, dn, 100.2, kl, 570, h)
    assert r is not None and r[0] == 1
    assert [x[3] for x in r[1]] == ["overnight_high", "pdh1"]                                              # the pool beyond the week's high (104 > 102) is dropped
    assert all(x[2] != "pool" for x in r[2])                                                              # no remaining sell-side pool is the draw
    assert D2.fri_pool_pick(c, Params(**BASE), up, dn, 100.2, kl, 570, h) is None                         # off
    calm = mk(fri, h, p)                                                                                  # PDL not run
    assert D2.fri_pool_pick(calm, p, up, dn, 100.2, kl, 570, h) is None
    thu = first_date(lambda x: x.weekday() == 3, start=date(2026, 6, 1))
    assert D2.fri_pool_pick(mk(thu, history(thu), p, rows=rows_5m(spec, "08:00"), start="08:00"), p, up, dn, 100.2, kl, 570, history(thu)) is None
    # the bearish mirror: the PDH ran, the unrun sell-side pools below are the draw
    spec2 = {"08:00": (100.0, 103.0, 99.9, 102.5), "08:05": (102.5, 102.6, 99.8, 99.9)}
    c2 = mk(fri, h, p, rows=rows_5m(spec2, "08:00"), start="08:00")
    up2 = [(3.0, 103.0, "pool", "x", 1)]
    dn2 = [(0.5, 99.5, "pool", "overnight_low", -1), (4.0, 96.0, "pool", "far", -1)]
    r2 = D2.fri_pool_pick(c2, p, up2, dn2, 100.0, kl, 570, h)
    assert r2 is not None and r2[0] == -1 and [x[3] for x in r2[2]] == ["overnight_low"]                  # 96 is below the week's low (98)
    # a TGIF Friday takes a single exit (no runner)
    cp = mk(fri, h, p, dt={"tgif_short"})
    assert cp.dplan.info["single_exit"] and D2.day_params(replace(p, runner_frac=0.3, po3_runner=True), cp.dplan).runner_frac == 0.0
    assert "single_exit" not in mk(fri, h, p).dplan.info


# --- item 57: Monday, a big range into a daily array -------------------------------------------------------------------------------

def _bear_weeks():
    """Two prior weeks that leave a bearish weekly tone: a closing-up week, then a week closing under its low (weekly_state -1)."""
    return weeks(date(2026, 5, 4), [(100.0, 105.0, 95.0, 102.0), (102.0, 103.0, 90.0, 93.0)])


def test_monday_big_into_array():
    d = date(2026, 5, 18)
    assert d.weekday() == 0 and not C.nfp_date(d)
    h = _bear_weeks()
    assert D1.weekly_state(h, d) == -1
    p = Params(**BASE, monday_mode="big_into_array", mon_big_frac=0.1)
    conf = Conf(z={"D": zone(-1, 102.0, 106.0)})                                                           # a bearish daily array around the overnight high (102.5)
    c = mk(d, h, p, spike=True, conf=conf)
    P = c.dplan
    assert P.info["mon_big"] == -1 and "mon_big_candidate" in P.tags and not any(r == "monday" for _s, r in P.blocks)
    assert D2.gate(c, p, "AM", at(c, "09:00"), 540) == "x_dw_mon_big_wait"                                  # the overnight range is complete at 09:30
    i = at(c, "09:30")
    assert D2.gate(c, p, "AM", i, 570) is None
    assert D2.side_ok(c, p, 1, "AM", i) == "x_dw_mon_big_side" and D2.side_ok(c, p, -1, "AM", i) is None   # only the weekly-bias side
    lvt = []
    assert D2.size_mult(c, p, lvt) == 0.5 and lvt == ["size_mon_big"] and DW.day_risk(c, p) == 0.5
    k = at(c, "09:35")
    assert "wk_ext_candidate" in D2.entry_tags(c, p, P, k)
    # the overnight extreme did not touch a daily array: no Monday
    far = mk(d, h, p, spike=True, conf=Conf(z={"D": zone(-1, 120.0, 125.0)}))
    assert D2.gate(far, p, "AM", at(far, "09:30"), 570) == "x_dw_mon_big"
    assert D2.gate(mk(d, h, p, spike=True, conf=None), p, "AM", i, 570) == "x_dw_mon_big"
    # the range is too small for the fraction
    q = replace(p, mon_big_frac=5.0)
    assert D2.gate(mk(d, h, q, spike=True, conf=conf), q, "AM", i, 570) == "x_dw_mon_big"
    # the bullish mirror: the overnight LOW into a bullish array
    hb = weeks(date(2026, 5, 4), [(100.0, 105.0, 95.0, 98.0), (98.0, 108.0, 97.0, 107.0)])
    assert D1.weekly_state(hb, d) == 1
    low_spec = {"03:00": (100.0, 100.1, 97.5, 98.0), "03:05": (98.0, 100.2, 97.9, 100.0)}
    cb = mk(d, hb, p, rows=rows_5m(low_spec, "00:00"), start="00:00", conf=Conf(z={"D": zone(1, 96.0, 98.0)}))
    assert cb.dplan.info["mon_big"] == 1
    assert D2.gate(cb, p, "AM", at(cb, "09:30"), 570) is None and D2.side_ok(cb, p, -1, "AM", at(cb, "09:30")) == "x_dw_mon_big_side"
    # no weekly bias: the Monday is skipped; a Tuesday and the default mode are untouched
    assert any(r == "monday_no_bias" for _s, r in mk(d, history(d), p).dplan.blocks)
    assert "mon_big" not in mk(d, h, Params(**BASE)).dplan.info
    tue = d + timedelta(days=1)
    assert "mon_big" not in mk(tue, h, p).dplan.info


# --- items 60 / 62 / 63 / 66 / 67 / 68 / 69: the week templates ---------------------------------------------------------------------

def _thu_hist(bias_up=True, mw=((102.0, 103.0, 102.0, 102.5),) * 3):
    """Two prior weeks (weekly tone +1 / -1), then Mon-Wed of the week of Thursday 2026-05-21."""
    if bias_up:
        wk = weeks(date(2026, 5, 4), [(100.0, 101.0, 90.0, 95.0), (95.0, 103.0, 94.0, 102.0)])
    else:
        wk = weeks(date(2026, 5, 4), [(100.0, 110.0, 99.0, 105.0), (105.0, 106.0, 90.0, 93.0)])
    cur = [daily(date(2026, 5, 18) + timedelta(days=k), *m) for k, m in enumerate(mw)]
    return wk + cur


def test_mw_break_bias_side():
    d = date(2026, 5, 21)
    h = _thu_hist(True)
    assert D1.weekly_state(h, d) == 1
    spec = {"09:30": (103.0, 105.0, 102.9, 104.9)}
    rows = rows_5m(spec, "09:30", base=103.0)
    p = Params(**BASE, thu_fri_break="side")
    c = mk(d, h, p, rows=rows, base=103.0)
    i = at(c, "09:30")
    assert c.dplan.info["mw"][0] == 103.0 and DW.side_ok(c, p, -1, "AM", i) == "x_dw_thu_fri_break"          # the break up is with the bias (+1): the counter side is blocked
    q = replace(p, mw_break_bias=True)
    assert DW.side_ok(c, q, -1, "AM", i) == "x_dw_thu_fri_break"                                           # a break WITH the weekly bias counts
    hd = _thu_hist(False)
    assert D1.weekly_state(hd, d) == -1
    cd = mk(d, hd, p, rows=rows, base=103.0)
    assert DW.side_ok(cd, p, -1, "AM", i) == "x_dw_thu_fri_break"                                          # without the switch the break counts either way
    assert DW.side_ok(cd, q, -1, "AM", i) is None                                                          # the break against the bias is not a confirmation
    assert DW.side_ok(cd, q, 1, "AM", i) is None


def test_mw_carry_keeps_the_bias_when_the_target_is_missed():
    d = date(2026, 5, 25)                                                                                   # (a Monday; the third prior week is 05-18)
    h = weeks(date(2026, 5, 4), [(100.0, 101.0, 90.0, 95.0), (95.0, 103.0, 94.0, 102.0), (102.0, 102.5, 92.0, 93.0)])
    assert D1.weekly_state(h, d) == -1                                                                      # the last week closed under the last up-week's low
    assert D2.carried_bias(h, d) == 1                                                                       # ... but it never reached the 4-week high (103)
    ctx = SimpleNamespace(bias_row=None)
    assert D2.weekly_bias(ctx, h, d, Params(**BASE)) == -1
    assert D2.weekly_bias(SimpleNamespace(bias_row=None), h, d, Params(**BASE, mw_carry=True)) == 1
    h2 = weeks(date(2026, 5, 4), [(100.0, 101.0, 90.0, 95.0), (95.0, 103.0, 94.0, 102.0), (102.0, 104.0, 92.0, 93.0)])            # the target (103) was reached
    assert D2.carried_bias(h2, d) == 0


def test_thu_reversal_tag_and_trade(monkeypatch):
    d = date(2026, 5, 21)
    monkeypatch.setattr(D2, "thu_release", lambda x: True)                                                  # a release (08:30 / 14:00) on the day
    h = _thu_hist(True)
    p = Params(**BASE, thu_reversal_tag=True, thu_reversal_trade=True)
    spec = {"09:30": (102.5, 102.6, 101.5, 101.7), "09:35": (101.7, 102.8, 101.6, 102.7)}
    c = mk(d, h, p, rows=rows_5m(spec, "09:30"), base=102.5)
    P = c.dplan
    a5 = P.info["adr5_prev"]
    assert P.info["thu_rev"][:2] == (103.0, 102.0) and P.info["thu_rev"][2] == 1 and "thu_rev_setup" in P.tags and (103.0 - 102.0) <= 1.5 * a5
    i = at(c, "09:35")
    assert "thu_reversal" in D2.entry_tags(c, p, P, i)
    assert "thu_reversal" not in D2.entry_tags(c, p, P, at(c, "09:30"))                                    # the low is in, the close is not back above yet
    # the pool and the side
    sl = c.sides_map[1]
    assert DW.sell_pools(c, sl, i, p) == {"mon_wed": 102.0} and DW.target_pools(c, sl, i, p)
    assert D2.side_ok(c, p, -1, "AM", i) == "x_dw_thu_reversal_side" and D2.side_ok(c, p, 1, "AM", i) is None
    assert D2.order_ok(c, sl, order(sl, 102.5, 101.5, [104.0], swept="mon_wed"), "AM", i, p) is None
    assert D2.order_ok(c, sl, order(sl, 102.5, 101.5, [104.0], swept="pdl1"), "AM", i, p) == "x_dw_thu_reversal_pool"
    # no release on the Thursday (the real calendar of 2026-05-21 has none): no setup, no trade filter
    monkeypatch.setattr(D2, "thu_release", lambda x: False)
    assert "thu_rev" not in mk(d, h, p, rows=rows_5m(spec, "09:30"), base=102.5).dplan.info
    monkeypatch.setattr(D2, "thu_release", lambda x: True)
    # the day-level tag (reporting): traded under the Mon-Wed low and closed back above it
    g = day(rows_5m(spec, "09:30"), d=d, start="09:30", base=102.5)
    assert D2.thu_day_tag(g, h, p) == "thu_reversal" and D2.thu_day_tag(g, [], p) == ""
    gq = day(rows_5m({"09:30": (102.5, 102.6, 102.2, 102.4)}, "09:30"), d=d, start="09:30", base=102.5)
    assert D2.thu_day_tag(gq, h, p) == ""
    # off: nothing; a Mon-Wed range above 1.5 x ADR5 is no consolidation
    assert "thu_rev" not in mk(d, h, Params(**BASE), rows=rows_5m(spec, "09:30"), base=102.5).dplan.info
    wide = _thu_hist(True, mw=((102.0, 140.0, 100.0, 102.5),) * 3)
    assert "thu_rev" not in mk(d, wide, p, base=102.5).dplan.info
    # the tag-only switch does not make the pool a trade pool
    ct = mk(d, h, Params(**BASE, thu_reversal_tag=True), rows=rows_5m(spec, "09:30"), base=102.5)
    assert DW.sell_pools(ct, ct.sides_map[1], i, Params(**BASE, thu_reversal_tag=True)) == {} and "thu_reversal" in D2.entry_tags(ct, Params(**BASE, thu_reversal_tag=True), ct.dplan, i)
    # the bearish mirror
    hd = _thu_hist(False)
    cd = mk(d, hd, p, rows=rows_5m({"09:30": (102.5, 103.6, 102.4, 103.4), "09:35": (103.4, 103.5, 102.3, 102.4)}, "09:30"), base=102.5)
    assert cd.dplan.info["thu_rev"][2] == -1
    assert "thu_reversal_bear" in D2.entry_tags(cd, p, cd.dplan, at(cd, "09:35"))


def test_days_mode_mon_wed():
    thu, mon, tue, fri = date(2026, 5, 21), date(2026, 5, 18), date(2026, 5, 19), date(2026, 5, 22)
    p = Params(days_mode="mon_wed")
    assert S.blocked(thu, "AM", p) == "days_mode" and S.blocked(fri, "AM", p) == "days_mode"
    assert S.blocked(mon, "AM", p) is None and S.blocked(tue, "AM", p) is None
    q = Params(days_mode="tue_wed")
    assert S.blocked(mon, "AM", q) == "days_mode" and S.blocked(tue, "AM", q) is None and S.blocked(thu, "AM", q) == "days_mode"
    assert S.blocked(thu, "AM", Params()) is None


def test_late_week_fallback():
    thu = date(2026, 5, 21)
    p = Params(**BASE, days_mode="mon_wed", late_week_fallback=True)
    assert S.blocked(thu, "AM", p) is None                                                                  # decided by the week's move instead
    delivered = _thu_hist(True, mw=((102.0, 140.0, 101.0, 130.0), (130.0, 141.0, 129.0, 131.0), (131.0, 142.0, 130.0, 140.0)))
    c = mk(thu, delivered, p, base=140.0)
    assert any(r == "days_mode" for _s, r in c.dplan.blocks) and "late_week" not in c.dplan.tags
    flat = _thu_hist(True)
    c2 = mk(thu, flat, p)
    assert not any(r == "days_mode" for _s, r in c2.dplan.blocks) and "late_week" in c2.dplan.tags
    # no bias = not delivered: the late-week templates stay available
    assert "late_week" in mk(thu, history(thu), p).dplan.tags
    assert D2.mw_delivered(flat, thu, 1, 5.0) is False and D2.mw_delivered(delivered, thu, 1, 5.0) is True and D2.mw_delivered(delivered, thu, 0, 5.0) is False
    # the Friday is decided the same way
    fri = thu + timedelta(days=1)
    assert any(r == "days_mode" for _s, r in mk(fri, delivered + [daily(thu, 140.0, 141.0, 139.0, 140.0)], p, base=140.0).dplan.blocks)


def test_no_long_after_thu_noon():
    thu, fri = date(2026, 5, 21), date(2026, 5, 22)
    h = _thu_hist(True)
    p = Params(**BASE, no_long_after_thu_noon=True)
    c = mk(thu, h, p)
    assert c.dplan.info["thu_cut"] == 1
    assert D2.side_ok(c, p, 1, "PM", at(c, "12:00")) == "x_dw_no_long_after_thu_noon" and D2.side_ok(c, p, 1, "AM", at(c, "11:55")) is None
    assert D2.side_ok(c, p, -1, "PM", at(c, "13:00")) is None
    # Friday after a Thursday that closed up with the bias: no weekly-direction entries
    up = h + [daily(thu, 102.5, 104.0, 102.0, 103.5)]
    cf = mk(fri, up, p)
    assert cf.dplan.sides["no_long_after_thu_noon"] == (1,) and DW.side_ok(cf, p, 1, "AM", at(cf, "10:00")) == "x_dw_no_long_after_thu_noon" and DW.side_ok(cf, p, -1, "AM", at(cf, "10:00")) is None
    dn = h + [daily(thu, 102.5, 103.0, 100.0, 100.5)]
    assert "no_long_after_thu_noon" not in mk(fri, dn, p).dplan.sides
    # the bearish week mirrors: a Thursday that closed down
    hd = _thu_hist(False) + [daily(thu, 102.5, 103.0, 100.0, 100.5)]
    assert mk(fri, hd, p).dplan.sides["no_long_after_thu_noon"] == (-1,)
    assert "thu_cut" not in mk(thu, h, Params(**BASE)).dplan.info


def test_wed_week_extreme():
    wed = date(2026, 5, 20)
    base = weeks(date(2026, 5, 4), [(100.0, 101.0, 90.0, 95.0), (95.0, 103.0, 94.0, 102.0)])
    cur = [daily(date(2026, 5, 18), 102.0, 103.0, 101.5, 102.5), daily(date(2026, 5, 19), 102.5, 103.0, 101.8, 102.2)]         # neither low reaches the discount array
    bull = SimpleNamespace(i=3, top=98.0, bottom=96.0, kind="bull")
    p = Params(**BASE, wed_week_extreme=True)
    orig = D1._alive_zones
    D1._alive_zones = lambda hist, kind, end=None: [bull] if kind == "bull" else []
    try:
        c = mk(wed, base + cur, p)
        assert c.dplan.info["wed_ext"] == 1 and c.dplan.sides["wed_week_extreme"] == (-1,) and "wed_low" in D2.entry_tags(c, p, c.dplan, at(c, "10:00"))
        reached = base + [daily(date(2026, 5, 18), 102.0, 103.0, 97.0, 102.5), daily(date(2026, 5, 19), 102.5, 103.0, 101.8, 102.2)]       # Monday already touched it
        assert "wed_ext" not in mk(wed, reached, p).dplan.info
        assert "wed_ext" not in mk(wed, base + cur, Params(**BASE)).dplan.info
    finally:
        D1._alive_zones = orig


def test_wed_week_extreme_takes_the_nearest_array():
    wed = date(2026, 5, 20)
    base = weeks(date(2026, 5, 4), [(100.0, 101.0, 90.0, 95.0), (95.0, 103.0, 94.0, 102.0)])
    near_z = SimpleNamespace(i=3, top=100.0, bottom=99.0, kind="bull")                   # the nearest daily array under the Monday open (102)
    far_z = SimpleNamespace(i=2, top=96.0, bottom=94.0, kind="bull")
    p = Params(**BASE, wed_week_extreme=True)
    orig = D1._alive_zones
    D1._alive_zones = lambda hist, kind, end=None: [far_z, near_z] if kind == "bull" else []
    try:
        mon_hits_near = base + [daily(date(2026, 5, 18), 102.0, 103.0, 99.5, 102.5), daily(date(2026, 5, 19), 102.5, 103.0, 101.8, 102.2)]       # Monday reached the NEAR zone only
        assert "wed_ext" not in mk(wed, mon_hits_near, p).dplan.info
        none = base + [daily(date(2026, 5, 18), 102.0, 103.0, 101.5, 102.5), daily(date(2026, 5, 19), 102.5, 103.0, 101.8, 102.2)]
        assert mk(wed, none, p).dplan.info["wed_ext"] == 1
        tue_hits = base + [daily(date(2026, 5, 18), 102.0, 103.0, 101.5, 102.5), daily(date(2026, 5, 19), 102.5, 103.0, 99.9, 102.2)]            # Tuesday did
        assert "wed_ext" not in mk(wed, tue_hits, p).dplan.info
    finally:
        D1._alive_zones = orig


def test_expansion_strict_uses_the_avoidance_filters():
    h = history(D0, first=(120.0, 80.0), hi=102.0, lo=98.0)
    p = Params(**BASE, expansion_due=True, expansion_targets=(1.5,), expansion_strict=True)
    assert D2.strict_filters(first_date(lambda x: x in __import__("claude_hf.daytypes", fromlist=["JOBS"]).JOBS), p) == "nfp"
    assert D2.strict_filters(first_date(lambda x: C.is_holiday_eve(x) and x not in __import__("claude_hf.daytypes", fromlist=["JOBS"]).JOBS), p) == "holiday_eve"
    assert D2.strict_filters(first_date(lambda x: C.fomc_info(x)["fomc"]), p) == "fomc"
    assert D2.strict_filters(first_date(lambda x: C.fomc_info(x)["after"]), p) == "fomc"
    ok = first_date(lambda x: not D2.strict_filters(x, p))
    assert D2.strict_filters(ok, p) == ""


def test_tue_off_monday_ote_anchor():
    tue = date(2026, 5, 19)
    mon = daily(date(2026, 5, 18), 95.0, 100.0, 90.0, 99.0)                                                 # Monday's low 90, high 100: the OTE band 92.1-93.8
    h = history(tue)[:-1] + [mon]
    p = Params(**BASE, tue_off_monday="ote")
    c = mk(tue, h, p, base=93.0)
    assert c.dplan.info["off_ref"] == (100.0, 90.0)
    sl = c.sides_map[1]
    i = at(c, "10:00")
    o = order(sl, 93.0, 92.5, [99.0])
    assert D2.order_ok(c, sl, o, "AM", i, p) is None
    assert o["stop"] == 90.0 - p.tick and o["shares"] == int(100 * 0.5 / (93.0 - (90.0 - p.tick)))        # the stop sits below Monday's low, the size keeps the risk
    assert D2.order_ok(c, sl, order(sl, 95.0, 94.0, [99.0]), "AM", i, p) == "x_dw_tue_off_monday_ote"      # not in the OTE band
    assert D2.order_ok(c, sl, order(sl, 91.0, 90.5, [99.0]), "AM", i, p) == "x_dw_tue_off_monday_ote"
    ss = c.sides_map[-1]                                                                                    # the mirror: a short in 96.2-97.9 with the stop above Monday's high
    o2 = order(ss, ss.x(97.0), ss.x(97.5), [ss.x(91.0)])
    assert D2.order_ok(c, ss, o2, "AM", i, p) is None and o2["stop"] == ss.x(100.0 + p.tick)
    # the "filter" mode of the first pass is untouched
    q = Params(**BASE, tue_off_monday="filter")
    assert D2.order_ok(mk(tue, h, q, base=93.0), sl, order(sl, 95.0, 94.0, [99.0]), "AM", i, q) is None


# --- items 71 / 72 / 73 / 77: day gates ---------------------------------------------------------------------------------------------

def _ny_rows(low_at="03:00", low=97.0, high=100.2, base=100.0):
    spec = {low_at: (base, base + 0.1, low, base - 1.0), "05:00": (base - 1.0, base - 0.5, base - 1.2, base - 0.6)}
    return rows_5m({**spec, "09:55": (base, high, base - 0.2, base)}, "00:00", base=base)


class ArrConf(Conf):
    def __init__(self, arrays=()):
        super().__init__()
        self._a = list(arrays)

    def arrays_any(self, t, side, tfs):
        return list(self._a)


def test_ny_cont_gate():
    d = D0
    h = history(d)                                                                                          # ADR5 18
    p = Params(**BASE, ny_cont_gate=True)
    rows = _ny_rows()
    c = mk(d, h, p, rows=rows, start="00:00", bias_row={"draw": 1}, conf=ArrConf())
    i = at(c, "09:30")
    assert D2.side_ok(c, p, 1, "AM", i) is None                                                              # London posted the low, no array touched, the range is small
    assert D2.side_ok(c, p, -1, "AM", i) is None                                                             # the counter side is not this gate's business
    assert D2.side_ok(c, p, 1, "AM", at(c, "10:00")) is None                                                 # from 10:00 the gate is off
    late = mk(d, h, p, rows=_ny_rows(low_at="06:00"), start="00:00", bias_row={"draw": 1}, conf=ArrConf())
    assert D2.side_ok(late, p, 1, "AM", at(late, "09:30")) == "x_dw_ny_cont_extreme"                         # the low printed after 05:00
    arr = mk(d, h, p, rows=rows, start="00:00", bias_row={"draw": 1}, conf=ArrConf([(100.1, 105.0)]))
    assert D2.side_ok(arr, p, 1, "AM", at(arr, "09:30")) == "x_dw_ny_cont_array"                             # a 4h / D premium array was touched
    far = mk(d, h, p, rows=rows, start="00:00", bias_row={"draw": 1}, conf=ArrConf([(130.0, 140.0)]))
    assert D2.side_ok(far, p, 1, "AM", at(far, "09:30")) is None
    small = mk(d, history(d, first=(101.0, 99.0), hi=101.0, lo=99.0), p, rows=rows, start="00:00", bias_row={"draw": 1}, conf=ArrConf())
    assert D2.side_ok(small, p, 1, "AM", at(small, "09:30")) == "x_dw_ny_cont_adr"                           # the range so far (3.2) already exceeds ADR5 (2)
    assert D2.side_ok(c, Params(**BASE), 1, "AM", i) is None
    # the bearish mirror: the high printed in London
    hi_spec = {"03:00": (100.0, 103.0, 99.9, 101.0)}
    cb = mk(d, h, p, rows=rows_5m({**hi_spec, "09:55": (100.0, 100.2, 99.8, 100.0)}, "00:00"), start="00:00", bias_row={"draw": -1}, conf=ArrConf())
    assert D2.side_ok(cb, p, -1, "AM", at(cb, "09:30")) is None
    # the LOD + ADR5 rung is offered to a gated continuation entry only
    sl, ss = c.sides_map[1], c.sides_map[-1]
    assert D2.ny_cont_rung(c, p, i, sl) is True and D2.ny_cont_rung(c, p, i, ss) is False and D2.ny_cont_rung(c, p, at(c, "10:00"), sl) is False
    assert D2.ny_cont_rung(c, Params(**BASE), i, sl) is False and D2.ny_cont_rung(c, Params(**BASE, ny_cont_gate=True, adr_target=True), i, sl) is False


def test_adr_news_exempt():
    d10 = first_date(lambda x: 600 in C.release_times(x) and 510 not in C.release_times(x) and x.weekday() in (1, 2, 3) and not C.is_post_holiday(x) and not C.holiday_in_week(x))
    d08 = first_date(lambda x: C.release_times(x) == [510] and x.weekday() in (1, 2, 3) and not C.is_post_holiday(x) and not C.holiday_in_week(x))
    spec = {"02:00": (100.0, 107.2, 100.0, 107.0), "02:05": (107.0, 107.2, 91.0, 92.0)}                      # London covers 16.2 = 0.9 x ADR5 (18)
    rows = rows_5m({**spec, "09:55": (92.0, 92.2, 91.8, 92.0)}, "02:00", base=92.0)
    for exempt, d, want in ((False, d10, True), (True, d10, False), (True, d08, True)):
        p = Params(**BASE, london_adr_skip=0.8, adr_news_exempt=exempt)
        c = mk(d, history(d), p, rows=rows, start="02:00", base=100.0)
        i = at(c, "09:30")
        assert DW.london_adr_hit(c, p, i) is want, (exempt, d)
        assert ("x_dw_london_adr" == DW.gate(c, p, "AM", i, 570)) is want
        assert ("adr_filled_news" in c.dplan.tags) is (exempt and d == d10)
    p = Params(**BASE, london_adr_skip=0.8, adr_news_exempt=True)
    c = mk(d10, history(d10), p, rows=rows, start="02:00")
    DW.london_adr_hit(c, p, at(c, "09:30"))
    assert "adr_filled_news" in D2.entry_tags(c, p, c.dplan, at(c, "09:30"))


def test_london_low_guard():
    d = D0
    h = history(d)
    p = Params(**BASE, london_low_guard=True)
    lon = {"03:00": (100.0, 100.1, 97.0, 98.0), "03:05": (98.0, 100.2, 97.9, 100.0)}                         # the London low 97.0
    ny = {"09:30": (100.0, 100.5, 99.0, 99.5), "10:00": (99.5, 100.0, 98.0, 98.5), "10:05": (98.5, 98.6, 96.6, 96.8), "10:10": (96.8, 97.5, 96.7, 97.4)}
    c = mk(d, h, p, rows=rows_5m({**lon, **ny}, "00:00"), start="00:00", bias_row={"draw": 1})
    assert D2.london_ext(c, 1) == 97.0 and D2.london_ext(c, -1) == 100.2
    assert D2.gate(c, p, "PRE9", at(c, "09:00"), 540) == "x_dw_london_guard_wait"                           # entries from 10:00 only
    assert D2.gate(c, p, "AM", at(c, "09:30"), 570) == "x_dw_london_guard_wait"
    assert D2.gate(c, p, "AM", at(c, "10:00"), 600) is None                                                  # the low holds
    assert D2.gate(c, p, "AM", at(c, "10:05"), 605) == "x_dw_london_violated"                                # traded through by more than a tick
    assert D2.gate(c, p, "PM", at(c, "14:00"), 840) == "x_dw_london_violated"                                # ... for every later session
    assert D2.gate(c, p, "LON", at(c, "03:30"), 210) is None                                                 # London itself is not gated
    assert D2.side_ok(c, p, -1, "AM", at(c, "10:00")) == "x_dw_london_guard_side" and D2.side_ok(c, p, 1, "AM", at(c, "10:00")) is None
    touch = {**lon, "10:00": (99.5, 99.6, 96.9, 97.2)}                                                       # 96.9 is within a tick? no: under 97.0 by 0.1 < one tick (0.25)
    ct = mk(d, h, p, rows=rows_5m(touch, "00:00"), start="00:00", bias_row={"draw": 1})
    assert D2.gate(ct, p, "AM", at(ct, "10:00"), 600) is None
    nob = mk(d, h, p, rows=rows_5m({**lon, **ny}, "00:00"), start="00:00", bias_row={"draw": 0})
    assert D2.gate(nob, p, "AM", at(nob, "10:05"), 605) is None and D2.side_ok(nob, p, -1, "AM", at(nob, "10:05")) is None
    bear = mk(d, h, p, rows=rows_5m({"03:00": (100.0, 103.0, 99.9, 101.0), "10:05": (100.0, 103.4, 100.0, 103.3)}, "00:00"), start="00:00", bias_row={"draw": -1})
    assert D2.gate(bear, p, "AM", at(bear, "10:05"), 605) == "x_dw_london_violated"
    assert D2.gate(c, Params(**BASE), "AM", at(c, "10:05"), 605) is None


def test_london_filters_scope(monkeypatch):
    d = first_date(lambda x: C.fomc_info(x)["after"] and x.weekday() in (2, 3))
    p = Params(**BASE, london_filters=True)
    monkeypatch.setattr(N2, "whip_flag", lambda ctx, p, day: True)
    c = mk(d, history(d), p)
    assert D2.gate(c, p, "LON", at(c, "03:00"), 180) == "x_dw_london_filter"                               # the sb_london family / the 120-300 windows
    assert D2.gate(c, p, "AM", at(c, "10:00"), 600) is None and D2.gate(c, p, "PM", at(c, "14:00"), 840) is None       # the AM is not blocked
    assert D2.gate(c, Params(**BASE), "LON", at(c, "03:00"), 180) is None                                    # off
    monkeypatch.setattr(N2, "whip_flag", lambda ctx, p, day: False)
    quiet = mk(d, history(d), p)
    assert D2.gate(quiet, p, "LON", at(quiet, "03:00"), 180) is None
    monkeypatch.setattr(N2, "rel_count", lambda day, p: 2)
    multi = mk(D0, history(D0), p)
    assert D2.gate(multi, p, "LON", at(multi, "03:00"), 180) == "x_dw_london_filter" and D2.gate(multi, p, "AM", at(multi, "10:00"), 600) is None
    # the whole-day switches of the first pass stay as they were
    assert Params().neutral_skip is False and "three_day_rule" in Params.__dataclass_fields__


# --- item 206: the New York close (true day) -------------------------------------------------------------------------------------------

def test_ny_close_1500_is_the_1459_bar_close():
    d = D0
    n = 960
    rows = [(100.0 + k * 0.01, 100.0 + k * 0.01 + 0.05, 100.0 + k * 0.01 - 0.05, 100.0 + k * 0.01 + 0.02) for k in range(n)]
    df = frame(d, rows, 1, "00:00")
    ctx = S.DayCtx(df, d, history(d), 1)
    assert ctx.ny_close_1500 == pytest.approx(rows[899][3])                                                   # the bar 14:59-15:00
    assert ctx.ny_close_1500 != pytest.approx(rows[959][3])                                                   # not the 16:00 session close
    assert ctx.true_day_hl == (pytest.approx(max(r[1] for r in rows[:900])), pytest.approx(min(r[2] for r in rows[:900])))
    assert D2.true_day(ctx, ctx.start + 898) == (None, None) and D2.true_day(ctx, ctx.start + 899)[0] == pytest.approx(rows[899][3])      # nothing before the bar has closed
    c5 = mk(d, history(d), Params(**BASE))
    assert c5.ny_close_1500 == pytest.approx(float(c5.c[c5.start + 179]))                                       # 5m: the 14:55 bar
    assert S.DayCtx(day(A_ROWS, d=d, start="09:30")[:100], d, history(d), 5).ny_close_1500 is None             # a day cut before 15:00 has none


# --- item 207: PO3 small open wick -----------------------------------------------------------------------------------------------------------

def test_po3_adr_invalid():
    d = D0
    h = history(d, first=(101.0, 99.0), hi=101.0, lo=99.0)                                                    # ADR5 2
    p = Params(**BASE, po3_adr_invalid=True)
    dip = {"09:30": (100.0, 100.1, 97.5, 97.8), "09:35": (97.8, 99.0, 97.7, 98.9)}                            # the low is 2.5 under the midnight open (> ADR5 = 2)
    c = mk(d, h, p, rows=rows_5m(dip, "09:30"), bias_row={"react": 1, "draw": 1})
    i = at(c, "09:35")
    assert D2.side_ok(c, p, 1, "AM", i) == "x_dw_po3_adr_invalid" and D2.side_ok(c, p, -1, "AM", i) is None
    shallow = {"09:30": (100.0, 100.1, 98.5, 98.8), "09:35": (98.8, 99.5, 98.7, 99.4)}
    cs = mk(d, h, p, rows=rows_5m(shallow, "09:30"), bias_row={"react": 1, "draw": 1})
    assert D2.side_ok(cs, p, 1, "AM", at(cs, "09:35")) is None                                                # a small open wick
    cn = mk(d, h, p, rows=rows_5m(dip, "09:30"), bias_row={"react": 0, "draw": 1})
    assert D2.side_ok(cn, p, 1, "AM", i) is None                                                              # no daily reaction yesterday
    up = {"09:30": (100.0, 102.5, 99.9, 102.2), "09:35": (102.2, 102.4, 101.5, 101.8)}
    cb = mk(d, h, p, rows=rows_5m(up, "09:30"), bias_row={"react": -1, "draw": -1})
    assert D2.side_ok(cb, p, -1, "AM", at(cb, "09:35")) == "x_dw_po3_adr_invalid"
    assert D2.side_ok(c, Params(**BASE), 1, "AM", i) is None
    assert D2.side_ok(c, p, 1, "AM", at(c, "09:00")) is None                                                  # the table row is cut at 09:30


# --- levels_liquidity_targets 63 / 81 / 97 / 157 / 160 -------------------------------------------------------------------------------------------

def test_count_5pt_legs():
    assert D2.count_legs([4000, 4006, 4003, 4009, 4004, 4010], 1, 5.0) == 3
    assert D2.count_legs([4000, 4006, 4003, 4009, 4004, 4010], -1, 5.0) == 1
    hl = [(4003, 4001), (4001, 4000), (4004, 4001), (4006, 4003), (4005, 4004), (4004, 4003), (4007, 4004), (4009, 4006), (4008, 4005), (4006, 4004), (4008, 4006), (4010, 4007), (4009, 4005)]
    sw = D2.swing_series([x[0] for x in hl], [x[1] for x in hl], 1)
    assert sw == [4000, 4006, 4003, 4009, 4004, 4010] and D2.count_legs(sw, 1, 5.0) == 3


def test_tgif_reversal_flag_threshold():
    mon = date(2026, 5, 11)
    wk = [daily(mon, 100.0, 105.0, 99.0, 104.0), daily(mon + timedelta(days=1), 104.0, 112.0, 103.0, 110.0), daily(mon + timedelta(days=2), 110.0, 120.0, 109.0, 118.0),
          daily(mon + timedelta(days=3), 118.0, 119.5, 117.0, 119.0), daily(mon + timedelta(days=4), 119.0, 119.5, 113.0, 114.0)]          # Friday retraced 6.5 of the 20-point range from 119.5? from 120: 7 = 35 %
    nxt = mon + timedelta(days=7)
    assert D2.reversal_flag(wk, nxt, 0.30) is True and D2.reversal_flag(wk, nxt, 0.40) is False
    assert D2.reversal_flag(wk, nxt, 0.33) is True and D2.reversal_flag(wk, nxt, 0.35) is False                  # (120 - 113) / (120 - 99) = 33 %
    assert "wk_reversal_flag" in mk(nxt, wk, Params(**BASE, tgif_zone=True, tgif_reversal_pct=0.30)).dplan.tags
    assert "wk_reversal_flag" not in mk(nxt, wk, Params(**BASE, tgif_zone=True, tgif_reversal_pct=0.40)).dplan.tags
    assert "wk_reversal_flag" not in mk(nxt, wk, Params(**BASE)).dplan.tags                                      # reported only with the TGIF model on
    # the down week mirrors (the Friday rallies back into the range)
    dn = [daily(mon, 120.0, 121.0, 115.0, 116.0), daily(mon + timedelta(days=1), 116.0, 117.0, 108.0, 110.0), daily(mon + timedelta(days=2), 110.0, 111.0, 100.0, 102.0),
          daily(mon + timedelta(days=3), 102.0, 103.0, 100.5, 101.0), daily(mon + timedelta(days=4), 101.0, 107.0, 100.5, 106.0)]
    assert D2.reversal_flag(dn, nxt, 0.30) is True and D2.reversal_flag(dn, nxt, 0.40) is False
    # the engine's TGIF stand-down follows min(tgif_stand_down, tgif_reversal_pct)
    fri = mon + timedelta(days=4)
    thu_wk = wk[:4]
    for pct, want in ((0.30, True), (0.40, False)):
        p = Params(**BASE, tgif_zone=True, tgif_reversal_pct=pct)
        c = mk(fri, thu_wk, p, base=114.0)
        c.day_tags = "tgif_short"
        sd = c.sides_map[-1]
        info = T.tgif_info(c, sd, at(c, "10:00"), p, sd.x(113.0))
        assert info is not None and info["stand_down"] is want, (pct, info)


def test_tgif_reversal_pct_default_leaves_the_stand_down_alone():
    """tgif_reversal_pct=None (the default) does not touch tgif_stand_down: a stand-down above 0.40 stays; an explicit value IS the threshold."""
    mon = date(2026, 5, 11)
    wk = [daily(mon, 100.0, 105.0, 99.0, 104.0), daily(mon + timedelta(days=1), 104.0, 112.0, 103.0, 110.0), daily(mon + timedelta(days=2), 110.0, 120.0, 109.0, 118.0),
          daily(mon + timedelta(days=3), 118.0, 119.5, 117.0, 119.0)]
    fri = mon + timedelta(days=4)

    def stand(**kw):
        p = Params(**BASE, tgif_zone=True, **kw)
        c = mk(fri, wk, p, base=114.0)
        c.day_tags = "tgif_short"
        sd = c.sides_map[-1]
        return T.tgif_info(c, sd, at(c, "10:00"), p, sd.x(111.0))["stand_down"]            # (120 - 111) / 21 = 43 %
    assert stand() is True and stand(tgif_stand_down=0.50) is False and stand(tgif_stand_down=0.50, tgif_reversal_pct=0.40) is True
    # the direction of the week is the Mon-Thu close against the Monday open (no outer-quarter precondition): a Thursday close mid-range still flags
    mid = wk[:3] + [daily(mon + timedelta(days=3), 118.0, 119.5, 100.0, 108.0), daily(mon + timedelta(days=4), 108.0, 108.5, 100.0, 101.0)]
    assert D2.reversal_flag(mid, mon + timedelta(days=7), 0.40) is True


def test_tgif_fvg_ce_cap():
    fri = date(2026, 5, 15)
    # a daily SIBI 15500-15560 above the open (CE 15530): candle 1 low 15560, candle 3 high 15500
    h = [daily(date(2026, 5, 11), 15600.0, 15620.0, 15560.0, 15570.0), daily(date(2026, 5, 12), 15570.0, 15575.0, 15480.0, 15490.0), daily(date(2026, 5, 13), 15490.0, 15500.0, 15450.0, 15460.0),
         daily(date(2026, 5, 14), 15460.0, 15490.0, 15440.0, 15450.0)]
    p = Params(**BASE, tgif_fvg_cap=True)
    c = mk(fri, h, p, base=15525.0, dt={"tgif_short"})
    fv = c.dplan.info["tgif_fvg"]
    assert fv[:3] == (15560.0, 15500.0, 15530.0) and fv[3] == 15440.0 and "tgif_fvg_cap" in c.dplan.tags
    ss = c.sides_map[-1]
    i = at(c, "10:00")
    o = order(ss, ss.x(15525.0), ss.x(15527.0), [ss.x(15480.0)], kinds=["pool"], ext_i=c.start + at(c, "09:30") - c.start)
    assert D2.order_ok(c, ss, o, "AM", i, p) is None
    assert ss.x(o["stop"]) >= 15530.0 + p.tick - 1e-9 and o["shares"] < 100                                  # the stop above the CE, the size keeps the risk
    real = sorted(ss.x(v) for v in o["levels"])
    assert 15439.75 in real and 15500.0 in real                                                              # PDL - 1 tick and the daily FVG low join the ladder
    assert D2.order_ok(c, ss, order(ss, ss.x(15540.0), ss.x(15541.0), [ss.x(15480.0)]), "AM", i, p) == "x_dw_tgif_fvg_ce"       # above the CE: blocked
    assert D2.order_ok(c, c.sides_map[1], order(c.sides_map[1], 15525.0, 15520.0, [15530.0]), "AM", i, p) is None            # longs are not this rule's
    # two 5m closes above the CE cancel the shorts
    spec = {"09:30": (15525.0, 15532.0, 15524.0, 15531.0), "09:35": (15531.0, 15533.0, 15530.5, 15532.0)}
    c2 = mk(fri, h, p, rows=rows_5m(spec, "09:30", base=15525.0), base=15525.0, dt={"tgif_short"})
    assert D2.side_ok(c2, p, -1, "AM", at(c2, "09:30")) is None and D2.side_ok(c2, p, -1, "AM", at(c2, "09:35")) == "x_dw_tgif_fvg_closes"
    assert D2.side_ok(c2, p, 1, "AM", at(c2, "09:35")) is None
    # the two closes must be consecutive 5m closes
    spec3 = {"09:30": (15525.0, 15532.0, 15524.0, 15531.0), "09:35": (15531.0, 15531.5, 15526.0, 15527.0), "09:40": (15527.0, 15533.0, 15526.0, 15532.0)}
    c3 = mk(fri, h, p, rows=rows_5m(spec3, "09:30", base=15525.0), base=15525.0, dt={"tgif_short"})
    assert D2.side_ok(c3, p, -1, "AM", at(c3, "09:40")) is None
    # a stop tighter than the order's own is set to the spec value (CE of the longest wick of the last 5m swing + 1 tick); the size is kept
    o_t = order(ss, ss.x(15525.0), ss.x(15560.0), [ss.x(15480.0)], kinds=["pool"], ext_i=c.start + at(c, "09:30") - c.start)
    assert D2.order_ok(c, ss, o_t, "AM", i, p) is None and ss.x(o_t["stop"]) < 15560.0 and o_t["shares"] == 100 and o_t["t2"] == (o_t["levels"][1] if len(o_t["levels"]) > 1 else None)
    assert "tgif_fvg" not in mk(fri, h, Params(**BASE), base=15525.0, dt={"tgif_short"}).dplan.info
    assert "tgif_fvg" not in mk(fri, h, p, base=15525.0).dplan.info                                          # not a TGIF short Friday


def test_pdh_pdl_touch_stat():
    d = D0
    h = history(d)                                                                                          # PDH 108, PDL 90
    g = day([(100.0, 109.0, 99.0, 108.5)], d=d, start="09:30")
    s = D2.day_summary(g, h, Params(**BASE), None, 5)
    assert s["pdh_hit"] == 1 and s["pdl_hit"] == 0 and s["pd_reach_ok"] in (0, 1)
    s2 = D2.day_summary(day([(100.0, 101.0, 99.0, 100.5)], d=d, start="09:30"), h, Params(**BASE), None, 5)
    assert s2["pdh_hit"] == 0 and s2["pdl_hit"] == 0
    st = D2.summary_stats([s, s2])
    assert st["pd_touch_rate"] == 0.5 and st["days"] == 2
    ok = D2.day_summary(g, history(d, first=(110.0, 80.0), hi=110.0, lo=80.0), Params(**BASE), None, 5)
    assert ok["pd_reach_ok"] == 1                                                                           # ADR5 30 >= the distance to the nearer level (10)


def test_adr_close_zone_stat():
    assert D2.adr_close_zone(4000.0, 4041.0, 4000.0, 4031.0, 40.0) is True                                  # L 4000, ADR5 40, close 4031: in [4028, 4032]
    assert D2.adr_close_zone(4000.0, 4041.0, 4000.0, 4020.0, 40.0) is False
    assert D2.adr_close_zone(4000.0, 4041.0, 4000.0, 4040.0, 40.0) is True                                  # at H
    assert D2.adr_close_zone(4000.0, 4030.0, 4000.0, 4029.0, 40.0) is None                                  # ADR not met
    assert D2.adr_close_zone(4040.0, 4040.0, 3999.0, 4008.0, 40.0, -1) is True                              # the bearish mirror: H = high - ADR5 ... zone [H + 0.2R, H + 0.3R]
    s = D2.day_summary(day([(100.0, 100.5, 99.5, 100.0)], d=D0, start="09:30"), history(D0, hi=102.0, lo=98.0, first=(102.0, 98.0)), Params(**BASE), {"react": 1}, 5)
    assert "close_in_adr_zone" in s and "adr_met" in s and s["react"] == 1 and "po3_open_low_adr" in s


# --- the position loop -----------------------------------------------------------------------------------------------------------------------

def _pos(fill_i, stop, left=10, n=10, **kw):
    return dict(fill_i=fill_i, stop=stop, left=left, n=n, **kw)


def test_friday_trail():
    fri, thu = date(2026, 5, 15), date(2026, 5, 14)
    lows = [100.0, 99.5, 100.5, 101.0, 100.8, 101.5, 102.0, 101.7, 102.4]
    spec = {f"15:{5 * k:02d}": (l + 0.4, l + 1.0 + k * 0.1, l, l + 0.8) for k, l in enumerate(lows)}
    rows = rows_5m(spec, "15:00", base=100.0)
    p = Params(**BASE, fri_trail_from=900)
    for d, trails in ((fri, True), (thu, False)):
        c = mk(d, history(d), p, rows=rows, start="15:00", base=100.0)
        sd = c.sides_map[1]
        k0 = at(c, "15:00")
        pos = _pos(k0, 90.0)
        seen = []
        for i in range(k0, k0 + len(lows)):
            D2.fri_trail(c, sd, pos, SimpleNamespace(), i, p)
            seen.append(pos["stop"])
        if trails:
            assert seen[-1] > 90.0 and seen == sorted(seen)                                                   # only ever ratchets up
            piv = [q.price for q in L.pivots(sd.h[:k0 + len(lows)], sd.l[:k0 + len(lows)], 1)[1] if q.i > k0]
            assert seen[-1] == pytest.approx(piv[-1] - p.tick)                                                # under the latest pivot low
            assert D2.fri_trail(c, sd, _pos(k0, 90.0, left=0), SimpleNamespace(), k0 + 8, p) is None
        else:
            assert seen == [90.0] * len(lows)                                                                 # Thursday: nothing moves
    # before the start minute, or switched off: nothing
    c = mk(fri, history(fri), p, rows=rows, start="15:00", base=100.0)
    sd = c.sides_map[1]
    pos = _pos(at(c, "15:00"), 90.0)
    D2.fri_trail(c, sd, pos, SimpleNamespace(), at(c, "15:20"), replace(p, fri_trail_from=930))
    D2.fri_trail(c, sd, pos, SimpleNamespace(), at(c, "15:40"), Params(**BASE))
    assert pos["stop"] == 90.0


def test_adr_met_runner():
    d = D0
    h = history(d, hi=130.0, lo=100.0, first=(130.0, 100.0))                                                  # ADR5 30
    p = Params(**BASE, adr_met_runner=True, runner_frac=0.2)
    spec32 = {"09:25": (100.0, 132.5, 100.0, 132.0)}
    spec20 = {"09:25": (100.0, 120.5, 100.0, 120.0)}
    for spec, ok in ((spec32, True), (spec20, False)):
        c = mk(d, h, p, rows=rows_5m({**spec, "11:55": (132.0, 133.0, 131.0, 132.0)}, "09:25", base=100.0), start="09:25", base=100.0)
        sd = c.sides_map[1]
        i = at(c, "11:55")
        tr = SimpleNamespace(exits=[])
        pos = _pos(at(c, "09:40"), 95.0, left=2, n=10)
        assert D2.am_exit_for(c, sd, pos, tr, i - 6, "ts", p, 720, 132.0) == 720                              # before the AM exit: nothing decided
        x = D2.am_exit_for(c, sd, pos, tr, i, "ts", p, 720, 132.0)
        assert x == (840 if ok else 720), ok                                                                   # ADR5 covered by 09:30 (32 >= 30) keeps the runner to 14:00
        if ok:
            assert D2.am_exit_for(c, sd, pos, tr, i + 6, "ts", p, 720, 132.0) == 840 and tr.exits == []
    # fewer than 75 % banked at 12:00: the normal AM exit
    c = mk(d, h, p, rows=rows_5m({**spec32, "11:55": (132.0, 133.0, 131.0, 132.0)}, "09:25", base=100.0), start="09:25", base=100.0)
    sd, i = c.sides_map[1], at(c, "11:55")
    assert D2.am_exit_for(c, sd, _pos(at(c, "09:40"), 95.0, left=5, n=10), SimpleNamespace(exits=[]), i, "ts", p, 720, 132.0) == 720
    # 76 % banked: the excess over the runner share is closed at the 12:00 AM exit, the runner stays
    tr = SimpleNamespace(exits=[])
    pos = _pos(at(c, "09:40"), 95.0, left=24, n=100)
    assert D2.am_exit_for(c, sd, pos, tr, i, "ts", p, 720, 132.0) == 840 and pos["left"] == 20 and tr.exits == [("ts", sd.x(132.0), 4, "am_exit")]
    assert D2.am_exit_for(c, sd, _pos(at(c, "09:40"), 95.0), SimpleNamespace(exits=[]), i, "ts", Params(**BASE), 720, 132.0) == 720        # off
    # a short mirrors
    cs = mk(d, h, p, rows=rows_5m({"09:25": (100.0, 100.0, 67.5, 68.0), "11:55": (68.0, 69.0, 67.0, 68.0)}, "09:25", base=100.0), start="09:25", base=100.0)
    ss = cs.sides_map[-1]
    assert D2.am_exit_for(cs, ss, _pos(at(cs, "09:40"), 95.0, left=2, n=10), SimpleNamespace(exits=[]), at(cs, "11:55"), "ts", p, 720, ss.x(68.0)) == 840


def test_adr_close_runner_exit():
    d = D0
    h = history(d, hi=140.0, lo=100.0, first=(140.0, 100.0))                                                  # ADR5 40
    p = Params(**BASE, adr_close_runner=True)
    spec = {"09:30": (100.0, 141.0, 99.9, 140.5), "09:35": (140.5, 140.7, 138.0, 139.0), "09:40": (139.0, 139.5, 131.0, 131.5)}
    c = mk(d, h, p, rows=rows_5m(spec, "09:30", base=100.0), base=100.0)
    sd = c.sides_map[1]
    a = c.dplan.info["adr5_prev"]
    lo = float(sd.l[c.start:].min())
    H, px = lo + a, lo + a - 0.2 * a
    pos = _pos(at(c, "09:30"), 95.0, left=4, n=10, t1_done=True)
    tr = SimpleNamespace(exits=[])
    D2.adr_close_exit(c, sd, pos, tr, at(c, "09:30"), "t0", p)
    assert pos["left"] == 4                                                                                   # traded H but the close is not back under it yet
    D2.adr_close_exit(c, sd, pos, tr, at(c, "09:35"), "t1", p)
    assert pos["left"] == 4 and pos["adr_close"]["turn_j"] == at(c, "09:35")                                                     # a close back below H
    D2.adr_close_exit(c, sd, pos, tr, at(c, "09:40"), "t2", p)
    assert pos["left"] == 0 and tr.exits == [("t2", px, 4, "adr_close")]
    # H moves with the running low: the level that traded (140) is the one the close is judged against, not today's lower H
    spec2 = {"09:30": (100.0, 141.0, 99.9, 140.5), "09:35": (140.5, 141.0, 90.0, 135.0)}
    c2 = mk(d, h, p, rows=rows_5m(spec2, "09:30", base=100.0), base=100.0)
    pos3 = _pos(at(c2, "09:30"), 95.0, left=4, n=10, t1_done=True)
    D2.adr_close_exit(c2, c2.sides_map[1], pos3, SimpleNamespace(exits=[]), at(c2, "09:30"), "a", p)
    D2.adr_close_exit(c2, c2.sides_map[1], pos3, SimpleNamespace(exits=[]), at(c2, "09:35"), "b", p)
    assert pos3["adr_close"]["H"] == pytest.approx(float(c2.l[c2.start:at(c2, "09:30") + 1].min()) + DW._adr(c2, p)) and pos3["adr_close"]["turn_j"] == at(c2, "09:35")                    # 135 < 139.9, though above 90 + ADR5
    # no first partial: a runner only
    pos2 = _pos(at(c, "09:30"), 95.0, left=4, n=10)
    D2.adr_close_exit(c, sd, pos2, SimpleNamespace(exits=[]), at(c, "09:40"), "t2", p)
    assert pos2["left"] == 4
    D2.adr_close_exit(c, sd, _pos(at(c, "09:30"), 95.0, t1_done=True), SimpleNamespace(exits=[]), at(c, "09:40"), "t2", Params(**BASE))


def test_adr_contracted_tag():
    d = D0
    wide = [daily(date(2026, 3, 2) + timedelta(days=k), 100.0, 100.0 + 12.0 + (k % 3), 100.0, 100.0) for k in range(0, 1)]
    ds, x = [], date(2026, 2, 2)
    for k in range(66):
        while not C.is_trading_day(x):
            x += timedelta(days=1)
        r = 20.0 if k < 60 else 3.0                                                                          # a contraction after 60 wide sessions
        ds.append(daily(x, 100.0, 100.0 + r, 100.0, 100.0))
        x += timedelta(days=1)
    assert D2.adr_contracted(ds) is True and D2.adr_contracted(ds[:60]) is False and D2.adr_contracted(ds[:10]) is False
    p = Params(**BASE, adr_contracted_tag=True)
    assert "adr_contracted" in mk(d, ds, p).dplan.tags and "adr_contracted" not in mk(d, ds, Params(**BASE)).dplan.tags
    assert "adr_contracted" not in mk(d, ds[:60], p).dplan.tags


# --- the weekly profile STUDIES (study_week.py) -----------------------------------------------------------------------------------------------

def dd(o, h, l, c, hi_min=600, lo_min=600, rel=(), **kw):
    return dict(o=o, h=h, l=l, c=c, hi_min=hi_min, lo_min=lo_min, rel=list(rel), **kw)


def test_study_week_template_fields():
    # a bullish week: the Mon-Wed impulse, a Tue retrace into the discount array (97-99), Thu / Fri above the Mon-Wed high
    days = [dd(100.0, 104.0, 99.5, 103.0), dd(103.0, 103.5, 98.0, 99.0), dd(99.0, 106.0, 98.9, 105.0), dd(105.0, 109.0, 104.0, 108.0), dd(108.0, 110.0, 107.0, 109.0)]
    r = SW.classify_week(days, 1, (97.0, 99.0), 10.0)
    assert r["impulse"] == pytest.approx(6.0) and r["retrace_into_array"] == 1 and r["expansion"] == 1
    flat = [dd(100.0, 104.0, 99.5, 103.0), dd(103.0, 104.0, 102.5, 103.5), dd(103.5, 105.0, 103.0, 104.0), dd(104.0, 104.5, 103.5, 104.2), dd(104.2, 104.8, 103.9, 104.0)]
    r2 = SW.classify_week(flat, 1, (97.0, 99.0), 10.0)
    assert r2["retrace_into_array"] == 0 and r2["expansion"] == 0
    # the bearish mirror (prices mirrored around 200)
    mir = [dd(200 - d_["o"], 200 - d_["l"], 200 - d_["h"], 200 - d_["c"]) for d_ in days]
    rm = SW.classify_week(mir, -1, (101.0, 103.0), 10.0)
    assert rm["impulse"] == pytest.approx(6.0) and rm["retrace_into_array"] == 1 and rm["expansion"] == 1


def test_study_week_tue_low():
    arr = (96.0, 98.0)
    days = [dd(100.0, 102.0, 99.0, 101.0, lo_min=600), dd(101.0, 101.5, 97.5, 100.5, hi_min=200, lo_min=630, lon_l=98.5, ny_l=97.5, lon_h=101.0, ny_h=101.5),
            dd(100.5, 104.0, 100.0, 103.0), dd(103.0, 108.0, 102.0, 107.0, hi_min=620), dd(107.0, 107.5, 105.0, 106.0)]
    r = SW.classify_week(days, 1, arr, 10.0)
    assert r["tue_ext"] == 1 and r["tue_ny_undercut_london"] == 1 and r["ext_high_by_thu720"] == 1       # the low is Tuesday, NY undercut London, the high printed Thursday before noon
    assert r["bull_low_mon_wed_high_by_thu720"] == 1
    late_high = [days[0], days[1], days[2], dd(103.0, 108.0, 102.0, 107.0, hi_min=800), days[4]]
    assert SW.classify_week(late_high, 1, arr, 10.0)["ext_high_by_thu720"] == 0
    # Monday's low already at the array, or Tuesday not the low: not a Tuesday low
    mon_low = [dd(100.0, 102.0, 97.9, 101.0)] + days[1:]
    assert SW.classify_week(mon_low, 1, arr, 10.0)["tue_ext"] == 0
    not_low = [days[0], days[1], dd(100.5, 104.0, 96.5, 103.0), days[3], days[4]]
    assert SW.classify_week(not_low, 1, arr, 10.0)["tue_ext"] == 0
    # the bearish week: Tuesday forms the high, the low prints Thursday in the NY session
    bear = [dd(100.0, 101.0, 98.0, 99.0), dd(99.0, 103.0, 98.5, 100.0, hi_min=630), dd(100.0, 101.0, 97.0, 98.0), dd(98.0, 98.5, 90.0, 91.0, lo_min=560), dd(91.0, 93.0, 90.5, 92.0)]
    rb = SW.classify_week(bear, -1, (102.0, 105.0), 10.0)
    assert rb["bear_high_tue_low_thu_ny"] == 1 and rb["tue_ext"] == 1


def test_study_week_wed_low():
    arr = (96.0, 98.0)
    days = [dd(100.0, 102.0, 99.0, 101.0), dd(101.0, 103.0, 99.5, 102.0), dd(102.0, 102.5, 97.5, 101.0), dd(101.0, 106.0, 100.5, 105.0), dd(105.0, 108.0, 104.0, 107.0)]
    r = SW.classify_week(days, 1, arr, 10.0)
    assert r["wed_ext"] == 1 and r["tue_ext"] == 0
    reached = [days[0], dd(101.0, 103.0, 97.8, 102.0), days[2], days[3], days[4]]                      # Tuesday already reached the array
    assert SW.classify_week(reached, 1, arr, 10.0)["wed_ext"] == 0
    thu_low = [days[0], days[1], dd(102.0, 102.5, 99.6, 101.0), dd(101.0, 106.0, 97.0, 105.0), days[4]]  # Wednesday does not reach it
    assert SW.classify_week(thu_low, 1, arr, 10.0)["wed_ext"] == 0
    mir = [dd(200 - d_["o"], 200 - d_["l"], 200 - d_["h"], 200 - d_["c"]) for d_ in days]
    assert SW.classify_week(mir, -1, (102.0, 104.0), 10.0)["wed_ext"] == 1


def test_study_week_midweek_rally():
    arr = (96.0, 99.0)
    days = [dd(100.0, 103.0, 99.5, 102.5), dd(102.5, 104.0, 98.5, 99.5), dd(99.5, 103.0, 98.0, 102.0, rel=[510]), dd(102.0, 108.0, 101.0, 107.0), dd(107.0, 111.0, 106.0, 110.0)]
    r = SW.classify_week(days, 1, arr, 10.0)
    assert r["midweek_rally"] == 1 and r["midweek_expansion"] == 1                                          # Monday up, the Tue-Wed low inside the array, a Wednesday release, a higher close
    no_rel = [days[0], days[1], dd(99.5, 103.0, 98.0, 102.0), days[3], days[4]]
    assert SW.classify_week(no_rel, 1, arr, 10.0)["midweek_rally"] == 0
    mon_dn = [dd(100.0, 103.0, 99.5, 99.8)] + days[1:]
    assert SW.classify_week(mon_dn, 1, arr, 10.0)["midweek_rally"] == 0
    tab = pd.DataFrame([r, SW.classify_week(no_rel, 1, arr, 10.0)])
    s = SW.summarize_profiles(tab)
    assert s["midweek_rally"]["n"] == 1 and s["midweek_rally_expansion_rate"] == 1.0


def test_study_week_wed_reversal():
    arr = (96.0, 99.0)
    days = [dd(100.0, 101.0, 99.0, 100.5), dd(100.5, 101.5, 99.5, 100.0), dd(100.0, 100.5, 96.5, 100.2), dd(100.2, 104.0, 100.0, 103.0), dd(103.0, 106.0, 102.0, 105.0)]
    r = SW.classify_week(days, 1, arr, 10.0)
    assert r["wed_weekly_reversal"] == 1                                                                    # Mon-Tue range 2.5 <= ADR5, Wednesday under it into the array, closes in the top third, the week's low
    weak = [days[0], days[1], dd(100.0, 100.5, 96.5, 97.5), days[3], days[4]]                               # the close is in the bottom of the range
    assert SW.classify_week(weak, 1, arr, 10.0)["wed_weekly_reversal"] == 0
    wide = [dd(100.0, 112.0, 99.0, 100.5), days[1], days[2], days[3], days[4]]
    assert SW.classify_week(wide, 1, arr, 10.0)["wed_weekly_reversal"] == 0


def test_study_week_first_driver():
    days = [dd(100.0, 101.0, 99.0, 100.0), dd(100.0, 102.0, 98.0, 101.0, lo_min=600, rel=[510]), dd(101.0, 104.0, 100.0, 103.0, rel=[600]), dd(103.0, 105.0, 102.0, 104.0), dd(104.0, 106.0, 103.0, 105.0)]
    r = SW.first_driver(days, 10.0, 1)
    assert r["first_driver_day"] == 1 and r["first_driver_min"] == 510 and r["against_ext_in_driver"] == 1      # the week's low is Tuesday, 600 is within 510..630
    assert r["pre_driver_range_adr"] == pytest.approx(0.2)
    days2 = [days[0], dd(100.0, 102.0, 98.0, 101.0, lo_min=800, rel=[510]), days[2], days[3], days[4]]
    assert SW.first_driver(days2, 10.0, 1)["against_ext_in_driver"] == 0
    assert SW.first_driver([dd(1, 2, 0, 1)] * 5, 10.0, 1)["first_driver_day"] is None


def test_pbr_return_stat():
    days = [dd(100.0, 103.0, 99.0, 101.0), dd(101.0, 101.5, 88.0, 90.0), dd(90.0, 92.0, 89.0, 91.0), dd(91.0, 100.0, 90.0, 99.0), dd(99.0, 99.5, 97.0, 98.0)]
    r = SW.classify_week(days, 1, None, 10.0)
    assert r["pbr_week"] == 1 and r["pbr_return"] == 1 and r["pbr_exceed"] == 0                             # Thursday re-enters Monday's range (>= 99), never above its high (103)
    over = days[:3] + [dd(91.0, 104.0, 90.0, 103.0), days[4]]
    r2 = SW.classify_week(over, 1, None, 10.0)
    assert r2["pbr_return"] == 1 and r2["pbr_exceed"] == 1
    none = days[:3] + [dd(91.0, 95.0, 90.0, 94.0), dd(94.0, 96.0, 93.0, 95.0)]
    assert SW.classify_week(none, 1, None, 10.0)["pbr_return"] == 0
    big_mon = [dd(100.0, 110.0, 99.0, 101.0)] + days[1:]
    assert SW.classify_week(big_mon, 1, None, 10.0)["pbr_week"] == 0
    s = SW.summarize_profiles(pd.DataFrame([r, r2]))
    assert s["pbr_weeks"] == 2 and s["pbr_return_rate"] == 1.0 and s["pbr_exceed_rate"] == 0.5


def test_study_week_tue_thu_excursion():
    days = [dd(100.0, 104.0, 100.0, 103.0), dd(103.0, 103.5, 97.5, 102.0), dd(102.0, 106.0, 101.0, 105.0), dd(105.0, 112.0, 104.0, 110.0, h1100=111.0, l1100=104.0), dd(110.0, 111.0, 108.0, 109.0)]
    r = SW.classify_week(days, 1, None, 10.0)
    # Monday's range 100-104; the 62 % level is 104 - 0.62 * 4 = 101.52: Tuesday (low 97.5) fills it; the best high to Thursday 11:00 is 111
    assert r["tue_thu_entry_day"] == 1 and r["tue_thu_excursion_adr"] == pytest.approx((111.0 - 101.52) / 10.0, abs=1e-3)
    wed = [days[0], dd(103.0, 103.5, 102.8, 103.2), dd(103.2, 106.0, 101.0, 105.0), days[3], days[4]]       # Tuesday never retraces: Wednesday off Tuesday's low
    r2 = SW.classify_week(wed, 1, None, 10.0)
    assert r2["tue_thu_entry_day"] == 2


def test_profile_table_on_bars():
    """The classifier runs on all-hours bars (a synthetic window): one row per week, the columns exist, nothing raises."""
    x, _y = B.synthetic(start="2026-03-02", end="2026-05-08", tf=5, seed=2)
    tab = SW.profile_table(x)
    assert len(tab) >= 8 and {"bias", "week", "high_day", "low_day", "first_driver_day"} <= set(tab.columns)
    s = SW.summarize_profiles(tab)
    assert s["weeks"] == len(tab)
    assert SW.weekly_tone([(100, 105, 95, 102), (102, 103, 90, 93)]) == -1 and SW.weekly_tone([]) == 0
    assert SW.nearest_array([(100, 101, 99, 100), (100, 105, 100, 104), (104, 108, 103.5, 107)], 1, 110.0) == (101.0, 103.5)


# --- no look-ahead: full run vs truncated runs --------------------------------------------------------------------------------------------------
# (1) synthetic multi-day windows with the Silver Bullet and Ma Deuce on, executed-path counters asserted where a path fires;
# (2) hand-made days; (3) ES windows (skipped when the data is absent).

W_D2 = {"W0": ("2026-03-02", "2026-04-17", 5), "W1": ("2026-04-27", "2026-05-13", 7), "W2": ("2026-04-06", "2026-04-24", 3)}
LA_D2 = {   # name -> (window, switches); NEED = at least one of the dwc2.HITS counters must have run
    "week": ("W0", dict(days_mode="mon_wed", late_week_fallback=True, no_long_after_thu_noon=True, mw_break_bias=True, thu_fri_break="side", mw_carry=True, thu_reversal_trade=True,
                        wed_week_extreme=True, monday_mode="big_into_array", mon_big_frac=0.05, tue_off_monday="ote", tgif_zone=True, tgif_reversal_pct=0.30)),
    "day": ("W2", dict(consolidation_mode="range_trade", expansion_strict=True, expansion_due=True, expansion_targets=(1.5,), expansion_mode="full", trend_recipe="side", trend_side_rule=True,
                       ny_cont_gate=True, adr_news_exempt=True, london_adr_skip=0.5, london_low_guard=True, po3_adr_invalid=True, london_filters=True, adr_contracted_tag=True)),
    "exits": ("W1", dict(fri_trail_from=840, adr_met_runner=True, adr_runner_until=900, adr_close_runner=True, fri_delivered_stop=True, eve_draw=True, fri_pool_choice=True,
                         tgif_model=True, tgif_fvg_cap=True, runner_frac=0.2)),
    "scalp": ("W2", dict(consolidation_mode="scalp", sd_intraday="tag")),
}
NEED_D2 = {   # name -> one group per switch ("a|b" = either counter): EVERY group must have run in the window (the rest of the switches are covered by the CAUSAL cases)
    "week": ("late_week_open|late_week_blocked", "thu_noon_block", "thu_rev_setup", "wed_week_extreme", "tue_ote_pass|tue_ote_reject", "mon_big_wait|mon_big_reject", "wk_reversal_flag"),
    "day": ("consol_mode_range_trade", "expansion_candidate", "expansion_strict_static_off", "expansion_full"),
    "exits": ("fri_pool_long|fri_pool_short", "fri_delivered_block", "wk_reversal_flag"),
    "scalp": ("consol_mode_scalp",)}
_RUNS = {}


def _syn_d2(wname, **kw):
    key = (wname, tuple(sorted(kw.items(), key=lambda kv: kv[0])))
    if key not in _RUNS:
        a, b, seed = W_D2[wname]
        x, y = B.synthetic(start=a, end=b, tf=5, seed=seed)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            _RUNS[key] = (x, y, B.run(x, 5, "ES", Params(**SYN, sb_model=True, ma_deuce=True, **kw), y))
    return _RUNS[key]


@pytest.mark.parametrize("name", list(LA_D2))
def test_look_ahead_synthetic_dwc2(name):
    wname, kw = LA_D2[name]
    D2.HITS.clear()
    x, y, full = _syn_d2(wname, **kw)
    assert len(full) >= 1, f"{name}: no trades in window {wname}"
    p = Params(**SYN, sb_model=True, ma_deuce=True, **kw)
    _no_look_ahead(x, 5, "ES", p, COLS, every=max(1, len(full) // 3), partner=y, exits=True, min_trades=1)
    missing = [g for g in NEED_D2[name] if not any(D2.HITS.get(h) for h in g.split("|"))]
    assert not missing, f"{name}: these switch paths did not run: {missing} (ran: {sorted(D2.HITS)})"


def test_look_ahead_sets_fire_something():
    """The sets change the engine on their windows (not inert): the trades differ from the switches-off run or a counter ran."""
    CMP = ["entry_time", "entry", "shares", "session", "lv_tags", "net", "stop"]
    D2.HITS.clear()
    fired = {}
    for name, (wname, kw) in LA_D2.items():
        _, _, base = _syn_d2(wname)
        _, _, t = _syn_d2(wname, **kw)
        same = len(t) == len(base) and (not len(t) or t[CMP].reset_index(drop=True).equals(base[CMP].reset_index(drop=True)))
        fired[name] = not same
    assert any(fired.values()) or D2.HITS, fired


def test_day_summary_is_reported_by_the_backtest():
    x, y, t = _syn_d2("W2")
    ds = t.attrs.get("day_summary")
    assert ds and {"pdh_hit", "pdl_hit", "pd_reach_ok", "date"} <= set(ds[0]) and any("adr_met" in r for r in ds)
    rep = B.report(t)
    assert rep["day_summary"]["days"] == len(ds) and "pd_touch_rate" in rep["day_summary"]
    assert study.day_summary_report(t)["days"] == len(ds)


def test_look_ahead_hand_made_days():
    D2.HITS.clear()
    fri = date(2026, 5, 15)
    _day_la(D0, A_ROWS, "09:50", ("10:05", "10:10", "10:30"), min_trades=0, london_low_guard=True, ny_cont_gate=True, expansion_strict=True, expansion_due=True, expansion_targets=(1.5,),
            trend_side_rule=True, trend_recipe="side", po3_adr_invalid=True, consolidation_mode="range_trade")
    _day_la(D0, A_ROWS, "09:50", ("10:05", "10:30"), min_trades=0, adr_met_runner=True, adr_close_runner=True, london_filters=True, adr_news_exempt=True, london_adr_skip=0.1)
    _day_la(fri, A_ROWS, "09:50", ("10:05", "10:30"), min_trades=0, fri_trail_from=600, fri_delivered_stop=True, eve_draw=True, fri_pool_choice=True)


# --- no look-ahead per path: the same function at the same closed bar on the full day, a day whose later bars are poisoned, and a day cut right after the bar ---------------------
# (the full-run comparisons above cannot reach every dwc2 path in a small window; each path listed here is asserted to RUN, and to give the same answer in the three variants)

def mk3(d, hist, p, probe, variant, rows=(), start="09:30", base=100.0, bias_row=None, conf=None, spike=False, dt=None):
    df = day(list(rows), d=d, start=start, spike=spike, base=base)
    ts = pd.Timestamp(f"{d} {probe}", tz=B.NY)
    if variant == "cut":
        df = df[df.index <= ts]
    elif variant == "poison":
        df = df.copy()
        m = df.index > ts
        for col, v in (("open", base + 60.0), ("high", base + 300.0), ("low", base - 300.0), ("close", base - 60.0)):
            df.loc[m, col] = v
    ctx = S.DayCtx(df, d, hist, 5)
    ctx.hist = hist
    ctx.lock = {}
    ctx.eth = None
    ctx.eve = None
    ctx.bias_row = bias_row
    ctx.conf = conf
    ctx.daily_all = None
    mg = p.min_fvg_pts * p.es_pt
    ctx.sides_map = {1: S.Side(1, ctx.o, ctx.h, ctx.l, ctx.c, p.pivot_n, mg), -1: S.Side(-1, ctx.o, ctx.h, ctx.l, ctx.c, p.pivot_n, mg)}
    ctx.dplan = DW.plan(ctx, hist, p, None, None, dt)
    return ctx


def _causal(case, mp, need):
    """Run `case(variant, mp)` -> a comparable result for the three variants; the full run must bump every counter in `need`."""
    D2.HITS.clear()
    full = case("full", mp)
    ran = set(D2.HITS)
    assert set(need) <= ran, f"paths that did not run: {sorted(set(need) - ran)} (ran: {sorted(ran)})"
    assert case("poison", mp) == full, "a later bar changed the decision at the probe bar"
    assert case("cut", mp) == full, "cutting the day after the probe bar changed the decision"


def _case_trend(v, mp):
    mp.setattr(DW, "news_class", lambda x: "high")
    bull = SimpleNamespace(i=10, top=95.0, bottom=93.0, kind="bull")
    mp.setattr(D1, "_alive_zones", lambda hist, kind, end=None: [bull] if kind == "bull" else [])
    p = Params(**BASE, trend_recipe="side", trend_side_rule=True)
    h = history(D0, n=25)
    out = []
    for br in ({"draw": 1}, {"draw": -1}):
        c = mk3(D0, h, p, "10:00", v, bias_row=br)
        out.append((D2.side_ok(c, p, 1, "AM", at(c, "09:00")), D2.side_ok(c, p, 1, "AM", at(c, "10:00")), c.dplan.info.get("trend_side")))
    return out


def _case_adr_news(v, mp):
    d10 = first_date(lambda x: 600 in C.release_times(x) and 510 not in C.release_times(x) and x.weekday() in (1, 2, 3) and not C.is_post_holiday(x) and not C.holiday_in_week(x))
    spec = {"02:00": (100.0, 107.2, 100.0, 107.0), "02:05": (107.0, 107.2, 91.0, 92.0)}
    rows = rows_5m({**spec, "09:55": (92.0, 92.2, 91.8, 92.0)}, "02:00", base=92.0)
    p = Params(**BASE, london_adr_skip=0.8, adr_news_exempt=True)
    c = mk3(d10, history(d10), p, "09:30", v, rows=rows, start="02:00")
    i = at(c, "09:30")
    return (DW.gate(c, p, "AM", i, 570), sorted(D2.entry_tags(c, p, c.dplan, i)), "adr_filled_news" in c.dplan.tags)


def _case_london_filters(v, mp):
    d = first_date(lambda x: C.fomc_info(x)["after"] and x.weekday() in (2, 3))
    p = Params(**BASE, london_filters=True)
    mp.setattr(N2, "whip_flag", lambda ctx, p, day: True)
    c = mk3(d, history(d), p, "03:00", v)
    r1 = D2.gate(c, p, "LON", at(c, "03:00"), 180)
    mp.setattr(N2, "whip_flag", lambda ctx, p, day: False)
    mp.setattr(N2, "rel_count", lambda day, p: 2)
    c2 = mk3(D0, history(D0), p, "03:00", v)
    return (r1, D2.gate(c2, p, "LON", at(c2, "03:00"), 180))


def _case_tgif_cap(v, mp):
    fri = date(2026, 5, 15)
    h = [daily(date(2026, 5, 11), 15600.0, 15620.0, 15560.0, 15570.0), daily(date(2026, 5, 12), 15570.0, 15575.0, 15480.0, 15490.0), daily(date(2026, 5, 13), 15490.0, 15500.0, 15450.0, 15460.0),
         daily(date(2026, 5, 14), 15460.0, 15490.0, 15440.0, 15450.0)]
    p = Params(**BASE, tgif_fvg_cap=True)
    spec = {"09:30": (15525.0, 15532.0, 15524.0, 15531.0), "09:35": (15531.0, 15533.0, 15530.5, 15532.0), "09:40": (15532.0, 15540.0, 15520.0, 15521.0)}
    c = mk3(fri, h, p, "09:35", v, rows=rows_5m(spec, "09:30", base=15525.0), base=15525.0, dt={"tgif_short"})
    ss = c.sides_map[-1]
    o = order(ss, ss.x(15525.0), ss.x(15527.0), [ss.x(15480.0)], kinds=["pool"], ext_i=at(c, "09:30"))
    r = D2.order_ok(c, ss, o, "AM", at(c, "09:30"), p)
    return (D2.side_ok(c, p, -1, "AM", at(c, "09:30")), D2.side_ok(c, p, -1, "AM", at(c, "09:35")), r, round(o["stop"], 6), o["shares"], tuple(o["levels"]))


def _case_mon_big(v, mp):
    d = date(2026, 5, 18)
    p = Params(**BASE, monday_mode="big_into_array", mon_big_frac=0.1)
    rows = rows_5m({"09:30": (100.0, 100.4, 99.6, 100.1), "09:35": (100.1, 100.5, 99.9, 100.2), "09:45": (100.0, 130.0, 70.0, 100.0)}, "09:30")
    c = mk3(d, _bear_weeks(), p, "09:35", v, spike=True, conf=Conf(z={"D": zone(-1, 102.0, 106.0)}), rows=rows)
    i = at(c, "09:35")
    return (D2.gate(c, p, "AM", at(c, "09:00"), 540), D2.gate(c, p, "AM", i, 575), D2.side_ok(c, p, 1, "AM", i), D2.size_mult(c, p), sorted(D2.entry_tags(c, p, c.dplan, i)))


def _case_am_exit(v, mp):
    d = D0
    h = history(d, hi=130.0, lo=100.0, first=(130.0, 100.0))
    p = Params(**BASE, adr_met_runner=True, runner_frac=0.2)
    rows = rows_5m({"09:25": (100.0, 132.5, 100.0, 132.0), "11:55": (132.0, 133.0, 131.0, 132.0), "12:05": (132.0, 300.0, 5.0, 100.0)}, "09:25", base=100.0)
    c = mk3(d, h, p, "11:55", v, rows=rows, start="09:25", base=100.0)
    sd = c.sides_map[1]
    i = at(c, "11:55")
    pos = _pos(at(c, "09:40"), 95.0, left=24, n=100)
    tr = SimpleNamespace(exits=[])
    x = D2.am_exit_for(c, sd, pos, tr, i, "ts", p, 720, 132.0)
    return (x, tuple(map(tuple, tr.exits)), pos["left"])


def _case_adr_close(v, mp):
    d = D0
    h = history(d, hi=140.0, lo=100.0, first=(140.0, 100.0))
    p = Params(**BASE, adr_close_runner=True)
    spec = {"09:30": (100.0, 141.0, 99.9, 140.5), "09:35": (140.5, 140.7, 138.0, 139.0), "09:40": (139.0, 139.5, 131.0, 131.5), "09:45": (131.5, 135.0, 120.0, 125.0)}
    c = mk3(d, h, p, "09:40", v, rows=rows_5m(spec, "09:30", base=100.0))
    sd = c.sides_map[1]
    pos = _pos(at(c, "09:30"), 95.0, left=4, n=10, t1_done=True)
    tr = SimpleNamespace(exits=[])
    for hh in ("09:30", "09:35", "09:40"):
        D2.adr_close_exit(c, sd, pos, tr, at(c, hh), "t" + hh, p)
    return (tuple(map(tuple, tr.exits)), pos["left"])


def _case_thu_rev(v, mp):
    d = date(2026, 5, 21)
    mp.setattr(D2, "thu_release", lambda x: True)
    p = Params(**BASE, thu_reversal_tag=True, thu_reversal_trade=True)
    spec = {"09:30": (102.5, 102.6, 101.5, 101.7), "09:35": (101.7, 102.8, 101.6, 102.7), "09:40": (102.7, 130.0, 70.0, 100.0)}
    c = mk3(d, _thu_hist(True), p, "09:35", v, rows=rows_5m(spec, "09:30", base=102.5), base=102.5)
    sl = c.sides_map[1]
    i = at(c, "09:35")
    return (D2.order_ok(c, sl, order(sl, 102.5, 101.5, [104.0], swept="mon_wed"), "AM", i, p), D2.side_ok(c, p, -1, "AM", i), sorted(D2.entry_tags(c, p, c.dplan, i)))


def _case_range_cap(v, mp):
    mp.setattr(DW, "_consol_predictors", lambda ctx, d, p, hist, eth: ["no_report"])
    p = Params(**BASE, consolidation_mode="range_trade")
    c = mk3(D0, history(D0), p, "10:00", v, rows=rows_5m({"09:30": (100.0, 100.4, 99.6, 100.1), "10:05": (100.0, 130.0, 70.0, 100.0)}, "09:30"))
    sl = c.sides_map[1]
    o = order(sl, 100.0, 99.0, [105.0, 110.0, 112.0], entry_kind="turtle_soup", runner=True)
    r = D2.order_ok(c, sl, o, "AM", at(c, "10:00"), p)
    return (r, tuple(o["levels"]), tuple(o["level_kinds"]))


def _case_mw_break(v, mp):
    d = date(2026, 5, 21)
    p = Params(**BASE, thu_fri_break="side", mw_break_bias=True, mw_carry=True)
    hd = _thu_hist(False)
    c = mk3(d, hd, p, "09:30", v, rows=rows_5m({"09:30": (103.0, 105.0, 102.9, 104.9), "09:35": (104.9, 140.0, 60.0, 100.0)}, "09:30", base=103.0), base=103.0)
    i = at(c, "09:30")
    h2 = weeks(date(2026, 5, 4), [(100.0, 101.0, 90.0, 95.0), (95.0, 103.0, 94.0, 102.0), (102.0, 102.5, 92.0, 93.0)])
    c2 = mk3(date(2026, 5, 25), h2, p, "09:30", v)
    c3 = mk3(d, hd, p, "09:30", v, rows=rows_5m({"09:30": (102.5, 102.6, 100.5, 100.6), "09:35": (100.6, 140.0, 60.0, 100.0)}, "09:30", base=102.5), base=102.5)          # the break DOWN is with the bearish week
    return (DW.side_ok(c, p, -1, "AM", i), DW.side_ok(c, p, 1, "AM", i), DW.side_ok(c3, p, 1, "AM", i), c2.dplan.info.get("wk_bias"))


def _case_ny_cont(v, mp):
    p = Params(**BASE, ny_cont_gate=True)
    spec = {"03:00": (100.0, 100.1, 97.0, 99.0), "05:00": (99.0, 99.5, 98.8, 99.4), "09:30": (100.0, 100.2, 99.8, 100.0), "09:55": (100.0, 150.0, 60.0, 100.0)}
    c = mk3(D0, history(D0), p, "09:30", v, rows=rows_5m(spec, "00:00"), start="00:00", bias_row={"draw": 1}, conf=ArrConf())
    i = at(c, "09:30")
    sl, ss = c.sides_map[1], c.sides_map[-1]
    return (D2.side_ok(c, p, 1, "AM", i), D2.ny_cont_rung(c, p, i, sl), D2.ny_cont_rung(c, p, i, ss))


def _case_expansion(v, mp):
    p = Params(**BASE, expansion_due=True, expansion_targets=(1.5,), expansion_strict=True, expansion_mode="full")
    d = first_date(lambda x: x.weekday() in (1, 2) and 510 in C.release_times(x) and DW.news_class(x) in ("high", "medium") and not D2.strict_filters(x, p) and not C.is_post_holiday(x) and not C.holiday_in_week(x))
    h = history(d, first=(120.0, 80.0), hi=102.0, lo=98.0)
    spec = {"09:30": (100.0, 100.1, 95.0, 95.2), "09:35": (95.2, 99.0, 95.0, 98.9), "09:40": (98.9, 100.5, 98.8, 100.4), "09:45": (100.4, 101.0, 100.3, 100.9), "10:00": (100.0, 160.0, 40.0, 100.0)}
    c = mk3(d, h, p, "09:45", v, rows=rows_5m(spec, "09:30"), bias_row={"draw": 1})
    i = at(c, "09:45")
    sd = c.sides_map[1]
    return (D2.expansion_live(c, p, i), DW.expansion_levels(c, sd, i, p), sorted(D2.entry_tags(c, p, c.dplan, i)), D2.day_params(p, c.dplan).po3_runner)


CAUSAL = {
    "trend_side_rule": (_case_trend, ("trend_side_rule", "trend_wait", "trend_draw_mismatch")),
    "adr_news_exempt": (_case_adr_news, ("adr_news_exempt",)),
    "london_filters": (_case_london_filters, ("london_filter_whipsaw", "london_filter_rel2plus")),
    "tgif_fvg_cap": (_case_tgif_cap, ("tgif_fvg_cap_plan", "tgif_fvg_cancel", "tgif_fvg_pass")),
    "monday_big": (_case_mon_big, ("mon_big_wait", "mon_big_size")),
    "adr_met_runner": (_case_am_exit, ("adr_runner_on",)),
    "adr_close_runner": (_case_adr_close, ("adr_close_exit",)),
    "thu_reversal": (_case_thu_rev, ("thu_rev_setup", "thu_rev_pass", "thu_rev_side")),
    "consol_range": (_case_range_cap, ("consol_mode_range_trade", "consol_range_cap")),
    "mw_break_mw_carry": (_case_mw_break, ("mw_break_bias", "mw_carry")),
    "ny_cont": (_case_ny_cont, ()),
    "expansion": (_case_expansion, ("expansion_strict_rungs", "expansion_full", "expansion_candidate")),
}


@pytest.mark.parametrize("name", list(CAUSAL))
def test_dwc2_paths_are_causal(name, monkeypatch):
    case, need = CAUSAL[name]
    _causal(case, monkeypatch, need)


def test_single_exit_friday_and_every_switch_is_covered():
    fri = first_date(lambda x: x.weekday() == 4 and not C.nfp_date(x), start=date(2026, 6, 1))
    p = Params(**BASE, fri_pool_choice=True, runner_frac=0.3, po3_runner=True)
    D2.HITS.clear()
    cp = mk(fri, history(fri), p, dt={"tgif_short"})
    q = D2.day_params(p, cp.dplan)
    assert q.runner_frac == 0.0 and D2.HITS["fri_single_exit"] == 1
    covered = {"consolidation_mode", "consol_range_days", "expansion_strict", "expansion_judas_adr", "expansion_mode", "trend_side_rule", "fri_delivered_stop", "fri_pool_choice", "mon_big_frac",
               "mw_break_bias", "mw_carry", "thu_reversal_tag", "thu_reversal_trade", "wed_week_extreme", "days_mode", "late_week_fallback", "no_long_after_thu_noon", "ny_cont_gate",
               "adr_news_exempt", "london_low_guard", "london_filters", "po3_adr_invalid", "tgif_reversal_pct", "tgif_fvg_cap", "adr_close_runner", "fri_trail_from", "adr_met_runner",
               "adr_runner_until", "adr_contracted_tag"}          # = the synthetic / ES full-run groups plus the CAUSAL cases above
    assert set(NEW_FIELDS) <= covered


ES_D2 = {   # name -> switches; one 5-week ES window (2022-09-12 .. 2022-10-14), every group produces trades there and bumps its counters
    "A": dict(days_mode="mon_wed", late_week_fallback=True, no_long_after_thu_noon=True, mw_break_bias=True, thu_fri_break="side", mw_carry=True, wed_week_extreme=True, tue_off_monday="ote",
              expansion_strict=True, expansion_due=True, expansion_targets=(1.5,), expansion_mode="full", adr_contracted_tag=True),
    "B": dict(monday_mode="big_into_array", mon_big_frac=0.2, thu_reversal_trade=True, trend_recipe="side", trend_side_rule=True, adr_news_exempt=True, london_adr_skip=0.6,
              po3_adr_invalid=True, ny_cont_gate=True),
    "C": dict(fri_trail_from=840, adr_met_runner=True, adr_runner_until=900, adr_close_runner=True, fri_delivered_stop=True, eve_draw=True, fri_pool_choice=True, tgif_model=True,
              tgif_fvg_cap=True, tgif_reversal_pct=0.30, runner_frac=0.2),
    "D": dict(london_low_guard=True, london_filters=True),
    "E": dict(consolidation_mode="fade_with_htf"),
    "F": dict(consolidation_mode="range_trade"),
    "G": dict(consolidation_mode="scalp"),
}
NEED_ES = {"A": ("late_week_open", "expansion_strict_rungs"), "B": ("ny_cont_extreme", "po3_adr_invalid", "thu_rev_side"), "C": ("fri_trail", "wk_reversal_flag"),
           "D": ("london_violated", "london_guard_wait"), "E": ("consol_mode_fade_with_htf",), "F": ("consol_mode_range_trade",), "G": ("consol_mode_scalp",)}


@pytest.mark.skipif(not ES, reason="no ES data")
@pytest.mark.parametrize("name", list(ES_D2))
def test_look_ahead_es_dwc2(name):
    es = B.load("ES", 5, source="databento")
    df = es[(es.index >= pd.Timestamp("2022-09-12", tz=B.NY)) & (es.index < pd.Timestamp("2022-10-14", tz=B.NY))]
    if not len(df):
        pytest.skip("the ES file does not cover the window")
    meta = B.load_meta("ES", 5)
    p = Params(**FUT, htf_resist_cap=False, draw_lock="off", leg_pd=0, min_draw_pts=0, use_bias=False, htf_bias="combo", ob_entry="post_mss", sb_model=True, ma_deuce=True,
               fomc_observe="defer", **ES_D2[name])
    D2.HITS.clear()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        n = len(B.run(df, 5, "ES", p, meta=meta))
    if n < 1:
        pytest.skip("no trades in the window with this data file")
    _no_look_ahead(df, 5, "ES", p, COLS, every=max(1, n // 3), meta=meta, exits=True, min_trades=1)
    assert any(D2.HITS.get(h) for h in NEED_ES[name]), f"{name}: none of these paths ran: {NEED_ES[name]} (ran: {sorted(D2.HITS)})"
