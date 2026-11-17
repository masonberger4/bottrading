"""python summary.py OUTDIR -> OUTDIR/summary.txt and summary.csv. Per market and variant: trades, R a trade, t, $ and
max drawdown for 2019-22 (the half to choose on) and 2023-26 (the check), and the 2019-26 total."""
import glob, re, sys
import numpy as np, pandas as pd
pd.set_option("display.width", 300)


def ts(x):
    return x.mean() / x.std() * len(x) ** .5 if len(x) > 1 and x.std() else 0.0


def dd(t):
    eq = t.sort_values("exit_time").net.cumsum().values
    return round((eq - np.maximum.accumulate(np.maximum(eq, 0))).min()) if len(eq) else 0


def half(t, tag):
    return {f"n{tag}": len(t), f"R{tag}": round(t.R.mean(), 3) if len(t) else np.nan, f"t{tag}": round(ts(t.R), 1),
            f"usd{tag}": round(t.net.sum()), f"dd{tag}": dd(t)}


def main():
    out = sys.argv[1]; rows = []
    for f in sorted(glob.glob(f"{out}/trades_*.csv")):
        m = re.match(r"trades_([A-Z]+)_(.+)_(\d{4})\.csv$", f.split("/")[-1])
        if sum(1 for _ in open(f)) < 2:
            continue
        t = pd.read_csv(f); t["market"], t["variant"], t["year"] = m.group(1), m.group(2), int(m.group(3)); rows.append(t)
    T = pd.concat(rows, ignore_index=True)
    res = []
    for (mk, v), t in T.groupby(["market", "variant"], sort=False):
        by = t.groupby("year").net.sum(); risk = (t.entry - t.stop).abs() * t.shares
        res.append(dict(market=mk, variant=v, **half(t[t.year <= 2022], 1), **half(t[t.year >= 2023], 2), total=round(t.net.sum()),
                        t=round(ts(t.R), 1), maxdd=dd(t), yrs_up=f"{int((by > 0).sum())}/{len(by)}", worst_yr=round(by.min()),
                        med_risk=round(risk.median()), max_risk=round(risk.max()), long_share=round((t.side == "long").mean(), 2)))
    R = pd.DataFrame(res); R.to_csv(f"{out}/summary.csv", index=False)
    txt = ("1 = 2019-22 (choose), 2 = 2023-26 (check). R = average result a trade in units of its risk ($1,000); t = t-stat; usd = net $; dd = max drawdown $.\n"
           "total / t / maxdd / yrs_up / worst_yr are 2019-26. med_risk / max_risk = $ risked a trade.\n\n" + R.to_string(index=False) + "\n")
    open(f"{out}/summary.txt", "w").write(txt); print(txt)


if __name__ == "__main__":
    main()
