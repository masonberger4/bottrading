"""After switch.py: the engine's own loaders return the fixed-roll series (and read the parquets, not the CSVs)."""
import sys, os, pandas as pd
sys.path.insert(0, ".worktrees/scb")
from mentorship import backtest as bt
N = "data/mentorship/roll_fix_2026-11-10/"
for S in ["ES", "NQ", "YM"]:
    for mins in (1, 5):
        df = bt.load(S, mins, source="databento"); m = bt.load_meta(S, mins)
        ref, refm = pd.read_parquet(N + f"{S}_{mins}min_db.parquet"), pd.read_parquet(N + f"{S}_{mins}min_dbmeta.parquet")
        ok = df.equals(ref) and m.index.equals(ref.index) and (m.adj - refm.adj).abs().max() == 0
        raw = bt.load_raw(S, mins)
        okr = (raw.close + m.adj.reindex(raw.index) - df.close.reindex(raw.index)).abs().max() < 1e-9
        days = bt.days(df, mins, close=975)
        print(S, mins, "min: load == fixed", ok, "| raw + adj == adjusted", okr, "| sessions", len(days), "| rolls", int(m.roll.sum()), flush=True)
    csv, pq = f"data/mentorship/{S}_1min_db.csv", f"data/mentorship/{S}_1min_db.parquet"
    print("  parquet newer than csv:", os.path.getmtime(pq) >= os.path.getmtime(csv))
