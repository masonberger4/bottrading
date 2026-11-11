"""Buy ES, NQ and YM next-contract 1-minute bars for the 2 weeks before each quarterly expiry, 2019-03 to 2026-09 (31 windows).
Quoted 2026-11-10 at $4.12 (ES alone $1.57) via metadata.get_cost. Re-quotes first and stops if the total is over $4.50.
Fixes the late .v.0 rolls found in runs/data_audit_2026-11-09/README.md (finding 1)."""
import databento as db, datetime as dt, os, sys
c = db.Historical()
ROOTS = ["ES", "NQ", "YM"]
out = "data/databento_extra/roll_next_2019-26"
os.makedirs(out, exist_ok=True)
def third_fri(y, m):
    d = dt.date(y, m, 15); return d + dt.timedelta((4 - d.weekday()) % 7)
M = {3: "H", 6: "M", 9: "U", 12: "Z"}
wins = []
for y in range(2019, 2027):
    for m in (3, 6, 9, 12):
        f = third_fri(y, m)
        if f > dt.date(2026, 10, 17): continue
        ny, nm = (y, m + 3) if m < 12 else (y + 1, 3)
        for r in ROOTS:
            wins.append((f - dt.timedelta(14), f + dt.timedelta(1), f"{r}{M[nm]}{ny % 10}", ny))
kws = [dict(dataset="GLBX.MDP3", symbols=[s], stype_in="raw_symbol", schema="ohlcv-1m", start=a.isoformat(), end=b.isoformat()) for a, b, s, _ in wins]
tot = sum(c.metadata.get_cost(**k) for k in kws)
print("requote $%.4f" % tot, flush=True)
if tot > 4.5: sys.exit("price changed, stop")
n = 0
for k, (a, b, s, ny) in zip(kws, wins):
    p = f"{out}/{s}{ny}_{a}_{b}.ohlcv1m.dbn.zst"
    if os.path.exists(p): continue
    c.timeseries.get_range(**k, path=p)
    n += len(db.DBNStore.from_file(p).to_df())
print("bought", len(wins), "files, records", n, flush=True)
