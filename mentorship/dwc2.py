"""Caption-gap pass, package day_week_context#2/3 (digests/rulebook_gaps/day_selection_news_calendar.md items 48, 50, 53-57, 59-73, 77; definitions_pd_arrays_structure.md 125, 206, 207;
levels_liquidity_targets.md 63, 81, 97, 122, 157, 160; management_partials_trailing_exits.md 30, 118; build_log.md).

The day / week templates and day-selection rules of the day_week_context package that were not in dwc1.py: the consolidation modes, the strict expansion day, the expansion candidate, the
trending-day direction, the Friday rules (delivered before the open, the pool choice, the tight trail, the TGIF reversal flag and daily-FVG CE cap), the big Monday into a daily array,
the Mon-Wed / Thu-Fri day selection, the Thursday-noon cut-off, the Thursday false-break reversal, the NY continuation gate, the ADR-filled-news exemption, the London-low guard, the London
filters, the true-day close, the PO3 small open wick, the ADR runner / fib close zone and the day-summary reporting fields. The weekly profile STUDIES (items 59, 61, 62, 64, 65, 68, 69, 70,
122) live in study_week.py. Everything reads completed daily candles (`hist`), the calendar, or today's bars that have closed (index <= the caller's bar i). Thresholds the sources never give
are marked [our interpretation]. Every rule is a Params switch (off by default).

Pieces (the engine hooks that call them)
  calendar_block   days_mode (Mon-Wed / Tue-Wed days)                                                                     (strategy.blocked, after dwc1.calendar_block)
  plan_rules       the DayPlan part: modes, tags, blocks, info                                                            (daycontext.plan tail, after dwc1.plan_rules)
  gate             per-bar gates: Monday big-into-array, London low guard, London filters                                 (daycontext.gate tail)
  side_ok          side filters: Friday delivered stop, NY continuation, Thursday noon, trend side, PO3 invalid ...       (daycontext.side_ok tail)
  order_ok         per-order filters: consolidation range trade, Tuesday off Monday's OTE, TGIF daily-FVG cap ...        (daycontext.order_ok tail)
  size_mult        Monday big-into-array risk x 0.5                                                                       (daycontext.day_risk)
  day_params       expansion_mode "full", Friday single exit, consolidation "scalp" outs                                  (strategy._run_day_once)
  entry_tags       per-trade tags (thu_reversal, wk_ext_candidate, adr_filled_news ...)                                   (daycontext.stamp)
  am_exit_for / adr_close_exit / fri_trail  the position-loop hooks (items 118, 160, 30)                                    (strategy._run_day_once)
  day_summary      the per-day reporting fields (items 63 legs5, 157 PDH / PDL touch, 160 ADR close zone, 118 contraction, 207)  (backtest.run)
"""
from __future__ import annotations

from collections import Counter
from datetime import date, timedelta

import numpy as np
import pandas as pd

from claude_hf.daytypes import events
from . import calendar as CAL
from . import dwc1 as D1
from . import levels as L

HITS: Counter = Counter()


def hit(k: str) -> None:
    """Executed-path counter (the look-ahead tests assert the switches act in their window)."""
    HITS[k] += 1


def _S():
    from . import strategy as S
    return S


def _DW():
    from . import daycontext as DW
    return DW


def _cache(ctx) -> dict:
    return ctx.__dict__.setdefault("_dwc2", {})


def _bias(ctx, p, i):
    """The htf table bias (the org_bias_src column) at the closed bar i; 0 before 09:30 (the table is cut there)."""
    return _DW()._bias_side(ctx, p, i)


def _draw(ctx, i):
    from .entries import bias_row_known
    row = bias_row_known(ctx, i)
    try:
        return 0 if row is None else int(row["draw"])
    except Exception:
        return 0


def _combo(ctx, i):
    """The htf.table 'bias' of the closed bar i (the combo column; the draw column when the row has none) - the 'HTF bias != 0' of item 48 (the table is cut at 09:30)."""
    from .entries import bias_row_known
    row = bias_row_known(ctx, i)
    if row is None:
        return 0
    for k in ("combo", "draw"):
        try:
            v = int(np.sign(float(row[k])))
        except Exception:
            continue
        return v
    return 0


def _react(ctx, i):
    from .entries import bias_row_known
    row = bias_row_known(ctx, i)
    try:
        return 0 if row is None else int(row["react"])
    except Exception:
        return 0


def _rng(x) -> float:
    return float(x.high.max() - x.low.min())


# --------------------------------------------------------------------------------------------------------------
# weekly bias (items 57, 60, 62, 67, 68)
# --------------------------------------------------------------------------------------------------------------

def carried_bias(hist, d: date) -> int:
    """NEW mw_carry (item 60, cc07_001 ~00:44:15): "if the target is not reached that week, keep the same bias for the next week". The bias the PREVIOUS completed week started with (weekly tone
    before that week) is carried when that week did not reach its target, [our interpretation] the weekly draw = the highest high (lowest low) of the four weeks before it, if beyond its open.
    0 when the week had no bias or reached the target."""
    wb = D1._week_bars(hist, d)
    if len(wb) < 2:
        return 0
    o, h, l, c, first = wb[-1]
    b = D1.weekly_state(hist, first)
    if not b:
        return 0
    prior = wb[-5:-1]
    if not prior:
        return 0
    if b > 0:
        tgt = max(x[1] for x in prior)
        return b if (tgt > o and h < tgt) else 0
    tgt = min(x[2] for x in prior)
    return b if (tgt < o and l > tgt) else 0


def weekly_bias(ctx, hist, d: date, p) -> int:
    """The weekly bias used by the week templates: the weekly tone from the completed weeks, else the flip state (the htf table); with `mw_carry` a missed target carries the previous week's bias."""
    c = _cache(ctx)
    k = ("wb", d, bool(p.mw_carry))
    if k not in c:
        b = 0
        if p.mw_carry:
            b = carried_bias(hist, d)
        if b and b != D1.weekly_state(hist, d):
            hit("mw_carry")                                   # the carried bias differs from the plain weekly tone: the switch acted
        c[k] = b or D1.weekly_state(hist, d) or D1.flip_state(ctx, hist, d)
    return c[k]


def mw_delivered(hist, d: date, bias: int, a5) -> bool:
    """Item 67 (cc12_004 ~00:06:30): by the Wednesday close the week moved >= 1 x ADR5 (the sources give no figure, [our interpretation]) in the weekly-bias direction from the Monday open.
    No bias or no ADR5 = not delivered (the Thu / Fri templates stay available)."""
    if not bias or not a5:
        return False
    wk = [x for x in D1._this_week(hist, d) if x.index[0].date().weekday() <= 2]
    if not wk:
        return False
    op = float(wk[0].open.iloc[0])
    if bias > 0:
        return float(max(x.high.max() for x in wk)) - op >= a5
    return op - float(min(x.low.min() for x in wk)) >= a5


# --------------------------------------------------------------------------------------------------------------
# calendar block (items 66 / 67)
# --------------------------------------------------------------------------------------------------------------

def calendar_block(d: date, session: str, p, t: int = 0):
    """Item 66 DS2-monday-ideal-day (cc08_007 ~7:17; cc12_004 ~6:30): `days_mode` "mon_wed" blocks Thursday / Friday, "tue_wed" also Monday. With `late_week_fallback` (item 67) the
    Thursday / Friday block is decided in plan_rules (the Mon-Wed move delivered or not) instead of here."""
    if p.days_mode == "all":
        return None
    wd = d.weekday()
    if p.days_mode == "tue_wed" and wd == 0:
        return "days_mode"
    if wd in (3, 4) and not p.late_week_fallback:
        return "days_mode"
    return None


# --------------------------------------------------------------------------------------------------------------
# the DayPlan part
# --------------------------------------------------------------------------------------------------------------

def _adr60_values(hist, n: int = 60) -> list:
    """Rolling ADR5 values over the last `n` sessions (each from the five sessions before it); oldest first."""
    lo = max(5, len(hist) - n)
    rr = np.array([_rng(x) for x in hist[lo - 5:]], float)            # one pass over the frames, then the rolling 5-session mean
    if len(rr) < 5:
        return []
    return [float(v) for v in np.convolve(rr, np.ones(5) / 5.0, mode="valid")]


def adr_contracted(hist, p=None) -> bool:
    """Item 118 (a) (cc09_008 ~00:47:45): ADR5 contracted = today's ADR5 (the last five sessions) in the bottom tercile of the last 60 sessions' ADR5 values [our interpretation for an index; FX < 60 pips].
    Needs 20 values."""
    v = _adr60_values(hist)
    if len(v) < 20 or float(np.ptp(v)) <= 0:
        return False
    return bool(v[-1] <= float(np.percentile(v, 100.0 / 3.0)) + 1e-12)


def _eq60(hist) -> float | None:
    w = hist[-60:]
    if len(w) < 20:
        return None
    return (max(float(x.high.max()) for x in w) + min(float(x.low.min()) for x in w)) / 2.0


def trend_side(d: date, p, hist, eth, a5):
    """Item 54 DS2-trending-day-direction (cc10_009 ~1:17-2:46, ~4:15). Returns the expected side (+1 / -1) when the recipe holds, else None:
      (1) "small" = the previous daily range is the smallest of the prior 5 [our threshold], OR the ranges contracted over the last 3 days (strictly decreasing);
      (2) those days recently (the last 3 sessions) traded down into a daily bullish FVG below the 60-day EQ (mirror: up into a bearish FVG above it). [our interpretation] the "daily discount
          array" is the daily FVG only (htf._arrays also has daily order blocks - not armed here) and "recently" = the last 3 sessions;
      (3) high / medium USD news at 08:30 (news_class in p.trend_news);
      (the PD matrix / order-flow agreement, (3) of the text = htf.table draw, is checked at the bar: side_ok, it needs the table row cut at 09:30)."""
    DW = _DW()
    if len(hist) < 6 or a5 is None:
        return None
    rr = [DW.day_range(x, eth, p) for x in hist[-5:]]
    small = rr[-1] <= min(rr) + 1e-12
    contract = rr[-1] < rr[-2] < rr[-3]
    if not (small or contract):
        return None
    if DW.news_class(d) not in p.trend_news:
        return None
    eq = _eq60(hist)
    if eq is None:
        return None
    n = len(hist)
    best = 0
    for kind, sgn in (("bull", 1), ("bear", -1)):
        for z in D1._alive_zones(hist, kind):
            mid = (z.top + z.bottom) / 2.0
            if (kind == "bull" and mid >= eq) or (kind == "bear" and mid <= eq):
                continue                                   # a discount array lies BELOW the 60-day EQ, a premium array above it
            for j in range(max(z.i + 1, n - 3), n):
                x = hist[j]
                if (kind == "bull" and float(x.low.min()) <= z.top) or (kind == "bear" and float(x.high.max()) >= z.bottom):
                    best = sgn if best in (0, sgn) else 2
    return best if best in (1, -1) else None


def plan_rules(P, ctx, d: date, p, hist, eth, a5, dt) -> None:
    """Everything of this package known before the session opens (completed candles and the calendar). `dt` = strategy.day_context's tags."""
    dt = dt or set()
    tg = P.tags
    DW = _DW()
    S = _S()
    wd = d.weekday()
    # --- item 48 N8-consolidation-tradeable (053 ~00:01:13; cc01_005 ~00:11:01; cc04_012 ~00:07:57; cc09_004 ~00:20:24; cc10_008 ~00:09:01)
    if p.consolidation_mode != "skip":
        preds = DW._consol_predictors(ctx, d, p, hist, eth)
        reg = DW.range_regime(hist, p, eth) if p.drr_tests else []
        is_c = len(preds) >= p.consol_min_predictors or "range" in reg
        if is_c:
            # the intraday chop stand-aside ("skip") is replaced by the mode's own rules ONLY on the days this mode applies to; every other day (and a chop day the predictors miss, [our interpretation]:
            # the stand-aside machinery of owner #10 keeps acting there) is unchanged
            P.info["consol_nochop"] = True
            tg.add("consol_day")
            tg.add("consol_mode_" + p.consolidation_mode)
            P.info["consol_mode"] = p.consolidation_mode
            P.info["consol_preds"] = preds
            hit("consol_mode_" + p.consolidation_mode)
            if p.consolidation_mode == "scalp":
                P.set_scalp("consol_day", DW.MORNING)         # AM scalps only, if the opening range is small, flat by 11:00 (gate / day_exit read consol_apply)
                P.info["consol_apply"] = True
            elif p.consolidation_mode == "range_trade":
                n = max(1, p.consol_range_days)
                w = hist[-n:]
                if w:
                    P.info["consol_range"] = (max(float(x.high.max()) for x in w), min(float(x.low.min()) for x in w))
            elif p.consolidation_mode == "fade_with_htf":
                P.info["consol_fade"] = True                  # the HTF bias is read at the bar (the table is cut at 09:30)
    # --- item 50 N8-expansion-day-conditions (cc08_006 ~00:24:37)
    if p.expansion_strict and "expansion_due" in tg:
        S_sl = S.sloppy_day(hist, d, p)
        why = strict_filters(d, p)
        if S_sl or why or dt & {"big_prev", "three_up", "three_down"}:
            tg.discard("expansion_due")
            P.info.pop("expansion_due", None)
            hit("expansion_strict_static_off")
        else:
            P.info["expansion_pending"] = True                # bias != 0 and the manipulation leg opposite the bias: the bar (expansion_live)
            P.info.pop("expansion_due", None)
            tg.discard("expansion_due")                       # re-created as a day-level tag by entry_tags / the day summary once the dynamic condition holds
    # --- item 53 DS2-contraction-precedes-expansion (cc10_008 ~17:40; cc09_007 ~22:04-22:37)
    if p.expansion_mode != "off" and a5 and hist:
        # "hist[-1] (or hist[-2]) range < ADR5 OR was tagged consol": a previous session counts as a consolidation day when the multi-day range regime read as of that session says "range"
        small = _rng(hist[-1]) < a5 or (len(hist) > 1 and _rng(hist[-2]) < a5)
        if not small and p.drr_tests and (p.consolidation_mode != "skip" or p.consol_day_rules != "off"):      # consolidation tags only exist with a consolidation switch on
            small = any("range" in DW.range_regime(hist[:len(hist) - k], p, eth) for k in (0, 1) if len(hist) - k > p.drr_days)
        # the high / medium impact class of the 08:30 news (DW.news_class) - not any release in 08:30-10:00 [our interpretation: a 10:00 release counts when it is a high / medium one]
        rel = [r for r in CAL.release_times(d) if 510 <= r <= 600] and DW.news_class(d) in ("high", "medium")
        if (small or "consol_day" in tg) and rel:
            tg.add("expansion_candidate")
            P.info["expansion_candidate"] = True
            hit("expansion_candidate")
    # --- item 118 (a) the ADR5 contraction tag
    if p.adr_contracted_tag and adr_contracted(hist):
        tg.add("adr_contracted")
        hit("adr_contracted")
    # --- item 54 trend side
    if p.trend_side_rule and p.trend_recipe in ("tag", "side", "only") and a5:
        ts = trend_side(d, p, hist, eth, a5)
        # the first-pass recipe already tagged / blocked on its own definition; this switch replaces its side and adds the draw check
        P.sides.pop("trend_recipe", None)
        P.blocks = [(s_, r_) for s_, r_ in P.blocks if r_ != "no_trend_recipe"]
        tg.discard("trend_recipe")
        P.info.pop("trend_side", None)
        if ts is not None:
            tg.add("trend_recipe")
            tg.add("trend_side_" + ("up" if ts > 0 else "dn"))
            P.info["trend_side"] = ts
            P.info["trend_need_draw"] = True
            hit("trend_side_rule")
            if p.trend_recipe == "side":
                P.side_block("trend_recipe", (-ts,))
        elif p.trend_recipe == "only":
            P.block(None, "no_trend_recipe")
    # --- bias dependent week rules
    need_wb = bool(p.days_mode != "all" and p.late_week_fallback and wd in (3, 4)) or p.no_long_after_thu_noon or p.thu_reversal_tag or p.thu_reversal_trade or p.wed_week_extreme \
        or p.monday_mode == "big_into_array" or p.mw_break_bias
    wb = weekly_bias(ctx, hist, d, p) if need_wb else 0
    if need_wb:
        P.info["wk_bias"] = wb
    # --- items 66 / 67
    if p.days_mode != "all" and p.late_week_fallback and wd in (3, 4):
        if mw_delivered(hist, d, wb, a5):
            P.block(None, "days_mode")
            hit("late_week_blocked")
        else:
            tg.add("late_week")
            hit("late_week_open")
    # --- item 68 DS2-weekly-template-sequence: no new weekly-direction entries after Thursday noon / after a Thursday that closed with the bias
    if p.no_long_after_thu_noon and wb:
        if wd == 3:
            P.info["thu_cut"] = wb
        elif wd == 4 and hist and hist[-1].index[0].date().weekday() == 3:
            th = hist[-1]
            up = float(th.close.iloc[-1]) > float(th.open.iloc[0])
            if (wb > 0) == up and float(th.close.iloc[-1]) != float(th.open.iloc[0]):
                P.side_block("no_long_after_thu_noon", (wb,))
                hit("friday_after_thu_block")
    # --- item 63 / 62: Thursday Mon-Wed range, the false break; Wednesday week extreme
    if wd == 3 and (p.thu_reversal_tag or p.thu_reversal_trade) and a5 and thu_release(d):
        mw = [x for x in hist if DW._week_key(x.index[0].date()) == DW._week_key(d) and x.index[0].date().weekday() <= 2]
        if mw:
            hh, ll = DW._week_hl(mw, eth, True)
            if hh - ll <= 1.5 * a5 and wb:
                P.info["thu_rev"] = (hh, ll, wb)
                if "mw" not in P.info:
                    P.info["mw"] = (hh, ll)
                tg.add("thu_rev_setup")
                hit("thu_rev_setup")
    if wd == 2 and p.wed_week_extreme and wb:
        wk = D1._this_week(hist, d)
        if len(wk) >= 2 and wk[0].index[0].date().weekday() == 0:
            pre = [x for x in hist if x.index[0].date() < wk[0].index[0].date()]
            kind = "bull" if wb > 0 else "bear"
            ref = float(wk[0].open.iloc[0])
            # the NEAREST daily array of the bias side to the Monday open (as study_week.nearest_array picks it); neither Monday nor Tuesday may have traded into it. Only daily FVGs are armed
            # (no old M / W / D lows, broken-high retests or OBs [our interpretation, recorded in build_log])
            zs = [z for z in D1._alive_zones(pre, kind) if (z.top < ref if wb > 0 else z.bottom > ref)]
            near = (max(zs, key=lambda z: z.top) if wb > 0 else min(zs, key=lambda z: z.bottom)) if zs else None
            if near is not None and not any(float(x.low.min()) <= near.top and float(x.high.max()) >= near.bottom for x in wk[:2]):
                P.info["wed_ext"] = wb
                P.side_block("wed_week_extreme", (-wb,))
                tg.add("wed_week_extreme")
                hit("wed_week_extreme")
    # --- item 57 Monday big range into a daily array
    if p.monday_mode == "big_into_array" and CAL.is_week_start(d) and "monday_exempt" not in tg and wb:
        P.info["mon_big"] = wb
        tg.add("mon_big_candidate")
    elif p.monday_mode == "big_into_array" and CAL.is_week_start(d) and "monday_exempt" not in tg and not wb:
        P.block(None, "monday_no_bias")                     # a Monday without a weekly bias has no 'against the bias' extreme to trade
    # --- item 81 M14-reversal-threshold: the Friday-retrace flag for the next week (reported)
    if p.tgif_zone and wd < 5:
        f = reversal_flag(hist, d, p.tgif_stand_down if p.tgif_reversal_pct is None else p.tgif_reversal_pct)
        if f:
            tg.add("wk_reversal_flag")
            hit("wk_reversal_flag")
    # --- item 56 Friday pool choice: a single exit on a TGIF Friday
    if p.fri_pool_choice and wd == 4 and (dt & {"tgif_short", "tgif_long"}):
        P.info["single_exit"] = True
    # --- item 97 TGIF daily FVG CE cap
    if p.tgif_fvg_cap and wd == 4 and "tgif_short" in dt and hist:
        op = float(hist[-1].close.iloc[-1])
        zs = [z for z in D1._alive_zones(hist, "bear") if z.bottom >= op - 1e-9]
        if zs:
            z = min(zs, key=lambda q: q.bottom)
            P.info["tgif_fvg"] = (float(z.top), float(z.bottom), (float(z.top) + float(z.bottom)) / 2.0, float(hist[-1].low.min()))
            tg.add("tgif_fvg_cap")
            hit("tgif_fvg_cap_plan")
    # --- item 30 Friday trail (position loop) needs no plan state


def strict_filters(d: date, p) -> str:
    """Item 50: the cc08_006 avoidance filters beyond the sloppy-day tests: a jobs (NFP) day, the eve of a holiday, an FOMC decision / day-after (whipsaw) day, a day with two or more releases
    08:30-11:00 (the news-count test of N5). Returns the first reason or ''. [our interpretation: the video lists these as the days that are not 'clean'.]"""
    from claude_hf.daytypes import JOBS
    from . import nct2 as N2
    if d in JOBS:
        return "nfp"
    if CAL.is_holiday_eve(d):
        return "holiday_eve"
    fi = CAL.fomc_info(d)
    if fi["fomc"] or fi["after"]:
        return "fomc"
    if N2.rel_count(d, p) >= 2:
        return "multi_release"
    return ""


def thu_release(d: date) -> bool:
    """Item 63 (cc07_002 ~00:04:51): the precise Thursday reversal needs a scheduled release on the day (08:30 / 14:00, minutes 510 or 840)."""
    return any(r in (510, 840) for r in CAL.release_times(d))


def thu_day_tag(g: pd.DataFrame, hist, p) -> str:
    """Item 63 day-level tag from the Thursday frame `g` (post-hoc reporting): 'thu_reversal' when Thursday traded under the Mon-Wed low (tick) and a bar CLOSED back above it, 'thu_reversal_bear'
    for the high; needs the Mon-Wed range <= 1.5 x ADR5 and a release on the day. '' otherwise. Never read by a decision."""
    DW = _DW()
    d = g.index[0].date()
    if d.weekday() != 3 or not hist or not thu_release(d):
        return ""
    a5 = _S().adr5(list(hist)[-5:])
    mw = [x for x in hist if DW._week_key(x.index[0].date()) == DW._week_key(d) and x.index[0].date().weekday() <= 2]
    if not mw or not a5:
        return ""
    hh, ll = max(float(x.high.max()) for x in mw), min(float(x.low.min()) for x in mw)
    if hh - ll > 1.5 * a5:
        return ""
    h, l, c = (g[k].values.astype(float) for k in ("high", "low", "close"))
    j = np.flatnonzero(l <= ll - p.tick)
    if len(j) and (c[j[0]:] > ll).any():
        return "thu_reversal"
    j = np.flatnonzero(h >= hh + p.tick)
    if len(j) and (c[j[0]:] < hh).any():
        return "thu_reversal_bear"
    return ""


def reversal_flag(hist, d: date, pct: float) -> bool:
    """Item 81 M14-reversal-threshold (066 ~25:34 "beyond 30 percent"; ~18:12 "40 % or more"): the PREVIOUS completed week was an up (down) week (Mon-Thu close above (below) the Monday open) and its Friday retraced >= `pct` of the Mon-Thu range from the extreme. Tag wk_reversal_flag for the next week (reported, no trading effect)."""
    DW = _DW()
    prev = [x for x in hist if x.index[0].date() < d and DW._week_key(x.index[0].date()) != DW._week_key(d)]
    if not prev:
        return False
    wkey = DW._week_key(prev[-1].index[0].date())
    wk = [x for x in prev if DW._week_key(x.index[0].date()) == wkey]
    fri = [x for x in wk if x.index[0].date().weekday() == 4]
    mt = [x for x in wk if x.index[0].date().weekday() <= 3]
    if not fri or not mt:
        return False
    hi, lo = max(float(x.high.max()) for x in mt), min(float(x.low.min()) for x in mt)
    rng = hi - lo
    if rng <= 0:
        return False
    c = float(mt[-1].close.iloc[-1])
    o = float(mt[0].open.iloc[0])
    f = fri[0]
    # [our interpretation] the week's direction = the Mon-Thu close against the Monday open; the retrace is measured from the Mon-Thu extreme against that direction
    if c > o:
        return (hi - float(f.low.min())) / rng >= pct - 1e-12
    if c < o:
        return (float(f.high.max()) - lo) / rng >= pct - 1e-12
    return False


# --------------------------------------------------------------------------------------------------------------
# London / ADR helpers
# --------------------------------------------------------------------------------------------------------------

def london_ext(ctx, bias: int):
    """Item 73: the London (02:00-05:00) low (bias +1) / high (bias -1); None until the window has data. Complete at 05:00, so it is read at bars from 09:30 only."""
    c = _cache(ctx)
    k = ("lon", bias)
    if k not in c:
        m = (ctx.t >= 120) & (ctx.t < 300)
        m[:ctx.start] = False
        if not m.any():
            c[k] = None
        else:
            c[k] = float(ctx.l[m].min()) if bias > 0 else float(ctx.h[m].max())
    return c[k]


def whip(ctx, p, day) -> bool:
    c = _cache(ctx)
    if "whip" not in c:
        from dataclasses import replace
        from . import nct2 as N2
        c["whip"] = bool(CAL.fomc_info(day)["after"] and N2.whip_flag(ctx, p if p.fomc_whipsaw_skip != "off" else replace(p, fomc_whipsaw_skip="london"), day))
    return c["whip"]


def _bars_ny(ctx, i):
    return _DW()._run(ctx, "ny570", i, 570, 100000)


def gate(ctx, p, session: str, i: int, t: int, trades=()):
    """Per-bar session gates: item 57 Monday big range, item 73 London low guard, item 77 London filters."""
    P = getattr(ctx, "dplan", None)
    if P is None:
        return None
    DW = _DW()
    tf = ctx.tf
    # item 77 N8-london-filters-gate-london (cc08_006 ~00:13:20): the cc08_006 filters gate the London windows only ("sleep in, trade New York")
    if p.london_filters and session == "LON":
        if whip(ctx, p, ctx.day):
            hit("london_filter_whipsaw")
            return "x_dw_london_filter"
        from . import nct2 as N2
        if N2.rel_count(ctx.day, p) >= 2:
            hit("london_filter_rel2plus")
            return "x_dw_london_filter"
    # item 57 N10-monday-weekly-extreme (cc07_008 ~00:29:09; cc08_001 ~00:20:18): a big Monday move into a daily array against the weekly bias, then only the weekly-bias side
    mb = P.info.get("mon_big")
    if mb:
        if t + tf < 570:
            hit("mon_big_wait")
            return "x_dw_mon_big_wait"
        ok = mon_big_ok(ctx, p, mb)
        if not ok:
            hit("mon_big_reject")
            return "x_dw_mon_big"
    # item 73 NEW-london-low-violated (092 ~02:29:00)
    from . import dwc3 as D3                       # caption-gap T3-london-extreme-consolidation: on a consol_overnight day the London extreme is a pool, not the protected extreme
    if p.london_low_guard and session in DW.NY and not D3.london_unprotected(ctx, p, i):
        if t < 570:
            hit("london_guard_pre_wait")
            return "x_dw_london_guard_wait"
        b = _bias(ctx, p, i)
        if b:
            if t < 600:
                hit("london_guard_wait")
                return "x_dw_london_guard_wait"
            ext = london_ext(ctx, b)
            r = _bars_ny(ctx, i)
            if ext is not None and r is not None:
                tk = p.tick
                if (b > 0 and r[1] <= ext - tk + 1e-12) or (b < 0 and r[0] >= ext + tk - 1e-12):
                    hit("london_violated")
                    return "x_dw_london_violated"
    return None


def mon_big_ok(ctx, p, bias: int) -> bool:
    """Item 57: the 00:00-09:30 range >= mon_big_frac x ADR5 AND the overnight extreme against the bias (the high for a bearish week, the low for a bullish) touched a daily array of the other
    colour (a bearish D array at the high, a bullish one at the low). Cached; needs the Confluence arrays."""
    c = _cache(ctx)
    k = ("mon_big", bias)
    if k in c:
        return c[k]
    DW = _DW()
    k570 = DW._k570(ctx)
    ok = False
    a5 = DW._adr(ctx, p)
    if k570 > ctx.start and a5 and getattr(ctx, "conf", None) is not None:
        hi, lo = float(ctx.h[ctx.start:k570].max()), float(ctx.l[ctx.start:k570].min())
        if hi - lo >= p.mon_big_frac * a5 - 1e-12:
            when = ctx.idx[k570]
            if bias < 0:
                ok = DW._array_touch(ctx.conf, when, hi, -1, ("D",), ctx.conf.tol)
            else:
                ok = DW._array_touch(ctx.conf, when, lo, 1, ("D",), ctx.conf.tol)
    c[k] = ok
    return ok


def size_mult(ctx, p, lvt=None) -> float:
    """Item 57: the Monday into-array trade is half size (risk_mult 0.5)."""
    P = getattr(ctx, "dplan", None)
    if P is not None and P.info.get("mon_big"):
        if lvt is not None:
            lvt.append("size_mon_big")
        hit("mon_big_size")
        return 0.5
    return 1.0


# --------------------------------------------------------------------------------------------------------------
# side filters
# --------------------------------------------------------------------------------------------------------------

def _smt_extreme(ctx, side: int, k: int, win: int = 12):
    """SMT at the pre-open extreme [our interpretation]: the partner index (ctx.pside) did not confirm the main index's extreme: the main made its extreme (high for side>0) inside the last `win`
    bars before bar k while the partner's running extreme over those bars did not exceed its extreme of the bars before them. None without a partner."""
    pctx, psides, ppos = getattr(ctx, "pside", (None, None, None))
    if pctx is None:
        return None
    a = ctx.start
    seg_h, seg_l = ctx.h[a:k], ctx.l[a:k]
    if len(seg_h) < win + 2:
        return None
    j = a + int(np.argmax(seg_h) if side > 0 else np.argmin(seg_l))
    if j < a + win:
        return None
    t0 = ctx.idx[j - win]
    t1 = ctx.idx[j]
    pj1 = int(ppos.index.searchsorted(t1, side="right"))
    pj0 = int(ppos.index.searchsorted(t0, side="left"))
    ph, pl = pctx.h, pctx.l
    pa = pctx.start
    if pj0 - pa < 2 or pj1 <= pj0:
        return None
    if side > 0:
        return bool(float(ph[pj0:pj1].max()) <= float(ph[pa:pj0].max()))
    return bool(float(pl[pj0:pj1].min()) >= float(pl[pa:pj0].min()))


def fri_delivered(ctx, p, hist):
    """Item 55 N10-friday-preopen-delivered (035 ~00:39:24): the locked draw (the N9.2 prior-close draw, `eve_draw`) was delivered before 09:30 AND an SMT failure printed at that extreme (the
    partner index did not confirm; DXY is not in the frame so NQ / YM stand in, [our interpretation]). Returns the draw side (+1 / -1) or 0."""
    c = _cache(ctx)
    if "fri_del" in c:
        return c["fri_del"]
    DW = _DW()
    out = 0
    ed = DW.eve_draw(ctx, p, hist)
    if ed is not None and ed.get("done") and ed.get("side"):
        k = DW._k570(ctx)
        smt = _smt_extreme(ctx, ed["side"], k)
        if smt:
            out = int(ed["side"])
    c["fri_del"] = out
    return out


def side_ok(ctx, p, sign: int, session: str, i: int):
    """Side filters: items 54 (trend draw), 55, 56, 57, 62, 63, 68, 71, 73, 97, 207."""
    P = getattr(ctx, "dplan", None)
    if P is None:
        return None
    DW = _DW()
    d = ctx.day
    t = int(ctx.t[i])
    hist = getattr(ctx, "hist", [])
    # item 54: the trending-day side needs the PD matrix / order flow (the table draw) to agree
    ts = P.info.get("trend_side")
    if ts and P.info.get("trend_need_draw") and p.trend_recipe in ("side", "only"):
        if t < 570:
            hit("trend_wait")
            return "x_dw_trend_wait"
        if _draw(ctx, i) != ts:
            hit("trend_draw_mismatch")
            return "x_dw_trend_draw"
    # item 55 Friday: the draw was delivered before 09:30 with an SMT at the extreme
    if p.fri_delivered_stop and d.weekday() == 4 and (t >= 660 or session in DW.LATE):         # (read only from 11:00: the pre-open bars it needs have long closed)
        s = fri_delivered(ctx, p, hist)
        if s and sign == s:
            hit("fri_delivered_block")
            return "x_dw_fri_delivered"
    # item 57: only the weekly-bias side on the Monday into an array
    mb = P.info.get("mon_big")
    if mb and sign != mb:
        hit("mon_big_side")
        return "x_dw_mon_big_side"
    # item 68: no new weekly-direction entries after Thursday noon
    tc = P.info.get("thu_cut")
    if tc and sign == tc and t >= 720:
        hit("thu_noon_block")
        return "x_dw_no_long_after_thu_noon"
    # item 63: the Thursday false break takes only the bias side
    tr_ = P.info.get("thu_rev")
    if p.thu_reversal_trade and tr_ and sign != tr_[2]:
        hit("thu_rev_side")
        return "x_dw_thu_reversal_side"
    # item 71 DS2-ny-continuation-adr-pending (cc09_003 ~00:12:11; cc09_006 ~00:18:28)
    if p.ny_cont_gate and session in DW.NY and t < 600:
        b = _bias(ctx, p, i)
        if b and sign == b:
            why = ny_cont_reject(ctx, p, b, i)
            if why:
                hit("ny_cont_" + why)
                return "x_dw_ny_cont_" + why
    # item 73: while the London extreme holds, only the bias side
    if p.london_low_guard and session in DW.NY and t >= 570 and not _D3_unprot(ctx, p, i):
        b = _bias(ctx, p, i)
        if b and sign != b:
            hit("london_guard_side")
            return "x_dw_london_guard_side"
    # item 97: cancel shorts after two 5m closes above the daily FVG CE
    fv = P.info.get("tgif_fvg")
    if fv and sign < 0 and p.tgif_fvg_cap and tgif_fvg_cancelled(ctx, fv[2], i):
        hit("tgif_fvg_cancel")
        return "x_dw_tgif_fvg_closes"
    # item 207 T13-po3-small-open-wick (cc08_008 ~9:13)
    if p.po3_adr_invalid and t >= 570:
        r = _react(ctx, i)
        a5 = DW._adr(ctx, p)
        op = ctx.opens.get("midnight")
        dh = DW._day_hl(ctx, i)
        if r and a5 and op is not None and dh is not None:
            if r > 0 and sign > 0 and dh[1] < op - a5 - 1e-12:
                hit("po3_adr_invalid")
                return "x_dw_po3_adr_invalid"
            if r < 0 and sign < 0 and dh[0] > op + a5 + 1e-12:
                hit("po3_adr_invalid")
                return "x_dw_po3_adr_invalid"
    return None


def _D3_unprot(ctx, p, i: int) -> bool:
    from . import dwc3 as D3
    return D3.london_unprotected(ctx, p, i)


def ny_cont_reject(ctx, p, b: int, i: int):
    """Item 71 (the three requirements, side b): "extreme" = the day's extreme against the bias did not print in 0-300; "array" = a 4h / D array of the bias side (a bearish one above price for a
    long) was touched intraday since 00:00; "adr" = the day's range so far is already >= ADR5. Returns the failing reason or None. No Confluence = the array test cannot be made and passes."""
    DW = _DW()
    S = ctx.start
    seg_l, seg_h = ctx.l[S:i + 1], ctx.h[S:i + 1]
    j = S + int(np.argmin(seg_l) if b > 0 else np.argmax(seg_h))
    if not 0 <= int(ctx.t[j]) < 300 and not _D3_unprot(ctx, p, i):      # (caption-gap T3-london-extreme-consolidation: on a consol_overnight day the London extreme is not required)
        return "extreme"
    a5 = DW._adr(ctx, p)
    if a5 and float(seg_h.max() - seg_l.min()) >= a5 - 1e-12:
        return "adr"
    cf = getattr(ctx, "conf", None)
    if cf is not None:
        try:
            now = ctx.idx[i] + pd.Timedelta(minutes=ctx.tf)
            arrs = cf.arrays_any(now, b, ("4h", "D"))
        except Exception:
            arrs = []
        for near, _far in arrs:
            if (b > 0 and float(seg_h.max()) >= near) or (b < 0 and float(seg_l.min()) <= near):
                return "array"
    return None


def ny_cont_rung(ctx, p, i, sd=None) -> bool:
    """Item 71: the target rung LOD + ADR5 (HOD - ADR5) through adr_target, for a continuation (bias-side) entry before 10:00 with the gate on."""
    if not (p.ny_cont_gate and not p.adr_target and i is not None and int(ctx.t[i]) < 600):
        return False
    return sd is None or _bias(ctx, p, i) == sd.sign


def tgif_fvg_cancelled(ctx, ce: float, i: int) -> bool:
    """Item 97: two consecutive 5m closes above the daily FVG CE today (closed bars through i; on a 1m frame two consecutive 5-bar-aligned closes are read from the frame's bars every 5 minutes)."""
    S = ctx.start
    m = ctx.t[S:i + 1]
    c = ctx.c[S:i + 1]
    five = [float(c[k]) for k in range(len(m)) if (int(m[k]) + ctx.tf) % 5 == 0]
    return any(a > ce and b > ce for a, b in zip(five[:-1], five[1:]))                    # two CONSECUTIVE 5m closes above the CE


# --------------------------------------------------------------------------------------------------------------
# per-order filters
# --------------------------------------------------------------------------------------------------------------

_TS_KINDS = ("ts_", "turtle", "prev_pm_turtle")


def _is_ote_entry(o: dict, sd) -> bool:
    """[our interpretation] an OTE entry: the fill sits in the 62-79% retracement band of the order's displacement leg (side space: leg low .. leg high)."""
    leg = o.get("leg")
    if not leg:
        return False
    lo, hi = float(leg[0]), float(leg[1])
    if hi <= lo:
        return False
    return hi - 0.79 * (hi - lo) - 1e-9 <= o["entry"] <= hi - 0.62 * (hi - lo) + 1e-9


def _cap_levels(o: dict, bound: float) -> bool:
    """Drop the order's targets beyond `bound` (side space); False when none is left."""
    lv, kd = list(o["levels"]), list(o["level_kinds"])
    keep = [k for k, v in enumerate(lv) if v <= bound + 1e-9]
    if not keep:
        return False
    if len(keep) < len(lv):
        o["levels"] = [lv[k] for k in keep]
        o["level_kinds"] = [kd[k] for k in keep]
        o["t1"] = o["levels"][0]
        o["t2"] = o["levels"][1] if (len(keep) > 1 and o.get("t2") is not None) else None
        o["final_T"] = False
        rp = o.get("rung_plan")
        if rp:
            o["rung_plan"] = [r for r in rp if r["v"] <= bound + 1e-9]
            if not any(r["role"] == "main" for r in o["rung_plan"]):
                return False
        hit("consol_range_cap")
    return True


def _range_rungs(ctx, sd, o: dict, bound: float, i: int, tol: float) -> None:
    """Item 48 range_trade targets: "the opposite open FVG or equal highs / lows inside the range": the near edge of every open opposing 1h / 4h / D array between the entry and the range
    extreme, and the range extreme itself (the equal-highs stand-in, [our interpretation]) are added as rungs when no existing rung sits within a tick-size of them. Side space."""
    cf = getattr(ctx, "conf", None)
    cand = []
    if cf is not None:
        try:
            now = ctx.idx[i] + pd.Timedelta(minutes=ctx.tf)
            for near, _far in cf.arrays_any(now, sd.sign, ("1h", "4h", "D")):
                cand.append((sd.x(near), "array"))
        except Exception:
            pass
    cand.append((bound, "pool"))
    lv, kd = list(o["levels"]), list(o["level_kinds"])
    rp = o.get("rung_plan")
    n0 = len(lv)
    for v, k in cand:
        if v <= o["entry"] + 1e-9 or v > bound + 1e-9 or any(abs(v - x) <= tol for x in lv):
            continue
        lv.append(v)
        kd.append(k)
        if rp:
            m0 = next((x for x in rp if x["role"] == "main"), None)
            if m0 is not None:
                rp.append(dict(m0, v=v, k=k))
    if len(lv) == n0:
        return
    order = sorted(range(len(lv)), key=lambda q: lv[q])
    o["levels"] = [lv[q] for q in order]
    o["level_kinds"] = [kd[q] for q in order]
    o["t1"] = o["levels"][0]
    if rp:
        rp.sort(key=lambda x: x["v"])
    hit("consol_range_rungs")


def _rescale(o: dict, new_stop: float, tighten: bool = False) -> bool:
    """Move the order's stop (side space) to `new_stop`. A WIDER stop keeps the risk: the units shrink with the distance (False when fewer than one unit is left). A tighter stop is applied only
    with `tighten` (item 97, where the spec value is the stop) and keeps the units [our interpretation: no size increase from a rule that only asks for a stop]."""
    old = o["entry"] - o["stop"]
    new = o["entry"] - new_stop
    if new <= 0:
        return False
    if new <= old + 1e-12:
        if tighten and new < old - 1e-12:
            o["stop"] = new_stop
            o["rungs"] = []
        return True
    n = int(o["shares"] * old / new)
    if n < 1:
        return False
    o["stop"] = new_stop
    o["shares"] = n
    o["plan_shares"] = n
    o["rungs"] = []
    return True


def order_ok(ctx, sd, o: dict, session: str, i: int, p):
    """Per-order filters: item 48 consolidation range / fade, item 63 Thursday false break, item 69 Tuesday OTE off Monday's low, item 97 TGIF daily-FVG CE cap."""
    P = getattr(ctx, "dplan", None)
    if P is None:
        return None
    DW = _DW()
    S = _S()
    d = ctx.day
    # item 48 N8-consolidation-tradeable
    cm = P.info.get("consol_mode")
    if cm == "range_trade":
        ek = str(o.get("entry_kind", ""))
        ok = ek.startswith(_TS_KINDS) or _is_ote_entry(o, sd) or o.get("smt") is True
        if not ok:
            hit("consol_range_setup_reject")
            return "x_dw_consol_range_setup"
        rg = P.info.get("consol_range")
        if rg:
            bound = rg[0] if sd.sign > 0 else sd.x(rg[1])
            if not _cap_levels(o, bound):
                hit("consol_range_no_target")
                return "x_dw_consol_range_target"
            _range_rungs(ctx, sd, o, bound, i, p.tick)
        o.pop("runner", None)                                  # B14: no runners or breakout trades inside a range
        o.pop("htf_runner", None)
    elif cm == "fade_with_htf" and P.info.get("consol_fade"):
        b = _combo(ctx, i)
        if not b:
            hit("consol_fade_no_bias")
            return "x_dw_consol_fade_bias"
        ek = str(o.get("entry_kind", ""))
        if sd.sign != b or not ek.startswith(_TS_KINDS):
            hit("consol_fade_reject")
            return "x_dw_consol_fade"
    # item 63 NEW-consolidation-thursday-reversal (cc07_002 ~00:04:51): the only Thursday trade is the false break of the Mon-Wed low
    tr_ = P.info.get("thu_rev")
    if p.thu_reversal_trade and tr_ and sd.sign == tr_[2]:
        if str(o.get("swept", "")) != "mon_wed":
            hit("thu_rev_not_pool")
            return "x_dw_thu_reversal_pool"
        hit("thu_rev_pass")
    # item 69 DS2-tue-to-thu-horizon (cc12_003 ~00:15:56): Tuesday off Monday's low, OTE retrace referenced to it
    if p.tue_off_monday == "ote" and "off_ref" in P.info:
        hi, lo = P.info["off_ref"]
        if sd.sign > 0:
            leg_lo, leg_hi = lo, max(hi, float(ctx.h[ctx.start:i + 1].max()))
        else:
            leg_lo, leg_hi = sd.x(hi), sd.x(min(lo, float(ctx.l[ctx.start:i + 1].min())))
        leg = leg_hi - leg_lo
        ent = o["entry"]
        if leg <= 0 or not (leg_hi - 0.79 * leg - 1e-9 <= ent <= leg_hi - 0.62 * leg + 1e-9):
            hit("tue_ote_reject")
            return "x_dw_tue_off_monday_ote"
        if not _rescale(o, min(o["stop"], leg_lo - p.tick)):
            hit("tue_ote_size")
            return "x_dw_tue_off_monday_ote"
        hit("tue_ote_pass")
    # item 97 M14-tgif-daily-fvg-ce-cap (089 ~00:02:57)
    fv = P.info.get("tgif_fvg")
    if fv and p.tgif_fvg_cap and sd.sign < 0 and d.weekday() == 4:
        top, bot, ce, pdl = fv
        ent = sd.x(o["entry"])
        if ent > ce + 1e-9:
            hit("tgif_fvg_entry_above_ce")
            return "x_dw_tgif_fvg_ce"
        k = int(o.get("ext_i", i))
        w = range(max(ctx.start, k - max(1, 25 // ctx.tf) + 1), k + 1)             # the last 5m swing: the last 25 minutes of bars up to the sweep extreme
        # the longest upper wick of that swing: its CE
        best, bl = ce, -1.0
        for j in w:
            wl = float(ctx.h[j]) - max(float(ctx.o[j]), float(ctx.c[j]))
            if wl > bl:
                bl, best = wl, (float(ctx.h[j]) + max(float(ctx.o[j]), float(ctx.c[j]))) / 2.0
        stop_real = max(ce, best) + p.tick
        if not _rescale(o, sd.x(stop_real), True):
            hit("tgif_fvg_size")
            return "x_dw_tgif_fvg_ce"
        # the ladder: PDL - 1 tick, the daily FVG low (if below the entry), then the zone band (the existing tgif_zone rungs stay)
        add = [pdl - p.tick]
        if bot < ent:
            add.append(bot)
        lv, kd = list(o["levels"]), list(o["level_kinds"])
        rp = o.get("rung_plan")
        for r_real in add:
            r = sd.x(r_real)
            if r <= o["entry"] + 1e-9 or any(abs(r - v) <= p.es_pt for v in lv):
                continue
            lv.append(r)
            kd.append("pool" if r_real == add[0] else "array")
            if rp:
                m0 = next((x for x in rp if x["role"] == "main"), None)
                if m0 is not None:
                    rp.append(dict(m0, v=r, k=kd[-1]))
        order = sorted(range(len(lv)), key=lambda q: lv[q])
        o["levels"] = [lv[q] for q in order]
        o["level_kinds"] = [kd[q] for q in order]
        o["t1"] = o["levels"][0]
        o["t2"] = o["levels"][1] if len(o["levels"]) > 1 else None
        if rp:
            rp.sort(key=lambda x: x["v"])
        hit("tgif_fvg_pass")
    return None


# --------------------------------------------------------------------------------------------------------------
# expansion (items 50, 53)
# --------------------------------------------------------------------------------------------------------------

def judas_leg(ctx, i: int, b: int, a5=None, frac: float = 0.0) -> bool:
    """Item 50 (the lesson 5 profile: manipulation, then expansion): the day's manipulation leg ran against the bias - the extreme against the bias printed BELOW the midnight open (bias +1) /
    above it by at least `frac` x ADR5 (`expansion_judas_adr`; noise around the open is no manipulation) and the bias-direction extreme came after it [our interpretation of the `_judas` flag]."""
    S = ctx.start
    op = ctx.opens.get("midnight")
    if op is None or i < S:
        return False
    seg_h, seg_l = ctx.h[S:i + 1], ctx.l[S:i + 1]
    jl, jh = int(np.argmin(seg_l)), int(np.argmax(seg_h))
    need = (frac * a5) if a5 else 0.0
    if b > 0:
        return bool(op - float(seg_l[jl]) > need and jh > jl)
    return bool(float(seg_h[jh]) - op > need and jl > jh)


def expansion_live(ctx, p, i: int):
    """Item 50: the dynamic half of the strict expansion day: a bias exists and the manipulation leg is opposite to it. Returns the bias or 0."""
    P = getattr(ctx, "dplan", None)
    if not p.expansion_strict or P is None or not P.info.get("expansion_pending"):
        return 0
    b = _bias(ctx, p, i)
    if not b or not judas_leg(ctx, i, b, P.info.get("adr5_prev"), p.expansion_judas_adr):
        return 0
    return b


def expansion_rungs(ctx, sd, i: int, p, a: float) -> list:
    """Item 50: the expansion rungs (side space) from the manipulation extreme: the existing multiples plus 1.5 x ADR5."""
    b = expansion_live(ctx, p, i)
    if not b or b != sd.sign:
        return []
    ext = float(sd.l[ctx.start:i + 1].min())
    ks = sorted(set(p.expansion_targets) | {1.5})
    hit("expansion_strict_rungs")
    return [(ext + k * a, "array") for k in ks]


# --------------------------------------------------------------------------------------------------------------
# params / tags
# --------------------------------------------------------------------------------------------------------------

def day_params(p, dw):
    """Item 53 expansion_mode "full": no slow-day ladder (the 80/20 split) and the po3 runner allowed; item 56: a single exit on a TGIF Friday (no runner); item 48 "scalp": the consolidation
    AM is out by 11:00."""
    from dataclasses import replace
    kw = {}
    if p.expansion_mode == "full" and dw.info.get("expansion_candidate"):
        kw.update(ladder_fracs_slow=p.ladder_fracs, po3_runner=True)
        hit("expansion_full")
    if dw.info.get("single_exit"):
        kw.update(runner_frac=0.0, po3_runner=False, runner_htf=False, htf_range_runner=False, urgency_runner=False)
        hit("fri_single_exit")
    if dw.info.get("consol_mode") == "scalp":
        kw.update(consol_am_out=660, consol_pm_rule=True)
    return replace(p, **kw) if kw else p


def entry_tags(ctx, p, P, k: int) -> set:
    """Per-trade tags from the bars through the entry bar k (reporting only)."""
    t = set()
    DW = _DW()
    s = ctx.t[k]
    tr_ = P.info.get("thu_rev")
    if tr_ and k >= ctx.start:
        hh, ll, b = tr_
        tk = p.tick
        if b > 0:
            if float(ctx.l[ctx.start:k + 1].min()) <= ll - tk and float(ctx.c[k]) > ll:
                t.add("thu_reversal")
        else:
            if float(ctx.h[ctx.start:k + 1].max()) >= hh + tk and float(ctx.c[k]) < hh:
                t.add("thu_reversal_bear")
    mb = P.info.get("mon_big")
    if mb and k >= ctx.start and mon_big_ok(ctx, p, mb):
        t.add("wk_ext_candidate")
    if p.adr_news_exempt and P.info.get("adr_filled_news"):
        t.add("adr_filled_news")
    if P.info.get("expansion_pending") and k >= ctx.start and expansion_live(ctx, p, k):
        t.add("expansion_due")
        P.tags.add("expansion_due")                        # the day-level tag once the dynamic condition holds (readers of the tag see it from then on)
    if P.info.get("wed_ext"):
        t.add("wed_low" if P.info["wed_ext"] > 0 else "wed_high")
    return t


# --------------------------------------------------------------------------------------------------------------
# position-loop hooks (items 30, 118, 160)
# --------------------------------------------------------------------------------------------------------------

def fri_trail(ctx, sd, pos, tr, i: int, p) -> None:
    """Item 30 X5-friday-tight-trail (103 ~00:30:33): on a Friday from `fri_trail_from` the open position's stop ratchets under the latest confirmed 1-bar pivot low after the fill (side space,
    minus a tick); the flatten at the close still closes what the stop leaves. Pivots are confirmed one bar later, so only bars through i are read."""
    if not p.fri_trail_from or ctx.day.weekday() != 4 or int(ctx.t[i]) < p.fri_trail_from or not pos["left"]:
        return
    a = pos["fill_i"]
    _hi, lows = L.pivots(sd.h[:i + 1], sd.l[:i + 1], 1)
    lows = [q for q in lows if q.i > a]
    if not lows:
        return
    from . import manage as MG
    new = float(lows[-1].price) - p.tick
    if new > pos["stop"]:
        MG.raise_stop(pos, new, True)
        hit("fri_trail")


def am_exit_for(ctx, sd, pos, tr, i: int, ts, p, am_x: int, c: float) -> int:
    """Item 118 L16-adr-contraction-runner (b) (cc09_008 ~00:47:45): when the range from midnight to 09:30 in the trade direction is >= ADR5 (the figure moves with the market) the AM exit of the
    LAST `runner_frac` of the units (0.2 when 0) moves from `am_exit` to `adr_runner_until`, once >= 75 % of the units are banked. Returns the minute at which the position is closed."""
    if not p.adr_met_runner:
        return am_x
    d = pos.setdefault("adr_runner", {"dec": False, "on": False})
    if d["on"]:
        return p.adr_runner_until
    if d["dec"] or int(ctx.t[i]) + ctx.tf < am_x:
        return am_x
    d["dec"] = True
    DW = _DW()
    a = DW._adr(ctx, p)
    k570 = DW._k570(ctx)
    if not a or k570 <= ctx.start:
        return am_x
    move = (float(ctx.c[k570 - 1]) - float(ctx.o[ctx.start])) * sd.sign
    if move < a - 1e-12:
        hit("adr_runner_short")
        return am_x
    n = pos["n"]
    if (n - pos["left"]) / n < 0.75 - 1e-9:
        hit("adr_runner_not_banked")
        return am_x
    keep = max(p.lot, int(round(n * (p.runner_frac or 0.2))), 1)
    if pos["left"] > keep:
        q = pos["left"] - keep
        tr.exits.append((ts, sd.x(c), q, "am_exit"))
        pos["left"] -= q
    d["on"] = True
    hit("adr_runner_on")
    return p.adr_runner_until


def adr_close_exit(ctx, sd, pos, tr, i: int, ts, p) -> None:
    """Item 160 LLT3-adr-fib-close-zone (cc09_006 ~00:26:59): H = L + ADR5 (L = the day's low so far, the London low once London is complete); once price has traded H AS IT STOOD (H moves with the
    running low) and a 5m bar closes back below it (a 1m frame reads only the closes at 5-minute boundaries), the runner (after the first partial) is out at H - 0.20 x ADR5 (a resting exit: a gap
    through fills at the open). Side space. State is advanced one closed bar at a time from the day's first bar."""
    if not p.adr_close_runner or not pos["left"] or not pos.get("t1_done"):
        return
    DW = _DW()
    a = DW._adr(ctx, p)
    if not a:
        return
    st = pos.setdefault("adr_close", {"turn_j": None, "H": None, "j": ctx.start - 1, "lo": np.inf})
    ls = getattr(ctx, "sess", {}).get("london")
    for j in range(st["j"] + 1, i + 1):
        st["j"] = j
        if st["turn_j"] is not None:
            break
        st["lo"] = min(st["lo"], float(sd.l[j]))
        lo = st["lo"]
        if ls is not None and ctx.t[j] >= ls[2]:
            lo = float(sd.x(ls[1] if sd.sign > 0 else ls[0]))
        H = lo + a
        if st["H"] is not None:
            if j > pos["fill_i"] and (int(ctx.t[j]) + ctx.tf) % 5 == 0 and float(sd.c[j]) < st["H"]:
                st["turn_j"] = j                                   # a 5m close back below the level that traded
        elif float(sd.h[j]) >= H - 1e-12:
            st["H"] = H                                            # H traded, as it stood at that bar (the turn is read from the next bar on)
    if st["turn_j"] is None:
        return
    px = st["H"] - 0.20 * a
    if st["turn_j"] == i:
        if float(sd.c[i]) <= px + 1e-12:
            tr.exits.append((ts, sd.x(float(sd.c[i])), pos["left"], "adr_close"))
            pos["left"] = 0
            hit("adr_close_exit")
    elif float(sd.l[i]) <= px + 1e-12:
        fill = min(px, float(sd.o[i]))
        tr.exits.append((ts, sd.x(fill), pos["left"], "adr_close"))
        pos["left"] = 0
        hit("adr_close_exit")


# --------------------------------------------------------------------------------------------------------------
# reporting: the per-day summary fields (items 63 legs5, 157, 160, 118, 207)
# --------------------------------------------------------------------------------------------------------------

def swing_series(h, l, n: int = 1) -> list:
    """Alternating pivot prices (low, high, low ...) of the bars, oldest first, confirmed pivots only; consecutive pivots of the same kind keep the more extreme one."""
    hi, lo = L.pivots(np.asarray(h, float), np.asarray(l, float), n)
    seq = sorted([(q.i, float(q.price), 1) for q in hi] + [(q.i, float(q.price), -1) for q in lo])
    out = []
    for _i, px, kd in seq:
        if out and out[-1][1] == kd:
            if (kd > 0 and px > out[-1][0]) or (kd < 0 and px < out[-1][0]):
                out[-1] = (px, kd)
            continue
        out.append((px, kd))
    return [x[0] for x in out]


def count_legs(swings, direction: int, pts: float = 5.0) -> int:
    """Item 63 L15-5-handle-legs (009 ~00:17:52): completed legs of >= `pts` in `direction` between consecutive swings (a run from a pivot low to a pivot high); [our interpretation] no fixed price
    grid. 4000-4006-4003-4009-4004-4010 gives 3 up legs."""
    n = 0
    for a, b in zip(swings[:-1], swings[1:]):
        if (b - a) * direction >= pts - 1e-12:
            n += 1
    return n


def adr_close_zone(o, h, l, c, adr: float, direction: int = 1):
    """Item 160: with L = the day's low (direction +1; the high for -1), H = L + ADR5 and R = ADR5: True when the close lies at H (or beyond) or inside [H - 0.30 R, H - 0.20 R], False
    otherwise, None when the day's range did not reach ADR5 ("on days ADR was met")."""
    if not adr or adr <= 0:
        return None
    rng = h - l
    if rng < adr - 1e-12:
        return None
    if direction >= 0:
        H = l + adr
        x = c
    else:
        H = -(h - adr)
        x = -c
    return bool(x >= H - 1e-12 or (H - 0.30 * adr - 1e-12 <= x <= H - 0.20 * adr + 1e-12))


def day_summary(g: pd.DataFrame, hist, p, bias_row=None, tf: int = 5) -> dict:
    """One row of the day-summary report for the day frame `g` (all bars of the day) after the prior regular sessions `hist`. Post-hoc reporting - never read by a decision."""
    S = _S()
    d = g.index[0].date()
    t = (g.index.hour * 60 + g.index.minute).values
    h, l, o, c = (g[k].values.astype(float) for k in ("high", "low", "open", "close"))
    a5 = S.adr5(list(hist)[-5:]) if hist else None
    out = dict(date=d)
    op = float(o[0])
    out["adr5"] = a5
    if hist:
        pdh, pdl = float(hist[-1].high.max()), float(hist[-1].low.min())
        out["pdh_hit"] = int(h.max() >= pdh)
        out["pdl_hit"] = int(l.min() <= pdl)
        near = min(abs(pdh - op), abs(op - pdl))
        out["pd_reach_ok"] = int(bool(a5) and a5 >= near)
    # RTH legs in the day's bias direction
    want = 0
    if bias_row is not None:
        try:
            want = int(np.sign(float(bias_row.get("draw", 0)))) if hasattr(bias_row, "get") else 0
        except Exception:
            want = 0
    m = (t >= 570) & (t < 960)
    if m.any():
        sw = swing_series(h[m], l[m], 1)
        out["legs5_bias"] = count_legs(sw, want or 1, 5.0 * p.es_pt) if want else None
        out["legs5_up"] = count_legs(sw, 1, 5.0 * p.es_pt)
        out["legs5_dn"] = count_legs(sw, -1, 5.0 * p.es_pt)
    if a5:
        dirn = 1 if c[-1] >= op else -1
        z = adr_close_zone(op, float(h.max()), float(l.min()), float(c[-1]), a5, dirn)
        out["adr_met"] = int(float(h.max() - l.min()) >= a5)
        out["close_in_adr_zone"] = None if z is None else int(z)
        r = _react_row(bias_row)
        if r:
            out["react"] = r
            out["po3_open_low_adr"] = round(((op - float(l.min())) if r > 0 else (float(h.max()) - op)) / a5, 4)
    if hist and p.adr_contracted_tag:
        out["adr_contracted"] = int(adr_contracted(hist))
    if hist and (p.thu_reversal_tag or p.thu_reversal_trade):
        out["thu_reversal"] = thu_day_tag(g, hist, p)
    m15 = t < 900
    if m15.any() and (t >= 900).any():
        out["ny_close_1500"] = float(c[np.flatnonzero(m15)[-1]])
        out["true_day_hi"], out["true_day_lo"] = float(h[m15].max()), float(l[m15].min())
    return out


def _react_row(row) -> int:
    try:
        v = row.get("react") if hasattr(row, "get") else None
        return 0 if v is None or v != v else int(np.sign(float(v)))
    except Exception:
        return 0


def summary_stats(rows) -> dict:
    """The distributions `study.py` prints: the PDH / PDL touch rate (overall and when ADR5 reaches the nearer level), legs5 per day, the share of ADR-met days that close in the fib zone."""
    df = pd.DataFrame(rows)
    out = dict(days=int(len(df)))
    if not len(df):
        return out
    if "pdh_hit" in df:
        touch = ((df.pdh_hit == 1) | (df.pdl_hit == 1))
        out["pd_touch_rate"] = round(float(touch.mean()), 4)
        ok = df[df.pd_reach_ok == 1]
        out["pd_touch_rate_reach_ok"] = round(float(((ok.pdh_hit == 1) | (ok.pdl_hit == 1)).mean()), 4) if len(ok) else None
    for k in ("legs5_bias", "legs5_up", "legs5_dn"):
        if k in df and df[k].notna().any():
            out[k] = {str(a): int(b) for a, b in df[k].dropna().astype(int).value_counts().sort_index().items()}
    if "close_in_adr_zone" in df and df.close_in_adr_zone.notna().any():
        z = df.close_in_adr_zone.dropna()
        out["close_in_adr_zone"] = dict(days=int(len(z)), rate=round(float(z.mean()), 4))
    return out


# --------------------------------------------------------------------------------------------------------------
# item 206: the New York (true day) close
# --------------------------------------------------------------------------------------------------------------

def true_day(ctx, i: int):
    """definitions_pd_arrays_structure #206 (cc08_002 ~9:32): (ny_close_1500, (true-day high, low)) of the IPDA true day 00:00-15:00 as known at the closed bar i, else (None, None): the 15:00 close is
    the close of the last bar ENDING at 15:00 (the 14:59 bar on a 1m frame), distinct from the 16:00 session close; nothing is returned before that bar has closed."""
    k = getattr(ctx, "ny_close_i", None)
    if k is None or i is None or i < k:
        return None, None
    return ctx.ny_close_1500, ctx.true_day_hl


def fri_pool_pick(ctx, p, up, dn, px: float, kl: int, t_lock: int, hist):
    """Item 56 N10-friday-pool-choice (096 ~00:06:54; cc04_011 ~00:18:05), called from strategy.mark_levels on a Friday: when price has already run a nearby sell-side pool (the previous day's low
    or lower) and sits under an unrun buy-side POOL (overnight / session high, PDH ...), lock the nearest such buy-side pool and do not use the remaining sell-side REL below as the draw; the
    mirror for a run buy-side. Targets are capped at the week's high / low. Returns (side, up, dn) or None (the normal pick)."""
    if not p.fri_pool_choice or ctx.day.weekday() != 4 or kl <= ctx.start:
        return None
    S = ctx.start
    lo_t, hi_t = float(ctx.l[S:kl].min()), float(ctx.h[S:kl].max())
    pdl = ctx.pd.get("pdl1")
    pdh = ctx.pd.get("pdh1")
    wk = [x for x in hist if _DW()._week_key(x.index[0].date()) == _DW()._week_key(ctx.day) and x.index[0].date() < ctx.day]
    whi = max([hi_t] + [float(x.high.max()) for x in wk])
    wlo = min([lo_t] + [float(x.low.min()) for x in wk])
    up_pools = [x for x in up if x[2] == "pool" and x[1] <= whi + 1e-9]
    dn_pools = [x for x in dn if x[2] == "pool" and x[1] >= wlo - 1e-9]
    if pdl is not None and lo_t <= pdl and up_pools:
        hit("fri_pool_long")
        return 1, up_pools, [x for x in dn if x[2] != "pool"]
    if pdh is not None and hi_t >= pdh and dn_pools:
        hit("fri_pool_short")
        return -1, [x for x in up if x[2] != "pool"], dn_pools
    return None
