"""Tables for the gap-scalp check: python report.py OUTDIR  (reads OUTDIR/ndog_all_trades.csv written by ndog.py)."""
import sys, numpy as np, pandas as pd
t = pd.read_csv(f"{sys.argv[1]}/ndog_all_trades.csv").sort_values("entry_time").reset_index(drop=True)
def line(g, col):
    r = g[col]; n = len(r)
    if not n: return dict(n=0)
    ev = g.groupby("date")[col].sum()                           # one evening = one observation (ES / NQ / YM move together)
    eq = (r * 1000).cumsum(); dd = (eq - eq.cummax().clip(lower=0)).min()
    return dict(n=n, evenings=len(ev), avg_R=round(r.mean(), 3), total_R=round(r.sum(), 1), usd=int(round(r.sum() * 1000, -2)), win=f"{(r > 0).mean():.0%}",
                t=round(r.mean() / r.std(ddof=1) * n ** .5, 2) if n > 2 else np.nan, t_evening=round(ev.mean() / ev.std(ddof=1) * len(ev) ** .5, 2) if len(ev) > 2 else np.nan,
                max_dd_usd=int(round(dd, -2)), max_dd_R=round(dd / 1000, 1))
def table(title, groups, cols=("R_eng", "R_thru", "R_slip")):
    print(f"\n## {title}")
    for c in cols:
        print(f"[{c}]"); print(pd.DataFrame({k: line(g, c) for k, g in groups}).T.to_string())
print("trades", len(t), "| price checks: 1m open == entry:", int(t.entry_px_ok.sum()), "| raw 1m open == entry - adj:", int((abs(t.raw_open_1m - t.raw_entry) < 1e-6).sum()),
      "| roll evenings:", int(t.roll_evening.sum()), "| missing entry minute:", int((t.entry_lag_min > 0).sum()))
print("5m engine exit vs 1m replay (touch):"); print(pd.crosstab(t.exit_reason, t.m1_touch))
print("target only touched, never traded through:", int(((t.exit_reason == "t1") & (t.m1_thru != "t1")).sum()), "of", int((t.exit_reason == "t1").sum()))
print("median risk in ticks:", t.groupby("market").apply(lambda g: round((g.tick_R ** -1).median(), 1)).to_dict(), "| median cost in R:", t.cost_R.median(), "| median 1-tick in R:", t.tick_R.median())
print("contracts-equivalent volume in the entry minute, median:", t.groupby("market").vol_entry_min.median().to_dict())
table("All evenings 2016-26", [("all", t)] + list(t.groupby("market")))
table("By period (choose 2019-22, check 2023-26; 2016-18 = extra)", list(t.groupby("period")))
table("Taken by the full engine run (2019-26) vs evenings the engine's day rules skipped", [("engine took", t[t.in_engine]), ("engine skipped 2019-26", t[~t.in_engine & (t.year >= 2019)]), ("2016-18 (not run)", t[t.year <= 2018])])
table("Without roll evenings", [("no roll", t[~t.roll_evening])])
table("By side", list(t.groupby("side")), cols=("R_eng", "R_slip"))
table("By year", list(t.groupby("year")), cols=("R_eng",))
