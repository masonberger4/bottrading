"""Build the feature table for every day 2019-2026 at 09:30, 09:45 and 10:00, and at ICT's call time on his days."""
import sys, glob, numpy as np, pandas as pd
from pathlib import Path
from feat import Mkt

HERE = Path(__file__).parent
OUT = HERE / "out"; OUT.mkdir(exist_ok=True)


def mins(x):
    h, m = str(x).split(":"); return int(h) * 60 + int(m)


def main():
    M = {s: Mkt(s) for s in ("NQ", "ES")}
    rows = []
    for s, m in M.items():
        for d in m.dates:
            if d.year < 2019:
                continue
            for T in (570, 585, 600):
                f = m.feats(d, T)
                if f is None:
                    continue
                f["sym"] = s
                f["R_long"] = m.plain(d, T, 1); f["R_short"] = m.plain(d, T, -1)
                f["mv1000"] = m.move(d, T, 600) if T < 600 else np.nan
                f["mv1130"] = m.move(d, T, 690); f["mv1600"] = m.move(d, T, 959)
                rows.append(f)
        print(s, len(rows), flush=True)
    pd.DataFrame(rows).to_csv(OUT / "days.csv", index=False)

    # his calls, features at his call time
    C = []
    for fn in sorted(glob.glob(str(HERE.parent / "ict_calls_2026-11-17" / "calls_*_scored.csv"))):
        c = pd.read_csv(fn, sep="|"); C.append(c)
    C = pd.concat(C, ignore_index=True)
    C["sym"] = C["sym"].fillna("NQ")
    rows = []
    for r in C.itertuples():
        d = pd.Timestamp(r.date).date(); T = mins(r.ref)
        row = dict(new=int(not str(r.id)[1:3].isdigit()), id=r.id, date=r.date, sym=r.sym, ref=r.ref, T=T, side=1 if r.dir == "up" else -1, end_day=r.end_day,
                   end=r.end, before=r.before, win=r.win_end, target=r.target, what=r.what)
        same_day = r.end_day == 0 and 420 <= T <= 900
        row["same_day"] = int(same_day)
        if same_day and r.sym in M and d in M[r.sym].k:
            f = M[r.sym].feats(d, T)
            if f:
                row.update({k: v for k, v in f.items() if k not in ("date", "T")})
                row["R_his"] = M[r.sym].plain(d, max(T, 570), row["side"]) if T < 690 else np.nan
        rows.append(row)
    pd.DataFrame(rows).to_csv(OUT / "calls_feats.csv", index=False)
    print("calls", len(rows))


if __name__ == "__main__":
    main()
