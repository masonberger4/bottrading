"""PD-array detectors from the ICT Mentorship rules (mentorship_rules.md).

Every detector reports the bar index at which its object became *known* (`Zone.i`,
`Pivot.known`), so a bar-by-bar caller can use an object at bar i only when its known
index is <= i. Nothing here reads a bar after the one it reports as known.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Zone:
    kind: str       # "bull" or "bear"
    top: float
    bottom: float
    i: int          # bar index at which the zone is known (the bar that completes it)
    src: int = -1   # index of the candle the zone is built from (blocks), or the gap's middle candle
    mt: float = float("nan")   # blocks: body mean threshold (see order_block_blend)

    @property
    def mid(self) -> float:
        """Consequent encroachment (gaps) or mean threshold (blocks): 50% of the zone."""
        return (self.top + self.bottom) / 2

    def overlaps(self, other: "Zone") -> bool:
        return self.bottom < other.top and self.top > other.bottom


@dataclass(frozen=True)
class Pivot:
    i: int          # bar of the swing high/low
    price: float
    known: int      # first bar at which it is confirmed (i + n)


def fvgs(h, l) -> list[Zone]:
    """Fair value gaps (3-candle). BISI: low[i] > high[i-2]; SIBI: high[i] < low[i-2].
    Known at the third candle i."""
    out = []
    for i in range(2, len(h)):
        if l[i] > h[i - 2]:
            out.append(Zone("bull", l[i], h[i - 2], i, i - 1))
        elif h[i] < l[i - 2]:
            out.append(Zone("bear", l[i - 2], h[i], i, i - 1))
    return out


def volume_imbalances(o, h, l, c) -> list[Zone]:
    """Gap between two consecutive candle bodies where only the wicks overlap."""
    out = []
    for i in range(1, len(o)):
        pb_hi, pb_lo = max(o[i - 1], c[i - 1]), min(o[i - 1], c[i - 1])
        cb_hi, cb_lo = max(o[i], c[i]), min(o[i], c[i])
        if cb_lo > pb_hi and l[i] <= h[i - 1]:
            out.append(Zone("bull", cb_lo, pb_hi, i, i))
        elif cb_hi < pb_lo and h[i] >= l[i - 1]:
            out.append(Zone("bear", pb_lo, cb_hi, i, i))
    return out


def pivots(h, l, n: int = 2) -> tuple[list[Pivot], list[Pivot]]:
    """Swing highs/lows: the bar's high (low) is strictly above (below) the n bars on each
    side. Confirmed n bars later."""
    highs, lows = [], []
    for k in range(n, len(h) - n):
        if h[k] > max(h[k - n:k]) and h[k] > max(h[k + 1:k + n + 1]):
            highs.append(Pivot(k, float(h[k]), k + n))
        if l[k] < min(l[k - n:k]) and l[k] < min(l[k + 1:k + n + 1]):
            lows.append(Pivot(k, float(l[k]), k + n))
    return highs, lows


def order_block(o, h, l, c, start: int, end: int, kind: str) -> Zone | None:
    """Bullish OB: the last down-close candle in [start, end]; bearish: last up-close.
    Its mean threshold is `Zone.mid`."""
    for k in range(min(end, len(o) - 1), max(start, 0) - 1, -1):
        if (kind == "bull" and c[k] < o[k]) or (kind == "bear" and c[k] > o[k]):
            return Zone(kind, float(h[k]), float(l[k]), end, k)
    return None


def order_block_blend(o, h, l, c, start: int, end: int, kind: str) -> Zone | None:
    """ICT order block: the last down-close candle in [start, end] (bullish; up-close for
    bearish) together with the consecutive same-colour candles right before it, blended into
    one block (002 ~4:14; 029 ~29:28; 032 ~23:06). Zone = the series' full range; `mt` = the
    body mean threshold, midway between the series' highest body and lowest body
    (bullish: (max open + min close) / 2). `src` = the first (anchor) candle."""
    down = (lambda k: c[k] < o[k]) if kind == "bull" else (lambda k: c[k] > o[k])
    start = max(start, 0)
    for k in range(min(end, len(o) - 1), start - 1, -1):
        if down(k):
            j = k
            while j - 1 >= start and down(j - 1):
                j -= 1
            hi, lo = float(max(h[j:k + 1])), float(min(l[j:k + 1]))
            if kind == "bull":
                mt = (max(o[j:k + 1]) + min(c[j:k + 1])) / 2
            else:
                mt = (min(o[j:k + 1]) + max(c[j:k + 1])) / 2
            return Zone(kind, hi, lo, end, j, float(mt))
    return None


BREAKER_MODES = ("range", "body", "leg", "last")


def breaker_candle(o, c, a0: int, ext_i: int, kind: str = "bull") -> int | None:
    """The breaker candle of a bullish breaker: the up-close candle with the HIGHEST close in
    [a0, ext_i] (the leg from the swing low L1 before the high to the sweep extreme L2;
    029 ~24:13; 048). Bearish: the down-close candle with the lowest close. Closed bars only:
    the caller passes ext_i <= the current bar. None when there is no such candle."""
    a0 = max(int(a0), 0)
    if kind == "bull":
        cand = [k for k in range(a0, int(ext_i) + 1) if c[k] > o[k]]
        return max(cand, key=lambda k: c[k]) if cand else None     # first on ties (as before)
    cand = [k for k in range(a0, int(ext_i) + 1) if c[k] < o[k]]
    return min(cand, key=lambda k: c[k]) if cand else None


def breaker_mt(o, h, l, c, k: int, mode: str = "range") -> float:
    """Breaker mean threshold (A13.3, owner directive #6): 50% of the breaker candle's FULL
    high-low ("range", Ep 02 ~3:37-3:54 "half of that range from the candle's high and low";
    007 ~1:22-1:58) or of its body ("body" switch)."""
    if mode == "range":
        return float((h[k] + l[k]) / 2)
    if mode == "body":
        return float((o[k] + c[k]) / 2)
    raise ValueError(f"breaker mt mode {mode!r}: expected 'range' or 'body'")


def breaker_zone(o, h, l, c, a0: int, ext_i: int, i: int, kind: str = "bull",
                 mode: str = "range", mt_mode: str | None = None) -> Zone | None:
    """Shared breaker-zone helper (A13; owner directive #14). The breaker candle is
    `breaker_candle` (highest-close up-close candle between L1 and the sweep extreme for a
    bullish breaker). Zone extent:
      "range"  the candle's full high-low (default; Ep 02 ~3:37, Ep 05 ~11:34/~15:20/~22:49,
               Ep 07's OB "entire range" [our interpretation])
      "body"   open-close only (Ep 01 ~56:19 switch)
      "leg"    D6 C (070): the whole A->B leg, from the swing low L1 (A, bar a0) to the swing high
               H (B = the highest high in [a0, ext_i]): low of L1's bar .. high of H's bar; MT =
               its midpoint [our interpretation of "inside the A-B leg"]
      "last"   D6 D (cc05_014): the LAST up-close candle before the sweep extreme (not the highest
               close), its full range [our interpretation]
    `mt` = breaker_mt(mt_mode) - by default it follows the zone mode, so the default MT is 50%
    of the full range (the leg's midpoint for "leg"). Known at bar i (the caller's bar)."""
    if mode not in BREAKER_MODES:
        raise ValueError(f"breaker_zone mode {mode!r}: expected one of {BREAKER_MODES}")
    a0, ext_i = max(int(a0), 0), int(ext_i)
    if mode == "leg":
        if ext_i <= a0:
            return None
        hk = a0 + int(np.argmax(h[a0:ext_i + 1])) if kind == "bull" else a0 + int(np.argmin(l[a0:ext_i + 1]))
        if kind == "bull":
            top, bot = float(h[hk]), float(min(l[a0:hk + 1]))
        else:
            top, bot = float(max(h[a0:hk + 1])), float(l[hk])
        mt = (top + bot) / 2 if (mt_mode or "range") in ("range", "leg") else breaker_mt(o, h, l, c, hk, mt_mode)
        return Zone(kind, top, bot, i, hk, mt)
    if mode == "last":
        up = (lambda k: c[k] > o[k]) if kind == "bull" else (lambda k: c[k] < o[k])
        cand = [k for k in range(a0, ext_i + 1) if up(k)]
        if not cand:
            return None
        k = cand[-1]
        mt = breaker_mt(o, h, l, c, k, "range" if (mt_mode or "range") in ("range", "last") else mt_mode)
        return Zone(kind, float(h[k]), float(l[k]), i, k, mt)
    k = breaker_candle(o, c, a0, ext_i, kind)
    if k is None:
        return None
    mt = breaker_mt(o, h, l, c, k, mt_mode or mode)
    if mode == "range":
        return Zone(kind, float(h[k]), float(l[k]), i, k, mt)
    return Zone(kind, float(max(o[k], c[k])), float(min(o[k], c[k])), i, k, mt)


def breakers(o, h, l, c, n: int = 2, mode: str = "range") -> list[Zone]:
    """Bullish breaker: swing low L1, swing high H, lower low (the sweep), then a candle *body*
    closes above H. The zone is the breaker candle from `breaker_zone` (highest-close up-close
    candle between L1 and the sweep extreme, full range by default) - the same rule `_scan`
    uses, so both agree. Bearish mirrors it. Known (emitted) at the closing break."""
    import bisect
    ph, pl = pivots(h, l, n)
    out = []
    used = set()
    known = {id(ph): [p.known for p in ph], id(pl): [p.known for p in pl]}
    at = {id(ph): [p.i for p in ph], id(pl): [p.i for p in pl]}
    for i in range(len(c)):
        for kind, hs, ls, sign in (("bull", ph, pl, 1), ("bear", pl, ph, -1)):
            # in "bull" terms: hs = swing highs, ls = swing lows (mirrored for bear)
            k = bisect.bisect_right(known[id(hs)], i)         # pivots known by bar i (sorted)
            if not k:
                continue
            H = hs[k - 1]
            if (kind, H.i) in used:
                continue
            j = bisect.bisect_left(at[id(ls)], H.i)          # swing lows before H (known by H.known)
            if not j:
                continue
            L1 = ls[j - 1]
            seg = l[H.i + 1:i] if sign > 0 else h[H.i + 1:i]
            if not len(seg):
                continue
            swept = seg.min() < L1.price if sign > 0 else seg.max() > L1.price
            broke = c[i] > H.price if sign > 0 else c[i] < H.price
            if swept and broke:
                ext_i = H.i + 1 + int(np.argmin(seg) if sign > 0 else np.argmax(seg))
                z = breaker_zone(o, h, l, c, L1.i, ext_i, i, kind, mode)
                if z is not None:
                    out.append(z)
                used.add((kind, H.i))
    return out


def turtle_soup(l, c, level: float, ext_i: int, i: int, max_depth: float,
                back_bars: int) -> bool:
    """Turtle-soup core (M12, shared by M12.x / M4.4 / D10 / Ep08.15), bullish terms: a false
    break of an old low `level` "by a little" - the extreme l[ext_i] is below the level by no more
    than `max_depth` - then a fast reversal: a candle CLOSES back above the level within
    `back_bars` bars of the extreme, at the latest at bar i (closed bars only). No MSS needed
    (022 ~2:47:29; cc05_004 ~6:45). Bearish = mirrored prices."""
    if not (l[ext_i] < level and level - l[ext_i] <= max_depth):
        return False
    if i <= ext_i or i - ext_i > back_bars:
        return False
    return bool((c[ext_i:i + 1] > level).any()) and bool(l[ext_i + 1:i + 1].min(initial=np.inf) >= l[ext_i])


def equal_levels(prices, tol: float) -> list[float]:
    """Relative equal highs (or lows): clusters of >= 2 swing prices within `tol` of each
    other. Returns the extreme of each cluster (max for highs; pass negated lows)."""
    p = sorted(prices)
    out, k = [], 0
    while k < len(p):
        j = k
        while j + 1 < len(p) and p[j + 1] - p[k] <= tol:
            j += 1
        if j > k:
            out.append(p[j])
        k = j + 1
    return out


def opens(index, o) -> dict[str, float]:
    """Opening prices for one day: midnight, 08:30, 09:30, 13:30 (first bar at or after).
    SPY has no bars at midnight, so its first pre-market bar (04:00) stands in for it."""
    t = index.hour * 60 + index.minute
    out = {}
    for name, m in (("midnight", 0), ("0830", 510), ("0930", 570), ("1330", 810)):
        k = np.flatnonzero(t >= m)
        if len(k):
            out[name] = float(o[k[0]])
    return out


def rejection_blocks(o, h, l, c, n: int = 2) -> list[Zone]:
    """Wicks at a swing high (low): from the highest candle body to the high (lowest body to
    the low) of the swing candle and its neighbours. A bearish rejection block sits at a
    swing high. Known when the swing is confirmed."""
    ph, pl = pivots(h, l, n)
    out = []
    for p in ph:
        a, b = max(0, p.i - 1), p.i + 2
        body = max(max(o[k], c[k]) for k in range(a, b))
        if body < p.price:
            out.append(Zone("bear", p.price, float(body), p.known, p.i))
    for p in pl:
        a, b = max(0, p.i - 1), p.i + 2
        body = min(min(o[k], c[k]) for k in range(a, b))
        if body > p.price:
            out.append(Zone("bull", float(body), p.price, p.known, p.i))
    return sorted(out, key=lambda z: z.i)


def balanced_ranges(h, l) -> list[Zone]:
    """Balanced price range: where a bullish and a bearish FVG overlap, price has been
    delivered both ways. Kind follows the later gap; known when the later gap forms."""
    g = fvgs(h, l)
    out = []
    for k, b in enumerate(g):
        for a in g[:k]:
            if a.kind != b.kind and a.overlaps(b):
                out.append(Zone(b.kind, min(a.top, b.top), max(a.bottom, b.bottom), b.i, a.i))
    return out


def wick_midpoints(o: float, h: float, l: float, c: float) -> dict[str, float]:
    """50% of a daily candle's upper and lower wicks."""
    return {"upper": max(o, c) + (h - max(o, c)) / 2, "lower": min(o, c) - (min(o, c) - l) / 2}


def inversion_fvgs(h, l, c, min_gap: float = 0.0) -> list[Zone]:
    """Inversion FVGs (015 ~21:00; 048 ~21:32; 102 ~1:02:03): a bearish FVG that a candle body
    closes above becomes bullish support (and a bullish FVG closed below becomes resistance).
    Same top/bottom as the original gap; known at the closing candle. A later candle must
    trade back into it for an entry, which a limit order placed after `i` guarantees."""
    out = []
    for z in fvgs(h, l):
        if z.top - z.bottom < min_gap:
            continue
        after = c[z.i + 1:]
        if z.kind == "bear":
            k = np.flatnonzero(after > z.top)
            if len(k):
                out.append(Zone("bull", z.top, z.bottom, z.i + 1 + int(k[0]), z.src))
        else:
            k = np.flatnonzero(after < z.bottom)
            if len(k):
                out.append(Zone("bear", z.top, z.bottom, z.i + 1 + int(k[0]), z.src))
    return sorted(out, key=lambda z: z.i)


def voids(h, l) -> list[Zone]:
    """Liquidity voids: a true price gap between two consecutive candles, no overlap at all
    (028 ~36:17). Bullish: low[i] > high[i-1]. Known at candle i."""
    out = []
    for i in range(1, len(h)):
        if l[i] > h[i - 1]:
            out.append(Zone("bull", l[i], h[i - 1], i, i))
        elif h[i] < l[i - 1]:
            out.append(Zone("bear", l[i - 1], h[i], i, i))
    return out


def mitigation_blocks(o, h, l, c, n: int = 1) -> list[Zone]:
    """Bullish mitigation block (cc04_004 ~2:42-14:35; 033 ~1:03:50): swing high A, swing low,
    a HIGHER low (no stop run below the swing low), then a body close above A; the zone is the
    last up-close candle at A (the failed high). The breaker's sibling without the sweep.
    Bearish mirrors it. Known at the closing break."""
    ph, pl = pivots(h, l, n)
    out, used = [], set()
    for i in range(len(c)):
        for kind, hs, ls, sign in (("bull", ph, pl, 1), ("bear", pl, ph, -1)):
            hk = [p for p in hs if p.known <= i]
            if not hk or (kind, hk[-1].i) in used:
                continue
            H = hk[-1]
            later = [p for p in ls if p.i > H.i and p.known <= i]
            if len(later) < 2:
                continue
            L0, L1 = later[-2], later[-1]              # swing low after A, then the next low
            higher_low = L1.price > L0.price if sign > 0 else L1.price < L0.price
            broke = c[i] > H.price if sign > 0 else c[i] < H.price
            if higher_low and broke:
                blk = order_block(o, h, l, c, H.i - n, H.i, "bear" if sign > 0 else "bull")
                if blk is not None:
                    out.append(Zone(kind, blk.top, blk.bottom, i, blk.src))
                used.add((kind, H.i))
    return out


def propulsion_blocks(o, h, l, c, obs: list[Zone]) -> list[Zone]:
    """Bullish propulsion block (cc04_008 ~0:30-5:40; 027 ~11:31): a down-close candle that
    trades down into an earlier bullish order block without a body close below that block's
    mean threshold; it becomes the new support. Zone = that candle's range, `mt` = its body
    midpoint (losing it = the idea is wrong). Known at that candle."""
    out = []
    for ob in obs:
        if ob.kind != "bull":
            continue
        mt = ob.mt if ob.mt == ob.mt else ob.mid
        for k in range(ob.i + 1, len(c)):
            if c[k] < mt:
                break                              # the order block failed
            if c[k] < o[k] and l[k] <= ob.top:
                out.append(Zone("bull", float(h[k]), float(l[k]), k, k, float((o[k] + c[k]) / 2)))
                break
    return out
