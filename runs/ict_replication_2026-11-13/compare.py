"""Line up ICT's video trades (ict_trades.csv) with the engine's traced runs (trace_run.py outputs in OUT)."""
import sys, pandas as pd
OUT = sys.argv[1] if len(sys.argv) > 1 else "out"
HERE = __file__.rsplit("/", 1)[0]
ict = pd.read_csv(f"{HERE}/ict_trades.csv", sep="|", dtype=str).fillna("")
def rd(k, sym, v, y):
    try:
        return pd.read_csv(f"{OUT}/{k}_{sym}_{v}_{y}.csv")
    except Exception:
        return pd.DataFrame()
rows = []
for _, x in ict.iterrows():
    y = x.date[:4]
    line = {"id": x.id, "date": x.date, "dow": pd.Timestamp(x.date).day_name()[:3], "sym": x.sym, "ict": f"{x.side} {x.t_entry} @{x.entry}"}
    for v in ("defaults", "open"):
        t, k, f = rd("trades", x.sym, v, y), rd("skips", x.sym, v, y), rd("funnel", x.sym, v, y)
        if not len(f) and not len(t):
            line[v] = "not run"; continue
        t = t[t.date == x.date] if len(t) else t
        k = k[k.iloc[:, 0] == x.date] if len(k) else k
        f = f[f.day == x.date] if len(f) else f
        tr = "; ".join(f"{r.setup} {r.side} {str(r.entry_time)[11:16]} @{r.entry:.2f} stop {r.stop:.2f} out {str(r.exit_time)[11:16]} {r.exit_reason} {r.R:+.2f}R" for r in t.itertuples())
        sk = "; ".join(f"{r[3]}:{r[4]}" for r in k.itertuples()) if len(k) else ""
        st = {r.key: r.n for r in f.itertuples()}
        stages = "/".join(str(st.get(s, 0)) for s in ("1_sweep", "2_mss", "3_fvg", "4_order"))
        xs = sorted(((n, key) for key, n in st.items() if key.startswith("x_")), reverse=True)[:5]
        line[v] = (tr or "no trade") + (f" | blocks: {sk}" if sk else "") + f" | sweep/mss/fvg/order {stages}" + (" | rejects: " + ", ".join(f"{key[2:]} {n}" for n, key in xs) if xs else "")
    rows.append(line)
df = pd.DataFrame(rows)
df.to_csv(f"{HERE}/compare.csv", index=False)
for r in df.itertuples():
    print(f"\n{r.id} {r.date} {r.dow} {r.sym} ICT {r.ict}\n  DEF : {r.defaults}\n  OPEN: {r.open}")
