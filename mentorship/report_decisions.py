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
            "max_dd_pct", "years_up", "expectancy_R", "ann_dd_pct_max", "ann_ret_pct", "accept"]
    # caption-gap OT-backtest-acceptance: rank by the acceptance verdict, then the lower annual drawdown, then the total R (the smoother curve first)
    rank = {"ok": 0, "tolerable": 1, "reject": 2}
    out = out.assign(_a=out["accept"].map(rank))
    return out.sort_values(["_a", "ann_dd_pct_max", "sum_R"], ascending=[True, True, False])[cols]


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


def b19_sign(t: pd.DataFrame) -> pd.DataFrame:
    """Decision "B19_sign" (B19-bond-stock-dxy-sign; cc10_019 ~2:37, cc10_009 ~14:33, cc05_009 ~8:31): the trades by the sign regime of the day (Params.im_regime_tag adds the tag
    im_b<with|against>_d<with|against>: whether the bond-price proxy and the dollar moved with or against stocks over the 20 sessions before the trade; "none" = no tag). Report only - no gate:
    trades, win rate, mean R and net per regime."""
    if not len(t):
        return pd.DataFrame(columns=["trades", "win_rate", "avg_R", "net"])
    tag = t.lv_tags.fillna("").astype(str).str.extract(r"(im_b(?:with|against)_d(?:with|against))")[0].fillna("none")
    rows = []
    for k, g in t.assign(regime=tag).groupby("regime"):
        rows.append(dict(regime=k, trades=int(len(g)), win_rate=round(float((g.net > 0).mean()), 3), avg_R=round(float(g.R.mean()), 3), net=round(float(g.net.sum()), 2)))
    return pd.DataFrame(rows).set_index("regime")


def by_tag(t: pd.DataFrame, pattern: str, name: str = "tag") -> pd.DataFrame:
    """Trades grouped by the first lv_tags tag matching the regex `pattern` ("none" = no such tag): trades, win rate, mean R and net. Report only."""
    if not len(t):
        return pd.DataFrame(columns=["trades", "win_rate", "avg_R", "net"])
    tag = t.lv_tags.fillna("").astype(str).str.extract("(" + pattern + ")")[0].fillna("none")
    rows = []
    for k, g in t.assign(_k=tag).groupby("_k"):
        rows.append({name: k, "trades": int(len(g)), "win_rate": round(float((g.net > 0).mean()), 3), "avg_R": round(float(g.R.mean()), 3), "net": round(float(g.net.sum()), 2)})
    return pd.DataFrame(rows).set_index(name)


def m17_hallmarks(t: pd.DataFrame) -> pd.DataFrame:
    """Decision "M17_hallmarks" (X3-swing-checklist-pipeline; cc06_002 ~0:45, cc06_008 ~30:27): the trades by the swing-hallmark count of the order (Params.hallmarks_tag adds the tag hallmarks_<n>: the count of
    trend_ok, daily iof, rates, the seasonal window and an opposing array in agreement with the order; COT is excluded until it is loaded). Report only - no gate."""
    return by_tag(t, r"hallmarks_\d+", "hallmarks")


def stack_report(t: pd.DataFrame) -> pd.DataFrame:
    """X3-full-confluence-stack (cc05_011 ~30:51): the trades by stack count (the tag stack_<n>: season window, flip state, kill-zone timing, rates, dollar; Params.stack_tag / stack_min)."""
    return by_tag(t, r"stack_\d+", "stack")


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
    if "lv_tags" in t.columns:                                           # decision B19_sign (B19-bond-stock-dxy-sign): the orders' im_b*_d* tags (Params.im_regime_tag)
        v = t[t.variant == "B19-bond-stock-dxy-sign"] if "B19-bond-stock-dxy-sign" in set(t.variant) else d
        if "net" in v.columns and "R" in v.columns:
            print("\n--- B19_sign: trades by the bond / dollar vs stock sign regime ---")
            print(b19_sign(v).to_string())
        for nm, fn, var in (("M17_hallmarks", m17_hallmarks, "X3-swing-checklist-pipeline"), ("stack", stack_report, "X3-full-confluence-stack")):      # caption-gap pass bias_htf#3/7: report-only counts
            v = t[t.variant == var] if var in set(t.variant) else d
            if "net" in v.columns and "R" in v.columns:
                print(f"\n--- {nm}: trades by tag count ---")
                print(fn(v).to_string())


if __name__ == "__main__":
    main()
