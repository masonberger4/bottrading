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
from . import me1 as _ME1
from . import dwc3 as _DWC3                    # caption-gap day_week_context#3/3: the shared session veto


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


def run_ma_deuce(ctx, hist, p, day, symbol, btag: dict, sides=None) -> list:
    from .strategy import (Trade, _first_units, news, day_type, _eff_flat, _stamp_frame,
                           mark_levels, CF_SRC, blocked, _arm_add, _lots, _f, _htf_tag)
    from . import entries as _EN
    from . import targets as _TP
    from . import manage as _MG
    from . import daycontext as _DW
    from types import SimpleNamespace
    # the funnel keys md_* (strategy.FUNNEL) show which gate stops Ma Deuce (setups_models review)
    if len(hist) < 3:
        return []
    from claude_hf.daytypes import events as _events
    if p.nfp_first_hour and "jobs" in _events(day):
        _f("md_x_nfp_first_hour")
        return []                                      # news_calendar_times N1: nobody trades the first hour after 08:30
    if p.md_need_news and news(day) != "0830":
        _f("md_x_need_news")
        return []                                      # setups_models M15: the release delivers
    if p.md_blocked and _DWC3.session_veto(ctx, p, day, "AM", 480, blocked, news) is not None:      # caption-gap OT-filters-before-bias: the shared veto helper
        _f("md_x_blocked")
        return []
    oo, hh, ll, cc = _dailies(ctx, hist, p, day, 10 if p.md_big_candle else 4)
    zones = [z for z in L.fvgs(hh, ll) if z.i >= len(hh) - 2]
    if not zones:
        _f("md_x_no_daily_fvg")
        return []
    z = zones[-1]                                     # the most recent daily FVG
    if p.md_big_candle:                               # M15: one big candle made the gap
        k = z.src
        prior = (hh - ll)[max(0, k - 5):k]
        up = cc[k] > oo[k] if z.kind == "bull" else cc[k] < oo[k]
        if not up or not len(prior) or hh[k] - ll[k] < p.md_big_candle * float(prior.mean()):
            _f("md_x_big_candle")
            return []
    t = ctx.t
    k8 = ctx.start + int(np.searchsorted(t[ctx.start:], 480))
    k830 = ctx.start + int(np.searchsorted(t[ctx.start:], 510))
    c0825 = _ME1.entry_cut_0825(day, p, "PRE8")             # caption-gap N5-hold-through-0830: no new Ma Deuce entry from 08:25 on a release day
    k_end = ctx.start + int(np.searchsorted(t[ctx.start:], c0825)) if c0825 else k830
    if k8 >= len(t) or k8 <= ctx.start:
        return []
    px = ctx.c[k8 - 1]
    if z.kind == "bull" and px > z.mid:
        sign = -1                                      # premium of a daily BISI -> sell
    elif z.kind == "bear" and px < z.mid:
        sign = 1                                       # discount of a daily SIBI -> buy
    else:
        _f("md_x_wrong_half")
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
        _f("md_x_no_inverted_fvg")
        return []
    entry = inv.top                                    # near edge from above (side space)
    stop = inv.bottom - p.pad
    sd_ = next((s_ for s_ in (sides or ()) if s_.sign == sign), None)
    lvx, lvt = {}, []
    if sd_ is not None:    # the main engine's stop modifiers (E6d / E6f nfp_stop_wide / A4 mohawk) [our interpretation:
        stop = _EN.refine_stop(ctx, sd_, dict(ext_i=inv.i), k8 - 1, p, entry, stop, {}, lvx, lvt)   # the sweep = the inverted FVG]
    # at 08:00 price must already be past the inverted gap (the retest comes later)
    if sc[k8 - 1] <= entry:
        _f("md_x_not_past_at_0800")
        return []
    risk = entry - stop
    if not (p.min_risk_pts * p.es_pt <= risk <= p.max_risk_pts * p.es_pt):
        _f("md_x_risk")
        return []
    lock = None
    if p.draw_lock == "session":                       # owner #9 [our interpretation]: Ma Deuce
        lock = mark_levels(ctx, getattr(ctx, "bias_by_cut", {}).get(480), 480, "MD", p, ())
        ctx.lock["MD"] = lock                          # decides at 08:00 - its own 08:00 lock
        if (lock["side"] == 0 and p.draw_lock_neutral == "skip") or (lock["side"] and lock["side"] != sign):
            _f("md_x_lock_side")
            return []
        if lock["side"]:
            tv = sign * lock["target"]
            T = tv + p.pool_beyond_pts * p.es_pt if (p.exit_mode == "split" and lock["kind"] == "pool") \
                else tv - p.exit_before_pts * p.es_pt
            target = min(target, T)                    # the nearer of the CE and the draw
    capped = False
    cap = np.inf                                       # the hard ceiling of every ladder rung
    if lock is not None and lock["side"]:
        cap = T
    cap_tfs, bump_tfs = _TP.resist_cfg(p)                # owner #7 REVISED: cap tfs / speed-bump tfs
    if cap_tfs and getattr(ctx, "conf", None) is not None:      # the cap at 08:00
        r = ctx.conf.resistance(ctx.idx[k8], sign * entry, sign, cap_tfs,
                                tuple(CF_SRC[x] for x in p.htf_resist_src))
        if r is not None:
            capx = sign * r[0] - p.htf_resist_buffer_pts * p.es_pt
            cap = min(cap, capx)
            if capx < target:
                if capx - entry < p.sb_room_pts * p.es_pt:
                    _f("md_x_htf_resist")
                    return []
                target, capped = capx, True
    # side space: the target (the daily gap's CE) lies beyond the entry for both directions
    if target - entry < p.sb_room_pts * p.es_pt:
        _f("md_x_room")
        return []
    levels = [target]
    if p.md_ladder or p.ma_deuce_ladder:
        # M15 ladder: CE, lower quadrant, the 1h BISI low. Review fix: no longer switched off under
        # the #9 lock / #7 cap - every rung is capped at the locked draw (one exact target, owner
        # #9) and at the HTF resistance (#7); the cap itself is the last rung when it cuts the
        # ladder [our interpretation]
        quad = sign * (z.bottom + 0.25 * (z.top - z.bottom) if sign < 0 else z.top - 0.25 * (z.top - z.bottom))
        h1 = _h1_gap_edge(ctx, sign, k8, max(quad, sign * z.mid))
        far_ = None
        if p.ma_deuce_ladder and h1 is None:              # caption-gap M15-ma-deuce-ladder (091 ~23:31): without a 1h BISI the daily BISI's low is the best-case final rung
            from .sm3 import md_far_edge
            far_ = md_far_edge(sign, z)
        raw = sorted({v for v in (sign * z.mid, quad, h1, far_) if v is not None and v > entry})
        levels = [v for v in raw if v < cap - p.es_pt]
        if np.isfinite(cap) and (not levels or max(raw) >= cap - p.es_pt):
            levels.append(float(cap))
        levels = levels or [target]
    bump_set = []
    if bump_tfs and getattr(ctx, "conf", None) is not None:     # owner #7 REVISED: a partial at the opposing HTF FVG
        shim = SimpleNamespace(sign=sign, x=lambda v: sign * v)  # between the entry and the draw (the speed bump)
        bumps = _TP.bump_levels(ctx, shim, k8, p, entry, risk, bump_tfs, tuple(CF_SRC[x] for x in p.htf_resist_src),
                                None, now=ctx.idx[k8])
        bumps = [b for b in bumps if entry + p.sb_room_pts * p.es_pt <= b < max(levels) - p.es_pt]
        if bumps:
            levels = sorted(set(levels) | set(bumps))
            bump_set = list(bumps)
            lvt.append("speed_bump")
    chop = getattr(ctx, "chop", None)
    sloppy = set(r for r in getattr(ctx, "sl_day", ()) if not r.endswith(":PM"))

    def scalp_cap(lv_, t_):                            # #10 scalp: every rung capped at +scalp pts
        s_ = entry + p.sloppy_scalp_pts * p.es_pt      # (review fix: the ladder too, not only target)
        return sorted({min(v, s_) for v in lv_}), min(t_, s_)
    if (p.sloppy_mode == "scalp" and sloppy) or _DW.scalp_now(ctx, p, "PRE8", k8 - 1):
        levels, target = scalp_cap(levels, target)     # #10 scalp mode (+ day_week_context: inside week, low-vol day, ...)
    rm = _EN.extras_risk_mult(ctx, p, ctx.idx[k8 - 1])        # E10 loss_halving / Ep08.12 after_loss_mult
    if sd_ is not None:
        sw_ = dict(ext=float(inv.bottom), ext_i=inv.i)
        rm *= _EN.size_mult(ctx, sd_, sw_, k8 - 1, p, "AM", entry,
                            _htf_tag(ctx, sd_, k8 - 1, sw_["ext"], p.eq_tol_pts * p.es_pt), "|".join(sorted(sloppy)), lvt)   # E9
    xcap = p.size_up_cap_pct * ctx.equity if (p.size_up_cap_pct and any(x.startswith("size_up_") for x in lvt)) else 0.0
    shares = _EN.cap_initial(_first_units(p, ctx.equity, risk, entry, rm, xcap), p)    # E11
    if shares < 1:
        return []
    flat = _DW.flat_for(day, p, _eff_flat(p))          # N7.1 EARLY_CLOSE
    from . import newscal as _NC
    ff = _NC.fomc_flat_min(day, p)                     # N3.2: an FOMC day is flat at the release
    x = lambda v: sign * v
    tr = None
    left = 0
    fill = None
    pos = None
    last_part = -1
    tightened = False
    kl, n_units, add, away, basis = 0, 0, None, False, 0.0
    for i in range(k8, len(t)):
        if tr is None:
            if i >= k_end:
                return []
            if p.sloppy_mode == "stand_aside" and chop is not None and chop.active_before(i):
                _f("md_x_chop")
                return []                              # #10: chop known before this bar
            if _MG.extras_blocked(ctx, p, "AM", ctx.idx[i], getattr(ctx, "ext_other", ())):
                _f("md_x_day_stop")
                return []                              # X12 / X13a / X14d: the morning / day is stopped
            main_ = list(getattr(ctx, "risk_view", {}).get("trades", []))
            if _DW.budget_full(ctx, ctx.idx[i], (), main_ + list(getattr(ctx, "ext_other", ()))):
                _f("md_x_week_budget")
                return []                              # D19 / X15: the week's trade budget (every engine, as of this bar)
            # day_week_context: the day / week rules, read at the PREVIOUS close (the limit can fill inside this bar)
            if _DW.gate(ctx, p, "PRE8", i - 1, t[i - 1], main_):
                _f("md_x_day_week")
                return []                              # (pre-09:30 windows)
            if _DW.side_ok(ctx, p, sign, "PRE8", i - 1) or (p.tgif and sign in getattr(ctx, "block_side", {}).get("tgif", ())):
                _f("md_x_day_week_side")
                return []
            if sl[i] <= entry - p.fill_through * p.tick - (0.0 if p.fill_through else 1e-9):
                                                     # retest fills the limit - E3: it must print THROUGH it
                                                     # (the first build filled on a touch, `<=`)
                fill = min(entry, so[i])
                on_chop = chop is not None and chop.active_before(i)
                if p.sloppy_mode == "scalp" and on_chop:
                    levels, target = scalp_cap(levels, target)
                if p.tue_off_monday == "filter" or p.tgif_week_sweep:
                    sh_ = SimpleNamespace(sign=sign, x=lambda v: sign * v)       # day_week_context per-order rules: the "sweep"
                    why_dw = _DW.order_ok(ctx, sh_, dict(ext=float(sl[ctx.start:i].min())), "PRE8", i - 1, p)   # = the lowest low (side
                    if why_dw:                                                   # space) of the day before the retest bar
                        _f("md_x_day_week_order")
                        return []
                tag = "|".join(sorted(sloppy | ({"chop"} if on_chop else set())))
                tr = Trade(day, symbol, "AM", "ma_deuce", "long" if sign > 0 else "short", "daily_fvg",
                           False, None, ctx.idx[k8], ctx.idx[i], x(fill), x(stop), x(levels[0] if len(levels) > 1 else target),
                           None if len(levels) < 2 else x(levels[-1]),
                           shares, day_type=day_type(day), news=news(day), weekday=day.weekday(),
                           capped=capped, sloppy=tag, lv_tags="|".join(dict.fromkeys(lvt)),
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
                best = fill
                ts_st = {}
                bulk_done = False
                last_part = -1
                if sd_ is not None:       # X4 / X6-X9c: the position dict exits() / be_modes() read (side space)
                    hi_ = float(max(sh[inv.i:k8].max(), inv.top))
                    pos = dict(entry=fill, n=n_units, left=left, basis=basis, stop=stop, t1_done=False, k=0, best=fill,
                               fill_i=i, fill_t=t[i], levels=levels, t1=levels[0], side=sd_, trade=tr, lvx=lvx,
                               stop0=stop)
                    kinds_ = ["level"] * len(levels)
                    if lock is not None and lock["side"] and kinds_ and abs(levels[-1] - T) < 1e-9:
                        kinds_[-1] = lock["kind"]
                    _MG.extras_init(ctx, sd_, pos, tr, dict(
                        zone_bottom=float(inv.bottom), zone_top=float(inv.top), zone_ce=float((inv.top + inv.bottom) / 2),
                        ext=float(inv.bottom), ext_i=inv.i, leg_hi=hi_, level_kinds=kinds_, session="AM",
                        draw=None if lock is None or not lock["side"] else float(sign * lock["target"])), i, p)
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
        for nm_, (lvl_, pre_t1) in lvx.items():       # A4 mohawk: a body close beyond the raw level exits
            if i > fill_i and (not pre_t1 or not kl) and sc[i] < lvl_:
                tr.exits.append((ctx.idx[i], x(sc[i]), left, nm_)); return [tr]
        if len(levels) > 1:                           # M15 md_ladder: scale out, BE after the first
            fr = _TP.bump_fracs(levels, bump_set, p.ladder_fracs, p) if bump_set else p.ladder_fracs
            while kl < len(levels) and left and sh[i] >= levels[kl] + p.exit_fill_through * p.tick + _ME1.rung_hit_off(p):
                q = left if kl == len(levels) - 1 else min(left, max(p.lot, _lots(n_units * fr[min(kl, len(fr) - 1)], p.lot)))
                tr.exits.append((ctx.idx[i], x(_ME1.rung_px(levels[kl], p)), q, f"t{kl + 1}")); left -= q
                kl += 1
                last_part = i
                if _MG.extras_be_mode(p) == "t1":                        # X4: BE at the first rung (extras_be_on "t1", the
                    stop = max(stop, _MG.be_stop(basis / n_units, p))    # default) with the pad; "follow" = be_on, below
            if not left:
                tr.final_hit = tr.exits[-1][3] == f"t{len(levels)}"          # X12 / Ep04.13
                _MG.mark_day_stop(tr, p)
                return [tr]
        elif sh[i] >= target + p.exit_fill_through * p.tick + _ME1.rung_hit_off(p):
            tr.exits.append((ctx.idx[i], x(_ME1.rung_px(target, p)), left, "t1"))
            tr.final_hit = True
            _MG.mark_day_stop(tr, p)
            return [tr]
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
                q2 = _EN.cap_add(q2, n_units, p)           # E11 max_contracts_total
                if q2 >= max(p.lot, 1):
                    add = (px2, q2)
        if left and ff and t[i] + ctx.tf >= ff:
            tr.exits.append((ctx.idx[i], x(sc[i]), left, "fomc_flat")); return [tr]
        if left and _DW.day_exit(ctx, p, "PRE8", t[i] + ctx.tf):
            tr.exits.append((ctx.idx[i], x(sc[i]), left, "consol_out")); return [tr]    # N8.3: consolidation-day AM out by 11:00
        if left and p.flat_0830_extras and _ME1.flat_0830(day, p) and t[i] + ctx.tf >= 510:
            tr.exits.append((ctx.idx[i], x(sc[i]), left, "pre_0830")); return [tr]    # N4: no position into the 08:30 release
        best = max(best, sh[i])
        if pos is not None and left:              # X4 / D14 breakeven modes + X6-X9c invalidation exits (same code as the engine)
            pos.update(left=left, basis=basis, n=n_units, stop=stop, best=best, t1_done=kl > 0, k=kl, last_partial_i=last_part,
                       day_trade=False)
            _MG.extras_be_bar(sd_, pos, tr, i, p)
            stop = max(stop, pos["stop"])
            _MG.exits(ctx, sd_, pos, tr, i, ctx.idx[i], p, None, extras=True)
            left = pos["left"]
            if not left:
                return [tr]
        if (p.am_bulk_t and not bulk_done and left and t[fill_i] < p.am_bulk_t and t[i] + ctx.tf >= p.am_bulk_t):
            bulk_done = True                                       # X10b: the bulk off at am_bulk_t
            q_ = _MG.cut_qty(left, p.am_bulk_frac, p)
            tr.exits.append((ctx.idx[i], x(sc[i]), q_, "am_bulk")); left -= q_
            if not left:
                return [tr]
        if p.time_stop_extras and (p.time_stop_min or p.time_stop_bars) and not kl and left:    # X9 / X9d
            frac = _MG.time_stop_frac(p, ts_st, nbars=i - fill_i + 1, elapsed=(t[i] + ctx.tf) - t[fill_i],
                                      best=best, basis=basis / n_units,
                                      leg_hi=None if pos is None else pos["leg"][1],
                                      zone_top=None if pos is None else pos["zone_top"])      # X9a: leg_high / array_far
            if frac > 0:
                q_ = _MG.cut_qty(left, frac, p)
                tr.exits.append((ctx.idx[i], x(sc[i]), q_, "time" if q_ >= left else "time_cut")); left -= q_
                if not left:
                    return [tr]
        if p.am_exit and p.am_exit_extras and t[i] + ctx.tf >= p.am_exit:   # owner #8
            if p.am_exit_mode == "close":
                tr.exits.append((ctx.idx[i], x(sc[i]), left, "am_exit")); return [tr]
            if not tightened:
                tightened = True
                new = max(stop, fill, sl[i] - p.trail_pad)
                if new >= sc[i]:
                    tr.exits.append((ctx.idx[i], x(sc[i]), left, "am_exit")); return [tr]
                stop = new
        if t[i] + ctx.tf >= flat:
            tr.exits.append((ctx.idx[i], x(sc[i]), left, "eod")); return [tr]
    if tr is not None:
        tr.exits.append((ctx.idx[-1], x(sc[-1]), left, "eod"))
        return [tr]
    return []
