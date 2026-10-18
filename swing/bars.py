"""Higher-timeframe bars built from 1-minute futures data (spec section 1).

CME session [our interpretation]: the trading day runs 18:00 ET to 17:00 ET and is dated by the
day it ends; 4h blocks are anchored at the 18:00 open (18, 22, 02, 06, 10, 14; the last one is
3h because of the 17:00-18:00 halt); a week runs Sunday 18:00 to Friday 17:00; a month is the
calendar month of its daily sessions.

Every frame carries `end`, the time the bar is closed and usable (its last minute + 1 minute).
Closed candles only: a caller may use bar k at time t only if frame.end[k] <= t.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

NY = "America/New_York"
TFS = ("1h", "4h", "D", "W", "M")
ONE = pd.Timedelta(minutes=1)


def load(path: str | Path = "data/mentorship/ES_1min_db.csv") -> pd.DataFrame:
    """1m bars written by mentorship.databento_data.build (back-adjusted, with `adj`/`roll`).
    Swing arrays span rolls, so the bot works on the back-adjusted series: in relative terms it
    equals the current contract's native prices (native = adjusted - adj), and only absolute
    round numbers would differ (owner directive #13 is about those)."""
    df = pd.read_csv(path, index_col=0)
    df.index = pd.to_datetime(df.index, utc=True).tz_convert(NY)
    return df[["open", "high", "low", "close"]].astype(float).sort_index()


def session_day(idx: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Trading day of each bar: 18:00 ET and later belong to the next day."""
    return (idx + pd.Timedelta(hours=6)).normalize().tz_localize(None)


def _agg(df: pd.DataFrame, key) -> pd.DataFrame:
    g = df.assign(ts=df.index).groupby(key, sort=True)
    return pd.DataFrame({"open": g.open.first(), "high": g.high.max(), "low": g.low.min(),
                         "close": g.close.last(), "start": g.ts.first(), "end": g.ts.last() + ONE,
                         "n": g.close.size()})


def resample(df: pd.DataFrame, min_daily_bars: int = 60) -> dict[str, pd.DataFrame]:
    """1h, 4h, D, W, M frames (RangeIndex, columns open high low close start end [day])."""
    day = session_day(df.index)
    d = _agg(df, day)
    d = d[d.n >= min_daily_bars]                       # holiday stubs are not sessions
    keep = pd.Index(day).isin(d.index)
    df, day = df[keep], day[keep]

    local = df.index.tz_localize(None)                 # wall-clock keys (no DST ambiguity)
    h1 = _agg(df, local.floor("h"))
    h4 = _agg(df, (local - pd.Timedelta(hours=18)).floor("4h") + pd.Timedelta(hours=18))

    d.index.name = "day"
    wk = d.index.to_period("W-FRI")
    w = _week_month(d, wk)
    m = _week_month(d, d.index.to_period("M"))
    out = {"1h": h1, "4h": h4, "D": d.reset_index(), "W": w, "M": m}
    for k in ("1h", "4h"):
        out[k] = out[k].reset_index(drop=True)
        out[k]["day"] = session_day(pd.DatetimeIndex(out[k].start))
    return {k: v.drop(columns="n", errors="ignore") for k, v in out.items()}


def _week_month(d: pd.DataFrame, key) -> pd.DataFrame:
    g = d.assign(dd=d.index).groupby(key, sort=True)
    out = pd.DataFrame({"open": g.open.first(), "high": g.high.max(), "low": g.low.min(),
                        "close": g.close.last(), "start": g.start.first(), "end": g.end.last(),
                        "first_day": g.dd.first(), "last_day": g.dd.last()})
    return out.reset_index(drop=True)


def known_before(frame: pd.DataFrame, t: pd.Timestamp) -> int:
    """Number of bars of `frame` closed at or before t (bars [0, n) are usable at t)."""
    return int(frame.end.searchsorted(t, side="right"))
