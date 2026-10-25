"""Package targets_partials: targets, speed bumps and partial rungs (rule_coverage.md section 3).

Everything here works in SIDE SPACE (a long's prices; a short runs the same code on mirrored
prices, `sd.x`), reads only bars up to the one that just closed, and is called from
strategy._finish_order (target assembly), strategy._targets (pool tweaks), the run_day ladder loop
(rung hits, mid-trade partials) and sb_model / pre_open (the owner #7 speed bump).

Owner #7 REVISED (owner_directives.md): an opposing HTF FVG between price and the draw is a SPEED
BUMP - take a partial at its near edge, keep the rest for the draw. "cap" (the first build: exit
before it, nothing beyond, no trade when the room is short) and the timeframe split ("split": cap on
1h and above, bump on 15m and lower) are switches. An FVG BEHIND the trade is never a target.

A trade's ladder is a list of RUNGS: `main` rungs share the ladder fractions as before, `extra`
rungs (wick CE partial, -0.5 SD, halfway, inner levels) each take a small share of the whole
position (Params.partial_extra_frac, capped by partial_extra_cap) and the mains share the rest.
Protected rungs (the speed bump, the wick CE rung, -0.5 SD) are never lost to the rung cap: they
become extras. With no switch on, no plan is built and the old ladder code runs unchanged.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import levels as L

POOL_KINDS = ("pool", "pool_eq")
SD_KINDS = ("sd", "sd_half", "sd_mm", "sd_ext", "sd_cluster", "proj", "proj_htf", "proj_cluster", "proj_runner", "proj_lh", "proj_wk")     # (the proj* kinds are the caption-gap SD-range projections: they take sd_close_hit / sd_align like the SD levels)
CF_SRC = {"fvg": 0, "ob": 1, "gap": 2, "vi": 3, "breaker": 4}
ALL_SRC = (0, 1, 2, 3, 4)


# --- small helpers ----------------------------------------------------------------------------

def _ph(sd):
    """The swing highs the pools are made of (caption-gap B5 pool_tf: the pool_tf bars' pivots when set, else the base bars')."""
    pp = getattr(sd, "pool_piv", None)
    return sd.ph if pp is None else pp[0]


def now_ts(ctx, i: int) -> pd.Timestamp:
    """The close time of bar i (what a confluence array must be known by)."""
    return ctx.idx[i] + pd.Timedelta(minutes=ctx.tf)


def _ns(ctx) -> np.ndarray:
    a = getattr(ctx, "_tp_ns", None)
    if a is None:
        a = np.asarray(ctx.idx.as_unit("ns").asi8)
        ctx._tp_ns = a
    return a


def _hist_hl(ctx):
    """(bar start ns, high, low, close) of up to 120 regular sessions BEFORE the day frame's first
    (previous-session) block - the frame itself covers that one and today."""
    c = getattr(ctx, "_tp_hist", None)
    if c is None:
        fr = list(getattr(ctx, "hist", None) or [])[-121:-1]      # review: 120 sessions (was 30)
        if fr:
            f = pd.concat(fr)
            c = (np.asarray(f.index.as_unit("ns").asi8), f.high.values.astype(float), f.low.values.astype(float),
                 f.close.values.astype(float))
        else:
            c = (np.zeros(0, dtype=np.int64), np.zeros(0), np.zeros(0), np.zeros(0))
        ctx._tp_hist = c
    return c


def extreme_since(ctx, i: int, t_ns: float, up: bool):
    """Real prices: the highest high (up) / lowest low of the bars that START at or after t_ns,
    through bar i. None when there is no such bar. Reads the regular-session history plus the
    day frame (a bar is used once it has closed: index <= i)."""
    ts, hi, lo, _ = _hist_hl(ctx)
    vals = []
    m = ts >= t_ns
    if m.any():
        vals.append(float(hi[m].max() if up else lo[m].min()))
    ns = _ns(ctx)[:i + 1]
    m2 = ns >= t_ns
    if m2.any():
        vals.append(float(ctx.h[:i + 1][m2].max() if up else ctx.l[:i + 1][m2].min()))
    if not vals:
        return None
    return max(vals) if up else min(vals)


def _ex(S, v, k, p):
    return S._exit_px(v, k, p)


def _zone_edges(sd, row):
    """Side-space (near, far) of an opposing confluence row (real top / bottom)."""
    a, b = sd.x(row["top"]), sd.x(row["bottom"])
    return min(a, b), max(a, b)


# --- owner #7 (revised): speed bump / cap -----------------------------------------------------

def resist_cfg(p):
    """(cap timeframes, bump timeframes) of the opposing-HTF-array rule. htf_resist_cap=False turns
    both off. "cap": all of htf_resist_tfs cap; "bump" (the default): all bump; "split": the
    timeframes in htf_resist_cap_tfs cap, the rest bump."""
    if not p.htf_resist_cap:
        return (), ()
    tfs = tuple(p.htf_resist_tfs)
    if p.htf_resist_mode == "cap":
        return tfs, ()
    if p.htf_resist_mode == "bump":
        return (), tfs
    cap = tuple(t for t in tfs if t in p.htf_resist_cap_tfs)
    return cap, tuple(t for t in tfs if t not in cap)


def bump_levels(ctx, sd, i: int, p, entry: float, risk: float, tfs, src, capx=None, now=None) -> list:
    """The speed bumps: up to htf_bump_max opposing HTF arrays (source `src`) between the entry and
    the draw, as exit prices (side space) just before the near edge (htf_resist_buffer_pts). An
    array the entry sits inside (its near edge is behind the entry) is a bump at its CE, or its far
    edge when the CE is behind the entry too [our interpretation]. A bump under min_rr x risk from
    the entry stays a (protected, small) partial when htf_bump_below_min is on and it is at least
    inner_min_pts from the entry; otherwise it is dropped. One beyond a cap is dropped."""
    conf = ctx.conf
    rows = conf.opposing_ext(now_ts(ctx, i) if now is None else now, sd.x(entry), sd.sign, tfs, src, straddle=True)
    buf = p.htf_resist_buffer_pts * p.es_pt
    out = []
    for r in rows:
        near, far = _zone_edges(sd, r)
        if near > entry:
            v = near - buf
        else:
            ce = (near + far) / 2
            v = (ce if ce > entry else far) - buf
        if v - entry < (p.inner_min_pts * p.es_pt if p.htf_bump_below_min else p.min_rr * risk):
            continue
        if capx is not None and v > capx:
            continue
        if not any(abs(v - w) <= p.es_pt for w in out):
            out.append(v)
        if len(out) >= max(p.htf_bump_max, 1):
            break
    return sorted(out)


def apply_resist(ctx, sd, i: int, p, entry: float, risk: float, lv: list, kinds: list, flag, skip=()):
    """Owner #7 on the target list (exit prices, side space). Returns dict(lv, kinds, capx, resist,
    bumps) or None when the cap leaves too little room (x_htf_resist). `flag(name)` counts a skip.
    Caption-gap N-opposing-fvg-speed-bump (019 ~00:11:08; Params.speed_bump_tfs): the timeframe names in `skip` are neither a cap nor a bump rung."""
    out = dict(lv=lv, kinds=kinds, capx=None, resist=None, bumps=[])
    cap_tfs, bump_tfs = resist_cfg(p)
    if skip:
        cap_tfs, bump_tfs = tuple(t for t in cap_tfs if t not in skip), tuple(t for t in bump_tfs if t not in skip)
    if not (cap_tfs or bump_tfs):
        return out
    if getattr(ctx, "conf", None) is None:
        flag("x_htf_resist_nodata")
        return out
    src = tuple(CF_SRC[x] for x in p.htf_resist_src)
    now = now_ts(ctx, i)
    capx = None
    if cap_tfs:
        r = ctx.conf.resistance(now, sd.x(entry), sd.sign, cap_tfs, src)
        if r is not None:
            capx = sd.x(r[0]) - p.htf_resist_buffer_pts * p.es_pt
            if capx - entry < max(p.min_rr * risk, p.htf_resist_min_room * p.es_pt):
                flag("x_htf_resist")
                return None
            pairs = [(v, k) for v, k in zip(lv, kinds) if v <= capx]
            if not any(abs(v - capx) <= p.es_pt for v, _ in pairs):
                pairs.append((capx, "array"))
            pairs.sort()
            lv, kinds = [v for v, _ in pairs], [k for _, k in pairs]
            out.update(lv=lv, kinds=kinds, capx=capx, resist=r)
    if bump_tfs:
        bumps = bump_levels(ctx, sd, i, p, entry, risk, bump_tfs, src, capx)
        pairs = list(zip(lv, kinds))
        for b in bumps:
            j = next((k for k, (v, kd) in enumerate(pairs) if abs(v - b) <= p.es_pt and kd not in POOL_KINDS), None)
            if j is not None:
                pairs[j] = (pairs[j][0], "bump")            # the existing rung is the bump
            elif not any(abs(v - b) <= p.es_pt for v, _ in pairs):
                pairs.append((b, "bump"))
        pairs.sort()
        out.update(lv=[v for v, _ in pairs], kinds=[k for _, k in pairs], bumps=bumps)
    return out


# --- HTF array levels with identity (L9 / A22 / L14d) -----------------------------------------

def needs_htf_rows(p) -> bool:
    return bool(p.fvg_over_ob or p.skip_exhausted or "htf" in p.target_hygiene or p.fvg_remainder
                or p.weekly_gap_ce_only)


def htf_levels(ctx, sd, i: int, above: float, p, htf_t: tuple) -> list:
    """The opposing HTF array levels of `conf.targets` (near edge, CE, far edge with htf_far_edge) as
    (side-space level, "array"), with the targets_partials filters:
      fvg_over_ob        an OB overlapping an FVG on the same side is dropped - the FVG's edge is the target (L9)
      weekly_gap_ce_only a weekly gap (NWOG) gives its CE only; the far edge is a ringer (L9)
      skip_exhausted /
      hygiene "htf"      an array price already traded into since it formed is not a target (A22, L14);
                         gaps are never retired (039)
      fvg_remainder      a partly traded FVG keeps its unvisited remainder: the traded extreme (or its
                         near edge), the remainder's CE and the far edge (L9, 038 ~1:11:44)"""
    conf = ctx.conf
    now = now_ts(ctx, i)
    rows = conf.opposing_ext(now, sd.x(above), sd.sign, htf_t, ALL_SRC)
    up = sd.sign > 0                                    # real direction price must travel
    out = []
    fvgs = [(r["bottom"], r["top"]) for r in rows if r["src"] == 0]
    for r in rows:
        if p.fvg_over_ob and r["src"] == 1 and any(b < r["top"] and t > r["bottom"] for b, t in fvgs):
            continue
        near, far = _zone_edges(sd, r)
        ce = (near + far) / 2
        lv = [near, ce] + ([far] if p.htf_far_edge else [])
        if r["src"] == 2 and r["tf"] == "W" and p.weekly_gap_ce_only:
            lv = [ce]
        elif r["src"] != 2 and (p.skip_exhausted or "htf" in p.target_hygiene or p.fvg_remainder):
            ext = extreme_since(ctx, i, r["known"], up)
            near_real = r["bottom"] if up else r["top"]
            touched = ext is not None and (ext >= near_real if up else ext <= near_real)
            if touched and p.array_reuse != "first_touch" and not p.fvg_remainder:
                from . import tp1 as _T1                     # caption-gap A22-array-reuse (061 ~2:11:51): a touched array stays valid until a body closes through its CE
                if _T1.untouched(ctx, sd.sign, i, r):
                    touched = False
                    _T1.hit("array_reuse")
            if touched:
                if not p.fvg_remainder:
                    continue
                trav = sd.x(ext)                      # side space: how far price went into the array
                rem_near = max(near, trav)
                if rem_near >= far:
                    continue
                lv = [rem_near, (rem_near + far) / 2, far]
        out += [(float(v), "array") for v in lv if v > above]
    return out


# --- pool tweaks (called from strategy._targets / _finish_order) ------------------------------

def rel_pools(ctx, sd, i: int, p) -> list:
    """L4 rel_tfs: relative equal highs on m-minute bars (completed bars only, built from the day
    frame up to bar i) - clusters of >= 2 untaken swing highs within eq_tol_pts. Side space. The
    pool's minutes are remembered in ctx._tp_pool_tf for pool_rank."""
    out = []
    tol = p.eq_tol_pts * p.es_pt
    tfmap = ctx.__dict__.setdefault("_tp_pool_tf", {})
    for m in p.rel_tfs:
        if m <= ctx.tf:
            continue
        idx = ctx.idx[:i + 1]
        g = pd.Series(np.arange(i + 1), index=idx).groupby(idx.floor(f"{m}min"))
        first, last, st = g.min().values, g.max().values, g.min().index
        done = (idx[last] - st) >= pd.Timedelta(minutes=m - ctx.tf)       # the m-minute bar has closed
        if done.sum() < 3:
            continue
        hh = np.array([sd.h[a:z + 1].max() for a, z in zip(first, last)])[done]
        ll = np.array([sd.l[a:z + 1].min() for a, z in zip(first, last)])[done]
        lastd = last[done]
        ph, _ = L.pivots(hh, ll, 1)
        vals = [q.price for q in ph
                if sd.h[lastd[q.i] + 1:i + 1].max(initial=-np.inf) < q.price
                and lastd[q.i] >= ctx.start - 1]
        for v in L.equal_levels(vals, tol):
            out.append(float(v))
            tfmap[round(float(v), 6)] = m
    return out


def close_pools(ctx, sd, i: int, p, above: float) -> list:
    """Ep07.1 close_draw (Ep 07: an old daily close is an "unrealized premium array"): the closes of
    the last five regular sessions and of last week's final session that price has NOT traded back
    to since (no bar from the next session on reached the close), above `above`, as pools (side
    space). The closes come from the session frames, never from a later day."""
    hist = list(getattr(ctx, "hist", None) or [])
    if not hist:
        return []
    out = []
    cands = [(float(fr.close.iloc[-1]), fr.index[-1]) for fr in hist[-5:]]
    wk = ctx.day.isocalendar()[:2]
    prev_wk = [fr for fr in hist if fr.index[0].date().isocalendar()[:2] != wk]
    if prev_wk:                                    # last week's close (the weekly draw as a pool)
        cands.append((float(prev_wk[-1].close.iloc[-1]), prev_wk[-1].index[-1]))
    seen = set()
    for cl, t_end in cands:
        key = round(cl, 4)
        if key in seen:
            continue
        seen.add(key)
        ext_hi = extreme_since(ctx, i, float(t_end.value) + 1.0, True)
        ext_lo = extreme_since(ctx, i, float(t_end.value) + 1.0, False)
        if ext_hi is None or ext_lo is None:
            continue
        if ext_lo <= cl <= ext_hi:                 # price traded through / back to it: realized
            continue
        v = sd.x(cl)
        if v > above:
            out.append((float(v), None))
    return out


def body_edge(ctx, sd, i: int, v: float, p, need_wick: bool):
    """A17 / L11: the body edge (side space) of the swing-high candle whose wick tip is `v`, from the
    day frame and the last sessions; None when the level is no bar's high or (need_wick) the wick is
    shorter than rb_min_wick_frac of the candle's range."""
    real = sd.x(v)
    frames = list(getattr(ctx, "hist", None) or [])[-6:]
    tol = 1e-9 + 0.01 * p.es_pt
    for o, h, l, c in [(ctx.o[:i + 1], ctx.h[:i + 1], ctx.l[:i + 1], ctx.c[:i + 1])] + [
            tuple(fr[k].values.astype(float) for k in ("open", "high", "low", "close")) for fr in reversed(frames)]:
        tip = h if sd.sign > 0 else l
        k = np.flatnonzero(np.abs(tip - real) <= tol)
        if not len(k):
            continue
        k = int(k[-1])
        body = max(o[k], c[k]) if sd.sign > 0 else min(o[k], c[k])
        rng = h[k] - l[k]
        wick = abs(tip[k] - body)
        if rng <= 0 or wick <= 0:
            return None
        if need_wick and wick < p.rb_min_wick_frac * rng:
            return None
        return float(sd.x(body))
    return None


# --- obstacles / resistance -------------------------------------------------------------------

def resistance_count(ctx, sd, i: int, p, entry: float, level: float) -> int:
    """L4 / X3f: the obstacles between the entry and `level` (side space): untouched opposing intraday
    FVGs / voids, untaken short-term swing highs of today's session, and opposing 15m+ arrays. A
    low-resistance run has few of them ("few overlapping swings between price and target")."""
    n = 0
    h = sd.h
    for z in sd.opposing():
        if z.i <= i and entry < z.bottom < level and h[z.i + 1:i + 1].max(initial=-np.inf) < z.bottom:
            n += 1
    for q in _ph(sd):
        if q.known <= i and q.i >= ctx.start - 1 and entry < q.price < level \
                and h[q.i + 1:i + 1].max(initial=-np.inf) < q.price:
            n += 1
    if getattr(ctx, "conf", None) is not None:
        for r in ctx.conf.opposing_ext(now_ts(ctx, i), sd.x(entry), sd.sign, ("15m", "1h", "4h", "D"), (0,)):
            near, _ = _zone_edges(sd, r)
            if entry < near < level:
                n += 1
    return n


def smoothness(sd, i: int, v: float, tol: float) -> float:
    """Ep04.11: how clean an equal-high level is = the spread of the swing highs forming it (0 = to
    the tick) plus a penalty per bar between the touches that poked above it. Smaller = cleaner."""
    qs = [q for q in _ph(sd) if q.known <= i and abs(q.price - v) <= tol]
    if len(qs) < 2:
        return 1e9
    spread = max(q.price for q in qs) - min(q.price for q in qs)
    a, b = min(q.i for q in qs), max(q.i for q in qs)
    pokes = int((sd.h[a:b + 1] > max(q.price for q in qs) + 1e-9).sum())
    return spread + 10.0 * pokes * tol


def draw_pref(ctx, sd, i: int, p, entry: float, risk: float, keep: list, leg_hi: float, sw: dict) -> list:
    """L4 / Ep04.11 draw overrides for the non-lock path: [(exit level, kind, name)] among the pools
    of `keep` (exit prices). The caller takes the nearest preference that pays min_rr.
      pool_rank       the larger pool: timeframe (rel_tfs minutes, D/W/M for daily levels), then touch count -
                      within pool_rank_reach x the distance to the nearest pool [our interpretation]
      draw_below_eq   only pools beyond the equilibrium of the dealing range (prior-day range, widened by the
                      sweep extreme / leg high) - "the pool below EQ" mirrored (042 ~1:09:17)
      lrlr_max        the nearest pool whose run has <= N obstacles (low resistance) over a high-resistance one
      clean_eq_pref   the smoothest relative-equal-high pool"""
    out = []
    pools = [(v, k) for v, k in keep if k in POOL_KINDS and v - entry >= p.min_rr * risk]
    if not pools:
        return out
    tol = p.eq_tol_pts * p.es_pt
    cands = list(pools)
    eq = None
    if p.draw_below_eq:
        lo, hi = float(sw["ext"]), float(max(leg_hi, entry))
        from . import tp2 as _T2
        hi_r = _T2.eq_leg_hi(ctx, sd, sw, leg_hi, p)         # caption-gap L4-target-below-eq-leg (042 ~01:09:19): eq_leg "rally" - the leg runs from the high that began the run into the sweep
        if hi_r is not None:
            hi = max(hi_r, float(sw["ext"]) + 1e-9)
        hist = getattr(ctx, "hist", None)
        if hist and hi_r is None:                           # (eq_leg 'rally': the leg itself is the range - no prior-day widening)
            pdh, pdl = float(hist[-1].high.max()), float(hist[-1].low.min())
            a, b = sd.x(pdh), sd.x(pdl)
            lo, hi = min(lo, a, b), max(hi, a, b)
        eq = (lo + hi) / 2
        cands = [(v, k) for v, k in cands if v > eq] or cands
    if p.lrlr_max >= 0:
        ok = [(v, k) for v, k in cands if resistance_count(ctx, sd, i, p, entry, v) <= p.lrlr_max]
        cands = ok or cands
    best = None
    name = "pool_pick"
    if p.pool_rank:
        reach = p.pool_rank_reach * (cands[0][0] - entry)
        near = [(v, k) for v, k in cands if v - entry <= reach] or cands[:1]
        tfmap = getattr(ctx, "_tp_pool_tf", {})

        def score(vk):
            v = vk[0]
            tfm = 0.0
            m = tfmap.get(round(v - p.pool_beyond_pts * p.es_pt, 6)) or tfmap.get(round(v, 6))
            if m:
                tfm = float(m)
            for key in ("pdh1", "pdh2", "pdh3", "pdl1", "pdl2", "pdl3"):
                if key in ctx.pd and abs(sd.x(ctx.pd[key]) - (v - p.pool_beyond_pts * p.es_pt)) <= tol:
                    tfm = max(tfm, 1440.0)
            for hl, w in ((getattr(ctx, "pw", None), 7200.0), (getattr(ctx, "pm_", None), 43200.0)):
                if hl is not None and abs(sd.x(hl[0] if sd.sign > 0 else hl[1]) - (v - p.pool_beyond_pts * p.es_pt)) <= tol:
                    tfm = max(tfm, w)
            touches = sum(1 for q in _ph(sd) if q.known <= i and abs(q.price - (v - p.pool_beyond_pts * p.es_pt)) <= tol)
            return (-tfm, -touches, v)

        best = sorted(near, key=score)[0]
        name = "pool_rank"
    if p.clean_eq_pref:
        eqs = [(v, k) for v, k in cands if k == "pool_eq"]
        if eqs:
            best = sorted(eqs, key=lambda vk: (smoothness(sd, i, vk[0] - p.pool_beyond_pts * p.es_pt, tol), vk[0]))[0]
            name = "clean_eq"
    if best is None and (p.draw_below_eq or p.lrlr_max >= 0):
        best = cands[0]
        name = "pool_eq_leg" if p.draw_below_eq else "lrlr"
    if best is not None and p.eq_beyond_imb and p.draw_below_eq and eq is not None:
        from . import tp2 as _T2
        nv = _T2.beyond_imb(ctx, sd, i, p, _raw(best[0], best[1], p))       # caption-gap L4-target-below-eq-leg (049 ~00:03:42): the first 15m (else 60m) imbalance beyond the pool, when it lies beyond the EQ
        if nv is not None and nv > eq:
            out.append((_exit_px_s(nv, p), "array", "eq_beyond_imb"))
            return out
    if best is not None:
        out.append((best[0], best[1], name))
    return out


# --- target sources (called from strategy._finish_order) --------------------------------------

def _raw(v: float, k: str, p) -> float:
    """Inverse of strategy._exit_px: the level a rung's exit price belongs to."""
    if p.exit_mode == "split" and k in POOL_KINDS:
        return v - p.pool_beyond_pts * p.es_pt
    if k in ("exact", "fixed"):
        return v
    if p.proj_exit_ticks and k.startswith("proj"):          # caption-gap L12-projection-exit-1tick: the projection rungs exit proj_exit_ticks before the level
        return v + p.proj_exit_ticks * p.tick
    if p.proj_kind and (k in SD_KINDS or k.startswith("proj")):    # caption-gap X2-projection-target-1tick-before: proj_before_pts before the level
        return v + p.proj_before_pts * p.es_pt
    return v + p.exit_before_pts * p.es_pt


def leg_start(sd, ext_i: int, floor: int, max_back: int = 60):
    """A10 [CC] / D23 "downleg": the start of the one-sided displacement leg that ends at the sweep
    extreme (side space: a run of down-close candles into the low, one counter candle allowed): the
    first candle's index and the run's highest high. A leg of fewer than two candles is none."""
    j, counter = ext_i, 0
    while j - 1 >= max(floor, 0) and ext_i - j < max_back:
        k = j - 1
        if sd.c[k] <= sd.o[k]:
            j = k
            continue
        if counter < 1 and k - 1 >= max(floor, 0) and sd.c[k - 1] <= sd.o[k - 1]:
            counter += 1
            j = k
            continue
        break
    if ext_i - j < 2:
        return None
    return j, float(sd.h[j:ext_i + 1].max())


def measuring_gap(sd, sw: dict, i: int, leg_hi: float, p):
    """A6 (003 ~31:35; 011 ~6:37; 061 ~1:22:05; 062 ~42:19): the FVG near the middle of the displacement
    leg - formed after the sweep extreme, its near edge in `measuring_band` of the leg and its CE within
    measuring_mid_frac (0.15, from the gap notes) of the leg's 50%, still open (no body closed through
    it). Returns the gap nearest the middle or None."""
    ext, ext_i = float(sw["ext"]), sw["ext_i"]
    rng = leg_hi - ext
    if rng <= 0:
        return None
    lo_b, hi_b = p.measuring_band
    best = None
    for g in sd.gaps:
        if not (g.i - 2 >= ext_i and g.i <= i):
            continue
        f_near = (g.bottom - ext) / rng
        f_ce = (g.mid - ext) / rng
        if not (lo_b <= f_near <= hi_b) or abs(f_ce - 0.5) > p.measuring_mid_frac:
            continue
        if sd.c[g.i + 1:i + 1].min(initial=np.inf) < g.bottom:           # bodies closed through it
            continue
        if best is None or abs(f_ce - 0.5) < abs((best.mid - ext) / rng - 0.5):
            best = g
    return best


def measuring_level(g, ext: float, anchor: str) -> float:
    """Ep03.5 / A6 projection (bullish; mirrored by side space): "far" = the gap's far edge from the
    swing (the gap notes' reading of 061 / 062: target = BISI high + (BISI high - root low)), "near" =
    the first reading of A6 (near edge), "ce", "dup" = 061's alternative (the range duplicated from the
    gap's other edge: near edge + (far edge - root))."""
    if anchor == "near":
        a = g.bottom
    elif anchor == "ce":
        a = g.mid
    elif anchor == "dup":
        return g.bottom + (g.top - ext)
    else:
        a = g.top
    return a + (a - ext)


def _pools_raw(lv: list) -> list:
    return [v for v, k in lv if k in POOL_KINDS]


def sd_active(p) -> bool:
    """The new SD engine replaces the old single-anchor block of strategy._targets."""
    from . import tp2 as _T2
    return bool(p.sd_targets and (p.sd_anchor not in ("leg", "sweep_leg") or p.sd_roles or p.sd_align
                                  or p.sd_cluster_ticks or p.sd_no_pool_fallback or _T2.sd_on(p)))


def sd_ranges(ctx, sd, i: int, p, sw: dict, leg_hi: float, rr) -> list:
    """The (name, lo, hi) ranges (side space) the SD levels hang on. D23 / L12 / Ep06.4:
      leg      sweep extreme .. leg high (the first build; "sweep_leg")
      broken   sweep extreme .. the broken MSS swing (the recommended anchor, D23)
      downleg  014: the one-sided down-leg into the low - its start high .. the extreme
      fulcrum  the first confirmed swing high after the extreme, measured only once a close is above it (Ep 06)
      london   (= manip) the London swing low .. high, measured only once a close is above the high
      multi    all of them, plus the last `sd_swings` confirmed swing legs of the session"""
    name = {"sweep_leg": "leg", "manip": "london", "mss_leg": "broken"}.get(p.sd_anchor, p.sd_anchor)     # (caption-gap L12-minus3-sd-last-hour: "mss_leg" = the sweep extreme .. the broken MSS swing, the "broken" leg)
    if name == "fulcrum_week":                           # caption-gap new-swing-projection-fulcrum (cc07_003 ~27:33): tp1.fulcrum_levels reads it; here only the range
        from . import tp1 as _T1
        f_ = _T1.fulcrum_week(ctx, sd, i, p)
        return [("fulcrum_week", f_[0], f_[1])] if f_ is not None else []
    names = ("leg", "broken", "downleg", "fulcrum", "london") if name == "multi" else (name,)
    if name in ("entry_low", "m15_leg"):                  # entry_low: the projection is built mid-trade (tp2.manage); m15_leg: added below
        names = ()
    ext, ext_i = float(sw["ext"]), sw["ext_i"]
    out = []
    for nm in names:
        if nm == "leg":
            out.append((nm, ext, float(leg_hi)))
        elif nm == "broken" and rr is not None:
            ref = float(rr[1])
            if ref > ext and (sd.c[ext_i + 1:i + 1] > ref).any():
                out.append((nm, ext, ref))
        elif nm == "downleg":
            ls = leg_start(sd, ext_i, 0)
            if ls is not None and ls[1] > ext:
                out.append((nm, ext, ls[1]))
        elif nm == "fulcrum" and p.sd_fulcrum_def == "inception":       # caption-gap D23-inception-fulcrum-anchor (090 ~01:34:04; 092 ~01:21:26)
            from . import tp2 as _T2
            out += _T2.sd_ranges_extra(ctx, sd, i, p, sw, "inception")
        elif nm == "fulcrum":
            q = next((q for q in sd.ph if q.i > ext_i and q.known <= i), None)
            if q is not None and q.price > ext and (sd.c[q.i + 1:i + 1] > q.price).any():
                out.append((nm, ext, float(q.price)))
        elif nm == "london":
            lon = getattr(ctx, "sess", {}).get("london")
            if lon is not None and ctx.t[i] >= lon[2]:
                hi_, lo_ = (lon[0], lon[1]) if sd.sign > 0 else (-lon[1], -lon[0])
                a = int(np.searchsorted(ctx.t[ctx.start:], lon[2])) + ctx.start
                if hi_ > lo_ and sd.c[a:i + 1].max(initial=-np.inf) > hi_:
                    out.append((nm, float(lo_), float(hi_)))
    if name == "m15_leg":                                  # caption-gap L12-prior-session-swing-htf-extreme (035 ~00:38:13)
        from . import tp2 as _T2
        out += _T2.sd_ranges_extra(ctx, sd, i, p, sw, "m15_leg")
    if p.sd_multi_tiers:                                   # caption-gap L12-cluster-anchors (014 ~00:03:48)
        from . import tp2 as _T2
        out += _T2.tier_ranges(ctx, sd, i, p, sw)
    if name == "multi" and p.sd_swings:
        legs = []
        for qh in sd.ph:
            if qh.known > i or qh.i < ctx.start:
                continue
            ql = [q for q in sd.pl if q.i < qh.i and q.known <= i and q.i >= ctx.start]
            if ql and (sd.c[qh.i + 1:i + 1] > qh.price).any():
                legs.append(("swing", float(ql[-1].price), float(qh.price)))
        out += legs[-p.sd_swings:]
    return [r for r in out if r[2] > r[1]]


def sd_levels(ctx, sd, i: int, p, sw: dict, leg_hi: float, rr, lv: list, entry: float, risk: float, lvt: list) -> list:
    """The SD targets of the new engine as raw (level, kind) pairs. Per anchor: only the first level
    beyond the nearest pool (sd_first_beyond; skip levels at or before it - 014 / 030; with no pool
    nothing, or with sd_no_pool_fallback the first level that pays min_rr). sd_align keeps a level only
    within sd_align_tol_pts of a pool or array level of the list [the "time" alignment is not coded: no
    rule gives a clock]. sd_cluster_ticks: levels from several anchors within N ticks are one cluster
    (the mean, kind sd_cluster) - only clusters are kept when any exist. sd_roles gives the kinds
    sd_half (0.5) / sd_mm (1.0) / sd_ext (2+) the partial planner reads."""
    pools = sorted(v for v, k in lv if k in POOL_KINDS and v > max(leg_hi, entry))
    pool = pools[0] if pools else None
    got = []
    if p.sd_anchor == "fulcrum_week":                    # caption-gap new-swing-projection-fulcrum: low + m x (high - low) for the sd_fulcrum_ext multiples (1.27 / 1.68 / 2.0)
        from . import tp1 as _T1
        got = [(v, 0.0, "fulcrum_week") for v in _T1.fulcrum_levels(ctx, sd, i, p, entry)]
        out = [(float(v), "sd") for v, _, _ in got]
        if out:
            lvt.append("sd_fulcrum_week")
        return out
    from . import tp2 as _T2                              # caption-gap pass (targets_partials #2/4): the arming, the rolled reference, the premium / last-hour / HTF-extreme / deep-convergence picks
    t2 = _T2.sd_on(p)
    for nm, lo, hi in sd_ranges(ctx, sd, i, p, sw, leg_hi, rr):
        if t2 and not _T2.armed(ctx, sd, sw, i, p, nm, lo, hi):
            continue
        rng = hi - lo
        cand = sorted((hi + k * rng, k) for k in p.sd_levels)
        if t2:
            got += [(v, k, nm, kd) for v, k, kd in _T2.sd_cands(ctx, sd, i, p, sw, nm, lo, hi, cand, pool, lv, entry, risk) if v > entry]
            continue
        if p.sd_first_beyond:
            if pool is not None:
                cand = [x for x in cand if x[0] > pool][:1]
            elif p.sd_no_pool_fallback:
                cand = [x for x in cand if x[0] - entry >= p.min_rr * risk][:1]
            else:
                cand = []
        got += [(v, k, nm, "") for v, k in cand if v > entry]
    if t2:
        got = _T2.sd_tail(ctx, sd, i, p, sw, got, lv, max(leg_hi, entry), lvt)
    if p.sd_align and got:
        others = [v for v, k in lv if k not in SD_KINDS]
        tol = p.sd_align_tol_pts * p.es_pt
        got = [g for g in got if any(abs(g[0] - o) <= tol for o in others)]
    if p.sd_cluster_ticks and got:
        tol = p.sd_cluster_ticks * 0.25 * p.es_pt
        got.sort()
        clusters, cur = [], [got[0]]
        for g in got[1:]:
            if g[0] - cur[0][0] <= tol + 1e-9:
                cur.append(g)
            else:
                clusters.append(cur)
                cur = [g]
        clusters.append(cur)
        cl = [c for c in clusters if len({x[2] for x in c}) >= 2]
        if cl:
            lvt.append("sd_cluster")
            return [(float(np.mean([x[0] for x in c])), "sd_cluster") for c in cl]
    out = []
    for v, k, nm, kd in got:
        if kd:
            kind = kd                       # caption-gap targets_partials #2/4: proj / proj_htf / proj_cluster / proj_runner / proj_lh
        elif p.sd_roles:
            kind = "sd_half" if abs(k - 0.5) < 1e-9 else "sd_mm" if abs(k - 1.0) < 1e-9 else "sd_ext" if k >= 2 else "sd"
        else:
            kind = "sd"                     # review: always an SD kind so sd_close_hit sees it (exits treat it like "array")
        out.append((float(v), kind))
    if out:
        lvt.append("sd_" + (p.sd_anchor if p.sd_anchor not in ("leg", "sweep_leg") else "leg"))
    return out


def tgif_info(ctx, sd, i: int, p, entry: float):
    """M14.2: the Friday retrace levels (side space) of the weekly range, or None when today is not a
    TGIF day in this direction. Weekly range = week low (including Sunday 18:00) .. week high from the
    full Monday-Thursday sessions (ctx.eth) or the regular-session frames, plus today's bars so far.
    Returns dict(levels=[...], retrace=how far price already retraced (0..1), stand_down=bool)."""
    if not p.tgif_zone or ctx.day.weekday() != 4:
        return None
    tags = getattr(ctx, "day_tags", "")
    want = "tgif_short" if sd.sign < 0 else "tgif_long"
    if want not in tags.split("|"):
        return None
    wk = ctx.day.isocalendar()[:2]
    hi_l, lo_l = [], []
    eth = getattr(ctx, "eth", None) or {}
    hist = list(getattr(ctx, "hist", None) or [])
    for fr in hist:
        d = fr.index[0].date()
        if d.isocalendar()[:2] != wk or d >= ctx.day:
            continue
        e = eth.get(d)
        hi_l.append(e[1] if e else float(fr.high.max()))
        lo_l.append(e[2] if e else float(fr.low.min()))
    if not hi_l:
        return None
    a = ctx.start
    hi_l.append(float(ctx.h[a:i + 1].max()))
    lo_l.append(float(ctx.l[a:i + 1].min()))
    whi, wlo = max(hi_l), min(lo_l)
    rng = whi - wlo
    if rng <= 0:
        return None
    # real prices: a short retraces down from the week high, a long up from the week low
    real = [whi - f * rng if sd.sign < 0 else wlo + f * rng for f in p.tgif_zone_levels if f <= p.tgif_cap + 1e-9]
    px = sd.x(entry)
    retr = (whi - px) / rng if sd.sign < 0 else (px - wlo) / rng
    ext_now = float(ctx.l[a:i + 1].min()) if sd.sign < 0 else float(ctx.h[a:i + 1].max())
    retr_max = (whi - ext_now) / rng if sd.sign < 0 else (ext_now - wlo) / rng
    return dict(levels=sorted(sd.x(v) for v in real), retrace=float(retr),
                stand_down=bool(max(retr, retr_max) >= p.tgif_stand_down))


def matrix_breakers(sd, p):
    """A22: the opposing (bearish, side space) breakers of the day frame."""
    return sd._lazy(("brk_opp", p.pivot_n), lambda: [z for z in L.breakers(sd.o, sd.h, sd.l, sd.c, max(p.pivot_n, 1))
                                                     if z.kind == "bear"])


def rb_zones(sd, p):
    """A17 (fixed rejection_blocks): the opposing (bearish, side space) rejection blocks."""
    return sd._lazy(("rb_bear", p.pivot_n, p.rb_min_wick_frac, p.rb_level),
                    lambda: [z for z in L.rejection_blocks(sd.o, sd.h, sd.l, sd.c, p.pivot_n, p.rb_min_wick_frac, p.rb_level)
                             if z.kind == "bear"])


def extra_sources(ctx, sd, i: int, p, sw: dict, entry: float, risk: float, leg_hi: float, above: float,
                  lv: list, lvt: list, rr) -> list:
    """New array / pool targets as raw (side-space level, kind): A6 / Ep03.5 measuring gap, Ep08.9 mm_targets,
    L13 proj_breaker / proj_org_k / proj_ext, the SD engine, A10 void_targets / leg_start_target,
    L11 / A17 rejection-block body edges, A22 matrix blocks, Ep01.21 inter_swing_target, L16 adr_target.
    Only levels beyond `above` are returned."""
    from . import strategy as S
    out = []
    ext = float(sw["ext"])
    h = sd.h
    after = lambda z: h[z.i + 1:i + 1].max(initial=-np.inf)
    if p.measuring_gap or p.measuring_target:
        g = measuring_gap(sd, sw, i, leg_hi, p)
        if g is not None and p.measuring_qualify:             # caption-gap A6-measuring-gap-confirmation (003 ~31:51; 062 ~44:24): the pullback left the far edge untouched and a new extreme printed
            st_, _ = L.bk_state(sd.h, sd.l, g, i, "any_open", c=sd.c)       # bodies filling the gap drop the label, a wick poke does not
            if st_ != "qualified":
                g = None
                from . import tp1 as _T1
                _T1.hit("measuring_unqualified")
        if g is not None:
            lvt.append("measuring_gap")
            if p.measuring_target:
                v = measuring_level(g, ext, p.measuring_anchor)
                pools = _pools_raw(lv)
                if (not p.measuring_pool_pts) or any(abs(v - q) <= p.measuring_pool_pts * p.es_pt for q in pools):
                    if not p.measuring_need_pool or any(q <= v + p.measuring_pool_pts * p.es_pt for q in pools):     # the -1 SD lies beyond an old liquidity pool (062 ~44:24)
                        out.append((v, "array"))
                        lvt.append("measuring_target")
    if p.mm_targets and p.mm_anchor in ("leg", "ref") and (rr is not None or p.mm_anchor == "leg"):      # ("reanchor" / "impulse": caption-gap tp3.mm_levels)
        base = float(rr[1]) if p.mm_anchor == "ref" else float(leg_hi)
        if base > ext:
            out.append((base + (base - ext), "proj" if p.proj_kind else "array"))             # caption-gap X2-projection-target-1tick-before: a measured move is a projection
            lvt.append("mm_target")
    if p.proj_breaker and rr is not None and float(rr[1]) > ext and sw.get("broke") is not None:
        fun, S.FUNNEL = S.FUNNEL, None                          # review: a helper call must not bump the x_breaker_* counters
        try:
            bz = S._breaker(ctx, sd, sw, rr[0], rr[2], i, p)
        finally:
            S.FUNNEL = fun
        if bz is not None:
            B = float(rr[1])
            if p.proj_breaker_k == (1.0,):
                out.append((B + (B - ext), "array"))             # L13 (070 ~37:31): B + 1 x (B - A)
            else:                                                # caption-gap L13-breaker-range-sd-weekly (074 ~00:30:15): k = 2 (the weekly range extreme) needs the weekly and day bias
                from . import tp2 as _T2
                out += _T2.breaker_ks(ctx, sd, i, p, getattr(ctx, "_tp2_session", "AM"), B, ext, sw.get("level"))
            lvt.append("proj_breaker")
    if p.proj_org_reprice and getattr(ctx, "org", None):       # caption-gap L13-org-sd-projection (055 ~00:19:31; 056 ~00:18:20): after the reprice, in the bias direction
        from . import tp2 as _T2
        out += _T2.org_projection(ctx, sd, i, p, getattr(ctx, "_tp2_session", "AM"), above)
    elif p.proj_org_k and getattr(ctx, "org", None):
        pre_open = ctx.t[i] < 570
        orgs = ctx.org[:-1] if (pre_open and ctx.org_today) else ctx.org
        if orgs:
            a, b = orgs[-1]
            far = max(sd.x(a), sd.x(b))
            size = abs(b - a)
            if size > 0:
                out += [(far + k * size, "array") for k in p.proj_org_k]
    if p.proj_ext and leg_hi > ext:
        rng = leg_hi - ext
        zones = []
        if getattr(ctx, "conf", None) is not None:
            for r in ctx.conf.opposing_ext(now_ts(ctx, i), sd.x(above), sd.sign, ("15m", "30m", "1h", "4h", "D"), (0, 1)):
                zones.append(_zone_edges(sd, r))
        zones += [(z.bottom, z.top) for z in sd.opposing() if z.i <= i and z.bottom > above and after(z) < z.bottom]
        tol = p.sd_align_tol_pts * p.es_pt
        for e in p.proj_ext:
            v = ext + e * rng
            if any(a - tol <= v <= b + tol for a, b in zones):
                out.append((v, "array"))
    if sd_active(p):
        out += sd_levels(ctx, sd, i, p, sw, leg_hi, rr, lv, entry, risk, lvt)
    if p.void_targets:
        for z in sd._lazy("voids_bear", lambda: [z for z in L.voids(sd.h, sd.l) if z.kind == "bear"
                                                 and z.top - z.bottom >= sd.min_gap]):
            if z.i <= i and z.bottom > above and after(z) < z.bottom:
                out += [(float(z.bottom), "array"), (float(z.mid), "array")]
    if p.leg_start_target:
        ls = leg_start(sd, sw["ext_i"], 0)
        if ls is not None and ls[1] > above:
            out.append((ls[1], "array"))
            lvt.append("leg_start")
    if p.rb_targets == "ladder":
        for z in rb_zones(sd, p):
            if z.i <= i and z.bottom > above and after(z) < z.bottom:
                out.append((float(z.bottom), "rb"))                  # "replace" is applied by refine()
                if p.rb_ce_level:                                    # caption-gap A17: level2 (the wick CE) and W (the extreme wick)
                    out += [(float(z.mid), "rb"), (float(z.top), "rb")]
    if p.matrix_targets:
        if "breaker" in p.matrix_targets:
            for z in matrix_breakers(sd, p):
                if z.i <= i and z.bottom > above and after(z) < z.bottom:
                    out += [(float(z.bottom), "array"), (float(z.mt if z.mt == z.mt else z.mid), "array")]
        if "mitigation" in p.matrix_targets:
            for z in sd.opp_mits():
                if z.i <= i and z.bottom > above and (not (p.mit_body_respect or p.mit_mt_invalid)
                                                  or L.mitigation_alive(sd.c, z, i, p.mit_mt_invalid)):
                    out += [(float(z.bottom), "array"), (float(z.mid), "array")]
        if "rejection" in p.matrix_targets:
            for z in rb_zones(sd, p):
                if z.i <= i and z.bottom > above and after(z) < z.bottom:
                    out.append((float(z.bottom), "rb"))
    if p.inter_swing_target:
        qs = [q for q in _ph(sd) if q.known <= i and q.i >= ctx.start - 1 and q.price > above
              and h[q.i + 1:i + 1].max(initial=-np.inf) < q.price]
        if qs:
            out.append((float(min(q.price for q in qs)), "swing"))       # the nearest untaken short-term high
    if p.adr_target:
        adr = S.adr5(getattr(ctx, "hist", [])[-5:])
        if adr:
            from . import tp3 as _T3
            out.append((_T3.adr_low(ctx, sd, i, p) + p.adr_frac * adr, "adr" if p.adr_before_frac > 0 else "array"))    # caption-gap L16 adr_anchor (day / London low); X2-exit-buffer-before-day-extreme: kind 'adr' exits adr_before_frac x ADR5 early
            lvt.append("adr_target")
    return [(float(v), k) for v, k in out if v > above]


def refine(ctx, sd, i: int, p, lv: list, sw: dict, entry: float, above: float, lvt: list) -> list:
    """Filters on the raw (level, kind) list before the exit prices are taken:
      pool_body_edge   2023 reads the BODY edge of a swing high, not its wick (A17: 015 ~2:15; 059 ~10:03)
      rb_targets       "replace": a pool that is a rejection block's wick tip becomes its body edge (L11)
      target_hygiene   "arrays": non-pool levels price traded through earlier today before the sweep are retired
                       (gap / ORG levels are never retired, 039); "wick": traded prior-day wick CEs are retired
      org_reprice      M8 (069): after a Judas away from the ORG, T1 = the ORG near edge, nearer rungs dropped"""
    ext_i = sw["ext_i"]
    if p.pool_body_edge or p.rb_targets == "replace":
        new = []
        for v, k in lv:
            if k in POOL_KINDS:
                e = body_edge(ctx, sd, i, v, p, need_wick=not p.pool_body_edge)
                if e is not None and e < v - 1e-9:
                    new.append((e, "rb"))
                    continue
            new.append((v, k))
        lv = new
    if "arrays" in p.target_hygiene and ext_i is not None and ext_i > ctx.start:
        seen = float(sd.h[ctx.start:ext_i].max())
        keepers = {round(v, 6) for v in _gap_levels(ctx, sd, p)}
        lv = [(v, k) for v, k in lv if k in POOL_KINDS or v > seen or round(v, 6) in keepers]
    if "wick" in p.target_hygiene:
        seen = float(sd.h[ctx.start:i + 1].max())
        wk = {round(sd.x(w), 6) for d in getattr(ctx, "wicks", [ctx.wick]) + getattr(ctx, "wick_wk", [])
              for w in (d["upper"], d["lower"])}
        lv = [(v, k) for v, k in lv if not (round(v, 6) in wk and v <= seen)]
    if p.org_reprice and ctx.t[i] >= 570 and getattr(ctx, "org", None) and ctx.org_today:
        a, b = ctx.org[-1]
        near = min(sd.x(a), sd.x(b))
        if near > entry and float(sw["ext"]) < near and _judas_org(ctx, sd, sw):
            lv = [(v, k) for v, k in lv if v >= near - p.es_pt] + [(near, "array")]
            lvt.append("org_reprice")
    return sorted(set(lv))


def _judas_org(ctx, sd, sw) -> bool:
    """M8: the 09:30 Judas swing ran AWAY from the ORG - the sweep extreme printed after the open, beyond
    the 09:30 open on the far side from the ORG."""
    o = ctx.opens.get("0930")
    if o is None:
        return False
    return bool(ctx.t[sw["ext_i"]] >= 570 and float(sw["ext"]) < sd.x(o) + 1e-9)


def _gap_levels(ctx, sd, p) -> list:
    out = []
    if getattr(ctx, "gaps", None) is not None:
        for kind, hi, lo, ce in ctx.gaps:
            out += [sd.x(hi), sd.x(ce), sd.x(lo)]
    for a, b in getattr(ctx, "org", []) or []:
        out += [sd.x(a + q * (b - a)) for q in (0.0, 0.25, 0.5, 0.75, 1.0)]
    for a, b in getattr(ctx, "nwog", []) or []:
        out += [sd.x(a), sd.x(b), sd.x((a + b) / 2)]
    return out


def breaker_cap(ctx, sd, i: int, p, entry: float, risk: float, flag):
    """A22 breaker_first (cc05_014 ~21:04): an unbroken opposing breaker in the path ends the run in
    front of it. Returns the cap (exit price, side space), None when there is none, or False when the
    room to it is too short (skip)."""
    if not p.breaker_first:
        return None
    if p.breaker_overtake:                      # caption-gap A22-breaker-precedence (cc05_014 ~28:18): only a BODY close through the breaker overtakes it (a wick into it keeps the stop)
        zs = [z for z in matrix_breakers(sd, p)
              if z.i <= i and z.bottom > entry and sd.c[z.i + 1:i + 1].max(initial=-np.inf) <= z.top]
        if len(zs) != len([z for z in matrix_breakers(sd, p) if z.i <= i and z.bottom > entry and sd.h[z.i + 1:i + 1].max(initial=-np.inf) < z.bottom]):
            from . import tp1 as _T1
            _T1.hit("breaker_overtake")                  # a wick into the breaker no longer re-enables the arrays beyond it
    else:
        zs = [z for z in matrix_breakers(sd, p)
              if z.i <= i and z.bottom > entry and sd.h[z.i + 1:i + 1].max(initial=-np.inf) < z.bottom]
    if not zs:
        return None
    cx = min(z.bottom for z in zs) - p.exit_before_pts * p.es_pt
    if cx - entry < p.min_rr * risk:
        flag("x_breaker_first")
        return False
    return cx


# --- partial rungs: wicks, SD, inner levels, the plan -----------------------------------------

TF_MIN = {"15m": 15, "30m": 30, "1h": 60, "4h": 240}


def tf_wicks(ctx, sd, i: int, p, tfs, above_lo: float, force_long: bool = False) -> list:
    """X3c / A23: the upper-wick CEs (side space; a short's lower wicks) of COMPLETED candles - daily
    candles of the last max(wick_days, 3) regular sessions ("D") and the 15m / 30m / 1h / 4h candles
    of the day frame up to bar i - as (CE, wick length, source) for candles whose CE lies above
    `above_lo` and which price has not traded through since. CE = body edge + half the wick (A23);
    a wick counts from wick_partial_min_pts (X3c [our interpretation])."""
    out = []
    mn = p.wick_partial_min_pts * p.es_pt
    for name in tfs:
        if name == "D":
            for fr in list(getattr(ctx, "hist", None) or [])[-max(p.wick_days, 3):]:
                o, h, l, c = (float(fr.open.iloc[0]), float(fr.high.max()), float(fr.low.min()), float(fr.close.iloc[-1]))
                if sd.sign < 0:
                    o, h, l, c = -o, -l, -h, -c
                top = max(o, c)
                ce = (top + h) / 2
                t_end = fr.index[-1].value
                ex = extreme_since(ctx, i, float(t_end) + 1.0, sd.sign > 0)
                if h - top >= mn and ce > above_lo and (ex is None or sd.x(ex) < ce):
                    out.append((float(ce), float(h - top), "D"))
            continue
        m = TF_MIN[name]
        if m <= ctx.tf:
            continue
        idx = ctx.idx[:i + 1]
        g = pd.Series(np.arange(i + 1), index=idx).groupby(idx.floor(f"{m}min"))
        first, last, st = g.min().values, g.max().values, g.min().index
        done = (idx[last] - st) >= pd.Timedelta(minutes=m - ctx.tf)
        long_only = p.wick_long_only or force_long
        wk_ = []                                            # caption-gap L10-intraday-wick-ce: the wicks of the completed buckets (long = >= the body and >= the 20-candle median)
        if long_only:
            for a, z, ok in zip(first, last, done):
                wk_.append(float(sd.h[a:z + 1].max() - max(sd.o[a], sd.c[z])) if ok else 0.0)
        for n_, (a, z, ok) in enumerate(zip(first, last, done)):
            if not ok:
                continue
            o_, c_ = sd.o[a], sd.c[z]
            hh = sd.h[a:z + 1].max()
            top = max(o_, c_)
            if long_only and not (wk_[n_] >= abs(c_ - o_) and wk_[n_] >= float(np.median([w_ for w_ in wk_[max(0, n_ - 19):n_ + 1]]))):
                continue
            ce = (top + hh) / 2
            if hh - top >= mn and ce > above_lo and sd.h[z + 1:i + 1].max(initial=-np.inf) < ce:
                out.append((float(ce), float(hh - top), name))
    return out


def partial_extras(ctx, sd, i: int, p, sw: dict, entry: float, leg_hi: float, last_v: float, rr, lvt: list) -> list:
    """The extra partial rungs as (exit price, kind, protected) - X3 / X3c / X3d:
      sd_half_partial  the -0.5 SD level of the sd_anchor range is ALWAYS a first partial, exempt from min_rr
      wick_partials    a partial a little before (exit_before_pts) the CE of a wick inside the path
                       (entry .. last rung); with two or more only the longest wick (065A ~2:37:30)"""
    from . import strategy as S
    out = []
    if p.sd_half_partial:
        rs = sd_ranges(ctx, sd, i, p, sw, leg_hi, rr)
        vs = [hi + 0.5 * (hi - lo) for _, lo, hi in rs]
        vs = [v for v in vs if v > entry]
        if vs:
            out.append((min(vs) - p.exit_before_pts * p.es_pt, "sd_half", True))
    if p.wick_partials:
        ws = [w for w in tf_wicks(ctx, sd, i, p, p.wick_partial_tfs, entry) if w[0] < last_v + 1e-9]
        if p.wick_partial_longest and len(ws) > 1:
            ws = [max(ws, key=lambda w: w[1])]
        for ce, ln, src in ws:
            out.append((ce - p.exit_before_pts * p.es_pt, "wick_ce", p.wick_partial_protect))
    return out


def inner_extras(p, entry: float, risk: float, lv: list, kinds: list) -> list:
    """X1 keep_inner_levels: the levels min_rr drops (nearer than min_rr x risk, at least inner_min_pts
    from the entry) stay as small early partials."""
    if not p.keep_inner_levels:
        return []
    lo = p.inner_min_pts * p.es_pt
    return [(v, "inner", False) for v, k in zip(lv, kinds) if lo <= v - entry < p.min_rr * risk - 1e-9]


def plan_active(p, keep: list, extras: list, tg) -> bool:
    return bool(extras or tg is not None or any(k in ("bump", "speed") for _, k in keep) or p.run_down or p.ladder_all_pools
                or p.ladder_max_levels or p.halfway_partial or p.resistance_mode != "off" or p.capture_frac
                or p.target_order or p.final_htf or p.pool_runner_pts or p.mgmt == "unit" or p.sd_roles
                or any(k == "wick_ce" for _, k in keep))


def _R(v, k, role="main", prot=False):
    return dict(v=float(v), k=k, role=role, prot=bool(prot))


def plan(ctx, sd, i: int, p, entry: float, risk: float, above: float, keep: list, final_T: bool,
         extras: list, tg, eq_raw: list, lvt: list):
    """Build the rung plan from `keep` (sorted exit prices with kinds). Returns "skip" (a TGIF day with
    no room inside the zone), None (inert) or dict(rungs, final_T, fracs_fixed, run_local).
    Order: TGIF zone, final_htf, target_order chain, resistance_mode, capture_frac, pool runner, then
    the extra rungs (protected ones survive min_rr; low_full yields to any extra - a speed bump, wick or SD
    partial - so the #7 bump is never silently removed; tgif_exits fixed fractions DO drop extras [documented]; none beyond the last main rung or within 1 pt of a
    main) and the halfway rung between the first two mains."""
    from . import strategy as S
    if not plan_active(p, keep, extras, tg):
        return None
    mains = [_R(v, k) for v, k in keep]
    bump_ex = []
    if len(mains) > 1:                                   # review: a speed bump is a small protected partial, not a main
        bump_ex = [(m["v"], m["k"], True) for m in mains[:-1] if m["k"] in ("bump", "speed")]      # (caption-gap L10-L11-A17: the old-high body edge "speed" is a protected small partial like a bump)
        mains = [m for j, m in enumerate(mains) if not (j < len(mains) - 1 and m["k"] in ("bump", "speed"))]
    extras = list(extras) + bump_ex
    fixed = None
    run_local = False
    if tg is not None:                                   # M14.2 / M14.4
        zl = [v for v in tg["levels"] if v - entry >= p.min_rr * risk]
        if not zl:
            return "skip"
        mains = [_R(v, "exact") for v in zl]
        final_T = False
        lvt.append("tgif_zone")
        if p.tgif_exits:
            mains = mains[:len(p.tgif_exit_fracs)]
            fixed = tuple(p.tgif_exit_fracs[:len(mains)])
            lvt.append("tgif_exits")
    if p.final_htf and not final_T and getattr(ctx, "conf", None) is not None and mains:
        rows = ctx.conf.opposing_ext(now_ts(ctx, i), sd.x(above), sd.sign, ("4h", "D", "W"), (0, 1, 2, 3))
        best = None
        for r in rows:
            near, _ = _zone_edges(sd, r)
            v = near - p.exit_before_pts * p.es_pt
            if v - entry >= p.min_rr * risk and (best is None or v < best):
                best = v
        if best is not None:
            mains = [m for m in mains if m["v"] < best - p.es_pt] + [_R(best, "array")]
            lvt.append("final_htf")
    if p.target_order and mains:
        picks, prev = [], entry + p.min_rr * risk - 1e-9
        for typ in p.target_order:
            cand = [m for m in mains if m["v"] > prev + 1e-9 and _type_of(m, typ, eq_raw, p)]
            if cand:
                picks.append(cand[0])
                prev = cand[0]["v"]
        if picks:
            if final_T and mains[-1] not in picks and mains[-1]["v"] > picks[-1]["v"]:
                picks.append(mains[-1])                  # the locked draw stays the last rung (review)
            mains = picks
            lvt.append("target_order")
    if p.resistance_mode != "off" and mains:
        n = resistance_count(ctx, sd, i, p, entry, mains[-1]["v"])
        if p.resistance_mode in ("low_full", "both") and n <= p.res_low_max and not extras:
            mains = [mains[-1]]                          # a low-resistance run: one full pull at the draw
            fixed = (1.0,)
            lvt.append("res_low")
        elif p.resistance_mode in ("high_run", "both") and n >= p.res_high_min:
            run_local = True                             # a high-resistance run: partials all the way
            lvt.append("res_high")
    if p.capture_frac and mains:
        last = mains[-1]
        nv = entry + p.capture_frac * (last["v"] - entry)
        if nv - entry >= p.min_rr * risk and nv < last["v"] - 1e-9:
            last = dict(last, v=nv)
            mains = [m for m in mains[:-1] if m["v"] < nv - p.es_pt] + [last]
            lvt.append("capture")
    if p.pool_runner_pts and mains and mains[-1]["k"] in POOL_KINDS:
        mains.append(_R(mains[-1]["v"] + p.pool_runner_pts * p.es_pt, "runner"))
        lvt.append("pool_runner")
    ex = []
    if mains:
        last_v = mains[-1]["v"]
        lo = p.inner_min_pts * p.es_pt
        for v, k, prot in extras:
            if v - entry < lo or v >= last_v - 1e-9:
                continue
            if any(abs(v - m["v"]) <= p.es_pt for m in mains) or any(abs(v - e["v"]) <= p.es_pt for e in ex):
                continue
            ex.append(_R(v, k, "extra", prot))
            tag = {"sd_half": "sd_half", "wick_ce": "wick_partial", "inner": "inner_level"}.get(k)
            if tag:
                lvt.append(tag)
        if p.halfway_partial and len(mains) >= 2 and mains[1]["v"] - mains[0]["v"] >= p.halfway_min_pts * p.es_pt:
            mid = (mains[0]["v"] + mains[1]["v"]) / 2
            if not any(abs(mid - e["v"]) <= p.es_pt for e in ex):
                ex.append(_R(mid, "halfway", "extra", False))
                lvt.append("halfway")
    rungs = sorted(mains + ex, key=lambda r: r["v"])
    return dict(rungs=rungs, final_T=final_T, fracs_fixed=fixed, run_local=run_local)


def _type_of(m: dict, typ: str, eq_raw: list, p) -> bool:
    """Ep04.12 target types: "eq" = a relative-equal-highs pool, "daily" = any other pool, "vi" = a
    daily volume-imbalance rung (kind "vi"), "pool" / "array" by kind."""
    k = m["k"]
    if typ == "eq":
        raw = _raw(m["v"], k, p)
        return k in POOL_KINDS and (k == "pool_eq" or any(abs(raw - e) <= p.es_pt for e in eq_raw))
    if typ == "daily":
        return k in POOL_KINDS and not _type_of(m, "eq", eq_raw, p)
    if typ == "vi":
        return k == "vi"
    return k in POOL_KINDS if typ == "pool" else k not in POOL_KINDS


def _ext_fracs(base: tuple, K: int, run: bool) -> list:
    """Main-rung shares. Same as the old engine: with K <= len(base) the first K-1 rungs take base[k] and the
    last takes the remainder (a 2-rung ladder on 50/25/25 is 50/50); running down / more rungs than fractions:
    the first keeps base[0], the rest is even."""
    if K <= 1:
        return [1.0]
    if run or K > len(base):
        return [float(base[0])] + [(1.0 - float(base[0])) / (K - 1)] * (K - 1)
    head = [float(f) for f in base[:K - 1]]
    return head + [max(1.0 - sum(head), 0.0)]


def bump_fracs(levels: list, bumps: list, base: tuple, p) -> list:
    """Shares for a ladder that carries speed-bump rungs (Silver Bullet / Ma Deuce, which keep their own ladder
    code): each bump rung (a level within one point of a bump, never the last) takes htf_bump_frac (all bumps
    together under partial_extra_cap), the other rungs share the rest like the old ladder (_ext_fracs)."""
    isb = [k < len(levels) - 1 and any(abs(v - b) <= p.es_pt for b in bumps) for k, v in enumerate(levels)]
    nb = sum(isb)
    if not nb:
        return [float(f) for f in base]
    per = min(p.htf_bump_frac, p.partial_extra_cap / nb)
    main = iter(_ext_fracs(base, len(levels) - nb, False))
    rest = 1.0 - per * nb
    return [per if b else next(main) * rest for b in isb]


def fill_plan(o: dict, base: tuple, p):
    """At the fill (when the day's split `base` is known): choose the main rungs, turn a protected main
    that no longer fits into an extra, give each extra its share and the mains the rest. Returns
    (levels, kinds, fracs) of equal length, ascending by price."""
    rungs = o["rung_plan"]
    mains = [r for r in rungs if r["role"] == "main"]
    extras = [dict(r) for r in rungs if r["role"] == "extra"]
    fixed = o.get("fracs_fixed")
    if fixed:
        return [m["v"] for m in mains], [m["k"] for m in mains], list(fixed)[:len(mains)]
    run = bool(p.run_down or o.get("run_local"))
    cap = p.ladder_max_levels or (6 if (run or p.ladder_all_pools) else len(base))
    elig = mains
    if p.ladder_all_pools:
        elig = [m for m in mains if m["k"] in POOL_KINDS] or mains
        if mains[-1] not in elig:
            elig = elig + [mains[-1]]
    K = max(min(len(elig), cap), 1)
    chosen = elig[:K]
    if o.get("final_T") and K < len(elig):
        chosen = elig[:K - 1] + [elig[-1]]
    for m in elig:
        if m not in chosen and m["prot"] and m["v"] < chosen[-1]["v"]:
            extras.append(dict(m, role="extra"))
    extras = [e for e in extras if e["v"] < chosen[-1]["v"] - 1e-9
              and not any(abs(e["v"] - m["v"]) <= (0.25 if e["k"] == "halfway" else 1.0) * p.es_pt for m in chosen)]
    extras.sort(key=lambda r: r["v"])
    if p.mgmt == "unit":
        fr = [1.0 / K] * K
    elif p.target_order and o.get("bulk"):
        fr = list(p.ladder_fracs_bulk[:K]) or [1.0]
    else:
        fr = _ext_fracs(base, K, run)
    if p.sd_roles:
        kinds = [m["k"] for m in chosen]
        if "sd_mm" in kinds and K > 1:                  # -1 SD = the measured move: the bulk comes off there
            j = kinds.index("sd_mm")
            big = fr.index(max(fr))
            fr[j], fr[big] = fr[big], fr[j]
        if "sd_ext" in kinds and K > 1:                 # -2 SD and beyond: very extended, the smallest piece
            j = kinds.index("sd_ext")
            small = fr.index(min(fr))
            fr[j], fr[small] = fr[small], fr[j]
    want = [p.htf_bump_frac if e["k"] == "bump" else p.speed_frac if e["k"] == "speed" else p.min_obj_frac if e["k"] == "min_obj" else p.partial_extra_frac for e in extras]
    scale = min(1.0, p.partial_extra_cap / sum(want)) if want else 1.0
    shares = [w * scale for w in want]
    tot = sum(shares)
    s = sum(fr) or 1.0
    items = [(m["v"], m["k"], f * (1.0 - tot) / s) for m, f in zip(chosen, fr)] + [(e["v"], e["k"], sh) for e, sh in zip(extras, shares)]
    items.sort(key=lambda x: x[0])
    return [x[0] for x in items], [x[1] for x in items], [x[2] for x in items]


# --- management hooks (run_day ladder loop) -----------------------------------------------

def rung_hit(pos: dict, k: int, level: float, h: float, c: float, t: int, tf: int, p, xt: float):
    """Is rung k hit on this bar, and at what price. Default: the bar's high reaches the level (plus
    exit_fill_through). Ep06.4 sd_close_hit: an SD rung is hit by a CLOSE at or beyond it (Ep 05 ~6:01-6:49:
    the 1.5 SD matched closing prices, not wicks), inside sd_close_window when one is set; the fill is the close."""
    if p.sd_close_hit:
        kinds = pos.get("level_kinds") or []
        if k < len(kinds) and kinds[k] in SD_KINDS:
            w = p.sd_close_window
            if not w or (w[0] < t + tf <= w[1]):
                return (c >= level, c)
    return (h >= level + xt, level)


def breakaway_gap(sd, ext_i: int, i: int, p=None):
    """A6: the breakaway gap = the first FVG after the sweep extreme (the structure shift's gap); it
    stays a breakaway gap while it is at least partly open and price retraced at most to its half
    (001 ~40:03; 062 ~37:02); fully filled / past the half = not breakaway. None when there is none.
    Caption-gap A6-breakaway-depth-qualification (`p` = Params; 062 ~37:12 / ~39:01; 065; cc04_009 ~13:37): `bk_depth` "any_open" lets the retrace
    go anywhere short of the far edge; `bk_bpr_ce` keeps the CE limit when a BPR sits beyond; `bk_state` returns the gap only once QUALIFIED
    (retraced, then price traded beyond the highest high since it formed with the far edge untouched - levels.bk_state)."""
    g = next((g for g in sd.gaps if g.i - 2 >= ext_i and g.i <= i), None)
    if g is None:
        return None
    if p is None or (p.bk_depth == "ce" and not p.bk_state and not p.bk_bpr_ce):
        if sd.l[g.i + 1:i + 1].min(initial=np.inf) <= g.mid - 1e-9:
            return None
        return g
    st, _ = L.bk_state(sd.h, sd.l, g, i, p.bk_depth, sd.bprs() if p.bk_bpr_ce else (), p.bk_bpr_ce)
    if p.bk_state:
        return g if st == "qualified" else None
    return g if st != "dead" else None


def manage(ctx, sd, pos: dict, tr, i: int, ts, p, pctx, psides, ppos) -> None:
    """Mid-trade partials / stops run on each closed bar (after the bar's stop and ladder tests; changes
    take effect from the next bar). smt_bank, smt_bank_against_frac, adr_early, wick_revisit and the SD close hit
    are market-on-close exits filled at the deciding bar's close (like htf_heavy / ce_close / lvx exits) - slightly
    optimistic against "armed on bar i, fills from bar i+1", but they use no data past that close [documented]:
      smt_bank        X3 / X3g (046 ~1:02:40; 037 ~32:56): our bar prints a new high since the fill, the sister
                      index does not -> bank smt_bank_frac of what is left (once), when >= smt_bank_min_r in profit
      adr_early       L16 (cc08_001 ~1:53): the day's range reached ADR5 before 10:00 -> take adr_early_frac, keep a runner
      wick_read       A23 (025 ~25:37; 100 ~38:13): the bar after a wick-CE rung was hit closes back through the CE ->
                      the rest is out (revisit); a close beyond it = continuation
      trail_breakaway A6 / X5: stop under the breakaway gap once a close is above it"""
    from . import strategy as S
    h, c, t, tf = sd.h[i], sd.c[i], ctx.t[i], ctx.tf
    basis = pos["basis"] / pos["n"]
    if p.smt_bank and not pos.get("smt_banked") and pos["left"] and pctx is not None and i > pos["fill_i"]:
        risk_s = abs(tr.entry - tr.stop)
        prev_hi = sd.h[pos["fill_i"]:i].max()
        if risk_s > 0 and h > prev_hi + 1e-9 and (c - basis) / risk_s >= p.smt_bank_min_r:
            ps = psides[sd.sign]
            j = ppos.index.searchsorted(ctx.idx[i], side="right") - 1
            jf = ppos.index.searchsorted(ctx.idx[pos["fill_i"]], side="right") - 1
            if jf >= pctx.start and j > jf and ps.h[j] <= ps.h[jf:j].max() + 1e-9:
                q = min(pos["left"], max(p.lot, S._lots(pos["left"] * p.smt_bank_frac, p.lot)))
                tr.exits.append((ts, sd.x(c), q, "smt_bank"))
                pos["left"] -= q
                pos["smt_banked"] = True
    if p.smt_bank_against_frac and not pos.get("smt_banked2") and pos["left"] and pctx is not None and i > pos["fill_i"]:
        risk_s = abs(tr.entry - tr.stop)
        if risk_s > 0 and (c - basis) / risk_s >= p.smt_bank_min_r:          # X3g: the sister breaks against the trade
            ps = psides[sd.sign]
            j = ppos.index.searchsorted(ctx.idx[i], side="right") - 1
            jf = ppos.index.searchsorted(ctx.idx[pos["fill_i"]], side="right") - 1
            if (jf >= pctx.start and j > jf and ps.l[j] < ps.l[jf:j].min() - 1e-9
                    and sd.l[i] > sd.l[pos["fill_i"]:i].min() - 1e-9):
                q = min(pos["left"], max(p.lot, S._lots(pos["left"] * p.smt_bank_against_frac, p.lot)))
                tr.exits.append((ts, sd.x(c), q, "smt_bank2"))       # market-on-close exit, like smt_bank
                pos["left"] -= q
                pos["smt_banked2"] = True
    if p.adr_early and not pos.get("adr_done") and pos["left"] and t + tf <= 600:
        adr = S.adr5(getattr(ctx, "hist", [])[-5:])
        if adr:
            rng = ctx.h[ctx.start:i + 1].max() - ctx.l[ctx.start:i + 1].min()
            if rng >= adr:
                q = min(pos["left"], max(p.lot, S._lots(pos["left"] * p.adr_early_frac, p.lot)))
                if q < pos["left"]:
                    tr.exits.append((ts, sd.x(c), q, "adr_early"))
                    pos["left"] -= q
                pos["adr_done"] = True
    if p.wick_read == "exit" and pos["left"]:
        chk = pos.get("wick_chk")
        if chk is not None and chk[0] < i:
            if c < chk[1]:
                tr.exits.append((ts, sd.x(c), pos["left"], "wick_revisit"))
                pos["left"] = 0
            pos["wick_chk"] = None
    if p.trail_breakaway and pos["left"]:
        g = breakaway_gap(sd, pos["ext_i"], i, p)
        if g is not None and c > g.top:
            from . import manage as _MG
            _MG.raise_stop(pos, g.bottom - p.trail_pad)            # X5c: never on a day trade


def capture_ratio(pos: dict, tr) -> float | None:
    """X3h capture metric: how much of the best-case run the exits took = (average exit - average entry) /
    (highest high reached - average entry), side space. None when price never traded above the entry."""
    sd = pos.get("side")
    if sd is None or "basis" not in pos:
        return None
    basis = pos["basis"] / pos["n"]
    best = pos.get("best")
    risk = abs(getattr(tr, "entry", 0.0) - getattr(tr, "stop", 0.0))
    if best is None or best - basis < max(risk, 1e-9) or not tr.exits:     # review: no meaningful run (< 1R) = no metric
        return None
    q = sum(e[2] for e in tr.exits)
    if q <= 0:
        return None
    avg = sum(sd.sign * e[1] * e[2] for e in tr.exits) / q
    return round(float(min(max((avg - basis) / (best - basis), 0.0), 1.0)), 4)     # clipped to [0, 1]


def _pool_weight(name: str) -> float:
    """L4: the size of a marked pool by its name (the minutes of the timeframe it belongs to): IPDA ranges and the
    previous month / week above the daily highs and lows, session ranges, the round handles last."""
    n = str(name)
    for pre, w in (("ipda60", 86400.0), ("ipda40", 57600.0), ("ipda20", 28800.0), ("pmonth", 43200.0), ("pw", 7200.0),
                   ("pdh", 1440.0), ("pdl", 1440.0), ("m3", 1440.0), ("today", 240.0), ("am_", 240.0), ("prev_am", 240.0),
                   ("lunch", 90.0), ("london", 180.0), ("overnight", 60.0), ("pmh", 60.0), ("pml", 60.0), ("round", 0.0)):
        if n.startswith(pre):
            return w
    return 1.0


def lock_rank(ctx, p, lst: list, px: float, up: bool) -> list:
    """L4 at the #9 lock (real prices; lst = (distance, level, kind, name, direction), nearest first):
      draw_below_eq  only levels beyond the equilibrium of the prior session's range (above it for the buy side,
                     below it for the sell side) when any remain (042 ~1:09:17)
      pool_rank      among the pools within pool_rank_reach x the nearest pool's distance the largest comes first
                     (the timeframe of its name, then the nearer) - "a 4h REL outranks a nearer 1h REL"."""
    if not lst:
        return lst
    if p.draw_below_eq and getattr(ctx, "hist", None):
        pdh, pdl = float(ctx.hist[-1].high.max()), float(ctx.hist[-1].low.min())
        eq = (pdh + pdl) / 2
        keep = [x for x in lst if (x[1] > eq if up else x[1] < eq)]
        lst = keep or lst
    if p.pool_rank:
        pools = [x for x in lst if x[2] in POOL_KINDS]
        if pools:
            reach = p.pool_rank_reach * pools[0][0]
            near = [x for x in pools if x[0] <= reach] or pools[:1]
            best = sorted(near, key=lambda x: (-_pool_weight(x[3]), x[0]))[0]
            lst = [best] + [x for x in lst if x is not best]
    return lst


def _exit_px_s(v: float, p) -> float:
    """The exit price of an 'array' level (caption-gap L4-target-below-eq-leg eq_beyond_imb)."""
    from . import strategy as S
    return S._exit_px(v, "array", p)
