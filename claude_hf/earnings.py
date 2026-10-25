"""Earnings dates for the universe, from Nasdaq's public earnings calendar.

What matters for intraday trading is the *reaction day*: the report day itself for a
before-the-open report, the next trading day for an after-the-close one. Nasdaq often omits
the time for past reports, so each company's usual timing fills the gap (these companies
have reported at the same time of day for years).
"""
from __future__ import annotations

import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from .daytypes import _step, is_trading_day

PATH = Path("data/claude_hf/earnings.csv")
URL = "https://api.nasdaq.com/api/calendar/earnings"
AFTER_CLOSE = set("AAPL MSFT NVDA AMZN META GOOGL TSLA AMD AVGO NFLX ORCL CRM ADBE QCOM MU "
                  "INTC CSCO PLTR V NKE COST".split())   # everyone else reports before the open


def fetch(symbols, start: date, end: date) -> pd.DataFrame:
    import httpx
    want, rows = set(symbols), []
    d = start
    with httpx.Client(headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
                      timeout=20) as c:
        while d <= end:
            if is_trading_day(d):
                for attempt in range(3):
                    try:
                        j = c.get(URL, params={"date": d.isoformat()}).json()
                        break
                    except Exception:
                        time.sleep(2 * (attempt + 1))
                else:
                    raise RuntimeError(f"Nasdaq earnings calendar failed for {d}")
                for r in (j.get("data") or {}).get("rows") or []:
                    if r["symbol"] in want:
                        t = r.get("time", "")
                        when = ("amc" if "after" in t else "bmo" if "pre" in t
                                else "amc" if r["symbol"] in AFTER_CLOSE else "bmo")
                        rows.append({"symbol": r["symbol"], "report_date": d, "when": when})
                time.sleep(0.3)
            d += timedelta(days=1)
    df = pd.DataFrame(rows, columns=["symbol", "report_date", "when"])
    df["reaction_date"] = [rd if w == "bmo" else _step(rd, 1)
                           for rd, w in zip(df.report_date, df.when)]
    PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(PATH, index=False)
    return df


def reaction_days() -> set:
    """{(symbol, date)} for every earnings reaction day on file."""
    if not PATH.exists():
        return set()
    df = pd.read_csv(PATH, parse_dates=["reaction_date"])
    return {(s, d.date()) for s, d in zip(df.symbol, df.reaction_date)}
