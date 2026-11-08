"""Caption-gap pass, package day_week_context#1/3 (digests/rulebook_gaps/bias_htf_intermarket.md items 11, 55, 56, 60-63, 72, 80, 81, 97, 159-163, 187, 191, 194, 210, 211 and
day_selection_news_calendar.md items 9, 34-44, 47; build_log.md).

Calendar rules (the landmine Monday, the holiday-week NFP override, summer / August / election / holiday-eve cases), the seasonal engine (windows, intramonth direction, result, strength rank,
weekly tone, regime, macro override, failed windows), the week templates (NWOG open scenarios, one-sided week Thursday / Friday, TGIF preconditions, the Monday high-of-week profile, the failed weekly
push range, the weekly profile classifier, the intra-week reversal watch, the monthly overdue tag) and the day-type rules (post-holiday AM symmetry, intraday and weekly seek-and-destroy, the
objective-before-lunch share, the day profile). Everything reads completed daily candles (`hist`), the calendar, or today's bars that have closed (index <= the caller's bar i); the whole-day causal
arrays (sd_intraday) are used only at indexes <= i. Thresholds the sources never give are marked [our interpretation]. Every rule is a Params switch (off by default).

Pieces
  plan_rules     the DayPlan part (tags, blocks, floors, side blocks, scalp flags, info)                              (daycontext.plan tail)
  gate           per-bar gates (post-holiday symmetry, sd_intraday rules)                                             (daycontext.gate, before the bias_day gate)
  side_ok        side filters (nwog templates, objective_done_pm, day_profile_gate)                                   (daycontext.side_ok)
  order_ok       per-order filters (thu_strict, fri_one_sided, mon_how, objective_frac_gate)                          (daycontext.order_ok)
  scalp_now      dynamic scalp (sd_intraday rules)                                                                    (daycontext.scalp_now)
  size_mult / adds_off   August light, holiday weeks, season_quality "size"                                           (daycontext.day_risk, entries.adds_blocked)
  calendar_block skip_election, summer_off, august_mode skip                                                         (strategy.blocked)
  tgif_strict_ok the TGIF preconditions                                                                              (strategy.day_context)
  entry_tags     per-trade tags (nwog fill status, mon_how, sd_intraday, one-sided week ...)                          (daycontext.stamp)
  lock_filter    macro-risk week: session pools only                                                                  (strategy.mark_levels)
  day_params     iw_no_measured: the measured-move rung switches off                                                 (strategy._run_day_once)
"""
from __future__ import annotations

import csv
import os
from collections import Counter
from datetime import date, timedelta
from functools import lru_cache

import numpy as np
import pandas as pd

from mentorship.calendar import events
from . import calendar as CAL
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
    return ctx.__dict__.setdefault("_dwc1", {})


# --------------------------------------------------------------------------------------------------------------
# small helpers on completed candles
# --------------------------------------------------------------------------------------------------------------

def _bars(frames) -> tuple:
    """(open, high, low, close) arrays of a list of session frames."""
    o = np.array([float(x.open.iloc[0]) for x in frames])
    c = np.array([float(x.close.iloc[-1]) for x in frames])
    h = np.array([float(x.high.max()) for x in frames])
    l = np.array([float(x.low.min()) for x in frames])
    return o, h, l, c


def _week_bars(hist, d: date) -> list:
    """(o, h, l, c, first date) of the COMPLETED Monday-Friday weeks before the week of d, oldest first."""
    DW = _DW()
    out = []
    for key, fr in DW._weeks([x for x in hist if x.index[0].date() < d]):
        if key == DW._week_key(d):
            continue
        o, h, l, c = _bars(fr)
        out.append((float(o[0]), float(h.max()), float(l.min()), float(c[-1]), fr[0].index[0].date()))
    return out


def _this_week(hist, d: date) -> list:
    """The completed sessions of d's own week (before d)."""
    DW = _DW()
    return [x for x in hist if DW._week_key(x.index[0].date()) == DW._week_key(d) and x.index[0].date() < d]


def weekly_state(hist, d: date) -> int:
    """The weekly tone from COMPLETED weeks (B8c wk_dc, the same definition as htf._flip): +1 after a week closing above the high of the last down-close week, -1 after one closing below the
    low of the last up-close week, else the standing state (0 until the first)."""
    state, dn_hi, up_lo = 0, None, None
    for o, h, l, c, _d in _week_bars(hist, d):
        if dn_hi is not None and c > dn_hi:
            state = 1
        elif up_lo is not None and c < up_lo:
            state = -1
        if c < o:
            dn_hi = h
        elif c > o:
            up_lo = l
    return state


def flip_state(ctx, hist=None, d: date | None = None) -> int:
    """The daily bias flip state known before the session (htf table column `flip`); with no table row the weekly tone from the completed weeks."""
    row = getattr(ctx, "bias_row", None)
    try:
        v = row["flip"]
        if v == v:
            return int(v)
    except Exception:
        pass
    if hist is not None and d is not None:
        return weekly_state(hist, d)
    return 0


def _adr5(ctx, p):
    P = getattr(ctx, "dplan", None)
    if P is not None and P.info.get("adr5_prev"):
        return P.info["adr5_prev"]
    return _DW()._adr(ctx, p)


def _alive_zones(frames, kind: str, end: int | None = None) -> list:
    """Daily FVGs of `kind` ("bull" / "bear") among the sessions `frames[:end]` not closed through by a later close of those sessions."""
    fr = frames if end is None else frames[:end]
    if len(fr) < 3:
        return []
    o, h, l, c = _bars(fr)
    out = []
    for z in L.fvgs(h, l, o, c):
        if z.kind != kind:
            continue
        after = c[z.i + 1:]
        if len(after) and ((kind == "bull" and after.min() < z.bottom) or (kind == "bear" and after.max() > z.top)):
            continue
        out.append(z)
    return out


def _nwog(ctx, hist, d: date, p, eth):
    """(Friday close, the week's first open) of d's week - the NWOG edges; None when the week's open is unknown (no evening data on a Monday)."""
    c = _cache(ctx)
    if "nwog" not in c:
        DW = _DW()
        lv = DW._week_objective_levels(ctx, hist, d, p, eth)
        nw = lv.get("_nwog")
        ev = getattr(ctx, "eve", None)
        if nw is None and ev and CAL.week_day_index(d) == 1:           # an unchanged open (no gap) is still the week's open: the 'open unchanged' template
            prior = [x for x in hist if x.index[0].date() < d and DW._week_key(x.index[0].date()) != DW._week_key(d)]
            if prior:
                nw = (DW._prior_close(prior[-1], eth), float(ev[0]))
        c["nwog"] = nw
    return c["nwog"]


# --------------------------------------------------------------------------------------------------------------
# macro-risk flags (BH-mixed-HTF-intraday-only 068 ~04:27; X3-seasonal-macro-override cc05_011 ~00:22:19)
# --------------------------------------------------------------------------------------------------------------

@lru_cache(maxsize=32)
def _flags_cached(spec, _mtime=None) -> tuple:
    rows = []
    if isinstance(spec, str):
        with open(spec, newline="", encoding="utf8") as f:
            for r in csv.DictReader(f):
                k = r.get("week") or r.get("date")
                if k:
                    rows.append((k.strip(), (r.get("direction") or "0").strip()))
    else:
        for x in spec:
            k, _, dr = str(x).partition(":")
            rows.append((k.strip(), dr.strip() or "0"))
    out = {}
    for k, dr in rows:
        day = date.fromisoformat(k[:10])
        mon = day - timedelta(days=day.weekday())
        try:
            v = int(float(dr))
        except ValueError:
            v = {"up": 1, "bull": 1, "risk_on": 1, "down": -1, "bear": -1, "risk_off": -1}.get(dr.lower(), 0)
        out[mon] = (v > 0) - (v < 0)
    return tuple(sorted(out.items()))


def macro_flags(spec) -> dict:
    """{Monday of the flagged week: direction (+1 / -1 / 0 = uncertainty only)}; `spec` is a CSV path (columns week, direction) or a tuple of "YYYY-MM-DD[:dir]"; "" / () = none."""
    if not spec:
        return {}
    if isinstance(spec, str):
        try:
            mt = os.path.getmtime(spec)                 # the cache is keyed on the file's mtime: an edited CSV is re-read
        except OSError:
            mt = None
        return dict(_flags_cached(spec, mt))
    return dict(_flags_cached(tuple(spec)))


def macro_week(p, d: date):
    """None when d's week is not flagged, else the flagged direction (0 = no direction given)."""
    return macro_flags(p.macro_risk_dates).get(d - timedelta(days=d.weekday()))


# --------------------------------------------------------------------------------------------------------------
# the seasonal engine (items 60-62, 159-163, 160)
# --------------------------------------------------------------------------------------------------------------

def result_of(net: float, direction: int, adr5: float, n: int, k: float) -> str:
    """BH-B23-seasonal-failure: the window's net move (close - open) against the yardstick k x ADR5 x n / 5: "counter" when the move AGAINST the window's direction exceeds it, "consol" when
    |net| is under half of it, else "worked" [our interpretation]."""
    unit = k * adr5 * n / 5.0
    against = -net * direction
    if against > unit:
        return "counter"
    if abs(net) < 0.5 * unit:
        return "consol"
    return "worked"


def _closes_before(closes: dict, keys: list, day: date):
    """The last close on or before `day` in the sorted date list `keys`, else None."""
    import bisect
    j = bisect.bisect_right(keys, day) - 1
    return closes[keys[j]] if j >= 0 else None


def composite(closes: dict, year: int) -> dict:
    """X3-seasonal-strength-grading (cc05_010): the composite of each window from the years BEFORE `year` only: the mean % move (close before the window to its last close). Returns
    {window name: mean % move} (windows without data are missing)."""
    keys = sorted(closes)
    out = {}
    for name, _dr, a, b in CAL.SEASON_WINDOWS:
        mv = []
        for y in range(min(k.year for k in keys) if keys else year, year):
            first = date(y - 1 if a > b else y, a[0], a[1])
            last = date(y, b[0], b[1])
            if last >= date(year, 1, 1):
                continue
            c0 = _closes_before(closes, keys, first - timedelta(days=1))
            c1 = _closes_before(closes, keys, last)
            if c0 and c1 and keys and keys[0] <= first:
                mv.append((c1 - c0) / c0 * 100.0)
        if mv:
            out[name] = float(np.mean(mv))
    return out


def rank_of(comp: dict, name: str):
    """The window's rank in [0, 1] by the size |composite| among the windows with data (1 = the largest swing); None without data."""
    if name not in comp:
        return None
    ordered = sorted(comp, key=lambda k: abs(comp[k]))
    if len(ordered) == 1:
        return 1.0
    return ordered.index(name) / (len(ordered) - 1)


def _closes_for(ctx, hist) -> dict:
    da = getattr(ctx, "daily_all", None)
    if da:
        return da
    return {x.index[0].date(): float(x.close.iloc[-1]) for x in hist}


def window_rank(ctx, hist, name: str, d: date):
    c = _cache(ctx)
    key = ("comp", d.year)
    if key not in c:
        c[key] = composite({k: v for k, v in _closes_for(ctx, hist).items() if k.year < d.year}, d.year)
    return rank_of(c[key], name)


def trend252(ctx, hist, d: date) -> int:
    """The 252-session trend (B22): the sign of the last completed close minus the close 252 sessions before it; 0 when the history is too short."""
    cl = _closes_for(ctx, [x for x in hist if x.index[0].date() < d])
    keys = sorted(k for k in cl if k < d)
    if len(keys) < 253:
        return 0
    return int(np.sign(cl[keys[-1]] - cl[keys[-253]]))


def ended_windows(hist, d: date, p, a5) -> list:
    """The windows that ended within the last 20 completed sessions before d: [(name, direction, result, failed)] - result from result_of, failed "up" / "dn" (X3-seasonal-consolidation-breakout:
    "consol" then a daily close beyond the window's range within 10 sessions after it ended)."""
    out = []
    done = [x for x in hist if x.index[0].date() < d]
    for name, dr, _a, _b in CAL.SEASON_WINDOWS:
        inst = CAL.window_instance(name, d)
        if inst is None:
            continue
        first, last = inst
        after = [x for x in done if x.index[0].date() > last]
        if len(after) + 1 > 20 or (d - last).days > 45:
            continue
        win = [x for x in done if first <= x.index[0].date() <= last]
        if len(win) < 3:
            continue
        o, h, l, c = _bars(win)
        net = float(c[-1] - o[0])
        a = float(np.mean(h[-5:] - l[-5:]))
        res = result_of(net, dr, a, len(win), p.season_move_adr)
        failed = ""
        if res == "consol":
            hi, lo = float(h.max()), float(l.min())
            for x in after[:10]:
                cx = float(x.close.iloc[-1])
                if dr < 0 and cx > hi:
                    failed = "up"
                    break
                if dr > 0 and cx < lo:
                    failed = "dn"
                    break
        out.append((name, dr, res, failed))
    return out


def season_info(ctx, d: date, p, hist, a5) -> dict:
    """The day's seasonal reading: tags, the primary window direction `wdir`, whether the window acts (`acts`), the intramonth direction and the failed-window side."""
    tags = CAL.season_tags(d)
    wins = [n for n in tags if n.startswith("win_")]
    macro = macro_week(p, d)
    dirs = {n: dr for n, dr, _a, _b in CAL.SEASON_WINDOWS}
    drop = set()
    for n in wins:
        if p.season_min_rank > 0:
            rk = window_rank(ctx, hist, n, d)
            if rk is not None and rk < p.season_min_rank:
                drop.add(n)                                  # X3-seasonal-strength-grading: below the rank cut
                hit("season_rank_drop")
        if macro and dirs[n] == -macro:
            drop.add(n)                                      # X3-seasonal-macro-override: a flagged dominant macro direction disables the opposing window
            hit("season_macro_drop")
    tags -= drop
    prim = next((n for n, dr, _a, _b in CAL.SEASON_WINDOWS if n in tags), None)
    wdir = dirs.get(prim, 0) if prim else 0
    if prim and p.season_poised:
        from . import bh3e as _B3                            # caption-gap B23-market-poised-first (bias_htf#3/7; cc10_016 ~1:51): a seasonal window acts only when the broad market is poised in its direction
        if _B3.window_poised(ctx, wdir) is False:
            tags.discard(prim)
            tags.add("season_not_poised")
            prim, wdir = None, 0
            hit("season_not_poised")
    qual = False
    if prim and p.season_qualified:
        from . import bh3e as _B3                            # caption-gap X3-seasonal-quarterly-qualifier (bias_htf#3/7; cc05_007 ~8:04): any ONE qualifier (the daily index SMT, the notes / dollar regime)
        qual = _B3.season_qualified(ctx, wdir)
        if qual:
            tags.add("season_qualified")
            hit("season_qualified")
    info = dict(tags=tags, prim=prim, wdir=wdir, acts=False, intra=CAL.season_dir(d), failed="", qualified=qual)
    if prim:
        ws = weekly_state(hist, d) or 0
        if ws and ws == wdir:
            tags.add("season_win_prime")
            prime = True
        else:
            prime = False
            if ws:
                tags.add("season_win_minor")                 # BH-X3-seasonal-trend-condition: the window against the weekly tone gives only a minor move
        tr = trend252(ctx, hist, d)
        regime_ok = not (tr and tr != wdir)
        if not regime_ok:
            tags.add("season_pullback")                      # X3-seasonal-regime-picks-window: the opposing window is the expected pullback
        info["acts"] = bool(prime and regime_ok)
    for nm, dr, res, failed in ended_windows(hist, d, p, a5):
        tags.add(f"sr_{nm}_{res}")
        tags.add(f"season_result_{res}")
        if failed:
            tags.add("season_failed_" + failed)
            info["failed"] = failed
    if info["intra"]:
        tags.add("season_intra_" + ("+1" if info["intra"] > 0 else "-1"))
    return info


# --------------------------------------------------------------------------------------------------------------
# weekly templates
# --------------------------------------------------------------------------------------------------------------

def one_sided_week(hist, d: date) -> int:
    """BH-N10-thursday-not-top-call (044 ~00:16:07) [our interpretation]: on a Thursday, +1 / -1 when Monday, Tuesday and Wednesday each closed beyond the PRIOR session's high (low) - a one-way
    algorithmic week; else 0."""
    if d.weekday() != 3:
        return 0
    wk = _this_week(hist, d)
    if len(wk) < 3 or wk[0].index[0].date().weekday() != 0:
        return 0
    prev = [x for x in hist if x.index[0].date() < wk[0].index[0].date()]
    if not prev:
        return 0
    seq = [prev[-1]] + wk[:3]
    up = all(float(seq[k].close.iloc[-1]) > float(seq[k - 1].high.max()) for k in (1, 2, 3))
    dn = all(float(seq[k].close.iloc[-1]) < float(seq[k - 1].low.min()) for k in (1, 2, 3))
    return 1 if up else (-1 if dn else 0)


def fri_dir(hist, d: date) -> int:
    """BH-B17-friday-after-one-sided-week (045 ~00:11:00): +1 / -1 when Tuesday, Wednesday and Thursday each closed above (below) the prior close; the pre-open high above Thursday's
    high is checked in the gate (it needs the overnight bars)."""
    if d.weekday() != 4:
        return 0
    wk = _this_week(hist, d)
    if len(wk) < 4:
        return 0
    cl = [float(x.close.iloc[-1]) for x in wk[-4:]]
    df_ = np.sign(np.diff(cl))
    if len(df_) == 3 and abs(df_.sum()) == 3:
        return int(df_[0])
    return 0


def tgif_strict_ok(hist, day: date, p, eth, conf, short: bool) -> bool:
    """BH-M14-TGIF-preconditions (066 ~00:15:52): the tgif tag holds only when (1) the week traded into a weekly or monthly array (a bear array at the week's high for the bullish week, i.e.
    tgif_short; a bull array at the low for tgif_long), (2) the prior tgif_weeks weeks each closed up (down) AND beyond their midpoint, (3) Monday to Thursday each closed above (below) the prior
    close. Completed sessions only."""
    wk = _this_week(hist, day)
    prev = [x for x in hist if x.index[0].date() < (wk[0].index[0].date() if wk else day)]
    if len(wk) < 4 or not prev:
        return False
    sgn = 1 if short else -1                                   # tgif_short = a bullish week
    cl = [float(prev[-1].close.iloc[-1])] + [float(x.close.iloc[-1]) for x in wk[:4]]
    if not all(sgn * (cl[k] - cl[k - 1]) > 0 for k in range(1, 5)):
        return False
    wb = _week_bars(hist, day)
    if len(wb) < p.tgif_weeks:
        return False
    for o, h, l, c, _d in wb[-p.tgif_weeks:]:
        mid = (h + l) / 2
        if not (sgn * (c - o) > 0 and sgn * (c - mid) > 0):
            return False
    if conf is None:
        return False
    hi, lo = float(max(x.high.max() for x in wk)), float(min(x.low.min() for x in wk))
    ext, kind = (hi, -1) if short else (lo, 1)
    when = pd.Timestamp(wk[-1].index[0].date(), tz=wk[-1].index.tz) + pd.Timedelta(hours=9, minutes=30)
    return bool(_DW()._array_touch(conf, when, ext, kind, ("W", "M"), conf.tol))


def monthly_bars(hist, d: date) -> list:
    """(o, h, l, c) of the completed calendar months before d's month from the sessions in `hist` (the oldest, usually partial, month dropped)."""
    g: dict = {}
    for x in hist:
        k = x.index[0].date()
        if (k.year, k.month) < (d.year, d.month):
            g.setdefault((k.year, k.month), []).append(x)
    keys = sorted(g)
    if len(keys) > 1:
        keys = keys[1:]
    out = []
    for k in keys:
        o, h, l, c = _bars(g[k])
        out.append((float(o[0]), float(h.max()), float(l.min()), float(c[-1])))
    return out


def mo_overdue(hist, d: date) -> int:
    """B11-monthly-five-up-closes (078 ~00:16:48): -1 (a down month is overdue) when the last 5 or more completed months each closed up and the last one traded into a monthly bear array
    (a bear FVG formed before it, not closed through); +1 for the mirror. 0 otherwise [our interpretation of the array: a monthly FVG]."""
    mb = monthly_bars(hist, d)
    n = len(mb)
    if n < 6:
        return 0
    o = np.array([m[0] for m in mb]); h = np.array([m[1] for m in mb]); l = np.array([m[2] for m in mb]); c = np.array([m[3] for m in mb])
    k = 0
    while k < n and c[n - 1 - k] > o[n - 1 - k]:
        k += 1
    if k >= 5:
        for z in L.fvgs(h, l, o, c):
            if z.kind == "bear" and z.i < n - 1 and not (c[z.i + 1:n - 1] > z.top).any() and h[-1] >= z.bottom:
                return -1
    k = 0
    while k < n and c[n - 1 - k] < o[n - 1 - k]:
        k += 1
    if k >= 5:
        for z in L.fvgs(h, l, o, c):
            if z.kind == "bull" and z.i < n - 1 and not (c[z.i + 1:n - 1] < z.bottom).any() and l[-1] <= z.top:
                return 1
    return 0


def mon_how_state(ctx, hist, d: date, p):
    """NEW-monday-high-of-week-profile (078 ~01:07:29): Tuesday-Thursday, flip state -1, Monday's high traded into a daily bear array (formed before Monday, not closed through) and Monday
    closed below its low (mon_how_edge "low", or the CE) -> (-1, Monday's high); the mirror gives (+1, Monday's low). None when the tag does not hold; it is cleared by a completed session of
    the week trading above Monday's high (below its low)."""
    if d.weekday() not in (1, 2, 3):
        return None
    wk = _this_week(hist, d)
    if not wk or wk[0].index[0].date().weekday() != 0:
        return None
    f = flip_state(ctx, hist, d)
    if not f:
        return None
    mon = wk[0]
    pre = [x for x in hist if x.index[0].date() < mon.index[0].date()]
    mh, ml, mc = float(mon.high.max()), float(mon.low.min()), float(mon.close.iloc[-1])
    if f < 0:
        for z in _alive_zones(pre, "bear"):
            edge = z.bottom if p.mon_how_edge == "low" else (z.top + z.bottom) / 2
            if mh >= z.bottom and mc < edge:
                if any(float(x.high.max()) > mh for x in wk[1:]):
                    return None
                return -1, mh
    else:
        for z in _alive_zones(pre, "bull"):
            edge = z.top if p.mon_how_edge == "low" else (z.top + z.bottom) / 2
            if ml <= z.top and mc > edge:
                if any(float(x.low.min()) < ml for x in wk[1:]):
                    return None
                return 1, ml
    return None


def push_range_frame(hist, d: date):
    """NEW-failed-weekly-push-range (102 ~00:11:29): last week traded to (or slightly through) the CE of the upper wick of the week before it, closed under that CE and did not exceed that week's
    high: the frame (last week's low, the wick's 75 % level) - the mirror gives (the lower wick's 75 % level, last week's high). Cleared by a completed session of this week closing beyond the 75 %
    level. Returns (lo, hi, up) or None [our interpretation: the wick of the week two weeks back; 'slightly through' = up to the wick's high]."""
    wb = _week_bars(hist, d)
    if len(wb) < 2:
        return None
    o2, h2, l2, c2, _ = wb[-2]
    o1, h1, l1, c1, _ = wb[-1]
    this = _this_week(hist, d)
    top2 = max(o2, c2)
    wick = h2 - top2
    if wick > 0:
        ce, q75 = top2 + wick / 2, top2 + 0.75 * wick
        if h1 >= ce - 0.1 * wick and h1 < h2 and c1 < ce:
            if any(float(x.close.iloc[-1]) > q75 for x in this):
                return None
            return l1, q75, True
    bot2 = min(o2, c2)
    wick = bot2 - l2
    if wick > 0:
        ce, q75 = bot2 - wick / 2, bot2 - 0.75 * wick
        if l1 <= ce + 0.1 * wick and l1 > l2 and c1 > ce:
            if any(float(x.close.iloc[-1]) < q75 for x in this):
                return None
            return q75, h1, False
    return None


def _touched(frames, zones, kind: str) -> list:
    """For each frame the first zone of `kind` it traded into (low <= top and high >= bottom), else None."""
    out = []
    for x in frames:
        hi, lo = float(x.high.max()), float(x.low.min())
        out.append(next((z for z in zones if lo <= z.top and hi >= z.bottom), None))
    return out


def wk_profile_name(ctx, hist, d: date, p, a5) -> str:
    """M17-weekly-profiles-selection (cc07_002 ~00:00:50): the weekly bias first (the weekly tone, else the flip state), then only the profiles in that direction, from the completed sessions of the
    week: classic_tue_low / classic_tue_high (Mon / Tue traded into a daily array of the bias side), wed_low / wed_high (no array by Tuesday, one on Wednesday), consol_thu_reversal (Mon-Wed
    inside ADR5, no array), mon_how (item 81). "none" otherwise."""
    bias = weekly_state(hist, d) or flip_state(ctx, hist, d)
    wk = _this_week(hist, d)
    if not bias or not wk or wk[0].index[0].date().weekday() != 0:
        return "none"
    mh = mon_how_state(ctx, hist, d, p)
    if mh is not None and mh[0] == bias:                       # the bearish Monday high of a bearish week / the bullish mirror
        return "mon_how"
    pre = [x for x in hist if x.index[0].date() < wk[0].index[0].date()]
    zones = _alive_zones(pre, "bull" if bias > 0 else "bear")
    if bias > 0:
        t = _touched(wk, zones, "bull")
    else:
        t = _touched(wk, zones, "bear")
    side = "low" if bias > 0 else "high"
    if any(t[:2]):
        return "classic_tue_" + side
    if len(wk) >= 3 and not any(t[:2]) and t[2] is not None:
        return "wed_" + side
    if len(wk) >= 3 and not any(t[:3]) and a5:
        o, h, l, c = _bars(wk[:3])
        if float(h.max() - l.min()) <= a5:
            return "consol_thu_reversal"
    return "none"


def weekly_fvg_fresh_inside(hist, d: date) -> bool:
    """BH-mixed-HTF-intraday-only (068 ~04:27): the last completed week closed a weekly FVG (it is the third candle) and the prior close sits inside it."""
    wb = _week_bars(hist, d)
    if len(wb) < 3 or not hist:
        return False
    o = np.array([w[0] for w in wb]); h = np.array([w[1] for w in wb]); l = np.array([w[2] for w in wb]); c = np.array([w[3] for w in wb])
    px = float(hist[-1].close.iloc[-1])
    return any(z.i == len(wb) - 1 and z.bottom <= px <= z.top for z in L.fvgs(h, l, o, c))


def sd_week_detected(hist, d: date, p, a5, conf=None) -> tuple:
    """N8-seek-destroy-week (cc07_002 ~00:07:57; cc07_003 ~00:33:45): (flag, released). Evaluated on Wednesday (Monday-Tuesday completed) and Thursday (Monday-Wednesday) and kept for the rest of
    the week: the week's running high AND low were both exceeded (each time by <= sd_shallow_frac x ADR5, summed per side as the largest single exceedance) with no daily close beyond the running
    extreme before it, and the week holds FOMC or NFP or the month is July / August. `released` = the week's extreme has touched a D / W array (sd_after_array)."""
    if d.weekday() < 2 or not a5:
        return False, False
    wk = _this_week(hist, d)
    if len(wk) < 2 or wk[0].index[0].date().weekday() != 0:
        return False, False
    cal = d.month in (7, 8) or any("fomc" in events(x) for x in CAL.week_dates(d)) or CAL.nfp_date(d) is not None
    if not cal:
        return False, False
    flag = False
    for upto in (2, 3):                                           # Wednesday evaluates Mon-Tue, Thursday Mon-Wed; Friday keeps either
        if d.weekday() == 2 and upto == 3:
            break
        seg = wk[:upto]
        if len(seg) < upto:
            continue
        rh, rl = float(seg[0].high.max()), float(seg[0].low.min())
        ex_h, ex_l, ok, hi_run, lo_run = 0.0, 0.0, True, False, False
        for x in seg[1:]:
            h_, l_, c_ = float(x.high.max()), float(x.low.min()), float(x.close.iloc[-1])
            if c_ > rh or c_ < rl:
                ok = False
                break
            if h_ > rh:
                ex_h, hi_run = max(ex_h, h_ - rh), True
            if l_ < rl:
                ex_l, lo_run = max(ex_l, rl - l_), True
            rh, rl = max(rh, h_), min(rl, l_)
        if ok and hi_run and lo_run and ex_h <= p.sd_shallow_frac * a5 and ex_l <= p.sd_shallow_frac * a5:
            flag = True
    rel = False
    if flag and p.sd_after_array and conf is not None:
        hi, lo = float(max(x.high.max() for x in wk)), float(min(x.low.min() for x in wk))
        when = pd.Timestamp(wk[-1].index[0].date(), tz=wk[-1].index.tz) + pd.Timedelta(hours=9, minutes=30)
        DW = _DW()
        rel = bool(DW._array_touch(conf, when, hi, -1, ("D", "W"), conf.tol) or DW._array_touch(conf, when, lo, 1, ("D", "W"), conf.tol))
    return flag, rel


# --------------------------------------------------------------------------------------------------------------
# the DayPlan part
# --------------------------------------------------------------------------------------------------------------

def plan_rules(P, ctx, d: date, p, hist, eth, a5, dt) -> None:
    """Everything of this package that is known before the session opens (completed candles and the calendar). `dt` = strategy.day_context's tags."""
    dt = dt or set()
    tg = P.tags
    DW = _DW()
    # N4-pre-cpi-monday-gap (028 ~00:34:21)
    if p.pre_cpi_mon != "off" and d.weekday() == 0 and "cpi" in events(CAL.next_trading_day(d)) and a5:
        nw = _nwog(ctx, hist, d, p, eth)
        if nw is not None:
            pc, so = nw
            big = abs(so - pc) > p.pre_cpi_gap_adr * a5
            tg.add("pre_cpi_mon_gap" if big else "pre_cpi_mon_small")
            P.info["pre_cpi_mon"] = (pc, so, big)
            if big and p.pre_cpi_mon == "gap":
                P.side_block("pre_cpi_mon", (-1,) if so < pc else (1,))     # the day reprices into the gap: gap down = longs only, gap up = shorts only
                hit("pre_cpi_gap_side")
            if not big and p.pre_cpi_mon == "skip_small":
                P.block(None, "pre_cpi_mon_small")
                hit("pre_cpi_small_skip")
    # N7-post-holiday-am-symmetry (090 ~02:07:38): the trigger is wider than the holiday - an abbreviated session or a large-range day before
    if p.post_holiday_am != "off":
        prev = CAL.prev_trading_day(d)
        trig = "post_holiday" in tg or bool(CAL.early_close_min(prev)) or "big_prev" in dt
        if trig:
            tg.add("post_holiday_trigger")
            if p.post_holiday_am == "skip":
                P.block(DW.NY_MORNING if p.post_holiday_pre_open else DW.NY_AM, "post_holiday_am")
            else:
                P.info["ph_symmetry"] = True
    # N7-august (079 ~00:10:14): the whole month
    if p.august_mode != "off" and d.month == 8:
        tg.add("august_mode")
        if p.august_mode == "skip":
            P.block(None, "august_mode")
        else:
            P.set_scalp("august_light")                              # one exit at the first target, no ladder / runners / adds
    # B23-seasonal-quality (079 ~00:24:47)
    if p.season_quality != "off":
        q = CAL.season_quality(d, p.season_autumn_start)
        tg.add("season_" + q)
        if d.month == 5:
            tg.add("season_may_overlap")                              # cc10_015 calls May-Oct less directional: the overlap with the Feb-May prime window
        P.info["season_quality"] = q
    # B23-daily-seasonal-review (cc05_012 ~00:13:05): the month list (existing seasonal_tag switch)
    if p.seasonal_tag:
        m0 = {"bull": 1, "bear": -1}.get(p.seasonal_map[d.month - 1], 0)
        m1 = {"bull": 1, "bear": -1}.get(p.seasonal_map[d.month % 12], 0)
        if m0:
            tg.add("season_dir_" + ("+1" if m0 > 0 else "-1"))
        if m1:
            tg.add("season_next_" + ("+1" if m1 > 0 else "-1"))
    # the seasonal engine
    if p.season_windows != "off":
        si = season_info(ctx, d, p, hist, a5)
        tg |= si["tags"]
        P.info["season"] = {k: v for k, v in si.items() if k != "tags"}
        if p.season_qualified and si.get("qualified"):
            P.side_block("season_qualified", (-si["wdir"],))        # caption-gap X3-seasonal-quarterly-qualifier (bias_htf#3/7): trades against a qualified window are blocked
            hit("season_qualified_gate")
        if p.season_gate:
            if si["intra"]:
                P.side_block("season_intramonth", (-si["intra"],))
                hit("season_intra_gate")
            if si["acts"]:
                P.side_block("season_window", (-si["wdir"],))
                hit("season_window_gate")
            if si["failed"]:
                P.side_block("season_failed", (-1,) if si["failed"] == "up" else (1,))
                hit("season_failed_gate")
    # B11-three-closes-day4 (cc08_006 ~00:02:07)
    if p.three_day_small and ("three_up" in dt or "three_down" in dt):
        tg.add("day4")
        P.set_scalp("three_day_small")
        hit("three_day_small")
    # N8-seek-destroy-week
    if p.sd_week_detect and (p.sd_week_skip != "off"):
        flag, rel = sd_week_detected(hist, d, p, a5, getattr(ctx, "conf", None))
        P.info["sd_week_detect"] = (flag, rel)
        P.info["sd_week"] = bool(flag and not rel)                  # the intraday seek_destroy context (sd_no_hold / sd_context_required) follows the detector, not the calendar-only _sd_week
        tg.discard("sd_week")
        P.blocks = [(s_, r_) for s_, r_ in P.blocks if r_ != "sd_week"]        # the calendar-only block of N8.6 sd_week_skip is replaced by the detector
        if flag:
            tg.add("sd_week")
            if rel:
                tg.add("sd_week_released")
            elif p.sd_week_skip == "skip":
                P.block(None, "sd_week")
                hit("sd_week_detect_skip")
    # N8-large-org-day: the AM may resume from big_day_am_resume
    if p.big_day_am_resume and any(r == "big_day_am" for _s, r in P.blocks):
        P.blocks = [(s, r) for s, r in P.blocks if r != "big_day_am"]
        P.floor(DW.AM_SACRIFICE, p.big_day_am_resume, "big_day_am")
        hit("big_day_am_resume")
    # BH-NWOG-week-open-scenarios (084; 028; 029; 103; 101)
    if p.nwog_templates != "off":
        _nwog_rules(P, ctx, d, p, hist, eth)
    # BH-N10-thursday-not-top-call (044 ~00:16:07)
    if d.weekday() == 3 and (p.thu_strict or p.fri_one_sided != "off"):
        os_ = one_sided_week(hist, d)
        if os_:
            tg.add("one_sided_week_up" if os_ > 0 else "one_sided_week_dn")
            P.info["one_sided"] = os_
    # BH-B17-friday-after-one-sided-week (045 ~00:11:00)
    if p.fri_one_sided != "off" and d.weekday() == 4:
        fd = fri_dir(hist, d)
        if fd:
            P.info["fri_dir"] = fd
    # BH-mixed-HTF-intraday-only (068 ~04:27)
    if p.macro_risk_dates and macro_week(p, d) is not None and weekly_fvg_fresh_inside(hist, d):
        tg.add("macro_risk_week")
        P.info["macro_scalp"] = True
        P.set_scalp("macro_risk_week")
        hit("macro_risk_week")
    # B11-monthly-five-up-closes (078 ~00:16:48)
    if p.mo_overdue:
        m = mo_overdue(hist, d)
        if m:
            tg.add("mo_overdue_dn" if m < 0 else "mo_overdue_up")
            hit("mo_overdue")
    # NEW-monday-high-of-week-profile (078 ~01:07:29)
    if p.mon_how != "off" or p.wk_profile != "off":
        mh = mon_how_state(ctx, hist, d, p)
        if mh is not None and p.mon_how != "off":
            tg.add("mon_how")
            P.info["mon_how"] = mh
    # NEW-failed-weekly-push-range (102 ~00:11:29)
    if p.wk_push_range:
        fr = push_range_frame(hist, d)
        if fr is not None:
            tg.add("wk_push_range")
            P.info["wk_range_frame"] = fr
            P.set_scalp("wk_push_range")                              # no trend / runner trades inside the range
            hit("wk_push_range")
    # M17-weekly-profiles-selection (cc07_002 ~00:00:50)
    if p.wk_profile != "off":
        nm = wk_profile_name(ctx, hist, d, p, a5)
        P.info["wk_profile"] = nm
        tg.add("wk_profile_" + nm)
    # B17-intraweek-reversal-profile (cc07_007 ~00:20:55)
    if p.iw_reversal_watch and d.weekday() in (2, 3) and a5:
        _iw_rules(P, ctx, d, p, hist, a5)
    # T13-day-profile-selection (cc10_013 ~00:04:22)
    if p.day_profile != "off" and a5 and hist:
        _profile_rules(P, ctx, d, p, hist, a5)


def _nwog_rules(P, ctx, d: date, p, hist, eth) -> None:
    nw = _nwog(ctx, hist, d, p, eth)
    f = flip_state(ctx, hist, d)
    if nw is None or not f or not hist:
        return
    pc, so = nw
    ce = (pc + so) / 2
    pl = float(hist[-1].low.min())
    kind = ""
    if f > 0 and so > pc:
        kind = "nwog_up_bull"
    elif f < 0 and so < pc:
        kind = "nwog_dn_bear"
    elif f < 0 and so >= pc:
        kind = "nwog_flat_bear"
    elif f > 0 and so < pl:
        kind = "nwog_below_wick_bull"
    if f > 0 and so < pl:
        P.tags.add("nwog_below_wick_bull")
        kind = kind or "nwog_below_wick_bull"
    if kind:
        P.tags.add(kind)
        hit(kind)
    info = dict(kind=kind, pc=pc, so=so, ce=ce, prior_low=pl, first=CAL.week_day_index(d) == 1)
    if kind == "nwog_flat_bear":
        ups = []
        for w in (getattr(ctx, "wicks", None) or [getattr(ctx, "wick", None)]):
            try:
                if w and w["upper"] >= so:
                    ups.append(float(w["upper"]))
            except Exception:
                pass
        info["wick_ce"] = min(ups) if ups else None
    P.info["nwog_tpl"] = info


def _iw_rules(P, ctx, d: date, p, hist, a5) -> None:
    wk = _this_week(hist, d)
    cf = getattr(ctx, "conf", None)
    for x in wk[:2]:
        if x.index[0].date().weekday() > 1:
            continue
        rng = float(x.high.max() - x.low.min())
        if rng > p.iw_k * a5 and cf is not None:
            px = float(x.close.iloc[-1])
            now = pd.Timestamp(d, tz=ctx.idx.tz)
            tfs = {tf for s_ in (1, -1) for tf in cf.at(now, px, s_, now)}
            if tfs & {"4h", "D", "W", "M"}:
                P.tags.add("iw_reversal_watch")
                P.info["iw_no_measured"] = bool(p.iw_no_measured)
                hit("iw_reversal_watch")
                return


def _profile_rules(P, ctx, d: date, p, hist, a5) -> None:
    row = getattr(ctx, "bias_row", None)
    side = 0
    for k in ("iof", "draw"):
        try:
            v = row[k]
            if v == v and int(v):
                side = int(v)
                break
        except Exception:
            continue
    cf = getattr(ctx, "conf", None)
    if not side or cf is None:
        return
    px = float(hist[-1].close.iloc[-1])
    lv = cf.targets(pd.Timestamp(d, tz=ctx.idx.tz), px, side, ("4h", "D", "W"))
    near = min(lv, key=lambda v: abs(v - px)) if len(lv) else None
    name = "am_pm_reversal" if (near is not None and abs(near - px) <= a5) else "two_session"
    P.tags.add("profile_" + name)
    P.info["profile_day"] = (name, side, None if near is None else float(near))


# --------------------------------------------------------------------------------------------------------------
# calendar rules (strategy.blocked)
# --------------------------------------------------------------------------------------------------------------

def calendar_block(d: date, session: str, p, t: int = 0):
    """The day rules of this package that need only the date: skip_election, summer_off. None = not blocked."""
    if p.skip_election != "off" and CAL.election_block(d, p.skip_election):
        return "election"                                         # N7-election (cc04_002 ~00:26:40)
    if p.summer_off and 6 <= d.month <= 8:
        return "summer_off"                                       # N7-august (084 ~00:28:06; 087 ~00:01:56)
    if getattr(p, "holiday_week_skip", False) and CAL.holiday_in_week(d):
        return "holiday_week"                                     # HOLIDAY-WEEK card B: stand aside in a holiday week [our interpretation: low volume = a weekday market holiday in the week]
    return None


def landmine_exempt(d: date, p) -> bool:
    """D20-landmine-week-monday (064 ~00:10:18): the week holds landmine_min or more high-impact releases on Tuesday-Friday - Monday is a trading day."""
    return bool(p.landmine_min and CAL.landmine_count(d) >= p.landmine_min)


# --------------------------------------------------------------------------------------------------------------
# risk and adds
# --------------------------------------------------------------------------------------------------------------

def size_mult(ctx, p, lvt=None) -> float:
    d = ctx.day
    m = 1.0
    P = getattr(ctx, "dplan", None)
    tags = P.tags if P is not None else set()
    if p.august_mode == "light" and d.month == 8:
        m *= 0.5
        lvt is not None and lvt.append("size_august_light")
    if p.holiday_week_mult != 1.0 and (("holiday_week" in tags) if P is not None else CAL.holiday_in_week(d)):
        m *= p.holiday_week_mult
        lvt is not None and lvt.append("size_holiday_week")
        hit("holiday_week_mult")
    if p.season_quality == "size":
        q = CAL.season_quality(d, p.season_autumn_start)
        m *= {"prime": 1.0, "poor": 0.5, "off": 0.75}[q]
        if d.month == 3:
            m *= p.season_march_mult
        lvt is not None and q != "prime" and lvt.append("size_season_" + q)
        hit("season_size_" + q)
    return m


def adds_off(ctx, p) -> bool:
    """entries.adds_blocked tail: no pyramiding in the August light mode and (with holiday_week_mult != 1) on holiday-week days."""
    d = ctx.day
    if p.august_mode == "light" and d.month == 8:
        return True
    return bool(p.holiday_week_mult != 1.0 and CAL.holiday_in_week(d))


# --------------------------------------------------------------------------------------------------------------
# per-bar rules
# --------------------------------------------------------------------------------------------------------------

def sd_intraday_at(ctx, p, i: int):
    """N8-intraday-seek-destroy (015 ~00:21:31; 024 ~00:19:27): the bar index at which the session was flagged "manipulated / seek and destroy" if that is <= i, else None. From 09:30 to
    sd_intraday_until the closed bars take the buy stops of an earlier swing high and the sell stops of an earlier swing low in turn (two or more alternations), inside a range under
    sd_intraday_frac x ADR5 and with no displacement bar (body >= displacement_mult, 1.5 when off, x the mean of the up to ten session bodies before it, from the fourth bar of the session). The whole-day array is causal (each step reads
    bars <= k and pivots confirmed by k), so a lookup at i reads indexes <= i only. Returns (flag bar, range high, range low) or None."""
    c = _cache(ctx)
    if "sdi" not in c:
        S = _S()
        c["sdi"] = _sd_scan(ctx, p, S)
    r = c["sdi"]
    if r is None or r[0] > i:
        return None
    return r


def _sd_scan(ctx, p, S):
    a = S._idx_at(ctx, 570)
    z = S._idx_at(ctx, p.sd_intraday_until)
    adr = _adr5(ctx, p)
    sides = getattr(ctx, "sides_map", None)
    if not adr or a >= len(ctx.t) or sides is None:
        return None
    sd = sides[1]
    mult = p.displacement_mult or 1.5
    seq, rng_h, rng_l = [], -np.inf, np.inf
    taken_h, taken_l = set(), set()
    for k in range(a, min(z, len(ctx.t))):
        rng_h, rng_l = max(rng_h, float(ctx.h[k])), min(rng_l, float(ctx.l[k]))
        ev = []
        for q in sd.ph:
            if q.known <= k - 1 and q.i >= ctx.start and q.i < k and id(q) not in taken_h and ctx.h[k] > q.price:
                taken_h.add(id(q))
                ev.append("H")
        for q in sd.pl:
            if q.known <= k - 1 and q.i >= ctx.start and q.i < k and id(q) not in taken_l and ctx.l[k] < q.price:
                taken_l.add(id(q))
                ev.append("L")
        if "H" in ev and "L" in ev:
            ev = ["L", "H"] if ctx.c[k] >= ctx.o[k] else ["H", "L"]
        elif ev:
            ev = ev[:1]
        for e in ev:
            if not seq or seq[-1] != e:
                seq.append(e)
        body = abs(float(ctx.c[k] - ctx.o[k]))
        prev = np.abs(ctx.c[max(a, k - 10):k] - ctx.o[max(a, k - 10):k])          # [our interpretation] the average body of the session's own bars (the overnight bars are far smaller than the RTH ones)
        if len(prev) >= 3 and body >= mult * float(prev.mean()):
            return None                                           # a displacement bar: not seek and destroy
        if len(seq) - 1 >= 2 and (rng_h - rng_l) < p.sd_intraday_frac * adr:
            return k, float(rng_h), float(rng_l)
    return None


def sd_fvg_held(ctx, fi: int, i: int, hh: float, ll: float) -> bool:
    """N8-intraday-seek-destroy rule (b) (015 ~00:21:31): after the first close beyond the flagged range (up: > hh, down: < ll) an FVG forms in that direction (three closed bars, the middle
    bar's displacement) and price later retraces into it with a bar that closes without a body through it (up: low <= the gap top and close >= the gap bottom). Reads bars <= i only
    [our interpretation: the FVG is the first one whose third bar is at or after the breaking bar]."""
    c, h, l = ctx.c, ctx.h, ctx.l
    bk, d = None, 0
    for k in range(fi + 1, i + 1):
        if c[k] > hh:
            bk, d = k, 1
            break
        if c[k] < ll:
            bk, d = k, -1
            break
    if bk is None:
        return False
    for k in range(max(bk, fi + 2), i + 1):
        if d > 0 and l[k] > h[k - 2]:
            lo_, hi_ = float(h[k - 2]), float(l[k])
        elif d < 0 and h[k] < l[k - 2]:
            lo_, hi_ = float(h[k]), float(l[k - 2])
        else:
            continue
        for j in range(k + 1, i + 1):
            if d > 0 and l[j] <= hi_ and c[j] >= lo_:
                return True
            if d < 0 and h[j] >= lo_ and c[j] <= hi_:
                return True
        break                                                     # only the first FVG counts
    return False


def gate(ctx, p, session: str, i: int, t: int, trades=()):
    """Per-bar session gates: post_holiday_am "symmetry" (the NY AM waits for ES / NQ to break the same side of the 09:30-09:45 range) and the sd_intraday "rules" (no entry before the flagged
    range is broken by a close; none after the locked HTF level traded)."""
    P = getattr(ctx, "dplan", None)
    if P is None:
        return None
    DW = _DW()
    if P.info.get("ph_symmetry") and session in DW.NY_AM:
        from . import nct2 as _N2
        if getattr(ctx, "pside", (None, None, None))[0] is None:
            hit("post_holiday_symmetry_nopartner")                 # no partner index (a SPY-only run): the symmetry cannot be judged, so the old post-holiday AM block stays [our interpretation]
            return "x_dw_post_holiday_symmetry"
        if not _N2.symmetry_ok(ctx, p, i):
            hit("post_holiday_symmetry_wait")
            return "x_dw_post_holiday_symmetry"
        hit("post_holiday_symmetry_open")
    if p.sd_intraday == "rules":
        r = sd_intraday_at(ctx, p, i)
        if r is not None:
            fi, hh, ll = r
            seg = ctx.c[fi + 1:i + 1]
            broke = bool(len(seg) and (seg.max() > hh or seg.min() < ll))
            if not broke:
                hit("sd_intraday_wait")
                return "x_dw_sd_intraday_range"
            if p.sd_fvg_hold and not sd_fvg_held(ctx, fi, i, hh, ll):
                hit("sd_intraday_fvg_wait")
                return "x_dw_sd_intraday_fvg"
            for s_, lk in (getattr(ctx, "lock", None) or {}).items():
                di = lk.get("delivered_i")
                if lk.get("delivered") and di is not None and di <= i and s_ not in ("PM", "LH") and di >= fi:
                    hit("sd_intraday_after_draw")
                    return "x_dw_sd_after_draw"
    return None


def scalp_now(ctx, p, session: str, i) -> str:
    """sd_intraday "rules": a flagged session's orders are scalps (single exit, no runner / trailing to a second target)."""
    P = getattr(ctx, "dplan", None)
    if p.fri_one_sided == "raid_first" and P is not None and fri_overnight_ok(ctx, p, P, i):
        hit("fri_one_sided_scalp")
        return "fri_one_sided"                                   # small targets (~5 handles, Params.fri_t1_pts), independent of the other scalp reasons' order
    if p.sd_intraday == "rules" and i is not None and session not in ("PM", "LUNCH", "LH"):
        if sd_intraday_at(ctx, p, i) is not None:
            hit("sd_intraday_scalp")
            return "sd_intraday"
    return ""


def _lock_side_am(ctx, i: int):
    lk = (getattr(ctx, "lock", None) or {}).get("AM")
    return lk


def side_ok(ctx, p, sign: int, session: str, i: int):
    """Side filters: the NWOG templates (gate), objective_done_pm "reversal_only", day_profile_gate."""
    P = getattr(ctx, "dplan", None)
    if P is None:
        return None
    DW = _DW()
    tpl = P.info.get("nwog_tpl")
    if p.nwog_templates == "gate" and tpl and tpl["first"] and tpl["kind"]:
        dh = DW._day_hl(ctx, i)
        k = tpl["kind"]
        if k == "nwog_up_bull" and sign > 0:
            lo_ = None if dh is None else dh[1]
            ev_ = getattr(ctx, "eve", None)
            if ev_ and lo_ is not None:
                lo_ = min(lo_, float(ev_[2]))                              # the Sunday evening session (where the gap normally fills) counts for the Friday-close / CE test
            ok = lo_ is not None and lo_ <= tpl["ce"]                      # the Friday close traded or the CE touched ("the CE holds")
            if not ok:
                hit("nwog_up_bull_wait")
                return "x_dw_nwog_up_bull"
        elif k == "nwog_below_wick_bull" and sign > 0:
            # [our interpretation] "the first session's close": any close of the first trading day (the frame from midnight) at or above the prior low reclaims the wick
            seg = ctx.c[ctx.start:i + 1]
            if not (len(seg) and float(seg.max()) >= tpl["prior_low"]):    # reclaimed by a close
                hit("nwog_below_wick_wait")
                return "x_dw_nwog_below_wick"
        elif k == "nwog_flat_bear" and sign < 0 and tpl.get("wick_ce") is not None:
            if not (dh is not None and dh[0] >= tpl["wick_ce"]):
                hit("nwog_flat_bear_wait")
                return "x_dw_nwog_flat_bear"
    if p.objective_done_pm == "reversal_only" and session in DW.LATE:
        lk = _lock_side_am(ctx, i)
        if lk and lk.get("side") and lk.get("delivered") and lk.get("delivered_i") is not None:
            di = lk["delivered_i"]
            if di <= i and ctx.t[di] + ctx.tf <= 720 and sign == lk["side"]:
                hit("objective_done_pm_block")
                return "x_dw_objective_done_pm"
    if p.day_profile_gate and session in DW.LATE:
        pr = P.info.get("profile_day")
        if pr is not None:
            name, side, lvl = pr
            lk = _lock_side_am(ctx, i)
            am = lk["side"] if lk and lk.get("side") else side
            if name == "two_session" and sign != am:
                hit("profile_two_session_block")
                return "x_dw_profile_two_session"
            if name == "am_pm_reversal" and lvl is not None:
                dh = DW._day_hl(ctx, i)
                touched = dh is not None and ((dh[0] >= lvl) if side > 0 else (dh[1] <= lvl))
                if touched and sign == side:
                    hit("profile_reversal_block")
                    return "x_dw_profile_reversal"
    return None


def fri_overnight_ok(ctx, p, P, i) -> bool:
    """BH-B17-friday-after-one-sided-week (045 ~00:11:00): Friday follows a one-way Tue-Thu week AND the pre-open (overnight) high is above Thursday's high (the low below Thursday's low for the
    bearish week). Known only once the 09:30 bar has closed (i >= its index), so an order armed before it is not gated [our interpretation: a pre-open order cannot satisfy 'the sweep
    below the 09:30 open', and the 09:30 open is not yet known]."""
    fd = P.info.get("fri_dir") if P is not None else 0
    if not fd or i is None:
        return False
    S = _S()
    k0 = S._idx_at(ctx, 570)
    if k0 >= len(ctx.t) or i < k0:
        return False
    hist = getattr(ctx, "hist", [])
    pre = _DW().overnight_stats(ctx, p, hist)
    if pre is None or not hist:
        return False
    thu = hist[-1]
    return (pre["hi"] > float(thu.high.max())) if fd > 0 else (pre["lo"] < float(thu.low.min()))


def order_ok(ctx, sd, o: dict, session: str, i: int, p):
    """Per-order filters: thu_strict, fri_one_sided "raid_first", mon_how "gate", objective_frac_gate."""
    P = getattr(ctx, "dplan", None)
    if P is None:
        return None
    S = _S()
    DW = _DW()
    # BH-N10-thursday-not-top-call (044 ~00:16:07 / ~01:21:30): a counter-trend entry after a one-sided week needs a sweep at an HTF array, a displaced MSS and a 10:00-11:00 fill
    os_ = P.info.get("one_sided")
    if p.thu_strict and os_ and sd.sign == -os_:
        tol = p.eq_tol_pts * p.es_pt
        if not S._htf_tag(ctx, sd, i, o["ext"], tol):
            hit("thu_strict_no_array")
            return "x_dw_thu_no_array"
        k = o.get("broke")
        if k is not None:
            k = int(k)
            mult = (p.displacement_mult or 1.0) * 1.5
            body = abs(float(sd.c[k] - sd.o[k]))
            prev = np.abs(sd.c[max(0, k - 10):k] - sd.o[max(0, k - 10):k])
            if len(prev) and body < mult * float(prev.mean()):
                hit("thu_strict_no_disp")
                return "x_dw_thu_no_displacement"
        nxt = int(ctx.t[i]) + ctx.tf
        if not 600 <= nxt < 660:
            hit("thu_strict_time")
            return "x_dw_thu_time"
        hit("thu_strict_pass")
    # BH-B17-friday-after-one-sided-week (045 ~00:11:00): the continuation long needs the sweep below the 09:30 open
    fd = P.info.get("fri_dir")
    if p.fri_one_sided == "raid_first" and fd and sd.sign == fd and fri_overnight_ok(ctx, p, P, i):
        k0 = S._idx_at(ctx, 570)
        ext = sd.x(o["ext"])
        op = float(ctx.o[k0])
        if not ((ext < op) if fd > 0 else (ext > op)):
            hit("fri_raid_first_reject")
            return "x_dw_fri_raid_first"
        hit("fri_raid_first_pass")
    # NEW-monday-high-of-week-profile (078 ~01:07:29)
    mh = P.info.get("mon_how")
    if p.mon_how == "gate" and mh is not None and sd.sign == mh[0]:
        side, ref = mh
        dh = DW._day_hl(ctx, i)
        cleared = dh is not None and ((dh[0] > ref) if side < 0 else (dh[1] < ref))
        if not cleared:
            ent = sd.x(o["entry"])
            if (side < 0 and ent >= ref) or (side > 0 and ent <= ref):
                hit("mon_how_reject")
                return "x_dw_mon_how"
    # N9-objective-before-lunch (015 ~00:16:22): the lion's share of the move to the locked draw is already delivered
    if p.objective_frac_gate:
        lk = (getattr(ctx, "lock", None) or {}).get("PM" if session in DW.LATE else "AM")
        if lk and lk.get("side") == sd.sign and lk.get("target") is not None:
            kl = S._idx_at(ctx, lk.get("t_lock", 570))
            kl = min(kl, len(ctx.t) - 1)
            op = float(ctx.o[kl])
            tgt = float(lk["target"])
            if (tgt - op) * sd.sign > 0:
                frac = (float(ctx.c[i]) - op) / (tgt - op)
                if frac > p.objective_frac_gate:
                    hit("objective_frac_reject")
                    return "x_dw_objective_frac"
    return None


# --------------------------------------------------------------------------------------------------------------
# lock candidates, day parameters, tags
# --------------------------------------------------------------------------------------------------------------

_HTF_NAMES = ("htf_", "pw", "pmonth", "nwog", "ndog", "ipda", "mon_wed", "pdh", "pdl", "m3", "org", "old_", "week")


def lock_filter(ctx, cands: list) -> list:
    """BH-mixed-HTF-intraday-only: on a flagged macro-risk week inside a fresh weekly FVG the lock candidates are session pools only (no weekly / daily draws)."""
    P = getattr(ctx, "dplan", None)
    if P is None or not P.info.get("macro_scalp"):
        return cands
    keep = [c for c in cands if not str(c[2]).startswith(_HTF_NAMES)]
    if len(keep) != len(cands):
        hit("macro_lock_filter")
    return keep


def day_params(p, dw):
    """iw_no_measured: on an intra-week reversal watch day the measured-move (equal-leg) rung switches are off [our interpretation of 'measured-move targets']."""
    if dw.info.get("iw_no_measured"):
        hit("iw_no_measured")
        from dataclasses import replace
        return replace(p, mm_targets=False, proj_ext_sym=False, pm_am_leg=False)
    return p


def entry_tags(ctx, p, P, k: int) -> set:
    """Per-trade tags from the bars through the entry bar k (reporting only)."""
    t = set()
    DW = _DW()
    tpl = P.info.get("nwog_tpl")
    if tpl and k >= ctx.start:
        hh, ll = float(ctx.h[ctx.start:k + 1].max()), float(ctx.l[ctx.start:k + 1].min())
        pc, so, ce = tpl["pc"], tpl["so"], tpl["ce"]
        if so > pc:
            if ll <= pc:
                t.add("nwog_filled")
            elif ll <= ce:
                t.add("nwog_ce_held")
            elif ll < so:
                t.add("nwog_partial")
        elif so < pc:
            if hh >= pc:
                t.add("nwog_filled")
            elif hh >= ce:
                t.add("nwog_ce_held")
            elif hh > so:
                t.add("nwog_partial")
    mh = P.info.get("mon_how")
    if mh is not None and k >= ctx.start:
        side, ref = mh
        hh, ll = float(ctx.h[ctx.start:k + 1].max()), float(ctx.l[ctx.start:k + 1].min())
        if not ((hh > ref) if side < 0 else (ll < ref)):
            t.add("mon_how_live")
    if p.sd_intraday != "off" and sd_intraday_at(ctx, p, k) is not None:
        t.add("sd_intraday")
    if P.info.get("one_sided"):
        t.add("one_sided_week")
    if P.info.get("fri_dir") and p.fri_one_sided != "off" and fri_overnight_ok(ctx, p, P, k):
        t.add("fri_one_sided")                                   # Tue-Thu one way and the overnight high above Thursday's high
    return t
