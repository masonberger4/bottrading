"""Phase 1 screen: current+defaults on 2019-2026, every other variant of the first half on 2021 only.
Phase 2 (argv[1] = file with variant names, one per line): those variants on 2019-2022 (then 2023-2026 with 'check')."""
import os, sys
os.environ["MENTORSHIP_SRC"] = "databento"
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
import pandas as pd
from mentorship import study as S
if __name__ == "__main__":
    out = Path("runs/mentorship/shard_laptop"); cache = out / "dec_jobs"; cache.mkdir(parents=True, exist_ok=True)
    allv = list(S.DECISIONS)
    prio = [x for x in allv if x in ("current", "defaults") or x.startswith(("CG", "TT-", "NEWS-", "DXY"))]
    first = prio + [v for v in allv[: len(allv) // 2] if v not in prio]
    if len(sys.argv) > 1:
        names = [l.strip() for l in open(sys.argv[1]) if l.strip()]
        yrs = range(2019, 2027) if (len(sys.argv) > 2 and sys.argv[2] == "check") else range(2019, 2023)
        jobs = [(5, y, v) for v in names for y in yrs]
    else:
        jobs = [(5, y, v) for v in ("current", "defaults") for y in range(2019, 2027)] + [(5, 2021, v) for v in first if v not in ("current", "defaults")]
    S._bias_cache(5, kw=S.B.table_kw(S.Params()))
    path = lambda j: cache / "{}m_{}_{}.csv".format(*j)
    todo = [j for j in jobs if not path(j).exists()]
    with ProcessPoolExecutor(4) as ex:
        futs = {ex.submit(S._dec_job, j): j for j in todo}
        for k, f in enumerate(as_completed(futs), 1):
            j = futs[f]; f.result().to_csv(path(j), index=False); print(f"{k}/{len(todo)} {j}", flush=True)
