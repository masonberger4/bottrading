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
         candle before the displacement), else beyond the FVG, one tick of pad (Ep 08); other
         stop modes / modifiers in entries.py (E6 family, mohawk, mt_close_stop); 1.2% open
         risk at entry, at most 1.3% including adds (owner #12, Ep 07); size rules (E9),
         loss halving (E10) and contract caps (E11) are switches.
Adds     before the first partial only: a new FVG after the fill, plus (owner #7 revised) the
         higher-timeframe FVG BEHIND the trade that price already traded through - support /
         resistance and an add zone, never a target; none on NFP days (E12f)
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
  (wick_levels  50% of the previous day's wicks as extra targets - ON by default, L10)
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
import warnings

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
STOP_MODES = ("ob_mt", "fvg", "ob_near", "fvg_candle", "ce2", "fvg_c1_low", "fvg_bodies", "fvg_open", "sweep",
              "ob_mt_pure")       # E6 / E6b / E6c / Ep01.20 / M2.5
ENTRY_MODES = ("edge", "ce", "edge_1tick", "iofed", "ladder")      # D11 / E2
# Ep07.2: the Ep 07 model in one preset (OB bodies before the break and VIs as entry zones, the body-midpoint
# stop, body exit and swing trail of Ep 07, VI holds, one tick inside the gap edge, VIs as adds)
PRESET_EP07 = dict(ob_entry="both", vi_entries=True, ep07_stop=True, ep07_body_exit=True, ep07_trail=True,
                   vi_hold=True, entry="edge_1tick", add_arrays=("vi",))
CF_SRC = {"fvg": 0, "ob": 1, "gap": 2, "vi": 3, "breaker": 4}   # confluence array sources (#7)


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
    trail: bool = False            # X5 / D14: trail the stop under EVERY new FVG after the fill (the old, aggressive trail; ICT's
                                   # "don't trail early" rule says no - the default trail is ladder_trail, after the partials)
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
    ladder_trail: str = "fvg"      # X5 / D14 (ICT): after trail_after rounds of partials, trail under the newest FVG formed
                                   # since the last partial (never the FVG right after the shift);
                                   # "hit" = stop to the array just paid at once price closes away_pts
                                   # beyond it (Mase's version); "prior" = one level behind;
                                   # "measuring" = under the measuring gap after trail_after rounds (Ep03.20);
                                   # "breakaway" = under the breakaway (first, protected) FVG after trail_after rounds (X5a);
                                   # "off" = no ladder trail (trail_first_fvg / trail_breakaway / ep07_trail are separate)
    away_pts: float = 1.0
    be_on: str = "expansion"       # X4 / D14: breakeven only after the first partial AND expansion -
                                   # [our interpretation] a later bar closes beyond the first target;
                                   # "t1" = at the first partial; "after_mss" = a close above the leg high (003 ~40:15);
                                   # "stall" = the trade stalls after 1R (009 ~09:46); "pool" = the high reaches the first
                                   # liquidity pool of the ladder (Ep03.15); "off" = never. The BE level is the average
                                   # entry + be_pad_pts (+ the round-trip cost with be_cost_pad). The Silver Bullet and Ma
                                   # Deuce follow it only with extras_be_on="follow" (default: BE at their first target)
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
                                   # breaker candle's full high-low range; "body" = Ep 01 switch;
                                   # "leg" = the A->B leg (070), "last" = the last up-close candle
                                   # (cc05_014) - see levels.breaker_zone
    sb_only: bool = False          # D2 test: fills only inside the Silver Bullet windows
    sb_windows: tuple = ((600, 660), (840, 900))
    fvg_abort: bool = False        # X6: a 5m candle CLOSE beyond the FVG's far edge, the next candle trades beyond its extreme
                                   # -> out (fvg_abort_mode "rule"; "legacy" = the first build)
    time_stop_min: int = 0         # X9 / X9a / X9d: no `time_stop_pts` of progress (time_stop_ref: or the leg high / the array's
                                   # far edge) within N minutes (time_stop_bars: candles) -> out (time_stop_frac: or cut half)
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
    org_close: int = 0             # ORG uses the last price before this minute: 975 = 16:15 ES
                                   # settlement (7 videos), 960 = 16:00 (3 videos; SPY's close);
                                   # 0 = per symbol (L7 levels_detectors): the resolved session close
    or_minutes: int = 30           # opening range 09:30-10:00 (2023 videos); 60 = CC's 09:30-10:30;
                                   # its high/low are AM sweep pools and targets once complete; 0 off
    htf_targets: tuple = ("15m", "1h", "4h", "D")   # opposing FVGs / OBs / gaps on these
                                   # those timeframes as targets, near edge then CE (L9, P2)
    neutral_skip: bool = False     # B17/N8: skip the day after a range > 2x the 5-day average
    three_day_rule: bool = False   # B11: after 3 same-direction daily closes, not that direction on day 4
    tgif: bool = False             # M14: on Fridays after a one-way week, only the retrace direction
    pd3_exit: bool = False         # X7 / X7a: out once bodies close through the 3 nearest PD arrays (FVG / VI / OB MT / breaker,
                                   # listed at the fill; pd3_dynamic re-reads; the second break tags pd3_warn)
    sd_first_beyond: bool = True   # L12: with sd_targets, only the first SD level beyond the nearest pool
    topdown: tuple = ()            # e.g. ("D", "4h", "1h", "15m"): structure on these timeframes
    topdown_min: int = 0           # must agree with the trade on at least this many (0 = all)
    # pre-09:30 setups (test-only switches; mentorship/digests/pre_open_entries.md)
    pre_0700: bool = False         # 07:00-08:30 window (022, 032, 099), same model; flat before an
                                   # 08:30 release (pre_flat_0830)
    pre_flat_0830: bool = True
    pre_0900: bool = False         # 09:00-09:29 entries, any day (018, 056, 100); not with am_from_0830 (the AM covers it)
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
    flip_triggers: tuple = ("ob_mt", "wk_dc")   # B8 triggers of the htf "flip" column: ob_mt (B8a),
                                   # wk_dc (B8c), flip_pd3 (B8b), flip_close_above (B8d), flip_thu_wopen
                                   # (B8e); B8f is the engine switch stop_flip
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
    # #3 year end (Ep01.9, N7.4) - owner answer 2026-10-18: (a) against December, squaring map
    year_end: str = "december"           # owner #3 (a): "december" (side from December's direction) / "long" (old
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
    breaker_mt_floor_strict: bool = False  # [our interpretation] switch: a unicorn gap wholly below the
                                         # MT is dropped as a plain-FVG entry too (spec 6b: unicorn pick only)
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
    # #10 sloppy days (B17.4, N8.1, Ep08.2) - owner answer 2026-10-18: stand aside on sloppy days only
    sloppy_mode: str = "stand_aside"     # owner #10: stand aside on sloppy days; "off" = tag only; "scalp"
    sloppy_tests: tuple = ("big_prev", "chop")   # owner: NFP-week Thu / FOMC week stay tradable; add "nfp_week" to block
    sloppy_big_mult: float = 2.0         # [our interpretation] prior range > 2x ADR5
    sloppy_chop_frac: float = 0.35       # [our interpretation] range since midnight < 0.35x ADR5 ...
    sloppy_chop_cross: int = 4           # ... and >= 4 close crossings of the midnight open
    sloppy_chop_from: int = 120          # checked from 02:00
    sloppy_release_frac: float = 0.25    # released by a close 0.25x ADR5 beyond the chop range
    sloppy_scalp_pts: float = 5.0        # scalp mode: single exit at min(+5, T1)
    # further sloppy tests (opt-in, add the name to sloppy_tests) [our interpretation throughout]:
    #   "premium_run" (B17, 044 ~1:14:47) a one-way run of sloppy_run_days sessions with no real
    #       retracement (each close and low above the prior one) whose last day traded into an old
    #       daily high of the last sloppy_run_lookback sessions (mirror for a run down)
    #   "fomc_week" (Ep03 00:18:23-00:18:49) the Mon-Fri week holds an FOMC day and the NFP
    #       release (sloppy_fomc_nfp=False: any FOMC week)
    #   "inside_bisi" (B17, 091 ~6:12) yesterday's whole range sat inside one open daily FVG
    sloppy_run_days: int = 3
    sloppy_run_lookback: int = 20
    sloppy_fomc_nfp: bool = True
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
    round_pool_from: str = "session"     # #13 [our interpretation, Ep 02 ~2:37]: a round handle is untaken
                                         # if the SESSION so far (09:30 AM / 13:30 PM; midnight before
                                         # 09:30) has not traded it - on 2023-01-03 ES traded 3906.75
                                         # overnight, yet ICT's buy side at the 09:30 open was "3 900"
                                         # (spec test c); "midnight" = untaken since midnight
    round_step_pts: float = 0.0          # L17 (cc12_001 ~34:00, CC only; 2023 index work does not round):
                                         # targets rounded DOWN and limit entries UP toward price to this
                                         # step (ES pts) on the real front-month price (#13 mapping; SPY:
                                         # its own price); stops are not rounded. 0 = off
    # --- verified bugs -----------------------------------------------------------------------
    seen_from_created: bool = True       # M7.1 fix: a pool is spent only if traded through AFTER it
                                         # formed (the lunch / overnight / AM highs could never be targets)
    pm_off_lunch: bool = False           # M7.1: PM draw = the lunch high (low) when it is untaken
    pm_judas_1330: bool = False          # M7.1: PM sweep must be the move against the 13:30 open
    displacement_mult: float = 0.0       # M1.2 option: MSS candle body >= N x the mean body of the
                                         # 10 bars before it [our interpretation]; 0 = off
    # --- shared helpers (rule_coverage.md "Shared pieces to build first") -------------------
    vi_arrays: bool = False              # VI wiring: volume imbalances in confluence / htf arrays
    turtle_soup: str = ""                # M12 turtle soup (off). Variants, one at a time:
                                         #  "2023"     M12.1 (022 ~2:47:29): no MSS; the sweep takes the level by
                                         #             <= ts_max_pts and closes back above within ts_back_bars;
                                         #             limit at the PD array's top, stop at the array / a gap
                                         #  "cc_limit" M12.3 (cc04_011 ~9:45): with a bias (lock side / htf_bias)
                                         #             a resting buy limit at (ts_cc_below_pts under) the old low
                                         #  "cc_1h_ob" M12.3 (cc02_001 ~17:41-25:21): 1h sweep into a daily bullish
                                         #             OB, buy limit at the 1h last down candle's open; half at
                                         #             1R, BE after 2R, runner 5R (ts_r_mults / ts_be_r)
                                         #  "or60"     M12.3 (cc10_010 ~6:51): turtle soup below the OR60 low after
                                         #             10:30, target the OR60 high
                                         #  "external" M12.4 (cc12_004 ~29:35): a false low that stopped short of an
                                         #             unreached HTF discount array is run into the array; buy there
    ts_max_pts: float = 5.0              # false break "by a little": at most this many ES pts (M12.5 depth)
    ts_back_bars: int = 3                # close back above within this many bars of the extreme (M12.5 back)
    ts_need_htf: bool = False            # the sweep must reach into an HTF array (htf tag)
    ts_entry: str = "array"              # 2023: "array" = limit at the PD array top (M12.1), capped at the swept
                                         # level [our interpretation]; "level" = at the swept level (old reading)
    ts_stop: str = "array"               # 2023/external: "array" below the array (022); "gap" the nearest
                                         # NWOG/NDOG/ORG level below the old low (038 ~41:58); "ext" below
                                         # the false-break extreme. No array / gap found -> "ext"
    ts_cc_below_pts: float = 0.0         # cc_limit: the limit this many ES pts under the old low ("at or
                                         # just below"); stop = level - ts_max_pts (a deeper run = a real decline)
    ts_r_mults: tuple = (1.0, 5.0)       # cc_1h_ob management: half off at 1R, the runner at 5R
    ts_be_r: float = 2.0                 # cc_1h_ob: breakeven once price reaches 2R
    ts_gate_mss: bool = False            # M12.5: the turtle-soup depth/back test also gates the MSS / OB model
    # B8f (042 ~1:08:19): stopped out beyond a breaker's far edge cancels the idea -> the other side
    # for the rest of that day. "breaker": the stop lay beyond the trade's breaker zone; "smt": an
    # SMT trade's stop-out (SMT-only option); "off"
    stop_flip: str = "off"
    # M3.10 (048 ~39:02): an immediate rebalance (A7) printed inside the SB window -> expect more
    # than 5 handles: the SB draw must be at least this many ES pts away (0 = off)
    sb_rebalance_ext: float = 0.0

    # --- package levels_detectors (rule_coverage.md section 3; build_log.md) -------------------
    # B21 / L3 IPDA data ranges [CC] (015 ~4:25; cc05_004 ~1:56; cc09_008 ~6:03): the high/low of the
    # last 20/40/60 trading sessions, rolling from yesterday (= day 1). Needs >= 61 prior sessions
    # (backtest.HIST_DAYS); shorter histories give only the ranges they cover.
    ipda_pools: bool = False             # the 20/40/60-day highs/lows as sweep pools and targets
    ipda_next: bool = False              # cc05_003 ~28:38: as targets only the NEXT in sequence - the 40-day
                                         # once today traded through the 20-day, then the 60-day
    ipda_eq_day: str = "off"             # cc05_003 ~1:18:26 "range day until news": price near EQ of all
                                         # three ranges with both sides run -> "tag" / "skip" (no entries
                                         # before the day's first release; none -> no entries)
    ipda_eq_frac: float = 0.15           # [our interpretation] "near EQ" = within 15% of each range of its EQ
    ipda_eq_days: int = 10               # [our interpretation] "both sides run" = an earlier 20-day high AND
                                         # low were both taken within the last N sessions
    ipda_session: str = "eth"            # review fix (B21 / L3): IPDA ranges from daily FULL-session candles
                                         # (backtest.prepare's eth dict; RTH where a date has none, e.g. SPY);
                                         # "rth" = the 09:30-16:00 sessions (the first build)
    # A1 swing tiers (014 ~0:12; cc05_002 ~20:14; MSS on the parent swing, 010 ~41:31)
    mss_ref: str = "stl"                 # MSS reference = the last "stl" / "itl" / "ltl" swing high before
                                         # the sweep extreme (a tier is known once its right neighbour is)
    mss_ref_fallback: str = "lower"      # no such swing: "lower" tiers then the highest high (old rule),
                                         # "highest" high of the 3*pivot_n bars at once, "none" = no MSS
    # A2 (042 ~59:04; 033 ~24:34): a level is booked only 1 tick through it; an imbalance is no liquidity
    sweep_ticks: float = 1.0             # ES ticks (0.25 ES pt) through a level for a sweep / spent pool /
                                         # partner SMT / SB swept tag; 0 = any print beyond (the old rule)
    sb_draw_pools_only: bool = False     # the Silver Bullet draw must be liquidity (a pool), not an array
    # A5 FVG sub-rules
    fvg_c2_dir: bool = True              # spec default: c2 (the displacement candle) closes in the gap's
                                         # direction (intraday gaps, confluence and the htf table)
    fvg_quadrants: bool = False          # 25/75% quadrants of LARGE opposing gaps as targets (020; 055)
    fvg_quad_min_pts: float = 4.0        # [our interpretation] "large" = at least 4 ES pts wide
    fvg_vi_extend: bool = False          # 022 ~55:00: extend the entry gap to an adjacent VI; a VI inside
                                         # the gap gives the exact limit (its top)
    fvg_skip_above_pool: bool = False    # 060 ~1:10:30: skip an entry gap sitting right above an untaken pool
    fvg_pool_gap_pts: float = 1.0        # [our interpretation] "right above" = gap bottom within 1 ES pt
    htf_ce_draw: bool = False            # 029 ~44:48: the CE of the nearest opposing HTF FVG is the draw
    fvg_q_hold: bool = False             # 022 ~9:09 / 030 ~15:46: bullish price holds the upper quarter of
                                         # the entry gap - a body close below it (after the fill, before T1) exits
    fvg_state_filter: tuple = ()         # entry gap states allowed (tag Trade.fvg_state): "open" (untouched),
                                         # "repriced" (traded into), "rebalanced" (traded through and left)
    fvg_keep_filled: bool = False        # 015 / 051: opposing gaps stay targets after a fill (up to 60 days)
    # B1 (038 ~47:04): price runs liquidity or rebalances, otherwise it consolidates
    vi_targets: bool = False             # untouched opposing intraday VIs as targets (near edge, CE)
    wick_days: int = 1                   # L10 / Ep08.1 / A23: wick CEs of the last N prior days as targets
    no_draw: bool = False                # tag sessions with no draw within no_draw_adr x ADR5 (consolidation)
    skip_no_draw: bool = False           # ... and take no entries in them
    no_draw_adr: float = 1.0             # [our interpretation] reach of a draw: 1 x ADR5 from the session price
    # L1 / M0.2 session pools (067 ~12:40-52:30)
    am_range_end: int = 810              # the AM range ends 13:30 (old); 720 = the rule's 12:00
    prev_am_pool: bool = False           # the previous AM range (09:30-am_range_end) H/L as an AM pool/target
    session_priority: bool = False       # 067 ~52:30: ONE session pool at 09:30 - previous PM if price is near
                                         # it, else London's range, else the previous AM
    org_pools: bool = False              # today's ORG edges (prior close, 09:30 open) as AM sweep pools
    # L2 / Ep08.10 liquidity matrix
    daily_level_needs_array: bool = False   # Ep 08 / 010 ~63:38: a PDH/PDL sweep needs an HTF PD array there
    daily_level_array_tfs: tuple = ("15m", "30m", "1h", "4h", "D", "W", "M")   # review fix: the confluence
                                         # timeframes that count as HTF for it (1m / 5m arrays do not)
    daily_level_needs_flow: bool = False    # cc09_005 ~03:12: ... and daily order flow (D structure) its way
    pd_hl_session: str = "rth"           # "eth": PDH/PDL 1-3 from the full session (18:00 -> close)
    pool_today_hl: bool = False          # today's high/low up to the session start as a pool / target
    matrix_full: bool = False            # Ep08.10: the matrix on full ETH sessions (= pd_hl_session "eth")
    matrix_days: str = "bot"             # "ict": today + yesterday + the day before, plus the 3-day extreme
                                         # (m3h / m3l); "bot" = the three prior days (old)
    # L5 / D21 opening gaps
    gap_quarters: bool = False           # NWOG + NDOG 25/75% levels as targets (020 ~8:21; 039 ~1:26)
    nwog_quarters: bool = False          # NWOG only quarters (D21)
    nwog_skip_holiday: bool = False      # 046 ~16:01: ignore the NWOG of a holiday-shortened week
    nwog_halfway: bool = False           # 037 ~22:46: at 50% between two NWOGs the next one is the draw
    gap_run_stop: bool = False           # 038 ~41:58: a sell-side run stops at the nearest NWOG/NDOG/ORG level -
                                         # the sweep extreme must reach it (within gap_run_tol_pts)
    gap_run_tol_pts: float = 2.0         # [our interpretation]
    nwog_trading_days: bool = True       # nwog_days counts trading days (fix); False = the old calendar estimate
    monday_ce: bool = False              # D21: gap_mode "monday" gaps get a CE level too
    org_sweep: bool = False              # D21: the kept ORGs' high / CE / low as sweep pools
    # L7 ORG behaviour (033 ~14:57; 036 ~53:00; 058 ~53:24)
    org_draw: str = "off"                # "tag" / "draw": the ORG far edge (prior close) is the AM draw unless
                                         # the gap acted as a breakaway (no attempt into it by 09:30 + org_break_min);
                                         # #9 lock: preferred from the 09:30 lock, dropped (re-marked) on breakaway
    org_break_min: int = 30              # B15 "no attempt in 30 minutes"
    org_half_draw: bool = False          # half filled (CE reached, far edge not) -> the unfilled half's far edge
                                         # (no-lock draw; in the #9 lock when half filled by the lock time)
    org_q_hold: bool = False             # tag: the ORG 25% level reached and no body close beyond it (strength)
    # L10 / Ep08.1 wick CE levels
    wick_weekly: bool = False            # the prior week's wick CEs as targets
    wick_both: bool = False              # both wick CEs of each day (any beyond price), not only the far wick
    wick_session: str = "rth"            # "eth": wicks of the full session candle (Ep08.1 full day)
    wick_invalidate: bool = False        # a close back through the prior day's wick CE behind the entry exits
    wick_partial: bool = False           # wick CEs are frozen lock rungs (partial levels) too
    wick_react: str = "off"              # Ep 08: a sweep extreme at a prior daily wick CE: "tag" / "require"
    daily_fvg_exact: bool = False        # Ep 08: daily FVG edges hit to the tick - exact target, no exit buffer
    # M2.1 opening gaps as sweep pools (022: "buy-side incl. NWOG taken")
    pool_gaps: bool = False
    gap_pool_edge: str = "far"           # "far" edge or "ce" of each NWOG/NDOG is the pool
    # T2 opening prices (010 ~38:31; 064 ~55:13)
    release_open: bool = False           # 08:30 release days: retrace bodies hold the 08:30 open (AM entries)
    release_open_stop: str = ""          # "open": stop beyond the 08:30 open; "wick_ce": the 08:30 candle's wick CE
    bias_open: str = "midnight"          # the AM premium/discount open: "midnight" / "0830" / "0930" (D22)
    # Ep01.5 / Ep02.9 / A6 breakaway gap = the first FVG after the MSS (001 ~40:03; 002 ~4:35)
    breakaway: str = "off"               # "tag"; "hold" = a body close beyond its CE exits; "next_fvg" = not an
                                         # entry, wait for the next FVG
    # A13.1 / A13.5 / Ep01.6 / A13.4 breaker structure
    # review fix: Ep01.6 is imperative ("Require a lower low for bz. Take the candle from the L1-to-H
    # leg.") - both are the defaults now; breaker_ll=False / breaker_cand_to="ext" = the old rule
    # (pinned in study.PRE_OWNER / CURRENT; variants A13.1_breaker_ll_off, Ep01.6_breaker_cand_ext)
    breaker_ll: bool = True              # real pivots, L2 < L1 and a body close above the real H
    breaker_cand_to: str = "h"           # breaker candle from the L1 -> "h" leg (Ep01.6) or L1 -> "ext" (old)
    breaker_time: str = "off"            # 070 ~6:24: "hl2" H, L2 and the break in one session block; "all" + L1
    breaker_entry: str = "off"           # "fallback": no FVG after the MSS -> a limit at the breaker top, stop
                                         # beyond the sweep, cancel on a close below the MT; "prefer" = at once
    breaker_levels: bool = False         # Ep05.1: unicorn without an OB MT stop -> stop below the breaker zone
    # A9 / Ep02.8 / Ep03.3 volume imbalances
    vi_min_gap_pts: float = 0.0          # minimum VI body gap (ES pts)
    vi_body_death: bool = False          # dead once a later body spans it (not a close beyond its far edge)
    vi_stop: bool = False                # 009 ~13:46: stop below the VI under the entry (touch ok, no pierce)
    vi_porous_n: int = 0                 # 027 ~22:09: >= N same-side VIs in the leg = porous, no trade (0 off)
    vi_htf_draw: bool = False            # the nearest opposing HTF VI (vi_arrays) is the draw (no-lock draw
                                         # and, review fix, a #9 lock preference)
    vi_news_draw: bool = False           # Ep 02 ~9:19: on release days the lock prefers the daily VI draw
    # Ep06.7 / A3 relative equal highs/lows
    eq_pref: str = "off"                 # "rank": rel-eq pools win the sweep pick and the draw (kind
                                         # "pool_eq"); "require": only rel-eq sweeps / draws
    eq_bodies: bool = False              # cc05_003 ~1:07:26: nearly level BODIES count; line at the lower low
    eq_rank: bool = False                # clusters ranked by touches, then spread (smoother = stronger)
    # A7 immediate rebalance
    imm_rebalance_disp: str = "off"      # "or": an IR in the leg also passes displacement_mult; "require"
    # A11 / Ep01.4 balanced price range
    bpr_max_gap_bars: int = 0            # the two gaps within N bars (0 = any pair)
    bpr_targets: bool = False            # BPRs beyond the entry: near edge and midpoint as targets
    bpr_abort: bool = False              # a body close through the midpoint of the BPR under the entry exits
    bpr_rule: bool = False               # Ep01.4: bpr_abort + the first target capped at the next BPR
    # A15 mitigation block
    mit_targets: bool = False            # opposing mitigation blocks as targets (075 ~21:40)
    mit_body_respect: bool = False       # ... only while no close went through them
    mit_legacy_order: bool = False       # review fix (contested alternative as a switch): the old swing order
                                         # of levels.mitigation_blocks (legacy=True) for the A15 blocks
    # D6
    unicorn_pref: bool = True            # the unicorn FVG is preferred over plain FVGs (A14); False = no preference
    # L3 higher pools
    or_extra: bool = False               # the other opening range (OR60 with or_minutes=30) as pools too
    pw_pm_full_session: bool = False     # previous week / month H/L from full (ETH) sessions
    # L8 vacuum block (cc04_009)
    vacuum_blocks: bool = False          # release gaps (08:30: near / MT / far; 09:45 / 10:00+: near / MT) as
                                         # targets; session opens are the ORG / NDOG (not duplicated)

    # --- package setups_models (rule_coverage.md section 3; build_log.md; code in setups.py) ------
    # All OFF by default (the old behaviour) unless noted. Bullish wording; shorts mirror.
    # A19 / Ep08.4 / A19.2 MSS reference (mss_ref also takes "parent" / "origin", see _mss_ref)
    #   "parent" (A19, 010 ~41:31) the start of the staircase of lower swing highs into the sweep
    #   "origin" (Ep08.4, Ep 08 ~MSS validity) the swing high that started the down-leg into the
    #            sweep extreme: walked back from ext_i while no close went above it and no higher
    #            swing low intervened (review fix: anchored at ext_i) [our interpretation]
    #   "origin_max" the first build's rule: the highest swing high between the swept level's
    #            creation and the sweep extreme [our interpretation]
    mss_eq_wait: bool = False            # A19.2 (044 ~42:55): with relative equal lows, no MSS until the
                                         # lower one (within eq_tol below the swept level) is taken too
    mss_on_side: str = "off"             # A19.4 / Ep04.7 (006 ~49:16; Ep 04 ~49:29) two MSSs each leaving an
                                         # open FVG = "on side": "tag" (a 2nd MSS between arming and the fill),
                                         # "require" (= mss_count 2: higher low, 2nd break, both FVGs open)
    # A20 / M0.4 / Ep07.6 displacement (also applied in the Silver Bullet's MSS)
    disp_mult: float = 0.0               # A20 (cc04_003 ~26:51): the move away (break close - OB body top)
                                         # >= N x the OB body; 2-3 per ICT
    disp_body_mult: float = 0.0          # M0.4 [our interpretation]: the breaking candle's body >= N x OB body
    disp_follow: bool = False            # A20 / M0.4 (009 ~15:51): the next candle follows (closes above the
                                         # break close); the MSS is confirmed at that close
    disp_through_pts: float = 0.0        # A20 rip-through margin: the break close >= ref + N ES pts
    disp_fvg_after_break: bool = False   # A20: the entry FVG must be left by the break (third candle at or
                                         # after the breaking bar), not an earlier gap of the leg
    mss_max_bars: int = 0                # Ep07.6 "speed": the break within N bars of the sweep extreme, else
                                         # the sweep is dropped (0 off)
    mss_disp: float = 0.0                # Ep07.6 "distance" [our interpretation]: breaking candle range >= N x
                                         # the mean range of the 10 bars before it
    mss_ref_sibi: bool = False           # Ep07.6 / M1 (009 ~15:51): the MSS reference is the high of the last
                                         # SIBI left by the leg into the low (else the swing reference)
    mss_ref_tf: int = 0                  # Ep08.16 (Ep 08 ~60:04): the reference is the last swing high on
                                         # this timeframe (minutes, e.g. 5 on 1m bars); 0 = the entry tf
    # M1 / M1.1 / M1.3 market maker model context and speed
    am_htf_draw: bool = False            # M1: AM trades need the htf table's draw on the far side (draw_up for
                                         # a long) beyond the entry
    am_discount_array: bool = False      # M1 (Ep 03): the AM sweep extreme sits in a same-side 5m OB / 1m BISI
    mm_context: str = "off"              # M1.1: both of the above: "tag" (lv_tags mm_ctx) / "require" (AM)
    daily_vi_targets: bool = False       # M1.1 (Ep 03): opposing daily VIs (near edge, CE) as targets
                                         # (needs vi_arrays for the confluence VI rows)
    speed_check: bool = False            # M1.3 (009 ~15:51-16:19): the leg's last SIBI must be closed above
    speed_bars: int = 3                  # ... within this many bars of the extreme, else the sweep is dropped
    body_low_cancel: bool = False        # M1.3 (009 ~16:19): a trade below the swing low's lowest body
                                         # cancels the pending order; on the fill bar it is a stop at it
    # stop_mode also takes "ob_near" (M1: below the MT of the OB nearest the sweep low), "fvg_candle"
    # (M2 062 ~37:28: beyond the FVG's middle candle) and "ce2" (M2 069 ~13:46: below the CE of the
    # lower of the last two FVGs)
    # M2 / M2.3 / M2.7 2022 model (fvg_pick also takes "2022": VI+OB, then the first in the leg's
    # discount, then the deeper of the last two; 022 ~55:00; 042 ~47:20; 082 ~5:31)
    no_breakout_fvg: bool = False        # M2 (022): never the FVG whose middle candle is the breakout candle
    add_leg_cut: bool = False            # M2 (022 ~49:26; 025 ~47:56): adds only in the leg's discount, none
                                         # once price traded past 75% of the leg after the fill
    m2_target: bool = False              # M2 (042 ~1:09:17) [our interpretation]: the draw lies beyond the
                                         # day's range EQ; a rel-eq ("larger") pool preferred, else nearest pool
    three_drives: str = "off"            # M2.7: three drives into the sweep: "tag" / "require"
    # M4 / M4.1-M4.5 / A14 / Ep05.4 breakers and unicorns (breaker_entry also takes "classic":
    # M4.1 the breaker top when the retrace reaches it before the FVG, MT cancel, stop beyond L2)
    unicorn_open_min: int = 30           # A14 / Ep05.4 [our interpretation]: "at the 09:30 open" = the sweep
                                         # extreme within this many minutes of 09:30 (tag unicorn_open)
    unicorn_open_only: bool = False      # M4: the unicorn counts only at the open
    unicorn_only: bool = False           # A14 / Ep05.4: only unicorn entries
    unicorn_entry: str = "edge"          # Ep05.4: "overlap" = limit at the top of the FVG/breaker overlap
    unicorn_rules: bool = False          # M4.2 (007; 018): unicorn needs the Judas, entry in the overlap,
                                         # never below the breaker MT
    add_on_vi: bool = False              # Ep05.4 "add on each new imbalance": new VIs after the fill are adds
    adds_in_breaker: bool = False        # Ep05.4: adds only inside the breaker zone (accumulate, not chase)
    breaker_retest_add: bool = False     # M4: add at the breaker top on its retest after the fill
    adv_breaker: bool = False            # M4.3 (070 ~34:59): limit at the A-B leg MT (fill needs 1 tick
                                         # through), stop beyond L2, target B + 1x(B-A)
    ts_breaker_pyramid: bool = False     # M4.4 (cc12_004 ~33:23): turtle-soup trades add once at the breaker
                                         # the turtle soup forms
    cc_swings: str = "off"               # M4.5 (cc05_005) [CC]: "breaker" (buy the retest of the broken high,
                                         # stop below the new low) / "failure" (a higher low that failed to reach
                                         # a pool, break of the high before it) / "both"
    cc_fail_pts: float = 5.0             # [our interpretation] "failed to reach" = within N ES pts above the pool
    # M5 / M5.1 / M5.2 / Ep01.13 / Ep01.16 / Ep01.17 / T10 last hour (owner #1 windows)
    last_hour_own_slot: bool = False     # M5.2 / Ep01.13: the last hour is its own slot (LH), apart from PM
    pm_last_hour_model: bool = False     # M5 (030; 032 ~56:57): the 2022 model in the last hour - LH sweeps
                                         # and entries inside owner #1's 15:00-15:50 (15:15-15:45 only with
                                         # last_hour_strict), skip once the HTF objective is done
    pm_ep01: bool = False                # M5.1 (001 ~39:03-45:20): nested 4h/1h FVG, refusal at the 1h low,
                                         # breakaway FVG, buy its top, stop below the FVG candle open, one exit
    last_hour_setup: bool = False        # Ep01.13: = last_hour_own_slot + lh_unengaged + lh_htf_done_skip
    lh_unengaged: bool = False           # Ep01.13 (001 ~49:28): the LH draw is liquidity untouched today
    lh_htf_done_skip: bool = False       # Ep01.13 / M5: no LH trade once the day's HTF objective is done
    pm_4h_ce: bool = False               # Ep01.16 (001 ~30:48): from 15:00 bodies hold above the 4h FVG CE
    lh_start_by: int = 0                 # Ep01.17 (001 ~38:57): LH sweep extreme by this minute (925 = 15:25)
    moc_run: bool = False                # T10 (032 ~1:01:00): no setup by 15:40 -> join the run to unengaged
                                         # liquidity (lock / bias side), 5-10 handles, HTF objective not done
    moc_cap_pts: float = 10.0            # [our interpretation] "5-8 (up to 10) handles": target cap
    moc_pool_exit: bool = False          # T10 (027 ~50:40): last-hour trades exit all at the first pool
    # M6 / M7 / M7.2 / M7.3 PM models (pm_judas_filter = the existing pm_judas_1330)
    pm_reversal: bool = False            # M6 (015 ~31:57-36:20): after the day's objective (a delivered lock)
                                         # and the AM extreme taken in the PM, the first return into the IFVG
                                         # at the high; targets the old daily level and the lunch extreme
    pm_lunch_target: bool = False        # M7 (067 ~46:00): PM sweeps of the lunch pool only; draw = the other
                                         # lunch extreme
    pm_lunch_org: bool = False           # M7 / M7.2: ... and the lunch sweep runs into today's ORG
    pm_judas_array: bool = False         # M7.3 (010 ~56:30): beyond the 13:30 open INTO a same-side HTF array
                                         # counts as the PM sweep (no pool needed)
    # M10 / A8 inversion FVG entries (with ifvg_entries)
    ifvg_entry: str = "edge"             # M10 (078 ~50:28; 085 ~27:21): "ce" = limit at the IFVG CE
    ifvg_stop_pts: float = 0.0           # M10 (102 ~1:40:20): stop N ES pts beyond the CE (3-4 per ICT)
    ifvg_min_risk_pts: float = 0.0       # M10: IFVG stops under N ES pts too tight (except 1m and below)
    ifvg_depth: bool = False             # A8 (102 ~1:09:00): no prior pass -> stop beyond the far edge; re-traded
                                         # or both ways -> CE at most (stop beyond the CE)
    ifvg_061: bool = False               # M10 (061 ~2:15:00): an IFVG with a normal FVG below; a body close at
                                         # that FVG's high/CE triggers (market entry)
    ifvg_hold: bool = False              # A8 (048 ~21:32): no close back below the IFVG top before arming;
                                         # a body close below its bottom after the fill exits
    ifvg_after_htf: bool = False         # A8 (086 ~14:12): IFVG entries only once the sweep reached an HTF array
    # M11 / M11a-c immediate-rebalance, CISD-OB and wick-CE entries
    ir_entries: bool = False             # M11a (099 ~3:46; 100 ~44:54): with a bias, enter at once after an
                                         # immediate rebalance; stop below its candle; out on a close below EQ
    cisd_ob_entries: bool = False        # M11b (075 ~1:16:40): wick CISD of the OB into the low; limit at
                                         # min(EQ of the post-CISD range, OB top); OB-low cancel
    wick_ce_entries: bool = False        # M11c (100 ~38:13): limit at the sweep candle's wick CE once the next
                                         # candle closed above it; target 0.5 pt before the high
    # M12 / M12.2 / Ep08.15 turtle soup extras
    ts_need_flow: bool = False           # M12 (cc09_005 ~3:12): daily order flow (D structure) its way
    ts_adds_breakers: bool = False       # M12.2 (Ep 08 ~25:13, ~36:53): turtle-soup trades add on new breakers
    ts_max_run: int = 0                  # Ep08.15 [our interpretation]: the failure close within N minutes of
                                         # the spike extreme (0 = ts_back_bars only)
    # M13 OTE (cc01_004; cc01_005)
    ote: str = "off"                     # "filter": the entry in the 62-79% band of the leg; "limit": limit
                                         # at the 70.5% level
    leg_pd_strict: bool = False          # M13 "never AT 50%": entry strictly below the leg's EQ
    ote_leg_stop: bool = False           # M13: stop beyond the leg's swing low (the sweep extreme)
    ote_stack_tag: bool = False          # M13 (cc12_004 pattern 1): tag ote_stack (OTE + FVG + swept low + OB)
    # M16 / M16.1 / M16.2 / Ep03.11 index SMT models
    smt_entry: bool = False              # M16.1 (cc10_011 ~8:01-18:36) [CC]: an SMT sweep of the 05:00-09:30
                                         # low (or London) -> buy stop above the last down-close candle
    smt_turtle: bool = False             # M16.1: ... or a turtle-soup limit at the swept level instead
    smt_exit: int = 660                  # M16.1: hold to 11:00 (time exit)
    smt_entry_syms: tuple = ("ES", "MES")  # M16.1 (cc10_012 ~10:17): ICT trades only ES off the signal
    sick_sister: bool = False            # M16.2 (053 ~1:56-7:57): trade only the index that took the fewest
                                         # reference highs (lows) by the session start, in the day's discount;
                                         # targets the references it failed to take
    smt_pick: str = "first"              # Ep03.11 / D15 (backtest.combine): "leader" / "laggard" by the SMT tag
    # B18 / B18.1 / B18.2 SMT qualifier
    smt_min_gap_pts: float = 0.0         # B18.1 (cc10_011 ~16:59 "if not obvious"): partner held by >= N ES pts
    smt_need_array: bool = False         # B18 (022): SMT counts only at a PD array (the htf tag)
    smt_rel_eq: bool = False             # B18.1: rel-eq sweeps get a partner twin (its lowest swing low near
                                         # the cluster's swing times) [our interpretation]
    smt_windows: tuple = ()              # B18.2 [CC]: SMT only for sweeps inside these windows, e.g.
                                         # ((300, 570), (720, 900)) = 05:00-09:30, 12:00-15:00; () = any
    smt_pre: bool = False                # B18.2: add the 05:00-09:30 window to smt_windows
    # N6 news profile
    news_profile: str = "off"            # N6 (064 ~52:12; 073 ~10:42): the release's first leg is false -
                                         # "tag" / "require" a trade against the first leg
    news_ce_target: bool = False         # N6 (064 ~1:10:43): with both sides of the news range taken, its CE
    news_no_unicorn: bool = False        # N6 (073 ~4:36): NFP / CPI / FOMC days - no unicorn / breaker entries
    # T13 / Ep04.3 / Ep04.4 power of three and day templates
    require_judas: bool = False          # Ep04.3 / T13: the sweep must be the session's Judas
    judas_window: int = 60               # minutes from the session start for the Judas extreme
    po3_runner: bool = False             # Ep04.3: the last ladder fraction is held as a runner to the close
    po3_require_bias: bool = False       # Ep04.4: PO3 trades need a bias (lock side / htf_bias) their way
    po3_inclusive: bool = False          # Ep04.4: entry "at or below" the open (within eq_tol above it ok)
    po3_hold: bool = False               # T13 [our interpretation]: the expansion holds - a body close back
                                         # beyond the reference open exits
    profile_tags: bool = False           # T13 [CC] (cc10_013): tag the expected profile from D / 4h structure
    nfp_sd: str = "off"                  # T13 [CC]: NFP "seek and destroy": "tag" / "skip"
    # Ep01.15 nested FVGs
    nest_tfs: tuple = ()                 # e.g. ("4h", "1h", "15m", "5m"): the sweep extreme inside an open
                                         # same-side FVG on every listed timeframe (FVG-only confluence)
    # Ep05.8 market maker sell (buy) model
    mmxm_ctx: bool = False               # draw = the original consolidation (the parent swing) [our
                                         # interpretation]; out on a body close beyond the entry FVG's CE
    mmxm_breaker: bool = False           # the smart money reversal must leave a breaker
    # Ep01.22 clean delivery
    clean_leg: int = -1                  # at most N down-close candles from the low to the break (-1 off)
    clean_body: float = 0.0              # down-close bodies in that leg <= N x the mean up-close body (0 off)
    # A18 / A24.2 / M0 / M0.5
    reclaimed_ob: bool = False           # A18: retest of a reclaimed sell-side-of-curve OB is an entry array
    reaper: bool = False                 # A24.2 (076 ~18:30): the Reaper FVG of the breaker leg is the entry
    reaper_confirm: bool = False         # ... only after a reaction candle (wick in, close above its CE)
    candle_draw_bias: str = "off"        # M0 (067 ~12:00): "daily" / "weekly" candle reaches for the nearer
                                         # untaken prior extreme - only that side
    entry_arrays: tuple = ()             # M0.5 / M5.2: more entry arrays after the MSS: "ob", "breaker", "ote",
                                         # "wick_ce", "vi", "reclaimed_ob" - the first one the retrace reaches
    # M15 Ma Deuce (pre_open.py)
    md_big_candle: float = 0.0           # the BISI's middle candle range >= N x ADR5 (one big candle)
    md_second: bool = False              # 2nd entry (a new small SIBI / 2nd rejection before 08:30) = an add
    md_ladder: bool = False              # targets CE, lower quadrant, the 1h BISI low (scale-out ladder)
    md_need_news: bool = False           # an 08:30 release must deliver it
    md_eth: bool = False                 # daily candles from full ETH sessions
    md_blocked: bool = False             # route Ma Deuce through blocked() / skip_news
    # --- setups_models review pass (2026-10-18; build_log.md "setups_models review fixes") --------
    ob_pre_gate: str = "cancel"          # owner #11 x the MSS gates (A20 disp_*, M0.4, Ep07.6 mss_max_bars /
                                         # mss_disp, M1.3 speed_check, A19.2 mss_eq_wait, Ep01.22 clean_*, M1.2
                                         # displacement_mult, A7 imm_rebalance_disp, the mss_ref variants): the
                                         # default pre-break OB order is armed BEFORE the break, so these gates
                                         # act on it through the break its sweep prints later. "cancel": a break
                                         # that fails them (or the sweep dropped by the timing gates) cancels the
                                         # still-pending OB order; "hold": the OB order fills only after the
                                         # gated MSS printed (entry at the OB after the MSS - contradicts #11's
                                         # "before the break", a contested alternative); "off": the first build
                                         # (gates inert for the OB order). Every gate is off by default, so
                                         # the default trades do not change [our interpretation]
    synth_po3: bool = False              # T10 moc_run / M11a ir / M5.1 pm_ep01 / M16.1 smt_entry skip the PO3
                                         # open filter (use_bias): they join a run in progress, and the CC
                                         # SMT model predates PO3 [our interpretation]; True = the first build
    lh_no_lock: bool = False             # M5.2 / Ep01.13 own LH slot: False (owner #9) = the slot locks its
                                         # own draw at 15:00; True = the first build (no lock once the PM
                                         # draw was delivered)
    pm_ep01_adds: bool = False           # M5.1 (001 ~37:45-45:02): the Ep 01 add sequence (in the FVG, in the
                                         # breakaway gap -> stop below its bodies, on a breaker) and trail
                                         # under the bodies of each new FVG, instead of the generic adds
    sick_depth: float = 0.25             # M16.2 "deep discount" [our interpretation]: entry below this
                                         # fraction of the day's range (0.5 = the EQ, the first build)
    mmxm_rel_eq: bool = False            # Ep05.8 (the MM model's liquidity = relative equal lows / highs):
                                         # the MMXM sweep must be of a relative-equal pool
    implied_fvg: bool = False            # A24.1 (035 ~29:46) implied FVGs (wick-CE to wick-CE across a
                                         # displacement candle whose outer wicks overlap) are entry gaps too
                                         # [our interpretation: named once, never defined]
    adv_breaker_pre: bool = False        # M4.3 (070 ~34:59) "with bias on side buy inside the A-B leg ...
                                         # without waiting for the break": with the bias this way (lock side
                                         # / htf_bias), the first close back above A after the run below it ->
                                         # market entry, stop beyond L2, target B + 1x(B-A) [our interpretation]
    cc_profile: str = "off"              # T13 [CC] (cc10_013 / cc10_014) the six index day profiles classified
                                         # at 13:30 from the AM: "tag" (lv_tags cc_<profile>) / "gate" (PM
                                         # trades only in the profile's PM direction; consolidation profiles
                                         # out by 14:00) [our interpretation of the classification]

    # --- package entries_stops_sizing (rule_coverage.md section 3; build_log.md) ---------------
    # Stops. Every distance is in ES points / ticks scaled by es_pt; side-space (bullish) wording.
    tick_pts: float = 0.25               # E3: one tick in ES points
    stop_tick_pts: float = 0.25          # Ep08.17 (010 ~16:01; "1 tick beyond the level"; DEFAULT ON): the
                                         # stop pad is one tick instead of the old 0.01; 0 = use stop_buffer.
                                         # While > 0, stop_buffer is dead (a warning says so). The tick scales
                                         # with es_pt: SPY (es_pt 0.10) pads 0.025, not 0.01 - paper / backtest
                                         # runs that relied on stop_buffer change behaviour
    stop_pad_ticks: float = 0.0          # E6f: > 0 replaces the pad by N ticks (overrides stop_tick_pts)
    ce_stop_pad_pts: float = 0.0         # E6f (102 ~1:40:20): extra ES pts beyond a stop on a CE entry
                                         # (entry="ce"); ICT: 3-4 pts in fast markets, < 2 is too tight
    nfp_stop_wide: bool = False          # E6f (105 ~0:51): on a jobs day the stop goes behind the lowest
                                         # body of the leg (bars sweep-3 .. now) [our interpretation of
                                         # "behind all HTF bodies"]
    mohawk_ticks: float = 0.0            # A4 (075 ~1:25:00): structural stops / trails sit N ticks beyond
                                         # the level (a wick may poke - respect is by the body) and a body
                                         # CLOSE beyond the raw level exits; the "fresh gap" test ignores
                                         # an N-tick poke. Covers the _finish_order stops, every trail
                                         # (trail_pad: FVG, ladder, Ep07, ep01_manage, add_body_stop, AM-tighten,
                                         # SB and Ma Deuce trails) and the stops of the Silver Bullet and Ma Deuce
    sweep_body: bool = False             # A4 (off, unranked): a level is swept only when a candle BODY
                                         # trades through it (min(open, close) beyond), not a wick
    stop_all_ineff: bool = False         # E6d (025 ~55:15; 027 ~30:20; 069 ~13:46): beyond every open
                                         # FVG / VI under the entry since the sweep and any overshoot wick
    stop_ineff_wick: bool = True         # ... incl. the lows printed after the sweep extreme below the gap
    mt_close_stop: bool = False          # A12 / Ep02.3 (002 ~3:45; 036 ~54:00): when the OB mean threshold
                                         # is the binding stop, the hard stop moves to the OB far edge and
                                         # a body CLOSE below the MT exits (wicks may poke)
    ob_zone: str = ""                    # A12 sensitive range (012 ~5:13; 055 ~1:44): "range" = full OB range
                                         # (entry at its high); "sensitive" = high down to the open - entry at
                                         # the open when the wick is stubby, else at the wick CE.
                                         # SCOPE: the pre-break OB path (_ob_pre, ob_entry "pre_break" / "both")
                                         # only; the Ep08.5 anchor path (ob_entries) and setups.array_order keep
                                         # their own entry price, as does ob_entry_px
    ob_stub_frac: float = 0.25           # [our interpretation] a wick <= this fraction of the candle range
                                         # is "stubby"
    ob_disp_mult: float = 0.0            # A12 quality (022 ~13:12; cc04_003 ~26:51): on the FVG path the move
                                         # away from the OB must be >= N x the OB body (0 off)
    ob_cisd: str = "off"                 # A12 validation (075 ~1:16:40): "tag" lv_tags ob_cisd when price has
                                         # traded through the open of the last down candle; "cancel" also
                                         # cancels the order when the OB low is traded before the fill
    ob_targets_1m: bool = False          # A12 (cc01_004 ~36:31): untraded opposing OBs of the session's bars
                                         # are targets (near edge, then MT)
    opp_ob_mt: bool = False              # A12 (065A ~1:39): an opposing OB whose MT price already traded
                                         # through is spent (its other half is not revisited)
    vi_hold: bool = False                # Ep07.4 (009 ~13:46): a body close below the VI under the entry
                                         # exits (the VI must hold)
    engage_range_pts: float = 0.0        # Ep08.17 (010 ~1:15:16): no entry until the session range (since
                                         # midnight) is at least N ES points ("give me 10 handles of a range")
    # Entry price / order types
    iofed_ref: str = "c2_high"           # E2 (003 ~30:30): entry="iofed" = the FVG-forming candle's high
                                         # clipped into the gap; "tick" = one tick past the edge; "q75" = 75%
    entry_ladder_fracs: tuple = (0.5, 0.3, 0.2)   # E2 (030 ~15:46): entry="ladder" = FVG high, 75%, CE
    sb_entry: str = "edge"               # E2: the Silver Bullet's entry price mode (no ladder: NOT BUILT for the SB)
    run_cancel: str = "t1"               # D11: a pending order is dropped when price runs to "t1" without it;
                                         # "last" = only at the last rung, "off" = never (loosened)
    entry_order: str = "limit"           # E1: "stop_cc" = a buy stop at the array top [CC] (never chases)
    add_order: str = "limit"             # E1: "market" = an add fills at the open after the retest bar
    fill_through: float = 0.0            # E3: ticks a limit entry must print THROUGH (0 = any print below)
    exit_fill_through: float = 0.0       # E3: ticks a target must print through to fill
    retrace_candle: str = "off"          # E4 (Ep 07; 009 ~8:11): "closed" = at least one down-close candle
                                         # since the order was armed; "intrabar" = the fill bar opens above
    no_new_extreme: bool = False         # M2.4: freeze the leg high at arming, cancel on a new low (below
                                         # the sweep extreme) before the fill
    evolve_fvg: bool = False             # E5 (057): keep the sweep alive; replace the pending order only by
                                         # a NEWER untouched FVG
    wait_structural: bool = False        # E5 (057 ~2:54): when the stop would be too wide wait for a newer
                                         # structural entry instead of dropping the setup
    mo_tol_pts: float = 0.0              # Ep04.6: ES pts the entry may sit above the reference open
    leg_pd_min: float = 0.0              # D12: entry at/above this fraction of the leg (0.21 = OTE 79% floor)
    ote_cancel: bool = False             # A21.3: a pending OTE order is cancelled when price trades through
                                         # the 79% line
    leg_depth_tag: bool = False          # A21.3: tag lv_tags leg_ote / leg_shallow / leg_deep + leg_third_N
    ob_mt_pure_pad_pts: float = 2.0      # M2.5: stop_mode "ob_mt_pure" = the OB MT minus this many ES pts
    prop_entry: bool = False             # A16 (cc04_008): entry at the propulsion block high - 1 tick
    prop_mt_exit: bool = False           # A16: a body close below the propulsion block MT exits
    prop_zone: str = "range"             # A16: propulsion block zone "range" (high-low) or "body"
    ob_entries: str = "off"              # Ep08.5 (010): OB entry at the anchor open, stop at the MT:
                                         # "fallback" = when no FVG follows the break, "prefer" = at the break
    vi_entries: bool = False             # Ep07.2 (009 / 022): a volume imbalance after the sweep is an entry
                                         # zone (limit at its top); not an IFVG
    irl_entries: tuple = ()              # L14b: internal range liquidity arrays allowed as entries:
                                         # "fvg", "ob", "void" (empty = the default FVG path)
    erl_range_swings: bool = False       # L14b: the P/D range for leg_pd / add cuts = sweep extreme .. the
                                         # highest confirmed swing high of the leg (external-to-external)
    erl_exits_only: bool = False         # L14b: targets are external liquidity (pools) only, not arrays
    # Sizing
    size_rules: tuple = ()               # E9: size-down rules: "news_eve" "fomc_week" "august" "against_macro"
                                         # "decoupled" "low_prob"
    size_down: float = 0.5               # E9: the multiplier of each active size-down rule (compounded)
    size_up_rules: tuple = ()            # E9 (test only): "bpr" (BPR under the entry) "htf_target" (HTF array
                                         # within htf_target_pts of the entry); capped by the 1.3% total
                                         # (size_up_cap_pct). "htf_target" is [our interpretation] of the
                                         # "HTF 5000" size-up (092 ~9:44; 102 ~1:23:50)
    size_up_cap_pct: float = 0.0         # E9: extra total-risk cap (fraction of equity) for an order a size-up
                                         # rule fired on. 0 = the 1.3% cap binds and size_up is nearly inert
                                         # (1.5 x 1.2% is clamped to 1.3%, ~1.08x); e.g. 0.005 lets it reach 1.8%
    size_up: float = 1.5
    htf_target_pts: float = 10.0
    low_prob_tests: tuple = ("against_bias",)   # [our interpretation] "low probability": against_bias,
                                         # no_htf, sloppy
    loss_halving: bool = False           # E10 (061 ~2:26:40): halve risk after each loss (floor halving_floor),
                                         # back to full once winback_frac of the drawdown is won back
    halving_floor: float = 0.25
    winback_frac: float = 0.5
    no_max_after_loss: bool = False      # E10 / Ep08.12 (010 ~49:51): after a loss that day no pyramid
    after_loss_mult: float = 1.0         # Ep08.12: risk multiplier of any later trade on a day with a loss
    after_loss_adds: bool = True         # Ep08.12: False = no adds after a loss that day
    max_contracts_initial: int = 0       # E11: first-unit cap in contracts (0 off; ICT ~6)
    max_contracts_total: int = 0         # E11: first unit + adds cap in contracts (0 off; ICT 10-16)
    units_per_contract: int = 0          # E11: shares per contract (0 = lot)
    # Adds
    add_points: str = "top"              # E12: where in a new FVG an add rests: "top" / "ce" / "q75"
    add_arrays: tuple = ("htf_fvg",)     # E12b: more add arrays: "vi", "ifvg", "ob", "breaker", "htf_fvg" (the
                                         # HTF FVG BEHIND the trade that price already traded through - owner
                                         # #7 REVISED, DEFAULT: support/resistance and an ADD zone, never a
                                         # target; the add still needs adds, a free pyramid slot, before T1)
    htf_add_extra_risk_pct: float = 0.0  # owner #7 add zone: extra open risk (fraction of equity) the HTF-FVG
                                         # add may use ABOVE the 1.3% cap. 0 = the cap binds (owner #12): the
                                         # zone arms only when a stop move (a trail, a BE) has freed risk, else
                                         # it waits (the one-shot flag is spent only when an add is armed).
                                         # Under the default 1.2% entry risk the room before T1 is ~0.1%, so the
                                         # default zone is a near no-op until the stop has moved [documented]
    add_hold: bool = False               # E12b: an add is cancelled by a body close below its array
    add_htf_tfs: tuple = ("15m", "30m", "1h")
    add_low_end: bool = False            # E12c (006 ~51:52): a body closing INTO the last add's FVG -> one
                                         # final add at its bottom (+1 tick), smallest earlier size
    add_fvg_low_end: bool = False        # E12 (same rule, restated)
    add_fvg_low: bool = False            # Ep04.10 (same rule, restated)
    add_cutoff: float = 0.0              # E12 / D12 (022 ~49:26; 025 ~47:56): no adds once price has covered
                                         # (1 - add_cutoff) of the range; 0.25 = the 25% line (0 off)
    add_cutoff_read: str = "covered"     # E12e/D12 reading of the 25% line (sources disagree: "past 25% of the
                                         # leg" 022 ~49:26 vs "halfway of the discount half" 025 ~47:56):
                                         # "covered" = no adds once (1 - add_cutoff) of the range is covered
                                         # (0.25 -> 75%); "progress" = no adds once add_cutoff of the range
                                         # is covered, measured up from the sweep low (0.25 -> 25%)
    add_cut: str = ""                    # E12e: "eq" = no adds past EQ of the range; "leg75" = past 75% of the leg
    add_cut_ref: str = "range"           # range = sweep extreme .. the locked draw; "leg" = .. the leg high
    nfp_no_adds: bool = True             # E12f (105 ~9:13): no pyramiding on a jobs (NFP) day
    no_adds_nfp: bool = False            # E12 (same rule, restated)
    decoupled_no_adds: bool = False      # E12f (045 ~1:01:43): none when ES and the partner diverge
    low_prob_no_adds: bool = False       # E12f: none on low-probability setups (low_prob_tests)
    add_on: str = ""                     # Ep01.18: "retest" = an add at the entry gap top once price left it;
                                         # "breaker" = at the breaker top (= breaker_retest_add)
    add_retest_away_pts: float = 2.0     # [our interpretation] "left" = a close this far above the gap top
    trail_ref: str = "gap"               # Ep01.20 (Ep 01: "below the FVG candle open and bodies"): trails sit under
                                         # each new FVG's "gap" bottom or under its candle "body" lows
    add_body_stop: bool = False          # Ep01.19: after an add the stop moves under the add gap's bodies
    # A13.4 / M1.4 / Ep05.5 / Ep02.2 are built by setups_models (breaker_entry, ob_entry, entry_arrays,
    # round_pools); this package only verifies them (tests/test_entries_stops.py)
    # ---- package targets_partials (build_log.md: targets_partials) -------------------------------------
    # owner #7 REVISED (owner_directives.md #7): an opposing HTF FVG BETWEEN price and the draw is a SPEED
    # BUMP - DEFAULT: a partial at its near edge (a protected "bump" rung), the rest stays for the draw;
    # "cap" = the first build (exit before it, no target beyond, no trade if the room is short); "split" =
    # the timeframe split (cap on the htf_resist_cap_tfs, bump on 15m and lower). An FVG BEHIND the trade
    # is never a target (it is the add zone, add_arrays "htf_fvg"). htf_resist_cap=False switches both off.
    htf_resist_mode: str = "bump"
    htf_resist_cap_tfs: tuple = ("1h", "4h", "D", "W")   # "split": these timeframes cap, the rest bump
    htf_bump_max: int = 1                # speed bumps taken per trade (the nearest N opposing FVGs); review: 1 so most of the
                                         # position stays for the draw ("take a partial at it and keep the rest for the draw")
    htf_bump_frac: float = 0.25          # [our interpretation] the share each bump partial takes (a small extra rung, not a main
                                         # ladder rung); all extras together stay under partial_extra_cap, the draw side keeps the rest
    htf_bump_below_min: bool = True      # a bump nearer than min_rr x risk (but >= inner_min_pts) is still a protected partial
                                         # (owner #7: "take a partial at it"); False = it is dropped (first review build)
    # X3 / X3a ladder shape ----------------------------------------------------------------------------
    ladder_all_pools: bool = False       # X3 (Ep 03; 003 ~1:04:25; 027 ~43:36): a partial at EVERY pool on the way
    run_down: bool = False               # X3a "running down equity": one piece per rung (the first keeps ladder_fracs[0],
                                         # the rest is split evenly) instead of the fixed 3-level cap
    ladder_max_levels: int = 0           # X3a: most main rungs (0 = len(ladder_fracs); run_down / ladder_all_pools: 6)
    partial_extra_frac: float = 0.25     # [our interpretation] each extra partial rung (wick CE, -0.5 SD, halfway,
                                         # inner level) takes this share of the position ...
    partial_extra_cap: float = 0.6       # ... all extras together at most this share; the main rungs share the rest
    wick_partials: bool = False          # X3c (065A ~2:37:30; 065B ~3:52:40; 105 ~9:00): always a partial a little before
    wick_ce_partial: bool = False        # the CE of a wick inside the path (alias of wick_partials); with two wicks the longer
    wick_partial_tfs: tuple = ("D",)     # candle timeframes read for wicks: "D" (prior days), "1h", "4h", "15m", ...
    wick_partial_longest: bool = True    # two wicks in the path -> only the longer one
    wick_partial_protect: bool = True    # the wick rung survives min_rr and the rung cap
    wick_partial_min_pts: float = 2.0    # [our interpretation] a wick counts from this length (ES pts)
    sd_half_partial: bool = False        # X3d (064 ~1:33:48): -0.5 SD is always a first partial (exempt from min_rr)
    sd_neg05_first: bool = False         # alias of sd_half_partial (X3 umbrella)
    halfway_partial: bool = False        # X3d (026 ~14:57): the next partial halfway between the first rung and the next one
    halfway_min_pts: float = 2.0         # [our interpretation] no halfway rung between rungs closer than this
    smt_bank: bool = False               # X3 / X3g (046 ~1:02:40; 037 ~32:56): the sister refuses to confirm a new high
    smt_bank_frac: float = 0.5           # -> bank this share of what is left (once)
    smt_bank_min_r: float = 0.5          # [our interpretation] only when the trade is at least this many R in profit
    smt_bank_against_frac: float = 0.0   # X3g (037 ~32:56 "80% off"): the sister index BREAKS against the trade (prints a new low
                                         # since the fill) while our bar holds its low -> bank this share of what is left (once;
                                         # 0 = off, 0.8 = the lesson's 80%); same min-R gate [our interpretation]
    resistance_mode: str = "off"         # X3f (089 ~8:46; 092 ~1:28:54; 102 ~2:15:30): "low_full" = a low-resistance run
                                         # (<= res_low_max obstacles) is one full pull at the draw; "high_run" = a
                                         # high-resistance run (>= res_high_min obstacles) runs down equity; "both"
    res_low_max: int = 1                 # [our interpretation] obstacles (opposing FVGs, untaken swing highs) allowed
    res_high_min: int = 3                # in a low- / required for a high-resistance run
    capture_frac: float = 0.0            # X3h (013 ~29:22): aim to capture 80-85% of the best-case run: the last rung
                                         # sits at entry + capture_frac x (rung - entry); 0 off (0.85 = ICT's top end)
    # A6 / Ep03.5 / L13 gaps and projections ---------------------------------------------------------------
    measuring_gap: bool = False          # A6 (003 ~31:35; 011 ~6:37; 061 ~1:22:05): tag the measuring gap (an FVG in the
    measuring_band: tuple = (0.3, 0.7)   # middle of the displacement leg; its near edge sits in this band of the leg)
    measuring_mid_frac: float = 0.15     # the gap's CE within this share of the leg's 50% (gap notes: A6)
    measuring_target: bool = False       # Ep03.5: swing extreme -> the gap's anchor, projected once more (-1 SD)
    measuring_anchor: str = "far"        # "far" edge from the swing (gap notes: 061 / 062), "near" (A6's first
                                         # reading), "ce", "dup" (061's alternative: duplicated from the other edge)
    measuring_pool_pts: float = 1.0      # keep the projection only if a pool lies within this many ES pts (062; 0 = always)
    proj_measuring: bool = False         # L13 (alias of measuring_target with the near anchor)
    trail_breakaway: bool = False        # A6 / X5: stop under the breakaway (protected) FVG once price closed above it
    proj_breaker: bool = False           # L13 (070 ~37:31): breaker A-B leg, B + 1 x (B - A): ext -> MSS reference
    proj_org_k: tuple = ()               # L13 (055 ~19:30; 056 ~17:10): ORG size multiples beyond its far edge, e.g. (1, 2)
    proj_ext: tuple = ()                 # L13 [CC]: extensions (1.27, 1.62) of the leg, only where they overlap an opposing array
    mm_targets: bool = False             # Ep08.9: measured move = a range projected once more
    mm_anchor: str = "leg"               # "leg" (ext .. leg high) or "ref" (ext .. the broken MSS swing)
    # A22 / L9 / L11 / A17 / L14d array targets --------------------------------------------------------------
    matrix_targets: tuple = ()           # A22 (cc05_014 ~18:20): "breaker", "mitigation", "rejection" blocks as targets
    breaker_first: bool = False          # A22 (cc05_014 ~21:04): an opposing breaker in the path ends the run in front of it
    skip_exhausted: bool = False         # A22 / L14 (cc07_004 ~4:00): HTF arrays price already traded into are not targets
    fvg_over_ob: bool = False            # L9 (049 ~5:37): where an OB overlaps an FVG the FVG's edge is the target
    fvg_remainder: bool = False          # L9 (038 ~1:11:44): a partly traded opposing FVG keeps its unvisited remainder
    weekly_gap_ce_only: bool = False     # L9 (061 ~2:30:15): the weekly gap's CE is enough, the far edge is a ringer
    rb_targets: str = "off"              # L11 (cc04_006 ~14:14; 059 ~9:38): cover at the rejection block's BODY edge:
                                         # "ladder" = an extra rung before the pool, "replace" = instead of the pool wick
    rej_targets: bool = False            # A17 (alias of rb_targets="ladder")
    pool_body_edge: bool = False         # A17 (015 ~2:15; 059 ~10:03): 2023 reads the body edge of a swing high, not its wick
    rb_min_wick_frac: float = 0.5        # A17 [our interpretation] a rejection candle: wick >= this share of its range
    target_hygiene: tuple = ()           # L14d: "arrays" (levels price traded through before the sweep), "htf" (HTF arrays
                                         # already touched since they formed), "wick" (traded wick CEs)
    void_targets: bool = False           # A10: true price gaps (liquidity voids) as targets, near edge then CE
    leg_start_target: bool = False       # A10 [CC]: the start of the one-sided displacement leg is a fill target
    inter_swing_target: bool = False     # Ep01.21 (~42:19): the nearest untaken short-term high before the draw is a rung
    target_ltf_obs: bool = False         # X1: untraded opposing LTF order blocks as targets
    keep_inner_levels: bool = False      # X1: levels under min_rr stay as small early partials
    inner_min_pts: float = 1.0           # [our interpretation] ... when at least this far from the entry (ES pts)
    final_htf: bool = False              # Ep03.22: the last rung = the nearest 4h / D / W array or daily VI
    org_reprice: bool = False            # M8 (069 ~10:06-14:50): Judas away from the ORG -> T1 = the ORG near edge
    adr_target: bool = False             # L16 [CC]: aim for adr_frac of the 5-day average range from the day's low
    adr_frac: float = 0.65               # (65-70% of the expected range)
    adr_early: bool = False              # L16 (cc08_001 ~1:53): ADR reached before 10:00 -> take adr_early_frac, keep a runner
    adr_early_frac: float = 0.8
    # L12 / D23 / Ep06.4 standard deviations --------------------------------------------------------------
    sd_anchor: str = "leg"               # D23: "leg" (sweep extreme .. leg high; "sweep_leg"), "broken" (.. the broken MSS
                                         # swing), "downleg" (014: the one-sided down-leg into the low), "fulcrum", "london"
                                         # (= "manip": [our interpretation] execution.md ~205 "on the manipulation leg" is read as the
                                         # London swing low..high, measured once its high was taken - NOT the sweep leg that runs
                                         # stops; the sweep leg is "leg"), "multi" (all)
    sd_swings: int = 3                   # [our interpretation] "multi": also the last N confirmed swing legs
    sd_cluster_ticks: int = 0            # L12 (014 ~2:54-4:43; 030 ~26:01): levels from several anchors within N ticks are
                                         # a cluster (high-probability turn); only clusters are kept when any exist
    sd_roles: bool = False               # L12 (064 ~1:33:48): -0.5 first partial, -1 the measured move (most off), -2+ extended
    sd_align: bool = False               # L12 (014; 062 ~42:19): keep an SD level only where it lines up with a pool / array
    sd_align_tol_pts: float = 1.0
    sd_no_pool_fallback: bool = False    # L12: with no pool to pass, use the first SD level that pays min_rr
    sd_close_hit: bool = False           # Ep06.4 (Ep 05 ~6:01-6:49): an SD level is hit by a CLOSE, not a wick ...
    sd_close_window: tuple = ()          # ... optionally only inside this clock window, e.g. (600, 720)
    # M14.2 / M14.4 TGIF ---------------------------------------------------------------------------------
    tgif_zone: bool = False              # M14.2 (066; 074; 084; 089): Friday retrace of 20/22.5/25/30% of the weekly range
    tgif_zone_levels: tuple = (0.20, 0.225, 0.25, 0.30)    # from the extreme (week low incl. Sunday 18:00 to the high)
    tgif_cap: float = 0.30               # no target beyond 30%
    tgif_stand_down: float = 0.40        # 40%+ is reversal talk: no trade
    tgif_exits: bool = False             # M14.4: 25/25/50 at the first three zone levels
    tgif_exit_fracs: tuple = (0.25, 0.25, 0.5)
    # Ep04.x / Ep07.1 / Ep03.19 / X3b -------------------------------------------------------------------------
    target_order: tuple = ()             # Ep04.12 (Ep 04): kinds in the order they are taken, e.g. ("eq", "daily", "vi"); the
                                         # bulk (ladder_fracs_bulk) sits on the first target
    ladder_fracs_bulk: tuple = (0.8, 0.1, 0.1)
    ladder_news_day: bool = False        # Ep04.12: on a CPI / jobs / FOMC day take the slow 80/20 split
    clean_eq_pref: bool = False          # Ep04.11 (Ep 04: smooth equal highs are magnets): the smoothest equal-high pool is the draw
    close_draw: bool = False             # Ep07.1: unrealized prior daily closes (and last week's close) are pool draws
    pool_rank: bool = False              # L4: the larger pool is the draw (timeframe, then touch count)
    pool_rank_reach: float = 3.0         # [our interpretation] ... only within this multiple of the nearest pool's distance
    rel_tfs: tuple = ()                  # L4: relative equal highs / lows read on these minutes too, e.g. (60, 240)
    draw_below_eq: bool = False          # L4 (042 ~1:09:17): the draw is beyond the dealing range's equilibrium
    lrlr_max: int = -1                   # L4 (cc01_007; 025 ~15:00): prefer a draw whose run has <= N obstacles (-1 off)
    pool_runner_pts: float = 0.0         # L4 (027 ~44:20): a runner rung this many ES pts beyond the last pool (fund stops)
    wick_daily_src: str = ""             # A23: "rth" / "eth" candles for the daily wicks (sets wick_session)
    wick_week: bool = False              # A23 (alias of wick_weekly)
    wick_tfs: tuple = ()                 # A23: wick CE targets from these candle timeframes ("1h", "4h")
    wick_read: str = "off"               # A23 (025 ~25:37; 100 ~38:13): "exit" = a close back through a wick CE the bar after it
                                         # was reached ends the rest; a close beyond it = continuation
    sb_split: bool = False               # X3b: the Silver Bullet scales out with the day's _split (slow / news-ahead)

    # --- package management_exits (rule_coverage.md section 3 "management_exits"; build_log.md) -----------------------
    # Every switch below defaults OFF (or to the old behaviour) unless its comment says "DEFAULT". Sources are the
    # rulebook X4-X16 / D14 / D18 / M2.6 / Ep03-Ep07 lines; judgment calls are marked [our interpretation].
    # M2.6 / Ep04.10 adds ---------------------------------------------------------------------------------------
    add_in_pd: bool = False              # M2.6 (022 ~49:26; 058 ~43:12): pyramid only on the entry side of the leg's EQ - the
                                         # add price must lie in the leg's discount (premium for a short), add_pd_level of the leg
    add_pd_level: float = 0.5            # ... the P/D line (0.5 = EQ)
    add_leg_at_fill: bool = True         # M2.6: the leg the add cuts measure is FIXED at the fill (its high = the highest high
                                         # from the sweep extreme through the fill bar), not the high at arming. Acts only
                                         # with add_cutoff / add_cut / add_in_pd / add_leg_cut set
    pool_size_rank: bool = False         # M2.6 (042 ~1:09:17): prefer the larger pool as the draw (alias of pool_rank)
    # X4 / D14 breakeven ---------------------------------------------------------------------------------------
    be_pad_pts: float = 0.0              # X4 (105 ~10:41 "BE + commissions + a little"): the breakeven stop sits this many ES
                                         # pts beyond the average entry
    be_cost_pad: bool = False            # ... plus the round-trip cost per unit (2 x cost_per_share) so that BE nets zero
    be_stall_bars: int = 2               # D14 be_on="stall" (009 ~09:46 "risk removed, free look"): this many closed bars in a
    be_stall_min_r: float = 1.0          # row without a new high, once the trade was at least this many R in profit, -> BE
                                         # [our interpretation of "when stalling"]
    # X5 trailing ----------------------------------------------------------------------------------------------
    trail_after: int = 1                 # Ep03.20 (003 ~1:05:10): the ladder trail starts after this many rounds of partials
    trail_pad_pts: float = 0.0           # X5a: trail pad in ES pts (0 = stop pad + mohawk, the old rule; 0.25 = one tick)
    trail_first_fvg: bool = False        # Ep03.10 / X5 (003 ~42:40; 062 ~37:02): stop under the FIRST FVG after the shift (the
                                         # protected / breakaway gap) once a close is above its top and no body closed below it
    first_fvg_fail: bool = False         # Ep03.10: ... and the first FVG fully closed by a body close = the trade is wrong
    first_fvg_fail_after_t1: bool = False  # ... also after the first partial (default: only before it)
    trade_type: str = "session"          # X5c (064 ~1:38:44): "day" = a day trade keeps its initial stop (below the 08:30 open /
                                         # wick CE), pays itself with partials: no trail, no breakeven. "session" = trails
    day_stop: str = "open"               # X5c: the day trade's stop level, "open" = the 08:30 candle open, "wick_ce" = the CE of
                                         # its lower wick (futures only: needs the 08:30 candle)
    # X6 FVG abort ---------------------------------------------------------------------------------------------
    fvg_abort_mode: str = "rule"         # X6 (045 ~1:19:58): "rule" = a candle CLOSE beyond the FVG's far edge arms the abort,
                                         # the NEXT candle trading beyond the armed candle's extreme confirms it (only the next
                                         # one; otherwise the arm is cleared); "legacy" = the first build (whole-body arm, any
                                         # later bar confirms)
    fvg_abort_tf: int = 5                # X6: the abort reads 5-minute candles (1m bars are grouped; confirm inside the next 5m)
    fvg_abort_body: bool = False         # X6: arm only when the whole candle BODY is beyond the edge (the first build's arm)
    # X7 three-PD-array rule -----------------------------------------------------------------------------------
    pd3_n: int = 3                       # X7a (026 ~28:02; 098 ~47:00): arrays in the list
    pd3_list: tuple = ("fvg", "vi", "ob", "breaker")   # X7a: which arrays count (discretionary in the source)
    pd3_dynamic: bool = False            # X7a: re-read the list every bar (default: fixed at the fill)
    pd3_legacy: bool = False             # the first build: count FVGs formed since the extreme that bodies closed through
    pd3_half: bool = False               # X7b (045 ~1:49:28): a body close below the nearest VI + FVG + OB MT -> half off, once
    pd3_half_frac: float = 0.5
    session_stop_after_fails: int = 0    # X7c (044 ~1:52:49): this many failed trades in a row in a session -> stop for the session
    session_fail_mode: str = "trades"    # "trades" = consecutive losing trades; "arrays" = consecutive losses that ended
                                         # on a structural failure (stop, abort, array/CE/MT/body exits) [our interpretation]
    # X8 other invalidations -----------------------------------------------------------------------------------
    leg_mt_exit: bool = False            # X8b (026 ~28:28): a body close below the MT of the candle that started the leg
    ir_eq_exit: bool = False             # X8c (100 ~1:37:18): an immediate-rebalance trade is out when price retakes the range EQ
    ir_eq_wick: bool = True              # ... by a wick (default); False = a body close
    prop_exit: bool = False              # X8d (cc04_008 ~5:15): propulsion block MT lost (alias of prop_mt_exit)
    offside_exit: bool = False           # X8e (085 ~11:18): the nearest opposing candle must be smashed through; bodies that respect
                                         # its open and trade back through the entry -> out [our interpretation, see manage.py]
    offside_level: str = "open"          # ... the level the bodies must clear: the candle "open" or its "wick_ce"
    meander_bars: int = 0                # X8g (092 ~1:04:38): this many closed bars meandering inside the entry FVG without
                                         # rejecting (no close above its top) -> out (0 off)
    # X9 time stops --------------------------------------------------------------------------------------------
    time_stop_ref: str = "pts"           # X9a: what the trade must deliver: "pts" = time_stop_pts of progress, "leg_high" = reach the
                                         # leg high, "array_far" = leave the entry array through its far (top) edge
    time_stop_bars: int = 0              # X9a (022 ~1:43:27): candles instead of minutes (the fill candle is the first; 0 = use minutes)
    time_stop_frac: float = 1.0          # X9d (cc03_003 ~13:18): share cut when the time stop fires (1 = out; 0.5 = cut half, once;
                                         # a remainder at minimum size is closed)
    time_stop_extras: bool = True        # X9: Silver Bullet / Ma Deuce follow the same time stop when it is on
    far_edge_min: int = 0                # X9c (092 ~1:11:05): minutes the trade has to move back (close at the entry FVG's CE) after
                                         # touching its far edge (0 off; 2 = ICT's two minutes)
    far_edge_frac: float = 0.5           # ... else this share is off ("half or all"; 1 = all)
    # X10 / X11 / X12 session exits -----------------------------------------------------------------------------
    am_bulk_t: int = 0                   # X10b (cc12_004 ~8:25): at this time (minute, e.g. 660) take am_bulk_frac of the AM-family
    am_bulk_frac: float = 0.8            # units that were filled before it (0 off)
    smt_hold_until: int = 0              # X10c (cc10_014 ~3:01): AM trades with an SMT tag are held until this time (630 / 660): no
                                         # soft exits (time stop, meander, far edge, bulk) before it
    smt_hold_exit: bool = False          # ... and what is left is closed at it
    pm_consol_exit: int = 0              # X11c (cc10_014 ~13:17): PM trades on a consolidation-profile day are out at this time (840)
                                         # and no entry starts after it (classifier: setups.cc_profile at 13:30)
    obj_stop: bool = False               # X12 (029 ~1:03:57; 040 ~0:39): the session objective is hit -> close everything at it and
                                         # stop for the day
    obj_source: str = "draw"             # ... "draw" = the locked draw (else the last ladder level), "htf_ce" = the CE of the last
                                         # HTF-array rung
    # X13 / X14 after a loss / a win -----------------------------------------------------------------------------
    reverse_in_session: bool = False     # X13a (001 ~46:57-48:43; experienced): after a loss the session may take the OPPOSITE side once
    lost_side_session: bool = False      # X13a / D18: the no-reversal lock (reverse_after_loss=False) lasts the session, not the day
    loss_ends_morning: bool = False      # X13a: an AM-family loss ends the morning (AM, SB, pre-open, Ma Deuce); the PM is open
    reentry_gate: bool = False           # X13b (070 ~38:41; 085 ~27:21): reentry_half only when the idea is intact - same side, the
                                         # draw not delivered, a RESTORED sweep and an FVG formed after the stop, not on FOMC
    reentry_fomc_ok: bool = False        # X13b (021 ~43:56): a re-entry on an FOMC day (default: none)
    reentry_risk: str = "budget"         # D18: the re-entry risks half of the standard budget ("budget") or half of the losing trade's
                                         # own risk ("loss")
    reentry_lock_r: float = 0.0          # D18 (cc02_005 ~11:33): at this R the re-entry's stop moves to the level that keeps the
                                         # prior loss repaid (0 off; 2.0)
    reentry_target_r: float = 0.0        # D18 (cc02_005 ~10:03): the re-entry is taken off at this R (0 off; 3.0)
    chop_one_win: bool = False           # X14b (031 ~9:20): on a chop / slow day one win ends the day
    no_trade_after_win: bool = False     # X14d (095 ~47:08): no new entry after a winner on the day (SB and pre-open included)
    done_if_target: bool = False         # Ep04.13 (006 ~41:45): the trade's final level hit before done_target_before -> the day is done
    done_target_before: int = 900
    # Ep07.5 / Ep07.7 / T11 ---------------------------------------------------------------------------------------
    add_mode: str = "fvg"                # Ep07.5 (Ep 07 "market efficiency paradigm"): "downclose" = adds rest at a closed down-close
                                         # candle's close (buy down candles) instead of at a new FVG
    tp_upclose: bool = False             # Ep07.5: the add units are sold into the first up-close candle that closes above the add
    ep07_body_fixes: bool = True         # Ep07.7: with ep07_body_exit the swing-low-bodies test also runs on the FILL bar and a pending
                                         # order is cancelled by a bar that traded below them
    late_cutoff: int = 945               # T11 (026 ~1:59:50) DEFAULT: from 15:45 no adds and no fades (entries against the day's direction)
    smt_bias: str = "off"                # B18.3 (B18 "Uses: bias"): SMT at the previous day's high / low in the overnight range gives a
                                         # session bias: "tag" = tag entries smt_bias_agree / smt_bias_against, "filter" = only with it
    smt_exit_against: bool = False       # B18.3 (037 ~32:56): the whole position is out when the sister breaks against the trade (the
                                         # X3g 80% bank at 100%; smt_exit is the unrelated M16.1 time exit). Works on its own (no
                                         # smt_bank needed). B18.3 names "smt_exit": that name is taken by M16.1, so this is the
                                         # same rule under another name [OWNER: confirm the name / the reading]
    # --- management_exits review fixes
    extras_be_on: str = "t1"             # X4: the Silver Bullet / Ma Deuce breakeven. "t1" = the first build (the stop goes to
                                         # breakeven when the first target / rung is taken - the DEFAULT, so their trades are the
                                         # same as before the package); "follow" = the main engine's be_on (t1 / expansion /
                                         # after_mss / stall / pool / off) incl. its pad
    invalidations_extras: bool = True    # X6-X9c / X7a / X8: the invalidation exits (first-FVG fail, abort, three arrays, leg MT,
                                         # IR EQ, offside, meander, far edge) also run in the Silver Bullet and Ma Deuce (each is
                                         # still its own switch, default off); False = main engine only [our interpretation:
                                         # SB: the entry FVG = the setup FVG, the sweep = the leg extreme before its MSS;
                                         # Ma Deuce: the inverted FVG is the entry zone and the sweep]
    stops_passes: int = 3                # X7c / X12 / X13a / X14b / X14d: passes of run_day's fixed point that makes the session /
                                         # day stops two-way between the main engine and the Silver Bullet / Ma Deuce (1 = the old
                                         # one-way order: main loop first, the extras read it, never the other way)
    reentry_stop_only: bool = False      # D18 "re-entry after a stop-out": only a stop / stop_gap exit re-opens (False: any loss)

    # ---- package news_calendar_times (rule_coverage.md section 3; build_log.md) --------------------------------
    # calendar: the minor releases and the release list the news gate (owner #4) waits for
    news_conf_board: bool = False        # N5: the Conference Board consumer confidence (last Tuesday, 10:00) counts as a release [our interpretation: rule-based date]
    news_claims: bool = False            # N5: jobless claims (Thursday 08:30, holiday-shifted) count as a release
    news_minutes: bool = False           # N5 / 082: FOMC minutes (14:00, 3 weeks after the decision) count as a release
    wait_0945: bool = True               # Ep02.1 / N5.2 (002 ~0:25): the 09:45 PMI is a release the AM waits for
    # N1 NFP Friday (Ep04; 006 ~8:35; 105 ~9:13) and D8
    nfp_first_hour: bool = True          # N1: nobody trades the first hour after 08:30 on a jobs day: no PRE9 / NEWS window and no
                                         # Ma Deuce (the 09:30 AM window with the 30-minute NFP floor stays - owner #4)
    nfp_day_from: int = 0                # D8 test: jobs-day entries only from this minute (0 = the engine's own windows)
    # N3 / N3.1 / N3.2 / N3.3 / N3.4 / N3.5 / M9.2 FOMC (14:00 statement, 14:30 press conference)
    fomc_flat: int = 840                 # N3 fomc_flat_before / N3.2: never hold into the release - flat at this minute on an FOMC
                                         # day (the bar ending at it; 0 = off). Orders still working are cancelled
    fomc_flat_before: int | None = None  # N3 spelling of fomc_flat (None = use fomc_flat; a number overrides it, 0 = off)
    fomc_am: str = "open"                # N3.2 (cc10_009 ~3:48; cc08_001 ~6:37): FOMC-day AM: "open" = traded, "recipe" = only if the
                                         # trending-day recipe holds (the HTF table's reaction and draw agree), "skip" = sit out
    fomc_only_am: str = "off"            # N3.3 (cc10_008 ~2:56): an FOMC-ONLY day (no other release) consolidates in the AM:
                                         # "off", "tag", "scalp" (single exit min(+5, T1), no adds), "skip"
    fomc_eve_risk: float = 1.0           # N3 (042 ~3:50; 094 ~1:48): the day before FOMC is slow and imprecise - trade light (x risk)
    pre_fomc_risk: float = 1.0           # N3.4: the same switch in the D8 spelling; both multiply (a re-entry compounds with them)
    skip_pre_fomc: bool = False          # filters.md: the day before FOMC is skipped
    fomc_after_am_block: bool = False    # N3 (095 ~51:27): the day after FOMC sit still in the AM
    skip_post_fomc_am: bool = False      # N3.4 / D8: the same switch in the D8 spelling (either blocks)
    fomc_no_reentry: bool = True         # N3 / N3.5 (021 ~43:56): a loss on an FOMC day ends the day for every session and model
    fomc_observe: str = "off"            # N3.1 (021 ~2:40-6:18): "defer" = scan 14:00 .. fomc_pm_from but hold the order until
                                         # then ("judas" = defer + the M9.2 side rule); "off" = the PM stays blocked
    fomc_pm_block_from: int = 0          # N3.1: the FOMC PM is open before this minute (default 0: blocked from the PM start,
                                         # fomc_pm_from lifts it); 840 = trade 13:30-14:00, sit out the release
    sb_fomc_pm: bool = False             # N3.1: the Silver Bullet PM window (14:00-15:00) runs on FOMC days from max(a, fomc_pm_from)
    fomc_whipsaw_skip_london: bool = False   # N3 (cc08_006 ~3:36): after an FOMC whipsaw (both sides of the 13:00-14:00 range taken in
                                         # 14:00-15:00) skip the next London open (the LON window and the London Silver Bullet)
    fomc_judas: bool = False             # M9.2 (021; 065B ~5:30): the 14:00 move is the Judas; the real move starts at
                                         # fomc_judas_end - only the side opposite to the first run in 14:00 .. end is traded,
                                         # and the PM opens at fomc_judas_end instead of fomc_pm_from
    fomc_judas_end: int = 870            # M9.2 correction: 14:30 (no source for 14:25 was found)
    fomc_stage2_cont: bool = False       # M9.2 (065B): the real-move side holds through the whole PM, not only to fomc_pm_from
    # N4 / D9 CPI
    pre_cpi: str = "off"                 # N4 / D9 (028; 029 ~5:22): the day before CPI: "off", "small" (pre_cpi_risk), "skip"
    pre_cpi_risk: float = 0.5
    skip_pre_cpi: bool = False           # D9: the same as pre_cpi="skip"
    flat_0830_extras: bool = True        # N4 (030 ~7:22; 047 ~5:26): with pre_flat_0830, the 08:29 flat also covers Ma Deuce and the
                                         # London Silver Bullet (the PRE7 / PRE8 / LON main-engine trades always follow pre_flat_0830)
    # N5.4 / N5.5 / N5.6
    skip_two_drivers: bool = False       # N5.4 (100 ~50:59-1:40:56): stand aside the AM when 08:30 and 09:45 / 10:00 both release
    two_driver_gate: bool = True         # N5.4 minimal rule: no entry window ends before the day's last morning release
    fed_chair_skip_am: bool = False      # N5.5 (default OFF: the calendar is unverified and incomplete - owner to verify / complete FED_CHAIR incl. 2026 and speeches, then switch on) (037 ~3:09; 038 ~39:59): no AM trade on a Fed chair 10:00 testimony day (calendar.FED_CHAIR, unverified)
    skip_auction_am: bool = False        # N5.6 (cc10_008 ~7:29): avoid the AM on Treasury auction days (calendar.is_auction_day, approximate)
    # M9 / M9.1 news Judas. NOTE (main engine only): the news / FOMC Judas, side filters (or_bias, or_wide, pm_continue_am), or_no_entry / or_deep,
    # macro gates and fomc_observe / fomc_only_am act in the main engine's scan loop; the Silver Bullet and Ma Deuce ignore them.
    news_judas: str = "off"              # M9 / M9.1 (064 ~52:12; 073 ~10:42): the first run of a pre-release pool after the release is
                                         # the losing side: "block" = that direction is closed, "wait" = also no entry before a run
    news_judas_ref_min: int = 60         # [our interpretation] the pre-release reference pools = the high / low of this many minutes
    # T4 / D1 opening range
    or_no_entry: bool = False            # T4 / D1 (031 ~4:52; 044 ~4:54): AM orders may be armed in the OR but fill from or_end
                                         # (the pending expiry counts from then)
    or_end: int = 600                    # the OR no-entry end (600 = 10:00; the CC OR runs to 630)
    or_no_entry_news1000: bool = False   # D1: also apply it on 10:00-release days (the release gate already holds those)
    or_deep: bool = False                # T4 (034; 041; 053 ~10:03): the exception - a fill inside or_deep_win with the entry deep in
                                         # discount of the prior day's range is allowed
    or_deep_win: tuple = (577, 586)      # 09:37-09:46
    or_deep_pd: float = 0.25             # D1: "deep" = the entry within this fraction of the prior RTH range from its low (high)
    or_bias: str = "off"                 # T4 (042 ~4:29): the OR's delivery gives the bias: "judas" (the first OR extreme was the
                                         # Judas -> the other way), "close" (the OR close vs its midpoint)
    or_bias_filter: bool = True          # or_bias: True = only that side after the OR, False = a tag
    or_wide: bool = False                # T4 (cc10_010 ~3:07-7:05): a wide OR gets its opposite end run - trade toward the far end
    or_wide_adr: float = 0.5             # wide = the OR range >= this x ADR5
    or_wide_end: int = 630               # the CC OR (09:30-10:30)
    # T5 / Ep01.10 / Ep06.1 session windows
    pre_0820: bool = False               # T5 / Ep01.10 (cc10_007): a PRE8 window 08:20 .. the AM start, skipped on 08:30 release days
    am_from_0830: bool = False           # Ep01.10 (Ep 01; 044 ~55:47): the AM window opens at 08:30 (lock and snapshot at 08:30)
    ny_kz_futures: bool = False          # Ep06.1 (cc10_007 ~4:35): the futures NY kill zone 08:20-11:00 (PRE8 window on release days
                                         # too - the news gate holds those; futures only)
    london_kz: bool = False              # Ep06.1: a LON window london_kz_start .. 05:00 on the main model (futures only)
    london_kz_start: int = 120
    # T8 lunch
    lunch: bool = False                  # T8 (064 ~1:45:41): a lunch session (the AM family's model, the AM draw carried, its own slot)
    lunch_win: tuple = (710, 810)        # 11:50 (the lunch macro) - 13:30
    lunch_exit: int = 810                # a lunch trade is out by then (never held into the PM)
    pm_carry_draw: bool = False          # T8 (029 ~1:29:48; 031 ~1:04:22): the AM's undelivered draw is the PM's draw
    draw_done_skip: bool = False         # T8: the AM draw delivered = the day's objective - no lunch / PM entries
    # T9 PM session
    pm_skip_after: int = 0               # T9 (044 ~1:55:03): nothing traded by this minute (870 = 14:30) -> the PM is skipped
    pm_skip_lh: bool = False             # pm_skip_after also skips the last hour (default: the owner's last hour stays open)
    pm_bad_am_start: int = 0             # T9: after a losing AM the PM restarts here (825 = 13:45)
    pm_continue_am: str = "off"          # T9 (047 ~09:21): the PM generally continues the AM: "tag" / "filter"
    pm_ob_entry: str = "off"             # T9 (cc10_012 ~0:34-7:07): the PM move starts off an AM / lunch OB: "tag" / "require"
    # T7 / Ep07.8 macros (timing, never direction)
    macro_gate: bool = False             # T7: an order must be armed inside an ICT macro window
    macro_only: str = "off"              # Ep07.8: "0950" = only the 09:50-10:10 macro, "all" = any macro (as macro_gate)
    macro_by: str = "arm"                # "arm" = the order is armed inside the window, "start" = the sweep that began the run was
                                         # (009 ~18:24: the run only needs to start inside)
    macro_done_skip: bool = False        # T7 (030 ~18:26): a macro fails when the day's run is done - no entry then
    moc_htf_done: bool = False           # T7 (Ep 01; 030 ~20:06): the MOC macro does nothing when the run / HTF target is done
    run_done_adr: float = 1.0            # "the day's run is done": the day's range so far >= this x ADR5 (or the session draw delivered)

    def __post_init__(self):
        if self.unicorn_sides not in ("both", "long", "short"):
            raise ValueError(f"unicorn_sides {self.unicorn_sides!r}")
        if self.breaker_zone not in L.BREAKER_MODES:
            raise ValueError(f"breaker_zone {self.breaker_zone!r}")
        if self.breaker_mt_mode not in ("range", "body"):
            raise ValueError(f"breaker_mt_mode {self.breaker_mt_mode!r}")
        for name, ok in (("news_wait", ("range", "fixed", "off")), ("draw_lock", ("session", "off")),
                         ("draw_lock_neutral", ("skip", "both")), ("draw_lock_levels", ("frozen", "live")),
                         ("draw_lock_pick", ("nearest",)),
                         ("ob_entry", ("pre_break", "post_mss", "both")),
                         ("ob_entry_px", ("body_top", "mt", "range_top", "open", "high")), ("ob_arm", ("leave", "touch")),
                         ("ob_stop", ("mt", "ext")), ("risk_basis", ("fixed", "equity")),
                         ("price_frame", ("front_month", "back_adjusted", "raw")),
                         ("sloppy_mode", ("off", "stand_aside", "scalp")),
                         ("year_end", ("december", "long", "tag", "off")),
                         ("year_end_map", ("squaring", "with")), ("am_exit_mode", ("close", "tighten")),
                         ("sb_target_mode", ("draw", "fixed")), ("runner_htf_exit", ("", "15m", "30m", "1h")),
                         ("turtle_soup", ("", "2023", "cc_limit", "cc_1h_ob", "or60", "external")),
                         ("ts_entry", ("array", "level")), ("round_pool_from", ("session", "midnight")), ("ts_stop", ("array", "gap", "ext")),
                         ("stop_flip", ("off", "breaker", "smt")),
                         # levels_detectors
                         ("ipda_eq_day", ("off", "tag", "skip")), ("mss_ref", ("stl", "itl", "ltl", "parent", "origin", "origin_max")),
                         ("ipda_session", ("rth", "eth")),
                         ("mss_ref_fallback", ("lower", "highest", "none")),
                         ("pd_hl_session", ("rth", "eth")), ("matrix_days", ("bot", "ict")),
                         ("org_draw", ("off", "tag", "draw")), ("wick_session", ("rth", "eth")),
                         ("wick_react", ("off", "tag", "require")), ("gap_pool_edge", ("far", "ce")),
                         ("release_open_stop", ("", "open", "wick_ce")),
                         ("bias_open", ("midnight", "0830", "0930")),
                         ("breakaway", ("off", "tag", "hold", "next_fvg")),
                         ("breaker_cand_to", ("ext", "h")), ("breaker_time", ("off", "hl2", "all")),
                         ("breaker_entry", ("off", "fallback", "prefer", "classic")),
                         ("eq_pref", ("off", "rank", "require")),
                         ("imm_rebalance_disp", ("off", "or", "require")),
                         # setups_models
                         ("mss_on_side", ("off", "tag", "require")), ("mm_context", ("off", "tag", "require")),
                         ("three_drives", ("off", "tag", "require")), ("unicorn_entry", ("edge", "overlap")),
                         ("cc_swings", ("off", "breaker", "failure", "both")), ("ifvg_entry", ("edge", "ce")),
                         ("ote", ("off", "filter", "limit")), ("smt_pick", ("first", "leader", "laggard")),
                         ("news_profile", ("off", "tag", "require")), ("nfp_sd", ("off", "tag", "skip")),
                         ("candle_draw_bias", ("off", "daily", "weekly")),
                         ("ob_pre_gate", ("off", "cancel", "hold")), ("cc_profile", ("off", "tag", "gate"))):
            if getattr(self, name) not in ok:
                raise ValueError(f"{name} {getattr(self, name)!r}: expected one of {ok}")
        for name, ok in (("fomc_am", ("open", "recipe", "skip")), ("fomc_only_am", ("off", "tag", "scalp", "skip")),
                         ("fomc_observe", ("off", "defer", "judas")), ("pre_cpi", ("off", "small", "skip")),
                         ("news_judas", ("off", "block", "wait")), ("or_bias", ("off", "judas", "close")),
                         ("pm_continue_am", ("off", "tag", "filter")), ("pm_ob_entry", ("off", "tag", "require")),
                         ("macro_only", ("off", "0950", "all")), ("macro_by", ("arm", "start"))):   # news_calendar_times
            if getattr(self, name) not in ok:
                raise ValueError(f"{name} {getattr(self, name)!r}: expected one of {ok}")
        if (self.fomc_eve_risk <= 0 or self.pre_fomc_risk <= 0 or self.pre_cpi_risk <= 0 or self.or_deep_pd < 0
                or self.run_done_adr < 0 or self.or_wide_adr < 0 or self.news_judas_ref_min < 1):
            raise ValueError("news_calendar_times: risk multipliers > 0, fractions / ADR multiples >= 0, news_judas_ref_min >= 1")
        if self.london_kz and self.london_kz_start not in PRE_AT_MINUTES:
            raise ValueError("london_kz_start: only the minutes in PRE_AT_MINUTES have a precomputed overnight pool (DayCtx.pre_at)")
        if len(self.or_deep_win) != 2 or len(self.lunch_win) != 2 or self.lunch_win[0] >= self.lunch_win[1]:
            raise ValueError("or_deep_win / lunch_win: expected (start_minute, end_minute)")
        if self.lunch and self.lunch_win[0] < self.am[1]:
            raise ValueError(f"lunch_win {self.lunch_win}: the lunch session must start at or after the AM end {self.am[1]} "
                             "(its AM range is read from the bars before it)")
        bad = [x for x in self.htf_resist_src if x not in CF_SRC]       # review: validate here, not
        if bad:                                                          # as a KeyError mid-run
            raise ValueError(f"htf_resist_src {bad}: expected names from {tuple(CF_SRC)}")
        bad = [x for x in self.htf_resist_tfs if x not in CF_TFS]
        if bad or not self.htf_resist_tfs:
            raise ValueError(f"htf_resist_tfs {self.htf_resist_tfs!r}: expected a non-empty subset of {CF_TFS}")
        from .htf import FLIP_TRIGGERS
        if set(self.flip_triggers) - set(FLIP_TRIGGERS):
            raise ValueError(f"flip_triggers {self.flip_triggers!r}: expected from {FLIP_TRIGGERS} "
                             "(B8f = Params.stop_flip)")
        if self.stop_mode not in STOP_MODES:
            raise ValueError(f"stop_mode {self.stop_mode!r}: expected one of {STOP_MODES}")
        for name, ok in (("entry", ENTRY_MODES), ("sb_entry", ENTRY_MODES[:-1]), ("iofed_ref", ("c2_high", "tick", "q75")),
                         ("run_cancel", ("t1", "last", "off")), ("entry_order", ("limit", "stop_cc")),
                         ("add_order", ("limit", "market")), ("retrace_candle", ("off", "closed", "intrabar")),
                         ("ob_zone", ("", "range", "sensitive")), ("ob_cisd", ("off", "tag", "cancel")),
                         ("prop_zone", ("range", "body")), ("ob_entries", ("off", "fallback", "prefer")),
                         ("add_points", ("top", "ce", "q75")), ("add_cut", ("", "eq", "leg75")), ("add_cutoff_read", ("covered", "progress")),
                         ("add_cut_ref", ("range", "leg")), ("add_on", ("", "retest", "breaker")),
                         ("ob_entry_px", ("body_top", "mt", "range_top", "open", "high")),
                         ("trail_ref", ("gap", "body"))):
            if getattr(self, name) not in ok:
                raise ValueError(f"{name} {getattr(self, name)!r}: expected one of {ok}")
        for name, ok in (("irl_entries", ("fvg", "ob", "void")),
                         ("size_rules", ("news_eve", "fomc_week", "august", "against_macro", "decoupled", "low_prob")),
                         ("size_up_rules", ("bpr", "htf_target")), ("low_prob_tests", ("against_bias", "no_htf", "sloppy")),
                         ("add_arrays", ("vi", "ifvg", "ob", "breaker", "htf_fvg"))):
            bad = set(getattr(self, name)) - set(ok)
            if bad:
                raise ValueError(f"{name} {sorted(bad)}: expected from {ok}")
        if len(self.entry_ladder_fracs) < 2 or abs(sum(self.entry_ladder_fracs) - 1.0) > 1e-6:
            raise ValueError(f"entry_ladder_fracs {self.entry_ladder_fracs!r}: expected >= 2 fractions summing to 1")
        if self.fvg_pick not in ("last", "first", "2022"):
            raise ValueError(f"fvg_pick {self.fvg_pick!r}")
        bad = set(self.entry_arrays) - {"ob", "breaker", "ote", "wick_ce", "vi", "reclaimed_ob"}
        if bad:
            raise ValueError(f"entry_arrays {sorted(bad)}")
        bad = [x for x in self.nest_tfs if x not in CF_TFS]
        if bad:
            raise ValueError(f"nest_tfs {bad}: expected names from {CF_TFS}")
        bad = set(self.fvg_state_filter) - {"open", "repriced", "rebalanced"}
        if bad:
            raise ValueError(f"fvg_state_filter {sorted(bad)}: expected open / repriced / rebalanced")
        known = {"big_prev", "chop", "nfp_week", "premium_run", "fomc_week", "inside_bisi"}
        if set(self.sloppy_tests) - known:
            raise ValueError(f"sloppy_tests {sorted(set(self.sloppy_tests) - known)}: expected from {sorted(known)}")
        # review fixes (levels_detectors)
        if not 570 < self.am_range_end <= 810:     # L1: past 13:30 the PM would read later bars (look-ahead)
            raise ValueError(f"am_range_end {self.am_range_end}: expected 570 < am_range_end <= 810")
        bad = [x for x in self.daily_level_array_tfs if x not in CF_TFS]
        if bad or not self.daily_level_array_tfs:
            raise ValueError(f"daily_level_array_tfs {self.daily_level_array_tfs!r}: expected a non-empty "
                             f"subset of {CF_TFS}")
        # package targets_partials: aliases (umbrella names) and validation
        if self.wick_ce_partial:
            self.wick_partials = True
        if self.sd_neg05_first:
            self.sd_half_partial = True
        if self.rej_targets and self.rb_targets == "off":
            self.rb_targets = "ladder"
        if self.proj_measuring:
            self.measuring_target = True
        if self.wick_week:
            self.wick_weekly = True
        if self.wick_daily_src:
            self.wick_session = self.wick_daily_src
        for name, ok in (("htf_resist_mode", ("bump", "cap", "split")), ("rb_targets", ("off", "ladder", "replace")),
                         ("resistance_mode", ("off", "low_full", "high_run", "both")),
                         ("measuring_anchor", ("far", "near", "ce", "dup")), ("mm_anchor", ("leg", "ref")),
                         ("wick_read", ("off", "exit")), ("wick_session", ("rth", "eth")),
                         ("sd_anchor", ("leg", "sweep_leg", "broken", "downleg", "fulcrum", "london", "manip", "multi")),
                         ("mgmt", ("ladder", "t1t2", "unit"))):
            if getattr(self, name) not in ok:
                raise ValueError(f"{name} {getattr(self, name)!r}: expected one of {ok}")
        for name, ok in (("matrix_targets", ("breaker", "mitigation", "rejection")),
                         ("target_hygiene", ("arrays", "htf", "wick")),
                         ("target_order", ("eq", "daily", "vi", "pool", "array")),
                         ("wick_partial_tfs", ("D", "4h", "1h", "30m", "15m")), ("wick_tfs", ("D", "4h", "1h", "30m", "15m"))):
            bad = set(getattr(self, name)) - set(ok)
            if bad:
                raise ValueError(f"{name} {sorted(bad)}: expected from {ok}")
        bad = [k for k in self.sd_levels if not (0.5 - 1e-9 <= k <= 4.5 + 1e-9) or abs(k * 2 - round(k * 2)) > 1e-9]
        if bad:                                     # L12 / D23: standard deviations 0.5 .. 4.5 in half steps
            raise ValueError(f"sd_levels {bad}: expected multiples of 0.5 from 0.5 to 4.5")
        bad = [x for x in self.htf_resist_cap_tfs if x not in CF_TFS]
        if bad:
            raise ValueError(f"htf_resist_cap_tfs {bad}: expected names from {CF_TFS}")
        if self.capture_frac and not 0.3 <= self.capture_frac <= 1.0:
            raise ValueError(f"capture_frac {self.capture_frac}: expected 0 (off) or 0.3 .. 1.0")
        if self.tgif_zone and not (0 < self.tgif_cap <= self.tgif_stand_down < 1):
            raise ValueError("tgif_cap must be > 0 and <= tgif_stand_down < 1")
        if self.sd_close_window and (len(self.sd_close_window) != 2 or self.sd_close_window[0] >= self.sd_close_window[1]):
            raise ValueError(f"sd_close_window {self.sd_close_window!r}: expected (start_minute, end_minute)")
        if self.wick_partial_min_pts < 0 or not 0 < self.partial_extra_frac <= 0.5 or not 0 < self.partial_extra_cap <= 0.9:
            raise ValueError("partial_extra_frac must be in (0, 0.5], partial_extra_cap in (0, 0.9]")
        # package management_exits: aliases and validation
        if self.pool_size_rank:
            self.pool_rank = True
        if self.prop_exit:
            self.prop_mt_exit = True
        if self.smt_exit_against:
            self.smt_bank_against_frac = 1.0
        for name, ok in (("be_on", ("expansion", "t1", "after_mss", "stall", "pool", "off")),
                         ("extras_be_on", ("t1", "follow")),
                         ("ladder_trail", ("fvg", "hit", "prior", "off", "measuring", "breakaway")),
                         ("trade_type", ("session", "day")), ("day_stop", ("open", "wick_ce")),
                         ("fvg_abort_mode", ("rule", "legacy")), ("session_fail_mode", ("trades", "arrays")),
                         ("offside_level", ("open", "wick_ce")), ("time_stop_ref", ("pts", "leg_high", "array_far")),
                         ("obj_source", ("draw", "htf_ce")), ("reentry_risk", ("budget", "loss")),
                         ("add_mode", ("fvg", "downclose")), ("smt_bias", ("off", "tag", "filter"))):
            if getattr(self, name) not in ok:
                raise ValueError(f"{name} {getattr(self, name)!r}: expected one of {ok}")
        bad = set(self.pd3_list) - {"fvg", "vi", "ob", "breaker"}
        if bad:
            raise ValueError(f"pd3_list {sorted(bad)}: expected from ('fvg', 'vi', 'ob', 'breaker')")
        if self.stops_passes < 1:
            raise ValueError(f"stops_passes {self.stops_passes}: expected >= 1")
        if (self.pd3_n < 1 or not 0 < self.time_stop_frac <= 1 or not 0 < self.far_edge_frac <= 1
                or not 0 < self.pd3_half_frac < 1 or not 0 < self.am_bulk_frac <= 1 or self.fvg_abort_tf < 1
                or not 0 <= self.add_pd_level <= 1 or self.trail_after < 1 or self.be_stall_bars < 1
                or self.session_stop_after_fails < 0 or self.meander_bars < 0 or self.far_edge_min < 0):
            raise ValueError("management_exits: pd3_n / trail_after / be_stall_bars >= 1, fractions in (0, 1], "
                             "add_pd_level in [0, 1], counts >= 0")
        inert = []                                  # switches the current draw_lock / vi_arrays make inert
        if self.vi_news_draw and self.draw_lock != "session":
            inert.append("vi_news_draw acts only in the #9 lock (draw_lock='session')")
        if (self.vi_news_draw or self.vi_htf_draw) and not self.vi_arrays:
            inert.append("vi_news_draw / vi_htf_draw need vi_arrays=True (the HTF VI rows)")
        if self.eq_pref != "off" and self.draw_lock == "session":
            inert.append("eq_pref: the rel-eq DRAW preference acts only with draw_lock='off' (the sweep "
                         "pick still applies)")
        if self.daily_vi_targets and not self.vi_arrays:
            inert.append("daily_vi_targets needs vi_arrays=True (the confluence VI rows)")
        if self.stop_tick_pts > 0 and self.stop_pad_ticks <= 0 and self.stop_buffer != 0.01:
            inert.append("stop_buffer is ignored while stop_tick_pts > 0 (the one-tick pad is the default): "
                         "set stop_tick_pts=0 to use stop_buffer, or stop_pad_ticks=N")
        if inert:
            warnings.warn("inert switches: " + "; ".join(inert), stacklevel=3)

    # --- package entries_stops_sizing helpers --------------------------------------------------
    @property
    def fomc_day_stop(self) -> bool:
        """N3 / N3.5: a loss on an FOMC day ends the day - unless X13b `reentry_fomc_ok` explicitly allows a re-entry there."""
        return bool(self.fomc_no_reentry and not self.reentry_fomc_ok)

    @property
    def am_win(self) -> tuple:
        """The AM entry window: `am`, opening at 08:30 with am_from_0830 (Ep01.10)."""
        return (510 if self.am_from_0830 else self.am[0], self.am[1])

    @property
    def tick(self) -> float:
        """One tick in price units (E3 tick_pts x es_pt)."""
        return self.tick_pts * self.es_pt

    @property
    def pad(self) -> float:
        """The stop pad in price units: E6f stop_pad_ticks, else Ep08.17 stop_tick_pts (one tick,
        default), else the old stop_buffer."""
        if self.stop_pad_ticks > 0:
            return self.stop_pad_ticks * self.tick
        if self.stop_tick_pts > 0:
            return self.stop_tick_pts * self.es_pt
        return self.stop_buffer

    @property
    def mohawk(self) -> float:
        """A4: the extra distance (price units) a structural stop / trail keeps beyond its level."""
        return self.mohawk_ticks * self.tick

    @property
    def trail_pad(self) -> float:
        if self.trail_pad_pts > 0:             # X5a: an explicit trail pad (0.25 = one tick)
            return self.trail_pad_pts * self.es_pt
        return self.pad + self.mohawk


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


def _first_units(p: "Params", eq: float, risk: float, entry: float, risk_mult: float = 1.0,
                 extra_cap: float = 0.0) -> int:
    """Owner #12: the first unit risks risk_pct (1.2%) of equity, never more than the total cap.
    extra_cap (E9 size_up_cap_pct x equity) raises the cap for an order a size-up rule fired on."""
    return _lots(min(risk_mult * _risk_budget(p, eq) / risk, (_total_cap(p, eq) + extra_cap) / risk,
                     p.max_notional / abs(entry)), p.lot)


def adr5(days: list) -> float | None:
    """Average daily range of 5 sessions (shared helper: N8, X16a, L16, X10d, X14b, #10)."""
    if len(days) < 5:
        return None
    return float(np.mean([float(x.high.max() - x.low.min()) for x in days[-5:]]))


_adr5 = adr5


PRE_AT_MINUTES = (60, 120, 180, 240, 300, 420, 500, 510, 540)   # session starts with a precomputed overnight range (DayCtx.pre_at)


def _lots(x: float, lot: int) -> int:
    return int(x // lot) * lot


def blocked(d: date, session: str, p: "Params | None" = None, t: int = 0) -> str | None:
    """Day-type rule that blocks this session (at minute t), or None. The NFP-week rules are relative
    to the week's ACTUAL jobs date (calendar.nfp_date): 2025-07-03 was a Thursday, so the day before
    it is the Wednesday (the old code assumed a Friday: Thursday = the day before, Wednesday PM = two
    days before). news_calendar_times adds the FOMC / CPI / chair / auction day rules (newscal)."""
    tags = events(d)
    if "jobs" in tags and not (p is not None and p.nfp_day):
        return "nfp_day"
    # [our interpretation] The NFP-week blocks apply only when the week's jobs date is a Thursday or Friday (nfp_shift);
    # a jobs date on Mon-Wed (2025-12-16, 2026-02-11: shutdown shifts) has no Thu / Fri block, the day after a
    # Thursday NFP is not blocked, and the shutdown-delayed Thursday 2025-11-20 counts as a normal Thursday NFP.
    sh = _calendar.nfp_shift(d)
    nfp = _calendar.nfp_date(d)
    week_block = p is None or p.nfp_week_block
    if sh >= 0 and week_block and d < nfp:
        w = d.weekday() + sh                         # the day's place as if the NFP were on a Friday
        if w >= 3 and not (p is not None and p.nfp_thu and w == 3):
            return "nfp_week_thu_fri"
        if w == 2 and session == "PM":
            return "nfp_week_wed_pm"
    if "fomc" in tags and session == "PM":
        frm = p.fomc_pm_from if p is not None else 885
        if p is not None and p.fomc_judas:
            frm = min(frm, p.fomc_judas_end)         # M9.2: the real move starts at 14:30
        if p is not None and p.fomc_pm_block_from and t < p.fomc_pm_block_from:
            pass                                     # N3.1: open before the release (flat by fomc_flat)
        elif not (frm and t >= frm) and not (p is not None and p.fomc_observe != "off" and t >= 840):
            return "fomc_pm"                         # (fomc_observe scans from 14:00; the order is held)
    if p is not None and p.skip_cpi and "cpi" in tags:
        return "cpi"
    if p is not None and p.skip_monday and d.weekday() == 0:
        mon = d - timedelta(days=d.weekday())
        week = [mon + timedelta(days=k) for k in range(5)]
        if not _calendar.nfp_date(d) and not any("fomc" in events(x) for x in week):
            return "monday"
    if p is not None:
        return _NC.calendar_block(d, session, p, t)
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
    lock_capped: bool = False      # #7 x #9: the locked draw lay beyond the HTF cap - exit at the cap
    sloppy: str = ""               # #10: sloppy-day reasons active at arming (tag in every mode)
    news_wait_min_actual: float | None = None   # #4: minutes from the release to the range's completion
    news_pd: bool | None = None    # #4: entry in the news range's discount (long) / premium (short)
    entry_risk_pct: float | None = None   # #12: open risk at the fill / equity
    peak_risk_pct: float | None = None    # #12: largest open risk incl. adds / equity
    contract: int | None = None    # #13: instrument id at the fill (databento meta)
    adj: float = 0.0               # #13: back-adjustment at the fill (real = engine - adj)
    roll_day: bool = False         # N7.5 hook: a contract roll from the prior 18:00 through the day
    # package levels_detectors
    lv_tags: str = ""              # "|"-joined: breakaway, ipda_eq, org_draw / org_breakaway / org_half /
                                   # org_q_hold, wick_react, gap_stop, release_open, bpr_cap, no_draw,
                                   # open_to_pdh / open_to_pdl (A7 daily), draw_<override>
    fvg_state: str = ""            # A5: the entry gap's state at arming (open / repriced / rebalanced)
    imm_rebal: bool = False        # A7: an immediate rebalance printed in the leg (sweep -> arming)
    # package setups_models (Ep03.11 smt_pick / reporting): the sweep extreme and the leg high
    ext_px: float | None = None
    leg_hi_px: float | None = None
    capture: float | None = None   # targets_partials X3h: (avg exit - avg entry) / (best high - avg entry)
    rungs: str = ""                # targets_partials: the ladder at the fill, "level:kind:share|..." (engine frame)
    # package management_exits
    final_hit: bool = False        # Ep04.13: the trade's last ladder level was hit (every rung taken)
    slow_chop: bool = False        # X14b: the day was chop / slow at the fill
    reentry: bool = False          # X13b / D18: the trade is a re-entry after a stop-out
    stop_day: str = ""             # what ended the day when this trade closed (obj_stop / done_target / chop_win / win)
    # package news_calendar_times
    macro_wins: str = ""           # T7: every ICT macro window the order was armed in, "HHMM|..." (macro_win keeps the first)
    news_tags: str = ""            # the day's news tags: nfp, nfp_week, fomc, fomc_only, fomc_eve, fomc_after, cpi, pre_cpi,
                                   # two_driver, fed_chair, auction, claims, minutes (newscal.day_tags)

    REAL_FIELDS = ("entry", "stop", "t1", "t2", "draw_px", "bz_top", "bz_bottom", "bz_mt",
                   "resist_lo", "resist_hi", "ext_px", "leg_hi_px")

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

    def __init__(self, sign, o, h, l, c, n, min_gap: float = 0.0, c2_dir: bool = False,
                 vi_min_gap: float = 0.0, mit_legacy: bool = False):
        self.sign = sign
        if sign > 0:
            self.o, self.h, self.l, self.c = o, h, l, c
        else:
            self.o, self.h, self.l, self.c = -o, -l, -h, -c
        self.ph, self.pl = L.pivots(self.h, self.l, n)
        self.c2_dir = c2_dir                  # A5 fvg_c2_dir (levels_detectors)
        self.vi_min_gap = vi_min_gap          # A9 vi_min_gap_pts (price units)
        self.mit_legacy = mit_legacy          # A15 mit_legacy_order (review fix: a Params switch)
        self.gaps = [z for z in L.fvgs(self.h, self.l, self.o, self.c, c2_dir)
                     if z.kind == "bull" and z.top - z.bottom >= min_gap]
        self.min_gap = min_gap
        self.sweep = None
        self.n = n
        self._ifvg = self._opp = self._mit = self._prop = None
        self._lz = {}                         # levels_detectors lazily built arrays

    def _lazy(self, key, fn):
        if key not in self._lz:
            self._lz[key] = fn()
        return self._lz[key]

    def tiers(self):
        """A1: {"stl"|"itl"|"ltl": (highs, lows)} in side space."""
        return self._lazy("tiers", lambda: L.swing_tiers(self.h, self.l, self.n))

    def vis(self, kind: str = "bull"):
        """A9 volume imbalances of one kind in side space ("bull" = support, "bear" = above)."""
        return self._lazy("vi_" + kind, lambda: [z for z in L.volume_imbalances(self.o, self.h, self.l, self.c,
                                                                                  self.vi_min_gap) if z.kind == kind])

    def bprs(self, max_gap: int = 0):
        """A11 balanced price ranges (both kinds), side space."""
        return self._lazy(("bpr", max_gap), lambda: L.balanced_ranges(self.h, self.l, max_gap, self.o, self.c,
                                                                       self.c2_dir))   # review fix: A5 c2 rule

    def irs(self, tick: float):
        """A7 immediate rebalances (bull kind, side space): candle indices."""
        return self._lazy(("ir", tick), lambda: [k for k, kd in L.immediate_rebalances(self.o, self.h, self.l, self.c, tick)
                                                 if kd == "bull"])

    def opp_mits(self):
        """A15 opposing (bearish, side space) mitigation blocks - targets above a long."""
        return self._lazy("opp_mit", lambda: [z for z in L.mitigation_blocks(self.o, self.h, self.l, self.c, self.n,
                                                                             self.mit_legacy) if z.kind == "bear"])

    def implied(self):
        """A24.1 implied FVGs (bull kind, side space; setups_models implied_fvg)."""
        return self._lazy("implied", lambda: [z for z in L.implied_fvgs(self.o, self.h, self.l, self.c)
                                              if z.kind == "bull" and z.top - z.bottom >= self.min_gap])

    # lazily built arrays (only the switches that use them pay for them)
    def ifvgs(self):
        if self._ifvg is None:
            self._ifvg = [z for z in L.inversion_fvgs(self.h, self.l, self.c, self.min_gap) if z.kind == "bull"]
        return self._ifvg

    def opposing(self):
        """Bearish FVGs and voids (resistance above, in side terms), for targets."""
        if self._opp is None:
            self._opp = [z for z in L.fvgs(self.h, self.l, self.o, self.c, self.c2_dir) + L.voids(self.h, self.l)
                         if z.kind == "bear" and z.top - z.bottom >= self.min_gap]
        return self._opp

    def mitigations(self):
        if self._mit is None:
            self._mit = [z for z in L.mitigation_blocks(self.o, self.h, self.l, self.c, self.n, self.mit_legacy)
                         if z.kind == "bull"]
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
        for z in L.fvgs(hh, ll, o, c, self.c2_dir):
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
        for m in PRE_AT_MINUTES:
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
        self.nwog_today = False                # review fix: True when the last NWOG is today's (known at 09:30)
        for a, b in zip(hist[-21:], hist[-20:] + [df]):
            if (b.index[0].date() - a.index[-1].date()).days >= 3 or b.index[0].weekday() < a.index[-1].weekday():
                rth = b[(b.index.hour * 60 + b.index.minute) >= 570]
                if len(rth):
                    self.nwog.append((float(a.close.iloc[-1]), float(rth.open.iloc[0])))
                    self.nwog_today = b is df
                else:
                    self.nwog_today = False
        self.nwog_prev = (self.nwog[:-1] if self.nwog_today else self.nwog)[-4:]   # before today's 09:30
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


OPEN_MIN = {"midnight": 0, "0830": 510, "0930": 570, "1330": 810}


def _htf_array(cf: list, p) -> bool:
    """L2 daily_level_needs_array: a confluence timeframe from daily_level_array_tfs in `cf`."""
    return any(x in p.daily_level_array_tfs for x in cf)


def _nwogs(ctx, i: int | None) -> list:
    """ctx.nwog known at bar i (review fix, found by the pre-09:30 look-ahead test): a Monday's own
    NWOG (Friday close -> today's 09:30 open) only from the 09:30 bar; i=None = a pre-09:30 lock."""
    if getattr(ctx, "nwog_today", False) and ctx.nwog and (i is None or i < _idx_at(ctx, 570)):
        return ctx.nwog_prev                   # the 4 prior NWOGs (not the 3 left after slicing)
    return ctx.nwog


def _open_known(ctx, name: str, i: int) -> float | None:
    """Review fix (T2 bias_open look-ahead): today's `name` open only once its bar is in (index
    <= i, as release_open's k830 <= i); ctx.opens is built from the whole day's frame."""
    if name not in ctx.opens or _idx_at(ctx, OPEN_MIN[name]) > i:
        return None
    return ctx.opens[name]


ROUND_STEP = {"ES": 50.0, "MES": 50.0, "SPX": 50.0, "NQ": 100.0, "MNQ": 100.0, "NDX": 100.0,
              "YM": 500.0, "MYM": 500.0}


def _round_anchor(ctx, i: int) -> int:
    """#13 round_pool_from: the first bar whose trading can take a round handle at bar i."""
    if getattr(ctx, "round_from", "session") == "midnight":
        return ctx.start
    t = ctx.t[i] if i < len(ctx.t) else ctx.t[-1]
    return _idx_at(ctx, 810) if t >= 810 else (_idx_at(ctx, 570) if t >= 570 else ctx.start)


def _round_levels(ctx, sd, i: int, beyond: bool, n: int = 1) -> list[float]:
    """#13 / Ep02.2: untaken round handles in side space. beyond=False: the nearest round level
    below the low so far (sell-side, bars a..i-1; no bar yet -> below the last close);
    beyond=True: the next n above the high through bar i (buy-side targets). a = the session's
    first bar (round_pool_from="session") or midnight. Real (front-month) level R maps to the
    engine at R + adj of the latest closed bar (look-ahead free)."""
    st = getattr(ctx, "round_step", 0.0)
    if not st or getattr(ctx, "adj", None) is None:
        return []
    if i < ctx.start:
        return []
    a = _round_anchor(ctx, i)
    if beyond:
        ext, adj = sd.h[a:i + 1].max(), float(ctx.adj[i])
    else:
        if i - 1 < ctx.start:
            return []
        ext = sd.l[a:i].min() if i - 1 >= a else sd.c[i - 1]
        adj = float(ctx.adj[i - 1])
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
    if p.matrix_days == "ict":              # Ep08.10: today (pool_today_hl) + yesterday + the day before
        pdk = pdk[:2]
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
    ae = min(810, getattr(ctx, "am_end", 810))   # L1 (review fix): a pool from am_range_end itself
    if ctx.t[i] >= ae and ctx.am_hl:        # (13:30 old / 12:00); Params checks 570 < end <= 810
        pools.append((sd.x(ctx.am_hl[0] if sd.sign > 0 else ctx.am_hl[1]), at(ae)))
    if getattr(ctx, "cur_session", "") == "LUNCH" and getattr(ctx, "am_lunch_hl", None) is not None:
        pools.append((sd.x(ctx.am_lunch_hl[0] if sd.sign > 0 else ctx.am_lunch_hl[1]),     # T8: the AM range, complete
                      at(getattr(ctx, "am_lunch_end", 660))))                                # before the lunch session
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
    pools += _lv_target_pools(ctx, sd, i, p)                           # levels_detectors pools
    if p.close_draw:                        # Ep07.1: unrealized prior closes + last week's close as pools
        pools += _TP.close_pools(ctx, sd, i, p, above)
    eqs = {round(v, 9) for v in eq} if p.eq_pref != "off" else set()   # Ep06.7: kind "pool_eq"
    pk = lambda v: "pool_eq" if round(v, 9) in eqs else "pool"
    tk = _tick(p)                           # A2: spent only once traded 1 tick through
    if p.seen_from_created:
        lv = []
        for v, cr in pools:
            if cr is None or ext_i is None or ext_i <= max(cr, ctx.start):
                lv.append((v, pk(v)))
            elif not _spent_up(sd.h[max(cr, ctx.start):ext_i].max(), v, tk):
                lv.append((v, pk(v)))
    else:                                   # the old rule: anything above today's high so far
        seen = sd.h[ctx.start:ext_i].max() if ext_i is not None and ext_i > ctx.start else -np.inf
        lv = [(v, pk(v)) for v, _ in pools if not _spent_up(seen, v, tk)]
    if getattr(ctx, "gaps", None) is not None:
        for kind, hi, lo, ce in ctx.gaps:
            if p.weekly_gap_ce_only and kind == "nwog":      # L9 (061 ~2:30:15): the CE is enough, the far edge a ringer
                lv.append((sd.x(ce), "array"))
            else:
                lv += [(sd.x(hi), "array"), (sd.x(ce), "array"), (sd.x(lo), "array")]
            if p.gap_quarters or (p.nwog_quarters and kind == "nwog"):   # L5 / D21 quarters
                lv += [(sd.x(lo + 0.25 * (hi - lo)), "array"), (sd.x(lo + 0.75 * (hi - lo)), "array")]
    else:
        for a, b in _nwogs(ctx, i):
            if p.weekly_gap_ce_only:        # L9: the CE only
                lv.append((sd.x((a + b) / 2), "array"))
            else:
                lv += [(sd.x(a), "array"), (sd.x(b), "array")]
                if p.monday_ce:             # D21: the Monday-gap CE
                    lv.append((sd.x((a + b) / 2), "array"))
            if p.nwog_quarters or p.gap_quarters:
                lv += [(sd.x(a + 0.25 * (b - a)), "array"), (sd.x(a + 0.75 * (b - a)), "array")]
    lv += _lv_target_arrays(ctx, sd, i, p)                             # levels_detectors arrays
    if p.org_days:
        orgs = ctx.org[:-1] if (pre_open and ctx.org_today) else ctx.org
        for a, b in orgs[-p.org_days:]:
            lv += [(sd.x(a + q * (b - a)), "array") for q in (0.0, 0.25, 0.5, 0.75, 1.0)]
    if p.wick_levels:
        wk_ = "wick" if p.wick_read != "off" else "array"       # A23 wick_read: the rung is told apart
        lv.append((sd.x(ctx.wick["upper"] if sd.sign > 0 else ctx.wick["lower"]), wk_))
        for w in getattr(ctx, "wicks", [])[1:] + getattr(ctx, "wick_wk", []):   # L10 wick_days / weekly
            lv.append((sd.x(w["upper"] if sd.sign > 0 else w["lower"]), wk_))
        if p.wick_both:                     # L10: the other wick's CE too (any beyond price)
            for w in getattr(ctx, "wicks", [ctx.wick]) + getattr(ctx, "wick_wk", []):
                lv.append((sd.x(w["lower"] if sd.sign > 0 else w["upper"]), wk_))
    if p.sd_targets and leg is not None and not _TP.sd_active(p):
        lo, hi = leg
        sds = [hi + k * (hi - lo) for k in p.sd_levels]
        if p.sd_first_beyond:              # only the first SD level beyond the nearest pool (014/030)
            pool = min((v for v, kind in lv if kind == "pool" and v > above), default=None)
            sds = [min((x for x in sds if x > pool), default=None)] if pool is not None else []
        lv += [(x, "sd") for x in sds if x is not None]
    out = []
    for v, kind in sorted(x for x in set(lv) if x[0] > above):   # merge levels within ~1 ES point
        if not out or v - out[-1][0] > p.es_pt:
            out.append((v, kind))
        elif kind == "pool_eq" and out[-1][1] == "pool":           # Ep06.7: keep the rel-eq kind
            out[-1] = (out[-1][0], "pool_eq")
    return out


def _eq_levels(sd: Side, i: int, tol: float, lows: bool, p: "Params | None" = None) -> list[float]:
    """Relative equal highs (lows) from swings confirmed by bar i and not yet traded through.
    levels_detectors A3: `eq_bodies` clusters the swing candles' BODY extremes (nearly level bodies
    count even if the wicks differ, cc05_003 ~1:07:26) and draws the line at the most extreme wick
    of the cluster (the lower of the lows, 038 ~43:43); `eq_rank` orders the clusters by touches
    (more = stronger), then by spread (smoother = stronger). Without either: the old list."""
    piv = sd.pl if lows else sd.ph
    bodies = p is not None and p.eq_bodies
    rank = p is not None and p.eq_rank
    out, wick, bar = [], [], []
    bt = np.minimum(sd.o, sd.c) if lows else np.maximum(sd.o, sd.c)
    for q in piv:
        if q.known > i:
            break
        if bodies:                    # untaken by BODIES (a later wick may poke past a wick)
            b = float(bt[q.i])
            after = bt[q.i + 1:i + 1]
            if len(after) == 0 or (after.min() >= b if lows else after.max() <= b):
                out.append(-b if lows else b)
                wick.append(-q.price if lows else q.price)
                bar.append(q.i)
            continue
        after = sd.l[q.i + 1:i + 1] if lows else sd.h[q.i + 1:i + 1]
        if (len(after) == 0) or (after.min() > q.price if lows else after.max() < q.price):
            out.append(-q.price if lows else q.price)
            wick.append(-q.price if lows else q.price)
            bar.append(q.i)
    if not bodies and not rank:
        lv = L.equal_levels(out, tol)
        return [-v for v in lv] if lows else lv
    cl = []
    for idx in L.equal_clusters(out, tol):
        lvl = max(wick[k] for k in idx)                   # the most extreme wick (side of the pool)
        last = max(bar[k] for k in idx)
        seg = (-sd.l[last + 1:i + 1]) if lows else sd.h[last + 1:i + 1]
        if bodies and len(seg) and seg.max() >= lvl:
            continue                                      # the cluster's line was traded through
        cl.append((-len(idx), max(out[k] for k in idx) - min(out[k] for k in idx), -lvl, lvl))
    if rank:
        cl.sort()                                         # touches desc, spread asc
    else:
        cl.sort(key=lambda x: x[3])
    lv = [x[3] for x in cl]
    return [-v for v in lv] if lows else lv


# --- package levels_detectors helpers (rule_coverage.md section 3) ---------------------------

POOL_KINDS = ("pool", "pool_eq")      # Ep06.7: rel-eq pools keep the pool exit rules


def _tick(p) -> float:
    """A2: the booking threshold in price units (sweep_ticks x one ES tick)."""
    return p.sweep_ticks * 0.25 * p.es_pt


def _thru(x: float, v: float, tk: float) -> bool:
    """A2 (042 ~59:04): a low x (side space) books the sell-side level v - at least one tick tk
    through it; tk = 0 keeps the old rule (any print below)."""
    return bool(x <= v - tk + 1e-9) if tk > 0 else bool(x < v)


def _spent_up(seen: float, v: float, tk: float) -> bool:
    """A2: a buy-side pool v (side space) is spent once the high `seen` traded tk through it;
    tk = 0 keeps the old rule (seen >= v)."""
    return bool(seen >= v + tk - 1e-9) if tk > 0 else bool(seen >= v)


def _drop_near_exact(lv: list, tk: float) -> list:
    """Ep08.1 daily_fvg_exact (review fix): drop the non-pool levels within a tick `tk` of an
    "exact" level, so the htf_targets copy of the same daily FVG edge (kind "array", exit
    exit_before_pts early) cannot be the rung hit first - the edge is hit to the tick."""
    ex = [v for v, k in lv if k == "exact"]
    if not ex:
        return lv
    return [(v, k) for v, k in lv if k == "exact" or k in POOL_KINDS
            or not any(abs(v - e) <= tk + 1e-9 for e in ex)]


def _exit_px(v: float, kind: str, p) -> float:
    """The exit price of a target level (side space): just beyond a pool (exit_mode "split"),
    exactly at an "exact" level (Ep08.1 daily_fvg_exact), else exit_before_pts in front of it."""
    if p.exit_mode == "split" and kind in POOL_KINDS:
        return v + p.pool_beyond_pts * p.es_pt
    if kind == "exact":
        return v
    return v - p.exit_before_pts * p.es_pt


def _sess_start(ctx, i: int) -> int | None:
    """Index of the current session's first bar: 13:30 (PM) or 09:30 (AM); None before 09:30."""
    t = ctx.t[i]
    m = 810 if t >= 810 else (570 if t >= 570 else None)
    return None if m is None else _idx_at(ctx, m)


def _hl(frame) -> tuple:
    return (float(frame.open.iloc[0]), float(frame.high.max()), float(frame.low.min()), float(frame.close.iloc[-1]))


def _extra_levels(ctx, df: pd.DataFrame, hist: list, p: "Params", eth: dict | None = None,
                  closes: dict | None = None) -> None:
    """levels_detectors: pools and arrays for the day (each used only from the bar it is known).
    B21 IPDA 20/40/60; L2/Ep08.10 ETH matrix; L3 ETH week/month and OR extra; L10 wick days /
    weekly / ETH wicks; L1 AM range end and the previous AM range; L7/D21 ORG history of
    max(org_days, 5) + 1 sessions; L8 vacuum blocks at the releases. `eth` = {date: (o, h, l, c)}
    of full sessions (backtest.prepare), read only for dates before today."""
    S = ctx.start
    ctx.hist = hist
    ctx.tk = _tick(p)
    tt = df.index.hour * 60 + df.index.minute
    dates = [x.index[0].date() for x in hist]
    ec = (lambda d: eth.get(d)) if eth else (lambda d: None)
    # B21 / L3: IPDA ranges, rolling from yesterday (day 1). Review fix: daily FULL-session candles
    # (ipda_session="eth": the eth dict, a date without one falls back to its RTH session)
    hl_ = lambda d, x: ((ec(d)[1], ec(d)[2]) if (p.ipda_session == "eth" and ec(d) is not None)
                        else (float(x.high.max()), float(x.low.min())))
    ctx.ipda_days = [hl_(d, x) for d, x in zip(dates, hist)]
    ctx.ipda = {}
    for n in (20, 40, 60):
        if len(hist) >= n:
            seg = ctx.ipda_days[-n:]
            ctx.ipda[n] = (max(x[0] for x in seg), min(x[1] for x in seg))
    # L2 / Ep08.10: the matrix on full ETH sessions
    if (p.pd_hl_session == "eth" or p.matrix_full) and eth and len(dates) >= 3:
        last3 = [ec(d) for d in dates[-3:]]
        if all(x is not None for x in last3):
            for k in [k for k in ctx.pd if k[:3] in ("pdh", "pdl")]:
                del ctx.pd[k]
            for k, x in enumerate(reversed(last3), 1):
                later = last3[len(last3) - k + 1:]
                if not later or max(y[1] for y in later) < x[1]:
                    ctx.pd[f"pdh{k}"] = x[1]
                if not later or min(y[2] for y in later) > x[2]:
                    ctx.pd[f"pdl{k}"] = x[2]
    cand = lambda d, fr: (ec(d) if (p.wick_session == "eth" and ec(d) is not None) else _hl(fr))
    # L10 / Ep08.1 / A23: wick CEs of the last wick_days days (ETH candles with wick_session="eth")
    ctx.wicks = [L.wick_midpoints(*cand(dates[-k], hist[-k])) for k in range(1, min(max(p.wick_days, 1), len(hist)) + 1)]
    if p.wick_session == "eth" and ctx.wicks:
        ctx.wick = ctx.wicks[0]
    d0 = df.index[0].date()
    pwk = (d0 - timedelta(days=7)).isocalendar()[:2]
    wk = [(d, x) for d, x in zip(dates, hist) if d.isocalendar()[:2] == pwk]
    ctx.wick_wk = []
    if p.wick_weekly and wk:
        cs = [cand(d, x) for d, x in wk]
        ctx.wick_wk = [L.wick_midpoints(cs[0][0], max(c[1] for c in cs), min(c[2] for c in cs), cs[-1][3])]
    # L3: previous week / month from full sessions
    if p.pw_pm_full_session and eth:
        if wk and all(ec(d) is not None for d, _ in wk):
            ctx.pw = (max(ec(d)[1] for d, _ in wk), min(ec(d)[2] for d, _ in wk))
        pmo = (d0.replace(day=1) - timedelta(days=1))
        mo = [d for d in dates if (d.year, d.month) == (pmo.year, pmo.month)]
        if mo and all(ec(d) is not None for d in mo):
            ctx.pm_ = (max(ec(d)[1] for d in mo), min(ec(d)[2] for d in mo))
    # L1 / M0.2: the AM range end and the previous AM range
    ctx.am_end = p.am_range_end
    if p.am_range_end != 810:
        am = df[(tt >= 570) & (tt < p.am_range_end)]
        ctx.am_hl = (float(am.high.max()), float(am.low.min())) if len(am) else None
    prev = hist[-1]
    pt = prev.index.hour * 60 + prev.index.minute
    pa = prev[(pt >= 570) & (pt < p.am_range_end)]
    ctx.prev_am = (float(pa.high.max()), float(pa.low.min())) if len(pa) else None
    if p.prev_am_pool and ctx.prev_am is not None:
        ctx.sess["prev_am"] = (ctx.prev_am[0], ctx.prev_am[1], 0)
    # L7 / D21: ORG history of max(org_days, 5) + 1 sessions (DayCtx keeps 6)
    if p.org_days > 5:
        seq = hist[-(max(p.org_days, 5) + 1):] + [df]
        ctx.org, ctx.org_today = [], False
        for a, b in zip(seq[:-1], seq[1:]):
            rth = b[(b.index.hour * 60 + b.index.minute) >= 570]
            if len(rth) and len(a):
                pc = (closes or {}).get(a.index[0].date(), float(a.close.iloc[-1]))
                ctx.org.append((float(pc), float(rth.open.iloc[0])))
                ctx.org_today = b is df
    # L3: the other opening range (OR60 next to OR30)
    ctx.or_alt = None
    if p.or_extra and p.or_minutes:
        m2 = 60 if p.or_minutes == 30 else 30
        ob = df[(tt >= 570) & (tt < 570 + m2)]
        if len(ob):
            ctx.or_alt = (570 + m2, (float(ob.high.max()), float(ob.low.min())))
    # L8: vacuum blocks at the releases (session opens are the ORG / NDOG - not duplicated)
    ctx.vac = []
    if p.vacuum_blocks:
        for R in _NC.releases(ctx.day, p):
            k = _idx_at(ctx, R)
            if k >= len(ctx.t) or k - 1 < S or ctx.t[k] != R or ctx.t[k - 1] + ctx.tf != R:
                continue
            z = L.vacuum_block(ctx.o, ctx.c, k, 0.25 * p.es_pt)
            if z is not None:
                near, far = float(ctx.o[k]), float(ctx.c[k - 1])
                ctx.vac.append((k, near, (near + far) / 2, far, R))


def _lv_target_pools(ctx, sd, i: int, p) -> list:
    """levels_detectors buy-side pools (side space) as (level, created bar) for _targets."""
    out = []
    S = ctx.start
    t = ctx.t[i]
    hi_ = lambda hl: sd.x(hl[0] if sd.sign > 0 else hl[1])
    if p.ipda_pools or p.ipda_next:            # B21 / L3
        seq = [hi_(hl) for _, hl in sorted(getattr(ctx, "ipda", {}).items())]
        if p.ipda_next:                         # cc05_003 ~28:38: 20 -> 40 -> 60
            seen = sd.h[S:i + 1].max()
            seq = [v for v in seq if not _spent_up(seen, v, _tick(p))][:1]
        out += [(v, S) for v in seq]
    ss = _sess_start(ctx, i)
    if (p.pool_today_hl or p.matrix_days == "ict") and ss is not None and ss > S:
        out.append((float(sd.h[S:ss].max()), ss))          # L2 / Ep08.10 today's high
        if p.matrix_days == "ict":                         # the 3-day high (m3h)
            raws = [float(sd.h[S:ss].max())] + [hi_((float(x.high.max()), float(x.low.min())))
                                               for x in getattr(ctx, "hist", [])[-2:]]
            out.append((max(raws), ss))
    oa = getattr(ctx, "or_alt", None)
    if oa is not None and t >= oa[0]:                      # L3 or_extra
        out.append((hi_(oa[1]), _idx_at(ctx, oa[0])))
    return out


def _lv_target_arrays(ctx, sd, i: int, p) -> list:
    """levels_detectors array targets (side space) for _targets: L8 vacuum blocks (08:30: near, MT and
    far edge; later releases - 09:45 / 10:00+: near and MT)."""
    out = []
    for k, near, mt, far, R in getattr(ctx, "vac", []):
        if k > i:
            continue
        out += [(sd.x(near), "array"), (sd.x(mt), "array")]
        if R == 510:                   # review fix: the spec gives the far edge at 08:30 only
            out.append((sd.x(far), "array"))
    return out


def _session_pick(ctx, i: int) -> str | None:
    """L1 / M0.2 priority at 09:30 (067 ~52:30): the previous PM range if the 09:30 open is near it
    [our interpretation: inside it or within a quarter of its height], else London's range, else
    the previous AM range."""
    k = _idx_at(ctx, 570)
    if k >= len(ctx.t) or k > i:
        return None
    px = float(ctx.o[k])
    if "prev_pm" in ctx.sess:
        hi, lo, _ = ctx.sess["prev_pm"]
        m = 0.25 * (hi - lo)
        if lo - m <= px <= hi + m:
            return "prev_pm"
    if "london" in ctx.sess:
        return "london"
    if getattr(ctx, "prev_am", None) is not None:
        return "prev_am"
    return None


def _lv_sell_side(ctx, sd, session: str, i: int, p, out: dict, extra: bool) -> None:
    """levels_detectors sell-side pools (side space) added to _sell_side's dict."""
    S = ctx.start
    t = ctx.t[i]
    lo_ = lambda hl: sd.x(hl[1] if sd.sign > 0 else hl[0])
    if p.ipda_pools:                                   # B21 / L3
        for n, hl in getattr(ctx, "ipda", {}).items():
            out[f"ipda{n}"] = lo_(hl)
    ss = _sess_start(ctx, i)
    if p.matrix_days == "ict":                         # Ep08.10: today + yesterday + the day before
        out.pop("pdl3" if sd.sign > 0 else "pdh3", None)
    if (p.pool_today_hl or p.matrix_days == "ict") and ss is not None and S < ss:
        out["today_low"] = float(sd.l[S:ss].min())
        if p.matrix_days == "ict":
            raws = [float(sd.l[S:ss].min())] + [lo_((float(x.high.max()), float(x.low.min())))
                                               for x in getattr(ctx, "hist", [])[-2:]]
            out["m3l"] = min(raws)
    if session == "AM":
        if extra and p.prev_am_pool and "prev_am" in ctx.sess:
            out["prev_am"] = lo_(ctx.sess["prev_am"][:2])
        if extra and p.session_priority:               # L1 / M0.2: ONE session pool
            pick = _session_pick(ctx, i)
            for k in ("london", "prev_pm", "prev_am"):
                if k != pick:
                    out.pop(k, None)
            if pick == "prev_am" and "prev_am" not in out and ctx.prev_am is not None:
                out["prev_am"] = lo_(ctx.prev_am)
        if p.org_pools and getattr(ctx, "org_today", False) and t >= 570 and ctx.org:
            pc, op = ctx.org[-1]                       # L1: the ORG's prior-close edge, when below the open
            if sd.x(pc) < sd.x(op):
                out["org_close"] = sd.x(pc)
        oa = getattr(ctx, "or_alt", None)
        if oa is not None and t >= oa[0]:
            out["or_alt"] = lo_(oa[1])
    last = sd.c[i - 1] if i - 1 >= 0 else sd.c[i]
    if p.org_sweep and p.org_days and ctx.org:         # D21: the kept ORGs' levels below price
        today = getattr(ctx, "org_today", False)
        orgs = ctx.org[:-1] if (t < 570 and today) else ctx.org
        orgs = orgs[-p.org_days:]
        for j, (a, b) in enumerate(orgs):
            tag = "org_t" if (today and t >= 570 and j == len(orgs) - 1) else f"org{len(orgs) - 1 - j}"
            for q, v in (("lo", min(a, b)), ("ce", (a + b) / 2), ("hi", max(a, b))):
                if sd.x(v) < last:
                    out[f"{tag}_{q}"] = sd.x(v)
    if p.pool_gaps:                                    # M2.1: NWOG / NDOG as sweep pools
        gl = ctx.gaps if getattr(ctx, "gaps", None) is not None else \
            [("monday", max(a, b), min(a, b), (a + b) / 2) for a, b in _nwogs(ctx, i)]
        for j, (kind, hi, lo, ce) in enumerate(gl):
            v = min(sd.x(hi), sd.x(lo)) if p.gap_pool_edge == "far" else sd.x(ce)
            if v < last:
                out[f"gap_{kind}{j}"] = v


def _ipda_eq(ctx, p, i: int) -> bool:
    """B21 (cc05_003 ~1:18:26) [our interpretation]: price near the EQ of all three IPDA ranges -
    within ipda_eq_frac of each range of its midpoint - with both sides run: an earlier 20-day high
    AND an earlier 20-day low were each taken within the last ipda_eq_days sessions. Price = the
    09:30 open (the last close before 09:30). Needs 60 + ipda_eq_days... at least 60 sessions."""
    hist = getattr(ctx, "hist", [])
    if len(ctx.ipda) < 3 or len(hist) < 21:
        return False
    k = _idx_at(ctx, 570)
    px = float(ctx.o[k]) if (k < len(ctx.t) and k <= i) else float(ctx.c[i])
    for n, (hi, lo) in ctx.ipda.items():
        if abs(px - (hi + lo) / 2) > p.ipda_eq_frac * (hi - lo):
            return False
    up = dn = False
    dh = getattr(ctx, "ipda_days", None) or [(float(x.high.max()), float(x.low.min())) for x in hist]
    for j in range(max(20, len(dh) - p.ipda_eq_days), len(dh)):   # review fix: the same (ETH) candles
        prior = dh[j - 20:j]
        if dh[j][0] > max(x[0] for x in prior):
            up = True
        if dh[j][1] < min(x[1] for x in prior):
            dn = True
    return up and dn


def _org_state(ctx, sd, i: int, p) -> dict | None:
    """L7 ORG behaviour at bar i (side space), today's ORG only, from 09:30: pc = the prior close
    (far edge), op = the 09:30 open (near edge). breakaway (B15 / 033 ~14:57) [our interpretation]:
    by 09:30 + org_break_min price never reached the gap's 25% level (no attempt) - None (unknown)
    before then; half: CE reached, far edge not; q_hold (036 ~53:00): the 25% level reached and no
    close beyond it since 09:30."""
    if not (getattr(ctx, "org_today", False) and ctx.org and ctx.t[i] >= 570):
        return None
    pc, op = ctx.org[-1]
    pcx, opx = sd.x(pc), sd.x(op)
    if pcx == opx:
        return None
    k0 = _idx_at(ctx, 570)
    q25 = opx + 0.25 * (pcx - opx)
    mid = (opx + pcx) / 2
    up = pcx > opx                                   # the prior close lies above (side space)
    hi = sd.h[k0:i + 1].max() if up else -sd.l[k0:i + 1].min()
    sgn = 1 if up else -1
    kb = _idx_at(ctx, 570 + p.org_break_min)
    brk = None
    if i >= kb:
        hb = sd.h[k0:kb].max() if up else -sd.l[k0:kb].min()
        brk = bool(hb < sgn * q25) if kb > k0 else None
    reach = lambda x: hi >= sgn * x
    closes = sd.c[k0:i + 1]
    q_hold = reach(q25) and bool(((closes <= q25) if up else (closes >= q25)).all())
    return dict(pcx=pcx, opx=opx, up=up, breakaway=brk, half=reach(mid) and not reach(pcx), q_hold=q_hold)


def _org_break(ctx, p, i: int) -> bool | None:
    """L7 breakaway in real prices (as _org_state): today's ORG and no reach to its 25% level in
    09:30 .. 09:30 + org_break_min; None until bar i is past that window (or no ORG today)."""
    if not (getattr(ctx, "org_today", False) and ctx.org):
        return None
    pc, op = ctx.org[-1]
    k0, kb = _idx_at(ctx, 570), _idx_at(ctx, 570 + p.org_break_min)
    if pc == op or i < kb or kb <= k0:
        return None
    q25 = op + 0.25 * (pc - op)
    return bool(ctx.h[k0:kb].max() < q25) if pc > op else bool(ctx.l[k0:kb].min() > q25)


def _nwog_half(ctx, sd, i: int) -> float | None:
    """L5 halfway rule (037 ~22:46; 051 ~16:51): with NWOG A below price and NWOG B above (side
    space), once today's high reached 50% of the space between A's and B's near edges, B's near
    edge is the next draw. Returns it (side space) or None."""
    if getattr(ctx, "gaps", None) is not None:
        zs = [(sd.x(hi), sd.x(lo)) for kind, hi, lo, _ in ctx.gaps if kind == "nwog"]
    else:
        zs = [(sd.x(a), sd.x(b)) for a, b in _nwogs(ctx, i)]
    zs = [(max(a, b), min(a, b)) for a, b in zs]
    px = sd.c[i]
    below = [z for z in zs if z[0] <= px]
    above = [z for z in zs if z[1] > px]
    if not below or not above:
        return None
    A, B = max(below), min(above, key=lambda z: z[1])
    half = (A[0] + B[1]) / 2
    return B[1] if sd.h[ctx.start:i + 1].max() >= half else None


def _wick_ces(ctx, sd, near_side: bool) -> list:
    """L10 / Ep08.1 prior daily wick CEs (side space): near_side=True -> the lower wicks (support
    under a long), False -> the upper wicks (targets)."""
    out = []
    for w in getattr(ctx, "wicks", [ctx.wick]):
        if sd.sign > 0:
            out.append(w["lower"] if near_side else w["upper"])
        else:
            out.append(-w["upper"] if near_side else -w["lower"])
    return out


def _draw_prefs(ctx, sd, i: int, entry: float, p, session: str, keep: list) -> list:
    """levels_detectors draw overrides for the non-lock path (side space, raw levels with kinds):
    A5 htf_ce_draw (029 ~44:48), A9 vi_htf_draw, L5 nwog_halfway, L7 org_draw / org_half_draw,
    Ep06.7 eq_pref (the nearest rel-eq pool). The caller takes the nearest with room."""
    out = []
    conf = getattr(ctx, "conf", None)
    now = ctx.idx[i] + pd.Timedelta(minutes=ctx.tf)
    if conf is not None and (p.htf_ce_draw or p.vi_htf_draw):
        tfs = tuple(p.htf_targets) or ("15m", "1h", "4h", "D")
        if p.htf_ce_draw:
            r = conf.opposing(now, sd.x(entry), sd.sign, tfs, (0,))
            if r:
                out.append((sd.x(r[0][1]), "array", "htf_ce"))
        if p.vi_htf_draw:
            r = conf.opposing(now, sd.x(entry), sd.sign, ("1h", "4h", "D", "W"), (3,))
            if r:
                out.append((sd.x(r[0][0]), "array", "htf_vi"))
    if p.nwog_halfway:
        b = _nwog_half(ctx, sd, i)
        if b is not None:
            out.append((b, "array", "nwog_half"))
    if session == "AM" and (p.org_draw == "draw" or p.org_half_draw):
        st = _org_state(ctx, sd, i, p)
        if st is not None and st["up"]:
            if p.org_draw == "draw" and st["breakaway"] is not True:
                out.append((st["pcx"], "array", "org_far"))
            if p.org_half_draw and st["half"]:
                out.append((st["pcx"], "array", "org_half"))
    return out


def _close(pos, trades, p):
    tr = pos["trade"]
    tr.capture = _TP.capture_ratio(pos, tr)           # X3h: how much of the best-case run the exits took
    trades.append(tr)
    gross, costs = tr.pnl(p.cost_per_share)
    return tr.side if gross - costs < 0 else None


def _after_close(pos, trades, p, done, state, i=None, ctx=None):
    """Record the trade; apply the session rules that depend on how it ended."""
    lost = _close(pos, trades, p)
    tr = pos["trade"]
    if p.stop_flip != "off" and lost is not None and tr.exits and tr.exits[-1][3] in ("stop", "stop_gap"):
        s_ = 1 if tr.side == "long" else -1           # B8f (042 ~1:08:19) [our interpretation]
        if p.stop_flip == "smt":
            hit_ = tr.smt is True
        else:                                         # the stop lay beyond the breaker's far edge
            hit_ = (tr.bz_bottom is not None and tr.stop <= tr.bz_bottom) if s_ > 0 else \
                   (tr.bz_top is not None and tr.stop >= tr.bz_top)
        if hit_:
            state["flip"] = -s_
    if lost is None and tr.session == "AM" and p.no_pm_after_am_win:
        done["PM"] = True
    gross, costs = tr.pnl(p.cost_per_share)
    net_ = gross - costs
    key = pos.get("done_key", tr.session)
    reopened = False
    if (lost is not None and p.reentry_half and not state["reentered"].get(tr.session)
            and not (p.fomc_day_stop and "fomc" in events(tr.date))):            # N3.5: none on an FOMC day
        # X13b / D18: one more try, same direction, half risk (reentry_gate: only while the idea is intact); the flag of
        # the trade's OWN done key is re-opened (an SB_AM loss no longer re-opens the plain AM slot)
        rc = (_MG.reentry_open(ctx, pos, tr, i if i is not None else pos["fill_i"], p, state, net_) if ctx is not None
              else dict(side=tr.side, stop_i=-1, pending=True, loss=max(0.0, -net_), ratio=1.0, key=key))
        if rc is not None:
            done[key] = False
            state["reentered"][tr.session] = True
            state.setdefault("re_ctx", {})[tr.session] = rc
            reopened = True
    if (lost is not None and not reopened and p.reverse_in_session
            and not state.setdefault("reversed", {}).get(tr.session)):
        # X13a (experienced, 001 ~47:32): the session may reverse once after a loss - the opposite side only (also when
        # reentry_half is on but its gate refused the re-entry)
        done[key] = False
        state["reversed"][tr.session] = True
        state.setdefault("only_side", {})[tr.session] = -1 if tr.side == "long" else 1
    if net_ < 0:
        state["day_loss"] = True                      # Ep08.12 after_loss_mult / after_loss_adds
    if lost is not None:
        state["lost_fam"] = _MG.fam(tr.session)       # X13a lost_side_session
    if p.loss_halving and state.get("rs") is not None:
        _EN.risk_state_update(state["rs"], gross - costs, p)       # E10 (carried across days)
    _MG.mark_day_stop(tr, p)                           # Ep04.13 / X12: the trade itself ended the day
    _MG.apply_stops(trades, p, done, state)           # X7c / X12 / X13a / X14b / X14d: session and day stops
    if p.day_target_pts:                              # X14a test (owner #2): N net ES pts -> done
        gross, costs = tr.pnl(p.cost_per_share)
        units = tr.shares + sum(q for *_, q in tr.adds)
        state["day_pts"] = state.get("day_pts", 0.0) + (gross - costs) / max(units, 1) / p.es_pt
        if state["day_pts"] >= p.day_target_pts:
            for k in list(done):
                done[k] = True
            state["day_done"] = True
    return lost


def _risk_mult(state, session, p) -> float:
    """The risk multiplier of a new order: D18 re-entry half, E10 loss_halving state, Ep08.12
    after_loss_mult (any later trade on a day with a loss)."""
    m = 0.5 if state["reentered"].get(session) else 1.0
    if m < 1.0 and p.reentry_risk == "loss":          # D18: half of the LOSING trade's own risk
        m = 0.5 * state.get("re_ctx", {}).get(session, {}).get("ratio", 1.0)
    if p.loss_halving and state.get("rs") is not None:
        m *= state["rs"]["m"]
    if state.get("day_loss"):
        m *= p.after_loss_mult
    return m


def _nadds(pos, tr) -> int:
    """Pyramid adds so far (entry-ladder rung fills, E2, are not adds)."""
    return len(tr.adds) - pos.get("rung_fills", 0)


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
    if "premium_run" in p.sloppy_tests and _premium_run(hist, p):
        out.add("premium_run")
    if "fomc_week" in p.sloppy_tests:
        mon = day - timedelta(days=day.weekday())
        wk = [mon + timedelta(days=k) for k in range(5)]
        fomc = any("fomc" in events(x) for x in wk)
        if fomc and (not p.sloppy_fomc_nfp or any(x in JOBS for x in wk)):
            out.add("fomc_week")
    if "inside_bisi" in p.sloppy_tests and _inside_daily_fvg(hist):
        out.add("inside_bisi")
    return out


def _daily(hist: list[pd.DataFrame]) -> tuple:
    o = np.array([float(x.open.iloc[0]) for x in hist]); c = np.array([float(x.close.iloc[-1]) for x in hist])
    h = np.array([float(x.high.max()) for x in hist]); l = np.array([float(x.low.min()) for x in hist])
    return o, h, l, c


def _premium_run(hist: list[pd.DataFrame], p: "Params") -> bool:
    """#10 / B17 (044 ~1:14:47 "we've moved essentially parabolically from Tuesday one direction
    with no real retracements ... we traded to an old high") [our interpretation]: the last
    sloppy_run_days completed sessions each closed above the prior close with a higher low, and the
    last one traded up into a daily high of the sloppy_run_lookback sessions before the run that no
    session had taken until the run (mirror: a run down into an old low). Completed days only."""
    n, lb = p.sloppy_run_days, p.sloppy_run_lookback
    if n < 1 or len(hist) < n + 3:
        return False
    o, h, l, c = _daily(hist)
    for sgn, hh, ll, cc in ((1, h, l, c), (-1, -l, -h, -c)):
        if not (all(cc[-k] > cc[-k - 1] for k in range(1, n + 1)) and all(ll[-k] > ll[-k - 1] for k in range(1, n + 1))):
            continue
        a = len(hh) - n                                # first session of the run
        before = range(max(0, a - lb), a)
        for j in before:
            untaken = hh[j + 1:a].max(initial=-np.inf) < hh[j]   # an old high still standing
            if untaken and hh[a:-1].max(initial=-np.inf) < hh[j] <= hh[-1]:
                return True                            # the run's last day traded into it
    return False


def _inside_daily_fvg(hist: list[pd.DataFrame]) -> bool:
    """#10 / B17 (091 ~6:12 "price inside one daily BISI range = don't trade that index") [our
    interpretation]: yesterday's whole range sat inside one daily FVG (either direction) formed
    before it and not closed through since."""
    if len(hist) < 4:
        return False
    o, h, l, c = _daily(hist)
    k = len(h) - 1
    for z in L.fvgs(h[:k], l[:k]):
        after = c[z.i + 1:k]
        if z.kind == "bull" and len(after) and after.min() < z.bottom:
            continue
        if z.kind == "bear" and len(after) and after.max() > z.top:
            continue
        if z.bottom <= l[k] and h[k] <= z.top:
            return True
    return False


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


def _judas(ctx, sd, sw, session, window: int = 60) -> bool:
    """Power of three: the sweep was the session's opening move against the trade - its
    extreme came within the first hour (`window` minutes; setups_models judas_window) of the
    session and beyond the session's reference open (midnight for the AM, 13:30 for the PM)."""
    t0 = 570 if session == "AM" else 810
    ref = ctx.opens.get("midnight" if session == "AM" else "1330")
    if ref is None:
        return False
    return bool(t0 <= ctx.t[sw["ext_i"]] < t0 + window and sw["ext"] < sd.x(ref))


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
    if p.ladder_news_day and tags & {"cpi", "jobs", "fomc"}:      # Ep04.12: a news day takes the bulk first
        return p.ladder_fracs_slow
    nxt = next_trading_day(day)
    if events(nxt) & {"cpi", "jobs", "fomc"}:
        ahead = True
    slow = _slow_day(p, ctx, hist, i)
    return p.ladder_fracs_slow if (ahead or slow) else p.ladder_fracs


def _slow_day(p, ctx, hist, i: int) -> bool:
    """Slow day [our interpretation]: the range from midnight to bar i is under slow_frac x the 5-day average
    regular-session range (adr5). Shared by _split (036 80/20) and X14b chop_one_win."""
    adr = adr5(hist[-5:])
    if adr is None:
        return False
    rng = ctx.h[ctx.start:i + 1].max() - ctx.l[ctx.start:i + 1].min()
    return bool(rng < p.slow_frac * adr)


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
    for R in _NC.releases(day, p):
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
    a = p.am_win[0] or 570
    rs = [R for R in _NC.releases(day, p) if a <= R < (p.am[1] or 660)]
    out = {"AM": max([a] + rs), "PM": p.pm[0] or 810}
    for name, a_, _ in pre_windows:
        out[name] = a_                                   # PRE7 07:00, PRE8 08:20, PRE9 / NEWS 09:00, LON its start
    if _SM.lh_on(p, "last_hour_own_slot") and not p.lh_no_lock:
        # setups_models review fix (owner #9 x M5.2 / Ep01.13): the own last-hour slot locks ITS
        # draw at 15:00 (bars closed by then, htf table cut at 15:00), like the MD / SB own locks
        # [our interpretation, owner open question 3]
        out["LH"] = p.last_hour[0]
    return out


def mark_levels(ctx, row: dict | None, t_lock: int, session: str, p, spent=(), org_pref: bool = True) -> dict:
    """Mark up the levels before the session opens and lock ONE draw (owner #9). Uses only bars
    that closed by t_lock (bar start + tf <= t_lock). Candidates, each with its kind (pool /
    array), its direction (+1 buy-side high, -1 sell-side low, 0 array / round handle) and the
    bar from which it exists: the HTF draws from the htf table cut at t_lock (draw_up /
    draw_dn), PDH/PDL 1-3, the overnight high/low known by t_lock, previous week / month (if
    on), NWOG/NDOG edges and CE, opening range gaps (today's only once 09:30 has printed), PM:
    the AM and lunch highs/lows (complete at 13:30), and the nearest round handles (#13).
    L14d (review fix, as M7.1 in _targets): a level is dropped only when bars AFTER it formed
    and up to the lock traded through it, so the lunch / AM highs can be the PM draw. Levels
    delivered earlier today (`spent`, L14e) are dropped. "nearest" [our interpretation]: the
    nearer remaining level at least draw_lock_min_pts away sets the side; no candidate on a
    side loses; none / a tie = neutral. `marked` keeps EVERY intact level on both sides,
    (v, kind, name, dir), nearest first - the frozen ladder rungs between the entry and the
    draw come from it (review fix: it used to hold only the far side's candidates)."""
    t = ctx.t
    S = ctx.start
    kl = S + int(np.searchsorted(t[S:] + ctx.tf, t_lock, side="right"))
    px = float(ctx.c[kl - 1])
    at = lambda m: _idx_at(ctx, m)
    cands = []                                         # (v, kind, name, dir, created)
    if row:
        for key, dr in (("draw_up", 1), ("draw_dn", -1)):
            v = row.get(key)
            if v is not None and v == v:
                nm = str(row.get(key + "_name", ""))
                cands.append((float(v), "pool" if nm in POOL_NAMES else "array", "htf_" + nm,
                              dr if nm in POOL_NAMES else 0, S))
    for k, v in ctx.pd.items():
        if k.startswith(("pdh", "pdl")):
            if p.matrix_days == "ict" and k in ("pdh3", "pdl3"):
                continue                               # review fix: the Ep08.10 matrix as in the scan
            cands.append((v, "pool", k, 1 if k.startswith("pdh") else -1, S))
    if t_lock >= 570:
        for k, dr in (("pmh", 1), ("pml", -1)):
            if k in ctx.pd:
                cands.append((ctx.pd[k], "pool", k, dr, at(570)))
    else:
        m = max((m for m in ctx.pre_at if m <= t_lock), default=None)
        if m is not None:
            cands += [(ctx.pre_at[m][0], "pool", "overnight_high", 1, at(m)),
                      (ctx.pre_at[m][1], "pool", "overnight_low", -1, at(m))]
    for on, hl, nm in ((p.pool_prev_week, ctx.pw, "pw"), (p.pool_prev_month, ctx.pm_, "pmonth_")):
        if on and hl is not None:
            cands += [(hl[0], "pool", nm + "h", 1, S), (hl[1], "pool", nm + "l", -1, S)]
    if getattr(ctx, "gaps", None) is not None:
        for kind, hi, lo, ce in ctx.gaps:
            cands += [(hi, "array", kind + "_high", 0, S), (ce, "array", kind + "_ce", 0, S),
                      (lo, "array", kind + "_low", 0, S)]
    else:
        for a, b in _nwogs(ctx, None if t_lock < 570 else at(570)):
            cands += [(a, "array", "nwog", 0, S), (b, "array", "nwog", 0, S)]
    if p.org_days:
        orgs = ctx.org[:-1] if (ctx.org_today and t_lock <= 570) else ctx.org
        orgs = orgs[-p.org_days:]
        for j, (a, b) in enumerate(orgs):
            cr = at(570) if (ctx.org_today and t_lock > 570 and j == len(orgs) - 1) else S
            cands += [(a, "array", "org", 0, cr), ((a + b) / 2, "array", "org_ce", 0, cr), (b, "array", "org", 0, cr)]
    if session == "PM" and t_lock >= 810:
        if ctx.am_hl:
            cands += [(ctx.am_hl[0], "pool", "am_high", 1, at(810)), (ctx.am_hl[1], "pool", "am_low", -1, at(810))]
        if "lunch" in ctx.sess:
            cands += [(ctx.sess["lunch"][0], "pool", "lunch_high", 1, at(810)),
                      (ctx.sess["lunch"][1], "pool", "lunch_low", -1, at(810))]
    st = getattr(ctx, "round_step", 0.0)
    if st and getattr(ctx, "adj", None) is not None and kl - 1 >= 0:
        adj = float(ctx.adj[kl - 1])
        raw = px - adj
        cr = S if getattr(ctx, "round_from", "session") == "midnight" else (
            at(810) if t_lock >= 810 else at(570) if t_lock >= 570 else S)   # untaken this session
        cands += [(float(np.ceil(raw / st) * st + adj), "pool", "round", 0, cr),
                  (float(np.floor(raw / st) * st + adj), "pool", "round", 0, cr)]
    # levels_detectors candidates: B21 IPDA pools, L2 today's high/low at the session start, L1 the
    # previous AM range; and draws the switches prefer (vi_news_draw, org_draw, nwog_halfway,
    # htf_ce_draw) - the nearest preferred level, when one is intact and far enough, is the lock
    if p.ipda_pools or p.ipda_next:
        for n, (hi_, lo_) in sorted(getattr(ctx, "ipda", {}).items()):
            cands += [(hi_, "pool", f"ipda{n}h", 1, S), (lo_, "pool", f"ipda{n}l", -1, S)]
    if p.pool_today_hl or p.matrix_days == "ict":
        k0 = at(810) if t_lock >= 810 else (at(570) if t_lock >= 570 else None)
        if k0 is not None and S < k0 <= kl:
            cands += [(float(ctx.h[S:k0].max()), "pool", "today_high", 1, k0),
                      (float(ctx.l[S:k0].min()), "pool", "today_low", -1, k0)]
            if p.matrix_days == "ict":                 # review fix: the 3-day extremes (m3h / m3l)
                hs3 = getattr(ctx, "hist", [])[-2:]
                cands += [(max([float(ctx.h[S:k0].max())] + [float(x.high.max()) for x in hs3]), "pool", "m3h", 1, k0),
                          (min([float(ctx.l[S:k0].min())] + [float(x.low.min()) for x in hs3]), "pool", "m3l", -1, k0)]
    if p.prev_am_pool and getattr(ctx, "prev_am", None) is not None:
        cands += [(ctx.prev_am[0], "pool", "prev_am_high", 1, S), (ctx.prev_am[1], "pool", "prev_am_low", -1, S)]
    prefs = []
    if p.vi_news_draw and row and release_times(ctx.day):     # Ep02.8 / Ep 02 ~9:19
        for key_ in ("vi_up", "vi_dn"):
            v = row.get(key_)
            if v is not None and v == v:
                prefs.append((float(v), "array", "vi_news", 0, S))
    # L7 (review fix): today's ORG is known from the 09:30 open, i.e. at the 09:30 lock itself (the
    # lock is taken while the 09:30 bar is in); the breakaway test (_org_break) drops org_far once
    # 09:30 + org_break_min shows no attempt - here when known by the lock, else _lock_step re-marks
    # the lock without it (org_pref=False). org_half_draw: CE reached, far edge not, by the lock.
    k570 = at(570)
    if (org_pref and session == "AM" and t_lock >= 570 and ctx.org_today and ctx.org and k570 < len(t)
            and (p.org_draw == "draw" or p.org_half_draw)):
        pc_, op_ = ctx.org[-1]
        brk = _org_break(ctx, p, kl - 1)
        if p.org_draw == "draw" and brk is not True:
            prefs.append((pc_, "array", "org_far", 0, k570))                # the prior close
        if p.org_half_draw and kl > k570 and pc_ != op_:
            up_ = pc_ > op_
            hh = ctx.h[k570:kl].max() if up_ else -ctx.l[k570:kl].min()
            sg = 1 if up_ else -1
            if hh >= sg * (pc_ + op_) / 2 and hh < sg * pc_:
                prefs.append((pc_, "array", "org_half", 0, k570))
    if p.nwog_halfway and kl - 1 >= S:                                     # L5 halfway rule
        if getattr(ctx, "gaps", None) is not None:
            zs = [(hi_, lo_) for kind, hi_, lo_, _ in ctx.gaps if kind == "nwog"]
        else:
            zs = [(max(a, b), min(a, b)) for a, b in _nwogs(ctx, None if t_lock < 570 else at(570))]
        bel = [z for z in zs if z[0] <= px]
        abv = [z for z in zs if z[1] > px]
        if bel and abv:
            A, Bz = max(bel), min(abv, key=lambda z: z[1])
            half = (A[0] + Bz[1]) / 2
            if ctx.h[S:kl].max() >= half:
                prefs.append((Bz[1], "array", "nwog_half", 0, S))
            elif ctx.l[S:kl].min() <= half:
                prefs.append((A[0], "array", "nwog_half", 0, S))
    if p.htf_ce_draw and getattr(ctx, "conf", None) is not None:          # A5 (029 ~44:48)
        now = pd.Timestamp(ctx.day, tz=ctx.idx.tz) + pd.Timedelta(minutes=t_lock)
        tfs = tuple(p.htf_targets) or ("15m", "1h", "4h", "D")
        for sgn in (1, -1):
            r = ctx.conf.opposing(now, px, sgn, tfs, (0,))
            if r:
                prefs.append((r[0][1], "array", "htf_ce", 0, S))
    if p.vi_htf_draw and getattr(ctx, "conf", None) is not None:          # A9 (review fix: in the lock too)
        now = pd.Timestamp(ctx.day, tz=ctx.idx.tz) + pd.Timedelta(minutes=t_lock)
        for sgn in (1, -1):
            r = ctx.conf.opposing(now, px, sgn, ("1h", "4h", "D", "W"), (3,))
            if r:
                prefs.append((r[0][0], "array", "htf_vi", 0, S))
    cands = prefs + cands                          # review fix: a preferred draw keeps its own name
    pref_keys = {(round(v, 9), k) for v, k, *_ in prefs}
    near = lambda v: any(abs(v - s) <= p.es_pt for s in spent)

    tk = _tick(p)

    def intact(v, dr, cr):
        """L14d: not traded through by the bars after it formed, up to the lock (review fix: A2
        booking tick - through = at least sweep_ticks beyond it, as in the scan)."""
        a = max(cr, S)
        if a >= kl:
            return True
        if tk <= 0:                                    # the old rule: a touch keeps it intact
            return (ctx.h[a:kl].max() <= v) if v > px else (ctx.l[a:kl].min() >= v)
        return (not _spent_up(ctx.h[a:kl].max(), v, tk)) if v > px else (not _thru(ctx.l[a:kl].min(), v, tk))

    if p.draw_lock_near_cap and _TP.resist_cfg(p)[0] and getattr(ctx, "conf", None) is not None:
        # switch: candidates beyond the nearest opposing HTF FVG wholly beyond the lock price
        # (as known at the lock) are not draws
        now = pd.Timestamp(ctx.day, tz=ctx.idx.tz) + pd.Timedelta(minutes=t_lock)
        src = tuple(CF_SRC[x] for x in p.htf_resist_src)
        for sgn in (1, -1):
            r = ctx.conf.resistance(now, px, sgn, _TP.resist_cfg(p)[0], src, straddle=False)
            if r is not None:          # [our interpretation] arrays wholly beyond the lock price
                cands = [x for x in cands if (x[0] <= r[0] if sgn > 0 else x[0] >= r[0])
                         or (x[0] < px if sgn > 0 else x[0] > px)]
    marked = {}
    for v, k, n, dr, cr in cands:
        if v == px or near(v) or not intact(v, dr, cr):
            continue
        if (v > px and dr < 0) or (v < px and dr > 0):
            continue                                   # a low above / high below price: taken
        key = (round(v, 9), k)
        if key not in marked:
            marked[key] = (abs(v - px), v, k, n, dr)
    mk = sorted(marked.values())
    mn = p.draw_lock_min_pts * p.es_pt
    pf = [x for x in mk if (round(x[1], 9), x[2]) in pref_keys and x[0] >= mn]
    up = [x for x in mk if x[1] > px and x[0] >= mn]
    dn = [x for x in mk if x[1] < px and x[0] >= mn]
    if pf:                                         # levels_detectors: a preferred draw wins
        up = [x for x in pf if x[1] > px]
        dn = [x for x in pf if x[1] < px]
    elif p.pool_rank or p.draw_below_eq:           # L4: the larger pool / beyond the range's equilibrium
        up, dn = _TP.lock_rank(ctx, p, up, px, True), _TP.lock_rank(ctx, p, dn, px, False)
    side = 0
    if up and (not dn or up[0][0] < dn[0][0]):
        side = 1
    elif dn and (not up or dn[0][0] < up[0][0]):
        side = -1
    pick = up if side > 0 else dn
    lock = dict(day=ctx.day, session=session, side=side, t_lock=t_lock, px=px,
                target=pick[0][1] if side else None, kind=pick[0][2] if side else "",
                name=pick[0][3] if side else "", marked=[(v, k, n, dr) for _, v, k, n, dr in mk] + (
                    [(w[s_], "array", "wick_ce", 0) for w in getattr(ctx, "wicks", [ctx.wick])
                     for s_ in ("upper", "lower")] if p.wick_partial else []),
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
               lock_capped=o.get("lock_capped", False), sloppy=o.get("sloppy", ""), news_wait_min_actual=o.get("news_wait_min_actual"),
               news_pd=o.get("news_pd"), lv_tags=o.get("lv_tags", ""), fvg_state=o.get("fvg_state", ""),
               imm_rebal=bool(o.get("imm_rebal", False)), macro_wins=o.get("macro_wins", ""),
               ext_px=None if o.get("ext") is None else float(sd.x(o["ext"])),
               leg_hi_px=None if not o.get("leg") else float(sd.x(o["leg"][1])), **btag)
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
    ra = getattr(ctx, "roll_at", None)               # review: only a roll known by the fill bar
    tr.roll_day = bool(ra is not None and i >= ra)


def _prints_through(low: float, px: float, p) -> bool:
    """E3: a resting buy limit at px fills when the low printed below it - with fill_through ticks
    of margin when that switch is on (042 ~59:04; 070 ~56:01: at least 1 tick through)."""
    ft = p.fill_through * p.tick
    return bool(low <= px - ft + 1e-12) if ft else bool(low < px)


def _retrace_ok(sd, o, i, p) -> bool:
    """E4 retrace_candle (Ep 07; 009 ~8:11; 037 ~21:10: buy into down-close candles, sell into up-close):
    "closed" = at least one down-close candle (side space) printed between the arming bar and the
    fill bar; "intrabar" = the fill bar opens above the limit (it trades down into it, no gap)."""
    if p.retrace_candle == "off" or o.get("market"):
        return True
    if p.retrace_candle == "closed":
        a = o["i"] + 1
        return bool((sd.c[a:i] < sd.o[a:i]).any())
    return bool(sd.o[i] > o["entry"])


def _fill_at(sd, o, i):
    """Fill price of pending order o on bar i (side space) or None. setups_models flags: market
    (the open), stop_entry (a buy stop: the high reached it; gap -> the open), through (a limit
    that needs `through` beyond it); else the plain limit (a low below it; gap -> the open)."""
    if o.get("market"):
        return float(sd.o[i])
    if o.get("stop_entry"):
        return float(max(o["entry"], sd.o[i])) if sd.h[i] >= o["entry"] else None
    th = o.get("through", 0.0)
    if th:
        return float(min(o["entry"], sd.o[i])) if sd.l[i] <= o["entry"] - th + 1e-12 else None
    return float(min(o["entry"], sd.o[i])) if sd.l[i] < o["entry"] else None


def _extra_sig(trs) -> tuple:
    return tuple(sorted((t.setup, t.side, str(t.entry_time), tuple((str(e[0]), round(float(e[1]), 4), int(e[2]), e[3])
                                                                 for e in t.exits)) for t in trs))


def run_day(df: pd.DataFrame, hist: list[pd.DataFrame], symbol: str, p: Params, tf: int,
            partner=None, log: list | None = None, live: bool = False, bias: dict | None = None,
            conf=None, gaps: list | None = None, closes: dict | None = None, evening=None, partner2=None,
            intermarket: dict | None = None, equity: float | None = None,
            bias_by_cut: dict | None = None, meta=None, locks: list | None = None, skips: list | None = None,
            eth: dict | None = None, risk_state: dict | None = None) -> list[Trade]:
    """Trades for one day (see `_run_day_once` for the arguments). The main loop runs BEFORE the Silver Bullet / Ma Deuce
    (they read its trades), so the session / day stops (X7c / X12 / X13a / X14b / X14d) would be one-way. With a stop
    switch on and an extra engine on, this wrapper makes them two-way by a fixed point: pass 1 as usual; its Silver Bullet
    / Ma Deuce trades are fed back to a second pass (the main loop reads them as of their exit time, Ma Deuce reads the
    SB's), until the extras' trades stop changing (at most `stops_passes` passes). Every decision only uses trades closed
    by its own bar, so there is no look-ahead; the side effects (locks, skips, log, the E10 risk state) come from the last
    pass only."""
    kw = dict(partner=partner, live=live, bias=bias, conf=conf, gaps=gaps, closes=closes, evening=evening,
              partner2=partner2, intermarket=intermarket, equity=equity, bias_by_cut=bias_by_cut, meta=meta, eth=eth)
    if not (_MG.any_stop_switch(p, df.index[0].date()) and (p.ma_deuce or p.sb_model) and p.stops_passes > 1):
        return _run_day_once(df, hist, symbol, p, tf, log=log, locks=locks, skips=skips, risk_state=risk_state, **kw)
    import copy
    ext, sig, res, sc = None, None, [], {}
    for k in range(p.stops_passes):
        sc = dict(log=None if log is None else [], locks=None if locks is None else [],
                  skips=None if skips is None else [],
                  risk_state=None if risk_state is None else copy.deepcopy(risk_state))
        out: dict = {}
        res = _run_day_once(df, hist, symbol, p, tf, _ext=ext, _out=out, **sc, **kw)
        new = out.get("extras", [])
        nsig = _extra_sig(new)
        if (k == 0 and not new) or nsig == sig:
            break
        ext, sig = new, nsig
    for key, real in (("log", log), ("locks", locks), ("skips", skips)):
        if real is not None:
            real.extend(sc[key])
    if risk_state is not None and sc.get("risk_state") is not None:
        risk_state.clear()
        risk_state.update(sc["risk_state"])
    return res


def _run_day_once(df: pd.DataFrame, hist: list[pd.DataFrame], symbol: str, p: Params, tf: int,
            partner: tuple[pd.DataFrame, list[pd.DataFrame]] | None = None,
            log: list | None = None, live: bool = False, bias: dict | None = None,
            conf=None, gaps: list | None = None, closes: dict | None = None,
            evening: pd.DataFrame | None = None,
            partner2: tuple[pd.DataFrame, list[pd.DataFrame]] | None = None,
            intermarket: dict | None = None, equity: float | None = None,
            bias_by_cut: dict | None = None, meta: pd.DataFrame | None = None,
            locks: list | None = None, skips: list | None = None, eth: dict | None = None,
            risk_state: dict | None = None, _ext: list | None = None, _out: dict | None = None) -> list[Trade]:
    """Trades for one day. With `live`, a position still open at the last bar is returned
    with no exit (exit_reason "open") instead of being closed at the last price.
    equity     (#12) start-of-day equity for risk_basis="equity"
    bias_by_cut  (#9) {lock minute: htf table row cut at that minute} for the draw lock
    meta       (#13) databento meta (adj, instrument_id, roll) covering the day
    locks / skips  optional lists that receive the session locks and the sloppy-day skips
    eth        (levels_detectors) {date: (o, h, l, c)} of full sessions, prior dates only
    risk_state (E10 loss_halving) {m, deficit, peak} carried across days by backtest.run (mutated)"""
    day = df.index[0].date()
    flat = _eff_flat(p)
    ff = _NC.fomc_flat_min(day, p)                        # N3 / N3.2: an FOMC day is flat at the release (0 = n/a)
    am_lo, am_hi = p.am_win                               # Ep01.10 am_from_0830
    ctx = DayCtx(df, day, hist, tf, p.htf, closes, p.or_minutes, evening if p.globex_pool else None)
    ctx.conf = conf
    ctx.gaps = gaps if (p.gap_mode == "ict" and gaps is not None) else None
    ctx.equity = float(equity) if (equity is not None and p.risk_basis == "equity") else p.account_equity
    ctx.symbol = symbol
    ctx.hist = hist
    ctx.am_lunch_end = p.am[1]
    ctx.am_lunch_hl = _NC.am_range(ctx, p) if p.lunch else None     # T8: the AM range, complete before the lunch session
    ctx.lon_start = p.london_kz_start
    ctx.bias_row = bias                                   # setups_models: htf table row (draws)
    ctx.eth = eth
    _attach_meta(ctx, meta, p, symbol)
    _setup_news(ctx, day, p)
    _extra_levels(ctx, df, hist, p, eth, closes)           # levels_detectors
    pctx = DayCtx(partner[0], day, partner[1], tf) if partner is not None else None
    if pctx is not None:
        _setup_news(pctx, day, p)
        _extra_levels(pctx, partner[0], partner[1], p)
    mg = p.min_fvg_pts * p.es_pt
    sk = dict(c2_dir=p.fvg_c2_dir, vi_min_gap=p.vi_min_gap_pts * p.es_pt,   # levels_detectors A5 / A9
              mit_legacy=p.mit_legacy_order)                                  # A15 (review fix)
    sides = [Side(1, ctx.o, ctx.h, ctx.l, ctx.c, p.pivot_n, mg, **sk), Side(-1, ctx.o, ctx.h, ctx.l, ctx.c, p.pivot_n, mg, **sk)]
    psides = ppos = None
    if pctx is not None:
        psides = {1: Side(1, pctx.o, pctx.h, pctx.l, pctx.c, p.pivot_n, mg, **sk),
                  -1: Side(-1, pctx.o, pctx.h, pctx.l, pctx.c, p.pivot_n, mg, **sk)}
        ppos = pd.Series(np.arange(len(pctx.idx)), index=pctx.idx)
    ctx.pside = (pctx, psides, ppos)                      # setups_models M16.2 sick sister
    ctx.partner2 = None
    if partner2 is not None:
        c2 = DayCtx(partner2[0], day, partner2[1], tf)
        _setup_news(c2, day, p)
        _extra_levels(c2, partner2[0], partner2[1], p)
        ctx.partner2 = (c2, {1: Side(1, c2.o, c2.h, c2.l, c2.c, p.pivot_n, mg, **sk),
                             -1: Side(-1, c2.o, c2.h, c2.l, c2.c, p.pivot_n, mg, **sk)},
                        pd.Series(np.arange(len(c2.idx)), index=c2.idx))
    tags = events(day)
    am_start = 600 if tags & NEWS_1000 else am_lo            # news_wait="off" only
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
    tt_ = df.index.hour * 60 + df.index.minute    # M12.3 or60: the 09:30-10:30 range (read from 10:30)
    o60 = df[(tt_ >= 570) & (tt_ < 630)]
    ctx.or60 = (float(o60.high.max()), float(o60.low.min())) if len(o60) else None
    ctx.bias_by_cut = bias_by_cut or {}
    chop = Chop(ctx, hist, p)
    ctx.chop = chop
    ctx.day_tags = "|".join(sorted(dt))
    ctx.intermarket = intermarket or {}
    trades: list[Trade] = []
    done = {"AM": False, "PM": False, "PRE7": False, "PRE9": False, "NEWS": False, "PRE8": False, "LON": False,
            "LUNCH": False}
    ctx.done_ref = done                                   # setups_models T10 moc_run
    pre_windows = []
    nfp_hour = p.nfp_first_hour and "jobs" in tags         # N1: nobody trades the first hour after 08:30 on a jobs day
    am0830 = p.am_from_0830                                # Ep01.10: the AM covers 09:00-09:30 itself (no double scan)
    ew = _NC.extra_windows(p, ctx, day, symbol)           # T5 / Ep01.10 / Ep06.1: PRE8, LON
    if nfp_hour:                                           # N1: on a jobs day every entry window is floored at 09:30
        ew = [w_ for w_ in ew if w_[0] != "PRE8"]          # (PRE8 ends by 09:30 at the latest: it is all inside the first hour)
        am_lo = max(am_lo, 570)
        am_start = max(am_start, am_lo)
    pre8 = any(n_ == "PRE8" for n_, *_ in ew)
    pre_windows += [w_ for w_ in ew if w_[0] == "LON"]
    if p.pre_0700:
        pre_windows.append(("PRE7", 420, 500 if pre8 else 510))
    pre_windows += [w_ for w_ in ew if w_[0] == "PRE8"]
    if p.post_news and news(day) == "0830" and not nfp_hour and not am0830:
        pre_windows.append(("NEWS", 540, 570))
    if p.pre_0900 and not nfp_hour and not am0830:
        pre_windows.append(("PRE9", 540, 570))
    state = {"day": day, "reentered": {}, "re_ctx": {}, "only_side": {}, "reversed": {}, "day_pts": 0.0, "day_loss": False,
             "rs": (risk_state if risk_state is not None else _EN.new_risk_state()) if p.loss_halving else None,
             "ext": list(_ext or ())}              # run_day fixed point: the extras' trades of the previous pass
    ctx.ext_other = [t_ for t_ in (_ext or ()) if t_.setup.startswith("sb_")]   # Ma Deuce reads the SB's (it runs first)
    # E9 / E10 / E11 / Ep08.12 for the setups that run AFTER the loop (Silver Bullet, Ma Deuce): they read
    # the day's closed trades as of their order time (entries.extras_risk_mult) - never a later loss
    ctx.risk_view = dict(rs0=None if state["rs"] is None else dict(state["rs"]), trades=trades)
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
        if state["ext"]:
            _MG.sync_ext(trades, p, done, state, ts)       # X7c / X12 / X13a / X14b / X14d: the extras' closed trades count too
        # --- 1. manage the open position on this bar
        if pos is not None:
            tr, sd = pos["trade"], pos["side"]
            o, h, l, c = sd.o[i], sd.h[i], sd.l[i], sd.c[i]
            pos["best"] = max(pos["best"], h)         # X3h capture metric: the best-case run includes this bar
            if pos.get("rungs"):                      # E2 / D11 entry ladder: the deeper rungs rest as limits
                if pos["t1_done"]:
                    pos["rungs"] = []
                else:
                    keep_r = []
                    for px_r, q_r in pos["rungs"]:
                        if i > pos["fill_i"] and _prints_through(l, px_r, p):
                            q_r = _EN.cap_add(q_r, pos["n"], p)         # E11: the total-contracts cap binds rungs too
                            if q_r < max(p.lot, 1):
                                continue                                # nothing left under the cap: the rung is dropped
                            px = min(px_r, o)
                            tr.adds.append((ts, sd.x(px), q_r))
                            pos["rung_fills"] = pos.get("rung_fills", 0) + 1
                            pos["left"] += q_r; pos["basis"] += px * q_r; pos["n"] += q_r
                        else:
                            keep_r.append((px_r, q_r))
                    pos["rungs"] = keep_r
            a = pos["add"]
            if a is not None:                         # pending pyramid add
                if (pos["t1_done"] or i - a["i"] > max(1, p.pending_minutes // tf) or chop_before
                        or (a.get("hold") is not None and i - 1 > a["i"] and sd.c[i - 1] < a["hold"])   # E12b add_hold
                        or _EN.add_cut_passed(sd, pos, i - 1, p)      # E12e: the cut passed on a closed bar
                        or (p.late_cutoff and t >= p.late_cutoff)):    # T11: no adds in the last 15 minutes
                    pos["add"] = None
                elif a.get("market"):                 # E1 add_order "market": the open after a retest bar
                    if i - 1 > a["i"] and sd.l[i - 1] <= a["px"]:
                        px = float(o)
                        tr.adds.append((ts, sd.x(px), a["q"]))
                        pos["left"] += a["q"]; pos["basis"] += px * a["q"]; pos["n"] += a["q"]
                        pos["add"] = None
                        if a.get("stop_to") is not None and a["stop_to"] < px:
                            pos["stop_to_next"] = (a["stop_to"], i)
                elif _prints_through(l, a["px"], p):
                    px = min(a["px"], o)
                    tr.adds.append((ts, sd.x(px), a["q"]))
                    pos["left"] += a["q"]; pos["basis"] += px * a["q"]; pos["n"] += a["q"]
                    pos["add"] = None
                    if a.get("stop_to") is not None and a["stop_to"] < px:
                        pos["stop_to_next"] = (a["stop_to"], i)   # M5.1: from the next bar (stop already
                                                             # tested on this bar after the fill)
            if pos.get("stop_to_next") is not None and pos["stop_to_next"][1] < i:   # M5.1 Ep 01: after the
                _MG.raise_stop(pos, pos.pop("stop_to_next")[0])   # breakaway-gap add, below its bodies (X5c: not on a day trade)
            stop = pos["stop"]
            if p.ambiguous == "target" and o > stop and not pos["t1_done"] and h >= pos["t1"]:
                stop = -np.inf                        # optimistic bound: target before stop
            if o <= stop:
                tr.exits.append((ts, sd.x(o), pos["left"], "stop_gap")); pos["left"] = 0
            elif l <= stop:
                tr.exits.append((ts, sd.x(stop), pos["left"], "be" if pos["t1_done"] else "stop")); pos["left"] = 0
            elif p.mgmt in ("ladder", "unit"):
                fr = pos["fracs"]
                lv_ = pos["levels"][:len(fr)]
                if pos.get("final_T") and len(pos["levels"]) > len(fr):   # #9: the last rung is the draw
                    lv_ = pos["levels"][:len(fr) - 1] + [pos["levels"][-1]]
                xt_ = p.exit_fill_through * p.tick          # E3: a target needs N ticks of print through it
                while pos["k"] < len(lv_) and pos["left"]:
                    k = pos["k"]
                    hit_, px_ = _TP.rung_hit(pos, k, lv_[k], h, c, t, tf, p, xt_)     # Ep06.4 sd_close_hit
                    if not hit_:
                        break
                    last = k == len(lv_) - 1 and not pos.get("runner")   # Ep04.3 po3_runner
                    if last:
                        tr.final_hit = True                           # Ep04.13: every rung taken
                    q = pos["left"] if last else min(pos["left"], max(p.lot, _lots(pos["n"] * fr[k], p.lot)))
                    tr.exits.append((ts, sd.x(px_), q, f"t{k + 1}")); pos["left"] -= q
                    if (p.wick_read == "exit" and pos["left"] and pos.get("level_kinds")
                            and k < len(pos["level_kinds"]) and pos["level_kinds"][k] in ("wick", "wick_ce")):
                        pos["wick_chk"] = (i, lv_[k] + p.exit_before_pts * p.es_pt)      # A23: read the next close
                    pos["k"] += 1
                    pos["last_partial_i"] = i
                    if not pos["t1_done"]:
                        pos["t1_done"] = True
                        if p.be_on == "t1":
                            _MG.be_move(pos, p)                        # X4: + be_pad_pts / cost pad
                    if p.ladder_trail == "prior" and k >= 1 and not pos.get("day_trade"):
                        pos["stop"] = max(pos["stop"], lv_[k - 1] - p.trail_pad)
                    pos["away"] = lv_[k]
                if (pos["t1_done"] and not pos.get("be_done") and p.be_on == "expansion"
                        and pos["last_partial_i"] < i and c > lv_[0]):
                    _MG.be_move(pos, p)                                       # breakeven after expansion
                    pos["be_done"] = True
            else:
                if not pos["t1_done"] and h >= pos["t1"] + p.exit_fill_through * p.tick:
                    q = pos["left"] if pos["t2"] is None else max(p.lot, _lots(pos["left"] * p.partial, p.lot))
                    q = min(q, pos["left"])
                    tr.exits.append((ts, sd.x(pos["t1"]), q, "t1")); pos["left"] -= q
                    pos["t1_done"] = True
                    if p.be_on != "off":
                        _MG.be_move(pos, p)
                if pos["left"] and pos["t2"] is not None and pos["t1_done"] and h >= pos["t2"] + p.exit_fill_through * p.tick:
                    tr.exits.append((ts, sd.x(pos["t2"]), pos["left"], "t2")); pos["left"] = 0
            if (pos["left"] and p.mgmt in ("ladder", "unit") and p.ladder_trail == "hit" and pos.get("away") is not None
                    and not pos.get("day_trade")
                    and c >= pos["away"] + p.away_pts * p.es_pt):
                pos["stop"] = max(pos["stop"], pos["away"] - p.trail_pad)   # price left the array
                pos["away"] = None
            if pos["left"] and p.ep07_body_exit and l < pos["body_low"]:
                px = min(o, pos["body_low"])           # traded below the swing low's lowest body
                tr.exits.append((ts, sd.x(px), pos["left"], "body_low")); pos["left"] = 0
            if pos["left"] and pos.get("be_at") is not None and h >= pos["be_at"]:
                _MG.be_move(pos, p)                                       # M12.3 cc_1h_ob: BE after 2R
            if pos["left"] and p.ep07_trail and not pos.get("trailed") and not pos.get("day_trade") and h > pos["swing_body"]:
                pos["stop"] = max(pos["stop"], pos["retr_low"] - p.trail_pad)
                pos["trailed"] = True
            if (pos["left"] and (p.ce_hold or pos.get("ce_hold")) and i > pos["fill_i"] and c < pos["fvg_ce"]
                    and not pos["t1_done"]):
                tr.exits.append((ts, sd.x(c), pos["left"], "ce_close")); pos["left"] = 0
            if (pos["left"] and pos.get("bz_mt") is not None and i > pos["fill_i"]
                    and (not pos["t1_done"] or p.breaker_mt_exit_after_t1) and c < pos["bz_mt"]):
                tr.exits.append((ts, sd.x(c), pos["left"], "breaker_mt")); pos["left"] = 0   # #6 (d)
            if pos["left"] and pos.get("lvx") and i > pos["fill_i"]:
                for nm_, (lvl_, pre_t1) in pos["lvx"].items():     # levels_detectors exits: A5 q_close,
                    if (not pre_t1 or not pos["t1_done"]) and c < lvl_:   # Ep01.5 breakaway_ce, L10
                        tr.exits.append((ts, sd.x(c), pos["left"], nm_)); pos["left"] = 0   # wick_inv,
                        break                                      # A11 bpr_abort (body close)
            if pos["left"] and pos.get("exit_at") and t + tf >= pos["exit_at"]:
                tr.exits.append((ts, sd.x(c), pos["left"], "time_exit")); pos["left"] = 0   # M16.1
            if pos["left"] and pos.get("po3_open") is not None and i > pos["fill_i"]:    # T13 po3_hold
                if pos.get("po3_seen") and c < pos["po3_open"]:
                    tr.exits.append((ts, sd.x(c), pos["left"], "po3_hold")); pos["left"] = 0
                elif c > pos["po3_open"]:
                    pos["po3_seen"] = True
            if pos["left"] and p.fvg_abort and p.fvg_abort_mode == "legacy":   # X6 first build (the rule mode: manage.py)
                if pos["abort"] is not None and l < pos["abort"]:
                    tr.exits.append((ts, sd.x(min(o, pos["abort"])), pos["left"], "abort")); pos["left"] = 0
                elif max(o, c) < pos["fvg_bottom"] and i > pos["fill_i"]:
                    pos["abort"] = l                  # body closed below the gap: arm the abort
            if pos["left"] and p.pd3_exit and p.pd3_legacy:       # X7 first build (X7a list: manage.py)
                for g in sd.gaps:
                    if g.i < i and g.i >= pos["ext_i"] and g.i not in pos["broken"] and c < g.bottom:
                        pos["broken"].add(g.i)
                if len(pos["broken"]) >= 3:
                    tr.exits.append((ts, sd.x(c), pos["left"], "pd3")); pos["left"] = 0
            if (pos["left"] and pos["t1_done"] and pos.get("heavy_dead") is not None
                    and (ts + pd.Timedelta(minutes=tf)).value >= pos["heavy_dead"]):
                tr.exits.append((ts, sd.x(c), pos["left"], "htf_heavy")); pos["left"] = 0   # #7 Ep02 30m
            if pos["left"] and (p.smt_bank or p.smt_bank_against_frac or p.adr_early or p.wick_read != "off" or p.trail_breakaway):
                _TP.manage(ctx, sd, pos, tr, i, ts, p, pctx, psides, ppos)      # X3g / L16 / A23 / A6 partials
            if pos["left"]:
                pos["best"] = max(pos["best"], h)
                _MG.exits(ctx, sd, pos, tr, i, ts, p, state)       # management_exits: X6-X12, X9 time stops, D18, Ep07.5
                if pos["left"]:
                    _MG.be_modes(sd, pos, tr, i, p)                # D14 / Ep03.15 after_mss / stall / pool breakeven
                    _MG.trail_extra(sd, pos, i, p)                 # Ep03.10 first-FVG and Ep03.20 measuring-gap trails
            if (pos["left"] and tr.session in ("PRE7", "PRE8", "LON") and p.pre_flat_0830 and news(day) == "0830"
                    and t + tf >= 510):
                tr.exits.append((ts, sd.x(c), pos["left"], "pre_0830")); pos["left"] = 0     # N4: no position into the release
            if pos["left"] and tr.session == "LUNCH" and t + tf >= p.lunch_exit:
                tr.exits.append((ts, sd.x(c), pos["left"], "lunch_exit")); pos["left"] = 0   # T8: never held into the PM
            if pos["left"] and tr.session not in ("PM", "LUNCH") and p.am_exit and t + tf >= p.am_exit:
                # Ep 03 / owner #8: CLOSE (not tighten) all remaining AM-family units at the close
                # of the bar ending 12:00; "tighten" is a test-only switch [our interpretation]
                if p.am_exit_mode == "close":
                    tr.exits.append((ts, sd.x(c), pos["left"], "am_exit")); pos["left"] = 0
                elif not pos.get("am_tightened"):
                    new = max(pos["stop"], pos["basis"] / pos["n"], l - p.trail_pad)
                    pos["am_tightened"] = True
                    if new >= c:
                        tr.exits.append((ts, sd.x(c), pos["left"], "am_exit")); pos["left"] = 0
                    else:
                        _MG.raise_stop(pos, new)               # X5c: a day trade keeps its stop
            if pos["left"] and tr.session == "PM" and p.pm_done_by and pos["t1_done"] and t + tf >= p.pm_done_by:
                tr.exits.append((ts, sd.x(c), pos["left"], "pm_done")); pos["left"] = 0
            if pos["left"] and ff and pos["fill_t"] < ff and t + tf >= ff:
                tr.exits.append((ts, sd.x(c), pos["left"], "fomc_flat")); pos["left"] = 0   # N3.2: never hold into the release
            if pos["left"] and t + tf >= flat:
                tr.exits.append((ts, sd.x(c), pos["left"], "eod")); pos["left"] = 0
            if pos["left"]:                            # #12: open risk against the current stop
                eq = ctx.equity
                if eq:
                    r_now = max(0.0, (pos["basis"] / pos["n"] - pos["stop"]) * pos["left"]) / eq
                    tr.peak_risk_pct = round(max(tr.peak_risk_pct or 0.0, r_now), 5)
            if not pos["left"]:
                lost_side = _after_close(pos, trades, p, done, state, i=i, ctx=ctx) or lost_side
                pos = None
            else:                                      # new FVG after the fill: trail / add
                if p.htf_resist_live and ctx.conf is not None and p.htf_resist_cap and _TP.resist_cfg(p)[0]:
                    _resist_live(ctx, sd, pos, i, p)
                new = [g for g in sd.gaps if g.i == i and g.i - 2 > pos["fill_i"]]
                can_add = (p.adds and not pos["t1_done"] and pos["add"] is None and not pos.get("no_adds")
                           and not (chop.on and p.sloppy_mode == "stand_aside")
                           and not _EN.adds_blocked(ctx, sd, pos, i, p)                 # E12f
                           and not (state["day_loss"] and (not p.after_loss_adds or p.no_max_after_loss))   # Ep08.12
                           and not _EN.add_cut_passed(sd, pos, i, p)                     # E12e / D12
                           and not (p.late_cutoff and t >= p.late_cutoff))                # T11
                if p.pm_ep01_adds and pos.get("kind") == "pm_ep01":
                    _SM.ep01_manage(ctx, sd, pos, tr, i, p, bool(can_add))   # M5.1: the Ep 01 sequence
                    new, can_add = [], False
                if new:
                    g = new[-1]
                    if not pos.get("day_trade") and (          # X5c: a day trade keeps its initial stop
                            p.trail or (p.mgmt in ("ladder", "unit") and p.ladder_trail == "fvg" and pos["t1_done"]
                                        and pos["k"] >= p.trail_after            # Ep03.20: after N rounds of partials
                                        and g.i - 2 > pos["last_partial_i"])):   # formed since the partial
                        ref_ = (g.bottom if p.trail_ref == "gap" else
                                float(min(min(sd.o[k_], sd.c[k_]) for k_ in range(g.i - 2, g.i + 1))))   # Ep01.20 body
                        pos["stop"] = max(pos["stop"], ref_ - p.trail_pad)
                    apx = _EN.add_px(g, p)                         # E12 add_points
                    if (can_add and p.add_mode == "fvg" and _nadds(pos, tr) < len(p.adds)
                            and _SM.add_ok(sd, pos, apx, i, p)):
                        _arm_add(pos, tr, apx, i, p, ctx.equity, floor=g.bottom, g=g, pos_g=True)
                        can_add = pos["add"] is None
                if can_add and p.add_mode == "downclose" and _nadds(pos, tr) < len(p.adds):       # Ep07.5
                    _MG.downclose_add(sd, pos, tr, i, p,
                                      lambda px: (_SM.add_ok(sd, pos, px, i, p)
                                                  and _arm_add(pos, tr, px, i, p, ctx.equity, floor=pos["fvg_bottom"]) is None
                                                  and pos["add"] is not None))
                    can_add = pos["add"] is None
                if can_add and p.ob_adds and pos.get("ob_pre") and _nadds(pos, tr) < len(p.adds):
                    _ob_add(sd, pos, tr, i, p, ctx.equity)
                    can_add = pos["add"] is None
                if can_add and _nadds(pos, tr) < len(p.adds) and (p.add_on_vi or p.breaker_retest_add
                                                                 or p.add_on == "breaker"
                                                                 or p.ts_adds_breakers or p.ts_breaker_pyramid):
                    _SM.more_adds(ctx, sd, pos, tr, i, p)          # setups_models Ep05.4 / M4 / M12.2 / M4.4
                    can_add = pos["add"] is None
                if can_add and _nadds(pos, tr) < len(p.adds) and p.add_arrays:       # E12b + owner #7 htf_fvg
                    arm_ = lambda px, floor=None, extra=0.0: (_SM.add_ok(sd, pos, px, i, p)
                                                              and _arm_add(pos, tr, px, i, p, ctx.equity, floor=floor,
                                                                           extra_room=extra) is None
                                                              and pos["add"] is not None)
                    _EN.more_add_arrays(ctx, sd, pos, tr, i, p, arm_)
                    can_add = pos["add"] is None
                if can_add and p.add_on == "retest":                            # Ep01.18
                    _EN.retest_add(sd, pos, tr, i, p, lambda px: _arm_add(pos, tr, px, i, p, ctx.equity, floor=pos["fvg_bottom"]))
                    can_add = pos["add"] is None
                if can_add and (p.add_low_end or p.add_fvg_low_end or p.add_fvg_low):   # E12c / E12 / Ep04.10
                    _EN.low_end_add(sd, pos, tr, i, p, lambda px, size: _arm_add(pos, tr, px, i, p, ctx.equity, size=size))
        # --- 2. pending limit order
        held_ = state.get("fomc_held")
        if held_ is not None and t >= _NC.first_pm_minute(p):    # N3.1 fomc_observe: arm the order seen in 14:00 - fomc_pm_from
            state["fomc_held"] = None
            if pending is None and pos is None and _NC.held_valid(ctx, held_["side"], held_, i, p):
                pending = dict(held_, i=i - 1)
        if pending is not None and ff and ctx.t[pending["i"]] < ff <= t + tf:
            pending = None                           # N3 fomc_flat: nothing armed before the release rests into it
        if pending is not None and chop_before:
            pending = None                           # #10 stand aside: chop drops the order
        if pending is not None and _MG.blocked_now(state, pending["session"]):
            pending = None                           # management_exits: the session / day was stopped meanwhile
        if (pending is not None and pending["session"] not in ("PM", "LUNCH") and p.am_exit
                and t + tf >= p.am_exit):
            pending = None                           # #8 guard: no AM-family fills into 12:00
        if pending is not None:
            sd = pending["side"]
            cut = {"AM": am_hi, "PM": p.pm[1], "PRE7": 510, "PRE8": 510 if (p.am_from_0830 or (p.pre_flat_0830 and news(day) == "0830")) else 570, "PRE9": 570,
                   "NEWS": 570, "LON": 300, "LUNCH": p.lunch_win[1]}[pending["session"]]
            if pending.get("done_key", "").startswith("SB_"):
                cut = p.sb_windows[0][1] if pending["session"] == "AM" else p.sb_windows[1][1]
            if p.sb_only:                               # fills only inside the session's SB window
                sb_a, cut = p.sb_windows[0] if pending["session"] == "AM" else p.sb_windows[1]
            if pending.get("cut"):                      # setups_models: M5 / M5.1 15:45
                cut = min(cut, pending["cut"])
            ob_pre = pending.get("ob_pre", False)
            mkt = pending.get("market") or pending.get("stop_entry")
            if t >= cut or i - max(pending["i"], pending.get("anchor_i", -1)) > max(1, p.pending_minutes // tf):
                pending = None
            elif ob_pre and i - 1 > pending["i"] and sd.c[i - 1] < pending["ob_body_low"]:
                pending = None                       # #11: a close below the OB bodies (bar i-1)
            elif (ob_pre and pending.get("sw_ref") is not None and pending["sw_ref"].get("ob_void")
                  and pending["sw_ref"].get("ext_i") == pending.get("sw_ext_i")):
                pending = None                       # setups_models: the break failed the MSS gates
            elif (ob_pre and pending.get("ob_hold") and not (pending["sw_ref"].get("broke") is not None
                                                             and pending["sw_ref"].get("ext_i") == pending.get("sw_ext_i"))):
                pass                                 # ob_pre_gate "hold": no fill before the gated MSS
            elif ("release_open" in (pending.get("lvx") or {}) and i - 1 > pending["i"]
                  and sd.c[i - 1] < pending["lvx"]["release_open"][0]):
                pending = None                       # T2 (review fix): bar i-1 closed below the 08:30 open
            elif (pending.get("cancel_low") is not None and i - 1 > pending["i"]
                  and sd.l[i - 1] < pending["cancel_low"]):
                pending = None                       # setups_models M11b: the OB low traded
            elif (pending.get("no_new_extreme") and i - 1 > pending["i"] and sd.l[i - 1] < pending["ext"]):
                pending = None                       # M2.4: a new low printed before the fill
            elif (p.body_low_cancel and i - 1 > pending["i"] and sd.l[i - 1] < pending["body_low"]):
                pending = None                       # setups_models M1.3: below the swing low's bodies
            elif (p.ep07_body_exit and p.ep07_body_fixes and i - 1 > pending["i"] and sd.l[i - 1] < pending["body_low"]):
                pending = None                       # Ep07.7 pending guard: the same test cancels the waiting order
            elif (not mkt and p.run_cancel != "off" and sd.l[i] >= pending["entry"]
                  and sd.h[i] >= (pending["t1"] if p.run_cancel == "t1" else pending["levels"][-1])):
                pending = None                       # ran to target without us (D11 run_cancel loosens it)
            elif p.sb_only and t < sb_a:
                pass                                 # armed before the window: wait for it
            elif (not ob_pre and not pending.get("no_leg_wait") and p.leg_pd and p.leg_pd_at == "fill" and pending["entry"] >
                  pending["ext"] + p.leg_pd * ((pending["leg_hi0"] if pending.get("no_new_extreme") else
                                                sd.h[pending["ext_i"]:i].max()) - pending["ext"])):
                pass                                 # not yet in the leg's discount: wait (M2.4: leg high frozen)
            elif (pos is None and _NC.fill_ok(pending, t, tf) and _fill_at(sd, pending, i) is not None
                  and _retrace_ok(sd, pending, i, p)):
                o = pending
                fill = _fill_at(sd, o, i)            # a gap through the limit fills at the open
                tr = _make_trade(ctx, day, symbol, o, sd, ts, fill, i, t, p, btag)
                base_ = (1.0,) if o.get("scalp") else (o.get("fracs") or _split(p, ctx, hist, day, i, t))
                if o.get("rung_plan"):               # targets_partials: the day's split is known now
                    lv_f, kd_f, fr_f = _TP.fill_plan(o, base_, p)
                else:
                    lv_f, kd_f, fr_f = o["levels"], o.get("level_kinds"), base_
                pos = dict(trade=tr, side=sd, stop=o["stop"], t1=lv_f[0] if o.get("rung_plan") else o["t1"], t2=o["t2"],
                           left=o["shares"], n=o["shares"], basis=fill * o["shares"],
                           t1_done=False, fill_i=i, fill_t=t, add=None, fvg_bottom=o["fvg_bottom"],
                           abort=None, best=fill, ext_i=o["ext_i"], broken=set(), fvg_ce=o["fvg_ce"],
                           body_low=o["body_low"], levels=lv_f, k=0, away=None, last_partial_i=i,
                           level_kinds=kd_f, final_T=o.get("final_T", False),
                           bz_mt=o.get("bz_mt"), ob_pre=ob_pre, no_adds=o.get("no_adds", False),
                           heavy_dead=o.get("heavy_dead"), ob_add_used=set(),
                           be_at=o.get("be_at"), lvx=o.get("lvx") or {},
                           fracs=tuple(fr_f),
                           leg=o.get("leg"), bz_side=o.get("bz_side"), kind=o.get("entry_kind"),
                           exit_at=o.get("exit_at"), runner=o.get("runner", False), po3_open=o.get("po3_open"),
                           ce_hold=o.get("ce_hold", False), rungs=list(o.get("rungs") or []),
                           draw=o.get("draw"), ext=o["ext"], low_prob=o.get("low_prob", False),
                           zone_top=o.get("zone_top"), plan_shares=o.get("plan_shares", o["shares"]),
                           **_swing_ref(sd, o["ext_i"], i))
                if pos["runner"]:                    # Ep04.3: the last fraction has no target
                    lv0 = pos["levels"][:-1] if (pos["final_T"] and len(pos["levels"]) > 1) else pos["levels"]
                    pos.update(levels=lv0[:max(1, len(pos["fracs"]) - 1)], final_T=False)
                if o.get("rung_plan"):
                    tr.rungs = "|".join(f"{sd.x(v_):.2f}:{k_}:{f_:.2f}" for v_, k_, f_ in zip(lv_f, kd_f, fr_f))
                state["fill_slow_chop"] = bool(p.chop_one_win and (chop.on or _slow_day(p, ctx, hist, i)))
                _MG.init_pos(ctx, sd, pos, tr, o, i, p, state)        # management_exits: per-position data at the fill
                if p.mss_on_side == "tag" and _SM.on_side_since(sd, o, i):   # A19.4
                    tr.lv_tags = "|".join(x for x in (tr.lv_tags, "on_side") if x)
                done[o.get("done_key", o["session"])] = True
                lk = ctx.lock.get("LH" if o.get("done_key") == "LH" and "LH" in ctx.lock else o["session"])
                if lk is not None:
                    lk["traded"] = True
                pending = None
                if sd.l[i] <= pos["stop"]:           # same-bar stop (conservative)
                    tr.exits.append((ts, sd.x(pos["stop"]), pos["left"], "stop")); pos["left"] = 0
                    lost_side = _after_close(pos, trades, p, done, state, i=i, ctx=ctx) or lost_side
                    pos = None
                elif p.ep07_body_exit and p.ep07_body_fixes and sd.l[i] < pos["body_low"] < fill:   # Ep07.7 on the fill bar
                    tr.exits.append((ts, sd.x(pos["body_low"]), pos["left"], "body_low")); pos["left"] = 0
                    lost_side = _after_close(pos, trades, p, done, state, i=i, ctx=ctx) or lost_side
                    pos = None
                elif p.body_low_cancel and sd.l[i] < o["body_low"] < fill:   # M1.3 on the fill bar
                    tr.exits.append((ts, sd.x(o["body_low"]), pos["left"], "body_low")); pos["left"] = 0
                    lost_side = _after_close(pos, trades, p, done, state, i=i, ctx=ctx) or lost_side
                    pos = None
                elif (pos["bz_mt"] is not None and sd.c[i] < pos["bz_mt"]
                      and not sd.h[i] >= pos["t1"]):  # #6 (c): filled, then closed below the MT
                    tr.exits.append((ts, sd.x(sd.c[i]), pos["left"], "breaker_mt")); pos["left"] = 0
                    lost_side = _after_close(pos, trades, p, done, state, i=i, ctx=ctx) or lost_side
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
            if am_lo <= t < am_hi:
                session, w0, wa, wb = "AM", am_start, am_lo, am_hi
            elif p.lunch and p.lunch_win[0] <= t < p.lunch_win[1]:
                session, w0, wa, wb = "LUNCH", p.lunch_win[0], p.lunch_win[0], p.lunch_win[1]    # T8
            elif p.pm[0] <= t < p.pm[1]:
                session, w0, wa, wb = "PM", p.pm[0], p.pm[0], p.pm[1]
            else:
                continue
        ctx.cur_session = session
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
        if session == "PM":
            w0 = _NC.pm_start(p, w0, trades)                  # T9 pm_bad_am_start
        why_ = _NC.gate(ctx, p, day, session, t, i, wb, trades)
        if why_ is not None:                                  # N3.2 / N5.4 / T8 / T9 per-bar gates
            _f(why_)
            continue
        jb_side, jb_wait = _NC.judas_gate(ctx, p, day, drv, i, t)    # M9 / M9.1 / M9.2
        if jb_wait:
            _f("x_news_judas_wait")
            continue
        if (session == "PM" and p.last_hour_strict and t >= p.last_hour[0]
                and not (p.last_hour_sweet[0] <= t < p.last_hour_sweet[1])):
            continue                                  # #1 test: last hour = sweet spot only
        done_key = session
        if done[session] and p.sb_setup and _in_sb(t, p) and not state.get("day_done"):
            done_key = "SB_" + session                # the Silver Bullet window's own trade
            done.setdefault(done_key, False)
        lh_slot = (session == "PM" and _SM.lh_on(p, "last_hour_own_slot")
                   and p.last_hour[0] <= t < p.last_hour[1])
        if lh_slot:                                   # setups_models M5.2 / Ep01.13: own LH slot
            done_key = "LH"
            done.setdefault("LH", False)
        skip_main = t < w0 or done[done_key] or pos is not None
        if _MG.blocked_now(state, session):
            continue                                  # X7c / X12 / X13a / X14b / X14d: the session or the day is stopped
        if (session == "PM" and p.pm_consol_exit and t >= p.pm_consol_exit and pos is None
                and _MG.consol_day(ctx, i, p)):
            continue                                  # X11c: a consolidation PM starts nothing after the exit time
        pmr = (p.pm_reversal and session == "PM" and pos is None and pending is None and t >= w0
               and not done.get("PMR"))
        if skip_main and not pmr:
            continue
        if (p.day_filter and blocked(day, session, p, t)) or (p.skip_news and news(day) != "none"):
            continue
        sl_now = set(sl_day if session == "PM" else sl_all_day)
        if chop.on:
            sl_now.add("chop")
        if p.sloppy_mode == "stand_aside" and sl_now:
            continue                                  # #10: no new entries while sloppy
        ctx.cur_sloppy = "|".join(sorted(sl_now))
        if pmr:                                       # setups_models M6: after the objective
            done.setdefault("PMR", False)
            ctx.cur_lock, ctx.cur_bias, armed = None, 0, False
            for sd in sides:
                if sd.sign in block_side.get("year_end", ()):
                    continue
                o_ = _SM.pm_reversal(ctx, sd, i, p, _risk_mult(state, session, p))
                if o_ is not None:
                    pending, armed = o_, True
                    break
            if skip_main or armed:
                continue
        lks = "LH" if (lh_slot and "LH" in lock_t) else ("AM" if session == "LUNCH" else session)   # LH: its own lock;
                                                      # T8: the lunch session carries the AM's draw
        lk = ctx.lock.get(lks) if lock_t else None
        if lock_t and lks in lock_t and lk is None:
            continue                                  # #9: not locked yet - nothing to trade toward
        if lk is not None and lk["delivered"]:
            if not (lh_slot and p.lh_no_lock and not _SM.lh_on(p, "lh_htf_done_skip") and not p.pm_last_hour_model):
                continue                              # #9: the session's draw delivered - done
            lk = None                                 # lh_no_lock (the first build, a switch): the LH
                                                      # slot trades on without a locked draw
        if p.ipda_eq_day == "skip":                   # B21: range day until the first release
            if session not in state.setdefault("ipda_eq", {}):
                state["ipda_eq"][session] = _ipda_eq(ctx, p, i)
            rel = _NC.releases(day, p)
            if state["ipda_eq"][session] and (not rel or t < min(rel)):
                continue
        ctx.cur_no_draw = False
        if p.no_draw or p.skip_no_draw:               # B1: no draw within reach = consolidation
            if session not in state.setdefault("no_draw", {}):
                state["no_draw"][session] = _no_draw(ctx, p, session, i, bias_by_cut)
            ctx.cur_no_draw = state["no_draw"][session]
            if p.skip_no_draw and ctx.cur_no_draw:
                continue
        for sd in sides:
            sname = "long" if sd.sign > 0 else "short"
            if (not p.reverse_after_loss and lost_side is not None and sname != lost_side
                    and (not p.lost_side_session or state.get("lost_fam") == _MG.fam(session))
                    and not state["only_side"].get(session)):
                continue                              # no reversals after a loss (X13a: lost_side_session = this session only;
                                                      # reverse_in_session is the one reversal the lock lets through)
            os_ = state["only_side"].get(session)
            if os_ and sd.sign != os_:
                continue                              # X13a reverse_in_session: the opposite side only
            rc_ = state["re_ctx"].get(session)
            if rc_ is not None and rc_.get("pending") and p.reentry_gate and sname != rc_["side"]:
                continue                              # X13b: a re-entry is the same direction only
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
            if jb_side and sd.sign == jb_side:
                _f("x_news_judas")
                continue                              # M9 / M9.2: the first run after the release is the losing side
            why_ = _NC.side_filter(ctx, p, session, sd.sign, i, t)
            if why_ is not None:
                _f(why_)
                continue                              # T4 or_bias / or_wide, T9 pm_continue_am
            if lk is not None and lk["side"] and sd.sign != lk["side"]:
                continue                              # #9: trade only toward the locked draw
            if state.get("flip") and sd.sign != state["flip"]:
                continue                              # B8f stop_flip: the other side for the day
            if p.late_cutoff and t >= p.late_cutoff and _MG.is_fade(ctx, sd, lk, i):
                continue                              # T11 (026 ~1:59:50): no fades in the last 15 minutes
            smtb = _MG.smt_bias(ctx, i, p) if p.smt_bias != "off" else 0
            if p.smt_bias == "filter" and smtb and sd.sign != smtb:
                continue                              # B18.3: against the SMT bias
            ctx.cur_lock = lk if (lk is not None and lk["side"] == sd.sign) else None
            ctx.cur_bias = lk["side"] if (lk is not None and lk["side"]) else (want or 0)
            o_ = _scan(ctx, sd, i, p, session, w0, pctx, psides, ppos, _risk_mult(state, session, p))
            if o_ is not None and rc_ is not None and rc_.get("pending") and not _MG.reentry_order_ok(o_, sd, rc_, p):
                _f("x_reentry_gate")
                o_ = None                             # X13b: no restored sweep / FVG after the stop
            if o_ is not None and smtb:
                o_["lv_tags"] = "|".join(x for x in (o_.get("lv_tags", ""), "smt_bias_agree" if sd.sign == smtb
                                                     else "smt_bias_against") if x)
            if o_ is not None:
                o_ = _NC.post_order(ctx, sd, i, p, session, o_, hist)    # T4 / T7 / T9 / Ep07.8 filters and tags
            if o_ is not None:
                if done_key.startswith("SB_"):
                    o_.update(done_key=done_key, setup="sb_" + session.lower())
                elif done_key == "LH" and "done_key" not in o_:
                    o_.update(done_key="LH")
                if (pending is not None and pending.get("ob_pre") and not o_.get("ob_pre")
                        and pending["side"] is sd and not p.ob_entry_cancel_on_mss
                        and pending["entry"] <= o_["entry"]):
                    continue                          # #11 "both": keep the lower entry (side space)
                if _NC.observing(p, day, session, t):
                    state["fomc_held"] = o_             # N3.1: seen during the FOMC observation, armed from fomc_pm_from
                    continue
                pending = o_
                if log is not None:
                    log.append((ts, symbol, session, sname, o_["swept"], sd.x(o_["entry"]),
                                sd.x(o_["stop"]), sd.x(o_["t1"])))
    ctx.cur_session = ""                                  # (T8: the extras' _targets must not see the last window)
    n_main = len(trades)
    if p.ma_deuce:
        from .pre_open import run_ma_deuce
        trades += run_ma_deuce(ctx, hist, p, day, symbol, btag, sides)
    if p.sb_model:
        from .sb_model import run_sb
        trades += run_sb(ctx, sides, p, day, symbol, blocked, btag)
    if _out is not None:
        _out["extras"] = list(trades[n_main:])
    if pos is not None:   # data ended early
        tr = pos["trade"]
        if not live:
            tr.exits.append((ctx.idx[-1], pos["side"].x(pos["side"].c[-1]), pos["left"], "eod"))
            _after_close(pos, trades, p, done, state, i=len(ctx.t) - 1, ctx=ctx)     # review fix: the risk state / day-loss see this close too
        else:
            trades.append(tr)
    if state["rs"] is not None and (p.ma_deuce or p.sb_model):
        _EN.replay_risk_state(state["rs"], ctx.risk_view["rs0"], trades, p)   # E10: carried state in time order
    if locks is not None:
        locks += [dict(lk, symbol=symbol, marked=len(lk["marked"])) for lk in all_locks + list(ctx.lock.values())]
    if trades:
        nt_ = _NC.day_tags(day, p)                         # news_calendar_times: the day's news tags on every trade
        for tr_ in trades:
            tr_.news_tags = nt_
    return trades


def _no_draw(ctx, p, session: str, i: int, bias_by_cut: dict | None) -> bool:
    """B1 (038 ~47:04; 050 ~8:01) [our interpretation]: at the session start, no marked level (the
    #9 mark-up: pools, gaps, ORGs, HTF draws) within no_draw_adr x ADR5 of price on either side ->
    the market has nothing to run or rebalance near by and is expected to consolidate."""
    t_lock = {"AM": 570, "PM": 810}.get(session, int(ctx.t[i]))
    t_lock = min(t_lock, int(ctx.t[i]))      # review fix: never past the current bar (the 09:30 open is
                                             # read at a 09:30 lock only once the 09:30 bar is in)
    rows = bias_by_cut or {}
    cut = max((m for m in rows if m <= t_lock), default=None)
    lk = mark_levels(ctx, rows.get(cut) if cut is not None else None, t_lock, session, p)
    adr = adr5(getattr(ctx, "hist", [])[-5:])
    if adr is None:
        return False
    reach = p.no_draw_adr * adr
    return not any(abs(v - lk["px"]) <= reach for v, *_ in lk["marked"])


def _arm_add(pos, tr, px, i, p, eq, floor=None, g=None, pos_g=False, size=None, extra_room=0.0):
    """#12: an add at `px` (side space) sized by the adds fraction, shrunk so the open risk
    (against the current stop; never negative) stays within the total cap (1.3%).
    floor      the array's bottom: add_hold cancels the add on a body close below it (E12b)
    g          the add's FVG: add_body_stop (Ep01.19) moves the stop under its bodies after the fill;
               pos_g remembers it for add_low_end (E12c)
    size       an explicit quantity (E12c: the smallest earlier add)
    extra_room extra open risk (fraction of equity) above the total cap (owner #7 htf_add_extra_risk_pct)
    E11 max_contracts_total caps the units; E1 add_order "market" fills at the open after a retest."""
    k = _nadds(pos, tr)
    base = pos.get("plan_shares") or tr.shares        # a ladder trade: the full planned size, not rung 0
    q = _lots(base * p.adds[min(k, len(p.adds) - 1)], p.lot) if size is None else size
    at_risk = max(0.0, pos["basis"] - pos["stop"] * pos["n"])
    d = px - pos["stop"]
    if d <= 0:
        return
    if not _SM.add_pd_ok(pos, px, p):
        _f("x_add_not_in_pd")                          # M2.6 add_in_pd: every add path, not only add_ok
        return
    room = _total_cap(p, eq) + extra_room * eq - at_risk
    if d * q > room:
        q = _lots(max(room, 0.0) / d, p.lot)
    q = _EN.cap_add(q, pos["n"], p)
    if q >= p.lot and q >= 1:
        pos["add"] = dict(px=px, q=q, i=i, market=p.add_order == "market",
                          hold=floor if (p.add_hold and floor is not None) else None)
        if g is not None and p.add_body_stop:         # Ep01.19: under the bodies of the add's FVG candles
            pos["add"]["stop_to"] = float(min(min(pos_sd(pos).o[k_], pos_sd(pos).c[k_])
                                              for k_ in range(g.i - 2, g.i + 1))) - p.trail_pad
        if pos_g and g is not None:
            pos["last_add_g"] = (float(g.top), float(g.bottom), int(g.i))


def pos_sd(pos):
    return pos["side"]


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
    if not _SM.add_ok(sd, pos, top, i, p):           # setups_models add rules (M2 / Ep05.4)
        return
    if sd.l[j:k + 1].min() >= pos["stop"] and sd.c[i] > top:
        pos["ob_add_used"].add(k)
        _arm_add(pos, tr, top, i, p, eq)


def _resist_live(ctx, sd, pos, i, p):
    """#7 htf_resist_live: recompute the cap at bar i's close and trim the remaining rungs
    (applies from bar i+1)."""
    now = ctx.idx[i] + pd.Timedelta(minutes=ctx.tf)
    src = tuple(CF_SRC[x] for x in p.htf_resist_src)
    r = ctx.conf.resistance(now, sd.x(sd.c[i]), sd.sign, _TP.resist_cfg(p)[0], src)
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
            lk = mark_levels(ctx, row, tl, "PM" if s_ == "LH" else s_, p, spent)   # LH: a PM mark-up
            lk["session"] = s_
            lk = _NC.carry_lock(ctx, p, s_, lk)                  # T8 pm_carry_draw
            ctx.lock[s_] = lk
            if lk["side"] == 0 and p.draw_lock_neutral == "skip":
                done[s_] = True
    for s_, lk in list(ctx.lock.items()):
        if not lk["side"] or lk["delivered"]:
            continue
        if lk["name"] == "org_far" and _org_break(ctx, p, i):
            # L7 (review fix): the ORG acted as a breakaway (no attempt by 09:30 + org_break_min) -
            # its far edge is no longer the draw: the lock as marked at its time without it
            nl = mark_levels(ctx, (bias_by_cut or {}).get(lk["t_lock"]), lk["t_lock"], "PM" if s_ == "LH" else s_, p,
                             spent, org_pref=False)
            nl["session"] = s_
            nl.update(org_break_i=i, traded=lk["traded"])   # (the lock report shows the replacement)
            lk = nl
            ctx.lock[s_] = lk
            if lk["side"] == 0:
                if p.draw_lock_neutral == "skip":
                    done[s_] = True
                continue
        hit = ctx.h[i] >= lk["target"] if lk["side"] > 0 else ctx.l[i] <= lk["target"]
        if hit:
            lk.update(delivered=True, delivered_t=ctx.idx[i], delivered_i=i)
            spent.append(lk["target"])
            _f("x_draw_delivered")
            if pending is not None and ("LH" if pending.get("done_key") == "LH" else pending["session"]) == s_:
                pending = None
            if p.draw_relock:                         # test: lock the next draw from here
                all_locks.append(lk)
                nl = mark_levels(ctx, None, int(t + ctx.tf), "PM" if s_ == "LH" else s_, p, spent)
                nl["session"] = s_
                ctx.lock[s_] = nl
                if nl["side"] == 0 and p.draw_lock_neutral == "skip":
                    done[s_] = True
            else:
                done[s_] = True
                done["SB_" + s_] = True
    return pending


def _attach_meta(ctx, meta, p, symbol):
    """#13: per-bar adj / contract for the day frame, the roll-day tag and the round step."""
    ctx.adj = ctx.contract = ctx.roll_at = None
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
        ev = []                                       # N7.5: roll events from the prior 18:00
        if "roll" in seg:
            ev += list(seg.index[seg["roll"].astype(bool).values])
        if "instrument_id" in seg and len(seg):
            iid = seg["instrument_id"].values
            ch = np.flatnonzero(iid[1:] != iid[0])
            if len(ch):
                ev.append(seg.index[ch[0] + 1])
        if ev:
            ctx.roll_day = True
            ctx.roll_at = int(ctx.idx.searchsorted(min(ev)))   # the bar from which it is known
    ctx.real_px = ctx.adj is not None and p.price_frame == "front_month"
    ctx.round_from = p.round_pool_from
    if p.round_pools and ctx.adj is not None and p.price_frame != "back_adjusted":
        ctx.round_step = p.round_pool_step_pts or ROUND_STEP.get(symbol.upper(), 0.0)


def _sell_side(ctx: DayCtx, sd: Side, session: str, i: int | None = None,
               extra: bool = False, p: "Params | None" = None) -> dict[str, float]:
    keys = ("pdl1", "pdl2", "pdl3") if sd.sign > 0 else ("pdh1", "pdh2", "pdh3")
    out = {k: sd.x(ctx.pd[k]) for k in keys if k in ctx.pd}
    if session in ("PRE7", "PRE8", "PRE9", "NEWS", "LON"):
        m = {"PRE7": 420, "PRE8": 500, "LON": getattr(ctx, "lon_start", 120)}.get(session, 540)
        if m in ctx.pre_at:
            hi, lo = ctx.pre_at[m]
            out["overnight"] = sd.x(lo if sd.sign > 0 else hi)
        for name in ("london", "prev_pm"):
            if name == "london" and session == "LON":
                continue                     # the London range is still being made (complete at 05:00)
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
    if session in ("AM", "LUNCH"):
        k = "pml" if sd.sign > 0 else "pmh"
        if k in ctx.pd:
            out["premarket"] = sd.x(ctx.pd[k])
        if session == "LUNCH" and getattr(ctx, "am_lunch_hl", None) is not None:   # T8: the AM range, complete before
            out["am_session"] = sd.x(ctx.am_lunch_hl[1] if sd.sign > 0 else ctx.am_lunch_hl[0])   # the lunch session
        if extra:
            for name in ("london", "prev_pm"):
                if name in ctx.sess:
                    hi, lo, _ = ctx.sess[name]
                    out[name] = sd.x(lo if sd.sign > 0 else hi)
        if ctx.or_hl is not None and i is not None and ctx.t[i] >= ctx.or_end:
            out["opening_range"] = sd.x(ctx.or_hl[1] if sd.sign > 0 else ctx.or_hl[0])
        o60 = getattr(ctx, "or60", None)           # M12.3 or60 turtle soup: the 09:30-10:30 range
        if o60 is not None and i is not None and ctx.t[i] >= 630 and p is not None and p.turtle_soup == "or60":
            out["or60"] = sd.x(o60[1] if sd.sign > 0 else o60[0])
    elif ctx.am_hl:
        out["am_session"] = sd.x(ctx.am_hl[1] if sd.sign > 0 else ctx.am_hl[0])
        if extra and "lunch" in ctx.sess and i is not None and ctx.t[i] >= ctx.sess["lunch"][2]:
            hi, lo, _ = ctx.sess["lunch"]
            out["lunch"] = sd.x(lo if sd.sign > 0 else hi)
    if p is not None and i is not None and hasattr(ctx, "ipda"):
        _lv_sell_side(ctx, sd, session, i, p, out, extra)        # levels_detectors pools
    if p is not None and i is not None and (p.smt_entry or p.pm_judas_array):
        _SM.extra_pools(ctx, sd, session, i, p, out)             # setups_models M16.1 / M7.3
    return out


FUNNEL = None   # set to a collections.Counter to count how setups are found and rejected


def _f(key):
    if FUNNEL is not None:
        FUNNEL[key] += 1


def _level_intact(ctx, l, i, k, v, session, tk: float = 0.0) -> bool:
    """A sell-side level (side space) not traded through between its creation and bar i-1
    (A2: through = at least tk below it; tk = 0 any print below)."""
    a = _level_created(ctx, k, session)
    return k.startswith(("rel_eq", "round")) or i <= a or not _thru(l[a:i].min(), v, tk)


def _level_created(ctx, k: str, session: str) -> int:
    """The bar from which sell-side pool `k` exists (shared by _level_intact and _smt)."""
    at = lambda m: ctx.start + int(np.searchsorted(ctx.t[ctx.start:], m))
    if k.startswith("swing_low"):          # M1.2 fix: from the bar after the swing low itself
        a = int(k[len("swing_low"):]) + 1
    elif k == "org_close" or k.startswith("org_t_"):
        a = at(570)                         # levels_detectors: today's ORG (from 09:30)
    elif k.startswith(("today_", "m3")):
        a = at(810) if session == "PM" else at(570)    # known at the session start
    elif k == "or_alt":
        a = at(ctx.or_alt[0])
    elif k == "l0500":
        a = at(570)                         # setups_models M16.1: the 05:00-09:30 low, from 09:30
    elif k == "pm_judas_array":
        a = at(810)                         # setups_models M7.3
    elif k == "am_session" and session == "LUNCH":
        a = at(getattr(ctx, "am_lunch_end", 660))      # T8 (the AM range ends at p.am[1])
    elif k == "am_session" and session == "PM":
        a = at(min(810, getattr(ctx, "am_end", 810)))
    elif k.startswith("news_range_"):
        a = ctx.news_dr[int(k[len("news_range_"):])]["made"]
    elif k == "news_range" and 510 in getattr(ctx, "news_dr", {}):
        a = ctx.news_dr[510]["made"]
    else:
        created = ctx.start if session in ("AM", "LUNCH") else at(810)
        a = {"am_session": created, "lunch": created, "opening_range": at(ctx.or_end),
             "london": at(300), "or60": at(630),
             "news_range": getattr(ctx, "news_made", at(540))}.get(k, ctx.start)
    return a


def _scan(ctx, sd: Side, i, p: Params, session, w0, pctx, psides, ppos, risk_mult=1.0):
    """Advance this side's sweep machine at bar i (_scan_core); with the M12.3 cc_limit / M12.4
    external turtle-soup variants, also their resting-limit setups (not sweep-driven)."""
    o_ = _scan_core(ctx, sd, i, p, session, w0, pctx, psides, ppos, risk_mult)
    if o_ is None and p.turtle_soup == "cc_limit" and sd.sweep is None:
        o_ = _cc_limit(ctx, sd, i, p, session, risk_mult)
    elif o_ is None and p.turtle_soup == "external":
        o_ = _external(ctx, sd, i, p, session, risk_mult)
    if o_ is None and (p.pm_ep01 or p.moc_run or p.ir_entries or p.cc_swings in ("failure", "both")):
        o_ = _SM.extra_setups(ctx, sd, i, p, session, risk_mult)   # setups_models non-sweep setups
    return o_


def _mss_ref(ctx, sd, sw, i, p):
    """A1 MSS reference (010 ~41:31: the parent swing): the last mss_ref-tier swing high before the
    sweep extreme known by bar i; mss_ref_fallback "lower" tries the lower tiers, then (like
    "highest") the highest high of the 3*pivot_n bars before the extreme (the old rule); "none" =
    no reference. Returns (ref_i, ref, real_pivot) or None."""
    if p.mss_ref in ("parent", "origin", "origin_max") or p.mss_ref_sibi or p.mss_ref_tf:
        r = _SM.mss_ref(ctx, sd, sw, i, p)      # setups_models A19 / Ep08.4 / Ep07.6 / Ep08.16
        if r is not None:
            return r
    tiers = ("stl", "itl", "ltl")
    base = p.mss_ref if p.mss_ref in tiers else "stl"
    t0 = tiers.index(base)
    order = [base] + (list(reversed(tiers[:t0])) if p.mss_ref_fallback == "lower" else [])
    for tier in order:
        hs = sd.ph if tier == "stl" else sd.tiers()[tier][0]
        refs = [q for q in hs if q.i < sw["ext_i"] and q.known <= i]
        if refs:
            return refs[-1].i, refs[-1].price, True
    if p.mss_ref_fallback == "none":
        return None
    a = max(ctx.start, sw["ext_i"] - 3 * p.pivot_n)
    if a >= sw["ext_i"]:
        return None
    ref_i = a + int(np.argmax(sd.h[a:sw["ext_i"]]))
    return ref_i, sd.h[ref_i], False


def _ir_in_leg(sd, sw, i, p) -> bool:
    """A7: an immediate rebalance printed in the leg from the sweep extreme through bar i."""
    return any(sw["ext_i"] + 2 <= k <= i for k in sd.irs(0.25 * p.es_pt))


def _breaker(ctx, sd, sw, ref_i, real_ref, i, p):
    """A13 breaker zone at bar i (owner #14 helper L.breaker_zone) with the levels_detectors rules:
    A13.1 / Ep01.6 `breaker_ll` (real pivots, L2 < L1, a body close above the real H),
    `breaker_cand_to` (the candle from the L1 -> sweep-extreme leg or the L1 -> H leg), A13.5
    `breaker_time` (H, L2 and the break in one session block; "all" adds L1), and #6 MT respect."""
    l, h, c = sd.l, sd.h, sd.c
    l1 = [q for q in sd.pl if q.i < ref_i and q.known <= i]
    a0 = l1[-1].i if l1 else max(0, ref_i - p.pivot_n)
    if p.breaker_ll:
        if not l1 or not real_ref or not sw["ext"] < l1[-1].price:
            _f("x_breaker_ll")
            return None
        if not (c[sw["broke"]:i + 1] > h[ref_i]).any():
            _f("x_breaker_ll")
            return None
    if p.breaker_time != "off":
        bars = [ref_i, sw["ext_i"], sw["broke"]] + ([a0] if p.breaker_time == "all" else [])
        if len({L.session_block(ctx.t[k]) for k in bars}) > 1:
            _f("x_breaker_time")
            return None
    to = sw["ext_i"] if p.breaker_cand_to == "ext" else ref_i
    bz = L.breaker_zone(sd.o, h, l, c, a0, to, i, "bull", p.breaker_zone, p.breaker_mt_mode)
    if bz is not None and p.breaker_mt_respect and (c[sw["broke"] + 1:i + 1] < bz.mt).any():
        _f("x_breaker_mt_lost")
        return None                    # #6 (a): a body close below the breaker MT - breaker lost
    return bz


def _breaker_order(ctx, sd, sw, bz, i, p, session, risk_mult):
    """A13.4 / Ep01.6 / Ep05.5 breaker entry (breaker_entry): a limit at the breaker top, the stop
    beyond the sweep extreme, cancelled / exited on a body close below the breaker MT (#6)."""
    sw["bz_sent"] = True
    entry = bz.top
    stop = sw["ext"] - p.pad
    tags = dict(unicorn=False, fvg_bottom=bz.bottom, fvg_ce=bz.mt, entry_kind="breaker", mitigation=False,
                propulsion=False, unicorn_side="",
                bz_top=float(max(sd.x(bz.top), sd.x(bz.bottom))), bz_bottom=float(min(sd.x(bz.top), sd.x(bz.bottom))),
                bz_mt=bz.mt if p.breaker_mt_respect else None)
    return _finish_order(ctx, sd, i, p, session, sw, entry, stop, risk_mult,
                         sd.h[sw["ext_i"]:i + 1].max(), tags, pctx_free=True)


def _fvg_wait_from(sw) -> int:
    """The bar the no-FVG timeout (fvg_wait) runs from: the MSS bar, or with Ep04.7
    mss_on_side="require" ready, the SECOND break (review fix: the first one emptied the leg-2
    gap list at once unless its FVG already existed on the second-break bar)."""
    if sw.get("leg2_from") is not None and sw.get("broke2") is not None:
        return sw["broke2"]
    return sw["broke"]


def _smt_window_ok(p, t: int) -> bool:
    """B18.2: SMT only inside smt_windows (+ 05:00-09:30 with smt_pre); no windows = any time
    (review fix: smt_pre alone used to narrow "any time" to 05:00-09:30)."""
    if p is None or not p.smt_windows:
        return True
    wins = tuple(p.smt_windows) + (((300, 570),) if p.smt_pre else ())
    return any(a <= t < b for a, b in wins)


def _fvg_state(sd, g, i) -> str:
    """A5 state of a gap at bar i (021 ~12:28; 050 ~30:29): "open" untouched since it formed,
    "repriced" traded into, "rebalanced" traded through its far edge (and left: still open by
    closes, which the caller requires)."""
    lo = sd.l[g.i + 1:i + 1].min(initial=np.inf)
    if lo > g.top:
        return "open"
    return "rebalanced" if lo <= g.bottom else "repriced"


def _scan_core(ctx, sd: Side, i, p: Params, session, w0, pctx, psides, ppos, risk_mult=1.0):
    """Advance this side's sweep -> (OB before the break | MSS -> FVG) machine at bar i;
    return an order or None."""
    l, h, c = sd.l, sd.h, sd.c
    tol = p.eq_tol_pts * p.es_pt
    tk = _tick(p)
    lv = _sell_side(ctx, sd, session, i, p.extra_pools, p)
    for k, eq in enumerate(_eq_levels(sd, i - 1, tol, lows=True, p=p)):
        lv[f"rel_eq_lows{k}"] = eq
    sw = sd.sweep
    if sw is not None and sw["session"] != session:
        sw = sd.sweep = None
    intact = lambda k, v: _level_intact(ctx, l, i, k, v, session, tk)
    lo_i = min(sd.o[i], c[i]) if p.sweep_body else l[i]       # A4 sweep_body: a BODY must trade through
    hit = [(k, v) for k, v in lv.items() if _thru(lo_i, v, tk) and intact(k, v)]
    if p.eq_pref == "require":                   # Ep06.7: only relative equal lows are liquidity
        hit = [kv for kv in hit if kv[0].startswith("rel_eq")]
    if sw is None and hit:
        eqh = [kv for kv in hit if kv[0].startswith("rel_eq")]
        if p.eq_pref == "rank" and eqh:          # Ep06.7: rel-eq pools win (best-ranked with eq_rank)
            k, v = eqh[0] if p.eq_rank else min(eqh, key=lambda kv: kv[1])
        else:
            k, v = min(hit, key=lambda kv: kv[1])
        sw = sd.sweep = dict(session=session, name=("rel_eq_lows" if sd.sign > 0 else "rel_eq_highs") if k.startswith("rel_eq") else k,
                             level=v, key=k, ext=l[i], ext_i=i, broke=None, sweep_i=i)
        sw["smt"] = _smt(ctx, sd, i, k, v, session, pctx, psides, ppos, p)
        sw["smt2"] = _smt(ctx, sd, i, k, v, session, *ctx.partner2, p) if getattr(ctx, "partner2", None) else None
        _f("1_sweep")
    if sw is None:
        return None
    if l[i] < sw["ext"]:
        sw.update(ext=l[i], ext_i=i, broke=None, ob=None, ob_sent=False, ob_frozen=False, ts_sent=False,
                  ts_ok=False, follow_i=None, wce_sent=False, cisd_sent=False, leg2_from=None, broke2=None,
                  on_side=False, f1=None, reaper_dead=False, ob_void=False, adv_pre_sent=False, smt_sent=False)
    if p.ts_gate_mss and sw["broke"] is None:    # M12.5: the depth/back test gates the MSS / OB model
        if not sw.get("ts_ok"):
            sw["ts_ok"] = L.turtle_soup(l, c, sw["level"], sw["ext_i"], i, p.ts_max_pts * p.es_pt, p.ts_back_bars)
        if not sw["ts_ok"]:
            if sw["level"] - sw["ext"] > p.ts_max_pts * p.es_pt or i - sw["ext_i"] >= p.ts_back_bars:
                sd.sweep = None                  # too deep, or no close back above in time
                _f("x_ts_gate")
            return None
    # reference: the swing high that led into the sweep extreme (A1 tiers: mss_ref)
    rr = _mss_ref(ctx, sd, sw, i, p)
    if rr is None:
        return None
    ref_i, ref, real_ref = rr
    if p.mss_cisd:                     # the open of the down-close series into the low
        blk = L.order_block_blend(sd.o, h, l, c, sw["ext_i"] - 5, sw["ext_i"], "bull")
        if blk is not None:
            ref = float(sd.o[blk.src])
    if sw["broke"] is None:
        if (p.mss_max_bars or p.speed_check) and _SM.drop_before_break(ctx, sd, sw, i, p):
            sw["ob_void"] = True              # review fix (owner #11 x gates): the OB order armed
            sd.sweep = None                   # before the break is cancelled with the sweep
            return None                       # setups_models Ep07.6 / M1.3 timing
        order = None
        if p.smt_entry or p.cisd_ob_entries or p.wick_ce_entries:   # setups_models M16.1 / M11b / M11c
            order = _SM.pre_break(ctx, sd, sw, i, p, session, risk_mult, ref)
            if order is not None:             # review fix: the model's own entry is not replaced by
                sw["ob_sent"] = True          # the #11 OB order armed on a later bar [our interpretation]
        if order is None and p.adv_breaker_pre and not sw.get("adv_pre_sent"):     # M4.3 bias on side
            order = _SM.adv_breaker_pre(ctx, sd, sw, i, p, session, risk_mult, ref_i, ref, real_ref)
            if order is not None:
                sw["ob_sent"] = True          # [our interpretation] it takes the OB order's place
        if order is None and p.ob_entry in ("pre_break", "both") and not sw.get("ob_sent"):
            order = _ob_pre(ctx, sd, sw, i, p, session, risk_mult)      # owner #11 (default)
        if order is None and p.turtle_soup and not sw.get("ts_sent"):
            order = _turtle(ctx, sd, sw, i, p, session, risk_mult)      # M12 core (off)
        fi, brk_i = sw.get("follow_i"), i
        gate_fail = False                # a close through the reference that the MSS gates reject
        if fi is not None:               # A20 disp_follow: the bar after the break must follow
            sw["follow_i"] = None
        if fi is not None and i == fi + 1 and c[i] > c[fi]:
            brk, brk_i = True, fi
        else:
            gate_fail = fi is not None   # the follow-through failed
            raw = i > sw["ext_i"] and (h[i] if p.mss_mode == "wick" else c[i]) > ref
            brk = raw
            if brk and p.displacement_mult:  # M1.2 option: the breaking candle must displace
                body = abs(c[i] - sd.o[i])
                prev = np.abs(c[max(0, i - 10):i] - sd.o[max(0, i - 10):i])
                brk = len(prev) == 0 or body >= p.displacement_mult * float(prev.mean())
                if not brk and p.imm_rebalance_disp == "or" and i > sw["ext_i"] and \
                        (h[i] if p.mss_mode == "wick" else c[i]) > ref and _ir_in_leg(sd, sw, i, p):
                    brk = True               # A7: an immediate rebalance is displacement too
            if brk and p.imm_rebalance_disp == "require" and not _ir_in_leg(sd, sw, i, p):
                brk = False                  # A7 switch: the shift must carry an immediate rebalance
                _f("x_no_imm_rebalance")
            if brk:                          # setups_models A20 / M0.4 / Ep07.6 / A19.2 / Ep01.22
                brk = _SM.break_ok(ctx, sd, sw, i, p, ref, lv, tol, tk)
            if raw and not brk:
                gate_fail = True
            if brk and p.disp_follow:
                sw["follow_i"], brk = i, False
        if gate_fail and p.ob_pre_gate == "cancel":
            # review fix (owner #11 x setups_models MSS gates): the break the OB order was armed for
            # failed the displacement / MSS-validity gates - the pending OB order of this sweep is
            # cancelled at the next bar (run_day, before any fill there) [our interpretation]
            sw["ob_void"] = True
            _f("x_ob_pre_gate")
        if brk:
            sw["broke"] = brk_i
            _f("2_mss")
            o2 = None                        # setups_models orders placed at the break
            if p.cc_swings in ("breaker", "both"):
                o2 = _SM.cc_breaker_order(ctx, sd, sw, i, p, session, risk_mult, ref)
            if o2 is None and p.adv_breaker:
                o2 = _SM.adv_breaker_order(ctx, sd, sw, i, p, session, risk_mult, ref_i, ref, real_ref)
            if o2 is not None:
                sd.sweep = None
                return o2
            if p.ob_entry == "pre_break":
                sd.sweep = None               # #11: no FVG entry after the break in this mode
                return order
            if order is not None:
                return order
        else:
            return order
    if p.mss_on_side == "require":            # setups_models Ep04.7 (mss_count 2)
        st_ = _SM.on_side_wait(ctx, sd, sw, i, p, p.fvg_wait)
        if st_ == "drop":
            sd.sweep = None
            _f("x_on_side")
        if st_ is not None:
            return None
    if p.reaper:                              # setups_models A24.2
        r_ = _SM.reaper_order(ctx, sd, sw, i, p, session, risk_mult, ref_i, real_ref, p.fvg_wait)
        if r_ == "drop":
            sd.sweep = None
            return None
        if r_ == "wait":
            return None
        if r_ is not None:
            sd.sweep = None
            return r_
    gaps = [g for g in sd.gaps if g.i <= i and g.i - 2 >= sw["ext_i"]]
    if sw.get("ev_g") is not None:        # E5 evolve_fvg / wait_structural: only a NEWER gap re-arms
        gaps = [g for g in gaps if g.i > sw["ev_g"]]
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
    imp = []
    if p.implied_fvg:                  # setups_models A24.1: implied FVGs of the leg are entry gaps too
        imp = [z for z in sd.implied() if z.i <= i and z.i - 2 >= sw["ext_i"]]
        gaps = sorted(gaps + imp, key=lambda z: z.i)
    # Ep01.5 / Ep02.9 breakaway gap: the first FVG formed at / after the structure break
    ba = next((g for g in sd.gaps if g.i >= sw["broke"] and g.i - 2 >= sw["ext_i"] and g.i <= i), None)
    if p.breakaway == "next_fvg" and ba is not None:
        gaps = [g for g in gaps if g is not ba]  # not expected to retrace: wait for the next FVG
    # setups_models gap rules: A20 the break leaves the gap, M2 never the breakout candle's gap,
    # Ep04.7 the second leg's gaps, A8 IFVG hold / after-HTF, M10 061 trigger
    if p.disp_fvg_after_break:
        gaps = [g for g in gaps if g.i >= sw["broke"]]
    if p.no_breakout_fvg:
        gaps = [g for g in gaps if g.src != sw["broke"]]
    if sw.get("leg2_from") is not None:
        gaps = [g for g in gaps if g.i - 2 >= sw["leg2_from"]]
    if p.ifvg_entries and (p.ifvg_hold or p.ifvg_after_htf):
        gaps = _SM.ifvg_filter(ctx, sd, sw, gaps, i, p)
    if p.ifvg_entries and p.ifvg_061:
        o61 = _SM.ifvg_061(ctx, sd, sw, i, p, session, risk_mult)
        if o61 is not None:
            sd.sweep = None
            return o61
        ifv = {id(z) for z in sd.ifvgs()}
        gaps = [g for g in gaps if id(g) not in ifv]
    xz = []                            # Ep07.2 vi_entries / L14b void: more entry zones (not IFVGs)
    if p.vi_entries or "void" in p.irl_entries:
        xz = [z for z in _EN.extra_entry_zones(sd, sw, i, p) if sw.get("ev_g") is None or z.i > sw["ev_g"]]
        gaps = sorted(gaps + xz, key=lambda z: z.i)
    if p.irl_entries and "fvg" not in p.irl_entries:
        gaps = [g for g in gaps if any(g is z for z in xz)]      # L14b: the FVG is not an allowed IRL entry
    nn = p.news_no_unicorn and bool(events(ctx.day) & {"jobs", "cpi", "fomc"})   # N6
    bz = None
    if p.breaker_entry != "off" and not nn:   # A13.4: the breaker is needed before the no-FVG return
        bz = _breaker(ctx, sd, sw, ref_i, real_ref, i, p)
        if p.breaker_entry == "prefer" and bz is not None and not sw.get("bz_sent"):
            sd.sweep = None
            return _breaker_order(ctx, sd, sw, bz, i, p, session, risk_mult)
    if p.ob_entries == "prefer" and not sw.get("ob2_sent"):      # Ep08.5: the OB at its anchor open first
        o3 = _ob_anchor(ctx, sd, sw, i, p, session, risk_mult)
        if o3 is not None:
            sd.sweep = None
            return o3
    if not gaps:
        if sw.get("ev_g") is not None:      # E5: alive until the order lifetime passed since the last gap
            if i - sw["ev_i"] > max(1, p.pending_minutes // ctx.tf):
                sd.sweep = None
            return None
        wait = p.fvg_wait * (p.setup_minutes // ctx.tf if p.entry_tf == "5m" and ctx.tf < p.setup_minutes else 1)
        if i - _fvg_wait_from(sw) >= wait:
            sd.sweep = None
            _f("x_no_fvg_after_mss")
            if p.entry_arrays or p.reclaimed_ob or "ob" in p.irl_entries:   # setups_models M0.5: any PD array
                bz_a = bz if (bz is not None or nn or "breaker" not in p.entry_arrays) else \
                    _breaker(ctx, sd, sw, ref_i, real_ref, i, p)
                o2 = _SM.array_order(ctx, sd, sw, i, p, session, risk_mult, None, bz_a)
                if o2 is not None:
                    return o2
            if p.ob_entries == "fallback" and not sw.get("ob2_sent"):   # Ep08.5: no FVG -> the OB anchor open
                o3 = _ob_anchor(ctx, sd, sw, i, p, session, risk_mult)
                if o3 is not None:
                    return o3
            if p.breaker_entry in ("fallback", "classic") and bz is not None and not sw.get("bz_sent"):
                return _breaker_order(ctx, sd, sw, bz, i, p, session, risk_mult)
        return None
    if not _EN.engage_ok(ctx, i, p):    # Ep08.17: the sweep waits (is not consumed) until the range has formed
        _f("x_engage_range")
        return None
    keep_sw = p.evolve_fvg or p.wait_structural
    rearm = sw.get("ev_g") is not None
    if keep_sw:                       # E5: the sweep stays alive; only a gap newer than these re-arms
        sw["ev_g"], sw["ev_i"] = max(g.i for g in gaps), i
    else:
        sd.sweep = None   # this sweep is consumed whether or not the order passes the filters
    _f("3_fvg")
    # breaker (A13, owner #14): the highest-close up-close candle between the swing low before
    # the reference high (L1) and the sweep extreme (L2) (029 ~24:13; 048), full range by default
    if p.breaker_entry == "off" and not nn:
        bz = _breaker(ctx, sd, sw, ref_i, real_ref, i, p)
    # the entry FVG must still be open: no close below its bottom since it formed (021; 050)
    gaps = [g for g in gaps if c[g.i + 1:i + 1].min(initial=np.inf) >= g.bottom]
    if p.fvg_skip_above_pool:          # A5 (060 ~1:10:30): not a gap sitting right above a pool
        pools = [v for k, v in lv.items() if _level_intact(ctx, l, i + 1, k, v, session, tk)]
        gp = p.fvg_pool_gap_pts * p.es_pt
        gaps = [g for g in gaps if not any(0 <= g.bottom - v <= gp for v in pools)]
    if p.fvg_state_filter:             # A5 state (open / repriced / rebalanced)
        gaps = [g for g in gaps if _fvg_state(sd, g, i) in p.fvg_state_filter]
    if not gaps:
        _f("x_fvg_closed_through")
        return None
    fresh = [g for g in gaps if l[g.i + 1:i + 1].min(initial=np.inf) > g.top - p.mohawk]    # A4 mohawk poke ok
    if not fresh:
        if p.evolve_fvg and rearm:
            return None                   # E5: only a newer UNTOUCHED gap replaces the order
        fresh = gaps
    uni_ok = p.unicorn_sides == "both" or p.unicorn_sides == ("long" if sd.sign > 0 else "short")
    uni = [g for g in fresh if bz is not None and g.overlaps(bz)] if uni_ok else []
    if uni and p.breaker_mt_entry_floor:       # #6 (b): a unicorn gap wholly below the MT is out
        below = [g for g in uni if g.top <= bz.mt]
        if below:                              # of the unicorn pick; re-pick (spec 6b: it may
            _f("x_unicorn_below_mt")           # still be the plain-FVG entry)
            uni = [g for g in uni if g.top > bz.mt]
            if p.breaker_mt_floor_strict:      # [our interpretation] switch: not as a plain FVG either
                fresh = [g for g in fresh if g not in below]
                if not uni and not fresh:
                    return None
    sm_tags = []                               # setups_models tags (Trade.lv_tags)
    if uni:                                    # A14 / M4 / M4.2 / Ep05.4 unicorn rules
        uo = 570 <= ctx.t[sw["ext_i"]] < 570 + p.unicorn_open_min
        if (p.unicorn_open_only and not uo) or (p.unicorn_rules and not _judas(ctx, sd, sw, session, p.judas_window)):
            uni = []
        elif uo and (p.unicorn_open_only or p.unicorn_only or p.unicorn_rules or p.unicorn_entry != "edge"):
            sm_tags.append("unicorn_open")
    pick = (uni or fresh) if p.unicorn_pref else fresh   # D6 unicorn_pref
    if p.unicorn_only:                         # A14 / Ep05.4 review fix: pick among the unicorns
        if not uni:                            # (a fresh non-unicorn gap no longer rejects a
            _f("x_unicorn_only")               # setup that has a unicorn)
            return None
        pick = uni
    if p.fvg_pick == "2022":                   # setups_models M2 / M2.3
        g = _SM.pick_2022(ctx, sd, sw, pick, i, p)
    else:
        g = pick[-1] if p.fvg_pick == "last" else pick[0]
    if p.unicorn_only and not (uni and g in uni):
        _f("x_unicorn_only")
        return None
    if p.mmxm_breaker and bz is None:          # Ep05.8: the smart money reversal leaves a breaker
        _f("x_mmxm_breaker")
        return None
    if p.mmxm_rel_eq and not str(sw.get("key", "")).startswith("rel_eq"):
        _f("x_mmxm_rel_eq")                    # Ep05.8: the MM model runs relative equal lows (highs)
        return None
    top, bottom = g.top, g.bottom
    vi_exact = None
    if p.fvg_vi_extend:                # A5 (022 ~55:00; 098 ~60:00): an adjacent VI extends the box;
        for z in sd.vis("bull"):       # a VI inside the gap is the exact limit
            if not (g.i - 1 <= z.i <= min(g.i + 1, i)) or (p.vi_body_death and not _vi_alive(sd, z, i)):
                continue
            if z.bottom >= g.bottom - 1e-9 and z.top <= g.top + 1e-9:
                vi_exact = z.top if vi_exact is None else max(vi_exact, z.top)
            elif z.bottom <= g.top + tk + 1e-9 and z.top > g.top:
                top = max(top, z.top)
            elif z.top >= g.bottom - tk - 1e-9 and z.bottom < g.bottom:
                bottom = min(bottom, z.bottom)
    entry = _EN.entry_px(sd, g, top, bottom, p)       # D11 / E2: edge, ce, edge_1tick, iofed, ladder
    if vi_exact is not None:
        entry = vi_exact
    ladder = _EN.ladder_rungs(top, bottom, p) if p.entry == "ladder" else None
    bz_mt = None
    if uni and g in uni:
        if p.unicorn_entry == "overlap" or p.unicorn_rules:   # Ep05.4 / M4.2: entry inside the breaker
            entry = min(entry, bz.top)
        if p.breaker_mt_entry_floor or p.unicorn_rules:
            entry = min(max(entry, bz.mt + 0.25 * p.es_pt), top)
        if p.breaker_mt_respect:
            bz_mt = bz.mt
    if p.vi_porous_n:                  # A9 (027 ~22:09): a porous cluster of VIs in the leg = low trust
        nvi = sum(1 for z in sd.vis("bull") if sw["ext_i"] <= z.i <= i
                  and (not p.vi_body_death or _vi_alive(sd, z, i)))
        if nvi >= p.vi_porous_n:
            _f("x_vi_porous")
            return None
    is_imp = any(g is z for z in imp)
    is_xz = any(g is z for z in xz)                   # Ep07.2 VI / L14b void entry zone
    is_ifvg = p.ifvg_entries and g not in sd.gaps and not is_imp and not is_xz
    mit = any(z.i <= i and g.overlaps(z) for z in sd.mitigations()) if p.tag_blocks else False
    prop = any(z.i <= i and z.bottom <= g.top and z.top >= sw["ext"] for z in sd.propulsions()) if p.tag_blocks else False
    prop_exit = None
    if p.prop_entry or p.prop_mt_exit:        # A16 (cc04_008 ~0:30-5:40): the propulsion block under the gap
        pb = _EN.prop_block(sd, sw, g.top, i, p)
        if pb is not None:
            ztop, prop_exit = pb
            if p.prop_entry and sw["ext"] < ztop - p.tick < c[i]:
                entry = ztop - p.tick         # the new support: its high - 1 tick (a limit below the market)
    # order block: the blended last down-close candle(s) before the structure break (A12)
    ob = L.order_block_blend(sd.o, h, l, c, sw["ext_i"] - 3, sw["broke"] - 1, "bull")
    if ob is not None and not _EN.ob_quality_ok(sd, sw, ob, i, p):      # A12 ob_disp_mult
        _f("x_ob_disp")
        return None
    stop = bottom - p.pad
    mt = None if ob is None else (ob.mt if p.mt_mode == "body" else ob.mid)
    mt_bind = None
    if p.stop_mode == "ob_mt" and mt is not None and mt < entry - p.min_risk_pts * p.es_pt:
        stop = min(stop, mt - p.pad)
        mt_bind = (float(mt), float(ob.bottom))        # A12 / Ep02.3 mt_close_stop reads it in _finish_order
    if p.ep07_stop:                    # down-close candle nearest the sweep low, body midpoint
        e = sw["ext_i"]
        cand = [k for k in range(max(0, e - 3), min(i, e + 2) + 1) if c[k] < sd.o[k]]
        if cand:
            k = min(cand, key=lambda k: (abs(k - e), -k))
            stop = (sd.o[k] + c[k]) / 2 - p.pad
    if p.breaker_levels and uni and g in uni and mt is None:
        stop = min(stop, bz.bottom - p.pad)    # Ep05.1: below the breaker without an OB MT
    vi_z = None
    if p.vi_stop or p.vi_hold:         # A9 (009 ~13:46): below the VI under the entry (touch ok); Ep07.4 hold
        vs = [z for z in sd.vis("bull") if sw["ext_i"] < z.i <= i and z.top <= entry
              and (_vi_alive(sd, z, i) if p.vi_body_death else l[z.i + 1:i + 1].min(initial=np.inf) >= z.bottom)]
        if vs:
            vi_z = max(vs, key=lambda z: z.top)
            if p.vi_stop and entry - (vi_z.bottom - p.pad) >= p.min_risk_pts * p.es_pt:
                stop = vi_z.bottom - p.pad
    if p.stop_mode == "ob_near":                # setups_models M1: the OB nearest the sweep low
        ob_n = _ob_at_low(sd, sw, i)
        if ob_n is not None and ob_n["mt"] < entry - p.min_risk_pts * p.es_pt:
            stop = ob_n["mt"] - p.pad
    elif p.stop_mode == "fvg_candle" and not is_ifvg and g.src >= 0:   # M2 (062 ~37:28)
        stop = float(l[g.src]) - p.pad
    elif p.stop_mode == "ce2":                  # M2 (069 ~13:46): CE of the lower of the last two FVGs
        two = sorted(fresh, key=lambda z: z.i)[-2:]
        if len(two) == 2:
            stop = min(z.mid for z in two) - p.pad
    elif p.stop_mode in ("fvg_c1_low", "fvg_bodies", "fvg_open") and not is_ifvg and not is_imp and not is_xz             and g in sd.gaps:                    # E6 / E6b / Ep01.20
        s_ = _EN.gap_stop(sd, g, sw, i, p, ob, p.stop_mode)
        stop = stop if s_ is None else s_
    elif p.stop_mode in ("sweep", "ob_mt_pure"):   # E6c / M2.5
        s_ = _EN.gap_stop(sd, g, sw, i, p, ob, p.stop_mode)
        stop = stop if s_ is None else s_
    if is_ifvg and (p.ifvg_entry != "edge" or p.ifvg_depth or p.ifvg_stop_pts):   # M10 / A8
        entry, stop = _SM.ifvg_stop(sd, g, entry, stop, p)
    if is_ifvg and p.ifvg_min_risk_pts and ctx.tf > 1 and entry - stop < p.ifvg_min_risk_pts * p.es_pt:
        _f("x_ifvg_min_risk")
        return None
    if p.ote != "off" or p.leg_pd_strict or p.ote_leg_stop or p.ote_stack_tag:     # M13
        r_ = _SM.ote_adjust(sd, sw, i, p, entry, stop, "ifvg" if is_ifvg else "fvg", sm_tags)
        if r_ is None:
            return None
        entry, stop = r_
    st = _fvg_state(sd, g, i) if g in sd.gaps else ""
    lvt = list(sm_tags)
    lvx = {}
    if p.prop_mt_exit and prop_exit is not None:
        lvx["prop_mt"] = (prop_exit, False)           # A16: a body close below the propulsion MT exits
    if p.vi_hold and vi_z is not None:
        lvx["vi_hold"] = (float(vi_z.bottom), False)   # Ep07.4: a body close below the VI exits
    if p.ob_cisd != "off" and ob is not None and _EN.ob_cisd_ok(sd, ob, i, p):
        lvt.append("ob_cisd")                          # A12 validation tag
    if is_ifvg and p.ifvg_hold:
        lvx["ifvg_fail"] = (g.bottom, True)    # A8: a body close back below the IFVG
    ce_hold_ = bool(p.mmxm_ctx)                # Ep05.8: fails to hold the imbalance's CE = the ce_hold
                                               # rule (review fix: reused, no new exit)
    if sw.get("on_side"):
        lvt.append("on_side")
    if ba is not None and g is ba and p.breakaway in ("tag", "hold"):
        lvt.append("breakaway")
        if p.breakaway == "hold":
            lvx["breakaway_ce"] = (ba.mid, True)       # a body close beyond its CE: not breakaway
    if p.fvg_q_hold:
        lvx["q_close"] = (top - 0.25 * (top - bottom), True)   # the upper quarter must hold
    ir = _ir_in_leg(sd, sw, i, p)
    tags = dict(unicorn=bool(uni) and g in uni if not p.unicorn_pref else bool(uni), fvg_bottom=bottom,
                fvg_ce=(top + bottom) / 2, zone_top=float(top), fvg_i=int(g.i),
                entry_kind="ifvg" if is_ifvg else "implied_fvg" if is_imp else
                ("vi" if any(g is z for z in sd.vis("bull")) else "void") if is_xz else "fvg", mitigation=bool(mit),
                propulsion=bool(prop), ce_hold=ce_hold_,
                unicorn_side=("bull" if sd.sign > 0 else "bear") if (uni and (p.unicorn_pref or g in uni)) else "",
                bz_top=None if bz is None else float(max(sd.x(bz.top), sd.x(bz.bottom))),
                bz_bottom=None if bz is None else float(min(sd.x(bz.top), sd.x(bz.bottom))),
                bz_mt=bz_mt, fvg_state=st, imm_rebal=ir, lv_tags=lvt, lvx=lvx,
                bz_side=None if bz is None else (bz.top, bz.bottom))
    if mt_bind is not None:
        tags["mt_close"] = mt_bind
    if p.entry == "ce" and vi_exact is None:
        tags["ce_entry"] = True                        # E6f ce_stop_pad_pts
    if ladder is not None:
        tags["ladder"] = ladder
    if p.ob_cisd == "cancel" and ob is not None:
        tags["cancel_low"] = float(ob.bottom)          # A12: the OB low must hold
    if p.breaker_entry == "classic" and bz is not None and bz.top > entry and not sw.get("bz_sent"):
        return _breaker_order(ctx, sd, sw, bz, i, p, session, risk_mult)   # M4.1: the breaker comes first
    if p.entry_arrays or p.reclaimed_ob or "ob" in p.irl_entries:       # M0.5: an array the retrace reaches before the FVG
        o2 = _SM.array_order(ctx, sd, sw, i, p, session, risk_mult, entry, bz)
        if o2 is not None:
            return o2
    o_ = _finish_order(ctx, sd, i, p, session, sw, entry, stop, risk_mult,
                       h[sw["ext_i"]:i + 1].max(), tags, pctx_free=True)
    if o_ is not None and keep_sw and not p.evolve_fvg:
        sd.sweep = None                   # wait_structural: the sweep is consumed once an order is armed
    return o_


def _vi_alive(sd, z, i: int) -> bool:
    """A9 / Ep03.3 body death rule for the intraday Side VIs (review fix, vi_body_death): alive until
    a later body spans it (L.vi_body_dead over bars z.i+1 .. i)."""
    return L.vi_body_dead(sd.o, sd.c, z, end=i) is None


def _lv_finish_targets(ctx, sd, i: int, above: float, p, htf_t: tuple) -> list:
    """levels_detectors targets beyond `above` (side space, raw levels with kinds): B1 vi_targets
    (untouched opposing intraday VIs: near edge, CE), A11 bpr_targets (near edge, midpoint), A15
    mit_targets (opposing mitigation blocks; mit_body_respect: only while no close went through),
    A5 fvg_quadrants (25/75% of large opposing gaps, intraday and HTF), A5 fvg_keep_filled (opposing
    gaps stay targets after a fill: intraday and HTF within their life), Ep08.1 daily_fvg_exact
    (daily FVG near edges as exact levels, kind "exact")."""
    h = sd.h
    out = []
    after = lambda z: h[z.i + 1:i + 1].max(initial=-np.inf)
    if p.vi_targets:                   # review fix: vi_body_death -> alive = no later body across it
        for z in sd.vis("bear"):
            if z.i <= i and z.bottom > above and (_vi_alive(sd, z, i) if p.vi_body_death else after(z) < z.bottom):
                out += [(z.bottom, "array"), (z.mid, "array")]
    if p.bpr_targets:                  # review fix: only BPRs not traded into since they formed
        for z in sd.bprs(p.bpr_max_gap_bars):
            if z.i <= i and z.bottom > above and after(z) < z.bottom:
                out += [(z.bottom, "array"), (z.mid, "array")]
    if p.mit_targets:
        for z in sd.opp_mits():
            if z.i <= i and z.bottom > above and (not p.mit_body_respect or L.mitigation_alive(sd.c, z, i)):
                out += [(z.bottom, "array"), (z.mid, "array")]
    wide = p.fvg_quad_min_pts * p.es_pt
    opp = [z for z in sd._lazy("opp_fvg", lambda: [g for g in L.fvgs(sd.h, sd.l, sd.o, sd.c, sd.c2_dir)
                                                    if g.kind == "bear" and g.top - g.bottom >= sd.min_gap])
           if z.i <= i and z.bottom > above]
    if p.fvg_quadrants:
        for z in opp:
            if z.top - z.bottom >= wide and after(z) < z.bottom:
                out += [(z.q(0.25), "array"), (z.q(0.75), "array")]
    if p.fvg_keep_filled:
        for z in opp:
            out += [(z.bottom, "array"), (z.mid, "array")]
    conf = getattr(ctx, "conf", None)
    if conf is not None and (p.fvg_quadrants or p.fvg_keep_filled or p.daily_fvg_exact):
        now = ctx.idx[i] + pd.Timedelta(minutes=ctx.tf)
        if p.fvg_quadrants and htf_t:
            for near, ce, far, tf, _ in conf.opposing(now, sd.x(above), sd.sign, htf_t, (0,)):
                a, b = sd.x(near), sd.x(far)
                if b - a >= wide:
                    out += [(a + 0.25 * (b - a), "array"), (a + 0.75 * (b - a), "array")]
        if p.fvg_keep_filled and htf_t:
            for near, ce, far, tf, _ in conf.opposing(now, sd.x(above), sd.sign, htf_t, (0,), keep_dead=True):
                out += [(sd.x(near), "array"), (sd.x(ce), "array")]
        if p.daily_fvg_exact:
            for near, ce, far, tf, _ in conf.opposing(now, sd.x(above), sd.sign, ("D",), (0,)):
                out.append((sd.x(near), "exact"))
    return [(float(v), k) for v, k in out if v > above]


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
    entry = _EN.ob_entry_price(ob, sd, p)          # Ep03.9 / A12: body_top, mt, range_top|high, open, ob_zone
    if entry >= sd.c[i]:
        entry = ob["body_top"]                     # [our interpretation] never a limit above the market
    stop = ob["mt"] - p.pad if p.ob_stop == "mt" else sw["ext"] - p.pad
    mt_close = (float(ob["mt"]), float(ob["lo"])) if p.ob_stop == "mt" else None
    if entry - stop < p.min_risk_pts * p.es_pt or entry <= stop:
        stop = sw["ext"] - p.pad        # [our interpretation] fallback to the sweep extreme
        mt_close = None
    tags = dict(unicorn=False, fvg_bottom=ob["body_low"], fvg_ce=ob["mt"], entry_kind="ob_pre",
                mitigation=False, propulsion=False, ob_pre=True, ob_body_low=ob["body_low"],
                ob_lo=ob["lo"],
                # setups_models review fix: the sweep this order belongs to, so the MSS gates acting
                # at the later break can cancel (ob_pre_gate "cancel") or release ("hold") it
                sw_ref=sw, sw_ext_i=sw["ext_i"], ob_hold=p.ob_pre_gate == "hold")
    if mt_close is not None:
        tags["mt_close"] = mt_close                # A12 / Ep02.3 mt_close_stop
    if p.ob_cisd != "off" and sd.c[i] > ob["body_top"]:
        tags["lv_tags"] = ["ob_cisd"]              # A12: price closed through the open of the last down candle
    if p.ob_cisd == "cancel":
        tags["cancel_low"] = float(ob["lo"])       # ... and the OB low must hold
    return _finish_order(ctx, sd, i, p, session, sw, entry, stop, risk_mult,
                         sd.h[sw["ext_i"]:i + 1].max(), tags, skip_leg_pd=True)


def _ob_anchor(ctx, sd, sw, i, p, session, risk_mult):
    """Ep08.5 (010) ob_entries: a limit at the ANCHOR OPEN of the order block before the break (the
    first candle of the down-close run) with the MT stop - "fallback" when no FVG follows the break,
    "prefer" at the break. Sent once per sweep."""
    sw["ob2_sent"] = True
    ob = L.order_block_blend(sd.o, sd.h, sd.l, sd.c, sw["ext_i"] - 3, sw["broke"] - 1, "bull")
    if ob is None:
        return None
    entry = float(sd.o[ob.src])
    if entry >= sd.c[i]:
        _f("x_ob_anchor_above")
        return None
    mt = ob.mt if p.mt_mode == "body" else ob.mid
    stop = float(mt) - p.pad
    mt_close = (float(mt), float(ob.bottom))
    if entry - stop < p.min_risk_pts * p.es_pt:
        stop, mt_close = sw["ext"] - p.pad, None
    tags = dict(unicorn=False, fvg_bottom=float(ob.bottom), fvg_ce=float(mt), entry_kind="ob_anchor",
                mitigation=False, propulsion=False)
    if mt_close is not None:
        tags["mt_close"] = mt_close
    return _finish_order(ctx, sd, i, p, session, sw, entry, stop, risk_mult,
                         sd.h[sw["ext_i"]:i + 1].max(), tags, pctx_free=True)


TS_TFS = ("15m", "30m", "1h", "4h", "D", "W")


def _ts_arrays(ctx, sd, i, known_by, tfs=TS_TFS, src=(0, 1, 3)) -> list:
    """Same-side HTF PD arrays (FVG / OB / VI) valid at bar i's close and complete by `known_by`,
    in side space: [(top, bottom, known_ts)]. From the confluence table; without it (no overnight
    bars) from the session's 15m/60m FVGs (DayCtx.hzones, not closed through by bar i)."""
    now = ctx.idx[i] + pd.Timedelta(minutes=ctx.tf)
    out = []
    if getattr(ctx, "conf", None) is not None:
        for top, bot, tf_, sc, kn in ctx.conf.valid(now, sd.sign, tfs, src, known_by):
            a, b = sd.x(top), sd.x(bot)
            out.append((max(a, b), min(a, b), pd.Timestamp(int(kn), tz="UTC").tz_convert(ctx.idx.tz)))
        return out
    if not getattr(ctx, "hzones", None):
        return out
    j = ctx.full_off + i
    for z, known, m in ctx.hzones:
        if known > known_by or z.kind != ("bull" if sd.sign > 0 else "bear"):
            continue
        top, bot = (z.top, z.bottom) if sd.sign > 0 else (-z.bottom, -z.top)
        k = int(ctx.full_idx.searchsorted(known))
        if (sd.sign * ctx.full_c[k:j + 1]).min(initial=np.inf) < bot:
            continue                                     # closed through
        out.append((top, bot, known))
    return out


def _gap_below(ctx, sd, i, x) -> float | None:
    """038 ~41:58: the nearest NWOG / NDOG / opening-range-gap level below x (side space) known
    at bar i (today's ORG only from 09:30)."""
    lv = []
    if getattr(ctx, "gaps", None) is not None:
        for _, hi, lo, ce in ctx.gaps:
            lv += [hi, lo, ce]
    else:
        for a, b in _nwogs(ctx, i):
            lv += [a, b]
    orgs = ctx.org[:-1] if (ctx.t[i] < 570 and ctx.org_today) else ctx.org
    for a, b in orgs[-5:]:
        lv += [a, b, (a + b) / 2]
    below = [sd.x(v) for v in lv if sd.x(v) < x]
    return max(below) if below else None


def _ts_stop(ctx, sd, sw, i, p, arr, entry) -> float:
    """Turtle-soup stop by ts_stop: below the PD array (022 ~2:47:29), the nearest gap level below
    the false-break low (038 ~41:58), else below the extreme ("ext"). Falls back to the extreme
    when the choice is missing or leaves less than min_risk_pts."""
    st = None
    if p.ts_stop == "array" and arr is not None:
        st = arr[1] - p.pad
    elif p.ts_stop == "gap":
        g = _gap_below(ctx, sd, i, sw["ext"])
        st = None if g is None else g - p.pad
    if st is None or entry - st < p.min_risk_pts * p.es_pt:
        st = sw["ext"] - p.pad
    return st


def _turtle(ctx, sd, sw, i, p, session, risk_mult):
    """M12 turtle soup on an active sweep (shared core L.turtle_soup: the level taken by at most
    ts_max_pts, a close back above it within ts_back_bars - no MSS needed; M12.5 depth/back).
      "2023" (M12.1; 022 ~2:47:29; rule_coverage M12.1 "limit at the array top, stop at the array
             or a gap"): limit at the top of the HTF PD array the sweep reached into, capped at the
             swept level [our interpretation]; ts_entry="level" = at the level (the first
             reading); stop below that array / the nearest gap (ts_stop); no array -> at the
             level, stop below the false-break extreme [our interpretation]
      "or60" (M12.3; cc10_010 ~6:51): only the OR60 low after 10:30; one target, the OR60 high
      "cc_1h_ob" (M12.3): see _cc_1h_ob. cc_limit / external are not sweep-driven (see _scan)."""
    v = p.turtle_soup
    if v in ("cc_limit", "external"):
        return None
    if v == "cc_1h_ob":
        return _cc_1h_ob(ctx, sd, sw, i, p, session, risk_mult)
    if v == "or60" and sw["key"] != "or60":
        return None
    if not L.turtle_soup(sd.l, sd.c, sw["level"], sw["ext_i"], i, p.ts_max_pts * p.es_pt, p.ts_back_bars):
        return None
    if p.ts_need_htf and not _htf_tag(ctx, sd, i, sw["ext"], p.eq_tol_pts * p.es_pt):
        return None
    if p.ts_need_flow:                   # setups_models M12 (cc09_005 ~3:12): HTF order flow its way
        cf_ = getattr(ctx, "conf", None)
        if cf_ is None or cf_.trend(ctx.idx[i] + pd.Timedelta(minutes=ctx.tf), "D") != sd.sign:
            _f("x_ts_flow")
            return None
    if p.ts_max_run:                     # setups_models Ep08.15: the failure close within N minutes
        k_ = sw["ext_i"] + int(np.flatnonzero(sd.c[sw["ext_i"]:i + 1] > sw["level"])[0])
        if (k_ - sw["ext_i"]) * ctx.tf > p.ts_max_run:
            return None
    sw["ts_sent"] = True
    entry, stop, fixed, arr = sw["level"], sw["ext"] - p.pad, None, None
    if v == "2023":
        tol = p.eq_tol_pts * p.es_pt
        kb = ctx.idx[sw["ext_i"]] + pd.Timedelta(minutes=ctx.tf)
        ins = [a for a in _ts_arrays(ctx, sd, i, kb) if a[1] - tol <= sw["ext"] <= a[0] + tol]
        if ins:
            arr = min(ins, key=lambda a: a[0])           # [our interpretation] the tightest array
        if arr is not None and p.ts_entry == "array":
            entry = min(arr[0], sw["level"])
        stop = _ts_stop(ctx, sd, sw, i, p, arr, entry)
    else:                                                # or60: target the OR60 high
        hi = sd.x(ctx.or60[0] if sd.sign > 0 else ctx.or60[1])
        fixed = [(hi + p.pool_beyond_pts * p.es_pt if p.exit_mode == "split" else hi - p.exit_before_pts * p.es_pt, "pool")]
    tags = dict(unicorn=False, fvg_bottom=sw["ext"] if arr is None else arr[1], fvg_ce=(entry + sw["ext"]) / 2,
                entry_kind="turtle_soup" if v == "2023" else "ts_or60", mitigation=False, propulsion=False)
    return _finish_order(ctx, sd, i, p, session, sw, entry, stop, risk_mult,
                         sd.h[sw["ext_i"]:i + 1].max(), tags, skip_leg_pd=True, fixed=fixed)


def _hour_down_candle(ctx, sd, ext_i: int, i: int):
    """cc_1h_ob: the last DOWN-close clock-aligned 1h candle (side space) that started at or before
    the sweep extreme's bar and is complete by bar i: (open, high, index of its last base bar)."""
    hc = sd.__dict__.get("_h60")
    if hc is None:
        key = ctx.idx.floor("60min")
        b = pd.Series(np.arange(len(key)), index=key).groupby(level=0)
        first, last = b.min().values, b.max().values
        done = np.asarray((ctx.idx[last] - b.min().index) >= pd.Timedelta(minutes=60 - ctx.tf))
        o = sd.o[first]; c = sd.c[last]
        hh = np.array([sd.h[a:z + 1].max() for a, z in zip(first, last)])
        hc = sd.__dict__["_h60"] = (first, last, done, o, hh, c)
    first, last, done, o, hh, c = hc
    ok = np.flatnonzero(done & (last <= i) & (first <= ext_i) & (c < o))
    if not len(ok):
        return None
    j = ok[-1]
    return float(o[j]), float(hh[j]), int(last[j])


def _cc_1h_ob(ctx, sd, sw, i, p, session, risk_mult):
    """M12.3 CC turtle soup into a daily OB (cc02_001 ~17:41-25:21) [our interpretation of the
    bar mechanics]: the sweep extreme sits in a valid daily bullish OB (known by the extreme's
    close); once a closed bar trades above the high of the last down-close 1h candle at the low,
    a buy limit at that candle's open; stop below the OB's MT (ts_stop "array") or the sweep low;
    half off at 1R, breakeven after 2R, runner to 5R (ts_r_mults / ts_be_r)."""
    if getattr(ctx, "conf", None) is None:
        return None
    tol = p.eq_tol_pts * p.es_pt
    kb = ctx.idx[sw["ext_i"]] + pd.Timedelta(minutes=ctx.tf)
    obs = [a for a in _ts_arrays(ctx, sd, i, kb, ("D",), (1,)) if a[1] - tol <= sw["ext"] <= a[0] + tol]
    if not obs:
        return None
    hc = _hour_down_candle(ctx, sd, sw["ext_i"], i)
    if hc is None:
        return None
    ho, hh, hlast = hc
    if not (sd.h[hlast + 1:i + 1] > hh).any():
        return None                                      # not yet traded back up through it
    sw["ts_sent"] = True
    ob = min(obs, key=lambda a: a[0])
    entry = ho
    stop = (ob[0] + ob[1]) / 2 - p.pad if p.ts_stop == "array" else sw["ext"] - p.pad
    if entry - stop < p.min_risk_pts * p.es_pt:
        stop = sw["ext"] - p.pad
    risk = entry - stop
    fixed = [(entry + r * risk, "array") for r in p.ts_r_mults]
    tags = dict(unicorn=False, fvg_bottom=ob[1], fvg_ce=(ob[0] + ob[1]) / 2, entry_kind="ts_cc_1h_ob",
                mitigation=False, propulsion=False, fracs=tuple([1.0 / len(fixed)] * len(fixed)),
                be_at=entry + p.ts_be_r * risk)
    return _finish_order(ctx, sd, i, p, session, sw, entry, stop, risk_mult,
                         sd.h[sw["ext_i"]:i + 1].max(), tags, skip_leg_pd=True, fixed=fixed)


def _cc_limit(ctx, sd, i, p, session, risk_mult):
    """M12.3 CC buy-limit raid (cc04_011 ~9:45) [our interpretation of the bar mechanics]: with a
    bias for this side (the session's locked draw, else the htf_bias side; none -> no trade), a
    resting buy limit at (ts_cc_below_pts under) the nearest untaken sell-side level below the
    close, armed once per level; stop ts_max_pts under the level (a deeper run is a real decline)."""
    if getattr(ctx, "cur_bias", 0) != sd.sign:
        return None
    lv = _sell_side(ctx, sd, session, i, p.extra_pools, p)
    sent = sd.__dict__.setdefault("_cc_sent", set())
    cand = [(v, k) for k, v in lv.items() if v < sd.c[i] and sd.l[i] >= v
            and _level_intact(ctx, sd.l, i, k, v, session, _tick(p)) and (session, k, round(v, 9)) not in sent]
    if not cand:
        return None
    v, k = max(cand)
    sent.add((session, k, round(v, 9)))
    entry = v - p.ts_cc_below_pts * p.es_pt
    stop = v - p.ts_max_pts * p.es_pt - p.pad
    sw = dict(session=session, name=k, level=v, key=k, ext=entry, ext_i=i, broke=None, sweep_i=i,
              smt=None, smt2=None)
    tags = dict(unicorn=False, fvg_bottom=stop, fvg_ce=(entry + stop) / 2, entry_kind="ts_cc_limit",
                mitigation=False, propulsion=False)
    return _finish_order(ctx, sd, i, p, session, sw, entry, stop, risk_mult, sd.h[i], tags, skip_leg_pd=True)


def _external(ctx, sd, i, p, session, risk_mult):
    """M12.4 external turtle soup (cc12_004 ~29:35) [our interpretation of the bar mechanics]: a
    swing low formed today (the false low) stopped short of a same-side HTF array below it that
    was known when the low was confirmed and not reached since; bar i runs the false low's sell
    stops and is the first to trade into the array, closing at or above its bottom -> buy limit
    at the array top, stop below it (ts_stop). Once per false low."""
    used = sd.__dict__.setdefault("_ts_ext", set())
    l, c = sd.l, sd.c
    for q in reversed(sd.pl):
        if q.i < ctx.start - 1:
            break
        if q.known > i - 1 or q.i in used or l[i] >= q.price:
            continue
        kq = ctx.idx[q.known] + pd.Timedelta(minutes=ctx.tf)
        arrs = []
        for top, bot, kn in _ts_arrays(ctx, sd, i, kq):
            if top >= q.price:
                continue
            k0 = max(0, int(ctx.idx.searchsorted(kn)))
            if l[k0:i].min(initial=np.inf) > top >= l[i] and c[i] >= bot:
                arrs.append((top, bot, kn))
        if not arrs:
            continue
        used.add(q.i)
        top, bot, _ = max(arrs)                          # the nearest array below the false low
        sw = dict(session=session, name="ts_external", level=q.price, key="ts_external", ext=float(l[i]),
                  ext_i=i, broke=None, sweep_i=i, smt=None, smt2=None)
        stop = _ts_stop(ctx, sd, sw, i, p, (top, bot), top)
        tags = dict(unicorn=False, fvg_bottom=bot, fvg_ce=(top + bot) / 2, entry_kind="ts_external",
                    mitigation=False, propulsion=False)
        return _finish_order(ctx, sd, i, p, session, sw, top, stop, risk_mult, sd.h[i], tags, skip_leg_pd=True)
    return None


def _round_px(ctx, sd, i, x: float, p, up: bool) -> float:
    """L17 (cc12_001 ~34:00): round a side-space price to round_step_pts on the REAL front-month
    price (#13 mapping: real = engine - adj of bar i; SPY / no meta: adj 0). up=True rounds toward
    higher side-space prices (limit entries toward price), up=False lower (targets toward price)."""
    st = p.round_step_pts * p.es_pt
    adj = getattr(ctx, "adj", None)
    off = sd.sign * (float(adj[i]) if adj is not None else 0.0)
    q = (x - off) / st
    return float((np.ceil(q - 1e-9) if up else np.floor(q + 1e-9)) * st + off)


def _finish_order(ctx, sd, i, p, session, sw, entry, stop, risk_mult, leg_hi, tags,
                  skip_leg_pd=False, pctx_free=False, fixed=None):
    """Shared order tail for every entry path: risk, bias / leg / HTF / confluence filters,
    targets (#2 room, #7 cap, #9 locked draw), size (#12) and the order dict. `fixed` (side
    space [(level, kind)]): the setup's own targets (turtle-soup or60 / cc_1h_ob) instead of the
    liquidity list; the #7 cap still trims them, the #9 lock gates the side only."""
    l, h, c = sd.l, sd.h, sd.c
    tol = p.eq_tol_pts * p.es_pt
    tags = dict(tags)
    lvt = list(tags.pop("lv_tags", []) or [])        # levels_detectors tags (Trade.lv_tags)
    lvx = dict(tags.pop("lvx", {}) or {})            # levels_detectors exit levels (side space)
    if p.round_step_pts:                 # L17: limit entries rounded toward price; stops are not
        entry = _round_px(ctx, sd, i, entry, p, up=True)
    zone_top = float(tags.get("zone_top", entry))        # Ep01.18: the entry zone top (retest add)
    stop_cc = p.entry_order == "stop_cc"
    if stop_cc:                          # E1 [CC]: a buy stop one tick over the array top, never a chase.
        if not sd.c[i] < entry:          # The shift comes BEFORE risk / size / min-max risk, so they are
            _f("x_stop_cc_chase")        # computed at the real fill price (review fix)
            return None
        entry = entry + p.tick
    if (p.release_open or p.release_open_stop) and session != "PM" and news(ctx.day) == "0830":
        k830 = _idx_at(ctx, 510)         # T2 (064 ~55:13): retrace bodies hold the 08:30 open
        if k830 < len(ctx.t) and ctx.t[k830] < 540 and k830 <= i and "0830" in ctx.opens:
            o830 = sd.x(ctx.opens["0830"])
            if p.release_open:
                bl = np.minimum(sd.o[k830:i + 1], c[k830:i + 1]).min()
                if bl < o830 - 0.25 * p.es_pt - 1e-9:
                    _f("x_release_open")
                    return None
                lvt.append("release_open")
                # review fix: the hold is enforced after arming too - a body close below the 08:30
                # open (minus a tick) cancels the pending order (run_day) and exits the trade (lvx)
                lvx["release_open"] = (o830 - 0.25 * p.es_pt - 1e-9, False)
            if p.release_open_stop:          # T2: the stop beyond the 08:30 open / its candle's wick CE
                b830 = min(sd.o[k830], c[k830])
                lvl = o830 if p.release_open_stop == "open" else b830 - (b830 - l[k830]) / 2
                if lvl < entry and entry - (lvl - p.pad) >= p.min_risk_pts * p.es_pt:
                    stop = lvl - p.pad
    if p.trade_type == "day":            # X5c (064 ~1:38:44): a day trade's stop sits below the 08:30 open / its wick CE
        k830 = _idx_at(ctx, 510)         # and is never moved (no trail, no breakeven): partials pay for it
        day_ok = False
        if k830 < i and k830 < len(ctx.t) and ctx.t[k830] == 510:
            b830 = min(sd.o[k830], c[k830])
            lvl = float(sd.o[k830]) if p.day_stop == "open" else float(b830 - (b830 - l[k830]) / 2)
            if lvl < entry and entry - (lvl - p.pad) >= p.min_risk_pts * p.es_pt:
                stop = lvl - p.pad
                tags["day_trade"] = True
                lvt.append("day_trade")
                day_ok = True
        if not day_ok:
            _f("x_day_trade_unavailable")   # no 08:30 candle yet / its level is not below the entry / too small:
                                            # the order stays an ordinary session trade (stop unchanged)
    stop = _EN.refine_stop(ctx, sd, sw, i, p, entry, stop, tags, lvx, lvt)   # A4 / A12 / E6d / E6f
    risk = entry - stop
    if not (p.min_risk_pts * p.es_pt <= risk <= p.max_risk_pts * p.es_pt):
        _f("x_risk_too_small" if risk < p.min_risk_pts * p.es_pt else "x_risk_too_big")
        return None
    if not _EN.engage_ok(ctx, i, p):
        _f("x_engage_range")                                         # Ep08.17: wait for a range to form
        return None
    # setups_models review fix (T10 / M11a / M5.1): moc_run joins the run at 15:40, the IR entry
    # enters at once in the trend and the Ep 01 last hour buys in the PM run - the PO3 open filter
    # does not gate them unless synth_po3 (the first build's behaviour) [our interpretation]
    skip_po3 = bool(tags.pop("skip_po3", False))
    if p.use_bias and not skip_po3:      # T2 / D22 bias_open: the AM reference open
        ref_open = _open_known(ctx, "1330" if session == "PM" else p.bias_open, i)
        if ref_open is None and session != "PM":     # review fix: a pre-09:30 window (PRE7 / PRE9 /
            ref_open = _open_known(ctx, "midnight", i)   # NEWS) reads the midnight open until it prints
        if ref_open is not None and not (entry <= sd.x(ref_open) + p.eq_tol_pts * p.es_pt if p.po3_inclusive
                                         else entry < sd.x(ref_open) + p.mo_tol_pts * p.es_pt):   # Ep04.4 / Ep04.6
            _f("x_wrong_side_of_open")
            return None
    pd_hi = _EN.pd_high(sd, sw, i, leg_hi, p)         # L14b erl_range_swings
    if not skip_leg_pd and p.leg_pd and p.leg_pd_at == "arm" and entry > sw["ext"] + p.leg_pd * (pd_hi - sw["ext"]):
        _f("x_leg_premium")
        return None                                   # entry FVG not in the leg's discount
    if not skip_leg_pd and p.leg_pd_min and entry < sw["ext"] + p.leg_pd_min * (pd_hi - sw["ext"]) - 1e-9:
        _f("x_leg_too_deep")                          # D12: deeper than the 79% line of the leg
        return None
    if p.leg_depth_tag:
        lvt += _EN.leg_depth_tags(entry, sw["ext"], pd_hi)
    cl = _EN.ote_cancel_level(entry, sw["ext"], leg_hi, tags.get("cancel_low"), p)     # A21.3
    if cl is not None:
        tags["cancel_low"] = cl
    if session == "PM" and p.pm_judas_1330 and not _judas(ctx, sd, sw, "PM"):
        _f("x_pm_judas")
        return None                                   # M7.1 option
    htf = _htf_tag(ctx, sd, i, sw["ext"], tol)
    if p.require_htf and not htf:
        return None
    if not _SM.finish_gates(ctx, sd, sw, i, p, session, entry, tags, lvt, lvx):   # setups_models
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
    key = sw.get("key", "")
    if (p.daily_level_needs_array or p.daily_level_needs_flow) and key.startswith(("pdl", "pdh", "m3", "ipda")):
        # L2 (Ep 08; 010 ~63:38): an old daily high/low alone is not an entry - a PD array there
        # review fix: only HTF arrays count (daily_level_array_tfs, >= 15m by default) - any 1m / 5m
        # FVG or OB at the sweep extreme made the gate a near no-op; no confluence -> the HTF tag
        if p.daily_level_needs_array and not (_htf_array(cf, p) if cf is not None else htf):
            _f("x_daily_no_array")
            return None
        if p.daily_level_needs_flow:     # cc09_005 ~03:12: plus HTF (daily) order flow its way
            fl = ctx.conf.trend(ctx.idx[i] + pd.Timedelta(minutes=ctx.tf), "D") if getattr(ctx, "conf", None) is not None else 0
            if fl != sd.sign:
                _f("x_daily_no_flow")
                return None
    if p.wick_react != "off":            # Ep 08: the sweep extreme at a prior daily wick CE
        wr = any(abs(sw["ext"] - w) <= tol for w in _wick_ces(ctx, sd, True))
        if wr:
            lvt.append("wick_react")
        elif p.wick_react == "require":
            _f("x_wick_react")
            return None
    if p.gap_run_stop:                   # L5 (038 ~41:58): the run stopped at the nearest gap level
        gl = _gap_below(ctx, sd, i, sw["level"])
        if gl is None or abs(sw["ext"] - gl) > p.gap_run_tol_pts * p.es_pt:
            _f("x_gap_run_stop")
            return None
        lvt.append("gap_stop")
    if getattr(ctx, "cur_no_draw", False):
        lvt.append("no_draw")            # B1 consolidation session (tag; skip_no_draw gates it)
    hs_ = getattr(ctx, "hist", None)     # A7 daily immediate rebalance (059 ~4:18) [our interpretation]:
    op_ = ctx.opens.get("midnight")      # today opened beyond yesterday's high (low) and traded straight
    if hs_ and op_ is not None:          # back to it within a tick
        yh, yl, tk1 = float(hs_[-1].high.max()), float(hs_[-1].low.min()), 0.25 * p.es_pt
        if op_ > yh and abs(ctx.l[ctx.start:i + 1].min() - yh) <= tk1:
            lvt.append("open_to_pdh")
        if op_ < yl and abs(ctx.h[ctx.start:i + 1].max() - yl) <= tk1:
            lvt.append("open_to_pdl")
    if p.ipda_eq_day != "off" and _ipda_eq(ctx, p, i):
        lvt.append("ipda_eq")            # B21 range day (skip mode gates the session in run_day)
    if p.org_draw != "off" or p.org_q_hold or p.org_half_draw:
        st = _org_state(ctx, sd, i, p)   # L7 tags
        if st is not None:
            if st["breakaway"]:
                lvt.append("org_breakaway")
            elif st["up"] and p.org_draw != "off":
                lvt.append("org_draw")
            if st["half"] and p.org_half_draw:
                lvt.append("org_half")
            if p.org_q_hold and st["q_hold"]:
                lvt.append("org_q_hold")
    if p.wick_invalidate:                # L10: the prior day's wick CE behind the entry invalidates
        ws = [w for w in _wick_ces(ctx, sd, True)[:1] if w < entry]
        if ws:
            lvx["wick_inv"] = (ws[0], False)
    if p.bpr_abort or p.bpr_rule:        # A11 (026 ~1:05:53; 065B ~4:28): body close through the BPR
        sup = [z for z in sd.bprs(p.bpr_max_gap_bars) if z.i <= i and z.bottom <= entry and z.top >= sw["ext"]]
        if sup:                          # midpoint under the entry = abort [our interpretation]
            z = max(sup, key=lambda z: z.top)
            lvx["bpr_abort"] = (z.mid, False)
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
    above = max(leg_hi, entry)
    tg = _TP.tgif_info(ctx, sd, i, p, entry) if p.tgif_zone else None     # M14.2 TGIF zone
    if tg is not None and tg["stand_down"]:
        _f("x_tgif_stand_down")                  # 40%+ of the weekly range retraced = reversal talk
        return None
    if p.sick_sister and fixed is None:          # setups_models M16.2: the sick sister's own targets
        fixed = _SM.sick_sister(ctx, sd, i, p, session, entry)
        if fixed is None:
            return None
    eq_hi, rr_ = [], None
    if fixed is not None:
        lv = sorted(fixed)
        kinds = [k for _, k in lv]
        lv = [v for v, _ in lv]
    else:
        eq_hi = _eq_levels(sd, i, tol, lows=False, p=p)
        if p.rel_tfs:                      # L4: relative equal highs on higher timeframes too
            eq_hi = list(eq_hi) + _TP.rel_pools(ctx, sd, i, p)
        lv = _targets(ctx, sd, i, above, eq_hi, p, (sw["ext"], leg_hi), sw["ext_i"])
        htf_t = tuple(p.htf_targets) + (("30m",) if p.htf_targets_30m and "30m" not in p.htf_targets else ())
        if htf_t and getattr(ctx, "conf", None) is not None:
            now = ctx.idx[i] + pd.Timedelta(minutes=ctx.tf)
            if _TP.needs_htf_rows(p):      # L9 / A22 / L14d: the same levels with the array filters applied
                lv = sorted(set(lv) | set(_TP.htf_levels(ctx, sd, i, above, p, htf_t)))
            else:
                real = ctx.conf.targets(now, sd.x(above), sd.sign, htf_t, p.htf_far_edge)
                lv = sorted(set(lv) | {(sd.x(v), "array") for v in real})
        if p.fvg_targets:                  # untouched opposing FVGs / voids: near edge, then CE (L9)
            extra = []
            for z in sd.opposing():
                if z.i <= i and z.bottom > above and h[z.i + 1:i + 1].max(initial=-np.inf) < z.bottom:
                    extra += [(z.bottom, "array"), (z.mid, "array")]
            lv = sorted(set(lv) | set(extra))
        extra = _lv_finish_targets(ctx, sd, i, above, p, htf_t)    # levels_detectors arrays
        if p.daily_vi_targets or p.news_ce_target:                 # setups_models M1.1 / N6
            more = _SM.more_targets(ctx, sd, i, above, p)
            extra = list(extra) + more
        if extra:
            lv = sorted(set(lv) | set(extra))
        if p.mm_targets or p.proj_breaker or p.sd_anchor in ("broken", "multi"):
            rr_ = _mss_ref(ctx, sd, sw, i, p)
        lv = sorted(set(lv) | set(_TP.extra_sources(ctx, sd, i, p, sw, entry, risk, leg_hi, above, lv, lvt, rr_)))
        if p.wick_tfs:                     # A23 wick_tfs: the nearest two long 1h / 4h wick CEs are targets
            wk = sorted(w[0] for w in _TP.tf_wicks(ctx, sd, i, p, p.wick_tfs, above))[:2]
            lv = sorted(set(lv) | {(v, "wick") for v in wk})
        lv = _TP.refine(ctx, sd, i, p, lv, sw, entry, above, lvt)
        if p.daily_fvg_exact:          # review fix: the exact daily edge replaces its "array" twin
            lv = _drop_near_exact(lv, 0.25 * p.es_pt)
        if p.ob_targets_1m or p.target_ltf_obs:   # A12 / X1: untraded opposing order blocks of the session's bars
            lv = sorted(set(lv) | set(_EN.ob_target_levels(sd, i, above, p)))
        if p.erl_exits_only:           # L14b: exit at external range liquidity only
            lv = [(v, k) for v, k in lv if k in POOL_KINDS]
        kinds = [kind for v, kind in lv]
        lv = [_exit_px(v, kind, p) for v, kind in lv]
    inner_ex = _TP.inner_extras(p, entry, risk, lv, kinds) if fixed is None else []   # X1 keep_inner_levels
    if p.round_step_pts:               # L17: targets rounded toward price (down for a long)
        pairs = sorted({(_round_px(ctx, sd, i, v, p, up=False), k) for v, k in zip(lv, kinds)})
        pairs = [(v, k) for v, k in pairs if v > entry]
        lv, kinds = [v for v, _ in pairs], [k for _, k in pairs]
    # owner #7 REVISED (Ep 02): an opposing HTF FVG between the entry and the target is a SPEED BUMP (a
    # partial at its near edge, the rest stays for the draw); "cap" / "split" keep the first build's cap
    capped, resist, capx, bumps = False, None, None, []
    if p.htf_resist_cap:
        rs_ = _TP.apply_resist(ctx, sd, i, p, entry, risk, lv, kinds, _f)
        if rs_ is None:
            return None
        lv, kinds, capx, bumps = rs_["lv"], rs_["kinds"], rs_["capx"], rs_["bumps"]
        resist, capped = rs_["resist"], rs_["resist"] is not None
        if bumps:
            lvt.append("speed_bump")
    if p.breaker_first and fixed is None:      # A22: an opposing breaker in the path ends the run in front of it
        bc = _TP.breaker_cap(ctx, sd, i, p, entry, risk, _f)
        if bc is False:
            return None
        if bc is not None:
            pairs = [(v, k) for v, k in zip(lv, kinds) if v <= bc]
            if not any(abs(v - bc) <= p.es_pt for v, _ in pairs):
                pairs.append((bc, "array"))
            pairs.sort()
            lv, kinds = [v for v, _ in pairs], [k for _, k in pairs]
            lvt.append("breaker_first")
    if p.bpr_rule and fixed is None:   # Ep01.4: the first target is capped at the next BPR above
        caps = [z for z in sd.bprs(p.bpr_max_gap_bars) if z.i <= i and z.bottom > entry]
        if caps:
            cx = min(z.bottom for z in caps) - p.exit_before_pts * p.es_pt
            if cx - entry < p.min_rr * risk:
                _f("x_bpr_cap")
                return None
            if not lv or lv[0] > cx + p.es_pt:
                lv, kinds = [cx] + lv, ["array"] + kinds
            lvt.append("bpr_cap")
    eps = 1e-9 if fixed is not None else 0.0      # fixed R-multiple rungs: exactly 1R passes
    keep = [(v, k) for v, k in zip(lv, kinds) if v - entry >= p.min_rr * risk - eps]
    pools = [v for v, k in keep if k in POOL_KINDS]
    lk = getattr(ctx, "cur_lock", None) if p.draw_lock == "session" else None
    lk_t = lk if fixed is None else None       # fixed-target setups: the lock gates the side only
    final_T = lock_capped = False
    if lk_t is not None:               # owner #9: ONE exact target, locked before the session
        tv = sd.x(lk["target"])
        T = tv + p.pool_beyond_pts * p.es_pt if (p.exit_mode == "split" and lk["kind"] in POOL_KINDS) \
            else tv - p.exit_before_pts * p.es_pt
        if p.round_step_pts:
            T = _round_px(ctx, sd, i, T, p, up=False)
        kT = lk["kind"]
        if p.erl_exits_only and kT not in POOL_KINDS:
            _f("x_erl_only")                      # L14b: the locked draw is not external range liquidity
            return None
        if capx is not None and T > capx:
            # owner #7 x #9: the draw's exit must be on the near side of the cap - an unbroken
            # opposing HTF FVG before the draw ends the trade in front of it [our interpretation;
            # OWNER QUESTION: or lock only near-side draws, draw_lock_near_cap=True]. Tagged
            # lock_capped so the share of trades whose locked draw was replaced is reported.
            T, kT, lock_capped = capx, "array", True
            _f("x_lock_capped")
        if T - entry < p.min_draw_pts * p.es_pt or T - entry < p.min_rr * risk:
            _f("x_room_lt_min")
            return None
        if not p.draw_lock_partials:
            rungs = []
        elif p.draw_lock_levels == "frozen":
            rungs = []
            for v, k, _, dr in lk["marked"]:     # levels marked at the lock, either side of the
                if k in POOL_KINDS and dr not in (0, sd.sign):   # lock price; pools only on the
                    continue                         # trade's side (buy-side highs for a long)
                if p.erl_exits_only and k not in POOL_KINDS:
                    continue
                x = _exit_px(sd.x(v), k, p)
                if entry + p.min_rr * risk <= x < T - p.es_pt:
                    rungs.append((x, k))
            rungs += [(b, "bump") for b in bumps if entry + p.min_rr * risk <= b < T - p.es_pt
                      and not any(abs(b - r_[0]) <= p.es_pt for r_ in rungs)]       # owner #7: the speed bump
            rungs = sorted(set(rungs))
        else:
            rungs = [(v, k) for v, k in keep if v < T - p.es_pt]
        keep = rungs + [(T, kT)]
        draw, final_T = T, True
    else:
        if not keep:
            _f("x_no_target_1R")
            return None
        draw = pools[0] if (pools and fixed is None) else keep[-1][0]   # the draw: the nearest pool
        if fixed is None and p.pm_off_lunch and session == "PM" and "lunch" in ctx.sess and ctx.t[i] >= ctx.sess["lunch"][2]:
            lu = sd.x(ctx.sess["lunch"][0] if sd.sign > 0 else ctx.sess["lunch"][1])
            lu = lu + p.pool_beyond_pts * p.es_pt if p.exit_mode == "split" else lu - p.exit_before_pts * p.es_pt
            if lu - entry >= p.min_rr * risk and sd.h[_idx_at(ctx, 810):i + 1].max(initial=-np.inf) < lu:
                draw = lu              # M7.1: the untaken lunch high is the PM draw
                keep = [(v, k) for v, k in keep if v < lu - p.es_pt] + [(lu, "pool")]
        if fixed is None:                  # levels_detectors draw overrides (nearest with room)
            prefs = [(_exit_px(v, k, p), k, n) for v, k, n in _draw_prefs(ctx, sd, i, entry, p, session, keep)]
            if p.eq_pref != "off":         # Ep06.7: the nearest relative-equal pool is the draw
                eqv = [(v, k, "rel_eq") for v, k in keep if k == "pool_eq"]
                if eqv:
                    prefs.append(eqv[0])
                elif p.eq_pref == "require":
                    _f("x_no_eq_draw")
                    return None
            if p.m2_target or p.mmxm_ctx or p.pm_lunch_target:      # setups_models M2 / Ep05.8 / M7
                prefs += _SM.draw_prefs(ctx, sd, sw, i, p, session, entry, risk, keep)
            if p.pool_rank or p.draw_below_eq or p.lrlr_max >= 0 or p.clean_eq_pref:   # L4 / Ep04.11
                prefs += _TP.draw_pref(ctx, sd, i, p, entry, risk, keep, leg_hi, sw)
            prefs = sorted(x for x in prefs if x[0] - entry >= p.min_rr * risk)
            if prefs:
                draw, kd, nm = prefs[0]
                keep = [(v, k) for v, k in keep if v < draw - p.es_pt] + [(draw, kd)]
                lvt.append("draw_" + nm)
        if p.min_draw_pts and draw - entry < p.min_draw_pts * p.es_pt:
            _f("x_room_lt_min")
            return None                                   # not enough room to the draw (minimum)
    if not _SM.unengaged_ok(ctx, sd, i, p, session, draw):   # setups_models Ep01.13
        _f("x_lh_engaged")
        return None
    lv, kinds = [v for v, _ in keep], [k for _, k in keep]
    if p.t1_fixed_pts > 0:             # Ep03.24 test (owner #2: not the goal, default off)
        f = entry + p.t1_fixed_pts * p.es_pt
        if p.t1_fixed_all:
            lv, kinds = [min(f, lv[0])], [kinds[0]]
        elif f < lv[0] - p.es_pt and f - entry >= p.min_rr * risk:
            lv, kinds = [f] + lv, ["fixed"] + kinds
    scalp = False
    sl = getattr(ctx, "cur_sloppy", "")
    if (sl and p.sloppy_mode == "scalp") or _NC.scalp_now(ctx, p, session):   # #10 scalp mode (N3.3: the FOMC-only AM):
                                          # one exit at min(+5, T1), no adds
        lv, kinds, scalp, final_T = [min(entry + p.sloppy_scalp_pts * p.es_pt, lv[0])], [kinds[0]], True, False
    smt_n = int(sw["smt"] is True) + int(sw.get("smt2") is True)
    if smt_n < p.smt_min:
        _f("x_no_smt")
        return None
    risk_mult *= _EN.size_mult(ctx, sd, sw, i, p, session, entry, htf, getattr(ctx, "cur_sloppy", ""), lvt)   # E9
    rungs = []
    lad = tags.pop("ladder", None)                  # E2 / D11 ladder: FVG high, 75%, CE (one order, later rungs)
    xcap = p.size_up_cap_pct * ctx.equity if (p.size_up_cap_pct and any(x.startswith("size_up_") for x in lvt)) else 0.0
    plan = None                                     # the planned full size (all ladder rungs together)
    if lad and not stop_cc and all(px > stop for px in lad):    # a stop-cc order is one stop: no ladder
        fr = p.entry_ladder_fracs
        n_ = _first_units(p, ctx.equity, sum(f * (px - stop) for f, px in zip(fr, lad)), entry, risk_mult, xcap)
        n_ = _EN.cap_initial(n_, p)                 # E11 caps the WHOLE ladder; the rungs scale together
        qs = [_lots(n_ * f, p.lot) for f in fr]
        shares = qs[0]
        rungs = [(px, q) for px, q in zip(lad[1:], qs[1:]) if q >= max(p.lot, 1)]
        plan = shares + sum(q for _, q in rungs)
    else:
        shares = _EN.cap_initial(_first_units(p, ctx.equity, risk, entry, risk_mult, xcap), p)    # E11
    if shares < 1:
        return None
    plan = plan or shares
    _f("4_order")
    t = ctx.t[i]
    lh = p.last_hour[0] <= t < p.last_hour[1]
    setup = "am_mm" if session == "AM" else session.lower() if session != "PM" else (
        "pm_last_hour" if lh else "pm_sb" if 840 <= t < 900 else "pm")
    if final_T or fixed is not None:
        levels = lv
    else:
        levels = lv[:max(1, len(p.ladder_fracs))]
    rp = None                                       # targets_partials: the rung plan (None = the old ladder)
    if (fixed is None and not scalp and not p.t1_fixed_all and not tags.get("fracs") and not tags.get("single_exit")
            and not (p.moc_pool_exit and session == "PM" and p.last_hour[0] <= t < p.last_hour[1])):
        extras_ = list(inner_ex)
        if p.htf_bump_below_min:          # owner #7: a bump nearer than min_rr x risk is still a small protected partial
            extras_ += [(b, "bump", True) for b in bumps if p.inner_min_pts * p.es_pt <= b - entry < p.min_rr * risk - eps]
        if p.sd_half_partial or p.wick_partials:
            extras_ += _TP.partial_extras(ctx, sd, i, p, sw, entry, leg_hi, lv[-1], rr_, lvt)
        rp = _TP.plan(ctx, sd, i, p, entry, risk, above, list(zip(lv, kinds)), final_T, extras_, tg, eq_hi, lvt)
        if rp == "skip":
            _f("x_tgif_room")
            return None
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
                 lock_capped=lock_capped, sloppy=sl, scalp=scalp, no_adds=scalp, news_pd=news_pd, news_wait_min_actual=news_wait,
                 heavy_dead=heavy, rungs=rungs, leg_hi0=float(leg_hi),
                 no_new_extreme=p.no_new_extreme,
                 low_prob=bool(p.low_prob_no_adds and _EN.low_probability(ctx, sd, p, htf, sl, i)))
    if p.fill_through:
        order["through"] = p.fill_through * p.tick       # E3: the limit needs N ticks of print through it
    order.update(zone_top=zone_top, plan_shares=plan)    # plan: adds are sized from the FULL ladder
    if stop_cc:
        order.update(stop_entry=True)                    # entry is already the stop price (top + 1 tick)
    order.update(tags)
    order["lv_tags"] = "|".join(dict.fromkeys(lvt))
    order["lvx"] = lvx
    if rp is not None:                           # targets_partials: rungs resolved again at the fill (the day's split)
        order.update(rung_plan=rp["rungs"], fracs_fixed=rp["fracs_fixed"], run_local=rp["run_local"],
                     final_T=rp["final_T"], bulk=bool(p.target_order))
        lv_o, kd_o, _ = _TP.fill_plan(order, p.ladder_fracs, p)
        order.update(levels=lv_o, level_kinds=kd_o, t1=lv_o[0],
                     t2=(lv_o[-1] if rp["final_T"] and len(lv_o) > 1 else lv_o[1] if len(lv_o) > 1 else None))
    # setups_models order plumbing (run_day): the draw, the displacement leg, the MSS bar
    order.update(draw=draw, leg=(float(sw["ext"]), float(pd_hi)), broke=sw.get("broke"))
    if order.pop("single_exit", False):          # M5.1: one exit at the draw
        order.update(levels=[draw], level_kinds=[kinds[-1] if kinds else "array"], t1=draw, t2=None,
                     fracs=(1.0,))
    lh_ = session == "PM" and p.last_hour[0] <= t < p.last_hour[1]
    if p.moc_pool_exit and lh_:                  # T10: everything off at the first pool
        js = [k for k, kd in enumerate(order["level_kinds"]) if kd in POOL_KINDS]
        if js:
            order["levels"] = order["levels"][:js[0] + 1]
            order["level_kinds"] = order["level_kinds"][:js[0] + 1]
            order["final_T"] = False
    if p.pm_last_hour_model and lh_ and "cut" not in order:
        order["cut"] = _SM.lh_window(p)[1]       # M5: the owner #1 window end (15:50; strict 15:45)
    if p.po3_runner:
        order["runner"] = True                   # Ep04.3: the last fraction rides to the close
    return order


def _smt(ctx, sd, i, key, level, session, pctx, psides, ppos, p=None):
    """SMT divergence: the partner index did NOT take its own version of the swept level
    (by the same bar). None when there is no partner or the level has no partner twin
    (swing lows are keyed by bar index - no twin)."""
    if pctx is None:
        return None
    if not _smt_window_ok(p, ctx.t[i]):    # setups_models B18.2: SMT windows (smt_pre adds 05:00-09:30)
        return None
    ps = psides[sd.sign]
    j = ppos.index.searchsorted(ctx.idx[i], side="right") - 1
    if j < pctx.start:
        return None
    if key.startswith("rel_eq") and p is not None and p.smt_rel_eq:   # B18.1 rel-eq partner twin
        return _smt_qual(ctx, sd, i, p, _smt_rel_eq(ctx, sd, i, level, pctx, ps, j, p))
    if key.startswith(("rel_eq", "round", "swing_low")):
        return None
    # review fix: p passed, so the partner gets the levels_detectors keys too (ipda*, today_low, m3l,
    # prev_am, org*, gap_*, or_alt ...) - _extra_levels ran on pctx; a key the partner lacks -> None
    plv = _sell_side(pctx, ps, session, j, True, p).get(key)
    if plv is None:
        return None
    at = lambda m: pctx.start + int(np.searchsorted(pctx.t[pctx.start:], m))
    created = {"am_session": at(810), "lunch": at(810), "opening_range": at(pctx.or_end),
               "london": at(300)}.get(key)
    if created is None:
        created = _level_created(pctx, key, session)
    if key.startswith("news_range"):
        R = 510 if key == "news_range" else int(key[len("news_range_"):])
        d = getattr(pctx, "news_dr", {}).get(R)
        created = d["made"] if d and d["made"] is not None else (at(540) if R == 510 else None)
    if created is None or j < created:
        return None
    res = not _thru(ps.l[created:j + 1].min(), plv, getattr(ctx, "tk", 0.0))   # A2 booking tick
    if res and p is not None and p.smt_min_gap_pts:      # setups_models B18.1: "if not obvious ..."
        res = bool(ps.l[created:j + 1].min() - plv >= p.smt_min_gap_pts * p.es_pt - 1e-12)
    return _smt_qual(ctx, sd, i, p, res)


def _smt_qual(ctx, sd, i, p, res):
    """setups_models B18 smt_need_array: an SMT counts only at a PD array (the sweep bar's low in
    an HTF array: confluence timeframes daily_level_array_tfs, else the 15m/60m htf tag)."""
    if res is not True or p is None or not p.smt_need_array:
        return res
    cf = getattr(ctx, "conf", None)
    if cf is not None:
        now = ctx.idx[i] + pd.Timedelta(minutes=ctx.tf)
        return _htf_array(cf.at(now, sd.x(sd.l[i]), sd.sign), p)
    return bool(_htf_tag(ctx, sd, i, sd.l[i], p.eq_tol_pts * p.es_pt))


def _smt_rel_eq(ctx, sd, i, level, pctx, ps, j, p):
    """B18.1 [our interpretation]: the partner twin of a relative-equal-lows sweep = the partner's
    lowest swing low formed within pivot_n bars (by time) of the cluster's swing lows (confirmed
    before bar i / partner bar j); True when the partner has not traded through it since."""
    tol = p.eq_tol_pts * p.es_pt
    qs = [q for q in sd.pl if q.known <= i - 1 and abs(q.price - level) <= tol]
    if len(qs) < 2:
        return None
    pad = pd.Timedelta(minutes=ctx.tf * max(p.pivot_n, 1))
    t0, t1 = ctx.idx[min(q.i for q in qs)] - pad, ctx.idx[max(q.i for q in qs)] + pad
    pq = [q for q in ps.pl if q.known <= j and t0 <= pctx.idx[q.i] <= t1]
    if not pq:
        return None
    twin = min(q.price for q in pq)
    a = max(q.i for q in pq) + 1
    if a > j:
        return None
    return not _thru(ps.l[a:j + 1].min(), twin, getattr(ctx, "tk", 0.0))


from . import newscal as _NC  # noqa: E402  (news_calendar_times package; imports this module back)
from . import setups as _SM   # noqa: E402  (setups_models package; imports this module back)
from . import entries as _EN  # noqa: E402  (entries_stops_sizing package; imports this module back)
from . import targets as _TP  # noqa: E402  (targets_partials package: speed bump, rung plan, partials)
from . import manage as _MG  # noqa: E402  (management_exits package: exits, stops, re-entry)
