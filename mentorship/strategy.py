"""The ICT Mentorship model as a bar-by-bar state machine (America/New_York times).

Setups
  AM  09:30-11:00  market maker buy/sell model: a sweep of sell-side (buy-side) liquidity
                   (previous 3 days' lows/highs, the pre-market low/high, relative equal
                   lows/highs), then a market structure shift: a candle body closes through
                   the swing high (low) that led into the sweep, with displacement leaving
                   an FVG. Entry is a limit at that FVG ("unicorn" FVG inside the breaker
                   preferred). Longs only below the midnight open, shorts only above it.
  PM  13:30-15:50  the same model against the AM-session high/low and the 13:30 open as the
                   premium/discount reference. Entries 15:00-15:50 are tagged "last hour"
                   (15:15-15:45 = the sweet spot, tag lh_sweet; owner #1).
Entry    default (owner #11, Ep 07): a limit at the bodies of the order block at the sweep low
         BEFORE the structure break; the FVG after the MSS is the switch ob_entry="post_mss".
Risk     stop beyond the mean threshold of the nearest order block (last opposite-close
         candle before the displacement), else beyond the FVG; 1.2% open risk at entry, at
         most 1.3% including adds (owner #12, Ep 07).
Targets  the session's locked draw (owner #9) with the liquidity / PD-array rungs before it; 5
         handles is the MINIMUM room to the draw, not the goal (owner #2); an unbroken opposing
         HTF FVG caps the trade (owner #7). Scale-out ladder; flat at the session close (16:15
         futures, 16:00 SPY; owner #1).
Limits   one AM and one PM trade; after a loss, no trade in the opposite direction.
Days     no NFP day, no Wed PM/Thu/Fri of NFP week, no FOMC-day PM; on 10:00-release days
         AM entries start at 10:00 (08:30 releases are already out by 09:30).

Optional rules (off by default, each a Params switch so its effect can be measured):
  require_htf   the sweep must reach into an open 15m/60m FVG (nested FVGs); always tagged
  trail / adds  trail the stop under each new FVG; pyramid smaller units on new FVGs
  weekly_bias   after a strong down (up) day, no longs (shorts) for the rest of the week
                unless a daily close gets back above (below) 50% of that day's wick
  sd_targets    standard-deviation projections of the manipulation leg as extra targets
  wick_levels   50% of the previous day's wicks as extra targets
  htf_bias      trade only the side of the daily HTF bias (htf.py: react / draw / pd / combo)
Tags on every trade: htf, macro (armed 09:50-10:10), news (08:30 / 10:00 release day),
weekly bias, number of adds.

The bearish side runs the bullish logic on mirrored prices (o,h,l,c -> -o,-l,-h,-c), so
both directions share one code path. A bar is used only after it closes: orders armed on
bar i can first fill on bar i+1. Ambiguous bars resolve against the trade (stop first).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from datetime import date, timedelta

import numpy as np
import pandas as pd

from claude_hf.daytypes import JOBS, day_type, events
from . import calendar as _calendar  # noqa: F401  (loads 2019-2025 event dates)
from .calendar import next_trading_day, release_times
from . import levels as L
from .confluence import TFS as CF_TFS

# ICT macro windows (T6): 08:50-09:10, 09:50-10:10, 10:50-11:10, 11:50-12:10, 13:10-13:40,
# 14:50-15:10, 15:15-15:45
MACROS = ((530, 550), (590, 610), (650, 670), (710, 730), (790, 820), (890, 910), (915, 945))
NEWS_1000 = {"ism_manufacturing", "ism_services", "jolts", "sentiment"}
NEWS_0830 = {"cpi", "jobs", "ppi", "pce", "retail_sales", "gdp"}


@dataclass
class Params:
    pivot_n: int = 1               # swing = 3-candle pivot (ICT, cc01_005 "not the Williams
                                   # 5-candle fractal"); 2 = the old 5-candle swing (D17)
    min_fvg_pts: float = 0.25      # an FVG must be at least one ES tick wide (in ES points)
    fvg_pick: str = "last"         # entry FVG among the open ones after the MSS: "last" or "first"
    ifvg_entries: bool = False     # inversion FVGs (a bearish gap closed through) after the sweep
                                   # also count as the entry gap (M10)
    fvg_targets: bool = False      # untouched opposing FVGs and liquidity voids above as targets:
                                   # near edge, then CE (L9)
    mss_cisd: bool = False         # structure shift = change in state of delivery: a close above
                                   # the open of the down-close candle(s) into the low (075 ~1:16:40)
    globex_pool: bool = False      # overnight pool from the prior 18:00 reopen, not midnight (023)
    tag_blocks: bool = True        # tag trades with mitigation / propulsion blocks (measurement)
    pool_prev_week: bool = False   # previous week's high/low as sweep pools and targets (L3)
    pool_prev_month: bool = False  # previous month's high/low as sweep pools and targets (L3)
    pool_swings: bool = False      # ordinary short-term swing highs/lows (not only equal ones)
    extra_pools: bool = True       # London 02:00-05:00, prior PM 13:30-16:00 and lunch 12:00-13:30
                                   # highs/lows as sweep pools and targets (067)
    es_pt: float = 0.10            # instrument price units per ES point (SPY ~ ES / 10)
    eq_tol_pts: float = 0.5        # relative equal highs/lows tolerance, ES points
    exit_before_pts: float = 0.5   # exit this far in front of a liquidity target
    min_risk_pts: float = 1.0
    max_risk_pts: float = 15.0
    min_rr: float = 1.0
    partial: float = 0.5
    entry: str = "edge"            # "edge" (top of a BISI) or "ce" (50% of the gap)
    stop_mode: str = "ob_mt"       # "ob_mt" or "fvg"
    stop_buffer: float = 0.01
    fvg_wait: int = 2              # bars after the structure break to wait for an FVG
    entry_tf: str = "1m"           # run on 1m bars, enter in: "1m" a 1m FVG; "5m" a 5m FVG (or the
                                   # 5m order block behind it) once the 1m shifts (Ep 03 / Ep 08);
                                   # "nested" a 1m FVG inside a 5m FVG or 5m order block (Ep 01)
    setup_minutes: int = 5         # the higher timeframe used by entry_tf "5m" / "nested"
    pending_minutes: int = 30
    am: tuple = (570, 660)         # 09:30-11:00
    pm: tuple = (810, 950)         # 13:30-15:50 (no new entries after 15:50)
    last_hour: tuple = (900, 950)  # owner #1: last-hour entries 15:00-15:50 (Ep 01 "10 minutes
                                   # before"; Ep 08's 13:30-16:15 PM session wins); tag only
    macro: tuple = (590, 610)      # 09:50-10:10
    flatten: int = 0               # owner #1: 0 = flat at the resolved session close (16:15 ES/MES,
                                   # 16:00 SPY; see session_close); 960 = the old 16:00 exit
    use_bias: bool = True
    day_filter: bool = True
    risk_dollars: float | None = None   # owner #12: None = risk_pct x equity (1.2%); a number
                                   # overrides it (study preset legacy_1pct_2pct = 1000 / 2000)
    max_notional: float = 400_000.0
    cost_per_share: float = 0.01   # commissions + slippage, each way
    ambiguous: str = "stop"        # a bar touching both stop and target: "stop" first, or "target"
    htf: tuple = (15, 60)          # higher timeframes (minutes) for nested FVGs
    require_htf: bool = False
    trail: bool = False
    adds: tuple = (0.5, 0.33, 0.17)  # Ep 04 pyramid 6/3/2/1: smaller adds on each new FVG after
                                   # the fill, none after the first partial, total risk capped
    max_total_risk: float | None = None  # owner #12: None = max_total_risk_pct x equity (1.3%)
                                   # across the first unit and the adds
    weekly_bias: bool = False
    sd_targets: bool = False
    sd_levels: tuple = (1.0, 1.5, 2.0, 2.5)
    ep07_stop: bool = False        # Ep 07: stop under the body midpoint of the down-close candle
                                   # nearest the sweep low (~4:07)
    ep07_body_exit: bool = False   # Ep 07: out if price trades below the swing low's lowest body (~15:36)
    ep07_trail: bool = False       # Ep 07: once price trades through the bodies of the prior swing
                                   # high, trail the stop to the retracement candle's low
    htf_far_edge: bool = False     # HTF gap targets: near edge, CE, and the far edge as a third level
    wick_levels: bool = True       # A23: the prior day's wick CEs as targets
    mgmt: str = "ladder"           # "ladder": scale out at each target level in turn (X3); "t1t2": old
    ladder_fracs: tuple = (0.5, 0.25, 0.25)   # 036 normal days: 50/25/25
    ladder_fracs_slow: tuple = (0.8, 0.2)     # 036 slow days or news ahead: 80/20
    ladder_by_day: bool = True     # pick the split per trade (slow / news-ahead vs normal)
    slow_frac: float = 0.5         # [our interpretation] "slow day": the day's range at the fill
                                   # (from midnight) is under slow_frac x the 5-day average RTH range
    ladder_trail: str = "fvg"      # X5 (ICT): after each partial, trail under the newest FVG formed
                                   # since that partial (never the FVG right after the shift);
                                   # "hit" = stop to the array just paid at once price closes away_pts
                                   # beyond it (Mase's version); "prior" = one level behind
    away_pts: float = 1.0
    be_on: str = "expansion"       # X4: breakeven only after the first partial AND expansion -
                                   # [our interpretation] a later bar closes beyond the first target;
                                   # "t1" = at the first partial
    ce_hold: bool = False           # A5/A6: the entry FVG is a breakaway gap - once filled, a candle BODY closing
                                   # beyond its CE (wicks may poke) exits the trade before T1
    skip_news: bool = False        # no trades at all on 08:30 / 10:00 release days
    # decisions in mentorship_rules.md section 3 (D#); defaults are the recommended ones
    mss_mode: str = "close"        # D3: structure shift on a candle "close" or a "wick" through
    mt_mode: str = "body"          # D4: order-block mean threshold of the "body" or full "range"
    exit_mode: str = "split"       # D5: "split" = before arrays, just beyond pools; "before" = all
    pool_beyond_pts: float = 0.25  # ES pts beyond a liquidity pool (one tick)
    min_draw_pts: float = 5.0      # L15 / owner #2: MINIMUM room, measured to the draw's exit price
                                   # (after pool_beyond / exit_before); 5 = ICT's minimum (default),
                                   # 10 = new-trader switch. Not a target: targets are the draw / arrays
    leg_pd: float = 0.5            # D12: entry at/below this fraction of the displacement leg; 0 off
    leg_pd_at: str = "fill"        # check it when the order is armed ("arm") or, as ICT waits for
                                   # the retrace, against the leg high reached before the fill ("fill")
    am_exit: int = 720             # D16: AM leftovers out at 12:00 (minutes); 0 = hold to flatten
    pm_done_by: int = 0            # D16 test: PM out at this time once T1 filled (900 = 15:00)
    breaker_zone: str = "range"    # owner #14 (D6): Ep 02/05 (and Ep 07 OB, [our interpretation]) use the
                                   # breaker candle's full high-low range; "body" = Ep 01 switch
    sb_only: bool = False          # D2 test: fills only inside the Silver Bullet windows
    sb_windows: tuple = ((600, 660), (840, 900))
    fvg_abort: bool = False        # X6: body close beyond the FVG, next bar beyond it -> out
    time_stop_min: int = 0         # X9: no `time_stop_pts` of progress within N minutes -> out
    time_stop_pts: float = 2.0
    nfp_day: bool = True           # experienced (101, 105, 071): trade NFP Friday (entries from 09:30)
    nfp_week_block: bool = False   # beginner rule: no NFP-week Wed PM / Thu / Fri
    reverse_after_loss: bool = True    # experienced (001 ~47:32): may reverse after a losing trade
    fomc_pm_from: int = 885          # D8 test: FOMC-day PM entries allowed from this time (885)
    nfp_thu: bool = True           # D8 test: trade the Thursday of NFP week
    skip_cpi: bool = False         # D9 test
    skip_monday: bool = False      # D20 test (NFP / FOMC weeks still traded)
    no_pm_after_am_win: bool = False   # D19 test
    max_trades_week: int = 0           # D19 test (0 = no cap)
    reentry_half: bool = False     # D18 test: one same-direction re-entry at half risk after a loss
    conf_min_n: int = 0            # min number of timeframes (1m..monthly) with a PD array at the
    conf_min_top: str = ""         # sweep extreme / highest such timeframe (confluence.py); 0/"" off
    gap_mode: str = "ict"          # opening-gap targets: "ict" = NWOG (Fri close -> Sun 18:00, last
                                   # 5) + this week's NDOGs, high/CE/low; "monday" = the old
                                   # Fri 16:00 -> Mon 09:30 edges (also the fallback without overnight bars)
    nwog_days: int = 60            # NWOGs from the last 60 trading days (ICT's maximum, 051/065);
    nwog_keep: int = 5             # used when nwog_days = 0: the last N NWOGs (039: "4, preferably 5")
    org_days: int = 5              # opening range gaps (prior 16:00 close -> 09:30 open) kept as
                                   # targets (high / 75% / CE / 25% / low); 0 = off (L7, D21)
    org_close: int = 975           # ORG uses the last price before this minute: 975 = 16:15 ES
                                   # settlement (7 videos), 960 = 16:00 (3 videos; SPY's close)
    or_minutes: int = 30           # opening range 09:30-10:00 (2023 videos); 60 = CC's 09:30-10:30;
                                   # its high/low are AM sweep pools and targets once complete; 0 off
    htf_targets: tuple = ("15m", "1h", "4h", "D")   # opposing FVGs / OBs / gaps on these
                                   # those timeframes as targets, near edge then CE (L9, P2)
    neutral_skip: bool = False     # B17/N8: skip the day after a range > 2x the 5-day average
    three_day_rule: bool = False   # B11: after 3 same-direction daily closes, not that direction on day 4
    tgif: bool = False             # M14: on Fridays after a one-way week, only the retrace direction
    pd3_exit: bool = False         # X: out once bodies close through 3 PD arrays (FVGs) against the trade
    sd_first_beyond: bool = True   # L12: with sd_targets, only the first SD level beyond the nearest pool
    topdown: tuple = ()            # e.g. ("D", "4h", "1h", "15m"): structure on these timeframes
    topdown_min: int = 0           # must agree with the trade on at least this many (0 = all)
    # pre-09:30 setups (test-only switches; mentorship/digests/pre_open_entries.md)
    pre_0700: bool = False         # 07:00-08:30 window (022, 032, 099), same model; flat before an
                                   # 08:30 release (pre_flat_0830)
    pre_flat_0830: bool = True
    pre_0900: bool = False         # 09:00-09:29 entries, any day (018, 056, 100)
    post_news: bool = False        # 08:30 release days: wait 30 min (065), then 09:00-09:29 entries
                                   # off the 08:30-09:00 range's high/low
    ma_deuce: bool = False         # 091: daily BISI premium + 1m FVG inverted before 08:00 ->
                                   # sell the retest 08:00-08:30 toward the BISI CE (and mirror)
    sb_model: bool = False         # ICT's Silver Bullet as its own setup (sb_model.py); off until a version holds up
    sb_room_pts: float = 5.0       # minimum room to the draw's exit price; 10 = new-trader switch (046)
    sb_target_pts: float = 5.0     # fixed-mode target only (sb_target_mode="fixed")
    sb_mgmt: str = "fixed"         # "fixed": all off at the first target (80% with sb_runner); "ladder":
                                   # scale out through the draw levels with the ladder rules
    sb_runner: bool = False        # keep 20% for the next draw, stop to breakeven
    sb_min_rr: float = 0.0         # optional reward:risk floor on t1 (x min_rr)
    sb_london: bool = False        # 03:00-04:00 window (futures only; SPY can't trade it)
    sb_setup: bool = False         # Silver Bullet as its own setup: one more trade inside each SB
                                   # window (10-11, 14-15) after that session's trade, tagged sb_am/sb_pm
    smt_min: int = 0               # B18: at least this many sister indices (NQ, YM) must have
                                   # failed to take their version of the swept level; 0 = tag only
    htf_bias: str = "off"          # daily HTF bias filter: off / react / draw / pd / combo / flip (htf.py)
    bias_neutral: str = "skip"     # with a bias filter, a 0 day: "skip" it or trade "both" sides
    lot: int = 1                   # units per contract: 1 for shares; 5 for MES, 2 for MNQ
                                   # (a unit is $1 per point, so P&L = points x units)

    # --- owner directives 2026-10-18 (mentorship/digests/owner_directive_specs.md) ------------
    # #1 last hour / PM session (T9, T10, T11, Ep01.11 - owner version, not pm_setup_window)
    last_hour_sweet: tuple = (915, 945)  # the typical sweet spot: tag lh_sweet only
    last_hour_strict: bool = False       # test: from 15:00 only setups inside the sweet spot
    session_close: int = 0               # 0 = auto (backtest.run / paper.py): 975 futures, 960 SPY
    # #2 five handles = minimum room (L15, M3, X14a, Ep03.24 - default OFF per the owner)
    t1_fixed_pts: float = 0.0            # Ep03.24 test: a fixed +N ES-pt first rung before the draw
    t1_fixed_all: bool = False           # with t1_fixed_pts: the whole position off at +N (no T2)
    day_target_pts: float = 0.0          # X14a test: stop for the day after N net ES pts
    sb_target_mode: str = "draw"         # Silver Bullet exits at the draw (owner #2); "fixed" = +5
    # #3 year end (Ep01.9, N7.4) - OWNER ANSWER PENDING: off until the mapping is confirmed
    year_end: str = "off"                # "december" (side from December's direction) / "long" (old
                                         # always-bullish) / "tag" (tags only) / "off"
    year_end_map: str = "squaring"       # Dec down -> long (Ep 01 Dec 2022); "with": Dec down -> short
                                         # (owner_directives.md l.23) - owner must confirm
    year_end_days: int = 1               # the last N trading days of the year
    year_end_flat_frac: float = 0.25     # [our interpretation] |Dec close-open| < 25% of its range = flat
    # #4 news dealing range (N5, N5.1, N5.2, Ep04.5) - the 30-minute wait is NFP-only
    news_wait: str = "range"             # wait for each release's dealing range, then trade from it;
                                         # "fixed" = 065B's news_wait_min after every release; "off" = old
    news_wait_min: int = 30              # "fixed" mode only (NOT a default rule; owner #4)
    nfp_floor_min: int = 30              # jobs day: "the first 30 minutes or so" is a floor (Ep04 ~8:23)
    news_range_max_min: int = 90         # [our interpretation] no range by R+90 -> no entries after R
    news_range_pivot: int = 0            # swing size for the range's high/low (0 = pivot_n)
    news_range_target: bool = True       # the range's opposite extreme is a target
    news_range_pd: bool = False          # test: entry must be in the range's discount (premium)
    # #5 unicorn both ways (A14, M4)
    unicorn_sides: str = "both"          # "long" / "short" switch the other side off
    # #6 breaker mean threshold (A13.3, Ep02.3, Ep05.1)
    breaker_mt_mode: str = "range"       # 50% of the breaker candle's full high-low; "body" switch
    breaker_mt_respect: bool = True      # a body close below the breaker MT loses the breaker / cancels /
                                         # exits a unicorn trade (wicks may poke; Ep 02 ~3:37-3:54)
    breaker_mt_entry_floor: bool = True  # unicorn entry not below the breaker MT (+1 tick)
    breaker_mt_exit_after_t1: bool = False
    conf_breakers: bool = False          # confluence: breaker zones with inv = MT (slow on 1m data)
    # #7 opposing HTF FVG = resistance cap (Ep02.10, L9, X3f)
    htf_resist_cap: bool = True
    htf_resist_tfs: tuple = ("15m", "30m", "1h", "4h", "D")
    htf_resist_src: tuple = ("fvg",)     # "ob" / "gap" / "vi" / "breaker" as switches
    htf_resist_buffer_pts: float = 0.5   # exit this many ES pts before its near edge
    htf_resist_min_room: float = 0.0     # ES pts; 5 = owner #2's minimum room to the cap
    htf_resist_live: bool = False        # recompute the cap at every bar close and trim the rungs
    htf_targets_30m: bool = False        # Ep02.5: add 30m arrays to htf_targets (separate step)
    runner_htf_exit: str = ""            # "30m": after T1, out once the same-side 30m FVG at the entry dies
    # #8 "tighten or close" before noon = close (X10, Ep03.23, D16)
    am_exit_mode: str = "close"          # "tighten" = test only [our interpretation]
    am_exit_extras: bool = True          # am_exit also for SB-AM, London SB and Ma Deuce
    # #9 lock ONE draw per session before it opens (B3, L14, L14a, M0.1, M3.2)
    draw_lock: str = "session"           # "off" = scan both sides with the old targets
    draw_lock_pick: str = "nearest"      # [our interpretation] the nearer marked level sets the side
    draw_lock_neutral: str = "skip"      # no / tied candidates: "skip" the session or trade "both"
    draw_lock_levels: str = "frozen"     # rungs before the draw: levels marked at the lock, or "live"
    draw_lock_partials: bool = True      # False: everything off at the draw
    draw_relock: bool = False            # test: lock a new draw once the first is delivered
    draw_lock_near_cap: bool = False     # test: drop lock candidates beyond the nearest HTF cap
    draw_lock_min_pts: float = 5.0       # [our interpretation] a draw must lie at least this many ES pts
                                         # from the lock price (owner #2: 5 handles = minimum room)
    # #10 sloppy days (B17.4, N8.1, Ep08.2) - OWNER ANSWER PENDING: tag only for now
    sloppy_mode: str = "off"             # "off" = tag only; "stand_aside" (owner #10); "scalp"
    sloppy_tests: tuple = ("big_prev", "chop", "nfp_week")
    sloppy_big_mult: float = 2.0         # [our interpretation] prior range > 2x ADR5
    sloppy_chop_frac: float = 0.35       # [our interpretation] range since midnight < 0.35x ADR5 ...
    sloppy_chop_cross: int = 4           # ... and >= 4 close crossings of the midnight open
    sloppy_chop_from: int = 120          # checked from 02:00
    sloppy_release_frac: float = 0.25    # released by a close 0.25x ADR5 beyond the chop range
    sloppy_scalp_pts: float = 5.0        # scalp mode: single exit at min(+5, T1)
    # #11 Ep 07 advanced entry at the order-block bodies before the break (M1.4, D10, Ep07.2/5)
    ob_entry: str = "pre_break"          # "post_mss" = FVG after the MSS (old); "both"
    ob_entry_px: str = "body_top"        # "mt" (body midpoint) / "range_top"
    ob_arm: str = "leave"                # [our interpretation] armed once a close leaves the bodies;
                                         # "touch" = the bar after the block
    ob_stop: str = "mt"                  # body MT - buffer, else the sweep extreme ("ext")
    ob_entry_cancel_on_mss: bool = False # "both": an FVG order after the MSS replaces the OB order
    ob_adds: bool = True                 # [our interpretation] add at a fresh down-close block's bodies
    # #12 risk (E8, E11): 1.2% at entry, 1.3% with adds - not 2%
    account_equity: float = 100_000.0
    risk_pct: float = 0.012
    max_total_risk_pct: float = 0.013
    risk_basis: str = "fixed"            # "equity" = start-of-day equity from earlier closed trades
    # #13 front-month prices (DATA1; L17, Ep02.2, N7.5)
    price_frame: str = "front_month"     # report / absolute levels in the real contract's prices;
                                         # "back_adjusted" = old reports; "raw" = bars are raw already
    round_pools: bool = True             # untaken round handles (ES 00/50) as pools and targets (Ep 02
                                         # "3 900"); futures with meta only
    round_pool_step_pts: float = 0.0     # 0 = per symbol (ES 50, NQ 100, YM 500); 25 = alternative
    # --- verified bugs -----------------------------------------------------------------------
    seen_from_created: bool = True       # M7.1 fix: a pool is spent only if traded through AFTER it
                                         # formed (the lunch / overnight / AM highs could never be targets)
    pm_off_lunch: bool = False           # M7.1: PM draw = the lunch high (low) when it is untaken
    pm_judas_1330: bool = False          # M7.1: PM sweep must be the move against the 13:30 open
    displacement_mult: float = 0.0       # M1.2 option: MSS candle body >= N x the mean body of the
                                         # 10 bars before it [our interpretation]; 0 = off
    # --- shared helpers (rule_coverage.md "Shared pieces to build first") -------------------
    vi_arrays: bool = False              # VI wiring: volume imbalances in confluence / htf arrays
    turtle_soup: str = ""                # M12 core: "2023" (no MSS: close back above the swept level)
    ts_max_pts: float = 5.0              # false break "by a little": at most this many ES pts
    ts_back_bars: int = 3                # close back above within this many bars of the extreme
    ts_need_htf: bool = False            # the sweep must reach into an HTF array (htf tag)

    def __post_init__(self):
        if self.unicorn_sides not in ("both", "long", "short"):
            raise ValueError(f"unicorn_sides {self.unicorn_sides!r}")
        if self.breaker_zone in ("leg", "last"):
            raise NotImplementedError("planned D6")
        if self.breaker_zone not in L.BREAKER_MODES:
            raise ValueError(f"breaker_zone {self.breaker_zone!r}")
        if self.breaker_mt_mode not in ("range", "body"):
            raise ValueError(f"breaker_mt_mode {self.breaker_mt_mode!r}")
        for name, ok in (("news_wait", ("range", "fixed", "off")), ("draw_lock", ("session", "off")),
                         ("draw_lock_neutral", ("skip", "both")), ("draw_lock_levels", ("frozen", "live")),
                         ("draw_lock_pick", ("nearest",)),
                         ("ob_entry", ("pre_break", "post_mss", "both")),
                         ("ob_entry_px", ("body_top", "mt", "range_top")), ("ob_arm", ("leave", "touch")),
                         ("ob_stop", ("mt", "ext")), ("risk_basis", ("fixed", "equity")),
                         ("price_frame", ("front_month", "back_adjusted", "raw")),
                         ("sloppy_mode", ("off", "stand_aside", "scalp")),
                         ("year_end", ("december", "long", "tag", "off")),
                         ("year_end_map", ("squaring", "with")), ("am_exit_mode", ("close", "tighten")),
                         ("sb_target_mode", ("draw", "fixed")), ("runner_htf_exit", ("", "15m", "30m", "1h")),
                         ("turtle_soup", ("", "2023"))):
            if getattr(self, name) not in ok:
                raise ValueError(f"{name} {getattr(self, name)!r}: expected one of {ok}")


def _eff_flat(p: "Params") -> int:
    """Flatten minute: an explicit `flatten`, else the resolved session close, else 16:00."""
    return p.flatten or p.session_close or 960


EQUITY_SYMBOLS = {"SPY", "QQQ", "IWM", "DIA", "RW"}


def resolve_session_close(p: "Params", df: pd.DataFrame, symbol: str):
    """Owner #1: resolve session_close once per run (16:15 for index futures / CFDs with an
    evening session, 16:00 for SPY and other cash ETFs). Returns a copy of p."""
    if p.session_close:
        return p
    from .htf import has_overnight
    fut = symbol.upper() not in EQUITY_SYMBOLS and has_overnight(df)
    return replace(p, session_close=975 if fut else 960)


def _risk_budget(p: "Params", eq: float) -> float:
    return p.risk_dollars if p.risk_dollars is not None else p.risk_pct * eq


def _total_cap(p: "Params", eq: float) -> float:
    return p.max_total_risk if p.max_total_risk is not None else p.max_total_risk_pct * eq


def _first_units(p: "Params", eq: float, risk: float, entry: float, risk_mult: float = 1.0) -> int:
    """Owner #12: the first unit risks risk_pct (1.2%) of equity, never more than the total cap."""
    return _lots(min(risk_mult * _risk_budget(p, eq) / risk, _total_cap(p, eq) / risk,
                     p.max_notional / abs(entry)), p.lot)


def adr5(days: list) -> float | None:
    """Average daily range of 5 sessions (shared helper: N8, X16a, L16, X10d, X14b, #10)."""
    if len(days) < 5:
        return None
    return float(np.mean([float(x.high.max() - x.low.min()) for x in days[-5:]]))


_adr5 = adr5


def _lots(x: float, lot: int) -> int:
    return int(x // lot) * lot


def blocked(d: date, session: str, p: "Params | None" = None, t: int = 0) -> str | None:
    """Day-type rule that blocks this session (at minute t), or None."""
    tags = events(d)
    if "jobs" in tags and not (p is not None and p.nfp_day):
        return "nfp_day"
    mon = d - timedelta(days=d.weekday())
    jd = [j for j in JOBS if mon <= j <= mon + timedelta(days=4)]
    week_block = p is None or p.nfp_week_block
    if jd and week_block and d.weekday() >= 3 and "jobs" not in tags and not (p is not None and p.nfp_thu and d.weekday() == 3):
        return "nfp_week_thu_fri"
    if jd and week_block and d.weekday() == 2 and session == "PM":
        return "nfp_week_wed_pm"
    if "fomc" in tags and session == "PM" and not (p is not None and p.fomc_pm_from and t >= p.fomc_pm_from):
        return "fomc_pm"
    if p is not None and p.skip_cpi and "cpi" in tags:
        return "cpi"
    if p is not None and p.skip_monday and d.weekday() == 0:
        week = [mon + timedelta(days=k) for k in range(5)]
        if not jd and not any("fomc" in events(x) for x in week):
            return "monday"
    return None


def news(d: date) -> str:
    tags = events(d)
    return "0830" if tags & NEWS_0830 else ("1000" if tags & NEWS_1000 else "none")


def weekly_bias(hist: list[pd.DataFrame], day: date, k: float = 1.5) -> int:
    """-1: a strong down day earlier this week and no daily close since back above 50% of
    its upper wick (favor shorts). +1 mirrors it. 0 otherwise. Uses completed days only."""
    days = [(g.index[0].date(), float(g.open.iloc[0]), float(g.high.max()), float(g.low.min()),
             float(g.close.iloc[-1])) for g in hist[-15:]]
    iso = day.isocalendar()[:2]
    bias, level = 0, None
    for j, (d, o, h, l, c) in enumerate(days):
        if d.isocalendar()[:2] != iso:
            continue
        if bias and level is not None and (c > level if bias < 0 else c < level):
            bias, level = 0, None                    # closed back through the wick midpoint
        prior = [x[2] - x[3] for x in days[max(0, j - 10):j]]
        if len(prior) < 5 or h - l < k * np.mean(prior):
            continue
        if c < o and c <= l + 0.25 * (h - l):
            bias, level = -1, o + (h - o) / 2
        elif c > o and c >= h - 0.25 * (h - l):
            bias, level = 1, o - (o - l) / 2
    return bias


@dataclass
class Trade:
    date: date
    symbol: str
    session: str
    setup: str
    side: str
    swept: str
    unicorn: bool
    smt: bool | None
    armed: pd.Timestamp
    entry_time: pd.Timestamp
    entry: float
    stop: float
    t1: float
    t2: float | None
    shares: int
    exits: list = field(default_factory=list)   # (time, price, shares, reason)
    adds: list = field(default_factory=list)    # (time, price, shares)
    day_type: str = ""
    htf: bool | None = None
    macro: bool = False
    news: str = "none"
    wbias: int = 0
    b_react: int | None = None
    b_draw: int | None = None
    b_pd: int | None = None
    sb: bool = False
    weekday: int = 0
    conf_n: int | None = None
    conf_top: str = ""
    conf_tfs: str = ""
    entry_kind: str = "fvg"        # fvg / ifvg / 5m entry modes keep "fvg"
    mitigation: bool = False       # entry gap overlaps a mitigation block
    propulsion: bool = False       # a propulsion block sits under the entry
    macro_win: str = ""            # ICT macro window at arming time
    td_agree: int | None = None    # of D/4h/1h/15m, how many have structure in the trade's direction
    day_tags: str = ""             # inside_day / big_prev / three_up / three_down / tgif_long|short
    judas: bool = False            # the sweep was the session's first move against the trade (PO3)
    dxy: int = 0                   # DXY daily trend (close vs 20-day mean, prior day): +1 / -1
    tnx: int = 0                   # 10-year yield daily trend, same way
    smt2: bool | None = None       # second sister index (YM)
    smt_n: int = 0                 # sister indices that did not confirm the sweep
    # owner directives 2026-10-18 (all default so sb_model / pre_open Trade calls still work)
    lh_sweet: bool = False         # #1: armed inside the 15:15-15:45 sweet spot
    unicorn_side: str = ""         # #5: "bull" / "bear" when the entry gap is a unicorn
    bz_top: float | None = None    # #5/#14: breaker zone (real prices)
    bz_bottom: float | None = None
    bz_mt: float | None = None     # #6: breaker mean threshold the trade respects (real price)
    resist_tf: str = ""            # #7: the opposing HTF array that capped the trade
    resist_lo: float | None = None
    resist_hi: float | None = None
    capped: bool = False
    draw_side: int = 0             # #9: the session's locked draw
    draw_px: float | None = None
    draw_name: str = ""
    draw_kind: str = ""
    sloppy: str = ""               # #10: sloppy-day reasons active at arming (tag in every mode)
    news_wait_min_actual: float | None = None   # #4: minutes from the release to the range's completion
    news_pd: bool | None = None    # #4: entry in the news range's discount (long) / premium (short)
    entry_risk_pct: float | None = None   # #12: open risk at the fill / equity
    peak_risk_pct: float | None = None    # #12: largest open risk incl. adds / equity
    contract: int | None = None    # #13: instrument id at the fill (databento meta)
    adj: float = 0.0               # #13: back-adjustment at the fill (real = engine - adj)
    roll_day: bool = False         # N7.5 hook: a contract roll from the prior 18:00 through the day

    REAL_FIELDS = ("entry", "stop", "t1", "t2", "draw_px", "bz_top", "bz_bottom", "bz_mt",
                   "resist_lo", "resist_hi")

    def pnl(self, cost: float) -> tuple[float, float]:
        s = 1 if self.side == "long" else -1
        bought = self.entry * self.shares + sum(px * q for _, px, q in self.adds)
        gross = s * (sum(px * q for _, px, q, _ in self.exits) - bought)
        n = self.shares + sum(q for *_, q in self.adds)
        return gross, cost * 2 * n

    def row(self, cost: float) -> dict:
        gross, costs = self.pnl(cost)
        risk = self.shares * abs(self.entry - self.stop)
        d = {k: v for k, v in asdict(self).items() if k not in ("exits", "adds")}
        if self.adj:                   # #13: report real contract prices (P&L is unchanged)
            for k in self.REAL_FIELDS:
                if d.get(k) is not None:
                    d[k] = round(d[k] - self.adj, 6)
        d.update(n_adds=len(self.adds), gross=round(gross, 2), costs=round(costs, 2),
                 net=round(gross - costs, 2), R=round((gross - costs) / risk, 3) if risk else 0.0,
                 exit_time=self.exits[-1][0] if self.exits else None,
                 exit_reason="+".join(e[3] for e in self.exits) or "open")
        return d


class Side:
    """One direction of one day, in bullish terms (mirrored prices for shorts)."""

    def __init__(self, sign, o, h, l, c, n, min_gap: float = 0.0):
        self.sign = sign
        if sign > 0:
            self.o, self.h, self.l, self.c = o, h, l, c
        else:
            self.o, self.h, self.l, self.c = -o, -l, -h, -c
        self.ph, self.pl = L.pivots(self.h, self.l, n)
        self.gaps = [z for z in L.fvgs(self.h, self.l) if z.kind == "bull" and z.top - z.bottom >= min_gap]
        self.min_gap = min_gap
        self.sweep = None
        self.n = n
        self._ifvg = self._opp = self._mit = self._prop = None

    # lazily built arrays (only the switches that use them pay for them)
    def ifvgs(self):
        if self._ifvg is None:
            self._ifvg = [z for z in L.inversion_fvgs(self.h, self.l, self.c, self.min_gap) if z.kind == "bull"]
        return self._ifvg

    def opposing(self):
        """Bearish FVGs and voids (resistance above, in side terms), for targets."""
        if self._opp is None:
            self._opp = [z for z in L.fvgs(self.h, self.l) + L.voids(self.h, self.l)
                         if z.kind == "bear" and z.top - z.bottom >= self.min_gap]
        return self._opp

    def mitigations(self):
        if self._mit is None:
            self._mit = [z for z in L.mitigation_blocks(self.o, self.h, self.l, self.c, self.n) if z.kind == "bull"]
        return self._mit

    def zones_tf(self, idx, base: int, m: int):
        """Bullish FVGs and order blocks on m-minute bars built from these (side-space) bars,
        as Zones in base-bar index terms: `i` = the base bar at whose close the m-minute bar
        that completes the zone has closed, `src` = the first base bar of its middle candle
        (FVG) or anchor candle (OB). Cached per m."""
        cache = self.__dict__.setdefault("_tfc", {})
        if m in cache:
            return cache[m]
        b = pd.Series(np.arange(len(idx)), index=idx).groupby(idx.floor(f"{m}min"))
        first, last = b.min().values, b.max().values
        start = b.min().index
        # a bucket counts only once its last base bar is in (else a partial bar at the end of
        # live data would complete a zone early)
        done = (idx[last] - start) >= pd.Timedelta(minutes=m - base)
        o = np.array([self.o[a] for a in first]); c = np.array([self.c[z] for z in last])
        hh = np.array([self.h[a:z + 1].max() for a, z in zip(first, last)])
        ll = np.array([self.l[a:z + 1].min() for a, z in zip(first, last)])
        out = []
        for z in L.fvgs(hh, ll):
            if z.kind != "bull" or z.top - z.bottom < self.min_gap:
                continue
            if not done[z.i]:
                continue
            out.append(L.Zone("bull", z.top, z.bottom, int(last[z.i]), int(first[z.src])))
            ob = L.order_block_blend(o, hh, ll, c, z.i - 4, z.i - 2, "bull")
            if ob is not None and c[z.i - 1] > ob.top:
                out.append(L.Zone("bull", ob.top, ob.bottom, int(last[z.i]), int(first[ob.src]), ob.mt))
        cache[m] = out
        return out

    def propulsions(self):
        if self._prop is None:
            obs = []
            for g in self.gaps:
                ob = L.order_block_blend(self.o, self.h, self.l, self.c, g.i - 4, g.i - 2, "bull")
                if ob is not None and self.c[g.i - 1] > ob.top:
                    obs.append(L.Zone("bull", ob.top, ob.bottom, g.i, ob.src, ob.mt))
            self._prop = L.propulsion_blocks(self.o, self.h, self.l, self.c, obs)
        return self._prop

    def x(self, price):
        return self.sign * price


def htf_bars(df: pd.DataFrame, m: int) -> pd.DataFrame:
    """Clock-aligned m-minute bars with the time each one completes (`end`)."""
    g = df.groupby(df.index.floor(f"{m}min"))
    out = pd.DataFrame({"open": g.open.first(), "high": g.high.max(), "low": g.low.min(),
                        "close": g.close.last()})
    out["end"] = out.index + pd.Timedelta(minutes=m)
    return out


class DayCtx:
    """Bars for one day (04:00-16:00) preceded by the previous session (RTH), plus the
    levels known before the open."""

    def __init__(self, df: pd.DataFrame, day: date, hist: list[pd.DataFrame], tf: int,
                 htf: tuple = (), closes: dict | None = None, or_minutes: int = 30,
                 evening: pd.DataFrame | None = None):
        prev = hist[-1]
        self.day, self.tf = day, tf
        frame = pd.concat([prev, df])
        self.idx = frame.index
        self.t = (self.idx.hour * 60 + self.idx.minute).values
        self.o, self.h, self.l, self.c = (frame[k].values.astype(float) for k in ("open", "high", "low", "close"))
        self.start = len(prev)
        self.opens = L.opens(df.index, df.open.values)
        self.pd = {}
        last3 = hist[-3:]
        for k, hd in enumerate(reversed(last3), 1):
            later = last3[len(last3) - k + 1:]          # days after this one (already traded)
            hi, lo = float(hd.high.max()), float(hd.low.min())
            if not later or max(float(x.high.max()) for x in later) < hi:
                self.pd[f"pdh{k}"] = hi                  # only highs no later day has taken
            if not later or min(float(x.low.min()) for x in later) > lo:
                self.pd[f"pdl{k}"] = lo
        po, ph, pl, pc = (float(prev.open.iloc[0]), float(prev.high.max()), float(prev.low.min()),
                          float(prev.close.iloc[-1]))
        self.wick = L.wick_midpoints(po, ph, pl, pc)
        tt = df.index.hour * 60 + df.index.minute
        pre = df[tt < 570]                         # overnight: midnight (SPY: 04:00) to 09:30
        if evening is not None and len(evening):
            pre = pd.concat([evening, pre])           # globex: from the prior 18:00 reopen
        if len(pre):
            self.pd["pmh"], self.pd["pml"] = float(pre.high.max()), float(pre.low.min())
        # the same overnight range as known at an earlier session start (no look-ahead)
        self.pre_at = {}
        for m in (420, 540):
            q = pre[(pre.index.hour * 60 + pre.index.minute < m) | (pre.index.date < df.index[0].date())]
            if len(q):
                self.pre_at[m] = (float(q.high.max()), float(q.low.min()))
        nr = df[(tt >= 510) & (tt < 540)]          # 08:30-09:00 news range
        self.news_hl = (float(nr.high.max()), float(nr.low.min())) if len(nr) else None
        am = df[(tt >= 570) & (tt < 810)]
        self.am_hl = (float(am.high.max()), float(am.low.min())) if len(am) else None
        # session pools (067): London 02:00-05:00 and prior PM 13:30-16:00 for the AM; lunch
        # 12:00-13:30 for the PM. Each with the bar index from which it is complete.
        self.sess = {}
        self.pw = self.pm_ = None
        d0 = df.index[0].date()
        wk = [x for x in hist if x.index[0].date().isocalendar()[:2] == (d0 - timedelta(days=7)).isocalendar()[:2]]
        if wk:
            self.pw = (max(float(x.high.max()) for x in wk), min(float(x.low.min()) for x in wk))
        pmo = (d0.replace(day=1) - timedelta(days=1))
        mo = [x for x in hist if (x.index[0].year, x.index[0].month) == (pmo.year, pmo.month)]
        if mo:
            self.pm_ = (max(float(x.high.max()) for x in mo), min(float(x.low.min()) for x in mo))
        lon = df[(tt >= 120) & (tt < 300)]
        if len(lon):
            self.sess["london"] = (float(lon.high.max()), float(lon.low.min()), 300)
        pt = prev.index.hour * 60 + prev.index.minute
        ppm = prev[(pt >= 810) & (pt < 960)]
        if len(ppm):
            self.sess["prev_pm"] = (float(ppm.high.max()), float(ppm.low.min()), 0)
        lun = df[(tt >= 720) & (tt < 810)]
        if len(lun):
            self.sess["lunch"] = (float(lun.high.max()), float(lun.low.min()), 810)
        self.nwog = []
        for a, b in zip(hist[-21:], hist[-20:] + [df]):
            if (b.index[0].date() - a.index[-1].date()).days >= 3 or b.index[0].weekday() < a.index[-1].weekday():
                rth = b[(b.index.hour * 60 + b.index.minute) >= 570]
                if len(rth):
                    self.nwog.append((float(a.close.iloc[-1]), float(rth.open.iloc[0])))
        self.nwog = self.nwog[-4:]
        # opening range gaps: each day's prior RTH close -> its 09:30 open (today's included)
        self.org = []
        self.org_today = False                 # True when the last ORG is today's (09:30-based)
        seq = hist[-6:] + [df]
        for a, b in zip(seq[:-1], seq[1:]):
            rth = b[(b.index.hour * 60 + b.index.minute) >= 570]
            if len(rth) and len(a):
                pc = (closes or {}).get(a.index[0].date(), float(a.close.iloc[-1]))
                self.org.append((float(pc), float(rth.open.iloc[0])))
                self.org_today = b is df
        # opening range 09:30 -> 09:30 + or_minutes: high/low usable once it is complete
        self.or_end, self.or_hl = 570 + or_minutes, None
        orb = df[(tt >= 570) & (tt < 570 + or_minutes)] if or_minutes else df.iloc[:0]
        if len(orb):
            self.or_hl = (float(orb.high.max()), float(orb.low.min()))
        self.wbias = weekly_bias(hist, day)
        # higher-timeframe FVGs over the last 5 sessions, in real prices, with the time known
        self.hzones = []
        if htf:
            full = pd.concat(hist[-5:] + [df])
            self.full_c = full.close.values.astype(float)
            self.full_idx = full.index
            self.full_off = len(full) - len(frame)      # bar i of `frame` is full_off + i
            for m in htf:
                hb = htf_bars(full, m)
                for z in L.fvgs(hb.high.values, hb.low.values):
                    self.hzones.append((z, hb.end.iloc[z.i], m))


def _htf_tag(ctx: DayCtx, sd: Side, i: int, price: float, tol: float) -> bool | None:
    """True if `price` (side space) sits in a still-open higher-timeframe FVG of the trade's
    direction known by the close of bar i."""
    if not ctx.hzones:
        return None
    now = ctx.idx[i] + pd.Timedelta(minutes=ctx.tf)
    j = ctx.full_off + i
    for z, known, m in ctx.hzones:
        if known > now or z.kind != ("bull" if sd.sign > 0 else "bear"):
            continue
        top, bot = (z.top, z.bottom) if sd.sign > 0 else (-z.bottom, -z.top)
        k = int(ctx.full_idx.searchsorted(known))
        closes = sd.sign * ctx.full_c[k:j + 1]
        if len(closes) and closes.min() < bot:
            continue                                  # closed through: no longer open
        if bot - tol <= price <= top + tol:
            return True
    return False


def _idx_at(ctx, m: int) -> int:
    """First bar of today starting at or after minute m (len(ctx.t) if none yet)."""
    return ctx.start + int(np.searchsorted(ctx.t[ctx.start:], m))


ROUND_STEP = {"ES": 50.0, "MES": 50.0, "SPX": 50.0, "NQ": 100.0, "MNQ": 100.0, "NDX": 100.0,
              "YM": 500.0, "MYM": 500.0}


def _round_levels(ctx, sd, i: int, beyond: bool, n: int = 1) -> list[float]:
    """#13 / Ep02.2: untaken round handles in side space. beyond=False: the nearest round level
    below today's low so far (sell-side, bars start..i-1); beyond=True: the next n above today's
    high through bar i (buy-side targets). Real (front-month) level R maps to the engine at
    R + adj of the latest closed bar (look-ahead free)."""
    st = getattr(ctx, "round_step", 0.0)
    if not st or getattr(ctx, "adj", None) is None:
        return []
    if beyond:
        if i < ctx.start:
            return []
        ext, adj = sd.h[ctx.start:i + 1].max(), float(ctx.adj[i])
    else:
        if i - 1 < ctx.start:
            return []
        ext, adj = sd.l[ctx.start:i].min(), float(ctx.adj[i - 1])
    raw = sd.x(ext) - adj                     # real front-month price of today's extreme
    up = (sd.sign > 0) == beyond              # real direction to look in
    out = []
    if up:
        r = np.ceil(raw / st) * st
        if r <= raw:
            r += st
        out = [r + k * st for k in range(n)]
    else:
        r = np.floor(raw / st) * st
        if r >= raw:
            r -= st
        out = [r - k * st for k in range(n)]
    return [sd.x(float(v) + adj) for v in out]


def _targets(ctx: DayCtx, sd: Side, i: int, above: float, eq: list[float], p: Params,
             leg: tuple | None = None, ext_i: int | None = None) -> list[tuple[float, str]]:
    """Buy-side liquidity (in side terms) above `above`, known at bar i, each with its kind:
    "pool" (old highs, equal highs, session highs) or "array" (gaps, wick CE, projections).
    A pool already traded through today before the sweep (bars ..ext_i) is spent (L14); with
    seen_from_created (M7.1 fix) only bars AFTER the pool formed count, so a session's own high
    (overnight, London, AM, lunch) is no longer spent by the bars that made it. Gap levels are
    never retired (039)."""
    pre_open = ctx.t[i] < 570
    at = lambda m: _idx_at(ctx, m)
    pdk = ("pdh1", "pdh2", "pdh3") if sd.sign > 0 else ("pdl1", "pdl2", "pdl3")
    pools = [(sd.x(ctx.pd[k]), ctx.start) for k in pdk if k in ctx.pd] + [(v, None) for v in eq]
    if not pre_open:                        # the overnight range is complete only at 09:30
        k = "pmh" if sd.sign > 0 else "pml"
        if k in ctx.pd:
            pools.append((sd.x(ctx.pd[k]), at(570)))
    else:                                   # pre-open sessions: the overnight range so far
        m = max((m for m in ctx.pre_at if m <= ctx.t[i]), default=None)
        if m is not None:
            hi, lo = ctx.pre_at[m]
            pools.append((sd.x(hi if sd.sign > 0 else lo), at(m)))
    if p.extra_pools:
        for name, (hi, lo, ready) in ctx.sess.items():
            if ctx.t[i] >= ready:           # complete only from `ready` (London 05:00: a 03:00 London
                created = ctx.start if name == "prev_pm" else at(ready)   # SB no longer sees it early)
                pools.append((sd.x(hi if sd.sign > 0 else lo), created))
    if ctx.or_hl is not None and ctx.t[i] >= ctx.or_end:
        pools.append((sd.x(ctx.or_hl[0] if sd.sign > 0 else ctx.or_hl[1]), at(ctx.or_end)))
    if ctx.t[i] >= 810 and ctx.am_hl:
        pools.append((sd.x(ctx.am_hl[0] if sd.sign > 0 else ctx.am_hl[1]), at(810)))
    for on, hl in ((p.pool_prev_week, ctx.pw), (p.pool_prev_month, ctx.pm_)):
        if on and hl is not None:
            pools.append((sd.x(hl[0] if sd.sign > 0 else hl[1]), ctx.start))
    if p.pool_swings:                       # untaken short-term swing highs known by bar i
        pools += [(q.price, None) for q in sd.ph if q.known <= i and q.i >= ctx.start - 1
                  and sd.h[q.i + 1:i + 1].max(initial=-np.inf) < q.price]
    if p.news_range_target:                 # #4: the news dealing range's opposite extreme
        for R, d in getattr(ctx, "news_dr", {}).items():
            if d["made"] is not None and d["made"] <= i:
                pools.append((sd.x(d["hi"] if sd.sign > 0 else d["lo"]), d["made"] + 1))
    pools += [(v, None) for v in _round_levels(ctx, sd, i, True, 2)]   # #13 round handles
    if p.seen_from_created:
        lv = []
        for v, cr in pools:
            if cr is None or ext_i is None or ext_i <= max(cr, ctx.start):
                lv.append((v, "pool"))
            elif v > sd.h[max(cr, ctx.start):ext_i].max():
                lv.append((v, "pool"))
    else:                                   # the old rule: anything above today's high so far
        seen = sd.h[ctx.start:ext_i].max() if ext_i is not None and ext_i > ctx.start else -np.inf
        lv = [(v, "pool") for v, _ in pools if v > seen]
    if getattr(ctx, "gaps", None) is not None:
        for _, hi, lo, ce in ctx.gaps:
            lv += [(sd.x(hi), "array"), (sd.x(ce), "array"), (sd.x(lo), "array")]
    else:
        for a, b in ctx.nwog:
            lv += [(sd.x(a), "array"), (sd.x(b), "array")]
    if p.org_days:
        orgs = ctx.org[:-1] if (pre_open and ctx.org_today) else ctx.org
        for a, b in orgs[-p.org_days:]:
            lv += [(sd.x(a + q * (b - a)), "array") for q in (0.0, 0.25, 0.5, 0.75, 1.0)]
    if p.wick_levels:
        lv.append((sd.x(ctx.wick["upper"] if sd.sign > 0 else ctx.wick["lower"]), "array"))
    if p.sd_targets and leg is not None:
        lo, hi = leg
        sds = [hi + k * (hi - lo) for k in p.sd_levels]
        if p.sd_first_beyond:              # only the first SD level beyond the nearest pool (014/030)
            pool = min((v for v, kind in lv if kind == "pool" and v > above), default=None)
            sds = [min((x for x in sds if x > pool), default=None)] if pool is not None else []
        lv += [(x, "array") for x in sds if x is not None]
    out = []
    for v, kind in sorted(x for x in set(lv) if x[0] > above):   # merge levels within ~1 ES point
        if not out or v - out[-1][0] > p.es_pt:
            out.append((v, kind))
    return out


def _eq_levels(sd: Side, i: int, tol: float, lows: bool) -> list[float]:
    """Relative equal highs (lows) from swings confirmed by bar i and not yet traded through."""
    piv = sd.pl if lows else sd.ph
    out = []
    for p in piv:
        if p.known > i:
            break
        after = sd.l[p.i + 1:i + 1] if lows else sd.h[p.i + 1:i + 1]
        if (len(after) == 0) or (after.min() > p.price if lows else after.max() < p.price):
            out.append(-p.price if lows else p.price)
    lv = L.equal_levels(out, tol)
    return [-v for v in lv] if lows else lv


def _close(pos, trades, p):
    tr = pos["trade"]
    trades.append(tr)
    gross, costs = tr.pnl(p.cost_per_share)
    return tr.side if gross - costs < 0 else None


def _after_close(pos, trades, p, done, state):
    """Record the trade; apply the session rules that depend on how it ended."""
    lost = _close(pos, trades, p)
    tr = pos["trade"]
    if lost is None and tr.session == "AM" and p.no_pm_after_am_win:
        done["PM"] = True
    if lost is not None and p.reentry_half and not state["reentered"].get(tr.session):
        done[tr.session] = False                      # one more try, same direction, half risk
        state["reentered"][tr.session] = True
    if p.day_target_pts:                              # X14a test (owner #2): N net ES pts -> done
        gross, costs = tr.pnl(p.cost_per_share)
        units = tr.shares + sum(q for *_, q in tr.adds)
        state["day_pts"] = state.get("day_pts", 0.0) + (gross - costs) / max(units, 1) / p.es_pt
        if state["day_pts"] >= p.day_target_pts:
            for k in list(done):
                done[k] = True
            state["day_done"] = True
    return lost


def december_dir(hist: list[pd.DataFrame], day, flat_frac: float = 0.25) -> int:
    """Owner #3: December's direction from the completed December sessions before `day` (+1 up,
    -1 down, 0 flat / unknown). 0 with fewer than 5 such sessions or when the history does not
    reach back before Dec 1 (December's first session could be missing)."""
    dec = [x for x in hist if x.index[0].date().year == day.year and x.index[0].date().month == 12
           and x.index[0].date() < day]
    if len(dec) < 5 or not any(x.index[0].date() < date(day.year, 12, 1) for x in hist):
        return 0
    o, c = float(dec[0].open.iloc[0]), float(dec[-1].close.iloc[-1])
    rng = max(float(x.high.max()) for x in dec) - min(float(x.low.min()) for x in dec)
    if abs(c - o) < flat_frac * rng:
        return 0
    return int(np.sign(c - o))


def day_context(hist: list[pd.DataFrame], day, p: "Params | None" = None) -> tuple[set, dict]:
    """Daily-candle context from the prior regular sessions (B11, B17, N8, M14, N7.4):
      big_prev     yesterday's range > 2x the average of the 5 days before it
      inside_day   yesterday inside the day before
      three_up/down  the last 3 closes each above / below the previous close -> day 4 not that way
      tgif_long/short  Friday after a week whose Mon-Thu range is >= 1.5x the average of the
                   prior weeks and whose Thursday close is in the top / bottom quarter of it:
                   only the retrace (short / long) is allowed
      year_end     (owner #3, p.year_end != "off") the last trading day(s) of the year: tags
                   year_end / year_end_inside (Ep01.8 low-vol inside day, report only) and the
                   side from December's direction (year_end_long / year_end_short)"""
    tags, block = set(), {}
    if p is not None and p.year_end != "off" and day in _calendar.last_n_trading_days(day.year, p.year_end_days):
        tags |= {"year_end", "year_end_inside"}
        if p.year_end == "long":
            side = 1
        else:
            dd = december_dir(hist, day, p.year_end_flat_frac)
            side = dd if p.year_end_map == "with" else -dd
        if side:
            tags.add("year_end_long" if side > 0 else "year_end_short")
            if p.year_end != "tag":
                block["year_end"] = (-side,)
    if len(hist) < 7:
        return tags, block
    rng = [float(x.high.max() - x.low.min()) for x in hist]
    cl = [float(x.close.iloc[-1]) for x in hist]
    if rng[-1] > 2 * np.mean(rng[-6:-1]):
        tags.add("big_prev")
    if hist[-1].high.max() < hist[-2].high.max() and hist[-1].low.min() > hist[-2].low.min():
        tags.add("inside_day")
    d = np.sign(np.diff(cl[-4:]))
    if len(d) == 3 and abs(d.sum()) == 3:
        tags.add("three_up" if d[0] > 0 else "three_down")
        block["three"] = (int(d[0]),)
    if day.weekday() == 4:
        mon = day - timedelta(days=4)
        wk = [x for x in hist if x.index[0].date() >= mon]
        prior = {}
        for x in hist:
            k = x.index[0].date().isocalendar()[:2]
            if x.index[0].date() < mon:
                prior.setdefault(k, []).append(x)
        if wk and len(prior) >= 2:
            hi, lo = max(float(x.high.max()) for x in wk), min(float(x.low.min()) for x in wk)
            avg = np.mean([max(float(x.high.max()) for x in v) - min(float(x.low.min()) for x in v)
                           for v in prior.values()])
            c = float(wk[-1].close.iloc[-1])
            if hi - lo >= 1.5 * avg:
                if c >= hi - 0.25 * (hi - lo):
                    tags.add("tgif_short"); block["tgif"] = (1,)
                elif c <= lo + 0.25 * (hi - lo):
                    tags.add("tgif_long"); block["tgif"] = (-1,)
    return tags, block


# --- owner #10: sloppy days [our interpretation throughout] -----------------------------
# Ep08 (010) 01:16:37-01:17:23 "sloppy consolidations ... seasoned students turn the charts off
# and walk away"; Ep03 (003) 00:58:43 "sloppy day ... I don't like to engage them"; Ep03
# 00:18:23-00:18:49 FOMC + NFP week tends to sloppy delivery. ICT never defines "sloppy"; the
# day-level reasons and the intraday chop test below are our reading.

def sloppy_day(hist: list[pd.DataFrame], day, p: "Params") -> set:
    """Day-level sloppy reasons known before the session: "big_prev" (yesterday's range >
    sloppy_big_mult x ADR5 of the 5 days before it), "nfp_week" / "nfp_week:PM" (the beginner
    NFP-week blocks via blocked() with nfp_week_block forced on; nfp_thu is kept - OWNER
    DECISION whether stand-aside also drops Thursday)."""
    out = set()
    if "big_prev" in p.sloppy_tests and len(hist) >= 6:
        a = adr5(hist[-6:-1])
        if a and float(hist[-1].high.max() - hist[-1].low.min()) > p.sloppy_big_mult * a:
            out.add("big_prev")
    if "nfp_week" in p.sloppy_tests:
        q = replace(p, nfp_week_block=True)
        if blocked(day, "AM", q) == "nfp_week_thu_fri":
            out.add("nfp_week")
        if blocked(day, "PM", q) == "nfp_week_wed_pm":
            out.add("nfp_week:PM")
    if "premium_run" in p.sloppy_tests:
        raise NotImplementedError("sloppy test premium_run: planned (B17.4)")
    return out


class Chop:
    """Intraday chop (N8.1 / Ep08.2) [our interpretation]: from sloppy_chop_from (02:00), the
    range since the day's first bar is under sloppy_chop_frac x ADR5 and the closes have crossed
    the midnight open at least sloppy_chop_cross times -> chop ON (its hi/lo frozen). A close
    beyond hi/lo +- sloppy_release_frac x ADR5 releases it for the rest of the day. update(i)
    runs at bar i's close; `state[i]` is the flag after bar i (gates arming at i, fills from i+1)."""

    def __init__(self, ctx, hist, p):
        self.ctx, self.p = ctx, p
        self.ref = ctx.opens.get("midnight")
        self.adr = adr5(hist[-5:])
        self.inert = self.ref is None or self.adr is None or "chop" not in p.sloppy_tests
        self.on = self.released = False
        self.lo = self.hi = None
        self.state = np.zeros(len(ctx.t), bool)
        self._hi, self._lo, self._sign, self._cross = -np.inf, np.inf, 0, 0
        self.on_at = None

    def update(self, i: int) -> bool:
        if self.inert:
            return False
        ctx, p = self.ctx, self.p
        self._hi, self._lo = max(self._hi, ctx.h[i]), min(self._lo, ctx.l[i])
        s = int(np.sign(ctx.c[i] - self.ref))
        if s and self._sign and s != self._sign:
            self._cross += 1
        if s:
            self._sign = s
        if self.on:
            r = p.sloppy_release_frac * self.adr
            if ctx.c[i] > self.hi + r or ctx.c[i] < self.lo - r:
                self.on, self.released = False, True
        elif (not self.released and ctx.t[i] >= p.sloppy_chop_from
              and self._hi - self._lo < p.sloppy_chop_frac * self.adr
              and self._cross >= p.sloppy_chop_cross):
            self.on, self.hi, self.lo, self.on_at = True, self._hi, self._lo, i
        self.state[i] = self.on
        return self.on

    def active_before(self, i: int) -> bool:
        """Chop flag known before bar i (after bar i-1's close)."""
        return bool(not self.inert and i - 1 >= self.ctx.start and self.state[i - 1])


def _judas(ctx, sd, sw, session) -> bool:
    """Power of three: the sweep was the session's opening move against the trade - its
    extreme came within the first hour of the session and beyond the session's reference open
    (midnight for the AM, 13:30 for the PM)."""
    t0 = 570 if session == "AM" else 810
    ref = ctx.opens.get("midnight" if session == "AM" else "1330")
    if ref is None:
        return False
    return bool(t0 <= ctx.t[sw["ext_i"]] < t0 + 60 and sw["ext"] < sd.x(ref))


def _split(p, ctx, hist, day, i, t) -> tuple:
    """Scale-out split for a new trade (036): 80/20 on slow days or with news ahead, else
    50/25/25. News ahead = a scheduled release later today after the fill (10:00 data, 14:00
    FOMC) or a CPI / NFP / FOMC day on the next trading day (holidays skipped: N3.4 fix). Slow
    day [our interpretation]: the range from midnight to the fill is under slow_frac x the
    5-day average regular-session range (adr5)."""
    if not p.ladder_by_day:
        return p.ladder_fracs
    tags = events(day)
    ahead = (bool(tags & NEWS_1000) and t < 600) or ("fomc" in tags and t < 840)
    nxt = next_trading_day(day)
    if events(nxt) & {"cpi", "jobs", "fomc"}:
        ahead = True
    slow = False
    adr = adr5(hist[-5:])
    if adr is not None:
        rng = ctx.h[ctx.start:i + 1].max() - ctx.l[ctx.start:i + 1].min()
        slow = rng < p.slow_frac * adr
    return p.ladder_fracs_slow if (ahead or slow) else p.ladder_fracs


def _swing_ref(sd, ext_i: int, fill_i: int) -> dict:
    """Ep 07 trail inputs at the fill: the body top of the swing high made between the sweep
    low and the fill (the high the retracement came from), and the retracement's low."""
    if fill_i <= ext_i + 1:
        return dict(swing_body=np.inf, retr_low=-np.inf)
    k = ext_i + int(np.argmax(sd.h[ext_i:fill_i]))
    return dict(swing_body=float(max(sd.o[k], sd.c[k])), retr_low=float(sd.l[k:fill_i + 1].min()))


def l_min_after(sd, q, i):
    return sd.l[q.i + 1:i].min(initial=np.inf)


def _in_sb(t: int, p: Params) -> bool:
    return any(a <= t < b for a, b in p.sb_windows)


# --- owner #4: news dealing range -----------------------------------------------------------

def _news_ranges(ctx, day, p) -> dict:
    """{R: dict(R, hi, lo, eq, made)} for each scheduled release R today (release_times).
    made = the bar index at whose close the post-release dealing range is complete
    [our interpretation]: the later of the first swing high and the first swing low confirmed
    after the release (3-candle pivots, Pivot.known), and on jobs days the 30-minute floor
    (Ep04 ~8:23 "after that first 30 minutes or so"). hi/lo = the extremes from the release bar
    to `made`. None when no range forms by R + news_range_max_min. Later breaks do not reset
    it. Under news_wait="fixed", made = the first bar at R + news_wait_min (065B). Every reader
    checks i >= made, so nothing here is used before it is known."""
    out = {}
    if p.news_wait == "off":
        return out
    t, n = ctx.t, (p.news_range_pivot or p.pivot_n)
    jobs = "jobs" in events(day)
    piv = None
    for R in release_times(day):
        kR = _idx_at(ctx, R)
        d = dict(R=R, hi=None, lo=None, eq=None, made=None)
        out[R] = d
        if kR >= len(t):
            continue                                   # not reached yet (live) - not formed
        if t[kR] >= R + max(ctx.tf, 1) and t[kR] - R >= 30:
            # no bars around the release (RTH-only history): nothing to wait for
            d.update(made=kR, hi=float(ctx.h[kR]), lo=float(ctx.l[kR]), eq=float((ctx.h[kR] + ctx.l[kR]) / 2))
            continue
        if p.news_wait == "fixed":
            made = _idx_at(ctx, R + p.news_wait_min)
        else:
            if piv is None:
                piv = L.pivots(ctx.h, ctx.l, n)
            sh = next((q for q in piv[0] if q.i >= kR), None)
            sl = next((q for q in piv[1] if q.i >= kR), None)
            if sh is None or sl is None:
                continue
            floor = _idx_at(ctx, R + p.nfp_floor_min) if (jobs and R == 510) else kR
            made = max(sh.known, sl.known, floor)
        if made >= len(t) or t[made] + ctx.tf > R + p.news_range_max_min:
            continue
        hi, lo = float(ctx.h[kR:made + 1].max()), float(ctx.l[kR:made + 1].min())
        d.update(made=int(made), hi=hi, lo=lo, eq=(hi + lo) / 2)
    return out


def _setup_news(ctx, day, p):
    ctx.news_dr = _news_ranges(ctx, day, p)
    if p.news_wait == "off":
        tt = ctx.t[ctx.start:]
        nr = (tt >= 510) & (tt < 540)                  # the old fixed 08:30-09:00 news range
        k = np.flatnonzero(nr) + ctx.start
        ctx.news_hl = (float(ctx.h[k].max()), float(ctx.l[k].min())) if len(k) else None
        ctx.news_made = _idx_at(ctx, 540)
    else:
        d = ctx.news_dr.get(510)
        ctx.news_hl = (d["hi"], d["lo"]) if d and d["made"] is not None else None
        ctx.news_made = d["made"] if d and d["made"] is not None else len(ctx.t)


def _news_gate(ctx, p, a: int, b: int):
    """The release driving session window [a, b): the latest R with a-60 <= R < b, or None."""
    if p.news_wait == "off":
        return None
    rs = [R for R in getattr(ctx, "news_dr", {}) if a - 60 <= R < b]
    return ctx.news_dr[max(rs)] if rs else None


# --- owner #9: lock one draw per session --------------------------------------------------

POOL_NAMES = ("PDH", "PDL", "PWH", "PWL", "D_swing_high", "D_swing_low")


def _lock_times(p, day, pre_windows) -> dict:
    """[our interpretation] lock = the session's start: AM 09:30 (the 09:45 / 10:00 release on
    those days), PM 13:30, PRE7 07:00, PRE9 / NEWS 09:00. SB / last-hour / pm_sb windows inherit
    their parent's lock."""
    a = p.am[0] or 570
    rs = [R for R in release_times(day) if a <= R < (p.am[1] or 660)]
    out = {"AM": max([a] + rs), "PM": p.pm[0] or 810}
    for name, a_, _ in pre_windows:
        out[name] = 420 if name == "PRE7" else 540
    return out


def mark_levels(ctx, row: dict | None, t_lock: int, session: str, p, spent=()) -> dict:
    """Mark up the levels before the session opens and lock ONE draw (owner #9). Uses only bars
    that closed by t_lock (bar start + tf <= t_lock). Candidates, each with its kind (pool /
    array): the HTF draws from the htf table cut at t_lock (draw_up / draw_dn), PDH/PDL 1-3, the
    overnight high/low known by t_lock, previous week / month (if on), NWOG/NDOG edges and CE,
    opening range gaps (today's only once 09:30 has printed), PM: the AM and lunch highs/lows,
    and the nearest untaken round handles (#13). Levels traded through today before t_lock
    (L14d) and levels delivered earlier today (`spent`, L14e) are dropped. "nearest": the nearer
    remaining level sets the side; no candidate on a side loses; none / a tie = neutral."""
    t = ctx.t
    kl = ctx.start + int(np.searchsorted(t[ctx.start:] + ctx.tf, t_lock, side="right"))
    px = float(ctx.c[kl - 1])
    cands = []
    if row:
        for key in ("draw_up", "draw_dn"):
            v = row.get(key)
            if v is not None and v == v:
                nm = str(row.get(key + "_name", ""))
                cands.append((float(v), "pool" if nm in POOL_NAMES else "array", "htf_" + nm))
    for k, v in ctx.pd.items():
        if k.startswith(("pdh", "pdl")):
            cands.append((v, "pool", k))
    if t_lock >= 570:
        for k in ("pmh", "pml"):
            if k in ctx.pd:
                cands.append((ctx.pd[k], "pool", k))
    else:
        m = max((m for m in ctx.pre_at if m <= t_lock), default=None)
        if m is not None:
            cands += [(ctx.pre_at[m][0], "pool", "overnight_high"), (ctx.pre_at[m][1], "pool", "overnight_low")]
    for on, hl, nm in ((p.pool_prev_week, ctx.pw, "pw"), (p.pool_prev_month, ctx.pm_, "pm")):
        if on and hl is not None:
            cands += [(hl[0], "pool", nm + "h"), (hl[1], "pool", nm + "l")]
    if getattr(ctx, "gaps", None) is not None:
        for kind, hi, lo, ce in ctx.gaps:
            cands += [(hi, "array", kind + "_high"), (ce, "array", kind + "_ce"), (lo, "array", kind + "_low")]
    else:
        for a, b in ctx.nwog:
            cands += [(a, "array", "nwog"), (b, "array", "nwog")]
    if p.org_days:
        orgs = ctx.org[:-1] if (ctx.org_today and t_lock <= 570) else ctx.org
        for a, b in orgs[-p.org_days:]:
            cands += [(a, "array", "org"), ((a + b) / 2, "array", "org_ce"), (b, "array", "org")]
    if session == "PM" and t_lock >= 810:
        if ctx.am_hl:
            cands += [(ctx.am_hl[0], "pool", "am_high"), (ctx.am_hl[1], "pool", "am_low")]
        if "lunch" in ctx.sess:
            cands += [(ctx.sess["lunch"][0], "pool", "lunch_high"), (ctx.sess["lunch"][1], "pool", "lunch_low")]
    st = getattr(ctx, "round_step", 0.0)
    if st and getattr(ctx, "adj", None) is not None and kl - 1 >= 0:
        adj = float(ctx.adj[kl - 1])
        raw = px - adj
        cands += [(float(np.ceil(raw / st) * st + adj), "pool", "round"),
                  (float(np.floor(raw / st) * st + adj), "pool", "round")]
    hi_t = ctx.h[ctx.start:kl].max() if kl > ctx.start else -np.inf
    lo_t = ctx.l[ctx.start:kl].min() if kl > ctx.start else np.inf
    near = lambda v: any(abs(v - s) <= p.es_pt for s in spent)
    if p.draw_lock_near_cap and p.htf_resist_cap and getattr(ctx, "conf", None) is not None:
        # switch: candidates beyond the nearest opposing HTF FVG wholly beyond the lock price
        # (as known at the lock) are not draws
        now = pd.Timestamp(ctx.day, tz=ctx.idx.tz) + pd.Timedelta(minutes=t_lock)
        src = tuple(CF_SRC[x] for x in p.htf_resist_src)
        for sgn in (1, -1):
            r = ctx.conf.resistance(now, px, sgn, p.htf_resist_tfs, src, straddle=False)
            if r is not None:          # [our interpretation] arrays wholly beyond the lock price
                cands = [x for x in cands if (x[0] <= r[0] if sgn > 0 else x[0] >= r[0])
                         or (x[0] < px if sgn > 0 else x[0] > px)]
    mn = p.draw_lock_min_pts * p.es_pt
    up = sorted({(v - px, v, k, n) for v, k, n in cands if v - px >= mn and v > px and v >= hi_t and not near(v)})
    dn = sorted({(px - v, v, k, n) for v, k, n in cands if px - v >= mn and v < px and v <= lo_t and not near(v)})
    side = 0
    if up and (not dn or up[0][0] < dn[0][0]):
        side = 1
    elif dn and (not up or dn[0][0] < up[0][0]):
        side = -1
    pick = up if side > 0 else dn
    lock = dict(day=ctx.day, session=session, side=side, t_lock=t_lock, px=px,
                target=pick[0][1] if side else None, kind=pick[0][2] if side else "",
                name=pick[0][3] if side else "", marked=[(v, k, n) for _, v, k, n in pick],
                delivered=False, delivered_t=None, delivered_i=None, traded=False)
    return lock


# --- owner #11: Ep 07 order block at the sweep low ----------------------------------------

def _ob_at_low(sd, sw, i):
    """The bullish OB at the sweep low, from closed bars only: down-close candles in
    [ext_i-3, min(i-1, ext_i+2)]; the one nearest the extreme (ties -> the later bar, as
    ep07_stop), extended back over consecutive down-close candles. Body top = the series'
    highest open, body low = its lowest close, mt = their midpoint."""
    e = sw["ext_i"]
    cand = [k for k in range(max(0, e - 3), min(i - 1, e + 2) + 1) if sd.c[k] < sd.o[k]]
    if not cand:
        return None
    k = min(cand, key=lambda k: (abs(k - e), -k))
    j = k
    while j - 1 >= 0 and sd.c[j - 1] < sd.o[j - 1]:
        j -= 1
    top, low = float(sd.o[j:k + 1].max()), float(sd.c[j:k + 1].min())
    return dict(k=k, j=j, body_top=top, body_low=low, mt=(top + low) / 2,
                hi=float(sd.h[j:k + 1].max()), lo=float(sd.l[j:k + 1].min()))


def _make_trade(ctx, day, symbol, o, sd, ts, fill, i, t, p, btag):
    tr = Trade(day, symbol, o["session"], o["setup"], "long" if sd.sign > 0 else "short",
               o["swept"], o["unicorn"], o["smt"], ctx.idx[o["i"]], ts, sd.x(fill),
               sd.x(o["stop"]), sd.x(o["t1"]), None if o["t2"] is None else sd.x(o["t2"]),
               o["shares"], day_type=day_type(day), htf=o["htf"], macro=o["macro"],
               news=news(day), wbias=ctx.wbias, sb=_in_sb(t, p), weekday=day.weekday(),
               conf_n=o["conf_n"], conf_top=o["conf_top"], conf_tfs=o["conf_tfs"],
               entry_kind=o["entry_kind"], mitigation=o["mitigation"],
               smt2=o["smt2"], smt_n=o["smt_n"], macro_win=o["macro_win"],
               td_agree=o["td_agree"], day_tags=ctx.day_tags, judas=o["judas"],
               dxy=int(ctx.intermarket.get("dxy", 0)), tnx=int(ctx.intermarket.get("tnx", 0)),
               propulsion=o["propulsion"], lh_sweet=o.get("lh_sweet", False),
               unicorn_side=o.get("unicorn_side", ""), bz_top=o.get("bz_top"),
               bz_bottom=o.get("bz_bottom"),
               bz_mt=None if o.get("bz_mt") is None else sd.x(o["bz_mt"]),
               resist_tf=o.get("resist_tf", ""), resist_lo=o.get("resist_lo"),
               resist_hi=o.get("resist_hi"), capped=o.get("capped", False),
               draw_side=o.get("draw_side", 0), draw_px=o.get("draw_px"),
               draw_name=o.get("draw_name", ""), draw_kind=o.get("draw_kind", ""),
               sloppy=o.get("sloppy", ""), news_wait_min_actual=o.get("news_wait_min_actual"),
               news_pd=o.get("news_pd"), **btag)
    eq = ctx.equity
    tr.entry_risk_pct = round(o["shares"] * (fill - o["stop"]) / eq, 5) if eq else None
    tr.peak_risk_pct = tr.entry_risk_pct
    _stamp_frame(ctx, tr, i)
    return tr


def _stamp_frame(ctx, tr, i):
    """#13: real-price frame of the fill bar (adj) and its contract."""
    if getattr(ctx, "adj", None) is not None and getattr(ctx, "real_px", False):
        tr.adj = float(ctx.adj[i])
    if getattr(ctx, "contract", None) is not None:
        v = ctx.contract[i]
        tr.contract = None if v != v else int(v)
    tr.roll_day = bool(getattr(ctx, "roll_day", False))


def run_day(df: pd.DataFrame, hist: list[pd.DataFrame], symbol: str, p: Params, tf: int,
            partner: tuple[pd.DataFrame, list[pd.DataFrame]] | None = None,
            log: list | None = None, live: bool = False, bias: dict | None = None,
            conf=None, gaps: list | None = None, closes: dict | None = None,
            evening: pd.DataFrame | None = None,
            partner2: tuple[pd.DataFrame, list[pd.DataFrame]] | None = None,
            intermarket: dict | None = None, equity: float | None = None,
            bias_by_cut: dict | None = None, meta: pd.DataFrame | None = None,
            locks: list | None = None, skips: list | None = None) -> list[Trade]:
    """Trades for one day. With `live`, a position still open at the last bar is returned
    with no exit (exit_reason "open") instead of being closed at the last price.
    equity     (#12) start-of-day equity for risk_basis="equity"
    bias_by_cut  (#9) {lock minute: htf table row cut at that minute} for the draw lock
    meta       (#13) databento meta (adj, instrument_id, roll) covering the day
    locks / skips  optional lists that receive the session locks and the sloppy-day skips"""
    day = df.index[0].date()
    flat = _eff_flat(p)
    ctx = DayCtx(df, day, hist, tf, p.htf, closes, p.or_minutes, evening if p.globex_pool else None)
    ctx.conf = conf
    ctx.gaps = gaps if (p.gap_mode == "ict" and gaps is not None) else None
    ctx.equity = float(equity) if (equity is not None and p.risk_basis == "equity") else p.account_equity
    ctx.symbol = symbol
    _attach_meta(ctx, meta, p, symbol)
    _setup_news(ctx, day, p)
    pctx = DayCtx(partner[0], day, partner[1], tf) if partner is not None else None
    if pctx is not None:
        _setup_news(pctx, day, p)
    mg = p.min_fvg_pts * p.es_pt
    sides = [Side(1, ctx.o, ctx.h, ctx.l, ctx.c, p.pivot_n, mg), Side(-1, ctx.o, ctx.h, ctx.l, ctx.c, p.pivot_n, mg)]
    psides = ppos = None
    if pctx is not None:
        psides = {1: Side(1, pctx.o, pctx.h, pctx.l, pctx.c, p.pivot_n, mg),
                  -1: Side(-1, pctx.o, pctx.h, pctx.l, pctx.c, p.pivot_n, mg)}
        ppos = pd.Series(np.arange(len(pctx.idx)), index=pctx.idx)
    ctx.partner2 = None
    if partner2 is not None:
        c2 = DayCtx(partner2[0], day, partner2[1], tf)
        _setup_news(c2, day, p)
        ctx.partner2 = (c2, {1: Side(1, c2.o, c2.h, c2.l, c2.c, p.pivot_n, mg),
                             -1: Side(-1, c2.o, c2.h, c2.l, c2.c, p.pivot_n, mg)},
                        pd.Series(np.arange(len(c2.idx)), index=c2.idx))
    tags = events(day)
    am_start = 600 if tags & NEWS_1000 else p.am[0]          # news_wait="off" only
    dt, block_side = day_context(hist, day, p)
    ctx.block_side = block_side
    if p.neutral_skip and "big_prev" in dt:
        if skips is not None:
            skips.append((day, symbol, "sloppy", "big_prev"))
        return []
    # owner #10: sloppy days ("off" = tag only; neutral_skip above is the old alias)
    sl_day = sloppy_day(hist, day, p) if p.sloppy_tests else set()
    sl_all_day = {r for r in sl_day if not r.endswith(":PM")}
    if p.sloppy_mode == "stand_aside" and sl_all_day:
        if skips is not None:
            skips.append((day, symbol, "sloppy", "|".join(sorted(sl_all_day))))
        return []
    ctx.sl_day = sl_day
    ctx.bias_by_cut = bias_by_cut or {}
    chop = Chop(ctx, hist, p)
    ctx.chop = chop
    ctx.day_tags = "|".join(sorted(dt))
    ctx.intermarket = intermarket or {}
    trades: list[Trade] = []
    done = {"AM": False, "PM": False, "PRE7": False, "PRE9": False, "NEWS": False}
    pre_windows = []
    if p.pre_0700:
        pre_windows.append(("PRE7", 420, 510))
    if p.post_news and news(day) == "0830":
        pre_windows.append(("NEWS", 540, 570))
    if p.pre_0900:
        pre_windows.append(("PRE9", 540, 570))
    state = {"reentered": {}, "day_pts": 0.0}
    pending = None    # dict with order details
    pos = None        # open Trade + live stop / remaining shares
    lost_side = None
    btag = {f"b_{k}": (None if bias is None else int(bias[k])) for k in ("react", "draw", "pd")}
    want = None
    if p.htf_bias != "off":
        want = 0 if bias is None else int(bias[p.htf_bias])
        if want == 0 and p.bias_neutral == "skip":
            return []
    lock_t = _lock_times(p, day, pre_windows) if p.draw_lock == "session" else {}
    ctx.lock, all_locks, spent = {}, [], []
    for i in range(ctx.start, len(ctx.t)):
        t = ctx.t[i]
        ts = ctx.idx[i]
        chop_before = chop.active_before(i) and p.sloppy_mode == "stand_aside"
        # --- 1. manage the open position on this bar
        if pos is not None:
            tr, sd = pos["trade"], pos["side"]
            o, h, l, c = sd.o[i], sd.h[i], sd.l[i], sd.c[i]
            a = pos["add"]
            if a is not None:                         # pending pyramid add
                if pos["t1_done"] or i - a["i"] > max(1, p.pending_minutes // tf) or chop_before:
                    pos["add"] = None
                elif l < a["px"]:
                    px = min(a["px"], o)
                    tr.adds.append((ts, sd.x(px), a["q"]))
                    pos["left"] += a["q"]; pos["basis"] += px * a["q"]; pos["n"] += a["q"]
                    pos["add"] = None
            stop = pos["stop"]
            if p.ambiguous == "target" and o > stop and not pos["t1_done"] and h >= pos["t1"]:
                stop = -np.inf                        # optimistic bound: target before stop
            if o <= stop:
                tr.exits.append((ts, sd.x(o), pos["left"], "stop_gap")); pos["left"] = 0
            elif l <= stop:
                tr.exits.append((ts, sd.x(stop), pos["left"], "be" if pos["t1_done"] else "stop")); pos["left"] = 0
            elif p.mgmt == "ladder":
                fr = pos["fracs"]
                lv_ = pos["levels"][:len(fr)]
                if pos.get("final_T") and len(pos["levels"]) > len(fr):   # #9: the last rung is the draw
                    lv_ = pos["levels"][:len(fr) - 1] + [pos["levels"][-1]]
                while pos["k"] < len(lv_) and pos["left"] and h >= lv_[pos["k"]]:
                    k = pos["k"]
                    last = k == len(lv_) - 1
                    q = pos["left"] if last else min(pos["left"], max(p.lot, _lots(pos["n"] * fr[k], p.lot)))
                    tr.exits.append((ts, sd.x(lv_[k]), q, f"t{k + 1}")); pos["left"] -= q
                    pos["k"] += 1
                    pos["last_partial_i"] = i
                    if not pos["t1_done"]:
                        pos["t1_done"] = True
                        if p.be_on == "t1":
                            pos["stop"] = max(pos["stop"], pos["basis"] / pos["n"])
                    if p.ladder_trail == "prior" and k >= 1:
                        pos["stop"] = max(pos["stop"], lv_[k - 1] - p.stop_buffer)
                    pos["away"] = lv_[k]
                if (pos["t1_done"] and not pos.get("be_done") and p.be_on == "expansion"
                        and pos["last_partial_i"] < i and c > lv_[0]):
                    pos["stop"] = max(pos["stop"], pos["basis"] / pos["n"])   # breakeven after expansion
                    pos["be_done"] = True
            else:
                if not pos["t1_done"] and h >= pos["t1"]:
                    q = pos["left"] if pos["t2"] is None else max(p.lot, _lots(pos["left"] * p.partial, p.lot))
                    q = min(q, pos["left"])
                    tr.exits.append((ts, sd.x(pos["t1"]), q, "t1")); pos["left"] -= q
                    pos["t1_done"] = True
                    pos["stop"] = max(pos["stop"], pos["basis"] / pos["n"])
                if pos["left"] and pos["t2"] is not None and pos["t1_done"] and h >= pos["t2"]:
                    tr.exits.append((ts, sd.x(pos["t2"]), pos["left"], "t2")); pos["left"] = 0
            if (pos["left"] and p.mgmt == "ladder" and p.ladder_trail == "hit" and pos.get("away") is not None
                    and c >= pos["away"] + p.away_pts * p.es_pt):
                pos["stop"] = max(pos["stop"], pos["away"] - p.stop_buffer)   # price left the array
                pos["away"] = None
            if pos["left"] and p.ep07_body_exit and l < pos["body_low"]:
                px = min(o, pos["body_low"])           # traded below the swing low's lowest body
                tr.exits.append((ts, sd.x(px), pos["left"], "body_low")); pos["left"] = 0
            if pos["left"] and p.ep07_trail and not pos.get("trailed") and h > pos["swing_body"]:
                pos["stop"] = max(pos["stop"], pos["retr_low"] - p.stop_buffer)
                pos["trailed"] = True
            if pos["left"] and p.ce_hold and i > pos["fill_i"] and c < pos["fvg_ce"] and not pos["t1_done"]:
                tr.exits.append((ts, sd.x(c), pos["left"], "ce_close")); pos["left"] = 0
            if (pos["left"] and pos.get("bz_mt") is not None and i > pos["fill_i"]
                    and (not pos["t1_done"] or p.breaker_mt_exit_after_t1) and c < pos["bz_mt"]):
                tr.exits.append((ts, sd.x(c), pos["left"], "breaker_mt")); pos["left"] = 0   # #6 (d)
            if pos["left"] and p.fvg_abort:
                if pos["abort"] is not None and l < pos["abort"]:
                    tr.exits.append((ts, sd.x(min(o, pos["abort"])), pos["left"], "abort")); pos["left"] = 0
                elif max(o, c) < pos["fvg_bottom"] and i > pos["fill_i"]:
                    pos["abort"] = l                  # body closed below the gap: arm the abort
            if pos["left"] and p.pd3_exit:
                for g in sd.gaps:
                    if g.i < i and g.i >= pos["ext_i"] and g.i not in pos["broken"] and c < g.bottom:
                        pos["broken"].add(g.i)
                if len(pos["broken"]) >= 3:
                    tr.exits.append((ts, sd.x(c), pos["left"], "pd3")); pos["left"] = 0
            if (pos["left"] and pos["t1_done"] and pos.get("heavy_dead") is not None
                    and (ts + pd.Timedelta(minutes=tf)).value >= pos["heavy_dead"]):
                tr.exits.append((ts, sd.x(c), pos["left"], "htf_heavy")); pos["left"] = 0   # #7 Ep02 30m
            if pos["left"]:
                pos["best"] = max(pos["best"], h)
                if (p.time_stop_min and not pos["t1_done"] and (t + tf) - pos["fill_t"] >= p.time_stop_min
                        and pos["best"] - pos["basis"] / pos["n"] < p.time_stop_pts * p.es_pt):
                    tr.exits.append((ts, sd.x(c), pos["left"], "time")); pos["left"] = 0
            if (pos["left"] and tr.session == "PRE7" and p.pre_flat_0830 and news(day) == "0830"
                    and t + tf >= 510):
                tr.exits.append((ts, sd.x(c), pos["left"], "pre_0830")); pos["left"] = 0
            if pos["left"] and tr.session != "PM" and p.am_exit and t + tf >= p.am_exit:
                # Ep 03 / owner #8: CLOSE (not tighten) all remaining AM-family units at the close
                # of the bar ending 12:00; "tighten" is a test-only switch [our interpretation]
                if p.am_exit_mode == "close":
                    tr.exits.append((ts, sd.x(c), pos["left"], "am_exit")); pos["left"] = 0
                elif not pos.get("am_tightened"):
                    new = max(pos["stop"], pos["basis"] / pos["n"], l - p.stop_buffer)
                    pos["am_tightened"] = True
                    if new >= c:
                        tr.exits.append((ts, sd.x(c), pos["left"], "am_exit")); pos["left"] = 0
                    else:
                        pos["stop"] = new
            if pos["left"] and tr.session == "PM" and p.pm_done_by and pos["t1_done"] and t + tf >= p.pm_done_by:
                tr.exits.append((ts, sd.x(c), pos["left"], "pm_done")); pos["left"] = 0
            if pos["left"] and t + tf >= flat:
                tr.exits.append((ts, sd.x(c), pos["left"], "eod")); pos["left"] = 0
            if pos["left"]:                            # #12: open risk against the current stop
                eq = ctx.equity
                if eq:
                    r_now = max(0.0, (pos["basis"] / pos["n"] - pos["stop"]) * pos["left"]) / eq
                    tr.peak_risk_pct = round(max(tr.peak_risk_pct or 0.0, r_now), 5)
            if not pos["left"]:
                lost_side = _after_close(pos, trades, p, done, state) or lost_side
                pos = None
            else:                                      # new FVG after the fill: trail / add
                if p.htf_resist_live and ctx.conf is not None and p.htf_resist_cap:
                    _resist_live(ctx, sd, pos, i, p)
                new = [g for g in sd.gaps if g.i == i and g.i - 2 > pos["fill_i"]]
                can_add = (p.adds and not pos["t1_done"] and pos["add"] is None and not pos.get("no_adds")
                           and not (chop.on and p.sloppy_mode == "stand_aside"))
                if new:
                    g = new[-1]
                    if p.trail or (p.mgmt == "ladder" and p.ladder_trail == "fvg" and pos["t1_done"]
                                   and g.i - 2 > pos["last_partial_i"]):   # formed since the partial
                        pos["stop"] = max(pos["stop"], g.bottom - p.stop_buffer)
                    if can_add and len(tr.adds) < len(p.adds):
                        _arm_add(pos, tr, g.top, i, p, ctx.equity)
                        can_add = pos["add"] is None
                if can_add and p.ob_adds and pos.get("ob_pre") and len(tr.adds) < len(p.adds):
                    _ob_add(sd, pos, tr, i, p, ctx.equity)
        # --- 2. pending limit order
        if pending is not None and chop_before:
            pending = None                           # #10 stand aside: chop drops the order
        if pending is not None and pending["session"] != "PM" and p.am_exit and t + tf >= p.am_exit:
            pending = None                           # #8 guard: no AM-family fills into 12:00
        if pending is not None:
            sd = pending["side"]
            cut = {"AM": p.am[1], "PM": p.pm[1], "PRE7": 510, "PRE9": 570, "NEWS": 570}[pending["session"]]
            if pending.get("done_key", "").startswith("SB_"):
                cut = p.sb_windows[0][1] if pending["session"] == "AM" else p.sb_windows[1][1]
            if p.sb_only:                               # fills only inside the session's SB window
                sb_a, cut = p.sb_windows[0] if pending["session"] == "AM" else p.sb_windows[1]
            ob_pre = pending.get("ob_pre", False)
            if t >= cut or i - pending["i"] > max(1, p.pending_minutes // tf):
                pending = None
            elif ob_pre and i - 1 > pending["i"] and sd.c[i - 1] < pending["ob_body_low"]:
                pending = None                       # #11: a close below the OB bodies (bar i-1)
            elif sd.h[i] >= pending["t1"] and sd.l[i] >= pending["entry"]:
                pending = None                       # ran to target without us
            elif p.sb_only and t < sb_a:
                pass                                 # armed before the window: wait for it
            elif (not ob_pre and p.leg_pd and p.leg_pd_at == "fill" and pending["entry"] >
                  pending["ext"] + p.leg_pd * (sd.h[pending["ext_i"]:i].max() - pending["ext"])):
                pass                                 # not yet in the leg's discount: wait
            elif sd.l[i] < pending["entry"] and pos is None:
                o = pending
                fill = min(o["entry"], sd.o[i])      # a gap through the limit fills at the open
                tr = _make_trade(ctx, day, symbol, o, sd, ts, fill, i, t, p, btag)
                pos = dict(trade=tr, side=sd, stop=o["stop"], t1=o["t1"], t2=o["t2"],
                           left=o["shares"], n=o["shares"], basis=fill * o["shares"],
                           t1_done=False, fill_i=i, fill_t=t, add=None, fvg_bottom=o["fvg_bottom"],
                           abort=None, best=fill, ext_i=o["ext_i"], broken=set(), fvg_ce=o["fvg_ce"],
                           body_low=o["body_low"], levels=o["levels"], k=0, away=None, last_partial_i=i,
                           level_kinds=o.get("level_kinds"), final_T=o.get("final_T", False),
                           bz_mt=o.get("bz_mt"), ob_pre=ob_pre, no_adds=o.get("no_adds", False),
                           heavy_dead=o.get("heavy_dead"), ob_add_used=set(),
                           fracs=(1.0,) if o.get("scalp") else _split(p, ctx, hist, day, i, t),
                           **_swing_ref(sd, o["ext_i"], i))
                done[o.get("done_key", o["session"])] = True
                lk = ctx.lock.get(o["session"])
                if lk is not None:
                    lk["traded"] = True
                pending = None
                if sd.l[i] <= pos["stop"]:           # same-bar stop (conservative)
                    tr.exits.append((ts, sd.x(pos["stop"]), pos["left"], "stop")); pos["left"] = 0
                    lost_side = _after_close(pos, trades, p, done, state) or lost_side
                    pos = None
                elif (pos["bz_mt"] is not None and sd.c[i] < pos["bz_mt"]
                      and not sd.h[i] >= pos["t1"]):  # #6 (c): filled, then closed below the MT
                    tr.exits.append((ts, sd.x(sd.c[i]), pos["left"], "breaker_mt")); pos["left"] = 0
                    lost_side = _after_close(pos, trades, p, done, state) or lost_side
                    pos = None
            if (pending is not None and pending.get("bz_mt") is not None and pending["i"] < i
                    and sd.c[i] < pending["bz_mt"]):
                pending = None                       # #6 (c): bar i closed below the breaker MT
        # --- 3. setup detection on the closed bar
        if p.sloppy_tests:
            chop.update(i)
        if lock_t:
            pending = _lock_step(ctx, p, lock_t, i, t, bias_by_cut, done, spent, all_locks, pending)
        session = None
        for name, a_, b_ in pre_windows:
            if a_ <= t < b_ and not done.get(name):
                session, w0, wa, wb = name, a_, a_, b_
                break
        if session is None:
            if p.am[0] <= t < p.am[1]:
                session, w0, wa, wb = "AM", am_start, p.am[0], p.am[1]
            elif p.pm[0] <= t < p.pm[1]:
                session, w0, wa, wb = "PM", p.pm[0], p.pm[0], p.pm[1]
            else:
                continue
        drv = None
        if p.news_wait != "off":                     # owner #4: wait for the news dealing range
            w0 = wa
            drv = _news_gate(ctx, p, wa, wb)
            if drv is not None:
                if drv["made"] is None:
                    if t >= drv["R"] or drv["R"] in (585, 600):
                        continue
                else:
                    w0 = max(wa, int(ctx.t[drv["made"]]))
                    if i < drv["made"]:
                        continue
        ctx.cur_news = drv
        if (session == "PM" and p.last_hour_strict and t >= p.last_hour[0]
                and not (p.last_hour_sweet[0] <= t < p.last_hour_sweet[1])):
            continue                                  # #1 test: last hour = sweet spot only
        done_key = session
        if done[session] and p.sb_setup and _in_sb(t, p) and not state.get("day_done"):
            done_key = "SB_" + session                # the Silver Bullet window's own trade
            done.setdefault(done_key, False)
        if t < w0 or done[done_key] or pos is not None:
            continue
        if (p.day_filter and blocked(day, session, p, t)) or (p.skip_news and news(day) != "none"):
            continue
        sl_now = set(sl_day if session == "PM" else sl_all_day)
        if chop.on:
            sl_now.add("chop")
        if p.sloppy_mode == "stand_aside" and sl_now:
            continue                                  # #10: no new entries while sloppy
        ctx.cur_sloppy = "|".join(sorted(sl_now))
        lk = ctx.lock.get(session) if lock_t else None
        if lock_t and session in lock_t and lk is None:
            continue                                  # #9: not locked yet - nothing to trade toward
        if lk is not None and lk["delivered"]:
            continue
        for sd in sides:
            sname = "long" if sd.sign > 0 else "short"
            if not p.reverse_after_loss and lost_side is not None and sname != lost_side:
                continue                              # no reversals after a loss
            if p.weekly_bias and ctx.wbias == -sd.sign:
                continue
            if want and want != sd.sign:
                continue
            if p.three_day_rule and sd.sign in block_side.get("three", ()):
                continue
            if p.tgif and sd.sign in block_side.get("tgif", ()):
                continue
            if sd.sign in block_side.get("year_end", ()):
                continue                              # #3 (off by default)
            if lk is not None and lk["side"] and sd.sign != lk["side"]:
                continue                              # #9: trade only toward the locked draw
            ctx.cur_lock = lk if (lk is not None and lk["side"] == sd.sign) else None
            o_ = _scan(ctx, sd, i, p, session, w0, pctx, psides, ppos,
                       0.5 if state["reentered"].get(session) else 1.0)
            if o_ is not None:
                if done_key != session:
                    o_.update(done_key=done_key, setup="sb_" + session.lower())
                if (pending is not None and pending.get("ob_pre") and not o_.get("ob_pre")
                        and pending["side"] is sd and not p.ob_entry_cancel_on_mss
                        and pending["entry"] <= o_["entry"]):
                    continue                          # #11 "both": keep the lower entry (side space)
                pending = o_
                if log is not None:
                    log.append((ts, symbol, session, sname, o_["swept"], sd.x(o_["entry"]),
                                sd.x(o_["stop"]), sd.x(o_["t1"])))
    if p.ma_deuce:
        from .pre_open import run_ma_deuce
        trades += run_ma_deuce(ctx, hist, p, day, symbol, btag)
    if p.sb_model:
        from .sb_model import run_sb
        trades += run_sb(ctx, sides, p, day, symbol, blocked, btag)
    if pos is not None:   # data ended early
        tr = pos["trade"]
        if not live:
            tr.exits.append((ctx.idx[-1], pos["side"].x(pos["side"].c[-1]), pos["left"], "eod"))
        trades.append(tr)
    if locks is not None:
        locks += [dict(lk, symbol=symbol, marked=len(lk["marked"])) for lk in all_locks + list(ctx.lock.values())]
    return trades


def _arm_add(pos, tr, px, i, p, eq):
    """#12: an add at `px` (side space) sized by the adds fraction, shrunk so the open risk
    (against the current stop; never negative) stays within the total cap (1.3%)."""
    k = len(tr.adds)
    q = _lots(tr.shares * p.adds[k], p.lot)
    at_risk = max(0.0, pos["basis"] - pos["stop"] * pos["n"])
    d = px - pos["stop"]
    if d <= 0:
        return
    room = _total_cap(p, eq) - at_risk
    if d * q > room:
        q = _lots(max(room, 0.0) / d, p.lot)
    if q >= p.lot and q >= 1:
        pos["add"] = dict(px=px, q=q, i=i)


def _ob_add(sd, pos, tr, i, p, eq):
    """#11 OB re-entry add [our interpretation of Ep 07 "accumulate more"]: a fresh down-close
    series (after the fill) whose low holds above the stop, then a close above its body top ->
    an add at its body top."""
    k = i - 1
    if k <= pos["fill_i"] or not sd.c[k] < sd.o[k] or k in pos["ob_add_used"]:
        return
    j = k
    while j - 1 > pos["fill_i"] and sd.c[j - 1] < sd.o[j - 1]:
        j -= 1
    top = float(sd.o[j:k + 1].max())
    if sd.l[j:k + 1].min() >= pos["stop"] and sd.c[i] > top:
        pos["ob_add_used"].add(k)
        _arm_add(pos, tr, top, i, p, eq)


def _resist_live(ctx, sd, pos, i, p):
    """#7 htf_resist_live: recompute the cap at bar i's close and trim the remaining rungs
    (applies from bar i+1)."""
    now = ctx.idx[i] + pd.Timedelta(minutes=ctx.tf)
    src = tuple(CF_SRC[x] for x in p.htf_resist_src)
    r = ctx.conf.resistance(now, sd.x(sd.c[i]), sd.sign, p.htf_resist_tfs, src)
    if r is None:
        return
    capx = sd.x(r[0]) - p.htf_resist_buffer_pts * p.es_pt
    if capx <= sd.c[i]:
        return
    k = pos["k"]
    rest = [v for v in pos["levels"][k:] if v <= capx]
    if not any(abs(v - capx) <= p.es_pt for v in rest):
        rest.append(capx)
    pos["levels"] = pos["levels"][:k] + sorted(rest)
    if pos.get("level_kinds") is not None:
        pos["level_kinds"] = (pos["level_kinds"][:k] + ["array"] * len(rest))[:len(pos["levels"])]
    if pos["t2"] is not None and pos["t2"] > capx:
        pos["t2"] = capx
    if not pos["t1_done"] and pos["t1"] > capx:
        pos["t1"] = capx


def _lock_step(ctx, p, lock_t, i, t, bias_by_cut, done, spent, all_locks, pending):
    """#9 per bar: lock each session's draw at its lock time (bars closed by then only), then
    mark a lock delivered when this closed bar reached its target (before or after an entry):
    that session (and its SB window) is done for the day."""
    for s_, tl in lock_t.items():
        if s_ not in ctx.lock and t >= tl:
            row = (bias_by_cut or {}).get(tl)
            lk = mark_levels(ctx, row, tl, s_, p, spent)
            ctx.lock[s_] = lk
            if lk["side"] == 0 and p.draw_lock_neutral == "skip":
                done[s_] = True
    for s_, lk in list(ctx.lock.items()):
        if not lk["side"] or lk["delivered"]:
            continue
        hit = ctx.h[i] >= lk["target"] if lk["side"] > 0 else ctx.l[i] <= lk["target"]
        if hit:
            lk.update(delivered=True, delivered_t=ctx.idx[i], delivered_i=i)
            spent.append(lk["target"])
            _f("x_draw_delivered")
            if pending is not None and pending["session"] == s_:
                pending = None
            if p.draw_relock:                         # test: lock the next draw from here
                all_locks.append(lk)
                nl = mark_levels(ctx, None, int(t + ctx.tf), s_, p, spent)
                ctx.lock[s_] = nl
                if nl["side"] == 0 and p.draw_lock_neutral == "skip":
                    done[s_] = True
            else:
                done[s_] = True
                done["SB_" + s_] = True
    return pending


def _attach_meta(ctx, meta, p, symbol):
    """#13: per-bar adj / contract for the day frame, the roll-day tag and the round step."""
    ctx.adj = ctx.contract = None
    ctx.real_px = False
    ctx.round_step = 0.0
    ctx.roll_day = False
    if p.price_frame == "raw":
        ctx.adj = np.zeros(len(ctx.idx))
    elif meta is not None and len(meta):
        a0 = max(0, int(meta.index.searchsorted(ctx.idx[0])) - 1)
        a1 = int(meta.index.searchsorted(ctx.idx[-1], side="right"))
        m = meta.iloc[a0:a1].reindex(ctx.idx, method="ffill")
        if "adj" in m:
            ctx.adj = m["adj"].fillna(0.0).values.astype(float)
        if "instrument_id" in m:
            ctx.contract = m["instrument_id"].values.astype(float)
        a = pd.Timestamp(ctx.day, tz=ctx.idx.tz) - pd.Timedelta(hours=6)
        seg = meta.iloc[int(meta.index.searchsorted(a)):a1]
        if "roll" in seg and bool(seg["roll"].astype(bool).any()):
            ctx.roll_day = True
        if "instrument_id" in seg and seg["instrument_id"].nunique() > 1:
            ctx.roll_day = True
    ctx.real_px = ctx.adj is not None and p.price_frame == "front_month"
    if p.round_pools and ctx.adj is not None and p.price_frame != "back_adjusted":
        ctx.round_step = p.round_pool_step_pts or ROUND_STEP.get(symbol.upper(), 0.0)


def _sell_side(ctx: DayCtx, sd: Side, session: str, i: int | None = None,
               extra: bool = False, p: "Params | None" = None) -> dict[str, float]:
    keys = ("pdl1", "pdl2", "pdl3") if sd.sign > 0 else ("pdh1", "pdh2", "pdh3")
    out = {k: sd.x(ctx.pd[k]) for k in keys if k in ctx.pd}
    if session in ("PRE7", "PRE9", "NEWS"):
        m = 420 if session == "PRE7" else 540
        if m in ctx.pre_at:
            hi, lo = ctx.pre_at[m]
            out["overnight"] = sd.x(lo if sd.sign > 0 else hi)
        for name in ("london", "prev_pm"):
            if name in ctx.sess:
                hi, lo, _ = ctx.sess[name]
                out[name] = sd.x(lo if sd.sign > 0 else hi)
        if (session == "NEWS" and ctx.news_hl is not None
                and (i is None or getattr(ctx, "news_made", 0) <= i - 1 or p is None or p.news_wait == "off")):
            out["news_range"] = sd.x(ctx.news_hl[1] if sd.sign > 0 else ctx.news_hl[0])
        if i is not None:
            for k, v in enumerate(_round_levels(ctx, sd, i, False)):
                out["round"] = v
        return out
    if p is not None:
        for name, on, hl in (("pwl", p.pool_prev_week, ctx.pw), ("pml_month", p.pool_prev_month, ctx.pm_)):
            if on and hl is not None:
                out[name] = sd.x(hl[1] if sd.sign > 0 else hl[0])
        if p.pool_swings and i is not None:     # untaken short-term swing lows (side terms)
            for q in sd.pl:
                if q.known <= i - 1 and q.i >= ctx.start - 1 and l_min_after(sd, q, i) > q.price:
                    out[f"swing_low{q.i}"] = q.price
    if i is not None:                           # #4: news dealing ranges once complete
        for R, d in getattr(ctx, "news_dr", {}).items():
            if d["made"] is not None and d["made"] <= i - 1:
                out["news_range" if R == 510 else f"news_range_{R}"] = sd.x(d["lo"] if sd.sign > 0 else d["hi"])
        for v in _round_levels(ctx, sd, i, False):   # #13: the nearest untaken round handle
            out["round"] = v
    if session == "AM":
        k = "pml" if sd.sign > 0 else "pmh"
        if k in ctx.pd:
            out["premarket"] = sd.x(ctx.pd[k])
        if extra:
            for name in ("london", "prev_pm"):
                if name in ctx.sess:
                    hi, lo, _ = ctx.sess[name]
                    out[name] = sd.x(lo if sd.sign > 0 else hi)
        if ctx.or_hl is not None and i is not None and ctx.t[i] >= ctx.or_end:
            out["opening_range"] = sd.x(ctx.or_hl[1] if sd.sign > 0 else ctx.or_hl[0])
    elif ctx.am_hl:
        out["am_session"] = sd.x(ctx.am_hl[1] if sd.sign > 0 else ctx.am_hl[0])
        if extra and "lunch" in ctx.sess and i is not None and ctx.t[i] >= ctx.sess["lunch"][2]:
            hi, lo, _ = ctx.sess["lunch"]
            out["lunch"] = sd.x(lo if sd.sign > 0 else hi)
    return out


FUNNEL = None   # set to a collections.Counter to count how setups are found and rejected


def _f(key):
    if FUNNEL is not None:
        FUNNEL[key] += 1


def _scan(ctx, sd: Side, i, p: Params, session, w0, pctx, psides, ppos, risk_mult=1.0):
    """Advance this side's sweep -> (OB before the break | MSS -> FVG) machine at bar i;
    return an order or None."""
    l, h, c = sd.l, sd.h, sd.c
    tol = p.eq_tol_pts * p.es_pt
    lv = _sell_side(ctx, sd, session, i, p.extra_pools, p)
    created = ctx.start if session == "AM" else ctx.start + int(np.searchsorted(ctx.t[ctx.start:], 810))
    or_made = ctx.start + int(np.searchsorted(ctx.t[ctx.start:], ctx.or_end))
    lon_made = ctx.start + int(np.searchsorted(ctx.t[ctx.start:], 300))
    news_made = getattr(ctx, "news_made", ctx.start + int(np.searchsorted(ctx.t[ctx.start:], 540)))
    for k, eq in enumerate(_eq_levels(sd, i - 1, tol, lows=True)):
        lv[f"rel_eq_lows{k}"] = eq
    sw = sd.sweep
    if sw is not None and sw["session"] != session:
        sw = sd.sweep = None

    def intact(k, v):   # not traded through between the level's creation and bar i-1
        if k.startswith("swing_low"):          # M1.2 fix: from the bar after the swing low itself
            a = int(k[len("swing_low"):]) + 1
        elif k.startswith("news_range_"):
            a = ctx.news_dr[int(k[len("news_range_"):])]["made"]
        elif k == "news_range" and 510 in getattr(ctx, "news_dr", {}):
            a = ctx.news_dr[510]["made"]
        else:
            a = {"am_session": created, "lunch": created, "opening_range": or_made,
                 "london": lon_made, "news_range": news_made}.get(k, ctx.start)
        return k.startswith(("rel_eq", "round")) or i <= a or l[a:i].min() >= v
    hit = [(k, v) for k, v in lv.items() if l[i] < v and intact(k, v)]
    if sw is None and hit:
        k, v = min(hit, key=lambda kv: kv[1])
        sw = sd.sweep = dict(session=session, name=("rel_eq_lows" if sd.sign > 0 else "rel_eq_highs") if k.startswith("rel_eq") else k,
                             level=v, key=k, ext=l[i], ext_i=i, broke=None, sweep_i=i)
        sw["smt"] = _smt(ctx, sd, i, k, v, session, pctx, psides, ppos)
        sw["smt2"] = _smt(ctx, sd, i, k, v, session, *ctx.partner2) if getattr(ctx, "partner2", None) else None
        _f("1_sweep")
    if sw is None:
        return None
    if l[i] < sw["ext"]:
        sw.update(ext=l[i], ext_i=i, broke=None, ob=None, ob_sent=False, ob_frozen=False, ts_sent=False)
    # reference: the swing high that led into the sweep extreme
    refs = [q for q in sd.ph if q.i < sw["ext_i"] and q.known <= i]
    if refs:
        ref_i, ref = refs[-1].i, refs[-1].price
    else:
        a = max(ctx.start, sw["ext_i"] - 3 * p.pivot_n)
        if a >= sw["ext_i"]:
            return None
        ref_i = a + int(np.argmax(h[a:sw["ext_i"]])); ref = h[ref_i]
    if p.mss_cisd:                     # the open of the down-close series into the low
        blk = L.order_block_blend(sd.o, h, l, c, sw["ext_i"] - 5, sw["ext_i"], "bull")
        if blk is not None:
            ref = float(sd.o[blk.src])
    if sw["broke"] is None:
        order = None
        if p.ob_entry in ("pre_break", "both") and not sw.get("ob_sent"):
            order = _ob_pre(ctx, sd, sw, i, p, session, risk_mult)      # owner #11 (default)
        if order is None and p.turtle_soup and not sw.get("ts_sent"):
            order = _turtle(ctx, sd, sw, i, p, session, risk_mult)      # M12 core (off)
        brk = i > sw["ext_i"] and (h[i] if p.mss_mode == "wick" else c[i]) > ref
        if brk and p.displacement_mult:  # M1.2 option: the breaking candle must displace
            body = abs(c[i] - sd.o[i])
            prev = np.abs(c[max(0, i - 10):i] - sd.o[max(0, i - 10):i])
            brk = len(prev) == 0 or body >= p.displacement_mult * float(prev.mean())
        if brk:
            sw["broke"] = i
            _f("2_mss")
            if p.ob_entry == "pre_break":
                sd.sweep = None               # #11: no FVG entry after the break in this mode
                return order
            if order is not None:
                return order
        else:
            return order
    gaps = [g for g in sd.gaps if g.i <= i and g.i - 2 >= sw["ext_i"]]
    if p.entry_tf != "1m" and ctx.tf < p.setup_minutes:
        z5 = sd.zones_tf(ctx.idx, ctx.tf, p.setup_minutes)
        if p.entry_tf == "5m":       # the 5m gap / block the 1m shift points at (formed after
            gaps = [z for z in z5 if z.i <= i and z.mt != z.mt   # the sweep: FVGs ...
                    and z.src + p.setup_minutes // ctx.tf > sw["ext_i"]]
            if not gaps:             # ... else the 5m order block at the low
                gaps = [z for z in z5 if z.i <= i and z.mt == z.mt and z.bottom <= sw["ext"] + 1e-9
                        and z.top > sw["ext"] and z.i >= sw["ext_i"]]
        else:                        # nested: 1m FVG inside a live 5m FVG or 5m order block
            live5 = [z for z in z5 if z.i <= i and c[z.i + 1:i + 1].min(initial=np.inf) >= z.bottom]
            gaps = [g for g in gaps if any(g.overlaps(z) for z in live5)]
    if p.ifvg_entries:                 # bearish gaps inverted by the move up from the sweep
        gaps = sorted(gaps + [z for z in sd.ifvgs() if sw["ext_i"] < z.i <= i], key=lambda z: z.i)
    if not gaps:
        wait = p.fvg_wait * (p.setup_minutes // ctx.tf if p.entry_tf == "5m" and ctx.tf < p.setup_minutes else 1)
        if i - sw["broke"] >= wait:
            sd.sweep = None
            _f("x_no_fvg_after_mss")
        return None
    sd.sweep = None   # this sweep is consumed whether or not the order passes the filters
    _f("3_fvg")
    # breaker (A13, owner #14): the highest-close up-close candle between the swing low before
    # the reference high (L1) and the sweep extreme (L2) (029 ~24:13; 048), full range by default
    l1 = [q for q in sd.pl if q.i < ref_i and q.known <= i]
    a0 = l1[-1].i if l1 else max(0, ref_i - p.pivot_n)
    bz = L.breaker_zone(sd.o, h, l, c, a0, sw["ext_i"], i, "bull", p.breaker_zone, p.breaker_mt_mode)
    if bz is not None and p.breaker_mt_respect and (c[sw["broke"] + 1:i + 1] < bz.mt).any():
        bz = None                      # #6 (a): a body close below the breaker MT - breaker lost
        _f("x_breaker_mt_lost")
    # the entry FVG must still be open: no close below its bottom since it formed (021; 050)
    gaps = [g for g in gaps if c[g.i + 1:i + 1].min(initial=np.inf) >= g.bottom]
    if not gaps:
        _f("x_fvg_closed_through")
        return None
    fresh = [g for g in gaps if l[g.i + 1:i + 1].min(initial=np.inf) > g.top] or gaps
    uni_ok = p.unicorn_sides == "both" or p.unicorn_sides == ("long" if sd.sign > 0 else "short")
    uni = [g for g in fresh if bz is not None and g.overlaps(bz)] if uni_ok else []
    if uni and p.breaker_mt_entry_floor:       # #6 (b): a unicorn gap wholly below the MT is out
        below = [g for g in uni if g.top <= bz.mt]
        if below:
            _f("x_unicorn_below_mt")
            uni = [g for g in uni if g.top > bz.mt]
            fresh = [g for g in fresh if g not in below]
            if not uni and not fresh:
                return None
    pick = uni or fresh
    g = pick[-1] if p.fvg_pick == "last" else pick[0]
    entry = g.top if p.entry == "edge" else g.mid
    bz_mt = None
    if uni and g in uni:
        if p.breaker_mt_entry_floor:
            entry = min(max(entry, bz.mt + 0.25 * p.es_pt), g.top)
        if p.breaker_mt_respect:
            bz_mt = bz.mt
    is_ifvg = p.ifvg_entries and g not in sd.gaps
    mit = any(z.i <= i and g.overlaps(z) for z in sd.mitigations()) if p.tag_blocks else False
    prop = any(z.i <= i and z.bottom <= g.top and z.top >= sw["ext"] for z in sd.propulsions()) if p.tag_blocks else False
    # order block: the blended last down-close candle(s) before the structure break (A12)
    ob = L.order_block_blend(sd.o, h, l, c, sw["ext_i"] - 3, sw["broke"] - 1, "bull")
    stop = g.bottom - p.stop_buffer
    mt = None if ob is None else (ob.mt if p.mt_mode == "body" else ob.mid)
    if p.stop_mode == "ob_mt" and mt is not None and mt < entry - p.min_risk_pts * p.es_pt:
        stop = min(stop, mt - p.stop_buffer)
    if p.ep07_stop:                    # down-close candle nearest the sweep low, body midpoint
        e = sw["ext_i"]
        cand = [k for k in range(max(0, e - 3), min(i, e + 2) + 1) if c[k] < sd.o[k]]
        if cand:
            k = min(cand, key=lambda k: (abs(k - e), -k))
            stop = (sd.o[k] + c[k]) / 2 - p.stop_buffer
    tags = dict(unicorn=bool(uni), fvg_bottom=g.bottom, fvg_ce=g.mid,
                entry_kind="ifvg" if is_ifvg else "fvg", mitigation=bool(mit), propulsion=bool(prop),
                unicorn_side=("bull" if sd.sign > 0 else "bear") if uni else "",
                bz_top=None if bz is None else float(max(sd.x(bz.top), sd.x(bz.bottom))),
                bz_bottom=None if bz is None else float(min(sd.x(bz.top), sd.x(bz.bottom))),
                bz_mt=bz_mt)
    return _finish_order(ctx, sd, i, p, session, sw, entry, stop, risk_mult,
                         h[sw["ext_i"]:i + 1].max(), tags, pctx_free=True)


def _ob_pre(ctx, sd, sw, i, p, session, risk_mult):
    """#11 (Ep 07 ~2:10, ~11:06, ~13:35, ~15:03): before the structure break, a limit at the
    bodies of the bullish OB at the sweep low. Armed once ("ob_sent") whether or not the
    filters pass; the sweep is not consumed."""
    if not sw.get("ob_frozen"):
        sw["ob"] = _ob_at_low(sd, sw, i)
        if i - 1 >= sw["ext_i"] + 2:
            sw["ob_frozen"] = True               # the candidate window is complete
    ob = sw.get("ob")
    if ob is None or i <= ob["k"]:
        return None
    if p.ob_arm == "leave" and not sd.c[i] > ob["body_top"]:
        return None
    sw["ob_sent"] = sw["ob_frozen"] = True
    entry = {"body_top": ob["body_top"], "mt": ob["mt"], "range_top": ob["hi"]}[p.ob_entry_px]
    stop = ob["mt"] - p.stop_buffer if p.ob_stop == "mt" else sw["ext"] - p.stop_buffer
    if entry - stop < p.min_risk_pts * p.es_pt or entry <= stop:
        stop = sw["ext"] - p.stop_buffer        # [our interpretation] fallback to the sweep extreme
    tags = dict(unicorn=False, fvg_bottom=ob["body_low"], fvg_ce=ob["mt"], entry_kind="ob_pre",
                mitigation=False, propulsion=False, ob_pre=True, ob_body_low=ob["body_low"],
                ob_lo=ob["lo"])
    return _finish_order(ctx, sd, i, p, session, sw, entry, stop, risk_mult,
                         sd.h[sw["ext_i"]:i + 1].max(), tags, skip_leg_pd=True)


def _turtle(ctx, sd, sw, i, p, session, risk_mult):
    """M12 turtle soup, 2023 variant (shared core L.turtle_soup): the sweep took the level by at
    most ts_max_pts and a candle closed back above it within ts_back_bars - no MSS needed. Limit
    at the swept level (the old low), stop below the false-break extreme (022 ~2:47:29)."""
    if not L.turtle_soup(sd.l, sd.c, sw["level"], sw["ext_i"], i, p.ts_max_pts * p.es_pt, p.ts_back_bars):
        return None
    if p.ts_need_htf and not _htf_tag(ctx, sd, i, sw["ext"], p.eq_tol_pts * p.es_pt):
        return None
    sw["ts_sent"] = True
    entry, stop = sw["level"], sw["ext"] - p.stop_buffer
    tags = dict(unicorn=False, fvg_bottom=sw["ext"], fvg_ce=(entry + sw["ext"]) / 2,
                entry_kind="turtle_soup", mitigation=False, propulsion=False)
    return _finish_order(ctx, sd, i, p, session, sw, entry, stop, risk_mult,
                         sd.h[sw["ext_i"]:i + 1].max(), tags, skip_leg_pd=True)


CF_SRC = {"fvg": 0, "ob": 1, "gap": 2, "vi": 3, "breaker": 4}


def _finish_order(ctx, sd, i, p, session, sw, entry, stop, risk_mult, leg_hi, tags,
                  skip_leg_pd=False, pctx_free=False):
    """Shared order tail for every entry path: risk, bias / leg / HTF / confluence filters,
    targets (#2 room, #7 cap, #9 locked draw), size (#12) and the order dict."""
    l, h, c = sd.l, sd.h, sd.c
    tol = p.eq_tol_pts * p.es_pt
    risk = entry - stop
    if not (p.min_risk_pts * p.es_pt <= risk <= p.max_risk_pts * p.es_pt):
        _f("x_risk_too_small" if risk < p.min_risk_pts * p.es_pt else "x_risk_too_big")
        return None
    if p.use_bias:
        ref_open = ctx.opens.get("1330" if session == "PM" else "midnight")
        if ref_open is not None and not entry < sd.x(ref_open):
            _f("x_wrong_side_of_open")
            return None
    if not skip_leg_pd and p.leg_pd and p.leg_pd_at == "arm" and entry > sw["ext"] + p.leg_pd * (leg_hi - sw["ext"]):
        _f("x_leg_premium")
        return None                                   # entry FVG not in the leg's discount
    if session == "PM" and p.pm_judas_1330 and not _judas(ctx, sd, sw, "PM"):
        _f("x_pm_judas")
        return None                                   # M7.1 option
    htf = _htf_tag(ctx, sd, i, sw["ext"], tol)
    if p.require_htf and not htf:
        return None
    cf = None
    if getattr(ctx, "conf", None) is not None:
        cf = ctx.conf.at(ctx.idx[i] + pd.Timedelta(minutes=ctx.tf), sd.x(sw["ext"]), sd.sign,
                         known_by=ctx.idx[sw["ext_i"]] + pd.Timedelta(minutes=ctx.tf))
        n_tf = len(cf)
        top = max((CF_TFS.index(x) for x in cf), default=-1)
        if n_tf < p.conf_min_n or (p.conf_min_top and top < CF_TFS.index(p.conf_min_top)):
            _f("x_confluence")
            return None
    elif p.conf_min_n or p.conf_min_top:
        return None
    td = None
    if getattr(ctx, "conf", None) is not None:
        now = ctx.idx[i] + pd.Timedelta(minutes=ctx.tf)
        td = sum(ctx.conf.trend(now, x) == sd.sign for x in ("D", "4h", "1h", "15m"))
        if p.topdown:
            ok = sum(ctx.conf.trend(now, x) == sd.sign for x in p.topdown)
            if ok < (p.topdown_min or len(p.topdown)):
                _f("x_topdown")
                return None
    elif p.topdown:
        return None
    drv = getattr(ctx, "cur_news", None)
    news_pd = news_wait = None
    if drv is not None and drv["made"] is not None:
        news_pd = bool(entry < sd.x(drv["eq"]))
        news_wait = float(ctx.t[drv["made"]] + ctx.tf - drv["R"])
        if p.news_range_pd and not news_pd:
            _f("x_news_range_premium")
            return None
    eq_hi = _eq_levels(sd, i, tol, lows=False)
    above = max(leg_hi, entry)
    lv = _targets(ctx, sd, i, above, eq_hi, p, (sw["ext"], leg_hi), sw["ext_i"])
    htf_t = tuple(p.htf_targets) + (("30m",) if p.htf_targets_30m and "30m" not in p.htf_targets else ())
    if htf_t and getattr(ctx, "conf", None) is not None:
        now = ctx.idx[i] + pd.Timedelta(minutes=ctx.tf)
        real = ctx.conf.targets(now, sd.x(above), sd.sign, htf_t, p.htf_far_edge)
        lv = sorted(set(lv) | {(sd.x(v), "array") for v in real})
    if p.fvg_targets:                  # untouched opposing FVGs / voids: near edge, then CE (L9)
        extra = []
        for z in sd.opposing():
            if z.i <= i and z.bottom > above and h[z.i + 1:i + 1].max(initial=-np.inf) < z.bottom:
                extra += [(z.bottom, "array"), (z.mid, "array")]
        lv = sorted(set(lv) | set(extra))
    kinds = [kind for v, kind in lv]
    lv = [v + p.pool_beyond_pts * p.es_pt if (p.exit_mode == "split" and kind == "pool")
          else v - p.exit_before_pts * p.es_pt for v, kind in lv]
    # owner #7 (Ep 02): an unbroken opposing HTF FVG between the entry and the target caps it
    capped, resist, capx = False, None, None
    if p.htf_resist_cap:
        if getattr(ctx, "conf", None) is None:
            _f("x_htf_resist_nodata")
        else:
            now = ctx.idx[i] + pd.Timedelta(minutes=ctx.tf)
            src = tuple(CF_SRC[x] for x in p.htf_resist_src)
            r = ctx.conf.resistance(now, sd.x(entry), sd.sign, p.htf_resist_tfs, src)
            if r is not None:
                capx = sd.x(r[0]) - p.htf_resist_buffer_pts * p.es_pt
                if capx - entry < max(p.min_rr * risk, p.htf_resist_min_room * p.es_pt):
                    _f("x_htf_resist")
                    return None
                pairs = [(v, k) for v, k in zip(lv, kinds) if v <= capx]
                if not any(abs(v - capx) <= p.es_pt for v, _ in pairs):
                    pairs.append((capx, "array"))
                pairs.sort()
                lv, kinds = [v for v, _ in pairs], [k for _, k in pairs]
                capped, resist = True, r
    keep = [(v, k) for v, k in zip(lv, kinds) if v - entry >= p.min_rr * risk]
    pools = [v for v, k in keep if k == "pool"]
    lk = getattr(ctx, "cur_lock", None) if p.draw_lock == "session" else None
    final_T = False
    if lk is not None:                 # owner #9: ONE exact target, locked before the session
        tv = sd.x(lk["target"])
        T = tv + p.pool_beyond_pts * p.es_pt if (p.exit_mode == "split" and lk["kind"] == "pool") \
            else tv - p.exit_before_pts * p.es_pt
        kT = lk["kind"]
        if capx is not None and T > capx:
            # owner #7 x #9: the draw's exit must be on the near side of the cap - an unbroken
            # opposing HTF FVG before the draw ends the trade in front of it [our interpretation]
            T, kT = capx, "array"
            _f("x_lock_capped")
        if T - entry < p.min_draw_pts * p.es_pt or T - entry < p.min_rr * risk:
            _f("x_room_lt_min")
            return None
        if not p.draw_lock_partials:
            rungs = []
        elif p.draw_lock_levels == "frozen":
            rungs = []
            for v, k, _ in lk["marked"]:
                x = sd.x(v)
                x = x + p.pool_beyond_pts * p.es_pt if (p.exit_mode == "split" and k == "pool") else x - p.exit_before_pts * p.es_pt
                if entry + p.min_rr * risk <= x < T - p.es_pt:
                    rungs.append((x, k))
            rungs = sorted(set(rungs))
        else:
            rungs = [(v, k) for v, k in keep if v < T - p.es_pt]
        keep = rungs + [(T, kT)]
        draw, final_T = T, True
    else:
        if not keep:
            _f("x_no_target_1R")
            return None
        draw = pools[0] if pools else keep[-1][0]     # the draw: the nearest liquidity pool
        if p.pm_off_lunch and session == "PM" and "lunch" in ctx.sess and ctx.t[i] >= ctx.sess["lunch"][2]:
            lu = sd.x(ctx.sess["lunch"][0] if sd.sign > 0 else ctx.sess["lunch"][1])
            lu = lu + p.pool_beyond_pts * p.es_pt if p.exit_mode == "split" else lu - p.exit_before_pts * p.es_pt
            if lu - entry >= p.min_rr * risk and sd.h[_idx_at(ctx, 810):i + 1].max(initial=-np.inf) < lu:
                draw = lu              # M7.1: the untaken lunch high is the PM draw
                keep = [(v, k) for v, k in keep if v < lu - p.es_pt] + [(lu, "pool")]
        if p.min_draw_pts and draw - entry < p.min_draw_pts * p.es_pt:
            _f("x_room_lt_min")
            return None                                   # not enough room to the draw (minimum)
    lv, kinds = [v for v, _ in keep], [k for _, k in keep]
    if p.t1_fixed_pts > 0:             # Ep03.24 test (owner #2: not the goal, default off)
        f = entry + p.t1_fixed_pts * p.es_pt
        if p.t1_fixed_all:
            lv, kinds = [min(f, lv[0])], [kinds[0]]
        elif f < lv[0] - p.es_pt and f - entry >= p.min_rr * risk:
            lv, kinds = [f] + lv, ["fixed"] + kinds
    scalp = False
    sl = getattr(ctx, "cur_sloppy", "")
    if sl and p.sloppy_mode == "scalp":   # #10 scalp mode: one exit at min(+5, T1), no adds
        lv, kinds, scalp, final_T = [min(entry + p.sloppy_scalp_pts * p.es_pt, lv[0])], [kinds[0]], True, False
    smt_n = int(sw["smt"] is True) + int(sw.get("smt2") is True)
    if smt_n < p.smt_min:
        _f("x_no_smt")
        return None
    shares = _first_units(p, ctx.equity, risk, entry, risk_mult)
    if shares < 1:
        return None
    _f("4_order")
    t = ctx.t[i]
    lh = p.last_hour[0] <= t < p.last_hour[1]
    setup = "am_mm" if session == "AM" else session.lower() if session != "PM" else (
        "pm_last_hour" if lh else "pm_sb" if 840 <= t < 900 else "pm")
    if final_T:
        levels = lv
    else:
        levels = lv[:max(1, len(p.ladder_fracs))]
    heavy = None
    if p.runner_htf_exit and getattr(ctx, "conf", None) is not None:
        s_ = ctx.conf.support(ctx.idx[i] + pd.Timedelta(minutes=ctx.tf), sd.x(entry), sd.sign, p.runner_htf_exit)
        if s_ is not None and np.isfinite(s_[2]):
            heavy = s_[2]
    order = dict(side=sd, session=session, setup=setup, swept=sw["name"],
                 smt=sw["smt"], smt2=sw.get("smt2"), smt_n=smt_n,
                 i=i, entry=entry, stop=stop, t1=lv[0],
                 ext=sw["ext"], ext_i=sw["ext_i"],
                 body_low=float(min(min(sd.o[k], c[k]) for k in range(max(0, sw["ext_i"] - 1), min(i, sw["ext_i"] + 1) + 1))),
                 t2=None if (scalp or p.t1_fixed_all) else
                 (lv[-1] if final_T and len(lv) > 1 else lv[1] if len(lv) > 1 else None),
                 shares=shares, htf=htf, levels=levels, level_kinds=kinds[:len(levels)], final_T=final_T,
                 conf_n=None if cf is None else len(cf), conf_top=(cf[-1] if cf else ""),
                 conf_tfs="|".join(cf or []),
                 macro=bool(p.macro[0] <= t < p.macro[1]), td_agree=td,
                 judas=_judas(ctx, sd, sw, session),
                 macro_win=next((f"{a // 60:02d}{a % 60:02d}" for a, b in MACROS if a <= t < b), ""),
                 lh_sweet=bool(p.last_hour_sweet[0] <= t < p.last_hour_sweet[1]),
                 capped=capped, resist_tf="" if resist is None else resist[1],
                 resist_lo=None if resist is None else resist[3], resist_hi=None if resist is None else resist[2],
                 draw_side=0 if lk is None else lk["side"], draw_px=None if lk is None else lk["target"],
                 draw_name="" if lk is None else lk["name"], draw_kind="" if lk is None else lk["kind"],
                 sloppy=sl, scalp=scalp, no_adds=scalp, news_pd=news_pd, news_wait_min_actual=news_wait,
                 heavy_dead=heavy)
    order.update(tags)
    return order


def _smt(ctx, sd, i, key, level, session, pctx, psides, ppos):
    """SMT divergence: the partner index did NOT take its own version of the swept level
    (by the same bar). None when there is no partner or the level has no partner twin."""
    if pctx is None or key.startswith(("rel_eq", "round")):
        return None
    ps = psides[sd.sign]
    j = ppos.index.searchsorted(ctx.idx[i], side="right") - 1
    if j < pctx.start:
        return None
    plv = _sell_side(pctx, ps, session, j, True).get(key)
    if plv is None:
        return None
    at = lambda m: pctx.start + int(np.searchsorted(pctx.t[pctx.start:], m))
    created = {"am_session": at(810), "lunch": at(810), "opening_range": at(pctx.or_end),
               "london": at(300)}.get(key, pctx.start)
    if key.startswith("news_range"):
        R = 510 if key == "news_range" else int(key[len("news_range_"):])
        d = getattr(pctx, "news_dr", {}).get(R)
        created = d["made"] if d and d["made"] is not None else (at(540) if R == 510 else None)
    if created is None or j < created:
        return None
    return bool(ps.l[created:j + 1].min() >= plv)
