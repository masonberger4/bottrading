"""Ma Deuce (091 ~17:20-26:47; mentorship/digests/pre_open_entries.md section E). Test-only.

Bearish version (the bullish one mirrors it):
  context  the most recent daily BISI - a bullish daily FVG whose third candle is one of the last
           two regular sessions - with price (at 08:00) in its premium half, above the CE.
  setup    a bullish 1m FVG formed after midnight is inverted (a close below its bottom) before
           08:00. "I want to see price get to 8:00" - no short on the first break.
  entry    08:00-08:30: sell a retest of the inverted FVG at its bottom edge (limit).
  stop     above the inverted FVG's top (inference; he gives none).
  target   the daily BISI's CE; needs >= sb_room_pts of room.
One trade a day; flat by 16:00. Daily candles are the regular sessions in `hist`.
"""
from __future__ import annotations

import numpy as np

from . import levels as L


def run_ma_deuce(ctx, hist, p, day, symbol, btag: dict) -> list:
    from .strategy import Trade, _lots, news, day_type
    if len(hist) < 3:
        return []
    hh = np.array([float(x.high.max()) for x in hist[-4:]])
    ll = np.array([float(x.low.min()) for x in hist[-4:]])
    zones = [z for z in L.fvgs(hh, ll) if z.i >= len(hh) - 2]
    if not zones:
        return []
    z = zones[-1]                                     # the most recent daily FVG
    t = ctx.t
    k8 = ctx.start + int(np.searchsorted(t[ctx.start:], 480))
    k830 = ctx.start + int(np.searchsorted(t[ctx.start:], 510))
    if k8 >= len(t) or k8 <= ctx.start:
        return []
    px = ctx.c[k8 - 1]
    if z.kind == "bull" and px > z.mid:
        sign = -1                                      # premium of a daily BISI -> sell
    elif z.kind == "bear" and px < z.mid:
        sign = 1                                       # discount of a daily SIBI -> buy
    else:
        return []
    o, h, l, c = ctx.o, ctx.h, ctx.l, ctx.c
    if sign < 0:
        so, sh, sl, sc = -o, -l, -h, -c                # side space: a short is a mirrored long
    else:
        so, sh, sl, sc = o, h, l, c
    target = sign * z.mid
    # 1m gaps against the trade (bullish in real terms for a short), formed after midnight, then
    # closed through before 08:00 -> inverted, now resistance (support in side space)
    inv = None
    for g in L.fvgs(sh, sl):
        if g.kind != "bear" or g.i < ctx.start or g.i >= k8:
            continue
        after = sc[g.i + 1:k8]
        if len(after) and (after > g.top).any():
            inv = g                                    # newest one inverted before 08:00
    if inv is None:
        return []
    entry = inv.top                                    # near edge from above (side space)
    stop = inv.bottom - p.stop_buffer
    # at 08:00 price must already be past the inverted gap (the retest comes later)
    if sc[k8 - 1] <= entry:
        return []
    risk = entry - stop
    if not (p.min_risk_pts * p.es_pt <= risk <= p.max_risk_pts * p.es_pt):
        return []
    # side space: the target (the daily gap's CE) lies beyond the entry for both directions
    if target - entry < p.sb_room_pts * p.es_pt:
        return []
    shares = _lots(min(p.risk_dollars / risk, p.max_notional / abs(entry)), p.lot)
    if shares < 1:
        return []
    x = lambda v: sign * v
    tr = None
    left = 0
    for i in range(k8, len(t)):
        if tr is None:
            if i >= k830:
                return []
            if sl[i] <= entry:                       # retest fills the limit
                fill = min(entry, so[i])
                tr = Trade(day, symbol, "AM", "ma_deuce", "long" if sign > 0 else "short", "daily_fvg",
                           False, None, ctx.idx[k8], ctx.idx[i], x(fill), x(stop), x(target), None,
                           shares, day_type=day_type(day), news=news(day), weekday=day.weekday(), **btag)
                left = shares
                if sl[i] <= stop:
                    tr.exits.append((ctx.idx[i], x(stop), left, "stop"))
                    return [tr]
                continue
            if sh[i] >= target:
                return []
            continue
        if so[i] <= stop:
            tr.exits.append((ctx.idx[i], x(so[i]), left, "stop_gap")); return [tr]
        if sl[i] <= stop:
            tr.exits.append((ctx.idx[i], x(stop), left, "stop")); return [tr]
        if sh[i] >= target:
            tr.exits.append((ctx.idx[i], x(target), left, "t1")); return [tr]
        if t[i] + ctx.tf >= p.flatten:
            tr.exits.append((ctx.idx[i], x(sc[i]), left, "eod")); return [tr]
    if tr is not None:
        tr.exits.append((ctx.idx[-1], x(sc[-1]), left, "eod"))
        return [tr]
    return []
