"""Caption-gap pass, package bias_htf#7/7 - ENGINE SIDE (models_setups_entries.md items 177, 178, 190, 205, 215; times_sessions_macros.md items 32, 42, 53, 65).

The bar-loop part: the side gates (London confirmation after a daily signal, the NY-continues-London gate), the order rules and tags (the sub-range exception and the top skip, the 15m %R tag, the NY-vs-London
tag, the PO3 Judas tag, the array-lost tag), the AM / day side inputs (the London breaker, the array-lost flip), the lock preference, the late-entry target cut, the CC day-trade preset and the weekly-flip
premise arrays. The columns they read are built by `bh7.py` inside `htf.table`. Nothing here reads a bar after the closed bar `i` the caller passes; every daily value is a table column or a completed-session
frame of `ctx.hist`.
Hooks (who calls them)
  side_ok        daycontext.side_ok tail     london_confirm, london_dir_gate
  order_ok       daycontext.order_ok tail    pd_subrange (top skip), wr15_tag, london_dir_tag, htf_bias="breaker" (po3_judas), array_lost_flip (tag)
  subrange_ok    bh2e.order_ok               pd_subrange relaxes pd_two_level
  want_adjust    bias_day.want_at            array_lost_flip, london_breaker_bias
  size_mult      bias_day.size_mult          london_confirm="half"
  targets_post   strategy._targets           late_obj_k
  lock_prefs     strategy._lock              array_lost_flip target
  day_params     strategy.run_day            cc_daytrade
  premise_extra  sm3.premise_sweep           weekly_flip_follow
Thresholds the sources never give are marked [our interpretation].
"""
from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd

from . import bh1e as B1
from . import bh2 as BH2
from . import bh7 as BH7
from . import levels as L

HITS = BH2.HITS
sw = BH2.sw
_n, _f, _row = B1._n, B1._f, B1._row

LONDON = (120, 300)            # 02:00-05:00 NY
HTF_TFS = ("4h", "D", "W", "M")


def hit(k: str) -> None:
    HITS[k] += 1


def _S():
    return B1._S()


def _c(ctx) -> dict:
    return ctx.__dict__.setdefault("_bh7e", {})


def on(p) -> bool:
    return bool(p.london_confirm != "off" or p.london_dir_gate or p.london_dir_tag or p.pd_subrange or p.wr15_tag or p.htf_bias == "breaker" or p.array_lost_flip)


def want_on(p) -> bool:
    return bool(p.array_lost_flip or p.london_breaker_bias)


def targets_on(p) -> bool:
    return bool(p.late_obj_k < 1.0)


def prefs_on(p) -> bool:
    return bool(p.array_lost_flip)


def _t(ctx, i: int) -> int:
    return int(ctx.t[i])


def _london_slice(ctx, i: int):
    """(j0, j1) bar range of today's London bars (02:00-05:00) closed by bar i; None without any."""
    ts = ctx.t
    st = ctx.start
    j0 = None
    j1 = None
    for j in range(st, min(i, len(ts) - 1) + 1):
        t = int(ts[j])
        if LONDON[0] <= t < LONDON[1]:
            if j0 is None:
                j0 = j
            j1 = j
    return None if j0 is None else (j0, j1)


# --------------------------------------------------------------------------------------------------------------
# new-london-confirm-after-daily-signal
# --------------------------------------------------------------------------------------------------------------

def outside_bisi(hist, p):
    """Yesterday's DOWN-close outside day that traded into a daily bullish FVG (BISI) formed before it - (dir, out_hi, out_lo, bisi_bottom, bisi_top) with dir = -1 [our interpretation of 'a down-close outside
    day into a daily inefficiency low': the outside day's low reached the BISI, the FVG being the latest one formed before the outside day that the outside day's low traded into]. The up-close outside day
    into a daily SIBI is the mirror (dir = +1; 'bullish mirror is our extension'). None otherwise. Completed sessions only (`hist`)."""
    if len(hist) < 5:
        return None
    from .daycontext import candle_patterns
    cp = candle_patterns(hist, p)
    if not cp.get("outside"):
        return None
    dr = -1 if cp["outside"] == "down" else 1
    o = np.array([float(x.open.iloc[0]) for x in hist])
    h = np.array([float(x.high.max()) for x in hist])
    l = np.array([float(x.low.min()) for x in hist])
    c = np.array([float(x.close.iloc[-1]) for x in hist])
    n = len(hist)
    j = n - 1                                                   # the outside day
    zs = [z for z in L.fvgs(h, l, o, c) if z.i <= j - 1 and z.kind == ("bull" if dr < 0 else "bear")]
    for z in reversed(zs):
        if dr < 0 and l[j] <= z.top and not (c[z.i + 1:j].size and c[z.i + 1:j].min() < z.bottom):
            return dr, float(h[j]), float(l[j]), float(z.bottom), float(z.top)
        if dr > 0 and h[j] >= z.bottom and not (c[z.i + 1:j].size and c[z.i + 1:j].max() > z.top):
            return dr, float(h[j]), float(l[j]), float(z.bottom), float(z.top)
    return None


def london_confirmed(ctx, dr: int, bot: float, top: float, i: int):
    """True / False / None (no London bars): London (02:00-05:00, closed bars through i) traded beyond the BISI low (SIBI high for dir=+1) AND a close came back beyond it after a retrace into it. dir=-1:
    a low under `bot`, later a high at / above `bot` (the retrace into the BISI) and later a close under `bot`. dir=+1: the mirror on `top`."""
    sl = _london_slice(ctx, i)
    if sl is None:
        return None
    j0, j1 = sl
    h, l, c = ctx.h, ctx.l, ctx.c
    stage = 0
    for j in range(j0, j1 + 1):
        if stage == 0 and ((dr < 0 and l[j] < bot) or (dr > 0 and h[j] > top)):
            stage = 1
        elif stage == 1 and ((dr < 0 and h[j] >= bot) or (dr > 0 and l[j] <= top)):
            stage = 2
        elif stage == 2 and ((dr < 0 and c[j] < bot) or (dr > 0 and c[j] > top)):
            return True
    return False


def london_state(ctx, p, sign: int, session: str, i: int):
    """None (no rule), or the state of the London confirmation for an order of side `sign`: 'ok' / 'unconfirmed' / 'invalid' (the outside day's extreme traded)."""
    if p.london_confirm == "off" or session == "PM" or _t(ctx, i) < LONDON[1]:
        return None
    c = _c(ctx)
    if "ob" not in c:
        c["ob"] = outside_bisi(getattr(ctx, "hist", []), p)
    ob = c["ob"]
    if ob is None or ob[0] != sign:
        return None
    dr, hi, lo, bot, top = ob
    dh = float(ctx.h[ctx.start:i + 1].max()) if dr < 0 else float(ctx.l[ctx.start:i + 1].min())
    if (dr < 0 and dh > hi) or (dr > 0 and dh < lo):
        return "invalid"
    ck = ("lc", int(i) if _t(ctx, i) < LONDON[1] + 5 else "done")
    if ck not in c:
        c[ck] = london_confirmed(ctx, dr, bot, top, i)
    ok = c[ck]
    if ok is None:
        return None                                              # no London bars in the frame: nothing to judge
    return "ok" if ok else "unconfirmed"


# --------------------------------------------------------------------------------------------------------------
# new-ny-continues-london
# --------------------------------------------------------------------------------------------------------------

def london_dir(ctx, i: int) -> int:
    """sign(05:00 close - 00:00 open) of today's frame [our interpretation of 'London direction']: the open of the first bar at / after 00:00 and the close of the last bar before 05:00; 0 without bars."""
    ts = ctx.t[ctx.start:i + 1]
    ok = np.flatnonzero(ts < LONDON[1])
    if not len(ok):
        return 0
    a = ctx.start
    b = ctx.start + int(ok[-1])
    if int(ctx.t[b]) + ctx.tf < LONDON[1] - 1:
        return 0
    return int(np.sign(ctx.c[b] - ctx.o[a]))


def london_at_array(ctx, p, d: int, i: int):
    """True when, at any closed bar of 07:00-09:30 through i, London's extreme side of the move (the high for an up move, the low for a down move) sat within 1 tick of a valid 4h / D / W / M array of the opposite
    (reversal) colour [our interpretation of 'reaches an HTF array']; None without the Confluence arrays."""
    cf = getattr(ctx, "conf", None)
    if cf is None or not hasattr(cf, "at"):
        return None
    for j in range(ctx.start, i + 1):
        t = int(ctx.t[j])
        if t < 420 or t >= 570:
            continue
        px = float(ctx.h[j]) if d > 0 else float(ctx.l[j])
        now = ctx.idx[j] + pd.Timedelta(minutes=ctx.tf)
        if any(tf in HTF_TFS for tf in cf.at(now, px, -d)):
            return True
    return False


def ny_state(ctx, p, session: str, i: int):
    """(london_dir, at_array) for an AM order, or None."""
    if session != "AM" or _t(ctx, i) < 420:
        return None
    d = london_dir(ctx, i)
    if not d:
        return None
    c = _c(ctx)
    k = ("nyl", i if _t(ctx, i) < 570 else "done")
    if k not in c:
        c[k] = (d, london_at_array(ctx, p, d, i))
    return c[k]


# --------------------------------------------------------------------------------------------------------------
# the side gate
# --------------------------------------------------------------------------------------------------------------

def side_ok(ctx, p, sign: int, session: str, i: int):
    """A funnel key when this side may not be traded at closed bar i for a bias_htf#7/7 reason, else None."""
    if i is None:
        return None
    if p.london_confirm != "off" and sign:
        st = london_state(ctx, p, sign, session, i)
        if st == "invalid":
            sw("london_confirm")
            return "x_bh7_london_invalid"
        if st == "unconfirmed" and p.london_confirm == "block":
            sw("london_confirm")
            return "x_bh7_london_confirm"
    if p.london_dir_gate and sign:
        ns = ny_state(ctx, p, session, i)
        if ns is not None and ns[1] is False and sign != ns[0]:
            sw("london_dir_gate")
            return "x_bh7_london_dir"
    return None


# --------------------------------------------------------------------------------------------------------------
# A21-longs-above-eq-subrange-discount
# --------------------------------------------------------------------------------------------------------------

def side_frac(sd, entry_raw: float, lo: float, hi: float) -> float:
    """The entry's position in the 60-session body range in SIDE terms (0 = the discount end for this side, 1 = the premium end)."""
    if not hi > lo:
        return float("nan")
    return (entry_raw - lo) / (hi - lo) if sd.sign > 0 else (hi - entry_raw) / (hi - lo)


def at_daily_array(ctx, sd, entry_raw: float, i) -> bool:
    """True when the entry price sits inside a live DAILY / WEEKLY array of the trade's colour (Confluence.at over D and W: known before the session, dead once a bar closed through it; an OB counts
    through its whole body, so its MT is inside it). [our interpretation of 'at a daily array (e.g. a daily OB MT)'.] False without the Confluence arrays."""
    cf = getattr(ctx, "conf", None)
    if cf is None or i is None or not hasattr(cf, "at"):
        return False
    now = ctx.idx[i] + pd.Timedelta(minutes=ctx.tf)               # bar i is closed
    return any(tf in ("D", "W") for tf in cf.at(now, float(entry_raw), int(sd.sign)))


def subrange_ok(ctx, sd, o: dict, row, entry_raw: float, p, i=None) -> bool:
    """pd_subrange: the order a pd_two_level rejection would block is allowed when its entry sits in the LOWER half of its quadrant of the 60-session body range, in quadrant 3 or 4 (side terms), at a live
    DAILY / WEEKLY array of its colour (at_daily_array; review fix: not the intraday 15m / 60m FVG tag) with a target left beyond the entry (o['t1']). The quadrant is the entry's, not the prior close's
    (table range_q). The range is the 60-session body range while the gate relaxed is pd_two_level's 20-session EQ: an entry above the 20-day EQ but in quadrant 1-2 of the 60-day range stays blocked."""
    if not p.pd_subrange or row is None:
        return False
    lo, hi = _f(row, "range_lo"), _f(row, "range_hi")
    fr = side_frac(sd, entry_raw, lo, hi)
    if fr != fr:
        return False
    q = min(4, max(1, int(fr * 4) + 1)) if fr >= 0 else 1
    lower_half = (fr * 4 - int(fr * 4)) < 0.5 if fr < 1 else False
    return bool(q >= 3 and lower_half and at_daily_array(ctx, sd, entry_raw, i) and o.get("t1") is not None and o.get("entry") is not None and float(o["t1"]) > float(o["entry"]))


def top_skip(ctx, sd, o: dict, row, entry_raw: float, p):
    """pd_top_skip: the upper half of quadrant 4 of the range (side terms) is skipped."""
    if not (p.pd_subrange and p.pd_top_skip) or row is None:
        return None
    lo, hi = _f(row, "range_lo"), _f(row, "range_hi")
    fr = side_frac(sd, entry_raw, lo, hi)
    if fr == fr and fr >= 0.875:
        sw("pd_subrange")
        return "x_bh7_pd_top"
    return None


# --------------------------------------------------------------------------------------------------------------
# B20-15m-williams-r-entry
# --------------------------------------------------------------------------------------------------------------

def wr15_extreme(ctx, sd, i: int, n_lb: int):
    """True when the 15m Williams %R(10) of the last COMPLETED 15m bar (side space) is the lowest (the most bearish; a short runs the mirror) of its last `n_lb` readings; None without ten completed bars. Report only."""
    from . import sm7
    g, ks = sm7._done_groups(ctx, sd, i, 15)
    if g is None or len(ks) < 10 + 1:
        return None
    _, _, _, _, h15, l15, c15 = g
    vals = []
    for q in range(9, len(ks)):
        w = ks[q - 9:q + 1]
        hh, ll = float(h15[w].max()), float(l15[w].min())
        vals.append(-100.0 * (hh - float(c15[w[-1]])) / (hh - ll) if hh > ll else -50.0)
    if len(vals) < 2:
        return None
    tail = vals[-n_lb:]
    return bool(vals[-1] <= min(tail) + 1e-9)


# --------------------------------------------------------------------------------------------------------------
# T13-po3-breaker-regime: the Judas tag
# --------------------------------------------------------------------------------------------------------------

def po3_judas(ctx, regime: int, i: int) -> bool:
    """London (02:00-05:00, closed bars) traded past the midnight open AGAINST the breaker regime (a bearish regime: a rally above the open; a bullish one: a drop below it)."""
    sl = _london_slice(ctx, i)
    if not regime or sl is None or int(ctx.t[i]) < LONDON[1]:
        return False
    mo = float(ctx.o[ctx.start]) if int(ctx.t[ctx.start]) <= 5 else None
    S = _S()
    m_ = S._open_known(ctx, "midnight", i)
    mo = m_ if m_ is not None else mo
    if mo is None:
        return False
    j0, j1 = sl
    return bool(ctx.h[j0:j1 + 1].max() > mo) if regime < 0 else bool(ctx.l[j0:j1 + 1].min() < mo)


# --------------------------------------------------------------------------------------------------------------
# the per-order rules and tags
# --------------------------------------------------------------------------------------------------------------

def order_ok(ctx, sd, o: dict, session: str, i: int, p):
    """A funnel key when the armed order `o` (side space) breaks a bias_htf#7/7 rule, else None. Adds tags to o['lv_tags']."""
    if not on(p) or i is None:
        return None
    row = _row(ctx, session, i)
    entry_raw = float(sd.x(o["entry"])) if o.get("entry") is not None else None
    tags: list = []
    if p.pd_subrange and entry_raw is not None:
        why = top_skip(ctx, sd, o, row, entry_raw, p)
        if why:
            return why
    if p.wr15_tag:
        ex = wr15_extreme(ctx, sd, i, int(p.wr_lookback))
        if ex is not None:
            sw("wr15_tag")
            if ex:
                tags.append("wr15_extreme")
    if p.london_dir_tag:
        ns = ny_state(ctx, p, session, i)
        if ns is not None:
            sw("london_dir_tag")
            tags.append("nyl_cont" if sd.sign == ns[0] else ("nyl_rev" if ns[1] else "nyl_rev_noarray"))
    if p.htf_bias == "breaker" and row is not None:
        rg = _n(row, "brk_react")
        if rg and po3_judas(ctx, rg, i):
            sw("htf_bias_breaker")
            tags.append("po3_judas")
    if p.array_lost_flip and row is not None and _n(row, "array_lost"):
        tags.append("array_lost")
    if tags:
        o["lv_tags"] = "|".join(dict.fromkeys(x for x in (o.get("lv_tags", ""), *tags) if x))
    return None


def size_mult(ctx, sd, i: int, p, lvt: list, session: str = "") -> float:
    """london_confirm='half': an unconfirmed London halves the risk of the order (risk_mult 0.5 in the spec)."""
    if p.london_confirm != "half":
        return 1.0
    session = session or getattr(ctx, "cur_session", "") or ("PM" if ctx.t[i] >= 810 else "AM")
    if london_state(ctx, p, sd.sign, session, i) == "unconfirmed":
        lvt.append("size_london_confirm")
        sw("london_confirm")
        return 0.5
    return 1.0


# --------------------------------------------------------------------------------------------------------------
# the side inputs
# --------------------------------------------------------------------------------------------------------------

def london_breaker(ctx, p, i: int) -> int:
    """new-london-breaker-precursor: +1 / -1 / 0. The last breaker (`levels.breakers`, known at its closing break) among the closed London bars: a bullish breaker whose closing break came 02:00-05:00 after a
    sweep of a swing low (the breaker is the last up-close candles before the run - levels.breaker_zone) = +1; a bearish one = -1. Read once London is complete (bar time >= 05:00)."""
    if int(ctx.t[i]) < LONDON[1]:
        return 0
    c = _c(ctx)
    if "lb" in c:
        return c["lb"]
    sl = _london_slice(ctx, i)
    v = 0
    if sl is not None:
        j0, j1 = sl
        zs = L.breakers(ctx.o[j0:j1 + 1], ctx.h[j0:j1 + 1], ctx.l[j0:j1 + 1], ctx.c[j0:j1 + 1], 2)
        if zs:
            z = max(zs, key=lambda z_: z_.i)
            v = 1 if z.kind == "bull" else -1
    c["lb"] = v
    return v


def want_adjust(ctx, p, session: str, i: int, v: int) -> int:
    """array_lost_flip (the day after a close through the planned daily array: against the daily bias until the target array traded, then back with it); london_breaker_bias (the AM side when the daily bias
    is neutral; an opposing daily bias stays)."""
    if p.array_lost_flip:
        row = _row(ctx, session, i)
        al = _n(row, "array_lost") if row is not None else 0
        tg = _f(row, "array_lost_tgt") if row is not None else float("nan")
        if al and tg == tg:
            touched = bool((ctx.l[ctx.start:i + 1].min() <= tg) if al > 0 else (ctx.h[ctx.start:i + 1].max() >= tg))
            sw("array_lost_flip")
            return al if touched else -al
    if p.london_breaker_bias and session == "AM" and v == 0:
        lb = london_breaker(ctx, p, i)
        if lb:
            row = _row(ctx, session, i)
            iof = _n(row, "iof") if row is not None else 0
            if iof != -lb:                                       # 'with bullish IOF': the daily order flow must not oppose [our interpretation]
                sw("london_breaker_bias")
                return lb
    return v


# --------------------------------------------------------------------------------------------------------------
# targets, lock preference, day parameters, premise arrays
# --------------------------------------------------------------------------------------------------------------

def targets_post(ctx, sd, i: int, p, above: float, lv: list) -> list:
    """late_obj_k (new-ipda-true-day, cc12_004: entries after the NY open get reduced objectives): for a bar at / after 09:30 keep only the rungs within late_obj_k x ADR5 of the entry (`above`); the nearest
    rung is always kept so the ladder is never empty."""
    if p.late_obj_k >= 1.0 or int(ctx.t[i]) < 570 or not lv:
        return lv
    from . import bh5e
    a5 = bh5e._adr5(ctx, p)
    if not a5:
        return lv
    lim = float(p.late_obj_k) * float(a5)
    kept = [(v, k) for v, k in lv if v - above <= lim + 1e-9]
    if not kept:
        far = [x for x in lv if x[0] > above]
        kept = [min(far)] if far else lv
    if len(kept) != len(lv):
        sw("late_obj_k")
    return kept


def lock_prefs(ctx, p, row, t_lock: int, session: str, S: int, px: float, kl: int) -> list:
    """array_lost_flip: the target array (the next lower / higher daily array) is the preferred lock candidate on the flipped day."""
    out = []
    if p.array_lost_flip and row is not None and _n(row, "array_lost"):
        v = _f(row, "array_lost_tgt")
        if v == v:
            out.append((v, "array", "array_lost_tgt", 0, S))
    return out


def day_params(p, tags):
    """cc_daytrade: AM leftovers out at 12:00 (am_exit), the PM session off, FOMC days PM 14:00-15:00 only."""
    if not p.cc_daytrade:
        return p
    hit("cc_daytrade")
    sw("cc_daytrade")
    return replace(p, am_exit=720, pm=(840, 900) if "fomc" in tags else (0, 0))


def premise_extra(ctx, p, sd, i: int, session: str) -> tuple:
    """weekly_flip_follow: ('4h',) when the table's stateful bias turned to this side inside the week (flip_turn), else ()."""
    if not p.weekly_flip_follow:
        return ()
    row = _row(ctx, session, i)
    if row is not None and _n(row, "flip_turn") == sd.sign:
        sw("weekly_flip_follow")
        return ("4h",)
    return ()
