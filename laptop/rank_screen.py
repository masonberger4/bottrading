"""Rank 2021 screen jobs against defaults. usage: python laptop/rank_screen.py <dec_jobs dir> [year=2021]"""
import sys, glob, os, pandas as pd
d = sys.argv[1]; y = sys.argv[2] if len(sys.argv) > 2 else "2021"
def load(f):
    t = pd.read_csv(f)
    return t if len(t) else t
base = pd.read_csv(f"{d}/5m_{y}_defaults.csv")
key = ["entry_time", "side", "entry", "stop"]
bk = set(map(tuple, base[key].astype(str).values))
rows = []
for f in glob.glob(f"{d}/5m_{y}_*.csv"):
    v = os.path.basename(f)[8:-4]
    if v in ("defaults", "current") or os.path.getsize(f) < 3: continue
    t = pd.read_csv(f)
    k = set(map(tuple, t[key].astype(str).values)) if len(t) else set()
    r = pd.to_numeric(t.R, errors="coerce")
    rows.append(dict(variant=v, trades=len(t), d_trades=len(t) - len(base), usd_1k=round(r.sum() * 1000), d_usd=round((r.sum() - base.R.sum()) * 1000),
                     avg_R=round(r.mean(), 3), win=round((t.net > 0).mean(), 3), exact_copy=(k == bk and abs(t.net.sum() - base.net.sum()) < 0.01), same_entries=(k == bk), changed=len(k ^ bk)))
o = pd.DataFrame(rows).sort_values("d_usd", key=abs, ascending=False)
print(f"defaults {y}: trades {len(base)}, $1k-risk {round(base.R.sum()*1000)}, avg_R {round(base.R.mean(),3)}")
print(o.to_string(index=False)); o.to_csv(f"{d}/../screen_{y}_ranking.csv", index=False)
