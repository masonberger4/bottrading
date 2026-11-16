"""Price path after entry on 1-minute bars (2026-11-16).   python entries_1m.py OUTDIR DATA_DIR [--variant wd_off] [--tf 5]
Same questions as entries.py part 2, but the path is followed minute by minute, so what happens inside a 5-minute
entry bar is seen in order. OUTDIR = a run.py output folder (5m or 1m engine run); DATA_DIR holds <S>_1min_db.parquet
(fixed-roll, back-adjusted). The fill minute is the first minute of the entry bar whose range holds the entry price
(for a 1m engine run that is the entry bar itself). Rules: the fill minute can stop the trade but cannot hit a target;
stop and target in one minute counts as a stop; flat at 16:00 otherwise. Gross R, before costs.
Also prints the engine result by stop size against the typical bar (median range of the 12 five-minute bars before
entry) and writes OUTDIR/paths_1m.csv."""
import sys
import numpy as np, pandas as pd
from report import load

def tstat(x):
    x = np.asarray(x, float); x = x[~np.isnan(x)]
    return x.mean() / x.std() * len(x) ** .5 if len(x) > 2 and x.std() > 0 else np.nan

def paths(A, data, tf):
    bars = {}
    for m in A.market.unique():
        b = pd.read_parquet(f"{data}/{m}_1min_db.parquet"); b.columns = [c.lower() for c in b.columns]
        bars[m] = (b.index.tz_convert("UTC").asi8, b.high.values, b.low.values, b.close.values)
    out = []
    for r in A.itertuples():
        ix, H, L, C = bars[r.market]
        t0 = pd.Timestamp(r.entry_time).tz_convert("UTC"); end = (pd.Timestamp(r.entry_time).normalize() + pd.Timedelta(hours=16)).tz_convert("UTC")
        unit = 60 * 10 ** 9 if ix[1] - ix[0] > 10 ** 8 else 60 * 10 ** 6     # index in ns or us
        to_i = lambda t: ix.searchsorted(int(t.value // (10 ** 9 // (unit // 60))) if unit == 60 * 10 ** 6 else t.value)
        i0, i1 = to_i(t0), to_i(end)
        s = 1 if r.side == "long" else -1; risk = abs(r.entry - r.stop); e = r.entry + r.adj
        d = dict(idx=r.Index)
        if i1 - i0 < 2 or risk <= 0:
            out.append(d); continue
        k = next((j for j in range(i0, min(i0 + tf, i1)) if L[j] - 1e-9 <= e <= H[j] + 1e-9), None)
        d["fill_found"] = k is not None
        if k is None:
            out.append(d); continue
        h, l, c = H[k:i1], L[k:i1], C[k:i1]
        fav = (h - e) / risk if s > 0 else (e - l) / risk
        adv = (e - l) / risk if s > 0 else (h - e) / risk
        cl = s * (c - e) / risk
        fav[0] = -np.inf
        n = len(h); stop_i = int(np.argmax(adv >= 1)) if (adv >= 1).any() else n
        d["fill_min"] = k - i0 + 1; d["stopped"] = stop_i < n; d["stop_same_min"] = stop_i == 0
        d["stop_in_5m"] = stop_i < i0 + 5 - k; d["stop_min"] = stop_i if stop_i < n else np.nan
        for q in (1, 2, 3):
            hi = int(np.argmax(fav >= q)) if (fav >= q).any() else n
            d[f"hit{q}"] = hi < stop_i; d[f"res{q}"] = q if hi < stop_i else (-1.0 if stop_i < n else cl[-1])
        for m_ in (2, 3):
            si = int(np.argmax(adv >= m_)) if (adv >= m_).any() else n; hi = int(np.argmax(fav >= m_)) if (fav >= m_).any() else n
            d[f"wide{m_}_res"] = 1.0 if hi < si else (-1.0 if si < n else cl[-1] / m_)
        for mins in (5, 15, 30, 60):
            d[f"m{mins}"] = cl[min(mins, n - 1)]
        d["close"] = cl[-1]
        j0 = max(0, k - 60); rng5 = [H[a:a + 5].max() - L[a:a + 5].min() for a in range(j0, k - 4, 5)]
        d["stop_vs_bar"] = risk / np.median(rng5) if rng5 and np.median(rng5) > 0 else np.nan
        rng1 = H[max(0, k - 30):k] - L[max(0, k - 30):k]
        d["stop_vs_1m_bar"] = risk / np.median(rng1) if len(rng1) and np.median(rng1) > 0 else np.nan
        out.append(d)
    return pd.DataFrame(out).set_index("idx")

def table(ok, groups):
    rows = []
    for nm, g in groups:
        if not len(g): continue
        r = dict(setup=nm, trades=len(g), engine_avg_R=g.R.mean(), engine_t=tstat(g.R), stop_in_fill_minute=g.stop_same_min.astype(float).mean(),
                 stop_within_5m=g.stop_in_5m.astype(float).mean(), stopped_by_16=g.stopped.astype(float).mean())
        for q in (1, 2, 3):
            r[f"hit_{q}R"] = g[f"hit{q}"].astype(float).mean(); r[f"need_{q}R"] = 1 / (1 + q); r[f"avgR_{q}R_target"] = g[f"res{q}"].mean(); r[f"t_{q}R"] = tstat(g[f"res{q}"])
        for m_ in (2, 3):
            r[f"stop_{m_}x_wide_avg"] = g[f"wide{m_}_res"].mean(); r[f"t_stop_{m_}x"] = tstat(g[f"wide{m_}_res"])
        for nm_ in ("m5", "m15", "m30", "m60", "close"):
            r[f"move_{nm_}"] = g[nm_].mean(); r[f"t_{nm_}"] = tstat(g[nm_])
        rows.append(r)
    return pd.DataFrame(rows).round(2).T.to_string(header=False)

def main():
    out, data = sys.argv[1], sys.argv[2]
    var = sys.argv[sys.argv.index("--variant") + 1] if "--variant" in sys.argv else "wd_off"
    tf = int(sys.argv[sys.argv.index("--tf") + 1]) if "--tf" in sys.argv else 5
    T = load(out); A = T[T.variant == var].reset_index(drop=True); pd.set_option("display.width", 250)
    A = A.join(paths(A, data, tf)); A["h"] = np.where(A.year <= 2022, "2019-22", "2023-26")
    ok = A[A.hit1.notna()].copy(); ok[["stop_same_min", "stop_in_5m", "stopped"]] = ok[["stop_same_min", "stop_in_5m", "stopped"]].astype(float)
    print(f"Variant {var}, engine bars {tf}m: {len(A)} trades; fill minute found for {len(ok)}\n")
    big = [s for s, n in A.setup.value_counts().items() if n >= 100]
    print("1-minute price path after the fill (gross R)\n"); print(table(ok, [(s, ok[ok.setup == s]) for s in big] + [("ALL", ok)]))
    print("\nSame, all setups, by half and market\n"); print(table(ok, [(k, g) for k, g in ok.groupby("h")] + [(k, g) for k, g in ok.groupby("market")]))
    for col, nm in (("stop_vs_bar", "typical 5m bar"), ("stop_vs_1m_bar", "typical 1m bar")):
        ok["b"] = pd.cut(ok[col], [0, .5, .75, 1, 1.5, 2, 3, 5, 1e9], labels=["<0.5", "0.5-0.75", "0.75-1", "1-1.5", "1.5-2", "2-3", "3-5", ">5"])
        print(f"\nEngine result by stop size / {nm} (all setups)\n")
        print(ok.groupby(["b"], observed=True).agg(trades=("R", "size"), stop_in_fill_minute=("stop_same_min", "mean"), stop_within_5m=("stop_in_5m", "mean"), avg_R=("R", "mean"),
                                                 t=("R", tstat), net=("net", "sum"), R_2019_22=("R", lambda x: x[ok.loc[x.index, "h"] == "2019-22"].mean()),
                                                 R_2023_26=("R", lambda x: x[ok.loc[x.index, "h"] == "2023-26"].mean()), avgR_3R_target=("res3", "mean")).round(2).to_string())
    ok.drop(columns="b").to_csv(f"{out}/paths_1m.csv", index=False)

if __name__ == "__main__":
    main()
