"""PD-array detectors from the ICT Mentorship rules (mentorship_rules.md).

Every detector reports the bar index at which its object became *known* (`Zone.i`,
`Pivot.known`), so a bar-by-bar caller can use an object at bar i only when its known
index is <= i. Nothing here reads a bar after the one it reports as known.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


def _same(a, b) -> bool:
    """Field equality where NaN equals NaN (an unset mean threshold)."""
    return a == b or (a != a and b != b)


@dataclass(frozen=True, eq=False)
class Zone:
    kind: str       # "bull" or "bear"
    top: float
    bottom: float
    i: int          # bar index at which the zone is known (the bar that completes it)
    src: int = -1   # index of the candle the zone is built from (blocks), or the gap's middle candle
    mt: float = float("nan")   # blocks: body mean threshold (see order_block_blend)

    # Equality and hashing treat a NaN mean threshold as equal to NaN. Python 3.13's dataclass
    # __eq__ compares fields with == (NaN != NaN), while 3.11/3.12 compared tuples, whose
    # identity shortcut made the shared NaN default compare equal; this keeps both the same.
    def _key(self):
        return (self.kind, self.top, self.bottom, self.i, self.src, None if self.mt != self.mt else self.mt)

    def __eq__(self, other):
        if not isinstance(other, Zone):
            return NotImplemented
        return all(_same(x, y) for x, y in zip(
            (self.kind, self.top, self.bottom, self.i, self.src, self.mt),
            (other.kind, other.top, other.bottom, other.i, other.src, other.mt)))

    def __hash__(self):
        return hash(self._key())

    @property
    def mid(self) -> float:
        """Consequent encroachment (gaps) or mean threshold (blocks): 50% of the zone."""
        return (self.top + self.bottom) / 2

    def overlaps(self, other: "Zone") -> bool:
        return self.bottom < other.top and self.top > other.bottom

    def q(self, frac: float) -> float:
        """A5 quadrant level (020 ~8:21; 029 ~30:44): `frac` of the way from the bottom to the
        top (0.25 / 0.5 = CE / 0.75)."""
        return self.bottom + frac * (self.top - self.bottom)


@dataclass(frozen=True)
class Pivot:
    i: int          # bar of the swing high/low
    price: float
    known: int      # first bar at which it is confirmed (i + n)


def fvgs(h, l, o=None, c=None, c2_dir: bool = False) -> list[Zone]:
    """Fair value gaps (3-candle). BISI: low[i] > high[i-2]; SIBI: high[i] < low[i-2].
    Known at the third candle i. A5 `c2_dir` (Params.fvg_c2_dir; 001 ~13:02, 024 ~23:22: "c2 is
    the displacement candle"): the middle candle must close in the gap's direction (up-close for
    a BISI, down-close for a SIBI); needs o and c."""
    out = []
    chk = c2_dir and o is not None and c is not None
    for i in range(2, len(h)):
        if l[i] > h[i - 2]:
            if chk and not c[i - 1] > o[i - 1]:
                continue
            out.append(Zone("bull", l[i], h[i - 2], i, i - 1))
        elif h[i] < l[i - 2]:
            if chk and not c[i - 1] < o[i - 1]:
                continue
            out.append(Zone("bear", l[i - 2], h[i], i, i - 1))
    return out


def volume_imbalances(o, h, l, c, min_gap: float = 0.0) -> list[Zone]:
    """Gap between two consecutive candle bodies where only the wicks overlap. A9 `min_gap`
    (Params.vi_min_gap_pts, in price units): body gaps narrower than this are ignored."""
    out = []
    for i in range(1, len(o)):
        pb_hi, pb_lo = max(o[i - 1], c[i - 1]), min(o[i - 1], c[i - 1])
        cb_hi, cb_lo = max(o[i], c[i]), min(o[i], c[i])
        if cb_lo > pb_hi and l[i] <= h[i - 1]:
            if cb_lo - pb_hi >= min_gap:
                out.append(Zone("bull", cb_lo, pb_hi, i, i))
        elif cb_hi < pb_lo and h[i] >= l[i - 1]:
            if pb_lo - cb_hi >= min_gap:
                out.append(Zone("bear", pb_lo, cb_hi, i, i))
    return out


def vi_body_dead(o, c, z: Zone, start: int | None = None, end: int | None = None) -> int | None:
    """A9 / Ep03.3 VI death rule (035 ~5:50; 090 ~13:01): a VI is dead once a LATER candle body on
    its own timeframe closes fully across it - the body spans the whole VI, bottom to top. Returns
    the first such candle index in [start (default z.i + 1), end] (known at its close) or None.
    Wicks never kill it."""
    a = z.i + 1 if start is None else start
    b = len(c) - 1 if end is None else min(end, len(c) - 1)
    for k in range(a, b + 1):
        if min(o[k], c[k]) <= z.bottom and max(o[k], c[k]) >= z.top:
            return k
    return None


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


def swing_tiers(h, l, n: int = 1) -> dict:
    """A1 swing hierarchy (014 ~0:12; cc05_002 ~20:14). STL = plain swing (pivots(n)); ITL low =
    an STL low with a HIGHER STL low on each side (its neighbours in the STL-low sequence); LTL low
    = an ITL low with higher ITL lows on each side; highs mirror it. A tier is known only once its
    right neighbour is known: Pivot.known = max(own known, right neighbour's known).
    Returns {"stl": (highs, lows), "itl": (highs, lows), "ltl": (highs, lows)}, sorted by bar."""
    ph, pl = pivots(h, l, n)

    def up(seq, lows: bool):
        out = []
        for k in range(1, len(seq) - 1):
            a, b, r = seq[k - 1], seq[k], seq[k + 1]
            ok = (b.price < a.price and b.price < r.price) if lows else (b.price > a.price and b.price > r.price)
            if ok:
                out.append(Pivot(b.i, b.price, max(b.known, r.known)))
        return out

    ih, il = up(ph, False), up(pl, True)
    return {"stl": (ph, pl), "itl": (ih, il), "ltl": (up(ih, False), up(il, True))}


def immediate_rebalances(o, h, l, c, tick: float) -> list[tuple[int, str]]:
    """A7 immediate rebalance (048 ~39:02; 060 ~7:20; 092 ~1:41:14) [our interpretation of the bar
    test, the same as sb_model.immediate_rebalance]: an up-close displacement candle k-1 whose NEXT
    candle k trades straight back to the high of the candle before it, h[k-2], within one tick and
    leaves no gap (an FVG is the deferred rebalance) -> (k, "bull"); bearish mirror (down-close
    k-1, h[k] back up to l[k-2]) -> (k, "bear"). Known at candle k's close."""
    out = []
    for k in range(2, len(c)):
        if c[k - 1] > o[k - 1] and abs(l[k] - h[k - 2]) <= tick and l[k] <= h[k - 2] + 1e-12:
            out.append((k, "bull"))
        elif c[k - 1] < o[k - 1] and abs(h[k] - l[k - 2]) <= tick and h[k] >= l[k - 2] - 1e-12:
            out.append((k, "bear"))
    return out


def vacuum_block(o, c, k: int, min_gap: float = 0.0) -> Zone | None:
    """L8 vacuum block (cc04_009 ~3:58-10:05): the gap between the last close before an event
    (bar k-1) and the first open after it (bar k), treated as a candle with high / low / MT.
    "bull" when the open is above the prior close (the gap lies below price). Known at bar k (the
    caller uses it from bar k's close). None when the gap is not wider than `min_gap`."""
    if k < 1 or k >= len(o):
        return None
    a, b = float(c[k - 1]), float(o[k])
    if abs(b - a) <= max(min_gap, 0.0) or a == b:
        return None
    return Zone("bull" if b > a else "bear", max(a, b), min(a, b), k, k)


def session_block(minute: int) -> int:
    """A13.5 time blocks [our interpretation of "the wrong time of day" (070 ~6:24)]: 0 Asia
    (18:00-02:00), 1 London (02:00-07:00), 2 NY AM (07:00-12:00), 3 lunch (12:00-13:30), 4 NY PM
    (13:30-18:00). A breaker's H, L2 and break must sit in one block."""
    m = int(minute) % 1440
    if m >= 1080 or m < 120:
        return 0
    if m < 420:
        return 1
    if m < 720:
        return 2
    if m < 810:
        return 3
    return 4


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


def equal_clusters(prices, tol: float) -> list[list[int]]:
    """A3: the clusters of equal_levels (>= 2 prices within `tol` of the cluster's lowest price),
    as lists of indices into `prices`, each ascending by price."""
    order = sorted(range(len(prices)), key=lambda k: prices[k])
    out, k = [], 0
    while k < len(order):
        j = k
        while j + 1 < len(order) and prices[order[j + 1]] - prices[order[k]] <= tol:
            j += 1
        if j > k:
            out.append(order[k:j + 1])
        k = j + 1
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
    SPY has no bars at midnight, so its first pre-market bar (04:00) stands in for it."""
    t = index.hour * 60 + index.minute
    out = {}
    for name, m in (("midnight", 0), ("0830", 510), ("0930", 570), ("1330", 810)):
        k = np.flatnonzero(t >= m)
        if len(k):
            out[name] = float(o[k[0]])
    return out


def rejection_blocks(o, h, l, c, n: int = 2, min_wick_frac: float = 0.0) -> list[Zone]:
    """Rejection block (A17; cc04_006 ~5:04-10:43): a swing high of long-upper-wick candles; the zone runs
    from the highest open / close of the swing (any candle colour) up to the highest wick. A bearish
    block sits at a swing high; the bullish mirror at a swing low. Known when the swing is confirmed.
    Review fix (targets_partials A17): the swing is the pivot candle plus its `n` neighbours each side
    (it was a fixed +-1), and the pivot candle itself must show the wick - its wick at least
    `min_wick_frac` of its range (0 = any wick, the old test). Default arguments keep the old zones for
    pivot_n = 1."""
    ph, pl = pivots(h, l, n)
    out = []
    w = max(n, 1)
    for p in ph:
        a, b = max(0, p.i - w), min(len(h), p.i + w + 1)
        body = max(max(o[k], c[k]) for k in range(a, b))
        rng = h[p.i] - l[p.i]
        wick = h[p.i] - max(o[p.i], c[p.i])
        if body < p.price and (min_wick_frac <= 0 or (rng > 0 and wick >= min_wick_frac * rng)):
            out.append(Zone("bear", p.price, float(body), p.known, p.i))
    for p in pl:
        a, b = max(0, p.i - w), min(len(h), p.i + w + 1)
        body = min(min(o[k], c[k]) for k in range(a, b))
        rng = h[p.i] - l[p.i]
        wick = min(o[p.i], c[p.i]) - l[p.i]
        if body > p.price and (min_wick_frac <= 0 or (rng > 0 and wick >= min_wick_frac * rng)):
            out.append(Zone("bull", float(body), p.price, p.known, p.i))
    return sorted(out, key=lambda z: z.i)


def balanced_ranges(h, l, max_gap_bars: int = 0, o=None, c=None, c2_dir: bool = False) -> list[Zone]:
    """Balanced price range: where a bullish and a bearish FVG overlap, price has been
    delivered both ways. Kind follows the later gap; known when the later gap forms.
    A11 `max_gap_bars` (Params.bpr_max_gap_bars): the two gaps must form within this many bars of
    each other [our interpretation: one delivery up and back]; 0 = any pair (the old rule).
    o / c / c2_dir (review fix): the gaps follow the same A5 c2 rule as every other FVG."""
    g = fvgs(h, l, o, c, c2_dir)
    out = []
    for k, b in enumerate(g):
        for a in g[:k]:
            if max_gap_bars and b.i - a.i > max_gap_bars:
                continue
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


def mitigation_blocks(o, h, l, c, n: int = 1, legacy: bool = False) -> list[Zone]:
    """Bullish mitigation block (A15; 033 ~1:03:50, the mirror of cc04_004 ~2:42-14:35): swing low
    A, then swing high X, then a HIGHER swing low B (no stop run below A: the breaker's failure-swing
    twin), then a body close above X; the zone is the last up-close candle at X (the failed high).
    Bearish mirrors it (high A, low X, lower high B, close below X). Known at the closing break.
    Review fix (rule_coverage A15): the old code took two lows AFTER X and never checked the A low
    before X; `legacy=True` keeps the old order."""
    ph, pl = pivots(h, l, n)
    out, used = [], set()
    for i in range(len(c)):
        for kind, hs, ls, sign in (("bull", ph, pl, 1), ("bear", pl, ph, -1)):
            hk = [p for p in hs if p.known <= i]
            if not hk or (kind, hk[-1].i) in used:
                continue
            H = hk[-1]                                 # X: the swing high the close breaks
            if legacy:
                later = [p for p in ls if p.i > H.i and p.known <= i]
                if len(later) < 2:
                    continue
                L0, L1 = later[-2], later[-1]
            else:
                before = [p for p in ls if p.i < H.i]
                later = [p for p in ls if p.i > H.i and p.known <= i]
                if not before or not later:
                    continue
                L0, L1 = before[-1], later[0]          # A (before X), then B (after X)
                seg = l[H.i + 1:i] if sign > 0 else h[H.i + 1:i]
                if len(seg) and (seg.min() < L0.price if sign > 0 else seg.max() > L0.price):
                    used.add((kind, H.i))              # A's stops were run: a breaker, not this
                    continue
            higher_low = L1.price > L0.price if sign > 0 else L1.price < L0.price
            broke = c[i] > H.price if sign > 0 else c[i] < H.price
            if higher_low and broke:
                blk = order_block(o, h, l, c, H.i - n, H.i, "bear" if sign > 0 else "bull")
                if blk is not None:
                    out.append(Zone(kind, blk.top, blk.bottom, i, blk.src))
                used.add((kind, H.i))
    return out


def mitigation_alive(c, z: Zone, i: int) -> bool:
    """A15 `mit_body_respect` (bodies respect the block, wicks may poke) [our interpretation]: no
    close after the block formed, through bar i, beyond its far side (bullish block: below its
    bottom; bearish: above its top)."""
    seg = c[z.i + 1:i + 1]
    if not len(seg):
        return True
    return bool(seg.min() >= z.bottom) if z.kind == "bull" else bool(seg.max() <= z.top)


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


# --- package setups_models detectors (rule_coverage.md section 3 "setups_models") ------------
# All in bullish terms (the engine mirrors prices for shorts); every one reads closed bars only,
# up to the index the caller passes.

OTE_LO, OTE_HI, OTE_SWEET = 0.62, 0.79, 0.705      # M13 (cc01_004 ~9:44-53:45)


def ote_band(ext: float, hi: float) -> tuple[float, float, float]:
    """M13 OTE of the impulse leg ext (swing low) -> hi: the 62-79% retracement as prices
    (lower, upper) and the 70.5% sweet spot. Bullish: lower = hi - 0.79 x leg."""
    leg = hi - ext
    return hi - OTE_HI * leg, hi - OTE_LO * leg, hi - OTE_SWEET * leg


def three_drives(lows: list, ext: float, ext_i: int, i: int, min_i: int = 0) -> bool:
    """M2.7 three drives ("three Indians", 093 ~10:37; 074 ~32:49) [our interpretation of the bar
    test]: the last two confirmed swing lows (Pivot list `lows`, known by bar i, before the sweep
    extreme ext_i, at or after bar min_i) and the extreme are three successively LOWER lows, and
    the pushes fail - the third drive extends below the second by less than the second extended
    below the first. Bullish: drives down into the swept level."""
    pl = [q for q in lows if min_i <= q.i < ext_i and q.known <= i]
    if len(pl) < 2:
        return False
    a, b = pl[-2], pl[-1]
    if not (a.price > b.price > ext):
        return False
    return (b.price - ext) < (a.price - b.price)


def wick_ce(o, l, c, k: int) -> float:
    """M11c / M0.5: the CE (50%) of candle k's lower wick (body low -> low)."""
    b = min(o[k], c[k])
    return float((b + l[k]) / 2)


def leg_sibi(h, l, o, c, a: int, ext_i: int, c2_dir: bool = False) -> Zone | None:
    """M1.3 / Ep07.6: the last bearish FVG (SIBI) formed in the leg down into the low - third
    candle in [a, ext_i]. None when the leg left none."""
    a = max(int(a), 2)
    last = None
    for k in range(a, int(ext_i) + 1):
        if h[k] < l[k - 2] and (not c2_dir or c[k - 1] < o[k - 1]):
            last = Zone("bear", float(l[k - 2]), float(h[k]), k, k - 1)
    return last


def ifvg_passes(h, l, top: float, bottom: float, a: int, b: int) -> str:
    """A8 depth rule (102 ~1:09:00) for an inversion FVG, bullish terms (an old bearish gap
    top/bottom that a later close went above): how price used the gap between its formation
    (bar a) and the inverting close (bar b), exclusive. "none" = untouched (one pass: the
    inversion itself -> may reach the far edge), "partial" = traded into it, "both" = traded
    through it and back (near edge, CE at most)."""
    if b - a <= 1:
        return "none"
    hh = h[a + 1:b].max()
    if hh > top:
        return "both"
    return "partial" if hh >= bottom else "none"


def reaper(o, h, l, c, a0: int, hk: int, ext_i: int, c2_dir: bool = False) -> Zone | None:
    """A24.2 Reaper (076 ~18:30-22:20) [our interpretation of the bar test]: of a bullish breaker,
    the FVG in the DISCOUNT half of its impulse leg L1 (bar a0) -> H (bar hk) - CE at or below the
    leg's midpoint - that price cut through (a close below its bottom) on the way to the lower low
    (bars hk+1 .. ext_i). The newest such gap; None if none."""
    if hk <= a0:
        return None
    mid = (float(l[a0]) + float(h[hk])) / 2
    out = None
    for z in fvgs(h[:hk + 1], l[:hk + 1], o[:hk + 1], c[:hk + 1], c2_dir):
        if z.kind != "bull" or z.i - 2 < a0 or z.i > hk or z.mid > mid:
            continue
        seg = c[hk + 1:ext_i + 1]
        if len(seg) and seg.min() < z.bottom:
            out = z
    return out


def reclaimed_obs(o, h, l, c, a: int, ext_i: int, i: int) -> list[Zone]:
    """A18 reclaimed OB (cc04_007 ~0:50-5:00; 104 ~46:56): down-close candles on the sell side of
    the curve (bars a .. ext_i-1) each followed by a bounce (the next candle closes up), reclaimed
    after the low - a close above the candle's high in ext_i+1 .. i. Zone = the candle's range,
    known at the reclaiming close."""
    out = []
    for k in range(max(int(a), 0), int(ext_i)):
        if not (c[k] < o[k] and k + 1 <= ext_i and c[k + 1] > o[k + 1]):
            continue
        seg = c[ext_i + 1:i + 1]
        hit = np.flatnonzero(seg > h[k])
        if len(hit):
            out.append(Zone("bull", float(h[k]), float(l[k]), int(ext_i + 1 + hit[0]), k,
                            float((o[k] + c[k]) / 2)))
    return out


def tf_pivots(idx, h, l, base: int, m: int, n: int = 1) -> tuple[list, list]:
    """Ep08.16: swing highs/lows on clock-aligned m-minute bars built from base-minute bars
    (h / l arrays, side space). Pivot.i = the base bar holding the m-minute extreme, Pivot.known =
    the last base bar of the m-minute bar that confirms it (n bars later), only buckets that are
    complete. Returns (highs, lows) sorted by bar."""
    import pandas as pd
    b = pd.Series(np.arange(len(idx)), index=idx).groupby(idx.floor(f"{m}min"))
    first, last = b.min().values, b.max().values
    done = np.asarray((idx[last] - b.min().index) >= pd.Timedelta(minutes=m - base))
    hh = np.array([h[a:z + 1].max() for a, z in zip(first, last)])
    ll = np.array([l[a:z + 1].min() for a, z in zip(first, last)])
    ph, pl = pivots(hh, ll, n)
    out_h = [Pivot(int(first[q.i] + np.argmax(h[first[q.i]:last[q.i] + 1])), q.price, int(last[q.known]))
             for q in ph if done[q.known]]
    out_l = [Pivot(int(first[q.i] + np.argmin(l[first[q.i]:last[q.i] + 1])), q.price, int(last[q.known]))
             for q in pl if done[q.known]]
    return out_h, out_l


def failure_swing(highs: list, lows: list, level: float, max_above: float, i: int,
                  min_i: int = 0) -> tuple | None:
    """M4.5 failure swing (cc05_005) [CC], bullish terms: the last confirmed swing low B (known by
    bar i, at or after min_i) sits above the key level `level` by at most `max_above` - it failed
    to reach it - and the swing high H before B is the breaking point. Returns (B, H) or None."""
    pl = [q for q in lows if q.i >= min_i and q.known <= i]
    if not pl:
        return None
    B = pl[-1]
    if not (level < B.price <= level + max_above):
        return None
    hs = [q for q in highs if q.i < B.i and q.known <= i]
    if not hs:
        return None
    return B, hs[-1]


def implied_fvgs(o, h, l, c) -> list[Zone]:
    """A24.1 implied FVG (035 ~29:46: "the consequent encroachment of this wick and this wick,
    that range projected out"; named once, never defined) [our interpretation of the bar test]:
    three candles with a displacement middle candle (bullish: up-close) whose outer wicks overlap
    (no real FVG: low[k] <= high[k-2]); the implied gap runs from the CE of candle 1's upper wick
    (between its body top and high) up to the CE of candle 3's lower wick (between its low and
    body bottom), when the latter is higher. Bearish mirrors it. Known at the third candle k."""
    out = []
    for k in range(2, len(h)):
        a, b = k - 2, k
        if c[k - 1] > o[k - 1] and l[b] <= h[a]:
            lo_ = (max(o[a], c[a]) + h[a]) / 2          # candle 1 upper-wick CE
            hi_ = (min(o[b], c[b]) + l[b]) / 2          # candle 3 lower-wick CE
            if hi_ > lo_:
                out.append(Zone("bull", float(hi_), float(lo_), k, k - 1))
        elif c[k - 1] < o[k - 1] and h[b] >= l[a]:
            hi_ = (min(o[a], c[a]) + l[a]) / 2          # candle 1 lower-wick CE
            lo_ = (max(o[b], c[b]) + h[b]) / 2          # candle 3 upper-wick CE
            if hi_ > lo_:
                out.append(Zone("bear", float(hi_), float(lo_), k, k - 1))
    return out
