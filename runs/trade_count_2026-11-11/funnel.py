"""Trade-count funnel: ES 5m databento, $1,000 risk, 2019-26, defaults (and single-switch variants given on the command line).
Keeps each run's trades and its skips (day / session blocks with reasons) so we can see where sessions are lost.
Run from the engine worktree:  python C:/Users/mason/bottrading/runs/trade_count_2026-11-11/funnel.py name=overrides ...
e.g. wd_off="dict(week_done_on_draw='off')". Resumable: finished jobs are cached."""
import os, sys
os.environ["MENTORSHIP_SRC"] = "databento"
sys.path.insert(0, os.getcwd())
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
import pandas as pd

OUT = Path(os.environ.get("FUNNEL_OUT", "C:/Users/mason/bottrading/runs/trade_count_2026-11-11/out"))
YEARS = [int(y) for y in os.environ.get("FUNNEL_YEARS", "2019,2020,2021,2022,2023,2024,2025,2026").split(",")]


def job(j):
    from mentorship import study as S
    from mentorship import backtest as B
    tf, year, name, kw = j
    S.DEC_BASE["risk_dollars"] = 1000.0
    S.DECISIONS[name] = kw
    cap = {}
    run0 = B.run

    def run(*a, **k):                      # keep the main book's attrs (skips, days)
        t = run0(*a, **k)
        cap.setdefault("attrs", t.attrs)
        return t
    B.run = run
    from collections import Counter
    from mentorship import strategy as ST
    ST.FUNNEL = Counter()                  # strategy's own setup funnel (stage keys "1_..." and rejections "x_...")
    t = S._dec_job((tf, year, name))
    pd.Series(ST.FUNNEL, dtype="int64").sort_values(ascending=False).to_csv(OUT / f"funnel_{name}_{year}.csv", header=["n"])
    at = cap.get("attrs", {})
    sk = pd.DataFrame(at.get("skips", []), columns=["day", "symbol", "stage", "reason"][:len(at["skips"][0])] if at.get("skips") else ["day", "symbol", "stage", "reason"])
    days = at.get("days")
    nd = days if isinstance(days, int) else (len(days) if days is not None else -1)
    return t, sk, nd


if __name__ == "__main__":
    variants = {"defaults": {}}
    for a in sys.argv[1:]:
        n, v = a.split("=", 1); variants[n] = eval(v)
    OUT.mkdir(parents=True, exist_ok=True)
    jobs = [(5, y, n, kw) for n, kw in variants.items() for y in YEARS]
    todo = [j for j in jobs if not (OUT / f"trades_{j[2]}_{j[1]}.csv").exists()]
    print(len(jobs), "jobs,", len(todo), "to do", flush=True)
    from mentorship import study as S
    S._bias_cache(5, kw=S.B.table_kw(S.Params()))          # build the (new-data) bias table once, before the workers
    with ProcessPoolExecutor(4) as ex:
        futs = {ex.submit(job, j): j for j in todo}
        for k, f in enumerate(as_completed(futs), 1):
            j = futs[f]
            try:
                t, sk, nd = f.result()
                sk.to_csv(OUT / f"skips_{j[2]}_{j[1]}.csv", index=False)
                t.to_csv(OUT / f"trades_{j[2]}_{j[1]}.csv", index=False)
                print(f"{k}/{len(todo)} {j[2]} {j[1]}: {len(t)} trades, {len(sk)} skips, days {nd}", flush=True)
            except Exception as e:
                import traceback; traceback.print_exc()
                print(f"{k}/{len(todo)} {j[2]} {j[1]} FAILED {type(e).__name__}: {e}", flush=True)
