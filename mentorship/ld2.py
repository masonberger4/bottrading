"""Caption-gap pass (digests/rulebook_gaps/*.md), package levels_detectors: the engine glue.

The detectors themselves live in levels.py (pure arrays in, zones out); this module wires them into the
bar-by-bar engine (strategy.py hooks) behind Params switches, all default off (see the "caption-gap pass,
levels_detectors #1/3" block of Params). Conventions as everywhere: side space (shorts run mirrored prices),
a bar is used only after it closes, an object only from the bar that completes it.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import levels as L

NY = "America/New_York"


def _S():
    from . import strategy as S
    return S


# --- B21 IPDA anchor ------------------------------------------------------------------------------------------------

def ipda_windows(ctx, p, dates: list) -> tuple[dict, object]:
    """X3-b21-ipda-anchor (cc05_001 ~53:44 / ~23:23 / ~26:56): the 20 / 40 / 60 session windows (high, low) and the date of
    the last session they include. "rolling" ends on yesterday (the first build); "month" ends on the session before the
    first trading day of the last closed calendar month; "swing" ends on the last daily MSS (L.daily_mss_end). A window
    the history cannot fill is left out.
    Caption-gap levels_detectors #3/3: the windows are Params.ipda_windows (20, 40, 60 and the 3 / 6 / 12-month 63, 126, 252 - cc05_002 ~2:41);
    "current_month" (B21-anchor-month-vs-daily, cc05_004 ~16:04: "we keep moving that basis forward each new month") ends them ON the first trading
    day of the CURRENT month, fixed until the next month (on that day itself, which is not complete, they end yesterday). Also stored: ctx.ipda_end
    (the number of sessions up to the window end) and ctx.ipda_D (the anchor session of the forward intervals, None for "rolling")."""
    days = ctx.ipda_days
    end = len(days)
    ctx.ipda_D = None
    if p.ipda_anchor == "month":
        k = L.ipda_month_end(dates, ctx.day)
        end = k if k is not None else 0
        ctx.ipda_D = k
    elif p.ipda_anchor == "current_month":
        k = next((j for j, d in enumerate(dates) if (d.year, d.month) == (ctx.day.year, ctx.day.month)), None)
        if k is not None and k > 0 and (dates[k - 1].year, dates[k - 1].month) != (ctx.day.year, ctx.day.month):
            end = k + 1
            ctx.ipda_D = k
        elif k is None:                                # today is the month's first trading day: no completed session of this month yet
            end = len(days)
        else:
            end = 0                                    # the history does not reach the month's first day
    elif p.ipda_anchor == "swing" and days:
        h = np.array([d[0] for d in days], float)
        l = np.array([d[1] for d in days], float)
        c = np.array([float(x.close.iloc[-1]) for x in ctx.hist[-len(days):]], float)
        k = L.daily_mss_end(h, l, c)
        end = (k + 1) if k is not None else 0
        ctx.ipda_D = k
    if p.ipda_forward and ctx.ipda_D is not None and end == ctx.ipda_D + 1:
        end = ctx.ipda_D          # review fix (B21-open-float-forward-windows: "back pools = highs/lows BEFORE D"): the forward intervals start AT D, so the back windows end the session before it - as "month" always did
    ctx.ipda_end = end
    out = {}
    for n in sorted(p.ipda_windows):
        if 0 < n <= end:
            seg = days[end - n:end]
            out[n] = (max(x[0] for x in seg), min(x[1] for x in seg))
    last = dates[end - 1] if 0 < end <= len(dates) else None
    return out, last


# --- B5 pool timeframe ------------------------------------------------------------------------------------------------

def attach_pool_tf(ctx, sides, p) -> None:
    """X3-b5-15m-pools-5m-gaps (cc05_003 ~1:27:21): with pool_tf > the base bars the intraday SWING pools (pool_swings,
    relative equal highs / lows) come from the pivots of the pool_tf-minute bars, each mapped to the base bar holding the
    extreme (L.tf_pivots: known only once the confirming bucket is complete)."""
    m = p.pool_tf
    if m <= ctx.tf or m % ctx.tf:
        return
    for sd in sides:
        sd.pool_piv = L.tf_pivots(ctx.idx, sd.h, sd.l, ctx.tf, m, sd.n)


def pool_piv(sd, lows: bool) -> list:
    """The swing pivots the pools are made of (side space): the base bars' pivots, or the pool_tf ones."""
    pp = getattr(sd, "pool_piv", None)
    if pp is None:
        return sd.pl if lows else sd.ph
    return pp[1] if lows else pp[0]


# --- A3 diagonal pools ----------------------------------------------------------------------------------------------

def diag_level(ctx, sd, i: int, p) -> float | None:
    """A3-diagonal-support-is-liquidity (045 ~26:02): the extrapolated line of a smooth run of higher lows, as a sweep pool
    (side space), when it is still untaken (no later low went below the line) and under the last close."""
    tol = p.eq_tol_pts * p.es_pt
    lows = [(q.i, q.price) for q in pool_piv(sd, True) if q.known <= i - 1 and q.i >= ctx.start - 1][-8:]
    r = L.diagonal_lows(lows, tol, i, p.diag_min_swings)
    if r is None:
        return None
    level, slope, _ = r
    x_last = lows[-1][0]
    ks = np.arange(x_last + 1, i)
    if len(ks) and (sd.l[ks] < level + slope * (ks - i) - 1e-9).any():
        return None
    if not level < sd.c[i - 1]:
        return None
    return float(level)


# --- N8 consolidation pools -----------------------------------------------------------------------------------------

def consol_pool(ctx, sd, i: int, buy: bool, p=None):
    """N8-consolidation-builds-orders (cc01_002 ~17:28): once the chop test has RELEASED (a close beyond its range, known at
    that bar's close), the range's high / low are pools. (level, created_bar) in side space: buy=True the buy-side one (a
    long's target), else the sell-side one (a sweep pool); None before the release.
    Caption-gap A21-consolidation-range-def (levels_detectors #2/3; cc01_001 ~11:50 / ~17:54: "defined specifically by the bodies of the candles
    not the wicks"): with Params.consol_body_range the range is the max / min BODY of the bars up to the moment the chop test switched on
    (levels.consolidation_box) and it must pass ICT's check - the EQ touched from both sides consol_eq_touches times - else it is no
    consolidation (None)."""
    ch = getattr(ctx, "chop", None)
    if ch is None or getattr(ch, "rel_i", None) is None or ch.rel_i >= i or ch.hi is None:
        return None
    hi, lo = ch.hi, ch.lo
    if p is not None and p.consol_body_range and getattr(ch, "on_at", None) is not None:
        a, b = ctx.start, int(ch.on_at)
        box = L.consolidation_box(ctx.o[a:b + 1], ctx.h[a:b + 1], ctx.l[a:b + 1], ctx.c[a:b + 1], True, p.consol_eq_touches)
        if not box["valid"]:
            return None
        hi, lo = box["high"], box["low"]
    real = (hi if sd.sign > 0 else lo) if buy else (lo if sd.sign > 0 else hi)
    return float(sd.x(real)), ch.rel_i + 1


# --- L8 vacuum-block context ----------------------------------------------------------------------------------------

def vb_valid(ctx, p, near: float, far: float, i: int | None = None) -> bool:
    """X3-l8-vb-exhaustion-gap: True when the vacuum block (open `near`, last close `far`; real prices) is in context
    (levels.vb_context). The bias clause reads the htf-table row known at closed bar `i` (bias_day.row_for: before 09:30 the table
    cut at the session's lock, never the 09:30 one); no row known / htf_bias off = the bias clause is skipped. The exhaustion
    clause compares the last close with the 20 sessions BEFORE it (the last close's own session is not in that range)."""
    from . import bias_day as BD
    want = None
    if p.htf_bias != "off" and i is not None:
        row = BD.row_for(ctx, "", i)
        want = None if row is None else BD.bias_value(row, p)
    cache = ctx.__dict__.setdefault("_vb_ctx", {})
    key = (round(float(near), 6), round(float(far), 6), want)
    if key not in cache:
        hist = getattr(ctx, "hist", [])
        closes = [float(x.close.iloc[-1]) for x in hist[-21:]]
        alld = list(getattr(ctx, "ipda_days", []))
        days = alld[-20:]
        prior = alld[-21:-1]
        kind = "bull" if near > far else "bear"
        cache[key] = L.vb_context(kind, near, far, closes, [d[0] for d in days], [d[1] for d in days], want,
                                  ex_highs=[d[0] for d in prior], ex_lows=[d[1] for d in prior])
    return cache[key] == "valid"


def vb_tags(ctx) -> list:
    return ["vb_exhaustion"] if any(v == "exhaustion" for v in getattr(ctx, "_vb_ctx", {}).values()) else []


# --- side-space arrays shared by several switches -------------------------------------------------------------------

def side_obs(sd) -> list:
    """The blended OBs (both kinds, side space) that led to a displacement FVG - as htf._arrays / confluence._zones build them."""
    def build():
        out = []
        for z in L.fvgs(sd.h, sd.l, sd.o, sd.c, sd.c2_dir):
            ob = L.order_block_blend(sd.o, sd.h, sd.l, sd.c, z.i - 4, z.i - 2, z.kind)
            if ob is None:
                continue
            disp = sd.c[z.i - 1]
            if (z.kind == "bull" and disp > ob.top) or (z.kind == "bear" and disp < ob.bottom):
                out.append(L.Zone(z.kind, ob.top, ob.bottom, z.i, ob.src, ob.mt))
        return out
    return sd._lazy("ld_obs", build)


def htf_zones_side(ctx, sd, i: int, tfs=("15m", "30m", "1h", "4h", "D", "W")) -> list:
    """(lo, hi) of the pre-called HTF arrays that back this trade side (confluence rows valid at bar i's close), in side space."""
    cf = getattr(ctx, "conf", None)
    if cf is None:
        return []
    now = ctx.idx[i] + pd.Timedelta(minutes=ctx.tf)
    out = []
    for top, bot, _, _, _ in cf.valid(now, sd.sign, tfs, src=(0, 1, 3)):
        out.append((float(bot), float(top)) if sd.sign > 0 else (float(-top), float(-bot)))
    return out


# --- B10 top-down transposition ------------------------------------------------------------------------------------

def htf_target_tfs(p, htf_t: tuple) -> tuple:
    """X3-b10-topdown-transposition (cc06_003 ~20:01: "transpose those monthly levels over to your weekly chart"): the timeframes whose opposing
    arrays feed the target ladder. With `topdown_targets` the 4h, D, W and M arrays (the monthly arrays transposed to the weekly, the weekly to
    the daily, then to the 4h - all carried to the intraday chart by the confluence rows, each with its own `tf`) join `htf_t`; they enter the
    ladder in distance order with the other levels."""
    if not p.topdown_targets:
        return htf_t
    return tuple(htf_t) + tuple(x for x in ("4h", "D", "W", "M") if x not in htf_t)


# --- A12 OB pick -----------------------------------------------------------------------------------------------------

def ob_run(ctx, sd, sw, j: int, k: int, i: int, p):
    """A12-ob-candle-selection: the order block's candle range [j, k] of `_ob_at_low` re-picked by `ob_pick` (and
    `ob_skip_encapsulated`): returns (j, k, mt or None). Bullish terms (side space); "largest_body" uses the swept level as the
    HTF support S; "blend_in_htf" blends only when the whole run lies inside a pre-called HTF array."""
    o, h, l, c = sd.o, sd.h, sd.l, sd.c
    if p.ob_skip_encapsulated:
        while k - 1 >= j:
            bl, bh = min(o[k], c[k]), max(o[k], c[k])
            pl_, ph_ = min(o[k - 1], c[k - 1]), max(o[k - 1], c[k - 1])
            if bl >= pl_ and bh <= ph_ and (bh - bl) <= 0.5 * (ph_ - pl_):
                k -= 1
            else:
                break
    run = list(range(j, k + 1))
    if p.ob_pick == "original":
        m = max(run, key=lambda q: h[q])
        return m, m, None
    if p.ob_pick == "largest_body":
        s = sw.get("level")
        near = [q for q in run if s is not None and l[q] - abs(o[q] - c[q]) <= s <= h[q] + abs(o[q] - c[q])]
        cand = near or run
        m = min(cand, key=lambda q: (l[q], -abs(o[q] - c[q])))
        return m, m, None
    if p.ob_pick == "blend_in_htf":
        hi, lo = float(h[j:k + 1].max()), float(l[j:k + 1].min())
        if any(a <= lo and hi <= b for a, b in htf_zones_side(ctx, sd, i)):
            return j, k, float((l[j] + h[k]) / 2)
        return k, k, None
    return j, k, None


def ob_blend(ctx, sd, sw, i: int, p, a: int, b: int, g=None):
    """The blended bullish OB in [a, b] with the caption-gap A12 pick (`ob_pick`, `ob_skip_encapsulated`); "blend" without the skip is
    levels.order_block_blend exactly as before. Caption-gap A12-entry-ob-outside-fvg (065 ~4:04:05; Params.ob_outside_fvg): the candles inside the
    FVG / shaded zone - the entry gap `g`, else the displacement FVG after the sweep extreme - are ignored (levels_detectors #3/3)."""
    from . import ld4 as _L4
    outside = _L4.disp_fvg_zone(sd, sw, i, g) if p.ob_outside_fvg else None
    if p.ob_pick == "blend" and not p.ob_skip_encapsulated:
        return L.order_block_blend(sd.o, sd.h, sd.l, sd.c, a, b, "bull", outside=outside)
    zs = htf_zones_side(ctx, sd, i) if p.ob_pick == "blend_in_htf" else None
    return L.order_block_blend(sd.o, sd.h, sd.l, sd.c, a, b, "bull", p.ob_pick, sw.get("level"), p.ob_skip_encapsulated, zs, outside)


# --- A5 / A8 / A9 entry zones ----------------------------------------------------------------------------------------

def gap_open(sd, g, i: int, ctx, p) -> bool:
    """A5-caffeine-bar-bisi (006 ~12:34): a gap stays valid until a body closes below its bottom - except a gap tagged
    single_bar (its middle candle one large displacement candle), which is dead on ANY trade below its low (the c1 high). Not on
    NFP / FOMC days: the overshoot is expected there, so the close rule stays."""
    if p.single_bar_fvg_strict and g.tag == "single_bar":
        from claude_hf.daytypes import events
        if not (events(ctx.day) & {"jobs", "fomc"}):
            from . import ld4 as _L4
            if _L4.td_hold(ctx, sd, g, i, p):      # caption-gap new-time-distortion (a): bodies hold inside the gap - the wicks do not kill it
                return True
            return bool(sd.l[g.i + 1:i + 1].min(initial=np.inf) >= g.bottom)
    return bool(sd.c[g.i + 1:i + 1].min(initial=np.inf) >= g.bottom)


def reclaimed_zones(ctx, sd, sw, i: int, p) -> list:
    """A5-broken-fvg-reclaim (027 ~22:24; 091 ~20:18): the reclaimed bullish FVGs (levels.reclaimed_fvgs) formed after the sweep
    extreme, known by bar i, as entry gaps (Zone.i = the reclaim bar), when the bias is not against the trade and the zone sits in
    the discount of the leg (not in premium) [our interpretation]."""
    if getattr(ctx, "cur_bias", 0) == -sd.sign:
        return []
    zs = sd._lazy("ld_reclaim", lambda: L.reclaimed_fvgs(sd.h, sd.l, sd.c, sd.gaps))
    hi = float(sd.h[sw["ext_i"]:i + 1].max())
    eq = (sw["ext"] + hi) / 2
    return [z for z in zs if z.i <= i and z.src - 1 >= sw["ext_i"] and z.top <= eq]


def htf_entry_zones(ctx, sd, sw, i: int, p) -> list:
    """B5-htf-arrays-anchor-transpose (043 ~3:13; 072 ~1:45; 074 ~7:00; 080 ~11:28; cc04_012): the FVGs / OBs of the listed
    higher-timeframe bars (Side.zones_tf, built from those bars' own candles, known when the HTF candle closes) as FIXED entry
    zones on the lower chart: no lower-timeframe 3-candle gap is needed. The zone must sit between the sweep extreme and the last
    close (a limit under the market)."""
    out = []
    seen = set()
    for m in p.htf_entry_arrays:
        m = int(m)
        if m <= ctx.tf or m % ctx.tf:
            continue
        for z in sd.zones_tf(ctx.idx, ctx.tf, m):
            key = (round(float(z.top), 9), round(float(z.bottom), 9))
            if z.i <= i and key not in seen and sw["ext"] < z.top < sd.c[i]:
                seen.add(key)
                out.append(z)
    return out


def _gap_zones_real(ctx, p) -> list:
    """(lo, hi, known_from_bar, name) of the ORGs / NWOGs the frame can judge (real prices)."""
    S = _S()
    out = []
    kinds = set(p.inversions)
    if "org" in kinds:
        orgs = list(getattr(ctx, "org", []))
        today = bool(getattr(ctx, "org_today", False))
        k930 = S._idx_at(ctx, 570)
        for j, (a, b) in enumerate(orgs):
            is_today = today and j == len(orgs) - 1
            if is_today and k930 >= len(ctx.t):
                continue
            out.append((min(a, b), max(a, b), k930 if is_today else 0, "org"))
    if "nwog" in kinds:
        gl = getattr(ctx, "gaps", None)
        if gl is not None:
            nw = [(lo, hi, 0) for kind, hi, lo, ce in gl if kind in ("nwog", "nwog_rth")]   # (gap_views "both": the RTH weekend gap follows the NWOG rules)
        else:
            nw = [(min(a, b), max(a, b), 0) for a, b in getattr(ctx, "nwog_prev", [])]
            if getattr(ctx, "nwog_today", False) and getattr(ctx, "nwog", None):
                a, b = ctx.nwog[-1]
                nw.append((min(a, b), max(a, b), S._idx_at(ctx, 570)))
        out += [(lo, hi, k, "nwog") for lo, hi, k in nw if k < len(ctx.t)]
    return out


def _build_inv(ctx, sd, p) -> list:
    kinds = set(p.inversions)
    out = []
    if "ob" in kinds:
        out += L.inverted_arrays(sd.o, sd.h, sd.l, sd.c, side_obs(sd), "ob")
    if "breaker" in kinds:
        brk = L.breakers(sd.o, sd.h, sd.l, sd.c, max(p.pivot_n, 1), p.breaker_zone)
        out += L.inverted_arrays(sd.o, sd.h, sd.l, sd.c, brk, "breaker")
    if "vi" in kinds:
        out += L.inverted_arrays(sd.o, sd.h, sd.l, sd.c, list(sd.vis("bull")) + list(sd.vis("bear")), "vi")
    for lo, hi, k0, name in _gap_zones_real(ctx, p):
        c = ctx.c
        side0 = next((1 if c[q] >= hi else -1 if c[q] <= lo else 0 for q in range(k0, len(c))
                      if c[q] >= hi or c[q] <= lo), 0)
        if side0 == 0:
            continue
        j = next((q for q in range(k0, len(c)) if (c[q] < lo if side0 > 0 else c[q] > hi)), None)
        if j is None:
            continue
        role_real = "bear" if side0 > 0 else "bull"           # a body close below a zone price was above: resistance
        mt = (lo + hi) / 2
        if sd.sign > 0:
            z = L.Zone("inv_" + name, hi, lo, j, j, mt, tag=role_real, levels=(lo, mt, hi))
        else:
            z = L.Zone("inv_" + name, -lo, -hi, j, j, -mt, tag="bull" if role_real == "bear" else "bear",
                       levels=(-hi, -mt, -lo))
        out.append(z)
    return sorted(out, key=lambda z: z.i)


def inverted(ctx, sd, i: int, p, role: str) -> list:
    """A8-inversion-any-pd-array (090 ~2:11:45; 068 ~13:37): the inverted PD arrays (Params.inversions) known by bar i whose NEW
    role is `role` ("bull" = support, an entry array for a long; "bear" = resistance, targets above), in side space, each
    Zone(kind="inv_<array>", tag=role, levels=(lo, mt, hi)). A body close through the MT back the other way retires the new role."""
    zs = sd._lazy(("ld_inv", tuple(sorted(p.inversions))), lambda: _build_inv(ctx, sd, p))
    out = []
    for z in zs:
        if z.tag != role or z.i > i:
            continue
        seg = sd.c[z.i + 1:i + 1]
        mt = z.levels[1]
        if len(seg) and ((role == "bear" and seg.max() > mt) or (role == "bull" and seg.min() < mt)):
            continue
        out.append(z)
    return out


def inv_entry_zones(ctx, sd, sw, i: int, p) -> list:
    """Inverted arrays with the support role as entry gaps (like ifvg_entries): formed after the sweep extreme, under the market."""
    out = []
    for z in inverted(ctx, sd, i, p, "bull"):
        if z.i - 1 >= sw["ext_i"] and sw["ext"] < z.top < sd.c[i]:
            out.append(L.Zone("bull", z.top, z.bottom, z.i, z.src, z.mt, levels=z.levels, tag="inv"))
    return out


# --- confluence ---------------------------------------------------------------------------------------------------

def converge_n(ctx, sd, g, i: int, p) -> int:
    """confluence-stacked-arrays (100 ~6:05; 103 ~4:38 / ~25:04; 011 ~7:19): how many arrays converge on the entry gap `g` - OBs and
    VIs overlapping it, prior-day wick CEs inside it (twice when within 2 ticks of its CE)."""
    S = _S()
    others = [z for z in side_obs(sd) if z.kind == "bull" and z.i <= i] + [z for z in sd.vis("bull") if z.i <= i]
    refs = list(S._wick_ces(ctx, sd, True))
    if p.monthly_ohlc:                                   # caption-gap L3-monthly-ohlc-3m (cc03_004 ~1:46): the monthly O / H / L / C count as converging levels (the scoring input)
        refs += [float(sd.x(v)) for v in getattr(ctx, "m_ohlc", [])]
    return L.converged_count(g, others, refs, 2 * p.tick)


def pick_converged(ctx, sd, pick: list, i: int, p, last: bool):
    """The entry gap with the most converging arrays (ties: the usual first / last pick). Returns (gap, count)."""
    ns = [converge_n(ctx, sd, g, i, p) for g in pick]
    best = max(ns)
    sub = [g for g, n in zip(pick, ns) if n == best]
    return (sub[-1] if last else sub[0]), best


# --- A6 breakaway gap -----------------------------------------------------------------------------------------------

def breakaway_gap(ctx, sd, sw, i: int, p):
    """A6-breakaway-identification: the breakaway gap per `breakaway_def`.
      "first_after_mss"  the first FVG formed at / after the structure break (Ep01.5, the first build)
      "context"          that gap, but only with HTF context (001 ~42:50: "Breakaway gaps must it must have some context"): a still-valid
                         HTF array (confluence rows / HTF FVG zones) of the trade's side within `breakaway_ctx_pts` of the leg origin
                         (the sweep extreme); no context = a common gap
      "second_mss"       062 ~34:53: the FVG of the SECOND market structure shift (a later swing high formed after the first break
                         and closed through) is the breakaway; the first MSS's gap is a common gap"""
    S = _S()
    first = next((g for g in sd.gaps if g.i >= sw["broke"] and g.i - 2 >= sw["ext_i"] and g.i <= i), None)
    if p.breakaway_def == "first_after_mss" or first is None:
        return first
    if p.breakaway_def == "context":
        tol = p.breakaway_ctx_pts * p.es_pt
        ext = sw["ext"]
        for a, b in htf_zones_side(ctx, sd, i, ("1h", "4h", "D", "W", "M")):
            if a - tol <= ext <= b + tol:
                return first
        if getattr(ctx, "conf", None) is None and getattr(ctx, "hzones", None):
            if S._htf_tag(ctx, sd, i, ext, tol):
                return first
        return None
    ph = [q for q in sd.ph if q.i > sw["broke"] and q.known <= i]
    for q in ph:
        j = next((k for k in range(q.known, i + 1) if sd.c[k] > q.price), None)
        if j is not None:
            return next((g for g in sd.gaps if g.i >= j and g.i - 2 >= sw["ext_i"] and g.i <= i), None)
    return None


# --- A21 leg anchor -------------------------------------------------------------------------------------------------

def leg_low(sd, sw, i: int, p, pd_hi: float) -> float:
    """A21-dealing-range-energetic-swing: the low of the dealing range for leg_pd / the leg-depth tags (side space): the sweep
    extreme (leg_anchor "mss_leg") or the latest displaced swing low (levels.dealing_range "energetic")."""
    if p.leg_anchor != "energetic":
        return float(sw["ext"])
    r = L.dealing_range(sd.h, sd.l, sd.o, sd.c, i, "energetic")
    if r is None or not pd_hi > r[2]:
        return float(sw["ext"])
    return float(r[2])


# --- N-initial-fvg-reference ----------------------------------------------------------------------------------------

def _rth(f: pd.DataFrame) -> pd.DataFrame:
    t = f.index.hour * 60 + f.index.minute
    return f[(t >= 570) & (t < 960)]


def build_init_fvg(ctx, df: pd.DataFrame, hist: list, p) -> list:
    """N-initial-fvg-reference (048 ~5:40; 082 ~5:13): the reference FVGs (real prices): "day" = the first 5m FVG whose third candle
    closes 09:30-10:00 (extended to 16:00); "week" = the first 5m FVG of the first session of the week [our interpretation of "Monday's
    session": the week's first trading day] (extended to Friday's close); "mon10" = Monday's 10:00 1h candle as the middle candle of a
    1h FVG (high / low / CE as a weekly array). Each: dict(name, kind, top, bottom, known, until)."""
    S = _S()
    out = []
    day = ctx.day
    if "day" in p.initial_fvg:
        hb = S.htf_bars(_rth(df), 5)
        for z in L.fvgs(hb.high.values, hb.low.values):
            end = hb.end.iloc[z.i]
            m = end.hour * 60 + end.minute
            if 570 < m <= 600:
                out.append(dict(name="day", kind=z.kind, top=float(z.top), bottom=float(z.bottom), known=end,
                                until=pd.Timestamp(day, tz=NY) + pd.Timedelta(hours=16)))
                break
    if ("week" in p.initial_fvg or "mon10" in p.initial_fvg):
        iso = day.isocalendar()[:2]
        wk = [x for x in hist if x.index[0].date().isocalendar()[:2] == iso] + [df]
        f0 = _rth(wk[0])
        fri = pd.Timestamp(day, tz=NY).normalize() + pd.Timedelta(days=4 - day.weekday(), hours=16)
        if len(f0) and "week" in p.initial_fvg:
            hb = S.htf_bars(f0, 5)
            z = next(iter(L.fvgs(hb.high.values, hb.low.values)), None)
            if z is not None:
                out.append(dict(name="week", kind=z.kind, top=float(z.top), bottom=float(z.bottom),
                                known=hb.end.iloc[z.i], until=fri))
        if len(f0) and "mon10" in p.initial_fvg and wk[0].index[0].weekday() == 0:
            hb = S.htf_bars(f0, 60)
            pos = [k for k, t in enumerate(hb.index) if t.hour == 10 and t.minute == 0]
            if pos:
                for z in L.fvgs(hb.high.values, hb.low.values):
                    if z.src == pos[0]:
                        out.append(dict(name="mon10", kind=z.kind, top=float(z.top), bottom=float(z.bottom),
                                        known=hb.end.iloc[z.i], until=fri))
                        break
        ctx.init_frame = pd.concat(wk)
    elif out:
        ctx.init_frame = df
    return out


def init_state(ctx, z: dict, i: int) -> str:
    """"untested" (no bar since it was known traded into it) / "respected" (traded into, no body closed through its far side) /
    "disrespected" (a body closed through its far side), from the bars closed by bar i."""
    fr = ctx.init_frame
    now = ctx.idx[i] + pd.Timedelta(minutes=ctx.tf)
    seg = fr[(fr.index >= z["known"]) & (fr.index + pd.Timedelta(minutes=ctx.tf) <= now)]
    if not len(seg):
        return "untested"
    cl = seg.close.values
    if (z["kind"] == "bull" and (cl < z["bottom"]).any()) or (z["kind"] == "bear" and (cl > z["top"]).any()):
        return "disrespected"
    touched = ((seg.low.values <= z["top"]) & (seg.high.values >= z["bottom"])).any()
    return "respected" if touched else "untested"


def init_fvg_tags(ctx, i: int, p) -> tuple[list, str]:
    """(lv_tags, Trade.init_fvg_respected) for the reference FVGs in force at bar i's close."""
    zs = getattr(ctx, "initfvg", None)
    if not zs:
        return [], ""
    now = ctx.idx[i] + pd.Timedelta(minutes=ctx.tf)
    tags, parts = [], []
    for z in zs:
        if z["known"] <= now <= z["until"]:
            st = init_state(ctx, z, i)
            tags.append(f"initfvg_{z['name']}_{st}")
            parts.append(f"{z['name']}:{st}")
    return tags, "|".join(parts)


# --- A9 daily VI forward levels -------------------------------------------------------------------------------------

def build_vi_flip(ctx, hist: list, df: pd.DataFrame, p) -> list:
    """A9-daily-vi-forward-levels (025 ~23:19; 007 ~3:40 / ~8:59): every daily VI (RTH session candles, each on its own: both body
    edges + the midpoint, never merged) of the current ISO week - known at the close of the later session, extended through the rest of
    the week. role: "support" when price was BELOW it when it formed (reached from below it becomes support on a retrace from above),
    "resistance" when above. Each dict(top, bottom, mid, role, known, until)."""
    day = ctx.day
    iso = day.isocalendar()[:2]
    sess = [x for x in hist if x.index[0].date().isocalendar()[:2] == iso]
    if len(sess) < 2:
        return []
    o = np.array([float(x.open.iloc[0]) for x in sess]); c = np.array([float(x.close.iloc[-1]) for x in sess])
    h = np.array([float(x.high.max()) for x in sess]); l = np.array([float(x.low.min()) for x in sess])
    fri = pd.Timestamp(day, tz=NY).normalize() + pd.Timedelta(days=4 - day.weekday(), hours=16)
    out = []
    for z in L.volume_imbalances(o, h, l, c, 0.0, wick_overlap=False):
        end = sess[z.i].index[-1] + pd.Timedelta(minutes=ctx.tf)
        role = "support" if z.kind == "bear" else "resistance"       # from the VI's own direction: a bearish VI (price below it)
        out.append(dict(top=float(z.top), bottom=float(z.bottom), mid=float((z.top + z.bottom) / 2), role=role,
                        known=end, until=fri, frame=pd.concat(sess[z.i + 1:] + [df]) if z.i + 1 < len(sess) else df))
    return out


def _vi_flip_live(ctx, i: int) -> list:
    """The daily-VI dicts price REACHED (a base bar since the VI was known overlapped it) and not invalidated at closed bar i: a
    60-minute body close beyond its far edge (below the low of a support, above the high of a resistance) [our interpretation] retires
    it. Each dict gets "reached_i" (the first base bar that overlapped it)."""
    out = []
    now = ctx.idx[i] + pd.Timedelta(minutes=ctx.tf)
    for z in getattr(ctx, "vi_flip", []):
        if not (z["known"] <= now <= z["until"]):
            continue
        fr = z["frame"]
        seg = fr[(fr.index >= z["known"]) & (fr.index + pd.Timedelta(minutes=ctx.tf) <= now)]
        hit = (seg.low.values <= z["top"]) & (seg.high.values >= z["bottom"]) if len(seg) else np.zeros(0, bool)
        if not hit.any():
            continue
        k = int(np.argmax(hit))
        after = _S().htf_bars(seg.iloc[k:], 60)
        after = after[after.end <= now]
        cl = after.close.values
        if len(cl) and ((z["role"] == "support" and (cl < z["bottom"]).any())
                        or (z["role"] == "resistance" and (cl > z["top"]).any())):
            continue
        out.append(dict(z, reached_i=int(ctx.idx.searchsorted(seg.index[k]))))
    return out


def vi_flip_levels(ctx, i: int, p) -> list:
    """(level, name) of the reached, still valid daily VIs (edges + midpoint, real prices), all roles; `vi_flip_target_levels` is the
    target use."""
    return [(v, "vi_" + z["role"]) for z in _vi_flip_live(ctx, i) for v in (z["top"], z["mid"], z["bottom"])]


def vi_flip_target_levels(ctx, sd, i: int, p) -> list:
    """A9-daily-vi-forward-levels, target use (side space): only the OPPOSING role - a long meets a reached VI that turned resistance
    above price; the support role is the entry array (vi_flip_entry_zones), never the long's own target."""
    want = "resistance" if sd.sign > 0 else "support"
    return [sd.x(v) for z in _vi_flip_live(ctx, i) if z["role"] == want for v in (z["top"], z["mid"], z["bottom"])]


def vi_flip_entry_zones(ctx, sd, sw, i: int, p) -> list:
    """A9-daily-vi-forward-levels, entry use (025 ~23:19: on a retrace from above the reached VI is the support array): the support-role
    daily VIs (a short: the resistance role, mirrored) as fixed entry zones between the sweep extreme and the last close, known from
    the bar that reached them. [our interpretation: the "ideally with an hourly FVG" pairing is not required]"""
    role = "support" if sd.sign > 0 else "resistance"
    out = []
    for z in _vi_flip_live(ctx, i):
        if z["role"] != role:
            continue
        top, bot, mt = (z["top"], z["bottom"], z["mid"]) if sd.sign > 0 else (-z["bottom"], -z["top"], -z["mid"])
        if not sw["ext"] < top < sd.c[i]:
            continue
        zi = min(i, max(z["reached_i"], sw["ext_i"] + 1))
        out.append(L.Zone("bull", float(top), float(bot), zi, zi, float(mt), tag="vi_flip"))
    return out


# --- A12 consolidation OB open --------------------------------------------------------------------------------------

def build_cons_ob(ctx, hist: list, df: pd.DataFrame, p) -> list:
    """A12-consolidation-ob-open-level (008 ~4:09): on 1h bars of the last 5 sessions + today, the open of the last down-close (up-close)
    candle before a consolidation (levels.consolidation_ob_opens), real prices, known when the 1h range reached its bar count. Each
    dict(kind, level, known, src_end)."""
    S = _S()
    fr = pd.concat(hist[-5:] + [df])
    hb = S.htf_bars(fr, 60)
    out = []
    for z in L.consolidation_ob_opens(hb.open.values, hb.high.values, hb.low.values, hb.close.values):
        out.append(dict(kind=z.kind, level=float(z.top), known=hb.end.iloc[z.i], from_t=hb.end.iloc[z.src]))
    return out


def cons_ob_levels(ctx, sd, i: int, p) -> list:
    """The consolidation OB opens (side space) usable at bar i: known, and no base close since it was known went through it the wrong way
    (a body close below a bullish open / above a bearish one)."""
    now = ctx.idx[i] + pd.Timedelta(minutes=ctx.tf)
    out = []
    for z in getattr(ctx, "cons_ob", []):
        if z["known"] > now:
            continue
        m = (ctx.idx >= z["known"]) & (ctx.idx + pd.Timedelta(minutes=ctx.tf) <= now)
        cl = ctx.c[m]
        if len(cl) and ((z["kind"] == "bull" and (cl < z["level"]).any()) or (z["kind"] == "bear" and (cl > z["level"]).any())):
            continue
        out.append((sd.x(z["level"]), z["kind"]))
    return out


# --- A5 two-pass delivery state -------------------------------------------------------------------------------------

def drop_efficient(ctx, sd, i: int, p, lv: list) -> list:
    """X-efficient-delivery-two-pass (026 ~1:58:21; 050 ~30:29; 061 ~1:35:24): from the target levels `lv` ((level, kind), side space) drop
    the levels (near edge, CE, far edge) of every intraday gap band - FVG, void, VI above price - that price has crossed BOTH ways on this
    timeframe (levels.pass_state counts from the band's own middle candle; wicks count): efficient delivery is not a target. A band crossed
    `shield_passes` or more times in all SHIELDS the arrays beyond it: array-kind levels past its far edge are dropped too (a one-way band
    does not shield). NDOG / NWOG are never dropped (050: they stay as references). HTF bands are not judged here."""
    S = _S()
    h, l = sd.h, sd.l
    bands = [z for z in list(sd.opposing()) + list(sd.vis("bear")) if z.i <= i]
    bands += [z for z in list(sd.gaps) + list(sd.vis("bull")) if z.i <= i and z.bottom > sd.c[i]]
    drop, shield = [], []
    for z in bands:
        up, down = L.pass_state(h, l, z, z.src, i)
        if L.is_efficient(up, down):
            drop += [z.bottom, z.mid, z.top]
        if up >= 1 and down >= 1 and up + down >= p.shield_passes and z.bottom > sd.c[i]:
            shield.append(z.top)
    tk = 0.25 * p.es_pt * 0.04
    cap = min(shield) if shield else None
    out = []
    for v, k in lv:
        if k == "array" and any(abs(v - d) <= tk for d in drop):       # only array-kind levels: a pool / wick on a band edge stays
            continue
        if cap is not None and k == "array" and v > cap + tk:
            continue
        out.append((v, k))
    return out


# --- management -----------------------------------------------------------------------------------------------------

def manage(ctx, sd, pos, tr, i: int, p) -> None:
    """Per-bar management hooks (after the other trails): A11 bpr2_trail (003 ~29:37) - a long's stop goes to the Type 2 BPR low minus a tick once a new
    bullish FVG has formed above its high; A23 wick_bias_line (065 ~4:19:02 / 075 ~1:05:07) - a body close at or below the CE of the 1h lower-wick
    tail at the sweep low stops the adds [our interpretation: the 1h candle holding the sweep extreme]."""
    S = _S()
    if p.bpr2_trail and pos["left"] and not pos.get("day_trade"):
        entry = pos["basis"] / pos["n"]
        zs = [z for z in sd._lazy(("ld_bpr2",), lambda: L.single_pass_bprs(sd.o, sd.h, sd.l, sd.c, ("gap", "range")))
              if z.tag == "bull" and 0 <= z.bi <= i and z.top <= entry + 1e-9]
        if zs:
            z = max(zs, key=lambda q: q.bi)
            if any(g.i <= i and g.i > z.bi and g.bottom >= z.top for g in sd.gaps):
                from . import manage as _MG
                _MG.raise_stop(pos, z.bottom - p.tick, trail=True)
    if p.wick_bias_line and not pos.get("bias_line_lost"):
        e = pos["ext_i"]
        if 0 <= e < len(ctx.idx):
            b0 = ctx.idx[e].floor("60min")
            b1 = b0 + pd.Timedelta(minutes=60)
            # the 1h candle is used only once it has CLOSED (bar i starts at or after its end): a mid-hour bar would read the hour's
            # later low and final close (look-ahead)
            if ctx.idx[i] < b1:
                return
            m = (ctx.idx >= b0) & (ctx.idx < b1)
            lo, bb = float(sd.l[m].min()), float(min(sd.o[m][0], sd.c[m][-1]))
            ce = (lo + bb) / 2
            if bb > lo and sd.c[i] <= ce and i > pos["fill_i"]:
                pos["bias_line_lost"] = True
                pos["no_adds"] = True
                tr.lv_tags = "|".join(x for x in (tr.lv_tags, "wick_bias_lost") if x)


# --- tags at the order ----------------------------------------------------------------------------------------------

def order_tags(ctx, sd, sw, i: int, p, entry: float) -> tuple[list, str]:
    """(lv_tags, init_fvg_respected) added in _finish_order: the vacuum-block exhaustion tag, the reference FVG states, the wick quarter
    tier of the sweep (A23), the Judas cap (A23), bpr2_cont (A11) and the converged count is added at the gap pick."""
    tags = []
    if p.vb_context:
        tags += vb_tags(ctx)
    t2, init = init_fvg_tags(ctx, i, p)
    tags += t2
    if p.wick_quarters:
        w = _wick_tier_tag(ctx, sd, sw, p)
        if w:
            tags.append(w)
    if p.judas_wick_cap:
        w = _judas_cap_tag(ctx, sd, sw, i)
        if w:
            tags.append(w)
    if p.bpr2_cont_trigger:
        for g in reversed([g for g in sd.gaps if g.i <= i and g.i - 2 >= sw["ext_i"]]):
            if L.fvg_continuation_trigger(sd.h, sd.l, g, g.i + 1, i) is not None:
                tags.append("bpr2_cont")
                break
    return tags, init


def _wick_tier_tag(ctx, sd, sw, p) -> str:
    """A23 (025 ~34:43; 103 ~24:07): how far the retrace (the sweep extreme) went into a prior-day wick: very_bearish (turned at q25) / normal
    (CE) / overshoot (past CE, within q75) / failed (through q75) - for a long it is the lower wick (very_bullish)."""
    best = None
    for w in getattr(ctx, "wicks", []):
        if "upper_q25" not in w:
            continue
        tol = 0.25 * p.tick
        if sd.sign < 0:                                  # a short: the upper wick, real prices
            ex = -float(sw["ext"])
            tier = L.wick_tier(ex, w["upper_body"], w["upper_w"], tol)
            edge = w["upper_body"]
        else:                                            # a long: the lower wick, mirrored
            ex = -float(sw["ext"])
            tier = L.wick_tier(ex, -w["lower_body"], -w["lower_w"], tol)
            edge = -w["lower_body"]
        if tier != "none" and (best is None or abs(ex - edge) < best[0]):
            best = (abs(ex - edge), tier)
    if best is None:
        return ""
    return "wick_tier_" + (best[1].replace("bearish", "bullish") if sd.sign > 0 else best[1])


def _judas_cap_tag(ctx, sd, sw, i: int) -> str:
    """A23 Judas cap (072 ~5:27): the prior day's upper wick CE (high + body top) / 2 caps rallies; held while every close since the
    sweep extreme stayed under it (a long: the lower wick CE mirrored)."""
    ws = getattr(ctx, "wicks", [])
    if not ws:
        return ""
    w = ws[0]
    if not len(sd.c[sw["ext_i"]:i + 1]):
        return ""
    ok = (np.array(ctx.c[sw["ext_i"]:i + 1]) < w["upper"]).all() if sd.sign < 0 else (np.array(ctx.c[sw["ext_i"]:i + 1]) > w["lower"]).all()
    return "judas_cap_held" if ok else "judas_cap_lost"
