"""How noisy are the weekly-rule screen results? Reads the saved trade files only (no backtest run).
Run:  python runs/backtest_method_2026-11-13/noise.py   (from C:/Users/mason/bottrading; needs runs/weekly_rule_2026-11-12/out)
Prints per variant: trades, total, per-trade mean / sd, t-stat, weekly-block bootstrap 90% range of the total;
then a random-filter test (random day subsets of the unfiltered run with the same trade count) and a cost stress."""
import glob, sys
import numpy as np, pandas as pd

OUT = sys.argv[1] if len(sys.argv) > 1 else "runs/weekly_rule_2026-11-12/out"
rng = np.random.default_rng(1)


def load(v):
    fs = [f for f in sorted(glob.glob(f"{OUT}/trades_{v}_20*.csv")) if sum(1 for _ in open(f)) > 1]
    return pd.concat([pd.read_csv(f, low_memory=False) for f in fs], ignore_index=True)


T = {}
for v in ["defaults", "wd_pwhl", "pwhl_x", "wd_off", "off_x", "wd_nearest"]:
    t = T[v] = load(v); x = t.net.values; n = len(x)
    wk = t.groupby(pd.to_datetime(t.date).dt.to_period("W")).net.sum().values
    bw = np.array([rng.choice(wk, len(wk)).sum() for _ in range(5000)])
    print(f"{v:11s} n={n:4d} total={x.sum():8.0f} mean={x.mean():6.1f} sd={x.std():5.0f} t={x.mean() / x.std() * n ** .5:5.2f} "
          f"P(total<=0)={np.mean(bw <= 0):.2f} 90% range=[{np.percentile(bw, 5):.0f}, {np.percentile(bw, 95):.0f}] costs={t.costs.sum():.0f}")
for base, sub in [("wd_off", "wd_pwhl"), ("off_x", "pwhl_x")]:      # is the weekly filter better than a random filter?
    b, target = T[base], len(T[sub]); byd = b.groupby("date").net.agg(["sum", "size"]); tots = []
    for _ in range(5000):
        p = rng.permutation(len(byd)); k = np.searchsorted(np.cumsum(byd["size"].values[p]), target)
        tots.append(byd["sum"].values[p][:k + 1].sum())
    tots = np.array(tots)
    print(f"{base} -> {sub}: actual {T[sub].net.sum():.0f}, random day subsets mean {tots.mean():.0f} sd {tots.std():.0f}, "
          f"share of random >= actual {np.mean(tots >= T[sub].net.sum()):.2f}")
for v in ["pwhl_x", "off_x"]:
    t = T[v]; print(v, "net at 1x / 2x / 3x costs:", [round(t.gross.sum() - k * t.costs.sum()) for k in (1, 2, 3)])
