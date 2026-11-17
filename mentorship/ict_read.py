"""The coded ICT direction read (PR #101, runs/ict_direction_2026-11-17/feat.py), as a function the engine can call.

Built from the reasons ICT gives when he calls the morning's direction in his dated live calls. Four signed votes
(+1 up, -1 down, 0 no opinion), each from bars that closed BEFORE the decision bar only:

  s_settle  toward yesterday's settlement (the close of the last bar before 16:15)
  s_first   the side of the range since the 18:00 reopen that was made LAST is done; the other side is next
            (the session high came after the low -> down; the low came after the high -> up)
  s_gapcl   toward the side with more opening gaps of the last five sessions (18:00 reopen vs the close before it)
            within one average daily range of price
  s_req     toward the nearer pair of relative equal highs / lows (5-minute swings of the last `look` sessions,
            within `tol` x the average range of each other) that nothing has traded beyond, within one average range

side = sign of the sum (0 = no read). on_pos = where price sits in the range since 18:00 (0 = its low, 1 = its high).
The average daily range is the mean 09:30-16:00 range of the prior 20 sessions (at least 10).

`read()` works on plain arrays so the same numbers come out of the research files and the engine (tests check that).
"""
from __future__ import annotations

import numpy as np

SESSIONS = 20        # sessions in the average daily range
MIN_SESSIONS = 10
GAP_DAYS = 5         # opening gaps of the last five sessions
PAST_DAYS = 45       # calendar days of history the engine hands over (covers 20 sessions and holidays)


def minutes(index) -> np.ndarray:
    """New York wall-clock minutes since the epoch for a (tz-aware or naive) DatetimeIndex."""
    w = index.tz_localize(None) if getattr(index, "tz", None) is not None else index
    return w.values.astype("datetime64[m]").astype(np.int64)


def _pivots(t, h, l, a, b, k=3):
    """5-minute swing highs / lows in bars [a, b): (level, index from which it is known, index one past its bar)."""
    if b - a < 5 * (2 * k + 1):
        return [], []
    _, st = np.unique(t[a:b] // 5, return_index=True)
    H = np.maximum.reduceat(h[a:b], st)
    L = np.minimum.reduceat(l[a:b], st)
    end = np.r_[st[1:], b - a] + a
    hi, lo = [], []
    for i in range(k, len(H) - k):
        if H[i] > H[i - k:i].max() and H[i] >= H[i + 1:i + k + 1].max():
            hi.append((H[i], end[i + k], end[i]))
        if L[i] < L[i - k:i].min() and L[i] <= L[i + 1:i + k + 1].min():
            lo.append((L[i], end[i + k], end[i]))
    return hi, lo


def _req(piv, x, e, tl, sgn):
    """The nearest untouched pair of equal swing highs (sgn=+1) or lows (sgn=-1): its level, or None."""
    best = None
    for a in range(len(piv)):
        la, _, ea = piv[a]
        for b in range(a + 1, len(piv)):
            lb, _, eb = piv[b]
            if eb - ea < 30 or abs(la - lb) > tl:
                continue
            lvl = max(la, lb) if sgn > 0 else min(la, lb)
            seg = x[ea:e]
            ext = seg.max() if sgn > 0 else seg.min()
            if (ext - lvl) * sgn > 0:                    # something traded beyond the pair: it is gone
                continue
            if best is None or (lvl - best) * sgn < 0:
                best = lvl
    return best


def read(t, o, h, l, c, e: int, look: int = 3, tol: float = 0.02):
    """The read at bar e (the first bar NOT known; bars [0, e) are closed). t: New York wall-clock minutes since the
    epoch, ascending. Returns dict(side, total, s_settle, s_first, s_gapcl, s_req, on_pos, adr, settle, prev_rng = yesterday's
    09:30-16:00 range as a share of adr) or None when there is
    not enough history (20 prior sessions wanted, 10 needed; the 18:00 reopen and an hour of bars since it)."""
    if e < 60:
        return None
    dd = int(t[e - 1] // 1440)
    if t[e - 1] % 1440 >= 1080:                              # an evening bar belongs to the next day's session
        dd += 1

    def ix(day, minute):
        return int(np.searchsorted(t, day * 1440 + minute))

    # prior sessions: days with a 09:30 bar before today
    first = int(t[0] // 1440) + 1
    days = [d for d in range(first, dd) if (lambda a: a < e and t[a] == d * 1440 + 570)(ix(d, 570))]
    if len(days) < max(MIN_SESSIONS, GAP_DAYS, look):
        return None
    rng = []
    for d in days[-SESSIONS:]:
        a, b = ix(d, 570), ix(d, 960)
        rng.append(h[a:b].max() - l[a:b].min())
    adr = float(np.mean(rng))
    y = days[-1]
    sa, sb = ix(y, 570), ix(y, 975)
    if sb <= sa or not adr > 0:
        return None
    settle = float(c[sb - 1])
    s0 = ix(dd, -360)                                        # 18:00 the evening before
    if e - s0 < 60:
        return None
    p = float(c[e - 1])

    # 1. toward yesterday's settlement
    s_settle = int(np.sign(settle - p))

    # 2. which side of the range since 18:00 was made last
    ih = s0 + int(np.argmax(h[s0:e]))
    il = s0 + int(np.argmin(l[s0:e]))
    r = h[ih] - l[il]
    on_pos = float((p - l[il]) / r) if r > 0 else 0.5
    s_first = 0 if ih == il else (-1 if ih > il else 1)

    # 3. opening gaps of the last five sessions (today's included), counted by side within one average range
    up = dn = 0
    for d in [dd] + days[-(GAP_DAYS - 1):]:
        i18 = ix(d, -360)
        if 0 < i18 < e and i18 + 1 < e:
            g = (c[i18 - 1] + o[i18]) / 2 - p
            if abs(g) <= adr:
                up += g > 0
                dn += g < 0
    s_gapcl = int(np.sign(up - dn))

    # 4. relative equal highs / lows of the last `look` sessions
    a0 = ix(([dd] + days[::-1])[look - 1], -360)
    hi, lo = _pivots(t, h, l, a0, e)
    hi = [x for x in hi if x[1] <= e]
    lo = [x for x in lo if x[1] <= e]
    reh, rel = _req(hi, h, e, tol * adr, +1), _req(lo, l, e, tol * adr, -1)
    du = reh - p if reh is not None else np.inf
    dn_ = p - rel if rel is not None else np.inf
    s_req = 0 if min(du, dn_) > adr else (1 if du < dn_ else -1)

    total = s_settle + s_first + s_gapcl + s_req
    return dict(side=int(np.sign(total)), total=int(total), s_settle=s_settle, s_first=s_first, s_gapcl=s_gapcl,
                s_req=s_req, on_pos=on_pos, adr=adr, settle=settle, prev_rng=float(rng[-1]) / adr)


def past_bars(df, d):
    """The bars the read needs before day d: from 18:00 PAST_DAYS calendar days back up to midnight of d."""
    import pandas as pd
    a = pd.Timestamp(d, tz=df.index.tz)
    return df[(df.index >= a - pd.Timedelta(days=PAST_DAYS, hours=6)) & (df.index < a)]
