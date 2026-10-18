"""ICT's Silver Bullet as its own setup (mentorship/digests/silver_bullet.md; 044, 054, 057,
058, 059, 060, 065B, 090).

Per window (AM 10:00-11:00, PM 14:00-15:00; London 03:00-04:00 optional, futures only):
  draw    the nearest untaken liquidity/array beyond the entry (PDH/PDL, session H/L, opening
          range, NWOG/NDOG/ORG levels, HTF arrays - the bot's target list); it must offer at
          least `sb_room_pts` ES points (10 for new traders, 5 for experienced, 046).
  trigger displacement toward the draw: a close beyond the swing that led into the leg's
          extreme (MSS). A liquidity sweep is not required (tagged when present).
  FVG     faces the trade, sits beyond the broken swing, still open, formed after the leg's
          extreme - it may come from the 09:30-10:00 (13:30-14:00) leg (058 ~44:37, 065B).
          Evolving SB (057): the newest such FVG price has not yet traded back into.
  entry   limit at the FVG's near edge, fills only inside the window; cancelled if the target
          trades first or at the window end.
  stop    below the FVG's first candle low and the order block mean threshold (090).
  exit    +`sb_target_pts` (5 ES handles) or the draw if nearer; optional runner to the draw
          with the stop at breakeven. Flat by 16:00.
  count   one Silver Bullet per window, independent of the bot's other setups.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import levels as L


def run_sb(ctx, sides, p, day, symbol, blocked, btag: dict) -> list:
    from .strategy import Trade, _targets, _eq_levels, _lots, news, day_type, _f   # noqa: avoid cycle
    wins = [("AM", "sb_am", p.sb_windows[0], 570), ("PM", "sb_pm", p.sb_windows[1], 810)]
    if p.sb_london:
        wins.insert(0, ("AM", "sb_london", (180, 240), 120))
    out = []
    tol = p.eq_tol_pts * p.es_pt
    for session, setup, (a, b), leg_from in wins:
        if p.day_filter and blocked(day, session, p, a):
            continue
        idx = [k for k in range(ctx.start, len(ctx.t)) if leg_from <= ctx.t[k] < 960]
        if not idx:
            continue
        k0 = idx[0]
        pending = pos = None
        for i in idx:
            t = ctx.t[i]
            ts = ctx.idx[i]
            if pos is not None:                       # manage the open trade
                sd = pos["side"]
                o, h, l, c = sd.o[i], sd.h[i], sd.l[i], sd.c[i]
                tr = pos["trade"]
                if o <= pos["stop"]:
                    tr.exits.append((ts, sd.x(o), pos["left"], "stop_gap")); pos["left"] = 0
                elif l <= pos["stop"]:
                    tr.exits.append((ts, sd.x(pos["stop"]), pos["left"], "be" if pos["t1_done"] else "stop"))
                    pos["left"] = 0
                elif p.sb_mgmt == "ladder":            # bread and butter at +5, then scale out
                    lv_, fr = pos["levels"], p.ladder_fracs
                    while pos["k"] < len(lv_) and pos["left"] and h >= lv_[pos["k"]]:
                        k = pos["k"]
                        q = pos["left"] if k == len(lv_) - 1 else min(pos["left"], max(p.lot, _lots(pos["n"] * fr[k], p.lot)))
                        tr.exits.append((ts, sd.x(lv_[k]), q, f"t{k + 1}")); pos["left"] -= q
                        pos["k"] += 1
                        if not pos["t1_done"]:
                            pos["t1_done"] = True
                            pos["stop"] = max(pos["stop"], pos["entry"])
                        pos["away"] = lv_[k]
                    if pos["left"] and pos["away"] is not None and c >= pos["away"] + p.away_pts * p.es_pt:
                        pos["stop"] = max(pos["stop"], pos["away"] - p.stop_buffer)
                        pos["away"] = None
                else:
                    if not pos["t1_done"] and h >= pos["t1"]:
                        q = pos["left"] if pos["t2"] is None else max(p.lot, _lots(pos["left"] * 0.8, p.lot))
                        q = min(q, pos["left"])
                        tr.exits.append((ts, sd.x(pos["t1"]), q, "t1")); pos["left"] -= q
                        pos["t1_done"] = True
                        pos["stop"] = max(pos["stop"], pos["entry"])
                    if pos["left"] and pos["t2"] is not None and pos["t1_done"] and h >= pos["t2"]:
                        tr.exits.append((ts, sd.x(pos["t2"]), pos["left"], "t2")); pos["left"] = 0
                if pos["left"] and t + ctx.tf >= p.flatten:
                    tr.exits.append((ts, sd.x(c), pos["left"], "eod")); pos["left"] = 0
                if not pos["left"]:
                    out.append(tr)
                    pos = None
                    break                             # one Silver Bullet per window
                continue
            if pending is not None:                   # working limit order
                sd = pending["side"]
                if t >= b:
                    pending = None                    # window over: cancel
                elif t < a and sd.l[i] < pending["entry"]:
                    pending = None                    # traded into before the window: not valid
                elif sd.h[i] >= pending["t1"] and sd.l[i] >= pending["entry"]:
                    pending = None                    # target traded before the fill
                if pending is not None and a <= t < b and sd.l[i] < pending["entry"]:
                    o_ = pending
                    fill = min(o_["entry"], sd.o[i])
                    tr = Trade(day, symbol, session, setup, "long" if sd.sign > 0 else "short",
                               o_["swept"], False, None, ctx.idx[o_["i"]], ts, sd.x(fill), sd.x(o_["stop"]),
                               sd.x(o_["t1"]), None if o_["t2"] is None else sd.x(o_["t2"]), o_["shares"],
                               day_type=day_type(day), news=news(day), sb=True, weekday=day.weekday(),
                               **btag)
                    pos = dict(trade=tr, side=sd, stop=o_["stop"], t1=o_["t1"], t2=o_["t2"],
                               left=o_["shares"], entry=fill, t1_done=False, n=o_["shares"],
                               levels=o_["levels"], k=0, away=None)
                    pending = None
                    if sd.l[i] <= pos["stop"]:
                        tr.exits.append((ts, sd.x(pos["stop"]), pos["left"], "stop")); pos["left"] = 0
                        out.append(tr)
                        pos = None
                        break
                    continue
            if t >= b:
                if pending is None:
                    break
                continue
            # (re)arm on the closed bar: newest qualifying FVG (evolving SB)
            best = None
            for sd in sides:
                o_ = _arm(ctx, sd, i, k0, p, tol)
                if o_ is not None and (best is None or o_["fvg_i"] > best["fvg_i"]):
                    best = o_
            if best is not None and (pending is None or best["fvg_i"] != pending["fvg_i"]
                                     or best["side"] is not pending["side"]):
                pending = best
        if pos is not None:                           # data ended
            out.append(pos["trade"])
    return out


def _arm(ctx, sd, i, k0, p, tol):
    from .strategy import _targets, _eq_levels, _lots, _f
    l, h, c = sd.l, sd.h, sd.c
    if i <= k0 + 2:
        return None
    li = k0 + int(np.argmin(l[k0:i + 1]))             # the leg's extreme since the leg start
    if li >= i:
        return None
    refs = [q for q in sd.ph if q.i < li and q.known <= i]
    if not refs:
        return None
    ref = refs[-1].price
    if not (c[li + 1:i + 1] > ref).any():             # displacement closed beyond the swing (MSS)
        return None
    gaps = [g for g in sd.gaps if li <= g.i - 2 and g.i <= i and g.top > ref
            and c[g.i + 1:i + 1].min(initial=np.inf) >= g.bottom          # still open
            and l[g.i + 1:i + 1].min(initial=np.inf) > g.top]             # not yet traded back in
    if not gaps:
        return None
    g = gaps[-1]                                       # evolving: the newest untouched FVG
    entry = g.top
    ob = L.order_block_blend(sd.o, h, l, c, li - 3, g.i - 2, "bull")
    stop = l[g.i - 2]
    if ob is not None and ob.mt == ob.mt:
        stop = min(stop, ob.mt)
    stop -= p.stop_buffer
    risk = entry - stop
    if not (p.min_risk_pts * p.es_pt <= risk <= p.max_risk_pts * p.es_pt):
        return None
    eq_hi = _eq_levels(sd, i, tol, lows=False)
    lv = _targets(ctx, sd, i, entry, eq_hi, p, None, li)
    draws = [v for v, kind in lv if v > entry]
    if not draws:
        return None
    draw = draws[0]
    if draw - entry < p.sb_room_pts * p.es_pt:
        return None                                    # not enough room (the 10 / 5 framework)
    t1 = min(entry + p.sb_target_pts * p.es_pt, draw - p.exit_before_pts * p.es_pt)
    if t1 - entry < p.min_rr * risk * p.sb_min_rr:
        return None
    t2 = draw if p.sb_runner and draw > t1 + p.es_pt else None
    shares = _lots(min(p.risk_dollars / risk, p.max_notional / abs(entry)), p.lot)
    if shares < 1:
        return None
    lo_seg = l[k0:li + 1].min()
    swept = "none"
    for name, v in ctx.pd.items():                      # tag a sweep of a prior level
        lv_ = sd.x(v)
        if name.startswith(("pdl", "pml")) and sd.sign > 0 and lo_seg < lv_:
            swept = name
        if name.startswith(("pdh", "pmh")) and sd.sign < 0 and lo_seg < lv_:
            swept = name
    levels = [t1] + [v for v in draws if v > t1 + p.es_pt][:2]
    return dict(side=sd, i=i, fvg_i=g.i, entry=entry, stop=stop, t1=t1, t2=t2, shares=shares,
                swept=swept, levels=levels)
