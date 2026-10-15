"""Command line.

  python -m mentorship2023 fetch                     # SPY + QQQ, 5-min and 1-min, extended hours
  python -m mentorship2023 backtest --minutes 5      # SPY with QQQ as the SMT partner
  python -m mentorship2023 backtest --minutes 1 --symbol QQQ --partner SPY
  python -m mentorship2023 synthetic --seeds 5       # random-walk sanity check
"""
from __future__ import annotations

import argparse
import json

from . import backtest as B
from .strategy import Params


def cmd_backtest(a):
    p = Params(es_pt=a.es_pt) if a.es_pt else Params()
    df = B.load(a.symbol, a.minutes)
    partner = B.load(a.partner, a.minutes) if a.partner else None
    if a.symbol != "SPY" and not a.es_pt:   # scale ES points by price relative to SPY
        spy = B.load("SPY", a.minutes)
        p.es_pt = round(0.10 * df.close.median() / spy.close.median(), 4)
    t = B.run(df, a.minutes, a.symbol, p, partner)
    rep = B.report(t)
    rep["days"] = t.attrs.get("days")
    B.save(t, rep, f"runs/mentorship2023/{a.symbol}_{a.minutes}min_trades.csv")
    print(json.dumps(rep["all"], indent=1))


def cmd_synthetic(a):
    import pandas as pd
    rows = []
    for s in range(a.seeds):
        x, y = B.synthetic(tf=a.minutes, seed=s)
        t = B.run(x, a.minutes, "RW", Params(es_pt=round(0.1 * 700 / 767, 4)), y)
        rows.append(t)
        print(s, B.stats(t))
    t = pd.concat(rows)
    print("all seeds", B.stats(t))


def main():
    ap = argparse.ArgumentParser(prog="mentorship2023")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("fetch").set_defaults(fn=lambda a: B.fetch())
    b = sub.add_parser("backtest")
    b.add_argument("--minutes", type=int, default=5)
    b.add_argument("--symbol", default="SPY")
    b.add_argument("--partner", default="QQQ")
    b.add_argument("--es-pt", type=float, default=None)
    b.set_defaults(fn=cmd_backtest)
    s = sub.add_parser("synthetic")
    s.add_argument("--minutes", type=int, default=5)
    s.add_argument("--seeds", type=int, default=5)
    s.set_defaults(fn=cmd_synthetic)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
