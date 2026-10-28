"""Package news_calendar_times (rule_coverage.md section 3 "news_calendar_times"; build_log.md).

Calendar-driven and session-window rules of the N1-N5 / T4-T9 / M9 / D1 / D8 / D9 / Ep01.10 / Ep02.1 /
Ep06.1 / Ep07.8 items. strategy.blocked() calls `calendar_block` for the pure calendar rules; run_day
calls the helpers below (extra windows, the per-bar gate, the Judas side, the order post-filter, the
deferred FOMC order). Everything reads only bars that have closed (index <= the caller's bar i); every
value fixed ahead of time (a window, a release minute, a pre-release range) is computed from bars that
ended before the minute it is used at; `first_run` / `or_dir` results carry the bar index from which they
are known and every reader compares it with its own bar. Thresholds the sources never give are marked
[our interpretation]. Every rule is a Params switch (strategy.Params, "package news_calendar_times").

Pieces
  calendar_block   N3 / N3.2 / N3.3 / N3.4 / N4 / N5.4 / N5.5 / N5.6 / D8 / D9  day rules (no bars needed)
  day_risk         N3 / N3.4 / N4 / D9   size multiplier of the eve of FOMC / CPI
  day_tags         N1 / N3.3 / N5.4 ...  the day's news tags (Trade.news_tags)
  fomc_flat_min    N3 / N3.2             flat before the 14:00 release
  extra_windows    T5 / Ep01.10 / Ep06.1 the PRE8 and LON windows
  gate             N3.2 / N5.4 / T8 / T9 per-bar session gates that need the bars or the day's trades
  judas_gate       M9 / M9.1 / M9.2      the first run after a release is the losing side
  side_filter      T4 / D1 / T9          opening-range bias, wide OR, the PM continues the AM
  post_order       T4 / T7 / T9 / Ep07.8 an armed order: macro gates, OR no-entry fills, tags
  held_valid / fill_ok                   N3.1 the deferred FOMC order; T4 the fill gate of an OR order
  carry_lock       T8                    the AM's undelivered draw is the PM's draw
"""
from __future__ import annotations

import numpy as np

from claude_hf.daytypes import events
from . import calendar as CAL

# ICT macros for the T7 gate (T7; 073 ~14:54): the engine's MACROS tag tuple plus the 13:30 PM macro and
# the 13:39 "2:00 macro" (015 ~31:57). (a, b) minutes, [a, b).
MACROS_T7 = ((530, 550), (590, 610), (650, 670), (710, 730), (790, 820), (810, 815), (819, 840),
             (890, 910), (915, 945))
MACRO_0950 = (590, 610)
PRE_NAMES = ("PRE7", "PRE8", "PRE9", "NEWS", "LON")


# ---------------------------------------------------------------------------------------------------
# calendar-only rules
# ---------------------------------------------------------------------------------------------------

def calendar_block(d, session: str, p, t: int = 0):
    """The day rule that blocks `session` ("PM" or any morning window) at minute t, or None:
      nfp_day_from      D8   jobs day: no entry before the minute
      fomc_am_skip      N3.2 FOMC day: sit out the AM       fomc_only_am_skip  N3.3 the FOMC-only AM
      post_fomc_am      N3 / N3.4 / D8   the AM after FOMC (095 ~51:27)
      pre_fomc          the day before FOMC skipped          pre_cpi   N4 / D9 the day before CPI skipped
      fed_chair         N5.5  the AM of a Fed chair 10:00 testimony
      auction_am        N5.6  the AM of a Treasury auction day
      two_drivers       N5.4  the AM when 08:30 and 09:45 / 10:00 both release (stand aside)
    ("recipe" for fomc_am needs the bars: gate())."""
    pm = session == "PM"
    tags = events(d)
    if "jobs" in tags and p.nfp_day_from and t < p.nfp_day_from:
        return "nfp_day_from"
    fi = CAL.fomc_info(d)
    if fi["fomc"] and not pm:
        if p.fomc_am == "skip":
            return "fomc_am_skip"
        if fi["only"] and p.fomc_only_am == "skip":
            return "fomc_only_am_skip"
    am_only = session in ("AM", "PRE9", "NEWS")             # the NY AM family (not London / PRE7 / PRE8 / lunch)
    if fi["after"] and am_only and (p.skip_post_fomc_am or p.fomc_after_am_block):
        return "post_fomc_am"
    if fi["eve"] and p.skip_pre_fomc:
        return "pre_fomc"
    if (p.skip_pre_cpi or p.pre_cpi == "skip") and CAL.eve_of(d, "cpi"):
        return "pre_cpi"
    if am_only:
        if p.fed_chair_skip_am and (d in CAL.FED_CHAIR or d in CAL.FED_CHAIR_EXTRA):
            return "fed_chair"
        if p.skip_auction_am and CAL.is_auction_day(d):
            return "auction_am"
        if p.skip_two_drivers and CAL.two_drivers(d, p.news_claims, p.news_conf_board):
            return "two_drivers"
    from . import nct2 as _N2
    return _N2.calendar_block2(d, session, p, t)         # caption-gap pass news_calendar_times#1/1


def day_risk(d, p, lvt: list | None = None) -> float:
    """Risk multiplier of the day: the eve of FOMC (N3 fomc_eve_risk x N3.4 pre_fomc_risk) and the eve of
    CPI (N4 / D9 pre_cpi="small"). A re-entry multiplies with it (entries.size_mult is per order)."""
    m = 1.0
    if (p.fomc_eve_risk != 1.0 or p.pre_fomc_risk != 1.0) and CAL.fomc_info(d)["eve"]:
        m *= p.fomc_eve_risk * p.pre_fomc_risk
        if lvt is not None:
            lvt.append("size_pre_fomc")
    if p.pre_cpi == "small" and CAL.eve_of(d, "cpi"):
        m *= p.pre_cpi_risk
        if lvt is not None:
            lvt.append("size_pre_cpi")
    return m


def day_tags(d, p=None) -> str:
    """The day's news tags, "|"-joined: nfp, nfp_week (the days before the jobs day), fomc, fomc_only,
    fomc_eve, fomc_after, cpi, pre_cpi, two_driver, fed_chair, auction, claims, minutes."""
    tags = events(d)
    fi = CAL.fomc_info(d)
    out = []
    if "jobs" in tags:
        out.append("nfp")
    elif CAL.nfp_shift(d) >= 0 and d < CAL.nfp_date(d):
        out.append("nfp_week")
    if fi["fomc"]:
        out.append("fomc_only" if fi["only"] else "fomc")
    if fi["eve"]:
        out.append("fomc_eve")
    if fi["after"]:
        out.append("fomc_after")
    if "cpi" in tags:
        out.append("cpi")
    if CAL.eve_of(d, "cpi"):
        out.append("pre_cpi")
    if CAL.two_drivers(d):
        out.append("two_driver")
    if d in CAL.FED_CHAIR or d in CAL.FED_CHAIR_EXTRA:
        out.append("fed_chair")
    if CAL.is_auction_day(d):
        out.append("auction")
    out += sorted(t for t in CAL.minor_events(d) if t != "conf_board" or (p is not None and p.news_conf_board))
    from . import nct2 as _N2
    out += [x for x in _N2.day_tags2(d, p) if x not in out]      # caption-gap pass news_calendar_times#1/1
    return "|".join(out)


def fomc_flat_min(d, p) -> int:
    """N3 / N3.2 (cc10_009 ~3:48): never hold into the afternoon release - the minute an FOMC day's positions that were
    opened before it are closed (the bar ending at it) and orders armed before it are cancelled; 0 = off / no FOMC.
    A position opened after the release (the PM from 14:45) is not touched."""
    v = p.fomc_flat if p.fomc_flat_before is None else p.fomc_flat_before
    return v if (v and CAL.fomc_info(d)["fomc"]) else 0


def releases(day, p) -> list[int]:
    """The release minutes the news gate waits for (calendar.release_times with the minor releases and
    wait_0945 of the Params)."""
    from . import strategy as S
    if p.news_claims or p.news_minutes or p.news_conf_board or not p.wait_0945:
        return CAL.release_times(day, claims=p.news_claims, minutes=p.news_minutes, pmi=p.wait_0945,
                                 conf=p.news_conf_board)
    return S.release_times(day)


# ---------------------------------------------------------------------------------------------------
# session windows
# ---------------------------------------------------------------------------------------------------

def futures_day(ctx, symbol: str, minute: int) -> bool:
    """Futures only (Ep06.1): a futures symbol whose day frame has bars at or before `minute`."""
    from .strategy import EQUITY_SYMBOLS
    return ((symbol or "").upper() not in EQUITY_SYMBOLS and len(ctx.t) > ctx.start
            and bool(ctx.t[ctx.start] <= minute))


def fomc_whipsaw(ctx, day, p) -> bool:
    """N3 (cc08_006 ~3:36): the previous session was an FOMC day whose 14:00-15:00 reaction took both sides of the
    13:00-14:00 range (a whipsaw). Read from the completed previous regular session (history)."""
    if p.fomc_whipsaw_skip != "off" and CAL.fomc_info(day)["after"]:
        from . import nct2 as _N2
        if _N2.whip_flag(ctx, p, day):                  # caption-gap N3-fomc-whipsaw-skip-london (cc08_006 ~00:04:37): the ADR5 form of the whipsaw
            return True
    if not (p.fomc_whipsaw_skip_london and CAL.fomc_info(day)["after"]):
        return False
    hist = getattr(ctx, "hist", None)
    if not hist:
        return False
    prev = hist[-1]
    m = prev.index.hour * 60 + prev.index.minute
    ref, run = prev[(m >= 780) & (m < 840)], prev[(m >= 840) & (m < 900)]
    if not len(ref) or not len(run):
        return False
    return bool(run.high.max() > ref.high.max() and run.low.min() < ref.low.min())


def pre8_enabled(p) -> bool:
    return bool(p.pre_0820 or p.ny_kz_futures)


def pre8_end(p) -> int:
    """Where the PRE8 window ends: 08:30 with am_from_0830 (the AM takes over), else where PRE9 / NEWS begin
    (09:00), else the AM start."""
    if p.am_from_0830:
        return 510
    if p.pre_0900 or p.post_news:
        return 540
    return p.am[0]


def extra_windows(p, ctx, day, symbol: str) -> list:
    """T5 / Ep01.10 / Ep06.1: the new pre-open windows (name, start, end).
      PRE8  08:20 .. pre8_end. pre_0820 skips 08:30 release days (the release is the first thing); ny_kz_futures
            (the futures kill zone 08:20-11:00) keeps them - the news gate (owner #4) holds those - and needs a
            futures day frame
      LON   london_kz_start .. 05:00, futures only (Ep06.1)"""
    out = []
    if p.london_kz and futures_day(ctx, symbol, p.london_kz_start) and not fomc_whipsaw(ctx, day, p):
        out.append(("LON", p.london_kz_start, 300))
    if pre8_enabled(p):
        if p.ny_kz_futures:
            ok = futures_day(ctx, symbol, 500)
        else:
            ok = 510 not in releases(day, p)
        if ok:
            out.append(("PRE8", 500, pre8_end(p)))
    return out


def lock_cuts_extra(p) -> set:
    """The draw-lock minutes the new windows add (backtest.lock_cuts)."""
    out = set()
    if p.am_from_0830:
        out.add(510)
    if pre8_enabled(p):
        out.add(500)
    if p.london_kz:
        out.add(p.london_kz_start)
    return out


def am_range(ctx, p):
    """T8: the AM range (09:30 .. am[1]) as (high, low) - complete before the lunch session starts."""
    tt = ctx.t[ctx.start:]
    k = np.flatnonzero((tt >= 570) & (tt < p.am[1])) + ctx.start
    if not len(k):
        return None
    return float(ctx.h[k].max()), float(ctx.l[k].min())


# ---------------------------------------------------------------------------------------------------
# per-bar gates
# ---------------------------------------------------------------------------------------------------

def recipe_ok(ctx, i: int) -> bool:
    """N3.2 "the trending-day recipe holds" [our interpretation]: the daily HTF table's reaction and draw
    columns agree and are not neutral. The table is cut at the 09:30 open, so before it it is unknown (False)."""
    from . import entries as _EN
    row = _EN.bias_row_known(ctx, i)
    if row is None:
        return False
    try:
        r, d = int(row["react"]), int(row["draw"])
    except Exception:
        return False
    return r != 0 and r == d


def run_done(ctx, i: int, p) -> bool:
    """T7 "the day's run is already done" (030 ~18:26) [our interpretation]: a session draw lock delivered, or the
    day's range so far (bars to i, closed) already spans run_done_adr x ADR5."""
    for lk in (getattr(ctx, "lock", None) or {}).values():
        if lk.get("delivered") and (lk.get("delivered_i") is None or lk["delivered_i"] <= i):
            return True
    if p.run_done_adr > 0:
        from .strategy import adr5
        adr = adr5(getattr(ctx, "hist", [])[-5:])
        if adr:
            rng = float(ctx.h[ctx.start:i + 1].max() - ctx.l[ctx.start:i + 1].min())
            return rng >= p.run_done_adr * adr
    return False


def gate(ctx, p, day, session: str, t: int, i: int, wb: int, trades):
    """A funnel key when this bar's session may not start a setup, else None:
      x_fomc_recipe    N3.2 fomc_am="recipe" and the recipe does not hold
      x_two_driver     N5.4 a pre-open window ends before the day's last morning release (two drivers)
      x_draw_done      T8 draw_done_skip: the AM's draw is delivered - no lunch / PM entry
      x_pm_skip_after  T9 pm_skip_after: nothing traded by then"""
    if session != "PM" and p.fomc_am == "recipe" and CAL.fomc_info(day)["fomc"] and not recipe_ok(ctx, i):
        return "x_fomc_recipe"
    if p.two_driver_gate and session in PRE_NAMES and CAL.two_drivers(day, p.news_claims, p.news_conf_board):
        last = max((r for r in releases(day, p) if r in (585, 600)), default=0)
        if last and wb <= last:
            return "x_two_driver"
    if p.draw_done_skip and session in ("PM", "LUNCH"):
        am = (getattr(ctx, "lock", None) or {}).get("AM")
        if am is not None and am.get("delivered") and (am.get("delivered_i") is None or am["delivered_i"] <= i):
            return "x_draw_done"
    if session == "PM" and p.pm_skip_after and t >= p.pm_skip_after:
        lh = p.last_hour[0] <= t < p.last_hour[1]
        if (not lh or p.pm_skip_lh) and not any(tr.session == "PM" for tr in trades):
            return "x_pm_skip_after"
    return None


def pm_start(p, w0: int, trades) -> int:
    """T9: after a losing AM (a closed morning-family trade with a net loss) the PM restarts at pm_bad_am_start."""
    if not p.pm_bad_am_start:
        return w0
    for tr in trades:
        if tr.session != "PM" and tr.exits:
            gross, costs = tr.pnl(p.cost_per_share)
            if gross - costs < 0:
                return max(w0, p.pm_bad_am_start)
    return w0


# ---------------------------------------------------------------------------------------------------
# news Judas (M9 / M9.1 / M9.2)
# ---------------------------------------------------------------------------------------------------

def first_run(ctx, R: int, ref_min: int, end: int | None = None) -> dict:
    """The first run after the release at minute R through the pre-release reference pools [our interpretation:
    the high / low of the ref_min minutes before R, today's bars]. dict(ref=bool, k=bar index | None, dir=+1 / -1):
    k = the first bar from R (before `end`) whose high (low) trades beyond the reference high (low); +1 = the buy
    side was taken first. Both on one bar: the move that came first is unknowable - take it as opposite to the
    bar's close (the close is the delivery); a doji bar is skipped. The index k is the bar that completes the run;
    every reader acts only from bar k on (closed bars)."""
    cache = ctx.__dict__.setdefault("_nc_run", {})
    key = (R, ref_min, end)
    if key in cache:
        return cache[key]
    t, S0 = ctx.t, ctx.start
    tt = t[S0:]
    ref = np.flatnonzero((tt >= R - ref_min) & (tt < R)) + S0
    out = dict(ref=False, k=None, dir=0)
    if len(ref):
        out["ref"] = True
        hi, lo = float(ctx.h[ref].max()), float(ctx.l[ref].min())
        for k in np.flatnonzero(tt >= R) + S0:
            if end is not None and t[k] >= end:
                break
            up, dn = ctx.h[k] > hi, ctx.l[k] < lo
            if up and dn:
                if ctx.c[k] == ctx.o[k]:
                    continue
                out.update(k=int(k), dir=-1 if ctx.c[k] > ctx.o[k] else 1)
                break
            if up or dn:
                out.update(k=int(k), dir=1 if up else -1)
                break
    cache[key] = out
    return out


def judas_gate(ctx, p, day, drv, i: int, t: int):
    """(blocked side sign | 0, wait) at bar i for the session driven by release `drv` (run_day's news gate):
      news_judas "block"  the first run's direction is closed after it (the losing side)
      news_judas "wait"   M9.1: also no entry before a first run has happened
      fomc_judas          M9.2: on an FOMC day the first run in 14:00 .. fomc_judas_end is the Judas - only the other
                          side from then on (to fomc_pm_from, or all PM with fomc_stage2_cont)"""
    block, wait = 0, False
    if drv is None:
        return block, wait
    R = drv["R"]
    if p.news_judas != "off":
        fr = first_run(ctx, R, p.news_judas_ref_min)
        if fr["ref"]:
            if fr["k"] is not None and i >= fr["k"]:
                block = fr["dir"]
            elif p.news_judas == "wait":
                wait = True
    if ((p.fomc_judas or p.fomc_observe == "judas") and R == 840 and t >= p.fomc_judas_end
            and CAL.fomc_info(day)["fomc"]):                  # not on an FOMC-minutes day (also a 14:00 release)
        fr = first_run(ctx, 840, p.news_judas_ref_min, end=p.fomc_judas_end)
        if fr["ref"] and fr["k"] is not None and (p.fomc_stage2_cont or t < p.fomc_pm_from):
            block = block or fr["dir"]
    return block, wait


# ---------------------------------------------------------------------------------------------------
# side filters: the opening range and the PM continuing the AM
# ---------------------------------------------------------------------------------------------------

def or_dir(ctx, mode: str, end: int) -> int:
    """T4 (042 ~4:29): the bias the 09:30 .. `end` opening range delivered. "judas": the extreme made first was the
    Judas, so the day goes the other way (the high first -> -1, the low first -> +1, a tie 0); "close": the range's
    last close above (below) its midpoint -> +1 (-1). Bars that ended by `end` only; read from `end` on."""
    cache = ctx.__dict__.setdefault("_nc_or", {})
    key = (mode, end)
    if key in cache:
        return cache[key]
    tt = ctx.t[ctx.start:]
    k = np.flatnonzero((tt >= 570) & (tt < end)) + ctx.start
    out = 0
    if len(k):
        if mode == "judas":
            ih, il = int(np.argmax(ctx.h[k])), int(np.argmin(ctx.l[k]))
            out = -1 if ih < il else (1 if il < ih else 0)
        else:
            mid = (ctx.h[k].max() + ctx.l[k].min()) / 2
            out = int(np.sign(ctx.c[k[-1]] - mid))
    cache[key] = out
    return out


def wide_or_dir(ctx, p) -> int:
    """T4 CC (cc10_010 ~3:07-7:05): a wide OR (09:30 .. or_wide_end, range >= or_wide_adr x ADR5) gets its opposite
    end run: toward the end farther from the OR's last close (+1 up, -1 down; 0 = not wide / unknown)."""
    cache = ctx.__dict__.setdefault("_nc_wide", {})
    if "v" in cache:
        return cache["v"]
    from .strategy import adr5
    tt = ctx.t[ctx.start:]
    k = np.flatnonzero((tt >= 570) & (tt < p.or_wide_end)) + ctx.start
    out = 0
    adr = adr5(getattr(ctx, "hist", [])[-5:])
    if len(k) and adr:
        hi, lo = float(ctx.h[k].max()), float(ctx.l[k].min())
        if hi - lo >= p.or_wide_adr * adr:
            out = -1 if ctx.c[k[-1]] > (hi + lo) / 2 else 1
    cache["v"] = out
    return out


def am_dir(ctx, p) -> int:
    """T9 (047 ~09:21): the AM's direction = the close of the last bar before 12:00 vs the 09:30 open (+1 / -1; 0 when
    flat or no data). Bars that ended by 12:00 - known at the PM."""
    cache = ctx.__dict__.setdefault("_nc_am", {})
    if "v" in cache:
        return cache["v"]
    tt = ctx.t[ctx.start:]
    k = np.flatnonzero((tt >= 570) & (tt < 720)) + ctx.start
    out = int(np.sign(ctx.c[k[-1]] - ctx.o[k[0]])) if len(k) else 0
    cache["v"] = out
    return out


def side_filter(ctx, p, session: str, sign: int, i: int, t: int):
    """A funnel key when side `sign` is closed at bar i, else None (T4 or_bias / or_wide, T9 pm_continue_am)."""
    if session != "PM":
        if p.or_bias != "off" and p.or_bias_filter and t >= p.or_end:
            b = or_dir(ctx, p.or_bias, p.or_end)
            if b and sign != b:
                return "x_or_bias"
        if p.or_wide and t >= p.or_wide_end:
            b = wide_or_dir(ctx, p)
            if b and sign != b:
                return "x_or_wide"
    elif p.pm_continue_am == "filter":
        b = am_dir(ctx, p)
        if b and sign != b:
            return "x_pm_continue_am"
    return None


# ---------------------------------------------------------------------------------------------------
# an armed order
# ---------------------------------------------------------------------------------------------------

MACRO_LAST_HOUR_END = (945, 950)     # X3-027-pm-runner-macro (027 ~00:40:28): the 15:45-15:50 last-hour macro, a T7 window with pm_macro_runner


def macro_wins(t: int, p=None) -> list[str]:
    """T7 multi-tag: every macro window minute t lies in, "HHMM" of its start. Caption-gap X3-027-pm-runner-macro: with Params.pm_macro_runner the 15:45-15:50 window is one too."""
    wins = MACROS_T7 + ((MACRO_LAST_HOUR_END,) if (p is not None and getattr(p, "pm_macro_runner", False)) else ())
    return [f"{a // 60:02d}{a % 60:02d}" for a, b in wins if a <= t < b]


def _in(wins, m: int) -> bool:
    return any(a <= m < b for a, b in wins)


def _ob_before_pm(ctx, sd, i, entry) -> bool:
    """T9 pm_ob_entry [our interpretation of "off an OB formed in the AM or lunch"]: the last down-close series
    (bullish; side space) between 09:30 and 13:30 as a blended order block that no close has broken since; True when
    the entry lies inside its range."""
    from . import levels as L
    a = ctx.start + int(np.searchsorted(ctx.t[ctx.start:], 570))
    b = min(ctx.start + int(np.searchsorted(ctx.t[ctx.start:], 810)), i)
    if b <= a + 1:
        return False
    z = L.order_block_blend(sd.o, sd.h, sd.l, sd.c, a, b - 1, "bull")
    if z is None:
        return False
    if z.src < b and (sd.c[z.src:b] < z.bottom).any():
        return False                                  # a close below the block broke it
    return z.bottom <= entry <= z.top


def post_order(ctx, sd, i: int, p, session: str, o_: dict, hist):
    """Filter / tag an order armed on bar i (None = rejected):
      T7 macro_gate / Ep07.8 macro_only (+ macro_by)   armed (or its sweep started) inside a macro window
      T7 macro_done_skip / moc_htf_done                 the day's run is done: the macro does nothing
      T4 / D1 or_no_entry (+ or_deep)                   AM orders fill from or_end; the pending expiry counts from then
      T9 pm_continue_am "tag", pm_ob_entry              tags / the AM-OB filter
      N3.3 fomc_only_am "tag" / "scalp"                 tag
    Tags go into the order's lv_tags (a funnel key `x_<reason>` counts a rejection); the macro windows go into the
    order's `macro_wins` (Trade.macro_wins)."""
    from .strategy import _f, _idx_at
    t = int(ctx.t[i])
    tags = []
    from . import nct2 as _N2
    if (p.macro_gate or p.macro_only != "off") and not (p.macro_trend_off and _N2.trend_day_nr(ctx, i)):     # caption-gap T7-no-macro-trending (025 ~00:59:10): a trending day has no macro signature - the gate is waived
        wins = (MACRO_0950,) if p.macro_only == "0950" else _N2.macro_wins_for(p)          # (caption-gap T7-macro-start-only-all: macro_gate_set picks the windows)
        tm = t if p.macro_by == "arm" else int(ctx.t[o_.get("ext_i", i)])
        if not _in(wins, tm):
            _f("x_macro_gate")
            return None
    if p.macro_done_skip and macro_wins(t, p) and run_done(ctx, i, p):
        _f("x_macro_done")
        return None
    if p.moc_htf_done and session == "PM" and p.last_hour_sweet[0] <= t < p.last_hour_sweet[1] and run_done(ctx, i, p):
        _f("x_moc_htf_done")
        return None
    if p.or_no_entry and session == "AM" and t < p.or_end:
        news1000 = any(r in (585, 600) for r in releases(ctx.day, p))
        if not news1000 or p.or_no_entry_news1000:
            o_["fill_from"] = p.or_end
            o_["anchor_i"] = _idx_at(ctx, p.or_end)
            if p.or_deep and hist:
                prev = hist[-1]
                hi, lo = float(prev.high.max()), float(prev.low.min())
                real = sd.x(o_["entry"])
                pos = ((real - lo) if sd.sign > 0 else (hi - real)) / (hi - lo) if hi > lo else 1.0
                if pos <= p.or_deep_pd:
                    o_["fill_win"] = (tuple(p.or_deep_win),)
                    tags.append("or_deep")
    if session != "PM" and p.or_bias != "off" and not p.or_bias_filter and t >= p.or_end:
        b = or_dir(ctx, p.or_bias, p.or_end)               # T4 or_bias_filter=False: tag only
        tags.append("or_bias_with" if b and sd.sign == b else "or_bias_against" if b else "or_bias_flat")
    if session == "PM":
        if p.pm_continue_am == "tag":
            b = am_dir(ctx, p)
            tags.append("pm_cont_am" if b and sd.sign == b else "pm_vs_am" if b else "pm_am_flat")
        if p.pm_ob_entry != "off":
            ok = _ob_before_pm(ctx, sd, i, o_["entry"])
            if not ok and p.pm_ob_entry == "require":
                _f("x_pm_ob_entry")
                return None
            if ok:
                tags.append("pm_ob")
    if session != "PM" and p.fomc_only_am in ("tag", "scalp") and CAL.fomc_info(ctx.day)["only"]:
        tags.append("fomc_only_am")
    t2_, why2_ = _N2.order_tags(ctx, sd, i, p, session, o_)       # caption-gap pass news_calendar_times#1/1: tags and order filters
    if why2_ is not None:
        _f(why2_)
        return None
    tags += t2_
    mw = macro_wins(t, p)
    if mw:
        o_["macro_wins"] = "|".join(mw)               # T7 multi-tag: every macro window the order was armed in
    if tags:
        o_["lv_tags"] = "|".join(dict.fromkeys(x for x in (o_.get("lv_tags", ""), *tags) if x))
    return o_


def scalp_now(ctx, p, session: str) -> bool:
    """N3.3 fomc_only_am="scalp": an AM order on an FOMC-only day is one scalp exit min(+5, T1), no adds."""
    return bool(p.fomc_only_am == "scalp" and session != "PM" and CAL.fomc_info(ctx.day)["only"])


def fill_ok(o: dict, t: int, tf: int = 0) -> bool:
    """T4 / D1: an OR order (fill_from) fills from that minute, or inside its or_deep window. With tf the window
    is read at the bar's CLOSE (t + tf in (a, b]), so 09:37-09:46 on 5m bars admits the bars closing 09:40 and 09:45."""
    ff = o.get("fill_from")
    if ff is None or t >= ff:
        return True
    if tf:
        return any(a < t + tf <= b for a, b in (o.get("fill_win") or ()))
    return any(a <= t < b for a, b in (o.get("fill_win") or ()))


# ---------------------------------------------------------------------------------------------------
# FOMC observation (N3.1)
# ---------------------------------------------------------------------------------------------------

def first_pm_minute(p) -> int:
    """The first FOMC-day PM minute entries are allowed (fomc_pm_from, or fomc_judas_end with the Judas rule)."""
    f = p.fomc_pm_from
    if p.fomc_judas or p.fomc_observe == "judas":
        f = min(f, p.fomc_judas_end) if f else p.fomc_judas_end
    return f


def observing(p, day, session: str, t: int) -> bool:
    """N3.1 fomc_observe: an FOMC-day PM bar in 14:00 .. the first allowed minute - scan, hold the order."""
    if p.fomc_observe == "off" or session != "PM" or t < 840 or not CAL.fomc_info(day)["fomc"]:
        return False
    return t < first_pm_minute(p)


def held_valid(ctx, sd, held: dict, i: int, p) -> bool:
    """A held FOMC order is armed at the first allowed bar if price has not traded back to its entry since it was
    armed (it would have filled in the observation window) and has not run to its target; with the Judas rule its
    side must not be the Judas side."""
    j = held["i"]
    if i - 1 > j and sd.l[j + 1:i].min() <= held["entry"]:
        return False
    if i - 1 > j and sd.h[j + 1:i].max() >= held["t1"]:
        return False
    if (p.fomc_judas or p.fomc_observe == "judas") and CAL.fomc_info(ctx.day)["fomc"]:
        fr = first_run(ctx, 840, p.news_judas_ref_min, end=p.fomc_judas_end)
        if fr["ref"] and fr["k"] is not None and sd.sign == fr["dir"]:
            return False
    return True


# ---------------------------------------------------------------------------------------------------
# T8: the carried draw
# ---------------------------------------------------------------------------------------------------

def _carry_erased(ctx, am: dict, lk: dict, tick: float = 0.25) -> bool:
    """T8-pm-carry-condition (029 ~1:30:37): the AM draw (side +1 = up) is NOT carried when, after the AM extreme (the AM session's high for an up draw, low for a down draw), price has traded
    a tick through the AM leg's origin (the AM session's low / high) before the PM lock. Measuring 'erased' as a retrace to the AM leg origin is our interpretation. Bars before 13:30 only."""
    from . import sm2
    from .strategy import _idx_at
    sm2.hit("eval_pm_carry")
    a, b = _idx_at(ctx, 570), _idx_at(ctx, int(lk.get("t_lock") or 810))      # (only the bars closed by the PM lock time)
    if b - a < 2:
        return False
    up = am["side"] > 0
    h, l = ctx.h[a:b], ctx.l[a:b]
    k = int(np.argmax(h)) if up else int(np.argmin(l))
    origin = float(l[:k + 1].min()) if up else float(h[:k + 1].max())          # the AM leg's origin: the extreme before the AM extreme [our interpretation: there is no ctx.am_leg object; sm2.am_leg gives only the whole 09:30-12:00 range]
    tail = l[k:] if up else h[k:]
    erased = bool(tail.min() <= origin - tick + 1e-9) if up else bool(tail.max() >= origin + tick - 1e-9)
    if erased:
        sm2.hit("pm_carry_erased")
    return erased


def carry_lock(ctx, p, name: str, lk: dict) -> dict:
    """T8 pm_carry_draw (029 ~1:29:48; 031 ~1:04:22): the PM lock keeps the AM's draw when the AM's lock is
    still undelivered at the PM's lock time. Only side / target / kind / name are carried; the mark-up (the
    ladder rungs) is the PM's own."""
    if name != "PM" or not (p.pm_carry_draw or p.range_day_mode == "pm_only"):          # (caption-gap B17-range-day-sit-out-am, bias_htf#4/7: a range day trades the PM only, with the AM's draw)
        return lk
    if not p.pm_carry_draw:
        from . import bh4e as _B4
        if not _B4.range_day(ctx):
            return lk
    am = (getattr(ctx, "lock", None) or {}).get("AM")
    if am is None or not am.get("side") or am.get("delivered"):
        return lk
    px, tgt = lk["px"], am["target"]
    if (tgt > px) != (am["side"] > 0):                # the draw already lies behind the price
        return lk
    if p.pm_carry_erase and _carry_erased(ctx, am, lk, float(p.tick)):    # caption-gap T8-pm-carry-condition (029 ~1:30:37): the AM move was erased - no carried draw
        return lk
    lk.update(side=am["side"], target=tgt, kind=am["kind"], name=am["name"], carried=True)
    return lk


# ---------------------------------------------------------------------------------------------------
# the Silver Bullet windows
# ---------------------------------------------------------------------------------------------------

def sb_start(p, day, session: str, a: int, b: int) -> int:
    """N3.1: on an FOMC day the Silver Bullet PM window (14:00-15:00) opens at max(a, fomc_pm_from) - the release and the
    observation window are out - when `sb_fomc_pm` is on (default off: the old build skipped the window)."""
    if session == "PM" and p.sb_fomc_pm and CAL.fomc_info(day)["fomc"]:
        return max(a, first_pm_minute(p))
    return a


def sb_gate(ctx, p, day, session: str, a: int) -> bool:
    """N3.2 fomc_am="recipe" for a Silver Bullet window: True when the recipe fails (the window is skipped)."""
    if session != "PM" and p.fomc_am == "recipe" and CAL.fomc_info(day)["fomc"]:
        i = min(len(ctx.t) - 1, ctx.start + int(np.searchsorted(ctx.t[ctx.start:], a)))
        return not recipe_ok(ctx, i)
    return False
