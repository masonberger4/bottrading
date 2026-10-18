"""Per-timeframe order flow for the MWD sequential (spec section 4).

[our interpretation of cc06_004 ~1:02 / ~14:47 and cc06_005 ~0:46]
  dir         +1 after a body close above the latest 3-candle swing high with a bullish FVG in
              the breaking leg (displacement off a discount array); -1 mirrored. A bearish
              breaker also sets -1 (and a bullish breaker +1): "only a bearish breaker cancels it".
  via         what set dir: "disp" or "breaker".
  correcting  dir is +1 but a later body close went below the latest swing low (a plain
              opposite break, no breaker); cleared by the next close above the latest swing high.
State at index k is the state after bar k closed.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from mentorship import levels as L


def states(frame: pd.DataFrame) -> pd.DataFrame:
    o, h, l, c = (frame[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    n = len(c)
    ph, pl = L.pivots(h, l, n=1)
    fv = L.fvgs(h, l)
    bull_fvg = np.zeros(n, int)
    bear_fvg = np.zeros(n, int)
    for z in fv:
        (bull_fvg if z.kind == "bull" else bear_fvg)[z.i] += 1
    cb, cs = np.cumsum(bull_fvg), np.cumsum(bear_fvg)
    brk = {}
    for z in L.breakers(o, h, l, c, n=1):
        brk.setdefault(z.i, z.kind)
    d, via, corr = np.zeros(n, int), np.empty(n, object), np.zeros(n, bool)
    cur, cur_via, cur_corr = 0, "", False
    hi_i = lo_i = 0                          # next pivot to become known
    last_hi = last_lo = None
    used_hi, used_lo = set(), set()
    for k in range(n):
        while hi_i < len(ph) and ph[hi_i].known <= k:
            last_hi = ph[hi_i]
            hi_i += 1
        while lo_i < len(pl) and pl[lo_i].known <= k:
            last_lo = pl[lo_i]
            lo_i += 1
        if last_hi is not None and last_hi.i not in used_hi and c[k] > last_hi.price:
            used_hi.add(last_hi.i)
            a = min(last_hi.i, last_lo.i if last_lo is not None else last_hi.i)
            if cb[k] - (cb[a - 1] if a > 0 else 0) > 0:
                cur, cur_via, cur_corr = 1, "disp", False
            elif cur == 1:
                cur_corr = False
            elif cur == -1:
                cur_corr = True
        if last_lo is not None and last_lo.i not in used_lo and c[k] < last_lo.price:
            used_lo.add(last_lo.i)
            a = min(last_lo.i, last_hi.i if last_hi is not None else last_lo.i)
            if cs[k] - (cs[a - 1] if a > 0 else 0) > 0:
                cur, cur_via, cur_corr = -1, "disp", False
            elif cur == -1:
                cur_corr = False
            elif cur == 1:
                cur_corr = True
        if k in brk:
            cur, cur_via, cur_corr = (1 if brk[k] == "bull" else -1), "breaker", False
        d[k], via[k], corr[k] = cur, cur_via, cur_corr
    return pd.DataFrame({"dir": d, "via": via, "correcting": corr}, index=frame.index)


def at(st: pd.DataFrame, frame: pd.DataFrame, t: pd.Timestamp) -> tuple[int, str, bool]:
    """State of the last bar of `frame` closed at or before t (0, "", False before any bar)."""
    k = int(frame.end.searchsorted(t, side="right")) - 1
    if k < 0:
        return 0, "", False
    r = st.iloc[k]
    return int(r.dir), str(r.via), bool(r.correcting)
