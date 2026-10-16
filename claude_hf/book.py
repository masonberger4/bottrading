"""Order-book signals per bar, built from what recorder.py saved.

For every bar (as of its close, so nothing from inside a later bar leaks in):
  imb     top-of-book size imbalance, (bid size - ask size) / (bid size + ask size)
  depth   imbalance of total size over the top recorded book levels
  flow    signed trade volume inside the bar / total traded volume inside the bar, where a
          trade above the prevailing mid counts as buying and below as selling
  spread  quoted spread in bps
Bars on days with no recording are 0 (no signal), and `has_book` marks the days that have it.
"""
from __future__ import annotations

import gzip
import io
from pathlib import Path

import numpy as np
import pandas as pd

from .recorder import BOOK_LEVELS, ROOT


def _read(path: Path):
    """Read a gzipped CSV that may still be open for writing, or was cut off by a crash:
    keep every complete line before the end of the readable data."""
    lines = []
    try:
        with gzip.open(path, "rt", newline="") as f:
            for line in f:
                lines.append(line)
    except (EOFError, OSError):
        pass
    if lines and not lines[-1].endswith("\n"):
        lines.pop()
    if len(lines) < 2:
        return None
    return pd.read_csv(io.StringIO("".join(lines)))


def load_day(day, root: Path = ROOT):
    d = Path(root) / day.isoformat()
    if not (d / "l1.csv.gz").exists():
        return None, None
    book = _read(d / "book.csv.gz") if (d / "book.csv.gz").exists() else None
    return _read(d / "l1.csv.gz"), book


def _asof(times: pd.DatetimeIndex, ts, values) -> np.ndarray:
    """Last value at or before each time (ts sorted ascending); NaN before the first."""
    t = pd.DatetimeIndex(ts).as_unit("ns").asi8
    v = np.asarray(values, float)
    i = np.searchsorted(t, times.as_unit("ns").asi8, side="right") - 1
    return np.where(i >= 0, v[np.clip(i, 0, None)], np.nan) if len(v) else np.full(len(times), np.nan)


def day_features(l1, book, bar_starts: pd.DatetimeIndex, bar_minutes: int, symbols) -> dict:
    n, m = len(bar_starts), len(symbols)
    out = {k: np.zeros((n, m)) for k in ("imb", "depth", "flow", "spread")}
    closes = bar_starts + pd.Timedelta(minutes=bar_minutes)
    tz = bar_starts.tz
    for j, s in enumerate(symbols):
        q = l1[l1.symbol == s] if l1 is not None else None
        if q is not None and len(q):
            q = q.sort_values("ts_ms")
            t = pd.to_datetime(q.ts_ms, unit="ms", utc=True).dt.tz_convert(tz)
            bid, ask = q.bid_price.to_numpy(float), q.ask_price.to_numpy(float)
            bs, as_ = q.bid_size.to_numpy(float), q.ask_size.to_numpy(float)
            mid = (bid + ask) / 2
            ok = (bid > 0) & (ask > bid)
            imb = np.where(ok & (bs + as_ > 0), (bs - as_) / np.maximum(bs + as_, 1), np.nan)
            spr = np.where(ok, (ask - bid) / mid * 1e4, np.nan)
            out["imb"][:, j] = _asof(closes, t, pd.Series(imb).ffill())
            out["spread"][:, j] = _asof(closes, t, pd.Series(spr).ffill())
            vol = q.total_volume.to_numpy(float)
            dv = np.r_[0.0, np.clip(np.diff(vol), 0, None)]
            prev_mid = np.r_[np.nan, mid[:-1]]
            sign = np.sign(q.last_price.to_numpy(float) - prev_mid)
            bins = np.searchsorted(closes.as_unit("ns").asi8, pd.DatetimeIndex(t).as_unit("ns").asi8,
                                   side="left")
            keep = bins < n
            signed = np.bincount(bins[keep], np.nan_to_num(sign * dv)[keep], n)
            total = np.bincount(bins[keep], dv[keep], n)
            out["flow"][:, j] = np.where(total > 0, signed / np.maximum(total, 1), 0.0)
        b = book[book.symbol == s] if book is not None else None
        if b is not None and len(b):
            b = b.sort_values("ts_ms")
            t = pd.to_datetime(b.ts_ms, unit="ms", utc=True).dt.tz_convert(tz)
            bsz = b[[f"bid{i}_sz" for i in range(BOOK_LEVELS)]].fillna(0).sum(axis=1)
            asz = b[[f"ask{i}_sz" for i in range(BOOK_LEVELS)]].fillna(0).sum(axis=1)
            depth = (bsz - asz) / np.maximum(bsz + asz, 1)
            out["depth"][:, j] = _asof(closes, t, depth)
    for k in out:
        out[k] = np.nan_to_num(out[k])
    return out


def build(index: pd.DatetimeIndex, bars_per_day: int, bar_minutes: int, symbols,
          root: Path = ROOT) -> dict:
    """Book signals on a Features grid. Returns arrays (rows x symbols) and has_book (days)."""
    n_days = len(index) // bars_per_day
    out = {k: np.zeros((len(index), len(symbols))) for k in ("imb", "depth", "flow", "spread")}
    has = np.zeros(n_days, dtype=bool)
    for d in range(n_days):
        starts = index[d * bars_per_day:(d + 1) * bars_per_day]
        l1, book = load_day(starts[0].date(), root)
        if l1 is None:
            continue
        has[d] = True
        f = day_features(l1, book, starts, bar_minutes, symbols)
        for k in out:
            out[k][d * bars_per_day:(d + 1) * bars_per_day] = f[k]
    out["has_book"] = has
    return out
