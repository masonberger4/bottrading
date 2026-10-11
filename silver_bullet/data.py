"""Bar data: CSV loading, Schwab price history, and a synthetic generator for smoke tests."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Iterator

import numpy as np
import pandas as pd

from .strategy import NY, Bar


def normalize(df: pd.DataFrame) -> pd.DataFrame:
    """Lower-case OHLCV columns and a tz-aware New York DatetimeIndex."""
    df = df.rename(columns={c: c.strip().lower() for c in df.columns})
    if not isinstance(df.index, pd.DatetimeIndex):
        for c in ("datetime", "timestamp", "time", "date", "ts_event"):
            if c in df.columns:
                df = df.set_index(pd.to_datetime(df.pop(c), utc=False))
                break
    idx = df.index
    if idx.tz is None:
        idx = idx.tz_localize(NY, ambiguous="infer", nonexistent="shift_forward")
    df.index = idx.tz_convert(NY)
    if "volume" not in df.columns:
        df["volume"] = 0.0
    return df[["open", "high", "low", "close", "volume"]].sort_index()


def load_csv(path: str, tz: str | None = None) -> pd.DataFrame:
    """Load OHLCV bars. If timestamps are naive, `tz` says what zone they're in (default New York)."""
    df = pd.read_csv(path)
    df = df.rename(columns={c: c.strip().lower() for c in df.columns})
    tcol = next(c for c in ("datetime", "timestamp", "time", "date", "ts_event") if c in df.columns)
    ts = pd.to_datetime(df.pop(tcol))
    if ts.dt.tz is None and tz:
        ts = ts.dt.tz_localize(tz)
    df.index = pd.DatetimeIndex(ts)
    return normalize(df)


def bar_minutes(df: pd.DataFrame) -> int:
    d = df.index.to_series().diff().dropna()
    return max(1, int(d.mode().iloc[0].total_seconds() // 60)) if len(d) else 1


def iter_bars(df: pd.DataFrame) -> Iterator[Bar]:
    for ts, o, h, l, c, v in zip(df.index, df.open.values, df.high.values, df.low.values,
                                 df.close.values, df.volume.values):
        yield Bar(ts.to_pydatetime(), float(o), float(h), float(l), float(c), float(v))


def schwab_history(client, symbol: str, days: int = 45, minutes: int = 1,
                   extended_hours: bool = True) -> pd.DataFrame:
    """Pull intraday bars from the Schwab Market Data API (equities/ETFs such as SPY).
    Schwab keeps roughly 48 days of 1-minute history and longer for 5-minute bars."""
    fn = {1: client.get_price_history_every_minute,
          5: client.get_price_history_every_five_minutes,
          15: client.get_price_history_every_fifteen_minutes}[minutes]
    end = datetime.now().astimezone()
    frames = []
    chunk = 10  # request in 10-day slices to stay under per-call limits
    start = end - timedelta(days=days)
    while start < end:
        stop = min(start + timedelta(days=chunk), end)
        r = fn(symbol, start_datetime=start, end_datetime=stop,
               need_extended_hours_data=extended_hours)
        r.raise_for_status()
        candles = r.json().get("candles", [])
        if candles:
            frames.append(pd.DataFrame(candles))
        start = stop
    if not frames:
        raise RuntimeError(f"Schwab returned no candles for {symbol}")
    df = pd.concat(frames).drop_duplicates("datetime")
    df.index = pd.to_datetime(df.pop("datetime"), unit="ms", utc=True)
    return normalize(df)


def synthetic(days: int = 60, start: str = "2026-06-01", price: float = 5500.0,
              seed: int = 7, tick: float = 0.25, trend: float = 0.12) -> pd.DataFrame:
    """Random-walk 1-minute futures bars (Sun-Fri 18:00-17:00 NY) with a realistic
    intraday volatility profile. For testing the plumbing only: it has no edge to find."""
    rng = np.random.default_rng(seed)
    rows = []
    day = pd.Timestamp(start, tz=NY).normalize()
    made = 0
    while made < days:
        if day.weekday() < 5:
            sess = pd.date_range(day - pd.Timedelta(hours=6), day + pd.Timedelta(hours=17),
                                 freq="1min", inclusive="left", tz=NY)
            hrs = sess.hour + sess.minute / 60
            vol = np.where((hrs >= 9.5) & (hrs < 16), 1.6, np.where((hrs >= 2) & (hrs < 5), 0.9, 0.45))
            vol = vol * np.where((hrs >= 9.5) & (hrs < 10.5), 1.6, 1.0)
            # mild trending regimes so structure shifts and gaps actually occur
            drift = np.repeat(rng.normal(0, trend, len(sess) // 30 + 1), 30)[: len(sess)]
            rets = drift + rng.standard_t(4, len(sess)) * vol * 0.55
            closes = price + np.cumsum(rets)
            opens = np.concatenate([[price], closes[:-1]])
            wick = np.abs(rng.normal(0, 0.5, (2, len(sess)))) * vol
            highs = np.maximum(opens, closes) + wick[0]
            lows = np.minimum(opens, closes) - wick[1]
            r = lambda a: np.round(a / tick) * tick
            for ts, o, h, l, c in zip(sess, r(opens), r(highs), r(lows), r(closes)):
                rows.append((ts, o, h, l, c, 100))
            price = float(closes[-1])
            made += 1
        day += pd.Timedelta(days=1)
    df = pd.DataFrame(rows, columns=["datetime", "open", "high", "low", "close", "volume"])
    return normalize(df.set_index("datetime"))
