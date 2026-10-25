"""Per-bar signals for every stock, using only information known at that bar's close.

Everything is a (bars x symbols) numpy array on the full-session grid that data.to_panel
builds (390 bars a day for 1-minute data, 78 for 5-minute). Lookbacks are counted in bars.
Signals are scaled by each stock's recent per-bar volatility so one weight means the same
thing for a quiet stock and a jumpy one.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .daytypes import day_type

LOOKBACKS = (1, 2, 3, 5, 10, 15, 30, 60)
SESSION_MINUTES = 390
OR_MINUTES = 15          # opening range length for the breakout signal


@dataclass
class Features:
    index: pd.DatetimeIndex
    symbols: list
    open: np.ndarray
    close: np.ndarray
    bar_minutes: int
    bars_per_day: int
    day: np.ndarray          # day number per row
    bar: np.ndarray          # bar number within the day per row
    z: dict                  # lookback -> vol-scaled return
    idio: dict               # lookback -> vol-scaled return minus the cross-sectional mean
    vwap: np.ndarray         # distance from today's VWAP
    orb: np.ndarray          # position vs. the opening range (0 inside the first 15 minutes)
    volshock: np.ndarray     # abnormal volume, signed by the last bar's direction
    dayret: np.ndarray       # return since today's open
    gap: np.ndarray          # overnight gap
    day_type: list           # daytypes.day_type of each day
    earn: np.ndarray         # (days x symbols) True on a stock's earnings reaction day
    imb: np.ndarray          # top-of-book size imbalance (0 on days with no recording)
    depth: np.ndarray        # top-5-level book size imbalance
    flow: np.ndarray         # signed trade flow inside the bar
    spread: np.ndarray       # quoted spread, bps
    has_book: np.ndarray     # (days,) True where order-book data was recorded

    @property
    def days(self) -> int:
        return int(self.day.max()) + 1 if len(self.day) else 0


def _clean(a):
    return np.clip(np.nan_to_num(a, nan=0.0, posinf=0.0, neginf=0.0), -5, 5)


def build(panel: dict, earnings_days: set | None = None, book_root=None) -> Features:
    """earnings_days: {(symbol, date)} reaction days; read from the earnings file if None."""
    o, h, l, c, v = (panel[k].to_numpy(float) for k in ("open", "high", "low", "close", "volume"))
    idx = panel["close"].index
    n = len(idx)
    bm = int((idx[1] - idx[0]).total_seconds() // 60)
    bpd = SESSION_MINUTES // bm
    assert n % bpd == 0, "panel must be on a full-session grid"
    bar = np.tile(np.arange(bpd), n // bpd)
    day = np.repeat(np.arange(n // bpd), bpd)
    first = bar == 0
    lc, lo = np.log(c), np.log(o)
    if earnings_days is None:
        from .earnings import reaction_days
        earnings_days = reaction_days()

    r1 = np.vstack([np.zeros((1, c.shape[1])), np.diff(lc, axis=0)])
    r1[first] = (lc - lo)[first]                      # no overnight jump in the 1-bar series
    vol = pd.DataFrame(r1).rolling(60, min_periods=20).std().to_numpy()
    vol = np.where(np.isnan(vol), 1e-3, vol)       # only the first bars of the sample
    vol = np.maximum(vol, 1e-5)

    z, idio = {}, {}
    for k in LOOKBACKS:
        rk = np.full_like(lc, np.nan)
        rk[k:] = lc[k:] - lc[:-k]
        rk[bar < k] = np.nan                       # never look back across the overnight gap
        zk = rk / (vol * np.sqrt(k))
        z[k] = _clean(zk)
        idio[k] = _clean(zk - np.nanmean(zk, axis=1, keepdims=True))

    df_day = pd.Series(day)
    def by_day(a, fn):
        return pd.DataFrame(a).groupby(df_day.values).transform(fn).to_numpy()

    tp = (h + l + c) / 3
    vwap = by_day(tp * v, "cumsum") / np.maximum(by_day(v, "cumsum"), 1)
    vwap = np.where(by_day(v, "cumsum") > 0, vwap, c)
    scale = vol * np.sqrt(bar[:, None] + 1)
    vwap_dev = (lc - np.log(vwap)) / scale

    open_px = np.repeat(o[first], bpd, axis=0)
    dayret = (lc - np.log(open_px)) / scale

    in_or = (bar < max(1, OR_MINUTES // bm))[:, None]
    or_hi = by_day(np.where(in_or, h, np.nan), "max")
    or_lo = by_day(np.where(in_or, l, np.nan), "min")
    half = np.maximum((or_hi - or_lo) / 2, 1e-9)
    orb = np.where(in_or, 0.0, (c - (or_hi + or_lo) / 2) / half)

    vavg = pd.DataFrame(v).rolling(30, min_periods=5).mean().shift(1).to_numpy()
    volshock = np.log((v + 1) / (np.nan_to_num(vavg) + 1)) * np.sign(r1)

    prev_close = np.vstack([np.full((1, c.shape[1]), np.nan), c[:-1]])
    gap_d = (lo - np.log(prev_close))[first] / (vol[first] * np.sqrt(bpd))
    gap = np.repeat(gap_d, bpd, axis=0)

    from . import book
    bk = book.build(idx, bpd, bm, list(panel["close"].columns),
                    **({"root": book_root} if book_root is not None else {}))
    return Features(idx, list(panel["close"].columns), o, c, bm, bpd, day, bar, z, idio,
                    _clean(vwap_dev), _clean(orb), _clean(volshock), _clean(dayret), _clean(gap),
                    [day_type(d) for d in idx[::bpd].date],
                    np.array([[(s, d) in earnings_days for s in panel["close"].columns]
                              for d in idx[::bpd].date], dtype=bool).reshape(-1, c.shape[1]),
                    2 * bk["imb"], 2 * bk["depth"], 2 * bk["flow"], bk["spread"], bk["has_book"])
