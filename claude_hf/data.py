"""Minute bars for the stock universe, pulled from Schwab and cached under data/claude_hf/.

Reuses silver_bullet's Schwab auth and price-history code. Bars are kept for the regular
session only (09:30-16:00 New York) and aligned into wide frames: one column per symbol.
"""
from __future__ import annotations

import os
import time
from pathlib import Path

import numpy as np
import pandas as pd

from silver_bullet.data import schwab_history
from silver_bullet.schwab_broker import make_client

# Liquid large-cap US stocks with penny-wide spreads. Stocks only: no ETFs.
UNIVERSE = (
    "AAPL MSFT NVDA AMZN META GOOGL TSLA AMD AVGO NFLX ORCL CRM ADBE QCOM MU INTC CSCO PLTR "
    "JPM BAC GS C WFC V MA XOM CVX WMT COST HD KO PEP UNH LLY PFE MRK DIS NKE BA UBER"
).split()

CACHE = Path("data/claude_hf")


def _env(name: str) -> str | None:
    """Environment variable, falling back to the Windows user registry (where setx writes)
    so a shell opened before setx still finds the Schwab keys."""
    v = os.environ.get(name)
    if v or os.name != "nt":
        return v
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            return winreg.QueryValueEx(k, name)[0]
    except OSError:
        return None


def client():
    key, secret = _env("SCHWAB_APP_KEY"), _env("SCHWAB_APP_SECRET")
    if not (key and secret):
        raise SystemExit("Set SCHWAB_APP_KEY and SCHWAB_APP_SECRET (from developer.schwab.com).")
    return make_client(key, secret, _env("SCHWAB_CALLBACK_URL") or "https://127.0.0.1:8182",
                       _env("SCHWAB_TOKEN_PATH") or "schwab_token.json")


def regular_session(df: pd.DataFrame) -> pd.DataFrame:
    t = df.index.hour * 60 + df.index.minute
    return df[(t >= 570) & (t < 960)]


def cache_dir(minutes: int) -> Path:
    return CACHE / f"{minutes}min"


def fetch(symbols=UNIVERSE, minutes: int = 1, days: int | None = None, c=None) -> None:
    """Download bars for each symbol into data/claude_hf/<N>min/<SYM>.csv (regular session).
    Schwab keeps about 48 days of 1-minute bars and about 9 months of 5-minute bars."""
    c = c or client()
    days = days or (48 if minutes == 1 else 270)
    out = cache_dir(minutes)
    out.mkdir(parents=True, exist_ok=True)
    for i, s in enumerate(symbols):
        try:
            df = regular_session(schwab_history(c, s, days=days, minutes=minutes, extended_hours=False))
            df.to_csv(out / f"{s}.csv")
            print(f"[{i + 1}/{len(symbols)}] {s}: {len(df)} bars, "
                  f"{df.index[0].date()} -> {df.index[-1].date()}")
        except Exception as e:  # one bad symbol shouldn't stop the pull
            print(f"[{i + 1}/{len(symbols)}] {s}: FAILED {e}")
        time.sleep(0.6 * days / 10)   # Schwab allows ~120 calls/min; one call per 10 days


def to_panel(frames: dict[str, pd.DataFrame], minutes: int = 1,
             min_frac: float = 0.95) -> dict[str, pd.DataFrame]:
    """Wide frames (index = bar time, columns = symbols) for open/high/low/close/volume on a
    full regular-session grid per day. Days where any symbol has fewer than `min_frac` of the
    session's bars are dropped (pass 0 for a live, still-running day); gaps inside a day are
    forward-filled."""
    per_day = 390 // minutes
    panel = {k: pd.DataFrame({s: d[k] for s, d in frames.items()})
             for k in ("open", "high", "low", "close", "volume")}
    idx = panel["close"].index
    counts = panel["close"].notna().groupby(idx.date).sum()
    good = counts.index[(counts >= max(min_frac * per_day, 1)).all(axis=1)]
    grid = pd.DatetimeIndex(np.concatenate([
        pd.date_range(pd.Timestamp(d, tz="America/New_York") + pd.Timedelta(minutes=570),
                      periods=per_day, freq=f"{minutes}min") for d in good]))
    out = {}
    for k, v in panel.items():
        v = v.reindex(grid)
        if k == "volume":
            v = v.fillna(0.0)
        else:
            v = v.groupby(v.index.date).transform(lambda x: x.ffill().bfill())
        out[k] = v
    return out


def load_frames(path: Path, symbols=None) -> dict[str, pd.DataFrame]:
    files = sorted(Path(path).glob("*.csv"))
    if symbols:
        files = [f for f in files if f.stem in set(symbols)]
    if not files:
        raise SystemExit(f"No cached bars in {path}. Run: python -m claude_hf fetch")
    frames = {}
    for f in files:
        df = pd.read_csv(f, index_col=0)
        df.index = pd.to_datetime(df.index, utc=True).tz_convert("America/New_York")
        frames[f.stem] = df
    return frames


def load_panel(minutes: int = 1, symbols=None) -> dict[str, pd.DataFrame]:
    return to_panel(load_frames(cache_dir(minutes), symbols), minutes)
