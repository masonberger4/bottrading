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
from .strategy import PRESET_EP07, Params

def study_pick(pick: str, runs: int = 2) -> str:
    """D15 smt_pick "middle" needs three instruments' books (ES / NQ / YM): with the two books these studies run it is inert ("first") until a third series
    is loaded (caption-gap BH-D15-middle-index; backtest.combine itself raises on fewer than three runs)."""
    return "first" if (pick == "middle" and runs < 3) else pick


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
    out = {"SPY": a, "QQQ": b, "combined": B.combine(a, b, pick=study_pick(p.smt_pick), laggard_consol_only=p.laggard_consol_only, one_market=p.one_market,
                                                     sb_one_market=p.sb_one_market, sb_am_done=p.sb_am_done, dual_deal=p.dual_deal,
                                                     exec_exclude=p.combine_exec_exclude, prefer=p.combine_prefer, max_exec=p.max_exec_markets)}
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
                               pick=study_pick(IVARIANTS.get(v, {}).get("smt_pick", "first")),
                               laggard_consol_only=bool(IVARIANTS.get(v, {}).get("laggard_consol_only", False)),
                               one_market=bool(IVARIANTS.get(v, {}).get("one_market", False)),
                               sb_one_market=IVARIANTS.get(v, {}).get("sb_one_market", False),     # SB package
                               sb_am_done=IVARIANTS.get(v, {}).get("sb_am_done", False)).assign(book="combined"))
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
               breaker_ll=False, breaker_cand_to="ext",   # review fix: Ep01.6 defaults pinned back
               stop_tick_pts=0.0, nfp_no_adds=False,      # entries_stops_sizing: the old 0.01 pad, adds on NFP days,
               add_arrays=(),                              # no HTF-FVG add zone (owner #7 revised)
               fomc_no_reentry=False, nfp_first_hour=False, fed_chair_skip_am=False, fomc_flat=0,   # news_calendar_times defaults
               flat_0830_extras=False,
               skip_post_holiday_am=False, london_adr_skip=0.0, friday_slow_split=False,   # day_week_context defaults
               sb_pw_pools=False, sb_cancel_sticky=False)   # SB package: the Silver Bullet draw list / cancel of the old build
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
                 breaker_ll=False, breaker_cand_to="ext",
                 # owner answers 2026-10-18 (year end against December; stand aside on sloppy days)
                 # came after the golden numbers were recorded
                 year_end="off", sloppy_mode="off",
                 # caption-gap entries_stops_sizing#1/3 (A12-ob-anchor-level): the HTF OB level defaults to the 2023 open now; the old engine used the candle extreme
                 htf_ob_anchor="extreme",
                 # entries_stops_sizing defaults (Ep08.17 one-tick pad; E12f no adds on NFP days)
                 stop_tick_pts=0.0, nfp_no_adds=False, add_arrays=(),
                 # news_calendar_times defaults (N3.5 no re-entry on FOMC, N1 no first hour on NFP, N5.5 chair days)
                 fomc_no_reentry=False, nfp_first_hour=False, fed_chair_skip_am=False, fomc_flat=0, flat_0830_extras=False,
                 # day_week_context defaults (N7.2 no AM after a holiday, N9.6 London 80% of ADR5, N10.4 Friday 80/20)
                 skip_post_holiday_am=False, london_adr_skip=0.0, friday_slow_split=False,
                 # silver_bullet package: the Silver Bullet draw list (PWH / PWL) and the cancel stay as they were
                 sb_pw_pools=False, sb_cancel_sticky=False)
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
    "D12_leg_062": dict(leg_pd=0.38, leg_pd_min=0.21),   # fixed: 62-79% RETRACE = entry at 21-38% of the leg
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
    # --- package targets_partials (build_log.md); the variants that act on the non-lock draw path drop the #9 lock ---
    "Ep02.10_resist_cap": dict(htf_resist_mode="cap"),                   # owner #7 first build: exit before the FVG
    "Ep02.10_resist_split": dict(htf_resist_mode="split"),               # cap on 1h+, speed bump on 15m and lower
    "Ep02.10_resist_split_4h": dict(htf_resist_mode="split", htf_resist_cap_tfs=("4h", "D", "W")),
    "Ep02.10_bump_max1": dict(htf_bump_max=1),
    "X3_run_down": dict(draw_lock="off", run_down=True, ladder_all_pools=True),
    "X3a_ladder_max5": dict(draw_lock="off", ladder_max_levels=5),
    "X3_wick_partials": dict(draw_lock="off", wick_partials=True, wick_partial_tfs=("D", "1h", "4h")),
    "X3c_wick_partials_all": dict(draw_lock="off", wick_ce_partial=True, wick_partial_longest=False,
                                  wick_partial_protect=False, wick_partial_min_pts=1.0),
    "X3_sd_neg05_first": dict(draw_lock="off", sd_neg05_first=True),
    "X3d_sd_half_partial": dict(draw_lock="off", sd_half_partial=True, sd_anchor="broken"),
    "X3d_halfway": dict(draw_lock="off", halfway_partial=True, halfway_min_pts=3.0),
    "X3_extra_share": dict(draw_lock="off", wick_partials=True, sd_half_partial=True, halfway_partial=True,
                           partial_extra_frac=0.15, partial_extra_cap=0.45),
    "X3g_smt_bank": dict(smt_bank=True, smt_bank_frac=0.5, smt_bank_min_r=0.5),
    "X3g_smt_bank_against80": dict(smt_bank_against_frac=0.8, smt_bank_min_r=0.5),    # the 80% half: sister breaks against the trade
    "Ep02.10_bump_max2": dict(htf_bump_max=2),                            # two speed bumps (review: default is 1)
    "Ep02.10_bump_frac50": dict(htf_bump_frac=0.5),
    "Ep02.10_bump_drop_inner": dict(htf_bump_below_min=False),            # a bump under min_rr x risk is dropped
    "X3f_resistance_low_full": dict(draw_lock="off", resistance_mode="low_full", res_low_max=1),
    "X3f_resistance_both": dict(draw_lock="off", resistance_mode="both", res_low_max=0, res_high_min=2),
    "X3h_capture_85": dict(capture_frac=0.85),
    "X3h_capture_80": dict(capture_frac=0.8),
    "X3b_sb_split": dict(sb_model=True, sb_split=True),
    "X3b_slow_frac_half": dict(slow_frac=0.5),
    "X3b_slow_frac_off": dict(slow_frac=0.0),
    "A6_measuring_gap_tag": dict(measuring_gap=True),
    "A6_trail_breakaway": dict(trail_breakaway=True),
    "Ep03.5_measuring_far": dict(draw_lock="off", measuring_gap=True, measuring_target=True, measuring_anchor="far"),
    "Ep03.5_measuring_near": dict(draw_lock="off", measuring_gap=True, measuring_target=True, measuring_anchor="near",
                                  measuring_pool_pts=0.0),
    "Ep03.5_measuring_ce_dup": dict(draw_lock="off", proj_measuring=True, measuring_anchor="dup", measuring_mid_frac=0.25),
    "A22_matrix_targets": dict(draw_lock="off", matrix_targets=("breaker", "mitigation", "rejection"), rb_level="open_close"),   # pinned: the built level1 (A17 rb_level default is now "close")
    "A22_breaker_first": dict(draw_lock="off", breaker_first=True, matrix_targets=("breaker",)),
    "A22_skip_exhausted": dict(skip_exhausted=True),
    "L4_pool_rank": dict(pool_rank=True, rel_tfs=(60, 240)),
    "L4_pool_rank_nolock": dict(draw_lock="off", pool_rank=True, pool_rank_reach=4.0, rel_tfs=(60,)),
    "L4_draw_below_eq": dict(draw_below_eq=True),
    "L4_lrlr_max1": dict(draw_lock="off", lrlr_max=1),
    "L4_pool_runner": dict(pool_runner_pts=5.0),
    "Ep04.11_clean_eq_pref": dict(draw_lock="off", clean_eq_pref=True, eq_pref="rank"),
    "L9_fvg_over_ob": dict(fvg_over_ob=True, htf_resist_src=("fvg", "ob")),
    "L9_fvg_remainder": dict(fvg_remainder=True),
    "L9_weekly_gap_ce_only": dict(weekly_gap_ce_only=True),
    "L11_rb_ladder": dict(draw_lock="off", rb_targets="ladder", rb_level="open_close"),
    "L11_rb_replace": dict(draw_lock="off", rb_targets="replace", rb_min_wick_frac=0.4, rb_level="open_close"),
    "A17_rej_targets": dict(draw_lock="off", rej_targets=True),
    "A17_pool_body_edge": dict(draw_lock="off", pool_body_edge=True),
    "L12_sd_anchor_broken": dict(draw_lock="off", sd_targets=True, sd_anchor="broken"),
    "L12_sd_anchor_downleg": dict(draw_lock="off", sd_targets=True, sd_anchor="downleg", sd_no_pool_fallback=True),
    "L12_sd_anchor_fulcrum": dict(draw_lock="off", sd_targets=True, sd_anchor="fulcrum"),
    "L12_sd_anchor_london": dict(draw_lock="off", sd_targets=True, sd_anchor="london"),
    "L12_sd_multi_cluster": dict(draw_lock="off", sd_targets=True, sd_anchor="multi", sd_cluster_ticks=4, sd_swings=4),
    "L12_sd_roles": dict(draw_lock="off", sd_targets=True, sd_anchor="broken", sd_roles=True,
                         sd_levels=(0.5, 1.0, 1.5, 2.0, 4.5), sd_first_beyond=False),
    "L12_sd_align": dict(draw_lock="off", sd_targets=True, sd_anchor="multi", sd_align=True, sd_align_tol_pts=2.0),
    "D23_sd_levels_05_45": dict(draw_lock="off", sd_targets=True, sd_levels=(0.5, 1.0, 2.0, 3.0, 4.5), sd_anchor="sweep_leg"),
    "Ep06.4_sd_close_hit": dict(draw_lock="off", sd_targets=True, sd_anchor="manip", sd_close_hit=True,
                                sd_close_window=(600, 720)),
    "Ep08.9_mm_leg": dict(draw_lock="off", mm_targets=True, mm_anchor="leg"),
    "Ep08.9_mm_ref": dict(draw_lock="off", mm_targets=True, mm_anchor="ref"),
    "L13_proj_breaker": dict(draw_lock="off", proj_breaker=True),
    "L13_proj_org": dict(draw_lock="off", proj_org_k=(1, 2)),
    "L13_proj_ext": dict(draw_lock="off", proj_ext=(1.27, 1.62)),
    "L14d_target_hygiene": dict(draw_lock="off", target_hygiene=("arrays", "htf", "wick")),
    "M8_org_reprice": dict(draw_lock="off", org_reprice=True),
    "M14.2_tgif_zone": dict(draw_lock="off", tgif=True, tgif_zone=True),
    "M14.2_tgif_zone_cap25": dict(draw_lock="off", tgif=True, tgif_zone=True, tgif_cap=0.25, tgif_stand_down=0.35),
    "M14.4_tgif_exits": dict(draw_lock="off", tgif=True, tgif_zone=True, tgif_exits=True),
    "X1_target_ltf_obs": dict(draw_lock="off", target_ltf_obs=True),
    "X1_keep_inner_levels": dict(draw_lock="off", keep_inner_levels=True, inner_min_pts=2.0),
    "Ep03.22_final_htf": dict(draw_lock="off", final_htf=True),
    "A10_void_targets": dict(draw_lock="off", void_targets=True),
    "A10_leg_start_target": dict(draw_lock="off", leg_start_target=True),
    "Ep01.21_inter_swing_target": dict(draw_lock="off", inter_swing_target=True),
    "A23_wick_tfs": dict(draw_lock="off", wick_tfs=("1h", "4h")),
    "A23_wick_read": dict(wick_read="exit", wick_days=3),
    "A23_wick_week_eth": dict(wick_week=True, wick_daily_src="eth", wick_days=2),
    "L16_adr_target": dict(draw_lock="off", adr_target=True, adr_frac=0.65),
    "L16_adr_early": dict(adr_early=True, adr_early_frac=0.8),
    "Ep03.19_mgmt_unit": dict(mgmt="unit"),
    "Ep04.12_target_order": dict(draw_lock="off", target_order=("eq", "daily", "vi"), daily_vi_targets=True, vi_arrays=True,
                                 ladder_fracs_bulk=(0.8, 0.1, 0.1)),
    "Ep04.12_ladder_news_day": dict(ladder_news_day=True),
    "Ep07.1_close_draw": dict(draw_lock="off", close_draw=True),
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
    # --- package entries_stops_sizing (one per new switch; name prefix = rule id) ----------------
    # FVG-path variants run with SM_POST (the default OB-before-break entry never uses them)
    "Ep08.17_stop_tick_off": dict(stop_tick_pts=0.0),                    # DEFAULT ON: the old 0.01 pad
    "Ep08.17_engage_range10": dict(engage_range_pts=10.0),
    "E6_stop_fvg_c1_low": dict(SM_POST, stop_mode="fvg_c1_low", max_risk_pts=25),
    "E6_stop_fvg_bodies": dict(SM_POST, stop_mode="fvg_bodies", max_risk_pts=25),
    "E6_stop_all_ineff": dict(SM_POST, stop_all_ineff=True, max_risk_pts=25),
    "E6_stop_all_ineff_no_wick": dict(SM_POST, stop_all_ineff=True, stop_ineff_wick=False, max_risk_pts=25),
    "E6_ce_stop_pad3": dict(SM_POST, entry="ce", ce_stop_pad_pts=3.0),
    "E6_nfp_stop_wide": dict(SM_POST, nfp_day=True, nfp_stop_wide=True, max_risk_pts=25),
    "E6c_stop_sweep": dict(SM_POST, stop_mode="sweep", max_risk_pts=25),
    "E6b_stop_fvg_candle": dict(SM_POST, stop_mode="fvg_candle"),
    "E6d_stop_all_ineff_ob": dict(stop_all_ineff=True, max_risk_pts=25),
    "E6f_stop_pad_3ticks": dict(stop_pad_ticks=3.0),
    "E6f_stop_pad_0ticks": dict(stop_pad_ticks=0.0001),
    "E6f_nfp_stop_wide_ob": dict(nfp_stop_wide=True, max_risk_pts=25),
    "Ep01.20_stop_fvg_open": dict(SM_POST, stop_mode="fvg_open", max_risk_pts=25),
    "Ep01.20_trail_pad_mohawk": dict(trail=True, mohawk_ticks=2.0),
    "Ep01.20_trail_ref_body": dict(trail=True, trail_ref="body"),
    "M2.5_stop_ob_mt_pure": dict(SM_POST, stop_mode="ob_mt_pure", max_risk_pts=25),
    "M2.5_stop_fvg_candle": dict(SM_POST, stop_mode="fvg_candle"),
    "M2.5_stop_ce2": dict(SM_POST, stop_mode="ce2"),
    "A4_mohawk2": dict(mohawk_ticks=2.0),
    "A4_mohawk4_post": dict(SM_POST, mohawk_ticks=4.0),
    "A4_sweep_body": dict(sweep_body=True),
    "A12_ob_zone_range": dict(ob_zone="range"),
    "A12_ob_zone_sensitive": dict(ob_zone="sensitive"),
    "A12_ob_zone_sensitive_stub10": dict(ob_zone="sensitive", ob_stub_frac=0.1),
    "A12_mt_close_stop": dict(mt_close_stop=True),
    "A12_ob_disp_mult2": dict(SM_POST, ob_disp_mult=2.0),
    "A12_ob_cisd_tag": dict(ob_cisd="tag"),
    "A12_ob_cisd_cancel": dict(ob_cisd="cancel"),
    "A12_ob_targets_1m": dict(ob_targets_1m=True),
    "A12_opp_ob_mt": dict(ob_targets_1m=True, opp_ob_mt=True),
    "Ep02.3_mt_close_stop_post": dict(SM_POST, mt_close_stop=True),
    "A13.4_breaker_entry_classic": dict(SM_POST, breaker_entry="classic"),
    "Ep05.5_breaker_entry_fallback": dict(SM_POST, breaker_entry="fallback"),
    "M1.4_ob_entry_pre_break": dict(ob_entry="pre_break"),
    "M2.4_no_new_extreme": dict(no_new_extreme=True),
    "M2.4_no_new_extreme_post": dict(SM_POST, no_new_extreme=True),
    "E2_entry_edge_1tick": dict(SM_POST, entry="edge_1tick"),
    "E2_entry_iofed": dict(SM_POST, entry="iofed"),
    "E2_entry_iofed_q75": dict(SM_POST, entry="iofed", iofed_ref="q75"),
    "E2_entry_ladder": dict(SM_POST, entry="ladder", max_risk_pts=25),
    "E2_sb_entry_edge_1tick": dict(sb_model=True, sb_entry="edge_1tick"),
    "E2_sb_entry_iofed": dict(sb_model=True, sb_entry="iofed"),
    "D11_entry_edge_1tick": dict(SM_POST, entry="edge_1tick"),
    "D11_entry_ladder_532": dict(SM_POST, entry="ladder", entry_ladder_fracs=(0.5, 0.3, 0.2), max_risk_pts=25),
    "D11_run_cancel_last": dict(run_cancel="last"),
    "D11_run_cancel_off": dict(run_cancel="off"),
    "D12_leg_ote_62_79": dict(leg_pd=0.38, leg_pd_min=0.21),            # fixed: the OTE band (62-79% retrace)
    "D12_leg_pd_min": dict(SM_POST, leg_pd_min=0.21),
    "D12_add_cutoff25": dict(add_cutoff=0.25),
    "A21.3_ote_limit_cancel": dict(SM_POST, ote="limit", ote_cancel=True, max_risk_pts=40),
    "A21.3_leg_depth_tag": dict(SM_POST, leg_depth_tag=True),
    "E5_evolve_fvg": dict(SM_POST, evolve_fvg=True),
    "E5_wait_structural": dict(SM_POST, wait_structural=True, max_risk_pts=12),
    "E1_stop_cc": dict(SM_POST, entry_order="stop_cc"),
    "E1_add_order_market": dict(add_order="market"),
    "E3_fill_through1": dict(fill_through=1.0),
    "E3_exit_fill_through1": dict(exit_fill_through=1.0),
    "E3_fill_through1_sb": dict(sb_model=True, fill_through=1.0, exit_fill_through=1.0, ma_deuce=True),
    "E4_retrace_closed": dict(SM_POST, retrace_candle="closed"),
    "E4_retrace_intrabar": dict(SM_POST, retrace_candle="intrabar"),
    "Ep04.6_mo_tol1": dict(mo_tol_pts=1.0),
    "Ep03.9_ob_px_open": dict(ob_entry_px="open"),
    "Ep03.9_ob_px_high": dict(ob_entry_px="high"),
    "Ep08.5_ob_entries_fallback": dict(SM_POST, ob_entries="fallback"),
    "Ep08.5_ob_entries_prefer": dict(SM_POST, ob_entries="prefer"),
    "Ep07.2_vi_entries": dict(SM_POST, vi_entries=True, max_risk_pts=25),
    "Ep07.2_ep07_preset": dict(PRESET_EP07),
    "Ep07.4_vi_stop": dict(SM_POST, vi_stop=True, vi_hold=True),
    "Ep07.4_vi_hold": dict(SM_POST, vi_hold=True),
    "A16_prop_entry": dict(SM_POST, prop_entry=True),
    "A16_prop_mt_exit": dict(SM_POST, prop_mt_exit=True, prop_zone="body"),
    "L14b_irl_fvg_ob_void": dict(SM_POST, irl_entries=("fvg", "ob", "void"), max_risk_pts=25),
    "L14b_irl_void_only": dict(SM_POST, irl_entries=("void",), max_risk_pts=25),
    "L14b_erl_range_swings": dict(erl_range_swings=True),
    "L14b_erl_exits_only": dict(erl_exits_only=True),
    "E9_size_news_eve": dict(size_rules=("news_eve",)),
    "E9_size_fomc_week": dict(size_rules=("fomc_week",)),
    "E9_size_august": dict(size_rules=("august",)),
    "E9_size_all_down": dict(size_rules=("news_eve", "fomc_week", "august", "against_macro", "decoupled", "low_prob")),
    "E9_size_up_bpr_htf": dict(size_up_rules=("bpr", "htf_target")),
    "E10_loss_halving": dict(loss_halving=True),
    "E10_loss_halving_floor1_8": dict(loss_halving=True, halving_floor=0.125, winback_frac=1.0),
    "E10_no_max_after_loss": dict(no_max_after_loss=True),
    "Ep08.12_after_loss_half": dict(after_loss_mult=0.5),
    "Ep08.12_after_loss_no_adds": dict(after_loss_adds=False),
    "E11_max_contracts_6_16": dict(max_contracts_initial=6, max_contracts_total=16, units_per_contract=1),
    "E12_add_points_ce": dict(add_points="ce"),
    "E12_add_cutoff25": dict(add_cutoff=0.25),
    "E12_adds_off_nfp_default": dict(nfp_no_adds=False),                 # DEFAULT ON: adds also on NFP days
    "E12_no_adds_nfp_alias": dict(no_adds_nfp=True),
    "E12b_add_arrays_vi_ifvg": dict(add_arrays=("vi", "ifvg"), ifvg_entries=True),
    "E12b_add_arrays_ob_breaker": dict(add_arrays=("ob", "breaker"), ob_adds=False),
    "E12b_add_hold": dict(add_hold=True),
    "E12c_add_low_end": dict(add_low_end=True),
    "E12e_add_cut_eq": dict(add_cut="eq"),
    "E12e_add_cut_leg75": dict(add_cut="leg75"),
    "E12e_add_cut_eq_leg": dict(add_cut="eq", add_cut_ref="leg"),
    "E12f_decoupled_no_adds": dict(decoupled_no_adds=True),
    "E12f_low_prob_no_adds": dict(low_prob_no_adds=True, low_prob_tests=("against_bias", "no_htf")),
    "Ep01.18_add_on_retest": dict(add_on="retest"),
    "Ep01.18_add_on_breaker": dict(SM_POST, add_on="breaker"),
    "Ep01.19_add_body_stop": dict(add_body_stop=True),
    "Ep04.10_add_fvg_low": dict(add_fvg_low=True),
    "E12_add_fvg_low_end": dict(add_fvg_low_end=True),
    "Ep02.2_add_htf_fvg_off": dict(add_arrays=()),                       # owner #7 revised: the add zone is the default
    "Ep02.2_add_htf_fvg_extra_risk": dict(htf_add_extra_risk_pct=0.005),  # the add may use 0.5% above the 1.3% cap
    "E12e_add_cutoff25_progress": dict(add_cutoff=0.25, add_cutoff_read="progress"),   # the other reading of the 25% line
    "E9_size_up_cap": dict(size_up_rules=("bpr", "htf_target"), size_up_cap_pct=0.005),   # a real 1.5x (cap 1.8%)
    "E12f_nfp_day_adds_blocked": dict(nfp_day=True, nfp_no_adds=True),   # NFP days traded: no pyramiding (default rule)
    "E12f_nfp_day_adds_allowed": dict(nfp_day=True, nfp_no_adds=False),  # NFP days traded and pyramided
    # --- package management_exits (name prefix = rule id) ---------------------------------------------------------
    "M2.6_add_in_pd": dict(add_in_pd=True),
    "M2.6_add_cutoff25_fixed_leg": dict(add_cutoff=0.25, add_cut_ref="leg", add_leg_at_fill=True),
    "M2.6_add_cutoff25_leg_at_arming": dict(add_cutoff=0.25, add_cut_ref="leg", add_leg_at_fill=False),
    "M2.6_pool_size_rank": dict(pool_size_rank=True),
    "X4_be_pad_cost": dict(be_pad_pts=0.5, be_cost_pad=True),
    "X4_be_t1": dict(be_on="t1"),
    "X4_sb_follows_be_t1": dict(sb_model=True, ma_deuce=True, extras_be_on="follow", be_on="t1"),
    "X4_extras_follow_be_expansion": dict(sb_model=True, ma_deuce=True, extras_be_on="follow"),
    "X4_extras_follow_be_after_mss": dict(sb_model=True, ma_deuce=True, extras_be_on="follow", be_on="after_mss"),
    "X4_extras_follow_be_stall": dict(sb_model=True, ma_deuce=True, extras_be_on="follow", be_on="stall"),
    "X4_extras_follow_be_pool": dict(sb_model=True, ma_deuce=True, extras_be_on="follow", be_on="pool"),
    "X4_extras_follow_be_off": dict(sb_model=True, ma_deuce=True, extras_be_on="follow", be_on="off"),
    "D14_be_after_mss": dict(be_on="after_mss"),
    "D14_be_stall": dict(be_on="stall"),
    "D14_be_off": dict(be_on="off"),
    "D14_ladder_trail_off": dict(ladder_trail="off"),
    "D14_ladder_trail_hit": dict(ladder_trail="hit"),
    "D14_ladder_trail_prior": dict(ladder_trail="prior"),
    "Ep03.15_be_pool": dict(be_on="pool"),
    "X5a_trail_pad_025": dict(trail_pad_pts=0.25),
    "X5a_trail_pad_100": dict(trail_pad_pts=1.0),
    "X5a_trail_breakaway": dict(trail_breakaway=True),
    "Ep03.10_trail_first_fvg": dict(trail_first_fvg=True),
    "Ep03.10_first_fvg_fail": dict(first_fvg_fail=True),
    "Ep03.10_first_fvg_trail_and_fail": dict(trail_first_fvg=True, first_fvg_fail=True),
    "X5a_ladder_trail_breakaway": dict(ladder_trail="breakaway", trail_after=1),
    "X5a_ladder_trail_breakaway_after2": dict(ladder_trail="breakaway", trail_after=2),
    "Ep03.20_trail_after2": dict(trail_after=2),
    "Ep03.20_trail_measuring": dict(ladder_trail="measuring", trail_after=2),
    "X5c_day_trade_open": dict(trade_type="day", day_stop="open"),
    "X5c_day_trade_wick_ce": dict(trade_type="day", day_stop="wick_ce"),
    "X6_fvg_abort_legacy": dict(fvg_abort=True, fvg_abort_mode="legacy"),
    "X6_fvg_abort_body": dict(fvg_abort=True, fvg_abort_body=True),
    "X7a_pd3_fixed": dict(pd3_exit=True),
    "X7a_pd3_dynamic": dict(pd3_exit=True, pd3_dynamic=True),
    "X7a_pd3_legacy": dict(pd3_exit=True, pd3_legacy=True),
    "X7a_pd3_fvg_only": dict(pd3_exit=True, pd3_list=("fvg",)),
    "X7b_pd3_half": dict(pd3_half=True),
    "X7c_fails3_trades": dict(session_stop_after_fails=3, reentry_half=True),
    "X7c_fails3_arrays": dict(session_stop_after_fails=3, session_fail_mode="arrays", reentry_half=True),
    "X7c_fails2_trades_sb": dict(session_stop_after_fails=2, sb_model=True, reentry_half=True),
    "X8b_leg_mt_exit": dict(leg_mt_exit=True),
    "X8c_ir_eq_wick": dict(ir_eq_exit=True),
    "X8c_ir_eq_body": dict(ir_eq_exit=True, ir_eq_wick=False),
    "X8d_prop_exit": dict(prop_exit=True),
    "X8e_offside_open": dict(offside_exit=True),
    "X8e_offside_wick_ce": dict(offside_exit=True, offside_level="wick_ce"),
    "X8g_meander4": dict(meander_bars=4),
    "X8g_meander8": dict(meander_bars=8),
    "X9_time_stop_bars2": dict(time_stop_min=0, time_stop_bars=2),
    "X9a_time_stop_leg_high": dict(time_stop_min=10, time_stop_ref="leg_high"),
    "X9a_time_stop_array_far": dict(time_stop_min=10, time_stop_ref="array_far"),
    "X9d_time_stop_half": dict(time_stop_min=10, time_stop_frac=0.5),
    "X9_time_stop_sb_md": dict(time_stop_min=10, sb_model=True, ma_deuce=True),
    "X9c_far_edge2": dict(far_edge_min=2),
    "X9c_far_edge2_all": dict(far_edge_min=2, far_edge_frac=1.0),
    "X10b_am_bulk_1100": dict(am_bulk_t=660, am_bulk_frac=0.8),
    "X10b_am_bulk_1000": dict(am_bulk_t=600, am_bulk_frac=0.8),
    "X10c_smt_hold_1030": dict(smt_hold_until=630, smt_hold_exit=True, am_bulk_t=600),
    "X11c_pm_consol_1400": dict(pm_consol_exit=840),
    "X12_obj_stop_draw": dict(obj_stop=True),
    "X12_obj_stop_htf_ce": dict(obj_stop=True, obj_source="htf_ce"),
    "X13a_reverse_in_session": dict(reverse_in_session=True),
    "X13a_lost_side_session": dict(reverse_after_loss=False, lost_side_session=True),
    "X13a_loss_ends_morning": dict(loss_ends_morning=True, sb_model=True),
    "X13b_reentry_half_gated": dict(reentry_half=True, reentry_gate=True),
    "X13b_reentry_half_gated_fomc_ok": dict(reentry_half=True, reentry_gate=True, reentry_fomc_ok=True),
    "D18_reentry_half_loss_risk": dict(reentry_half=True, reentry_risk="loss"),
    "D18_reentry_lock_target": dict(reentry_half=True, reentry_lock_r=2.0, reentry_target_r=3.0),
    "X14b_chop_one_win": dict(chop_one_win=True, sloppy_tests=("chop",)),
    "X14d_no_trade_after_win": dict(no_trade_after_win=True, sb_model=True, ma_deuce=True),
    "Ep04.13_done_if_target": dict(done_if_target=True),
    "Ep07.5_add_downclose": dict(add_mode="downclose"),
    "Ep07.5_tp_upclose": dict(tp_upclose=True),
    "Ep07.7_body_exit_fixed": dict(ep07_body_exit=True, ep07_body_fixes=True),
    "Ep07.7_body_exit_first_build": dict(ep07_body_exit=True, ep07_body_fixes=False),
    "T11_late_cutoff_off": dict(late_cutoff=0),
    "B18.3_smt_pick_leader": dict(smt_pick="leader"),
    # --- management_exits review fixes: one variant per switch the review listed + the new ones --------------------
    "M2.6_add_pd_level_03": dict(add_in_pd=True, add_pd_level=0.3),
    "M2.6_add_in_pd_low_end": dict(add_in_pd=True, add_fvg_low=True),
    "M2.6_add_in_pd_ep01_adds": dict(add_in_pd=True, pm_ep01_adds=True),
    "D14_be_stall_3bars": dict(be_on="stall", be_stall_bars=3),
    "D14_be_stall_min_r_05": dict(be_on="stall", be_stall_min_r=0.5),
    "Ep03.10_first_fvg_fail_after_t1": dict(first_fvg_fail=True, first_fvg_fail_after_t1=True),
    "X6_fvg_abort_tf1": dict(fvg_abort=True, fvg_abort_tf=1),
    "X6_fvg_abort_tf15": dict(fvg_abort=True, fvg_abort_tf=15),
    "X7a_pd3_n2": dict(pd3_exit=True, pd3_n=2),
    "X7a_pd3_n4": dict(pd3_exit=True, pd3_n=4),
    "X7b_pd3_half_033": dict(pd3_half=True, pd3_half_frac=0.33),
    "X7b_pd3_half_067": dict(pd3_half=True, pd3_half_frac=0.67),
    "X9_time_stop_extras_off": dict(time_stop_min=10, time_stop_extras=False, sb_model=True, ma_deuce=True),
    "X9a_time_stop_leg_high_sb_md": dict(time_stop_min=10, time_stop_ref="leg_high", sb_model=True, ma_deuce=True),
    "X9a_time_stop_array_far_sb_md": dict(time_stop_min=10, time_stop_ref="array_far", sb_model=True, ma_deuce=True),
    "X6_abort_sb_md": dict(fvg_abort=True, sb_model=True, ma_deuce=True),
    "X7a_pd3_sb_md": dict(pd3_exit=True, sb_model=True, ma_deuce=True),
    "X8b_leg_mt_exit_sb_md": dict(leg_mt_exit=True, sb_model=True, ma_deuce=True),
    "X8e_offside_sb_md": dict(offside_exit=True, sb_model=True, ma_deuce=True),
    "X8g_meander4_sb_md": dict(meander_bars=4, sb_model=True, ma_deuce=True),
    "X9c_far_edge2_sb_md": dict(far_edge_min=2, sb_model=True, ma_deuce=True),
    "Ep03.10_first_fvg_fail_sb_md": dict(first_fvg_fail=True, sb_model=True, ma_deuce=True),
    "X6_invalidations_extras_off": dict(fvg_abort=True, pd3_exit=True, sb_model=True, ma_deuce=True, invalidations_extras=False),
    "X7c_stops_one_way": dict(no_trade_after_win=True, sb_model=True, ma_deuce=True, stops_passes=1),
    "X14d_no_trade_after_win_two_way": dict(no_trade_after_win=True, sb_model=True, ma_deuce=True),
    "X13a_reverse_in_session_lost_side": dict(reverse_in_session=True, reverse_after_loss=False, lost_side_session=True),
    "X13a_reverse_in_session_reentry_gate": dict(reverse_in_session=True, reentry_half=True, reentry_gate=True),
    "D18_reentry_stop_only": dict(reentry_half=True, reentry_stop_only=True),
    "Ep04.13_done_target_1030": dict(done_if_target=True, done_target_before=630),
    "B18.3_smt_bias_tag": dict(smt_bias="tag"),
    "B18.3_smt_bias_filter": dict(smt_bias="filter"),
    "B18.3_smt_exit_against": dict(smt_exit_against=True),
    "B18.3_smt_exit_against_bank": dict(smt_exit_against=True, smt_bank=True),
    # --- package news_calendar_times (rule_coverage.md section 3; build_log.md) ----------------------------
    "N1_nfp_first_hour_off": dict(nfp_first_hour=False, pre_0900=True, ma_deuce=True),
    "N1_nfp_first_hour": dict(nfp_first_hour=True, pre_0900=True, ma_deuce=True),
    "D8_nfp_day_from_1000": dict(nfp_day_from=600),
    "D8_nfp_week_block": dict(nfp_week_block=True),                      # the blocked() fix: relative to the real NFP date
    "N3_fomc_flat_off": dict(fomc_flat=0),
    "N3_fomc_flat_before_1330": dict(fomc_flat_before=810),
    "N3_fomc_eve_risk_half": dict(fomc_eve_risk=0.5),
    "N3.4_pre_fomc_risk_half": dict(pre_fomc_risk=0.5),
    "N3_skip_pre_fomc": dict(skip_pre_fomc=True),
    "N3_fomc_after_am_block": dict(fomc_after_am_block=True),
    "D8_skip_post_fomc_am": dict(skip_post_fomc_am=True),
    "N3.5_fomc_reentry_ok": dict(fomc_no_reentry=False),
    "N3.2_fomc_am_recipe": dict(fomc_am="recipe"),
    "N3.2_fomc_am_skip": dict(fomc_am="skip"),
    "N3.3_fomc_only_am_tag": dict(fomc_only_am="tag"),
    "N3.3_fomc_only_am_scalp": dict(fomc_only_am="scalp"),
    "N3.3_fomc_only_am_skip": dict(fomc_only_am="skip"),
    "N3.1_fomc_pm_block_from_1400": dict(fomc_pm_block_from=840),
    "N3.1_fomc_observe_defer": dict(fomc_observe="defer"),
    "N3.1_fomc_observe_judas": dict(fomc_observe="judas"),
    "N3.1_sb_fomc_pm": dict(sb_model=True, sb_fomc_pm=True),
    "N3_fomc_whipsaw_skip_london": dict(fomc_whipsaw_skip_london=True, london_kz=True, sb_model=True, sb_london=True),
    "M9.2_fomc_judas": dict(fomc_judas=True),
    "M9.2_fomc_judas_stage2": dict(fomc_judas=True, fomc_stage2_cont=True),
    "M9.2_fomc_judas_1425": dict(fomc_judas=True, fomc_judas_end=865),
    "N4_pre_cpi_small": dict(pre_cpi="small"),
    "N4_pre_cpi_skip": dict(pre_cpi="skip"),
    "D9_skip_pre_cpi": dict(skip_pre_cpi=True),
    "N4_pre_flat_0830_sb_london_md": dict(pre_flat_0830=True, sb_model=True, sb_london=True, ma_deuce=True),
    "N4_flat_0830_extras_off": dict(flat_0830_extras=False, sb_model=True, sb_london=True, ma_deuce=True),
    "N5_news_claims": dict(news_claims=True),
    "N5_news_conf_board": dict(news_conf_board=True),
    "N5_news_minutes": dict(news_minutes=True),
    "N5_news_claims_minutes": dict(news_claims=True, news_minutes=True),
    "Ep02.1_wait_0945_off": dict(wait_0945=False),
    "N5.4_skip_two_drivers": dict(skip_two_drivers=True),
    "N5.4_two_driver_gate_off": dict(two_driver_gate=False, pre_0900=True),
    "N5.5_fed_chair_skip": dict(fed_chair_skip_am=True),
    "N4_pre_cpi_small_03": dict(pre_cpi="small", pre_cpi_risk=0.3),
    "T4_or_deep_win_1000": dict(or_no_entry=True, or_deep=True, or_deep_win=(580, 600)),
    "T8_lunch_win_1150": dict(lunch=True, lunch_win=(700, 800), lunch_exit=790),
    "T8_lunch_exit_1200": dict(lunch=True, lunch_exit=720),
    "N1_nfp_first_hour_ny_kz": dict(nfp_first_hour=True, ny_kz_futures=True, am_from_0830=True),
    "N5.6_skip_auction_am": dict(skip_auction_am=True),
    "M9_news_judas_block": dict(news_judas="block"),
    "M9.1_news_judas_wait": dict(news_judas="wait"),
    "M9.1_news_judas_ref30": dict(news_judas="wait", news_judas_ref_min=30),
    "T4_or_no_entry": dict(or_no_entry=True),
    "T4_or_no_entry_1030": dict(or_no_entry=True, or_end=630),
    "D1_or_no_entry_news1000": dict(or_no_entry=True, or_no_entry_news1000=True),
    "T4_or_deep": dict(or_no_entry=True, or_deep=True),
    "D1_or_deep_pd33": dict(or_no_entry=True, or_deep=True, or_deep_pd=0.33),
    "T4_or_bias_judas": dict(or_bias="judas"),
    "T4_or_bias_close": dict(or_bias="close"),
    "T4_or_bias_tag": dict(or_bias="judas", or_bias_filter=False),
    "T4_or_wide": dict(or_wide=True),
    "T4_or_wide_1000": dict(or_wide=True, or_wide_end=600, or_wide_adr=0.4),
    "T5_pre_0820": dict(pre_0820=True),
    "Ep01.10_am_from_0830": dict(am_from_0830=True),
    "Ep01.10_am_from_0830_pre_0820": dict(am_from_0830=True, pre_0820=True),
    "Ep06.1_ny_kz_futures": dict(ny_kz_futures=True),
    "Ep06.1_london_kz": dict(london_kz=True),
    "Ep06.1_london_kz_0100": dict(london_kz=True, london_kz_start=60),
    "T8_lunch": dict(lunch=True),
    "T8_lunch_pm_carry": dict(lunch=True, pm_carry_draw=True),
    "T8_pm_carry_draw": dict(pm_carry_draw=True),
    "T8_draw_done_skip": dict(draw_done_skip=True),
    "T9_pm_skip_after_1430": dict(pm_skip_after=870),
    "T9_pm_skip_after_lh": dict(pm_skip_after=870, pm_skip_lh=True),
    "T9_pm_bad_am_1345": dict(pm_bad_am_start=825),
    "T9_pm_continue_am_tag": dict(pm_continue_am="tag"),
    "T9_pm_continue_am_filter": dict(pm_continue_am="filter"),
    "T9_pm_ob_entry_tag": dict(pm_ob_entry="tag"),
    "T9_pm_ob_entry_require": dict(pm_ob_entry="require"),
    "T7_macro_gate": dict(macro_gate=True),
    "Ep07.8_macro_only_0950": dict(macro_only="0950"),
    "Ep07.8_macro_only_0950_start": dict(macro_only="0950", macro_by="start"),
    "Ep07.8_macro_only_all": dict(macro_only="all"),
    "T7_macro_done_skip": dict(macro_gate=True, macro_done_skip=True),
    "T7_macro_done_skip_adr05": dict(macro_gate=True, macro_done_skip=True, run_done_adr=0.5),
    "T7_moc_htf_done": dict(moc_htf_done=True),
    # --- package day_week_context (rule_coverage.md section 3; build_log.md) --------------------------------
    "B11_inside_week_tag": dict(b11_inside_week="tag"),
    "B11c_inside_week_scalp": dict(b11_inside_week="scalp"),
    "B11c_inside_week_scalp_1day": dict(b11_inside_week="scalp", b11_inside_week_days=1),
    "B11c_inside_day_expansion": dict(b11_inside_expansion="no_chop_skip"),
    "B11c_inside_day_expansion_tag": dict(b11_inside_expansion="tag"),
    "B11b_outside_day_block": dict(outside_day_rule="block"),
    "B11b_outside_day_block_no_mirror": dict(outside_day_rule="block", outside_day_mirror=False),
    "B11_nr_tags": dict(nr_tags=("nr3", "nr7", "inside_body"), nr_expansion="tag"),
    "B11_nr_expansion": dict(nr_tags=("nr7",), nr_expansion="no_chop_skip"),
    "B11_nr_expansion_nr3": dict(nr_expansion="tag"),                       # NR3 / NR7 count without nr_tags
    "B17.4_daily_range_tag": dict(daily_range_regime="tag"),
    "B17.4_daily_range_scalp": dict(daily_range_regime="scalp", drr_days=4, drr_net_frac=0.6),
    "B17.4_daily_range_skip": dict(daily_range_regime="skip", drr_range_mult=3.0),
    "B17.4_daily_range_all_tests": dict(daily_range_regime="skip", drr_tests=("range", "inside_bisi", "premium_run")),
    "B15_org_tell_tag": dict(org_tell="tag"),
    "B15_org_tell_filter": dict(org_tell="filter"),
    "B15_org_tell_filter_wait": dict(org_tell="filter", org_tell_wait=True, org_tell_level=0.25),
    "B15_org_bias_gap_filter": dict(org_bias_gap="filter"),
    "B15_org_bias_gap_filter_react": dict(org_bias_gap="filter", org_bias_src="react", org_gap_fill_frac=0.25),
    "B16_sunday_scenario_tag": dict(sunday_scenario="tag"),
    "B16_sunday_scenario_filter": dict(sunday_scenario="filter"),
    "B16_sunday_no_gap_trade": dict(sunday_scenario="filter", sunday_no_gap_trade=True),
    "B16_sunday_scenario_filter_away2": dict(sunday_scenario="filter", sunday_away_mult=2.0, sunday_min_gap_pts=2.0),
    "N7.1_skip_holiday_eve": dict(skip_holiday_eve=True),
    "N7.1_skip_holiday_eve_bank": dict(skip_holiday_eve=True, holiday_eve_bank=True),
    "N7.1_early_close_flat_off": dict(early_close_flat=False),
    "N7.2_post_holiday_am_off": dict(skip_post_holiday_am=False),
    "N7.2_post_holiday_pre_open": dict(post_holiday_pre_open=True),
    "N7.2_post_holiday_pm_sync": dict(post_holiday_pm_sync=True),
    "N7.3_holiday_week_thu_fri": dict(holiday_week_thu_fri="trade", nfp_week_block=True),
    "N7.4_year_first_am_from_1000": dict(year_first_am_from=600),
    "Ep02.7_first_day_wait_1015": dict(first_day_wait=615),
    "Ep02.7_first_day_skip_am": dict(first_day_skip_am=True),
    "Ep01.8_low_vol_inside_scalp": dict(low_vol_inside="scalp"),
    "Ep01.8_low_vol_inside_skip": dict(low_vol_inside="skip", low_vol_holiday_adj=True),
    "N7.5_roll_week_half": dict(roll_risk=0.5),
    "N7.5_roll_week_src_data": dict(roll_week_src="data", roll_risk=0.5),
    "N7.5_roll_week_src_either": dict(roll_week_src="either", skip_roll_week=True),
    "N7.5_skip_roll_week": dict(skip_roll_week=True),
    "N7.6_august_half": dict(august_risk=0.5),
    "N7.6_august_half_last_two_weeks": dict(august_risk=0.5, august_from_day=15),
    "N7.6_skip_august": dict(skip_august=True, august_from_day=15),
    "N8.1_consol_skip_off": dict(consol_skip=False),
    "N8.2_trend_recipe_tag": dict(trend_recipe="tag"),
    "N8.2_trend_recipe_high_news_only": dict(trend_recipe="tag", trend_news=("high",)),
    "N8.2_trend_recipe_only": dict(trend_recipe="only"),
    "N8.2_trend_recipe_side": dict(trend_recipe="side", trend_contract=True, trend_small_frac=1.0, trend_array_days=3),
    "N8.3_consol_day_tag": dict(consol_day_rules="tag"),
    "N8.3_consol_predictors_report_auction": dict(consol_day_rules="tag", consol_predictors=("no_report", "auction")),
    "N8.3_consol_day_apply": dict(consol_day_rules="apply"),
    "N8.3_consol_pm_pools_on": dict(consol_day_rules="apply", consol_pm_pools=("pd", "on")),
    "N8.3_consol_day_apply_2pred": dict(consol_day_rules="apply", consol_min_predictors=2, consol_or_frac=0.35,
                                         consol_am_out=720, consol_pm_rule=False, consol_eq_tol=0.2),
    "N8.4_big_day_am_skip": dict(big_day_am_skip=True),
    "N8.4_big_day_am_skip_2x": dict(big_day_am_skip=True, big_day_range_mult=2.0, big_day_org_frac=0.3),
    "N8.5_expansion_due": dict(expansion_due=True),
    "N8.5_expansion_targets": dict(expansion_due=True, expansion_targets=(1.5, 2.0), expansion_frac=0.8),
    "N8.5_adr_basis_eth": dict(adr_basis="eth", expansion_due=True),
    "N8.6_sd_no_hold": dict(sd_no_hold=True),
    "N8.6_sd_no_hold_context": dict(sd_no_hold=True, sd_context_required=True, sd_week_news=False),
    "N8.6_sd_week_skip": dict(sd_week_skip="skip", sd_week_months=(7, 8)),
    "N8.6_sd_week_tag": dict(sd_week_skip="tag"),
    "N9.2_eve_draw": dict(eve_draw=True),
    "N9.2_pre_draw_pm": dict(pre_draw_pm=True, eve_draw=True),
    "N9.3_objective_done_skip": dict(objective_done_skip=True),
    "N9.4_min_on_range": dict(min_on_range_frac=0.3),
    "N9.4_min_on_range_globex": dict(min_on_range_frac=0.4, on_range_from="globex"),
    "N9.4_min_raid_pts": dict(min_raid_pts=2.0),
    "N9.4_min_raid_pts_london": dict(min_raid_pts=1.0, raid_ref="london"),
    "N9.5_macro_no_move": dict(macro_no_move=True),
    "N9.5_macro_no_move_pm": dict(macro_no_move=True, macro_no_move_pm=True, macro_move_pts=1.0, macro_ref_min=20,
                                    macro_no_move_wins=((590, 610),), macro_no_move_pm_wins=((890, 910),)),
    "N9.6_london_adr_skip_off": dict(london_adr_skip=0.0),
    "N9.6_london_adr_win_0800": dict(london_adr_win=(120, 480)),             # the earlier 02:00-08:00 window
    "N9.6_london_adr_skip_06": dict(london_adr_skip=0.6, london_adr_win=(120, 570)),
    "N10.2_monday_skip": dict(monday_mode="skip"),
    "N10.2_monday_pm_only": dict(monday_mode="pm_only"),
    "N10.2_monday_obvious": dict(monday_mode="obvious"),
    "D20_monday_small_range": dict(monday_small_range=0.6),
    "N10.2_tue_off_monday": dict(tue_off_monday="filter"),
    "N10.2_tue_off_monday_tag": dict(tue_off_monday="tag"),
    "N10.3_pool_mon_wed": dict(pool_mon_wed=True),
    "N10.3_mon_wed_extreme_tag": dict(mon_wed_extreme="tag"),
    "N10.3_thu_fri_break_side": dict(thu_fri_break="side"),
    "N10.4_friday_slow_split_off": dict(friday_slow_split=False),
    "N10_friday_first_pool": dict(friday_first_pool=True),
    "N10.4_friday_objective_scalp": dict(friday_objective="scalp"),
    "N10.4_friday_objective_skip": dict(friday_objective="skip"),
    "N10.4_friday_week_done_draw": dict(friday_week_done="draw"),
    "N10.4_friday_week_done_trades": dict(friday_week_done="trades"),
    "N10_strong_thu_no_long": dict(strong_thu_no_long=True),
    "N10_strong_thu_no_long_mirror": dict(strong_thu_no_long=True, strong_thu_mirror=True, strong_thu_mult=0.8, strong_thu_frac=0.3),
    "N10.4_no_fri_after_strong_thu": dict(no_fri_after_strong_thu=True),
    "T14_tue_week_extreme_side": dict(tue_week_extreme="side"),
    "T14_tue_week_extreme_tag": dict(tue_week_extreme="tag"),
    "M14_tgif_model": dict(tgif_model=True),
    "M14_tgif_model_skip_zone": dict(tgif_model=True, tgif_model_skip=("tgif_zone",)),
    "M14.1_tgif_htf_array": dict(tgif=True, tgif_htf_array=True),
    "M14.1_tgif_htf_array_4h": dict(tgif=True, tgif_htf_array=True, tgif_htf_tfs=("4h",)),
    "M14.3_tgif_timing": dict(tgif=True, tgif_timing=((600, 720), (810, 900))),
    "M14.3_tgif_week_sweep": dict(tgif=True, tgif_week_sweep=True),
    "X10d_am_range_skip_pm": dict(am_range_skip_pm=0.8),
    "X15d_week_done_on_draw": dict(week_done_on_draw="skip"),
    "X15d_week_done_nearest": dict(week_done_on_draw="skip", week_done_pick="nearest", week_done_levels=("pwh", "pwl")),
    "X15d_week_done_tag": dict(week_done_on_draw="tag"),
    "D19_max_3_week_in_engine": dict(max_trades_week=3, sb_model=True, ma_deuce=True),
    "D19_no_pm_after_win_be_loses": dict(no_pm_after_am_win=True, be_counts_as_win=False),
    "B23_seasonal_tag": dict(seasonal_tag=True),
    "B23_seasonal_map_flat": dict(seasonal_tag=True, seasonal_map=("cons",) * 12),
    "B23_seasonal_two_samples": dict(seasonal_tag=True, seasonal_map_b=("bear", "bull", "cons", "bull", "bull", "cons", "bull", "cons", "bear", "bull", "bull", "bull"),
                                       seasonal_fail_day=5),
    "X16_journal_tags_off": dict(journal_tags=False),
    # ---- package bias_htf (name prefix = rule id; the look-ahead test runs each one alone) ----
    "B2_ordered_pick": dict(draw_lock_pick="ordered"),
    "B2_htf_bias_ordered": dict(htf_bias="ordered"),
    "B2_draw_ext_target": dict(draw_lock_pick="ordered", draw_ext_target=True),
    "B3_largest_pick": dict(draw_lock_pick="largest"),
    "B3_want_all_engines_draw": dict(htf_bias="draw", want_all_engines=True),
    "B3_want_main_only_draw": dict(htf_bias="draw", want_all_engines=False),
    "B3_judas_filter": dict(judas_required="filter"),
    "B3_judas_tag": dict(judas_required="tag"),
    "B6_iof": dict(htf_bias="iof"),
    "B6_combo2": dict(htf_bias="combo2"),
    "B6_iof_days5": dict(htf_bias="iof", iof_days=5, iof_min=1),
    "L14_draw_first": dict(draw_first="session"),
    "L14_draw_first_no_cond": dict(draw_first="session", draw_first_skip=("cond",)),
    "L14a_draw_first_pick_only": dict(draw_first="session", draw_first_skip=("hygiene", "ext", "cond")),
    "L14_conf_hygiene": dict(target_hygiene=("htf",), htf_ce_draw=True, vi_htf_draw=True, vi_arrays=True),
    "L14c_matrix_tf_lower": dict(matrix_tf_lower=True),
    "L14e_cond_draw": dict(cond_draw=True),
    "B7_how_rule_tag": dict(how_rule="tag"),
    "B20.1_cot_tag_tag": dict(cot_tag="tag"),
    "B20.3_wpr_tag_tag": dict(wpr_tag="tag"),
    "B10_mwd_nest_tag": dict(mwd_nest="tag"),
    "B17.5_smt_both_tag": dict(smt_both="tag"),
    "L14e_cond_draw_umbrella": dict(draw_first="session", cond_draw=True),
    "B2_draw_ext_target_nearest": dict(draw_ext_target=True),
    "B3_bias_neutral_scalp": dict(htf_bias="combo2", bias_neutral="scalp"),
    "B3_bias_neutral_both": dict(htf_bias="combo2", bias_neutral="both"),
    "B5_news_topdown_tag": dict(news_topdown="tag", vi_arrays=True),
    "B5_weekly_gate_tag": dict(weekly_gate="tag"),
    "B9_objective_neutral_both": dict(htf_bias="combo", objective_neutral="both"),
    "B17.3_objective_met_stop_both": dict(objective_met_stop="both"),
    "B17_neutral_gate_range_market_tag": dict(neutral_gate=("range_market",), neutral_gate_mode="tag"),
    "B17_neutral_gate_range_market_skip": dict(neutral_gate=("range_market",), neutral_gate_mode="skip"),
    "B19.3_bond_range_skip": dict(bond_range="skip"),
    "B17.5_decoupled_skip": dict(decoupled_mode="skip", decouple_corr=0.97),

    "A21_pd_zone_third": dict(htf_bias="pd", pd_zone="third"),
    "A21_pd_zone_ote": dict(htf_bias="pd", pd_zone="ote"),
    "A21_pd_zone_deep": dict(htf_bias="pd", pd_zone="deep"),
    "A21.2_day_pd_20d": dict(htf_bias="pd", day_pd="20d"),
    "A21.2_pd20_bias": dict(htf_bias="pd20"),
    "A21.4_pd_bodies_off": dict(htf_bias="pd", day_pd="20d", pd_body_multiday=False),
    "B5_weekly_gate_filter": dict(weekly_gate="filter"),
    "B5_weekly_gate_bias": dict(htf_bias="wk"),
    "B5_news_topdown_side": dict(news_topdown="side", vi_arrays=True),
    "B5_bellwether_filter": dict(bellwether_15m="filter"),
    "B5_bellwether_tag": dict(bellwether_15m="tag"),
    "B7_ob_mt_bias": dict(htf_bias="ob_mt"),
    "B7_how_rule_no_long": dict(how_rule="no_long"),
    "B7_how_rule_no_short": dict(how_rule="no_short"),
    "B7_how_rule_both": dict(how_rule="both"),
    "B8_flip_all_triggers": dict(htf_bias="flip", flip_triggers=("ob_mt", "wk_dc", "flip_pd3", "flip_close_above", "flip_thu_wopen")),
    "B9_objective_neutral_day": dict(htf_bias="combo", objective_neutral="day"),
    "B9_objective_neutral_week": dict(htf_bias="combo", objective_neutral="week"),
    "B9_bias_persist2": dict(htf_bias="combo", bias_persist=2),
    "B9_next_array_on_fail": dict(htf_bias="combo", next_array_on_fail=True),
    "B10_mwd_bias": dict(htf_bias="mwd"),
    "B10_mwd_nest_filter": dict(htf_bias="mwd", mwd_nest="filter"),
    "B13_weekly_open_sun18": dict(weekly_open="sun18"),
    "B13_weekly_open_mon00": dict(weekly_open="mon00"),
    "B13_weekly_open_either": dict(weekly_open="either"),
    "B14.1_nwog_regime_scalp": dict(nwog_regime="scalp"),
    "B14.1_nwog_regime_skip": dict(nwog_regime="skip", nwog_returns_cons=1),
    "B14.2_nwog_converge_skip": dict(nwog_regime="skip", nwog_converge_pts=40.0),
    "B14.3_nwog_bias_filter": dict(nwog_bias="filter"),
    "B14.3_nwog_bias_ce": dict(htf_bias="nwog", nwog_bias_reclaim="ce"),
    "B17_neutral_gate_fifty": dict(neutral_gate=("fifty_fifty",), neutral_gate_mode="skip"),
    "B17_neutral_gate_premium_chop": dict(neutral_gate=("premium_chop",), neutral_gate_mode="skip"),
    "B17_neutral_gate_draw_delivered": dict(neutral_gate=("draw_delivered",), neutral_gate_mode="skip"),
    "B17_neutral_gate_range_market": dict(neutral_gate=("range_market",), neutral_gate_mode="scalp"),
    "B17_neutral_gate_decoupled": dict(neutral_gate=("decoupled",), neutral_gate_mode="skip", decouple_corr=0.97),
    "B17.1_neutral_5050_armed": dict(neutral_5050="armed"),
    "B17.1_neutral_5050_react": dict(neutral_5050="react"),
    "B17.3_objective_met_stop_day": dict(objective_met_stop="day"),
    "B17.3_objective_met_stop_week": dict(objective_met_stop="week"),
    "B17.5_decoupled_scalp": dict(decoupled_mode="scalp", decouple_corr=0.97),
    "B17.5_smt_both_skip": dict(smt_both="skip"),
    "B19_intermarket_model": dict(intermarket_model=True),
    "B19.1_dxy_gate_block": dict(dxy_gate="block"),
    "B19.3_bond_range_scalp": dict(bond_range="scalp"),
    "B19.3_bond_dir_filter": dict(bond_dir="filter"),
    "B20_cot_oi_model": dict(cot_oi_model=True),
    "B20.1_cot_tag_filter": dict(cot_tag="filter"),
    "B20.2_oi_tag": dict(oi_tag="tag"),
    "B20.3_wpr_tag_filter": dict(wpr_tag="filter"),
    "B22_qshift_tag": dict(qshift_tag=True),
    "B22_qshift_size_half": dict(qshift_size=0.5),
    "M0.1_bias_candle_D": dict(htf_bias="candle", bias_candle="D"),
    "M0.1_bias_candle_W": dict(htf_bias="candle", bias_candle="W"),
    "M0.1_bias_candle_D_midnight": dict(htf_bias="candle", bias_candle="D", bias_candle_open="midnight"),
    "M0.1_bias_candle_W_midnight": dict(htf_bias="candle", bias_candle="W", bias_candle_open="midnight"),
    "D15_smt_pick_trend": dict(smt_pick="trend"),
    "D15_one_market": dict(one_market=True),
    "D22_bias_open_src_spy": dict(bias_open_src="spy"),
    "D22_bias_open_src_es_map": dict(bias_open_src="es_map"),
    "Ep02.6_no_narrative_scalp": dict(no_narrative_scalp=True),
    "Ep03.12_draw_pd": dict(htf_bias="draw_pd", vi_arrays=True),
    "Ep03.12_mmbm_zone_filter": dict(mmbm_zone="filter"),
    "Ep06.6_midnight_target": dict(midnight_target=True),
    "Ep06.6_midnight_confirm_filter": dict(midnight_confirm="filter", htf_bias="combo"),
    "Ep06.6_midnight_below_ok": dict(midnight_confirm="tag", midnight_below_ok=True),
    "Ep08.2_chop_skip": dict(chop_mode="skip"),
    "Ep08.2_chop_scalp": dict(chop_mode="scalp"),
    "Ep08.3_bias_open_all": dict(bias_open="all"),
    "L14c_react_tf_tag": dict(react_tf_tag=True),
    "M0.1_bias_candle_tag": dict(bias_candle_tag=True),
    "A21_pd20_column_only": dict(cond_pd_tags=True),
    "Ep08.2_chop_skip_day": dict(chop_mode="skip_day"),
    "B14.3_nwog_bias_tag": dict(nwog_bias="tag"),
    "B14.2_nwog_converge_shrink": dict(nwog_regime="tag", nwog_converge_mode="shrink"),
}
# --- package silver_bullet (sb_model.py): one variant per switch, the Silver Bullet alone (name prefix = rule id) ---------
SB_ONLY = dict(sb_model=True, am=(0, 0), pm=(0, 0))
_SB_DECISIONS = {
    "M3_sb_only": dict(SB_ONLY),
    "M3_sb_mss_not_required": dict(SB_ONLY, sb_mss_required=False),
    "M3.3_sb_need_mss_off": dict(SB_ONLY, sb_need_mss=False),
    "D2_sb_fvg_in_window": dict(SB_ONLY, sb_fvg_in_window=True),
    "D2_sb_fvg_from_0945": dict(SB_ONLY, sb_fvg_from=585),
    "D2_sb_evolve_off": dict(SB_ONLY, sb_evolve=False),
    "D2_sb_mss_mode_wick": dict(SB_ONLY, mss_mode="wick"),
    "D2_sb_mt_mode_range": dict(SB_ONLY, mt_mode="range"),
    "E2_sb_entry_ce": dict(SB_ONLY, sb_entry="ce"),
    "gap16_sb_fvg_pick_first": dict(SB_ONLY, sb_fvg_pick="first"),
    "gap16_sb_fvg_pick_any_in_leg": dict(SB_ONLY, sb_fvg_pick="any_in_leg"),
    "gap17_sb_cancel_ticks3": dict(SB_ONLY, sb_cancel_ticks=3),
    "gap17_sb_cancel_sticky_off": dict(SB_ONLY, sb_cancel_sticky=False),
    # windows (T6, M3.1, gap 14)
    "T6_sb_london": dict(SB_ONLY, sb_london=True),
    "T6_sb_0700": dict(SB_ONLY, sb_0700=True),
    "T6_sb_last_hour": dict(SB_ONLY, sb_last_hour=True),
    "T6_sb_all_windows": dict(SB_ONLY, sb_london=True, sb_0700=True, sb_last_hour=True),
    "gap14_sb_moc_extra": dict(SB_ONLY, sb_moc_extra=True),
    "M3.1_sb_extra_pm2": dict(SB_ONLY, sb_extra=("pm2",)),
    "M3.1_sb_extra_early": dict(SB_ONLY, sb_extra=("early",)),
    # count (M3, M3.9, gap 14, gap 7)
    "M3_sb_one_per_day": dict(SB_ONLY, sb_london=True, sb_one_per_day=True),
    "M3.9_sb_cascade": dict(SB_ONLY, sb_london=True, sb_cascade=True),
    "M3.9_sb_one_market": dict(SB_ONLY, sb_one_market=True),
    "gap14_sb_max_per_window2": dict(SB_ONLY, sb_max_per_window=2),
    "gap14_sb_adds": dict(SB_ONLY, sb_adds=True),
    "gap7_sb_am_done": dict(SB_ONLY, sb_am_done=True),
    "gap7_sb_imm_tag": dict(SB_ONLY, sb_imm_tag=True),
    # direction filters
    "M3.2_sb_draw_first": dict(SB_ONLY, sb_draw_first=True),
    "SBdir_draw_first_day_dir_lock": dict(SB_ONLY, sb_draw_first=True, sb_day_dir="lock"),
    "SBdir_draw_first_day_dir_free": dict(SB_ONLY, sb_draw_first=True, sb_day_dir="lock", sb_day_dir_delivered="free"),
    "SBdir_day_dir_first_trade": dict(SB_ONLY, sb_day_dir="first_trade"),
    "L14g_sb_pw_pools_off": dict(SB_ONLY, sb_pw_pools=False),
    "L14g_sb_ote_draw": dict(SB_ONLY, sb_ote_draw=True),
    "L14g_sb_htf_fallback": dict(SB_ONLY, sb_draw_first=True, sb_htf_fallback=True),
    "L14g_sb_htf_targets": dict(SB_ONLY, sb_htf_targets=True),
    "M3.3_sb_use_bias_combo": dict(SB_ONLY, htf_bias="combo", bias_neutral="both", sb_use_bias=True),
    "SBdir_sb_weekly_require": dict(SB_ONLY, sb_weekly="require"),
    "SBdir_sb_weekly_tag": dict(SB_ONLY, sb_weekly="tag"),
    "SBdir_sb_weekly_skip_neutral": dict(SB_ONLY, sb_weekly="require", sb_weekly_neutral="skip"),
    "SBdir_sb_sync_require": dict(SB_ONLY, sb_sync="require"),
    "SBdir_sb_sync_dir": dict(SB_ONLY, sb_sync="require", sb_sync_mode="dir"),
    "SBdir_sb_spotty_skip": dict(SB_ONLY, sb_spotty="skip"),
    "SBdir_sb_spotty_tag": dict(SB_ONLY, sb_spotty="tag"),
    "SBdir_sb_disp_pts_1": dict(SB_ONLY, sb_disp_pts=1.0),
    "SBdir_sb_disp_leg_3": dict(SB_ONLY, sb_disp_leg_pts=3.0),
    "SBdir_sb_disp_range_2": dict(SB_ONLY, sb_disp_range_mult=2.0),
    # trigger / entry arrays
    "M3.5_sb_need_sweep": dict(SB_ONLY, sb_need_sweep=True),
    "M3.5_sb_sweep_max_2": dict(SB_ONLY, sb_sweep_max_pts=2.0),
    "gap5_sb_sweep_alt_discount": dict(SB_ONLY, sb_need_sweep=True, sb_sweep_alt="discount_array"),
    "gap6_sb_bpr_exclude": dict(SB_ONLY, sb_bpr_exclude=True),
    "gap21_sb_cons_wait": dict(SB_ONLY, sb_cons_wait=True),
    "gap18_sb_lrc_tag": dict(SB_ONLY, sb_lrc_mult=2.0, sb_lrc_mode="tag"),
    "gap18_sb_lrc_wait": dict(SB_ONLY, sb_lrc_mult=2.0, sb_lrc_mode="wait"),
    "gap18_sb_lrc_skip": dict(SB_ONLY, sb_lrc_mult=2.0, sb_lrc_mode="skip"),
    "gap13_sb_premise_htf_array": dict(SB_ONLY, sb_premise="htf_array"),
    "gap13_sb_premise_smt": dict(SB_ONLY, sb_premise="smt"),
    "gap13_sb_premise_either": dict(SB_ONLY, sb_premise="either"),
    "gap22_sb_nwog_tag": dict(SB_ONLY, sb_nwog_expansion="tag"),
    "gap22_sb_nwog_require": dict(SB_ONLY, sb_nwog_expansion="require"),
    "gap1_sb_ifvg_add": dict(SB_ONLY, sb_ifvg="add"),
    "gap1_sb_ifvg_prefer": dict(SB_ONLY, sb_ifvg="prefer"),
    "gap1_sb_ifvg_market": dict(SB_ONLY, sb_ifvg="prefer", sb_ifvg_market=True),
    "gap1_sb_ifvg_reaper": dict(SB_ONLY, sb_ifvg="add", sb_ifvg_reaper=True),
    "gap1_sb_ifvg_breaker_stop": dict(SB_ONLY, sb_ifvg="prefer", sb_ifvg_stop="breaker"),
    "gap9_sb_ob_entry": dict(SB_ONLY, sb_draw_first=True, sb_entry_arrays=("fvg", "ob")),
    "gap10_sb_confluence_tag": dict(SB_ONLY, sb_entry_arrays=("fvg", "confluence")),
    "gap10_sb_confluence_entry": dict(SB_ONLY, sb_entry_arrays=("fvg", "confluence"), sb_conf_mode="entry"),
    "gap15_sb_reverse_after_target": dict(SB_ONLY, sb_ote_draw=True, sb_reverse_after_target=True),
    "gap20_sb_simple": dict(SB_ONLY, sb_simple=True, sb_ote_draw=True),
    # stop (M3.8, gap 19, 045)
    "M3.8_sb_stop_fvg2": dict(SB_ONLY, sb_stop="fvg2"),
    "M3.8_sb_stop_entry_candle": dict(SB_ONLY, sb_stop="entry_candle"),
    "M3.8_sb_stop_fvg_ce": dict(SB_ONLY, sb_stop="fvg_ce"),
    "gap19_sb_stop_swing": dict(SB_ONLY, sb_stop="swing"),
    "gap19_sb_max_stop4_skip": dict(SB_ONLY, sb_max_stop_pts=4.0, sb_wide="skip"),
    "gap19_sb_max_stop4_size": dict(SB_ONLY, sb_max_stop_pts=4.0, sb_wide="size"),
    "E5_sb_abort_045": dict(SB_ONLY, sb_abort=True),
    # room (L15, gaps 2, 3) and exits (M3.11, gap 8)
    "L15_sb_room_mode_draw": dict(SB_ONLY, sb_room_mode="draw"),
    "gap2_sb_room10_overshoot3": dict(SB_ONLY, sb_room_pts=10.0, sb_room_overshoot_pts=3.0),
    "gap3_sb_room_untaken": dict(SB_ONLY, sb_room_untaken=True),
    "gap3_sb_org_chop": dict(SB_ONLY, sb_org_chop=True),
    "gap3_sb_org_chop_scalp": dict(SB_ONLY, sb_org_chop=True, sb_fail_mode="scalp"),
    "M3.11_sb_gap424": dict(SB_ONLY, sb_mgmt="gap424"),
    "M3.11_sb_ladder": dict(SB_ONLY, sb_mgmt="ladder"),                          # SB package review: the ladder exits
    "M3.11_sb_layered057": dict(SB_ONLY, sb_mgmt="layered057"),                  # (= gap424: an alias, kept for the record)
    "M3.3_sb_use_bias_po3": dict(SB_ONLY, htf_bias="combo", bias_neutral="both", sb_use_bias=True, use_bias=True),   # the PO3 test
    "review_sb_no_overlap_off": dict(SB_ONLY, sb_last_hour=True, sb_no_overlap=False),   # two SB positions at once (double risk)
    "review_sb_stop_entry_candle": dict(SB_ONLY, sb_stop="entry_candle"),        # 086 stop from the last closed bar (no look-ahead)
    "review_sb_conf_tol": dict(SB_ONLY, sb_entry_arrays=("fvg", "ob", "confluence"), sb_conf_mode="entry", sb_conf_min=3, sb_conf_tol_pts=2.0),
    "review_sb_cons_bars": dict(SB_ONLY, sb_cons_wait=True, sb_cons_bars=4),
    "review_sb_windows_shifted": dict(SB_ONLY, sb_windows=((600, 650), (840, 890))),
    "M3.11_sb_runner_if_weekly": dict(SB_ONLY, sb_runner=True, sb_runner_if_weekly=True),
    "gap8_sb_supercharge": dict(SB_ONLY, sb_runner=True, sb_supercharge=True),
}
DECISIONS.update(_SB_DECISIONS)
# caption-gap pass, levels_detectors #1/3 (digests/rulebook_gaps/*.md): one variant per switch, name prefix = the gap id. The FVG-path
# variants run the post-MSS entry (SM_POST) so the new entry zones can arm; look-ahead tests: tests/test_caption_gap_ld1.py.
_LD1_DECISIONS = {
    "X3-l8-vb-exhaustion-gap": dict(vacuum_blocks=True, vb_context=True),
    "X3-b21-ipda-anchor_month": dict(ipda_pools=True, ipda_anchor="month"),
    "X3-b21-ipda-anchor_swing": dict(ipda_pools=True, ipda_anchor="swing"),
    "B21-ipda-windows-arrays": dict(ipda_arrays_first20=True),
    "X3-b5-15m-pools-5m-gaps": dict(pool_swings=True, pool_tf=15),
    "X3-b10-topdown-transposition": dict(topdown_targets=True),
    "N8-consolidation-builds-orders": dict(consol_pools=True),
    "A11-bpr-one-pass-definition_single": dict(bpr_def="single_range", bpr_targets=True, bpr_abort=True),
    "A11-bpr-one-pass-definition_both": dict(bpr_def="both", bpr_targets=True, bpr_abort=True, bpr2_trail=True, bpr2_cont_trigger=True),
    "A11-bpr-one-pass-definition_two_candle": dict(bpr_def="single_range", bpr_targets=True, bpr2_two_candle=True),
    "X-efficient-delivery-two-pass": dict(two_pass_state=True, fvg_targets=True),
    "X-efficient-delivery-two-pass_shield2": dict(two_pass_state=True, fvg_targets=True, shield_passes=2),
    "A12-ob-candle-selection_original": dict(ob_pick="original"),
    "A12-ob-candle-selection_largest_body": dict(ob_pick="largest_body"),
    "A12-ob-candle-selection_blend_in_htf": dict(ob_pick="blend_in_htf"),
    "A12-ob-candle-selection_skip_encapsulated": dict(ob_skip_encapsulated=True),
    "A12-consolidation-ob-open-level": dict(cons_ob_open=True, entry_arrays=("cons_ob_open",), **SM_POST),
    "A8-inversion-any-pd-array": dict(inversions=("ob", "breaker", "vi", "org", "nwog"), **SM_POST),
    "A12-mt-all-blocks-ce-all-gaps": dict(mit_targets=True, mit_mt_invalid=True),
    "A13-breaker-candle-selection_last": dict(breaker_candle="last", breaker_entry="fallback", **SM_POST),
    "A13-breaker-candle-selection_extreme_body": dict(breaker_candle="extreme_body", breaker_body_swing=True, breaker_entry="fallback", **SM_POST),
    "A13-breaker-zone-extent_blend": dict(breaker_zone="blend", breaker_entry="fallback", **SM_POST),
    "A13-breaker-zone-extent_leg_disruptor": dict(breaker_zone="leg_disruptor", breaker_entry="fallback", **SM_POST),
    "A6-breakaway-identification_context": dict(breakaway="hold", breakaway_def="context", **SM_POST),
    "A6-breakaway-identification_context_wide": dict(breakaway="hold", breakaway_def="context", breakaway_ctx_pts=20.0, **SM_POST),
    "A6-breakaway-identification_second_mss": dict(breakaway="hold", breakaway_def="second_mss", **SM_POST),
    "A5-caffeine-bar-bisi": dict(single_bar_fvg_strict=True, **SM_POST),
    "A5-broken-fvg-reclaim": dict(fvg_reclaim=True, **SM_POST),
    "B5-htf-arrays-anchor-transpose": dict(htf_entry_arrays=(15, 60), **SM_POST),
    "N-initial-fvg-reference": dict(initial_fvg=("day", "week", "mon10")),
    "A9-vi-definition-no-wick-condition": dict(vi_arrays=True, vi_wick_overlap=False, vi_entries=True),
    "A9-vi-definition-no-wick-condition_multi": dict(vi_arrays=True, vi_wick_overlap=False, vi_multi=True, vi_entries=True),
    "A9-vi-delivery-state_overlap": dict(vi_arrays=True, vi_dead_rule="overlap", vi_targets=True),
    "A9-vi-delivery-state_two_sided": dict(vi_arrays=True, vi_two_sided_draw=True, vi_targets=True),
    "A9-daily-vi-forward-levels": dict(vi_flip_support=True),
    "A9-daily-vi-forward-levels_entries": dict(vi_flip_support=True, vi_flip_entries=True),
    "A16-propulsion-context-sequence_cc04_008": dict(pb_def="cc04_008", prop_entry=True, **SM_POST),
    "A16-propulsion-context-sequence_cc09_008": dict(pb_def="cc09_008", prop_entry=True, **SM_POST),
    "A17-rejection-block-levels_open_close": dict(rb_level="open_close", rb_targets="ladder"),
    "A17-rejection-block-levels_close": dict(rb_level="close", rb_targets="ladder", rb_ce_level=True),
    "A21-dealing-range-energetic-swing": dict(leg_anchor="energetic"),          # acts through leg_pd (the Params default 0.5)
    "A23-wick-quarter-strength": dict(wick_quarters=True, wick_bias_line=True, judas_wick_cap=True),
    "confluence-stacked-arrays": dict(converge_rank=True, **SM_POST),
    "A3-diagonal-support-is-liquidity": dict(diag_pools=True),
    "A3-diagonal-support-is-liquidity_4": dict(diag_pools=True, diag_min_swings=4),
}
DECISIONS.update(_LD1_DECISIONS)
# caption-gap pass, levels_detectors #2/3 (digests/rulebook_gaps/*.md): one variant per switch, name prefix = the gap id; look-ahead
# tests: tests/test_caption_gap_ld2.py (+ the per-variant ES run of test_bias_htf_lookahead.py).
_LD2_DECISIONS = {
    "A2-which-old-high": dict(active_old_pool=True),
    "A2-round-number-pool_confluence": dict(round_pool_mode="confluence"),
    "A2-round-number-pool_tag_only": dict(round_pool_mode="tag_only"),
    "A3-engineered-liquidity": dict(engineered_pools=True),
    "L1-rth-session-pools": dict(rth_pool_spent=True, extra_pools=True),
    "L3-midnight-session-opening-ranges": dict(session_ors=((0, 30), (0, 60), (120, 30), (810, 30))),
    "L5-partial-redelivery": dict(nwog_rebalanced=True),
    "L5-cfd-nwog-mapping_monday_0930": dict(nwog_cfd_src="monday_0930"),
    "L5-cfd-nwog-mapping_sunday_else_monday": dict(nwog_cfd_src="sunday_else_monday"),
    "A2-open-float": dict(open_float_pools=True),
    "A11-htf-gap-own-tf_legacy": dict(balance_tf="legacy"),
    "A11-htf-gap-own-tf_next_lower": dict(balance_tf="next_lower"),
    "A7-immediate-rebalance-definition_open_space": dict(ir_def="open_space", ir_entries=True, htf_bias="combo"),
    "A7-immediate-rebalance-definition_zero_width": dict(ir_def="zero_width", ir_entries=True, htf_bias="combo"),
    "A12-open-vs-wick-gap-criterion": dict(ob_anchor_rule="gap_presence", ob_entry="both", ob_entries="fallback"),
    "A5-twice-traded-not-fvg": dict(ob_anchor_rule="gap_presence", ob_zone="sensitive", ob_entry="both"),
    "A12-tf-relative-ob": dict(htf_ob_ltf_drill=True),
    "A6-breakaway-depth-qualification": dict(bk_depth="any_open", bk_state=True, bk_bpr_ce=True, breakaway="tag", ladder_trail="breakaway", **SM_POST),
    "A9-vi-breakaway": dict(vi_entries=True, vi_breakaway=True, **SM_POST),
    "A6-gap-hierarchy-common": dict(gap_classes=True, trail_skip_common=True, trail_first_fvg=True, breakaway="tag", **SM_POST),
    "new-single-candle-daily-inefficiency": dict(single_pass_draw=True),
    "A5-vi-extended-ce": dict(fvg_vi_extend=True, fvg_vi_extend_ce=True, vi_arrays=True, **SM_POST),
    "A11-balanced-range-body-filled": dict(balanced_range=True),
    "M1-original-consolidation": dict(mmxm_ctx=True, orig_consol=True, **SM_POST),
    "A21-consolidation-range-def": dict(consol_pools=True, consol_body_range=True, consol_eq_touches=2),
    "A3-clean-high": dict(eq_min_sep_bars=3),
    "A12-void-up-down-ob": dict(void_rt_ob=True),
    "A15-stoprun-variant": dict(mit_def="stoprun", mit_targets=True),
    "M4-failure-swing-no-new-extreme": dict(fs_def="no_new_extreme", cc_swings="failure", cc_fail_pts=5.0),
    "B21-data-range-fv-eq": dict(ipda_pools=True, ipda_fv=True, ipda_consol_eq=True, ipda_eq_day="tag"),
}
DECISIONS.update(_LD2_DECISIONS)
# caption-gap pass, levels_detectors #3/3 (digests/rulebook_gaps/*.md): one variant per switch, name prefix = the gap id; look-ahead tests:
# tests/test_caption_gap_ld3.py (+ the per-variant ES run of test_bias_htf_lookahead.py).
_LD3B_DECISIONS = {
    "L5-rth-and-eth-gap-views": dict(gap_views="both"),
    "L5-holiday-nwog": dict(nwog_skip_holiday=True, nwog_holiday_pick="closest", htf_bias="combo", weekly_open="sun18", tue_open_ref=True),
    "L7-org-lifetime-sr": dict(org_days=60, org_both_ways=True),
    "L10-older-daily-weekly-wick-ce": dict(wick_levels=True, wick_days=10, wick_weekly=True, wick_weeks=3, wick_untraded=True, wick_lod_tag="tag"),
    "new-reactionary-high-liquidity": dict(reactionary_pools=True),
    "new-parent-pool-bodies-short": dict(parent_pools=True),
    "L2-sr-needs-fvg": dict(daily_level_needs_array="fvg"),
    "L1-prior-day-london-pm-pools": dict(prev_london_pool=True, extra_pools=True),
    "new-lookback-per-tf-topdown": dict(tf_lookback={"D": 252, "4h": 63, "1h": 15, "15m": 4}),
    "L3-monthly-ohlc-3m": dict(monthly_ohlc=True),
    "L3-htf-pd-arrays-intraday": dict(htf_targets=("15m", "1h", "4h", "D", "W", "M")),
    "L3-3-6-12-month-pools": dict(ipda_pools=True, ipda_windows=(20, 40, 60, 63, 126, 252)),
    "new-trendline-trap-target": dict(trendline_pools=True),
    "B21-reference-points-in-windows": dict(ipda_pools=True, ipda_rb=True, ipda_arrays=True),
    "B21-progression-20-40-60-beyond": dict(ipda_next=True, ipda_roll_arrays=True, ipda_beyond_days=120),
    "B21-open-float-forward-windows": dict(ipda_pools=True, ipda_anchor="current_month", ipda_forward=True),
    "B21-anchor-month-vs-daily_current_month": dict(ipda_pools=True, ipda_anchor="current_month"),
    "B21-anchor-month-vs-daily_daily": dict(ipda_pools=True, ipda_anchor="daily"),
    "LLT3-london-extreme-preny-range_tag": dict(london_lr_zone="tag"),
    "LLT3-london-extreme-preny-range_require": dict(london_lr_zone="require", htf_bias="combo"),
    "LLT3-0800-0900-pool-stock-open": dict(or0809_pool=True),
    "A17-rejection-block-short-protocol": dict(rb_pools=True),
    "A12-entry-ob-outside-fvg": dict(ob_outside_fvg=True, ob_entry="both"),
    "new-trendline-trap": dict(trendline_trap=True, htf_bias="combo"),
    "new-hs-fade": dict(hs_fade=True, htf_bias="combo", hs_tf=15, hs_stop_pts=10.0),
    "new-intra-week-extreme-raid": dict(week_pools=True),
    "T4-or-length_20": dict(or_minutes=20),
    "L3-or-refs-expire-1100": dict(or_expire=660, or_fvg_entries=True),
    "new-time-distortion": dict(time_distortion=True, td_lunch=True, td_fvg_hold=True, single_bar_fvg_strict=True),
}
DECISIONS.update(_LD3B_DECISIONS)
# caption-gap pass, levels_detectors #3/3 REVIEW FIXES: one variant per added switch (name prefix = the gap id)
_LD3C_DECISIONS = {
    "L2-sr-needs-fvg_flip_retest": dict(daily_level_needs_array="fvg", flip_retest_entry=True, htf_bias="combo"),
    "new-trendline-trap_entries": dict(trendline_trap=True, tl_trap_entries=("ob", "breaker"), htf_bias="combo"),
    "new-trendline-trap-target_adr_tol": dict(trendline_pools=True, trendline_trap=True, tl_tol_adr=0.1, htf_bias="combo"),
    "new-hs-fade_rearm": dict(hs_fade=True, hs_rearm=True, htf_bias="combo", hs_tf=15, hs_stop_pts=10.0),
    "L3-htf-pd-arrays-intraday_monthly": dict(htf_monthly_arrays=True, htf_bias="combo", htf_targets=("15m", "1h", "4h", "D", "W", "M")),
    "new-lookback-per-tf-topdown_pools": dict(tf_lookback={"D": 252, "4h": 63, "1h": 15, "15m": 4}, tf_pools=True, pool_rank=True, rel_tfs=(60, 240)),
    "B21-reference-points-in-windows_arrays": dict(ipda_pools=True, ipda_anchor="current_month", ipda_arrays=True, ipda_window_arrays=True,
                                                   ipda_frame=True, tf_lookback={"D": 252}),
    "B21-progression-20-40-60-beyond_converge": dict(ipda_next=True, ipda_roll_arrays=True, ipda_converge=True),
    "B21-open-float-forward-windows_recompute": dict(ipda_pools=True, ipda_anchor="month", ipda_forward=True, ipda_recompute=True),
    "L3-monthly-ohlc-3m_frame": dict(monthly_ohlc=True, monthly_frame=True, converge_rank=True),
    "LLT3-london-extreme-preny-range_ny_frame": dict(london_lr_zone="tag", ny_hl_frame=True),
    "L5-holiday-nwog_midnight": dict(nwog_skip_holiday=True, nwog_holiday_pick="closest", htf_bias="combo", weekly_open="sun18", tue_open_ref=True,
                                     tue_open_time="midnight"),
    "L7-org-lifetime-sr_revisit_gate": dict(org_days=60, org_both_ways=True, org_revisit_gate=True),
    "new-reactionary-high-liquidity_precond": dict(reactionary_pools=True, reactionary_precond=True),
}
DECISIONS.update(_LD3C_DECISIONS)
# caption-gap pass, setups_models #1/7 (36 specs of rulebook_gaps/bias_htf_intermarket.md, day_selection_news_calendar.md, definitions_pd_arrays_structure.md): one
# variant per behaviour switch, named by the gap id (name prefix = the id). Switches that need an MSS or a bias carry them.
_SM1_DECISIONS = {
    "BH-B12-midnight-open-tolerance": dict(open_tol_pts=3.0, **SM_POST),
    "BH-B12-midnight-open-tolerance_wk_open": dict(wk_open_side=True),
    "BH-B12-po3-sequence": dict(po3_seq="tag", **SM_POST),
    "BH-B12-po3-sequence_filter": dict(po3_seq="filter", **SM_POST),
    "BH-A8-opposing-FVG-inversion-confirms": dict(ifvg_narrative="block", htf_bias="combo", **SM_POST),
    "BH-A8-opposing-FVG-inversion-confirms_require": dict(ifvg_narrative="require", htf_bias="combo", **SM_POST),
    "BH-B12-gap-up-short-below-0930": dict(gap_premium_arm=True),
    "BH-compressed-higher-highs": dict(compressed_hh=True, htf_bias="combo"),
    "BH-D15-sick-sister-laggard": dict(smt_pick="laggard_objective"),
    "BH-D15-sick-sister-laggard_consol_only": dict(smt_pick="laggard_objective", laggard_consol_only=True),
    "BH-D15-middle-index": dict(smt_pick="middle"),           # inert with the two books these studies run (needs a third series, study_pick)
    "BH-D15-clean-swing-point": dict(smt_pick="clean_swing"),
    "D15-short-index-by-premium-depth": dict(smt_pick="depth"),
    "BH-M3-scan-all-indices": dict(markets=("ES", "NQ")),
    "BH-three-pool-runs-exhaustion": dict(pool_runs_max=3),
    "BH-premium-FVG-CE-vs-far-edge-trap": dict(far_edge_trap=True),
    "B18-am-smt-window-points": dict(smt_pre=True, smt_windows=((570, 660),), smt_win_a=120, smt_win_b=660, smt_open_points=True, smt_ref_window=True),
    "NEW-low-of-day-zone-tag-first": dict(lod_zone_first=True),
    "B18-smt-only-with-bias": dict(smt_with_bias=True, htf_bias="combo"),
    "B5-mature-trend-continuation": dict(mature_flag_block=True),
    "M12-classic-patterns-fade": dict(hs_fade=True, htf_bias="combo", hs_tf=15, hs_stop_pts=10.0),      # already built (levels_detectors#3: hs_fade)
    "X3-a15-mitblock-bear-context": dict(mitigation_entry=True, mit_needs_bias=True, htf_bias="combo"),
    "X3-graduated-pricing-second-touch": dict(touch_tag=True),
    "B12-judas-depth-adr": dict(judas_max_adr=0.4),
    "T3-london-close-multiday-reversal": dict(lc_tag=True, lc_reentry=True),
    "D15-which-index-contradiction": dict(smt_pick="swept"),
    "D15-which-index-contradiction_fixed_es": dict(smt_pick="fixed_es"),
    "B18-pm-smt-reference-points": dict(smt_pm_points=True),
    "N1-nfp-release-4h-fvg": dict(nfp_release_fvg=True, htf_bias="combo"),
    "N6-nfp-first-move-fake-if-liquidity": dict(news_profile="pool_test"),
    "N5-entry-at-release": dict(post_news_continuation=True, htf_bias="combo"),
    "N5-entry-at-release_release_ob": dict(release_ob_entry=True, htf_bias="combo"),
    "T13-judas-news-driver": dict(require_judas_news=True, judas_news_tag=True),            # the tag (require_judas_news gates only together with require_judas)
    "T13-judas-news-driver_require": dict(require_judas=True, judas_window=600, require_judas_news=True),     # the default +-30 minute window around a release (a wide judas_window so a 10:00 release day can back a 10:10 sweep)
    "DS2-two-session-close-templates": dict(profile_two_session=True, htf_bias="combo", extra_pools=True),
    "DS2-am-move-pm-reversal-templates": dict(pm_reversal=True, pm_reversal_pool="lunch_or_am", pm_reversal_ltf_only=True, extra_pools=True),
    "DS2-consolidation-profiles": dict(profile_consol_pm=True),
    "A13-breaker-needs-rebalance-and-fvg": dict(breaker_needs_disp=True, breaker_break_ref="body_high", **SM_POST),
    "A13-breaker-close-vs-wick": dict(breaker_by_close=True, mss_mode="wick", breaker_ll=False, **SM_POST),
    "A13-breaker-lifetime": dict(breaker_day_life=True, breaker_keep_original=True, **SM_POST),
    "A19-break-against-htf-stop-run": dict(mss_requires_htf_agreement=True, stoprun_rearm=True, htf_bias="combo", **SM_POST),
    "A5-short-into-htf-sibi": dict(htf_sibi_short_zone=True, htf_sibi_need_smt=True, **SM_POST),
    "A15-mitigation-block-entry": dict(mitigation_entry=True, htf_bias="combo"),
    "A15-mitigation-block-entry_mid": dict(mitigation_entry=True, mit_entry_px="mid", htf_bias="combo"),
    # review fixes (setups_models#1/7): the sub-cases the first build left out
    "DS2-two-session-close-templates_am": dict(profile_two_session=True, two_session_am=True, two_session_catalyst=True, htf_bias="combo", extra_pools=True),
    "DS2-consolidation-profiles_am": dict(profile_consol_am=True),
    "A13-breaker-lifetime_accumulate": dict(breaker_day_life=True, breaker_accumulate=True, **SM_POST),
    "A15-mitigation-block-entry_preopen": dict(mitigation_entry=True, mit_preopen=True, htf_bias="combo"),
    "B12-judas-depth-adr_tag": dict(judas_depth_tag=True),
}
DECISIONS.update(_SM1_DECISIONS)

# --- caption-gap pass, setups_models #2/7 (definitions_pd_arrays_structure.md, levels_liquidity_targets.md): one variant per gap id (name prefix = the gap id) ---
_SM2_DECISIONS = {
    "A5-premium-half-daily-fvg": dict(dfvg_half="tag"),
    "A5-premium-half-daily-fvg_skip": dict(dfvg_half="skip"),
    "L5-nwog-sr-levels": dict(nwog_sr_entries=True, htf_bias="combo", nwog_regime="tag"),
    "new-stop-run-overshoot-next-array": dict(turtle_soup="2023", ts_next_array=True, **SM_POST),
    "new-stop-run-overshoot-next-array_cc_limit": dict(turtle_soup="cc_limit", ts_next_array=True, htf_bias="combo"),
    "L5-quarter-level-no-imbalance": dict(gap_quarter_retrace=True),
    "L6-ndog-nwog-primary-entry": dict(gap_edge_entry=True, htf_bias="combo"),
    "L7-gap-up-premium-template": dict(org_two_rally=True),
    "A18-reclaimed-ob-codeable": dict(reclaimed_ob=True, reclaimed_def="loose", **SM_POST),
    "A18-reclaimed-ob-codeable_strict": dict(reclaimed_ob=True, **SM_POST),
    "A18-traded-through-ok": dict(reclaimed_ob=True, **SM_POST),                       # already built (levels.reclaimed_obs keeps the overrun candidates): the same run as the strict definition
    "A19-mss-when-raid-missing": dict(mss_ref_raid=True, **SM_POST),
    "A19-mss-no-rel-sweep-with-htf-draw": dict(mss_eq_wait=True, mss_eq_wait_unless_draw=True, ob_entry="post_mss", htf_resist_cap=False),      # draw_lock stays "session": the waiver needs the locked draw
    "A19-reh-short-term-low-trap": dict(reh_trap=True, htf_bias="combo", **SM_POST),
    "N-micro-structure-regime": dict(micro_regime=True, **SM_POST),
    "M12-second-takeout-turtle-soup": dict(turtle_soup="2023", ts_skip_reswept=True, second_break_partial=True, **SM_POST),
    "A21-pre-trigger-dealing-range": dict(breaker_entry="fallback", breaker_range_hold=True, **SM_POST),
    "A21-pre-trigger-dealing-range_trigger": dict(breaker_entry="fallback", breaker_range_trigger=True, **SM_POST),
    "A8-ifvg-narrative-liquidity-run": dict(ifvg_entries=True, ifvg_need_run=True, ifvg_over_pool_pref=True, htf_bias="combo", **SM_POST),
    "A8-ifvg-narrative-liquidity-run_quadrant": dict(ifvg_entries=True, ifvg_entry="quadrant", ifvg_need_run=True, ifvg_far_edge_tag=True, htf_bias="combo", **SM_POST),
    "A8-ifvg-stacked-tails-exclusion": dict(ifvg_entries=True, ifvg_tails_block=True, **SM_POST),
    "A7-immediate-rebalance-gates": dict(ir_entries=True, htf_bias="combo"),
    "A7-immediate-rebalance-gates_ungated": dict(ir_entries=True, ir_need_draw=False, ir_need_window=False, htf_bias="combo"),
    "A11-bpr-levels-ce-rejection": dict(entry_arrays=("bpr_ce",), **SM_POST),
    "A11-bpr-levels-ce-rejection_both": dict(entry_arrays=("bpr_ce",), bpr_def="both", bpr_left_far_edge=True, **SM_POST),
    "A12-range-internal-ignore": dict(range_lock=True, **SM_POST),
    "A19-second-mss-no-new-low": dict(mss_rearm_lower_high=True, **SM_POST),
    "A24-reaper-definition": dict(reaper=True, reaper_def="ob_overlap", **SM_POST),
    "A4-wick-poke-vi-invalidation": dict(poke_high_cancel=True, **SM_POST),
    "A8-ifvg-before-pool": dict(ifvg_entries=True, ifvg_pool_intact=True, **SM_POST),
    "A8-ifvg-depth-tolerances": dict(ifvg_entries=True, ifvg_depth="w_cap", **SM_POST),
    "A2-delivery-vs-liquidity": dict(mmxm_ctx=True, mm_ssl_target=True, **SM_POST),
    "A4-ltf-body-qualification": dict(htf_entry_arrays=(15, 60), htf_body_qual=True, **SM_POST),
    "new-state-to-array-map": dict(state_machine=True, state_tool_map=True, **SM_POST),
    "A4-sweep-body-cluster": dict(sweep_ref="body", daily_first_return=True, **SM_POST),
    "A4-sweep-body-cluster_ltf": dict(sweep_ref="body", daily_first_return=True, daily_first_ltf=True, **SM_POST),
    "B18-smt-accum-distrib": dict(turtle_soup="2023", ts_need_smt=True, **SM_POST),
    "new-divergence-types": dict(div_tag=True, **SM_POST),
    "A17-index-or-rejection-block": dict(or_rb=True),
    "A22-htf-definition-nested-arrays": dict(pm_reversal=True, pm_rev_nested=True, extra_pools=True),
    "new-consolidation-exit-direction": dict(consol_fade=True, htf_bias="combo"),
    "new-price-engine-models": dict(),                                                  # a tag only (Trade.setup_model, always on): the default run carries it
    "new-intermediate-term-hl-fade": dict(turtle_soup="2023", ts_itl_context=True, extra_pools=True, **SM_POST),
    "B18-smt-three-point-swing": dict(smt_mode="three_point", smt_pre=True, smt_windows=((570, 660),), **SM_POST),
}
DECISIONS.update(_SM2_DECISIONS)

# --- caption-gap pass, setups_models #3/7 (levels_liquidity_targets.md, management_partials_trailing_exits.md, models_setups_entries.md): one variant per gap id (name prefix = the gap id) ---
_SM3_DECISIONS = {
    "A23-1h-wick-ce-sweep-depth": dict(wick_sweep_depth=True, **SM_POST),
    "new-shallow-rel-sweep-one-more-drive": dict(shallow_sweep_wait=True, **SM_POST),
    "new-leg-grading-quadrants": dict(leg_grade_gate="require", **SM_POST),
    "new-leg-grading-quadrants_tag": dict(leg_grade_gate="tag", leg_origin="session_low", **SM_POST),
    "L7-org-later-day-entry-array": dict(org_entry_array=True, org_entry_confl=False, htf_bias="combo", **SM_POST),
    "L7-org-later-day-entry-array_confl": dict(org_entry_array=True, htf_bias="combo", **SM_POST),                   # (092: the default - another array within 4 ticks required)
    "new-eq-stop-hunt-entry": dict(eq_hunt="prefer", pool_swings=True, **SM_POST),
    "new-prev-day-range-eq-long": dict(prev_eq_long=True, **SM_POST),
    "new-retrace-to-recapitalized-ob": dict(recap_ob_entry=True, htf_bias="combo", **SM_POST),
    "new-retrace-to-recapitalized-ob_nearest": dict(recap_ob_entry=True, unfulfilled_nearest=True, htf_bias="combo", **SM_POST),
    "M1-turning-level-types": dict(am_discount_array=True, mm_turn_types=("ob", "fvg", "old_high", "old_low", "void"), **SM_POST),
    "new-vb-target": dict(vb_trade=True, vb_min_gap_pts=0.5, **SM_POST),
    "new-vb-target_close_above": dict(vb_trade=True, vb_min_gap_pts=0.5, vb_entry="close_above", vb_back_full=True, **SM_POST),
    "L2-raid-level-rolls": dict(turtle_soup="cc_limit", raid_roll=True, ts_cc_below_pts=0.25, htf_bias="combo", **SM_POST),
    "B1-nearby-unrun-high-trap": dict(near_pool_block=True, **SM_POST),
    "L13-weekly-high-london-swing": dict(wk_high_proj=True, weekly_bias=True, weekly_gate="tag", **SM_POST),
    "M4-swept-low-age": dict(turtle_soup="2023", ts_age_rank="prefer", ts_linger_bars=2, **SM_POST),
    "LLT3-equal-highs-fade-condition": dict(reh_fade_gate=True, htf_bias="combo", **SM_POST),
    "LLT3-judas-depth-third-adr": dict(judas_max_adr=0.33),                                       # already built (judas_max_adr)
    "LLT3-consolidation-lunch-vs-am-extreme": dict(profile_consol_pm=True),                       # already built (profile_consol_pm)
    "LLT3-lunch-hl-raid-not-target": dict(pm_lunch_raid=True, htf_bias="combo"),
    "X3-hs-fade-targets": dict(hs_fade=True, htf_bias="combo", hs_tf=15, hs_stop_pts=10.0),       # already built (levels_detectors#3: hs_fade)
    "M11-immediate-rebalance-management": dict(ir_entries=True, ir_filters=True, ir_accel_hold=True, htf_bias="combo"),
    "M14-tgif-draw-hit-first-sd-depth": dict(tgif_model=True, tgif_need_draw=True, tgif_sd_exit=True),
    "M15-ma-deuce-ladder": dict(ma_deuce=True, ma_deuce_ladder=True, md_second=True),
    "M16-sick-sister-exit-ladder": dict(ss_ladder=True),                                           # (the ladder acts under sick_sister, which needs the partner index and so makes no trade in the single-index ES look-ahead windows: tested in the synthetic partner runs, SYN_CASES "sick_sister")
    "A15-mitigation-block-targets": dict(mitigation_entry=True, mb_targets=True, mb_done_at_htf=True, htf_bias="combo"),
    "A15-mitigation-block-body-hold": dict(mitigation_entry=True, mb_body_exit=True, htf_bias="combo"),
    "new-vb-post-fill-management": dict(vb_trade=True, vb_min_gap_pts=0.5, **SM_POST),
    "new-counter-bias-scalp-exit": dict(counter_scalp=True, htf_bias="combo", **SM_POST),
    "M4-immediate-response-swept-extreme": dict(sweep_max_linger=2, **SM_POST),
    "M4-immediate-response-swept-extreme_fs": dict(sweep_max_linger=2, fs_sweep_close=True, cc_swings="failure", cc_fail_pts=5.0, fs_def="no_new_extreme", **SM_POST),
    "X9-repeated-array-taps": dict(breaker_max_taps_for_entry=2, breaker_entry="fallback", **SM_POST),
    "M5-lasthour-draw-frozen-noon": dict(last_hour_own_slot=True, lh_draw_freeze=True),
    "M1-three-entry-plans": dict(mm_plan="full", mmxm_ctx=True),
    "M1-three-entry-plans_mss_scalp": dict(mm_plan="mss_scalp"),
    "M1-three-entry-plans_pyramid": dict(mm_plan="pyramid", adds=(0.5, 0.5)),
    "M4-unicorn-sequence-preopen-breaker": dict(unicorn_preopen=True, unicorn_pref=True, breaker_entry="fallback", **SM_POST),
    "M4-accumulate-in-breaker-needs-bias-draw": dict(breaker_need_bias_draw=True, breaker_entry="fallback", adds_in_breaker=True, htf_bias="combo", **SM_POST),
    "M1-sell-model-fail-to-reach-CE": dict(ce_fail_entry=True, htf_bias="combo", **SM_POST),
    "M1-inside-fvg-expansion-only": dict(expansion_ce_entry=True, draw_lock="session", htf_resist_cap=False, ob_entry="post_mss"),
    "M7-pm-1330-judas-full": dict(pm_judas_array=True, pm_need_htf_target=True, pm_lunch_fvg_array=True, **SM_POST),
    "M1M2-htf-array-replaces-sweep": dict(allow_htf_array_premise=True, **SM_POST),
}
DECISIONS.update(_SM3_DECISIONS)

# --- caption-gap pass, setups_models #4/7 (models_setups_entries.md): one variant per gap id (name prefix = the gap id) ---
_SM4_DECISIONS = {
    "new-falling-dagger-upper-half-buy": dict(dagger_entry=True, htf_bias="combo", **SM_POST),
    "new-falling-dagger-upper-half-buy_ltf": dict(dagger_entry=True, dagger_level="ltf", htf_bias="combo", **SM_POST),
    "M12-0930-htf-fvg-stab-no-mss": dict(turtle_soup="htf_stab", **SM_POST),
    "B12-po3-low-after-0830-into-old-low": dict(po3_ideal="tag", **SM_POST),
    "B12-po3-low-after-0830-into-old-low_require": dict(po3_ideal="require", **SM_POST),
    "new-po3-midnight-open-resting-order": dict(po3_resting=True, po3_rest_off_pts=0.25, po3_rest_mgmt="none", htf_bias="combo"),
    "M5-lasthour-first-unit-at-old-low": dict(lh_old_low_entry=True, lh_add2_mult=1.0, lh_old_low_stop_pts=3.0, last_hour_own_slot=True, htf_bias="combo", **SM_POST),
    "M6-pm-continuation-long-at-old-high": dict(pm_old_high_fvg=True, pm_old_high_bars=6, adds=(0.5,), htf_bias="combo", **SM_POST),
    "M6-ifvg-must-stay-partly-open": dict(pm_reversal=True, pm_rev_partial=True, pm_rev_first_only=True, **SM_POST),
    "new-pm-retracement-short-after-draw-delivered": dict(pm_after_draw=True, pm_after_room_pts=10.0, htf_bias="combo", **SM_POST),
    "new-pm-retracement-short-after-draw-delivered_sb": dict(sb_model=True, sb_counter_after_draw=True, pm_after_room_pts=10.0, htf_bias="combo", **SM_POST),
    "M1-ob-entry-after-mss": dict(entry_arrays=("ob_post",), **SM_POST),
    "B5-multi-tf-fvg-scan": dict(leg_tfs=(15, 5, 4, 3, 2), fvg_pick="2022", **SM_POST),
    "M2-leg-eq-after-low-prints": dict(m2_live_eq=True, fvg_pick="2022", **SM_POST),
    "M2-pyramid-runup-leg-eq": dict(m2_anchor="runup", fvg_pick="2022", **SM_POST),
    "M2-implied-range-eq-gate": dict(implied_range_gate=True, draw_lock="session", ob_entry="post_mss", htf_resist_cap=False),
    "M7-pm-short-after-lunch-run-of-am-stops": dict(pm_am_stops=True, pool_swings=True, **SM_POST),
    "M5-lasthour-short-sequence": dict(lh_array_short=True, **SM_POST),
    "M5-lasthour-short-sequence_sd3": dict(lh_array_short=True, lh_array_target="sd3", lh_array_iofed=True, lh_array_need_draw=True, **SM_POST),      # review fix: -3 SD target, IOFED add, draw required
    "B16-nwog-gapup-return-then-mss": dict(nwog_fill_long=True, nwog_fill_tol_pts=2.0, **SM_POST),
    "M11-wick-ce-fade-short": dict(wick_ce_entries=True, wick_ce_mode="intrabar", wick_ce_pad_pts=1.0, **SM_POST),
    "M11-wick-ce-fade-short_noprec": dict(wick_ce_entries=True, wick_ce_mode="intrabar", wick_ce_precursor=False, **SM_POST),
    "M11-wick-ce-fade-short_retrace": dict(wick_ce_mode="retrace", **SM_POST),
    "M5-lasthour-shallowest-unused-array": dict(entry_arrays=("ob", "vi", "breaker"), entry_pick="shallowest_unused", **SM_POST),
    "new-nwog-edge-to-ce-cookie-cutter": dict(nwog_edge_ce=True, **SM_POST),
    "M8-short-after-reprice-to-prior-close": dict(org_fill_reverse=True, **SM_POST),
    "A12-entry-array-at-key-level": dict(ob_at_key="tag", ob_key_ticks=2, **SM_POST),
    "A12-entry-array-at-key-level_require": dict(ob_at_key="require", **SM_POST),
    "M4-breaker-needs-fvg-inside": dict(breaker_low_invalidate=True, breaker_entry="fallback", unicorn_pref=True, **SM_POST),
    "A13-breaker-inversion-against": dict(breaker_block_counter=True, breaker_entry="fallback", **SM_POST),
    "new-sweep-wick-ce-failure-swing-long": dict(wick_ce_entries=True, wick_ce_tf=15, wick_ce_need_pool=True, **SM_POST),
    "M16-sick-sister-ob-open-entry": dict(sick_entry="ob_open", **SM_POST),          # (the sister needs a partner index: tested in the synthetic partner runs)
    "M16-sick-sister-discount-confluence": dict(sick_entry="ote_stack", sick_units=2, **SM_POST),
    "new-lunch-macro-long-nwog": dict(lunch_nwog_long=True, **SM_POST),
    "new-lunch-macro-long-nwog_ob": dict(lunch_nwog_long=True, lunch_nwog_entry="ob", **SM_POST),
    "A8-symmetry-skip-ifvg-confirmation": dict(ifvg_entries=True, ifvg_hold=True, ifvg_symmetry_skip=True, **SM_POST),
    "A8-ifvg-5m-to-1m-handoff": dict(ifvg_entries=True, ifvg_tf=5, ifvg_hold=True, **SM_POST),
    "new-short-top-of-htf-discount-fvg": dict(htf_fvg_top_short=True, htf_bias="combo", **SM_POST),
    "new-ndog-asian-scalp": dict(ndog_scalp=True, asia_session=True, **SM_POST),
    "M16-trending-divergence-continuation": dict(smt_trend_ignore=True, smt_bias="filter", **SM_POST),         # (the sick-sister half needs a partner index: tested in the synthetic partner runs)
    "M2-three-drives-conditions": dict(three_drives_htf=True, htf_bias="combo", **SM_POST),
    "M4-complete-model-breaker-ote-ob": dict(complete_model="tag", breaker_entry="fallback", unicorn_pref=True, **SM_POST),
    "M4-complete-model-breaker-ote-ob_require": dict(complete_model="require", breaker_entry="fallback", unicorn_pref=True, **SM_POST),
    "M5-lasthour-reversal-into-org": dict(lh_org_fill=True, last_hour_own_slot=True, **SM_POST),
    "D15-one-clean-gap-instrument": dict(smt_pick="clean"),
}
DECISIONS.update(_SM4_DECISIONS)

# --- caption-gap pass, setups_models #5/7 (models_setups_entries.md): one variant per gap id (name prefix = the gap id) ---
_SM5_DECISIONS = {
    "M10-ifvg-fvg-signature-full": dict(ifvg_entries=True, ifvg_061=True, ifvg_061_entry="iofed", **SM_POST),
    "new-false-bull-flag-short": dict(false_flag="tag", **SM_POST),
    "new-false-bull-flag-short_require": dict(false_flag="require", flag_min_bars=4, flag_max_frac=0.6, **SM_POST),
    "M9-news-judas-full-sequence": dict(news_two_sided=True, **SM_POST),
    "new-15m-candle-po3-upper-half": dict(po3_15m=True, po3_15m_n=3, **SM_POST),
    "M12-new-trader-no-turtle-soup": dict(turtle_soup="2023", **SM_POST),                     # (no switch: the Trade.entry_style tag splits raid / confirmed results; this variant produces the raid style)
    "M12-turtle-soup-prev-pm-low": dict(turtle_soup="prev_pm", htf_bias="combo", **SM_POST),
    "M7-second-dip-into-rejection-block": dict(rb_second_dip=True, **SM_POST),
    "M8-org-repricing-full-conditions": dict(org_reprice=True, org_reprice_full=True, stop_mode="ce2", **SM_POST),
    "M0-all-nearby-pools-run-first": dict(all_pools_first="tag", **SM_POST),
    "M0-all-nearby-pools-run-first_require": dict(all_pools_first="require", all_pools_pts=30.0, **SM_POST),
    "M7-lunch-reprice-org-ce-moc": dict(lunch_org_ce_short=True, htf_bias="combo"),
    "D15-dual-dealing": dict(dual_deal="split", **SM_POST),
    "D15-dual-dealing_full": dict(dual_deal="full", **SM_POST),
    "M4-1m-last-upclose-finetune": dict(breaker_entry="fallback", breaker_tf=5, breaker_pref="last_1m", **SM_POST),
    "M4-two-pool-breaker-near-miss": dict(near_miss_pts=3.0, breaker_entry="fallback", **SM_POST),
    "M4-unfinished-high-keep-ab-leg": dict(adv_breaker=True, ab_anchor_lock=True, **SM_POST),
    "M11-cisd-ob-stop-skip-rearm": dict(cisd_ob_entries=True, cisd_need_htf=True, cisd_rearm=True, max_stop_pts=10.0, **SM_POST),
    "M10-ifvg-footholds-buy-program": dict(ifvg_entries=True, ifvg_targets=True, ifvg_need_hunt=True, **SM_POST),
    "A4-bodies-hold-prev-day-50": dict(pd50_bodies=True, **SM_POST),
    "A4-bodies-hold-prev-day-50_5m": dict(pd50_bodies=True, pd50_tf=5, **SM_POST),
    "new-overshoot-ltf-fvg-into-htf-level": dict(htf_overshoot_short=True, overshoot_pts=3.0, **SM_POST),
    "new-open-returns-into-bearish-ob": dict(open_ob_min=10, ob_entry="pre_break"),
    "B5-ltf-at-htf-array": dict(htf_entry_array="tag", entry_arrays=("htf",), **SM_POST),
    "B5-ltf-at-htf-array_require": dict(htf_entry_array="require", **SM_POST),
    "M2-htf-ob-precondition": dict(allow_htf_array_premise=True, premise_tfs=(15, 60, 1440), **SM_POST),
    "M2-three-drives-breaker-fallback": dict(three_drives="tag", td_same_level=True, td_level_pts=2.0, td_fallback=True, ifvg_entries=True, **SM_POST),
    "A15-mitigation-block-entry_array": dict(entry_arrays=("mitigation",), htf_bias="combo", **SM_POST),
    "A15-mitigation-block-entry_daily": dict(entry_arrays=("mitigation",), mit_entry_tf="D", htf_bias="combo", **SM_POST),
    "A15-stair-step-mitigation": dict(mit_stair=True, adds=(0.5, 0.5), htf_bias="combo", **SM_POST),
    "A15-stair-step-mitigation_stop": dict(mit_stair=True, mb_order="stop", htf_bias="combo", **SM_POST),
    "new-next-day-or-reh-short": dict(prev_reh_plan=True, **SM_POST),
    "M2-skip-filter": dict(stop_zone_pool=True, fvg_pick="2022", **SM_POST),
    "A14-unicorn-standalone": dict(unicorn_standalone=True, unicorn_tf=5, **SM_POST),
    "A14-unicorn-standalone_60m": dict(unicorn_standalone=True, unicorn_tf=60, **SM_POST),
    "M13-max-depth-79": dict(max_retrace=0.79, fvg_pick="2022", **SM_POST),
    "M10-ifvg-open-dependent": dict(ifvg_open_mode=True, ifvg_gap_pts=5.0, ifvg_depth=True, htf_bias="combo", **SM_POST),
    "M0-htf-array-not-reached": dict(array_fallback_breaker=True, draw_lock="session", htf_resist_cap=False, ob_entry="post_mss"),
    "M1-original-consolidation-entry": dict(mm_oc_entry=True, mmxm_ctx=True, orig_consol=True, **SM_POST),
    "M1-consolidate-at-discount-array": dict(mm_accum_bars=3, mm_accum_frac=0.8, mmxm_ctx=True, **SM_POST),
    "M1-accumulation-stages": dict(mm_stages=True, mmxm_ctx=True, adds=(0.5, 0.5), **SM_POST),
    "M1-distribution-stages-lowrisk-short": dict(mm_lowrisk=True, mm_oc_frac=0.8, mm_stages=True, mmxm_ctx=True, **SM_POST),
    "M1-distribution-stages-lowrisk-short_reentry": dict(mm_lowrisk=True, mm_lowrisk_reentry="wick_ce", mm_stages=True, mm_stage2=True, mm_oc_frac=0.8, mmxm_ctx=True, **SM_POST),
    "M1-consolidate-at-discount-array_gate": dict(mm_accum_bars=3, mm_accum_frac=0.8, mm_accum_gate=True, mm_oc_entry=True, mm_stages=True, mmxm_ctx=True, **SM_POST),
    "A14-unicorn-standalone_independent": dict(unicorn_standalone=True, unicorn_independent=True, unicorn_tf=5, ob_entry="pre_break"),
    "A18-curve-arrays-reverse-ladder": dict(reclaimed_ladder=True, reclaim_bounce_bars=2, reclaimed_ob=True, adds=(0.5, 0.5), **SM_POST),
    "M1-one-segment": dict(mm_flip=True, mm_stages=True, mmxm_ctx=True, draw_lock="session", htf_resist_cap=False, ob_entry="post_mss"),
}
DECISIONS.update(_SM5_DECISIONS)

# --- caption-gap pass, setups_models #6/7 (models_setups_entries.md): one variant per gap id (name prefix = the gap id) ---
_SM6_DECISIONS = {
    "M1-short-sell-side-of-buy-curve": dict(curve_short=True, **SM_POST),
    "A12-ob-at-consolidation-eq-and-eq-retest": dict(consol_eq_entry=True, consol_eq_mode="ob", **SM_POST),
    "A12-ob-at-consolidation-eq-and-eq-retest_eq": dict(consol_eq_entry=True, consol_eq_mode="eq", consol_bars=12, consol_max_pts=10.0, **SM_POST),
    "A10-void-retrace-trades": dict(void_trades=("fill", "range", "cont"), **SM_POST),
    "new-retrace-to-origin-ob": dict(consol_eq_entry=True, consol_eq_mode="origin_ob", **SM_POST),
    "M13-ote-needs-bias-trigger-structure": dict(ote="limit", ote_need_trigger=True, ote_parent_pd=True, **SM_POST),
    "M13-premium-ote-turtle-soup": dict(turtle_soup="2023", ts_need_htf=True, ts_ote_ok=True, **SM_POST),
    "M13-bodies-stall-62-ob": dict(ote="ob62", **SM_POST),
    "M12-quick-rejection-required": dict(ts_cont=True, ts_cont_bars=10, turtle_soup="2023", **SM_POST),
    "M12-cc-daily-ob-turtle-soup": dict(turtle_soup="cc_1h_ob", **SM_POST),
    "M12-cc-daily-ob-turtle-soup_noval": dict(turtle_soup="cc_1h_ob", cc_ob_validate=False, **SM_POST),
    "M12-cc-daily-ob-turtle-soup_5m": dict(turtle_soup="cc_1h_ob", cc_ob_tf=5, ts_r_preset="cc02_003", cc_ob_offset_ticks=1, **SM_POST),
    "B5-topdown-entry-refinement": dict(turtle_soup="cc_1h_ob", refine_tfs=(60, 15, 5), **SM_POST),
    "A12-secondary-ob": dict(entry_arrays=("ob_secondary",), **SM_POST),
    "new-false-bear-flag-long": dict(false_flag="tag", entry_arrays=("ob",), **SM_POST),       # (already built: false_flag is side-symmetric; this variant adds the OB entry array)
    "M12-setup-selection-order": dict(entry_discipline="turtle_soup", **SM_POST),
    "M12-setup-selection-order_loose": dict(entry_discipline="turtle_soup", entry_discipline_only=False, **SM_POST),
    "M12-setup-selection-order_ob_return": dict(entry_discipline="ob_return", **SM_POST),
    "M12-setup-selection-order_range_void": dict(entry_discipline="range_void", **SM_POST),
    "M12-contrarian-pmh": dict(pmh_contrarian=True, **SM_POST),
    "B12-ob-below-midnight-open": dict(ob_below_open=True, entry_arrays=("ob",), **SM_POST),
    "new-eq-wait-fresh-ob": dict(eq_fresh_ob=True, entry_arrays=("ob",), **SM_POST),
    "M12-counter-run-in-confirmed-trend": dict(sym_swing_ts=True, **SM_POST),
    "E2-body-extreme-entry": dict(turtle_soup="cc_limit", ts_level_src="body", **SM_POST),
    "A13-breaker-reentries-and-wait": dict(breaker_entry="fallback", breaker_retests=3, breaker_leave_pts=3.0, **SM_POST),
    "A17-rejection-block-entries": dict(rb_entry="limit", **SM_POST),
    "A17-rejection-block-entries_stop": dict(rb_entry="stop", **SM_POST),
    "A16-propulsion-entries": dict(entry_arrays=("propulsion",), prop_second=True, **SM_POST),
    "L8-vacuum-block-entries": dict(vb_entry="auto", **SM_POST),
    "L8-vacuum-block-entries_partial": dict(vb_entry="partial", vb_react_bars=2, **SM_POST),
    "L8-vacuum-block-entries_full": dict(vb_entry="full", **SM_POST),
    "new-post-void-fill-gap-sell": dict(void_trades=("void_fill_gap",), **SM_POST),
    "new-last-buyside-offered-level": dict(entry_arrays=("last_offer",), offer_run=3, offer_step_pts=1.0, **SM_POST),
    "M4-two-chance-aggressive-vs-mss-retest": dict(two_chance=True, cc_swings="breaker", turtle_soup="2023", ts_gate_mss=True, **SM_POST),
    "M4-retest-nearer-ob-or-none": dict(cc_swings="breaker", cc_near_ob=True, **SM_POST),
    "A15-mitigation-block-sell-entry": dict(entry_arrays=("mitigation", "breaker"), entry_arrays_order=("mitigation", "breaker"), htf_bias="combo", **SM_POST),
    "new-clarity-filter-pass-if-arguing": dict(clarity="drop", clarity_overlap=4.0, **SM_POST),
    "new-clarity-filter-pass-if-arguing_tag": dict(clarity="tag", **SM_POST),
    "new-bullish-week-daily-routine-london-ny": dict(ny_london_range=True, weekly_bias=True, **SM_POST),
    "M0-judas-ends-in-15m-array": dict(sweep_15m_array="tag", sweep_leave_bars=3, sweep_leave_pts=2.0, **SM_POST),
    "M0-judas-ends-in-15m-array_require": dict(sweep_15m_array="require", **SM_POST),
    "M12-turtle-soup-entry-depth": dict(turtle_soup="cc_limit", ts_cc_below_pts=1.25, **SM_POST),
    "new-consolidation-outer-edge-fade": dict(consol_edge_fade="edge", consol_tf=15, consol_bars=12, **SM_POST),
    "new-consolidation-outer-edge-fade_market": dict(consol_edge_fade="edge", consol_edge_entry="market", consol_tf=15, consol_bars=12, **SM_POST),
    "new-inside-range-expansion-fade": dict(consol_edge_fade="inner", consol_tf=15, consol_bars=12, consol_eq_band=0.15, **SM_POST),
    "new-eight-reversal-catalogue": dict(reversal_tag=True, reversal_need_htf=True, **SM_POST),
    "L2-pdh-pdl-fade-only-in-expansion-retrace": dict(pdl_expansion=True, daily_level_needs_array=True, **SM_POST),
    "new-overlapping-reversal-score": dict(reversal_tag=True, reversal_score=True, **SM_POST),
}
DECISIONS.update(_SM6_DECISIONS)

# --- caption-gap pass, setups_models #7/7 (models_setups_entries.md, other.md, session_day_week_stops_frequency.md, stops_sizing_scaling_in.md, times_sessions_macros.md): one variant per gap id (name prefix = the gap id) ---
_SM7_DECISIONS = {
    "OT-D15-default-instrument": dict(combine_prefer="es", nq_overshoot_mult=1.5, **SM_POST),
    "OT-D15-default-instrument_nq2": dict(combine_prefer="es", nq_overshoot_mult=2.0, **SM_POST),
    "OT-max-two-correlated-markets": dict(max_exec_markets=2, combine_exec_exclude=("YM",), combine_prefer="es", **SM_POST),
    "T3-london-close-counter-trend-scalp": dict(lc_scalp=True, lc_mode="failure_swing", lc_adr_mult=1.0, **SM_POST),
    "T3-london-close-counter-trend-scalp_wide": dict(lc_scalp=True, lc_mode="failure_swing", lc_adr_mult=1.25, lc_fs_win=(600, 720), **SM_POST),
    "new-london-close-scalp-large-range": dict(lc_scalp=True, lc_mode="mss", lc_adr_k=1.25, **SM_POST),
    "new-london-close-scalp-large-range_short_window": dict(lc_scalp=True, lc_mode="mss", lc_adr_k=1.33, london_close=(600, 660), **SM_POST),
    "M17-london-close-asia-only-reversal-profile": dict(lc_rev_need_htf=True, lc_tag=True, **SM_POST),
    "E5-missed-entry-5m-retrace": dict(missed_5m=True, **SM_POST),
    "E5-missed-entry-5m-retrace_lon": dict(missed_5m=True, missed_lon=True, london_kz=True, **SM_POST),
    "B12-dip-below-open-into-converging-15m-array": dict(htf_converge=True, sweep_15m_array="tag", **SM_POST),
    "new-or-reference-arrays-reused": dict(entry_arrays=("or_ref",), or_ref_reuse=2, **SM_POST),
    "new-am-trend-definition-and-start": dict(am_array_open=True, **SM_POST),
    "T9-pm-reversal-turtle-soup-am-high": dict(turtle_soup="2023", pm_am_stops=True, ts_sessions=("PM",), **SM_POST),
    "T13-two-session-close-profile": dict(two_session_smt=True, profile_two_session=True, smt_windows=((720, 810),), **SM_POST),
    "T13-am-move-pm-reversal-htf-nesting": dict(pm_nest_reversal=True, pm_reversal=True, pm_rev_nested=True, **SM_POST),
    "T13-consolidation-profiles": dict(profile_consol=True, profile_consol_pm=True, consol_exit_min=15, **SM_POST),
    "M13-pattern1-full-sequence-ote-fvg": dict(ote="limit", ote_fvg_overlap=True, ote_need_s=True, **SM_POST),
    "M4-pattern3-breaker-half-size-add-ltf": dict(turtle_soup="2023", ts_breaker_pyramid=True, ts_breaker_add_mult=0.5, ts_breaker_ltf=True, two_chance=True, cc_swings="breaker", **SM_POST),
    "OT-M17-cc09_001-checklist": dict(cc09_gate="tag", **SM_POST),
    "OT-M17-cc09_001-checklist_gate": dict(cc09_gate="gate", cc09_room_pts=10.0, cc09_depart_bars=3, **SM_POST),
    "OT-M17-cc09_003-ny-expansion": dict(nyx_model=True, nyx_start=570, nyx_max=2, **SM_POST),
    "OT-M17-cc09_003-ny-expansion_0830": dict(nyx_model=True, nyx_start=510, nyx_max=2, **SM_POST),
    "OT-one-state-tool-pairing": dict(pairing="reversal_pool", **SM_POST),
    "OT-one-state-tool-pairing_state_tag": dict(state_tag=True, **SM_POST),
    "OT-one-state-tool-pairing_expansion_ob": dict(pairing="expansion_ob", entry_arrays=("ob",), **SM_POST),
    "OT-one-state-tool-pairing_retracement_void": dict(pairing="retracement_void", **SM_POST),
    "OT-one-state-tool-pairing_consolidation_eq": dict(pairing="consolidation_eq", **SM_POST),
    "X14-reentry-after-winning-exit": dict(reentry_after_win=True, reentry_win_max=1, **SM_POST),
    "X14-reentry-after-winning-exit_two_sister": dict(reentry_after_win=True, reentry_win_max=2, reentry_need_sister=True, **SM_POST),
    "X13-reentry-after-trail-stop-in-profit": dict(reentry_after_trail_win=True, trail_reentry_entry="ifvg_ce", trail_reentry_max=2, trail=True, **SM_POST),
    "X13-reentry-after-trail-stop-in-profit_breaker": dict(reentry_after_trail_win=True, trail_reentry_entry="breaker", trail=True, **SM_POST),
    "X13-reentry-after-loss-conditions": dict(reentry_half=True, reentry_gate=True, reentry_idea_gate=True, reentry_risk_mult=0.5, **SM_POST),
    "X13-reentry-after-loss-conditions_same_size": dict(reentry_half=True, reentry_gate=True, reentry_idea_gate=True, reentry_risk_mult=1.0, **SM_POST),
    "X13-reentry-after-loss-conditions_sibi_only": dict(reentry_half=True, reentry_gate=True, reentry_trigger="sibi_return", **SM_POST),
    "X13-reentry-after-loss-conditions_sibi": dict(reentry_half=True, reentry_gate=True, reentry_idea_gate=True, reentry_trigger="sibi_return", reentry_stop="wick_ce", **SM_POST),
    "X13-reverse-after-failure-switch": dict(reverse_after_failure="all", reverse_risk_mult=0.5, **SM_POST),
    "X13-reverse-after-failure-switch_inversion": dict(reverse_after_failure="inversion", **SM_POST),
    "X13-reverse-after-failure-switch_prop_fail": dict(reverse_after_failure="prop_fail", entry_arrays=("propulsion",), prop_mt_exit=True, **SM_POST),
    "X13-reverse-after-failure-switch_at_stop": dict(reverse_after_failure="at_stop", offside_frac=0.5, **SM_POST),
    "X14-opposite-second-trade-after-win": dict(allow_opposite_after_target="both", lod_conf_pts=2.0, no_pm_after_am_win=True, **SM_POST),
    "E12-070-rung-order": dict(adv_breaker=True, adv_rungs=True, adv_rung_fracs=(0.1, 0.3, 0.6), **SM_POST),
    "X13-reentry-turtle-soup": dict(turtle_soup="cc_limit", reentry_ts=True, reentry_max=2, reentry_mult=0.5, **SM_POST),
    "E6-breakaway-gap-stop": dict(breakaway_reentry=True, **SM_POST),
    "M12-ts-stop-midpoint": dict(turtle_soup="2023", ts_stop="mid", **SM_POST),
    "T7-0950-reversal-or-continuation": dict(m0950_branch="both", **SM_POST),
    "T7-0950-reversal-or-continuation_rev": dict(m0950_branch="rev", **SM_POST),
    "T7-1050-macro-setup": dict(m1050=True, m1050_cut=True, protect_macro_ext=True, **SM_POST),
    "T10-lasthour-ob-pullback": dict(lh_ob_pullback=True, **SM_POST),
    "T7-lasthour-after-target": dict(lh_after_target=True, last_hour_setup=True, **SM_POST),
    "T7-lasthour-consolidation-direction": dict(moc_run=True, moc_range_dir=True, moc_no_chase_hod=True, **SM_POST),
    "T7-lunch-macro-htf-program": dict(lunch_macro_entry=True, lunch_htf_program=True, htf_bias="combo", **SM_POST),
    "new-ny-runs-london-extreme-news": dict(london_ext_guard=True, **SM_POST),
}
DECISIONS.update(_SM7_DECISIONS)

# --- caption-gap pass, entries_stops_sizing #1/3 (bias_htf_intermarket.md, definitions_pd_arrays_structure.md): one variant per gap id (name prefix = the gap id) ---
_ES1_DECISIONS = {
    "NEW-no-return-to-origin-ob": dict(no_origin_retest=True, turtle_soup="2023", **SM_POST),
    "NEW-no-return-to-origin-ob_cc_limit": dict(no_origin_retest=True, turtle_soup="cc_limit", htf_bias="react", **SM_POST),
    "B5-prior-day-ny-range-retracement": dict(entry_pd_frame="prev_day", **SM_POST),
    "B5-prior-day-ny-range-retracement_ny": dict(entry_pd_frame="prev_ny", **SM_POST),
    "B5-prior-day-ny-range-retracement_any": dict(entry_pd_frame="any", **SM_POST),
    "A12-ob-requires-signatures": dict(ob_need_fvg=True),
    "A12-ob-requires-signatures_anchor": dict(ob_need_fvg=True, ob_entries="prefer", **SM_POST),
    "A12-cisd-open-buy-level": dict(cisd_ob_entries=True, cisd_ob_px="open", **SM_POST),
    "A12-cisd-open-buy-level_adds": dict(cisd_ob_entries=True, cisd_ob_px="open", cisd_adds=True, adds=(0.5, 0.33), **SM_POST),
    "A12-ob-overshoot-to-vi": dict(ob_vi_overshoot=True, vi_arrays=True),
    "A12-ob-overshoot-to-vi_fvg": dict(ob_vi_overshoot=True, **SM_POST),
    "D4-mt-source-tally": dict(mt_mode="sensitive", mt_break="close", **SM_POST),
    "D4-mt-source-tally_blended_warn": dict(mt_mode="body_single_range_blended", mt_break="warn", **SM_POST),
    "D4-mt-source-tally_trade": dict(mt_break="trade", **SM_POST),
    "A13-breaker-fvg-refinement": dict(breaker_entry="fallback", breaker_refine=True, **SM_POST),
    "E2-iofed-full-definition": dict(entry="iofed", iofed_strict=True, **SM_POST),
    "A5-ob-in-vi-over-newer-fvg": dict(add_pref_ob_in_vi=True, adds=(0.5, 0.33), **SM_POST),
    "A5-mtf-gap-refinement": dict(gap_tf_mode="refine_down", htf_entry_arrays=(15,), **SM_POST),
    "A5-mtf-gap-refinement_widen": dict(gap_tf_mode="widen_up", fvg_targets=True, **SM_POST),
    "A9-vi-retest-tolerance": dict(vi_stop=True, vi_tol="ce", vi_arrays=True, **SM_POST),
    "A9-vi-retest-tolerance_adjacent": dict(vi_stop=True, vi_tol="adjacent_extreme", vi_arrays=True, **SM_POST),
    "A16-propulsion-block-full": dict(prop_entry=True, prop_mt_exit=True, prop_mt_test="wick", prop_fail_flip=True, **SM_POST),
    "A16-propulsion-depth-grade": dict(prop_entry=True, prop_deep_mult=0.5, prop_deep_cut=0.4, **SM_POST),
    "A15-mitigation-definition-and-iofed": dict(mit_iofed_edge=True, entry="ce", **SM_POST),
    "A21-implied-range-to-target": dict(leg_pd_anchor="target", **SM_POST),
    "A21-post-cisd-range-retrace": dict(leg_pd_anchor="retrace_range", **SM_POST),
    "A23-broken-wick-ce-inversion": dict(entry_arrays=("broken_wick_ce",), broken_wick_stop="body_edge", **SM_POST),
    "A23-broken-wick-ce-inversion_swing": dict(entry_arrays=("broken_wick_ce",), broken_wick_stop="swing", **SM_POST),
    "A5-far-edge-reach-conditions": dict(far_edge_reach=True, htf_entry_arrays=(15, 60), **SM_POST),
    "A5-partial-reprice-shrink": dict(fvg_edge="remaining", **SM_POST),
    "A12-ob-edge-at-fvg-ce": dict(ob_ce_confluence=True, ob_ce_tol_pts=2.0, **SM_POST),
    "A21-intraday-fib-bodies": dict(leg_fib="body", **SM_POST),
    "A8-htf-gap-resistance-grade": dict(htf_depth_mult=(1.0, 1.0, 0.5), **SM_POST),
    "A12-ob-requires-narrative": dict(ob_need_narrative=True, htf_bias="react"),
    "A12-ob-requires-narrative_no_array": dict(ob_need_narrative=True, ob_need_htf_array=False, htf_bias="react"),
    "A12-ob-open-anchor-ltf-wick": dict(ob_wick_ltf_entry=True, htf_ob_anchor="open", htf_entry_arrays=(15, 60), **SM_POST),
    "A12-ob-anchor-level": dict(htf_ob_anchor="open", htf_targets=("15m", "1h", "4h", "D"), **SM_POST),
    "new-multi-tf-scan": dict(scan_tfs=(1, 2, 3, 4, 5, 15), **SM_POST),
    "new-2m-fvg-ce": dict(two_min_ce=True, **SM_POST),
    "A5-skip-fvg-near-stop-pool": dict(fvg_skip_below_pool_short=True, fvg_pool_gap_pts=2.0, **SM_POST),
    "A5-multitf-hold-test": dict(mtf_hold=True, entry_tf="5m", **SM_POST),
    "M13-swing-confirm-gate": dict(ote="limit", ote_gate_4th=True, **SM_POST),
    "M13-reanchor-parent": dict(ote="limit", ote_reanchor=True, ote_cancel=True, **SM_POST),
    "M13-nested-ranges": dict(ote="limit", ote_nested=True, **SM_POST),
    "M13-nested-ranges_third": dict(ote="filter", ote_nested=True, ote_parent_third=True, **SM_POST),
    "M13-short-ote-mirror": dict(ote="limit", **SM_POST),
    "A12-ltf-ob-upper-half": dict(ob_entry_px="mt", ob_mt_range="range"),
    "A12-ob-reached-body": dict(ob_reach="body", allow_htf_array_premise=True, htf_bias="react"),
}
DECISIONS.update(_ES1_DECISIONS)
SB_VARIANTS = tuple(_SB_DECISIONS)       # silver_bullet package (sb_model.py): their look-ahead tests are in test_silver_bullet.py

DEC_BASE = dict(AM_SPY, pm=Params().pm, skip_news=False)


import os
SRC = os.environ.get("MENTORSHIP_SRC", "histdata")      # "histdata" (SPX/NDX CFDs) or "databento"
SYMS = {"histdata": ("SPX", "NDX"), "merged": ("SPX", "NDX"), "databento": ("ES", "NQ", "YM")}[SRC]


_BX_TABLES: dict = {}


def _bias_cache(tf: int, cut: int = 570, vi: bool = False, flip: tuple = ("ob_mt", "wk_dc"),
                kw: dict | None = None) -> pd.DataFrame:
    """The htf table (cut at `cut` minutes; 570 = the ordinary bias table), cached per source,
    VI wiring and flip triggers (review: the VI_arrays variant used to get the non-VI table), and
    the levels_detectors table switches `kw` (backtest.htf_kw: A5 c2 check, A9 VI size / death)."""
    from . import htf
    kw = kw or {}
    import hashlib
    tag = ("" if cut == 570 else f"_cut{cut}") + ("_vi" if vi else "") + \
        ("" if tuple(flip) == ("ob_mt", "wk_dc") else "_" + "-".join(flip)) + \
        "".join(f"_{k}{v}" if k != "bx" else "_bx" + hashlib.md5(str(v).encode()).hexdigest()[:8]
                for k, v in sorted(kw.items()))
    if "bx" in kw:        # bias_htf columns hold lists / strings a CSV would flatten: built once per process instead
        key = (tf, cut, vi, tuple(flip), tuple(sorted(kw.items())))
        if key not in _BX_TABLES:
            _BX_TABLES[key] = htf.table(B.load(SYMS[0], tf, source=SRC), cut_min=cut, vi=vi, flip_triggers=tuple(flip), **kw)
        t = _BX_TABLES[key].copy()
        t.index = pd.to_datetime(t.index).date
        return t
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
    return {m: _bias_cache(tf, m, p.vi_arrays, p.flip_triggers, B.table_kw(p)) for m in sorted(B.lock_cuts(p))}


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
    ref = None
    if p.bias_open_src == "es_map":                 # D22: the futures midnight open mapped to the traded frame
        ref = B.load("ES", tf, source="databento")
        ref = ref[(ref.index >= lo) & (ref.index < b)]
    t = B.run(df[(df.index >= lo) & (df.index < b)], tf, SYMS[0], p, pa[(pa.index >= lo) & (pa.index < b)],
              partner2=p2, ref_df=ref,
              bias_table=_bias_cache(tf, 570, p.vi_arrays, p.flip_triggers, B.table_kw(p)), meta=B.load_meta(SYMS[0], tf, SRC),
              lock_cuts=_lock_cache(tf, p))
    if p.smt_pick != "first" or p.one_market or p.sb_one_market or p.sb_am_done or p.dual_deal or len(p.markets) > 1 or p.combine_prefer != "none":    # SB package: M3.9 / gap 7 need the second market too (BH-M3-scan-all-indices: markets)
        # Ep03.11 (review fix): smt_pick only acts when two instruments are combined - run the
        # partner as its own book (es_pt scaled by the price ratio, as main_index) and combine
        q = replace(p, es_pt=round(p.es_pt * float(pa.close.median() / df.close.median()), 2))
        tb = B.run(pa[(pa.index >= lo) & (pa.index < b)], tf, SYMS[1], q, df[(df.index >= lo) & (df.index < b)],
                   meta=B.load_meta(SYMS[1], tf, SRC) if SRC == "databento" else None, lock_cuts={} if p.draw_lock == "off" else None)
        t = B.combine(t, tb, pick=study_pick(p.smt_pick), laggard_consol_only=p.laggard_consol_only, one_market=p.one_market,
                      sb_one_market=p.sb_one_market, sb_am_done=p.sb_am_done, dual_deal=p.dual_deal,   # SB package (+ setups_models #5/7 D15-dual-dealing)
                      exec_exclude=p.combine_exec_exclude, prefer=p.combine_prefer, max_exec=p.max_exec_markets)       # setups_models #7/7: OT-D15-default-instrument / OT-max-two-correlated-markets
    if len(t):
        t = t[pd.to_datetime(t.entry_time.astype(str).str[:10]) >= f"{year}-01-01"].copy()
        t["tf"], t["year"], t["variant"] = tf, year, name
    return t


def main_decisions(out="runs/mentorship", workers=6, tfs=(5, 1), variants=None, tag="dec"):
    variants = variants or list(DECISIONS)
    for tf in tfs:
        _bias_cache(tf, kw=B.table_kw(Params()))
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
