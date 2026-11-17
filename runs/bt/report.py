"""Standard report for run.py output.   python report.py OUTDIR [--base wd_off] [--md]
Per market and for all markets together, each variant gets: trades, total $, 2019-22, 2023-26, years up, max drawdown,
t-stat, 90% chance range of the total (weekly-block bootstrap), total at 2x costs, total in R (x $1,000 = the result
if every trade really risked $1,000; the engine's $400k notional cap makes most trades risk less), and by year.
With --base, also the paired weekly difference to that variant (t-stat of the difference)."""
import glob, re, sys
import numpy as np, pandas as pd

def load(out):
    rows = []
    for f in sorted(glob.glob(f"{out}/trades_*.csv")):
        m = re.match(r"trades_([A-Z]+)_(.+)_(\d{4})\.csv$", f.replace("\\", "/").split("/")[-1])
        if not m or sum(1 for _ in open(f)) < 2:
            continue
        t = pd.read_csv(f, low_memory=False); t["market"], t["variant"], t["year"] = m.group(1), m.group(2), int(m.group(3)); rows.append(t)
    t = pd.concat(rows, ignore_index=True)
    t["week"] = pd.to_datetime(t.date).dt.to_period("W").astype(str)
    return t

def stats(t, rng):
    x = t.net.values; n = len(x)
    wk = t.groupby("week").net.sum().values
    bw = np.array([rng.choice(wk, len(wk)).sum() for _ in range(3000)])
    eq = t.sort_values("exit_time").net.cumsum().values
    by = t.groupby("year").net.sum()
    ts = t.sort_values("exit_time"); eqR = ts.R.cumsum().values; risk = (t.entry - t.stop).abs() * t.shares
    peak = np.maximum.accumulate(np.maximum(eq, 0)); d = pd.to_datetime(ts.exit_time.astype(str).str[:10]).values
    last_peak = pd.Series(np.where(eq >= peak, np.arange(len(eq)), np.nan)).ffill().fillna(0).astype(int).values     # longest stretch below a prior equity high, in days
    dd_days = int(((d - d[last_peak]) / np.timedelta64(1, "D")).max()) if len(d) else 0
    bad = int((np.where(t.side == "long", 1, -1) * (t.entry - t.stop) <= 0).sum())      # stop not on the loss side of the entry (PR #95): must be 0, such "trades" stop out at a profit
    return dict(trades=n, bad_stop=bad, total=x.sum(), h1=t.net[t.year <= 2022].sum(), h2=t.net[t.year >= 2023].sum(), yrs_up=f"{int((by > 0).sum())}/{len(by)}",
                maxdd=(eq - np.maximum.accumulate(np.maximum(eq, 0))).min(), t=x.mean() / x.std() * n ** .5 if n > 1 and x.std() else 0.0,
                lo=np.percentile(bw, 5), hi=np.percentile(bw, 95), x2=t.gross.sum() - 2 * t.costs.sum(), R=t.R.sum() if "R" in t else np.nan,
                med_risk=risk.median(), max_risk=risk.max(), maxdd_R=(eqR - np.maximum.accumulate(np.maximum(eqR, 0))).min(),
                dd_days=dd_days, worst_year=by.min(), **{str(y): by.get(y, 0.0) for y in range(2019, 2027)})

def main():
    out = sys.argv[1]; base = sys.argv[sys.argv.index("--base") + 1] if "--base" in sys.argv else None
    rng = np.random.default_rng(1); T = load(out); rows = []
    order = list(dict.fromkeys(T.variant))
    for mk in list(dict.fromkeys(T.market)) + (["ALL"] if T.market.nunique() > 1 else []):
        M = T if mk == "ALL" else T[T.market == mk]
        for v in order:
            t = M[M.variant == v]
            if not len(t):
                continue
            r = dict(market=mk, variant=v, **stats(t, rng))
            if base and v != base and (M.variant == base).any():
                d = t.groupby("week").net.sum().sub(M[M.variant == base].groupby("week").net.sum(), fill_value=0)
                r["diff_vs_base"], r["diff_t"] = d.sum(), d.mean() / d.std() * len(d) ** .5
            rows.append(r)
    R = pd.DataFrame(rows)
    num = [c for c in R.columns if c not in ("market", "variant", "yrs_up", "trades", "bad_stop", "t", "R", "diff_t")]
    R[num] = R[num].round(0).astype("Int64"); R[[c for c in ("t", "R", "diff_t") if c in R]] = R[[c for c in ("t", "R", "diff_t") if c in R]].round(2)
    R.to_csv(f"{out}/report.csv", index=False)
    print(f"engine {open(f'{out}/ENGINE.txt').read().strip()}; {T.variant.nunique()} variants in this folder (count every variant ever tried when judging a winner)\n")
    if R.bad_stop.sum():
        print(f"WARNING: {int(R[R.market != 'ALL'].bad_stop.sum())} trades have their stop on the profit side of the entry (column bad_stop); those results are not real\n")
    print(R.to_markdown(index=False) if "--md" in sys.argv else R.to_string(index=False))

if __name__ == "__main__":
    main()
