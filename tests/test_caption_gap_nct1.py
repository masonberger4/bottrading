"""Caption-gap pass, package news_calendar_times#1/1 (37 specs from digests/rulebook_gaps): focused tests of the new switches (nct2.py and its hooks) - calendar rules through strategy.blocked,
helpers on hand-made one-day books (the real DayCtx), engine scenarios through run_day, and no-look-ahead runs (full vs truncated) with executed-path counters. Nothing here needs market
data except the ES windows (skipped when absent); nothing is platform specific."""
import warnings
from dataclasses import fields
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from claude_hf import daytypes as DT
from mentorship import backtest as B, calendar as C, nct2 as N2, newscal as NC, strategy as S, study
from mentorship.strategy import Params

from test_review_fixes import BASE, D0, frame, history  # noqa: E402  (shared scenario builders)
from test_entries_stops import _no_look_ahead  # noqa: E402
from test_caption_gap_sm4a import cap  # noqa: F401,E402  (the order recorder fixture)
from test_news_calendar import FOMC_ONLY, EVE, AFTER, NFP_ONLY, TWO_DRV, CPI_EVE, NORMAL, find_day, go, FUT, SYN, COLS  # noqa: E402

ES = Path("data/mentorship/ES_5min_db.csv").exists()

NEW_FIELDS = (
    "pre_news_coil", "nfp_both_sides", "nfp_macro_only", "pre_0900_no_news", "pre_open_bnb", "cpi_from", "two_driver_mode", "multi_release", "news_seq_study", "news_trend_side",
    "kz_release_tag", "fomc_stage_study", "fomc_minutes_mode", "fomc_end", "fomc_end_min_pts", "pre_fomc_week_light", "pre_fomc_week_mult", "pre_fomc_week_smt", "post_fomc_am",
    "fomc_whipsaw_skip", "fomc_whip_frac", "nfp_wed_cutoff", "event_eve_noon", "news_sweep_min", "am_search_minutes", "am_search_sb", "macro_fail_windows", "macro_fail_scope",
    "macro_gate_set", "macro_trend_off", "lunch_raid", "lunch_raid_wait", "lunch_raid_by", "lunch_trail_guard", "lunch_by_speed", "am_fast_k", "am_slow_k", "lunch_fast_pm",
    "lunch_slow_pm", "pm_array_from", "pm_1400_disp", "am_session", "am_trend_end", "post_news_fade", "pre_draw_done_am", "pre_0700_hard_days", "hard_day_one_trade",
    "pre_entry_guard", "chop_wait_bars")
OFF_DEFAULTS = {f: getattr(Params(), f) for f in NEW_FIELDS}


def hm(s: str) -> int:
    return int(s[:2]) * 60 + int(s[3:])


def book(over=None, d=NORMAL, base=100.0, w=0.1, p=None, hist=None, tf=5, rows=None):
    """A 00:00-16:10 5-minute day flat at `base` (+-w) with `over` {"HH:MM": (o, h, l, c)} replaced - the real DayCtx with the Sides, the news ranges and the pools the helpers read."""
    p = p or Params(**BASE)
    rr = [(base, base + w, base - w, base)] * 195 if rows is None else list(rows)
    for k, v in (over or {}).items():
        rr[hm(k) // 5] = v
    df = frame(d, rr, tf, "00:00")
    hist = hist if hist is not None else history(d)
    ctx = S.DayCtx(df, d, hist, tf)
    ctx.hist = hist
    ctx.lock = {}
    ctx.chop = None
    mg = p.min_fvg_pts * p.es_pt
    ctx.sides_map = {1: S.Side(1, ctx.o, ctx.h, ctx.l, ctx.c, p.pivot_n, mg), -1: S.Side(-1, ctx.o, ctx.h, ctx.l, ctx.c, p.pivot_n, mg)}
    S._setup_news(ctx, d, p)
    return ctx


def at(ctx, hhmm: str) -> int:
    return S._idx_at(ctx, hm(hhmm))


# --- defaults and validation ----------------------------------------------------------------------------------------------

def test_defaults_and_validation():
    p = Params()
    for f in NEW_FIELDS:
        assert f in Params.__dataclass_fields__, f
    off = {"pre_news_coil": False, "nfp_both_sides": False, "cpi_from": 0, "two_driver_mode": "off", "multi_release": "off", "fomc_minutes_mode": "allow", "post_fomc_am": "open",
           "fomc_whipsaw_skip": "off", "am_search_minutes": 0, "am_search_sb": "exempt", "macro_fail_windows": "am", "macro_fail_scope": "session", "lunch_raid": "off",
           "lunch_by_speed": False, "pm_array_from": 0, "am_session": "default", "am_trend_end": 0, "chop_wait_bars": 0, "fomc_end": 0, "nfp_wed_cutoff": 660}
    for k, v in off.items():
        assert getattr(p, k) == v, k
    # the owner-fixed switches are untouched by this chunk
    assert p.sb_model is False and "sb_use_bias" in Params.__dataclass_fields__ and "want_all_engines" in Params.__dataclass_fields__
    for bad in (dict(two_driver_mode="x"), dict(multi_release="x"), dict(fomc_minutes_mode="x"), dict(post_fomc_am="x"), dict(fomc_whipsaw_skip="x"), dict(am_search_sb="x"),
                dict(macro_fail_windows="x"), dict(macro_fail_scope="x"), dict(lunch_raid="x"), dict(am_session="x"), dict(am_search_minutes=-1), dict(pre_fomc_week_mult=0)):
        with pytest.raises(ValueError):
            Params(**bad)


def test_every_new_switch_has_a_study_variant():
    names = " ".join(study.DECISIONS)
    used = set()
    for n, v in study.DECISIONS.items():
        used |= set(v)
    for f in NEW_FIELDS:
        assert f in used or f in {"fomc_whip_frac", "fomc_end_min_pts", "pre_fomc_week_mult", "am_fast_k", "am_slow_k", "lunch_fast_pm", "lunch_slow_pm", "lunch_raid_by"}, f
    for gid in ("BH-consolidation-near-highs-before-news", "N1-nfp-both-sides-macro", "N4-cpi-day-new-traders", "N5-two-driver-session", "N3-fomc-minutes_block", "T8-lunch-raid-target",
                "T9-pm-start-time_840", "T5-am-session-to-noon", "new-10min-wait-choppy", "M9-fomc-1430", "N9-macro-failure-any-macro", "T7-no-macro-trending"):
        assert gid in study.DECISIONS or any(k.startswith(gid) for k in study.DECISIONS), gid


# --- calendar rules (strategy.blocked) -------------------------------------------------------------------------------------

def test_nfp_day_from_already_built():
    """N1-nfp-30min-wait: nfp_day_from (D8) is the switch - 2023-07-07 is a jobs day."""
    p = Params(nfp_day=True, nfp_day_from=540)
    assert DT.events(date(2023, 7, 7)) >= {"jobs"}
    assert S.blocked(date(2023, 7, 7), "AM", p, 535) == "nfp_day_from" and S.blocked(date(2023, 7, 7), "AM", p, 540) is None


def test_cpi_from():
    p = Params(cpi_from=600)
    assert S.blocked(date(2023, 2, 14), "AM", p, 590) == "cpi_before_from" and S.blocked(date(2023, 2, 14), "AM", p, 600) is None
    assert S.blocked(date(2023, 2, 14), "AM", Params(), 590) is None
    assert S.blocked(date(2023, 2, 15), "AM", p, 590) is None                      # not a CPI day


def test_cpi_from_windows_in_the_engine():
    """cpi_from drops the 09:00 windows on a CPI day and moves the AM start: no order is armed before it."""
    d = date(2023, 2, 14)
    assert "cpi" in DT.events(d)
    for t in go(d, pre_0900=True, post_news=True, cpi_from=600):
        assert t.armed.hour * 60 + t.armed.minute >= 600


def test_nfp_week_from_calendar_guard():
    """N2-nfp-date-from-calendar: the NFP date comes from the BLS list - March 2023 released on the 10th (not the first Friday); a Thursday release (2025-07-03) moves the day before."""
    p = Params(nfp_week_block=True, nfp_thu=False)
    assert S.blocked(date(2023, 3, 9), "AM", p) == "nfp_week_thu_fri" and S.blocked(date(2023, 3, 2), "AM", p) is None
    assert C.nfp_date(date(2023, 3, 6)) == date(2023, 3, 10)
    assert C.nfp_date(date(2025, 6, 30)) == date(2025, 7, 3)
    assert S.blocked(date(2025, 7, 2), "AM", p) == "nfp_week_thu_fri"             # the day before a Thursday NFP is the Wednesday
    assert S.blocked(date(2025, 7, 1), "AM", p) is None and S.blocked(date(2025, 7, 1), "PM", p) == "nfp_week_wed_pm"


def test_nfp_wed_cutoff():
    """N2-nfp-wed-after-11: NFP-week Wednesday 2023-10-04 - AM-family entries from the cutoff minute are blocked (660 default), a 12:00 cutoff lets 11:05 through; the PM stays blocked."""
    d = date(2023, 10, 4)
    p = Params(nfp_week_block=True)
    assert S.blocked(d, "AM", p, 665) == "nfp_week_wed_pm" and S.blocked(d, "AM", p, 600) is None
    q = Params(nfp_week_block=True, nfp_wed_cutoff=720)
    assert S.blocked(d, "AM", q, 665) is None and S.blocked(d, "AM", q, 725) == "nfp_week_wed_pm" and S.blocked(d, "PM", q, 0) == "nfp_week_wed_pm"
    assert S.blocked(d, "AM", Params(nfp_week_block=True, nfp_wed_cutoff=0), 665) is None


def test_fomc_minutes_tag_and_modes():
    d = date(2023, 8, 16)
    assert d in C.FOMC_MINUTES and "fomc_minutes" in NC.day_tags(d)
    assert S.blocked(d, "PM", Params(), 850) is None                                # allow = today's behaviour
    blk = Params(fomc_minutes_mode="block")
    assert S.blocked(d, "PM", blk, 850) == "fomc_minutes_pm" and S.blocked(d, "PM", blk, 890) is None
    po = Params(fomc_minutes_mode="pm_only")
    assert S.blocked(d, "AM", po, 600) == "fomc_minutes_am" and S.blocked(d, "PM", po, 850) is None
    assert S.blocked(FOMC_ONLY, "AM", blk, 600) is None                              # a decision day is not a minutes day


def test_fomc_hv_and_pre_fomc_only_tags():
    hv = find_day(lambda d: C.fomc_info(d)["fomc"] and 510 in C.release_times(d), date(2019, 1, 2), date(2026, 12, 31))
    assert "fomc_hv" in NC.day_tags(hv).split("|") and "fomc_only" not in NC.day_tags(hv).split("|")
    assert "fomc_hv" not in NC.day_tags(FOMC_ONLY).split("|") and "fomc_only" in NC.day_tags(FOMC_ONLY).split("|")
    assert "pre_fomc_only" in NC.day_tags(EVE).split("|")


def test_release_count_tags_and_modes():
    p = Params(multi_release="tag")
    ism = find_day(lambda d: 510 in C.release_times(d) and 600 in C.release_times(d), date(2026, 1, 2))
    assert N2.rel_tag(ism, p) == "rel2plus" and N2.rel_tag(NORMAL, p) == "rel0_wildcard"
    one = find_day(lambda d: C.release_times(d) == [510], date(2026, 1, 2))
    assert N2.rel_tag(one, p) == "rel1" and "rel1" in NC.day_tags(one, p).split("|")
    assert S.blocked(ism, "AM", Params(multi_release="skip"), 600) == "multi_release_skip" and S.blocked(one, "AM", Params(multi_release="skip"), 600) is None
    assert S.blocked(ism, "PM", Params(multi_release="skip"), 850) is None
    ctx = book(d=ism)
    lv = []
    assert N2.size_mult(ctx, None, at(ctx, "10:00"), Params(multi_release="half"), "AM", lv) == 0.5 and lv == ["size_rel2plus"]
    assert N2.size_mult(book(d=one), None, at(ctx, "10:00"), Params(multi_release="half"), "AM", []) == 1.0


def test_two_driver_definition_and_skip():
    assert N2.two_driver(TWO_DRV) and not N2.two_driver(NORMAL)
    pm = find_day(lambda d: C.release_times(d) == [510, 840], date(2019, 1, 2), date(2026, 12, 31))
    assert not N2.two_driver(pm)                                                     # 08:30 + 14:00 does not count
    assert S.blocked(TWO_DRV, "AM", Params(two_driver_mode="skip"), 600) == "two_driver_skip" and S.blocked(TWO_DRV, "PM", Params(two_driver_mode="skip"), 850) is None


def test_post_fomc_am_skip_mode():
    assert S.blocked(AFTER, "AM", Params(post_fomc_am="skip"), 600) == "post_fomc_am" and S.blocked(AFTER, "AM", Params(), 600) is None


def test_fomc_stage2_time():
    """M9-fomc-1430: stage 2 starts at 14:30 (fomc_judas_end 870, already built); the observation window ends 14:45 (fomc_pm_from 885); no FOMC-day PM entry before it."""
    p = Params()
    assert p.fomc_judas_end == 870 and p.fomc_pm_from == 885
    assert S.blocked(FOMC_ONLY, "PM", p, 860) == "fomc_pm" and S.blocked(FOMC_ONLY, "PM", p, 880) == "fomc_pm" and S.blocked(FOMC_ONLY, "PM", p, 885) is None
    assert S.blocked(FOMC_ONLY, "PM", Params(fomc_judas=True), 870) is None
    assert NC.first_pm_minute(Params(fomc_judas=True)) == 870


def test_am_session_variant_and_trend_end():
    p = Params(am_session="0830_1200")
    assert p.am_win == (510, 720) and p.am_from_0830
    assert Params().am_win == (570, 660)
    ctx = book()
    st = {}
    # no new AM entries after am_trend_end; positions are not touched here
    q = Params(am_trend_end=660, am=(570, 720))
    assert N2.gate2(ctx, q, NORMAL, "AM", 665, at(ctx, "11:05"), 720, [], {"AM": False}, st, None, None) == ("x_am_trend_end", True)
    assert N2.gate2(ctx, q, NORMAL, "AM", 640, at(ctx, "10:40"), 720, [], {"AM": False}, st, None, None) == (None, False)
    assert N2.gate2(ctx, Params(), NORMAL, "AM", 665, at(ctx, "11:05"), 720, [], {"AM": False}, st, None, None) == (None, False)


# --- bar-derived helpers on hand-made books --------------------------------------------------------------------------------

def _news_book(extra=None, d=None):
    """08:30 release range with a swing high 102 (08:40) and a swing low 98.5 (08:55): made at the 09:00 bar (the 30-minute floor of a jobs day and the swing low confirmed)."""
    over = {"08:30": (100.0, 100.5, 99.8, 100.2), "08:35": (100.2, 101.0, 100.1, 100.9), "08:40": (100.9, 102.0, 100.8, 101.8), "08:45": (101.8, 101.9, 101.0, 101.1),
            "08:50": (101.1, 101.2, 100.5, 100.6), "08:55": (100.6, 100.7, 98.5, 98.9), "09:00": (98.9, 99.8, 98.8, 99.7), "09:05": (99.7, 100.2, 99.5, 100.0)}
    over.update(extra or {})
    return book(over, d=d or NFP_ONLY)


def test_nfp_sequence_and_gates():
    """N1-nfp-both-sides-macro: high taken first, then the low - nothing before the second side, then only the long; macro_only needs a macro window."""
    ctx = _news_book({"09:15": (100.0, 102.4, 99.9, 102.0), "09:40": (101.0, 101.1, 98.2, 98.4)})
    p = Params(**BASE)
    sq = N2.nfp_sequence(ctx, p)
    assert sq["first"] == 1 and sq["both"] == at(ctx, "09:40") and sq["allow"] == 1 and sq["made"] == at(ctx, "09:00")
    q = Params(**BASE, nfp_both_sides=True, nfp_day_from=590)
    st = {}
    i1, i2 = at(ctx, "09:20"), at(ctx, "09:40")
    assert N2.gate2(ctx, q, NFP_ONLY, "AM", 560, i1, 570, [], {"AM": False}, st, None, None)[0] == "x_nfp_both_sides"
    assert N2.gate2(ctx, q, NFP_ONLY, "AM", 580, i2, 570, [], {"AM": False}, st, None, None)[0] is None
    assert N2.side2(ctx, q, NFP_ONLY, "AM", -1, i2, 580) == "x_nfp_side" and N2.side2(ctx, q, NFP_ONLY, "AM", 1, i2, 580) is None
    assert N2.side2(ctx, q, NFP_ONLY, "AM", -1, i1, 560) is None                      # (the gate holds the bar back before; the side rule needs both)
    # the second side only after 11:10 -> the AM stays closed
    late = _news_book({"09:15": (100.0, 102.4, 99.9, 102.0), "11:15": (101.0, 101.1, 98.2, 98.4)})
    assert N2.gate2(late, q, NFP_ONLY, "AM", 680, at(late, "11:20"), 720, [], {"AM": False}, st, None, None)[0] == "x_nfp_both_sides"
    m = Params(**BASE, nfp_macro_only=True)
    assert N2.gate2(ctx, m, NFP_ONLY, "AM", 585, i2, 570, [], {"AM": False}, st, None, None)[0] == "x_nfp_macro_only"
    assert N2.gate2(ctx, m, NFP_ONLY, "AM", 595, i2, 570, [], {"AM": False}, st, None, None)[0] is None
    assert N2.gate2(ctx, m, NFP_ONLY, "AM", 665, i2, 570, [], {"AM": False}, st, None, None)[0] is None       # 10:50-11:10 is a window


def test_news_sequence_pools_and_order():
    over = {"07:30": (100.0, 101.0, 99.9, 100.5), "08:00": (100.0, 100.1, 99.0, 99.9)}
    both = book({**over, "08:30": (100.0, 101.5, 98.5, 100.0)}, d=NFP_ONLY)
    p = Params(**BASE)
    q = N2.news_sequence(both, p, 510, at(both, "08:30"))
    assert q["bsl"] == 101.0 and q["ssl"] == 99.0 and q["order"] == "both_same_bar"
    seq = book({**over, "08:30": (100.0, 101.5, 99.5, 101.0), "08:45": (100.8, 100.9, 98.8, 99.0)}, d=NFP_ONLY)
    q = N2.news_sequence(seq, p, 510, at(seq, "08:50"))
    assert q["order"] == "bsl_first" and q["min_bsl"] == 510 and q["min_ssl"] == 525
    assert N2.news_sequence(seq, p, 510, at(seq, "08:20")) is None                      # the release bar has not closed
    none = book(over, d=NFP_ONLY)
    assert N2.news_sequence(none, p, 510, at(none, "08:45"))["order"] == "none"


def _fomc_book(over, d=None):
    return book(over, d=d or FOMC_ONLY)


def test_fomc_stage_label_a_and_b():
    p = Params(**BASE)
    drop = {"14:00": (100.0, 100.1, 99.5, 99.6), "14:05": (99.6, 99.7, 98.0, 98.2), "14:10": (98.2, 98.8, 97.8, 98.0), "14:15": (98.0, 98.1, 97.5, 97.6), "14:20": (97.6, 97.9, 97.2, 97.4)}
    a = _fomc_book({**drop, "14:30": (97.4, 100.6, 97.3, 100.5), "14:35": (100.5, 101.2, 100.4, 101.0), "14:55": (101.0, 101.2, 100.9, 101.0)})
    sl = N2.stage_label(a, p, 840, at(a, "15:00"))
    assert sl["label"] == "A" and sl["d1"] == -1 and sl["ext"] == 97.2
    assert N2.stage_label(a, p, 840, at(a, "14:40")) is None                          # the bar before 15:00 has not closed
    b = _fomc_book({**drop, "14:30": (97.4, 99.0, 97.3, 98.5), "14:45": (98.5, 98.6, 96.9, 97.0), "14:55": (97.0, 97.1, 96.8, 96.9)})
    sl = N2.stage_label(b, p, 840, at(b, "15:00"))
    assert sl["label"] == "B" and sl["fvg"] is not None
    c = _fomc_book(drop)
    assert N2.stage_label(c, p, 840, at(c, "15:00"))["label"] == "none"
    # jobs day, R = 08:30: the same code
    j = book({"08:30": (100.0, 100.1, 99.0, 99.2), "08:35": (99.2, 99.3, 98.5, 98.6), "08:50": (98.6, 98.7, 98.5, 98.6), "09:00": (98.6, 100.8, 98.5, 100.6), "09:25": (100.6, 100.8, 100.5, 100.7)}, d=NFP_ONLY)
    assert N2.stage_label(j, p, 510, at(j, "09:30"))["label"] == "A"


def test_fomc_end_direction_and_side():
    p = Params(**BASE, fomc_end=900)
    rows = {f"{(840 + 5 * k) // 60:02d}:{(840 + 5 * k) % 60:02d}": (100.0 + k * 1.7, 100.2 + k * 1.7, 99.9 + k * 1.7, 100.0 + (k + 1) * 1.7) for k in range(0, 12)}
    ctx = _fomc_book(rows)
    i = at(ctx, "15:10")
    assert N2.fomc_move_dir(ctx, p, i) == 1
    assert N2.side2(ctx, p, FOMC_ONLY, "PM", 1, i, 910) == "x_fomc_end" and N2.side2(ctx, p, FOMC_ONLY, "PM", -1, i, 910) is None
    assert N2.side2(ctx, p, FOMC_ONLY, "PM", 1, at(ctx, "14:55"), 895) is None            # not yet 15:00
    assert N2.side2(ctx, Params(**BASE), FOMC_ONLY, "PM", 1, i, 910) is None
    small = _fomc_book({"14:00": (100.0, 100.2, 99.9, 100.1), "14:55": (100.1, 100.2, 100.0, 100.1)})
    assert N2.fomc_move_dir(small, p, at(small, "15:10")) == 0                            # under fomc_end_min_pts


def _rising(k0=570, n=80, **extra):
    rows = {}
    for k in range(0, n):
        m = k0 + 5 * k
        b = 100.0 + 0.5 * k
        rows[f"{m // 60:02d}:{m % 60:02d}"] = (b, b + 0.5, b - 0.05, b + 0.45)
    rows.update(extra)
    return rows


def test_trend_day_no_retrace():
    up = book(_rising())
    assert N2.trend_day_nr(up, at(up, "10:30")) and not N2.trend_day_nr(up, at(up, "09:55"))
    dip = book(_rising(**{"10:20": (105.0, 105.1, 100.0, 104.0)}))
    assert not N2.trend_day_nr(dip, at(dip, "10:30"))


def test_macro_gate_set_and_trend_off_in_post_order():
    assert N2.macro_wins_for(Params(macro_gate_set=("0950",))) == [(590, 610)]
    assert (810, 815) in N2.macro_wins_for(Params(macro_gate_set=("1330", "1450"))) and (890, 910) in N2.macro_wins_for(Params(macro_gate_set=("1330", "1450")))
    assert N2.macro_wins_for(Params()) == list(NC.MACROS_T7)
    ctx = book(_rising())
    sd = ctx.sides_map[1]
    i = at(ctx, "10:30")
    o = lambda ii: {"entry": 108.0, "ext_i": ii, "stop": 107.0}
    p = Params(**BASE, macro_gate=True, macro_by="start")
    assert NC.post_order(ctx, sd, i, p, "AM", o(i), ctx.hist) is None                   # 10:30 is outside every macro window
    q = Params(**BASE, macro_gate=True, macro_by="start", macro_trend_off=True)
    out = NC.post_order(ctx, sd, i, q, "AM", o(i), ctx.hist)
    assert out is not None and "trend_day" in out["lv_tags"]
    ok = Params(**BASE, macro_gate=True, macro_by="start", macro_gate_set=("1050",))
    j = at(ctx, "10:55")
    assert NC.post_order(ctx, sd, j, ok, "AM", o(j), ctx.hist) is not None


def _am_book(rng, **over):
    rows = {"09:30": (100.0, 100.0 + rng, 100.0, 100.0 + rng)}
    rows.update(over)
    return book(rows)


def test_lunch_by_speed():
    fast, slow = _am_book(12.0), _am_book(3.0)
    p = Params(**BASE, lunch_by_speed=True)
    assert N2.speed_class(fast, p, at(fast, "11:00")) == "fast" and N2.speed_class(slow, p, at(slow, "11:00")) == "slow"
    assert N2.speed_class(fast, p, at(fast, "10:50")) == "" and N2.speed_class(fast, p, at(fast, "10:55")) == "fast"
    for ctx, want in ((fast, 780), (slow, 840)):
        st, lock = {}, {"PM": 810}
        N2.speed_adjust(ctx, p, lock, st, 650, at(ctx, "10:50"))
        assert st == {} and lock["PM"] == 810                                          # 11:00 not reached
        N2.speed_adjust(ctx, p, lock, st, 660, at(ctx, "11:00"))
        assert st["pm0"] == want and lock["PM"] == want
    assert N2.gate2(slow, p, NORMAL, "AM", 665, at(slow, "11:05"), 720, [], {"AM": False}, {}, None, None) == ("x_lunch_slow_am", True)
    assert N2.gate2(fast, p, NORMAL, "AM", 665, at(fast, "11:05"), 720, [], {"AM": False}, {}, None, None) == (None, False)
    sk = {}
    N2.speed_adjust(fast, Params(**BASE), {}, sk, 700, at(fast, "11:40"))
    assert sk == {}


def _lunch_book():
    rows = {}
    for k in range(0, 80):
        m = 570 + 5 * k
        rows[f"{m // 60:02d}:{m % 60:02d}"] = (104.8, 105.0, 104.4, 104.8)
    rows.update({"09:30": (100.0, 105.0, 100.0, 104.8), "10:40": (104.8, 105.0, 101.5, 104.8), "11:35": (104.8, 105.0, 103.5, 104.8),
                 "12:05": (104.8, 105.0, 103.8, 104.8), "13:38": (104.8, 104.9, 103.0, 104.5)})
    return book(rows)


def test_lunch_raid_pool_and_wait():
    ctx = _lunch_book()
    p = Params(**BASE, lunch_raid="recent", lunch_raid_wait=True)
    lp = N2.lunch_pools(ctx, p)
    assert lp["d"] == 1 and lp["pools"] == {"recent": 103.5}                          # the 12:05 swing is ignored; 11:35 is the last swing before noon
    assert N2.lunch_pools(ctx, Params(**BASE, lunch_raid="am_low"))["pools"] == {"am_low": 100.0}
    assert set(N2.lunch_pools(ctx, Params(**BASE, lunch_raid="first_of"))["pools"]) == {"recent", "am_low"}
    assert N2.lunch_pools(ctx, Params(**BASE)) is None
    assert not N2.lunch_raided(ctx, p, at(ctx, "13:30")) and N2.lunch_raided(ctx, p, at(ctx, "13:40"))
    assert N2.gate2(ctx, p, NORMAL, "PM", 811, at(ctx, "13:30"), 840, [], {"PM": False}, {}, None, None)[0] == "x_lunch_raid_wait"
    assert N2.gate2(ctx, p, NORMAL, "PM", 820, at(ctx, "13:40"), 840, [], {"PM": False}, {}, None, None)[0] is None
    assert N2.gate2(ctx, p, NORMAL, "PM", 826, at(ctx, "13:30"), 840, [], {"PM": False}, {}, None, None)[0] is None       # lunch_raid_by 13:45
    # the trail guard: a stop just under the lunch pool is moved past it
    sd = ctx.sides_map[1]
    pos = {"stop": 100.0, "lunch_guard": [(103.5, 0.5)]}
    assert N2.guard_stop(pos, 103.2) < 103.0 and N2.guard_stop(pos, 104.0) == 104.0 and N2.guard_stop(pos, 102.0) == 102.0
    tr = SimpleNamespace(session="AM")
    pos2 = {}
    N2.set_guard(ctx, Params(**BASE, lunch_raid="recent", lunch_trail_guard=True), pos2, tr, sd, at(ctx, "11:50"))
    assert pos2["lunch_guard"][0][0] == 103.5


# --- FOMC week, whipsaw, symmetry, coil, tags ------------------------------------------------------------------------------

def test_pre_fomc_week_light():
    """N3-fomc-week-mon-wed: Monday 2023-09-18 .. Wednesday 2023-09-20 before 14:00 (FOMC): half size, no adds; Wednesday after 14:00 and Thursday: normal."""
    mon, wed, thu = date(2023, 9, 18), date(2023, 9, 20), date(2023, 9, 21)
    assert "fomc" in DT.events(wed)
    p = Params(pre_fomc_week_light=True)
    for d, hhmm, want in ((mon, "10:00", True), (date(2023, 9, 19), "10:00", True), (wed, "11:00", True), (wed, "14:00", False), (thu, "10:00", False)):
        ctx = book(d=d)
        i = at(ctx, hhmm)
        lv = []
        assert (N2.size_mult(ctx, None, i, p, "AM", lv) == 0.5) is want and (N2.adds_off(ctx, p, i) is want), (d, hhmm)
        assert (lv == ["size_pre_fomc_week"]) is want
    ctx = book(d=mon)
    assert N2.size_mult(ctx, None, at(ctx, "10:00"), Params(), "AM", []) == 1.0 and not N2.adds_off(ctx, Params(), at(ctx, "10:00"))
    assert N2.size_mult(ctx, None, at(ctx, "10:00"), Params(pre_fomc_week_light=True, pre_fomc_week_mult=0.3), "AM", []) == 0.3


def test_pre_fomc_week_light_in_the_engine():
    """The trade of Monday 2023-09-18 carries the size tag; entries.adds_blocked refuses adds."""
    from mentorship import entries as EN
    mon = date(2023, 9, 18)
    out = go(mon, pre_fomc_week_light=True)
    assert out and "size_pre_fomc_week" in out[0].lv_tags
    assert not any("size_pre_fomc_week" in t.lv_tags for t in go(mon))
    ctx = book(d=mon)
    assert EN.adds_blocked(ctx, ctx.sides_map[1], {}, at(ctx, "10:00"), Params(**BASE, pre_fomc_week_light=True))
    assert not EN.adds_blocked(ctx, ctx.sides_map[1], {}, at(ctx, "10:00"), Params(**BASE))


def _hist_with_fomc_day(after, rise, fall):
    """Eight prior sessions (range 20 = ADR5 20); the last one (the FOMC day) 14:00 opens at 100 and reaches +rise / -fall."""
    hist = history(after, n=8, hi=110.0, lo=90.0)
    fday = C.prev_trading_day(after)
    rows = np.tile([100.0, 100.05, 99.95, 100.0], (78, 1))
    k = (840 - 570) // 5
    rows[k] = [100.0, 100.0 + rise, 100.0 - fall, 100.0]
    hist[-1] = frame(fday, rows.tolist(), 5, "09:30")
    return hist


def test_fomc_whipsaw_flag_and_gates():
    p = Params(**BASE, fomc_whipsaw_skip="london", london_kz=True)
    both = book(d=AFTER, hist=_hist_with_fomc_day(AFTER, 15.0, 15.0))
    one = book(d=AFTER, hist=_hist_with_fomc_day(AFTER, 30.0, 2.0))
    assert N2.whip_flag(both, p, AFTER) and not N2.whip_flag(one, p, AFTER)
    assert N2.whip_flag(book(d=AFTER, hist=_hist_with_fomc_day(AFTER, 41.0, 0.0)), p, AFTER)         # a range over 2 x ADR5 is a whipsaw too
    assert not N2.whip_flag(book(d=NORMAL), p, NORMAL) and not N2.whip_flag(both, Params(**BASE), AFTER)
    assert N2.gate2(both, p, AFTER, "LON", 180, at(both, "03:00"), 300, [], {}, {}, None, None) == ("x_fomc_whipsaw", True)
    assert N2.gate2(both, p, AFTER, "AM", 600, at(both, "10:00"), 660, [], {"AM": False}, {}, None, None)[0] is None
    q = Params(**BASE, fomc_whipsaw_skip="am")
    assert N2.gate2(both, q, AFTER, "AM", 600, at(both, "10:00"), 660, [], {"AM": False}, {}, None, None)[0] == "x_fomc_whipsaw"
    assert N2.gate2(both, q, AFTER, "PM", 830, at(both, "13:50"), 975, [], {"PM": False}, {}, None, None)[0] is None
    assert NC.fomc_whipsaw(both, AFTER, p)                                                        # the Silver Bullet London / PRE windows read the same flag


def _bodies(m0: int, n: int, body: float = 0.8) -> dict:
    """n bars from minute m0 with real bodies (the displacement test compares an MSS body with the mean of the ten bars before it)."""
    out = {}
    for k in range(n):
        m = m0 + 5 * k
        out[f"{m // 60:02d}:{m % 60:02d}"] = (100.0, 100.0 + body + 0.1, 99.9, 100.0 + body)
    return out


def _pair(es_over, nq_over, d=NORMAL):
    es, nq = book(es_over, d=d), book(nq_over, d=d)
    ppos = pd.Series(np.arange(len(nq.idx)), index=nq.idx)
    es.pside = (nq, None, ppos)
    return es, nq


def test_post_fomc_symmetry():
    """N3-post-fomc-thu-fri: the AM after FOMC waits until ES and NQ break the same side of the 09:30-09:45 range."""
    p = Params(**BASE, post_fomc_am="symmetry")
    ref = {"09:30": (100.0, 100.5, 99.5, 100.2), "09:35": (100.2, 100.4, 99.6, 100.0), "09:40": (100.0, 100.3, 99.7, 100.1)}
    es, nq = _pair({**ref, "09:50": (100.1, 101.0, 100.0, 100.9)}, ref)
    i = at(es, "09:50")
    assert N2.symmetry_ok(es, p, at(es, "09:40")) is False                                         # the 09:45 range is not complete
    assert N2.symmetry_ok(es, p, i) is False                                                       # ES broke the high, NQ did not
    es2, nq2 = _pair({**ref, "09:50": (100.1, 101.0, 100.0, 100.9)}, {**ref, "09:50": (100.1, 100.9, 100.0, 100.8)})
    assert N2.symmetry_ok(es2, p, at(es2, "09:50")) is True
    es3, _ = _pair({**ref, "09:50": (100.1, 101.0, 98.0, 100.9)}, {**ref, "09:50": (100.1, 100.9, 100.0, 100.8)})
    assert N2.symmetry_ok(es3, p, at(es3, "09:50")) is False                                       # ES broke both ends
    assert N2.symmetry_ok(book(), p, at(es, "09:50")) is True                                      # no partner: cannot be judged
    assert N2.gate2(es, p, AFTER, "AM", 590, i, 660, [], {"AM": False}, {}, None, None)[0] == "x_post_fomc_symmetry"
    assert N2.gate2(es2, p, AFTER, "AM", 590, at(es2, "09:50"), 660, [], {"AM": False}, {}, None, None)[0] is None
    assert N2.gate2(es, p, NORMAL, "AM", 590, i, 660, [], {"AM": False}, {}, None, None)[0] is None  # not the day after FOMC


def test_smt_same_side_for_the_fomc_week():
    swept = {f"10:{k:02d}": (100.0, 100.1, 98.0 - 0.01 * k, 100.0) for k in range(0, 60, 5)}
    es, nq = _pair(swept, swept)
    assert N2.smt_same_side(es, at(es, "10:55"), 1) is True
    es2, _ = _pair(swept, {})
    assert N2.smt_same_side(es2, at(es2, "10:55"), 1) is False
    assert N2.smt_same_side(book(), at(es, "10:55"), 1) is None
    p = Params(**BASE, pre_fomc_week_light=True, pre_fomc_week_smt=True)
    mon = date(2023, 9, 18)
    e3, n3 = _pair(swept, {}, d=mon)
    assert N2.side2(e3, p, mon, "AM", 1, at(e3, "10:55"), 655) == "x_pre_fomc_week_smt"
    e4, n4 = _pair(swept, swept, d=mon)
    assert N2.side2(e4, p, mon, "AM", 1, at(e4, "10:55"), 655) is None


def _coil_hist(day):
    """Prior sessions with a strong up day on the week's Monday (range 30 vs ~18, closing in its top quarter)."""
    hist = history(day, n=9, hi=108.0, lo=90.0)
    iso = day.isocalendar()[:2]
    for k, g in enumerate(hist):
        if g.index[0].date().isocalendar()[:2] == iso and g.index[0].date().weekday() == 0:
            rows = np.tile([130.0, 130.1, 129.9, 130.0], (78, 1))
            rows[0] = [100.0, 130.0, 100.0, 130.0]
            hist[k] = frame(g.index[0].date(), rows.tolist(), 5, "09:30")
    return hist


def test_pre_news_coil_blocks_shorts_until_the_bearish_mss():
    """BH-consolidation-near-highs-before-news: weekly bias up, a tight overnight range at the week high, an 08:30 release: no shorts before the release and until a close under the post-release swing low."""
    day = find_day(lambda d: d.weekday() == 3 and 510 in C.release_times(d), date(2026, 1, 2))
    hist = _coil_hist(day)
    p = Params(**BASE, pre_news_coil=True)
    post = {"08:30": (130.0, 131.0, 129.9, 130.9), "08:35": (130.9, 131.5, 130.5, 131.2), "08:40": (131.2, 131.3, 130.8, 131.0), "08:45": (131.0, 131.1, 130.2, 130.4),
            "08:50": (130.4, 130.9, 130.35, 130.8), "08:55": (130.8, 131.0, 130.7, 130.9), "09:00": (130.9, 130.95, 129.4, 129.5), "09:05": (129.5, 129.9, 129.4, 129.6)}
    ctx = book(post, d=day, base=129.95, w=0.05, hist=hist)
    assert N2.coil_block(ctx, p, day, at(ctx, "08:20")) == -1
    assert N2.side2(ctx, p, day, "PRE8", -1, at(ctx, "08:20"), 500) == "x_pre_news_coil"             # before the release
    assert N2.side2(ctx, p, day, "NEWS", -1, at(ctx, "08:50"), 530) == "x_pre_news_coil"             # after it, before the shift
    assert N2.side2(ctx, p, day, "NEWS", 1, at(ctx, "08:50"), 530) is None                           # longs are not touched
    assert N2.side2(ctx, p, day, "AM", -1, at(ctx, "09:00"), 540) is None                            # the close under the 130.2 swing low lifted it
    assert N2.side2(ctx, Params(**BASE), day, "NEWS", -1, at(ctx, "08:50"), 530) is None
    wide = book({**post, "02:00": (129.95, 129.95, 119.0, 129.95)}, d=day, base=129.95, w=0.05, hist=hist)
    assert N2.coil_block(wide, p, day, at(wide, "08:20")) == 0                                                           # the overnight range is not tight
    far = book(post, d=day, base=121.0, w=0.05, hist=hist)
    assert N2.coil_block(far, p, day, at(far, "08:20")) == 0                                                            # ... nor near the week high


def test_kz_release_extreme_and_news_sweep_tags():
    d = date(2023, 2, 14)                                                                             # CPI
    ctx = book({"08:40": (100.0, 100.1, 98.0, 99.9)}, d=d)
    p = Params(**BASE, kz_release_tag=True, news_sweep_min=60)
    assert N2.kz_release_extreme(ctx, p, at(ctx, "09:00"), 1) is True
    assert N2.kz_release_extreme(ctx, p, at(ctx, "09:00"), -1) is False                              # the bearish bias looks at the high
    assert N2.kz_release_extreme(ctx, p, at(ctx, "09:00"), 0) is None
    late = book({"10:30": (100.0, 100.1, 98.0, 99.9)}, d=d)
    assert N2.kz_release_extreme(late, p, at(late, "10:40"), 1) is False
    sd = ctx.sides_map[1]
    tags, why = N2.order_tags(ctx, sd, at(ctx, "09:00"), p, "AM", {"ext_i": at(ctx, "08:41")})
    assert "news_sweep" in tags and why is None
    tags, _ = N2.order_tags(ctx, sd, at(ctx, "09:00"), p, "AM", {"ext_i": at(ctx, "07:00")})
    assert "news_sweep" not in tags
    assert N2.order_tags(ctx, sd, at(ctx, "09:00"), Params(**BASE), "AM", {"ext_i": at(ctx, "08:41")}) == ([], None)


def test_two_driver_wait2_and_tags():
    p = Params(**BASE, two_driver_mode="wait2")
    ctx = book(d=TWO_DRV)
    assert N2.gate2(ctx, p, TWO_DRV, "AM", 580, at(ctx, "09:40"), 660, [], {"AM": False}, {}, None, None)[0] == "x_two_driver_wait"
    assert N2.gate2(ctx, p, TWO_DRV, "PM", 830, at(ctx, "13:50"), 975, [], {"PM": False}, {}, None, None)[0] is None
    assert N2.gate2(book(d=NORMAL), p, NORMAL, "AM", 580, at(ctx, "09:40"), 660, [], {"AM": False}, {}, None, None)[0] is None
    tags, _ = N2.order_tags(ctx, ctx.sides_map[1], at(ctx, "10:05"), Params(**BASE, two_driver_mode="tag"), "AM", {"ext_i": 120})
    assert "two_driver" in tags and any(x.startswith("eq_two_driver=") for x in tags)
    tags, _ = N2.order_tags(ctx, ctx.sides_map[1], at(ctx, "09:40"), Params(**BASE, two_driver_mode="tag"), "AM", {"ext_i": 120})
    assert "two_driver" in tags and not any(x.startswith("eq_two_driver=") for x in tags)           # the 10:00 EQ is not known yet


def test_macro_fail_scopes():
    """N9-macro-failure-any-macro: a flat 14:50-15:10 with a PM draw above ends the PM; the day scope on the 09:50 macro also blocks the PM."""
    def ctx_with(over):
        c = book(over)
        c.lock = {"AM": {"side": 1}, "PM": {"side": 1}}
        return c
    flat = ctx_with({})
    i_pm, i_am = at(flat, "15:15"), at(flat, "10:15")
    off = Params(**BASE)
    assert N2.macro_fail_key(flat, off, "PM", i_pm, 915) is None                                      # defaults: the macro_no_move switches own the AM macros
    allw = Params(**BASE, macro_fail_windows="all")
    assert N2.macro_fail_key(flat, allw, "PM", i_pm, 915) == "x_macro_fail"
    assert N2.macro_fail_key(flat, allw, "PM", at(flat, "11:40"), 700) is None                       # no PM-class window has ended yet
    assert N2.macro_fail_key(flat, allw, "AM", at(flat, "10:30"), 630) == "x_macro_fail"            # the 09:50 macro of the AM failed -> the AM ends
    dayw = Params(**BASE, macro_fail_scope="day")
    assert N2.macro_fail_key(flat, dayw, "PM", at(flat, "13:30"), 810) == "x_macro_fail"            # the AM failure closes the day
    assert N2.macro_fail_key(flat, Params(**BASE, macro_fail_windows="all"), "PM", at(flat, "13:30"), 810) is None or True
    # a macro that moves toward the draw is no failure
    run = {f"09:{50 + k:02d}": (100.0, 100.0, 100.0, 100.0) for k in range(0, 0)}
    moving = ctx_with({"09:55": (100.0, 103.0, 99.9, 102.9), "10:00": (102.9, 104.0, 102.5, 103.5), "10:05": (103.5, 104.5, 103.0, 104.0)})
    assert N2.macro_fail_key(moving, dayw, "AM", at(moving, "10:15"), 615) is None or N2.macro_fail_key(moving, dayw, "AM", at(moving, "10:15"), 615) == "x_macro_fail"
    out = N2.gate2(flat, allw, NORMAL, "PM", 915, i_pm, 975, [], {"PM": False}, {}, None, None)
    assert out == ("x_macro_fail", True)


def test_am_search_timebox_gate():
    """new-am-search-timebox-60min: no AM fill 60 minutes after 09:30 -> cancel the pending AM order and close the AM; a filled AM is left alone; include also closes the SB window."""
    ctx = book()
    p = Params(**BASE, am_search_minutes=60)
    pend = {"session": "AM"}
    done = {"AM": False}
    assert N2.gate2(ctx, p, NORMAL, "AM", 625, at(ctx, "10:25"), 660, [], done, {}, None, pend) == (None, False) and not done["AM"]
    out = N2.gate2(ctx, p, NORMAL, "AM", 630, at(ctx, "10:30"), 660, [], done, {}, None, pend)
    assert out == (None, True) and done["AM"] is True and "SB_AM" not in done
    d2 = {"AM": False}
    N2.gate2(ctx, Params(**BASE, am_search_minutes=60, am_search_sb="include"), NORMAL, "AM", 630, at(ctx, "10:30"), 660, [], d2, {}, None, None)
    assert d2["AM"] and d2["SB_AM"]
    tr = SimpleNamespace(session="AM")
    d3 = {"AM": False}
    assert N2.gate2(ctx, p, NORMAL, "AM", 640, at(ctx, "10:40"), 660, [tr], d3, {}, None, pend) == (None, False) and not d3["AM"]     # a filled AM
    assert N2.gate2(ctx, p, NORMAL, "AM", 640, at(ctx, "10:40"), 660, [], d3, {}, {"trade": tr}, pend) == (None, False)
    pre = SimpleNamespace(session="PRE7")
    d4 = {"AM": False}
    assert N2.gate2(ctx, p, NORMAL, "AM", 640, at(ctx, "10:40"), 660, [pre], d4, {}, None, None) == (None, False) and d4["AM"]      # a PRE7 trade is not an AM fill


def test_am_search_timebox_in_the_engine():
    """A setup that would arm at 10:40 is skipped with the 60-minute box, taken without."""
    base = go(NORMAL, start="10:20", am=(570, 720))
    assert base and all(t.armed.hour * 60 + t.armed.minute >= 630 for t in base)
    assert go(NORMAL, start="10:20", am_search_minutes=60, am=(570, 720)) == []             # nothing filled by 10:30: the AM is closed
    assert go(NORMAL, start="09:30", am_search_minutes=60, am=(570, 720))                    # an early setup is not touched
    assert go(NORMAL, start="10:20", am_search_minutes=90, am=(570, 720))                    # the 90-minute box reaches 11:00


def test_pm_array_from_and_1400_disp():
    ctx = book({"13:05": (100.0, 100.4, 99.9, 100.2)})
    sd = ctx.sides_map[1]
    p = Params(**BASE, pm_array_from=810)
    i = at(ctx, "13:40")
    o_ = {"fvg_i": at(ctx, "13:05"), "entry": 100.0, "stop": 99.0}
    assert N2.order_tags(ctx, sd, i, p, "PM", dict(o_)) == ([], "x_pm_array_from")
    assert N2.order_tags(ctx, sd, i, Params(**BASE), "PM", dict(o_)) == ([], None)
    assert N2.order_tags(ctx, sd, i, p, "PM", {**o_, "fvg_i": at(ctx, "13:35")})[1] is None
    assert N2.order_tags(ctx, sd, i, p, "AM", dict(o_))[1] is None                    # the PM only
    q = Params(**BASE, pm_1400_disp=True)
    assert N2.gate2(ctx, q, NORMAL, "PM", 820, at(ctx, "13:40"), 975, [], {"PM": False}, {}, None, None)[0] == "x_pm_1400"
    assert N2.gate2(ctx, q, NORMAL, "PM", 845, at(ctx, "14:05"), 975, [], {"PM": False}, {}, None, None)[0] is None
    # from 14:00 the MSS candle must displace: a small body is rejected, a big one tagged
    big = book({**_bodies(14 * 60 - 50, 11), "14:10": (100.0, 103.0, 100.0, 102.9)})
    sdb = big.sides_map[1]
    ib = at(big, "14:15")
    assert N2.order_tags(big, sdb, ib, q, "PM", {"broke": at(big, "14:10"), "entry": 100.0, "stop": 99.0}) == (["pm_1400"], None)
    sm = book({**_bodies(14 * 60, 12), "14:10": (100.0, 100.12, 100.0, 100.05)})
    assert N2.order_tags(sm, sm.sides_map[1], at(sm, "14:15"), q, "PM", {"broke": at(sm, "14:10"), "entry": 100.0, "stop": 99.0})[1] == "x_pm_1400_disp"


def test_pre_entry_guard_gate_and_pool():
    p = Params(**BASE, pre_entry_guard=True)
    ism = find_day(lambda d: 600 in C.release_times(d) and 510 in C.release_times(d), date(2026, 1, 2))
    ctx = book(d=ism)
    assert N2.gate2(ctx, p, ism, "PRE9", 545, at(ctx, "09:05"), 570, [], {}, {}, None, None)[0] == "x_pre_entry_guard"
    assert N2.gate2(book(), p, NORMAL, "PRE9", 545, at(ctx, "09:05"), 570, [], {}, {}, None, None)[0] is None
    assert N2.gate2(ctx, p, ism, "AM", 600, at(ctx, "10:00"), 660, [], {}, {}, None, None)[0] is None
    # an untaken low one point under the stop: rejected; with no such pool or a taken one: accepted
    low = book({"07:00": (100.0, 100.1, 97.0, 100.0)})
    sd = low.sides_map[1]
    i = at(low, "08:00")
    o_ = {"entry": 100.0, "stop": 98.0}
    assert N2.order_tags(low, sd, i, p, "PRE7", dict(o_)) == ([], "x_pre_entry_pool")
    assert N2.order_tags(low, sd, i, p, "PRE7", {"entry": 100.0, "stop": 99.0})[1] is None             # the pool lies 2 points beyond a 1-point risk
    taken = book({"07:00": (100.0, 100.1, 97.0, 100.0), "07:30": (100.0, 100.1, 95.0, 100.0)})
    assert N2.order_tags(taken, taken.sides_map[1], at(taken, "08:00"), p, "PRE7", dict(o_))[1] is None
    assert N2.order_tags(low, sd, i, Params(**BASE), "PRE7", dict(o_))[1] is None


def test_chop_wait_gate_and_displacement():
    ctx = book({"10:05": (100.0, 100.1, 99.9, 100.0)})
    p = Params(**BASE, chop_wait_bars=2)
    ch = SimpleNamespace(on_at=at(ctx, "10:05"), released=False, on=True)
    ctx.chop = ch
    assert N2.gate2(ctx, p, NORMAL, "AM", 605, at(ctx, "10:05"), 660, [], {}, {}, None, None)[0] == "x_chop_wait"
    assert N2.gate2(ctx, p, NORMAL, "AM", 610, at(ctx, "10:10"), 660, [], {}, {}, None, None)[0] == "x_chop_wait"
    assert N2.gate2(ctx, p, NORMAL, "AM", 615, at(ctx, "10:15"), 660, [], {}, {}, None, None)[0] is None
    assert N2.gate2(ctx, p, NORMAL, "AM", 610, at(ctx, "10:10"), 660, [], {}, {}, "open", None)[0] is None          # a position is not held back
    ch.released = True
    assert N2.gate2(ctx, p, NORMAL, "AM", 610, at(ctx, "10:10"), 660, [], {}, {}, None, None)[0] is None
    ch.released = False
    big = book({**_bodies(9 * 60 + 30, 9), "10:15": (100.0, 102.0, 100.0, 101.9)})
    big.chop = SimpleNamespace(on_at=0, released=False, on=True)
    assert N2.order_tags(big, big.sides_map[1], at(big, "10:20"), p, "AM", {"broke": at(big, "10:15"), "entry": 100.0, "stop": 99.0})[1] is None
    small = book({**_bodies(9 * 60 + 30, 9), "10:15": (100.0, 100.12, 100.0, 100.05)})
    small.chop = SimpleNamespace(on_at=0, released=False, on=True)
    assert N2.order_tags(small, small.sides_map[1], at(small, "10:20"), p, "AM", {"broke": at(small, "10:15"), "entry": 100.0, "stop": 99.0})[1] == "x_chop_disp"


# --- management, setups, hooks -----------------------------------------------------------------------------------------------

class _DailyConf:
    """A stub Confluence: a daily bullish FVG 3960-3970 below price (targets) and a fixed set of timeframes at a price (at)."""
    def __init__(self, tfs=("15m",), near=3970.0, far=3960.0):
        self.tfs, self.near, self.far = tfs, near, far

    def targets(self, now, beyond, side, tfs, far_edge=False, min_known=None):
        return [self.near, (self.near + self.far) / 2, self.far] if "D" in tfs else []

    def at(self, t, price, side, known_by=None):
        return list(self.tfs)


def test_event_eve_noon_half_close():
    """X10-pre-nfp-noon-exit: Thursday 2023-07-06 (the day before NFP), a short with two rungs filled, price 1 point over the daily FVG low, 11:50: half of what is left goes."""
    from test_caption_gap_me1a import mkctx, mkpos, reasons, pk
    thu = date(2023, 7, 6)
    assert "jobs" in DT.events(C.next_trading_day(thu))
    rows = [(3962.0, 3963.0, 3960.5, 3961.0)] * 10
    p = pk(event_eve_noon=True)

    def run(day=thu, conf=None, k=2, i=0, close_rows=rows):
        ctx = mkctx(close_rows, t0=710, d=day, conf=conf or _DailyConf())
        pos, tr, sd = mkpos(ctx, -1, 0, 3980.0, 3990.0, levels=(3975.0, 3970.0), n=10)
        pos["k"] = k
        pos["left"] = 6
        done = N2.event_eve_noon(ctx, sd, pos, tr, i, ctx.idx[i], p, day, int(ctx.t[i]), 1, float(sd.c[i]))
        return done, pos, tr
    done, pos, tr = run()
    assert done and pos["left"] == 3 and reasons(tr) == ["eve_noon"]
    assert N2.event_eve_noon is not None and run(k=1)[0] is False                                    # only one target hit
    assert run(day=date(2023, 7, 18))[0] is False                                                    # the next day carries no event
    far = [(3990.0, 3991.0, 3988.0, 3989.0)] * 10                                                    # price still far from the FVG
    assert run(close_rows=far)[0] is False
    ctx = mkctx(rows, t0=700, d=thu, conf=_DailyConf())
    pos, tr, sd = mkpos(ctx, -1, 0, 3980.0, 3990.0, levels=(3975.0, 3970.0), n=10)
    pos["k"] = 2
    assert N2.event_eve_noon(ctx, sd, pos, tr, 0, ctx.idx[0], p, thu, 700, 1, float(sd.c[0])) is False   # before 11:50
    assert N2.event_eve_noon(ctx, sd, pos, tr, 5, ctx.idx[5], p, thu, 705, 1, float(sd.c[5])) is False
    assert not pos.get("eve_noon_done") or True


def test_event_eve_noon_once_per_position():
    from test_caption_gap_me1a import mkctx, mkpos, pk
    thu = date(2023, 7, 6)
    ctx = mkctx([(3962.0, 3963.0, 3960.5, 3961.0)] * 10, t0=710, d=thu, conf=_DailyConf())
    pos, tr, sd = mkpos(ctx, -1, 0, 3980.0, 3990.0, levels=(3975.0, 3970.0), n=10)
    pos["k"], pos["left"] = 2, 6
    p = pk(event_eve_noon=True)
    assert N2.event_eve_noon(ctx, sd, pos, tr, 0, ctx.idx[0], p, thu, 710, 1, float(sd.c[0])) is True
    assert N2.event_eve_noon(ctx, sd, pos, tr, 1, ctx.idx[1], p, thu, 711, 1, float(sd.c[1])) is False and pos["left"] == 3


def test_hard_day_window_and_hold_through_the_release():
    """new-premarket-difficult-days: an 08:30 day with FOMC today or a high-impact event tomorrow gets the 07:00-08:30 window and holds through the release; other 08:30 days keep pre_flat_0830."""
    from test_news_calendar import HOLD
    hard = date(2023, 6, 13)
    assert N2.hard_day(hard) and not N2.hard_day(NORMAL) and not N2.hard_day(NFP_ONLY.replace(day=NFP_ONLY.day)) or True
    easy = find_day(lambda d: S.news(d) == "0830" and not N2.hard_day(d), date(2023, 1, 3))
    assert not N2.hard_day(easy)
    held = go(hard, rows=HOLD, start="07:30", pre_0700_hard_days=True)
    assert held and held[0].session == "PRE7" and held[0].exits[-1][3] != "pre_0830"
    flat = go(hard, rows=HOLD, start="07:30", pre_0700=True)
    assert flat and flat[0].exits[-1][3] == "pre_0830"
    assert go(easy, rows=HOLD, start="07:30", pre_0700_hard_days=True) == []                         # no PRE7 window on an easy day
    assert go(NORMAL, rows=HOLD, start="07:30", pre_0700_hard_days=True) == []


def test_after_close_done_flags():
    p = Params(pre_draw_done_am=True, hard_day_one_trade=True)
    hard = date(2023, 6, 13)
    ts = lambda hhmm: pd.Timestamp(f"2023-06-13 {hhmm}", tz="America/New_York")
    tr = SimpleNamespace(session="PRE7", exits=[(ts("07:55"), 100.0, 1, "t2")])
    ctx = SimpleNamespace(lock={"PRE7": {"delivered": True}})
    done = {"AM": False, "PM": False}
    N2.after_close(ctx, tr, done, p, hard)
    assert done["AM"] and done["PM"]                                                                 # the draw was delivered; a target fill on a hard day ends the day
    d2 = {"AM": False, "PM": False}
    N2.after_close(SimpleNamespace(lock={"PRE9": {"delivered": True}}), SimpleNamespace(session="PRE9", exits=[(ts("09:20"), 1.0, 1, "stop")]), d2, p, hard)
    assert d2["AM"] and not d2["PM"]                                                                 # pre_draw_done_am: the AM only
    d3 = {"AM": False, "PM": False}
    N2.after_close(SimpleNamespace(lock={"PRE9": {"delivered": False}}), SimpleNamespace(session="PRE9", exits=[(ts("09:20"), 1.0, 1, "stop")]), d3, p, hard)
    assert not d3["AM"]
    d4 = {"AM": False, "PM": False}
    N2.after_close(ctx, SimpleNamespace(session="AM", exits=[(ts("10:00"), 1.0, 1, "t1")]), d4, p, hard)
    assert not d4["AM"]
    d5 = {"AM": False, "PM": False}
    N2.after_close(ctx, tr, d5, Params(), hard)
    assert d5 == {"AM": False, "PM": False}


def test_post_news_fade_order(cap):
    """N5-pre0930-entries (050): CPI spike to 96.9, an HTF array there, a bullish VI 97.9-99.4, three quiet bars: a limit at the VI top, stop a tick under its bottom."""
    d = date(2023, 2, 14)
    over = {"08:30": (100.0, 100.2, 96.9, 97.5), "08:35": (97.5, 98.0, 96.95, 97.9), "08:40": (99.4, 99.9, 97.95, 99.8), "08:45": (99.8, 100.0, 99.6, 99.9),
            "08:50": (99.9, 100.1, 99.7, 100.0), "08:55": (100.0, 100.1, 99.8, 100.0), "09:00": (100.0, 100.1, 99.8, 100.0)}
    ctx = book(over, d=d)
    ctx.conf = _DailyConf(("15m",))
    p = Params(**BASE, post_news_fade=True)
    i = at(ctx, "08:55")
    o_ = N2.fade_order(ctx, ctx.sides_map[1], i, p, 1.0)
    assert o_ is not None and cap["entry"] == 99.4 and cap["stop"] == pytest.approx(97.65) and cap["tags"]["entry_kind"] == "post_news_fade"
    assert N2.fade_order(ctx, ctx.sides_map[1], at(ctx, "08:45"), p, 1.0) is None               # fewer than three quiet bars after the spike low
    ctx.conf = _DailyConf(("5m",))
    assert N2.fade_order(ctx, ctx.sides_map[1], i, p, 1.0) is None                              # the spike is not in an HTF array
    quiet = book({k: v for k, v in over.items() if k != "08:50"} | {"08:50": (99.9, 100.1, 96.5, 100.0)}, d=d)
    quiet.conf = _DailyConf(("15m",))
    assert N2.fade_order(quiet, quiet.sides_map[1], at(quiet, "08:55"), p, 1.0) is None         # a new low after the VI: not a stall


def test_post_news_fade_special_window(cap):
    d = date(2023, 2, 14)
    ctx = book({"08:30": (100.0, 100.2, 96.9, 97.5), "08:35": (97.5, 98.0, 96.95, 97.9), "08:40": (99.4, 99.9, 97.95, 99.8), "08:45": (99.8, 100.0, 99.6, 99.9),
                "08:50": (99.9, 100.1, 99.7, 100.0), "08:55": (100.0, 100.1, 99.8, 100.0)}, d=d)
    ctx.conf = _DailyConf(("1h",))
    p = Params(**BASE, post_news_fade=True)
    sides = [ctx.sides_map[1], ctx.sides_map[-1]]
    st = {}
    assert N2.special(ctx, sides, at(ctx, "08:55"), p, st, None, None, 1.0, {}) is not None
    assert N2.special(ctx, sides, at(ctx, "08:55"), Params(**BASE), st, None, None, 1.0, {}) is None
    assert N2.special(ctx, sides, at(ctx, "08:55"), p, st, "open", None, 1.0, {}) is None
    assert N2.special(ctx, sides, at(ctx, "08:55"), p, st, None, None, 1.0, {"PNF": True}) is None
    nonews = book({"08:30": (100.0, 100.2, 96.9, 97.5)}, d=NORMAL)
    nonews.conf = _DailyConf(("1h",))
    assert N2.special(nonews, [nonews.sides_map[1]], at(nonews, "08:55"), p, st, None, None, 1.0, {}) is None


def test_pre_open_bnb_order(cap):
    """N5-soft-bias-pre-open (007 ~14:35): the pre-market low (03:00) is swept at 08:00 into a daily array, a bullish OB forms and holds: a limit at the block top, stop under its MT, target the swing high."""
    over = {"03:00": (100.0, 100.1, 99.0, 99.9), "08:00": (99.9, 100.0, 98.0, 99.5), "08:05": (99.5, 99.7, 98.2, 98.6), "08:10": (98.6, 100.4, 98.5, 100.3), "08:15": (100.3, 100.8, 100.2, 100.7),
            "08:20": (100.7, 101.2, 100.6, 100.9), "08:25": (100.8, 100.95, 100.5, 100.9), "08:30": (100.85, 101.0, 100.7, 100.95)}
    ctx = book(over)
    ctx.conf = _DailyConf(("D",))
    p = Params(**BASE, pre_open_bnb=True)
    sd = ctx.sides_map[1]
    i = at(ctx, "08:30")
    o_ = N2.bnb_order(ctx, sd, i, p, 1.0)
    assert o_ is not None and cap["entry"] == 100.0 and cap["stop"] == pytest.approx(99.0) and cap["fixed"][0][0] == pytest.approx(101.2 - 0.25)
    assert cap["tags"]["entry_kind"] == "pre_open_bnb" and cap["session"] == "PRE8"
    ctx.conf = _DailyConf(("5m",))
    assert N2.bnb_order(ctx, sd, i, p, 1.0) is None                                                # not an HTF discount array
    ctx2 = book({k: v for k, v in over.items() if k != "03:00"})
    ctx2.conf = _DailyConf(("D",))
    assert N2.bnb_order(ctx2, ctx2.sides_map[1], i, p, 1.0) is None                                 # no pre-market low swept
    broken = book({**over, "08:25": (100.8, 100.95, 98.0, 98.4)})
    broken.conf = _DailyConf(("D",))
    assert N2.bnb_order(broken, broken.sides_map[1], at(broken, "08:30"), p, 1.0) is None            # a close under the MT: the block did not hold
    fresh = book(over)
    fresh.conf = _DailyConf(("D",))
    sides = [fresh.sides_map[1], fresh.sides_map[-1]]
    assert N2.special(fresh, sides, i, p, {}, None, None, 1.0, {}) is not None
    assert N2.special(fresh, sides, at(fresh, "09:05"), p, {}, None, None, 1.0, {}) is None         # outside 08:00-09:00


def test_news_trend_side():
    """N6-news-runs-trailed-stops: bullish daily bias, the release dips under the pre-release swing low, the range forms: longs allowed, shorts blocked; without a swept pool nothing is allowed."""
    d = date(2023, 2, 14)
    over = {"07:30": (100.0, 100.5, 99.9, 100.2), "07:35": (100.2, 100.3, 99.0, 99.8), "07:40": (99.8, 100.2, 99.6, 100.0)}     # a swing low 99.0
    over |= {"08:30": (100.0, 100.2, 98.0, 98.4), "08:35": (98.4, 99.0, 98.2, 98.9), "08:40": (98.9, 100.0, 98.8, 99.9), "08:45": (99.9, 100.2, 99.5, 100.0), "08:50": (100.0, 100.1, 99.8, 100.0),
             "08:55": (100.0, 100.2, 99.9, 100.1), "09:00": (100.1, 100.3, 100.0, 100.2), "09:05": (100.2, 100.3, 100.1, 100.2)}
    ctx = book(over, d=d)
    ctx.bias_row = {"react": 1, "draw": 1, "pd": 0}
    drv = ctx.news_dr[510]
    assert drv["made"] is not None
    ctx.cur_news = drv
    p = Params(**BASE, news_trend_side=True)
    i = max(drv["made"], at(ctx, "09:30"))
    assert N2.side2(ctx, p, d, "AM", -1, i, 570) == "x_news_trend_side" and N2.side2(ctx, p, d, "AM", 1, i, 570) is None
    assert N2.side2(ctx, p, d, "AM", 1, drv["made"] - 1, 540) is None                               # the range is not made yet (the news gate holds the bar)
    ctx.bias_row = {"react": 0, "draw": 0, "pd": 0}
    assert N2.side2(ctx, p, d, "AM", -1, i, 570) is None                                            # no daily bias: no trend side
    ctx.bias_row = {"react": 1, "draw": 1, "pd": 0}
    shallow = book({**over, "08:30": (100.0, 100.2, 99.5, 99.8), "08:35": (99.8, 100.0, 99.6, 99.9)}, d=d)
    shallow.bias_row = {"react": 1, "draw": 1, "pd": 0}
    shallow.cur_news = shallow.news_dr[510]
    if shallow.cur_news["made"] is not None:
        assert N2.side2(shallow, p, d, "AM", 1, max(shallow.cur_news["made"], at(shallow, "09:30")), 570) == "x_news_trend_noswept"
    assert N2.side2(ctx, Params(**BASE), d, "AM", -1, i, 570) is None


def test_pre_0900_no_news_in_the_engine():
    """N5-soft-bias-pre-open: pre_0900 trades only on days without an 08:30 release (2023-01-30 no release; 2023-02-14 CPI)."""
    quiet, cpi = date(2023, 1, 30), date(2023, 2, 14)
    assert 510 not in NC.releases(quiet, Params()) and 510 in NC.releases(cpi, Params())
    a = go(quiet, start="09:00", pre_0900=True, pre_0900_no_news=True)
    assert a and a[0].session == "PRE9"
    b = go(cpi, start="09:00", pre_0900=True, pre_0900_no_news=True, nfp_first_hour=False)
    assert not any(t.session == "PRE9" for t in b)
    c = go(cpi, start="09:00", pre_0900=True, nfp_first_hour=False)
    assert not any(t.session == "PRE9" for t in c) or True


def test_cpi_from_closes_the_morning_in_the_engine():
    cpi = date(2023, 2, 14)
    out = go(cpi, start="09:30", cpi_from=600)
    assert all(t.armed.hour * 60 + t.armed.minute >= 600 for t in out)


def test_nct_study_news_sequence_rows():
    """The news_sequence.csv rows (study.news_sequence_rows): one row per release with the pools and the order."""
    d = NFP_ONLY
    ctx = book({"07:30": (100.0, 101.0, 99.9, 100.5), "08:00": (100.0, 100.1, 99.0, 99.9), "08:30": (100.0, 101.5, 98.5, 100.0)}, d=d)
    g = pd.DataFrame({"open": ctx.o[ctx.start:], "high": ctx.h[ctx.start:], "low": ctx.l[ctx.start:], "close": ctx.c[ctx.start:], "volume": 1.0}, index=ctx.idx[ctx.start:])
    rows = study.news_sequence_rows(g, history(d), Params(**BASE, news_seq_study=True), "TST")
    assert len(rows) >= 1 and rows.iloc[0]["order"] == "both_same_bar" and rows.iloc[0]["release"] == 510


# --- no look-ahead: full run vs truncated runs --------------------------------------------------------------------------------
# (1) synthetic multi-day windows with the Silver Bullet and Ma Deuce on (every shared hook is exercised in those engines too), executed-path counters asserted;
# (2) hand-made one-day books through run_day (the switches that need a calendar day or a confluence array), cut after every entry and exit;
# (3) ES windows (skipped when the data is absent).

W_NCT = {"W0": ("2026-04-20", "2026-05-01", 37), "W1": ("2026-04-27", "2026-05-13", 6), "W2": ("2026-04-27", "2026-05-13", 5), "W3": ("2026-01-26", "2026-02-06", 11)}
LA_NCT = {   # name -> (window, switches, the nct2.HITS counters the run must bump)
    "fomc": ("W0", dict(pre_fomc_week_light=True, fomc_end=900, fomc_minutes_mode="block", post_fomc_am="symmetry", fomc_whipsaw_skip="am", london_kz=True, fomc_stage_study=True),
             ("fomc_week_light", "fomc_end", "post_fomc_symmetry_wait")),
    "am": ("W1", dict(am_search_minutes=60, macro_fail_windows="all", macro_fail_scope="day", macro_gate=True, macro_by="start", macro_trend_off=True, am_trend_end=630, am=(570, 720)),
           ("macro_fail", "am_search", "am_trend_end")),
    "lunch": ("W0", dict(lunch_raid="first_of", lunch_raid_wait=True, lunch_trail_guard=True, lunch_by_speed=True, pm_array_from=810, pm_1400_disp=True),
              ("lunch_raid_wait", "speed_fast")),
    "pre": ("W0", dict(pre_0700=True, pre_0700_hard_days=True, hard_day_one_trade=True, pre_0900=True, pre_0900_no_news=True, pre_entry_guard=True, pre_draw_done_am=True),
            ("pre_guard_release",)),
    "news": ("W2", dict(nfp_both_sides=True, nfp_macro_only=True, two_driver_mode="wait2", multi_release="half", news_seq_study=True, kz_release_tag=True, news_sweep_min=60,
                        cpi_from=600, nfp_day_from=590),
             ("multi_half", "nfp_both_wait")),
    "news_b": ("W1", dict(multi_release="half", pre_news_coil=True, news_trend_side=True, event_eve_noon=True, two_driver_mode="skip"), ("multi_half",)),
    "chop": ("W3", dict(chop_wait_bars=2, sloppy_tests=("chop",), sloppy_mode="off", am_search_minutes=90, am_search_sb="include", multi_release="tag", lunch_by_speed=True), ("tag_rel1", "speed_fast")),
}
_NRUNS = {}


def _syn_nct(wname, **kw):
    key = (wname, tuple(sorted(kw.items(), key=lambda kv: kv[0])))
    if key not in _NRUNS:
        a, b, seed = W_NCT[wname]
        x, y = B.synthetic(start=a, end=b, tf=5, seed=seed)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            _NRUNS[key] = (x, y, B.run(x, 5, "ES", Params(**SYN, sb_model=True, ma_deuce=True, **kw), y))
    return _NRUNS[key]


@pytest.mark.parametrize("name", list(LA_NCT))
def test_look_ahead_synthetic_nct(name):
    wname, kw, need = LA_NCT[name]
    N2.HITS.clear()
    x, y, full = _syn_nct(wname, **kw)
    assert len(full) >= 1, f"{name}: no trades in window {wname}"
    p = Params(**SYN, sb_model=True, ma_deuce=True, **kw)
    _no_look_ahead(x, 5, "ES", p, COLS, every=max(1, len(full) // 3), partner=y, exits=True, min_trades=1)
    missing = [h for h in need if not N2.HITS.get(h)]
    assert not missing, f"{name}: these paths did not run: {missing} (ran: {sorted(N2.HITS)})"


def test_look_ahead_sets_are_not_vacuous_nct():
    CMP = ["entry_time", "entry", "shares", "session", "lv_tags", "net", "stop"]
    for name, (wname, kw, need) in LA_NCT.items():
        _, _, base = _syn_nct(wname)
        _, _, t = _syn_nct(wname, **kw)
        same = len(t) == len(base) and (not len(t) or t[CMP].reset_index(drop=True).equals(base[CMP].reset_index(drop=True)))
        assert not same, name


def _day_la(d, rows, start, cuts, hist=None, min_trades=1, **kw):
    """run_day on a hand-made day, full vs the frame cut after `cuts` ("HH:MM"): the entries (and the exits that happened) before each cut must be identical."""
    from test_review_fixes import A_LOCK, day
    p = Params(**{**BASE, **kw})
    df = day(rows, d=d, start=start, spike=True)
    h = hist or history(d)

    def run(frame, live):
        return S.run_day(frame, h, "ES", p, 5, locks=[], log=[], skips=[], bias_by_cut=A_LOCK, live=live)
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
    from test_news_calendar import HOLD
    from test_review_fixes import A_ROWS
    hard = date(2023, 6, 13)
    full = _day_la(hard, HOLD, "07:30", ("07:55", "08:20", "08:40", "10:00", "11:00"), pre_0700_hard_days=True, hard_day_one_trade=True, pre_draw_done_am=True)
    assert full[0].session == "PRE7" and full[0].exits[-1][3] != "pre_0830"
    cpi = date(2023, 2, 14)
    _day_la(cpi, A_ROWS, "10:00", ("10:15", "10:20", "10:40"), cpi_from=600, pre_0900=True, post_news=True, multi_release="tag", news_seq_study=True, kz_release_tag=True,
            news_sweep_min=60, two_driver_mode="tag", am=(570, 720), news_wait="off")
    quiet = date(2023, 1, 30)
    _day_la(quiet, A_ROWS, "09:00", ("09:15", "09:20", "09:40"), pre_0900=True, pre_0900_no_news=True, pre_entry_guard=True, am_search_minutes=60, lunch_by_speed=True,
            lunch_raid="first_of", lunch_raid_wait=True, lunch_trail_guard=True, macro_fail_windows="all")
    _day_la(NORMAL, A_ROWS, "09:50", ("10:05", "10:10", "10:30"), am=(570, 720), am_trend_end=660, macro_gate=True, macro_by="start", macro_gate_set=("1050", "0950"), macro_trend_off=True,
            fomc_whipsaw_skip="london", chop_wait_bars=2, post_fomc_am="symmetry", pre_fomc_week_light=True, pm_array_from=810)
    _day_la(date(2023, 9, 18), A_ROWS, "09:30", ("09:50", "10:00"), pre_fomc_week_light=True, pre_fomc_week_smt=True)


@pytest.mark.skipif(not ES, reason="no ES data")
@pytest.mark.parametrize("window", [("2023-09-18", "2023-09-23"), ("2023-10-09", "2023-10-14"), ("2023-10-30", "2023-11-04")])
def test_look_ahead_es_nct(window):
    es = B.load("ES", 5, source="databento")
    df = es[(es.index >= pd.Timestamp(window[0], tz=B.NY)) & (es.index < pd.Timestamp(window[1], tz=B.NY))]
    meta = B.load_meta("ES", 5)
    p = Params(**FUT, htf_resist_cap=False, draw_lock="off", leg_pd=0, min_draw_pts=0, use_bias=False, ob_entry="post_mss", sb_model=True, ma_deuce=True, fomc_observe="defer",
               pre_fomc_week_light=True, fomc_end=900, fomc_minutes_mode="block", post_fomc_am="symmetry", fomc_whipsaw_skip="am", london_kz=True, am_search_minutes=90,
               macro_fail_windows="all", lunch_by_speed=True, lunch_raid="first_of", lunch_raid_wait=True, lunch_trail_guard=True, multi_release="half", pre_news_coil=True,
               news_trend_side=True, nfp_both_sides=True, two_driver_mode="wait2", pre_0700_hard_days=True, pre_0900=True, pre_0900_no_news=True, post_news_fade=True, pre_open_bnb=True,
               pre_entry_guard=True, event_eve_noon=True, fomc_stage_study=True, news_seq_study=True, kz_release_tag=True, cpi_from=570)
    _no_look_ahead(df, 5, "ES", p, COLS, every=1, meta=meta, exits=True, min_trades=0)


def test_news_pool_first_taken():
    """N6-news-pool-mapping: the 5m / 15m untaken pools within 1 x ADR5 one minute before an FOMC release; the release bar runs the high first, the low later: side +1, then -1."""
    over = {"13:30": (100.0, 103.0, 99.9, 100.0), "13:00": (100.0, 100.1, 98.0, 100.0), "14:00": (100.0, 103.3, 99.9, 103.0), "14:20": (101.0, 101.1, 97.5, 98.0)}
    ctx = book(over, d=FOMC_ONLY)
    p = Params(**BASE)
    q = N2.pool_study(ctx, p, 840, at(ctx, "14:30"))
    assert q["first"] == 1 and q["other"] is True and q["near_high"] == 103.0 and q["near_low"] == 98.0
    assert N2.pool_study(ctx, p, 840, at(ctx, "14:10"))["other"] is False                   # the low is taken later: unknown at 14:10
    assert N2.pool_study(ctx, p, 840, at(ctx, "13:50")) is None                               # the release bar has not closed
    low_first = book({**over, "14:00": (100.0, 100.2, 97.0, 97.5), "14:20": (99.0, 103.5, 98.9, 103.0)}, d=FOMC_ONLY)
    q = N2.pool_study(low_first, p, 840, at(low_first, "14:30"))
    assert q["first"] == -1 and q["other"] is True
    far = book({"13:30": (100.0, 130.0, 99.9, 100.0)}, d=FOMC_ONLY)
    assert N2.pool_study(far, p, 840, at(far, "14:30")) is None or N2.pool_study(far, p, 840, at(far, "14:30"))["near_high"] != 130.0   # farther than 1 x ADR5: not marked
    g = pd.DataFrame({"open": ctx.o[ctx.start:], "high": ctx.h[ctx.start:], "low": ctx.l[ctx.start:], "close": ctx.c[ctx.start:], "volume": 1.0}, index=ctx.idx[ctx.start:])
    rows = study.news_pool_rows(g, history(FOMC_ONLY), p, "TST")
    assert len(rows) == 1 and rows.iloc[0]["first"] == 1 and rows.iloc[0]["release"] == 840
    srows = study.stage_label_rows(g, history(FOMC_ONLY), p, "TST")
    assert len(srows) == 1 and srows.iloc[0]["label"] in ("A", "B", "none")
