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

setups_models M15 switches (all off; 091 ~19:02-26:47):
  md_big_candle  the daily BISI comes from ONE big candle: its middle candle closes in the gap's
                 direction with a range >= N x the mean range of the 5 daily candles before it
  md_second      the 2nd entry (a 2nd rejection of the inverted FVG - a touch after a close away
                 from it - or a new small SIBI before 08:30) is one add (adds[0] x size, 1.3% cap)
  md_ladder      targets: the BISI CE, its lower quadrant, then the low of the nearest 1h BISI below
                 (mirror for a SIBI), scaled out with ladder_fracs, stop to breakeven after the first
  md_need_news   only on 08:30 release days ("the 08:30 release delivers")
  md_eth         daily candles from the full ETH sessions (Ep08.1-style), RTH where missing
  md_blocked     route it through blocked() (day filter) and skip_news like the other setups
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import levels as L


def _dailies(ctx, hist, p, day, n: int):
    """The last n daily candles (o, h, l, c arrays): RTH sessions, or ETH ones with md_eth."""
    if p.md_eth and getattr(ctx, "eth", None):
        ds = sorted(d for d in ctx.eth if d < day)[-n:]
        rows = [ctx.eth[d] for d in ds]
    else:
        rows = [(float(x.open.iloc[0]), float(x.high.max()), float(x.low.min()), float(x.close.iloc[-1]))
                for x in hist[-n:]]
    a = np.array(rows, float).reshape(-1, 4)
    return a[:, 0], a[:, 1], a[:, 2], a[:, 3]


def _h1_gap_edge(ctx, sign, k8, beyond):
    """md_ladder: the far edge (side space) of the nearest same-direction-as-the-daily-gap 1h FVG
    beyond `beyond` (side space), complete by 08:00 (the 1h BISI low below for a short)."""
    from .strategy import htf_bars
    fr = pd.DataFrame({"open": ctx.o[:k8], "high": ctx.h[:k8], "low": ctx.l[:k8], "close": ctx.c[:k8]},
                      index=ctx.idx[:k8])
    hb = htf_bars(fr, 60)
    t8 = ctx.idx[k8]
    out = []
    for g in L.fvgs(hb.high.values, hb.low.values):
        if hb.end.iloc[g.i] > t8:
            continue
        if sign < 0 and g.kind == "bull":
            out.append(-g.bottom)
        elif sign > 0 and g.kind == "bear":
            out.append(g.top)
    out = [v for v in out if v > beyond]
    return min(out) if out else None


def run_ma_deuce(ctx, hist, p, day, symbol, btag: dict) -> list:
    from .strategy import (Trade, _first_units, news, day_type, _eff_flat, _stamp_frame,
                           mark_levels, CF_SRC, blocked, _arm_add, _lots)
    if len(hist) < 3:
        return []
    if p.md_need_news and news(day) != "0830":
        return []                                      # setups_models M15: the release delivers
    if p.md_blocked and ((p.day_filter and blocked(day, "AM", p, 480)) or (p.skip_news and news(day) != "none")):
        return []
    oo, hh, ll, cc = _dailies(ctx, hist, p, day, 10 if p.md_big_candle else 4)
    zones = [z for z in L.fvgs(hh, ll) if z.i >= len(hh) - 2]
    if not zones:
        return []
    z = zones[-1]                                     # the most recent daily FVG
    if p.md_big_candle:                               # M15: one big candle made the gap
        k = z.src
        prior = (hh - ll)[max(0, k - 5):k]
        up = cc[k] > oo[k] if z.kind == "bull" else cc[k] < oo[k]
        if not up or not len(prior) or hh[k] - ll[k] < p.md_big_candle * float(prior.mean()):
            return []
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
    levels = [target]
    if p.md_ladder and not capped and not (lock is not None and lock["side"]):   # M15 ladder (no lock)
        quad = sign * (z.bottom + 0.25 * (z.top - z.bottom) if sign < 0 else z.top - 0.25 * (z.top - z.bottom))
        h1 = _h1_gap_edge(ctx, sign, k8, max(quad, target))
        levels = sorted({v for v in (target, quad, h1) if v is not None and v > entry})
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
    kl, n_units, add, away, basis = 0, 0, None, False, 0.0
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
                           False, None, ctx.idx[k8], ctx.idx[i], x(fill), x(stop), x(levels[0] if len(levels) > 1 else target),
                           None if len(levels) < 2 else x(levels[-1]),
                           shares, day_type=day_type(day), news=news(day), weekday=day.weekday(),
                           capped=capped, sloppy=tag,
                           draw_side=0 if lock is None else lock["side"],
                           draw_px=None if lock is None else lock["target"],
                           draw_name="" if lock is None else lock["name"],
                           draw_kind="" if lock is None else lock["kind"], **btag)
                tr.entry_risk_pct = tr.peak_risk_pct = (round(shares * (fill - stop) / ctx.equity, 5)
                                                        if ctx.equity else None)
                _stamp_frame(ctx, tr, i)
                left = n_units = shares
                basis = fill * shares
                if sl[i] <= stop:
                    tr.exits.append((ctx.idx[i], x(stop), left, "stop"))
                    return [tr]
                fill_i = i
                continue
            if sh[i] >= target:
                return []
            continue
        if add is not None:                           # M15 md_second: the pending 2nd entry
            if i >= k830 or kl:
                add = None
            elif sl[i] < add[0]:
                px_ = min(add[0], so[i])
                tr.adds.append((ctx.idx[i], x(px_), add[1]))
                left += add[1]; n_units += add[1]; basis += px_ * add[1]
                add = None
        if so[i] <= stop:
            tr.exits.append((ctx.idx[i], x(so[i]), left, "stop_gap")); return [tr]
        if sl[i] <= stop:
            tr.exits.append((ctx.idx[i], x(stop), left, "be" if kl else "stop")); return [tr]
        if len(levels) > 1:                           # M15 md_ladder: scale out, BE after the first
            fr = p.ladder_fracs
            while kl < len(levels) and left and sh[i] >= levels[kl]:
                q = left if kl == len(levels) - 1 else min(left, max(p.lot, _lots(n_units * fr[min(kl, len(fr) - 1)], p.lot)))
                tr.exits.append((ctx.idx[i], x(levels[kl]), q, f"t{kl + 1}")); left -= q
                kl += 1
                stop = max(stop, basis / n_units)
            if not left:
                return [tr]
        elif sh[i] >= target:
            tr.exits.append((ctx.idx[i], x(target), left, "t1")); return [tr]
        if p.md_second and not tr.adds and add is None and not kl and i < k830 and p.adds:
            # 2nd entry before 08:30: a new small SIBI (side space: a bullish gap after the fill) or
            # a 2nd rejection of the inverted FVG (a touch of the entry after a close away from it)
            gs = [g for g in L.fvgs(sh[:i + 1], sl[:i + 1]) if g.kind == "bull" and g.i == i and g.i - 2 > fill_i]
            if sc[i] > entry:
                away = True
            px2 = gs[-1].top if gs else (entry if (away and sl[i] > entry) else None)
            if px2 is not None and px2 > stop:
                q2 = _lots(shares * p.adds[0], p.lot)
                room = (p.max_total_risk if p.max_total_risk is not None else p.max_total_risk_pct * ctx.equity) \
                    - max(0.0, basis - stop * n_units)
                if (px2 - stop) * q2 > room:
                    q2 = _lots(max(room, 0.0) / (px2 - stop), p.lot)
                if q2 >= max(p.lot, 1):
                    add = (px2, q2)
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
