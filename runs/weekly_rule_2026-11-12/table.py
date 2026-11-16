import sys, glob, warnings, pandas as pd
warnings.filterwarnings("ignore")
O = "C:/Users/mason/bottrading/runs/weekly_rule_2026-11-12/out"
vs = sys.argv[1:]
rows, sets = [], []
for v in vs:
    fs = glob.glob(f"{O}/trades_{v}_*.csv")
    if len(fs) < 8: print(v, "incomplete", len(fs)); continue
    T = pd.concat([pd.read_csv(f, low_memory=False) for f in fs], ignore_index=True)
    r = {"variant": v, "trades": len(T), "$": T.net.sum(), "19-22": T[T.year <= 2022].net.sum(), "23-26": T[T.year >= 2023].net.sum(), "win": (T.net > 0).mean()}
    eq = T.sort_values("entry_time").net.cumsum(); r["maxDD"] = (eq - eq.cummax()).min()
    for y in range(2019, 2027): r[y] = T[T.year == y].net.sum()
    rows.append(r)
    s = T.groupby("setup").net.agg(["size", "sum"]); s.columns = [f"{v}_n", f"{v}_$"]; sets.append(s)
print(pd.DataFrame(rows).set_index("variant").round(2).to_string(float_format=lambda x: f"{x:,.0f}" if abs(x) > 2 else f"{x:.2f}"))
print(pd.concat(sets, axis=1).fillna(0).round(0).to_string())
