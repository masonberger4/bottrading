"""Caption-gap pass (digests/rulebook_gaps/*.md), package setups_models, chunk 3 of 7: the engine glue of its 36 specs (levels_liquidity_targets 17, management_partials_trailing_exits
11, models_setups_entries 8; sm2.py holds chunks 1-2).

Same conventions as sm2.py: side space (shorts run mirrored prices), a bar is used only after it closes (`i` = the last CLOSED bar, an order armed on it fills from bar i+1), an object
only from the bar that completes it, daily / weekly objects only after their session closes (everything reads `ctx.hist`, the COMPLETED prior sessions, plus today's bars through
the bar being judged). Every function sits behind a Params switch of the "caption-gap pass, setups_models #3/7" block; interpretations the sources do not pin down are marked
[our interpretation]. `HITS` is sm2's counter dict (tests: proof that a switch's code path RAN).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import levels as L
from . import sm2

HITS = sm2.HITS
hit = sm2.hit

MIN1 = 1e-9


def _S():
    from . import strategy as S
    return S


def _c(ctx) -> dict:
    return ctx.__dict__.setdefault("_sm3", {})


def _want(ctx) -> int:
    return sm2.want(ctx)


def _arr_tf(m: int) -> str:
    return {15: "15m", 30: "30m", 60: "1h", 240: "4h", 1440: "D"}[m]       # (1440: caption-gap M2-htf-ob-precondition - the daily arrays, order blocks included)


# --- 1h buckets of a Side (A23 wick depth) -----------------------------------------------------------------------------------------------------

def h1_buckets(ctx, sd):
    """Clock-aligned 1h buckets of the day frame in side space: (first, last, done, o, h, l, c) arrays; a bucket is `done` once its last base bar is in (never a partial bucket)."""
    hc = sd.__dict__.get("_h60_sm3")
    if hc is None:
        key = ctx.idx.floor("60min")
        b = pd.Series(np.arange(len(key)), index=key).groupby(level=0)
        first, last = b.min().values, b.max().values
        done = np.asarray((ctx.idx[last] - b.min().index) >= pd.Timedelta(minutes=60 - ctx.tf))
        o = np.array([sd.o[a] for a in first])
        c = np.array([sd.c[z] for z in last])
        hh = np.array([sd.h[a:z + 1].max() for a, z in zip(first, last)])
        ll = np.array([sd.l[a:z + 1].min() for a, z in zip(first, last)])
        hc = sd.__dict__["_h60_sm3"] = (first, last, done, o, hh, ll, c)
    return hc


def wick_ce_for(ctx, sd, level: float, i: int, p):
    """A23-1h-wick-ce-sweep-depth (063 ~24:04): the CE of the longest LOWER wick among the last `wick_depth_bars` complete 1h bars whose wick reaches under the pool `level` (the CE itself
    at or under it); None when there is none."""
    first, last, done, o, hh, ll, c = h1_buckets(ctx, sd)
    ok = np.flatnonzero(done & (last <= i))[-p.wick_depth_bars:]
    best, ce = 0.0, None
    for j in ok:
        body_lo = min(o[j], c[j])
        wk = body_lo - ll[j]
        mid = (body_lo + ll[j]) / 2
        if ll[j] < level and mid <= level + MIN1 and wk > best:
            best, ce = wk, float(mid)
    return ce


def dealing_range(ctx, sd, i: int, p):
    """The dealing range (side space) of the last `pd_day_range` sessions plus today through bar i: (low, high)."""
    hist = list(getattr(ctx, "hist", []))[-p.pd_day_range:]
    hi = [float(x.high.max()) for x in hist] + [float(ctx.h[ctx.start:i + 1].max())]
    lo = [float(x.low.min()) for x in hist] + [float(ctx.l[ctx.start:i + 1].min())]
    R_hi, R_lo = max(hi), min(lo)
    return (R_lo, R_hi) if sd.sign > 0 else (-R_hi, -R_lo)


def eq_hunt_level(ctx, sd, i: int, p, key: str, v: float) -> bool:
    """new-eq-stop-hunt-entry (075 ~1:31:00): the short-term low `v` (a swing_low pool) lies within eq_hunt_band of the dealing-range EQ."""
    if not str(key).startswith("swing_low"):
        return False
    lo, hi = dealing_range(ctx, sd, i, p)
    if hi - lo <= 0:
        return False
    return bool(abs(v - (lo + hi) / 2) <= p.eq_hunt_band * (hi - lo) + MIN1)


def pool_age(ctx, key: str):
    """M4-swept-low-age: the age in sessions of the swept low behind a pool key (None = unknown): pdl1..3 / pdh1..3 = 1..3, a swing low of today 0 / of the prior session 1, the week / month
    pools 5 / 20 (upper bounds), ipda<n> = n [our interpretation of "recent": a few days to a week]."""
    k = str(key)
    if k[:3] in ("pdl", "pdh") and k[3:].isdigit():
        return int(k[3:])
    if k.startswith("swing_low") and k[len("swing_low"):].isdigit():
        return 0 if int(k[len("swing_low"):]) >= ctx.start else 1
    if k in ("pwl", "pwh", "week_lo", "week_hi"):
        return 5
    if k in ("pml_month", "pmh_month"):
        return 20
    if k.startswith("ipda") and k[4:].isdigit():
        return int(k[4:])
    return None


def prefer_hits(ctx, sd, i: int, p, hits: list) -> list:
    """The sweep pick's candidates (strategy._scan_core, before min()): eq_hunt "prefer" - the stop-hunt sweeps win; ts_age_rank "prefer" - a swept low of at most 5 sessions wins (both
    stay eligible when none is preferred)."""
    if p.eq_hunt == "prefer":
        hh = [kv for kv in hits if eq_hunt_level(ctx, sd, i, p, kv[0], kv[1])]
        if hh:
            hit("eq_hunt_prefer")
            hits = hh
    if p.ts_age_rank == "prefer":
        hh = [kv for kv in hits if (pool_age(ctx, kv[0]) is not None and pool_age(ctx, kv[0]) <= 5)]
        if hh and len(hh) < len(hits):
            hit("ts_age_prefer")
            hits = hh
    return hits


def any_sweep_switch(p) -> bool:
    return bool(p.wick_sweep_depth or p.shallow_sweep_wait or p.sweep_max_linger or p.ts_linger_bars or p.allow_htf_array_premise)


def sweep_init(ctx, sd, sw, i: int, p, session: str):
    """At the creation of a sweep (strategy._scan_core): A23 wick CE (the longest 1h wick under the REL), M3 shallow-run wait, eq_hunt / ts_age tags. Returns "drop" or None."""
    key = str(sw.get("key", ""))
    if p.wick_sweep_depth and key.startswith("rel_eq"):
        ce = wick_ce_for(ctx, sd, sw["level"], i, p)
        if ce is None:
            hit("wick_depth_none")
            return "drop"                                  # "not every wick works": no wick to reach under this pool
        sw["wick_ce"] = ce
        hit("wick_depth")
    if p.shallow_sweep_wait and key.startswith("rel_eq"):
        sw["shallow"] = True
        sw["pending_drive"] = True
    if p.eq_hunt != "off" and eq_hunt_level(ctx, sd, i, p, key, sw["level"]):
        sw["eq_hunt"] = True
        hit("eq_hunt")
    if p.ts_age_rank != "off":
        sw["ts_age"] = pool_age(ctx, key)
    return None


def sweep_step(ctx, sd, sw, i: int, p):
    """Every bar of a live sweep before its order (strategy._scan_core, after the extreme update): None, "wait" (nothing is armed this bar) or "drop" (the sweep is void)."""
    tk = p.tick
    S = _S()
    ce = sw.get("wick_ce")
    if ce is not None:
        first, last, done, o, hh, ll, c = h1_buckets(ctx, sd)
        j = np.flatnonzero(done & (last <= i) & (last > sw.get("sweep_i", sw["ext_i"])))
        if len(j) and (c[j] < ce - MIN1).any():
            hit("wick_depth_cancel")
            return "drop"                                  # a 1h body closed under the wick's CE: the run is a real decline
        if sw["ext"] > ce + 2 * tk + MIN1:
            return "wait"                                  # the sweep has not reached the CE yet
    if sw.get("shallow"):
        if sw["level"] - sw["ext"] < p.shallow_ticks * tk - MIN1:
            hit("shallow_wait")
            return "wait"                                  # one more drive is still to come
        sw["shallow"] = False
        hit("shallow_cleared")
    if sw.get("broke") is None and sw.get("key") != "htf_array" and (p.sweep_max_linger or (p.ts_linger_bars and p.turtle_soup not in ("", "prev_pm"))):
        # [our interpretation] "lingers" = the COUNT of closes beyond the swept level since the sweep (not necessarily consecutive: a bounce and a re-break still mean it hung around)
        n = int(np.count_nonzero(sd.c[sw["sweep_i"]:i + 1] < sw["level"] - MIN1))
        if p.sweep_max_linger and n > p.sweep_max_linger:
            sw["ob_void"] = True                           # a pending OB order of this sweep dies with it
            S._f("x_linger")
            hit("sweep_linger")
            return "drop"
        if p.ts_linger_bars and p.turtle_soup not in ("", "prev_pm") and n > p.ts_linger_bars:      # review fix: "prev_pm" is a resting limit, not a sweep-driven turtle variant
            sw["ob_void"] = True                           # levels#141 "cancel the sweep" (review fix: the whole sweep, not only its turtle order): its pending OB order dies with it
            hit("ts_linger")
            return "drop"
    if sw.get("key") == "htf_array" and sd.c[i] < sw["arr_bot"] - tk:
        hit("premise_dead")
        return "drop"                                      # a body closed beyond the array: not a test of it
    return None


def premise_sweep(ctx, sd, i: int, p, session: str):
    """M1M2-htf-array-replaces-sweep (011 ~8:49; 082 ~4:45): with no pool taken, a bar whose extreme reaches (the near edge of) a same-side 15m / 60m array of the Confluence object
    (FVG / OB / VI) while its close stays inside / above it is a pseudo-sweep (key "htf_array"). Once per array per day. A new sweep dict or None."""
    S = _S()
    names = tuple(_arr_tf(m) for m in p.premise_tfs)
    kb = ctx.idx[i] + pd.Timedelta(minutes=ctx.tf)
    try:
        arrs = S._ts_arrays(ctx, sd, i, kb, names)
    except Exception:
        return None
    if not arrs or i < 1:
        return None
    sent = sd.__dict__.setdefault("_prem_sent", set())
    best = None
    for top, bot, kn in arrs:
        key = (round(float(top), 6), round(float(bot), 6))
        if key in sent or not (sd.l[i] <= top + MIN1 and sd.c[i] >= bot - MIN1 and sd.c[i - 1] > top):
            continue
        if best is None or top > best[0]:
            best = (float(top), float(bot), key)
    if best is None:
        return None
    sent.add(best[2])
    hit("premise_array")
    return dict(session=session, name="htf_array", level=best[0], key="htf_array", ext=float(sd.l[i]), ext_i=i, broke=None, sweep_i=i, smt=None, smt2=None,
                arr_bot=best[1], **{S._SM.SYNTH: True})


def stop_adjust(ctx, sd, sw, i: int, p, entry: float, stop: float, tags: dict) -> float:
    """Stops of this package (strategy._finish_order, before refine_stop): A23 - under min(sweep extreme, wick CE); eq_hunt - under the sweep extreme ("sweep" stop mode)."""
    ce = sw.get("wick_ce")
    if ce is not None:
        stop = min(stop, min(float(sw["ext"]), float(ce)) - p.pad)
    if sw.get("eq_hunt"):
        stop = min(stop, float(sw["ext"]) - p.pad)
    return stop


# --- row draws / locked draws ---------------------------------------------------------------------------------------------------------------------

DAILY_DRAWS = ("D_fvg", "W_fvg", "D_vi", "W_vi", "D_nwog", "D_ndog", "D_swing_high", "D_swing_low", "PDH", "PDL", "PWH", "PWL")
HTF_PIVOTS = ("D_swing_high", "D_swing_low", "PWH", "PWL", "PDH", "PDL")


def row_draw(ctx, sd, i: int, session: str):
    """The htf.table draw known at bar i in the trade's direction: (side-space price, name) or None."""
    from . import bias_day as BD
    row = BD.row_for(ctx, session, i)
    if row is None:
        return None
    v = row.get("draw_up" if sd.sign > 0 else "draw_dn")
    if v is None or v != v:
        return None
    nm = str(row.get("draw_up_name" if sd.sign > 0 else "draw_dn_name", ""))
    return float(sd.x(float(v))), nm


def htf_pivot_high(ctx, sd, i: int, session: str):
    """The untaken HTF pivot high above (side space): the locked draw when it is on this side, else the htf.table draw named D/W pivot / PDH / PWH; None when there is none or the day
    already traded it."""
    lk = getattr(ctx, "cur_lock_any", None) or getattr(ctx, "cur_lock", None)
    v = None
    if lk is not None and lk.get("side") == sd.sign:
        v = float(sd.x(lk["target"]))
    else:
        r = row_draw(ctx, sd, i, session)
        if r is not None and r[1] in HTF_PIVOTS:
            v = r[0]
    if v is None or v <= sd.c[i] or float(sd.h[ctx.start:i + 1].max()) >= v:
        return None
    return v


# --- A79: leg grading ---------------------------------------------------------------------------------------------------------------------------

def leg_grade(ctx, sd, sw, i: int, p, entry: float, session: str):
    """new-leg-grading-quadrants (061 ~2:07:40; 075 ~1:35:57): (grade 1..4, O, D) of the entry in the leg O -> D, or None without a draw. O = the sweep extreme (leg_origin "mss_low")
    or the day's low so far; D = the locked draw, else the htf.table draw. grade 0 = below O."""
    lk = getattr(ctx, "cur_lock", None)
    if lk is not None and lk.get("side") == sd.sign:
        D = float(sd.x(lk["target"]))
    else:
        r = row_draw(ctx, sd, i, session)
        D = None if r is None else r[0]
    if D is None:
        return None
    O = float(sw["ext"]) if p.leg_origin == "mss_low" else float(sd.l[ctx.start:i + 1].min())
    if D <= O:
        return None
    f = (entry - O) / (D - O)
    return (0 if f < 0 else min(4, int(f / 0.25) + 1), O, D)


# --- 158: REH / REL fade condition ---------------------------------------------------------------------------------------------------------------

def reh_fade_ok(ctx, sd, sw, i: int, p, session: str) -> bool:
    """A3 / LLT3-equal-highs-fade-condition (cc09_005 ~20:04), side space (a long sweeps REL; a short's REH is the mirror): (1) the order flow is this way and the sweep reached a same-side
    HTF array, or (2) the market is neutral and an HTF (1h+) array sits just beyond the pool (within ts_max_pts) - else the pool is a continuation target and the fade is not taken."""
    S = _S()
    cf = getattr(ctx, "conf", None)
    now = sm2.now_ts(ctx, i)
    w = _want(ctx)
    hit("reh_fade_gate")
    if cf is None:
        return True                                          # no arrays to read: the gate cannot say no
    if w == sd.sign:
        return bool(cf.at(now, sd.x(float(sw["ext"])), sd.sign))
    if w == 0:
        lv = float(sw["level"])
        kb = ctx.idx[sw["ext_i"]] + pd.Timedelta(minutes=ctx.tf)
        arrs = S._ts_arrays(ctx, sd, i, kb, ("1h", "4h", "D", "W"))
        return any(lv - p.ts_max_pts * p.es_pt - MIN1 <= top <= lv + p.eq_tol_pts * p.es_pt + MIN1 for top, bot, _ in arrs)
    return False


# --- 125: nearby untaken pool ---------------------------------------------------------------------------------------------------------------------

def near_pool(ctx, sd, sw, i: int, p, session: str, entry: float):
    """B1-nearby-unrun-high-trap (cc04_013 ~6:11): an untaken pool (a sell-side level in side space - for a short an untaken HIGH) within near_pool_adr x ADR5 BEYOND the entry that
    the setup's sweep did not take (it lies under the sweep extreme). The level or None."""
    S = _S()
    a5 = sm2.adr5(ctx)
    if not a5:
        return None
    x = p.near_pool_adr * a5
    tk = S._tick(p)
    best = None
    for k, v in S._sell_side(ctx, sd, session, i, p.extra_pools, p).items():
        if k in ("round",) or str(k).startswith("open_"):
            continue
        if v >= entry or entry - v > x + MIN1 or v >= sw["ext"] - MIN1:
            continue                                         # not within X below the entry / the sweep took it
        if not S._level_intact(ctx, sd.l, i + 1, k, v, session, tk):
            continue
        if best is None or v > best:
            best = v
    return best


# --- 92: prior-day range EQ long -----------------------------------------------------------------------------------------------------------------

def prev_range_eq(ctx, sd, i: int, p, entry: float):
    """new-prev-day-range-eq-long (076 ~20:09): after an expansion day that took a key high (the prior high beyond the day before's and the week before's) the range R = [prior 00:00
    open .. prior high]; longs (with the bias, review fix: `want == +1`) only at or below EQ(R); a Reaper (levels.reaper: an FVG in the discount half of the prior impulsive leg that price
    cut through) below EQ lowers the floor to its CE. The mirror runs on the mirrored Side. Needs ctx.prev_full (the prior day's 00:00 open; backtest passes it for prev_eq_long) - without
    it the gate is n/a (review fix: no fallback to the RTH open). Returns True (allowed) / False / None (n/a)."""
    hist = getattr(ctx, "hist", [])
    pf = getattr(ctx, "prev_full", None)
    if len(hist) < 2 or pf is None or not len(pf) or _want(ctx) != sd.sign:
        return None
    po, ph, pl = float(pf.open.iloc[0]), float(pf.high.max()), float(pf.low.min())
    pw = getattr(ctx, "pw", None)
    if sd.sign > 0:
        key_ref = max([float(hist[-2].high.max())] + ([float(pw[0])] if pw else []))
        took = ph > key_ref
        lo_r, hi_r = po, ph
    else:
        key_ref = min([float(hist[-2].low.min())] + ([float(pw[1])] if pw else []))
        took = pl < key_ref
        lo_r, hi_r = -po, -pl                                # mirrored: [open .. low] -> [-open .. -low]
    if not took or hi_r <= lo_r:
        return None
    eq = (lo_r + hi_r) / 2
    hit("prev_eq_long")
    if entry <= eq + MIN1:
        # a Reaper under EQ: the long may also not sit below its CE (support there) [our interpretation of "allow entries down to its CE"]
        z = prev_reaper(pf, sd.sign)
        if z is not None and z.mid < eq:
            return bool(entry >= z.mid - p.eq_tol_pts * p.es_pt - MIN1)
        return True
    return False


def prev_reaper(prev: pd.DataFrame, sign: int):
    """The Reaper of the prior session's impulsive leg (low a0 -> high hk, side space) by levels.reaper: the newest bullish FVG in the discount half of the leg that a later close (hk+1 ..
    the lowest low after the high) cut through. The Zone (.mid = its CE) or None."""
    if sign > 0:
        o, h, l, c = (prev[k].values.astype(float) for k in ("open", "high", "low", "close"))
    else:
        o, h, l, c = (-prev.open.values.astype(float), -prev.low.values.astype(float), -prev.high.values.astype(float), -prev.close.values.astype(float))
    if len(h) < 4:
        return None
    hk = int(np.argmax(h))
    if hk < 1 or hk >= len(h) - 1:
        return None
    a0 = int(np.argmin(l[:hk + 1]))
    ext_i = hk + 1 + int(np.argmin(l[hk + 1:]))
    return L.reaper(o, h, l, c, a0, hk, ext_i)


# --- 121: turning-level types -------------------------------------------------------------------------------------------------------------------

def turn_level_ok(ctx, sd, sw, tol: float, p) -> bool:
    """M1-turning-level-types (cc04_007 ~1:04): the sweep extreme sits at a support of one of the extra types in `mm_turn_types`: an old high (a 1h swing high or a prior-day high) now
    support / an old low / a liquidity void (a true gap) known by the extreme's bar."""
    S = _S()
    e, x = sw["ext_i"], float(sw["ext"])
    types = set(p.mm_turn_types)
    if "old_high" in types or "old_low" in types:
        ph, pl = S._SM._tf_pivots(ctx, sd, 60)
        if "old_high" in types and any(q.known <= e and abs(q.price - x) <= tol for q in ph if q.i < e):
            return True
        if "old_low" in types and any(q.known <= e and abs(q.price - x) <= tol for q in pl if q.i < e):
            return True
        daily = [sd.x(ctx.pd[k]) for k in ctx.pd if k.startswith("pdh" if sd.sign > 0 else "pdl")]
        if "old_high" in types and any(abs(v - x) <= tol for v in daily):
            return True
    if "void" in types:
        for z in L.voids(sd.h, sd.l):
            if z.kind == "bull" and z.i <= e and z.bottom - tol <= x <= z.top + tol:
                return True
    return False


# --- 4 / 101: breaker entries -------------------------------------------------------------------------------------------------------------------------

BREAKER_KINDS = ("breaker", "adv_breaker", "adv_breaker_pre", "cc_breaker_swing", "breaker_range", "reaper_ob", "arr_breaker")


def breaker_bounds(sd, tags: dict):
    """The (top, bottom) of the entry breaker in side space from the order's tags, or None."""
    if tags.get("bz_side") is not None:
        t, b = tags["bz_side"]
        return float(max(t, b)), float(min(t, b))
    if tags.get("bz_top") is not None and tags.get("bz_bottom") is not None:
        a, b = sd.x(float(tags["bz_top"])), sd.x(float(tags["bz_bottom"]))
        return float(max(a, b)), float(min(a, b))
    return None


def is_breaker_entry(tags: dict) -> bool:
    return bool(tags.get("entry_kind") in BREAKER_KINDS or tags.get("unicorn"))


def bias_draw_ok(ctx, sd, i: int, p, session: str, top: float) -> bool:
    """M4-accumulate-in-breaker-needs-bias-draw (007 ~21:34): the session bias is this way AND a specific draw above the zone was named before the entry (the locked draw, else the
    htf.table draw)."""
    if _want(ctx) != sd.sign:
        return False
    lk = getattr(ctx, "cur_lock_any", None)
    if lk is not None:                                       # review fix: once a session lock exists it IS the named draw - it must be this side's and above the zone
        return bool(lk.get("side") == sd.sign and sd.x(lk["target"]) > top)
    r = row_draw(ctx, sd, i, session)                        # no lock made (draw_lock off / before the lock time): the htf.table row draw
    return bool(r is not None and r[0] > top)


def breaker_taps(ctx, sd, sw, i: int, p, top: float, bottom: float):
    """X9-repeated-array-taps (048 ~32:51): (taps, window verdict). A tap = a bar after the MSS whose low enters the zone and whose NEXT closed bar closes above it. At tap
    `breaker_max_taps_for_entry` (2) a 2-bar window must trade above the nearest opposing FVG without a low under that tap's low (None = n/a, True / False)."""
    b = sw.get("broke")
    if b is None:
        return 0, None
    taps = []
    for j in range(b + 1, i):
        if sd.l[j] <= top + MIN1 and sd.c[j + 1] > top:
            taps.append(j)
    n = len(taps)
    if n != p.breaker_max_taps_for_entry:
        return n, None
    j2 = taps[-1]
    opp = [z for z in sd.opposing() if z.i <= i and z.bottom >= top - MIN1]
    if not opp:
        return n, True
    tgt = min(z.top for z in opp)
    w = range(j2 + 1, min(j2 + 3, i + 1))
    ok = any(sd.h[k] > tgt for k in w) and not (sd.l[j2 + 1:min(j2 + 3, i + 1)].min(initial=np.inf) < sd.l[j2] - MIN1)
    return n, bool(ok)


# --- 9: PM needs an HTF target ---------------------------------------------------------------------------------------------------------------------

def pm_htf_target_ok(ctx, sd, i: int, p, session: str, entry: float) -> bool:
    """M7-pm-1330-judas-full (010 ~57:47): an undelivered daily-level target lies beyond the entry in the trade's direction: the htf.table draw named as a daily level / daily FVG, or (review
    fix: "in htf.table arrays") any untouched daily pool (the prior days' extremes) or D / W array edge of the Confluence object (sm2.daily_beyond) - not yet traded today."""
    day_hi = float(sd.h[ctx.start:i + 1].max())
    r = row_draw(ctx, sd, i, session)
    if r is not None and r[1] in DAILY_DRAWS and r[0] > entry and day_hi < r[0]:
        return True
    if sm2.daily_beyond(ctx, sd, i, p, entry) is not None:
        return True
    cf = getattr(ctx, "conf", None)
    if cf is not None:
        for near, ce, far, tf, src in cf.opposing(sm2.now_ts(ctx, i), sd.x(entry), sd.sign, ("W",), (0,)):
            if sd.x(near) > entry and sd.x(near) > day_hi + MIN1:
                return True
    return False


def lunch_fvg_tops(ctx, sd, i: int, ref: float) -> list:
    """M7.3 pm_lunch_fvg_array: the tops of the alive 5m FVGs formed 12:00-13:30 (side space) beyond (under, for a long) the 13:30 open `ref`."""
    out = []
    try:
        zs = sd.zones_tf(ctx.idx, ctx.tf, 5)
    except Exception:
        return out
    for z in zs:
        if z.mt == z.mt:                                     # an order block, not an FVG
            continue
        if not (720 <= ctx.t[z.i] < 810) or z.i > i or z.top >= ref:
            continue                                         # (formed = completed by its third candle inside 12:00-13:30)
        if sd.c[z.i + 1:i].min(initial=np.inf) < z.bottom:
            continue                                         # closed through
        out.append(float(z.top))
    if out:
        hit("pm_lunch_fvg")
    return out


# --- order gate ---------------------------------------------------------------------------------------------------------------------------------

def order_gate3(ctx, sd, sw, i: int, p, entry: float, stop: float, session: str, lvt: list, lvx: dict, tags: dict):
    """Gates / tags of setups_models #3/7 at order completion (strategy._finish_order, after order_gate2). Returns a reject key or None."""
    S = _S()
    if p.ts_age_rank != "off" and sw.get("ts_age") is not None:
        lvt.append(f"ts_age_{int(sw['ts_age'])}")
        hit("ts_age")
    if sw.get("eq_hunt"):
        lvt.append("eq_hunt")
    if sw.get("key") == "htf_array":
        lvt.append("premise_array")
    if p.leg_grade_gate != "off":
        g = leg_grade(ctx, sd, sw, i, p, entry, session)
        if g is not None:
            hit("leg_grade")
            lvt.append(f"grade_q{g[0]}" if g[0] else "grade_below_origin")
            if p.leg_grade_gate == "require":
                O, D = g[1], g[2]
                if not (O - MIN1 <= entry <= O + (0.5 + p.leg_grade_tol) * (D - O) + MIN1):          # review fix: the allowed zone starts AT O (the tolerance widens only the 50% edge)
                    return "x_leg_grade"
                if "cancel_close" not in tags:
                    tags["cancel_close"] = float(O)          # a close under O cancels the pending long
    if p.near_pool_block:
        v = near_pool(ctx, sd, sw, i, p, session, entry)
        if v is not None:
            hit("near_pool")
            return "x_near_pool"
    if p.reh_fade_gate and str(sw.get("key", "")).startswith("rel_eq") and not reh_fade_ok(ctx, sd, sw, i, p, session):
        hit("reh_fade")
        return "x_reh_fade"
    if p.prev_eq_long:
        ok = prev_range_eq(ctx, sd, i, p, entry)
        if ok is False:
            return "x_prev_eq"
    if p.recap_ob_entry:
        # an untaken HTF pivot high (low) in the direction OPPOSITE to this order is an unfulfilled objective while the bias / the locked draw points at it (review fix: the locked draw counts):
        # the order against it is blocked while it stands. With neither a bias nor a lock naming the direction (both HTF pivots would block each other) - and always with unfulfilled_nearest
        # (the first build) - the objective is the nearer of the two htf.table draws.
        ot = sm2.other_side(ctx, sd)
        ho = htf_pivot_high(ctx, ot, i, session)
        if ho is not None:
            lka = getattr(ctx, "cur_lock_any", None)
            w = _want(ctx)
            if p.unfulfilled_nearest or not (w or (lka is not None and lka.get("side"))):
                r = row_draw(ctx, sd, i, session)                # no bias / lock names the objective's direction (or the first build): the nearer of the two HTF draws is the objective
                blk = r is None or ho - ot.c[i] < r[0] - sd.c[i]
            else:
                blk = w == ot.sign or (lka is not None and lka.get("side") == ot.sign)
            if blk:
                lvt.append("unfulfilled")
                hit("unfulfilled")
                return "x_unfulfilled"
    if p.breaker_need_bias_draw or p.breaker_max_taps_for_entry:
        bb = breaker_bounds(sd, tags) if is_breaker_entry(tags) else None
        if bb is not None:
            if p.breaker_need_bias_draw:
                ok = bias_draw_ok(ctx, sd, i, p, session, bb[0])
                tags["sm3"] = dict(tags.get("sm3") or {}, bd_ok=bool(ok))
                hit("breaker_bias_draw")
                if not ok and bb[1] - p.tick <= entry <= bb[0] + p.tick:
                    return "x_breaker_no_draw"            # an entry inside the breaker without the bias + a named draw beyond it
            if p.breaker_max_taps_for_entry:
                n, win = breaker_taps(ctx, sd, sw, i, p, bb[0], bb[1])
                hit("breaker_taps")
                if n >= p.breaker_max_taps_for_entry + 1:
                    lvt.append("breaker_worn")
                    return "x_breaker_worn"
                if win is False:
                    return "x_breaker_tap2"
    if p.pm_need_htf_target and session == "PM" and not pm_htf_target_ok(ctx, sd, i, p, session, entry):
        hit("pm_need_htf")
        return "x_pm_no_htf_target"
    return None


# --- extra (non-sweep) setups ---------------------------------------------------------------------------------------------------------------------

def extra3(ctx, sd, i: int, p, session: str, risk_mult: float):
    """The non-sweep setups of this chunk, tried when the sweep machine has nothing (strategy._scan)."""
    if p.vb_trade:
        o = vb_order(ctx, sd, i, p, session, risk_mult)
        if o is not None:
            return o
    if p.recap_ob_entry:
        o = recap_ob_order(ctx, sd, i, p, session, risk_mult)
        if o is not None:
            return o
    if p.ce_fail_entry:
        o = ce_fail_order(ctx, sd, i, p, session, risk_mult)
        if o is not None:
            return o
    if p.wk_high_proj:
        o = wk_proj_order(ctx, sd, i, p, session, risk_mult)
        if o is not None:
            return o
    return None


def any_extra3(p) -> bool:
    return bool(p.vb_trade or p.recap_ob_entry or p.ce_fail_entry or p.wk_high_proj)


def _synth(S, session: str, name: str, level: float, ext: float, ext_i: int, broke):
    return dict(session=session, name=name, level=float(level), key=name, ext=float(ext), ext_i=int(ext_i), broke=broke, sweep_i=int(ext_i), smt=None, smt2=None,
                **{S._SM.SYNTH: True})


# --- vacuum block trade (L8 123, 85) -----------------------------------------------------------------------------------------------------------------------

def vb_gaps(ctx, sd, p) -> list:
    """The bullish (side space) vacuum blocks of the day frame: bars k >= start whose open sits more than vb_min_gap_pts above the previous close. [(k, bottom=pre-gap close, top=open)]."""
    c = _c(ctx)
    key = ("vb", sd.sign, p.vb_min_gap_pts)
    if key not in c:
        out = []
        mg = p.vb_min_gap_pts * p.es_pt
        for k in range(max(ctx.start, 1), len(ctx.t)):
            if k == ctx.start and ctx.t[k] < 570:
                continue                                     # the frame's first bar after the prior RTH close: the evening is missing, not a gap
            z = L.vacuum_block(sd.o, sd.c, k, mg)
            if z is not None and z.kind == "bull":
                out.append((k, float(z.bottom), float(z.top)))
        c[key] = out
    return c[key]


def vb_order(ctx, sd, i: int, p, session: str, risk_mult: float):
    """L8-vacuum-block-trade (cc04_009 ~12:42) + new-vb-post-fill-management (~11:48, ~14:09), bullish terms: once a bar has filled the gap 100% (a low at or under the pre-gap close) and
    the close is back above it, a limit at the pre-gap close (the close of the last up candle before the gap), stop under the lowest low of the fill, T1 = the high formed at the gap opening
    (the gap bar .. the fill bar) + one tick, a runner to the next pool. Management (sm3.manage): vb_stall / vb_back."""
    S = _S()
    if p.vb_entry in ("partial", "full", "auto"):       # caption-gap L8-vacuum-block-entries (setups_models #6/7): the partial / full fill entries
        return S._SM6.vb_order6(ctx, sd, i, p, session, risk_mult)
    sent = sd.__dict__.setdefault("_vb_sent", set())
    for k, bot, top in vb_gaps(ctx, sd, p):
        if k > i - 1 or k in sent:
            continue
        seg = sd.l[k:i + 1]
        fl = np.flatnonzero(seg <= bot + MIN1)
        if not len(fl):
            continue
        j = k + int(fl[0])
        if sd.c[i] <= bot + MIN1:
            continue
        low = float(sd.l[j:i + 1].min())
        up = [x for x in range(k, j + 1) if sd.c[x] > sd.o[x]]
        cand_hi = float(sd.h[up[0]]) if up else float(sd.h[k])
        mkt = p.vb_entry == "close_above"
        if mkt:                                              # new-vb-target (123, cc04_009 ~12:42): a bar CLOSING above the first post-gap up candle after the fill -> market at that close
            if i <= j or not sd.c[i] > cand_hi + MIN1:
                continue
            entry = float(sd.c[i])
        else:                                                # new-vb-post-fill-management (85, ~11:48): the limit at the pre-gap close
            entry = bot
        stop = low - p.pad
        if entry - stop < p.min_risk_pts * p.es_pt:
            continue
        sent.add(k)
        hit("vb_trade")
        gh = float(sd.h[k:j + 1].max())
        fixed = [(S._exit_px(gh, "pool", p), "pool")]
        try:
            nx = [x for x in S._targets(ctx, sd, i, fixed[0][0], [], p, None, None) if x[1] in S.POOL_KINDS and x[0] > fixed[0][0] + p.es_pt]
        except Exception:
            nx = []
        if nx:
            fixed.append((S._exit_px(nx[0][0], "pool", p), "pool"))
        sw = _synth(S, session, "vb", bot, low, j, j)
        tags = dict(unicorn=False, fvg_bottom=low, fvg_ce=(entry + low) / 2, entry_kind="vb", mitigation=False, propulsion=False, no_leg_wait=True, market=mkt,
                    skip_po3=not p.synth_po3, lv_tags=["vb_trade"], sm3=dict(vb=dict(hi=cand_hi, pre=float(bot), stall=0, reached=False, above=False, traded_above=False, back=0, back_c=None, done_stall=False)))
        return S._finish_order(ctx, sd, i, p, session, sw, entry, stop, risk_mult, float(sd.h[j:i + 1].max()), tags, skip_leg_pd=True, fixed=fixed)
    return None


# --- recapitalized OB (111) ------------------------------------------------------------------------------------------------------------------------

def recap_ob_order(ctx, sd, i: int, p, session: str, risk_mult: float):
    """new-retrace-to-recapitalized-ob (cc03_003 ~38:17): bias this way, an untaken HTF pivot high H above, an intermediate pool above swept today and price retracing: a limit at the open
    of the most recent reclaimed bullish OB under the close, stop under its low, target H."""
    S = _S()
    if _want(ctx) != sd.sign:
        return None
    H = htf_pivot_high(ctx, sd, i, session)
    if H is None:
        return None
    pools = [sd.x(ctx.pd[k]) for k in ctx.pd if k.startswith("pdh" if sd.sign > 0 else "pdl")]
    if "pmh" in ctx.pd and sd.sign > 0:
        pools.append(float(ctx.pd["pmh"]))
    elif "pml" in ctx.pd and sd.sign < 0:
        pools.append(float(sd.x(ctx.pd["pml"])))
    for nm in ("london", "prev_pm"):
        if nm in ctx.sess:
            hi, lo, _ = ctx.sess[nm]
            pools.append(float(sd.x(hi if sd.sign > 0 else lo)))
    pools = [v for v in pools if v < H]
    hi_day = sd.h[ctx.start:i + 1]
    swept = [v for v in pools if (hi_day > v + MIN1).any()]
    if not swept:
        return None
    j_sw = ctx.start + int(np.flatnonzero(hi_day > max(swept) + MIN1)[0])         # the bar that took the highest intermediate pool
    top_so_far = float(sd.h[j_sw:i + 1].max())
    if not sd.c[i] < top_so_far - p.tick:
        return None
    e = ctx.start + int(np.argmin(sd.l[ctx.start:j_sw + 1]))
    zs = sm2.reclaimed_zones(sd, ctx.start, e, i, p)
    sent = sd.__dict__.setdefault("_recap_sent", set())
    zs = [z for z in zs if z.i <= i and (z.i, z.src) not in sent and z.top < sd.c[i] and sd.c[z.i + 1:i + 1].min(initial=np.inf) >= z.bottom - MIN1]
    if not zs:
        return None
    z = max(zs, key=lambda z: (z.i, z.src))
    entry = min(float(z.top), max(float(z.bottom), float(sd.o[z.src])))
    if entry >= sd.c[i]:
        return None
    stop = float(z.bottom) - p.pad
    sent.add((z.i, z.src))
    hit("recap_ob")
    fixed = [(S._exit_px(H, "pool", p), "pool")]
    sw = _synth(S, session, "recap_ob", z.top, z.bottom, z.src, z.i)
    tags = dict(unicorn=False, fvg_bottom=float(z.bottom), fvg_ce=float((entry + z.bottom) / 2), entry_kind="recap_ob", mitigation=False, propulsion=False, no_leg_wait=True,
                skip_po3=not p.synth_po3, lv_tags=["recap_ob"])
    return S._finish_order(ctx, sd, i, p, session, sw, entry, stop, risk_mult, top_so_far, tags, skip_leg_pd=True, fixed=fixed)


# --- sell model: the candle that fails to reach the CE (M1 5) -------------------------------------------------------------------------------------------

def mss_breaks(ctx, sd, a: int, i: int) -> list:
    """The market-structure breaks of the leg that started at the low bar `a` (side space): each close above a swing high that formed after `a` and had not been broken, in time order [bar]."""
    out, used = [], set()
    ph = [q for q in sd.ph if q.i > a and q.known <= i]
    for j in range(a + 1, i + 1):
        for q in ph:
            if q.i < j and q.known <= j and q.i not in used and sd.c[j] > q.price:
                used.add(q.i)
                out.append(j)
                break
    return out


def ce_fail_order(ctx, sd, i: int, p, session: str, risk_mult: float):
    """M1-sell-model-fail-to-reach-CE (007 ~20:36), side space (the source is the sell model; a long mirrors it): (1) the leg started inside a same-side HTF (1h+) array when a Confluence
    object exists, (2) two market-structure breaks followed, (3) on the next pullback into the last imbalance (BISI) of the leg the first candle whose low enters it but stays above its CE
    and closes up is the entry, at market on that candle (fill = the next open); stop under the BISI + pad (E6)."""
    S = _S()
    if i < ctx.start + 6:
        return None
    a = ctx.start + int(np.argmin(sd.l[ctx.start:i + 1]))
    br = mss_breaks(ctx, sd, a, i)
    if len(br) < 2:
        return None
    cf = getattr(ctx, "conf", None)
    if cf is not None:
        now = sm2.now_ts(ctx, a)
        tfs = [t_ for t_ in cf.at(now, sd.x(float(sd.l[a])), sd.sign) if t_ in ("1h", "4h", "D", "W", "M")]
        if not tfs:
            return None
    gs = [g for g in sd.gaps if a < g.i - 2 and g.i <= br[1] + 3 and g.i < i]
    if not gs:
        return None
    g = gs[-1]
    sent = sd.__dict__.setdefault("_cef_sent", set())
    if g.i in sent or i <= br[1]:
        return None
    if sd.c[g.i + 1:i].min(initial=np.inf) < g.bottom:                     # closed through: no longer the imbalance
        return None
    if not (sd.l[i] < g.top - MIN1 and sd.l[i] > g.mid + MIN1 and sd.c[i] > sd.o[i] and sd.c[i - 1] >= g.top - MIN1):
        return None
    sent.add(g.i)
    hit("ce_fail")
    entry, stop = float(sd.c[i]), float(g.bottom) - p.pad
    sw = _synth(S, session, "ce_fail", g.top, sd.l[a], a, br[1])
    tags = dict(unicorn=False, fvg_bottom=float(g.bottom), fvg_ce=float(g.mid), entry_kind="ce_fail", mitigation=False, propulsion=False, no_leg_wait=True, market=True,
                skip_po3=not p.synth_po3, lv_tags=["ce_fail"])
    return S._finish_order(ctx, sd, i, p, session, sw, entry, stop, risk_mult, float(sd.h[a:i + 1].max()), tags, skip_leg_pd=True)


# --- Monday weekly-high projection (L13 137) --------------------------------------------------------------------------------------------------------------

def wk_proj_levels(ctx, sign: int, p):
    """L13-weekly-high-london-swing (cc07_008 ~30:29), real prices: Monday of a bearish week (sign -1): L = the London high (02:00-05:00), R = the lowest low from 05:00 to 09:30;
    levels L + k (L - R). The bullish week mirrors it. [(k, level)] or [] (known from 09:30)."""
    c_ = _c(ctx)
    key = ("wkp", sign, tuple(p.wk_proj_k))
    if key in c_:
        return c_[key]
    t = ctx.t
    s = ctx.start
    kl = [j for j in range(s, len(t)) if 120 <= t[j] < 300]
    kr = [j for j in range(s, len(t)) if 300 <= t[j] < 570]
    out = []
    if kl and kr:
        if sign < 0:
            L_, R_ = float(ctx.h[kl].max()), float(ctx.l[kr].min())
            out = [(k, L_ + k * (L_ - R_)) for k in p.wk_proj_k] if L_ > R_ else []
        else:
            L_, R_ = float(ctx.l[kl].min()), float(ctx.h[kr].max())
            out = [(k, L_ - k * (R_ - L_)) for k in p.wk_proj_k] if R_ > L_ else []
    if kr and ctx.t[-1] >= 570:
        c_[key] = out                                      # (only cached once the 09:30 bar exists: the range 05:00-09:30 is complete)
    return out


def week_dir(ctx, i: int, session: str) -> int:
    """The week's direction on a MONDAY [our interpretation of "weekly_bias -1" of the spec: strategy.weekly_bias reads only EARLIER days of the same week, so it is always 0 on Monday]: the
    htf.table weekly reading (`wk_bias`, built with weekly_gate / weekly_open / htf_bias "wk") known at bar i; falls back to ctx.wbias."""
    w = int(getattr(ctx, "wbias", 0) or 0)
    if w:
        return w
    from . import bias_day as BD
    row = BD.row_for(ctx, session, i)
    if row is None:
        return 0
    try:
        v = row.get("wk_bias")
    except Exception:
        return 0
    return 0 if v is None or v != v else int(np.sign(v))


def wk_proj_order(ctx, sd, i: int, p, session: str, risk_mult: float):
    """L13 wk_high_proj: Monday, weekly bias with this side, from 09:30: a projected level within 1 point of a weekly array (the weekly bearish OB / FVG for a short) becomes a limit
    shaded one tick toward price, stop beyond the array, `wk_proj_size` x the normal risk (the Monday partial)."""
    S = _S()
    if ctx.day.weekday() != 0 or ctx.t[i] < 570 or ctx.t[i] >= 960 or week_dir(ctx, i, session) != sd.sign:
        return None
    hit("wk_proj_eval")
    sent = sd.__dict__.setdefault("_wkp_sent", set())
    kb = ctx.idx[i] + pd.Timedelta(minutes=ctx.tf)
    arrs = S._ts_arrays(ctx, sd, i, kb, ("W",), (0, 1, 3))
    if not arrs:
        return None
    for k, lv in wk_proj_levels(ctx, sd.sign, p):
        x = float(sd.x(lv))
        for top, bot, _ in arrs:
            if bot - p.es_pt - MIN1 <= x <= top + p.es_pt + MIN1 and (k, round(x, 4)) not in sent:
                entry = x + p.tick                                  # shaded one tick toward price
                if not entry < sd.c[i]:
                    continue
                stop = float(bot) - p.pad
                if entry - stop < p.min_risk_pts * p.es_pt:
                    continue
                sent.add((k, round(x, 4)))
                hit("wk_proj")
                sw = _synth(S, session, "wk_proj", x, bot, i, i)
                tags = dict(unicorn=False, fvg_bottom=float(bot), fvg_ce=float((entry + bot) / 2), entry_kind="wk_proj", mitigation=False, propulsion=False, no_leg_wait=True,
                            skip_po3=True, lv_tags=[f"wk_proj_{k}"])
                return S._finish_order(ctx, sd, i, p, session, sw, entry, stop, risk_mult * p.wk_proj_size, float(sd.h[ctx.start:i + 1].max()), tags, skip_leg_pd=True)
    return None


# --- raid-level roll (L2 124) ----------------------------------------------------------------------------------------------------------------------

def rolled_raid(ctx, sd, i: int, p, lv: dict, session: str):
    """L2-raid-level-rolls (cc04_011 ~13:57), side space: for a raid level (an old-low pool: pdl* / pdh*) that already traded WITHOUT a 15m MSS (no 15m close above the last 15m pivot
    high since), the raid level rolls to the newest confirmed 15m pivot low formed under it. Returns (key, level) of the current raid or None; the cc_limit places its limit under it
    and takes no entry above."""
    S = _S()
    ph, pl = S._SM._tf_pivots(ctx, sd, 15)
    best = None
    tk = S._tick(p)
    for k, v in lv.items():
        if not str(k).startswith(("pdl", "pdh")) or S._level_intact(ctx, sd.l, i + 1, k, v, session, tk):
            continue                                         # not an old-low pool / not traded yet: the plain raid level
        seg = np.flatnonzero(sd.l[ctx.start:i + 1] < v - MIN1)
        if not len(seg):
            continue
        j0 = ctx.start + int(seg[0])
        hs = [q for q in ph if q.known <= i and q.i < j0]
        if hs and (sd.c[j0:i + 1] > hs[-1].price).any():
            continue                                         # a real reversal (a 15m MSS): the level does not roll
        lows = [q for q in pl if j0 <= q.i and q.known <= i and q.price < v]
        if not lows:
            continue
        cand = float(lows[-1].price)
        if best is None or cand > best[1]:
            best = (str(k) + "_roll", cand)
    return best


# --- ORG entries on later days (L7 82) ----------------------------------------------------------------------------------------------------------------

def org_cands(ctx, sd, sw, i: int, p, out: list) -> list:
    """L7-org-later-day-entry-array (080 ~13:20; 092 ~1:59:32): entry candidates (entry, bottom, kind) from the UNFILLED part of each prior day's ORG: its high (the near edge), the upper
    quadrant (75%) and the CE, side space, when the bias agrees and the bar's minute lies in `org_entry_windows`; with org_entry_confl another array (an alive FVG or an `out` entry)
    within org_confl_ticks of the level is required."""
    t = int(ctx.t[i])
    if _want(ctx) != sd.sign or not any(a <= t < b for a, b in p.org_entry_windows):
        return []
    orgs = ctx.org[:-1] if getattr(ctx, "org_today", False) else ctx.org
    dates = (ctx.org_dates[:-1] if getattr(ctx, "org_today", False) else ctx.org_dates) if getattr(ctx, "org_dates", None) else [None] * len(orgs)
    hist = list(getattr(ctx, "hist", []))
    tol = p.org_confl_ticks * p.tick
    res = []
    hit("org_eval")
    for (pc, op), d in zip(orgs[-5:], dates[-5:]):
        glo, ghi = sorted((float(sd.x(pc)), float(sd.x(op))))
        later = [x for x in hist if d is None or x.index[0].date() >= d]
        if sd.sign > 0:
            ext_real = min([float(x.low.min()) for x in later] + [float(ctx.l[ctx.start:i + 1].min())])
        else:
            ext_real = max([float(x.high.max()) for x in later] + [float(ctx.h[ctx.start:i + 1].max())])
        tp = min(ghi, float(sd.x(ext_real)))
        if tp <= glo + MIN1:
            continue                                         # filled
        for v in (tp, glo + 0.75 * (tp - glo), (glo + tp) / 2):
            if p.org_entry_confl:
                alive = [g for g in sd.gaps if g.i <= i and g.bottom - tol <= v <= g.top + tol and sd.c[g.i + 1:i + 1].min(initial=np.inf) >= g.bottom]
                near_out = [x for x in out if abs(x[0] - v) <= tol or x[1] - tol <= v <= x[0] + tol]
                if not alive and not near_out:
                    continue
                hit("org_confl")
            hit("org_cand")
            res.append((float(v), float(glo), "org"))
    return res


# --- expansion CE entry (M1 8) ----------------------------------------------------------------------------------------------------------------------

DAILY_LOCK_NAMES = ("pdh", "pdl", "pwh", "pwl", "htf_PDH", "htf_PDL", "htf_PWH", "htf_PWL", "htf_D_swing", "pmonth_h", "pmonth_l")
# review fix: the month pools are "pmonth_h" / "pmonth_l" (mark_levels); "pmh" / "pml" are the PRE-market high / low (not daily levels - dropped). Daily gap / VI draws (htf_D_fvg ...) are arrays, not
# "one level": excluded on purpose.


def single_expansion(ctx, p, i: int) -> bool:
    """M1-inside-fvg-expansion-only (009 ~3:49) [our interpretation]: the session lock is ONE daily level (an old close / high / low, not an array) within ADR5 of the 09:30 open."""
    lk = getattr(ctx, "cur_lock", None)
    if lk is None or not lk.get("side"):
        return False
    nm = str(lk.get("name", ""))
    if not nm.startswith(DAILY_LOCK_NAMES):
        return False
    a5 = sm2.adr5(ctx)
    o0 = _S()._open_known(ctx, "0930", i)                    # review fix: the 09:30 open only once its bar is in (an order completed before it cannot read it)
    if not a5 or o0 is None:
        return False
    return bool(abs(float(lk["target"]) - float(o0)) <= a5)


# --- ladders -------------------------------------------------------------------------------------------------------------------------------------

def ss_ladder(tg: list, p) -> list:
    """M16-sick-sister-exit-ladder (053 ~6:21), side space: T1 = just above the nearer untaken high, T2 = the midpoint of the nearer and the farther highs; the farther high is no rung."""
    S = _S()
    tg = sorted(tg)
    t1 = (S._exit_px(tg[0], "pool", p), "pool")
    if len(tg) == 1:
        return [t1]
    return [t1, ((tg[0] + tg[-1]) / 2, "exact")]


def ss_fracs(n: int, p) -> tuple:
    return (1.0,) if n == 1 else (p.ss_t1_frac, 1.0 - p.ss_t1_frac)


def md_far_edge(sign: int, z) -> float:
    """M15-ma-deuce-ladder: the daily BISI's far edge in side space (the low of a bullish gap for a short)."""
    hit("ma_deuce_far")
    return float(sign * (z.bottom if sign < 0 else z.top))


def tgif_draw_ok(ctx, sd, i: int, p, session: str) -> bool:
    """M14-tgif-draw-hit-first-sd-depth (070 ~50:36): Friday has traded to the named weekly draw before the entry bar - the htf.table draw on the far side of the move (a TGIF short fades
    the week HIGH: the draw above) has been touched by a bar that closed by i."""
    ot = sm2.other_side(ctx, sd)
    r = row_draw(ctx, ot, i, session)
    hit("tgif_draw")
    if r is None:
        return False
    return bool(float(ot.h[ctx.start:i + 1].max()) >= r[0] - MIN1)


def tgif_sd_level(ctx, sd, i: int, p, entry: float):
    """M14 / L13 (070 ~50:36-53:43): the first (side-space) breaker formed after the Friday extreme (the side's day low = the real week high for a short) with zone top A and bottom B; the
    level A + k (A - B), k = 1, 2, that lies inside an EARLIER opposing breaker or FVG (Confluence arrays included) is the final rung; the first such level wins. None otherwise."""
    S = _S()
    a = ctx.start
    ext_i = a + int(np.argmin(sd.l[a:i + 1]))
    brk = [z for z in L.breakers(sd.o, sd.h, sd.l, sd.c, max(p.pivot_n, 1)) if z.kind == "bull" and ext_i < z.i <= i]
    if not brk:
        return None
    z0 = min(brk, key=lambda z: z.i)
    A, B = float(z0.top), float(z0.bottom)
    if A <= B:
        return None
    hit("tgif_sd_eval")
    opp = [(zz.bottom, zz.top) for zz in sd.opposing() if zz.i < z0.i and sd.c[zz.i + 1:i + 1].max(initial=-np.inf) <= zz.top]
    opp += [(zz.bottom, zz.top) for zz in S._TP.matrix_breakers(sd, p) if zz.i < z0.i]
    cf = getattr(ctx, "conf", None)
    if cf is not None:
        now = sm2.now_ts(ctx, i)
        for t_, b_, *_ in cf.valid(now, -sd.sign, ("15m", "1h", "4h", "D"), (0, 1)):
            x1, x2 = sd.x(t_), sd.x(b_)
            opp.append((min(x1, x2), max(x1, x2)))
    for k in (1, 2):
        lv = A + k * (A - B)
        if lv > entry and any(lo - MIN1 <= lv <= hi + MIN1 for lo, hi in opp):
            hit("tgif_sd")
            return float(lv)
    return None


# --- last hour draw freeze (M5 1) ------------------------------------------------------------------------------------------------------------------

def lh_frozen(ctx, p, s_: str, lk: dict) -> dict:
    """M5-lasthour-draw-frozen-noon (001 ~28:39): the LH slot's lock is made at lh_freeze_t (12:00): the AM lock while it stands (not delivered), else the noon mark-up that strategy
    _lock_step made. The draw is never re-picked at 15:00."""
    if s_ != "LH" or not p.lh_draw_freeze:
        return lk
    am = ctx.lock.get("AM")
    if am is not None and am.get("side") and not am.get("delivered"):
        hit("lh_freeze_am")
        return dict(am, session="LH", traded=False, delivered=False)
    hit("lh_freeze")
    return lk


# --- 2: three entry plans --------------------------------------------------------------------------------------------------------------------------

def mm_plan_exit(p, keep: list, eq_hi: list, entry: float, risk: float, draw: float):
    """M1-three-entry-plans (003 ~1:28:27): returns (single_exit?, draw, keep) for the plan: "full" - one exit at the draw; "mss_scalp" - one exit at the first relative equal highs above
    (just beyond); "pyramid" - the rungs are the pools."""
    S = _S()
    hit("mm_plan_" + p.mm_plan)
    if p.mm_plan == "full":
        return True, draw, keep
    if p.mm_plan == "mss_scalp":
        cand = [x for x in eq_hi if x - entry >= p.min_rr * risk]
        if cand:
            return True, S._exit_px(min(cand), "pool", p), keep
        return False, draw, keep
    if p.mm_plan == "pyramid":
        pk = [(v, k) for v, k in keep if k in S.POOL_KINDS]
        return False, draw, (pk or keep)
    return False, draw, keep


# --- management (run_day) ---------------------------------------------------------------------------------------------------------------------------

def _part(sd, pos, tr, ts, price_s: float, frac: float, reason: str, p, all_: bool = False) -> None:
    S = _S()
    left = pos["left"]
    q = left if all_ else min(left, max(p.lot, S._lots(left * frac, p.lot)))
    if q <= 0:
        return
    tr.exits.append((ts, sd.x(price_s), q, reason))
    pos["left"] -= q


def manage(ctx, sd, pos, tr, i: int, ts, p) -> None:
    """Per-bar management of the positions this package tagged (pos["sm3"]): vacuum block stall / back, counter-scalp midnight open, the immediate-rebalance acceleration hold."""
    st = pos.get("sm3")
    if not st or i <= pos["fill_i"] or not pos["left"]:
        return
    o, h, l, c = float(sd.o[i]), float(sd.h[i]), float(sd.l[i]), float(sd.c[i])
    v = st.get("vb")
    if v is not None:
        if h > v["hi"] + MIN1:
            v["traded_above"] = True
        if not v["done_stall"] and not v["above"]:
            if h >= v["hi"] - MIN1:
                v["reached"] = True
            if v["reached"]:
                if c > v["hi"] + MIN1:
                    v["above"] = True
                    v["stall"] = 0
                else:
                    v["stall"] += 1
                    if v["stall"] >= 2:
                        _part(sd, pos, tr, ts, c, 0.5, "vb_stall", p)
                        v["done_stall"] = True
                        hit("vb_stall")
        if pos["left"] and v["traded_above"] and c < v["pre"] - MIN1:
            if p.vb_back_full:                               # 123: "exit fully" on the first close back under the pre-gap close (85 = the two-step partial / full)
                _part(sd, pos, tr, ts, c, 1.0, "vb_back_full", p, all_=True)
                hit("vb_back_full")
            elif v["back"] == 0:
                _part(sd, pos, tr, ts, c, 0.5, "vb_back", p)
                v["back"], v["back_c"] = 1, c
                hit("vb_back")
            elif v["back_c"] is not None and c < v["back_c"] - MIN1:
                _part(sd, pos, tr, ts, c, 1.0, "vb_back2", p, all_=True)
                hit("vb_back2")
        if not pos["left"]:
            return
    x = st.get("counter_mo")
    if x is not None and h >= x - MIN1:
        _part(sd, pos, tr, ts, max(o, x), 1.0, "counter_mo", p, all_=True)
        hit("counter_mo")
        return
    if st.get("ir_accel") and not st.get("ir_done") and pos["k"] >= 1 and pos["last_partial_i"] == i:
        st["ir_done"] = True
        a = max(ctx.start - 1, 0, i - 20)
        rng = sd.h[a:i] - sd.l[a:i]
        if len(rng) >= 5 and (h - l) < 1.5 * float(np.median(rng)) - MIN1:
            _part(sd, pos, tr, ts, c, 1.0, "ir_decel", p, all_=True)
            hit("ir_decel")


def after_close(pos, tr, done: dict) -> None:
    """A15-mitigation-block-targets: the session is done after the final rung filled (mb_done_at_htf)."""
    st = pos.get("sm3")
    if st and st.get("mb_done") and tr.final_hit:
        done[pos.get("done_key", tr.session)] = True
        hit("mb_done")


def ir_rungs(ctx, sd, i: int, p, entry: float, levels: list, kinds: list):
    """M11 ir_accel_hold: the first rung = just beyond the nearest pivot (side space, above the entry), the second = the existing first target; None when the pivot is not usable."""
    S = _S()
    cand = [q.price for q in sd.ph if q.known <= i and q.price > entry + MIN1]
    if not cand:
        return None
    r1 = S._exit_px(min(cand), "pool", p)
    rest = [(v, k) for v, k in zip(levels, kinds) if v > r1 + p.es_pt]
    if not rest:
        return [r1], ["pool"]
    return [r1, rest[0][0]], ["pool", rest[0][1]]


# --- pre-open breaker for the unicorn (M4 3) -----------------------------------------------------------------------------------------------------------

def preopen_zone(ctx, sd, i: int, p):
    """M4-unicorn-sequence-preopen-breaker (007 ~15:27, ~11:34): the most recent bullish (side space) breaker on the 5m bars that closed before 09:30, the zone from levels.breaker_zone
    (the candle's range); None when there is none. The 5m bars are built from the base bars in front of 09:30 only, so nothing after the open is read."""
    S = _S()
    c = _c(ctx)
    key = ("pre", sd.sign, p.breaker_zone, p.pivot_n)
    if key in c:
        return c[key]
    k0 = S._idx_at(ctx, 570)
    z = None
    if k0 > ctx.start + 12 and k0 <= len(ctx.t):
        idx = ctx.idx[:k0]
        b = pd.Series(np.arange(len(idx)), index=idx).groupby(idx.floor("5min"))
        first, last = b.min().values, b.max().values
        done = np.asarray((idx[last] - b.min().index) >= pd.Timedelta(minutes=5 - ctx.tf))
        first, last = first[done], last[done]
        o5 = np.array([sd.o[a] for a in first])
        c5 = np.array([sd.c[q] for q in last])
        h5 = np.array([sd.h[a:q + 1].max() for a, q in zip(first, last)])
        l5 = np.array([sd.l[a:q + 1].min() for a, q in zip(first, last)])
        zs = [q for q in L.breakers(o5, h5, l5, c5, max(p.pivot_n, 1), p.breaker_zone) if q.kind == "bull"]
        if zs:
            z = max(zs, key=lambda q: q.i)
    c[key] = z
    return z


def preopen_unicorn(ctx, sd, sw, i: int, p, fresh: list):
    """The pre-open sequence (007 ~11:34 "takes out the sell side here then comes back inside the breaker"): (zone, unicorn gaps). The sweep extreme (at / after 09:30) lies under the
    zone, a bar trades back into the zone within `unicorn_back_bars` of the extreme, and only gaps formed from then on that overlap the zone arm. ([], None) when any step fails."""
    z = preopen_zone(ctx, sd, i, p)
    if z is None:
        return None, []
    e = sw["ext_i"]
    if not (sw["level"] <= z.bottom + p.eq_tol_pts * p.es_pt and sw["ext"] < z.bottom + MIN1):
        return z, []
    seg = np.flatnonzero(sd.h[e + 1:min(i, e + p.unicorn_back_bars) + 1] >= z.bottom - MIN1)
    if not len(seg):
        return z, []
    j = e + 1 + int(seg[0])
    hit("unicorn_preopen")
    return z, [g for g in fresh if g.overlaps(z) and g.i >= j]


# --- mitigation block targets (A15 82) / lunch raid (174) ----------------------------------------------------------------------------------------------

def htf_level_beyond(ctx, sd, i: int, p, entry: float, session: str, above: float):
    """A15-mitigation-block-targets (cc04_004 ~8:13): the nearest HTF level beyond `above` in the trade's direction (side space): the daily pools / arrays of sm2.daily_beyond, the 4h / D / W
    PD arrays (FVG and OB near edges) of the Confluence object and the htf.table draw. None when there is none."""
    cands = []
    v = sm2.daily_beyond(ctx, sd, i, p, entry)
    if v is not None:
        cands.append(float(v))
    cf = getattr(ctx, "conf", None)
    if cf is not None:
        for near, ce, far, tf, src in cf.opposing(sm2.now_ts(ctx, i), sd.x(entry), sd.sign, ("4h", "D", "W"), (0, 1)):
            cands.append(float(sd.x(near)))
    r = row_draw(ctx, sd, i, session)
    if r is not None:
        cands.append(r[0])
    day_hi = float(sd.h[ctx.start:i + 1].max())
    cands = [x for x in cands if x > above + MIN1 and x > entry and x > day_hi + MIN1]
    return min(cands) if cands else None


def lunch_not_target(ctx, sd) -> bool:
    """LLT3-lunch-hl-raid-not-target (cc10_013 ~1:50): in the PM with a bias, the lunch extreme this (counter) side would target is the raid pool of the biased move - it leaves the ladder."""
    w = _want(ctx)
    hit("pm_lunch_raid_eval")
    r = bool(w and sd.sign == -w and getattr(ctx, "cur_session", "") == "PM")
    if r:
        hit("pm_lunch_raid")
    return r
