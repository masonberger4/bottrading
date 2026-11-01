"""DXY bars for the intraday / hourly dollar rules (dxy_intraday_spec_2026-10-31.md, section 0). No look-ahead: a DXY bar is visible only once it has closed.

Sources (`dxy_htf_src` / what is on disk):
  spot  data/dxy/spot_dxy_1m_close_2019-2025_NYtime.csv.gz (1-minute CLOSE only, NY clock, 2019-2025; also looked for directly under data/)
  dx    Databento DX 1h futures bars (databento_extra.dx_hourly: 2019-2026, back-adjusted; the only source for 2026 and for bars of 60 minutes and up in a spot gap)
Highs / lows from a close-only file (spec 0.2 mode "line"): high = the highest 1-minute close in the bar (and the previous bar's close), low the lowest; open = the previous bar's close. Bars of 5 minutes and up only.
`bars(tf, src)` returns a frame indexed by bar START (NY) with open / high / low / close and `end`; `closed(frame, t)` the rows with end <= t.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

NY = "America/New_York"
SPOT_FILES = ("data/dxy/spot_dxy_1m_close_2019-2025_NYtime.csv.gz", "data/spot_dxy_1m_close_2019-2025_NYtime.csv.gz",
              "data/mentorship/dxy/spot_dxy_1m_close_2019-2025_NYtime.csv.gz")
BAD_HOURS = tuple(pd.Timestamp(x, tz=NY) for x in (                    # the stale hours of the spot file (spec 0.1): the carried quote barely moves, treat as no data
    "2023-03-07 10:00", "2019-03-13 10:00", "2019-06-12 10:00", "2019-09-11 10:00", "2019-12-11 10:00", "2020-03-19 09:00", "2020-03-19 10:00",
    "2020-03-20 10:00", "2020-03-20 13:00", "2020-03-20 15:00", "2022-06-15 14:00", "2022-06-15 15:00", "2023-03-02 09:00", "2023-03-22 13:00",
    "2023-04-28 10:00", "2023-05-19 11:00", "2023-05-31 11:00"))
DXY_TICK = 0.005                      # the DX futures tick [our interpretation; spot quotes to 0.001]

_SPOT: dict = {}
_CACHE: dict = {}


def set_spot(df: pd.DataFrame | None) -> None:
    """Install a 1-minute close frame (column `close`, NY index) - tests and the loader; None clears it."""
    _SPOT.clear()
    _CACHE.clear()
    if df is not None:
        _SPOT["df"] = df


def spot_path() -> Path | None:
    for f in SPOT_FILES:
        if Path(f).exists():
            return Path(f)
    return None


def spot_1m() -> pd.DataFrame | None:
    if "df" in _SPOT:
        return _SPOT["df"]
    f = spot_path()
    if f is None:
        _SPOT["df"] = None
        return None
    raw = pd.read_csv(f)
    ts = pd.to_datetime(raw.iloc[:, 0], utc=False)
    if ts.dt.tz is None:
        ts = ts.dt.tz_localize(NY, ambiguous="NaT", nonexistent="shift_forward")
    else:
        ts = ts.dt.tz_convert(NY)
    col = "close" if "close" in raw.columns else raw.columns[1]
    out = pd.DataFrame({"close": raw[col].astype(float).values}, index=pd.DatetimeIndex(ts))
    out = out[out.index.notna()]
    out = out[~out.index.duplicated(keep="last")].sort_index()
    _SPOT["df"] = out
    return out


def _from_closes(c: pd.Series, tf: int) -> pd.DataFrame:
    g = c.groupby(c.index.floor(f"{tf}min"))
    b = pd.DataFrame({"close": g.last(), "hi_c": g.max(), "lo_c": g.min()})
    prev_end = b.index.to_series().shift(1) + pd.Timedelta(minutes=tf)
    cont = (b.index.to_series() == prev_end)                      # open = the previous bar's close only inside a continuous run; after a break (17:00-18:00, weekends, holes) the first close
    b["open"] = b.close.shift(1).where(cont, g.first())
    b["high"] = np.maximum(b.hi_c, b.open)
    b["low"] = np.minimum(b.lo_c, b.open)
    return b[["open", "high", "low", "close"]]


def _drop_bad(b: pd.DataFrame, tf: int) -> pd.DataFrame:
    if not len(b):
        return b
    bad = pd.DatetimeIndex(BAD_HOURS)
    hour = b.index.floor("60min")
    return b[~hour.isin(bad)]


def bars(tf: int, src: str = "auto") -> pd.DataFrame | None:
    """DXY OHLC bars of `tf` minutes (1 / 5 / 15 / 60 / 240 ...), indexed by bar start, with `end` = start + tf. src: "spot" (needs the spot file), "dx" (Databento DX 1h resampled; tf >= 60),
    "auto" = spot when available and the bar is inside its 2019-2025 range, else dx for tf >= 60, else None. None when nothing covers it."""
    key = (tf, src, "df" in _SPOT, id(_SPOT.get("df")))
    if key in _CACHE:
        return _CACHE[key]
    out = None
    s = spot_1m() if src in ("auto", "spot") else None
    if s is not None and len(s) and tf >= 1:
        out = _drop_bad(_from_closes(s.close, tf), tf)
    if src in ("auto", "dx") and tf >= 60:
        from . import databento_extra as DE
        h = DE.dx_hourly()
        if h is not None and len(h):
            d = h[["open", "high", "low", "close"]]
            if tf > 60:
                g = d.groupby(d.index.floor(f"{tf}min"))
                d = pd.DataFrame({"open": g.open.first(), "high": g.high.max(), "low": g.low.min(), "close": g.close.last()})
            out = d if out is None else _merge(out, d)
    if out is not None:
        out = out.copy()
        out["end"] = out.index + pd.Timedelta(minutes=tf)
    _CACHE[key] = out
    return out


def _merge(spot_b: pd.DataFrame, dx_b: pd.DataFrame) -> pd.DataFrame:
    """Spot bars where they exist, DX bars after the spot range (2026): levels of the two series are never mixed inside one comparison by the callers (spec 0.3); this only extends the frame in time."""
    return pd.concat([spot_b, dx_b[dx_b.index > spot_b.index[-1]]]).sort_index()


def closed(b: pd.DataFrame | None, t: pd.Timestamp) -> pd.DataFrame | None:
    """The rows whose bar has closed at or before `t`."""
    if b is None:
        return None
    n = int(b.end.searchsorted(t, side="right"))
    return b.iloc[:n]


def session_label(idx: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """The trading date of a bar start: the 18:00 reopen belongs to the NEXT calendar date (a session is 18:00-17:00 NY), as the daily bars of the spec (0.3, `session_date`)."""
    return (idx + pd.Timedelta(hours=6)).normalize().tz_localize(None)


def daily(src: str = "dx") -> pd.DataFrame | None:
    """DXY daily bars (session 18:00-17:00 NY) from the 1h bars of `src` ("dx" Databento DX 1h / "spot" the spot file), indexed by the naive session date, with `end` = 17:00 NY of that date.
    One series per call: the levels of a comparison are never mixed across sources (spec 0.3)."""
    key = ("daily", src, "df" in _SPOT, id(_SPOT.get("df")))
    if key in _CACHE:
        return _CACHE[key]
    h = bars(60, src)
    out = None
    if h is not None and len(h):
        g = h.groupby(session_label(h.index))
        out = pd.DataFrame({"open": g.open.first(), "high": g.high.max(), "low": g.low.min(), "close": g.close.last()})
        out["end"] = [pd.Timestamp(d, tz=NY) + pd.Timedelta(hours=17) for d in out.index]
    _CACHE[key] = out
    return out
