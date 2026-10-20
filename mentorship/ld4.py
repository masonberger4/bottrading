"""Caption-gap pass (digests/rulebook_gaps/*.md), package levels_detectors #3/3: the engine glue.

The detectors live in levels.py (pure arrays in, objects out) and htf.py (opening gaps incl. the RTH view, gap selection); this module
wires them into the bar-by-bar engine (strategy.py hooks) behind Params switches - see the "caption-gap pass, levels_detectors #3/3"
block of Params; every switch cites its gap id and source video/time there. Conventions as everywhere: side space (shorts run mirrored
prices), a bar is used only after it closes, an object only from the bar that completes it; daily / weekly objects only after their
session closes (everything here reads `ctx.hist`, the COMPLETED prior sessions, plus today's bars through the bar being judged).
"""
from __future__ import annotations

from datetime import timedelta

import numpy as np
import pandas as pd

from . import levels as L


def _S():
    from . import strategy as S
    return S


def _c(ctx) -> dict:
    return ctx.__dict__.setdefault("_ld4", {})


def _adr5(ctx):
    return _S().adr5(getattr(ctx, "hist", [])[-5:])


# --- daily history -----------------------------------------------------------------------------------------------------

def daily_rows(ctx, p) -> tuple[list, list]:
    """(dates, rows): the completed sessions before today, oldest first, rows = (open, high, low, close) - the full-session (ETH) candles
    when ipda_session is "eth" and the frame has them, else the regular-session ones (the IPDA frame)."""
    c = _c(ctx)
    if "rows" not in c:
        hist = getattr(ctx, "hist", [])
        eth = getattr(ctx, "eth", None)
        dates = [x.index[0].date() for x in hist]
        rows = []
        for d, x in zip(dates, hist):
            e = eth.get(d) if (eth and p.ipda_session == "eth") else None
            rows.append(tuple(float(v) for v in e) if e is not None else
                        (float(x.open.iloc[0]), float(x.high.max()), float(x.low.min()), float(x.close.iloc[-1])))
        c["rows"] = (dates, rows)
    return c["rows"]


# --- build (called once per day from strategy._extra_levels) -----------------------------------------------------------------

def build(ctx, df, hist, p, dates, cand, eth) -> None:
    """Static, per-day objects of this package (all from completed sessions; today's bars are read per bar by the functions below)."""
    if eth is not None and getattr(ctx, "eth", None) is None:
        ctx.eth = eth
    if p.prev_london_pool:                                  # L1-prior-day-london-pm-pools (072 ~27:52): the previous day's London 02:00-05:00 range
        src = getattr(ctx, "prev_full", None)
        if src is None or not len(src):
            src = hist[-1]
        pt = src.index.hour * 60 + src.index.minute
        lon = src[(pt >= 120) & (pt < 300)]
        if len(lon) and dates and src.index[0].date() == dates[-1]:
            ctx.sess["prev_london"] = (float(lon.high.max()), float(lon.low.min()), 0)
    ctx.m_ohlc = []
    if p.monthly_ohlc and hist:                             # L3-monthly-ohlc-3m (cc03_004 ~1:46): O / H / L / C of the last 3 completed months
        d_, rows = daily_rows(ctx, p)
        a = np.array(rows, float)
        for _, mo, mh, ml, mc in L.monthly_candles(d_, a[:, 0], a[:, 1], a[:, 2], a[:, 3], ctx.day, 3):
            ctx.m_ohlc += [mo, mh, ml, mc]
    ctx.rb_lv = rb_build(ctx, p) if p.rb_pools else ([], [])
    ctx.week_hl = week_build(ctx, dates, hist, p, eth) if p.week_pools else None
    ctx.lr_prev = lr_build(ctx, p) if p.london_lr_zone != "off" else None
    ctx.or_fvgs = or_fvg_build(ctx, p) if p.or_fvg_entries else []
    if p.wick_untraded or p.wick_weeks > 1 or p.wick_lod_tag != "off":
        build_wicks(ctx, p, dates, hist, cand)
    ctx.org_hist = org_hist_build(ctx, p) if p.org_both_ways else []


# --- L7 ORG: both directions, partial delivery ---------------------------------------------------------------------------

def org_hist_build(ctx, p) -> list:
    """L7-org-lifetime-sr (068 ~9:51; 092 ~1:59:32): per ORG of ctx.org the highest high / lowest low traded since its formation through
    YESTERDAY - the regular session of the formation day from 09:30, then the later completed sessions (full-session candles when the
    frame has them). Today's bars are added per bar (org_state)."""
    out = []
    eth = getattr(ctx, "eth", None)
    fr = []                                                  # per completed session: (date, regular-session high, low)
    for x in getattr(ctx, "hist", []):
        r = x[(x.index.hour * 60 + x.index.minute) >= 570]
        fr.append((x.index[0].date(), float(r.high.max()) if len(r) else -np.inf, float(r.low.min()) if len(r) else np.inf))
    for d in getattr(ctx, "org_dates", []):
        hi, lo = -np.inf, np.inf
        for dx, rh, rl in fr:
            if dx < d:
                continue
            e = eth.get(dx) if (eth and dx > d) else None
            if e is not None:
                hi, lo = max(hi, float(e[1])), min(lo, float(e[2]))
            else:
                hi, lo = max(hi, rh), min(lo, rl)
        out.append((float(hi), float(lo)))
    return out


def org_sel(ctx, p, pre_open: bool) -> list[int]:
    """Global indices (into ctx.org) of the ORGs inside the org_days window (today's own only from 09:30), oldest first."""
    n = len(ctx.org) - (1 if (pre_open and getattr(ctx, "org_today", False)) else 0)
    return list(range(n))[-p.org_days:] if p.org_days else []


def org_state(ctx, j: int, i: int, p) -> dict:
    """The ORG j (real prices) as of bar i: top / bot of the gap, up_done (a print at or above the top since it formed), dn_done (at or below
    the bottom), part_up / part_dn (the furthest point reached inside the gap going up / down, None when the gap was not entered that way).
    A gap-up ORG opens at its top, so its up side is done by construction (and the mirror)."""
    S = _S()
    a, b = ctx.org[j]
    top, bot = max(a, b), min(a, b)
    hi, lo = ctx.org_hist[j] if j < len(getattr(ctx, "org_hist", [])) else (-np.inf, np.inf)
    d = ctx.org_dates[j] if j < len(getattr(ctx, "org_dates", [])) else None
    k0 = S._idx_at(ctx, 570) if d == ctx.day else ctx.start
    if i >= k0 and k0 < len(ctx.h):
        hi, lo = max(hi, float(ctx.h[k0:i + 1].max())), min(lo, float(ctx.l[k0:i + 1].min()))
    return dict(top=top, bot=bot, up_done=bool(hi >= top - 1e-9), dn_done=bool(lo <= bot + 1e-9),
                part_up=float(hi) if bot < hi < top else None, part_dn=float(lo) if bot < lo < top else None)


def org_alive(ctx, j: int, i: int, p) -> bool:
    """With org_both_ways an ORG whose two sides are both done drops out of the lists (it stays after a one-way fill)."""
    if not p.org_both_ways:
        return True
    st = org_state(ctx, j, i, p)
    return not (st["up_done"] and st["dn_done"])


def org_levels(ctx, sd, i: int, p, idxs: list) -> list:
    """Target levels (side space) of the ORGs `idxs`: the usual 0 / 25 / 50 / 75 / 100% levels, but only the part still PENDING in the
    side's direction - [the partial-delivery extreme, the far edge]; none when that side is done."""
    out = []
    for j in idxs:
        st = org_state(ctx, j, i, p)
        if st["up_done"] and st["dn_done"]:
            continue
        a, b = ctx.org[j]
        pts = [a + q * (b - a) for q in (0.0, 0.25, 0.5, 0.75, 1.0)]
        if sd.sign > 0:
            if st["up_done"]:
                continue
            lim = st["part_up"] if st["part_up"] is not None else st["bot"]
            vals = [v for v in pts if v >= lim - 1e-9] + ([st["part_up"]] if st["part_up"] is not None else [])
        else:
            if st["dn_done"]:
                continue
            lim = st["part_dn"] if st["part_dn"] is not None else st["top"]
            vals = [v for v in pts if v <= lim + 1e-9] + ([st["part_dn"]] if st["part_dn"] is not None else [])
        out += [float(sd.x(v)) for v in vals]
    return out


# --- L10 wick CEs of older candles --------------------------------------------------------------------------------------

def build_wicks(ctx, p, dates, hist, cand) -> None:
    """L10-older-daily-weekly-wick-ce (010 ~1:45; 015 ~31:48; 011 ~5:22): which wick CEs are still UNTRADED - no later completed daily bar
    traded through the CE by a tick (upper CE: a later high at or above CE + tick; lower: a later low at or below CE - tick).
    ctx.wick_ok[k] = (upper_ok, lower_ok) aligned with ctx.wicks (k = 0 yesterday); with wick_weeks > 1 ctx.wick_wk is rebuilt from the last
    `wick_weeks` completed weeks (ctx.wick_wk_ok likewise)."""
    tk = _S()._tick(p)
    cs = [cand(d, x) for d, x in zip(dates, hist)]
    ok = []
    for k in range(1, len(ctx.wicks) + 1):
        w = ctx.wicks[k - 1]
        later = cs[len(cs) - k + 1:]
        ok.append((not any(x[1] >= w["upper"] + tk - 1e-9 for x in later), not any(x[2] <= w["lower"] - tk + 1e-9 for x in later)))
    ctx.wick_ok = ok
    cur = ctx.day.isocalendar()[:2]
    wk_idx: dict = {}
    for j, d in enumerate(dates):
        key = d.isocalendar()[:2]
        if key < cur:
            wk_idx.setdefault(key, []).append(j)
    weeks = []                                            # [(wick dict, index of the week's last session)]
    if p.wick_weeks > 1:
        for key in sorted(wk_idx)[-p.wick_weeks:]:
            js = wk_idx[key]
            seg = [cs[j] for j in js]
            weeks.append((L.wick_midpoints(seg[0][0], max(x[1] for x in seg), min(x[2] for x in seg), seg[-1][3]), js[-1]))
        ctx.wick_wk = [w for w, _ in weeks]
    elif ctx.wick_wk:                                     # the prior calendar week built by _extra_levels (wick_weekly)
        pk = (ctx.day - timedelta(days=7)).isocalendar()[:2]
        js = wk_idx.get(pk)
        weeks = [(ctx.wick_wk[0], js[-1])] if js else []
    ctx.wick_wk_ok = []
    for w, last in weeks:
        later = cs[last + 1:]
        ctx.wick_wk_ok.append((not any(x[1] >= w["upper"] + tk - 1e-9 for x in later), not any(x[2] <= w["lower"] - tk + 1e-9 for x in later)))


def wick_ce_levels(ctx, sd, p, both: bool) -> list:
    """The older-day / weekly wick CEs of _targets (side space): the far wick of each (yesterday excluded unless `both`, where every day's
    other wick is added too - the L10 wick_both rule). With wick_untraded a CE some later daily bar traded through is dropped."""
    out = []
    dly = list(getattr(ctx, "wicks", []))
    wk = list(getattr(ctx, "wick_wk", []))
    f_d = list(getattr(ctx, "wick_ok", [])) + [(True, True)] * len(dly)
    f_w = list(getattr(ctx, "wick_wk_ok", [])) + [(True, True)] * len(wk)
    items = [(w, f_d[k]) for k, w in enumerate(dly)][1:] + [(w, f_w[k]) for k, w in enumerate(wk)]
    for w, (uo, lo) in items:
        if not p.wick_untraded or (uo if sd.sign > 0 else lo):
            out.append(float(sd.x(w["upper"] if sd.sign > 0 else w["lower"])))
    if both:
        for w, (uo, lo) in [(w, f_d[k]) for k, w in enumerate(dly)] + [(w, f_w[k]) for k, w in enumerate(wk)]:
            if not p.wick_untraded or (lo if sd.sign > 0 else uo):
                out.append(float(sd.x(w["lower"] if sd.sign > 0 else w["upper"])))
    return out


def wick_lod(ctx, sd, sw, i: int, p) -> bool:
    """L10-older-daily-weekly-wick-ce (010 ~1:45; 093 ~6:48): the sweep extreme (side space) within 2 ticks of an UNTRADED lower-wick CE (a
    short: the upper) of the last wick_days daily candles that also sits within 1 pt of a 5m / 15m discount array of the trade's side - the
    expected low of the day [our interpretation: 'coincides' = within 1 pt]. The arrays are the confluence 5m / 15m FVGs / OBs known at the sweep
    (ctx.conf), else the bullish FVGs of the base bars when those are 5m / 15m."""
    if not getattr(ctx, "wick_ok", None):
        return False
    tick = p.tick
    ext = float(sw["ext"])
    ces = []
    for w, (uo, lo) in zip(ctx.wicks, ctx.wick_ok):
        if sd.sign > 0 and lo:
            ces.append(float(w["lower"]))
        elif sd.sign < 0 and uo:
            ces.append(float(w["upper"]))
    ces = [sd.x(v) for v in ces if abs(sd.x(v) - ext) <= 2 * tick + 1e-9]
    if not ces:
        return False
    zones = []                                            # (low, high) in side space
    cf = getattr(ctx, "conf", None)
    if cf is not None:
        kb = ctx.idx[sw["ext_i"]] + pd.Timedelta(minutes=ctx.tf)
        now = ctx.idx[i] + pd.Timedelta(minutes=ctx.tf)
        for top, bot, tf_, _, _ in cf.valid(now, sd.sign, ("5m", "15m"), (0, 1, 3), kb):
            zones.append(tuple(sorted((float(sd.x(top)), float(sd.x(bot))))))
    elif ctx.tf in (5, 15):
        zones = [(float(z.bottom), float(z.top)) for z in sd.gaps
                 if z.i <= i and sd.c[z.i + 1:i + 1].min(initial=np.inf) >= z.bottom]
    tol = p.es_pt
    return any(lo - tol - 1e-9 <= v <= hi + tol + 1e-9 for lo, hi in zones for v in ces)


# --- pools ----------------------------------------------------------------------------------------------------------------

def _hi_side(sd, hl) -> float:
    return float(sd.x(hl[0] if sd.sign > 0 else hl[1]))


def _lo_side(sd, hl) -> float:
    return float(sd.x(hl[1] if sd.sign > 0 else hl[0]))


def reactionary_buy(ctx, sd, i: int, p):
    """The latest UNTAKEN reactionary high (side space) known at bar i: (price, known) or None (new-reactionary-high-liquidity)."""
    recs = sd._lazy("ld4_react_b", lambda: L.reactionary_highs(sd.o, sd.h, sd.l, sd.c, sd.ph, p.displacement_mult or 1.5))
    best = None
    for price, bi, known in recs:
        if known <= i and sd.h[bi + 1:i + 1].max(initial=-np.inf) < price:
            best = (price, known)
    return best


def reactionary_sell(ctx, sd, i: int, p):
    """The mirror: the latest untaken reactionary LOW (a pivot low that launched a displacement leg up) known at bar i-1 (the sweep bar excluded)."""
    mir = [L.Pivot(q.i, -q.price, q.known) for q in sd.pl]
    recs = sd._lazy("ld4_react_s", lambda: L.reactionary_highs(-sd.o, -sd.l, -sd.h, -sd.c, mir, p.displacement_mult or 1.5))
    best = None
    for price, bi, known in recs:
        if known <= i - 1 and (-sd.l[bi + 1:i]).max(initial=-np.inf) < price:
            best = (-price, known)
    return best


def _parent_band(ctx, p) -> float:
    a = _adr5(ctx)
    return 0.25 * a if a else 0.0


def parent_buy(ctx, sd, i: int, p) -> list:
    """Parent buy-side pools (side space) known at bar i: highs with >= parent_n later highs in the area (within 0.25 x ADR5 below) whose bodies
    stop short of it. [(price, known)]."""
    band = _parent_band(ctx, p)
    if band <= 0:
        return []
    mir = [L.Pivot(q.i, -q.price, q.known) for q in sd.ph if q.known <= i]
    res = L.parent_pools(-sd.o, -sd.l, -sd.h, -sd.c, mir, p.parent_n, band, end=i)
    return [(-v, k) for v, _, k in res]


def parent_sell(ctx, sd, i: int, p) -> list:
    """Parent sell-side pools: lows known by bar i-1 (the sweep bar excluded)."""
    band = _parent_band(ctx, p)
    if band <= 0 or i < 1:
        return []
    res = L.parent_pools(sd.o, sd.h, sd.l, sd.c, [q for q in sd.pl if q.known <= i - 1], p.parent_n, band, end=i - 1)
    return [(v, k) for v, _, k in res]


def trendline_state(ctx, sd, i: int, p, tol: float):
    """The latest three-touch down-trendline of highs (side space) confirmed by bar i, with the lowest low between H2 and H3, or None."""
    pv = sd._lazy("ld4_pv1", lambda: L.pivots(sd.h, sd.l, 1))
    hs = [q for q in pv[0] if q.known <= i]
    return L.trendline_highs(hs, tol, sd.l)


def _tl_tol(ctx, p, pools: bool) -> float:
    if pools:                                             # new-trendline-trap-target [our interpretation]: touches within 0.1 x ADR5 of the line
        a = _adr5(ctx)
        if a:
            return 0.1 * a
    return p.tl_tol_ticks * p.tick


def trendline_target(ctx, sd, i: int, p):
    """trendline_pools: H2 + 1 tick (the buy stops above the second touch) as a buy-side pool, for the sweep recorded by `_targets` (ext_i, ext):
    the entry low lies between H2 and H3 in time (or is a re-run of that low after H3). (price, known) or None."""
    te = _c(ctx).get("tgt_ext")
    if te is None or te[0] is None:
        return None
    ext_i, ext = te
    tl = trendline_state(ctx, sd, i, p, _tl_tol(ctx, p, True))
    if tl is None:
        return None
    h2, h3 = tl["h2"], tl["h3"]
    between = h2.i < ext_i <= h3.i
    rerun = ext_i > h3.i and "l23" in tl and ext is not None and abs(ext - tl["l23"]) <= _tl_tol(ctx, p, True)
    if not (between or rerun):
        return None
    return float(h2.price + p.tick), int(tl["known"])


def is_rb_key(key) -> bool:
    """A17 rejection-block sweep pool keys: rb0, rb1, ..."""
    k = str(key or "")
    return k[:2] == "rb" and k[2:].isdigit()


def bias_with(ctx, sd) -> bool:
    return getattr(ctx, "cur_bias", 0) == sd.sign


def target_pools(ctx, sd, i: int, p) -> list:
    """[(level, created_bar)] buy-side pools of this package for _targets (side space)."""
    out = []
    S = ctx.start
    if p.reactionary_pools:
        r = reactionary_buy(ctx, sd, i, p)
        if r is not None:
            out.append((float(r[0]), int(r[1])))
    if p.parent_pools:
        out += [(float(v), int(k)) for v, k in parent_buy(ctx, sd, i, p)]
    if p.trendline_pools:
        t = trendline_target(ctx, sd, i, p)
        if t is not None:
            out.append(t)
    if p.trendline_trap and bias_with(ctx, sd):
        tl = trendline_state(ctx, sd, i, p, _tl_tol(ctx, p, False))
        if tl is not None:
            out.append((float(tl["h2"].price + p.tick), int(tl["known"])))      # the ladder starts above H2 (cc03_007 ~10:46)
    if p.week_pools and getattr(ctx, "week_hl", None) is not None:
        out.append((_hi_side(sd, ctx.week_hl), S))
    return out


def sell_pools(ctx, sd, i: int, p, out: dict) -> None:
    """Sweep pools of this package added to _sell_side's dict (side space); the creation bars go into ld3's map for _level_created."""
    from . import ld3 as LD3
    cr_map = LD3._c(ctx).setdefault("created", {})
    S = ctx.start
    if p.reactionary_pools:
        r = reactionary_sell(ctx, sd, i, p)
        if r is not None:
            out["reactionary_lo"] = float(r[0])
            cr_map["reactionary_lo"] = int(r[1])
    if p.parent_pools:
        for v, k in parent_sell(ctx, sd, i, p):
            nm = f"parent_lo{int(round(v * 100))}"
            out[nm] = float(v)
            cr_map[nm] = int(k)
    if p.trendline_trap and bias_with(ctx, sd):
        tl = trendline_state(ctx, sd, i - 1, p, _tl_tol(ctx, p, False))
        if tl is not None and "l23" in tl:
            out["tl23"] = float(tl["l23"])
            cr_map["tl23"] = int(tl["known"]) + 1
    if p.week_pools and getattr(ctx, "week_hl", None) is not None:
        wd = ctx.day.weekday()
        if sd.sign > 0 and wd in set(p.week_raid_days) | {0}:           # a raid of the week LOW (Mon-Thu): a long
            out["week_lo"] = _lo_side(sd, ctx.week_hl)
            cr_map["week_lo"] = S
        elif sd.sign < 0 and wd in set(p.week_raid_days):               # a raid of the week HIGH (Tue-Thu): a short
            out["week_hi"] = _lo_side(sd, ctx.week_hl)
            cr_map["week_hi"] = S
    if p.rb_pools and not (getattr(ctx, "cur_bias", 0) == -sd.sign):      # A17: against the bias the level is a target rung only
        hi_l, lo_l = ctx.rb_lv
        for n_, v in enumerate(lo_l if sd.sign > 0 else hi_l):
            nm = f"rb{n_}"
            out[nm] = float(sd.x(v))
            cr_map[nm] = S
    if p.ipda_forward:
        for nm, v in ipda_fwd_lo(ctx, sd, p).items():
            out[nm] = float(v)
            cr_map[nm] = S


def lock_cands(ctx, p, t_lock: int, kl: int) -> list:
    """mark_levels candidates (real prices) of this package: (value, "pool", name, dir, created)."""
    out = []
    S = ctx.start
    if p.week_pools and getattr(ctx, "week_hl", None) is not None:
        out += [(ctx.week_hl[0], "pool", "week_hi", 1, S), (ctx.week_hl[1], "pool", "week_lo", -1, S)]
    if p.prev_london_pool and "prev_london" in ctx.sess:
        hi, lo, _ = ctx.sess["prev_london"]
        out += [(hi, "pool", "prev_london_high", 1, S), (lo, "pool", "prev_london_low", -1, S)]
    if p.rb_pools:
        hi_l, lo_l = ctx.rb_lv
        out += [(v, "pool", f"rb_hi{n}", 1, S) for n, v in enumerate(hi_l)] + [(v, "pool", f"rb_lo{n}", -1, S) for n, v in enumerate(lo_l)]
    return out


def target_arrays(ctx, sd, i: int, p) -> list:
    """Array-kind target levels (side space) of this package: the older rejection-block closes (rungs), the IPDA wick runners."""
    out = []
    if p.rb_pools:
        hi_l, lo_l = ctx.rb_lv
        out += [(float(sd.x(v)), "array") for v in (hi_l if sd.sign > 0 else lo_l)]
    if p.ipda_rb and (p.ipda_pools or p.ipda_next):
        for n in sorted(getattr(ctx, "ipda", {})):
            _, rung = ipda_level(ctx, p, n, sd.sign > 0)
            if rung is not None:
                out.append((float(sd.x(rung)), "array"))
    return out


def draw_prefs(ctx, sd, i: int, entry: float, p) -> list:
    """Draw overrides (side space, raw levels with kind and name) of this package for _draw_prefs: the reactionary high (a retracement's
    draw, preferred over nearer minor highs), a parent pool (beyond its intermediate highs), the pools hit by two IPDA windows."""
    out = []
    if p.reactionary_pools:
        r = reactionary_buy(ctx, sd, i, p)
        if r is not None and r[0] > entry:
            out.append((float(r[0]), "pool", "reactionary"))
    if p.parent_pools:
        ps = [v for v, _ in parent_buy(ctx, sd, i, p) if v > entry]
        if ps:
            out.append((float(min(ps)), "pool", "parent"))
    if p.ipda_forward:
        m = [v for v in multi_window_levels(ctx, sd, i, p) if v > entry]
        if m:
            out.append((float(min(m)), "pool", "ipda_multi"))
    return out


# --- B21 IPDA ---------------------------------------------------------------------------------------------------------------

def ipda_level(ctx, p, n: int, high: bool):
    """(level, runner) of window n's high (low) in real prices. ipda_rb (cc05_001 ~24:28: "if those highs have a lot of Wicks you're going to be
    looking for rejection blocks"): when the extreme candle's wick is longer than its body [our interpretation: wick > body] the level is the
    candle's BODY edge (A17) and the wick extreme the runner; otherwise (the wick extreme, None)."""
    hl = ctx.ipda[n]
    v = hl[0] if high else hl[1]
    if not p.ipda_rb:
        return v, None
    _, rows = daily_rows(ctx, p)
    end = getattr(ctx, "ipda_end", len(rows))
    seg = rows[max(0, end - n):end]
    if not seg:
        return v, None
    k = int(np.argmax([r[1] for r in seg])) if high else int(np.argmin([r[2] for r in seg]))
    o, h, l, c = seg[k]
    body = abs(c - o)
    if high and (h - max(o, c)) > body:
        return max(o, c), h
    if not high and (min(o, c) - l) > body:
        return min(o, c), l
    return v, None


def ipda_hi_lo(ctx, p, sd, n: int) -> tuple:
    """(buy-side level, sell-side level) of window n in side space."""
    hi, _ = ipda_level(ctx, p, n, True)
    lo, _ = ipda_level(ctx, p, n, False)
    return (float(sd.x(hi if sd.sign > 0 else lo)), float(sd.x(lo if sd.sign > 0 else hi)))


def arrays20_exhausted(ctx, sd, i: int, p) -> bool:
    """B21 (cc06_008 ~12:50: "if all the epad data range PD arrays are exhausted ... move out to the 40-day lookback"): every premium array (a
    bearish daily FVG in side space) formed inside the 20-day window has been traded to - a later session's high, or today's high so far,
    reached its bottom. At least one such array must exist [our interpretation: an empty window is not 'exhausted']."""
    _, rows = daily_rows(ctx, p)
    end = getattr(ctx, "ipda_end", len(rows))
    seg = rows[max(0, end - 20):end]
    if len(seg) < 3:
        return False
    a = np.array(seg, float)
    if sd.sign > 0:
        o, h, l, c = a[:, 0], a[:, 1], a[:, 2], a[:, 3]
    else:
        o, h, l, c = -a[:, 0], -a[:, 2], -a[:, 1], -a[:, 3]
    today = float(sd.h[ctx.start:i + 1].max()) if i >= ctx.start else -np.inf
    arrs = [z for z in L.fvgs(h, l, o, c) if z.kind == "bear"]
    if not arrs:
        return False
    return all(max(float(h[z.i + 1:].max(initial=-np.inf)), today) >= z.bottom for z in arrs)


def ipda_pools(ctx, sd, i: int, p) -> list:
    """The IPDA buy-side pools (side space) as (level, created): Params.ipda_pools / ipda_next - the windows' extremes, with ipda_rb the body
    edge of a wicky extreme, with ipda_next the sequence (20 -> 40 -> 60, rolling out on a taken extreme; ipda_roll_arrays: also when the
    20-day window's arrays are exhausted; ipda_beyond_days: the nearest older swing once all three are taken, tag expansion), plus the
    forward intervals of the anchor (ipda_forward)."""
    S = _S()
    st = ctx.start
    wins = {n: ipda_hi_lo(ctx, p, sd, n)[0] for n in sorted(getattr(ctx, "ipda", {}))}
    out = []
    if not (p.ipda_pools or p.ipda_next):
        pass                                                            # (only the forward intervals below)
    elif p.ipda_next:
        seen = float(sd.h[st:i + 1].max())
        if p.ipda_roll_arrays or p.ipda_beyond_days:
            beyond = None
            if p.ipda_beyond_days and wins:
                from . import ld3 as LD3
                end = getattr(ctx, "ipda_end", 0)
                days_n = len(ctx.ipda_days)
                off = days_n - len(LD3.daily_hl(ctx))                 # (tf_lookback["D"] cuts the pivot history)
                lo_i, hi_i = max(0, days_n - p.ipda_beyond_days), end - max(wins)
                ph, _ = LD3.daily_piv(ctx, sd.sign)
                beyond = L.first_old_beyond([q for q in ph if lo_i <= q.i + off < hi_i], seen)
            exh = bool(p.ipda_roll_arrays and arrays20_exhausted(ctx, sd, i, p))
            for v, nm in L.ipda_sequence(wins, seen, S._tick(p), exh, beyond):
                out.append((v, st))
                if nm == "expansion":
                    _c(ctx)["expansion"] = float(sd.x(v))
        else:
            out += [(v, st) for v in [x for x in wins.values() if not S._spent_up(seen, x, S._tick(p))][:1]]
    else:
        out += [(v, st) for v in wins.values()]
    if p.ipda_forward:
        out += [(v, st) for v in ipda_fwd_hi(ctx, sd, p).values()]
    return out


def ipda_fwd(ctx, p) -> dict:
    """Forward intervals / float of the anchor (levels.ipda_forward) in real prices {name: (high, low)}; {} without an anchored window."""
    D = getattr(ctx, "ipda_D", None)
    if D is None:
        return {}
    return L.ipda_forward(list(getattr(ctx, "ipda_days", [])), int(D))


def ipda_fwd_hi(ctx, sd, p) -> dict:
    return {f"ipda_{k}": _hi_side(sd, hl) for k, hl in ipda_fwd(ctx, p).items()}


def ipda_fwd_lo(ctx, sd, p) -> dict:
    return {f"ipda_{k}": _lo_side(sd, hl) for k, hl in ipda_fwd(ctx, p).items()}


def multi_window_levels(ctx, sd, i: int, p) -> list:
    """Buy-side levels (side space) that are the extreme of two or more windows (the back windows, the forward intervals, the float) - ranked
    first (pool_rank) [our interpretation: the same price to the tick]."""
    tk = p.tick
    vals = list(ipda_hi_lo(ctx, p, sd, n)[0] for n in sorted(getattr(ctx, "ipda", {}))) + list(ipda_fwd_hi(ctx, sd, p).values())
    seen = float(sd.h[ctx.start:i + 1].max())
    return sorted({round(v, 6) for v in vals if sum(abs(v - w) <= tk + 1e-9 for w in vals) >= 2 and v > seen})


def conf_targets(ctx, p, now, beyond: float, side: int, tfs, far_edge: bool) -> list:
    """Confluence.targets with the ipda_arrays window: the DAILY arrays must have formed inside the 60-session IPDA window (they are known no
    earlier than the end of its first session)."""
    cf = ctx.conf
    if not (p.ipda_arrays and "D" in tuple(tfs)):
        return cf.targets(now, beyond, side, tfs, far_edge)
    return cf.targets(now, beyond, side, tfs, far_edge, min_known={"D": ipda_since(ctx, p)})


def ipda_since(ctx, p):
    """Timestamp (ns) from which a daily array counts as 'inside the window': the end (17:00) of the first session of the 60-session window
    ending at the anchor."""
    dates, _ = daily_rows(ctx, p)
    end = getattr(ctx, "ipda_end", len(dates))
    if not dates or end <= 0:
        return float("-inf")
    d = dates[max(0, end - 60)]
    return float(pd.Timestamp(d, tz="America/New_York").value + pd.Timedelta(hours=17).value)


# --- A17 rejection-block closes -----------------------------------------------------------------------------------------------

def rb_build(ctx, p) -> tuple:
    """A17-rejection-block-short-protocol (035 ~23:08): the CLOSE of the candle that made an old daily swing high (low) - levels.rejection_blocks
    on the completed daily candles (level1 of the close variant) - while no later session traded through it. ([highs], [lows]) real prices,
    the three nearest each (newest first)."""
    dates, rows = daily_rows(ctx, p)
    if len(rows) < 3:
        return [], []
    a = np.array(rows[-60:], float)
    o, h, l, c = a[:, 0], a[:, 1], a[:, 2], a[:, 3]
    hi_l, lo_l = [], []
    for z in L.rejection_blocks(o, h, l, c, 1, 0.0, "close"):
        lvl = float(z.levels[0])
        if z.kind == "bear" and h[z.src + 1:].max(initial=-np.inf) < lvl:
            hi_l.append((z.src, lvl))
        elif z.kind == "bull" and l[z.src + 1:].min(initial=np.inf) > lvl:
            lo_l.append((z.src, lvl))
    return [v for _, v in sorted(hi_l, reverse=True)[:3]], [v for _, v in sorted(lo_l, reverse=True)[:3]]


# --- L1 / new context ranges ---------------------------------------------------------------------------------------------------

def week_build(ctx, dates, hist, p, eth):
    """new-intra-week-extreme-raid (cc09_005 ~4:07): the highest high / lowest low of the week's completed sessions before today (full-session
    candles when the frame has them - the Sunday evening is part of Monday's); None on the week's first day."""
    wk = ctx.day.isocalendar()[:2]
    hs, ls = [], []
    for d, x in zip(dates, hist):
        if d.isocalendar()[:2] == wk and d < ctx.day:
            e = eth.get(d) if eth else None
            hs.append(float(e[1]) if e is not None else float(x.high.max()))
            ls.append(float(e[2]) if e is not None else float(x.low.min()))
    return (max(hs), min(ls)) if hs else None


def lr_build(ctx, p):
    """LLT3-london-extreme-preny-range (cc08_007 ~2:37): from the PREVIOUS day's bars before 09:30: the bearish range (O, E) - E = the London
    (02:00-05:00) high, O = the lowest low printed between E's bar and 09:30 - and the bullish mirror (E', O'). Needs ctx.prev_full."""
    src = getattr(ctx, "prev_full", None)
    dates = [x.index[0].date() for x in getattr(ctx, "hist", [])[-1:]]
    if src is None or not len(src) or not dates or src.index[0].date() != dates[0]:
        return None
    t = src.index.hour * 60 + src.index.minute
    lon = np.flatnonzero((t >= 120) & (t < 300))
    pre = np.flatnonzero(t < 570)
    if not len(lon) or not len(pre):
        return None
    h, l = src.high.values.astype(float), src.low.values.astype(float)
    ie = int(lon[np.argmax(h[lon])])
    il = int(lon[np.argmin(l[lon])])
    seg_e = pre[pre >= ie]
    seg_l = pre[pre >= il]
    return dict(bear=(float(l[seg_e].min()), float(h[ie])), bull=(float(l[il]), float(h[seg_l].max())))


def lr_state(ctx, sd, entry: float, p) -> bool | None:
    """True when the entry (side space) is in the traded half of yesterday's London-to-pre-NY range: a short in the premium half of
    (O, E) (>= (O + E) / 2, up to E), a long in the discount half of (E', O'); None when no range is known."""
    lr = getattr(ctx, "lr_prev", None)
    if not lr:
        return None
    tol = p.tick
    real = sd.x(entry)
    if sd.sign < 0:
        o, e = lr["bear"]
        return bool((o + e) / 2 - tol <= real <= e + tol)
    e, o = lr["bull"]
    return bool(e - tol <= real <= (e + o) / 2 + tol)


def or_fvg_build(ctx, p) -> list:
    """L3-or-refs-expire-1100 (090 ~49:21): the FVGs formed inside the opening range (bars 09:30 to the OR end) as Zones in frame-bar terms (real
    prices; kind bull / bear; i = the bar completing the gap)."""
    t = ctx.t
    S = ctx.start
    idx = np.flatnonzero((t[S:] >= 570) & (t[S:] < ctx.or_end)) + S
    if len(idx) < 3:
        return []
    a, b = int(idx[0]), int(idx[-1])
    out = []
    for z in L.fvgs(ctx.h[a:b + 1], ctx.l[a:b + 1], ctx.o[a:b + 1], ctx.c[a:b + 1]):
        out.append(L.Zone(z.kind, z.top, z.bottom, a + z.i, a + z.src))
    return out


def or_fvg_zones(ctx, sd, sw, i: int, p) -> list:
    """Entry zones (side space): the OR FVGs of the side's colour, known at bar i, still open (no close below the bottom since), between the
    sweep extreme and the last close, for setups armed 10:00-11:00 (600 <= t < 660)."""
    if not (600 <= ctx.t[i] < 660):
        return []
    out = []
    for z in getattr(ctx, "or_fvgs", []):
        if z.i > i:
            continue
        top, bot = (z.top, z.bottom) if sd.sign > 0 else (-z.bottom, -z.top)
        if (z.kind == "bull") != (sd.sign > 0):
            continue
        if sd.c[z.i + 1:i + 1].min(initial=np.inf) < bot or not sw["ext"] < top < sd.c[i]:
            continue
        out.append(L.Zone("bull", float(top), float(bot), z.i, z.src, tag="or_fvg"))
    return out


# --- time distortion ---------------------------------------------------------------------------------------------------------

def td_mask(ctx, p) -> np.ndarray:
    """new-time-distortion: per frame bar, True where no signal is read (levels.time_distortion_mask: the 15 min before a release, from
    16:00, the lunch chop when td_lunch). Today's releases apply to today's bars only."""
    c = _c(ctx)
    key = ("td", bool(p.td_lunch))
    if key not in c:
        from .calendar import release_times
        S = ctx.start
        m = L.time_distortion_mask(ctx.t, (), p.td_lunch)
        m[S:] = L.time_distortion_mask(ctx.t[S:], release_times(ctx.day), p.td_lunch)
        c[key] = m
    return c[key]


def td_masked(ctx, p, k: int) -> bool:
    return bool(p.time_distortion and 0 <= k < len(ctx.t) and td_mask(ctx, p)[k])


def td_ref(ctx, sd, sw, i: int, p, rr):
    """The MSS reference swing (ref_i, ref, real) with the time-distortion filter: a swing high formed in a masked bar is no reference - the
    newest earlier swing high outside the mask (known by bar i) takes its place; None when there is none."""
    if rr is None or not p.time_distortion or not td_masked(ctx, p, rr[0]):
        return rr
    for q in reversed(sd.ph):
        if q.i < sw["ext_i"] and q.known <= i and not td_masked(ctx, p, q.i):
            return q.i, q.price, True
    return None


def td_gaps(ctx, sd, gaps: list, p) -> list:
    """FVGs whose middle or completing bar falls under the mask are not triggers."""
    if not p.time_distortion:
        return gaps
    return [g for g in gaps if not td_masked(ctx, p, g.i) and not td_masked(ctx, p, g.src)]


def td_hold(ctx, sd, g, i: int, p) -> bool:
    """td_fvg_hold: bodies stay inside the gap for several bars (5+) inside 10:00-12:00 while wicks poke out - the gap stays valid."""
    if not (p.td_fvg_hold and 600 <= ctx.t[i] < 720):
        return False
    k = i
    while k > g.i and 600 <= ctx.t[k] < 720:
        k -= 1
    return L.fvg_body_hold(sd.o, sd.h, sd.l, sd.c, g.bottom, g.top, max(g.i + 1, k + 1), i)


# --- order-level gates and tags ---------------------------------------------------------------------------------------------

def daily_fvg_ok(ctx, sd, sw, i: int, p) -> bool:
    """L2-sr-needs-fvg (058 ~13:34; 076 ~21:21: "classic support resistance is only confirmed if it has one of my fair value gaps"):
    daily_level_needs_array="fvg" - the swept daily level needs a same-side FVG (not any PD array) on daily_level_array_tfs whose range is within a
    tick of the level. Without a confluence object the answer is False."""
    cf = getattr(ctx, "conf", None)
    if cf is None:
        return False
    kb = ctx.idx[sw["ext_i"]] + pd.Timedelta(minutes=ctx.tf)
    now = ctx.idx[i] + pd.Timedelta(minutes=ctx.tf)
    lvl = sd.x(float(sw["level"]))
    tk = p.tick
    return any(bot - tk - 1e-9 <= lvl <= top + tk + 1e-9
               for top, bot, tf_, _, _ in cf.valid(now, sd.sign, tuple(p.daily_level_array_tfs), (0,), kb))


def order_gate(ctx, sd, sw, i: int, p, entry: float, cf, htf_tag, lvt: list):
    """Gates / tags of this package at order completion (strategy._finish_order). Returns a reject reason or None; tags go into `lvt`."""
    key = str(sw.get("key", ""))
    if p.week_pools and key.startswith("week_"):               # cc09_005: a raid of the week extreme needs a same-side HTF array
        S = _S()
        if not (S._htf_array(cf, p) if cf is not None else htf_tag):
            return "x_week_no_array"
        lvt.append(key)
    if p.trendline_trap and key == "tl23":
        if float(sw["level"]) - float(sw["ext"]) > p.ts_max_pts * p.es_pt + 1e-9:
            return "x_tl_poke"                                    # a turtle soup: the poke stays within ts_max_pts
        lvt.append("tl23")
    if p.rb_pools and is_rb_key(key):
        lvt.append("rb_close")
    if p.wick_lod_tag != "off":
        if wick_lod(ctx, sd, sw, i, p):
            lvt.append("wick_lod")
        elif p.wick_lod_tag == "require":
            return "x_wick_lod"
    if p.london_lr_zone != "off":
        st = lr_state(ctx, sd, entry, p)
        if st:
            lvt.append("in_lr")
        elif st is False and p.london_lr_zone == "require" and bias_with(ctx, sd):
            return "x_in_lr"
    if p.reactionary_pools and key == "reactionary_lo":
        lvt.append("reactionary")
    if p.parent_pools and key.startswith("parent_lo"):
        lvt.append("parent_pool")
    if p.ipda_forward and key.startswith("ipda_"):
        lvt.append(key)
    return None


def late_tags(ctx, sd, p, entry: float, lv: list) -> list:
    """Tags added once the targets are known: m_ohlc (an entry / target within 1 pt of a monthly O / H / L / C), expansion (the beyond-60
    older swing is among the targets)."""
    out = []
    tol = p.es_pt
    if p.monthly_ohlc and getattr(ctx, "m_ohlc", None):
        near = [sd.x(v) for v in ctx.m_ohlc]
        if any(abs(entry - v) <= tol for v in near) or any(abs(t - v) <= tol for t in lv for v in near):
            out.append("m_ohlc")
    exp = _c(ctx).get("expansion")
    if p.ipda_beyond_days and exp is not None and any(abs(t - sd.x(exp)) <= tol for t in lv):
        out.append("expansion")
    return out


# --- A12 order block outside the FVG ---------------------------------------------------------------------------------------

def disp_fvg_zone(sd, sw, i: int, g=None):
    """(bottom, top) of the FVG whose shaded zone is skipped when choosing the entry order block: the entry gap `g`, else the first bullish gap
    formed after the sweep extreme and complete by bar i."""
    if g is not None:
        return float(g.bottom), float(g.top)
    for z in sd.gaps:
        if z.i <= i and z.i - 2 >= sw["ext_i"]:
            return float(z.bottom), float(z.top)
    return None


# --- new-hs-fade -------------------------------------------------------------------------------------------------------------

def hs_bars(ctx, sd, m: int):
    """Clock-aligned m-minute buckets of today's frame in side space: (highs, lows, last base bar index of each bucket)."""
    c = _c(ctx)
    key = ("hs", sd.sign, m)
    if key not in c:
        b = pd.Series(np.arange(len(ctx.idx)), index=ctx.idx).groupby(ctx.idx.floor(f"{m}min"))
        first, last = b.min().values, b.max().values
        hh = np.array([sd.h[a:z + 1].max() for a, z in zip(first, last)])
        ll = np.array([sd.l[a:z + 1].min() for a, z in zip(first, last)])
        c[key] = (hh, ll, last, first)
    return c[key]


def hs_pattern(ctx, sd, i: int, p):
    """The head-and-shoulders (side space) complete at bar i: levels.head_shoulders on the hs_tf buckets whose last base bar is <= i (a bucket is used only
    once it has closed). dict (see levels.head_shoulders) plus kb = the base bar at which the right shoulder was confirmed; None when there is none."""
    hh, ll, last, first = hs_bars(ctx, sd, p.hs_tf)
    nb = int(np.searchsorted(last, i, side="right"))
    if nb < 5:
        return None
    r = L.head_shoulders(hh[:nb], ll[:nb], 1, p.eq_tol_pts * p.es_pt)
    if r is not None:
        r["kb"] = int(last[r["known"]])
        r["s2_px"], r["head_px"] = float(r["s2"].price), float(r["head"].price)
    return r


def hs_order(ctx, sd, i: int, p, session: str, risk_mult: float):
    """new-hs-fade (cc03_008 ~6:30 / ~7:11): with the bias for this side, a same-side HTF array at price (when there is a confluence object)
    and a head and shoulders on the hs_tf bars whose neckline lows are still untraded since the right shoulder was confirmed: a resting buy limit at
    (ts_cc_below_pts under) the neckline lows, armed once per neckline; stop hs_stop_pts below the entry (else the ts_max_pts stop of the
    cc_limit); targets [the right shoulder S2 (partial), the head + buffer]. Short: the inverse pattern on mirrored prices. Re-selling a
    re-run level is not built."""
    S = _S()
    if getattr(ctx, "cur_bias", 0) != sd.sign:
        return None
    hs = hs_pattern(ctx, sd, i, p)
    if hs is None:
        return None
    v = hs["neck"]
    sent = sd.__dict__.setdefault("_hs_sent", set())
    kb = hs["kb"]
    if (session, round(v, 9)) in sent or not (sd.c[i] > v and sd.l[i] >= v) or kb > i or sd.l[kb:i + 1].min(initial=np.inf) < v:
        return None
    cf = getattr(ctx, "conf", None)
    if cf is not None:
        now = ctx.idx[i] + pd.Timedelta(minutes=ctx.tf)
        if not S._htf_array(cf.at(now, sd.x(float(sd.c[i])), sd.sign), p):
            return None
    sent.add((session, round(v, 9)))
    entry = v - p.ts_cc_below_pts * p.es_pt
    stop = entry - p.hs_stop_pts * p.es_pt if p.hs_stop_pts > 0 else v - p.ts_max_pts * p.es_pt - p.pad
    sw = dict(session=session, name="hs_neck", level=v, key="hs_neck", ext=entry, ext_i=i, broke=None, sweep_i=i,
              smt=None, smt2=None)
    tags = dict(unicorn=False, fvg_bottom=stop, fvg_ce=(entry + stop) / 2, entry_kind="hs_fade",
                mitigation=False, propulsion=False, lv_tags=["hs_fade"])
    fixed = [(hs["s2_px"], "array"), (S._exit_px(hs["head_px"], "pool", p), "pool")]
    return S._finish_order(ctx, sd, i, p, session, sw, entry, stop, risk_mult, sd.h[i], tags, skip_leg_pd=True, fixed=fixed)
