"""Caption-gap pass (digests/rulebook_gaps/*.md), package entries_stops_sizing, chunk 1 of 3: the engine glue of its 35 specs - bias_htf_intermarket.md items 118, 196;
definitions_pd_arrays_structure.md items 4, 7, 9, 11, 14, 23, 26, 34, 39, 42, 44, 45, 55, 59, 76-79, 84, 87-89, 92, 97, 100, 102, 109, 129-132, 136, 141.

Same conventions as sm2.py ... sm7.py: side space (shorts run mirrored prices), a bar is used only after it closes (`i` = the last CLOSED bar, an order armed on it fills from bar i+1), an object only
from the bar that completes it, daily / weekly objects only after their session closes (everything reads `ctx.hist`, the COMPLETED prior sessions, plus today's bars through the bar being judged).
Every function sits behind a Params switch of the "caption-gap pass, entries_stops_sizing #1/3" block; interpretations the sources do not pin down are marked [our interpretation]. `HITS` is sm2's
counter dict (tests: proof that a switch's code path RAN).

Sections: 1 mean threshold (D4 / A12) - 2 OB entries (A12) - 3 FVG entries (A5 / A21 / E2 / A15 / A16) - 4 the P/D frames (A21 / B5) - 5 OTE (M13) - 6 breakers / adds / tags - 7 position hooks.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import levels as L
from . import sm2, sm4, sm6

HITS = sm2.HITS
hit = sm2.hit
MIN1 = 1e-9


def _S():
    from . import strategy as S
    return S


def _tol(p) -> float:
    return p.eq_tol_pts * p.es_pt


def _want(ctx) -> int:
    return sm2.want(ctx)


def _es(o: dict | None) -> dict:
    return (o or {}).get("es1") or {}


# --- 1. the mean threshold (D4-mt-source-tally 11, A12-ltf-ob-upper-half 136) -------------------------------------------------------------------------

def _multi_zone(sd, ob) -> bool:
    """A blended OB Zone (src = the first candle of the run) spans more than one candle."""
    k = int(ob.src) + 1
    return bool(k <= ob.i and k < len(sd.c) and sd.c[k] < sd.o[k])


def mt_of(p, sd, ob) -> float:
    """The MT of an OB Zone by Params.mt_mode (D4; cc04_013 ~07:02, 065A ~40:00 / ~1:21 / ~1:39): "body" the body mean (Zone.mt), "range" 50 % of the high-low, "sensitive" (high + open) / 2 of the first
    candle's open, "body_single_range_blended" the body mean for a single candle and the range mid for a multi-candle block."""
    m = p.mt_mode
    if m == "range":
        return float(ob.mid)
    if m == "sensitive":
        return float((ob.top + sd.o[ob.src]) / 2)
    if m == "body_single_range_blended":
        return float(ob.mid if _multi_zone(sd, ob) else ob.mt)
    return float(ob.mt)


def dict_mt(p, sd, ob: dict, default: float) -> float:
    """The same for an OB dict of strategy._ob_at_low (j = the first candle of the run, k = the last). The built "range" value is left as it was for this path (the dict MT was always the body mean)."""
    if p.mt_mode == "sensitive":
        return float((ob["hi"] + sd.o[ob["j"]]) / 2)
    if p.mt_mode == "body_single_range_blended":
        return float((ob["hi"] + ob["lo"]) / 2) if ob["j"] < ob["k"] else float(default)
    return float(default)


def candle_mt(p, o: float, h: float, l: float, c: float) -> float:
    """The MT of ONE candle by mt_mode (the leg candle, the breaker's last 1m candle)."""
    if p.mt_mode == "range":
        return float((h + l) / 2)
    if p.mt_mode == "sensitive":
        return float((h + o) / 2)
    return float((o + c) / 2)


def zone_dict(sd, ob) -> dict:
    """An OB Zone (levels.order_block_blend: src = the first candle of the run, i = the window end) in the dict form of strategy._ob_at_low: j / k = the first / last candle of the run, the body range, the full range."""
    j = int(ob.src)
    k = j
    while k + 1 <= ob.i and k + 1 < len(sd.c) and sd.c[k + 1] < sd.o[k + 1]:
        k += 1
    return dict(j=j, k=k, body_top=float(sd.o[j:k + 1].max()), body_low=float(sd.c[j:k + 1].min()), hi=float(ob.top), lo=float(ob.bottom), mt=float(ob.mt))


def ob_mt_price(ob: dict) -> float:
    """A12-ltf-ob-upper-half (cc02_002 ~6:24): ob_entry_px "mt" with ob_mt_range "range" = the midpoint of the candle's high and low."""
    hit("ob_mt_range")
    return float((ob["hi"] + ob["lo"]) / 2)


# --- 2. order-block entries (A12) -----------------------------------------------------------------------------------------------------------------

def ob_fvg_ok(sd, k: int, i: int) -> bool:
    """A12-ob-requires-signatures (022 ~13:12, ~1:37:52): "there has to be signatures" - the bullish OB candle (index k) is only a potential OB until an FVG whose first candle is the OB candle or
    the one after it (the displacement) has printed: its third candle has closed by bar i."""
    return any(g.i <= i and (g.i - 2) in (k, k + 1) for g in sd.gaps)


def htf_contains(ctx, sd, sw, i: int, lo: float, hi: float, p) -> bool:
    """A same-side HTF PD array (FVG / OB / VI of 15m..W, known BEFORE the sweep extreme completed) contains [lo, hi] (side space, tolerance eq_tol_pts) [our interpretation of "the OB candles lie inside
    the pre-called HTF discount array"]."""
    S = _S()
    kq = ctx.idx[sw["ext_i"]] + pd.Timedelta(minutes=ctx.tf)
    tol = _tol(p)
    return any(bot - tol <= lo and hi <= top + tol for top, bot, _ in S._ts_arrays(ctx, sd, i, kq))


def narrative_ok(ctx, sd, sw, ob: dict, i: int, p) -> bool:
    """A12-ob-requires-narrative (059 ~19:00; 064 ~51:56; 065 ~1:28:02; 085 ~40:10): "there has to be a narrative". (1) the session bias is this side (`want`); (2) with ob_need_htf_array the OB bodies lie in a
    same-side HTF array that was known before the sweep; (3) a transitional event happened before or by the OB candle: the pool sweep (its first bar not after the OB candle) - for an HTF-array premise
    (key "htf_array") the traded-into array itself; (4)-(6) are the engine's own flow (the last down-close run, the leave-the-bodies close, the leg_pd discount)."""
    if _want(ctx) != sd.sign:
        return False
    if sw.get("key") != "htf_array" and int(sw.get("sweep_i", sw["ext_i"])) > int(ob["k"]):
        return False
    if p.ob_need_htf_array and not htf_contains(ctx, sd, sw, i, float(ob["body_low"]), float(ob["body_top"]), p):
        return False
    hit("ob_narrative")
    return True


def vi_far_edge(sd, lo: float, top: float, j: int, i: int, p) -> float | None:
    """A12-ob-overshoot-to-vi (050 ~33:56): the far edge (side space: the bottom) of the lowest live VI that lies under the OB and touches its far side (VI top within eq_tol_pts of the OB low or inside the
    OB region, VI bottom below the OB low), formed from the OB's first candle on [our interpretation: "adjacent lower-TF VI" = a base-bar VI]; a close under its far edge since it formed kills it."""
    tol = _tol(p)
    best = None
    for z in sd.vis("bull"):
        if z.i > i or z.i < j - 1:
            continue
        if not (z.top >= lo - tol and z.top <= top + tol and z.bottom < lo - MIN1):
            continue
        if sd.c[z.i + 1:i + 1].min(initial=np.inf) < z.bottom:
            continue
        best = float(z.bottom) if best is None else min(best, float(z.bottom))
    return best


def ob_gate(ctx, sd, sw, ob: dict, i: int, p) -> bool:
    """The pre-break / anchor OB order gates of the chunk: ob_need_fvg (4) and ob_need_narrative (87). False = the OB does not arm (yet)."""
    if p.ob_need_fvg and not ob_fvg_ok(sd, int(ob["k"]), i):
        hit("ob_potential")
        return False
    if p.ob_need_narrative and not narrative_ok(ctx, sd, sw, ob, i, p):
        _S()._f("x_ob_narrative")
        return False
    return True


def ob_ce_entry(ctx, sd, sw, g, top: float, bottom: float, i: int, p) -> float | None:
    """A12-ob-edge-at-fvg-ce (058 ~32:02): the HIGH of the parent-TF (15m) down-close run (bullish; the LOW of the up-close run for a short) within ob_ce_tol_pts of the entry FVG's CE sets the limit - the
    FVG's upper half is then expected to stay unfilled. Only a 15m OB known by bar i (the 15m bars must be coarser than the base bars). The level is clipped into the gap."""
    if ctx.tf >= 15 or 15 % ctx.tf:
        return None
    ce = (top + bottom) / 2
    tol = p.ob_ce_tol_pts * p.es_pt
    cands = [z for z in sd.zones_tf(ctx.idx, ctx.tf, 15) if z.mt == z.mt and z.i <= i and abs(z.top - ce) <= tol + MIN1]
    if not cands:
        return None
    z = min(cands, key=lambda z: abs(z.top - ce))
    hit("ob_ce_confluence")
    return float(min(max(z.top, bottom), top))


def wick_ltf_entry(ctx, sd, g, sw, i: int, p) -> tuple | None:
    """A12-ob-open-anchor-ltf-wick (061 ~26:10): an HTF OB zone whose upper wick is stubby (< 25 % of the candle range [our interpretation]): the open is the HTF anchor, but a trade into the wick between the open and
    the extreme does not invalidate - the entry is a base-bar FVG inside [open, high] (the most recent live one). Returns (top, bottom) of that FVG or None."""
    lv = getattr(g, "levels", ())
    if not lv or g.mt != g.mt:
        return None
    hit("ob_wick_eval")
    op, hi = float(lv[0]), float(g.top)
    rng = hi - float(g.bottom)
    if rng <= 0 or not (hi - op) < 0.25 * rng or hi - op <= MIN1:
        return None
    tol = _tol(p)
    cs = [b for b in sd.gaps if b.i <= i and b.bottom >= op - tol and b.top <= hi + tol and b.src > sw["ext_i"] - 1
          and sd.c[b.i + 1:i + 1].min(initial=np.inf) >= b.bottom - MIN1]
    if not cs:
        return None
    b = max(cs, key=lambda z: z.i)
    hit("ob_wick_ltf")
    return float(b.top), float(b.bottom)


def htf_open_top(g, p) -> float:
    """A12-ob-anchor-level (cc03_001 ~28:18; cc06_004; cc10_005; 072): an HTF OB zone enters at its open under htf_ob_anchor "open" (the A12 2023 level), at its candle extreme under "extreme" (the zone range's
    top, as built)."""
    lv = getattr(g, "levels", ())
    if p.htf_ob_anchor == "open" and lv and g.mt == g.mt:
        hit("htf_ob_open")
        return float(min(g.top, lv[0]))
    return float(g.top)


# --- 3. FVG entries (A5 / E2 / A15 / A16 / A9) ----------------------------------------------------------------------------------------------------

def remaining_top(sd, g, top: float, bottom: float, i: int, p) -> float:
    """A5-partial-reprice-shrink (056 ~16:13): the part of the entry FVG not yet traded through - a wick into the gap from above shrinks its top to the lowest low printed since the gap formed (never under the
    bottom + a tick); the limit rests at the top of what remains."""
    mn = float(sd.l[g.i + 1:i + 1].min(initial=np.inf))
    if mn < top and mn > bottom + p.tick:
        hit("fvg_remaining")
        return mn
    return top


def two_min_ce(ctx, sd, g, i: int, p) -> float | None:
    """new-2m-fvg-ce (062 ~40:09): when the 1m FVG's displacement is two consecutive same-direction 1m candles (the middle candle and a neighbour), view it on the 2m chart - the limit is the CE of the 2m FVG whose
    middle candle holds the displacement and which overlaps the 1m gap (this can be the measuring gap)."""
    if ctx.tf != 1 or g.src < 1 or g.src + 1 >= len(sd.c):
        return None
    hit("two_min_eval")
    k = int(g.src)
    up = lambda q: sd.c[q] > sd.o[q]
    if not up(k) or not (up(k - 1) or up(k + 1)):
        return None
    gr = sm6.tf_groups(ctx, sd, 2)
    if gr is None:
        return None
    first, last, done, o2, h2, l2, c2 = gr
    for z in L.fvgs(h2, l2, o2, c2):
        if z.kind != "bull" or not done[z.i] or last[z.i] > i:
            continue
        if first[z.src] <= k <= last[z.src] and z.bottom < g.top and z.top > g.bottom:
            hit("two_min_ce")
            return float(z.mid)
    return None


def scan_gaps(ctx, sd, sw, i: int, p) -> list:
    """new-multi-tf-scan (070 ~30:37; 072 ~11:09): the FVGs of the extra bar sizes of scan_tfs (built from the base bars; 2m..5m, 120 = 2h; sub-minute is out of reach) as further entry gaps - formed after the sweep,
    complete by bar i, not closed through. Each carries the tag scan_tf_<m> in sw["_scan_tf"] by id."""
    out = []
    tags = sw.setdefault("_scan_tf", {})
    for m in sorted({int(x) for x in p.scan_tfs}):
        if m <= ctx.tf or m % ctx.tf:
            continue
        for z in sm4._tf_fvgs(ctx, sd, m):
            if z.i <= i and z.src > sw["ext_i"] and sm4._alive(sd, z, i):
                out.append(z)
                tags[id(z)] = m
    if out:
        hit("scan_tfs")
    return out


def refine_down(ctx, sd, sw, g, i: int, p):
    """A5-mtf-gap-refinement (044 ~45:31; 046 ~19:32) gap_tf_mode "refine_down": the entry array is an HTF imbalance (a coarser zone, not a base-bar gap) - an LTF FVG of the same displacement that lies inside or
    overlaps it (any price overlap [our interpretation]) and still beyond the swept liquidity replaces it: its edges / CE are the operative level. Returns the LTF gap or None."""
    if any(g is z for z in sd.gaps) or g.mt == g.mt:
        return None
    span = max(int(g.i - g.src), 1)
    cs = [b for b in sd.gaps if b.i <= i and g.src - span <= b.src <= g.i and b.top > g.bottom and b.bottom < g.top
          and b.bottom >= sw["ext"] - MIN1 and sd.c[b.i + 1:i + 1].min(initial=np.inf) >= b.bottom - MIN1]
    if not cs:
        return None
    hit("gap_refine_down")
    return max(cs, key=lambda b: (b.top, b.i))


def widen_targets(ctx, sd, i: int, above: float, p) -> list:
    """A5-mtf-gap-refinement (024 ~21:39) gap_tf_mode "widen_up": a target FVG (an untraded opposing FVG of the base bars) that overlaps a 15m opposing FVG of the same move extends to the 15m far edge - that
    far edge is a further target level (side space, "array"). Returns [(level, "array")]."""
    if ctx.tf >= 15 or 15 % ctx.tf:
        return []
    gr = sm6.tf_groups(ctx, sd, 15)
    if gr is None:
        return []
    first, last, done, o2, h2, l2, c2 = gr
    out = []
    for z in sd.opposing():
        if z.i > i or z.bottom <= above or sd.h[z.i + 1:i + 1].max(initial=-np.inf) >= z.bottom:
            continue
        for y in L.fvgs(h2, l2, o2, c2):
            if y.kind != "bear" or not done[y.i] or last[y.i] > i or y.top <= z.bottom or y.bottom >= z.top:
                continue
            if first[y.src] > z.i or last[y.i] < z.src:
                continue                                           # the same move: the 15m gap's candles span the base gap's formation
            if y.top > z.top and sd.h[last[y.i] + 1:i + 1].max(initial=-np.inf) < y.bottom:
                out.append((float(y.top), "array"))
    if out:
        hit("gap_widen_up")
    return out


def near_stop_pool(sd, sw, g, i: int, p) -> bool:
    """A5-skip-fvg-near-stop-pool (060 ~1:11:00): "this is too close in proximity so it could run above here to take out buy side" - an entry FVG within fvg_pool_gap_pts of an untaken short-term extreme (the
    3-candle swing formed in the retrace, side space: a swing low UNDER the gap) that lies between the gap and the protective extreme (the sweep extreme) is skipped; the next gap higher up is looked for instead.
    ICT gives no distance threshold [our interpretation: fvg_pool_gap_pts]. The side-space mirror covers the short."""
    gp = p.fvg_pool_gap_pts * p.es_pt
    for q in sd.pl:
        if q.known > i or q.i <= sw["ext_i"]:
            continue
        if not (sw["ext"] < q.price < g.bottom and g.bottom - q.price <= gp + MIN1):
            continue
        if sd.l[q.i + 1:i + 1].min(initial=np.inf) >= q.price - MIN1:
            hit("fvg_near_pool")
            return True
    return False


def mtf_closes_inside(ctx, sd, g, i: int, p) -> int:
    """A5-multitf-hold-test (064 ~1:32:01): the largest number of bar closes inside the gap [bottom, top] on any of the 1m..4m charts (the base bars, 2m, 3m, 4m built from them) since the gap formed - "wicks
    entering the gap while the bodies stay above its high = holding; bodies closing inside = a weaker hold" [our interpretation: 'mostly' = fewer than two closes inside on every chart]."""
    best = 0
    for m in (1, 2, 3, 4):
        if m < ctx.tf or m % ctx.tf:
            continue
        gr = sm6.tf_groups(ctx, sd, m)
        if gr is None:
            continue
        first, last, done, o2, h2, l2, c2 = gr
        ks = np.flatnonzero(done & (last <= i) & (first > g.i))
        n = int(sum(1 for k in ks if g.bottom - MIN1 <= c2[k] <= g.top + MIN1))
        best = max(best, n)
    return best


def mtf_hold_ok(ctx, sd, g, i: int, p) -> bool:
    if ctx.tf >= 5 or any(g is z for z in sd.gaps):
        return True                                     # judged on the 1-4m charts, for a coarser (5m) entry gap
    hit("mtf_hold_eval")
    n = mtf_closes_inside(ctx, sd, g, i, p)
    if n >= 2:
        hit("mtf_hold_cancel")
        return False
    return True


def iofed_check(sd, g, entry: float, i: int, p) -> bool:
    """E2-iofed-full-definition (015 ~18:57; 047 ~10:40), the arm-time part of the strict IOFED: the retrace so far has not reached the CE (no trade at or under it since the gap formed) and the limit sits above
    the CE. The sweep + MSS context is the engine's own path; the 3-candle swing low inside the gap is the position check (manage)."""
    if sd.l[g.i + 1:i + 1].min(initial=np.inf) <= g.mid + MIN1 or entry <= g.mid + MIN1:
        return False
    hit("iofed_strict")
    return True


def vi_stop_level(sd, z, p) -> float | None:
    """A9-vi-retest-tolerance (026 ~1:34:23; 027 ~16:27): the invalidation level of the VI under the entry (side space; the stop sits a tick under it). vi_tol "ce": the extreme of the VI's two candles (the
    marked low) - retests up to the CE are allowed; "adjacent_extreme": the same for a SMALL VI (<= vi_tol_small_pts) only - it may overshoot to the adjacent candle's extreme, beyond that it failed. None = the
    VI's own bottom (built)."""
    if p.vi_tol == "none":
        return None
    if p.vi_tol == "adjacent_extreme" and z.top - z.bottom > p.vi_tol_small_pts * p.es_pt + MIN1:
        return None
    lo = float(min(sd.l[z.i - 1], sd.l[z.i])) if z.i >= 1 else float(z.bottom)
    if lo < z.bottom - MIN1:
        hit("vi_tol")
        return lo
    return None


def mit_context(sd, sw, g, i: int) -> bool:
    """A15-mitigation-definition-and-iofed (012 ~11:39): the arming context is a mitigation block - a bullish mitigation block (a would-be breaker candle price trades back to and above) known since the sweep
    that lies above the entry gap or overlaps it: the IOFED follows into the FVG just below it."""
    return any(z.i <= i and z.i >= sw["ext_i"] and (z.bottom >= g.top - MIN1 or z.bottom < g.top and z.top > g.bottom) for z in sd.mitigations())


def prop_depth(sd, sw, g_top: float, i: int):
    """A16-propulsion-depth-grade (079 ~12:00): (zone, depth) of the highest propulsion block under the entry gap (the one strategy.prop_block / entries.prop_block pick) with
    depth = (K_high - P_low) / (K_high - K_low), K the earlier OB the PB candle traded into. None when no PB / OB is found."""
    pz = [z for z in sd.propulsions() if z.i <= i and z.i > sw["ext_i"] and z.bottom <= g_top and z.top >= sw["ext"]]
    if not pz:
        return None
    hit("prop_depth_eval")
    z = max(pz, key=lambda z: z.top)
    ks = []
    for g in sd.gaps:
        ob = L.order_block_blend(sd.o, sd.h, sd.l, sd.c, g.i - 4, g.i - 2, "bull")
        if ob is not None and sd.c[g.i - 1] > ob.top and g.i < z.src and z.bottom <= ob.top and ob.top > ob.bottom:
            ks.append((g.i, ob))
    if not ks:
        return None
    ob = max(ks, key=lambda t: t[0])[1]
    return z, float((ob.top - z.bottom) / (ob.top - ob.bottom))


# --- NEW-no-return-to-origin-ob (cc03_003 ~00:21:37) ----------------------------------------------------------------------------------------------

def _daily_side(ctx, sd, n: int = 40):
    """The last n COMPLETED sessions as side-space (highs, lows, closes), or None."""
    hist = (getattr(ctx, "hist", None) or [])[-n:]
    if len(hist) < 6:
        return None
    hi = np.array([float(f.high.max()) for f in hist])
    lo = np.array([float(f.low.min()) for f in hist])
    cl = np.array([float(f.close.iloc[-1]) for f in hist])
    return (hi, lo, cl) if sd.sign > 0 else (-lo, -hi, -cl)


def origin_info(ctx, sd):
    """The origin of a confirmed reversal on the daily chart (side space): the window's lowest daily low L0 tested at least twice (daily lows within ctx.no_origin = eq_tol_pts x 4 of it), a daily pivot high
    after the second test (3-candle, known one session later) and a LATER daily close above it - "institutional sponsorship should protect price from ever coming back down". Returns dict(L0, H) (H = the
    highest high since the first test) or None. Completed sessions only."""
    c = ctx.__dict__.setdefault("_es1", {})
    key = ("origin", sd.sign)
    if key in c:
        return c[key]
    res = None
    tol = getattr(ctx, "no_origin", None)
    d = _daily_side(ctx, sd)
    if d is not None and tol is not None:
        hi, lo, cl = d
        l0 = float(lo.min())
        tests = np.flatnonzero(lo <= l0 + tol)
        if len(tests) >= 2:
            for q in range(int(tests[1]) + 1, len(hi) - 2):
                if hi[q] > hi[q - 1] and hi[q] > hi[q + 1] and bool((cl[q + 2:] > hi[q]).any()):
                    res = dict(L0=l0, H=float(hi[int(tests[0]):].max()))
    c[key] = res
    return res


def is_origin(ctx, sd, i: int, v: float) -> bool:
    """A level (side space) at / under the origin low of a confirmed daily reversal."""
    info = origin_info(ctx, sd)
    if info is None:
        return False
    if v <= info["L0"] + ctx.no_origin:
        hit("no_origin_level")
        return True
    return False


def drop_origin(ctx, sd, i: int, arrs: list) -> list:
    """NEW-no-return-to-origin-ob: after repeated tests of a daily low and a daily break above the old high, price is not expected back to the origin - the arrays holding the origin low are no entry arrays;
    the retracement is bought at the swing's lower grades (25-50 %): when such arrays exist the deeper ones (their middle under the 25 % line) go as well. arrs = [(top, bottom, known)] side space."""
    info = origin_info(ctx, sd)
    if info is None:
        return arrs
    tol, l0 = ctx.no_origin, info["L0"]
    r = max(info["H"] - l0, 0.0)
    keep = [a for a in arrs if not (a[1] - tol <= l0 <= a[0] + tol)]
    band = [a for a in keep if l0 + 0.25 * r - tol <= (a[0] + a[1]) / 2 <= l0 + 0.5 * r + tol]
    if band:
        keep = [a for a in keep if (a[0] + a[1]) / 2 >= l0 + 0.25 * r - tol]
    if len(keep) < len(arrs):
        hit("no_origin_drop")
    return keep


# --- 4. the P/D frames (A21 / B5) -----------------------------------------------------------------------------------------------------------------

def body_leg(sd, sw, i: int):
    """A21-intraday-fib-bodies (058 ~41:48): "using the bodies not the wicks because the bodies tell the story" - the leg from the lowest min(o, c) to the highest max(o, c) since the sweep extreme."""
    e = sw["ext_i"]
    lo = float(np.minimum(sd.o[e:i + 1], sd.c[e:i + 1]).min())
    hi = float(np.maximum(sd.o[e:i + 1], sd.c[e:i + 1]).max())
    hit("pd_body")
    return lo, hi


def pd_top_fixed(sd, sw, i: int, p):
    """A21-post-cisd-range-retrace (075 ~1:23:41): leg_pd_anchor "retrace_range" - after a CISD validates the OB, the dealing range is [the sweep low (the low the CISD protects), the swing high the decline began
    from]: the MSS reference swing high. Returns that high (side space) or None. ("target" is applied after the targets are known: pd_top_target.)"""
    if p.leg_pd_anchor == "retrace_range":
        px = sw.get("ref_px")
        if px is not None and px > sw["ext"]:
            hit("pd_retrace_range")
            return float(px)
    return None


def prev_range(ctx, kind: str):
    """B5-prior-day-ny-range-retracement (cc08_007 ~00:00:40): (low, high) in REAL prices of the previous session: "prev_day" = its RTH day (09:30-16:00), "prev_ny" = its NY session 08:30-16:00 [our interpretation].
    ctx.hist holds the COMPLETED prior sessions (backtest.run keeps them RTH-only: then both frames are the RTH range). None without data."""
    f = getattr(ctx, "prev_full", None)
    if f is None or not len(f):
        hist = getattr(ctx, "hist", None)
        f = hist[-1] if hist else None
    if f is None or not len(f):
        return None
    t = f.index.hour * 60 + f.index.minute
    m = (t >= (570 if kind == "prev_day" else 510)) & (t < 960)
    if not bool(np.any(m)):
        return None
    return float(f.low[m].min()), float(f.high[m].max())


def frame_line(ctx, sd, p, leg_line: float) -> float:
    """B5-prior-day-ny-range-retracement: the discount line (side space) the entry is measured against. "leg" = the displacement leg's line (built); "prev_day" / "prev_ny" = leg_pd of the previous session's
    low-to-high range; "any" = the highest of the three (passes if either frame is in discount). A frame without data falls back to the leg line."""
    fr = p.entry_pd_frame
    if fr == "leg":
        return leg_line
    lines = {}
    for k in ("prev_day", "prev_ny"):
        r = prev_range(ctx, k)
        if r is not None:
            a, b = sorted((sd.x(r[0]), sd.x(r[1])))
            lines[k] = a + p.leg_pd * (b - a)
    if fr == "any":
        hit("pd_frame_any")
        return max([leg_line] + list(lines.values()))
    if fr in lines:
        hit("pd_frame_" + fr)
        return lines[fr]
    return leg_line


def pd_active(p) -> bool:
    return bool(p.entry_pd_frame != "leg" or p.leg_pd_anchor != "displacement_leg" or p.leg_fib != "wick")


def pd_line(ctx, sd, p, o: dict, i: int) -> float:
    """The fill-time leg_pd discount line of a pending order `o` (run_day): the built formula - leg_lo + leg_pd x (leg high - leg_lo) with the live leg high (the frozen high with no_new_extreme) - with
    the fixed top of leg_pd_anchor ("target" / "retrace_range": o["pd_top"]), the body leg of leg_fib and the frames of entry_pd_frame."""
    lo = o.get("leg_lo", o["ext"])
    if o.get("pd_top") is not None:
        hi = o["pd_top"]
    elif p.leg_fib == "body":
        hi = float(np.maximum(sd.o[o["ext_i"]:i], sd.c[o["ext_i"]:i]).max(initial=-np.inf))
        hi = hi if np.isfinite(hi) else o["leg_hi0"]
    else:
        hi = o["leg_hi0"] if o.get("no_new_extreme") else float(sd.h[o["ext_i"]:i].max())
    return frame_line(ctx, sd, p, lo + p.leg_pd * (hi - lo))


# --- 5. the OTE (M13) -----------------------------------------------------------------------------------------------------------------------------

def ote_gate_ok(sd, sw, i: int, p) -> bool:
    """M13-swing-confirm-gate (cc01_004 ~13:58, ~21:38, ~28:18; cc01_005 ~8:05, ~13:30): the leg's far extreme H (the latest highest high since the sweep) must be a 3-candle swing high confirmed by the 4th
    candle - bar h+2 lower than high[h] (h+1 too). Only then is the retrace watched; a dip on h+1 is ignored. A new extreme re-anchors and redoes the gate (the next call sees the new H)."""
    e = sw["ext_i"]
    seg = sd.h[e:i + 1]
    hh = e + int(len(seg) - 1 - np.argmax(seg[::-1]))        # the latest of equal highs
    if hh + 2 > i:
        hit("ote_gate_wait")
        return False
    if hh - 1 >= 0 and not sd.h[hh] > sd.h[hh - 1]:
        return False
    ok = bool(sd.h[hh + 1] < sd.h[hh] and sd.h[hh + 2] < sd.h[hh])
    if ok:
        hit("ote_gate_open")
    return ok


def ote_children(sd, sw, i: int) -> list:
    """M13-nested-ranges (cc01_004 ~23:31; cc01_005 ~8:28): the child legs - swing lows (3-candle) after the sweep extreme that held above it and did not trade below since (a trade below a child low drops
    that child). The legs run from each such low to the leg high. Returns the child lows, most recent first."""
    e = sw["ext_i"]
    out = [q.price for q in sd.pl if q.i > e and q.known <= i and q.price > sw["ext"] + MIN1
           and sd.l[q.i + 1:i + 1].min(initial=np.inf) >= q.price - MIN1]
    return sorted(set(out), reverse=True)


def ote_band_for(sd, sw, i: int, p, entry: float, lo_base: float, leg_hi: float):
    """M13-nested-ranges: the base (leg low) whose OTE band holds `entry`: the parent (the sweep extreme), else the most recent live child. Returns the base or None."""
    cands = [lo_base]
    if p.ote_nested:
        cands = ote_children(sd, sw, i) + [lo_base]
    for b in cands:
        lo, hi, _ = L.ote_band(b, leg_hi)
        if lo - MIN1 <= entry <= hi + MIN1:
            if b != lo_base:
                hit("ote_child")
            return b
    return None


def parent_third_ok(sd, sw, i: int, p, entry: float, leg_hi: float, base: float) -> bool:
    """M13-nested-ranges (cc01_006 ~13:16): the high-probability long location - the lower third of the parent swing (the sweep extreme to the high) AND below the EQ of the current small range (the most
    recent live child, else the parent itself), buy-side above as the target."""
    ext = sw["ext"]
    hit("ote_third_eval")
    if entry > ext + (leg_hi - ext) / 3 + MIN1:
        return False
    ch = ote_children(sd, sw, i)
    small = ch[0] if ch else base
    return bool(entry <= small + 0.5 * (leg_hi - small) + MIN1)


def ote_reprice(sd, o: dict, k: int, p):
    """M13-reanchor-parent (cc01_004 ~13:58, ~37:30): a pending OTE limit whose leg got a NEW swing high (3-candle, confirmed by bar k) above its H with no trade under L: H moves up, the band / sweet spot
    are recomputed and the order follows (entry, the leg, the cancel line, the size for the same dollar risk). Returns the updated order dict or None (nothing to do)."""
    e = o["ext_i"]
    hs = [q for q in sd.ph if q.i > e and q.known <= k and q.price > o["leg_hi0"] + MIN1]
    if not hs or sd.l[e:k + 1].min() < o["ext"] - MIN1:
        return None
    new_h = max(q.price for q in hs)
    lo, hi, sweet = L.ote_band(o["ext"], new_h)
    entry = min(sweet, float(sd.c[k]))
    if p.ote == "limit" and entry < o["stop"] + p.min_risk_pts * p.es_pt:
        return None
    o2 = dict(o)
    old_risk, new_risk = o["entry"] - o["stop"], entry - o["stop"]
    o2.update(entry=entry, leg_hi0=float(new_h), leg=(float(o["ext"]), float(new_h)), zone_top=float(min(o.get("zone_top", entry), hi)), i=k)
    if o2.get("cancel_low") is not None and p.ote_cancel:
        o2["cancel_low"] = float(lo)
    if new_risk > 0 and old_risk > 0:
        o2["shares"] = max(1, int(o["shares"] * old_risk / new_risk))
    hit("ote_reanchor")
    return o2


# --- 6. breakers / adds / tags --------------------------------------------------------------------------------------------------------------------

def breaker_refine(sd, sw, bz, i: int, p):
    """A13-breaker-fvg-refinement (031 ~1:02:29; 032 ~41:26): the zone is [low, high] of the breaker candle; any FVG or VI inside it (formed in the displacement after the sweep, not closed through) is the
    refinement - the entry is its near edge, the idea is cancelled on a body close under its low (wicks may reach the zone low). Returns (entry, cancel_close) or None."""
    tol = _tol(p)
    zs = [z for z in list(sd.gaps) + list(sd.vis("bull")) if z.i <= i and z.src >= sw["ext_i"] - 1 and z.bottom >= bz.bottom - tol and z.top <= bz.top + tol
          and sd.c[z.i + 1:i + 1].min(initial=np.inf) >= z.bottom - MIN1 and z.top - z.bottom > MIN1]
    if not zs:
        return None
    z = max(zs, key=lambda z: (z.top, z.i))
    hit("breaker_refine")
    return float(z.top), float(z.bottom)


def ob_in_vi_add(sd, pos, i: int, p):
    """A5-ob-in-vi-over-newer-fvg (009 ~12:07): while adding to an open long after the sell-side is cleared (the sweep preceded the fill): a down-close candle (a bullish OB) of this pullback (after the fill)
    whose low traded into a VI - touch allowed, the VI's bottom not pierced - is the add, at the OB's MT; the VI bottom is the floor / stop reference. Returns (mt, floor) or None."""
    f = pos["fill_i"]
    best = None
    hit("add_ob_vi_eval")
    for z in sd.vis("bull"):
        if z.i > i or z.i <= f - 1:
            continue
        for k in range(f + 1, i):
            if not sd.c[k] < sd.o[k] or k < z.i - 1:
                continue
            if sd.l[k] <= z.top + MIN1 and sd.l[k] >= z.bottom - MIN1 and sd.l[z.i + 1:i + 1].min(initial=np.inf) >= z.bottom - MIN1:
                j = k
                while j - 1 > f and sd.c[j - 1] < sd.o[j - 1]:
                    j -= 1
                top = float(sd.o[j:k + 1].max())
                low = float(sd.c[j:k + 1].min())
                mt = (top + low) / 2
                if mt < sd.c[i] and (best is None or k > best[2]):
                    best = (float(mt), float(z.bottom), k)
    if best is None:
        return None
    hit("add_ob_in_vi")
    return best[0], best[1]


def cisd_runs(sd, f: int, i: int):
    """A12-cisd-open-buy-level (032 ~53:04, ~55:30): the down-close runs after bar f as (first, last) index pairs, closed by bar i (a run ends at an up-close or flat candle)."""
    runs, j = [], None
    for k in range(f + 1, i + 1):
        if sd.c[k] < sd.o[k]:
            j = k if j is None else j
        elif j is not None:
            runs.append((j, k - 1))
            j = None
    return runs


def cisd_add(sd, pos, tr, i: int, p, arm) -> None:
    """cisd_adds: each LATER down-close run (after the fill, before the draw) that gets its own CISD (a bar whose high is at least the run's first open + 1 tick, with no body close under the run low in
    between) gives a new open_ref: a resting add at that open (arm(px, floor)). The CISD bar is bar i itself, once per run; E12 sizes; no adds after a partial (can_add already says so)."""
    st = pos.setdefault("es1", {})
    hit("cisd_add_eval")
    used = st.setdefault("cisd_used", set())
    for j, k in cisd_runs(sd, pos["fill_i"], i):
        if j in used:
            continue
        ref = float(sd.o[j])
        lo = float(sd.l[j:k + 1].min())
        if sd.c[k + 1:i + 1].min(initial=np.inf) < lo - MIN1:
            used.add(j)
            continue
        hit_bars = np.flatnonzero(sd.h[k + 1:i + 1] >= ref + p.tick - MIN1)
        if not len(hit_bars) or k + 1 + int(hit_bars[0]) != i:
            continue
        used.add(j)
        if ref < sd.c[i]:
            hit("cisd_add")
            arm(ref, lo)
            return


def htf_depth_tier(ctx, sd, sw, i: int, p) -> str | None:
    """A8-htf-gap-resistance-grade (065 ~1:27:00): how deep the reaction went into the HTF FVG (D / 4h / 1h / 30m / 15m / W) holding the sweep extreme: "near" (it did not reach the CE), "ce" (reached the CE,
    not the far edge), "far" (traded to the far edge). Side space: the gap's top is the near edge. None when no such gap."""
    cf = getattr(ctx, "conf", None)
    if cf is None:
        return None
    now = sm2.now_ts(ctx, i)
    kb = ctx.idx[sw["ext_i"]] + pd.Timedelta(minutes=ctx.tf)
    tol = _tol(p)
    best = None
    for top, bot, tf_, sc, kn in cf.valid(now, sd.sign, ("15m", "30m", "1h", "4h", "D", "W"), (0,), kb):
        a, b = sorted((sd.x(top), sd.x(bot)))
        if a - tol <= sw["ext"] <= b + tol:
            best = (a, b) if best is None or (b - a) > (best[1] - best[0]) else best
    if best is None:
        return None
    a, b = best
    ce = (a + b) / 2
    ext = float(sw["ext"])
    if ext <= a + tol:
        return "far"
    if ext <= ce + MIN1:
        return "ce"
    return "near"


# --- the order gate (called from strategy._finish_order) ------------------------------------------------------------------------------------------

def any_gate_es1(p) -> bool:
    return bool(p.htf_depth_mult != (1.0, 1.0, 1.0) or p.prop_deep_mult != 1.0)


def order_gate_es1(ctx, sd, sw, i: int, p, entry: float, stop: float, session: str, lvt: list, lvx: dict, tags: dict):
    """The tags / risk multipliers of the chunk: A8-htf-gap-resistance-grade (the htf_depth tier and its multiplier), A16-propulsion-depth-grade (the deep-PB multiplier; 0 = skip). Returns a reject key or None."""
    mult = 1.0
    if p.htf_depth_mult != (1.0, 1.0, 1.0):
        tier = htf_depth_tier(ctx, sd, sw, i, p)
        if tier is not None:
            lvt.append("htf_depth_" + tier)
            mult *= p.htf_depth_mult[("near", "ce", "far").index(tier)]
            hit("htf_depth_" + tier)
    pdp = tags.pop("es1_prop_depth", None)
    if pdp is not None and pdp > p.prop_deep_cut:
        lvt.append("prop_deep")
        if p.prop_deep_mult == 0:
            return "x_prop_deep"
        mult *= p.prop_deep_mult
        hit("prop_deep")
    if mult != 1.0:
        tags["es1_mult"] = mult
    return None


# --- 7. position hooks ----------------------------------------------------------------------------------------------------------------------------

def on_fill(ctx, sd, pos, tr, o: dict, i: int, p) -> None:
    st = dict(o.get("es1") or {})
    pos["es1"] = st
    if st.get("prop_wick") is not None:
        hit("prop_wick_set")
    if st.get("iofed"):
        io = dict(st["iofed"], ok=False)
        if sd.l[i] <= io["ce"] + MIN1:
            io["fill_bar_ce"] = True                 # the fill bar itself traded to the CE: the stop-at-CE is taken on the next management call
        st["iofed"] = io


def manage(ctx, sd, pos, tr, i: int, ts, p) -> None:
    """Per-bar management of the positions this chunk tagged (pos["es1"]):
    prop_mt_test "wick" (A16, 027 / cc04_008): any trade through the propulsion block's MT exits at that level (reason prop_wick);
    mt_break "warn" (D4): a trade under the OB MT is a tag only (lv_tags mt_traded);
    iofed_strict (E2): until a 3-candle swing low inside the gap has confirmed, a trade to the CE exits at the CE (reason iofed_ce)."""
    st = pos.get("es1")
    if not st or not pos["left"]:
        return
    f = pos["fill_i"]
    if st.get("prop_wick") is not None and i > f:
        lvl = float(st["prop_wick"])
        if sd.l[i] < lvl - MIN1:
            tr.exits.append((ts, sd.x(min(float(sd.o[i]), lvl)), pos["left"], "prop_wick"))
            pos["left"] = 0
            hit("prop_wick_exit")
            return
    if st.get("mt_warn") is not None and not st.get("warned") and i >= f and sd.l[i] < st["mt_warn"] - MIN1:
        st["warned"] = True
        tr.mt_warn = True
        hit("mt_warn_traded")
    io = st.get("iofed")
    if io and not io.get("ok"):
        ce, top, bot = io["ce"], io["top"], io["bottom"]
        if io.get("fill_bar_ce") or sd.l[i] <= ce + MIN1:
            px_ = min(ce, pos["basis"] / max(pos["n"], 1)) if io.get("fill_bar_ce") else min(float(sd.o[i]), ce)
            tr.exits.append((ts, sd.x(px_), pos["left"], "iofed_ce"))
            pos["left"] = 0
            hit("iofed_ce_exit")
            return
        j = i - 1
        if j >= f and j >= 1 and sd.l[j] < sd.l[j - 1] and sd.l[j] < sd.l[i] and bot - MIN1 <= sd.l[j] <= top + MIN1:
            io["ok"] = True                          # the retrace low is a confirmed 3-candle swing low inside the gap
            hit("iofed_swing_ok")


def after_close(ctx, pos, tr, done, key: str, state: dict, p) -> None:
    """A16-propulsion-block-full prop_fail_flip: the long (short) failed on the propulsion block's MT - no more longs this session (shorts only), the session slot re-opens for the opposite side."""
    if not p.prop_fail_flip or not tr.exits or tr.exits[-1][3] not in ("prop_mt", "prop_wick"):
        return
    side = 1 if tr.side == "long" else -1
    if state.setdefault("only_side", {}).get(tr.session) is None:
        done[key] = False
        state["only_side"][tr.session] = -side
        hit("prop_fail_flip")


# --- A23-broken-wick-ce-inversion (043 ~10:45, ~17:20; 044 ~46:41) -------------------------------------------------------------------------------

def broken_wick_cand(sd, sw, i: int, p):
    """entry_arrays "broken_wick_ce": the swing the MSS broke (the reference swing high, side space) supplies the wick; the CE of its upper wick, (max(open, close) + high) / 2, is the inversion level - the retrace goes
    to the CE, not to the old high, and may stop above it without voiding the idea. Returns (entry, bottom, "broken_wick_ce") like the other array candidates or None; sw["_bwc_edge"] = the wick's body edge
    (a body close beyond it - under it for a long - voids the level [our interpretation, test]). broken_wick_stop "body_edge" = the stop under the body edge, "swing" = under the sweep extreme."""
    k = int(sw["ref_i"])
    edge = float(max(sd.o[k], sd.c[k]))
    hi = float(sd.h[k])
    if hi - edge <= p.tick:
        return None
    sw["_bwc_edge"] = edge
    hit("broken_wick_ce")
    return (edge + hi) / 2, (edge if p.broken_wick_stop == "body_edge" else float(sw["ext"])), "broken_wick_ce"


# --- A5-far-edge-reach-conditions (058 ~25:40-29:46; 080 ~12:22) ---------------------------------------------------------------------------------

def far_edge(ctx, sd, g, top: float, bottom: float, i: int, p):
    """HTF entry array [bottom, top] (side space), the LTF read of whether the far edge is reached. (1) Layering: at least 3 pivots (back-and-forth swings) already printed in the band around the near edge
    since the array formed [our interpretation: the swing count 3, the band = the upper half of the array] -> the limit goes to the CE of the most recent small nested LTF FVG. (2) Inner BPR: the band was
    crossed one pass each way already (levels.pass_state) -> no full fill is expected. After (1) or (2) the far edge is protected (a valid stop location, tag far_edge_protected) and the gap should stay open.
    (3) A residual untraded LTF sub-gap sitting on the far edge makes the far edge a valid entry / target (tag far_edge_subgap); without it (and without (1) / (2)) the entry is the nested LTF FVG's near edge.
    Returns (entry or None, [tags])."""
    tol = _tol(p)
    z = L.Zone("bull", float(top), float(bottom), int(g.i))
    mid = (top + bottom) / 2
    pivs = [q for q in list(sd.ph) + list(sd.pl) if q.known <= i and q.i > g.i and mid - tol <= q.price <= top + tol]
    layered = len(pivs) >= 3
    up, down = L.pass_state(sd.h, sd.l, z, g.i + 1, i, side0=1)
    inner = L.is_efficient(up, down)
    nested = [b for b in sd.gaps if b.i <= i and b.i > g.i and b.bottom >= bottom - tol and b.top <= top + tol
              and sd.c[b.i + 1:i + 1].min(initial=np.inf) >= b.bottom - MIN1]
    nz = max(nested, key=lambda b: b.i) if nested else None
    sub = any(b.i <= i and abs(b.bottom - bottom) <= tol and sd.l[b.i + 1:i + 1].min(initial=np.inf) > b.top + MIN1
              for b in sd.gaps if b.bottom >= bottom - tol and b.top <= mid + tol)
    tags, entry = [], None
    if layered or inner:
        tags.append("far_edge_protected")
        hit("far_edge_protected")
        if layered and nz is not None:
            entry = float(nz.mid)
            tags.append("far_edge_layered")
    elif sub:
        tags.append("far_edge_subgap")
        hit("far_edge_subgap")
    elif nz is not None:
        entry = float(nz.top)
        tags.append("far_edge_nested")
        hit("far_edge_nested")
    return entry, tags
