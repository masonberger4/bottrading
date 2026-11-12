"""Summarise the funnel outputs: trades / $ by year, and the skips by stage and reason (first reason per day)."""
import sys, pandas as pd
from pathlib import Path
O = Path("C:/Users/mason/bottrading/runs/trade_count_2026-11-11/out")
pd.set_option("display.width", 220); pd.set_option("display.max_rows", 200)
for v in sys.argv[1:] or ["defaults", "wd_off"]:
    T = pd.concat([pd.read_csv(f).assign(y=int(f.stem[-4:])) for f in sorted(O.glob(f"trades_{v}_*.csv")) if f.stat().st_size > 2])
    K = pd.concat([pd.read_csv(f).assign(y=int(f.stem[-4:])) for f in sorted(O.glob(f"skips_{v}_*.csv")) if f.stat().st_size > 2])
    print(f"===== {v}: {len(T)} trades, ${T.net.sum():,.0f}; 2019-22 ${T[T.y <= 2022].net.sum():,.0f}, 2023-26 ${T[T.y >= 2023].net.sum():,.0f}")
    print(T.groupby("y").agg(n=("net", "size"), net=("net", "sum"), win=("net", lambda s: (s > 0).mean())).round(2).T.to_string())
    if "session" in T: print("by session:", T.session.value_counts().to_dict())
    if "setup" in T: print("by setup:", T.setup.value_counts().head(12).to_dict())
    K["day"] = pd.to_datetime(K.day).dt.date
    first = K.drop_duplicates("day")
    print("days with a skip row:", K.day.nunique(), "| rows", len(K))
    print("day-killing stage of the first skip row:"); print(first.groupby(["stage", "reason"]).size().sort_values(ascending=False).head(25).to_string())
    print("all skip rows by stage/reason (top 30):"); print(K.groupby(["stage", "reason"]).size().sort_values(ascending=False).head(30).to_string())
    print("trade days:", pd.to_datetime(T.entry_time.astype(str).str[:10]).nunique())
