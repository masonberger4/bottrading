"""Caption-gap pass, package setups_models #5/7, part A: the 36 specs of digests/rulebook_gaps/models_setups_entries.md (items 63, 64, 66, 68-70, 72, 75-81, 83, 84, 86-89, 91, 95, 98, 99, 101-112).
Unit tests of the detectors / gates (sm5.py) and of the engine glue (strategy / setups / levels / backtest hooks), Params plumbing. Tests that need local market data (ES) skip cleanly when it is
absent; no platform-specific paths. The study variants and the no-look-ahead runs live in test_caption_gap_sm5b.py."""
from dataclasses import replace
from datetime import date
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from mentorship import backtest as B, levels as L, setups as SM, sm2, sm3, sm4, sm5, strategy as S
from mentorship.strategy import Params

from test_levels_detectors import BASE, D0, NY, day, ctx_for, frame, history, prior_days, rth_day
from test_caption_gap_sm1a import StubConf, hist_close, ib, mkctx, sd_of, stub
from test_caption_gap_sm4a import cap  # noqa: F401  (cap: the order recorder fixture)

A = np.array

NEW_SWITCHES = (
    "ifvg_061_entry", "false_flag", "flag_min_bars", "flag_max_frac", "news_two_sided", "po3_15m", "po3_15m_n", "rb_second_dip", "org_reprice_full", "all_pools_first", "all_pools_names",
    "all_pools_pts", "lunch_org_ce_short", "dual_deal", "breaker_tf", "breaker_pref", "near_miss_pts", "ab_anchor_lock", "cisd_need_htf", "cisd_rearm", "max_stop_pts", "ifvg_targets",
    "ifvg_need_hunt", "pd50_bodies", "pd50_tf", "htf_overshoot_short", "overshoot_pts", "open_ob_min", "htf_entry_array", "td_same_level", "td_level_pts", "td_fallback", "mit_entry_tf",
    "mit_stair", "mb_order", "prev_reh_plan", "stop_zone_pool", "unicorn_standalone", "unicorn_tf", "max_retrace", "ifvg_open_mode", "ifvg_gap_pts", "array_fallback_breaker", "mm_oc_entry",
    "mm_accum_bars", "mm_accum_frac", "mm_stages", "mm_lowrisk", "mm_oc_frac", "mm_flip", "reclaimed_ladder", "reclaim_bounce_bars",
)


def test_new_switch_defaults_and_validation():
    p = Params()
    assert (p.ifvg_061_entry, p.false_flag, p.flag_min_bars, p.flag_max_frac, p.news_two_sided, p.po3_15m, p.po3_15m_n, p.rb_second_dip, p.org_reprice_full) == \
        ("market", "off", 5, 0.5, False, False, 3, False, False)
    assert (p.all_pools_first, p.all_pools_names, p.all_pools_pts, p.lunch_org_ce_short, p.dual_deal, p.breaker_tf, p.breaker_pref, p.near_miss_pts, p.ab_anchor_lock) == \
        ("off", ("london", "prev_ny"), 30.0, False, "", 0, "", 0.0, False)
    assert (p.cisd_need_htf, p.cisd_rearm, p.max_stop_pts, p.ifvg_targets, p.ifvg_need_hunt, p.pd50_bodies, p.pd50_tf, p.htf_overshoot_short, p.overshoot_pts, p.open_ob_min) == \
        (False, False, 0.0, False, False, False, 1, False, 3.0, 0)
    assert (p.htf_entry_array, p.td_same_level, p.td_level_pts, p.td_fallback, p.mit_entry_tf, p.mit_stair, p.mb_order, p.prev_reh_plan, p.stop_zone_pool) == \
        ("off", False, 2.0, False, "", False, "limit", False, False)
    assert (p.unicorn_standalone, p.unicorn_tf, p.max_retrace, p.ifvg_open_mode, p.ifvg_gap_pts, p.array_fallback_breaker, p.mm_oc_entry, p.mm_accum_bars, p.mm_accum_frac) == \
        (False, 1, 0.0, False, 5.0, False, False, 0, 1.0)
    assert (p.mm_stages, p.mm_lowrisk, p.mm_oc_frac, p.mm_flip, p.reclaimed_ladder, p.reclaim_bounce_bars) == (False, False, 0.8, False, False, 2)
    for kw in (dict(ifvg_061_entry="x"), dict(false_flag="x"), dict(all_pools_first="x"), dict(dual_deal="x"), dict(breaker_pref="x"), dict(htf_entry_array="x"), dict(mit_entry_tf="W"),
               dict(mb_order="x"), dict(flag_min_bars=1), dict(flag_max_frac=0), dict(po3_15m_n=0), dict(all_pools_names=("nope",)), dict(unicorn_tf=7), dict(max_retrace=1.0), dict(pd50_tf=0),
               dict(mm_oc_frac=0), dict(reclaim_bounce_bars=0), dict(near_miss_pts=-1), dict(max_stop_pts=-1), dict(turtle_soup="x"), dict(entry_arrays=("nope",)), dict(premise_tfs=(7,))):
        with pytest.raises(ValueError):
            Params(**kw)
    assert Params(turtle_soup="prev_pm").turtle_soup == "prev_pm" and Params(entry_arrays=("htf", "mitigation")).entry_arrays == ("htf", "mitigation") and Params(premise_tfs=(15, 1440))
    assert set(NEW_SWITCHES) <= set(Params.__dataclass_fields__)


# --- 63 M10-ifvg-fvg-signature-full ------------------------------------------------------------------------------------------------------------------

def test_ifvg_061_iofed_limit(cap):
    """061 ~02:18:22: ifvg_061_entry "iofed" - the IFVG with a normal FVG below it, a body close at that FVG's CE-top zone: a LIMIT at the FVG top + 1 tick (never above the market, never under
    the CE), the stop under the FVG, a trade under the CE cancels the pending order (cancel_low) and exits the position (manage: ifvg_ce); the default stays the market entry."""
    p = Params(**BASE, ifvg_entries=True, ifvg_061=True, ifvg_061_entry="iofed")
    rows = [(4010.0, 4011.0, 4005.0, 4006.0)] * 2 + [(4006.0, 4009.0, 4005.5, 4008.5), (4008.5, 4009.0, 4004.0, 4005.0)]
    ctx, (sl, ss) = mkctx(rows, base=4010.0, hist=hist_close(close=4010.0, hi=4130.0, lo=3900.0))
    i = ib(ctx, "09:30") + 3
    e = ib(ctx, "09:30")
    f = L.Zone("bull", 4010.0, 4004.0, e + 1, e)                       # the normal FVG below the IFVG
    z = L.Zone("bull", 4020.0, 4012.0, e + 2, e)
    sl._ifvg, sl.gaps = [z], [f]
    ctx.h[i], ctx.o[i], ctx.c[i] = ctx.h[i], ctx.o[i], ctx.c[i]
    sl.c[i] = 4008.0                                                    # a close between the CE (4007) and the top (4010)
    sl.o[i] = 4009.0
    sw = dict(session="AM", key="pdl1", name="pdl1", level=4000.0, ext=3999.0, ext_i=e, broke=e + 1, sweep_i=e, smt=None, smt2=None)
    assert SM.ifvg_061(ctx, sl, sw, i, p, "AM", 1.0) is not None
    assert cap["entry"] == pytest.approx(4008.0 - p.tick) and cap["entry"] >= f.mid and cap["stop"] == pytest.approx(4004.0 - p.pad)          # top + 1 tick (4010.25) is above the market: one tick under it
    assert cap["tags"]["cancel_low"] == pytest.approx(4007.0) and cap["tags"]["sm5"] == dict(kind="ifvg061", ce=4007.0) and "market" not in cap["tags"]
    sl.c[i] = 4008.0 + 6.0                                              # beyond the tolerance of the top: the 061 trigger itself does not fire
    assert SM.ifvg_061(ctx, sl, sw, i, p, "AM", 1.0) is None
    sl.c[i] = 4008.0
    assert SM.ifvg_061(ctx, sl, sw, i, replace(p, ifvg_061_entry="market"), "AM", 1.0) is not None and cap["tags"]["market"] is True and cap["entry"] == pytest.approx(4008.0)
    # the exit under the CE
    sd = sd_of([(4008.0, 4009.0, 4007.5, 4008.5), (4008.5, 4009.0, 4006.5, 4007.0)])
    pos = dict(fill_i=0, left=10, stop=4003.0, sm5=dict(kind="ifvg061", ce=4007.0))
    tr = SimpleNamespace(exits=[])
    sm5.manage(ctx, sd, pos, tr, 1, "t1", p)
    assert tr.exits == [("t1", 4007.0, 10, "ifvg_ce")] and pos["left"] == 0


# --- 64 new-false-bull-flag-short -------------------------------------------------------------------------------------------------------------------

def _flag_rows():
    pole = [(4050.0 - 10 * k, 4051.0 - 10 * k, 4040.0 - 10 * k, 4041.0 - 10 * k) for k in range(6)]               # a rapid drop 4050 -> 3990
    flag = [(3992.0, 3998.0, 3990.5, 3995.0), (3995.0, 3997.0, 3990.2, 3991.0), (3991.0, 3998.0, 3990.0, 3996.0), (3996.0, 3997.5, 3990.4, 3992.0), (3992.0, 3998.0, 3990.1, 3997.0),
            (3997.0, 3998.0, 3991.0, 3993.0)]
    sweep = [(3993.0, 3994.0, 3988.0, 3993.5)]
    return pole + flag + sweep


def test_false_flag_context_gate():
    """061 ~01:41:32: in side space a bear flag over the swept pool - a one-sided drop (the pole) then >= flag_min_bars bars whose range is within flag_max_frac of the pole, the pool at the flag's
    low - lying under the EQ of the previous day's range (the real flag above it) or in a same-side HTF array: tag false_flag + the flagpole origin as the first target rung; require drops the rest
    (a wide 'flag', a flag above the EQ without an HTF array, a pool away from the flag low)."""
    rows = _flag_rows()
    p = Params(**BASE, false_flag="tag")
    ctx, (sl, ss) = mkctx(rows, base=4050.0, hist=hist_close(close=4000.0, hi=4130.0, lo=3900.0))    # EQ of yesterday = 4015: the flag (3990-3998) sits under it
    e = ib(ctx, "09:30") + len(rows) - 1
    sw = dict(session="AM", key="pdl1", name="pdl1", level=3990.0, ext=3988.0, ext_i=e, broke=None, sweep_i=e, smt=None, smt2=None)
    fl = sm5.flag_info(ctx, sl, sw, e, p)
    assert fl is not None and fl["low"] == pytest.approx(3990.0) and fl["high"] == pytest.approx(3998.0) and fl["origin"] == pytest.approx(4051.0)
    lvt, tags = [], {}
    assert sm5.false_flag_gate(ctx, sl, sw, e, p, lvt, tags) is None and lvt == ["false_flag"] and tags["extra5"] == [(4051.0, "pool")]
    lvt2 = []
    assert sm5.false_flag_gate(ctx, sl, dict(sw, level=3970.0), e, p, lvt2, {}) is None and lvt2 == []                  # the pool is not at the flag's low: no tag
    assert sm5.false_flag_gate(ctx, sl, dict(sw, level=3970.0), e, replace(p, false_flag="require"), [], {}) == "x_false_flag"
    assert sm5.flag_info(ctx, sl, sw, e, replace(p, flag_max_frac=0.05)) is None                                        # too wide for a flag
    assert sm5.flag_info(ctx, sl, sw, e, replace(p, flag_min_bars=9)) is None                                           # nine bars back are pole bars: no flag
    ctx2, (sl2, _) = mkctx(rows, base=4050.0, hist=hist_close(close=3960.0, hi=3990.0, lo=3940.0))                   # yesterday's EQ 3965: the flag is ABOVE it (and no HTF array)
    assert sm5.false_flag_gate(ctx2, sl2, sw, e, replace(p, false_flag="require"), [], {}) == "x_false_flag"
    ctx2.hzones = [(L.Zone("bull", 3999.0, 3985.0, 0, 0), ctx2.idx[e - 3], 15)]
    ctx2.full_off, ctx2.full_idx, ctx2.full_c = 0, ctx2.idx, ctx2.c
    assert sm5.false_flag_gate(ctx2, sl2, sw, e, replace(p, false_flag="require"), [], {}) is None                     # ... but inside an HTF array: valid


# --- 66 M9-news-judas-full-sequence ------------------------------------------------------------------------------------------------------------------

def test_news_two_sided_waits_for_ce():
    """064 ~01:10:05: after the 08:30 release range (hi 4010, lo 3990, EQ 4000, 08:30 open 4001) is complete, BOTH extremes must be taken; the trade side = the one taken second (SSL then BSL =
    long); the order arms only after a bar trades back to the nearer of the range CE / the 08:30 open; the OB's MT is the exit line. Only one extreme taken, the wrong side, or no pullback = no order."""
    p = Params(**BASE, news_two_sided=True)
    rows = ([(4001.0, 4003.0, 3999.0, 4001.0), (4001.0, 4009.0, 3992.0, 4005.0), (4005.0, 4006.0, 3995.0, 4000.0), (4000.0, 4001.0, 3994.0, 3995.0)]    # 08:30-08:45: the range 3990?
            + [(3995.0, 3996.0, 3989.0, 3990.5), (3990.5, 4011.0, 3990.0, 4010.0), (4010.0, 4012.0, 4000.5, 4004.0)])
    ctx, (sl, ss) = mkctx(rows, base=4001.0, start="08:30", hist=hist_close(close=4001.0, hi=4130.0, lo=3900.0))
    k = ib(ctx, "08:30")
    ctx.news_dr = {510: dict(R=510, hi=4009.0, lo=3992.0, eq=4000.5, made=k + 3)}              # complete at the close of the 08:45 bar
    i = k + 6
    sw = dict(session="AM", key="news_range_510", name="x", level=3992.0, ext=3989.0, ext_i=k + 4, broke=k + 5, sweep_i=k + 4, smt=None, smt2=None)
    lvt, lvx = [], {}
    assert sm5.news_two_sided_gate(ctx, sl, sw, i, p, "AM", lvt, lvx) is None and "news_two_sided" in lvt                       # lo (k+4) first, hi (k+5) second -> long; the k+6 bar trades back to 4000.5 <= max(eq 4000.5, open 4001)
    assert sm5.news_two_sided_gate(ctx, ss, sw, i, p, "AM", [], {}) == "x_news_2s_side"                                      # the short side is the wrong one
    assert sm5.news_two_sided_gate(ctx, sl, sw, k + 4, p, "AM", [], {}) == "x_news_2s_wait"                                   # only the low was taken so far
    ctx.news_dr[510]["eq"] = 3996.0
    ctx.opens["0830"] = 3996.0
    assert sm5.news_two_sided_gate(ctx, sl, sw, i, p, "AM", [], {}) == "x_news_2s_pullback"                                   # price never came back to the CE / the open (low 4000.5)
    ctx.news_dr = {}
    assert sm5.news_two_sided_gate(ctx, sl, sw, i, p, "AM", [], {}) is None                                                  # no release range: not applicable


# --- 68 new-15m-candle-po3-upper-half ----------------------------------------------------------------------------------------------------------------

def _po3_rows():
    return [(4000.0, 4001.0, 3999.0, 4000.5), (4000.5, 4006.0, 4000.4, 4005.5), (4005.5, 4008.0, 4004.0, 4007.0),          # 09:30-09:45: up-close 15m bar, a bullish FVG 4001-4004
            (4007.0, 4009.0, 4006.5, 4008.0), (4008.0, 4010.0, 4007.5, 4009.0), (4009.0, 4013.0, 4008.5, 4012.0),            # 09:45-10:00 up
            (4012.0, 4014.0, 4011.5, 4013.0), (4013.0, 4015.0, 4012.5, 4014.0), (4014.0, 4017.0, 4013.5, 4016.0),            # 10:00-10:15 up
            (4016.0, 4016.5, 4013.0, 4014.0)]                                                                              # the bar that opens 10:15


def test_po3_15m_upper_half(cap):
    """065 ~04:29:00: at the bar that opens a 15m candle, with the last 3 closed 15m bars up-close and a bullish FVG below: a buy limit at the 15m open - 1 tick, cancelled by a trade under 50%
    of the prior 15m bar, cut at the 15m close; the target = the prior 15m high + its range; the exit line the FVG CE. No flow, no gap below, a non-15m-open bar or an off switch = nothing."""
    p = Params(**BASE, po3_15m=True)
    ctx, (sl, ss) = mkctx(_po3_rows(), base=4000.0, hist=hist_close(close=4000.0, hi=4130.0, lo=3900.0))
    i = ib(ctx, "10:15")
    assert sm5.po3_15m_order(ctx, sl, i, p, "AM", 1.0) is not None
    g = max((g for g in sl.gaps if g.i <= i and g.top < sl.o[i]), key=lambda g: g.top)                  # the nearest bullish FVG below the open
    assert cap["entry"] == pytest.approx(4016.0 - p.tick) and cap["stop"] == pytest.approx(g.bottom - p.pad)
    assert cap["fixed"] == [(S._exit_px(4017.0 + (4017.0 - 4011.5), "array", p), "array")] and cap["tags"]["cut"] == 10 * 60 + 30
    assert cap["tags"]["cancel_low"] == pytest.approx((4017.0 + 4011.5) / 2) and cap["tags"]["lvx"]["po3_15m_ce"] == (pytest.approx(g.mid), False)
    assert sm5.po3_15m_order(ctx, sl, i, p, "AM", 1.0) is None                                          # once per 15m open
    sl.__dict__.pop("_po3_15_sent")
    assert sm5.po3_15m_order(ctx, sl, i - 1, p, "AM", 1.0) is None                                      # not a 15m open
    assert sm5.po3_15m_order(ctx, sl, i, replace(p, po3_15m_n=4), "AM", 1.0) is None                    # only three closed 15m bars before it
    down = _po3_rows()
    down[8] = (4014.0, 4014.5, 4010.0, 4011.0)
    ctx2, (sl2, _) = mkctx(down, base=4000.0, hist=hist_close(close=4000.0, hi=4130.0, lo=3900.0))
    assert sm5.po3_15m_order(ctx2, sl2, ib(ctx2, "10:15"), p, "AM", 1.0) is None                        # the last 15m bar closed down: no bullish flow
    ctx.cur_bias = -1
    assert sm5.po3_15m_order(ctx, sl, i, p, "AM", 1.0) is None                                          # the bias is the other way


# --- 69 M12-new-trader-no-turtle-soup ----------------------------------------------------------------------------------------------------------------

def test_entry_style_tag():
    """065 ~03:01:01 / 066 ~00:31:09: the Trade carries entry_style - "raid" for the turtle-soup family and the pre-break OB, "confirmed" for the post-MSS FVG (and every other kind); no
    default changes."""
    for k in ("turtle_soup", "ob_pre", "ts_or60", "ts_cc_limit", "ts_external", "htf_stab", "smt_turtle"):
        assert sm5.entry_style(k) == "raid", k
    for k in ("fvg", "ifvg", "breaker", "arr_ob", "mitigation_entry", "unicorn_standalone", "ifvg_061"):
        assert sm5.entry_style(k) == "confirmed", k
    assert "entry_style" in S.Trade.__dataclass_fields__ and S.Trade.__dataclass_fields__["entry_style"].default == ""
    o = dict(session="AM", setup="am_mm", swept="pdl1", unicorn=False, smt=None, i=0, stop=1.0, t1=2.0, t2=None, shares=1, htf=None, macro=False, conf_n=None, conf_top="", conf_tfs="",
             entry_kind="ob_pre", mitigation=False, smt2=None, smt_n=0, macro_win="", td_agree=None, judas=False, propulsion=False)
    ctx, (sl, ss) = mkctx([(4000.0, 4001.0, 3999.0, 4000.0)] * 3, base=4000.0, hist=hist_close(close=4000.0, hi=4130.0, lo=3900.0))
    ctx.intermarket, ctx.day_tags = {}, ""
    tr = S._make_trade(ctx, ctx.day, "ES", o, sl, ctx.idx[1], 4000.0, 1, 570, Params(**BASE), {})
    assert tr.entry_style == "raid" and tr.row(0.0)["entry_style"] == "raid"


# --- 70 M12-turtle-soup-prev-pm-low ------------------------------------------------------------------------------------------------------------------

def test_turtle_prev_pm_low(cap):
    """067 ~00:20:12: turtle_soup "prev_pm" - the weekly bias this way and price near the previous 13:30-16:00 range at 09:30: a resting limit 1 tick under the range's low, the target the range's high,
    the stop ts_max_pts under the level; once a day; the weekly bias the other way / no range / a price far from it = nothing; the sweep path's _turtle ignores the value."""
    p = Params(**BASE, turtle_soup="prev_pm")
    ctx, (sl, ss) = mkctx([(4090.0, 4091.0, 4089.0, 4090.0)] * 3, base=4090.0, hist=hist_close(close=4090.0, hi=4130.0, lo=3900.0))
    ctx.sess["prev_pm"] = (4100.0, 4080.0, 0)
    ctx.wbias = 1
    i = ib(ctx, "09:30")
    assert sm5.prev_pm_limit(ctx, sl, i, p, "AM", 1.0) is not None
    assert cap["entry"] == pytest.approx(4080.0 - p.tick) and cap["stop"] == pytest.approx(4080.0 - p.tick - p.ts_max_pts * p.es_pt - p.pad)
    assert cap["fixed"] == [(S._exit_px(4100.0, "pool", p), "pool")] and cap["tags"]["no_expire"] is True
    assert sm5.prev_pm_limit(ctx, sl, i, p, "AM", 1.0) is None                                          # once a day
    sl.__dict__.pop("_ppm_sent")
    assert sm5.prev_pm_limit(ctx, ss, i, p, "AM", 1.0) is None                                          # the short Side: the weekly bias is long
    ctx.wbias = -1
    assert sm5.prev_pm_limit(ctx, sl, i, p, "AM", 1.0) is None
    ctx.wbias = 1
    assert sm5.prev_pm_limit(ctx, sl, i + 1, p, "AM", 1.0) is None                                      # only the 09:30 bar
    ctx.sess["prev_pm"] = (4300.0, 4280.0, 0)
    assert sm5.prev_pm_limit(ctx, sl, i, p, "AM", 1.0) is None                                          # the price is below the range (the limit would sit above the market)
    sw = dict(session="AM", key="pdl1", level=4000.0, ext=3999.0, ext_i=i, broke=None, sweep_i=i)
    assert S._turtle(ctx, sl, sw, i, p, "AM", 1.0) is None                                              # "prev_pm" is not a sweep-driven variant


# --- 72 M7-second-dip-into-rejection-block ----------------------------------------------------------------------------------------------------------

def _dip_rows():
    return [(4100.0, 4101.0, 4096.0, 4097.0), (4097.0, 4098.0, 4091.0, 4092.0), (4092.0, 4093.0, 4085.0, 4086.0),          # 13:30: the lunch low (4090) is swept, wick low L = 4085, close 4086
            (4086.0, 4092.0, 4085.5, 4091.0), (4091.0, 4097.0, 4090.5, 4096.0), (4096.0, 4096.5, 4087.0, 4087.2),            # a bounce, then back down
            (4087.2, 4087.5, 4085.6, 4086.5),                                                                                 # the dip: under RB (4086) above L (4085)
            (4086.5, 4089.0, 4086.2, 4088.8), (4088.8, 4093.0, 4088.0, 4092.5)]                                               # the rebound leaves a FVG 4087.5-4088


def test_second_dip_below_rb_above_low(cap):
    """067 ~01:05:38: the lunch low swept (wick L 4085), RB = the lowest close of that swing (4086); a later dip under RB that holds above L (4085.6) and the FVG its rebound leaves (4087.5-4088, in
    the discount of the move since L): a limit at its top, the stop under L, the targets the lunch high; the body-low cancel is replaced by L itself. A dip under L, one that stays above RB,
    no bounce first, or no array = nothing."""
    p = Params(**BASE, rb_second_dip=True)
    ctx, (sl, ss) = mkctx(_dip_rows(), base=4100.0, start="13:30", hist=hist_close(close=4100.0, hi=4130.0, lo=3900.0))
    ctx.sess["lunch"] = (4100.0, 4090.0, 810)
    i = ib(ctx, "13:30") + 8
    assert sm5.second_dip_order(ctx, sl, i, p, "PM", 1.0) is not None
    assert cap["entry"] == pytest.approx(4090.5) and cap["stop"] == pytest.approx(4085.0 - p.pad) and cap["tags"]["body_low"] == pytest.approx(4085.0)          # the highest array in the discount: the IFVG 4087.5-4090.5
    assert cap["fixed"] == [(S._exit_px(4100.0, "pool", p), "pool")] and "second_dip_ifvg" in cap["tags"]["lv_tags"]
    assert sm5.second_dip_order(ctx, sl, i, p, "PM", 1.0) is None or cap["entry"] == pytest.approx(4088.0)       # once per array (the next call may arm the lower FVG, never the IFVG again)
    sl.__dict__.pop("_rb2_sent")
    sl._ifvg = []
    assert sm5.second_dip_order(ctx, sl, i, p, "PM", 1.0) is not None and cap["entry"] == pytest.approx(4088.0) and "second_dip_fvg" in cap["tags"]["lv_tags"]       # without the IFVG: the FVG 4087.5-4088
    sl.__dict__.pop("_rb2_sent")
    assert sm5.second_dip_order(ctx, sl, i, p, "AM", 1.0) is None and sm5.second_dip_order(ctx, ss, i, p, "PM", 1.0) is None
    deep = _dip_rows()
    deep[6] = (4087.2, 4087.5, 4084.0, 4086.5)                                                          # the dip took L
    ctx2, (sl2, _) = mkctx(deep, base=4100.0, start="13:30", hist=hist_close(close=4100.0, hi=4130.0, lo=3900.0))
    ctx2.sess["lunch"] = (4100.0, 4090.0, 810)
    assert sm5.second_dip_order(ctx2, sl2, i, p, "PM", 1.0) is None
    shallow = _dip_rows()
    shallow[6] = (4087.2, 4087.5, 4086.4, 4086.8)                                                       # the dip stays above RB
    ctx3, (sl3, _) = mkctx(shallow, base=4100.0, start="13:30", hist=hist_close(close=4100.0, hi=4130.0, lo=3900.0))
    ctx3.sess["lunch"] = (4100.0, 4090.0, 810)
    assert sm5.second_dip_order(ctx3, sl3, i, p, "PM", 1.0) is None


# --- 76 M0-all-nearby-pools-run-first / 75 M8-org-repricing-full-conditions -----------------------------------------------------------------------

POOL_ROWS = [(4005.0, 4006.0, 4004.0, 4005.0), (4005.0, 4005.5, 3998.0, 3999.0), (3999.0, 4000.0, 3994.0, 3995.0), (3995.0, 4001.0, 3994.5, 4000.0)]


def test_wait_for_both_pools():
    """069 ~00:16:49: the listed Judas-side pools within all_pools_pts of the open (London low 3995; the prior NY low 3900 is 105 away) must all be run before the MSS entry counts: tag / require.
    Untaken pools = x_all_pools under require; no pool in range = nothing to wait for; the short Side reads the highs."""
    p = Params(**BASE, all_pools_first="tag")
    ctx, (sl, ss) = mkctx(POOL_ROWS[:2], base=4005.0, hist=hist_close(close=4005.0, hi=4130.0, lo=3900.0))
    ctx.sess["london"] = (4012.0, 3995.0, 300)
    i = ib(ctx, "09:30") + 1
    assert sm5.pools_taken(ctx, sl, i, p, ("london", "prev_ny"), 30.0, "AM") == (1, 0)             # the pool is listed (10 pts away), not run (low 3998)
    lvt = []
    assert sm5.all_pools_gate(ctx, sl, {}, i, p, "AM", lvt) is None and lvt == []
    assert sm5.all_pools_gate(ctx, sl, {}, i, replace(p, all_pools_first="require"), "AM", []) == "x_all_pools"
    ctx2, (sl2, ss2) = mkctx(POOL_ROWS, base=4005.0, hist=hist_close(close=4005.0, hi=4130.0, lo=3900.0))
    ctx2.sess["london"] = (4012.0, 3995.0, 300)
    j = ib(ctx2, "09:30") + 3
    assert sm5.pools_taken(ctx2, sl2, j, p, ("london", "prev_ny"), 30.0, "AM") == (1, 1)
    lvt = []
    assert sm5.all_pools_gate(ctx2, sl2, {}, j, replace(p, all_pools_first="require"), "AM", lvt) is None and lvt == ["all_pools"]
    assert sm5.pools_taken(ctx2, sl2, j, p, ("london", "prev_ny"), 200.0, "AM") == (2, 1)           # a wider net lists the prior NY low too: one of two run
    assert sm5.all_pools_gate(ctx2, sl2, {}, j, replace(p, all_pools_first="require", all_pools_pts=200.0), "AM", []) == "x_all_pools"
    assert sm5.pools_taken(ctx2, ss2, j, p, ("london",), 30.0, "AM") == (1, 0)                    # the short Side: London's HIGH 4012 never traded
    assert sm5.pools_taken(ctx2, sl2, j, p, ("london",), 5.0, "AM") == (0, 0)                     # nothing within 5 points of the open
    assert sm5.all_pools_gate(ctx2, sl2, {}, j, replace(p, all_pools_first="require", all_pools_pts=5.0), "AM", []) is None


def test_org_reprice_conditions(monkeypatch):
    """069 ~00:14:49: the ORG-first ladder (org_reprice_full) needs the Judas to run beyond the midnight open and take the London + prior-NY pools, a premium array at the sweep, an arming bar
    in 10:00-11:00 (the fill by 11:00: cut 660) and the ORG between the entry and the htf.table draw; each missing piece rejects."""
    p = Params(**BASE, org_reprice=True, org_reprice_full=True)
    rows = [(4003.0, 4004.0, 3990.0, 3992.0)] * 3
    ctx, (sl, ss) = mkctx(rows, base=4005.0, start="10:00", hist=hist_close(close=4005.0, hi=4130.0, lo=3900.0))
    ctx.org, ctx.org_today = [(4020.0, 4000.0)], True
    i = ib(ctx, "10:00") + 2
    sw = dict(session="AM", key="pdl1", level=3995.0, ext=3990.0, ext_i=ib(ctx, "10:00"), broke=None, sweep_i=ib(ctx, "10:00"))
    monkeypatch.setattr(sm5, "pools_taken", lambda *a, **k: (2, 2))
    monkeypatch.setattr(S, "_htf_tag", lambda *a, **k: True)
    monkeypatch.setattr(sm3, "row_draw", lambda *a, **k: (4040.0, "PDH"))
    tags = {}
    assert sm5.org_reprice_gate(ctx, sl, sw, i, p, "AM", 3995.0, tags) is None and tags["cut"] == 660
    assert sm5.org_reprice_gate(ctx, sl, sw, ib(ctx, "09:30") - 1, p, "AM", 3995.0, {}) == "x_org_reprice_time"          # before 10:00
    assert sm5.org_reprice_gate(ctx, sl, dict(sw, ext=4010.0), i, p, "AM", 3995.0, {}) == "x_org_reprice_midnight"       # the sweep did not run beyond the midnight open (4005)
    monkeypatch.setattr(sm5, "pools_taken", lambda *a, **k: (2, 1))
    assert sm5.org_reprice_gate(ctx, sl, sw, i, p, "AM", 3995.0, {}) == "x_org_reprice_pools"
    monkeypatch.setattr(sm5, "pools_taken", lambda *a, **k: (2, 2))
    monkeypatch.setattr(S, "_htf_tag", lambda *a, **k: False)
    assert sm5.org_reprice_gate(ctx, sl, sw, i, p, "AM", 3995.0, {}) == "x_org_reprice_array"
    monkeypatch.setattr(S, "_htf_tag", lambda *a, **k: True)
    monkeypatch.setattr(sm3, "row_draw", lambda *a, **k: (3999.0, "PDH"))                                                # the draw lies before the ORG
    assert sm5.org_reprice_gate(ctx, sl, sw, i, p, "AM", 3995.0, {}) == "x_org_reprice_draw"
    monkeypatch.setattr(sm3, "row_draw", lambda *a, **k: None)
    assert sm5.org_reprice_gate(ctx, sl, sw, i, p, "AM", 3995.0, {}) == "x_org_reprice_draw"                             # no forecast draw


# --- 77 M7-lunch-reprice-org-ce-moc -----------------------------------------------------------------------------------------------------------------

def test_lunch_org_ce_short(cap):
    """069 ~00:20:38: 12:00-13:30, the AM-locked draw (short, 3980) undelivered, today's ORG above (prior close 4020 -> open 4000): a short limit at the ORG CE (4010; mirrored -4010 in side
    space), the stop beyond the ORG's far edge (4020), the single target the locked draw, done key LOCS, held to the close; relative equal highs of the lunch session raise it; a delivered draw, the
    other side, an ORG on the near side or outside the lunch window = nothing."""
    p = Params(**BASE, lunch_org_ce_short=True)
    rows = [(4003.0, 4005.0, 4001.0, 4004.0)] * 3
    ctx, (sl, ss) = mkctx(rows, base=4004.0, start="12:00", hist=hist_close(close=4004.0, hi=4130.0, lo=3900.0))
    ctx.org, ctx.org_today = [(4020.0, 4000.0)], True
    ctx.lock = {"AM": dict(side=-1, target=3980.0, kind="pool", delivered=False)}
    i = ib(ctx, "12:00") + 2
    assert sm5.lunch_org_order(ctx, ss, i, p, 1.0) is not None
    assert cap["entry"] == pytest.approx(-4010.0) and cap["stop"] == pytest.approx(-4020.0 - p.pad) and cap["session"] == "PM"
    assert cap["fixed"] == [(S._exit_px(-3980.0, "pool", p), "pool")] and cap["tags"]["done_key"] == "LOCS" and cap["tags"]["exit_at"] == 960
    assert sm5.lunch_org_order(ctx, ss, i, p, 1.0) is None                                              # once a day
    ss.__dict__.pop("_locs_sent")
    assert sm5.lunch_org_order(ctx, sl, i, p, 1.0) is None                                              # the long Side: the lock is short
    ctx.lock["AM"]["delivered"] = True
    assert sm5.lunch_org_order(ctx, ss, i, p, 1.0) is None
    ctx.lock["AM"]["delivered"] = False
    ctx.org = [(4000.0, 4020.0)]
    assert sm5.lunch_org_order(ctx, ss, i, p, 1.0) is None                                              # the ORG is on the near side
    ctx.org = [(4020.0, 4000.0)]
    assert sm5.lunch_org_order(ctx, ss, ib(ctx, "11:50"), p, 1.0) is None                               # before 12:00
    assert sm5.any_special5(p) and not sm5.any_special5(Params(**BASE))


# --- 78 D15-dual-dealing ----------------------------------------------------------------------------------------------------------------------

def _dual_book(sym, side="long", entry="09:40", exit_="10:00", session="AM", **kw):
    d = dict(date="2026-06-23", session=session, setup="am_mm", symbol=sym, side=side, entry_time=f"2026-06-23 {entry}", exit_time=f"2026-06-23 {exit_}", exit_reason="t1", smt=False,
             gross=100.0, costs=2.0, net=98.0, entry_risk_pct=0.01, peak_risk_pct=0.012, R=1.5)
    d.update(kw)
    df = pd.DataFrame([d])
    for c in ("entry_time", "exit_time"):
        df[c] = pd.to_datetime(df[c]).dt.tz_localize(NY)
    return df


def test_combine_dual_deal_split():
    """069 ~00:19:09: dual_deal "split" keeps both same-session same-side fills at half risk each (gross / costs / net / risk x 0.5, dual_risk 0.5), "full" at full risk, "" the one-instrument pick;
    opposite sides or different sessions go through the ordinary pick."""
    es, nq = _dual_book("ES"), _dual_book("NQ", entry="09:41", exit_="10:01")
    assert list(B.combine(es, nq).symbol) == ["ES"]
    out = B.combine(es, nq, dual_deal="split")
    assert sorted(out.symbol) == ["ES", "NQ"] and list(out.dual_risk) == [0.5, 0.5] and list(out.net) == [49.0, 49.0] and list(out.gross) == [50.0, 50.0]
    assert list(out.entry_risk_pct) == [0.005, 0.005] and list(out.R) == [1.5, 1.5]
    full = B.combine(es, nq, dual_deal="full")
    assert sorted(full.symbol) == ["ES", "NQ"] and list(full.dual_risk) == [1.0, 1.0] and list(full.net) == [98.0, 98.0]
    nq_short = _dual_book("NQ", side="short", entry="09:41", exit_="10:01")
    one = B.combine(es, nq_short, dual_deal="split")
    assert list(one.symbol) == ["ES"] and list(one.dual_risk) == [1.0]                            # the other side: the ordinary pick
    pm = _dual_book("NQ", session="PM", entry="14:00", exit_="14:20")
    assert sorted(B.combine(es, pm, dual_deal="split").symbol) == ["ES", "NQ"] and set(B.combine(es, pm, dual_deal="split").dual_risk) == {1.0}     # different slots: both stay, at full risk
    assert B.combine(_dual_book("ES").iloc[:0], _dual_book("NQ").iloc[:0], dual_deal="split").empty
    with pytest.raises(ValueError):
        B.combine(es, nq, dual_deal="x")
    assert list(B.combine(es, dual_deal="split").symbol) == ["ES"]


# --- 79 M4-1m-last-upclose-finetune -----------------------------------------------------------------------------------------------------------------

def test_breaker_5m_zone_1m_last_upclose(cap):
    """070 ~00:55:41: breaker_tf 5 builds the breaker zone on the completed 5m bars; breaker_pref "last_1m" takes the LAST up-close base bar inside that zone before the run to the lower low as the
    entry block - a limit at its MT, filled only on a print 1 tick through. The base-bar zone and the zone top stay the default."""
    rows = [(4010.0, 4011.0, 4008.0, 4009.0), (4009.0, 4012.0, 4008.5, 4011.5), (4011.5, 4013.0, 4010.5, 4012.5), (4012.5, 4013.5, 4009.0, 4010.0), (4010.0, 4010.5, 4004.0, 4004.5),
            (4004.5, 4005.0, 4000.0, 4001.0), (4001.0, 4009.0, 4000.5, 4008.0), (4008.0, 4014.0, 4007.5, 4013.5)]
    p = Params(**BASE, breaker_entry="classic", breaker_pref="last_1m")
    ctx, (sl, ss) = mkctx(rows, base=4010.0, hist=hist_close(close=4010.0, hi=4130.0, lo=3900.0))
    e = ib(ctx, "09:30") + 5
    i = ib(ctx, "09:30") + 7
    sw = dict(session="AM", key="pdl1", name="pdl1", level=4004.0, ext=4000.0, ext_i=e, broke=e + 2, sweep_i=e, smt=None, smt2=None, ref_i=ib(ctx, "09:30") + 2)
    bz = L.Zone("bull", 4013.5, 4008.0, i, ib(ctx, "09:30") + 3, 4010.75)
    r = sm5.breaker_last_1m(ctx, sl, sw, bz, i, p)
    assert r is not None and r[0] == pytest.approx((4011.5 + 4008.5) / 2 if p.mt_mode != "body" else (4009.0 + 4011.5) / 2) or r is not None      # the last up-close bar inside [4008, 4013.5] before bar e
    k = max(k for k in range(ib(ctx, "09:30"), e) if sl.c[k] > sl.o[k] and sl.l[k] >= 4008.0 and sl.h[k] <= 4013.5)
    mt = (sl.o[k] + sl.c[k]) / 2 if p.mt_mode == "body" else (sl.h[k] + sl.l[k]) / 2
    assert r[0] == pytest.approx(mt) and r[1] == pytest.approx(sl.l[k])
    assert sm5.breaker_last_1m(ctx, sl, sw, L.Zone("bull", 4030.0, 4020.0, i, 0), i, p) is None      # no bar inside a zone elsewhere
    # the order: the MT replaces the zone top, a print 1 tick through fills
    S._breaker_order(ctx, sl, sw, bz, i, p, "AM", 1.0)
    assert cap["entry"] == pytest.approx(mt) and cap["tags"]["through"] == p.tick and "breaker_last_1m" in cap["tags"]["lv_tags"]
    S._breaker_order(ctx, sl, dict(sw), bz, i, replace(p, breaker_pref=""), "AM", 1.0)
    assert cap["entry"] == pytest.approx(4013.5) and "through" not in cap["tags"]
    # the zone on the 5m bars: base bars here ARE 5m bars, so breaker_tf 5 changes nothing; a 15m zone is built from the completed 15m buckets
    assert sm5.breaker_zone_tf(ctx, sl, ib(ctx, "09:30"), e, i, replace(p, breaker_tf=5)) is None
    z15 = sm5.breaker_zone_tf(ctx, sl, ib(ctx, "09:30"), e, i, replace(p, breaker_tf=15))
    assert z15 is None or (z15.kind == "bull" and z15.i == i)


# --- 80 M4-two-pool-breaker-near-miss ---------------------------------------------------------------------------------------------------------------

def test_near_miss_tag():
    """070 ~00:41:22: before the sweep bar a swing low within near_miss_pts ABOVE the swept pool formed after a bounce of at least that size = the near miss (tag); a swing farther away, one with
    a smaller bounce, or none = no tag; the switch off (0) never tags."""
    rows = [(4010.0, 4012.0, 4008.0, 4009.0), (4009.0, 4009.5, 4003.0, 4004.0), (4004.0, 4009.0, 4003.2, 4008.0), (4008.0, 4010.0, 4006.0, 4007.0), (4007.0, 4007.5, 3999.0, 3999.5)]
    ctx, (sl, ss) = mkctx(rows, base=4010.0, hist=hist_close(close=4010.0, hi=4130.0, lo=3900.0))
    e = ib(ctx, "09:30") + 4
    sw = dict(session="AM", key="pdl1", level=4000.0, ext=3999.0, ext_i=e, sweep_i=e, broke=None)
    p = Params(**BASE, near_miss_pts=4.0)
    lvt = []
    sm5.near_miss_tag(ctx, sl, sw, e + 2, p, lvt)
    assert lvt == ["near_miss"]                                                                      # the swing low 4003 (3 pts above the pool) bounced to 4010
    lvt = []
    sm5.near_miss_tag(ctx, sl, sw, e + 2, replace(p, near_miss_pts=2.0), lvt)
    assert lvt == []                                                                                 # 4003 is 3 pts above: outside 2 pts
    lvt = []
    sm5.near_miss_tag(ctx, sl, dict(sw, level=3990.0), e + 2, replace(p, near_miss_pts=4.0), lvt)
    assert lvt == []
    lvt = []
    sm5.near_miss_tag(ctx, sl, dict(sw, ext_i=ib(ctx, "09:30") + 1, sweep_i=ib(ctx, "09:30") + 1), e, p, lvt)
    assert lvt == []                                                                                 # the swing must precede the sweep bar


# --- 81 M4-unfinished-high-keep-ab-leg --------------------------------------------------------------------------------------------------------------

def test_ab_leg_not_reanchored(cap, monkeypatch):
    """070 ~00:52:42: with ab_anchor_lock the A-B leg of a FILLED advanced-breaker order stays the anchor while the locked target is untaken - a newer swing high below it does not re-anchor;
    before the fill, or once the target was taken, the new leg is used."""
    p = Params(**BASE, adv_breaker=True, ab_anchor_lock=True)
    rows = [(4010.0, 4020.0, 4008.0, 4015.0), (4015.0, 4016.0, 4005.0, 4006.0), (4006.0, 4007.0, 4000.0, 4001.0), (4001.0, 4012.0, 3999.0, 4011.0)]
    ctx, (sl, ss) = mkctx(rows, base=4010.0, hist=hist_close(close=4010.0, hi=4130.0, lo=3900.0))
    ctx.cur_session = "AM"
    e0 = ib(ctx, "09:30")
    sw = dict(session="AM", key="pdl1", level=4004.0, ext=3999.0, ext_i=e0 + 3, broke=e0 + 3, sweep_i=e0 + 3, smt=None, smt2=None)
    i = e0 + 3
    monkeypatch.setattr(SM, "_l1", lambda sd_, ref_i, i_: SimpleNamespace(price=4000.0, i=e0 + 2))
    assert SM.adv_breaker_order(ctx, sl, sw, i, p, "AM", 1.0, e0, 4020.0, True) is not None
    assert cap["entry"] == pytest.approx(4010.0) and cap["tags"]["sm5"] == dict(kind="ab_anchor")        # A = 4000, B = 4020: MT 4010
    # a newer, lower swing high 4015 (the next order's B) while the first order is still unfilled: the new leg re-anchors
    assert SM.adv_breaker_order(ctx, sl, sw, i, p, "AM", 1.0, e0, 4015.0, True) is not None and cap["entry"] == pytest.approx(4007.5)
    # fill the order: the anchor locks
    pos = {}
    sm5.on_fill(ctx, sl, pos, SimpleNamespace(lv_tags=""), dict(sm5=dict(kind="ab_anchor")), i, p)
    assert pos["sm5"]["kind"] == "ab_anchor" and sl._ab5["filled"] is True
    assert SM.adv_breaker_order(ctx, sl, sw, i, p, "AM", 1.0, e0, 4012.0, True) is not None and cap["entry"] == pytest.approx(4007.5)    # the locked leg (A 4000, B 4015), not the newer high 4012
    monkeypatch.setattr(S._SM, "htf_done", lambda *a, **k: True)                                         # the locked target was delivered
    assert SM.adv_breaker_order(ctx, sl, sw, i, p, "AM", 1.0, e0, 4012.0, True) is not None and cap["entry"] == pytest.approx(4006.0)
    off = replace(p, ab_anchor_lock=False)
    assert SM.adv_breaker_order(ctx, sl, sw, i, off, "AM", 1.0, e0, 4012.0, True) is not None and "sm5" not in cap["tags"]


# --- 83 M11-cisd-ob-stop-skip-rearm -----------------------------------------------------------------------------------------------------------------

def test_cisd_ob_rearm_after_low_break(cap, monkeypatch):
    """075 ~01:19:43: the CISD OB (the down-close series into the low; its high is the CISD level) arms on the first trade above it; cisd_need_htf: only when the sweep sits in a same-side HTF
    array; cisd_rearm: a trade under the OB low voids the setup and only a NEW CISD after it re-arms (default: once per sweep); the stop is the OB low less the pad."""
    rows = [(4010.0, 4011.0, 4004.0, 4005.0), (4005.0, 4006.0, 3997.0, 4005.5), (4005.5, 4012.0, 4005.0, 4011.0), (4011.0, 4011.5, 4003.0, 4003.5), (4003.5, 4005.0, 4003.2, 4004.5),
            (4004.5, 4013.0, 4004.2, 4012.0)]
    p = Params(**BASE, cisd_ob_entries=True)
    ctx, (sl, ss) = mkctx(rows, base=4010.0, hist=hist_close(close=4010.0, hi=4130.0, lo=3900.0))
    k0 = ib(ctx, "09:30")
    e = k0 + 1
    sw = dict(session="AM", key="pdl1", level=4000.0, ext=3997.0, ext_i=e, broke=None, sweep_i=e, smt=None, smt2=None)
    assert SM._cisd_ob(ctx, sl, sw, k0 + 1, p, "AM", 1.0) is None                                # no trade above the series' open yet
    assert SM._cisd_ob(ctx, sl, sw, k0 + 2, p, "AM", 1.0) is not None and sw["cisd_sent"] is True
    assert cap["stop"] == pytest.approx(4004.0 - p.pad) and cap["tags"]["cancel_low"] == pytest.approx(4004.0)
    assert SM._cisd_ob(ctx, sl, sw, k0 + 5, p, "AM", 1.0) is None                                # once per sweep: the trade under the OB low (bars 3-4) voids it, but the default does not re-arm
    pr = replace(p, cisd_rearm=True)
    sw2 = dict(session="AM", key="pdl1", level=4000.0, ext=3997.0, ext_i=e, broke=None, sweep_i=e, smt=None, smt2=None)
    assert SM._cisd_ob(ctx, sl, sw2, k0 + 2, pr, "AM", 1.0) is not None and sw2["cisd_floor"] == e
    assert SM._cisd_ob(ctx, sl, sw2, k0 + 5, pr, "AM", 1.0) is not None                          # a NEW CISD after the void re-arms
    assert sw2["cisd_floor"] == k0 + 4 and sw2["cisd_sent"] is True
    assert SM._cisd_ob(ctx, sl, sw2, k0 + 5, pr, "AM", 1.0) is None                              # ... once
    assert SM.pre_break(ctx, sl, dict(sw, cisd_sent=True), k0 + 5, pr, "AM", 1.0, 4010.0) is not None     # pre_break calls it again under cisd_rearm
    assert SM.pre_break(ctx, sl, dict(sw, cisd_sent=True), k0 + 5, p, "AM", 1.0, 4010.0) is None
    # the HTF context
    ph = replace(p, cisd_need_htf=True)
    monkeypatch.setattr(S, "_htf_tag", lambda *a, **k: False)
    fresh = lambda **k: dict(session="AM", key="pdl1", level=4000.0, ext=3997.0, ext_i=e, broke=None, sweep_i=e, smt=None, smt2=None, **k)
    assert SM._cisd_ob(ctx, sl, fresh(), k0 + 2, ph, "AM", 1.0) is None
    monkeypatch.setattr(S, "_htf_tag", lambda *a, **k: True)
    assert SM._cisd_ob(ctx, sl, fresh(), k0 + 2, ph, "AM", 1.0) is not None
    assert sm5.cisd_floor(fresh(), e, 4004.0, sl, k0 + 5, p) == e and sm5.cisd_floor(fresh(), e, 4004.0, sl, k0 + 5, pr) == k0 + 4


# --- 84 M10-ifvg-footholds-buy-program --------------------------------------------------------------------------------------------------------------

def test_ifvg_needs_stop_hunt():
    """075 ~01:29:33: an IFVG entry arms only after a short-term low under the price was run since the IFVG formed while no body closed under the IFVG CE; the prior down leg's open bearish FVGs
    are the buy-side targets (near edge, CE) after the MSS."""
    rows = [(110.0, 111.0, 109.0, 110.0), (110.0, 112.0, 109.5, 111.0), (111.0, 113.0, 110.0, 112.0), (112.0, 114.0, 111.0, 113.0), (113.0, 114.0, 106.0, 107.0), (107.0, 112.0, 107.0, 111.0),
            (111.0, 113.0, 110.0, 112.0), (112.0, 112.5, 105.5, 106.0), (106.0, 110.0, 106.0, 109.0)]
    sd = sd_of(rows)
    ctx = SimpleNamespace(start=0)
    p = Params(**BASE, ifvg_need_hunt=True)
    assert sm5.ifvg_hunt_ok(ctx, sd, 8, p, dict(fvg_i=3, fvg_ce=100.0)) is True                       # the pivot low 106 (bar 4) was run by bar 7
    assert sm5.ifvg_hunt_ok(ctx, sd, 8, p, dict(fvg_i=3, fvg_ce=108.0)) is False                      # a body closed under the CE (107)
    assert sm5.ifvg_hunt_ok(ctx, sd_of(rows[:7] + [(112.0, 113.0, 108.0, 111.0), (111.0, 112.0, 109.0, 111.0)]), 8, p, dict(fvg_i=3, fvg_ce=100.0)) is False      # no swing low was run
    assert sm5.ifvg_hunt_ok(ctx, sd, 8, p, dict(entry_kind="ifvg")) is True                            # no zone data: nothing to test
    # the targets: a bear FVG of the down leg (bar0 low 119 > bar2 high 117) that no high went into
    down = [(120.0, 121.0, 119.0, 119.5), (119.0, 119.5, 116.0, 116.5), (116.5, 117.0, 112.0, 113.0), (113.0, 114.0, 108.0, 109.0), (109.0, 110.0, 105.0, 106.0), (106.0, 108.0, 105.5, 107.0)]
    sd2 = sd_of(down)
    sw = dict(ext_i=4, broke=5)
    out = sm5.ifvg_target_levels(ctx, sd2, sw, 5, p, 106.0)
    assert (117.0, "array") in out and (118.0, "array") in out and all(k == "array" for _, k in out)               # the gap 117-119: near edge, CE
    assert sm5.ifvg_target_levels(ctx, sd2, dict(ext_i=4, broke=None), 5, p, 106.0) == []            # no MSS / CISD yet
    assert sm5.ifvg_target_levels(ctx, sd2, sw, 5, p, 125.0) == []                                   # nothing above the entry


# --- 86 A4-bodies-hold-prev-day-50 ------------------------------------------------------------------------------------------------------------------

def test_pd50_body_hold():
    """076 ~00:22:29: a sweep inside yesterday's range (3980-4020, 50% = 4000): no base-bar (or 5m) close under 4000 between the sweep extreme and now; one close under = x_pd50_bodies; a
    pending order is cancelled by such a close (cancel_close); a sweep outside the range is not judged; wicks may pierce."""
    p = Params(**BASE, pd50_bodies=True)
    hist = [rth_day(x, 4020.0, 3980.0, close=4000.0) for x in prior_days(D0, 8)]
    rows = [(4003.0, 4004.0, 3994.0, 4001.0), (4001.0, 4005.0, 3998.0, 4003.0), (4003.0, 4007.0, 4002.0, 4006.0)]
    ctx, (sl, ss) = mkctx(rows, base=4003.0, hist=hist)
    e = ib(ctx, "09:30")
    sw = dict(session="AM", key="pdl1", level=3995.0, ext=3994.0, ext_i=e, broke=e + 1)
    tags = {}
    assert sm5.pd50_gate(ctx, sl, sw, e + 2, p, tags) is None and tags["cancel_close"] == pytest.approx(4000.0)       # wicks pierced (3994 / 3998), every body closed at / above 4000
    bad = rows[:1] + [(4001.0, 4005.0, 3996.0, 3999.0)] + rows[2:]
    ctx2, (sl2, _) = mkctx(bad, base=4003.0, hist=hist)
    assert sm5.pd50_gate(ctx2, sl2, sw, e + 2, p, {}) == "x_pd50_bodies"
    assert sm5.pd50_gate(ctx2, sl2, dict(sw, ext=4030.0), e + 2, p, {}) is None                       # the sweep extreme is outside yesterday's range
    p15 = replace(p, pd50_tf=15)
    t15 = {}
    assert sm5.pd50_gate(ctx2, sl2, sw, e + 2, p15, t15) is None and "cancel_close" not in t15       # the completed 15m bars: none yet under 4000 (the 09:30 bucket closes at 09:45)
    ss_sw = dict(session="AM", key="pdh1", level=4005.0, ext=-4006.0, ext_i=e, broke=e + 1)
    assert sm5.pd50_gate(ctx, ss, ss_sw, e + 2, p, {}) == "x_pd50_bodies"                              # the short Side: bodies above 4000 (mirrored: under -4000) fail it


# --- 87 new-overshoot-ltf-fvg-into-htf-level ---------------------------------------------------------------------------------------------------------

def test_60m_overshoot_into_daily(cap, monkeypatch):
    """078 ~01:22:24: a 60m FVG whose near edge lies within overshoot_pts of the older daily FVG's near edge: a limit one tick beyond it (filled when price trades through), the stop beyond the
    swing that formed the leg - never beyond the FVG / the daily level -, cancelled when that swing is taken; one order per 60m FVG; too far = nothing."""
    p = Params(**BASE, htf_overshoot_short=True)
    rows = [(4010.0, 4011.0, 4008.0, 4009.0), (4009.0, 4010.0, 3996.0, 3997.0), (3997.0, 4015.0, 3997.0, 4014.0), (4014.0, 4016.0, 4013.0, 4015.0), (4015.0, 4016.0, 4010.0, 4011.0)]
    ctx, (sl, ss) = mkctx(rows, base=4010.0, hist=hist_close(close=4010.0, hi=4130.0, lo=3900.0))
    k0 = ib(ctx, "09:30")
    z = L.Zone("bull", 4008.0, 4002.0, k0 + 3, k0 + 2)
    monkeypatch.setattr(sm4, "_tf_fvgs", lambda ctx_, sd_, m: [z] if m == 60 else [])
    monkeypatch.setattr(sm4, "conf_arrays", lambda ctx_, sd_, i_, tfs, src=(0,), known_at_start=True: [(4000.0, 3990.0, "D")])
    i = k0 + 4
    assert sm5.overshoot_order(ctx, sl, i, p, "AM", 1.0) is not None
    assert cap["entry"] == pytest.approx(4002.0 - p.tick) and cap["stop"] == pytest.approx(3996.0 - p.pad) and cap["tags"]["cancel_low"] == pytest.approx(3996.0)
    assert "through" not in cap["tags"]                                                                  # a plain limit: filled when price trades through it
    assert sm5.overshoot_order(ctx, sl, i, p, "AM", 1.0) is None                                       # once per 60m FVG
    sl.__dict__.pop("_ovs_sent")
    assert sm5.overshoot_order(ctx, sl, i, replace(p, overshoot_pts=1.0), "AM", 1.0) is None            # the daily edge is 2 points away
    monkeypatch.setattr(sm4, "conf_arrays", lambda ctx_, sd_, i_, tfs, src=(0,), known_at_start=True: [(3990.0, 3980.0, "D")])
    assert sm5.overshoot_order(ctx, sl, i, p, "AM", 1.0) is None                                       # no daily FVG just under it
    monkeypatch.setattr(sm4, "conf_arrays", lambda ctx_, sd_, i_, tfs, src=(0,), known_at_start=True: [])
    assert sm5.overshoot_order(ctx, sl, i, p, "AM", 1.0) is None


# --- 88 new-open-returns-into-bearish-ob ------------------------------------------------------------------------------------------------------------

def test_open_into_ob_tag():
    """081 ~00:11:34: the entry OB formed BEFORE the 09:30 open and the fill within open_ob_min minutes after it = tag open_into_ob at the fill; an OB formed after the open, or a later fill, is
    not; 0 = off."""
    rows = [(4010.0, 4011.0, 4008.0, 4009.0), (4009.0, 4009.5, 4001.0, 4002.0), (4002.0, 4003.0, 3999.0, 4000.0), (4000.0, 4008.0, 3999.5, 4007.0), (4007.0, 4012.0, 4006.0, 4011.0)]
    p = Params(**BASE, open_ob_min=10)
    ctx, (sl, ss) = mkctx(rows, base=4010.0, start="09:15", hist=hist_close(close=4010.0, hi=4130.0, lo=3900.0))
    k = ib(ctx, "09:15")
    sw = dict(session="AM", key="pdl1", level=4001.0, ext=3999.0, ext_i=k + 2, broke=k + 3, sweep_i=k + 2)
    tags = {}
    sm5.open_ob_note(ctx, sl, sw, k + 4, p, "AM", tags)
    assert tags["sm5"]["open_ob"] == 570                                                             # the down-close series 09:20-09:25 is before the open
    tr = SimpleNamespace(lv_tags="")
    pos = {}
    ctx.t = np.array(ctx.t, copy=True)
    sm5.on_fill(ctx, sl, pos, tr, dict(sm5=dict(open_ob=570)), ib(ctx, "09:30") + 1, p)             # filled 09:35: 5 minutes after the open
    assert tr.lv_tags == "open_into_ob"
    tr2 = SimpleNamespace(lv_tags="")
    sm5.on_fill(ctx, sl, {}, tr2, dict(sm5=dict(open_ob=570)), ib(ctx, "09:30") + 3, p)             # filled 09:45: 15 minutes
    assert tr2.lv_tags == ""
    late = [(4010.0, 4011.0, 4008.0, 4009.0)] * 3 + [(4009.0, 4009.5, 4001.0, 4002.0), (4002.0, 4003.0, 3999.0, 4000.0), (4000.0, 4012.0, 3999.5, 4011.0)]
    ctx2, (sl2, _) = mkctx(late, base=4010.0, start="09:30", hist=hist_close(close=4010.0, hi=4130.0, lo=3900.0))
    k2 = ib(ctx2, "09:30")
    t2 = {}
    sm5.open_ob_note(ctx2, sl2, dict(sw, ext_i=k2 + 4, broke=k2 + 5, sweep_i=k2 + 4), k2 + 5, p, "AM", t2)
    assert t2 == {}                                                                                  # the OB formed after the open
    assert not sm5.any_gate5(Params(**BASE)) and sm5.any_gate5(p)


# --- 89 B5-ltf-at-htf-array ---------------------------------------------------------------------------------------------------------------------------

def test_htf_entry_array_tag(monkeypatch):
    """082 ~00:06:22: the entry inside a same-side 15m / 60m array (Confluence FVG / OB / VI or the day's own 15m / 60m FVG) = tag htf_entry_array; require drops the others; entry_arrays "htf"
    offers the arrays' near edges between the sweep extreme and the close."""
    rows = [(4020.0, 4021.0, 4019.0, 4020.0)] * 3
    conf = StubConf(arrays={1: [(4010.0, 4000.0, "15m", 0, 0), (4050.0, 4040.0, "4h", 0, 0)]})
    ctx, (sl, ss) = mkctx(rows, base=4020.0, hist=hist_close(close=4020.0, hi=4130.0, lo=3900.0), conf=conf)
    i = ib(ctx, "09:30") + 2
    p = Params(**BASE, htf_entry_array="tag")
    lvt = []
    assert sm5.htf_entry_gate(ctx, sl, i, p, 4005.0, lvt) is None and lvt == ["htf_entry_array"]
    lvt = []
    assert sm5.htf_entry_gate(ctx, sl, i, p, 4015.0, lvt) is None and lvt == []                      # between the arrays
    assert sm5.htf_entry_gate(ctx, sl, i, replace(p, htf_entry_array="require"), 4015.0, []) == "x_htf_entry_array"
    assert sm5.htf_entry_gate(ctx, sl, i, replace(p, htf_entry_array="require"), 4045.0, []) == "x_htf_entry_array"     # the 4h array is not a 15m / 60m one
    z = L.Zone("bull", 4016.0, 4012.0, i - 1, i - 2)
    monkeypatch.setattr(sm4, "_tf_fvgs", lambda ctx_, sd_, m: [z] if m == 60 else [])
    assert sm5.htf_entry_gate(ctx, sl, i, replace(p, htf_entry_array="require"), 4015.0, []) is None                 # the day's own 60m FVG
    sw = dict(session="AM", ext=4001.0, ext_i=i - 1)
    c = sm5.htf_cands(ctx, sl, sw, i, p)
    assert (4016.0, 4012.0, "htf") in c and (4010.0, 4000.0, "htf") in c                            # both lie above the sweep extreme 4001 and under the close 4020
    ea = replace(p, entry_arrays=("htf",))
    assert [x for x in SM.array_cands(ctx, sl, dict(sw, ext=3995.0, ext_i=i - 1), i, ea, None) if x[2] == "htf"]


# --- 91 M2-htf-ob-precondition ----------------------------------------------------------------------------------------------------------------------

def test_htf_ob_premise_daily():
    """087 ~00:05:51: premise_tfs may include 1440 - a same-side DAILY array (FVG or order block of the Confluence object, src 1) reached with the bodies holding is the premise (the pseudo-sweep
    htf_array); the default timeframes (15m / 60m) ignore it."""
    arr = {1: [(4050.0, 4040.0, "D", 1, 0)]}
    rows = [(4062.0, 4063.0, 4060.0, 4061.0)] * 3 + [(4061.0, 4061.5, 4049.0, 4052.0)] + [(4052.0, 4053.0, 4051.0, 4052.5)] * 2
    pd_ = Params(**BASE, allow_htf_array_premise=True, premise_tfs=(1440,))
    ctx, (sl, ss) = mkctx(rows, base=4062.0, p=pd_, conf=StubConf(arrays=arr), hist=hist_close(close=4062.0, hi=4130.0, lo=3900.0))
    k0 = ib(ctx, "09:30")
    sw = sm3.premise_sweep(ctx, sl, k0 + 3, pd_, "AM")
    assert sw is not None and sw["key"] == "htf_array" and sw["level"] == 4050.0 and sw["arr_bot"] == 4040.0
    ctx2, (sl2, _) = mkctx(rows, base=4062.0, p=pd_, conf=StubConf(arrays=arr), hist=hist_close(close=4062.0, hi=4130.0, lo=3900.0))
    assert sm3.premise_sweep(ctx2, sl2, k0 + 3, replace(pd_, premise_tfs=(15, 60)), "AM") is None
    assert Params(premise_tfs=(60, 1440)).premise_tfs == (60, 1440)


# --- 95 M2-three-drives-breaker-fallback ------------------------------------------------------------------------------------------------------------

def test_three_drives_breaker_fallback(cap, monkeypatch):
    """093 ~00:11:14: td_same_level - all three drives (the two swing lows and the extreme) within td_level_pts of the swept level; td_fallback - when the FVG order of a three-drives top expired
    unfilled the breaker of the top, where it overlaps an IFVG, arms a breaker order (once; nothing before the FVG order expired, with no overlap or with a live sweep)."""
    lows = [L.Pivot(2, 100.0, 3), L.Pivot(6, 98.0, 7)]
    assert L.three_drives(lows, 97.0, 10, 12) is True
    assert L.three_drives(lows, 97.0, 10, 12, 0, 98.0, 2.5) is True                                   # 100 / 98 / 97 all within 2.5 of the level 98
    assert L.three_drives(lows, 97.0, 10, 12, 0, 98.0, 1.5) is False                                  # 100 is 2 away
    assert L.three_drives(lows, 97.0, 10, 12, 0, None, 0.0) is True
    rows = [(4010.0, 4011.0, 4009.0, 4010.0)] * 14
    p = Params(**BASE, td_fallback=True, td_same_level=True, td_level_pts=2.0, three_drives="tag", ifvg_entries=True)
    ctx, (sl, ss) = mkctx(rows, base=4010.0, hist=hist_close(close=4010.0, hi=4130.0, lo=3900.0))
    k0 = ib(ctx, "09:30")
    sl.pl = [L.Pivot(k0 + 1, 4000.0, k0 + 2), L.Pivot(k0 + 5, 3998.0, k0 + 6)]
    sw = dict(session="AM", key="pdl1", level=3998.0, ext=3997.0, ext_i=k0 + 9, broke=k0 + 10, sweep_i=k0 + 9, ref_i=k0 + 3, smt=None, smt2=None)
    tags = {}
    assert sm5.order_gate5(ctx, sl, sw, k0 + 11, p, 4004.0, 3996.0, "AM", [], {}, tags) is None
    assert sl._td_fb["armed"] == k0 + 11 and sl._td_fb["ref_i"] == k0 + 3 and sl._td_fb["done"] is False       # remembered
    sl.pl = [L.Pivot(k0 + 1, 4004.0, k0 + 2), L.Pivot(k0 + 5, 3998.0, k0 + 6)]                          # drives 4004 / 3998 / 3997: not the same level
    del sl._td_fb
    sm5.order_gate5(ctx, sl, sw, k0 + 11, p, 4004.0, 3996.0, "AM", [], {}, {})
    assert not hasattr(sl, "_td_fb")
    sl.pl = [L.Pivot(k0 + 1, 4000.0, k0 + 2), L.Pivot(k0 + 5, 3998.0, k0 + 6)]
    sm5.order_gate5(ctx, sl, sw, k0 + 11, p, 4004.0, 3996.0, "AM", [], {}, {})
    bz = L.Zone("bull", 4006.0, 4001.0, k0 + 11, k0 + 7, 4003.5)
    monkeypatch.setattr(S, "_breaker", lambda *a, **k: bz)
    sl._ifvg = [L.Zone("bull", 4004.0, 4000.5, k0 + 12, k0 + 8)]
    assert sm5.td_fallback_order(ctx, sl, k0 + 12, p, "AM", 1.0) is None                              # the FVG order has not expired (armed at k0 + 11)
    i = k0 + 11 + max(1, p.pending_minutes // ctx.tf) + 1
    ctx2, (sl2, _) = mkctx(rows + [(4010.0, 4011.0, 4009.0, 4010.0)] * 12, base=4010.0, hist=hist_close(close=4010.0, hi=4130.0, lo=3900.0))
    sl2._td_fb = dict(sw=dict(sw), ref_i=k0 + 3, armed=k0 + 11, day=ctx2.day, done=False)
    sl2._ifvg = [L.Zone("bull", 4004.0, 4000.5, i, k0 + 8)]
    assert sm5.td_fallback_order(ctx2, sl2, i, p, "AM", 1.0) is not None and cap["entry"] == pytest.approx(4006.0)
    assert cap["stop"] == pytest.approx(3997.0 - p.pad) and cap["tags"]["entry_kind"] == "breaker"
    assert sm5.td_fallback_order(ctx2, sl2, i, p, "AM", 1.0) is None                                  # once
    sl2._td_fb["done"] = False
    sl2._ifvg = []
    assert sm5.td_fallback_order(ctx2, sl2, i, p, "AM", 1.0) is None                                  # no IFVG overlapping the breaker


# --- 98 A15-mitigation-block-entry (entry_arrays "mitigation") ---------------------------------------------------------------------------------------

def test_entry_arrays_mitigation_short():
    """098 ~00:45:55 (side space, the long here; the short is its mirror): entry_arrays "mitigation" - the alive mitigation block of the execution TF (or the daily bars with mit_entry_tf "D")
    the retrace reached: a limit at its near edge, the stop beyond the block's MT AND the adjacent FVG's far edge; only while the price is on the open's wrong side (under the midnight open for
    a long); a block closed through, or the price above the open, = no candidate."""
    rows = [(4004.0, 4005.0, 3999.0, 4000.0), (4000.0, 4003.0, 3997.0, 4002.0), (4002.0, 4009.0, 4001.0, 4008.0)]
    ctx, (sl, ss) = mkctx(rows, base=4010.0, hist=hist_close(close=4010.0, hi=4130.0, lo=3900.0))
    k0 = ib(ctx, "09:30")
    i = k0 + 2
    p = Params(**BASE, entry_arrays=("mitigation",))
    sl._mit = [L.Zone("bull", 4005.0, 3999.0, k0 + 1, k0, 4002.0)]
    sl.gaps = [L.Zone("bull", 4000.0, 3998.0, k0 + 1, k0)]                                              # an adjacent FVG reaching lower
    sw = dict(session="AM", ext=3997.0, ext_i=k0 + 1, key="pdl1")
    assert sm5.mit_cand(ctx, sl, sw, i, p) == (4005.0, 3998.0, "mitigation")
    assert [x for x in SM.array_cands(ctx, sl, sw, i, p, None) if x[2] == "mitigation"] == [(4005.0, 3998.0, "mitigation")]
    sl.gaps = []
    assert sm5.mit_cand(ctx, sl, sw, i, p) == (4005.0, 4002.0, "mitigation")                           # no FVG: the block's MT
    sl._mit = [L.Zone("bull", 4005.0, 4003.0, k0, k0, 4004.0)]                                          # the close at k0 + 1 (4002) went under its bottom: dead
    assert sm5.mit_cand(ctx, sl, sw, i, p) is None
    sl._mit = [L.Zone("bull", 4005.0, 3999.0, k0 + 1, k0, 4002.0)]
    ctx.opens["midnight"] = 4007.0                                                                      # the close (4008) is ABOVE the open: wrong side
    assert sm5.mit_cand(ctx, sl, sw, i, p) is None
    ctx.opens["midnight"] = 4010.0
    # the daily bars
    dc = np.array([4010.0, 4003.0, 4006.0, 4008.0])
    dsd = SimpleNamespace(c=dc, gaps=[], mitigations=lambda: [L.Zone("bull", 4005.0, 4001.0, 0, 0, 4003.0)])
    monkeypatch_daily = dsd
    S_daily = sm5.daily_side
    try:
        sm5.daily_side = lambda ctx_, sd_, p_: monkeypatch_daily
        assert sm5.mit_cand(ctx, sl, sw, i, replace(p, mit_entry_tf="D")) == (4005.0, 4003.0, "mitigation")
        dsd2 = SimpleNamespace(c=np.array([4010.0, 3999.0, 4006.0]), gaps=[], mitigations=lambda: [L.Zone("bull", 4005.0, 4001.0, 0, 0, 4003.0)])
        sm5.daily_side = lambda ctx_, sd_, p_: dsd2
        assert sm5.mit_cand(ctx, sl, sw, i, replace(p, mit_entry_tf="D")) is None                       # a daily close under the block's bottom
    finally:
        sm5.daily_side = S_daily


# --- 99 A15-stair-step-mitigation ------------------------------------------------------------------------------------------------------------------

def test_mitigation_stair_adds(cap, monkeypatch):
    """cc04_004 ~00:11:52: every swing the price CLOSED beyond is broken and the last candle at it (up-close in side space) becomes a mitigation block (whole range); mit_stair arms a limit at the
    newest block's near edge once price is back above it, the stop beyond its far edge; mb_order "stop" = a stop one tick beyond the block (price inside / under it); each LATER block is an add
    (once), none once the HTF target is delivered; bodies that violate a block (a close under its bottom) remove it."""
    rows = [(4000.0, 4004.0, 3999.0, 4003.0), (4003.0, 4008.0, 4002.0, 4005.0), (4005.0, 4006.0, 4001.0, 4002.0), (4002.0, 4003.0, 4000.0, 4001.0), (4001.0, 4012.0, 4000.5, 4011.0),
            (4011.0, 4012.0, 4009.0, 4010.0), (4010.0, 4010.5, 4007.0, 4007.5)]
    p = Params(**BASE, mit_stair=True)
    ctx, (sl, ss) = mkctx(rows, base=4000.0, bias=1, hist=hist_close(close=4000.0, hi=4130.0, lo=3900.0))
    k0 = ib(ctx, "09:30")
    bl = sm5.stair_blocks(ctx, sl, k0 + 5, p)
    assert len(bl) == 1 and bl[0]["top"] == 4008.0 and bl[0]["bottom"] == 4002.0 and bl[0]["j"] == k0 + 1 and bl[0]["broke"] == k0 + 4
    assert sm5.mit_stair_order(ctx, sl, k0 + 5, p, "AM", 1.0) is not None
    assert cap["entry"] == pytest.approx(4008.0) and cap["stop"] == pytest.approx(4002.0 - p.pad) and cap["tags"]["sm5"]["kind"] == "mit_stair" and cap["tags"]["no_expire"] is True
    assert sm5.mit_stair_order(ctx, sl, k0 + 5, p, "AM", 1.0) is None                                  # the first retrace only
    sl.__dict__.pop("_stair_sent")
    ctx.cur_bias = 0
    assert sm5.mit_stair_order(ctx, sl, k0 + 5, p, "AM", 1.0) is None                                  # no bias
    ctx.cur_bias = 1
    ps = replace(p, mb_order="stop")
    assert sm5.mit_stair_order(ctx, sl, k0 + 5, ps, "AM", 1.0) is None                                 # price (4010) is above the block: a stop would chase
    sl.__dict__.pop("_stair_sent", None)
    assert sm5.mit_stair_order(ctx, sl, k0 + 6, ps, "AM", 1.0) is not None
    assert cap["entry"] == pytest.approx(4008.0 + p.tick) and cap["tags"]["stop_entry"] is True       # price (4007.5) is inside the block: a buy stop one tick beyond its top
    bad = rows[:5] + [(4010.0, 4010.5, 3998.0, 4001.0)]
    ctx2, (sl2, _) = mkctx(bad, base=4000.0, bias=1, hist=hist_close(close=4000.0, hi=4130.0, lo=3900.0))
    assert sm5.mit_stair_order(ctx2, sl2, k0 + 5, p, "AM", 1.0) is None                                # a close under the block's bottom: violated
    # the adds
    armed = []
    monkeypatch.setattr(S, "_arm_add", lambda pos, tr, px, i_, p_, eq, **k: armed.append((px, k.get("floor"))))
    b2 = dict(top=4012.0, bottom=4009.0, j=k0 + 4, broke=k0 + 5)
    monkeypatch.setattr(sm5, "stair_blocks", lambda *a, **k: [bl[0], b2])
    pa = Params(**{**BASE, "adds": (0.5,)}, mit_stair=True)
    sd = sd_of([(4010.0, 4014.0, 4009.5, 4013.5)] * 4)
    pos = dict(fill_i=0, left=10, add=None, stop=4000.0, sm5=dict(kind="mit_stair", j=k0 + 1))
    tr = SimpleNamespace(adds=[], exits=[])
    ctx.lock = {}
    sm5.manage(ctx, sd, pos, tr, 3, "t", pa)
    assert armed == [(4012.0, 4009.0)] and k0 + 4 in pos["sm5"]["used"]
    sm5.manage(ctx, sd, pos, tr, 3, "t", pa)
    assert len(armed) == 1                                                                              # each block once
    ctx.lock = {"AM": dict(side=1, delivered_i=0)}
    pos2 = dict(fill_i=0, left=10, add=None, stop=4000.0, sm5=dict(kind="mit_stair", j=k0 + 1))
    sm5.manage(ctx, sd, pos2, tr, 3, "t", pa)
    assert len(armed) == 1                                                                              # the HTF target is delivered: no more adds


# --- 101 new-next-day-or-reh-short -------------------------------------------------------------------------------------------------------------------

def _reh_hist():
    """Previous session in 15m groups (3 x 5m): a rally with two equal 15m highs at 4020 / 4020.1 and the close 4000."""
    hs = [4000.0, 4003.0, 4020.0, 4008.0, 4006.0, 4020.1, 4007.0, 4005.0, 4003.0, 4002.0, 4001.0, 4001.0, 4001.0, 4001.0, 4001.0, 4001.0, 4001.0, 4001.0, 4001.0, 4001.0, 4001.0, 4001.0, 4001.0,
          4001.0, 4001.0, 4001.0]
    rows = []
    for h in hs:
        rows += [(h - 4.0, h, h - 6.0, h - 3.0)] * 3
    rows = rows[:-1] + [(4000.0, 4000.5, 3999.5, 4000.0)]
    d = prior_days(D0, 8)
    return [rth_day(x, 4010.0, 3995.0, close=4000.0) for x in d[:-1]] + [frame(d[-1], rows, 5, "09:30")]


def test_prev_day_reh_plan():
    """099 ~00:52:08 (the short; the long is the mirror): the prior day closed in the lower half of a daily bullish FVG and the overnight low held above the prior day's low = the plan: the prior
    day's 15m relative equal highs (4020 / 4020.1) are AM pools from 09:30 (side space: sell-side lows of the short), the target the swing before the sweep; no daily FVG / an overnight low under the
    prior low = no pools."""
    p = Params(**BASE, prev_reh_plan=True)
    conf = StubConf(arrays={1: [(4012.0, 3990.0, "D", 0, 0)]})
    rows = [(4003.0, 4004.0, 4002.0, 4003.0)] * 4
    ctx, (sl, ss) = mkctx(rows, base=4003.0, hist=_reh_hist(), conf=conf)
    ctx.pd["pml"] = 3996.0                                                                              # the overnight low held above the prior day's low (pdl1)
    i = ib(ctx, "09:30") + 1
    lv = sm5.prev_reh_levels(ctx, ss, i, p)
    assert len(lv) == 1 and abs(lv[0] - (-4020.1)) < 0.2
    out = {}
    sm5.pools5(ctx, ss, i, p, "AM", out)
    assert list(out) == ["prev_reh0"] and S._level_created(ctx, "prev_reh0", "AM") == ib(ctx, "09:30")
    out2 = {}
    sm5.pools5(ctx, ss, ib(ctx, "09:25"), p, "AM", out2)
    assert out2 == {}                                                                                   # not before 09:30
    sm5.pools5(ctx, ss, i, replace(p, prev_reh_plan=False), "AM", out2)
    assert out2 == {}
    ctx2, (sl2, ss2) = mkctx(rows, base=4003.0, hist=_reh_hist(), conf=StubConf(arrays={1: [(4040.0, 4030.0, "D", 0, 0)]}))
    ctx2.pd["pml"] = 3996.0
    assert sm5.prev_reh_levels(ctx2, ss2, i, p) == []                                                   # the prior close is not inside a daily FVG
    ctx3, (sl3, ss3) = mkctx(rows, base=4003.0, hist=_reh_hist(), conf=conf)
    ctx3.pd["pml"] = 3990.0                                                                             # the overnight traded under the prior day's low
    assert sm5.prev_reh_levels(ctx3, ss3, i, p) == []
    # the target: the last swing before the sweep (side space: the last pivot high)
    ss.ph = [L.Pivot(ib(ctx, "09:30"), -4005.0, ib(ctx, "09:30") + 1)]
    tags = {}
    sm5.reh_target(ctx, ss, dict(key="prev_reh0", ext_i=ib(ctx, "09:30") + 3), ib(ctx, "09:30") + 3, p, -4015.0, tags)
    assert tags["fixed4"] == [(S._exit_px(-4005.0, "pool", p), "pool")]
    t2 = {}
    sm5.reh_target(ctx, ss, dict(key="pdl1", ext_i=ib(ctx, "09:30") + 3), ib(ctx, "09:30") + 3, p, -4015.0, t2)
    assert t2 == {}


# --- 102 M2-skip-filter ------------------------------------------------------------------------------------------------------------------------------

def test_skip_when_pool_inside_stop(monkeypatch):
    """100 ~01:07:20: the order is dropped when an unraided pool (no wick through) or a level probed by >= 2 wicks with no body close beyond it lies between the entry and the stop (side space: under
    the entry, above the stop); a pool whose bodies closed beyond, the swept pool itself and pools outside the zone do not count."""
    rows = [(4020.0, 4021.0, 4019.0, 4020.0)] * 3 + [(4019.0, 4020.0, 4002.8, 4010.0), (4010.0, 4012.0, 4002.9, 4011.0), (4011.0, 4012.0, 4009.0, 4010.0)]
    ctx, (sl, ss) = mkctx(rows, base=4020.0, hist=hist_close(close=4020.0, hi=4130.0, lo=3900.0))
    i = ib(ctx, "09:30") + 5
    p = Params(**BASE, stop_zone_pool=True)
    sw = dict(session="AM", key="pdl1", level=3999.0, ext=3997.0, ext_i=ib(ctx, "09:30") + 3)
    monkeypatch.setattr(S, "_sell_side", lambda *a, **k: {"lunch": 4003.0})
    assert sm5.stop_zone_gate(ctx, sl, sw, i, p, "AM", 4011.0, 3995.0) == "x_stop_zone_pool"            # 4003 was poked twice by wicks (4002.8 / 4002.9) with no close under it
    assert sm5.stop_zone_gate(ctx, sl, sw, i, p, "AM", 4001.0, 3995.0) is None                         # the pool is above the entry: not in the stop zone
    assert sm5.stop_zone_gate(ctx, sl, sw, i, p, "AM", 4011.0, 4004.0) is None                         # ... or under the stop
    monkeypatch.setattr(S, "_sell_side", lambda *a, **k: {"x": 3999.0})
    assert sm5.stop_zone_gate(ctx, sl, dict(sw, level=3999.0), i, p, "AM", 4011.0, 3995.0) is None     # the swept pool itself
    bad = rows[:4] + [(4010.0, 4012.0, 4002.0, 4002.5)] + rows[5:]
    monkeypatch.setattr(S, "_sell_side", lambda *a, **k: {"lunch": 4003.0})
    ctx2, (sl2, _) = mkctx(bad, base=4020.0, hist=hist_close(close=4020.0, hi=4130.0, lo=3900.0))
    assert sm5.stop_zone_gate(ctx2, sl2, sw, i, p, "AM", 4011.0, 3995.0) is None                       # a body closed under 4003: it was raided
    monkeypatch.setattr(S, "_sell_side", lambda *a, **k: {"lunch": 4005.0})
    assert sm5.stop_zone_gate(ctx, sl, sw, i, p, "AM", 4011.0, 3995.0) == "x_stop_zone_pool"           # two wicks went through 4005 (lows 4002.8 / 4002.9), no body closed under it: still unraided


# --- 103 A14-unicorn-standalone -----------------------------------------------------------------------------------------------------------------------

UNI_ROWS = [(4000.0, 4001.0, 3999.0, 4000.0), (4000.0, 4010.0, 4000.0, 4009.0), (4009.0, 4009.5, 4004.0, 4005.0), (4005.0, 4006.0, 3998.0, 3999.0), (3999.0, 4003.0, 3999.5, 4002.0),
            (4002.0, 4012.0, 4001.0, 4011.0), (4011.0, 4013.0, 4007.0, 4012.0), (4012.0, 4012.5, 4008.0, 4009.0)]


def test_unicorn_standalone_60m(cap):
    """101 ~01:24:37 (side space; 5m bars here, the 60m case uses the same code on the completed buckets): a retrace into a same-side array forms the swing low 3998, a later close (4011) above
    the swing high before it (4010) is the MSS, the breaker (the leg's up-close candle 4000-4010) and a bullish FVG (4003-4007) overlap: a limit at the overlap's top (4007), the stop under the
    lower edge (4000), the single target = the nearest swing high above (4010), no adds, done key UNI; nothing without the array premise, once per swing, and not again once UNI is done."""
    p = Params(**BASE, unicorn_standalone=True, unicorn_tf=5)
    conf = StubConf(arrays={1: [(4000.0, 3996.0, "1h", 0, 0)]})
    ctx, (sl, ss) = mkctx(UNI_ROWS, base=4000.0, hist=hist_close(close=4000.0, hi=4130.0, lo=3900.0), conf=conf)
    ctx.done_ref = {}
    i = ib(ctx, "09:30") + 7
    assert sm5.unicorn_order(ctx, sl, i, p, "AM", 1.0) is not None
    assert cap["entry"] == pytest.approx(4007.0) and cap["stop"] == pytest.approx(4000.0 - p.pad) and cap["tags"]["done_key"] == "UNI" and cap["tags"]["single_exit"] is True
    assert cap["tags"]["no_adds"] is True and cap["fixed"] == [(S._exit_px(4010.0, "pool", p), "pool")] and cap["tags"]["entry_kind"] == "unicorn_standalone"
    assert sm5.unicorn_order(ctx, sl, i, p, "AM", 1.0) is None                                          # once per swing
    sl.__dict__.pop("_uni_sent")
    ctx.done_ref["UNI"] = True
    assert sm5.unicorn_order(ctx, sl, i, p, "AM", 1.0) is None                                          # the idea is done
    ctx.done_ref = {}
    ctx2, (sl2, _) = mkctx(UNI_ROWS, base=4000.0, hist=hist_close(close=4000.0, hi=4130.0, lo=3900.0), conf=StubConf(arrays={1: [(4040.0, 4030.0, "1h", 0, 0)]}))
    ctx2.done_ref = {}
    assert sm5.unicorn_order(ctx2, sl2, i, p, "AM", 1.0) is None                                        # the swing low is in no array / NWOG quadrant
    assert sm5.unicorn_order(ctx, sl, i, replace(p, unicorn_tf=7 if False else 1), "AM", 1.0) is None   # 1m bars cannot be built from 5m base bars
    sl.__dict__.pop("_uni_sent", None)
    assert sm5.unicorn_order(ctx, sl, i - 2, p, "AM", 1.0) is None                                      # before the FVG exists (it completes at bar 6)


# --- 104 M13-max-depth-79 ---------------------------------------------------------------------------------------------------------------------------

def test_fvg_beyond_79_dropped():
    """102 ~01:00:33: max_retrace 0.79 drops the entry FVGs whose NEAR edge lies deeper than 79% of the displacement leg (the leg high less the gap's top, over the leg); 0 = off."""
    sd = sd_of([(4000.0, 4001.0, 3999.0, 4000.5), (4000.5, 4020.0, 4000.0, 4019.0), (4019.0, 4020.0, 4010.0, 4012.0)])
    sw = dict(ext=4000.0, ext_i=0)
    a, b = L.Zone("bull", 4012.0, 4008.0, 2, 1), L.Zone("bull", 4004.0, 4001.0, 2, 1)
    p = Params(**BASE, max_retrace=0.79)
    assert sm5.depth_filter(sd, sw, [a, b], 2, p) == [a]                                               # depth 0.4 / 0.8
    assert sm5.depth_filter(sd, sw, [a, b], 2, replace(p, max_retrace=0.9)) == [a, b]
    assert sm5.depth_filter(sd, dict(ext=4020.0, ext_i=1), [a, b], 2, p) == [a, b]                      # no leg (the extreme is the high): untouched


# --- 105 M10-ifvg-open-dependent --------------------------------------------------------------------------------------------------------------------

def test_ifvg_open_dependent(cap, monkeypatch):
    """102 ~02:21:33 (side space, long): a daily IFVG 3990-4000 below; the 09:30 bar opens 10 pts away from the previous close (gap away from it, > ifvg_gap_pts): a resting limit at its near edge, the
    stop CE - 3.5 pts (the far edge with ifvg_depth when the IFVG had no prior pass); an open within the gap threshold pre-places nothing; once a day; only on the 09:30 bar."""
    rows = [(4020.0, 4021.0, 4019.0, 4020.0)] * 3
    ctx, (sl, ss) = mkctx(rows, base=4020.0, bias=1, hist=hist_close(close=4010.0, hi=4130.0, lo=3900.0))
    n = 4
    dsd = SimpleNamespace(c=np.array([4010.0, 4005.0, 4012.0, 4015.0]), h=np.array([4020.0, 4012.0, 4016.0, 4017.0]), l=np.array([4005.0, 4001.0, 4003.0, 4010.0]),
                          ifvgs=lambda: [L.Zone("bull", 4000.0, 3990.0, 1, 0)])
    monkeypatch.setattr(sm5, "daily_side", lambda ctx_, sd_, p_: dsd)
    p = Params(**BASE, ifvg_open_mode=True)
    i = ib(ctx, "09:30")
    assert sm5.ifvg_open_order(ctx, sl, i, p, "AM", 1.0) is not None
    assert cap["entry"] == pytest.approx(4000.0) and cap["stop"] == pytest.approx(3995.0 - 3.5 * p.es_pt - p.pad)
    assert sm5.ifvg_open_order(ctx, sl, i, p, "AM", 1.0) is None                                        # once a day
    sl.__dict__.pop("_ifo_sent")
    assert sm5.ifvg_open_order(ctx, sl, i, replace(p, ifvg_depth=True), "AM", 1.0) is not None
    assert cap["stop"] == pytest.approx(3990.0 - p.pad)                                                 # no pass through the IFVG: beyond its far edge
    sl.__dict__.pop("_ifo_sent")
    assert sm5.ifvg_open_order(ctx, sl, i + 1, p, "AM", 1.0) is None and sm5.ifvg_open_order(ctx, sl, i, p, "PM", 1.0) is None      # only the 09:30 bar of the AM
    assert sm5.ifvg_open_order(ctx, sl, i, replace(p, ifvg_gap_pts=15.0), "AM", 1.0) is None            # the open is only 10 points from the previous close: "relatively unchanged"
    ctx2, (sl2, _) = mkctx(rows, base=4020.0, bias=1, hist=hist_close(close=4018.0, hi=4130.0, lo=3900.0))
    assert sm5.ifvg_open_order(ctx2, sl2, i, p, "AM", 1.0) is None                                      # open 2 pts from the close: unchanged
    ctx.cur_bias = -1
    assert sm5.ifvg_open_order(ctx, sl, i, p, "AM", 1.0) is None                                        # the bias is the other way


# --- 106 M0-htf-array-not-reached -------------------------------------------------------------------------------------------------------------------

def test_fallback_15m_breaker(cap, monkeypatch):
    """103 ~00:29:15 (side space): the session lock on this side, the planned 1h / 4h array (3980-3990) under the price NOT reached today: a 15m breaker above it and under the locked draw arms a
    breaker order (limit at its top, stop under its bottom), once per breaker; a reached array, a delivered lock, the wrong side or a breaker beyond the draw = nothing."""
    rows = [(4020.0, 4021.0, 4019.0, 4020.0)] * 30
    conf = StubConf(arrays={1: [(3990.0, 3980.0, "1h", 0, 0)]})
    ctx, (sl, ss) = mkctx(rows, base=4020.0, hist=hist_close(close=4020.0, hi=4130.0, lo=3900.0), conf=conf)
    ctx.cur_lock = dict(side=1, target=4100.0, kind="pool", delivered=False)
    monkeypatch.setattr(L, "breakers", lambda o, h, l, c, n=2, mode="range": [L.Zone("bull", 4015.0, 4008.0, len(o) - 2, len(o) - 3, 4011.5)])
    i = ib(ctx, "09:30") + 29
    p = Params(**BASE, array_fallback_breaker=True)
    assert sm5.array_fb_order(ctx, sl, i, p, "AM", 1.0) is not None
    assert cap["entry"] == pytest.approx(4015.0) and cap["stop"] == pytest.approx(4008.0 - p.pad) and "array_fb_breaker" in cap["tags"]["lv_tags"]
    assert sm5.array_fb_order(ctx, sl, i, p, "AM", 1.0) is None                                         # once per breaker
    sl.__dict__.pop("_afb_sent")
    ctx.cur_lock["delivered"] = True
    assert sm5.array_fb_order(ctx, sl, i, p, "AM", 1.0) is None
    ctx.cur_lock = dict(side=-1, target=3900.0, kind="pool", delivered=False)
    assert sm5.array_fb_order(ctx, sl, i, p, "AM", 1.0) is None
    ctx.cur_lock = dict(side=1, target=4012.0, kind="pool", delivered=False)
    assert sm5.array_fb_order(ctx, sl, i, p, "AM", 1.0) is None                                         # the breaker (top 4015) lies beyond the draw
    ctx.cur_lock = dict(side=1, target=4100.0, kind="pool", delivered=False)
    ctx.l[ctx.start:] = np.minimum(ctx.l[ctx.start:], 3985.0)
    sl2 = S.Side(1, ctx.o, ctx.h, ctx.l, ctx.c, 1)
    assert sm5.array_fb_order(ctx, sl2, i, p, "AM", 1.0) is None                                        # the planned array WAS reached today


# --- 107 M1-original-consolidation-entry ----------------------------------------------------------------------------------------------------------

MM_ROWS = [(4018.0, 4020.0, 4016.0, 4019.0), (4019.0, 4021.0, 4017.0, 4018.0), (4018.0, 4020.0, 4016.0, 4019.5), (4017.0, 4017.5, 4010.0, 4011.0), (4011.0, 4012.0, 3998.0, 3999.0),
           (3999.0, 4004.0, 3999.0, 4003.0), (4003.0, 4015.0, 4002.0, 4014.0), (4014.0, 4024.0, 4013.0, 4022.0), (4022.0, 4026.0, 4021.0, 4025.0)]


def _mm_ctx(rows=MM_ROWS, **kw):
    ctx, sides = mkctx(rows, base=4018.0, hist=hist_close(close=4018.0, hi=4130.0, lo=3900.0), **kw)
    k0 = ib(ctx, "09:30")
    sw = dict(session="AM", key="pdl1", name="pdl1", level=4000.0, ext=3998.0, ext_i=k0 + 4, broke=k0 + 7, sweep_i=k0 + 4, ref_i=k0 + 1, smt=None, smt2=None)
    sides[0].__dict__["_mm5"] = sw
    return ctx, sides, k0, sw


def test_mm_original_consolidation_retest(cap):
    """104 ~00:32:10: the original consolidation (three touches of the body-edge 4019.5, its bars' low 4016): once a body CLOSED above its high (4022 at bar 7) a limit at that high (first return only),
    the stop under its midpoint (4017.75); a close not yet above, a price that already returned to the level, or an expired once-only flag = nothing."""
    p = Params(**BASE, mm_oc_entry=True)
    ctx, (sl, ss), k0, sw = _mm_ctx()
    oc = sm5.orig_consolidation(sl, sw, k0 + 8, p)
    assert oc == (pytest.approx(4019.5), pytest.approx(4016.0), pytest.approx(4017.75))
    assert sm5.mm_oc_order(ctx, sl, k0 + 8, p, "AM", 1.0) is not None
    assert cap["entry"] == pytest.approx(4019.5) and cap["stop"] == pytest.approx(4017.75 - p.pad) and cap["tags"]["no_expire"] is True and cap["tags"]["sm5"] == dict(kind="mm")
    assert sm5.mm_oc_order(ctx, sl, k0 + 8, p, "AM", 1.0) is None                                       # first return only
    sl.__dict__.pop("_mmoc_sent")
    assert sm5.mm_oc_order(ctx, sl, k0 + 6, p, "AM", 1.0) is None                                       # no body closed above the high yet (4014)
    back = MM_ROWS[:8] + [(4022.0, 4023.0, 4019.0, 4021.0)]
    ctx2, (sl2, ss2), _, _ = _mm_ctx(back)
    assert sm5.mm_oc_order(ctx2, sl2, k0 + 8, p, "AM", 1.0) is None                                     # the price already traded back to the level
    ctx3, (sl3, _), _, sw3 = _mm_ctx()
    sw3["broke"] = None
    assert sm5.mm_oc_order(ctx3, sl3, k0 + 8, p, "AM", 1.0) is None                                     # no MSS yet


# --- 108 M1-consolidate-at-discount-array ----------------------------------------------------------------------------------------------------------

def test_mm_accumulation_required(cap):
    """104 ~00:23:42: after the shift, a discount FVG (4002-4004, under the leg EQ 4004.5) the price goes sideways in: 3 consecutive bars closing inside it with a total range under 1.0 x the gap
    height arm a limit at its CE (4003); wider chop, closes outside, or the gap above the EQ = nothing; a body close under the gap's low cancels (cancel_close)."""
    rows = [(4003.0, 4004.0, 3999.0, 3999.5), (3999.5, 4002.0, 3999.2, 4001.5), (4001.5, 4008.0, 4001.0, 4007.0), (4007.0, 4010.0, 4004.0, 4009.0), (4004.0, 4004.0, 4002.5, 4003.8),
            (4003.8, 4004.0, 4002.8, 4003.2), (4003.2, 4003.9, 4002.6, 4003.6)]
    ctx, (sl, ss) = mkctx(rows, base=4003.0, hist=hist_close(close=4003.0, hi=4130.0, lo=3900.0))
    k0 = ib(ctx, "09:30")
    sw = dict(session="AM", key="pdl1", level=4000.0, ext=3999.0, ext_i=k0, broke=k0 + 2, sweep_i=k0, smt=None, smt2=None)
    sl.__dict__["_mm5"] = sw
    p = Params(**BASE, mm_accum_bars=3)
    i = k0 + 6
    assert [(g.top, g.bottom) for g in sl.gaps if g.i == k0 + 3] == [(4004.0, 4002.0)]
    assert sm5.mm_accum_order(ctx, sl, i, p, "AM", 1.0) is not None
    assert cap["entry"] == pytest.approx(4003.0) and cap["stop"] == pytest.approx(4002.0 - p.pad) and cap["tags"]["cancel_close"] == pytest.approx(4002.0)
    assert sm5.mm_accum_order(ctx, sl, i, p, "AM", 1.0) is None                                         # once per array
    sl.__dict__.pop("_mmacc_sent")
    assert sm5.mm_accum_order(ctx, sl, i, replace(p, mm_accum_bars=4), "AM", 1.0) is None               # only three bars inside so far
    assert sm5.mm_accum_order(ctx, sl, i, replace(p, mm_accum_frac=0.5), "AM", 1.0) is None             # the chop (1.5) is wider than half the gap height
    assert sm5.mm_accum_order(ctx, sl, i - 1, p, "AM", 1.0) is None


# --- 109 M1-accumulation-stages / 110 M1-distribution-stages-lowrisk-short ----------------------------------------------------------------------

def test_mm_stage_adds(cap, monkeypatch):
    """104 ~00:36:46: flat - the first stage entry is the sweep's bullish breaker order, then the CE of the newest FVG since the MSS (each once, not once the HTF target is delivered); after the
    first MM fill the next stages arm ADDS (the breaker top, then each later FVG's CE) with the E12 sizes."""
    rows = [(4003.0, 4004.0, 3999.0, 3999.5), (3999.5, 4002.0, 3999.2, 4001.5), (4001.5, 4008.0, 4001.0, 4007.0), (4007.0, 4010.0, 4004.0, 4009.0), (4009.0, 4010.0, 4005.0, 4006.0),
            (4006.0, 4016.0, 4005.5, 4015.0), (4015.0, 4018.0, 4012.0, 4017.0)]
    ctx, (sl, ss) = mkctx(rows, base=4003.0, hist=hist_close(close=4003.0, hi=4130.0, lo=3900.0))
    k0 = ib(ctx, "09:30")
    sw = dict(session="AM", key="pdl1", level=4000.0, ext=3999.0, ext_i=k0, broke=k0 + 2, sweep_i=k0, ref_i=k0 - 1, smt=None, smt2=None)
    sl.__dict__["_mm5"] = sw
    p = Params(**BASE, mm_stages=True)
    bz = L.Zone("bull", 4006.0, 4001.0, k0 + 6, k0 + 1, 4003.5)
    monkeypatch.setattr(S, "_breaker", lambda *a, **k: bz)
    i = k0 + 6
    assert sm5.mm_stage_order(ctx, sl, i, p, "AM", 1.0) is not None
    assert cap["entry"] == pytest.approx(4006.0) and cap["tags"]["entry_kind"] == "breaker" and sw["bz_sent"] is True                  # the first stage: the breaker
    assert sm5.mm_stage_order(ctx, sl, i, p, "AM", 1.0) is not None
    assert cap["tags"]["entry_kind"] == "mm_stage_bisi" and cap["entry"] == pytest.approx(float(max(g.mid for g in sl.gaps if g.i > k0 + 3 and g.i <= i)))     # the next stage: a later BISI's CE
    ctx.lock = {"AM": dict(side=1, delivered_i=0)}
    assert sm5.mm_stage_order(ctx, sl, i, p, "AM", 1.0) is None                                         # the HTF target is delivered
    ctx.lock = {}
    # the adds after the fill
    armed = []
    monkeypatch.setattr(S, "_arm_add", lambda pos, tr, px, i_, p_, eq, **k: armed.append(px))
    pa = Params(**{**BASE, "adds": (0.5, 0.5)}, mm_stages=True)
    st = dict(kind="mm", sw=sw)
    pos = dict(fill_i=k0 + 3, left=10, add=None, stop=3998.0, sm5=st)
    tr = SimpleNamespace(adds=[], exits=[])
    sm5.manage(ctx, sl, pos, tr, i, None, pa)
    assert armed == [4006.0] and st["bz"] is True                                                       # the breaker's top first
    sm5.manage(ctx, sl, pos, tr, i, None, pa)
    assert len(armed) == 2 and armed[1] < sl.c[i]                                                        # then a later FVG's CE
    assert sm5.need_note(pa) and not sm5.need_note(Params(**BASE))


def test_mm_lowrisk_short_60m_ce(cap, monkeypatch):
    """104 ~00:45:30 (side space): a 60m FVG (4000-4010) wicked UNDER (3998) with every body staying inside it, then an LTF MSS (a close above the swing high before the wick, 4012) = a limit at its CE
    (4005), the stop under the wick; 80% off at the original consolidation, the rest to the next HTF level; a body under the FVG, no MSS, or a live setup already sent = nothing."""
    rows = [(4004.0, 4005.0, 4000.5, 4002.0), (4002.0, 4010.0, 4001.0, 4009.0), (4009.0, 4012.0, 4008.0, 4009.5), (4009.5, 4010.0, 3998.0, 4001.0), (4001.0, 4014.0, 4000.5, 4013.0)]
    ctx, (sl, ss) = mkctx(rows, base=4004.0, hist=hist_close(close=4004.0, hi=4130.0, lo=3900.0))
    k0 = ib(ctx, "09:30")
    sw = dict(session="AM", key="pdl1", level=4000.0, ext=3998.0, ext_i=k0 + 3, broke=k0 + 4, sweep_i=k0 + 3, smt=None, smt2=None)
    sl.__dict__["_mm5"] = sw
    z = L.Zone("bull", 4010.0, 4000.0, k0 + 1, k0)
    monkeypatch.setattr(sm4, "_tf_fvgs", lambda ctx_, sd_, m: [z] if m == 60 else [])
    monkeypatch.setattr(sm5, "orig_consolidation", lambda *a, **k: (4020.0, 4016.0, 4018.0))
    monkeypatch.setattr(sm3, "htf_level_beyond", lambda *a, **k: 4040.0)
    p = Params(**BASE, mm_lowrisk=True)
    i = k0 + 4
    assert sm5.mm_lowrisk_order(ctx, sl, i, p, "AM", 1.0) is not None
    assert cap["entry"] == pytest.approx(4005.0) and cap["stop"] == pytest.approx(3998.0 - p.pad)
    assert cap["fixed"] == [(S._exit_px(4020.0, "pool", p), "pool"), (S._exit_px(4040.0, "array", p), "array")] and cap["tags"]["fracs"] == (0.8, pytest.approx(0.2))
    assert sm5.mm_lowrisk_order(ctx, sl, i, p, "AM", 1.0) is None                                       # once per FVG
    sl.__dict__.pop("_mmlr_sent")
    assert sm5.mm_lowrisk_order(ctx, sl, i - 1, p, "AM", 1.0) is None                                   # no MSS up yet (the close above 4012 is bar 4)
    body = rows[:3] + [(4009.5, 4010.0, 3998.0, 3999.5)] + rows[4:]
    ctx2, (sl2, _) = mkctx(body, base=4004.0, hist=hist_close(close=4004.0, hi=4130.0, lo=3900.0))
    sl2.__dict__["_mm5"] = dict(sw)
    assert sm5.mm_lowrisk_order(ctx2, sl2, i, p, "AM", 1.0) is None                                     # a body closed under the FVG's bottom


# --- 111 A18-curve-arrays-reverse-ladder -----------------------------------------------------------------------------------------------------------

REC_ROWS = [(4020.0, 4021.0, 4019.0, 4020.0), (4020.0, 4020.5, 4012.0, 4013.0), (4013.0, 4016.0, 4012.5, 4015.0), (4015.0, 4018.0, 4014.5, 4017.0), (4017.0, 4017.5, 4008.0, 4009.0),
            (4009.0, 4012.0, 4008.5, 4011.0), (4011.0, 4013.0, 4010.5, 4012.0), (4012.0, 4013.0, 4000.0, 4001.0), (4001.0, 4006.0, 3999.0, 4005.0), (4005.0, 4022.0, 4004.0, 4021.0)]


def test_reclaimed_ladder_sell_curve(cap, monkeypatch):
    """104 ~00:52:18: the reclaimed blocks of the curve's left leg (down-close candles each followed by >= 2 up-close bars, reclaimed by a close above their high) in order from the lowest: a limit at each
    block's top when flat (each once), a pyramid add per block after the fill; a close back under a block kills the rest; reclaim_bounce_bars 3 leaves no block. The sell curve is the mirror."""
    ctx, (sl, ss) = mkctx(REC_ROWS, base=4020.0, hist=hist_close(close=4020.0, hi=4130.0, lo=3900.0))
    k0 = ib(ctx, "09:30")
    sw = dict(session="AM", key="pdl1", level=4000.0, ext=3999.0, ext_i=k0 + 8, broke=k0 + 9, sweep_i=k0 + 8, smt=None, smt2=None)
    sl.__dict__["_mm5"] = sw
    p = Params(**BASE, reclaimed_ladder=True)
    i = k0 + 9
    bl = sm5.reclaim_blocks(ctx, sl, sw, i, p)
    assert [(z.top, z.bottom) for z in bl] == [(4017.5, 4008.0), (4020.5, 4012.0)]                      # lowest first
    assert sm5.reclaim_blocks(ctx, sl, sw, i, replace(p, reclaim_bounce_bars=3)) == []
    assert sm5.reclaim_order(ctx, sl, i, p, "AM", 1.0) is not None
    assert cap["entry"] == pytest.approx(4017.5) and cap["stop"] == pytest.approx(4008.0 - p.pad) and cap["tags"]["sm5"] == dict(kind="reclaim")
    assert sm5.reclaim_order(ctx, sl, i, p, "AM", 1.0) is not None and cap["entry"] == pytest.approx(4020.5)   # the next block
    assert sm5.reclaim_order(ctx, sl, i, p, "AM", 1.0) is None                                          # each block once
    armed = []
    monkeypatch.setattr(S, "_arm_add", lambda pos, tr, px, i_, p_, eq, **k: armed.append(px))
    pa = Params(**{**BASE, "adds": (0.5, 0.5)}, reclaimed_ladder=True)
    st = dict(kind="reclaim", sw=sw)
    pos = dict(fill_i=k0 + 8, left=10, add=None, stop=3998.0, sm5=st)
    tr = SimpleNamespace(adds=[], exits=[])
    sm5.manage(ctx, sl, pos, tr, i, None, pa)
    sm5.manage(ctx, sl, pos, tr, i, None, pa)
    assert armed == [4017.5, 4020.5]
    bad = REC_ROWS[:9] + [(4005.0, 4022.0, 4004.0, 4021.0)]
    bad[8] = (4001.0, 4006.0, 3999.0, 4005.0)
    ctx2, (sl2, _) = mkctx(bad, base=4020.0, hist=hist_close(close=4020.0, hi=4130.0, lo=3900.0))
    sl2.__dict__["_mm5"] = dict(sw)
    sl2.c[k0 + 9] = 4020.0                                                                                 # reclaims block 1 only (4017.5 < 4020 < 4020.5)
    assert [z.top for z in sm5.reclaim_blocks(ctx2, sl2, sw, i, p)] == [4017.5]
    ss_ = S.Side(-1, ctx.o, ctx.h, ctx.l, ctx.c, 1)
    assert isinstance(sm5.reclaim_blocks(ctx, ss_, dict(sw), i, p), list)                                # the mirror runs on the same code


# --- 112 M1-one-segment ---------------------------------------------------------------------------------------------------------------------------

def test_mm_no_flip_by_default():
    """104 ~00:09:27: an MM trade that reached its last ladder level ends the session for its side by default; with mm_flip the session reopens for the OPPOSITE side only (the delivered lock no
    longer gates it, the bias reading of the first leg does not either); once per session; non-MM trades are untouched."""
    p = Params(**BASE, mm_flip=True)
    tr = SimpleNamespace(final_hit=True, session="AM", side="long")
    done, state = {"AM": True}, {"only_side": {}}
    sm5.after_close(dict(sm5=dict(kind="mm")), tr, done, state, Params(**BASE))
    assert done["AM"] is True and "mm_flip" not in state                                              # the default: done
    sm5.after_close(dict(sm5=dict(kind="mm")), tr, done, state, p)
    assert done["AM"] is False and state["only_side"]["AM"] == -1 and state["mm_flip"]["AM"] is True
    done["AM"] = True
    sm5.after_close(dict(sm5=dict(kind="mm")), tr, done, state, p)
    assert done["AM"] is True                                                                          # once per session
    d2, s2 = {"AM": True}, {"only_side": {}}
    sm5.after_close(dict(sm5=dict(kind="mm")), SimpleNamespace(final_hit=False, session="AM", side="long"), d2, s2, p)
    assert d2["AM"] is True                                                                            # the trade did not reach its last level
    sm5.after_close(dict(sm5=dict(kind="mit_stair")), tr, d2, s2, p)
    assert d2["AM"] is True                                                                            # not an MM trade
    d3, s3 = {"PM": True}, {"only_side": {}}
    sm5.after_close(dict(sm5=dict(kind="mm")), SimpleNamespace(final_hit=True, session="PM", side="short"), d3, s3, p)
    assert d3["PM"] is False and s3["only_side"]["PM"] == 1
