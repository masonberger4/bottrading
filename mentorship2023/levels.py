"""PD-array detectors from the 2023 Mentorship rules (mentorship2023_rules.md).

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


def breakers(o, h, l, c, n: int = 2) -> list[Zone]:
    """Bullish breaker: swing low, swing high, lower low, then a candle *body* closes above
    the swing high. The zone is the last up-close candle at/before that swing high (it
    failed as resistance and now acts as support). Bearish mirrors it. Known at the
    closing break."""
    ph, pl = pivots(h, l, n)
    out = []
    used = set()
    for i in range(len(c)):
        for kind, hs, ls, sign in (("bull", ph, pl, 1), ("bear", pl, ph, -1)):
            # in "bull" terms: hs = swing highs, ls = swing lows (mirrored for bear)
            hk = [p for p in hs if p.known <= i]
            if not hk:
                continue
            H = hk[-1]
            if (kind, H.i) in used:
                continue
            prior = [p for p in ls if p.i < H.i and p.known <= i]
            if not prior:
                continue
            L = prior[-1]
            seg = l[H.i + 1:i] if sign > 0 else h[H.i + 1:i]
            if not len(seg):
                continue
            swept = seg.min() < L.price if sign > 0 else seg.max() > L.price
            broke = c[i] > H.price if sign > 0 else c[i] < H.price
            if swept and broke:
                blk = order_block(o, h, l, c, H.i - n, H.i, "bear" if sign > 0 else "bull")
                if blk is not None:
                    out.append(Zone(kind, blk.top, blk.bottom, i, blk.src))
                used.add((kind, H.i))
    return out


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
    SPY has no bars at midnight, so the first pre-market bar (04:00) stands in for it."""
    t = index.hour * 60 + index.minute
    out = {}
    for name, m in (("midnight", 0), ("0830", 510), ("0930", 570), ("1330", 810)):
        k = np.flatnonzero(t >= max(m, 240))
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
