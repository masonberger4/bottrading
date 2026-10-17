"""Rule-by-rule study: each optional rule switched on alone and all together, on SPY, QQQ
and the one-instrument-per-session combination, plus the random-walk control.

    python -m mentorship.study            # SPY/QQQ (Schwab)
    python -m mentorship.study --index    # SPX/NDX index CFDs since 2019 (HistData)
"""
from __future__ import annotations

import json
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from dataclasses import replace

import pandas as pd

from . import backtest as B
from .strategy import Params

VARIANTS = {
    "base": {},
    "require_htf": dict(require_htf=True),
    "trail": dict(trail=True),
    "adds": dict(adds=(0.5, 0.33)),
    "weekly_bias": dict(weekly_bias=True),
    "sd_targets": dict(sd_targets=True),
    "wick_levels": dict(wick_levels=True),
    "all_but_htf": dict(trail=True, adds=(0.5, 0.33), weekly_bias=True, sd_targets=True, wick_levels=True),
    "all": dict(require_htf=True, trail=True, adds=(0.5, 0.33), weekly_bias=True, sd_targets=True,
                wick_levels=True),
}


def _real(job):
    tf, name = job
    spy, qqq = B.load("SPY", tf), B.load("QQQ", tf)
    q_pt = round(0.10 * qqq.close.median() / spy.close.median(), 4)
    p = replace(Params(), **VARIANTS[name])
    a = B.run(spy, tf, "SPY", p, qqq)
    b = B.run(qqq, tf, "QQQ", replace(p, es_pt=q_pt), spy)
    out = {"SPY": a, "QQQ": b, "combined": B.combine(a, b)}
    for k, v in out.items():
        if len(v):
            v["variant"], v["tf"], v["book"] = name, tf, k
    return pd.concat([v for v in out.values() if len(v)], ignore_index=True) if any(len(v) for v in out.values()) else pd.DataFrame()


def _rw(job):
    tf, seed, name = job
    x, y = B.synthetic(tf=tf, seed=200 + seed)
    t = B.run(x, tf, "RW", replace(Params(es_pt=0.0913), **VARIANTS[name]), y)
    if len(t):
        t["variant"], t["tf"], t["seed"] = name, tf, seed
    return t


def main(out="runs/mentorship"):
    jobs = [(tf, v) for tf in (5, 1) for v in VARIANTS]
    rw = [(5, s, v) for s in range(12) for v in ("base", "all_but_htf")] + \
         [(1, s, v) for s in range(3) for v in ("base", "all_but_htf")]
    with ProcessPoolExecutor(6) as ex:
        real = pd.concat(list(ex.map(_real, jobs)), ignore_index=True)
        rand = pd.concat([t for t in ex.map(_rw, rw) if len(t)], ignore_index=True)
    real.to_csv(f"{out}/study_trades.csv", index=False)
    rand.to_csv(f"{out}/study_random_walk.csv", index=False)
    rep = {"real": {f"{tf}m/{b}/{v}": B.stats(g) for (tf, b, v), g in real.groupby(["tf", "book", "variant"])},
           "random_walk": {f"{tf}m/{v}": dict(B.stats(g), R_se=round(g.R.std() / len(g) ** .5, 3))
                           for (tf, v), g in rand.groupby(["tf", "variant"])}}
    base = real[(real.variant == "base") & (real.book == "SPY")]
    for col in ("setup", "day_type", "news", "macro", "htf", "unicorn", "smt", "wbias", "side"):
        rep[f"SPY_base_by_{col}"] = {f"{tf}m/{k}": B.stats(g) for (tf, k), g in base.groupby(["tf", base[col].astype(str)])}
    with open(f"{out}/study.json", "w") as f:
        json.dump(rep, f, indent=1, default=str)
    return rep



# --- index CFD study (HistData SPX / NDX, 2019 onward; see histdata.py) -----------------
# Sizing is in micro futures: MES $5/pt (lot 5 units), MNQ $2/pt (lot 2 units). Costs per
# side are one tick of slippage plus $0.62 commission per contract, in points per unit.
INDEX = {"SPX": dict(es_pt=1.0, lot=5, cost_per_share=round((0.25 * 5 + 0.62) / 5, 4)),
         "NDX": dict(lot=2, cost_per_share=round((0.25 * 2 + 0.62) / 2, 4))}
IVARIANTS = dict(VARIANTS, no_bias=dict(use_bias=False), no_day_filter=dict(day_filter=False))


def _index_job(job):
    tf, sym, name, year = job
    other = "NDX" if sym == "SPX" else "SPX"
    df, pa = B.load(sym, tf, source="histdata"), B.load(other, tf, source="histdata")
    kw = dict(INDEX[sym], max_notional=1e12)
    if sym == "NDX":   # NQ handles: scale the ES-point tolerances by the NDX/SPX price ratio
        spx = pa if other == "SPX" else df
        kw["es_pt"] = round(float(df.close.median() / spx.close.median()), 2)
    a, b = pd.Timestamp(f"{year}-01-01", tz=B.NY), pd.Timestamp(f"{year + 1}-01-01", tz=B.NY)
    lo = a - pd.Timedelta(days=45)                  # warm-up: prior days' levels and history
    t = B.run(df[(df.index >= lo) & (df.index < b)], tf, sym, replace(Params(), **kw, **IVARIANTS[name]),
              pa[(pa.index >= lo) & (pa.index < b)])
    if len(t):
        t = t[pd.to_datetime(t.entry_time.astype(str).str[:10]) >= f"{year}-01-01"].copy()
        t["variant"], t["tf"], t["year"] = name, tf, year
    return t


def main_index(out="runs/mentorship", variants=None, tfs=(5, 1), workers=6):
    variants = variants or list(IVARIANTS)
    years = range(2019, 2027)
    jobs = [(tf, s, v, y) for tf in tfs for v in variants for s in INDEX for y in years]
    jobs.sort(key=lambda j: (j[0] == 1, j[2] != "base"))     # quick 5-min first, then 1-min base
    cache = Path(out) / "index_jobs"                          # one file per job: resumable
    cache.mkdir(parents=True, exist_ok=True)
    path = lambda j: cache / "{}m_{}_{}_{}.csv".format(*j)
    todo = [j for j in jobs if not path(j).exists()]
    with ProcessPoolExecutor(workers) as ex:
        futs = {ex.submit(_index_job, j): j for j in todo}
        for k, f in enumerate(as_completed(futs), 1):
            j = futs[f]
            f.result().to_csv(path(j), index=False)
            print(f"{k}/{len(todo)} {j}", flush=True)
    parts = [pd.read_csv(path(j)) for j in jobs if path(j).exists() and path(j).stat().st_size > 2]
    t = pd.concat([x for x in parts if len(x)], ignore_index=True)
    books = []
    for (tf, v), g in t.groupby(["tf", "variant"]):
        books.append(B.combine(g[g.symbol == "SPX"], g[g.symbol == "NDX"]).assign(book="combined"))
    t = pd.concat([t.assign(book=t.symbol)] + books, ignore_index=True)
    t.to_csv(f"{out}/index_trades.csv", index=False)
    rep = {"all": {f"{tf}m/{b}/{v}": B.stats(g) for (tf, b, v), g in t.groupby(["tf", "book", "variant"])}}
    base = t[(t.variant == "base") & (t.book != "combined")]
    for col in ("setup", "day_type", "news", "macro", "htf", "unicorn", "smt", "wbias", "side", "year", "swept"):
        rep[f"base_by_{col}"] = {f"{tf}m/{k}": B.stats(g) for (tf, k), g in base.groupby(["tf", base[col].astype(str)])}
    with open(f"{out}/index_study.json", "w") as f:
        json.dump(rep, f, indent=1, default=str)
    return t, rep


if __name__ == "__main__":
    import sys
    if "--index" in sys.argv:
        _, rep = main_index()
        for k, v in rep["all"].items():
            print(k, v)
        raise SystemExit
    rep = main()
    for k, v in rep["real"].items():
        print(k, v)
    for k, v in rep["random_walk"].items():
        print("RW", k, v)


# --- AM model on S&P 500 levels, traded as SPY ------------------------------------------
# Signals from the SPX index CFD (real midnight open), P&L as SPY: a unit is $1 per SPX
# point = 10 SPY shares, so 1 cent per share each way = 0.10 points per unit per side,
# commission $0, buying power $400k (4x a $100k account).
AM_SPY = dict(es_pt=1.0, lot=1, cost_per_share=0.10, max_notional=400_000.0, pm=(0, 0),
              skip_news=True)


def _am_job(job):
    tf, year = job
    df, pa = B.load("SPX", tf, source="histdata"), B.load("NDX", tf, source="histdata")
    a, b = pd.Timestamp(f"{year}-01-01", tz=B.NY), pd.Timestamp(f"{year + 1}-01-01", tz=B.NY)
    lo = a - pd.Timedelta(days=45)
    t = B.run(df[(df.index >= lo) & (df.index < b)], tf, "SPX", replace(Params(), **AM_SPY),
              pa[(pa.index >= lo) & (pa.index < b)])
    if len(t):
        t = t[pd.to_datetime(t.entry_time.astype(str).str[:10]) >= f"{year}-01-01"].copy()
        t["tf"], t["year"] = tf, year
    return t


def main_am_spy(out="runs/mentorship", workers=6, tfs=(1, 5)):
    jobs = [(tf, y) for tf in tfs for y in range(2019, 2027)]
    with ProcessPoolExecutor(workers) as ex:
        t = pd.concat([x for x in ex.map(_am_job, jobs) if len(x)], ignore_index=True)
    t.to_csv(f"{out}/am_spy_trades{'' if tuple(tfs) == (1, 5) else '_' + '_'.join(map(str, tfs))}.csv", index=False)
    return t
