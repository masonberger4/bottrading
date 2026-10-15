"""The 2023 Mentorship model as a bar-by-bar state machine (America/New_York times).

Setups
  AM  09:30-11:00  market maker buy/sell model: a sweep of sell-side (buy-side) liquidity
                   (previous 3 days' lows/highs, the pre-market low/high, relative equal
                   lows/highs), then a market structure shift: a candle body closes through
                   the swing high (low) that led into the sweep, with displacement leaving
                   an FVG. Entry is a limit at that FVG ("unicorn" FVG inside the breaker
                   preferred). Longs only below the midnight open, shorts only above it.
  PM  13:30-15:50  the same model against the AM-session high/low and the 13:30 open as the
                   premium/discount reference. Entries 15:15-15:45 are tagged "last hour".
Risk     stop beyond the mean threshold of the nearest order block (last opposite-close
         candle before the displacement), else beyond the FVG; ~1% of $100k per trade.
Targets  nearest opposing liquidity that pays >= min_rr, exited 0.5 ES pt before the level;
         half off at T1 with the stop to breakeven, rest at T2; flat by 16:00.
Limits   one AM and one PM trade; after a loss, no trade in the opposite direction.
Days     no NFP day, no Wed PM/Thu/Fri of NFP week, no FOMC-day PM; on 10:00-release days
         AM entries start at 10:00 (08:30 releases are already out by 09:30).

The bearish side runs the bullish logic on mirrored prices (o,h,l,c -> -o,-l,-h,-c), so
both directions share one code path. A bar is used only after it closes: orders armed on
bar i can first fill on bar i+1. Ambiguous bars resolve against the trade (stop first).
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta

import numpy as np
import pandas as pd

from claude_hf.daytypes import JOBS, day_type, events
from . import levels as L

NEWS_1000 = {"ism_manufacturing", "ism_services", "jolts", "sentiment"}


@dataclass
class Params:
    pivot_n: int = 2               # swing confirmation, bars each side
    es_pt: float = 0.10            # instrument price units per ES point (SPY ~ ES / 10)
    eq_tol_pts: float = 0.5        # relative equal highs/lows tolerance, ES points
    exit_before_pts: float = 0.5   # exit this far in front of a liquidity target
    min_risk_pts: float = 1.0
    max_risk_pts: float = 15.0
    min_rr: float = 1.0
    partial: float = 0.5
    entry: str = "edge"            # "edge" (top of a BISI) or "ce" (50% of the gap)
    stop_mode: str = "ob_mt"       # "ob_mt" or "fvg"
    stop_buffer: float = 0.01
    fvg_wait: int = 2              # bars after the structure break to wait for an FVG
    pending_minutes: int = 30
    am: tuple = (570, 660)         # 09:30-11:00
    pm: tuple = (810, 950)         # 13:30-15:50 (no new entries after 15:50)
    last_hour: tuple = (915, 945)  # 15:15-15:45
    flatten: int = 960
    use_bias: bool = True
    day_filter: bool = True
    risk_dollars: float = 1000.0   # 1% of $100k
    max_notional: float = 400_000.0
    cost_per_share: float = 0.01   # commissions + slippage, each way
    ambiguous: str = "stop"        # a bar touching both stop and target: "stop" first, or "target"


def blocked(d: date, session: str) -> str | None:
    """Day-type rule that blocks this session, or None."""
    tags = events(d)
    if "jobs" in tags:
        return "nfp_day"
    mon = d - timedelta(days=d.weekday())
    jd = [j for j in JOBS if mon <= j <= mon + timedelta(days=4)]
    if jd and d.weekday() >= 3:
        return "nfp_week_thu_fri"
    if jd and d.weekday() == 2 and session == "PM":
        return "nfp_week_wed_pm"
    if "fomc" in tags and session == "PM":
        return "fomc_pm"
    return None


@dataclass
class Trade:
    date: date
    symbol: str
    session: str
    setup: str
    side: str
    swept: str
    unicorn: bool
    smt: bool | None
    armed: pd.Timestamp
    entry_time: pd.Timestamp
    entry: float
    stop: float
    t1: float
    t2: float | None
    shares: int
    exits: list = field(default_factory=list)   # (time, price, shares, reason)
    day_type: str = ""

    def pnl(self, cost: float) -> tuple[float, float]:
        s = 1 if self.side == "long" else -1
        gross = sum(s * (px - self.entry) * q for _, px, q, _ in self.exits)
        costs = cost * (self.shares + sum(q for *_, q, _ in self.exits))
        return gross, costs

    def row(self, cost: float) -> dict:
        gross, costs = self.pnl(cost)
        risk = self.shares * abs(self.entry - self.stop)
        d = {k: v for k, v in asdict(self).items() if k != "exits"}
        d.update(gross=round(gross, 2), costs=round(costs, 2), net=round(gross - costs, 2),
                 R=round((gross - costs) / risk, 3) if risk else 0.0,
                 exit_time=self.exits[-1][0], exit_reason="+".join(e[3] for e in self.exits))
        return d


class Side:
    """One direction of one day, in bullish terms (mirrored prices for shorts)."""

    def __init__(self, sign, o, h, l, c, n):
        self.sign = sign
        if sign > 0:
            self.o, self.h, self.l, self.c = o, h, l, c
        else:
            self.o, self.h, self.l, self.c = -o, -l, -h, -c
        self.ph, self.pl = L.pivots(self.h, self.l, n)
        self.gaps = [z for z in L.fvgs(self.h, self.l) if z.kind == "bull"]
        self.sweep = None
        self.n = n

    def x(self, price):
        return self.sign * price


class DayCtx:
    """Bars for one day (04:00-16:00) preceded by the previous session (RTH), plus the
    levels known before the open."""

    def __init__(self, df: pd.DataFrame, day: date, hist: list[pd.DataFrame], tf: int):
        prev = hist[-1]
        self.day, self.tf = day, tf
        frame = pd.concat([prev, df])
        self.idx = frame.index
        self.t = (self.idx.hour * 60 + self.idx.minute).values
        self.o, self.h, self.l, self.c = (frame[k].values.astype(float) for k in ("open", "high", "low", "close"))
        self.start = len(prev)
        self.opens = L.opens(df.index, df.open.values)
        self.pd = {}
        for k, hd in enumerate(reversed(hist[-3:]), 1):
            self.pd[f"pdh{k}"], self.pd[f"pdl{k}"] = float(hd.high.max()), float(hd.low.min())
        tt = df.index.hour * 60 + df.index.minute
        pre = df[(tt >= 240) & (tt < 570)]
        if len(pre):
            self.pd["pmh"], self.pd["pml"] = float(pre.high.max()), float(pre.low.min())
        am = df[(tt >= 570) & (tt < 810)]
        self.am_hl = (float(am.high.max()), float(am.low.min())) if len(am) else None
        self.nwog = []
        for a, b in zip(hist[-21:], hist[-20:] + [df]):
            if (b.index[0].date() - a.index[-1].date()).days >= 3 or b.index[0].weekday() < a.index[-1].weekday():
                rth = b[(b.index.hour * 60 + b.index.minute) >= 570]
                if len(rth):
                    self.nwog.append((float(a.close.iloc[-1]), float(rth.open.iloc[0])))
        self.nwog = self.nwog[-4:]


def _targets(ctx: DayCtx, sd: Side, i: int, above: float, eq: list[float]) -> list[float]:
    """Buy-side liquidity (in side terms) above `above`, known at bar i."""
    pdk = ("pdh1", "pdh2", "pdh3", "pmh") if sd.sign > 0 else ("pdl1", "pdl2", "pdl3", "pml")
    lv = [sd.x(ctx.pd[k]) for k in pdk if k in ctx.pd]
    lv += eq
    for a, b in ctx.nwog:
        lv += [sd.x(a), sd.x(b)]
    if ctx.t[i] >= 810 and ctx.am_hl:
        lv.append(sd.x(ctx.am_hl[0] if sd.sign > 0 else ctx.am_hl[1]))
    out = []
    for v in sorted(v for v in set(lv) if v > above):   # merge levels within ~1 ES point
        if not out or v - out[-1] > 1.0 * (ctx.pt if hasattr(ctx, "pt") else 0.1):
            out.append(v)
    return out


def _eq_levels(sd: Side, i: int, tol: float, lows: bool) -> list[float]:
    """Relative equal highs (lows) from swings confirmed by bar i and not yet traded through."""
    piv = sd.pl if lows else sd.ph
    out = []
    for p in piv:
        if p.known > i:
            break
        after = sd.l[p.i + 1:i + 1] if lows else sd.h[p.i + 1:i + 1]
        if (len(after) == 0) or (after.min() > p.price if lows else after.max() < p.price):
            out.append(-p.price if lows else p.price)
    lv = L.equal_levels(out, tol)
    return [-v for v in lv] if lows else lv


def run_day(df: pd.DataFrame, hist: list[pd.DataFrame], symbol: str, p: Params, tf: int,
            partner: tuple[pd.DataFrame, list[pd.DataFrame]] | None = None,
            log: list | None = None) -> list[Trade]:
    day = df.index[0].date()
    ctx = DayCtx(df, day, hist, tf)
    ctx.pt = p.es_pt
    pctx = DayCtx(partner[0], day, partner[1], tf) if partner is not None else None
    sides = [Side(1, ctx.o, ctx.h, ctx.l, ctx.c, p.pivot_n), Side(-1, ctx.o, ctx.h, ctx.l, ctx.c, p.pivot_n)]
    psides = None
    if pctx is not None:
        psides = {1: Side(1, pctx.o, pctx.h, pctx.l, pctx.c, p.pivot_n),
                  -1: Side(-1, pctx.o, pctx.h, pctx.l, pctx.c, p.pivot_n)}
        ppos = pd.Series(np.arange(len(pctx.idx)), index=pctx.idx)
    pt = p.es_pt
    tags = events(day)
    am_start = 600 if tags & NEWS_1000 else p.am[0]
    trades: list[Trade] = []
    done = {"AM": False, "PM": False}
    pending = None    # dict with order details
    pos = None        # open Trade + live stop / remaining shares
    lost_side = None
    for i in range(ctx.start, len(ctx.t)):
        t = ctx.t[i]
        ts = ctx.idx[i]
        # --- 1. manage the open position on this bar
        if pos is not None:
            tr, sd = pos["trade"], pos["side"]
            o, h, l, c = sd.o[i], sd.h[i], sd.l[i], sd.c[i]
            fresh = pos["fill_i"] == i
            stop = pos["stop"]
            if p.ambiguous == "target" and not fresh and o > stop and not pos["t1_done"] and h >= pos["t1"]:
                stop = -np.inf                        # optimistic bound: target before stop
            if not fresh and o <= stop:
                tr.exits.append((ts, sd.x(o), pos["left"], "stop_gap")); pos["left"] = 0
            elif l <= stop:
                tr.exits.append((ts, sd.x(stop), pos["left"], "stop" if stop != pos["entry"] else "be")); pos["left"] = 0
            elif not fresh:
                if not pos["t1_done"] and h >= pos["t1"]:
                    q = pos["left"] if pos["t2"] is None else max(1, int(tr.shares * p.partial))
                    q = min(q, pos["left"])
                    tr.exits.append((ts, sd.x(pos["t1"]), q, "t1")); pos["left"] -= q
                    pos["t1_done"] = True; pos["stop"] = pos["entry"]
                if pos["left"] and pos["t2"] is not None and pos["t1_done"] and h >= pos["t2"]:
                    tr.exits.append((ts, sd.x(pos["t2"]), pos["left"], "t2")); pos["left"] = 0
            if pos["left"] and t + tf >= p.flatten:
                tr.exits.append((ts, sd.x(c), pos["left"], "eod")); pos["left"] = 0
            if not pos["left"]:
                gross, costs = tr.pnl(p.cost_per_share)
                if gross - costs < 0:
                    lost_side = tr.side
                trades.append(tr); pos = None
        # --- 2. pending limit order
        if pending is not None:
            sd = pending["side"]
            cut = p.am[1] if pending["session"] == "AM" else p.pm[1]
            if t >= cut or i - pending["i"] > max(1, p.pending_minutes // tf):
                pending = None
            elif sd.h[i] >= pending["t1"] and sd.l[i] >= pending["entry"]:
                pending = None                       # ran to target without us
            elif sd.l[i] < pending["entry"] and pos is None:
                o = pending
                fill = min(o["entry"], sd.o[i])      # a gap through the limit fills at the open
                tr = Trade(day, symbol, o["session"], o["setup"], "long" if sd.sign > 0 else "short",
                           o["swept"], o["unicorn"], o["smt"], ctx.idx[o["i"]], ts, sd.x(fill),
                           sd.x(o["stop"]), sd.x(o["t1"]), None if o["t2"] is None else sd.x(o["t2"]),
                           o["shares"], day_type=day_type(day))
                pos = dict(trade=tr, side=sd, entry=fill, stop=o["stop"], t1=o["t1"], t2=o["t2"],
                           left=o["shares"], t1_done=False, fill_i=i)
                done[o["session"]] = True
                pending = None
                # same-bar stop check (conservative)
                if sd.l[i] <= pos["stop"]:
                    tr.exits.append((ts, sd.x(pos["stop"]), pos["left"], "stop")); pos["left"] = 0
                    lost_side = tr.side; trades.append(tr); pos = None
        # --- 3. setup detection on the closed bar
        if p.am[0] <= t < p.am[1]:
            session, w0 = "AM", am_start
        elif p.pm[0] <= t < p.pm[1]:
            session, w0 = "PM", p.pm[0]
        else:
            continue
        if t < w0 or done[session] or pos is not None:
            continue
        why = blocked(day, session) if p.day_filter else None
        if why:
            continue
        for sd in sides:
            sname = "long" if sd.sign > 0 else "short"
            if lost_side is not None and sname != lost_side:
                continue                              # no reversals after a loss
            o_ = _scan(ctx, sd, i, p, session, w0, pctx, psides, ppos if pctx is not None else None)
            if o_ is not None:
                pending = o_
                if log is not None:
                    log.append((ts, symbol, session, sname, o_["swept"], o_["entry"], o_["stop"]))
    if pos is not None:   # data ended early
        tr = pos["trade"]
        tr.exits.append((ctx.idx[-1], pos["side"].x(pos["side"].c[-1]), pos["left"], "eod"))
        trades.append(tr)
    return trades


def _sell_side(ctx: DayCtx, sd: Side, session: str) -> dict[str, float]:
    keys = ("pdl1", "pdl2", "pdl3") if sd.sign > 0 else ("pdh1", "pdh2", "pdh3")
    out = {k: sd.x(ctx.pd[k]) for k in keys if k in ctx.pd}
    if session == "AM":
        k = "pml" if sd.sign > 0 else "pmh"
        if k in ctx.pd:
            out["premarket"] = sd.x(ctx.pd[k])
    elif ctx.am_hl:
        out["am_session"] = sd.x(ctx.am_hl[1] if sd.sign > 0 else ctx.am_hl[0])
    return out


def _scan(ctx, sd: Side, i, p: Params, session, w0, pctx, psides, ppos):
    """Advance this side's sweep -> MSS -> FVG machine at bar i; return an order or None."""
    l, h, c = sd.l, sd.h, sd.c
    w0i = ctx.start + int(np.searchsorted(ctx.t[ctx.start:], w0))
    tol = p.eq_tol_pts * p.es_pt
    # levels valid at the window start (not traded through between creation and bar i-1)
    lv = _sell_side(ctx, sd, session)
    created = ctx.start if session == "AM" else ctx.start + int(np.searchsorted(ctx.t[ctx.start:], 810))
    for k, eq in enumerate(_eq_levels(sd, i - 1, tol, lows=True)):
        lv[f"rel_eq_lows{k}"] = eq
    sw = sd.sweep
    if sw is not None and sw["session"] != session:
        sw = sd.sweep = None
    def intact(k, v):   # not traded through between the level's creation and bar i-1
        a = created if k == "am_session" else ctx.start
        return k.startswith("rel_eq") or i <= a or l[a:i].min() >= v
    hit = [(k, v) for k, v in lv.items() if l[i] < v and intact(k, v)]
    if sw is None and hit:
        k, v = min(hit, key=lambda kv: kv[1])
        sw = sd.sweep = dict(session=session, name=k.rstrip("0123456789") if k.startswith("rel_eq") else k,
                             level=v, key=k, ext=l[i], ext_i=i, broke=None, sweep_i=i)
        sw["smt"] = _smt(ctx, sd, i, k, v, session, pctx, psides, ppos, w0)
    if sw is None:
        return None
    if l[i] < sw["ext"]:
        sw.update(ext=l[i], ext_i=i, broke=None)
    # reference: the swing high that led into the sweep extreme
    refs = [q for q in sd.ph if q.i < sw["ext_i"] and q.known <= i]
    if refs:
        ref_i, ref = refs[-1].i, refs[-1].price
    else:
        a = max(ctx.start, sw["ext_i"] - 3 * p.pivot_n)
        if a >= sw["ext_i"]:
            return None
        ref_i = a + int(np.argmax(h[a:sw["ext_i"]])); ref = h[ref_i]
    if sw["broke"] is None:
        if i > sw["ext_i"] and c[i] > ref:
            sw["broke"] = i
        else:
            return None
    gaps = [g for g in sd.gaps if g.i <= i and g.i - 2 >= sw["ext_i"]]
    if not gaps:
        if i - sw["broke"] >= p.fvg_wait:
            sd.sweep = None
        return None
    sd.sweep = None   # this sweep is consumed whether or not the order passes the filters
    bz = L.order_block(sd.o, h, l, c, ref_i - p.pivot_n, ref_i, "bear")   # breaker candle
    uni = [g for g in gaps if bz is not None and g.overlaps(bz)]
    g = (uni or gaps)[-1]
    entry = g.top if p.entry == "edge" else g.mid
    ob = L.order_block(sd.o, h, l, c, sw["ext_i"] - 3, g.src - 1, "bull")
    stop = g.bottom - p.stop_buffer
    if p.stop_mode == "ob_mt" and ob is not None and ob.mid < entry - p.min_risk_pts * p.es_pt:
        stop = min(stop, ob.mid - p.stop_buffer)
    risk = entry - stop
    if not (p.min_risk_pts * p.es_pt <= risk <= p.max_risk_pts * p.es_pt):
        return None
    if p.use_bias:
        ref_open = ctx.opens.get("midnight" if session == "AM" else "1330")
        if ref_open is not None and not entry < sd.x(ref_open):
            return None
    eq_hi = _eq_levels(sd, i, tol, lows=False)
    above = max(h[sw["ext_i"]:i + 1].max(), entry)
    lv = _targets(ctx, sd, i, above, eq_hi)
    lv = [v - p.exit_before_pts * p.es_pt for v in lv]
    lv = [v for v in lv if v - entry >= p.min_rr * risk]
    if not lv:
        return None
    shares = int(min(p.risk_dollars / risk, p.max_notional / abs(entry)))
    if shares < 1:
        return None
    t = ctx.t[i]
    setup = "am_mm" if session == "AM" else ("pm_last_hour" if p.last_hour[0] <= t < p.last_hour[1] else "pm")
    return dict(side=sd, session=session, setup=setup, swept=sw["name"], unicorn=bool(uni),
                smt=sw["smt"], i=i, entry=entry, stop=stop, t1=lv[0],
                t2=lv[1] if len(lv) > 1 else None, shares=shares)


def _smt(ctx, sd, i, key, level, session, pctx, psides, ppos, w0):
    """SMT divergence: the partner index did NOT take its own version of the swept level
    (by the same bar). None when there is no partner or the level has no partner twin."""
    if pctx is None or key.startswith("rel_eq"):
        return None
    ps = psides[sd.sign]
    plv = _sell_side(pctx, ps, session).get(key)
    if plv is None:
        return None
    ts = ctx.idx[i]
    j = ppos.index.searchsorted(ts, side="right") - 1
    if j < pctx.start:
        return None
    created = pctx.start + int(np.searchsorted(pctx.t[pctx.start:], 810)) if key == "am_session" else pctx.start
    if j < created:
        return None
    return bool(ps.l[created:j + 1].min() >= plv)
