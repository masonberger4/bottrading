"""Caption-gap pass (digests/rulebook_gaps/*.md), package targets_partials, chunk 4 of 4: the engine glue of its 33 specs -
management_partials_trailing_exits.md 44, 45, 46, 47, 48, 51, 56, 59, 60, 61, 62, 63, 65, 66, 75, 79, 80, 81, 84, 106, 125; models_setups_entries.md 46, 71, 122, 126, 140, 147;
other.md 8; session_day_week_stops_frequency.md 22; stops_sizing_scaling_in.md 28, 70; times_sessions_macros.md 6, 19.

Same conventions as tp1.py .. tp3.py: side space (shorts run mirrored prices), a bar is used only after it closes (`i` = the last CLOSED bar, an order armed on it fills from bar i+1), an
object only from the bar that completes it. Every function sits behind a Params switch of the "caption-gap pass, targets_partials #4/4" block; interpretations the sources do not pin
down are marked [our interpretation]. `HITS` is sm2's counter dict (tests: proof that a switch's code path RAN).

Sections: 1 validation - 2 helpers (timeframe pools, gap / void registries, fractions) - 3 hook R (strategy._finish_order: raw rungs before the exit prices) - 4 ladder presets
(041 / 096, tp3.late) - 5 hook L (the ladder after tp3.late: gates, structural cuts, whole-ladder shapes, modifiers) - 6 weekly state (target stage, month gate; backtest.run) -
7 mid-trade management (runner stop, strength hold, TGIF 066, fulcrum trail) and the report fields."""
from __future__ import annotations

import warnings
from dataclasses import replace

import numpy as np
import pandas as pd

from . import levels as L
from . import sm2

HITS = sm2.HITS
hit = sm2.hit

POOLK = ("pool", "pool_eq")
SHAPES = ("ladder_kind", "fulcrum_exit", "mm_first", "partial_trigger")      # each shapes the whole ladder: at most one of them (and none with an exit_mode2 / partial_mode / ladder_preset shape)
TFRANK = {15: 15, 60: 60, "D": 1440, "W": 10080}


def _S():
    from . import strategy as S
    return S


def _TP():
    from . import targets as TP
    return TP


def _T3():
    from . import tp3 as T3
    return T3


def _T2():
    from . import tp2 as T2
    return T2


# --- 1. validation ----------------------------------------------------------------------------------------------------------------------------------

R_PRESETS = {"cc02_001": (((1.0, 0.5), (3.0, 0.25)), 2.0), "cc02_003": (((3.0, 0.5),), 0.0)}     # partial_trigger presets: (r_ladder, r_be)


def check_params(p) -> None:
    """Validation of the chunk's Params (strategy.Params.__post_init__) and the inert-switch notes."""
    for name, ok in (("ladder_kind", ("", "half_3r")), ("fulcrum_exit", ("", "ladder", "trail")), ("partial_trigger", ("", "r_multiple") + tuple(R_PRESETS))):
        if getattr(p, name) not in ok:
            raise ValueError(f"{name} {getattr(p, name)!r}: expected one of {ok}")
    if p.tgif_exits not in (False, True, "066"):
        raise ValueError(f"tgif_exits {p.tgif_exits!r}: expected False / True (25/25/50) / '066'")
    if (p.collapse_adr_frac < 0 or not 0 <= p.runner_frac < 1 or p.capture_n < 1 or p.runner_htf_pts < 0 or not 0 <= p.gap_speed_bump_partial < 1 or p.bump_max_pts <= 0
            or not 0 <= p.eq60_frac < 1 or not 0 <= p.mm_first < 1 or p.proj_k_max < 1 or p.consol_eq_bars < 5 or p.consol_adr_frac <= 0 or p.pm_sd_mult <= 0
            or p.stage_weeks < 1 or p.rr_big <= 0 or p.rr_n_big < 1 or p.rr_relaxed < 0):
        raise ValueError("targets_partials #4/4: collapse_adr_frac >= 0; 0 <= runner_frac, gap_speed_bump_partial, eq60_frac, mm_first < 1; capture_n >= 1; runner_htf_pts >= 0; bump_max_pts, "
                         "consol_adr_frac, pm_sd_mult, rr_big > 0; proj_k_max >= 1; consol_eq_bars >= 5; stage_weeks, rr_n_big >= 1; rr_relaxed >= 0")
    if len(p.ob_pt_windows) < 1 or any(len(w) != 2 or not 0 <= w[0] < w[1] <= 1440 for w in p.ob_pt_windows):
        raise ValueError("ob_pt_windows: (start_minute, end_minute) pairs")
    if any(len(x) != 2 or int(x[0]) < 1 or float(x[1]) <= 0 for x in p.tf_cap_pts):
        raise ValueError("tf_cap_pts: (timeframe minutes, cap in ES pts) pairs")
    if not p.stage_targets or any(float(x) <= 0 for x in p.stage_targets):
        raise ValueError("stage_targets: a non-empty tuple of fixed targets (ES pts) > 0")
    if p.partial_trigger in ("r_multiple",) and not p.r_ladder:
        raise ValueError("partial_trigger='r_multiple' needs r_ladder ((R, share), ...) - or use a preset ('cc02_001' / 'cc02_003')")
    if any(float(r) <= 0 or float(f) <= 0 for r, f in p.r_ladder) or sum(float(f) for _, f in p.r_ladder) >= 1 or p.r_be < 0:
        raise ValueError("r_ladder: (R > 0, share > 0) pairs whose shares sum to < 1; r_be >= 0")
    n_shape = sum(1 for x in (p.ladder_kind, p.fulcrum_exit, p.mm_first > 0 and "mm", p.partial_trigger) if x)
    if n_shape > 1:
        raise ValueError("ladder_kind, fulcrum_exit, mm_first and partial_trigger each shape the whole ladder: set at most one of them")
    if n_shape and (p.ladder_preset or p.exit_mode2 or p.partial_mode not in ("", "experienced")):
        raise ValueError("ladder_kind / fulcrum_exit / mm_first / partial_trigger cannot be combined with ladder_preset, exit_mode2 or partial_mode (they each shape the whole ladder)")
    inert = []
    if p.fulcrum_exit and p.sd_anchor != "fulcrum":
        inert.append("fulcrum_exit acts on trades of sd_anchor='fulcrum'")
    if p.runner_htf_steps and not p.runner_htf:
        inert.append("runner_htf_steps acts on runner_htf=True")
    if (p.lrlr_allow_beyond) and not p.lrlr_ceiling:
        inert.append("lrlr_allow_beyond acts on lrlr_ceiling=True")
    if p.confluence_only and not p.confluence_weight:
        inert.append("confluence_only acts on confluence_weight=True")
    if p.tgif_last_hour_cover and p.tgif_exits != "066":
        inert.append("tgif_last_hour_cover acts on tgif_exits='066'")
    if p.tgif_reentry_pm and not p.tgif_zone:
        inert.append("tgif_reentry_pm acts on tgif_zone=True days")
    if p.consol_eq_target and p.htf_bias == "off":
        inert.append("consol_eq_target needs a bias (htf_bias != 'off'): it is inert with htf_bias='off'")
    if p.fulcrum_exit == "trail" and p.htf_bias == "off":
        inert.append("fulcrum_exit='trail' needs a bias (htf_bias != 'off'): it falls back to 'ladder' with htf_bias='off'")
    if (p.collapse_adr_frac or p.runner_frac) and p.consol_no_runner:
        inert.append("consol_no_runner ignores runner_frac / collapse_adr_frac / runner_htf on a consolidation day")
    if inert:
        warnings.warn("inert switches (targets_partials #4/4): " + "; ".join(inert), stacklevel=4)


def derive(p) -> None:
    """X3-r-multiple-partials: the presets 'cc02_001' / 'cc02_003' fill r_ladder / r_be (an explicit r_ladder wins)."""
    if p.partial_trigger in R_PRESETS:
        lad, be = R_PRESETS[p.partial_trigger]
        if not p.r_ladder:
            p.r_ladder = lad
        if not p.r_be:
            p.r_be = be


def raw_on(p) -> bool:
    """True when a switch that adds / removes raw rungs (hook R) is on."""
    return bool(p.weekly_hl_rung or p.proj_breaker_multi or p.pm_ladder_am or p.skip_balanced or p.ob_target_tod)


def late_on(p) -> bool:
    return bool(p.collapse_adr_frac > 0 or p.runner_frac > 0 or p.capture_zone or p.runner_at_half or p.runner_htf or p.gap_speed_bump_partial > 0 or p.partial_trigger
                or p.eq60_rung or p.subrange_first or p.confluence_weight or p.void_ladder or p.mm_first > 0 or p.fulcrum_exit or p.lrlr_ceiling or p.lrlr_zone or p.consol_eq_target
                or p.consol_no_runner or p.same_range_t1 or p.tf_target_cap or p.void_draw or p.void_rearm or p.rr_month_gate or p.ladder_kind or p.m1450_targets
                or p.min_rr_final > 0 or p.strength_hold or p.tgif_exits == "066" or p.tgif_reentry_pm or p.ob_target_tod or p.target_stage)


def any_on(p) -> bool:
    """True when the state dict of _finish_order is needed (every hook)."""
    return bool(raw_on(p) or late_on(p) or p.tgif_exits == "066")


# --- 2. helpers -------------------------------------------------------------------------------------------------------------------------------------

def _adr(ctx):
    return _T3()._adr(ctx)


def _conf(ctx):
    return getattr(ctx, "conf", None)


def base_fr(p, keep: list, fr):
    """The shares of `keep`: the given ones, else the built ladder's."""
    return list(fr) if fr is not None else list(_T3().base_fracs(p, len(keep)))


def norm(fr: list) -> list:
    s = sum(fr) or 1.0
    return [f / s for f in fr]


def prune(keep: list, fr: list):
    """Rungs with no share left are dropped; the shares are renormalised."""
    pairs = [(x, f) for x, f in zip(keep, fr) if f > 1e-9]
    if not pairs:
        return keep, fr
    return [x for x, _ in pairs], norm([f for _, f in pairs])


def scale_head(fr: list, n_head: int, tail: list) -> list:
    """The first n_head shares of fr rescaled to (1 - sum(tail)), followed by the tail shares."""
    head = fr[:n_head]
    room = max(0.0, 1.0 - sum(tail))
    s = sum(head) or 1.0
    return [f * room / s for f in head] + list(tail)


def day_tag_set(ctx) -> set:
    """The day's tags: strategy.day_context's (ctx.day_tags: tgif_short, big_prev ...) and the day_week_context plan's (ctx.dplan.tags: post_holiday, holiday_eve, consol_day ...)."""
    t = set(str(getattr(ctx, "day_tags", "") or "").split("|"))
    P = getattr(ctx, "dplan", None)
    if P is not None:
        t |= set(P.tags)
    return t


def bias_dir(ctx, p, session: str, i: int) -> int:
    """The htf.table bias (+1 / -1 / 0) for the session at closed bar i; 0 when it cannot be read."""
    try:
        from . import bias_day as _BD
        return int(_BD.want_at(ctx, p, session, i))
    except Exception:
        return 0


def tf_pools(ctx, sd, i: int, above: float) -> list:
    """X3-runner-htf-target (099 ~37:57; cc02_003 ~3:26): the untaken buy-side pools above `above` ranked by the timeframe of the swing that made them: 15m / 60m pivot highs
    (levels.tf_pivots on the bars through i), the untaken prior daily highs (rank 1440), the prior week's high (10080). Returns [(price, rank)] ascending; side space."""
    out = []
    n = i + 1
    for m in (15, 60):
        if m <= ctx.tf:
            continue
        ph, _ = L.tf_pivots(ctx.idx[:n], sd.h[:n], sd.l[:n], ctx.tf, m)
        for q in ph:
            if q.known <= i and q.price > above and sd.h[q.i + 1:n].max(initial=-np.inf) < q.price:
                out.append((float(q.price), m))
    for k in (("pdh1", "pdh2", "pdh3") if sd.sign > 0 else ("pdl1", "pdl2", "pdl3")):
        if k in ctx.pd:
            v = float(sd.x(ctx.pd[k]))
            if v > above and sd.h[ctx.start:n].max(initial=-np.inf) < v:
                out.append((v, 1440))
    pw = getattr(ctx, "pw", None)
    if pw is not None:
        v = float(sd.x(pw[0] if sd.sign > 0 else pw[1]))
        if v > above and sd.h[ctx.start:n].max(initial=-np.inf) < v:
            out.append((v, 10080))
    return sorted(set(out))


def void_registry(ctx, sd, i: int, p, above: float) -> list:
    """The unfilled bearish voids above `above` (side space) as (near, ce, far): the A10 true price gaps (levels.voids) and the one-sided down legs (tp3.void_levels' source). Known from
    the bar that completes them; filled = a later high reached the near edge."""
    out = []
    for z in sd._lazy("voids_bear", lambda: [z for z in L.voids(sd.h, sd.l) if z.kind == "bear" and z.top - z.bottom >= sd.min_gap]):
        if z.i <= i and z.bottom > above and sd.h[z.i + 1:i + 1].max(initial=-np.inf) < z.bottom:
            out.append((float(z.bottom), float(z.mid), float(z.top)))
    T3 = _T3()
    for m in sorted({ctx.tf, 15, 60}):
        a = T3.tf_arrays(ctx, sd, i, m)
        if a is None or len(a[1]) < 6:
            continue
        o, h, l, c, ends = a
        for z in L.one_sided_legs(o, h, l, c, p.void_leg_mult, p.void_max_opp):
            if z.i >= len(h):
                continue
            end = int(ends[z.i])
            leg_end = int(ends[z.i - 1]) if z.i >= 1 else end
            if end > i or z.top <= above or sd.h[leg_end + 1:i + 1].max(initial=-np.inf) >= z.bottom:
                continue
            out.append((float(z.bottom), float((z.top + z.bottom) / 2), float(z.top)))
    return sorted(set(out))


def range60_quarters(ctx, p, entry: float):
    """The 60-day body range's quarter containing `entry` as (lo, hi, eq) real prices -> side space is the caller's; None without a range [our interpretation of the 'daily
    consolidation quadrant' of cc07_005: the quarter of the 60-day range]."""
    r = _T3().range60(ctx, p, "body")
    if r is None:
        return None
    return r


def p60_bracket(ctx, sd, i: int):
    """The last confirmed 60m pivot high above and low below the last close (side space), or None."""
    if 60 <= ctx.tf:
        return None
    n = i + 1
    ph, pl = L.tf_pivots(ctx.idx[:n], sd.h[:n], sd.l[:n], ctx.tf, 60)
    c = float(sd.c[i])
    hs = [q for q in ph if q.known <= i and q.price > c]
    ls = [q for q in pl if q.known <= i and q.price < c]
    if not hs or not ls:
        return None
    return float(ls[-1].price), float(hs[-1].price)


def raw_of(v: float, k: str, p) -> float:
    return _TP()._raw(v, k, p)


# --- 3. hook R: the raw rungs ----------------------------------------------------------------------------------------------------------------------

def weekly_hl_levels(ctx, sd, i: int, p, above: float) -> list:
    """X3-layered-pool-ladder-runner (cc04_003 ~30:19): the prior week's high (low for a short) as a pool-kind level - the 'nearest old weekly high' rung - when it lies above the price
    and today's bars have not traded it. (ctx.pw is built from the completed sessions of the prior ISO week.)"""
    pw = getattr(ctx, "pw", None)
    if pw is None:
        return []
    v = float(sd.x(pw[0] if sd.sign > 0 else pw[1]))
    if v <= above or sd.h[ctx.start:i + 1].max(initial=-np.inf) >= v:
        return []
    hit("weekly_hl_rung")
    return [(v, "pool")]


def breaker_legs(ctx, sd, i: int, p) -> list:
    """L13-multi-sd-breaker-confluence (070 ~1:04:18): the A-B legs of the bullish breakers (side space) on the 1m / 5m frame since the session start: A = the sweep extreme (the lowest
    low between the swing high and the closing break), B = the swing high H the body close broke; known from the break bar. [(A, B, known_bar_in_base_terms)]"""
    T3 = _T3()
    out = []
    for m in sorted({ctx.tf, 5}):
        if m < ctx.tf:
            continue
        if m == ctx.tf:
            h, l, c, ends = sd.h[:i + 1], sd.l[:i + 1], sd.c[:i + 1], np.arange(i + 1)
            o = sd.o[:i + 1]
        else:
            a = T3.tf_arrays(ctx, sd, i, m)
            if a is None:
                continue
            o, h, l, c, ends = a
        ph, pl = L.pivots(h, l, 2)
        used = set()
        for j in range(len(c)):
            ks = [q for q in ph if q.known <= j]
            if not ks:
                continue
            H = ks[-1]
            if H.i in used:
                continue
            lows = [q for q in pl if q.i < H.i]
            if not lows:
                continue
            L1 = lows[-1]
            seg = l[H.i + 1:j]
            if not len(seg) or seg.min() >= L1.price or not c[j] > H.price:
                continue
            used.add(H.i)
            ext_i = H.i + 1 + int(np.argmin(seg))
            if int(ends[ext_i]) < ctx.start or int(ends[j]) > i:
                continue
            out.append((float(l[ext_i]), float(H.price), int(ends[j])))
    return out


def proj_breaker_multi_levels(ctx, sd, i: int, p, above: float, lv: list, st: dict) -> list:
    """L13-multi-sd-breaker-confluence (070 ~1:01:47 - 1:05:22): for each breaker leg A-B compute B + k (B - A), k in 1, 1.5 .. proj_k_max; keep the levels inside the HTF draw range (from the
    first pool up to the far edge of the nearest untouched daily / weekly array; without one up to 3 x ADR5 beyond the first pool [our interpretation]); levels of >= 2 distinct legs within
    sd_cluster_ticks (4 = 1 pt when 0) are one cluster = one 'proj' rung (the mean); a cluster within 1 pt of a pool confirms that pool (report tag proj_confirms_pool)."""
    legs = breaker_legs(ctx, sd, i, p)
    if len(legs) < 2:
        return []
    hit("eval_proj_breaker_multi")
    pools = sorted(v for v, k in lv if k in POOLK and v > above)
    lo_b = pools[0] if pools else above
    hi_b = None
    cf = _conf(ctx)
    if cf is not None:
        far = []
        for r in cf.opposing_ext(_TP().now_ts(ctx, i), sd.x(above), sd.sign, ("D", "W", "M"), (0, 1, 2, 3)):
            near, f = _TP()._zone_edges(sd, r)
            if near > lo_b:
                far.append(max(near, f))
        hi_b = min(far) if far else None
    if hi_b is None:
        adr = _adr(ctx)
        hi_b = lo_b + 3.0 * adr if adr else np.inf
    ks = [1.0 + 0.5 * n for n in range(int(round((p.proj_k_max - 1.0) / 0.5)) + 1)]
    cand = []
    for li, (A, B, _) in enumerate(legs):
        if B <= A:
            continue
        for k in ks:
            v = B + k * (B - A)
            if lo_b < v <= hi_b and v > above:
                cand.append((v, li))
    cand.sort()
    tol = (p.sd_cluster_ticks or 4) * 0.25 * p.es_pt
    out, cur = [], []
    for v, li in cand:
        if cur and v - cur[0][0] > tol + 1e-9:
            if len({x[1] for x in cur}) >= 2:
                out.append(float(np.mean([x[0] for x in cur])))
            cur = []
        cur.append((v, li))
    if cur and len({x[1] for x in cur}) >= 2:
        out.append(float(np.mean([x[0] for x in cur])))
    if not out:
        return []
    st.setdefault("conf_pools", [])
    for v in out:
        for pv in pools:
            if abs(v - pv) <= p.es_pt + 1e-9:
                st["conf_pools"].append(pv)
    hit("proj_breaker_multi")
    return [(v, "proj") for v in out]


def pm_am_ladder_levels(ctx, sd, i: int, p, session: str, ext: float, leg_hi: float, above: float) -> list:
    """M7-pm-mss-after-1300-targets (043 ~13:28): after 13:00 a bullish MSS with displacement targets the highs formed during lunch and before it: the lunch high, every untaken AM swing
    high (09:30-12:00 pivots), nearest first, then the SD projection of the MSS leg (leg_hi + pm_sd_mult x the leg). [our interpretation: 'untaken' = not traded since the pivot]."""
    S = _S()
    if session != "PM":
        return []
    out = []
    ls = getattr(ctx, "sess", {}).get("lunch")
    if ls is not None and ctx.t[i] >= ls[2]:
        v = float(sd.x(ls[0] if sd.sign > 0 else ls[1]))
        if v > above and sd.h[S._idx_at(ctx, ls[2]):i + 1].max(initial=-np.inf) < v:
            out.append((v, "pool"))
    a, b = S._idx_at(ctx, 570), S._idx_at(ctx, 720)
    for q in _TP()._ph(sd):
        if q.known <= i and a <= q.i < b and q.price > above and sd.h[q.i + 1:i + 1].max(initial=-np.inf) < q.price:
            out.append((float(q.price), "pool"))
    if leg_hi > ext:
        out.append((float(leg_hi + p.pm_sd_mult * (leg_hi - ext)), "proj"))
    if out:
        hit("pm_ladder_am")
    return out


def balanced_drop(ctx, sd, i: int, p, lv: list) -> list:
    """T8-pm-carry-condition (029 ~1:30:37): a candidate level (not a pool) that today's closed bars have crossed in both directions - a close above it and a close below it - is balanced
    and no target. 'Since it formed' = since the bar that made the level known (a pivot's `known` bar, `sd.ph` / `sd.pl`) when the level is a pivot of the base frame, else [our
    interpretation] since the day's first bar."""
    if not i + 1 > ctx.start:
        return lv
    piv = [(x.price, x.known) for x in list(sd.ph) + list(sd.pl) if x.known <= i]
    out = []
    for v, k in lv:
        b0 = max([kn for pr, kn in piv if abs(pr - v) <= 1e-9] or [ctx.start])       # (the latest pivot at that price)
        c = sd.c[max(ctx.start, b0):i + 1]
        if k not in POOLK and len(c) and (c > v).any() and (c < v).any():
            hit("skip_balanced")
            continue
        out.append((v, k))
    return out


def raw_post(ctx, sd, i: int, p, session: str, entry: float, risk: float, above: float, sw: dict, leg_hi: float, lv: list, lvt: list, tags: dict, st: dict) -> list:
    """The raw (level, kind) rungs of the order before the exit prices (hook R, after tp3.raw_post): the prior week's high, the multi-k breaker clusters, the PM lunch + AM highs, the
    balanced-level filter."""
    out = list(lv)
    add = []
    if p.weekly_hl_rung:
        add += weekly_hl_levels(ctx, sd, i, p, above)
    if p.proj_breaker_multi:
        add += proj_breaker_multi_levels(ctx, sd, i, p, above, out, st)
    if p.pm_ladder_am:
        add += pm_am_ladder_levels(ctx, sd, i, p, session, float(sw["ext"]), float(leg_hi), above)
    out = sorted(set(out) | {(float(v), k) for v, k in add if v > above})
    if p.skip_balanced:
        out = balanced_drop(ctx, sd, i, p, out)
    return out


# --- 4. ladder presets (called from tp3.late) -------------------------------------------------------------------------------------------------------

def ladder_041(ctx, sd, i: int, p, entry: float, risk: float, keep: list, st: dict):
    """X3-041-projection-first-then-nwog (041 ~1:16): T1 = the first SD projection (kind sd / proj*) short of the NWOG's near edge, 1/3 of the units there; then the NWOG near edge, its CE
    and its near edge + 0.75 x height ('deep', exact) with (0.33, 0.27, 0.2, 0.2). Needs a stored NWOG above the entry (tp2.nwog_zones) and a projection rung below it; else None
    (today's ladder). `be_pad_pts` applies after rung 1 when be_on == 't1'. Returns (rungs, fracs) or None."""
    S = _S()
    TP = _TP()
    zs = [z for z in _T2().nwog_zones(ctx, sd, i) if z[0] > entry]
    if not zs:
        return None
    lo, hi, ce = min(zs, key=lambda z: z[0])[:3]
    proj = [x for x in keep if (x[1] in TP.SD_KINDS or str(x[1]).startswith("proj")) and x[0] - entry >= p.min_rr * risk and x[0] < lo - 1e-9]
    if not proj:
        return None
    r1 = proj[0]
    h = hi - lo
    rungs = [r1, (float(S._exit_px(lo, "array", p)), "array"), (float(S._exit_px(ce, "array", p)), "array"), (float(lo + 0.75 * h), "exact")]
    hit("ladder_041")
    return rungs, [0.33, 0.27, 0.2, 0.2]


def ladder_096(ctx, sd, i: int, p, entry: float, risk: float, keep: list, st: dict):
    """X3-resting-1lot-partials-vi-final (096 ~5:34): rung 1 = the nearest swing high (exact, +1 tick: a limit just above it), rung 2 = the next level, the balance (0.6) at the near edge
    of the first bearish volume imbalance (Side.vis('bear')) short of the last pool - the pool itself is dropped from the ladder. Shares (0.2, 0.2, 0.6). Without a VI: today's ladder
    (None). Returns (rungs, fracs) or None."""
    S = _S()
    if not keep:
        return None
    pools = [x for x in keep if x[1] in POOLK]
    last_pool = pools[-1] if pools else keep[-1]
    pool_raw = raw_of(last_pool[0], last_pool[1], p)
    vi = [z for z in sd.vis("bear") if z.i <= i and entry < z.bottom < pool_raw - 1e-9 and sd.h[z.i + 1:i + 1].max(initial=-np.inf) < z.bottom]
    if not vi:
        return None
    z = min(vi, key=lambda z: z.bottom)
    last = (float(S._exit_px(z.bottom, "array", p)), "array")
    pre = [x for x in keep if x[0] < last[0] - p.es_pt and x[1] != "speed"]
    if not pre:
        return None
    r1 = pre[0]
    swing = next((x for x in pre if x[1] in ("swing",) or x[1] in POOLK), r1)
    r1 = (float(raw_of(swing[0], swing[1], p) + p.tick), "exact")
    nxt = next((x for x in pre if x[0] > r1[0] + p.es_pt), None)
    if nxt is None:
        return None                                  # review fix: the spec has only (0.2, 0.2, 0.6); fewer than three rungs = today's ladder
    hit("ladder_096")
    return [r1, nxt, last], [0.2, 0.2, 0.6]


# --- 5. hook L: the ladder after tp3.late -----------------------------------------------------------------------------------------------------------

def tf_cap(ctx, p, entry: float, keep: list):
    """new-tf-matches-objective (cc04_002 ~37:27) tf_target_cap: the final rung is capped at tf_cap_pts[tf] ES pts from the entry for the run's timeframe (default {1: 10, 5: 20,
    15: 40}); T1 beyond the cap = the objective needs a higher timeframe (None = reject). Rungs beyond the cap are replaced by one 'fixed' rung AT the cap. A timeframe without an entry
    in the table is unlimited."""
    cap = dict((int(a), float(b)) for a, b in p.tf_cap_pts).get(int(ctx.tf))
    hit("eval_tf_cap")
    if cap is None or not keep:
        return keep
    px = entry + cap * p.es_pt
    if keep[0][0] > px + 1e-9:
        return None
    if keep[-1][0] <= px + 1e-9:
        return keep
    hit("tf_target_cap")
    return [x for x in keep if x[0] < px - p.es_pt] + [(float(px), "fixed")]


def range_session_t1(ctx, sd, sw, i: int, p, entry: float, risk: float, keep: list):
    """M0-target-opposite-extreme-same-range (067 ~18:56): the raided pool is the extreme of a session range (prev_pm, london, lunch, prev_london, prev_am): the OTHER extreme of that
    same range is the first rung (T1) when it pays min_rr; the nearer rungs are dropped, the farther ones stay. Returns the new keep or None."""
    S = _S()
    nm = str(sw.get("name", ""))
    r = getattr(ctx, "sess", {}).get(nm)
    if r is None:
        return None
    hit("eval_same_range")
    v = float(sd.x(r[0] if sd.sign > 0 else r[1]))
    px = float(S._exit_px(v, "pool", p))
    if px - entry < p.min_rr * risk:
        return None
    hit("same_range_t1")
    return [(px, "pool")] + [x for x in keep if x[0] > px + p.es_pt]


def lrlr_ceiling_level(ctx, sd, sw, i: int, p, entry: float):
    """L4-lrlr-ceiling (cc01_007 ~13:38): U = the old low (a swing_tiers low - the intermediate-term lows first, else the plain swing lows - formed before the sweep) that a later close
    broke before the sweep, the nearest one above the entry (side space) [our interpretation of the spec's 'most recent / lowest': the lowest broken low above the entry]. Returns (U or
    None, the highest broken old low above the sweep extreme or None)."""
    ext_i = int(sw["ext_i"])
    tiers = sd.tiers()
    for name in ("itl", "stl"):
        best, top = None, None
        for q in tiers[name][1]:
            if q.known > i or q.i >= ext_i or q.price <= float(sw["ext"]):
                continue
            if (sd.c[q.i + 1:ext_i + 1] < q.price).any():
                top = q.price if top is None else max(top, q.price)
                if q.price > entry:
                    best = q.price if best is None else min(best, q.price)
        if best is not None:
            return float(best), top
        if top is not None:
            return None, float(top)                     # every broken old low lies at or under the entry
    return None, None


def lrlr_zone_gate(ctx, sd, sw, i: int, p, entry: float):
    """L4-lrlr-repeated-buys (cc01_007 ~14:10) under `lrlr_zone` (review fix: the spec puts it there): no new long once price is AT the zone's ceiling L_b - the order's entry is at or above
    L_b while the sweep extreme lies inside the zone (at or above the MSS level) [our interpretation of 'at the ceiling']. Returns the reject reason or None."""
    from . import tp1
    z = tp1.lrlr_zone(ctx, sd, i, p)
    hit("eval_lrlr_zone_gate")
    if z is None:
        return None
    if float(sw["ext"]) >= z[0] - 1e-9 and entry >= z[1] - 1e-9:
        hit("lrlr_zone_ceiling")
        return "x_lrlr_ceiling"
    return None


def lrlr_cap(ctx, sd, sw, i: int, p, entry: float, risk: float, keep: list, lvt: list):
    """L4-lrlr-ceiling: levels at or above U are high resistance ('hrlr', dropped unless lrlr_allow_beyond); the final rung is capped at U - exit_before_pts. Returns (why, keep)."""
    U, top = lrlr_ceiling_level(ctx, sd, sw, i, p, entry)
    hit("eval_lrlr_ceiling")
    if U is None:
        if top is not None and entry - top <= 2.0 * risk and not p.lrlr_allow_beyond:     # review fix: only AT the ceiling (within 2 risks above the highest broken old low [our interpretation]), not any price above it
            hit("lrlr_at_ceiling")
            return "x_lrlr_ceiling", keep                # L4-lrlr-repeated-buys (cc01_007 ~14:10): no new long once price is at the ceiling - beyond it the run is high resistance
        return None, keep
    hit("lrlr_ceiling")
    cap = U - p.exit_before_pts * p.es_pt
    if cap - entry < p.min_rr * risk:
        return "x_lrlr_ceiling", keep
    lvt.append("lrlr_ceiling")
    if p.lrlr_allow_beyond:
        lvt.append("hrlr_beyond")
        return None, keep
    inside = [x for x in keep if x[0] <= cap + 1e-9]
    if len(inside) < len(keep):
        lvt.append("hrlr")
        hit("hrlr_dropped")
    if not inside or inside[-1][0] < cap - p.es_pt:
        inside = inside + [(float(cap), "array")]
    return None, inside


def consol_range(ctx, sd, sw, i: int, p):
    """X1-consol-sweep-target-eq (cc09_004 ~12:29): the consolidation range of the last consol_eq_bars bars BEFORE the sweep (side space): (RL, RH) when its height is under
    consol_adr_frac x ADR5 and the sweep took its low (the swept level sits at RL when the sweep names one); else None."""
    e = int(sw["ext_i"])
    hit("eval_consol_eq")
    a = max(ctx.start, e - int(p.consol_eq_bars))
    if e - a < int(p.consol_eq_bars) // 2:
        return None
    RL, RH = float(sd.l[a:e].min()), float(sd.h[a:e].max())
    adr = _adr(ctx)
    if not adr or RH - RL > p.consol_adr_frac * adr or float(sw["ext"]) >= RL:
        return None
    lvl = sw.get("level")
    if lvl is not None and abs(float(lvl) - RL) > max(p.eq_tol_pts * p.es_pt, 0.25):
        return None
    return RL, RH


def consol_eq_cut(ctx, sd, sw, i: int, p, session: str, entry: float, risk: float, keep: list):
    """X1-consol-sweep-target-eq: with the htf.table bias in the trade direction the final rung is the range EQ - exit_before_pts and the farther rungs go (or the last stays as a
    runner_frac runner). Returns (keep, fr or None) or None."""
    r = consol_range(ctx, sd, sw, i, p)
    if r is None or bias_dir(ctx, p, session, i) != sd.sign:
        return None
    eq = (r[0] + r[1]) / 2
    v = float(_S()._exit_px(eq, "array", p))
    if v - entry < p.min_rr * risk:
        return None
    far = [x for x in keep if x[0] > v + p.es_pt]
    new = [x for x in keep if x[0] < v - p.es_pt] + [(v, "array")]
    hit("consol_eq_target")
    if p.runner_frac > 0 and far:
        new = new + [far[-1]]
        return new, scale_head(base_fr(p, new, None), len(new) - 1, [p.runner_frac])
    return new, None


def void_pick(ctx, sd, i: int, p, entry: float, risk: float):
    """new-sellstop-run-before-void-fill (cc04_010 ~8:07): the nearest unfilled opposing void within 3 x ADR5 whose top (the full fill) pays min_rr is the final target. Returns its exit
    price or None."""
    adr = _adr(ctx)
    reach = 3.0 * adr if adr else np.inf
    S = _S()
    hit("eval_void_draw")
    zs = [z for z in void_registry(ctx, sd, i, p, entry) if z[2] - entry <= reach and S._exit_px(z[2], "array", p) - entry >= p.min_rr * risk]
    if not zs:
        return None
    z = min(zs, key=lambda z: z[2])
    return float(S._exit_px(z[2], "array", p))


def final_gates(ctx, p, entry: float, risk: float, fin: float, lvt: list, d4: dict):
    """The reward gates on the FINAL placed target (after every cut; review fix): records rr_final on every order that reaches tp4.late (L15-min-3R-prefer-5R / L15-min-rr-3), the rr5 tag,
    the minimum final reward (x_min_rr_final) and the month gate (new-rr-month-gate cc02_001 ~12:11: x_rr_month). Returns the reject reason or None."""
    rrf = (fin - entry) / risk if risk > 0 else 0.0
    d4["rr_final"] = round(float(rrf), 3)
    if p.min_rr_final > 0 and rrf >= 5.0 - 1e-9:
        lvt.append("rr5")
        hit("rr5")
    if p.rr_month_gate:
        wk = getattr(ctx, "week", None) or {}
        need = p.rr_big if int(wk.get("month_big", 0)) < p.rr_n_big else p.rr_relaxed
        hit("eval_rr_month")
        if fin - entry < need * risk - 1e-9:
            return "x_rr_month"
    if p.min_rr_final > 0 and fin - entry < p.min_rr_final * risk - 1e-9:
        return "x_min_rr_final"
    return None


def m1450_ladder(ctx, sd, sw, i: int, p, entry: float, risk: float, leg_hi: float, tg):
    """T7-1450-targets (043 ~15:49; 075 ~1:45:16), side space (the spec's 'premium high, down swing' is the mirror): the PM leg = the highest high since 13:30 down to the macro low
    (the extreme of the PM move so far). Premium gate: the macro extreme must be in the discount half of the 00:00-now range (and beyond the midnight open when m1450_mid_open) else
    ('x_m1450_not_premium', []). Rungs: the nearest swing high above the leg's EQ (formed in the leg, untaken), then the untaken highs of the 07:00-08:30, 08:30-09:30 and
    09:30-11:00 ranges (complete at 510 / 570 / 660) nearest first, on a TGIF Friday also the 20 % level of the weekly range. Returns (why, [(price, kind)]) - an empty list = keep
    today's ladder. [our interpretation: the three session ranges are read straight from the day's bars (no DayCtx pools), so nothing else treats them as targets.]"""
    S = _S()
    hit("eval_m1450")
    a = S._idx_at(ctx, 810)
    if a > i or a >= len(ctx.t):
        return None, []
    m = a + int(np.argmin(sd.l[a:i + 1]))
    macro = float(sd.l[m])
    top = float(sd.h[ctx.start:i + 1].max())
    bot = float(sd.l[ctx.start:i + 1].min())
    ok = macro < (top + bot) / 2
    mo = S._open_known(ctx, "midnight", i)
    if ok and p.m1450_mid_open and mo is not None:
        ok = macro < float(sd.x(mo))
    if not ok:
        hit("m1450_not_premium")
        return "x_m1450_not_premium", []
    leg0 = float(sd.h[a:m + 1].max())
    eq = (leg0 + macro) / 2
    swings = [q.price for q in _TP()._ph(sd) if q.known <= i and a <= q.i <= m and eq < q.price <= leg0 and sd.h[q.i + 1:i + 1].max(initial=-np.inf) < q.price]
    out = []
    if swings:
        out.append((float(S._exit_px(min(swings), "pool", p)), "pool"))
    pools = []
    for lo_m, hi_m in ((420, 510), (510, 570), (570, 660)):
        k0, k1 = S._idx_at(ctx, lo_m), S._idx_at(ctx, hi_m)
        if k1 >= len(ctx.t) or k1 > i or k1 <= k0:
            continue
        v = float(sd.h[k0:k1].max())
        if v > entry and sd.h[k1:i + 1].max(initial=-np.inf) < v:
            pools.append(v)
    out += [(float(S._exit_px(v, "pool", p)), "pool") for v in sorted(set(pools))]
    if tg is not None and tg.get("levels"):
        out.append((float(tg["levels"][0]), "exact"))
    out = sorted(x for x in set(out) if x[0] - entry >= p.min_rr * risk)
    dedup = []
    for x in out:
        if not dedup or x[0] - dedup[-1][0] > p.es_pt:
            dedup.append(x)
    if dedup:
        hit("m1450_ladder")
    return None, dedup


def half_3r(ctx, sd, i: int, p, entry: float, risk: float, keep: list, draw: float, locked: bool, st: dict):
    """E8-2pct-split-experienced (cc02_003 ~12:32): half the units at entry + 3R (kind 'fixed'), the other half at the HTF objective: the locked draw, else the near edge of the nearest
    untouched daily / weekly / monthly opposing array (tp3.htf_draw), else the last ladder rung. Returns (rungs, fracs)."""
    S = _S()
    R3 = float(entry + 3.0 * risk)
    if locked:
        fin = (float(draw), keep[-1][1] if keep else "array")
    else:
        H = _T3().htf_draw(ctx, sd, i, p, entry, st)
        fin = (float(S._exit_px(H, "array", p)), "array") if H is not None else keep[-1]
    if fin[0] <= R3 + p.es_pt:
        return [fin], [1.0]
    hit("ladder_half_3r")
    return [(R3, "fixed"), fin], [0.5, 0.5]


def fulcrum_ladder(ctx, sd, sw, i: int, p, session: str, entry: float, risk: float, leg_hi: float):
    """X3-fulcrum-exit-modes (090 ~1:32:54), trades of sd_anchor='fulcrum': 'ladder' = the fulcrum pool + beyond (0.33), -0.5 SD (0.33), -1 SD - exit_before_pts (the rest); 'trail' =
    one rung at -1 SD, the FVG trail active from the fill - only with a bias (htf.table) and not on a holiday-adjacent day, else the ladder. Returns (rungs, fracs, trail) or None."""
    if p.sd_anchor != "fulcrum":
        return None
    hit("eval_fulcrum")
    S = _S()
    rg = next((r for r in _TP().sd_ranges(ctx, sd, i, p, sw, leg_hi, None) if r[0] == "fulcrum"), None)
    if rg is None:
        return None
    _, lo, hi = rg
    h = hi - lo
    far = (float(S._exit_px(hi + h, "sd", p)), "sd")
    trail = False
    if p.fulcrum_exit == "trail":
        if p.htf_bias != "off" and bias_dir(ctx, p, session, i) == sd.sign and not (day_tag_set(ctx) & {"post_holiday", "holiday_eve"}):
            trail = True
    if trail:
        hit("fulcrum_trail")
        return [far], [1.0], True
    rungs = [(float(S._exit_px(hi, "pool", p)), "pool"), (float(S._exit_px(hi + 0.5 * h, "sd", p)), "sd"), far]
    rungs = [x for x in rungs if x[0] - entry >= p.min_rr * risk]
    if not rungs:
        return None
    hit("fulcrum_ladder")
    fr = [0.33, 0.33, 0.34] if len(rungs) == 3 else [1.0 / len(rungs)] * len(rungs)
    return rungs, norm(fr), False


def mm_first_ladder(ctx, sd, i: int, p, session: str, entry: float, risk: float, keep: list):
    """X3-mm-model-target (104 ~53:35): an MM-model trade (sm5 state): rung 1 = the original consolidation's near boundary (its low in side space; sm5.orig_consolidation) with mm_first
    of the units, the final rung the next pool beyond it (the rest). Returns (rungs, fracs) or None. [our interpretation: the NEAR boundary is the edge the trade reaches first.]"""
    from . import sm5
    S = _S()
    hit("eval_mm_first")
    m = sm5._mm(sd, ctx, session)
    if m is None:
        return None
    oc = sm5.orig_consolidation(sd, m, i, p)
    if oc is None:
        return None
    r1 = (float(S._exit_px(oc[1], "array", p)), "array")
    if r1[0] - entry < p.min_rr * risk:
        return None
    nxt = next((x for x in keep if x[1] in POOLK and x[0] > r1[0] + p.es_pt), None) or next((x for x in keep if x[0] > r1[0] + p.es_pt), None)
    hit("mm_first")
    if nxt is None:
        return [r1], [1.0]
    return [r1, nxt], [p.mm_first, 1.0 - p.mm_first]


def r_ladder_rungs(p, entry: float, risk: float, keep: list, fr):
    """X3-r-multiple-partials (cc02_001 ~24:10; cc02_003 ~3:00): the R rungs ('fixed' at entry + R x risk, shares from r_ladder) merged with the pool rungs of `keep`; a rung beyond the
    nearest pool is kept; the other rungs share the rest in ladder proportions; a rung beyond the final level is dropped. Returns (keep, fr, be_at)."""
    final = keep[-1]
    rr = [(entry + float(r) * risk, float(f)) for r, f in p.r_ladder if entry + float(r) * risk < final[0] - p.es_pt]
    be_at = float(entry + p.r_be * risk) if p.r_be else None
    if not rr:
        return keep, fr, be_at
    share = sum(f for _, f in rr)
    base = norm(base_fr(p, keep, None))
    items = [(v, "fixed", f) for v, f in rr] + [(v, k, b * (1.0 - share)) for (v, k), b in zip(keep, base)]
    items.sort(key=lambda x: x[0])
    hit("r_ladder")
    return [(v, k) for v, k, _ in items], [f for _, _, f in items], be_at


def bump_rung(ctx, sd, i: int, p, entry: float, keep: list):
    """X3-gap-speed-bump-before-pool (072 ~28:41): the first unfilled gap (an FVG of either polarity or a void) of height <= bump_max_pts between the entry and the first pool rung: a 'speed'
    rung at its far edge + one tick. Returns the rung price or None."""
    pool = next((raw_of(v, k, p) for v, k in keep if k in POOLK), None)
    if pool is None:
        return None
    zs = []
    for z in list(sd.opposing()) + list(sd.gaps):
        if z.i <= i and z.bottom > entry and z.top < pool and z.top - z.bottom <= p.bump_max_pts * p.es_pt + 1e-9 and sd.h[z.i + 1:i + 1].max(initial=-np.inf) < z.bottom:
            zs.append(z)
    if not zs:
        return None
    z = min(zs, key=lambda z: z.bottom)
    hit("gap_speed_bump")
    return float(z.top + p.tick)


def conf_score(ctx, sd, i: int, p, entry: float, ext: float, leg_hi: float, px: float, st: dict) -> int:
    """X3-scaleout-skip-and-confluence (cc08_007 ~19:41): +1 when the rung sits at an opposing array edge (tp3.gap_registry: within eq_tol_pts of it, the exit buffer short of it
    included), +1 when it sits there at a 1.27 / 1.618 extension of the entry leg (sweep extreme -> leg high) or at its 100 % measured move (entry + the leg)."""
    tol = p.eq_tol_pts * p.es_pt
    buf = p.exit_before_pts * p.es_pt
    s = 0
    edges = [e for g in _T3().gap_registry(ctx, sd, i, p, entry, st) for e in (g[0], g[2])]
    if any(-tol <= e - px <= tol + buf for e in edges):
        s += 1
    rng = leg_hi - ext
    if rng > 0:
        ex = [ext + 1.27 * rng, ext + 1.618 * rng, entry + rng]
        if any(-tol <= e - px <= tol + buf for e in ex):
            s += 1
    return s


def b17_consolidation(ctx, p) -> bool:
    """B17 / B1: the day sits inside a multi-day daily range (daycontext.range_regime 'range') or is flagged a consolidation day (day tags consol_day / daily_range, or the B1 no-draw
    session)."""
    if day_tag_set(ctx) & {"consol_day", "daily_range", "drr_range"} or getattr(ctx, "cur_no_draw", False):
        return True
    c = getattr(ctx, "_tp4_b17", None)
    if c is not None:
        return c
    hist = list(getattr(ctx, "hist", None) or [])
    res = False
    if hist:
        try:
            from . import daycontext as DW
            res = "range" in DW.range_regime(hist, replace(p, drr_tests=("range",)), getattr(ctx, "eth", None))
        except Exception:
            res = False
    try:
        ctx._tp4_b17 = res
    except Exception:
        pass
    return res


def consol_no_runner_cut(ctx, sd, i: int, p, entry: float, keep: list, locked: bool):
    """B17-consolidation-no-runners (048 ~1:51:24; 053 ~9:25): the HTF-array rungs (4h / D / W / M) are dropped, the remaining rungs split ladder_fracs_slow (bulk at T1). Returns (keep, fr)."""
    TP = _TP()
    htf = ("4h", "D", "W", "M")
    kept = [x for x in keep if x[1] in POOLK or not _T3().near_htf_array(ctx, sd, i, entry, raw_of(x[0], x[1], p), p.es_pt, htf)] if not locked else list(keep)
    if not kept:
        kept = [keep[0]]
    return kept, list(TP._ext_fracs(p.ladder_fracs_slow, len(kept), False))


def subrange_cut(ctx, sd, i: int, p, entry: float, risk: float, keep: list, fr):
    """X3-first-profit-premium-subrange (cc07_005 ~9:58): the entry sits in the discount half of its quarter of the 60-day body range; rung 1 = the nearest 1h / 4h opposing array
    (FVG, OB, gap, VI) whose near edge lies above the quarter's EQ and below the final level; the earlier rungs below the EQ are dropped. [our interpretation: the 'daily consolidation
    quadrant' is the quarter of the 60-day range.] Returns (keep, fr) or None."""
    cf = _conf(ctx)
    hit("eval_subrange")
    r = range60_quarters(ctx, p, entry)
    if r is None or cf is None:
        return None
    lo, hi = float(sd.x(r[0])), float(sd.x(r[1]))
    lo, hi = min(lo, hi), max(lo, hi)
    q = (hi - lo) / 4.0
    k = min(3, max(0, int((entry - lo) // q))) if q > 0 else 0
    qlo, qhi = lo + k * q, lo + (k + 1) * q
    eq = (qlo + qhi) / 2
    if entry >= eq or not keep:
        return None
    final = keep[-1][0]
    S = _S()
    cands = []
    for row in cf.opposing_ext(_TP().now_ts(ctx, i), sd.x(entry), sd.sign, ("1h", "4h"), (0, 1, 2, 3)):
        near, _ = _TP()._zone_edges(sd, row)
        if eq < near and S._exit_px(near, "array", p) < final - 1e-9 and S._exit_px(near, "array", p) - entry >= p.min_rr * risk:
            cands.append(near)
    if not cands:
        return None
    v = float(S._exit_px(min(cands), "array", p))
    rest = [x for x in keep if x[0] > v + p.es_pt and raw_of(x[0], x[1], p) > eq]
    hit("subrange_first")
    new = [(v, "array")] + rest
    return new, None


def eq60_insert(ctx, sd, i: int, p, entry: float, keep: list, fr):
    """X3-partial-60m-eq (cc08_007 ~17:13): the 60m dealing range (the last confirmed 60m pivot low below / high above the price) - its EQ between the entry and the final level is an
    'array' rung (exit_before_pts short) taking eq60_frac from rung 1's share. Returns (keep, fr) or None."""
    br = p60_bracket(ctx, sd, i)
    if br is None or not keep:
        return None
    S = _S()
    eq = (br[0] + br[1]) / 2
    v = float(S._exit_px(eq, "array", p))
    if not entry < v < keep[-1][0] - p.es_pt or any(abs(v - x[0]) <= p.es_pt for x in keep):
        return None
    f = list(base_fr(p, keep, fr))
    new = sorted(keep + [(v, "array")])
    j = new.index((v, "array"))
    take = min(p.eq60_frac, f[0])
    f.insert(j, take)
    f[0 if j != 0 else 1] -= take
    hit("eq60_rung")
    return new, f


def void_ladder_cut(ctx, sd, i: int, p, entry: float, keep: list, fr, st: dict):
    """X3-scale-through-void (cc01_006 ~24:21): a void used as the draw (its near edge or CE is the final rung) expands into three rungs near edge / CE / far edge - exit_before_pts,
    each 1/3 of the share the void rungs held. The void is the A10 void (levels.voids) or a one-sided leg, not the CC one-sided range of A10's note. Returns (keep, fr) or None."""
    if not keep:
        return None
    S = _S()
    raw = raw_of(keep[-1][0], keep[-1][1], p)
    tol = p.es_pt * 0.5
    z = next((z for z in void_registry(ctx, sd, i, p, entry) if any(abs(raw - e) <= tol for e in z)), None)
    if z is None:
        return None
    outs = [(float(S._exit_px(e, "array", p)), "array") for e in z]
    f = list(base_fr(p, keep, fr))
    mine = [k for k, x in enumerate(keep) if x[1] not in POOLK and any(abs(raw_of(x[0], x[1], p) - e) <= tol for e in z)]
    share = sum(f[k] for k in mine) or f[-1]
    head = [(x, f[k]) for k, x in enumerate(keep) if k not in mine]
    new = head + [(r, share / 3.0) for r in outs]
    new.sort(key=lambda t: t[0][0])
    hit("void_ladder")
    return [x for x, _ in new], [w for _, w in new]


def runner_htf_cut(ctx, sd, i: int, p, entry: float, keep: list, fr, d4: dict):
    """X3-runner-htf-target (099 ~37:57; cc02_003 ~3:26): the final rung is the nearest 60m-or-higher pool beyond the last execution-timeframe rung, at v + runner_htf_pts, with the
    runner share (runner_frac, else 0.2); the stop of the runner moves to the previous rung after it filled (management); runner_htf_steps: the intermediate 15m pools are extra rungs taking
    half of the runner between them. Returns (keep, fr) or None."""
    S = _S()
    hit("eval_runner_htf")
    pools = tf_pools(ctx, sd, i, entry)
    htf = [(v, r) for v, r in pools if r >= 60]
    if not htf or not keep:
        return None
    match = lambda x: any(abs(raw_of(x[0], x[1], p) - v) <= p.es_pt * 0.5 + 1e-9 for v, _ in pools if _ >= 15)
    exec_r = [x for x in keep if not match(x)]
    last_exec = max([x[0] for x in exec_r], default=entry)
    cands = [(v, r) for v, r in htf if S._exit_px(v, "pool", p) > last_exec + p.es_pt]
    if not cands:
        return None
    v, _ = min(cands)
    mid = [S._exit_px(w, "pool", p) for w, r in pools if r == 15 and last_exec + p.es_pt < S._exit_px(w, "pool", p) < v - p.es_pt] if p.runner_htf_steps else []
    final = (float(v + p.runner_htf_pts * p.es_pt), "fixed")
    R = p.runner_frac if p.runner_frac > 0 else 0.2
    head = [x for x in keep if x[0] <= last_exec + 1e-9]
    if not head:
        return None
    f_all = base_fr(p, keep, fr)
    f_head = norm(f_all[:len(head)])
    if mid:
        tail_f = [R / 2.0 / len(mid)] * len(mid) + [R / 2.0]
        rungs = head + [(float(m), "pool") for m in mid] + [final]
    else:
        tail_f = [R]
        rungs = head + [final]
    d4["runner_k"] = len(head)
    hit("runner_htf")
    return rungs, [f * (1.0 - R) for f in f_head] + tail_f


def confluence_cut(ctx, sd, sw, i: int, p, entry: float, leg_hi: float, keep: list, fr, st: dict):
    """X3-scaleout-skip-and-confluence (cc08_007 ~19:41): score each rung (conf_score), shares in proportion to share x (1 + score); confluence_only drops the score-0 rungs except the
    final one. Returns (keep, fr) or None when no rung scores."""
    ext = float(sw["ext"])
    hit("eval_confluence")
    sc = [conf_score(ctx, sd, i, p, entry, ext, float(leg_hi), x[0], st) for x in keep]
    if not any(sc):
        return None
    f = base_fr(p, keep, fr)
    if p.confluence_only:
        idx = [k for k in range(len(keep)) if sc[k] > 0 or k == len(keep) - 1]
        keep, f, sc = [keep[k] for k in idx], [f[k] for k in idx], [sc[k] for k in idx]
    hit("confluence_weight")
    return keep, norm([a * (1 + b) for a, b in zip(f, sc)])


def capture_cut(p, entry: float, keep: list, fr, d4: dict):
    """X3-best-case-80-85-capture (013 ~30:23): the last capture_n rungs become equal rungs at avg + f x (B - avg) for f in linspace(0.85, 1.0, capture_n), B = the final level; the
    share of the replaced rungs is split equally between the new ones. Returns (keep, fr) or None."""
    hit("eval_capture_zone")
    if not keep:
        return None
    n = int(p.capture_n)
    B = float(keep[-1][0])
    if B - entry <= p.es_pt:
        return None
    m = min(n, len(keep))
    f = list(base_fr(p, keep, fr))
    share = sum(f[-m:])
    fs = np.linspace(0.85, 1.0, n) if n > 1 else np.array([1.0])
    new = [(float(entry + x * (B - entry)), "fixed") for x in fs]
    new[-1] = (B, keep[-1][1])
    head, hf = keep[:-m], f[:-m]
    head = [(v, k) for v, k in head if v < new[0][0] - p.es_pt]
    hf = hf[:len(head)]
    d4["capture_B"] = B
    hit("capture_zone")
    return head + new, hf + [share / n] * n


def collapse_runner(ctx, sd, sw, i: int, p, keep: list, fr):
    """X3-layered-pool-ladder-runner (cc04_003 ~30:19): when the move from the sweep extreme to the first pool already exceeds collapse_adr_frac x ADR5 the first pool takes ALL the units
    [our interpretation]; otherwise the last rung keeps runner_frac (a small runner to the farthest pool). Returns (keep, fr) or None."""
    pool = next((x for x in keep if x[1] in POOLK), None)
    adr = _adr(ctx)
    if p.collapse_adr_frac > 0 and pool is not None and adr:
        if raw_of(pool[0], pool[1], p) - float(sw["ext"]) > p.collapse_adr_frac * adr:
            hit("pool_collapse")
            return [pool], [1.0]
    if p.runner_frac > 0 and len(keep) >= 2:
        hit("runner_frac")
        return keep, scale_head(base_fr(p, keep, fr), len(keep) - 1, [p.runner_frac])
    return None


def late(ctx, sd, sw, i: int, p, session: str, entry: float, risk: float, keep: list, keep_full: list, draw: float, final_T: bool, lvt: list, tags: dict,
         st: dict, locked: bool, fixed, leg_hi: float, tg=None) -> tuple:
    """The ladder stage after tp3.late (strategy._finish_order). Returns (reject reason or None, keep, draw, final_T). Order: the month gate (22), the void re-arm gate (147), the
    PM 14:50 ladder (6), the structural cuts (140 / 71 / 80 / 84 / 147), the whole-ladder shape (28 / 66 / 65 / 59), the modifiers (125 / 61 / 60 / 56 / 63 / 48 / 51 / 62 / 47 / 46),
    the report fields and the minimum final reward (126 / 70)."""
    es = p.es_pt
    hit("eval_late4")
    d4 = tags.setdefault("tp4", {})
    if not keep:
        return None, keep, draw, final_T
    if tg is not None and p.tgif_exits == "066":           # M14-tgif-management (066 ~48:02): the zone levels L20 .. L30 for the stop roll and the last-hour cover (the rungs are targets.plan's)
        d4["tgif066"] = [float(v) for v in tg["levels"]]
    if tg is not None and p.tgif_reentry_pm and not tg.get("held", True) and p.sb_windows[1][0] <= ctx.t[i] < p.sb_windows[1][1]:
        hit("tgif_week_broken")
        return "x_tgif_week_broken", keep, draw, final_T            # M14-tgif-management (066 ~45:47): the PM-window entries need the week's extreme to hold
    # --- gates
    if p.void_rearm:
        vr = (getattr(ctx, "state7", None) or {}).get("void_rearm")
        if vr and vr.get("session") == session:
            if str(sw.get("name", "")) != vr.get("swept") or sd.sign != vr.get("sign"):
                return "x_void_rearm_other", keep, draw, final_T
            lvt.append("void_rearm")
            hit("void_rearm_order")
    scalp = bool(tags.get("single_exit")) or fixed is not None or (bool(tags.get("fracs")) and not tags.get("tp3_ladder"))
    if scalp:
        fin_s = float(keep[-1][0])
        if p.t1_fixed_all and (p.t1_fixed_pts > 0 or p.t1_fixed_r > 0):
            fin_s = min(fin_s, entry + (p.t1_fixed_r * risk if p.t1_fixed_r > 0 else p.t1_fixed_pts * es))      # strategy applies the fixed single target after this stage
        elif tags.get("single_exit") or final_T or locked:
            fin_s = float(draw)
        d4.setdefault("final", fin_s)
        return final_gates(ctx, p, entry, risk, fin_s, lvt, d4), keep, draw, final_T
    fr = list(tags["fracs"]) if (tags.get("tp3_ladder") and tags.get("fracs")) else None
    keep = list(keep)
    # --- the PM 14:50 ladder replaces the ladder
    if p.m1450_targets and session == "PM" and 890 <= ctx.t[i] < 910:
        why, rs = m1450_ladder(ctx, sd, sw, i, p, entry, risk, leg_hi, tg)
        if why:
            return why, keep, draw, final_T
        if rs and not locked:
            keep, fr = rs, None
            draw = keep[-1][0]
            lvt.append("m1450")
    if p.lrlr_zone:
        why = lrlr_zone_gate(ctx, sd, sw, i, p, entry)
        if why:
            return why, keep, draw, final_T
    # --- structural cuts (not under a locked draw: the lock is one exact target)
    if p.tf_target_cap:
        k2 = tf_cap(ctx, p, entry, keep if not locked else keep[:1])       # review fix: T1 beyond the cap is rejected under a locked draw too; the ladder is cut only when free
        if k2 is None:
            return "x_tf_cap", keep, draw, final_T
        if k2 != keep and not locked:
            keep, fr = k2, None
            lvt.append("tf_cap")
    if p.same_range_t1 and not locked:
        k2 = range_session_t1(ctx, sd, sw, i, p, entry, risk, keep)
        if k2 is not None:
            keep, fr = k2, None
            lvt.append("same_range_t1")
    if p.lrlr_ceiling and not locked:
        why, k2 = lrlr_cap(ctx, sd, sw, i, p, entry, risk, keep, lvt)
        if why:
            return why, keep, draw, final_T
        if k2 != keep:
            keep, fr = k2, None
    consol_done = False
    if p.consol_eq_target and not locked:
        r = consol_eq_cut(ctx, sd, sw, i, p, session, entry, risk, keep)
        if r is not None:
            keep, fr = r
            consol_done = True
            lvt.append("consol_eq_target")
    if p.void_draw:
        v_ = void_pick(ctx, sd, i, p, entry, risk)
        if v_ is not None and not locked:
            keep, fr = [x for x in keep if x[0] < v_ - es] + [(v_, "array")], None
            lvt.append("void_draw")
            hit("void_draw")
        elif v_ is not None and v_ < draw - es:               # review fix (owner question 8): a nearer unfilled void replaces the LOCKED draw as the lock-side final target
            keep, fr, draw = [x for x in keep if x[0] < v_ - es] + [(v_, "array")], None, float(v_)
            lvt.append("void_draw")
            lvt.append("void_draw_lock")
            hit("void_draw")
            hit("void_draw_lock")
    # --- whole-ladder shapes (at most one is on)
    if p.ladder_kind == "half_3r":
        keep, fr = half_3r(ctx, sd, i, p, entry, risk, keep, draw, final_T or locked, st)
        lvt.append("ladder_half_3r")
    elif p.fulcrum_exit and not locked:
        r = fulcrum_ladder(ctx, sd, sw, i, p, session, entry, risk, leg_hi)
        if r is not None:
            keep, fr, trail = r
            lvt.append("fulcrum_trail" if trail else "fulcrum_ladder")
            if trail:
                d4["fulcrum_trail"] = True
    elif p.mm_first > 0 and not locked:
        r = mm_first_ladder(ctx, sd, i, p, session, entry, risk, keep)
        if r is not None:
            keep, fr = r
            lvt.append("mm_first")
    elif p.partial_trigger:
        keep, fr, be_at = r_ladder_rungs(p, entry, risk, keep, fr)
        if be_at is not None:
            tags["be_at"] = be_at
        lvt.append("r_ladder")
    # --- modifiers
    no_run = False
    if p.consol_no_runner and b17_consolidation(ctx, p):
        keep, fr = consol_no_runner_cut(ctx, sd, i, p, entry, keep, locked or final_T)
        no_run = True
        lvt.append("consol_no_runner")
        hit("consol_no_runner")
    if p.subrange_first and not locked:
        r = subrange_cut(ctx, sd, i, p, entry, risk, keep, fr)
        if r is not None:
            keep, fr = r
            lvt.append("subrange_first")
    if p.eq60_rung:
        r = eq60_insert(ctx, sd, i, p, entry, keep, fr)
        if r is not None:
            keep, fr = r
            lvt.append("eq60_rung")
    if p.gap_speed_bump_partial > 0:
        b = bump_rung(ctx, sd, i, p, entry, keep)
        if b is not None and not any(abs(b - x[0]) <= es for x in keep):
            f0 = list(base_fr(p, keep, fr))
            keep = sorted(keep + [(b, "speed")])
            j = keep.index((b, "speed"))
            f0.insert(j, 0.0)
            fr = [f * (1.0 - p.gap_speed_bump_partial) for f in f0]
            fr[j] = p.gap_speed_bump_partial
            lvt.append("gap_speed_bump")
    if p.void_ladder:
        r = void_ladder_cut(ctx, sd, i, p, entry, keep, fr, st)
        if r is not None:
            keep, fr = r
            lvt.append("void_ladder")
    if p.runner_at_half and not locked and len(keep) >= 2:
        hit("eval_runner_at_half")
        cand = entry + 0.5 * (keep[-1][0] - entry)
        d4["final"] = float(keep[-1][0])
        if cand > keep[-2][0] + 1e-9:
            keep = keep[:-1] + [(float(cand), "fixed")]
            lvt.append("runner_at_half")
            hit("runner_at_half")
    if p.runner_htf and not locked and not no_run:
        r = runner_htf_cut(ctx, sd, i, p, entry, keep, fr, d4)
        if r is not None:
            keep, fr = r
            lvt.append("runner_htf")
    if p.confluence_weight:
        r = confluence_cut(ctx, sd, sw, i, p, entry, leg_hi, keep, fr, st)
        if r is not None:
            keep, fr = r
            lvt.append("confluence_weight")
    if p.capture_zone and not locked:
        r = capture_cut(p, entry, keep, fr, d4)
        if r is not None:
            keep, fr = r
            lvt.append("capture_zone")
    if (p.collapse_adr_frac > 0 or p.runner_frac > 0) and not no_run and not locked and not d4.get("runner_k") and not consol_done:
        r = collapse_runner(ctx, sd, sw, i, p, keep, fr)
        if r is not None:
            keep, fr = r
            lvt.append("collapse_runner")
    if p.strength_hold:
        d4["strength"] = True
    # --- the shares, the report fields and the minimum final reward
    if fr is None and tags.get("tp3_ladder") and tags.get("fracs") and len(tags["fracs"]) != len(keep):
        fr = base_fr(p, keep, None)                 # a cut changed the ladder tp3.late had shared out: the built shares for the new rungs
    if fr is not None:
        keep, fr = prune(keep, fr)
        if len(fr) != len(keep):
            fr = norm(list(fr[:len(keep)]) + [0.0] * (len(keep) - len(fr)))
        tags["fracs"] = tuple(fr)
        tags["tp3_ladder"] = True
    if not (final_T or locked):
        draw = keep[-1][0]
    fin = draw if (final_T or locked) else keep[-1][0]
    d4.setdefault("final", float(fin))
    why = final_gates(ctx, p, entry, risk, float(fin), lvt, d4)
    if why:
        return why, keep, draw, final_T
    if d4.get("tgif066") and len(d4["tgif066"]) > 2 and keep:
        dd = [abs(v - d4["tgif066"][2]) for v, _ in keep]
        if min(dd) <= 3.0 * es:
            d4["tgif_l25_k"] = int(np.argmin(dd))          # the index of the L25 rung in the placed ladder (manage matches it by index)
    if st.get("conf_pools") and any(abs(v - c) <= es for c in st["conf_pools"] for v, _ in keep):
        lvt.append("proj_confirms_pool")
    return None, keep, draw, final_T


# --- 6. the weekly / monthly state (backtest.run) --------------------------------------------------------------------------------------------------

def stage_for(rows: list, day, p) -> tuple:
    """OT-target-progression (099 ~40:55): (stage index, consecutive non-negative weeks) before `day` from the closed trade rows. The weeks are the completed ISO weeks with at least one
    trade [our interpretation: a week without a trade neither confirms nor breaks the run]; stage_weeks (4) non-negative weeks in a row step the stage up (capped at the last, the count
    restarts), a negative week resets the count (and with stage_drop steps one stage back). The stage never touches the risk or the size (E8 / E11 stay as set)."""
    wk = day.isocalendar()[:2]
    net: dict = {}
    for r in rows:
        d = r["date"]
        k = d.isocalendar()[:2]
        if d < day and k < wk:
            net[k] = net.get(k, 0.0) + float(r["net"])
    last = len(p.stage_targets) - 1
    stage = streak = 0
    for k in sorted(net):
        if net[k] >= 0:
            streak += 1
            if streak >= p.stage_weeks:
                stage, streak = min(stage + 1, last), 0
        else:
            streak = 0
            if p.stage_drop:
                stage = max(0, stage - 1)
    return stage, streak


def stage_params(rows: list, day, p):
    """The day's Params with the staged fixed target (t1_fixed_pts) - or p unchanged when target_stage is off."""
    if not p.target_stage:
        return p
    st, _ = stage_for(rows, day, p)
    hit("target_stage")
    return replace(p, t1_fixed_pts=float(p.stage_targets[st]))


def month_big(rows: list, day, p) -> int:
    """new-rr-month-gate (cc02_001 ~12:11): the trades of this calendar month (before `day`) whose realised R reached rr_big."""
    return sum(1 for r in rows if r["date"] < day and (r["date"].year, r["date"].month) == (day.year, day.month) and float(r.get("R", 0.0)) >= p.rr_big)


# --- 7. mid-trade management and the report ---------------------------------------------------------------------------------------------------------

def ob1_body(ctx, sd, o: dict, i: int, fill: float):
    """new-strength-no-return-discount-array (105 ~17:00): OB1 = the nearest bullish order block's BODY (down-close candle: close .. open) below the fill, from the closed bars between the
    sweep extreme and the fill bar. (bottom, top) or None. [our interpretation: the spec's `levels.order_block` (the post-fill pullback / entry OB) is replaced by this simple nearest down-close
    candle]"""
    e = int(o.get("ext_i", ctx.start))
    for k in range(i - 1, max(ctx.start, e) - 1, -1):
        if sd.c[k] < sd.o[k] and sd.o[k] <= fill + 1e-9:
            return float(sd.c[k]), float(sd.o[k])
    return None


def on_fill(ctx, sd, pos: dict, tr, o: dict, i: int, p, fill: float) -> None:
    """Fill time: the state the mid-trade hook needs (runner stop, OB1, the TGIF 066 levels, the trail from the fill)."""
    d = dict(o.get("tp4") or {})
    d["fill_i"] = i
    if d.get("strength"):
        ob = ob1_body(ctx, sd, o, i, float(fill))
        hit("eval_strength")
        if ob is not None:
            d["ob1"] = ob
            d["hi0"] = float(max(o.get("leg_hi0", -np.inf), sd.h[int(o.get("ext_i", i)):max(i, int(o.get("ext_i", i)) + 1)].max()))     # the CLOSED bars before the fill bar (review fix)
        else:
            d.pop("strength", None)
    if p.ob_target_tod:
        d["ob_tod"] = True
    if d.get("fulcrum_trail"):
        pos["trail_now"] = True
    if p.void_rearm and "void_rearm" in (tr.lv_tags or ""):
        (getattr(ctx, "state7", None) or {}).pop("void_rearm", None)
    tr.rr_final = d.get("rr_final")
    if p.target_stage:
        tr.stage_pts = float(p.t1_fixed_pts)
    pos["tp4"] = d


def ob_skip(pos: dict, k: int, t: int, tf: int, p) -> bool:
    """A12-opposing-ob-time-of-day (cc04_003 ~34:17), ladder loop: a touched OB rung outside the profit-taking windows is skipped (no fill); its share moves to the next rung. True = skipped."""
    d = pos.get("tp4")
    kinds = pos.get("level_kinds") or []
    if not d or not d.get("ob_tod") or k >= len(kinds) or kinds[k] != "ob":
        return False
    hit("eval_ob_tod")
    if any(a <= t < b for a, b in p.ob_pt_windows):
        return False
    fr = list(pos["fracs"])
    if k + 1 >= len(fr):
        hit("ob_tod_last_kept")             # review fix: the LAST rung has no next rung to take its share - it is never skipped (the units would sit open until the stop / session end)
        return False
    fr[k + 1] += fr[k]
    fr[k] = 0.0
    pos["fracs"] = tuple(fr)
    hit("ob_tod_skip")
    return True


def manage(ctx, sd, pos: dict, tr, i: int, ts, p) -> None:
    """Mid-trade (bar i closed): the runner's stop to the previous rung once it filled (51), the strength read of OB1 (106), the TGIF 066 stop roll and last-hour cover (75)."""
    from . import manage as MG
    d = pos.get("tp4")
    if not d or not pos["left"]:
        return
    lv = pos["levels"]
    rk = d.get("runner_k")
    from .me1 import trail_ok as _trail_ok
    if rk and pos["k"] >= rk and rk >= 1 and _trail_ok(pos):
        MG.raise_stop(pos, float(lv[rk - 1]) - p.pad, trail=True)             # X3-runner-htf-target: "move its stop to a profitable level" - just under the rung that filled
        if not d.get("runner_stop"):
            d["runner_stop"] = True
            hit("runner_stop")
    if d.get("ob1") is not None and "strength_state" not in d and i > pos["fill_i"]:
        bot, top = d["ob1"]
        if sd.l[i] <= top:
            d["strength_state"] = "normal"                         # the pullback traded into OB1's body: the narrative stands, normal partials
            tr.strength = "normal"
        elif sd.h[i] > d["hi0"]:
            d["strength_state"] = "strong"
            tr.strength = "strong"
            drop_array_rungs(pos)
            hit("strength_hold")
    t066 = d.get("tgif066")
    if t066 and pos["left"]:
        hit("eval_tgif066")
        k25 = d.get("tgif_l25_k")                              # review fix: the L25 rung is matched by its INDEX in the placed ladder (set in late), not by its price
        if k25 is not None and not d.get("tgif_roll") and pos["k"] > k25 and _trail_ok(pos):
            q = [x for x in sd.pl if x.known <= i and x.i > pos["fill_i"] and x.price < sd.c[i]]      # the latest swing formed AFTER the fill
            if q:
                MG.raise_stop(pos, float(q[-1].price) - p.tick, trail=True)     # the "tgif_roll": the stop to the latest swing (side space: the swing low of a short's swing high)
                d["tgif_roll"] = True
                hit("tgif_roll")
        if p.tgif_last_hour_cover and not d.get("cover") and ctx.t[i] >= 900:
            band = (t066[0], t066[-1])
            q = [x for x in sd.ph if x.known <= i and x.i >= ctx.start and band[0] - 1e-9 <= x.price <= band[1] + 1e-9 and ctx.t[x.i] >= 900]
            if q:
                cover = float(q[-1].price - p.exit_before_pts * p.es_pt)
                k = pos["k"]
                if k < len(lv) and cover > sd.c[i]:
                    done_f = list(pos["fracs"][:k])
                    pos["levels"] = list(lv[:k]) + [cover]
                    pos["level_kinds"] = list((pos.get("level_kinds") or [])[:k]) + ["exact"]
                    pos["fracs"] = tuple(done_f + [max(0.0, 1.0 - sum(done_f))])
                    pos["final_T"] = False
                    d["cover"] = cover
                    hit("tgif_cover")


def drop_array_rungs(pos: dict) -> None:
    """new-strength-no-return-discount-array: the not yet taken non-pool rungs are dropped (their shares go to the pool rungs left, proportionally); with no pool rung left the last rung
    stays."""
    k = pos["k"]
    lv, kd, fr = list(pos["levels"]), list(pos.get("level_kinds") or []), list(pos["fracs"])
    if k >= len(lv) or len(kd) < len(lv):
        return
    keep = [j for j in range(k, len(lv)) if kd[j] in POOLK]
    if not keep:
        keep = [len(lv) - 1]
    gone = sum(fr[j] for j in range(k, len(lv)) if j not in keep)
    s = sum(fr[j] for j in keep) or 1.0
    new = {j: fr[j] + gone * fr[j] / s for j in keep}
    pos["levels"] = lv[:k] + [lv[j] for j in keep]
    pos["level_kinds"] = kd[:k] + [kd[j] for j in keep]
    pos["fracs"] = tuple(fr[:k] + [new[j] for j in keep])


def tgif_pm_slot(ctx, p, session: str, t: int) -> bool:
    """M14-tgif-management (066 ~45:47): on a TGIF day the PM Silver-Bullet window (sb_windows[1]) accepts one more TGIF entry after the first trade."""
    if not p.tgif_reentry_pm or session != "PM":
        return False
    a, b = p.sb_windows[1]
    ok = bool(a <= t < b and ctx.day.weekday() == 4 and any(x.startswith("tgif") for x in day_tag_set(ctx)))
    if ok:
        hit("tgif_pm_slot")
    return ok


def after_close(ctx, pos, tr, lost, done: dict, key: str, state: dict, p) -> None:
    """new-sellstop-run-before-void-fill (cc04_010 ~8:07): a stopped-out void_draw trade re-arms its session ONCE; the next order must sweep the same lows again (same swept pool, same
    side). The gate is in late()."""
    if (p.void_rearm and lost is not None and "void_draw" in (tr.lv_tags or "") and tr.exits and tr.exits[-1][3] in ("stop", "stop_gap")
            and not state.get("void_rearmed")):
        state["void_rearmed"] = True
        state["void_rearm"] = dict(session=tr.session, swept=tr.swept, sign=1 if tr.side == "long" else -1)
        done[key] = False
        hit("void_rearm")


def close_note(pos: dict, tr, p) -> None:
    """The report fields of the closed trade: half_range_ok (the runner exit reached half the range to the final level), capture_b (the realised average exit distance / the distance to
    the capture zone's best case B), rr_final (set at the fill)."""
    d = pos.get("tp4")
    if not d or not tr.exits:
        return
    s = pos["side"].sign
    n_in = tr.shares + sum(q for *_, q in tr.adds)
    avg_in = (tr.entry * tr.shares + sum(px * q for _, px, q in tr.adds)) / max(n_in, 1)
    q_out = sum(q for _, _, q, _ in tr.exits)
    avg_out = sum(px * q for _, px, q, _ in tr.exits) / max(q_out, 1)
    fin = d.get("final")
    if fin is not None:
        F = pos["side"].x(float(fin))
        tr.half_range_ok = bool(s * (tr.exits[-1][1] - avg_in) >= 0.5 * s * (F - avg_in) - 1e-9)
    B = d.get("capture_B")
    if B is not None:
        den = s * (pos["side"].x(float(B)) - avg_in)
        tr.capture_b = round(float(s * (avg_out - avg_in) / den), 4) if den > 0 else None
    if d.get("strength_state"):
        tr.strength = d["strength_state"]
