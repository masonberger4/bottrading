"""Replication check runner: one year of the engine (5m databento, $1,000 risk) on ES or NQ, keeping the trades, the
day / session skips and a PER-DAY setup funnel (strategy.FUNNEL deltas), so each of ICT's video trades can be lined up
with what the engine did that day.  Run from the engine worktree (mentorship branch):
    python runs/ict_replication_2026-11-13/trace_run.py 2023 ES defaults "{}" OUTDIR
    python runs/ict_replication_2026-11-13/trace_run.py 2023 NQ open "dict(week_done_on_draw='off', ...)" OUTDIR
NQ is run the way study._dec_job runs the partner book (es_pt scaled by the price ratio, ES as the SMT partner)."""
import os, sys, time
os.environ["MENTORSHIP_SRC"] = "databento"
sys.path.insert(0, os.getcwd())
from collections import Counter
from dataclasses import replace
import pandas as pd
from mentorship import study as S, backtest as B, strategy as ST

year, sym, name = int(sys.argv[1]), sys.argv[2], sys.argv[3]
kw = eval(sys.argv[4]) if len(sys.argv) > 4 else {}
out = sys.argv[5] if len(sys.argv) > 5 else "."
S.DEC_BASE["risk_dollars"] = 1000.0
ST.FUNNEL = Counter()
rows, cap = [], {}
run_day0, run0 = B.run_day, B.run


def run_day(*a, **k):
    before = Counter(ST.FUNNEL)
    r = run_day0(*a, **k)
    d = k["df"].index[-1].date() if "df" in k else a[0].index[-1].date()
    for key, n in (ST.FUNNEL - before).items():
        rows.append((str(d), k.get("symbol", ""), key, n))
    return r


def run(*a, **k):
    t = run0(*a, **k)
    cap.setdefault("attrs", t.attrs)
    return t


B.run_day, B.run = run_day, run
t0 = time.time()
tf = 5
if sym == "ES":
    S.DECISIONS[name] = kw
    t = S._dec_job((tf, year, name))
else:
    df, pa = B.load("ES", tf, source="databento"), B.load("NQ", tf, source="databento")
    a, b = pd.Timestamp(f"{year}-01-01", tz=B.NY), pd.Timestamp(f"{year + 1}-01-01", tz=B.NY)
    lo = a - pd.Timedelta(days=45)
    p = replace(ST.Params(), **{**S.DEC_BASE, **kw})
    q = replace(p, es_pt=round(p.es_pt * float(pa.close.median() / df.close.median()), 2))
    t = B.run(pa[(pa.index >= lo) & (pa.index < b)], tf, "NQ", q, df[(df.index >= lo) & (df.index < b)],
              meta=B.load_meta("NQ", tf, "databento"), lock_cuts={} if p.draw_lock == "off" else None)
    if len(t):
        t = t[pd.to_datetime(t.entry_time.astype(str).str[:10]) >= f"{year}-01-01"].copy()
tag = f"{sym}_{name}_{year}"
t.to_csv(f"{out}/trades_{tag}.csv", index=False)
pd.DataFrame(cap.get("attrs", {}).get("skips", [])).to_csv(f"{out}/skips_{tag}.csv", index=False)
pd.DataFrame(rows, columns=["day", "symbol", "key", "n"]).to_csv(f"{out}/funnel_{tag}.csv", index=False)
print(tag, len(t), "trades", round(time.time() - t0), "s", flush=True)
