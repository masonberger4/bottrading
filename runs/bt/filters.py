"""Free filter-combination pass.   python filters.py OUTDIR [--market ES|ALL] [--min-trades 100] [--draws 400]
Uses only saved trade files: the "everything on" run (variant wd_off) and, for the weekly rule, which of those trades
also exist in wd_pwhl. Filters only remove trades, so every on/off combination is evaluated in pandas.
Caveat: removing a trade can let another one through in a real run (one position at a time, daily limits), so the
short list must be confirmed with real runs.
Filters: week rule (high/low only), AM setup off, PM Silver Bullet off, lunch off, PM last hour off, Monday off,
Friday off, 08:30-news days off, 10:00-news days off.
For each combination: trades, $ total, 2019-22, 2023-26, years up in 2019-22, t-stat, and the share of random day
filters (same trade count, drawn from the unfiltered trades) that do as well.
Then: does choosing on 2019-22 carry over to 2023-26 (rank correlation across combinations, and the top 10)."""
import itertools, sys
import numpy as np, pandas as pd
from report import load

def main():
    out = sys.argv[1]; arg = lambda k, d: sys.argv[sys.argv.index(k) + 1] if k in sys.argv else d
    mk, mint, draws = arg("--market", "ES"), int(arg("--min-trades", 100)), int(arg("--draws", 400))
    T = load(out); T = T if mk == "ALL" else T[T.market == mk]
    A = T[T.variant == "wd_off"].copy(); W = T[T.variant == "wd_pwhl"]
    key = lambda d: d.market + "|" + d.entry_time.astype(str) + "|" + d.setup
    F = {"week_rule": ~key(A).isin(set(key(W))), "am_off": A.setup.isin(["am_mm", "release_ob"]), "pm_sb_off": A.setup == "pm_sb",
         "lunch_off": A.setup == "lunch", "last_hour_off": A.setup == "pm_last_hour", "mon_off": A.weekday == 0, "fri_off": A.weekday == 4,
         "news0830_off": A.news.astype(str) == "0830", "news1000_off": A.news.astype(str) == "1000"}
    print(f"{mk}: {len(A)} unfiltered trades, total {A.net.sum():.0f}; trades each filter removes:", {k: int(v.sum()) for k, v in F.items()})
    rng = np.random.default_rng(1); names = list(F); M = np.array([F[k].values for k in names]); net = A.net.values; yr = A.year.values
    byd = A.groupby(["market", "date"]).net.agg(["sum", "size"]); ds, dn = byd["sum"].values, byd["size"].values
    perms = [rng.permutation(len(byd)) for _ in range(draws)]; cums = [(np.cumsum(dn[p]), np.cumsum(ds[p])) for p in perms]
    rows = []
    for bits in itertools.product([0, 1], repeat=len(names)):
        keep = ~M[np.array(bits, bool)].any(axis=0) if any(bits) else np.ones(len(net), bool)
        x = net[keep]; n = len(x)
        if n < 2:
            continue
        rnd = np.array([cs[min(np.searchsorted(cn, n), len(cs) - 1)] for cn, cs in cums])
        y = yr[keep]
        rows.append(dict(combo="+".join(k for k, b in zip(names, bits) if b) or "(none)", n_filters=sum(bits), trades=n, total=x.sum(),
                         h1=x[y <= 2022].sum(), h2=x[y >= 2023].sum(), n_h1=int((y <= 2022).sum()),
                         h1_yrs_up=sum(x[y == k].sum() > 0 for k in range(2019, 2023)), t=x.mean() / x.std() * n ** .5,
                         rand_as_good=np.mean(rnd >= x.sum())))
    R = pd.DataFrame(rows); R.to_csv(f"{out}/filters_{mk}.csv", index=False)
    ok = R[R.n_h1 >= mint]
    print(f"\n{len(R)} combinations, {len(ok)} with at least {mint} trades in 2019-22.")
    print(f"Positive in 2019-22: {np.mean(ok.h1 > 0):.0%}; positive in 2023-26: {np.mean(ok.h2 > 0):.0%}; positive in both: {np.mean((ok.h1 > 0) & (ok.h2 > 0)):.0%}")
    print(f"Rank correlation of 2019-22 total with 2023-26 total across combinations: {ok.h1.rank().corr(ok.h2.rank()):+.2f}")
    print(f"Best t-stat of any combination: {R.t.max():.2f}; combinations a random filter beats less than 5% of the time: {int((ok.rand_as_good < .05).sum())} of {len(ok)}")
    cols = ["combo", "trades", "total", "h1", "h2", "h1_yrs_up", "t", "rand_as_good"]
    fmt = lambda d: d[cols].round({"total": 0, "h1": 0, "h2": 0, "t": 2, "rand_as_good": 2}).to_string(index=False)
    print("\nTop 10 chosen on 2019-22 (at least 3 of 4 years up), with their 2023-26 result:\n" + fmt(ok[ok.h1_yrs_up >= 3].sort_values("h1", ascending=False).head(10)))
    print("\nFor comparison, top 10 by 2023-26 (hindsight):\n" + fmt(ok.sort_values("h2", ascending=False).head(10)))
    print("\nEach filter alone:\n" + fmt(R[R.n_filters <= 1]))

if __name__ == "__main__":
    main()
