"""Command line.

  python -m silver_bullet backtest --synthetic --symbol MES
  python -m silver_bullet backtest --csv mes_1min.csv --symbol MES
  python -m silver_bullet backtest --schwab --symbol SPY --days 45
  python -m silver_bullet paper --symbol SPY            # live Schwab data, simulated fills
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import time as _time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from . import backtest, data
from .config import INSTRUMENTS, params_for
from .execution import PaperBroker, step
from .strategy import NY, Strategy

log = logging.getLogger("silver_bullet")


def _client():
    from .schwab_broker import make_client
    try:
        key, secret = os.environ["SCHWAB_APP_KEY"], os.environ["SCHWAB_APP_SECRET"]
    except KeyError:
        raise SystemExit("Set SCHWAB_APP_KEY and SCHWAB_APP_SECRET (from developer.schwab.com).")
    return make_client(key, secret, os.environ.get("SCHWAB_CALLBACK_URL", "https://127.0.0.1:8182"),
                       os.environ.get("SCHWAB_TOKEN_PATH", "schwab_token.json"))


def _params(a):
    over = {}
    if a.target_mode:
        over["target_mode"] = a.target_mode
    if a.windows:
        over["windows"] = tuple(a.windows.split(","))
    if a.bias:
        over["bias"] = a.bias
    return params_for(a.symbol, **over)


def cmd_backtest(a):
    inst = INSTRUMENTS[a.symbol]
    if a.synthetic:
        df = data.synthetic(days=a.days)
    elif a.csv:
        df = data.load_csv(a.csv, tz=a.tz)
    else:
        df = data.schwab_history(_client(), a.symbol, days=a.days, minutes=a.minutes)
        df.to_csv(f"{a.symbol}_{a.minutes}min.csv")
    trades, summary = backtest.run(df, inst, _params(a), a.qty)
    print(backtest.format_summary(summary))
    if a.out:
        trades.to_csv(a.out, index=False)
        with open(a.out.rsplit(".", 1)[0] + "_summary.json", "w") as f:
            json.dump(summary, f, indent=2, default=str)
        print(f"trades -> {a.out}")


def cmd_paper(a):
    """Forward paper trading on live Schwab 1-minute bars."""
    from .schwab_broker import SchwabBroker
    inst, params = INSTRUMENTS[a.symbol], _params(a)
    if inst.is_future:
        raise SystemExit("Schwab's API can't trade or chart futures; use SPY/QQQ here and the "
                         "thinkScript strategy for /MES in paperMoney.")
    client = _client()
    strat = Strategy(inst, params, bar_minutes=1)
    # warm up levels (prior day/week, sessions, swings) on recent history without trading
    hist = data.schwab_history(client, a.symbol, days=8, minutes=1)
    warm = PaperBroker(inst, params)
    now = datetime.now(ZoneInfo(NY))
    for bar in data.iter_bars(hist[hist.index < now.replace(second=0, microsecond=0) - timedelta(minutes=1)]):
        step(strat, warm, bar)
    strat.pending, strat.armed = None, None
    last_ts = hist.index[-1]
    broker = SchwabBroker(client, inst, params, a.qty, dry_run=not a.live)
    journal = open(a.journal, "a", newline="")
    jw = csv.writer(journal)
    seen = 0
    log.info("paper trading %s %s, warm-up through %s", a.symbol,
             "LIVE ORDERS" if a.live else "(simulated fills)", last_ts)
    while True:
        now = datetime.now(ZoneInfo(NY))
        df = data.schwab_history(client, a.symbol, days=1, minutes=1)
        closed = df[(df.index > last_ts) & (df.index + timedelta(minutes=1) <= now)]
        for bar in data.iter_bars(closed):
            step(strat, broker, bar)
            last_ts = bar.ts
        for t in broker.trades[seen:]:
            d = t.as_dict()
            if journal.tell() == 0:
                jw.writerow(d.keys())
            jw.writerow(d.values())
            journal.flush()
        seen = len(broker.trades)
        _time.sleep(max(5, 65 - datetime.now().second))   # wake just after each minute closes


def main():
    ap = argparse.ArgumentParser(prog="silver_bullet")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("backtest", "paper"):
        p = sub.add_parser(name)
        p.add_argument("--symbol", default="MES" if name == "backtest" else "SPY",
                       choices=sorted(INSTRUMENTS))
        p.add_argument("--qty", type=int)
        p.add_argument("--target-mode", choices=["fixed", "draw"])
        p.add_argument("--windows", help="comma list of London,AM,PM")
        p.add_argument("--bias", choices=["auto", "long", "short"])
        p.add_argument("-v", "--verbose", action="store_true")
    b = sub.choices["backtest"]
    g = b.add_mutually_exclusive_group()
    g.add_argument("--csv")
    g.add_argument("--synthetic", action="store_true")
    g.add_argument("--schwab", action="store_true", help="pull history from the Schwab API (default)")
    b.add_argument("--tz", default="America/New_York", help="zone of naive CSV timestamps")
    b.add_argument("--days", type=int, default=45)
    b.add_argument("--minutes", type=int, default=1, choices=[1, 5, 15])
    b.add_argument("--out", help="write the trade log CSV here")
    pp = sub.choices["paper"]
    pp.add_argument("--journal", default="paper_trades.csv")
    pp.add_argument("--live", action="store_true",
                    help="send real Schwab orders (also needs SB_ALLOW_LIVE=1)")
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO if (a.cmd == "paper" or a.verbose) else logging.WARNING,
                        format="%(message)s")
    {"backtest": cmd_backtest, "paper": cmd_paper}[a.cmd](a)


if __name__ == "__main__":
    main()
