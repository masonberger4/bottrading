"""PD arrays on monthly, weekly, daily, 4h and 1h bars (spec section 3).

Built with the mentorship.levels detectors (not edited). Each array keeps `known`, the time
its completing bar closed, and `touch`, the first later time price traded to it (computed on
1h bars). An array price already traded to is exhausted (cc07_004 ~00:04:00; cc07_005 ~23:13).
Swings are 3-candle swings (pivots n=1, project memory).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from mentorship import levels as L

# PD array matrix order from market price outward, spoken order (cc05_014 ~18:20, cc07_004
# ~00:01:01); "slide" puts the FVG before the void.
ORDER = {"mitigation": 0, "breaker": 1, "void": 2, "fvg": 3, "ob": 4, "rejection": 5, "old": 6}
ORDER_SLIDE = {**ORDER, "void": 3, "fvg": 2}
TF_RANK = {"1h": 0, "4h": 1, "D": 2, "W": 3, "M": 4}
STOP_TYPES = {"breaker", "mitigation", "void", "fvg"}   # entered on a stop order (cc06_008 ~14:20)


@dataclass
class Arr:
    tf: str
    typ: str
    kind: str              # "bull" = discount array (support), "bear" = premium array
    top: float
    bottom: float
    mt: float
    entry: float           # the exact price a limit order rests at
    known: pd.Timestamp
    src: int = -1

    @property
    def near(self) -> float:
        """Edge price reaches first when it comes from the other side (target edge)."""
        return self.bottom if self.kind == "bear" else self.top


def _ob(o, h, l, c, start, end, kind, mt_mode, ob_entry):
    z = L.order_block_blend(o, h, l, c, start, end, kind)
    if z is None:
        return None
    k = z.src
    while k + 1 <= end and ((c[k + 1] < o[k + 1]) if kind == "bull" else (c[k + 1] > o[k + 1])):
        k += 1
    sl = slice(z.src, k + 1)
    if mt_mode == "body":
        mt = z.mt
    else:
        mt = (z.top + z.bottom) / 2
    if kind == "bull":     # OB high = fair level, highest open of the series = conservative
        entry = z.top if ob_entry == "high" else float(max(o[sl]))   # (cc06_004 ~13:07; cc05_015 ~16:46)
    else:
        entry = z.bottom if ob_entry == "high" else float(min(o[sl]))
    return z, mt, entry


def build(frame: pd.DataFrame, tf: str, mt_mode: str = "range", ob_entry: str = "high",
          tick: float = 0.25) -> list[Arr]:
    o, h, l, c = (frame[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    end = frame.end
    out: list[Arr] = []

    def add(typ, z, entry=None, mt=None):
        out.append(Arr(tf, typ, z.kind, float(z.top), float(z.bottom),
                       float(z.mid if mt is None else mt),
                       float((z.top if z.kind == "bull" else z.bottom) if entry is None else entry),
                       end.iloc[z.i], z.src))

    for z in L.fvgs(h, l):
        add("fvg", z)
        r = _ob(o, h, l, c, z.i - 4, z.i - 2, z.kind, mt_mode, ob_entry)
        if r is not None:            # OB = last opposite-close candle(s) before the displacement
            ob, mt, entry = r
            disp = c[z.i - 1]
            if (z.kind == "bull" and disp > ob.top) or (z.kind == "bear" and disp < ob.bottom):
                add("ob", L.Zone(z.kind, ob.top, ob.bottom, z.i, ob.src), entry, mt)
    for z in L.voids(h, l):
        add("void", z)
    for z in L.breakers(o, h, l, c, n=1):
        add("breaker", z, mt=z.mt)
    for z in L.mitigation_blocks(o, h, l, c, n=1):
        add("mitigation", z)
    for z in L.rejection_blocks(o, h, l, c, n=1):
        add("rejection", z)
    ph, pl = L.pivots(h, l, n=1)
    for p in ph:                     # old high: buy stops above, premium extreme
        out.append(Arr(tf, "old", "bear", p.price, p.price, p.price, p.price + tick, end.iloc[p.known], p.i))
    for p in pl:                     # old low: sell stops below; buy just beyond it (turtle soup)
        out.append(Arr(tf, "old", "bull", p.price, p.price, p.price, p.price - tick, end.iloc[p.known], p.i))
    return out


class Sparse:
    """Range-min (lows) and range-max (highs) tables over 1h bars for 'first bar at or after s
    that trades to x' queries in O(log n)."""

    def __init__(self, lo: np.ndarray, hi: np.ndarray):
        self.n = len(lo)
        self.mn, self.mx = [np.asarray(lo, float)], [np.asarray(hi, float)]
        k = 1
        while (1 << k) <= self.n:
            a, b = self.mn[-1], self.mx[-1]
            s = 1 << (k - 1)
            self.mn.append(np.minimum(a[:-s], a[s:]))
            self.mx.append(np.maximum(b[:-s], b[s:]))
            k += 1

    def first_le(self, s: int, x: float) -> int:
        """First i >= s with low[i] <= x, or n."""
        i = s
        for k in range(len(self.mn) - 1, -1, -1):
            t = self.mn[k]
            if i < len(t) and t[i] > x:
                i += 1 << k
        return min(i, self.n)

    def first_ge(self, s: int, x: float) -> int:
        i = s
        for k in range(len(self.mx) - 1, -1, -1):
            t = self.mx[k]
            if i < len(t) and t[i] < x:
                i += 1 << k
        return min(i, self.n)


class Book:
    """All arrays of all timeframes as parallel numpy columns, plus touch times on 1h bars."""

    def __init__(self, frames: dict[str, pd.DataFrame], tfs=("4h", "D", "W", "M"),
                 mt_mode: str = "range", ob_entry: str = "high", tick: float = 0.25):
        arrs = [a for tf in tfs for a in build(frames[tf], tf, mt_mode, ob_entry, tick)]
        self.arrs = arrs
        h1 = frames["1h"]
        self.h1_start = h1.start
        sp = Sparse(h1.low.to_numpy(float), h1.high.to_numpy(float))
        n = len(arrs)
        self.tf = np.array([TF_RANK[a.tf] for a in arrs], int)
        self.typ = np.array([a.typ for a in arrs], object)
        self.bull = np.array([a.kind == "bull" for a in arrs], bool)
        self.top = np.array([a.top for a in arrs], float)
        self.bottom = np.array([a.bottom for a in arrs], float)
        self.entry = np.array([a.entry for a in arrs], float)
        self.known = pd.DatetimeIndex([a.known for a in arrs]) if n else pd.DatetimeIndex([], tz="America/New_York")
        k0 = h1.start.searchsorted(self.known, side="left") if n else np.array([], int)
        self.k0 = np.asarray(k0, int)      # first 1h bar that starts at/after the array is known
        touch = np.empty(n, int)
        dead = np.empty(n, int)            # first 1h bar that CLOSES through the far side
        cl = h1.close.to_numpy(float)
        spc = Sparse(cl, cl)
        for j, a in enumerate(arrs):
            s = int(self.k0[j])
            if a.kind == "bull":
                touch[j] = sp.first_le(s, a.top)
                dead[j] = spc.first_le(s, a.bottom - 1e-9) if a.typ != "old" else touch[j]
            else:
                touch[j] = sp.first_ge(s, a.bottom)
                dead[j] = spc.first_ge(s, a.top + 1e-9) if a.typ != "old" else touch[j]
        self.touch, self.dead = touch, dead

    def fresh(self, k: int) -> np.ndarray:
        """Arrays usable at the start of 1h bar k: known before it and not traded to yet."""
        return (self.k0 <= k) & (self.touch >= k)

    def alive(self, k: int) -> np.ndarray:
        """Known and not closed through yet (may have been traded into)."""
        return (self.k0 <= k) & (self.dead >= k)
