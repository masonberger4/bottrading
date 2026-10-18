"""Command line.

  python -m mentorship fetch                     # SPY + QQQ, 5-min and 1-min, extended hours
  python -m mentorship backtest --minutes 5      # SPY with QQQ as the SMT partner
  python -m mentorship backtest --minutes 1 --symbol QQQ --partner SPY
  python -m mentorship synthetic --seeds 5       # random-walk sanity check
  python -m mentorship paper --minutes 1         # live Schwab bars, simulated fills only
"""
from __future__ import annotations

import argparse
import json

from . import backtest as B
from .strategy import Params


def cmd_backtest(a):
    from dataclasses import replace
    p = Params(es_pt=a.es_pt) if a.es_pt else Params()
    p = replace(p, ob_entry=a.ob_entry, ob_entry_px=a.ob_entry_px, ob_stop=a.ob_stop)   # owner #11
    df = B.load(a.symbol, a.minutes, source=a.source)
    partner = B.load(a.partner, a.minutes, source=a.source) if a.partner else None
    if a.symbol != "SPY" and not a.es_pt:   # scale ES points by price relative to SPY
        spy = B.load("SPY", a.minutes, source=a.source)
        p.es_pt = round(0.10 * df.close.median() / spy.close.median(), 4)
    t = B.run(df, a.minutes, a.symbol, p, partner, meta=B.load_meta(a.symbol, a.minutes, a.source))
    rep = B.report(t)
    rep["days"] = t.attrs.get("days")
    B.save(t, rep, f"runs/mentorship/{a.symbol}_{a.minutes}min_trades.csv")
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


def cmd_paper(a):
    from . import paper
    paper.run(a.symbol, a.partner, a.minutes)


def main():
    ap = argparse.ArgumentParser(prog="mentorship")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("fetch").set_defaults(fn=lambda a: B.fetch())
    b = sub.add_parser("backtest")
    b.add_argument("--minutes", type=int, default=5)
    b.add_argument("--symbol", default="SPY")
    b.add_argument("--partner", default="QQQ")
    b.add_argument("--es-pt", type=float, default=None)
    b.add_argument("--source", default="schwab", choices=("schwab", "alpaca", "databento"))
    b.add_argument("--ob-entry", default="pre_break", choices=("pre_break", "post_mss", "both"))
    b.add_argument("--ob-entry-px", default="body_top", choices=("body_top", "mt", "range_top"))
    b.add_argument("--ob-stop", default="mt", choices=("mt", "ext"))
    b.set_defaults(fn=cmd_backtest)
    s = sub.add_parser("synthetic")
    s.add_argument("--minutes", type=int, default=5)
    s.add_argument("--seeds", type=int, default=5)
    s.set_defaults(fn=cmd_synthetic)
    pp = sub.add_parser("paper")
    pp.add_argument("--minutes", type=int, default=1)
    pp.add_argument("--symbol", default="SPY")
    pp.add_argument("--partner", default="QQQ")
    pp.set_defaults(fn=cmd_paper)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
