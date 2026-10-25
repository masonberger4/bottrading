"""Caption-gap pass (digests/rulebook_gaps/*.md), package targets_partials, chunk 3 of 4: the engine glue of its 33 specs -
levels_liquidity_targets.md 106, 107, 109, 110, 119, 126, 131, 132, 134, 140, 156, 159, 168, 169, 170, 171, 172, 175, 178 and
management_partials_trailing_exits.md 1, 2, 3, 4, 7, 34, 35, 37, 38, 39, 40, 41, 42, 43.

Same conventions as tp1.py / tp2.py: side space (shorts run mirrored prices), a bar is used only after it closes (`i` = the last CLOSED bar, an order armed on it fills from
bar i+1), an object only from the bar that completes it. Every function sits behind a Params switch of the "caption-gap pass, targets_partials #3/4" block;
interpretations the sources do not pin down are marked [our interpretation]. `HITS` is sm2's counter dict (tests: proof that a switch's code path RAN).

Sections: 1 validation - 2 helpers (timeframe buckets, gap registry, HTF draw) - 3 hook R (strategy._finish_order: raw rungs before the exit prices) - 4 hook E (the exit
prices of FVG / ADR / REH-cluster rungs) - 5 hook C (the daily-breaker cap) - 6 hook L (the ladder after the draw: final picks, shapes, fractions, gates) - 7 sweep gate
(pool milestone) - 8 locked-draw candidates - 9 mid-trade management (speed skip) and report notes."""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

from . import levels as L
from . import sm2

HITS = sm2.HITS
hit = sm2.hit

POOLK = ("pool", "pool_eq")
AM_START, AM_END = 570, 720                          # the morning session of the PM measured move / launch array / PM rejection block (09:30 - 12:00)
GRADE_PCTS = (0.0, 0.125, 0.25, 0.375, 0.5, 0.625, 0.75, 0.875, 1.0)
HTF_ALL = ("15m", "30m", "1h", "4h", "D", "W", "M")


def _S():
    from . import strategy as S
    return S


def _TP():
    from . import targets as TP
    return TP


def _T2():
    from . import tp2 as T2
    return T2


# --- 1. validation ----------------------------------------------------------------------------------------------------------------------------------

def check_params(p) -> None:
    """Validation of the chunk's Params (strategy.Params.__post_init__) and the inert-switch notes."""
    for name, ok in (("fvg_target_level", ("before_edge", "at_edge", "deep")), ("pool_exit", ("beyond", "at", "before")), ("partial_mode", ("", "new", "experienced", "terminus", "quarters")),
                     ("exit_mode2", ("", "pay_first", "full_pull", "hold_runner")), ("ladder_preset", ("", "004", "037")), ("weekly_beyond_mode", ("off", "tag", "require")),
                     ("grades60_src", ("body", "wick")), ("proj_ext_anchor", ("leg", "stop_run", "midweek")), ("adr_anchor", ("day_low", "london_low"))):
        if getattr(p, name) not in ok:
            raise ValueError(f"{name} {getattr(p, name)!r}: expected one of {ok}")
    if (p.min_rr_final < 0 or p.void_leg_mult <= 0 or p.void_max_opp < 0 or p.fvg_deep_frac < 0 or p.fvg_deep_frac > 1 or p.pool_before_ticks < 0 or p.proj_before_pts < 0
            or p.adr_conv_pts < 0 or not 0 <= p.adr_conv_last <= 1440 or p.wide_or_mult <= 0 or p.adr_before_frac < 0 or p.proj_ext2 <= 1.0
            or not 0 < p.new_first <= 1 or not 0 <= p.pool_milestone < 1 or not 0 <= p.no_collapse_keep < 1 or p.energy_room_pts < 0):
        raise ValueError("targets_partials #3/4: min_rr_final, void_max_opp, pool_before_ticks, proj_before_pts, adr_conv_pts, adr_before_frac, energy_room_pts >= 0; void_leg_mult, wide_or_mult > 0; "
                         "0 <= fvg_deep_frac <= 1; proj_ext2 > 1; 0 < new_first <= 1; 0 <= pool_milestone, no_collapse_keep < 1; 0 <= adr_conv_last <= 1440")
    if any(float(x) <= 0 for x in p.fixed_partials) or any(float(f) <= 0 for f in p.fixed_partial_fracs) or sum(float(f) for f in p.fixed_partial_fracs[:len(p.fixed_partials)]) >= 1:
        raise ValueError("fixed_partials: distances > 0; fixed_partial_fracs: shares > 0 whose first len(fixed_partials) sum to < 1")
    if len(p.fixed_partials) > len(p.fixed_partial_fracs):
        raise ValueError("fixed_partial_fracs needs one share per fixed_partials distance")
    if sum(1 for x in (p.ladder_preset, p.exit_mode2, p.partial_mode not in ("", "experienced")) if x) > 1:
        raise ValueError("ladder_preset, exit_mode2 and partial_mode (new / terminus / quarters) each shape the whole ladder: set at most one of them")
    inert = []
    if p.speed_skip and p.exit_mode2 != "pay_first":
        inert.append("speed_skip acts on exit_mode2='pay_first'")
    if p.ladder037_ce and p.ladder_preset != "037":
        inert.append("ladder037_ce acts on ladder_preset='037'")
    if (p.adr_t2_htf or p.adr_ext or p.adr_before_frac > 0 or p.adr_anchor != "day_low") and not p.adr_target:
        inert.append("adr_t2_htf / adr_ext / adr_before_frac / adr_anchor act on the adr_target ladder: they need adr_target=True")
    if p.proj_ext_anchor != "leg" and p.proj_ext:
        inert.append("proj_ext_anchor 'stop_run' / 'midweek' takes its multiples from (1.27, proj_ext2), not from proj_ext")
    if p.mm_anchor in ("reanchor", "impulse") and not p.mm_targets:
        inert.append("mm_anchor 'reanchor' / 'impulse' needs mm_targets=True")
    if p.no_collapse_htf and getattr(p, "no_collapse_keep", 0) <= 0:
        inert.append("no_collapse_htf keeps nothing: no_collapse_keep is 0")
    if inert:
        warnings.warn("inert switches (targets_partials #3/4): " + "; ".join(x for x in inert if x), stacklevel=4)


def derive_pool_exit(p) -> None:
    """X2-pool-exit-at-or-before (037 ~53:34; 063 ~29:41; 101 ~1:28:47; 102 ~1:32:29): the pool exit offset `pool_beyond_pts` (ES pts beyond the pool) is derived from
    `pool_exit`: 'beyond' keeps the field (0.25 = one tick; 006 ~33:37 1.25 pts is the same switch with a larger value), 'at' = 0, 'before' = -pool_before_ticks ticks."""
    if p.pool_exit == "at":
        p.pool_beyond_pts = 0.0
    elif p.pool_exit == "before":
        p.pool_beyond_pts = -float(p.pool_before_ticks) * 0.25


def exit_on(p) -> bool:
    return bool(p.fvg_target_level != "before_edge" or p.adr_before_frac > 0 or p.pool_exit == "before")


def raw_on(p) -> bool:
    """True when a switch that adds / removes raw rungs (hook R) is on."""
    return bool(p.void_legs or p.mm_anchor in ("reanchor", "impulse") or p.ob_target_order or p.dt_proj or p.grades60 or p.target_past_eq60 or p.proj_ext_anchor != "leg"
                or p.daily_breaker_cap or p.adr_conv_target or p.adr_t2_htf or p.adr_ext or p.pm_am_leg or p.pm_am_rb or p.session_obj_tf)


def any_on(p) -> bool:
    """True when the state dict of _finish_order is needed (every hook)."""
    return bool(raw_on(p) or exit_on(p) or p.min_rr_final > 0 or p.weekly_beyond_mode != "off" or p.consol_overnight_targets or p.wide_or_draw or p.pm_launch_filter
                or p.pool_milestone > 0 or p.no_collapse_htf or p.partial_mode not in ("", "experienced") or p.exit_mode2 or p.ladder_preset or p.energy_split or p.fixed_partials
                or p.session_obj_tf)


# --- 2. helpers -------------------------------------------------------------------------------------------------------------------------------------

def _adr(ctx):
    return _S().adr5(list(getattr(ctx, "hist", None) or [])[-5:])


def _now(ctx, i: int):
    return _TP().now_ts(ctx, i)


def _zone_edges(sd, row):
    return _TP()._zone_edges(sd, row)


def _conf(ctx):
    return getattr(ctx, "conf", None)


def _near(v: float, vals, tol: float = 1e-6) -> bool:
    return any(abs(v - w) <= tol for w in vals)


def tf_buckets(ctx, i: int, m: int) -> list:
    """The COMPLETED m-minute buckets of the day frame up to bar i as (first, last) bar indices (m > the base timeframe)."""
    if m <= ctx.tf or i < 0:
        return [(k, k) for k in range(i + 1)] if m == ctx.tf else []
    idx = ctx.idx[:i + 1]
    g = pd.Series(np.arange(i + 1), index=idx).groupby(idx.floor(f"{m}min"))
    first, last, st = g.min().values, g.max().values, g.min().index
    done = (idx[last] - st) >= pd.Timedelta(minutes=m - ctx.tf)
    return [(int(a), int(z)) for a, z, ok in zip(first, last, done) if ok]


def tf_arrays(ctx, sd, i: int, m: int):
    """(o, h, l, c, last bar index of each bucket) of the completed m-minute buckets in side space; m == the base timeframe returns the bars themselves."""
    bk = tf_buckets(ctx, i, m)
    if not bk:
        return None
    o = np.array([sd.o[a] for a, z in bk])
    h = np.array([sd.h[a:z + 1].max() for a, z in bk])
    l = np.array([sd.l[a:z + 1].min() for a, z in bk])
    c = np.array([sd.c[z] for a, z in bk])
    return o, h, l, c, np.array([z for a, z in bk])


def _taken_up(sd, since: int, i: int, v: float) -> bool:
    """A buy-side level v (side space) was traded by the bars after `since` (inclusive of nothing before) through bar i."""
    return bool(sd.h[since + 1:i + 1].max(initial=-np.inf) >= v)


def gap_registry(ctx, sd, i: int, p, above: float, st: dict) -> list:
    """The opposing gaps above `above` as (near, ce, far) in side space: the confluence rows (FVG 0, opening gap 2, VI 3) of every timeframe from 15m up, the own-timeframe
    FVGs of the Side. Cached in st. Used by fvg_target_level (item 1) and the quarters ladder (item 42)."""
    if "gaps" in st:
        return st["gaps"]
    out = []
    cf = _conf(ctx)
    if cf is not None:
        for r in cf.opposing_ext(_now(ctx, i), sd.x(above), sd.sign, HTF_ALL, (0, 2, 3)):
            a, b = _zone_edges(sd, r)
            if b - a > 0:
                out.append((float(a), float((a + b) / 2), float(b)))
    for z in sd.opposing():
        if z.i <= i and z.bottom > above and z.top - z.bottom > 0 and sd.h[z.i + 1:i + 1].max(initial=-np.inf) < z.bottom:
            out.append((float(z.bottom), float(z.mid), float(z.top)))
    st["gaps"] = out
    return out


def gap_of(px: float, gaps: list, p, tol: float = 1e-6):
    """The registered gap whose near edge is the rung `px` (raw, or its before-edge exit price)."""
    for g in gaps:
        if abs(g[0] - px) <= tol or abs(g[0] - p.exit_before_pts * p.es_pt - px) <= tol:
            return g
    return None


def htf_draw(ctx, sd, i: int, p, above: float, st: dict):
    """The near edge (side space) of the nearest UNTOUCHED daily / weekly / monthly opposing array beyond `above` - the HTF draw of the 'bank', 'milestone' and 'no collapse'
    rules (36 / 37 / 38). Untouched = price has not traded to the near edge since the array formed. Within reach = at most 3 x ADR5 away [our interpretation]. None if none."""
    if "htf" in st:
        return st["htf"]
    out = None
    cf = _conf(ctx)
    if cf is not None:
        hit("eval_htf_draw")
        adr = _adr(ctx)
        reach = 3.0 * adr if adr else np.inf
        TP = _TP()
        for r in cf.opposing_ext(_now(ctx, i), sd.x(above), sd.sign, ("D", "W", "M"), (0, 1, 2, 3)):
            near, far = _zone_edges(sd, r)
            ex = TP.extreme_since(ctx, i, r["known"] + 1.0, sd.sign > 0)
            if ex is not None and sd.x(ex) >= near:
                continue                                         # already traded to
            if near - above > reach:
                continue
            if out is None or near < out:
                out = float(near)
    st["htf"] = out
    return out


def base_fracs(p, K: int) -> list:
    """The share of each of K rungs under the built ladder fractions (targets._ext_fracs)."""
    return _TP()._ext_fracs(p.ladder_fracs, K, False)


def news_ahead(ctx, p, i: int) -> bool:
    """The `ahead` flag of strategy._split: a scheduled release later today after the fill (10:00 data, 14:00 FOMC) or a CPI / NFP / FOMC day next."""
    from claude_hf.daytypes import events
    from .calendar import next_trading_day
    S = _S()
    day, t = ctx.day, int(ctx.t[min(i + 1, len(ctx.t) - 1)])
    tags = events(day)
    if (bool(tags & S.NEWS_1000) and t < 600) or ("fomc" in tags and t < 840):
        return True
    try:
        return bool(events(next_trading_day(day)) & {"cpi", "jobs", "fomc"})
    except Exception:
        return False


def range60(ctx, p, src: str | None = None):
    """The 60-day range (real prices) from the last 60 completed sessions: highest / lowest candle BODY (open / close; cc07_005) or wick (cc05_003). None with < 20 sessions."""
    fr = list(getattr(ctx, "hist", None) or [])[-60:]
    if len(fr) < 20:
        return None
    src = src or p.grades60_src
    if src == "body":
        hi = max(max(float(f.open.iloc[0]), float(f.close.iloc[-1])) for f in fr)
        lo = min(min(float(f.open.iloc[0]), float(f.close.iloc[-1])) for f in fr)
    else:
        hi = max(float(f.high.max()) for f in fr)
        lo = min(float(f.low.min()) for f in fr)
    return (lo, hi) if hi > lo else None


def grade_levels(lo: float, hi: float) -> list:
    """new-60day-range-grades (cc07_006 ~10:09): the nine grade lines 0 / 12.5 / ... / 100 % of the range."""
    return [lo + g * (hi - lo) for g in GRADE_PCTS]


def near_htf_array(ctx, sd, i: int, above: float, v: float, tol: float, tfs=("15m", "30m", "1h", "4h", "D", "W", "M")) -> bool:
    cf = _conf(ctx)
    if cf is None:
        return False
    for r in cf.opposing_ext(_now(ctx, i), sd.x(above), sd.sign, tfs, (0, 1, 2, 3)):
        a, b = _zone_edges(sd, r)
        if a - tol <= v <= b + tol:
            return True
    return False


def adr_low(ctx, sd, i: int, p) -> float:
    """L16 adr_anchor (side space): the day's low so far, or the London low once London is complete (cc09_006: 'day low or London low')."""
    if p.adr_anchor == "london_low":
        lo_ = getattr(ctx, "sess", {}).get("london")
        if lo_ is not None and ctx.t[i] >= lo_[2]:
            return float(sd.x(lo_[1] if sd.sign > 0 else lo_[0]))
    return float(sd.l[ctx.start:i + 1].min())


# --- 3. hook R: the raw rungs ----------------------------------------------------------------------------------------------------------------------

def void_levels(ctx, sd, i: int, p, above: float, st: dict) -> list:
    """new-void-fill-target (cc01_006 ~10:28): the CE and the top (the final fill) of the nearest unfilled one-sided down leg on 5m / 15m / 1h, in side space."""
    best = None
    for m in sorted({ctx.tf, 15, 60}):
        a = tf_arrays(ctx, sd, i, m)
        if a is None or len(a[1]) < 6:
            continue
        o, h, l, c, ends = a
        for z in L.one_sided_legs(o, h, l, c, p.void_leg_mult, p.void_max_opp):
            if z.i >= len(h):
                continue
            end = int(ends[z.i])
            if end > i or z.top <= above or sd.h[end + 1:i + 1].max(initial=-np.inf) >= z.top:
                continue
            if best is None or z.top < best[0]:
                best = (float(z.top), float((z.top + z.bottom) / 2))
    if best is None:
        return []
    hit("void_legs")
    st["void_final"] = best[0]
    return [(c_, "array") for c_ in (best[1], best[0]) if c_ > above]


def mm_levels(ctx, sd, i: int, p, sw: dict, leg_hi: float, entry: float, above: float) -> list:
    """L13-sweep-low-measured-move (cc02_008 ~17:01) 'reanchor': L2 = this trade's sweep low, L1 = the lowest swing low before it today (the initial buy low, lower than L2),
    H1 = the highest high between: T = L2 + (H1 - L1). 'impulse' (LLT3-impulse-retrace-expansion, cc12_002 ~44:24): A = the sweep extreme (the leg origin), B = the MSS leg
    high, C = the retrace low = the entry [our interpretation: the fill is not known at the order]: T = C + (B - A). Kind 'proj' ('proj_htf' within 1 pt of an HTF array)."""
    ext, ext_i = float(sw["ext"]), sw["ext_i"]
    v = None
    if p.mm_anchor == "impulse":
        if leg_hi > ext:
            v = entry + (leg_hi - ext)
    else:
        cand = [q for q in sd.pl if q.known <= i and ctx.start <= q.i < ext_i and q.price < ext]
        if cand:
            q1 = min(cand, key=lambda q: q.price)
            h1 = float(sd.h[q1.i:ext_i].max())
            if h1 > ext:
                v = ext + (h1 - q1.price)
    if v is None or v <= above:
        return []
    hit("mm_" + p.mm_anchor)
    return [(float(v), "proj_htf" if near_htf_array(ctx, sd, i, above, v, p.es_pt) else "proj")]


def ob_order_levels(ctx, sd, i: int, p, above: float, tags: dict) -> list:
    """X1-bullish-objective-order (cc03_002 ~20:14): for an OB entry, T1 = the low of the nearest bearish OB candle above (the last up-close candle at an untaken swing
    high), T2 = its high + one tick (the buy stops), T3 = the near edge of the nearest 1h / 4h / D bearish OB. Side space."""
    ek = str(tags.get("entry_kind", ""))
    if not (ek.startswith("ob") or ek == "vi_ob"):
        return []
    best = None
    for q in sd.ph:
        if q.known > i or q.i < ctx.start or q.price <= above or sd.h[q.i + 1:i + 1].max(initial=-np.inf) >= q.price:
            continue
        j = next((k for k in range(q.i, max(ctx.start - 1, q.i - 3), -1) if sd.c[k] > sd.o[k]), None)
        if j is None or sd.l[j] <= above:
            continue
        if best is None or sd.l[j] < best[0]:
            best = (float(sd.l[j]), float(sd.h[j]))
    if best is None:
        return []
    out = [(best[0], "array"), (best[1] + p.tick, "exact")]
    cf = _conf(ctx)
    if cf is not None:
        rows = [(_zone_edges(sd, r)[0]) for r in cf.opposing_ext(_now(ctx, i), sd.x(above), sd.sign, ("1h", "4h", "D"), (1,))]
        rows = [v for v in rows if v > best[1]]
        if rows:
            out.append((float(min(rows)), "array"))
    hit("ob_target_order")
    return out


def double_tops(ctx, sd, i: int, p, above: float):
    """new-double-top-projection (cc04_014 ~8:40): the 1h / 4h double tops of the day frame (two consecutive swing highs of the completed buckets within eq_tol_pts), as
    (pool, projection, reached, booked): R = the higher peak minus the lowest low between the peaks, projection = peak + R (levels.double_top_proj). A pair is known once
    the bucket after its second peak is complete. reached = the projection has traded; booked = the pool traded one tick through (its projection stays live)."""
    out = []
    tol = p.eq_tol_pts * p.es_pt
    for m in (60, 240):
        if m <= ctx.tf:
            continue
        a = tf_arrays(ctx, sd, i, m)
        if a is None or len(a[1]) < 3:
            continue
        hit("eval_dt")
        o, h, l, c, ends = a
        piv = [k for k in range(1, len(h) - 1) if h[k] > h[k - 1] and h[k] > h[k + 1]]
        for k1, k2 in zip(piv, piv[1:]):
            if abs(h[k1] - h[k2]) > tol:
                continue
            pool, proj = L.double_top_proj(h, l, (k1, k2))
            known = int(ends[k2 + 1])
            reached = bool(sd.h[known + 1:i + 1].max(initial=-np.inf) >= proj)
            booked = bool(sd.h[known + 1:i + 1].max(initial=-np.inf) >= pool + p.tick)
            out.append((float(pool), float(proj), reached, booked))
    return out


def dt_levels(ctx, sd, i: int, p, above: float, st: dict) -> list:
    out = []
    for pool, proj, reached, booked in double_tops(ctx, sd, i, p, above):
        if reached:
            st["dt_reached"] = True
            continue
        if proj > above:
            out.append((proj, "proj"))
        if not booked and pool > above:
            out.append((pool, "pool_eq"))
    if out:
        hit("dt_proj")
    return out


def grade_rungs(ctx, sd, i: int, p, above: float, entry: float, st: dict, lvt: list) -> list:
    """new-60day-range-grades (cc07_006 ~10:09): the nine grade lines of the 60-day range beyond `above` (kind 'grade'); the entry's grade band is tagged."""
    r = range60(ctx, p)
    if r is None:
        return []
    hit("eval_grades60")
    lo, hi = r
    gl = [sd.x(g) for g in grade_levels(lo, hi)]
    if not (min(gl) - 1e-9 <= sd.x(entry) <= max(gl) + 1e-9):
        return []
    step = (hi - lo) / 8.0
    band = int(np.clip((sd.x(entry) * sd.sign - lo) // step, 0, 7)) if step > 0 else 0
    lvt.append(f"grade{band}")
    hit("grades60")
    st["grades"] = sorted(g for g in gl if g > above)
    return [(float(g), "grade") for g in st["grades"]]


def past_eq_final(ctx, sd, i: int, p, entry: float, st: dict):
    """L14-target-past-eq (cc07_005 ~8:07): an entry on the premium side of the 60-day body range (a short above the EQ; in side space an entry below the mirrored EQ) targets
    the first UNTRADED opposing M / W / D array whose near edge lies at or beyond the EQ. Returns the near edge (side space) or None."""
    r = range60(ctx, p, "body")
    cf = _conf(ctx)
    if r is None or cf is None:
        return None
    hit("eval_past_eq")
    eq = sd.x((r[0] + r[1]) / 2)
    if not entry < eq:
        return None
    TP = _TP()
    best = None
    for rr in cf.opposing_ext(_now(ctx, i), sd.x(entry), sd.sign, ("D", "W", "M"), (0, 1, 2, 3)):
        near, far = _zone_edges(sd, rr)
        ex = TP.extreme_since(ctx, i, rr["known"] + 1.0, sd.sign > 0)
        if near >= eq - 1e-9 and not (ex is not None and sd.x(ex) >= near) and (best is None or near < best):
            best = float(near)
    return best


def ext_multiples(start: float, end: float, mults) -> list:
    """L13-cc-extension-projections (cc06_008 ~28:08; cc07_003 ~30:54): start + m x (end - start): the H - 1.27 R / H - 1.68 R of the bearish template (start H, end L)
    in real prices; in side space the same call on mirrored prices."""
    return [start + float(m) * (end - start) for m in mults]


def week_bars(ctx, sd, i: int):
    """The bars of this ISO week up to bar i in side space: (frames of the earlier days as (weekday, high, low), today's highs / lows). For the midweek anchor."""
    d0 = ctx.day
    wk = d0.isocalendar()[:2]
    prev = []
    for fr in list(getattr(ctx, "hist", None) or []):
        d = fr.index[0].date()
        if d.isocalendar()[:2] == wk and d < d0:
            prev.append((d.weekday(), float(sd.x(fr.high.max())) if sd.sign > 0 else float(sd.x(fr.low.min())), float(sd.x(fr.low.min())) if sd.sign > 0 else float(sd.x(fr.high.max()))))
    return prev


def ext_levels(ctx, sd, i: int, p, sw: dict, above: float) -> list:
    """L13-cc-extension-projections: the 1.27 / proj_ext2 extensions of the anchored swing, kept only where they overlap (within sd_htf_tol) an opposing array of a timeframe
    below the daily ('lower than the entry array's timeframe' [our interpretation]). 'stop_run': start = the sweep low (side space), end = the last swing high before the
    sweep; 'midweek' (from Wednesday): start = Wednesday's extreme (side-space low), end = the highest high of the week from Monday's open up to it."""
    cf = _conf(ctx)
    if cf is None:
        return []
    hit("eval_ext_levels")
    start = end = None
    if p.proj_ext_anchor == "stop_run":
        ext_i = sw["ext_i"]
        q = [q for q in sd.ph if q.known <= i and ctx.start <= q.i < ext_i]
        if q:
            start, end = float(sw["ext"]), float(q[-1].price)
    elif ctx.day.weekday() >= 2:
        prev = week_bars(ctx, sd, i)
        if ctx.day.weekday() == 2:
            k0 = int(np.argmin(sd.l[ctx.start:i + 1])) + ctx.start
            start = float(sd.l[k0])
            hi_ = float(sd.h[ctx.start:k0 + 1].max())
        else:
            wed = [x for x in prev if x[0] == 2]
            if wed:
                start, hi_ = wed[0][2], wed[0][1]
            else:
                hi_ = None
        if start is not None and hi_ is not None:
            for wd, h_, l_ in prev:
                if wd < 2 or (wd == 2 and ctx.day.weekday() > 2):
                    hi_ = max(hi_, h_)
            end = hi_
    if start is None or end is None or end <= start:
        return []
    tol = p.sd_htf_tol * p.es_pt
    rows = [_zone_edges(sd, r) for r in cf.opposing_ext(_now(ctx, i), sd.x(above), sd.sign, ("15m", "30m", "1h", "4h"), (0, 1, 2, 3))]
    out = []
    for v in ext_multiples(start, end, (1.27, p.proj_ext2)):
        if v > above and any(a - tol <= v <= b + tol for a, b in rows):
            out.append((float(v), "proj"))
    if out:
        hit("proj_ext_" + p.proj_ext_anchor)
    return out


def adr_levels(ctx, sd, i: int, p, above: float, entry: float, st: dict) -> list:
    """L16 (cc09_006 ~19:23; cc09_007 ~8:32; cc12_004 ~17:45) and X1 (cc09_002 ~17:01): adr_t2_htf = the nearest 1h / 4h opposing array beyond the ADR level is the next rung;
    adr_ext = once a bar traded beyond ADR_hi, ADR_lo + 1.27 / 1.62 x ADR5 (kept within 1 pt of a 15m / 1h array); adr_conv_target = the proj / SD level that sits in an
    opposing 15m / 1h / 4h / D array holding the projected ADR high (min(day low, midnight open) + ADR5) becomes the final target (kind proj_htf), not after adr_conv_last."""
    S = _S()
    adr = _adr(ctx)
    if not adr:
        return []
    out = []
    lo = adr_low(ctx, sd, i, p)
    cf = _conf(ctx)
    if p.adr_t2_htf and cf is not None:
        lvl = lo + p.adr_frac * adr
        rows = [_zone_edges(sd, r)[0] for r in cf.opposing_ext(_now(ctx, i), sd.x(lvl), sd.sign, ("1h", "4h"), (0, 1, 2, 3))]
        rows = [v for v in rows if v > lvl]
        if rows:
            out.append((float(min(rows)), "array"))
            hit("adr_t2_htf")
    if p.adr_ext and cf is not None and sd.h[ctx.start:i + 1].max() >= lo + adr:
        zs = [_zone_edges(sd, r) for r in cf.opposing_ext(_now(ctx, i), sd.x(above), sd.sign, ("15m", "1h"), (0, 1, 2, 3))]
        for e in (1.27, 1.62):
            v = lo + e * adr
            if v > above and any(a - p.es_pt <= v <= b + p.es_pt for a, b in zs):
                out.append((float(v), "proj"))
                hit("adr_ext")
    if p.adr_conv_target and ctx.t[i] <= p.adr_conv_last and cf is not None:
        mo = S._open_known(ctx, "midnight", i)
        base = float(sd.l[ctx.start:i + 1].min())
        if mo is not None:
            base = min(base, float(sd.x(mo)))
        adr_hi = base + adr
        tol = p.adr_conv_pts * p.es_pt
        zs = [_zone_edges(sd, r) for r in cf.opposing_ext(_now(ctx, i), sd.x(above), sd.sign, ("15m", "1h", "4h", "D"), (0, 1, 2, 3))]
        if any(a - tol <= adr_hi <= b + tol for a, b in zs):
            st["adr_hi"] = adr_hi
            hit("eval_adr_conv")
    return out


def pm_leg_levels(ctx, sd, i: int, p, sw: dict, above: float, session: str) -> list:
    """LLT3-pm-measured-move-am-leg (cc10_013 ~2:31; cc10_007 ~8:34): a PM trade with the lunch low above the AM low (a shallow retrace) adds the equal-distance second
    leg: (the trade's sweep low, or the PM swing low) + (AM high - AM low), kind 'proj'. Side space; the AM is 09:30 - 12:00."""
    S = _S()
    if session != "PM":
        return []
    k0, k1, k2 = S._idx_at(ctx, AM_START), S._idx_at(ctx, AM_END), S._idx_at(ctx, 810)
    if not (k0 < k1 <= i and k2 <= i):
        return []
    am_hi, am_lo = float(sd.h[k0:k1].max()), float(sd.l[k0:k1].min())
    lun = sd.l[k1:k2].min(initial=np.inf)
    if not (lun > am_lo and am_hi > am_lo):
        return []
    base = float(sw["ext"]) if sw["ext_i"] >= k2 else float(sd.l[k2:i + 1].min())
    v = base + (am_hi - am_lo)
    if v <= above:
        return []
    hit("pm_am_leg")
    return [(float(v), "proj")]


def pm_rb_levels(ctx, sd, i: int, p, above: float, session: str) -> list:
    """LLT3-pm-target-am-rejection-block (cc10_012 ~4:34): the nearest untraded bearish rejection block of the AM bars (09:30 - 12:00) above price: the body edge (kind 'array',
    first partial) and the wick tip (kind 'pool')."""
    S = _S()
    if session != "PM":
        return []
    k0, k1 = S._idx_at(ctx, AM_START), S._idx_at(ctx, AM_END)
    if not k0 + 3 <= k1 <= i + 1:
        return []
    TP = _TP()
    hit("eval_pm_rb")
    zs = L.rejection_blocks(sd.o[k0:k1], sd.h[k0:k1], sd.l[k0:k1], sd.c[k0:k1], p.pivot_n, p.rb_min_wick_frac, p.rb_level)
    best = None
    for z in zs:
        if z.kind != "bear" or z.bottom <= above or sd.h[k0 + z.i + 1:i + 1].max(initial=-np.inf) >= z.bottom:
            continue
        if best is None or z.bottom < best.bottom:
            best = z
    if best is None:
        return []
    hit("pm_am_rb")
    return [(float(best.bottom), "array"), (float(best.top), "pool")]


def or_wide(ctx, sd, i: int, p):
    """LLT3-wide-or-bias-end (cc10_010 ~6:15): (OR60 high, OR60 low) of today in side space when the 09:30 - 10:30 range is >= wide_or_mult x the median OR60 range of the last 20
    sessions and the opening range is complete at bar i; else None."""
    S = _S()
    k0, k1 = S._idx_at(ctx, 570), S._idx_at(ctx, 630)
    if not (k0 < k1 <= i + 1 and ctx.t[i] + ctx.tf >= 630):
        return None
    rngs = []
    for fr in list(getattr(ctx, "hist", None) or [])[-20:]:
        sub = fr.between_time("09:30", "10:29")
        if len(sub):
            rngs.append(float(sub.high.max() - sub.low.min()))
    if len(rngs) < 10:
        return None
    hit("eval_wide_or")
    hi, lo = float(sd.h[k0:k1].max()), float(sd.l[k0:k1].min())
    return (hi, lo) if (hi - lo) >= p.wide_or_mult * float(np.median(rngs)) else None


def raw_post(ctx, sd, i: int, p, session: str, entry: float, risk: float, above: float, sw: dict, leg_hi: float, lv: list, lvt: list, tags: dict, st: dict) -> list:
    """The raw (level, kind) rungs of the order before the exit prices: the one-sided-leg voids, the re-anchored / impulse measured moves, the OB-entry objective order, the
    double-top projection, the 60-day grades, the cc extension anchors, the ADR rungs, the PM measured move / AM rejection block, the daily-breaker cap."""
    out = list(lv)
    add = []
    if p.void_legs:
        add += void_levels(ctx, sd, i, p, above, st)
    if p.mm_targets and p.mm_anchor in ("reanchor", "impulse"):
        add += mm_levels(ctx, sd, i, p, sw, leg_hi, entry, above)
    if p.ob_target_order:
        add += ob_order_levels(ctx, sd, i, p, above, tags)
    if p.dt_proj:
        add += dt_levels(ctx, sd, i, p, above, st)
    if p.grades60:
        add += grade_rungs(ctx, sd, i, p, above, entry, st, lvt)
    if p.proj_ext_anchor != "leg":
        add += ext_levels(ctx, sd, i, p, sw, above)
    if p.adr_t2_htf or p.adr_ext or p.adr_conv_target:
        add += adr_levels(ctx, sd, i, p, above, entry, st)
    if p.pm_am_leg:
        add += pm_leg_levels(ctx, sd, i, p, sw, above, session)
    if p.pm_am_rb:
        add += pm_rb_levels(ctx, sd, i, p, above, session)
    if p.adr_conv_target and "adr_hi" in st:
        ah, tol = st["adr_hi"], p.adr_conv_pts * p.es_pt
        hits_ = [(v, k) for v, k in out + add if (k.startswith("proj") or k in _TP().SD_KINDS) and abs(v - ah) <= tol + 1e-9]
        if hits_:
            v0 = min(hits_, key=lambda x: abs(x[0] - ah))[0]
            out = [(v, ("proj_htf" if v == v0 else k)) for v, k in out]
            add = [(v, ("proj_htf" if v == v0 else k)) for v, k in add]
            st["adr_final"] = v0
    if p.daily_breaker_cap:
        cap = daily_breaker(ctx, sd, i, p, above)
        if cap is not None:
            out = [(v, k) for v, k in out if v < cap - 1e-9]
            add = [(v, k) for v, k in add if v < cap - 1e-9] + [(cap, "array")]
            st["db_cap"] = cap
            lvt.append("daily_breaker_cap")
            hit("daily_breaker_cap")
    return sorted(set(out) | {(float(v), k) for v, k in add if v > above})


# --- 4. hook E: exit prices of gap / ADR / REH-cluster rungs ----------------------------------------------------------------------------------------

def exit_post(ctx, sd, i: int, p, entry: float, raw: list, kinds: list, lv: list, st: dict) -> list:
    """X2-fvg-exit (items 1 / 7 / 2): after the standard exit prices - 'at_edge': a gap's near edge exits AT the edge; 'deep': every rung at the edge, the last rung (the runner,
    applied in the ladder hook) deep inside; 'adr' rungs exit adr_before_frac x ADR5 before the level, or at the edge of a 15m / 1h array within that buffer minus
    exit_before_pts, whichever is nearer to price; pool_exit 'before': the REH cluster (rel-eq pools within eq_tol_pts) keeps the usual beyond-exit on all but the highest."""
    out = list(lv)
    S = _S()
    hit("eval_exit_post")
    if p.fvg_target_level != "before_edge":
        gaps = gap_registry(ctx, sd, i, p, entry, st)
        for j, (v, k) in enumerate(zip(raw, kinds)):
            if k == "array" and gap_of(v, gaps, p) is not None and abs(gap_of(v, gaps, p)[0] - v) <= 1e-6:
                out[j] = float(v)
                hit("fvg_" + p.fvg_target_level)
    if p.adr_before_frac > 0 and "adr" in kinds:
        adr = _adr(ctx)
        cf = _conf(ctx)
        if adr:
            buf = p.adr_before_frac * adr
            edges = []
            if cf is not None:
                edges = [_zone_edges(sd, r)[0] for r in cf.opposing_ext(_now(ctx, i), sd.x(entry), sd.sign, ("15m", "1h"), (0, 1, 2, 3))]
            for j, k in enumerate(kinds):
                if k != "adr":
                    continue
                px = raw[j] - buf
                near = [e - p.exit_before_pts * p.es_pt for e in edges if abs(e - px) <= buf + 1e-9]
                out[j] = float(min([px] + near))
                hit("adr_before")
    if p.pool_exit == "before":
        eq = sorted((raw[j], j) for j, k in enumerate(kinds) if k == "pool_eq")
        tol = p.eq_tol_pts * p.es_pt
        for a, b in zip(eq, eq[1:]):
            if b[0] - a[0] <= tol + 1e-9:
                out[a[1]] = float(a[0] + 0.25 * p.es_pt)               # scale out above each sub-high (067 ~1:09:17); the highest keeps the 'before' exit
                hit("reh_cluster_before")
    return out


# --- 5. hook C: the daily-breaker cap -------------------------------------------------------------------------------------------------------------

def daily_breaker(ctx, sd, i: int, p, above: float):
    """new-swing-target-breaker-cap (cc06_004 ~29:06): the near edge (side space) of the nearest daily BEARISH breaker above `above` that no daily close has overtaken since
    it formed ([our interpretation]: a daily close above its top = 'the daily chart shows a willingness to go higher'). Daily bars = the completed sessions (ctx.hist)."""
    fr = list(getattr(ctx, "hist", None) or [])[-80:]
    if len(fr) < 8:
        return None
    hit("eval_daily_breaker")
    o = np.array([float(f.open.iloc[0]) for f in fr])
    h = np.array([float(f.high.max()) for f in fr])
    l = np.array([float(f.low.min()) for f in fr])
    c = np.array([float(f.close.iloc[-1]) for f in fr])
    if sd.sign < 0:
        o, h, l, c = -o, -l, -h, -c
    best = None
    for z in L.breakers(o, h, l, c, 1):
        if z.kind != "bear" or z.bottom <= above:
            continue
        if c[z.i + 1:].max(initial=-np.inf) > z.top:
            continue
        if best is None or z.bottom < best:
            best = float(z.bottom)
    return best


def cap_post(ctx, sd, i: int, p, above: float, st: dict):
    """Hook C: the cap merged into the #7 cap of _finish_order (the locked draw ends at the breaker's low too)."""
    if not p.daily_breaker_cap:
        return None
    return st.get("db_cap") if "db_cap" in st else daily_breaker(ctx, sd, i, p, above)


# --- 6. hook L: the ladder after the draw ---------------------------------------------------------------------------------------------------------

def _cut(keep: list, v: float, es: float, add) -> list:
    return [x for x in keep if x[0] < v - es] + [add]


def ladder_004(ctx, sd, i: int, p, keep: list, keep_full: list, draw: float, st: dict):
    """D13-speed-bump-ladder-004 (004 ~1:00): speed bump (a small piece, the stop and break-even untouched) - the next level - the draw (the buy-side pool) - one unit to the
    nearest HTF array beyond the draw. Shares 2/9, 3/9, 3/9, 1/9 (the spec's 0.22 / 0.33 / 0.33 / 0.12 as exact ninths). Missing roles drop out and the rest are renormalised. Returns (keep, fracs) or None."""
    S = _S()
    pre = [x for x in keep if x[0] < draw - p.es_pt]
    dk = next((k for v, k in keep if abs(v - draw) <= p.es_pt), "pool")
    bump = next((x for x in pre if x[1] not in POOLK), None)
    nxt = next((x for x in pre if x is not bump), None)
    rest = [x for x in pre if x not in (bump, nxt)]
    htf = next((x for x in keep_full if x[0] > draw + p.es_pt and x[1] not in POOLK), None)
    if htf is None:
        cf = _conf(ctx)
        if cf is not None:
            rows = [_zone_edges(sd, r)[0] for r in cf.opposing_ext(_now(ctx, i), sd.x(draw), sd.sign, ("4h", "D", "W", "M"), (0, 1, 2, 3))]
            rows = [v for v in rows if v > draw + p.es_pt]
            if rows:
                htf = (float(S._exit_px(min(rows), "array", p)), "array")
    roles = [("bump", (bump[0], "speed") if bump else None), ("next", nxt), ("draw", (draw, dk)), ("htf", htf)]
    w = {"bump": 2 / 9, "next": 1 / 3, "draw": 1 / 3, "htf": 1 / 9}      # the source's 2 / 3 / 3 / 1 units of 9 (the spec's 0.22 / 0.33 / 0.33 / 0.12 rounded): exact in the engine's lot arithmetic
    got = [(r, x) for r, x in roles if x is not None]
    if len(got) < 2:
        return None
    tot = sum(w[r] for r, _ in got)
    rungs = [x for _, x in got]
    fr = [w[r] if len(got) == 4 else w[r] / tot for r, _ in got]
    return rungs, fr


def ladder_037(ctx, sd, i: int, p, entry: float, keep: list, st: dict):
    """X3-037-three-unit-ladder (037 ~53:54): 1/3 at the nearest old short-term high (exact price), 1/3 one tick into the first bearish FVG above it (its near edge), the last 1/3 at
    that FVG's far edge less a tick (or its CE with ladder037_ce). News ahead (0.4, 0.4, 0.2). Returns (rungs, fracs) or None."""
    S = _S()
    TP = _TP()
    pool = next(((v, k) for v, k in keep if k in POOLK or k == "swing"), None)
    if pool is None:
        return None
    raw = TP._raw(pool[0], pool[1], p)
    gaps = [g for g in gap_registry(ctx, sd, i, p, entry, st) if g[0] > raw - 1e-9]
    if not gaps:
        return None
    near, ce, far = min(gaps, key=lambda g: g[0])
    r2 = near + p.tick
    r3 = ce if p.ladder037_ce else far - p.tick
    fr = [0.4, 0.4, 0.2] if news_ahead(ctx, p, i) else [1 / 3, 1 / 3, 1 / 3]
    return [(float(raw), "exact"), (float(r2), "fixed"), (float(r3), "fixed")], fr


def quarters(ctx, sd, i: int, p, entry: float, risk: float, keep: list, st: dict):
    """X3-gradient-ladder-htf-target (065 ~3:53; 070 ~32:22; 098 ~26:26) partial_mode 'quarters': (a) the final level is an HTF gap: near edge, +25 %, CE, +75 % of its height, each
    through the array exit price; (b) a pool precedes it: the pool (beyond), the 25 / 50 / 75 % points of [pool, HTF near edge] (exact), then the near edge less exit_before_pts;
    (c) two pool targets: the 25 / 50 / 75 % points between them, then T2. Equal fractions; ladder_max_levels caps the rungs. Returns (rungs, fracs) or None."""
    S = _S()
    TP = _TP()
    if not keep:
        return None
    last_px, last_k = keep[-1]
    gaps = gap_registry(ctx, sd, i, p, entry, st)
    g = gap_of(last_px, gaps, p) if last_k not in POOLK else None
    pools = [x for x in keep[:-1] if x[1] in POOLK]
    rungs = None
    if pools and last_k not in POOLK:                                  # (b) a pool precedes the HTF array (its near edge is the last rung, exit price = near - exit_before_pts)
        pv = TP._raw(pools[-1][0], pools[-1][1], p)
        hv = last_px + p.exit_before_pts * p.es_pt
        rungs = [pools[-1]] + [(pv + f * (hv - pv), "fixed") for f in (0.25, 0.5, 0.75)] + [(last_px, last_k)]
    elif g is not None:                                                # (a) the final level is an HTF gap (it carries its far edge)
        near, ce, far = g
        h = far - near
        rungs = [(S._exit_px(v, "array", p), "array") for v in (near, near + 0.25 * h, ce, near + 0.75 * h)]
    elif len(keep) >= 2 and last_k in POOLK and keep[-2][1] in POOLK:      # (c) two pool targets
        a_, b_ = TP._raw(keep[-2][0], keep[-2][1], p), TP._raw(last_px, last_k, p)
        rungs = [(a_ + f * (b_ - a_), "fixed") for f in (0.25, 0.5, 0.75)] + [(last_px, last_k)]
    if not rungs:
        return None
    rungs = [x for x in rungs if x[0] - entry >= p.min_rr * risk - 1e-9]
    if p.ladder_max_levels and len(rungs) > p.ladder_max_levels:
        rungs = rungs[:p.ladder_max_levels - 1] + [rungs[-1]]
    if not rungs:
        return None
    return rungs, [1.0 / len(rungs)] * len(rungs)


def energy_first(ctx, sd, i: int, p, keep: list, keep_full: list):
    """X3-partial-size-by-energy (009 ~11:26): the first fraction by delivery quality: 0.5 when the bars that crossed the 09:30 candle's high before the order left no bullish
    gap (a poke without energy); else 0.65 when no pool / array lies within energy_room_pts beyond T1 ('no continuation on the outside'); else None (today's split)."""
    S = _S()
    hit("eval_energy")
    k0 = S._idx_at(ctx, 570)
    if k0 <= i:
        ref = float(sd.h[k0])
        j = next((k for k in range(k0 + 1, i + 1) if sd.h[k] > ref), None)
        if j is not None:
            gap = any(z.i in (j, j + 1) for z in sd.gaps if z.i <= i)
            if not gap:
                hit("energy_poke")
                return 0.5
    if keep:
        t1 = keep[0][0]
        if not any(t1 < v <= t1 + p.energy_room_pts * p.es_pt for v, _ in keep_full if v > t1 + 1e-9):
            hit("energy_no_room")
            return 0.65
    return None


def late(ctx, sd, sw, i: int, p, session: str, entry: float, risk: float, keep: list, keep_full: list, draw: float, final_T: bool, lvt: list, tags: dict,
         st: dict, locked: bool, fixed) -> tuple:
    """The ladder stage after the draw is known (strategy._finish_order, after the targets_partials #1/4 late hook). Returns (reject reason or None, keep, draw, final_T).
    Order: dead-side gates (126), the final-target picks (107 / 131 / 132 / 156 / 169 / 170 / 172), the weekly / monthly beyond tag (119), the pool milestone (37), the ladder shape
    (39 / 43 / 35 / 34 / 42), the fixed partials (41), the no-collapse keep (38), the energy split (40), the deep runner (1), the minimum final reward (106)."""
    S = _S()
    TP = _TP()
    es = p.es_pt
    hit("eval_late3")
    if fixed is not None and not keep:
        return None, keep, draw, final_T
    # --- gates
    if p.dt_proj and st.get("dt_reached"):
        _T2().hit("eval_dt_done")
        return "x_dt_done", keep, draw, final_T
    # --- final-target picks (not under a locked draw: the lock is one exact target)
    def final(v, k, tag):
        nonlocal keep, draw
        keep = _cut(keep, v, es, (float(v), k))
        draw = float(v)
        lvt.append(tag)
        hit(tag)
    if fixed is None and not locked and keep:
        if st.get("adr_final") is not None and st["adr_final"] - entry >= p.min_rr * risk:
            final(S._exit_px(st["adr_final"], "proj_htf", p), "proj_htf", "adr_conv_final")
        if p.target_past_eq60:
            pe = past_eq_final(ctx, sd, i, p, entry, st)
            if pe is not None and pe - entry >= p.min_rr * risk:
                final(S._exit_px(pe, "array", p), "array", "past_eq60_final")
        if st.get("void_final") is not None and st["void_final"] - entry >= p.min_rr * risk and not any(t in lvt for t in ("adr_conv_final", "past_eq60_final")):
            final(S._exit_px(st["void_final"], "array", p), "array", "void_final")
        if p.grades60 and st.get("grades"):
            nx = next((g for g in st["grades"] if g - entry >= p.min_rr * risk), None)
            pools_ = [v for v, k in keep if k in POOLK and v - entry >= p.min_rr * risk]
            if nx is not None and not (pools_ and min(pools_) < nx):
                final(S._exit_px(nx, "grade", p), "grade", "grade_final")
    if fixed is None and keep:
        r = pm_gate_targets(ctx, sd, sw, i, p, session, entry, risk, keep, keep_full, draw, locked, lvt, tags)
        if r is not None:
            why, keep, draw = r
            if why:
                return why, keep, draw, final_T
    # --- weekly / monthly pool beyond the first daily pool (119)
    if p.weekly_beyond_mode != "off" and fixed is None:
        wb, mb = weekly_beyond(ctx, sd, i, p, entry, keep)
        for nm, on in (("weekly_beyond", wb), ("monthly_beyond", mb)):
            if on:
                lvt.append(nm)
                hit(nm)
        if p.weekly_beyond_mode == "require" and not wb:
            return "x_no_weekly_beyond", keep, draw, final_T
    # --- shape + fractions
    fr = None
    scalp = bool(tags.get("single_exit")) or fixed is not None or bool(tags.get("fracs"))
    if p.pool_milestone > 0 and not scalp and keep:
        r = milestone(ctx, sd, i, p, entry, risk, keep)
        if r is not None:
            keep, fr = r
            draw = keep[-1][0]
            lvt.append("pool_milestone")
            hit("pool_milestone")
    if not scalp and keep and fr is None:
        r = None
        if p.ladder_preset == "004":
            r = ladder_004(ctx, sd, i, p, keep, keep_full, draw, st)
        elif p.ladder_preset == "037":
            r = ladder_037(ctx, sd, i, p, entry, keep, st)
        elif p.exit_mode2 == "full_pull":
            first = next((x for x in keep if x[1] in POOLK), keep[-1])
            r = ([first], [1.0])
        elif p.exit_mode2 == "hold_runner":
            r = ([keep[-1]], [1.0])
            tags["day_trade"] = True              # [our interpretation] the stop is never moved: the day-trade flag blocks the break-even / trail code
            tags["no_adds"] = True
            tags.setdefault("exit_at", 945)       # out by 15:45 at the latest (X10)
        elif p.exit_mode2 == "pay_first":
            r = pay_first(p, keep)
            if p.speed_skip:
                tags["tp3_speed"] = True
        elif p.partial_mode == "new":
            r = new_trader(p, keep, final_T)
        elif p.partial_mode == "terminus":
            r = ([keep[-1]], [1.0])
        elif p.partial_mode == "quarters":
            r = quarters(ctx, sd, i, p, entry, risk, keep, st)
        if r is not None:
            keep, fr = r
            draw = keep[-1][0]
            if p.ladder_preset in ("004", "037") or p.exit_mode2 or p.partial_mode in ("new", "terminus", "quarters"):
                lvt.append((p.ladder_preset and "ladder_" + p.ladder_preset) or (p.exit_mode2 and "exit_" + p.exit_mode2) or "partial_" + p.partial_mode)
                hit(lvt[-1])
    if p.fixed_partials and not scalp and keep:
        keep, fr = fixed_rungs(p, entry, keep, fr)
        lvt.append("fixed_partials")
        hit("fixed_partials")
    if p.no_collapse_htf and not scalp and keep:
        r = no_collapse(ctx, sd, i, p, entry, keep, fr, st)
        if r is not None:
            keep, fr = r
            draw = keep[-1][0]
            lvt.append("no_collapse")
            hit("no_collapse")
    if p.energy_split and not scalp and keep and len(keep) > 1:
        f0 = energy_first(ctx, sd, i, p, keep, keep_full)
        if f0 is not None:
            K = len(keep)
            fr = [f0] + [(1.0 - f0) / (K - 1)] * (K - 1)
            lvt.append("energy_split")
    if p.fvg_target_level == "deep" and keep and fixed is None and not scalp:
        g = gap_of(keep[-1][0], gap_registry(ctx, sd, i, p, entry, st), p)
        if g is not None and keep[-1][1] == "array":
            near, ce, far = g
            keep = keep[:-1] + [(float(near + p.fvg_deep_frac * (far - near)), "array")]
            draw = keep[-1][0]
            lvt.append("fvg_deep")
            hit("fvg_deep_runner")
    if fr is not None:
        if len(fr) != len(keep):
            fr = list(fr[:len(keep)]) + [0.0] * (len(keep) - len(fr))
        s_ = sum(fr) or 1.0
        tags["fracs"] = tuple(fr) if abs(s_ - 1.0) < 1e-9 else tuple(f / s_ for f in fr)
        tags["tp3_ladder"] = True
    if p.min_rr_final > 0 and keep:
        fin = draw if (final_T or locked) else keep[-1][0]
        if fin - entry < p.min_rr_final * risk - 1e-9:
            return "x_min_rr_final", keep, draw, final_T
    return None, keep, draw, final_T


def pay_first(p, keep: list):
    """X3-full-pull-vs-mandatory-partial (092 ~1:30:11; cc02_003 ~15:05) 'pay_first': the first pool rung takes at least half; the other rungs share the rest in the
    ladder proportions."""
    K = len(keep)
    j = next((k for k, x in enumerate(keep) if x[1] in POOLK), None)
    if K < 2 or j is None:
        return None
    fr = base_fracs(p, K)
    if fr[j] < 0.5:
        others = [k for k in range(K) if k != j]
        so = sum(fr[k] for k in others) or 1.0
        fr = [0.5 if k == j else fr[k] * 0.5 / so for k in range(K)]
    return list(keep), fr


def new_trader(p, keep: list, final_T: bool):
    """X3-new-vs-experienced-partials (065 ~2:34; 067 ~1:03:59) 'new': the ladder is cut at the first pool (the nearest low-hanging fruit) and new_first (0.8) of the position comes
    off at the first partial, the rest at the pool. A locked draw keeps its first rung and the draw."""
    if final_T and len(keep) > 2:
        keep = [keep[0], keep[-1]]
    else:
        j = next((k for k, x in enumerate(keep) if x[1] in POOLK), None)
        if j is not None:
            keep = keep[:j + 1]
    K = len(keep)
    if K == 1:
        return list(keep), [1.0]
    return list(keep), [p.new_first] + [(1.0 - p.new_first) / (K - 1)] * (K - 1)


def fixed_rungs(p, entry: float, keep: list, fr):
    """X3-five-handle-first-partial-before-draw (036 ~49:59; 060 ~1:14:58): partial rungs at entry + 5.25 and entry + 10 (fixed_partials, kind 'fixed', exact price) before any
    farther level; the shares come from fixed_partial_fracs, the draw rungs share the rest. They are no target: min_draw_pts is judged on the draw alone."""
    last = keep[-1][0]
    add = [(entry + float(d) * p.es_pt, "fixed") for d in p.fixed_partials if entry + float(d) * p.es_pt < last - p.es_pt]
    if not add:
        return keep, fr
    sh = [float(f) for f in p.fixed_partial_fracs[:len(add)]]
    rest = base_fracs(p, len(keep)) if fr is None else list(fr)
    rest = [f * (1.0 - sum(sh)) / (sum(rest) or 1.0) for f in rest]
    items = sorted([(v, k, f) for (v, k), f in zip(add, sh)] + [(v, k, f) for (v, k), f in zip(keep, rest)], key=lambda x: x[0])
    return [(v, k) for v, k, _ in items], [f for _, _, f in items]


def no_collapse(ctx, sd, i: int, p, entry: float, keep: list, fr, st: dict):
    """X3-no-collapse-intermediate-pools (cc03_003 ~25:28; cc04_002 ~16:04): while the HTF draw is untouched a non-final rung never closes the last no_collapse_keep of the units;
    the remainder rides to the HTF draw rung (appended when it lies beyond the ladder)."""
    H = htf_draw(ctx, sd, i, p, entry, st)
    if H is None:
        return None
    S = _S()
    keep = list(keep)
    fr = list(base_fracs(p, len(keep)) if fr is None else fr)
    hx = float(S._exit_px(H, "array", p))
    if hx > keep[-1][0] + p.es_pt:
        keep.append((hx, "array"))
        fr = [f * (1.0 - p.no_collapse_keep) for f in fr] + [p.no_collapse_keep]
    elif abs(hx - keep[-1][0]) <= p.es_pt or keep[-1][0] > hx:
        if fr[-1] < p.no_collapse_keep and len(fr) > 1:
            need = p.no_collapse_keep - fr[-1]
            so = sum(fr[:-1]) or 1.0
            fr = [f * (so - need) / so for f in fr[:-1]] + [p.no_collapse_keep]
    else:
        return None
    return keep, fr


def milestone(ctx, sd, i: int, p, entry: float, risk: float, keep: list):
    """X3-pool-below-untraded-htf-partial (061 ~2:19:41): a pool that lies short of an untouched same-direction HTF array (daily / weekly / monthly, within reach) is a partial
    (pool_milestone of the units), not the final target; the array's near edge is appended as the final rung. The rungs before the pool share half of the rest
    [our interpretation]."""
    st_ = {}
    H = htf_draw(ctx, sd, i, p, entry, st_)
    if H is None:
        return None
    S = _S()
    hx = float(S._exit_px(H, "array", p))
    pools = [k for k, (v, kd) in enumerate(keep) if kd in POOLK and v < hx - p.es_pt]
    if not pools:
        return None
    j = pools[-1]
    head = list(keep[:j + 1])
    m = p.pool_milestone
    n0 = len(head) - 1
    fr = [(1.0 - m) * 0.5 / n0] * n0 + [m] + [(1.0 - m) * 0.5] if n0 else [m, 1.0 - m]
    return head + [(hx, "array")], fr


def weekly_beyond(ctx, sd, i: int, p, entry: float, keep: list) -> tuple:
    """L3-daily-target-weekly-beyond (cc04_003 ~15:58): (weekly_beyond, monthly_beyond) - an untaken weekly (PWH / PWL, a weekly array) / monthly (PMH / PML, a monthly array)
    pool lies beyond T1 = the nearest pool rung."""
    t1 = next((v for v, k in keep if k in POOLK), None)
    if t1 is None:
        return False, False
    hit("eval_weekly_beyond")
    S = _S()
    raw1 = _TP()._raw(t1, "pool", p)
    out = []
    for hl, tfs in ((getattr(ctx, "pw", None), ("W",)), (getattr(ctx, "pm_", None), ("M",))):
        ok = False
        if hl is not None:
            v = sd.x(hl[0] if sd.sign > 0 else hl[1])
            ok = bool(v > raw1 + 1e-9 and sd.h[ctx.start:i + 1].max() < v)
        cf = _conf(ctx)
        if not ok and cf is not None:
            for r in cf.opposing_ext(_now(ctx, i), sd.x(raw1), sd.sign, tfs, (0, 1, 2, 3)):
                ok = True
                break
        out.append(ok)
    return out[0], out[1]


def pm_gate_targets(ctx, sd, sw, i: int, p, session: str, entry: float, risk: float, keep: list, keep_full: list, draw: float, locked: bool, lvt: list, tags: dict):
    """The session-bound final targets: consolidation-day overnight pools (169), the wide-OR end (170), the PM launch-array filter (172), the locked session objective hold (175).
    Returns None (nothing applies) or (reject reason | None, keep, draw)."""
    S = _S()
    es = p.es_pt
    if p.consol_overnight_targets and _T2().is_consol_day(ctx):
        hit("eval_consol_overnight")
        if session != "AM" or ctx.t[i] >= 660:
            return "x_consol_am_only", keep, draw
        k570 = S._idx_at(ctx, 570)
        cands = []
        ld = getattr(ctx, "sess", {}).get("london")
        if ld is not None:
            cands.append(float(sd.x(ld[0] if sd.sign > 0 else ld[1])))
        if k570 > ctx.start:
            cands.append(float(sd.h[ctx.start:k570].max()))
        for q in sd.ph:
            if q.known <= i and ctx.start <= q.i < k570 and sd.h[q.i + 1:i + 1].max(initial=-np.inf) < q.price:
                cands.append(float(q.price))
        cands = sorted(v for v in set(cands) if sd.h[k570:i + 1].max(initial=-np.inf) < v)
        px = [(float(S._exit_px(v, "pool", p)), v) for v in cands]
        px = [x for x in px if x[0] - entry >= p.min_rr * risk]
        if not px:
            return "x_consol_no_overnight", keep, draw
        keep, draw = [(px[0][0], "pool")], px[0][0]
        tags["single_exit"] = True
        lvt.append("consol_overnight")
        hit("consol_overnight")
        return None, keep, draw
    if p.wide_or_draw and ctx.t[i] + ctx.tf >= 630:
        w = or_wide(ctx, sd, i, p)
        want = S._BD.want_at(ctx, p, session, i) if p.htf_bias != "off" else 0
        if w is not None and want == sd.sign and want:
            v = float(S._exit_px(w[0], "pool", p))
            if v - entry >= p.min_rr * risk and sd.h[S._idx_at(ctx, 630):i + 1].max(initial=-np.inf) < w[0]:
                keep = _cut(keep, v, es, (v, "pool"))
                draw = v
                lvt.append("wide_or_draw")
                hit("wide_or_draw")
    if p.pm_launch_filter and session == "PM":
        r = launch_target(ctx, sd, i, p, entry, risk, keep, keep_full)
        if r is not None:
            keep, draw = r
            lvt.append("pm_launch")
            hit("pm_launch")
    if p.session_obj_tf and locked and session == "PM" and str(getattr(ctx, "cur_lock", None) and ctx.cur_lock.get("name", "")).startswith("obj_"):
        tags.setdefault("exit_at", 945)                     # hold_to_obj: not flattened before 15:45 unless stopped
        lvt.append("hold_to_obj")
        hit("hold_to_obj")
    return None, keep, draw


def launch_target(ctx, sd, i: int, p, entry: float, risk: float, keep: list, keep_full: list):
    """LLT3-pm-reversal-launch-array-filter (cc10_013 ~8:50): the PD array that the AM move launched from (the one holding the AM extreme the PM trade turns away from). 4h / D / W:
    the PM trade's final target is that array's near edge. 15m / 30m / 1h: it is traded through - the ladder runs beyond it to the next pool."""
    cf = _conf(ctx)
    if cf is None:
        return None
    S = _S()
    k0, k1 = S._idx_at(ctx, AM_START), S._idx_at(ctx, AM_END)
    if not k0 < k1 <= i:
        return None
    hit("eval_launch")
    d = sd.sign
    x_ = float(ctx.l[k0:k1].min()) if d < 0 else float(ctx.h[k0:k1].max())            # the AM extreme the AM move launched from (real)
    now = float(_now(ctx, i).value)
    tol = p.es_pt * 0.25
    held = None
    for r in cf.rows(("15m", "30m", "1h", "4h", "D", "W"), (0, 1, 3)):
        if r["kind"] == -d and r["known"] <= now < r["dead"] and r["bottom"] - tol <= x_ <= r["top"] + tol:
            held = r if held is None or HTF_ALL.index(r["tf"]) > HTF_ALL.index(held["tf"]) else held
    if held is None:
        return None
    near, far = _zone_edges(sd, held)
    if held["tf"] in ("4h", "D", "W"):
        v = float(S._exit_px(near, "array", p))
        if v - entry >= p.min_rr * risk:
            return _cut(keep, v, p.es_pt, (v, "array")), v
        return None
    nxt = next(((v, k) for v, k in keep_full if k in POOLK and v > far + 1e-9), None)
    if nxt is None:
        return None
    return _cut(keep_full, nxt[0], p.es_pt, nxt), nxt[0]


# --- 7. the sweep gate (pool milestone, setups_models half) ------------------------------------------------------------------------------------

def sweep_gate(ctx, sd, sw: dict, i: int, p, session: str, want: int | None = None):
    """X3-pool-below-untraded-htf-partial (061 ~2:19:41), setups_models half: a counter-direction (reversal) sweep setup whose swept pool lies between price and an untouched HTF
    array in the bias direction is no reversal - the pool is a partial. Returns the reject reason or None. `want` is the bias side (htf_bias); 0 / unknown = no gate."""
    if p.pool_milestone <= 0:
        return None
    S = _S()
    if want is None:
        want = S._BD.want_at(ctx, p, session, i) if p.htf_bias != "off" else 0
    cf = _conf(ctx)
    if not want or want == sd.sign or cf is None:
        return None
    pool = sw.get("level", sw.get("ext"))
    if pool is None:
        return None
    hit("eval_sweep_gate")
    pool_real = float(sd.x(pool))
    TP = _TP()
    for r in cf.opposing_ext(_now(ctx, i), pool_real, want, ("D", "W", "M"), (0, 1, 2, 3)):
        near = r["bottom"] if want > 0 else r["top"]
        ex = TP.extreme_since(ctx, i, r["known"] + 1.0, want > 0)
        if ex is not None and (ex >= near if want > 0 else ex <= near):
            continue
        hit("htf_untraded")
        return "x_htf_untraded"
    return None


# --- 8. the locked session objective (175) ------------------------------------------------------------------------------------------------------

def lock_cands(ctx, p, t_lock: int, kl: int) -> list:
    """LLT3-session-targets-15m-60m (cc10_014 ~4:18): the near edges of the untouched opposing 15m / 1h arrays beyond the price at the lock, as lock candidates (real prices):
    (value, 'array', 'obj_<tf>', 0, created). Both directions (the lock picks its side)."""
    if not p.session_obj_tf or _conf(ctx) is None or kl - 1 < 0:
        return []
    hit("eval_obj_lock")
    S = _S()
    px = float(ctx.c[kl - 1])
    now = pd.Timestamp(ctx.day, tz=ctx.idx.tz) + pd.Timedelta(minutes=t_lock)
    out = []
    for sgn in (1, -1):
        for r in ctx.conf.opposing_ext(now, px, sgn, ("15m", "1h"), (0, 1, 2, 3)):
            near = r["bottom"] if sgn > 0 else r["top"]
            ex = _TP().extreme_since(ctx, kl - 1, r["known"] + 1.0, sgn > 0)
            if ex is not None and (ex >= near if sgn > 0 else ex <= near):
                continue
            out.append((float(near), "array", "obj_" + r["tf"], 0, ctx.start))
    return out


def lock_obj_rank(lst: list) -> list:
    """Hook: the candidates named obj_<tf> come first (stable inside each group). Items are (distance, level, kind, name, dir)."""
    first = [x for x in lst if str(x[3]).startswith("obj_")]
    if first:
        hit("session_obj_lock_rank")
    return first + [x for x in lst if x not in first]


# --- 9. management and report ---------------------------------------------------------------------------------------------------------------------

def speed_defer(pos: dict, k: int, lv: list, h, c, o, l, i: int, sd, p) -> bool:
    """X3-full-pull-vs-mandatory-partial (092 ~1:30:11) speed_skip: the pool rung k is NOT paid when the bar touching it and the bar before are both large-range bars
    (>= 1.5 x the median range of the 20 bars before them) and the touching bar closes beyond the pool - the fraction moves to the next rung [our interpretation: the
    spec's 'next bar' is not known at the touch, so the previous bar stands in for it]. Only a non-final pool rung of an exit_mode2='pay_first' ladder."""
    d = pos.get("tp3")
    if not d or not d.get("speed") or k >= len(pos["fracs"]) - 1:
        return False
    kinds = pos.get("level_kinds") or []
    if k >= len(kinds) or kinds[k] not in POOLK or d.get("skipped", set()) & {k}:
        return False
    rng = sd.h[:i + 1] - sd.l[:i + 1]
    if i < 22:
        return False
    hit("eval_speed")
    med = float(np.median(rng[i - 21:i - 1]))
    if not (rng[i] >= 1.5 * med and rng[i - 1] >= 1.5 * med and sd.c[i] >= lv[k]):
        return False
    fr = list(pos["fracs"])
    fr[k + 1] += fr[k]
    fr[k] = 0.0
    pos["fracs"] = tuple(fr)
    d.setdefault("skipped", set()).add(k)
    hit("speed_skip")
    return True


def on_fill(ctx, sd, pos: dict, tr, o: dict, i: int, p) -> None:
    """Fill time: the state the mid-trade hook needs."""
    if o.get("tp3_speed"):
        pos["tp3"] = dict(speed=True)


def near_miss(pos: dict, tr, p) -> None:
    """X2-projection-target-1tick-before (012 ~29:40; 030 ~24:14) report: the trade's best price fell within 1 pt short of a projection rung that did not fill."""
    kinds = pos.get("level_kinds") or []
    TP = _TP()
    for k, (v, kd) in enumerate(zip(pos["levels"], kinds)):
        if k >= pos["k"] and (kd in TP.SD_KINDS or str(kd).startswith("proj")) and 0 < v - pos["best"] <= p.es_pt + 1e-9:
            tr.near_miss = True
            hit("near_miss")
            return
