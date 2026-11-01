"""Caption-gap pass (digests/rulebook_gaps/*.md), package setups_models, chunk 6 of 7: the engine glue of its 36 specs from models_setups_entries.md (items 113-117, 119-121, 123, 125, 127, 130-132,
134-136, 139, 142-146, 148-150, 153, 163, 181, 189, 191, 193-196, 198).

Same conventions as sm2.py ... sm5.py: side space (shorts run mirrored prices), a bar is used only after it closes (`i` = the last CLOSED bar, an order armed on it fills from bar i+1), an object only
from the bar that completes it, daily / weekly objects only after their session closes (everything reads `ctx.hist`, the COMPLETED prior sessions, plus today's bars through the bar being judged).
Every function sits behind a Params switch of the "caption-gap pass, setups_models #6/7" block; interpretations the sources do not pin down are marked [our interpretation]. `HITS` is sm2's counter
dict (tests: proof that a switch's code path RAN).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import levels as L
from . import sm2, sm3, sm4, sm5

HITS = sm2.HITS
hit = sm2.hit

MIN1 = 1e-9

# the entry kinds that are an order block entry (ob_below_open / eq_fresh_ob)
OB_KINDS = frozenset({"ob_pre", "ob_anchor", "arr_ob", "arr_ob_post", "arr_ob_secondary"})


def _S():
    from . import strategy as S
    return S


def _c(ctx) -> dict:
    return ctx.__dict__.setdefault("_sm6", {})


def _want(ctx) -> int:
    return sm2.want(ctx)


def _tol(p) -> float:
    return p.eq_tol_pts * p.es_pt


_DEFER: list = []


def _dh(name: str) -> None:
    """Defer a counter until the function returns an order (review fix: the counters prove an ORDER was produced, not that a candidate builder ran)."""
    _DEFER.append(name)


def _counted(fn):
    import functools

    @functools.wraps(fn)
    def w(*a, **k):
        del _DEFER[:]
        r = fn(*a, **k)
        if r is not None:
            for n in _DEFER:
                hit(n)
        del _DEFER[:]
        return r
    return w



# --- timeframe bars of the day frame -------------------------------------------------------------------------------------------------------------------

def tf_groups(ctx, sd, m: int):
    """The m-minute bars of the day frame (clock aligned) in side space: (first, last, done, o, h, l, c) arrays; `done` = the bar's last base bar closed (so bar `last <= i` is complete at i). None
    when m cannot be built from the base bars."""
    if m < ctx.tf or m % ctx.tf:
        return None
    c = _c(ctx)
    key = ("tfg", sd.sign, m)
    if key not in c:
        idx = ctx.idx
        if m == ctx.tf:
            n = len(idx)
            first = last = np.arange(n)
            done = np.ones(n, bool)
            o, h, l, cl = sd.o, sd.h, sd.l, sd.c
        else:
            fl = idx.floor(f"{m}min")
            b = pd.Series(np.arange(len(fl)), index=fl).groupby(level=0)
            first, last = b.min().values, b.max().values
            starts = b.min().index
            done = np.asarray((idx[last] - starts) >= pd.Timedelta(minutes=m - ctx.tf))
            o, cl = sd.o[first], sd.c[last]
            h = np.array([sd.h[a:z + 1].max() for a, z in zip(first, last)])
            l = np.array([sd.l[a:z + 1].min() for a, z in zip(first, last)])
        c[key] = (first, last, done, o, h, l, cl)
    return c[key]


# --- 113 M1-short-sell-side-of-buy-curve / 132 M12-contrarian-pmh: the counter-bias sides -------------------------------------------------------------

def curve_target(ctx, sd, i: int, p, w_: int):
    """113 (cc04_007 ~00:01:21): the bias `w_` points the other way than this side (an MMBM draw up, this side short) and an untouched HTF array of the bias side lies beyond the market (a discount
    array below for a draw up) - the near edge of the nearest one in this side's space (its single target), else None. Untouched = valid on the Confluence table and today's bars never traded into it
    (a decline that already happened has nothing left to short)."""
    cf = getattr(ctx, "conf", None)
    if cf is None or not w_ or w_ == sd.sign:
        return None
    now, kb = sm2.now_ts(ctx, i), ctx.idx[ctx.start]
    px = float(sd.x(sd.c[i]))
    lo_d, hi_d = float(ctx.l[ctx.start:i + 1].min()), float(ctx.h[ctx.start:i + 1].max())
    best = None
    for top, bot, tf, sc, kn in cf.valid(now, int(w_), ("D", "4h", "1h"), (0, 1, 3), kb):
        if w_ > 0 and top < px and lo_d > top + MIN1:
            edge = float(top)
        elif w_ < 0 and bot > px and hi_d < bot - MIN1:
            edge = float(bot)
        else:
            continue
        if best is None or abs(edge - px) < abs(best - px):
            best = edge
    return None if best is None else float(sd.x(best))


def pm_level(ctx, sd):
    """The previous month's extreme this side raids (side space: the month low of a long, the month high of a short mirrored) or None."""
    hl = getattr(ctx, "pm_", None)
    if hl is None:
        return None
    return float(sd.x(hl[1] if sd.sign > 0 else hl[0]))


def pm_swept(ctx, sd, i: int) -> bool:
    v = pm_level(ctx, sd)
    return v is not None and float(sd.l[ctx.start:i + 1].min()) < v - MIN1


def counter_kind(ctx, sd, i: int, p, w_: int) -> str:
    """The counter-bias reason that lets this side be scanned against the bias `w_`: "curve" (113), "pmh" (132) or "" (none)."""
    if p.curve_short and curve_target(ctx, sd, i, p, w_) is not None:
        return "curve"
    if p.pmh_contrarian and pm_swept(ctx, sd, i):
        return "pmh"
    return ""


# --- 114 / 116 consolidation EQ / origin OB -------------------------------------------------------------------------------------------------------------

@_counted
def consol_eq_order(ctx, sd, i: int, p, session: str, risk_mult: float):
    """A12-ob-at-consolidation-eq-and-eq-retest (cc01_001 ~00:11:11, ~00:18:01) + new-retrace-to-origin-ob (cc01_002 ~00:18:12), side space: a consolidation defined by candle BODIES (the bars before
    the breakout, >= consol_bars of them, body range <= consol_max_pts) and the first close above its body high (the impulse). consol_eq_mode: "ob" = a limit at the open of the last down-close candle of the
    range when it lies within 25% of the range height of the EQ [our interpretation of "near or at EQ"]; "eq" = a limit at the range EQ; "origin_ob" = that candle at any location, cancelled on a body close
    under its MT. Stop under the OB / range low, one target beyond the impulse high [our interpretation: the breakout bar's high]; no retrace = no trade (the limit rests, then expires)."""
    S = _S()
    if _want(ctx) not in (0, sd.sign):
        return None
    n, mx = p.consol_bars, p.consol_max_pts * p.es_pt
    j = i
    a = j - n
    if a < ctx.start:
        return None
    top_b, bot_b = np.maximum(sd.o, sd.c), np.minimum(sd.o, sd.c)
    hi, lo = float(top_b[a:j].max()), float(bot_b[a:j].min())
    if hi - lo > mx + MIN1:
        return None
    while a - 1 >= ctx.start and max(hi, float(top_b[a - 1])) - min(lo, float(bot_b[a - 1])) <= mx + MIN1:
        a -= 1
        hi, lo = max(hi, float(top_b[a])), min(lo, float(bot_b[a]))
    if not sd.c[j] > hi + p.tick - MIN1:
        return None
    sent = sd.__dict__.setdefault("_consol6_sent", set())
    key = (a, round(hi, 4), round(lo, 4))
    if key in sent:
        return None
    eq, height = (hi + lo) / 2, hi - lo
    mode = p.consol_eq_mode
    extra = {}
    if mode == "eq":
        entry, stop = eq, lo - p.pad
    else:
        ks = [k for k in range(a, j) if sd.c[k] < sd.o[k]]
        if not ks:
            return None
        k = ks[-1]
        mid = float((sd.o[k] + sd.c[k]) / 2)
        if mode == "ob" and abs(mid - eq) > 0.25 * height + MIN1:
            return None
        entry, stop = float(sd.o[k]), min(float(sd.l[k]), lo) - p.pad
        if mode == "origin_ob":
            extra["cancel_close"] = mid
    imp = float(sd.h[j])
    if not entry < sd.c[i] - MIN1 or entry - stop < p.min_risk_pts * p.es_pt or imp <= entry:
        return None
    sent.add(key)
    _dh("consol_eq")
    fixed = [(float(S._exit_px(imp, "pool", p)), "pool")]
    return sm4._order(ctx, sd, i, p, session, risk_mult, "consol_eq", float(entry), float(stop), level=hi, ext=lo, ext_i=a, broke=j, fixed=fixed, lv=("consol_" + mode,), **extra)


# --- 115 / 146 void trades ---------------------------------------------------------------------------------------------------------------------------------

def mss_fvg(sd, a: int, i: int):
    """After the swing low at bar a (side space): the MSS = the first close above the last swing high formed after a (confirmed by i); the entry = the top of the first bullish FVG at / after the
    break that no close went through yet and that lies under the close. (entry, bottom, break bar) or None."""
    ph = [q for q in sd.ph if q.i > a and q.known <= i]
    if not ph:
        return None
    q = ph[-1]
    ks = np.flatnonzero(sd.c[q.known:i + 1] > q.price)
    if not len(ks):
        return None
    b = q.known + int(ks[0])
    for g in sd.gaps:
        if b - 1 <= g.i <= i and g.i - 2 >= a and sd.c[g.i + 1:i + 1].min(initial=np.inf) >= g.bottom - MIN1 and g.top < sd.c[i] - MIN1:
            return float(g.top), float(g.bottom), b
    return None


def _voids(ctx, sd):
    c = _c(ctx)
    key = ("voids", sd.sign)
    if key not in c:
        c[key] = L.voids(sd.h, sd.l)
    return c[key]


@_counted
def void_order(ctx, sd, i: int, p, session: str, risk_mult: float):
    """A10-void-retrace-trades (cc01_001 ~00:15:21; cc03_001 ~00:47:58) + new-post-void-fill-gap-sell (cc04_010 ~00:12:41), side space. A void = `levels.voids` (a true price gap between two
    candles, no overlap). Bull void (an up-leg L -> H):
      "range"  - no sweep armed and none in the last void_idle_bars bars, price above the void CE, the CE not yet touched: a limit at the CE, stop under the leg origin L (the lowest low of the 3 bars
                 before the void), the single target = the leg extreme H (the known range, no runner);
      "cont"   - price traded back to the void origin (its bottom) and the normal MSS + FVG followed: the FVG top, stop under the origin, the target BEYOND the leg extreme (review fix: H + pool_beyond_pts);
      "void_fill_gap" - the void's bottom was touched and two up-close bars with a gap between their bodies print 1-2 bars after it: a limit at the CE of that body gap, stop under the fill low,
                 the ladder = the relative equal highs formed before the fill (else the normal targets).
    Bear void (a down-leg): "fill" - an MSS up after the leg's low: the FVG top, stop under the low, the target = the void's top edge. One order per void and kind."""
    S = _S()
    if _want(ctx) not in (0, sd.sign):
        return None
    vt = set(p.void_trades)
    sent = sd.__dict__.setdefault("_void6_sent", set())
    tk, tol = float(p.tick), _tol(p)
    for z in reversed(_voids(ctx, sd)):
        if z.i > i or z.i < ctx.start + 1:
            continue
        if z.kind == "bull":
            H = float(sd.h[z.i:i + 1].max())
            L0 = float(sd.l[max(0, z.i - 3):z.i].min())
            ce = (float(z.top) + float(z.bottom)) / 2
            if "range" in vt and ("r", z.i) not in sent and sd.sweep is None and i - sd.__dict__.get("_sweep_seen6", -10 ** 9) > p.void_idle_bars and sd.c[i] > ce + tk \
                    and float(sd.l[z.i + 1:i + 1].min(initial=np.inf)) > ce and H > ce + p.min_risk_pts * p.es_pt and ce - (L0 - p.pad) >= p.min_risk_pts * p.es_pt:
                sent.add(("r", z.i))
                _dh("void_range")
                return sm4._order(ctx, sd, i, p, session, risk_mult, "void_range", ce, L0 - p.pad, level=float(z.top), ext=L0, ext_i=max(0, z.i - 3), broke=z.i,
                                  fixed=[(float(S._exit_px(H, "pool", p)), "pool")], lv=("void_range",))
            kf = next((k for k in range(z.i + 1, i + 1) if sd.l[k] <= z.bottom + MIN1), None)
            if kf is None:
                continue
            if "cont" in vt and ("c", z.i) not in sent:
                r = mss_fvg(sd, kf, i)
                if r is not None:
                    entry, fb, b = r
                    stop = min(L0, float(sd.l[kf:i + 1].min())) - p.pad
                    if entry - stop >= p.min_risk_pts * p.es_pt and H > entry:
                        sent.add(("c", z.i))
                        _dh("void_cont")
                        return sm4._order(ctx, sd, i, p, session, risk_mult, "void_cont", entry, stop, level=float(z.bottom), ext=float(sd.l[kf:i + 1].min()), ext_i=kf, broke=b,
                                          fixed=[(float(H + max(p.pool_beyond_pts * p.es_pt, tk)), "pool")], lv=("void_cont",), fvg_bottom=fb)
            if "void_fill_gap" in vt and ("g", z.i) not in sent and kf + 1 <= i - 1 <= kf + 2 and sd.c[i - 1] > sd.o[i - 1] and sd.c[i] > sd.o[i] and sd.o[i] > sd.c[i - 1] + MIN1:
                entry = float((sd.c[i - 1] + sd.o[i]) / 2)
                stop = float(sd.l[kf:i + 1].min()) - p.pad
                if entry < sd.c[i] and entry - stop >= p.min_risk_pts * p.es_pt:
                    sent.add(("g", z.i))
                    _dh("void_fill_gap")
                    eq = [v for v in S._eq_levels(sd, kf, tol, False, p) if v > entry + p.min_risk_pts * p.es_pt]
                    fixed = [(float(S._exit_px(v, "pool", p)), "pool") for v in sorted(eq)] or None
                    return sm4._order(ctx, sd, i, p, session, risk_mult, "void_fill_gap", entry, stop, level=float(z.bottom), ext=float(sd.l[kf:i + 1].min()), ext_i=kf, broke=i,
                                      fixed=fixed, lv=("void_fill_gap",))
        elif "fill" in vt and ("f", z.i) not in sent:
            seg = sd.l[z.i:i + 1]
            kl = z.i + int(np.argmin(seg))
            if kl >= i or float(sd.h[z.i + 1:i + 1].max(initial=-np.inf)) >= z.top - MIN1:
                continue                                          # the void is already filled / no leg low yet
            r = mss_fvg(sd, kl, i)
            if r is not None:
                entry, fb, b = r
                stop = float(sd.l[kl]) - p.pad
                if entry - stop >= p.min_risk_pts * p.es_pt and z.top > entry:
                    sent.add(("f", z.i))
                    _dh("void_fill")
                    return sm4._order(ctx, sd, i, p, session, risk_mult, "void_fill", entry, stop, level=float(z.top), ext=float(sd.l[kl]), ext_i=kl, broke=b,
                                      fixed=[(float(S._exit_px(float(z.top), "array", p)), "array")], lv=("void_fill",), fvg_bottom=fb)
    return None


# --- 121 failed turtle soup -> continuation ------------------------------------------------------------------------------------------------------------

@_counted
def ts_cont_order(ctx, sd, i: int, p, session: str, risk_mult: float):
    """M12-quick-rejection-required (cc01_006 ~00:14:24; cc04_002 ~00:25:05), side space = the run goes UP: an old high V (a pool of the opposite side's sweep machine) was run by bar j today, and the
    price did not reverse - the >= ts_cont_bars bars after j all CLOSED above V (less one tolerance), a sideways range holding the run: that is no turtle soup, it is a continuation. The entry
    follows the normal path [our interpretation]: the first close above that small range's high (the MSS), a limit at the top of the FVG that break left (else the broken range high), the stop under the
    range low, the normal targets."""
    S = _S()
    if _want(ctx) not in (0, sd.sign):
        return None
    other = sm2.other_side(ctx, sd, p)
    lv = S._sell_side(ctx, other, session, i, p.extra_pools, p)
    sent = sd.__dict__.setdefault("_tsc6_sent", set())
    tol, tk = _tol(p), float(p.tick)
    for k, v_o in sorted(lv.items(), key=lambda kv: kv[1]):       # the highest old high first (side space V = -v_o)
        V = -float(v_o)
        js = np.flatnonzero(sd.h[ctx.start:i + 1] > V + tk - MIN1)
        if not len(js):
            continue
        j = ctx.start + int(js[0])
        if (k, j) in sent or i - j < p.ts_cont_bars + 1 or float(sd.c[j + 1:i + 1].min()) < V - tol:
            continue
        rh = float(sd.h[j + 1:i].max())
        if not sd.c[i] > rh + MIN1 or float(sd.c[j + 1:i].max()) > rh:
            continue
        rl = float(sd.l[j + 1:i + 1].min())
        if rh - rl > p.consol_max_pts * p.es_pt:
            continue                                                  # not a small sideways range [our interpretation: <= consol_max_pts]
        g = [g for g in sd.gaps if g.i in (i - 1, i) and g.top < sd.c[i] - MIN1]
        entry = float(g[-1].top) if g else rh
        stop = rl - p.pad
        if not entry < sd.c[i] - MIN1 or entry - stop < p.min_risk_pts * p.es_pt:
            continue
        sent.add((k, j))
        _dh("ts_cont")
        return sm4._order(ctx, sd, i, p, session, risk_mult, "ts_cont", entry, stop, level=V, ext=rl, ext_i=j, broke=i, lv=("ts_cont",))
    return None


# --- 143 rejection block entries ---------------------------------------------------------------------------------------------------------------------------

@_counted
def rb_order(ctx, sd, i: int, p, session: str, risk_mult: float):
    """A17-rejection-block-entries (cc04_006 ~00:10:39, ~00:11:19), side space (a long off the rejection block of a swing LOW; the short is its mirror): the trigger = the block's body extreme (the lowest
    open / close of the swing, `levels.rejection_blocks`), the wick low W under it. rb_entry "limit" = the aggressive limit AT the trigger (price above it, not yet touched), stop under W; "stop" = the
    conservative buy-stop one tick over the trigger: armed only after a bar traded through the trigger by >= 1 tick WITHOUT a new wick low (>= W) while the close is still under the trigger, cancelled
    on a new wick low (cancel_low), stop under W. A block whose wick low was broken is dead. One order per block (formed today)."""
    c = _c(ctx)
    key = ("rb", sd.sign, p.pivot_n, p.rb_min_wick_frac, p.rb_level)
    if key not in c:
        c[key] = [z for z in L.rejection_blocks(sd.o, sd.h, sd.l, sd.c, p.pivot_n, p.rb_min_wick_frac, p.rb_level) if z.kind == "bull"]
    sent = sd.__dict__.setdefault("_rb6_sent", set())
    if _want(ctx) not in (0, sd.sign):
        return None
    tk = float(p.tick)
    for z in sorted(c[key], key=lambda z: -z.i):
        if z.i > i or z.src < ctx.start or z.i in sent:
            continue
        trig, wick = float(z.top), float(z.bottom)
        low_since = float(sd.l[z.i + 1:i + 1].min(initial=np.inf))
        if low_since < wick - MIN1:
            continue
        stop = wick - p.pad
        if p.rb_entry == "limit":
            if not trig < sd.c[i] - MIN1 or low_since <= trig + MIN1 or trig - stop < p.min_risk_pts * p.es_pt:
                continue
            sent.add(z.i)
            _dh("rb_limit")
            return sm4._order(ctx, sd, i, p, session, risk_mult, "rb_entry", trig, stop, level=trig, ext=wick, ext_i=int(z.src), broke=i, lv=("rb_limit",), fvg_bottom=wick)
        if not (low_since < trig - tk + MIN1 and sd.c[i] < trig - MIN1):
            continue
        entry = trig + tk
        if entry - stop < p.min_risk_pts * p.es_pt:
            continue
        sent.add(z.i)
        _dh("rb_stop")
        return sm4._order(ctx, sd, i, p, session, risk_mult, "rb_entry", entry, stop, level=trig, ext=wick, ext_i=int(z.src), broke=i, lv=("rb_stop",), fvg_bottom=wick,
                          stop_entry=True, cancel_low=wick)
    return None


# --- 193 / 194 consolidation edge / inner fade ------------------------------------------------------------------------------------------------------------

def consol_ranges(ctx, sd, i: int, p) -> list:
    """The candidate 1h / 15m ranges completed before bar i: the last consol_bars completed consol_tf bars ending at each of the latest completed bars, at most consol_width_adr x ADR5 wide (side
    space): [(low, high, eq, first base bar, last base bar)], newest window first."""
    g = tf_groups(ctx, sd, p.consol_tf)
    adr = sm2.adr5(ctx)
    if g is None or not adr:
        return []
    first, last, done, o, h, l, cl = g
    ok = np.flatnonzero(done & (last < i))
    n = p.consol_bars
    out = []
    for e in range(len(ok) - 1, max(len(ok) - 9, n - 2), -1):
        sel = ok[e - n + 1:e + 1]
        if len(sel) < n:
            break
        hi, lo = float(h[sel].max()), float(l[sel].min())
        if hi - lo <= p.consol_width_adr * adr + MIN1:
            out.append((lo, hi, (lo + hi) / 2, int(first[sel[0]]), int(last[sel[-1]])))
    return out


@_counted
def consol_fade_order(ctx, sd, i: int, p, session: str, risk_mult: float):
    """new-consolidation-outer-edge-fade (cc09_004 ~00:12:08) + new-inside-range-expansion-fade (~00:15:37), side space, the bias must be this side (a breakout against the HTF bias is never taken).
    Review fix: the sweep arms a RESTING LIMIT (consol_edge_entry "limit", default - the rulebook has no market entries for the reversal models); the first build's market order at the close back inside
    stays as the value "market".
    "edge" - the range is intact (nothing traded a tick under its low yet): limit just under the range low (ts_cc_below_pts, at least a tick, under it = the "buy those sell stops" fill), stop
             ts_max_pts under the low (a deeper run is a real break, as the cc_limit raid), the single target = the range EQ (not the opposite end). "market": the first close back above the
             low after a sweep, entered at that close, stop under the sweep extreme;
    "inner" - a 3-bar swing low just under the EQ (within consol_eq_band of the range height) not yet traded through, the range still intact: limit just under that pivot (the expansion away from the
             EQ fills it), stop just outside the range (under its low), the target the far end of the range (its high, less the exit buffer). "market": the close of the bar that traded through it.
    The break is not an MSS. One per range / pivot."""
    S = _S()
    if _want(ctx) != sd.sign:
        return None
    sent = sd.__dict__.setdefault("_cfade6_sent", set())
    tk = float(p.tick)
    lim = p.consol_edge_entry == "limit"
    for lo, hi, eq, fa, la in consol_ranges(ctx, sd, i, p):
        if sd.h[la + 1:i + 1].max(initial=-np.inf) > hi + tk:
            continue
        if p.consol_edge_fade in ("edge", "both") and ("e", round(lo, 4), la) not in sent:
            if lim:
                entry = lo - max(p.ts_cc_below_pts * p.es_pt, tk)
                stop = lo - p.ts_max_pts * p.es_pt - p.pad
                if sd.l[la + 1:i + 1].min(initial=np.inf) >= lo - tk + MIN1 and entry + MIN1 < sd.c[i] and eq > entry + MIN1 and entry - stop >= p.min_risk_pts * p.es_pt:
                    sent.add(("e", round(lo, 4), la))
                    _dh("consol_edge")
                    return sm4._order(ctx, sd, i, p, session, risk_mult, "consol_edge", entry, stop, level=lo, ext=stop + p.pad, ext_i=i, broke=i,
                                      fixed=[(float(S._exit_px(eq, "array", p)), "array")], lv=("consol_edge",))
            else:
                k0 = next((k for k in range(la + 1, i + 1) if sd.l[k] < lo - tk + MIN1), None)
                if k0 is not None and sd.c[i] > lo + MIN1 and not (sd.c[k0:i] > lo).any():
                    stop = float(sd.l[k0:i + 1].min()) - p.pad
                    entry = float(sd.c[i])
                    if entry - stop >= p.min_risk_pts * p.es_pt and eq > entry:
                        sent.add(("e", round(lo, 4), la))
                        _dh("consol_edge")
                        return sm4._order(ctx, sd, i, p, session, risk_mult, "consol_edge", entry, stop, level=lo, ext=float(sd.l[k0:i + 1].min()), ext_i=k0, broke=i, market=True,
                                          fixed=[(float(S._exit_px(eq, "array", p)), "array")], lv=("consol_edge",))
        if p.consol_edge_fade in ("inner", "both") and sd.l[la + 1:i + 1].min(initial=np.inf) >= lo - MIN1:
            for q in sd.pl:
                if not (fa <= q.i <= la and q.known <= i - 1) or ("i", q.i) in sent:
                    continue
                if not (eq - p.consol_eq_band * (hi - lo) - MIN1 <= q.price < eq) or sd.l[q.i + 1:i].min(initial=np.inf) < q.price - MIN1:
                    continue
                if lim:
                    entry, stop = float(q.price) - tk, lo - p.pad
                    if sd.l[q.i + 1:i + 1].min(initial=np.inf) >= q.price - MIN1 and entry + MIN1 < sd.c[i] and entry - stop >= p.min_risk_pts * p.es_pt and hi > entry:
                        sent.add(("i", q.i))
                        _dh("consol_inner")
                        return sm4._order(ctx, sd, i, p, session, risk_mult, "consol_inner", entry, stop, level=float(q.price), ext=lo, ext_i=i, broke=i,
                                          fixed=[(float(S._exit_px(hi, "pool", p)), "pool")], lv=("consol_inner",))
                elif sd.l[i] < q.price - tk + MIN1:
                    entry, stop = float(sd.c[i]), float(sd.l[i]) - p.pad
                    if entry - stop >= p.min_risk_pts * p.es_pt and hi > entry:
                        sent.add(("i", q.i))
                        _dh("consol_inner")
                        return sm4._order(ctx, sd, i, p, session, risk_mult, "consol_inner", entry, stop, level=float(q.price), ext=float(sd.l[i]), ext_i=i, broke=i, market=True,
                                          fixed=[(float(S._exit_px(hi, "pool", p)), "pool")], lv=("consol_inner",))
    return None


# --- 145 vacuum block entries ----------------------------------------------------------------------------------------------------------------------------

@_counted
def vb_order6(ctx, sd, i: int, p, session: str, risk_mult: float):
    """L8-vacuum-block-entries (cc04_009 ~00:07:24, ~00:10:12, ~00:14:37), bullish terms (the short mirrors): at the close of the gap bar k (or the next two) the vacuum block (pre-gap close .. gap
    open) with the buy-side liquidity above the gap candle's high still untaken (a swing high above it that no bar traded): vb_entry "partial" = a limit at the TOP of the highest down-close candle of the
    pre-gap run (since the last swing low), stop under that run's lowest low, out when no bar closes above the fill within vb_react_bars (manage); "full" = a limit at VB_low = the pre-gap close
    (the last pre-gap up candle's close), stop under the run's low; "auto" = full for a gap before 10:00, partial after. The OB inside a bearish gap (the short's alternative) is not built."""
    S = _S()
    sent = sd.__dict__.setdefault("_vb6_sent", set())
    for k, bot, top in sm3.vb_gaps(ctx, sd, p):
        if k > i or i - k > 2 or k in sent:
            continue
        pre = [q for q in sd.pl if q.i < k and q.known <= k - 1]
        r0 = pre[-1].i if pre else max(ctx.start - 1, k - 12, 0)
        r0 = max(r0, 0)
        if r0 >= k:
            continue
        run_low = float(sd.l[r0:k].min())
        mode = p.vb_entry
        if mode == "auto":
            mode = "full" if int(ctx.t[k]) < 600 else "partial"
        ups = [x for x in range(r0, k) if sd.c[x] > sd.o[x]]
        vbl = float(sd.c[ups[-1]]) if ups else float(bot)          # review fix: VB_low = the close of the LAST pre-gap UP candle (not simply the previous bar's close)
        gh = float(sd.h[k])
        liq = [q.price for q in sd.ph if q.known <= i and q.price > gh + MIN1 and float(sd.h[k:i + 1].max()) < q.price - MIN1]
        if not liq:
            continue
        if mode == "full":
            entry = vbl
        else:
            dn = [x for x in range(r0, k) if sd.c[x] < sd.o[x]]
            if not dn:
                continue
            entry = float(sd.h[max(dn, key=lambda x: sd.h[x])])
        stop = run_low - p.pad
        if not entry < sd.c[i] - MIN1 or entry - stop < p.min_risk_pts * p.es_pt:
            continue
        sent.add(k)
        _dh("vb_" + mode)
        sw = sm3._synth(S, session, "vb", bot, run_low, r0, k)
        tags = dict(unicorn=False, fvg_bottom=run_low, fvg_ce=(entry + run_low) / 2, entry_kind="vb", mitigation=False, propulsion=False, no_leg_wait=True, skip_po3=not p.synth_po3,
                    lv_tags=["vb_" + mode], sm6=dict(kind="vb", mode=mode, vb_low=vbl, top=float(top), reach=False))
        return S._finish_order(ctx, sd, i, p, session, sw, entry, stop, risk_mult, float(sd.h[k:i + 1].max()), tags, skip_leg_pd=True)
    return None


# --- array candidates (entry_arrays: ob_secondary / propulsion / last_offer / ob62) -----------------------------------------------------------------------

def secondary_cand(ctx, sd, sw, i: int, p):
    """A12-secondary-ob (cc02_004 ~00:03:14): while price retraces into the primary OB (the sweep's down-close candle[s]), the first down-close candle after it that OPENS inside the primary zone is a
    secondary OB: (entry = its open - or its MT with ob_entry_px "mt" -, bottom = its low, kind). Invalid on a body close under its MT (the order carries cancel_close = MT); once a close under it
    went by, the candle is dead."""
    S = _S()
    ob = S._ob_at_low(sd, sw, i, p, ctx)
    if ob is None:
        return None
    tol = _tol(p)
    for j in range(ob["k"] + 1, i + 1):
        # review fix: the candle must OPEN inside the primary zone (between its low and its high), and a dead candidate (a body closed under its MT) does not end the search
        if sd.c[j] < sd.o[j] and ob["lo"] - tol <= sd.o[j] <= ob["hi"] + tol and sd.l[j] <= ob["hi"] + tol:
            mt = float((sd.o[j] + sd.c[j]) / 2)
            if sd.c[j + 1:i + 1].min(initial=np.inf) < mt:
                continue
            sw["_ob_sec_mt"] = mt
            sw["_ob_sec_k"] = j
            return (mt if p.ob_entry_px == "mt" else float(sd.o[j]), float(sd.l[j]), "ob_secondary")
    return None


def prop_cands(ctx, sd, sw, i: int, p) -> list:
    """A16-propulsion-entries (cc04_008 ~00:01:49, ~00:06:53): a propulsion block formed after the sweep (`Side.propulsions`, both sides by mirroring): a limit at the block's high (the deepest fill is
    its MT: the stop sits just beyond the MT, a body close under it cancels). The FIRST return only: the departure is the first close above the block's high after it formed; the order is armed from that
    close until a bar has traded back down to the block's high (the return, filled or not). With prop_second a block that was already returned to is entered again on the next return (review fix: the first
    return used to count as "broken" before any order could arm, so only prop_second ever produced one). [(entry, bottom = MT, kind)]; `sw["_prop_2nd"]` marks the second-entry candidates."""
    out = []
    for z in sd.propulsions():
        if z.i > i or z.i < sw["ext_i"]:
            continue
        mt = float(z.mt) if z.mt == z.mt else float(z.mid)
        if sd.c[z.i + 1:i + 1].min(initial=np.inf) < mt - MIN1:
            continue
        dep = next((j for j in range(z.i + 1, i + 1) if sd.c[j] > z.top + MIN1), None)
        if dep is None:
            continue                                                  # no departure yet: nothing to return to
        returned = bool((sd.l[dep + 1:i + 1] <= z.top + MIN1).any())
        if returned and not p.prop_second:
            continue
        sw["_prop_mt"] = mt
        sw.setdefault("_prop_2nd", {})[float(z.top)] = returned
        out.append((float(z.top), mt, "propulsion"))
    return out


def chosen(sw, kind: str, entry: float) -> None:
    """The counters of the new array kinds are bumped here - when the kind WON the pick and an order is built - not where the candidate is listed (review fix: they proved only that a candidate builder ran)."""
    if kind == "propulsion":
        hit("prop_second" if (sw.get("_prop_2nd") or {}).get(float(entry)) else "propulsion")
    elif kind in ("ob_secondary", "last_offer"):
        hit(kind)
    elif kind == "ob62":
        hit("ote_ob62")


def offer_cand(ctx, sd, sw, i: int, p):
    """new-last-buyside-offered-level (cc04_012 ~00:15:37), side space: L = the high of the last DOWN-close candle before >= offer_run consecutive up-close candles (the last point where sell-side was
    delivered before the one-sided buy-side run; the real short's "low of the last up-close candle"). Once price closed above L the first return to L is the zone. The spec's ladder (L and a step beyond
    it, `offer_step_pts`) is one resting limit at L + step here (it fills first on the way back down) [our interpretation: the E12 split is not built]; the stop = under that candle's low."""
    e, n = sw["ext_i"], p.offer_run
    for k in range(i - n, e - 1, -1):
        if k < 0 or not sd.c[k] < sd.o[k]:
            continue
        if all(sd.c[x] > sd.o[x] for x in range(k + 1, k + 1 + n)) and k + n <= i:
            Lv = float(sd.h[k])
            if sd.c[i] > Lv + MIN1:
                return (min(Lv + p.offer_step_pts * p.es_pt, float(sd.c[i]) - p.tick), float(sd.l[k]), "last_offer")
            return None
    return None


def ob62_cand(ctx, sd, sw, i: int, p):
    """M13-bodies-stall-62-ob (cc01_005 ~00:13:59), ote="ob62": a down-close bar (side space) after the sweep whose BODY bottom sits within one tick of the 62% retracement of the leg while its wick
    pokes below it: a limit at that bar's open, the stop under the leg low (the sweep extreme)."""
    S = _S()
    e = sw["ext_i"]
    leg_hi = float(sd.h[e:i + 1].max())
    base = S._LD.leg_low(sd, sw, i, p, leg_hi)
    lvl = leg_hi - L.OTE_LO * (leg_hi - base)
    tk = float(p.tick)
    for j in range(i, e, -1):
        bb = float(min(sd.o[j], sd.c[j]))
        if sd.c[j] < sd.o[j] and abs(bb - lvl) <= tk + MIN1 and sd.l[j] < bb - MIN1:
            return (float(sd.o[j]), float(base), "ob62")
    return None


def arr_cands6(ctx, sd, sw, i: int, p, ea: set) -> list:
    out = []
    if "ob_secondary" in ea:
        r = secondary_cand(ctx, sd, sw, i, p)
        if r is not None:
            out.append(r)
    if "propulsion" in ea:
        out += prop_cands(ctx, sd, sw, i, p)
    if "last_offer" in ea:
        r = offer_cand(ctx, sd, sw, i, p)
        if r is not None:
            out.append(r)
    if p.ote == "ob62":
        r = ob62_cand(ctx, sd, sw, i, p)
        if r is not None:
            out.append(r)
    return out


def pick_array(cs: list, p):
    """A15-mitigation-block-sell-entry (cc05_014 ~00:07:47): entry_arrays_order - the first kind of the list that has a candidate wins (its highest entry), else the highest entry of all."""
    for kd in p.entry_arrays_order:
        sub = [x for x in cs if x[2] == kd]
        if sub:
            hit("entry_arrays_order")
            return max(sub)
    return max(cs)


def array_tags(sw, kind: str, tags: dict) -> None:
    """Cancel lines of the new array kinds: a body close under the candle's MT."""
    if kind == "ob_secondary" and sw.get("_ob_sec_mt") is not None:
        tags["cancel_close"] = float(sw["_ob_sec_mt"])
    if kind == "propulsion" and sw.get("_prop_mt") is not None:
        tags["cancel_close"] = float(sw["_prop_mt"])


# --- 117 OTE trigger -----------------------------------------------------------------------------------------------------------------------------------------

def ote_trigger_ok(sd, sw, i: int, hi: float) -> bool:
    """M13-ote-needs-bias-trigger-structure (cc01_004 ~00:17:12): inside the OTE band (price traded down to its upper edge `hi`) an LTF MSS printed - a close above a swing high formed after price entered
    the band, with price still inside / under the band when it formed [our interpretation of "an LTF MSS inside the band"]."""
    hit("ote_trigger_eval")
    e = sw["ext_i"]
    j0 = next((j for j in range(e + 1, i + 1) if sd.l[j] <= hi + MIN1), None)
    if j0 is None:
        return False
    for q in sd.ph:
        if q.i < j0 or q.known > i or q.price > hi + MIN1:
            continue
        if (sd.c[q.known:i + 1] > q.price).any():
            return True
    return False


# --- 119 premium OTE turtle soup ----------------------------------------------------------------------------------------------------------------------------

def ts_ote(ctx, sd, sw, i: int, p) -> bool:
    """M13-premium-ote-turtle-soup (cc01_005 ~00:07:03), side space: the swept level lies at or beyond the EQ of the last impulse leg (the day's low before the day's high so far -> that high): the
    retracement fraction (H - level) / (H - L0) >= 0.5 (the 62-79% band included; deeper counts too). [our interpretation of "the last impulse leg" and "(or above EQ)"]"""
    a, b = ctx.start, sw["ext_i"]
    if b - a < 2:
        return False
    jH = a + int(np.argmax(sd.h[a:b]))
    H = float(sd.h[jH])
    L0 = float(sd.l[a:jH + 1].min())
    if H - L0 <= MIN1:
        return False
    adr = sm2.adr5(ctx)
    if adr and H - L0 < 0.25 * adr:
        return False                                        # review fix: a sliver is no impulse leg (a one-way down day leaves a tiny L0 -> H leg and huge ratios)
    r = (H - float(sw["level"])) / (H - L0)
    return 0.5 - MIN1 <= r <= 1.0 + MIN1                    # review fix: bounded - a level beyond the leg's origin is a new leg, not a 50-100% retracement of this one


# --- 139 body level -----------------------------------------------------------------------------------------------------------------------------------------

def level_src(ctx, sd, v: float, i: int, p) -> float:
    """E2-body-extreme-entry (cc03_008 ~00:15:43): ts_level_src "body" - the limit level of a turtle-soup fade is the extreme BODY (the lowest min(open, close), side space) of the swing candles that
    printed the pool v (bars whose low is within the equal-level tolerance of it) instead of the wick extreme; no such candle in the day frame (an older day's pool) = the wick level."""
    if p.ts_level_src != "body":
        return v
    ks = np.flatnonzero(np.abs(sd.l[:i + 1] - v) <= max(_tol(p), MIN1))
    if not len(ks):
        return v
    hit("ts_body_level")
    return float(np.minimum(sd.o[ks], sd.c[ks]).min())


def prev_pm_body(ctx, sd, lvl: float, p) -> float:
    """ts_level_src "body" for the previous-PM turtle limit: the extreme body of the previous 13:30-16:00 bars (the day frame's prior session) instead of its wick."""
    if p.ts_level_src != "body":
        return lvl
    a = np.flatnonzero((ctx.t[:ctx.start] >= 810))
    if not len(a):
        return lvl
    hit("ts_body_level")
    return float(np.minimum(sd.o[a], sd.c[a]).min())


# --- 142 breaker retests -----------------------------------------------------------------------------------------------------------------------------------

def retest_ok(sd, e: dict, i: int, p) -> bool:
    """A13-breaker-reentries-and-wait (cc04_005 ~00:04:51, ~00:01:08): with breaker_retests > 1 a breaker may create at most breaker_retests - 1 retest orders in the day-life path (the first return is
    the ordinary flow's), and every order after the first of this path needs price to have LEFT the zone by breaker_leave_pts (a high that far above the top) since the previous order, before the
    retest touches it. Review fix: the first return of the path needs no departure (it used to change the primary entry), and the order count is kept by the caller when an order is returned."""
    if p.breaker_retests <= 1:
        return True
    if e.get("n_ret", 0) >= p.breaker_retests - 1:
        return False
    if e["armed_i"] is None:
        return True
    last = e["armed_i"]
    tj = next((j for j in range(last + 1, i + 1) if sd.l[j] <= e["top"]), None)
    if tj is None or tj <= last:
        return False
    return bool(sd.h[last:tj].max() >= e["top"] + p.breaker_leave_pts * p.es_pt - MIN1)


# --- 150 near OB (cc_breaker_order) ----------------------------------------------------------------------------------------------------------------------

def near_ob_entry(sd, sw, i: int, ref: float, p) -> float:
    """M4-retest-nearer-ob-or-none (cc05_005 ~00:16:56): the retest order of the breaking point `ref` is OCO with a limit at the OPEN of the last down-close bar of the break leg (the nearer OB):
    one resting order at the nearer (higher, side space) of the two - the first reached - which is exactly "the first fill cancels the other"; neither reached = it expires / the target cancels it."""
    for k in range(i - 1, sw["ext_i"] - 1, -1):
        if sd.c[k] < sd.o[k]:
            ob = float(sd.o[k])
            if ob > ref and ob < sd.c[i] - p.tick:
                hit("cc_near_ob")
                return ob
            break
    return ref


# --- 149 two chance --------------------------------------------------------------------------------------------------------------------------------------------

def two_chance_add(ctx, sd, pos, tr, i: int, p) -> None:
    """M4-two-chance-aggressive-vs-mss-retest (cc05_005 ~00:17:52): chance 2 after a FILLED turtle soup (chance 1): once price closed above the in-between swing high (the MSS reference H before the sweep
    extreme) the return to H is an ADD (E12), once. Without a fill the sweep stays alive instead (ts_gate_mss does not drop it) and the cc_swings breaking-point order is the new order."""
    S = _S()
    st = pos.setdefault("tc6", dict(ref=None, broke=None, done=False))
    if st["done"] or pos["add"] is not None:
        return
    if st["ref"] is None:
        hs = [q.price for q in sd.ph if q.i < pos["ext_i"] and q.known <= pos["ext_i"] + 1]
        st["ref"] = float(hs[-1]) if hs else -1.0
    ref = st["ref"]
    if ref <= 0 or i <= pos["fill_i"]:
        return
    if st["broke"] is None:
        if sd.c[i] > ref:
            st["broke"] = i
        return
    if i > st["broke"] and ref < sd.c[i] and ref > pos["stop"]:
        st["done"] = True
        hit("two_chance_add")
        S._arm_add(pos, tr, float(ref), i, p, ctx.equity)


# --- exits of the tagged positions -------------------------------------------------------------------------------------------------------------------------

def on_fill(ctx, sd, pos, tr, o: dict, i: int, p) -> None:
    st = o.get("sm6")
    if st:
        pos["sm6"] = dict(st)


def manage(ctx, sd, pos, tr, i: int, ts, p) -> None:
    """Per-bar management of the positions this chunk tagged (pos["sm6"]): the vacuum-block fills - partial: out when no bar closed above the fill price within vb_react_bars of the fill (the spec's
    "immediate reaction", 1-3 candles); after the rally (a close above the gap top) a close back under VB_low exits the rest (the spec's "take partials or exit")."""
    st = pos.get("sm6")
    if not st or st.get("kind") != "vb" or i <= pos["fill_i"] or not pos["left"] or st.get("done"):
        return
    if sd.c[i] > st["top"]:
        st["reach"] = True
    fill_px = float(pos["basis"] / max(pos["n"], 1))
    if st["reach"] and sd.c[i] < st["vb_low"] - MIN1:
        st["done"] = True
        sm3._part(sd, pos, tr, ts, float(sd.c[i]), 1.0, "vb_back", p, all_=True)
        hit("vb_back6")
        return
    if st["mode"] == "partial" and not st["reach"] and i - pos["fill_i"] >= p.vb_react_bars and not (sd.c[pos["fill_i"] + 1:i + 1] > fill_px).any():
        st["done"] = True
        sm3._part(sd, pos, tr, ts, float(sd.c[i]), 1.0, "vb_timeout", p, all_=True)
        hit("vb_timeout")


# --- 131 entry discipline --------------------------------------------------------------------------------------------------------------------------------

def apply_discipline(p):
    """M12-setup-selection-order (cc03_001 ~00:45:51; cc04_002 ~00:22:09): entry_discipline is a PRESET of the other path switches - "turtle_soup" -> turtle_soup="cc_limit", the OB path off, no
    void trades; "ob_return" -> turtle_soup off, the pre_break OB, no void trades; "range_void" -> turtle_soup off, void_trades ("range",), the OB path off. Review fix: with entry_discipline_only (default) every
    order of another kind is dropped at the end of the scan (`discipline_ok`), so the FVG model after the MSS and the extra setups are off too; "any" = the configuration as is."""
    from dataclasses import replace
    d = p.entry_discipline
    hit("entry_discipline_" + d)
    if d == "turtle_soup":
        return replace(p, turtle_soup="cc_limit", ob_entry="post_mss", void_trades=())
    if d == "ob_return":
        return replace(p, turtle_soup="", ob_entry="pre_break", void_trades=())
    if d == "range_void":
        return replace(p, turtle_soup="", ob_entry="post_mss", void_trades=("range",))
    return p


def discipline_ok(o: dict, p) -> bool:
    """M12-setup-selection-order (review fix): with entry_discipline_only an order passes only when its entry kind belongs to the chosen discipline - "turtle_soup": the turtle-soup kinds (turtle_soup /
    ts_*); "ob_return": the order-block kinds (ob_pre / ob_anchor / arr_ob*); "range_void": the void trades (void_*)."""
    k = str(o.get("entry_kind") or "")
    d = p.entry_discipline
    ok = (k == "turtle_soup" or k.startswith("ts_")) if d == "turtle_soup" else (k.startswith("ob_") or k.startswith("arr_ob")) if d == "ob_return" else k.startswith("void_") if d == "range_void" else True
    if ok:
        hit("discipline_only_ok")
    return ok


# --- non-sweep setups of the chunk ---------------------------------------------------------------------------------------------------------------------------

def any_extra6(p) -> bool:
    return bool(p.consol_eq_entry or p.void_trades or p.ts_cont or p.rb_entry or p.consol_edge_fade != "off" or p.vb_entry in ("partial", "full", "auto"))


def extra6(ctx, sd, i: int, p, session: str, risk_mult: float):
    """The non-sweep setups of this chunk, tried when the sweep machine has nothing (strategy._scan)."""
    if p.consol_eq_entry:
        o = consol_eq_order(ctx, sd, i, p, session, risk_mult)
        if o is not None:
            return o
    if p.void_trades:
        o = void_order(ctx, sd, i, p, session, risk_mult)
        if o is not None:
            return o
    if p.ts_cont:
        o = ts_cont_order(ctx, sd, i, p, session, risk_mult)
        if o is not None:
            return o
    if p.rb_entry:
        o = rb_order(ctx, sd, i, p, session, risk_mult)
        if o is not None:
            return o
    if p.consol_edge_fade != "off":
        o = consol_fade_order(ctx, sd, i, p, session, risk_mult)
        if o is not None:
            return o
    if p.vb_entry in ("partial", "full", "auto"):
        o = vb_order6(ctx, sd, i, p, session, risk_mult)
        if o is not None:
            return o
    return None


# --- gates and tags at order completion --------------------------------------------------------------------------------------------------------------------

def _htf_ok(ctx, sd, sw, i: int, p) -> bool:
    S = _S()
    now = ctx.idx[i] + pd.Timedelta(minutes=ctx.tf)
    cf = getattr(ctx, "conf", None)
    if cf is not None:
        return bool(S._htf_array(cf.at(now, sd.x(sw["ext"]), sd.sign, known_by=ctx.idx[sw["ext_i"]] + pd.Timedelta(minutes=ctx.tf)), p))
    return bool(S._htf_tag(ctx, sd, i, sw["ext"], _tol(p)))


def _week_levels(ctx, sd):
    """(this week's extreme so far, the intermediate-term extreme) of the pool side, side space: the high / low of the COMPLETED days of the current ISO week before today, and of the older days of
    the last 20 sessions (previous week or older) [our interpretation of "intra-week" / "intermediate-term"]. None where there are no such days."""
    hist = getattr(ctx, "hist", None) or []
    wk = ctx.day.isocalendar()[:2]
    this = [f for f in hist[-6:] if f.index[0].date().isocalendar()[:2] == wk]
    old = [f for f in hist[-20:] if f.index[0].date().isocalendar()[:2] != wk]
    out = []
    for fs in (this, old):
        if not fs:
            out.append(None)
            continue
        v = min(float(f.low.min()) for f in fs) if sd.sign > 0 else max(float(f.high.max()) for f in fs)
        out.append(float(sd.x(v)))
    return out[0], out[1]


def reversal_types(ctx, sd, sw, i: int, p, session: str) -> tuple:
    """new-eight-reversal-catalogue (cc09_005 ~00:00:29): the reversal types the sweep satisfies - "pdl"/"pdh" (1/2: the prior day's extreme, the first-pool keys), "week" (3/4: this week's extreme
    so far), "iterm" (5/6: an older week's extreme or the prior week / month pools), "ny_rev" (7: a sweep trade at 08:30-10:00 with an HTF array at the sweep) and "lc_rev" (8: 10:00-12:00 with one).
    (types, htf_ok)."""
    key, lvl, tol = str(sw.get("key", "")), float(sw["level"]), _tol(p)
    htf = _htf_ok(ctx, sd, sw, i, p)
    tys = []
    if key.startswith(("pdl1", "pdh1")):
        tys.append("pdl" if sd.sign > 0 else "pdh")
    wk, it = _week_levels(ctx, sd)
    if wk is not None and abs(lvl - wk) <= tol:
        tys.append("week")
    if key in ("pwl", "pml_month") or (it is not None and abs(lvl - it) <= tol):
        tys.append("iterm")
    t = int(ctx.t[int(sw.get("sweep_i", sw["ext_i"]))])      # review fix: the clock time of the SWEEP bar (not of the bar that completes the order)
    if 510 <= t < 600 and htf:
        tys.append("ny_rev")
    elif 600 <= t < 720 and htf:
        tys.append("lc_rev")
    return tuple(tys), htf


def ob_candle(ctx, sd, sw, kind: str, i: int, p):
    """The order-block candle an OB-kind entry actually trades: arr_ob_secondary / arr_ob_post / ob_anchor store their candle on the sweep dict; others use the primary OB at the sweep. {k, body_top} or None."""
    S = _S()
    key = {"arr_ob_secondary": "_ob_sec_k", "arr_ob_post": "_ob_post_k", "ob_anchor": "_ob_anchor_k"}.get(kind)
    if key and sw.get(key) is not None:
        k = int(sw[key])
        return dict(k=k, body_top=float(max(sd.o[k], sd.c[k])))
    return S._ob_at_low(sd, sw, i, p, ctx)


def pdl_expansion_ok(ctx, sd, i: int, p) -> bool:
    """L2-pdh-pdl-fade-only-in-expansion-retrace (cc09_005 ~00:15:56): a PDL / PDH fade needs the htf.table bias (weekly bias + the daily flip) on this side, the Confluence daily flow on this side, and
    the prior 1-3 days to be counter-moves (a close under the day before, side space): the run of consecutive counter-move days ending yesterday must be 1..3 long."""
    if _want(ctx) != sd.sign:
        return False
    cf = getattr(ctx, "conf", None)
    if cf is not None and cf.trend(sm2.now_ts(ctx, i), "D") != sd.sign:
        return False
    hist = getattr(ctx, "hist", None) or []
    cl = [float(sd.x(f.close.iloc[-1])) for f in hist[-6:]]
    run = 0
    for k in range(len(cl) - 1, 0, -1):
        if cl[k] < cl[k - 1]:
            run += 1
        else:
            break
    return 1 <= run <= 3


def any_gate6(p) -> bool:
    return bool(p.ote_parent_pd or p.ob_below_open or p.eq_fresh_ob or p.sym_swing_ts or p.ny_london_range or p.sweep_15m_array != "off" or p.sweep_leave_bars > 0 or p.reversal_tag
                or p.reversal_need_htf or p.reversal_score or p.pdl_expansion)


def order_gate6(ctx, sd, sw, i: int, p, entry: float, stop: float, session: str, lvt: list, lvx: dict, tags: dict):
    """Gates / tags of setups_models #6/7 at order completion (strategy._finish_order, after order_gate5). Returns a reject key or None."""
    S = _S()
    synth = bool(sw.get(S._SM.SYNTH))
    kind = str(tags.get("entry_kind", ""))
    tol = _tol(p)
    if p.ote_parent_pd and not synth:
        leg_hi = float(sd.h[sw["ext_i"]:i + 1].max())
        base = S._LD.leg_low(sd, sw, i, p, leg_hi)
        lo_, hi_, _ = L.ote_band(base, leg_hi)
        if lo_ - MIN1 <= entry <= hi_ + MIN1:
            phi, plo = float(sd.h[ctx.start:i + 1].max()), float(sd.l[ctx.start:i + 1].min())
            hit("ote_parent_pd")
            if entry > (phi + plo) / 2 + MIN1:
                return "x_ote_parent_pd"
    if (p.ob_below_open or p.eq_fresh_ob) and not synth and kind in OB_KINDS:
        ob = ob_candle(ctx, sd, sw, kind, i, p)           # review fix: the candle that is actually traded (secondary / post-MSS / anchor OB), not always the primary OB at the sweep
        if p.ob_below_open and ob is not None:
            mo = S._open_known(ctx, "midnight", i)
            if mo is not None:
                hit("ob_below_open")
                o_s = float(sd.x(mo))
                if ob["body_top"] > o_s + MIN1 or entry > o_s + MIN1:
                    return "x_ob_above_open"
        if p.eq_fresh_ob and ob is not None:
            hi_c = np.maximum.accumulate(sd.h[ctx.start:i + 1])
            lo_c = np.minimum.accumulate(sd.l[ctx.start:i + 1])
            eq = float((hi_c[-1] + lo_c[-1]) / 2)
            if abs(entry - eq) <= tol:
                hit("eq_fresh_ob")
                # the EQ is anchored when price FIRST reached it: the first bar that touched the EQ band of the range known before it (the EQ moves while the range grows) and that EQ lies within the
                # tolerance of today's EQ
                eqp = (hi_c[:-1] + lo_c[:-1]) / 2
                n_ = len(eqp)
                hit_j = np.flatnonzero((np.abs(eqp - eq) <= tol) & (sd.l[ctx.start + 1:ctx.start + 1 + n_] <= eqp + tol) & (sd.h[ctx.start + 1:ctx.start + 1 + n_] >= eqp - tol))
                j0 = ctx.start + 1 + int(hit_j[0]) if len(hit_j) else None
                if j0 is not None and ob["k"] <= j0:
                    return "x_eq_stale_ob"
    if p.sym_swing_ts and not synth and sw.get("smt") is False and (not p.sym_swing_dxy or S._CG3.dxy_confirms(ctx, sd, i, p, sw)):
        hit("sym_swing")
        if sw["ext"] <= float(sd.l[ctx.start:i + 1].min()) + p.tick:
            return "x_sym_swing"
    if p.ny_london_range and session == "AM" and int(ctx.wbias) == sd.sign:
        a, b, k20 = S._idx_at(ctx, 120), S._idx_at(ctx, 300), S._idx_at(ctx, 500)
        if b > a and k20 <= i and a < len(ctx.t):
            jL = a + int(np.argmin(sd.l[a:b]))
            R_lo, R_hi = float(sd.l[jL]), float(sd.h[jL:k20].max())
            hit("ny_london_range")
            if not (R_lo - tol <= entry <= (R_lo + R_hi) / 2 + MIN1):
                return "x_ny_london_range"
    if not synth and (p.sweep_15m_array != "off" or p.sweep_leave_bars > 0):
        if p.sweep_15m_array != "off":
            kb = ctx.idx[sw["ext_i"]] + pd.Timedelta(minutes=ctx.tf)
            arrs = S._ts_arrays(ctx, sd, i, kb, ("15m",))
            hit("sweep_15m_array")
            if any(b_ - tol <= sw["ext"] <= t_ + tol for t_, b_, _ in arrs):
                lvt.append("sweep_15m_array")
            elif p.sweep_15m_array == "require":
                return "x_sweep_no_15m_array"
        if p.sweep_leave_bars > 0:
            e, n = sw["ext_i"], p.sweep_leave_bars
            if e + n + 1 <= i:
                hit("sweep_hover")
                if float(sd.h[e + 1:e + n + 2].max()) <= sw["ext"] + p.sweep_leave_pts * p.es_pt + MIN1:
                    return "x_sweep_hover"
    if (p.reversal_tag or p.reversal_need_htf or p.reversal_score) and not synth:
        tys, htf = reversal_types(ctx, sd, sw, i, p, session)
        hit("reversal_types")
        if p.reversal_need_htf and any(t_ in ("week", "iterm", "ny_rev", "lc_rev") for t_ in tys) and not htf:
            return "x_reversal_no_htf"
        if p.reversal_tag:
            lvt += ["rev_" + t_ for t_ in tys]
        if p.reversal_score and tys:
            lvt.append(f"rev_score_{len(tys)}")
    if p.pdl_expansion and not synth and str(sw.get("key", "")).startswith(("pdl", "pdh")):
        hit("pdl_expansion")
        if not pdl_expansion_ok(ctx, sd, i, p):
            return "x_pdl_expansion"
    return None


def late6(ctx, sd, sw, i: int, p, order: dict, tags: dict) -> str | None:
    """new-clarity-filter-pass-if-arguing (cc06_002 ~00:09:20), on the finished order (the first target is known): the entry zone's height within 10% of a size threshold (the Side's min_gap, or the
    displacement multiple against the break candle's body) or the path entry .. T1 dominated by overlapping candles (the day's bars' range inside the path / the path length > clarity_overlap) is not
    "clearly defined": clarity "drop" removes the order (returns the reject key), "tag" appends lv_tags clarity_marginal / clarity_overlap."""
    if p.clarity == "off":
        return None
    entry, t1 = float(order["entry"]), float(order["t1"])
    why = []
    gap = float(order.get("zone_top", entry)) - float(tags.get("fvg_bottom", entry))
    mg = float(getattr(sd, "min_gap", 0.0) or 0.0)
    if mg > 0 and gap > 0 and abs(gap - mg) <= 0.1 * mg + MIN1:
        why.append("clarity_marginal")
    elif p.displacement_mult and sw.get("broke") is not None and not sw.get(_S()._SM.SYNTH):
        b = sw["broke"]
        prev = np.abs(sd.c[max(0, b - 10):b] - sd.o[max(0, b - 10):b])
        if len(prev) and float(prev.mean()) > 0 and abs(abs(sd.c[b] - sd.o[b]) / float(prev.mean()) - p.displacement_mult) <= 0.1 * p.displacement_mult:
            why.append("clarity_marginal")
    if t1 > entry:
        h, l = sd.h[ctx.start:i + 1], sd.l[ctx.start:i + 1]
        inside = np.clip(np.minimum(h, t1) - np.maximum(l, entry), 0.0, None)
        if float(inside.sum()) / (t1 - entry) > p.clarity_overlap:
            why.append("clarity_overlap")
    hit("clarity")
    if not why:
        return None
    if p.clarity == "drop":
        return "x_clarity"
    order["lv_tags"] = "|".join(x for x in (order.get("lv_tags", ""), *why) if x)
    return None
