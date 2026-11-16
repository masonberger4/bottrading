"""DXY / bond switch comparison from run.py trade files.   python summary.py OUTDIR
Choose on 2019-22, check on 2023-25 (the 1m DXY file ends 2025); 2026 is shown apart. $ at "$1k risk" (the engine's
$400k notional cap makes the real risk smaller) and R. Paired weekly difference to the base variant of each group."""
import glob, re, sys
import numpy as np, pandas as pd
out = sys.argv[1]
rows = []
for f in sorted(glob.glob(f"{out}/trades_*.csv")):
    m = re.match(r"trades_([A-Z]+)_(.+)_(\d{4})\.csv$", f.split("/")[-1])
    if not m or sum(1 for _ in open(f)) < 2:
        continue
    t = pd.read_csv(f, low_memory=False); t["market"], t["variant"], t["year"] = m.group(1), m.group(2), int(m.group(3)); rows.append(t)
T = pd.concat(rows, ignore_index=True)
T["week"] = pd.to_datetime(T.date).dt.to_period("W").astype(str)
T["per"] = np.where(T.year <= 2022, "2019-22", np.where(T.year <= 2025, "2023-25", "2026"))
GROUPS = [("defaults", ["defaults", "dxy", "bond", "both"]), ("wd_off", ["wd_off", "wo_dxy", "wo_bond", "wo_both"])]
def tstat(d):
    return d.mean() / d.std() * len(d) ** .5 if len(d) > 1 and d.std() else 0.0
res = []
for mk in ["ES", "NQ", "YM", "ALL"]:
    M = T if mk == "ALL" else T[T.market == mk]
    for base, vs in GROUPS:
        for v in vs:
            for per in ["2019-22", "2023-25", "2026"]:
                t = M[(M.variant == v) & (M.per == per)]; b = M[(M.variant == base) & (M.per == per)]
                if not len(t):
                    continue
                r = dict(market=mk, variant=v, period=per, trades=len(t), net=round(t.net.sum()), R=round(t.R.sum(), 1), R_per_trade=round(t.R.mean(), 3))
                if v != base:
                    key = ["market", "week"]
                    d = t.groupby(key).net.sum().sub(b.groupby(key).net.sum(), fill_value=0)
                    dR = t.groupby(key).R.sum().sub(b.groupby(key).R.sum(), fill_value=0)
                    r.update(d_net=round(d.sum()), d_R=round(dR.sum(), 1), d_t=round(tstat(dR), 2))
                res.append(r)
R = pd.DataFrame(res)
R.to_csv(f"{out}/dxy_bond_summary.csv", index=False)
pd.set_option("display.width", 250)
for mk in ["ALL", "ES", "NQ", "YM"]:
    print(f"\n== {mk} =="); print(R[R.market == mk].drop(columns="market").to_string(index=False))
