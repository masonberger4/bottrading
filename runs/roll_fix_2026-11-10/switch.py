"""Switch the engine's ES / NQ / YM databento files to the fixed-roll series (or back with --undo).

Switch: moves the current files to data/mentorship/backup_pre_rollfix_2026-11-10/, then writes the new CSVs (same layout as
databento_data._write) from data/mentorship/roll_fix_2026-11-10/ and copies its parquets next to them, with parquet times
set after the CSVs so backtest._read / load_meta read the parquets as they are.
Undo: moves the backed-up files back (the fixed-roll files stay in roll_fix_2026-11-10/).
"""
import os, sys, shutil, time
import pandas as pd

D = "data/mentorship/"; N = D + "roll_fix_2026-11-10/"; B = D + "backup_pre_rollfix_2026-11-10/"
NAMES = ["1min_db.csv", "1min_db.parquet", "1min_dbmeta.parquet", "1min_dbraw.csv", "1min_dbraw.parquet",
         "5min_db.csv", "5min_db.parquet", "5min_dbmeta.parquet"]
SYMS = ["ES", "NQ", "YM"]
P = lambda *a: print(*a, flush=True)


def undo():
    for S in SYMS:
        for n in NAMES:
            f = f"{S}_{n}"
            if os.path.exists(B + f):
                if os.path.exists(D + f): os.remove(D + f)
                shutil.move(B + f, D + f)
            elif os.path.exists(D + f):          # a file the old set never had (NQ / YM dbraw.parquet)
                os.remove(D + f)
    P("restored the pre-rollfix files")


def switch():
    if os.path.exists(B): sys.exit(f"{B} already exists: switched before? run --undo first")
    os.makedirs(B)
    for S in SYMS:
        for n in NAMES:
            if os.path.exists(D + f"{S}_{n}"): shutil.move(D + f"{S}_{n}", B + f"{S}_{n}")
        a, m = pd.read_parquet(N + f"{S}_1min_db.parquet"), pd.read_parquet(N + f"{S}_1min_dbmeta.parquet")
        raw = pd.read_parquet(N + f"{S}_1min_dbraw.parquet")
        a5, m5 = pd.read_parquet(N + f"{S}_5min_db.parquet"), pd.read_parquet(N + f"{S}_5min_dbmeta.parquet")
        for x in (a, raw, a5): x.index.name = "ts_event"
        raw.assign(instrument_id=m.instrument_id).to_csv(D + f"{S}_1min_dbraw.csv")
        a.assign(instrument_id=m.instrument_id, roll=m.roll, adj=m.adj).to_csv(D + f"{S}_1min_db.csv")
        a5.assign(instrument_id=m5.instrument_id, adj=m5.adj, roll=m5.roll).to_csv(D + f"{S}_5min_db.csv")
        time.sleep(1)
        now = time.time()
        for n in ["1min_db.parquet", "1min_dbmeta.parquet", "1min_dbraw.parquet", "5min_db.parquet", "5min_dbmeta.parquet"]:
            shutil.copyfile(N + f"{S}_{n}", D + f"{S}_{n}")
            os.utime(D + f"{S}_{n}", (now, now))
        P(S, "switched", len(a), "1-min bars,", int(m.roll.sum()), "rolls")


if __name__ == "__main__":
    undo() if "--undo" in sys.argv else switch()
