"""Caption-gap pass (digests/rulebook_gaps/*.md), package targets_partials, chunk 2 of 4: the engine glue of its 33 specs -
levels_liquidity_targets.md 15, 16, 17, 20, 24, 27, 37, 39, 41, 43, 45, 48, 49, 50, 51, 52, 53, 54, 56, 60, 61, 62, 65, 66, 83, 85, 86, 88, 89, 94, 98, 99, 101.

Same conventions as tp1.py: side space (shorts run mirrored prices), a bar is used only after it closes (`i` = the last CLOSED bar, an order armed on it fills from
bar i+1), an object only from the bar that completes it. Every function sits behind a Params switch of the "caption-gap pass, targets_partials #2/4" block;
interpretations the sources do not pin down are marked [our interpretation]. `HITS` is sm2's counter dict (tests: proof that a switch's code path RAN).

Sections: 1 validation - 2 pool helpers - 3 hook T (strategy._targets: pool filters, the pools / arrays the chunk adds) - 4 hook R (strategy._finish_order: raw
rung changes) - 5 draw preferences - 6 hook L (the ladder after the draw: ORG family, NWOG ladder, final-target picks, resistance runs) - 7 SD engine pieces
(targets.sd_ranges / sd_levels / extra_sources) - 8 mid-trade management - 9 scoring."""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

from . import levels as L
from . import sm2

HITS = sm2.HITS
hit = sm2.hit

POOLK = ("pool", "pool_eq")
SESSION_BASE = ("prev_pm", "london")                  # L14-session-pools-only (067 ~00:27:37)
SESSION_EXT = ("lunch", "am", "am_session", "prev_am")
S_LAST_HOUR = 900                                      # L12-minus3-sd-last-hour (047 ~00:10:59): the last hour starts at 15:00


def _S():
    from . import strategy as S
    return S


def _TP():
    from . import targets as TP
    return TP


def _T1():
    from . import tp1 as T1
    return T1


def _BD():
    from . import bias_day as BD
    return BD


# --- 1. validation ----------------------------------------------------------------------------------------------------------------------------------

def check_params(p) -> None:
    """Validation of the chunk's Params (strategy.Params.__post_init__) and the inert-switch notes."""
    for name, ok in (("eq_leg", ("sweep", "rally")), ("session_pools_mode", ("off", "rank", "only", "extended")), ("sd_arm", ("trade", "close")),
                     ("htf_gap_final", ("ce", "far_edge")), ("room_ref", ("exit", "htf_far")), ("sd_fulcrum_def", ("ep06", "inception"))):
        if getattr(p, name) not in ok:
            raise ValueError(f"{name} {getattr(p, name)!r}: expected one of {ok}")
    bad = [t for t in p.sd_multi_tiers if t not in ("itl", "ltl")]
    if bad:
        raise ValueError(f"sd_multi_tiers {bad}: expected from ('itl', 'ltl')")
    if (p.sd_arm_bars < 1 or p.sd_cluster_min < 2 or p.proj_exit_ticks < 0 or p.sd_htf_tol < 0 or p.sd_last_hour_k < 0 or p.proj_org_kmax < 1 or p.sd_conv_ticks < 0
            or p.hrlr_time_k < 0 or p.linger_bars < 1 or p.linger_pts < 0 or p.consol_min_bars < 2 or p.consol_max_adr <= 0 or p.org_beyond_adr <= 0
            or p.beyond_pool_adr <= 0 or p.break_accel_mult <= 0 or p.confl_tol_frac <= 0 or p.defended_band_adr <= 0 or p.defended_touches < 1 or p.defended_bars < 1
            or not 0 <= p.min_obj_frac < 1 or not 0 <= p.nwog_near_frac <= 1 or not 0 <= p.nwog_ce_frac <= 1 or p.nwog_near_frac + p.nwog_ce_frac > 1 + 1e-9
            or not p.proj_breaker_k or any(k <= 0 for k in p.proj_breaker_k)):
        raise ValueError("targets_partials #2/4: sd_arm_bars >= 1; sd_cluster_min >= 2; proj_exit_ticks, sd_htf_tol, sd_last_hour_k, sd_conv_ticks, hrlr_time_k, linger_pts >= 0; proj_org_kmax, "
                         "linger_bars, defended_touches, defended_bars >= 1; consol_min_bars >= 2; consol_max_adr, org_beyond_adr, beyond_pool_adr, break_accel_mult, confl_tol_frac, "
                         "defended_band_adr > 0; min_obj_frac in [0, 1); nwog_near_frac, nwog_ce_frac in [0, 1] with a sum <= 1; proj_breaker_k a non-empty tuple of multiples > 0")
    inert = []
    sd_needed = [n for n, on in (("sd_arm", p.sd_arm != "trade"), ("sd_ref_roll", p.sd_ref_roll), ("sd_cap_htf", p.sd_cap_htf), ("sd_multi_tiers", bool(p.sd_multi_tiers)),
                                 ("sd_htf_extreme", p.sd_htf_extreme), ("sd_premium_consol", p.sd_premium_consol), ("sd_last_hour_k", p.sd_last_hour_k > 0),
                                 ("sd_deep_conv", p.sd_deep_conv)) if on]
    if sd_needed and not p.sd_targets:
        inert.append(", ".join(sd_needed) + " act on the SD levels: they need sd_targets=True")
    if p.sd_htf_extreme and p.sd_anchor != "m15_leg":
        inert.append("sd_htf_extreme reads the sd_anchor 'm15_leg' leg")
    if p.sd_last_hour_k > 0 and p.sd_anchor != "mss_leg":
        inert.append("sd_last_hour_k reads the sd_anchor 'mss_leg' leg")
    if p.eq_beyond_imb and not p.draw_below_eq:
        inert.append("eq_beyond_imb acts on the draw_below_eq pick")
    if p.nwog_ladder and not (p.draw_lock == "session" or p.nwog_halfway):
        pass                                           # (an NWOG draw can also come from the ladder: no note)
    if inert:
        warnings.warn("inert switches (targets_partials #2/4): " + "; ".join(inert), stacklevel=4)


def targets_on(p) -> bool:
    """True when a switch that acts inside strategy._targets / the raw rung hooks is on."""
    return bool(p.session_pools_mode in ("only", "extended") or p.defended_filter or p.break_accel_gate or p.swept_pool_targets or p.event_horizon_target
                or p.nwog_magnet or p.overnight_5m_fvgs or p.htf_ob_open or p.htf_gap_gate or p.keep_traded_wfvg or p.min_obj_frac > 0 or p.beyond_pool_final
                or p.confl_rank)


def any_on(p) -> bool:
    """True when the state dict of _finish_order is needed (the late hook)."""
    return bool(targets_on(p) or p.session_pool_first or p.nwog_ladder or p.org_beyond or p.org_ce_if_flow or p.org_breaker_stop or p.hrlr_time_k > 0 or p.clear_path
                or p.sd_last_hour_k > 0 or p.sd_multi_tiers or p.sd_deep_conv or p.sd_htf_extreme or p.eq_beyond_imb or p.t1_skip_near or p.room_ref != "exit"
                or p.proj_exit_ticks > 0 or p.sd_anchor == "entry_low")


def sd_on(p) -> bool:
    """True when the new SD engine (targets.sd_levels) must run for a switch of this chunk."""
    return bool(p.sd_arm != "trade" or p.sd_ref_roll or p.sd_cap_htf or p.sd_multi_tiers or p.sd_htf_extreme or p.sd_premium_consol or p.sd_last_hour_k > 0
                or p.sd_deep_conv or p.sd_fulcrum_def != "ep06")


# --- 2. pool helpers --------------------------------------------------------------------------------------------------------------------------------

def _st(ctx) -> dict:
    d = ctx.__dict__.get("_tp2_st")
    if d is None:
        d = ctx.__dict__["_tp2_st"] = dict(tags=[], prefs=[])
    return d


def named_pools(ctx, sd, i: int, opposite: bool = False) -> list:
    """The named day / session pools in side space as (value, created bar index, name), known at bar i. Target type (opposite=False): the buy-side highs of a long (the
    sell-side lows of a short); opposite=True: the other type (the lows a long's session swept). Names: pdh1.. / pdl1.., pmh / pml, the ctx.sess ranges (prev_pm, london,
    lunch ...), 'or', 'am'."""
    S = _S()
    hi_real = (sd.sign > 0) != opposite
    at = lambda m: S._idx_at(ctx, m)
    out = []
    for k in (("pdh1", "pdh2", "pdh3") if hi_real else ("pdl1", "pdl2", "pdl3")):
        if k in ctx.pd:
            out.append((float(sd.x(ctx.pd[k])), ctx.start, k))
    k = "pmh" if hi_real else "pml"
    if ctx.t[i] >= 570 and k in ctx.pd:
        out.append((float(sd.x(ctx.pd[k])), at(570), k))
    for name, (hi, lo, ready) in getattr(ctx, "sess", {}).items():
        if ctx.t[i] >= ready:
            out.append((float(sd.x(hi if hi_real else lo)), ctx.start if name == "prev_pm" else at(ready), name))
    if getattr(ctx, "or_hl", None) is not None and ctx.t[i] >= ctx.or_end:
        out.append((float(sd.x(ctx.or_hl[0] if hi_real else ctx.or_hl[1])), at(ctx.or_end), "or"))
    ae = min(810, getattr(ctx, "am_end", 810))
    if ctx.t[i] >= ae and getattr(ctx, "am_hl", None):
        out.append((float(sd.x(ctx.am_hl[0] if hi_real else ctx.am_hl[1])), at(ae), "am"))
    return out


def _near(v: float, vals, tol: float = 1e-6) -> bool:
    return any(abs(v - w) <= tol for w in vals)


def _drop_vals(lv: list, vals, kinds=None, tol: float = 1e-6) -> list:
    return [(v, k) for v, k in lv if not ((kinds is None or k in kinds) and _near(v, vals, tol))]


def _adr(ctx):
    S = _S()
    return S.adr5(list(getattr(ctx, "hist", None) or [])[-5:])


def _zone_edges(sd, row):
    return _TP()._zone_edges(sd, row)


def _now(ctx, i: int):
    return _TP().now_ts(ctx, i)


def is_news_day(ctx) -> bool:
    """A jobs / FOMC day (the release is the driver; L4-resistance-runs news exception)."""
    from claude_hf.daytypes import events
    ev = events(ctx.day)
    return "jobs" in ev or "fomc" in ev


def nwog_zones(ctx, sd, i: int) -> list:
    """The stored NWOGs in side space as (low, high, ce, real (hi, lo, ce)), sorted by price. ETH 'nwog' rows only (their RTH twins would duplicate them)."""
    S = _S()
    out = []
    if getattr(ctx, "gaps", None) is not None:
        raw = [(hi, lo, ce) for kind, hi, lo, ce in ctx.gaps if kind == "nwog"] or [(hi, lo, ce) for kind, hi, lo, ce in ctx.gaps if kind == "nwog_rth"]
    else:
        raw = [(max(a, b), min(a, b), (a + b) / 2) for a, b in S._nwogs(ctx, i)]
    for hi, lo, ce in raw:
        a, b = float(sd.x(hi)), float(sd.x(lo))
        out.append((min(a, b), max(a, b), float(sd.x(ce)), (hi, lo, ce)))
    return sorted(out)


# --- 3. hook T: strategy._targets -------------------------------------------------------------------------------------------------------------------

def targets_post(ctx, sd, i: int, p, above: float, lv: list, eq, ext_i) -> list:
    """The pool filters and the pools / arrays this chunk adds to the buy-side list of strategy._targets (side space, before the ~1 pt merge). State and tags of the call
    are kept in ctx._tp2_st (the order stage reads them)."""
    st = ctx.__dict__["_tp2_st"] = dict(tags=[], prefs=[])
    if p.session_pools_mode in ("only", "extended"):
        lv = session_filter(ctx, sd, i, p, lv)
    if p.defended_filter:
        lv = defended(ctx, sd, i, p, lv, st)
    if p.break_accel_gate:
        lv = break_accel(ctx, sd, i, p, lv, st)
    add = []
    if p.swept_pool_targets:
        add += swept_targets(ctx, sd, i, p, above, lv, st)
    if p.overnight_5m_fvgs:
        add += overnight_fvgs(ctx, sd, i, p, above)
    if p.htf_ob_open and getattr(ctx, "conf", None) is not None:
        add += htf_ob(ctx, sd, i, p, above, st)
    if p.event_horizon_target:
        lv, a = event_horizon(ctx, sd, i, p, above, lv, st)
        add += a
    if p.nwog_magnet:
        add += magnet(ctx, sd, i, p, above, st)
    if add:
        lv = list(lv) + [(float(v), k) for v, k in add if v > above]
    return lv


def session_filter(ctx, sd, i: int, p, lv: list) -> list:
    """L14-session-pools-only (067 ~00:27:37): 'only' keeps the buy-side pools of the previous PM and London ranges, the ORG edges and PDH / PDL; 'extended' adds the lunch / AM
    ranges and the relative equal highs lying inside the previous PM / London ranges [our interpretation]. Arrays are not pools: they stay."""
    allowed, ranges = [], []
    for v, cr, nm in named_pools(ctx, sd, i):
        if nm in SESSION_BASE or nm.startswith(("pdh", "pdl")) or (p.session_pools_mode == "extended" and nm in SESSION_EXT):
            allowed.append(v)
    if getattr(ctx, "org_today", False) and getattr(ctx, "org", None):
        allowed += [float(sd.x(x)) for x in ctx.org[-1]]
    if p.session_pools_mode == "extended":
        for nm in SESSION_BASE:
            if nm in getattr(ctx, "sess", {}):
                hi, lo, _ = ctx.sess[nm]
                a, b = float(sd.x(hi)), float(sd.x(lo))
                ranges.append((min(a, b), max(a, b)))
    out = [(v, k) for v, k in lv if k not in POOLK or _near(v, allowed, 0.01 * p.es_pt) or (k == "pool_eq" and any(a <= v <= b for a, b in ranges))]
    if len(out) < len(lv):
        hit("session_pools_filter")
    return out


def _visits(inband) -> int:
    """Distinct visits: consecutive in-band bars are one touch (the pool's own pivot bar and its neighbours are the first visit, not four)."""
    a = np.asarray(inband, bool)
    return int((a & ~np.concatenate(([False], a[:-1]))).sum()) if a.size else 0


def defended(ctx, sd, i: int, p, lv: list, st: dict) -> list:
    """new-defended-level (cc01_007 ~00:24:23): a pool whose level the last defended_bars bars touched (a high within defended_band_adr x ADR5 of it; consecutive in-band bars are one visit) at least
    defended_touches times is defended - not a target (tag defended)."""
    hit("eval_defended")
    adr = _adr(ctx)
    if not adr:
        return lv
    x = p.defended_band_adr * adr
    hs = sd.h[max(0, i + 1 - p.defended_bars):i + 1]
    out = []
    for v, k in lv:
        if k in POOLK and _visits(np.abs(hs - v) <= x + 1e-9) >= p.defended_touches:
            st["tags"].append("defended")
            hit("defended")
            continue
        out.append((v, k))
    return out


def break_accel(ctx, sd, i: int, p, lv: list, st: dict) -> list:
    """new-pool-break-accel-vs-reject (072 ~00:01:21): the highest buy-side pool taken today decides whether the pools beyond it are still draws - they stay when the break
    ACCELERATED (a bar of the first three from the break with a body >= break_accel_mult x the mean body of the 10 bars before it, closing beyond the pool, and an FVG left by
    them), they go when the break is not displaced or any close since came back below the pool [our interpretation of the A20 displacement test]."""
    S = _S()
    hit("eval_break_accel")
    tk = S._tick(p)
    taken = []
    for v, cr, nm in named_pools(ctx, sd, i):
        a = max(cr, ctx.start)
        if a < i:
            m = sd.h[a:i + 1] >= (v + tk - 1e-9 if tk > 0 else v)
            if m.any():
                taken.append((v, a + int(np.argmax(m))))
    if not taken:
        return lv
    v1, kb = max(taken)
    deeper = [(v, k) for v, k in lv if k in POOLK and v > v1 + p.es_pt]
    if not deeper:
        return lv
    body = np.abs(sd.c - sd.o)
    mb = float(body[max(0, kb - 10):kb].mean()) if kb > 0 else float(body[kb:min(kb + 3, i + 1)].mean())
    w = range(kb, min(kb + 3, i + 1))
    big = any(body[j] >= p.break_accel_mult * mb and sd.c[j] > v1 for j in w)
    fvg = any(kb <= z.i <= min(kb + 2, i) for z in sd.gaps)
    back = bool((sd.c[kb:i + 1] <= v1).any())
    if big and fvg and not back:
        st["tags"].append("break_accel")
        hit("break_accel_keep")
        return lv
    st["tags"].append("break_reject")
    hit("break_accel_drop")
    return [x for x in lv if x not in deeper]


def swept_targets(ctx, sd, i: int, p, above: float, lv: list, st: dict) -> list:
    """new-old-pool-redelivery (072 ~00:36:04): the pools of the OPPOSITE type that today's bars swept (a long's session took sell-side lows, which now sit above price)
    are re-delivery targets - kind 'array', never an entry level - when the day's bias is with the trade or another ladder level lies within 1 pt of them."""
    S = _S()
    hit("eval_swept")
    tk = S._tick(p)
    want = 0
    try:
        want = int(_BD().want_at(ctx, p, getattr(ctx, "_tp2_session", "AM"), i))
    except Exception:
        want = 0
    out = []
    for v, cr, nm in named_pools(ctx, sd, i, opposite=True):
        a = max(cr, ctx.start)
        if a >= i or v <= above:
            continue
        lo_seen = float(sd.l[a:i + 1].min())
        swept = lo_seen <= v - tk + 1e-9 if tk > 0 else lo_seen < v
        if swept and (want == sd.sign or any(abs(w - v) <= p.es_pt for w, _ in lv)):
            out.append((v, "array"))
            st["tags"].append("swept_pool")
            hit("swept_pool")
    return out


def overnight_fvgs(ctx, sd, i: int, p, above: float) -> list:
    """X1-london-0300-fvg-draw (018 ~00:03:49): the open 5m FVGs formed between the previous 18:00 and 09:30 (the frame must be 5 minutes) beyond `above`: near edge, CE, far edge."""
    S = _S()
    hit("eval_on_fvg")
    if ctx.tf != 5:
        return []
    k570 = S._idx_at(ctx, 570)
    out = []
    for z in sd.opposing():
        if z.i > i or z.i >= k570 or z.bottom <= above or sd.h[z.i + 1:i + 1].max(initial=-np.inf) >= z.bottom:
            continue
        ts = ctx.idx[z.i]
        mod = ts.hour * 60 + ts.minute
        if (ts.date() == ctx.day and mod < 570) or (ts.date() < ctx.day and mod >= 1080):
            out += [(float(z.bottom), "array"), (float(z.mid), "array"), (float(z.top), "array")]
    if out:
        hit("overnight_5m_fvg")
    return out


def htf_ob(ctx, sd, i: int, p, above: float, st: dict) -> list:
    """X1-htf-ob-open-target (058 ~00:08:20): an opposing daily / weekly OB gives its near edge and its candle open as rungs; with htf_ob_open_final the open of the nearest one
    is the final target when no FVG / VI lies between `above` and it (state: ob_open_final)."""
    hit("eval_htf_ob")
    rows = ctx.conf.opposing_ext(_now(ctx, i), sd.x(above), sd.sign, ("D", "W"), (1,))
    out = []
    for n, r in enumerate(rows):
        near, far = _zone_edges(sd, r)
        opn = r.get("opn")
        out.append((float(near), "array"))
        if opn is not None and opn == opn:
            v = float(sd.x(opn))
            if v > above:
                out.append((v, "array"))
                if n == 0 and p.htf_ob_open_final and _T1()._clear_path(ctx, sd, i, p, above, near):
                    st["ob_open_final"] = v
        st["tags"].append("htf_ob_open")
        hit("htf_ob_open")
    return out


def event_horizon(ctx, sd, i: int, p, above: float, lv: list, st: dict) -> tuple:
    """L5-event-horizon-objective (037 ~00:22:37; 051 ~16:51): k = the highest NWOG whose low edge price has reached; the event horizon = the midpoint between its near (top)
    edge and the next NWOG's near (bottom) edge. Until a high traded one tick through it the next NWOG's levels are out of the ladder and the midpoint is a rung."""
    hit("eval_event_horizon")
    zs = nwog_zones(ctx, sd, i)
    px = float(sd.c[i])
    below = [z for z in zs if z[0] <= px]
    if not below:
        return lv, []
    k = max(below, key=lambda z: z[0])
    nxt = [z for z in zs if z[0] > k[1]]
    if not nxt:
        return lv, []
    n1 = min(nxt, key=lambda z: z[0])
    mid = (k[1] + n1[0]) / 2
    tk = max(p.tick, 0.0)
    if float(sd.h[ctx.start:i + 1].max()) >= mid + tk - 1e-9:
        return lv, []
    r = n1[1] - n1[0]
    vals = [n1[0], n1[1], n1[2], n1[0] + 0.25 * r, n1[0] + 0.75 * r]
    out = _drop_vals(lv, vals, ("array",))
    st["tags"].append("event_horizon")
    hit("event_horizon")
    return out, ([(float(mid), "array")] if mid > above else [])


def magnet(ctx, sd, i: int, p, above: float, st: dict) -> list:
    """L5-old-nwog-in-consolidation (044 ~01:18:34; 051 ~00:17:37): (a) for every untaken daily swing high ahead the price band of its 3-bar consolidation (the bodies of the pivot
    bar +-1): a stored NWOG overlapping it is the nwog_magnet; (b) a consolidation of the last consol_min_bars bars within consol_max_adr x ADR5: the NWOG running through it
    is the range_anchor. Their near edges are the preferred draw (st['prefs']); the NWOG edges are rungs."""
    hit("eval_magnet")
    zs = nwog_zones(ctx, sd, i)
    if not zs:
        return []
    out = []
    hist = list(getattr(ctx, "hist", None) or [])[-60:]
    if len(hist) >= 3:
        H = np.array([float(f.high.max()) if sd.sign > 0 else -float(f.low.min()) for f in hist])
        O = np.array([sd.sign * float(f.open.iloc[0]) for f in hist])
        C = np.array([sd.sign * float(f.close.iloc[-1]) for f in hist])
        for k in range(1, len(hist) - 1):
            if not (H[k] > H[k - 1] and H[k] >= H[k + 1]) or H[k] <= above or H[k + 1:].max(initial=-np.inf) >= H[k]:
                continue
            bo = np.minimum(O[k - 1:k + 2], C[k - 1:k + 2])
            bt = np.maximum(O[k - 1:k + 2], C[k - 1:k + 2])
            for lo_s, hi_s, ce_s, raw in zs:
                if lo_s <= bt.max() and hi_s >= bo.min() and hi_s > above:
                    near = lo_s if lo_s > above else (ce_s if ce_s > above else hi_s)
                    st["prefs"].append((float(near), "array", "nwog_magnet"))
                    st["tags"].append("nwog_magnet")
                    out += [(lo_s, "array"), (ce_s, "array"), (hi_s, "array")]
                    hit("nwog_magnet")
    adr = _adr(ctx)
    if adr:
        band = L.consolidation_band(sd.h, sd.l, i, p.consol_min_bars, p.consol_max_adr * adr)
        if band is not None:
            for lo_s, hi_s, ce_s, raw in zs:
                if lo_s <= band[1] and hi_s >= band[0] and hi_s > above:
                    st["tags"].append("range_anchor")
                    for v in (lo_s, hi_s):
                        if v > above:
                            out.append((v, "array"))
                    near = lo_s if lo_s > above else hi_s
                    st["prefs"].append((float(near), "array", "range_anchor"))
                    hit("range_anchor")
    return out


# --- 4. hook R: strategy._finish_order (raw rungs) ----------------------------------------------------------------------------------------------------

def raw_post(ctx, sd, i: int, p, session: str, entry: float, risk: float, above: float, sw: dict, lv: list, lvt: list, st2: dict) -> list:
    """The raw (level, kind) rungs of the order before the exit prices: the HTF FVG CE-first gate, the kept traded weekly FVG edges and the minimum-objective wick CEs. `st2` carries
    what the late hook needs."""
    S = _S()
    tgs = _st(ctx)["tags"]
    out = list(lv)
    conf = getattr(ctx, "conf", None)
    if p.htf_gap_gate and conf is not None:
        hit("eval_htf_gap")
        ns = _TP()._ns(ctx)[:i + 1]
        row = _T1()._row(ctx, session, i)
        flip_ok = int((row or {}).get("flip") or 0) != -sd.sign if p.htf_gap_final == "far_edge" else False
        for r in conf.opposing_ext(_now(ctx, i), sd.x(above), sd.sign, ("15m", "30m", "1h", "4h", "D"), (0,)):
            near, far = _zone_edges(sd, r)
            if far - near <= 0:
                continue
            ce = (near + far) / 2
            m = ns >= r["known"]
            if flip_ok or bool((sd.c[:i + 1][m] > ce).any()):
                continue
            n0 = len(out)
            out = _drop_vals(out, [near + 0.75 * (far - near), far], ("array",))
            if len(out) < n0:
                lvt.append("htf_gap_ce_first")
                hit("htf_gap_gate")
    if p.keep_traded_wfvg and conf is not None:
        hit("eval_wfvg")
        now_ns = float(_now(ctx, i).value)
        add = []
        for r in conf.rows(("W",), (0,)):
            if r["kind"] == -sd.sign and r["known"] <= now_ns and r["dead"] <= now_ns:
                a, b = _zone_edges(sd, r)
                add += [(float(a), "array"), (float(b), "array")]
        if add:
            out = sorted(set(out) | {(v, k) for v, k in add if v > above})
            lvt.append("wfvg_kept")
            hit("keep_traded_wfvg")
    if p.min_obj_frac > 0:
        hit("eval_min_obj")
        w = sorted(x[0] for x in _TP().tf_wicks(ctx, sd, i, p, ("1h", "4h"), above, True))     # (the minimum objective is a LONG 1h / 4h wick whatever wick_long_only says)
        if w:
            st2["min_obj"] = w
    out = sorted(set(out))
    for t in dict.fromkeys(tgs):
        lvt.append(t)
    return out


def skip_near(keep: list, entry: float, p) -> tuple:
    """L15-first-sth-offering-5 (012 ~00:32:07): the pools nearer than min_draw_pts are dropped from the ladder - T1 is the first pool that offers the room. Returns
    (keep, ok); ok False when pools existed but none offers the room (the order is rejected)."""
    need = p.min_draw_pts * p.es_pt
    pools = [(v, k) for v, k in keep if k in POOLK]
    if not pools:
        return keep, True
    out = [(v, k) for v, k in keep if not (k in POOLK and v - entry < need)]
    hit("t1_skip_near")
    return out, any(k in POOLK for _, k in out)


def room(ctx, sd, i: int, p, entry: float, above: float, draw: float) -> float:
    """L15-room-measure-anchors (024 ~00:25:13): the room to the draw. 'exit' = the draw's exit price - the entry (built); 'htf_far' = the far edge of the nearest opposing 15m+ array
    beyond the entry - the entry (falls back to the draw's exit)."""
    if p.room_ref == "htf_far" and getattr(ctx, "conf", None) is not None:
        hit("eval_room_htf")
        rows = ctx.conf.opposing_ext(_now(ctx, i), sd.x(entry), sd.sign, ("15m", "30m", "1h", "4h", "D", "W"), (0,))
        if rows:
            hit("room_htf_far")
            return float(_zone_edges(sd, rows[0])[1] - entry)
    return float(draw - entry)


# --- 5. draw preferences ----------------------------------------------------------------------------------------------------------------------------

def draw_prefs(ctx, sd, i: int, entry: float, p, session: str, keep: list) -> list:
    """The draw preferences of this chunk (exit prices, kind, name): the NWOG magnet / range anchor, the open of an HTF OB, the projection clusters and last-hour SD (`rank` also
    sorts the session pools first through session_first)."""
    st = _st(ctx)
    S = _S()
    out = []
    for v, k, n in st.get("prefs", []):
        out.append((S._exit_px(v, k, p), k, n))
    if st.get("ob_open_final") is not None:
        out.append((S._exit_px(st["ob_open_final"], "array", p), "array", "htf_ob_open"))
    for v, k in keep:
        if k in ("proj_cluster", "proj_runner"):
            out.append((v, k, k))
    if p.session_pools_mode == "rank":          # L14-session-pools-only (067 ~00:27:37): the nearest session-range pool of the ladder is the preferred draw
        vals = [v for v, cr, nm in named_pools(ctx, sd, i) if nm in SESSION_BASE + SESSION_EXT or nm.startswith(("pdh", "pdl"))]
        TP = _TP()
        near = [(v, k) for v, k in keep if k in POOLK and _near(TP._raw(v, k, p), vals, 0.01 * p.es_pt) and v > entry]
        if near:
            v, k = min(near)
            out.append((v, k, "session_pool"))
            hit("session_pools_draw")
    return [x for x in out if x[0] > entry]


def session_first(ctx, sd, i: int, p, entry: float, risk: float, keep_full: list, draw: float):
    """L4-session-pool-before-rel (067 ~00:50:27): the nearest untaken session-range pool in front of the draw is the first rung and the draw; the draw (the rel-eq pool) stays as
    the next rung. Returns (keep, draw) or None."""
    S = _S()
    TP = _TP()
    hit("eval_session_first")
    names = SESSION_BASE + SESSION_EXT
    vals = [v for v, cr, nm in named_pools(ctx, sd, i) if nm in names]
    if not vals:
        return None
    cands = [(v, k) for v, k in keep_full if k in POOLK and entry + p.min_rr * risk <= v < draw - p.es_pt and _near(TP._raw(v, k, p), vals, 0.01 * p.es_pt)]
    if not cands:
        return None
    s = min(cands)
    out = [(v, k) for v, k in keep_full if v < s[0] - p.es_pt] + [s] + [(v, k) for v, k in keep_full if s[0] + p.es_pt < v <= draw + 1e-9]
    hit("session_pool_first")
    return out, s[0]


def eq_leg_hi(ctx, sd, sw: dict, leg_hi: float, p):
    """L4-target-below-eq-leg (042 ~01:09:19): eq_leg 'rally' - the high that began the run into the sweep: the start of the one-sided leg into the extreme, else the session's highest
    high before it [our interpretation]. None for 'sweep'."""
    if p.eq_leg != "rally":
        return None
    TP = _TP()
    ls = TP.leg_start(sd, sw["ext_i"], 0)
    hi = ls[1] if ls is not None else float(sd.h[ctx.start:sw["ext_i"] + 1].max())
    hit("eq_leg_rally")
    return float(hi)


def beyond_imb(ctx, sd, i: int, p, pool_raw: float):
    """L4-target-below-eq-leg (049 ~00:03:42): the first 15m FVG (else the first 60m one) lying wholly beyond the pool P (side space): its near edge. None when there is none."""
    if getattr(ctx, "conf", None) is None:
        return None
    for tf in (("15m",), ("1h",)):
        rows = ctx.conf.opposing_ext(_now(ctx, i), sd.x(pool_raw), sd.sign, tf, (0,))
        if rows:
            hit("eq_beyond_imb")
            return float(_zone_edges(sd, rows[0])[0])
    return None


# --- 6. hook L: the ladder after the draw -----------------------------------------------------------------------------------------------------------

def org_geom(ctx, sd, i: int, p):
    """Today's ORG in side space as (open edge, prior-close edge) when the gap lies in the order's direction (the prior close above the open), else None."""
    st = _S()._org_state(ctx, sd, i, p)
    if st is None or not st["up"]:
        return None
    return float(st["opx"]), float(st["pcx"])


def _inside(v: float, a: float, b: float) -> bool:
    return a - 1e-9 <= v <= b + 1e-9


def org_flow(ctx, sd, i: int, p, a: float, b: float) -> bool:
    """L7-org-partial-close-orderflow (068 ~00:11:50): an untouched opposing FVG / void, an opposing OB (intraday or 5m / 15m confluence rows) lies inside the gap [a, b]."""
    h = sd.h
    for z in sd.opposing():
        if z.i <= i and _inside(z.bottom, a, b) and h[z.i + 1:i + 1].max(initial=-np.inf) < z.bottom:
            return True
    conf = getattr(ctx, "conf", None)
    if conf is not None:
        for r in conf.opposing_ext(_now(ctx, i), sd.x(a), sd.sign, ("5m", "15m"), (0, 1)):
            if _inside(_zone_edges(sd, r)[0], a, b):
                return True
    from . import entries as EN
    return any(_inside(v, a, b) for v, _ in EN.ob_target_levels(sd, i, a - p.es_pt, p))


def org_breaker(ctx, sd, i: int, p, a: float, b: float, entry: float):
    """L7-org-breaker-inside (072 ~00:32:02): the nearest untraded opposing breaker whose zone lies inside the gap: the far side of its candle (side space) or None."""
    h = sd.h
    zs = [z for z in _TP().matrix_breakers(sd, p) if z.i <= i and _inside(z.bottom, a, b) and _inside(z.top, a, b) and z.bottom > entry
          and h[z.i + 1:i + 1].max(initial=-np.inf) < z.bottom]
    return float(min(zs, key=lambda z: z.bottom).top) if zs else None


def level_scores(ctx, sd, i: int, p, pairs: list) -> list:
    """new-level-confluence-scoring: the confluence.level_score of each (raw level, kind); sources = the confluence rows alive at bar i (FVG / VI / gap edges and CE, the OB MT)
    of every timeframe, the daily wick CEs and the named pools."""
    from . import confluence as CF
    srcs = []
    conf = getattr(ctx, "conf", None)
    if conf is not None:
        now = float(_now(ctx, i).value)
        for tf, z in conf.z.items():
            m = (z["known"] <= now) & (z["dead"] > now) & (now - z["known"] <= z["life"])
            for k in np.flatnonzero(m):
                top, bot = float(sd.x(z["top"][k])), float(sd.x(z["bottom"][k]))
                pts = [top, bot, (top + bot) / 2]
                if int(z["src"][k]) == 1 and "obm" in z and z["obm"][k] == z["obm"][k]:
                    pts.append(float(sd.x(z["obm"][k])))
                srcs.append(((tf, int(k)), tf, pts))
    for j, w in enumerate(getattr(ctx, "wicks", None) or [getattr(ctx, "wick", None)]):
        if w:
            srcs.append((("wick", j), "D", [float(sd.x(w["upper"])), float(sd.x(w["lower"]))]))
    for j, (v, cr, nm) in enumerate(named_pools(ctx, sd, i) + named_pools(ctx, sd, i, opposite=True)):
        srcs.append((("pool", j), "intraday", [v]))
    return [CF.level_score(float(v), srcs, p.confl_tol_frac, p.tick) for v, _ in pairs]


def pick_scored(ctx, sd, i: int, p, cands: list):
    """new-level-confluence-scoring: the entry array candidate (entry, bottom, kind) of the highest confluence score (ties: the highest entry, the built pick)."""
    sc = level_scores(ctx, sd, i, p, [(c[0], "array") for c in cands])
    hit("confl_pick")
    return max(zip(sc, cands), key=lambda x: (x[0], x[1][0]))[1]


def late(ctx, sd, sw, i: int, p, session: str, entry: float, risk: float, keep: list, keep_full: list, draw: float, final_T: bool, lvt: list, tags: dict,
         st2: dict, org_draw: bool, locked: bool, leg_hi: float):
    """The ladder stage after the draw is known (strategy._finish_order). Returns (reject reason or None, keep, draw, final_T). Order: resistance runs (16), ORG family (83 / 39 / 37),
    NWOG ladder (20), the final-target picks (85, 99 / 49 / 54 clusters and last-hour SD, 94), the minimum objective (43)."""
    S = _S()
    TP = _TP()
    hit("eval_late")
    stt = _st(ctx)
    for t in dict.fromkeys(stt["tags"]):
        if t not in lvt:
            lvt.append(t)
    if p.hrlr_time_k > 0 or p.clear_path:
        why, keep, draw = resistance_runs(ctx, sd, sw, i, p, entry, keep, draw, locked, lvt, tags)
        if why:
            return why, keep, draw, final_T
    # --- ORG family
    if org_draw:
        g = org_geom(ctx, sd, i, p)
        if g is not None:
            a, b = g
            ce = (a + b) / 2
            fin, runner = None, None
            if p.org_breaker_stop:
                hit("eval_org_breaker")
                t_ = org_breaker(ctx, sd, i, p, a, b, entry)
                if t_ is not None:
                    fin = (S._exit_px(t_, "array", p), "org_breaker")
                    runner = S._exit_px(b, "array", p)
            if p.org_ce_if_flow:
                hit("eval_org_flow")
                if org_flow(ctx, sd, i, p, a, b):
                    c_ = S._exit_px(ce, "array", p)
                    if fin is None or c_ < fin[0]:
                        fin = (c_, "org_ce_flow")
                        runner = S._exit_px(b, "array", p)
            if fin is not None and fin[0] - entry >= p.min_rr * risk:
                keep = [(v, k) for v, k in keep if v < fin[0] - p.es_pt] + [(fin[0], "array")]
                draw = fin[0]
                st2["runner"] = runner if (runner is not None and runner > fin[0] + p.es_pt) else None
                lvt.append(fin[1])
                hit(fin[1])
            elif p.org_beyond:
                hit("eval_org_beyond")
                adr = _adr(ctx)
                far = S._exit_px(b, "array", p)
                if adr:
                    nx = [(v, k) for v, k in keep_full if v > max(far, draw) + p.es_pt and v - b <= p.org_beyond_adr * adr]
                    if nx:
                        keep = list(keep) + [min(nx)]
                        lvt.append("org_beyond")
                        hit("org_beyond")
    # --- NWOG ladder
    if p.nwog_ladder and not tags.get("fracs") and keep:
        r = nwog_ladder(ctx, sd, i, p, entry, risk, keep, draw)
        if r is not None:
            keep, fr = r
            tags["fracs"] = fr
            draw = keep[-1][0]
            final_T = False
            lvt.append("nwog_ladder")
            hit("nwog_ladder")
    # --- final target picks
    if p.beyond_pool_final:
        hit("eval_beyond_pool")
        r = beyond_pool(ctx, sd, i, p, entry, above=entry, keep=keep, keep_full=keep_full, draw=draw)
        if r is not None:
            keep, draw = r
            lvt.append("beyond_pool")
            hit("beyond_pool")
    pk = [x for x in keep_full if x[1] in ("proj_cluster", "proj_runner")]
    if pk and not locked:
        v, k = pk[-1]
        keep = [(a_, b_) for a_, b_ in keep if a_ < v - p.es_pt] + [(v, k)]
        draw = v
        lvt.append("final_" + k)
        hit("final_" + k)
    if p.proj_org_reprice and not locked:                 # L13-org-sd-projection: the nearest projection at an HTF array / the locked draw is the final exit (1 tick before it via proj_exit_ticks)
        ph = sorted(x for x in keep_full if x[1] == "proj_htf" and x[0] - entry >= p.min_rr * risk)
        if ph:
            v, k = ph[0]
            keep = [(a_, b_) for a_, b_ in keep if a_ < v - p.es_pt] + [(v, k)]
            draw = v
            lvt.append("final_proj_htf")
            hit("final_proj_htf")
    if p.sd_last_hour_k > 0 and ctx.t[i] >= S_LAST_HOUR:
        lh = [x for x in keep_full if x[1] == "proj_lh" and x[0] - entry >= p.min_rr * risk]      # (room: at least min_rr x risk)
        if lh:
            v, k = lh[-1]
            keep = [(a_, b_) for a_, b_ in keep if a_ < v - p.es_pt] + [(v, k)]
            draw = v
            tags["exit_at"] = 945                  # out by 15:45 (the position-level time exit)
            lvt.append("sd_last_hour")
            hit("sd_last_hour")
    if p.confl_rank and not locked and len(keep_full) >= 2:
        hit("eval_confl")
        cand = keep_full[1:]
        sc = level_scores(ctx, sd, i, p, [(TP._raw(v, k, p), k) for v, k in cand])
        best = max(zip(sc, [-x[0] for x in cand], cand))[2]
        keep = [(a_, b_) for a_, b_ in keep_full if a_ < best[0] - p.es_pt] + [best]
        draw = best[0]
        lvt.append("confl_final")
        hit("confl_final")
    # --- minimum objective
    mo = st2.get("min_obj")
    if mo:
        cand = [v for v in mo if entry + p.min_rr * risk <= S._exit_px(v, "min_obj", p) < draw - p.es_pt]
        if cand:
            v = S._exit_px(min(cand), "min_obj", p)
            tags.setdefault("tp2_extras", []).append((v, "min_obj", True))
            lvt.append("min_obj")
            hit("min_obj")
    return None, keep, draw, final_T


def resistance_runs(ctx, sd, sw, i: int, p, entry: float, keep: list, draw: float, locked: bool, lvt: list, tags: dict):
    """L4-resistance-runs: (time factor) a target is dropped when the bars price spent in the band [the lowest intermediate untaken swing high, the target] exceed hrlr_time_k x the bars
    of the leg (the sweep to now), unless the day is a jobs / FOMC day; (clear path) the draw needs an opposing 4h / D array beyond it with lrlr_max satisfied up to it;
    (linger) the position is watched for lingering at the entry (tag lingered). Returns (reject reason or None, keep, draw)."""
    TP = _TP()
    h = sd.h
    if p.hrlr_time_k > 0 and not is_news_day(ctx):
        hit("eval_hrlr_time")
        e_ = int(sw["ext_i"])
        leg_bars = max(1, int(np.argmax(sd.h[e_:i + 1])))          # the leg = the sweep extreme .. the leg's high
        kept = []
        for v, k in keep:
            qs = [q for q in TP._ph(sd) if q.known <= i and q.i >= ctx.start - 1 and entry < q.price < v]          # (the swings of the overlap: taken or not - the time price spent among them is the measure)
            if qs:
                lo = min(q.price for q in qs)
                a = min(q.i for q in qs)
                n_in = int(((sd.c[a:i + 1] >= lo) & (sd.c[a:i + 1] <= v)).sum())
                if n_in > p.hrlr_time_k * leg_bars:
                    hit("hrlr_time_drop")
                    lvt.append("hrlr_time")
                    continue
            kept.append((v, k))
        if not kept:
            return "x_hrlr_time", keep, draw
        if locked and kept[-1] != keep[-1]:
            return "x_hrlr_time", keep, draw
        keep = kept
        draw = keep[-1][0] if draw not in [v for v, _ in keep] else draw
    if p.clear_path and keep:
        hit("eval_clear_path")
        ok = False
        conf = getattr(ctx, "conf", None)
        if conf is not None:
            for r in conf.opposing_ext(_now(ctx, i), sd.x(draw), sd.sign, ("4h", "D"), (0, 1, 3)):
                near, _ = _zone_edges(sd, r)
                if p.lrlr_max < 0 or TP.resistance_count(ctx, sd, i, p, entry, near) <= p.lrlr_max:
                    ok = True
                    break
        if conf is None:
            hit("clear_path_not_evaluable")                  # no confluence table: the test cannot be evaluated - no rejection
        elif not ok:
            return "x_no_clear_path", keep, draw
        else:
            lvt.append("clear_path")
    if p.hrlr_time_k > 0 or p.clear_path:
        tags["tp2"] = dict(tags.get("tp2") or {}, linger=(int(p.linger_bars), float(p.linger_pts)), entry=float(entry))
    return None, keep, draw


def nwog_ladder(ctx, sd, i: int, p, entry: float, risk: float, keep: list, draw: float):
    """L5-nwog-target-ladder (020 ~00:03:50; 025 ~00:43:43): the draw is an NWOG level: the NWOG tail of the ladder is near edge (nwog_near_frac; 0 = no partial there, the rung is
    dropped) -> CE (nwog_ce_frac, the bulk) -> far edge (the rest, scaled out in nwog_far_split single-lot rungs "one contract at a time"). The rungs of `keep` below the NWOG near edge stay
    (they share nwog_pre_frac of the size); rungs behind the entry are absent, so CE and far edge are targets only once the near edge traded. Returns (keep, fracs) or None."""
    S = _S()
    hit("eval_nwog_ladder")
    zs = nwog_zones(ctx, sd, i)
    eb = p.exit_before_pts * p.es_pt
    for lo_s, hi_s, ce_s, _ in zs:
        if any(abs(draw + eb - v) <= p.es_pt for v in (lo_s, ce_s, hi_s)):
            ex = lambda v: S._exit_px(v, "array", p)
            near_x = ex(lo_s)
            low = [(v, k) for v, k in keep if v < near_x - p.es_pt and v - entry >= p.min_rr * risk]
            tail = [(ex(lo_s), p.nwog_near_frac), (ex(ce_s), p.nwog_ce_frac)]
            nf = max(1, int(p.nwog_far_split))
            far_f = max(0.0, 1.0 - p.nwog_near_frac - p.nwog_ce_frac)
            tail += [(ex(hi_s), far_f / nf)] * nf
            sel = [(v, f) for v, f in tail if v - entry >= p.min_rr * risk]
            sel = [(v, f) for v, f in sel if f > 0 or v != near_x]          # a 0 near fraction: no partial at the near edge (the rung goes)
            if not sel:
                return None
            pre = float(p.nwog_pre_frac) if low else 0.0
            rungs = [(v, k) for v, k in low] + [(v, "array") for v, _ in sel]
            fr = [pre / len(low)] * len(low) if low else []
            fs = [f for _, f in sel]
            s_ = sum(fs)
            fs = [f / s_ * (1.0 - pre) for f in fs] if s_ > 0 else [(1.0 - pre) / len(fs)] * len(fs)
            hit("nwog_ladder_kept_low") if low else None
            return rungs, tuple(fr + fs)
    return None


def beyond_pool(ctx, sd, i: int, p, entry: float, above: float, keep: list, keep_full: list, draw: float):
    """B2-target-beyond-pool-inefficiency (071 ~00:22:18; 104 ~00:22:24): P = the draw pool; the final target is the nearest FVG / OB near edge beyond P within beyond_pool_adr x
    ADR5, else the rejection-block body edge beyond P, else the next relative equal high beyond P. The arrays between the price and P stay partial rungs. Returns (keep, draw) or None."""
    S = _S()
    TP = _TP()
    pools = [(v, k) for v, k in keep if k in POOLK]
    if not pools:
        return None
    P = pools[-1][0]
    adr = _adr(ctx)
    raw_p = TP._raw(P, pools[-1][1], p)
    h = sd.h
    cands = []
    if adr:
        band = p.beyond_pool_adr * adr
        for z in sd.opposing():
            if z.i <= i and raw_p < z.bottom <= raw_p + band and h[z.i + 1:i + 1].max(initial=-np.inf) < z.bottom:
                cands.append(float(z.bottom))
        from . import entries as EN
        cands += [v for v, _ in EN.ob_target_levels(sd, i, raw_p, p) if v <= raw_p + band]
        conf = getattr(ctx, "conf", None)
        if conf is not None:
            for r in conf.opposing_ext(_now(ctx, i), sd.x(raw_p), sd.sign, ("5m", "15m", "30m", "1h"), (0, 1)):
                v = _zone_edges(sd, r)[0]
                if v <= raw_p + band:
                    cands.append(float(v))
    if cands:
        fin = (S._exit_px(min(cands), "array", p), "array")
    else:
        rb = [z for z in TP.rb_zones(sd, p) if z.i <= i and z.bottom > raw_p and h[z.i + 1:i + 1].max(initial=-np.inf) < z.bottom]
        if rb:
            fin = (S._exit_px(float(min(z.bottom for z in rb)), "rb", p), "rb")
        else:
            eqs = [(v, k) for v, k in keep_full if k == "pool_eq" and v > P + p.es_pt]
            if not eqs:
                return None
            fin = min(eqs)
    return [(v, k) for v, k in keep if v <= P + 1e-9] + [fin], fin[0]


# --- 7. SD engine pieces (targets.sd_ranges / sd_levels / extra_sources) ----------------------------------------------------------------------------------

def armed(ctx, sd, sw: dict, i: int, p, nm: str, lo: float, hi: float) -> bool:
    """L12-sd-activation (029 ~00:21:45; 008 ~00:06:39): with sd_arm 'close' a projection is armed only after a bar CLOSED beyond the anchor extreme `hi` (a wick through it does not) and the
    next sd_arm_bars closes stay beyond it (no immediate return). 'trade' = the built behaviour (always armed)."""
    if p.sd_arm != "close":
        return True
    hit("eval_sd_arm")
    n = p.sd_arm_bars
    c = sd.c
    for k in range(int(sw["ext_i"]) + 1, i + 1 - n):
        if c[k] > hi and bool((c[k + 1:k + 1 + n] > hi).all()):
            hit("sd_armed")
            return True
    return False


def sd_ranges_extra(ctx, sd, i: int, p, sw: dict, name: str) -> list:
    """The ranges (name, lo, hi) of the anchors this chunk adds, in side space: 'm15_leg' (the last 15m swing low -> the first 15m swing high after it) and the 'fulcrum' leg of
    sd_fulcrum_def 'inception' (the sweep extreme -> the first confirmed swing high after it, armed when a bar TRADES through it)."""
    out = []
    if name == "m15_leg":
        hit("eval_m15_leg")
        base = ctx.tf
        ph, pl = (L.tf_pivots(ctx.idx[:i + 1], sd.h[:i + 1], sd.l[:i + 1], base, 15) if base < 15 else (sd.ph, sd.pl))
        ph = [q for q in ph if q.known <= i]
        for ql in reversed([q for q in pl if q.known <= i]):
            qh = next((q for q in ph if q.i > ql.i and q.price > ql.price), None)
            if qh is not None:
                out.append((name, float(ql.price), float(qh.price)))
                break
    elif name == "inception":
        hit("eval_inception")
        ext, ext_i = float(sw["ext"]), int(sw["ext_i"])
        q = next((q for q in sd.ph if q.i > ext_i and q.known <= i), None)
        if q is not None and q.price > ext and sd.h[q.i + 1:i + 1].max(initial=-np.inf) > q.price:
            out.append(("fulcrum", ext, float(q.price)))
            hit("inception_fulcrum")
    return out


def tier_ranges(ctx, sd, i: int, p, sw: dict) -> list:
    """L12-cluster-anchors (014 ~00:03:48): one range per ITL / LTL low of the current up-leg (low -> the swing high before it) [our interpretation of the anchor set]."""
    out = []
    hit("eval_tiers")
    ext_i = int(sw["ext_i"])
    tiers = sd.tiers()
    ph = [q for q in sd.ph if q.known <= i]
    for t in p.sd_multi_tiers:
        for q in tiers[t][1]:
            if q.known > i or q.i < ext_i:
                continue
            hs = [x for x in ph if x.i < q.i]
            if hs and hs[-1].price > q.price:
                out.append((t, float(q.price), float(hs[-1].price)))
    return out


def sd_pool(ctx, sd, i: int, p, sw: dict, pool):
    """L12-ref-rolls-to-new-high (014 ~00:03:27): the buy-side reference rolls to the highest confirmed swing high above it formed since the sweep."""
    if pool is None or not p.sd_ref_roll:
        return pool
    hit("eval_sd_ref_roll")
    hs = [q.price for q in sd.ph if q.known <= i and q.i >= int(sw["ext_i"]) and q.price > pool]
    if hs:
        hit("sd_ref_roll")
        return max(hs)
    return pool


def is_consol_day(ctx) -> bool:
    P = getattr(ctx, "dplan", None)
    return bool(P is not None and "consol_day" in getattr(P, "tags", ()))       # the DayPlan N8 tag only (cur_no_draw is a lock-state flag)


def sd_cands(ctx, sd, i: int, p, sw: dict, nm: str, lo: float, hi: float, cand: list, pool, lv: list, entry: float, risk: float) -> list:
    """The (level, k, kind) picks of one range: kind 'sd' unless a switch of this chunk names it. `cand` = [(level, k)] sorted. Replaces the first-beyond block of sd_levels when a switch
    of the chunk is on (sd.on)."""
    S = _S()
    TP = _TP()
    pool = sd_pool(ctx, sd, i, p, sw, pool)
    rng = hi - lo
    if p.sd_last_hour_k > 0 and p.sd_anchor == "mss_leg" and nm == "broken":
        hit("eval_last_hour")
    if p.sd_last_hour_k > 0 and p.sd_anchor == "mss_leg" and ctx.t[i] >= S_LAST_HOUR and nm == "broken":
        return [(hi + p.sd_last_hour_k * rng, p.sd_last_hour_k, "proj_lh")]
    if p.sd_htf_extreme and nm == "m15_leg":
        hv = htf_level_values(ctx, sd, i, p, entry)
        got = [(v, k, "proj_htf") for v, k in cand if v > entry and _near(v, hv, p.sd_htf_tol * p.es_pt)]
        if got:
            hit("sd_htf_extreme")
        return got
    if p.sd_premium_consol and is_consol_day(ctx) and pool is not None:
        hit("eval_sd_premium")
        eq50 = (float(sd.l[ctx.start:i + 1].min()) + float(sd.h[ctx.start:i + 1].max())) / 2
        ok = [(v, k) for v, k in cand if v > pool and v > eq50]
        if ok:
            edges = [z.bottom for z in sd.opposing() if z.i <= i] + [z.top for z in sd.opposing() if z.i <= i] + [q.price for q in sd.ph if q.known <= i]
            pref = [x for x in ok if any(abs(x[0] - e) <= p.es_pt for e in edges)]
            v, k = (pref or ok)[0]
            hit("sd_premium_consol")
            return [(v, k, "proj")]                      # (no premium level: the pick falls back to the first level beyond the pool below)
    if p.sd_first_beyond:
        if pool is not None:
            beyond = [x for x in cand if x[0] > pool]
        elif p.sd_no_pool_fallback:
            beyond = [x for x in cand if x[0] - entry >= p.min_rr * risk]
        else:
            beyond = []
        out = [(v, k, "") for v, k in beyond[:1]]
        if p.sd_deep_conv and beyond:
            out = [(v, k, "") for v, k in beyond[:1]]
            fv = fvg_edge_values(ctx, sd, i, p)
            tol = p.sd_conv_ticks * p.tick
            deep = [(v, k) for v, k in beyond[1:] if _near(v, fv, tol)]
            if deep:
                out += [(v, k, "proj") for v, k in deep[:-1]] + [(deep[-1][0], deep[-1][1], "proj_runner")]
                hit("sd_deep_conv")
        return out
    return [(v, k, "") for v, k in cand]


def fvg_edge_values(ctx, sd, i: int, p) -> list:
    """The 5m / 15m FVG edges and CEs above (side space): the untouched intraday opposing FVGs and the confluence rows of 5m / 15m."""
    out = []
    for z in sd.opposing():
        if z.i <= i and sd.h[z.i + 1:i + 1].max(initial=-np.inf) < z.bottom:
            out += [z.bottom, z.top, z.mid]
    conf = getattr(ctx, "conf", None)
    if conf is not None:
        for r in conf.opposing_ext(_now(ctx, i), sd.x(float(sd.c[i])), sd.sign, ("5m", "15m"), (0,), straddle=True):
            a, b = _zone_edges(sd, r)
            out += [a, b, (a + b) / 2]
    return [float(v) for v in out]


def htf_level_values(ctx, sd, i: int, p, entry: float) -> list:
    """The HTF levels an SD level may coincide with (L12-prior-session-swing-htf-extreme): the daily wick CEs, the HTF array levels and the rejection-block bodies (side space)."""
    S = _S()
    vals = [float(v) for v in S._wick_ces(ctx, sd, False)]
    vals += [v for v in _T1().htf_values(ctx, sd, i, p, entry, "array")]
    vals += [float(z.bottom) for z in _TP().rb_zones(sd, p) if z.i <= i]
    return vals


def sd_tail(ctx, sd, i: int, p, sw: dict, got: list, lv: list, above: float, lvt: list) -> list:
    """After the per-range picks (sd_levels): the clusters of the tier anchors, the HTF cap. `got` = [(level, k, range name, kind)]; returns the same shape."""
    if p.sd_multi_tiers:
        tol = (p.sd_cluster_ticks or 2) * p.tick
        tg = sorted(x for x in got if x[2] in p.sd_multi_tiers)
        cl, cur = [], []
        for g in tg:
            if cur and g[0] - cur[0][0] > tol + 1e-9:
                cl.append(cur)
                cur = []
            cur.append(g)
        if cur:
            cl.append(cur)
        cl = [c for c in cl if len(c) >= p.sd_cluster_min]
        if cl:
            lvt.append("sd_cluster_tiers")
            hit("sd_cluster_tiers")
            got = [x for x in got if x[2] not in p.sd_multi_tiers] + [(float(np.median([x[0] for x in c])), 0.0, "tiers", "proj_cluster") for c in cl]
    if p.sd_cap_htf and got:
        hit("eval_sd_cap")
        conf = getattr(ctx, "conf", None)
        if conf is not None:
            tfs = tuple(t for t in (p.htf_targets or ("15m", "1h", "4h", "D")) if t != "5m") or ("15m", "1h", "4h", "D")
            rows = conf.opposing_ext(_now(ctx, i), sd.x(above), sd.sign, tfs, (0,))
            if rows:
                far = _zone_edges(sd, rows[0])[1]
                n0 = len(got)
                got = [x for x in got if x[0] <= far + 1e-9]
                if len(got) < n0:
                    lvt.append("sd_cap_htf")
                    hit("sd_cap_htf")
    return got


def org_projection(ctx, sd, i: int, p, session: str, above: float) -> list:
    """L13-org-sd-projection (055 ~00:19:31; 056 ~00:18:20): U = the ORG size. Only once a bar since 09:30 traded back to the prior close, and only in the bias direction, the levels far edge +
    k U (k = 1 .. proj_org_kmax or proj_org_k) are returned: kind proj_htf when within sd_htf_tol of the locked draw / an HTF array, else proj."""
    S = _S()
    if not (getattr(ctx, "org_today", False) and ctx.org and ctx.t[i] >= 570):
        return []
    hit("eval_org_reprice")
    pc, op = ctx.org[-1]
    size = abs(pc - op)
    if size <= 0:
        return []
    want = 0
    try:
        want = int(_BD().want_at(ctx, p, session, i))
    except Exception:
        want = 0
    if want != sd.sign:
        return []
    k0 = S._idx_at(ctx, 570)
    reached = bool((ctx.l[k0:i + 1] <= pc).any()) if op > pc else bool((ctx.h[k0:i + 1] >= pc).any())
    if not reached:
        return []
    far = max(sd.x(pc), sd.x(op))
    ks = p.proj_org_k or tuple(range(1, p.proj_org_kmax + 1))
    lk = getattr(ctx, "cur_lock", None)
    hv = list(htf_level_values(ctx, sd, i, p, above))
    if lk and lk.get("target") is not None:
        hv.append(float(sd.x(lk["target"])))
    out = []
    for k in ks:
        v = float(far + k * size)
        out.append((v, "proj_htf" if _near(v, hv, p.sd_htf_tol * p.es_pt) else "proj"))
    hit("org_projection")
    return out


def breaker_ks(ctx, sd, i: int, p, session: str, B: float, ext: float, l1=None) -> list:
    """L13-breaker-range-sd-weekly (074 ~00:30:15): the breaker-range multiples beyond B: k = 1 as built ('array'); k > 1 is kind proj_wk and needs the weekly bias and the day's bias to agree
    with the order. The k > 1 range runs from the swept swing low L1 (`l1`, the level the sweep took) to B - not from the sweep extreme L2 (k = 1 keeps the 070 formula, from the extreme)."""
    out = []
    ok = None
    a_ = ext if l1 is None or not (ext <= l1 < B) else float(l1)
    hit("eval_proj_breaker_k")
    for k in p.proj_breaker_k:
        v = B + k * (B - (ext if k == 1.0 else a_))
        if k == 1.0:
            out.append((v, "array"))
            continue
        if ok is None:
            want = 0
            try:
                want = int(_BD().want_at(ctx, p, session, i))
            except Exception:
                want = 0
            ok = bool(ctx.wbias == sd.sign and want == sd.sign)
        if ok:
            out.append((v, "proj_wk"))
            hit("proj_wk")
    return out


# --- 8. mid-trade management ----------------------------------------------------------------------------------------------------------------------------

def on_fill(ctx, sd, pos: dict, tr, o: dict, i: int, p) -> None:
    """Fill time: the state the mid-trade hook needs (linger window, the entry-low anchor)."""
    d = dict(o.get("tp2") or {})
    if p.sd_htf_extreme:
        d["x_fill"] = True
    if p.sd_anchor == "entry_low":
        hit("eval_entry_low")
        d["entry_low"] = min(float(sd.l[i]), float(o["ext"]))
        d["fill_i"] = i
    if d:
        d["fill_i"] = i
        pos["tp2"] = d


def manage(ctx, sd, pos: dict, tr, i: int, p) -> None:
    """Per closed bar of an open position (strategy.run_day after the management exits): the lingering tag and the entry-low projection rung."""
    d = pos.get("tp2")
    if not d:
        return
    if d.get("linger") and not d.get("linger_done"):
        bars, pts = d["linger"]
        n = i - d["fill_i"] + 1
        if n >= bars:
            d["linger_done"] = True
            seg = sd.c[d["fill_i"]:d["fill_i"] + bars]
            if bool((np.abs(seg - d["entry"]) <= pts * p.es_pt + 1e-9).all()):
                tr.lv_tags = "|".join(x for x in (tr.lv_tags, "lingered") if x)
                hit("lingered")
    if d.get("entry_low") is not None and not d.get("el_done") and pos["left"]:
        lo = d["entry_low"]
        q = next((q for q in sd.ph if q.i >= d["fill_i"] and q.known <= i and q.price > lo), None)
        if q is None:
            return
        d["el_done"] = True
        hi = float(q.price)
        v = hi + (hi - lo)
        S = _S()
        x = float(S._exit_px(v, "proj", p))
        lv, fr = list(pos["levels"]), list(pos["fracs"])
        if (pos.get("final_T") and len(lv) > len(fr)) or pos["k"] >= len(lv) or x <= float(sd.c[i]) or not fr or len(fr) != len(lv):
            return
        kinds = list(pos.get("level_kinds") or ["array"] * len(lv))
        j = next((j for j in range(pos["k"], len(lv)) if lv[j] > x), len(lv))       # inserted in sorted position among the rungs still ahead
        if any(abs(x - v) <= p.es_pt for v in lv[pos["k"]:]):
            return
        src = min(j, len(fr) - 1)
        f = min(float(p.htf_runner_frac), fr[src])
        fr[src] -= f
        pos["levels"] = lv[:j] + [x] + lv[j:]
        pos["fracs"] = tuple(fr[:j] + [f] + fr[j:])
        pos["level_kinds"] = kinds[:j] + ["proj"] + kinds[j:]
        tr.lv_tags = "|".join(x_ for x_ in (tr.lv_tags, "entry_low_proj") if x_)
        hit("entry_low_proj")


def sell_side_filter(out: dict, ctx, sd, p) -> dict:
    """L14-session-pools-only (067 ~00:27:37): the swept (sell-side) pools of the scan: 'only' / 'extended' keep the session-range / PDH-PDL / ORG keys, 'rank' only puts them first."""
    mode = p.session_pools_mode
    base = ("pdh", "pdl", "prev_pm", "london", "prev_london", "org")
    ext = base + ("lunch", "am_session", "prev_am", "rel_eq")
    keys = list(out)
    if mode == "rank":
        first = [k for k in keys if k.startswith(base)]
        hit("session_pools_rank")
        return {**{k: out[k] for k in first}, **{k: out[k] for k in keys if k not in first}}
    if mode in ("only", "extended"):
        use = base if mode == "only" else ext
        n0 = len(out)
        res = {k: v for k, v in out.items() if k.startswith(use)}
        if len(res) < n0:
            hit("session_pools_sweep")
        return res
    return out


def lock_cands(ctx, p, t_lock: int, kl: int) -> list:
    """X1-london-0300-fvg-draw: the overnight 5m FVGs as lock candidates (real prices, dir 0): (value, 'array', name, 0, created) for the near edge, CE and far edge of every FVG formed
    between the previous 18:00 and 09:30 that was not traded into by the bars up to the lock."""
    if not p.overnight_5m_fvgs or t_lock < 570 or ctx.tf != 5:
        return []
    hit("eval_on_fvg_lock")
    S = _S()
    k570 = S._idx_at(ctx, 570)
    out = []
    for z in L.fvgs(ctx.h, ctx.l, ctx.o, ctx.c):
        if z.i >= min(k570, kl):
            continue
        ts = ctx.idx[z.i]
        mod = ts.hour * 60 + ts.minute
        if not ((ts.date() == ctx.day and mod < 570) or (ts.date() < ctx.day and mod >= 1080)):
            continue
        if z.kind == "bull":
            if ctx.l[z.i + 1:kl].min(initial=np.inf) <= z.top:
                continue
            vals = (z.top, z.mid, z.bottom)
        else:
            if ctx.h[z.i + 1:kl].max(initial=-np.inf) >= z.bottom:
                continue
            vals = (z.bottom, z.mid, z.top)
        out += [(float(v), "array", "on_fvg", 0, S._idx_at(ctx, 0)) for v in vals]
    return out


# --- 9. small hooks ---------------------------------------------------------------------------------------------------------------------------------

SESSION_NAME_WORDS = ("lunch", "london", "prev_pm", "pm_", "am_", "org", "or_")


def lock_session_rank(lst: list) -> list:
    """L14-session-pools-only (067 ~00:27:37), 'rank' in the lock: the candidates whose name is a session-range pool come first (stable inside each group). Items are (distance, level, kind, name, dir)."""
    first = [x for x in lst if any(w in str(x[3]) for w in SESSION_NAME_WORDS)]
    if first:
        hit("session_pools_lock_rank")
    return first + [x for x in lst if x not in first]


def ts_weekly_bisi(ctx, sd, sw: dict, i: int, p) -> bool:
    """L9 (102 ~02:12:22) [our interpretation]: the swept pool lies at most ts_max_pts above the top of an unfilled weekly BISI of this side (side space) - the gap, not the pool, is the draw."""
    conf = getattr(ctx, "conf", None)
    if conf is None:
        return False
    hit("eval_ts_weekly_bisi")
    now = float(_now(ctx, i).value)
    lvl = float(sw["level"])
    for r in conf.rows(("W",), (0,)):
        if r["kind"] == sd.sign and r["known"] <= now and r["dead"] > now:
            top = max(sd.x(r["top"]), sd.x(r["bottom"]))
            if 0 <= lvl - top <= p.ts_max_pts * p.es_pt:
                hit("ts_weekly_bisi")
                return True
    return False


def extreme_smt(ctx, sd, pos: dict, i: int, pctx, psides, ppos) -> bool:
    """SMT at the projection extreme: our side printed a high (it reached the rung) that the partner index did not match - its highest high since the fill stayed at or below its highest
    high before the fill [our interpretation of "a recorded SMT at the extreme"]. False without a partner."""
    d = pos.get("tp2") or {}
    f = d.get("fill_i")
    if pctx is None or f is None or psides is None:
        return False
    ps = psides[sd.sign]
    j = int(ppos.index.searchsorted(ctx.idx[i], side="right") - 1)
    jf = int(ppos.index.searchsorted(ctx.idx[f], side="right") - 1)
    if j <= jf or jf < pctx.start:
        return False
    return bool(ps.h[jf + 1:j + 1].max() <= ps.h[pctx.start:jf + 1].max() + 1e-9)


def close_here(pos: dict, k: int, tr, t: int, tf: int, p, ctx=None, sd=None, i: int = 0, pctx=None, psides=None, ppos=None) -> bool:
    """L12-prior-session-swing-htf-extreme (035 ~00:38:13): a proj_htf rung reached after 11:00 with an SMT at that extreme (extreme_smt, evaluated on the bar that reaches the rung - not the
    entry's SMT) closes the trade; the last rung's final_hit flag is the session's side done."""
    if not p.sd_htf_extreme:
        return False
    kinds = pos.get("level_kinds") or ()
    if not (k < len(kinds) and kinds[k] == "proj_htf" and t + tf >= 660):
        return False
    hit("eval_extreme_smt")
    ok = ctx is not None and extreme_smt(ctx, sd, pos, i, pctx, psides, ppos)
    if ok:
        hit("extreme_smt_close")
    return ok
