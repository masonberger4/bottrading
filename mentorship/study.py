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
               seen_from_created=False)
# the defaults just before the owner directives of 2026-10-18 (A/B baseline for the new defaults).
# Bug fixes it can NOT undo (no switch, by design): the London-pool look-ahead (London 02:00-05:00
# pools hidden before 05:00), the _split news-ahead holiday skip (N3.4), the M1.2 swing-low intact
# start and the mark_levels / causal roll_day fixes - so "reproduces 833350f exactly" holds on the
# tested window (ES 5m 2024 Q1), not on every window.
PRE_OWNER = dict(ob_entry="post_mss", draw_lock="off", htf_resist_cap=False, news_wait="off",
                 breaker_mt_respect=False, breaker_mt_entry_floor=False, breaker_zone="body",
                 risk_dollars=1000.0, max_total_risk=2000.0, last_hour=(915, 945), flatten=960,
                 sb_target_mode="fixed", price_frame="back_adjusted", round_pools=False,
                 seen_from_created=False, am_exit_extras=False)
LEGACY_1PCT_2PCT = dict(risk_dollars=1000.0, max_total_risk=2000.0)   # E8 / owner #12 preset
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
    "N7.4_year_end_december": dict(year_end="december"),                 # #3 (owner answer pending)
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
    "B17.4_sloppy_stand_aside": dict(sloppy_mode="stand_aside"),         # #10 (owner answer pending)
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
}
DEC_BASE = dict(AM_SPY, pm=Params().pm, skip_news=False)


import os
SRC = os.environ.get("MENTORSHIP_SRC", "histdata")      # "histdata" (SPX/NDX CFDs) or "databento"
SYMS = {"histdata": ("SPX", "NDX"), "merged": ("SPX", "NDX"), "databento": ("ES", "NQ", "YM")}[SRC]


def _bias_cache(tf: int, cut: int = 570, vi: bool = False, flip: tuple = ("ob_mt", "wk_dc")) -> pd.DataFrame:
    """The htf table (cut at `cut` minutes; 570 = the ordinary bias table), cached per source,
    VI wiring and flip triggers (review: the VI_arrays variant used to get the non-VI table)."""
    from . import htf
    tag = ("" if cut == 570 else f"_cut{cut}") + ("_vi" if vi else "") + \
        ("" if tuple(flip) == ("ob_mt", "wk_dc") else "_" + "-".join(flip))
    f = Path(f"runs/mentorship/htf_table_{SRC}_{tf}m{tag}.csv")
    if not f.exists() or "flip" not in pd.read_csv(f, nrows=1).columns:     # B8 flip column
        htf.table(B.load(SYMS[0], tf, source=SRC), cut_min=cut, vi=vi, flip_triggers=tuple(flip)).to_csv(f)
    t = pd.read_csv(f, index_col=0)
    t.index = pd.to_datetime(t.index).date
    return t


def _lock_cache(tf: int, p: Params) -> dict:
    """#9: the per-lock-time tables of backtest.lock_tables (same cuts: B.lock_cuts), from the cache."""
    if p.draw_lock == "off":
        return {}
    return {m: _bias_cache(tf, m, p.vi_arrays, p.flip_triggers) for m in sorted(B.lock_cuts(p))}


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
              bias_table=_bias_cache(tf, 570, p.vi_arrays, p.flip_triggers), meta=B.load_meta(SYMS[0], tf, SRC),
              lock_cuts=_lock_cache(tf, p))
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
