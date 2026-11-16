"""Per ICT trade: what the traced engine did on his side inside his entry window (labels = strategy.py lines).
    python why_miss.py OUTDIR VARIANT [SYM]"""
import sys, re, pandas as pd
OUT, V = sys.argv[1], sys.argv[2]
SYM = sys.argv[3] if len(sys.argv) > 3 else None
HERE = __file__.rsplit("/", 1)[0] if "/" in __file__ else "."
ict = pd.read_csv(f"{HERE}/ict_trades.csv", sep="|", dtype=str).fillna("")
def mins(s):
    h, m = s.split(":"); return int(h) * 60 + int(m)
def window(t):
    ts = re.findall(r"\d\d:\d\d", t)
    if ts:
        return mins(ts[0]) - 20, mins(ts[-1]) + 10
    return {"AM": (570, 720), "PM": (720, 960)}.get(t, (570, 960))
cache = {}
for _, x in ict.iterrows():
    if SYM and x.sym != SYM:
        continue
    key = (x.sym, x.date[:4])
    if key not in cache:
        try:
            cache[key] = pd.read_csv(f"{OUT}/trace_{x.sym}_{V}_{x.date[:4]}.csv")
        except Exception:
            cache[key] = None
    tr = cache[key]
    if tr is None:
        continue
    lo, hi = window(x.t_entry)
    sg = 1 if x.side == "long" else -1
    d = tr[(tr.day == x.date) & (tr.t >= lo) & (tr.t <= hi) & (tr.side.isin([sg, 0]))]
    print(f"\n{x.id} {x.date} {x.sym} {x.side} {x.t_entry} @{x.entry} | {x.setup}")
    for (ses, lab), g in sorted(d.groupby([d.session.fillna('-'), "label"]), key=lambda kv: kv[1].t.min()):
        print(f"   {ses:6s} {lab:28s} n={int(g.n.sum()):3d}  {g.t.min()//60:02d}:{g.t.min()%60:02d}-{g.t.max()//60:02d}:{g.t.max()%60:02d}")
