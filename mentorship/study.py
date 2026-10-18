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


# --- daily HTF bias (htf.py) on the AM-as-SPY setup ---------------------------------------
def _bias_job(job):
    tf, year, mode = job
    df, pa = B.load("SPX", tf, source="histdata"), B.load("NDX", tf, source="histdata")
    a, b = pd.Timestamp(f"{year}-01-01", tz=B.NY), pd.Timestamp(f"{year + 1}-01-01", tz=B.NY)
    lo = a - pd.Timedelta(days=120)                 # HTF arrays look back 60 trading days
    p = replace(Params(), **dict(AM_SPY, pm=Params().pm), htf_bias=mode)
    t = B.run(df[(df.index >= lo) & (df.index < b)], tf, "SPX", p, pa[(pa.index >= lo) & (pa.index < b)])
    if len(t):
        t = t[pd.to_datetime(t.entry_time.astype(str).str[:10]) >= f"{year}-01-01"].copy()
        t["tf"], t["year"], t["mode"] = tf, year, mode
    return t


def main_bias(out="runs/mentorship", workers=6, tfs=(5, 1), modes=("off", "react", "draw", "pd", "combo")):
    jobs = [(tf, y, m) for tf in tfs for m in modes for y in range(2019, 2027)]
    with ProcessPoolExecutor(workers) as ex:
        t = pd.concat([x for x in ex.map(_bias_job, jobs) if len(x)], ignore_index=True)
    t.to_csv(f"{out}/bias_trades.csv", index=False)
    return t


# --- the 23 decisions: recommended defaults vs each contradiction -------------------------
# SPX signals, SPY pricing (AM_SPY costs), AM and PM sessions, 2019-2026.
CURRENT = dict(mt_mode="range", exit_mode="before", min_draw_pts=0.0, leg_pd=0.0, am_exit=0,
               breaker_zone="range")                # the engine before the decisions
DECISIONS = {
    "current": CURRENT,
    "defaults": {},
    "D1_am_from_1000": dict(am=(600, 660)),
    "D2_sb_only": dict(sb_only=True),
    "D2_sb_only_room5": dict(sb_only=True, min_draw_pts=5.0),
    "D3_mss_wick": dict(mss_mode="wick"),
    "D4_mt_range": dict(mt_mode="range"),
    "D5_exit_before": dict(exit_mode="before"),
    "D6_breaker_range": dict(breaker_zone="range"),
    "D7_pm_from_1400": dict(pm=(840, 950)),
    "D8_fomc_pm_1445": dict(fomc_pm_from=885),
    "D8_nfp_thu": dict(nfp_thu=True),
    "D9_skip_cpi": dict(skip_cpi=True),
    "D11_entry_ce": dict(entry="ce"),
    "D12_leg_062": dict(leg_pd=0.62),
    "D12_leg_off": dict(leg_pd=0.0),
    "D13_partial_08": dict(partial=0.8),
    "D14_trail": dict(trail=True),
    "D16_am_exit_1100": dict(am_exit=660),
    "D16_am_hold": dict(am_exit=0),
    "D16_pm_done_1500": dict(pm_done_by=900),
    "D17_pivot_1": dict(pivot_n=1),
    "D17_pivot_2": dict(pivot_n=2),
    "D18_reentry_half": dict(reentry_half=True),
    "D19_no_pm_after_win": dict(no_pm_after_am_win=True),
    "D19_max_3_week": dict(max_trades_week=3),
    "D20_skip_monday": dict(skip_monday=True),
    "L15_room_off": dict(min_draw_pts=0.0),
    "X6_fvg_abort": dict(fvg_abort=True),
    "X9_time_stop_10": dict(time_stop_min=10),
    "combo_sb_mt_range": dict(sb_only=True, mt_mode="range"),
    "combo_sb_mt_range_nfp_thu": dict(sb_only=True, mt_mode="range", nfp_thu=True),
    "D12_leg_at_arm": dict(leg_pd_at="arm"),
    "A_ifvg_entries": dict(ifvg_entries=True),
    "A_fvg_targets": dict(fvg_targets=True),
    "A_cisd": dict(mss_cisd=True),
    "A_globex_pool": dict(globex_pool=True),
    "A_all_arrays": dict(ifvg_entries=True, fvg_targets=True, globex_pool=True),
    "D21_gaps_monday": dict(gap_mode="monday"),
    "D21_org_off": dict(org_days=0),
    "ORG_close_1600": dict(org_close=960),
    "OR_60min": dict(or_minutes=60),
    "OR_off": dict(or_minutes=0),
    "conf_2tf": dict(conf_min_n=2),
    "conf_3tf": dict(conf_min_n=3),
    "conf_4tf": dict(conf_min_n=4),
    "conf_4h_up": dict(conf_min_top="4h"),
    "conf_daily_up": dict(conf_min_top="D"),
    "best5_filters": dict(sb_only=True, mt_mode="range", nfp_thu=True, htf_bias="combo"),
    "best5_additive": dict(mt_mode="range", nfp_thu=True, gap_mode="monday", ifvg_entries=True,
                           htf_bias="combo"),
    "best5_all": dict(sb_only=True, mt_mode="range", nfp_thu=True, gap_mode="monday",
                      ifvg_entries=True, htf_bias="combo"),
    "TF_entry_5m": dict(entry_tf="5m"),
    "TF_nested_5m": dict(entry_tf="nested"),
    "HTF_targets_off": dict(htf_targets=()),
    "CE_hold_on": dict(ce_hold=True),
    "PRE_0700": dict(pre_0700=True),
    "PRE_0900": dict(pre_0900=True),
    "PRE_post_news": dict(post_news=True),
    "PRE_ma_deuce": dict(ma_deuce=True),
    "EP07_stop": dict(ep07_stop=True),
    "EP07_body_exit": dict(ep07_body_exit=True),
    "EP07_trail": dict(ep07_trail=True),
    "EP07_all": dict(ep07_stop=True, ep07_body_exit=True, ep07_trail=True),
    "HTF_far_edge": dict(htf_far_edge=True),
    "POOL_prev_week": dict(pool_prev_week=True),
    "POOL_prev_month": dict(pool_prev_month=True),
    "POOL_swings": dict(pool_swings=True),
    "POOL_all": dict(pool_prev_week=True, pool_prev_month=True, pool_swings=True),
    "SB_off": dict(sb_model=False),
    "SB_only": dict(sb_model=True, am=(0, 0), pm=(0, 0)),
    "SB_room10": dict(sb_room_pts=10.0),
    "SB_runner": dict(sb_runner=True),
    "BEGINNER_news": dict(nfp_day=False, nfp_week_block=True, nfp_thu=False, fomc_pm_from=0),
    "BEGINNER_no_reverse": dict(reverse_after_loss=False),
    "BEGINNER_room10": dict(min_draw_pts=10.0),
    "BEGINNER_all": dict(nfp_day=False, nfp_week_block=True, nfp_thu=False, fomc_pm_from=0,
                         reverse_after_loss=False, min_draw_pts=10.0, nwog_days=0, nwog_keep=5),
    "NWOG_last5": dict(nwog_days=0, nwog_keep=5),
    "NWOG_last4": dict(nwog_days=0, nwog_keep=4),
    "NWOG_20d": dict(nwog_days=20),
    "wick_levels_off": dict(wick_levels=False),
    "DAY_neutral_skip": dict(neutral_skip=True),
    "DAY_three_day_rule": dict(three_day_rule=True),
    "DAY_tgif": dict(tgif=True),
    "X_pd3_exit": dict(pd3_exit=True),
    "X_sd_targets": dict(sd_targets=True, sd_levels=(0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4, 4.5)),
    "TD_all4": dict(topdown=("D", "4h", "1h", "15m")),
    "TD_3of4": dict(topdown=("D", "4h", "1h", "15m"), topdown_min=3),
    "TD_D_1h": dict(topdown=("D", "1h")),
    "SMT_1": dict(smt_min=1),
    "SMT_2": dict(smt_min=2),
    "bias_react": dict(htf_bias="react"),
    "bias_draw": dict(htf_bias="draw"),
    "bias_pd": dict(htf_bias="pd"),
    "bias_combo": dict(htf_bias="combo"),
}
DEC_BASE = dict(AM_SPY, pm=Params().pm, skip_news=False)


import os
SRC = os.environ.get("MENTORSHIP_SRC", "histdata")      # "histdata" (SPX/NDX CFDs) or "databento"
SYMS = {"histdata": ("SPX", "NDX"), "merged": ("SPX", "NDX"), "databento": ("ES", "NQ", "YM")}[SRC]


def _bias_cache(tf: int) -> pd.DataFrame:
    from . import htf
    f = Path(f"runs/mentorship/htf_table_{SRC}_{tf}m.csv")
    if not f.exists():
        htf.table(B.load(SYMS[0], tf, source=SRC)).to_csv(f)
    t = pd.read_csv(f, index_col=0)
    t.index = pd.to_datetime(t.index).date
    return t


def _dec_job(job):
    tf, year, name = job
    df, pa = B.load(SYMS[0], tf, source=SRC), B.load(SYMS[1], tf, source=SRC)
    a, b = pd.Timestamp(f"{year}-01-01", tz=B.NY), pd.Timestamp(f"{year + 1}-01-01", tz=B.NY)
    lo = a - pd.Timedelta(days=45)
    p = replace(Params(), **{**DEC_BASE, **DECISIONS[name]})
    p2 = None
    if len(SYMS) > 2:
        p2 = B.load(SYMS[2], tf, source=SRC)
        p2 = p2[(p2.index >= lo) & (p2.index < b)]
    t = B.run(df[(df.index >= lo) & (df.index < b)], tf, SYMS[0], p, pa[(pa.index >= lo) & (pa.index < b)],
              partner2=p2,
              bias_table=_bias_cache(tf))
    if len(t):
        t = t[pd.to_datetime(t.entry_time.astype(str).str[:10]) >= f"{year}-01-01"].copy()
        t["tf"], t["year"], t["variant"] = tf, year, name
    return t


def main_decisions(out="runs/mentorship", workers=6, tfs=(5, 1), variants=None, tag="dec"):
    variants = variants or list(DECISIONS)
    for tf in tfs:
        _bias_cache(tf)
    jobs = [(tf, y, v) for tf in tfs for v in variants for y in range(2019, 2027)]
    jobs.sort(key=lambda j: (j[0] == 1, j[2] not in ("current", "defaults")))
    cache = Path(out) / f"{tag}_jobs"
    cache.mkdir(parents=True, exist_ok=True)
    path = lambda j: cache / "{}m_{}_{}.csv".format(*j)
    todo = [j for j in jobs if not path(j).exists()]
    with ProcessPoolExecutor(workers) as ex:
        futs = {ex.submit(_dec_job, j): j for j in todo}
        for k, f in enumerate(as_completed(futs), 1):
            j = futs[f]
            f.result().to_csv(path(j), index=False)
            print(f"{k}/{len(todo)} {j}", flush=True)
    parts = [pd.read_csv(path(j)) for j in jobs if path(j).exists() and path(j).stat().st_size > 2]
    t = pd.concat([x for x in parts if len(x)], ignore_index=True)
    t.to_csv(f"{out}/{tag}_trades.csv", index=False)
    return t
