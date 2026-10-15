"""Historical minute bars from Alpaca's market data API (free account works).

Set ALPACA_API_KEY_ID and ALPACA_API_SECRET_KEY (environment or the Windows user
registry via setx). Read-only: this only calls the market data endpoint.

    python -m mentorship2023.alpaca_data --start 2019-01-01
"""
from __future__ import annotations

import argparse
import time

import pandas as pd
import requests

from claude_hf.data import _env
from .backtest import DATA, NY

URL = "https://data.alpaca.markets/v2/stocks/{}/bars"


def bars(symbol: str, minutes: int, start: str, end: str | None = None, feed: str = "sip") -> pd.DataFrame:
    key, secret = _env("ALPACA_API_KEY_ID"), _env("ALPACA_API_SECRET_KEY")
    if not (key and secret):
        raise SystemExit("Set ALPACA_API_KEY_ID and ALPACA_API_SECRET_KEY first.")
    hdr = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
    end = end or (pd.Timestamp.now(tz="UTC") - pd.Timedelta(minutes=20)).isoformat()  # free tier: no last 15 min
    q = {"timeframe": f"{minutes}Min", "start": pd.Timestamp(start, tz=NY).isoformat(), "end": end,
         "limit": 10000, "adjustment": "split", "feed": feed}
    rows = []
    while True:
        r = requests.get(URL.format(symbol), headers=hdr, params=q, timeout=60)
        if r.status_code == 429:
            time.sleep(5); continue
        r.raise_for_status()
        j = r.json()
        rows += j.get("bars") or []
        if not j.get("next_page_token"):
            break
        q["page_token"] = j["next_page_token"]
        time.sleep(0.35)                     # stay under 200 requests/minute
    df = pd.DataFrame(rows).rename(columns={"t": "datetime", "o": "open", "h": "high", "l": "low",
                                            "c": "close", "v": "volume"})
    df.index = pd.to_datetime(df.pop("datetime"), utc=True).tz_convert(NY)
    return df[["open", "high", "low", "close", "volume"]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2019-01-01")
    ap.add_argument("--symbols", default="SPY,QQQ")
    ap.add_argument("--minutes", default="1,5")
    ap.add_argument("--feed", default="sip", help="sip (all exchanges) or iex")
    a = ap.parse_args()
    DATA.mkdir(parents=True, exist_ok=True)
    for m in map(int, a.minutes.split(",")):
        for s in a.symbols.split(","):
            df = bars(s, m, a.start, feed=a.feed)
            df.to_csv(DATA / f"{s}_{m}min_alpaca.csv")
            print(s, m, len(df), df.index[0], df.index[-1])


if __name__ == "__main__":
    main()
