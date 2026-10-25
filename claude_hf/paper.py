"""Forward paper trading of the champion genome on live Schwab bars, with simulated fills.

At each bar close it pulls today's bars for every stock, rebuilds the signals exactly as the
backtest does, and, on the champion's decision bars, opens simulated positions at the next
bar's open and closes them at the close `hold` minutes later. No orders are ever sent: this
module has no live mode.
"""
from __future__ import annotations

import csv
import json
import logging
import time as _time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

from silver_bullet.data import schwab_history

from . import data, features
from . import strategy as S

NY = ZoneInfo("America/New_York")
log = logging.getLogger("claude_hf")


def snapshot(c, symbols, minutes: int) -> features.Features:
    frames = {}
    for s in symbols:
        try:
            frames[s] = data.regular_session(
                schwab_history(c, s, days=4, minutes=minutes, extended_hours=False))
        except Exception as e:
            log.warning("%s: %s", s, e)
    return features.build(data.to_panel(frames, minutes, min_frac=0))


def run(champion_path: str = "claude_hf/champion.json",
        journal_path: str = "runs/claude_hf/paper_trades.csv", cost_bps: float = 1.5):
    champ = json.load(open(champion_path))
    g, bm = champ["genome"], champ["bar_minutes"]
    c = data.client()
    Path(journal_path).parent.mkdir(parents=True, exist_ok=True)
    journal = open(journal_path, "a", newline="")
    jw = csv.writer(journal)
    if journal.tell() == 0:
        jw.writerow(["symbol", "side", "signal_ts", "entry_ts", "entry_px", "exit_ts", "exit_px",
                     "gross_bps", "net_bps"])
    log.info("Claude HF paper trading (simulated fills, no orders sent): %s",
             S.describe(g, bm))
    open_trades: list[dict] = []     # waiting for entry or exit bars
    decided: set = set()
    cost = 2 * cost_bps + S.SEC_FEE_BPS
    while True:
        now = datetime.now(NY)
        if now.weekday() >= 5 or not (9 * 60 + 30 <= now.hour * 60 + now.minute < 16 * 60 + 5):
            _time.sleep(60)
            continue
        f = snapshot(c, data.UNIVERSE, bm)
        today = f.day.max()
        base = today * f.bars_per_day
        closed = [b for b in range(f.bars_per_day)
                  if f.index[base + b] + timedelta(minutes=bm) <= now]
        if f.index[base].date() != now.date() or not closed:
            _time.sleep(20)
            continue
        last = closed[-1]
        kind = f.day_type[today]
        pb = S.route(g, kind)
        if pb != getattr(run, "_announced", None):
            run._announced = pb
            log.info("today is a %s day: %s", kind,
                     "sitting out" if pb == "skip" else f"trading playbook {pb}")
        # fill entries and exits whose bars have now closed
        for t in list(open_trades):
            if t["symbol"] not in f.symbols:      # that stock's fetch failed this round
                continue
            t["col"] = f.symbols.index(t["symbol"])
            if t["entry_px"] is None and t["bar"] + 1 <= last:
                t["entry_px"] = float(f.open[base + t["bar"] + 1, t["col"]])
                t["entry_ts"] = f.index[base + t["bar"] + 1]
            if t["entry_px"] is not None and t["bar"] + t["hold"] <= last:
                px = float(f.close[base + t["bar"] + t["hold"], t["col"]])
                gross = t["side"] * np.log(px / t["entry_px"]) * 1e4
                jw.writerow([t["symbol"], "long" if t["side"] > 0 else "short", t["signal_ts"],
                             t["entry_ts"], round(t["entry_px"], 4), f.index[base + t["bar"] + t["hold"]],
                             round(px, 4), round(gross, 2), round(gross - cost, 2)])
                journal.flush()
                log.info("closed %s %s: %+.1f bps net", t["symbol"],
                         "long" if t["side"] > 0 else "short", gross - cost)
                open_trades.remove(t)
        # new decisions
        key = (now.date(), last)
        b = S.playbook(g, pb) if pb != "skip" else None
        if b and last in set(S.decision_bars(b, f)) and key not in decided:
            decided.add(key)
            hold = S.hold_bars(b, bm)
            row = np.array([base + last])
            pos = S.select(b, S.score(b, f, row))[0]
            for col in np.flatnonzero(pos):
                open_trades.append({"symbol": f.symbols[col], "side": int(pos[col]),
                                    "bar": last, "hold": hold, "signal_ts": f.index[base + last],
                                    "entry_px": None, "entry_ts": None})
                log.info("%s signal: %s %s, enter next bar open, exit after %d min",
                         f.index[base + last], "BUY" if pos[col] > 0 else "SHORT",
                         f.symbols[col], hold * bm)
        # wake just after the next bar closes
        nxt = f.index[base + last] + timedelta(minutes=2 * bm)
        _time.sleep(max(5, (nxt - datetime.now(NY)).total_seconds() + 3))
