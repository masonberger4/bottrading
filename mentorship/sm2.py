"""Caption-gap pass (digests/rulebook_gaps/*.md), package setups_models: the engine glue (chunk 1 of 7; later chunks extend this module).

The detectors live in levels.py (pure arrays in, objects out), the combine picks in backtest.py; this module wires the new switches into
the bar-by-bar engine (strategy.py / setups.py hooks) behind Params switches - see the "caption-gap pass, setups_models #1/7" block of
Params; every switch cites its gap id and source video/time there. Conventions as everywhere: side space (shorts run mirrored prices),
a bar is used only after it closes (`i` = the last CLOSED bar, an order armed on it fills from bar i+1), an object only from the bar that
completes it, daily / weekly objects only after their session closes (everything reads `ctx.hist`, the COMPLETED prior sessions, plus
today's bars through the bar being judged). Interpretations the sources do not pin down are marked [our interpretation].
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import levels as L

HITS: dict = {}          # test hook: {name: number of calls} - proof that a switch's code path RAN; a plain counter, no effect on results


def hit(name: str) -> None:
    HITS[name] = HITS.get(name, 0) + 1


def _S():
    from . import strategy as S
    return S


def _c(ctx) -> dict:
    return ctx.__dict__.setdefault("_sm2", {})


TRADE_KEYS = ("open_grade", "po3_seq", "wk_open_side", "touch_n", "judas_depth", "array_depth", "array_respect", "clean_swing", "move_pct",
              "lc_reversal")


def trade_fields(o: dict) -> dict:
    """The Trade fields of this package carried by an order dict (strategy._make_trade)."""
    return {k: o[k] for k in TRADE_KEYS if k in o}


# --- small helpers ---------------------------------------------------------------------------------------------------------------

def want(ctx) -> int:
    """The bias side the current scan trades toward (the session's locked draw, else the htf_bias reading; 0 = none), as set per side by run_day."""
    return int(getattr(ctx, "cur_bias", 0) or 0)


def now_ts(ctx, i: int) -> pd.Timestamp:
    return ctx.idx[i] + pd.Timedelta(minutes=ctx.tf)


def adr5(ctx):
    return _S().adr5(getattr(ctx, "hist", [])[-5:])


def other_side(ctx, sd, p=None):
    """The opposite Side of the day (the live object while the engine runs: ctx.sides_map; else a private one built from the day's bars)."""
    sm = getattr(ctx, "sides_map", None)
    if sm and -sd.sign in sm:
        return sm[-sd.sign]
    c = _c(ctx)
    k = ("side", -sd.sign)
    if k not in c:
        c[k] = _S().Side(-sd.sign, ctx.o, ctx.h, ctx.l, ctx.c, getattr(p, "pivot_n", 2) if p is not None else 2)
    return c[k]


def sess_a(ctx, session: str) -> int:
    """First bar of the reference-open span: 13:30 for the PM, the day's first bar (00:00) otherwise."""
    return _S()._idx_at(ctx, 810) if session == "PM" else ctx.start


def ref_open(ctx, p, session: str, i: int):
    """The (first) reference open the entry is judged against (real price) or None: T2 / D22 bias_open, the 13:30 open for the PM."""
    from . import bias_day as BD
    refs = BD.reference_opens(ctx, p, session, i)
    return refs[0] if refs else None


def bias_at(ctx, p, session: str, i: int) -> int:
    """The HTF bias side known at closed bar i, for the setups that run outside the per-side loop: the loop's own reading when set, else
    the htf.table row KNOWN at that bar (bias_day.row_for: the 09:30 table from 09:30, the lock-time cut before it) read with the htf_bias
    column ("combo" when htf_bias is off), else the daily / 4h structure of the Confluence object when both agree [our interpretation]."""
    from . import bias_day as BD
    w = want(ctx)
    if w:
        return w
    row = BD.row_for(ctx, session, i)
    if row is not None:
        col = BD.bias_col(p) if p.htf_bias != "off" else "combo"
        v = row.get(col)
        try:
            return 0 if v is None or v != v else int(v)
        except Exception:
            return 0
    cf = getattr(ctx, "conf", None)
    if cf is not None:
        now = now_ts(ctx, i)
        d, h4 = cf.trend(now, "D"), cf.trend(now, "4h")
        if d and h4 and d != h4:
            return 0
        return int(d or h4)
    return 0


def attach(ctx, df, hist, p, eth=None) -> None:
    """Per-day static objects (strategy._extra_levels): the week's Sunday 18:00 open for wk_open_side (from the completed first session's all-hours
    open, or the evening session before a Monday; known before 09:30)."""
    ctx.sunday_open = None
    if p.wk_open_side:
        hit("sunday_open")
        try:
            lv = _S()._DW._week_objective_levels(ctx, hist, ctx.day, p, eth)
        except Exception:
            lv = {}
        nw = lv.get("_nwog")
        ctx.sunday_open = None if nw is None else float(nw[1])


# --- open pools (B18-am-smt-window-points) ----------------------------------------------------------------------------------------------

OPEN_KEYS = {"open_0830": "0830", "open_0930": "0930"}


def open_pools(ctx, sd, i: int, p, out: dict) -> None:
    """B18.2 smt_open_points (cc10_011 ~12:50: the 08:30 / 09:30 opens can be one point): the opening prices that have printed are sell-side
    reference points (side space), compared like any pool (the partner twin is the partner's own open)."""
    if not p.smt_open_points:
        return
    S = _S()
    for k, nm in OPEN_KEYS.items():
        v = S._open_known(ctx, nm, i)
        if v is not None:
            hit("open_pools")
            out[k] = sd.x(v)


def created(ctx, key: str):
    """The bar from which the open pool exists (the bar AFTER the open's own bar: its low is always at or under its open), else None."""
    if key in OPEN_KEYS:
        S = _S()
        return S._idx_at(ctx, S.OPEN_MIN[OPEN_KEYS[key]]) + 1
    return None


# --- B12: wrong-side tolerance, the PO3 sequence, Judas depth ---------------------------------------------------------------------------

def open_tol_ok(ctx, sd, sw, i: int, p, session: str, entry: float, ref_open_px: float) -> bool:
    """BH-B12-midnight-open-tolerance (006 ~25:38; 010 ~38:48): the entry may sit up to `open_tol_pts` ES points on the WRONG side of the reference
    open when (a) the session's extreme since 00:00 (13:30 in the PM) already went beyond the open in the Judas direction, (b) the entry is at an
    FVG / OB (every entry here is) and (c) an MSS followed that move (sw["broke"] after the extreme). Side space: a long's wrong side is above the open."""
    hit("open_tol")
    x = sd.x(ref_open_px)
    if entry - x > p.open_tol_pts * p.es_pt + 1e-9:
        return False
    a = sess_a(ctx, session)
    b = sw.get("broke")
    if b is None:
        return False                                   # (c) no MSS yet
    seg = sd.l[a:b]                                    # the Judas: the open traded through BEFORE the MSS bar
    return bool(len(seg) and seg.min() < x - 1e-9)


def po3_seq_state(ctx, sd, sw, i: int, p, session: str, entry: float):
    """BH-B12-po3-sequence (006 ~6:33): True when the preferred order held - (1) a trade beyond the reference open after 00:00 (13:30), (2) a LATER
    close back across it before the MSS, (3) the entry at or on the right side of the open within `po3_seq_below_pts` of it. None = no open yet."""
    r = ref_open(ctx, p, session, i)
    if r is None:
        return None
    hit("po3_seq")
    x = sd.x(r)
    a = sess_a(ctx, session)
    b = sw.get("broke")
    end = i if b is None else b
    below = np.flatnonzero(sd.l[a:end + 1] < x - 1e-9)
    if not len(below):
        return False
    j1 = a + int(below[0])
    stop_at = end + 1 if b is None else end          # the MSS bar itself does not count as the close back
    if not (sd.c[j1 + 1:stop_at] > x).any():
        return False
    return bool(entry <= x + p.po3_seq_below_pts * p.es_pt + 1e-9)


def judas_depth(ctx, sd, sw, i: int, p, session: str):
    """B12-judas-depth-adr (cc08_003 ~12:59, FX translated by ADR): (reference open - the sweep extreme) / ADR5 in side terms (0 when the extreme is
    not beyond the open); None without an open or an ADR."""
    r = ref_open(ctx, p, session, i)
    a5 = adr5(ctx)
    if r is None or not a5:
        return None
    return max(0.0, (sd.x(r) - sw["ext"]) / a5)


def touch_count(ctx, sd, sw, i: int, p, session: str) -> int:
    """X3-graduated-pricing-second-touch (cc04_010 ~11:24): the touches (separate approaches, not bars) of the swept level since it formed, the sweep
    itself included: earlier bars whose low came within 4 x eq_tol_pts above the level without trading through it."""
    hit("touch_count")
    S = _S()
    v = sw["level"]
    a = S._level_created(ctx, str(sw.get("key", "")), session)
    j = sw.get("sweep_i", sw["ext_i"])
    a = min(max(int(a), 0), j)
    tol4 = 4 * p.eq_tol_pts * p.es_pt
    near = (sd.l[a:j] <= v + tol4) & (sd.l[a:j] >= v - 1e-9)
    n = int(near[0]) + int(np.count_nonzero(near[1:] & ~near[:-1])) if len(near) else 0
    return n + 1


# --- A8 / B12 / B5 narrative gates ------------------------------------------------------------------------------------------------------

def _closed_through(sd, z, i: int) -> int | None:
    """First bar after the zone formed whose CLOSE is beyond its far edge in the zone's own direction (side space: a bull zone closed below its
    bottom = a real bearish FVG closed through upward), else None."""
    seg = sd.c[z.i + 1:i + 1]
    k = np.flatnonzero(seg < z.bottom)
    return None if not len(k) else int(z.i + 1 + k[0])


def inverted_against_draw(ctx, sd, i: int, p, entry: float) -> bool:
    """BH-A8-opposing-FVG-inversion-confirms (015 ~26:19): the entry sits inside an FVG of the trade's own orientation (a real bearish FVG for a
    short) that was already CLOSED THROUGH the draw's way earlier in the day - not a short while the bullish draw is unmet."""
    tol = p.eq_tol_pts * p.es_pt
    for g in sd.gaps:
        if g.i < ctx.start or g.i > i:
            continue
        if g.bottom - tol <= entry <= g.top + tol and _closed_through(sd, g, i) is not None:
            return True
    return False


def ifvg_confirmed(ctx, sd, sw, i: int, p) -> bool:
    """A8 (061 ~46:50): with the draw our way, a bearish (side space) FVG formed today was closed through, RETESTED (a later low inside it) and
    HELD (no later close below its bottom) before the MSS - then the entry pattern may follow."""
    b = sw.get("broke")
    end = i if b is None else b
    for z in sd.opposing():
        if z.i < ctx.start or z.i > i:
            continue
        seg = sd.c[z.i + 1:end + 1]
        k = np.flatnonzero(seg > z.top)
        if not len(k):
            continue
        kk = z.i + 1 + int(k[0])
        lows = sd.l[kk + 1:end + 1]
        if not len(lows) or not ((lows <= z.top) & (lows >= z.bottom - 1e-9)).any():
            continue
        if (sd.c[kk + 1:i + 1] < z.bottom).any():
            continue
        return True
    return False


def ifvg_gate(ctx, sd, sw, i: int, p, entry: float):
    """The A8 narrative gate: a reject key or None."""
    if p.ifvg_narrative == "off":
        return None
    w = want(ctx)
    if not w:
        return None
    hit("ifvg_narrative")
    if w == -sd.sign and inverted_against_draw(ctx, sd, i, p, entry):
        return "x_inverted_against_draw"
    if w == sd.sign and p.ifvg_narrative == "require" and not ifvg_confirmed(ctx, sd, sw, i, p):
        return "x_ifvg_narrative"
    return None


def gap_premium_gate(ctx, sd, sw, i: int, p, lvt: list):
    """BH-B12-gap-up-short-below-0930 (044 ~34:06): a gap up (09:30 open above the prior RTH close) into an HTF bear array (an old NWOG CE counts):
    no longs, shorts only after a trade below the 09:30 open; the mirror for a gap down into a bull array. Tags the SMT state of the sweep."""
    S = _S()
    o930 = S._open_known(ctx, "0930", i)
    hs = getattr(ctx, "hist", None)
    cf = getattr(ctx, "conf", None)
    if o930 is None or not hs or cf is None:
        return None
    c = _c(ctx)
    if "gp" not in c:
        k930 = S._idx_at(ctx, 570)
        pc = float(hs[-1].close.iloc[-1])
        g = 1 if o930 > pc else -1 if o930 < pc else 0
        arr = False
        if g:
            tol = p.eq_tol_pts * p.es_pt
            for top, bot, *_ in cf.valid(now_ts(ctx, k930), -g, ("15m", "30m", "1h", "4h", "D", "W"), (0, 1, 2), now_ts(ctx, k930)):
                if bot - tol <= o930 <= top + tol:
                    arr = True
                    break
        c["gp"] = (g, arr, k930)
    g, arr, k930 = c["gp"]
    if not g or not arr:
        return None
    hit("gap_premium")
    if sd.sign == g:                                   # the gap's own direction (longs after a gap up): not chased
        return "x_gap_premium_long"
    seg = ctx.l[k930:i + 1] if g > 0 else ctx.h[k930:i + 1]
    if not len(seg) or (seg.min() >= o930 if g > 0 else seg.max() <= o930):
        return "x_gap_premium_wait"
    lvt.append("gap_premium_smt" if sw.get("smt") is True else "gap_premium_nosmt")
    return None


def mature_flag_gate(ctx, sd, i: int, p):
    """B5-mature-trend-continuation (cc02_007 ~1:56): a with-trend continuation (the order's side = the prior 5-day trend) is a possible false flag when
    the prior daily close is beyond `mature_pd` of the 20-day range (its premium for longs, discount for shorts) or inside an opposing daily array."""
    hs = getattr(ctx, "hist", None)
    if not hs or len(hs) < 6:
        return None
    cl = [float(x.close.iloc[-1]) for x in hs[-6:]]
    trend = np.sign(cl[-1] - cl[0])
    if trend != sd.sign:
        return None
    hit("mature_flag")
    rng = hs[-20:]
    hi, lo = max(float(x.high.max()) for x in rng), min(float(x.low.min()) for x in rng)
    if hi > lo:
        pdv = (cl[-1] - lo) / (hi - lo)
        if (pdv if sd.sign > 0 else 1.0 - pdv) > p.mature_pd:
            return "x_mature_flag"
    cf = getattr(ctx, "conf", None)
    if cf is not None and "D" in cf.at(now_ts(ctx, i), cl[-1], -sd.sign):
        return "x_mature_flag"
    return None


def far_edge_gate(ctx, sd, sw, i: int, p, lvt: list):
    """BH-premium-FVG-CE-vs-far-edge-trap (062 ~15:56): the entry lies inside an HTF (60m) FVG of the trade's side; the retrace into it that reached its far
    edge (within 10% of its height) is a trap - no trade; one held at / below the CE is tagged ce_hold. Real prices, from the bar the array was known."""
    cf = getattr(ctx, "conf", None)
    if cf is None:
        return None
    S = _S()
    ent_r = sd.x(float(sw.get("entry_ref", sd.c[i])))
    now = now_ts(ctx, i)
    best = None
    for top, bot, tf, src, known in cf.valid(now, sd.sign, ("1h",), (0,)):
        if bot - 1e-9 <= ent_r <= top + 1e-9 and (best is None or known > best[4]):
            best = (top, bot, tf, src, known)
    if best is None:
        return None
    hit("far_edge")
    top, bot, _, _, known = best
    kb = int(ctx.idx.searchsorted(pd.Timestamp(int(known), tz="UTC").tz_convert(ctx.idx.tz)))
    kb = max(kb, ctx.start)
    # side space: the zone is [zb, zt]; the retrace extreme is the lowest low once price first traded into it from above
    zt, zb = max(sd.x(top), sd.x(bot)), min(sd.x(top), sd.x(bot))
    seg = sd.l[kb:i + 1]
    ent = np.flatnonzero(seg <= zt)
    if not len(ent):
        return None
    deep = float(seg[ent[0]:].min())
    h = zt - zb
    if deep < zb + 0.1 * h + 1e-9:
        return "x_far_edge_trap"
    if deep >= (zt + zb) / 2 - 1e-9:
        lvt.append("ce_hold")
    return None


# --- pools: compressed highs, runs, lod zone ---------------------------------------------------------------------------------------------

def dealing_eq(ctx, sd, i: int) -> float:
    """[our interpretation] the dealing range's equilibrium = the middle of today's range through bar i (side space)."""
    a = ctx.start
    return float((sd.h[a:i + 1].max() + sd.l[a:i + 1].min()) / 2)


def compressed_gate(ctx, sd, sw, i: int, p, lvt: list):
    """BH-compressed-higher-highs (028 ~1:26:02): (a) a with-trend order whose MSS reference is one of a compressed run of higher highs above the
    dealing-range EQ (the buy-side engineering) is rejected; (b) the opposite order after an MSS below such a run (the opposite Side's run) is tagged
    compressed_hh. Returns a reject key or None."""
    a5 = adr5(ctx)
    if not a5:
        return None
    hit("compressed")
    ref_i = sw.get("ref_i")
    own = [q for q in sd.ph if q.known <= i and q.i >= ctx.start]
    run = L.compressed_run(own, a5, p.compressed_k, p.compressed_n, dealing_eq(ctx, sd, i), i)
    if run and ref_i is not None and ref_i in {q.i for q in run}:
        return "x_compressed_hh"
    ot = other_side(ctx, sd, p)
    oth = [q for q in ot.ph if q.known <= i and q.i >= ctx.start]
    orun = L.compressed_run(oth, a5, p.compressed_k, p.compressed_n, dealing_eq(ctx, ot, i), i)
    b = sw.get("broke")
    if orun and b is not None and b > orun[-1].i:
        lvt.append("compressed_hh")
    return None


def compressed_leg_low(ctx, sd, sw, i: int, p):
    """The first target of a short after the MSS below a compressed run: the leg low (the low before the run's first high), in this Side's space; None
    when there is no such run."""
    a5 = adr5(ctx)
    if not a5:
        return None
    ot = other_side(ctx, sd, p)
    oth = [q for q in ot.ph if q.known <= i and q.i >= ctx.start]
    orun = L.compressed_run(oth, a5, p.compressed_k, p.compressed_n, dealing_eq(ctx, ot, i), i)
    b = sw.get("broke")
    if not orun or b is None or b <= orun[-1].i:
        return None
    a = ctx.start + int(np.argmax(ot.h[ctx.start:orun[0].i + 1]))
    low = float(ot.l[a:orun[0].i + 1].min())
    return sd.x(ot.x(low))


def pool_runs(ctx, sd, i: int, p, session: str) -> int:
    """BH-three-pool-runs-exhaustion (048 ~1:13:41, DXY): the number of successive pools of the order's direction (a short: sell-side pools) the leg took.
    The leg starts at the last MSS in the opposite direction (the last close beyond the latest confirmed swing extreme the other way; the day's
    start without one) [our interpretation]; pools = the day's named sell-side pools of the other Side below the leg's start plus the swing extremes
    formed before it, counted when the leg traded a tick through them."""
    S = _S()
    ot = other_side(ctx, sd, p)                # real orientation of the leg's pools: the other Side's sell side = the order's direction
    a = ctx.start
    ph = ot.ph
    jp = 0
    for k in range(ctx.start, i + 1):
        while jp < len(ph) and ph[jp].known <= k - 1:
            jp += 1
        if jp and ot.c[k] > ph[jp - 1].price and ph[jp - 1].i >= ctx.start - 1:
            a = k
    start_px = float(ot.h[a])
    tk = S._tick(p)
    cands = []
    for k, v in S._sell_side(ctx, ot, session, i, p.extra_pools, p).items():
        cr = S._level_created(ctx, k, session)               # a pool formed after the leg started (the opening range ...) was not taken BY the leg
        if cr <= a:
            cands.append((v, max(int(cr), ctx.start)))
    cands += [(q.price, q.i + 1) for q in ot.pl if q.known <= a and q.i < a]
    # a pool the leg took must still be standing when the leg starts: nothing traded through it between its formation and bar a
    lv = sorted({round(v, 6) for v, since in cands if v < start_px and ot.l[since:a + 1].min(initial=np.inf) >= v - 1e-9})
    low = float(ot.l[a:i + 1].min())
    taken = [v for v in lv if S._thru(low, v, tk)]
    out, last = 0, None
    gap = max(p.eq_tol_pts * p.es_pt, 1e-9)
    for v in taken:                              # distinct pools: levels closer than eq_tol_pts are one pool
        if last is None or v - last > gap:
            out += 1
        last = v
    return out


def pool_runs_gate(ctx, sd, i: int, p, session: str):
    if p.pool_runs_max <= 0:
        return None
    hit("pool_runs")
    return "x_pool_runs_exhausted" if pool_runs(ctx, sd, i, p, session) >= p.pool_runs_max else None


def lod_zone(ctx, sd, i: int, p):
    """NEW-low-of-day-zone-tag-first (093 ~8:46) [our interpretation of the definition]: at 08:30, the nearest completed 60m candle tail's CE
    (side space: low .. body bottom) below the price at 08:30 that has a 5m FVG of the side (or a daily array of the side) within eq_tol_pts. Cached
    per day and side; None before 08:30 or without a candidate."""
    S = _S()
    k830 = S._idx_at(ctx, 510)
    if k830 >= len(ctx.t) or k830 > i or k830 - 1 < ctx.start:
        return None
    c = _c(ctx)
    key = ("lod", sd.sign)
    if key in c:
        return c[key]
    tol = p.eq_tol_pts * p.es_pt
    px = float(sd.c[k830 - 1])
    a5 = adr5(ctx)
    tail_min = max(0.1 * a5 if a5 else 0.0, 4 * tol)
    ts = ctx.idx[ctx.start:k830]
    grp = pd.Series(np.arange(ctx.start, k830), index=ts).groupby(ts.floor("60min"))
    ces = []
    for _, g in grp:
        a, z = int(g.min()), int(g.max())
        if (ctx.idx[z] + pd.Timedelta(minutes=ctx.tf)) - ctx.idx[a].floor("60min") < pd.Timedelta(minutes=60):
            continue                                             # the hour is incomplete at 08:30
        lo = float(sd.l[a:z + 1].min())
        bb = float(min(sd.o[a], sd.c[z]))
        if bb - lo >= tail_min and (lo + bb) / 2 < px:        # [our interpretation] a TAIL = a lower wick of at least 0.1 x ADR5 (and 4 x eq_tol_pts)
            ces.append((lo + bb) / 2)
    z5 = [z for z in sd.zones_tf(ctx.idx, ctx.tf, 5) if z.mt != z.mt and z.i < k830]
    cf = getattr(ctx, "conf", None)
    res = None
    for ce in sorted(ces, reverse=True):
        if any(z.bottom - tol <= ce <= z.top + tol for z in z5) or (
                cf is not None and "D" in cf.at(ctx.idx[k830], sd.x(ce), sd.sign)):
            res = ce
            break
    c[key] = res
    return res


def lod_gate(ctx, sd, sw, i: int, p):
    """NEW-low-of-day-zone-tag-first: no longs (shorts: the mirror) until a bar traded down to the zone + 2 ticks, then the sweep needs the SMT tag."""
    z = lod_zone(ctx, sd, i, p)
    if z is None:
        return None
    hit("lod_zone")
    k830 = _S()._idx_at(ctx, 510)
    if sd.l[k830:i + 1].min() > z + 2 * p.tick + 1e-9:
        return "x_lod_zone_first"
    if sw.get("smt") is not True and not sw.get(_S()._SM.SYNTH):         # (a synthetic setup - no sweep - has no SMT tag to ask for)
        return "x_lod_no_smt"
    return None


# --- SMT (B18) -------------------------------------------------------------------------------------------------------------------------------

def smt_bias_gate(ctx, sd, sw, p) -> None:
    """B18-smt-only-with-bias (099 ~56:49): an SMT counts only on the bias side - against the bias the non-confirming index is a LAGGARD expected to catch
    up (the sweep's SMT result becomes False, tag smt_laggard). With no bias the result stays and order_gate rejects the SMT-qualified order."""
    w = want(ctx)
    if not w or w == sd.sign:
        return
    for k in ("smt", "smt2"):
        if sw.get(k) is True:
            hit("smt_laggard")
            sw[k] = False
            sw["smt_laggard"] = True


def lunch_post(ctxx, sx, upto: int):
    """B18-pm-smt-reference-points (cc10_014 ~2:18): (the 12:00-13:00 low, the first pivot low (n=1) formed after 13:00 - confirmed by `upto`) in side
    space for one instrument, or None while either is missing."""
    S = _S()
    k12, k13 = S._idx_at(ctxx, 720), S._idx_at(ctxx, 780)
    if k13 > upto or k13 >= len(ctxx.t) or k13 <= k12:
        return None
    lunch = float(sx.l[k12:k13].min())
    for k in range(k13, upto):
        if sx.l[k] < sx.l[k - 1] and sx.l[k] < sx.l[k + 1]:
            return lunch, float(sx.l[k])
    return None


def pm_points(ctx, sd, i: int, pctx, ps, j: int):
    """True when exactly one of the two indices made a lower low after 13:00 than its lunch-hour low (the other failed to: SMT), False when both or neither
    did, None while a pivot is missing. Bullish terms in side space (the mirror runs on the mirrored Sides)."""
    a, b = lunch_post(ctx, sd, i), lunch_post(pctx, ps, j)
    hit("pm_points")
    if a is None or b is None:
        return None
    return bool((a[1] < a[0]) != (b[1] < b[0]))


# --- A19: MSS vs the HTF flow, the stop-run re-arm ----------------------------------------------------------------------------------------------

def mss_htf_reject(ctx, sd, sw, i: int, p, session: str, ref_i: int, ref: float) -> bool:
    """A19-break-against-htf-stop-run (cc09_004 ~9:01; 102 ~39:11): an intraday MSS counts only when it does not oppose the HTF flow (the bias column);
    a break against it is a stop run. True = reject. With stoprun_rearm the opposite Side's sweep is armed once (the stops this break ran)."""
    w = want(ctx)
    if w != -sd.sign:
        return False
    hit("mss_htf_reject")
    if p.stoprun_rearm and not sw.get("sr_armed"):
        sw["sr_armed"] = True
        sm = getattr(ctx, "sides_map", None)
        o = sm.get(-sd.sign) if sm else None
        if o is not None and o.sweep is None:
            hit("stoprun_rearm")
            seg = o.l[sw["ext_i"]:i + 1]
            ext_i = sw["ext_i"] + int(np.argmin(seg))
            o.sweep = dict(session=session, name="stoprun", level=float(o.x(sd.x(ref))), key="stoprun", ext=float(o.l[ext_i]), ext_i=ext_i,
                           broke=None, sweep_i=i, smt=None, smt2=None)
    return True


# --- A13: breakers --------------------------------------------------------------------------------------------------------------------------

def breaker_confirmed(ctx, sd, sw, bz, i: int, p) -> bool:
    """A13-breaker-needs-rebalance-and-fvg (cc04_005 ~4:31; 001 ~56:19): breaker_needs_disp - the break leg leaves an FVG (its middle candle between the
    sweep extreme and the break) completed within `breaker_disp_bars` bars of the break [our interpretation of the speed window]; breaker_break_ref
    "body_high" - the breaker has 'left' only once a close is above the breaker candle's BODY high."""
    b = sw.get("broke")
    if b is None:
        return False
    if p.breaker_needs_disp:
        hit("breaker_disp")
        if not any(sw["ext_i"] <= g.src <= b and g.i <= min(b + p.breaker_disp_bars, i) for g in sd.gaps):
            return False
    if p.breaker_break_ref == "body_high":
        hit("breaker_body_high")
        bh = float(max(sd.o[bz.src], sd.c[bz.src]))
        if not (sd.c[b:i + 1] > bh).any():
            return False
    return True


def breaker_by_close_ok(ctx, sd, sw, ref_i: int, i: int) -> bool:
    """A13-breaker-close-vs-wick (035 ~42:44): the candle that BREAKS the swing must close its body beyond it to mark the breaker; a wick through it is an MSS
    without one (FVG entry). [our interpretation] It is the breaking bar itself that is judged: a later close does not turn the wick break into a breaker."""
    b = sw.get("broke")
    hit("breaker_by_close")
    return bool(b is not None and sd.c[b] > sd.h[ref_i])


def _zone_overlap(e: dict, bz) -> bool:
    return bool(bz.bottom <= e["top"] and bz.top >= e["bottom"]) or bool(bz.bottom >= e["bottom"])


def brk_alive(sd, e: dict, i: int, p) -> bool:
    seg = sd.c[e["born"] + 1:i + 1]
    lvl = e["mt"] if (p.breaker_mt_respect and e["mt"] == e["mt"]) else e["bottom"]
    return not len(seg) or bool(seg.min() >= lvl)


def breaker_register(ctx, sd, sw, bz, i: int, p) -> None:
    """A13-breaker-lifetime (043 ~4:43, ~16:07; 015 ~22:43): remember the day's breakers. breaker_keep_original - a newer breaker formed on top of (or
    overlapping) an alive one is not remembered; otherwise it replaces the zones it overlaps."""
    reg = _c(ctx).setdefault(("brk", sd.sign), [])
    new = dict(top=float(bz.top), bottom=float(bz.bottom), mt=float(bz.mt), src=int(bz.src), born=i, sw=dict(sw), armed_i=None)
    hit("breaker_register")
    if p.breaker_keep_original and any(brk_alive(sd, e, i, p) and _zone_overlap(e, bz) for e in reg):
        return
    if any(abs(e["top"] - new["top"]) < 1e-9 and abs(e["bottom"] - new["bottom"]) < 1e-9 for e in reg):
        return
    if not p.breaker_keep_original:
        reg[:] = [e for e in reg if not (bz.bottom <= e["top"] and bz.top >= e["bottom"])]
    reg.append(new)


def breaker_retest_order(ctx, sd, i: int, p, session: str, risk_mult: float):
    """A13-breaker-lifetime: a remembered, alive breaker that price retested (traded into) and left again arms a resting limit at its top once per retest,
    to the end of the day (PM last hour included). The first touch is the ordinary flow's; this is the REPEAT retest."""
    S = _S()
    for e in sorted(_c(ctx).get(("brk", sd.sign), []), key=lambda e: -e["born"]):
        if i <= e["born"] or not brk_alive(sd, e, i, p) or not sd.c[i] > e["top"]:
            continue
        last = e["born"] if e["armed_i"] is None else e["armed_i"]
        if not sd.l[last + 1:i + 1].min(initial=np.inf) <= e["top"]:
            continue
        e["armed_i"] = i
        hit("breaker_retest")
        bz = L.Zone("bull", e["top"], e["bottom"], i, e["src"], e["mt"])
        sw = dict(e["sw"], session=session)
        sw.pop("bz_sent", None)
        return S._breaker_order(ctx, sd, sw, bz, i, p, session, risk_mult)
    return None


# --- A5: daily SIBI / BISI short (long) zone ------------------------------------------------------------------------------------------------

def htf_sibi_gate(ctx, sd, sw, i: int, p, entry: float, lvt: list, lvx: dict):
    """A5-short-into-htf-sibi (035 ~1:05:16): inside a daily SIBI (BISI for longs) the entry must lie between its low and its CE (CE and top for longs);
    once the CE has traded the zone is skipped; best in the lower quarter (tag sibi_q1); with htf_sibi_need_smt the sweep needs an SMT; a body close
    beyond the CE after the fill exits (lvx htf_sibi_ce). Real arrays (conf, D, FVGs), translated to side space."""
    cf = getattr(ctx, "conf", None)
    if cf is None:
        return None
    now = now_ts(ctx, i)
    ent_r = sd.x(entry)
    tol = p.eq_tol_pts * p.es_pt
    for top, bot, tf, src, known in cf.valid(now, sd.sign, ("D",), (0,)):
        if not (bot - tol <= ent_r <= top + tol):
            continue
        hit("htf_sibi")
        ce = (top + bot) / 2
        kb = max(int(ctx.idx.searchsorted(pd.Timestamp(int(known), tz="UTC").tz_convert(ctx.idx.tz))), 0)
        seg_h, seg_l = ctx.h[kb:i + 1], ctx.l[kb:i + 1]
        traded_ce = (seg_h.max() > ce + 1e-9) if sd.sign < 0 else (seg_l.min() < ce - 1e-9)
        zt, zb = max(sd.x(top), sd.x(bot)), min(sd.x(top), sd.x(bot))
        ce_s = sd.x(ce)
        # real: a short's valid span is the zone's low up to its CE (a long's: its top down to the CE) = side space: at or above the CE's image
        if entry < ce_s - 1e-9:
            return "x_sibi_above_ce"
        if traded_ce:
            return "x_sibi_ce_traded"
        if p.htf_sibi_need_smt and not (sw.get("smt") is True or sw.get("smt2") is True):
            return "x_sibi_no_smt"
        if entry >= zt - 0.25 * (zt - zb) - 1e-9:          # the quadrant at the zone's near edge (a short: its lowest 25%)
            lvt.append("sibi_q1")
        lvx["htf_sibi_ce"] = (float(ce_s), False)
        lvt.append("htf_sibi")
        return None
    return None


# --- T3 / T13 ------------------------------------------------------------------------------------------------------------------------------------

def lc_reversal(ctx, sd, sw, i: int, p, cf, htf) -> bool:
    """T3-london-close-multiday-reversal (cc09_005 ~32:44): an entry armed in 10:00-12:00 whose sweep extreme sat at an HTF array and ran against the
    morning (side space: below the 09:30 open) - a possible multi-day turn."""
    S = _S()
    t = ctx.t[i]
    if not 600 <= t < 720:
        return False
    o930 = S._open_known(ctx, "0930", i)
    if o930 is None or not sw["ext"] < sd.x(o930) - 1e-9:
        return False
    return bool(S._htf_array(cf, p) if cf is not None else htf)


def lc_reopen(ctx, tr, done: dict, key: str, state: dict) -> None:
    """T3 lc_reentry: after a stopped-out lc_reversal one more try (the one-trade-per-session flag is re-opened for this case only)."""
    hit("lc_reopen")
    done[key] = False
    state["lc_done"] = True
    ctx.lc_retry = dict(side=1 if tr.side == "long" else -1, ext_px=float(tr.ext_px) if tr.ext_px is not None else None)


def lc_retry_gate(ctx, sd, sw, i: int, p, lc: bool):
    """While the re-opened slot is live every order must be the retry: same direction, 10:00-12:00, a sweep BEYOND the first extreme at an HTF array."""
    ry = getattr(ctx, "lc_retry", None)
    if not ry:
        return None
    hit("lc_retry")
    if not (sd.sign == ry["side"] and lc and ry["ext_px"] is not None and sw["ext"] < sd.x(ry["ext_px"]) - 1e-9):
        return "x_lc_retry"
    return None


def judas_news(ctx, sw, p) -> bool:
    """T13-judas-news-driver (cc01_002 ~15:16): the Judas sweep's extreme came within `judas_news_min` minutes of a scheduled release."""
    from . import newscal as NC
    t = int(ctx.t[sw["ext_i"]])
    return any(R - p.judas_news_min <= t <= R + p.judas_news_min for R in NC.releases(ctx.day, p))


def am_leg(ctx, k810: int):
    """The AM leg (09:30-12:00): (direction, high, low) - +1 when its low came before its high and it closed above its open, -1 the mirror, else 0."""
    S = _S()
    a, b = S._idx_at(ctx, 570), min(S._idx_at(ctx, 720), k810)
    if b - a < 2:
        return 0, None, None
    h, l, o, c = ctx.h[a:b], ctx.l[a:b], ctx.o[a:b], ctx.c[a:b]
    ih, il = int(np.argmax(h)), int(np.argmin(l))
    d = 1 if (il < ih and c[-1] > o[0]) else -1 if (ih < il and c[-1] < o[0]) else 0
    return d, float(h.max()), float(l.min())


def pm_profile_gate(ctx, sd, sw, i: int, p, session: str, entry: float, lvt: list):
    """DS2-two-session-close-templates / DS2-consolidation-profiles (cc10_013 ~1:33-15:43), PM only."""
    if session != "PM" or not (p.profile_two_session or p.profile_consol_pm):
        return None
    S = _S()
    k810 = S._idx_at(ctx, 810)
    if i < k810 or k810 >= len(ctx.t):
        return None
    from .calendar import release_times
    d, ah, al = am_leg(ctx, k810)
    if d == 0:
        return None
    cf = getattr(ctx, "conf", None)
    now = now_ts(ctx, k810 - 1)
    ext_r = ah if d > 0 else al
    opp = lambda tfs: cf is not None and any(t_ in tfs for t_ in cf.at(now, ext_r, -d))
    bias = bias_at(ctx, p, session, i)
    if p.profile_two_session and bias == d and not opp(("4h", "D", "W")):
        hit("two_session")
        if sd.sign != d:
            return "x_two_session_counter"
        lo, hi = float(sd.l[ctx.start:i + 1].min()), float(sd.h[ctx.start:i + 1].max())
        if not (sw.get("key") == "lunch" or entry <= (lo + hi) / 2 + 1e-9):
            return "x_two_session_trigger"
        lvt.append("two_session_up" if d > 0 else "two_session_down")
        return None
    if p.profile_consol_pm and bias == 0 and not any(R >= 600 for R in release_times(ctx.day)):
        hit("consol_pm")
        htf_arr = opp(("1h", "4h", "D", "W", "M"))
        if sd.sign != -d:
            return "x_consol_pm_side"
        need = "lunch" if htf_arr else "am_session"
        if str(sw.get("key", "")) != need:
            return "x_consol_pm_pool"
        lvt.append("consol_am_rally" if d > 0 else "consol_am_decline")
    return None


def pm_extra_targets(ctx, sd, i: int, p, session: str, entry: float) -> list:
    """DS2-consolidation-profiles: after the PM sweep + MSS the counter side targets the day's / London's opposite pools (side space, > entry)."""
    if session != "PM" or not p.profile_consol_pm:
        return []
    out = []
    cand = [float(sd.h[ctx.start:i + 1].max())]          # side space: the day's far extreme in the trade's direction (a short: the day LOW, mirrored)
    lon = ctx.sess.get("london")
    if lon is not None:
        cand.append(float(sd.x(lon[0] if sd.sign > 0 else lon[1])))    # London's opposite extreme
    for v in cand:
        if v > entry:
            out.append((v, "pool"))
    return out


# --- the order gate ----------------------------------------------------------------------------------------------------------------------------

def order_gate(ctx, sd, sw, i: int, p, entry: float, stop: float, session: str, cf, htf, lvt: list, lvx: dict, tags: dict):
    """Gates / tags of this package at order completion (strategy._finish_order, after levels_detectors' own). Returns a reject key or None."""
    S = _S()
    if p.smt_with_bias and not want(ctx) and (sw.get("smt") is True or sw.get("smt2") is True):
        return "x_smt_no_bias"                             # B18: no clear daily IOF - the SMT is not traded
    if sw.get("smt_laggard"):
        lvt.append("smt_laggard")
    if p.touch_tag and sw.get("key") and "level" in sw and not sw.get(S._SM.SYNTH):
        try:
            tags["touch_n"] = touch_count(ctx, sd, sw, i, p, session)
        except Exception:                                  # a synthetic sweep without a level history
            pass
    if p.judas_max_adr:
        jd = judas_depth(ctx, sd, sw, i, p, session)
        if jd is not None:
            tags["judas_depth"] = round(float(jd), 4)
            hit("judas_depth")
            if jd > p.judas_max_adr + 1e-12:
                return "x_judas_too_deep"
    if p.po3_seq != "off":
        ps = po3_seq_state(ctx, sd, sw, i, p, session, entry)
        if ps is not None:
            tags["po3_seq"] = bool(ps)
            if ps:
                lvt.append("po3_seq")
            elif p.po3_seq == "filter":
                return "x_po3_seq"
        elif p.po3_seq == "filter":
            return "x_po3_seq"
    if p.wk_open_side:
        so = S._open_known(ctx, "sunday", i)
        if so is not None:
            tags["wk_open_side"] = int(np.sign(sd.x(entry) - so))
    r = ifvg_gate(ctx, sd, sw, i, p, entry)
    if r:
        return r
    if p.gap_premium_arm:
        r = gap_premium_gate(ctx, sd, sw, i, p, lvt)
        if r:
            return r
    if p.lod_zone_first:
        r = lod_gate(ctx, sd, sw, i, p)
        if r:
            return r
    if p.compressed_hh:
        r = compressed_gate(ctx, sd, sw, i, p, lvt)
        if r:
            return r
    r = pool_runs_gate(ctx, sd, i, p, session)
    if r:
        return r
    if p.far_edge_trap:
        sw_ = dict(sw, entry_ref=entry)
        r = far_edge_gate(ctx, sd, sw_, i, p, lvt)
        if r:
            return r
    if p.mature_flag_block:
        r = mature_flag_gate(ctx, sd, i, p)
        if r:
            return r
    if p.htf_sibi_short_zone:
        r = htf_sibi_gate(ctx, sd, sw, i, p, entry, lvt, lvx)
        if r:
            return r
    if p.lc_tag or p.lc_reentry:
        lc = lc_reversal(ctx, sd, sw, i, p, cf, htf)
        if lc:
            tags["lc_reversal"] = True
            lvt.append("lc_reversal")
        r = lc_retry_gate(ctx, sd, sw, i, p, lc)
        if r:
            return r
    r = pm_profile_gate(ctx, sd, sw, i, p, session, entry, lvt)
    if r:
        return r
    return None


def extra_targets(ctx, sd, sw, i: int, p, session: str, entry: float) -> list:
    """Extra target levels (side space, kind) of this package for _finish_order: the leg low after a compressed-highs MSS, the PM consolidation pools."""
    out = []
    if p.compressed_hh:
        v = compressed_leg_low(ctx, sd, sw, i, p)
        if v is not None and v > entry:
            out.append((v, "pool"))
    out += pm_extra_targets(ctx, sd, i, p, session, entry)
    return out


# --- order-time tags that need the targets (clean swing, array depth, the move) ---------------------------------------------------------

def bars_tf(ctx, sd, m: int, i: int):
    """Closed m-minute buckets of the day's bars through bar i (side space): (o, h, l, c, last base bar) arrays; a bucket counts only once its last base
    bar is in. Not cached across bars (small)."""
    idx = ctx.idx[:i + 1]
    b = pd.Series(np.arange(i + 1), index=idx).groupby(idx.floor(f"{m}min"))
    first, last = b.min().values, b.max().values
    ok = [(ctx.idx[z] + pd.Timedelta(minutes=ctx.tf)) - ctx.idx[a].floor(f"{m}min") >= pd.Timedelta(minutes=m) for a, z in zip(first, last)]
    first, last = first[ok], last[ok]
    o = np.array([sd.o[a] for a in first])
    c = np.array([sd.c[z] for z in last])
    h = np.array([sd.h[a:z + 1].max() for a, z in zip(first, last)])
    l = np.array([sd.l[a:z + 1].min() for a, z in zip(first, last)])
    return o, h, l, c, last, first


def clean_swing(ctx, sd, i: int, entry: float, t1: float) -> bool:
    """BH-D15-clean-swing-point (072 ~34:33): a 15m pivot (n=2) in the target direction between the entry and T1 (side space: a pivot high), pivots
    confirmed by closed 15m bars only."""
    o, h, l, c, last, first = bars_tf(ctx, sd, 15, i)
    if len(h) < 5:
        return False
    ph, _ = L.pivots(h, l, 2)
    return any(entry < q.price <= t1 + 1e-9 for q in ph)


def array_depth(ctx, sd, sw, i: int, p):
    """D15-short-index-by-premium-depth (086 ~9:49): (depth, respect) of the sweep in the highest HTF array of the side holding the sweep extreme.
    depth = how far the extreme ran from the array's near edge toward its far edge (side space: (top - extreme) / height); respect = the share of the
    closed 15m bodies inside the array that did not cross its far edge. (None, None) without an array."""
    cf = getattr(ctx, "conf", None)
    if cf is None:
        return None, None
    from .confluence import TFS
    now = now_ts(ctx, i)
    ext_r = sd.x(sw["ext"])
    tol = p.eq_tol_pts * p.es_pt
    best = None
    for top, bot, tf, src, known in cf.valid(now, sd.sign, ("15m", "30m", "1h", "4h", "D", "W"), (0, 1), ctx.idx[sw["ext_i"]] + pd.Timedelta(minutes=ctx.tf)):
        if bot - tol <= ext_r <= top + tol and (best is None or TFS.index(tf) > TFS.index(best[2])):
            best = (top, bot, tf, src, known)
    if best is None:
        return None, None
    hit("array_depth")
    top, bot = best[0], best[1]
    zt, zb = max(sd.x(top), sd.x(bot)), min(sd.x(top), sd.x(bot))
    if zt - zb <= 0:
        return None, None
    depth = max(0.0, (zt - sw["ext"]) / (zt - zb))
    o, h, l, c, last, first = bars_tf(ctx, sd, 15, i)
    kb = int(ctx.idx.searchsorted(pd.Timestamp(int(best[4]), tz="UTC").tz_convert(ctx.idx.tz)))
    keep = [k for k in range(len(h)) if first[k] >= kb]
    inside = [k for k in keep if min(o[k], c[k]) <= zt and max(o[k], c[k]) >= zb]
    respect = None if not inside else float(np.mean([min(o[k], c[k]) >= zb - 1e-9 for k in inside]))
    return round(float(depth), 4), None if respect is None else round(respect, 4)


def move_pct(ctx, sd, i: int, session: str, entry: float):
    """D15 smt_pick "middle": the move from the session open (09:30; 13:30 for the PM; midnight before 09:30) to the entry, in the trade direction, as a
    fraction of the open."""
    S = _S()
    t = ctx.t[i]
    nm = "1330" if session == "PM" else ("0930" if t >= 570 else "midnight")
    o = S._open_known(ctx, nm, i)
    if o is None or not o:
        return None
    return round(float((entry - sd.x(o)) / abs(o)), 6)


def late_tags(ctx, sd, sw, i: int, p, session: str, entry: float, lv: list, tags: dict) -> None:
    """Order-time tags that need the targets (strategy._finish_order, just before the order dict): clean_swing, array_depth / array_respect, move_pct."""
    if p.smt_pick == "clean_swing" and lv:
        tags["clean_swing"] = bool(clean_swing(ctx, sd, i, entry, lv[0]))
    if p.smt_pick == "depth":
        d, r = array_depth(ctx, sd, sw, i, p)
        tags["array_depth"], tags["array_respect"] = d, r
    if p.smt_pick == "middle":
        tags["move_pct"] = move_pct(ctx, sd, i, session, entry)


# --- mitigation-block entry (A15) -----------------------------------------------------------------------------------------------------------

def mit_order(ctx, sd, i: int, p, session: str, risk_mult: float):
    """A15-mitigation-block-entry (033 ~1:04:05; cc04_004 ~4:37, ~13:51) and X3-a15-mitblock-bear-context (cc04_004 ~6:44): with the order flow and
    narrative our way (the bias side), a resting limit in the day's alive mitigation block (the full range of the last down-close candle at the failed
    low for a short; side space: a bull zone below price) - at its near edge ("near") or CE ("mid") - stop beyond the block; once per retest, no
    expiry. Ranks below breakers (only tried when the sweep flow produced nothing). mit_needs_bias: the bias must be its way AND an untaken daily
    pool / array lies beyond - its level is the target. Sub-cases NOT built: the 041 pre-open consolidation block and the cc06_005 4h block."""
    S = _S()
    if want(ctx) != sd.sign:
        return None
    sent = sd.__dict__.setdefault("_mit_sent", {})
    for z in sorted(sd.mitigations(), key=lambda z: -z.i):
        if z.i > i or z.i < ctx.start or not L.mitigation_alive(sd.c, z, i, p.mit_mt_invalid):
            continue
        if not sd.c[i] > z.top:
            continue
        last = sent.get((z.i, z.src))
        a = z.i if last is None else last
        if last is not None and not sd.l[a + 1:i + 1].min(initial=np.inf) <= z.top:
            continue                                     # no new retest since the last arm
        entry = z.top if p.mit_entry_px == "near" else (z.top + z.bottom) / 2
        if entry >= sd.c[i]:
            continue
        stop = z.bottom - p.pad
        fixed = None
        if p.mit_needs_bias:
            tgt = daily_beyond(ctx, sd, i, p, entry)
            if tgt is None:
                S._f("x_mit_no_daily_beyond")
                continue
            fixed = [(S._exit_px(tgt, "pool", p), "pool")]
        sent[(z.i, z.src)] = i
        hit("mit_order")
        sw = dict(session=session, name="mitigation", level=float(z.top), key="mitigation", ext=float(z.bottom), ext_i=int(z.src), broke=int(z.i),
                  sweep_i=int(z.src), smt=None, smt2=None, **{S._SM.SYNTH: True})
        tags = dict(unicorn=False, fvg_bottom=float(z.bottom), fvg_ce=float((z.top + z.bottom) / 2), entry_kind="mitigation_entry", mitigation=True,
                    propulsion=False, no_leg_wait=True, lv_tags=["mitigation_entry"])
        return S._finish_order(ctx, sd, i, p, session, sw, entry, stop, risk_mult, float(sd.h[z.src:i + 1].max()), tags, skip_leg_pd=True, fixed=fixed)
    return None


def daily_beyond(ctx, sd, i: int, p, entry: float):
    """The nearest untaken daily pool (the prior days' extremes ctx.pd) or daily array edge beyond the entry in the trade's direction (side space)."""
    cands = []
    keys = ("pdh1", "pdh2", "pdh3") if sd.sign > 0 else ("pdl1", "pdl2", "pdl3")
    for k in keys:
        if k in ctx.pd:
            cands.append(sd.x(ctx.pd[k]))
    cf = getattr(ctx, "conf", None)
    if cf is not None:
        for near, ce, far, tf, src in cf.opposing(now_ts(ctx, i), sd.x(entry), sd.sign, ("D",), (0,)):
            cands.append(sd.x(near))
    cands = [v for v in cands if v > entry]
    return min(cands) if cands else None


# --- release setups (N1 / N5) ----------------------------------------------------------------------------------------------------------------

def release_setups(ctx, sides, i: int, p, state: dict, pos, pending, risk_mult: float):
    """The three setups that fire around a scheduled release and bypass the news windows (nfp_floor_min / news_wait / nfp_first_hour) for themselves
    only: N1-nfp-release-4h-fvg, N5-entry-at-release (a) post_news_continuation, (b) release_ob_entry. Returns an order or None; each fires at most once a
    day (state["sm2_sent"]). Armed on the bar that has just closed."""
    if pos is not None or pending is not None:
        return None
    S = _S()
    sent = state.setdefault("sm2_sent", set())
    t = int(ctx.t[i])
    end = t + ctx.tf
    from claude_hf.daytypes import events
    from . import newscal as NC
    tags = events(ctx.day)
    rel = NC.releases(ctx.day, p)
    saved = {k: ctx.__dict__[k] for k in ("cur_lock", "cur_bias", "cur_news", "cur_sloppy", "cur_no_draw") if k in ctx.__dict__}
    out = None
    try:
        ctx.cur_lock, ctx.cur_news, ctx.cur_sloppy, ctx.cur_no_draw, ctx.cur_bias = None, None, "", False, 0
        if p.nfp_release_fvg and "nfp" not in sent and "jobs" in tags and end == 510:
            sent.add("nfp")
            out = nfp_release_order(ctx, sides, i, p, risk_mult)
        if out is None and p.release_ob_entry and "relob" not in sent and 600 in rel and end == 600:
            sent.add("relob")
            out = release_ob_order(ctx, sides, i, p, risk_mult)
        if out is None and p.post_news_continuation and "pnc" not in sent and 510 in rel and 515 <= end <= 570:
            out = post_news_order(ctx, sides, i, p, risk_mult, sent)
    finally:
        for k in ("cur_lock", "cur_bias", "cur_news", "cur_sloppy", "cur_no_draw"):
            if k in saved:
                setattr(ctx, k, saved[k])
            else:
                ctx.__dict__.pop(k, None)
    return out


def _side_of(sides, b: int):
    return sides[0] if b > 0 else sides[1]


def nfp_release_order(ctx, sides, i: int, p, risk_mult: float):
    """N1-nfp-release-4h-fvg (105 ~5:54): NFP day, 4h bias: the nearest 4h FVG of the bias side on the discount side of the swing range (its CE below the
    range EQ; the 20-session range [our interpretation]) below price; a limit at its upper edge armed for the release, valid `nfp_release_fvg_min` minutes
    from 08:30 (the existing pending-fill block), the stop under the FVG (the FVG low - the stop pad: the lower candle body is not on the array),
    50% at the first pool and the rest to the draw (the table's draw), breakeven + commissions at the first target, one small add at the CE
    (nfp_release_fvg_add). Returns an order or None."""
    S = _S()
    cf = getattr(ctx, "conf", None)
    if cf is None:
        return None
    b = bias_at(ctx, p, "NEWS", i)
    if not b:
        return None
    sd = _side_of(sides, b)
    ctx.cur_bias = b
    now = now_ts(ctx, i)
    px = float(ctx.c[i])
    hs = getattr(ctx, "hist", None) or []
    rng = hs[-20:]
    if not rng:
        return None
    hi = max(float(x.high.max()) for x in rng)
    lo = min(float(x.low.min()) for x in rng)
    eq = (hi + lo) / 2
    cand = []
    for top, bot, tf, src, known in cf.valid(now, b, ("4h",), (0,)):
        ce = (top + bot) / 2
        if b > 0 and top < px and ce < eq:
            cand.append((px - top, top, bot))
        if b < 0 and bot > px and ce > eq:
            cand.append((bot - px, top, bot))
    if not cand:
        return None
    _, top, bot = min(cand)
    zt, zb = max(sd.x(top), sd.x(bot)), min(sd.x(top), sd.x(bot))
    entry, stop = zt, zb - p.pad
    if entry >= sd.c[i] or entry - stop < p.min_risk_pts * p.es_pt:
        return None
    eq_hi = S._eq_levels(sd, i, p.eq_tol_pts * p.es_pt, lows=False, p=p)
    pools = sorted({S._exit_px(v, k, p) for v, k in S._targets(ctx, sd, i, entry, eq_hi, p, None, i) if k in S.POOL_KINDS and v > entry})
    fixed = []
    if pools:
        fixed.append((pools[0], "pool"))
    row = S._BD.row_for(ctx, "NEWS", i) or getattr(ctx, "bias_row", None) or {}
    dv = row.get("draw_up" if b > 0 else "draw_dn") if hasattr(row, "get") else None
    if dv is not None and dv == dv and sd.x(float(dv)) > entry:
        draw = S._exit_px(sd.x(float(dv)), "pool", p)
        if not fixed or draw > fixed[-1][0] + p.es_pt:
            fixed.append((draw, "pool"))
    if not fixed:
        return None
    sw = dict(session="NEWS", name="nfp_release_fvg", level=float(zt), key="nfp_release_fvg", ext=float(zb), ext_i=int(i), broke=int(i), sweep_i=int(i),
              smt=None, smt2=None, **{S._SM.SYNTH: True})
    tg = dict(unicorn=False, fvg_bottom=float(zb), fvg_ce=float((zt + zb) / 2), entry_kind="nfp_release_fvg", mitigation=False, propulsion=False,
              skip_po3=True, no_leg_wait=True, done_key="NFPR", cut=510 + p.nfp_release_fvg_min, lv_tags=["nfp_release_fvg"],
              fracs=(0.5, 0.5) if len(fixed) == 2 else (1.0,), be_at=float(fixed[0][0]))
    o = S._finish_order(ctx, sd, i, p, "NEWS", sw, entry, stop, risk_mult, float(entry), tg, skip_leg_pd=True, fixed=fixed)
    if o is None:
        return None
    hit("nfp_release_fvg")
    o["setup"] = "nfp_release_fvg"
    if p.nfp_release_fvg_add:
        o["rungs"] = list(o.get("rungs") or []) + [(float((zt + zb) / 2), max(p.lot, 1))]
    return o


def release_ob_order(ctx, sides, i: int, p, risk_mult: float):
    """N5-entry-at-release (b) (049 ~2:27): a 10:00 high-impact day with a known daily draw (the bias): when the close at 10:00 is inside an alive 5m OB of
    the bias side, a market entry at the 10:00 open (bar i + 1), the stop beyond the OB's far edge, one exit at the nearest short-term swing (a scalp,
    sb_mgmt 'fixed' semantics). 'Continue only if SMT / sick sister supports it' is NOT built (always the scalp)."""
    S = _S()
    b = bias_at(ctx, p, "AM", i)
    if not b:
        return None
    sd = _side_of(sides, b)
    ctx.cur_bias = b
    c = float(sd.c[i])
    zs = [z for z in sd.zones_tf(ctx.idx, ctx.tf, 5) if z.mt == z.mt and z.i <= i and z.bottom <= c <= z.top
          and sd.c[z.i + 1:i + 1].min(initial=np.inf) >= z.bottom]
    if not zs:
        return None
    z = max(zs, key=lambda z: z.i)
    t1 = [q.price for q in sd.ph if q.known <= i and q.price > c and q.i >= ctx.start]
    if not t1:
        return None
    entry, stop = c, float(z.bottom) - p.pad
    sw = dict(session="AM", name="release_ob", level=float(z.top), key="release_ob", ext=float(z.bottom), ext_i=int(i), broke=int(i), sweep_i=int(i),
              smt=None, smt2=None, **{S._SM.SYNTH: True})
    tg = dict(unicorn=False, fvg_bottom=float(z.bottom), fvg_ce=float((z.top + z.bottom) / 2), entry_kind="release_ob", mitigation=False,
              propulsion=False, skip_po3=True, no_leg_wait=True, market=True, single_exit=True, lv_tags=["release_ob"])
    o = S._finish_order(ctx, sd, i, p, "AM", sw, entry, stop, risk_mult, float(c), tg, skip_leg_pd=True, fixed=[(S._exit_px(min(t1), "pool", p), "pool")])
    if o is not None:
        hit("release_ob")
        o["setup"] = "release_ob"
    return o


def post_news_order(ctx, sides, i: int, p, risk_mult: float, sent: set):
    """N5-entry-at-release (a) (040 ~1:28, a drill): after the 08:30 release, the run-out leg of at least `post_news_run_pts` in the daily bias direction
    has printed (its extreme bar before bar i) and bar i is the first opposing candle after it: a limit at the body top of the order block (the last
    opposing candle before the run-out's extreme), stop under it, targets the SD projections of the run-out leg (L12, the first two sd_levels from the
    leg high). Once a day; [our interpretation] of 'first 1m OB retrace'."""
    S = _S()
    b = bias_at(ctx, p, "NEWS", i)
    if not b:
        return None
    sd = _side_of(sides, b)
    ctx.cur_bias = b
    kR = S._idx_at(ctx, 510)
    if kR >= i or ctx.t[kR] != 510:
        return None
    base = float(sd.o[kR])
    seg = sd.h[kR:i + 1]
    kh = kR + int(np.argmax(seg))
    run = float(sd.h[kh]) - base
    if run < p.post_news_run_pts * p.es_pt or kh >= i or not sd.c[i] < sd.o[i]:
        return None
    if (sd.c[kh + 1:i] < sd.o[kh + 1:i]).any():
        return None                                         # not the FIRST opposing candle after the run-out's extreme
    ob = [k for k in range(max(kR - 2, ctx.start), kh) if sd.c[k] < sd.o[k]]
    if not ob:
        return None
    k = ob[-1]
    entry, lo = float(sd.o[k]), float(sd.l[k])
    if entry >= sd.c[i]:
        return None
    stop = lo - p.pad
    hi_ = float(sd.h[kh])
    rng = hi_ - lo
    fixed = [(hi_ + kk * rng, "array") for kk in p.sd_levels[:2]]
    sent.add("pnc")
    sw = dict(session="NEWS", name="post_news", level=entry, key="post_news", ext=lo, ext_i=int(k), broke=int(kh), sweep_i=int(k), smt=None, smt2=None,
              **{S._SM.SYNTH: True})
    tg = dict(unicorn=False, fvg_bottom=lo, fvg_ce=float((entry + lo) / 2), entry_kind="post_news", mitigation=False, propulsion=False, skip_po3=True,
              no_leg_wait=True, done_key="PNC", lv_tags=["post_news_continuation"])
    o = S._finish_order(ctx, sd, i, p, "NEWS", sw, entry, stop, risk_mult, hi_, tg, skip_leg_pd=True, fixed=fixed)
    if o is not None:
        hit("post_news")
        o["setup"] = "post_news"
    return o


# --- N6: the news profile "pool_test" ----------------------------------------------------------------------------------------------------------

def news_move1(ctx, i: int):
    """(direction, high, low) of the first leg after the release driving the window (the latest complete range today), real prices; (0, None, None) when
    there is none. -1 when its low formed before its high."""
    S = _S()
    drv = getattr(ctx, "cur_news", None)
    if drv is None or drv.get("made") is None:
        ds = [d for d in getattr(ctx, "news_dr", {}).values() if d["made"] is not None and d["made"] <= i]
        drv = max(ds, key=lambda d: d["R"]) if ds else None
    if drv is None:
        return 0, None, None
    kR = S._idx_at(ctx, drv["R"])
    m = drv["made"]
    if m < kR:
        return 0, None, None
    ih = kR + int(np.argmax(ctx.h[kR:m + 1]))
    il = kR + int(np.argmin(ctx.l[kR:m + 1]))
    d = -1 if il < ih else (1 if ih < il else 0)
    return d, float(ctx.h[kR:m + 1].max()), float(ctx.l[kR:m + 1].min())


def pool_taken(ctx, p, i: int, session: str, d: int, hi: float, lo: float) -> bool:
    """Whether move 1 (direction d) traded through a marked pool on its side: the highs above (buy side) for d > 0, the lows below for d < 0 (the named
    pools of the day: _sell_side of the real-orientation Side), a tick through."""
    S = _S()
    sg = 1 if d < 0 else -1                                  # the Side whose SELL side holds the pools the leg ran: real lows (d < 0) / mirrored highs (d > 0)
    sm = getattr(ctx, "sides_map", None)
    s2 = sm[sg] if sm else S.Side(sg, ctx.o, ctx.h, ctx.l, ctx.c, p.pivot_n)
    ext_s = lo if d < 0 else -hi                             # the leg's extreme in that Side's space
    return any(S._thru(ext_s, v, S._tick(p)) for v in S._sell_side(ctx, s2, session, i, True, p).values())


def news_pool_gate(ctx, sd, sw, i: int, p, session: str, lvt: list):
    """N6-nfp-first-move-fake-if-liquidity (105 ~7:58), news_profile "pool_test": the first post-release move is the fake only if it ran a defined pool
    (then it is blocked as in 'require'). Otherwise the counter move is the Judas: orders in the counter-move direction are blocked until price has
    reached an HTF array (1h / 4h) of their side; the bias-direction entries at the array are the trade (targets: the pools move 1 left untaken). Returns
    a reject key or None."""
    d, hi, lo = news_move1(ctx, i)
    if not d:
        return None
    hit("news_pool_test")
    if pool_taken(ctx, p, i, session, d, hi, lo):
        if d == -sd.sign:
            lvt.append("news_profile")
            return None
        return "x_news_profile"
    lvt.append("news_pool_test")
    if sd.sign == -d:
        cf = getattr(ctx, "conf", None)
        at_arr = cf is not None and any(t_ in ("1h", "4h") for t_ in cf.at(now_ts(ctx, i), sd.x(sw["ext"]), sd.sign))
        if not at_arr:
            return "x_news_pool_counter"
    return None
