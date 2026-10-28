"""Caption-gap pass, package bias_htf#5/7 (digests/rulebook_gaps/definitions_pd_arrays_structure.md items 192, 201 and levels_liquidity_targets.md items 22, 23, 29, 35, 38, 58, 59, 69, 75, 78, 80, 93, 102, 103,
115, 133, 136, 138, 143, 147, 149, 164, 180) - ENGINE SIDE.

The bar-loop part: side gates, per-order rules and tags, the want (htf_bias) overrides and fallbacks, the draw preferences / filters of the lock, the per-bar re-lock, the extra rungs and entry arrays. The
columns they read are built by `bh5.py` inside `htf.table`. Nothing here reads a bar after the closed bar `i` the caller passes; every daily value is a table column or a completed hist session.
Hooks (who calls them)
  side_ok          daycontext.side_ok tail        org_with_bias, pm_range_break (done), pdh_raid_rev, range_block_probed, h4_ob_flip, program_gate
  order_ok         daycontext.order_ok tail       wk_two_draw, wk_range, weekly_open_array (+ tag wo_both)
  want_adjust      bias_day.want_at               program_gate, stack_draw, eq_breakout_draw, fast_week_rev (overrides); monthly_ctrl, shift_origin_pool, d_draw_carry, wk_ssl_draw, gap_theory_bias,
                                                  or60_bias (fallbacks); nwog_below_return, org_pm_draw, pm_flip_draw, pm_range_break, range_alternate (intraday), b7_spike_floor (the failed floor)
  lock_cands_filter / lock_prefs   strategy.mark_levels   nwog_draw_confl, nwog_fill_rule, org_with_bias (the filters); the forced draws of the table / intraday states (prefs)
  lock_bar         strategy._lock_step            nwog_below_return: the NWOG CE then its high / low is the draw once the break leg shows no displacement
  targets_post     strategy._targets              nwog_fill_rule (the dropped far edge), wk_range (the weekly draw), org_pm_draw (the lunch high rung), shift_origin_pool
  entry_rows       strategy._ts_arrays0           b7_spike_floor (the 1h OB open), h4_ob_flip (the 4h bullish OB)
  tf_lower_pref    bias_day.tf_lower_pref         target_tf
Thresholds the sources never give are marked [our interpretation].
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import levels as L
from . import bh1e as B1
from . import bh2 as BH2
from . import bh4 as BH4
from . import bh5 as BH5

HITS = BH2.HITS
sw = BH2.sw
_n, _f, _row = B1._n, B1._f, B1._row
DISP_MULT = 1.5                                     # [our interpretation] a displacement bar: range >= 1.5 x the mean range of the 20 bars before it


def hit(k: str) -> None:
    HITS[k] += 1


def _S():
    return B1._S()


def _BD():
    return B1._BD()


def _DC():
    from . import daycontext
    return daycontext


def _c(ctx) -> dict:
    return ctx.__dict__.setdefault("_bh5", {})


def on(p) -> bool:
    """Any engine-side bias_htf#5/7 switch is on (the hooks return at once otherwise)."""
    return bool(p.org_with_bias or p.pm_range_break or p.pdh_raid_rev or p.range_block_probed or p.h4_ob_flip or p.program_gate or p.wk_two_draw or p.wk_range
                or (p.weekly_open_array and p.weekly_open != "off"))


def want_on(p) -> bool:
    return bool(p.program_gate or p.stack_draw or p.eq_breakout_draw or p.fast_week_rev or p.monthly_ctrl or p.shift_origin_pool or p.d_draw_carry or p.wk_ssl_draw or p.gap_theory_bias
                or p.or60_bias or p.nwog_below_return or p.org_pm_draw or p.pm_flip_draw or p.pm_range_break or p.range_alternate or p.b7_spike_floor)


def lock_on(p) -> bool:
    return bool(p.nwog_below_return)


def prefs_on(p) -> bool:
    return bool(p.stack_draw or p.program_gate or p.eq_breakout_draw or p.fast_week_rev or p.d_draw_carry or p.shift_origin_pool or p.wk_ssl_draw or p.org_pm_draw or p.pm_flip_draw
                or p.nwog_fill_rule or p.nwog_draw_confl or p.org_with_bias)


def targets_on(p) -> bool:
    return bool(p.nwog_fill_rule or p.wk_range or p.org_pm_draw or p.shift_origin_pool)


def rows_on(p) -> bool:
    return bool(p.h4_ob_flip or p.b7_spike_floor)


def _k570(ctx) -> int:
    return _DC()._k570(ctx)


def _idx(ctx, m: int) -> int:
    return _S()._idx_at(ctx, m)


def _adr5(ctx, p):
    try:
        a = _DC()._adr(ctx, p)
    except Exception:
        a = None
    return float(a) if a else None


def _tk(p) -> float:
    return 0.25 * p.es_pt


def _want0(ctx, p, session: str, i: int) -> int:
    """The bias side WITHOUT this module's own adjustments (the table reading through every earlier hook): used where a rule needs 'the bias' as an input and must not read its own output."""
    c = _c(ctx)
    if c.get("in_want"):
        return 0
    c["in_want"] = True
    try:
        return int(_BD().want_at(ctx, p, session, i))
    finally:
        c["in_want"] = False


def _session_of(ctx, i: int) -> str:
    return "AM" if ctx.t[i] < 810 else "PM"


# --------------------------------------------------------------------------------------------------------------
# shared intraday readings
# --------------------------------------------------------------------------------------------------------------

def org_now(ctx, p, i: int):
    """Today's ORG (prior RTH close, 09:30 open) once the 09:30 bar has closed, else None; a gap under a quarter point is none."""
    if not getattr(ctx, "org_today", False) or not getattr(ctx, "org", None) or _k570(ctx) > i:
        return None
    pc, op = ctx.org[-1]
    if abs(op - pc) < 0.25 * p.es_pt:
        return None
    return float(pc), float(op)


def nwog_now(ctx, i: int):
    """The current NWOG as (high, low, ce): the newest 'nwog' row of the day's gap list (ict gap_mode), else the frame's own latest weekly gap (known at 09:30, so before it the previous one)."""
    gl = getattr(ctx, "gaps", None)
    if gl is not None:
        g = [(float(hi), float(lo), float(ce)) for kind, hi, lo, ce in gl if kind in ("nwog", "nwog_rth")]
        return g[-1] if g else None
    lst = ctx.nwog if (i >= _k570(ctx) or not getattr(ctx, "nwog_today", False)) else ctx.nwog_prev
    if not lst:
        return None
    a, b = lst[-1]
    hi, lo = (max(a, b), min(a, b))
    return float(hi), float(lo), float((hi + lo) / 2)


def eth_gaps(ctx, p, i: int) -> list:
    """The gaps the gap theory reads: the day's NWOG / NDOG rows (or the frame's weekly gaps) and today's ORG: [(hi, lo, ce, kind)]."""
    out = []
    gl = getattr(ctx, "gaps", None)
    if gl is not None:
        out += [(float(hi), float(lo), float(ce), kind) for kind, hi, lo, ce in gl]
    else:
        lst = ctx.nwog if (i >= _k570(ctx) or not getattr(ctx, "nwog_today", False)) else ctx.nwog_prev
        for a, b in lst[-2:]:
            hi, lo = max(a, b), min(a, b)
            out.append((float(hi), float(lo), float((hi + lo) / 2), "nwog"))
    og = org_now(ctx, p, i)
    if og is not None:
        hi, lo = max(og), min(og)
        out.append((float(hi), float(lo), float((hi + lo) / 2), "org"))
    return out


def _disp_count(ctx, a: int, b: int) -> int:
    """Displacement bars in a..b (inclusive): range >= DISP_MULT x the mean range of the 20 bars before the bar."""
    n = 0
    for j in range(max(a, 1), b + 1):
        w = slice(max(0, j - 20), j)
        m = float((ctx.h[w] - ctx.l[w]).mean())
        if m > 0 and float(ctx.h[j] - ctx.l[j]) >= DISP_MULT * m:
            n += 1
    return n


def _resampled_zones(ctx, p, i: int, m: int, days: int) -> list:
    """The FVGs of the m-minute bars of the last `days` completed sessions (hist) and today (bars closed by i): [(kind, top, bottom, untouched)] - 'untouched' = no later bar traded into the gap (through i)."""
    segs = []
    for fr in (getattr(ctx, "hist", None) or [])[-days:]:
        r = fr.resample(f"{m}min").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
        if len(r) >= 3:
            segs.append(tuple(r[k].values.astype(float) for k in ("open", "high", "low", "close")))
    b = B1.tf_complete(ctx, m, i)
    keep = b["first"] >= ctx.start
    if keep.sum() >= 3:
        segs.append((b["o"][keep], b["h"][keep], b["l"][keep], b["c"][keep]))
    out = []
    for s, (o, h, l, c) in enumerate(segs):
        for z in L.fvgs(h, l, o, c):
            hh = max([h[z.i + 1:].max(initial=-np.inf)] + [x[1].max() for x in segs[s + 1:]])
            ll = min([l[z.i + 1:].min(initial=np.inf)] + [x[2].min() for x in segs[s + 1:]])
            untouched = (hh < z.bottom) if z.kind == "bear" else (ll > z.top)
            out.append((z.kind, float(z.top), float(z.bottom), bool(untouched)))
    return out


# --------------------------------------------------------------------------------------------------------------
# item 23: below the NWOG low without displacement
# --------------------------------------------------------------------------------------------------------------

def nwog_below_state(ctx, p, i: int):
    """L5-below-nwog-low (033 ~08:19: 'it'll accumulate here run back up and start to work inside this Gap'): once today's bars have traded below the current NWOG's low and the break leg (the bar that first traded
    below it through bar i) holds fewer than two displacement bars (range >= 1.5 x the 20-bar mean range) the expectation is a return into the gap: (+1, hi, lo, ce). The same above the NWOG's high without displacement
    gives -1 (the mirror). (0, ...) when the leg displaced or nothing broke - then the bias stays [our interpretation: displacement = 2+ bars]."""
    ng = nwog_now(ctx, i)
    if ng is None or i < ctx.start:
        return 0, None
    hi, lo, ce = ng
    a = ctx.start
    below = np.flatnonzero(ctx.l[a:i + 1] < lo)
    above = np.flatnonzero(ctx.h[a:i + 1] > hi)
    j_b = a + int(below[0]) if len(below) else None
    j_a = a + int(above[0]) if len(above) else None
    if j_b is None and j_a is None:
        return 0, None
    if j_a is None or (j_b is not None and j_b <= j_a):
        if ctx.c[i] >= lo:
            return 0, ng                                  # back inside already: no longer below
        return (1 if _disp_count(ctx, j_b, i) < 2 else 0), ng
    if ctx.c[i] <= hi:
        return 0, ng
    return (-1 if _disp_count(ctx, j_a, i) < 2 else 0), ng


# --------------------------------------------------------------------------------------------------------------
# item 35: the ORG with the bias
# --------------------------------------------------------------------------------------------------------------

def org_with_bias_dir(ctx, p, i: int) -> int:
    """L7-breakaway-test (070 ~27:06: 'it's in a hurry to get somewhere'): the gap direction (+1 up / -1 down) when, at 09:30, the ORG points the way of the bias and an untaken daily pivot / PDH / PWH / the table's
    draw lies beyond the open in that direction; 0 otherwise. Fixed at the 09:30 bar (cached)."""
    c = _c(ctx)
    if "owb" in c:
        return c["owb"]
    og = org_now(ctx, p, i)
    if og is None:
        return 0
    pc, op = og
    g = 1 if op > pc else -1
    w = _want0(ctx, p, "AM", _k570(ctx))
    res = 0
    if w == g:
        row = _row(ctx, "AM", _k570(ctx))
        lv = []
        if row is not None:
            v = _f(row, "draw_up" if g > 0 else "draw_dn")
            if v == v:
                lv.append(v)
        for k, v in ctx.pd.items():
            if k.startswith("pdh" if g > 0 else "pdl"):
                lv.append(v)
        if ctx.pw is not None:
            lv.append(ctx.pw[0] if g > 0 else ctx.pw[1])
        if any((v - op) * g > 0 for v in lv):
            res = g
    c["owb"] = res
    if res:
        hit("org_with_bias")
    return res


# --------------------------------------------------------------------------------------------------------------
# item 38: the delayed PM fill of the ORG
# --------------------------------------------------------------------------------------------------------------

def org_pm_state(ctx, p, i: int):
    """L7-org-fill-delayed-pm (067 ~31:06, ~1:07:42: 'it doesn't mean it wants to run up there immediately'): at the PM start (bars closed by 13:30): a GAP DOWN not yet traded into since 09:30 (no high above the
    open + 10 % of the gap [our interpretation of 'traded into']) while today's RTH low is under the previous AM-session low (prev_am, deep discount) = (+1, near edge, CE, far edge, lunch high); the gap up mirrors
    (-1, ...). (0, None) otherwise or before 13:30."""
    kpm = _idx(ctx, 810)
    if i < kpm - 1 or getattr(ctx, "prev_am", None) is None:
        return 0, None
    c = _c(ctx)
    if "ompm" in c:
        return c["ompm"]
    res = (0, None)
    og = org_now(ctx, p, kpm - 1)
    if og is not None:
        pc, op = og
        k0 = _k570(ctx)
        gap = abs(pc - op)
        if pc > op:                                                   # gap down
            if ctx.l[k0:kpm].min() < ctx.prev_am[1] and ctx.h[k0:kpm].max() < op + 0.10 * gap:
                lun = ctx.h[_idx(ctx, 720):kpm].max() if kpm > _idx(ctx, 720) else None
                res = (1, (float(op), float((pc + op) / 2), float(pc), lun))
        else:
            if ctx.h[k0:kpm].max() > ctx.prev_am[0] and ctx.l[k0:kpm].min() > op - 0.10 * gap:
                lun = ctx.l[_idx(ctx, 720):kpm].min() if kpm > _idx(ctx, 720) else None
                res = (-1, (float(op), float((pc + op) / 2), float(pc), lun))
    c["ompm"] = res
    if res[0]:
        hit("org_pm_draw")
    return res


# --------------------------------------------------------------------------------------------------------------
# item 58: the alternation of the sweeps since 08:30
# --------------------------------------------------------------------------------------------------------------

def _session_pools(ctx, p, i: int) -> list:
    """[(level, side, created_bar)] of the session pools known at bar i: the prior days' highs / lows (untaken), the previous PM and London ranges, the previous AM range, the previous week, the overnight range
    once 09:30 is in, the lunch range once 13:30 is in."""
    out = []
    S = ctx.start
    for k, v in ctx.pd.items():
        if k.startswith(("pdh", "pdl")):
            out.append((float(v), 1 if k.startswith("pdh") else -1, S))
    if ctx.t[i] >= 570:
        for k, sd in (("pmh", 1), ("pml", -1)):
            if k in ctx.pd:
                out.append((float(ctx.pd[k]), sd, _k570(ctx)))
    for name, (hi, lo, ready) in ctx.sess.items():
        if name == "lunch":
            if ctx.t[i] >= 810:
                out += [(float(hi), 1, _idx(ctx, 810)), (float(lo), -1, _idx(ctx, 810))]
            continue
        if ctx.t[i] >= ready:
            cr = S if name in ("prev_pm", "prev_am") else _idx(ctx, ready)
            out += [(float(hi), 1, cr), (float(lo), -1, cr)]
    if getattr(ctx, "prev_am", None) is not None and "prev_am" not in ctx.sess:
        out += [(float(ctx.prev_am[0]), 1, S), (float(ctx.prev_am[1]), -1, S)]
    if ctx.pw is not None:
        out += [(float(ctx.pw[0]), 1, S), (float(ctx.pw[1]), -1, S)]
    seen, uniq = set(), []
    for lvl, sdn, cr in out:                                          # one pool per (level, side): two days with the same extreme are one run
        key = (round(lvl, 9), sdn)
        if key not in seen:
            seen.add(key)
            uniq.append((lvl, sdn, cr))
    return uniq


def sweep_runs(ctx, p, i: int) -> tuple:
    """L14-consolidation-alternation (022 ~3:04:38: 'buy side to sell side, buy side to sell side'): the runs since 08:30 - how many session pools of each side were swept (a bar with t >= 08:30 trading beyond a pool
    nothing had traded beyond since it existed) through bar i: (buy_runs, sell_runs, last_side) with last_side +1 / -1 / 0."""
    k0 = _idx(ctx, 510)
    buy = sell = 0
    ev = []
    for lvl, sdn, cr in _session_pools(ctx, p, i):
        a = max(cr, k0)
        if a > i:
            continue
        if sdn > 0:
            idx = np.flatnonzero(ctx.h[a:i + 1] > lvl)
            if len(idx) and not (cr < a and ctx.h[cr:a].max(initial=-np.inf) > lvl):
                ev.append((a + int(idx[0]), 1))
        else:
            idx = np.flatnonzero(ctx.l[a:i + 1] < lvl)
            if len(idx) and not (cr < a and ctx.l[cr:a].min(initial=np.inf) < lvl):
                ev.append((a + int(idx[0]), -1))
    buy = sum(1 for _, s in ev if s > 0)
    sell = sum(1 for _, s in ev if s < 0)
    ev.sort()
    return buy, sell, (ev[-1][1] if ev else 0)


def alternate_want(ctx, p, i: int) -> int:
    """The side to run next while the day is in an intraday range (the sloppy-day chop state): the side swept FEWER times; a tie = opposite the last sweep; 0 without a range or a sweep."""
    ch = getattr(ctx, "chop", None)
    if ch is None or getattr(ch, "inert", True) or not bool(ch.state[i]):
        return 0
    buy, sell, last = sweep_runs(ctx, p, i)
    if buy == sell:
        return -last
    return 1 if buy < sell else -1


# --------------------------------------------------------------------------------------------------------------
# item 59: the PM draw back up after the AM draw ran
# --------------------------------------------------------------------------------------------------------------

def pm_flip_state(ctx, p, i: int):
    """L14-conditional-pm-draw-up (024 ~8:36: 'if we fail to go much lower ... the market would want to go back up into that'): at 13:30, when the AM lock was DELIVERED and the AM extreme beyond its target is
    under pm_flip_adr x ADR5 [our interpretation of 'much lower'], the PM leans the OTHER way (side = minus the AM lock's) toward the nearest untouched opposing 5m / 15m FVG of the last pm_flip_days sessions
    (its near edge): (side, level). (0, None) when the condition fails or no FVG lies on that side."""
    kpm = _idx(ctx, 810)
    if i < kpm - 1:
        return 0, None
    c = _c(ctx)
    if "pmf" in c:
        return c["pmf"]
    res = (0, None)
    lk = (getattr(ctx, "lock", None) or {}).get("AM")
    adr = _adr5(ctx, p)
    if lk and lk.get("side") and lk.get("delivered") and adr and (lk.get("delivered_i") is not None and lk["delivered_i"] < kpm):
        k0 = _k570(ctx)
        s = lk["side"]
        tgt = float(lk["target"])
        beyond = (tgt - ctx.l[k0:kpm].min()) if s < 0 else (ctx.h[k0:kpm].max() - tgt)
        if beyond < p.pm_flip_adr * adr:
            px = float(ctx.c[kpm - 1])
            best = None
            for m in (5, 15):
                if m < ctx.tf:
                    continue
                for kind, top, bot, un in _resampled_zones(ctx, p, kpm - 1, m, int(p.pm_flip_days)):
                    if not un:
                        continue
                    if s < 0 and kind == "bear" and bot > px and (best is None or bot < best):
                        best = bot
                    if s > 0 and kind == "bull" and top < px and (best is None or top > best):
                        best = top
            if best is not None:
                res = (-s, float(best))
    c["pmf"] = res
    if res[0]:
        hit("pm_flip_draw")
    return res


# --------------------------------------------------------------------------------------------------------------
# item 69: the PM range break, hold and run
# --------------------------------------------------------------------------------------------------------------

def pm_range_state(ctx, p, i: int) -> tuple:
    """new-range-edge-break-retest (044 ~1:58:07: 'it needs to trade above it treat it as support and then run higher'): from the 12:00 mark of the AM range - hi_edge = the nearest of the AM high and the NWOG / gap
    edges above the price, lo_edge = the lower of the AM low and the far edge of the nearest 15m FVG below the price [our interpretation] - the state through bar i: +1 after (a trade above hi_edge, then a 1-bar
    pivot low that holds it within one tick, then a new high), -1 after a trade below lo_edge, else 0; done = no state by 14:30. Returns (state, done)."""
    k12 = _idx(ctx, 720)
    if i < k12 or _k570(ctx) >= k12:
        return 0, False
    k0 = _k570(ctx)
    c = _c(ctx)
    if "pmr_edges" not in c:
        am_hi, am_lo = float(ctx.h[k0:k12].max()), float(ctx.l[k0:k12].min())
        x0 = float(ctx.c[k12 - 1])
        edges = [am_hi] + [e for g in eth_gaps(ctx, p, k12 - 1) for e in (g[0], g[1]) if x0 < e < am_hi]
        hi_e = min(edges)
        fv = [bot for kind, top, bot, un in _resampled_zones(ctx, p, k12 - 1, 15, 1) if top < x0 and bot < x0]
        lo_e = min([am_lo] + ([max(fv)] if fv else []))
        c["pmr_edges"] = (hi_e, lo_e)
    hi_e, lo_e = c["pmr_edges"]
    tk = _tk(p)
    state, hi_since = 0, None
    jb = None
    for j in range(k12, i + 1):
        if ctx.l[j] < lo_e and not state:
            state = -1
            break
        if jb is None and ctx.h[j] > hi_e:
            jb = j
        if jb is not None and j >= jb + 2 and not state:
            # a 1-bar pivot low at q (q-1 .. q+1 all closed by j) that holds the edge, then a high above the pre-pullback high
            for q in range(jb + 1, j):
                if ctx.l[q] < ctx.l[q - 1] and ctx.l[q] < ctx.l[q + 1] and ctx.l[q] >= hi_e - tk and q + 1 <= j - 1:
                    if ctx.h[j] > ctx.h[jb:q + 1].max():
                        state = 1
                        break
        if state:
            break
    done = bool(ctx.t[i] + ctx.tf > 870 and state == 0)
    if state:
        hit("pm_range_break")
    return state, done


# --------------------------------------------------------------------------------------------------------------
# item 80: the gap theory
# --------------------------------------------------------------------------------------------------------------

def gap_theory_state(ctx, p, i: int) -> int:
    """new-gap-theory (065 ~4:53:00: 'it fills the gap rallies up treats the higher the gap as support'): among the gaps price has traded into today (NWOG / NDOG rows or the frame's weekly gaps, today's ORG) the NEAREST one
    (0 when price is inside it) decides from the last complete 5m close: above its high = +1 (support), below its low = -1 (resistance), inside it the CE side (+1 above the CE, -1 below). 0 without an active gap."""
    b = B1.tf_complete(ctx, 5, i)
    keep = b["first"] >= ctx.start
    if not keep.any():
        return 0
    c5 = float(b["c"][keep][-1])
    best = None
    for hi, lo, ce, kind in eth_gaps(ctx, p, i):
        seg_h, seg_l = ctx.h[ctx.start:i + 1], ctx.l[ctx.start:i + 1]
        if not ((seg_l <= hi) & (seg_h >= lo)).any():
            continue
        dist = 0.0 if lo <= c5 <= hi else min(abs(c5 - hi), abs(c5 - lo))
        st = 1 if c5 > hi else (-1 if c5 < lo else (1 if c5 > ce else (-1 if c5 < ce else 0)))
        if best is None or dist < best[0]:
            best = (dist, st)
    return 0 if best is None else best[1]


# --------------------------------------------------------------------------------------------------------------
# item 164: the OR60 extreme
# --------------------------------------------------------------------------------------------------------------

def or60_side(ctx, p, i: int) -> int:
    """LLT3-or-forms-day-extreme (cc10_006 ~3:50: 'it can be a run on stops or fair value setup'): from 10:30 (the 10:00 bar closed) - the OR60 low (09:30-10:30) formed by a stop run (it is within one sweep tick of a
    pool that was untaken at 09:30 and ran at most 2 points beyond it [our interpretation]) or by a fair-value setup (it lies inside a 5m / 15m bullish FVG formed before it) while the OR60 high was not = +1 (the
    low is the probable low of the day); the high mirrors (-1); both or neither 0."""
    k0, k1 = _k570(ctx), _idx(ctx, 630)
    if i < k1 - 1 or k0 >= k1:
        return 0
    c = _c(ctx)
    if "or60" in c:
        return c["or60"]
    lo_, hi_ = float(ctx.l[k0:k1].min()), float(ctx.h[k0:k1].max())
    tk = _tk(p)
    pools = _session_pools(ctx, p, k0 - 1)
    pools += [(float(ctx.pd[k]), 1 if k == "pmh" else -1, ctx.start) for k in ("pmh", "pml") if k in ctx.pd]
    pre_hi, pre_lo = (float(ctx.h[ctx.start:k0].max()), float(ctx.l[ctx.start:k0].min())) if k0 > ctx.start else (-np.inf, np.inf)

    def swept_low():
        return any(sdn < 0 and lvl <= float(ctx.c[k0 - 1] if k0 > 0 else lvl) and lo_ <= lvl + tk and lvl - lo_ <= 2.0 * p.es_pt for lvl, sdn, cr in pools)

    def swept_high():
        return any(sdn > 0 and lvl >= float(ctx.c[k0 - 1] if k0 > 0 else lvl) and hi_ >= lvl - tk and hi_ - lvl <= 2.0 * p.es_pt for lvl, sdn, cr in pools)

    def in_array(price: float, bull: bool) -> bool:
        for m in (5, 15):
            if m < ctx.tf:
                continue
            bb = B1.tf_complete(ctx, m, k1 - 1)
            for z in L.fvgs(bb["h"], bb["l"], bb["o"], bb["c"]):
                if z.kind == ("bull" if bull else "bear") and z.bottom <= price <= z.top:
                    return True
        return False

    lo_formed = swept_low() or in_array(lo_, True)
    hi_formed = swept_high() or in_array(hi_, False)
    res = 1 if (lo_formed and not hi_formed) else (-1 if (hi_formed and not lo_formed) else 0)
    c["or60"] = res
    if res:
        hit("or60_bias")
    return res


# --------------------------------------------------------------------------------------------------------------
# item 103: the 1h spike floor
# --------------------------------------------------------------------------------------------------------------

def b7_floor(ctx, p, row, i: int):
    """B7-spike-floor-1h-ob-fvg (101 ~38:37: 'here's your order block right there and it has a fair value gap'): with the daily bullish OB guard (its MT, table b7sf_guard) in force - the previous daily close
    not below it - and price trading below it today: the nearest 1h bullish OB below the MT with a bullish FVG right after it. Returns (floor = the OB low, entry = the open of its anchor candle, dead) or None.
    dead = a trade through the floor after price went under the MT. Skipped on a jobs-report (NFP) day."""
    if row is None or "b7sf_guard" not in row:
        return None
    g = _f(row, "b7sf_guard")
    if g != g:
        return None
    hist = getattr(ctx, "hist", None) or []
    if hist and float(hist[-1].close.iloc[-1]) < g:
        return None                                               # a daily close below the MT = the B7 failure, not a spike
    from claude_hf.daytypes import events
    if "jobs" in events(ctx.day):
        return None
    below = np.flatnonzero(ctx.l[ctx.start:i + 1] < g)
    if not len(below):
        return None
    j_g = ctx.start + int(below[0])
    b = B1.tf_complete(ctx, 60, i)
    if len(b["c"]) < 5:
        return None
    best = None
    for z in L.fvgs(b["h"], b["l"], b["o"], b["c"]):
        if z.kind != "bull":
            continue
        ob = L.order_block_blend(b["o"], b["h"], b["l"], b["c"], z.i - 4, z.i - 2, "bull")
        if ob is None or ob.top >= g:
            continue
        if best is None or ob.top > best[0].top:
            best = (ob, z)
    if best is None:
        return None
    ob = best[0]
    op = float(b["o"][ob.src]) if 0 <= ob.src < len(b["o"]) else float(ob.top)
    entry = min(max(op, float(ob.bottom)), float(ob.top))
    dead = bool(ctx.l[j_g:i + 1].min() < ob.bottom)
    return float(ob.bottom), entry, dead


# --------------------------------------------------------------------------------------------------------------
# item 192: the 4h bearish OB's MT traded through
# --------------------------------------------------------------------------------------------------------------

def h4_flip_state(ctx, p, row, i: int):
    """A12-4h-ob-mt-invalidation-flip (cc09_008 ~26:44: 'that would nullify any near-term four-hour bearishness'): with the daily IOF bullish (table iof > 0) a trade above the MT of the latest 4h bearish OB (its
    up-close candle run before a bearish FVG's displacement) cancels the 4h shorts: returns (flip side +1, [bullish OB zone (top, bottom) once the whole up candle (its high) traded through]) or (0, None); the
    daily IOF bearish mirrors it (flip -1: the latest 4h bullish OB's MT traded below cancels the longs). The OB 'preceding down-close 4h candles' = the run of down-close candles right before the up-close run,
    zone from their lowest open to their highest high [our interpretation of 'open to high']."""
    io = _n(row, "iof") if row is not None else 0
    if not io:
        return 0, None
    b = B1.tf_complete(ctx, 240, i)
    if len(b["c"]) < 4:
        return 0, None
    kind = "bear" if io > 0 else "bull"
    pick = None
    for z in L.fvgs(b["h"], b["l"], b["o"], b["c"]):
        if z.kind != kind:
            continue
        ob = L.order_block_blend(b["o"], b["h"], b["l"], b["c"], z.i - 4, z.i - 2, kind)
        if ob is None or (kind == "bear" and b["c"][z.i - 1] >= ob.bottom) or (kind == "bull" and b["c"][z.i - 1] <= ob.top):
            continue
        pick = (ob, z)
    if pick is None:
        return 0, None
    ob, z = pick
    k_done = int(b["last"][z.i]) + 1
    if k_done > i:
        return 0, None
    seg_h, seg_l = ctx.h[k_done:i + 1], ctx.l[k_done:i + 1]
    if not len(seg_h):
        return 0, None
    if io > 0:
        if seg_h.max() <= ob.mt:
            return 0, None
        zone = None
        if seg_h.max() > ob.top:                                   # the whole up candle traded through
            a = int(ob.src)
            q = a - 1
            while q >= 0 and b["c"][q] < b["o"][q]:
                q -= 1
            run = list(range(q + 1, a))
            if run:
                zone = (float(b["h"][run].max()), float(b["o"][run].min()))
        return 1, zone
    if seg_l.min() >= ob.mt:
        return 0, None
    zone = None
    if seg_l.min() < ob.bottom:
        a = int(ob.src)
        q = a - 1
        while q >= 0 and b["c"][q] > b["o"][q]:
            q -= 1
        run = list(range(q + 1, a))
        if run:
            zone = (float(b["o"][run].max()), float(b["l"][run].min()))
    return -1, zone


# --------------------------------------------------------------------------------------------------------------
# item 93: the acceptance above the 15m short-term high
# --------------------------------------------------------------------------------------------------------------

def ssl_cancelled(ctx, p, row, i: int) -> bool:
    """L14-consolidation-above-ssl (077 ~14:58): the read ends with ACCEPTANCE above the latest 15m short-term high - a 15m close above it followed by another 15m close above it [our interpretation], counted
    over the week's sessions so far and today - or a daily close above Friday's high (below Friday's low for the bullish mirror)."""
    side = _n(row, "wk_ssl")
    hi = _f(row, "wk_ssl_hi")
    if not side or hi != hi:
        return True
    fri = _f(row, "wk_ssl_fri")
    hist = getattr(ctx, "hist", None) or []
    wk = pd.Timestamp(ctx.day).to_period("W-FRI")
    this_week = [x for x in hist if pd.Timestamp(x.index[0].date()).to_period("W-FRI") == wk]
    closes = []
    for fr in this_week:
        r = fr.resample("15min").agg({"close": "last"}).dropna()
        closes += list(r.close.values.astype(float))
        if fri == fri and ((float(fr.close.iloc[-1]) > fri) if side < 0 else (float(fr.close.iloc[-1]) < fri)):
            return True
    b = B1.tf_complete(ctx, 15, i)
    keep = b["first"] >= ctx.start
    closes += list(b["c"][keep].astype(float))
    run = 0
    for x in closes:
        run = run + 1 if ((x > hi) if side < 0 else (x < hi)) else 0
        if run >= 2:
            return True
    return False


# --------------------------------------------------------------------------------------------------------------
# the side gate
# --------------------------------------------------------------------------------------------------------------

def side_ok(ctx, p, sign: int, session: str, i: int):
    """A funnel key when this side may not be traded at closed bar i for a bias_htf#5/7 reason, else None."""
    if not on(p) or i is None:
        return None
    row = _row(ctx, session, i)
    t = int(ctx.t[i])
    if p.org_with_bias and t < 810:
        g = org_with_bias_dir(ctx, p, i)
        if g and sign != g:
            sw("org_with_bias")
            return "x_bh5_org_with_bias"
    if p.pm_range_break and t >= 810:
        st, done = pm_range_state(ctx, p, i)
        if done:
            sw("pm_range_break")
            return "x_bh5_pm_range_done"
    if p.pdh_raid_rev and row is not None and "run_arr" in row:
        ra = _n(row, "run_arr")
        if ra > 0 and "pdh1" in ctx.pd:
            sw("pdh_raid_rev")
            if sign > 0 and float(ctx.h[ctx.start:i + 1].max()) > ctx.pd["pdh1"]:
                return "x_bh5_pdh_raid"                           # the buy-stop raid above the previous day's high after the run: shorts only
        if ra < 0 and "pdl1" in ctx.pd:
            sw("pdh_raid_rev")
            if sign < 0 and float(ctx.l[ctx.start:i + 1].min()) < ctx.pd["pdl1"]:
                return "x_bh5_pdl_raid"
    if p.range_block_probed:
        ch = getattr(ctx, "chop", None)
        if ch is not None and not getattr(ch, "inert", True) and bool(ch.state[i]):
            buy, sell, _ = sweep_runs(ctx, p, i)
            sw("range_alternate")
            if (sign > 0 and buy >= p.range_block_probed) or (sign < 0 and sell >= p.range_block_probed):
                return "x_bh5_range_probed"
    if p.program_gate and row is not None and "bprog" in row:
        v = _n(row, "bprog")
        if v:
            sw("program_gate")
            if sign == -v:
                return "x_bh5_program"
    if p.h4_ob_flip and row is not None:
        fl, _ = h4_flip_state(ctx, p, row, i)
        if fl:
            sw("h4_ob_flip")
            if sign == -fl:
                return "x_bh5_h4_flip"
    return None


# --------------------------------------------------------------------------------------------------------------
# the per-order rules and tags
# --------------------------------------------------------------------------------------------------------------

def _week_side(row) -> int:
    for k in ("wk_bias", "wk_dir", "bias_w"):
        v = _n(row, k)
        if v:
            return 1 if v > 0 else -1
    return 0


def _week_hl(ctx, i: int) -> tuple:
    """(high, low) of this week's bars so far: the completed sessions of the week (hist) and today's bars through i."""
    hist = getattr(ctx, "hist", None) or []
    wk = pd.Timestamp(ctx.day).to_period("W-FRI")
    hh = [float(x.high.max()) for x in hist if pd.Timestamp(x.index[0].date()).to_period("W-FRI") == wk]
    ll = [float(x.low.min()) for x in hist if pd.Timestamp(x.index[0].date()).to_period("W-FRI") == wk]
    hh.append(float(ctx.h[ctx.start:i + 1].max()))
    ll.append(float(ctx.l[ctx.start:i + 1].min()))
    return max(hh), min(ll)


def weekly_draw_level(ctx, row, side: int, i: int):
    """The weekly range's other end: the nearest 4h / daily / weekly array edge on the side the week runs to (below the price for a bearish week), from the confluence table, else the table's weekly draw."""
    px = float(ctx.c[i])
    cf = getattr(ctx, "conf", None)
    if cf is not None and hasattr(cf, "opposing"):
        now = ctx.idx[i] + pd.Timedelta(minutes=ctx.tf)
        r = cf.opposing(now, px, 1 if side > 0 else -1, ("4h", "D", "W"), (0, 1, 2, 3))
        if r:
            return float(r[0][0])
    if row is not None:
        v = _f(row, "wk_draw_up" if side > 0 else "wk_draw_dn")
        if v == v:
            return v
        v = _f(row, "draw_up" if side > 0 else "draw_dn")
        if v == v:
            return v
    return None


def order_ok(ctx, sd, o: dict, session: str, i: int, p):
    """A funnel key when the armed order `o` (side space) breaks a bias_htf#5/7 rule, else None. Adds tags to o['lv_tags']."""
    if not on(p):
        return None
    row = _row(ctx, session, i)
    sign = sd.sign
    entry_raw = sd.x(o["entry"])
    tags: list = []
    S = _S()
    if p.wk_two_draw and row is not None and "wk_prem_draw" in row:
        pr, ds = _f(row, "wk_prem_draw"), _f(row, "wk_disc_draw")
        if (pr == pr or ds == ds) and ctx.day.weekday() >= 2:
            sw("wk_two_draw")
            lk = (getattr(ctx, "lock", None) or {}).get("PM" if session in ("PM", "LUNCH", "LH") else "AM")
            tol = 1.0 * p.es_pt
            lv = [x for x in (pr, ds) if x == x]
            fin = o.get("t2") if o.get("t2") is not None else o.get("t1")
            fin_raw = None if fin is None else sd.x(fin)
            ok = (lk is not None and lk.get("target") is not None and any(abs(float(lk["target"]) - x) <= tol for x in lv)) or (fin_raw is not None and any(abs(fin_raw - x) <= tol for x in lv))
            if not ok:
                return "x_bh5_two_draw"
    if p.wk_range and row is not None:
        ws = _week_side(row)
        if ws and ws == sign:
            dr = weekly_draw_level(ctx, row, ws, i)
            wh, wl = _week_hl(ctx, i)
            if dr is not None:
                top, bot = (wh, dr) if ws < 0 else (dr, wl)
                if top > bot:
                    eq = (top + bot) / 2
                    sw("wk_range")
                    if (ws < 0 and entry_raw < eq - 1e-9) or (ws > 0 and entry_raw > eq + 1e-9):
                        return "x_bh5_wk_range"
                    tags.append("wk_range_" + ("prem" if ws < 0 else "disc"))
    if p.weekly_open_array and p.weekly_open != "off" and row is not None and not _n(row, "wo_expired"):
        wd = _n(row, "wk_dir")
        if wd and sign == wd:
            ops = {"sun18": ("wo_sun",), "mon00": ("wo_mon",), "either": ("wo_sun", "wo_mon")}[p.weekly_open]
            vals = [_f(row, k) for k in ops if _f(row, k) == _f(row, k)]
            if vals:
                sw("weekly_open_array")
                if not BH4E_entry_in_array(ctx, sd, o, i, p):
                    return "x_bh5_wo_array"
                if len(vals) == 2 and all((entry_raw < v) if wd > 0 else (entry_raw > v) for v in vals):
                    tags.append("wo_both")
    if tags:
        o["lv_tags"] = "|".join(dict.fromkeys(x for x in (o.get("lv_tags", ""), *tags) if x))
    return None


def BH4E_entry_in_array(ctx, sd, o, i, p) -> bool:
    from . import bh4e
    return bh4e.entry_in_htf_array(ctx, sd, o, i, p)


# --------------------------------------------------------------------------------------------------------------
# the bias (want) overrides and fallbacks
# --------------------------------------------------------------------------------------------------------------

def want_adjust(ctx, p, session: str, i: int, v: int) -> int:
    """The htf_bias value after the bias_htf#5/7 readings. Overrides (the spec sets the side): the buy / sell program, the stacked highs, the EQ-breakout side, the fast week's reversal, the NWOG-below return, the
    delayed PM ORG draw, the PM flip, the PM range break, the alternation of an intraday range, the failed 1h spike floor (a bullish bias turns 0). Fallbacks (only when the bias is neutral): the monthly control, the
    shift-origin MSS, the carried daily draw, the weekly SSL read (Tuesday on), the gap theory; the OR60 side counts when the bias is neutral or agrees."""
    c = _c(ctx)
    if c.get("in_want"):
        return v
    row = _row(ctx, session, i)
    t = int(ctx.t[i])
    if row is not None:
        if p.program_gate and "bprog" in row and _n(row, "bprog"):
            sw("program_gate")
            v = _n(row, "bprog")
        if p.stack_draw and "stack_side" in row and _n(row, "stack_side"):
            sw("stack_draw")
            v = _n(row, "stack_side")
        if p.eq_breakout_draw and "eqb_dir" in row:
            if _n(row, "eqb_dir"):
                sw("eq_breakout_draw")
                v = _n(row, "eqb_dir")
            elif _n(row, "eqb_in_eq"):
                sw("eq_breakout_draw")
                v = 0
        if p.fast_week_rev and "fast_week" in row and _n(row, "fast_week") and ctx.day.weekday() >= 2:
            sw("fast_week_rev")
            v = _n(row, "fast_week")
        if not v:
            for flag, col, name in ((p.monthly_ctrl, "m_ctrl", "monthly_ctrl"), (p.d_draw_carry, "d_draw_dir", "d_draw_carry")):
                if flag and col in row and _n(row, col):
                    sw(name)
                    v = _n(row, col)
                    break
        if not v and p.shift_origin_pool and "shift_last" in row and _n(row, "shift_last"):
            side = _n(row, "shift_last")
            lvl = _f(row, "shift_origin_lo" if side < 0 else "shift_origin_hi")
            if lvl == lvl:
                sw("shift_origin_pool")
                v = _n(row, "shift_last")
        if not v and p.wk_ssl_draw and "wk_ssl" in row and _n(row, "wk_ssl") and ctx.day.weekday() >= 1:
            if not ssl_cancelled(ctx, p, row, i):
                sw("wk_ssl_draw")
                v = _n(row, "wk_ssl")
        if p.b7_spike_floor and v > 0:
            fl = b7_floor(ctx, p, row, i)
            if fl is not None and fl[2]:
                sw("b7_spike_floor")
                v = 0
    if not v and p.gap_theory_bias:
        g = gap_theory_state(ctx, p, i)
        if g:
            sw("gap_theory_bias")
            v = g
    if p.or60_bias:
        s = or60_side(ctx, p, i)
        if s and (not v or v == s):
            sw("or60_bias")
            v = s
    if p.nwog_below_return:
        s, _ = nwog_below_state(ctx, p, i)
        if s:
            sw("nwog_below_return")
            v = s
    if p.range_alternate:
        s = alternate_want(ctx, p, i)
        if s:
            sw("range_alternate")
            v = s
    if t >= 810:
        if p.org_pm_draw:
            s, _ = org_pm_state(ctx, p, i)
            if s:
                sw("org_pm_draw")
                v = s
        if p.pm_flip_draw:
            s, _ = pm_flip_state(ctx, p, i)
            if s:
                sw("pm_flip_draw")
                v = s
        if p.pm_range_break:
            s, _ = pm_range_state(ctx, p, i)
            if s:
                sw("pm_range_break")
                v = s
    return v


# --------------------------------------------------------------------------------------------------------------
# the draw lock: filters, preferred draws, the per-bar re-lock
# --------------------------------------------------------------------------------------------------------------

def _is_nwog_name(n: str) -> bool:
    return str(n).startswith("nwog")


def lock_filter(ctx, p, row, cands: list, prefs: list, t_lock: int, session: str, kl: int, px: float):
    """(cands, prefs) after the filters: nwog_draw_confl (an NWOG level stays a lock candidate only with a pool or an HTF array level within confl_pts, or in the bias direction from the price), nwog_fill_rule
    (the far edge - Friday's close - of the week's NWOG is dropped when the table says a partial fill is fine), org_with_bias (the ORG levels leave the AM lock when the gap goes the way of the bias)."""
    if not (p.nwog_draw_confl or p.nwog_fill_rule or p.org_with_bias):
        return cands, prefs
    keep_c, keep_p = list(cands), list(prefs)
    tol = p.confl_pts * p.es_pt
    if p.nwog_draw_confl:
        want = 0
        if p.htf_bias != "off" and row is not None:
            try:
                want = int(_BD().bias_value(row, p))
            except Exception:
                want = 0
        anchors = [x[0] for x in keep_c if x[1] == "pool" and not _is_nwog_name(x[2])] + [x[0] for x in keep_c if str(x[2]).startswith("htf_")]

        def ok(x):
            if not _is_nwog_name(x[2]):
                return True
            if any(abs(x[0] - a) <= tol for a in anchors):
                return True
            return bool(want and (x[0] - px) * want > 0)
        n0 = len(keep_c)
        keep_c = [x for x in keep_c if ok(x)]
        keep_p = [x for x in keep_p if ok(x)]
        if len(keep_c) != n0:
            hit("nwog_not_standalone")
            sw("nwog_draw_confl")
    if p.nwog_fill_rule and row is not None and "nwog_fill" in row and _n(row, "nwog_gap") and not _n(row, "nwog_fill", 1):
        ng = nwog_now(ctx, kl - 1)
        if ng is not None:
            hi, lo, ce = ng
            far = lo if _n(row, "nwog_gap") > 0 else hi                       # a gap up: Friday's close is the gap's low edge
            n0 = len(keep_c)
            keep_c = [x for x in keep_c if not (_is_nwog_name(x[2]) and abs(x[0] - far) <= 1e-9)]
            keep_p = [x for x in keep_p if not (_is_nwog_name(x[2]) and abs(x[0] - far) <= 1e-9)]
            if len(keep_c) != n0:
                hit("nwog_far_edge_dropped")
                sw("nwog_fill_rule")
    if p.org_with_bias and t_lock >= 570 and session == "AM" and kl - 1 >= _k570(ctx) and org_with_bias_dir(ctx, p, kl - 1):
        n0 = len(keep_c)
        keep_c = [x for x in keep_c if not str(x[2]).startswith("org")]
        keep_p = [x for x in keep_p if not str(x[2]).startswith("org")]
        if len(keep_c) != n0:
            sw("org_with_bias")
    return keep_c, keep_p


def lock_prefs(ctx, p, row, t_lock: int, session: str, S: int, px: float, kl: int) -> list:
    """The draws the bias_htf#5/7 states force as PREFERRED lock candidates: (level, kind, name, dir, created)."""
    out = []
    if row is not None:
        if p.program_gate and "bprog" in row and _n(row, "bprog"):
            v = _f(row, "bprog_tgt")
            if v == v:
                out.append((v, "array", "program_tgt", 0, S))
        if p.stack_draw and "stack_side" in row and _n(row, "stack_side"):
            v = _f(row, "stack_hi")
            if v == v:
                out.append((v, "pool", "stack_hi", _n(row, "stack_side"), S))
        if p.eq_breakout_draw and "eqb_dir" in row and _n(row, "eqb_dir"):
            v = _f(row, "eqb_tgt")
            if v == v:
                out.append((v, "array", "eq_breakout_tgt", 0, S))
        if p.fast_week_rev and "fast_week" in row and _n(row, "fast_week") and ctx.day.weekday() >= 2:
            tg = None
            cf = getattr(ctx, "conf", None)
            if cf is not None and hasattr(cf, "opposing"):
                now = pd.Timestamp(ctx.day, tz=ctx.idx.tz) + pd.Timedelta(minutes=t_lock)
                r = cf.opposing(now, px, _n(row, "fast_week"), ("4h", "D", "W"), (0, 1, 2, 3))
                if r:
                    tg = float(r[0][0])
            if tg is None:
                v = _f(row, "fw_tgt")
                tg = v if v == v else None
            if tg is not None:
                out.append((tg, "array", "fast_week_tgt", 0, S))
        if p.d_draw_carry and "d_draw_dir" in row and _n(row, "d_draw_dir"):
            v = _f(row, "d_draw")
            if v == v:
                out.append((v, "array", "d_draw", 0, S))
        if p.shift_origin_pool and "shift_last" in row and _n(row, "shift_last"):
            side = _n(row, "shift_last")
            v = _f(row, "shift_origin_lo" if side < 0 else "shift_origin_hi")
            if v == v:
                out.append((v, "pool", "shift_origin", -side if side < 0 else side, S))
        if p.wk_ssl_draw and "wk_ssl" in row and _n(row, "wk_ssl") and ctx.day.weekday() >= 1 and kl - 1 >= S:
            v = _f(row, "wk_ssl_lvl")
            if v == v and not ssl_cancelled(ctx, p, row, kl - 1):
                out.append((v, "pool", "wk_ssl_lvl", _n(row, "wk_ssl"), S))
    if t_lock >= 810 and kl - 1 >= S:
        if p.org_pm_draw:
            s, info = org_pm_state(ctx, p, kl - 1)
            if s:
                out.append((info[0], "array", "org_pm", 0, S))
        if p.pm_flip_draw:
            s, lvl = pm_flip_state(ctx, p, kl - 1)
            if s:
                out.append((lvl, "array", "pm_flip_fvg", 0, S))
    return out


def lock_bar(ctx, p, s_: str, lk: dict, i: int, done: dict, spent, state=None):
    """_lock_step hook, once per bar and session lock: nwog_below_return re-locks (once per session) to the NWOG CE, then its far edge, on the side of the return when the break leg shows no displacement.
    Returns (new_lock, cancel_pending) or None."""
    if not p.nwog_below_return or lk.get("nb_done") or lk.get("delivered"):
        return None
    st, ng = nwog_below_state(ctx, p, i)
    if not st or ng is None:
        return None
    hi, lo, ce = ng
    px = float(ctx.c[i])
    levels = [ce, hi] if st > 0 else [ce, lo]
    tgt = next((x for x in levels if (x - px) * st > p.draw_lock_min_pts * p.es_pt * 0.0 and (x - px) * st > 0), None)
    if tgt is None:
        return None
    if lk.get("side") == st and abs(float(lk.get("target") or 0) - tgt) < 1e-9:
        return None
    nl = B1._relock(ctx, p, s_, lk, i, spent, st, "nwog_below")
    nl.update(side=st, target=float(tgt), kind="array", name="nwog_ce" if tgt == ce else ("nwog_high" if st > 0 else "nwog_low"), nb_done=True)
    nl.update(delivered=False, delivered_t=None, delivered_i=None)
    nl.setdefault("bh5", []).append("nwog_below_return")
    hit("nwog_below_return")
    return nl, True


# --------------------------------------------------------------------------------------------------------------
# the extra rungs and entry arrays
# --------------------------------------------------------------------------------------------------------------

def targets_post(ctx, sd, i: int, p, above: float, lv: list) -> list:
    """nwog_fill_rule: the dropped far edge leaves the rungs; wk_range: the weekly draw is the final rung of a trade in the week's direction; org_pm_draw: the ORG ladder (near edge, CE, far edge) and the lunch
    high as the first rung; shift_origin_pool: the stored origin pool is a pool rung."""
    session = getattr(ctx, "cur_session", "") or ("PM" if ctx.t[i] >= 810 else "AM")
    row = _row(ctx, session, i)
    if p.nwog_fill_rule and row is not None and "nwog_fill" in row and _n(row, "nwog_gap") and not _n(row, "nwog_fill", 1):
        ng = nwog_now(ctx, i)
        if ng is not None:
            hi, lo, ce = ng
            far = lo if _n(row, "nwog_gap") > 0 else hi
            x = sd.x(far)
            kept = [(v, k) for v, k in lv if abs(v - x) > 1e-9]
            if len(kept) != len(lv):
                hit("nwog_far_edge_dropped")
                sw("nwog_fill_rule")
            lv = kept
    if p.wk_range and row is not None:
        ws = _week_side(row)
        if ws and ws == sd.sign:
            dr = weekly_draw_level(ctx, row, ws, i)
            if dr is not None:
                x = sd.x(dr)
                if x > above:
                    sw("wk_range")
                    lv = list(lv) + [(float(x), "array")]
    if p.org_pm_draw and ctx.t[i] >= 810:
        s, info = org_pm_state(ctx, p, i)
        if s and s == sd.sign:
            sw("org_pm_draw")
            near, ce, far, lun = info
            lvl = ([(sd.x(lun), "pool")] if lun is not None else []) + [(sd.x(near), "array"), (sd.x(ce), "array"), (sd.x(far), "array")]
            lv = list(lv) + [(float(v), k) for v, k in lvl if v > above]
    if p.shift_origin_pool and row is not None:
        v = _f(row, "shift_origin_hi" if sd.sign > 0 else "shift_origin_lo")
        if v == v:
            x = sd.x(v)
            if x > above:
                sw("shift_origin_pool")
                lv = list(lv) + [(float(x), "pool")]
    return lv


def entry_rows(ctx, sd, i: int, p=None) -> list:
    """Entry arrays (side space (top, bottom, known)): the 1h OB open of the b7 spike floor (zero height, a long only) and the 4h bullish OB that formed once the 4h bearish OB's candle was traded through."""
    out = []
    if p is None:
        return out
    session = _session_of(ctx, i)
    row = _row(ctx, session, i)
    if row is None:
        return out
    kn = ctx.idx[ctx.start]
    if p.b7_spike_floor and sd.sign > 0:
        fl = b7_floor(ctx, p, row, i)
        if fl is not None and not fl[2]:
            sw("b7_spike_floor")
            out.append((float(sd.x(fl[1])), float(sd.x(fl[1])), kn))
    if p.h4_ob_flip:
        fl, zone = h4_flip_state(ctx, p, row, i)
        if fl == sd.sign and zone is not None:
            sw("h4_ob_flip")
            a, b = float(sd.x(zone[0])), float(sd.x(zone[1]))
            out.append((max(a, b), min(a, b), kn))
    return out


# --------------------------------------------------------------------------------------------------------------
# item 133: the target timeframe
# --------------------------------------------------------------------------------------------------------------

TARGET_TFS = {"one_lower": {"M": ("W", "D", "4h"), "W": ("D", "4h"), "D": ("4h", "1h")}, "same": {"M": ("M",), "W": ("W",), "D": ("D",)}}


def target_tfs(react_tf: str, mode: str) -> tuple:
    """L14-target-timeframe (cc07_003 ~2:50; cc07_004 ~14:37; cc06_006 ~3:24): the timeframes the draw is searched on after a reaction at `react_tf`: 'one_lower' = monthly -> weekly / daily (4h allowed), weekly -> daily /
    4h, daily -> 4h / 1h; 'same' = the reaction timeframe's own opposing arrays; () for 'off' or an unknown timeframe. (cc06_006 same-timeframe position context vs the cc07_003 one-lower weekly templates.)"""
    return TARGET_TFS.get(mode, {}).get(react_tf, ())


def target_pref(ctx, row, px: float, now, S: int, mode: str):
    """The preferred lock candidate of target_tf: the nearest opposing array on `target_tfs(react_tf)` (conf.opposing nearest first), (level, 'array', name, 0, S) or None."""
    if not row or getattr(ctx, "conf", None) is None:
        return None
    rs, tf = _n(row, "react"), row.get("react_tf")
    tfs = target_tfs(tf, mode) if tf else ()
    if not rs or not tfs:
        return None
    r = ctx.conf.opposing(now, px, 1 if rs > 0 else -1, tfs, (0, 1, 2, 3))
    if not r:
        return None
    sw("target_tf")
    return (float(r[0][0]), "array", f"target_tf_{mode}_{r[0][3] if len(r[0]) > 3 else tfs[0]}", 0, S)


# --------------------------------------------------------------------------------------------------------------
# item 164: the conditional statistic
# --------------------------------------------------------------------------------------------------------------

def or60_stat(days) -> dict:
    """LLT3-or-forms-day-extreme (cc10_006 ~3:50): over consecutive day frames (bars with a time-of-day index) - how often the RTH low (high) of the day lies INSIDE the OR60 window (09:30-10:30) when the OR60
    low (high) was formed by a stop run on the previous day's low (high) (the OR60 extreme at or beyond it) versus not. {'n': days, 'low_run': {n, in_or, rate}, 'low_other': ..., 'high_run': ..., 'high_other': ...}."""
    out = {k: [0, 0] for k in ("low_run", "low_other", "high_run", "high_other")}
    n = 0
    for prev, cur in zip(days[:-1], days[1:]):
        t = cur.index.hour * 60 + cur.index.minute
        rth = cur[(t >= 570) & (t < 960)]
        orw = cur[(t >= 570) & (t < 630)]
        if len(rth) < 20 or len(orw) < 6:
            continue
        n += 1
        pl, ph = float(prev.low.min()), float(prev.high.max())
        o_lo, o_hi = float(orw.low.min()), float(orw.high.max())
        d_lo, d_hi = float(rth.low.min()), float(rth.high.max())
        k = "low_run" if o_lo <= pl else "low_other"
        out[k][0] += 1
        out[k][1] += int(o_lo <= d_lo + 1e-12)
        k = "high_run" if o_hi >= ph else "high_other"
        out[k][0] += 1
        out[k][1] += int(o_hi >= d_hi - 1e-12)
    res = {"n": n}
    for k, (a, b) in out.items():
        res[k] = dict(n=a, in_or=b, rate=(b / a if a else float("nan")))
    return res
