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
              "lc_reversal", "setup_model", "delivery", "div_type", "gap_count")


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


def bias_at(ctx, p, session: str, i: int, use_want: bool = True) -> int:
    """The HTF bias side known at closed bar i, for the setups that run outside the per-side loop: the loop's own reading when set, else
    the htf.table row KNOWN at that bar (bias_day.row_for: the 09:30 table from 09:30, the lock-time cut before it) read with the htf_bias
    column ("combo" when htf_bias is off), else the daily / 4h structure of the Confluence object when both agree [our interpretation]."""
    from . import bias_day as BD
    w = want(ctx) if use_want else 0
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


def smt_ref_ok(ctx, sd, i: int, key: str, level: float, p) -> bool:
    """B18-am-smt-window-points (086 ~5:42): the extreme the SMT compares (the swept level's low in side space; for an open point the open's own time) printed
    inside [smt_win_a, smt_win_b] (minutes of the day, inclusive). The time = the last bar before i whose low sits at the level within eq_tol_pts; a level
    with no such bar today (a prior day's pool) is outside. [our interpretation]"""
    S = _S()
    hit("smt_ref_window")
    if key in OPEN_KEYS:
        t = S.OPEN_MIN[OPEN_KEYS[key]]
        return p.smt_win_a <= t <= p.smt_win_b
    a = ctx.start
    if i <= a:
        return False
    near = np.flatnonzero(np.abs(sd.l[a:i] - level) <= p.eq_tol_pts * p.es_pt + 1e-9)
    if not len(near):
        return False
    return p.smt_win_a <= int(ctx.t[a + int(near[-1])]) <= p.smt_win_b


def created(ctx, key: str):
    """The bar from which the open pool exists (the bar AFTER the open's own bar: its low is always at or under its open), else None."""
    if key in OPEN_KEYS:
        S = _S()
        return S._idx_at(ctx, S.OPEN_MIN[OPEN_KEYS[key]]) + 1
    return None


# --- B12: wrong-side tolerance, the PO3 sequence, Judas depth ---------------------------------------------------------------------------

def judas_from(ctx, a: int, ref_px: float) -> int:
    """First bar the Judas scan may read: the bar AFTER the open's own bar when the reference open is that of bar `a` (midnight; the 13:30 open in the
    PM) - the open bar's low is below its own open almost every time, so counting it would make 'the open already traded through' trivially true.
    Other opens (08:30 / 09:30) keep the scan from `a` (the overnight trade beyond a later open is the Judas the source describes)."""
    S = _S()
    for nm, m in S.OPEN_MIN.items():
        v = ctx.opens.get(nm) if hasattr(ctx, "opens") else None
        if v is not None and abs(float(v) - float(ref_px)) < 1e-9 and S._idx_at(ctx, m) == a:
            return a + 1
    return a


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
    seg = sd.l[judas_from(ctx, a, ref_open_px):b]       # the Judas: the open traded through BEFORE the MSS bar (not the open bar itself)
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
    a = judas_from(ctx, a, r)                         # not the open bar itself (its low is below its own open almost always)
    below = np.flatnonzero(sd.l[a:end + 1] < x - 1e-9)
    if not len(below):
        return False
    j1 = a + int(below[0])
    stop_at = end + 1 if b is None else end          # the MSS bar itself does not count as the close back
    if not (sd.c[j1 + 1:stop_at] > x).any():
        return False
    return bool(entry <= x + p.po3_seq_below_pts * p.es_pt + 1e-9)


def judas_depth(ctx, sd, sw, i: int, p, session: str):
    """B12-judas-depth-adr (cc08_003 ~12:59, FX translated by ADR): (reference open - the Judas extreme) / ADR5 in side terms (0 when the extreme is not
    beyond the open). The Judas extreme = the session's lowest low (side space) after the open bar up to the MSS (bar i without one), or the sweep
    extreme when that is lower; None without an open or an ADR."""
    r = ref_open(ctx, p, session, i)
    a5 = adr5(ctx)
    if r is None or not a5:
        return None
    ext = sw["ext"]
    a = judas_from(ctx, sess_a(ctx, session), r)
    b = sw.get("broke")
    seg = sd.l[a:(i if b is None else b) + 1]
    if len(seg):
        ext = min(ext, float(seg.min()))
    return max(0.0, (sd.x(r) - ext) / a5)


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
    seg = ctx.l[k930 + 1:i + 1] if g > 0 else ctx.h[k930 + 1:i + 1]    # a bar AFTER the 09:30 bar (its own low is below its open almost always)
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


def compressed_first(ctx, sd, sw, i: int, p, entry: float, lv: list) -> list:
    """BH-compressed-higher-highs (028 ~1:26:02): after an MSS below a compressed run the leg low is the FIRST target - the targets nearer than it go
    (side space), the leg low joins as a pool."""
    v = compressed_leg_low(ctx, sd, sw, i, p)
    if v is None or v <= entry:
        return lv
    hit("compressed_first")
    return sorted(set([(x, k) for x, k in lv if x >= v - 1e-9] + [(v, "pool")]))


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
        sm = getattr(ctx, "sides_map", None)
        o = sm.get(-sd.sign) if sm else None
        if o is not None and o.sweep is None:
            hit("stoprun_rearm")
        arm_bias_side(ctx, sd, sw, i, session, float(o.x(sd.x(ref))) if o is not None else 0.0, sw["ext_i"])
        sw["sr_armed"] = True
    return True


def against_bias_break(ctx, sd, i: int, p, session: str, w: int) -> None:
    """A19-break-against-htf-stop-run in the main loop: the side AGAINST the bias is never scanned, so its break is looked for here. The first CLOSE of bar i
    beyond the latest confirmed swing of `sd` (side space: a close above its newest pivot high of today = a real break of a swing low for a short Side) while the
    bias flow is the other way is a stop run, not an MSS: with stoprun_rearm the bias Side's sweep is armed (`mss_htf_reject`, once per sweep; the run's extreme
    = the lowest low since that swing formed). [our interpretation of 'the break']"""
    ph = [q for q in sd.ph if q.known <= i - 1 and q.i >= ctx.start]
    if not ph or i <= ctx.start:
        return
    q = ph[-1]
    if not (sd.c[i] > q.price and sd.c[i - 1] <= q.price):
        return
    ctx.cur_bias = w
    sws = _c(ctx).setdefault("against_sw", {})
    sw = sws.setdefault((sd.sign, q.i), dict(session=session, ext_i=int(q.i), ext=float(sd.x(ctx.l[q.i])), broke=None))
    hit("against_break")
    mss_htf_reject(ctx, sd, sw, i, p, session, int(q.i), float(q.price))


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
        gs = [g for g in sd.gaps if sw["ext_i"] <= g.src <= b and g.i <= min(b + p.breaker_disp_bars, i)]
        # "price should not trade back into the rebalanced range" (001 ~45:39) [our interpretation]: a CLOSE back through the displacement FVG (below its bottom,
        # side space) undoes the repricing - that FVG no longer confirms (a retest of the breaker inside the gap's span is the entry itself, so only a full return counts)
        gs = [g for g in gs if not (sd.c[g.i + 1:i + 1] < g.bottom - 1e-9).any()]
        if not gs:
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
        if i <= e["born"] or not brk_alive(sd, e, i, p):
            continue
        if p.breaker_accumulate and not e.get("acc") and e["bottom"] <= sd.c[i] <= e["top"]:
            # A13-breaker-lifetime (015): entries may ACCUMULATE inside the breaker without a break and retest - once per breaker, a limit at the zone's CE
            # while price sits inside it [our interpretation of 'accumulate']
            e["acc"] = True
            hit("breaker_accumulate")
            bz = L.Zone("bull", (e["top"] + e["bottom"]) / 2, e["bottom"], i, e["src"], e["mt"])
            sw = dict(e["sw"], session=session)
            sw.pop("bz_sent", None)
            o = S._breaker_order(ctx, sd, sw, bz, i, p, session, risk_mult)
            if o is not None:
                return o
            continue
        if not sd.c[i] > e["top"]:
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


def breaker_dealing_range(sd, e: dict, i: int):
    """A21-pre-trigger-dealing-range (048 ~1:20:40): the dealing range of a remembered bullish breaker `e` once price TAPPED it (a low at or under its top after it
    formed): (low = the tap bar's low, high = the highest high between the breaker's birth and the tap = the swing high before the retrace [our interpretation of
    "the latest 3-candle swing high before the retrace"], tap bar), or None before the tap, when the tap bar or any later bar traded deeper than the breaker's
    bottom (invalid - time never invalidates), or without a range."""
    tap = next((j for j in range(e["born"] + 1, i + 1) if sd.l[j] <= e["top"]), None)
    if tap is None or sd.l[tap:i + 1].min() < e["bottom"] - 1e-9:
        return None
    hi = float(sd.h[e["born"]:tap].max(initial=-np.inf))
    lo = float(sd.l[tap])
    return (lo, hi, tap) if hi > lo + 1e-9 else None


def breaker_trigger_order(ctx, sd, i: int, p, session: str, risk_mult: float):
    """A21-pre-trigger-dealing-range, the explicit trigger (048 ~1:20:40: "I don't care how much time it spends inside"): inside the breaker's dealing range
    nothing is done however long it chops. The TRIGGER is an up-close candle whose body closes above a bearish FVG sitting in the upper half of the range while also
    closing above the internal highs (the swing highs formed since the tap) - the MSS. Then the first bullish FVG at / after the trigger bar gets a limit at its top
    (the 1m FVG of the spec; the 10:00-11:00 preference is not enforced), stop under the range low, once per breaker. Side space."""
    S = _S()
    ws = other_side(ctx, sd, p)
    for e in sorted(_c(ctx).get(("brk", sd.sign), []), key=lambda e: -e["born"]):
        if i <= e["born"] or e.get("trig_sent") or not brk_alive(sd, e, i, p):
            continue
        rng = breaker_dealing_range(sd, e, i)
        if rng is None:
            continue
        lo, hi, tap = rng
        mid = (lo + hi) / 2
        if e.get("trig") is None:
            ph = [q.price for q in sd.ph if tap < q.i and q.known <= i - 1 and q.price < hi]
            bears = [(-g.bottom, -g.top) for g in ws.gaps if e["born"] <= g.i <= i and -g.top >= mid]        # (top, bottom) in side space, upper half
            if (sd.c[i] > sd.o[i] and ph and sd.c[i] > max(ph) + 1e-9
                    and any(sd.c[i] > t_ for t_, b_ in bears)):
                e["trig"] = i
                hit("breaker_trigger")
        if e.get("trig") is None:
            continue
        if i - e["trig"] > max(3, p.pending_minutes // ctx.tf):
            e["trig_sent"] = True
            continue
        gs = [g for g in sd.gaps if e["trig"] <= g.i <= i and sd.c[g.i + 1:i + 1].min(initial=np.inf) >= g.bottom - 1e-9]
        if not gs:
            continue
        g = min(gs, key=lambda g: g.i)
        entry, stop = float(g.top), float(lo - p.pad)
        if entry - stop < p.min_risk_pts * p.es_pt or entry >= sd.c[i] + 1e-9:
            continue
        e["trig_sent"] = True
        hit("breaker_trigger_order")
        sw = _synth_sw(S, session, "breaker_range", hi, lo, tap, e["trig"])
        tags = dict(unicorn=False, fvg_bottom=float(g.bottom), fvg_ce=float(g.mid), entry_kind="breaker_range", mitigation=False, propulsion=False,
                    no_leg_wait=True, lv_tags=["breaker_range_trigger"])
        o = S._finish_order(ctx, sd, i, p, session, sw, entry, stop, risk_mult, hi, tags, skip_leg_pd=True)
        if o is not None:
            return o
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

def lc_array(ctx, sd, sw, i: int, p):
    """The highest HTF array (Confluence, FVG / OB of the order's side, p.daily_level_array_tfs) that holds the SWEEP EXTREME, known by the time the extreme
    printed: (top, bottom, tf) real prices, or None (also without a Confluence object)."""
    cf = getattr(ctx, "conf", None)
    if cf is None:
        return None
    from .confluence import TFS
    j = sw.get("ext_i", i)
    when = ctx.idx[j] + pd.Timedelta(minutes=ctx.tf)
    ext_r = sd.x(sw["ext"])
    tol = p.eq_tol_pts * p.es_pt
    best = None
    for top, bot, tf, src, known in cf.valid(when, sd.sign, tuple(p.daily_level_array_tfs), (0, 1), when):
        if min(top, bot) - tol <= ext_r <= max(top, bot) + tol and (best is None or TFS.index(tf) > TFS.index(best[2])):
            best = (round(float(top), 6), round(float(bot), 6), tf)
    return best


def morning_dir(ctx, i: int) -> int:
    """The 09:30-10:00 leg's direction (real): sign of (the close of the last bar before 10:00 - the 09:30 open); 0 when 10:00 is not yet in / no open."""
    S = _S()
    k1000 = S._idx_at(ctx, 600)
    o930 = S._open_known(ctx, "0930", i)
    if o930 is None or k1000 > i + 1 or k1000 - 1 < 0:
        return 0
    return int(np.sign(float(ctx.c[k1000 - 1]) - float(o930)))


def lc_reversal(ctx, sd, sw, i: int, p, cf, htf) -> bool:
    """T3-london-close-multiday-reversal (cc09_005 ~32:44): an entry armed in 10:00-12:00 against the morning's direction (the 09:30-10:00 leg; a long after
    a morning decline) whose sweep extreme (below the 09:30 open, side space) sat INSIDE an HTF array - a possible multi-day turn. The array is the Confluence
    array holding the sweep extreme (`lc_array`; recorded per extreme for the retry's 'same array'); without a Confluence object the order's own confluence list
    stands in."""
    S = _S()
    t = ctx.t[i]
    if not 600 <= t < 720:
        return False
    o930 = S._open_known(ctx, "0930", i)
    if o930 is None or not sw["ext"] < sd.x(o930) - 1e-9:
        return False
    md = morning_dir(ctx, i)
    if md and md == sd.sign:                           # the morning already went the order's way: not a reversal against it
        return False
    if getattr(ctx, "conf", None) is not None:
        arr = lc_array(ctx, sd, sw, i, p)
        if arr is None:
            return False
        _c(ctx).setdefault("lc_arr", {})[round(float(sd.x(sw["ext"])), 6)] = arr
        return True
    return bool(S._htf_array(cf, p) if cf is not None else htf)


def lc_reopen(ctx, tr, done: dict, key: str, state: dict) -> None:
    """T3 lc_reentry: after a stopped-out lc_reversal one more try (the one-trade-per-session flag is re-opened for this case only). The retry is bound to
    the slot (session + done key) and to the first trade's HTF array."""
    hit("lc_reopen")
    done[key] = False
    state["lc_done"] = True
    ext = float(tr.ext_px) if tr.ext_px is not None else None
    arr = None if ext is None else _c(ctx).get("lc_arr", {}).get(round(ext, 6))
    ctx.lc_retry = dict(side=1 if tr.side == "long" else -1, ext_px=ext, session=tr.session, key=key, arr=arr)


def lc_clear(ctx) -> None:
    """The retry slot was used (its trade closed): the gate is gone."""
    if getattr(ctx, "lc_retry", None):
        ctx.lc_retry = None


def lc_retry_gate(ctx, sd, sw, i: int, p, lc: bool, session: str = "AM", tags: dict | None = None):
    """While the re-opened slot is live, an order OF THAT SLOT (same session and done key) must be the retry: same direction, 10:00-12:00, a sweep BEYOND the
    first extreme inside the SAME HTF array. Orders of other sessions (the PM) are not touched."""
    ry = getattr(ctx, "lc_retry", None)
    if not ry:
        return None
    if session != ry.get("session", session) or (tags or {}).get("done_key", session) != ry.get("key", session):
        return None
    hit("lc_retry")
    if not (sd.sign == ry["side"] and lc and ry["ext_px"] is not None and sw["ext"] < sd.x(ry["ext_px"]) - 1e-9):
        return "x_lc_retry"
    if ry.get("arr") is not None and getattr(ctx, "conf", None) is not None and lc_array(ctx, sd, sw, i, p) != ry["arr"]:
        return "x_lc_retry"
    return None


def judas_news(ctx, sw, p) -> bool:
    """T13-judas-news-driver (cc01_002 ~15:16): the Judas sweep's extreme came within `judas_news_min` minutes of a scheduled release."""
    from . import newscal as NC
    hit("judas_news")
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


def opp_touched(cf, now, d: int, lo: float, hi: float, tfs=("4h", "D", "W")) -> bool:
    """Whether price has traded INTO an opposing array (real prices; for a leg in direction d the arrays of side -d on `tfs`) anywhere in the leg's range
    [lo, hi] - the swing origin to its extreme, not only at the extreme (DS2 two-session validity, cc10_013 ~5:10)."""
    if cf is None:
        return False
    for top, bot, *_ in cf.valid(now, -d, tfs, (0, 1), now):
        if min(top, bot) <= hi and max(top, bot) >= lo:
            return True
    return False


def _releases(ctx) -> list:
    from .calendar import release_times
    return release_times(ctx.day)


def _day_release(ctx) -> bool:
    """A scheduled release from 10:00 on (the consolidation profiles' precondition)."""
    return any(R >= 600 for R in _releases(ctx))


def pm_profile_gate(ctx, sd, sw, i: int, p, session: str, entry: float, lvt: list):
    """DS2-two-session-close-templates / DS2-consolidation-profiles (cc10_013 ~1:33-15:43): the PM templates, and the AM variants (`two_session_am`,
    `profile_consol_am`)."""
    if session == "AM":
        return am_profile_gate(ctx, sd, sw, i, p, entry, lvt)
    if session != "PM" or not (p.profile_two_session or p.profile_consol_pm):
        return None
    S = _S()
    k810 = S._idx_at(ctx, 810)
    if i < k810 or k810 >= len(ctx.t):
        return None
    d, ah, al = am_leg(ctx, k810)
    if d == 0:
        return None
    cf = getattr(ctx, "conf", None)
    now = now_ts(ctx, k810 - 1)
    ext_r = ah if d > 0 else al
    opp = lambda tfs: cf is not None and any(t_ in tfs for t_ in cf.at(now, ext_r, -d))
    bias = bias_at(ctx, p, session, i)
    if p.profile_two_session and bias == d and not opp_touched(cf, now, d, al, ah):
        hit("two_session")
        catalyst = p.two_session_catalyst and bool(_releases(ctx))       # a strong-catalyst day may trend straight through lunch: the PM trigger is not asked for
        if sd.sign != d:
            return "x_two_session_counter"
        lo, hi = float(sd.l[ctx.start:i + 1].min()), float(sd.h[ctx.start:i + 1].max())
        if not (catalyst or sw.get("key") == "lunch" or entry <= (lo + hi) / 2 + 1e-9):
            return "x_two_session_trigger"
        _c(ctx)["two_leg"] = (d, float(ah - al))
        lvt.append("two_session_up" if d > 0 else "two_session_down")
        if catalyst:
            lvt.append("two_session_catalyst")
        return None
    if p.profile_consol_pm and bias == 0 and not _day_release(ctx):
        hit("consol_pm")
        htf_arr = opp(("1h", "4h", "D", "W", "M"))
        if sd.sign != -d:
            return "x_consol_pm_side"
        need = "lunch" if htf_arr else "am_session"
        if str(sw.get("key", "")) != need:
            return "x_consol_pm_pool"
        lvt.append("consol_am_rally" if d > 0 else "consol_am_decline")
    return None


def am_profile_gate(ctx, sd, sw, i: int, p, entry: float, lvt: list):
    """DS2 AM variants. `two_session_am` (cc10_013 ~1:33, 'AM returns to a discount array, then rallies'): with the bias (`bias_at`) up and no opposing
    4h / D / W array traded into since the day's low, AM orders are bias-direction longs at a same-side HTF (1h+) array only (the mirror for a down bias);
    tag two_session_am_up / _down. `profile_consol_am` (~11:35-12:00; neutral bias, no release from 10:00): either direction, at an array of the order's side
    (return to a discount / premium array) or - once the opening range has formed - on the expansion side of its equilibrium; London's opposite extreme
    and the day's far extreme are extra targets (`pm_extra_targets`); tag consol_am_up / _down. [our interpretation of 'return to an array']"""
    if not (p.two_session_am or p.profile_consol_am):
        return None
    cf = getattr(ctx, "conf", None)
    now = now_ts(ctx, i)
    ent_r = sd.x(entry)
    bias = bias_at(ctx, p, "AM", i)
    at_arr = cf is not None and any(t_ in ("1h", "4h", "D", "W") for t_ in cf.at(now, ent_r, sd.sign))
    if p.two_session_am and bias:
        lo, hi = float(ctx.l[ctx.start:i + 1].min()), float(ctx.h[ctx.start:i + 1].max())
        if not opp_touched(cf, now, bias, lo, hi):
            hit("two_session_am")
            if sd.sign != bias:
                return "x_two_session_am_counter"
            if not at_arr:
                return "x_two_session_am_array"
            lvt.append("two_session_am_up" if bias > 0 else "two_session_am_down")
            return None
    if p.profile_consol_am and bias == 0 and not _day_release(ctx):
        hit("consol_am")
        ok = at_arr
        if not ok and ctx.or_hl is not None and ctx.t[i] >= ctx.or_end:
            eq = sd.x((ctx.or_hl[0] + ctx.or_hl[1]) / 2)
            ok = entry >= eq - p.eq_tol_pts * p.es_pt
        if not ok:
            return "x_consol_am"
        lvt.append("consol_am_up" if sd.sign > 0 else "consol_am_down")
    return None


def pm_extra_targets(ctx, sd, i: int, p, session: str, entry: float) -> list:
    """DS2-consolidation-profiles: after the PM sweep + MSS the counter side targets the day's / London's opposite pools (side space, > entry); the AM
    consolidation variant (`profile_consol_am`) the same; DS2-two-session: the measured move (the PM leg ~= the AM leg, from the entry)."""
    out = []
    tl = _c(ctx).get("two_leg")
    if session == "PM" and p.profile_two_session and tl and tl[0] == sd.sign and tl[1] > 0:
        out.append((entry + tl[1], "array"))
    if not ((session == "PM" and p.profile_consol_pm) or (session == "AM" and p.profile_consol_am and bias_at(ctx, p, session, i) == 0)):
        return out
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
        hit("smt_no_bias")
        return "x_smt_no_bias"                             # B18: no clear daily IOF - the SMT is not traded
    if sw.get("smt_laggard"):
        lvt.append("smt_laggard")
    if p.touch_tag and sw.get("key") and "level" in sw and not sw.get(S._SM.SYNTH):
        try:
            tags["touch_n"] = touch_count(ctx, sd, sw, i, p, session)
        except Exception:                                  # a synthetic sweep without a level history
            pass
    if p.judas_max_adr or p.judas_depth_tag:
        jd = judas_depth(ctx, sd, sw, i, p, session)
        if jd is not None:
            tags["judas_depth"] = round(float(jd), 4)
            hit("judas_depth")
            if p.judas_max_adr and jd > p.judas_max_adr + 1e-12:
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
        r = lc_retry_gate(ctx, sd, sw, i, p, lc, session, tags)
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
    out += news_pool_targets(ctx, sd, i, p, session, entry)
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

def _SM3():
    from . import sm3
    return sm3


def mit_order(ctx, sd, i: int, p, session: str, risk_mult: float):
    """A15-mitigation-block-entry (033 ~1:04:05; cc04_004 ~4:37, ~13:51) and X3-a15-mitblock-bear-context (cc04_004 ~6:44): with the order flow and
    narrative our way (the bias side), a resting limit in the day's alive mitigation block (the full range of the last down-close candle at the failed
    low for a short; side space: a bull zone below price) - at its near edge ("near") or CE ("mid") - stop beyond the block; once per retest, no
    expiry. Ranks below breakers (only tried when the sweep flow produced nothing). mit_needs_bias: the bias must be its way AND an untaken daily
    pool / array lies beyond - its level is the target. `mit_preopen` adds the 041 pre-open consolidation block (`preopen_block`). NOT built: the cc06_005 4h-premium block (the 4h arrays carry no mitigation source and the day holds three 4h bars)."""
    S = _S()
    if want(ctx) != sd.sign:
        return None
    sent = sd.__dict__.setdefault("_mit_sent", {})
    zs, pre = list(sd.mitigations()), set()
    pz = preopen_block(ctx, sd, i, p) if p.mit_preopen else None
    if pz is not None:
        zs.append(pz)
        pre.add((pz.i, pz.src))
    for z in sorted(zs, key=lambda z: -z.i):
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
        mtags = {}
        if p.mb_targets:                                # caption-gap A15-mitigation-block-targets (cc04_004 ~8:13): the post-break extreme (just beyond), then the nearest HTF level as the final rung
            C = float(sd.h[z.i:i + 1].max())
            r1 = S._exit_px(C, "pool", p)
            if r1 > entry:
                fixed = [(r1, "pool")]
                nxt = _SM3().htf_level_beyond(ctx, sd, i, p, entry, session, r1)
                if nxt is not None:
                    fixed.append((S._exit_px(nxt, "array", p), "array"))
                    if p.mb_done_at_htf:
                        mtags["sm3"] = {"mb_done": True}
                hit("mb_targets")
        if p.mb_body_exit:                              # caption-gap A15-mitigation-block-body-hold (cc04_004 ~14:29) [our interpretation]: a body close beyond the candle's body before T1 exits
            mtags["lvx"] = {"mb_body": (float(min(sd.o[z.src], sd.c[z.src])), True)}
            hit("mb_body_exit")
        sent[(z.i, z.src)] = i
        hit("mit_order")
        sw = dict(session=session, name="mitigation", level=float(z.top), key="mitigation", ext=float(z.bottom), ext_i=int(z.src), broke=int(z.i),
                  sweep_i=int(z.src), smt=None, smt2=None, **{S._SM.SYNTH: True})
        tags = dict(unicorn=False, fvg_bottom=float(z.bottom), fvg_ce=float((z.top + z.bottom) / 2), entry_kind="mitigation_entry", mitigation=True,
                    propulsion=False, no_leg_wait=True, lv_tags=["mitigation_entry"] + (["mit_preopen"] if (z.i, z.src) in pre else []))
        tags.update(mtags)
        return S._finish_order(ctx, sd, i, p, session, sw, entry, stop, risk_mult, float(sd.h[z.src:i + 1].max()), tags, skip_leg_pd=True, fixed=fixed)
    return None


def preopen_block(ctx, sd, i: int, p):
    """A15-mitigation-block-entry, 041 ~0:00 (side space): the up-close candles of the 09:00-09:30 pre-open consolidation as ONE bullish mitigation block
    (their full range: lowest low .. highest high), known from 09:30; the consolidation = the window's range of at most 0.25 x ADR5 [our interpretation of
    the 041 window and of 'consolidation']. A Zone with kind bull, i = the last window bar, src = the first up-close candle, mt = the last one's body mean."""
    S = _S()
    k0, k1 = S._idx_at(ctx, 540), S._idx_at(ctx, 570)
    if k1 > i + 1 or k1 - k0 < 2 or k0 < ctx.start:
        return None
    c = _c(ctx)
    key = ("preopen", sd.sign)
    if key not in c:
        o, h, l, cl = sd.o[k0:k1], sd.h[k0:k1], sd.l[k0:k1], sd.c[k0:k1]
        a5 = adr5(ctx)
        up = np.flatnonzero(cl > o)
        z = None
        if len(up) and a5 and float(h.max() - l.min()) <= 0.25 * a5:
            u = up + k0
            z = L.Zone("bull", float(sd.h[u].max()), float(sd.l[u].min()), k1 - 1, int(u[0]), float((sd.o[u[-1]] + sd.c[u[-1]]) / 2))
            hit("mit_preopen")
        c[key] = z
    return c[key]


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
    day_hi = float(sd.h[ctx.start:i + 1].max())
    cands = [v for v in cands if v > entry and v > day_hi + 1e-9]          # untapped today: a level the day already traded is not a draw
    return min(cands) if cands else None


# --- release setups (N1 / N5) ----------------------------------------------------------------------------------------------------------------

def release_setups(ctx, sides, i: int, p, state: dict, pos, pending, risk_mult: float, done: dict | None = None):
    """The three setups that fire around a scheduled release and bypass the news windows (nfp_floor_min / news_wait / nfp_first_hour) for themselves
    only: N1-nfp-release-4h-fvg, N5-entry-at-release (a) post_news_continuation, (b) release_ob_entry. Returns an order or None; each fires at most once a
    day (state["sm2_sent"]). Armed on the bar that has just closed."""
    if pos is not None or pending is not None:
        return None
    if state.get("day_done"):                              # a day stop (daily loss / target / the day's trade ended it) ends these setups too
        return None
    done = done or {}
    S = _S()
    sent = state.setdefault("sm2_sent", set())
    t = int(ctx.t[i])
    end = t + ctx.tf
    from claude_hf.daytypes import events
    from . import newscal as NC
    tags = events(ctx.day)
    rel = NC.releases(ctx.day, p)
    saved = {k: ctx.__dict__[k] for k in ("cur_lock", "cur_lock_any", "cur_bias", "cur_news", "cur_sloppy", "cur_no_draw") if k in ctx.__dict__}
    out = None
    try:
        ctx.cur_lock, ctx.cur_lock_any, ctx.cur_news, ctx.cur_sloppy, ctx.cur_no_draw, ctx.cur_bias = None, None, None, "", False, 0
        if p.nfp_release_fvg and "nfp" not in sent and "jobs" in tags and end == 510 and not done.get("NFPR"):
            sent.add("nfp")
            out = nfp_release_order(ctx, sides, i, p, risk_mult)
        if out is None and p.release_ob_entry and "relob" not in sent and 600 in rel and end == 600 and not done.get("AM"):
            sent.add("relob")
            out = release_ob_order(ctx, sides, i, p, risk_mult)
        if out is None and p.post_news_continuation and "pnc" not in sent and 510 in rel and 515 <= end <= 570 and not done.get("PNC"):
            out = post_news_order(ctx, sides, i, p, risk_mult, sent)
    finally:
        for k in ("cur_lock", "cur_lock_any", "cur_bias", "cur_news", "cur_sloppy", "cur_no_draw"):
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
    sb_mgmt 'fixed' semantics); 'continue only if SMT / the sick sister supports it' (`release_support`): then a second exit at the table's draw and the
    lv_tag release_ob_continue, else the scalp."""
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
    cont = release_support(ctx, sd, i, p, entry)
    sw = dict(session="AM", name="release_ob", level=float(z.top), key="release_ob", ext=float(z.bottom), ext_i=int(i), broke=int(i), sweep_i=int(i),
              smt=None, smt2=None, **{S._SM.SYNTH: True})
    tg = dict(unicorn=False, fvg_bottom=float(z.bottom), fvg_ce=float((z.top + z.bottom) / 2), entry_kind="release_ob", mitigation=False,
              propulsion=False, skip_po3=True, no_leg_wait=True, market=True, lv_tags=["release_ob"])
    fixed = [(S._exit_px(min(t1), "pool", p), "pool")]
    if cont:                                                # SMT / the sick sister supports it: continue to the draw after the scalp's first exit
        row = S._BD.row_for(ctx, "AM", i) or getattr(ctx, "bias_row", None) or {}
        dv = row.get("draw_up" if b > 0 else "draw_dn") if hasattr(row, "get") else None
        if dv is not None and dv == dv and sd.x(float(dv)) > fixed[0][0] + p.es_pt:
            fixed.append((S._exit_px(sd.x(float(dv)), "pool", p), "pool"))
            tg["fracs"] = (0.5, 0.5)
            tg["lv_tags"] = ["release_ob", "release_ob_continue"]
    if len(fixed) == 1:
        tg["single_exit"] = True                            # the scalp: one exit at the nearest short-term swing
    o = S._finish_order(ctx, sd, i, p, "AM", sw, entry, stop, risk_mult, float(c), tg, skip_leg_pd=True, fixed=fixed)
    if o is not None:
        hit("release_ob")
        o["setup"] = "release_ob"
    return o


def release_support(ctx, sd, i: int, p, entry: float) -> bool:
    """N5-entry-at-release (b) (049 ~2:27): 'continue only if SMT or the sick sister supports it'. Supported when (a) this index is the sick sister
    (`setups.sick_sister`: fewer reference highs / lows traded than the sister, in the discount) or (b) the index took a pool today (a tick through) and
    the partner did NOT (an SMT, `strategy._smt`), both read at the 10:00 close."""
    S = _S()
    if S._SM.sick_sister(ctx, sd, i, p, "AM", entry) is not None:
        hit("release_sick")
        return True
    ps = getattr(ctx, "pside", None)
    if not ps or ps[0] is None:
        return False
    pctx, psides, ppos = ps
    tk = S._tick(p)
    low = float(sd.l[ctx.start:i + 1].min())
    for k, v in S._sell_side(ctx, sd, "AM", i, p.extra_pools, p).items():
        if S._thru(low, v, tk) and S._smt(ctx, sd, i, k, v, "AM", pctx, psides, ppos, p) is True:
            hit("release_smt")
            return True
    return False


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
    rng = hi_ - base                                        # the run-out leg (the 08:30 open to its extreme), not the OB: the SD projections of the leg
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
    w = want(ctx)
    if w != sd.sign:                                         # the trade is the BIAS-direction entry at the array (N6 spec: no bias / the other way = no trade)
        return "x_news_pool_bias"
    if sd.sign == -d:
        cf = getattr(ctx, "conf", None)
        at_arr = cf is not None and any(t_ in ("1h", "4h") for t_ in cf.at(now_ts(ctx, i), sd.x(sw["ext"]), sd.sign))
        if not at_arr:
            return "x_news_pool_counter"
    return None


# --- D15 laggard_objective: the instrument's OWN draw met, at engine level -------------------------------------------------------------------

def objective_record(ctx, p, symbol: str):
    """BH-D15-sick-sister-laggard (056 ~9:10; 070 ~18:41; 099 ~26:53): this instrument's objective = the draw of its OWN htf.table row (the 09:30 table:
    draw_up for a bullish bias column, draw_dn for a bearish one; the bias column is the htf_bias one, "combo" when htf_bias is off). It is MET when the
    day's bars from 09:30 (the row is known from then; [our interpretation] of 'since formed') traded through the draw level (high >= draw / low <= draw);
    the moment is the END of that bar. Returns dict(date, symbol, side, draw, t) (t None = not met) or None without a row / bias / draw."""
    from . import bias_day as BD
    S = _S()
    row = getattr(ctx, "bias_row", None)
    if row is None or not hasattr(row, "get"):
        return None
    col = BD.bias_col(p) if p.htf_bias != "off" else "combo"
    try:
        v = row.get(col)
        side = 0 if v is None or v != v else int(v)
    except Exception:
        side = 0
    if not side:
        return None
    dv = row.get("draw_up" if side > 0 else "draw_dn")
    if dv is None or dv != dv:
        return None
    draw = float(dv)
    k0 = S._idx_at(ctx, 570)
    seg = (ctx.h[k0:] >= draw - 1e-9) if side > 0 else (ctx.l[k0:] <= draw + 1e-9)
    hit_ = np.flatnonzero(seg)
    t = None if not len(hit_) else ctx.idx[k0 + int(hit_[0])] + pd.Timedelta(minutes=ctx.tf)
    return dict(date=ctx.day, symbol=symbol, side=side, draw=draw, t=t)


def objective_stamp(ctx, p, symbol: str, trades: list, out: list | None) -> None:
    """Stamp `Trade.obj_met_t` on the day's trades and (for the days without a trade) append the record to `out` (run_day's `objective` list) - only
    with smt_pick "laggard_objective"; everything else is untouched. `combine` compares a later FILL with t: only a past moment is ever read."""
    if p.smt_pick != "laggard_objective":
        return
    rec = objective_record(ctx, p, symbol)
    hit("objective_met")
    if rec is None:
        return
    for tr in trades:
        tr.obj_met_t = rec["t"]
    if out is not None:
        out.append(rec)


def news_pool_targets(ctx, sd, i: int, p, session: str, entry: float) -> list:
    """N6 pool_test: when move 1 took no pool, the pools it left UNTAKEN on its own side (the buy-side pools above a rally that took none; the mirror)
    are the targets of the bias-direction entry (side space, above the entry). Empty when move 1 took a pool / the order is not in move 1's direction."""
    if p.news_profile != "pool_test":
        return []
    d, hi, lo = news_move1(ctx, i)
    if not d or d != sd.sign or pool_taken(ctx, p, i, session, d, hi, lo):
        return []
    S = _S()
    sg = 1 if d < 0 else -1
    sm = getattr(ctx, "sides_map", None)
    s2 = sm[sg] if sm else S.Side(sg, ctx.o, ctx.h, ctx.l, ctx.c, p.pivot_n)
    ext_s = lo if d < 0 else -hi
    out = []
    for v in S._sell_side(ctx, s2, session, i, True, p).values():
        if v < ext_s:                                      # left untaken (in that Side's space the pools sit below the leg's extreme)
            tgt = sd.x(s2.x(float(v)))
            if tgt > entry:
                out.append((tgt, "pool"))
    if out:
        hit("news_pool_targets")
    return sorted(set(out))


# =====================================================================================================================================================
# caption-gap pass, setups_models #2/7 (chunk 2 of 7): digests/rulebook_gaps/definitions_pd_arrays_structure.md items 48-202, levels_liquidity_targets.md
# items 6-36. Same conventions as above. The switches are named in strategy.Params ("caption-gap pass, setups_models #2/7").
# =====================================================================================================================================================

def _tk(p) -> float:
    return _S()._tick(p)


def _real_disp(ctx, j: int, mult: float = 1.5) -> bool:
    """A displacement bar at j (real prices): body >= mult x the mean body of the 10 bars before (bars up to j only)."""
    if j < 1:
        return False
    body = abs(ctx.c[j] - ctx.o[j])
    prev = np.abs(ctx.c[max(0, j - 10):j] - ctx.o[max(0, j - 10):j])
    return bool(len(prev) and body >= mult * float(prev.mean()) > 0)


# --- A2-delivery-vs-liquidity / new-price-engine-models: tags that are always on ---------------------------------------------------------------------

def delivery_dir(ctx, sd, i: int) -> str:
    """A2-delivery-vs-liquidity (104 ~11:24: "buy side delivery is the actual animated movement of price"): "up" / "down" = the real direction of the last
    displacement bar within the 20 bars up to i ("" without one). Buy-side delivery = a leg moving higher; BSL / SSL are the static stop pools."""
    for j in range(i, max(ctx.start, i - 19) - 1, -1):
        if _real_disp(ctx, j):
            return "up" if ctx.c[j] > ctx.o[j] else "down"
    return ""


def setup_model(sd, sw) -> str:
    """new-price-engine-models (cc09_006 ~0:54; cc09_007 ~1:27, ~2:23): OA / OD for a sweep-driven order (a raid of an old low (high), then a long (short) to a
    short-term array), RA / RD for a retrace into an array without a sweep of its own (the synthetic setups: breaker retests, mitigation, IFVG returns ...)."""
    synth = bool(sw.get(_S()._SM.SYNTH)) or sw.get("key") in ("mitigation", "ir", "pm_reversal")
    return ("R" if synth else "O") + ("A" if sd.sign > 0 else "D")


# --- A5-premium-half-daily-fvg ------------------------------------------------------------------------------------------------------------------------

def dfvg_gate(ctx, sd, sw, i: int, p, lvt: list):
    """A5-premium-half-daily-fvg (012 ~18:02: "I want to see the majority of the reactions in the upper portion"): the sweep extreme lies inside a large unfilled
    daily BISI (SIBI for shorts; height >= dfvg_large_pts): a continuation long needs the extreme at / above its CE (side space, 1 tick); and no 15m / 1h body
    may have closed below the CE today. A breach is tagged dfvg_lower_half ("tag") or rejects the order ("skip"). Real daily arrays from the Confluence object."""
    cf = getattr(ctx, "conf", None)
    if cf is None:
        return None
    tk = _tk(p)
    ext = float(sw["ext"])
    for top, bot, tf, src, known in cf.valid(now_ts(ctx, i), sd.sign, ("D",), (0,)):
        if top - bot < p.dfvg_large_pts * p.es_pt - 1e-9:
            continue
        zt, zb = max(sd.x(top), sd.x(bot)), min(sd.x(top), sd.x(bot))
        if not (zb - tk <= ext <= zt + tk):
            continue
        hit("dfvg_half")
        ce = (zt + zb) / 2
        bad = ext < ce - tk - 1e-9
        if not bad:
            for m in (15, 60):
                o, h, l, c, last, first = bars_tf(ctx, sd, m, i)
                if any(last[k] >= ctx.start and c[k] < ce - 1e-9 for k in range(len(c))):
                    bad = True
                    break
        if bad:
            lvt.append("dfvg_lower_half")
            if p.dfvg_half == "skip":
                return "x_dfvg_lower_half"
        return None
    return None


# --- L5 / L6 / L7: gap setups --------------------------------------------------------------------------------------------------------------------------

def gap_list(ctx, i: int, kinds=("nwog", "nwog_rth")) -> list:
    """The stored gaps known at closed bar i as (hi, lo, ce) real prices: the ICT gap table (ctx.gaps) when the engine has it (rows of the given kinds), else the
    NWOGs of the day context (a Monday's own NWOG only from 09:30: strategy._nwogs)."""
    S = _S()
    if getattr(ctx, "gaps", None) is not None:
        return [(float(hi), float(lo), float(ce)) for kind, hi, lo, ce in ctx.gaps if kind in kinds]
    return [(max(a, b), min(a, b), (a + b) / 2) for a, b in S._nwogs(ctx, i)]


def _synth_sw(S, session: str, name: str, level: float, ext: float, ext_i: int, broke: int | None = None) -> dict:
    return dict(session=session, name=name, level=float(level), key=name, ext=float(ext), ext_i=int(ext_i), broke=broke, sweep_i=int(ext_i),
                smt=None, smt2=None, **{S._SM.SYNTH: True})


def nwog_sr_order(ctx, sd, i: int, p, session: str, risk_mult: float):
    """L5-nwog-sr-levels (039 ~10:52-12:06; 024 ~18:37): in a CONSOLIDATION NWOG week (the htf.table `nwog_regime` column = "cons", B14.1) the stored NWOG high /
    CE / low are exact support / resistance: with the bias this way a limit at the nearest stored level below the market (side space), stop nwog_sr_stop_pts beyond
    it, first target the next stored level above; once per level. A trending week gives no order. Tag nwog_sr."""
    from . import bias_day as BD
    S = _S()
    if want(ctx) != sd.sign:
        return None
    row = BD.row_for(ctx, session, i)
    if not row or (row.get("nwog_regime") or "") != "cons":
        return None
    lv = sorted({round(float(sd.x(v)), 6) for hi, lo, ce in gap_list(ctx, i) for v in (hi, lo, ce)})
    below = [v for v in lv if v < sd.c[i] - 1e-9]
    if not below:
        return None
    entry = max(below)
    sent = sd.__dict__.setdefault("_nwog_sr", set())
    if (session, entry) in sent:
        return None
    sent.add((session, entry))
    hit("nwog_sr")
    above = [v for v in lv if v > entry + 1e-9]
    fixed = [(S._exit_px(above[0], "array", p), "array")] if above else None
    stop = entry - p.nwog_sr_stop_pts * p.es_pt
    sw = _synth_sw(S, session, "nwog_sr", entry, entry, i, i)
    tags = dict(unicorn=False, fvg_bottom=stop, fvg_ce=entry, entry_kind="nwog_sr", mitigation=False, propulsion=False, no_leg_wait=True, lv_tags=["nwog_sr"])
    return S._finish_order(ctx, sd, i, p, session, sw, entry, stop, risk_mult, float(sd.h[max(ctx.start, i - 3):i + 1].max()), tags, skip_leg_pd=True, fixed=fixed)


def gap_edge_order(ctx, sd, i: int, p, session: str, risk_mult: float):
    """L6-ndog-nwog-primary-entry (050 ~54:42, ~51:00): with the daily bias this way the FIRST return of price to the near edge of an active NWOG / NDOG is an
    entry on its own (no FVG / OB needed; contradicts 052 "confluence only" and 051 "never standalone" - hence a switch): a short at the gap's lower edge with the
    bias down (side space: a long at the gap's upper edge), stop = the gap's far edge + pad, targets the ordinary pools. Once per gap and session; tag gap_edge."""
    S = _S()
    if want(ctx) != sd.sign:
        return None
    a0 = sess_a(ctx, session)
    sent = sd.__dict__.setdefault("_gap_edge", set())
    for hi, lo, ce in gap_list(ctx, i, ("nwog", "nwog_rth", "ndog")):
        zt, zb = max(sd.x(hi), sd.x(lo)), min(sd.x(hi), sd.x(lo))
        key = (session, round(zt, 6), round(zb, 6))
        if key in sent or not sd.c[i] > zt or sd.l[a0:i + 1].min() <= zt:
            continue                                      # inside / below the gap, or the gap was already entered this session (not a first return)
        sent.add(key)
        hit("gap_edge")
        entry, stop = zt, zb - p.pad
        sw = _synth_sw(S, session, "gap_edge", zt, zb, i, i)
        tags = dict(unicorn=False, fvg_bottom=zb, fvg_ce=(zt + zb) / 2, entry_kind="gap_edge", mitigation=False, propulsion=False, no_leg_wait=True,
                    lv_tags=["gap_edge"])
        o = S._finish_order(ctx, sd, i, p, session, sw, entry, stop, risk_mult, float(sd.h[max(ctx.start, i - 3):i + 1].max()), tags, skip_leg_pd=True)
        if o is not None:
            return o
    return None


def gap_quarter_order(ctx, sd, i: int, p, session: str, risk_mult: float):
    """L5-quarter-level-no-imbalance (030 ~1:23:49: "was there any imbalance in here no so what level are we looking at"): after a CLOSE beyond an NWOG edge, if the
    retrace leg (the break extreme to bar i) holds no FVG / VI, the retrace level is the NEAR QUARTER ((CE + edge) / 2): a limit there, stop beyond the CE
    + 1 tick; no order once price has traded back to the gap's far edge. Side space: a close above the gap top (coming from inside / below it), the retrace falls
    toward it. Once per gap and day; tag gap_quarter. Targets: the ordinary pools / wick CEs."""
    S = _S()
    tk = _tk(p)
    a = ctx.start
    for hi, lo, ce in gap_list(ctx, i):
        zt, zb = max(sd.x(hi), sd.x(lo)), min(sd.x(hi), sd.x(lo))
        ce_s = (zt + zb) / 2
        key = (round(zt, 6), round(zb, 6))
        sent = sd.__dict__.setdefault("_gap_q", set())
        if key in sent or a < 1:
            continue
        cross = np.flatnonzero((sd.c[a:i + 1] > zt) & (sd.c[a - 1:i] <= zt))
        if not len(cross):
            continue
        j = a + int(cross[0])                             # the first close beyond the edge, coming from inside / below the gap
        e = j + int(np.argmax(sd.h[j:i + 1]))             # the break extreme
        if e >= i or sd.l[e:i + 1].min() <= zb:
            continue                                      # no retrace yet / the far edge traded: the read is dead
        quarter = (ce_s + zt) / 2
        if not sd.c[i] > quarter + 1e-9:
            continue
        has_imb = any(e <= g.i <= i and g.i - 2 >= e for g in list(sd.gaps) + list(sd.opposing())) \
            or any(e <= z.i <= i for z in list(sd.vis("bull")) + list(sd.vis("bear")))
        if has_imb:
            continue
        entry, stop = quarter, ce_s - tk
        if entry - stop < p.min_risk_pts * p.es_pt:
            continue
        sent.add(key)
        hit("gap_quarter")
        sw = _synth_sw(S, session, "gap_quarter", zt, zb, e, j)
        tags = dict(unicorn=False, fvg_bottom=stop, fvg_ce=ce_s, entry_kind="gap_quarter", mitigation=False, propulsion=False, no_leg_wait=True,
                    lv_tags=["gap_quarter"])
        o = S._finish_order(ctx, sd, i, p, session, sw, entry, stop, risk_mult, float(sd.h[e]), tags, skip_leg_pd=True)
        if o is not None:
            return o
    return None


def org_state(ctx, i: int, p):
    """L7-gap-up-premium-template (042 ~11:31): (gap direction +1 / -1, open, prior close, step) of a SIGNIFICANT opening-range gap at closed bar i, or None.
    Significant = |open - prior RTH close| >= org_sig_adr x ADR5, with the open in the premium (gap up) / discount (gap down) of the 20-day range
    [our interpretation]. step: 0 before the first rally beyond the open, 1 after it, 2 after the dip back to the open (within 1 pt), 3 after the second rally
    beyond the first extreme (only then may the fade be taken). Real prices; bars up to i only."""
    S = _S()
    if not getattr(ctx, "org", None) or not getattr(ctx, "org_today", False):
        return None
    k0 = S._idx_at(ctx, 570)
    if k0 >= len(ctx.t) or i < k0:
        return None
    pc, op = ctx.org[-1]
    a5 = adr5(ctx)
    if not a5 or abs(op - pc) < p.org_sig_adr * a5:
        return None
    d = 1 if op > pc else -1
    hist = getattr(ctx, "hist", [])[-20:]
    if not hist:
        return None
    eq = (max(float(x.high.max()) for x in hist) + min(float(x.low.min()) for x in hist)) / 2
    if (d > 0 and op <= eq) or (d < 0 and op >= eq):
        return None
    hi_s, lo_s, op_s = (ctx.h, ctx.l, op) if d > 0 else (-ctx.l, -ctx.h, -op)     # the gap direction made "up"
    near = 1.0 * p.es_pt
    h1, step = None, 0
    for j in range(k0, i + 1):
        if step == 0:
            if hi_s[j] > op_s + near:
                step, h1 = 1, float(hi_s[j])
        elif step == 1:
            h1 = max(h1, float(hi_s[j]))                  # (the dip bar's own high counts toward the first extreme)
            if lo_s[j] <= op_s + near:
                step = 2
        elif step == 2 and hi_s[j] > h1:
            step = 3
            break
    return d, float(op), float(pc), step


def org_two_rally_gate(ctx, sd, i: int, p):
    """L7-gap-up-premium-template: after a significant gap up into premium (down into discount) a SHORT (long) waits for the two-rally template - no fade before
    step 3 (a second rally above the first high after the dip to the 09:30 open). Returns a reject key or None."""
    st = org_state(ctx, i, p)
    if st is None:
        return None
    d, op, pc, step = st
    if sd.sign != -d:
        return None
    hit("org_two_rally")
    return None if step >= 3 else "x_org_two_rally"


def org_two_rally_targets(ctx, sd, i: int, p, entry: float) -> list:
    """L7-gap-up-premium-template: the fade's first target is the 09:30 open -/+ 5 pts ("about a 5-handle run into the ORG"), then the prior close (optional)."""
    st = org_state(ctx, i, p)
    if st is None:
        return []
    d, op, pc, step = st
    if sd.sign != -d or step < 3:
        return []
    out = [(sd.x(op - d * 5.0 * p.es_pt), "array"), (sd.x(pc), "pool")]
    return [(float(v), k) for v, k in out if v > entry]


# --- A18: reclaimed order blocks ---------------------------------------------------------------------------------------------------------------------

def reclaimed_zones(sd, a: int, e: int, i: int, p) -> list:
    """A18-reclaimed-ob-codeable: the reclaimed OBs known by bar i under `reclaimed_def` ("strict" = cc04_007: the curve's candles, reclaimed after the low e;
    "loose" = 006: a block price left, re-traded and left again). A18-traded-through-ok (cc04_007 ~9:45: "it trades through it but we see a climax high"): neither
    definition drops a candidate that price traded or closed through before the curve extreme - the A12 MT invalidation does not apply (already so in
    levels.reclaimed_obs: nothing there reads the closes before e)."""
    if p.reclaimed_def == "loose":
        hit("reclaimed_loose")
        return [z for z in L.reclaimed_obs_loose(sd.o, sd.h, sd.l, sd.c, a, i) if z.i <= i]
    return [z for z in L.reclaimed_obs(sd.o, sd.h, sd.l, sd.c, a, e, i) if z.i <= i]


# --- A19: MSS reference rules ------------------------------------------------------------------------------------------------------------------------

def disp_break(ctx, sd, i: int, mult: float = 1.5) -> bool:
    """A displacement break at bar i (side space): a body >= mult x the mean body of the 10 bars before, or an FVG completed at i."""
    body = abs(sd.c[i] - sd.o[i])
    prev = np.abs(sd.c[max(0, i - 10):i] - sd.o[max(0, i - 10):i])
    return bool((len(prev) and body >= mult * float(prev.mean()) > 0) or any(g.i == i for g in sd.gaps))


def raid_ref(ctx, sd, sw, i: int, p):
    """A19-mss-when-raid-missing (010 ~41:31: "I wanted this one to break down more specifically"): the expected raid level R (raid_level "pdh" = the prior day's
    low for a long / high for a short, when no later day took it). R TAKEN today (case A): the MSS reference is the swing that started the leg into the raid
    (Ep08.4 leg_origin of the sweep extreme). R NOT TAKEN (case B): a break of a short-term swing inside the range is no MSS; the reference is the swing that
    launched the leg making the SESSION extreme; in both cases only a displacement break counts (sw["raid_disp"], tested in setups.break_ok). None = rule n/a (R unknown):
    the caller falls back to the ordinary reference."""
    S = _S()
    key = "pdl1" if sd.sign > 0 else "pdh1"
    if key not in ctx.pd:
        return None
    r_s = sd.x(ctx.pd[key])
    e = sw["ext_i"]
    taken = bool(sd.l[ctx.start:i + 1].min() <= r_s + 1e-9)
    hit("raid_ref")
    sw["raid_disp"] = True                            # both cases: a DISPLACEMENT body close beyond the reference is the MSS (010)
    if taken:
        q = S._SM.leg_origin(sd, e, i)
        sw["raid_miss"] = False
    else:
        e_d = ctx.start + int(np.argmin(sd.l[ctx.start:e + 1]))
        q = S._SM.leg_origin(sd, e_d, i)
        sw["raid_miss"] = True
    return None if q is None else (q.i, q.price, True)


def eq_wait_waived(ctx, sd, p) -> bool:
    """A19-mss-no-rel-sweep-with-htf-draw (019 ~8:34, ~9:25: "why didn't it go below that it doesn't need to"): with the session draw LOCKED in the trade's direction the
    lower relative equal low need not be run before the MSS."""
    if not p.mss_eq_wait_unless_draw:
        return False
    lk = getattr(ctx, "cur_lock", None)
    ok = bool(lk and lk.get("side") == sd.sign)
    if ok:
        hit("eq_wait_waived")
    return ok


def micro_active(ctx, sd, i: int, p) -> bool:
    """N-micro-structure-regime (024 ~10:08: "when the market is moving when it's dynamic"): a small intraday consolidation at closed bar i - the range since
    09:30 under micro_range_adr x ADR5, at least two ALTERNATING swing points (a high and a low, twice) and no displacement bar since 09:30
    [our interpretation of "consolidation / no displacement"]. Then the MSS reference is read on the 5m chart (mss_ref_tf 5)."""
    S = _S()
    k0 = S._idx_at(ctx, 570)
    if k0 >= len(ctx.t) or i <= k0 + 4:
        return False
    a5 = adr5(ctx)
    if not a5:
        return False
    if float(ctx.h[k0:i + 1].max() - ctx.l[k0:i + 1].min()) >= p.micro_range_adr * a5:
        return False
    pv = sorted([(q.i, 1) for q in sd.ph if q.known <= i and q.i >= k0] + [(q.i, -1) for q in sd.pl if q.known <= i and q.i >= k0])
    if sum(1 for a, b in zip(pv, pv[1:]) if a[1] != b[1]) < 2:
        return False
    if any(_real_disp(ctx, j) for j in range(k0, i + 1)):
        return False
    hit("micro_regime")
    return True


def arm_bias_side(ctx, sd, sw, i: int, session: str, ref_in_o_space: float, ext_from: int) -> bool:
    """Arm the OPPOSITE Side's sweep once (the stops the against-bias break ran): level = the broken swing (in that Side's space), extreme = its lowest low since
    bar `ext_from` (shared by A19-break-against-htf-stop-run and A19-reh-short-term-low-trap). False when it was armed before / that Side is busy / unknown."""
    if sw.get("sr_armed"):
        return False
    sm = getattr(ctx, "sides_map", None)
    o = sm.get(-sd.sign) if sm else None
    if o is None or o.sweep is not None:
        return False
    sw["sr_armed"] = True
    seg = o.l[ext_from:i + 1]
    ext_i = ext_from + int(np.argmin(seg))
    o.sweep = dict(session=session, name="stoprun", level=float(ref_in_o_space), key="stoprun", ext=float(o.l[ext_i]), ext_i=ext_i, broke=None, sweep_i=i, smt=None, smt2=None)
    return True


def reh_trap_gate(ctx, sd, sw, i: int, p, session: str = "AM"):
    """A19-reh-short-term-low-trap (029 ~48:29: "what do they see that as a market structure shift"): bias long (the htf.table / loop reading, `bias_at`), the HTF
    objective above not yet reached and the last two swing highs relatively equal (A3 eq_tol) and still untaken: a MSS-path break of a short-term low under them
    (a swing low formed after the first of the two highs and closed through by bar i) is bait that builds buy-side above the REH, not a bearish MSS - the
    AGAINST-bias order (a break/MSS-based one: sw["broke"] set) is rejected and the bias Side's sweep is armed once at that low (the stops the break ran; its
    long then follows the ordinary next-bullish-FVG flow). Mirror for shorts. Other order kinds (no MSS break) are not this gate's business."""
    S = _S()
    if sw.get("broke") is None:
        return None
    w = bias_at(ctx, p, session, i)
    if not w or w == sd.sign:
        return None
    ws = other_side(ctx, sd, p)
    hs = [q for q in ws.ph if q.known <= i and q.i >= ctx.start]
    if len(hs) < 2 or abs(hs[-1].price - hs[-2].price) > p.eq_tol_pts * p.es_pt:
        return None
    top = max(hs[-1].price, hs[-2].price)
    if ws.h[hs[-1].i + 1:i + 1].max(initial=-np.inf) >= top:
        return None                                       # the REH was taken: the run is spent
    if S._SM.htf_done_sign(ctx, w, i):
        return None                                       # the HTF objective was reached
    lows = [q for q in ws.pl if hs[-2].i < q.i and q.known <= i and ws.c[q.known:i + 1].min(initial=np.inf) < q.price - 1e-9]
    if not lows:
        return None                                       # no short-term low under the REH was actually broken
    hit("reh_trap")
    q = lows[-1]
    if arm_bias_side(ctx, sd, sw, i, session, q.price, q.i):
        hit("reh_trap_arm")
    return "x_reh_trap"


# --- M12: turtle soup, second take-out / intermediate-term pools / SMT / next array -------------------------------------------------------------------

def reswept(ctx, sd, sw, i: int, p) -> bool:
    """M12-second-takeout-turtle-soup (046 ~1:01:58: "I don't think it's something to build a framework on"): the swept pool was ALREADY traded through earlier (after
    it formed) and a later close came back above it (a rally) before this sweep - a second, shallow break and recovery is a likely deeper retracement, no turtle
    long. The rally must NOT have taken the opposing high (the highest high from the pool's creation to the first break); one that did starts a new range. The pool
    exists from its natural creation (the last swing of a relative-equal cluster; strategy._level_created with the sweep's own session clock), never from before."""
    S = _S()
    key = sw.get("key", "")
    if not key or sw.get(S._SM.SYNTH):
        return False
    lvl, s_i = float(sw["level"]), int(sw.get("sweep_i", sw["ext_i"]))
    if key.startswith("rel_eq"):
        tol = p.eq_tol_pts * p.es_pt
        qs = [q for q in sd.pl if q.known <= s_i and abs(q.price - lvl) <= tol and q.i < s_i]
        a = (max(q.i for q in qs) + 1) if qs else s_i
    else:
        try:
            a = max(ctx.start, int(S._level_created(ctx, key, str(sw.get("session") or "AM"))))
        except Exception:
            a = ctx.start
    if a >= s_i:
        return False
    seg = np.flatnonzero(sd.l[a:s_i] < lvl - 1e-12)
    if not len(seg):
        return False
    j = a + int(seg[0])
    h0 = float(sd.h[a:j + 1].max())                  # the opposing high of the range the first break came from: a rally that TOOK it is a new range, not a failed break
    ok = bool((sd.c[j + 1:s_i] > lvl).any()) and bool(sd.h[j + 1:s_i].max(initial=-np.inf) < h0 - 1e-12)
    if ok:
        hit("reswept")
    return ok


def second_break_partial(ctx, sd, pos, tr, ts, i: int, p) -> None:
    """M12-second-takeout-turtle-soup (046): an open trade whose target POOL was already traded earlier today (before the fill) and now takes it by a shallow break
    (<= ts_max_pts) that closes back inside protects itself: a partial of what is left at the close (once). Side space (shorts = the mirrored long)."""
    if pos.get("sb_done") or not pos["left"] or i <= pos["fill_i"]:
        return
    S = _S()
    kinds = pos.get("level_kinds") or []
    for k in range(pos["k"], len(pos["levels"])):
        v = pos["levels"][k]
        if k >= len(kinds) or kinds[k] not in S.POOL_KINDS:
            continue
        before = sd.h[ctx.start:pos["fill_i"]]
        if not len(before) or before.max() < v:
            continue
        if sd.h[i] > v and sd.h[i] - v <= p.ts_max_pts * p.es_pt and sd.c[i] < v:
            q = min(pos["left"], max(p.lot, S._lots(pos["left"] * p.partial, p.lot)))
            if q >= pos["left"]:
                return
            tr.exits.append((ts, sd.x(sd.c[i]), q, "second_break"))
            pos["left"] -= q
            pos["sb_done"] = True
            hit("second_break")
            return


ITL_KEYS = ("pdl2", "pdl3", "pdh2", "pdh3", "pwl", "pwh", "pml", "pmh", "ipda", "week_", "parent_lo", "parent_hi", "tfp")     # the pool keys older than yesterday (strategy._sell_side / ld4 pools)


def itl_ok(ctx, sd, sw, i: int, p) -> bool:
    """new-intermediate-term-hl-fade (cc09_005 ~23:14: "it's beyond just yesterday"): a turtle-soup fade of an INTERMEDIATE-TERM pool (older than yesterday: pdl2 / pdl3,
    last week, last month, IPDA) needs context: an HTF array at the extreme, or a range-bound market (the last 10 sessions' whole range <= 3 x ADR5), or a long
    trend into the pool (profit taking: the last 10 sessions moved >= 3 x ADR5 against the fade's direction) [our interpretation of "long trend"]. Other pools
    are n/a (True)."""
    S = _S()
    key = str(sw.get("key", ""))
    if not key.startswith(ITL_KEYS):
        return True
    hit("itl_context")
    if S._htf_tag(ctx, sd, i, sw["ext"], p.eq_tol_pts * p.es_pt):
        return True
    hs = getattr(ctx, "hist", [])[-10:]
    a5 = adr5(ctx)
    if not hs or not a5:
        return False
    rng = max(float(x.high.max()) for x in hs) - min(float(x.low.min()) for x in hs)
    if rng <= 3.0 * a5:
        return True
    net = float(hs[-1].close.iloc[-1]) - float(hs[0].open.iloc[0])
    return bool(sd.sign * net <= -3.0 * a5)                # a long fade of a low after a decline of >= 3 ADR (the mirror for a short)


def ts_smt_ok(sw) -> bool:
    """B18-smt-accum-distrib (cc03_005 ~10:20: "otherwise it would have been permitted to go lower"): the SMT of the sweep (either partner)."""
    return bool(sw.get("smt") is True or sw.get("smt2") is True)


def next_array_level(ctx, sd, i: int, level: float, p, known_by):
    """new-stop-run-overshoot-next-array (025 ~1:05:16; 038 ~46:12): the likely extreme of a run of the pool `level` (side space, a sell-side low) is the next
    opening gap (NWOG / NDOG / ORG) or PD array (FVG / OB / VI) BEYOND it: the first level more than ts_min_beyond_pts below it - a wick CE hugging the pool is
    skipped. Returns (limit price = the level's near edge, stop = its far edge - 1 tick) or None. Gap rows offer each of high / CE / low, the gap's low as far edge."""
    S = _S()
    mb = p.ts_min_beyond_pts * p.es_pt
    cand = [(top, bot) for top, bot, kn in S._ts_arrays(ctx, sd, i, known_by)]
    cand += [(z.top, z.bottom) for z in sd.vis("bull") if z.i <= i]
    orgs = ctx.org[:-1] if (ctx.t[i] < 570 and ctx.org_today) else ctx.org
    rows = list(gap_list(ctx, i, ("nwog", "nwog_rth", "ndog"))) + [(max(a, b), min(a, b), (a + b) / 2) for a, b in orgs[-5:]]
    for hi, lo, ce in rows:
        zt, zb = max(sd.x(hi), sd.x(lo)), min(sd.x(hi), sd.x(lo))
        for v in (zt, (zt + zb) / 2, zb):
            cand.append((v, zb))
    ok = [(near, far) for near, far in cand if near <= level - mb - 1e-9]
    if not ok:
        return None
    near, far = max(ok, key=lambda x: (x[0], x[1]))
    hit("ts_next_array")
    return float(near), float(far - _tk(p))


# --- A8: inversion FVGs ------------------------------------------------------------------------------------------------------------------------------

def ifvg_zone(sd, tags: dict):
    """The inversion zone of an IFVG order (its tags: zone_top / fvg_bottom / fvg_i), or None."""
    top, bot, zi = tags.get("zone_top"), tags.get("fvg_bottom"), tags.get("fvg_i")
    if top is None or bot is None or zi is None:
        return None
    for z in sd.ifvgs():
        if z.i == zi and abs(z.top - float(top)) < 1e-9 and abs(z.bottom - float(bot)) < 1e-9:
            return z
    return None


def _taken_pools(ctx, sd, i: int, p, session: str, a: int, b: int) -> list:
    """The sell-side pools (side space) traded through by a bar in a..b: this session's named pools and the relative equal lows standing at bar a-1."""
    S = _S()
    lv = S._sell_side(ctx, sd, session, i, p.extra_pools, p)
    for k, eq in enumerate(S._eq_levels(sd, max(a, 1) - 1, p.eq_tol_pts * p.es_pt, lows=True, p=p)):
        lv[f"rel_eq_lows{k}"] = eq               # the relative equal lows standing when the window STARTS (one taken inside it is dropped from a later list)
    low = sd.l[a:b + 1].min(initial=np.inf)
    return sorted(v for v in lv.values() if low < v - 1e-12)


def ifvg_run_gate(ctx, sd, sw, i: int, p, session: str, z, lvt: list):
    """A8-ifvg-narrative-liquidity-run (078 ~51:00: "an inversion fair value gap is narrative based"): (a) the HTF bias is this way, (b) an old low (sell-side pool)
    was taken inside or just beyond (one gap height) the bearish FVG between its formation and the inversion; (c) the inversion (an MSS closing above its high) is
    the IFVG itself. Without (a) it is just an FVG in its original direction. ifvg_over_pool_pref: an IFVG whose range does not contain the taken pool is
    rejected when another IFVG after the sweep does."""
    if not p.ifvg_need_run:
        return None
    hit("ifvg_run")
    if want(ctx) != sd.sign:
        return "x_ifvg_no_bias"
    a = max(ctx.start, z.src - 1)
    ht = z.top - z.bottom
    pools = [v for v in _taken_pools(ctx, sd, i, p, session, a, z.i) if z.bottom - ht <= v <= z.top + 1e-9]
    if not pools:
        return "x_ifvg_no_run"
    if any(z.bottom - 1e-9 <= v <= z.top + 1e-9 for v in pools):
        lvt.append("ifvg_pool_inside")
    elif p.ifvg_over_pool_pref:
        hit("ifvg_pool_pref")
        for z2 in sd.ifvgs():
            if z2 is z or z2.i > i or z2.i < ctx.start:
                continue
            if any(z2.bottom - 1e-9 <= v <= z2.top + 1e-9 for v in _taken_pools(ctx, sd, i, p, session, max(ctx.start, z2.src - 1), z2.i)):
                return "x_ifvg_pool_pref"
    return None


def ifvg_tails_gate(ctx, sd, i: int, p, z):
    """A8-ifvg-stacked-tails-exclusion (090 ~21:24: "I like to see these things fail"): a cluster of 2+ candles with long lower tails (lower wick >= body) whose lows end
    within tails_tol_ticks ticks of each other, sitting just below the IFVG (within one gap height under its bottom), is run first: the IFVG is armed only after a
    low below the cluster's lows. Side space."""
    tk = _tk(p) * p.tails_tol_ticks
    ht = z.top - z.bottom
    a = max(ctx.start, z.src - 20)
    ks = [k for k in range(a, z.i + 1) if z.bottom - ht - 1e-9 <= sd.l[k] < z.bottom
          and (min(sd.o[k], sd.c[k]) - sd.l[k]) >= abs(sd.c[k] - sd.o[k]) - 1e-9]
    best = None
    for k in ks:
        grp = [m for m in ks if abs(sd.l[m] - sd.l[k]) <= tk + 1e-9]
        if len(grp) >= 2 and (best is None or len(grp) > len(best)):
            best = grp
    if best is None:
        return None
    hit("ifvg_tails")
    lo, last = min(sd.l[m] for m in best), max(best)
    if sd.l[last + 1:i + 1].min(initial=np.inf) < lo - 1e-9:
        return None
    return "x_ifvg_tails"


def ifvg_far_edge_unlikely(sd, i: int, z) -> bool:
    """A8-ifvg-narrative-liquidity-run (078, the bearish-mirror remark: the far edge H "is unlikely to be reached if an FVG just beyond it is still open"), side
    space [our interpretation]: an FVG still untouched directly beyond the inversion zone's far edge (its top within one gap height under z.bottom) is a support the
    retrace stops at - the zone's far edge is not expected to be reached (tag ifvg_far_edge_unlikely). The 'balanced range beyond' half of the remark is the
    htf.table's own business (balance_tf decides which arrays are still alive); nothing is added for it."""
    ht = z.top - z.bottom
    for g in sd.gaps:
        if g.i > i or not (z.bottom - ht - 1e-9 <= g.top <= z.bottom + 1e-9) or g.i >= z.i:
            continue
        if sd.l[g.i + 1:i + 1].min(initial=np.inf) > g.top + 1e-9:
            hit("ifvg_far_edge")
            return True
    return False


def ifvg_pool_gate(ctx, sd, i: int, p, z):
    """A8-ifvg-before-pool (102 ~1:08:45: "because that sell side's still there"): the IFVG is armed only while the nearest swing extreme beyond it (the draw: side space the
    nearest swing high above its top, known at the inversion) has not been traded through; once taken before the return the draw is spent - cancel."""
    hs = [q for q in sd.ph if q.known <= z.i and q.price > z.top]
    if not hs:
        return None
    hit("ifvg_pool")
    q = min(hs, key=lambda q: q.price)
    return "x_ifvg_pool_taken" if sd.h[z.i + 1:i + 1].max(initial=-np.inf) > q.price + 1e-9 else None


def ifvg_w_cap(sd, g, entry: float, stop: float, i: int | None, p):
    """A8-ifvg-depth-tolerances (102 ~1:11:04, ~1:55:46: "only be high probability if it stayed below consequent encroachment"), ifvg_depth "w_cap", side space (the
    inverted bearish gap [bottom, top], the retrace falls toward it; the real short's wording mirrored). The original gap's third candle opens the passes.
      (a) PARTLY re-traded - a candle printed high W inside the gap before the failure: the retrace should stop at the top, the CE or W (cap = max(CE, W)); the entry
          is at / above the cap, the stop just under it, and a retrace deeper than the cap by more than the mohawk (2 ticks) kills the setup;
      (b) NOT re-traded: the retrace may go to the far edge (bottom), stop beyond it;
      (c) traded through and back: valid only while the lows stay >= CE - 1 tick, stop just under the CE.
    Returns (entry, stop) or None (skip)."""
    hit("ifvg_w_cap")
    ce = (g.top + g.bottom) / 2
    orig = g.src + 1
    ps = L.ifvg_passes(sd.h, sd.l, g.top, g.bottom, orig, g.i)
    tk = _tk(p)
    low = sd.l[g.i + 1:i + 1].min(initial=np.inf) if i is not None else np.inf
    if ps == "none":
        return entry, g.bottom - p.pad
    if ps == "partial":
        w = float(sd.h[orig + 1:g.i].max())
        cap = max(ce, min(w, g.top))
        if low < cap - 2 * tk - 1e-9:
            return None
        return max(entry, cap), cap - p.pad
    if low < ce - tk - 1e-9:
        return None
    return entry, ce - p.pad


# --- A4: poke, sweep body cluster, HTF body qualification ------------------------------------------------------------------------------------------

def poke_cancel(ctx, sd, i: int, p, session: str):
    """A4-wick-poke-vi-invalidation (090 ~1:05:53: "if it goes back above this high here ... I'm not interested"): an AM idea whose HTF level (a same-side 4h / daily array)
    was only POKED by a wick (no body close beyond) records the poke extreme H; a later trade beyond H (after the poke cluster ended) cancels the AM orders of
    that side (the PM is re-evaluated at 13:30), a pending one included (strategy's pending block asks again on every bar). WICK-only means no body at all since
    09:30 reached beyond the array's far edge (a day that already closed beyond it is no poke). Side space: a poke below the array's bottom image. Returns a reject
    key or None."""
    cf = getattr(ctx, "conf", None)
    if cf is None or session == "PM":
        return None
    S = _S()
    k0 = S._idx_at(ctx, 570)
    if k0 >= len(ctx.t) or i <= k0:
        return None
    body_lo = np.minimum(sd.o[k0:i + 1], sd.c[k0:i + 1])
    for top, bot, tf, src, known in cf.valid(now_ts(ctx, i), sd.sign, ("4h", "D"), (0, 1, 3)):
        zb = min(sd.x(top), sd.x(bot))
        poke = (sd.l[k0:i + 1] < zb - 1e-9) & (body_lo >= zb - 1e-9)
        if not poke.any() or body_lo.min() < zb - 1e-9:
            continue                                        # no poke / a body already closed beyond the array: not a wick-only poke
        hit("poke_cancel")
        j = int(np.argmax(poke))
        ext, m = sd.l[k0 + j], j + 1
        while m < len(poke) and poke[m]:
            ext = min(ext, sd.l[k0 + m])
            m += 1                                          # the poke cluster
        if m < len(poke) and sd.l[k0 + m:i + 1].min() < ext - 1e-9:
            return "x_poke_high_cancel"
    return None


def body_qualified(ctx, sd, g, i: int, p) -> bool:
    """A4-ltf-body-qualification (104 ~21:53, ~34:55: "only the candlesticks wicks are piercing it"): an HTF entry zone reached by a run stays qualified while the
    15m and 5m BODIES since it formed stay on the near side of its far edge (side space: no body low below its bottom), however far the wicks pierce."""
    for m in (5, 15):
        if m < ctx.tf:
            continue
        o, h, l, c, last, first = bars_tf(ctx, sd, m, i)
        for k in range(len(c)):
            if first[k] > g.i and min(o[k], c[k]) < g.bottom - 1e-9:
                return False
    hit("htf_body_qual")
    return True


def body_qual_zone(ctx, sd, bottom: float, from_i: int, i: int) -> bool:
    """A4-ltf-body-qualification for a zone given by its bottom (the turtle-soup external array): the 15m and 5m BODIES since bar `from_i` stayed on the near side of
    it (no body low below `bottom`, side space), whatever the wicks did."""
    for m in (5, 15):
        if m < ctx.tf:
            continue
        o, h, l, c, last, first = bars_tf(ctx, sd, m, i)
        for k in range(len(c)):
            if first[k] > from_i and min(o[k], c[k]) < bottom - 1e-9:
                return False
    hit("htf_body_qual_zone")
    return True


def daily_first_return(ctx, sd, sw, i: int, p) -> bool:
    """A4-sweep-body-cluster (cc02_007 ~21:51): the sweep extreme ran below a daily BODY-low cluster (2+ sessions whose bodies' lows end within 0.1 x ADR5) and it
    is the first return to that zone since the cluster formed, at least daily_first_days sessions ago (30-45 trading days = 1.5-2 months [our interpretation]): HTF
    accumulation - tagged daily_first_return (on the LTF the continuation patterns there are ignored and the buy comes after a swing high is broken). Side space."""
    hs = getattr(ctx, "hist", [])
    a5 = adr5(ctx)
    if len(hs) < p.daily_first_days + 2 or not a5:
        return False
    s, tol = sd.sign, 0.1 * a5
    bl = np.array([min(s * float(x.open.iloc[0]), s * float(x.close.iloc[-1])) for x in hs])
    lo = np.array([float(s * x.low.min()) if s > 0 else float(-x.high.max()) for x in hs])
    for m in range(len(hs) - 1 - p.daily_first_days, 0, -1):
        grp = [k for k in range(max(0, m - 6), m + 1) if abs(bl[k] - bl[m]) <= tol]
        if len(grp) < 2:
            continue
        zone_lo = min(bl[k] for k in grp)
        if sw["ext"] < zone_lo and lo[m + 1:].min(initial=np.inf) > zone_lo + tol:       # no session since traded back down to the cluster's bodies
            hit("daily_first_return")
            return True
    return False


# --- B18: three-point swing SMT ---------------------------------------------------------------------------------------------------------------------

def three_point_smt(ctx, sd, i: int, pctx, ps, j: int, p):
    """B18-smt-three-point-swing (cc11_004 ~27:39: "you can sometimes have to trade through a short-term low"): this index prints low - LOWER low - HIGHER low
    while the partner prints low - lower low - LOWER low = a bullish SMT (side space; the mirror for shorts). The first point may be an earlier swing than the
    one next to the lower low (the window extends past a short-term low that all traded through) [our interpretation]. True / False, None without three swing
    lows on both. Swing lows confirmed by closed bars only."""
    xs = [q for q in sd.pl if q.known <= i and q.i >= ctx.start - 1]
    if len(xs) < 3:
        return None
    c_ = xs[-1]
    b_ = next((q for q in reversed(xs[:-1]) if q.price < c_.price), None)
    if b_ is None:
        return None
    a_ = next((q for q in reversed([q for q in xs if q.i < b_.i]) if q.price > b_.price), None)
    if a_ is None:
        return None
    pad = pd.Timedelta(minutes=ctx.tf * max(p.pivot_n, 1))

    def twin(q):
        t0, t1 = ctx.idx[q.i] - pad, ctx.idx[q.i] + pad
        cand = [r for r in ps.pl if r.known <= j and t0 <= pctx.idx[r.i] <= t1]
        return None if not cand else min(cand, key=lambda r: r.price)

    ta, tb, tc = twin(a_), twin(b_), twin(c_)
    if ta is None or tb is None or tc is None:
        return None
    hit("smt_three_point")
    return bool(tb.price < ta.price and tc.price < tb.price)


# --- A22 / M6 nested arrays --------------------------------------------------------------------------------------------------------------------------

def nested_at_am(ctx, sd, i: int, p) -> bool:
    """A22-htf-definition-nested-arrays (cc10_013 ~8:17, ~13:44; cc10_014 ~11:08: "nested ideas of premium array would be our catalyst"): the AM extreme of the PM
    reversal's side lies in an HTF array - the reversal set {4h, D, W} of the spec - or in a NESTED one: a 15m / 1h array overlapping an HTF array of the same
    polarity (any price overlap [our interpretation]). An extreme inside an HTF array alone counts too (that array is itself the higher-timeframe level the nested
    pair is made of); one only inside an un-nested 15m / 1h array does not (continuation). Real prices; False without a Confluence object."""
    cf = getattr(ctx, "conf", None)
    if cf is None or not ctx.am_hl:
        return False
    ext_r = float(ctx.am_hl[1] if sd.sign > 0 else ctx.am_hl[0])
    now = now_ts(ctx, i)
    tol = p.eq_tol_pts * p.es_pt
    low = [(min(t_, b_), max(t_, b_)) for t_, b_, *_ in cf.valid(now, sd.sign, ("15m", "1h"), (0,))]
    high = [(min(t_, b_), max(t_, b_)) for t_, b_, *_ in cf.valid(now, sd.sign, ("4h", "D", "W"), (0,))]
    hit("pm_rev_nested")
    if any(a - tol <= ext_r <= b + tol for a, b in high):
        return True
    return any(a - tol <= ext_r <= b + tol and any(c <= b and d >= a for c, d in high) for a, b in low)


# --- delivery states: state machine, tool map, consolidation fade -------------------------------------------------------------------------------------

STATE_TOOLS = {
    "RETRACEMENT": ("fvg", "ifvg", "implied_fvg", "vi", "void", "ifvg_061", "nfp_release_fvg", "arr_vi"),
    "EXPANSION": ("ob_pre", "ob_anchor", "arr_ob", "arr_cons_ob_open", "cisd_ob", "release_ob", "ts_cc_1h_ob"),
    "REVERSAL": ("turtle_soup", "ts_or60", "ts_cc_limit", "ts_external", "prev_pm_turtle", "hs_fade", "consol_fade"),
    "CONSOLIDATION": (),
}
_MAPPED = frozenset(k for v in STATE_TOOLS.values() for k in v)


def state_at(ctx, i: int, p) -> str:
    """The delivery state at closed bar i (levels.delivery_state, real prices; cached per bar)."""
    c = _c(ctx).setdefault(("state", p.consol_bars, p.consol_adr), {})
    if i not in c:
        c[i] = L.delivery_state(ctx.o, ctx.h, ctx.l, ctx.c, i, adr5(ctx), p.consol_bars, p.consol_adr)
    return c[i]


def state_gate(ctx, sd, i: int, p, tags: dict):
    """new-delivery-states-machine (cc01_001 ~2:33, ~7:51; cc01_002 ~18:35): no entry while the state is CONSOLIDATION (state_machine). new-state-to-array-map
    (cc01_001 ~2:33; cc01_002 ~12:42): state_tool_map - EXPANSION <-> order blocks, RETRACEMENT <-> FVG / void / VI, REVERSAL <-> sweeps (turtle soup),
    CONSOLIDATION <-> wait; an entry kind of another tool than the state's is rejected (kinds outside the map pass). Returns a reject key or None."""
    st = state_at(ctx, i, p)
    if not st:
        return None
    hit("state")
    if p.state_machine and st == "CONSOLIDATION" and tags.get("entry_kind") != "consol_fade":
        return "x_state_consolidation"
    k = tags.get("entry_kind")
    if p.state_tool_map and k in _MAPPED and k not in STATE_TOOLS[st]:
        return "x_state_tool"
    return None


def consol_fade_order(ctx, sd, i: int, p, session: str, risk_mult: float):
    """new-consolidation-exit-direction (cc09_004 ~5:07: "that's going to be the direction of the move outside the consolidation"): a lower-timeframe consolidation
    (range under consol_adr x ADR5 over consol_bars bars) most often exits with the daily / 4h order flow. A break OUT of the range against the bias (side space:
    a wick below the range low within the last 10 bars) that closes back inside is a stop run to fade: a limit at the range low, stop under the break's extreme,
    target the opposite extreme (the range high). Once per range. Entry kind consol_fade."""
    S = _S()
    if want(ctx) != sd.sign:
        return None
    n = p.consol_bars
    a5 = adr5(ctx)
    if not a5:
        return None
    sent = sd.__dict__.setdefault("_cfade", set())
    for j in range(i, max(ctx.start + n + 1, i - 10) - 1, -1):
        lo, hi = float(sd.l[j - n:j].min()), float(sd.h[j - n:j].max())
        if hi - lo >= p.consol_adr * a5 or not sd.l[j] < lo - 1e-9 or (j - n, j) in sent:
            continue
        if not sd.c[i] > lo or sd.h[j:i + 1].max() > hi:
            continue                                         # not back inside / it left through the top (the exit went the bias way)
        ext = float(sd.l[j:i + 1].min())
        entry, stop = lo, ext - p.pad
        if entry - stop < p.min_risk_pts * p.es_pt:
            continue
        sent.add((j - n, j))
        hit("consol_fade")
        sw = _synth_sw(S, session, "consol_fade", lo, ext, j + int(np.argmin(sd.l[j:i + 1])), j)
        tags = dict(unicorn=False, fvg_bottom=ext, fvg_ce=(lo + hi) / 2, entry_kind="consol_fade", mitigation=False, propulsion=False, no_leg_wait=True,
                    lv_tags=["consol_fade"])
        o = S._finish_order(ctx, sd, i, p, session, sw, entry, stop, risk_mult, hi, tags, skip_leg_pd=True, fixed=[(S._exit_px(hi, "pool", p), "pool")])
        if o is not None:
            return o
    return None


# --- A11: BPR CE entries, A17: opening-range rejection block -------------------------------------------------------------------------------------

def bpr_dead(sd, z, i: int, p) -> bool:
    """A11-bpr-levels-ce-rejection: the CE entry is void once a body closed below the CE since the BPR formed; bpr_left_far_edge (062: "once price has left, the far
    edge is the invalidation"): after the first close beyond the near edge (above the top, side space) only a close below the FAR edge (the bottom) voids it."""
    seg = sd.c[z.i + 1:i + 1]
    if not len(seg):
        return False
    if p.bpr_left_far_edge:
        left = np.flatnonzero(seg > z.top)
        if len(left):
            hit("bpr_far_edge")
            k = int(left[0])
            return bool(seg[:k].min(initial=np.inf) < z.mid - 1e-9 or seg[k:].min() < z.bottom - 1e-9)
    return bool(seg.min() < z.mid - 1e-9)


def bpr_ce_order(ctx, sd, i: int, p, session: str, risk_mult: float):
    """A11-bpr-levels-ce-rejection (062 ~3:47: "hits it like a brick wall"): a balanced price range (also a single-candle BISI / SIBI pair: bpr_def) is a reaction
    zone - high, CE, low, extended right: a limit at the CE on EVERY revisit from above (side space), stop below the BPR low, valid while no body closes below the
    CE. Repeat retests arm again (once per retest). Entry kind bpr_ce."""
    S = _S()
    sent = sd.__dict__.setdefault("_bpr_ce", {})
    for z in sorted([z for z in sd.bprs(p.bpr_max_gap_bars) if z.kind == "bull"], key=lambda z: -z.i):
        if z.i > i or z.i < ctx.start or bpr_dead(sd, z, i, p) or not sd.c[i] > z.top:
            continue
        key = (z.i, z.src)
        last = sent.get(key)
        a = z.i if last is None else last
        if last is not None and not sd.l[a + 1:i + 1].min(initial=np.inf) <= z.top:
            continue
        entry, stop = float(z.mid), float(z.bottom - p.pad)
        if entry - stop < p.min_risk_pts * p.es_pt:
            continue
        sent[key] = i
        hit("bpr_ce")
        sw = _synth_sw(S, session, "bpr_ce", z.top, z.bottom, max(z.src, 0), z.i)
        tags = dict(unicorn=False, fvg_bottom=float(z.bottom), fvg_ce=float(z.mid), entry_kind="bpr_ce", mitigation=False, propulsion=False, no_leg_wait=True,
                    lv_tags=["bpr_ce"], lvx={"bpr_ce_close": (float(z.mid), False)})
        o = S._finish_order(ctx, sd, i, p, session, sw, entry, stop, risk_mult, float(sd.h[max(z.src, 0):i + 1].max()), tags, skip_leg_pd=True)
        if o is not None:
            return o
    return None


def or_rb_order(ctx, sd, i: int, p, session: str, risk_mult: float):
    """A17-index-or-rejection-block (cc10_010 ~9:03: "the lowest close down close candle"): the opening-range rejection block. Long: among the down-close candles inside
    the 09:30-10:30 range the one with the LOWEST close - level = its close, the zone down to the OR60 low; on a later-morning return (from or_rb_from, before 12:00
    [our interpretation]) a limit at the level, valid while the lows hold above the OR60 low. Short: the LAST up-close candle inside the range (or_rb_bear "last";
    "highest_close" = the highest close) - level its close, invalid above the OR60 high. Real prices, mirrored by sd for shorts. Once per side and day."""
    S = _S()
    t = ctx.t[i]
    if t < max(p.or_rb_from, 630) or t >= 720 or getattr(ctx, "or60", None) is None:
        return None
    sent = sd.__dict__.setdefault("_or_rb", set())
    if (ctx.day, sd.sign) in sent:
        return None
    k0, k1 = S._idx_at(ctx, 570), S._idx_at(ctx, 630)
    o, c = ctx.o[k0:k1], ctx.c[k0:k1]
    if sd.sign > 0:
        ks = np.flatnonzero(c < o)
        if not len(ks):
            return None
        k = int(ks[np.argmin(c[ks])])
    else:
        ks = np.flatnonzero(c > o)
        if not len(ks):
            return None
        k = int(ks[-1]) if p.or_rb_bear == "last" else int(ks[np.argmax(c[ks])])
    level = float(sd.x(c[k]))
    or_lo = float(sd.x(ctx.or60[1] if sd.sign > 0 else ctx.or60[0]))
    if not (sd.c[i] > level and sd.l[k1:i + 1].min() > or_lo):
        return None
    entry, stop = level, or_lo - p.pad
    if entry - stop < p.min_risk_pts * p.es_pt:
        return None
    sent.add((ctx.day, sd.sign))
    hit("or_rb")
    sw = _synth_sw(S, session, "or_rb", level, or_lo, k0 + k, i)
    tags = dict(unicorn=False, fvg_bottom=or_lo, fvg_ce=(level + or_lo) / 2, entry_kind="or_rb", mitigation=False, propulsion=False, no_leg_wait=True,
                lv_tags=["or_rb"])
    return S._finish_order(ctx, sd, i, p, session, sw, entry, stop, risk_mult, float(sd.x(ctx.or60[0] if sd.sign > 0 else ctx.or60[1])), tags, skip_leg_pd=True)


def extra2(ctx, sd, i: int, p, session: str, risk_mult: float):
    """The non-sweep setups of this chunk, tried in order when the sweep machine has nothing (strategy._scan)."""
    if p.nwog_sr_entries:
        o = nwog_sr_order(ctx, sd, i, p, session, risk_mult)
        if o is not None:
            return o
    if p.gap_edge_entry:
        o = gap_edge_order(ctx, sd, i, p, session, risk_mult)
        if o is not None:
            return o
    if p.gap_quarter_retrace:
        o = gap_quarter_order(ctx, sd, i, p, session, risk_mult)
        if o is not None:
            return o
    if "bpr_ce" in p.entry_arrays:
        o = bpr_ce_order(ctx, sd, i, p, session, risk_mult)
        if o is not None:
            return o
    if p.or_rb:
        o = or_rb_order(ctx, sd, i, p, session, risk_mult)
        if o is not None:
            return o
    if p.consol_fade:
        o = consol_fade_order(ctx, sd, i, p, session, risk_mult)
        if o is not None:
            return o
    return None


# --- IR gates ---------------------------------------------------------------------------------------------------------------------------------------

def ir_window_ok(p, t: int) -> bool:
    """A7-immediate-rebalance-gates (b): minute-of-day t lies in a window where volatility is expected [our interpretation]: the macro window, the AM / PM sessions
    (p.am / p.pm) or a Silver Bullet window (p.sb_windows). By the clock - not by the caller's session label, which the Silver Bullet path only maps to AM / PM."""
    wins = [tuple(p.macro), tuple(p.am), tuple(p.pm)] + [tuple(w) for w in (p.sb_windows or ())]
    return any(a <= t < b for a, b in wins)


def ir_gates_ok(ctx, sd, i: int, p, session: str, use_want: bool = True) -> bool:
    """A7-immediate-rebalance-gates (059 ~4:50: "the immediate rebalance isn't going to help you all that much"): an immediate rebalance is a continuation trigger only
    if (a) the draw / HTF bias was known beforehand and points its way (ir_need_draw) and (b) it prints in a window where volatility is expected (ir_need_window:
    [our interpretation] the macro window, the am / pm sessions or a Silver Bullet window - by the clock, see ir_window_ok). Used by the opt-in IR paths (ir_entries, sb_rebalance_ext)."""
    if p.ir_filters:                          # caption-gap M11-immediate-rebalance-management (092 ~1:41:37; 100 ~1:36:14): no IR on a Friday or ahead of a pending 10:00 release
        from claude_hf.daytypes import events as _ev
        if ctx.day.weekday() == 4 or (_ev(ctx.day) & _S().NEWS_1000 and int(ctx.t[i]) < 600):
            hit("ir_filters")
            return False
    if p.ir_need_draw and bias_at(ctx, p, session, i, use_want) != sd.sign:
        return False
    if p.ir_need_window and not ir_window_ok(p, int(ctx.t[i])):
        return False
    hit("ir_gates")
    return True


# --- range lock (A12-range-internal-ignore) -----------------------------------------------------------------------------------------------------

def range_lock_set(sd, sw, i: int, inval: float, lo: float) -> None:
    """A12-range-internal-ignore (064 ~56:17; 066 ~32:01: "all of these candles in between are all time distortion"): remember the dealing range an armed order defines -
    low `lo` (the OB low / the sweep extreme), high = the leg high so far, invalid on a body close below `inval` (the OB MT / the low) or an expansion beyond the high."""
    hit("range_lock")
    sd.__dict__["_rlock"] = dict(lo=float(lo), hi=float(sd.h[sw["ext_i"]:i + 1].max()), inval=float(inval), since=i)


def range_locked(sd, i: int) -> bool:
    """True while bar i lies strictly INSIDE (wicks) an active range lock: its candles are ignored (no new sweep / MSS / FVG is read from them). The lock ends on a
    body close below its invalidation or a trade beyond its high (expansion toward the first draw)."""
    rl = sd.__dict__.get("_rlock")
    if rl is None or i <= rl["since"]:
        return False
    if sd.c[i - 1] < rl["inval"] or sd.h[i - 1] > rl["hi"]:
        sd.__dict__["_rlock"] = None
        return False
    hit("range_locked")
    return bool(sd.h[i] <= rl["hi"] and sd.l[i] >= rl["lo"])


# --- the order gate of this chunk -------------------------------------------------------------------------------------------------------------------

def order_gate2(ctx, sd, sw, i: int, p, entry: float, stop: float, session: str, lvt: list, lvx: dict, tags: dict):
    """Gates / tags of setups_models #2/7 at order completion (strategy._finish_order, after order_gate). Returns a reject key or None."""
    tags["setup_model"] = setup_model(sd, sw)
    tags["delivery"] = delivery_dir(ctx, sd, i)
    if p.div_tag:
        d = L.stoch_divergence(sd.h, sd.l, sd.c, i, p.pivot_n)
        if d:
            tags["div_type"] = d
            hit("div_tag")
    if p.dfvg_half != "off":
        r = dfvg_gate(ctx, sd, sw, i, p, lvt)
        if r:
            return r
    if p.reh_trap:
        r = reh_trap_gate(ctx, sd, sw, i, p, session)
        if r:
            return r
    if p.org_two_rally:
        r = org_two_rally_gate(ctx, sd, i, p)
        if r:
            return r
    if p.poke_high_cancel:
        r = poke_cancel(ctx, sd, i, p, session)
        if r:
            return r
    if p.state_machine or p.state_tool_map:
        r = state_gate(ctx, sd, i, p, tags)
        if r:
            return r
    if p.daily_first_ltf and _c(ctx).get("dfr") == -sd.sign:
        hit("dfr_against")
        return "x_dfr_against"                       # cc02_007: at a daily first-return zone the LTF ignores the continuation against the accumulation
    if tags.get("entry_kind") == "ifvg" and (p.ifvg_need_run or p.ifvg_tails_block or p.ifvg_pool_intact or p.ifvg_far_edge_tag):
        z = ifvg_zone(sd, tags)
        if z is not None:
            if p.ifvg_far_edge_tag and ifvg_far_edge_unlikely(sd, i, z):
                lvt.append("ifvg_far_edge_unlikely")
            r = ifvg_run_gate(ctx, sd, sw, i, p, session, z, lvt)
            if not r and p.ifvg_tails_block:
                r = ifvg_tails_gate(ctx, sd, i, p, z)
            if not r and p.ifvg_pool_intact:
                r = ifvg_pool_gate(ctx, sd, i, p, z)
            if r:
                return r
    if (p.daily_first_return or p.daily_first_ltf) and str(sw.get("key", "")).startswith("rel_eq") and daily_first_return(ctx, sd, sw, i, p):
        lvt.append("daily_first_return")
        _c(ctx)["dfr"] = sd.sign
        if p.daily_first_ltf and sw.get("broke") is None:
            hit("dfr_need_break")
            return "x_dfr_need_break"                # buy only AFTER the swing high is broken (an MSS-path order), not the bare sweep / OB-before-break
    return None
