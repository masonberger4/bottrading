"""Free 1-minute S&P 500 and Nasdaq 100 index CFD bars from HistData.com (no account).

SPXUSD / NSXUSD trade nearly around the clock (Sunday-Friday 18:00-17:00 New York), so
unlike SPY they have a real 00:00 midnight open and an overnight session, and their
prices are index points (ICT's ES/NQ handles apply directly). Timestamps are New York
local time (see _parse).
Prices are bid quotes; volume is always 0. Files come one zip per past year and one per
month for the current year. Market data only.

    python -m mentorship2023.histdata --start 2019
"""
from __future__ import annotations

import argparse
import io
import re
import time
import zipfile
from datetime import date
from pathlib import Path

import pandas as pd
import requests

from .backtest import DATA, NY

PAIRS = {"SPX": "spxusd", "NDX": "nsxusd"}
PAGE = "https://www.histdata.com/download-free-forex-historical-data/?/ascii/1-minute-bar-quotes/{}/{}"
GET = "https://www.histdata.com/get.php"
RAW = DATA / "histdata"


def _download(pair: str, year: int, month: int | None, s: requests.Session) -> Path | None:
    tag = f"{year}" if month is None else f"{year}{month:02d}"
    path = RAW / f"{pair}_{tag}.zip"
    if path.exists() and path.stat().st_size > 1000:
        return path
    page = PAGE.format(pair, year if month is None else f"{year}/{month}")
    r = s.get(page, timeout=60)
    m = re.search(r'name="tk" id="tk" value="([^"]+)"', r.text)
    if not m:
        return None
    form = {"tk": m.group(1), "date": str(year), "datemonth": tag, "platform": "ASCII",
            "timeframe": "M1", "fxpair": pair.upper()}
    z = s.post(GET, data=form, headers={"Referer": page}, timeout=120)
    if z.status_code != 200 or not z.content.startswith(b"PK"):
        return None
    RAW.mkdir(parents=True, exist_ok=True)
    path.write_bytes(z.content)
    return path


def download(start: int = 2019) -> list[Path]:
    s = requests.Session()
    s.headers["User-Agent"] = "Mozilla/5.0 (research backtest)"
    today = date.today()
    out = []
    for pair in PAIRS.values():
        for y in range(start, today.year + 1):
            months = [None] if y < today.year else range(1, today.month + 1)
            for m in months:
                p = _download(pair, y, m, s)
                print(pair, y, m or "", "ok" if p else "missing", flush=True)
                if p:
                    out.append(p)
                time.sleep(1.5)
    return out


def _parse(path: Path) -> pd.DataFrame:
    with zipfile.ZipFile(path) as z:
        name = next(n for n in z.namelist() if n.endswith(".csv"))
        df = pd.read_csv(io.BytesIO(z.read(name)), sep=";", header=None,
                         names=["ts", "open", "high", "low", "close", "volume"])
    # HistData documents EST without daylight saving, but checked against Schwab SPY bars
    # (Feb and Aug 2026) and the daily 16:15-18:00 break (same clock hours in winter and
    # summer, 2019-2026) the stamps are New York local time, daylight saving included.
    idx = pd.to_datetime(df.pop("ts"), format="%Y%m%d %H%M%S").dt.tz_localize(
        NY, ambiguous="NaT", nonexistent="NaT")
    df.index = pd.DatetimeIndex(idx)
    return df[df.index.notna()]


def build(name: str, start: int = 2019) -> pd.DataFrame:
    """Writes <name>_1min_hd.csv and <name>_5min_hd.csv (New York time)."""
    pair = PAIRS[name]
    files = sorted(p for p in RAW.glob(f"{pair}_*.zip") if int(p.stem.split("_")[1][:4]) >= start)
    df = pd.concat([_parse(p) for p in files])
    df = df[~df.index.duplicated()].sort_index()
    df.to_csv(DATA / f"{name}_1min_hd.csv")
    g = df.groupby(df.index.floor("5min"))
    five = pd.DataFrame({"open": g.open.first(), "high": g.high.max(), "low": g.low.min(),
                         "close": g.close.last(), "volume": g.volume.sum()})
    five.to_csv(DATA / f"{name}_5min_hd.csv")
    print(name, len(df), "1-min bars", df.index[0], "->", df.index[-1])
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=2019)
    a = ap.parse_args()
    download(a.start)
    for n in PAIRS:
        build(n, a.start)


if __name__ == "__main__":
    main()
