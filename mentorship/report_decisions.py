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
