"""Caption-gap pass, package day_week_context#3/3 (digests/rulebook_gaps: management_partials_trailing_exits.md 121, 126; models_setups_entries.md 85, 90, 93, 175, 180; other.md 7, 9, 10, 11, 25;
session_day_week_stops_frequency.md 11, 18, 20, 21, 27, 28, 29, 31, 32, 33, 35, 37; stops_sizing_scaling_in.md 38; times_sessions_macros.md 4, 14, 18, 30, 33, 49, 50, 57).

The week / month budget rules of the day_week_context package (monthly cap, weekly goal, Friday after a profitable week, August drawdown, the carried weekly draw), the day / week templates (choppy
week, Thursday after the targets, missed Mon-Wed move, trending-week extreme, weekly PO3, the TGIF window / precondition / branch / week-high invalidation, the consolidation PM rules, the lunch
behaviours, the PM narrative from a chop AM), the session-veto helper, the pre-session checklist, the time-to-move journal and the studies. Everything reads completed daily candles (`hist`),
the calendar, or today's bars that have closed (index <= the caller's bar i). Thresholds the sources never give are marked [our interpretation]. Every rule is a Params switch (off by default
unless the build spec says otherwise).

Pieces (the engine hooks that call them)
  calendar_block   skip_months                                                                         (strategy.blocked, after dwc2.calendar_block)
  week_extra       month / week P&L state and the day skips (monthly cap, weekly goal, Friday, August)  (backtest.run, before run_day)
  plan_rules       the DayPlan part: PM news, choppy week, carry, Thursday targets, missed week ...      (daycontext.plan tail, after dwc2.plan_rules)
  gate             per-bar gates: PM fizzle, PM pool exit, PM narrative, weekly goal, TGIF window ...    (daycontext.gate tail)
  side_ok          side filters: weekly PO3, TGIF Thursday, TGIF branch, noon reversal ...               (daycontext.side_ok tail)
  order_ok         per-order filters: HTF quality, PM pool exit, nearest-only, TGIF week high ...        (daycontext.order_ok tail)
  size_mult        low-magnitude season                                                                  (daycontext.day_risk)
  day_params       choppy week: no runner                                                                (strategy._run_day_once)
  entry_tags       per-trade tags (lunch kind, consol_overnight, weekly_judas ...)                       (daycontext.stamp)
  session_veto     the explicit order: filters before bias (item 10)                                      (strategy main loop, sb_model, pre_open)
  journal_*        item 7: MFE / MAE, time to the first favourable move, time to the exit                (strategy position loop, _close)
"""
from __future__ import annotations

from collections import Counter
from datetime import date, timedelta

import numpy as np
import pandas as pd

from mentorship.calendar import events
from . import calendar as CAL
from . import dwc1 as D1
from . import dwc2 as D2

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
    return ctx.__dict__.setdefault("_dwc3", {})


def _hl(fr) -> tuple:
    return float(fr.high.max()), float(fr.low.min())


def _rng(fr) -> float:
    return float(fr.high.max() - fr.low.min())


# --------------------------------------------------------------------------------------------------------------
# calendar block: skip_months (item X15-monthly-cap)
# --------------------------------------------------------------------------------------------------------------

def calendar_block(d: date, session: str, p, t: int = 0):
    """session_day_week_stops_frequency #18 X15-monthly-cap: `skip_months` (month numbers) block every session of those months (blocked() -> "month")."""
    if p.skip_months and d.month in p.skip_months:
        return "month"
    return None


# --------------------------------------------------------------------------------------------------------------
# the week / month state (backtest.run)
# --------------------------------------------------------------------------------------------------------------

def needs_week(p) -> bool:
    return bool(p.max_trades_month or p.weekly_target_pct or p.weekly_cap_pts or p.skip_fri_if_week_up or p.aug_dd_stop_pct or p.missed_week_mode != "off"
                or p.low_mag_week_cap or p.checklist != "off" or p.thu_targets_met_block)


def _row_pts(r, p) -> float:
    """The trade's gross result in ES points per unit [our interpretation of `week["pts"]`: gross / shares / es_pt]."""
    try:
        return float(r["gross"]) / max(1, int(r["shares"])) / float(p.es_pt)
    except Exception:
        return 0.0


def week_extra(wk: dict | None, rows: list, d: date, p) -> tuple:
    """(week dict, skip reason | None). Adds to the week state (backtest.week_state): month_n / month_net, week_eq0 (the account at the start of the week), week_pct / week_pts (the week's closed
    result in % of that account and in ES points), week_trades [(side, net)]. The reason is the first firing of: the monthly cap (#18), the weekly goal (#21), Friday after a profitable week (#29),
    the August drawdown stop (#37). Reads only the trade rows of earlier days."""
    wk = dict(wk or {})
    mon = d - timedelta(days=d.weekday())
    wr = [r for r in rows if mon <= r["date"] < d]
    mr = [r for r in rows if r["date"].year == d.year and r["date"].month == d.month and r["date"] < d]
    eq0 = float(p.account_equity) + sum(float(r["net"]) for r in rows if r["date"] < mon)
    net = sum(float(r["net"]) for r in wr)
    wk.update(month_n=len(mr), month_net=float(sum(float(r["net"]) for r in mr)), week_eq0=eq0, week_net3=net,
              week_pct=100.0 * net / eq0 if eq0 else 0.0, week_pts=float(sum(_row_pts(r, p) for r in wr)),
              week_trades=[(str(r.get("side", "")), float(r["net"])) for r in wr])
    wk.setdefault("net", net)
    why = None
    if p.max_trades_month and wk["month_n"] >= p.max_trades_month:
        why = "month_cap"                                                       # #18
    elif (p.weekly_target_pct and wr and wk["week_pct"] >= p.weekly_target_pct) or (p.weekly_cap_pts and wr and wk["week_pts"] >= p.weekly_cap_pts):
        why = "weekly_goal"                                                     # #21
    elif p.skip_fri_if_week_up and d.weekday() == 4 and wr and net > 0:
        why = "fri_week_up"                                                     # #29
    elif p.aug_dd_stop_pct and d.month == 8 and aug_dd_hit(rows, d, p):
        why = "august_dd"                                                       # #37
    if why:
        hit("skip_" + why)
    return wk, why


def aug_dd_hit(rows: list, d: date, p) -> bool:
    """#37 N7-august-drawdown-restart: in August the drawdown from the August equity peak (the account at the start of August and after each August trade, closed trades only) reached
    `aug_dd_stop_pct` % of the August start account, or the month's net is at most -aug_dd_stop_pct % [our interpretation of "drawdown or a failed challenge"]."""
    a = date(d.year, 8, 1)
    eq0 = float(p.account_equity) + sum(float(r["net"]) for r in rows if r["date"] < a)
    aug = sorted((r for r in rows if a <= r["date"] < d), key=lambda r: str(r.get("entry_time", r["date"])))
    cur = peak = eq0
    for r in aug:
        cur += float(r["net"])
        peak = max(peak, cur)
    return bool(aug and eq0 and ((peak - cur) / eq0 * 100.0 >= p.aug_dd_stop_pct or (cur - eq0) / eq0 * 100.0 <= -p.aug_dd_stop_pct))


def cap_day_trades(day_trades: list, p, wk: dict | None) -> list:
    """#18: the month's budget in ENTRY-time order (backtest.run truncates the day's trades the same way as the weekly one)."""
    if not p.max_trades_month:
        return day_trades
    left = max(0, p.max_trades_month - int((wk or {}).get("month_n", 0)))
    return sorted(day_trades, key=lambda t_: t_.entry_time)[:left]


# --------------------------------------------------------------------------------------------------------------
# the DayPlan part
# --------------------------------------------------------------------------------------------------------------

def swept_first(x, prev, wb: int) -> bool:
    """#126 one day's signature: the session first traded beyond the prior day's high (bearish bias) / low (bullish) BEFORE the day's extreme in the bias direction formed (bar order)."""
    h, l = x.high.values, x.low.values
    if wb < 0:
        a = np.nonzero(h > float(prev.high.max()))[0]
        b = int(np.argmin(l))
    else:
        a = np.nonzero(l < float(prev.low.min()))[0]
        b = int(np.argmax(h))
    return bool(len(a) and int(a[0]) < b)


def choppy_week(hist, d: date, wb: int, n: int = 2) -> bool:
    """#126 N8-choppy-week-no-hold (079 ~00:21:40): the last `n` completed sessions of this week each swept the prior day's high first (bearish week; the low in a bullish week) before moving
    in the bias direction. Monday's prior day is the previous Friday. No bias = False."""
    if not wb:
        return False
    wk = D1._this_week(hist, d)
    if len(wk) < n:
        return False
    pos = {x.index[0].date(): k for k, x in enumerate(hist)}
    for x in wk[-n:]:
        k = pos.get(x.index[0].date(), 0)
        if k == 0 or not swept_first(x, hist[k - 1], wb):
            return False
    return True


def carry_draw(hist, d: date):
    """#27 N10-unmet-target-carries-to-monday (061 ~02:32:51): (side, level) of the previous completed week's weekly draw when that week did not reach it, else None. Same definition as
    dwc2.carried_bias [our interpretation: the draw is the 4-week extreme beyond the week's open, the bias is the weekly tone before that week]."""
    wb = D1._week_bars(hist, d)
    if len(wb) < 2:
        return None
    o, h, l, c, first = wb[-1]
    b = D1.weekly_state(hist, first)
    prior = wb[-5:-1]
    if not b or not prior:
        return None
    if b > 0:
        tgt = max(x[1] for x in prior)
        return (1, tgt) if (tgt > o and h < tgt) else None
    tgt = min(x[2] for x in prior)
    return (-1, tgt) if (tgt < o and l > tgt) else None


def _week_open(ctx, hist, d: date):
    """The week's open: the Sunday 18:00 reopen (the evening before a Monday; the first session's all-hours open from `eth` later in the week), else the first regular open [our interpretation]."""
    first = d
    for x in CAL.week_dates(d):
        if CAL.is_trading_day(x):
            first = x
            break
    if first == d:
        ev = getattr(ctx, "eve", None)
        return float(ev[0]) if ev else float(ctx.o[ctx.start])
    eth = getattr(ctx, "eth", None)
    if eth and first in eth:
        return float(eth[first][0])
    cur = D1._this_week(hist, d)
    return float(cur[0].open.iloc[0]) if cur else None


def mw_draw_hit(ctx, hist, d: date, p):
    """#28: the week's HTF draw levels (daycontext._week_objective_levels, names in p.week_done_levels) delivered by the Mon-Wed sessions: (names, trend sign). The sign is that of the delivered
    level (a high up, a low down), else the sign of the Monday open -> Wednesday close move."""
    DW = _DW()
    eth = getattr(ctx, "eth", None)
    mw = [x for x in D1._this_week(hist, d) if x.index[0].date().weekday() <= 2]
    if not mw:
        return [], 0
    lv = DW._week_objective_levels(ctx, hist, d, p, eth)
    hi, lo = DW._week_hl(mw, eth, True)
    names, sign = [], 0
    for n in p.week_done_levels:
        if n not in lv:
            continue
        v, kind = lv[n]
        if kind == "high" and hi >= v:
            names.append(n); sign = sign or 1
        elif kind == "low" and lo <= v:
            names.append(n); sign = sign or -1
        elif kind == "ce_up" and lo <= v:
            names.append(n)
        elif kind == "ce_dn" and hi >= v:
            names.append(n)
    if names and not sign:
        sign = int(np.sign(float(mw[-1].close.iloc[-1]) - float(mw[0].open.iloc[0])))
    return names, sign


def week_started(hist, d: date, a5: float, p):
    """#32: (sign, week extreme) when the weekly move has visibly started Mon-Wed: the week's low (high) set Mon-Wed and the last Mon-Wed close >= 30% of 5 x ADR5 away from it [our interpretation].
    Needs all of Mon-Wed completed (Thursday / Friday only)."""
    mw = [x for x in D1._this_week(hist, d) if x.index[0].date().weekday() <= 2]
    if len(mw) < 2 or not a5:
        return 0, None
    lo = min(float(x.low.min()) for x in mw)
    hi = max(float(x.high.max()) for x in mw)
    c = float(mw[-1].close.iloc[-1])
    need = 0.30 * 5.0 * a5
    up, dn = c - lo, hi - c
    if up >= need and up >= dn:
        return 1, lo
    if dn >= need:
        return -1, hi
    return 0, None


def trending_week(hist, d: date, a5: float, p) -> int:
    """#31 N10-mon-wed-extreme-trending-week (cc07_006 ~00:21:27): +1 / -1 when the previous completed week's range >= 5 x ADR5 x `trend_k` and it closed in its outer quarter [our
    interpretation of "trending"]; the sign is the side of the close."""
    if not a5:
        return 0
    wb = D1._week_bars(hist, d)
    if not wb:
        return 0
    o, h, l, c, _f = wb[-1]
    rg = h - l
    if rg < 5.0 * a5 * p.trend_k or rg <= 0:
        return 0
    if c >= h - 0.25 * rg:
        return 1
    if c <= l + 0.25 * rg:
        return -1
    return 0


def plan_rules(P, ctx, d: date, p, hist, eth, a5, dt) -> None:
    """Everything of this package known before the session opens (completed candles, the calendar, the week state). `dt` = strategy.day_context's tags."""
    dt = dt or set()
    tg = P.tags
    DW = _DW()
    wd = d.weekday()
    week = getattr(ctx, "week", None) or {}
    # --- #18 / #38: the month's and the low-magnitude season's trade budgets join the week's budget (DayPlan.info["week_left"], read by daycontext.budget_full and the run_day truncation)
    low_mag = d.month in p.low_mag_months
    if low_mag:
        tg.add("low_mag_season")                          # E9: every date in low_mag_months carries the tag (the cap / size switches act on it separately)
    budgets = []
    if p.max_trades_month:
        budgets.append(("month_cap", int(p.max_trades_month) - int(week.get("month_n", 0))))
    if p.low_mag_week_cap and low_mag:
        budgets.append(("low_mag_cap", int(p.low_mag_week_cap) - int(week.get("n", 0))))
    for reason, left in budgets:
        left = max(0, left)
        P.info["week_left"] = min(left, P.info.get("week_left", left))
        if left <= 0:
            P.block(None, reason)
            hit("budget_block")
    # --- #57 N8-consolidation-pm-news (cc10_008 ~00:16:34): a consolidation day with a PM release: the AM setup is not expected
    if p.consol_pm_news_skip_am and consol_tagged(P, ctx, d, p, hist, eth):
        rel = [r for r in CAL.release_times(d, minutes=True) if r >= 720]
        if rel or "fomc" in events(d):
            P.block(("AM",), "consol_pm_news")
            tg.add("consol_pm_news")
            hit("consol_pm_news")
    wb = 0
    need_wb = bool(p.choppy_week_tag or p.weekly_po3 or p.thu_targets_met_block or p.missed_week_mode != "off")
    if need_wb:
        wb = D2.weekly_bias(ctx, hist, d, p)
        P.info["wk_bias3"] = wb
    # --- #126 N8-choppy-week-no-hold
    if p.choppy_week_tag and wd >= 2 and choppy_week(hist, d, wb, p.choppy_week_days):
        tg.add("choppy_week")
        P.info["choppy_week"] = True
        hit("choppy_week")
    # --- #27 N10-unmet-target-carries-to-monday
    if p.carry_weekly_draw and (wd in (0, 1) or (wd >= 2 and p.carry_neutral_after)):       # Wed-Fri: only the neutral-after-hit state (the carry side / pool stay Mon-Tue)
        cd = carry_draw(hist, d)
        if cd is not None:
            side, lvl = cd
            done = [x for x in D1._this_week(hist, d) if (float(x.high.max()) >= lvl if side > 0 else float(x.low.min()) <= lvl)]
            if done:
                if p.carry_neutral_after:
                    P.info["carry_neutral"] = True
                    tg.add("carry_neutral")
                    hit("carry_neutral")
            elif wd in (0, 1):
                P.info["carry"] = (side, lvl)
                tg.add("carry_weekly_draw")
                P.side_block("carry_weekly_draw", (-side,))
                hit("carry_active")
    # --- #28 N10-thursday-reversal-after-targets-met
    if p.thu_targets_met_block and wd in (3, 4):
        names, sg = mw_draw_hit(ctx, hist, d, p)
        if names and sg:
            tg.add("thu_after_targets")
            P.info["thu_after"] = sg
            P.side_block("thu_targets", (sg,))                    # the with-trend side is blocked Thursday and Friday
            hit("thu_after_targets")
    # --- #32 N10-missed-mon-wed-no-chase
    if p.missed_week_mode != "off" and wd in (3, 4) and a5:
        sg, ext = week_started(hist, d, a5, p)
        wins = [1 for s_, n_ in week.get("week_trades", []) if (s_ == "long") == (sg > 0) and n_ > 0]
        if sg and not wins:
            tg.add("missed_week")
            P.info["missed_week"] = sg
            hit("missed_week_" + p.missed_week_mode)
            if p.missed_week_mode == "skip":
                P.block(None, "missed_week")
    # --- #31 N10-mon-wed-extreme-trending-week
    if p.mw_extreme_need_array and wd <= 2:
        tw = trending_week(hist, d, a5, p)
        if tw:
            P.info["mw_trend"] = tw
            tg.add("mw_trend_week")
            hit("mw_trend_week")
    if wd in (3, 4) and a5 and (p.mw_extreme_need_array or p.missed_week_mode != "off"):
        wk = D1._this_week(hist, d)
        if wk:
            hi = max(float(x.high.max()) for x in wk)
            lo = min(float(x.low.min()) for x in wk)
            ihi = max(range(len(wk)), key=lambda q: float(wk[q].high.max()))
            ilo = min(range(len(wk)), key=lambda q: float(wk[q].low.min()))
            tg.add("wk_hi_dow_%d" % wk[ihi].index[0].date().weekday())
            tg.add("wk_lo_dow_%d" % wk[ilo].index[0].date().weekday())
    # --- #180 M17-weekly-judas-po3
    if p.weekly_po3 and wd <= 2 and wb:
        wo = _week_open(ctx, hist, d)
        if wo is not None:
            P.info["weekly_po3"] = (wb, wo)
            tg.add("weekly_po3")
            hit("weekly_po3_plan")
    # --- #38 E9-may-october: the tag only (the size multiplier is size_mult)
    # --- #11 N9-pm-narrative-from-am-chop: the static parts are read in the gate at the first PM bar
    # --- #30 T3: consol_overnight is read at the bar (the overnight range is complete at 09:30)


def consol_tagged(P, ctx, d: date, p, hist, eth) -> bool:
    """A consolidation day known before the open (#57 / #35 / #121): the DayPlan tag (consolidation_mode / consol_day_rules) or the N8.3 predictors (>= consol_min_predictors)."""
    if "consol_day" in P.tags:
        return True
    c = _cache(ctx)
    if "ct" not in c:
        try:
            c["ct"] = len(_DW()._consol_predictors(ctx, d, p, hist, eth)) >= p.consol_min_predictors
        except Exception:
            c["ct"] = False
    return bool(c["ct"])


# --------------------------------------------------------------------------------------------------------------
# bars helpers
# --------------------------------------------------------------------------------------------------------------

def _range_bars(ctx, i: int, a: int, b: int):
    """(high, low) of today's bars with start minute in [a, b) through the closed bar i, None when none."""
    return _DW()._run(ctx, "d3_%d_%d" % (a, b), i, a, b)


def mss_after(ctx, side: int, j: int, i: int, from_t: int = 0):
    """Real-price MSS: after a high at bar j (side>0) a close below the last pivot low (2-bar confirmed, formed before j); after a low at j (side<0) a close above the last pivot high. Returns the
    bar index of the first such close in (j, i] whose bar starts at or after minute `from_t`, else None."""
    n = 2
    h, l, c = ctx.h, ctx.l, ctx.c
    lo = max(ctx.start, j - 60)
    if side > 0:
        ref = None
        for q in range(j - n, lo + n - 1, -1):
            if q - n >= ctx.start and l[q] < min(l[q - n:q].min(), l[q + 1:q + n + 1].min()):
                ref = float(l[q])
                break
        if ref is None:
            ref = float(l[lo:j + 1].min())
        for m in range(j + 1, i + 1):
            if c[m] < ref and ctx.t[m] >= from_t:
                return m
    else:
        ref = None
        for q in range(j - n, lo + n - 1, -1):
            if q - n >= ctx.start and h[q] > max(h[q - n:q].max(), h[q + 1:q + n + 1].max()):
                ref = float(h[q])
                break
        if ref is None:
            ref = float(h[lo:j + 1].max())
        for m in range(j + 1, i + 1):
            if c[m] > ref and ctx.t[m] >= from_t:
                return m
    return None


def _k(ctx, minute: int) -> int:
    return _S()._idx_at(ctx, minute)


def _extreme_idx(ctx, ext: int, a: int, b: int, i: int | None = None):
    """Index of the bar with the extreme (ext>0 the high, ext<0 the low) among today's bars with minute in [a, b) (through the closed bar i when given), None when none."""
    m = (ctx.t >= a) & (ctx.t < b)
    m[:ctx.start] = False
    if i is not None:
        m[i + 1:] = False
    if not m.any():
        return None
    idx = np.nonzero(m)[0]
    seg = ctx.h[idx] if ext > 0 else ctx.l[idx]
    return int(idx[int(np.argmax(seg) if ext > 0 else np.argmin(seg))])


# --------------------------------------------------------------------------------------------------------------
# per-bar gates
# --------------------------------------------------------------------------------------------------------------

def _today_net_pts(ctx, p, trades, i: int) -> tuple:
    """(net $, ES points, count) of today's trades closed through the closed bar i (their last exit at or before the bar's start)."""
    ts = ctx.idx[i]
    net = pts = 0.0
    n = 0
    for tr in trades or ():
        if not tr.exits or tr.exits[-1][0] > ts:
            continue
        g, c = tr.pnl(p.cost_per_share)
        net += g - c
        pts += g / max(1, tr.shares) / float(p.es_pt)
        n += 1
    return net, pts, n


def goal_reached(ctx, p, trades, i: int) -> bool:
    """#21 X15-weekly-goal-stop (cc02_001 ~00:22:57; cc02_003 ~00:13:56): the week's closed result (the earlier days from the week state, today's closed trades through bar i) reached
    `weekly_target_pct` % of the start-of-week account or `weekly_cap_pts` ES points. Never adds trades."""
    wk = getattr(ctx, "week", None) or {}
    if not (p.weekly_target_pct or p.weekly_cap_pts):
        return False
    net, pts, n = _today_net_pts(ctx, p, trades, i)
    eq0 = float(wk.get("week_eq0", p.account_equity)) or float(p.account_equity)
    pct = 100.0 * (float(wk.get("week_net3", 0.0)) + net) / eq0 if eq0 else 0.0
    n_tr = int(wk.get("n", 0)) + n
    return bool(n_tr and ((p.weekly_target_pct and pct >= p.weekly_target_pct) or (p.weekly_cap_pts and float(wk.get("week_pts", 0.0)) + pts >= p.weekly_cap_pts)))


def pm_fizzle(ctx, p, i: int) -> bool:
    """#121 T13-consolidation-pm-fizzle (cc10_013 ~00:13:57): True when a bar of the PM (13:30 on, through the closed bar i) has traded beyond the lunch (12:00-13:30) high / low or beyond
    the session (09:30-13:30) high / low. False = no sweep yet (the PM drifts sideways: no trade)."""
    k = _k(ctx, 810)
    if i < k:
        return False
    lunch = _range_bars(ctx, i, 720, 810)
    sess = _range_bars(ctx, i, 570, 810)
    pm = _range_bars(ctx, i, 810, 100000)
    if pm is None:
        return False
    for ref in (lunch, sess):
        if ref is not None and (pm[0] > ref[0] + 1e-12 or pm[1] < ref[1] - 1e-12):
            return True
    return False


def _day_is_consol(ctx, p, P, i: int) -> bool:
    """A consolidation day at bar i: the plan tag / predictors, or the X11c profile classifier at 13:30 (manage.consol_day)."""
    if consol_tagged(P, ctx, ctx.day, p, getattr(ctx, "hist", []), getattr(ctx, "eth", None)):
        return True
    try:
        from . import manage as MG
        return bool(MG.consol_day(ctx, i, p))
    except Exception:
        return False


def pm_narrative(ctx, p, hist, trades=()):
    """#11 N9-pm-narrative-from-am-chop (022 ~02:26:36): (side, gap level) or None, decided once at the first PM bar from the bars before 13:30. Needs (a) the opening gap (ORG) at least
    `pm_narr_gap_pts` pts and still unfilled at 13:30 (the prior close not yet traded), (b) an SMT at the AM extreme against the partner index (no partner = no narrative), (c) at least two
    AM runs of nearby swing extremes (by at most two ticks) with no bar range above the displacement multiple of the AM's mean range, and the AM flagged chop (the chop detector was on in
    the AM, or the AM took no trade). The side is the gap's (toward the prior close); the draw is the gap level. [our interpretation of "large" and "repeated runs"]"""
    c = _cache(ctx)
    if "pmn" in c:
        return c["pmn"]
    k = _k(ctx, 810)
    res = None
    if k < len(ctx.t) and getattr(ctx, "org_today", False) and getattr(ctx, "org", None):
        pc, op = ctx.org[-1]
        a = _k(ctx, 570)
        side = 1 if pc > op else -1
        big = abs(op - pc) >= p.pm_narr_gap_pts * p.es_pt
        seg_h, seg_l = ctx.h[a:k], ctx.l[a:k]
        unfilled = bool(len(seg_h) and ((float(seg_h.max()) < pc) if side > 0 else (float(seg_l.min()) > pc)))
        if big and unfilled:
            am_traded = any(tr.session in ("AM", "PRE8", "PRE9", "NEWS") for tr in (trades or ()))
            ch = getattr(ctx, "chop", None)
            am_chop = bool(ch is not None and not ch.inert and ch.state[a:k].any()) or not am_traded
            if am_chop and _smt_at_am_extreme(ctx, -side, a, k) and _am_runs(ctx, p, side, a, k):
                res = (side, float(pc))
                hit("pm_narrative")
    c["pmn"] = res
    return res


def _smt_at_am_extreme(ctx, ext: int, a: int, k: int):
    """SMT at the AM extreme (ext>0 the AM high, ext<0 the AM low): the partner index did not confirm it - its extreme over the bars around the main's extreme did not exceed the extreme of
    the bars before them [our interpretation; the same test as dwc2._smt_extreme]. False without a partner."""
    pctx, psides, ppos = getattr(ctx, "pside", (None, None, None))
    if pctx is None or k - a < 6:
        return False
    j = _extreme_idx(ctx, ext, 570, 810)
    win = 12
    if j is None or j < a + 1:
        return False
    t0, t1 = ctx.idx[max(ctx.start, j - win)], ctx.idx[j]
    pj1 = int(ppos.index.searchsorted(t1, side="right"))
    pj0 = int(ppos.index.searchsorted(t0, side="left"))
    pa = pctx.start
    if pj0 - pa < 2 or pj1 <= pj0:
        return False
    if ext > 0:
        return bool(float(pctx.h[pj0:pj1].max()) <= float(pctx.h[pa:pj0].max()))
    return bool(float(pctx.l[pj0:pj1].min()) >= float(pctx.l[pa:pj0].min()))


def _am_runs(ctx, p, side: int, a: int, k: int) -> bool:
    """#11 (c): at least two AM swing extremes (the swing lows when the PM bias is long, `side`>0) were run by a later AM bar by at most two ticks, and no AM bar's range is above
    displacement_mult (2.0 when 0) x the AM mean range. [our interpretation]"""
    h, l = ctx.h, ctx.l
    tk = p.tick
    rng = h[a:k] - l[a:k]
    if not len(rng):
        return False
    if float(rng.max()) > (p.displacement_mult or 2.0) * float(rng.mean()):
        return False
    runs = 0
    for q in range(a + 1, k - 2):
        piv = (l[q] < l[q - 1] and l[q] <= l[q + 1]) if side > 0 else (h[q] > h[q - 1] and h[q] >= h[q + 1])
        if not piv:
            continue
        lvl = l[q] if side > 0 else h[q]
        for m in range(q + 2, k):
            beyond = (lvl - l[m]) if side > 0 else (h[m] - lvl)
            if beyond > 1e-12:
                if beyond <= 2 * tk + 1e-12:
                    runs += 1
                break
    return runs >= 2


def tgif_tag(ctx) -> str:
    """"tgif_short" / "tgif_long" from the day's tags, else ''."""
    tg = str(getattr(ctx, "day_tags", ""))
    return "tgif_short" if "tgif_short" in tg else ("tgif_long" if "tgif_long" in tg else "")


TGIF_WIN = {"am": (570, 720), "london_close": (600, 720), "pm": (810, 900)}


def tgif_array_needed(p) -> bool:
    """M14-tgif-am-timing (085 ~00:17:32): the Friday sweep must be at a same-side HTF array - the first-pass `tgif_htf_array`, or (the spec default) `tgif_need_htf_array` with tgif on, unless the
    tgif_model umbrella was told to skip tgif_htf_array."""
    return bool(p.tgif_htf_array or (p.tgif and p.tgif_need_htf_array and "tgif_htf_array" not in p.tgif_model_skip))


def tgif_window_governs(p) -> bool:
    """M14-tgif-am-timing: `tgif_window` is the TGIF entry window with tgif on; under the tgif_model umbrella the M14.3 `tgif_timing` windows stay authoritative unless "tgif_timing" is in
    tgif_model_skip."""
    return bool(p.tgif and p.tgif_window != "off" and (not p.tgif_model or "tgif_timing" in p.tgif_model_skip))


def oneway_week_so_far(hist, d: date, ext: int) -> bool:
    """#33 tgif_thu precondition: the Monday-Wednesday range of d's week is >= 1.5 x the average of the prior weeks' ranges (two prior weeks needed) and Wednesday closed in the outer quarter
    toward `ext` (the week's low for ext<0, the high for ext>0) - the same large one-way-week test as the Friday TGIF tag, a day earlier."""
    wk = [x for x in D1._this_week(hist, d) if x.index[0].date().weekday() <= 2]
    if len(wk) < 3:
        return False
    mon = wk[0].index[0].date()
    prior = {}
    for x in hist:
        if x.index[0].date() < mon:
            prior.setdefault(x.index[0].date().isocalendar()[:2], []).append(x)
    if len(prior) < 2:
        return False
    avg = float(np.mean([max(float(x.high.max()) for x in v) - min(float(x.low.min()) for x in v) for v in prior.values()]))
    hi, lo = max(float(x.high.max()) for x in wk), min(float(x.low.min()) for x in wk)
    c = float(wk[-1].close.iloc[-1])
    if hi - lo < 1.5 * avg:
        return False
    return bool(c <= lo + 0.25 * (hi - lo)) if ext < 0 else bool(c >= hi - 0.25 * (hi - lo))


def tgif_seq_ok(ctx, p, hist, i: int, t: int, tag: str):
    """#33 M14-tgif-timing-and-precondition (084 ~00:15:56) item (3) Friday sequencing: with a new weekly low (high for tgif_short) printed in the Friday AM (09:30-12:00) the TGIF entry
    window is 10:00-12:00; with the 10:00-12:00 range under `tgif_consol_frac` x ADR5 it moves to 13:30-15:00. None = allowed, else the reject key. No new extreme = unconstrained."""
    wk = D1._this_week(hist, ctx.day)
    if not wk:
        return None
    r = _range_bars(ctx, i, 570, 720)
    if r is None:
        return None
    if tag == "tgif_long":
        new = r[1] < min(float(x.low.min()) for x in wk) - 1e-12
    else:
        new = r[0] > max(float(x.high.max()) for x in wk) + 1e-12
    if not new:
        return None
    hit("tgif_seq_newext")
    if t < 600:
        return "x_dw_tgif_seq_wait"
    if t < 720:
        return None
    a5 = _DW()._adr(ctx, p)
    rr = _range_bars(ctx, i, 600, 720)
    consol = bool(rr is not None and a5 and (rr[0] - rr[1]) < p.tgif_consol_frac * a5)
    if consol and 810 <= t < 900:
        hit("tgif_seq_pm")
        return None
    return "x_dw_tgif_seq_window"


def gate(ctx, p, session: str, i: int, t: int, trades=()):
    """Per-bar session gates: #21 weekly goal, #121 PM fizzle, #35 PM pool exit, #11 PM narrative done, #90 / #33 TGIF windows and sequencing, #11 checklist."""
    P = getattr(ctx, "dplan", None)
    if P is None:
        return None
    DW = _DW()
    d = ctx.day
    hist = getattr(ctx, "hist", [])
    late = session in DW.LATE
    # #21 X15-weekly-goal-stop
    if (p.weekly_target_pct or p.weekly_cap_pts) and goal_reached(ctx, p, trades, i):
        hit("weekly_goal")
        return "x_dw_weekly_goal"
    # #121 T13-consolidation-pm-fizzle
    if p.consol_pm_need_sweep and session == "PM" and t >= 810 and _day_is_consol(ctx, p, P, i) and not pm_fizzle(ctx, p, i):
        hit("pm_fizzle")
        return "x_dw_pm_fizzle"
    # #35 N8-consolidation-pm-full-exit-at-pool
    if p.consol_pm_pool_exit and late and _day_is_consol(ctx, p, P, i):
        if DW.am_ran_pool(ctx, hist, i, ("pd", "on")):
            hit("pm_pool_run_am")
            return "x_dw_consol_pm_pool_run"
        if any("consol_pm_pool" in str(tr.lv_tags) for tr in (trades or ())):
            hit("pm_pool_done")
            return "x_dw_consol_pm_pool_done"
    # #11 N9-pm-narrative-from-am-chop
    if p.pm_narrative and session == "PM" and t >= 810:
        nv = pm_narrative(ctx, p, hist, trades)
        if nv is not None and any(tr.session == "PM" for tr in (trades or ())):
            hit("pm_narr_done")
            return "x_dw_pm_narr_done"
    # TGIF windows (Fridays with a TGIF tag)
    if d.weekday() == 4:
        tag = tgif_tag(ctx) if p.tgif else ""            # (the windows / sequencing act only with tgif on - the tag is computed on every Friday)
        if tag:
            if tgif_window_governs(p):
                a, b = TGIF_WIN[p.tgif_window]
                if not a <= t < b:
                    hit("tgif_window_block")
                    return "x_dw_tgif_window"
            if p.tgif_seq:
                why = tgif_seq_ok(ctx, p, hist, i, t, tag)
                if why:
                    hit("tgif_seq_block")
                    return why
    # #11 OT-pre-session-checklist-order
    if p.checklist != "off":
        fails = checklist_for(ctx, p, session, i, t)
        if fails and p.checklist == "gate":
            hit("checklist_gate")
            return "x_dw_checklist"
    return None


# --------------------------------------------------------------------------------------------------------------
# the pre-session checklist (#11)
# --------------------------------------------------------------------------------------------------------------

def checklist(ctx, hist, day: date, session: str, p, i: int, t: int) -> dict:
    """OT-pre-session-checklist-order (cc12_004 ~00:22:21): {step: ok} for the steps the bot can read: htf, dow, ipda, kz, profile, levels, adr (steps 5-7, the fx CBDR / Asian / flout, are
    not computed)."""
    DW = _DW()
    out = {}
    b = DW._bias_side(ctx, p, i) if p.htf_bias != "off" else D2._combo(ctx, i)
    out["htf"] = b != 0
    wd = day.weekday()
    wkd = getattr(ctx, "week", None) or {}
    out["dow"] = bool(wd in p.cl_days or (wd in (3, 4) and int(wkd.get("final_hits", 0)) == 0))
    pm = session in DW.LATE
    # [our interpretation of the IPDA true day, bulk 03:00-10:00 NY] every pre-open / AM session window lies inside it; the PM fails the step unless cl_pm_ok
    out["ipda"] = bool((180 <= t < 600) if not pm else p.cl_pm_ok)       # the session window must START inside 03:00-10:00 (t = the session's first gated bar); a 10:00+ window fails
    # the kill zones: the AM window, the Silver Bullet windows, the London window (a PM arming is inside only when a Silver Bullet window holds it)
    out["kz"] = bool((p.am_win[0] <= t < p.am_win[1]) or any(a <= t < b_ for a, b_ in p.sb_windows) or (120 <= t < 300) or session in ("PRE7", "PRE8", "PRE9", "LON", "NEWS"))
    ok = True
    cf = getattr(ctx, "conf", None)
    if p.profile_tags and cf is not None and b:
        now = ctx.idx[i] + pd.Timedelta(minutes=ctx.tf)
        d_, h4_ = cf.trend(now, "D"), cf.trend(now, "4h")
        ok = (1 if (d_ == 1 and h4_ == 1) else (-1 if (d_ == -1 and h4_ == -1) else 0)) == b
    out["profile"] = bool(ok)
    lk = (getattr(ctx, "lock", None) or {}).get("AM" if session == "LUNCH" else session)
    out["levels"] = bool((lk is not None and lk.get("side")) or D2._draw(ctx, i) != 0)
    a5 = DW._adr(ctx, p)
    adr_ok = True
    if a5 and b and i >= ctx.start:
        if b > 0:
            adr_ok = float(ctx.h[ctx.start:i + 1].max()) < float(ctx.l[ctx.start:i + 1].min()) + a5
        else:
            adr_ok = float(ctx.l[ctx.start:i + 1].min()) > float(ctx.h[ctx.start:i + 1].max()) - a5
    out["adr"] = bool(adr_ok)
    return out


def checklist_for(ctx, p, session: str, i: int, t: int) -> str:
    """The failing step names of the session (evaluated once per session at its first gated bar, then cached), '' when all are green."""
    c = _cache(ctx).setdefault("cl", {})
    if session not in c:
        r = checklist(ctx, getattr(ctx, "hist", []), ctx.day, session, p, i, t)
        c[session] = ",".join(k for k, v in r.items() if not v)
        ctx.cl = c                                       # the per-session failing steps (read by stamp -> Trade.cl_fail)
        hit("checklist_eval")
        if c[session]:
            hit("checklist_fail")
            sk = getattr(ctx, "skips_ref", None)
            if sk is not None:
                sk.append((ctx.day, getattr(ctx, "symbol", ""), "checklist", f"{session}:{c[session]}"))
    return c[session]


# --------------------------------------------------------------------------------------------------------------
# side filters
# --------------------------------------------------------------------------------------------------------------

def thu_extreme_held(ctx, hist, i: int, ext: int) -> bool:
    """#33 tgif_thu: Thursday has made the week's low (ext<0; the high for ext>0) after 10:00, with Wednesday's low (high) taken at an earlier bar."""
    wk = [x for x in D1._this_week(hist, ctx.day) if x.index[0].date().weekday() <= 2]
    if len(wk) < 2 or i < ctx.start or wk[-1].index[0].date().weekday() != 2:
        return False
    wed = wk[-1]
    wk_ext = min(float(x.low.min()) for x in wk) if ext < 0 else max(float(x.high.max()) for x in wk)
    seg = ctx.l[ctx.start:i + 1] if ext < 0 else ctx.h[ctx.start:i + 1]
    if not len(seg):
        return False
    j = ctx.start + int(np.argmin(seg) if ext < 0 else np.argmax(seg))
    val = float(ctx.l[j]) if ext < 0 else float(ctx.h[j])
    if (val >= wk_ext) if ext < 0 else (val <= wk_ext):
        return False                                             # not the week's extreme
    if ctx.t[j] < 600:
        return False
    wref = float(wed.low.min()) if ext < 0 else float(wed.high.max())
    brk = np.nonzero((ctx.l[ctx.start:j + 1] < wref) if ext < 0 else (ctx.h[ctx.start:j + 1] > wref))[0]
    return bool(len(brk) and ctx.start + int(brk[0]) < j)


def tgif_branch_ok(ctx, p, hist, sign: int, i: int, t: int, tag: str):
    """#50 M14-tgif-timing (066 ~00:46:41), the retrace-side orders of a TGIF Friday: with a Judas at 09:30 (09:30-10:00 ran beyond the week-to-date extreme and the MSS formed before
    10:15) entries are allowed from 10:00 after the MSS; otherwise the AM is blocked and entries are allowed from `tgif_pm_from` after an MSS whose extreme formed 11:30-14:00. None = allowed."""
    ext = 1 if tag == "tgif_short" else -1                       # the week extreme being faded: a high for tgif_short
    if sign != -ext:
        return None
    wk = D1._this_week(hist, ctx.day)
    if not wk:
        return None
    wref = max(float(x.high.max()) for x in wk) if ext > 0 else min(float(x.low.min()) for x in wk)
    r = _range_bars(ctx, i, 570, 600)
    judas = False
    if r is not None and ((r[0] > wref + 1e-12) if ext > 0 else (r[1] < wref - 1e-12)):
        j = _extreme_idx(ctx, ext, 570, 600, i)
        m = None if j is None else mss_after(ctx, ext, j, i)
        judas = bool(m is not None and ctx.t[m] + ctx.tf <= 615)
    if judas:
        hit("tgif_branch_judas")
        return None if t >= 600 else "x_dw_tgif_branch_wait"
    if t < p.tgif_pm_from:
        hit("tgif_branch_am_block")
        return "x_dw_tgif_branch_am"
    j = _extreme_idx(ctx, ext, 570, 100000, i)
    if j is None or not 690 <= ctx.t[j] < 840:
        hit("tgif_branch_pm_time")
        return "x_dw_tgif_branch_pm"
    if mss_after(ctx, ext, j, i) is None:
        hit("tgif_branch_pm_mss")
        return "x_dw_tgif_branch_pm"
    hit("tgif_branch_pm_ok")
    return None


def consol_overnight(ctx, p, i: int) -> bool:
    """#30 T3-london-extreme-consolidation (010 ~00:39:18): the prior regular session's range was under 0.6 x ADR5 and the overnight (00:00-09:30) range stays inside it. Read from the first
    bar at or after 09:30 only (the overnight range is complete then)."""
    if i < _k(ctx, 570):
        return False
    c = _cache(ctx)
    if "co" not in c:
        hist = getattr(ctx, "hist", [])
        a5 = _DW()._adr(ctx, p)
        ok = False
        if hist and a5:
            ph, pl = _hl(hist[-1])
            m = (ctx.t < 570)
            m[:ctx.start] = False
            if m.any() and (ph - pl) < 0.6 * a5:
                ok = bool(float(ctx.h[m].max()) <= ph + 1e-12 and float(ctx.l[m].min()) >= pl - 1e-12)
        c["co"] = ok
    return bool(c["co"])


def london_unprotected(ctx, p, i: int) -> bool:
    """#30 london_ext_consol: on a consol_overnight day the London high / low is a pool, not the day's protected extreme (dwc2's London guard and extreme requirement stand down)."""
    return bool(p.london_ext_consol and consol_overnight(ctx, p, i))


# --------------------------------------------------------------------------------------------------------------
# lunch behaviours (#14)
# --------------------------------------------------------------------------------------------------------------

def lunch_state(ctx, p, i: int):
    """#14 T8-lunch-three-behaviours-reversal (073 ~00:29:35; 059 ~00:15:28; 007 ~00:09:44): None before 11:50. Else {kind, am_dir, noon_i, rev_i}:
      kind at 11:50 "consol" (the AM lock's draw delivered), "run" (the lock undelivered and the opposite pool already taken), else "open";
      noon_i  the first bar of 11:50-12:15 (through the closed bar i) that traded into the far edge of a 1h FVG on the AM side (htf arrays "1h") or into the AM lock's draw: the likely HOD / LOD;
      rev_i   an MSS against the AM direction that closed at or after 12:00 with noon_i set -> kind "reversal"."""
    k710 = _k(ctx, 710)
    if i < k710 or k710 >= len(ctx.t):
        return None
    c = _cache(ctx)
    if "lunch0" not in c:
        a = _k(ctx, 570)
        ji_h = _extreme_idx(ctx, 1, 570, 710, k710 - 1)
        ji_l = _extreme_idx(ctx, -1, 570, 710, k710 - 1)
        if ji_h is None or ji_l is None:
            c["lunch0"] = None
        else:
            am_dir = 1 if ji_h > ji_l else -1
            lk = (getattr(ctx, "lock", None) or {}).get("AM")
            deliv = bool(lk is not None and lk.get("delivered") and (lk.get("delivered_i") is None or lk.get("delivered_i") < k710))
            kind = "open"
            if deliv:
                kind = "consol"
            elif lk is not None and lk.get("side"):
                s = lk["side"]
                pk = ("pdl1" if s > 0 else "pdh1")
                hl = _range_bars(ctx, k710 - 1, 570, 710)
                if pk in ctx.pd and hl is not None and ((hl[1] < ctx.pd[pk]) if s > 0 else (hl[0] > ctx.pd[pk])):
                    kind = "run"
            far = []
            cf = getattr(ctx, "conf", None)
            if cf is not None:
                try:
                    now = ctx.idx[k710 - 1] + pd.Timedelta(minutes=ctx.tf)
                    ref = float(ctx.l[a:k710].min()) if am_dir > 0 else float(ctx.h[a:k710].max())
                    far = list(cf.targets(now, ref, am_dir, ("1h",), far_edge=True))
                except Exception:
                    far = []
            if lk is not None and lk.get("side") == am_dir and lk.get("target") is not None:       # (a draw delivered before 11:50 is behaviour (1), not a noon extreme)
                far.append(float(lk["target"]))
            c["lunch0"] = dict(kind=kind, am_dir=am_dir, far=far)
    base = c["lunch0"]
    if base is None:
        return None
    am_dir = base["am_dir"]
    noon_i = None
    for q in range(k710, min(i, _k(ctx, 735) - 1) + 1):
        if any((ctx.h[q] >= v - 1e-12) if am_dir > 0 else (ctx.l[q] <= v + 1e-12) for v in base["far"]):
            noon_i = q
            break
    rev_i = None
    kind = base["kind"]
    if noon_i is not None:
        m = mss_after(ctx, am_dir, noon_i, i, 720)        # the first MSS close AT OR AFTER 12:00 (an earlier 11:50-11:59 close does not hide it)
        if m is not None:
            rev_i, kind = m, "reversal"
    return dict(kind=kind, am_dir=am_dir, noon_i=noon_i, rev_i=rev_i)


def noon_rev_exit(ctx, sd, pos, tr, i: int, ts, p, c: float) -> bool:
    """#14 noon_rev_flat: the lunch reversal printed (MSS against the morning after a noon extreme) -> every open position in the AM direction closes at the close of that bar, reason
    "noon_rev"."""
    if not pos["left"] or i < ctx.start:
        return False
    st = lunch_state(ctx, p, i)
    if st is None or st["kind"] != "reversal":
        return False
    if (1 if tr.side == "long" else -1) != st["am_dir"] or i < st["rev_i"]:
        return False
    tr.exits.append((ts, sd.x(c), pos["left"], "noon_rev"))
    pos["left"] = 0
    hit("noon_rev_flat")
    return True


def side_ok(ctx, p, sign: int, session: str, i: int):
    """Side filters: #180 weekly PO3, #33 TGIF Thursday, #50 TGIF branch, #14 noon-reversal PM side, #11 PM narrative side."""
    P = getattr(ctx, "dplan", None)
    if P is None:
        return None
    DW = _DW()
    d = ctx.day
    t = int(ctx.t[i])
    hist = getattr(ctx, "hist", [])
    wp = P.info.get("weekly_po3")
    if wp:
        wb, wo = wp
        if sign == -wb:
            hit("weekly_po3_side")
            return "x_dw_weekly_po3_side"
        c_ = float(ctx.c[i])
        if (wb < 0 and c_ <= wo) or (wb > 0 and c_ >= wo):
            hit("weekly_po3_open")
            return "x_dw_weekly_po3_open"
    if p.tgif and p.tgif_thu and d.weekday() == 3 and session in DW.LATE:
        for ext in (-1, 1):
            if sign == ext and oneway_week_so_far(hist, d, ext) and thu_extreme_held(ctx, hist, i, ext):
                hit("tgif_thu_block")
                return "x_dw_tgif_thu"
    if p.tgif and p.tgif_branch and d.weekday() == 4:
        tag = tgif_tag(ctx)
        if tag:
            why = tgif_branch_ok(ctx, p, hist, sign, i, t, tag)
            if why:
                return why
    if p.noon_rev_pm and session in ("PM", "LUNCH"):
        st = lunch_state(ctx, p, i)
        if st is not None and st["kind"] == "reversal" and sign == st["am_dir"]:
            hit("noon_rev_pm_side")
            return "x_dw_noon_rev_side"
    if p.pm_narrative and session == "PM" and t >= 810:
        nv = pm_narrative(ctx, p, hist)
        if nv is not None and sign != nv[0]:
            hit("pm_narr_side")
            return "x_dw_pm_narr_side"
    return None


# --------------------------------------------------------------------------------------------------------------
# per-order filters
# --------------------------------------------------------------------------------------------------------------

def single_first(o: dict) -> bool:
    """Keep only the first (nearest) target of the order: one exit of the whole position, no runner, no adds (side space). False when the order has no target."""
    if not o.get("levels"):
        return False
    v = o["levels"][0]
    if len(o["levels"]) > 1 or o.get("rung_plan"):
        if not D2._cap_levels(o, v):
            return False
    o["levels"] = [v]
    o["level_kinds"] = list(o["level_kinds"])[:1]
    o["t1"], o["t2"] = v, None
    o["final_T"] = True
    o["scalp"] = True
    o["no_adds"] = True
    o["fracs_fixed"] = (1.0,)
    o.pop("runner", None)
    o.pop("htf_runner", None)
    rp = o.get("rung_plan")
    if rp:
        m0 = next((x for x in rp if x["role"] == "main"), None)
        o["rung_plan"] = [dict(m0, v=v)] if m0 is not None else rp
    return True


def pool_levels(ctx, sd, i: int) -> list:
    """#35: the reference pools of a consolidation PM scalp, side space (name, level, minute the pool counts from): the overnight high / low (untapped = not traded since 09:30), the prior
    day's high / low (since the day's first bar) and the AM (09:30-12:00) high / low (since 12:00)."""
    out = []
    k = "pmh" if sd.sign > 0 else "pml"
    if k in ctx.pd:
        out.append(("onh", float(sd.x(ctx.pd[k])), 570))
    pk = "pdh1" if sd.sign > 0 else "pdl1"
    if pk in ctx.pd:
        out.append(("pd", float(sd.x(ctx.pd[pk])), 0))
    am = _range_bars(ctx, i, 570, 720) if ctx.t[i] >= 720 else None          # the AM range is complete from 12:00 (read through the closed bar i only)
    if am is not None:
        out.append(("am", float(sd.x(am[0] if sd.sign > 0 else am[1])), 720))
    return out


def add_rung(o: dict, v: float, kind: str, tol: float) -> bool:
    """Add one target rung (side space) beyond the entry unless one lies within `tol` of it (same shape as dwc2._range_rungs). False when nothing was added."""
    if v <= o["entry"] + 1e-9:
        return False
    lv, kd = list(o["levels"]), list(o["level_kinds"])
    if any(abs(v - x) <= tol for x in lv):
        return False
    lv.append(v)
    kd.append(kind)
    rp = o.get("rung_plan")
    if rp:
        m0 = next((x for x in rp if x["role"] == "main"), None)
        if m0 is not None:
            rp.append(dict(m0, v=v, k=kind))
            rp.sort(key=lambda x: x["v"])
    order = sorted(range(len(lv)), key=lambda q: lv[q])
    o["levels"] = [lv[q] for q in order]
    o["level_kinds"] = [kd[q] for q in order]
    o["t1"] = o["levels"][0]
    o["t2"] = o["levels"][1] if len(o["levels"]) > 1 else None
    return True


def _now(ctx, i: int):
    return ctx.idx[i] + pd.Timedelta(minutes=ctx.tf)


def htf_discount_hit(ctx, sd, o: dict, i: int, p) -> bool:
    """#31: the order's sweep extreme (or entry) sits inside a valid daily / weekly array of its side (bullish for longs, bearish for shorts), or at the 20 / 40 / 60-day extreme (the IPDA
    pools) [our interpretation: within four ticks, swept counts]."""
    cf = getattr(ctx, "conf", None)
    DW = _DW()
    now = _now(ctx, i)
    ext_real, ent_real = float(sd.x(o["ext"])), float(sd.x(o["entry"]))
    if cf is not None:
        tol = getattr(cf, "tol", 0.0)
        for px in (ext_real, ent_real):
            if DW._array_touch(cf, now, px, sd.sign, ("D", "W"), tol):
                return True
    hist = getattr(ctx, "hist", [])
    tk = 4 * p.tick
    for n in (20, 40, 60):
        seg = hist[-n:]
        if len(seg) < max(5, n // 2):
            continue
        if sd.sign > 0:
            lv = min(float(x.low.min()) for x in seg)
            if ext_real <= lv + tk:
                return True
        else:
            lv = max(float(x.high.max()) for x in seg)
            if ext_real >= lv - tk:
                return True
    return False


def _final_target_htf(ctx, sd, o: dict, i: int, p) -> bool:
    """#20 (a): the order's FINAL target is a daily / weekly array edge or CE, the previous day's high / low (PDH / PDL: pdh1 / pdl1 only), the previous week's high / low or an NWOG level (matched to
    two ticks). Matched by price against the level sets (the order carries no level_kinds before it is placed)."""
    if not o.get("levels"):
        return False
    real = float(sd.x(o["levels"][-1]))
    tol = 2 * p.tick
    cand = []
    for k in ("pdh1", "pdl1"):
        if k in ctx.pd:
            cand.append(float(ctx.pd[k]))
    pw = getattr(ctx, "pw", None)
    if pw is not None:
        cand += [float(pw[0]), float(pw[1])]
    for g in getattr(ctx, "gaps", None) or ():
        if g[0] in ("nwog", "nwog_rth"):                  # the NWOG only (not the NDOG / ORG kinds)
            cand += [float(g[1]), float(g[2]), float(g[3])]
    cf = getattr(ctx, "conf", None)
    if cf is not None:
        try:
            for near, far in cf.arrays_any(_now(ctx, i), sd.sign, ("D", "W")):
                cand += [float(near), float(far), (float(near) + float(far)) / 2.0]
        except Exception:
            hit("htf_quality_conf_err")                   # counted, never silent: a Confluence signature change would show here
    return any(abs(real - v) <= tol for v in cand)


def hourly_swing_near(ctx, sd, i: int, price_real: float, tol: float) -> bool:
    """#20 (b): an hourly (60m) 1-bar swing low (high for shorts), complete by the closed bar i, lies at or just above (below) `price_real` (the sweep extreme) within `tol` - the sweep
    took out a 1h swing. Hourly blocks are built from today's bars (aligned to the hour)."""
    a = ctx.start
    if i <= a:
        return False
    hrs = (ctx.t[a:i + 1] // 60).astype(int)
    blocks = []
    cur = None
    for q in range(a, i + 1):
        hq = int(ctx.t[q] // 60)
        if cur is None or hq != cur[0]:
            cur = [hq, float(ctx.h[q]), float(ctx.l[q])]
            blocks.append(cur)
        else:
            cur[1] = max(cur[1], float(ctx.h[q]))
            cur[2] = min(cur[2], float(ctx.l[q]))
    # the last block is complete only when the closed bar ends the hour
    if int(ctx.t[i] + ctx.tf) % 60 != 0:
        blocks = blocks[:-1]
    for q in range(1, len(blocks) - 1):
        if sd.sign > 0 and blocks[q][2] < blocks[q - 1][2] and blocks[q][2] < blocks[q + 1][2]:
            if price_real - 1e-9 <= blocks[q][2] <= price_real + tol:
                return True
        if sd.sign < 0 and blocks[q][1] > blocks[q - 1][1] and blocks[q][1] > blocks[q + 1][1]:
            if price_real - tol <= blocks[q][1] <= price_real + 1e-9:
                return True
    return False


def htf_quality_ok(ctx, sd, o: dict, i: int, p) -> bool:
    """#20 X15-three-per-week-htf-quality (099 ~00:47:36): the final target is a daily / weekly array, PDH / PDL, PWH / PWL or NWOG level (a) AND the setup formed on the 1h / 4h chart
    (b): the sweep extreme sits in a valid 1h / 4h / D / W array of the order's side or took out an hourly swing [our interpretation of "mss_ref_tf in 60 / 240"]."""
    if not _final_target_htf(ctx, sd, o, i, p):
        return False
    real = float(sd.x(o["ext"]))
    cf = getattr(ctx, "conf", None)
    if cf is not None:
        try:
            if set(cf.at(_now(ctx, i), real, sd.sign, _now(ctx, i))) & {"1h", "4h", "D", "W"}:
                return True
        except Exception:
            hit("htf_quality_conf_err")
    return hourly_swing_near(ctx, sd, i, real, 8 * p.tick)


def tgif_week_ref(ctx, hist, tag: str, o: dict, sd):
    """#85: the week extreme the TGIF idea is invalid beyond (side space), the Mon-Thu extreme or the Friday extreme up to the order's sweep bar, whichever is further."""
    wk = D1._this_week(hist, ctx.day)
    if not wk:
        return None
    k = int(o.get("ext_i", ctx.start))
    if tag == "tgif_short":
        ref = max(float(x.high.max()) for x in wk)
        ref = max(ref, float(ctx.h[ctx.start:k + 1].max()))
    else:
        ref = min(float(x.low.min()) for x in wk)
        ref = min(ref, float(ctx.l[ctx.start:k + 1].min()))
    return float(sd.x(ref))


def order_ok(ctx, sd, o: dict, session: str, i: int, p):
    """Per-order filters: #31 trending-week sweep array, #32 / #28 nearest-only targets, #85 TGIF week-high invalidation, #35 PM pool exit, #20 HTF quality, #18 PM measured move."""
    P = getattr(ctx, "dplan", None)
    if P is None:
        return None
    DW = _DW()
    d = ctx.day
    hist = getattr(ctx, "hist", [])
    # #31 N10-mon-wed-extreme-trending-week
    mt = P.info.get("mw_trend")
    if p.mw_extreme_need_array and mt and sd.sign == mt and d.weekday() <= 2:
        if not htf_discount_hit(ctx, sd, o, i, p):
            hit("mw_array_reject")
            return "x_dw_mw_extreme_array"
        hit("mw_array_pass")
    # #20 X15-three-per-week-htf-quality
    if p.htf_quality_only and not htf_quality_ok(ctx, sd, o, i, p):
        hit("htf_quality_reject")
        return "x_dw_htf_quality"
    # #35 N8-consolidation-pm-full-exit-at-pool
    if p.consol_pm_pool_exit and session in DW.LATE and _day_is_consol(ctx, p, P, i):
        ref = [(n, v) for n, v, m0 in pool_levels(ctx, sd, i) if v > o["entry"] + 1e-9 and float(sd.h[min(i, _k(ctx, m0)):i + 1].max()) < v - 1e-12]
        if not ref:
            hit("pm_pool_none")
            return "x_dw_consol_pm_pool"
        n, v = min(ref, key=lambda x: x[1])
        o["levels"], o["level_kinds"] = [v], ["pool"]
        o["t1"], o["t2"], o["final_T"] = v, None, True
        o["scalp"] = o["no_adds"] = True
        o["fracs_fixed"] = (1.0,)
        o.pop("runner", None)
        o.pop("htf_runner", None)
        rp = o.get("rung_plan")
        if rp:
            m0 = next((x for x in rp if x["role"] == "main"), None)
            o["rung_plan"] = [dict(m0, v=v, k="pool")] if m0 is not None else rp
        o["lv_tags"] = "|".join(x for x in (o.get("lv_tags", ""), "consol_pm_pool", "consol_pm_" + n) if x)
        hit("pm_pool_exit")
    # #32 N10-missed-mon-wed-no-chase / #28 N10-thursday-reversal-after-targets-met: the nearest pool only
    mw = P.info.get("missed_week")
    if mw and p.missed_week_mode == "nearest" and sd.sign == mw and single_first(o):
        hit("missed_nearest")
    ta = P.info.get("thu_after")
    if ta and p.thu_targets_met_block and sd.sign == -ta and single_first(o):
        hit("thu_counter_nearest")
    # #85 M14-tgif-invalidation-timing (075 ~01:40:30)
    if p.tgif and p.tgif_week_high_exit and d.weekday() == 4:
        tag = tgif_tag(ctx)
        if tag and sd.sign == (-1 if tag == "tgif_short" else 1):
            ref = tgif_week_ref(ctx, hist, tag, o, sd)
            if ref is not None:
                o["cancel_low"] = max(ref, o["cancel_low"]) if o.get("cancel_low") is not None else ref
                stop = ref - p.tick
                if o["stop"] < stop - 1e-12:
                    if stop >= o["entry"] - 1e-12 or not D2._rescale(o, stop, True):
                        hit("tgif_ref_reject")
                        return "x_dw_tgif_week_high"
                    hit("tgif_ref_stop")
    # #18 T9-pm-faster-measured-move
    if p.pm_mm_target and session == "PM":
        mm = pm_mm_level(ctx, sd, i)
        if mm is not None and add_rung(o, mm, "array", p.tick):
            hit("pm_mm_rung")
    return None


def am_leg(ctx, i: int):
    """The AM (09:30-12:00) leg through the closed bar i: (direction, low, high) with the direction from the order of the extremes (the high after the low = up), None before any AM bar."""
    hl = _range_bars(ctx, i, 570, 720)
    if hl is None:
        return None
    jh = _extreme_idx(ctx, 1, 570, 720, i)
    jl = _extreme_idx(ctx, -1, 570, 720, i)
    return (1 if jh > jl else -1), hl[1], hl[0]


def pm_mm_level(ctx, sd, i: int):
    """#18: for a PM trade in the AM direction, the AM extreme + S (S = the AM leg size) in side space; None for a counter-AM order or without an AM leg."""
    leg = am_leg(ctx, i)
    if leg is None or leg[0] != sd.sign:
        return None
    dr, lo, hi = leg
    s = hi - lo
    return float(sd.x(hi + s)) if dr > 0 else float(sd.x(lo - s))


# --------------------------------------------------------------------------------------------------------------
# size, day params, tags, pools
# --------------------------------------------------------------------------------------------------------------

def size_mult(ctx, p, lvt=None) -> float:
    """#38 E9-may-october (cc10_015 ~00:03:49): the risk multiplier of the low-magnitude months (`low_mag_months`, May-October). August keeps its own E9 row: the smaller multiplier wins."""
    d = ctx.day
    if p.low_mag_mult == 1.0 or d.month not in p.low_mag_months:
        return 1.0
    f = float(p.low_mag_mult)
    if d.month == 8 and p.august_risk != 1.0 and d.day >= p.august_from_day:
        f = 1.0 if p.august_risk <= f else f / p.august_risk
    if f != 1.0:
        if lvt is not None:
            lvt.append("size_low_mag")
        hit("low_mag_size")
    return f


def day_params(p, dw):
    """#126: a choppy week takes the slow ladder (the bulk at T1) and no runner of any kind (the consol_no_runner behaviour applied to the tagged day)."""
    from dataclasses import replace
    if dw.info.get("choppy_week"):
        hit("choppy_no_runner")
        return replace(p, runner_frac=0.0, po3_runner=False, runner_htf=False, htf_range_runner=False, urgency_runner=False, ladder_fracs=p.ladder_fracs_slow)
    return p


def target_pools(ctx, sd, i: int, p) -> list:
    """Target pools (side space, (level, created)): #27 the carried weekly draw, #11 the PM narrative's gap level, #14 the noon-reversal PM draw (the AM range's opposite extreme)."""
    P = getattr(ctx, "dplan", None)
    out = []
    if P is None:
        return out
    cr = P.info.get("carry")
    if cr and cr[0] == sd.sign and p.carry_weekly_draw:
        out.append((float(sd.x(cr[1])), ctx.start))
        hit("carry_target")
    if p.pm_narrative and ctx.t[i] >= 810:
        nv = pm_narrative(ctx, p, getattr(ctx, "hist", []))
        if nv is not None and nv[0] == sd.sign:
            out.append((float(sd.x(nv[1])), ctx.start))
    if p.noon_rev_pm and ctx.t[i] >= 720:
        st = lunch_state(ctx, p, i)
        if st is not None and st["kind"] == "reversal" and sd.sign == -st["am_dir"]:
            hl = _range_bars(ctx, i, 570, 720)
            if hl is not None:
                out.append((float(sd.x(hl[1] if st["am_dir"] > 0 else hl[0])), ctx.start))
                if getattr(ctx, "org_today", False) and getattr(ctx, "org", None):
                    out.append((float(sd.x(ctx.org[-1][0])), ctx.start))
    return out


def want_override(ctx, p, w: int) -> int:
    """#27: the carried weekly draw's side is the bias when the table has none; after the draw traded (carry_neutral_after) the rest of the week is neutral (0)."""
    P = getattr(ctx, "dplan", None)
    if P is None or not p.carry_weekly_draw:
        return w
    if P.info.get("carry_neutral"):
        return 0
    cr = P.info.get("carry")
    if cr and not w:
        return int(cr[0])
    return w


def entry_tags(ctx, p, P, k: int) -> set:
    """Per-trade tags from the bars through the entry bar k (reporting only)."""
    t = set()
    if p.london_ext_consol and consol_overnight(ctx, p, k):
        t.add("consol_overnight")
    if p.lunch_kind_tag and ctx.t[k] >= 720:
        try:
            st = lunch_state(ctx, p, k)
        except Exception:
            st = None
        if st is not None:
            t.add("lunch_" + st["kind"])
    wp = P.info.get("weekly_po3")
    cf = getattr(ctx, "conf", None)
    if wp and cf is not None and k >= ctx.start:
        wb = wp[0]
        hist = getattr(ctx, "hist", [])
        wk = D1._this_week(hist, ctx.day)
        try:
            if wb < 0:
                ref = max([float(x.high.max()) for x in wk] + [float(ctx.h[ctx.start:k + 1].max())])
            else:
                ref = min([float(x.low.min()) for x in wk] + [float(ctx.l[ctx.start:k + 1].min())])
            if _DW()._array_touch(cf, _now(ctx, k), ref, -1 if wb < 0 else 1, ("W",), getattr(cf, "tol", 0.0)):
                t.add("weekly_judas")
        except Exception:
            pass
    return t


def stamp(ctx, trades, p) -> None:
    """Trade columns of this package (reporting only): cl_fail (the failing checklist steps of the trade's session)."""
    if p.checklist == "off" or not trades:
        return
    cl = _cache(ctx).get("cl", {})
    for tr in trades:
        tr.cl_fail = cl.get(tr.session, cl.get("AM" if tr.session in ("LUNCH",) else tr.session, ""))


# --------------------------------------------------------------------------------------------------------------
# #10 the explicit veto order
# --------------------------------------------------------------------------------------------------------------

def session_veto(ctx, p, day: date, session: str, t: int, blocked_fn, news_fn=None) -> str | None:
    """OT-filters-before-bias (cc08_006 ~00:19:14): the FIRST firing no-trade filter of the session, before any bias is read: the calendar block (`blocked`) then `skip_news`. Every veto is
    appended to the run's skips once per (session, reason); `news_fn` None = the engine does not apply skip_news there (the Silver Bullet). The sloppy stand-aside and the side blocks stay where they are (they need the per-bar state). Returns the reason or None."""
    why = None
    if p.day_filter:
        why = blocked_fn(day, session, p, t) or None          # a falsy return (False / "" / None) is no veto
    if why is None and news_fn is not None and p.skip_news and news_fn(day) != "none":
        why = "skip_news"
    if why is not None:
        log_veto(ctx, day, session, why if isinstance(why, str) else "blocked")
    return why


def log_veto(ctx, day: date, session: str, why: str) -> None:
    """One 'veto' skips row per (session, reason) per day (also used for the per-bar sloppy stand-aside, which needs the bar's chop state and so stays in the loop right after the calendar veto)."""
    seen = ctx.__dict__.setdefault("_veto_seen", set())
    if (session, why) not in seen:
        seen.add((session, why))
        sk = getattr(ctx, "skips_ref", None)
        if sk is not None:
            sk.append((day, getattr(ctx, "symbol", ""), "veto", f"{session}:{why}"))
        hit("veto")


# --------------------------------------------------------------------------------------------------------------
# #7 the time-to-move journal
# --------------------------------------------------------------------------------------------------------------

INDEX_SYMBOLS = {"SPY", "QQQ", "DIA", "SPX", "NDX", "ES", "NQ", "YM", "MES", "MNQ", "MYM", "RTY", "M2K", "IWM", "RUT", "RW", "ZB", "ZN", "US500", "NAS100", "US30"}      # (re-exported as strategy.INDEX_SYMBOLS; wider than the spec's eight - owner question)


def journal_bar(pos: dict, sd, i: int, ts, p) -> None:
    """OT-X16-time-to-move-journal: per open bar after the fill the favourable / adverse excursion from the fill (engine price units, side space) and the first bar whose favourable excursion
    reached `fav_pts` ES points. Read-only: no stop or exit logic changes."""
    if "j_entry" not in pos:
        pos["j_entry"] = pos["basis"] / pos["n"]
        pos["mfe"] = pos["mae"] = 0.0
        pos["fav_t"] = None
    e = pos["j_entry"]
    pos["mfe"] = max(pos["mfe"], float(sd.h[i]) - e)
    pos["mae"] = max(pos["mae"], e - float(sd.l[i]))
    if pos["fav_t"] is None and float(sd.h[i]) - e >= p.fav_pts * p.es_pt - 1e-12:
        pos["fav_t"] = ts


def journal_close(pos: dict, tr, p) -> None:
    """Fill the Trade journal fields at the close (_close): minutes fill -> first favourable move, fill -> final exit, the first exit's kind, MFE / MAE in ES points. A position that never
    saw a later bar (the same-bar stop) has no favourable move (None), exit minutes 0 and MFE 0."""
    if not tr.exits:
        return
    t0 = pd.Timestamp(tr.entry_time)
    if pos.get("fav_t") is not None:
        tr.min_to_fav = float((pd.Timestamp(pos["fav_t"]) - t0).total_seconds() / 60.0)
    r = str(tr.exits[0][3])
    tr.first_exit_kind = _exit_kind(r)
    if "j_entry" not in pos:
        return                                           # stopped on the fill bar: no later bar was seen - no exit minutes, no excursions (None, not 0)
    tr.min_to_exit = float((pd.Timestamp(tr.exits[-1][0]) - t0).total_seconds() / 60.0)
    tr.mfe_pts = round(pos.get("mfe", 0.0) / p.es_pt, 4)
    tr.mae_pts = round(-pos.get("mae", 0.0) / p.es_pt, 4)


def _exit_kind(r: str) -> str:
    return "stop" if r.startswith("stop") or r == "be" else ("target" if (r.startswith("t") and r[1:].isdigit()) or r.endswith("target") else "other")


def journal_extras(ctx, trades, p) -> None:
    """OT-X16-time-to-move-journal for the Silver Bullet / Ma Deuce rows (their engines have no shared close hook): after the trade closed, replay the bars strictly after the fill bar through the
    last exit bar (never a bar later than the exit) with the same definitions as journal_bar / journal_close. Read-only."""
    if not p.journal_timing:
        return
    idx = ctx.idx
    for tr in trades:
        if not tr.exits or getattr(tr, "min_to_exit", None) is not None or getattr(tr, "first_exit_kind", ""):
            continue
        t0, tx = pd.Timestamp(tr.entry_time), pd.Timestamp(tr.exits[-1][0])
        sel = [k for k in range(ctx.start, len(idx)) if t0 < idx[k] <= tx]
        tr.first_exit_kind = _exit_kind(str(tr.exits[0][3]))
        if not sel:
            continue
        e = float(tr.entry)
        sgn = 1.0 if tr.side == "long" else -1.0
        mfe = mae = 0.0
        fav_t = None
        for k in sel:
            up = (float(ctx.h[k]) - e) if sgn > 0 else (e - float(ctx.l[k]))
            dn = (e - float(ctx.l[k])) if sgn > 0 else (float(ctx.h[k]) - e)
            mfe, mae = max(mfe, up), max(mae, dn)
            if fav_t is None and up >= p.fav_pts * p.es_pt - 1e-12:
                fav_t = idx[k]
        if fav_t is not None:
            tr.min_to_fav = float((pd.Timestamp(fav_t) - t0).total_seconds() / 60.0)
        tr.min_to_exit = float((tx - t0).total_seconds() / 60.0)
        tr.mfe_pts = round(mfe / p.es_pt, 4)
        tr.mae_pts = round(-mae / p.es_pt, 4)
        hit("journal_extras")


def journal_day_tags(day: date) -> set:
    """pre_fomc (the next trading day is an FOMC day) and news_day (jobs / cpi / ppi / fomc today)."""
    out = set()
    try:
        if "fomc" in events(CAL.next_trading_day(day)):
            out.add("pre_fomc")
    except Exception:
        pass
    if events(day) & {"jobs", "cpi", "ppi", "fomc"}:
        out.add("news_day")
    return out


def journal_report(t: pd.DataFrame) -> dict:
    """backtest.report: by_pre_fomc and the medians of min_to_fav / min_to_exit split by winner / loser."""
    out = {}
    if "min_to_fav" not in t or "min_to_exit" not in t or not (t.min_to_fav.notna().any() or t.min_to_exit.notna().any()):
        return out
    win = t.net > 0
    out["time_to_move"] = {k: {"min_to_fav": None if not g.min_to_fav.notna().any() else round(float(g.min_to_fav.median()), 2),
                               "min_to_exit": None if not g.min_to_exit.notna().any() else round(float(g.min_to_exit.median()), 2), "n": int(len(g))}
                           for k, g in (("winners", t[win]), ("losers", t[~win])) if len(g)}
    if "day_tags" in t:
        pf = t.day_tags.fillna("").astype(str).str.contains("pre_fomc")
        out["by_pre_fomc"] = {"pre_fomc": _stats_small(t[pf]), "other": _stats_small(t[~pf])}
    return out


def _stats_small(g: pd.DataFrame) -> dict:
    if not len(g):
        return {"trades": 0}
    return {"trades": int(len(g)), "win_rate": round(float((g.net > 0).mean()), 3), "avg_R": round(float(g.R.mean()), 3), "net": round(float(g.net.sum()), 2)}


# --------------------------------------------------------------------------------------------------------------
# studies (report only; no engine effect): #4 macro runs, #18 PM profile, #33 session template, #49 week states, #175 Wednesday news reversal
# --------------------------------------------------------------------------------------------------------------

def _mins(fr) -> np.ndarray:
    return (fr.index.hour * 60 + fr.index.minute).values.astype(int)


def _leg_from_window(fr, m: np.ndarray, a: int, b: int, end: int = 960):
    """The best leg that STARTS inside the window [a, b) (start-only test): up from the window's lowest low to the highest high after it up to `end` (the caller passes the window end plus
    `leg_extra_min`), down from the window's highest high to the lowest low after it. Returns the larger travel in price units, 0 without bars."""
    w = np.nonzero((m >= a) & (m < b))[0]
    if not len(w):
        return 0.0
    rest = np.nonzero((m >= a) & (m < end))[0]
    hi, lo = fr.high.values, fr.low.values
    j = int(w[int(np.argmin(lo[w]))])
    up = float(hi[j:rest[-1] + 1].max() - lo[j])
    j2 = int(w[int(np.argmax(hi[w]))])
    dn = float(hi[j2] - lo[j2:rest[-1] + 1].min())
    return max(up, dn, 0.0)


MACRO_WINDOWS = ((890, 910), (915, 945), (945, 960))        # 14:50-15:10, 15:15-15:45, 15:45-16:00


def macro_runs_study(days: list, macro_run_pts: float = 5.0, leg_extra_min: int = 0) -> dict:
    """#4 T7-1500-at-least-one (022 ~03:16:44): per day and per 15:00-16:00 macro window (14:50-15:10, 15:15-15:45, 15:45-16:00) a "run" = a leg that STARTS in the window and travels at least
    `macro_run_pts` points before `leg_extra_min` minutes after the window ended (0 = inside the window) [our interpretation of the start-only test]. Rows: date, windows with a run, htf_done at 15:00 (the day's range before 15:00 already >= the mean range of the 5 days
    before it [our interpretation of "the HTF target already hit"]). The summary: the share of days with at least one / two runs, split by htf_done. No engine change."""
    rows = []
    rngs = [float(x.high.max() - x.low.min()) for x in days]
    for k, fr in enumerate(days):
        m = _mins(fr)
        runs = [int(_leg_from_window(fr, m, a, b, min(960, b + leg_extra_min)) >= macro_run_pts) for a, b in MACRO_WINDOWS]
        pre = fr[m < 900]
        prior = rngs[max(0, k - 5):k]
        done = bool(len(pre) and prior and float(pre.high.max() - pre.low.min()) >= float(np.mean(prior)))
        rows.append(dict(date=fr.index[0].date(), runs=int(sum(runs)), windows=tuple(runs), htf_done=done))
    out = dict(rows=rows)
    n = len(rows)
    for key, sel in (("all", rows), ("htf_done", [r for r in rows if r["htf_done"]]), ("htf_open", [r for r in rows if not r["htf_done"]])):
        out[key] = dict(days=len(sel), at_least_one=round(sum(r["runs"] >= 1 for r in sel) / len(sel), 3) if sel else None,
                        at_least_two=round(sum(r["runs"] >= 2 for r in sel) / len(sel), 3) if sel else None,
                        mean_runs=round(float(np.mean([r["runs"] for r in sel])), 3) if sel else None)
    return out


def _leg(fr, m: np.ndarray, a: int, b: int):
    """(size, minutes between the extremes, direction) of the bars with minute in [a, b); the direction is +1 when the high comes after the low. None without bars."""
    w = np.nonzero((m >= a) & (m < b))[0]
    if not len(w):
        return None
    jh = int(w[int(np.argmax(fr.high.values[w]))])
    jl = int(w[int(np.argmin(fr.low.values[w]))])
    return float(fr.high.values[jh] - fr.low.values[jl]), abs(int(m[jh]) - int(m[jl])), (1 if jh > jl else -1)


def pm_profile_study(days: list) -> dict:
    """#18 T9-pm-faster-measured-move (067 ~39:22; cc10_012 ~1:52; cc10_007 ~8:46): per day the AM leg (09:30-12:00, extreme to extreme) size S and duration, the PM leg (14:00-16:00) size
    and duration, and a profile label (1 reversal: the PM leg runs against the AM and is >= 0.7 S; 3 measured: with the AM, >= 0.7 S, a quiet 12:00-13:00 (< 0.5 S); 2 trending: with the AM,
    >= 0.7 S after an active lunch; 4 consolidation: the PM range < 0.3 S; 0 other) [our interpretation]. Reports the ratio PM duration / AM duration. No engine effect."""
    rows = []
    for fr in days:
        m = _mins(fr)
        am, pm, lu = _leg(fr, m, 570, 720), _leg(fr, m, 840, 960), _leg(fr, m, 720, 780)
        if am is None or pm is None or am[0] <= 0:
            continue
        s, s_pm = am[0], pm[0]
        lunch = lu[0] if lu is not None else 0.0
        if s_pm < 0.3 * s:
            lab = 4
        elif s_pm >= 0.7 * s and pm[2] != am[2]:
            lab = 1
        elif s_pm >= 0.7 * s and lunch < 0.5 * s:
            lab = 3
        elif s_pm >= 0.7 * s:
            lab = 2
        else:
            lab = 0
        rows.append(dict(date=fr.index[0].date(), am_size=s, am_min=am[1], pm_size=s_pm, pm_min=pm[1], am_dir=am[2], pm_dir=pm[2], label=lab,
                         ratio=(pm[1] / am[1]) if am[1] else None))
    summ = {"days": len(rows)}
    for lab in range(5):
        sel = [r for r in rows if r["label"] == lab]
        summ[f"label_{lab}"] = len(sel)
    r3 = [r["ratio"] for r in rows if r["label"] == 3 and r["ratio"] is not None]
    summ["ratio_label_3_median"] = round(float(np.median(r3)), 3) if r3 else None
    return dict(rows=rows, summary=summ)


SESSION_BINS = ((0, 120, "asia"), (120, 300, "london"), (300, 420, "london_lunch"), (420, 600, "ny_0700_1000"), (600, 720, "london_close"), (720, 900, "pm"), (900, 960, "last_hour"))


def _bin(minute: int) -> str:
    for a, b, n in SESSION_BINS:
        if a <= minute < b:
            return n
    return "other"


def session_template_study(days: list) -> dict:
    """#33 T13-fx-daily-session-template (065 ~02:10:04; cc09_006 ~00:10:28 ...): on all-hours bars (00:00-16:00 NY) per day: london_share = the London (02:00-05:00) range / the day's range, the
    session bin of the day's high (HOD) and low (LOD) (asia / london / london_lunch / ny_0700_1000 / london_close / pm / last_hour), the daily direction and whether it was a trend day
    (|close - open| >= 0.6 of the range [our interpretation]). The summary counts the HOD / LOD bins by direction and by trend_day. No engine change."""
    rows = []
    for fr in days:
        m = _mins(fr)
        sel = (m >= 0) & (m < 960)
        f = fr[sel]
        mm = m[sel]
        if len(f) < 10:
            continue
        rng = float(f.high.max() - f.low.min())
        if rng <= 0:
            continue
        lon = f[(mm >= 120) & (mm < 300)]
        share = float(lon.high.max() - lon.low.min()) / rng if len(lon) else None
        hod = _bin(int(mm[int(np.argmax(f.high.values))]))
        lod = _bin(int(mm[int(np.argmin(f.low.values))]))
        o, c = float(f.open.iloc[0]), float(f.close.iloc[-1])
        rows.append(dict(date=fr.index[0].date(), london_share=share, hod_bin=hod, lod_bin=lod, direction=int(np.sign(c - o)), trend_day=bool(abs(c - o) >= 0.6 * rng)))
    summ = {"days": len(rows)}
    shares = [r["london_share"] for r in rows if r["london_share"] is not None]
    summ["london_share_median"] = round(float(np.median(shares)), 3) if shares else None
    for nm, sel in (("up", [r for r in rows if r["direction"] > 0]), ("down", [r for r in rows if r["direction"] < 0]),
                    ("trend", [r for r in rows if r["trend_day"]]), ("other", [r for r in rows if not r["trend_day"]])):
        summ[nm] = dict(days=len(sel), hod=dict(Counter(r["hod_bin"] for r in sel)), lod=dict(Counter(r["lod_bin"] for r in sel)))
    return dict(rows=rows, summary=summ)


def week_state_labels(days: list) -> dict:
    """#49 T14-weekly-template (cc01_002 ~24:06): per Monday-Friday week the state of each weekday - "consol" (range < 0.6 x ADR5), "expansion" (range >= ADR5 and the close in the outer
    quarter of the range), "reversal" (the day took the prior day's extreme and closed beyond its 50% the other way) [our interpretation] - the weekday of the weekly high and low, and whether the
    template Mon expansion -> Tue reversal -> a consolidation Wed / Thu -> a Thu / Fri reversal or retrace occurred (counted). `days` = daily regular-session frames, oldest first."""
    rows = []
    byw = {}
    for k, fr in enumerate(days):
        byw.setdefault(fr.index[0].date().isocalendar()[:2], []).append(k)
    for key in sorted(byw):
        ks = byw[key]
        labs = [None] * 5
        for k in ks:
            fr = days[k]
            wd = fr.index[0].date().weekday()
            if wd > 4 or k < 5:
                continue
            adr = float(np.mean([float(x.high.max() - x.low.min()) for x in days[k - 5:k]]))
            rg = float(fr.high.max() - fr.low.min())
            o, h, l, c = float(fr.open.iloc[0]), float(fr.high.max()), float(fr.low.min()), float(fr.close.iloc[-1])
            prev = days[k - 1]
            ph, pl = float(prev.high.max()), float(prev.low.min())
            mid = (ph + pl) / 2.0
            if (h > ph and c < mid) or (l < pl and c > mid):
                labs[wd] = "reversal"
            elif rg < 0.6 * adr:
                labs[wd] = "consol"
            elif rg >= adr and (c >= h - 0.25 * rg or c <= l + 0.25 * rg):
                labs[wd] = "expansion"
            else:
                labs[wd] = "other"
        wk = [days[k] for k in ks if days[k].index[0].date().weekday() <= 4]
        if not wk:
            continue
        hi_d = max(wk, key=lambda x: float(x.high.max())).index[0].date().weekday()
        lo_d = min(wk, key=lambda x: float(x.low.min())).index[0].date().weekday()
        late = labs[3] == "reversal" or labs[4] == "reversal" or (labs[3] in ("other", "expansion") and labs[4] in ("other", None))
        tmpl_loose = bool(labs[0] == "expansion" and labs[1] == "reversal" and ("consol" in (labs[2], labs[3])) and late)
        # the strict template also needs the "expansion" step BETWEEN the Tuesday reversal and the midweek consolidation (Wed expansion -> Thu consolidation -> Fri reversal / retrace). A Monday
        # reversal cannot follow a Monday expansion, so the reversal day is Tuesday [our interpretation]
        tmpl = bool(labs[0] == "expansion" and labs[1] == "reversal" and labs[2] == "expansion" and labs[3] == "consol" and (labs[4] in ("reversal", "other")))
        rows.append(dict(week=key, labels=tuple(labs), high_day=hi_d, low_day=lo_d, template=tmpl, template_loose=tmpl_loose))
    n = len(rows)
    return dict(rows=rows, summary=dict(weeks=n, template=sum(r["template"] for r in rows), template_loose=sum(r["template_loose"] for r in rows), template_share=round(sum(r["template"] for r in rows) / n, 3) if n else None,
                                        mon_expansion=sum(r["labels"][0] == "expansion" for r in rows),
                                        low_tue=sum(r["low_day"] == 1 for r in rows), high_tue=sum(r["high_day"] == 1 for r in rows)))


def midweek_turn_by_month(days: list) -> dict:
    """#28 N10-thursday-reversal-after-targets-met (cc07_007 ~00:27:48 / 061): per month, the weeks whose Monday + Tuesday range exceeded ADR5 (the five sessions before the week) and whose
    weekly extreme (high or low) was then set on Wednesday or Thursday - the "turn" - against all such big-start weeks. `days` = daily regular-session frames, oldest first. Report only."""
    byw = {}
    for k, fr in enumerate(days):
        byw.setdefault(fr.index[0].date().isocalendar()[:2], []).append(k)
    mon = {}
    for key in sorted(byw):
        ks = [k for k in byw[key] if days[k].index[0].date().weekday() <= 4]
        if len(ks) < 4 or ks[0] < 5:
            continue
        wk = [days[k] for k in ks]
        wds = [x.index[0].date().weekday() for x in wk]
        if wds[0] != 0 or wds[1] != 1:
            continue
        adr = float(np.mean([float(x.high.max() - x.low.min()) for x in days[ks[0] - 5:ks[0]]]))
        rng = max(float(wk[0].high.max()), float(wk[1].high.max())) - min(float(wk[0].low.min()), float(wk[1].low.min()))
        if adr <= 0 or rng <= adr:
            continue
        hi_d = wds[int(np.argmax([float(x.high.max()) for x in wk]))]
        lo_d = wds[int(np.argmin([float(x.low.min()) for x in wk]))]
        ym = f"{wk[0].index[0].year}-{wk[0].index[0].month:02d}"
        r = mon.setdefault(ym, dict(big_start=0, turn=0))
        r["big_start"] += 1
        r["turn"] += int(hi_d in (2, 3) or lo_d in (2, 3))
    return dict(by_month=mon, summary=dict(big_start=sum(v["big_start"] for v in mon.values()), turn=sum(v["turn"] for v in mon.values())))


def wed_news_reversal(weeks: list, tol_frac: float = 0.15) -> dict:
    """#175 new-wednesday-news-weekly-reversal (cc07_003 ~00:36:11): `weeks` = a list of Monday-Friday lists of daily regular-session frames, oldest first. For every week whose Wednesday has a
    high / medium impact release (daycontext.news_class) and ran below the OLD weekly low (the lowest low of the four weeks before it) into an alive bullish daily FVG, then reclaimed it (the
    Wednesday or Thursday close back above), the 1.27 / 1.68 extension of the swing from the old low to Tuesday's high, projected DOWN from that high, is measured against the realised week low:
    hit = the week low within `tol_frac` x the swing of the projection. The bearish mirror is reported with `side` -1. Report only; no engine effect."""
    from . import daycontext as DW
    rows = []
    flat = [x for w in weeks for x in w]
    for wi, w in enumerate(weeks):
        if wi < 4 or len(w) < 4:
            continue
        old = weeks[wi - 4:wi]
        mon, tue, wed, thu = w[0], w[1], w[2], w[3]
        wd = wed.index[0].date()
        if wd.weekday() != 2 or DW.news_class(wd) not in ("high", "medium"):
            continue
        prior = [x for ww in old for x in ww]
        for side in (1, -1):
            if side > 0:
                oldx = min(float(x.low.min()) for x in prior)
                ran = float(wed.low.min()) < oldx
                recl = float(wed.close.iloc[-1]) > oldx or (float(thu.close.iloc[-1]) > oldx)
                ext1 = float(tue.high.max())
                sw = ext1 - oldx
                p127, p168 = ext1 - 1.27 * sw, ext1 - 1.68 * sw
                wk_ext = min(float(x.low.min()) for x in w)
                zs = D1._alive_zones([x for x in flat if x.index[0] < wed.index[0]], "bull")
                in_arr = any(float(wed.low.min()) <= z.top for z in zs)
            else:
                oldx = max(float(x.high.max()) for x in prior)
                ran = float(wed.high.max()) > oldx
                recl = float(wed.close.iloc[-1]) < oldx or (float(thu.close.iloc[-1]) < oldx)
                ext1 = float(tue.low.min())
                sw = oldx - ext1
                p127, p168 = ext1 + 1.27 * sw, ext1 + 1.68 * sw
                wk_ext = max(float(x.high.max()) for x in w)
                zs = D1._alive_zones([x for x in flat if x.index[0] < wed.index[0]], "bear")
                in_arr = any(float(wed.high.max()) >= z.bottom for z in zs)
            if not (ran and recl) or sw <= 0:
                continue
            tol = tol_frac * sw
            rows.append(dict(week=wd, side=side, old_extreme=oldx, swing=sw, p127=p127, p168=p168, week_extreme=wk_ext, in_array=in_arr,
                             hit127=abs(wk_ext - p127) <= tol, hit168=abs(wk_ext - p168) <= tol))
    n = len(rows)
    return dict(rows=rows, summary=dict(cases=n, hit127=sum(r["hit127"] for r in rows), hit168=sum(r["hit168"] for r in rows), in_array=sum(r["in_array"] for r in rows)))


# --------------------------------------------------------------------------------------------------------------
# TGIF trending-week size (#90), the inside-BISI reconciliation (#93)
# --------------------------------------------------------------------------------------------------------------

def tgif_adr_ok(hist, day: date, p) -> bool:
    """#90 M14-tgif-am-timing: the Mon-Thu range of the TGIF week is above `tgif_min_adr` x ADR5 (the five sessions before the week). No ADR5 = not testable = True."""
    S = _S()
    mon = day - timedelta(days=day.weekday())
    wk = [x for x in hist if x.index[0].date() >= mon]
    before = [x for x in hist if x.index[0].date() < mon]
    a5 = S.adr5(before[-5:])
    if not wk or not a5:
        return True
    return bool(max(float(x.high.max()) for x in wk) - min(float(x.low.min()) for x in wk) > p.tgif_min_adr * a5)


def _inside_zones(hist):
    """EVERY daily FVG (zone, yesterday high, yesterday low) yesterday's whole range sat inside (same test as strategy._inside_daily_fvg, which returns only a flag), [] if none."""
    from . import levels as L
    S = _S()
    if len(hist) < 4:
        return []
    o, h, l, c = S._daily(hist)
    k = len(h) - 1
    out = []
    for z in L.fvgs(h[:k], l[:k]):
        after = c[z.i + 1:k]
        if z.kind == "bull" and len(after) and after.min() < z.bottom:
            continue
        if z.kind == "bear" and len(after) and after.max() > z.top:
            continue
        if z.bottom <= l[k] and h[k] <= z.top:
            out.append((z, float(h[k]), float(l[k])))
    return out


def bisi_two_sided(hist, open_px, p) -> bool:
    """#93 B17-M15-madeuce-inside-bisi: B17's inside-BISI no-trade applies only when BOTH sides are arguable - yesterday's range already traded through the FVG's CE (below it for a BISI,
    above for a SIBI) and today opens within `bisi_ce_band` x the gap's height of the CE. Without today's open the old rule stands (True). With several qualifying zones any two-sided one counts."""
    rs = _inside_zones(hist)
    if not rs or open_px is None:
        return True
    for z, yh, yl in rs:
        ce = (z.top + z.bottom) / 2.0
        redeliv = (yl < ce) if z.kind == "bull" else (yh > ce)
        near = abs(float(open_px) - ce) <= p.bisi_ce_band * (z.top - z.bottom)
        if redeliv and near:
            return True
    return False


def md_inside_exempt(hist, open_px, p) -> bool:
    """#93: Ma Deuce is allowed inside the range when price opens in the premium half of a BISI (the discount half of a SIBI) whose range was not yet re-delivered (yesterday never traded
    through the CE). In that state bisi_two_sided() is False, so the sloppy "inside_bisi" stand-aside does not fire at all (the whole engine, Ma Deuce included, trades): the exemption is
    therefore implicit; this predicate only names the state (used by the test and the debug counter)."""
    for z, yh, yl in _inside_zones(hist):
        ce = (z.top + z.bottom) / 2.0
        if open_px is None:
            continue
        if z.kind == "bull" and float(open_px) > ce and yl >= ce - 1e-12:
            return True
        if z.kind != "bull" and float(open_px) < ce and yh <= ce + 1e-12:
            return True
    return False
