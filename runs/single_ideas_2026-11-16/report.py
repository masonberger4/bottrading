"""Tables for ideas.py:  python report.py [DIR with trades.parquet] > output.txt
Choose on 2019-22, check on 2023-26. $ at $1,000 risk a trade (= R x 1,000). "t" counts one day as one result
(the three markets move together). Max drawdown is on the three markets traded together, in time order."""
import sys
from pathlib import Path
import numpy as np, pandas as pd

d = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent
t = pd.read_parquet(d / "trades.parquet")
t["key"] = t.idea + ":" + t["var"] + ":" + t.tgt
t["half"] = np.where(t.day < "2023-01-01", "choose", "check")
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 500)


def stats(x, col="r"):
    if not len(x):
        return dict(n=0)
    byday = x.groupby("day")[col].sum()
    eq = x.sort_values("exit_ts")[col].cumsum()
    return dict(n=len(x), days=len(byday), avgR=x[col].mean(), usd=x[col].sum() * 1000, win=(x[col] > 0).mean() * 100,
                t=byday.mean() / byday.std(ddof=1) * np.sqrt(len(byday)) if len(byday) > 2 else np.nan,
                maxdd=(eq - eq.cummax().clip(lower=0)).min() * 1000, risk=x.risk.median())


def line(x):
    a, b, c = stats(x[x.half == "choose"]), stats(x[x.half == "check"]), stats(x)
    s1 = stats(x[x.half == "check"], "r1")
    c["best"], c["amb"] = x.r_best.mean(), x.amb.mean() * 100
    return dict(n=c["n"], ch_n=a.get("n"), ch_avgR=a.get("avgR"), ch_usd=a.get("usd"), ch_t=a.get("t"), ck_n=b.get("n"), ck_avgR=b.get("avgR"),
                ck_usd=b.get("usd"), ck_t=b.get("t"), ck_win=b.get("win"), ck_avgR_1tick=s1.get("avgR"), all_usd=c["usd"], all_t=c["t"], maxdd=c["maxdd"], all_avgR=c["avgR"], amb=c["amb"], all_avgR_best=c["best"])


fmt = {"ch_avgR": "{:+.3f}", "ck_avgR": "{:+.3f}", "ck_avgR_1tick": "{:+.3f}", "ch_usd": "{:+,.0f}", "ck_usd": "{:+,.0f}", "all_usd": "{:+,.0f}",
       "maxdd": "{:,.0f}", "ch_t": "{:+.2f}", "ck_t": "{:+.2f}", "all_t": "{:+.2f}", "ck_win": "{:.0f}%", "all_avgR": "{:+.3f}", "all_avgR_best": "{:+.3f}", "amb": "{:.1f}%"}
def show(df):
    df = df.copy()
    for k, f in fmt.items():
        if k in df:
            df[k] = df[k].map(lambda v: "" if pd.isna(v) else f.format(v))
    print(df.to_string()); print()


allv = pd.DataFrame({k: line(x) for k, x in t.groupby("key")}).T
print("== Every variant, all three markets (ch = 2019-22 choose, ck = 2023-26 check) ==")
show(allv)

print("== Chosen on 2019-22 (best t with 100+ trades in 2019-22), per idea, then its 2023-26 check ==")
ok = allv[allv.ch_n >= 100].copy(); ok["idea"] = [k.split(":")[0] for k in ok.index]
ok["ch_t"] = ok.ch_t.astype(float)
best = ok.sort_values("ch_t", ascending=False).groupby("idea").head(3)
show(best.sort_values(["idea", "ch_t"], ascending=[True, False]).drop(columns="idea"))

print("== The top pick of each idea, by market ==")
top = ok.sort_values("ch_t", ascending=False).groupby("idea").head(1).index
show(pd.DataFrame({(k, mk): line(x) for k in top for mk, x in t[t.key == k].groupby("market")}).T)

print("== The top pick of each idea, by year (avg R, trades) ==")
y = t[t.key.isin(top)].assign(year=lambda x: x.day.dt.year)
print(y.pivot_table(index="key", columns="year", values="r", aggfunc="mean").round(2).to_string())
print(y.pivot_table(index="key", columns="year", values="r", aggfunc="size").to_string()); print()

print("== How choosing carries over: 2019-22 t against 2023-26 t across all variants with 100+ trades each half ==")
z = allv[(allv.ch_n >= 100) & (allv.ck_n >= 100)].astype({"ch_t": float, "ck_t": float, "ch_avgR": float, "ck_avgR": float})
print("variants:", len(z), " rank correlation of t:", round(z.ch_t.rank().corr(z.ck_t.rank()), 2),
      " positive in both halves:", int(((z.ch_avgR > 0) & (z.ck_avgR > 0)).sum()), " positive in 2019-22:", int((z.ch_avgR > 0).sum()),
      " positive in 2023-26:", int((z.ck_avgR > 0).sum()))
print("largest |t| over the whole period:", z.assign(a=allv.all_t.astype(float).abs()).sort_values("a", ascending=False).head(8)[["n", "ch_avgR", "ck_avgR", "all_t"]].to_string())
print()
print("== By idea, every variant pooled (shows the idea's average trade; variants overlap, so no t) ==")
g = t.groupby(["idea", "half"]).r.agg(["size", "mean"]).unstack(); print(g.round(3).to_string()); print()
print("== Median risk in points and exit mix, by idea and market ==")
print(t.groupby(["idea", "market"]).risk.median().unstack().round(2).to_string())
print(t.groupby(["idea", "how"]).size().unstack().to_string())
