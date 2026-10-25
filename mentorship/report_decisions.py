"""Summarise runs/mentorship/decision_trades.csv: each decision variant vs the defaults.

    python -m mentorship.report_decisions
"""
from __future__ import annotations

import pandas as pd

from . import backtest as B


def table(t: pd.DataFrame, tf: int) -> pd.DataFrame:
    t = t[t.tf == tf]
    rows = []
    for v, g in t.groupby("variant"):
        s = B.stats(g)
        yr = g.groupby("year").R.sum()
        s.update(variant=v, sum_R=round(float(g.R.sum()), 1), years_up=f"{int((yr > 0).sum())}/{len(yr)}",
                 R_se=round(float(g.R.std() / max(len(g), 1) ** 0.5), 3),
                 top5_R=round(float(g.R.nlargest(5).sum()), 1))
        rows.append(s)
    out = pd.DataFrame(rows).set_index("variant")
    cols = ["trades", "win_rate", "avg_R", "R_se", "sum_R", "top5_R", "profit_factor", "net",
            "max_dd_pct", "years_up"]
    return out[cols].sort_values("avg_R", ascending=False)


def m3_scan(*runs: pd.DataFrame) -> dict:
    """Decision "M3_scan" (BH-M3-scan-all-indices; 054 ~18:18 'specialize in one market' vs 067 ~1:33:29 'it might only be in one and that is why I teach you
    to look at all three'): the per-market books of the same strategy run on each market (Params.markets), summarised - the days with a setup in at least one
    market (the union the combined book trades), in both markets, in only one market, the share of the setup days that only ONE market offered, and the
    setups per setup day. No engine change: backtest.combine(pick="first") takes the first fill across the books."""
    books = [r for r in runs if len(r)]
    if not books:
        return dict(days=0, both_days=0, one_market_days=0, share_one_market=0.0, setups_per_day=0.0)
    days = [set(r.date.astype(str)) for r in books]
    union = set().union(*days)
    both = {d for d in union if sum(d in x for x in days) >= 2}
    one = union - both
    n = sum(len(r) for r in books)
    return dict(days=len(union), both_days=len(both), one_market_days=len(one), share_one_market=len(one) / len(union), setups_per_day=n / len(union))


def main(path="runs/mentorship/decision_trades.csv"):
    t = pd.read_csv(path)
    for tf in sorted(t.tf.unique()):
        print(f"\n=== {tf}-minute, SPX signals traded as SPY, 2019-2026 ===")
        print(table(t, tf).to_string())
    d = t[t.variant == "defaults"]
    for col in ("setup", "sb", "b_react", "b_draw", "b_pd", "exit_reason", "side"):
        print(f"\n--- defaults by {col} ---")
        for (tf, k), g in d.groupby(["tf", d[col].astype(str)]):
            s = B.stats(g)
            print(f"{tf}m {k:>14}  n={s['trades']:4d}  avgR={s.get('avg_R', 0):+.3f}  win={s.get('win_rate', 0):.2f}")


if __name__ == "__main__":
    main()
