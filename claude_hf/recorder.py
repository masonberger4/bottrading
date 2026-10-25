"""Record Schwab's live quote and order-book stream so later research has data Schwab
doesn't keep: top-of-book quotes (Level 1) and the top levels of the Nasdaq/NYSE books
(Level 2). Market data only; this module places no orders.

Files go to data/claude_hf/stream/<date>/ as gzipped CSV:
  l1.csv.gz    one row per quote/trade update: bid/ask/sizes/last/volume
  book.csv.gz  at most one row per stock per second: top BOOK_LEVELS bid and ask levels
"""
from __future__ import annotations

import asyncio
import csv
import gzip
import logging
import time as _time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from . import data
from .daytypes import is_trading_day

NY = ZoneInfo("America/New_York")
ROOT = Path("data/claude_hf/stream")
BOOK_LEVELS = 5
L1_COLS = ["BID_PRICE", "ASK_PRICE", "BID_SIZE", "ASK_SIZE", "LAST_PRICE", "LAST_SIZE",
           "TOTAL_VOLUME"]
log = logging.getLogger("claude_hf")


class DayFiles:
    def __init__(self, day):
        d = ROOT / day.isoformat()
        d.mkdir(parents=True, exist_ok=True)
        self.l1f = gzip.open(d / "l1.csv.gz", "at", newline="")
        self.bookf = gzip.open(d / "book.csv.gz", "at", newline="")
        self.l1, self.book = csv.writer(self.l1f), csv.writer(self.bookf)
        if self.l1f.tell() == 0:
            self.l1.writerow(["ts_ms", "symbol", *[c.lower() for c in L1_COLS]])
        if self.bookf.tell() == 0:
            self.book.writerow(["ts_ms", "symbol", "venue", *[
                f"{side}{i}_{x}" for side in ("bid", "ask") for i in range(BOOK_LEVELS)
                for x in ("px", "sz", "n")]])

    def close(self):
        self.l1f.close()
        self.bookf.close()


class Recorder:
    def __init__(self, symbols=data.UNIVERSE):
        self.symbols = list(symbols)
        self.state: dict[str, dict] = {s: {} for s in self.symbols}   # last Level 1 values
        self.last_book: dict[tuple, int] = {}
        self.files: DayFiles | None = None
        self.counts = {"l1": 0, "book": 0}

    def on_l1(self, msg):
        ts = msg.get("timestamp", int(_time.time() * 1000))
        for q in msg.get("content", []):
            s = q.get("key")
            st = self.state.setdefault(s, {})
            st.update({k: q[k] for k in L1_COLS if k in q})        # updates carry changed fields
            self.files.l1.writerow([ts, s, *[st.get(k, "") for k in L1_COLS]])
            self.counts["l1"] += 1

    def on_book(self, msg):
        ts = msg.get("timestamp", int(_time.time() * 1000))
        venue = msg.get("service", "")
        for b in msg.get("content", []):
            s = b.get("key")
            k = (s, venue)
            if ts - self.last_book.get(k, 0) < 1000:                 # one snapshot/sec/stock
                continue
            self.last_book[k] = ts
            row = [ts, s, venue]
            for side, price_key in (("BIDS", "BID_PRICE"), ("ASKS", "ASK_PRICE")):
                levels = b.get(side) or []
                for i in range(BOOK_LEVELS):
                    if i < len(levels):
                        lv = levels[i]
                        row += [lv.get(price_key, ""), lv.get("TOTAL_VOLUME", ""),
                                lv.get("NUM_BIDS", lv.get("NUM_ASKS", ""))]
                    else:
                        row += ["", "", ""]
            self.files.book.writerow(row)
            self.counts["book"] += 1

    async def session(self, client, until: datetime):
        from schwab.streaming import StreamClient
        sc = StreamClient(client)
        await sc.login()
        sc.add_level_one_equity_handler(self.on_l1)
        sc.add_nasdaq_book_handler(self.on_book)
        sc.add_nyse_book_handler(self.on_book)
        f = StreamClient.LevelOneEquityFields
        await sc.level_one_equity_subs(self.symbols, fields=[
            f.SYMBOL, *[getattr(f, c) for c in L1_COLS]])
        await sc.nasdaq_book_subs(self.symbols)
        await sc.nyse_book_subs(self.symbols)
        log.info("recording %d stocks until %s", len(self.symbols), until.strftime("%H:%M"))
        last_flush = _time.time()
        try:
            while datetime.now(NY) < until:
                await asyncio.wait_for(sc.handle_message(), timeout=60)
                if _time.time() - last_flush > 30:
                    self.files.l1f.flush()
                    self.files.bookf.flush()
                    last_flush = _time.time()
                    log.info("%s  l1 %d rows, book %d rows", datetime.now(NY).strftime("%H:%M:%S"),
                             self.counts["l1"], self.counts["book"])
        finally:
            await sc.logout()

    def run_day(self, client, until: datetime):
        self.files = DayFiles(datetime.now(NY).date())
        try:
            while datetime.now(NY) < until:
                try:
                    asyncio.run(self.session(client, until))
                except Exception as e:                                # drop, then reconnect
                    log.warning("stream error: %r; reconnecting in 10s", e)
                    _time.sleep(10)
        finally:
            self.files.close()


def run(symbols=data.UNIVERSE, days: int | None = None):
    """Record every trading day from 09:25 to 16:05 New York time. `days` limits how many."""
    c = data.client()
    rec, done = Recorder(symbols), 0
    while days is None or done < days:
        now = datetime.now(NY)
        start = now.replace(hour=9, minute=25, second=0, microsecond=0)
        end = now.replace(hour=16, minute=5, second=0, microsecond=0)
        if is_trading_day(now.date()) and start <= now < end:
            rec.run_day(c, end)
            done += 1
            continue
        nxt = start if now < start else start + timedelta(days=1)
        while not is_trading_day(nxt.date()):
            nxt += timedelta(days=1)
        log.info("next session %s", nxt.strftime("%a %Y-%m-%d %H:%M"))
        _time.sleep(max(30, (nxt - datetime.now(NY)).total_seconds()))
