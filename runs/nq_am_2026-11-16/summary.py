"""Compact table for the narrow morning runs: python summary.py OUTDIR  ->  OUTDIR/summary.txt (and .csv)."""
import glob, re, sys
import numpy as np, pandas as pd
pd.set_option("display.width", 400)

def load(out):
    rows = []
    for f in sorted(glob.glob(f"{out}/trades_*.csv")):
        m = re.match(r"trades_([A-Z]+)_(.+)_(\d{4})\.csv$", f.split("/")[-1])
        if sum(1 for _ in open(f)) < 2:
            continue
        t = pd.read_csv(f, usecols=["date", "side", "swept", "entry", "stop", "shares", "gross", "costs", "net", "R", "exit_time", "exit_reason"]); t["market"], t["variant"], t["year"] = m.group(1), m.group(2), int(m.group(3)); rows.append(t)
    return pd.concat(rows, ignore_index=True)

def ts(x):
    return x.mean() / x.std() * len(x) ** .5 if len(x) > 1 and x.std() else 0.0

def stat(t):
    z = t[t.year <= 2018]; t = t[t.year >= 2019]
    t = t.sort_values("exit_time"); eq = t.net.cumsum().values; eqR = t.R.cumsum().values
    dd = (eq - np.maximum.accumulate(np.maximum(eq, 0))).min(); ddR = (eqR - np.maximum.accumulate(np.maximum(eqR, 0))).min()
    a, b = t[t.year <= 2022], t[t.year >= 2023]; by = t.groupby("year").net.sum()
    risk = (t.entry - t.stop).abs() * t.shares
    return dict(trades=len(t), win=round((t.net > 0).mean() * 100), R=round(t.R.mean(), 3), t=round(ts(t.R), 2), total=round(t.net.sum()),
                n1=len(a), R1=round(a.R.mean(), 3) if len(a) else np.nan, t1=round(ts(a.R), 2), usd1=round(a.net.sum()),
                n2=len(b), R2=round(b.R.mean(), 3) if len(b) else np.nan, t2=round(ts(b.R), 2), usd2=round(b.net.sum()),
                n0=len(z), R0=round(z.R.mean(), 3) if len(z) else np.nan, t0=round(ts(z.R), 2), usd0=round(z.net.sum()),
                maxdd=round(dd), maxddR=round(ddR, 1), yrs_up=f"{int((by > 0).sum())}/{len(by)}", worst_yr=round(by.min()),
                x2cost=round(t.gross.sum() - 2 * t.costs.sum()), med_risk=round(risk.median()), max_risk=round(risk.max()),
                cost_R=round((t.costs / risk).mean(), 3))

def main():
    out = sys.argv[1]; T = load(out); rows = []
    for (mk, v), t in T.groupby(["market", "variant"], sort=False):
        rows.append(dict(market=mk, variant=v, **stat(t)))
    if T.market.nunique() > 1:
        for v, t in T.groupby("variant", sort=False):
            rows.append(dict(market="ALL", variant=v, **stat(t)))
    R = pd.DataFrame(rows)
    R.to_csv(f"{out}/summary.csv", index=False)
    txt = ("Columns: R = average result a trade in units of its own risk (x $1,000 = $ a trade); t = t-stat; 1 = 2019-22 (chosen on), 2 = 2023-26 (check), 0 = 2016-18 (second check, not in the totals);\ntrades, win, R, t, total, maxdd, yrs_up, worst_yr, x2cost are 2019-26;\n"
           "maxdd in $ and in R; x2cost = total at twice the costs; med_risk / max_risk = $ risked a trade; cost_R = costs a trade in R.\n\n" + R.to_string(index=False) + "\n")
    txt += "\nBase by year, $ (trades):\n"
    for mk, M in T[T.variant == "base"].groupby("market"):
        g = M.groupby("year").net.agg(["sum", "count"])
        txt += f"  {mk}: " + "  ".join(f"{y} {v['sum']:+,.0f} ({int(v['count'])})" for y, v in g.iterrows()) + "\n"
    b = T[(T.variant == "base") & (T.year >= 2019)]
    for col in ("exit_reason", "side", "swept"):
        g = b.groupby(col).R.agg(["count", "mean"])
        txt += f"Base 2019-26, all markets, by {col}: " + "; ".join(f"{k} {int(v['count'])} trades {v['mean']:+.3f} R" for k, v in g.iterrows()) + "\n"
    for mk, M in R.groupby("market"):
        one = M[~M.variant.isin(["pick"])]
        txt += (f"\n{mk}: {len(one)} variants; positive R in 2019-22: {(one.R1 > 0).sum()}, in 2023-26: {(one.R2 > 0).sum()}, in both: {((one.R1 > 0) & (one.R2 > 0)).sum()}, in 2016-18: {(one.R0 > 0).sum()}; "
                f"rank correlation of R 2019-22 vs 2023-26: {one.R1.rank().corr(one.R2.rank()):.2f}\n")
    open(f"{out}/summary.txt", "w").write(txt); print(txt)

if __name__ == "__main__":
    main()
