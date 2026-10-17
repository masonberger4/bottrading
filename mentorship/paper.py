"""Paper mode: run the model on live Schwab bars as they close and log what it would do.
It never sends an order; there is no order code in this package."""
from __future__ import annotations

import csv
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

from . import backtest as B
from .strategy import Params, run_day


def snapshot(c, symbol: str, partner: str | None, minutes: int, p: Params):
    """Today's trades and armed setups from the bars closed so far."""
    from silver_bullet.data import schwab_history
    days = 8 if minutes == 1 else 30
    df = schwab_history(c, symbol, days=days, minutes=minutes)
    now = pd.Timestamp.now(tz=B.NY)
    df = df[df.index + pd.Timedelta(minutes=minutes) <= now]          # closed bars only
    ds = B.days(df, minutes, partial_last=True)
    if len(ds) < 4 or ds[-1].index[0].date() != now.date():
        return [], []
    pa = None
    if partner:
        q = schwab_history(c, partner, days=days, minutes=minutes)
        q = q[q.index + pd.Timedelta(minutes=minutes) <= now]
        qs = B.days(q, minutes, partial_last=True)
        if qs and qs[-1].index[0].date() == now.date():
            pa = (qs[-1], [B.rth(x) for x in qs[:-1]][-21:])
    log: list = []
    trades = run_day(ds[-1], [B.rth(x) for x in ds[:-1]][-21:], symbol, p, minutes, pa, log, live=True)
    return trades, log


def run(symbol="SPY", partner="QQQ", minutes=1, p: Params | None = None, out="runs/mentorship"):
    from claude_hf.data import client
    p = p or Params()
    c = client()
    Path(out).mkdir(parents=True, exist_ok=True)
    seen_arm, seen_tr = set(), {}
    path = Path(out) / f"paper_{symbol}_{datetime.now():%Y%m%d}.csv"
    print(f"paper mode {symbol} {minutes}m (partner {partner}); simulated only, logging to {path}")
    while True:
        now = pd.Timestamp.now(tz=B.NY)
        if now.hour * 60 + now.minute > 16 * 60 + 5:
            print("session over"); break
        try:
            trades, log = snapshot(c, symbol, partner, minutes, p)
        except Exception as e:                        # keep going through API hiccups
            print(f"{now:%H:%M:%S} fetch failed: {e}"); trades, log = [], []
        for ev in log:
            if ev not in seen_arm:
                seen_arm.add(ev)
                print(f"{ev[0]:%H:%M} ARMED {ev[2]} {ev[3]} after {ev[4]} sweep: limit {ev[5]:.2f} "
                      f"stop {ev[6]:.2f} t1 {ev[7]:.2f}")
        for tr in trades:
            r = tr.row(p.cost_per_share)
            key = (r["entry_time"], r["exit_reason"])
            if seen_tr.get(r["entry_time"]) != key:
                seen_tr[r["entry_time"]] = key
                print(f"{now:%H:%M} {r['side']} {r['shares']} @ {r['entry']:.2f} -> {r['exit_reason']} "
                      f"net {r['net']:+.2f}")
                new = not path.exists()
                with path.open("a", newline="") as f:
                    w = csv.DictWriter(f, fieldnames=list(r))
                    if new:
                        w.writeheader()
                    w.writerow(r)
        wait = minutes * 60 - (time.time() % (minutes * 60)) + 5    # just after the next close
        time.sleep(wait)
