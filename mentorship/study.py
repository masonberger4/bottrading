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
    out = {"SPY": a, "QQQ": b, "combined": B.combine(a, b, pick=p.smt_pick)}
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
    for col in ("setup", "day_type", "news", "macro", "htf", "unicorn", "unicorn_side", "smt", "wbias", "side"):
        rep[f"SPY_base_by_{col}"] = {f"{tf}m/{k}": B.stats(g) for (tf, k), g in base.groupby(["tf", base[col].astype(str)])}
    with open(f"{out}/study.json", "w") as f:
        json.dump(rep, f, indent=1, default=str)
    return rep



# --- index CFD study (HistData SPX / NDX, 2019 onward; see histdata.py) -----------------
# Sizing is in micro futures: MES $5/pt (lot 5 units), MNQ $2/pt (lot 2 units). Costs per
# side are one tick of slippage plus $0.62 commission per contract, in points per unit.
INDEX = {"SPX": dict(es_pt=1.0, lot=5, cost_per_share=round((0.25 * 5 + 0.62) / 5, 4)),
         "NDX": dict(lot=2, cost_per_share=round((0.25 * 2 + 0.62) / 2, 4))}
IVARIANTS = dict(VARIANTS, no_bias=dict(use_bias=False), no_day_filter=dict(day_filter=False),
                 # setups_models Ep03.11: smt_pick acts in the combined book (main_index combines)
                 **{"Ep03.11_smt_pick_leader": dict(smt_pick="leader"),
                    "Ep03.11_smt_pick_laggard": dict(smt_pick="laggard")})


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
        books.append(B.combine(g[g.symbol == "SPX"], g[g.symbol == "NDX"],
                               pick=IVARIANTS.get(v, {}).get("smt_pick", "first")).assign(book="combined"))
    t = pd.concat([t.assign(book=t.symbol)] + books, ignore_index=True)
    t.to_csv(f"{out}/index_trades.csv", index=False)
    rep = {"all": {f"{tf}m/{b}/{v}": B.stats(g) for (tf, b, v), g in t.groupby(["tf", "book", "variant"])}}
    base = t[(t.variant == "base") & (t.book != "combined")]
    for col in ("setup", "day_type", "news", "macro", "htf", "unicorn", "unicorn_side", "smt", "wbias", "side", "year", "swept"):
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
CURRENT = dict(mt_mode="range", exit_mode="before", min_draw_pts=0.0, leg_pd=0.0, am_exit=0, mgmt="t1t2", adds=(),
               breaker_zone="range",                # the engine before the decisions, pinned to the
               ob_entry="post_mss", draw_lock="off",  # pre-owner-directive entry / draw / cap / news /
               htf_resist_cap=False, news_wait="off",  # breaker-MT / risk / session-close behaviour
               breaker_mt_respect=False, breaker_mt_entry_floor=False,
               risk_dollars=1000.0, max_total_risk=2000.0, last_hour=(915, 945), flatten=960,
               sb_target_mode="fixed", price_frame="back_adjusted", round_pools=False,
               seen_from_created=False, sweep_ticks=0.0, fvg_c2_dir=False, nwog_trading_days=False,
               breaker_ll=False, breaker_cand_to="ext")   # review fix: Ep01.6 defaults pinned back
# the defaults just before the owner directives of 2026-10-18 (A/B baseline for the new defaults).
# Bug fixes it can NOT undo (no switch, by design): the London-pool look-ahead (London 02:00-05:00
# pools hidden before 05:00), the _split news-ahead holiday skip (N3.4), the M1.2 swing-low intact
# start and the mark_levels / causal roll_day fixes - so "reproduces 833350f exactly" holds on the
# tested window (ES 5m 2024 Q1), not on every window.
PRE_OWNER = dict(ob_entry="post_mss", draw_lock="off", htf_resist_cap=False, news_wait="off",
                 breaker_mt_respect=False, breaker_mt_entry_floor=False, breaker_zone="body",
                 risk_dollars=1000.0, max_total_risk=2000.0, last_hour=(915, 945), flatten=960,
                 sb_target_mode="fixed", price_frame="back_adjusted", round_pools=False,
                 seen_from_created=False, am_exit_extras=False,
                 # levels_detectors defaults that change the engine (A2 booking tick, A5 c2 check, L5 NWOG
                 # trading-day count): switched back so the golden window still reproduces 833350f
                 sweep_ticks=0.0, fvg_c2_dir=False, nwog_trading_days=False,
                 # review fix (levels_detectors): Ep01.6 breaker lower low + L1 -> H candle are defaults now
                 breaker_ll=False, breaker_cand_to="ext")
LEGACY_1PCT_2PCT = dict(risk_dollars=1000.0, max_total_risk=2000.0)   # E8 / owner #12 preset
# setups_models review: the FVG-path variants need the FVG path to trade at all - post_mss with the
# owner #9 lock and #7 cap produced 0 trades on ES 5m 2023H2, so those variants drop both too
SM_POST = dict(ob_entry="post_mss", draw_lock="off", htf_resist_cap=False)
DECISIONS = {
    "current": CURRENT,
    "defaults": {},
    "D1_am_from_1000": dict(am=(600, 660)),
    "D2_sb_only": dict(sb_only=True),
    "D2_sb_only_room5": dict(sb_only=True, min_draw_pts=5.0),
    "D3_mss_wick": dict(mss_mode="wick"),
    "D4_mt_range": dict(mt_mode="range"),
    "D5_exit_before": dict(exit_mode="before"),
    "D6_breaker_body": dict(breaker_zone="body"),   # owner #14: range is the default now
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
    "MGMT_t1t2": dict(mgmt="t1t2", adds=()),
    "SB_ladder": dict(sb_model=True, sb_mgmt="ladder"),
    "SB_only_ladder": dict(sb_model=True, sb_mgmt="ladder", am=(0, 0), pm=(0, 0)),
    "MGMT_ladder_80_20": dict(ladder_fracs=(0.8, 0.2)),
    "MGMT_trail_prior": dict(ladder_trail="prior"),
    "MGMT_trail_hit": dict(ladder_trail="hit"),
    "MGMT_be_at_t1": dict(be_on="t1"),
    "MGMT_fixed_split": dict(ladder_by_day=False),
    "MGMT_no_adds": dict(adds=()),
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
    "SB_on": dict(sb_model=True),
    "SB_only": dict(sb_model=True, am=(0, 0), pm=(0, 0)),
    "SB_room10": dict(sb_model=True, sb_room_pts=10.0),
    "SB_runner": dict(sb_model=True, sb_runner=True),
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
    # --- owner directives 2026-10-18 and the shared helpers (variant name = rule id) ---------
    "D0_pre_owner_directives": PRE_OWNER,
    "T10_last_hour_strict": dict(last_hour_strict=True),                 # #1
    "T11_flatten_1600": dict(flatten=960),
    "Ep03.24_t1_fixed5": dict(t1_fixed_pts=5.0),                         # #2
    "Ep03.24_t1_fixed5_all": dict(t1_fixed_pts=5.0, t1_fixed_all=True),
    "X14a_day_target5": dict(day_target_pts=5.0),
    "M3_sb_target_fixed": dict(sb_model=True, sb_target_mode="fixed"),
    "M3_sb_target_draw": dict(sb_model=True),
    "N7.4_year_end_off": dict(year_end="off"),                           # #3 owner (a) default = december/squaring
    "N7.4_year_end_dec_with": dict(year_end="december", year_end_map="with"),
    "N7.4_year_end_long": dict(year_end="long"),
    "N7.4_year_end_tag": dict(year_end="tag"),
    "N5_news_fixed30": dict(news_wait="fixed"),                          # #4
    "N5_news_off": dict(news_wait="off"),
    "N5_news_range_pd": dict(news_range_pd=True),
    "N5_news_no_target": dict(news_range_target=False),
    "A14_unicorn_long_only": dict(unicorn_sides="long"),                 # #5
    "A14_unicorn_short_only": dict(unicorn_sides="short"),
    "A13.3_breaker_mt_off": dict(breaker_mt_respect=False, breaker_mt_entry_floor=False),   # #6
    "A13.3_breaker_mt_no_floor": dict(breaker_mt_entry_floor=False),
    "A13.3_breaker_mt_body": dict(breaker_mt_mode="body"),
    "A13.3_breaker_mt_exit_after_t1": dict(breaker_mt_exit_after_t1=True),
    "A13.3_conf_breakers": dict(conf_breakers=True),
    "Ep02.10_resist_cap_off": dict(htf_resist_cap=False),                # #7
    "Ep02.10_resist_fvg_ob": dict(htf_resist_src=("fvg", "ob")),
    "Ep02.10_resist_live": dict(htf_resist_live=True),
    "Ep02.10_resist_room5": dict(htf_resist_min_room=5.0),
    "Ep02.5_htf_targets_30m": dict(htf_targets_30m=True),
    "Ep02.5_runner_30m": dict(runner_htf_exit="30m"),
    "X10_am_tighten": dict(am_exit_mode="tighten"),                      # #8
    "X10_am_extras_off": dict(sb_model=True, ma_deuce=True, am_exit_extras=False),
    "B3_draw_lock_off": dict(draw_lock="off"),                           # #9
    "B3_lock_neutral_both": dict(draw_lock_neutral="both"),
    "B3_lock_live_levels": dict(draw_lock_levels="live"),
    "B3_lock_no_partials": dict(draw_lock_partials=False),
    "B3_lock_relock": dict(draw_relock=True),
    "B3_lock_near_cap": dict(draw_lock_near_cap=True),
    "B3_lock_min0": dict(draw_lock_min_pts=0.0),
    "B17.4_sloppy_off": dict(sloppy_mode="off"),                         # #10 owner default = stand_aside
    "B17.4_sloppy_nfp_week": dict(sloppy_tests=("big_prev", "chop", "nfp_week")),
    "B17.4_sloppy_scalp": dict(sloppy_mode="scalp"),
    "M1.4_ob_post_mss": dict(ob_entry="post_mss"),                       # #11
    "M1.4_ob_both": dict(ob_entry="both"),
    "M1.4_ob_both_cancel": dict(ob_entry="both", ob_entry_cancel_on_mss=True),
    "M1.4_ob_px_mt": dict(ob_entry_px="mt"),
    "M1.4_ob_px_range_top": dict(ob_entry_px="range_top"),
    "M1.4_ob_arm_touch": dict(ob_arm="touch"),
    "M1.4_ob_stop_ext": dict(ob_stop="ext"),
    "M1.4_ob_adds_off": dict(ob_adds=False),
    "E8_legacy_1pct_2pct": LEGACY_1PCT_2PCT,                             # #12
    "E8_risk_equity": dict(risk_basis="equity"),
    "DATA1_back_adjusted": dict(price_frame="back_adjusted"),            # #13
    "Ep02.2_round_off": dict(round_pools=False),
    "Ep02.2_round_25": dict(round_pool_step_pts=25.0),
    "M7.1_seen_old": dict(seen_from_created=False),                      # verified bugs
    "M7.1_pm_off_lunch": dict(pm_off_lunch=True),
    "M7.1_pm_judas_1330": dict(pm_judas_1330=True),
    "M1.2_displacement_1.5": dict(displacement_mult=1.5),
    "VI_arrays": dict(vi_arrays=True),                                   # shared helpers
    "M12_turtle_2023": dict(turtle_soup="2023"),
    "M12_turtle_2023_htf": dict(turtle_soup="2023", ts_need_htf=True),
    "B8_bias_flip": dict(htf_bias="flip"),
    # --- review fixes / not-built items of package owner_directives_and_bugs (2026-10-18) ------
    "A13.3_ob_both_breaker_mt": dict(ob_entry="both"),                   # #5/#6/#14 act only with an
    "A13.3_ob_both_breaker_mt_off": dict(ob_entry="both", breaker_mt_respect=False,   # FVG entry path
                                         breaker_mt_entry_floor=False),
    "A13.3_post_mss_breaker_mt_off": dict(ob_entry="post_mss", breaker_mt_respect=False,
                                          breaker_mt_entry_floor=False),
    "A13.3_floor_strict": dict(ob_entry="both", breaker_mt_floor_strict=True),
    "D6_breaker_leg": dict(ob_entry="both", breaker_zone="leg"),
    "D6_breaker_last": dict(ob_entry="both", breaker_zone="last"),
    "L17_round_5": dict(round_step_pts=5.0),
    "B17.4_sloppy_premium_run": dict(sloppy_mode="stand_aside", sloppy_tests=("big_prev", "chop", "nfp_week", "premium_run")),
    "B17.4_sloppy_fomc_week": dict(sloppy_mode="stand_aside", sloppy_tests=("big_prev", "chop", "nfp_week", "fomc_week")),
    "B17.4_sloppy_inside_bisi": dict(sloppy_mode="stand_aside", sloppy_tests=("big_prev", "chop", "nfp_week", "inside_bisi")),
    "B17.4_sloppy_all": dict(sloppy_mode="stand_aside", sloppy_tests=("big_prev", "chop", "nfp_week", "premium_run",
                                                                      "fomc_week", "inside_bisi")),
    "B8b_flip_pd3": dict(htf_bias="flip", flip_triggers=("ob_mt", "wk_dc", "flip_pd3")),
    "B8d_flip_close_above": dict(htf_bias="flip", flip_triggers=("ob_mt", "wk_dc", "flip_close_above")),
    "B8e_flip_thu_wopen": dict(htf_bias="flip", flip_triggers=("ob_mt", "wk_dc", "flip_thu_wopen")),
    "B8_flip_all": dict(htf_bias="flip", flip_triggers=("ob_mt", "wk_dc", "flip_pd3", "flip_close_above", "flip_thu_wopen")),
    "B8f_stop_flip_breaker": dict(ob_entry="both", stop_flip="breaker"),
    "B8f_stop_flip_smt": dict(stop_flip="smt"),
    "M12.1_turtle_2023_level": dict(turtle_soup="2023", ts_entry="level", ts_stop="ext"),
    "M12.1_turtle_2023_gap": dict(turtle_soup="2023", ts_stop="gap"),
    "M12.3_turtle_cc_limit": dict(turtle_soup="cc_limit"),
    "M12.3_turtle_cc_1h_ob": dict(turtle_soup="cc_1h_ob"),
    "M12.3_turtle_or60": dict(turtle_soup="or60"),
    "M12.4_turtle_external": dict(turtle_soup="external"),
    "M12.5_ts_gate_mss": dict(ts_gate_mss=True),
    "M3.10_sb_rebalance_ext10": dict(sb_model=True, sb_rebalance_ext=10.0),
    # --- package levels_detectors (one per new switch; name prefix = rule id) -----------------
    "B21_ipda_pools": dict(ipda_pools=True),
    "B21_ipda_next": dict(ipda_next=True),
    "B21_ipda_eq_day_skip": dict(ipda_eq_day="skip"),
    "B21_ipda_eq_day_tag": dict(ipda_eq_day="tag"),
    "A1_mss_ref_itl": dict(ob_entry="post_mss", mss_ref="itl"),
    "A1_mss_ref_ltl": dict(ob_entry="post_mss", mss_ref="ltl"),
    "A1_mss_ref_itl_no_fallback": dict(ob_entry="post_mss", mss_ref="itl", mss_ref_fallback="none"),
    "A1_mss_ref_fallback_highest": dict(ob_entry="post_mss", mss_ref="itl", mss_ref_fallback="highest"),
    "A2_sweep_ticks_off": dict(sweep_ticks=0.0),
    "A2_sweep_ticks_2": dict(sweep_ticks=2.0),
    "A2_pool_swings": dict(pool_swings=True),
    "A2_sb_draw_pools_only": dict(sb_model=True, sb_draw_pools_only=True),
    "A5_fvg_c2_dir_off": dict(fvg_c2_dir=False),
    "A5_fvg_quadrants": dict(fvg_quadrants=True),
    "A5_fvg_vi_extend": dict(ob_entry="both", fvg_vi_extend=True),
    "A5_fvg_skip_above_pool": dict(ob_entry="both", fvg_skip_above_pool=True),
    "A5_htf_ce_draw": dict(htf_ce_draw=True),
    "A5_htf_ce_draw_nolock": dict(htf_ce_draw=True, draw_lock="off"),
    "A5_fvg_q_hold": dict(ob_entry="both", fvg_q_hold=True),
    "A5_fvg_state_open": dict(ob_entry="both", fvg_state_filter=("open",)),
    "A5_fvg_keep_filled": dict(fvg_keep_filled=True),
    "B1_vi_targets": dict(vi_targets=True),
    "B1_wick_days3": dict(wick_days=3),
    "B1_no_draw_tag": dict(no_draw=True),
    "B1_skip_no_draw": dict(skip_no_draw=True),
    "L1_am_range_1200": dict(am_range_end=720),
    "L1_prev_am_pool": dict(prev_am_pool=True),
    "L1_session_priority": dict(session_priority=True, prev_am_pool=True),
    "L1_org_pools": dict(org_pools=True),
    "L2_daily_needs_array": dict(daily_level_needs_array=True),
    "L2_daily_needs_flow": dict(daily_level_needs_array=True, daily_level_needs_flow=True),
    "L2_pd_hl_eth": dict(pd_hl_session="eth"),
    "L2_pool_today_hl": dict(pool_today_hl=True),
    "L5_gap_quarters": dict(gap_quarters=True),
    "L5_nwog_skip_holiday": dict(nwog_skip_holiday=True),
    "L5_nwog_halfway": dict(nwog_halfway=True),
    "L5_nwog_halfway_nolock": dict(nwog_halfway=True, draw_lock="off"),
    "L5_gap_run_stop": dict(gap_run_stop=True),
    "L5_nwog_calendar_days": dict(nwog_trading_days=False),
    "L7_org_draw": dict(org_draw="draw"),
    "L7_org_draw_nolock": dict(org_draw="draw", draw_lock="off"),
    "L7_org_half_draw": dict(org_half_draw=True, draw_lock="off"),
    "L7_org_q_hold_tag": dict(org_q_hold=True, org_draw="tag"),
    "L7_org_days60": dict(org_days=60),
    "L10_wick_weekly": dict(wick_weekly=True),
    "L10_wick_both": dict(wick_both=True),
    "L10_wick_eth": dict(wick_session="eth"),
    "L10_wick_invalidate": dict(wick_invalidate=True),
    "L10_wick_partial": dict(wick_partial=True),
    "M2.1_pool_gaps_far": dict(pool_gaps=True),
    "M2.1_pool_gaps_ce": dict(pool_gaps=True, gap_pool_edge="ce"),
    "T2_release_open": dict(release_open=True),
    "T2_release_open_stop_open": dict(release_open=True, release_open_stop="open"),
    "T2_release_open_stop_wick": dict(release_open=True, release_open_stop="wick_ce"),
    "T2_bias_open_0930": dict(bias_open="0930"),
    "T2_bias_open_0830": dict(bias_open="0830"),
    "Ep01.5_breakaway_tag": dict(ob_entry="both", breakaway="tag"),
    "Ep01.5_breakaway_hold": dict(ob_entry="both", breakaway="hold"),
    "Ep01.5_breakaway_next_fvg": dict(ob_entry="both", breakaway="next_fvg"),
    "Ep01.6_breaker_cand_h": dict(ob_entry="both", breaker_cand_to="h"),
    "Ep01.6_breaker_entry_fallback": dict(ob_entry="post_mss", breaker_entry="fallback"),
    "Ep01.6_breaker_entry_prefer": dict(ob_entry="post_mss", breaker_entry="prefer"),
    "Ep02.8_vi_news_draw": dict(vi_arrays=True, vi_news_draw=True),
    "Ep03.3_vi_body_death": dict(vi_arrays=True, vi_body_death=True),
    "Ep05.1_breaker_levels": dict(ob_entry="both", breaker_levels=True),
    "Ep06.7_eq_pref_rank": dict(eq_pref="rank"),
    "Ep06.7_eq_pref_require": dict(eq_pref="require"),
    "Ep08.10_matrix_ict": dict(matrix_days="ict"),
    "Ep08.10_matrix_full": dict(matrix_full=True),
    "A3_eq_bodies": dict(eq_bodies=True),
    "A3_eq_rank": dict(eq_rank=True, eq_pref="rank"),
    "A3_eq_tol_025": dict(eq_tol_pts=0.25),
    "A3_eq_tol_1": dict(eq_tol_pts=1.0),
    "A7_imm_rebalance_or": dict(displacement_mult=1.5, imm_rebalance_disp="or", ob_entry="post_mss"),
    "A7_imm_rebalance_require": dict(imm_rebalance_disp="require", ob_entry="post_mss"),
    "A9_vi_min_gap1": dict(vi_arrays=True, vi_min_gap_pts=1.0),
    "A9_vi_stop": dict(ob_entry="both", vi_stop=True),
    "A9_vi_porous3": dict(ob_entry="both", vi_porous_n=3),
    "A9_vi_htf_draw": dict(vi_arrays=True, vi_htf_draw=True, draw_lock="off"),
    "A11_bpr_targets": dict(bpr_targets=True, bpr_max_gap_bars=12),
    "A11_bpr_abort": dict(bpr_abort=True),
    "A13.1_breaker_ll": dict(ob_entry="both", breaker_ll=True),
    "A13.5_breaker_time": dict(ob_entry="both", breaker_time="hl2"),
    "A13.5_breaker_time_all": dict(ob_entry="both", breaker_time="all"),
    "A15_mit_targets": dict(mit_targets=True),
    "A15_mit_targets_respect": dict(mit_targets=True, mit_body_respect=True),
    "D6_unicorn_pref_off": dict(ob_entry="both", unicorn_pref=False),
    "D21_monday_ce": dict(gap_mode="monday", monday_ce=True),
    "D21_nwog_quarters": dict(nwog_quarters=True),
    "D21_org_sweep": dict(org_sweep=True),
    "L3_or_extra": dict(or_extra=True),
    "L3_pw_pm_full_session": dict(pool_prev_week=True, pool_prev_month=True, pw_pm_full_session=True),
    "L8_vacuum_blocks": dict(vacuum_blocks=True),
    "Ep01.4_bpr_rule": dict(bpr_rule=True, bpr_max_gap_bars=12),
    "Ep08.1_wick_react_tag": dict(wick_react="tag"),
    "Ep08.1_wick_react_require": dict(wick_react="require"),
    "Ep08.1_daily_fvg_exact": dict(daily_fvg_exact=True),
    # --- review fixes to levels_detectors: new switches, old defaults, interpretive thresholds ------
    "B21_ipda_session_rth": dict(ipda_pools=True, ipda_session="rth"),
    "L2_daily_needs_array_any_tf": dict(daily_level_needs_array=True,
                                        daily_level_array_tfs=("1m", "5m", "15m", "30m", "1h", "4h", "D", "W", "M")),
    "A13.1_breaker_ll_off": dict(ob_entry="both", breaker_ll=False),
    "Ep01.6_breaker_cand_ext": dict(ob_entry="both", breaker_cand_to="ext"),
    "A15_legacy_order": dict(mit_targets=True, mit_legacy_order=True),
    "L7_org_half_draw_lock": dict(org_half_draw=True),
    "A9_vi_htf_draw_lock": dict(vi_arrays=True, vi_htf_draw=True),
    "B21_ipda_eq_frac_010": dict(ipda_eq_day="tag", ipda_eq_frac=0.10),
    "B21_ipda_eq_frac_025": dict(ipda_eq_day="tag", ipda_eq_frac=0.25),
    "B21_ipda_eq_days_20": dict(ipda_eq_day="tag", ipda_eq_days=20),
    "A5_fvg_quad_min_8": dict(fvg_quadrants=True, fvg_quad_min_pts=8.0),
    "A5_fvg_pool_gap_2": dict(ob_entry="both", fvg_skip_above_pool=True, fvg_pool_gap_pts=2.0),
    "B1_no_draw_adr_05": dict(no_draw=True, no_draw_adr=0.5),
    "B1_no_draw_adr_15": dict(no_draw=True, no_draw_adr=1.5),
    "L7_org_break_15": dict(org_draw="draw", org_break_min=15),
    "L7_org_break_60": dict(org_draw="draw", org_break_min=60),
    "L5_gap_run_tol_4": dict(gap_run_stop=True, gap_run_tol_pts=4.0),
    "A11_bpr_targets_any_pair": dict(bpr_targets=True, bpr_max_gap_bars=0),
    "A11_bpr_abort_gap12": dict(bpr_abort=True, bpr_max_gap_bars=12),
    # --- package setups_models (rule_coverage.md section 3; build_log.md). FVG-path switches run
    # with SM_POST (post_mss + no #9 lock + no #7 cap: post_mss with the owner lock / cap gave 0
    # trades on ES 2023H2, review); the MSS-gate switches also run under the default pre-break OB
    # order through ob_pre_gate ("_ob_cancel" = the default, "_ob_hold") -------------------------
    "A19_mss_ref_parent": dict(**SM_POST, mss_ref="parent"),
    "A19.2_mss_eq_wait": dict(**SM_POST, mss_eq_wait=True),
    "A19.4_on_side_tag": dict(**SM_POST, mss_on_side="tag"),
    "Ep04.7_on_side_require": dict(**SM_POST, mss_on_side="require"),
    "Ep08.4_mss_ref_origin": dict(**SM_POST, mss_ref="origin"),
    "A20_disp_mult2": dict(**SM_POST, disp_mult=2.0),
    "A20_disp_through_1": dict(**SM_POST, disp_through_pts=1.0),
    "A20_disp_fvg_after_break": dict(**SM_POST, disp_fvg_after_break=True),
    "A20_disp_all_sb": dict(sb_model=True, disp_mult=2.0, disp_follow=True, disp_fvg_after_break=True),
    "M0.4_disp_body_mult1": dict(**SM_POST, disp_body_mult=1.0),
    "M0.4_disp_follow": dict(**SM_POST, disp_follow=True),
    "Ep07.6_mss_max_bars6": dict(**SM_POST, mss_max_bars=6),
    "Ep07.6_mss_disp15": dict(**SM_POST, mss_disp=1.5),
    "Ep07.6_mss_ref_sibi": dict(**SM_POST, mss_ref_sibi=True),
    "Ep08.16_mss_ref_tf5": dict(**SM_POST, mss_ref_tf=5),
    "M1_am_htf_draw": dict(am_htf_draw=True),
    "M1_am_discount_array": dict(am_discount_array=True),
    "M1_stop_ob_near": dict(**SM_POST, stop_mode="ob_near"),
    "M1.1_mm_context_require": dict(mm_context="require"),
    "M1.1_daily_vi_targets": dict(vi_arrays=True, daily_vi_targets=True),
    "M1.3_speed_check": dict(**SM_POST, speed_check=True, speed_bars=3),
    "M1.3_body_low_cancel": dict(**SM_POST, body_low_cancel=True),
    "M2_no_breakout_fvg": dict(**SM_POST, no_breakout_fvg=True),
    "M2_stop_fvg_candle": dict(**SM_POST, stop_mode="fvg_candle"),
    "M2_stop_ce2": dict(**SM_POST, stop_mode="ce2"),
    "M2_add_leg_cut": dict(**SM_POST, add_leg_cut=True),
    "M2_m2_target": dict(**SM_POST, m2_target=True),
    "M2.3_fvg_pick_2022": dict(**SM_POST, fvg_pick="2022"),
    "M2.7_three_drives_require": dict(three_drives="require"),
    "M4_unicorn_open_only": dict(**SM_POST, unicorn_open_only=True),
    "M4_breaker_retest_add": dict(**SM_POST, breaker_retest_add=True),
    "M4.1_breaker_classic": dict(**SM_POST, breaker_entry="classic"),
    "M4.2_unicorn_rules": dict(**SM_POST, unicorn_rules=True),
    "M4.3_adv_breaker": dict(**SM_POST, adv_breaker=True),
    "M4.4_ts_breaker_pyramid": dict(turtle_soup="2023", ts_breaker_pyramid=True),
    "M4.5_cc_swings_breaker": dict(cc_swings="breaker"),
    "M4.5_cc_swings_failure": dict(cc_swings="failure", cc_fail_pts=5.0),
    "A14_unicorn_only": dict(**SM_POST, unicorn_only=True, unicorn_open_min=30),
    "Ep05.4_unicorn_overlap": dict(**SM_POST, unicorn_entry="overlap"),
    "Ep05.4_add_on_vi": dict(**SM_POST, add_on_vi=True),
    "Ep05.4_adds_in_breaker": dict(**SM_POST, adds_in_breaker=True),
    "M5_pm_last_hour_model": dict(**SM_POST, pm_last_hour_model=True),
    "M5.1_pm_ep01": dict(pm_ep01=True, last_hour_own_slot=True),
    "M5.2_last_hour_own_slot": dict(last_hour_own_slot=True),
    "M5.2_entry_arrays_vi_ob": dict(**SM_POST, entry_arrays=("vi", "ob")),
    "Ep01.13_last_hour_setup": dict(last_hour_setup=True),
    "Ep01.13_lh_parts": dict(last_hour_own_slot=True, lh_unengaged=True, lh_htf_done_skip=True),
    "Ep01.16_pm_4h_ce": dict(pm_4h_ce=True),
    "Ep01.17_lh_start_by_1525": dict(last_hour_own_slot=True, lh_start_by=925),
    "T10_moc_run": dict(moc_run=True, moc_cap_pts=10.0),
    "T10_moc_pool_exit": dict(moc_pool_exit=True),
    "M6_pm_reversal": dict(pm_reversal=True),
    "M7_pm_lunch_target": dict(**SM_POST, pm_lunch_target=True),
    "M7.2_pm_lunch_org": dict(pm_lunch_org=True),
    "M7.3_pm_judas_array": dict(pm_judas_array=True),
    "M10_ifvg_ce_stop3": dict(**SM_POST, ifvg_entries=True, ifvg_entry="ce", ifvg_stop_pts=3.0,
                              ifvg_min_risk_pts=2.0),
    "M10_ifvg_061": dict(**SM_POST, ifvg_entries=True, ifvg_061=True),
    "A8_ifvg_depth_hold": dict(**SM_POST, ifvg_entries=True, ifvg_depth=True, ifvg_hold=True),
    "A8_ifvg_after_htf": dict(**SM_POST, ifvg_entries=True, ifvg_after_htf=True),
    "M11a_ir_entries": dict(ir_entries=True),
    "M11b_cisd_ob_entries": dict(cisd_ob_entries=True),
    "M11c_wick_ce_entries": dict(wick_ce_entries=True),
    "M12_ts_need_flow": dict(turtle_soup="2023", ts_need_flow=True),
    "M12.2_ts_adds_breakers": dict(turtle_soup="2023", ts_adds_breakers=True),
    "Ep08.15_ts_max_run": dict(turtle_soup="2023", ts_need_htf=True, ts_max_run=15),
    "M13_ote_filter": dict(**SM_POST, ote="filter"),
    "M13_ote_limit_stop": dict(**SM_POST, ote="limit", ote_leg_stop=True),
    "M13_leg_pd_strict": dict(**SM_POST, leg_pd_strict=True, ote_stack_tag=True),
    # review fix: the study runs the SPX / NDX CFDs by default (SRC) - SPX is listed so the variant
    # is not inert by design there (ICT trades ES off the signal; the CFD stands in for it)
    "M16.1_smt_entry": dict(smt_entry=True, smt_exit=660, smt_entry_syms=("ES", "MES", "SPX")),
    "M16.1_smt_turtle": dict(smt_entry=True, smt_turtle=True, smt_entry_syms=("ES", "MES", "SPX")),
    "M16.2_sick_sister": dict(sick_sister=True),
    "Ep03.11_smt_pick_leader": dict(smt_pick="leader"),
    "Ep03.11_smt_pick_laggard": dict(smt_pick="laggard"),
    "B18.1_smt_min_gap1": dict(smt_min=1, smt_min_gap_pts=1.0),
    "B18.1_smt_rel_eq": dict(smt_min=1, smt_rel_eq=True),
    "B18_smt_need_array": dict(smt_min=1, smt_need_array=True),
    "B18.2_smt_windows": dict(smt_min=1, smt_windows=((570, 660), (720, 900)), smt_pre=True),
    "N6_news_profile": dict(news_profile="require"),
    "N6_news_ce_target": dict(news_ce_target=True),
    "N6_news_no_unicorn": dict(**SM_POST, news_no_unicorn=True),
    "T13_po3_hold_profiles": dict(po3_hold=True, profile_tags=True),
    "T13_nfp_sd_skip": dict(nfp_sd="skip"),
    "Ep04.3_require_judas": dict(require_judas=True, judas_window=60),
    "Ep04.3_po3_runner": dict(po3_runner=True),
    "Ep04.4_po3_bias_inclusive": dict(po3_require_bias=True, po3_inclusive=True),
    "Ep01.15_nest_tfs": dict(nest_tfs=("4h", "1h", "15m")),
    "Ep05.6_0800_ob_move": dict(pre_0700=True),            # test variant only (one observation)
    "Ep05.8_mmxm": dict(**SM_POST, mmxm_ctx=True, mmxm_breaker=True),
    "Ep01.22_clean_leg2": dict(**SM_POST, clean_leg=2, clean_body=0.5),
    "A18_reclaimed_ob": dict(**SM_POST, reclaimed_ob=True),
    "A24.2_reaper": dict(**SM_POST, reaper=True),
    "A24.2_reaper_confirm": dict(**SM_POST, reaper=True, reaper_confirm=True),
    "M0_candle_draw_daily": dict(candle_draw_bias="daily"),
    "M0_candle_draw_weekly": dict(candle_draw_bias="weekly"),
    "M0.5_entry_arrays_all": dict(ob_entry="post_mss", entry_arrays=("ob", "breaker", "ote", "wick_ce", "vi",
                                                                      "reclaimed_ob")),
    "M15_ma_deuce_full": dict(ma_deuce=True, md_big_candle=1.5, md_second=True, md_ladder=True, md_need_news=True,
                              md_eth=True, md_blocked=True),
    "M15_ma_deuce_ladder": dict(ma_deuce=True, md_ladder=True, md_second=True, md_eth=True),
    # --- setups_models review pass: the MSS gates on the default pre-break OB order (ob_pre_gate),
    # and the switches added by the review (build_log.md "setups_models review fixes") ------------
    "A20_disp_mult2_ob_cancel": dict(disp_mult=2.0),
    "A20_disp_mult2_ob_hold": dict(disp_mult=2.0, ob_pre_gate="hold"),
    "A20_disp_through_1_ob_cancel": dict(disp_through_pts=1.0),
    "M0.4_disp_body_mult1_ob_cancel": dict(disp_body_mult=1.0),
    "M0.4_disp_follow_ob_hold": dict(disp_follow=True, ob_pre_gate="hold"),
    "Ep07.6_mss_max_bars6_ob_cancel": dict(mss_max_bars=6),
    "Ep07.6_mss_disp15_ob_hold": dict(mss_disp=1.5, ob_pre_gate="hold"),
    "M1.3_speed_check_ob_cancel": dict(speed_check=True, speed_bars=3),
    "A19.2_mss_eq_wait_ob_hold": dict(mss_eq_wait=True, ob_pre_gate="hold"),
    "Ep01.22_clean_leg2_ob_hold": dict(clean_leg=2, clean_body=0.5, ob_pre_gate="hold"),
    "A19_mss_ref_parent_ob_hold": dict(mss_ref="parent", ob_pre_gate="hold"),
    "Ep08.4_mss_ref_origin_ob_hold": dict(mss_ref="origin", ob_pre_gate="hold"),
    "Ep08.4_mss_ref_origin_max": dict(**SM_POST, mss_ref="origin_max"),
    "A19.4_on_side_tag_ob": dict(mss_on_side="tag", ob_pre_gate="hold"),
    "D10_ob_pre_gate_hold": dict(ob_pre_gate="hold"),
    "M5.1_pm_ep01_adds": dict(pm_ep01=True, last_hour_own_slot=True, pm_ep01_adds=True),
    "M5.1_pm_ep01_strict": dict(pm_ep01=True, last_hour_own_slot=True, last_hour_strict=True),
    "M5_pm_last_hour_model_strict": dict(**SM_POST, pm_last_hour_model=True, last_hour_strict=True),
    "M5.2_lh_no_lock": dict(last_hour_own_slot=True, lh_no_lock=True),
    "T10_moc_run_synth_po3": dict(moc_run=True, synth_po3=True),
    "M16.2_sick_depth_eq": dict(sick_sister=True, sick_depth=0.5),
    "Ep05.8_mmxm_rel_eq": dict(**SM_POST, mmxm_ctx=True, mmxm_rel_eq=True),
    "A24.1_implied_fvg": dict(**SM_POST, implied_fvg=True),
    "M4.3_adv_breaker_pre": dict(adv_breaker_pre=True),
    "T13_cc_profile_tag": dict(cc_profile="tag"),
    "T13_cc_profile_gate": dict(cc_profile="gate"),
}
DEC_BASE = dict(AM_SPY, pm=Params().pm, skip_news=False)


import os
SRC = os.environ.get("MENTORSHIP_SRC", "histdata")      # "histdata" (SPX/NDX CFDs) or "databento"
SYMS = {"histdata": ("SPX", "NDX"), "merged": ("SPX", "NDX"), "databento": ("ES", "NQ", "YM")}[SRC]


def _bias_cache(tf: int, cut: int = 570, vi: bool = False, flip: tuple = ("ob_mt", "wk_dc"),
                kw: dict | None = None) -> pd.DataFrame:
    """The htf table (cut at `cut` minutes; 570 = the ordinary bias table), cached per source,
    VI wiring and flip triggers (review: the VI_arrays variant used to get the non-VI table), and
    the levels_detectors table switches `kw` (backtest.htf_kw: A5 c2 check, A9 VI size / death)."""
    from . import htf
    kw = kw or {}
    tag = ("" if cut == 570 else f"_cut{cut}") + ("_vi" if vi else "") + \
        ("" if tuple(flip) == ("ob_mt", "wk_dc") else "_" + "-".join(flip)) + \
        "".join(f"_{k}{v}" for k, v in sorted(kw.items()))
    f = Path(f"runs/mentorship/htf_table_{SRC}_{tf}m{tag}.csv")
    if not f.exists() or "flip" not in pd.read_csv(f, nrows=1).columns:     # B8 flip column
        htf.table(B.load(SYMS[0], tf, source=SRC), cut_min=cut, vi=vi, flip_triggers=tuple(flip), **kw).to_csv(f)
    t = pd.read_csv(f, index_col=0)
    t.index = pd.to_datetime(t.index).date
    return t


def _lock_cache(tf: int, p: Params) -> dict:
    """#9: the per-lock-time tables of backtest.lock_tables (same cuts: B.lock_cuts), from the cache."""
    if p.draw_lock == "off":
        return {}
    return {m: _bias_cache(tf, m, p.vi_arrays, p.flip_triggers, B.htf_kw(p)) for m in sorted(B.lock_cuts(p))}


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
              bias_table=_bias_cache(tf, 570, p.vi_arrays, p.flip_triggers, B.htf_kw(p)), meta=B.load_meta(SYMS[0], tf, SRC),
              lock_cuts=_lock_cache(tf, p))
    if p.smt_pick != "first":
        # Ep03.11 (review fix): smt_pick only acts when two instruments are combined - run the
        # partner as its own book (es_pt scaled by the price ratio, as main_index) and combine
        q = replace(p, es_pt=round(p.es_pt * float(pa.close.median() / df.close.median()), 2))
        tb = B.run(pa[(pa.index >= lo) & (pa.index < b)], tf, SYMS[1], q, df[(df.index >= lo) & (df.index < b)],
                   meta=B.load_meta(SYMS[1], tf, SRC) if SRC == "databento" else None, lock_cuts={} if p.draw_lock == "off" else None)
        t = B.combine(t, tb, pick=p.smt_pick)
    if len(t):
        t = t[pd.to_datetime(t.entry_time.astype(str).str[:10]) >= f"{year}-01-01"].copy()
        t["tf"], t["year"], t["variant"] = tf, year, name
    return t


def main_decisions(out="runs/mentorship", workers=6, tfs=(5, 1), variants=None, tag="dec"):
    variants = variants or list(DECISIONS)
    for tf in tfs:
        _bias_cache(tf, kw=B.htf_kw(Params()))
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
