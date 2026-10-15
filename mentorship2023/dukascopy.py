"""Free 1-minute index CFD bars from Dukascopy's public datafeed (no account needed).

USA500.IDX/USD (S&P 500) and USATECH.IDX/USD (Nasdaq 100) trade nearly around the clock,
so unlike SPY they have a real 00:00 New York midnight open and an overnight session.
Prices are index points, so ICT's ES/NQ handles apply directly.

Files: https://datafeed.dukascopy.com/datafeed/<SYM>/<YYYY>/<MM-1>/<DD>/<BID|ASK>_candles_min_1.bi5
— one per UTC day, LZMA-compressed, 1440 big-endian records of
(seconds from 00:00 UTC, open, close, low, high as int / 1000, volume as float32).
Minutes with no trading repeat the last price with zero volume and are dropped.
Market data only.

    python -m mentorship2023.dukascopy --start 2019-01-01
"""
from __future__ import annotations

import argparse
import lzma
import struct
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from .backtest import DATA, NY

SYMBOLS = {"SPX": "USA500IDXUSD", "NDX": "USATECHIDXUSD"}
URL = "https://datafeed.dukascopy.com/datafeed/{}/{:04d}/{:02d}/{:02d}/{}_candles_min_1.bi5"
RAW = DATA / "dukascopy"
REC = struct.Struct(">IIIIIf")


def _get(sym: str, d: date, side: str, session: requests.Session) -> Path | None:
    path = RAW / sym / f"{d:%Y%m%d}_{side}.bi5"
    if path.exists():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    url = URL.format(sym, d.year, d.month - 1, d.day, side)
    for k in range(6):
        try:
            r = session.get(url, timeout=30)
        except requests.RequestException:
            time.sleep(2 ** k); continue
        if r.status_code == 200:
            path.write_bytes(r.content)
            return path
        if r.status_code == 404:
            path.write_bytes(b"")        # no file for that day (holiday / weekend)
            return path
        time.sleep(2 ** k)               # 429 or 5xx: back off
    return None


def download(start: str, end: str | None = None, workers: int = 4) -> None:
    d0 = date.fromisoformat(start)
    d1 = date.fromisoformat(end) if end else date.today() - timedelta(days=1)
    days = [d0 + timedelta(days=k) for k in range((d1 - d0).days + 1)]
    days = [d for d in days if d.weekday() != 5]        # nothing trades on Saturday (UTC)
    jobs = [(s, d, side) for s in SYMBOLS.values() for d in days for side in ("BID", "ASK")]
    s = requests.Session()
    s.headers["User-Agent"] = "Mozilla/5.0 (research backtest)"
    missing = 0
    with ThreadPoolExecutor(workers) as ex:
        for k, p in enumerate(ex.map(lambda j: _get(*j, s), jobs)):
            missing += p is None
            if k % 500 == 0:
                print(f"{k}/{len(jobs)} files, {missing} failed", flush=True)
    print(f"done: {len(jobs)} files, {missing} failed")


def _decode(path: Path, d: date) -> pd.DataFrame | None:
    raw = path.read_bytes() if path.exists() else b""
    if not raw:
        return None
    b = lzma.decompress(raw)
    a = np.array(list(REC.iter_unpack(b)), dtype=float)
    if not len(a):
        return None
    idx = pd.Timestamp(d, tz="UTC") + pd.to_timedelta(a[:, 0], unit="s")
    return pd.DataFrame({"open": a[:, 1] / 1000, "high": a[:, 4] / 1000, "low": a[:, 3] / 1000,
                         "close": a[:, 2] / 1000, "volume": a[:, 5]}, index=idx)


def build(name: str, start: str = "2019-01-01") -> pd.DataFrame:
    """Bid/ask midpoint 1-minute bars in New York time, zero-volume minutes dropped.
    Writes <name>_1min_duka.csv and <name>_5min_duka.csv."""
    sym = SYMBOLS[name]
    frames = []
    for p in sorted((RAW / sym).glob("*_BID.bi5")):
        d = date(int(p.name[:4]), int(p.name[4:6]), int(p.name[6:8]))
        if d < date.fromisoformat(start):
            continue
        bid, ask = _decode(p, d), _decode(p.with_name(p.name.replace("BID", "ASK")), d)
        if bid is None:
            continue
        if ask is not None and len(ask) == len(bid):
            m = (bid[["open", "high", "low", "close"]] + ask[["open", "high", "low", "close"]]) / 2
            m["volume"] = bid.volume + ask.volume
        else:
            m = bid
        frames.append(m[m.volume > 0])
    df = pd.concat(frames)
    df.index = df.index.tz_convert(NY)
    df = df[~df.index.duplicated()].sort_index()
    df.round(3).to_csv(DATA / f"{name}_1min_duka.csv")
    g = df.groupby(df.index.floor("5min"))
    five = pd.DataFrame({"open": g.open.first(), "high": g.high.max(), "low": g.low.min(),
                         "close": g.close.last(), "volume": g.volume.sum()})
    five.round(3).to_csv(DATA / f"{name}_5min_duka.csv")
    print(name, len(df), "1-min bars", df.index[0], "->", df.index[-1])
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2019-01-01")
    ap.add_argument("--end", default=None)
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    download(a.start, a.end, a.workers)
    for n in SYMBOLS:
        build(n, a.start)


if __name__ == "__main__":
    main()
