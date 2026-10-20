"""Caption-gap pass (digests/rulebook_gaps/*.md), package levels_detectors #2/3: the engine glue.

The detectors live in levels.py (pure arrays in, zones out) and htf.py (daily / weekly arrays, opening gaps); this module wires
them into the bar-by-bar engine (strategy.py hooks) behind Params switches - see the "caption-gap pass, levels_detectors #2/3"
block of Params; every switch cites its gap id and source video/time there. Conventions as everywhere: side space (shorts run
mirrored prices), a bar is used only after it closes, an object only from the bar that completes it.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import levels as L


def _S():
    from . import strategy as S
    return S


def _c(ctx) -> dict:
    return ctx.__dict__.setdefault("_ld3", {})


# --- daily history ---------------------------------------------------------------------------------------------------

def daily_hl(ctx) -> list:
    """[(high, low)] of the completed sessions before today (the IPDA frame: RTH or ETH candles)."""
    d = getattr(ctx, "ipda_days", None)
    if d is None:
        d = [(float(x.high.max()), float(x.low.min())) for x in getattr(ctx, "hist", [])]
    return d


def daily_piv(ctx, sign: int):
    """Daily swing highs / lows (3-candle pivots) in SIDE space: (highs, lows). Only completed days; a pivot is confirmed one day later."""
    c = _c(ctx)
    key = ("dpiv", sign)
    if key not in c:
        d = daily_hl(ctx)
        if len(d) < 3:
            c[key] = ([], [])
        else:
            hi = np.array([x[0] for x in d], float)
            lo = np.array([x[1] for x in d], float)
            hs, ls = (hi, lo) if sign > 0 else (-lo, -hi)
            c[key] = L.pivots(hs, ls, 1)
    return c[key]


def _mirror(piv: list) -> list:
    return [L.Pivot(q.i, -q.price, q.known) for q in piv]


# --- A2 the active old high / low ------------------------------------------------------------------------------------

def old_pool(ctx, sd, i: int, p, buy: bool):
    """A2-which-old-high (002 ~0:34): buy=True the active buy-side pool = the first earlier daily swing high above today's high so far
    (bars through i; walk back newest to oldest); buy=False the sell-side mirror below today's low through bar i-1 (the sweep bar itself
    is not in it). Side space; None when there is none."""
    ph, pl = daily_piv(ctx, sd.sign)
    S = ctx.start
    if buy:
        return L.first_old_beyond(ph, float(sd.h[S:i + 1].max())) if i >= S else None
    if i - 1 < S:
        return None
    v = L.first_old_beyond([-q.price for q in pl], -float(sd.l[S:i].min()))
    return None if v is None else -float(v)


# --- A3 engineered pools ---------------------------------------------------------------------------------------------

def eng_all(ctx, sd, p, buy: bool) -> list:
    """A3-engineered-liquidity: every engineered pool of the frame (levels.engineered_pools on the 15m and 1h swings of the frame - mapped to
    base bars, known only once the confirming bucket is complete - and on the daily swings), each as dict(price, score, created,
    h2, taken): `created` the bar from which it exists, `taken` the first bar whose trade went through the level (None: untaken). Each pool
    needs only data up to its created bar; `taken` is a fact about a later bar and is compared with the asking bar at use. buy=False:
    the sell-side mirror (negated prices)."""
    c = _c(ctx)
    key = ("eng", sd.sign, buy, p.eng_short_pts)
    if key in c:
        return c[key]
    tol = p.eng_short_pts * p.es_pt
    H, Lw = (sd.h, sd.l) if buy else (-sd.l, -sd.h)
    res = []
    n = len(H)
    # review fix #5: the "+1 when an opposing FVG sits just above H1" weight, causal - an FVG counts only if it formed (z.i) by the bar the pool is created
    opp = [(z.i, float(z.bottom)) for z in L.fvgs(H, Lw) if z.kind == "bear"]
    bonus = lambda price, created: 1.0 if any(zi <= created and 0 <= fb - price <= tol for zi, fb in opp) else 0.0
    for m in (15, 60):
        if m < ctx.tf or m % ctx.tf:
            continue
        hs, ls = L.tf_pivots(ctx.idx, H, Lw, ctx.tf, m, 1)
        for price, score, created, h2 in L.engineered_pools(hs, ls, n - 1, tol):
            after = np.flatnonzero(H[h2 + 1:] > price)
            res.append(dict(price=price, score=score + bonus(price, int(created)), created=int(created), h2=int(h2), taken=int(h2 + 1 + after[0]) if len(after) else None,
                            name=f"eng{m}_{int(h2)}"))
    ph, pl = daily_piv(ctx, sd.sign)
    if len(ph) and len(pl):
        dh, dl = (ph, pl) if buy else (_mirror(pl), _mirror(ph))
        d = daily_hl(ctx)
        hd = np.array([x[0] for x in d], float) if sd.sign > 0 else -np.array([x[1] for x in d], float)
        ld = np.array([x[1] for x in d], float) if sd.sign > 0 else -np.array([x[0] for x in d], float)
        seq_h, seq_l = (hd, ld) if buy else (-ld, -hd)
        for price, score, created, h2 in L.engineered_pools(dh, dl, len(d) - 1, tol, h=seq_h):
            taken = None
            if len(H[ctx.start:]):
                a = np.flatnonzero(H[ctx.start:] > price)
                taken = int(ctx.start + a[0]) if len(a) else None
            res.append(dict(price=price, score=score + bonus(price, 0), created=0, h2=int(h2), taken=taken, name=f"engD_{int(h2)}"))
    c[key] = res
    return res


def eng_pools(ctx, sd, i: int, p, buy: bool) -> list:
    """[(price, created_bar, name, score)] of the engineered pools usable at bar i (untaken: for the buy side through bar i, for the sell side
    through bar i-1)."""
    lim = i if buy else i - 1
    out = []
    for r in eng_all(ctx, sd, p, buy):
        if r["created"] <= i and (r["taken"] is None or r["taken"] > lim):
            out.append((r["price"] if buy else -r["price"], r["created"], r["name"], r["score"]))
    return out


# --- L3 session opening ranges ---------------------------------------------------------------------------------------

def build_sors(ctx, p) -> list:
    """L3-midnight-session-opening-ranges (050 ~18:13): [(name, high, low, created_bar)] for each (start_minute, minutes) of Params.session_ors,
    from today's frame bars with start <= minute-of-day < start + minutes (the Asian 20:00 range is the prior evening, which is in the frame
    only with ETH data). Created = the bar after the window's last bar - the range exists only once it is complete. Real prices."""
    out = []
    S = ctx.start
    t = ctx.t
    for st, mins in p.session_ors:
        st, mins = int(st), int(mins)
        idx = np.flatnonzero((t[S:] >= st) & (t[S:] < st + mins)) + S
        if not len(idx):
            continue
        a, b = int(idx[0]), int(idx[-1])
        out.append((f"sor_{st}_{mins}", float(ctx.h[a:b + 1].max()), float(ctx.l[a:b + 1].min()), b + 1))
    return out


# --- A2 open float ---------------------------------------------------------------------------------------------------

def float_pools(ctx, sd, i: int, p, buy: bool) -> list:
    """A2-open-float (033 ~24:26; cc05_002 ~1:10): resting stops are not only at old highs. After a DOWN move the short-term highs formed during
    the decline hold shorts' trailed stops; when price is DENIED continuation - no new low for `float_denied_bars` bars and the range since
    the low under `float_denied_adr` x ADR5 [our interpretation] - those untaken swing highs are pools (buy side, side space; the nearest above
    is the draw). buy=False mirrors it: after an UP move the swing lows formed during the rally, when no new high came. [(price, created_bar)]."""
    S = ctx.start
    if i - S < p.float_denied_bars:
        return []
    adr = _S().adr5(getattr(ctx, "hist", [])[-5:])
    if not adr:
        return []
    if buy:
        seg_h, seg_l = sd.h[S:i + 1], sd.l[S:i + 1]
        lo_i, hi_i = S + int(np.argmin(seg_l)), S + int(np.argmax(seg_h))
        if hi_i >= lo_i or i - lo_i < p.float_denied_bars:
            return []
        if float(sd.h[lo_i:i + 1].max() - sd.l[lo_i:i + 1].min()) >= p.float_denied_adr * adr:
            return []
        return [(float(q.price), int(q.known)) for q in sd.ph
                if q.i > hi_i and q.known <= i and sd.h[q.i + 1:i + 1].max(initial=-np.inf) < q.price]
    if i - 1 < S + p.float_denied_bars:
        return []
    seg_h, seg_l = sd.h[S:i], sd.l[S:i]
    lo_i, hi_i = S + int(np.argmin(seg_l)), S + int(np.argmax(seg_h))
    if lo_i >= hi_i or i - 1 - hi_i < p.float_denied_bars:
        return []
    if float(sd.h[hi_i:i].max() - sd.l[hi_i:i].min()) >= p.float_denied_adr * adr:
        return []
    return [(float(q.price), int(q.known)) for q in sd.pl
            if q.i > lo_i and q.known <= i - 1 and sd.l[q.i + 1:i].min(initial=np.inf) > q.price]


# --- pool plumbing ---------------------------------------------------------------------------------------------------

def target_pools(ctx, sd, i: int, p) -> list:
    """[(level, created_bar)] buy-side pools of this package for _targets (side space)."""
    out = []
    if p.active_old_pool:
        v = old_pool(ctx, sd, i, p, True)
        if v is not None:
            out.append((float(v), ctx.start))
    if p.engineered_pools:
        out += [(v, cr) for v, cr, _, _ in eng_pools(ctx, sd, i, p, True)]
    for name, hi, lo, cr in (getattr(ctx, "sors", []) if p.session_ors else []):
        if cr <= i:
            out.append((float(sd.x(hi if sd.sign > 0 else lo)), cr))
    if p.open_float_pools:
        out += float_pools(ctx, sd, i, p, True)
    return out


def confluence_refs(ctx, sd, i: int, p, buy: bool = True, out_pools: dict | None = None) -> list:
    """Reference pools (side space) for the A2 round-handle confluence: an old high / low or a rel-eq pool - the daily old highs / lows
    (+ prior week / month) and rel-eq pools among `out_pools` (the sell side's dict), the active old pool (active_old_pool) and the
    engineered pools (engineered_pools) [review fix #2: not every other pool of the ladder]."""
    out = []
    if out_pools:
        out += [float(v) for k, v in out_pools.items() if k.startswith(("pdh", "pdl", "pwl", "pml_month", "rel_eq"))]
    if p.active_old_pool:
        v = old_pool(ctx, sd, i, p, buy)
        if v is not None:
            out.append(float(v))
    if p.engineered_pools:
        out += [float(v) for v, *_ in eng_pools(ctx, sd, i, p, buy)]
    return out


def eng_levels(ctx, sd, i: int, p) -> set:
    """The rounded engineered buy-side levels (they rank like rel-eq pools with eq_pref != "off")."""
    return {round(float(v), 9) for v, *_ in eng_pools(ctx, sd, i, p, True)} if p.engineered_pools else set()


def sell_pools(ctx, sd, i: int, p, out: dict) -> None:
    """Sweep pools of this package added to _sell_side's dict (side space); the creation bars are kept for _level_created."""
    cr_map = _c(ctx).setdefault("created", {})
    if p.active_old_pool:
        v = old_pool(ctx, sd, i, p, False)
        if v is not None:
            out["old_lo"] = float(v)
            cr_map["old_lo"] = ctx.start
    if p.engineered_pools:
        sc_map = _c(ctx).setdefault("eng_score", {})
        for v, cr, nm, sc in eng_pools(ctx, sd, i, p, False):
            out[nm] = float(v)
            cr_map[nm] = cr
            sc_map[nm] = sc
    for name, hi, lo, cr in (getattr(ctx, "sors", []) if p.session_ors else []):
        if cr <= i:
            out[name] = float(sd.x(lo if sd.sign > 0 else hi))
            cr_map[name] = cr
    if p.open_float_pools:
        for v, cr in float_pools(ctx, sd, i, p, False):
            nm = f"float_lo{int(round(v * 100))}"
            out[nm] = float(v)
            cr_map[nm] = cr


def eng_score(ctx, k: str) -> float:
    """Ranking score of the engineered sell-side pool `k` (bars between H1 and H2, +1 for an opposing FVG at H1); 0 for any other key."""
    return float(_c(ctx).get("eng_score", {}).get(k, 0.0))


def created(ctx, k: str):
    """The bar from which sell-side pool `k` of this package exists (None: not one of ours)."""
    return _c(ctx).get("created", {}).get(k)


def lock_cands(ctx, p, t_lock: int, kl: int) -> list:
    """mark_levels candidates (real prices) of this package: (value, "pool", name, dir, created)."""
    out = []
    S = ctx.start
    if p.active_old_pool and kl > S:
        ph, pl = daily_piv(ctx, 1)
        v = L.first_old_beyond(ph, float(ctx.h[S:kl].max()))
        if v is not None:
            out.append((float(v), "pool", "old_hi", 1, S))
        v = L.first_old_beyond([-q.price for q in pl], -float(ctx.l[S:kl].min()))
        if v is not None:
            out.append((-float(v), "pool", "old_lo", -1, S))
    for name, hi, lo, cr in (getattr(ctx, "sors", []) if p.session_ors else []):
        if cr <= kl:
            out += [(hi, "pool", name + "_h", 1, cr), (lo, "pool", name + "_l", -1, cr)]
    return out


# --- A2 round handles as confluence ----------------------------------------------------------------------------------

def round_filter(vals: list, refs: list, p) -> list:
    """A2-round-number-pool (002 ~2:37: "the buy side is nice round number 3,900"): the round handles `vals` (side space) per
    Params.round_pool_mode - "pool" unchanged; "confluence" a handle is kept only when an old high / low / rel-eq pool (`refs`, side
    space) lies within round_conf_pts of it; "tag_only" never a pool."""
    if p.round_pool_mode == "pool":
        return list(vals)
    if p.round_pool_mode == "tag_only":
        return []
    tol = p.round_conf_pts * p.es_pt + 1e-9
    return [v for v in vals if any(abs(v - r) <= tol for r in refs)]


def round_tag(ctx, sd, sw, p) -> str:
    """"round_conf" when the swept level coincides (within round_conf_pts) with a round handle of the instrument (real prices; the handle
    step is the front-month one), in the modes "confluence" / "tag_only" - or when the sweep IS a surviving handle."""
    if p.round_pool_mode == "pool":
        return ""
    if str(sw.get("key", "")) == "round":
        return "round_conf"
    st = getattr(ctx, "round_step", 0.0)
    lvl = sw.get("level")
    if not st or lvl is None:
        return ""
    adj = float(ctx.adj[min(sw["ext_i"], len(ctx.adj) - 1)]) if getattr(ctx, "adj", None) is not None else 0.0
    real = sd.x(float(lvl)) - adj
    m = round(real / st) * st
    return "round_conf" if abs(real - m) <= p.round_conf_pts * p.es_pt + 1e-9 else ""


# --- L1 RTH session pools are spent by RTH prints only --------------------------------------------------------------

RTH_POOLS = ("prev_pm", "prev_am", "lunch")


def rth_spent_up(ctx, sd, v: float, cr: int, ext_i, tk: float) -> bool:
    """L1-rth-session-pools (067 ~55:50): a previous PM / AM / lunch pool v (side space) is spent only by RTH prints - bars from 09:30 today
    (after its creation) up to the sweep extreme - never by overnight trade."""
    S = _S()
    a = max(cr, ctx.start, S._idx_at(ctx, 570))
    if ext_i is None or ext_i <= a:
        return False
    return S._spent_up(float(sd.h[a:ext_i].max()), v, tk)


# --- L5 rebalanced NWOG -----------------------------------------------------------------------------------------------

def nwog_levels(ctx, sd, i: int, kind: str, hi: float, lo: float, ce: float, p):
    """L5-partial-redelivery: for an NWOG that the both-way redelivery rebalanced (htf.nwog_rebalanced, known by bar i's close) the ladder
    contributes only its near edge and the exit FVG's near edge - CE and far edge dropped. Returns the level list (side space) or None
    (not rebalanced: the caller adds the usual edges)."""
    reb = getattr(getattr(ctx, "gaps", None), "reb", None)
    if not (p.nwog_rebalanced and reb and kind == "nwog"):
        return None
    r = reb.get((round(float(hi), 6), round(float(lo), 6)))
    if r is None:
        return None
    now = ctx.idx[i] + pd.Timedelta(minutes=ctx.tf)
    if r[0] > now:
        return None
    if len(r) > 3 and r[3] is not None and r[3] <= now:      # review fix #18: a later full redelivery to the far edge un-rebalances it
        return None
    return [sd.x(r[1]), sd.x(r[2])]


# --- A11 balanced ranges ----------------------------------------------------------------------------------------------

def balanced_zones(sd, i: int) -> list:
    """Body-filled balanced ranges (levels.balanced_bodies, side space) known by bar i."""
    zs = sd._lazy("balanced", lambda: L.balanced_bodies(sd.o, sd.h, sd.l, sd.c))
    return [z for z in zs if z.i <= i]


def balanced_filter(sd, i: int, above: float, lv: list, p) -> list:
    """A11-balanced-range-body-filled (098 ~34:57): a balanced range above the entry is REDELIVERED, not rebalanced: its near edge and EQ are
    targets, but nothing is targeted past its EQ without fresh displacement [our interpretation: a close beyond its top since it formed].
    Adds the near edge / EQ as array levels, drops every level beyond the nearest such EQ."""
    if not p.balanced_range:
        return lv
    cap = None
    extra = []
    for z in balanced_zones(sd, i):
        eq = float(z.levels[0])
        if eq <= above:
            continue
        if sd.c[z.i + 1:i + 1].max(initial=-np.inf) > z.top:
            continue                                  # left behind by a fresh displacement
        extra += [(float(z.bottom), "array"), (eq, "array")]
        cap = eq if cap is None else min(cap, eq)
    if cap is None:
        return lv
    tk = 1e-9
    return [(v, k) for v, k in lv if v <= cap + tk] + [x for x in extra if x[0] <= cap + tk]


# --- A12 order block anchor -------------------------------------------------------------------------------------------

def ob_anchor_choice(sd, j: int, k: int, i: int, p) -> str:
    """A12-open-vs-wick-gap-criterion (cc05_015 ~11:32): "closed_in" (anchor on the body / open), "gap" (the wick extreme) or "rule" (the A12 stubby /
    long-wick rule) for the order block candles [j, k]; only with ob_anchor_rule "gap_presence", else "rule"."""
    if p.ob_anchor_rule != "gap_presence":
        return "rule"
    return L.ob_anchor_state(sd.o, sd.h, sd.l, sd.c, j, k, i, p.ob_anchor_passes)


def ob_run_end(sd, j: int) -> int:
    """The last candle of the down-close run that starts at j (the blended order block's run)."""
    k = j
    while k + 1 < len(sd.c) and sd.c[k + 1] < sd.o[k + 1]:
        k += 1
    return k


# --- A5 VI linked to an FVG ------------------------------------------------------------------------------------------

def vi_link(sd, g, z, tk: float, p) -> str:
    """A5-vi-extended-ce (098 ~1:09:26 / ~1:09:42: "you have to incorporate the entirety of that"): how the volume imbalance z relates to the entry gap g
    (side space, tk = the touch tolerance): "inside" (a VI within the gap: its top is the exact limit), "up" / "down" (a VI joined to the gap's top /
    bottom - by the bodies within a tick, or with `fvg_vi_extend_ce` by a WICK: the candle below the VI reaches the gap top / the VI's upper candle
    reaches the gap bottom - extends the zone to the VI's far body edge, and the zone's CE moves with it), or ""."""
    if z.bottom >= g.bottom - 1e-9 and z.top <= g.top + 1e-9:
        return "inside"
    wick_up = p.fvg_vi_extend_ce and z.bottom > g.top and sd.l[z.i - 1] <= g.top + tk + 1e-9
    wick_dn = p.fvg_vi_extend_ce and z.top < g.bottom and sd.h[z.i] >= g.bottom - tk - 1e-9
    if (z.bottom <= g.top + tk + 1e-9 or wick_up) and z.top > g.top:
        return "up"
    if (z.top >= g.bottom - tk - 1e-9 or wick_dn) and z.bottom < g.bottom:
        return "down"
    return ""


# --- A6 breakaway classes ---------------------------------------------------------------------------------------------

def gap_class(sd, ext_i: int, ext: float, g, i: int, p, leg_hi: float | None = None) -> str:
    """A6-gap-hierarchy-common (062 ~39:41 / ~43:58: "gaps are just like a PD array matrix, they have a hierarchy"): the class of FVG g of the leg that
    starts at the sweep extreme - "breakaway" (targets.breakaway_gap: the shift's gap, per bk_depth / bk_state), "measuring" (the gap near the
    leg's middle, targets.measuring_gap), else "common"."""
    from . import targets as T
    ba = T.breakaway_gap(sd, ext_i, i, p)
    if ba is not None and ba == g:
        return "breakaway"
    hi = leg_hi if leg_hi is not None else float(sd.h[ext_i:i + 1].max())
    mg = T.measuring_gap(sd, dict(ext=ext, ext_i=ext_i), i, hi, p)
    if mg is not None and mg == g:
        return "measuring"
    return "common"


def trail_ok(sd, pos: dict, g, i: int, p) -> bool:
    """A6 trail_skip_common [our interpretation]: never trail behind a COMMON gap."""
    if not p.trail_skip_common:
        return True
    leg = pos.get("leg")
    hi = max(leg[1], float(sd.h[pos["ext_i"]:i + 1].max())) if leg else None      # the position's leg high (as the measuring-gap trail reads it)
    return gap_class(sd, pos["ext_i"], pos["ext"], g, i, p, hi) != "common"


def cc_common_tag(sd, entry: float, i: int) -> bool:
    """True when `entry` (side space) lies in a CC body gap (levels.common_gaps_cc, bull kind) known by bar i."""
    zs = sd._lazy("cc_common", lambda: [z for z in L.common_gaps_cc(sd.o, sd.h, sd.l, sd.c) if z.kind == "bull"])
    return any(z.i <= i and z.bottom - 1e-9 <= entry <= z.top + 1e-9 for z in zs)


# --- A9 breakaway VI --------------------------------------------------------------------------------------------------

def vi_is_breakaway(sd, sw: dict, z, i: int) -> bool:
    """A9-vi-breakaway (079 ~14:20; 103 ~25:18): the bullish VI z is a breakaway VI (levels.vi_breakaway) and no later body has laid fully across it
    (then it was not breakaway)."""
    r = L.vi_breakaway(sd.o, sd.h, sd.l, sd.c, z, broke=sw.get("broke"), ext=sw.get("ext"), ext_i=sw.get("ext_i"),
                       leg_hi=float(sd.h[sw["ext_i"]:i + 1].max()) if sw.get("ext_i") is not None else None)
    if not r:
        return False
    return L.vi_body_dead(sd.o, sd.c, z, None, i) is None


def opp_vi_is_breakaway(sd, z, i: int) -> bool:
    """A9-vi-breakaway for an OPPOSING (bearish, side space) VI used as a retrace target: it left a consolidation (the context test on the mirrored
    bars; the MSS / leg clauses need the setup of its own leg, which a target has none of) and no later body has laid fully across it."""
    m = sd._lazy("mirror", lambda: (-sd.o, -sd.l, -sd.h, -sd.c))
    zz = L.Zone("bull", -z.bottom, -z.top, z.i, z.src)
    return bool(L.vi_breakaway(m[0], m[1], m[2], m[3], zz)) and L.vi_body_dead(sd.o, sd.c, z, None, i) is None


# --- L7 ORG direction -------------------------------------------------------------------------------------------------

def org_dir(ctx, i: int) -> str:
    """L7-org-close-and-direction (069 ~10:03 / ~11:05: "we are opening with a discount opening range gap"): "discount" when the 09:30 open is below the
    prior RTH close (ORG high = the prior close, low = the open), "premium" above it, from the 09:30 bar on; "" before it / without an ORG."""
    if not (getattr(ctx, "org_today", False) and ctx.org and ctx.t[i] >= 570):
        return ""
    pc, op = ctx.org[-1]
    return "discount" if op < pc else "premium" if op > pc else ""


# --- M1 original consolidation ----------------------------------------------------------------------------------------

def orig_consol_level(sd, q, e: int, i: int, p, win: int = 30):
    """M1-original-consolidation (104 ~27:53): the smooth-edge upper bound U of the original consolidation around the parent swing high q (side
    space): levels.smooth_edge_range over the bars from `win` before q to min(q's neighbourhood, the sweep extreme e, i). None when there is no
    level with orig_consol_touches touches within orig_consol_tol_pts."""
    a = max(0, q.i - win)
    b = min(q.i + win, e, i)
    r = L.smooth_edge_range(sd.o, sd.h, sd.l, sd.c, p.orig_consol_tol_pts * p.es_pt, p.orig_consol_touches, a, b)
    return None if r is None else r[0]


# --- B21 data range: fair value gaps and consolidation EQs ------------------------------------------------------------

def build_ipda_x(ctx, hist: list, dates: list, eth, p) -> tuple:
    """B21-data-range-fv-eq (cc05_003 ~1:18:00: "that's where your equilibrium price points are"): from the daily candles of the 60 sessions the IPDA windows
    end on, (gaps, eqs): the open daily FVGs (not yet traded across by a later session) as [(top, bottom)] and the consolidations' EQs as
    [(eq, height)] (levels.daily_consolidations). Real prices, all known before today. ETH candles when ipda_session is "eth" and the
    frame has them (like the IPDA ranges)."""
    n = len(hist)
    last = getattr(ctx, "ipda_last", None)
    end = n
    if last is not None and last in dates:
        end = dates.index(last) + 1
    a = max(0, end - 60)
    rows = []
    for d, x in zip(dates[a:end], hist[a:end]):
        e = eth.get(d) if (eth and p.ipda_session == "eth") else None
        rows.append(e if e is not None else (float(x.open.iloc[0]), float(x.high.max()), float(x.low.min()), float(x.close.iloc[-1])))
    if len(rows) < 5:
        return [], []
    o, h, l, c = (np.array([r[k] for r in rows], float) for k in range(4))
    gaps = []
    if p.ipda_fv:
        for z in L.fvgs(h, l, o, c):
            later = slice(z.i + 1, None)
            if not (len(h[later]) and ((l[later] <= z.bottom) & (h[later] >= z.top)).any()):
                gaps.append((float(z.top), float(z.bottom)))
    eqs = []
    if p.ipda_consol_eq:
        eqs = [(b["eq"], b["high"] - b["low"]) for b in L.daily_consolidations(o, h, l, c, eq_touches=p.consol_eq_touches)]
    return gaps, eqs


def ipda_arrays(ctx, sd, p) -> list:
    """Array targets (side space) of the IPDA data range: the open daily gaps' near edge and CE, the consolidations' EQs."""
    out = []
    for top, bot in getattr(ctx, "ipda_gaps", []):
        a, b = sorted((sd.x(top), sd.x(bot)))
        out += [(float(a), "array"), (float((a + b) / 2), "array")]
    out += [(float(sd.x(eq)), "array") for eq, _ in getattr(ctx, "ipda_ceq", [])]
    return out


def consol_eq_day(ctx, p, i: int) -> bool:
    """B21 (cc05_003 ~1:18:00) "range (Z) day": the 09:30 open (the last close before it) hangs within ipda_eq_frac of a daily consolidation's height of its EQ
    and there is no driver - no CPI / NFP / FOMC today [our interpretation: for an index no driver = no high-impact news]."""
    from claude_hf.daytypes import events
    eqs = getattr(ctx, "ipda_ceq", [])
    if not eqs or events(ctx.day) & {"cpi", "jobs", "fomc"}:
        return False
    S = _S()
    k = S._idx_at(ctx, 570)
    px = float(ctx.o[k]) if (k < len(ctx.t) and k <= i) else float(ctx.c[i])
    return any(abs(px - eq) <= p.ipda_eq_frac * max(h_, 1e-9) for eq, h_ in eqs)
