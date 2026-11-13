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
    return dict(trades=n, total=x.sum(), h1=t.net[t.year <= 2022].sum(), h2=t.net[t.year >= 2023].sum(), yrs_up=f"{int((by > 0).sum())}/{len(by)}",
                maxdd=(eq - np.maximum.accumulate(np.maximum(eq, 0))).min(), t=x.mean() / x.std() * n ** .5 if n > 1 and x.std() else 0.0,
                lo=np.percentile(bw, 5), hi=np.percentile(bw, 95), x2=t.gross.sum() - 2 * t.costs.sum(), R=t.R.sum() if "R" in t else np.nan,
                med_risk=((t.entry - t.stop).abs() * t.shares).median(), **{str(y): by.get(y, 0.0) for y in range(2019, 2027)})

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
    num = [c for c in R.columns if c not in ("market", "variant", "yrs_up", "trades", "t", "R", "diff_t")]
    R[num] = R[num].round(0).astype("Int64"); R[[c for c in ("t", "R", "diff_t") if c in R]] = R[[c for c in ("t", "R", "diff_t") if c in R]].round(2)
    R.to_csv(f"{out}/report.csv", index=False)
    print(f"engine {open(f'{out}/ENGINE.txt').read().strip()}; {T.variant.nunique()} variants in this folder (count every variant ever tried when judging a winner)\n")
    print(R.to_markdown(index=False) if "--md" in sys.argv else R.to_string(index=False))

if __name__ == "__main__":
    main()
