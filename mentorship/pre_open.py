"""Ma Deuce (091 ~17:20-26:47; mentorship/digests/pre_open_entries.md section E). Test-only.

Bearish version (the bullish one mirrors it):
  context  the most recent daily BISI - a bullish daily FVG whose third candle is one of the last
           two regular sessions - with price (at 08:00) in its premium half, above the CE.
  setup    a bullish 1m FVG formed after midnight is inverted (a close below its bottom) before
           08:00. "I want to see price get to 8:00" - no short on the first break.
  entry    08:00-08:30: sell a retest of the inverted FVG at its bottom edge (limit).
  stop     above the inverted FVG's top (inference; he gives none).
  target   the daily BISI's CE; needs >= sb_room_pts of room (room gate only; target is the CE,
           owner #2). Capped before an unbroken opposing HTF FVG (owner #7); with the draw lock
           (owner #9) only toward the draw locked at 08:00, target = the nearer of CE and draw.
One trade a day; out at 12:00 (owner #8, am_exit) or at the session close. Daily candles are
the regular sessions in `hist`.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import levels as L


def run_ma_deuce(ctx, hist, p, day, symbol, btag: dict) -> list:
    from .strategy import (Trade, _first_units, news, day_type, _eff_flat, _stamp_frame,
                           mark_levels, CF_SRC)
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
    if sign in getattr(ctx, "block_side", {}).get("year_end", ()):
        return []                                      # owner #3 (off by default)
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
    lock = None
    if p.draw_lock == "session":                       # owner #9 [our interpretation]: Ma Deuce
        lock = mark_levels(ctx, getattr(ctx, "bias_by_cut", {}).get(480), 480, "MD", p, ())
        ctx.lock["MD"] = lock                          # decides at 08:00 - its own 08:00 lock
        if (lock["side"] == 0 and p.draw_lock_neutral == "skip") or (lock["side"] and lock["side"] != sign):
            return []
        if lock["side"]:
            tv = sign * lock["target"]
            T = tv + p.pool_beyond_pts * p.es_pt if (p.exit_mode == "split" and lock["kind"] == "pool") \
                else tv - p.exit_before_pts * p.es_pt
            target = min(target, T)                    # the nearer of the CE and the draw
    capped = False
    if p.htf_resist_cap and getattr(ctx, "conf", None) is not None:      # owner #7 at 08:00
        r = ctx.conf.resistance(ctx.idx[k8], sign * entry, sign, p.htf_resist_tfs,
                                tuple(CF_SRC[x] for x in p.htf_resist_src))
        if r is not None:
            capx = sign * r[0] - p.htf_resist_buffer_pts * p.es_pt
            if capx < target:
                if capx - entry < p.sb_room_pts * p.es_pt:
                    return []
                target, capped = capx, True
    # side space: the target (the daily gap's CE) lies beyond the entry for both directions
    if target - entry < p.sb_room_pts * p.es_pt:
        return []
    chop = getattr(ctx, "chop", None)
    sloppy = set(r for r in getattr(ctx, "sl_day", ()) if not r.endswith(":PM"))
    if p.sloppy_mode == "scalp" and sloppy:
        target = min(target, entry + p.sloppy_scalp_pts * p.es_pt)      # #10 scalp mode
    shares = _first_units(p, ctx.equity, risk, entry)
    if shares < 1:
        return []
    flat = _eff_flat(p)
    x = lambda v: sign * v
    tr = None
    left = 0
    fill = None
    tightened = False
    for i in range(k8, len(t)):
        if tr is None:
            if i >= k830:
                return []
            if p.sloppy_mode == "stand_aside" and chop is not None and chop.active_before(i):
                return []                              # #10: chop known before this bar
            if sl[i] <= entry:                       # retest fills the limit
                fill = min(entry, so[i])
                on_chop = chop is not None and chop.active_before(i)
                if p.sloppy_mode == "scalp" and on_chop:
                    target = min(target, entry + p.sloppy_scalp_pts * p.es_pt)
                tag = "|".join(sorted(sloppy | ({"chop"} if on_chop else set())))
                tr = Trade(day, symbol, "AM", "ma_deuce", "long" if sign > 0 else "short", "daily_fvg",
                           False, None, ctx.idx[k8], ctx.idx[i], x(fill), x(stop), x(target), None,
                           shares, day_type=day_type(day), news=news(day), weekday=day.weekday(),
                           capped=capped, sloppy=tag,
                           draw_side=0 if lock is None else lock["side"],
                           draw_px=None if lock is None else lock["target"],
                           draw_name="" if lock is None else lock["name"],
                           draw_kind="" if lock is None else lock["kind"], **btag)
                tr.entry_risk_pct = tr.peak_risk_pct = (round(shares * (fill - stop) / ctx.equity, 5)
                                                        if ctx.equity else None)
                _stamp_frame(ctx, tr, i)
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
        if p.am_exit and p.am_exit_extras and t[i] + ctx.tf >= p.am_exit:   # owner #8
            if p.am_exit_mode == "close":
                tr.exits.append((ctx.idx[i], x(sc[i]), left, "am_exit")); return [tr]
            if not tightened:
                tightened = True
                new = max(stop, fill, sl[i] - p.stop_buffer)
                if new >= sc[i]:
                    tr.exits.append((ctx.idx[i], x(sc[i]), left, "am_exit")); return [tr]
                stop = new
        if t[i] + ctx.tf >= flat:
            tr.exits.append((ctx.idx[i], x(sc[i]), left, "eod")); return [tr]
    if tr is not None:
        tr.exits.append((ctx.idx[-1], x(sc[-1]), left, "eod"))
        return [tr]
    return []
