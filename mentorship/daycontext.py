"""Package day_week_context (rule_coverage.md section 3 "day_week_context", 49 items; build_log.md).

Weekly profiles, day templates, neutral / consolidation days, inside days, TGIF and holidays. Everything here is
either a pure function of the calendar, of COMPLETED daily / weekly candles (`hist`, `ctx.eth`), or of the bars of
today that have closed (index <= the caller's bar i). Nothing reads a later bar: every value that depends on a
window (the overnight range at 09:30, the 10:00 opening-range tell, the London range, a macro window, the
opening-range size) is evaluated from the bars of that window only, and only by callers whose bar index lies
past it. Thresholds the sources never give are marked [our interpretation] and are Params.

Layout
  plan(ctx, hist, p, ...)      DayPlan for the day: static session blocks / floors / side blocks / scalp flags /
                               tags, computed from the calendar, the completed candles and the week state
  gate(ctx, p, session, i, t)  a reason when `session` may not arm an order at the closed bar i (dynamic rules)
  side_ok(ctx, p, sign, session, i)  a reason when the side may not be traded (outside day, ORG tell, ...)
  order_ok(ctx, sd, o, session, i, p)  per-order filters (tue_off_monday, tgif_week_sweep, tgif array)
  scalp_now / day_risk / flat_for / day_exit   the engines' hooks (scalp exits, risk multipliers, early-close
                               flat, consolidation-day exit)
  stamp(ctx, trades, p)        the day's tags and the X16 journal columns on every trade
  target_pools / sell_pools / expansion_levels   extra pools and targets (pool_mon_wed, expansion_targets)
  tgif_context                 M14 / M14.1 Friday context (also used by strategy.day_context)
  day_ranges / weekly_extremes / week_summary   X16a / X16c / T14 reporting helpers (study_week.py)
"""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd

from claude_hf.daytypes import events
from . import calendar as CAL
from . import levels as L

MORNING = frozenset({"AM", "PRE7", "PRE8", "PRE9", "NEWS", "LON"})       # the morning windows (not lunch, not PM)
LATE = frozenset({"LUNCH", "PM"})                                       # "the PM": lunch carries the AM draw to it
NY = frozenset({"AM", "PRE7", "PRE8", "PRE9", "NEWS", "LUNCH", "PM"})   # everything but the London window
NY_AM = frozenset({"AM", "PRE9", "NEWS"})                               # the NY morning session proper (09:30 family; no London, no pre-open)
NY_MORNING = NY_AM | {"PRE7", "PRE8"}                                   # + the pre-open windows (07:00 / 08:00 Ma Deuce)
AM_SACRIFICE = NY_MORNING | {"LUNCH"}                                   # N8.4: the NY AM is given up until 13:30 (London is not the AM)
HIGH_NEWS = {"cpi", "jobs"}                                              # N8.2 08:30 impact classes
MEDIUM_NEWS = {"ppi", "pce", "retail_sales", "gdp"}
SEASONAL_DOW20 = ("bear", "bull", "cons", "bull", "bear", "cons", "bull", "cons", "split", "bull", "bull", "bull")
                                                                         # B23 (cc10_015 ~5:04): Jan .. Dec


# --------------------------------------------------------------------------------------------------------------
# small helpers on completed candles
# --------------------------------------------------------------------------------------------------------------

def _hl(fr) -> tuple:
    return float(fr.high.max()), float(fr.low.min())


def _ohlc(hist) -> tuple:
    o = np.array([float(x.open.iloc[0]) for x in hist]); c = np.array([float(x.close.iloc[-1]) for x in hist])
    h = np.array([float(x.high.max()) for x in hist]); l = np.array([float(x.low.min()) for x in hist])
    return o, h, l, c


def _dates(hist) -> list:
    return [x.index[0].date() for x in hist]


def day_range(fr, eth: dict | None, p) -> float:
    """One session's range on the p.adr_basis ("rth" = the 09:30-16:00 frame; "eth" = the full session from the
    evening reopen when ctx.eth has it, else RTH)."""
    d = fr.index[0].date()
    if p.adr_basis == "eth" and eth and d in eth and p.n8_use_overnight:      # (caption-gap N8-overnight-not-precursor cc10_009 ~00:00:55: n8_use_overnight False = RTH ranges for the day classifications)
        return float(eth[d][1] - eth[d][2])
    return float(fr.high.max() - fr.low.min())


def adr(hist, p, eth: dict | None = None, n: int = 5, offset: int = 0) -> float | None:
    """Average daily range of the n sessions ending `offset` sessions before the last completed one; None with
    fewer than n (X16a / N8.5 `adr_basis`)."""
    seg = hist[:len(hist) - offset][-n:] if offset else hist[-n:]
    if len(seg) < n:
        return None
    return float(np.mean([day_range(x, eth, p) for x in seg]))


def _week_key(d: date) -> tuple:
    return d.isocalendar()[:2]


def _weeks(hist) -> list:
    """Completed sessions grouped by Monday-Friday week, oldest first: [(key, [frames])]."""
    out, cur, key = [], [], None
    for fr in hist:
        k = _week_key(fr.index[0].date())
        if k != key and cur:
            out.append((key, cur))
            cur = []
        key = k
        cur.append(fr)
    if cur:
        out.append((key, cur))
    return out


def _week_hl(frames, eth: dict | None, use_eth: bool) -> tuple:
    hs, ls = [], []
    for fr in frames:
        d = fr.index[0].date()
        if use_eth and eth and d in eth:
            hs.append(eth[d][1]); ls.append(eth[d][2])
        else:
            hs.append(float(fr.high.max())); ls.append(float(fr.low.min()))
    return max(hs), min(ls)


def strong_day(fr, a: float | None, mult: float, frac: float) -> int:
    """+1 / -1: an up (down) close whose range is >= mult x ADR5 and whose close sits in the top (bottom) `frac` of
    the range; 0 otherwise (cc09_008 ~41:53 "strong Thursday" [our interpretation])."""
    o, c = float(fr.open.iloc[0]), float(fr.close.iloc[-1])
    h, l = _hl(fr)
    if a is None or h - l < mult * a or h <= l:
        return 0
    if c > o and c >= h - frac * (h - l):
        return 1
    if c < o and c <= l + frac * (h - l):
        return -1
    return 0


# --------------------------------------------------------------------------------------------------------------
# B11 / B11b / B11c: candle-pattern day context
# --------------------------------------------------------------------------------------------------------------

def candle_patterns(hist, p, eth: dict | None = None) -> dict:
    """Patterns of the last completed daily / weekly candles (completed days only):
      inside_day     yesterday inside the day before (012 ~16:17: a large range comes next)
      outside        None / "up" / "down": yesterday outside the day before, by its close (081 ~1:31)
      out_hi / out_lo  the outside day's extremes
      nr3 / nr7      yesterday has the smallest range of the last 3 / 7 sessions (cc06_007 ~21:24); the ranges
                     follow p.adr_basis (full sessions with "eth" when `eth` has them)
      inside_body    yesterday's body inside the day before's body (the 'inside bar' by bodies; the regular-session
                     open / close: the daily candle's body is the cash session's)
    (the inside WEEK needs the day: week_patterns)
    """
    out = dict(inside_day=False, outside=None, nr3=False, nr7=False, inside_body=False, inside_week=False)
    if len(hist) >= 2:
        o, h, l, c = _ohlc(hist[-2:])
        out["inside_day"] = bool(h[1] < h[0] and l[1] > l[0])
        if h[1] > h[0] and l[1] < l[0]:
            out["outside"] = "down" if c[1] < o[1] else "up"
            out["out_hi"], out["out_lo"] = float(h[1]), float(l[1])
        b0, b1 = (min(o[0], c[0]), max(o[0], c[0])), (min(o[1], c[1]), max(o[1], c[1]))
        out["inside_body"] = bool(b1[0] > b0[0] and b1[1] < b0[1])
    for n in (3, 7):
        if len(hist) >= n:
            r = [day_range(x, eth, p) for x in hist[-n:]]
            out[f"nr{n}"] = bool(r[-1] <= min(r) and r[-1] < max(r))
    return out


def week_patterns(hist, day: date, p, eth: dict | None = None) -> dict:
    """B11 / B11c inside week (103 ~12:53): the last COMPLETED week (before the week of `day`) sits inside the week
    before it; then "expansion within 2 candles, else scalp only": the days of this week already completed
    (k of them) are checked for a close outside the inside week's range. Returns dict(inside=bool, hi, lo, k,
    expanded=bool, waiting=bool, scalp=bool). Completed sessions only."""
    out = dict(inside=False, k=0, expanded=False, waiting=False, scalp=False)
    wk = _weeks([x for x in hist if x.index[0].date() < day])
    this = _week_key(day)
    cur = [f for key, f in wk if key == this]
    prior = [(k_, f) for k_, f in wk if k_ != this]
    if len(prior) < 2:
        return out
    use = p.adr_basis == "eth"
    h1, l1 = _week_hl(prior[-1][1], eth, use)
    h0, l0 = _week_hl(prior[-2][1], eth, use)
    if not (h1 < h0 and l1 > l0):
        return out
    out.update(inside=True, hi=h1, lo=l1)
    days_ = cur[0] if cur else []
    out["k"] = len(days_)
    out["expanded"] = any(float(fr.close.iloc[-1]) > h1 or float(fr.close.iloc[-1]) < l1 for fr in days_)
    n = p.b11_inside_week_days
    out["waiting"] = (not out["expanded"]) and len(days_) < n
    out["scalp"] = (not out["expanded"]) and len(days_) >= n
    return out


# --------------------------------------------------------------------------------------------------------------
# the plan
# --------------------------------------------------------------------------------------------------------------

class DayPlan:
    """One day's context. `blocks` = [(sessions | None, reason)] (None = every session); `floors` = [(sessions,
    minute, reason)] (no arming before the minute); `sides` = {reason: (blocked signs,)}; `scalp` = {reason:
    sessions | None}; `expansion` = reasons the day is expected to expand (the consolidation stand-aside is
    waived with b11_inside_expansion / nr_expansion = "no_chop_skip"); `info` = values for the trade columns."""

    def __init__(self, day):
        self.day = day
        self.tags: set = set()
        self.blocks: list = []
        self.floors: list = []
        self.sides: dict = {}
        self.scalp: dict = {}
        self.expansion: set = set()
        self.info: dict = {}

    def block(self, sessions, reason: str) -> None:
        self.blocks.append((None if sessions is None else frozenset(sessions), reason))

    def floor(self, sessions, minute: int, reason: str) -> None:
        self.floors.append((frozenset(sessions), int(minute), reason))

    def side_block(self, reason: str, signs: tuple) -> None:
        self.sides[reason] = tuple(signs)

    def set_scalp(self, reason: str, sessions=None) -> None:
        self.scalp[reason] = None if sessions is None else frozenset(sessions)

    def static_reason(self, session: str, t: int) -> str | None:
        for ss, why in self.blocks:
            if ss is None or session in ss:
                return why
        for ss, m, why in self.floors:
            if session in ss and t < m:
                return why
        return None


def _ctx_cache(ctx) -> dict:
    c = ctx.__dict__.get("_dw")
    if c is None:
        c = ctx.__dict__["_dw"] = {}
    return c


def plan(ctx, hist, p, week: dict | None = None, eve: tuple | None = None, dt: set | None = None) -> DayPlan:
    """Build the day's DayPlan. `hist` = prior regular sessions, `week` = the week's trade state (backtest.week_state:
    n trades so far, final_hits ...), `eve` = (open, high, low, close) of the evening session before today
    (18:00-24:00; futures only), `dt` = strategy.day_context's tags (inside_day, big_prev, ...)."""
    d = ctx.day
    P = DayPlan(d)
    ctx.dplan = P
    ctx.week = week or {}
    ctx.eve = eve
    eth = getattr(ctx, "eth", None)
    P.tags |= _calendar_tags(d, p, ctx)
    P.info["week_idx"] = CAL.week_day_index(d)
    a5 = adr(hist, p, eth, 5)
    P.info["adr5_prev"] = a5
    _calendar_rules(P, d, p, hist, ctx, a5)
    _candle_rules(P, d, p, hist, eth, a5)
    _week_rules(P, ctx, d, p, hist, eth, a5, week or {})
    _friday_rules(P, ctx, d, p, hist, eth, a5)
    _monday_rules(P, ctx, d, p, hist, eth, a5)
    _consol_rules(P, ctx, d, p, hist, eth, a5)
    _regime_rules(P, d, p, hist, eth)
    _misc_rules(P, ctx, d, p, hist, eth, a5)
    from . import dwc1 as _D1
    _D1.plan_rules(P, ctx, d, p, hist, eth, a5, dt)          # caption-gap pass day_week_context#1/3
    from . import dwc2 as _D2
    _D2.plan_rules(P, ctx, d, p, hist, eth, a5, dt)          # caption-gap pass day_week_context#2/3
    return P


# --- calendar tags and rules ---------------------------------------------------------------------------------

def _calendar_tags(d: date, p, ctx=None) -> set:
    t = set()
    if CAL.holiday_eve(d, p.holiday_eve_cases, p.holiday_eve_bank):          # (caption-gap DS2-holiday-eve-friday-before-tue-holiday: holiday_eve_cases "ab" adds the Friday before a Mon / Tue holiday)
        t.add("holiday_eve")
    if CAL.is_post_holiday(d):
        t.add("post_holiday")
    if CAL.holiday_in_week(d):
        t.add("holiday_week")
    if CAL.after_monday_holiday(d) and d.weekday() == 2:
        t.add("wed_reversal")                         # N7.2 (cc09_008 ~55:24): Wednesday after a Monday holiday
    if CAL.is_week_start(d) and d.weekday() != 0:
        t.add("monday_like")
    if CAL.first_trading_day_of_year(d):
        t.add("first_day")
    if CAL.last_trading_day_of_year(d):
        t.add("last_day")
    if d.month == 8:
        t.add("august")
    rw = p.roll_week_src in ("calendar", "either") and CAL.roll_week(d)
    ra = getattr(ctx, "roll_at", None)
    if p.roll_week_src in ("data", "either") and ra is not None and ra <= ctx.start:
        rw = True                                     # N7.5 from the data's roll flag / contract change, known by the day's
        t.add("roll_day")                             # first bar (the roll's own day only: later days carry no flag)
    if rw:
        t.add("roll_week")                            # N7.5: independent of the day type tag
    if CAL.early_close_min(d):
        t.add("early_close")
    if CAL.is_auction_day(d):
        t.add("auction")
    return t


def _calendar_rules(P: DayPlan, d: date, p, hist, ctx, a5) -> None:
    tg = P.tags
    if p.skip_holiday_eve and "holiday_eve" in tg:                          # N7.1 (cc08_006 ~5:06; cc10_008 ~6:54)
        P.block(None, "holiday_eve")
    if p.skip_post_holiday_am and "post_holiday" in tg and p.post_holiday_am != "symmetry":      # N7.2 (090 ~8:00); caption-gap N7-post-holiday-am-symmetry: "symmetry" releases it once ES / NQ agree (dwc1.gate)
        P.block(NY_MORNING if p.post_holiday_pre_open else NY_AM, "post_holiday_am")   # [our interpretation] the NY AM family
                                                                            # only (post_holiday_pre_open adds the 07:00-08:30 pre-open
                                                                            # windows); London is not "the morning"
    if p.skip_august and d.month == 8 and d.day >= p.august_from_day:       # N7.6 (079 ~8:54; 084; 087)
        P.block(None, "august")
    if p.skip_roll_week and "roll_week" in tg:                              # N7.5 (093 ~0:32)
        P.block(None, "roll_week")
    if "holiday_week" in tg and d.weekday() in (3, 4):
        tg.add("holiday_week_thu_fri")                                      # N7.3 tag (072 ~3:36)
    # Ep01.8 / N7.4 low-volatility inside day: the last trading day of the year (+ holiday-adjacent days)
    lv = "last_day" in tg or (p.low_vol_holiday_adj and ("holiday_eve" in tg or "post_holiday" in tg))
    if lv:
        tg.add("low_vol_inside")
        if p.low_vol_inside == "skip":
            P.block(None, "low_vol_inside")
        elif p.low_vol_inside == "scalp":
            P.set_scalp("low_vol_inside")
    # Ep02.7 / N7.4 first trading day of the year: "don't rush"
    if "first_day" in tg:
        if p.first_day_skip_am:
            P.block(NY_AM, "first_day_am")
        wait = max(p.first_day_wait, p.year_first_am_from)
        if wait:
            P.floor({"AM", "PRE7", "PRE8", "PRE9", "NEWS"}, wait, "first_day_wait")


# --- candle-pattern rules (B11 family, N8.5) ------------------------------------------------------------------

def _candle_rules(P: DayPlan, d: date, p, hist, eth, a5) -> None:
    cp = candle_patterns(hist, p, eth)
    P.info["candles"] = cp
    tg = P.tags
    if cp["inside_day"]:
        tg.add("inside_day")
        if p.b11_inside_expansion != "off":
            tg.add("b11_inside_expansion")
            P.expansion.add("inside_day")
    if cp["outside"]:
        tg.add("outside_" + cp["outside"])
    if "nr3" in p.nr_tags and cp["nr3"]:
        tg.add("nr3")
    if "nr7" in p.nr_tags and cp["nr7"]:
        tg.add("nr7")
    if "inside_body" in p.nr_tags and cp["inside_body"]:
        tg.add("inside_body")
    # nr_expansion evaluates NR3 / NR7 itself (nr_tags only controls the reporting tags and the opt-in inside_body reading)
    if p.nr_expansion != "off" and (cp["nr3"] or cp["nr7"] or tg & {"inside_body", "inside_day"}):
        for k_ in ("nr3", "nr7"):
            if cp[k_]:
                tg.add(k_)
        tg.add("nr_expansion")
        P.expansion.add("nr")
    if p.outside_day_rule != "off" and cp["outside"]:
        down = cp["outside"] == "down"
        if down or p.outside_day_mirror:
            P.info["outside_day"] = (cp["outside"], cp["out_hi"], cp["out_lo"])
            tg.add("outside_day_rule")
    if p.b11_inside_week != "off":
        wp = week_patterns(hist, d, p, eth)
        P.info["inside_week"] = wp
        if wp["inside"]:
            tg.add("inside_week")
            if wp["expanded"]:
                tg.add("inside_week_expanded")
            if wp["scalp"] and p.b11_inside_week == "scalp":
                P.set_scalp("inside_week")
    # N8.5: the prior range under ADR5 -> an expansion of 1.5-2 x ADR5 is due (cc08_006 ~23:33)
    if (p.expansion_due or p.expansion_targets) and len(hist) >= 6:
        a_prior = adr(hist, p, eth, 5, offset=1)
        if a_prior:
            r1 = day_range(hist[-1], eth, p)
            P.info["adr_prev"] = r1 / a_prior
            if r1 < p.expansion_frac * a_prior:
                tg.add("expansion_due")
                P.info["expansion_due"] = True
    if len(hist) >= 6 and "adr_prev" not in P.info:
        a_prior = adr(hist, p, eth, 5, offset=1)
        if a_prior:
            P.info["adr_prev"] = day_range(hist[-1], eth, p) / a_prior


# --- week rules (X15d / D19 / N8.6 / M14 ...) ------------------------------------------------------------------

def _week_objective_levels(ctx, hist, d: date, p, eth) -> dict:
    """X15d the weekly draw: {name: (level, kind)} with kind "high" / "low" / "ce_up" / "ce_dn" - the all-hours prior-week
    high / low (full sessions from ctx.eth, else the regular sessions) and the CE of this week's NWOG (Friday
    close -> the first session's open: the Sunday 18:00 open from eth when there is one) [our interpretation]."""
    out = {}
    wk = _weeks([x for x in hist if x.index[0].date() < d])
    this = _week_key(d)
    prior = [(k, f) for k, f in wk if k != this]
    if prior:
        hh, ll = _week_hl(prior[-1][1], eth, True)
        out["pwh"] = (hh, "high")
        out["pwl"] = (ll, "low")
        pc = _prior_close(prior[-1][1][-1], eth)
        first = d
        for x in CAL.week_dates(d):
            if CAL.is_trading_day(x):
                first = x
                break
        so = None
        if first == d:                                      # the week's first trading day: the evening session before it
            ev = getattr(ctx, "eve", None)                  # (the Sunday 18:00 open) is the only open known before 09:30
            if ev:
                so = float(ev[0])
        elif eth and first in eth:
            so = float(eth[first][0])                       # completed first session: its all-hours open (Sunday 18:00)
        else:
            cur = [f for k, f in wk if k == this]
            if cur:
                so = float(cur[0][0].open.iloc[0])          # no all-hours data: the first RTH open
        if so is not None and abs(so - pc) > 0:
            out["nwog_ce"] = ((so + pc) / 2, "ce_up" if so > pc else "ce_dn")
            out["_nwog"] = (pc, so)
    return out


def _prior_close(fr, eth: dict | None) -> float:
    """The prior week's last close: the all-hours (17:00) close of the session when `eth` has it, else the 16:00 regular
    close [our interpretation: the Friday-close side of the NWOG / the Sunday gap]."""
    d = fr.index[0].date()
    if eth and d in eth:
        return float(eth[d][3])
    return float(fr.close.iloc[-1])


def week_range_so_far(ctx, hist, d: date, p, eth, i: int | None = None) -> tuple | None:
    """High / low of THIS week from completed sessions (full sessions when eth has them) plus today's bars through
    the closed bar i (None = completed sessions only)."""
    c = _ctx_cache(ctx)
    if "wk_done" not in c:
        cur = [x for x in hist if _week_key(x.index[0].date()) == _week_key(d) and x.index[0].date() < d]
        c["wk_done"] = _week_hl(cur, eth, True) if cur else None
    base = c["wk_done"]
    td = _day_hl(ctx, i) if i is not None and i >= ctx.start else None
    if base is None and td is None:
        return None
    if base is None:
        return td
    if td is None:
        return base
    return max(base[0], td[0]), min(base[1], td[1])


def objective_delivered(ctx, hist, d: date, p, eth, i: int | None) -> list:
    """Names of the weekly objectives delivered by the completed sessions (i None) or by completed sessions + the
    closed bars of today through i. week_done_pick "nearest": only the objective nearest to the week's first open."""
    c = _ctx_cache(ctx)
    key = ("wobj",)
    if key not in c:
        lv = _week_objective_levels(ctx, hist, d, p, eth)
        names = [n for n in p.week_done_levels if n in lv]
        if p.week_done_pick == "nearest" and names:
            ref = lv["_nwog"][1] if "_nwog" in lv else float(hist[-1].close.iloc[-1])
            names = [min(names, key=lambda n: abs(lv[n][0] - ref))]
        c[key] = (lv, names)
    lv, names = c[key]
    rng = week_range_so_far(ctx, hist, d, p, eth, i)
    if rng is None:
        return []
    hi, lo = rng
    done = []
    for n in names:
        v, kind = lv[n]
        if (kind == "high" and hi >= v) or (kind == "low" and lo <= v) \
                or (kind == "ce_up" and lo <= v) or (kind == "ce_dn" and hi >= v):
            done.append(n)
    return done


def _week_rules(P: DayPlan, ctx, d: date, p, hist, eth, a5, week: dict) -> None:
    tg = P.tags
    # D19 / X15: the weekly trade budget is enforced in run_day (week_left); here only the tag
    if p.max_trades_week:
        left = max(0, p.max_trades_week - int(week.get("n", 0)))
        P.info["week_left"] = left
        if left <= 0:
            P.block(None, "week_cap")
    if p.late_week_flat and week.get("flat_done"):
        P.block(None, "week_flat_done")                # caption-gap new-late-week-close-flat: the week was closed flat by a recovery re-entry
    # X15d: the weekly objective already delivered by the completed sessions -> done for the week
    if p.week_done_on_draw != "off":
        done = objective_delivered(ctx, hist, d, p, eth, None)
        P.info["week_done"] = done
        if done:
            tg.add("week_done")
            if p.week_done_on_draw == "skip":
                P.block(None, "week_done")
    # N10.4: Friday after a week whose targets were all met (100 ~7:05)
    if d.weekday() == 4 and p.friday_week_done != "off":
        if p.friday_week_done == "draw":
            fd = objective_delivered(ctx, hist, d, p, eth, None)
            hit = bool(fd)
        else:                                          # "trades": the week traded and every trade hit its last target
            hit = bool(week.get("n", 0)) and bool(week.get("all_final", False))
        if hit:
            tg.add("friday_week_done")
            P.block(None, "friday_week_done")
    # N8.6 seek & destroy weeks (024 ~13:57; 044 ~1:36:11; cc07_002 ~7:42): July / August, FOMC and NFP weeks
    sdw = _sd_week(d, p)
    if sdw:
        tg.add("sd_week")
        if p.sd_week_skip == "skip":
            P.block(None, "sd_week")


def _sd_week(d: date, p) -> bool:
    if d.month in p.sd_week_months:
        return True
    if p.sd_week_news:
        wk = CAL.week_dates(d)
        if any("fomc" in events(x) for x in wk) or CAL.nfp_date(d) is not None:
            return True
    return False


# --- Friday (N10.4, M14, M14.1, M14.3) -------------------------------------------------------------------------

def _friday_rules(P: DayPlan, ctx, d: date, p, hist, eth, a5) -> None:
    if d.weekday() != 4:
        return
    tg = P.tags
    mt = [x for x in hist if _week_key(x.index[0].date()) == _week_key(d) and x.index[0].date() < d]
    if mt and p.tgif_week_sweep:
        P.info["tgif_ref"] = _week_hl(mt, eth, True)        # M14.3: the Mon-Thu extremes Friday must sweep
    th = hist[-1] if hist else None
    if th is not None and th.index[0].date().weekday() == 3 and (p.strong_thu_no_long or p.no_fri_after_strong_thu
                                                                 or p.mon_wed_extreme != "off"):
        s = strong_day(th, adr(hist, p, eth, 5, offset=1), p.strong_thu_mult, p.strong_thu_frac)
        if s:
            tg.add("strong_thu_up" if s > 0 else "strong_thu_down")
            if p.no_fri_after_strong_thu:
                P.block(None, "strong_thu")
            if p.strong_thu_no_long and (s > 0 or p.strong_thu_mirror):
                P.side_block("strong_thu_no_long" if s > 0 else "strong_thu_no_short", (1,) if s > 0 else (-1,))
    if p.friday_objective != "off":                    # "small range unless the weekly objective is unmet" (cc08_001)
        done = objective_delivered(ctx, hist, d, p, eth, None)
        P.info["friday_obj"] = done
        if done:
            tg.add("friday_objective_met")
            if p.friday_objective == "skip":
                P.block(None, "friday_objective")
            elif p.friday_objective == "scalp":
                P.set_scalp("friday_objective")


# --- Monday family (N10.2, D20, B16) -----------------------------------------------------------------------------

def _nfp_fomc_week(d: date, p=None) -> bool:
    from . import dwc1 as _D1                        # (caption-gap D20-landmine-week-monday 064 ~00:10:18: landmine_min releases Tue-Fri exempt Monday too)
    return (CAL.nfp_date(d) is not None or any("fomc" in events(x) for x in CAL.week_dates(d))
            or (p is not None and _D1.landmine_exempt(d, p)))


def _monday_rules(P: DayPlan, ctx, d: date, p, hist, eth, a5) -> None:
    tg = P.tags
    monday_like = CAL.is_week_start(d)                  # Monday, or Tuesday after a Monday holiday (cc09_008 ~55:24)
    if monday_like and p.monday_mode != "trade":
        if _nfp_fomc_week(d, p):
            tg.add("monday_exempt")                      # Monday of an NFP / FOMC week is always a trading day (100; 101)
        else:
            tg.add("monday_rule")
            if p.monday_mode == "skip":
                P.block(None, "monday")
            elif p.monday_mode == "pm_only":
                P.block(MORNING | {"LUNCH"}, "monday_pm_only")
            elif p.monday_mode == "obvious":
                P.info["monday_obvious"] = True           # evaluated at 09:30 (the htf row): gate()
            # monday_mode "big_into_array" (caption-gap N10-monday-weekly-extreme): decided in dwc2.plan_rules / gate
    if monday_like and p.monday_small_range and not _nfp_fomc_week(d, p):
        P.info["monday_small"] = True
    # N10.2 / cc12_003: "let Monday go" - Tuesday off Monday's extreme, Wednesday off Tuesday's
    if (p.tue_off_monday != "off" and d.weekday() in (1, 2) and hist
            and hist[-1].index[0].date() == CAL.prev_weekday(d) and not (d.weekday() == 1 and CAL.after_monday_holiday(d))):
        P.info["off_ref"] = (float(hist[-1].high.max()), float(hist[-1].low.min()))     # [our interpretation] a Tuesday after a
        tg.add("tue_off_monday")                                                          # Monday holiday has no Monday: no reference
    # B16: Sunday scenarios (futures only: needs the Sunday 18:00 open)
    if p.sunday_scenario != "off" and monday_like:                  # N7.2: the Tuesday after a Monday holiday has the Sunday gap too
        P.info["sunday"] = True
    # N10: Mon-Wed extremes (cc07_008): Thu / Fri
    if d.weekday() in (3, 4) and (p.mon_wed_extreme != "off" or p.pool_mon_wed or p.thu_fri_break != "off"):
        mw = [x for x in hist if _week_key(x.index[0].date()) == _week_key(d) and x.index[0].date().weekday() <= 2]
        if mw:
            hh, ll = _week_hl(mw, eth, True)
            P.info["mw"] = (hh, ll)
            tg.add("mw_extreme")


# --- consolidation days (N8.1 / N8.2 / N8.3 / N8.4 / N9.6) -------------------------------------------------------

def news_class(d: date) -> str:
    """High / medium / low 08:30 news of the day (N8.2 "high/medium 08:30 news")."""
    ev = events(d)
    if ev & HIGH_NEWS:
        return "high"
    if ev & MEDIUM_NEWS:
        return "medium"
    return "none"


def daily_arrays_touched(hist, p) -> tuple:
    """The last trend_array_days sessions traded into an open daily FVG formed before them: (+1 into a bullish
    array below -> expect up, -1 into a bearish array above -> expect down, 0 none). Daily candles from the
    regular sessions; an FVG stays open until a close beyond its far edge [our interpretation]."""
    n = len(hist)
    if n < 5:
        return 0
    o, h, l, c = _ohlc(hist)
    best = 0
    for z in L.fvgs(h, l, o, c):
        for j in range(max(z.i, n - p.trend_array_days), n):
            if j <= z.i:
                continue
            after = c[z.i + 1:j]
            dead = len(after) and ((z.kind == "bull" and after.min() < z.bottom) or (z.kind == "bear" and after.max() > z.top))
            if dead:
                continue
            if l[j] <= z.top and h[j] >= z.bottom:
                best = 1 if z.kind == "bull" else -1
    return best


def trend_recipe(P: DayPlan, d: date, p, hist, eth, a5) -> int | None:
    """N8.2 the trending-day recipe (cc10_009 ~1:17-2:46) - all three: (1) small / contracting prior ranges, (2) price
    just traded into a daily PD array, (3) high / medium 08:30 news. Returns the expected side (+1 / -1) when all
    hold, 0 when they hold but the array gives no side, None when one fails."""
    if len(hist) < 6 or a5 is None:
        return None
    rr = [day_range(x, eth, p) for x in hist[-3:]]
    small = rr[-1] < p.trend_small_frac * (adr(hist, p, eth, 5, offset=1) or a5)
    contract = rr[-1] < rr[-2] < rr[-3]
    if not ((small and not p.trend_contract) or contract):
        return None
    if news_class(d) not in p.trend_news:
        return None
    side = daily_arrays_touched(hist, p)
    return side if side else None


def _consol_predictors(ctx, d: date, p, hist, eth) -> list:
    """N8.3 the consolidation-day predictors (cc10_008 ~1:51-7:47; 053 ~0:38) known before the open."""
    out = []
    names = p.consol_predictors
    if "no_report" in names:
        rt = CAL.release_times(d)
        later = any(CAL.release_times(x) for x in CAL.week_dates(d) if x > d)
        if not [r for r in rt if r < 840] and later:
            out.append("no_report")                  # no NY report today, reports later in the week
    if "holiday_eve" in names and CAL.is_holiday_eve(d, p.holiday_eve_bank):
        out.append("holiday_eve")
    if "auction" in names and CAL.is_auction_day(d):
        out.append("auction")
    px = float(hist[-1].close.iloc[-1]) if hist else None
    if px is not None and "htf_array" in names and getattr(ctx, "conf", None) is not None:
        now = pd.Timestamp(d, tz=ctx.idx.tz)
        tfs = {tf for s_ in (1, -1) for tf in ctx.conf.at(now, px, s_, now)}
        if tfs & {"4h", "D", "W"}:
            out.append("htf_array")                  # the prior close sits inside a 4h / D / W array
    if px is not None and "htf_50" in names and getattr(ctx, "pw", None) is not None:
        hi, lo = ctx.pw
        if hi > lo and abs(px - (hi + lo) / 2) <= p.consol_eq_tol * (hi - lo):
            out.append("htf_50")
    return out


def _consol_rules(P: DayPlan, ctx, d: date, p, hist, eth, a5) -> None:
    tg = P.tags
    # N8.2 trending-day recipe
    if p.trend_recipe != "off":
        side = trend_recipe(P, d, p, hist, eth, a5)
        if side is not None:
            tg.add("trend_recipe")
            P.info["trend_side"] = side
            if p.trend_recipe == "side":
                P.side_block("trend_recipe", (-side,))
        elif p.trend_recipe == "only":
            P.block(None, "no_trend_recipe")
    # N8.4 very large prior range -> sacrifice the AM (033 ~13:27); the ORG part is dynamic (gate)
    if p.big_day_am_skip and len(hist) >= 6:
        a_prior = adr(hist, p, eth, 5, offset=1)
        if a_prior and day_range(hist[-1], eth, p) > p.big_day_range_mult * a_prior:
            tg.add("big_day")
            P.block(AM_SACRIFICE, "big_day_am")
    # N8.3 consolidation-day predictors
    if p.consol_day_rules != "off":
        preds = _consol_predictors(ctx, d, p, hist, eth)
        P.info["consol_preds"] = preds
        if len(preds) >= p.consol_min_predictors:
            tg.add("consol_day")
            if p.consol_day_rules == "apply":
                P.set_scalp("consol_day", MORNING)         # AM scalps only
                P.info["consol_apply"] = True
    # N8.6 seek & destroy (needs the day's own bars: dynamic) - the context part
    if p.sd_no_hold or p.sd_week_skip == "tag":
        P.info["sd_week"] = _sd_week(d, p)


def range_regime(hist, p, eth=None) -> list:
    """B17.4 the daily-candle regime reasons ("range", "inside_bisi", "premium_run") among p.drr_tests, from completed
    sessions only [our interpretation]:
      range         the last drr_days sessions went nowhere: |last close - first open| < drr_net_frac x their high-low
                    range, and that range is < drr_range_mult x their mean daily range (a stack of overlapping candles,
                    not a trend that merely paused) - a multi-day range with no daily trend
      inside_bisi   yesterday's whole range sat inside one open daily FVG (strategy._inside_daily_fvg, 091 ~6:12)
      premium_run   a one-way run into an old daily high / low (strategy._premium_run, 044 ~1:14:47)"""
    out = []
    n = p.drr_days
    if "range" in p.drr_tests and len(hist) >= n:
        w = hist[-n:]
        o, h, l, c = _ohlc(w)
        rng = float(h.max() - l.min())
        mean = float(np.mean([day_range(x, eth, p) for x in w]))
        if rng > 0 and mean > 0 and abs(float(c[-1]) - float(o[0])) < p.drr_net_frac * rng and rng < p.drr_range_mult * mean:
            out.append("range")
    if "inside_bisi" in p.drr_tests or "premium_run" in p.drr_tests:
        from . import strategy as _S
        if "inside_bisi" in p.drr_tests and _S._inside_daily_fvg(hist):
            out.append("inside_bisi")
        if "premium_run" in p.drr_tests and _S._premium_run(hist, p):
            out.append("premium_run")
    return out


def _regime_rules(P: DayPlan, d: date, p, hist, eth) -> None:
    if p.daily_range_regime == "off":
        return
    why = range_regime(hist, p, eth)
    if not why:
        return
    P.tags |= {"daily_range"} | {"drr_" + x for x in why}
    P.info["drr"] = why
    if p.daily_range_regime == "skip":
        P.block(None, "daily_range")
    elif p.daily_range_regime == "scalp":
        P.set_scalp("daily_range")


def _misc_rules(P: DayPlan, ctx, d: date, p, hist, eth, a5) -> None:
    tg = P.tags
    if p.seasonal_tag:
        s = seasonal(d, p, hist)
        P.info["seasonal"] = s
    if p.london_adr_skip:
        P.info["london_adr"] = True


# --------------------------------------------------------------------------------------------------------------
# B23 seasonals
# --------------------------------------------------------------------------------------------------------------

def seasonal(d: date, p, hist) -> str:
    """B23 (cc10_015 ~5:04; road map, never a trigger): the month's seasonal reading "bull" / "bear" / "cons" /
    "split" from p.seasonal_map (12 entries, January first); with a second sample (p.seasonal_map_b) only when both
    lines agree (cc05_010: use only when the long- and short-sample lines agree), else "none". "fail" is appended
    after the 10th trading day (p.seasonal_fail_day) when the month so far moved against it; "htf_agree" /
    "htf_against" is added by stamp() from the htf table (the HTF trend must agree)."""
    m = p.seasonal_map[d.month - 1]
    if p.seasonal_map_b:
        if p.seasonal_map_b[d.month - 1] != m:
            return "none"
    if m in ("bull", "bear"):
        n = CAL.month_trading_day(d)
        mon = [x for x in hist if x.index[0].date().year == d.year and x.index[0].date().month == d.month]
        if n > p.seasonal_fail_day and len(mon) >= 5:
            mv = float(mon[-1].close.iloc[-1]) - float(mon[0].open.iloc[0])
            if (m == "bull" and mv < 0) or (m == "bear" and mv > 0):
                return m + ":fail"
    return m


# --------------------------------------------------------------------------------------------------------------
# the per-bar gates
# --------------------------------------------------------------------------------------------------------------

def _run(ctx, key: str, i: int, a: int, b: int):
    """Running (high, low) of today's bars with minute t in [a, b) through the closed bar i, None until such a bar
    has closed. Prefix arrays over the whole day frame are cached; a lookup reads index i only (causal, also when the
    Silver Bullet re-reads earlier bars after the main loop)."""
    c = _ctx_cache(ctx)
    k = ("run", key, a, b)
    if k not in c:
        m = (ctx.t >= a) & (ctx.t < b)
        m[:ctx.start] = False
        c[k] = (np.maximum.accumulate(np.where(m, ctx.h, -np.inf)), np.minimum.accumulate(np.where(m, ctx.l, np.inf)))
    hi, lo = c[k]
    if i < ctx.start or hi[i] == -np.inf:
        return None
    return float(hi[i]), float(lo[i])


def _day_hl(ctx, i: int):
    """Today's high / low through the closed bar i (all bars from the frame's first)."""
    return _run(ctx, "day", i, 0, 100000)


def _k570(ctx) -> int:
    return ctx.start + int(np.searchsorted(ctx.t[ctx.start:], 570))


def _adr(ctx, p, n: int = 5):
    P = getattr(ctx, "dplan", None)
    if n == 5 and P is not None and "adr5_prev" in P.info:
        return P.info["adr5_prev"]                      # computed once by plan() on the p.adr_basis
    return adr(getattr(ctx, "hist", []), p, getattr(ctx, "eth", None), n)


def overnight_stats(ctx, p, hist) -> dict | None:
    """N9.4 the overnight range and the pre-09:30 raid, from the bars that closed before 09:30 (midnight; with
    on_range_from "globex" from the 18:00 reopen via ctx.eve). Known once the 09:30 bar is in."""
    c = _ctx_cache(ctx)
    if "on" in c:
        return c["on"]
    k = _k570(ctx)
    if k >= len(ctx.t) or k <= ctx.start:
        return None
    hi, lo = float(ctx.h[ctx.start:k].max()), float(ctx.l[ctx.start:k].min())
    if p.on_range_from == "globex" and getattr(ctx, "eve", None):
        hi, lo = max(hi, ctx.eve[1]), min(lo, ctx.eve[2])
    out = dict(hi=hi, lo=lo, range=hi - lo)
    if p.raid_ref == "london":
        w0, w1 = p.london_adr_win                        # one London window for N9.6 and this raid test
        seg = [(ctx.t[j] >= w0) and (ctx.t[j] < w1) for j in range(ctx.start, k)]
        idx = np.flatnonzero(seg) + ctx.start
        if len(idx):
            lh, ll = float(ctx.h[idx].max()), float(ctx.l[idx].min())
            post = np.flatnonzero((ctx.t[ctx.start:k] >= w1)) + ctx.start
            if len(post):
                out["raid"] = max(float(ctx.h[post].max()) - lh, ll - float(ctx.l[post].min()), 0.0)
            else:
                out["raid"] = 0.0
    elif hist:
        pdh, pdl = _hl(hist[-1])
        out["raid"] = max(hi - pdh, pdl - lo, 0.0)
    c["on"] = out
    return out


def eve_draw(ctx, p, hist) -> dict | None:
    """N9.2 the draw as it stood at the prior close: the nearest untaken pool / array beyond the last close at least
    draw_lock_min_pts away, from the levels known before today's first bar (PDH / PDL 1-3, the prior NWOG / ORG
    levels, the previous week) [our interpretation: mark_levels at t=0 without the HTF table row]. Delivered
    before 09:30 when the overnight bars (and the evening session) traded to it."""
    c = _ctx_cache(ctx)
    if "eve_draw" in c:
        return c["eve_draw"]
    from .strategy import mark_levels
    k = _k570(ctx)
    if k >= len(ctx.t) or k <= ctx.start:
        return None
    lk = mark_levels(ctx, None, 0, "AM", p)
    out = dict(side=lk["side"], px=lk["target"], name=lk["name"], done=None, base=float(ctx.c[ctx.start - 1]))
    if lk["side"]:
        hi, lo = float(ctx.h[ctx.start:k].max()), float(ctx.l[ctx.start:k].min())
        ev = getattr(ctx, "eve", None)
        if ev:
            hi, lo = max(hi, ev[1]), min(lo, ev[2])
        out["done"] = bool(hi >= lk["target"] if lk["side"] > 0 else lo <= lk["target"])
    c["eve_draw"] = out
    return out


def london_adr_hit(ctx, p, i: int) -> bool:
    """N9.6 (cc08_001 ~13:41) London already made >= london_adr_skip x ADR5: skip the NY session. The London range
    is today's high - low over london_adr_win (default 02:00-05:00, the London window everywhere else) through the closed bar i; ADR5 from the completed
    sessions."""
    a = _adr(ctx, p)
    if not a:
        return False
    w = p.london_adr_win
    r = _run(ctx, "london", i, w[0], w[1])
    hit_ = bool(r is not None and (r[0] - r[1]) >= p.london_adr_skip * a)
    if hit_ and p.adr_news_exempt and any(x >= 600 for x in CAL.release_times(ctx.day)):     # caption-gap DS2-adr-filled-news-extends (cc09_007 ~00:18:32): a 10:00 / 14:00 release after the open extends the range - no ADR skip
        P_ = getattr(ctx, "dplan", None)
        if P_ is not None:
            P_.info["adr_filled_news"] = True
            P_.tags.add("adr_filled_news")
        from . import dwc2 as _D2
        _D2.hit("adr_news_exempt")
        return False
    return hit_


def macro_failed(ctx, p, session: str, i: int, t: int) -> bool:
    """N9.5 (073 ~30:51) "a macro window with no move toward the draw: close the charts for that session". Each
    window of p.macro_no_move_wins (AM) / macro_no_move_pm_wins (PM) that has ended by the closed bar i is tested
    once from the bars of the reference minutes before it and the window: the move toward the session's locked
    draw (else the htf bias side) is the window's extreme beyond the reference high (draw up) / low (draw down)
    by more than macro_move_pts. A failed window ends the session's entries from its end on."""
    am = session != "PM" and session != "LUNCH"
    on = p.macro_no_move if am else p.macro_no_move_pm
    if not on:
        return False
    wins = p.macro_no_move_wins if am else p.macro_no_move_pm_wins
    c = _ctx_cache(ctx)
    for (a, b) in wins:
        if t + ctx.tf < b:
            continue
        key = ("macro", a, b)
        if key not in c:
            c[key] = _macro_test(ctx, p, session, a, b, i)
        if c[key]:
            return True
    return False


def _macro_test(ctx, p, session: str, a: int, b: int, i: int | None = None) -> bool:
    lk = (getattr(ctx, "lock", None) or {}).get("PM" if session in ("PM", "LUNCH") else "AM")
    side = 0
    if lk and lk.get("side"):
        side = lk["side"]
    else:
        from .entries import bias_row_known
        row = bias_row_known(ctx, i)                    # the htf table is cut at the 09:30 open: never read before it
        if row is not None:
            try:
                side = int(row["draw"])
            except Exception:
                side = 0
    if not side:
        return False
    t = ctx.t
    S = ctx.start
    ref = np.flatnonzero((t[S:] >= a - p.macro_ref_min) & (t[S:] < a)) + S
    win = np.flatnonzero((t[S:] >= a) & (t[S:] < b)) + S
    if not len(ref) or not len(win):
        return False
    if side > 0:
        move = float(ctx.h[win].max()) - float(ctx.h[ref].max())
    else:
        move = float(ctx.l[ref].min()) - float(ctx.l[win].min())
    return move <= p.macro_move_pts * p.es_pt


def gate(ctx, p, session: str, i: int, t: int, trades=()) -> str | None:
    """A funnel key when `session` may not arm an order at the closed bar i (t = the bar's start minute), else None.
    Static day rules come from the DayPlan; the rest read only bars through i and completed candles."""
    P = getattr(ctx, "dplan", None)
    if P is None:
        return None
    why = P.static_reason(session, t)
    if why:
        return "x_dw_" + why
    d = ctx.day
    hist = getattr(ctx, "hist", [])
    mor = session in MORNING
    # N9.6 London made ~80% of ADR5
    if p.london_adr_skip and session in NY and london_adr_hit(ctx, p, i):
        return "x_dw_london_adr"
    # N9.4 narrow overnight range / shallow raid: no AM trade (015 ~11:58)
    if session in NY_AM and (p.min_on_range_frac or p.min_raid_pts) and t >= 570:
        st = overnight_stats(ctx, p, hist)
        a = _adr(ctx, p)
        if st is not None:
            if p.min_on_range_frac and a and st["range"] < p.min_on_range_frac * a:
                return "x_dw_on_range"
            if p.min_raid_pts and st.get("raid") is not None and st["raid"] < p.min_raid_pts * p.es_pt:
                return "x_dw_raid"
    # N9.2 the prior-close draw was delivered before 09:30: choppy open, trade the PM (022 ~1:16:11)
    if p.pre_draw_pm and session in NY_AM and t >= 570:
        ed = eve_draw(ctx, p, hist)
        if ed is not None and ed["done"]:
            return "x_dw_pre_draw"
    # N8.4 a large opening range gap: sacrifice the AM (033 ~13:27)
    if (p.big_day_am_skip and session in AM_SACRIFICE and t >= 570 and not (p.big_day_am_resume and t >= p.big_day_am_resume)       # (caption-gap N8-large-org-day: big_day_am_resume)
            and getattr(ctx, "org", None) and getattr(ctx, "org_today", False)):
        a = _adr(ctx, p)
        pc, op = ctx.org[-1]
        if a and abs(op - pc) >= p.big_day_org_frac * a:
            return "x_dw_big_org"
    # N8.3 consolidation day: AM scalps only if the opening range is small (known at 10:00)
    if P.info.get("consol_apply") and session == "AM":
        if t + ctx.tf < ctx.or_end:
            return "x_dw_consol_or_wait"
        a = _adr(ctx, p)
        if a and ctx.or_hl is None:
            return "x_dw_consol_or_missing"          # no opening-range data: not "small", so no stand-in scalp
        if a and (ctx.or_hl[0] - ctx.or_hl[1]) >= p.consol_or_frac * a:
            return "x_dw_consol_or_big"
    if P.info.get("consol_apply") and session in LATE and p.consol_pm_rule:
        if am_ran_pool(ctx, hist, i, p.consol_pm_pools):
            return "x_dw_consol_pm"
    # N9.5 macro windows without a move toward the draw
    if (p.macro_no_move or p.macro_no_move_pm) and macro_failed(ctx, p, session, i, t):
        return "x_dw_macro_no_move"
    # N9.3 objective done before lunch / X10d the AM delivered the range: the PM is done
    if session in LATE:
        if p.objective_done_skip and p.objective_done_pm == "off" and objective_done(ctx, i, trades):      # (caption-gap N9-objective-before-lunch: objective_done_pm "reversal_only" trades the counter direction instead)
            return "x_dw_objective_done"
        if p.am_range_skip_pm and am_range_done(ctx, p, i):
            return "x_dw_am_range"
    # X15d the weekly objective delivered (completed sessions or today's closed bars): done for the week
    if p.week_done_on_draw == "skip":
        if objective_delivered(ctx, hist, d, p, getattr(ctx, "eth", None), i):
            return "x_dw_week_done"
    # D20 Monday small range: the small range is made
    if P.info.get("monday_small") and p.monday_small_range:
        a = _adr(ctx, p)
        dh = _day_hl(ctx, i)
        if a and dh is not None and (dh[0] - dh[1]) >= p.monday_small_range * a:
            return "x_dw_monday_small"
    # N10.2 Monday "obvious" only: HTF reaction and draw agree (the htf row is cut at 09:30)
    if P.info.get("monday_obvious"):
        if t < 570:
            return "x_dw_monday_wait"
        row = getattr(ctx, "bias_row", None)
        try:
            ok = row is not None and int(row["react"]) != 0 and int(row["react"]) == int(row["draw"])
        except Exception:
            ok = False
        if not ok:
            return "x_dw_monday_not_obvious"
    # B15 org_tell_wait: no entry until the 10:00 tell is known
    if p.org_tell != "off" and p.org_tell_wait and session == "AM" and ctx.t[i] + ctx.tf < 570 + p.org_break_min:
        if getattr(ctx, "org_today", False):
            return "x_dw_org_tell_wait"
    # B16 Sunday scenarios (Monday)
    if P.info.get("sunday") and p.sunday_scenario == "filter":
        if t < 570:
            return "x_dw_sunday_wait"
        sc = sunday_state(ctx, p, hist)
        if sc == "neither" or (sc == "no_gap" and not p.sunday_no_gap_trade):
            return "x_dw_sunday_" + sc
    # N7.2 PM after a holiday only once ES / NQ move in step
    if p.post_holiday_pm_sync and "post_holiday" in P.tags and session in LATE:
        if not partners_in_step(ctx, i):
            return "x_dw_post_holiday_sync"
    # M14.3 TGIF timing windows
    if "tgif" in str(getattr(ctx, "day_tags", "")) and p.tgif_timing and d.weekday() == 4:
        if not any(a <= t < b for a, b in p.tgif_timing):
            return "x_dw_tgif_timing"
    # N8.1 / N8.6 consolidation / seek-and-destroy handled via scalp_now (no gate)
    from . import dwc1 as _D1                        # caption-gap pass day_week_context#1/3
    why_ = _D1.gate(ctx, p, session, i, t, trades)
    if why_ is not None:
        return why_
    from . import dwc2 as _D2                        # caption-gap pass day_week_context#2/3
    why_ = _D2.gate(ctx, p, session, i, t, trades)
    if why_ is not None:
        return why_
    from . import bias_day as _BD                    # bias_htf: objective met, neutral gates, chop, intermarket, NWOG regime ...
    return _BD.gate(ctx, p, session, i, t)


def am_ran_pool(ctx, hist, i: int, pools: tuple = ("pd", "london", "draw")) -> bool:
    """N8.3 "the AM has run a stop pool" [our interpretation], tested through the closed bar i against the pools named
    in `pools` (p.consol_pm_pools):
      pd       the 09:30-12:00 range traded beyond the prior day's high / low
      london   ... beyond London's high / low (ctx.sess["london"])
      on       ... beyond the overnight high / low (the whole pre-09:30 range: nearly every normal AM trips it, so it
               is opt-in)
      draw     the AM session lock's draw was delivered by the closed bar i (the pool the AM itself targeted)
    False while none of them has been run (a quiet AM leaves the PM open)."""
    r = _run(ctx, "am", i, 570, 720)
    if "draw" in pools:
        lk = (getattr(ctx, "lock", None) or {}).get("AM")
        di = None if lk is None else lk.get("delivered_i")
        if lk is not None and lk.get("delivered") and di is not None and di <= i:
            return True
    if r is None:
        return False
    hi, lo = r
    if "pd" in pools and hist:
        h_, l_ = _hl(hist[-1])
        if hi > h_ or lo < l_:
            return True
    if "on" in pools and "pmh" in ctx.pd and (hi > ctx.pd["pmh"] or lo < ctx.pd["pml"]):
        return True
    if "london" in pools and "london" in getattr(ctx, "sess", {}):
        if hi > ctx.sess["london"][0] or lo < ctx.sess["london"][1]:
            return True
    return False


def budget_full(ctx, ts, mine=(), others=()) -> bool:
    """D19 / X15 the week's trade budget is used up at the time `ts`: the trades of every engine that had filled by
    then (`mine` + `others`, each counted once; the previous pass of run_day's fixed point stands in for the engines
    that run later) number at least the trades left in the week. False without a cap. A trade filled later never
    counts, so no decision sees the future; the cap itself is the week's budget minus the earlier days' trades."""
    P = getattr(ctx, "dplan", None)
    wl = None if P is None else P.info.get("week_left")
    if wl is None:
        return False
    seen, n = set(), 0
    for tr in list(mine) + list(others):
        if id(tr) in seen:
            continue
        seen.add(id(tr))
        if tr.entry_time <= ts:
            n += 1
    return n >= wl


def objective_done(ctx, i: int, trades=()) -> bool:
    """N9.3 (015 ~16:22) the day's objective was delivered before noon: an AM-family session lock was delivered
    before 12:00, or a morning trade closed with its last level hit (final_hit) before 12:00 [our interpretation].
    Uses the lock flags / trades as of the closed bar i."""
    for s_, lk in (getattr(ctx, "lock", None) or {}).items():
        if s_ in ("PM", "LH"):
            continue
        di = lk.get("delivered_i")
        if lk.get("delivered") and di is not None and di <= i and ctx.t[di] + ctx.tf <= 720:
            return True
    for tr in trades:
        if tr.session not in ("PM", "LUNCH", "LH") and tr.exits and tr.final_hit:
            tx = tr.exits[-1][0]
            if tx <= ctx.idx[i] and tx.hour * 60 + tx.minute + ctx.tf <= 720:
                return True
    return False


def am_range_done(ctx, p, i: int) -> bool:
    """X10d the AM (09:30-12:00) range, complete once the 12:00 bar is in, is >= am_range_skip_pm x ADR5."""
    if ctx.t[i] < 720 - ctx.tf:
        return False
    a = _adr(ctx, p)
    r = _run(ctx, "am", i, 570, 720)
    return bool(a and r is not None and (r[0] - r[1]) >= p.am_range_skip_pm * a)


def partners_in_step(ctx, i: int) -> bool:
    """N7.2 (090 ~8:00) ES / NQ in step: both instruments' moves since the 09:30 open have the same sign. True when
    there is no partner data (nothing to check)."""
    ps = getattr(ctx, "pside", None)
    if not ps or ps[0] is None:
        return True
    pctx, _, ppos = ps
    try:
        j = int(ppos.index.get_indexer([ctx.idx[i]])[0])
    except Exception:
        return True
    if j < 0:
        return True
    k0 = _k570(ctx)
    kp = pctx.start + int(np.searchsorted(pctx.t[pctx.start:], 570))
    if k0 >= len(ctx.t) or kp >= len(pctx.t) or k0 > i or kp > j:
        return True
    a, b = ctx.c[i] - ctx.o[k0], pctx.c[j] - pctx.o[kp]
    return bool(a * b > 0)


def sunday_state(ctx, p, hist) -> str:
    """B16 the Sunday gap scenarios at Monday 09:30 (028 ~1:09:37-1:16:09; 077 ~7:30; 084 ~3:21; 103 ~7:22), from the
    Friday RTH close and the Sunday 18:00 open (ctx.eve): "fill" (price traded back to the gap's CE by 09:30),
    "away" (never reached the CE and ran >= sunday_away_mult x the gap beyond the open), "neither" (wait for
    Monday 09:30, trade from Tuesday), "no_gap" (no gap >= sunday_min_gap_pts), "na" (no evening data / no Friday
    close: not futures). Bars that closed before 09:30 only."""
    c = _ctx_cache(ctx)
    if "sunday" in c:
        return c["sunday"]
    ev = getattr(ctx, "eve", None)
    k = _k570(ctx)
    if not ev or not hist or k >= len(ctx.t) or k <= ctx.start:
        return "na"
    so, ehi, elo = ev[0], ev[1], ev[2]
    pc = _prior_close(hist[-1], getattr(ctx, "eth", None))
    gap = so - pc
    if abs(gap) < p.sunday_min_gap_pts * p.es_pt:
        c["sunday"] = "no_gap"
        return "no_gap"
    hi, lo = max(ehi, float(ctx.h[ctx.start:k].max())), min(elo, float(ctx.l[ctx.start:k].min()))
    ce = (so + pc) / 2
    up = gap > 0
    if (up and lo <= ce) or (not up and hi >= ce):
        out = "fill"
    else:
        ext = (hi - so) if up else (so - lo)
        out = "away" if ext >= p.sunday_away_mult * abs(gap) else "neither"
    c["sunday"] = out
    return out


# --------------------------------------------------------------------------------------------------------------
# side rules
# --------------------------------------------------------------------------------------------------------------

def org_tell(ctx, p, i: int) -> int:
    """B15 (030 ~1:27:01) the ORG direction tell: the 09:30 open gaps away from the prior RTH close and makes no
    attempt back to the gap's org_tell_level (50%) within org_break_min minutes -> +1 (gap up, very bullish) /
    -1 (gap down, very bearish); 0 while unknown (the bar that closes at 09:30 + org_break_min is not in yet) or
    when the gap was attempted. Reads the bars of the window only."""
    if not getattr(ctx, "org_today", False) or not getattr(ctx, "org", None):
        return 0
    k0 = _k570(ctx)
    kend = ctx.start + int(np.searchsorted(ctx.t[ctx.start:], 570 + p.org_break_min))
    if i < kend - 1 or k0 >= kend or kend > len(ctx.t):
        return 0
    c = _ctx_cache(ctx)
    if "tell" not in c:
        pc, op = ctx.org[-1]
        c["tell"] = 0
        if abs(op - pc) >= 0.25 * p.es_pt:
            lvl = op + p.org_tell_level * (pc - op)
            if pc > op:                              # gap down: no attempt back up = very bearish
                c["tell"] = 0 if ctx.h[k0:kend].max() >= lvl else -1
            else:                                    # gap up: no attempt back down = very bullish
                c["tell"] = 0 if ctx.l[k0:kend].min() <= lvl else 1
    return c["tell"]


def org_gap_state(ctx, p, i: int) -> tuple:
    """B15 (055 ~17:50) bias x gap: returns (gap direction +1 up / -1 down / 0, repriced) - repriced = the gap has been
    traded back into by the closed bars through i (to org_gap_fill_frac of the way to the prior close)."""
    if not getattr(ctx, "org_today", False) or not getattr(ctx, "org", None):
        return 0, False
    pc, op = ctx.org[-1]
    if abs(op - pc) < 0.25 * p.es_pt:
        return 0, False
    k0 = _k570(ctx)
    if k0 > i:
        return 0, False
    lvl = op + p.org_gap_fill_frac * (pc - op)
    r = _run(ctx, "rth", i, 570, 100000)
    if r is None:
        return 0, False
    if pc < op:                                      # gap up: repriced when price traded down to the level
        return 1, bool(r[1] <= lvl)
    return -1, bool(r[0] >= lvl)


def _bias_side(ctx, p, i: int) -> int:
    from .entries import bias_row_known
    row = bias_row_known(ctx, i)
    if row is None:
        return 0
    try:
        return int(row[p.org_bias_src])
    except Exception:
        return 0


def side_ok(ctx, p, sign: int, session: str, i: int) -> str | None:
    """A funnel key when this side may not be traded at the closed bar i, else None."""
    P = getattr(ctx, "dplan", None)
    if P is None:
        return None
    for why, signs in P.sides.items():
        if sign in signs:
            return "x_dw_" + why
    d = ctx.day
    # B11b outside-day rule: block longs until the (down-close) outside day's high has traded today
    od = P.info.get("outside_day")
    if od and p.outside_day_rule == "block":
        kind, hi, lo = od
        dh = _day_hl(ctx, i)
        if dh is not None:
            if kind == "down" and sign > 0 and not dh[0] >= hi:
                return "x_dw_outside_day"
            if kind == "up" and sign < 0 and p.outside_day_mirror and not dh[1] <= lo:
                return "x_dw_outside_day"
    # B15 ORG tell: only the tell's side once it is known
    if p.org_tell == "filter":
        tl = org_tell(ctx, p, i)
        if tl and sign != tl:
            return "x_dw_org_tell"
    # B15 bias x gap (AM only)
    if p.org_bias_gap == "filter" and session not in LATE:
        gd, rep = org_gap_state(ctx, p, i)
        b = _bias_side(ctx, p, i)
        if gd and b:
            if sign != b:
                return "x_dw_org_bias_gap"
            if b == gd and not rep:
                return "x_dw_org_gap_wait"           # bullish + gap up: reprice into the gap first, then higher
    # N10.3 Thu / Fri break of the Mon-Wed extreme = expansion: trade the break only
    if p.thu_fri_break == "side" and d.weekday() in (3, 4) and "mw" in P.info:
        hh, ll = P.info["mw"]
        dh = _day_hl(ctx, i)
        up = bool(dh is not None and dh[0] > hh)
        dn = bool(dh is not None and dh[1] < ll)
        if up != dn and sign != (1 if up else -1):
            from . import dwc2 as _D2                # caption-gap N10-mon-wed-range-break: mw_break_bias counts only the weekly-bias side's break
            if not p.mw_break_bias or _D2.weekly_bias(ctx, getattr(ctx, "hist", []), d, p) == (1 if up else -1):
                return "x_dw_thu_fri_break"
    # T14 Tuesday of a bullish / bearish week: the week's extreme forms on Tuesday (switch built from study_week)
    if p.tue_week_extreme == "side" and d.weekday() == 1:
        row = getattr(ctx, "bias_row", None)
        if row is not None and ctx.t[i] >= 570:
            try:
                b = int(row["draw"])
            except Exception:
                b = 0
            if b and sign != b:
                return "x_dw_tue_week_extreme"
    # N8.6 seek & destroy context required for no_hold is a scalp rule (see scalp_now); nothing here
    from . import dwc1 as _D1                        # caption-gap pass day_week_context#1/3
    why_ = _D1.side_ok(ctx, p, sign, session, i)
    if why_ is not None:
        return why_
    from . import dwc2 as _D2                        # caption-gap pass day_week_context#2/3
    why_ = _D2.side_ok(ctx, p, sign, session, i)
    if why_ is not None:
        return why_
    from . import bias_day as _BD                    # bias_htf: the bias side (all engines), weekly open, judas, filters ...
    return _BD.side_ok(ctx, p, sign, session, i)


def order_ok(ctx, sd, o: dict, session: str, i: int, p) -> str | None:
    """A funnel key when the armed order `o` breaks a per-order day rule (side space prices), else None."""
    P = getattr(ctx, "dplan", None)
    if P is None:
        return None
    # N10.2 Tuesday off Monday's extreme / Wednesday off Tuesday's: the sweep took the reference day's low / high
    if p.tue_off_monday == "filter" and "off_ref" in P.info:
        hi, lo = P.info["off_ref"]
        ext = sd.x(o["ext"])
        took = ext <= lo if sd.sign > 0 else ext >= hi
        if not took:
            return "x_dw_tue_off_monday"
    # M14.3 tgif_week_sweep: Friday has traded beyond the week's extreme before the order
    if p.tgif_week_sweep and ctx.day.weekday() == 4 and "tgif" in str(getattr(ctx, "day_tags", "")):
        ref = P.info.get("tgif_ref")
        if ref is not None:
            hi, lo = ref
            dh = _day_hl(ctx, i)
            taken = bool(dh is not None and (dh[0] > hi if sd.sign < 0 else dh[1] < lo))
            if not taken:
                return "x_dw_tgif_week_sweep"
    from . import dwc1 as _D1                        # caption-gap pass day_week_context#1/3
    why_ = _D1.order_ok(ctx, sd, o, session, i, p)
    if why_ is not None:
        return why_
    from . import dwc2 as _D2                        # caption-gap pass day_week_context#2/3
    why_ = _D2.order_ok(ctx, sd, o, session, i, p)
    if why_ is not None:
        return why_
    from . import bias_day as _BD                    # bias_htf: mwd_nest, mmbm_zone, 50/50 and the order tags
    return _BD.order_ok(ctx, sd, o, session, i, p)


def scalp_now(ctx, p, session: str, i: int | None = None) -> str:
    """The day-context reason an order of `session` is a scalp (one exit min(+5, T1), no adds), else "": the
    DayPlan's static scalp flags (inside week, low-volatility day, consolidation day, Friday objective met) and
    the dynamic seek-and-destroy no-hold (N8.6: both sides of yesterday's range run today)."""
    P = getattr(ctx, "dplan", None)
    if P is None:
        return ""
    for why, ss in P.scalp.items():
        if ss is None or session in ss:
            return why
    if p.sd_no_hold and i is not None:
        if (not p.sd_context_required) or P.info.get("sd_week"):
            if seek_destroy(ctx, i):
                return "sd_no_hold"
    from . import dwc1 as _D1                        # caption-gap pass day_week_context#1/3
    why_ = _D1.scalp_now(ctx, p, session, i)
    if why_:
        return why_
    from . import bias_day as _BD                    # bias_htf: neutral bias / no narrative / chop / consolidation-week scalps
    return _BD.scalp_now(ctx, p, session, i)


def seek_destroy(ctx, i: int) -> bool:
    """N8.6 "seek & destroy" (both sides run, then reversal): through the closed bar i today's bars have traded
    beyond BOTH the prior day's high and its low."""
    hist = getattr(ctx, "hist", [])
    if not hist or i < ctx.start:
        return False
    hh, ll = _hl(hist[-1])
    dh = _day_hl(ctx, i)
    return bool(dh is not None and dh[0] > hh and dh[1] < ll)


def flat_for(day, p, flat: int) -> int:
    """N7.1 EARLY_CLOSE: a shortened day is flat before its early close (early_close_min; the bars normally end
    there: such days are not loaded by backtest.days(), so this matters for custom frames / live)."""
    if p.early_close_flat:
        ec = CAL.early_close_min(day)
        if ec:
            return min(flat, ec)
    return flat


def day_exit(ctx, p, session: str, t_close: int) -> str | None:
    """A reason an open position must be closed at this bar's close for a day-context rule: N8.3 consolidation-day
    AM trades are out by consol_am_out (11:00)."""
    P = getattr(ctx, "dplan", None)
    if P is None or not P.info.get("consol_apply") or not p.consol_am_out:
        return None
    if session not in LATE and t_close >= p.consol_am_out:
        return "consol_out"
    return None


def day_risk(ctx, p, lvt: list | None = None) -> float:
    """Risk multiplier of the day: N7.6 august_risk (from august_from_day), N7.5 roll_risk in the futures roll week."""
    m = 1.0
    d = ctx.day
    if p.august_risk != 1.0 and d.month == 8 and d.day >= p.august_from_day:
        m *= p.august_risk
        if lvt is not None:
            lvt.append("size_august_dw")
    P = getattr(ctx, "dplan", None)
    if p.roll_risk != 1.0 and (("roll_week" in P.tags) if P is not None else CAL.roll_week(d)):
        m *= p.roll_risk
        if lvt is not None:
            lvt.append("size_roll_week")
    from . import dwc1 as _D1
    m *= _D1.size_mult(ctx, p, lvt)                 # caption-gap pass day_week_context#1/3: August light, holiday weeks, season_quality "size"
    from . import dwc2 as _D2
    m *= _D2.size_mult(ctx, p, lvt)                 # caption-gap pass day_week_context#2/3: the Monday into an array is half size
    return m


# --------------------------------------------------------------------------------------------------------------
# targets and pools (N10.3 pool_mon_wed, N8.5 expansion_targets)
# --------------------------------------------------------------------------------------------------------------

def _mw_pool_on(ctx, p, P) -> bool:
    """pool_mon_wed (N10.3), or (caption-gap new-consolidation-thursday-reversal) the Thursday false-break trade: the Mon-Wed extremes are pools on a flagged Thursday."""
    if P is None or "mw" not in P.info:
        return False
    return bool(p.pool_mon_wed or (p.thu_reversal_trade and ctx.day.weekday() == 3 and P.info.get("thu_rev")))


def target_pools(ctx, sd, i: int, p) -> list:
    """pool_mon_wed (N10.3): on Thursday / Friday the week's Mon-Wed high (low) is a buy-side (sell-side) pool and
    target, from the start of the day (completed sessions, full sessions when ctx.eth has them). [(level, created)]."""
    P = getattr(ctx, "dplan", None)
    if not _mw_pool_on(ctx, p, P):
        return []
    hh, ll = P.info["mw"]
    return [(sd.x(hh if sd.sign > 0 else ll), ctx.start)]


def sell_pools(ctx, sd, i: int, p) -> dict:
    """pool_mon_wed as the sell-side pool (side space) the sweep may take."""
    P = getattr(ctx, "dplan", None)
    if not _mw_pool_on(ctx, p, P):
        return {}
    hh, ll = P.info["mw"]
    return {"mon_wed": sd.x(ll if sd.sign > 0 else hh)}


def expansion_levels(ctx, sd, i: int, p) -> list:
    """expansion_targets (N8.5): on an expansion-due day (prior range < ADR5: a 1.5-2 x ADR5 move is due, cc08_006
    ~23:33) the day's extreme so far plus each multiple of ADR5 is an array target (side space) [our interpretation:
    measured from today's extreme at the closed bar i, the sweep extreme of the setup]."""
    P = getattr(ctx, "dplan", None)
    if p.expansion_targets and P is not None and p.expansion_strict and P.info.get("expansion_pending") and P.info.get("adr5_prev"):
        from . import dwc2 as _D2                    # caption-gap N8-expansion-day-conditions: the strict day (bias + manipulation leg opposite) adds 1.5 x ADR5 from the manipulation extreme
        return _D2.expansion_rungs(ctx, sd, i, p, P.info["adr5_prev"])
    if not p.expansion_targets or P is None or not P.info.get("expansion_due"):
        return []
    a = P.info.get("adr5_prev")
    if not a:
        return []
    ext = float(sd.l[ctx.start:i + 1].min())
    return [(ext + k * a, "array") for k in p.expansion_targets]


# --------------------------------------------------------------------------------------------------------------
# M14 / M14.1 TGIF context
# --------------------------------------------------------------------------------------------------------------

def _array_touch(conf, when: pd.Timestamp, price: float, want_kind: int, tfs, tol: float) -> bool:
    """M14.1 a valid HTF array (a bearish one at a high, a bullish one at a low) or any NWOG / NDOG (source 2)
    of the timeframes `tfs` contained `price` at `when`, counting arrays complete by then."""
    now = float(when.value)
    for tf in tfs:
        z = conf.z.get(tf)
        if z is None:
            continue
        m = ((z["known"] <= now) & (z["dead"] > now) & (now - z["known"] <= z["life"])
             & (z["bottom"] - tol <= price) & (price <= z["top"] + tol)
             & ((z["kind"] == want_kind) | (z["src"] == 2)))
        if m.any():
            return True
    return False


def tgif_context(hist, day: date, p, eth=None, conf=None) -> tuple:
    """M14 / M14.1: (side tag, blocked direction) for a Friday, else (None, None). The week's Mon-Thu range counts the
    full sessions (Sunday 18:00 on) when `eth` has them (tgif_htf_array); it must be >= 1.5 x the average of the
    prior weeks and Thursday must close in the top (bottom) quarter - and with tgif_htf_array the week's
    extreme must have touched a D / W / 4h array or an NWOG / NDOG (known at the open of the extreme's session).
    Returns ("tgif_short", 1) for a bullish week (only the retrace is allowed: longs blocked) or ("tgif_long", -1)."""
    if day.weekday() != 4 or len(hist) < 7:
        return None, None
    mon = day - timedelta(days=4)
    wk = [x for x in hist if x.index[0].date() >= mon]
    prior = {}
    for x in hist:
        k = _week_key(x.index[0].date())
        if x.index[0].date() < mon:
            prior.setdefault(k, []).append(x)
    if not wk or len(prior) < 2:
        return None, None
    use = bool(p.tgif_htf_array and eth)
    hi, lo = _week_hl(wk, eth, use)
    avg = np.mean([(lambda a_: a_[0] - a_[1])(_week_hl(v, eth, use)) for v in prior.values()])
    c = float(wk[-1].close.iloc[-1])
    if hi - lo < 1.5 * avg:
        return None, None
    if c >= hi - 0.25 * (hi - lo):
        tag, blk, ext, kind = "tgif_short", 1, hi, -1
    elif c <= lo + 0.25 * (hi - lo):
        tag, blk, ext, kind = "tgif_long", -1, lo, 1
    else:
        return None, None
    if p.tgif_htf_array and conf is not None:
        # the session that made the extreme (full-session extremes when eth has them)
        best, bd = None, None
        for x in wk:
            e = eth.get(x.index[0].date()) if eth else None
            v = (e[1] if kind < 0 else e[2]) if e else (float(x.high.max()) if kind < 0 else float(x.low.min()))
            if best is None or (v > best if kind < 0 else v < best):
                best, bd = v, x.index[0].date()
        when = pd.Timestamp(bd, tz=conf_tz(conf, wk)) + pd.Timedelta(hours=9, minutes=30)
        if not _array_touch(conf, when, best, kind, p.tgif_htf_tfs, conf.tol):
            return None, None
    return tag, blk


def conf_tz(conf, frames):
    return frames[0].index.tz


# --------------------------------------------------------------------------------------------------------------
# journal columns (X16 / X16a / X16b / X16d / B23 / N9.2) and the day's tags on every trade
# --------------------------------------------------------------------------------------------------------------

def stamp(ctx, trades, p) -> None:
    """Fill the day_week_context columns on every trade of the day (reporting only - never read by a decision):
    dw_tags, week_idx, adr5_prev, adr_prev, adr_fill, adr5_today (the whole day's range, POST-HOC: a look-ahead column for the study reports, no decision reads it), taken_3d /
    prev3_taken, entry_array_tf, seasonal, eve_draw_*."""
    P = getattr(ctx, "dplan", None)
    if P is None or not trades:
        return
    d = ctx.day
    hist = getattr(ctx, "hist", [])
    a5 = P.info.get("adr5_prev")
    base_tags = set(P.tags)
    if p.sd_week_skip == "off" and not p.sd_no_hold:
        base_tags.discard("sd_week")
    if P.info.get("sunday") and p.sunday_scenario != "off":
        base_tags.add("sunday_" + sunday_state(ctx, p, hist))
    tl = org_tell(ctx, p, len(ctx.t) - 1) if p.org_tell != "off" else 0
    if tl:
        base_tags.add("org_tell_up" if tl > 0 else "org_tell_dn")
    if p.consol_day_rules != "off":
        base_tags |= {"consol_" + x for x in P.info.get("consol_preds", [])}
    ed = eve_draw(ctx, p, hist) if p.eve_draw else None
    seas = P.info.get("seasonal", "")
    rng_day = float(ctx.h[ctx.start:].max() - ctx.l[ctx.start:].min())
    for tr in trades:
        tags = set(base_tags)
        k = ctx.idx.get_indexer([tr.entry_time])[0]
        s = 1 if tr.side == "long" else -1
        tr.week_idx = P.info.get("week_idx", 0)
        if p.journal_tags and a5:
            tr.adr5_prev = round(a5, 4)
            tr.adr_prev = None if P.info.get("adr_prev") is None else round(P.info["adr_prev"], 4)
            tr.adr5_today = round(rng_day / a5, 4)
            if k >= 0:
                tr.adr_fill = round(float(ctx.h[ctx.start:k + 1].max() - ctx.l[ctx.start:k + 1].min()) / a5, 4)
        if p.journal_tags and k >= 0:
            names = []                                    # the last three completed sessions' highs / lows (all of them, also those a
            hi_k, lo_k = ctx.h[ctx.start:k + 1].max(), ctx.l[ctx.start:k + 1].min()      # session in between already took) vs today to the fill
            for j_ in (1, 2, 3):
                if len(hist) >= j_:
                    ph, pl = _hl(hist[-j_])
                    if hi_k >= ph:
                        names.append(f"pdh{j_}")
                    if lo_k <= pl:
                        names.append(f"pdl{j_}")
            tr.prev3_taken = "|".join(names)
            tr.taken_3d = len(names)
            tr.entry_array_tf = entry_array_tf(ctx, tr, p, k)
        if seas:
            tr.seasonal = seasonal_with_htf(seas, ctx, k)
        if ed is not None:
            tr.eve_draw_px, tr.eve_draw_side, tr.eve_draw_done = ed["px"], ed["side"], ed["done"]
        if k >= 0:
            tags |= _entry_tags(ctx, p, P, d, s, k, tr)
            from . import dwc1 as _D1
            tags |= _D1.entry_tags(ctx, p, P, k)         # caption-gap pass day_week_context#1/3
            from . import dwc2 as _D2
            tags |= _D2.entry_tags(ctx, p, P, k)         # caption-gap pass day_week_context#2/3
        if P.info.get("wk_profile"):
            tr.wk_profile = P.info["wk_profile"]
        tr.dw_tags = "|".join(sorted(tags))


def entry_array_tf(ctx, tr, p, k: int) -> str:
    """X16 / X16d the timeframe of the entry array: the chart timeframe ("5m") plus, when the entry price sat inside a
    valid array of the trade's side on a higher timeframe, the highest one ("5m>4h"; Confluence.at)."""
    base = f"{ctx.tf}m"
    cf = getattr(ctx, "conf", None)
    if cf is None:
        return base
    try:
        from .confluence import TFS
        s = 1 if tr.side == "long" else -1
        tfs = cf.at(ctx.idx[k], tr.entry, s)
        hi = max((TFS.index(x) for x in tfs), default=-1)
        if hi >= 0 and TFS[hi] != base:
            return f"{base}>{TFS[hi]}"
    except Exception:
        pass
    return base


def seasonal_with_htf(seas: str, ctx, k: int) -> str:
    """B23: the HTF trend must agree: htf_agree / htf_against from the htf table's draw column (known from 09:30)."""
    row = getattr(ctx, "bias_row", None)
    m = seas.split(":")[0]
    if row is None or m not in ("bull", "bear") or k < 0 or ctx.t[k] < 570:
        return seas
    try:
        b = int(row["draw"])
    except Exception:
        return seas
    if not b:
        return seas
    return seas + (":htf_agree" if (b > 0) == (m == "bull") else ":htf_against")


def _entry_tags(ctx, p, P: DayPlan, d: date, s: int, k: int, tr=None) -> set:
    """Per-trade tags from the day's bars through the entry bar k (reporting only; the 'tag' modes of the switches):
      mon_wed_extreme / thu_fri_break "tag"   mw_break_up / mw_break_dn (+ thu_reversal), thu_fri_break_with / _against
                                              (the trade's side against the side of the break made by the entry bar)
      org_bias_gap "tag"                      org_gap_up / org_gap_dn, org_gap_repriced, org_bias_up / org_bias_dn,
                                              org_bias_with_gap / org_bias_against_gap (AM entries; the htf row from 09:30)
      tue_week_extreme "tag"                  tue_draw_up / tue_draw_dn, tue_with_draw / tue_against_draw
      tue_off_monday "tag" / "filter"         off_ref_swept / off_ref_not_swept (the order's sweep took the reference
                                              day's low / high)"""
    t = set()
    mw = P.info.get("mw")
    if mw and (p.mon_wed_extreme != "off" or p.thu_fri_break != "off"):
        hh, ll = mw
        up = bool(ctx.h[ctx.start:k + 1].max() > hh)
        dn = bool(ctx.l[ctx.start:k + 1].min() < ll)
        if p.mon_wed_extreme != "off":
            if up:
                t.add("mw_break_up")
            if dn:
                t.add("mw_break_dn")
            # N10 / N10.3 a Thursday reversal: the Mon-Wed extreme was swept and the trade fades the sweep
            if d.weekday() == 3 and ((up and s < 0) or (dn and s > 0)):
                t.add("thu_reversal")
        if p.thu_fri_break != "off" and up != dn:
            t.add("thu_fri_break_up" if up else "thu_fri_break_dn")
            t.add("thu_fri_break_with" if s == (1 if up else -1) else "thu_fri_break_against")
    if p.org_bias_gap != "off" and ctx.t[k] >= 570 and ctx.t[k] < 720:
        gd, rep = org_gap_state(ctx, p, k)
        b = _bias_side(ctx, p, k)
        if gd:
            t.add("org_gap_up" if gd > 0 else "org_gap_dn")
            if rep:
                t.add("org_gap_repriced")
        if b:
            t.add("org_bias_up" if b > 0 else "org_bias_dn")
            if gd:
                t.add("org_bias_with_gap" if b == gd else "org_bias_against_gap")
    if p.tue_week_extreme != "off" and d.weekday() == 1 and ctx.t[k] >= 570:
        from .entries import bias_row_known
        row = bias_row_known(ctx, k)
        try:
            b = 0 if row is None else int(row["draw"])
        except Exception:
            b = 0
        if b:
            t.add("tue_draw_up" if b > 0 else "tue_draw_dn")
            t.add("tue_with_draw" if s == b else "tue_against_draw")
    ref = P.info.get("off_ref")
    if p.tue_off_monday != "off" and ref is not None and tr is not None and getattr(tr, "ext_px", None) is not None:
        hi, lo = ref
        took = tr.ext_px <= lo if s > 0 else tr.ext_px >= hi
        t.add("off_ref_swept" if took else "off_ref_not_swept")
    return t


# --------------------------------------------------------------------------------------------------------------
# reporting helpers: X16a day_ranges, X16c weekly_extremes, T14 week statistics
# --------------------------------------------------------------------------------------------------------------

def session_label(minute: int) -> str:
    """X16c kill-zone label of a clock minute (America/New_York)."""
    if minute >= 18 * 60 or minute < 120:
        return "asia"
    if minute < 300:
        return "london"
    if minute < 510:
        return "pre_ny"
    if minute < 720:
        return "ny_am"
    if minute < 810:
        return "lunch"
    if minute < 975:
        return "ny_pm"
    return "close"


def trading_label(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """The trading date of each bar (the evening reopen belongs to the next trading day)."""
    return (index + pd.Timedelta(hours=7)).normalize().tz_localize(None)


def weekly_extremes(df: pd.DataFrame) -> pd.DataFrame:
    """X16c / T14 for every Monday-Friday week of the all-hours bars `df`: the weekday and the kill-zone session
    that made the week's high and low (Sunday-evening bars count to Monday). Columns: week, high, high_day (0 =
    Monday), high_session, low, low_day, low_session, range, plus the Monday-Wednesday split (mon_wed_high /
    mon_wed_low: the extreme formed Monday to Wednesday). Uses whole weeks: reporting only."""
    lab = trading_label(df.index)
    wk = pd.Series(lab.to_period("W-FRI"), index=df.index)
    wd = pd.Series(lab.dayofweek, index=df.index)
    m = pd.Series(df.index.hour * 60 + df.index.minute, index=df.index)
    rows = []
    for key, g in df.groupby(wk.values):
        if len(g) < 10:
            continue
        ih, il = g.high.idxmax(), g.low.idxmin()
        rows.append(dict(week=str(key), high=float(g.high.max()), high_day=int(wd[ih]), high_session=session_label(int(m[ih])),
                         low=float(g.low.min()), low_day=int(wd[il]), low_session=session_label(int(m[il])),
                         range=float(g.high.max() - g.low.min()),
                         first_open=float(g.open.iloc[0]), last_close=float(g.close.iloc[-1]),
                         high_ts=ih, low_ts=il))
    out = pd.DataFrame(rows)
    if len(out):
        out["mon_wed_high"] = out.high_day <= 2
        out["mon_wed_low"] = out.low_day <= 2
        out["bullish"] = out.last_close > out.first_open
    return out


def day_ranges(frames: list, adr_n: int = 5, eth: dict | None = None) -> pd.DataFrame:
    """X16a one row per completed session: date, weekday, range, ADR5 of the five sessions before it, the ratio
    (range / ADR5), the high / low and the close position (0 = low .. 1 = high). Written by study_week as the
    day_ranges CSV."""
    rows = []
    rng = [float(f.high.max() - f.low.min()) for f in frames]
    for j, f in enumerate(frames):
        a = float(np.mean(rng[j - adr_n:j])) if j >= adr_n else None
        h, l = _hl(f)
        c = float(f.close.iloc[-1])
        rows.append(dict(date=f.index[0].date(), weekday=f.index[0].weekday(), range=rng[j], adr5=a,
                         ratio=None if not a else rng[j] / a, high=h, low=l,
                         close_pos=None if h <= l else (c - l) / (h - l)))
    return pd.DataFrame(rows)
