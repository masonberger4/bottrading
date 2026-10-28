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
from . import daycontext as _DW
from . import bias_day as _BD
from .daycontext import SEASONAL_DOW20

# ICT macro windows (T6): 08:50-09:10, 09:50-10:10, 10:50-11:10, 11:50-12:10, 13:10-13:40,
# 14:50-15:10, 15:15-15:45
MACROS = ((530, 550), (590, 610), (650, 670), (710, 730), (790, 820), (890, 910), (915, 945))
NEWS_1000 = {"ism_manufacturing", "ism_services", "jolts", "sentiment"}
NEWS_0830 = {"cpi", "jobs", "ppi", "pce", "retail_sales", "gdp"}
STOP_MODES = ("ob_mt", "fvg", "ob_near", "fvg_candle", "ce2", "fvg_c1_low", "fvg_bodies", "fvg_open", "sweep",
              "ob_mt_pure", "wick_ce", "m2_auto", "three_pd", "next_pd", "bpr75", "fixed")       # E6 / E6b / E6c / Ep01.20 / M2.5 / caption-gap entries_stops_sizing #3/3
ENTRY_MODES = ("edge", "ce", "edge_1tick", "iofed", "ladder")      # D11 / E2
# Ep07.2: the Ep 07 model in one preset (OB bodies before the break and VIs as entry zones, the body-midpoint
# stop, body exit and swing trail of Ep 07, VI holds, one tick inside the gap edge, VIs as adds)
PRESET_EP07 = dict(ob_entry="both", vi_entries=True, ep07_stop=True, ep07_body_exit=True, ep07_trail=True,
                   vi_hold=True, entry="edge_1tick", add_arrays=("vi",))
CF_SRC = {"fvg": 0, "ob": 1, "gap": 2, "vi": 3, "breaker": 4}   # confluence array sources (#7)


SMT_PICKS = ("first", "leader", "laggard", "trend", "laggard_objective", "middle", "clean_swing", "depth", "swept", "fixed_es", "clean")   # D15 (backtest.combine)


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
    mt_mode: str = "body"          # D4: order-block mean threshold of the "body" or full "range"; caption-gap D4-mt-source-tally (entries_stops_sizing #1/3): "sensitive" = (high + open) / 2 (cc04_013 ~07:02), "body_single_range_blended" = the body mean of a single candle, the range mid of a multi-candle block (065A)
    exit_mode: str = "split"       # D5: "split" = before arrays, just beyond pools; "before" = all
    pool_beyond_pts: float = 0.25  # ES pts beyond a liquidity pool (one tick)
    min_draw_pts: float = 5.0      # L15 / owner #2: MINIMUM room, measured to the draw's exit price
                                   # (after pool_beyond / exit_before); 5 = ICT's minimum (default),
                                   # 10 = new-trader switch. Not a target: targets are the draw / arrays
    leg_pd: float = 0.5            # D12: entry at/below this fraction of the displacement leg; 0 off
    leg_pd_at: str = "fill"        # check it when the order is armed ("arm") or, as ICT waits for
                                   # the retrace, against the leg high reached before the fill ("fill")
    am_exit: int = 720             # D16: AM leftovers out at 12:00 (minutes); 0 = hold to flatten
    pm_done_by: int = 0            # D16 test: PM out at this time once T1 filled (900 = 15:00) - the 15:00 DEADLINE variant, not ICT's 006 rule (that is last_hour_target_done: a target hit from 15:00 closes everything at the target)
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
    htf_bias: str = "off"          # daily HTF bias filter: off / react / draw / pd / combo / flip (htf.py); bias_htf adds
                                   # "ordered" (B2), "iof" / "combo2" (B6), "ob_mt" (B7), "mwd" (B10), "nwog" (B14.3), "candle"
                                   # (M0.1, bias_candle), "draw_pd" (Ep03.12), "wk" (B5 weekly), "pd20" (A21)
    flip_triggers: tuple = ("ob_mt", "wk_dc")   # B8 triggers of the htf "flip" column: ob_mt (B8a),
                                   # wk_dc (B8c), flip_pd3 (B8b), flip_close_above (B8d), flip_thu_wopen
                                   # (B8e); B8f is the engine switch stop_flip
    bias_neutral: str = "skip"     # with a bias filter, a 0 day: "skip" it, trade "both" sides, or (Ep02.6) "scalp" them, or ("scalp_week", B17-neutral-htf-monday-close) scalp them at scalp_week_risk x the size
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
    daily_level_needs_array: bool | str = False   # (L2 76: "fvg" = the array must be an FVG within a tick of the swept level; True / "any" = any PD array) Ep 08 / 010 ~63:38: a PDH/PDL sweep needs an HTF PD array there
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
    bias_open: str = "midnight"          # the AM premium/discount open: "midnight" / "0830" / "0930" (D22); Ep08.3 "all" = the
                                         # entry must be on the right side of EVERY one of the three opens already printed
    bias_open_src: str = "data"          # D22: where the midnight open comes from: "data" = the frame's own first bar from 00:00 (a
                                         # futures / CFD midnight bar; SPY's 04:00 stand-in), "spy" = force the 04:00 stand-in
                                         # (the old behaviour, for comparison), "es_map" = a futures midnight open mapped to the
                                         # traded instrument by the prior close ratio (backtest.prepare(ref_df=...), paper mode)
    es_symbol: str = "/ES"               # D22 es_map in paper mode: the futures symbol whose bars give the midnight open
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
    ifvg_entry: str = "edge"             # M10 (078 ~50:28; 085 ~27:21): "ce" = limit at the IFVG CE; "quadrant" (caption-gap A8-ifvg-narrative-liquidity-run, 078 ~51:00) = its upper quadrant (75%)
    ifvg_stop_pts: float = 0.0           # M10 (102 ~1:40:20): stop N ES pts beyond the CE (3-4 per ICT)
    ifvg_min_risk_pts: float = 0.0       # M10: IFVG stops under N ES pts too tight (except 1m and below)
    ifvg_depth: bool | str = False       # A8 (102 ~1:09:00): True = no prior pass -> stop beyond the far edge; re-traded (the first build); "w_cap" = caption-gap A8-ifvg-depth-tolerances cases a / b / c; re-traded
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
    smt_pick: str = "first"              # Ep03.11 / D15 (backtest.combine): "leader" / "laggard" by the SMT tag; D15 "trend" = the leader
                                         # on trend days, the laggard on consolidation days (the DayPlan's consolidation tags)
    one_market: bool = False             # D15 / Ep05 "watch one market only": after the first fill of the day the other instrument's
                                         # trades are dropped for the rest of the day (backtest.combine)
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
                                         # (= "manip": [our interpretation] execution.md ~205 (relabelled "inception-to-fulcrum leg", caption-gap D23-inception-fulcrum-anchor: see sd_fulcrum_def) was read as "on the manipulation leg" = the
                                         # London swing low..high, measured once its high was taken - NOT the sweep leg that runs
                                         # stops; the sweep leg is "leg"), "multi" (all); caption-gap targets_partials #2/4: "entry_low" (L12-projection-exit-1tick:
                                         # the fill bar's low .. the first pivot high after it, built mid-trade), "m15_leg" (L12-prior-session-swing-htf-extreme: the
                                         # last 15m swing low -> high), "mss_leg" (L12-minus3-sd-last-hour: = "broken")
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
    tgif_exits: bool | str = False       # M14.4: 25/25/50 at the first three zone levels; caption-gap M14-tgif-management (066): "066" = L20 / L22.5 / L25 / L27.5 / L30 with 15/15/50/10/10 (targets_partials #4/4)
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
    reentry_fomc_ok: bool = False        # X13b: a re-entry on an FOMC day (default: none; the 021 citation was wrong - see fomc_no_reentry)
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
    fomc_no_reentry: bool = True         # N3 / N3.5: a loss on an FOMC day ends the day for every session and model - a design choice resting on N3's 14:00-14:45 observation-only rule and the FOMC PM block, NO source (caption-gap N3-021-citation-misread: 021 ~43:56 shows an AM trade that day)
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

    # ---- package day_week_context (rule_coverage.md section 3; mentorship/daycontext.py; build_log.md) ---------------
    # B11 / B11b / B11c candle-pattern day context (completed daily / weekly candles only)
    b11_inside_week: str = "off"         # B11 / B11c (103 ~12:53): the last completed week was an inside week: "tag", or "scalp" -
                                         # expansion within b11_inside_week_days candles (a daily close outside the inside week's
                                         # range) else scalp-only for the rest of the week [our interpretation]
    b11_inside_week_days: int = 2
    b11_inside_expansion: str = "off"    # B11 / B11c (012 ~16:17): yesterday an inside day -> a large range is due: "tag", or
                                         # "no_chop_skip" (the consolidation stand-aside, #10 chop, is waived that day)
    outside_day_rule: str = "off"        # B11b (081 ~1:31): a down-close outside day -> lower prices until that day's high is taken:
                                         # "tag", or "block" (no longs until today's price has traded that high)
    outside_day_mirror: bool = True      # [our interpretation] the up-close outside day blocks shorts until its low trades
    nr_tags: tuple = ()                  # B11 (cc06_007 ~21:24): tag "nr3" / "nr7" (yesterday has the smallest range of 3 / 7 days)
                                         # and "inside_body" (yesterday's body inside the day before's body)
    nr_expansion: str = "off"            # B11: an NR / inside-bar day -> expansion, no direction: "tag" or "no_chop_skip". The
                                         # inside day and the NR3 / NR7 readings all count while it is on (nr_tags only adds the
                                         # reporting tags and "inside_body", which is expansion only when listed there)
    # B17.4 daily range regime (the third reading of "sloppy": a multi-day range / inside daily BISI / run into premium)
    daily_range_regime: str = "off"      # "tag" / "scalp" (all sessions scalp) / "skip" (no trading) on a day whose completed daily
                                         # candles read as drr_tests say [our interpretation; sloppy_mode/sloppy_tests are the
                                         # intraday + day-level #10 owner switch, this one is the daily-candle regime]
    drr_tests: tuple = ("range",)        # "range" (the last drr_days sessions net moved < drr_net_frac of their high-low range and
                                         # that range is < drr_range_mult x their mean daily range: no daily trend), "inside_bisi"
                                         # (yesterday's whole range inside one open daily FVG), "premium_run" (a one-way run into an
                                         # old daily high / low) - any of them
    drr_days: int = 5
    drr_net_frac: float = 0.5
    drr_range_mult: float = 2.0
    # B15 ORG direction tell and gap x bias (030 ~1:27:01; 055 ~17:50)
    org_tell: str = "off"                # "tag" / "filter": the 09:30 gap with NO attempt back to org_tell_level of it by
                                         # 09:30 + org_break_min is very bullish (gap up) / bearish (gap down): only that side after 10:00
    org_tell_level: float = 0.5          # the attempt = price back to this share of the way to the prior close (50%)
    org_tell_wait: bool = False          # [our interpretation] no AM entry before the tell is known (10:00)
    org_bias_gap: str = "off"            # "tag" / "filter" (AM only): with the htf bias on the gap's side (bullish + gap up) price
                                         # reprices into the gap first, then goes higher (trade the bias side only after it); against it
                                         # (bearish + gap up) the fill is a false run (trade the bias side only)
    org_bias_src: str = "draw"           # the htf table column that is the bias: react / draw / pd
    org_gap_fill_frac: float = 0.5       # "repriced" = price back to this share of the gap
    # B16 Sunday gap scenarios (futures only: needs the Sunday 18:00 open; 028 ~1:09:37-1:16:09)
    sunday_scenario: str = "off"         # "tag" / "filter": at Monday 09:30 the scenarios "fill" (back to the gap CE) / "away"
                                         # (ran away from it) / "neither"; "filter": neither = no trade Monday (trade from Tuesday)
    sunday_away_mult: float = 1.0        # [our interpretation] "away" = beyond the Sunday open by >= this x the gap
    sunday_min_gap_pts: float = 1.0      # smaller gaps = "no_gap" (neither scenario can play out)
    sunday_no_gap_trade: bool = False    # [our interpretation] "filter": a Sunday without a gap has no scenario to wait for - False (the
                                         # default) treats it like "neither" (no Monday trade), True trades it as an ordinary Monday
    # N7 holidays and calendar (cc08_006 ~5:06; 090 ~8:00; 072 ~3:36; 079 ~8:54; 093 ~0:32)
    skip_holiday_eve: bool = False       # N7.1: no trading the day before a long weekend / market holiday
    holiday_eve_bank: bool = False       # N7.1 "and bank holidays": Columbus / Veterans Day count as holidays
    early_close_flat: bool = True        # N7.1 EARLY_CLOSE: flat before a shortened day's close (those days are not loaded by
                                         # backtest.days(); matters for live / custom frames)
    skip_post_holiday_am: bool = True    # N7.2 (090 ~8:00): the morning after a holiday is choppy - no AM trade (PM / next day)
    post_holiday_pre_open: bool = False  # N7.2: the post-holiday AM block also covers the 07:00 / 08:00 pre-open (Ma Deuce) windows
                                         # (False = the NY 09:30 family only [our interpretation])
    post_holiday_pm_sync: bool = False   # N7.2: the PM trades only once ES / NQ move in step (needs the partner instrument)
    holiday_week_thu_fri: str = "off"    # N7.3 (072 ~3:36): holiday weeks deliver cleaner Thu / Fri: "trade" lifts the NFP-week
                                         # Thu / Fri block in a holiday week (the holiday_week tag is always set)
    year_first_am_from: int = 0          # N7.4 / Ep02.7: first trading day of the year, no AM entry before this minute (e.g. 600)
    roll_week_src: str = "calendar"      # N7.5: where the roll week comes from: "calendar" (the week of the roll Thursday, 8 days before the
                                         # third Friday), "data" (the databento roll flag / contract change known by the day's first bar:
                                         # the roll's own day, tagged roll_day) or "either"
    skip_roll_week: bool = False         # N7.5 (093 ~0:32): the futures roll week is more volatile / choppy - no trading
    roll_risk: float = 1.0               # N7.5: risk multiplier in the roll week (e.g. 0.5)
    august_risk: float = 1.0             # N7.6 (079 ~8:54): August "meat grinder": trade small (risk multiplier from august_from_day)
    august_from_day: int = 1             # 15 = the last two weeks only
    skip_august: bool = False            # N7.6: stand aside in August (from august_from_day)
    low_vol_inside: str = "off"          # Ep01.8 / N7.4 (Ep 01 ~16:42): the last trading day of the year is a low-volatility inside
                                         # day: "tag", "scalp" or "skip"
    low_vol_holiday_adj: bool = False    # also the days next to a market holiday
    first_day_wait: int = 0              # Ep02.7 (Ep 02 "don't rush"): first trading day of the year, AM entries from this minute (a floor:
                                         # values <= the order's own time move nothing; 0 = off)
    first_day_skip_am: bool = False      # Ep02.7: no AM trade on the first trading day of the year (PM allowed)
    # N8 day type
    adr_basis: str = "rth"               # N8.5 / X16a: the ranges of the day_week_context rules: "rth" (09:30-16:00) or "eth" (full sessions)
    consol_skip: bool = True             # N8.1 (cc01_001): consolidation = no trade - the #10 chop test (range < 0.35 ADR5 and 4+ crosses of
                                         # the midnight open) stands aside; False = chop never stops a session (expansion resumes trading)
    trend_recipe: str = "off"            # N8.2 (cc10_009 ~1:17-2:46): small / contracting prior ranges + price just traded into a daily
                                         # array + high / medium 08:30 news: "tag", "only" (trade only such days), "side" (the array's side)
    trend_small_frac: float = 0.8        # [our interpretation] small = yesterday's range < this x ADR5
    trend_contract: bool = False         # require three contracting ranges (instead of small OR contracting)
    trend_news: tuple = ("high", "medium")
    trend_array_days: int = 2            # price "just traded into" the array within this many sessions
    consol_day_rules: str = "off"        # N8.3 (cc10_008 ~1:51-17:19): consolidation-day predictors (no report today / HTF array / HTF 50% /
                                         # holiday eve / auction): "tag" or "apply" (AM scalps only if the opening range is small, out by
                                         # 11:00, PM only if the AM has not run a stop pool)
    consol_predictors: tuple = ("no_report", "htf_array", "htf_50", "holiday_eve", "auction")
    consol_min_predictors: int = 1
    consol_or_frac: float = 0.25         # [our interpretation] a small opening range: 09:30-10:00 range < this x ADR5
    consol_am_out: int = 660             # out by 11:00
    consol_eq_tol: float = 0.1           # [our interpretation] "at the HTF 50%": within 10% of the prior week's range of its midpoint
    consol_pm_rule: bool = True
    consol_pm_pools: tuple = ("pd", "london", "draw")   # N8.3 "the AM ran a stop pool": the prior day's high / low, London's, the AM lock's own
                                         # draw; "on" (the overnight range: nearly always run) is opt-in [our interpretation]
    big_day_am_skip: bool = False        # N8.4 (033 ~13:27): a very large prior range or a large ORG gap -> the first 30-45 min chop:
                                         # sacrifice the AM (everything before 13:30), keep the PM
    big_day_range_mult: float = 1.5      # [our interpretation] very large = prior range > this x the ADR5 before it
    big_day_org_frac: float = 0.5        # [our interpretation] large ORG = |open - prior close| >= this x ADR5
    expansion_due: bool = False          # N8.5 (cc08_006 ~23:33): prior range < expansion_frac x ADR5 -> expansion_due tag
    expansion_frac: float = 1.0
    expansion_targets: tuple = ()        # N8.5: multiples of ADR5 above (below) today's extreme as array targets, e.g. (1.5, 2.0)
    sd_no_hold: bool = False             # N8.6 (024 ~13:57; cc07_002 ~7:42) seek & destroy: once both sides of yesterday's range ran
                                         # today, new trades are scalps (no hold, no runner)
    sd_week_skip: str = "off"            # N8.6: S&D weeks (waiting on rates / NFP, July-August): "tag" or "skip"
    sd_week_months: tuple = (7, 8)
    sd_week_news: bool = True            # FOMC and NFP weeks count as S&D weeks
    sd_context_required: bool = False    # sd_no_hold only inside an S&D week
    # N9 in-day no-trade conditions
    eve_draw: bool = False               # N9.2: Trade.eve_draw_px / side / done - the draw at the prior close and whether it was delivered pre-09:30
    pre_draw_pm: bool = False            # N9.2 (022 ~1:16:11): that draw delivered before 09:30 -> choppy 09:30, no AM trade, PM kept
    objective_done_skip: bool = False    # N9.3 (015 ~16:22): the day's objective delivered before 12:00 (the AM lock, or a morning
                                         # trade's last level) -> the PM (and lunch) are done
    min_on_range_frac: float = 0.0       # N9.4 (015 ~11:58): overnight range < this x ADR5 -> no AM trade (0 = off)
    min_raid_pts: float = 0.0            # N9.4: pre-09:30 raid shallower than this many ES pts -> no AM trade (0 = off)
    raid_ref: str = "pd"                 # the raided level: "pd" (the prior day's high / low) or "london" (the London range)
    on_range_from: str = "midnight"      # the overnight range from midnight or the "globex" 18:00 reopen (needs the evening bars)
    macro_no_move: bool = False          # N9.5 (073 ~30:51): the AM macro (09:50-10:10, 10:50-11:10) makes no move toward the draw ->
                                         # the AM is over (the charts are closed)
    macro_no_move_pm: bool = False       # the same for the PM macros (13:10-13:40, 14:50-15:10)
    macro_no_move_wins: tuple = ((590, 610), (650, 670))
    macro_no_move_pm_wins: tuple = ((790, 820), (890, 910))
    macro_move_pts: float = 0.0          # [our interpretation] "a move" = the window's extreme beyond the reference extreme by > this
    macro_ref_min: int = 30              # reference = the extremes of the minutes before the window
    london_adr_skip: float = 0.8         # N9.6 (cc08_001 ~13:41): London already made this x ADR5 (0 = off) -> skip NY
    london_adr_win: tuple = (120, 300)   # the London window of N9.6 and of the N9.4 raid_ref="london" test: 02:00-05:00, the same
                                         # window as ctx.sess["london"] and T3 (one London everywhere; the pre-open 07:00 / 08:00 windows
                                         # see the finished range, the NY open sees it too)
    # N10 day of week
    monday_mode: str = "trade"           # N10.2 / D20 (065B ~4:12; 101 ~30:53): "skip", "pm_only" or "obvious" outside NFP / FOMC weeks;
                                         # Tuesday after a Monday holiday acts like Monday (cc09_008 ~55:24)
    monday_small_range: float = 0.0      # D20 (cc08_001): Monday's range is small - no new entry once the day's range >= this x ADR5 (0 = off)
    tue_off_monday: str = "off"          # N10.2 (cc12_003 ~15:40): "tag" / "filter": Tuesday off Monday's low / high, Wednesday off
                                         # Tuesday's - the sweep must take the prior day's extreme (main engine, Silver Bullet and Ma Deuce -
                                         # whose "sweep" is the day's lowest low before the retest; no reference after a Monday holiday).
                                         # "tag": day tag tue_off_monday + per-trade off_ref_swept / off_ref_not_swept
    pool_mon_wed: bool = False           # N10.3 (cc07_008 ~1:35): Thu / Fri: the Mon-Wed high / low are sweep pools and targets
    mon_wed_extreme: str = "off"         # N10 / N10.3: "tag" mw_break_up / mw_break_dn (Thu / Fri break of the Mon-Wed extreme) and thu_reversal
    thu_fri_break: str = "off"           # N10.3 (cc07_001 ~42:44): "side": after a Thu / Fri break of the Mon-Wed extreme only the break side
    friday_slow_split: bool = True       # N10.4 (070 ~1:06:37): Friday takes most at the first pool - the 80/20 split (main engine via _split,
                                         # and the Silver Bullet ladder when sb_split is on; Ma Deuce keeps its own ladder)
    friday_first_pool: bool = False      # N10: everything off at the first pool on Fridays (main engine and Silver Bullet; Ma Deuce's
                                         # target is the daily FVG's CE, not a pool: n/a)
    friday_objective: str = "off"        # N10.4 (cc08_001): "tag" / "scalp" / "skip" when the weekly objective is already delivered
    friday_week_done: str = "off"        # N10.4 (100 ~7:05): "draw" (the weekly objective delivered) / "trades" (every trade of the week
                                         # hit its last target) -> no Friday trading
    strong_thu_no_long: bool = False     # N10 (cc09_008 ~41:53): no Friday longs after a strong (up) Thursday
    strong_thu_mirror: bool = False      # [our interpretation] and no shorts after a strong down Thursday
    no_fri_after_strong_thu: bool = False   # N10.4: no Friday trading at all after a strong Thursday
    strong_thu_mult: float = 1.0         # strong = range >= this x ADR5 and the close in the top / bottom strong_thu_frac of the range
    strong_thu_frac: float = 0.25
    tue_week_extreme: str = "off"        # T14 (cc08_001 ~20:43; study_week.py): "tag" / "side" - on Tuesday trade the htf draw side only
    # M14 / M14.1 / M14.3 TGIF model
    tgif_model: bool = False             # M14: the whole model - tgif, tgif_zone, tgif_htf_array, tgif_timing, tgif_week_sweep (forced on
                                         # by __post_init__, replace() re-runs it); tgif_model_skip names the sub-switches it must not force
    tgif_model_skip: tuple = ()          # e.g. ("tgif_zone",): the umbrella leaves those alone (set them explicitly)
    tgif_htf_array: bool = False         # M14.1 (066; 074): the week's extreme touched a D / W / 4h array or an NWOG / NDOG; the week from Sunday 18:00
    tgif_htf_tfs: tuple = ("4h", "D", "W")
    tgif_timing: tuple = ()              # M14.3 (066; 084): entry windows on TGIF days, e.g. ((600, 720), (810, 900))
    tgif_week_sweep: bool = False        # M14.3: Friday has swept the Mon-Thu extreme before the order (all three engines)
    # X10d / X15 / X15d / D19
    am_range_skip_pm: float = 0.0        # X10d: AM (09:30-12:00) range >= this x ADR5 -> no PM / lunch entries (0 = off)
    week_done_on_draw: str = "off"       # X15d (038 ~6:33; 101 ~34:21): the weekly objective (all-hours prior-week high / low, this week's
                                         # NWOG CE) delivered -> "tag" / "skip": done for the week
    week_done_levels: tuple = ("pwh", "pwl", "nwog_ce")
    week_done_pick: str = "any"          # "any" delivered objective, or "nearest" to the week's first open
    be_counts_as_win: bool = True        # D19: no_pm_after_am_win counts a breakeven (net >= 0) as a win (the old behaviour); False = net > 0
    # B23 / X16
    seasonal_tag: bool = False           # B23 (cc10_015 ~5:04): month map tag, HTF agreement, fail after day 10 - reported only
    seasonal_map: tuple = SEASONAL_DOW20
    seasonal_map_b: tuple = ()           # an optional second sample: the tag is "none" unless both lines agree
    seasonal_fail_day: int = 10
    journal_tags: bool = True            # X16 / X16a / X16b / X16d: adr5_prev, adr_prev, adr_fill, adr5_today, taken_3d, entry_array_tf columns

    # ===== package bias_htf (rule_coverage.md section 3 "bias_htf"; build_log.md). The daily columns are built by bias_htf.py inside
    # htf.table (bias_htf.bx_string(Params)); the bar-level rules live in bias_day.py behind daycontext.side_ok / order_ok / gate /
    # scalp_now. Everything defaults to the old behaviour; nothing here is on unless named. =====
    want_all_engines: bool = True        # B3: the Silver Bullet and Ma Deuce honour the htf_bias side too (inert while htf_bias is "off")
    # B2 / B3 / L14 / L14a the draw
    draw_ext_target: bool = False        # B2 (104 ~16:18): beyond a liquidity draw the nearest inefficiency sets how far the run goes - the
                                         # locked target becomes that array (the pool a rung)
    judas_required: str = "off"          # B3 / M0 (068 ~16:30; 082 ~8:02): "tag" / "filter" - the bias side's entry waits for the Judas, price
                                         # delivered AGAINST the bias by judas_min_pts from the session's first open
    judas_min_pts: float = 2.0           # [our interpretation]
    draw_first: str = "off"              # L14 / L14a umbrella: "session" = draw_lock "session" + draw_lock_pick "ordered" (B2 order) + the HTF target
                                         # hygiene ("htf" in target_hygiene) + draw_ext_target (cond_draw stays a separate switch until the owner confirms it); draw_first_skip names the parts to leave
    draw_first_skip: tuple = ()          # from ("pick", "hygiene", "ext", "cond")
    cond_draw: bool = False              # L14e (080 ~16:58): a failed draw switches the lock once to the other side (the failed target spent).
                                         # [our interpretation] failed = the OTHER side's nearest marked level was taken before the draw was
                                         # reached (a retrace alone is the Judas, not a failure); the new draw is the next level beyond it
    matrix_tf_lower: bool = False        # L14c (cc06_003 ~0:50): after a reaction from timeframe X the draw is the opposing array one timeframe lower
    react_tf_tag: bool = False           # report the table's react_tf column (W / D) with matrix_tf_lower off
    # B6 institutional order flow
    iof_days: int = 10                   # B6: the sessions scored (candle respect + pivot raids) [our interpretation]
    iof_min: int = 2                     # |score| needed for a +1 / -1 reading
    # A21 premium / discount of the multi-day range
    day_pd: str = "swing"                # A21.2: "20d" = the P/D reading (htf `pd`, also in combo / combo2 / draw_pd) is the pd_day_range-session range
    pd_day_range: int = 20               # A21 / A21.2 (cc07_004 ~7:00; cc09_008 ~8:47): sessions of the day-context range
    pd_body_multiday: bool = True        # A21.4 (cc07_005 ~3:10; 058 ~41:54): bodies for the multi-day range, wicks for intraday legs
    pd_zone: str = "half"                # A21: "half" (< 50%) / "third" / "deep" (0.3 / 0.7) / "ote" (ote_band retracement) - the zone that counts as P/D
    ote_band: tuple = (0.62, 0.79)       # A21 (cc01_004 ~23:59): the OTE retracement band
    cond_pd_tags: bool = False           # build the pd20 column without using it (reporting)
    # B5 timeframe chain
    weekly_gate: str = "off"             # B5 (064 ~1:44:34; 095 ~12:52): "tag" / "filter" - weekly direction first: no side against the weekly bias
    news_topdown: str = "off"            # B5 (Ep 02): "tag" / "side" - on a release day the daily VI sets the side
    bellwether_15m: str = "off"          # B5 (013 ~2:36): "tag" / "filter" - the 15m bellwether (last 15m close vs the midpoint of the last four) must not deliver against the side
    # B7 / B8 / B9 flips and persistence
    how_rule: str = "off"                # B7 (101 ~32:58): "tag" / "no_long" / "no_short" / "both" - a daily close below 50% of the last down-close candle = high of the week in
                                         # (no longs); the mirror, a close above 50% of the last up-close candle in a decline week = low of the week in (no shorts)
    objective_neutral: str = "off"       # B9 / B17 (038 ~6:33): "day" / "week" / "both" - the previous day's / the week's draw delivered: bias neutral
    objective_met_stop: str = "off"      # B17.3: "day" / "week" / "both" - the same, but no new trades at all (stand aside)
    bias_persist: int = 0                # B9 (cc05_003 ~1:34:51): an opposite reading must show this many sessions in a row (or a close-based flip agrees) to count
    next_array_on_fail: bool = False     # B9 (cc05_015 ~18:45): a failed daily array -> the next weekly array is a re-buy (react +1 / -1), not a bias change
    nof_days: int = 3
    mwd_disp_mult: float = 1.0           # B10 (cc06_004 ~1:02): body >= this x the mean body of the last 10 bars for a displacement
    mwd_nest: str = "off"                # B10 cases B / C: "tag" / "filter" - entries only inside the weekly (B) / monthly (C) arrays
    # B13 weekly open
    weekly_open: str = "off"             # B13 (048 ~1:00:10): "sun18" / "mon00" / "either" - best longs below the week's open early, then above it
    weekly_open_early_days: int = 2      # Monday and Tuesday are "early"
    weekly_open_array_days: int = 60     # [our interpretation] B13 wo_expired: daily arrays older than this many sessions at the week's open are ignored (the table's lookback)
    # B14 NWOG
    nwog_regime: str = "off"             # B14.1 (025 ~3:11; 051 ~9:25-13:30): "tag" / "scalp" / "skip" on a consolidation week (returns to the gap, converging gaps)
    nwog_leave_adr: float = 0.5          # [our interpretation] "left sharply" = moved this many ADR5 from the gap
    nwog_returns_cons: int = 2           # returns to the gap that make a consolidation week
    nwog_converge_pts: float = 10.0      # B14.2 (053 ~1:31): [our interpretation, a distance heuristic - the rule says the gaps converge] this NWOG's CE within
                                         # this many ES pts of the previous one = converging (or three gaps in a row each closer, within 2x this)
    nwog_converge_mode: str = "near"     # B14.2 [our interpretation]: "near" (the default above) / "shrink" (only: the CE distances fall across three gaps in a row)
    nwog_bias: str = "off"               # B14.3 (036 ~16:00; 058 ~53:46): "tag" / "filter" - bullish while above the NWOG, bearish while below
    nwog_bias_reclaim: str = ""          # which level ends a state: "" (follow nwog_flip_edge), or an explicit override "low" (bearish until back above the low, bullish until back below the high), "ce", "high"
    # B17 neutral / no-bias conditions
    neutral_gate: tuple = ()             # B17: tests from fifty_fifty, premium_chop, draw_delivered, range_market, decoupled
    neutral_gate_mode: str = "tag"       # "tag" / "skip" / "scalp" for the tests above (premium_chop: before 09:30 only)
    neutral_5050: str = "off"            # B17.1 (025 ~11:18; 095 ~27:33): "armed" (both sides armed in one window: stand aside) / "react" (both sides' reaction weights alike)
    fifty_react_ratio: float = 0.5       # "react": the smaller side's weight at least this share of the larger
    chop_mode: str = "off"               # Ep08.2 (Ep 08): "skip" (wait for 09:30) / "skip_day" / "scalp" when stuck inside an HTF array or the overnight range is narrow
    chop_on_adr: float = 0.35            # [our interpretation] narrow = overnight range < this x ADR5
    chop_in_array: bool = True           # count "price inside a daily / weekly array" as chop
    decoupled_mode: str = "off"          # B17.5 (045 ~1:01:43; 090 ~41:00): "tag" / "scalp" / "skip" when the indices are decoupled
    decouple_days: int = 10
    decouple_corr: float = 0.5           # [our interpretation] daily-return correlation (S&P vs Nasdaq 100, prior sessions) under this = decoupled; 0.5 on a
                                         # 10-day window almost never fires (the study variants use 0.97) - an owner question
    smt_both: str = "off"                # B17.5 (090 ~41:00): "tag" / "skip" - SMT both ways at once with no bias = no trade
    # M0.1 / Ep02.6 / Ep03.12
    bias_candle: str = "D"               # M0.1: "D" / "W" - htf_bias "candle": the nearest unreached draw from the candle's open
    bias_candle_open: str = "session"    # M0.1 [our interpretation]: the daily candle's open = the session open (18:00 Globex) / "midnight" (ICT's 00:00 open;
                                         # the weekly candle then opens at the Monday 00:00 open)
    bias_candle_tag: bool = False
    no_narrative_scalp: bool = False     # Ep02.6 (Ep 02): no daily narrative (neutral bias) -> intraday scalps, small targets, no adds
    mmbm_zone: str = "off"               # Ep03.12 (Ep 03): "tag" / "filter" - the buy model enters the discount half of [sweep low .. draw]
    # B19 intermarket and B20 COT / OI / sentiment
    intermarket_model: bool = False      # B19 umbrella: dxy_gate "block", bond_range "scalp", bond_dir "filter", decoupled_mode "scalp" (intermarket_model_skip leaves parts alone)
    intermarket_model_skip: tuple = ()   # from ("dxy_gate", "bond_range", "bond_dir", "decoupled_mode")
    dxy_gate: str = "off"                # B19.1 (031 ~7:54; 045 ~42:05): "tag" / "block" - the dollar's prior close above its 20-day high and rising: no longs
    dxy_gate_days: int = 20
    bond_range: str = "off"              # B19.3 (061 ~1:05:42; cc10_008 ~8:47): "tag" / "scalp" / "skip" - the 10-year yield in a range: markets consolidate
    bond_range_days: int = 10
    bond_range_frac: float = 0.3         # the last bond_range_days' span under this share of the last 60 sessions' span
    bond_dir: str = "off"                # B19.3 / B57: "tag" / "filter" - rising yields (falling bonds) hold equity rallies back: no longs
    cot_oi_model: bool = False           # B20 umbrella: cot_tag / oi_tag / wpr_tag "tag" (cot_oi_model_skip leaves parts alone)
    cot_oi_model_skip: tuple = ()        # from ("cot_tag", "oi_tag", "wpr_tag")
    cot_tag: str = "off"                 # B20.1 (cc10_001 ~8:48; cc12_003 ~4:25): "tag" / "filter" - commercial net vs the midpoint of the 52-week range (files in data/mentorship/cot)
    cot_market: str = "E-MINI S&P 500"
    oi_tag: str = "off"                  # B20.2 (cc05_003 ~58:26): "tag" - the roll-summed open interest moved by oi_pct over oi_days (data/mentorship/ES_oi.csv)
    oi_days: int = 10
    oi_pct: float = 0.125
    wpr_tag: str = "off"                 # B20.3 (cc12_002 ~12:17): "tag" / "filter" - weekly Williams %R: <= -80 long, >= -20 short
    wpr_len: int = 14                    # B20-williams-r (cc12_002 ~13:41; cc06_007 ~25:49): the WEEKLY Williams %R period (10 / 14 / 20; spec name wpr_period)
    # B22 quarterly shift
    qshift_tag: bool = False             # B22 (cc05_001 ~5:05; cc12_001 ~18:43): tags qs_turn / qs_cons / qs_due from the 60-session turn or consolidation
    qshift_size: float = 1.0             # risk multiplier against the 252-session trend while a shift is due (1 = off)
    qs_turn_pct: float = 0.03            # [our interpretation] a turn = the sign of the 60-session change flips by at least this
    qs_cons_pct: float = 0.07            # a consolidation = the 60-session range under this share of the price
    qs_due_lo: int = 63                  # 3-4 months after the last shift began, in sessions
    qs_due_hi: int = 84
    # Ep06.6 / Ep08.3 the opens
    midnight_target: bool = False        # Ep06.6: the midnight open is a target rung toward it (a short entered above it)
    midnight_confirm: str = "off"        # Ep06.6 (Ep 06 ~0:51): "tag" / "filter" - the bias side needs price beyond the midnight open in its direction
    midnight_below_ok: bool = False      # Ep06.6: with use_bias, a confirmed bias side may enter on the far side of the midnight open

    # --- silver_bullet package (sb_model.py; the Silver Bullet stays OFF: sb_model=False) ----------------------------
    # Every switch cites its rule id and source (rule_coverage.md section 3 silver_bullet; rulebook_gaps/silver_bullet.md;
    # silver_bullet.md); "[our interpretation]" marks a judgment call. Defaults keep the previous Silver Bullet behaviour
    # except sb_pw_pools (spec "sb_pw_pools=True": PWH / PWL are in the 054 draw list) and sb_cancel_sticky (a cancelled
    # draw is not re-armed on the same bar); False/False reproduces the old build trade for trade (build_log.md).
    # windows (T6, M3.1; 054 ~08:51, 092 ~20:04, 099 ~53:30)
    sb_last_hour: bool = False           # T6: the 15:00-16:00 window (092 ~20:04; 099 ~53:30), entries 15:00-15:50 (owner #1)
    sb_lh_window: tuple = (900, 950)
    sb_0700: bool = False                # T6: the optional 07:00-08:30 window (099), futures only; flat at sb_0700_flat
    sb_0700_window: tuple = (420, 510)
    sb_0700_flat: int = 509              # T6: 08:29 flat (no position through the 08:30 release)
    sb_london_window: tuple = (180, 240) # T6: London 03:00-04:00 (needs sb_london)
    sb_extra: tuple = ()                 # M3.1: "pm2" = a second PM entry (056 ~15:00 "you get two chances"); "early" = fills
                                         # from sb_early_start (the 09:50 macro, test only) [our interpretation]
    sb_early_start: int = 590
    sb_moc_extra: bool = False           # gap 14 (056): a third PM window 15:15-15:45 when no PM SB hit its target
    sb_moc_window: tuple = (915, 945)
    # count / sessions (M3 umbrella, M3.9, gap 14)
    sb_one_per_day: bool = False         # M3 / 047 ~08:00 "if I was only going to trade one time a day": one SB per day
    sb_cascade: bool = False             # M3.9 / 054 ~18:01: London, else AM, else PM - a later window only if the earlier
                                         # windows produced no SB trade
    sb_one_market: bool = False          # M3.9 / 046 ~55:21: don't switch markets - backtest.combine keeps the first SB market
    sb_max_per_window: int = 1           # gap 14: SB entries per window (1 = old)
    sb_adds: bool = False                # gap 14 (080 ~17:20): a return into the filled FVG / a new FVG adds (half size)
    sb_am_done: bool = False             # gap 7 (048 ~1:35): done for the AM after an SB win (backtest.combine pass)
    # direction: draw first, one way (M3.2, M3.3, L14g; 054 ~09:52)
    sb_draw_first: bool = False          # M3.2: mark the 054 draw list and lock ONE draw before the window; trade only toward it
    sb_pw_pools: bool = True             # L14g: PWH / PWL are draws of the SB list (054 ~04:02)
    sb_ote_draw: bool = False            # L14g (054 ~04:02): a classic OTE of the prior day's leg is a draw [our interpretation]
    sb_htf_fallback: bool = False        # L14g / M3.2 (054 ~06:50): the draw was raided -> an HTF pool or array
    sb_htf_targets: bool = False         # L14g: merge the HTF conf arrays / opposing FVGs into the SB draw list
    sb_use_bias: bool = False            # M3.3: the main engine's want (htf_bias), weekly_bias and use_bias (entry in the discount of the
                                         # reference open, T2 / D22) also bind the SB
    sb_day_dir: str = "off"              # one direction per day: "lock" (the first window's locked side) / "first_trade"
    sb_day_dir_delivered: str = "hold"   # ... "hold" keeps the side after its draw printed, "free" releases it
    sb_weekly: str = "off"               # weekly-profile alignment (048 ~2:02): "tag" / "require" [our interpretation]
    sb_weekly_neutral: str = "allow"     # a profile with no side: "allow" / "skip"
    sb_sync: str = "off"                 # ES/NQ/YM in sync (045 ~1:01; 048 ~11:38): "tag" / "require" [our interpretation]
    sb_sync_mode: str = "mss"            # "dir" = the sisters moved the same way over the leg, "mss" = they also broke
    sb_sync_min: int = 1                 # sisters that must be in sync (of those present)
    sb_spotty: str = "off"               # 045 ~31:22-36:27 spotty day: "tag" / "skip" [our interpretation]
    sb_spotty_tests: tuple = ("no_disp", "no_fvg", "whipsaw")
    sb_spotty_min: int = 2
    sb_spotty_bars: int = 30
    sb_disp_pts: float = 0.0             # displacement size: the MSS candle's body >= N ES pts
    sb_disp_leg_pts: float = 0.0         # ... the run from the leg low to the MSS close >= N ES pts
    sb_disp_range_mult: float = 0.0      # ... the MSS candle's range >= N x the mean range of the 20 bars before the leg low
    # trigger / FVG pick (M3, M3.3, M3.5, D2; 044 ~0:50, 048 ~57:36, 058 ~44:37, 065B ~5:15)
    sb_mss_required: bool = True         # M3 / 044: False = displacement + FVG only (the MSS is then only tagged)
    sb_need_mss: bool = True             # M3.3 alias of sb_mss_required (both must be True for the MSS to bind)
    sb_fvg_in_window: bool = False       # D2: True = the FVG must form inside the window (the early 044 / 047 / 054 wording)
    sb_fvg_from: int = 0                 # D2: minute from which an FVG counts (0 = the leg start 09:30 / 13:30)
    sb_evolve: bool = True               # D2 / M3.4 (057 ~2:16): move the limit to a newer FVG
    sb_fvg_pick: str = "evolving"        # gap 16 (093 ~9:15): "evolving" / "first" / "any_in_leg"
    sb_need_sweep: bool = False          # M3.5: require a sweep of a prior level before the MSS (tag in swept)
    sb_sweep_max_pts: float = 0.0        # M3.5: the sweep may not run deeper than N ES pts beyond the level (0 = any)
    sb_sweep_alt: str = ""               # gap 5 (048 ~1:36): "discount_array" stands in for the raid
    sb_bpr_exclude: bool = False         # gap 6 (048 ~1:34:40): an FVG below the break / offset by an opposing FVG is no entry
    sb_cons_wait: bool = False           # gap 21 (072 ~35:41): consolidating -> wait for the displacement out of the range
    sb_cons_bars: int = 10
    sb_cons_pts: float = 2.0
    sb_cons_body_mult: float = 2.0
    sb_lrc_mult: float = 0.0             # gap 18 (057 ~2:16): large-range candle before the leg (x mean range of 20 bars)
    sb_lrc_mode: str = "tag"             # "tag" / "wait" (arm a flagged first FVG only after a later one) / "skip"
    sb_premise: str = ""                 # gap 13 (054 PM; 093): "htf_array" / "smt" / "either" before the MSS
    sb_nwog_expansion: str = ""          # gap 22 (054 ~5:17): "tag" / "require" a reaction at an NWOG
    sb_entry_arrays: tuple = ("fvg",)    # gaps 9 / 10: "ob" (5m order block, 049), "confluence" (wick CE + VI + MT, 090)
    sb_ifvg: str = ""                    # gap 1 (076; 092): "add" / "prefer" an IFVG near edge as an entry
    sb_ifvg_reaper: bool = False
    sb_ifvg_stop: str = "candle"         # "candle" / "breaker"
    sb_ifvg_market: bool = False         # 076: market buy on a down-close candle trading into the IFVG
    sb_ob_min_pts: float = 2.0
    sb_conf_min: int = 2
    sb_conf_tol_pts: float = 1.0
    sb_conf_mode: str = "tag"            # "tag" / "entry"
    sb_reverse_after_target: bool = False  # gap 15 (058 ~44-47): ONE opposite SB after an HTF-array target
    sb_cancel_ticks: int = 0             # gap 17 (057 ~4:18): cancel after a run N ticks beyond the draw (0 = at the exit)
    sb_no_overlap: bool = True           # SB package (review): no SB fill while an earlier SB trade (any window) is still open - one SB position at a time (double risk otherwise)
    sb_cancel_sticky: bool = True        # M3.5 / 057 ~3:35: once the draw traded and the order was cancelled the same draw is not re-armed
    sb_simple: bool = False              # gap 20 (069 ~15:05): EQ of the leg, target the first array beyond it, one exit
    # stop (M3.8, gap 19)
    sb_stop: str = "fvg_ob"              # "fvg_ob" = "090" (090) / "fvg2" (057) / "entry_candle" (086) / "swing" / "fvg_ce" (069)
    sb_stop_pts: float = 2.0             # sb_stop="fvg2": 2 ES pts beyond the entry (057 ~6:41)
    sb_max_stop_pts: float = 0.0         # gap 19 (057 ~2:54; 092 ~55:30): a stop wider than this is cut or skipped (0 = off)
    sb_wide: str = "skip"                # "skip" / "size"
    sb_abort: bool = False               # 045 ~1:19:58: a body closes outside the FVG and the next candle exceeds it -> out
    # room / draw (L15, gaps 2, 3, 7)
    sb_room_mode: str = "exit"           # L15: room measured to the "exit" price (owner #2) / the raw "draw" level
    sb_room_overshoot_pts: float = 0.0   # gap 2 (059): room counts this far beyond a pool (best case)
    sb_room_untaken: bool = False        # gap 3 (058 ~54:20): room never counts past a low already swept today
    sb_org_chop: bool = False            # gap 3: consolidating inside today's ORG is not a classic SB
    sb_org_chop_bars: int = 6
    sb_fail_mode: str = "skip"           # gap 3: "scalp" = half size to the nearer untaken pool
    sb_imm_tag: bool = False             # gap 7 (048 ~1:31): tag imm_rebal on the SB trade, count runaways
    # exits (M3.11, gap 8)
    sb_runner_if_weekly: bool = False    # M3.11 (048 ~2:02:12): the runner only when the weekly profile is aligned
    sb_supercharge: bool = False         # gap 8: Mon-Wed, daily not ranging, week extreme not yet in -> 1 lot runner
    sb_supercharge_seasonal: bool = False  # needs the B23 seasonal column (not built): reserved, no effect
    sb_gap424_fracs: tuple = (0.4, 0.2, 0.4)   # M3.11 / 057: 4 / 2 / 4 of 10 at the NWOG high / 75% / CE

    # --- caption-gap pass, levels_detectors #1/3 (digests/rulebook_gaps/*.md; every switch cites its gap id + source video/time) ---
    # X3-l8-vb-exhaustion-gap (cc04_009 ~2:48)
    vb_context: bool = False             # L8: a vacuum block is used only in context - bias side + the gap on the discount (premium) side of the 20-day
                                         # range EQ; a gap after 5 straight days (or above the 20-day high) is an EXHAUSTION gap, tagged and not used
    # X3-b21-ipda-anchor (cc05_001 ~53:44/~23:23/~26:56; cc05_003 ~19:10), B21-ipda-windows-arrays (cc05_001 ~22:58; cc07_005 ~14:17)
    ipda_anchor: str = "rolling"        # B21: where the 20/40/60 windows end - "rolling" (yesterday) / "month" (the session before the first trading day of the
                                         # last closed month) / "swing" (the last daily MSS)
    ipda_arrays_first20: bool = False    # B21: the HTF array lists use only arrays up to 20 sessions old until all of them are traded through, then 40, then 60
    # X3-b5-15m-pools-5m-gaps (cc05_003 ~1:27:21)
    pool_tf: int = 1                     # B5: minutes of the bars the intraday SWING pools are mapped on (1 = the base bars as before; 15 = 15m pivots)
    # X3-b10-topdown-transposition (cc06_003 ~20:01)
    topdown_targets: bool = False        # B10: the target ladder includes the transposed 4h / D / W / M opposing arrays in distance order
    # N8-consolidation-builds-orders (cc01_002 ~17:28)
    consol_pools: bool = False           # N8: when the intraday chop test releases, its range high / low are named pools consol_h / consol_l
    # A11-bpr-one-pass-definition (001 ~15:17; 003 ~29:37; 032 ~51:23; 056 ~7:24; 075 ~54:50)
    bpr_def: str = "overlap"             # A11: "overlap" (Type 1: a bullish and a bearish FVG overlap) / "single_range" (Type 2: a gap crossed both ways in one
                                         # pass, then left) / "both"
    bpr2_two_candle: bool = False        # A11 variant (a): two adjacent opposite-colour candles' overlap is a Type 2 zone too [our interpretation: off]
    bpr2_trail: bool = False             # A11 (003 ~29:37): a long's stop moves to the BPR low - 1 tick once a new bullish FVG forms above its high
    bpr2_cont_trigger: bool = False      # A11 (056 ~7:24): tag bpr2_cont when a retrace into a bullish FVG to its CE is followed by a trade above its high
    # X-efficient-delivery-two-pass (026 ~1:58:21; 050 ~30:29; 061 ~1:35:24)
    two_pass_state: bool = False         # A5: a gap band crossed both ways (efficient) is not a target; a band crossed several times shields the arrays beyond
    shield_passes: int = 3               # A5 [our interpretation]: >= this many two-way crossings = a shield (078 uses >= 2 opposite LTF candles)
    # A12-ob-candle-selection (012 ~14:06; cc04_003 ~1:00; cc03_004 ~10:30; cc06_005 ~19:10; 065 ~1:21:02; 032 ~53:04)
    ob_pick: str = "blend"               # A12: "blend" / "original" (first / highest candle) / "largest_body" / "blend_in_htf"
    ob_skip_encapsulated: bool = False   # A12 (cc06_005): skip a last candle whose body sits inside the previous same-colour body and is clearly smaller
    # A12-consolidation-ob-open-level (008 ~4:09)
    cons_ob_open: bool = False           # A12: the open of the last down-close 1h candle before a consolidation is support (up-close: resistance)
    # A8-inversion-any-pd-array (090 ~2:11:45; 068 ~13:37; 086 ~11:30; 035 ~1:02:55)
    inversions: tuple = ()               # A8: PD arrays that flip role on a body close through them: subset of "ob", "breaker", "vi", "org", "nwog"
    # A12-mt-all-blocks-ce-all-gaps (021 ~21:06)
    mit_mt_invalid: bool = False         # A12/A15: a body close through a mitigation block's MT drops it (E6 / X8 respect, for mitigation blocks)
    # A13-breaker-candle-selection (015 ~21:17; 032 ~41:26; 043 ~18:03; 060 ~26:39; 063 ~3:49; 081 ~12:52)
    breaker_candle: str = "extreme_close"   # A13: "extreme_close" (the built behaviour; owner question: the spec lists "last") / "last" / "extreme_body"
    breaker_body_swing: bool = False     # A13 (060 / 081): the swing is judged on bodies - wick-only extremes are discarded
    # A13-breaker-zone-extent: breaker_zone gains "blend" and "leg_disruptor" (025 ~12:13; 042 ~46:29; 044 ~37:47; 070 ~46:45)
    # A6-breakaway-identification (001 ~42:50/~44:20; 062 ~34:53/~35:59; 060 ~1:14:06)
    breakaway_def: str = "first_after_mss"   # A6: "first_after_mss" (Ep01.5) / "context" (needs an HTF level at the leg origin) / "second_mss"
    breakaway_ctx_pts: float = 10.0      # A6 [our interpretation]: the HTF level must lie within this many ES points of the leg origin
    # A5-caffeine-bar-bisi (006 ~12:34)
    single_bar_fvg_strict: bool = False  # A5: a gap whose middle candle is one large displacement candle is dead on ANY trade below its low (not a close)
    # A5-broken-fvg-reclaim (027 ~22:24; 091 ~20:18)
    fvg_reclaim: bool = False            # A5: a broken bullish FVG that price left (a swing away) and then closed back above is a discount entry again
    # B5-htf-arrays-anchor-transpose (043 ~3:13; 072 ~1:45; 074 ~7:00; 080 ~11:28; cc04_012 ~0:37/~5:25)
    htf_entry_arrays: tuple = ()         # B5: higher-timeframe bars (minutes, e.g. (15, 60)) whose FVGs / OBs are fixed entry zones on the lower chart
    # N-initial-fvg-reference (048 ~5:40; 082 ~5:13)
    initial_fvg: tuple = ()              # subset of "day" / "week" / "mon10": reference FVGs tagged respected / disrespected on the trade
    # A9-vi-definition-no-wick-condition (009 ~7:18; 036 ~22:55; 027 ~22:24)
    vi_wick_overlap: bool = True         # A9: True = the old rule (the two candles' wicks must overlap); False = ICT (bodies only; a wick gap too = also a void)
    vi_multi: bool = False               # A9: a VI may span a run of up to 3 candles (an earlier body in the run occupies its band)
    # A9-vi-delivery-state (035 ~21:01; 046 ~28:33; 050 ~33:20; 077 ~3:23; 090 ~14:07)
    vi_dead_rule: str = "full_span"      # A9: "full_span" (a body lays over the whole VI = vi_body_death, 046 / 090) / "overlap" (any overlapping body, 035)
    vi_two_sided_draw: bool = False      # A9: an open daily / weekly VI stays a draw from either side until dead (reached / target_hit do not retire it)
    # A9-daily-vi-forward-levels (025 ~23:19; 007 ~3:40/~8:59)
    vi_flip_support: bool = False        # A9: a daily VI price reached becomes a support / resistance level (edges + midpoint) for the rest of its week (the opposing role = targets)
    vi_flip_entries: bool = False        # A9 (025 ~23:19): the support-role reached daily VI (a short: resistance) is also an entry array on the retrace
    # A16-propulsion-context-sequence (cc04_008 ~3:58; cc09_008 ~14:45)
    pb_def: str = "a16"                  # A16: "a16" (as built) / "cc04_008" (context, OB, confirmation, move, then the PB) / "cc09_008" (looser)
    # A17-rejection-block-levels (015 ~2:18; 038 ~4:15; 059 ~10:11; 080 ~5:41; 090 ~34:21; cc04_006 ~9:23/~12:47)
    rb_level: str = "close"             # A17: level1 = the extreme CLOSE of the same-colour candles (015 / 038 / 059 / 090) / "open_close" (cc04_006: any open or close)
    rb_ce_level: bool = False            # A17: the rung ladder adds level2 (the wick CE) and W (the extreme wick)
    # A21-dealing-range-energetic-swing (028 ~1:07:33; 044 ~40:26; cc01_005 ~2:20/~9:40/~19:23; cc04_002 ~18:44)
    leg_anchor: str = "mss_leg"          # A21: the leg's low for leg_pd / OTE depth - "mss_leg" (the sweep extreme) / "energetic" (the latest displaced swing low)
    # A23-wick-quarter-strength (025 ~34:43; 028 ~15:24; 103 ~24:07/~27:23; 065 ~4:19:02; 075 ~1:05:07; 072 ~5:27)
    wick_quarters: bool = False          # A23: q25 / q75 levels of the prior-day wicks; a trade is tagged with how far its retrace into the wick got
    wick_bias_line: bool = False         # A23: no adds after a body closed through the 1h lower-wick tail's CE (the bias line)
    judas_wick_cap: bool = False         # A23: the Judas wick CE (high + body top) / 2 is a cap tag while rallies fail to close above it
    # confluence-stacked-arrays (100 ~6:05; 103 ~4:38/~25:04; 011 ~7:19)
    converge_rank: bool = False          # confluence: the entry gap with the most converging arrays wins; the trade carries the count
    # A3-diagonal-support-is-liquidity (045 ~26:02; cc03_007 ~2:12/~23:18)
    diag_pools: bool = False             # A3: a diagonal run of higher lows (lower highs) is a sweep pool (kind "diag") at the extrapolated line
    diag_min_swings: int = 3             # A3 [our interpretation]: swings within the tolerance of one line

    # --- caption-gap pass, levels_detectors #2/3 (digests/rulebook_gaps/*.md; every switch cites its gap id + source video/time) ---
    # A2-which-old-high (002 ~0:34)
    active_old_pool: bool = False        # A2: the active buy-side pool = the first earlier daily swing high ABOVE today's high so far (walk back newest to oldest); the sell side mirrors
    # A2-round-number-pool (002 ~2:37)
    round_pool_mode: str = "pool"        # A2: round handles (round_pools): "pool" = standalone pools (as built) / "confluence" = kept only where an old high / low / rel-eq pool lies within round_conf_pts, tagged round_conf / "tag_only" = never a pool, tag only
    round_conf_pts: float = 1.0          # A2 [our interpretation]: "near an old high" = within this many ES points
    # A3-engineered-liquidity (035 ~49:54)
    engineered_pools: bool = False       # A3: a lower high H2 that falls short of an older high H1 and then drops away builds buy stops above H1 - H1 is a pool (tag engineered), ranked by the time between them
    eng_short_pts: float = 3.0           # A3 [our interpretation]: "falls short" = H2 within this many ES points below H1
    # L1-rth-session-pools (067 ~15:00 / ~32:00 / ~55:50)
    rth_pool_spent: bool = False         # L1: the previous PM / AM / lunch RTH ranges are spent only by RTH prints (>= 09:30 today), never by overnight trade
    # L3-midnight-session-opening-ranges (050 ~18:13)
    session_ors: tuple = ()              # L3: (start_minute, minutes) opening ranges, e.g. ((0, 30), (0, 60), (1200, 30), (120, 30), (810, 30)): their high / low are low-priority pools once complete (tag sor_<start>_<min>)
    # L5-partial-redelivery (019 ~16:36)
    nwog_rebalanced: bool = False        # L5: an NWOG whose Sunday open ran to the far edge, back through, failed at the CE and left a lone FVG is rebalanced: only its near edge and the exit FVG's near edge stay targets
    # L5-cfd-nwog-mapping (036 ~1:32:40)
    nwog_cfd_src: str = "auto"           # L5: how an index CFD's NWOG is built - "auto" / "sunday_bars" (the bars at the futures' Friday close and at Sunday 18:00; a weekend without them is flagged unavailable) / "monday_0930" (Friday close -> Monday 09:30 open, 039; all weekends) / "sunday_else_monday" (per weekend: Sunday bars when present, else the Monday 09:30 variant) / "none"
    # A2-open-float (033 ~24:26; cc05_002 ~1:10; cc09_004 ~4:02)
    open_float_pools: bool = False       # A2: the resting stops of a denied-continuation range - the short-term highs formed during the decline (the lows of a rally) - are pools (kind float); a consolidation's internal highs / lows weigh more with its bar count
    float_denied_bars: int = 20          # A2 [our interpretation]: "denied continuation" = no new low (high) for this many bars ...
    float_denied_adr: float = 0.3        # ... with the range since the extreme under this fraction of ADR5
    # A11-htf-gap-own-tf (061 ~40:20; 078 ~1:13:50)
    balance_tf: str = "own"              # A11: which closes balance / retire an HTF array - "own" (only closes of its own timeframe; the spec default) / "legacy" (the earlier build: a weekly array is judged on DAILY closes) / "next_lower" (4h for daily, daily for weekly). Changes the bias table: the old behaviour is "legacy" (build_log owner questions)
    # A7-immediate-rebalance-definition (059 ~4:16; 060 ~7:29; 061 ~1:23:38; 078 ~1:15:05; 100 ~44:46; 099 ~1:04:01)
    ir_def: str = "a7"                   # A7: "a7" (yesterday's high, next candle) / "open_space" (the candle that bounds the open space, not necessarily yesterday's) / "zero_width" (c3 low == c1 high to the tick after a large c2)
    ir_overshoot_ticks: float = 2.0      # A7 [our interpretation]: open_space may overshoot the level by this many ticks (no body close through)
    ir_body_mult: float = 1.5            # A7 [our interpretation]: zero_width needs c2's body >= this x the mean body of the last 20 bars
    # A12-open-vs-wick-gap-criterion / A5-twice-traded-not-fvg (cc05_015 ~11:32 / ~11:38; cc04_013 ~16:17)
    ob_anchor_rule: str = "wick_len"     # A12: "wick_len" (the stubby / long wick rule) / "gap_presence" (a wick area traded through twice - no FVG - anchors on the open; an untraded gap keeps the wick extreme)
    ob_anchor_passes: int = 2            # A12 [our interpretation]: the "twice" count - the block's own candle plus this many minus one other bars overlapping the wick area
    # A12-tf-relative-ob (079 ~15:06)
    htf_ob_ltf_drill: bool = False       # A12: a wrong-coloured HTF swing-extreme candle takes its OB from the last opposite-colour 1h bar inside it
    # A6-breakaway-depth-qualification (062 ~37:12 / ~39:01; 065 ~4:39:02; 075 ~1:39:36; 084 ~29:16; cc04_009 ~13:37)
    bk_depth: str = "ce"                 # A6: how deep a retrace may go and still be a breakaway gap - "ce" (A6: at most 50%) / "any_open" (062, cc04_009: any portion left open)
    bk_state: bool = False               # A6: the candidate -> retraced -> QUALIFIED state machine; the breakaway trail (trail_breakaway / ladder_trail "breakaway") and the entry tag use only qualified gaps
    bk_bpr_ce: bool = False              # A6 (065): a BPR directly beyond the gap's far edge limits the retrace to the near side of the CE even under any_open
    # A9-vi-breakaway (079 ~14:20; 103 ~25:18)
    vi_breakaway: bool = False           # A9: a VI on the candles leaving a consolidation / right after the MSS / inside the displacement leg beyond the retrace limit is a breakaway VI - not an entry zone
    # A6-gap-hierarchy-common (062 ~39:41 / ~43:58; cc04_010 ~12:25)
    gap_classes: bool = False            # A6: tag the entry gap breakaway / measuring / common (gap_<class>) and the CC body gaps (cc_common)
    trail_skip_common: bool = False      # A6 [our interpretation, extrapolated]: never trail behind a COMMON gap (only breakaway / measuring gaps are trail references)
    # new-single-candle-daily-inefficiency (091 ~25:37)
    single_pass_draw: bool = False       # a large daily candle no other candle traded through is a draw: its CE, then the lower quadrant, until price trades back down through it
    # A5-vi-extended-ce (098 ~1:09:26 / ~1:09:42)
    fvg_vi_extend_ce: bool = True        # A5: with fvg_vi_extend the CE is the midpoint of the EXTENDED zone and a wick-linked VI extends it too (a fix, not a behaviour switch)
    # A11-balanced-range-body-filled (098 ~34:57 / ~1:00:35; 099 ~11:14)
    balanced_range: bool = False         # A11: a body-filled balanced range (>= 3 overlapping candles, both ways, left by displacement) has an EQ; the target ladder does not reach past its EQ
    # M1-original-consolidation (104 ~27:53)
    orig_consol: bool = False            # M1: mmxm_ctx draws to the smooth-edge level of the original consolidation (not the parent swing high)
    orig_consol_touches: int = 3         # M1 [our interpretation]: >= this many body tops / highs within the tolerance
    orig_consol_tol_pts: float = 0.5     # M1 [our interpretation]: ES points
    # A21-consolidation-range-def (cc01_001 ~11:50 / ~17:54)
    consol_body_range: bool = False      # A21 (review fix #127: opt-in, N8 consol_pools keeps the built wick range): a consolidation's high / low are its max / min BODY (impulse legs keep the wick rule); acts on the N8 consol_pools range and the daily consolidation EQs
    consol_eq_touches: int = 2           # A21 [our interpretation]: the EQ is touched from each side at least this many times (0: no check)
    # A3-clean-high (cc01_003 ~15:33)
    eq_min_sep_bars: int = 0             # A3: relative equal highs / lows need their swings at least this many bars apart (0 = the old rule; test 3)
    # A12-void-up-down-ob (cc02_007 ~13:33)
    void_rt_ob: bool = False             # A12: on 4h and higher, a one-sided rally then a one-sided drop through the same range = one bearish OB (MT 50%); bullish mirror
    # A15-stoprun-variant (cc03_002 ~19:11)
    mit_def: str = "a15"                 # A15: "a15" (failure swing, cc04_004) / "stoprun" (the up-close candle before a down leg that ran a low's stops: its upper wick is the block)
    # M4-failure-swing-no-new-extreme (cc05_005 ~19:40)
    fs_def: str = "m4"                   # M4: "m4" (the higher low B fails to reach the key level) / "no_new_extreme" (the earlier swing reached it; B simply makes no new extreme)
    # B21-data-range-fv-eq (cc05_003 ~1:18:00)
    ipda_fv: bool = False                # B21: the daily gaps (FVGs) inside the 20 / 40 / 60-day windows are array targets
    ipda_consol_eq: bool = False         # B21: the EQ of each daily consolidation inside the windows is a target level, and ipda_eq_day tests price against those EQs (no news driver)

    # --- caption-gap pass, levels_detectors #3/3 (digests/rulebook_gaps/*.md; every switch cites its gap id + source video/time) ---
    # L5-rth-and-eth-gap-views (019 ~4:31)
    gap_views: str = "auto"              # L5: "auto" = the ETH-bar gaps only (as built) / "both" = also the RTH view of the weekend gap (kind nwog_rth: Friday's last RTH close -> the Monday 09:30 open), no de-duplication
    # L5-holiday-nwog (046 ~16:34 / ~20:47)
    nwog_holiday_pick: str = "all"       # L5: with nwog_skip_holiday, "closest" = when this week's NWOG is dropped as a holiday week only the one normal NWOG (within nwog_days) closest to the day's open stays (none if there is none)
    tue_open_ref: bool = False           # L5/B13: a week whose Monday is a holiday takes TUESDAY 09:30 as its opening reference for the weekly_open filter (index; the Tuesday open is used from the 09:30 bar on)
    # L7-org-lifetime-sr (068 ~9:51; 072 ~23:03; 092 ~1:59:32)
    org_both_ways: bool = False          # L7: each ORG tracks up_done / dn_done and the furthest point reached inside it; it leaves the lists once both directions are done (or org_days - up to 60 - pass); the pending targets are [partial-delivery extreme, far edge]
    # L10-older-daily-weekly-wick-ce (010 ~1:45; 015 ~31:48; 011 ~5:22; 093 ~6:48)
    wick_untraded: bool = False          # L10: a daily (weekly) wick CE of the last wick_days days (wick_weeks weeks) is kept only while no later daily bar traded through it by a tick
    wick_weeks: int = 1                  # L10: how many prior weeks' wick CEs (> 1 turns the weekly list on; "several weeks old", 011)
    wick_lod_tag: str = "off"            # L10: "tag" / "require" - a sweep within 2 ticks of an untraded lower-wick CE that sits within 1 pt of a 5m / 15m discount array is the expected low of day (lv_tag wick_lod; "require": longs need it)
    # new-reactionary-high-liquidity (046 ~56:01; 099 ~51:16)
    reactionary_pools: bool = False      # the latest untaken pivot high that launched a displacement leg lower (shorts' trailed stops) is a buy-side pool (tag reactionary) and the retracement draw; sell-side mirror
    # new-parent-pool-bodies-short (050 ~56:39)
    parent_pools: bool = False           # an earlier swing low with >= parent_n later lows in its area whose bodies all stop short of it is the parent pool (the target; the later lows are rungs only); mirror for highs
    parent_n: int = 2                    # [our interpretation] n >= 2 later lows ("same area" = within 0.25 x ADR5 above L0)
    # L1-prior-day-london-pm-pools (072 ~27:52)
    prev_london_pool: bool = False       # L1: the previous day's London 02:00-05:00 high / low are pools, like today's London and the previous PM range
    # new-lookback-per-tf-topdown (cc01_003 ~13:38 / ~18:23)
    tf_lookback: dict = field(default_factory=dict)   # {"D": 252, "4h": 63, "1h": 15, "15m": 4} trading days: the HTF array lives (htf.table lookback, Confluence) and the daily pivot history are cut to these windows when set
    # L3-monthly-ohlc-3m (cc03_004 ~1:46)
    monthly_ohlc: bool = False           # L3: O / H / L / C of the last 3 completed monthly candles (12 levels) as reference levels - lv_tag m_ohlc on an entry / target within 1 pt; not standalone pools
    # L3-3-6-12-month-pools (cc05_002 ~2:41)
    ipda_windows: tuple = (20, 40, 60)   # L3/B21: the data-range windows in sessions - any of (20, 40, 60, 63, 126, 252): the 3 / 6 / 12-month highs and lows
    # new-trendline-trap-target (cc03_007 ~11:26)
    trendline_pools: bool = False        # the second touch H2 of a three-touch retail trendline is a buy-side pool (tag tl2) for a long whose entry low lies between H2 and H3; T1 = H2 + 1 tick
    # B21-reference-points-in-windows (cc05_001 ~24:28)
    ipda_rb: bool = False                # B21: when the window extreme's wick is longer than its body the pool is the candle's BODY edge (A17 rejection block) and the wick extreme a runner rung
    ipda_arrays: bool = False            # B21: the daily HTF array targets are limited to arrays formed inside the 60-day IPDA window (ending at the anchor)
    # B21-progression-20-40-60-beyond (cc05_004 ~26:38; cc06_008 ~12:50; cc07_004 ~7:43; cc05_003 ~28:40)
    ipda_roll_arrays: bool = False       # B21 (with ipda_next): the draw also rolls from the 20-day to the 40-day window when every daily array of the 20-day window has been traded to
    ipda_beyond_days: int = 0            # B21: 0 = off; N > 0: once all three extremes are taken the nearest older daily swing (within N sessions, e.g. 120) is the draw, tag expansion
    # B21-open-float-forward-windows (cc05_004 ~25:15; cc05_003 ~2:02:01)
    ipda_forward: bool = False           # B21: with an anchored ipda_anchor ("month" / "current_month" / "swing"): the completed forward 20-day intervals of the anchor and the realised D-60..D+59 float are pools; pools hit by >= 2 windows are the preferred draw
    # B21-anchor-month-vs-daily (cc05_004 ~16:04): ipda_anchor accepts "daily" (= "rolling") and "current_month" (the windows end on the first trading day of the CURRENT month, fixed all month)
    # LLT3-london-extreme-preny-range (cc08_007 ~2:37)
    london_lr_zone: str = "off"          # L1: "tag" / "require" - yesterday's London extreme -> the opposite extreme before 09:30 is a range; a short today sells its premium half (lv_tag in_lr); "require" rejects the others on days with that bias
    # LLT3-0800-0900-pool-stock-open (cc10_006 ~4:06)
    or0809_pool: bool = False            # L1: the 08:00-09:00 high / low (or0809_pool) as session-opening-range pools (adds (480, 60) to session_ors)
    # A17-rejection-block-short-protocol (035 ~23:08)
    rb_pools: bool = False               # A17: the close of an old daily swing high (low) candle is a pool; the MSS after its sweep uses a wick pierce; against the bias it is only a target rung
    # A12-entry-ob-outside-fvg (065 ~4:04:05)
    ob_outside_fvg: bool = False         # A12: the entry order block is the last down-close candle OUTSIDE the FVG (candles inside the shaded zone are ignored)
    # new-trendline-trap (cc03_007 ~8:18 / ~10:46)
    trendline_trap: bool = False         # the low between H2 and H3 of a three-touch retail trendline is a priority sweep pool (turtle-soup within ts_max_pts) when the HTF bias is with the trade
    tl_tol_ticks: int = 4                # [our interpretation] touch tolerance of the line, in ticks
    # new-hs-fade (cc03_008 ~6:30 / ~7:11)
    hs_fade: bool = False                # head and shoulders on hs_tf bars against a same-side HTF array: a resting limit at / just below the neckline lows, partial at the right shoulder, objective above the head
    hs_tf: int = 60                      # [our interpretation] minutes of the H&S bars (index: 15 - 60)
    hs_stop_pts: float = 0.0             # a wide fixed stop (ES points) for the H&S fade (0 = the ts_max_pts stop)
    # new-intra-week-extreme-raid (cc09_005 ~4:07 / ~6:08)
    week_pools: bool = False             # the intra-week high / low so far (prior sessions of the week) are pools week_hi / week_lo; a sweep of one needs a same-side HTF array
    week_raid_days: tuple = (1, 2, 3)    # weekdays (Mon = 0) of a raid of the week HIGH (Tue-Thu); the week LOW also on Monday
    # T4-or-length (073 ~25:03; cc10_010 ~11:09): or_minutes accepts 20 (OR20 = 09:30-09:50, usable from 09:50; ctx.or20 is always built)
    # L3-or-refs-expire-1100 (090 ~49:21)
    or_expire: int = 0                   # L3/P2: the opening range stops being a pool / target at this minute (660 = 11:00); 0 = never
    or_fvg_entries: bool = False         # L3: the FVGs formed inside the opening range are entry arrays for setups armed 10:00-11:00
    # new-time-distortion (060 ~24:12; 100 ~42:21; 075 ~1:40:05)
    time_distortion: bool = False        # swings / MSS / FVGs formed in the 15 min before a release, after 16:00 and (td_lunch) in the lunch chop 12:10-14:00 are no signals
    td_lunch: bool = True                # [with time_distortion] the chop between the lunch macro and 14:00 counts
    td_fvg_hold: bool = False            # bodies holding inside an FVG for 5+ bars in 10:00-12:00 (wicks may poke out) keep it valid

    # --- caption-gap pass, levels_detectors #3/3 REVIEW FIXES (the switches the review added; every one defaults off / to the built behaviour) ---
    # L2-sr-needs-fvg (058 ~13:34; 076 ~21:21) - with daily_level_needs_array="fvg"
    flip_retest_entry: bool = False      # L2: a broken old swing level with an FVG of the breaking leg within a tick of it is a flip-retest entry: a resting limit at that FVG's CE (needs the bias for the side)
    # new-trendline-trap (cc03_007 ~8:18 / ~10:46)
    tl_trap_entries: tuple = ()          # with trendline_trap: "ob" / "breaker" - a resting limit at the bullish OB / LTF breaker at L23 (price dips into the old low, no sweep needed); ladder H2 + 1 tick, then the daily draw
    tl_tol_adr: float = 0.0              # [our interpretation, OWNER QUESTION 15] 0 = the trap's touch tolerance is tl_tol_ticks; > 0 = this fraction of ADR5 (trendline_pools always uses 0.1 x ADR5)
    # new-hs-fade (cc03_008 ~7:11)
    hs_rearm: bool = False               # "Re-sell if price runs the level again": after a run of the neckline lows and a close back above, the fade is armed again (once per run)
    # L3-htf-pd-arrays-intraday (cc05_015 ~19:55)
    htf_monthly_arrays: bool = False     # L3: htf.table also builds the monthly FVG / OB arrays (react weight 3) next to the daily and weekly ones
    # new-lookback-per-tf-topdown (cc01_003 ~13:38 / ~18:23)
    tf_pools: bool = False               # with tf_lookback keys "15m" / "1h" / "4h": the untaken swing highs / lows of those bars inside their window (older than the prior session) are pools tagged tf_<label>; pool_rank ranks them by timeframe
    # B21-reference-points-in-windows (cc05_001 ~24:28)
    ipda_window_arrays: bool = False     # B21: the daily OBs and liquidity voids formed inside the 60-session IPDA window are array targets too (next to ipda_fv's FVGs)
    ipda_frame: bool = False             # B21: "frame off the window low when the market has been trading higher, off the window high when lower": tags frame_low / frame_high, ipda_disc / ipda_prem for the entry in that range
    # B21-progression-20-40-60-beyond (cc05_004 ~26:38)
    ipda_converge: bool = False          # B21: the window extreme that coincides with a daily PD array (within 0.25 x ADR5) is preferred as the draw (tag ipda_converge)
    # B21-open-float-forward-windows (cc05_003 ~28:40; cc05_004 ~25:15)
    ipda_recompute: bool = False         # B21 (with ipda_forward): the 20/40/60 look-backs recomputed ending at each forward marker D+20 / D+40 / D+60 reached are pools too (ipda_m<j>w<n>); the back windows then end BEFORE D
    # L3-monthly-ohlc-3m (cc03_004 ~2:30)
    monthly_frame: bool = False          # L3: the monthly range framed from the most recent down-close monthly candle's low to the high of the up-close candle above its high - tags m_frame_disc / m_frame_prem; monthly levels also count as converging arrays (converge_rank)
    # LLT3-london-extreme-preny-range (cc08_007 ~2:37)
    ny_hl_frame: bool = False            # L1: the prior NY session (09:30-16:00) high / low frame - a retracement inside it frames the next higher low / lower high (tag in_ny_range)
    # L5-holiday-nwog (046 ~20:47-21:11)
    tue_open_time: str = "0930"          # L5: the Tuesday opening reference of tue_open_ref - "0930" (indices) / "midnight" (FX)
    # L7-org-lifetime-sr (092 ~1:59:32)
    org_revisit_gate: bool = False       # L7 (with org_both_ways): today's revisit of an ORG high / 75% / CE counts only inside 10:00-11:00, 14:00-15:00, 15:00-16:00 with another PD array within 1 pt (NWOGs exempt)
    # new-reactionary-high-liquidity (046 ~56:01)
    reactionary_precond: bool = False    # the reactionary high is the draw only after a deep-discount move (>= 0.5 x ADR5 below it) with no FVG between price and it on the 15m bars [our interpretation]

    # --- caption-gap pass, setups_models #1/7 (every switch defaults off / to the built behaviour; the gap id is the comment's first word) ---
    # BH-B12-midnight-open-tolerance (006 ~25:38; 010 ~38:48, ~47:02; 048 ~1:00:57)
    open_tol_pts: float = 0.0            # B12: ES pts the entry may sit on the WRONG side of the reference open when the open was already traded through in the Judas direction, the entry is at an FVG/OB and an MSS followed that move (0 = strict, as built); Trade.open_grade "best" / "allowed" (test 2.0 / 3.0)
    wk_open_side: bool = False           # B13: tag Trade.wk_open_side = sign(entry - the week's Sunday 18:00 open) (a preference for >2-week trades, never a filter)
    # BH-B12-po3-sequence (006 ~6:33)
    po3_seq: str = "off"                 # B12: "tag" / "filter" - the preferred order: a trade beyond the reference open (the Judas), a close back across it, THEN the MSS + entry at / near the open
    po3_seq_below_pts: float = 3.0       # [our interpretation] "just below it" = this many ES pts
    # BH-A8-opposing-FVG-inversion-confirms (015 ~26:19; 061 ~46:50, ~2:33:50)
    ifvg_narrative: str = "off"          # A8: "block" - against a bullish unmet draw an entry inside an FVG that was closed through the draw's way is no trade; "require" - a with-bias entry needs the opposing FVG closed through, retested and held before the MSS
    # BH-B12-gap-up-short-below-0930 (044 ~34:06)
    gap_premium_arm: bool = False        # B12 / L7: gap up into an HTF premium array (down into discount): no longs, shorts only after a trade below the 09:30 open
    # BH-compressed-higher-highs (028 ~1:26:02)
    compressed_hh: bool = False          # a run of compressed marginal higher highs into premium is buy-side engineering: no long off them, the short after the MSS below is tagged and its first target is the leg low
    compressed_k: float = 0.1            # [our interpretation] each high exceeds the previous by < k x ADR5
    compressed_n: int = 3                # ... for n consecutive pivot highs
    # BH-D15-sick-sister-laggard / middle-index / clean-swing-point / short-index-by-premium-depth, D15-which-index-contradiction (smt_pick values)
    laggard_consol_only: bool = False    # D15 smt_pick "laggard_objective": only on consolidation days (the 053 statement); False = every day
    # BH-M3-scan-all-indices (067 ~1:33:29)
    markets: tuple = ("ES",)             # M3: the markets scanned in the study (("ES", "NQ") = scan both through the same combine; no engine effect)
    # BH-three-pool-runs-exhaustion (048 ~1:13:41)
    pool_runs_max: int = 0               # once the leg took this many successive pools in the order's direction no continuation order is taken (0 = off; test 3)
    # BH-premium-FVG-CE-vs-far-edge-trap (062 ~15:56)
    far_edge_trap: bool = False          # A5: a retrace that reaches the HTF FVG's far edge (top - 10% of its height) is a trap: no trade; held at / below the CE = tag ce_hold
    # B18-am-smt-window-points (086 ~5:42; cc10_011 ~12:50)
    smt_win_a: int = 300                 # B18.2: the SMT window (smt_pre) in minutes of the day, start (05:00) ...
    smt_win_b: int = 570                 # ... end (09:30); test 120 / 660
    smt_ref_window: bool = False         # B18.2 (086 ~5:42): the COMPARED extremes (the swept level's own low / high and the partner's twin) must have printed inside [smt_win_a, smt_win_b] (inclusive: an open at the edge is a point); acts without smt_windows
    smt_open_points: bool = False        # B18.2: the 08:30 and 09:30 opening prices are candidate reference points (pools open_0830 / open_0930)
    # NEW-low-of-day-zone-tag-first (093 ~8:46)
    lod_zone_first: bool = False         # M0 / B4: no longs until price trades down to the pre-market low-of-day zone (+ 2 ticks), then an SMT sweep is required
    # B18-smt-only-with-bias (099 ~56:49; cc04_001 ~13:14; cc10_011 ~11:35; cc10_002 ~7:14)
    smt_with_bias: bool = False          # B18: an SMT counts only on the bias side (the other side is the laggard, tag smt_laggard); no bias = an SMT-qualified order is rejected
    # B5-mature-trend-continuation (cc02_007 ~1:56)
    mature_flag_block: bool = False      # B5: no with-trend continuation after a mature trend (prior close in the extreme of the 20-day range) or inside an opposing daily array
    mature_pd: float = 0.62              # the premium / discount line of the 20-day range
    # X3-a15-mitblock-bear-context (cc04_004 ~6:44)
    mit_needs_bias: bool = False         # A15: a mitigation-block entry needs the bias its way and an untaken daily pool / array beyond; the target is that level
    mit_preopen: bool = False            # A15 (041 ~0:00): with mitigation_entry, the up-close candles of the 09:00-09:30 consolidation (<= 0.25 x ADR5 range) are one more bullish mitigation block (tag mit_preopen)
    # X3-graduated-pricing-second-touch (cc04_010 ~11:24)
    touch_tag: bool = False              # L: Trade.touch_n = the touches of the swept level (the sweep included) since it formed
    # B12-judas-depth-adr (cc08_003 ~12:59)
    judas_max_adr: float = 0.0           # B12: reject a Judas deeper than this x ADR5 (0 = off; test 0.4); Trade.judas_depth is tagged when set
    judas_depth_tag: bool = False        # B12-judas-depth-adr: tag Trade.judas_depth at every fill with an open (no gate; judas_max_adr gates)
    # T3-london-close-multiday-reversal (cc09_005 ~32:44)
    lc_tag: bool = False                 # T3: tag lc_reversal (a 10:00-12:00 fill whose sweep was at an HTF array against the morning)
    lc_reentry: bool = False             # T3: after a stopped-out lc_reversal one more try in the same direction when the new sweep runs beyond the first extreme at the same HTF array
    # B18-pm-smt-reference-points (cc10_014 ~2:18)
    smt_pm_points: bool = False          # B18.2: the PM SMT compares the lunch-hour (12:00-13:00) extreme with the first pivot formed after 13:00
    # N1-nfp-release-4h-fvg (105 ~5:54)
    nfp_release_fvg: bool = False        # N1 / D8 option B: NFP Friday with a 4h bias: a limit at the nearest 4h FVG in the discount, armed for the 08:30 release (experienced exception)
    nfp_release_fvg_min: int = 5         # [our interpretation] minutes after 08:30 during which a fill is accepted
    nfp_release_fvg_add: bool = True     # one small add at the FVG CE (never more than one unit)
    # N5-entry-at-release (040 ~1:28; 049 ~2:27)
    post_news_continuation: bool = False # N5 (a): after the 08:30 run-out in the daily bias direction, the first 1m OB retrace in that direction
    post_news_run_pts: float = 5.0       # [our interpretation] the run-out leg is at least this many ES pts
    release_ob_entry: bool = False       # N5 (b): 10:00 high-impact day, price at 10:00 inside a 5m OB in the bias direction: a market entry at the 10:00 open
    # T13-judas-news-driver (cc01_002 ~15:16)
    require_judas_news: bool = False     # T13: with require_judas only a Judas sweep within judas_news_min of a scheduled release counts
    judas_news_min: int = 30             # [our interpretation] the window around the release (minutes)
    judas_news_tag: bool = False         # T13: tag judas_news on a sweep inside that window
    # DS2-two-session-close-templates / am-move-pm-reversal-templates / consolidation-profiles (cc10_013)
    profile_two_session: bool = False    # T13: two-session close - PM entries only the bias way, off a lunch-low sweep or a tap of a discount FVG; valid until an opposing 4h/D/W array is reached
    pm_reversal_pool: str = "am_high"    # M6: "am_high" (as built) / "lunch_or_am" (a sweep of the lunch high - failure swing - also counts)
    pm_reversal_ltf_only: bool = False   # M6: the PM reversal only when the AM move started off an array of 60m or lower (a 4h+ origin blocks it)
    profile_consol_pm: bool = False      # T13: consolidation day (neutral bias, no release from 10:00): the PM sweeps the lunch extreme (an HTF AM extreme) or the AM extreme, then reverses
    two_session_am: bool = False         # T13 (cc10_013 ~1:33): the AM of a two-session close - with the bias up and no opposing 4h/D/W array reached since the day's low, AM orders are bias-direction longs at a same-side 1h+ array only (the mirror)
    two_session_catalyst: bool = False   # T13 (cc10_013 ~3:26): on a scheduled-release day the market may trend straight through lunch - profile_two_session then drops the lunch-sweep / discount trigger (tag two_session_catalyst)
    profile_consol_am: bool = False      # T13 (cc10_013 ~11:35-12:00): consolidation day AM (neutral bias, no release from 10:00) - orders at an array of their side or from the opening-range EQ's expansion side; London / day extremes as targets
    # A13-breaker-needs-rebalance-and-fvg / close-vs-wick / lifetime (cc04_005; 001; 035; 015; 043)
    breaker_needs_disp: bool = False     # A13: the break leg leaves an FVG within breaker_disp_bars bars of the break
    breaker_disp_bars: int = 3
    breaker_break_ref: str = "wick"      # A13: "body_high" - the breaker has "left" only once a close is above the breaker candle's BODY high
    breaker_by_close: bool = False       # A13: a body close beyond the swing marks the breaker (taken first); a wick-only break is an MSS without one (FVG entry)
    breaker_day_life: bool = False       # A13: a breaker stays eligible for retest entries to the end of the day (PM last hour included)
    breaker_keep_original: bool = False  # A13: a newer breaker formed on top of an alive one does not replace it
    breaker_accumulate: bool = False     # A13-breaker-lifetime (015 ~22:43): with breaker_day_life, one order may accumulate inside an alive breaker (a limit at its CE while a close sits in the zone) without waiting for a break and retest
    # A19-break-against-htf-stop-run (cc09_004 ~9:01; 102 ~39:11; cc02_008 ~0:58)
    mss_requires_htf_agreement: bool = False   # A19: an intraday MSS counts only with the HTF flow (the bias column); a counter-HTF break is a stop run
    stoprun_rearm: bool = False          # A19: a counter-HTF break arms the opposite side's sweep (the stops it ran)
    # A5-short-into-htf-sibi (035 ~1:05:16)
    htf_sibi_short_zone: bool = False    # A5: inside a daily SIBI (BISI) the entry must be between its low and CE (CE and top); once the CE has traded the zone is skipped
    htf_sibi_need_smt: bool = False      # A5: ... with SMT confirmation (ES/NQ SMT stands in for index vs DXY)
    # A15-mitigation-block-entry (033 ~1:04:05; cc04_004; 075)
    mitigation_entry: bool = False       # A15: True - a mitigation block is an entry (a limit in the block with the bias); the 075 reading (target only) is the default
    mit_entry_px: str = "near"           # ... "near" (the block edge price reaches first) / "mid" (its CE)

    # --- caption-gap pass, setups_models #2/7 (every switch defaults off / to the built behaviour unless its comment says otherwise; the gap id is the comment's first word) ---
    # A5-premium-half-daily-fvg (012 ~18:02)
    dfvg_half: str = "off"               # A5: inside a large unfilled daily BISI (SIBI) the sweep must sit at / above the CE (below it): "tag" (lv_tag dfvg_lower_half) / "skip" (no order); also tagged / skipped once a 15m / 1h body closed below the CE today
    dfvg_large_pts: float = 15.0         # [our interpretation of "large"] the daily gap's height in ES pts
    # L5-nwog-sr-levels (039 ~10:52; 024 ~18:37)
    nwog_sr_entries: bool = False        # L5: in a consolidation NWOG week (nwog_regime table column) a limit at the nearest stored NWOG level (high / CE / low) in the bias direction (tag nwog_sr)
    nwog_sr_stop_pts: float = 1.0        # ... the stop this many ES pts beyond the level
    # new-stop-run-overshoot-next-array (025 ~1:05:16; 038 ~46:12)
    ts_next_array: bool = False          # M12 / L5: the turtle-soup limit sits at the first array / gap level more than ts_min_beyond_pts beyond the swept pool (skipping a wick CE hugging it); stop 1 tick beyond that array's far edge
    ts_min_beyond_pts: float = 1.0       # [our interpretation] a level within this many ES pts of the pool is no stopping point
    # L5-quarter-level-no-imbalance (030 ~1:23:49)
    gap_quarter_retrace: bool = False    # L5: after a close beyond an NWOG edge, a retrace leg without an FVG / VI is entered at the NEAR QUARTER ((CE + edge) / 2); stop beyond the CE + 1 tick
    # L6-ndog-nwog-primary-entry (050 ~54:42)
    gap_edge_entry: bool = False         # L6: with the daily bias, the first return of price to the near edge of an active NWOG (NDOG) is an entry on its own (contradicts 052 / 051 "confluence only"); stop beyond the gap's far edge
    # L7-gap-up-premium-template (042 ~11:31, ~1:00:16)
    org_two_rally: bool = False          # L7 / B15: on a significant gap up (down) the short (long) waits for the two-rally template: first high, a dip to the 09:30 open, a second rally above the first high; T1 = open -/+ 5 pts, then the prior close
    org_sig_adr: float = 0.25            # [our interpretation] "significant" = the gap >= this x ADR5
    # A18-reclaimed-ob-codeable (006 ~49:57; cc04_007 ~4:07)
    reclaimed_def: str = "strict"        # A18: "strict" (cc04_007: the curve's down-close candles reclaimed after the low) / "loose" (006: an OB price leaves, re-trades and leaves again)
    # A19-mss-when-raid-missing (010 ~41:31)
    mss_ref_raid: bool = False           # A19: the MSS reference depends on the expected raid level R: taken -> the swing that started the leg into the raid; not taken -> the swing that launched the leg making the session extreme, displacement break only
    raid_level: str = "pdh"              # [our interpretation] R = the prior day's high (low) on the trade's side
    # A19-mss-no-rel-sweep-with-htf-draw (019 ~8:34; 044 ~42:55)
    mss_eq_wait_unless_draw: bool = False    # A19.2: mss_eq_wait is waived when the session draw is locked in the trade's direction (the REL need not be swept)
    # A19-reh-short-term-low-trap (029 ~48:29)
    reh_trap: bool = False               # A19: bias long, HTF objective untaken, the last two swing highs relatively equal (REH): a short on a break of the short-term low under them is bait - the short is rejected
    # N-micro-structure-regime (024 ~10:08)
    micro_regime: bool = False           # N: inside a small intraday consolidation (< micro_range_adr x ADR5 since 09:30, >= 2 alternating pivots, no displacement) the MSS reference is read on the 5m chart
    micro_range_adr: float = 0.25        # [our interpretation]
    # M12-second-takeout-turtle-soup (046 ~1:01:58)
    ts_skip_reswept: bool = True         # M12: a swept pool that was already swept earlier and followed by a rally is no turtle-soup setup (a shallow second break = a deeper retracement); only acts with turtle_soup on
    second_break_partial: bool = False   # M12 / ME: an open SHORT (long) takes a partial at a failed shallow second break of a low (high) already swept
    # A21-pre-trigger-dealing-range (048 ~1:20:40)
    breaker_range_hold: bool = False     # A21: after a breaker tap the order stays armed with no expiry until a body closes below the breaker's low
    # A8-ifvg-narrative-liquidity-run (078 ~51:00; 084 ~19:43)
    ifvg_need_run: bool = False          # A8: an IFVG entry needs the narrative - the HTF bias its way AND an old sell-side pool taken inside / just beyond the gap before its inversion
    ifvg_over_pool_pref: bool = False    # A8: prefer an IFVG whose range contains the taken pool (others are rejected when one exists)
    # A8-ifvg-stacked-tails-exclusion (090 ~21:24)
    ifvg_tails_block: bool = False       # A8: an IFVG with a cluster of long lower tails just below it is armed only after a low below the cluster
    tails_tol_ticks: int = 3             # [our interpretation] the tails' lows end within this many ticks of each other (cluster = 2+ candles)
    # A7-immediate-rebalance-gates (059 ~4:50; 060 ~7:29)
    ir_need_draw: bool = True            # A7: an immediate rebalance acts only when the draw / HTF bias was known beforehand and points its way (only the opt-in IR paths: ir_entries, sb_rebalance_ext)
    ir_need_window: bool = True          # A7: ... and only inside a volatility window ([our interpretation] the macro window + the am / pm sessions)
    # A12-range-internal-ignore (064 ~56:17; 066 ~32:01)
    range_lock: bool = False             # A12: the order armed after the MSS stays armed (no pending_minutes expiry) while no body closes below the OB MT / range low; new sweeps inside the range are ignored
    # A19-second-mss-no-new-low (069 ~14:41)
    mss_rearm_lower_high: bool = False   # A19: after a valid MSS the side stays armed while the retrace does not pierce the sweep extreme (lower high / higher low); a later displacement FVG arms an entry
    # A24-reaper-definition (076 ~21:44; 081 ~11:49)
    reaper_def: str = "fvg"              # A24.2: "fvg" (076: the discount-half FVG the leg cut through) / "ob_overlap" (081: the breaker zone coincides with an order block - enter the return)
    # A4-wick-poke-vi-invalidation (090 ~1:05:53)
    poke_high_cancel: bool = False       # A4: after a wick-only poke through an HTF array / level (no body close beyond) a trade beyond the poke extreme cancels the AM orders of that side (re-evaluated in the PM)
    # A8-ifvg-before-pool (102 ~1:08:45)
    ifvg_pool_intact: bool = False       # A8: an IFVG is armed only while the nearest swing extreme beyond it (the draw) has not been traded through
    # A8-ifvg-depth-tolerances (102 ~1:11:04, ~1:55:46): ifvg_depth (above) is False / True (the first build) / "w_cap" (cases a / b / c)
    # A2-delivery-vs-liquidity (104 ~11:24)
    mm_ssl_target: bool = False          # A2 / Ep05.8: with mmxm_ctx the MM model's target is the far end of the leg that engineered the pool (the origin of the decline into a long's sweep)
    # A4-ltf-body-qualification (104 ~21:53, ~34:55)
    htf_body_qual: bool = False          # A4: an HTF entry zone (htf_entry_arrays) pierced by wicks beyond the mohawk is still qualified while 15m and 5m bodies stay inside it
    # new-state-to-array-map / new-delivery-states-machine (cc01_001 ~2:33; cc01_002 ~12:42)
    state_tool_map: bool = False         # new: entry filter by delivery state - EXPANSION: order blocks; RETRACEMENT: FVG / void / VI; REVERSAL: sweeps (turtle soup); CONSOLIDATION: nothing
    state_machine: bool = False          # new-delivery-states-machine (helper of the DWC package, built here): no entry while the state is CONSOLIDATION
    consol_bars: int = 20                # ... the bars of the consolidation test
    consol_adr: float = 0.3              # ... a range under this x ADR5 is a consolidation [our interpretation]
    # A4-sweep-body-cluster (cc03_002 ~11:36; cc02_007 ~21:51)
    sweep_ref: str = "wick"              # A4: "wick" (as built) / "body" (the relative-equal-low pool is the cluster of 2+ candles whose BODIES end at about the same price; the sweep needs a low below the lowest body)
    daily_first_return: bool = False     # A4 / cc02_007: tag a sweep of a daily body-low cluster that is the first return to the zone in daily_first_days sessions (HTF accumulation)
    daily_first_days: int = 30           # [our interpretation] the 30-45 trading-day window
    # B18-smt-accum-distrib (cc03_005 ~10:20)
    ts_need_smt: bool = False            # B18 / M12: a turtle-soup setup needs the SMT at the swept level (the correlated asset refuses the break); the order is tagged smt
    # new-divergence-types (cc04_013 ~2:41)
    div_tag: bool = False                # new: tag the stochastic divergence type at the order (type1 classic / type2 hidden); confirmation only
    # A17-index-or-rejection-block (cc10_010 ~9:03)
    or_rb: bool = False                  # A17: the opening-range rejection block - a long off the lowest-close down candle of the 09:30-10:30 range, a short off its last up-close candle
    or_rb_from: int = 630                # ... armed from this minute of the day (10:30)
    or_rb_bear: str = "last"             # [our interpretation] the bearish block: "last" (cc10_010 NQ example: the last up-close candle) / "highest_close"
    # A22-htf-definition-nested-arrays (cc10_013 ~8:17; cc10_014 ~11:08)
    pm_rev_nested: bool = False          # A22 / M6: the PM reversal needs the AM extreme at a NESTED array (a 15m / 60m array overlapping a 4h / D array of the same polarity)
    # new-consolidation-exit-direction (cc09_004 ~5:07)
    consol_fade: bool = False            # new: a break out of a consolidation (delivery state CONSOLIDATION) against the bias that closes back inside is fought - an entry back toward the opposite extreme
    # A5/A10-style tag: new-price-engine-models (cc09_006 ~0:54) is a tag only (Trade.setup_model, always on)
    # new-intermediate-term-hl-fade (cc09_005 ~23:14)
    ts_itl_context: bool = False         # new: a turtle-soup fade of an intermediate-term pool (older than yesterday: pdl2 / pdl3 / week / month / IPDA) needs context: an HTF array tag or a range-bound day
    # B18-smt-three-point-swing (cc11_004 ~27:39)
    smt_mode: str = "pair"               # B18: "pair" (the partner did not take the swept level) / "three_point" (this index low - lower low - higher low against the partner's low - lower low - lower low)
    # setups_models #2/7 review fixes (the not-built remainders of the specs; all default off)
    bpr_left_far_edge: bool = False      # A11-bpr-levels-ce-rejection (062 ~3:47): once price has LEFT the BPR (a close beyond its near edge) the far edge, not the CE, is the invalidation of the CE entry
    ifvg_far_edge_tag: bool = False      # A8-ifvg-narrative-liquidity-run (078): tag an IFVG whose far edge H is unlikely to be reached - an FVG just beyond it is still open [our interpretation]
    breaker_range_trigger: bool = False  # A21-pre-trigger-dealing-range (048 ~1:20:40): the dealing range (swing high before the retrace .. the breaker-tap bar's low) + the MSS trigger (an up-close body above the bearish FVG in the upper half that takes the internal highs) arms the first bullish FVG; needs the breaker registry (breaker_day_life or this switch)
    daily_first_ltf: bool = False        # A4-sweep-body-cluster (cc02_007 ~21:51): at a daily first-return zone the LTF ignores the bearish continuation (the against-side is rejected) and buys only after the swing high is broken (an MSS-path order)

    # --- caption-gap pass, setups_models #3/7 (every switch defaults off / to the built behaviour; the gap id is the comment's first word) ---
    # A23-1h-wick-ce-sweep-depth (063 ~24:04)
    wick_sweep_depth: bool = False       # A23: a relative-equal-low sweep is valid only once its extreme reaches (within 2 ticks) the CE of the longest lower 1h wick of the last wick_depth_bars 1h bars under the pool; a 1h body close under that CE cancels it; stop under min(sweep extreme, CE)
    wick_depth_bars: int = 12            # ... the 1h bars looked back
    # new-shallow-rel-sweep-one-more-drive (060 ~59:18; conflicts with M3 / 057 ~4:18 - a 1-2 tick dip before the fill is fine there)
    shallow_sweep_wait: bool = False     # M3: a REL sweep that ran fewer than shallow_ticks ticks under the pool is an incomplete run - nothing is armed until a deeper low (one more drive)
    shallow_ticks: int = 4               # [our interpretation] shallow = fewer ticks than this
    # new-leg-grading-quadrants (061 ~2:07:40; 075 ~1:35:57; cc03_001 ~38:09)
    leg_grade_gate: str = "off"          # A21: grade the entry in the projected leg O -> D: "tag" (lv_tag grade_q1..q4) / "require" (longs only in [O, O + 0.5 (D - O)] + tolerance; a close under O cancels the pending order)
    leg_origin: str = "mss_low"          # ... O: "mss_low" (the sweep extreme that started the post-MSS run) / "session_low" (the day's low so far)
    leg_grade_tol: float = 0.05          # [our interpretation] tolerance as a fraction of the leg (D - O)
    # L7-org-later-day-entry-array (080 ~13:20; 092 ~1:59:32)
    org_entry_array: bool = False        # L7: the unfilled part of a prior day's ORG (its high, 75% and CE) is an entry-reaction level in the org_entry_windows when the bias agrees
    org_entry_confl: bool = True         # ... never alone (092): another entry array within org_confl_ticks (False = 080: the ORG level alone)
    org_confl_ticks: int = 4             # [our interpretation] "a few ticks"
    org_entry_windows: tuple = ((180, 240), (600, 660), (840, 900), (900, 960))      # 03-04, 10-11, 14-15, 15-16
    # new-eq-stop-hunt-entry (075 ~1:31:00)
    eq_hunt: str = "off"                 # new: a sweep of a short-term low within eq_hunt_band of the dealing-range EQ is a stop hunt - "tag" (lv_tag eq_hunt) / "prefer" (such sweeps win the sweep pick); the stop sits under the sweep extreme
    eq_hunt_band: float = 0.10           # [our interpretation] "at EQ" = within this fraction of the range around 50%
    # new-prev-day-range-eq-long (076 ~20:09)
    prev_eq_long: bool = False           # new: after an expansion day that took a key high, longs only at or below EQ(prior 00:00 open .. prior high); a Reaper under EQ moves the floor to its CE
    # new-retrace-to-recapitalized-ob (cc03_003 ~38:17)
    recap_ob_entry: bool = False         # new: with an untaken HTF high above and a pool above swept, the retrace buys the most recent reclaimed OB's open (target the HTF high); the opposite side is blocked while that objective stands (lv_tag unfulfilled)
    unfulfilled_nearest: bool = False    # new-retrace-to-recapitalized-ob: True = the opposite side is blocked only while the untaken HTF high is also NEARER than the order's own draw (the first build); default = blocked while the objective stands (spec)
    # M1-turning-level-types (cc04_007 ~1:04)
    mm_turn_types: tuple = ("ob", "fvg")  # M1 am_discount_array: what counts as the turning level under the sweep extreme - "ob" (5m OB), "fvg" (1m BISI), "old_high" (an old high as support), "old_low", "void"
    # L8-vacuum-block-trade / new-vb-post-fill-management (cc04_009 ~11:48, ~12:42, ~14:09)
    vb_trade: bool = False               # L8: a vacuum block (a gap between a close and the next open) that price has filled 100% is bought at the pre-gap close; T1 above the high formed at the gap opening; stall / back-below management
    vb_min_gap_pts: float = 1.0          # [our interpretation] the smallest gap that counts as a vacuum block
    vb_entry: str = "fill_limit"         # L8 / levels#123 vs management#85 (contested, owner question): "fill_limit" = a limit at the pre-gap close once the gap is filled (85); "close_above" = market on the close of the first bar that closes above the first post-gap up candle (123, cc04_009 ~12:42)
    vb_back_full: bool = False           # L8 levels#123: exit the WHOLE position on the first close back under the pre-gap close (default = 85: half there, all on a lower close)
    # L2-raid-level-rolls (cc04_011 ~13:57)
    raid_roll: bool = False              # L2 cc_limit: after the raid level (an old low) traded without a 15m MSS the level rolls to each new confirmed 15m pivot low under it; no entries above the current raid
    # B1-nearby-unrun-high-trap (cc04_013 ~6:11)
    near_pool_block: bool = False        # B1 / A2: no entry within near_pool_adr x ADR5 of an untaken pool on the far side of the move that the setup did not take (a short under an untaken high)
    near_pool_adr: float = 0.25          # [our interpretation] X
    # L13-weekly-high-london-swing (cc07_008 ~30:29)
    wk_high_proj: bool = False           # L13: Monday of a bearish (bullish) week - the London swing projected k times from its extreme; a level at a weekly array becomes a partial-size limit
    wk_proj_k: tuple = (1.27, 1.62)      # [our interpretation] the extension multiples tested
    wk_proj_size: float = 0.5            # ... the Monday partial position
    # M4-swept-low-age (cc05_005 ~13:24)
    ts_age_rank: str = "off"             # M4: the swept low may be of any age; "tag" (lv_tag ts_age_<sessions>) / "prefer" (a sweep of a low of at most 5 sessions wins the sweep pick)
    ts_linger_bars: int = 0              # M4: a turtle-soup sweep is cancelled when more than this many bars close under the swept level before the order (0 = off)
    # A3 / LLT3-equal-highs-fade-condition (cc09_005 ~20:04)
    reh_fade_gate: bool = False          # A3: a fade of relative equal highs (lows) needs either the HTF order flow with the trade and the sweep into a same-side HTF array, or a neutral market with an HTF array just beyond the pool; else the pool is a continuation target
    # LLT3-lunch-hl-raid-not-target (cc10_013 ~1:50)
    pm_lunch_raid: bool = False          # L3 / T13: in the PM the lunch extreme opposite the bias is the raid (sweep) pool, not a target (it leaves the target ladder of the counter side)
    # M11-immediate-rebalance-management (092 ~1:41:37; 100 ~1:36:14)
    ir_filters: bool = False             # M11: no immediate-rebalance entry on a Friday or while a 10:00 release is still ahead
    ir_accel_hold: bool = False          # M11: the first half exits just beyond the nearest pivot (the sell-side lows); the rest is held only if that bar's range is >= 1.5 x the median of the last 20
    # M14-tgif-draw-hit-first-sd-depth (070 ~50:36)
    tgif_need_draw: bool = False         # M14.2: the TGIF zone is valid only after Friday traded to the named weekly draw (the htf.table draw)
    tgif_sd_exit: bool = False           # M14 / L13: the final rung = the SD of the first breaker formed after the Friday extreme that lands inside an earlier opposing breaker / gap
    # M15-ma-deuce-ladder (091 ~23:31)
    ma_deuce_ladder: bool = False        # M15: md_ladder, and without a 1h BISI the daily BISI's far edge is the final rung (best case)
    # M16-sick-sister-exit-ladder (053 ~6:21)
    ss_ladder: bool = False              # M16: T1 = just above the nearer high (ss_t1_frac of the position), T2 = the midpoint of the nearer and farther highs; the farther high is no rung
    ss_t1_frac: float = 0.8              # [our interpretation] the share exited at T1
    # A15-mitigation-block-targets / body-hold (cc04_004 ~8:13, ~14:29)
    mb_targets: bool = False             # A15: mitigation-block targets - the post-break extreme (just beyond), then the nearest HTF level (the final rung)
    mb_done_at_htf: bool = False         # A15: the session is done after the final rung fills
    mb_body_exit: bool = False           # A15 [our interpretation]: a body close beyond the mitigation candle's body before T1 exits at the close (reason mb_body)
    # new-counter-bias-scalp-exit (013 ~15:07)
    counter_scalp: bool = False          # B3 (opt-in): a setup AGAINST the htf bias is allowed as a scalp - half risk, one exit at the nearest pool, flat when the midnight open trades in the trade's direction
    # M4-immediate-response-swept-extreme (cc05_005 ~14:40)
    sweep_max_linger: int = 0            # M4: a sweep is void when more than this many bars close beyond the swept level before the MSS (0 = off; test 2)
    fs_sweep_close: bool = False         # M4 / management#88 daily clause: the failure swing (fs_def "no_new_extreme") needs the bar of the sweep (swing low L1 under the key level) to close back above the level
    # X9-repeated-array-taps (048 ~32:51; 063 ~28:54)
    breaker_max_taps_for_entry: int = 0  # X9 / A13: at tap 2 of the entry breaker a 2-bar window must trade above the nearest opposing FVG without breaking the tap low; a 3rd tap marks it worn (0 = no gate)
    # M5-lasthour-draw-frozen-noon (001 ~28:39)
    lh_draw_freeze: bool = False         # M5: the last-hour draw is frozen at lh_freeze_t (the AM lock, else the noon mark-up); the LH slot trades only toward it and is done once it traded
    lh_freeze_t: int = 720               # 12:00
    # M1-three-entry-plans (003 ~1:28:27)
    mm_plan: str = ""                    # M1: "full" (OB before the break, MM draw, one exit) / "mss_scalp" (after the MSS, all out at the first relative equal highs) / "pyramid" (OB before the break, adds on each new imbalance, pool rungs)
    # M4-unicorn-sequence-preopen-breaker (007 ~15:27, ~11:34)
    unicorn_preopen: bool = False        # M4 / A14: after 09:30 the unicorn's breaker is the one formed before 09:30 (5m); sequence: a sweep at/after 09:30 under it, then back inside the breaker within unicorn_back_bars, then the FVG inside it
    unicorn_back_bars: int = 15          # [our interpretation] the re-entry timeout
    # M4-accumulate-in-breaker-needs-bias-draw (007 ~21:34)
    breaker_need_bias_draw: bool = False  # M4: an entry or add inside a breaker needs the session bias with it and a named draw beyond it
    # M1-sell-model-fail-to-reach-CE (007 ~20:36)
    ce_fail_entry: bool = False          # M1 / E2: after a second MSS the pullback candle into the last imbalance of the leg that fails to reach its CE and closes the trade's way is the entry (market at the close)
    # M1-inside-fvg-expansion-only (009 ~3:49)
    expansion_ce_entry: bool = False     # M1: a single-expansion day (the locked draw is one daily level within ADR5 of the open) enters at the FVG CE and takes expansion_bulk at the draw, the rest at the next level
    expansion_bulk: float = 0.65         # [our interpretation] "9 of 14"
    # M7-pm-1330-judas-full (010 ~57:47)
    pm_need_htf_target: bool = False     # M7: PM entries need an undelivered daily-level HTF target in the trade's direction
    pm_lunch_fvg_array: bool = False     # M7.3: a 5m FVG formed 12:00-13:30 (alive) is one more array pm_judas_array accepts
    # M1M2-htf-array-replaces-sweep (011 ~8:49; 082 ~4:45)
    allow_htf_array_premise: bool = False  # M1 / M2 / A19: price reaching a same-side 15m / 60m array (bodies hold) is a pseudo-sweep when no pool was taken
    premise_tfs: tuple = (15, 60)        # ... the array timeframes (minutes)
    # --- caption-gap pass, setups_models #4/7 (every switch defaults off / to the built behaviour; the gap id is the comment's first word) ---
    # new-falling-dagger-upper-half-buy (012 ~00:20:06; experienced-only, conflicts with E1 / M0)
    dagger_entry: bool = False           # new: bias + a bullish daily FVG price is trading back into, in its UPPER half: a pre-MSS buy limit into the falling move (stop under the daily CE); skipped once a lower-half 60m / 15m FVG was filled today
    dagger_level: str = "ce"             # ... the limit: "ce" (the daily FVG CE) / "ltf" (the highest 15m / 60m FVG low between the CE and the daily FVG top)
    # M12-0930-htf-fvg-stab-no-mss (015 ~00:16:57; 038 ~00:21:57)
    stab_tfs: tuple = (15, 60)           # M12 turtle_soup="htf_stab": the HTF FVG timeframes (minutes) a pool run may stab into with no MSS / SMT
    # B12-po3-low-after-0830-into-old-low (013 ~00:04:52)
    po3_ideal: str = "off"               # B12: the ideal PO3 low = at / after 08:30 under the midnight open, taking an old low under it - "tag" (lv_tag po3_ideal) / "require" (the others are dropped)
    # new-po3-midnight-open-resting-order (013 ~00:09:46)
    po3_resting: bool = False            # new: at 00:00, bias of the night before: a minimum-size limit just under (over) the midnight open, T1 = the day's high at the fill, T2 = the HTF objective, no management
    po3_rest_off_pts: float = 0.25       # ... ES pts under the midnight open
    po3_rest_mgmt: str = "none"          # ... "none" = no breakeven / trail (a day trade); "normal" = the usual management
    # M5-lasthour-first-unit-at-old-low (013 ~00:26:58)
    lh_old_low_entry: bool = False       # M5: the last hour's first unit = a limit at the nearest untaken old low (filled on a 1-tick print through, no MSS first); the first FVG of the rally arms the same-size second unit
    lh_add2_mult: float = 1.0            # ... the second unit's size as a multiple of the first
    lh_old_low_stop_pts: float = 3.0     # [our interpretation] the stop this many ES pts under the old low (ICT gives none)
    # M6-pm-continuation-long-at-old-high (015 ~00:31:57)
    pm_old_high_fvg: bool = False        # M6: PM, bias + HTF objective ahead, price just traded above an intraday old high: a buy limit at the top of the FVG spanning that high, single target = the HTF objective; the target fill arms the M6 reversal
    pm_old_high_bars: int = 6            # [our interpretation] "just traded above": within this many bars
    # M6-ifvg-must-stay-partly-open (015 ~00:33:56)
    pm_rev_partial: bool = False         # M6: the reversal's gap must stay partly open - a body close past its far edge cancels the pending order, a trade through it exits; the lunch relative equal pools join the ladder
    pm_rev_first_only: bool = True       # ... take the very first retrace only (the built once-per-IFVG rule)
    # new-pm-retracement-short-after-draw-delivered (019 ~00:20:53; 060 ~01:09:30)
    pm_after_draw: bool = False          # M7 / M3: after the session objective is delivered a flip-and-BPR or a displacement-SIBI entry the other way, 13:20-15:00
    pm_after_room_pts: float = 10.0      # ... at least this many ES pts to the next gap / void
    sb_counter_after_draw: bool = False  # M3: the Silver Bullet may take the opposite side 14:00-15:00 once the session draw is delivered (same room rule)
    # B5-multi-tf-fvg-scan (022 ~00:43:05)
    leg_tfs: tuple = ()                  # M2: with no 1m gap of the leg at / under the leg EQ, scan these timeframes (minutes) in this order, e.g. (5, 4, 3, 2)
    # M2-leg-eq-after-low-prints (022 ~00:47:17)
    m2_live_eq: bool = False             # M2 fvg_pick "2022": the leg EQ is recomputed on every new extreme of the leg; only gaps at / under the current EQ qualify, the sweep waits for one
    # M2-pyramid-runup-leg-eq (022 ~01:03:28)
    m2_anchor: str = "leg"               # M2 fvg_pick "2022": "leg" (the displacement leg EQ) / "runup" (the EQ of the run into the swept pool; a VI first, then the FVG)
    # M2-implied-range-eq-gate (025 ~00:46:41; 060 ~01:24:16)
    implied_range_gate: bool = False     # M2: the implied range H .. the session objective; H is valid only after price traded from premium into discount; entries and adds only above EQ (side space: under it)
    # M7-pm-short-after-lunch-run-of-am-stops (025 ~01:05:57)
    pm_am_stops: bool = False            # M7: the PM pool am_last_high (the last AM swing extreme before 12:00); a sweep of it enters at the FVG CE, ladder = the relative equal pools, then the AM session's far extreme
    # M5-lasthour-short-sequence (026 ~01:35:33; 047 ~00:09:56)
    lh_array_short: bool = False         # M5: the last-hour sequence array -> rejection -> early confirmation -> MSS -> the displacement VI / SIBI CE (both sides)
    lh_array_target: str = "ladder"      # M5 (review fix): "ladder" = the normal ladder / lock; "sd3" = the -`lh_array_sd_k` SD projection of the MSS leg (R's extreme .. the leg extreme) is the single target [026]
    lh_array_sd_k: float = 3.0
    lh_array_iofed: bool = False         # M5: an add of `lh_add2_mult` x the unit at the near edge of the NEXT same-side gap (the SIBI) the rally forms after the fill (the IOFED add)
    lh_array_need_draw: bool = False     # M5 step (1): the draw must be set this way (off: a neutral bias may trade it too)
    # B16-nwog-gapup-return-then-mss (028 ~01:22:36)
    nwog_fill_long: bool = False         # B16: in a gap-up week a long needs price to have traded back to the NWOG low (Friday close) and the sweep within nwog_fill_tol_pts of it
    nwog_fill_tol_pts: float = 2.0
    # M11-wick-ce-fade-short (028 ~00:18:38; 042; 084) / new-sweep-wick-ce-failure-swing-long (038 ~00:50:59; 080)
    wick_ce_mode: str = "close"          # M11c: "close" (built) / "intrabar" (a limit one tick beyond the CE armed on the sweep candle, no confirmation) / "retrace" (the wick CE joins the no-FVG fallback arrays)
    wick_ce_pad_pts: float = 1.0         # ... intrabar: the stop this many ES pts beyond the CE
    wick_ce_tf: int = 0                  # M11c / A23: the sweep candle on this timeframe (5 / 15 / 60 min; 0 = the base bars) gives the CE - the order when a later bar retraces within a tick of it, the sweep low intact
    wick_ce_need_pool: bool = True       # ... the sweep must have taken a pool (a pre-marked array premise is no sweep)
    # M1-ob-entry-after-mss: entry_arrays "ob_post" (020 ~00:06:14)
    # M5-lasthour-shallowest-unused-array (030 ~00:21:36)
    entry_pick: str = "first"            # M0.5 / M5: "first" (the highest candidate, as built) / "shallowest_unused" (arrays price already traded back into are dropped first)
    # new-nwog-edge-to-ce-cookie-cutter (030 ~01:09:40; research tag)
    nwog_edge_ce: bool = False           # research: a sweep of an NWOG far edge targets that NWOG's CE - exit_before_pts (>= 5 pts of room, not on a choppy day)
    # M8-short-after-reprice-to-prior-close (030 ~01:47:48)
    org_fill_reverse: bool = False       # M8: the ORG's prior-close edge is a sweep pool (price repriced to it, then the MSS); target the session extreme, entries before 12:00
    # A12-entry-array-at-key-level (032 ~00:21:34)
    ob_at_key: str = "off"               # A12: the OB candle's extreme within ob_key_ticks of a key level (NWOG / NDOG edges + CE, ORG edges, session pools) - "tag" / "require"
    ob_key_ticks: int = 2
    # M4-breaker-needs-fvg-inside (032 ~00:42:02)
    breaker_low_invalidate: bool = False  # M4: a body close beyond the breaker candle's far extreme (not its MT) cancels a pending breaker / unicorn order and exits an open one
    # A13-breaker-inversion-against (033 ~00:49:43; 048 ~01:54:11)
    breaker_block_counter: bool = False  # A13: no counter-trend trade while the session's breaker holds; an inverted breaker blocks its own direction; the counter side needs a retrace into it and a close back through
    # M16-sick-sister-ob-open-entry (045 ~01:41:00) / M16-sick-sister-discount-confluence (053 ~00:05:17)
    sick_entry: str = "discount"         # M16.2: "discount" (built: the deep-discount gate) / "ob_open" (the forming down-close candle's open) / "ote_stack" (OTE band + OB + FVG overlap, consolidation only)
    sick_units: int = 1                  # ... ote_stack: up to this many resting limits over the overlap
    # new-lunch-macro-long-nwog (046 ~02:07:16; experimental, conflicts with T8)
    wick_ce_precursor: bool = True       # M11 intrabar (028 ~00:18:38): the wick candle follows a precursor that closed with the trade (short: a down-close; side space: an up-close)
    lunch_nwog_entry: str = "ce"         # T7 (review fix): "ce" = a limit at the NWOG CE; "ob" = at the body top of a down-close OB inside the zone (else the CE)
    lunch_nwog_long: bool = False        # T7: 11:40-12:10 inside [the NWOG low, the NWOG CE] after a down AM, nothing under the NWOG low: a limit at the CE (bypasses the lunch block)
    # A8-symmetry-skip-ifvg-confirmation (048 ~00:38:07)
    ifvg_symmetry_skip: bool = False     # A8: ES and NQ agree (the same higher high in the window): an opposing FVG is bought inside directly, the inversion steps are skipped
    ifvg_sym_bars: int = 30              # [our interpretation] the agreement window (bars)
    # A8-ifvg-5m-to-1m-handoff (048 ~00:21:30)
    ifvg_tf: int = 0                     # A8: 5 = the reference gaps are the 5m SIBIs; a 5m close above + a 5m retrace that holds, else the 1m close / new candle / hold sequence
    # new-short-top-of-htf-discount-fvg (050 ~00:51:08)
    htf_fvg_top_short: bool = False      # new: the top of a daily discount FVG already hit, a 5m bearish breaker there: sell it, target just beyond the nearest swing inside the FVG, out by 12:00
    # new-ndog-asian-scalp (052 ~00:08:18)
    ndog_scalp: bool = False             # new: Asian session (18:00-24:00) gap-down NDOG, price at / consolidating at its low: a long to the NDOG high
    asia_session: bool = False           # ... adds the 18:00-24:00 window to the day (backtest passes the evening bars)
    # M16-trending-divergence-continuation (053 ~00:08:20)
    smt_trend_ignore: bool = False       # M16 / B18: on a trending day an SMT against the trend blocks nothing and the sick sister needs no deep discount
    # M2-three-drives-conditions (056 ~00:08:47; 074; 076)
    three_drives_htf: bool = False       # M2: a three-drives reversal counts only with the HTF bias this way or the original-direction objective delivered; else a one-exit scalp
    # M4-complete-model-breaker-ote-ob (056 ~00:12:24)
    complete_model: str = "off"          # M4: a breaker entry from a parent swing, inside the leg's OTE band, with an opposite-colour candle inside - "tag" / "require"
    # M5-lasthour-reversal-into-org (059 ~00:24:09)
    lh_org_fill: bool = False            # M5: last hour with an unfilled ORG and the objective delivered: trade toward it, ladder [near edge, CE, prior close]
    # D15-one-clean-gap-instrument (061 ~01:49:01): smt_pick "clean" (SMT_PICKS)

    # --- caption-gap pass, setups_models #5/7 (every switch defaults off / to the built behaviour; the gap id is the comment's first word) ---
    # M10-ifvg-fvg-signature-full (061 ~02:18:22)
    ifvg_061_entry: str = "market"       # M10: "market" (built: the 061 market entry at the body close) / "iofed" (a limit at the lower FVG top + 1 tick, never deeper than its CE; a trade under the CE cancels / exits)
    # new-false-bull-flag-short (061 ~01:41:32; cc02_007 ~00:16:23)
    false_flag: str = "off"              # new: the swept pool is the low of a flag (a rapid drop, then a consolidation) lying under the day's / prior day's EQ or in a same-side HTF array: "tag" (lv_tag false_flag) / "require"; the first target rung = the flagpole origin
    flag_min_bars: int = 5               # ... the flag is at least this many bars
    flag_max_frac: float = 0.5           # ... and no wider than this fraction of the flagpole (origin .. flag low)
    # M9-news-judas-full-sequence (064 ~01:10:05)
    news_two_sided: bool = False         # M9: after both extremes of the post-release range are taken, trade the extreme taken second; arm only after a trade back to the range CE / the release open; exit on a body close under the OB MT
    # new-15m-candle-po3-upper-half (065 ~04:29:00)
    po3_15m: bool = False                # new: at a 15m open after `po3_15m_n` up-close 15m bars (bullish flow) with a BPR / FVG below: a buy limit at the 15m open - 1 tick, valid while price stays above 50% of the prior 15m bar, cut at the 15m close
    po3_15m_n: int = 3                   # [our interpretation] "bullish flow" = the last N closed 15m bars are up-close
    # M12-turtle-soup-prev-pm-low (067 ~00:20:12): turtle_soup "prev_pm" (a resting limit under the previous 13:30-16:00 low at 09:30, the weekly bias this way; target = that range's high)
    # M7-second-dip-into-rejection-block (067 ~01:05:38)
    rb_second_dip: bool = False          # M7: after the lunch low is swept (wick L, RB = the lowest close of that swing), a later dip under RB that holds above L buys the LTF array there; stop under L (the X8 / M1.3 body-low cancel does not apply)
    # M8-org-repricing-full-conditions (069 ~00:14:49)
    org_reprice_full: bool = False       # M8 (needs org_reprice): an order with the ORG-first ladder is REJECTED unless the Judas took the London + prior-NY pools beyond the midnight open, a premium array sits at the sweep, it is armed 10:00-11:00 and the ORG lies between the entry and the htf.table draw
    # M0-all-nearby-pools-run-first (069 ~00:16:49)
    all_pools_first: str = "off"         # M0: before a counter-Judas entry every listed pool of the Judas side within all_pools_pts of the open must be run - "tag" (lv_tag all_pools) / "require"
    all_pools_names: tuple = ("london", "prev_ny")   # ... london / prev_ny / lunch / prev_pm
    all_pools_pts: float = 30.0          # ... ES points from the session open
    # M7-lunch-reprice-org-ce-moc (069 ~00:20:38)
    lunch_org_ce_short: bool = False     # M7 research (conflicts with T8): 12:00-13:30, the AM draw undelivered: a limit at max(ORG CE, lunch REH + 1 tick), stop beyond the ORG far edge, held to the MOC / the lock
    # D15-dual-dealing (069 ~00:19:09): backtest.combine(dual_deal=...)
    dual_deal: str = ""                  # D15: "" (one instrument per session) / "split" (both same-session same-side trades at half risk each) / "full" (both at full risk)
    # M4-1m-last-upclose-finetune (070 ~00:55:41)
    breaker_tf: int = 0                  # M4: build the breaker zone on this many minute bars (5 = the 5m leg; 0 = the base bars)
    breaker_pref: str = ""               # M4: "last_1m" = inside the zone the entry block is the last up-close base bar before the run to the lower low, a limit at its MT (1 tick through)
    # M4-two-pool-breaker-near-miss (070 ~00:41:22)
    near_miss_pts: float = 0.0           # M4 (tag): a swing low within N ES pts above the swept pool after a bounce of at least that size before the sweep bar - lv_tag near_miss (0 = off)
    # M4-unfinished-high-keep-ab-leg (070 ~00:52:42)
    ab_anchor_lock: bool = False         # M4 advanced: the A-B leg of a filled advanced-breaker order stays the projection anchor while the locked target is untaken
    # M11-cisd-ob-stop-skip-rearm (075 ~01:19:43)
    cisd_need_htf: bool = False          # M11b: the CISD OB only when the sweep extreme sits in a same-side HTF array
    cisd_rearm: bool = False             # M11b: after a trade under the OB low the setup is void; re-arm only on a NEW CISD after it
    max_stop_pts: float = 0.0            # E5 (item 44, built here for M11b): a structural stop farther than this many ES pts drops the order but keeps the sweep alive (0 = off)
    # M10-ifvg-footholds-buy-program (075 ~01:29:33)
    ifvg_targets: bool = False           # M10: after the CISD the open bearish FVGs of the prior down leg are buy-side targets (near edge, CE)
    ifvg_need_hunt: bool = False         # M10: an IFVG entry arms only after a short-term low was run while no body closed under the IFVG CE
    # A4-bodies-hold-prev-day-50 (076 ~00:22:29)
    pd50_bodies: bool = False            # A4: for a sweep inside the previous day's range no body may close on the wrong side of the previous day's 50% between the sweep and the fill
    pd50_tf: int = 1                     # ... in minutes (1 = the base bars, 5 = the completed 5m bars)
    # new-overshoot-ltf-fvg-into-htf-level (078 ~01:22:24)
    htf_overshoot_short: bool = False    # new: a 60m FVG whose edge lies within overshoot_pts of an older daily FVG's edge: a limit one tick beyond it, the stop beyond the leg's swing (both sides)
    overshoot_pts: float = 3.0
    # new-open-returns-into-bearish-ob (081 ~00:11:34)
    open_ob_min: int = 0                 # new (tag open_into_ob): the entry OB formed before the 09:30 / 13:30 open and the fill comes within N minutes after it (0 = off)
    # B5-ltf-at-htf-array (082 ~00:06:22): entry_arrays "htf"
    htf_entry_array: str = "off"         # B5: the entry sits inside a same-side 15m / 60m array - "tag" / "require"
    # M2-htf-ob-precondition (087 ~00:05:51): premise_tfs may include 1440 (the daily arrays, OBs included)
    # M2-three-drives-breaker-fallback (093 ~00:11:14)
    td_same_level: bool = False          # M2: the three drives sit at the same level (all within td_level_pts of the swept level)
    td_level_pts: float = 2.0
    td_fallback: bool = False            # M2: the FVG order expired unfilled - the breaker of the three-drives top, where it overlaps an IFVG, arms a breaker order
    # A15-mitigation-block-entry (098 ~00:45:55): entry_arrays "mitigation"
    mit_entry_tf: str = ""               # A15: "D" = the mitigation blocks of the completed daily bars (traded today)
    # A15-stair-step-mitigation (cc04_004 ~00:11:52, ~00:13:57)
    mit_stair: bool = False              # A15: each newly broken swing arms a new mitigation block (the last candle at it): the first retrace is an entry, later blocks are adds
    mb_order: str = "limit"              # A15: "limit" (inside the block, near edge) / "stop" (a stop one tick beyond the block's far side from the retrace)
    # new-next-day-or-reh-short (099 ~00:52:08)
    prev_reh_plan: bool = False          # new: the prior day's 15m relative equal highs (lows) become AM pools when the prior day drove into the low end of an HTF FVG and the overnight held the prior low; target = the swing before the sweep
    # M2-skip-filter (100 ~01:07:20)
    stop_zone_pool: bool = False         # M2: drop the order when an unraided pool (or a level probed by >= 2 wicks with no body close beyond) lies between the entry and the stop
    # A14-unicorn-standalone (101 ~01:24:37)
    unicorn_standalone: bool = False     # A14: the unicorn (breaker + overlapping FVG after a retrace into a same-side array / NWOG quadrant) as a model of its own, any timeframe, one target, done
    unicorn_tf: int = 1                  # ... minutes (1, 5, 15, 60)
    # M13-max-depth-79 (102 ~01:00:33)
    max_retrace: float = 0.0             # M13 / M2: drop entry FVGs whose near edge lies deeper than this fraction of the leg (0.79 = the OTE upper bound; 0 = off)
    # M10-ifvg-open-dependent (102 ~02:21:33)
    ifvg_open_mode: bool = False         # M10: a resting limit at a daily IFVG only when the session opens away from it by more than ifvg_gap_pts; an unchanged open waits for the LTF path
    ifvg_gap_pts: float = 5.0
    # M0-htf-array-not-reached (103 ~00:29:15)
    array_fallback_breaker: bool = False  # M0: the planned 1h / 4h array was not reached - a 15m breaker above it and under the draw arms a breaker order
    # M1-original-consolidation-entry (104 ~00:32:10) / M1-consolidate-at-discount-array (~00:23:42) / M1-accumulation-stages (~00:36:46) / M1-distribution-stages-lowrisk-short (~00:45:30) / M1-one-segment (~00:09:27)
    mm_oc_entry: bool = False            # M1: after a body closed above the original consolidation's high, a limit at that high (first return only), stop under its midpoint
    mm_accum_bars: int = 0               # M1: MM longs arm only after N consecutive bars inside the discount array with a small total range (0 = off)
    mm_accum_frac: float = 1.0           # ... total range < this x the array height
    mm_stages: bool = False              # M1: stage entries / adds - the bullish breaker's order, then the CE of each later BISI (both sides); none once the lock is delivered
    mm_lowrisk: bool = False             # M1: the low-risk short at the CE of a 60m SIBI wicked through with bodies inside, armed after an LTF MSS; mm_oc_frac off at the original consolidation
    mm_oc_frac: float = 0.8
    mm_flip: bool = False                # M1: after an MM trade hit the lock the session may reverse into the MM leg of the other side - MM-kind orders only (sm5 kind "mm") (advanced, off)
    # setups_models #5/7 review fixes (chunk 5/7): the parts of the specs the first build left out, as switches (all off)
    mm_lowrisk_reentry: str = ""         # M1-distribution-stages-lowrisk-short (104 ~00:45:30): after the low-risk order's stop was run, ONE re-entry at the FVG's near edge; "extreme" = stop beyond the new extreme, "wick_ce" = beyond the wick candle's CE
    mm_stage2: bool = False              # M1-distribution-stages-lowrisk-short (104 ~00:49:45): stage-2 entry = the retrace into an OB's MT / the body of a reclaimed block; a stage-2 leg already traded is never chased
    mm_accum_gate: bool = False          # M1-consolidate-at-discount-array (104 ~00:23:42): the MM-model orders (original consolidation, stages) arm only after the mm_accum_bars accumulation test passed (a gate, not only the standalone order)
    unicorn_independent: bool = False    # A14-unicorn-standalone (101 ~01:24:37): owner choice - run the standalone unicorn under the pre-break ob_entry default too (the spec needs ob_entry "post_mss" / "both")
    # A18-curve-arrays-reverse-ladder (104 ~00:52:18; cc04_007 ~00:04:46)
    reclaimed_ladder: bool = False       # A18: every reclaimed block of the curve's left leg, lowest first, is the next entry / add (each once; a close back through a block cancels the rest)
    reclaim_bounce_bars: int = 2         # ... only blocks followed by a bounce of at least this many up-close bars

    # --- caption-gap pass, setups_models #6/7 (every switch defaults off / to the built behaviour; the gap id is the comment's first word) ---
    # M1-short-sell-side-of-buy-curve (cc04_007 ~00:01:21)
    curve_short: bool = False            # M1 / A18: with the draw up and an untouched HTF discount array below, a short against the bias is allowed, its single target = the array's near edge (mirror for a draw down)
    # A12-ob-at-consolidation-eq-and-eq-retest (cc01_001 ~00:11:11, ~00:18:01) / new-retrace-to-origin-ob (cc01_002 ~00:18:12); consol_bars (the bars of the consolidation, 20) is shared with the delivery state
    consol_eq_entry: bool = False        # A12: a body-defined consolidation (>= consol_bars bars, body range <= consol_max_pts) then a close outside it: a limit at the OB / the range EQ / the origin OB
    consol_max_pts: float = 8.0          # ... the widest body range that still counts as a consolidation (ES points)
    consol_eq_mode: str = "ob"           # "ob" (the last opposite-close candle, only within 25% of the range height of the EQ) / "eq" (the EQ) / "origin_ob" (new-retrace-to-origin-ob: that candle at any location; cancelled on a body close through its MT)
    # A10-void-retrace-trades (cc01_001 ~00:15:21; cc03_001 ~00:47:58) / new-post-void-fill-gap-sell (cc04_010 ~00:12:41)
    void_trades: tuple = ()              # A10: "fill" (an MSS against a void leg targets the void), "range" (a limit at the void CE of an up-leg, target = the leg extreme), "cont" (the fill then an MSS back the leg's way), "void_fill_gap" (a body gap of two same-direction bars right after the void was filled)
    void_idle_bars: int = 20             # ... "range": no pool may have been swept in the last this many bars (and none is armed) [review fix: the sweep lookback, not the leg's age]
    # M13-ote-needs-bias-trigger-structure (cc01_004 ~00:17:12; cc01_006 ~00:19:45)
    ote_need_trigger: bool = False       # M13: the 70.5% OTE limit arms only after an LTF MSS inside the band
    ote_parent_pd: bool = False          # M13: an entry in the OTE band of a small leg is dropped when it lies on the wrong side of the parent (day) range EQ (longs above it, shorts below it)
    # M13-premium-ote-turtle-soup (cc01_005 ~00:07:03)
    ts_ote_ok: bool = False              # M13 / M12: with ts_need_htf the swept level also qualifies at or beyond the EQ of the last impulse leg (the 62-79% band included); tag premium_ts
    # M13-bodies-stall-62-ob: ote "ob62" (cc01_005 ~00:13:59)
    # M12-quick-rejection-required (cc01_006 ~00:14:24; cc04_002 ~00:25:05)
    ts_cont: bool = False                # M12: a failed turtle soup (price ranges beyond the swept level >= ts_cont_bars bars, no close back) becomes a continuation entry in the run's direction
    ts_cont_bars: int = 10
    # M12-cc-daily-ob-turtle-soup / B5-topdown-entry-refinement (cc02_001 ~00:18:50; cc02_003 ~00:01:21; cc02_002 ~00:02:27)
    cc_ob_tf: int = 60                   # M12: the timeframe (60 / 15 / 5) of the down-close candle C in cc_1h_ob
    ts_r_preset: str = ""                # M12: "cc02_003" = half at 3R, then 9R / 15R, breakeven after 3R (the 5m refined switch B)
    refine_tfs: tuple = ()               # B5: e.g. (60, 15, 5): cc_1h_ob searches each timeframe from the lowest up for a validated down-close candle inside the daily OB and uses the lowest found; the stop stays below the sweep low
    cc_ob_validate: bool = True          # M12 (cc02_001, 123): the order arms only after a later bar traded above the 1h / 15m / 5m candle's high (default on = as built; off = arm at once) (advanced)
    cc_ob_offset_ticks: int = 0          # M12 (cc02_001): the spread - the cc_1h_ob limit this many ticks toward the market (the E3 entry_offset_ticks switch belongs to another package)
    # A12-secondary-ob (cc02_004 ~00:03:14): entry_arrays "ob_secondary"
    # M12-setup-selection-order (cc03_001 ~00:45:51)
    entry_discipline_only: bool = True   # M12-setup-selection-order (131): a discipline preset leaves ONLY that path (every other order kind - the FVG model after the MSS, the extra setups - is dropped); False = the preset only switches the named paths (as first built)
    entry_discipline: str = "any"        # M12: "turtle_soup" (cc_limit) / "ob_return" (the pre_break OB) / "range_void" (void_trades range) / "any" (as configured)
    # M12-contrarian-pmh (cc03_001 ~00:16:57)
    pmh_contrarian: bool = False         # M12 / M17: a sweep of the previous month's high / low arms the normal path against the bias; one exit at the nearest pool
    # B12-ob-below-midnight-open (cc03_003 ~00:33:28) / new-eq-wait-fresh-ob (~00:34:10)
    ob_below_open: bool = False          # B12: an OB entry needs the OB body at or below (shorts above) the midnight open
    eq_fresh_ob: bool = False            # new: an OB entry within eq_tol_pts of the day range EQ needs an OB formed after price first reached the EQ
    # M12-counter-run-in-confirmed-trend (cc03_005 ~00:03:27)
    sym_swing_ts: bool = False           # M12 / B18: a sweep that makes the day's extreme with both indices confirming (no SMT) is no reversal - the counter trade is dropped
    # E2-body-extreme-entry (cc03_008 ~00:15:43)
    ts_level_src: str = "wick"           # E2: "wick" / "body" - the level of the cc_limit / htf_stab / prev_pm turtle limit: the swing's wick extreme or its extreme body (open / close)
    # A13-breaker-reentries-and-wait (cc04_005 ~00:04:51, ~00:01:08)
    breaker_retests: int = 1             # A13: the number of retests of one breaker that may create orders (1 = the first return only, the built behaviour); a retest needs a departure of breaker_leave_pts
    breaker_leave_pts: float = 3.0
    # A17-rejection-block-entries (cc04_006 ~00:10:39, ~00:11:19)
    rb_entry: str = ""                   # A17: "limit" (at the trigger = the extreme open / close) / "stop" (a stop one tick beyond the trigger after a trade-through with no new wick extreme; cancelled on one)
    # A16-propulsion-entries (cc04_008 ~00:01:49, ~00:06:53): entry_arrays "propulsion"
    prop_second: bool = False            # A16: a propulsion block whose far extreme was already broken is entered again on the next return
    # L8-vacuum-block-entries (cc04_009 ~00:07:24, ~00:10:12, ~00:14:37): vb_entry "partial" / "full" / "auto"
    vb_react_bars: int = 3               # L8: partial fill - out when no bar closes above the fill within this many bars
    # new-last-buyside-offered-level (cc04_012 ~00:15:37): entry_arrays "last_offer"
    offer_run: int = 3
    offer_step_pts: float = 1.0
    # M4-two-chance-aggressive-vs-mss-retest (cc05_005 ~00:17:52, ~00:15:36) / M4-retest-nearer-ob-or-none (~00:16:56)
    two_chance: bool = False             # M4: a failed / missed turtle soup keeps the sweep alive for the MSS retest (ts_gate_mss does not drop it); after a turtle fill the breaking-point retest is an add
    cc_near_ob: bool = False             # M4: with cc_swings the retest order also covers the last opposite-close bar of the break leg (OCO: the nearer fills, the other is cancelled)
    # A15-mitigation-block-sell-entry (cc05_014 ~00:07:47)
    entry_arrays_order: tuple = ()       # A15: the order in which entry_arrays kinds are tried (e.g. ("mitigation", "breaker")); kinds not named come after, the highest entry first
    # new-clarity-filter-pass-if-arguing (cc06_002 ~00:09:20)
    clarity: str = "off"                 # new: "tag" / "drop" - an entry gap within 10% of its size threshold, or a path to T1 dominated by overlapping candles (ratio > clarity_overlap)
    clarity_overlap: float = 4.0
    # new-bullish-week-daily-routine-london-ny (cc08_001 ~00:42:40, ~00:44:50)
    ny_london_range: bool = False        # new: with the weekly bias this side, an AM entry after 08:20 must lie inside the London-low .. pre-08:20-high range, below its EQ
    # M0-judas-ends-in-15m-array (cc09_001 ~00:05:11)
    sweep_15m_array: str = "off"         # M0: "tag" / "require" - the sweep extreme lies in a same-side 15m array
    sweep_leave_bars: int = 0            # M0: the sweep is dropped when price stays within sweep_leave_pts of its extreme for more than N bars (0 = off)
    sweep_leave_pts: float = 2.0
    # new-consolidation-outer-edge-fade (cc09_004 ~00:12:08) / new-inside-range-expansion-fade (~00:15:37): named consol_edge_fade (consol_fade is the delivery-state fade of an earlier chunk)
    consol_edge_entry: str = "limit"     # 193 / 194 (review fix): "limit" = the sweep arms a resting limit just under the range low / the swing low near the EQ (mirrored for shorts); "market" = the first build's market order at the close back inside / the break bar's close
    consol_edge_fade: str = "off"        # new: "edge" (a sweep of a 1h / 15m range edge with the bias, target = the range EQ) / "inner" (a pivot just beyond the EQ is swept: target the far end) / "both"
    consol_tf: int = 60                  # ... the range's timeframe (minutes)
    consol_width_adr: float = 0.5        # ... the range is at most this x ADR5 wide
    consol_eq_band: float = 0.15         # ... "inner": the pivot lies within this fraction of the range height of the EQ
    # new-eight-reversal-catalogue / L2-pdh-pdl-fade-only-in-expansion-retrace / new-overlapping-reversal-score (cc09_005 ~00:00:29, ~00:15:56, ~00:20:57)
    reversal_tag: bool = False           # new: tag every swept-pool trade with its reversal type (pdh / pdl / week / iterm / ny_rev / lc_rev)
    reversal_need_htf: bool = False      # new: reversal types 3-8 need a same-side HTF array at the sweep
    reversal_score: bool = False         # new: tag the number of reversal types one sweep satisfies (report only)
    pdl_expansion: bool = False          # L2: PDL / PDH fades need the bias and the daily flow to agree and the prior 1-3 days to be counter-moves
    # --- caption-gap pass, setups_models #7/7 (every switch defaults off / to the built behaviour; the gap id is the comment's first word) ---
    # OT-D15-default-instrument (028 ~00:23:58) / OT-max-two-correlated-markets (055 ~00:27:38; 054 ~00:16:01): backtest.combine + the NQ overshoot
    combine_prefer: str = "none"         # D15 pref: "es" = on a same-bar tie keep the S&P row (ES / SPX / SPY) over the Nasdaq one (NQ / NDX / QQQ), ahead of the weak / relative-leg tie-break
    combine_exec_exclude: tuple = ("YM",)   # D15 pref: symbols never EXECUTED (YM, the Dow, is an SMT reference only): their rows are dropped before the pick (the bot never executed YM: trades unchanged)
    max_exec_markets: int = 2            # Ep05: at most two closely correlated execution markets (one S&P + one Nasdaq instrument); ValueError beyond; 0 = no cap
    nq_overshoot_mult: float = 1.0       # D15 pref: NQ / NDX / QQQ over-deliver past levels - sweep_ticks and mohawk_ticks x this on those runs (test 1.5 / 2.0)
    # T3-london-close-counter-trend-scalp (cc09_006 ~00:23:58) / new-london-close-scalp-large-range (cc09_005 ~00:12:05) / M17-london-close-asia-only-reversal-profile (cc09_006 ~00:29:41)
    lc_scalp: bool = False               # T3: the London-close counter-trend scalp (off)
    lc_mode: str = "failure_swing"       # "failure_swing" (cc09_006: a 5m high, a pullback, a lower / equal rally, sell the last up-close candle) / "mss" (cc09_005: the normal MSS + FVG against the day's move)
    lc_adr_mult: float = 1.0             # failure_swing: the day range (00:00 -> now) >= this x ADR5 (ICT prefers 1.25)
    lc_adr_k: float = 1.25               # mss: the day range >= this x ADR5 (1.25 - 1.33, an explosive one-sided move)
    lc_stop_pts: float = 2.0             # failure_swing: the stop = the day's extreme + this many ES points [our interpretation: the FX 10 pips scaled]
    lc_retrace: float = 0.25             # failure_swing: the target = the extreme - this x the day range (20 - 30 %, ~1R max)
    lc_retrace_mss: float = 0.2          # mss: the target = entry + this x the day range (20 % [our interpretation])
    london_close: tuple = (600, 720)     # mss: the window (10:00-12:00; variants (600, 660) and (630, 780))
    lc_fs_win: tuple = (630, 780)        # failure_swing: the window (10:30-13:00)
    lc_oneside: float = 0.15             # mss: "one-sided" = the day's open lies within this fraction of the day range of the opposite extreme [our interpretation]
    lc_rev_need_htf: bool = False        # M17: a 10:00-12:00 reversal (a sweep whose extreme falls in 600-720) needs a same-side, not-yet-met HTF array at the sweep
    # E5-missed-entry-5m-retrace (cc09_006 ~00:17:03; cc09_007 ~00:21:11)
    missed_5m: bool = False              # E5: the session's sweep / MSS fired, no order filled and price left: one more order on the first 5m same-side FVG / OB of the move
    missed_leave_pts: float = 5.0        # ... "left" = the close this far past the broken MSS reference
    missed_kz: tuple = ((500, 660),)     # E5 (review fix): the order only inside a kill zone - the NY one (the futures NY kill zone 08:20-11:00, as ny_kz_futures) [our interpretation]
    missed_lon: bool = False             # E5: ... plus the London lunch 05:00-07:00 when London was quiet early (02:00-03:30) and active late (03:30-05:00)
    missed_lon_ratio: float = 0.5        # ... quiet early = the first-half range <= this x the second-half range [our interpretation]
    # B12-dip-below-open-into-converging-15m-array (cc09_008 ~00:46:17)
    htf_converge: bool = False           # B12: tag htf_converge when the 15m array holding the sweep extreme overlaps a 60m / 4h / D same-side array
    # new-or-reference-arrays-reused (cc10_010 ~00:07:38) / new-am-trend-definition-and-start (cc10_011 ~00:01:08)
    or_ref_reuse: int = 2                # entry_arrays "or_ref": each OR60 reference array arms at most this many returns (until a body closes through it)
    or_ref_near_pts: float = 5.0         # ... a "return" = a bar's low within this many ES points of the array's body edge while the close is still above it
    am_array_open: bool = False          # 09:30-10:30: a first touch of a pre-09:30 same-side array (London FVG, the last opposite-close OB) in the bias direction arms a limit at its near edge, no MSS
    # T9-pm-reversal-turtle-soup-am-high (cc10_012 ~00:06:19)
    ts_sessions: tuple = ()              # M12: the turtle soup runs only in these sessions (e.g. ("PM",)); () = every session
    # T13-two-session-close-profile / T13-am-move-pm-reversal-htf-nesting / T13-consolidation-profiles (cc10_014 ~00:01:09 - ~00:17:47)
    two_session_smt: bool = False        # T13: an AM trade with an SMT tag that reached its target -> the PM takes the same side only, with SMT on the lunch-low vs post-13:00-low pair; held to the close (no 14:00 time exit)
    pm_nest_reversal: bool = False       # T13: a PM trade against the AM leg needs the PM sweep extreme inside an array of every timeframe in pm_nest_tfs; the target = the AM entry array when it is HTF, else the ladder extends past the AM extreme
    pm_nest_tfs: tuple = ("D", "4h", "1h")
    profile_consol: bool = False         # T13: AM and PM trades on opposite sides: the PM trade is out at 14:00 + consol_exit_min with a target at the 15m / 60m array; the PM pool follows the nesting test
    consol_exit_min: int = 15
    # M13-pattern1-full-sequence-ote-fvg (cc12_004 ~00:26:47) / M4-pattern3-breaker-half-size-add-ltf (cc12_004 ~00:36:02)
    ote_fvg_overlap: bool = False        # M13: with ote="limit" the 70.5 % limit stays only where it lies inside an FVG of the leg, else at the FVG edge nearest it inside the band; no overlapping FVG = no entry
    ote_need_s: bool = False             # M13: the leg needs a short-term low S (above the leg low) that was taken before the order
    ts_breaker_add_mult: float | None = None   # M4: the breaker add of a turtle-soup trade = this x the initial units (spec 0.5); None = the standard add fraction (adds), as before the pass
    ts_breaker_ltf: bool = False         # M4: the add limit is the 1m FVG / OB inside the breaker zone nearest its top
    # X14-reentry-after-winning-exit (049 ~00:02:38; 050 ~00:49:44) / X13-reentry-after-trail-stop-in-profit (085 ~00:27:16; 056; 022) / X13-reentry-after-loss-conditions (060; cc02_005; 104)
    reentry_after_win: bool = False      # X14: after a winning exit short of the draw (draw untouched) one more same-direction entry at a NEW PD array formed after the exit, same target, fresh size
    reentry_win_max: int = 1
    reentry_need_sister: bool = False    # ... the sister index must already have delivered the same draw kind (traded beyond its pre-entry extreme) [our interpretation]
    reentry_after_trail_win: bool = False   # X13c: a trailed stop hit in profit, target untouched, defended IFVG / breaker intact, not a high-resistance day: a limit at the IFVG CE / breaker retest
    trail_reentry_entry: str = "ifvg_ce"    # "ifvg_ce" (085) / "breaker" (022)
    trail_reentry_max: int = 2
    reentry_trigger: str = "new_array"   # X13b: the loss re-entry trigger - "new_array" (a PD array formed after the stop, limit only) / "sibi_return" (104: beyond the entry array's far edge, then the return)
    reentry_risk_mult: float = 0.5       # X13b: the re-entry risk (half per X13; 060 / 104 give no cut: test 1.0) - replaces the hard 0.5
    reentry_stop: str = "array"          # "array" (the order's own stop) / "wick_ce" (104: the CE of the new wick)
    reentry_idea_gate: bool = False      # X13b: replace the restored-sweep trigger with the three idea-intact conditions (draw untouched, no opposing MSS / close beyond the leg origin, a NEW array after the stop)
    # X13-reverse-after-failure-switch (045; 094; 102; cc04_008) / X14-opposite-second-trade-after-win (093; cc10_007)
    reverse_after_failure: str = "off"   # D18 B: "off" / "inversion" / "at_stop" / "prop_fail" / "sick_sister" / "all": at most one opposite trade per session
    reverse_risk_mult: float = 0.5
    offside_frac: float = 0.5            # at_stop: the open trade is offside by >= this x (entry -> stop) with bodies closing beyond the entry gap [our interpretation]
    allow_opposite_after_target: str = "off"   # X14: "lod" (093: a counter-bias short into a predefined low-of-day level, then a long) / "split" (cc10_007: a PM trade against the AM after a noon reversal) / "both"
    lod_conf_pts: float = 2.0
    # E12-070-rung-order (070 ~00:58:44) / X13-reentry-turtle-soup (cc01_005 ~00:12:36) / E6-breakaway-gap-stop (062 ~00:37:28) / M12-ts-stop-midpoint (022 ~02:48:40)
    adv_rungs: bool = False              # E12: the advanced breaker ladder - rung 1 the 5m FVG CE, rung 2 the IFVG CE, rung 3 the IFVG bottom (inside the A-B leg)
    adv_rung_fracs: tuple = (0.1, 0.3, 0.6)
    reentry_ts: bool = False             # X13: after a stop-out a same-direction re-entry only by a turtle soup of an old 3-bar swing extreme made inside the session range, with price on the right side of the range EQ
    reentry_max: int = 2
    reentry_mult: float = 0.5
    breakaway_reentry: bool = False      # E6: after two same-direction MSSs a retrace into the breakaway FVG arms a limit at its near edge, stop = the retrace bar's extreme + 1 tick (drops to the gap once price leaves)
    # T7-0950-reversal-or-continuation (043 ~00:05:31) / T7-1050-macro-setup (022 ~03:09:01) / T10-lasthour-ob-pullback / T7-lasthour-after-target / T10 range-day MOC / T7-lunch-macro-htf-program
    m0950_branch: str = "off"            # T7: "tag" / "rev" / "cont" / "both" - the 09:50-10:10 reversal / continuation branches (AM trades are tagged m0950_rev / m0950_cont / m0950_start)
    m1050: bool = False                  # T7: the 10:50-11:10 model - a short-term sweep, an MSS inside the window, the first VI / FVG of the break
    m1050_cut: bool = True               # ... the order is cancelled at 11:10
    protect_macro_ext: bool = False      # ... the macro extreme is a protected level: a later same-side stop sits just beyond it
    lh_ob_pullback: bool = False         # T10: the last hour (15:00-15:50) pullback into the last down-close OB before the PM high, bias this way, HTF draw not done
    lh_after_target: bool = False        # T7: the objective is done before noon, a PM MSS against the AM move formed, an opposite ORG / FVG unfilled: the last hour trades the reversal toward it
    moc_range_dir: bool = False          # T10: a range day tested one boundary 2+ times without a sustained break: only the other direction in 15:00-16:00
    moc_no_chase_hod: bool = False       # T10: a big bull day (range >= ADR5, close in the top quarter) whose HOD printed before 15:00 and which is not a trend day: no new longs from 15:00 (bear mirror)
    lunch_macro_entry: bool = False      # T8: the 11:50-12:30 lunch-macro entry - a retrace into a 5m / 15m same-side FVG against the AM move; the first rung only
    lunch_macro_win: tuple = (710, 750)
    lunch_first_rung_only: bool = True
    lunch_htf_program: bool = False      # T7: the lunch macro runs the buy-side (REH) above the late-AM pullback: with the HTF program that way the first rung = REH + exit_before_pts, the runner the HTF draw; against it no entry
    lunch_long_win: tuple = (710, 730)   # ... the program's long is armed inside the 11:50-12:10 macro only (times#12 'long setup in 710-730'); a later bar is x_lunch_program_window
    # new-ny-runs-london-extreme-news (065 ~03:07:01) / OT-M17-cc09_001-checklist (cc09_001 ~00:01:26) / OT-M17-cc09_003-ny-expansion (cc09_003 ~00:17:37) / OT-one-state-tool-pairing (cc01_001 ~00:19:34)
    london_ext_guard: bool = False       # T3: a no-news day whose London leg made the high and broke down: no AM long targeting above the London high, an AM short's stop never beyond it (mirror)
    cc09_gate: str = "off"               # M17: the cc09_001 day-trade checklist - "off" / "tag" (Trade.cc09 lists the failing names) / "gate" (reject when (1)-(4) or (6) fail)
    cc09_room_pts: float = 10.0          # ... (3) room to the opposing D / 4h array [our interpretation: ~50 EURUSD pips as a share of price, in ES points]
    cc09_scalp_pts: float = 7.0          # ... below this much room the trade is tagged cc09_scalp (~40 pips)
    cc09_depart_bars: int = 3            # ... (6) the leg from the sweep extreme reaches the MSS within this many bars [our interpretation of "sharply"]
    nyx_model: bool = False              # M17: cc09_003 setup 2 - the NY expansion turtle soup of a 5m short-term low / high after London set the day's extreme
    nyx_start: int = 570                 # ... window start (510 = the 08:30 futures test) -> 600
    nyx_target_pct: float = 0.0018       # ... 20 EURUSD pips at ~1.10 as a fraction of price [our interpretation]
    nyx_stop_pct: float = 0.0018
    nyx_max: int = 2
    nyx_counts_session: bool = False
    skip_pm_adr_k: float = 0.8           # X14 split: the AM range at or above this x ADR5 = the AM delivered the bulk of the day's range - no PM trade against it (X10d's 0.8)
    pairing: str = "all"                 # M0: one market condition coupled with one tool - "all" / "expansion_ob" / "retracement_void" / "reversal_pool" / "consolidation_eq"
    state_tag: bool = False              # M0 (review fix): stamp Trade.state (consolidation / expansion / retracement / reversal) on every trade, so the report can split by it even with pairing "all"
    # --- caption-gap pass, entries_stops_sizing #1/3 (every switch defaults off / to the built behaviour; the gap id is the comment's first word; es1.py) ---
    no_origin_retest: bool = False       # NEW-no-return-to-origin-ob (cc03_003 ~00:21:37): after >= 2 tests of a daily low and a daily close above the last daily pivot high, the origin low / OB is no entry array of the HTF-array entries (turtle-soup cc_limit / external / ts arrays); the swing's 25-50% arrays stay
    entry_pd_frame: str = "leg"          # B5-prior-day-ny-range-retracement (cc08_007 ~00:00:40): the leg_pd frame - "leg" (the displacement leg, built) / "prev_day" (previous RTH day H-L) / "prev_ny" (previous NY session 08:30-16:00 [our interpretation]) / "any" (either one in discount passes)
    ob_need_fvg: bool = False            # A12-ob-requires-signatures (022 ~13:12, ~1:37:52): an OB order arms only once an FVG with c1 on the OB candle (or the next one) has printed (c3 closed) - until then it is a potential OB
    cisd_ob_px: str = "eq"               # A12-cisd-open-buy-level (032 ~53:04, ~55:30): "eq" (M11b: the post-CISD range EQ, built) / "open" (the first candle's open of the down-close run; CISD = high >= open + 1 tick; valid while no body closes under the run low)
    cisd_adds: bool = False              # ... every later down-close run with its own CISD before the draw gives a new open as an add (E12 sizes; none after a partial)
    ob_vi_overshoot: bool = False        # A12-ob-overshoot-to-vi (050 ~33:56): an adjacent VI under the bullish OB (above a bearish one) extends the zone to the VI's far edge: stop = far edge - 1 tick, a body close beyond it exits
    mt_break: str = "off"                # D4-mt-source-tally: "off" (the built stop_mode / mt_close_stop behaviour) / "close" (a body close under the OB MT is the failure; the hard stop sits at the OB far edge) / "trade" (any trade under the MT stops) / "warn" (a trade under the MT is a tag only; the far-edge stop)
    breaker_refine: bool = False         # A13-breaker-fvg-refinement (031 ~1:02:29; 032 ~41:26): an FVG / VI inside the breaker zone is the entry (its near edge); cancelled on a body close under its low
    iofed_strict: bool = False           # E2-iofed-full-definition (015 ~18:57; 047 ~10:40): entry="iofed" needs the CE untouched since the gap formed and a fill above the CE; a trade to the CE before a 3-bar swing low inside the gap has confirmed exits at the CE
    add_pref_ob_in_vi: bool = False      # A5-ob-in-vi-over-newer-fvg (009 ~12:07): an add prefers a down-close OB that traded into a VI (add at its MT) over a newer small FVG of the same pullback
    gap_tf_mode: str = ""                # A5-mtf-gap-refinement (044 ~45:31; 046 ~19:32; 024 ~21:39): "refine_down" (an HTF entry gap is replaced by the LTF FVG of the same displacement inside it) / "widen_up" (a target FVG overlapping an HTF FVG of the same move extends to the HTF far edge)
    vi_tol: str = "none"                 # A9-vi-retest-tolerance (026 ~1:34:23; 027 ~16:27): the VI stop - "none" (built) / "ce" (retests up to the VI CE stay valid: invalidation = the VI far edge) / "adjacent_extreme" (a small VI may overshoot to the adjacent candle's extreme)
    vi_tol_small_pts: float = 2.0        # ... "small VI" = at most this many points [our interpretation]
    prop_mt_test: str = "close"          # A16-propulsion-block-full (019, 075, 079 / 027, cc04_008): the propulsion invalidation - "close" (a body close under the PB MT, built) / "wick" (any trade through it)
    prop_fail_flip: bool = False         # ... on a failure (prop_mt / prop_wick exit): no more longs this session (shorts only; overrides an earlier only_side), the PB becomes a reclaimed bearish block = the "pb_flip" entry array of the flipped side (state pb_flip -> setups.array_cands)
    prop_deep_mult: float = 1.0          # A16-propulsion-depth-grade (079 ~12:00): the risk multiplier of a deep PB (depth = (K_high - P_low) / (K_high - K_low) > prop_deep_cut); 0 = skip
    prop_deep_cut: float = 0.5           # ... the cut [our interpretation]
    mit_iofed_edge: bool = False         # A15-mitigation-definition-and-iofed (012 ~11:39): after a mitigation-block tag the next FVG below is entered at its near edge (entry="edge"), never the CE
    leg_pd_anchor: str = "displacement_leg"   # A21-implied-range-to-target (025 ~41:59) / A21-post-cisd-range-retrace (075 ~1:23:41): the leg_pd range - "displacement_leg" (built) / "target" (sweep extreme .. the first ladder target) / "retrace_range" (the swing high the decline began from .. the sweep low)
    broken_wick_stop: str = "body_edge"  # A23-broken-wick-ce-inversion (043 ~10:45; 044 ~46:41): entry_arrays "broken_wick_ce" - the stop beyond the wick's body edge ("body_edge") or beyond the swept extreme ("swing")
    far_edge_reach: bool = False         # A5-far-edge-reach-conditions (058 ~27:22, ~29:46; 080 ~12:22): HTF entry arrays - layering (the limit at the CE of the latest nested LTF FVG) / an inner BPR (no full fill) protect the far edge; a residual sub-gap at it makes it a valid entry
    fvg_edge: str = "original"           # A5-partial-reprice-shrink (056 ~16:13): "original" / "remaining" (the part of the entry FVG not yet traded through - a wick into the gap from above shrinks its top)
    ob_ce_confluence: bool = False       # A12-ob-edge-at-fvg-ce (058 ~32:02): a 15m OB edge within ob_ce_tol_pts of the entry FVG's CE is the entry level
    ob_ce_tol_pts: float = 1.0
    leg_fib: str = "wick"                # A21-intraday-fib-bodies (058 ~41:48): the leg / EQ anchors - "wick" (built) / "body" (lowest min(o,c) .. highest max(o,c))
    htf_depth_mult: tuple = (1.0, 1.0, 1.0)   # A8-htf-gap-resistance-grade (065 ~1:27:00): risk multiplier by how deep an HTF gap entry reacted: (near / ce / far); tag lv_tags htf_depth_*
    ob_need_narrative: bool = False      # A12-ob-requires-narrative (059 ~19:00; 064 ~51:56; 065 ~1:28:02): an OB qualifies only with the bias this way, a transitional event (a pool swept, or an array traded into) before or by it, and (ob_need_htf_array) lying inside an HTF array
    ob_need_htf_array: bool = True       # ... (2) the OB lies inside a same-side HTF array [our interpretation: the array contains the OB bodies, tolerance eq_tol_pts]
    ob_wick_ltf_entry: bool = False      # A12-ob-open-anchor-ltf-wick (061 ~26:10): an HTF OB with a stubby wick (< 25% of its range) - the entry is an LTF FVG / OB inside [open, low] of it; the wick area does not invalidate
    htf_ob_anchor: str = "open"          # A12-ob-anchor-level (default "open" = the 2023 Mentorship level; "extreme" is the Core Content swing level and sits in study.PRE_OWNER) (cc03_001 ~28:18; cc06_004; cc10_005; 072): the HTF OB level - "open" (A12 2023) / "extreme" (CC swing: the OB candle's high / highest high of the series)
    scan_tfs: tuple = (1,)               # new-multi-tf-scan (070 ~30:37; 072 ~11:09): minutes of the extra bar sizes whose FVGs join the entry gaps ((1, 2, 3, 4, 5) = 1m..5m; 120 = 2h); 1 = the base bars only
    two_min_ce: bool = False             # new-2m-fvg-ce (062 ~40:09): a 1m FVG whose displacement is two same-direction 1m candles enters at the CE of the 2m FVG
    fvg_skip_below_pool_short: bool = False   # A5-skip-fvg-near-stop-pool (060 ~1:11:00): skip an entry FVG within fvg_pool_gap_pts of an untaken short-term extreme that lies between it and the protective extreme (side-space mirror: covers both directions)
    mtf_hold: bool = False               # (scope: only on bars finer than 5m, a coarse 5m gap judged on the 1-4m closes - nothing on 5m base bars) A5-multitf-hold-test (064 ~1:32:01): a 5m entry gap is judged on the 1-4m bars - two or more bar closes inside it on any of them cancel the entry
    ote_gate_4th: bool = False           # (scope: the FVG path through ote_adjust, and the "ote" entry array) M13-swing-confirm-gate (cc01_004 ~13:58, ~21:38, ~28:18): the OTE watch starts only once the leg's far extreme is a 3-candle swing confirmed by the 4th candle; a new extreme before EQ redoes the gate
    ote_reanchor: bool = False           # M13-reanchor-parent (cc01_004 ~13:58, ~37:30): on a new swing high above H with no trade under L the leg is re-anchored (EQ / 62 / 70.5 / 79 recomputed, gate redone)
    ote_nested: bool = False             # (scope: the FVG path through ote_adjust only; the "ote" array keeps the parent band) M13-nested-ranges (cc01_004 ~23:31; cc01_005 ~8:28): child legs from a reaction level are kept; a child stopped out falls back to the parent leg's OTE
    ote_parent_third: bool = False       # ... (cc01_006 ~13:16) the high-probability long is in the lower third of the parent swing AND under the EQ of the current small range
    ob_mt_range: str = "body"            # A12-ltf-ob-upper-half (cc02_002 ~6:24): the "mt" OB entry price - "body" (the body mean, built) / "range" ((high + low) / 2 of the candle)
    ob_reach: str = "wick"               # A12-ob-reached-body (cc03_002 ~8:33): an OB counts as reached on a WICK (built) or only when a BODY enters it (min(open, close) <= OB high)
    # --- caption-gap pass, entries_stops_sizing #2/3 (every switch defaults off / to the built behaviour; the gap id is the comment's first word; es2.py) ---
    ob_session_filter: bool = False      # NEW-new-ob-session-filter (cc03_003 ~41:41): an OB entry needs the OB candle in a London / NY window (ob_session_windows) or a run below a prior London / NY session low
    ob_session_windows: tuple = ((120, 300), (420, 660))   # ... London 02:00-05:00, NY 07:00-11:00 ET [our interpretation]
    ob_grade_mult: tuple = (1.0, 1.0)    # A12-mt-grading (cc04_003 ~9:59 / ~10:35 / ~24:21): the size multiplier of an OB retest graded A (low at / above the MT) / B (slightly under it, no body close under); (1, 1) = no grade tag
    ob_grade_tol: float = 0.10           # ... "slightly" = at most this share of the body height [our interpretation]
    gap_risk: str = "off"                # A6-voids-fill-holding-range (cc04_002 ~1:41): in a CONSOLIDATION an unfilled FVG between the entry and the stop (or just under it) will fill - "widen" the stop under it / "skip" the order
    gap_risk_near_pts: float = 2.0       # ... "just below the stop" = within this many points [our interpretation]
    rb_ctx_mult: float = 1.0             # A17-rb-trend-context (cc04_006 ~5:14): the risk multiplier of a rejection-block entry that is not (bias this way AND at an HTF array); 0.5 = graded lower [our interpretation]
    entry_fvg_min_tf: int = 1            # B5-execution-tf-15m-min (cc12_004 ~5:00; contradicts the 2023 1m execution): the entry FVGs come from bars of at least this many minutes (5, 15 tested)
    ob_mt_two_sided: bool = False        # A12-mt-worked-both-sides (cc09_008 ~14:37): an OB whose MT price has traded on both sides of is no MT level - the stop falls back to the OB low
    stop_bpr_mt: bool = False            # A11-bpr-mt-overshoot-cap (026 ~00:59:14): a BPR just beyond the entry gap's far edge caps the overshoot at its MT - the stop beyond that MT
    bpr_adj_pts: float = 1.0             # ... "directly beyond" = the BPR's near edge within this many points of the gap's far edge
    fvg_wick_ce: bool = False            # new-fvg-wick-ce (075 ~01:04:11): an entry FVG whose first candle has a long lower wick (wick >= body) is entered at the wick CE (entry="ladder": CE then wick CE); body close under the wick CE exits, the hard stop at the wick low
    ob_mt_if_swept: bool = False         # A12-mt-retrace-after-stop-run (cc04_003 ~00:32:47): an OB candle that ran a prior pivot low is bought at its body MT instead of the open
    bz_higher_array: bool = False        # A13-breaker-close-beyond-higher-array (081 ~00:14:11): a same-polarity OB / FVG within bz_higher_pts beyond the breaker's far edge: the stop and the abort go beyond that array, not the breaker
    bz_higher_pts: float = 5.0
    fri_shallow: bool = False            # new-friday-near-draw-shallow-entry (070 ~00:47:11): on a Friday closer to the draw than the A-B leg is tall the first FVG of the leg is entered at its near edge (no leg_pd, no deep retrace)
    vi_ob_add: bool = False              # E12-second-stage-ob-at-MT (009 ~00:11:15): the down-close candle whose low trades into an intact VI above the entry is a bullish OB - an add at its MT, cancelled on a body close under the VI
    vi_ob_entry: bool = False            # ... standalone: the same pattern after an MSS as an entry array ("vi_ob" is appended to entry_arrays)
    vi_add_early_pts: float = 0.0        # E12-add-while-falling-toward-VI (009 ~00:08:03): > 0 = a down candle heading to an intact VI: the add limit at VI top + this many points, filled only on a down bar (no VI touch needed)
    close_proximity: bool = False        # E1-close-proximity-entries (022 ~03:08:33): in a macro window with a session lock the entry is the VI / FVG of the shift nearest the market, at its near edge (no breaker retest, no M2 EQ filter)
    close_prox_windows: tuple = ((650, 670),)   # ... 10:50-11:10
    vi_first: bool = False               # E2-vi-primary-entry-array (025 ~00:49:04; 026 ~01:36:42): after the MSS a VI of the leg at / beyond the leg EQ is the entry zone (near edge); the FVG pick is the fallback
    wick_ce_refine: bool = False         # A5-wick-ce-inside-fvg-exact-entry (025 ~01:08:00): a wick CE of the bars before the leg lying inside the entry gap sets the limit (CE + 1 tick)
    wick_ce_lookback: int = 120
    e4_color: bool = False               # E4 candle colour (already built as a SURROGATE, [our interpretation]: retrace_candle="intrabar" - the fill bar OPENS beyond the limit, i.e. it is already up-close so far for a short - is set when this is on and retrace_candle is off; the true bar colour is only known at the close, after the fill)
    e4_wick_ok: bool = False             # E4-redelivery-wick-suffices (026 ~01:57:39): a redelivery already complete at the fill (the fill price or a closed bar since traded across the full range of the most recent opposite-colour candle) counts whatever the fill bar's colour
    fvg_then_ob: bool = False            # E2-fvg-first-then-ob-open (032 ~00:23:46): entry #1 in the FVG, entry #2 (an add) at the OB candle's open when the OB lies beyond the FVG; one stop beyond the OB
    breakaway_chase: bool = False        # E5-breakaway-gap-chase (049 ~00:05:01): after a closed winner (the X14 win re-entry state) the next breakaway-tagged FVG gets a near-edge limit; unfilled after breakaway_chase_bars -> market at the next open
    breakaway_chase_bars: int = 3
    mot_dead_mult: float = 1.0           # E1-market-on-touch (089 ~00:04:20) / E5-breakaway-gap-chase: a converted market order is dead when the next open lies farther over the entry than this many times the planned risk (entry - stop) [our interpretation: 1 = total risk at most 2x]
    fri_shallow_edge: str = "fvg"         # new-friday-near-draw-shallow-entry (070 ~00:47:11): the shallow entry - "fvg" the first FVG of the leg at its near edge / "breaker" the breaker's upper edge (the FVG when there is no breaker under the market)
    breaker_iofed: bool = False          # E2-iofed-breaker-exact-match (043 ~00:16:21): the breaker limit sits 1 tick inside (market side of) the breaker extreme, so an exact match fills under E3
    ifvg_stop: str = "ce"                # M10-ifvg-stop-below-whole-ifvg (067 ~01:19:07): the IFVG stop - "ce" (built: CE + pts) / "far" (beyond the whole IFVG: the far edge - pad)
    ifvg_ob_add: bool = False            # ... an add where the IFVG overlaps a reclaimed OB (levels.reclaimed_obs)
    iofed_gap_bars: int = 5              # E2-iofed-depth-second-gap (074 ~00:36:02): entry="auto2" - the near edge (IOFED) when another same-side gap lies within this many bars ...
    iofed_gap_pts: float = 3.0           # ... and this many points beyond the picked gap, else the CE
    mot_next_open: bool = True           # E1-market-on-touch (089 ~00:04:20; cc04_003 ~00:07:43): entry_order="market_on_touch" - the first bar touching the level (no tick through) -> a market buy at the NEXT bar's open; False = at the level
    entry_offset_ticks: int = 0          # E3-entry-spread-offset (cc02_001 ~00:21:13; cc04_003): every limit moves this many ticks toward the market (a touch of the original level fills)
    add_sizes: str = "decreasing"        # E12-equal-size-adds (001 ~00:39:05; 013 ~00:27:18): "decreasing" (adds) / "equal_or_less" (add_max_n adds of the first unit's size, the 1.3 % cap shrinks them) / "equal_013" (10 / 10 / 5 / 5)
    add_max_n: int = 3
    add_far_edge: bool = False           # ... add location: a limit at the entry FVG's far edge while no body closed under it (001)
    add_wick_retouch: bool = False       # ... add location: a limit at the prior retrace's wick extreme (096)
    add_htf_fvg_edge: bool = False       # ... add location: the near edge of the nearest 30m FVG under the price (002)
    add_ladder: str = ""                 # E12-ladder-631 / E12-067-citation-wrong (021, 026, 060, 070, 067): "" (adds) / "631" / "6421" / "6321" / "067" (8, then 5/5/2/5/5 at reclaimed OB / IFVG retests)
    add_on_ifvg: bool = False            # ... an IFVG formed after the fill, a limit at its near edge (067)
    add_stop_under_array: bool = False   # ... each add raises the stop to the add array's bottom - pad when that is higher and leaves >= min_risk_pts (never lowers)
    in_zone_ladder: bool = False         # E12-in-zone-larger-second (103 ~00:34:22): a breaker entry rests as two limits - 1/3 at the near edge and 2/3 at the breaker MT; later adds are sized from the first leg
    add_after_partial: str = ""          # E12-adds-after-partials-intraday (071 ~00:15:58; 092 ~01:30:08): "" (none, 006) / "inv_fvg" (one add at the broken FVG's edge) / "high_vol" (partials added back in a high-volatility regime)
    add_hv_mult: float = 1.2             # ... high volatility = ADR5 above this x the median of the last 20 daily ranges [our interpretation]
    add_form_eq: bool = False            # E12-add-cutoff-definition (092 ~01:16:43): an add array must have FORMED on the H side of the EQ of the implied range H .. T (the draw); the rest is calibration only (add_cut_ref="range" / add_cutoff are built)
    add_day_mode: str = "eq_cutoff"      # E12-trend-day-adds (038 ~01:15:27): "eq_cutoff" (the built add cuts) / "trend_day" (a clean trending day keeps adding until the far daily extreme)
    trend_day_adr: float = 0.5           # ... trend day: price >= this x ADR5 from the 09:30 open without trading back through it, no FOMC / CPI / jobs day [our interpretation]
    add_low_end_size: str = "smallest"   # E12-low-end-add-conditions (006 ~00:52:14): the add_low_end size - "smallest" (the smallest earlier add, built) / "ladder" (the next add fraction)
    # --- caption-gap pass, entries_stops_sizing #3/3 (stops_sizing_scaling_in.md items 11-62; every switch defaults off / to the built behaviour; the gap id is the comment's first word; es3.py) ---
    add_dig_mult: float = 1.0            # E12-repeat-dig-smaller-add (003 ~00:44:27): < 1 = an add at an FVG that price already dug into twice (a bar low under the top after a close above it) is cut to this fraction (0.67: 3 -> 2)
    add_momentum: bool = False           # E12-single-add-variants (020 ~00:01:40): after an OB-before-break entry ONE add at market (the next open) once a bar closes add_mom_r x the initial risk above the fill; no later OB-retest adds
    add_mom_r: float = 0.5
    add_mom_frac: float = 0.25
    add_wick_ce: bool = False            # E12-wick-ce-add-5m (010 ~00:58:28): a limit at the CE of the latest add_wick_tf-minute wick (lower wick for a long) formed since the fill, even while executing on 1m
    add_wick_tf: int = 5
    vi_ladder: bool = False              # E12-631-vi-wickce-invalidation (026 ~01:48:03): rung 1 = the next VI after the fill, rung 2 = the latest wick CE, only beyond the entry VI; a weak wick-CE reaction caps the last add at 1 contract (use add_ladder="631")
    vi_ladder_exit: bool = False         # ... price trading to the MT of the OB before the displacement (before the first partial) exits everything at that level
    add_void: bool = False               # E12-liquidity-void-add (018 ~00:04:01): a 1m liquidity void formed after the fill, overlapping the 5m FVG CE band and above the entry OB MT = an add at the void bottom + 1 tick
    add_gate_wick: bool = False          # X8-downclose-wickce-add (085 ~00:10:04): a body closing through the open of the opposing-close candle in the way (between the entry and T1) = a stop-direction add at that candle's target-side wick CE
    ifvg_mohawk_add: bool = False        # E12-mohawk-add-ifvg (102 ~01:14:30): an untouched (one-pass) IFVG entry also rests a smaller add mohawk_add_ticks beyond the far edge - filled only by a mohawk
    mohawk_add_ticks: int = 2
    add_reclaimed_ob: bool = False       # E12-mm-sell-model-adds (104 ~00:53:29): one add at the retest of a reclaimed OB (levels.reclaimed_obs, both sides) - size min(first unit, add fraction 0)
    daily_loss_pct: float = 0.0          # E11-funded-account-caps (040 ~00:01:56; 050 ~00:48:18): > 0 = the day's loss limit (fraction of the start-of-day equity, 0.02 on a 150k account): a new order / add that could reach it is skipped, a position is flattened at the close that reaches it
    max_exposure_pct: float = 0.0        # E11-portfolio-exposure-cap (cc05_013 ~00:26:39; cc06_002 ~00:12:27): > 0 = backtest.combine drops a trade whose entry risk would push the open risk of all concurrent trades over this fraction of equity
    alloc_frac: float = 1.0              # E8-alloc-30pct (cc05_013 ~00:04:16): risk_pct / max_total_risk_pct apply to this fraction of the equity (CC: 0.30; 1.0 = the 2023 whole-account rule)
    htf_near_risk_pct: float = 0.0       # E8-E9-5pct-near-htf (102 ~01:24:11): > 0 = the per-unit risk (first unit and each add) when the trade runs toward a stored HTF level within htf_near_pts ES pts (research switch; away from them min(risk_pct, 0.015))
    htf_near_pts: float = 30.0
    htf_near_any: bool = False           # E8-E9-5pct-near-htf review fix: True = ANY 4h/D/W/M level within htf_near_pts beyond the entry triggers the 5 % risk (the broader reading); False = only when the DRAW is such a level
    htf_near_cap_pct: float = 0.20       # ... and the total-risk cap of such a trade
    htf_near_add_literal: bool = False   # E8-E9-5pct-near-htf review fix (102 ~01:24:11): True = the spec's literal reading - the first unit AND each add are sized at htf_near_risk_pct (the add = that budget / its stop distance), the total at htf_near_cap_pct; False = adds stay proportional to the 5 % first unit [owner question]
    class_risk: dict = field(default_factory=dict)   # E8-risk-by-trade-class (cc09_006 ~00:05:42; cc06_006; cc05_018): {"scalp": 0.005, "day": 0.012, "swing": 0.015, "position": 0.01} per-unit risk by trade class (scalp = a single fixed exit at <= 1.5R); empty = off
    max_lev: float = 0.0                 # E8-leverage-cap-3x (cc06_006 ~00:15:32): > 0 = position notional (first unit + adds) <= max_lev x equity
    stop_fixed_pts: float = 0.0          # E8-new-trader-drill (042 ~00:32:11; 001 ~00:55:20): stop_mode="fixed" - the stop this many ES pts under the entry
    fixed_units: int = 0                 # ... > 0 = the first unit is exactly this many contracts (x lot units) whatever the equity / risk %
    t1_fixed_r: float = 0.0              # E8-2pct-new-trader (cc02_001 ~00:16:41): with t1_fixed_all, the single exit at this many R (the cc_starter preset: 1R)
    trader_mode: str = ""                # E8-new-trader-graduation (042 ~00:21:02): "new" = 1 contract per trade, +1 after each grad_block closed trades with a positive net (backtest.run); wide stops (E6-new-trader-wide-stops)
    grad_block: int = 20
    grad_max: int = 4
    deep_run_mult: float = 1.0           # E9-deep-discount-reduced (099 ~00:28:59): < 1 = a with-trend trade after a deep_run_weeks one-way weekly run into the bottom / top quarter of the 13-week range is sized by this and takes no adds (htf.table column deep_run)
    deep_run_weeks: int = 3
    freq_ref: float = 0.0                # E9-frequency-small-size (101 ~00:44:29): > 0 = risk x min(1, freq_ref / trades in the last 5 sessions) (set by backtest.run through freq_recent)
    freq_recent: int = 0                 # ... runtime input: the trades of the last 5 sessions (backtest.run fills it each day)
    probe_mult: float = 0.0              # new-probe-position (026 ~00:16:16): > 0 = on an indecisive session (bias set, nothing by probe_t) a market probe of this fraction of the normal size toward the bias; no adds
    probe_t: int = 630
    probe_cut: float = 0.5               # ... closed early when price trades this fraction of the stop distance against the entry
    wick_ce_tol_ticks: int = 1           # E6-wick-ce-stop (022 ~01:14:11; 085; 089): stop_mode="wick_ce" - beyond the defending wick's CE by the pad + this many ticks (a tick through the CE is tolerated)
    trail_wick_ce: bool = False          # ... each new defending wick after the fill raises the stop to its CE - pad (never lowers)
    mt_pad_ticks: int = 2                # M2-stop-by-fvg-choice (022 ~00:53:59): stop_mode="m2_auto" - the OB MT minus this many ticks when the FVG has VI + OB confluence, else the leg extreme - 1 tick
    stop_old_low_body: bool = False      # E6-old-low-rejection-body (022 ~02:50:25): an old low under the stop moves the stop below that low's rejection body (the lowest open / close of its 3-bar swing) - 1 tick
    stop_gap_edge: str = ""              # E6-nwog-stop (050 ~00:54:56): "own" = beyond the far edge of the opening gap the entry array sits in, "all" = beyond every opening gap within the max risk
    three_pd_n: int = 3                  # E6-three-pd-arrays (098 ~00:47:02): stop_mode="three_pd" - behind this many protecting PD arrays (the outermost found when fewer)
    bpr75_ref: str = "upper"             # E6-bpr-75-stop (075 ~01:07:19): stop_mode="bpr75" - inside the cleared two-way range at its 75 % level measured from the "upper" (H - 25 %) or "lower" (L + 25 %) end
    new_max_risk_pts: float = 15.0       # E6-new-trader-wide-stops (102 ~01:52:49): trader_mode="new" - the max risk (a 15-pt stop is fine at micro size)
    tight_stop_pts: float = 3.0          # ... a stop tighter than this: no immediate same-direction re-entry after it (experienced only) [our interpretation], and with stop_widen_new it is pushed out
    stop_widen_new: bool = False
    stop_htf_anchor: bool = False        # E6-refined-stop-htf (cc02_002 ~00:06:34): a sweep into an HTF array keeps the stop beyond min(sweep extreme, that array's bottom) - the LTF refinement moves the entry only
    ob_stop_kind: str = ""               # E6-ob-body-stop (cc04_003 ~00:10:44): the OB-before-break stop - "" (the built MT / sweep stop) / "body" (under the OB body low = the close) / "wick" (under the OB wick low)
    ob_anchor: str = "highest_open"      # A12-ob-anchor (cc05_015 ~00:16:48): multi-candle OB top / entry anchor - "highest_open" (the series' highest = first open, built) / "last_open" (the last down candle's open, ultra tight)
    mit_entries: bool = False            # E6-mitigation-block-stop (cc04_004 ~00:14:00): a mitigation block (levels.mitigation_blocks) is an entry array - limit at its body edge, stop beyond its far extreme + 1 tick
    prop_stop: str = ""                  # E6-propulsion-mt (cc04_008 ~00:05:21): "mt" = a prop_entry order's stop just beyond the propulsion candle's MT - 1 tick

    # --- caption-gap pass: targets_partials #1/4 (digests/rulebook_gaps; every new switch off unless noted) -----------------------------------------------------------------------------------------
    nwog_revert_targets: bool = False    # BH-B14-consolidation-week-reversion (051 ~00:13:12): in a B14 consolidation NWOG week (nwog_regime table column "cons") the first rung is the current NWOG's near edge (the nearest old NWOG when the entry is already past it); one scalp exit; a rung counts only with another draw factor (pool / FVG / wick CE) within eq_tol_pts
    dxy_rally_cap: bool = False          # BH-B19-DXY-falling-risk-on (032 ~00:32:11; 102 ~00:31:27): with the daily dxy state +1 a long's ladder ends at its first array / pool rung (no runner), with dxy -1 a short's does (index rallies only reprice an inefficiency); the other side keeps the ladder. Gold hook: ctx.intermarket.get("gold") (not loaded)
    resist_def: str = "off"              # BH-L4-resistance-definitions (062 ~00:08:42; cc04_002 ~00:31:25): "struct" (>= resist_overlaps 5m swing pivots between the entry and T1), "htf" (against the weekly state), "both" = either; tags Trade.resist "high" / "low"
    resist_overlaps: int = 3
    resist_filter: bool = False          # ... and with it the high-resistance orders are skipped
    post_raid_cap: bool = False          # X3-a21-eq-after-raid (cc05_002 ~00:15:30): after an HTF raid and rejection (table first_clue / tug = -1) with price at / under the range EQ no long rung lies beyond the raided high (mirror)
    eq_first_rung: bool = False          # X3-a21-rebalance-to-eq (cc05_015 ~00:04:03): an entry in the discount of the 20-day range (pd20 column) gets the range EQ as a rung "eq20" (T1 when nothing is nearer); mirror
    htf_range_runner: bool = False       # L14-monthly-to-weekly-range (cc07_001 ~00:09:47): a matrix_tf_lower draw beyond the ladder keeps htf_runner_frac of the position open to that level (flat time still applies)
    htf_runner_frac: float = 0.1
    or_needs_bias: bool = False          # T4-or-needs-bias-iof (cc10_010 ~00:11:25): OR30 / OR60 levels (target pools, the or60 turtle-soup variant) count only with a bias side set and the daily iof agreeing [our interpretation]
    nfp_week_split: bool = False         # N2-nfp-week-imprecise-targets (003 ~00:18:39): in an NFP week (Mon-Fri) and on an FOMC day the ladder split is (nfp_week_partial, rest) and HTF-array rungs sit nfp_week_inside_pts inside the array [our interpretation: the 0.8 / 1 pt values]
    nfp_week_partial: float = 0.8
    nfp_week_inside_pts: float = 1.0
    nfp_no_htf_targets: bool = False     # N1-nfp-no-htf-hold (006 ~00:03:31): on a jobs day the HTF array rungs (htf_targets, daily VIs, weekly pools) are dropped - intraday liquidity only (PDH / PDL, old daily H / L, session pools stay)
    nfp_flat_by: int = 0                 # ... [our interpretation] with > 0 a jobs day's AM trades are flat at this minute (720 = 12:00; the am_exit close)
    eve_mode: str = "off"                # N4-eve-of-high-impact (029 ~00:52:11; 042 ~00:39:05): the day before a CPI / NFP / FOMC release: "tag" (lv_tags pre_cpi / pre_nfp / pre_fomc, eve_risk_mult) or "bnb" (also one scalp exit at min(entry +- eve_target_pts, first pool) before the level, no ladder trail, the day ends after one win)
    eve_target_pts: float = 5.0
    eve_risk_mult: float = 1.0
    skip_high_resistance: str = "off"    # new-skip-high-resistance (036 ~00:39:59): "tag" (lv_tags high_res, the slow ladder) / "skip" on a high-resistance order: >= hr_max_obstacles opposing open FVGs + untaken swing pivots between the entry and the draw
    hr_max_obstacles: int = 3
    hrlr_news_only: bool = False         # L4-hrlr-news-exception (cc01_007 ~00:08:34): a high-resistance draw (obstacle count above lrlr_max; res_high_min when lrlr_max is off) is a locked draw only on a jobs / FOMC day after its release; otherwise the nearest other level is the draw
    reh_merge_pts: float = 0.0           # A3-reh-under-older-high (021 ~00:40:41): > 0 = a relative equal high (pool_eq) within this many ES pts under an older higher pool is one buy-side pool - the target is the older high (the sweep side too)
    vi_void_level: bool = False          # A10-vi-target-ladder (045 ~02:47:00; 061 ~01:55:50): a daily / weekly VI whose wicks leave an unprinted interval (a liquidity void) gets the void's midpoint as a rung
    vi_ob_levels: bool = False           # ... a VI that is part of an order block (c1 is the last opposite candle before the displacement) uses the OB open and MT instead of the VI CE
    vi_keep_traded: bool = False         # ... a traded (dead) daily / weekly VI keeps both edges as levels for vi_keep_days sessions (076)
    vi_keep_days: int = 20
    vi_return_tag: bool = False          # ... tag only (077): the entry sits at an edge of a VI traded within the last 5 sessions
    bpr_gate_htf: bool = False           # A11-bpr-clear-for-htf-targets (012 ~00:08:35): an HTF (D / W) target beyond an opposing BPR stays pending until a bar closed beyond the BPR's far edge and left an FVG; tag bpr_chop
    old_high_ladder: bool = False        # L10-A17-old-high-target-ladder (003 ~01:03:13; 030 ~01:04:30): toward an old swing high without an FVG / VI on the way: body edge ("speed" rung, speed_frac of the position, never a done flag) -> wick CE -> the high
    speed_frac: float = 0.2
    speed_bump_tfs: tuple = ()           # N-opposing-fvg-speed-bump (019 ~00:11:08; 089 ~00:04:52): minutes of the opposing-FVG timeframes (5, 15, 60 ...) that are neither a cap, a bump rung, nor a target when the session bias agrees with the order
    measuring_qualify: bool = False      # A6-measuring-gap-confirmation (003 ~31:51; 062 ~44:24): a measuring gap projects only once QUALIFIED (the pullback left its far edge untouched and a new extreme printed - levels.bk_state)
    measuring_need_pool: bool = False    # ... and only when the -1 SD lies beyond an old pool
    stubby_wick_ce: bool = False         # A23-stubby-wick-first-approach (028 ~15:24): the first approach to a day extreme (pdh / pdl) whose wick is <= stubby_frac of the candle range targets the wick CE instead
    stubby_frac: float = 0.2
    void_ce_rung: bool = False           # A10-void-levels-persistence (065 ~1:58:00): the CE of an open liquidity void (intraday and daily / weekly VIs with a void) as a rung
    void_persist_days: int = 0           # A10-void-levels-persistence (065 ~1:58:00; 077 ~2:24: "can stay open for a long time"): with void_ce_rung, the intraday voids of the last N regular sessions stay open rungs until traded (0 = the day frame only)
    vi_quarters: bool = False            # A9-vi-quarters (074 ~16:08): the 25 / 50 / 75 % levels of an opposing weekly VI as rungs
    array_reuse: str = "first_touch"     # A22-array-reuse (061 ~2:11:51): "first_touch" (skip_exhausted / the htf hygiene as built) / "reuse" (an array is spent only by a body close through its CE) / "tiebreak" (an alias of reuse: the ladder is price-ordered, so an untested-first ordering has no effect [our interpretation])
    htf_no_time_stop: bool = False       # ... the X9 time stop does not apply to a trade whose entry array is W / M
    lrlr_zone: bool = False              # L4-lrlr-bounds (cc01_007 ~12:03): the low-resistance zone (MSS up .. the broken old low L_b) caps the ladder at L_b and adds the untaken short-term highs inside it as rungs
    leg_mt_target: bool = False          # A10-one-sided-leg-levels (cc03_002 ~3:38; cc04_004 ~10:17): the body MT (first open + last close) / 2 of the one-sided leg is a rung before the leg start
    erl_range_update: str = "off"        # L14-dealing-range-redefine (cc04_002 ~5:59): "swing" = with erl_range_swings the dealing range is rolled by tp1.current_range (a break of the range high sets range_high = the new swing high, range_low = the swing low that started the leg)
    breaker_overtake: bool = False       # A22-breaker-precedence (cc05_014 ~28:18): breaker_first keeps its cap until a BODY close through the breaker zone (a wick into it no longer re-enables the arrays beyond)
    rb_fallback: bool = False            # A22-rejection-block-fallback (cc05_014 ~22:54): with no opposing OB in the range the rejection block body level, then the old high, are the rungs
    matrix_anchor: str = "eq"            # A22-matrix-anchor-market-price (cc06_003 ~3:45): "price" = the matrix_targets list starts at the current market price (the arrays between price and the leg high count)
    level_polarity: bool = False         # A22-old-level-polarity (cc05_014 ~23:22): an old low above price (high below price) is a premium (discount) array whatever its type - a rung of the long (short)
    ob_location_cap: bool = False        # A21-ob-strength-by-location (cc06_004 ~35:33): an OB entry in the wrong half of the 20-day range (a long in premium, a short in discount) gets the first rung only
    swing_grade_tag: bool = False        # new-swing-grades (cc07_003 ~17:26): Trade.swing_grade 1-4 = the entry's place in origin..terminus (sweep extreme .. leg high: 0.25 / EQ / 0.75 / terminus)
    sd_need_array: bool = False          # new-swing-projection-fulcrum (cc07_003 ~27:33): a fulcrum_week projection is kept only where it overlaps an opposing array on a lower timeframe
    sd_fulcrum_ext: tuple = (1.27, 1.68, 2.0)   # ... multiples of the fulcrum range measured from the week's low (2.0 = the 100 % symmetrical swing)
    # --- caption-gap pass: targets_partials #2/4 (digests/rulebook_gaps/levels_liquidity_targets.md items 15 .. 101; tp2.py; every new switch off unless noted; the gap id is the comment's first word) ---------------
    eq_leg: str = "sweep"                # L4-target-below-eq-leg (042 ~01:09:19): the dealing-range leg of draw_below_eq: "sweep" (the sweep extreme .. the leg high, built) / "rally" (the sweep extreme .. the high that began the run into it: the start of the one-sided leg, else the session's extreme) [our interpretation]
    eq_beyond_imb: bool = False          # L4-target-below-eq-leg (049 ~00:03:42): after the pool P is picked, the first 15m (else 60m) imbalance beyond P is the final target (exit at its near edge) when it lies beyond the EQ
    hrlr_time_k: float = 0.0             # L4-resistance-runs (cc01_007 ~10:00): > 0 = a target is dropped when the bars price spent in the band [first intermediate swing, target] exceed hrlr_time_k x the bars of the leg (the sweep to now), unless the day is a jobs / FOMC day (test 1.0)
    clear_path: bool = False             # L4-resistance-runs (cc08_007 ~6:58): the draw needs an opposing 4h / D array beyond it with lrlr_max satisfied up to it, else the order is skipped
    linger_bars: int = 10                # L4-resistance-runs (025 ~17:40; 095 ~31:03) [our interpretation]: with hrlr_time_k / clear_path on, a position whose first linger_bars closes all stay within linger_pts of the entry is tagged "lingered" (the existing X9 time stop does the exit)
    linger_pts: float = 1.0
    session_pool_first: bool = False     # L4-session-pool-before-rel (067 ~00:50:27): the nearest untaken session-range pool (lunch, previous PM, London, AM) in front of the chosen rel-eq draw becomes the first rung AND the draw; the rel-eq pool stays as the next rung
    nwog_ladder: bool = False            # L5-nwog-target-ladder (020 ~00:03:50; 025 ~00:43:43): an NWOG draw takes near edge (nwog_near_frac) -> CE (nwog_ce_frac, the bulk) -> far edge (the rest); conflict with L9 (the far edge a "ringer") listed in the rulebook
    nwog_near_frac: float = 0.0          # (the engine exits at least one lot per rung)
    nwog_ce_frac: float = 0.8
    nwog_far_split: int = 3              # L5-nwog-target-ladder: the far edge is scaled out in this many rungs ("one contract at a time")
    nwog_pre_frac: float = 0.2           # L5-nwog-target-ladder: the share of the size on the rungs below the NWOG near edge that stay
    event_horizon_target: bool = False   # L5-event-horizon-objective (037 ~00:22:37; 051 ~16:51): the midpoint between NWOG k's and NWOG k+1's near edges is a rung; NWOG k+1's levels stay out of the ladder until that midpoint traded (one tick through)
    nwog_magnet: bool = False            # L5-old-nwog-in-consolidation (044 ~01:18:34; 051 ~17:37): the stored NWOG running through the consolidation of an old daily swing high (bodies of the pivot bar +-1) / through the current cluster is tagged nwog_magnet / range_anchor and its near edge is the preferred draw
    consol_min_bars: int = 6             # ... [our interpretation] a consolidation = this many overlapping bars within consol_max_adr x ADR5
    consol_max_adr: float = 0.3
    org_beyond: bool = False             # L7-org-overshoot-discount (043 ~00:12:22): with the ORG far edge as the draw the ladder goes on to the first pool / HTF array beyond it within org_beyond_adr x ADR5
    org_beyond_adr: float = 0.5
    org_ce_if_flow: bool = False         # L7-org-partial-close-orderflow (068 ~00:11:50): opposing arrays (FVG / OB) inside the ORG make its CE the final rung; the far edge stays as a runner slice (htf_runner_frac)
    htf_gap_final: str = "ce"            # L9-htf-fvg-target-ladder (010 ~00:58:40; 029 ~00:32:25; 098 ~01:01:48; 102 ~02:12:22): with htf_gap_gate the 75 % and the far edge of an HTF FVG appear only after a bar closed beyond its CE ("ce"); "far_edge" keeps them while the bias table's flip is not against the order
    htf_gap_gate: bool = False           # ... the switch that turns the CE-first gating on (the spec's default "ce" would otherwise change the built ladder)
    weekly_bisi_ts_block: bool = False   # L9 (102 ~02:12:22) [our interpretation]: no turtle-soup long at a pool within ts_max_pts above an unfilled weekly BISI (the draw is the BISI)
    keep_traded_wfvg: bool = False       # L9 (098 ~01:01:48): the edges of weekly FVGs price traded through stay "array" levels
    wick_long_only: bool = False         # L10-intraday-wick-ce (062 ~00:25:01): wick_tfs counts only LONG wicks (wick >= body and >= the 20-bar median wick of its timeframe) [our interpretation]
    min_obj_frac: float = 0.0            # L10-intraday-wick-ce (058 ~00:17:40): > 0 = the nearest long 1h / 4h wick CE before the draw is the minimum objective: a protected partial of this share (tag min_obj)
    sd_arm: str = "trade"                # L12-sd-activation (029 ~00:21:45; 008 ~00:06:39): "close" = an SD projection is armed only after a bar CLOSED beyond the anchor extreme and the next sd_arm_bars closes stay beyond it ("trade" = the built behaviour)
    sd_arm_bars: int = 1
    sd_ref_roll: bool = False            # L12-ref-rolls-to-new-high (014 ~00:03:27): the buy-side reference rolls to every newer confirmed swing high above it before the first SD level beyond it is picked
    sd_multi_tiers: tuple = ()           # L12-cluster-anchors (014 ~00:03:48): ("itl", "ltl") = one SD range per intermediate / long-term low of the up-leg (low .. the swing high before it); >= sd_cluster_min levels within sd_cluster_ticks (2 when 0) are one "proj_cluster" rung (the preferred final target)
    sd_cluster_min: int = 3
    proj_exit_ticks: int = 0             # L12-projection-exit-1tick (013 ~00:29:08): > 0 = a projection rung (kinds proj*) exits this many ticks before its level (0 = the X2 offset)
    sd_cap_htf: bool = False             # L12-cap-at-htf-array (029 ~00:37:20): SD levels beyond the far edge of the nearest opposing 15m+ FVG are dropped
    sd_htf_extreme: bool = False         # L12-prior-session-swing-htf-extreme (035 ~00:38:13): with sd_anchor "m15_leg" only the SD levels within sd_htf_tol of an HTF level are kept (kind proj_htf); a proj_htf rung reached after 11:00 with an SMT closes the trade
    sd_htf_tol: float = 1.0
    sd_premium_consol: bool = False      # L12-sd-in-premium-consolidation (043 ~00:14:29): on a consolidation day (dplan tag consol_day / no_draw) the SD level is the first beyond the pool AND above the 50 % of the day's range so far, preferring an old FVG edge / pivot high within 1 pt
    sd_last_hour_k: float = 0.0          # L12-minus3-sd-last-hour (047 ~00:10:59): > 0 = an order at or after 15:00 targets the SD level k of the sd_anchor "mss_leg" leg (no first-beyond rule) and is out by 15:45 (test 1, 2, 3)
    proj_org_reprice: bool = False       # L13-org-sd-projection (055 ~00:19:31; 056 ~00:18:20): ORG multiples (U = the gap size) project from the gap's far edge in the order's direction only after a bar since 09:30 traded back to the prior close
    proj_org_kmax: int = 12              # ... k = 1 .. proj_org_kmax (or the proj_org_k tuple when set)
    session_pools_mode: str = "off"      # L14-session-pools-only (067 ~00:27:37): "rank" = session pools first (draw preference, sweep pools), "only" = pools limited to the previous PM / London ranges, the ORG edges and PDH / PDL, "extended" adds lunch / AM ranges and the rel-eq pools inside those ranges [our interpretation]
    room_ref: str = "exit"               # L15-room-measure-anchors (024 ~00:25:13): "htf_far" measures the room (min_draw_pts) from the entry to the far edge of the nearest opposing 15m+ array (fallback: the draw's exit)
    t1_skip_near: bool = False           # L15-first-sth-offering-5 (012 ~00:32:07): pools nearer than min_draw_pts are dropped from the ladder (T1 = the first pool offering the room) instead of rejecting the order
    overnight_5m_fvgs: bool = False      # X1-london-0300-fvg-draw (018 ~00:03:49): unfilled 5m FVGs formed before 09:30 (overnight / London) are arrays of the ladder (near edge, CE, far edge) and AM lock candidates
    htf_ob_open: bool = False            # X1-htf-ob-open-target (058 ~00:08:20): an opposing daily / weekly OB gives its near edge and its candle open as rungs
    htf_ob_open_final: bool = False      # ... the open is the final target when no FVG / VI lies between the entry and the OB
    org_breaker_stop: bool = False       # L7-org-breaker-inside (072 ~00:32:02): a breaker inside the ORG makes the far side of its candle the final rung (the prior close stays a runner slice)
    beyond_pool_final: bool = False      # B2-target-beyond-pool-inefficiency (071 ~00:22:18; 104 ~00:22:24): the final target is the nearest FVG / OB near edge beyond the draw pool within beyond_pool_adr x ADR5, else the rejection-block body edge, else the next rel-eq pool
    beyond_pool_adr: float = 0.25
    break_accel_gate: bool = False       # new-pool-break-accel-vs-reject (072 ~00:01:21): pools beyond a pool taken today stay only if the break was displaced (body >= break_accel_mult x the mean body, closes beyond, an FVG left); a break that closed back removes them
    break_accel_mult: float = 1.5
    swept_pool_targets: bool = False     # new-old-pool-redelivery (072 ~00:36:04): today's swept pools of the opposite type are re-delivery targets when the bias agrees or another ladder level lies within 1 pt
    proj_breaker_k: tuple = (1.0,)       # L13-breaker-range-sd-weekly (074 ~00:30:15): the multiples of the breaker range (B - A) beyond B; k >= 2 is kind proj_wk and needs the weekly and daily bias to agree with the order
    confl_rank: bool = False             # new-level-confluence-scoring (078 ~00:48:23; 094 ~00:06:04): the final target = the highest-scoring ladder level beyond the first rung (confluence.level_score; ties: the nearest)
    confl_tol_frac: float = 0.001
    sd_fulcrum_def: str = "ep06"         # D23-inception-fulcrum-anchor (090 ~01:34:04; 092 ~01:21:26): the sd_anchor "fulcrum" leg: "ep06" (built: a close beyond the first swing high after the extreme) / "inception" (inception = the sweep extreme, fulcrum = the first displacement leg's swing high, armed when a bar TRADES through it)
    sd_deep_conv: bool = False           # L12-deep-sd-pd-convergence (092 ~01:25:18): deeper SD levels stay (kind proj, the deepest proj_runner) when within sd_conv_ticks of a 5m / 15m FVG edge or CE
    sd_conv_ticks: int = 2
    defended_filter: bool = False        # new-defended-level (cc01_007 ~00:24:23): pools touched >= defended_touches times within defended_band_adr x ADR5 over the last defended_bars bars are "defended" - not targets (tag defended)
    defended_band_adr: float = 0.1
    defended_touches: int = 4
    defended_bars: int = 200
    # --- caption-gap pass: targets_partials #3/4 (digests/rulebook_gaps/levels_liquidity_targets.md 106 .. 178 and management_partials_trailing_exits.md 1 .. 43; tp3.py; every new switch off unless noted; the gap id is the comment's first word) ---------------
    min_rr_final: float = 0.0            # L15-min-3r-final-draw (cc02_001 ~00:05:22): the order is skipped unless the reward to the final target (the locked draw, else the last ladder rung) is >= min_rr_final x the risk (test 2, 3, 5); T1's min_rr is unchanged
    void_legs: bool = False              # new-void-fill-target (cc01_006 ~00:10:28): the CE and the top (the final fill) of the nearest unfilled one-sided down leg (levels.one_sided_legs) on 5m / 15m / 1h are targets; "void_targets" (gap-like voids) is the built twin - an independent switch here (the spec says "with void_targets"; the two target sets are separate, either one alone works, both together add both)
    void_leg_mult: float = 1.5           # ... "large" candle = range >= void_leg_mult x the mean range of the 20 bars before it [our interpretation]
    void_max_opp: int = 1                # ... at most void_max_opp up-close candles inside the leg [our interpretation]
    ob_target_order: bool = False        # X1-bullish-objective-order (cc03_002 ~00:20:14): an OB entry's rungs: the nearest bearish OB candle's low, its high + 1 tick, the near edge of the nearest 1h / 4h / D bearish OB
    weekly_beyond_mode: str = "off"      # L3-daily-target-weekly-beyond (cc04_003 ~00:15:58): "tag" (lv_tags weekly_beyond / monthly_beyond when an untaken weekly / monthly pool lies beyond the first pool rung) / "require" (the order needs weekly_beyond)
    dt_proj: bool = False                # new-double-top-projection (cc04_014 ~00:08:40): 1h / 4h double tops: the pool and the projection (peak + peak - lowest low between) as targets; once a projection has traded the same-direction side is done (x_dt_done)
    grades60: bool = False               # new-60day-range-grades (cc07_006 ~00:10:09): the nine grade lines (0 .. 100 % in 12.5 % steps) of the 60-day range are targets (kind grade); the final target is the next grade unless a nearer pool exists; lv_tags gradeN = the entry's band
    grades60_src: str = "body"           # ... the range from the candle "body" (cc07_005 / cc07_006) or the "wick" extremes (cc05_003)
    target_past_eq60: bool = False       # L14-target-past-eq (cc07_005 ~00:08:07): an entry on the premium side of the 60-day body range targets the first untraded opposing M / W / D array at or beyond the EQ
    grades60_range_only: bool = False    # new-60day-range-grades (cc07_006 ~00:10:09): the grade ladder only in a range-bound daily market (the 60 sessions net moved < drr_net_frac of their range) [our interpretation of the B17 / N8 classifier]; off = any market. The next grade is the final target only after the grade below the entry was traded through without a reaction since the sweep
    proj_ext_sym: bool = False           # L13-cc-extension-projections (cc07_003 ~00:30:54): also the 100% symmetrical swing (1.0 x the measured swing) as a rung; off = the 1.27 / proj_ext2 extensions only
    proj_ext_anchor: str = "leg"         # L13-cc-extension-projections (cc06_008 ~00:28:08; cc07_003 ~00:30:54): "leg" = the built proj_ext (MSS leg) / "stop_run" (swing high before the sweep -> sweep low) / "midweek" (Wednesday's extreme, from Wednesday); the multiples are (1.27, proj_ext2), kept only where they overlap an opposing 15m .. 4h array
    proj_ext2: float = 1.62              # ... second extension: 1.62 (cc06_008) | 1.68 (cc07_003)
    daily_breaker_cap: bool = False      # new-swing-target-breaker-cap (cc06_004 ~00:29:06): the ladder ends at the nearest daily bearish breaker above (its low = the final target) unless a daily close above it exists
    adr_conv_target: bool = False        # LLT3-target-confluence-projection-adr-array (cc09_002 ~00:17:01): the proj / SD level inside an opposing 15m / 1h / 4h / D array that holds the projected ADR high (min(day low, midnight open) + ADR5) is the final target (proj_htf)
    adr_conv_pts: float = 1.0            # ... "holds" = within the array or this many ES pts of it
    adr_conv_last: int = 690             # ... not after 11:30 (minute of day)
    adr_t2_htf: bool = False             # LLT3-adr5-target-ladder (cc09_006 ~00:19:23): T2 = the nearest 1h / 4h opposing array beyond the ADR level
    adr_ext: bool = False                # ... (cc12_004 ~00:17:45) once price traded beyond the ADR level: ADR_lo + 1.27 / 1.62 x ADR5 rungs, kept within 1 pt of a 15m / 1h array
    adr_anchor: str = "day_low"          # ... the ADR low: "day_low" or "london_low" (once London is complete)
    pm_am_leg: bool = False              # LLT3-pm-measured-move-am-leg (cc10_013 ~00:02:31): a PM trade with the lunch low above the AM low adds (sweep / PM swing low) + (AM high - AM low) as a projection rung
    consol_overnight_targets: bool = False   # LLT3-consolidation-day-overnight-targets (cc10_008 ~00:16:19): on a consolidation day the only target is the nearest untaken overnight pool (London, overnight H/L, overnight 5m pivots), AM only, not after 11:00
    wide_or_draw: bool = False           # LLT3-wide-or-bias-end (cc10_010 ~00:06:15): after 10:30 a wide OR60 makes the OR60 end in the bias direction the draw (pool) - the order's final target AND the session lock (_lock_step) for the rest of the day. NEEDS a bias (htf_bias != 'off'): with the default htf_bias='off' the switch is inert (cc10_010: without a bias no target from this rule)
    wide_or_mult: float = 1.5            # ... "wide" = >= wide_or_mult x the median OR60 range of the last 20 sessions [our interpretation]
    pm_am_rb: bool = False               # LLT3-pm-target-am-rejection-block (cc10_012 ~00:04:34): PM trades: the nearest untraded AM rejection block above: body edge (array), wick tip (pool), then the AM high
    pm_launch_filter: bool = False       # LLT3-pm-reversal-launch-array-filter (cc10_013 ~00:08:50): PM: the array the AM move launched from - 4h / D / W: its near edge is the final target; 15m .. 1h: the ladder runs beyond it to the next pool
    session_obj_tf: bool = False         # LLT3-session-targets-15m-60m (cc10_014 ~00:04:18): the session lock prefers the nearest opposing 15m / 1h array (obj_<tf>) over pools; a PM trade to it is held to 15:45 (hold_to_obj)
    fvg_target_level: str = "before_edge"   # X2-pdarray-exit-at-or-inside-edge (003 ~00:53:30; 041 ~00:01:45; 049 ~00:05:37): a gap target exits "before_edge" (exit_before_pts, built) / "at_edge" (exactly at the near edge) / "deep" (at the edge, the last rung - the runner - near + fvg_deep_frac x height)
    fvg_deep_frac: float = 0.75          # ... [our interpretation] the far quarter of the gap
    pool_exit: str = "beyond"            # X2-pool-exit-at-or-before (006 ~00:33:37; 037 ~00:53:34; 063 ~00:29:41; 102 ~01:32:29): a pool exits "beyond" (pool_beyond_pts, built) / "at" (exactly) / "before" (pool_before_ticks ticks short): derives pool_beyond_pts (so an 'at' / 'before' mode REPLACES an explicit pool_beyond_pts, and the same offset reaches every engine that reads pool_beyond_pts: the pre-open / SB / sm6 pool exits)
    pool_before_ticks: int = 2
    pool_exit_fomc_before: bool = False  # ... (065 ~05:43:00) on an FOMC day the pools exit "before" whatever pool_exit says ('beyond' or 'at')
    proj_kind: bool = False              # X2-projection-target-1tick-before (012 ~00:29:40; 030 ~00:24:14): SD / measured-move / projection levels exit proj_before_pts before the level (rung kinds proj*); Trade.near_miss reports the stops just short of one
    proj_before_pts: float = 0.25
    adr_before_frac: float = 0.15        # X2-exit-buffer-before-day-extreme (cc09_007 ~00:17:04; cc12_004 ~00:18:54): the adr_target rung (kind adr) exits this share of ADR5 before the level (or at a 15m / 1h array edge inside the buffer minus exit_before_pts, the nearer to price); 0 = off (the spec default 0.15 - only acts with adr_target; study grid {0.10, 0.15, 0.20})
    partial_mode: str = ""               # X3-new-vs-experienced-partials (022 ~00:53:36; 065 ~02:34:01; 067 ~01:03:59): "" (today) / "experienced" (today) / "new" (cut at the first pool, new_first of the units at the first partial) / "terminus" (one rung at the last level) / "quarters" (X3-gradient-ladder-htf-target: quarter-point rungs of the HTF gap / pool-to-HTF range / two pools)
    new_first: float = 0.8
    exit_mode2: str = ""                 # X3-full-pull-vs-mandatory-partial (076 ~00:26:32; 092 ~01:30:11; 102 ~02:18:40): "pay_first" (the first pool rung >= 0.5) / "full_pull" (one rung at the first pool) / "hold_runner" (the final rung only, the stop never moved, out by 15:45)
    speed_skip: bool = False             # ... pay_first: the first pool is not paid when the touching bar and the bar before are both >= 1.5 x the median range and the touching bar closes beyond it (the share moves to the next rung)
    pool_milestone: float = 0.0          # X3-pool-below-untraded-htf-partial (061 ~02:19:41): a pool short of an untouched daily / weekly / monthly array takes this share (the partial), the array's near edge is the final rung; a counter-direction sweep setup below that array is rejected (x_htf_untraded); 0 = off (test 0.5)
    no_collapse_htf: bool = False        # X3-no-collapse-intermediate-pools (cc03_003 ~00:25:28; cc04_002 ~00:16:04): the last no_collapse_keep of the units rides to the untouched HTF draw
    no_collapse_keep: float = 0.2
    ladder_preset: str = ""              # X3 ladders: "004" (D13-speed-bump-ladder-004: speed bump 2/9, next level 3/9, draw 3/9, 1/9 to the next HTF array; the bump neither moves the stop nor sets break-even) / "037" (X3-037-three-unit-ladder: the old high at its price, one tick into the first bearish FVG, its far edge less a tick; thirds, (0.4, 0.4, 0.2) with news ahead)
    ladder037_ce: bool = False           # ... "037": the last third at the FVG's CE
    energy_split: bool = False           # X3-partial-size-by-energy (009 ~00:11:26): the first fraction 0.5 after a poke through the 09:30 high without a gap, 0.65 with no pool / array within energy_room_pts beyond T1
    energy_room_pts: float = 5.0
    fixed_partials: tuple = ()           # X3-five-handle-first-partial-before-draw (036 ~00:49:59; 060 ~01:14:58): partial rungs at entry + these ES pts (test (5.25, 10.0)), exact price, no target (min_draw_pts judges the draw alone)
    fixed_partial_fracs: tuple = (0.25, 0.25)

    # --- caption-gap pass: targets_partials #4/4 (digests/rulebook_gaps/management_partials_trailing_exits.md 44 .. 125, models_setups_entries.md 46 .. 147, other.md 8, session_day_week_stops_frequency.md 22, stops_sizing_scaling_in.md 28 / 70, times_sessions_macros.md 6 / 19; tp4.py; every new switch off unless noted; the gap id is the comment's first word) ---------------
    weekly_hl_rung: bool = False         # X3-layered-pool-ladder-runner (cc04_003 ~00:30:19, ~00:11:24): the prior week's high (low for a short) is a pool rung - "a little more profit at the nearest old weekly high"
    collapse_adr_frac: float = 0.0       # ... when the move from the sweep extreme to the first pool already exceeds this x ADR5 the first pool takes ALL the units [our interpretation; 0 = off, test 1.0]
    runner_frac: float = 0.0             # ... otherwise the last rung keeps this share as the runner to the farthest pool (0 = off); also the runner share of runner_htf (0.2 when 0) and consol_eq_target's runner
    capture_zone: bool = False           # X3-best-case-80-85-capture (013 ~00:30:23): the last capture_n rungs become equal rungs at avg + f x (B - avg), f = 0.85 .. 1.0 (B = the final level); Trade.capture_b = realised / (B - avg)
    capture_n: int = 3
    runner_at_half: bool = False         # X3-half-range-runner-success (cc02_003 ~00:07:06): the last rung = avg + 0.5 x (final - avg) when that lies beyond the previous rung; Trade.half_range_ok is the report flag
    runner_htf: bool = False             # X3-runner-htf-target (099 ~00:37:57; cc02_003 ~00:03:26): the final rung = the nearest 60m-or-higher pool beyond the last execution-timeframe rung, runner_htf_pts beyond it, runner_frac of the units; the runner's stop follows the previous rung
    runner_htf_pts: float = 2.0
    runner_htf_steps: bool = False       # ... the intermediate 15m pools are extra rungs taking half of the runner
    gap_speed_bump_partial: float = 0.0  # X3-gap-speed-bump-before-pool (072 ~00:28:41): a small unfilled gap (<= bump_max_pts) between price and the first pool gets a 'speed' partial of this share just past its far edge (test 0.25)
    bump_max_pts: float = 2.0
    partial_trigger: str = ""            # X3-r-multiple-partials (cc02_001 ~00:24:10; cc02_003 ~00:03:00): "r_multiple" (r_ladder = ((R, share), ...) as 'fixed' rungs at avg + R x risk, merged with the pool rungs) or the presets "cc02_001" (1R 50 %, 3R 25 %, break-even at 2R, runner to the far pool) / "cc02_003" (3R 50 %)
    r_ladder: tuple = ()
    r_be: float = 0.0                    # ... the break-even trigger in R (be_at = avg + r_be x risk; 0 = none)
    eq60_rung: bool = False              # X3-partial-60m-eq (cc08_007 ~00:17:13): a partial at the EQ of the 60m dealing range (the last confirmed 60m pivots around the price) when it lies between the entry and the final level
    eq60_frac: float = 0.25              # ... its share, taken from rung 1's
    subrange_first: bool = False         # X3-first-profit-premium-subrange (cc07_005 ~00:09:58): a discount entry in a quarter of the 60-day range: rung 1 = the nearest 1h / 4h opposing array above that quarter's EQ, the earlier rungs go [our interpretation of the 'daily consolidation quadrant']
    confluence_weight: bool = False      # X3-scaleout-skip-and-confluence (cc08_007 ~00:19:41): a rung scores +1 at an opposing array edge, +1 at a 1.27 / 1.618 extension or the 100 % measured move of the entry leg; the shares follow share x (1 + score)
    confluence_only: bool = False        # ... only rungs that score (and the final rung) stay
    void_ladder: bool = False            # X3-scale-through-void (cc01_006 ~00:24:21): a void used as the draw becomes three rungs, near edge / CE / far edge (each exit_before_pts short), a third of its share each
    mm_first: float = 0.0                # X3-mm-model-target (104 ~00:53:35): an MM-model trade takes this share (0.8) at the original consolidation's near boundary, the rest at the next pool
    fulcrum_exit: str = ""               # X3-fulcrum-exit-modes (090 ~01:32:54): trades of sd_anchor='fulcrum': "ladder" (pool + beyond, -0.5 SD, -1 SD) / "trail" (one rung at -1 SD, the FVG trail from the fill; needs a bias and no holiday-adjacent day)
    tgif_reentry_pm: bool = False        # M14-tgif-management (066 ~00:45:47): a TGIF day takes one more TGIF entry in the PM Silver-Bullet window while the week's extreme holds (tgif_exits="066": the 066 ladder, see targets.plan)
    tgif_last_hour_cover: bool = False   # ... from 15:00 a swing inside the 20 .. 30 % band sets a resting cover just short of it for everything left
    proj_breaker_multi: bool = False     # L13-multi-sd-breaker-confluence (070 ~01:04:18): B + k (B - A), k = 1 .. proj_k_max step 0.5, of every 1m / 5m breaker leg; clusters of >= 2 legs inside the HTF draw range are 'proj' rungs
    proj_k_max: float = 7.5
    lrlr_ceiling: bool = False           # L4-lrlr-ceiling (cc01_007 ~00:13:38): U = the old low a later close broke before the sweep (swing_tiers); the ladder ends at U - exit_before_pts, levels beyond it are 'hrlr' (dropped)
    lrlr_allow_beyond: bool = False
    ob_target_tod: bool = False          # A12-opposing-ob-time-of-day (cc04_003 ~00:34:17): an opposing-OB rung (kind 'ob') is paid only inside ob_pt_windows; outside it is a pause - the rung is skipped and its share moves on
    ob_pt_windows: tuple = ((600, 660), (690, 720), (900, 960))      # ... [our interpretation] 10:00-11:00, 11:30-12:00, 15:00-16:00
    consol_eq_target: bool = False       # X1-consol-sweep-target-eq (cc09_004 ~00:12:29): the sweep of a consolidation's outer edge with the daily / 4h bias that way targets the range EQ (the final rung), not the opposite extreme
    consol_eq_bars: int = 60             # ... the consolidation = the last N bars before the sweep (the spec's `consol_bars`; renamed because consol_bars (20) exists for the delivery state)
    consol_adr_frac: float = 0.35        # ... under this x ADR5 [our interpretation]
    strength_hold: bool = False          # new-strength-no-return-discount-array (105 ~00:17:00): a new high with no low inside OB1's body since the fill = "strong": the remaining non-pool rungs are dropped
    consol_no_runner: bool = False       # B17-consolidation-no-runners (048 ~01:51:24; 053 ~00:09:25): on a multi-day-range / consolidation day: ladder_fracs_slow (bulk at T1), no HTF-array rungs, no runner
    pm_ladder_am: bool = False           # M7-pm-mss-after-1300-targets (043 ~00:13:28): PM orders add the lunch high and every untaken AM swing high as rungs, then the SD projection of the MSS leg
    pm_sd_mult: float = 1.5
    same_range_t1: bool = False          # M0-target-opposite-extreme-same-range (067 ~00:18:56): the raided pool is the extreme of a session range (prev_pm / london / lunch ..): T1 = the other extreme of that range
    tf_target_cap: bool = False          # new-tf-matches-objective (cc04_002 ~00:37:27): the final rung is capped at tf_cap_pts[tf] ES pts for the run's timeframe; a T1 beyond it is rejected (needs a higher timeframe)
    tf_cap_pts: tuple = ((1, 10.0), (5, 20.0), (15, 40.0))
    void_draw: bool = False              # new-sellstop-run-before-void-fill (cc04_010 ~00:08:07): the nearest unfilled opposing void within 3 x ADR5 is the final target of a long after a sell-side sweep (not under a locked draw)
    void_rearm: bool = False             # ... a stopped-out void_draw trade re-arms its session once, on a second sweep of the same lows
    target_stage: bool = False           # OT-target-progression (099 ~00:40:55): the fixed target t1_fixed_pts steps stage_targets (10 -> 15 -> 20) after stage_weeks non-negative weeks (backtest.run); the size never changes
    stage_targets: tuple = (10.0, 15.0, 20.0)
    stage_weeks: int = 4                 # ... [our interpretation] N
    stage_drop: bool = False             # ... a negative week steps back one stage
    rr_month_gate: bool = False          # new-rr-month-gate (cc02_001 ~00:12:11): until rr_n_big winners of >= rr_big R closed this month the final-draw reward must be >= rr_big R, afterwards >= rr_relaxed
    rr_big: float = 5.0                  # ... [our interpretation] 5
    rr_n_big: int = 1
    rr_relaxed: float = 2.0
    ladder_kind: str = ""                # E8-2pct-split-experienced (cc02_003 ~00:12:32): "half_3r" = half the units at entry + 3R, half at the HTF objective (study: risk_pct 0.02, adds off)
    m1450_targets: bool = False          # T7-1450-targets (043 ~00:15:49; 075 ~01:45:16): a PM order armed 14:50-15:10 in the discount (the mirror of 'premium') of the day's range: rungs = the swing above the PM leg's EQ, the untaken 07:00 / 08:30 / 09:30-11:00 highs, the TGIF 20 % level
    m1450_mid_open: bool = True          # ... the macro extreme must also lie beyond the midnight open
    pm_carry_erase: bool = False         # T8-pm-carry-condition (029 ~01:30:37): the AM draw carries into the PM only while price has not traded back (a tick through) to the AM leg's origin after the AM extreme
    skip_balanced: bool = False          # ... a candidate level the day's closes crossed both ways is no target [our interpretation]

    # --- caption-gap pass: management_exits #1/3 (digests/rulebook_gaps/bias_htf_intermarket.md 13 / 68 / 79 / 209, day_selection_news_calendar.md 11 / 58, definitions_pd_arrays_structure.md 2 .. 196, levels_liquidity_targets.md 3 / 47 / 57 / 84, management_partials_trailing_exits.md 5 .. 19; me1.py; every new switch off unless noted; the gap id is the comment's first word) ---------------
    nwog_traverse_hold: bool = False     # BH-B14-NWOG-traverse-large-range (026 ~01:32:09): price traded from one NWOG edge to the other this session = an expansion day: no T1 partial (the whole position runs to the final rung), the final rung moves to the next pool beyond (not under a locked draw, owner #9); tag nwog_traverse
    tick_match_hold: bool = False        # BH-micro-BPR-tick-match-LOD (055 ~00:15:51): AM 3m chart, inside a BPR a later candle's low equals an earlier candle's high to the tick, then a 3m close above the retrace high = the low of the day is in: hold (the X9 time stop is skipped); tag lod_in [our interpretation]
    heavy_gauge: bool = False            # B6-untouched-premium-arrays-heavy (078 ~00:57:07; 098 ~01:06:52): the opposing arrays between the entry and the stop; a print past one's CE = a partial of heavy_scale (once); none touched by T1 = tag 'heavy' and the T1 share is held (moved to the next rung)
    heavy_scale: float = 0.33
    no_lunch_retrace_hold: bool = False  # T9-strong-am-no-lunch-retrace (cc10_012 ~00:11:54): a strong AM rally from the day's low whose 12:00-13:00 low retraces < lunch_retr_max of the AM leg keeps the AM position past the 12:00 close (stop to the lunch low, out at 15:50 or the target); else it closes at 13:00. The PM-entry extension to the last hour is NOT built
    lunch_retr_max: float = 0.3          # ... [our interpretation] 25-30 %
    hold_through_0830: bool = False      # N5-hold-through-0830 (032 ~00:06:56; 091 ~00:22:26): the experienced version - a pre-09:30 position (incl. Ma Deuce / SB London) is held through the 08:30 release, the exit being a resting limit at the pool; jobs / CPI days stay excluded. PRE8 orders still never fill on or after the 08:30 bar. Default OFF (flat at 08:29, pre_flat_0830) because owner directive "No 08:30 entries; pre-09:30 setups are test-only switches" (owner_directives.md line 16) wins over the experienced-version rule; listed under the owner questions
    no_entry_0825: bool = True           # ... no pre-09:30 order fills 08:25-08:30 on a day with a 08:30 release (main engine; the experienced hold_through_0830 lifts it) [spec default on: the existing intent of pre_flat_0830]
    thu_cap: bool = False                # N10-thursday-caps-week (cc08_001 ~00:21:59): a Thursday position entered before 09:30 is closed at 10:00; a Thursday 09:30-12:00 new weekly extreme into a daily array blocks entries in its direction that day (x_thu_week_ext) [our interpretation]
    bpr_limit: str = "mt_body_close_abort"   # A11-bpr-retrace-allowance (001 ~20:43; 012 ~22:34; 024 ~6:18; 026 ~1:05:53; 065 ~4:28): how deep a return into the BPR under the entry may go (needs bpr_abort or bpr_rule): "mt_body_close_abort" (the built rule, 065) / "no_reentry" (001) / "ce_touch" (012) / "mt_warn_far_exit" (026) / "far_edge" (024: a trade-through of the far edge)
    breaker_mt_test: str = "close"       # A13-breaker-mt-trade-test (018 ~1:56): "close" (a body close below the breaker MT, the built rule) / "trade" (a print below MT - mohawk_ticks)
    far_half_no_adds: bool = False       # A5-partial-fill-strength-read (007 ~10:00 ...): no adds once price traded into the far half (past the CE) of the newest gap formed after the entry; tag strength_read
    ce_exit: str = "close"               # A5-quadrants-any-gap-ladder (030 ~58:34; X8): "close" (the built ce_hold exit: a body close under the CE) / "trade" (any print under the CE after the fill)
    fvg_bpr_backstop: bool = False       # A5-reclaimed-fvg-full-revisit (026 ~1:08:48): an entry FVG with a BPR behind it (overlapping or abutting its far edge within a tick) does not exit on the FVG far-edge rules (X6 abort, X9c); the BPR midpoint body close (A11) is the invalidation
    vi_mid_exit: bool = False            # A9-broken-vi-retrace-midpoint (027 ~16:40): after a VI entry, a touch of the midpoint of the retraced leg must reject: no close back beyond it within vi_mid_bars bars = exit
    vi_mid_bars: int = 2                 # ... [our interpretation] immediately = 2 one-minute bars
    rip_through: bool = False            # A8-rip-through-ce-signature (031 ~51:52): a bar through the CE of the opposing gap ahead that continues through the far edge = 'rip'; >= 3 bars within 1 pt of the CE = 'stall': no adds, a partial of stall_partial
    stall_partial: float = 0.5
    fvg_full_fill_void: bool = False     # X9-entry-fvg-immediate-rejection (013 ~17:55): a trade through the entry FVG's far edge voids the idea: the pending order is cancelled / the position exits at once (the stop-1-tick-beyond-the-forming-candle part is not built)
    resistance_def: str = "swings"       # L4-resistance-is-delivery-speed (036 ~1:21:17): "swings" (the 1st-pass proxy: old highs / lows in the path) / "speed" (2023: the first rung reached within resist_speed_bars bars of the fill = low resistance); tags Trade.resist_speed; with resistance_mode low_full / both a fast run is pulled in full
    resist_speed_bars: int = 3           # ... [our interpretation] 2-3 bars (named so: speed_bars is the M1.3 sweep speed check)
    ifvg_fail_tf: int = 0                # A8-ifvg-15m-body-failure (084 ~12:08): the IFVG entry fails on a body close back through the FVG on this timeframe (15 = ICT; 0 = the engine's own bars, the built lvx rule)
    refusal_breakaway: bool = False      # A6-breakaway-by-refusal (090 ~2:03:43): two armed adds that expired unfilled = the newest FVG is a breakaway gap: no ladder_trail FVG trailing, hold the runner
    iof_intraday_exit: bool = False      # B6-intraday-iof (075 ~1:21:58): the open of the newest down-close candle after the fill is the support; a body close below it exits
    iof_strict: bool = False             # B6-intraday-iof (075 ~1:21:58) [our interpretation of the Rule]: with iof_intraday_exit - each down-close support must lead to a new short-term high within iof_tol_bars bars, and a low taken under the support candle must reverse (close back above it) within iof_tol_bars bars, else the IOF is no longer bullish: exit
    iof_tol_bars: int = 3                # ... the 1-3 bar reversal tolerance [our interpretation]
    iof_min_body_ticks: int = 0          # ... a down-close candle counts as a support only with a body of this many ticks (0 = any)
    rip_wick_mult: float = 0.0           # A8-rip-through-ce-signature (031 ~51:52): > 0 = a large upper wick (>= this x the median range of the 20 bars before it) in the path is a rip / stall object like an opposing FVG [our interpretation of 'old FVG or large wick in the path']
    pos_switch_frac: float = 0.5         # new-position-trade-grading-fib (cc05_018 ~16:20): SPEC ONLY - the switch from the 40-day to the 20-day extreme trail (me1.pos_trail); no multi-day position engine exists yet
    run_through_bars: int = 0            # A2-quick-run-through (033 ~00:51:37): a rung that does not run > run_through_ticks beyond within this many bars of its touch (the touch bar counts) is 'stalled' (tag rt_stall, stall_at); a later body close back through it exits the rest (0 = off, test 1 / 2 / 3)
    run_through_ticks: float = 2.0
    sd_time_roll: bool = False           # L12-sd-step-to-time-window (008 ~00:06:53): SD rungs before sd_window[0] are not exits (reaching one rolls to the next SD level); inside the window the first SD level closed beyond is the final exit
    sd_window: tuple = (600, 720)        # ... [our interpretation] the index window = AM 10:00-12:00 (T12)
    hold_reached: bool = False           # L14-hold-above-reached-objective (015 ~00:28:03): after a rung is taken the next draw holds only while price holds it - a hold_tf-minute body close back through it exits the rest and the session slot is done
    hold_tf: int = 5
    sd_body_hold: bool = False           # L12-bodies-hold-sd-continuation (070 ~00:52:10): the partial of a reached SD rung is deferred while the 5m bodies stay beyond it; a 5m body close back through it takes the partial and arms the body trail
    best_case_limit: bool = False        # X2-best-case-resting-limit (009 ~00:01:06; cc10_008 ~00:14:20): the last rung O is not an exit: best_case_bulk of the units go at market once price prints beyond O; with momentum the rest rests at O + best_case_mult x (O - avg), else it goes at the bar's close
    best_case_mult: float = 1.0
    best_case_bulk: float = 0.65
    exit_fill: str = "touch"             # E1-manual-touch-exits (026 ~22:05; 037 ~54:03): when a rung/target counts as hit: "touch" (the built rule), "limit_through" (a resting limit: 1 tick through), "touch_1tick" (a manual exit at market within a tick, filled at the level minus exit_slip_ticks)
    exit_slip_ticks: int = 1
    be_mode: str = "partial"             # X4-be-vi-then-new-ssl / X4-be-without-partials / D14-be-after-adr-fraction: "partial" (be_on, the built rule) / "vi_then_new_ssl" (042 ~52:21) / "through_opposing_fvg" (089 ~8:35) / "adr_frac" (cc08_007 ~14:14); any other mode switches be_on off
    be_adr: float = 0.4                  # ... adr_frac: open profit >= be_adr x ADR5 (grid 0.4 / 0.5)
    be_cap_htf: bool = False             # X4-be-plus-cap-htf (105 ~00:10:50): partial 1 = BE + pad capped under the HTF entry array's top (no FVG trailing); partial 2 = 1 tick under the CE of the highest wick; partial 3 = the HTF array's top
    runner_stop: str = ""                # X5-runner-stop-half-open-profit (036 ~01:01:33; 065 ~02:56:01): after the bulk partial the runner's stop, once, no trailing: "leg_eq" (max(entry, EQ of sweep-low..best - 1 tick)) / "half_profit" (entry + half the open profit)
    runner_eq_after: float = 0.75        # ... the closed ladder fraction that counts as 'the bulk'
    day_mode_auto: bool = False          # X5-day-trade-stop-no-trail (064 ~01:45:14): day mode (the 08:30 open / wick-CE stop, no trail) picked per order: the bias agrees, today's range < 0.5 x ADR5 and the HTF draw >= 0.75 x ADR5 away [our interpretation]
    day_mode_size: float = 0.5           # ... the size multiplier of a day-mode order
    event_eve_lock: bool = False         # X5-event-tight-lock-020 (020 ~00:09:40): the day before FOMC / CPI / jobs, bulk off: the stop goes just over the newest fresh same-direction gap under price, no trailing
    trail_confirm: bool = False          # X5-trail-after-protected-gap-confirmed (003 ~00:41:35; 062 ~00:39:12): the stop stays initial until a new gap beyond the entry gap P forms or a new extreme past the post-gap swing prints with P partly unfilled; then it goes under P. A trade through P first voids it

    # --- caption-gap pass: management_exits #2/3 (digests/rulebook_gaps/management_partials_trailing_exits.md 20 .. 108; me2.py; every new switch off unless noted; the gap id is the comment's first word) ---------------
    pool_lock_after: float = 0.8         # X5-tight-stop-under-swept-pool-near-target (003 ~01:09:14; 021 ~00:44:11): the closed share (about 80-90 %) after which the last pool run before the final rung locks the stop
    pool_lock_pts: float = 1.5           # ... the stop sits this many ES pts under the swept pool (spec default 1.5; 0 = off; review fix: the default follows the spec) and the idea gets no re-entry after a stop
    pool_lock_day_done: bool = False     # ... a final-rung fill ends the day (X12)
    trail_after_pool: bool = False       # X5-no-trail-into-new-inefficiency (022 ~01:12:22; 067 ~01:19:24): after the add cutoff (price past the leg's 50 % line) no FVG / swing trail until the targeted pool has run
    raise_on_vi: bool = False            # X5-raise-stop-conditional-structure (009 ~00:07:10): a bar that retests the nearest VI under the entry and closes above its top lifts the stop to the VI low - 1 tick
    raise_on_sth_break: bool = False     # ... (018 ~00:01:38): the short-term high above the entry breaks: the stop to the breaker zone's low - 1 tick (the entry array's bottom with no breaker [our interpretation])
    raise_need_5m_fvg: bool = False      # ... the break must leave a 5m gap
    trail_swing_at_array: bool = False   # X5-trail-swing-low-at-intermediate-level (060 ~00:54:30): a non-final array rung fills (incl. NDOG / ORG gap levels): the stop under the latest 1m swing low, the last unit held
    ob_retests: int = 0                  # X5-ob-open-after-retests (085 ~00:17:52): this many retests of the entry OB's open (each followed by a higher bar) lift the stop to the open - 1 tick and freeze it (0 = off; test 3)
    trail_wick_gate: str = ""            # X5-roll-after-wick-ce-cleared (085 ~00:26:11, ~00:31:34): "" / "trade" / "close" - no trail (BE excepted) until a bar's high (close) is above the CE of the nearest overhead upper wick (a wick >= 25 % of the bar's range [our interpretation])
    ob_stop_to_mt_after_run: bool = False  # X5-stop-to-ob-mt-after-run (cc04_003 ~00:02:00): after an OB entry has run away (best - avg >= 2 x the OB body, or a pivot high over the validating candle) the stop goes to the OB MT (mt_mode) - the pad
    htf_bank: float = 0.0                # X3-htf-target-bank-partial (050 ~00:09:50; 099 ~00:22:50): the share banked when price trades into the HTF (daily / weekly) draw array, stop to BE + pad, no adds, no counter entries inside that array (0 = off; test 0.5)
    rde_partials: bool = False           # X3-running-down-equity-trigger (063 ~00:26:23; 064 ~01:03:42): once progress >= rde_arm of the way to the final rung, a tranche of rde_frac at each short-term high that a later bar exceeds
    rde_arm: float = 0.75
    rde_frac: float = 0.2
    peel_singles: bool = False           # X3-020-runner-peel-singles (020 ~00:10:25 ..): after >= 75 % is closed and above the target NWOG's CE: one lot per bar at an REH poke / a higher high / halfway to the gap top; the last unit gets a pivot-low stop
    pm_macro_runner: bool = False        # X3-027-pm-runner-macro (027 ~00:40:28): a PM trade's first partial lifts the stop to +1 pt, the last unit is held to 15:50 (the 15:45-15:50 macro, newscal.macro_wins)
    hh_low_hold: bool = False            # X3-runner-swing-low-must-hold (027 ~00:43:52): after the first partial, the swing low between a pivot high and the new high that takes it out must hold; a trade under it closes hh_low_frac of the rest
    hh_low_frac: float = 1.0
    marginal_ext_warn: bool = False      # X3-marginal-lower-lows-warning (046 ~01:00:39): bars that make a new session extreme by < marginal_pts and close back inside it, marginal_n times before the final rung = no adds
    marginal_pts: float = 1.0
    marginal_n: int = 2                  # ... [our interpretation]
    marginal_exit: bool = False          # ... and the rest closed
    stall_exits: bool = False            # X3-runner-stall-exits (003 ~01:17:52): >= 75 % closed and stall_bars bars without a new high: a trade into the last down-close body = 1 unit off; a poke over a relative equal high that closes back under it = the rest
    stall_bars: int = 10                 # ... [our interpretation of 'lethargic']; evaluated on every bar (a new extreme switches the exits off again)
    stall_reh_against: bool = False      # ... (b) read 'against the trade' literally: a poke under a relative equal LOW (side space) that closes back above it closes the rest ("stall_rel"); off = a poke over a relative equal high that closes back under it (the spec's test text)
    wick_ce_close_test: bool = False     # X3-nfp-wick-ce-ladder-close-test (105 ~00:09:03, ~00:23:32): a wick-CE first rung is a 10 % rung, BE + pad after it; a 5m close above W then a 5m close at or under it takes 30 % to fund the trade
    adr_closed_min: float = 0.0          # L16-adr5-60-80-closed (cc08_007 ~00:17:25): at the ADR5 projection from the day's low at least this share must be closed (any time of day; 0 = off; test 0.7)
    ote_leave_bars: int = 0              # M13-ote-leave-discount-fast (cc01_004 ~00:50:18): an OTE entry with no close over the band's 62 % line after this many bars loses half (0 = off; test 3)
    three_array_mode: str = ""           # X7-three-array-exit-trigger (026 ~00:28:00; 045 ~01:57:01; 078 ~01:03:02; 105 ~01:24:00): "" / "trade" (a low under A3's far edge = all) / "close" (a close under the A3 level = pd3_close_frac) / "into" (a low into A3's body = all)
    pd3_close_frac: float = 0.5
    pd3_near_pts: float = 0.0            # ... A3 within this many ES pts of A2: the trigger moves to A2 (078; 0 = off)
    held_hi_action: str = ""             # X8-hold-above-broken-session-highs (009 ~00:17:38): "" / "tighten" (stop under the bar's low) / "partial" (half the rest) when a 1m close falls back under the 09:30 high / the swing high it broke
    gap_q_hold: bool = False             # X8-nwog-ce-pullback-hold (020 ~00:09:23): after the NWOG CE rung, a trade under the gap's lower quarter closes the rest
    ref_speed_check: bool = False        # X8-fast-through-next-reference (006 ~00:53:30; 022 ~01:40:24): speed check at each reference (rung / VI): a slow break pares speed_pare before T1, closes the rest after T1
    speed_k: float = 1.5                 # ... 'ok' when the breaking bar's range >= speed_k x the median of the last 20 ranges, or a gap is left over the reference
    ref_speed_bars: int = 3              # ... a close back under the reference within this many bars = slow (named so: speed_bars is the M1.3 sweep speed check)
    speed_pare: float = 0.5
    opp_tear_check: bool = False         # X8-opposing-array-torn-through (027 ~00:31:40): an opposing gap touched must be torn through to its CE within the touch bar or the next, else no adds and a warn count
    edge_bump_add: bool = False          # X8-broken-fvg-edge-bump-once (071 ~00:30:16): the first retrace to the broken gap's edge may arm an add
    edge_bump_guard: bool = False        # ... the second bump = no more adds and the ladder levels frozen
    late_fvg_flip: bool = False          # X8-late-day-fvg-lost-hod-in (027 ~00:57:44): from 15:00 the small bearish gap after the session high: reclaimed = support, then lost = the runner is out; no entries in the direction while price is under it
    sister_breaker_hold: bool = False    # X8-sister-index-breaker-hold (085 ~00:19:11): a sister-index close under its breaker of the same leg adds 1 to the position's warn count (feeds three_array_mode 'trade')
    stall_at_htf: bool = False           # X8-profitable-stall-exit (cc07_007 ~00:22:33): Mon / Tue week range >= 1.5 x ADR5, a profitable trade inside a daily-or-higher array with no new extreme for stall_at_htf_bars bars closes; no same-direction trade next session = reversal_watch
    stall_at_htf_bars: int = 30          # ... [our interpretation]
    chop_close: bool = False             # X9-lethargic-or-choppy-trade (022 ~01:52:48; cc03_003 ~00:13:49): the intraday Chop detector turning on while a position is open closes it
    after_chop_exit: str = "end_session"  # ... "end_session" (022: the session is done) / "reentry_allowed" (cc03_003: a re-entry at the half risk of X13b)
    upclose_pair_guard: bool = False     # X9-071-move-away-from-up-close-pair (071 ~00:33:10): after a bar trades through the last same-colour candle pair's open, neither the break bar nor the next two making a new extreme = no adds
    fulcrum_speed_bars: int = 0          # X9-speed-after-fulcrum-break (090 ~01:31:35): sd_anchor 'fulcrum' - -0.5 SD must print within this many bars of the fulcrum pool break (no close back under it), else the first rung's share closes and the stop goes under the break bar (0 = off; test 5)
    breaker_far_partial: float = 0.0     # A13-breaker-far-edge-partial (078 ~00:55:36): the first trade through the breaker's far edge (BH of a bearish breaker) takes this share (0.5 / 0.25), no adds, the stop stays
    small_fvg_linger: int = 0            # new-small-fvg-last-line (105 ~00:37:35): after T1 more than this many 5m bars inside the latest 5m gap (or a 5m close under it) = no adds and a stop cap at the HTF entry array's high (0 = off; test 2)
    urgency_runner: bool = False         # new-no-down-close-urgency (021 ~00:43:53): T1 with no down-close candle since the fill: most of the position off (runner_frac, 0.2 if 0, stays), the stop urgency_stop_pts under the close, the farther target kept
    urgency_stop_pts: float = 1.0
    urgency_bulk: bool = False           # new-no-down-close-urgency review fix: with only two rungs (no rung between T1 and the last to shrink) the T1 fill also closes everything above the runner share at once (the first build's behaviour; the spec has no such exit - owner question)

    # --- caption-gap pass: management_exits #3/3 (digests/rulebook_gaps/management_partials_trailing_exits.md 109 .. 132, models_setups_entries.md 57 / 65 / 118 / 128 / 199, session_day_week_stops_frequency.md 1 .. 30, stops_sizing_scaling_in.md 41 / 42, times_sessions_macros.md 8 / 16 / 25; me3.py; every new switch off unless noted; the gap id is the comment's first word) ---------------
    implied_range: bool = False          # new-implied-range-behaviour (045 ~03:02:00): the range sweep extreme .. final level: no X9 time stop between its 25 % and 75 % lines; a trade under the latest pivot low formed above 75 % / under the last bullish OB body halves the position (ir_top_raid)
    laggard_mult: float = 1.0            # new-laggard-slow-delivery (090 ~01:49:28): a trade taken in the index moving in sympathy after the leader reached its draw runs time_stop_min / meander_bars x this (test 2.0); tag laggard
    vol_div_exit: bool = False           # new-volume-divergence-exit (cc10_006 ~00:06:00; BOND futures volume, a test switch - not for SPY / ES without validation): a new session extreme on less than vol_div_ratio x the volume of the bar behind the prior extreme = half off
    vol_div_ratio: float = 1.0
    day_mode_no_am_exit: bool = True     # D16-am-trade-held-into-pm (064 ~01:40:54; 026 ~01:32:26): a day-mode position (trade_type "day" / day_mode_auto) is exempt from am_exit (and the pending noon guard); flat by the session flat time. DEFAULT ON (the spec: day mode itself is the exemption); False restores the old 12:00 close of a day-mode trade
    am_runner_hold_to: int = 0           # ... after >= 85 % off at 12:00 at most 2 lots stay on the current stop and close at this minute (900 = 15:00; 085 ~00:32:13; 0 = off)
    explosive_runner: bool = False       # D16-big-range-day-runner-past-noon (cc09_006 ~00:12:51; cc10_014 ~00:03:28): an explosive day (range >= ADR5 by 10:00 or >= explosive_frac x ADR5 by 11:00, the extreme made within the last 15 bars) keeps its runner past 12:00 to explosive_until
    explosive_frac: float = 1.25         # [our threshold]
    explosive_until: int = 900
    last_hour_target_done: bool = False  # X11-last-hour-target-hit-done (006 ~00:41:27): from 15:00 a fill of any rung closes everything left at that rung (lh_target); pm_done_by stays the 15:00-deadline variant (NOT ICT's 006 rule)
    pm_two_stage: bool = False           # X11-two-stage-pm-delivery (cc10_014 ~00:04:52): a PM trade on a two-session day keeps its time stop and stall exits suspended until 15:00 while the far (non-pool) rung is unhit and the close holds above the entry array's far edge
    cc_day_exit: int = 0                 # X10-cc-day-trade-exit-1400 (cc03_001 ~00:17:22): a Core Content model trade (cc_* tags) is closed at the first bar close at or after this minute and no cc order is armed from then on (840 = 14:00; 0 = off)
    london_tod_partials: bool = False    # X10-london-time-of-day-scaleouts (cc08_001 ~00:18:01; cc08_007 ~00:18:59): a London position takes london_tod_frac at 04:55, again at 06:55 and on the first new extreme in 10:00-11:00
    london_tod_frac: float = 0.25
    scalp_mode: str = ""                 # new-scalp-fixed-1to1-2h (cc09_003 ~00:04:51; cc09_006 ~00:03:58): "fixed_1to1" - a scalp order (sloppy_mode "scalp" / N8 scalp day) has ONE rung at the entry + its risk, no BE / trail / adds, and a time exit scalp_max_min after the fill
    scalp_max_min: int = 120
    abort_blocks_side: bool = False      # new-no-close-to-reenter (085 ~00:13:50): an abort-set exit (abort, ce_close, breaker_mt, pd3*, chop_close, htf_stall, time, slow_ref, lost_hi, hh_low, stall_reh) abandons the direction for the leg: no same-direction order until a new MSS forms after the close; no reentry_half
    stop_ack_sec: int = 0                # new-no-working-stop-close-exit (093 ~00:14:12; live / paper only): no stop acknowledgement within this many seconds of the entry fill = the position is unprotected (the ladder collapses to one 100 % rung at rung 1; an adverse close exits at market; 0 = off, test 10)
    recovery_exit: str = ""              # new-drawdown-recovery-exit (cc02_005 ~00:11:33): a re-entry after a loss: "new" = close everything once the open profit covers the unrecovered loss and stand aside; "experienced" = stop to +2R - 1 tick at +2R, one rung at +3R
    open_reclaim_runner: bool = False    # T13-reclaim-0930-open-expansion (055 ~00:21:00): a close over the 09:30 open after the session low formed under it = the day is expanding: the ladder's last fraction is kept as a runner, the breakeven waits for the next rung
    reentry_breakaway: bool = False      # new-reentry-after-breakaway-fill (062 ~00:38:24): a loss whose breakaway entry gap filled completely re-enters only after price reached the HTF level / prior FVG, then a new MSS + FVG (half risk)
    ote_fail_ts: bool = False            # M12-ote-failure-turtle-soup (cc01_004 ~00:45:27): an OTE entry stopped under a prior low arms a turtle-soup buy at that low (a close back above within ts_back_bars), half risk
    reentry_mode: str = ""               # X13-reentry-mechanics (cc02_005 ~00:04:02): "cc_ob" - the loss re-entry order is the next CC-validated down-close candle: a limit at its high (reentry_cc_entry "high") or open, the stop under its whole low, half risk
    reentry_cc_entry: str = "high"
    lc_second_swipe: bool = False        # new-london-close-second-swipe-reentry (cc09_005 ~00:34:08): a stopped AM trade whose sweep extreme sat in an HTF array: a second sweep of it inside the same array in 10:00-12:00 arms one more try (T3 lc_reentry machinery), half risk
    lost_side_scope: str = "day"         # X13-am-fail-no-reverse-pm-reset (001 ~00:48:43): with reverse_after_loss off, "session" lets the lost-side block lapse at the PM reset (pm_reset_t) instead of lasting the day
    am_idea_fail: bool = False           # ... the AM idea also fails when price runs the opposite session / pre-market pool with displacement before any fill: the AM is done, a pending AM order is cancelled
    pm_reset_t: int = 810                # ... the PM reset minute (13:30; 001 says 14:00 = 840)
    reentry_count_max: int = 1           # D18-reentry-count-max-2 (cc02_005 ~00:13:41): same-direction loss re-entries per session, each at reentry_risk_mult ** n (the spec's name reentry_max is the turtle-soup re-entry cap since setups_models #7/7); test 2
    reentry_ob_stop: str = "mt"          # ... "full" = the re-entry stop below the whole OB (the built reentry_stop "ob_low" order)
    runner_stop_no_reentry: bool = False  # N3-021-citation-misread (021 ~00:44:08): a runner stopped after >= runner_frac_done of the units were banked ends the move (no win / trail-win re-entry); the final rung ends the session and its Silver Bullet key
    runner_frac_done: float = 0.75
    chop_scalp_pts: float = 0.0          # L15-chop-micro-scalps (010 ~01:15:51): with sloppy_mode "scalp" the scalp's only exit is the nearest pool within this many pts, which is also its minimum room (test 2.5)
    chop_scalp_max: int = 2
    chop_scalp_day_pts: float = 5.0
    session_fail_flatten: bool = False   # X7-three-failures-flatten-open-trade (044 ~01:54:41): the third failed array of the session closes the open position at the bar close (pd3_session), cancels orders, ends the family and its SB key
    pd3_pm_window: bool = False          # ... after that the PM window is 13:45-14:30
    new_day_stops: bool = True           # X14-new-trader-stop-when-day-positive (065 ~04:16; 102 ~01:51:30): trader_mode "new" implies it (default ON; False = the old meaning of "new"): stop once the day is net positive; AM or PM, not both; a losing AM is not recovered in the PM (recovery is experienced-only: with trader_mode "experienced" nothing blocks the PM, so there is no separate switch)
    pm_after_am_win: str = "off"         # ... experienced: "draw_open" = a PM entry after an AM win only while the day's HTF draw is untouched (056 ~08:19)
    beginner_template: bool = False      # X14-beginner-template-numbers (095 ~00:47:08): preset - 1 contract, one setup, a single exit at beginner_target_pts, the stop at most 12 handles (max_stop_pts), trader_mode "new" with new_day_stops
    beginner_target_pts: float = 12.5
    conflicted_mode: str = "off"         # X14-conflicted-htf-one-entry (091 ~00:10:44): a conflicted HTF day (both sides valid / inside a daily BISI-SIBI): "skip" / "one" (one entry then done) / "one_win" (done after the first win)
    late_week_flat: bool = False         # new-late-week-close-flat (cc02_005 ~00:08:05): a recovery re-entry that brings the week back to >= 0 on Thu / Fri or from late_flat_t is closed there and the week is done
    late_flat_t: int = 900               # [our interpretation: 15:00]
    recover_trail: bool = False          # ... otherwise the stop trails to the price where the week's P&L is 0
    abort_mode: str = "full"             # E7-reduce-size (046 ~01:33:39): "half" - the confirmed X6 abort closes abort_frac of the units, the stop stays, no adds; a second confirmation closes the rest
    abort_frac: float = 0.5
    offside_flip: bool = False           # X8-offside-flip (085 ~00:14:05): an X8e offside close reverses at the next open with the same units (stop under the reaction bodies / the defending wick CE, nearest pool), overriding the no-reversal lock once
    lh_pool_timing: bool = False         # T10-1550-pool-timing (027 ~00:49:36; 056 ~00:19:28): last-hour pool rung before 15:50 = all but lh_keep_frac off + BE; from 15:50 the runner (lh_keep_frac) goes lh_late_ext_pts beyond the pool; the MOC target before 15:45 ends the LH slot
    lh_keep_frac: float = 0.1
    lh_late_ext_pts: float = 3.0         # [027 example]
    am_exit_trend_hold: bool = False     # T8-lunch-trending-days (cc10_013 ~00:16:58): on a trend day an open position in the trend direction skips the 12:00 am_exit and keeps its ladder / trail to the session close
    pre_hold_open: bool = False          # new-hold-pre0930-through-open (105 ~00:39:20): a pre-09:30 position held through 09:30: funded = held (tag risk_0930_sweep on a drift into the open), unfunded and flagged = closed at 09:29
    # --- Caption-gap pass, package news_calendar_times#1/1 (digests/rulebook_gaps; nct2.py) ------------------------------------------------------------------------------------------------
    pre_news_coil: bool = False          # BH-consolidation-near-highs-before-news (075 ~01:37:16): weekly bias up + a tight overnight range (< 0.5 x ADR5) with its high within 0.25 x ADR5 of the week high on an 08:30 day: no shorts before the release nor until a bearish MSS after it (longs for a bearish week) [our interpretation of "tight"]
    nfp_both_sides: bool = False         # N1-nfp-both-sides-macro (073 ~00:13:15): jobs day - entries only after both post-release news-range pools were traded through by a tick, then only toward the side off the second pool; nothing after 11:10 unless both were taken by then
    nfp_macro_only: bool = False         # ... with this the entries also have to fall in 09:50-10:10 / 10:00-11:00 / 10:50-11:10 (use with nfp_day_from=590) [our interpretation: the macro gating as a hard rule]
    pre_0900_no_news: bool = False       # N5-soft-bias-pre-open (007 ~00:11:21; 019 ~00:07:57): pre_0900 (09:00-09:29) only on days without an 08:30 release
    pre_open_bnb: bool = False           # N5-soft-bias-pre-open (experienced; 007 ~14:35): 08:00-09:00 sweep of a pre-market REL into an HTF discount array, buy a 1m bullish OB that holds, target the nearest short-term high, flat by 09:30 [our interpretation]
    cpi_from: int = 0                    # N4-cpi-day-new-traders (030 ~00:07:13; ~42:21): CPI day - no entry before this minute (0 = off; test 600)
    two_driver_mode: str = "off"         # N5-two-driver-session (100 ~01:10:53): 08:30 + 10:00 releases in the NY AM: "tag" / "wait2" (nothing before the 10:00 dealing range is made) / "skip" (the AM family)
    multi_release: str = "off"           # N5-multi-release-count (cc08_006 ~00:07:04): releases in 08:30-11:00: tags rel0_wildcard / rel1 / rel2plus; "skip" the AM on rel2plus, "half" halves its risk
    news_seq_study: bool = False         # N6-both-pools-news (064 ~00:30:16): study / tag only - the pools marked before the release and the order they are taken in
    news_trend_side: bool = False        # N6-news-runs-trailed-stops (065 ~04:11:02): a release day with a daily bias: after the news range only the bias side, and only when the range's counter-trend extreme swept a pool
    kz_release_tag: bool = False         # DS2-killzone-news-manipulation-time (cc09_008 ~00:01:46): tag kz_release_extreme - the day's counter-bias extreme formed within 60 minutes after a release in the kill zone
    fomc_stage_study: bool = False       # N3-fomc-two-stage (021 ~00:39:02): label an FOMC (and jobs) day's second stage A (reversal through the first leg's origin) / B (retrace into the first-leg FVG, then a new first-leg extreme)
    fomc_minutes_mode: str = "allow"     # N3-fomc-minutes (082 ~00:04:18; cc10_008): FOMC minutes day (14:00): "allow" (normal day) / "block" (the PM is blocked like an FOMC day) / "pm_only" (no AM)
    fomc_end: int = 0                    # N3-fomc-move-ends-1500 (cc08_002 ~00:09:56): 0 = off (test 900) - from this minute no entry in the direction of the 14:00-15:00 FOMC move
    fomc_end_min_pts: float = 5.0        # ... [our interpretation] the move must be at least this many points
    pre_fomc_week_light: bool = False    # N3-fomc-week-mon-wed (094 ~00:01:48): Monday of FOMC week until Wednesday 14:00 - reduced size and no pyramiding
    pre_fomc_week_mult: float = 0.5
    pre_fomc_week_smt: bool = False      # ... optional: the partner index must have swept the same side (needs a partner)
    post_fomc_am: str = "open"           # N3-post-fomc-thu-fri (094 ~00:07:09 vs 095 ~51:27): the AM after FOMC: "open" / "skip" / "symmetry" (the partner index must break the same side of the 09:30-09:45 range)
    fomc_whipsaw_skip: str = "off"       # N3-fomc-whipsaw-skip-london (cc08_006 ~00:04:37): the day after an FOMC whipsaw (both sides of the 14:00 price by fomc_whip_frac x ADR5, or a range > 2 x ADR5): "london" skips the London windows, "am" the NY AM too
    fomc_whip_frac: float = 0.5          # [our interpretation]
    nfp_wed_cutoff: int = 660            # N2-nfp-wed-after-11 (101 ~01:29:18): NFP week Wednesday - no entry from this minute (the PM stays blocked); test 720
    event_eve_noon: bool = False         # X10-pre-nfp-noon-exit (050 ~00:52:31): the eve of NFP / CPI / FOMC, at 11:50 with >= 2 targets hit and price near the far edge of the daily FVG: close half of what is left
    news_sweep_min: int = 0              # B4-prefer-calendar-driven-manipulation (cc12_003 ~00:25:39): 0 = off; tag news_sweep when the sweep extreme fell within this many minutes after a release
    am_search_minutes: int = 0           # new-am-search-timebox-60min (042 ~00:05:55): 0 = off (test 60 / 90) - no AM fill within this many minutes of 09:30: cancel and stop the AM
    am_search_sb: str = "exempt"         # ... "exempt": the Silver Bullet window stays open / "include": it ends with the box
    macro_fail_windows: str = "am"       # N9-macro-failure-any-macro (073 ~00:35:33): "am" (the two AM macros) / "all" (also 11:50, 13:30, 14:50, 15:15)
    macro_fail_scope: str = "session"    # ... "session" / "day" (maybe even that trading day)
    macro_gate_set: tuple = ()           # T7-macro-start-only-all (044 ~00:56:58; 046): the macro windows ("0950", "1050", "1150", "1330", "1450", "1515") the macro_gate / macro_only tests use; () = every window as before
    macro_trend_off: bool = False        # T7-no-macro-trending (025 ~00:59:10): on a one-sided trending day (no retrace to the running session EQ after 10:00) the macro gate is waived
    lunch_raid: str = "off"              # T8-lunch-raid-target (025 ~01:01:51; 064 ~01:46:02; 075): the lunch pool L - "recent" (last swing against the AM move before noon) / "am_low" (the AM extreme before 11:00) / "post_news" (the first swing after the 08:30 release) / "first_of"
    lunch_raid_wait: bool = False        # ... no PM entry until L traded a tick through or lunch_raid_by
    lunch_raid_by: int = 825             # 13:45
    lunch_trail_guard: bool = False      # ... an AM trade's trailed stop may not sit just beyond L
    lunch_by_speed: bool = False         # T8-lunch-length-am-speed (cc10_012 ~00:02:56): fast AM -> PM from lunch_fast_pm; lethargic AM -> no AM entries after 11:00 and PM from lunch_slow_pm
    am_fast_k: float = 0.6               # [our interpretation] 09:30-11:00 range >= 0.6 x ADR5
    am_slow_k: float = 0.3               # < 0.3 x ADR5
    lunch_fast_pm: int = 780
    lunch_slow_pm: int = 840
    pm_array_from: int = 0               # T9-pm-start-time (019 ~00:20:37): 0 = off (test 800 / 810 / 840) - the PM entry array must have formed at or after this minute
    pm_1400_disp: bool = False           # ... PM setups between 13:30 and 14:00 are skipped; from 14:00 the MSS leg must show displacement
    am_session: str = "default"          # T5-am-session-to-noon (044 ~00:55:47; 073): "0830_1200" = the AM from 08:30 to 12:00
    am_trend_end: int = 0                # ... 0 = off (test 630 / 660): no new AM entries after this minute (positions run to am_exit)
    post_news_fade: bool = False         # N5-pre0930-entries (050 ~00:34:08): after an 08:30 release the spike into an HTF OB with a VI that stalls 3+ bars: fade it from the VI
    pre_draw_done_am: bool = False       # ... a pre-09:30 trade that reaches the session draw ends the AM (the PM is untouched)
    pre_0700_hard_days: bool = False     # new-premarket-difficult-days (032 ~00:06:00): 07:00-08:30 window on an 08:30 day with FOMC today or a high-impact event tomorrow, held through the release
    hard_day_one_trade: bool = False     # ... the target fill ends the day
    pre_entry_guard: bool = False        # T4-no-early-entry-conditions (100 ~01:26:48): no pre-open entry when a 10:00+ release is pending or an untaken pool lies within one risk distance beyond the stop
    chop_wait_bars: int = 0              # new-10min-wait-choppy (027 ~00:25:03): 0 = off (test 10) - after the chop detector turns on wait this many bars, then require displacement
    # --- Caption-gap pass, package day_week_context#1/3 (digests/rulebook_gaps; dwc1.py). Everything defaults off. ---------------------------------------------------------------------
    pre_cpi_mon: str = "off"             # day_selection N4-pre-cpi-monday-gap (028 ~00:34:21): Monday before a Tuesday CPI: "tag" (pre_cpi_mon_small / pre_cpi_mon_gap) / "gap" (a large NWOG: only the side that reprices into the gap) / "skip_small" (skip a small-NWOG Monday)
    pre_cpi_gap_adr: float = 0.5         # ... [our interpretation] large = |Sunday open - Friday close| > this x ADR5
    landmine_min: int = 0                # D20-landmine-week-monday (064 ~00:10:18): 0 = off (test 2) - a week with this many high-impact release days Tue-Fri exempts Monday from skip_monday
    post_holiday_am: str = "off"         # N7-post-holiday-am-symmetry (090 ~02:07:38): "skip" = the AM after a holiday / abbreviated session / large-range day is blocked; "symmetry" = ... until ES and NQ break the same side of the 09:30-09:45 range (lifts skip_post_holiday_am); "off" = skip_post_holiday_am alone
    holiday_nfp_override: bool = False   # N7-holiday-week (072 ~00:04:19): a holiday on Mon-Wed of NFP week: the Thursday is not blocked by nfp_week_block (clean Thu / Fri)
    holiday_week_mult: float = 1.0       # N7-holiday-week (045 ~00:44:04): holiday weeks (wonky delivery): risk multiplier (test 0.5); != 1 also means no pyramiding on holiday_week days
    august_mode: str = "off"             # N7-august (079 ~00:10:14; 081; 084; 087): the whole month - "skip" or "light" (experienced: risk x0.5, no adds, a single exit at the first target)
    summer_off: bool = False             # N7-august (084 ~00:28:06; 087 ~00:01:56): no trading Jun-Aug
    season_quality: str = "off"          # B23-seasonal-quality (079 ~00:24:47; 100; 102; cc10_015): "tag" (season_prime / season_poor / season_off / season_may_overlap) or "size" (risk x 1.0 / 0.5 / 0.75 [our interpretation])
    season_autumn_start: int = 9         # ... the autumn prime window starts Sep 1 (079) or 10 = Oct 1 (cc10_015)
    season_march_mult: float = 1.0       # ... March risk multiplier in "size" mode (B23 flags March low probability; test 0.5)
    skip_election: str = "off"           # N7-election (cc04_002 ~00:26:40): "two_weeks" (Nov 1 to election day + 9) / "narrow" (election day and the next trading day) - ICT's personal practice
    holiday_eve_cases: str = "a"         # DS2-holiday-eve-friday-before-tue-holiday (cc10_019 ~00:23:45): "a" = the day before a holiday, "ab" = also the Friday before a Monday / Tuesday holiday (skip_holiday_eve)
    objective_frac_gate: float = 0.0     # N9-objective-before-lunch (015 ~00:16:22): 0 = off (test 0.5) - once the move to the session's locked draw is past this share, no continuation entry toward it [our interpretation: the 'more than about half' threshold]
    objective_done_pm: str = "off"       # ... "reversal_only": after the AM draw traded before 12:00 the PM trades only the counter direction (not the whole PM skipped as objective_done_skip does)
    sd_intraday: str = "off"             # N8-intraday-seek-destroy (015 ~00:21:31; 024 ~00:19:27): "tag" or "rules" (single exit, no entry before the range breaks, none after the locked HTF level traded)
    sd_intraday_until: int = 630         # ... [our interpretation] the detector window 09:30-10:30
    sd_intraday_frac: float = 0.35       # ... [our interpretation] the session range < this x ADR5
    sd_fvg_hold: bool = True             # N8-intraday-seek-destroy (015 ~00:21:31) rule (b), only with sd_intraday="rules": after the close beyond the flagged range wait for an FVG in the break direction and a retrace into it that closes without a body through it
    sd_week_detect: bool = False         # N8-seek-destroy-week (cc07_002 ~00:07:57): the S&D week needs the Mon-Wed/Thu shallow two-sided run (sd_shallow_frac x ADR5, no daily close beyond) on top of the FOMC / NFP / July-August calendar condition
    sd_shallow_frac: float = 0.25        # ... [our interpretation]
    sd_after_array: bool = False         # ... the week is released again once its extreme touched a D / W array (a new setup is then allowed)
    big_day_am_resume: int = 0           # N8-large-org-day (033 ~00:13:51): 0 = off (test 645) - big_day_am_skip lets the AM resume from this minute
    nwog_templates: str = "off"          # BH-NWOG-week-open-scenarios (084; 028; 029; 103; 101): "tag" / "gate" the Monday templates (nwog_up_bull, nwog_dn_bear, nwog_flat_bear, nwog_below_wick_bull + fill status)
    thu_strict: bool = False             # BH-N10-thursday-not-top-call (044 ~00:16:07): Thursday after a one-sided week: a counter-trend entry needs an HTF array at the sweep, a displaced MSS (x1.5) and a 10:00-11:00 fill
    fri_one_sided: str = "off"           # BH-B17-friday-after-one-sided-week (045 ~00:11:00): "tag" / "raid_first" (longs need the sweep below the 09:30 open; T1 capped at fri_t1_pts)
    fri_t1_pts: float = 5.0
    season_windows: str = "off"          # BH-B23-index-seasonal-windows / B23-intramonth-detail / seasonal-failure / X3-seasonal-*: "tag" = the regime / window / intramonth / result / prime-minor tags (reported by dw_tags)
    season_gate: bool = False            # ... the gate: intramonth season_dir, the window only when strength / regime / weekly tone / macro agree, no shorts after a failed-up result
    season_move_adr: float = 1.0         # BH-B23-seasonal-failure [our interpretation]: the counter / consolidation yardstick = this x ADR5 x window sessions / 5
    season_min_rank: float = 0.0         # X3-seasonal-strength-grading (cc05_010): 0 = off (test 0.67) - windows whose composite swing ranks below it (prior years only) give no tag / gate
    macro_risk_dates: object = ""        # BH-mixed-HTF-intraday-only (068 ~04:27) / X3-seasonal-macro-override (cc05_011 ~00:22:19): a CSV path (columns week, direction) or a tuple of "YYYY-MM-DD[:dir]" flagged weeks; "" = off
    tgif_strict: bool = False            # BH-M14-TGIF-preconditions (066 ~00:15:52): the tgif tags need a weekly / monthly array reached, tgif_weeks strong prior weeks and Mon-Thu each closing up
    tgif_weeks: int = 2                  # ... [our interpretation] "several weeks" = at least 2
    mo_overdue: bool = False             # B11-monthly-five-up-closes (078 ~00:16:48): tag mo_overdue_dn / mo_overdue_up for the month after 5+ same-way monthly closes into a monthly array
    mon_how: str = "off"                 # NEW-monday-high-of-week-profile (078 ~01:07:29): "tag" / "gate" (Tue-Thu shorts need an entry under Monday's high; mirror for bullish)
    mon_how_edge: str = "low"            # ... Monday closed below the array's "low" (default) or its "ce"
    wk_push_range: bool = False          # NEW-failed-weekly-push-range (102 ~00:11:29): last week pushed to a prior weekly wick's CE and failed: this week is a range (orders scalp) until a daily close beyond the wick's 75 % level
    wk_profile: str = "off"              # M17-weekly-profiles-selection (cc07_002 ~00:00:50): "tag" - classic_tue_low / wed_low / consol_thu_reversal / mon_how (mirrored for a bearish week), Trade.wk_profile
    iw_reversal_watch: bool = False      # B17-intraweek-reversal-profile (cc07_007 ~00:20:55): tag iw_reversal_watch on Wed / Thu after a Mon / Tue range > iw_k x ADR5 closing at an HTF array
    iw_k: float = 1.5                    # ... [our interpretation] ICT gives no multiple
    iw_no_measured: bool = False         # ... drop the measured-move (equal-leg) targets on those days
    three_day_small: bool = False        # B11-three-closes-day4 (cc08_006 ~00:02:07): day 4 after three same-way closes: tag day4, every order a scalp (single target, no runners)
    day_profile: str = "off"             # T13-day-profile-selection (cc10_013 ~00:04:22): "tag" profile_day two_session / am_pm_reversal
    day_profile_gate: bool = False       # ... on am_pm_reversal days the PM lock side is the opposite of the AM's once the array traded; on two_session days the PM goes with the AM side only
    n8_use_overnight: bool = True        # N8-overnight-not-precursor (cc10_009 ~00:00:55): False = the consolidation / trending classification ignores the overnight range (premium_chop on_range); the N9 narrow-overnight skip is its own switch
    # --- Caption-gap pass, package day_week_context#2/3 (digests/rulebook_gaps; dwc2.py). Everything defaults off. ---------------------------------------------------------------------
    consolidation_mode: str = "skip"     # day_selection N8-consolidation-tradeable (053 ~00:01:13; cc01_005; cc04_012; cc09_004; cc10_008): "skip" (today: stand_aside), "range_trade" (only turtle-soup / OTE / sick-sister entries, targets inside the range), "fade_with_htf" (turtle soup on the HTF-bias side only), "scalp" (AM scalps, flat by 11:00)
    consol_range_days: int = 3           # ... [our interpretation] range_trade: the consolidation range = the high / low of the last N sessions
    expansion_strict: bool = False       # N8-expansion-day-conditions (cc08_006 ~00:24:37): expansion_due also needs a bias, no sloppy / big_prev / three-close day and the manipulation leg against the bias; expansion_targets then adds 1.5 x ADR5 from the manipulation extreme
    expansion_judas_adr: float = 0.1     # ... [our interpretation] the manipulation leg must reach this x ADR5 beyond the midnight open (noise around the open is no manipulation)
    expansion_mode: str = "off"          # DS2-contraction-precedes-expansion (cc10_008 ~00:17:40): "tag" expansion_candidate (a sub-ADR5 / consolidation day, then a 08:30-10:00 release), "full" = also no slow-day (80/20) ladder and the po3 runner on it
    trend_side_rule: bool = False        # DS2-trending-day-direction (cc10_009 ~00:04:15): replaces the trend_recipe side: the smallest range of 5 (or 3 contracting), a daily FVG discount (premium) array touched below (above) the 60-day EQ, high / medium 08:30 news, and the table draw agreeing
    fri_delivered_stop: bool = False     # N10-friday-preopen-delivered (035 ~00:39:24): Friday, the locked draw delivered before 09:30 with an SMT at the extreme: no continuation entries after 11:00 and none in the PM
    fri_pool_choice: bool = False        # N10-friday-pool-choice (096 ~00:06:54; cc04_011 ~00:18:05): on Fridays a sell-side pool already run and an unrun buy-side pool above lock the buy-side (mirror), targets capped at the week's extreme; a TGIF Friday takes a single exit
    mon_big_frac: float = 0.5            # N10-monday-weekly-extreme (cc07_008 ~00:29:09): monday_mode "big_into_array" - the 00:00-09:30 range must reach this x ADR5 [our interpretation]
    mw_break_bias: bool = False          # N10-mon-wed-range-break (cc07_001 ~00:44:15): thu_fri_break counts only a break on the weekly-bias side
    mw_carry: bool = False               # ... a weekly target not reached by Friday keeps the bias for the next week
    thu_reversal_tag: bool = False       # new-consolidation-thursday-reversal (cc07_002 ~00:04:51): precise tag thu_reversal / thu_reversal_bear (Mon-Wed <= 1.5 x ADR5, Thursday under the Mon-Wed low then closing above it)
    thu_reversal_trade: bool = False     # ... the turtle-soup variant with the Mon-Wed low as the pool, bias side only (implies the tag)
    wed_week_extreme: bool = False       # new-wednesday-weekly-extreme (cc07_002 ~00:03:01): Wednesday of a bullish week whose Monday / Tuesday did not reach the nearest daily discount array: longs only (mirror)
    days_mode: str = "all"               # DS2-monday-ideal-day (cc08_007 ~00:07:17; cc12_004 ~00:06:30): "mon_wed" (block Thursday / Friday) or "tue_wed" (also Monday)
    late_week_fallback: bool = False     # DS2-mon-wed-fallback-thu-fri (cc12_004 ~00:06:30): with days_mode, Thursday / Friday open only if the Mon-Wed move (>= 1 x ADR5 with the weekly bias) did not deliver
    no_long_after_thu_noon: bool = False # DS2-weekly-template-sequence (cc09_008 ~00:41:53): weekly-direction entries stop after Thursday 12:00 and on a Friday after a Thursday that closed with the bias
    ny_cont_gate: bool = False           # DS2-ny-continuation-adr-pending (cc09_003 ~00:12:11): bias-side entries before 10:00 need the day's counter extreme in 0-300, no 4h / D array touched on the bias side and the range under ADR5; adds the LOD + ADR5 target
    adr_news_exempt: bool = False        # DS2-adr-filled-news-extends (cc09_007 ~00:18:32): the London ADR skip (london_adr_skip) does not fire on a day with a release at or after 10:00
    london_low_guard: bool = False       # new-london-low-violated (092 ~02:29:00): bias set, NY trades through the London low (high): no entries that day; bias side only; entries from 10:00
    london_filters: bool = False         # N8-london-filters-gate-london (cc08_006 ~00:13:20): the FOMC whipsaw / multi-release filters gate the London windows only
    po3_adr_invalid: bool = False        # T13-po3-small-open-wick (cc08_008 ~9:13): after a daily discount (premium) reaction a low below midnight open - ADR5 (high above + ADR5) clears the long (short) bias
    tgif_reversal_pct: float | None = None  # M14-reversal-threshold (066 ~25:34 / ~18:12): the Friday retrace share of the weekly range that flags a reversal (0.30 | 0.40); None = tgif_stand_down (0.40, unchanged); when set it IS the effective TGIF stand-down; tag wk_reversal_flag next week
    tgif_fvg_cap: bool = False           # M14-tgif-daily-fvg-ce-cap (089 ~00:02:57): TGIF short entry at or below the CE of the nearest daily SIBI above, stop above max(CE, longest-wick CE), PDL / FVG-low rungs, cancelled after two 5m closes above the CE
    adr_close_runner: bool = False       # LLT3-adr-fib-close-zone (cc09_006 ~00:26:59): the runner leaves at H - 0.20 x ADR5 once price traded H = L + ADR5 and turned
    fri_trail_from: int = 0              # X5-friday-tight-trail (103 ~00:30:33): 0 = off (test 900) - from this minute on a Friday the stop ratchets under each new 1-bar pivot low
    adr_met_runner: bool = False         # L16-adr-contraction-runner (cc09_008 ~00:47:45): ADR5 covered by 09:30 in the trade direction: the last runner share leaves at adr_runner_until, not at am_exit
    adr_runner_until: int = 840
    adr_contracted_tag: bool = False     # ... (a) the context tag adr_contracted: ADR5 in the bottom tercile of the last 60 sessions
    # --- Caption-gap pass, package day_week_context#3/3 (digests/rulebook_gaps; dwc3.py). Everything defaults off unless a comment says otherwise. ---------------------------------------------
    consol_pm_need_sweep: bool = False   # T13-consolidation-pm-fizzle (cc10_013 ~00:13:57): on a consolidation day the PM trades only after a bar traded beyond the lunch (12:00-13:30) or session high / low (else the PM fizzles: no trade)
    choppy_week_tag: bool = False        # N8-choppy-week-no-hold (079 ~00:21:40): after choppy_week_days consecutive days that each swept the prior day's high (bearish week; low if bullish) before the bias-direction extreme: tag choppy_week; the day takes the slow ladder and no runner
    choppy_week_days: int = 2            # ... [our interpretation] "consecutive days" = 2
    tgif_week_high_exit: bool = True     # M14-tgif-invalidation-timing (075 ~01:40:30): with tgif on, a TGIF order is void (pending cancelled, stop at the level) beyond the week high (low) that preceded it
    tgif_window: str = "pm"              # M14-tgif-am-timing (085 ~00:17:32; 089 ~00:01:29; spec default "pm"): with tgif on, TGIF entries only in "am" (09:30-12:00) | "london_close" (10:00-12:00) | "pm" (13:30-15:00); "off" = no window. Under tgif_model the M14.3 tgif_timing windows stay in force (unless tgif_model_skip has "tgif_timing")
    tgif_min_adr: float = 3.0            # M14-tgif-am-timing (spec default 3.0): with tgif on, the Mon-Thu range must exceed this x ADR5 for a TGIF tag (0 = off)
    tgif_need_htf_array: bool = True     # M14-tgif-am-timing (spec default True): with tgif on, the Friday sweep must be at a same-side HTF array (tgif_htf_array behaviour); tgif_precond="loose" waives it
    inside_bisi_redelivered: bool = False  # B17-M15-madeuce-inside-bisi (091 ~00:15:17): the sloppy "inside_bisi" fires only when yesterday already traded through the daily FVG's CE and today opens within bisi_ce_band of it (in the not-yet-re-delivered premium-half state it does not fire, so Ma Deuce is free there)
    bisi_ce_band: float = 0.15           # ... [our interpretation] the band = this share of the FVG's height around its CE
    weekly_po3: bool = False             # M17-weekly-judas-po3 (cc07_008 ~00:31:31): weekly bias set: Mon-Wed entries in its direction only while price is beyond the weekly open (above for bearish), the other side blocked; tag weekly_judas
    journal_timing: bool = False         # OT-X16-time-to-move-journal (042 ~00:51:03): Trade.min_to_fav / min_to_exit / first_exit_kind / mfe_pts / mae_pts and the day tags pre_fomc / news_day (reporting only)
    fav_pts: float = 2.0                 # ... [our interpretation] a "favourable move" = this many ES pts from the fill
    checklist: str = "off"               # OT-pre-session-checklist-order (cc12_004 ~00:22:21): "tag" (Trade.cl_fail = the failing steps) / "gate" (also skip the session's entries when a step fails)
    cl_days: tuple = (0, 1, 2)           # ... the preferred weekdays (Mon-Wed); Thu / Fri pass when the week had no target hit yet
    cl_pm_ok: bool = True                # ... [our interpretation] the PM passes the IPDA true-day step
    stock_intraday: bool = False         # OT-stocks-swing-only (cc10_018 ~00:33:36): False = run_day returns nothing for an individual stock symbol (index futures / ETF proxies are unaffected)
    pm_narrative: bool = False           # N9-pm-narrative-from-am-chop (022 ~02:26:36): a chop AM + an unfilled opening gap + SMT at the AM extreme + repeated AM runs -> the PM trades toward the gap only, one attempt
    pm_narr_gap_pts: float = 5.0         # ... [our interpretation] "large" gap = at least this many ES pts
    max_trades_month: int = 0            # X15-monthly-cap (095 ~00:49:31): 0 = off (test 3 / 10)
    skip_months: tuple = ()              # X15-monthly-cap: month numbers with no trading (our mapping, e.g. (8,))
    htf_quality_only: bool = False       # X15-three-per-week-htf-quality (099 ~00:47:36): the final target must be a daily / weekly array, PDH / PDL, PWH / PWL or NWOG level and the setup must sit on a 1h / 4h swing / array (combine with max_trades_week=3)
    weekly_target_pct: float = 0.0       # X15-weekly-goal-stop (cc02_001 ~00:22:57): no new trades for the rest of the week once the week's closed P&L reaches this % of the start-of-week account (test 1.5)
    weekly_cap_pts: float = 0.0          # ... or this many ES points (test 10-15 [our interpretation])
    carry_weekly_draw: bool = False      # N10-unmet-target-carries-to-monday (061 ~02:32:51): a weekly draw not reached keeps its side (and the level as a target) on Monday / Tuesday of the next week
    carry_neutral_after: bool = True     # ... once the carried level traded the rest of that week is neutral (bias 0)
    thu_targets_met_block: bool = False  # N10-thursday-reversal-after-targets-met (099 ~01:02:20): the week's HTF draw hit Mon-Wed -> Thu / Fri block the with-trend side; the counter-trend side exits fully at the nearest pool
    skip_fri_if_week_up: bool = False    # N10-friday-skip-profitable-week (100 ~00:07:18): no Friday trading when the week's closed P&L is above 0
    mw_extreme_need_array: bool = False  # N10-mon-wed-extreme-trending-week (cc07_006 ~00:21:27): in a trending week Mon-Wed with-trend entries need the sweep inside a D / W array (or at the 20 / 40 / 60-day extreme)
    trend_k: float = 0.8                 # ... [our interpretation] trending = the previous week's range >= 5 x ADR5 x trend_k and a close in its outer quarter
    missed_week_mode: str = "off"        # N10-missed-mon-wed-no-chase (cc07_006 ~00:24:29): Thu / Fri after a visibly started Mon-Wed move the bot did not trade: "nearest" (with-trend orders exit fully at the nearest pool) | "skip" (no trade)
    tgif_precond: str = "strict"         # M14-tgif-timing-and-precondition (084 ~00:15:56): "strict" = tgif_htf_array decides (an HTF array reached); "loose" = the large one-way week alone (no array needed)
    tgif_thu: bool = False               # ... Thursday holding the week's low (high) after 10:00 with Wednesday's taken earlier: the TGIF side block applies Thursday PM
    tgif_seq: bool = False               # ... Friday sequencing: a new weekly extreme in the AM -> entries 10:00-12:00, or 13:30-15:00 when 10:00-12:00 consolidates
    tgif_consol_frac: float = 0.25       # ... [our interpretation] consolidation = the 10:00-12:00 range under this x ADR5
    tgif_no_rel: bool = False            # ... on a TGIF Friday the with-trend side does not target the relative equal highs / lows
    consol_pm_pool_exit: bool = False    # N8-consolidation-pm-full-exit-at-pool (cc10_008 ~00:10:24): a consolidation-day PM is one scalp to the nearest untapped pool (ONH / ONL, AM H/L, PDH / PDL), 100 % out there; none when the AM ran a pool
    aug_dd_stop_pct: float = 0.0         # N7-august-drawdown-restart (079 ~00:25:46): in August a drawdown of this % (from the August peak, or the month's net) stops trading until September (test 2-3)
    low_mag_months: tuple = (5, 6, 7, 8, 9, 10)   # E9-may-october (cc10_015 ~00:03:49): the low-magnitude months
    low_mag_mult: float = 1.0            # ... the risk multiplier there (test 0.5); August keeps its own row (the smaller wins)
    low_mag_week_cap: int = 0            # ... optional weekly trade cap there (0 = off)
    lunch_kind_tag: bool = True          # T8-lunch-three-behaviours-reversal (073 ~00:29:35): tag lunch_consol / lunch_run / lunch_open / lunch_reversal on PM trades (no behaviour change)
    noon_rev_flat: bool = False          # ... the lunch reversal (MSS against the morning after the noon extreme at a 1h FVG's far edge) flattens the open AM-direction position (exit "noon_rev")
    noon_rev_pm: bool = False            # ... and the PM trades the opposite side toward the AM range's opposite extreme / the ORG
    pm_mm_target: bool = False           # T9-pm-faster-measured-move (067 ~39:22): a PM continuation order adds a rung at the AM extreme + the AM leg's size
    london_ext_consol: bool = False      # T3-london-extreme-consolidation (010 ~00:39:18): on a consol_overnight day the London high / low is not the protected extreme (tag consol_overnight)
    tgif_branch: bool = False            # M14-tgif-timing (066 ~00:46:41): TGIF Friday: a 09:30 Judas -> entries from 10:00 after the MSS; else no AM entry and entries from tgif_pm_from after an MSS of a high formed 11:30-14:00
    tgif_pm_from: int = 810
    consol_pm_news_skip_am: bool = False  # N8-consolidation-pm-news (cc10_008 ~00:16:34): a consolidation day with a PM release (at / after 12:00) has no AM trade
    # --- Caption-gap pass, package bias_htf#1/7 (digests/rulebook_gaps/bias_htf_intermarket.md; bh1.py table side, bh1e.py engine side). Everything defaults off. -----------------------------------
    drange_scalp: bool = False           # BH-B17-daily-range-scalp-regime (002 ~00:06:57; 043 ~00:06:55; ~00:13:48): in a multi-day daily consolidation every order is a scalp (one target, no adds, T1 capped at drange_t1_pts), after one side's pool ran only the opposite side trades, the day stops after drange_day_pts or two wins; after the range breaks only the breakout side trades, runners allowed
    drange_n: int = 5                    # ... [our interpretation] the range = the last N daily closes inside the first of those days' high-low
    drange_break: str = "close"          # ... a breakout = a daily "close" beyond the range or a "wick" beyond it (undefined by the source: test both)
    drange_t1_pts: float = 5.0           # ... scalp target distance, ES points (~5 handles)
    drange_day_pts: float = 10.0         # ... stop for the day after about 10 handles
    b7_fresh_break: bool = False         # BH-B7-last-daily-OB-guard (review round 1): True = only a FRESH break counts for wk_high_in (the previous close was still on the guard's side; first-pass reading), False (the spec) = any daily close below the guard MT sets it from the next day
    b7_mode: str = "mt_close"            # BH-B7-last-daily-OB-guard (058 ~00:06:43; 072 ~00:17:12; 101 ~00:33:35): what breaks the last daily OB's guard - "mt_close" (a daily close below its MT; wicks allowed), "mt_trade" (any trade below the MT), "ob_close" (a close below the OB's low); also the ob_mt flip trigger's level
    wk_high_in_gate: bool = False        # ... after a daily close below the guard MT the week's high is in: longs lose every target above the week's high (a long that needs a new weekly high is no trade); not a short signal. Mirror
    bisi60_draw: bool = False            # BH-A8-60m-BISI-loss-draw (007 ~00:06:46, single source): a 60m close below the nearest discount 60m BISI (under the swing's 50 %) before the lock leans the lock to the sell-side below; tag bisi60_lost. Mirror
    neutral_lean: bool = False           # BH-B17-neutral-lean (010 ~00:36:36): with htf_bias on and a neutral bias, the gun-to-head lean at a daily premium (discount) array probed repeatedly without a close through it becomes the bias - scalp-tagged unless the prior (Tuesday) high / low was raided before the entry
    lean_n: int = 2                      # ... [our interpretation] repeated failed attempts = the last N daily highs (lows) probed the array
    lean_tol_pts: float = 5.0            # ... [our interpretation] "at the array" = within this many ES pts
    wk_bisi_ce_neutral: bool = False     # BH-weekly-BISI-CE-and-full-close (011 ~00:05:06; 047 ~00:02:05): with the flip trigger "wk_bisi" a weekly close below the weekly BISI's CE (but not its low) turns a bullish state neutral [our interpretation of "in doubt"]
    ceiling_ladder: bool = False         # BH-B1-imbalance-ceiling-ladder (011 ~00:00:24): while no daily body closes above the nearest overhead daily VI / FVG the lower arrays are drawn in order: the session lock is the sell-side (buy-side under a floor); suspended once price traded above it and held it as support
    bpr_lean: bool = False               # BH-A11-BPR-lean (011 ~00:01:51, opinion): a 1h down-up-down BPR formed in the last 24 h with a bearish state leans the lock to the nearest pool below (mirror); tag bpr_lean
    nwog_ref: str = "current"            # BH-B14-NWOG-flip-edge (030 ~1:19:54; 046 ~26:00; 060 ~35:36; 058): "current" = this week's NWOG holds the bias state, "previous" = last week's (030); the reclaim edge is nwog_flip_edge
    nwog_flip_edge: str = "high"         # BH-B14-NWOG-flip-edge (the spec default, review round 1): a bearish state holds until price is back above the NWOG HIGH ("high" = 030 / 046 / 060) or LOW ("low" = 058); mirror. nwog_bias_reclaim, when set, overrides it ("ce" lives there)
    nwog_bias_basis: str = "close"       # ... a reclaim is a daily CLOSE beyond the edge ("close", the spec default [our interpretation]) or the row's 09:30 price ("px", the first-pass build)
    raid_gap_guard: bool = False         # BH-B14-protective-gap-and-low (061 ~02:28:31): after a sell-side raid below the prior session's range the lock is long toward the current NWOG's near edge until the raid low is taken while the small bear gap left after the raid is still open (then the lock flips to the sell-side). Mirror
    inval_src: str = "off"               # BH-B8-pre-stated-invalidation-price (012 ~00:27:58): "array" (the far edge of the nearest opposing daily array beyond the lock price) / "manual" (data/mentorship/inval_levels.csv: date, session, price) - a TOUCH flips the session's lock side and cancels the old side's pending order
    bellwether_tf: int = 0               # BH-B5-bellwether (013 ~2:46; cc01_003 ~19:10; cc03_001 ~20:13): 0 off, 15 or 60 - an order needs the last swing break (3-candle pivots) of the 15m / 60m chart to be in its direction; 15 needs a known bias / weekly expansion side, else the 60m chart is used
    org_gap_filter: bool = False         # BH-B15-gap-down-ORG-no-shorts (059 ~00:14:52; 018 ~00:03:09): a gap down at 09:30 blocks shorts (gap up: longs) unless the flip state agrees and the dollar is on its side (INTERMARKET dxy), or the B15 tell fired (no attempt by 10:00)
    org_tell_seq: bool = False           # BH-B15-ORG-tell-details (030 ~01:29:44): the sequence tell - no meaningful attempt back toward the prior close 09:33-10:00, then a displacement close through the CE and the low of yesterday's FVG: the bias for the AM rest (org_tell is the older attempt-only tell)
    org_attempt_frac: float = 0.25       # ... [our interpretation] "meaningful attempt" = a retrace of at least this share of the gap
    org_tell_skip_min: int = 3           # ... the first minutes after 09:30 are ignored
    org_tell_end: int = 600              # ... the tell is judged at this minute (10:00)
    org_consol_case: bool = False        # BH-B15-ORG-consolidation-case (055 ~00:18:18): objective met / a consolidating market (daily range or NWOG regime) and the ORG filled: the day ranges inside the gap - every later order a scalp capped at the opposite ORG edge or CE; tag org_consol
    dxy_filter: str = "off"              # BH-B19-DXY-soft-filter-for-indices (063 ~00:10:53; 046 ~02:13:40; 028 ~00:22:53): "tag" counter_dxy / dxy_ok, "soft" (a counter-dollar index order trades at dxy_soft_risk x risk as a scalp, tagged counter_dxy), "hard" (block longs with the dollar rising, shorts with it falling); prior-day dollar vs its 20-day mean
    dxy_soft_risk: float = 0.5           # ... [our interpretation] the reduced size of a counter-dollar index trade
    low_in_relock: bool = False          # BH-failed-sweeps-low-in (022 ~02:01:51): after the AM sell-side draw is delivered, repeated short-term highs taken against few new lows = the morning low is in: re-lock the session buy-side (a second trade); tag low_in. Mirror
    low_in_min_highs: int = 3            # ... [our interpretation] at least this many short-term highs taken
    low_in_ratio: float = 2.0            # ... and at least this many times the new lows made since the delivery
    fifty_rel: bool = False              # BH-B17-REL-REH-both-intact (025 ~00:10:58): the 50/50 test - price inside a daily FVG with the nearest REL below and the buy-side above both untaken: the session lock is neutral; a sweep of the REL then an MSS up re-locks long (mirror: REH). (neutral_gate "fifty_fifty" is the older reaction-weight test)
    iof_tf: int = 0                      # BH-B6-intraday-iof (028 ~00:21:27; 085 ~00:10:28; 099 ~00:15:03): 0 off, else the bar size (e.g. 15 / 60) of the intraday order-flow state - bearish while up-close candles hold as resistance and down-close candles are closed through; orders against it are rejected
    allow_counter_trend: bool = False    # BH-B3-counter-bias-modes (095 ~11:56; 030 ~25:11): after the session's locked draw was taken and a MSS the other way formed, one counter-bias trade to the nearest pool on the other side (single target, scalp, no adds); tag counter_trend
    draw_order: str = "nearest"          # BH-B2-draw-by-proximity (067 ~1:30:55; cc02_008 ~13:11; 054 ~6:38; 065A ~50:00): "nearest" (built), "nearest_tb" (near-ties within eq_tol_pts go to the candidate with fewer arrays between, then the newer) or "inefficiency_first" (the table's draw column = the ordered B2 pick)
    wick_ce_draw: bool = False           # BH-B2-wick-CE-draw (065A ~39:00; review round 1: acts as a lock candidate / the ordered draw columns - the table's plain draw column is unchanged): with no inefficiency left the draw is the nearest untaken weekly (else daily) wick's CE (first objective), its extreme the full one (draw_ext_lvl)
    stack_far: bool = False              # BH-B2-two-HTF-FVGs-farther (069 ~1:59): two stacked daily FVGs in the bias direction: the draw is the farther gap's near edge, the nearer one's near edge a partial rung (draw_mid_lvl)
    no_htf_top_pick: bool = False        # BH-no-HTF-top-picking (061 ~01:40:32; 074 ~00:37:14; 076 ~00:05:21; cc06_001 ~00:06:55; 104 ~00:44:07): while the flip state is up and the HTF draw unmet, no turtle-soup / three-drive / reversal shorts (mirror)
    min_criteria: bool = False           # BH-B4-HTF-bias-minimum-criteria (075 ~00:34:50): the long lock needs (1) price at a daily bull array, (2) a swept 60m REL, (3) a later 60m high above the last 60m pivot high - else the lock is neutral. Mirror
    wk_po3: bool = False                 # BH-B13-weekly-PO3 (066 ~00:08:51; 072 ~00:07:07; cc07_006 ~00:08:30): after the week traded below the weekly open into a daily array and closed back above it (mirror above/below), the opposing side is blocked for the rest of the week and the lock is long toward the weekly draw; an NFP week stays 0 until Friday
    run_extreme_lean: bool = False       # BH-consolidation-takes-run-high (046 ~00:09:16): with a neutral lock, lock toward the high (low) of a >= 2 x ADR5 run followed by >= 2 inside days until it is taken
    pwh_giveback_draw: bool = False      # BH-PWH-run-giveback-weekly-gap (047 ~00:01:31): the week ran above the previous week's high and gave back giveback_frac of its range: the nearest weekly BISI's CE is a sell-side lock candidate (tag pwh_giveback)
    giveback_frac: float = 0.5           # ... [our interpretation] "much of"
    htf_monthly: bool = False            # BH-A5-HTF-FVG-own-timeframe (068 ~3:02): alias of htf_monthly_arrays (monthly FVGs on monthly bars, usable the session after the month closes); weekly arrays are already built on weekly bars
    bisi60_hold: str = "off"             # BH-B8-1h-BISI-CE-hold (072 ~00:13:53, ~00:15:19): "trade" / "close" - with a +1 lock the latest 60m BISI: a trade (60m close) below its CE tags bias_weak, below its low sets the lock to neutral for the session and cancels the pending order. Mirror
    wk_dc_joint: bool = False            # B8-weekly-ith-both-indices-close (077 ~00:09:44): the wk_dc -1 flip applies only when ES and NQ BOTH closed the week below their own last down-close week's low (backtest.run with a partner; persists until a +1 on either)
    b9_persist: bool = False             # B9-retrace-above-swing-low (077 ~00:11:02): a flip to the opposite state is suppressed while the daily low (high) holds the last daily pivot low (high) and the lower (upper) breakaway FVG stays partly open
    # --- Caption-gap pass, package bias_htf#2/7 (digests/rulebook_gaps/bias_htf_intermarket.md items 82-88, 90, 91, 93-96, 104-109, 114, 116, 117, 119, 121, 122, 130-136, 138, 139, 143; bh2.py table side, bh2e.py engine side).
    # Everything defaults off; thresholds the sources never give are [our interpretation]. -----------------------------------------------------------------------------------------------------------------------------
    scalp_week_risk: float = 0.5         # B17-neutral-htf-monday-close (084 ~1:26): bias_neutral="scalp_week" - a week without an HTF draw trades both sides as scalps (one target, no runners) at this multiple of the risk [our interpretation: 0.5]
    q_days_tag: bool = False             # B22-timing-tool (cc05_001 ~35:25-37:51; cc05_003 ~29:20): the table columns q_days (sessions since the last daily MSS) and q_window (q_window_lo <= q_days <= q_window_hi); tag q_window on the orders. Report only
    q_window_lo: int = 40                # ... [our interpretation] "the last third" of the 60-session cast: S+40 ..
    q_window_hi: int = 60                # ... .. S+60
    q_window_gate: bool = False          # B22-timing-tool: the daily-SMT bias (dsmt_bias) counts only inside the q_window (a time filter, not a direction source)
    q_window_size: float = 1.0           # B22-timing-tool: risk multiplier (> 1 sizes up) when the q_window, the bias side and the seasonal direction (calendar window, else the intramonth map) all agree with the order; 1 = off
    shift_due_tag: bool = False          # X3-shift-due-six-months (cc05_001 ~48:36): column shift_due = q_days >= 126 with the 126-session net move in one direction; tag only
    qshift_bias: bool = False            # X3-b22-shift-trigger-quarter-bias (cc05_001 ~32:36; cc05_004 ~16:53; cc05_003 ~16:01): the concrete quarterly shift (column qshift): a new 60-session high within the last 10 sessions and then a daily low under the last daily STL -> -1 for 63 sessions (or until a new 60-session high); mirror. With the switch the bias defaults to qshift when otherwise 0
    q_obj_lean: bool = False             # B22-quarterly-shift (084 ~22:18 ...): column q_obj = the nearest weekly array in the shift's direction beyond the 60-session range (quarterly_objective), kept until traded or q_obj_days sessions; with the switch a neutral lock leans to it
    q_obj_days: int = 84                 # B22-quarterly-shift (084 ~22:18): the quarterly objective stays valid 84 sessions (4 months) unless traded earlier [our interpretation of "until the objective is reached"]
    qshift_strong_consol: bool = False   # X3-b22-shift-form-strong-trend (cc05_001 ~7:35): a shift against a strong primary trend (price > qshift_strong_pct beyond its 252-session mean) is a consolidation, not a retracement: qshift does not change the bias and the next 20 sessions are scalps (tag qshift_form)
    qshift_strong_pct: float = 0.10      # ... [our interpretation] "strong" = price more than this far beyond the 252-session mean
    iof_weekly_weight: bool = False      # B6-weekly-iof (cc12_002 ~16:34): the B6 candle-respect score on WEEKLY bars (column iof_w, usable the session after the week closes); orders agreeing with it trade at full size, against it at iof_w_risk x (tag iof_w_agree / iof_w_oppose) [our interpretation of "favoured"]
    iof_w_risk: float = 0.5              # B6-weekly-iof (cc12_002 ~16:34): risk multiple of an order against the weekly order flow [our interpretation: 0.5]
    iof_w_weeks: int = 10                # ... the weekly bars scored (the daily iof_days is in sessions)
    sibi_gate: bool = False              # NEW-daily-sibi-bias-gate (086 ~2:22, ~12:30): after a daily sell-side sweep the nearest daily bear FVG formed after it repels price: a close under its CE = only shorts; inside it above the CE = longs as scalps; above its high with a bar holding above = longs toward the buy-side pool. Mirror for a BISI after a buy-side sweep
    wick_ce_60m: bool = False            # A23-intraday-close-line-in-sand (090 ~19:57): a completed 60m bar closing above the prior day's upper-wick CE cancels the session's short lock (mirror: below the lower-wick CE cancels a long lock)
    sibi15_ce_cancel: bool = False       # ... (092 ~2:10:25, softer): a trade above the CE of the session's latest 15m bear FVG does the same (no close type given)
    allow_reversal_after_target: bool = False  # B3-reversal-after-target (086 ~10:26): once the session's draw is reached a wick into an opposite-colour breaker with the next 3 bars' bodies holding the wick extreme re-locks the other side; the PM Silver Bullet in the new direction may trade after a winning AM trade
    soft_carry: bool = False             # B17-unreached-draw-soft-bias (087 ~0:30): the previous day's last lock, not delivered, carries as a SOFT bias when today's own lock is neutral: soft_carry_risk x size, no adds (tag soft_carry); dropped when the opposing pool was taken overnight or the flip state changed
    soft_carry_risk: float = 0.5         # B17-unreached-draw-soft-bias (087 ~0:30): risk multiple of the carried soft bias ("a softer bias") [our interpretation: 0.5]
    inside_bisi_release: bool = False    # B17-inside-daily-range-no-trade (091 ~6:20): an inside_bisi stand-aside day is released from the first bar that trades release_pts beyond the daily FVG's high or low - and only that side trades
    release_pts: float = 1.0             # ... [our interpretation of "definitively"]
    fast_draw_extend: bool = False       # NEW-speed-into-weekly-draw (095 ~8:01): a weekly draw reached at >= fast_draw_mult x the speed of the prior leg is NOT neutral (objective_neutral): the next weekly array beyond is the new draw
    fast_draw_mult: float = 1.5          # ... [our interpretation]
    dxy_needs_rates: bool = False        # NEW-rates-dxy-fx-direction (095 ~14:49; cc03_006 ~5:35): INTERMARKET tnx_slow / rates_dxy_agree; the dxy_filter acts only when the 60-session yield slope agrees with the dollar's side (tag rates_agree / rates_diverge)
    pd3_result: str = "flip"             # B8-three-pd-array-abort (098 ~1:08:36 ...): the flip_pd3 trigger's result - "flip" (the opposite state, the built behaviour) or "neutral" (abandon the bias; the opposite state only after a displacement day)
    pd3_disp_adr: float = 1.5            # ... [our interpretation] a displacement day = range >= this x ADR5 closing in the top (bottom) quarter
    pd3_first_caution: bool = False      # ... while the first adverse array is closed through (and the third not yet) orders in the bias direction are scalps
    wk_q75_confirm: bool = False         # B8-weekly-wick-quadrant-gate (102 ~2:11:40; 103 ~0:02:32): the bias counts only after a daily close beyond the prior week's wick 75 % quadrant in its direction (this week); otherwise 0
    consol_dir: str = "off"              # N8-consolidation-breakout-direction (cc01_001 ~9:50; cc01_006 ~18:37): "first_expansion" (no trades inside the daily range; after the breakout only its side, entries at / under EQ + 25 % of the range) / "prior_strongest" (inside the range the side is the direction of the strongest day since the previous range, entries in the discount) - needs the drange table columns
    consol_chase_frac: float = 0.25      # ... [our interpretation] "no chase"
    htf_after_draw: str = "neutral"      # B17-after-draw-retrace-or-reverse (cc01_002 ~18:49; cc07_007 ~23:55; cc10_013 ~6:27; cc03_002 ~10:14): "neutral" (built) or "reverse" - at a daily/weekly array draw hit the bias is the OPPOSITE side (tag after_draw_case); a PM lock may reverse an AM draw hit at a 4h/daily array
    pd_two_level: bool = False           # A21-two-level-discount (cc01_004 ~30:18): a long needs the entry at / below the EQ of the 20-session BODY range as well as the leg discount (tag htf_discount); mirror
    range_no_bias: bool = False          # B3-range-trading-without-bias (cc01_005 ~18:51): with no bias a short needs the entry >= 62 % of the last 60m swing range (long <= 38 %), single target just beyond the opposite swing extreme
    range_no_bias_pct: float = 0.62      # B3-range-trading-without-bias (cc01_005 ~18:51): the premium (discount) threshold of the 60m swing range, 62 % (Fibonacci) for a short, the mirror 38 % for a long
    eq_tiebreak: bool = False            # B3-eq-recent-structure-break (cc01_006 ~7:29; cc05_015 ~5:09): bias 0 with the prior close within eq_tie_frac of the 20-session range EQ (monthly: 12-month range) takes the direction of the most recent daily (monthly) pivot broken by a close
    eq_tie_frac: float = 0.10
    tier_regime_gate: bool = False       # B6-hrlr-lrlr-structure-regime (cc01_007 ~19:48): column tier_regime -1 = intact LTH, lower ITH, last two STLs broken (mirror +1): longs whose target is above the defended ITH are rejected, a neutral lock goes short
    tug_required: bool = False           # X3-b6-tug-of-war-new-ground (cc05_002 ~16:12): the tier regime counts only with the tug-of-war reading too (column tug, post_raid)
    raid_profile_bias: bool = False      # B6-consolidation-raid-profile (cc02_008 ~14:28): the last raid_profile_n daily ranges each raided the low first and then exited up -> +1 (mirror -1) when the bias is 0
    raid_profile_n: int = 2              # B6-consolidation-raid-profile (cc02_008 ~14:28): "the last two" daily ranges
    htf_bias_tf: str = "D"               # B5-monthly-first-hierarchy (cc04_003 ~14:07; cc04_002 ~29:38): "D" (built) / "W" (weekly draw) / "M" (monthly draw, else weekly, else none - monthly arrays are built)
    htf_bias_pools: bool = False         # ... [our interpretation, owner question] the monthly / weekly bias reading also counts the previous month's / week's high and low as draws (like htf.table's PWH / PWL); off = the literal spec (FVGs of that timeframe only)
    tier_stl_mode: str = "last2"         # B6-hrlr-lrlr-structure-regime (cc01_007 ~19:48): the short-term lows (highs) being run - "last2" (the spec: each of the last two was broken) / "two_of_four" [our interpretation, owner question]
    htf_rank_tf: bool = False            # ... array rungs at the same level are labelled with the highest timeframe and ranked M > W > D (table columns rk_<tf>_up / _dn; bh2e.rung_tf)
    flip_terminus: bool = False          # B17-hold-bias-most-recent-htf-setup (cc03_001 ~21:17; cc05_002 ~22:06): the flip state ends (0) when the draw it was set with trades, or after flip_max_days sessions
    flip_max_days: int = 126             # B17-hold-bias-most-recent-htf-setup (cc05_002 ~22:06): the held state lapses after about six months (126 sessions) [our interpretation: the six-month shift cycle of X3-shift-due-six-months]
    dsmt_bias: bool = False              # B18-htf-daily-smt (cc03_005 ~19:41; cc11_003 ~23:40): the daily ES / NQ SMT (one makes a lower low in the last dsmt_days sessions, the other does not) is the bias when it is 0 (backtest.run with a partner); tag dsmt_trend / dsmt_short by the season
    dsmt_days: int = 18                  # B18-htf-daily-smt (cc03_005 ~19:41): the 15-18 day lookback of the daily SMT (optional extrapolation per the spec)
    im_regime_tag: bool = False          # B19-bond-stock-dxy-sign (cc10_019 ~2:37; cc10_009 ~14:33; cc05_009 ~8:31): tag the orders with the 20-session bond / dollar vs stock correlation signs (INTERMARKET); no gate
    oneway_n: int = 0                    # E4-daily-one-way-delivery-rebalance (cc03_007 ~23:41): >= this many consecutive down-close days after an up-close day U make U's range a draw (mirror); 0 off
    raid_side_gate: bool = False         # X3-iof-60day-framing-raids (cc05_001 ~26:08; cc05_004 ~23:59): column raid_side60 - buy stops taken (20-day highs) over the last 60 sessions raid_ratio x more often than sell stops = bullish: no shorts (mirror)
    raid_ratio: float = 2.0              # ... [our interpretation]
    ipda_draw_side: bool = False         # X3-b21-draw-side-and-flip (cc05_003 ~1:24:00): the lock draws the next 20 / 40 / 60 day extreme on the side of the last daily MSS; a bullish MSS after a 20-day-low raid short of the 40-day low is a quarterly shift +1
    first_clue_neutral: bool = False     # X3-one-sided-delivery-first-clue (cc05_002 ~13:28): the first daily STL break after the HTF buy-side pool was raided (table first_clue) turns the opposing state neutral until the tug of war confirms
    ipda_extreme_pause: bool = False     # X3-60day-low-deep-discount-bounce (cc05_004 ~24:29): a prior low within 0.25 x ADR5 of the 60-day low (or under it) blocks shorts for the session (mirror: highs block longs)
    decoupled_scalp: bool = False        # B19-four-asset-risk-map (cc10_019 ~6:41; cc05_009 ~15:12): the instrument's 20-session trend against the dollar (and commodities when loaded): not in harmony = decoupled (tag), orders are scalps
    # --- Caption-gap pass, package bias_htf#3/7 (digests/rulebook_gaps/bias_htf_intermarket.md items 147, 148, 152, 154, 164, 167, 168, 172-174, 177, 179, 180, 184-190, 195, 197, 198, 200-203, 215, 216, 221, 222, 224-227
    # and day_selection_news_calendar.md item 45; cot.py, bh3.py table side, bh3e.py engine side). Everything defaults off; thresholds the sources never give are [our interpretation]. ------------------------------------
    cot_two_states: bool = False         # B20-cot-zero-line-vs-hedging (cc10_001 ~8:48): tag the two separate COT states, cot_program (sign of the commercial net: the zero line) and cot_hedge (net vs the MID of its 12-month range, MID26 when the range is narrow)
    cot_gate: str = "off"                # ... "hedge_iof": an order is allowed when cot_hedge agrees with its side and the daily iof agrees, whatever cot_program says (no COT data = no gate)
    tandem_scalp: bool = False           # X3-notes-dollar-regime (cc05_006 ~10:16, ~15:57, ~7:11): INTERMARKET notes_dxy = 'tandem' (the 10Y note price and the dollar move the same way over 20 sessions: a large consolidation regime) / 'opposed'; orders on tandem days are scalps
    notes_dxy_tag: bool = False          # ... tag the orders with the notes / dollar regime (tandem_scalp tags it too)
    season_qualified: bool = False       # X3-seasonal-quarterly-qualifier (cc05_007 ~8:04, ~8:22, ~9:04): a seasonal window is QUALIFIED when the daily index SMT (dsmt) agrees with its direction or the notes / dollar regime is 'opposed' (any ONE of the three qualifiers; only the index-relevant ones exist); trades against a qualified window are blocked (needs season_windows)
    stack_tag: bool = False              # X3-full-confluence-stack (cc05_011 ~30:51): tag the orders with the count of agreeing factors (season window, flip state, kill-zone timing, rates, dollar), stack_<n>
    stack_min: int = 0                   # ... 0 = off; skip orders whose stack is below it (position-trade quality: accept few trades)
    swing_gate_runners: bool = False     # X3-swing-two-group-trending-gate (cc06_007 ~9:14; cc06_008 ~5:31): when trend_ok is False (no trending market in {rates, dollar} AND the instrument itself not trending) the orders drop their runners (single target)
    trend_slope_min: float = 0.5         # ... [our interpretation] a market trends when |20-session regression slope| / its mean absolute daily change exceeds this
    bond_lt_tag: bool = False            # X3-bonds-lead-stocks (cc05_009 ~13:48, ~5:14, ~14:18): INTERMARKET bond_lt = -sign(126-session change of the 10Y yield) (the bond price proxy; bonds lead stocks by 6-12 months); tag only
    wpr_daily_tag: bool = False          # B20-williams-r (cc12_002 ~13:41; cc06_007 ~25:49): tag the daily Williams %R(15) reading (0..100 scale, below 50 = oversold / buy area); inside a +-5 band the side most recently left holds. The weekly period is wpr_len (10 / 14 / 20)
    hallmarks_tag: bool = False          # X3-swing-checklist-pipeline (cc06_002 ~0:45; cc06_008 ~30:27): tag hallmarks_<n> = trend_ok, daily iof, rates, season window, an opposing array (draw) in agreement; report_decisions 'M17_hallmarks'. No gate
    profile_gate: bool = False           # X3-htf-market-profile (cc06_001 ~2:43, ~5:34, ~3:52): table column profile (consol / trend / retrace on 52 weekly bars): consol -> scalps without runners; trend -> counter-trend orders blocked; retrace -> with-trend orders need the entry inside a weekly / monthly array
    mwd_tf_test: bool = False            # X3-b10-tf-test (cc06_004 ~3:13; cc06_005 ~1:15): the per-timeframe M / W / D state = a displacement bar (range >= 1.5 x the 10-bar mean, close in the top third) after the last array touch; case A needs HH/HL and the timeframe's iof to agree (otherwise it is B)
    mwd_cancel_case: bool = False        # X3-b10-cancel-condition (cc06_004 ~5:51; cc06_005 ~2:52): case B is cancelled (mwd 0) by a daily bearish breaker formed after a new daily high (case C: weekly); the mirror for a bearish sequential
    mwd_upgrade: bool = False            # X3-b10-case-c-to-b-upgrade (cc06_004 ~17:29): case C becomes B when price is inside a monthly array holding a weekly OB that reacted (a weekly up-close); in case B the open and high of every daily down-close candle since the correction began are exported (mwd_levels)
    mwd_levels_entries: bool = False     # ... the mwd_levels as entry arrays for the HTF-array entries (_ts_arrays; levels, not zones)
    retire_arrays: bool = False          # B17-no-active-array (cc07_001 ~10:33): a daily / weekly array traded through to its far edge is expired and no longer a draw candidate (with skip_no_draw the day is skipped when none remain)
    pause_on_hold: bool = False          # B9-ltf-arrays-break-in-succession (cc07_001 ~14:48): table column held_arrays; when an opposing array touched in the state's run produced a daily close back on the bias-opposing side, want = 0 for the next session [our interpretation of 'a holding array is a reason to pause']
    mw_bookkeeping: bool = False         # B5-monthly-weekly-range-bookkeeping (cc07_001 ~34:13, ~35:56): table columns mo_pd / wk_pd / wk_expand; tags only
    pd60_only_consol: bool = False       # A21-trend-vs-consolidation-first (cc07_005 ~2:14): the pd_day_range (60) body-range premium / discount (pd20 / pd columns) is used only when the range is consolidating (pd60_consol), else 0
    consol_ratio: float = 0.25           # ... [our interpretation of range-bound] |net move| < consol_ratio x the body range
    in_play_gate: bool = False           # B5-htf-arrays-respected-and-in-play (cc09_001 ~3:30; cc08_006 ~21:14): orders need table in_play == side (a daily / 4h array traded into within in_play_days sessions, then a daily close beyond it, daily iof not against) and the room to the opposing array
    in_play_days: int = 3
    in_play_room_pts: float = 5.0        # ... owner #2's 5-point minimum room to the opposing array
    iof_mode: str = "basic"              # B6-iof-checklist-extended (cc08_007 ~6:10; cc10_002 ~5:58): "score" - the bias is the sign of iof_sum (iof_ob_bounce + iof_gap_fill_rally + iof_premium_broken, each +1/-1/0 over the last 10 sessions) when |sum| >= 2
    bias_dh: str = "off"                 # B5-daily-and-4h-bias (cc09_001 ~2:12; cc09_004 ~0:57): "tag" (bias_dh_both / daily_only / 4h_only / conflict) / "both" (daily iof and 4h iof agree with the side) / "either" (one agrees, none opposes)
    ny_continue_london: bool = False     # N9-ny-continues-london (cc09_007 ~7:58): London (02:00-05:00) made the day's high with bearish daily iof and no daily / 4h bull array was touched: the AM lock goes short toward the ADR5 low (high - ADR5, rung adr5); mirror
    pd_needs_iof: bool = False           # A21-discount-not-buy-signal (cc09_008 ~13:20): the 'pd' range-position bias (and the P/D part of combo modes) counts only when the daily iof agrees, else 0
    counter_range_extreme: bool = False  # B3-countertrend-from-range-extreme (cc09_008 ~16:57): against the bias, a counter-trend day trade only at a 20-day range extreme (bottom / top 25 %) after the sweep took a daily pivot low (high): single target at the nearest opposing array inside the range, half risk
    iof_premium_wait: bool = False       # B6-bullish-iof-at-premium-wait (cc09_008 ~23:43): daily iof +1 with the prior close above 75 % of the 20-day range: a long needs its sweep low inside a daily / 4h bull array (mirror)
    fall_low_bias: bool = False          # B23-fall-seasonal-low-setup (cc10_018 ~34:58): the daily ES / NQ SMT in a bullish seasonal window (fall low / spring) with the price below the 60-day EQ = bias +1 until the 60-day high is taken (mirror); used when the bias is 0
    season_poised: bool = False          # B23-market-poised-first (cc10_016 ~1:51; cc11_003 ~4:37): a seasonal window acts only when the market is poised (both indices' 20-session slopes agree, or the daily SMT with the price on the discount side of the 60-day EQ)
    mo_bias_gate: bool = False           # MB-monthly-bias-routine (cc12_001 ~11:22, ~12:08, ~27:01, ~52:52): table column mo_bias (the monthly draw side, held 63 sessions, 84 max); when season window, quarterly objective, rates and SMT / structure all equal it (mo_aligned) every order against it is blocked, scalps included
    q_dir_tag: bool = False              # B22-quarterly-shift-direction (cc12_001 ~20:16): table column q_dir (12 trending monthly closes: the trend sign; else the opposite of the last 4 months); tag, with q_obj_lean the side of an unset quarterly objective
    wk_struct_weight: bool = False       # B10-weekly-structure-control (cc12_002 ~17:43): table column wk_control (the controlling weekly swing tier); an order that does not agree with wk_control and mo_bias trades at half risk (tag wk_struct_agree)
    iof_sponsor_gate: str = "off"        # B6-daily-iof-htf-relative (cc12_003 ~6:01): "tag" / "skip" - orders on days with a non-zero weekly bias need the daily iof to equal it (iof_sponsor)
    chop_lean: bool = False              # B17-chop-revert-middle (031 ~19:39): on a chop / range day only the side toward the pool on the far side of the post-08:30 baseline (the midpoint of the range since 08:30) from price trades (above = longs); a lean, not an entry signal
    chop_target_baseline: bool = False   # ... the baseline is a target rung for counter-moves (a single exit back to the middle; no runners, no extensions)

    def __post_init__(self):
        from .sb_model import check_params as _sb_check   # SB package
        _sb_check(self)
        if self.unicorn_sides not in ("both", "long", "short"):
            raise ValueError(f"unicorn_sides {self.unicorn_sides!r}")
        if self.breaker_zone not in L.BREAKER_MODES:
            raise ValueError(f"breaker_zone {self.breaker_zone!r}")
        if self.breaker_mt_mode not in ("range", "body"):
            raise ValueError(f"breaker_mt_mode {self.breaker_mt_mode!r}")
        # caption-gap pass (levels_detectors #1/3)
        for name, ok in (("ipda_anchor", ("rolling", "daily", "month", "swing", "current_month")), ("bpr_def", ("overlap", "single_range", "both")),
                         ("ob_pick", L.OB_PICKS), ("breaker_candle", L.BREAKER_CANDLES),
                         ("breakaway_def", ("first_after_mss", "context", "second_mss")),
                         ("vi_dead_rule", ("full_span", "overlap")), ("pb_def", L.PB_DEFS),
                         ("rb_level", ("close", "open_close")), ("leg_anchor", ("mss_leg", "energetic"))):
            if getattr(self, name) not in ok:
                raise ValueError(f"{name} {getattr(self, name)!r}: expected one of {ok}")
        for name, ok in (("inversions", ("ob", "breaker", "vi", "org", "nwog")), ("initial_fvg", ("day", "week", "mon10"))):
            if not set(getattr(self, name)) <= set(ok):
                raise ValueError(f"{name} {getattr(self, name)!r}: expected a subset of {ok}")
        if self.pool_tf < 1 or self.shield_passes < 1 or self.diag_min_swings < 3 or self.breakaway_ctx_pts < 0:
            raise ValueError("pool_tf >= 1, shield_passes >= 1, diag_min_swings >= 3, breakaway_ctx_pts >= 0")
        if any(int(m) < 1 for m in self.htf_entry_arrays):
            raise ValueError(f"htf_entry_arrays {self.htf_entry_arrays!r}: minutes >= 1")
        # caption-gap pass (levels_detectors #2/3)
        for name, ok in (("round_pool_mode", ("pool", "confluence", "tag_only")), ("nwog_cfd_src", ("auto", "sunday_bars", "monday_0930", "sunday_else_monday", "none")),
                         ("balance_tf", ("legacy", "own", "next_lower")), ("ir_def", L.IR_DEFS),
                         ("ob_anchor_rule", ("wick_len", "gap_presence")), ("bk_depth", ("ce", "any_open")),
                         ("mit_def", L.MIT_DEFS), ("fs_def", L.FS_DEFS)):
            if getattr(self, name) not in ok:
                raise ValueError(f"{name} {getattr(self, name)!r}: expected one of {ok}")
        for t_ in self.session_ors:
            if len(t_) != 2 or not (0 <= int(t_[0]) < 1440 and int(t_[1]) > 0):
                raise ValueError(f"session_ors {self.session_ors!r}: expected (start_minute, minutes) pairs")
        if (self.round_conf_pts < 0 or self.eng_short_pts < 0 or self.float_denied_bars < 1 or self.float_denied_adr < 0
                or self.ob_anchor_passes < 1 or self.orig_consol_touches < 2 or self.orig_consol_tol_pts < 0
                or self.consol_eq_touches < 0 or self.eq_min_sep_bars < 0 or self.ir_overshoot_ticks < 0 or self.ir_body_mult <= 0):
            raise ValueError("round_conf_pts, eng_short_pts, float_denied_adr, orig_consol_tol_pts, ir_overshoot_ticks >= 0; float_denied_bars, "
                             "ob_anchor_passes >= 1; orig_consol_touches >= 2; consol_eq_touches, eq_min_sep_bars >= 0; ir_body_mult > 0")
        # caption-gap pass (levels_detectors #3/3 review fixes)
        if not set(self.tl_trap_entries) <= {"ob", "breaker"} or self.tl_tol_adr < 0:
            raise ValueError(f"tl_trap_entries {self.tl_trap_entries!r}: expected a subset of ('ob', 'breaker'); tl_tol_adr >= 0")
        if self.tue_open_time not in ("0930", "midnight"):
            raise ValueError(f"tue_open_time {self.tue_open_time!r}: expected '0930' or 'midnight'")
        # caption-gap pass (setups_models #1/7)
        for name, ok in (("po3_seq", ("off", "tag", "filter")), ("ifvg_narrative", ("off", "block", "require")),
                         ("pm_reversal_pool", ("am_high", "lunch_or_am")), ("breaker_break_ref", ("wick", "body_high")),
                         ("mit_entry_px", ("near", "mid"))):
            if getattr(self, name) not in ok:
                raise ValueError(f"{name} {getattr(self, name)!r}: expected one of {ok}")
        if (self.open_tol_pts < 0 or self.po3_seq_below_pts < 0 or self.compressed_k <= 0 or self.compressed_n < 2 or self.pool_runs_max < 0
                or self.judas_max_adr < 0 or not 0 <= self.smt_win_a < self.smt_win_b <= 1440 or not 0 < self.mature_pd < 1
                or self.nfp_release_fvg_min < 1 or self.post_news_run_pts < 0 or self.judas_news_min < 0 or self.breaker_disp_bars < 0):
            raise ValueError("setups_models #1/7: tolerances / counts >= 0, compressed_k > 0, compressed_n >= 2, 0 <= smt_win_a < smt_win_b <= 1440, "
                             "0 < mature_pd < 1, nfp_release_fvg_min >= 1")
        if not self.markets or any(not isinstance(m_, str) for m_ in self.markets):
            raise ValueError(f"markets {self.markets!r}: expected a non-empty tuple of market names")
        # caption-gap pass (setups_models #2/7)
        for name, ok in (("dfvg_half", ("off", "tag", "skip")), ("reclaimed_def", ("strict", "loose")), ("raid_level", ("pdh",)),
                         ("reaper_def", ("fvg", "ob_overlap")), ("sweep_ref", ("wick", "body")), ("or_rb_bear", ("last", "highest_close")),
                         ("smt_mode", ("pair", "three_point")), ("ifvg_depth", (False, True, "w_cap"))):
            if getattr(self, name) not in ok:
                raise ValueError(f"{name} {getattr(self, name)!r}: expected one of {ok}")
        if (self.dfvg_large_pts < 0 or self.nwog_sr_stop_pts < 0 or self.ts_min_beyond_pts < 0 or self.org_sig_adr < 0 or self.micro_range_adr <= 0
                or self.tails_tol_ticks < 0 or self.consol_bars < 2 or self.consol_adr <= 0 or self.daily_first_days < 1 or not 0 <= self.or_rb_from < 1440):
            raise ValueError("setups_models #2/7: dfvg_large_pts / nwog_sr_stop_pts / ts_min_beyond_pts / org_sig_adr >= 0, micro_range_adr > 0, tails_tol_ticks >= 0, "
                             "consol_bars >= 2, consol_adr > 0, daily_first_days >= 1, 0 <= or_rb_from < 1440")
        # caption-gap pass (setups_models #3/7)
        for name, ok in (("leg_grade_gate", ("off", "tag", "require")), ("leg_origin", ("mss_low", "session_low")), ("eq_hunt", ("off", "tag", "prefer")),
                         ("ts_age_rank", ("off", "tag", "prefer")), ("mm_plan", ("", "full", "mss_scalp", "pyramid")), ("vb_entry", ("fill_limit", "close_above", "partial", "full", "auto")), ("consol_eq_mode", ("ob", "eq", "origin_ob")), ("entry_discipline", ("turtle_soup", "ob_return", "range_void", "any")), ("ts_level_src", ("wick", "body")), ("rb_entry", ("", "limit", "stop")), ("ts_r_preset", ("", "cc02_003")), ("clarity", ("off", "tag", "drop")), ("sweep_15m_array", ("off", "tag", "require")), ("consol_edge_fade", ("off", "edge", "inner", "both")), ("consol_edge_entry", ("limit", "market"))):
            if getattr(self, name) not in ok:
                raise ValueError(f"{name} {getattr(self, name)!r}: expected one of {ok}")
        if not set(self.mm_turn_types) <= {"ob", "fvg", "old_high", "old_low", "void"}:
            raise ValueError(f"mm_turn_types {self.mm_turn_types!r}: expected a subset of ('ob', 'fvg', 'old_high', 'old_low', 'void')")
        if (self.wick_depth_bars < 1 or self.shallow_ticks < 0 or self.leg_grade_tol < 0 or self.org_confl_ticks < 0 or not 0 <= self.eq_hunt_band <= 0.5
                or self.vb_min_gap_pts < 0 or self.near_pool_adr < 0 or self.wk_proj_size <= 0 or self.wk_proj_size > 1 or self.ts_linger_bars < 0
                or not 0 < self.ss_t1_frac <= 1 or self.sweep_max_linger < 0 or self.breaker_max_taps_for_entry < 0 or not 0 <= self.lh_freeze_t < 1440
                or self.unicorn_back_bars < 1 or not 0 < self.expansion_bulk <= 1 or not self.wk_proj_k or any(k_ <= 0 for k_ in self.wk_proj_k)
                or not self.premise_tfs or any(m_ not in (15, 30, 60, 240, 1440) for m_ in self.premise_tfs)
                or any(len(w_) != 2 or not 0 <= w_[0] < w_[1] <= 1440 for w_ in self.org_entry_windows)):
            raise ValueError("setups_models #3/7: counts >= 1 / tolerances >= 0, 0 <= eq_hunt_band <= 0.5, 0 < wk_proj_size <= 1, 0 < ss_t1_frac <= 1, 0 < expansion_bulk <= 1, "
                             "wk_proj_k > 0, premise_tfs in (15, 30, 60, 240, 1440), org_entry_windows pairs inside the day, 0 <= lh_freeze_t < 1440")
        # caption-gap pass (setups_models #4/7)
        for name, ok in (("dagger_level", ("ce", "ltf")), ("po3_ideal", ("off", "tag", "require")), ("po3_rest_mgmt", ("none", "normal")), ("m2_anchor", ("leg", "runup")),
                         ("wick_ce_mode", ("close", "intrabar", "retrace")), ("entry_pick", ("first", "shallowest_unused")), ("ob_at_key", ("off", "tag", "require")),
                         ("sick_entry", ("discount", "ob_open", "ote_stack")), ("complete_model", ("off", "tag", "require")), ("lh_array_target", ("ladder", "sd3")), ("lunch_nwog_entry", ("ce", "ob"))):
            if getattr(self, name) not in ok:
                raise ValueError(f"{name} {getattr(self, name)!r}: expected one of {ok}")
        if (self.po3_rest_off_pts < 0 or self.lh_add2_mult <= 0 or self.lh_old_low_stop_pts <= 0 or self.lh_array_sd_k <= 0 or self.pm_old_high_bars < 1 or self.pm_after_room_pts < 0 or self.nwog_fill_tol_pts < 0
                or self.wick_ce_pad_pts < 0 or self.wick_ce_tf not in (0, 5, 15, 30, 60) or self.ob_key_ticks < 0 or self.sick_units < 1 or self.ifvg_sym_bars < 1
                or self.ifvg_tf not in (0, 5, 15) or any(int(m_) < 2 for m_ in self.leg_tfs) or any(int(m_) not in (5, 15, 30, 60) for m_ in self.stab_tfs) or not self.stab_tfs):
            raise ValueError("setups_models #4/7: sizes / distances >= 0 (lh_add2_mult, lh_old_low_stop_pts > 0), pm_old_high_bars / sick_units / ifvg_sym_bars >= 1, wick_ce_tf in (0, 5, 15, 30, 60), "
                             "ifvg_tf in (0, 5, 15), leg_tfs minutes >= 2, stab_tfs in (5, 15, 30, 60)")
        # caption-gap pass (setups_models #5/7)
        for name, ok in (("ifvg_061_entry", ("market", "iofed")), ("false_flag", ("off", "tag", "require")), ("all_pools_first", ("off", "tag", "require")), ("dual_deal", ("", "split", "full")),
                         ("breaker_pref", ("", "last_1m")), ("htf_entry_array", ("off", "tag", "require")), ("mit_entry_tf", ("", "D")), ("mb_order", ("limit", "stop"))):
            if getattr(self, name) not in ok:
                raise ValueError(f"{name} {getattr(self, name)!r}: expected one of {ok}")
        if (self.flag_min_bars < 2 or not 0 < self.flag_max_frac <= 1 or self.po3_15m_n < 1 or self.all_pools_pts < 0 or not set(self.all_pools_names) <= {"london", "prev_ny", "lunch", "prev_pm"}
                or self.breaker_tf < 0 or self.near_miss_pts < 0 or self.max_stop_pts < 0 or self.pd50_tf < 1 or self.overshoot_pts < 0 or self.open_ob_min < 0 or self.td_level_pts < 0
                or self.unicorn_tf not in (1, 5, 15, 60) or not 0 <= self.max_retrace < 1 or self.ifvg_gap_pts < 0 or self.mm_accum_bars < 0 or self.mm_accum_frac <= 0
                or not 0 < self.mm_oc_frac <= 1 or self.reclaim_bounce_bars < 1 or self.mm_lowrisk_reentry not in ("", "extreme", "wick_ce")):
            raise ValueError("setups_models #5/7: flag_min_bars >= 2, 0 < flag_max_frac <= 1, po3_15m_n / pd50_tf / reclaim_bounce_bars >= 1, distances >= 0, all_pools_names a subset of "
                             "(london, prev_ny, lunch, prev_pm), unicorn_tf in (1, 5, 15, 60), 0 <= max_retrace < 1, mm_accum_frac > 0, 0 < mm_oc_frac <= 1")
        if self.ndog_scalp and not self.asia_session:
            self.asia_session = True           # new-ndog-asian-scalp: the scalp needs the evening window
        if self.mm_plan:                       # M1-three-entry-plans: the umbrella forces the paths it names (ONE-WAY: ob_entry / mmxm_ctx / add_on_vi stay forced after replace(p, mm_plan=""); set them back explicitly)
            self.ob_entry = "post_mss" if self.mm_plan == "mss_scalp" else "pre_break"
            if self.mm_plan == "full":
                self.mmxm_ctx = True
            elif self.mm_plan == "pyramid":
                self.add_on_vi = True
        # caption-gap pass (levels_detectors #3/3)
        if self.ipda_anchor == "daily":
            self.ipda_anchor = "rolling"       # B21-anchor-month-vs-daily: "daily" is the rolling count from yesterday
        for name, ok in (("gap_views", ("auto", "both")), ("nwog_holiday_pick", ("all", "closest")),
                         ("wick_lod_tag", ("off", "tag", "require")), ("london_lr_zone", ("off", "tag", "require"))):
            if getattr(self, name) not in ok:
                raise ValueError(f"{name} {getattr(self, name)!r}: expected one of {ok}")
        if self.daily_level_needs_array not in (False, True, "any", "fvg"):
            raise ValueError(f"daily_level_needs_array {self.daily_level_needs_array!r}: expected False / True / 'any' / 'fvg'")
        if self.or_minutes not in (0, 20, 30, 60):
            raise ValueError(f"or_minutes {self.or_minutes!r}: expected one of 0, 20, 30, 60")
        if not self.ipda_windows or not set(self.ipda_windows) <= {20, 40, 60, 63, 126, 252}:
            raise ValueError(f"ipda_windows {self.ipda_windows!r}: expected a non-empty subset of (20, 40, 60, 63, 126, 252)")
        if not set(self.week_raid_days) <= {0, 1, 2, 3, 4}:
            raise ValueError(f"week_raid_days {self.week_raid_days!r}: weekdays 0-4")
        if not isinstance(self.tf_lookback, dict) or any(k not in ("D", "W", "4h", "1h", "30m", "15m") or int(v) < 1
                                                          for k, v in self.tf_lookback.items()):
            raise ValueError(f"tf_lookback {self.tf_lookback!r}: {{'D' / 'W' / '4h' / '1h' / '30m' / '15m': trading days >= 1}}")
        if (self.wick_weeks < 1 or self.parent_n < 1 or self.tl_tol_ticks < 0 or self.hs_tf < 1 or self.hs_stop_pts < 0
                or self.ipda_beyond_days < 0 or (self.or_expire and not 570 < self.or_expire <= 975)):
            raise ValueError("wick_weeks, parent_n, hs_tf >= 1; tl_tol_ticks, hs_stop_pts, ipda_beyond_days >= 0; or_expire 0 or 571..975")
        if self.vi_dead_rule == "overlap" or self.vi_two_sided_draw:
            self.vi_body_death = True      # A9: the body death rules (full_span / overlap) and the two-sided draw both need it (replace() re-runs this)
        for name, ok in (("news_wait", ("range", "fixed", "off")), ("draw_lock", ("session", "off")),
                         ("draw_lock_neutral", ("skip", "both")), ("draw_lock_levels", ("frozen", "live")),
                         ("draw_lock_pick", ("nearest", "ordered", "largest")),
                         ("ob_entry", ("pre_break", "post_mss", "both")),
                         ("ob_entry_px", ("body_top", "mt", "range_top", "open", "high")), ("ob_arm", ("leave", "touch", "intrabar_htf")),
                         ("ob_stop", ("mt", "ext")), ("risk_basis", ("fixed", "equity")),
                         ("price_frame", ("front_month", "back_adjusted", "raw")),
                         ("sloppy_mode", ("off", "stand_aside", "scalp")),
                         ("year_end", ("december", "long", "tag", "off")),
                         ("year_end_map", ("squaring", "with")), ("am_exit_mode", ("close", "tighten")),
                         ("sb_target_mode", ("draw", "fixed")), ("runner_htf_exit", ("", "15m", "30m", "1h")),
                         ("turtle_soup", ("", "2023", "cc_limit", "cc_1h_ob", "or60", "external", "htf_stab", "prev_pm")),
                         ("ts_entry", ("array", "level")), ("round_pool_from", ("session", "midnight")), ("ts_stop", ("array", "gap", "ext", "mid")),
                         ("stop_flip", ("off", "breaker", "smt")),
                         # levels_detectors
                         ("ipda_eq_day", ("off", "tag", "skip")), ("mss_ref", ("stl", "itl", "ltl", "parent", "origin", "origin_max")),
                         ("ipda_session", ("rth", "eth")),
                         ("mss_ref_fallback", ("lower", "highest", "none")),
                         ("pd_hl_session", ("rth", "eth")), ("matrix_days", ("bot", "ict")),
                         ("org_draw", ("off", "tag", "draw")), ("wick_session", ("rth", "eth")),
                         ("wick_react", ("off", "tag", "require")), ("gap_pool_edge", ("far", "ce")),
                         ("release_open_stop", ("", "open", "wick_ce")),
                         ("bias_open", ("midnight", "0830", "0930", "all")), ("bias_open_src", ("data", "spy", "es_map")),
                         ("breakaway", ("off", "tag", "hold", "next_fvg")),
                         ("breaker_cand_to", ("ext", "h")), ("breaker_time", ("off", "hl2", "all")),
                         ("breaker_entry", ("off", "fallback", "prefer", "classic")),
                         ("eq_pref", ("off", "rank", "require")),
                         ("imm_rebalance_disp", ("off", "or", "require")),
                         # setups_models
                         ("mss_on_side", ("off", "tag", "require")), ("mm_context", ("off", "tag", "require")),
                         ("three_drives", ("off", "tag", "require")), ("unicorn_entry", ("edge", "overlap")),
                         ("cc_swings", ("off", "breaker", "failure", "both")), ("ifvg_entry", ("edge", "ce", "quadrant")),
                         ("ote", ("off", "filter", "limit", "ob62")), ("smt_pick", SMT_PICKS),
                         ("news_profile", ("off", "tag", "require", "pool_test")), ("nfp_sd", ("off", "tag", "skip")),
                         ("candle_draw_bias", ("off", "daily", "weekly")),
                         ("ob_pre_gate", ("off", "cancel", "hold")), ("cc_profile", ("off", "tag", "gate"))):
            if getattr(self, name) not in ok:
                raise ValueError(f"{name} {getattr(self, name)!r}: expected one of {ok}")
        for name, ok in (("fomc_am", ("open", "recipe", "skip")), ("fomc_only_am", ("off", "tag", "scalp", "skip")),
                         ("fomc_observe", ("off", "defer", "judas")), ("pre_cpi", ("off", "small", "skip")),
                         ("news_judas", ("off", "block", "wait")), ("or_bias", ("off", "judas", "close")),
                         ("pm_continue_am", ("off", "tag", "filter")), ("pm_ob_entry", ("off", "tag", "require")),
                         ("macro_only", ("off", "0950", "all")), ("macro_by", ("arm", "start")),   # news_calendar_times
                         ("two_driver_mode", ("off", "tag", "wait2", "skip")), ("multi_release", ("off", "tag", "skip", "half")),
                         ("fomc_minutes_mode", ("allow", "block", "pm_only")), ("post_fomc_am", ("open", "skip", "symmetry")),
                         ("fomc_whipsaw_skip", ("off", "london", "am")), ("am_search_sb", ("exempt", "include")),
                         ("macro_fail_windows", ("am", "all")), ("macro_fail_scope", ("session", "day")),
                         ("lunch_raid", ("off", "recent", "am_low", "post_news", "first_of")),
                         ("am_session", ("default", "0830_1200"))):                      # caption-gap pass news_calendar_times#1/1
            if getattr(self, name) not in ok:
                raise ValueError(f"{name} {getattr(self, name)!r}: expected one of {ok}")
        if self.am_session == "0830_1200":                   # caption-gap T5-am-session-to-noon (044 ~00:55:47; 073 ~00:14:36): the AM from 08:30 (the Ep01.10 snapshot) to 12:00
            self.am_from_0830 = True
            self.am = (self.am[0], 720)
        if any(k not in ("0950", "1050", "1150", "1330", "1450", "1515") for k in self.macro_gate_set):
            raise ValueError(f"macro_gate_set {self.macro_gate_set!r}: entries must be keys of nct2.MACRO_SET")
        if self.fomc_whip_frac < 0 or self.pre_fomc_week_mult <= 0 or self.am_search_minutes < 0 or self.chop_wait_bars < 0:
            raise ValueError("news_calendar_times#1/1: fomc_whip_frac >= 0, pre_fomc_week_mult > 0, am_search_minutes >= 0, chop_wait_bars >= 0")
        for name, ok in (("pre_cpi_mon", ("off", "tag", "gap", "skip_small")), ("post_holiday_am", ("off", "skip", "symmetry")),
                         ("august_mode", ("off", "skip", "light")), ("season_quality", ("off", "tag", "size")),
                         ("skip_election", ("off", "two_weeks", "narrow")), ("holiday_eve_cases", ("a", "ab")),
                         ("objective_done_pm", ("off", "reversal_only")), ("sd_intraday", ("off", "tag", "rules")),
                         ("nwog_templates", ("off", "tag", "gate")), ("fri_one_sided", ("off", "tag", "raid_first")),
                         ("season_windows", ("off", "tag")), ("mon_how", ("off", "tag", "gate")), ("mon_how_edge", ("low", "ce")),
                         ("wk_profile", ("off", "tag")), ("day_profile", ("off", "tag"))):          # caption-gap pass day_week_context#1/3
            if getattr(self, name) not in ok:
                raise ValueError(f"{name} {getattr(self, name)!r}: expected one of {ok}")
        if (self.pre_cpi_gap_adr < 0 or self.landmine_min < 0 or self.holiday_week_mult <= 0 or self.season_march_mult <= 0 or not 0 <= self.season_min_rank <= 1
                or self.objective_frac_gate < 0 or self.sd_intraday_frac < 0 or self.sd_shallow_frac < 0 or self.big_day_am_resume < 0 or self.tgif_weeks < 1
                or self.iw_k <= 0 or self.fri_t1_pts <= 0 or self.season_move_adr <= 0 or self.season_autumn_start not in (9, 10)):
            raise ValueError("day_week_context#1/3: fractions / multiples >= 0 (holiday_week_mult, season_march_mult > 0), season_min_rank in [0, 1], tgif_weeks >= 1, season_autumn_start 9 or 10")
        # caption-gap pass (day_week_context#2/3)
        for name, ok in (("consolidation_mode", ("skip", "range_trade", "fade_with_htf", "scalp")), ("expansion_mode", ("off", "tag", "full")), ("days_mode", ("all", "mon_wed", "tue_wed"))):
            if getattr(self, name) not in ok:
                raise ValueError(f"{name} {getattr(self, name)!r}: expected one of {ok}")
        if (self.consol_range_days < 1 or self.mon_big_frac < 0 or self.expansion_judas_adr < 0 or (self.tgif_reversal_pct is not None and not 0 < self.tgif_reversal_pct < 1) or self.fri_trail_from < 0 or self.adr_runner_until <= 0
                or self.adr_runner_until > 1440 or (self.tgif_zone and self.tgif_reversal_pct is not None and self.tgif_reversal_pct < self.tgif_cap)):
            raise ValueError("day_week_context#2/3: consol_range_days >= 1, mon_big_frac >= 0, 0 < tgif_reversal_pct < 1 (and >= tgif_cap with tgif_zone), fri_trail_from >= 0, 0 < adr_runner_until <= 1440")
        # caption-gap pass (day_week_context#3/3)
        for name, ok in (("tgif_window", ("off", "am", "london_close", "pm")), ("tgif_precond", ("strict", "loose")), ("missed_week_mode", ("off", "nearest", "skip")),
                         ("checklist", ("off", "tag", "gate"))):
            if getattr(self, name) not in ok:
                raise ValueError(f"{name} {getattr(self, name)!r}: expected one of {ok}")
        if (self.choppy_week_days < 1 or self.tgif_min_adr < 0 or self.bisi_ce_band < 0 or self.fav_pts <= 0 or self.pm_narr_gap_pts < 0 or self.max_trades_month < 0 or self.weekly_target_pct < 0
                or self.weekly_cap_pts < 0 or self.trend_k <= 0 or self.tgif_consol_frac < 0 or self.aug_dd_stop_pct < 0 or self.low_mag_mult <= 0 or self.low_mag_week_cap < 0
                or not 0 <= self.tgif_pm_from <= 1440 or any(not 1 <= m_ <= 12 for m_ in tuple(self.skip_months) + tuple(self.low_mag_months)) or set(self.cl_days) - {0, 1, 2, 3, 4}):
            raise ValueError("day_week_context#3/3: choppy_week_days >= 1, fractions / caps / percentages >= 0, fav_pts > 0, trend_k > 0, low_mag_mult > 0, 0 <= tgif_pm_from <= 1440, months 1-12, cl_days weekdays 0-4")
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
        for name, ok in (("entry", ENTRY_MODES + ("far_on_breaker", "auto2")), ("sb_entry", ENTRY_MODES[:-1]), ("iofed_ref", ("c2_high", "tick", "q75")),
                         ("run_cancel", ("t1", "last", "off")), ("entry_order", ("limit", "stop_cc", "market_on_touch")),
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
        bad = set(self.entry_arrays) - {"ob", "breaker", "ote", "wick_ce", "vi", "reclaimed_ob", "cons_ob_open", "bpr_ce", "ob_post", "htf", "mitigation", "ob_secondary", "propulsion", "last_offer", "or_ref", "broken_wick_ce", "vi_ob"}
        if bad:
            raise ValueError(f"entry_arrays {sorted(bad)}")
        bad = set(self.void_trades) - {"fill", "range", "cont", "void_fill_gap"}
        if bad:
            raise ValueError(f"void_trades {sorted(bad)}")
        bad = set(self.entry_arrays_order) - {"ob", "breaker", "ote", "wick_ce", "vi", "reclaimed_ob", "cons_ob_open", "bpr_ce", "ob_post", "htf", "mitigation", "ob_secondary", "propulsion", "last_offer", "ob62", "broken_wick_ce", "vi_ob"}
        if bad:
            raise ValueError(f"entry_arrays_order {sorted(bad)}")
        if (self.consol_max_pts <= 0 or self.void_idle_bars < 1 or self.ts_cont_bars < 1 or self.cc_ob_tf not in (5, 15, 60) or any(int(m) not in (5, 15, 60) for m in self.refine_tfs)
                or self.cc_ob_offset_ticks < 0 or self.breaker_retests < 1 or self.breaker_leave_pts < 0 or self.vb_react_bars < 1 or self.offer_run < 2 or self.offer_step_pts < 0
                or self.clarity_overlap <= 0 or self.sweep_leave_bars < 0 or self.sweep_leave_pts < 0 or self.consol_tf not in (5, 15, 60) or self.consol_width_adr <= 0
                or not 0 < self.consol_eq_band < 0.5):
            raise ValueError("setups_models #6/7: consol_max_pts > 0; void_idle_bars, ts_cont_bars, breaker_retests, vb_react_bars >= 1; offer_run >= 2; cc_ob_tf / refine_tfs / consol_tf in (5, 15, 60); "
                             "cc_ob_offset_ticks, breaker_leave_pts, offer_step_pts, sweep_leave_bars, sweep_leave_pts >= 0; clarity_overlap, consol_width_adr > 0; 0 < consol_eq_band < 0.5")
        # caption-gap pass (setups_models #7/7)
        for name, ok in (("combine_prefer", ("none", "es")), ("lc_mode", ("failure_swing", "mss")), ("trail_reentry_entry", ("ifvg_ce", "breaker")),
                         ("reentry_trigger", ("new_array", "sibi_return")), ("reentry_stop", ("array", "wick_ce", "ob_low")),
                         ("reverse_after_failure", ("off", "inversion", "at_stop", "prop_fail", "sick_sister", "all")),
                         ("allow_opposite_after_target", ("off", "lod", "split", "both")), ("m0950_branch", ("off", "tag", "rev", "cont", "both")),
                         ("cc09_gate", ("off", "tag", "gate")), ("pairing", ("all", "expansion_ob", "retracement_void", "reversal_pool", "consolidation_eq"))):
            if getattr(self, name) not in ok:
                raise ValueError(f"{name} {getattr(self, name)!r}: expected one of {ok}")
        if (self.max_exec_markets < 0 or self.nq_overshoot_mult <= 0 or self.lc_adr_mult <= 0 or self.lc_adr_k <= 0 or self.lc_stop_pts < 0 or not 0 < self.lc_retrace < 1
                or not 0 < self.lc_retrace_mss < 1 or not 0 < self.lc_oneside < 1 or self.missed_leave_pts < 0 or self.or_ref_reuse < 1 or self.or_ref_near_pts < 0
                or self.consol_exit_min < 0 or (self.ts_breaker_add_mult is not None and self.ts_breaker_add_mult <= 0) or self.missed_lon_ratio <= 0 or self.reentry_win_max < 1 or self.trail_reentry_max < 1 or self.reentry_risk_mult <= 0
                or self.reverse_risk_mult <= 0 or self.offside_frac <= 0 or self.lod_conf_pts < 0 or self.reentry_max < 1 or self.reentry_mult <= 0
                or self.cc09_room_pts < 0 or self.cc09_scalp_pts < 0 or self.cc09_depart_bars < 1 or self.nyx_target_pct <= 0 or self.nyx_stop_pct <= 0 or self.nyx_max < 1
                or not 0 <= self.nyx_start < 600 or self.skip_pm_adr_k <= 0):
            raise ValueError("setups_models #7/7: max_exec_markets, lod_conf_pts, missed_leave_pts, or_ref_near_pts, consol_exit_min, cc09_room_pts, cc09_scalp_pts, lc_stop_pts >= 0; "
                             "nq_overshoot_mult, lc_adr_mult, lc_adr_k, ts_breaker_add_mult, reentry_risk_mult, reverse_risk_mult, offside_frac, reentry_mult, nyx_*_pct > 0; "
                             "0 < lc_retrace, lc_retrace_mss, lc_oneside < 1; or_ref_reuse, reentry_win_max, trail_reentry_max, reentry_max, cc09_depart_bars, nyx_max >= 1; 0 <= nyx_start < 600")
        # caption-gap pass (entries_stops_sizing #1/3)
        for name, ok in (("entry_pd_frame", ("leg", "prev_day", "prev_ny", "any")), ("cisd_ob_px", ("eq", "open")), ("mt_break", ("off", "close", "trade", "warn")),
                         ("gap_tf_mode", ("", "refine_down", "widen_up")), ("vi_tol", ("none", "ce", "adjacent_extreme")), ("prop_mt_test", ("close", "wick")),
                         ("leg_pd_anchor", ("displacement_leg", "target", "retrace_range")), ("broken_wick_stop", ("body_edge", "swing")), ("fvg_edge", ("original", "remaining")),
                         ("leg_fib", ("wick", "body")), ("htf_ob_anchor", ("open", "extreme")), ("ob_mt_range", ("body", "range")), ("ob_reach", ("wick", "body")),
                         ("mt_mode", ("body", "range", "sensitive", "body_single_range_blended"))):
            if getattr(self, name) not in ok:
                raise ValueError(f"{name} {getattr(self, name)!r}: expected one of {ok}")
        if (self.vi_tol_small_pts < 0 or self.prop_deep_mult < 0 or not 0 < self.prop_deep_cut < 1 or self.ob_ce_tol_pts < 0 or len(self.htf_depth_mult) != 3
                or any(m_ < 0 for m_ in self.htf_depth_mult) or not self.scan_tfs or any(int(m_) < 1 for m_ in self.scan_tfs)):
            raise ValueError("entries_stops_sizing #1/3: vi_tol_small_pts, prop_deep_mult, ob_ce_tol_pts >= 0; 0 < prop_deep_cut < 1; htf_depth_mult three multipliers >= 0; scan_tfs minutes >= 1")
        # caption-gap pass (entries_stops_sizing #2/3)
        from . import es2 as _es2_check
        _es2_check.check_params(self)
        from . import es3 as _es3_check                  # caption-gap pass (entries_stops_sizing #3/3)
        _es3_check.check_params(self)
        from . import tp1 as _tp1_check                  # caption-gap pass (targets_partials #1/4)
        _tp1_check.check_params(self)
        from . import tp2 as _tp2_check                  # caption-gap pass (targets_partials #2/4)
        _tp2_check.check_params(self)
        from . import tp3 as _tp3_check                  # caption-gap pass (targets_partials #3/4)
        _tp3_check.check_params(self)
        _tp3_check.derive_pool_exit(self)
        from . import tp4 as _tp4_check                  # caption-gap pass (targets_partials #4/4)
        _tp4_check.derive(self)
        _tp4_check.check_params(self)
        from . import me1 as _me1_check                  # caption-gap pass (management_exits #1/3)
        _me1_check.check_params(self)
        from . import me2 as _me2_check                  # caption-gap pass (management_exits #2/3)
        _me2_check.check_params(self)
        from . import me3 as _me3_check                  # caption-gap pass (management_exits #3/3)
        _me3_check.check_params(self)
        _me3_check.apply_presets(self)
        if self.e4_color and self.retrace_candle == "off":
            self.retrace_candle = "intrabar"          # E4 candle colour = the built retrace_candle "intrabar" (a short fills on an up-close bar: the fill bar opens beyond the limit and trades into it)
        if self.vi_ob_entry and "vi_ob" not in self.entry_arrays:
            self.entry_arrays = tuple(self.entry_arrays) + ("vi_ob",)
        if any(len(w_) != 2 or not 0 <= w_[0] < w_[1] <= 1440 for w_ in self.missed_kz):
            raise ValueError(f"missed_kz {self.missed_kz!r}: expected (start_minute, end_minute) pairs")
        for name in ("london_close", "lc_fs_win", "lunch_macro_win", "lunch_long_win"):
            w_ = getattr(self, name)
            if len(w_) != 2 or not 0 <= w_[0] < w_[1] <= 1440:
                raise ValueError(f"{name} {w_!r}: expected (start_minute, end_minute)")
        if len(self.adv_rung_fracs) != 3 or any(f_ <= 0 for f_ in self.adv_rung_fracs) or abs(sum(self.adv_rung_fracs) - 1.0) > 1e-6:
            raise ValueError(f"adv_rung_fracs {self.adv_rung_fracs!r}: three positive fractions summing to 1")
        if self.two_session_smt and self.smt_windows and not any(a_ <= 720 and b_ >= 810 for a_, b_ in self.smt_windows):
            self.smt_windows = tuple(self.smt_windows) + ((720, 810),)          # T13: the lunch-low vs post-13:00-low pair is part of the switch (empty smt_windows = SMT at any time already covers it)
        if not set(self.ts_sessions) <= {"AM", "PM", "LUNCH", "PRE7", "PRE8", "PRE9", "NEWS", "LON"}:
            raise ValueError(f"ts_sessions {self.ts_sessions!r}: session names (AM / PM / LUNCH / PRE7 / PRE8 / PRE9 / NEWS / LON)")
        bad = [x for x in self.pm_nest_tfs if x not in CF_TFS]
        if bad or not self.pm_nest_tfs:
            raise ValueError(f"pm_nest_tfs {self.pm_nest_tfs!r}: expected names from {CF_TFS}")
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
                         ("measuring_anchor", ("far", "near", "ce", "dup")), ("mm_anchor", ("leg", "ref", "reanchor", "impulse")),
                         ("wick_read", ("off", "exit")), ("wick_session", ("rth", "eth")),
                         ("sd_anchor", ("leg", "sweep_leg", "broken", "downleg", "fulcrum", "london", "manip", "multi", "fulcrum_week", "entry_low", "m15_leg", "mss_leg")),
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
                         ("ladder_trail", ("fvg", "hit", "prior", "off", "measuring", "breakaway", "candle_mt", "eq_pause", "rej_block", "071", "structure", "rolling_bpr")),
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
        # package day_week_context: validation and the TGIF model master switch
        for name, ok in (("b11_inside_week", ("off", "tag", "scalp")), ("b11_inside_expansion", ("off", "tag", "no_chop_skip")),
                         ("outside_day_rule", ("off", "tag", "block")), ("nr_expansion", ("off", "tag", "no_chop_skip")),
                         ("org_tell", ("off", "tag", "filter")), ("org_bias_gap", ("off", "tag", "filter")),
                         ("org_bias_src", ("react", "draw", "pd")), ("sunday_scenario", ("off", "tag", "filter")),
                         ("holiday_week_thu_fri", ("off", "trade")), ("low_vol_inside", ("off", "tag", "scalp", "skip")),
                         ("adr_basis", ("rth", "eth")), ("trend_recipe", ("off", "tag", "only", "side")),
                         ("consol_day_rules", ("off", "tag", "apply")), ("sd_week_skip", ("off", "tag", "skip")),
                         ("raid_ref", ("pd", "london")), ("on_range_from", ("midnight", "globex")),
                         ("monday_mode", ("trade", "skip", "pm_only", "obvious", "big_into_array")), ("tue_off_monday", ("off", "tag", "filter", "ote")),
                         ("mon_wed_extreme", ("off", "tag")), ("thu_fri_break", ("off", "tag", "side")),
                         ("friday_objective", ("off", "tag", "scalp", "skip")), ("friday_week_done", ("off", "draw", "trades")),
                         ("tue_week_extreme", ("off", "tag", "side")), ("daily_range_regime", ("off", "tag", "scalp", "skip")), ("week_done_on_draw", ("off", "tag", "skip")),
                         ("week_done_pick", ("any", "nearest")), ("roll_week_src", ("calendar", "data", "either"))):
            if getattr(self, name) not in ok:
                raise ValueError(f"{name} {getattr(self, name)!r}: expected one of {ok}")
        if (set(self.nr_tags) - {"nr3", "nr7", "inside_body"} or set(self.trend_news) - {"high", "medium"}
                or set(self.consol_predictors) - {"no_report", "htf_array", "htf_50", "holiday_eve", "auction"}
                or set(self.consol_pm_pools) - {"pd", "london", "on", "draw"}
                or set(self.tgif_model_skip) - {"tgif", "tgif_zone", "tgif_htf_array", "tgif_week_sweep", "tgif_timing"}
                or set(self.drr_tests) - {"range", "inside_bisi", "premium_run"}
                or set(self.week_done_levels) - {"pwh", "pwl", "nwog_ce"} or set(self.tgif_htf_tfs) - set(CF_TFS)):
            raise ValueError("day_week_context: nr_tags / trend_news / consol_predictors / week_done_levels / tgif_htf_tfs name an unknown item")
        if len(self.seasonal_map) != 12 or (self.seasonal_map_b and len(self.seasonal_map_b) != 12):
            raise ValueError("seasonal_map / seasonal_map_b: expected 12 entries, January first")
        if (self.roll_risk <= 0 or self.august_risk <= 0 or not 1 <= self.august_from_day <= 31 or self.london_adr_skip < 0
                or self.min_on_range_frac < 0 or self.min_raid_pts < 0 or self.monday_small_range < 0
                or self.am_range_skip_pm < 0 or self.b11_inside_week_days < 1 or self.consol_min_predictors < 1
                or not 0 < self.org_tell_level <= 1 or not 0 < self.org_gap_fill_frac <= 1 or self.macro_ref_min < 1
                or self.year_first_am_from < 0 or self.first_day_wait < 0 or self.trend_array_days < 1
                or self.drr_days < 3 or not 0 < self.drr_net_frac <= 1 or self.drr_range_mult <= 0):
            raise ValueError("day_week_context: risk multipliers > 0, ADR fractions >= 0, day / minute counts >= 1 (or 0 = off)")
        for name in ("macro_no_move_wins", "macro_no_move_pm_wins", "tgif_timing", "london_adr_win"):
            w = getattr(self, name)
            if name == "london_adr_win":
                w = (w,)
            if any(len(x) != 2 or x[0] >= x[1] for x in w):
                raise ValueError(f"{name} {getattr(self, name)!r}: expected (start_minute, end_minute) windows")
        if self.tgif_model:                          # M14: the umbrella switches the sub-switches on (replace() re-runs this)
            for nm_ in ("tgif", "tgif_zone", "tgif_htf_array", "tgif_week_sweep"):
                if nm_ not in self.tgif_model_skip:
                    setattr(self, nm_, True)
            if not self.tgif_timing and "tgif_timing" not in self.tgif_model_skip:
                self.tgif_timing = ((600, 720), (810, 900))     # 10:00-12:00 (London close) and 13:30-15:00 (PM)
        # package bias_htf: validation and the umbrellas (replace() re-runs this)
        for name, ok in (("htf_bias", ("off", "react", "draw", "pd", "combo", "flip", "ordered", "iof", "combo2", "ob_mt", "mwd",
                                       "nwog", "candle", "draw_pd", "wk", "pd20", "week_pre", "week_check", "wd_check")),
                         ("bias_neutral", ("skip", "both", "scalp", "scalp_week")), ("judas_required", ("off", "tag", "filter")),
                         ("draw_first", ("off", "session")), ("day_pd", ("swing", "20d")),
                         ("pd_zone", ("half", "third", "deep", "ote")), ("weekly_gate", ("off", "tag", "filter")),
                         ("news_topdown", ("off", "tag", "side")), ("bellwether_15m", ("off", "tag", "filter")),
                         ("how_rule", ("off", "tag", "no_long", "no_short", "both")), ("objective_neutral", ("off", "day", "week", "both")),
                         ("objective_met_stop", ("off", "day", "week", "both")), ("mwd_nest", ("off", "tag", "filter")),
                         ("weekly_open", ("off", "sun18", "mon00", "either")), ("nwog_regime", ("off", "tag", "scalp", "skip")),
                         ("nwog_bias", ("off", "tag", "filter")), ("nwog_bias_reclaim", ("", "low", "ce", "high")), ("nwog_flip_edge", ("high", "low")),
                         ("neutral_gate_mode", ("tag", "skip", "scalp")), ("neutral_5050", ("off", "armed", "react")), ("nwog_converge_mode", ("near", "shrink")),
                         ("chop_mode", ("off", "skip", "skip_day", "scalp")), ("decoupled_mode", ("off", "tag", "scalp", "skip")),
                         ("smt_both", ("off", "tag", "skip")), ("bias_candle", ("D", "W")), ("bias_candle_open", ("session", "midnight")),
                         ("mmbm_zone", ("off", "tag", "filter")), ("dxy_gate", ("off", "tag", "block")),
                         ("bond_range", ("off", "tag", "scalp", "skip")), ("bond_dir", ("off", "tag", "filter")),
                         ("cot_tag", ("off", "tag", "filter")), ("oi_tag", ("off", "tag")), ("wpr_tag", ("off", "tag", "filter")),
                         ("midnight_confirm", ("off", "tag", "filter"))):
            if getattr(self, name) not in ok:
                raise ValueError(f"{name} {getattr(self, name)!r}: expected one of {ok}")
        if (set(self.neutral_gate) - {"fifty_fifty", "premium_chop", "draw_delivered", "range_market", "decoupled"}
                or set(self.draw_first_skip) - {"pick", "hygiene", "ext", "cond"}
                or set(self.intermarket_model_skip) - {"dxy_gate", "bond_range", "bond_dir", "decoupled_mode"}
                or set(self.cot_oi_model_skip) - {"cot_tag", "oi_tag", "wpr_tag"}):
            raise ValueError("bias_htf: neutral_gate / draw_first_skip / intermarket_model_skip / cot_oi_model_skip name an unknown item")
        if (self.iof_days < 3 or self.iof_min < 1 or self.pd_day_range < 3 or len(self.ote_band) != 2
                or not 0 <= self.ote_band[0] < self.ote_band[1] <= 1 or self.bias_persist < 0 or self.nof_days < 1
                or self.mwd_disp_mult <= 0 or self.weekly_open_early_days < 1 or self.weekly_open_array_days < 1 or self.nwog_leave_adr <= 0
                or self.nwog_returns_cons < 1 or self.nwog_converge_pts < 0 or self.chop_on_adr < 0
                or not 0 < self.fifty_react_ratio <= 1 or self.judas_min_pts < 0
                or self.decouple_days < 3 or self.dxy_gate_days < 3 or self.bond_range_days < 3
                or not 0 < self.bond_range_frac <= 1 or self.oi_days < 1 or self.oi_pct <= 0 or self.wpr_len < 2
                or self.qshift_size <= 0 or self.qs_due_lo < 1 or self.qs_due_hi < self.qs_due_lo):
            raise ValueError("bias_htf: day counts >= 1 (3 for ranges), fractions in (0, 1], ote_band (lo, hi) inside [0, 1]")
        if self.draw_first == "session":              # L14 / L14a umbrella
            sk = self.draw_first_skip
            self.draw_lock = "session"
            if "pick" not in sk:
                self.draw_lock_pick = "ordered"
            if "hygiene" not in sk and "htf" not in self.target_hygiene:
                self.target_hygiene = tuple(self.target_hygiene) + ("htf",)
            if "ext" not in sk:
                self.draw_ext_target = True
            # cond_draw is NOT part of the umbrella (review fix): the owner has not confirmed the failure definition (L14e)
        if self.intermarket_model:                    # B19 umbrella
            for nm_, val_ in (("dxy_gate", "block"), ("bond_range", "scalp"), ("bond_dir", "filter"), ("decoupled_mode", "scalp")):
                if nm_ not in self.intermarket_model_skip:
                    setattr(self, nm_, val_)
        if self.cot_oi_model:                         # B20 umbrella: tags only (optional enhancers, cc06_002 ~0:24)
            for nm_ in ("cot_tag", "oi_tag", "wpr_tag"):
                if nm_ not in self.cot_oi_model_skip:
                    setattr(self, nm_, "tag")
        # caption-gap pass bias_htf#1/7 (bh1.py / bh1e.py)
        for name, ok in (("drange_break", ("close", "wick")), ("b7_mode", ("mt_close", "mt_trade", "ob_close")), ("nwog_ref", ("current", "previous")),
                         ("nwog_bias_basis", ("px", "close")), ("inval_src", ("off", "array", "manual")), ("dxy_filter", ("off", "tag", "soft", "hard")),
                         ("draw_order", ("nearest", "nearest_tb", "inefficiency_first")), ("bisi60_hold", ("off", "trade", "close"))):
            if getattr(self, name) not in ok:
                raise ValueError(f"{name} {getattr(self, name)!r}: expected one of {ok}")
        if self.bellwether_tf not in (0, 15, 60) or self.iof_tf not in (0, 5, 15, 30, 60, 240):
            raise ValueError("bellwether_tf: 0 / 15 / 60; iof_tf: 0 or a bar size of 5 / 15 / 30 / 60 / 240 minutes")
        if (self.drange_n < 3 or self.drange_t1_pts <= 0 or self.drange_day_pts <= 0 or self.lean_n < 1 or self.lean_tol_pts < 0 or not 0 < self.org_attempt_frac <= 1
                or self.org_tell_skip_min < 0 or not 570 < self.org_tell_end <= 720 or not 0 < self.dxy_soft_risk <= 1 or self.low_in_min_highs < 1 or self.low_in_ratio <= 0
                or not 0 < self.giveback_frac < 1):
            raise ValueError("bias_htf#1/7: drange_n >= 3, drange_t1_pts / drange_day_pts > 0, lean_n >= 1, lean_tol_pts >= 0, org_attempt_frac in (0, 1], org_tell_skip_min >= 0, "
                             "org_tell_end in (570, 720], dxy_soft_risk in (0, 1], low_in_min_highs >= 1, low_in_ratio > 0, giveback_frac in (0, 1)")
        if self.htf_monthly:
            self.htf_monthly_arrays = True        # BH-A5-HTF-FVG-own-timeframe: the named alias of the built monthly arrays
        # caption-gap pass bias_htf#2/7 (bh2.py / bh2e.py)
        for name, ok in (("pd3_result", ("flip", "neutral")), ("consol_dir", ("off", "first_expansion", "prior_strongest")), ("htf_after_draw", ("neutral", "reverse")),
                         ("htf_bias_tf", ("D", "W", "M")), ("tier_stl_mode", ("last2", "two_of_four"))):
            if getattr(self, name) not in ok:
                raise ValueError(f"{name} {getattr(self, name)!r}: expected one of {ok}")
        if (not 0 < self.scalp_week_risk <= 1 or self.q_window_size <= 0 or not 0 < self.soft_carry_risk <= 1 or not 0 < self.iof_w_risk <= 1 or self.q_window_lo < 0 or self.q_window_hi < self.q_window_lo
                or self.q_obj_days < 1 or self.iof_w_weeks < 3 or self.release_pts < 0 or self.fast_draw_mult <= 0 or self.pd3_disp_adr <= 0 or not 0 < self.consol_chase_frac <= 0.5
                or not 0.5 < self.range_no_bias_pct < 1 or not 0 <= self.eq_tie_frac < 0.5 or self.raid_profile_n < 1 or self.flip_max_days < 1 or self.dsmt_days < 2
                or self.oneway_n < 0 or self.raid_ratio <= 0 or not 0 <= self.qshift_strong_pct < 1):
            raise ValueError("bias_htf#2/7: scalp_week_risk / soft_carry_risk / iof_w_risk in (0, 1], q_window_size > 0, 0 <= q_window_lo <= q_window_hi, q_obj_days >= 1, iof_w_weeks >= 3, release_pts >= 0, fast_draw_mult > 0, "
                             "pd3_disp_adr > 0, consol_chase_frac in (0, 0.5], range_no_bias_pct in (0.5, 1), eq_tie_frac in [0, 0.5), raid_profile_n >= 1, flip_max_days >= 1, dsmt_days >= 2, oneway_n >= 0, "
                             "raid_ratio > 0, qshift_strong_pct in [0, 1)")
        # caption-gap pass bias_htf#3/7 (bh3.py / bh3e.py / cot.py)
        for name, ok in (("cot_gate", ("off", "hedge_iof")), ("iof_mode", ("basic", "score")), ("bias_dh", ("off", "tag", "both", "either")), ("iof_sponsor_gate", ("off", "tag", "skip"))):
            if getattr(self, name) not in ok:
                raise ValueError(f"{name} {getattr(self, name)!r}: expected one of {ok}")
        if self.stack_min < 0 or self.stack_min > 5 or self.trend_slope_min <= 0 or self.in_play_days < 1 or self.in_play_room_pts < 0 or not 0 < self.consol_ratio <= 1:
            raise ValueError("bias_htf#3/7: 0 <= stack_min <= 5, trend_slope_min > 0, in_play_days >= 1, in_play_room_pts >= 0, consol_ratio in (0, 1]")
        if self.htf_bias_tf == "M":
            self.htf_monthly_arrays = True        # B5-monthly-first-hierarchy: the monthly draw needs the monthly arrays
        inert = []                                  # switches the current draw_lock / vi_arrays make inert
        if (self.draw_lock_pick != "nearest" or self.draw_ext_target or self.cond_draw) and self.draw_lock != "session":
            inert.append("draw_lock_pick / draw_ext_target / cond_draw act only in the #9 lock (draw_lock='session')")
        if self.htf_bias == "off" and (self.bias_persist or self.next_array_on_fail or self.objective_neutral != "off"):
            inert.append("bias_persist / next_array_on_fail / objective_neutral reshape the htf_bias reading: inert with htf_bias='off'")
        if (self.htf_bias != "off" and self.draw_lock == "off"
                and (self.pre_0700 or self.pre_0900 or self.pre_0820 or self.ma_deuce or self.sb_model)):
            inert.append("htf_bias with draw_lock='off': a window before 09:30 has no bias row (the 09:30 table would look ahead), "
                         "so with bias_neutral='skip' those windows are skipped")
        if self.news_topdown != "off" and not self.vi_arrays:
            inert.append("news_topdown needs vi_arrays=True (the daily VI rows)")
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
        # caption-gap pass (levels_detectors #2/3)
        if self.ir_def != "a7" and not (self.ir_entries or self.imm_rebalance_disp != "off"):
            inert.append("ir_def acts through ir_entries (M11a) or imm_rebalance_disp")
        if self.vi_breakaway and not (self.vi_entries or self.vi_targets or "vi" in self.entry_arrays):
            inert.append("vi_breakaway acts on the VI entry zones / entry_arrays 'vi' / vi_targets")
        if (self.bk_state or self.bk_depth != "ce" or self.bk_bpr_ce) and not (self.breakaway != "off" or self.trail_breakaway
                                                                               or self.ladder_trail == "breakaway"):
            inert.append("bk_depth / bk_state / bk_bpr_ce act on the breakaway tag, trail_breakaway and ladder_trail='breakaway'")
        if self.nwog_rebalanced and self.gap_mode != "ict":
            inert.append("nwog_rebalanced needs gap_mode='ict' (the NWOG table)")
        if self.ceiling_ladder and not self.vi_arrays:     # caption-gap pass bias_htf#1/7 (review round 1): the documented couplings
            inert.append("ceiling_ladder: the VI ceilings need vi_arrays=True (the ladder otherwise reads FVGs only)")
        if self.bellwether_15m != "off" and self.bellwether_tf:
            inert.append("bellwether_15m (the original midpoint test) and bellwether_tf (the swing-break test) are two readings of B5: both apply when both are set")
        if self.htf_bias == "off" and (self.qshift_bias or self.dsmt_bias or self.raid_profile_bias or self.eq_tiebreak or self.htf_bias_tf != "D" or self.wk_q75_confirm       # caption-gap pass bias_htf#2/7: the documented couplings
                                       or self.htf_after_draw == "reverse" or self.fast_draw_extend):
            inert.append("qshift_bias / dsmt_bias / raid_profile_bias / eq_tiebreak / htf_bias_tf / wk_q75_confirm / htf_after_draw / fast_draw_extend reshape the htf_bias reading: inert with htf_bias='off'")
        if (self.pd3_result == "neutral" or self.pd3_first_caution) and "flip_pd3" not in self.flip_triggers:
            inert.append("pd3_result / pd3_first_caution act on the flip_pd3 trigger: add it to flip_triggers")
        if (self.flip_terminus or self.first_clue_neutral or self.pd3_result == "neutral") and self.htf_bias != "flip":
            inert.append("flip_terminus / first_clue_neutral / pd3_result change the stateful `flip` column: read with htf_bias='flip' (or the flip-based sessions rules)")
        if self.inside_bisi_release and "inside_bisi" not in self.sloppy_tests:
            inert.append("inside_bisi_release lifts the inside_bisi sloppy test: add it to sloppy_tests")
        if (self.soft_carry or self.q_obj_lean or self.ipda_draw_side or self.wick_ce_60m or self.sibi15_ce_cancel or self.allow_reversal_after_target) and self.draw_lock != "session":
            inert.append("soft_carry / q_obj_lean / ipda_draw_side / wick_ce_60m / sibi15_ce_cancel / allow_reversal_after_target act on the draw lock (draw_lock='session')")
        if self.tug_required and not self.tier_regime_gate:      # caption-gap pass bias_htf#2/7 review round 2
            inert.append("tug_required narrows tier_regime_gate: inert without it")
        if self.ipda_draw_side and not (self.ipda_pools or self.ipda_next):
            inert.append("ipda_draw_side picks among the IPDA pools: add ipda_next (or ipda_pools)")
        if self.htf_after_draw == "reverse" and self.objective_neutral == "off":
            inert.append("htf_after_draw='reverse' replaces the objective-met neutral: set objective_neutral to 'day', 'week' or 'both'")
        if self.htf_bias_pools and self.htf_bias_tf == "D":
            inert.append("htf_bias_pools shapes the monthly / weekly bias reading: set htf_bias_tf to 'W' or 'M'")
        if self.tier_stl_mode != "last2" and not self.tier_regime_gate:
            inert.append("tier_stl_mode acts on the tier regime: set tier_regime_gate")
        if (self.pause_on_hold or self.pd_needs_iof or self.fall_low_bias or self.htf_bias in ("week_pre", "week_check", "wd_check")) and self.htf_bias == "off":     # caption-gap pass bias_htf#3/7: the documented couplings
            inert.append("pause_on_hold / pd_needs_iof / fall_low_bias reshape the htf_bias reading: inert with htf_bias='off'")
        if self.pause_on_hold and self.htf_bias != "flip":
            inert.append("pause_on_hold counts held arrays inside the flip state's run: read it with htf_bias='flip' (the table's flip column)")
        if (self.season_qualified or self.season_poised) and self.season_windows == "off":
            inert.append("season_qualified / season_poised act on the seasonal windows: set season_windows")
        if self.pd60_only_consol and (self.pd_day_range != 60 or not self.pd_body_multiday):
            inert.append("pd60_only_consol is the 60-session body-range rule: set pd_day_range=60 and pd_body_multiday")
        if self.counter_range_extreme and self.counter_scalp:
            inert.append("counter_range_extreme (kind 'ctr') is ignored while counter_scalp is on: the counter scalp is not limited to the range extreme")
        if self.ny_continue_london and self.draw_lock != "session":
            inert.append("ny_continue_london acts on the AM draw lock (draw_lock='session')")
        if self.q_dir_tag and self.q_obj_lean and self.draw_lock != "session":
            inert.append("q_dir_tag with q_obj_lean leans the draw lock (draw_lock='session')")
        if self.chop_lean and not (self.sloppy_tests or "range_market" in self.neutral_gate):
            inert.append("chop_lean / chop_target_baseline act on chop days: set sloppy_tests (chop) or neutral_gate 'range_market'")
        if self.mwd_levels_entries and not self.mwd_upgrade:
            inert.append("mwd_levels_entries needs mwd_upgrade (the table's mwd_levels)")
        if self.iof_mode == "score" and not (self.htf_bias in ("iof", "combo2") or self.needs_iof_col):
            inert.append("iof_mode='score' rewrites the daily iof column: read it with htf_bias 'iof' / 'combo2' or a switch that reads iof")
        if inert:
            warnings.warn("inert switches: " + "; ".join(inert), stacklevel=3)

    # --- package day_week_context helpers ------------------------------------------------------
    @property
    def dw_needs_eth(self) -> bool:
        """The day_week_context switches that read full (all-hours) sessions: backtest.prepare then builds the eth dict."""
        return bool(self.tgif_htf_array or self.week_done_on_draw != "off" or self.friday_week_done == "draw"
                    or self.friday_objective != "off" or self.adr_basis == "eth" or self.pool_mon_wed
                    or self.mon_wed_extreme != "off" or self.thu_fri_break != "off" or self.thu_reversal_tag or self.thu_reversal_trade)

    @property
    def dw_needs_eve(self) -> bool:
        """The switches that read the evening session (18:00-24:00) before the day (futures / CFDs with overnight bars)."""
        return bool(self.sunday_scenario != "off" or self.eve_draw or self.pre_draw_pm or self.on_range_from == "globex"
                    or self.week_pools)       # (caption-gap new-intra-week-extreme-raid: the Sunday evening is part of the week so far)

    @property
    def needs_iof_col(self) -> bool:
        """caption-gap bias_htf#3/7: a switch beyond htf_bias reads the daily iof column."""
        from . import bh3
        return bh3.needs_iof(self)

    @property
    def bx(self) -> str:
        """package bias_htf: the htf.table configuration these switches need (bias_htf.bx_string)."""
        from . import bias_htf
        return bias_htf.bx_string(self)

    @property
    def dw1_hist(self) -> int:
        """Sessions of history the day_week_context#1/3 switches need (the seasonal windows and the 252-session trend, five monthly closes): 0 = the default."""
        return 270 if (self.season_windows != "off" or self.mo_overdue) else 0

    @property
    def dw2_hist(self) -> int:
        """Sessions of history the day_week_context#2/3 switches need (the 60-session ADR5 tercile and the 60-day EQ): 0 = the default."""
        return 66 if (self.adr_contracted_tag or self.trend_side_rule) else 0

    @property
    def dw_needs_week(self) -> bool:
        """The switches that read the week's trade state (backtest.week_state)."""
        return bool(self.max_trades_week or self.friday_week_done == "trades" or self.stall_at_htf or self.late_week_flat or _DWC3.needs_week(self))

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
    return p.risk_dollars if p.risk_dollars is not None else p.risk_pct * eq * p.alloc_frac      # caption-gap E8-alloc-30pct: the risk percent applies to alloc_frac of the equity


def _total_cap(p: "Params", eq: float) -> float:
    return p.max_total_risk if p.max_total_risk is not None else p.max_total_risk_pct * eq * p.alloc_frac


def _first_units(p: "Params", eq: float, risk: float, entry: float, risk_mult: float = 1.0,
                 extra_cap: float = 0.0) -> int:
    """Owner #12: the first unit risks risk_pct (1.2%) of equity, never more than the total cap.
    extra_cap (E9 size_up_cap_pct x equity) raises the cap for an order a size-up rule fired on."""
    if p.fixed_units > 0:
        return _ES3.fixed_first_units(p)                  # caption-gap E8-new-trader-drill / -graduation: exactly N contracts whatever the equity
    if p.alloc_frac != 1.0:
        _ES3.hit("alloc_frac")                            # (executed-path counter: the first unit was sized on the allocation fraction)
    return _lots(min(risk_mult * _risk_budget(p, eq) / risk, (_total_cap(p, eq) + extra_cap) / risk,
                     _ES3.notional_cap(p, eq) / abs(entry)), p.lot)


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
            if not (p is not None and p.holiday_week_thu_fri == "trade" and d.weekday() in (3, 4)
                    and _calendar.holiday_in_week(d)) \
                    and not (p is not None and p.holiday_nfp_override and w == 3 and _calendar.holiday_mon_wed(d)):          # N7.3: holiday weeks deliver cleaner Thu / Fri (caption-gap N7-holiday-week 072 ~00:04:19: holiday_nfp_override - a holiday on Mon-Wed of NFP week frees the Thursday)
                return "nfp_week_thu_fri"
        if w == 2 and (session == "PM" or (p is not None and p.nfp_wed_cutoff and t >= p.nfp_wed_cutoff)):
            return "nfp_week_wed_pm"                 # caption-gap N2-nfp-wed-after-11 (101 ~01:29:18): the Wednesday cutoff minute (11:00; test 12:00) - AM-family entries from it are blocked too
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
        if not _calendar.nfp_date(d) and not any("fomc" in events(x) for x in week) and not _DWC.landmine_exempt(d, p):      # (caption-gap D20-landmine-week-monday 064 ~00:10:18: landmine_min releases Tue-Fri)
            return "monday"
    if p is not None:
        why = _NC.calendar_block(d, session, p, t)
        why = why if why is not None else _DWC.calendar_block(d, session, p, t)         # caption-gap pass day_week_context#1/3: skip_election, summer_off
        why = why if why is not None else _DWC2.calendar_block(d, session, p, t)        # caption-gap pass day_week_context#2/3: days_mode
        return why if why is not None else _DWC3.calendar_block(d, session, p, t)       # caption-gap pass day_week_context#3/3: skip_months
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
    init_fvg_respected: str = ""   # caption-gap N-initial-fvg-reference: "day:respected|week:untested|..." as of the entry
    org_dir: str = ""              # caption-gap L7-org-close-and-direction: "discount" / "premium" - the opening range gap's direction at the entry (from 09:30)
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
    # package day_week_context#1/3
    wk_profile: str = ""           # M17-weekly-profiles-selection: the week's profile at the entry (classic_tue_low / wed_low / consol_thu_reversal / mon_how / none)
    news_tags: str = ""            # the day's news tags: nfp, nfp_week, fomc, fomc_only, fomc_eve, fomc_after, cpi, pre_cpi,
                                   # two_driver, fed_chair, auction, claims, minutes (newscal.day_tags)

    # package day_week_context (daycontext.stamp): the day's tags and the journal columns (reporting only)
    dw_tags: str = ""              # "|"-joined: holiday_eve, post_holiday, holiday_week, inside_day, outside_down, nr7, tgif, consol_day, ...
    week_idx: int = 0              # N7.2: the trading-day number within the week (a Monday holiday makes Tuesday 1)
    adr5_prev: float | None = None   # X16: ADR5 (points) known at the day start
    adr_prev: float | None = None    # X16a: yesterday's range / the ADR5 before it
    adr5_today: float | None = None  # X16: today's whole-session range / ADR5 (study only: known after the close)
    adr_fill: float | None = None    # X16a: the range from the day's first bar to the fill bar / ADR5
    taken_3d: int | None = None      # X16b: how many of the last 3 days' highs / lows were taken at the fill
    prev3_taken: str = ""            # X16 / X16b: which ("pdh1|pdl2 ...")
    entry_array_tf: str = ""         # X16 / X16d: chart timeframe, ">tf" the highest higher-timeframe array holding the entry
    seasonal: str = ""               # B23: bull / bear / cons / split (":fail", ":htf_agree" / ":htf_against")
    eve_draw_px: float | None = None     # N9.2: the draw at the prior close (engine frame)
    eve_draw_side: int = 0
    eve_draw_done: bool | None = None    # delivered before 09:30
    # SB package (sb_model.py): the Silver Bullet trade tags (entry_kind carries the entry array: fvg / ifvg / ifvg_breaker / ob / conf)
    sb_win: str = ""               # window: london / am / pm / lh / moc / 0700
    sb_n: int = 0                  # nth Silver Bullet entry of its window (1 = first)
    sb_sweep_depth: float | None = None   # M3.5: ES pts the leg low ran beyond the swept level (None: no sweep)
    sb_pre_run_ticks: float | None = None  # gap 17: ticks the market ran beyond the draw before the fill
    # package setups_models #1/7 (caption-gap pass; every tag stays empty / None while its switch is off)
    open_grade: str = ""           # B12 open_tol_pts: "best" (beyond every reference open) / "allowed" (inside the wrong-side tolerance)
    po3_seq: bool = False          # B12 po3_seq: the Judas -> close back across the open -> MSS order held
    wk_open_side: int = 0          # B13 wk_open_side: sign(entry - the week's Sunday 18:00 open)
    touch_n: int | None = None     # touch_tag: touches of the swept level since it formed (the sweep included)
    judas_depth: float | None = None   # judas_max_adr: (reference open - the sweep extreme) / ADR5 (side terms; 0 when not beyond the open)
    array_depth: float | None = None   # D15 smt_pick "depth": how deep the sweep ran into the HTF array (0..1)
    array_respect: float | None = None  # ... the share of 15m bodies inside the array that stayed on the far side of its edge
    clean_swing: bool | None = None    # D15 smt_pick "clean_swing": a 15m pivot (n=2) between the entry and T1
    move_pct: float | None = None  # D15 smt_pick "middle": the move from the session open to the fill, in the trade direction (fraction)
    lc_reversal: bool = False      # lc_tag: a 10:00-12:00 reversal off an HTF array against the morning
    # package setups_models #2/7 (caption-gap pass)
    setup_model: str = ""          # new-price-engine-models (cc09_006): OA / OD (a sweep-driven order: old-low sweep then the premium array / old-high sweep then the discount array), RA / RD (a retrace into an array)
    delivery: str = ""             # A2-delivery-vs-liquidity (104 ~11:24): "up" / "down" - the sign of the last displacement leg in the trade's direction terms at the order
    div_type: str = ""             # div_tag: "type1" (classic) / "type2" (hidden) stochastic divergence at the order
    gap_count: int | None = None   # D15 smt_pick "clean" (setups_models #4/7): the number of same-side FVGs of the leg between its EQ and its extreme (1 = one clean obvious gap)
    obj_met_t: object = None       # D15 smt_pick "laggard_objective": when this instrument's OWN htf.table draw was first traded (end of that bar); None = not met / not asked
    # package setups_models #5/7 (caption-gap pass)
    laggard: bool = False          # management_exits #3/3 new-laggard-slow-delivery (laggard_mult): the leader index had already reached its draw before this fill (set at the fill)
    entry_style: str = ""          # M12-new-trader-no-turtle-soup: "raid" (a turtle-soup / pre-break entry at the run of a pool) / "confirmed" (displacement, swing taken and FVG first)
    # package setups_models #7/7 (caption-gap pass)
    cc09: str = ""                 # OT-M17-cc09_001-checklist: "|"-joined names of the failing checklist items (iof / react / room / open / depart; m15 / wpr15 are tag-only); "" = all held
    state: str = ""                # OT-one-state-tool-pairing: the session state at the order (consolidation / expansion / retracement / reversal); stamped while pairing != "all"
    # package targets_partials #1/4 (caption-gap pass)
    resist: str = ""            # BH-L4-resistance-definitions: "high" / "low" resistance of the run (resist_def)
    swing_grade: int = 0           # new-swing-grades: the entry's grade 1-4 in the swing sweep extreme .. leg high (swing_grade_tag)
    near_miss: bool = False        # targets_partials #3/4 X2-projection-target-1tick-before (proj_kind): the best price fell within 1 pt short of a projection rung that did not fill
    # package targets_partials #4/4 (caption-gap pass; empty / None while the switch is off)
    rr_final: float | None = None  # L15-min-rr-3 / new-rr-month-gate: the reward to the final target / the risk at the order (recorded with min_rr_final or rr_month_gate)
    stage_pts: float = 0.0         # OT-target-progression: the staged fixed target (ES pts) the trade ran with
    half_range_ok: bool | None = None   # X3-half-range-runner-success: the runner's exit reached half the range to the final level (set when any targets_partials #4/4 ladder state exists)
    capture_b: float | None = None      # X3-best-case-80-85-capture (capture_zone): realised average exit distance / the distance to the zone's best case B
    strength: str = ""            # new-strength-no-return-discount-array (strength_hold): "strong" (a new high without a return into OB1) / "normal"
    # package management_exits #1/3 (caption-gap pass)
    mgmt_tags: str = ""           # management_exits #1/3: the "|"-joined tags set DURING the trade (nwog_traverse, lod_in, heavy, heavy_scale, lunch_hold, thu_cap, rt_stall, hold_lost, bpr_warn, strength_read, rip, stall, breakaway_refusal, best_case, sd_window, event_lock) - not an entry column
    resist_speed: str = ""        # L4-resistance-is-delivery-speed (resistance_def "speed"): "low" (the first rung came within resist_speed_bars bars of the fill) / "high" (later or never)
    # package entries_stops_sizing #1/3 (caption-gap pass)
    mt_warn: bool = False         # D4-mt-source-tally mt_break "warn": price traded under the OB MT after the fill (a warning, not the failure) - set during the trade, so it is no entry column
    # package day_week_context#3/3 (caption-gap pass; None / "" while the switch is off)
    min_to_fav: float | None = None    # OT-X16-time-to-move-journal (journal_timing): minutes fill -> the first bar whose favourable excursion reached fav_pts
    min_to_exit: float | None = None   # ... minutes fill -> the final exit
    first_exit_kind: str = ""          # ... "stop" / "target" / "other" (the first exit)
    mfe_pts: float | None = None       # ... maximum favourable excursion after the fill (ES pts)
    mae_pts: float | None = None       # ... maximum adverse excursion (ES pts, <= 0)
    cl_fail: str = ""                  # OT-pre-session-checklist-order (checklist): the failing step names of the trade's session, "" = all green

    REAL_FIELDS = ("entry", "stop", "t1", "t2", "draw_px", "bz_top", "bz_bottom", "bz_mt",
                   "resist_lo", "resist_hi", "ext_px", "leg_hi_px", "eve_draw_px")

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
                 vi_min_gap: float = 0.0, mit_legacy: bool = False, single_bar: float = 0.0,
                 vi_wick_overlap: bool = True, vi_multi: bool = False, bpr_def: str = "overlap",
                 bpr2_two_candle: bool = False, pb_def: str = "a16", mit_mt: bool = False, vi_dead_rule: str = "full_span",
                 mit_def: str = "a15", ir_cfg: tuple = ("a7", 2.0, 1.5)):
        self.sign = sign
        if sign > 0:
            self.o, self.h, self.l, self.c = o, h, l, c
        else:
            self.o, self.h, self.l, self.c = -o, -l, -h, -c
        self.ph, self.pl = L.pivots(self.h, self.l, n)
        self.c2_dir = c2_dir                  # A5 fvg_c2_dir (levels_detectors)
        self.vi_min_gap = vi_min_gap          # A9 vi_min_gap_pts (price units)
        self.mit_legacy = mit_legacy          # A15 mit_legacy_order (review fix: a Params switch)
        self.single_bar = single_bar          # A5 caffeine bar (single_bar_fvg_strict): c2 range multiple, 0 = no tag
        self.vi_wick_overlap, self.vi_multi = vi_wick_overlap, vi_multi        # A9 vi_wick_overlap / vi_multi
        self.bpr_def, self.bpr2_two_candle = bpr_def, bpr2_two_candle         # A11 Type 1 / Type 2
        self.pb_def = pb_def                                                   # A16
        self.vi_dead_rule = vi_dead_rule                                       # A9 vi_dead_rule (intraday Side VIs)
        self.mit_mt = mit_mt                                                   # A12 mit_mt_invalid: mitigation blocks carry their MT
        self.mit_def = mit_def                                                 # A15 mit_def (levels_detectors #2/3): "a15" / "stoprun"
        self.ir_cfg = ir_cfg                                                   # A7 ir_def, overshoot ticks, body multiple
        self.gaps = [z for z in L.fvgs(self.h, self.l, self.o, self.c, c2_dir, single_bar)
                     if z.kind == "bull" and z.top - z.bottom >= min_gap]
        self.min_gap = min_gap
        self.sweep = None
        self.n = n
        self._ifvg = self._opp = self._mit = self._prop = None
        self._lz = {}                         # levels_detectors lazily built arrays
        self.td_mask = None                   # caption-gap new-time-distortion: per-bar mask (ld4.attach_td) - zones / swings defined on a masked bar are dropped

    def _lazy(self, key, fn):
        if key not in self._lz:
            v = fn()
            self._lz[key] = v if self.td_mask is None else _LD4.td_filter(self.td_mask, v)
        return self._lz[key]

    def tiers(self):
        """A1: {"stl"|"itl"|"ltl": (highs, lows)} in side space."""
        return self._lazy("tiers", lambda: L.swing_tiers(self.h, self.l, self.n))

    def vis(self, kind: str = "bull"):
        """A9 volume imbalances of one kind in side space ("bull" = support, "bear" = above)."""
        return self._lazy("vi_" + kind, lambda: [z for z in L.volume_imbalances(self.o, self.h, self.l, self.c,
                                                                                  self.vi_min_gap, self.vi_wick_overlap,
                                                                                  self.vi_multi) if z.kind == kind])

    def bprs(self, max_gap: int = 0):
        """A11 balanced price ranges (both kinds), side space. Caption-gap `bpr_def`: "overlap" = Type 1 (a bullish and a
        bearish FVG overlap), "single_range" = Type 2 (a gap crossed both ways in one pass, then left: known - and only
        returned - once it is BALANCED, i = the balancing bar), "both" = the two lists together."""
        def build():
            t1 = L.balanced_ranges(self.h, self.l, max_gap, self.o, self.c, self.c2_dir)   # review fix: A5 c2 rule
            if self.bpr_def == "overlap":
                return t1
            forms = ("gap", "range") + (("two_candle",) if self.bpr2_two_candle else ())
            t2 = [L.Zone(z.tag, z.top, z.bottom, z.bi, z.src, tag="bpr2", bi=z.bi)
                  for z in L.single_pass_bprs(self.o, self.h, self.l, self.c, forms, max(self.n, 1)) if z.bi >= 0]
            return sorted((t1 if self.bpr_def == "both" else []) + t2, key=lambda z: z.i)
        return self._lazy(("bpr", max_gap, self.bpr_def, self.bpr2_two_candle), build)

    def irs(self, tick: float):
        """A7 immediate rebalances (bull kind, side space): candle indices."""
        cfg = getattr(self, "ir_cfg", ("a7", 2.0, 1.5))        # caption-gap A7 ir_def (ld3.attach)
        return self._lazy(("ir", tick, cfg), lambda: [k for k, kd in L.immediate_rebalances(self.o, self.h, self.l, self.c, tick, *cfg)
                                                      if kd == "bull"])

    def ir_info(self, tick: float) -> dict:
        """A7 review fix #85: {k: (bound level, displacement candle d)} of the bull immediate rebalances (side space), same detector as irs()."""
        cfg = getattr(self, "ir_cfg", ("a7", 2.0, 1.5))
        return self._lazy(("irx", tick, cfg), lambda: {k: (b, d) for k, kd, b, d in L.immediate_rebalances_ex(
            self.o, self.h, self.l, self.c, tick, *cfg) if kd == "bull"})

    def opp_mits(self):
        """A15 opposing (bearish, side space) mitigation blocks - targets above a long."""
        return self._lazy("opp_mit", lambda: [z for z in L.mitigation_blocks(self.o, self.h, self.l, self.c, self.n,
                                                                             self.mit_legacy, self.mit_mt, getattr(self, "mit_def", "a15"))
                                              if z.kind == "bear"])

    def implied(self):
        """A24.1 implied FVGs (bull kind, side space; setups_models implied_fvg)."""
        return self._lazy("implied", lambda: [z for z in L.implied_fvgs(self.o, self.h, self.l, self.c)
                                              if z.kind == "bull" and z.top - z.bottom >= self.min_gap])

    # lazily built arrays (only the switches that use them pay for them)
    def ifvgs(self):
        if self._ifvg is None:
            self._ifvg = _LD4.td_filter(self.td_mask, [z for z in L.inversion_fvgs(self.h, self.l, self.c, self.min_gap) if z.kind == "bull"])
        return self._ifvg

    def opposing(self):
        """Bearish FVGs and voids (resistance above, in side terms), for targets."""
        if self._opp is None:
            self._opp = [z for z in L.fvgs(self.h, self.l, self.o, self.c, self.c2_dir) + L.voids(self.h, self.l)
                         if z.kind == "bear" and z.top - z.bottom >= self.min_gap]
            self._opp = _LD4.td_filter(self.td_mask, self._opp)
        return self._opp

    def mitigations(self):
        if self._mit is None:
            self._mit = [z for z in L.mitigation_blocks(self.o, self.h, self.l, self.c, self.n, self.mit_legacy, self.mit_mt,
                                                        getattr(self, "mit_def", "a15")) if z.kind == "bull"]
            self._mit = _LD4.td_filter(self.td_mask, self._mit)
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
                out.append(L.Zone("bull", ob.top, ob.bottom, int(last[z.i]), int(first[ob.src]), ob.mt, levels=(float(o[ob.src]),)))   # (levels[0] = the OB's open: caption-gap A12-ob-anchor-level)
        out = _LD4.td_filter(self.td_mask, out)
        cache[m] = out
        return out

    def propulsions(self):
        """The propulsion blocks. pb_def "cc04_008" step (1), the bullish context: dropped while the current bias is AGAINST this side
        [our interpretation: an unknown / neutral bias does not test the context]."""
        if self.pb_def == "cc04_008" and getattr(self, "ctx_bias", 0) == -self.sign:
            return []
        if self._prop is None:
            obs = []
            for g in self.gaps:
                ob = L.order_block_blend(self.o, self.h, self.l, self.c, g.i - 4, g.i - 2, "bull")
                if ob is not None and self.c[g.i - 1] > ob.top:
                    obs.append(L.Zone("bull", ob.top, ob.bottom, g.i, ob.src, ob.mt))
            self._prop = L.propulsion_blocks(self.o, self.h, self.l, self.c, obs, self.pb_def)
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
                 evening: pd.DataFrame | None = None, tf_lookback: dict | None = None):
        prev = hist[-1]
        self.day, self.tf = day, tf
        frame = pd.concat([prev, df])
        self.idx = frame.index
        self.t = (self.idx.hour * 60 + self.idx.minute).values
        self.o, self.h, self.l, self.c = (frame[k].values.astype(float) for k in ("open", "high", "low", "close"))
        self.start = len(prev)
        self.v = frame["volume"].values.astype(float) if "volume" in frame.columns else None      # caption-gap new-volume-divergence-exit (cc10_006): the bars' volume (None without it)
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
        self.org_dates = []                    # caption-gap L7 org_both_ways: the formation date of each ORG
        self.org_today = False                 # True when the last ORG is today's (09:30-based)
        seq = hist[-6:] + [df]
        for a, b in zip(seq[:-1], seq[1:]):
            rth = b[(b.index.hour * 60 + b.index.minute) >= 570]
            if len(rth) and len(a):
                pc = (closes or {}).get(a.index[0].date(), float(a.close.iloc[-1]))
                self.org.append((float(pc), float(rth.open.iloc[0])))
                self.org_dates.append(b.index[0].date())
                self.org_today = b is df
        # opening range 09:30 -> 09:30 + or_minutes: high/low usable once it is complete
        self.or_end, self.or_hl = 570 + or_minutes, None
        orb = df[(tt >= 570) & (tt < 570 + or_minutes)] if or_minutes else df.iloc[:0]
        if len(orb):
            self.or_hl = (float(orb.high.max()), float(orb.low.min()))
        o20 = df[(tt >= 570) & (tt < 590)]         # caption-gap T4-or-length: OR20 (09:30-09:50) is always built (the macro branch reads it whatever or_minutes is)
        self.or20 = (float(o20.high.max()), float(o20.low.min())) if len(o20) else None
        self.wbias = weekly_bias(hist, day)
        # caption-gap definitions_pd_arrays_structure #206 (cc08_002 ~9:32): "New York" = the IPDA true day 00:00-15:00 - its close is the close of the bar that ends at 15:00 (not the 16:00 session close);
        # known only once that bar has closed (index `ny_close_i`; read it through dwc2.true_day(ctx, i))
        self.ny_close_1500 = None
        self.ny_close_i = None
        self.true_day_hl = None
        td_ = np.flatnonzero((tt >= 0) & (tt < 900))
        k_ = np.flatnonzero(tt == 900 - tf)
        if len(td_):
            self.true_day_hl = (float(df.high.values[td_].max()), float(df.low.values[td_].min()))
        if len(k_):
            self.ny_close_1500 = float(df.close.values[k_[0]])
            self.ny_close_i = len(prev) + int(k_[0])
        # higher-timeframe FVGs over the last 5 sessions, in real prices, with the time known
        self.hzones = []
        if htf:
            # caption-gap new-lookback-per-tf-topdown (cc01_003 ~18:23): tf_lookback {"15m": 4, "1h": 15, "4h": 63} (trading days) replaces the 5-session
            # window of the 15m / 60m / 4h FVGs - the zones are built on the longest window and each timeframe keeps the ones completed inside its own
            lbm = {m_: int((tf_lookback or {}).get(lab_, 5)) for m_, lab_ in ((15, "15m"), (30, "30m"), (60, "1h"), (240, "4h"))}
            nmax = max([5] + [lbm.get(m_, 5) for m_ in htf])
            full = pd.concat(hist[-nmax:] + [df])
            self.full_c = full.close.values.astype(float)
            self.full_idx = full.index
            self.full_off = len(full) - len(frame)      # bar i of `frame` is full_off + i
            for m in htf:
                n_m = lbm.get(m, 5)
                cut = hist[-n_m].index[0] if n_m <= len(hist) else hist[0].index[0]
                hb = htf_bars(full, m)
                for z in L.fvgs(hb.high.values, hb.low.values):
                    if hb.end.iloc[z.i] >= cut:
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
    if name == "sunday":                      # caption-gap B13 wk_open_side: the week's Sunday 18:00 open (known before 09:30; sm2.attach)
        return getattr(ctx, "sunday_open", None)
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
    _LD4._c(ctx)["tgt_ext"] = (ext_i, None if leg is None else leg[0])      # caption-gap new-trendline-trap-target: the sweep this call prices
    pdk = ("pdh1", "pdh2", "pdh3") if sd.sign > 0 else ("pdl1", "pdl2", "pdl3")
    if p.tgif and p.tgif_no_rel and sd.sign in getattr(ctx, "block_side", {}).get("tgif", ()):
        eq = []                             # caption-gap M14-tgif-timing-and-precondition (084 ~00:18:42): the with-trend side of a TGIF Friday does not target the remaining relative equal highs / lows
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
    rth_pools = []
    if p.extra_pools:
        for name, (hi, lo, ready) in ctx.sess.items():
            if ctx.t[i] >= ready:           # complete only from `ready` (London 05:00: a 03:00 London
                created = ctx.start if name == "prev_pm" else at(ready)   # SB no longer sees it early)
                if p.pm_lunch_raid and name == "lunch" and _SM3.lunch_not_target(ctx, sd):
                    continue                # caption-gap LLT3-lunch-hl-raid-not-target (cc10_013 ~1:50): the raid pool of the biased move is no target of the counter side
                if p.rth_pool_spent and name in _LD3.RTH_POOLS:           # caption-gap L1: spent by RTH prints only (judged below)
                    rth_pools.append((sd.x(hi if sd.sign > 0 else lo), created))
                    continue
                pools.append((sd.x(hi if sd.sign > 0 else lo), created))
    if ctx.or_hl is not None and ctx.t[i] >= ctx.or_end and not (p.or_expire and ctx.t[i] >= p.or_expire) and _TP1.or_ok(ctx, p, sd, i):    # caption-gap L3 or_expire: an AM reference only (T4-or-needs-bias-iof: with a bias and the iof agreeing)
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
        pools += [(q.price, None) for q in _LD.pool_piv(sd, False) if q.known <= i and q.i >= ctx.start - 1
                  and sd.h[q.i + 1:i + 1].max(initial=-np.inf) < q.price]
    if p.news_range_target:                 # #4: the news dealing range's opposite extreme
        for R, d in getattr(ctx, "news_dr", {}).items():
            if d["made"] is not None and d["made"] <= i:
                pools.append((sd.x(d["hi"] if sd.sign > 0 else d["lo"]), d["made"] + 1))
    # #13 round handles (A2 round_pool_mode); review fix #2: "confluence" = an old high / low or a rel-eq pool near the handle - the old-high pools
    # (pdh/pdl), rel-eq pools, the active old pool (A2) and the engineered pools (A3), not every other pool (PM, London, news...)
    refs = [sd.x(ctx.pd[k]) for k in pdk if k in ctx.pd] + list(eq) + _LD3.confluence_refs(ctx, sd, i, p, True)
    pools += [(v, None) for v in _LD3.round_filter(_round_levels(ctx, sd, i, True, 2), refs, p)]
    pools += _lv_target_pools(ctx, sd, i, p)                           # levels_detectors pools
    if p.close_draw:                        # Ep07.1: unrealized prior closes + last week's close as pools
        pools += _TP.close_pools(ctx, sd, i, p, above)
    eqs = {round(v, 9) for v in eq} if p.eq_pref != "off" else set()   # Ep06.7: kind "pool_eq"
    if p.eq_pref != "off":
        eqs |= _LD3.eng_levels(ctx, sd, i, p)                          # caption-gap A3: engineered pools rank like rel-eq pools
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
    for v, cr in rth_pools:                 # caption-gap L1 rth_pool_spent: a previous PM / AM / lunch range is spent by RTH prints only
        if not _LD3.rth_spent_up(ctx, sd, v, cr, ext_i, tk):
            lv.append((v, pk(v)))
    if getattr(ctx, "gaps", None) is not None:
        for kind, hi, lo, ce in ctx.gaps:
            reb_ = _LD3.nwog_levels(ctx, sd, i, kind, hi, lo, ce, p)       # caption-gap L5 nwog_rebalanced: near edge + exit FVG edge only
            if reb_ is not None:
                lv += [(v, "array") for v in reb_]
                continue
            if p.weekly_gap_ce_only and kind in ("nwog", "nwog_rth"):      # L9 (061 ~2:30:15): the CE is enough, the far edge a ringer
                lv.append((sd.x(ce), "array"))
            else:
                lv += [(sd.x(hi), "array"), (sd.x(ce), "array"), (sd.x(lo), "array")]
            if p.gap_quarters or (p.nwog_quarters and kind in ("nwog", "nwog_rth")):   # L5 / D21 quarters
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
    if p.midnight_target:                   # Ep06.6: the midnight open is the level price returns to (a short entered above it)
        m_ = _open_known(ctx, "midnight", i)
        if m_ is not None:
            lv.append((sd.x(m_), "array"))
    if p.org_days and p.org_both_ways:      # caption-gap L7: only the part of each ORG still pending in this direction: [partial-delivery extreme, far edge]
        lv += [(v, "array") for v in _LD4.org_levels(ctx, sd, i, p, _LD4.org_sel(ctx, p, pre_open))]
    elif p.org_days:
        orgs = ctx.org[:-1] if (pre_open and ctx.org_today) else ctx.org
        for a, b in orgs[-p.org_days:]:
            lv += [(sd.x(a + q * (b - a)), "array") for q in (0.0, 0.25, 0.5, 0.75, 1.0)]
    if p.wick_levels:
        wk_ = "wick" if p.wick_read != "off" else "array"       # A23 wick_read: the rung is told apart
        lv.append((sd.x(ctx.wick["upper"] if sd.sign > 0 else ctx.wick["lower"]), wk_))
        if p.wick_untraded or p.wick_weeks > 1:      # caption-gap L10: only wick CEs no later daily bar traded through (weekly: the last wick_weeks)
            lv += [(v, wk_) for v in _LD4.wick_ce_levels(ctx, sd, p, p.wick_both, i)]
        else:
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
    lv = _LD3.balanced_filter(sd, i, above, lv, p)                    # caption-gap A11 balanced_range: nothing past a redelivered body-filled range's EQ
    if p.reh_merge_pts > 0 or p.stubby_wick_ce:
        lv = _TP1.targets_post(ctx, sd, i, p, lv)                     # caption-gap A3-reh-under-older-high / A23-stubby-wick-first-approach (targets_partials #1/4)
    if _TP2.targets_on(p):
        lv = _TP2.targets_post(ctx, sd, i, p, above, lv, eq, ext_i)    # caption-gap targets_partials #2/4: session-pool filter, defended pools, break gate, swept pools, event horizon, NWOG magnet, overnight FVGs, HTF OB open
    if _BH2E.targets_on(p):
        lv = _BH2E.targets_post(ctx, sd, i, p, above, lv)              # caption-gap bias_htf#2/7: the tier-regime trim, the weekly / monthly rungs
    if _BH1E.targets_on(p):
        lv = _BH1E.targets_post(ctx, sd, i, p, above, lv)              # caption-gap bias_htf#1/7: no long target above a week whose high is in (wk_high_in_gate), the stacked-gap partial rung
    if _BH3E.targets_on(p):
        lv = _BH3E.targets_post(ctx, sd, i, p, above, lv)              # caption-gap bias_htf#3/7: the chop-day baseline rung
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
    piv = _LD.pool_piv(sd, lows)          # caption-gap B5 pool_tf: the pools' pivots may come from 15m bars
    body_ref = p is not None and p.sweep_ref == "body"      # caption-gap A4-sweep-body-cluster: the pool is the cluster of BODIES (the line = the lowest body), the sweep needs a low below it
    bodies = p is not None and (p.eq_bodies or body_ref)
    if body_ref:
        _SM2.hit("sweep_body")
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
                wick.append((-b if lows else b) if body_ref else (-q.price if lows else q.price))
                bar.append(q.i)
            continue
        after = sd.l[q.i + 1:i + 1] if lows else sd.h[q.i + 1:i + 1]
        slack = tol if (p is not None and p.eq_min_sep_bars) else 0.0     # A3-clean-high: H2 "slightly above" H1 leaves the pool standing
        if (len(after) == 0) or (after.min() > q.price - slack if lows else after.max() < q.price + slack):
            out.append(-q.price if lows else q.price)
            wick.append(-q.price if lows else q.price)
            bar.append(q.i)
    ms = p.eq_min_sep_bars if p is not None else 0         # caption-gap A3-clean-high: the swings must be separated in time
    if not bodies and not rank:
        lv = L.equal_levels(out, tol, bar, ms)
        return [-v for v in lv] if lows else lv
    cl = []
    for idx in L.equal_clusters(out, tol, bar, ms):
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
    if kind in ("exact", "fixed"):
        return v
    if p.proj_exit_ticks and kind.startswith("proj"):        # caption-gap L12-projection-exit-1tick (013 ~00:29:08): a projection exits proj_exit_ticks ticks before its level
        return v - p.proj_exit_ticks * p.tick
    if p.proj_kind and (kind.startswith("proj") or kind in _TP.SD_KINDS):    # caption-gap X2-projection-target-1tick-before (012 ~00:29:40): SD / measured-move / projection levels exit proj_before_pts before the level
        return v - p.proj_before_pts * p.es_pt
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
    ctx.tf_lookback = dict(p.tf_lookback)      # caption-gap new-lookback-per-tf-topdown (ld3.daily_hl cuts the daily pivot history to the "D" window)
    ctx.tk = _tick(p)
    tt = df.index.hour * 60 + df.index.minute
    dates = [x.index[0].date() for x in hist]
    ec = (lambda d: eth.get(d)) if eth else (lambda d: None)
    # B21 / L3: IPDA ranges, rolling from yesterday (day 1). Review fix: daily FULL-session candles
    # (ipda_session="eth": the eth dict, a date without one falls back to its RTH session)
    hl_ = lambda d, x: ((ec(d)[1], ec(d)[2]) if (p.ipda_session == "eth" and ec(d) is not None)
                        else (float(x.high.max()), float(x.low.min())))
    ctx.ipda_days = [hl_(d, x) for d, x in zip(dates, hist)]
    ctx.ipda, ctx.ipda_last = _LD.ipda_windows(ctx, p, dates)     # caption-gap B21 ipda_anchor ("rolling" = yesterday, as before)
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
    ctx.wicks = [L.wick_midpoints(*cand(dates[-k], hist[-k]), quarters=p.wick_quarters)
                 for k in range(1, min(max(p.wick_days, 1), len(hist)) + 1)]
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
        ctx.org, ctx.org_today, ctx.org_dates = [], False, []
        for a, b in zip(seq[:-1], seq[1:]):
            rth = b[(b.index.hour * 60 + b.index.minute) >= 570]
            if len(rth) and len(a):
                pc = (closes or {}).get(a.index[0].date(), float(a.close.iloc[-1]))
                ctx.org.append((float(pc), float(rth.open.iloc[0])))
                ctx.org_dates.append(b.index[0].date())
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
    # caption-gap pass (levels_detectors #1/3): reference FVGs, daily VI flips, 1h consolidation OB opens
    ctx.initfvg = _LD.build_init_fvg(ctx, df, hist, p) if p.initial_fvg else []
    ctx.vi_flip = _LD.build_vi_flip(ctx, hist, df, p) if (p.vi_flip_support or p.vi_flip_entries) else []
    ctx.cons_ob = _LD.build_cons_ob(ctx, hist, df, p) if p.cons_ob_open else []
    # caption-gap pass (levels_detectors #2/3): L1 RTH pools spent by RTH prints only, L3 session opening ranges, B21 daily gaps / consolidation EQs
    ctx.rth_spent = p.rth_pool_spent
    ctx.sors = _LD3.build_sors(ctx, p) if _LD3.sor_windows(p) else []
    ctx.ipda_gaps, ctx.ipda_ceq = _LD3.build_ipda_x(ctx, hist, dates, eth, p) if (p.ipda_fv or p.ipda_consol_eq or p.ipda_window_arrays) else ([], [])
    # caption-gap pass (levels_detectors #3/3): previous-day London, wick CEs still untraded, ORG state, monthly O/H/L/C, rejection-block closes, week pools, LR zone, OR FVGs
    _LD4.build(ctx, df, hist, p, dates, cand, eth)
    _SM2.attach(ctx, df, hist, p, eth)                      # caption-gap setups_models #1/7: the Sunday open (wk_open_side)


def _lv_target_pools(ctx, sd, i: int, p) -> list:
    """levels_detectors buy-side pools (side space) as (level, created bar) for _targets."""
    out = []
    S = ctx.start
    t = ctx.t[i]
    hi_ = lambda hl: sd.x(hl[0] if sd.sign > 0 else hl[1])
    if p.ipda_pools or p.ipda_next or p.ipda_forward:   # B21 / L3 (cc05_003 ~28:38: 20 -> 40 -> 60; caption-gap ld4: window list, rejection-block body edge, array roll, beyond 60, forward intervals)
        out += _LD4.ipda_pools(ctx, sd, i, p)
    ss = _sess_start(ctx, i)
    if (p.pool_today_hl or p.matrix_days == "ict") and ss is not None and ss > S:
        out.append((float(sd.h[S:ss].max()), ss))          # L2 / Ep08.10 today's high
        if p.matrix_days == "ict":                         # the 3-day high (m3h)
            raws = [float(sd.h[S:ss].max())] + [hi_((float(x.high.max()), float(x.low.min())))
                                               for x in getattr(ctx, "hist", [])[-2:]]
            out.append((max(raws), ss))
    oa = getattr(ctx, "or_alt", None)
    if oa is not None and t >= oa[0] and _TP1.or_ok(ctx, p, sd, i):                      # L3 or_extra (T4-or-needs-bias-iof)
        out.append((hi_(oa[1]), _idx_at(ctx, oa[0])))
    out += _DW.target_pools(ctx, sd, i, p)                 # day_week_context N10.3 pool_mon_wed
    if p.consol_pools:                                     # caption-gap N8: the released chop range's far edge
        cp = _LD.consol_pool(ctx, sd, i, True, p)
        if cp is not None:
            out.append(cp)
    out += _LD3.target_pools(ctx, sd, i, p)                # caption-gap A2 / A3 / L3 pools (old high, engineered, session ORs, open float)
    out += _LD4.target_pools(ctx, sd, i, p)                # caption-gap levels_detectors #3/3 pools (reactionary, parent, trendline, week)
    return out


def _lv_target_arrays(ctx, sd, i: int, p) -> list:
    """levels_detectors array targets (side space) for _targets: L8 vacuum blocks (08:30: near, MT and
    far edge; later releases - 09:45 / 10:00+: near and MT)."""
    out = []
    for k, near, mt, far, R in getattr(ctx, "vac", []):
        if k > i:
            continue
        if p.vb_context and not _LD.vb_valid(ctx, p, near, far, i):      # caption-gap L8: exhaustion / out of context
            continue
        out += [(sd.x(near), "array"), (sd.x(mt), "array")]
        if R == 510:                   # review fix: the spec gives the far edge at 08:30 only
            out.append((sd.x(far), "array"))
    out += _DW.expansion_levels(ctx, sd, i, p)             # day_week_context N8.5 expansion_targets
    if p.inversions:                                       # caption-gap A8: arrays inverted to resistance (low, MT)
        for z in _LD.inverted(ctx, sd, i, p, "bear"):
            out += [(float(z.levels[0]), "array"), (float(z.levels[1]), "array")]
    if p.cons_ob_open:                                     # caption-gap A12: the 1h consolidation OB opens
        out += [(v, "array") for v, _ in _LD.cons_ob_levels(ctx, sd, i, p)]
    if p.vi_flip_support:                                  # caption-gap A9: reached daily VIs flipped to support / resistance
        out += [(v, "array") for v in _LD.vi_flip_target_levels(ctx, sd, i, p)]
    if p.ipda_fv or p.ipda_consol_eq or p.ipda_window_arrays:   # caption-gap B21: the data range's open daily gaps and consolidation EQs
        out += _LD3.ipda_arrays(ctx, sd, p)
    out += _LD4.target_arrays(ctx, sd, i, p)               # caption-gap levels_detectors #3/3 (rejection-block closes, IPDA wick runners)
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
            out[f"ipda{n}"] = _LD4.ipda_hi_lo(ctx, p, sd, n)[1] if p.ipda_rb else lo_(hl)     # caption-gap ipda_rb: the body edge of a wicky extreme
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
        if (p.org_pools or p.org_fill_reverse) and getattr(ctx, "org_today", False) and t >= 570 and ctx.org:
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
            if p.org_both_ways and not _LD4.org_alive(ctx, (len(ctx.org) - (1 if (t < 570 and today) else 0) - len(orgs)) + j, i - 1, p):
                continue                               # caption-gap L7: both directions done = no longer a level
            tag = "org_t" if (today and t >= 570 and j == len(orgs) - 1) else f"org{len(orgs) - 1 - j}"
            for q, v in (("lo", min(a, b)), ("ce", (a + b) / 2), ("hi", max(a, b))):
                if sd.x(v) < last:
                    out[f"{tag}_{q}"] = sd.x(v)
    out.update(_DW.sell_pools(ctx, sd, i, p))          # day_week_context N10.3 pool_mon_wed
    if p.diag_pools:                                   # caption-gap A3: a diagonal run of higher lows is liquidity
        v = _LD.diag_level(ctx, sd, i, p)
        if v is not None:
            out["diag"] = v
    if p.consol_pools:                                 # caption-gap N8: the released chop range's edge
        cp = _LD.consol_pool(ctx, sd, i, False, p)
        if cp is not None:
            out["consol_l" if sd.sign > 0 else "consol_h"] = cp[0]
    _LD3.sell_pools(ctx, sd, i, p, out)                # caption-gap A2 / A3 / L3 pools (old low, engineered, session ORs, open float)
    _LD4.sell_pools(ctx, sd, i, p, out)                # caption-gap levels_detectors #3/3 pools (reactionary, parent, trendline, week, rejection-block closes, IPDA forward)
    if p.pool_gaps or p.nwog_edge_ce:                  # M2.1: NWOG / NDOG as sweep pools (caption-gap new-nwog-edge-to-ce-cookie-cutter: the NWOG far edges alone)
        gl = ctx.gaps if getattr(ctx, "gaps", None) is not None else \
            [("monday", max(a, b), min(a, b), (a + b) / 2) for a, b in _nwogs(ctx, i)]
        for j, (kind, hi, lo, ce) in enumerate(gl):
            if not p.pool_gaps and kind not in ("nwog", "nwog_rth", "monday"):
                continue
            v = min(sd.x(hi), sd.x(lo)) if (p.gap_pool_edge == "far" or not p.pool_gaps) else sd.x(ce)
            if v < last:
                out[f"gap_{kind}{j}"] = v
                if p.nwog_edge_ce and not p.pool_gaps:
                    _SM2.hit("nwog_edge_pool")


def _ipda_eq(ctx, p, i: int) -> bool:
    """B21 (cc05_003 ~1:18:26) [our interpretation]: price near the EQ of all three IPDA ranges -
    within ipda_eq_frac of each range of its midpoint - with both sides run: an earlier 20-day high
    AND an earlier 20-day low were each taken within the last ipda_eq_days sessions. Price = the
    09:30 open (the last close before 09:30). Needs 60 + ipda_eq_days... at least 60 sessions."""
    if p.ipda_consol_eq:                  # caption-gap B21: price against the daily consolidations' EQs, no news driver
        return _LD3.consol_eq_day(ctx, p, i)
    hist = getattr(ctx, "hist", [])
    if len({20, 40, 60} & set(ctx.ipda)) < 3 or len(hist) < 21:
        return False
    k = _idx_at(ctx, 570)
    px = float(ctx.o[k]) if (k < len(ctx.t) and k <= i) else float(ctx.c[i])
    for n, (hi, lo) in ctx.ipda.items():
        if n not in (20, 40, 60):             # (caption-gap ipda_windows: the 63 / 126 / 252-day ranges do not take part)
            continue
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
        zs = [(sd.x(hi), sd.x(lo)) for kind, hi, lo, _ in ctx.gaps if kind in ("nwog", "nwog_rth")]
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
    out += _LD4.draw_prefs(ctx, sd, i, entry, p)       # caption-gap levels_detectors #3/3 (reactionary high, parent pool, two-window IPDA pools)
    return out


def _close(pos, trades, p):
    tr = pos["trade"]
    if p.journal_timing:
        _DWC3.journal_close(pos, tr, p)                   # caption-gap OT-X16-time-to-move-journal: minutes to the first favourable move / to the exit, MFE / MAE
    tr.capture = _TP.capture_ratio(pos, tr)           # X3h: how much of the best-case run the exits took
    if pos.get("tp4"):
        _TP4.close_note(pos, tr, p)                   # caption-gap targets_partials #4/4: half_range_ok, capture_b, strength
    trades.append(tr)
    gross, costs = tr.pnl(p.cost_per_share)
    return tr.side if gross - costs < 0 else None


def _after_close(pos, trades, p, done, state, i=None, ctx=None):
    """Record the trade; apply the session rules that depend on how it ended."""
    lost = _close(pos, trades, p)
    tr = pos["trade"]
    if (p.pre_draw_done_am or p.hard_day_one_trade) and done is not None:
        _NCT.after_close(ctx, tr, done, p, tr.date)          # caption-gap N5-pre0930-entries / new-premarket-difficult-days
    if p.proj_kind and pos.get("level_kinds"):
        _TP3.near_miss(pos, tr, p)                       # caption-gap X2-projection-target-1tick-before: the stops just short of a projection rung
    if pos.get("sm4") and done is not None:
        _SM4.after_close(pos, tr, done)                  # caption-gap M6-pm-continuation-long-at-old-high: the target fill arms the M6 reversal
    if pos.get("sm3") and done is not None:
        _SM3.after_close(pos, tr, done)                  # caption-gap A15-mitigation-block-targets: the session is done after the final rung
    if pos.get("sm5") and done is not None:
        _SM5.after_close(pos, tr, done, state, p)        # caption-gap M1-one-segment: mm_flip reopens the session for the opposite MM leg
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
        g_, c_ = tr.pnl(p.cost_per_share)
        if p.be_counts_as_win or g_ - c_ > 0:                # D19: a breakeven counts as a win (the old behaviour) unless off
            if p.allow_opposite_after_target in ("split", "both"):
                state["split_pm"] = -(1 if tr.side == "long" else -1)      # caption-gap X14-opposite-second-trade-after-win (cc10_007 ~00:12:21): the PM stays open for the OPPOSITE side only (the gate judges the AM range)
                state.setdefault("only_side", {})["PM"] = state["split_pm"]
                _SM7.hit("split_open")
            else:
                done["PM"] = True
    gross, costs = tr.pnl(p.cost_per_share)
    net_ = gross - costs
    state["day_net"] = state.get("day_net", 0.0) + net_            # caption-gap E11-funded-account-caps: the day's realized P&L
    tight_ = lost is not None and _ES3.tight_loss(tr, p, pos)           # caption-gap E6-new-trader-wide-stops: no immediate re-entry after a tight-stop loss (trader_mode "new")
    key = pos.get("done_key", tr.session)
    _ME1.after_close(pos, tr, done, key)              # caption-gap management_exits #1/3: the hold_reached session slot, the delivery-speed tag
    _ME2.after_close(pos, tr, done, key, state, p)    # caption-gap management_exits #2/3: the pool lock's re-entry block / day done, the chop-close session rule
    blocked3_ = _ME3.pre_close(pos, tr, state, p, i) if (p.abort_blocks_side or _ME3.runner_stop_on(p)) else False      # caption-gap management_exits #3/3: an abort-set exit abandons the leg's direction (no re-entry), a runner stop after the bulk was banked ends the move
    reopened = False
    if (lost is not None and p.reentry_half and not tight_ and not blocked3_ and (not state["reentered"].get(tr.session) or _ME3.more_reentries(state, tr.session, p))      # (caption-gap D18-reentry-count-max-2: reentry_count_max attempts)
            and not (p.fomc_day_stop and "fomc" in events(tr.date))):            # N3.5: none on an FOMC day
        # X13b / D18: one more try, same direction, half risk (reentry_gate: only while the idea is intact); the flag of
        # the trade's OWN done key is re-opened (an SB_AM loss no longer re-opens the plain AM slot)
        rc = (_MG.reentry_open(ctx, pos, tr, i if i is not None else pos["fill_i"], p, state, net_) if ctx is not None
              else dict(side=tr.side, stop_i=-1, pending=True, loss=max(0.0, -net_), ratio=1.0, key=key))
        if rc is not None and ctx is not None and i is not None and (p.reentry_idea_gate or p.reentry_trigger != "new_array"):
            rc.update(_SM7.rc_extra(pos, tr, i, p))            # caption-gap X13b: the entry zone / leg origin / stop-out low the idea-intact gate reads
            rc["fill_i"] = pos["fill_i"]
        if rc is not None:
            done[key] = False
            _ME3.count_reentry(state, tr.session, p)
            state.setdefault("re_ctx", {})[tr.session] = rc
            reopened = True
    if (lost is not None and not reopened and p.reverse_in_session
            and not state.setdefault("reversed", {}).get(tr.session)):
        # X13a (experienced, 001 ~47:32): the session may reverse once after a loss - the opposite side only (also when
        # reentry_half is on but its gate refused the re-entry)
        done[key] = False
        state["reversed"][tr.session] = True
        state.setdefault("only_side", {})[tr.session] = -1 if tr.side == "long" else 1
    if p.void_rearm:
        _TP4.after_close(ctx, pos, tr, lost, done, key, state, p)      # caption-gap new-sellstop-run-before-void-fill: a stopped-out void_draw trade re-arms its session once
    if ctx is not None and _SM7.any_after7(p):
        reopened = _SM7.after_close(ctx, pos, tr, lost, net_, done, key, state, i, p, reopened, no_same=tight_) or reopened     # caption-gap setups_models #7/7: win / trail-win re-entries, reversals, the turtle-soup re-entry, the lod reopen
    state.pop("no_win_reentry", None)
    if p.prop_fail_flip:
        _ES1.after_close(ctx, pos, tr, done, key, state, p)         # caption-gap A16-propulsion-block-full: a failed propulsion block ends the longs of the session
    if (p.lc_reentry or p.lc_second_swipe) and ctx is not None and tr.session == (getattr(ctx, "lc_retry", None) or {}).get("session"):
        _SM2.lc_clear(ctx)                              # the re-opened slot's trade closed: the retry gate ends
    if (p.lc_reentry and ctx is not None and lost is not None and not reopened and not state.get("lc_done") and "lc_reversal" in (tr.lv_tags or "")
            and tr.exits and tr.exits[-1][3] in ("stop", "stop_gap") and 600 <= tr.exits[-1][0].hour * 60 + tr.exits[-1][0].minute < 720):
        _SM2.lc_reopen(ctx, tr, done, key, state)       # caption-gap T3 lc_reentry: one more try after a stopped-out London-close reversal
    if ctx is not None and _ME3.any_on(p):
        reopened = _ME3.after_close(ctx, pos, tr, done, key, state, p, i, lost, net_, reopened) or reopened       # caption-gap management_exits #3/3: the day / session stops, the re-entry arms, the second swipe
    if net_ < 0:
        state["day_loss"] = True                      # Ep08.12 after_loss_mult / after_loss_adds
    if lost is not None:
        state["lost_fam"] = _MG.fam(tr.session)       # X13a lost_side_session
    if p.loss_halving and state.get("rs") is not None:
        _EN.risk_state_update(state["rs"], gross - costs, p)       # E10 (carried across days)
    _MG.mark_day_stop(tr, p)                           # Ep04.13 / X12: the trade itself ended the day
    _MG.apply_stops(trades, p, done, state)           # X7c / X12 / X13a / X14b / X14d: session and day stops
    if p.eve_mode == "bnb" and net_ > 0 and "eve_bnb" in (tr.lv_tags or ""):      # caption-gap N4-eve-of-high-impact (029 ~00:52:11): stop for the day after the objective / one win
        for k in list(done):
            done[k] = True
        state["day_done"] = True
        _TP1.hit("eve_bnb_day_done")
    if p.drange_scalp and ctx is not None:
        _BH1E.after_close(ctx, tr, done, state, p, net_)              # caption-gap BH-B17-daily-range-scalp-regime: the day's points / wins on a range day
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
    m = p.reentry_risk_mult if state["reentered"].get(session) else 1.0
    if state["reentered"].get(session) and p.reentry_risk == "loss":          # D18: half of the LOSING trade's own risk (caption-gap X13b: reentry_risk_mult, 0.5 by default)
        m = p.reentry_risk_mult * state.get("re_ctx", {}).get(session, {}).get("ratio", 1.0)
    m = _ME3.risk_count(state, session, p, m)         # caption-gap D18-reentry-count-max-2: the n-th re-entry at reentry_risk_mult ** n
    if p.loss_halving and state.get("rs") is not None:
        m *= state["rs"]["m"]
    if state.get("day_loss"):
        m *= p.after_loss_mult
    return _SM7.risk_mult7(state, session, p, m)


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


def day_context(hist: list[pd.DataFrame], day, p: "Params | None" = None, eth: dict | None = None,
                conf=None) -> tuple[set, dict]:
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
    if p is not None and p.journal_timing:
        tags |= _DWC3.journal_day_tags(day)                   # caption-gap OT-X16-time-to-move-journal: pre_fomc / news_day
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
    if day.weekday() == 4 and p is not None and _DWC3.tgif_array_needed(p) and p.tgif_precond == "strict":      # (caption-gap M14-tgif-timing-and-precondition: "loose" = the large one-way week alone, the elif branch)
        tag_, blk_ = _DW.tgif_context(hist, day, p, eth, conf)        # M14.1: full-session week + the HTF array check
        if tag_:
            tags.add(tag_)
            block["tgif"] = (blk_,)
    elif day.weekday() == 4:
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
    if p is not None and p.tgif and p.tgif_min_adr and ("tgif_short" in tags or "tgif_long" in tags) and not _DWC3.tgif_adr_ok(hist, day, p):
        tags -= {"tgif_short", "tgif_long"}                    # caption-gap M14-tgif-am-timing: the trending week must exceed tgif_min_adr x ADR5
        block.pop("tgif", None)
    if p is not None and p.tgif_strict and ("tgif_short" in tags or "tgif_long" in tags):
        if not _DWC.tgif_strict_ok(hist, day, p, eth, conf, "tgif_short" in tags):      # caption-gap BH-M14-TGIF-preconditions (066 ~00:15:52)
            tags -= {"tgif_short", "tgif_long"}
            block.pop("tgif", None)
    return tags, block


# --- owner #10: sloppy days [our interpretation throughout] -----------------------------
# Ep08 (010) 01:16:37-01:17:23 "sloppy consolidations ... seasoned students turn the charts off
# and walk away"; Ep03 (003) 00:58:43 "sloppy day ... I don't like to engage them"; Ep03
# 00:18:23-00:18:49 FOMC + NFP week tends to sloppy delivery. ICT never defines "sloppy"; the
# day-level reasons and the intraday chop test below are our reading.

def sloppy_day(hist: list[pd.DataFrame], day, p: "Params", open_px: float | None = None) -> set:
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
        if not p.inside_bisi_redelivered or _DWC3.bisi_two_sided(hist, open_px, p):        # caption-gap B17-M15-madeuce-inside-bisi: only when both sides are arguable
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


def _inside_daily_fvg_zone(hist: list[pd.DataFrame]):
    """The daily FVG (top, bottom) yesterday's whole range sat inside (formed before it and not closed through since; the first one found), None when there is none."""
    if len(hist) < 4:
        return None
    o, h, l, c = _daily(hist)
    k = len(h) - 1
    for z in L.fvgs(h[:k], l[:k]):
        after = c[z.i + 1:k]
        if z.kind == "bull" and len(after) and after.min() < z.bottom:
            continue
        if z.kind == "bear" and len(after) and after.max() > z.top:
            continue
        if z.bottom <= l[k] and h[k] <= z.top:
            return float(z.top), float(z.bottom)
    return None


def _inside_daily_fvg(hist: list[pd.DataFrame]) -> bool:
    """#10 / B17 (091 ~6:12 "price inside one daily BISI range = don't trade that index") [our
    interpretation]: yesterday's whole range sat inside one daily FVG (either direction) formed
    before it and not closed through since (`_inside_daily_fvg_zone`)."""
    return _inside_daily_fvg_zone(hist) is not None


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
        self.rel_i = None

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
                self.rel_i = i                       # caption-gap N8 consol_pools: the release bar (range = self.hi / self.lo)
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
    if p.nfp_week_split:
        f_ = _TP1.split_fracs(p, day)             # caption-gap N2-nfp-week-imprecise-targets (003 ~00:18:39): most of the position at the nearer liquidity in an NFP week / on an FOMC day
        if f_ is not None:
            return f_
    if not p.ladder_by_day:
        return p.ladder_fracs
    tags = events(day)
    ahead = (bool(tags & NEWS_1000) and t < 600) or ("fomc" in tags and t < 840)
    if p.ladder_news_day and tags & {"cpi", "jobs", "fomc"}:      # Ep04.12: a news day takes the bulk first
        return p.ladder_fracs_slow
    nxt = next_trading_day(day)
    if events(nxt) & {"cpi", "jobs", "fomc"}:
        ahead = True
    if p.friday_slow_split and day.weekday() == 4:          # N10.4 (070 ~1:06:37): most at the first pool on a Friday
        return p.ladder_fracs_slow
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
        out["LH"] = p.lh_freeze_t if p.lh_draw_freeze else p.last_hour[0]       # caption-gap M5-lasthour-draw-frozen-noon: the draw is fixed before lunch, not re-picked at 15:00
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
            if p.org_both_ways and not _LD4.org_alive(ctx, len(ctx.org) - (1 if (ctx.org_today and t_lock <= 570) else 0) - len(orgs) + j, kl - 1, p):
                continue                               # caption-gap L7: both directions done
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
            if p.ipda_rb:                              # caption-gap B21 ipda_rb: the body edge of a wicky extreme
                hi_, lo_ = _LD4.ipda_level(ctx, p, n, True)[0], _LD4.ipda_level(ctx, p, n, False)[0]
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
        cr_am = at(570) if p.rth_pool_spent else S          # caption-gap L1: only RTH prints spend the previous AM range
        cands += [(ctx.prev_am[0], "pool", "prev_am_high", 1, cr_am), (ctx.prev_am[1], "pool", "prev_am_low", -1, cr_am)]
    cands += _LD3.lock_cands(ctx, p, t_lock, kl)           # caption-gap A2 old_hi / old_lo, L3 session opening ranges
    cands += _LD4.lock_cands(ctx, p, t_lock, kl)           # caption-gap levels_detectors #3/3 (week pools, previous London, rejection-block closes)
    cands += _TP2.lock_cands(ctx, p, t_lock, kl)           # caption-gap X1-london-0300-fvg-draw (018 ~00:03:49): the overnight 5m FVGs
    cands += _TP3.lock_cands(ctx, p, t_lock, kl)           # caption-gap LLT3-session-targets-15m-60m (cc10_014 ~00:04:18): the opposing 15m / 1h arrays as session objectives
    cands += _BH1E.lock_cands(ctx, p, row, t_lock, S)      # caption-gap pass bias_htf#1/7: the weekly BISI CE after a PWH give-back, the wick CE draw
    cands += _BH2E.lock_cands(ctx, p, row, t_lock, S)      # caption-gap pass bias_htf#2/7: the next weekly array beyond a fast weekly draw
    mw_ = getattr(getattr(ctx, "dplan", None), "info", {}).get("mw")
    if p.pool_mon_wed and mw_ is not None:             # day_week_context N10.3: the Mon-Wed extremes on Thu / Fri
        cands += [(mw_[0], "pool", "mon_wed_high", 1, S), (mw_[1], "pool", "mon_wed_low", -1, S)]
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
            zs = [(hi_, lo_) for kind, hi_, lo_, _ in ctx.gaps if kind in ("nwog", "nwog_rth")]
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
            if "htf" in p.target_hygiene:          # L14 / L14d conf-target hygiene: an array price already traded into since it formed is no draw
                r = _BD.untraded_arrays(ctx, kl - 1, now, px, sgn, tfs, (0,), p.array_reuse != "first_touch")
            else:
                r = ctx.conf.opposing(now, px, sgn, tfs, (0,))
            if r:
                prefs.append((r[0][1], "array", "htf_ce", 0, S))
    if p.vi_htf_draw and getattr(ctx, "conf", None) is not None:          # A9 (review fix: in the lock too)
        now = pd.Timestamp(ctx.day, tz=ctx.idx.tz) + pd.Timedelta(minutes=t_lock)
        for sgn in (1, -1):
            if "htf" in p.target_hygiene:
                r = _BD.untraded_arrays(ctx, kl - 1, now, px, sgn, ("1h", "4h", "D", "W"), (3,), p.array_reuse != "first_touch")
            else:
                r = ctx.conf.opposing(now, px, sgn, ("1h", "4h", "D", "W"), (3,))
            if r:
                prefs.append((r[0][0], "array", "htf_vi", 0, S))
    if p.matrix_tf_lower:                          # L14c: the opposing array one timeframe below the one price reacted from
        r_ = _BD.tf_lower_pref(ctx, row, px, pd.Timestamp(ctx.day, tz=ctx.idx.tz) + pd.Timedelta(minutes=t_lock), S)
        if r_ is not None:
            prefs.append(r_)
    if p.round_pool_mode != "pool":                # caption-gap A2-round-number-pool: a round handle is a lock candidate only with a pool at it
        keep_ = set(_LD3.round_filter([c_[0] for c_ in cands if c_[2] == "round"], [c_[0] for c_ in cands if c_[2] != "round" and c_[1] == "pool"], p))
        cands = [c_ for c_ in cands if c_[2] != "round" or c_[0] in keep_]
    cands = prefs + cands                          # review fix: a preferred draw keeps its own name
    cands = _DWC.lock_filter(ctx, cands)           # caption-gap BH-mixed-HTF-intraday-only (068 ~04:27): a macro-risk week inside a fresh weekly FVG - session pools only
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
    elif p.session_pools_mode == "rank":           # caption-gap L14-session-pools-only (067 ~00:27:37): the session-range pools first (stable: nearest first inside each group)
        up, dn = _TP2.lock_session_rank(up), _TP2.lock_session_rank(dn)
    elif p.session_obj_tf:                         # caption-gap LLT3-session-targets-15m-60m (cc10_014 ~00:04:18): the nearest opposing 15m / 1h array before the pools
        up, dn = _TP3.lock_obj_rank(up), _TP3.lock_obj_rank(dn)
    if p.hrlr_news_only:                           # caption-gap L4-hrlr-news-exception (cc01_007 ~00:08:34): a high-resistance run is a draw only on a jobs / FOMC day after the release
        up, dn = _TP1.hrlr_filter(ctx, p, up, dn, kl, t_lock)
    side = 0
    fp_ = _DWC2.fri_pool_pick(ctx, p, up, dn, px, kl, t_lock, getattr(ctx, "hist", [])) if p.fri_pool_choice else None       # caption-gap N10-friday-pool-choice (096 ~00:06:54)
    if fp_ is not None:
        side, up, dn = fp_
    elif p.draw_lock_pick != "nearest" and not pf and not (p.pool_rank or p.draw_below_eq or p.session_obj_tf):
        side, up, dn = _BD.ordered_side(up, dn, row, p)   # B2 / B3: inefficiency first, then liquidity by P/D ("largest": the bigger move)
    elif up and dn and p.draw_order == "nearest_tb" and abs(up[0][0] - dn[0][0]) <= p.eq_tol_pts * p.es_pt:
        now_tb = pd.Timestamp(ctx.day, tz=ctx.idx.tz) + pd.Timedelta(minutes=t_lock)
        side = _BH1E.tiebreak(up, dn, mk, cands, lambda sg_, it_: _BH1E.arrays_between(ctx, p, now_tb, px, sg_, it_[1]))       # caption-gap BH-B2-draw-by-proximity: near-ties go to the side with fewer opposing arrays in between, then the newer
    elif up and (not dn or up[0][0] < dn[0][0]):
        side = 1
    elif dn and (not up or dn[0][0] < up[0][0]):
        side = -1
    pick = up if side > 0 else dn
    ext_from = None
    if side and p.draw_ext_target and pick[0][2] == "pool":    # B2 (104 ~16:18): the nearest inefficiency beyond a liquidity draw is how far it runs
        extra = []
        if getattr(ctx, "conf", None) is not None:             # the untraded HTF arrays beyond the pool (not marked draws themselves)
            now_ = pd.Timestamp(ctx.day, tz=ctx.idx.tz) + pd.Timedelta(minutes=t_lock)
            for n_, ce_, f_, tf_, src_ in _BD.untraded_arrays(ctx, kl - 1, now_, px, side, tuple(p.htf_targets) or ("15m", "1h", "4h", "D"), (0,), p.array_reuse != "first_touch"):
                extra.append((abs(ce_ - px), ce_, "array", f"ext_htf_{tf_}", 0))
        e_ = _BD.ext_target(pick, [x for x in mk if (x[1] > px) == (side > 0)], extra)
        if e_ is not None:
            ext_from = pick[0][1]
            pick = [e_] + [x for x in pick if x is not e_]
            if all(abs(e_[1] - x[1]) > 1e-9 or x[2] != e_[2] for x in mk):
                mk = sorted(mk + [e_])
    lock = dict(ext_from=ext_from, day=ctx.day, session=session, side=side, t_lock=t_lock, px=px,
                target=pick[0][1] if side else None, kind=pick[0][2] if side else "",
                name=pick[0][3] if side else "", marked=[(v, k, n, dr) for _, v, k, n, dr in mk] + (
                    [(w[s_], "array", "wick_ce", 0) for w in getattr(ctx, "wicks", [ctx.wick])
                     for s_ in ("upper", "lower")] if p.wick_partial else []),
                delivered=False, delivered_t=None, delivered_i=None, traded=False)
    lock = _BH1E.lock_post(ctx, p, row, t_lock, session, kl, px, lock, mk)
    lock = _BH2E.lock_post(ctx, p, row, t_lock, session, kl, px, lock)       # caption-gap pass bias_htf#2/7: ipda side, PM reversal, tier regime, quarterly objective, soft carry      # caption-gap pass bias_htf#1/7: ceiling ladder, weekly PO3, 60m BISI loss, BPR lean, raid gap, minimum criteria, 50/50, run extreme, invalidation
    return _BH3E.lock_post(ctx, p, row, t_lock, session, kl, px, lock)       # caption-gap pass bias_htf#3/7: ny_continue_london, the q_obj_dir fallback


# --- owner #11: Ep 07 order block at the sweep low ----------------------------------------

def _ob_at_low(sd, sw, i, p=None, ctx=None):
    """The bullish OB at the sweep low, from closed bars only: down-close candles in
    [ext_i-3, min(i-1, ext_i+2)]; the one nearest the extreme (ties -> the later bar, as
    ep07_stop), extended back over consecutive down-close candles. Body top = the series'
    highest open, body low = its lowest close, mt = their midpoint."""
    e = sw["ext_i"]
    zone = _LD4.disp_fvg_zone(sd, sw, i) if (p is not None and p.ob_outside_fvg) else None     # caption-gap A12 ob_outside_fvg: candles inside the shaded zone are ignored
    cand = [k for k in range(max(0, e - 3), min(i - 1, e + 2) + 1) if sd.c[k] < sd.o[k]
            and not (zone is not None and sd.l[k] >= zone[0] - 1e-9 and sd.h[k] <= zone[1] + 1e-9)
            and not (p is not None and ctx is not None and _LD4.td_masked(ctx, p, k))]      # (caption-gap new-time-distortion: no OB candle of a masked bar)
    if not cand:
        return None
    k = min(cand, key=lambda k: (abs(k - e), -k))
    j = k
    while j - 1 >= 0 and sd.c[j - 1] < sd.o[j - 1]:
        j -= 1
    mt_ = None
    if p is not None and (p.ob_pick != "blend" or p.ob_skip_encapsulated):    # caption-gap A12 ob_pick / ob_skip_encapsulated
        j, k, mt_ = _LD.ob_run(ctx, sd, sw, j, k, i, p)
    top, low = float(sd.o[j:k + 1].max()), float(sd.c[j:k + 1].min())
    if p is not None and p.ob_anchor == "last_open":
        top = float(sd.o[k])                                 # caption-gap A12-ob-anchor (cc05_015 ~00:16:48): the last candle's open - the ultra-tight anchor
        mt_ = None                                           # review fix: the ob_run path's own MT belonged to the old top - the MT is the midpoint of the anchored body (every ob_pick)
        _ES3.hit("ob_anchor_last_open")
    d_ = dict(k=k, j=j, body_top=top, body_low=low, mt=(top + low) / 2 if mt_ is None else mt_,
              hi=float(sd.h[j:k + 1].max()), lo=float(sd.l[j:k + 1].min()))
    if p is not None and mt_ is None and p.mt_mode in ("range", "sensitive", "body_single_range_blended"):    # review fix: "range" now reaches dict_mt too
        d_["mt"] = _ES1.dict_mt(p, sd, d_, d_["mt"])          # caption-gap D4-mt-source-tally: the sensitive / blended MT of the OB
    return d_


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
               init_fvg_respected=o.get("init_fvg", ""), org_dir=_LD3.org_dir(ctx, i),
               imm_rebal=bool(o.get("imm_rebal", False)), macro_wins=o.get("macro_wins", ""),
               ext_px=None if o.get("ext") is None else float(sd.x(o["ext"])),
               leg_hi_px=None if not o.get("leg") else float(sd.x(o["leg"][1])), entry_style=_SM5.entry_style(o["entry_kind"]), **btag, **_SM2.trade_fields(o), **_SM7.trade_fields(o), **_TP1.trade_fields(o))
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
        ok_ = bool((sd.c[a:i] < sd.o[a:i]).any())
    else:
        ok_ = bool(sd.o[i] > o["entry"])
        _ES2.hit("retrace_intrabar_ok" if ok_ else "retrace_intrabar_skip")      # caption-gap E4 colour (surrogate): the executed-path counter of retrace_candle / e4_color
    if not ok_ and p.e4_wick_ok:
        ok_ = _ES2.wick_redelivery(sd, i, min(float(o["entry"]), float(sd.o[i])))            # caption-gap E4-redelivery-wick-suffices (026 ~01:57:39): trading across the full range of the last opposite-colour candle is the redelivery
        if ok_:
            _ES2.hit("e4_wick_ok")
    return ok_


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
    if o.get("mot"):                                 # caption-gap E1-market-on-touch (mot_next_open): no resting-limit fill - the touch turns the order into a market order at the next open (run_day)
        return None
    if o.get("touch"):                               # caption-gap E1-market-on-touch (mot_next_open off): the first touch of the level fills at the level - no tick through
        return float(min(o["entry"], sd.o[i])) if sd.l[i] <= o["entry"] + 1e-12 else None
    return float(min(o["entry"], sd.o[i])) if sd.l[i] < o["entry"] else None


def _extra_sig(trs) -> tuple:
    return tuple(sorted((t.setup, t.side, str(t.entry_time), tuple((str(e[0]), round(float(e[1]), 4), int(e[2]), e[3])
                                                                 for e in t.exits)) for t in trs))


def run_day(df: pd.DataFrame, hist: list[pd.DataFrame], symbol: str, p: Params, tf: int,
            partner=None, log: list | None = None, live: bool = False, bias: dict | None = None,
            conf=None, gaps: list | None = None, closes: dict | None = None, evening=None, partner2=None,
            intermarket: dict | None = None, equity: float | None = None,
            bias_by_cut: dict | None = None, meta=None, locks: list | None = None, skips: list | None = None,
            eth: dict | None = None, risk_state: dict | None = None, week: dict | None = None,
            eve: tuple | None = None, prev_full: pd.DataFrame | None = None, objective: list | None = None,
            post_eve: pd.DataFrame | None = None, daily_all: dict | None = None) -> list[Trade]:
    """Trades for one day (see `_run_day_once` for the arguments). The main loop runs BEFORE the Silver Bullet / Ma Deuce
    (they read its trades), so the session / day stops (X7c / X12 / X13a / X14b / X14d) would be one-way. With a stop
    switch on and an extra engine on, this wrapper makes them two-way by a fixed point: pass 1 as usual; its Silver Bullet
    / Ma Deuce trades are fed back to a second pass (the main loop reads them as of their exit time, Ma Deuce reads the
    SB's), until the extras' trades stop changing (at most `stops_passes` passes). Every decision only uses trades closed
    by its own bar, so there is no look-ahead; the side effects (locks, skips, log, the E10 risk state) come from the last
    pass only."""
    if not p.stock_intraday and str(symbol).upper() not in _DWC3.INDEX_SYMBOLS:
        if skips is not None:                    # caption-gap OT-stocks-swing-only (cc10_018 ~00:33:36): individual stocks are swing-only - no intraday setups
            skips.append((df.index[0].date(), symbol, "stock", "swing_only"))
        return []
    if p.entry_discipline != "any":
        p = _SM6.apply_discipline(p)             # caption-gap M12-setup-selection-order: the discipline preset of the path switches
    if _ES2.sizing_on(p):
        p = _ES2.apply_sizing(p)                 # caption-gap entries_stops_sizing #2/3 (E12-equal-size-adds / E12-ladder-631 / E12-067-citation-wrong): the add fractions of the day
    p = _ME1.eff_params(p)                       # caption-gap management_exits #1/3: be_mode / be_cap_htf replace the first-partial breakeven (be_on off)
    if p.nq_overshoot_mult != 1.0:
        p = _SM7.nq_params(p, symbol)            # caption-gap OT-D15-default-instrument: NQ / NDX / QQQ get a wider overshoot tolerance (sweep_ticks, mohawk_ticks)
    if p.pool_exit_fomc_before and p.pool_exit != "before" and "fomc" in events(df.index[0].date()):
        p = replace(p, pool_exit="before")       # caption-gap X2-pool-exit-at-or-before (065 ~5:43:00): an FOMC day exits the pools short of the level
        _TP3.hit("pool_exit_fomc")
    kw = dict(partner=partner, live=live, bias=bias, conf=conf, gaps=gaps, closes=closes, evening=evening,
              partner2=partner2, intermarket=intermarket, equity=equity, bias_by_cut=bias_by_cut, meta=meta, eth=eth,
              week=week, eve=eve, prev_full=prev_full, post_eve=post_eve, daily_all=daily_all)
    if not ((_MG.any_stop_switch(p, df.index[0].date()) or p.max_trades_week) and (p.ma_deuce or p.sb_model)
            and p.stops_passes > 1):                       # (the D19 / X15 week budget is two-way across the engines the same way)
        return _run_day_once(df, hist, symbol, p, tf, log=log, locks=locks, skips=skips, risk_state=risk_state, objective=objective, **kw)
    import copy
    ext, sig, res, sc = None, None, [], {}
    for k in range(p.stops_passes):
        sc = dict(log=None if log is None else [], locks=None if locks is None else [],
                  skips=None if skips is None else [], objective=None if objective is None else [],
                  risk_state=None if risk_state is None else copy.deepcopy(risk_state))
        out: dict = {}
        res = _run_day_once(df, hist, symbol, p, tf, _ext=ext, _out=out, **sc, **kw)
        new = out.get("extras", [])
        nsig = _extra_sig(new)
        if (k == 0 and not new) or nsig == sig:
            break
        ext, sig = new, nsig
    for key, real in (("log", log), ("locks", locks), ("skips", skips), ("objective", objective)):
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
            risk_state: dict | None = None, week: dict | None = None, eve: tuple | None = None,
            prev_full: pd.DataFrame | None = None, _ext: list | None = None, _out: dict | None = None,
            objective: list | None = None, post_eve: pd.DataFrame | None = None, daily_all: dict | None = None) -> list[Trade]:
    """Trades for one day. With `live`, a position still open at the last bar is returned
    with no exit (exit_reason "open") instead of being closed at the last price.
    equity     (#12) start-of-day equity for risk_basis="equity"
    bias_by_cut  (#9) {lock minute: htf table row cut at that minute} for the draw lock
    meta       (#13) databento meta (adj, instrument_id, roll) covering the day
    locks / skips  optional lists that receive the session locks and the sloppy-day skips
    eth        (levels_detectors) {date: (o, h, l, c)} of full sessions, prior dates only
    risk_state (E10 loss_halving) {m, deficit, peak} carried across days by backtest.run (mutated)
    week       (day_week_context) the week's trade state before today: {n, net, final_hits, all_final} (backtest.week_state)
    eve        (day_week_context) (open, high, low, close) of the evening session (18:00-24:00) before today
    post_eve   (setups_models #4/7 ndog_scalp) the day's own bars from 16:00 to midnight (the 17:00 close, the 18:00 reopen, the Asian evening); read bar by bar, only after the engine's day ran
    prev_full  (levels_detectors #3/3) the previous trading day's FULL frame (midnight on): the previous day's London range (prev_london_pool) and
               the London-extreme-to-pre-NY range (london_lr_zone); the `hist` frames are regular-session only"""
    day = df.index[0].date()
    flat = _DW.flat_for(day, p, _eff_flat(p))                # N7.1 EARLY_CLOSE
    ff = _NC.fomc_flat_min(day, p)                        # N3 / N3.2: an FOMC day is flat at the release (0 = n/a)
    am_lo, am_hi = p.am_win                               # Ep01.10 am_from_0830
    ctx = DayCtx(df, day, hist, tf, p.htf, closes, p.or_minutes, evening if p.globex_pool else None, tf_lookback=p.tf_lookback)
    ctx.conf = conf
    ctx.gaps = gaps if (p.gap_mode == "ict" and gaps is not None) else None
    ctx.equity = float(equity) if (equity is not None and p.risk_basis == "equity") else p.account_equity
    ctx.symbol = symbol
    ctx.skips_ref = skips                                 # caption-gap OT-filters-before-bias: session_veto logs every veto here
    ctx.hist = hist
    ctx.no_origin = 4 * p.eq_tol_pts * p.es_pt if p.no_origin_retest else None     # caption-gap NEW-no-return-to-origin-ob: the "same daily low" tolerance (eq_tol_pts x 4)
    ctx.am_lunch_end = p.am[1]
    ctx.am_lunch_hl = _NC.am_range(ctx, p) if p.lunch else None     # T8: the AM range, complete before the lunch session
    ctx.lon_start = p.london_kz_start
    ctx.bias_row = bias                                   # setups_models: htf table row (draws)
    _BD.apply_open_src(ctx, p, intermarket)               # bias_htf D22: bias_open_src "spy" / "es_map"
    ctx.eth = eth
    ctx.daily_all = daily_all                             # caption-gap pass day_week_context#1/3: {date: close} of every completed session (season_min_rank composite; prior years only are read)
    ctx.eve = eve                                         # caption-gap new-intra-week-extreme-raid: the evening before today (Sunday's for a Monday)
    ctx.prev_full = prev_full
    _attach_meta(ctx, meta, p, symbol)
    _setup_news(ctx, day, p)
    _extra_levels(ctx, df, hist, p, eth, closes)           # levels_detectors
    pctx = DayCtx(partner[0], day, partner[1], tf) if partner is not None else None
    if pctx is not None:
        _setup_news(pctx, day, p)
        _extra_levels(pctx, partner[0], partner[1], p)
    mg = p.min_fvg_pts * p.es_pt
    sk = dict(c2_dir=p.fvg_c2_dir, vi_min_gap=p.vi_min_gap_pts * p.es_pt,   # levels_detectors A5 / A9
              mit_legacy=p.mit_legacy_order,                                  # A15 (review fix)
              single_bar=2.0 if p.single_bar_fvg_strict else 0.0,             # caption-gap pass (levels_detectors #1/3)
              vi_wick_overlap=p.vi_wick_overlap, vi_multi=p.vi_multi, bpr_def=p.bpr_def,
              bpr2_two_candle=p.bpr2_two_candle, pb_def=p.pb_def, mit_mt=p.mit_mt_invalid,
              vi_dead_rule=p.vi_dead_rule,
              mit_def=p.mit_def, ir_cfg=(p.ir_def, p.ir_overshoot_ticks, p.ir_body_mult))     # caption-gap pass (levels_detectors #2/3)
    sides = [Side(1, ctx.o, ctx.h, ctx.l, ctx.c, p.pivot_n, mg, **sk), Side(-1, ctx.o, ctx.h, ctx.l, ctx.c, p.pivot_n, mg, **sk)]
    psides = ppos = None
    if pctx is not None:
        psides = {1: Side(1, pctx.o, pctx.h, pctx.l, pctx.c, p.pivot_n, mg, **sk),
                  -1: Side(-1, pctx.o, pctx.h, pctx.l, pctx.c, p.pivot_n, mg, **sk)}
        ppos = pd.Series(np.arange(len(pctx.idx)), index=pctx.idx)
    _LD.attach_pool_tf(ctx, sides, p)                     # caption-gap B5 pool_tf
    _LD4.attach_td(ctx, sides, p)                         # caption-gap new-time-distortion: swings / zones of masked bars are dropped from the sides
    if psides is not None:
        _LD.attach_pool_tf(pctx, list(psides.values()), p)
    ctx.sides_map = {1: sides[0], -1: sides[1]}            # caption-gap setups_models #1/7: the live Sides (the other Side of the day: stop-run re-arm, pool runs, compressed highs)
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
    dt, block_side = day_context(hist, day, p, eth, conf)
    ctx.block_side = block_side
    if p.neutral_skip and "big_prev" in dt:
        if skips is not None:
            skips.append((day, symbol, "sloppy", "big_prev"))
        return []
    # owner #10: sloppy days ("off" = tag only; neutral_skip above is the old alias)
    sl_day = sloppy_day(hist, day, p, ctx.opens.get("midnight")) if p.sloppy_tests else set()
    sl_all_day = {r for r in sl_day if not r.endswith(":PM")}
    ctx.inside_zone, ctx.inside_side = None, 0
    if p.inside_bisi_release and "inside_bisi" in sl_all_day:
        ctx.inside_zone = _BH2E.inside_zone(hist)                  # caption-gap B17-inside-daily-range-no-trade (091 ~6:20): the stand-aside is released by a trade beyond the daily FVG
    rel_ = {"inside_bisi"} if ctx.inside_zone is not None else set()
    if p.sloppy_mode == "stand_aside" and (sl_all_day - rel_):
        if skips is not None:
            skips.append((day, symbol, "sloppy", "|".join(sorted(sl_all_day))))
        return []
    ctx.sl_day = sl_day
    if p.conflicted_mode != "off":                       # caption-gap X14-conflicted-htf-one-entry (091 ~00:10:44): both sides valid / inside a daily BISI-SIBI
        ctx.conflicted = _ME3.conflicted_day(hist, bias, p)
        if ctx.conflicted and p.conflicted_mode == "skip":
            if skips is not None:
                skips.append((day, symbol, "conflicted", "htf"))
            return []
    ctx.day_tags = "|".join(sorted(dt))
    ctx.bias_by_cut = bias_by_cut or {}                   # (bias_htf rows known before 09:30 come from these cuts)
    ctx.intermarket = intermarket or {}                   # (caption-gap bias_htf#3/7: the seasonal qualifiers of the DayPlan read the day's intermarket values)
    ctx.bh3_mwdl = bool(p.mwd_levels_entries)
    dw = _DW.plan(ctx, hist, p, week, eve, dt)            # day_week_context: the day's blocks / flags / tags
    p = _DWC.day_params(p, dw)                            # caption-gap pass day_week_context#1/3: iw_no_measured
    p = _DWC2.day_params(p, dw)                           # caption-gap pass day_week_context#2/3: expansion_mode "full", the Friday single exit, the consolidation scalp outs
    p = _DWC3.day_params(p, dw)                           # caption-gap pass day_week_context#3/3: choppy week - slow ladder, no runner
    _BD.plan(dw, ctx, hist, p, dt)                        # bias_htf: day tags, range_market reading, ctx.bh_on
    wl = dw.info.get("week_left")                         # D19 / X15: trades left in the week's budget (None = no cap)
    why_dw = next((r_ for ss_, r_ in dw.blocks if ss_ is None), None)
    if why_dw is not None:
        if skips is not None:
            skips.append((day, symbol, "day_week", why_dw))
        return []
    tt_ = df.index.hour * 60 + df.index.minute    # M12.3 or60: the 09:30-10:30 range (read from 10:30)
    o60 = df[(tt_ >= 570) & (tt_ < 630)]
    ctx.or60 = (float(o60.high.max()), float(o60.low.min())) if len(o60) else None
    ctx.bias_by_cut = bias_by_cut or {}
    chop = Chop(ctx, hist, p)
    if not p.consol_skip or dw.info.get("consol_nochop") or (dw.expansion and (("inside_day" in dw.expansion and p.b11_inside_expansion == "no_chop_skip")
                                               or ("nr" in dw.expansion and p.nr_expansion == "no_chop_skip"))):
        chop.inert = True                                 # N8.1 consol_skip off / B11 expansion due: no chop stand-aside
    ctx.chop = chop
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
    cpi_off = bool(p.cpi_from and "cpi" in tags)          # caption-gap N4-cpi-day-new-traders (030): a CPI day's entries start at cpi_from - no 09:00 windows, the AM opens there
    if cpi_off:
        am_start = max(am_start, p.cpi_from)
    pre8 = any(n_ == "PRE8" for n_, *_ in ew)
    pre_windows += [w_ for w_ in ew if w_[0] == "LON"]
    if p.pre_0700 or (p.pre_0700_hard_days and _NCT.hard_day(day)):       # (caption-gap new-premarket-difficult-days: the 07:00-08:30 window on a hard 08:30 day)
        pre_windows.append(("PRE7", 420, 500 if pre8 else 510))
    pre_windows += [w_ for w_ in ew if w_[0] == "PRE8"]
    if p.post_news and news(day) == "0830" and not nfp_hour and not am0830 and not cpi_off:
        pre_windows.append(("NEWS", 540, 570))
    if p.pre_0900 and not nfp_hour and not am0830 and not cpi_off and not (p.pre_0900_no_news and 510 in _NC.releases(day, p)):    # caption-gap N5-soft-bias-pre-open (007 ~00:11:21): pre_0900_no_news - 09:00-09:29 only on a day without an 08:30 release
        pre_windows.append(("PRE9", 540, 570))
    state = {"day": day, "reentered": {}, "re_ctx": {}, "re7": {}, "re3": {}, "only_side": {}, "reversed": {}, "day_pts": 0.0, "day_loss": False, "day_net": 0.0,
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
        want = _BD.bias_value(bias, p)                    # the 09:30 reading (reporting + the legacy day-level skip)
        if want == 0 and p.bias_neutral == "skip" and not p.want_all_engines:
            return []                                     # (want_all_engines: the skip is per session, from the row known at its bar)
    lock_t = _lock_times(p, day, pre_windows) if p.draw_lock == "session" else {}
    ctx.lock_t = lock_t                                   # bias_htf: the session start minutes (judas, row cuts)
    ctx.lock, all_locks, spent = {}, [], []
    ctx.prior_locks = locks if locks is not None else []        # caption-gap B17-unreached-draw-soft-bias (bias_htf#2/7): the earlier days' lock reports (the soft carry reads the last one)
    ctx.state7 = state                                    # caption-gap setups_models #7/7: the gates read the re-entry / split state, the trades of the day
    ctx.pend_now = None
    for i in range(ctx.start, len(ctx.t)):
        t = ctx.t[i]
        ts = ctx.idx[i]
        ctx.pend_now = pending
        if p.lunch_by_speed:
            _NCT.speed_adjust(ctx, p, lock_t, state, int(t), i)      # caption-gap T8-lunch-length-am-speed (cc10_012 ~00:02:56): the PM start follows the AM speed
        chop_before = chop.active_before(i) and p.sloppy_mode == "stand_aside"
        if p.am_idea_fail or p.reentry_breakaway:
            if _ME3.bar(ctx, i, p, state, done, trades, pos, (_BD.want_at(ctx, p, "AM", i) if (want is not None and p.am_idea_fail) else 0)) == "cancel_am" and pending is not None and pending["session"] == "AM":
                pending = None                       # caption-gap X13-am-fail-no-reverse-pm-reset: the AM idea failed (the opposite pool ran before any fill)
        if state["ext"]:
            _MG.sync_ext(trades, p, done, state, ts)       # X7c / X12 / X13a / X14b / X14d: the extras' closed trades count too
        # --- 1. manage the open position on this bar
        if pos is not None:
            tr, sd = pos["trade"], pos["side"]
            o, h, l, c = sd.o[i], sd.h[i], sd.l[i], sd.c[i]
            pos["best"] = max(pos["best"], h)         # X3h capture metric: the best-case run includes this bar
            if p.journal_timing:
                _DWC3.journal_bar(pos, sd, i, ts, p)  # caption-gap OT-X16-time-to-move-journal: MFE / MAE and the first favourable bar (read-only)
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
                a_time_ = i - a["i"] > max(1, p.pending_minutes // tf)
                a_oth_ = bool((pos["t1_done"] and not a.get("post_partial")) or chop_before
                              or (a.get("hold") is not None and i - 1 > a["i"] and sd.c[i - 1] < a["hold"])   # E12b add_hold
                              or (a.get("hold_es2") is not None and i - 1 > a["i"] and sd.c[i - 1] < a["hold_es2"])   # caption-gap E12-second-stage-ob-at-MT: a body close under the VI cancels the OB add
                              or _EN.add_cut_passed(sd, pos, i - 1, p)      # E12e: the cut passed on a closed bar
                              or (p.late_cutoff and t >= p.late_cutoff))    # T11: no adds in the last 15 minutes
                if a_time_ or a_oth_:
                    if p.refusal_breakaway and a_time_ and not a_oth_:
                        _ME1.add_missed(pos, p, a)                    # caption-gap A6-breakaway-by-refusal: an armed add that only TIMED OUT while price ran away (hold-break / chop / partial / cut cancels are no refusal)
                    pos["add"] = None
                elif a.get("now"):                    # caption-gap E12-single-add-variants (020 ~00:01:40): the momentum add - a market buy at the open after the arming close
                    px = float(o)
                    tr.adds.append((ts, sd.x(px), a["q"]))
                    pos["left"] += a["q"]; pos["basis"] += px * a["q"]; pos["n"] += a["q"]
                    pos["add"] = None
                elif a.get("up"):                     # caption-gap X8-downclose-wickce-add (085 ~00:10:04): a stop-direction add - filled when the bar trades UP to the wick CE (side space)
                    if h >= a["px"]:
                        px = max(float(o), float(a["px"]))
                        tr.adds.append((ts, sd.x(px), a["q"]))
                        pos["left"] += a["q"]; pos["basis"] += px * a["q"]; pos["n"] += a["q"]
                        pos["add"] = None
                elif a.get("market"):                 # E1 add_order "market": the open after a retest bar
                    if i - 1 > a["i"] and sd.l[i - 1] <= a["px"]:
                        px = float(o)
                        tr.adds.append((ts, sd.x(px), a["q"]))
                        pos["left"] += a["q"]; pos["basis"] += px * a["q"]; pos["n"] += a["q"]
                        pos["add"] = None
                        if a.get("stop_to") is not None and a["stop_to"] < px:
                            pos["stop_to_next"] = (a["stop_to"], i)
                elif _prints_through(l, a["px"], p) and (not a.get("down_only") or o > a["px"]):     # (caption-gap E12-add-while-falling-toward-VI: filled only on a down bar - one that opens above the limit and trades down into it)
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
            es3x_ = _ES3.exit_hit(pos, o, l) if (pos.get("es3_exits") and i > pos["fill_i"]) else None
            if es3x_ is not None and l > stop:
                tr.exits.append((ts, sd.x(es3x_[0]), pos["left"], es3x_[1])); pos["left"] = 0     # caption-gap new-probe-position / E12-631-vi-wickce-invalidation: a resting early exit (the probe cut, the OB MT before the displacement)
                _ES3.hit("exit_" + es3x_[1])
            elif o <= stop:
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
                    sp_ = _TP3.speed_state(pos, k, lv_, i, sd, p) if pos.get("tp3") else None    # caption-gap X3-full-pull-vs-mandatory-partial (092 ~1:30:11): the pool touched on the bar before is decided on the bar after (both closed)
                    if sp_ == "skip":
                        fr = pos["fracs"]
                        pos["k"] += 1
                        continue
                    hit_, px_ = _TP.rung_hit(pos, k, lv_[k], h, c, t, tf, p, xt_)     # Ep06.4 sd_close_hit
                    if sp_ == "pay":
                        hit_, px_ = True, lv_[k]
                    if hit_ and sp_ is None and pos.get("tp4") and p.ob_target_tod and _TP4.ob_skip(pos, k, t, tf, p):     # caption-gap A12-opposing-ob-time-of-day (cc04_003 ~00:34:17): a touched OB rung outside the profit-taking windows is a pause
                        fr = pos["fracs"]
                        pos["k"] += 1
                        continue
                    if not hit_:
                        break
                    if pos.get("me1"):
                        rh_ = _ME1.rung_hook(ctx, sd, pos, tr, k, lv_, h, c, i, ts, p, t, tf)      # caption-gap management_exits #1/3: best-case limit, SD time roll / body hold, the heavy T1
                        if rh_ == "skip":
                            fr = pos["fracs"]
                            pos["k"] += 1
                            continue
                        if rh_ == "break":
                            break
                    if pos.get("me3") and _ME3.rung_pre(ctx, sd, pos, tr, k, lv_, i, p, t) == "reload":      # caption-gap T10-1550-pool-timing: from 15:50 the pool rung leaves a runner past the pool
                        fr = pos["fracs"]
                        lv_ = _ME1.lv(pos)
                    if sp_ is None and pos.get("tp3") and _TP3.speed_hold(pos, k, i, sd, p):    # the touch bar: the pool is pending until the next bar closes
                        break
                    last = (k == len(lv_) - 1 and not pos.get("runner")) or _TP2.close_here(pos, k, tr, t, tf, p, ctx, sd, i, pctx, psides, ppos)   # Ep04.3 po3_runner; caption-gap L12-prior-session-swing-htf-extreme: a proj_htf rung with an SMT after 11:00 closes the trade
                    lh3_ = bool(not last and _ME3.lh_all(pos, t, p))   # caption-gap X11-last-hour-target-hit-done: from 15:00 any rung fill closes everything left (lh_target)
                    if last:
                        tr.final_hit = True                           # Ep04.13: every rung taken
                    q = pos["left"] if (last or lh3_) else min(pos["left"], max(p.lot, _lots(pos["n"] * fr[k], p.lot)))
                    tr.exits.append((ts, sd.x(px_), q, "lh_target" if lh3_ else f"t{k + 1}")); pos["left"] -= q
                    if (p.wick_read == "exit" and pos["left"] and pos.get("level_kinds")
                            and k < len(pos["level_kinds"]) and pos["level_kinds"][k] in ("wick", "wick_ce")):
                        pos["wick_chk"] = (i, lv_[k] + p.exit_before_pts * p.es_pt)      # A23: read the next close
                    pos["k"] += 1
                    if pos.get("me1"):
                        _ME1.rung_taken(ctx, sd, pos, tr, k, lv_[k], i, p)           # caption-gap management_exits #1/3: the run-through watch, the reached level, the delivery-speed tag
                        fr = pos["fracs"]
                        lv_ = _ME1.lv(pos)
                    if pos.get("me2"):
                        _ME2.rung_taken(ctx, sd, pos, tr, k, lv_[k], i, p)           # caption-gap management_exits #2/3: the pool lock, the swing trail at an array, the PM runner, the NWOG quarter, the urgency runner
                        fr = pos["fracs"]
                    if pos.get("me3"):
                        _ME3.rung_taken(ctx, sd, pos, tr, k, lv_[k], i, p)           # caption-gap management_exits #3/3: the last-hour early take, the reclaim runner's breakeven wait
                    if pos["left"] and k < len(pos.get("level_kinds") or ()) and pos["level_kinds"][k] == "speed":
                        _TP1.hit("speed_rung")           # caption-gap L10-A17-old-high-target-ladder: a speed-bump rung is a small partial only - no done flag, breakeven or trail
                        continue
                    pos["last_partial_i"] = i
                    if not pos["t1_done"]:
                        pos["t1_done"] = True
                        if p.be_on == "t1":
                            _MG.be_move(pos, p)                        # X4: + be_pad_pts / cost pad
                    if p.ladder_trail == "prior" and k >= 1 and not pos.get("day_trade") and _ME1.trail_ok(pos):
                        pos["stop"] = max(pos["stop"], _ME2.capv(pos, lv_[k - 1] - p.trail_pad))
                    pos["away"] = lv_[k]
                if (pos["t1_done"] and not pos.get("be_done") and p.be_on == "expansion"
                        and pos["last_partial_i"] < i and c > lv_[0]):
                    _MG.be_move(pos, p)                                       # breakeven after expansion
                    pos["be_done"] = True
            else:
                if not pos["t1_done"] and h >= pos["t1"] + p.exit_fill_through * p.tick + _ME1.rung_hit_off(p):      # (caption-gap E1-manual-touch-exits: exit_fill)
                    q = pos["left"] if pos["t2"] is None else max(p.lot, _lots(pos["left"] * p.partial, p.lot))
                    q = min(q, pos["left"])
                    tr.exits.append((ts, sd.x(_ME1.rung_px(pos["t1"], p)), q, "t1")); pos["left"] -= q
                    pos["t1_done"] = True
                    if p.be_on != "off":
                        _MG.be_move(pos, p)
                if pos["left"] and pos["t2"] is not None and pos["t1_done"] and h >= pos["t2"] + p.exit_fill_through * p.tick + _ME1.rung_hit_off(p):
                    tr.exits.append((ts, sd.x(_ME1.rung_px(pos["t2"], p)), pos["left"], "t2")); pos["left"] = 0
            if (pos["left"] and p.mgmt in ("ladder", "unit") and p.ladder_trail == "hit" and pos.get("away") is not None
                    and not pos.get("day_trade") and _ME1.trail_ok(pos)
                    and c >= pos["away"] + p.away_pts * p.es_pt):
                pos["stop"] = max(pos["stop"], _ME2.capv(pos, pos["away"] - p.trail_pad))   # price left the array
                pos["away"] = None
            if pos["left"] and p.ep07_body_exit and l < pos["body_low"]:
                px = min(o, pos["body_low"])           # traded below the swing low's lowest body
                tr.exits.append((ts, sd.x(px), pos["left"], "body_low")); pos["left"] = 0
            if pos["left"] and pos.get("be_at") is not None and h >= pos["be_at"]:
                _MG.be_move(pos, p)                                       # M12.3 cc_1h_ob: BE after 2R
            if pos["left"] and p.ep07_trail and not pos.get("trailed") and not pos.get("day_trade") and _ME1.trail_ok(pos) and not (pos.get("tp1") or {}).get("eve_bnb") and h > pos["swing_body"]:
                pos["stop"] = max(pos["stop"], pos["retr_low"] - p.trail_pad)
                pos["trailed"] = True
            if (pos["left"] and (p.ce_hold or pos.get("ce_hold")) and i > pos["fill_i"] and p.ce_exit == "close" and c < pos["fvg_ce"]
                    and not pos["t1_done"]):
                tr.exits.append((ts, sd.x(c), pos["left"], "ce_close")); pos["left"] = 0
            if (pos["left"] and pos.get("bz_mt") is not None and i > pos["fill_i"]
                    and (not pos["t1_done"] or p.breaker_mt_exit_after_t1) and (bx_ := _ME1.mt_exit_px(p, pos, o, l, c)) is not None):      # (caption-gap A13-breaker-mt-trade-test: breaker_mt_test)
                tr.exits.append((ts, sd.x(bx_), pos["left"], "breaker_mt")); pos["left"] = 0   # #6 (d)
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
            if pos["left"] and p.second_break_partial:
                _SM2.second_break_partial(ctx, sd, pos, tr, ts, i, p)            # caption-gap M12-second-takeout-turtle-soup: a failed shallow second break of a swept pool = a partial
            if pos["left"] and pos.get("sm3"):
                _SM3.manage(ctx, sd, pos, tr, i, ts, p)                          # caption-gap setups_models #3/7: vacuum-block stall / back, counter-scalp midnight open, IR acceleration hold
            if pos["left"] and pos.get("sm4"):
                _SM4.manage(ctx, sd, pos, tr, i, ts, p)                          # caption-gap setups_models #4/7: last-hour second unit, PM old-high add, the reversal gap fully re-traded
            if pos["left"] and pos.get("sm5"):
                _SM5.manage(ctx, sd, pos, tr, i, ts, p)                          # caption-gap setups_models #5/7: IFVG 061 CE exit, stair-step / MM stage / reclaimed-ladder adds
            if pos["left"] and pos.get("sm6"):
                _SM6.manage(ctx, sd, pos, tr, i, ts, p)                          # caption-gap setups_models #6/7: vacuum-block timeout / back under VB_low
            if pos["left"] and pos.get("sm7"):
                _SM7.manage(ctx, sd, pos, tr, i, ts, p)                          # caption-gap setups_models #7/7: the at_stop offside exit, the breakaway re-entry stop drop
            if pos["left"] and pos.get("es1"):
                _ES1.manage(ctx, sd, pos, tr, i, ts, p)                          # caption-gap entries_stops_sizing #1/3: PB wick exit, MT warn, strict IOFED
            if pos["left"] and pos.get("tp2"):
                _TP2.manage(ctx, sd, pos, tr, i, p)                              # caption-gap targets_partials #2/4: the lingering tag, the entry-low projection rung
            if pos["left"] and pos.get("tp4"):
                _TP4.manage(ctx, sd, pos, tr, i, ts, p)                          # caption-gap targets_partials #4/4: the runner stop, the strength read of OB1, the TGIF 066 roll / cover
            if pos["left"] and pos.get("me1"):
                _ME1.manage(ctx, sd, pos, tr, i, ts, p)                          # caption-gap management_exits #1/3: breakeven modes, stop locks, BPR / VI / IFVG / IOF exits, holds and tags
            if pos["left"] and pos.get("me2"):
                _ME2.manage(ctx, sd, pos, tr, i, ts, p, pctx, psides, ppos)       # caption-gap management_exits #2/3: the exits, partials and stop moves of the 34 trailing / partial specs
                if pos["left"] and p.chop_close:
                    _ME2.chop_close(pos, tr, sd, ts, c, chop, p, pos["fill_i"])   # caption-gap X9-lethargic-or-choppy-trade: the intraday chop turned on while the position was open
            if pos["left"] and pos.get("me3"):
                _ME3.manage(ctx, sd, pos, tr, i, ts, p, state, done, trades)      # caption-gap management_exits #3/3: the exits, partials and stop moves of the 33 specs
            if pos["left"]:
                pos["best"] = max(pos["best"], h)
                _MG.exits(ctx, sd, pos, tr, i, ts, _ME3.eff_p(pos, p), state)       # management_exits: X6-X12, X9 time stops, D18, Ep07.5 (caption-gap new-laggard-slow-delivery: the laggard's longer windows)
                if pos["left"] and not (pos.get("tp1") or {}).get("eve_bnb"):        # (caption-gap N4-eve-of-high-impact: the eve scalp keeps its initial stop - no trailing)
                    _MG.be_modes(sd, pos, tr, i, p)                # D14 / Ep03.15 after_mss / stall / pool breakeven
                    _MG.trail_extra(sd, pos, i, p)                 # Ep03.10 first-FVG and Ep03.20 measuring-gap trails
                    if (p.bpr2_trail or p.wick_bias_line) and _ME1.trail_ok(pos):      # (caption-gap stop locks: no BPR / wick-line stop raise inside a blocked or locked phase)
                        _LD.manage(ctx, sd, pos, tr, i, p)         # caption-gap A11 bpr2_trail / A23 wick_bias_line
            if (pos["left"] and tr.session in ("PRE7", "PRE8", "LON") and _ME1.flat_0830(day, p) and not (p.pre_0700_hard_days and tr.session == "PRE7" and _NCT.hard_day(day))     # (caption-gap new-premarket-difficult-days: a PRE7 position on a hard day is held through the release)
                         # (caption-gap N5-hold-through-0830: pre_flat_0830 unless the experienced hold_through_0830)
                    and t + tf >= 510):
                tr.exits.append((ts, sd.x(c), pos["left"], "pre_0830")); pos["left"] = 0     # N4: no position into the release
            if pos["left"] and tr.session == "LUNCH" and t + tf >= p.lunch_exit:
                tr.exits.append((ts, sd.x(c), pos["left"], "lunch_exit")); pos["left"] = 0   # T8: never held into the PM
            if pos["left"] and p.event_eve_noon:
                _NCT.event_eve_noon(ctx, sd, pos, tr, i, ts, p, day, int(t), tf, float(c))     # caption-gap X10-pre-nfp-noon-exit (050 ~00:52:31): the event-eve noon half-close
            if pos["left"] and p.lunch_trail_guard and t >= 710:
                _NCT.set_guard(ctx, p, pos, tr, sd, i)                 # caption-gap T8-lunch-raid-target: the AM trade's trail may not sit just beyond the lunch pool
            am_x_ = (min(p.am_exit, p.nfp_flat_by) if p.am_exit else p.nfp_flat_by) if (p.nfp_flat_by and "jobs" in tags) else p.am_exit     # caption-gap N1-nfp-no-htf-hold [our interpretation]: flat by nfp_flat_by on a jobs day
            if p.adr_met_runner and pos["left"] and am_x_ and tr.session not in ("PM", "LUNCH"):
                am_x_ = _DWC2.am_exit_for(ctx, sd, pos, tr, i, ts, p, am_x_, float(c))      # caption-gap L16-adr-contraction-runner (cc09_008 ~00:47:45): ADR5 covered by 09:30 - the runner share leaves at adr_runner_until
            if (pos["left"] and tr.session not in ("PM", "LUNCH") and am_x_ and t + tf >= am_x_
                    and not (p.no_lunch_retrace_hold and _ME1.am_exit_hold(ctx, sd, pos, tr, i, ts, p, am_x_, ev_flat=bool(p.nfp_flat_by and "jobs" in tags)))      # (caption-gap T9-strong-am-no-lunch-retrace: a held AM position skips the close)
                    and not (_ME3.am_on(p) and _ME3.am_skip(ctx, sd, pos, tr, i, ts, p, am_x_))):      # (caption-gap management_exits #3/3: day mode, the 85 % runner, the explosive-day runner, the trend-day hold)
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
            if pos["left"] and tr.session == "PM" and p.pm_done_by and pos["t1_done"] and t + tf >= p.pm_done_by and not _SM7.held(pos) and not (pos.get("tp3") or {}).get("hold_obj") and not (pos.get("me1") or {}).get("lunch_ext"):      # (caption-gap T9-strong-am-no-lunch-retrace: a PM entry after the lunch-high break keeps the last-hour window)
                tr.exits.append((ts, sd.x(c), pos["left"], "pm_done")); pos["left"] = 0
            if pos["left"] and ff and pos["fill_t"] < ff and t + tf >= ff:
                tr.exits.append((ts, sd.x(c), pos["left"], "fomc_flat")); pos["left"] = 0   # N3.2: never hold into the release
            if pos["left"] and _DW.day_exit(ctx, p, tr.session, t + tf):
                tr.exits.append((ts, sd.x(c), pos["left"], "consol_out")); pos["left"] = 0   # N8.3: consolidation-day AM out by 11:00
            if pos["left"] and p.adr_close_runner:
                _DWC2.adr_close_exit(ctx, sd, pos, tr, i, ts, p)         # caption-gap LLT3-adr-fib-close-zone (cc09_006 ~00:26:59): the runner leaves at H - 0.20 x ADR5 after the turn
            if pos["left"] and p.fri_trail_from:
                _DWC2.fri_trail(ctx, sd, pos, tr, i, p)                  # caption-gap X5-friday-tight-trail (103 ~00:30:33): the Friday stop ratchets under each new pivot low
            if pos["left"] and p.noon_rev_flat:
                _DWC3.noon_rev_exit(ctx, sd, pos, tr, i, ts, p, float(c))   # caption-gap T8-lunch-three-behaviours-reversal (059 ~00:15:28): the lunch reversal flattens the AM-direction position
            if pos["left"] and t + tf >= flat:
                tr.exits.append((ts, sd.x(c), pos["left"], "eod")); pos["left"] = 0
            if pos["left"] and p.daily_loss_pct > 0 and _ES3.daily_loss_hit(ctx, state, pos, tr, sd, i, ts, p):
                tr.exits.append((ts, sd.x(c), pos["left"], "daily_loss")); pos["left"] = 0     # caption-gap E11-funded-account-caps (050 ~00:48:18): the day's loss limit is reached - flat at this close
                _ES3.hit("daily_loss_flat")
            if pos["left"]:                            # #12: open risk against the current stop
                eq = ctx.equity
                if eq:
                    r_now = max(0.0, (pos["basis"] / pos["n"] - pos["stop"]) * pos["left"]) / eq
                    tr.peak_risk_pct = round(max(tr.peak_risk_pct or 0.0, r_now), 5)
            if not pos["left"]:
                lost_side = _after_close(pos, trades, p, done, state, i=i, ctx=ctx) or lost_side
                pos = None
            else:                                      # new FVG after the fill: trail / add
                if p.htf_resist_live and ctx.conf is not None and p.htf_resist_cap and _TP.resist_cfg(p)[0] and not pos.get("levels_frozen"):
                    _resist_live(ctx, sd, pos, i, p)
                new = [g for g in sd.gaps if g.i == i and g.i - 2 > pos["fill_i"]]
                if p.ob_grade_mult != (1.0, 1.0) and (pos.get("es2") or {}).get("ob_mt") is not None:
                    _ES2.grade_update(sd, pos, tr, i, p)                # caption-gap A12-mt-grading (cc04_003), review fix: the retest after the fill regrades the OB (later add sizes only; the tag keeps the fill-time grade)
                if (pos.get("es2") or {}).get("far_raise"):
                    _ES2.far_raise_update(sd, pos, i, p)                # caption-gap E2-far-edge-fvg-over-breaker (018 ~00:00:09): the short-term high broke - the stop rises to the breaker bottom (under its MT)
                if p.add_day_mode == "trend_day":
                    _ES2.trend_day_update(ctx, sd, pos, i, p)           # caption-gap E12-trend-day-adds (038 ~1:15:27): pos["td_ok"] / ["td_block"]
                if p.trail_wick_ce and not pos.get("day_trade") and _ME1.trail_ok(pos):
                    _ES3.trail_wick(sd, pos, i, p)                      # caption-gap E6-wick-ce-stop (022 ~01:14:11): the managed variant - each new defending wick raises the stop
                pos["dl_room"] = _ES3.dl_room(ctx, state, p, pos, tr, sd, i, ts) if p.daily_loss_pct > 0 else None     # caption-gap E11-funded-account-caps: an add's risk stays inside the day's loss limit
                can_add0 = (p.adds and pos["add"] is None and not pos.get("no_adds")
                            and (pos["dl_room"] is None or pos["dl_room"] > 0)
                            and not (chop.on and p.sloppy_mode == "stand_aside")
                            and not _EN.adds_blocked(ctx, sd, pos, i, p)                 # E12f
                            and not (state["day_loss"] and (not p.after_loss_adds or p.no_max_after_loss))   # Ep08.12
                            and not _EN.add_cut_passed(sd, pos, i, p)                     # E12e / D12
                            and not (p.late_cutoff and t >= p.late_cutoff))                # T11
                can_add = can_add0 and not pos["t1_done"]
                if can_add and p.add_momentum and _nadds(pos, tr) < len(p.adds) and _ES3.momentum_add(pos, tr, sd, i, p, ctx.equity):
                    can_add = False                                     # caption-gap E12-single-add-variants (020 ~00:01:40): the one market add as price runs from the OB
                if can_add0 and pos["t1_done"] and p.add_after_partial and _nadds(pos, tr) < len(p.adds) + 1:
                    _ES2.post_partial_add(ctx, sd, pos, tr, i, p, lambda px, size, fl: (_SM.add_ok(sd, pos, px, i, p) and _arm_add(pos, tr, px, i, p, ctx.equity, floor=fl, size=size) is None
                                                                                         and pos["add"] is not None))     # caption-gap E12-adds-after-partials-intraday
                if p.pm_ep01_adds and pos.get("kind") == "pm_ep01":
                    _SM.ep01_manage(ctx, sd, pos, tr, i, p, bool(can_add))   # M5.1: the Ep 01 sequence
                    new, can_add = [], False
                ov_ = None
                if can_add and p.add_pref_ob_in_vi and p.add_mode == "fvg" and _nadds(pos, tr) < len(p.adds):
                    ov_ = _ES1.ob_in_vi_add(sd, pos, i, p)           # caption-gap A5-ob-in-vi-over-newer-fvg (009 ~12:07): the OB that traded into a VI is the add, not the newer small FVG
                if new:
                    g = new[-1]
                    if not pos.get("day_trade") and _ME1.trail_ok(pos) and _LD3.trail_ok(sd, pos, g, i, p) and (    # X5c: a day trade keeps its initial stop (A6: never behind a common gap)
                            p.trail or pos.get("trail_now") or (p.mgmt in ("ladder", "unit") and p.ladder_trail == "fvg" and pos["t1_done"]
                                        and pos["k"] >= p.trail_after            # Ep03.20: after N rounds of partials
                                        and g.i - 2 > pos["last_partial_i"])):   # formed since the partial
                        ref_ = (g.bottom if (p.trail_ref == "gap" and not (pos.get("me1") or {}).get("trail_body")) else
                                float(min(min(sd.o[k_], sd.c[k_]) for k_ in range(g.i - 2, g.i + 1))))   # Ep01.20 body
                        if ref_ - p.trail_pad > pos["stop"]:
                            pos["trail_ref"] = (float(g.bottom), float(g.top), int(g.i))      # caption-gap X13-reentry-after-trail-stop-in-profit: the structure the stop was trailed under (recorded only when the stop rose)
                        pos["stop"] = max(pos["stop"], _ME2.capv(pos, ref_ - p.trail_pad))      # (caption-gap new-small-fvg-last-line: a stop_cap refuses the level)
                    apx = _EN.add_px(g, p)                         # E12 add_points
                    if ov_ is not None and can_add and _SM.add_ok(sd, pos, ov_[0], i, p, form=ov_[2]):
                        _arm_add(pos, tr, ov_[0], i, p, ctx.equity, floor=ov_[1])
                        can_add = pos["add"] is None
                    elif (can_add and p.add_mode == "fvg" and _nadds(pos, tr) < len(p.adds)
                            and _SM.add_ok(sd, pos, apx, i, p, form=float(g.bottom))):
                        _arm_add(pos, tr, apx, i, p, ctx.equity, floor=g.bottom, g=g, pos_g=True)
                        can_add = pos["add"] is None
                if ov_ is not None and not new and can_add and _SM.add_ok(sd, pos, ov_[0], i, p, form=ov_[2]):
                    _arm_add(pos, tr, ov_[0], i, p, ctx.equity, floor=ov_[1])        # review fix (A5-ob-in-vi-over-newer-fvg): the OB-in-VI add also stands when no newer FVG printed
                    can_add = pos["add"] is None
                if can_add and p.cisd_adds and (pos.get("es1") or {}).get("cisd") and _nadds(pos, tr) < len(p.adds):
                    _ES1.cisd_add(sd, pos, tr, i, p, lambda px, fl: _SM.add_ok(sd, pos, px, i, p) and _arm_add(pos, tr, px, i, p, ctx.equity, floor=fl) is None)    # caption-gap A12-cisd-open-buy-level (032 ~55:30): each later CISD run's open is an add
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
                                                                 or p.ts_adds_breakers or p.ts_breaker_pyramid or p.two_chance):
                    _SM.more_adds(ctx, sd, pos, tr, i, p)          # setups_models Ep05.4 / M4 / M12.2 / M4.4
                    can_add = pos["add"] is None
                if can_add and _nadds(pos, tr) < len(p.adds) and p.add_arrays:       # E12b + owner #7 htf_fvg
                    arm_ = lambda px, floor=None, extra=0.0: (_SM.add_ok(sd, pos, px, i, p, form=floor)
                                                              and _arm_add(pos, tr, px, i, p, ctx.equity, floor=floor,
                                                                           extra_room=extra) is None
                                                              and pos["add"] is not None)
                    _EN.more_add_arrays(ctx, sd, pos, tr, i, p, arm_)
                    can_add = pos["add"] is None
                if can_add and _nadds(pos, tr) < len(p.adds) and _ES2.add_loc_on(p):          # caption-gap E12 add locations (far edge / wick retouch / 30m FVG / IFVG / IFVG-OB / VI early / VI-OB)
                    _ES2.add_locations(ctx, sd, pos, tr, i, p, lambda px, floor=None, form=None: (_SM.add_ok(sd, pos, px, i, p, form=floor if form is None else form) and _arm_add(pos, tr, px, i, p, ctx.equity, floor=floor) is None
                                                                                        and pos["add"] is not None))
                    can_add = pos["add"] is None
                if can_add and _nadds(pos, tr) < len(p.adds) and _ES3.add_locs3_on(p):          # caption-gap entries_stops_sizing #3/3: 5m wick CE / VI ladder / void / gate-candle wick / reclaimed-OB adds
                    _ES3.add_locations3(ctx, sd, pos, tr, i, p, lambda px, floor=None, size=None: (_SM.add_ok(sd, pos, px, i, p, form=floor) and _arm_add(pos, tr, px, i, p, ctx.equity, floor=floor, size=size) is None
                                                                                                    and pos["add"] is not None))
                    can_add = pos["add"] is None
                if can_add and p.add_on == "retest":                            # Ep01.18
                    _EN.retest_add(sd, pos, tr, i, p, lambda px: _arm_add(pos, tr, px, i, p, ctx.equity, floor=pos["fvg_bottom"], dig_g=_ES3.entry_zone(pos)))
                    can_add = pos["add"] is None
                if can_add and (p.add_low_end or p.add_fvg_low_end or p.add_fvg_low):   # E12c / E12 / Ep04.10
                    _EN.low_end_add(sd, pos, tr, i, p, lambda px, size: _arm_add(pos, tr, px, i, p, ctx.equity, size=size))
                if p.add_form_eq and pos.get("es2_cal") and "cal_check" not in (tr.lv_tags or ""):
                    tr.lv_tags = "|".join(x for x in (tr.lv_tags, "cal_check") if x)      # caption-gap E12-add-cutoff-definition (092 ~1:16:43): an array formed on the draw side of the implied EQ is a calibration check only
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
                and t + tf >= p.am_exit and not _ME3.noon_exempt(pending, p)):
            pending = None                           # #8 guard: no AM-family fills into 12:00
        if pending is not None and p.fvg_full_fill_void and _ME1.void_pending(pending, pending["side"], i):
            pending = None                           # caption-gap X9-entry-fvg-immediate-rejection: a print through the entry FVG's far edge voids the resting order
        if pending is not None:
            sd = pending["side"]
            cut = {"AM": am_hi, "PM": p.pm[1], "PRE7": 510, "PRE8": _ME1.pre8_cut(day, p), "PRE9": 570,
                   "NEWS": 570, "LON": 300, "LUNCH": p.lunch_win[1], "PO3R": p.am_exit or 720}[pending["session"]]
            if pending.get("done_key", "").startswith("SB_"):
                cut = p.sb_windows[0][1] if pending["session"] == "AM" else p.sb_windows[1][1]
            if p.sb_only:                               # fills only inside the session's SB window
                sb_a, cut = p.sb_windows[0] if pending["session"] == "AM" else p.sb_windows[1]
            if pending.get("cut_at"):                   # caption-gap setups_models #7/7: a window-less order (London-close scalp, 10:50 macro, lunch macro) lives until its own cut
                cut = int(pending["cut_at"])
            if pending.get("cut"):                      # setups_models: M5 / M5.1 15:45
                cut = min(cut, pending["cut"])
            c0825_ = _ME1.entry_cut_0825(day, p, pending["session"])      # caption-gap N5-hold-through-0830: no new entries 08:25-08:30 on a release day
            if c0825_ is not None:
                cut = min(cut, c0825_)
            if p.ote_reanchor and (pending.get("es1") or {}).get("ote_leg") and i - 1 > pending["i"]:
                np_ = _ES1.ote_reprice(sd, pending, i - 1, p)       # caption-gap M13-reanchor-parent: a new swing high above H (no trade under L) moves the band
                if np_ is not None:
                    pending = np_
            pending = _ES2.convert_pending(pending, sd, i, p)           # caption-gap E1-market-on-touch / E5-breakaway-gap-chase: a touched / N-bar-old order becomes a market order at this bar's open
            ob_pre = pending.get("ob_pre", False)
            mkt = pending.get("market") or pending.get("stop_entry")
            if pending.get("es2_dead") or t >= cut or (i - max(pending["i"], pending.get("anchor_i", -1)) > max(1, p.pending_minutes // tf) and not pending.get("no_expire")):
                pending = None                       # (caption-gap A12 range_lock / A21 breaker_range_hold: no_expire - the order rests until its range breaks)
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
            elif (p.poke_high_cancel and pending["session"] != "PM" and i - 1 > pending["i"]
                  and _SM2.poke_cancel(ctx, sd, i - 1, p, pending["session"]) is not None):
                pending = None                       # caption-gap A4-wick-poke-vi-invalidation: the trade beyond the poke high cancels the PENDING AM order too
                _SM2.hit("poke_pending")
            elif (pending.get("cancel_low") is not None and i - 1 > pending["i"]
                  and sd.l[i - 1] < pending["cancel_low"]):
                pending = None                       # setups_models M11b: the OB low traded
            elif (pending.get("cancel_close") is not None and i - 1 > pending["i"]
                  and sd.c[i - 1] < pending["cancel_close"]):
                pending = None                       # caption-gap A12-range-internal-ignore: a body close below the OB MT / the range low
            elif pending.get("cancel_close_tf") is not None and i - 1 > pending["i"] and _SM5.tf_close_cancel(ctx, sd, pending, i - 1):
                pending = None                       # caption-gap A4-bodies-hold-prev-day-50 (pd50_tf > base): a completed m-minute bar closed under the previous day's 50%
            elif pending.get("m2_live") and i - 1 > pending["i"] and _SM4.m2_order_dead(sd, pending, i - 1):
                pending = None                       # caption-gap M2-leg-eq-after-low-prints: the leg EQ moved above the order's gap
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
                  (_ES1.pd_line(ctx, sd, p, pending, i) if (_ES1.pd_active(p) or pending.get("pd_top") is not None) else
                   pending.get("leg_lo", pending["ext"]) + p.leg_pd * ((pending["leg_hi0"] if pending.get("no_new_extreme") else
                                                sd.h[pending["ext_i"]:i].max()) - pending.get("leg_lo", pending["ext"])))):
                pass                                 # not yet in the leg's discount: wait (M2.4: leg high frozen)
            elif p.daily_loss_pct > 0 and pos is None and _ES3.dl_blocks_order(pending, ctx, state, p):
                pending = None                       # caption-gap E11-funded-account-caps: the closed losses of the day + this order's risk would reach the day's loss limit
                _f("x_daily_loss")
            elif pending.get("mtf_gap") is not None and i - 1 > pending["i"] and _ES1.mtf_pending_dead(ctx, sd, pending, i - 1, p):
                pending = None                       # review fix A5-multitf-hold-test (064 ~1:32:01): two or more 1-4m closes inside the 5m entry gap while the limit rests cancel it
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
                if o.get("htf_runner") is not None:   # caption-gap L14-monthly-to-weekly-range (cc07_001 ~00:09:47): a small final slice is held to the HTF range's level
                    lv_f, kd_f, fr_f = _TP1.runner_rung(list(lv_f), list(kd_f or ["array"] * len(lv_f)), list(fr_f), o["htf_runner"], p)
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
                           zone_top=o.get("zone_top"), plan_shares=o.get("plan_shares", o["shares"]), sm3=o.get("sm3"), sm4=o.get("sm4"), sm5=o.get("sm5"),
                           tp1=dict(speed=o.get("tp1_speed", ()), eve_bnb=bool(o.get("eve_bnb"))),       # caption-gap targets_partials #1/4: the live-cap speed-bump timeframes, the eve scalp's hold
                           **_swing_ref(sd, o["ext_i"], i))
                if pos["runner"]:                    # Ep04.3: the last fraction has no target
                    lv0 = pos["levels"][:-1] if (pos["final_T"] and len(pos["levels"]) > 1) else pos["levels"]
                    pos.update(levels=lv0[:max(1, len(pos["fracs"]) - 1)], final_T=False)
                if o.get("rung_plan"):
                    tr.rungs = "|".join(f"{sd.x(v_):.2f}:{k_}:{f_:.2f}" for v_, k_, f_ in zip(lv_f, kd_f, fr_f))
                state["fill_slow_chop"] = bool(p.chop_one_win and (chop.on or _slow_day(p, ctx, hist, i)))
                _MG.init_pos(ctx, sd, pos, tr, o, i, p, state)        # management_exits: per-position data at the fill
                if o.get("sm4"):
                    _SM4.on_fill(ctx, sd, pos, tr, o, i, p)           # caption-gap setups_models #4/7: fill-time levels (resting PO3 order), tagged management
                if o.get("sm5"):
                    _SM5.on_fill(ctx, sd, pos, tr, o, i, p)           # caption-gap setups_models #5/7: open_into_ob tag, A-B anchor filled, MM / reclaim sweep reference
                if o.get("sm6"):
                    _SM6.on_fill(ctx, sd, pos, tr, o, i, p)           # caption-gap setups_models #6/7: the vacuum-block fill state
                if o.get("sm7"):
                    _SM7.on_fill(ctx, sd, pos, tr, o, i, p)           # caption-gap setups_models #7/7: hold-to-close, the at_stop reversal watch, the breakaway re-entry stop drop
                if o.get("es1"):
                    _ES1.on_fill(ctx, sd, pos, tr, o, i, p)           # caption-gap entries_stops_sizing #1/3: the PB-wick exit, the MT warn tag, the strict IOFED watch, the CISD adds
                _ES3.on_fill(ctx, sd, pos, tr, o, i, p, fill)             # caption-gap entries_stops_sizing #3/3: initial risk, the OB MT / probe exits, the gate candle, the near-HTF room
                if o.get("tp2") or p.sd_anchor == "entry_low":
                    _TP2.on_fill(ctx, sd, pos, tr, o, i, p)               # caption-gap targets_partials #2/4: the lingering window, the entry-low anchor
                if o.get("tp3_speed") or o.get("tp3_hold"):
                    _TP3.on_fill(ctx, sd, pos, tr, o, i, p)               # caption-gap targets_partials #3/4: the pay_first speed exception
                if o.get("tp4"):
                    _TP4.on_fill(ctx, sd, pos, tr, o, i, p, fill)         # caption-gap targets_partials #4/4: the runner stop, OB1, the TGIF 066 levels, the trail from the fill
                if o.get("me1") or _ME1.any_on(p):
                    _ME1.on_fill(ctx, sd, pos, tr, o, i, p, fill)         # caption-gap management_exits #1/3: the breakeven / lock / hold state, the best-case limit, the BPR / IFVG exits
                if o.get("me2") or _ME2.any_on(p):
                    _ME2.on_fill(ctx, sd, pos, tr, o, i, p, fill)         # caption-gap management_exits #2/3: the trail / partial / exit state of the 34 specs
                if o.get("me3") or _ME3.any_on(p):
                    _ME3.on_fill(ctx, sd, pos, tr, o, i, p, fill, state, done)       # caption-gap management_exits #3/3: the implied range, the laggard, the scalp rung, the recovery state
                if o.get("es2"):
                    _ES2.on_fill(ctx, sd, pos, tr, o, i, p, fill)      # caption-gap entries_stops_sizing #2/3: the OB grade, the FVG-then-OB add, the zone-ladder add base
                _SM7.fill_note(state, o)                              # caption-gap setups_models #7/7: the re-entry / reversal context is no longer pending
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
                elif p.fvg_full_fill_void and (vx_ := _ME1.void_fill_bar(pos, sd, i, fill)) is not None:
                    tr.exits.append((ts, sd.x(vx_), pos["left"], "fvg_void")); pos["left"] = 0     # caption-gap X9-entry-fvg-immediate-rejection: the fill bar traded on through the far edge
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
        if p.sloppy_tests or p.chop_wait_bars:
            chop.update(i)
        if (p.nfp_release_fvg or p.post_news_continuation or p.release_ob_entry) and pending is None and pos is None:
            o_x = _SM2.release_setups(ctx, sides, i, p, state, pos, pending, _risk_mult(state, "NEWS", p), done)     # caption-gap N1 / N5: the release setups (bypass the news windows for themselves)
            if o_x is not None:
                pending = o_x
        if lock_t:
            pending = _lock_step(ctx, p, lock_t, i, t, bias_by_cut, done, spent, all_locks, pending, state)
        if _SM4.any_special4(p) and pending is None and pos is None:
            o_x = _SM4.special4(ctx, sides, i, p, state, pos, pending, _risk_mult(state, "AM", p), done)     # caption-gap setups_models #4/7: the 00:00 resting PO3 order, the lunch-macro NWOG long (outside the session windows)
            if o_x is not None:
                pending = o_x
        if _SM5.any_special5(p) and pending is None and pos is None:
            o_x = _SM5.special5(ctx, sides, i, p, state, pos, pending, _risk_mult(state, "PM", p), done)     # caption-gap setups_models #5/7: the lunch-hour ORG-CE short
            if o_x is not None:
                pending = o_x
        if _SM7.any_special7(p) and pending is None and pos is None:
            o_x = _SM7.special7(ctx, sides, i, p, state, pos, pending, _risk_mult(state, "AM", p), done)     # caption-gap setups_models #7/7: the London-close scalp, the 10:50 macro, the lunch macro, the NY expansion turtle soup
            if o_x is not None:
                pending = o_x
        if _NCT.any_special(p) and pending is None and pos is None:
            o_x = _NCT.special(ctx, sides, i, p, state, pos, pending, _risk_mult(state, "AM", p), done)     # caption-gap news_calendar_times#1/1: the post-news fade (08:30-09:30) and the pre-open buy (08:00-09:00)
            if o_x is not None:
                pending = o_x
        if state.get("flip_req") and pending is None and pos is None:
            pending = _ME3.flip_order(ctx, state, i, p, 1.0) or pending       # caption-gap X8-offside-flip: the market reversal at the next open (it overrides the no-reversal lock once)
        if p.probe_mult > 0 and want is not None and pending is None and pos is None and am_lo <= t < am_hi and not _MG.blocked_now(state, "AM"):
            o_x = _ES3.probe_order(ctx, sides, i, p, state, trades, done, _BD.want_at(ctx, p, "AM", i), ctx.lock.get("AM"))     # caption-gap new-probe-position (026 ~00:16:16): a small market probe on an indecisive session
            if o_x is not None:
                pending = o_x
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
            elif p.lunch_htf_program and p.lunch_macro_win[0] <= t < p.lunch_macro_win[1]:
                session, w0, wa, wb = "LUNCH", p.lunch_macro_win[0], p.lunch_macro_win[0], p.lunch_macro_win[1]    # caption-gap T7-lunch-macro-htf-program: the normal model inside the lunch macro (the bias-against short after the REH raid)
            elif state.get("pm0", p.pm[0]) <= t < p.pm[1]:
                pm0_ = state.get("pm0", p.pm[0])               # (caption-gap T8-lunch-length-am-speed: lunch_by_speed moves the PM start)
                session, w0, wa, wb = "PM", pm0_, pm0_, p.pm[1]
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
        why_, cx_ = _NCT.gate2(ctx, p, day, session, int(t), i, wb, trades, done, state, pos, pending)     # caption-gap news_calendar_times#1/1 per-bar gates
        if cx_ and pending is not None and pending.get("session") == session:
            pending = None                                    # (an order armed earlier does not fill into a rule that has switched on since)
        if why_ is not None:
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
        if done[session] and (p.sb_setup or _TP4.tgif_pm_slot(ctx, p, session, t)) and _in_sb(t, p) and not state.get("day_done"):     # (caption-gap M14-tgif-management: one more TGIF entry in the PM window)
            done_key = "SB_" + session                # the Silver Bullet window's own trade
            done.setdefault(done_key, False)
        lh_slot = (session == "PM" and _SM.lh_on(p, "last_hour_own_slot")
                   and p.last_hour[0] <= t < p.last_hour[1])
        if lh_slot:                                   # setups_models M5.2 / Ep01.13: own LH slot
            done_key = "LH"
            done.setdefault("LH", False)
        skip_main = (t < w0 or done[done_key] or pos is not None
                     or (wl is not None and _DW.budget_full(ctx, ts, trades, state["ext"])))   # D19 / X15 week budget, all engines
        if _MG.blocked_now(state, session):
            continue                                  # X7c / X12 / X13a / X14b / X14d: the session or the day is stopped
        if (session == "PM" and p.pm_consol_exit and t >= p.pm_consol_exit and pos is None
                and _MG.consol_day(ctx, i, p)):
            continue                                  # X11c: a consolidation PM starts nothing after the exit time
        pmr = (p.pm_reversal and session == "PM" and pos is None and pending is None and t >= w0
               and not done.get("PMR"))
        if skip_main and not pmr:
            continue
        if _DWC3.session_veto(ctx, p, day, session, int(t), blocked, news) is not None:
            continue                                  # caption-gap OT-filters-before-bias: the explicit veto order (blocked() then skip_news), before any bias is read
        why_ = _DW.gate(ctx, p, session, i, t, trades)        # day_week_context: the day / week rules (N7-N10, X10d, X15d ...)
        if why_ is not None:
            _f(why_)
            pending = None                            # an order armed earlier does not fill into a day / week rule that has
            continue                                  # switched on since (the Silver Bullet drops its order the same way)
        sl_now = set(sl_day if session == "PM" else sl_all_day)
        if ctx.inside_zone is not None:
            sl_now = _BH2E.sloppy_release(ctx, p, sl_now, i)       # caption-gap B17-inside-daily-range-no-trade: from the first bar beyond the FVG's high / low, that side only
        if chop.on:
            sl_now.add("chop")
        if p.sloppy_mode == "stand_aside" and sl_now:
            _DWC3.log_veto(ctx, day, session, "sloppy:" + "|".join(sorted(sl_now)))     # caption-gap OT-filters-before-bias: the sloppy stand-aside is a logged veto too
            continue                                  # #10: no new entries while sloppy
        ctx.cur_sloppy = "|".join(sorted(sl_now))
        if pmr:                                       # setups_models M6: after the objective
            done.setdefault("PMR", False)
            ctx.cur_lock, ctx.cur_lock_any, ctx.cur_bias, armed = None, None, 0, False
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
        flip_ = bool(state.get("mm_flip", {}).get(session))      # caption-gap M1-one-segment: mm_flip - the session may reverse into the MM leg of the other side
        if lk is not None and lk["delivered"]:
            org_ok_ = lh_slot and p.lh_org_fill and _SM4.lh_org_open(ctx, i, p)      # caption-gap M5-lasthour-reversal-into-org: the last hour may still trade toward an unfilled ORG
            org_ok_ = bool(org_ok_ or (lh_slot and _SM7.lh_after_open(ctx, i, p)))   # caption-gap T7-lasthour-after-target: ... or the reversal after a noon-delivered objective
            if not org_ok_ and not flip_ and not lk.get("ct_open") and not (lh_slot and p.lh_no_lock and not _SM.lh_on(p, "lh_htf_done_skip") and not p.pm_last_hour_model):
                continue                              # #9: the session's draw delivered - done (caption-gap BH-B3-counter-bias-modes: allow_counter_trend reopens it for the counter-bias trade)
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
                    and (not (p.lost_side_session or p.lost_side_scope == "session") or _ME3.lost_side_holds(state, session, t, p))      # (caption-gap X13-am-fail-no-reverse-pm-reset: lost_side_scope "session" lapses at pm_reset_t)
                    and not state["only_side"].get(session)):
                continue                              # no reversals after a loss (X13a: lost_side_session = this session only;
                                                      # reverse_in_session is the one reversal the lock lets through)
            os_ = state["only_side"].get(session)
            if os_ and sd.sign != os_:
                continue                              # X13a reverse_in_session: the opposite side only
            rc_ = state["re_ctx"].get(session)
            if rc_ is not None and rc_.get("pending") and p.reentry_gate and sname != rc_["side"]:
                continue                              # X13b: a re-entry is the same direction only
            r7_ = state["re7"].get(session)
            if r7_ is not None and r7_.get("pending") and r7_["kind"] in ("win", "trail_win", "ts_re") and sname != r7_["side"]:
                continue                              # caption-gap X14 / X13 re-entries (setups_models #7/7): the same direction only
            ctx.re7, ctx.re_ctx_now, ctx.pend_now = r7_, rc_, pending
            ctx.re3_now = state["re3"].get(session)          # caption-gap management_exits #3/3: the OTE-failure turtle soup / breakaway re-entry context
            ctx.pb_flip = state.get("pb_flip", {}).get(session)          # caption-gap A16-propulsion-block-full: the failed propulsion block (an entry array of the flipped side)
            if p.weekly_bias and ctx.wbias == -sd.sign:
                continue
            w_ = _BD.want_at(ctx, p, session, i) if want is not None else 0     # B3: the bias known at THIS bar (pre-09:30 sessions: their own cut)
            if flip_ and state["only_side"].get(session) == sd.sign:
                w_ = sd.sign                                  # caption-gap M1-one-segment: the flipped leg trades its own side (the bias read the first leg)
            counter_, curve_ = False, ""
            ct_ = _BH1E.counter_kind(ctx, sd, i, p, w_ if want is not None else 0, session) if p.allow_counter_trend else ""      # caption-gap BH-B3-counter-bias-modes (095 ~11:56): the counter-bias trade after the delivered draw
            if not ct_ and p.counter_range_extreme and want is not None:
                ct_ = _BH3E.counter_kind(ctx, sd, i, p, w_, session)             # caption-gap B3-countertrend-from-range-extreme (bias_htf#3/7): the counter-trend day trade at a 20-day range extreme
            if want is not None:
                if w_ and w_ != sd.sign:
                    if p.stoprun_rearm:
                        _SM2.against_bias_break(ctx, sd, i, p, session, w_)    # caption-gap A19: a break against the bias flow is a stop run - arm the bias side
                    if not p.counter_scalp:
                        curve_ = _SM6.counter_kind(ctx, sd, i, p, w_) if (p.curve_short or p.pmh_contrarian) else ""     # caption-gap M1-short-sell-side-of-buy-curve / M12-contrarian-pmh (setups_models #6/7)
                        if not curve_ and (p.m0950_branch in ("rev", "both") or p.allow_opposite_after_target in ("lod", "both")):
                            curve_ = _SM7.counter_kind7(ctx, sd, i, p, w_)       # caption-gap T7-0950-reversal-or-continuation / X14-opposite-second-trade-after-win (setups_models #7/7)
                        if not curve_ and ct_:
                            curve_ = ct_
                        if not curve_:
                            continue
                    else:
                        counter_ = True                   # caption-gap new-counter-bias-scalp-exit (013 ~15:07): an opt-in scalp against the bias
                if not w_ and p.bias_neutral == "skip":
                    continue
            if ct_ and not curve_ and not counter_:
                curve_ = ct_                                  # (with no bias filter, or a bias that agrees / is neutral, the reopened session still trades its counter side as the single-exit counter-trend order)
            if p.three_day_rule and sd.sign in block_side.get("three", ()):
                continue
            if p.tgif and sd.sign in block_side.get("tgif", ()):
                continue
            if sd.sign in block_side.get("year_end", ()):
                continue                              # #3 (off by default)
            why_ = _DW.side_ok(ctx, p, sd.sign, session, i)
            if why_ is not None and not ((counter_ or curve_) and why_ == "x_bh_want"):
                _f(why_)
                continue                              # day_week_context: outside day, ORG tell, strong Thursday, ... (a counter-bias scalp skips only the bias-side rule)
            if jb_side and sd.sign == jb_side:
                _f("x_news_judas")
                continue                              # M9 / M9.2: the first run after the release is the losing side
            why_ = _NC.side_filter(ctx, p, session, sd.sign, i, t)
            if why_ is not None:
                _f(why_)
                continue                              # T4 or_bias / or_wide, T9 pm_continue_am
            why_ = _NCT.side2(ctx, p, day, session, sd.sign, i, int(t))
            if why_ is not None:
                _f(why_)
                continue                              # caption-gap news_calendar_times#1/1 side filters
            if lk is not None and lk["side"] and sd.sign != lk["side"] and not counter_ and not curve_:
                continue                              # #9: trade only toward the locked draw
            if state.get("flip") and sd.sign != state["flip"]:
                continue                              # B8f stop_flip: the other side for the day
            if p.late_cutoff and t >= p.late_cutoff and _MG.is_fade(ctx, sd, lk, i):
                continue                              # T11 (026 ~1:59:50): no fades in the last 15 minutes
            # (review fix setups_models #4/7 smt_trend_ignore: the lock / bias context of THIS side is set before the SMT filter so trend_day reads it)
            ctx.cur_lock = lk if (lk is not None and lk["side"] == sd.sign) else None
            ctx.cur_lock_any = lk                     # review fix (setups_models #3/7 breaker_need_bias_draw): the session lock of ANY side (a neutral lock must not fall back to the row draw)
            ctx.cur_bias = lk["side"] if (lk is not None and lk["side"]) else (w_ or 0)
            sd.ctx_bias = ctx.cur_bias                # A16 pb_def cc04_008 step (1): the bullish context of the propulsion block
            smtb = _MG.smt_bias(ctx, i, p) if p.smt_bias != "off" else 0
            if p.smt_bias == "filter" and smtb and sd.sign != smtb:
                if p.smt_trend_ignore and _SM4.trend_day(ctx, sd, i, p):    # (caption-gap M16-trending-divergence-continuation: on a trending day the divergence is continuation)
                    _SM2.hit("trend_waive")
                else:
                    continue                          # B18.3: against the SMT bias
            ctx.counter_now = counter_
            ctx.curve_now = curve_
            o_ = _scan(ctx, sd, i, (replace(p, sick_sister=True) if (r7_ is not None and r7_.get("pending") and r7_["kind"] == "reverse" and r7_["variant"] == "sick_sister") else p),
                       session, w0, pctx, psides, ppos, _risk_mult(state, session, p))
            ctx.counter_now = False
            ctx.curve_now = ""
            if o_ is not None and flip_ and state["only_side"].get(session) == sd.sign and (o_.get("sm5") or {}).get("kind") != "mm":
                _f("x_mm_flip_kind")
                o_ = None                             # caption-gap M1-one-segment review fix: the flipped leg is an MM leg (mm_lowrisk / mm stage / OC / accum orders carry sm5 kind "mm"), not any setup
            if o_ is not None and rc_ is not None and rc_.get("pending") and not _SM7.loss_reentry_ok(ctx, sd, i, p, o_, rc_):
                _f("x_reentry_gate")
                o_ = None                             # X13b: no restored sweep / FVG after the stop (reentry_idea_gate: the three idea-intact conditions)
            if o_ is not None and r7_ is not None and r7_.get("pending") and not _SM7.reentry_ok(ctx, sd, i, p, o_, r7_):
                _f("x_reentry7_gate")
                o_ = None                             # caption-gap X14 / X13 re-entry kinds: a new array / the trail structure / the turtle-soup form / the reversal order
            if o_ is not None and smtb:
                o_["lv_tags"] = "|".join(x for x in (o_.get("lv_tags", ""), "smt_bias_agree" if sd.sign == smtb
                                                     else "smt_bias_against") if x)
            if o_ is not None:
                o_ = _NC.post_order(ctx, sd, i, p, session, o_, hist)    # T4 / T7 / T9 / Ep07.8 filters and tags
            if o_ is not None:
                why_ = _DW.order_ok(ctx, sd, o_, session, i, p)          # day_week_context per-order rules
                if why_ is not None:
                    _f(why_)
                    o_ = None
                    if why_ == "x_bh_fifty_fifty" and pending is not None and pending["session"] == session:
                        pending = None                # B17.1: 50/50 - the first side's armed order is cancelled too
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
                _BD.register_armed(ctx, p, session, sd.sign)
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
    if p.ndog_scalp and post_eve is not None and len(post_eve):
        trades += _SM4.ndog_scalp(ctx, post_eve, p, day, symbol, btag)       # caption-gap new-ndog-asian-scalp: the Asian-evening NDOG scalp (its own window, after the day's frame)
    if p.journal_timing and len(trades) > n_main:
        _DWC3.journal_extras(ctx, trades[n_main:], p)      # caption-gap OT-X16-time-to-move-journal: the Silver Bullet / Ma Deuce / NDOG rows
    if p.daily_loss_pct > 0 and len(trades) > n_main:
        trades = _ES3.extras_loss_gate(trades, n_main, ctx, p)      # caption-gap E11-funded-account-caps (review fix): the Ma Deuce / Silver Bullet / NDOG rows obey the day's loss limit too
    if _out is not None:
        _out["extras"] = list(trades[n_main:])
    if pos is not None:   # data ended early
        tr = pos["trade"]
        if not live:
            tr.exits.append((ctx.idx[-1], pos["side"].x(pos["side"].c[-1]), pos["left"], "eod"))
            _after_close(pos, trades, p, done, state, i=len(ctx.t) - 1, ctx=ctx)     # review fix: the risk state / day-loss see this close too
        else:
            trades.append(tr)
    if wl is not None and len(trades) > wl:                # X15 / D19: the week's budget in ENTRY-time order across all engines
        trades.sort(key=lambda t_: t_.entry_time)          # (after a position left open at the data end is in the list)
        del trades[wl:]
    if state["rs"] is not None and (p.ma_deuce or p.sb_model):
        _EN.replay_risk_state(state["rs"], ctx.risk_view["rs0"], trades, p)   # E10: carried state in time order
    if locks is not None:
        locks += [dict(lk, symbol=symbol, marked=len(lk["marked"])) for lk in all_locks + list(ctx.lock.values())]
    if trades:
        nt_ = _NC.day_tags(day, p)                         # news_calendar_times: the day's news tags on every trade
        for tr_ in trades:
            tr_.news_tags = nt_
        _DW.stamp(ctx, trades, p)                          # day_week_context: dw_tags and the X16 journal columns
    _SM2.objective_stamp(ctx, p, symbol, trades, objective)   # caption-gap D15 laggard_objective: this instrument's own draw met (engine level)
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


def _arm_add(pos, tr, px, i, p, eq, floor=None, g=None, pos_g=False, size=None, extra_room=0.0, dig_g=None):
    """#12: an add at `px` (side space) sized by the adds fraction, shrunk so the open risk
    (against the current stop; never negative) stays within the total cap (1.3%).
    floor      the array's bottom: add_hold cancels the add on a body close below it (E12b)
    g          the add's FVG: add_body_stop (Ep01.19) moves the stop under its bodies after the fill;
               pos_g remembers it for add_low_end (E12c)
    size       an explicit quantity (E12c: the smallest earlier add)
    extra_room extra open risk (fraction of equity) above the total cap (owner #7 htf_add_extra_risk_pct)
    dig_g      the zone whose repeat digs shrink the add (add_dig_mult; the entry zone for the retest add) - g is not reused (it also drives add_body_stop)
    E11 max_contracts_total caps the units; E1 add_order "market" fills at the open after a retest."""
    k = _nadds(pos, tr)
    base = pos.get("add_base") or pos.get("plan_shares") or tr.shares        # a ladder trade: the full planned size, not rung 0 (caption-gap E12-in-zone-larger-second: the zone ladder's first leg)
    dm_ = _ES3.dig_mult(pos_sd(pos), px, g if g is not None else dig_g, i, p, pos) if p.add_dig_mult < 1.0 else 1.0     # caption-gap E12-repeat-dig-smaller-add: an FVG price dug into twice
    q = _lots(base * p.adds[min(k, len(p.adds) - 1)] * pos.get("es2_add_mult", 1.0) * dm_, p.lot) if size is None else size
    at_risk = max(0.0, pos["basis"] - pos["stop"] * pos["n"])
    d = px - pos["stop"]
    if d <= 0:
        return
    if p.vi_ladder and pos.get("zone_top") is not None and px <= pos["zone_top"]:
        return                                         # caption-gap E12-631-vi-wickce-invalidation: adds only beyond the entry VI (the position stays net from it)
    if not _SM.add_pd_ok(pos, px, p):
        _f("x_add_not_in_pd")                          # M2.6 add_in_pd: every add path, not only add_ok
        return
    room = _total_cap(p, eq) + (extra_room + pos.get("es3_room", 0.0)) * eq - at_risk
    if p.htf_near_add_literal and p.htf_near_risk_pct > 0 and pos.get("es3_room") and size is None and not pos.get("no_adds"):
        q = _lots(p.htf_near_risk_pct * eq / d, p.lot)         # caption-gap E8-E9-5pct-near-htf (literal): this add risks htf_near_risk_pct itself; the room above still caps the total
        if d * q > room:
            q = _lots(max(room, 0.0) / d, p.lot)
        _ES2.hit("htf_near_add_literal")
    if d * q > room:
        q = _lots(max(room, 0.0) / d, p.lot)
    if pos.get("dl_room") is not None and d * q > pos["dl_room"]:
        q = _lots(max(pos["dl_room"], 0.0) / d, p.lot)        # caption-gap E11-funded-account-caps: the add's risk stays inside the day's loss limit
    lr_ = _ES3.lev_room_units(p, eq, pos["n"], px)
    if lr_ is not None and q > lr_:
        q = _lots(lr_, p.lot)                                 # caption-gap E8-leverage-cap-3x: first unit + adds <= max_lev x equity
    q = _EN.cap_add(q, pos["n"], p)
    if q >= p.lot and q >= 1:
        pos["add"] = dict(px=px, q=q, i=i, market=p.add_order == "market",
                          hold=floor if (p.add_hold and floor is not None) else None)
        if p.add_stop_under_array and floor is not None and floor - p.pad > pos["stop"] and px - (floor - p.pad) >= p.min_risk_pts * p.es_pt:
            pos["add"]["stop_to"] = float(floor - p.pad)   # caption-gap E12-067-citation-wrong: the stop under the add's array (never lowers; E7)
            _ES2.hit("add_stop_under_array")
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
    top = float(sd.o[k]) if p.ob_anchor == "last_open" else float(sd.o[j:k + 1].max())     # caption-gap A12-ob-anchor: the add's zone top
    if not _SM.add_ok(sd, pos, top, i, p, form=float(sd.c[j:k + 1].min())):           # setups_models add rules (M2 / Ep05.4); the add-cutoff test reads the OB's body bottom (review fix)
        return
    if sd.l[j:k + 1].min() >= pos["stop"] and sd.c[i] > top:
        pos["ob_add_used"].add(k)
        _arm_add(pos, tr, top, i, p, eq)


def _resist_live(ctx, sd, pos, i, p):
    """#7 htf_resist_live: recompute the cap at bar i's close and trim the remaining rungs
    (applies from bar i+1)."""
    now = ctx.idx[i] + pd.Timedelta(minutes=ctx.tf)
    src = tuple(CF_SRC[x] for x in p.htf_resist_src)
    cap_tfs = tuple(t_ for t_ in _TP.resist_cfg(p)[0] if t_ not in (pos.get("tp1") or {}).get("speed", ()))      # caption-gap N-opposing-fvg-speed-bump: a speed-bump timeframe is no live cap either
    if not cap_tfs:
        return
    r = ctx.conf.resistance(now, sd.x(sd.c[i]), sd.sign, cap_tfs, src)
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


def _lock_step(ctx, p, lock_t, i, t, bias_by_cut, done, spent, all_locks, pending, state=None):
    """#9 per bar: lock each session's draw at its lock time (bars closed by then only), then
    mark a lock delivered when this closed bar reached its target (before or after an entry):
    that session (and its SB window) is done for the day."""
    if not hasattr(ctx, "lock_hist"):
        ctx.lock_hist = {}                            # SB package: {key: [(effective bar, replaced lock)]}
    for s_, tl in lock_t.items():
        if s_ not in ctx.lock and t >= tl:
            row = (bias_by_cut or {}).get(tl)
            lk = mark_levels(ctx, row, tl, "PM" if s_ == "LH" else s_, p, spent)   # LH: a PM mark-up
            lk["session"] = s_
            lk = _NC.carry_lock(ctx, p, s_, lk)                  # T8 pm_carry_draw
            if p.lh_draw_freeze:
                lk = _SM3.lh_frozen(ctx, p, s_, lk)              # caption-gap M5-lasthour-draw-frozen-noon: the AM lock (else the noon mark-up) is the LH draw
            ctx.lock[s_] = lk
            if lk["side"] == 0 and p.draw_lock_neutral == "skip":
                done[s_] = True
    for s_, lk in list(ctx.lock.items()):
        if _BH1E.lock_on(p) or _BH2E.lock_on(p):       # caption-gap pass bias_htf#1/7: invalidation touch, 60m BISI hold, raid gap guard, 50/50 and low-in re-locks, the counter-trend reopen; bias_htf#2/7: the wick CE 60m cancel, the reversal after the target
            r_ = _BH1E.lock_bar(ctx, p, s_, lk, i, done, spent, state) if _BH1E.lock_on(p) else None
            if r_ is None and _BH2E.lock_on(p):
                r_ = _BH2E.lock_bar(ctx, p, s_, lk, i, done, spent, state)
            if r_ is not None:
                nl_, cancel_ = r_
                all_locks.append(dict(lk, failed=True))
                ctx.lock_hist.setdefault(s_, []).append((i + 1, lk))
                ctx.lock[s_] = lk = nl_
                _f("x_bh1_relock")
                if nl_["side"] == 0 and p.draw_lock_neutral == "skip":
                    done[s_] = True
                if cancel_ and pending is not None and ("LH" if pending.get("done_key") == "LH" else pending["session"]) == s_ and pending["side"].sign != nl_["side"]:
                    pending = None
                continue
        if not lk["side"] or lk["delivered"]:
            continue
        if lk["name"] == "org_far" and _org_break(ctx, p, i):
            # L7 (review fix): the ORG acted as a breakaway (no attempt by 09:30 + org_break_min) -
            # its far edge is no longer the draw: the lock as marked at its time without it
            nl = mark_levels(ctx, (bias_by_cut or {}).get(lk["t_lock"]), lk["t_lock"], "PM" if s_ == "LH" else s_, p,
                             spent, org_pref=False)
            nl["session"] = s_
            nl.update(org_break_i=i, traded=lk["traded"])   # (the lock report shows the replacement)
            ctx.lock_hist.setdefault(s_, []).append((i, lk))   # SB package: the replaced lock, for SB bars before i
            lk = nl
            ctx.lock[s_] = lk
            if lk["side"] == 0:
                if p.draw_lock_neutral == "skip":
                    done[s_] = True
                continue
        if p.dt_proj:                                  # caption-gap new-double-top-projection (cc04_014 ~11:53): the projection traded - the draw is the nearest sell-side pool
            nl = _TP3.dt_relock(ctx, p, lk, i, spent)
            if nl is not None:
                all_locks.append(dict(lk, failed=True))
                ctx.lock[s_] = lk = nl
                _f("x_dt_relock")
                if pending is not None and pending["side"].sign != nl["side"] and                         ("LH" if pending.get("done_key") == "LH" else pending["session"]) == s_:
                    pending = None
                continue
        if p.wide_or_draw:                             # caption-gap LLT3-wide-or-bias-end (cc10_010 ~6:15): the OR60 end in the bias direction is the locked draw from 10:30
            nl = _TP3.wide_or_relock(ctx, p, lk, i, s_)
            if nl is not None:
                all_locks.append(dict(lk, failed=True))
                ctx.lock[s_] = lk = nl
                _f("x_wide_or_lock")
                if pending is not None and pending["side"].sign != nl["side"] and \
                        ("LH" if pending.get("done_key") == "LH" else pending["session"]) == s_:
                    pending = None
                continue
        hit = ctx.h[i] >= lk["target"] if lk["side"] > 0 else ctx.l[i] <= lk["target"]
        if not hit and p.cond_draw:                   # L14e: the draw failed - switch once to the other side (the failed target spent)
            nl = _BD.cond_relock(ctx, p, lk, i, spent)
            if nl is not None:
                all_locks.append(dict(lk, failed=True))   # the failed draw stays in the lock report
                ctx.lock[s_] = lk = nl
                _f("x_cond_draw")
                if pending is not None and pending["side"].sign != nl["side"] and \
                        ("LH" if pending.get("done_key") == "LH" else pending["session"]) == s_:
                    pending = None
                continue
        if hit:
            lk.update(delivered=True, delivered_t=ctx.idx[i], delivered_i=i)
            spent.append(lk["target"])
            _f("x_draw_delivered")
            if pending is not None and ("LH" if pending.get("done_key") == "LH" else pending["session"]) == s_:
                pending = None
            if p.draw_relock and not (p.lh_draw_freeze and s_ == "LH"):      # test: lock the next draw from here (review fix: not for the frozen last-hour draw - delivered = the slot is done)
                all_locks.append(lk)
                nl = mark_levels(ctx, None, int(t + ctx.tf), "PM" if s_ == "LH" else s_, p, spent)
                nl["session"] = s_
                ctx.lock_hist.setdefault(s_, []).append((i + 1, lk))   # SB package: the delivered lock, for SB bars before i
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
    out = _sell_side0(ctx, sd, session, i, extra, p)
    if p is not None and p.session_pools_mode != "off":
        out = _TP2.sell_side_filter(out, ctx, sd, p)       # caption-gap L14-session-pools-only (067 ~00:27:37): rank / limit the swept pools to the session ranges
    return out


def _sell_side0(ctx: DayCtx, sd: Side, session: str, i: int | None = None,
                extra: bool = False, p: "Params | None" = None) -> dict[str, float]:
    keys = ("pdl1", "pdl2", "pdl3") if sd.sign > 0 else ("pdh1", "pdh2", "pdh3")
    out = {k: sd.x(ctx.pd[k]) for k in keys if k in ctx.pd}
    if session in ("PRE7", "PRE8", "PRE9", "NEWS", "LON"):
        m = {"PRE7": 420, "PRE8": 500, "LON": getattr(ctx, "lon_start", 120)}.get(session, 540)
        if m in ctx.pre_at:
            hi, lo = ctx.pre_at[m]
            out["overnight"] = sd.x(lo if sd.sign > 0 else hi)
        for name in ("london", "prev_pm") + (("prev_london",) if "prev_london" in ctx.sess else ()):      # caption-gap L1 prev_london_pool
            if name == "london" and session == "LON":
                continue                     # the London range is still being made (complete at 05:00)
            if name in ctx.sess:
                hi, lo, _ = ctx.sess[name]
                out[name] = sd.x(lo if sd.sign > 0 else hi)
        if (session == "NEWS" and ctx.news_hl is not None
                and (i is None or getattr(ctx, "news_made", 0) <= i - 1 or p is None or p.news_wait == "off")):
            out["news_range"] = sd.x(ctx.news_hl[1] if sd.sign > 0 else ctx.news_hl[0])
        if i is not None:
            for k, v in enumerate(_LD3.round_filter(_round_levels(ctx, sd, i, False), _LD3.confluence_refs(ctx, sd, i, p, False, out), p) if p is not None else _round_levels(ctx, sd, i, False)):
                out["round"] = v
        if p is not None and i is not None:
            _SM2.open_pools(ctx, sd, i, p, out)          # caption-gap B18-am-smt-window-points: the opens as reference points
        return out
    if p is not None:
        for name, on, hl in (("pwl", p.pool_prev_week, ctx.pw), ("pml_month", p.pool_prev_month or (p.pmh_contrarian and getattr(ctx, "curve_now", "") == "pmh"), ctx.pm_)):
            if on and hl is not None:
                out[name] = sd.x(hl[1] if sd.sign > 0 else hl[0])
        if p.pool_swings and i is not None:     # untaken short-term swing lows (side terms)
            for q in _LD.pool_piv(sd, True):
                if q.known <= i - 1 and q.i >= ctx.start - 1 and l_min_after(sd, q, i) > q.price:
                    out[f"swing_low{q.i}"] = q.price
    if i is not None:                           # #4: news dealing ranges once complete
        for R, d in getattr(ctx, "news_dr", {}).items():
            if d["made"] is not None and d["made"] <= i - 1:
                out["news_range" if R == 510 else f"news_range_{R}"] = sd.x(d["lo"] if sd.sign > 0 else d["hi"])
        for v in (_LD3.round_filter(_round_levels(ctx, sd, i, False), _LD3.confluence_refs(ctx, sd, i, p, False, out), p) if p is not None
                  else _round_levels(ctx, sd, i, False)):   # #13: the nearest untaken round handle (A2 round_pool_mode)
            out["round"] = v
    if session in ("AM", "LUNCH"):
        k = "pml" if sd.sign > 0 else "pmh"
        if k in ctx.pd:
            out["premarket"] = sd.x(ctx.pd[k])
        if session == "LUNCH" and getattr(ctx, "am_lunch_hl", None) is not None:   # T8: the AM range, complete before
            out["am_session"] = sd.x(ctx.am_lunch_hl[1] if sd.sign > 0 else ctx.am_lunch_hl[0])   # the lunch session
        if extra:
            for name in ("london", "prev_pm", "prev_london"):
                if name in ctx.sess:
                    hi, lo, _ = ctx.sess[name]
                    out[name] = sd.x(lo if sd.sign > 0 else hi)
        or_gate_ = p is None or i is None or _TP1.or_ok(ctx, p, sd, i)        # caption-gap T4-or-needs-bias-iof: the OR levels only with a bias and the iof agreeing
        if ctx.or_hl is not None and i is not None and ctx.t[i] >= ctx.or_end and not (p is not None and p.or_expire and ctx.t[i] >= p.or_expire) and or_gate_:
            out["opening_range"] = sd.x(ctx.or_hl[1] if sd.sign > 0 else ctx.or_hl[0])       # (caption-gap L3 or_expire: an AM reference until 11:00)
        o60 = getattr(ctx, "or60", None)           # M12.3 or60 turtle soup: the 09:30-10:30 range
        if o60 is not None and i is not None and ctx.t[i] >= 630 and p is not None and p.turtle_soup == "or60" and or_gate_:
            out["or60"] = sd.x(o60[1] if sd.sign > 0 else o60[0])
    elif ctx.am_hl:
        out["am_session"] = sd.x(ctx.am_hl[1] if sd.sign > 0 else ctx.am_hl[0])
        if (extra or (p is not None and p.pm_lunch_raid)) and "lunch" in ctx.sess and i is not None and ctx.t[i] >= ctx.sess["lunch"][2]:
            hi, lo, _ = ctx.sess["lunch"]
            out["lunch"] = sd.x(lo if sd.sign > 0 else hi)        # (caption-gap pm_lunch_raid: the lunch extreme is the PM raid pool whatever extra_pools says)
    if p is not None and i is not None and hasattr(ctx, "ipda"):
        _lv_sell_side(ctx, sd, session, i, p, out, extra)        # levels_detectors pools
    if p is not None and i is not None and (p.smt_entry or p.pm_judas_array):
        _SM.extra_pools(ctx, sd, session, i, p, out)             # setups_models M16.1 / M7.3
    if p is not None and i is not None:
        _SM2.open_pools(ctx, sd, i, p, out)                      # caption-gap B18-am-smt-window-points: the opens as reference points
        if p.pm_am_stops:
            _SM4.pools4(ctx, sd, i, p, session, out)             # caption-gap M7-pm-short-after-lunch-run-of-am-stops: the trailed AM stops
        if p.prev_reh_plan:
            _SM5.pools5(ctx, sd, i, p, session, out)             # caption-gap new-next-day-or-reh-short: the prior day's 15m relative equal highs as AM pools
    return out


FUNNEL = None   # set to a collections.Counter to count how setups are found and rejected


def _f(key):
    if FUNNEL is not None:
        FUNNEL[key] += 1


def _level_intact(ctx, l, i, k, v, session, tk: float = 0.0) -> bool:
    """A sell-side level (side space) not traded through between its creation and bar i-1
    (A2: through = at least tk below it; tk = 0 any print below)."""
    vr_ = (getattr(ctx, "state7", None) or {}).get("void_rearm")
    if vr_ and vr_.get("session") == session and k == vr_.get("swept"):
        _TP4.hit("void_rearm_offer")          # caption-gap new-sellstop-run-before-void-fill (cc04_010 ~8:07): after a stopped-out void_draw trade the SAME lows are offered again (once)
        return True
    a = _level_created(ctx, k, session)
    return k.startswith(("rel_eq", "round", "diag")) or i <= a or not _thru(l[a:i].min(), v, tk)


def _level_created(ctx, k: str, session: str) -> int:
    """The bar from which sell-side pool `k` exists (shared by _level_intact and _smt)."""
    at = lambda m: ctx.start + int(np.searchsorted(ctx.t[ctx.start:], m))
    cr_ = _LD3.created(ctx, k)
    if cr_ is not None:                    # caption-gap pass (levels_detectors #2/3): old_lo, engineered, session OR, float pools
        return cr_
    cr_ = _SM2.created(ctx, k)
    if cr_ is not None:                    # caption-gap B18-am-smt-window-points: the 08:30 / 09:30 open points
        return cr_
    cr_ = _SM4.created(ctx, k)
    if cr_ is not None:                    # caption-gap M7-pm-short-after-lunch-run-of-am-stops: the PM pool am_last_high exists from 12:00
        return cr_
    cr_ = _SM5.created(ctx, k)
    if cr_ is not None:                    # caption-gap new-next-day-or-reh-short: the prior day's REH pools exist from 09:30
        return cr_
    if getattr(ctx, "rth_spent", False) and k in ("prev_pm", "prev_am"):     # L1 rth_pool_spent: only RTH prints (>= 09:30) spend them
        return at(570)
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
    elif k in ("consol_l", "consol_h"):
        a = int(getattr(getattr(ctx, "chop", None), "rel_i", None) or 0) + 1       # caption-gap N8: from the bar after the release
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
    if o_ is None and p.hs_fade and sd.sweep is None:
        o_ = _LD4.hs_order(ctx, sd, i, p, session, risk_mult)      # caption-gap new-hs-fade (levels_detectors #3/3)
    if o_ is None and p.trendline_trap and p.tl_trap_entries and sd.sweep is None:
        o_ = _LD4.tl_trap_order(ctx, sd, i, p, session, risk_mult)  # caption-gap new-trendline-trap: the OB / breaker entries at L23 (no sweep needed)
    if o_ is None and p.flip_retest_entry and sd.sweep is None:
        o_ = _LD4.flip_order(ctx, sd, i, p, session, risk_mult)     # caption-gap L2-sr-needs-fvg: the flip retest at the FVG CE
    if o_ is None and (p.pm_ep01 or p.moc_run or p.ir_entries or p.cc_swings in ("failure", "both")):
        o_ = _SM.extra_setups(ctx, sd, i, p, session, risk_mult)   # setups_models non-sweep setups
    if o_ is None and (p.breaker_day_life or p.breaker_retests > 1) and sd.sweep is None:
        o_ = _SM2.breaker_retest_order(ctx, sd, i, p, session, risk_mult)    # caption-gap A13-breaker-lifetime: repeat retests of the day's breakers
    if o_ is None and p.breaker_range_trigger and sd.sweep is None:
        o_ = _SM2.breaker_trigger_order(ctx, sd, i, p, session, risk_mult)   # caption-gap A21-pre-trigger-dealing-range: the MSS trigger inside the breaker's dealing range
    if o_ is None and p.mitigation_entry and sd.sweep is None:
        o_ = _SM2.mit_order(ctx, sd, i, p, session, risk_mult)               # caption-gap A15-mitigation-block-entry: ranks below the breakers
    if o_ is None and sd.sweep is None and (p.nwog_sr_entries or p.gap_edge_entry or p.gap_quarter_retrace or "bpr_ce" in p.entry_arrays or p.or_rb or p.consol_fade):
        o_ = _SM2.extra2(ctx, sd, i, p, session, risk_mult)                  # caption-gap setups_models #2/7: the gap / BPR CE / OR block / consolidation-fade setups
    if o_ is None and sd.sweep is None and _SM3.any_extra3(p):
        o_ = _SM3.extra3(ctx, sd, i, p, session, risk_mult)                  # caption-gap setups_models #3/7: vacuum block, recapitalized OB, CE-fail, Monday projection
    if o_ is None and sd.sweep is None and _SM4.any_extra4(p):
        o_ = _SM4.extra4(ctx, sd, i, p, session, risk_mult)                  # caption-gap setups_models #4/7: dagger, last-hour old low / array short, PM old-high FVG, after-draw retracement, top-of-discount short, sick-sister entries
    if o_ is None and p.turtle_soup == "prev_pm" and sd.sweep is None:
        o_ = _SM5.prev_pm_limit(ctx, sd, i, p, session, risk_mult)           # caption-gap M12-turtle-soup-prev-pm-low: the resting limit under the previous PM range's low
    if o_ is None and _SM5.any_extra5(p):
        o_ = _SM5.extra5(ctx, sd, i, p, session, risk_mult)                  # caption-gap setups_models #5/7: 15m PO3, second dip, overshoot, unicorn, IFVG open, MM stages, reclaimed ladder, ...
    if o_ is None and sd.sweep is None and _SM6.any_extra6(p) and not getattr(ctx, "curve_now", ""):
        o_ = _SM6.extra6(ctx, sd, i, p, session, risk_mult)                  # caption-gap setups_models #6/7: consolidation EQ, void trades, failed-turtle continuation, rejection block, range fades, vacuum block
    if o_ is None and sd.sweep is None and _SM7.any_extra7(p):
        o_ = _SM7.extra7(ctx, sd, i, p, session, risk_mult)                  # caption-gap setups_models #7/7: or_ref, am_array_open, lh_ob_pullback, the 09:50 continuation, missed_5m
    if (p.reentry_stop == "ob_low" or p.reentry_ob_stop == "full" or p.reentry_mode == "cc_ob") and (getattr(ctx, "re_ctx_now", None) or {}).get("pending"):
        o2_ = _ES3.ob_low_order(ctx, sd, i, p, session, risk_mult)             # caption-gap E6-attempt-based-stop (cc02_005 ~00:01:47): the re-entry is the first new OB after the stop-out
        if o2_ is not None:
            o_ = o2_
    if o_ is None and _ME3.any_re_orders(ctx, p):
        o_ = _ME3.re_order(ctx, sd, i, p, session, risk_mult)                  # caption-gap M12-ote-failure-turtle-soup: the turtle-soup buy at the low the stopped OTE entry ran
    if o_ is None and _SM7.any_re_orders(ctx, p):
        o_ = _SM7.re_order(ctx, sd, i, p, session, risk_mult)                # caption-gap X13 / X14 (setups_models #7/7): the trail-win IFVG CE / breaker retest, the reversal inversion / at-stop orders, the sibi return
    if o_ is not None and p.entry_discipline != "any" and p.entry_discipline_only and not _SM6.discipline_ok(o_, p):
        _f("x_discipline")                                                   # caption-gap M12-setup-selection-order (review fix): the preset leaves ONLY the chosen discipline
        return None
    if o_ is not None and p.ts_sessions and session not in p.ts_sessions and _SM7.is_ts_kind(o_):
        _f("x_ts_session")                                                   # caption-gap T9-pm-reversal-turtle-soup-am-high: the turtle soup runs only in ts_sessions
        _SM7.hit("ts_session_drop")
        return None
    if o_ is not None and p.pairing != "all" and not _SM7.pairing_ok(ctx, sd, i, p, o_):
        _f("x_pairing")                                                      # caption-gap OT-one-state-tool-pairing: the session state and the entry kind must be the chosen pairing
        return None
    return o_


def _mss_ref(ctx, sd, sw, i, p):
    """A1 MSS reference (010 ~41:31: the parent swing): the last mss_ref-tier swing high before the
    sweep extreme known by bar i; mss_ref_fallback "lower" tries the lower tiers, then (like
    "highest") the highest high of the 3*pivot_n bars before the extreme (the old rule); "none" =
    no reference. Returns (ref_i, ref, real_pivot) or None."""
    if p.mss_ref in ("parent", "origin", "origin_max") or p.mss_ref_sibi or p.mss_ref_tf or p.mss_ref_raid or p.micro_regime:
        r = _SM.mss_ref(ctx, sd, sw, i, p)      # setups_models A19 / Ep08.4 / Ep07.6 / Ep08.16 (+ #2/7: A19 mss_ref_raid, N micro_regime)
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
    bz = L.breaker_zone(sd.o, h, l, c, a0, to, i, "bull", p.breaker_zone, p.breaker_mt_mode,
                        p.breaker_candle, p.breaker_body_swing)       # caption-gap A12 / A13 pick + body swing
    if p.breaker_tf and bz is not None:
        z_ = _SM5.breaker_zone_tf(ctx, sd, a0, to, i, p)          # caption-gap M4-1m-last-upclose-finetune: the zone of the m-minute leg (e.g. 5m)
        if z_ is not None:
            bz = z_
    if bz is not None and p.breaker_mt_respect and (c[sw["broke"] + 1:i + 1] < bz.mt).any():
        _f("x_breaker_mt_lost")
        return None                    # #6 (a): a body close below the breaker MT - breaker lost
    if bz is not None and p.breaker_by_close and not _SM2.breaker_by_close_ok(ctx, sd, sw, ref_i, i):
        _f("x_breaker_wick_only")
        return None                    # caption-gap A13-breaker-close-vs-wick: a wick-only break is an MSS without a breaker
    if bz is not None and (p.breaker_needs_disp or p.breaker_break_ref != "wick") and not _SM2.breaker_confirmed(ctx, sd, sw, bz, i, p):
        _f("x_breaker_unconfirmed")
        return None                    # caption-gap A13-breaker-needs-rebalance-and-fvg: no fast repricing / the candle's body high not left
    if bz is not None and (p.breaker_day_life or p.breaker_range_trigger or p.breaker_retests > 1):
        _SM2.breaker_register(ctx, sd, sw, bz, i, p)       # caption-gap A13-breaker-lifetime
    return bz


def _breaker_order(ctx, sd, sw, bz, i, p, session, risk_mult):
    """A13.4 / Ep01.6 / Ep05.5 breaker entry (breaker_entry): a limit at the breaker top, the stop
    beyond the sweep extreme, cancelled / exited on a body close below the breaker MT (#6)."""
    sw["bz_sent"] = True
    entry = bz.top
    stop = sw["ext"] - p.pad
    rf_ = _ES1.breaker_refine(sd, sw, bz, i, p) if p.breaker_refine else None     # caption-gap A13-breaker-fvg-refinement (031 ~1:02:29; 032 ~41:26): the FVG / VI inside the zone is the entry
    if rf_ is not None and rf_[0] < sd.c[i]:
        entry = rf_[0]
    tags = dict(unicorn=False, fvg_bottom=bz.bottom, fvg_ce=bz.mt, entry_kind="breaker", mitigation=False,
                propulsion=False, unicorn_side="",
                bz_top=float(max(sd.x(bz.top), sd.x(bz.bottom))), bz_bottom=float(min(sd.x(bz.top), sd.x(bz.bottom))),
                bz_mt=bz.mt if p.breaker_mt_respect else None)
    if p.breaker_range_hold:                      # caption-gap A21-pre-trigger-dealing-range (048 ~1:20:40): time does not invalidate - the order rests until a trade goes deeper than the breaker
        tags.update(no_expire=True, cancel_low=float(bz.bottom))
        _SM2.hit("breaker_hold")
    if rf_ is not None and rf_[0] < sd.c[i]:
        tags.update(cancel_close=float(rf_[1]), lv_tags=["breaker_refined"], lvx={"breaker_refine": (float(rf_[1]), False)})      # a body close under the refinement's low cancels the idea (and exits a filled one)
    if p.breaker_pref == "last_1m":               # caption-gap M4-1m-last-upclose-finetune (070 ~00:55:41): the last up-close base bar inside the zone, a limit at its MT (1 tick through)
        r5_ = _SM5.breaker_last_1m(ctx, sd, sw, bz, i, p)
        if r5_ is not None:
            entry = r5_[0]
            tags.update(through=float(p.tick), lv_tags=["breaker_last_1m"])
    if p.breaker_iofed and entry + p.tick < sd.c[i]:
        entry += p.tick                           # caption-gap E2-iofed-breaker-exact-match (043 ~00:16:21): the limit 1 tick inside (market side of) the breaker extreme - an exact match fills under E3
        _ES2.hit("breaker_iofed")
    if p.bz_higher_array or p.in_zone_ladder:
        stop = _ES2.breaker_tail(ctx, sd, i, p, bz, entry, stop, tags)    # caption-gap A13-breaker-close-beyond-higher-array (081 ~00:14:11) / E12-in-zone-larger-second (103 ~00:34:22): shared by every breaker path
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
    wins = tuple(p.smt_windows) + (((p.smt_win_a, p.smt_win_b),) if p.smt_pre else ())      # (caption-gap B18-am-smt-window-points: the bounds are Params)
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
    if p.range_lock and _SM2.range_locked(sd, i):
        return None                  # caption-gap A12-range-internal-ignore: a candle strictly inside the armed order's dealing range arms nothing
    tol = p.eq_tol_pts * p.es_pt
    tk = _tick(p)
    lv = _sell_side(ctx, sd, session, i, p.extra_pools or p.profile_consol_pm or p.profile_consol, p)      # (caption-gap DS2-consolidation-profiles: the PM lunch pool)
    for k, eq in enumerate(_eq_levels(sd, i - 1, tol, lows=True, p=p)):
        lv[f"rel_eq_lows{k}"] = eq
    if p.reh_merge_pts > 0:
        lv = _TP1.merged_sweep(lv, p, sd)         # caption-gap A3-reh-under-older-high: sweeping the REL alone does not book the merged pool
    sw = sd.sweep
    if sw is not None and sw["session"] != session:
        sw = sd.sweep = None
    intact = lambda k, v: _level_intact(ctx, l, i, k, v, session, tk)
    lo_i = min(sd.o[i], c[i]) if p.sweep_body else l[i]       # A4 sweep_body: a BODY must trade through
    hit = [(k, v) for k, v in lv.items() if _thru(lo_i, v, tk) and intact(k, v)]
    releq = ("rel_eq", "eng") if p.engineered_pools else ("rel_eq",)     # caption-gap A3 (review fix #5): engineered pools count as rel-eq pools in the sweep pick
    if getattr(ctx, "curve_now", "") == "pmh":   # caption-gap M12-contrarian-pmh: the counter-bias side raids the previous month's extreme only
        hit = [kv for kv in hit if kv[0] == "pml_month"]
    if p.eq_pref == "require":                   # Ep06.7: only relative equal lows are liquidity
        hit = [kv for kv in hit if kv[0].startswith(releq)]
    if hit and (p.eq_hunt == "prefer" or p.ts_age_rank == "prefer"):
        hit = _SM3.prefer_hits(ctx, sd, i, p, hit)         # caption-gap new-eq-stop-hunt-entry / M4-swept-low-age: the preferred sweeps win the pick
    if (sw is None or (sw.get("key") == "htf_array" and sw["broke"] is None)) and hit and not _LD4.td_masked(ctx, p, i):     # (caption-gap new-time-distortion: a run of a pool in a masked bar infers no direction; M1M2 premise: a pool run replaces an array pseudo-sweep that has not broken yet)
        eqh = [kv for kv in hit if kv[0].startswith(releq)]
        if p.eq_pref == "rank" and eqh:          # Ep06.7: rel-eq pools win (best-ranked with eq_rank)
            k, v = eqh[0] if p.eq_rank else min(eqh, key=lambda kv: (kv[1], -_LD3.eng_score(ctx, kv[0])))
        else:
            k, v = min(hit, key=lambda kv: kv[1])
        if p.trendline_trap and any(kv[0] == "tl23" for kv in hit):      # caption-gap new-trendline-trap: the low between H2 and H3 is the priority pool
            k, v = next(kv for kv in hit if kv[0] == "tl23")
        sw = sd.sweep = dict(session=session, name=("rel_eq_lows" if sd.sign > 0 else "rel_eq_highs") if k.startswith("rel_eq") else k,
                             level=v, key=k, ext=l[i], ext_i=i, broke=None, sweep_i=i)
        sd.__dict__["_sweep_seen6"] = i                  # caption-gap A10-void-retrace-trades (review fix): the bar of the last pool sweep ("no pool swept in the last N bars")
        if p.nwog_edge_ce and str(k).startswith("gap_"):
            _SM2.hit("nwog_edge_sweep")                 # caption-gap new-nwog-edge-to-ce-cookie-cutter: a sweep of an NWOG far edge
        sw["smt"] = _smt(ctx, sd, i, k, v, session, pctx, psides, ppos, p)
        sw["smt2"] = _smt(ctx, sd, i, k, v, session, *ctx.partner2, p) if getattr(ctx, "partner2", None) else None
        if p.smt_with_bias:
            _SM2.smt_bias_gate(ctx, sd, sw, p)          # caption-gap B18-smt-only-with-bias: against the bias the non-confirming index is the laggard
        _f("1_sweep")
        if _SM3.any_sweep_switch(p) or p.eq_hunt != "off" or p.ts_age_rank != "off":
            if _SM3.sweep_init(ctx, sd, sw, i, p, session) == "drop":      # caption-gap setups_models #3/7: A23 wick CE, M3 shallow run, eq_hunt / age tags
                sd.sweep = None
                return None
    if sw is None and p.allow_htf_array_premise and not hit and not _LD4.td_masked(ctx, p, i):
        sw = sd.sweep = _SM3.premise_sweep(ctx, sd, i, p, session)      # caption-gap M1M2-htf-array-replaces-sweep: an HTF array reached with the bodies holding is the premise
        if sw is not None:
            _f("1_sweep")
    if sw is None:
        return None
    if _SM5.need_note(p):
        _SM5.note_sweep(sd, sw)         # caption-gap setups_models #5/7: the MM model / reclaimed ladder / three-drives fallback outlive the sweep a first order consumed
    if l[i] < sw["ext"]:
        sw.update(ext=l[i], ext_i=i, broke=None, ob=None, ob_sent=False, ob_frozen=False, ts_sent=False,
                  ts_ok=False, follow_i=None, wce_sent=False, cisd_sent=False, leg2_from=None, broke2=None,
                  on_side=False, f1=None, reaper_dead=False, ob_void=False, adv_pre_sent=False, smt_sent=False)
    if _SM3.any_sweep_switch(p):
        r3_ = _SM3.sweep_step(ctx, sd, sw, i, p)       # caption-gap setups_models #3/7: wick CE reached, shallow-run wait, linger, array test
        if r3_ == "drop":
            sd.sweep = None
            return None
        if r3_ == "wait":
            return None
    if p.ts_gate_mss and sw["broke"] is None:    # M12.5: the depth/back test gates the MSS / OB model
        if not sw.get("ts_ok"):
            sw["ts_ok"] = L.turtle_soup(l, c, sw["level"], sw["ext_i"], i, p.ts_max_pts * p.es_pt, p.ts_back_bars)
        if not sw["ts_ok"]:
            if sw["level"] - sw["ext"] > p.ts_max_pts * p.es_pt or i - sw["ext_i"] >= p.ts_back_bars:
                if not p.two_chance:             # caption-gap M4-two-chance-aggressive-vs-mss-retest: a failed / missed soup keeps the sweep alive for the MSS retest
                    sd.sweep = None              # too deep, or no close back above in time
                    _f("x_ts_gate")
                    return None
                _SM6.hit("two_chance_keep")      # chance 2 (review fix): the missed soup no longer returns here - the MSS / cc_swings breaking-point order below proceeds
            else:
                return None                      # the soup window is still open
    # reference: the swing high that led into the sweep extreme (A1 tiers: mss_ref)
    rr = _LD4.td_ref(ctx, sd, sw, i, p, _mss_ref(ctx, sd, sw, i, p))      # (caption-gap time_distortion: a swing formed in a masked bar is no reference)
    if rr is None:
        return None
    ref_i, ref, real_ref = rr
    sw["ref_i"] = ref_i                    # caption-gap BH-compressed-higher-highs: the MSS reference swing (sm2.compressed_gate)
    sw["ref_px"] = float(ref)              # caption-gap A21-post-cisd-range-retrace: the swing high the decline into the sweep began from
    if p.missed_5m:
        _SM7.note_sweep(ctx, sd, sw, ref, i)                   # caption-gap E5-missed-entry-5m-retrace: the sweep and its MSS reference, for a later 5m retrace order
    wick_mss = p.mss_mode == "wick" or (p.rb_pools and _LD4.is_rb_key(sw.get("key")))   # caption-gap A17: a wick pierce is enough after a rejection-block sweep
    if p.mss_cisd:                     # the open of the down-close series into the low
        blk = L.order_block_blend(sd.o, h, l, c, sw["ext_i"] - 5, sw["ext_i"], "bull",
                                  outside=_LD4.disp_fvg_zone(sd, sw, i) if p.ob_outside_fvg else None)
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
            raw = i > sw["ext_i"] and (h[i] if wick_mss else c[i]) > ref
            brk = raw
            if brk and p.displacement_mult:  # M1.2 option: the breaking candle must displace
                body = abs(c[i] - sd.o[i])
                prev = np.abs(c[max(0, i - 10):i] - sd.o[max(0, i - 10):i])
                brk = len(prev) == 0 or body >= p.displacement_mult * float(prev.mean())
                if not brk and p.imm_rebalance_disp == "or" and i > sw["ext_i"] and \
                        (h[i] if wick_mss else c[i]) > ref and _ir_in_leg(sd, sw, i, p):
                    brk = True               # A7: an immediate rebalance is displacement too
            if brk and p.imm_rebalance_disp == "require" and not _ir_in_leg(sd, sw, i, p):
                brk = False                  # A7 switch: the shift must carry an immediate rebalance
                _f("x_no_imm_rebalance")
            if brk:                          # setups_models A20 / M0.4 / Ep07.6 / A19.2 / Ep01.22
                brk = _SM.break_ok(ctx, sd, sw, i, p, ref, lv, tol, tk)
            if brk and p.mss_requires_htf_agreement:      # caption-gap A19-break-against-htf-stop-run: a break against the HTF flow is a stop run, not an MSS
                brk = not _SM2.mss_htf_reject(ctx, sd, sw, i, p, session, ref_i, ref)
                if not brk:
                    _f("x_mss_htf")
            if raw and not brk:
                gate_fail = True
            if brk and _LD4.td_masked(ctx, p, i):      # caption-gap new-time-distortion: a break printed in a masked bar is no MSS
                brk = False
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
    gaps = _LD4.td_gaps(ctx, sd, gaps, p)  # caption-gap new-time-distortion: gaps formed in a masked bar are no triggers
    if sw.get("ev_g") is not None:        # E5 evolve_fvg / wait_structural: only a NEWER gap re-arms
        gaps = [g for g in gaps if g.i > sw["ev_g"]]
    coarse_ids = set()                 # caption-gap A5-mtf-gap-refinement: the entry zones built from coarser bars (the 5m path, the HTF entry arrays, the leg / scan timeframes)
    if p.entry_tf != "1m" and ctx.tf < p.setup_minutes:
        z5 = sd.zones_tf(ctx.idx, ctx.tf, p.setup_minutes)
        if p.entry_tf == "5m":       # the 5m gap / block the 1m shift points at (formed after
            gaps = [z for z in z5 if z.i <= i and z.mt != z.mt   # the sweep: FVGs ...
                    and z.src + p.setup_minutes // ctx.tf > sw["ext_i"]]
            if not gaps:             # ... else the 5m order block at the low
                gaps = [z for z in z5 if z.i <= i and z.mt == z.mt and z.bottom <= sw["ext"] + 1e-9
                        and z.top > sw["ext"] and z.i >= sw["ext_i"]]
            coarse_ids |= {id(z) for z in gaps}
        else:                        # nested: 1m FVG inside a live 5m FVG or 5m order block
            live5 = [z for z in z5 if z.i <= i and c[z.i + 1:i + 1].min(initial=np.inf) >= z.bottom]
            gaps = [g for g in gaps if any(g.overlaps(z) for z in live5)]
    if p.entry_fvg_min_tf > ctx.tf:    # caption-gap B5-execution-tf-15m-min (cc12_004 ~5:00): only the FVGs of the m-minute bars arm entries
        mg_ = _ES2.min_tf_gaps(ctx, sd, sw, i, p)
        if mg_ is not None:
            gaps = [z for z in mg_ if sw.get("ev_g") is None or z.i > sw["ev_g"]]
            coarse_ids |= {id(z) for z in gaps}
    if p.ifvg_entries:                 # bearish gaps inverted by the move up from the sweep
        ifz_ = sd.ifvgs() if not p.ifvg_tf else _SM4.ifvg_tf_zones(ctx, sd, sw, i, p)       # (caption-gap A8-ifvg-5m-to-1m-handoff: the 5m SIBIs as the reference gaps)
        gaps = sorted(gaps + [z for z in ifz_ if sw["ext_i"] < z.i <= i], key=lambda z: z.i)
    imp = []
    if p.implied_fvg:                  # setups_models A24.1: implied FVGs of the leg are entry gaps too
        imp = [z for z in sd.implied() if z.i <= i and z.i - 2 >= sw["ext_i"]]
        gaps = sorted(gaps + imp, key=lambda z: z.i)
    # Ep01.5 / Ep02.9 breakaway gap: the first FVG formed at / after the structure break
    ba = _LD.breakaway_gap(ctx, sd, sw, i, p)          # caption-gap A6 breakaway_def (first_after_mss = the line above, as before)
    if p.breakaway_reentry and sw.get("broke") is not None:
        o7 = _SM7.breakaway_order(ctx, sd, sw, ba if ba is not None else _LD.breakaway_gap(ctx, sd, sw, i, p), i, p, session, risk_mult)
        if o7 is not None:
            return o7                            # caption-gap E6-breakaway-gap-stop: the retrace into the breakaway gap after two MSSs, stop = the retrace bar's extreme + 1 tick
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
    if p.ifvg_entries and p.ifvg_symmetry_skip and _SM4.symmetric(ctx, sd, i, p):    # caption-gap A8-symmetry-skip-ifvg-confirmation: ES and NQ agree - the opposing FVG is bought inside directly
        sz_ = [z for z in _SM4.sym_zones(ctx, sd, sw, i, p) if sw.get("ev_g") is None or z.i > sw["ev_g"]]
        if sz_:
            _SM2.hit("ifvg_symmetry")
            gaps = sorted(gaps + sz_, key=lambda z: z.i)
    if p.ifvg_entries and p.ifvg_061:
        o61 = _SM.ifvg_061(ctx, sd, sw, i, p, session, risk_mult)
        if o61 is not None:
            sd.sweep = None
            return o61
        ifv = {id(z) for z in sd.ifvgs()}
        gaps = [g for g in gaps if id(g) not in ifv]
    xz = []                            # Ep07.2 vi_entries / L14b void: more entry zones (not IFVGs)
    if p.vi_entries or "void" in p.irl_entries:
        xz = [z for z in _LD4.td_gaps(ctx, sd, _EN.extra_entry_zones(sd, sw, i, p), p) if sw.get("ev_g") is None or z.i > sw["ev_g"]]
        gaps = sorted(gaps + xz, key=lambda z: z.i)
    if p.irl_entries and "fvg" not in p.irl_entries:
        gaps = [g for g in gaps if any(g is z for z in xz)]      # L14b: the FVG is not an allowed IRL entry
    ldz = []                           # caption-gap pass: A5 reclaimed FVGs, B5 HTF fixed zones, A8 inverted arrays (entry zones, not IFVGs)
    if p.fvg_reclaim:
        ldz += _LD.reclaimed_zones(ctx, sd, sw, i, p)
    htf_keys = set()
    if p.htf_entry_arrays:
        hz_ = _LD.htf_entry_zones(ctx, sd, sw, i, p)
        htf_keys = {(round(float(z.top), 9), round(float(z.bottom), 9), z.i) for z in hz_}      # caption-gap A4-ltf-body-qualification
        coarse_ids |= {id(z) for z in hz_}
        ldz += hz_
    if p.inversions:
        ldz += _LD.inv_entry_zones(ctx, sd, sw, i, p)
    if p.vi_flip_entries:
        ldz += _LD.vi_flip_entry_zones(ctx, sd, sw, i, p)
    if p.or_fvg_entries:                  # caption-gap L3-or-refs-expire-1100: the opening range's FVGs are entry arrays for setups armed 10:00-11:00
        ldz += _LD4.or_fvg_zones(ctx, sd, sw, i, p)
    if ldz:
        ldz = [z for z in _LD4.td_gaps(ctx, sd, ldz, p) if sw.get("ev_g") is None or z.i > sw["ev_g"]]
        xz = list(xz) + ldz
        gaps = sorted(gaps + ldz, key=lambda z: z.i)
    leg_tf_z = []
    if p.leg_tfs:                      # caption-gap B5-multi-tf-fvg-scan: no 1m gap at / under the leg EQ - the 5 / 4 / 3 / 2 minute bars of the leg
        gaps, leg_tf_z = _SM4.leg_tf_gaps(ctx, sd, sw, gaps, i, p)
        xz = list(xz) + leg_tf_z
        coarse_ids |= {id(z) for z in leg_tf_z}
    if any(int(m_) > ctx.tf for m_ in p.scan_tfs):      # caption-gap new-multi-tf-scan (070 ~30:37; 072 ~11:09): the FVGs of the 2m..5m / 2h bars join the entry gaps
        sz_ = [z for z in _LD4.td_gaps(ctx, sd, _ES1.scan_gaps(ctx, sd, sw, i, p), p) if sw.get("ev_g") is None or z.i > sw["ev_g"]]
        if sz_:
            gaps = sorted(gaps + sz_, key=lambda z: z.i)
            xz = list(xz) + sz_
            coarse_ids |= {id(z) for z in sz_}
    nn = p.news_no_unicorn and bool(events(ctx.day) & {"jobs", "cpi", "fomc"})   # N6
    bz = None
    if (p.breaker_entry != "off" or p.breaker_by_close) and not nn:   # A13.4: the breaker is needed before the no-FVG return
        bz = _breaker(ctx, sd, sw, ref_i, real_ref, i, p)
        if (p.breaker_entry == "prefer" or p.breaker_by_close) and bz is not None and not sw.get("bz_sent"):    # (A13-breaker-close-vs-wick: a body-close breaker is taken first)
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
                if p.mss_rearm_lower_high:
                    _SM2.hit("mss_rearm")
                else:
                    sd.sweep = None
            return None
        wait = p.fvg_wait * (p.setup_minutes // ctx.tf if p.entry_tf == "5m" and ctx.tf < p.setup_minutes else 1)
        if i - _fvg_wait_from(sw) >= wait:
            sd.sweep = None
            _f("x_no_fvg_after_mss")
            if p.entry_arrays or p.reclaimed_ob or p.prop_fail_flip or "ob" in p.irl_entries or p.org_entry_array or p.wick_ce_mode == "retrace" or p.ote == "ob62":   # setups_models M0.5 (+ the ote "ob62" body stall): any PD array (caption-gap M11-wick-ce-fade-short: the retrace variant's wick CE)
                sw["_nofvg"] = True
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
    imp_eq, m2_live = None, False
    if p.implied_range_gate:           # caption-gap M2-implied-range-eq-gate: H is valid only after price traded from premium into discount; then only the gaps at / under the implied EQ
        imp_eq, gaps = _SM4.implied_gate(ctx, sd, sw, gaps, i, p, session)
        if imp_eq == "dead":
            sd.sweep = None
            _f("x_implied_h_traded")
            return None
        if imp_eq == "wait" or (imp_eq is not None and not gaps):
            _f("x_implied_wait")
            return None
    if p.m2_live_eq and p.fvg_pick == "2022":     # caption-gap M2-leg-eq-after-low-prints: the leg EQ moves with every new extreme - the candidates are re-filtered on each bar
        gaps = _SM4.m2_discount_gaps(sd, sw, gaps, i)
        if not gaps:
            if i - _fvg_wait_from(sw) >= p.fvg_wait * (p.setup_minutes // ctx.tf if p.entry_tf == "5m" and ctx.tf < p.setup_minutes else 1):
                sd.sweep = None
                _f("x_m2_eq")
            return None
        m2_live = True
    if not _EN.engage_ok(ctx, i, p):    # Ep08.17: the sweep waits (is not consumed) until the range has formed
        _f("x_engage_range")
        return None
    keep_sw = p.evolve_fvg or p.wait_structural or p.mss_rearm_lower_high      # caption-gap A19-second-mss-no-new-low (069 ~14:41): the side stays armed while the retrace does not pierce the sweep extreme
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
    gaps = [g for g in gaps if _LD.gap_open(sd, g, i, ctx, p)]     # (single_bar_fvg_strict: a trade below the low kills a caffeine-bar gap)
    if p.fvg_skip_above_pool:          # A5 (060 ~1:10:30): not a gap sitting right above a pool
        pools = [v for k, v in lv.items() if _level_intact(ctx, l, i + 1, k, v, session, tk)]
        gp = p.fvg_pool_gap_pts * p.es_pt
        gaps = [g for g in gaps if not any(0 <= g.bottom - v <= gp for v in pools)]
    if p.fvg_skip_below_pool_short:    # caption-gap A5-skip-fvg-near-stop-pool (060 ~1:11:00): a gap right under an untaken short-term extreme that lies between it and the protective extreme
        gaps = [g for g in gaps if not _ES1.near_stop_pool(sd, sw, g, i, p)]
    if p.fvg_state_filter:             # A5 state (open / repriced / rebalanced)
        held_ = _LD4.td_held(ctx, sd, gaps, i, p)       # caption-gap new-time-distortion (a): wicks outside, bodies inside = still valid, whatever its state
        gaps = [g for g in gaps if _fvg_state(sd, g, i) in p.fvg_state_filter or g in held_]
    if gaps and p.max_retrace:
        gaps = _SM5.depth_filter(sd, sw, gaps, i, p)      # caption-gap M13-max-depth-79: no entry FVG deeper than the cap into the displacement leg
        if not gaps:
            _f("x_max_retrace")
            return None
    if not gaps:
        _f("x_fvg_closed_through")
        return None
    fresh = [g for g in gaps if l[g.i + 1:i + 1].min(initial=np.inf) > g.top - p.mohawk       # A4 mohawk poke ok
             or (p.htf_body_qual and (round(float(g.top), 9), round(float(g.bottom), 9), g.i) in htf_keys and _SM2.body_qualified(ctx, sd, g, i, p))]   # caption-gap A4-ltf-body-qualification: wicks pierce, 15m / 5m bodies hold
    if not fresh:
        if p.evolve_fvg and rearm:
            return None                   # E5: only a newer UNTOUCHED gap replaces the order
        fresh = gaps
    uni_ok = p.unicorn_sides == "both" or p.unicorn_sides == ("long" if sd.sign > 0 else "short")
    uni = [g for g in fresh if bz is not None and g.overlaps(bz)] if uni_ok else []
    if p.unicorn_preopen and uni_ok and ctx.t[i] >= 570:       # caption-gap M4-unicorn-sequence-preopen-breaker (007 ~15:27): after 09:30 only the breaker formed before it, sweep -> back inside -> FVG
        bz_pre, uni = _SM3.preopen_unicorn(ctx, sd, sw, i, p, fresh)
        if uni:
            bz = bz_pre
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
    elif p.converge_rank and len(pick) > 1:    # caption-gap confluence: the gap with the most converging arrays
        g, _ = _LD.pick_converged(ctx, sd, pick, i, p, p.fvg_pick == "last")
    else:
        g = pick[-1] if p.fvg_pick == "last" else pick[0]
    if p.converge_rank:
        nconv = _LD.converge_n(ctx, sd, g, i, p)
        if nconv:
            sm_tags.append(f"converged_{nconv}")
    if p.unicorn_only and not (uni and g in uni):
        _f("x_unicorn_only")
        return None
    cp_ = False                                # caption-gap E1-close-proximity-entries / new-friday-near-draw-shallow-entry: no leg_pd (M2 EQ filter) for these picks
    if p.close_proximity or p.fri_shallow or p.vi_first:
        g2_, k2_ = None, ""
        if p.close_proximity:
            g2_, k2_ = _ES2.close_prox_pick(ctx, sd, sw, fresh, i, p, session), "close_prox"
        if g2_ is None and p.fri_shallow:
            g2_, k2_ = _ES2.fri_shallow_pick(ctx, sd, sw, fresh, i, p, bz), "fri_shallow"
        if g2_ is None and p.vi_first:
            g2_, k2_ = _ES2.vi_first_pick(ctx, sd, sw, i, p), "vi_first"      # E2-vi-primary-entry-array: the VI of the leg first, the FVG pick is the fallback
        if g2_ is not None:
            g = g2_
            sm_tags.append(k2_)
            if not any(g is z for z in gaps):
                xz = list(xz) + [g]                        # a VI is an entry zone (entry_kind "vi"), not an FVG
            cp_ = k2_ in ("close_prox", "fri_shallow")
    if p.gap_tf_mode == "refine_down" and id(g) in coarse_ids:         # caption-gap A5-mtf-gap-refinement (044 ~45:31; 046 ~19:32): an HTF entry gap is replaced by the LTF FVG of the same displacement inside it
        b_ = _ES1.refine_down(ctx, sd, sw, g, i, p)
        if b_ is not None:
            g = b_
            sm_tags.append("refined_down")
    if p.mtf_hold and not _ES1.mtf_hold_ok(ctx, sd, g, i, p):
        _f("x_mtf_hold")                       # caption-gap A5-multitf-hold-test (064 ~1:32:01): two or more closes inside the 5m gap on a 1-4m chart = a weaker hold
        return None
    if p.mmxm_breaker and bz is None:          # Ep05.8: the smart money reversal leaves a breaker
        _f("x_mmxm_breaker")
        return None
    if p.mmxm_rel_eq and not str(sw.get("key", "")).startswith("rel_eq"):
        _f("x_mmxm_rel_eq")                    # Ep05.8: the MM model runs relative equal lows (highs)
        return None
    top, bottom = g.top, g.bottom
    es_x, es_lvx, wick_tb = {}, {}, None
    ote_fill_ = False
    if g.mt == g.mt and (round(float(g.top), 9), round(float(g.bottom), 9), g.i) in htf_keys:     # caption-gap A12-ob-anchor-level / A12-ob-open-anchor-ltf-wick: an HTF OB zone
        wick_tb = _ES1.wick_ltf_entry(ctx, sd, g, sw, i, p) if p.ob_wick_ltf_entry else None
        if wick_tb is not None:
            sm_tags.append("ob_wick_ltf")
        elif p.htf_ob_anchor == "open":
            top = _ES1.htf_open_top(g, p)
    if p.fvg_edge == "remaining":      # caption-gap A5-partial-reprice-shrink (056 ~16:13): the limit rests at the top of the part not yet traded through
        top = _ES1.remaining_top(sd, g, top, bottom, i, p)
    vi_exact = None
    if p.fvg_vi_extend:                # A5 (022 ~55:00; 098 ~60:00): an adjacent VI extends the box;
        for z in sd.vis("bull"):       # a VI inside the gap is the exact limit
            if not (g.i - 1 <= z.i <= min(g.i + 1, i)) or (p.vi_body_death and not _vi_alive(sd, z, i)):
                continue
            lk_ = _LD3.vi_link(sd, g, z, tk, p)           # caption-gap A5-vi-extended-ce: body- or wick-linked VIs extend the zone (the CE below follows)
            if lk_ == "inside":
                vi_exact = z.top if vi_exact is None else max(vi_exact, z.top)
            elif lk_ == "up":
                top = max(top, z.top)
            elif lk_ == "down":
                bottom = min(bottom, z.bottom)
    em_ = p.entry                                     # caption-gap E2-iofed-depth-second-gap: "auto2" = the near edge when another gap lies close beyond the picked one, else the CE; far_on_breaker takes the edge here
    if em_ == "auto2":
        em_ = "edge" if _ES2.second_gap_near(sd, g, i, p) else "ce"
        _ES2.hit("auto2_" + em_)
    elif em_ == "far_on_breaker":
        em_ = "edge"
    if cp_:
        em_ = "edge"                                   # review fix (E1-close-proximity-entries / new-friday-near-draw-shallow-entry): "a limit at the near edge", whatever p.entry says
    entry = _EN.entry_px(sd, g, top, bottom, p, em_)       # D11 / E2: edge, ce, edge_1tick, iofed, ladder
    es2_t, es2_stop, es2_lvx, wick_ce2, chase_ = {}, None, {}, None, None
    exp_ = bool(p.expansion_ce_entry and vi_exact is None and _SM3.single_expansion(ctx, p, i))
    if exp_:
        entry = (top + bottom) / 2                    # caption-gap M1-inside-fvg-expansion-only (009 ~3:49): a single-expansion day enters inside the FVG toward its middle
        _SM2.hit("expansion_ce")
    if vi_exact is not None:
        entry = vi_exact
    elif p.pm_am_stops:
        entry = _SM4.entry_adjust(sw, entry, top, bottom, p)       # caption-gap M7-pm-short-after-lunch-run-of-am-stops: the entry is the FVG CE
    if vi_exact is None:
        if p.far_edge_reach and (round(float(g.top), 9), round(float(g.bottom), 9), g.i) in htf_keys:
            fe_ = _ES1.far_edge(ctx, sd, g, top, bottom, i, p)      # caption-gap A5-far-edge-reach-conditions (058 ~27:22, ~29:46; 080 ~12:22)
            if fe_[0] is not None and bottom - 1e-9 <= fe_[0] < c[i]:
                entry = fe_[0]
            sm_tags.extend(fe_[1])
        if wick_tb is not None:
            entry = _EN.entry_px(sd, g, wick_tb[0], wick_tb[1], p)  # caption-gap A12-ob-open-anchor-ltf-wick: the LTF FVG inside the OB's wick
        if p.mit_iofed_edge and entry != top and g in sd.gaps and _ES1.mit_context(sd, sw, g, i):
            entry = top                                             # caption-gap A15-mitigation-definition-and-iofed (012 ~11:39): after a mitigation block the IOFED enters at the FVG's near edge, never the CE
            sm_tags.append("mit_iofed_edge")
            _ES1.hit("mit_iofed_edge")
        if p.two_min_ce and any(g is z_ for z_ in gaps):        # review fix: only a base-bar gap (g.src is its middle candle)
            ce2_ = _ES1.two_min_ce(ctx, sd, g, i, p)               # caption-gap new-2m-fvg-ce (062 ~40:09)
            if ce2_ is not None and bottom - 1e-9 <= ce2_ < c[i]:
                entry = ce2_
                sm_tags.append("two_min_ce")
        if p.ob_ce_confluence:
            oc_ = _ES1.ob_ce_entry(ctx, sd, sw, g, top, bottom, i, p)   # caption-gap A12-ob-edge-at-fvg-ce (058 ~32:02)
            if oc_ is not None and oc_ < c[i]:
                entry = oc_
                sm_tags.append("ob_ce_confluence")
        if p.iofed_strict and p.entry == "iofed" and g in sd.gaps:
            if not _ES1.iofed_check(sd, g, entry, i, p):             # caption-gap E2-iofed-full-definition: the CE was reached - not an IOFED
                _f("x_iofed_ce")
                return None
            es_x["iofed"] = dict(ce=float(g.mid), top=float(g.top), bottom=float(g.bottom))
        if p.wick_ce_refine and g in sd.gaps:
            wr_ = _ES2.wick_ce_refine(ctx, sd, sw, g, top, bottom, i, p)         # caption-gap A5-wick-ce-inside-fvg-exact-entry (025 ~01:08:00)
            if wr_ is not None and wr_ < c[i]:
                entry = wr_
                sm_tags.append("wick_ce_refine")
        if p.entry == "far_on_breaker" and g in sd.gaps:
            fb_ = _ES2.far_on_breaker_stop(ctx, sd, sw, g, bz, id(g) in coarse_ids, i, p)         # caption-gap E2-far-edge-fvg-over-breaker (018 ~00:00:09)
            if fb_ is not None and fb_[0] < c[i]:
                entry, es2_stop = fb_
                sm_tags.append("far_on_breaker")
                fr_ = _ES2.far_raise_tags(sd, g, bz, i, p, es2_stop)
                if fr_ is not None:
                    es2_t["far_raise"] = fr_           # the post-break stop raise to the breaker bottom (under its MT)
        if p.fvg_wick_ce and g in sd.gaps:
            wick_ce2 = _ES2.wick_ce_of(sd, g, p)                                  # caption-gap new-fvg-wick-ce (075 ~01:04:11): the retrace runs through the gap to the wick CE
            if wick_ce2 is not None and wick_ce2[0] < c[i]:
                entry = wick_ce2[0]
                sm_tags.append("fvg_wick_ce")
                _ES2.hit("fvg_wick_ce")
            else:
                wick_ce2 = None
        if p.breakaway_chase and ba is not None and g is ba and (getattr(ctx, "re7", None) or {}).get("pending") and ctx.re7.get("kind") == "win":
            entry = top                                                           # caption-gap E5-breakaway-gap-chase (049 ~00:05:01): the breakaway gap of the winner's continuation, a near-edge limit (market after N bars)
            chase_ = int(p.breakaway_chase_bars)
            sm_tags.append("breakaway_chase")
            _ES2.hit("breakaway_chase")
    ladder = _EN.ladder_rungs(top, bottom, p) if p.entry == "ladder" else None
    if ladder is not None and wick_ce2 is not None:
        ladder = [(top + bottom) / 2, wick_ce2[0]]                                # the FVG CE, then the wick CE (the ladder fractions truncate to the two rungs)
        entry = ladder[0]
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
    prop_exit = prop_moved = None
    if p.prop_entry or p.prop_mt_exit:        # A16 (cc04_008 ~0:30-5:40): the propulsion block under the gap
        pb = _EN.prop_block(sd, sw, g.top, i, p)
        if pb is not None:
            ztop, prop_exit = pb
            if p.prop_fail_flip:
                es_x["prop_zone"] = _ES1.prop_zone_real(sd, sw, g.top, i, p)      # caption-gap A16-propulsion-block-full: the block that fails becomes a bearish array of the flipped side
            if p.prop_entry and sw["ext"] < ztop - p.tick < c[i]:
                entry = ztop - p.tick         # the new support: its high - 1 tick (a limit below the market)
                prop_moved = prop_exit        # caption-gap E6-propulsion-mt (review fix): the entry WAS moved to the block - only then the MT stop applies
    if p.prop_deep_mult != 1.0:               # caption-gap A16-propulsion-depth-grade (079 ~12:00): a deep PB is weaker
        pdp_ = _ES1.prop_depth(sd, sw, g.top, i)
        if pdp_ is not None:
            es_x["es1_prop_depth"] = pdp_[1]
    # order block: the blended last down-close candle(s) before the structure break (A12)
    ob = _LD.ob_blend(ctx, sd, sw, i, p, sw["ext_i"] - 3, sw["broke"] - 1, g)      # A12 (caption-gap ob_pick; ob_outside_fvg: the block outside the entry gap)
    if ob is not None and not _EN.ob_quality_ok(sd, sw, ob, i, p):      # A12 ob_disp_mult
        _f("x_ob_disp")
        return None
    stop = bottom - p.pad
    mt = None if ob is None else _ES1.mt_of(p, sd, ob)          # (caption-gap D4-mt-source-tally: body / range / sensitive / blended)
    mt_bind = None
    if (p.stop_mode == "ob_mt" or p.mt_break != "off") and mt is not None and mt < entry - p.min_risk_pts * p.es_pt:
        if p.ob_mt_two_sided and _ES2.ob_mt_dead(sd, _ES1.zone_dict(sd, ob)["k"], float(mt), i):
            stop = min(stop, float(ob.bottom) - p.pad)  # caption-gap A12-mt-worked-both-sides (cc09_008 ~14:37): the MT has worked on both sides - the stop falls back to the OB low
            _ES2.hit("ob_mt_dead")
        else:
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
            if p.vi_stop:
                vb_ = _ES1.vi_stop_level(sd, vi_z, p) if p.vi_tol != "none" else None       # caption-gap A9-vi-retest-tolerance
                vb_ = vi_z.bottom if vb_ is None else vb_
                if entry - (vb_ - p.pad) >= p.min_risk_pts * p.es_pt:
                    stop = vb_ - p.pad
    if p.stop_mode == "ob_near":                # setups_models M1: the OB nearest the sweep low
        ob_n = _ob_at_low(sd, sw, i, p, ctx)
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
    if p.stop_mode in ("wick_ce", "m2_auto", "three_pd", "next_pd", "bpr75") or p.prop_stop:
        stop = _ES3.stop_adjust(ctx, sd, sw, g, ob, mt, entry, stop, i, p, prop_moved)       # caption-gap entries_stops_sizing #3/3: wick CE / M2 auto / three PD arrays / next PD array / BPR 75 % stops, the propulsion MT stop
    if p.ob_vi_overshoot and ob is not None:        # caption-gap A12-ob-overshoot-to-vi (050 ~33:56): the invalidation runs to the adjacent VI's far edge
        d_ = _ES1.zone_dict(sd, ob)
        vf_ = _ES1.vi_far_edge(sd, d_["lo"], d_["hi"], d_["j"], i, p)
        if vf_ is not None and vf_ - p.tick < stop and entry - (vf_ - p.tick) >= p.min_risk_pts * p.es_pt:
            stop, mt_bind = vf_ - p.tick, None
            es_lvx["ob_vi_close"] = (float(vf_), False)
            _ES1.hit("ob_vi_overshoot")
    if p.mss_rearm_lower_high and not is_ifvg:      # caption-gap A19-second-mss-no-new-low (069 ~14:41): "stop just above the CE of the higher FVG when there are two" (mirror: under the lower one's CE)
        prev_ = [m_ for gi_, m_ in sw.get("rg", []) if 0 < g.i - gi_ <= 3]       # the gap the previous order of THIS displacement leg used (consecutive gaps of one leg [our interpretation])
        if rearm and prev_ and p.stop_mode in ("ob_mt", "fvg") and min(prev_ + [g.mid]) - p.pad < entry - p.min_risk_pts * p.es_pt:
            stop = min(prev_ + [g.mid]) - p.pad
            _SM2.hit("mss_rearm_ce2")
        sw.setdefault("rg", []).append((g.i, float(g.mid)))
    if p.stop_bpr_mt and not is_ifvg and g in sd.gaps:      # caption-gap A11-bpr-mt-overshoot-cap (026 ~00:59:14): the BPR directly beyond the gap caps the overshoot at its MT
        bs_ = _ES2.bpr_stop(sd, g, i, p)
        if bs_ is not None and bs_ < stop:
            stop = bs_
    if wick_ce2 is not None:                               # new-fvg-wick-ce: a body close under the wick CE exits, the hard stop at the wick low
        stop = min(stop, wick_ce2[1] - p.pad)
        es2_lvx["wick_ce_close"] = (float(wick_ce2[0] - p.tick), False)
    if es2_stop is not None:
        stop = min(stop, es2_stop)                         # E2-far-edge-fvg-over-breaker: under the overlapped VI / breaker
    if p.fvg_then_ob and ob is not None and g in sd.gaps:  # caption-gap E2-fvg-first-then-ob-open (032 ~00:23:46): the OB beyond the FVG gets a second entry (an add) at its open; one stop beyond the OB
        ob_d_ = _ES1.zone_dict(sd, ob)
        if ob_d_["body_top"] < entry - p.tick + 1e-9:       # the OB open lies beyond (deeper than) the FVG entry
            es2_t["then_ob"] = (float(ob_d_["body_top"]), float(ob.bottom))
            stop = min(stop, float(ob.bottom) - p.pad)
    if is_ifvg and (p.ifvg_entry != "edge" or p.ifvg_depth or p.ifvg_stop_pts or p.ifvg_stop == "far"):   # M10 / A8
        r_ = _SM.ifvg_stop(sd, g, entry, stop, p, i)
        if r_ is None:
            _f("x_ifvg_depth")
            return None                           # caption-gap A8-ifvg-depth-tolerances: the retrace reached past the cap / the CE
        entry, stop = r_
    if is_ifvg and p.ifvg_min_risk_pts and ctx.tf > 1 and entry - stop < p.ifvg_min_risk_pts * p.es_pt:
        _f("x_ifvg_min_risk")
        return None
    if p.ote != "off" or p.leg_pd_strict or p.ote_leg_stop or p.ote_stack_tag or p.ote_need_s or p.ote_parent_third:     # M13 (+ caption-gap ote_need_s / ote_parent_third)
        r_ = _SM.ote_adjust(sd, sw, i, p, entry, stop, "ifvg" if is_ifvg else "fvg", sm_tags)
        if r_ is None:
            if sw.pop("_ote_wait", False) and sd.sweep is None:
                sd.sweep = sw                          # caption-gap M13-swing-confirm-gate: the gate is not open yet - the sweep (and its gap) wait for the 4th candle
            return None
        entry, stop = r_
        if p.ote == "limit" and p.ote_reanchor:
            es_x["ote_leg"] = True                     # caption-gap M13-reanchor-parent: the pending OTE limit follows a new swing high above H
        if p.ote == "limit" and p.ote_leave_bars:
            ote_fill_ = True                           # caption-gap M13-ote-leave-discount-fast (review fix): the OTE limit on the FVG path is an OTE entry for me2's leave check
    uni_t = {}
    if bz is not None and uni and g in uni and (p.bz_higher_array or (p.in_zone_ladder and ladder is None)):
        stop = _ES2.breaker_tail(ctx, sd, i, p, bz, entry, stop, uni_t)     # caption-gap A13-breaker-close-beyond-higher-array / E12-in-zone-larger-second: the unicorn is a breaker entry too (review fix)
    st = _fvg_state(sd, g, i) if g in sd.gaps else ""
    lvt = list(sm_tags)
    if p.td_fvg_hold and _LD4.td_hold(ctx, sd, g, i, p) and _fvg_state(sd, g, i) != "open":
        lvt.append("td_hold")                          # caption-gap new-time-distortion (a): the gap lives on the body hold
    lvx = dict(es_lvx, **es2_lvx)
    if p.prop_mt_exit and prop_exit is not None:
        if p.prop_mt_test == "wick":
            es_x["prop_wick"] = float(prop_exit)      # caption-gap A16-propulsion-block-full: any trade through the PB MT exits (027, cc04_008)
        else:
            lvx["prop_mt"] = (prop_exit, False)       # A16: a body close below the propulsion MT exits
    if p.vi_hold and vi_z is not None:
        lvx["vi_hold"] = (float(vi_z.bottom), False)   # Ep07.4: a body close below the VI exits
    if p.ob_cisd != "off" and ob is not None and _EN.ob_cisd_ok(sd, ob, i, p):
        lvt.append("ob_cisd")                          # A12 validation tag
    if is_ifvg and p.ifvg_hold and not p.ifvg_fail_tf:
        lvx["ifvg_fail"] = (g.bottom, True)    # A8: a body close back below the IFVG
    ce_hold_ = bool(p.mmxm_ctx)                # Ep05.8: fails to hold the imbalance's CE = the ce_hold
                                               # rule (review fix: reused, no new exit)
    if sw.get("on_side"):
        lvt.append("on_side")
    if ba is not None and g is ba and p.breakaway in ("tag", "hold"):
        lvt.append("breakaway")
        if p.bk_state:                                 # caption-gap A6 bk_state: candidate / retraced / qualified / dead
            lvt.append("bk_" + L.bk_state(sd.h, sd.l, g, i, p.bk_depth, sd.bprs() if p.bk_bpr_ce else (), p.bk_bpr_ce)[0])
        if p.breakaway == "hold":
            lvx["breakaway_ce"] = (ba.mid, True)       # a body close beyond its CE: not breakaway
    if p.gap_classes and g in sd.gaps:                 # caption-gap A6-gap-hierarchy-common: breakaway / measuring / common
        lvt.append("gap_" + _LD3.gap_class(sd, sw["ext_i"], sw["ext"], g, i, p))
        if _LD3.cc_common_tag(sd, entry, i):
            lvt.append("cc_common")                    # cc04_010: the entry sits in a CC body gap
    if p.fvg_q_hold:
        lvx["q_close"] = (top - 0.25 * (top - bottom), True)   # the upper quarter must hold
    ir = _ir_in_leg(sd, sw, i, p)
    if ir and p.ir_def != "a7" and p.imm_rebalance_disp != "off":
        lvt.append("ir_fast_" + p.ir_def)              # review fix #85: the "fast delivery expected" tag on the displacement-gate path too
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
    if is_ifvg and p.ifvg_hold and p.ifvg_fail_tf:
        _ME1.mark_tags(tags, "ifvg15", float(g.bottom))      # caption-gap A8-ifvg-15m-body-failure: the failure is a body close on the ifvg_fail_tf bars (me1.manage)
    if mt_bind is not None:
        tags["mt_close"] = mt_bind
    if uni_t:
        lv_u = uni_t.pop("lvx", None)
        if lv_u:
            tags["lvx"] = dict(tags.get("lvx") or {}, **lv_u)
        tags.update(uni_t)
    if p.ob_grade_mult != (1.0, 1.0) and ob is not None:
        es2_t = dict(es2_t, **_ES2.ob_grade_tags(_ES1.zone_dict(sd, ob)))      # caption-gap A12-mt-grading (cc04_003), review fix: the FVG-path OB (ob_blend) is graded at the fill too [our interpretation: the retest depth of the OB's MT during the retrace to the gap]
    if es2_t:
        tags["es2"] = es2_t
    if p.mtf_hold and ctx.tf < 5 and not any(g is z for z in sd.gaps):
        tags["mtf_gap"] = (float(g.bottom), float(g.top), int(g.i))      # review fix A5-multitf-hold-test: the resting order is re-judged on the 1-4m closes each bar (es1.mtf_pending_dead)
    if p.vi_ladder_exit and mt is not None:
        tags["es3"] = dict(tags.get("es3") or {}, ob_mt=float(mt))       # caption-gap E12-631-vi-wickce-invalidation: the OB MT whose trade (before the displacement) voids the idea
    if p.ifvg_mohawk_add and is_ifvg and not (sd.l[g.i + 1:i] <= g.top).any():
        tags["es3_rung"] = float(g.bottom) - p.mohawk_add_ticks * p.tick   # caption-gap E12-mohawk-add-ifvg (102 ~01:14:30): the one-pass IFVG's mohawk add beyond the far edge
    if chase_ is not None:
        tags["chase_bars"] = chase_
    if cp_:
        tags["no_leg_wait"] = True
    if es_x:
        if "es1_prop_depth" in es_x:
            tags["es1_prop_depth"] = es_x.pop("es1_prop_depth")
        if es_x:
            tags["es1"] = es_x
    if ote_fill_:
        tags["me2"] = dict(tags.get("me2") or {}, ote_fill=True)
    if m2_live:
        tags["m2_live"] = True                         # caption-gap M2-leg-eq-after-low-prints: the pending order is cancelled when the leg re-anchors above its gap
    if imp_eq is not None and imp_eq != "wait":
        tags["sm4"] = dict(kind="implied", implied_eq=float(imp_eq))     # caption-gap M2-implied-range-eq-gate: adds only under the implied EQ (side space)
    if any(g is z for z in leg_tf_z):
        lvt.append(f"leg_tf_{sw.get('leg_tf', 0)}m")
    if em_ == "ce" and vi_exact is None:
        tags["ce_entry"] = True                        # E6f ce_stop_pad_pts
    if exp_:
        tags["expansion"] = True                       # caption-gap M1-inside-fvg-expansion-only: _finish_order sets the bulk / rest ladder
        tags["ce_entry"] = True
    if ladder is not None:
        tags["ladder"] = ladder
        if wick_ce2 is not None:
            tags["ladder_fracs"] = (0.5, 0.5)
    if p.ob_cisd == "cancel" and ob is not None:
        tags["cancel_low"] = float(ob.bottom)          # A12: the OB low must hold
    if p.breaker_entry == "classic" and bz is not None and bz.top > entry and not sw.get("bz_sent"):
        return _breaker_order(ctx, sd, sw, bz, i, p, session, risk_mult)   # M4.1: the breaker comes first
    if p.entry_arrays or p.reclaimed_ob or p.prop_fail_flip or "ob" in p.irl_entries or p.org_entry_array or p.ote == "ob62":       # M0.5: an array the retrace reaches before the FVG
        o2 = _SM.array_order(ctx, sd, sw, i, p, session, risk_mult, entry, bz)
        if o2 is not None:
            return o2
    rl_inv = None
    if p.range_lock:                              # caption-gap A12-range-internal-ignore: the order rests with no expiry while the range holds
        rl_inv = float(mt) if mt is not None else (float(ob.bottom) if ob is not None else float(sw["ext"]))
        tags["no_expire"], tags["cancel_close"] = True, rl_inv
    o_ = _finish_order(ctx, sd, i, p, session, sw, entry, stop, risk_mult,
                       h[sw["ext_i"]:i + 1].max(), tags, pctx_free=True, skip_leg_pd=cp_)
    if o_ is None and p.max_stop_pts and sw.pop("_wide_stop", False) and sd.sweep is None:
        sd.sweep = sw                                  # caption-gap E5-stop-feasibility (item 44): a too-wide stop keeps the sweep alive - only a NEWER gap (a second break) re-arms it
        sw["ev_g"], sw["ev_i"] = max(g_.i for g_ in gaps), i
    if o_ is not None and rl_inv is not None:
        _SM2.range_lock_set(sd, sw, i, rl_inv, float(ob.bottom) if ob is not None else float(sw["ext"]))
    if o_ is not None and keep_sw and not p.evolve_fvg and not p.mss_rearm_lower_high:
        sd.sweep = None                   # wait_structural: the sweep is consumed once an order is armed
    return o_


def _vi_alive(sd, z, i: int) -> bool:
    """A9 / Ep03.3 body death rule for the intraday Side VIs (review fix, vi_body_death): alive until
    a later body spans it (L.vi_body_dead over bars z.i+1 .. i)."""
    return L.vi_body_dead(sd.o, sd.c, z, end=i, rule=getattr(sd, "vi_dead_rule", "full_span")) is None


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
                if p.vi_breakaway and _LD3.opp_vi_is_breakaway(sd, z, i):
                    continue                   # caption-gap A9-vi-breakaway: no retrace target in a protected range
                out += [(z.bottom, "array"), (z.mid, "array")]
    if p.bpr_targets:                  # review fix: only BPRs not traded into since they formed
        for z in sd.bprs(p.bpr_max_gap_bars):
            if z.i <= i and z.bottom > above and after(z) < z.bottom:
                out += [(z.bottom, "array"), (z.mid, "array")]
    if p.mit_targets:
        for z in sd.opp_mits():
            if z.i <= i and z.bottom > above and (not (p.mit_body_respect or p.mit_mt_invalid)
                                                  or L.mitigation_alive(sd.c, z, i, p.mit_mt_invalid)):
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
        sw["ob"] = _ob_at_low(sd, sw, i, p, ctx)
        if i - 1 >= sw["ext_i"] + 2:
            sw["ob_frozen"] = True               # the candidate window is complete
    ob = sw.get("ob")
    if ob is None or i <= ob["k"]:
        return None
    if p.ob_arm == "leave" and not sd.c[i] > ob["body_top"]:
        return None
    if p.ob_arm == "intrabar_htf":
        if not sd.h[i] > ob["body_top"]:
            return None                            # caption-gap A12-same-candle-retrace (cc04_003 ~00:04:04): the trade-through of the OB high validates it - armed at once, not at a candle close
        _ES2.hit("ob_arm_intrabar" if not sd.c[i] > ob["body_top"] else "ob_arm_intrabar_close")
    if _ES1.ob_gate_on(p) and not _ES1.ob_gate(ctx, sd, sw, ob, i, p):
        return None                                # caption-gap A12-ob-requires-signatures / A12-ob-requires-narrative: a potential OB, not yet an order block
    sw["ob_sent"] = sw["ob_frozen"] = True
    entry = _EN.ob_entry_price(ob, sd, p, i)       # Ep03.9 / A12: body_top, mt, range_top|high, open, ob_zone (+ caption-gap ob_anchor_rule)
    sw_e = _ES2.ob_swept_entry(sd, ob, p)          # caption-gap A12-mt-retrace-after-stop-run (cc04_003 ~00:32:47): a candle that ran a prior low is bought at its body MT
    if sw_e is not None:
        entry = sw_e
    if entry >= sd.c[i]:
        entry = ob["body_top"]                     # [our interpretation] never a limit above the market
    mt_stop_ = p.ob_stop == "mt" or p.mt_break != "off"          # review fix (D4-mt-source-tally): mt_break also governs the pre-break OB (trade = the stop at the MT, close / warn = the far-edge stop + the MT close / warning)
    stop = ob["mt"] - p.pad if mt_stop_ else sw["ext"] - p.pad
    mt_close = (float(ob["mt"]), float(ob["lo"])) if mt_stop_ else None
    if sw_e is not None and entry < sd.c[i]:
        stop, mt_close = ob["lo"] - p.pad, None    # caption-gap A12-mt-retrace-after-stop-run: a body-MT entry takes the stop under the OB low
    if p.ob_mt_two_sided and mt_stop_ and _ES2.ob_mt_dead(sd, int(ob["k"]), float(ob["mt"]), i):
        stop, mt_close = ob["lo"] - p.pad, None    # caption-gap A12-mt-worked-both-sides (cc09_008 ~14:37): no MT level any more - the stop at the OB low
        _ES2.hit("ob_mt_dead")
    osk_ = _ES3.ob_stop_for(ob, p)                 # caption-gap E6-ob-body-stop (cc04_003 ~00:10:44): under the OB body low (the close) / wick low instead of the MT
    if osk_ is not None and entry - osk_ >= p.min_risk_pts * p.es_pt:
        stop, mt_close = osk_, None
        _ES3.hit("ob_stop_" + p.ob_stop_kind)
    if entry - stop < p.min_risk_pts * p.es_pt or entry <= stop:
        stop = sw["ext"] - p.pad        # [our interpretation] fallback to the sweep extreme
        mt_close = None
    ob_low_cancel, es_lvx = ob["body_low"], {}
    if p.ob_vi_overshoot:                          # caption-gap A12-ob-overshoot-to-vi (050 ~33:56): the zone runs to the adjacent VI's far edge
        vf_ = _ES1.vi_far_edge(sd, ob["lo"], ob["body_top"], ob["j"], i, p)
        if vf_ is not None and vf_ - p.tick < stop and entry - (vf_ - p.tick) >= p.min_risk_pts * p.es_pt:
            stop, mt_close, ob_low_cancel = vf_ - p.tick, None, vf_
            es_lvx["ob_vi_close"] = (float(vf_), False)
            _ES1.hit("ob_vi_overshoot")
    tags = dict(unicorn=False, fvg_bottom=ob["body_low"], fvg_ce=ob["mt"], entry_kind="ob_pre",
                mitigation=False, propulsion=False, ob_pre=True, ob_body_low=ob_low_cancel,
                ob_lo=ob["lo"],
                # setups_models review fix: the sweep this order belongs to, so the MSS gates acting
                # at the later break can cancel (ob_pre_gate "cancel") or release ("hold") it
                sw_ref=sw, sw_ext_i=sw["ext_i"], ob_hold=p.ob_pre_gate == "hold")
    if mt_close is not None:
        tags["mt_close"] = mt_close                # A12 / Ep02.3 mt_close_stop
    if es_lvx:
        tags["lvx"] = es_lvx
    if p.vi_ladder_exit:
        tags["es3"] = dict(tags.get("es3") or {}, ob_mt=float(ob["mt"]))      # caption-gap E12-631-vi-wickce-invalidation (review fix): the pre-break OB's MT voids the idea too
    if p.add_momentum:
        tags["es3"] = dict(tags.get("es3") or {}, ob_top=float(ob["body_top"]))      # caption-gap E12-single-add-variants (review fix): "runs away" is measured from the OB body top
    if p.ob_grade_mult != (1.0, 1.0):
        _ES2.tag(tags, **_ES2.ob_grade_tags(ob))   # caption-gap A12-mt-grading (cc04_003): the fill-time grade A / B
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
    ob = _LD.ob_blend(ctx, sd, sw, i, p, sw["ext_i"] - 3, sw["broke"] - 1, None)       # caption-gap A12 ob_pick (ob_outside_fvg: outside the displacement FVG)
    if ob is None:
        return None
    if _ES1.ob_gate_on(p) and not _ES1.ob_gate(ctx, sd, sw, _ES1.zone_dict(sd, ob), i, p):
        sw["ob2_sent"] = False                     # caption-gap A12-ob-requires-signatures / -narrative: not yet an order block - tried again on the next bar
        return None
    entry = float(sd.o[ob.src])
    sw["_ob_anchor_k"] = int(ob.src)                   # caption-gap setups_models #6/7 review fix: ob_below_open / eq_fresh_ob judge this candle
    if p.ob_anchor_rule == "gap_presence" and _LD3.ob_anchor_choice(sd, ob.src, _LD3.ob_run_end(sd, ob.src), i, p) == "gap":
        entry = float(ob.top)                          # caption-gap A12: an untraded wick gap keeps the wick extreme as the anchor
    if entry >= sd.c[i]:
        _f("x_ob_anchor_above")
        return None
    mt = _ES1.mt_of(p, sd, ob)
    stop = float(mt) - p.pad
    mt_close = (float(mt), float(ob.bottom))
    zd_ = _ES1.zone_dict(sd, ob) if (p.ob_mt_two_sided or p.ob_grade_mult != (1.0, 1.0)) else None
    if p.ob_mt_two_sided and _ES2.ob_mt_dead(sd, int(zd_["k"]), float(mt), i):
        stop, mt_close = float(ob.bottom) - p.pad, None      # caption-gap A12-mt-worked-both-sides (cc09_008 ~14:37), review fix: the anchor OB's MT is no level any more either
        _ES2.hit("ob_mt_dead")
    if entry - stop < p.min_risk_pts * p.es_pt:
        stop, mt_close = sw["ext"] - p.pad, None
    tags = dict(unicorn=False, fvg_bottom=float(ob.bottom), fvg_ce=float(mt), entry_kind="ob_anchor",
                mitigation=False, propulsion=False)
    if p.ob_grade_mult != (1.0, 1.0):
        _ES2.tag(tags, **_ES2.ob_grade_tags(zd_))        # caption-gap A12-mt-grading (cc04_003), review fix: the anchor OB is graded at its fill too
    if mt_close is not None:
        tags["mt_close"] = mt_close
    return _finish_order(ctx, sd, i, p, session, sw, entry, stop, risk_mult,
                         sd.h[sw["ext_i"]:i + 1].max(), tags, pctx_free=True)


TS_TFS = ("15m", "30m", "1h", "4h", "D", "W")


def _ts_arrays(ctx, sd, i, known_by, tfs=TS_TFS, src=(0, 1, 3)) -> list:
    """Same-side HTF PD arrays (FVG / OB / VI) valid at bar i's close and complete by `known_by`,
    in side space: [(top, bottom, known_ts)]. From the confluence table; without it (no overnight
    bars) from the session's 15m/60m FVGs (DayCtx.hzones, not closed through by bar i).
    Caption-gap NEW-no-return-to-origin-ob (`no_origin_retest`): the origin daily low's arrays are dropped (es1.drop_origin)."""
    out = _ts_arrays0(ctx, sd, i, known_by, tfs, src)
    if getattr(ctx, "no_origin", None) is not None and out:
        out = _ES1.drop_origin(ctx, sd, i, out)
    return out


def _ts_arrays0(ctx, sd, i, known_by, tfs=TS_TFS, src=(0, 1, 3)) -> list:
    now = ctx.idx[i] + pd.Timedelta(minutes=ctx.tf)
    out = []
    if getattr(ctx, "conf", None) is not None:
        for top, bot, tf_, sc, kn in ctx.conf.valid(now, sd.sign, tfs, src, known_by):
            a, b = sd.x(top), sd.x(bot)
            out.append((max(a, b), min(a, b), pd.Timestamp(int(kn), tz="UTC").tz_convert(ctx.idx.tz)))
        if getattr(ctx, "bh3_mwdl", False):
            out += _BH3E.dcandle_rows(ctx, sd, i)             # caption-gap X3-b10-case-c-to-b-upgrade (bias_htf#3/7): the case-B daily down-candle levels as entry arrays
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
    elif p.ts_stop == "mid" and arr is not None:
        st = _SM7.mid_stop(ctx, sd, i, arr, p)              # caption-gap M12-ts-stop-midpoint (022 ~02:48:40): the VI bottom / FVG CE / OB MT, minus a tick
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
    if v in ("cc_limit", "external", "prev_pm"):
        return None
    if v == "htf_stab":                  # caption-gap M12-0930-htf-fvg-stab-no-mss: a pool run stabbing into an HTF FVG - a limit in it, no MSS / SMT
        return _SM4.stab_order(ctx, sd, sw, i, p, session, risk_mult)
    if v == "cc_1h_ob":
        return _cc_1h_ob(ctx, sd, sw, i, p, session, risk_mult)
    if v == "or60" and sw["key"] != "or60":
        return None
    if not L.turtle_soup(sd.l, sd.c, sw["level"], sw["ext_i"], i, p.ts_max_pts * p.es_pt, p.ts_back_bars):
        return None
    if p.weekly_bisi_ts_block and _TP2.ts_weekly_bisi(ctx, sd, sw, i, p):
        _f("x_ts_weekly_bisi")           # caption-gap L9-htf-fvg-target-ladder (102 ~02:12:22): the pool lies just above an unfilled weekly BISI - the draw is the gap, no turtle long
        return None
    premium_ts = False
    if p.ts_need_htf and not _htf_tag(ctx, sd, i, sw["ext"], p.eq_tol_pts * p.es_pt):
        if not (p.ts_ote_ok and _SM6.ts_ote(ctx, sd, sw, i, p)):       # caption-gap M13-premium-ote-turtle-soup: the OTE band / beyond the EQ of the last impulse leg qualifies too
            return None
        premium_ts = True
        _SM6.hit("premium_ts")
    if p.ts_skip_reswept and _SM2.reswept(ctx, sd, sw, i, p):
        _f("x_ts_reswept")               # caption-gap M12-second-takeout-turtle-soup (046): a second shallow break of an already swept pool is no turtle long
        return None
    if p.ts_need_smt and not _SM2.ts_smt_ok(sw):
        _f("x_ts_no_smt")                # caption-gap B18-smt-accum-distrib (cc03_005): the correlated asset must refuse the break
        return None
    if p.ts_need_smt:
        _SM2.hit("ts_need_smt")
    if p.ts_itl_context and not _SM2.itl_ok(ctx, sd, sw, i, p):
        _f("x_ts_itl_context")           # caption-gap new-intermediate-term-hl-fade (cc09_005): an older-than-yesterday pool is faded only with context
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
        nx = _SM2.next_array_level(ctx, sd, i, sw["level"], p, kb) if p.ts_next_array else None     # caption-gap new-stop-run-overshoot-next-array (025 ~1:05:16)
        if nx is not None:
            entry, stop = nx
            _SM2.hit("ts_next_array_turtle")
        else:
            stop = _ts_stop(ctx, sd, sw, i, p, arr, entry)
    else:                                                # or60: target the OR60 high
        hi = sd.x(ctx.or60[0] if sd.sign > 0 else ctx.or60[1])
        fixed = [(hi + p.pool_beyond_pts * p.es_pt if p.exit_mode == "split" else hi - p.exit_before_pts * p.es_pt, "pool")]
    tags = dict(unicorn=False, fvg_bottom=sw["ext"] if arr is None else arr[1], fvg_ce=(entry + sw["ext"]) / 2,
                entry_kind="turtle_soup" if v == "2023" else "ts_or60", mitigation=False, propulsion=False)
    if premium_ts:
        tags["lv_tags"] = ["premium_ts"]
    return _finish_order(ctx, sd, i, p, session, sw, entry, stop, risk_mult,
                         sd.h[sw["ext_i"]:i + 1].max(), tags, skip_leg_pd=True, fixed=fixed)


def _hour_down_candle(ctx, sd, ext_i: int, i: int, m: int = 60):
    """cc_1h_ob: the last DOWN-close clock-aligned 1h candle (side space) that started at or before
    the sweep extreme's bar and is complete by bar i: (open, high, index of its last base bar).
    (caption-gap M12-cc-daily-ob-turtle-soup / B5-topdown-entry-refinement: `m` = 15 / 5 for the refined candle.)"""
    if m < ctx.tf or m % ctx.tf:
        return None
    hc = sd.__dict__.get("_h60" if m == 60 else f"_h{m}")
    if hc is None:
        key = ctx.idx.floor(f"{m}min")
        b = pd.Series(np.arange(len(key)), index=key).groupby(level=0)
        first, last = b.min().values, b.max().values
        done = np.asarray((ctx.idx[last] - b.min().index) >= pd.Timedelta(minutes=m - ctx.tf))
        o = sd.o[first]; c = sd.c[last]
        hh = np.array([sd.h[a:z + 1].max() for a, z in zip(first, last)])
        hc = sd.__dict__["_h60" if m == 60 else f"_h{m}"] = (first, last, done, o, hh, c)
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
    ob = min(obs, key=lambda a: a[0])
    ho = None
    if p.refine_tfs:                                     # caption-gap B5-topdown-entry-refinement: the lowest timeframe with a validated down-close candle INSIDE the daily OB (the stop stays below the sweep low)
        for m_ in sorted(int(x) for x in p.refine_tfs):
            hc = _hour_down_candle(ctx, sd, sw["ext_i"], i, m_)
            if hc is None or not (ob[1] - tol <= hc[0] <= ob[0] + tol) or (p.cc_ob_validate and not (sd.h[hc[2] + 1:i + 1] > hc[1]).any()):
                continue
            ho, hh, hlast = hc
            _SM6.hit("refine_tf_%d" % m_)
            break
        if ho is None:
            return None
    else:
        hc = _hour_down_candle(ctx, sd, sw["ext_i"], i, p.cc_ob_tf)
        if hc is None:
            return None
        ho, hh, hlast = hc
        if p.cc_ob_validate and not (sd.h[hlast + 1:i + 1] > hh).any():
            return None                                  # (cc_ob_validate, review fix: the validation is a switch, default on = as built) not yet traded back up through it (the order arms only after a later bar trades above C.high)
    sw["ts_sent"] = True
    if p.cc_ob_tf != 60 or p.ts_r_preset or p.cc_ob_offset_ticks:
        _SM6.hit("cc_ob_variant")
    entry = ho
    if p.cc_ob_offset_ticks:                             # review fix (M12-cc-daily-ob-turtle-soup / E3): the spread moves the buy limit TOWARD the market (C.open + spread) so a touch fills; capped below the last close
        entry = min(ho + p.cc_ob_offset_ticks * p.tick, float(sd.c[i]) - p.tick)
    stop = (ob[0] + ob[1]) / 2 - p.pad if p.ts_stop == "array" else sw["ext"] - p.pad
    if entry - stop < p.min_risk_pts * p.es_pt:
        stop = sw["ext"] - p.pad
    risk = entry - stop
    mults, be_r = (p.ts_r_mults, p.ts_be_r) if p.ts_r_preset != "cc02_003" else ((3.0, 9.0, 15.0), 3.0)     # caption-gap M12-cc-daily-ob-turtle-soup switch B (cc02_003, 5m refined): half at 3R, 9R / 15R runners, breakeven after 3R
    fixed = [(entry + r * risk, "array") for r in mults]
    fr_ = tuple([1.0 / len(fixed)] * len(fixed)) if p.ts_r_preset != "cc02_003" else (0.5, 0.25, 0.25)
    tags = dict(unicorn=False, fvg_bottom=ob[1], fvg_ce=(ob[0] + ob[1]) / 2, entry_kind="ts_cc_1h_ob",
                mitigation=False, propulsion=False, fracs=fr_,
                be_at=entry + be_r * risk)
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
    if p.no_origin_retest and cand:
        cand = [(v, k) for v, k in cand if not _ES1.is_origin(ctx, sd, i, v)]      # caption-gap NEW-no-return-to-origin-ob: the origin low is not bought again
    if p.raid_roll:                         # caption-gap L2-raid-level-rolls (cc04_011 ~13:57): the raid level rolls to the newest 15m pivot low while no 15m MSS printed; nothing above it
        rr_ = _SM3.rolled_raid(ctx, sd, i, p, lv, session)
        if rr_ is not None:
            _SM2.hit("raid_roll")
            k_, v_ = rr_
            cand = [(v_, k_)] if (v_ < sd.c[i] and sd.l[i] >= v_ and (session, k_, round(v_, 9)) not in sent) else []
    if not cand:
        return None
    v, k = max(cand)
    sent.add((session, k, round(v, 9)))
    entry = _SM6.level_src(ctx, sd, v, i, p) - p.ts_cc_below_pts * p.es_pt     # caption-gap E2-body-extreme-entry: the wick extreme (default) or the extreme body of the swing candles
    stop = v - p.ts_max_pts * p.es_pt - p.pad
    sw = dict(session=session, name=k, level=v, key=k, ext=entry, ext_i=i, broke=None, sweep_i=i,
              smt=None, smt2=None)
    if p.ts_skip_reswept and _SM2.reswept(ctx, sd, sw, i, p):
        _f("x_ts_reswept")                  # caption-gap M12-second-takeout-turtle-soup
        return None
    if p.ts_itl_context and not _SM2.itl_ok(ctx, sd, dict(sw, ext=v), i, p):
        _f("x_ts_itl_context")
        return None
    if p.ts_next_array:                     # caption-gap new-stop-run-overshoot-next-array: the resting limit sits at the next array beyond the pool
        nx = _SM2.next_array_level(ctx, sd, i, v, p, ctx.idx[i] + pd.Timedelta(minutes=ctx.tf))
        if nx is not None:
            entry, stop = nx
            sw["ext"] = entry
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
            elif (p.htf_body_qual and top >= l[i] and c[i] >= bot and l[k0:i].min(initial=np.inf) <= top
                  and _SM2.body_qual_zone(ctx, sd, bot, k0, i)):
                arrs.append((top, bot, kn))      # caption-gap A4-ltf-body-qualification: wicks reached the array before, the 15m / 5m bodies never closed beyond it
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
    if p.chop_scalp_pts > 0 and p.sloppy_mode == "scalp" and getattr(ctx, "cur_sloppy", ""):
        p = replace(p, min_draw_pts=p.chop_scalp_pts)      # caption-gap L15-chop-micro-scalps (010 ~01:15:51): the minimum room of a chop scalp is chop_scalp_pts, not min_draw_pts
    tol = p.eq_tol_pts * p.es_pt
    sw.pop("_wide_stop", None)                       # caption-gap item 44 review fix: a stale too-wide-stop flag of an earlier call must not restore the sweep after an unrelated None return
    tags = dict(tags)
    lvt = list(tags.pop("lv_tags", []) or [])        # levels_detectors tags (Trade.lv_tags)
    lvx = dict(tags.pop("lvx", {}) or {})            # levels_detectors exit levels (side space)
    if getattr(ctx, "counter_now", False):           # caption-gap new-counter-bias-scalp-exit (013 ~15:07): half risk, one exit at the nearest pool, flat at the midnight open
        risk_mult *= 0.5
        tags["single_exit"] = True
        lvt.append("counter_scalp")
        mo_ = _open_known(ctx, "midnight", i)
        tags["sm3"] = dict(tags.get("sm3") or {}, **({} if mo_ is None else {"counter_mo": float(sd.x(mo_))}))
        if mo_ is not None and entry >= float(sd.x(mo_)) - 1e-9:
            _f("x_counter_past_mo")                  # review fix: an entry already past the midnight open in the trade's direction (a counter short filled below it) is the "never hold there" case
            return None
        _SM2.hit("counter_scalp")
    cn6_ = getattr(ctx, "curve_now", "")
    ct_pool_ = False
    if cn6_ == "curve":                  # caption-gap M1-short-sell-side-of-buy-curve: the counter-bias short's single target = the HTF array's near edge
        tg6_ = _SM6.curve_target(ctx, sd, i, p, -sd.sign)
        if tg6_ is None or fixed is not None:
            _f("x_curve_no_array")
            return None
        fixed = [(float(_exit_px(tg6_, "array", p)), "array")]
        lvt.append("curve_short")
        _SM6.hit("curve_short")
    elif cn6_ == "lod":                  # caption-gap X14-opposite-second-trade-after-win (093 ~00:14:52): the counter-bias short is allowed only toward the predefined low-of-day level - its final target
        lv7_ = _SM7.lod_level(ctx, sd, i, p)
        if lv7_ is None:
            _f("x_lod_no_level")
            return None
        fixed = [(float(min(_exit_px(lv7_, "pool", p), lv7_ - _tick(p))), "pool")]
        lvt.append("lod_short")
        _SM7.hit("lod_short")
    elif cn6_ == "m0950":                # caption-gap T7-0950-reversal-or-continuation (073 ~00:25:56): the NFP reversal profile after the pool run in 09:50-10:10
        lvt.append("m0950_rev_counter")
    elif cn6_ == "ct":                   # caption-gap BH-B3-counter-bias-modes (095 ~11:56; 030 ~25:11): a counter-bias trade after the delivered draw - the nearest pool only, one exit, no adds
        tags["single_exit"] = True
        tags["no_adds"] = True
        ct_pool_ = True                              # (review round 1) the single exit is the nearest opposing POOL - no pool, no trade (checked where the draw is picked)
        lvt.append("counter_trend")
        _BH1E.hit("counter_trend")
    elif cn6_ == "ctr":                  # caption-gap B3-countertrend-from-range-extreme (bias_htf#3/7; cc09_008 ~16:57): single target at the nearest opposing array inside the range, no adds, half risk
        tg3_ = _BH3E.ctr_target(ctx, sd, i, p)
        if tg3_ is None or fixed is not None:
            _f("x_ctr_no_array")
            return None
        fixed = [(float(_exit_px(tg3_, "array", p)), "array")]
        tags["single_exit"] = True
        tags["no_adds"] = True
        risk_mult *= 0.5
        lvt.append("counter_range")
        _BH3E.hit("counter_range")
    elif cn6_ == "pmh":                  # caption-gap M12-contrarian-pmh: only the previous month's extreme, one exit at the nearest pool
        if str(sw.get("key", "")) != "pml_month":
            _f("x_pmh_key")
            return None
        tags["single_exit"] = True
        lvt.append("pmh_contrarian")
        _SM6.hit("pmh_contrarian")
    if p.ir_accel_hold and tags.get("entry_kind") == "ir":     # caption-gap M11-immediate-rebalance-management (100 ~1:36:14): half at the nearest pivot, the rest only on acceleration
        tags["fracs"] = (0.5, 0.5)
        tags["sm3"] = dict(tags.get("sm3") or {}, ir_accel=True)
    if p.entry_offset_ticks and p.entry_order != "stop_cc" and entry < c[i]:      # caption-gap E3-entry-spread-offset (cc02_001 ~00:21:13): every limit moves toward the market, a touch of the original level fills
        entry = max(entry, min(entry + p.entry_offset_ticks * p.tick, float(c[i]) - p.tick))
        _ES2.hit("entry_offset")
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
    if p.trade_type == "day" or (p.day_mode_auto and _ME1.day_pick(ctx, sd, i, p, entry)):      # X5c (064 ~1:38:44): a day trade's stop sits below the 08:30 open / its wick CE
        auto_ = p.trade_type != "day"    # caption-gap X5-day-trade-stop-no-trail: day_mode_auto picks it per order (lower of the open and the wick CE, beyond a swept pre-release low, a smaller size)
        k830 = _idx_at(ctx, 510)         # and is never moved (no trail, no breakeven): partials pay for it
        day_ok = False
        if k830 < i and k830 < len(ctx.t) and ctx.t[k830] == 510:
            b830 = min(sd.o[k830], c[k830])
            lvl = float(sd.o[k830]) if p.day_stop == "open" else float(b830 - (b830 - l[k830]) / 2)
            if auto_:
                lvl = _ME1.day_level(ctx, sd, k830, i, p)
            if lvl < entry and entry - (lvl - p.pad) >= p.min_risk_pts * p.es_pt:
                stop = lvl - p.pad
                tags["day_trade"] = True
                lvt.append("day_trade")
                if auto_:
                    tags["day_auto"] = True
                    lvt.append("day_auto")
                day_ok = True
        if not day_ok and not auto_:
            _f("x_day_trade_unavailable")   # no 08:30 candle yet / its level is not below the entry / too small:
                                            # the order stays an ordinary session trade (stop unchanged)
    stop = _SM3.stop_adjust(ctx, sd, sw, i, p, entry, stop, tags)            # caption-gap setups_models #3/7: the A23 wick CE / eq_hunt stops
    stop = _EN.refine_stop(ctx, sd, sw, i, p, entry, stop, tags, lvx, lvt)   # A4 / A12 / E6d / E6f
    if p.stop_mode == "fixed" and p.stop_fixed_pts > 0:
        stop = entry - p.stop_fixed_pts * p.es_pt                            # caption-gap E8-new-trader-drill (042 ~00:32:11): a fixed stop (5 ES pts) under the final entry
        _ES3.hit("stop_fixed")
    if p.stop_old_low_body or p.stop_gap_edge or p.stop_htf_anchor or (p.stop_widen_new and p.trader_mode == "new"):
        stop = _ES3.stop_post(ctx, sd, sw, i, p, entry, stop, tags)          # caption-gap E6-old-low-rejection-body / E6-nwog-stop / E6-refined-stop-htf / E6-new-trader-wide-stops
    if p.gap_risk != "off":
        st_g = _ES2.gap_risk_adjust(ctx, sd, sw, i, p, entry, stop)          # caption-gap A6-voids-fill-holding-range (cc04_002 ~1:41): an unfilled gap under the entry in a consolidation
        if st_g is None:
            _f("x_gap_risk")
            return None
        stop = st_g
    if p.protect_macro_ext or p.london_ext_guard:
        stop = _SM7.stop_adjust7(ctx, sd, sw, i, p, entry, stop, tags, session)      # caption-gap setups_models #7/7: the protected macro extreme, the London-extreme stop cap
    risk = entry - stop
    if not (p.min_risk_pts * p.es_pt <= risk <= p.max_risk_pts * p.es_pt):
        _f("x_risk_too_small" if risk < p.min_risk_pts * p.es_pt else "x_risk_too_big")
        return None
    if p.max_stop_pts and risk > p.max_stop_pts * p.es_pt:
        _f("x_stop_too_wide")                        # caption-gap E5-stop-feasibility-at-entry-location (item 44, built for M11b): the structural stop is too wide for the risk budget - skip, the sweep stays alive
        sw["_wide_stop"] = True
        _SM2.hit("stop_too_wide")
        return None
    if not _EN.engage_ok(ctx, i, p):
        _f("x_engage_range")                                         # Ep08.17: wait for a range to form
        return None
    # setups_models review fix (T10 / M11a / M5.1): moc_run joins the run at 15:40, the IR entry
    # enters at once in the trend and the Ep 01 last hour buys in the PM run - the PO3 open filter
    # does not gate them unless synth_po3 (the first build's behaviour) [our interpretation]
    skip_po3 = bool(tags.pop("skip_po3", False))
    if p.use_bias and not skip_po3:      # T2 / D22 bias_open: the AM reference open
        refs = _BD.reference_opens(ctx, p, session, i)   # Ep08.3 "all": every open already printed (each only once its bar closed)
        mid_open = _open_known(ctx, "midnight", i)
        grade = "best"
        for ref_open in refs:
            if not (entry <= sd.x(ref_open) + p.eq_tol_pts * p.es_pt if p.po3_inclusive
                    else entry < sd.x(ref_open) + p.mo_tol_pts * p.es_pt):   # Ep04.4 / Ep04.6
                if (p.midnight_below_ok and mid_open is not None and ref_open == mid_open
                        and _BD.below_ok(ctx, p, sd, session, i)):
                    continue                 # Ep06.6: a confirmed bias side may enter on the far side of the MIDNIGHT open only (the other opens still bind)
                if p.open_tol_pts > 0 and _SM2.open_tol_ok(ctx, sd, sw, i, p, session, entry, ref_open):
                    grade = "allowed"        # caption-gap BH-B12-midnight-open-tolerance: inside the wrong-side tolerance after a Judas + MSS
                    continue
                _f("x_wrong_side_of_open")
                return None
        if p.open_tol_pts > 0 and refs:
            tags["open_grade"] = grade
    pd_hi = _EN.pd_high(sd, sw, i, leg_hi, p)         # L14b erl_range_swings
    leg_lo = _LD.leg_low(sd, sw, i, p, pd_hi)         # caption-gap A21 leg_anchor ("mss_leg": the sweep extreme, as before)
    if p.erl_range_swings and p.erl_range_update == "swing":      # caption-gap L14-dealing-range-redefine (cc04_002 ~5:59): the range low is the swing low that started the latest leg
        r_ = _TP1.current_range(sd, i, sw["ext_i"])
        if r_ is not None and r_[0] < pd_hi:
            leg_lo = r_[0]
        if r_ is not None and p.irl_entries and not (r_[0] <= entry <= r_[1]):      # IRL = the arrays INSIDE the referenced range: an entry outside the rolling range is not an IRL entry (153: 'enter on IRL, target ERL of the same range')
            _f("x_irl_outside_range")
            _TP1.hit("irl_outside_range")
            return None
    pd_top, pd_act = None, _ES1.pd_active(p)
    if pd_act:                                        # caption-gap A21-intraday-fib-bodies / A21-post-cisd-range-retrace / B5-prior-day-ny-range-retracement
        if p.leg_fib == "body":
            leg_lo, pd_hi = _ES1.body_leg(sd, sw, i)
        pd_top = _ES1.pd_top_fixed(sd, sw, i, p)
        if pd_top is not None:
            pd_hi = pd_top
    pd_line_ = leg_lo + p.leg_pd * (pd_hi - leg_lo)
    if pd_act:
        pd_line_ = _ES1.frame_line(ctx, sd, p, pd_line_)
    if not skip_leg_pd and p.leg_pd and p.leg_pd_at == "arm" and p.leg_pd_anchor != "target" and entry > pd_line_:
        _f("x_leg_premium")
        return None                                   # entry FVG not in the leg's discount
    if not skip_leg_pd and p.leg_pd_min and entry < leg_lo + p.leg_pd_min * (pd_hi - leg_lo) - 1e-9:
        _f("x_leg_too_deep")                          # D12: deeper than the 79% line of the leg
        return None
    if p.leg_depth_tag:
        lvt += _EN.leg_depth_tags(entry, leg_lo, pd_hi)
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
    ld_tags, ld_init = _LD.order_tags(ctx, sd, sw, i, p, entry)    # caption-gap pass tags (vb exhaustion, init FVG, wick tier, ...)
    lvt += ld_tags
    if p.engineered_pools and str(sw.get("key", "")).startswith("eng"):
        lvt.append("engineered")                       # caption-gap A3-engineered-liquidity (035 ~49:54): the sweep took an engineered pool
    rt_ = _LD3.round_tag(ctx, sd, sw, p)               # caption-gap A2-round-number-pool: a sweep at a round handle is tagged
    if rt_:
        lvt.append(rt_)
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
        if p.daily_level_needs_array == "fvg":          # caption-gap L2-sr-needs-fvg (058 ~13:34; 076 ~21:21): the array must be an FVG within a tick of the level
            if not _LD4.daily_fvg_ok(ctx, sd, sw, i, p):
                _f("x_daily_no_fvg")
                return None
        elif p.daily_level_needs_array and not (_htf_array(cf, p) if cf is not None else htf):
            _f("x_daily_no_array")
            return None
        if p.daily_level_needs_flow:     # cc09_005 ~03:12: plus HTF (daily) order flow its way
            fl = ctx.conf.trend(ctx.idx[i] + pd.Timedelta(minutes=ctx.tf), "D") if getattr(ctx, "conf", None) is not None else 0
            if fl != sd.sign:
                _f("x_daily_no_flow")
                return None
    rj_ = _LD4.order_gate(ctx, sd, sw, i, p, entry, cf, htf, lvt)      # caption-gap levels_detectors #3/3 gates / tags (week pools, trendline, wick LOD, LR zone, ...)
    if rj_:
        _f(rj_)
        return None
    rj_ = _SM2.order_gate(ctx, sd, sw, i, p, entry, stop, session, cf, htf, lvt, lvx, tags)     # caption-gap setups_models #1/7 gates / tags (open grade, PO3 order, narrative, pools, profiles, ...)
    if rj_:
        _f(rj_)
        return None
    rj_ = _SM2.order_gate2(ctx, sd, sw, i, p, entry, stop, session, lvt, lvx, tags)             # caption-gap setups_models #2/7 gates / tags (setup model, delivery, daily half, REH trap, two-rally, poke, states, IFVG narrative ...)
    if rj_:
        _f(rj_)
        return None
    rj_ = _SM3.order_gate3(ctx, sd, sw, i, p, entry, stop, session, lvt, lvx, tags)             # caption-gap setups_models #3/7 gates / tags (leg grade, near pool, REH fade, prior-range EQ, unfulfilled, breaker bias / taps, PM HTF target)
    if rj_:
        _f(rj_)
        return None
    if _SM4.any_gate4(p):
        rj_ = _SM4.order_gate4(ctx, sd, sw, i, p, entry, stop, session, lvt, lvx, tags)         # caption-gap setups_models #4/7 gates / tags (PO3 ideal, NWOG fill, OB at key, complete model, breaker low / counter, three drives, NWOG edge / ORG fill targets, gap count)
        if rj_:
            _f(rj_)
            return None
    if _SM5.any_gate5(p):
        rj_ = _SM5.order_gate5(ctx, sd, sw, i, p, entry, stop, session, lvt, lvx, tags)         # caption-gap setups_models #5/7 gates / tags (false flag, news two-sided, all pools, near miss, PD50 bodies, htf entry array, stop-zone pool, ...)
        if rj_:
            _f(rj_)
            return None
    if _SM6.any_gate6(p):
        rj_ = _SM6.order_gate6(ctx, sd, sw, i, p, entry, stop, session, lvt, lvx, tags)         # caption-gap setups_models #6/7 gates / tags (OTE parent range, OB below the open / fresh OB, symmetric swing, London range, 15m array, reversal catalogue, PDL expansion)
        if rj_:
            _f(rj_)
            return None
    if _SM7.any_gate7(p):
        rj_ = _SM7.order_gate7(ctx, sd, sw, i, p, entry, stop, session, lvt, lvx, tags)         # caption-gap setups_models #7/7 gates / tags (lc_rev htf, htf_converge, two-session SMT, PM nesting, consolidation exit, cc09 checklist, 09:50 tag, MOC direction, lunch program, last hour after target, split)
        if rj_:
            _f(rj_)
            return None
    if _ES1.any_gate_es1(p):
        rj_ = _ES1.order_gate_es1(ctx, sd, sw, i, p, entry, stop, session, lvt, lvx, tags)      # caption-gap entries_stops_sizing #1/3 tags / multipliers (HTF gap reaction depth, deep propulsion block)
        if rj_:
            _f(rj_)
            return None
    if _ES2.any_gate_es2(p):
        rj_ = _ES2.order_gate_es2(ctx, sd, sw, i, p, entry, stop, session, cf, htf, lvt, tags)       # caption-gap entries_stops_sizing #2/3 multipliers (rejection-block context)
        if rj_:
            _f(rj_)
            return None
    if fixed is None and tags.get("fixed4"):
        fixed = tags["fixed4"]                         # caption-gap setups_models #4/7: the ladder the setup names itself (AM-stops, NWOG CE, ORG fill, last-hour ORG)
    tags.pop("fixed4", None)
    extra5_ = tags.pop("extra5", None)                 # caption-gap setups_models #5/7: raw (level, kind) targets a gate adds (the false flag's flagpole origin)
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
            if p.bpr_limit == "mt_body_close_abort":
                lvx["bpr_abort"] = (z.mid, False)
            else:                        # caption-gap A11-bpr-retrace-allowance: the other tolerances (no re-entry / CE touch / MT warning, far-edge exit / far-edge trade-through)
                _ME1.mark_tags(tags, "bpr", (float(z.bottom), float(z.top), float(z.mid)))
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
    if p.no_lunch_retrace_hold and session == "PM" and _ME1.lunch_ext(ctx, sd, i, p):
        _ME1.mark_tags(tags, "lunch_ext")                  # caption-gap T9-strong-am-no-lunch-retrace: a PM entry in the AM direction after the lunch-high break keeps the last-hour window
    if p.thu_cap:
        why_thu = _ME1.thu_block(ctx, sd, i, p, session)      # caption-gap N10-thursday-caps-week: a Thursday NY-morning weekly extreme into a daily array
        if why_thu:
            _f(why_thu)
            return None
    if _ME3.order_on(p):
        why_me3 = _ME3.order_block(ctx, sd, sw, i, p, session, entry, tags)      # caption-gap management_exits #3/3: the abort's blocked side, the breakaway re-entry wait, the CC cut-off, the PM window
        if why_me3:
            _f(why_me3)
            return None
    if p.htf_bank or p.stall_at_htf or p.late_fvg_flip:
        why_me2 = _ME2.order_block(ctx, sd, i, p, session, entry)      # caption-gap management_exits #2/3: no counter entry inside a banked HTF array, the weekly reversal watch, no entry under the late-day gap
        if why_me2:
            _f(why_me2)
            return None
    above = max(leg_hi, entry)
    tp1 = {} if _TP1.any_on(p) else None             # caption-gap targets_partials #1/4: what the later stages of this order need
    tp2 = {} if _TP2.any_on(p) else None             # caption-gap targets_partials #2/4: ditto (the state of the _targets call is in ctx._tp2_st)
    ctx._tp2_session = session
    if tp2 is not None:
        ctx.__dict__["_tp2_st"] = dict(tags=[], prefs=[])
    tp3 = {} if _TP3.any_on(p) else None             # caption-gap targets_partials #3/4: the state of this order's rung hooks
    tp4 = {} if _TP4.any_on(p) else None             # caption-gap targets_partials #4/4: ditto (the raw rungs, the ladder stage, the mid-trade state)
    if tp3 is not None and p.pool_milestone > 0:
        why3_ = _TP3.sweep_gate(ctx, sd, sw, i, p, session)     # caption-gap X3-pool-below-untraded-htf-partial (061 ~02:19:41): no reversal off a pool that lies short of an untouched HTF array
        if why3_:
            _f(why3_)
            return None
    sp_ = ()                                          # N-opposing-fvg-speed-bump: the timeframes that are neither cap, bump nor target for this order
    tg = _TP.tgif_info(ctx, sd, i, p, entry) if p.tgif_zone else None     # M14.2 TGIF zone
    if tg is not None and tg["stand_down"]:
        _f("x_tgif_stand_down")                  # 40%+ of the weekly range retraced = reversal talk
        return None
    if tg is not None and p.tgif_need_draw and not _SM3.tgif_draw_ok(ctx, sd, i, p, session):
        _f("x_tgif_no_draw")                     # caption-gap M14-tgif-draw-hit-first-sd-depth (070 ~50:36): Friday has not traded to the named weekly draw
        return None
    if tg is not None and p.tgif_sd_exit:
        v_sd = _SM3.tgif_sd_level(ctx, sd, i, p, entry)
        if v_sd is not None:
            tg = dict(tg, levels=sorted([x for x in tg["levels"] if x < v_sd - p.es_pt] + [v_sd]))
            lvt.append("tgif_sd")
    if p.sick_sister and fixed is None:          # setups_models M16.2: the sick sister's own targets
        fixed = _SM.sick_sister(ctx, sd, i, p, session, entry)
        if fixed is None:
            return None
        if p.ss_ladder:
            tags["fracs"] = _SM3.ss_fracs(len(fixed), p)     # caption-gap M16-sick-sister-exit-ladder (053 ~6:21): the bulk exits at T1, the rest at the midpoint
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
        htf_t = _LD.htf_target_tfs(p, htf_t)    # caption-gap B10 topdown_targets: transposed 4h / D / W / M arrays (cc06_003 ~20:01)
        if p.speed_bump_tfs:
            sp_ = _TP1.speed_names(ctx, sd, p)  # caption-gap N-opposing-fvg-speed-bump (019 ~00:11:08): with the bias agreeing these opposing FVGs are no target
            htf_t = tuple(t_ for t_ in htf_t if t_ not in sp_)
        if htf_t and getattr(ctx, "conf", None) is not None:
            now = ctx.idx[i] + pd.Timedelta(minutes=ctx.tf)
            if _TP.needs_htf_rows(p):      # L9 / A22 / L14d: the same levels with the array filters applied
                lv = sorted(set(lv) | set(_TP.htf_levels(ctx, sd, i, above, p, htf_t)))
            else:
                real = _LD4.conf_targets(ctx, p, now, sd.x(above), sd.sign, htf_t, p.htf_far_edge)      # (caption-gap ipda_arrays: daily arrays of the IPDA window only)
                lv = sorted(set(lv) | {(sd.x(v), "array") for v in real})
        if p.fvg_targets and not (sp_ and ctx.tf in p.speed_bump_tfs):      # untouched opposing FVGs / voids: near edge, then CE (L9); the base timeframe as a speed bump is none
            extra = []
            for z in sd.opposing():
                if z.i <= i and z.bottom > above and h[z.i + 1:i + 1].max(initial=-np.inf) < z.bottom:
                    extra += [(z.bottom, "array"), (z.mid, "array")]
            lv = sorted(set(lv) | set(extra))
        if p.gap_tf_mode == "widen_up":    # caption-gap A5-mtf-gap-refinement (024 ~21:39): a target FVG overlapping an HTF FVG of the same move extends to the HTF far edge
            lv = sorted(set(lv) | set(_ES1.widen_targets(ctx, sd, i, above, p)))
        extra = _lv_finish_targets(ctx, sd, i, above, p, htf_t)    # levels_detectors arrays
        if p.ifvg_targets:
            extra = list(extra) + _SM5.ifvg_target_levels(ctx, sd, sw, i, p, above)     # caption-gap M10-ifvg-footholds-buy-program: the prior down leg's open SIBIs are the first buy-side targets
        if extra5_:
            extra = list(extra) + list(extra5_)
        extra = list(extra) + _SM2.extra_targets(ctx, sd, sw, i, p, session, entry)     # caption-gap setups_models #1/7: the leg low after compressed highs, the PM consolidation pools
        if p.org_two_rally:
            extra = list(extra) + _SM2.org_two_rally_targets(ctx, sd, i, p, entry)      # caption-gap L7-gap-up-premium-template: open -/+ 5 pts, then the prior close
        if p.daily_vi_targets or p.news_ce_target:                 # setups_models M1.1 / N6
            more = _SM.more_targets(ctx, sd, i, above, p)
            extra = list(extra) + more
        if extra:
            lv = sorted(set(lv) | set(extra))
            if p.compressed_hh:
                lv = _SM2.compressed_first(ctx, sd, sw, i, p, entry, lv)      # caption-gap BH-compressed-higher-highs: the leg low is the FIRST target
        if p.mm_targets or p.proj_breaker or p.sd_anchor in ("broken", "multi", "mss_leg"):
            rr_ = _mss_ref(ctx, sd, sw, i, p)
        lv = sorted(set(lv) | set(_TP.extra_sources(ctx, sd, i, p, sw, entry, risk, leg_hi, above, lv, lvt, rr_)))
        if p.wick_tfs:                     # A23 wick_tfs: the nearest two long 1h / 4h wick CEs are targets
            wk = sorted(w[0] for w in _TP.tf_wicks(ctx, sd, i, p, p.wick_tfs, above))[:2]
            lv = sorted(set(lv) | {(v, "wick") for v in wk})
        lv = _TP.refine(ctx, sd, i, p, lv, sw, entry, above, lvt)
        if p.org_reprice_full and "org_reprice" in lvt:
            rj_ = _SM5.org_reprice_gate(ctx, sd, sw, i, p, session, entry, tags)       # caption-gap M8-org-repricing-full-conditions: the stacked conditions of the ORG-first ladder
            if rj_:
                _f(rj_)
                return None
        if p.two_pass_state:           # caption-gap A5: efficient bands are no targets; a shield hides the arrays beyond it
            lv = _LD.drop_efficient(ctx, sd, i, p, lv)
        if p.daily_fvg_exact:          # review fix: the exact daily edge replaces its "array" twin
            lv = _drop_near_exact(lv, 0.25 * p.es_pt)
        if p.ob_targets_1m or p.target_ltf_obs:   # A12 / X1: untraded opposing order blocks of the session's bars
            lv = sorted(set(lv) | set(_EN.ob_target_levels(sd, i, above, p)))
        if tp1 is not None:            # caption-gap targets_partials #1/4: the NFP-day / NFP-week handling of the HTF rungs and the rungs the chunk adds (hook A)
            lv = _TP1.raw_post(ctx, sd, i, p, session, entry, risk, above, sw, lv, lvt, tp1)
        if tp2 is not None:            # caption-gap targets_partials #2/4: the HTF gap CE-first gate, the kept traded weekly FVG edges, the minimum-objective wick CEs
            lv = _TP2.raw_post(ctx, sd, i, p, session, entry, risk, above, sw, lv, lvt, tp2)
        if tp3 is not None and _TP3.raw_on(p):   # caption-gap targets_partials #3/4: void legs, measured-move anchors, OB-entry order, double tops, 60-day grades, cc extensions, ADR rungs, PM legs, the daily-breaker cap
            lv = _TP3.raw_post(ctx, sd, i, p, session, entry, risk, above, sw, leg_hi, lv, lvt, tags, tp3)
        if tp4 is not None and _TP4.raw_on(p):   # caption-gap targets_partials #4/4: the prior week's high, the multi-k breaker clusters, the PM lunch + AM highs, the balanced-level filter
            lv = _TP4.raw_post(ctx, sd, i, p, session, entry, risk, above, sw, leg_hi, lv, lvt, tags, tp4)
        if p.erl_exits_only:           # L14b: exit at external range liquidity only
            lv = [(v, k) for v, k in lv if k in POOL_KINDS]
        kinds = [kind for v, kind in lv]
        raw3_ = [v for v, kind in lv]
        lv = [_exit_px(v, kind, p) for v, kind in lv]
        if tp3 is not None and _TP3.exit_on(p):    # caption-gap targets_partials #3/4: at-edge / deep gap exits, the ADR buffer, the REH cluster
            lv = _TP3.exit_post(ctx, sd, i, p, entry, raw3_, kinds, lv, tp3)
    inner_ex = _TP.inner_extras(p, entry, risk, lv, kinds) if fixed is None else []   # X1 keep_inner_levels
    if p.round_step_pts:               # L17: targets rounded toward price (down for a long)
        pairs = sorted({(_round_px(ctx, sd, i, v, p, up=False), k) for v, k in zip(lv, kinds)})
        pairs = [(v, k) for v, k in pairs if v > entry]
        lv, kinds = [v for v, _ in pairs], [k for _, k in pairs]
    # owner #7 REVISED (Ep 02): an opposing HTF FVG between the entry and the target is a SPEED BUMP (a
    # partial at its near edge, the rest stays for the draw); "cap" / "split" keep the first build's cap
    capped, resist, capx, bumps = False, None, None, []
    if p.htf_resist_cap:
        rs_ = _TP.apply_resist(ctx, sd, i, p, entry, risk, lv, kinds, _f, sp_)
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
    if tp1 is not None and fixed is None:         # caption-gap targets_partials #1/4: the caps and gates (DXY, post-raid, OB location, LRLR zone, BPR) merge into the #7 cap (hook B)
        lv, kinds, cap1_ = _TP1.cap_gates(ctx, sd, i, p, session, entry, risk, above, lv, kinds, lvt, tp1, tags)
        if cap1_ is not None:
            capx = cap1_ if capx is None else min(capx, cap1_)
    if tp3 is not None and fixed is None and p.daily_breaker_cap:      # caption-gap new-swing-target-breaker-cap (cc06_004 ~00:29:06): the locked draw ends at the daily breaker's low too
        cap3_ = _TP3.cap_post(ctx, sd, i, p, above, tp3)
        if cap3_ is not None:
            cap3_ = float(_exit_px(cap3_, "array", p))
            capx = cap3_ if capx is None else min(capx, cap3_)
    eps = 1e-9 if fixed is not None else 0.0      # fixed R-multiple rungs: exactly 1R passes
    keep = [(v, k) for v, k in zip(lv, kinds) if v - entry >= p.min_rr * risk - eps]
    if p.mm_plan == "pyramid" and fixed is None:
        _, _, keep = _SM3.mm_plan_exit(p, keep, [], entry, risk, 0.0)      # caption-gap M1-three-entry-plans: the pyramid takes one rung per pool
    pools = [v for v, k in keep if k in POOL_KINDS]
    lk = getattr(ctx, "cur_lock", None) if p.draw_lock == "session" else None
    lk_t = lk if fixed is None else None       # fixed-target setups: the lock gates the side only
    final_T = lock_capped = False
    keep0 = keep
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
        if tp1 is not None:                       # caption-gap N1-nfp-no-htf-hold / A11-bpr-clear-for-htf-targets: an HTF draw on a jobs day / beyond an uncleared BPR ends in front of it
            nt_, why_ = _TP1.lock_adjust(ctx, sd, i, p, tp1, tv, keep, entry)
            if why_:
                _f(why_)
                return None
            if nt_ is not None and nt_ < T:
                T, kT, lock_capped = nt_, "array", True
                lvt.append("tp1_lock_capped")
        if capx is not None and T > capx:
            # owner #7 x #9: the draw's exit must be on the near side of the cap - an unbroken
            # opposing HTF FVG before the draw ends the trade in front of it [our interpretation;
            # OWNER QUESTION: or lock only near-side draws, draw_lock_near_cap=True]. Tagged
            # lock_capped so the share of trades whose locked draw was replaced is reported.
            T, kT, lock_capped = capx, "array", True
            _f("x_lock_capped")
        if (p.min_draw_pts and _TP2.room(ctx, sd, i, p, entry, above, T) < p.min_draw_pts * p.es_pt) or T - entry < p.min_rr * risk:     # (caption-gap L15-room-measure-anchors: room_ref)
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
            if lk.get("ext_from") is not None:           # B2 draw_ext_target: the pool the run passes on its way to the array is a rung
                x = _exit_px(sd.x(lk["ext_from"]), "pool", p)
                if entry + p.min_rr * risk <= x < T - p.es_pt and not any(abs(x - r_[0]) <= p.es_pt for r_ in rungs):
                    rungs.append((x, "pool"))
            rungs += [(b, "bump") for b in bumps if entry + p.min_rr * risk <= b < T - p.es_pt
                      and not any(abs(b - r_[0]) <= p.es_pt for r_ in rungs)]       # owner #7: the speed bump
            if tp1 is not None:                  # caption-gap targets_partials #1/4: the EQ rung / the old-high ladder / the LRLR highs are partials of a locked draw too
                for v_, kd_ in tp1.get("lock_rungs", []):
                    x_ = _exit_px(v_, kd_, p)
                    if entry + p.min_rr * risk <= x_ < T - p.es_pt and not any(abs(x_ - r_[0]) <= p.es_pt for r_ in rungs):
                        rungs.append((x_, kd_))
            rungs = sorted(set(rungs))
        else:
            rungs = [(v, k) for v, k in keep if v < T - p.es_pt]
        keep = rungs + [(T, kT)]
        if tags.get("expansion"):      # caption-gap M1-inside-fvg-expansion-only (009 ~3:49): the bulk at the locked level, the rest at the next level
            nx_ = [(v, k) for v, k in keep0 if v > T + p.es_pt][:1]
            keep = [(T, kT)] + nx_
            tags["fracs"] = (p.expansion_bulk, 1.0 - p.expansion_bulk) if nx_ else (1.0,)
        draw, final_T = T, True
    else:
        if p.t1_skip_near and p.min_draw_pts and fixed is None and pools:       # caption-gap L15-first-sth-offering-5 (012 ~00:32:07): pools nearer than min_draw_pts are skipped, not trade-killers
            keep, ok_ = _TP2.skip_near(keep, entry, p)
            if not ok_:
                _f("x_room_lt_min")
                return None
            pools = [v for v, k in keep if k in POOL_KINDS]
        keep_full = list(keep)
        if not keep:
            _f("x_no_target_1R")
            return None
        if ct_pool_ and not pools:       # caption-gap BH-B3-counter-bias-modes: the counter-bias scalp aims at the nearest sell-side pool only
            _f("x_bh1_ct_no_pool")
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
            if tp2 is not None:        # caption-gap targets_partials #2/4: the NWOG magnet / range anchor, the HTF OB open, the projection clusters
                prefs += _TP2.draw_prefs(ctx, sd, i, entry, p, session, keep)
            prefs = sorted(x for x in prefs if x[0] - entry >= p.min_rr * risk)
            if prefs:
                draw, kd, nm = prefs[0]
                keep = [(v, k) for v, k in keep if v < draw - p.es_pt] + [(draw, kd)]
                lvt.append("draw_" + nm)
                if p.session_pool_first:   # caption-gap L4-session-pool-before-rel (067 ~00:50:27): the nearer session-range pool is the draw, the rel-eq pool the next rung
                    sf_ = _TP2.session_first(ctx, sd, i, p, entry, risk, keep_full, draw)
                    if sf_ is not None:
                        keep, draw = sf_
                        lvt.append("session_pool_first")
        if p.min_draw_pts and _TP2.room(ctx, sd, i, p, entry, above, draw) < p.min_draw_pts * p.es_pt:
            _f("x_room_lt_min")
            return None                                   # not enough room to the draw (minimum)
    if tp2 is not None and fixed is None and keep:      # caption-gap targets_partials #2/4: resistance runs, the ORG family, the NWOG ladder, the final-target picks, the minimum objective
        why2_, keep, draw, final_T = _TP2.late(ctx, sd, sw, i, p, session, entry, risk, keep, keep0 if lk_t is not None else keep_full, draw, final_T, lvt, tags, tp2,
                                               ("draw_org_far" in lvt) or (lk_t is not None and lk_t.get("name") == "org_far"), lk_t is not None, leg_hi)
        if why2_:
            _f(why2_)
            return None
    if p.mm_plan in ("full", "mss_scalp") and fixed is None:      # caption-gap M1-three-entry-plans (003 ~1:28:27): one exit - at the draw / at the first relative equal highs
        se_, draw, _ = _SM3.mm_plan_exit(p, keep, eq_hi, entry, risk, draw)
        if se_:
            tags["single_exit"] = True
    if not _SM.unengaged_ok(ctx, sd, i, p, session, draw):   # setups_models Ep01.13
        _f("x_lh_engaged")
        return None
    if tp1 is not None:                # caption-gap targets_partials #1/4: eve of a release, the NWOG reversion scalp, resistance class / filter, the high-resistance skip, the swing grade
        why_, risk_mult, one_ = _TP1.late(ctx, sd, i, p, session, entry, risk, tags, lvt, [v for v, _ in keep], [k for _, k in keep], draw, tp1, risk_mult,
                                          (sw["ext"], leg_hi))
        if why_:
            _f(why_)
            return None
        if one_ is not None and not tags.get("single_exit"):
            keep, draw, final_T = [one_], one_[0], False
            tags["single_exit"] = True
    if tp3 is not None and keep:       # caption-gap targets_partials #3/4: final picks, weekly beyond, milestone, ladder presets / modes, fixed partials, no-collapse, energy split, deep runner, minimum final reward
        why3_, keep, draw, final_T = _TP3.late(ctx, sd, sw, i, p, session, entry, risk, keep, keep0 if lk_t is not None else keep_full, draw, final_T, lvt, tags, tp3, lk_t is not None, fixed)
        if why3_:
            _f(why3_)
            return None
    if tp4 is not None and keep and _TP4.late_on(p):      # caption-gap targets_partials #4/4: month gate, PM 14:50 ladder, structural cuts, ladder shapes, modifiers, minimum final reward
        why4_, keep, draw, final_T = _TP4.late(ctx, sd, sw, i, p, session, entry, risk, keep, keep0 if lk_t is not None else keep_full, draw, final_T, lvt, tags, tp4, lk_t is not None, fixed, float(leg_hi), tg)
        if why4_:
            _f(why4_)
            return None
    lv, kinds = [v for v, _ in keep], [k for _, k in keep]
    if p.t1_fixed_pts > 0 or p.t1_fixed_r > 0:             # Ep03.24 test (owner #2: not the goal, default off); caption-gap E8-2pct-new-trader: t1_fixed_r = a fixed R multiple (the cc_starter single exit at 1R)
        f = entry + (p.t1_fixed_r * risk if p.t1_fixed_r > 0 else p.t1_fixed_pts * p.es_pt)
        if p.t1_fixed_all:
            lv, kinds = [min(f, lv[0])], [kinds[0]]
        elif f < lv[0] - p.es_pt and f - entry >= p.min_rr * risk:
            lv, kinds = [f] + lv, ["fixed"] + kinds
    scalp = False
    sl = getattr(ctx, "cur_sloppy", "")
    dws = _DW.scalp_now(ctx, p, session, i, sd.sign)           # day_week_context: inside week, low-vol day, S&D, ... (caption-gap bias_htf#1/7: the side for the dxy / lean reasons)
    if dws:
        lvt.append("scalp_" + dws)
    if (sl and p.sloppy_mode == "scalp") or _NC.scalp_now(ctx, p, session) or dws:   # #10 scalp mode (N3.3: the FOMC-only AM):
                                          # one exit at min(+5, T1), no adds
        _dsc = getattr(getattr(ctx, "dplan", None), "scalp", {})
        if "august_light" in _dsc and not (sl and p.sloppy_mode == "scalp"):       # N7-august "light": a single exit AT the first target (no +5 cap)
            _cap = lv[0]
        elif dws.startswith("bh1_") and _BH1E.scalp_cap(ctx, sd, i, p, dws, entry, lv[0]) is not None:
            _cap = _BH1E.scalp_cap(ctx, sd, i, p, dws, entry, lv[0])      # caption-gap bias_htf#1/7: drange_t1_pts / the opposite ORG edge
        elif dws.startswith("bh2_") and _BH2E.scalp_cap(ctx, sd, i, p, dws, entry, lv[0]) is not None:
            _cap = _BH2E.scalp_cap(ctx, sd, i, p, dws, entry, lv[0])      # caption-gap bias_htf#2/7: the single range target (range_no_bias)
        else:
            _cap = min(entry + (p.chop_scalp_pts if (p.chop_scalp_pts > 0 and sl and p.sloppy_mode == "scalp") else (p.fri_t1_pts if (dws == "fri_one_sided" or "fri_one_sided" in _dsc) else p.sloppy_scalp_pts)) * p.es_pt, lv[0])
        lv, kinds, scalp, final_T = [_cap], [kinds[0]], True, False
    smt_n = int(sw["smt"] is True) + int(sw.get("smt2") is True)
    if smt_n < p.smt_min:
        _f("x_no_smt")
        return None
    risk_mult *= _EN.size_mult(ctx, sd, sw, i, p, session, entry, htf, getattr(ctx, "cur_sloppy", ""), lvt)   # E9
    risk_mult *= float(tags.pop("es1_mult", 1.0))        # caption-gap entries_stops_sizing #1/3: HTF gap reaction depth / deep propulsion block
    risk_mult *= float(tags.pop("es2_mult", 1.0))        # caption-gap entries_stops_sizing #2/3: rejection-block context
    if tags.get("day_auto"):
        risk_mult *= p.day_mode_size                      # caption-gap X5-day-trade-stop-no-trail: a day-mode order is smaller than the session size
    x3_ = 0.0
    if p.class_risk or p.htf_near_risk_pct > 0 or p.deep_run_mult != 1.0 or p.freq_ref > 0:
        m3_, x3_ = _ES3.order_risk(ctx, sd, sw, i, p, entry, risk, scalp, draw, tags, lvt)        # caption-gap E8-risk-by-trade-class / E8-E9-5pct-near-htf / E9-deep-discount-reduced / E9-frequency-small-size
        risk_mult *= m3_
    rungs = []
    lad = tags.pop("ladder", None)                  # E2 / D11 ladder: FVG high, 75%, CE (one order, later rungs)
    xcap = p.size_up_cap_pct * ctx.equity if (p.size_up_cap_pct and any(x.startswith("size_up_") for x in lvt)) else 0.0
    xcap += x3_ * ctx.equity                         # caption-gap E8-E9-5pct-near-htf: the near-HTF total-risk cap
    plan = None                                     # the planned full size (all ladder rungs together)
    lad_fr = tags.pop("ladder_fracs", None)         # caption-gap E12-070-rung-order: the advanced breaker's own rung sizes
    if lad and not stop_cc and all(px > stop for px in lad):    # a stop-cc order is one stop: no ladder
        fr = lad_fr or p.entry_ladder_fracs
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
    er_ = tags.pop("es3_rung", None)
    if er_ is not None and p.ifvg_mohawk_add and not rungs and not stop_cc:
        mr_ = _ES3.mohawk_rung(shares, er_, stop, shares * (entry - stop), p, ctx.equity)     # caption-gap E12-mohawk-add-ifvg: the smaller resting add beyond the IFVG far edge
        if mr_ is not None:
            rungs = [mr_]
            _ES3.hit("ifvg_mohawk_add")
    if tags.pop("zone_ladder", False):
        _ES2.tag(tags, add_base=int(shares))             # caption-gap E12-in-zone-larger-second: later adds are sized from the first leg (1x)
    _f("4_order")
    t = ctx.t[i]
    lh = p.last_hour[0] <= t < p.last_hour[1]
    setup = "am_mm" if session == "AM" else session.lower() if session != "PM" else (
        "pm_last_hour" if lh else "pm_sb" if 840 <= t < 900 else "pm")
    if tags.pop("tp3_ladder", False) or final_T or fixed is not None:      # (caption-gap targets_partials #3/4: a ladder with its own fractions keeps every rung)
        levels = lv
    else:
        levels = lv[:max(1, len(p.ladder_fracs))]
    _SM2.late_tags(ctx, sd, sw, i, p, session, entry, lv, tags)     # caption-gap setups_models #1/7: clean swing / array depth / move tags (D15 picks)
    rp = None                                       # targets_partials: the rung plan (None = the old ladder)
    if (fixed is None and not scalp and not p.t1_fixed_all and not tags.get("fracs") and not tags.get("single_exit")
            and not (p.moc_pool_exit and session == "PM" and p.last_hour[0] <= t < p.last_hour[1])
            and not (p.friday_first_pool and ctx.day.weekday() == 4)):
        extras_ = list(inner_ex) + list(tags.pop("tp2_extras", []))        # (caption-gap L10-intraday-wick-ce: the minimum-objective wick CE is a protected partial)
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
                 ext=sw["ext"], ext_i=sw["ext_i"], broke=sw.get("broke"),     # (caption-gap BH-N10-thursday-not-top-call: the MSS bar, read by dwc1.order_ok)
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
    elif p.entry_order == "market_on_touch":
        order["mot" if p.mot_next_open else "touch"] = True      # caption-gap E1-market-on-touch (089 ~00:04:20): the first touch fills at market (the next open) / at the level
        _ES2.hit("mot_order")
    order.update(tags)
    lvt += _LD4.late_tags(ctx, sd, p, entry, lv)         # caption-gap m_ohlc / expansion
    order["lv_tags"] = "|".join(dict.fromkeys(lvt))
    order["lvx"] = lvx
    if rp is not None:                           # targets_partials: rungs resolved again at the fill (the day's split)
        order.update(rung_plan=rp["rungs"], fracs_fixed=rp["fracs_fixed"], run_local=rp["run_local"],
                     final_T=rp["final_T"], bulk=bool(p.target_order))
        lv_o, kd_o, _ = _TP.fill_plan(order, p.ladder_fracs, p)
        order.update(levels=lv_o, level_kinds=kd_o, t1=lv_o[0],
                     t2=(lv_o[-1] if rp["final_T"] and len(lv_o) > 1 else lv_o[1] if len(lv_o) > 1 else None))
    # setups_models order plumbing (run_day): the draw, the displacement leg, the MSS bar
    order.update(draw=draw, leg=(float(sw["ext"] if p.leg_fib == "wick" else leg_lo), float(pd_hi)), broke=sw.get("broke"), init_fvg=ld_init)
    if p.leg_anchor != "mss_leg" or p.leg_fib == "body" or (p.erl_range_swings and p.erl_range_update == "swing"):
        order["leg_lo"] = float(leg_lo)                  # A21 energetic anchor / body fib: the fill-time leg_pd check reads it
    if pd_top is not None:
        order["pd_top"] = float(pd_top)                  # caption-gap A21-post-cisd-range-retrace: the fixed top of the dealing range
    if p.leg_pd_anchor == "target" and p.leg_pd and not tags.get("no_leg_wait"):
        t_pd = float(draw) if (order.get("single_exit") and draw is not None) else float(order["t1"])      # caption-gap A21-implied-range-to-target (025 ~41:59): the implied range = the sweep extreme .. the stated draw (the first ladder target; review fix: the draw when a single_exit replaces t1)
        if t_pd > leg_lo + 1e-9:
            ln_pd = _ES1.frame_line(ctx, sd, p, leg_lo + p.leg_pd * (t_pd - leg_lo))
            if not skip_leg_pd and p.leg_pd_at == "arm" and entry > ln_pd:
                _f("x_leg_premium")
                return None
            order["pd_top"] = t_pd
            order["leg"] = (float(leg_lo), t_pd)
            _ES1.hit("pd_target")
    if order.pop("single_exit", False):          # M5.1: one exit at the draw
        order.update(levels=[draw], level_kinds=[kinds[-1] if kinds else "array"], t1=draw, t2=None,
                     fracs=(1.0,))
    if p.ir_accel_hold and tags.get("entry_kind") == "ir" and not scalp and "single_exit" not in tags:
        r_ir = _SM3.ir_rungs(ctx, sd, i, p, entry, order["levels"], order["level_kinds"])
        if r_ir is not None:
            order.update(levels=r_ir[0], level_kinds=r_ir[1], t1=r_ir[0][0], t2=r_ir[0][1] if len(r_ir[0]) > 1 else None, final_T=False,
                         fracs=(0.5, 0.5) if len(r_ir[0]) > 1 else (1.0,))
            _SM2.hit("ir_accel")
    lh_ = session == "PM" and p.last_hour[0] <= t < p.last_hour[1]
    if p.moc_pool_exit and lh_:                  # T10: everything off at the first pool
        js = [k for k, kd in enumerate(order["level_kinds"]) if kd in POOL_KINDS]
        if js:
            order["levels"] = order["levels"][:js[0] + 1]
            order["level_kinds"] = order["level_kinds"][:js[0] + 1]
            order["final_T"] = False
    if p.friday_first_pool and ctx.day.weekday() == 4:   # N10 (070 ~1:06:37): Friday takes everything at the first pool
        js = [k for k, kd in enumerate(order["level_kinds"]) if kd in POOL_KINDS]
        if js:
            order["levels"] = order["levels"][:js[0] + 1]
            order["level_kinds"] = order["level_kinds"][:js[0] + 1]
            order["final_T"] = False
            order["lv_tags"] = "|".join(x for x in (order.get("lv_tags", ""), "friday_first_pool") if x)
    if p.pm_last_hour_model and lh_ and "cut" not in order:
        order["cut"] = _SM.lh_window(p)[1]       # M5: the owner #1 window end (15:50; strict 15:45)
    if p.po3_runner:
        order["runner"] = True                   # Ep04.3: the last fraction rides to the close
    if tp2 is not None and tp2.get("runner") is not None and not order.get("scalp") and not order.get("runner") and order.get("htf_runner") is None:
        order["htf_runner"] = tp2["runner"]      # caption-gap L7-org-partial-close-orderflow / L7-org-breaker-inside: the ORG far edge stays a runner slice
    if tp1 is not None:                          # caption-gap targets_partials #1/4: the speed-bump timeframes of the live cap, the held HTF-range slice
        if sp_:
            order["tp1_speed"] = sp_
        if p.htf_range_runner and not order.get("scalp") and not order.get("runner"):
            rn_ = _TP1.runner(ctx, sd, i, p, session, entry, order["levels"])
            if rn_ is not None:
                order["htf_runner"] = rn_
    if _SM7.any_late7(p):
        rj_ = _SM7.late7(ctx, sd, sw, i, p, order, tags, session)     # caption-gap setups_models #7/7: the London-extreme target check, the pairing state, the position-loop flags
        if rj_:
            _f(rj_)
            return None
    if p.clarity != "off":
        rj_ = _SM6.late6(ctx, sd, sw, i, p, order, tags)      # caption-gap new-clarity-filter-pass-if-arguing: a marginal entry gap / a path of overlapping candles
        if rj_:
            _f(rj_)
            return None
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
    if p is not None and p.smt_mode == "three_point":
        return _smt_qual(ctx, sd, i, p, _SM2.three_point_smt(ctx, sd, i, pctx, ps, j, p))     # caption-gap B18-smt-three-point-swing: low - lower low - higher low vs low - lower low - lower low
    if p is not None and p.smt_pm_points and session == "PM":
        return _smt_qual(ctx, sd, i, p, _SM2.pm_points(ctx, sd, i, pctx, ps, j))     # caption-gap B18-pm-smt-reference-points: lunch-hour low vs the first low after 13:00
    if p is not None and p.smt_ref_window and not _SM2.smt_ref_ok(ctx, sd, i, key, level, p):
        return None                                      # caption-gap B18-am-smt-window-points: the compared extreme is outside [smt_win_a, smt_win_b]
    if key.startswith("rel_eq") and p is not None and p.smt_rel_eq:   # B18.1 rel-eq partner twin
        return _smt_qual(ctx, sd, i, p, _smt_rel_eq(ctx, sd, i, level, pctx, ps, j, p))
    if key.startswith(("rel_eq", "round", "swing_low")):
        return None
    # review fix: p passed, so the partner gets the levels_detectors keys too (ipda*, today_low, m3l,
    # prev_am, org*, gap_*, or_alt ...) - _extra_levels ran on pctx; a key the partner lacks -> None
    plv = _sell_side(pctx, ps, session, j, True, p).get(key)
    if plv is None:
        return None
    if p is not None and p.smt_ref_window and not _SM2.smt_ref_ok(pctx, ps, j, key, plv, p):
        return None                                      # (the partner's twin extreme too)
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
from . import nct2 as _NCT  # noqa: E402  (caption-gap pass, news_calendar_times#1/1: engine glue)
from . import dwc1 as _DWC  # noqa: E402  (caption-gap pass, day_week_context#1/3: engine glue)
from . import dwc2 as _DWC2  # noqa: E402  (caption-gap pass, day_week_context#2/3: engine glue)
from . import dwc3 as _DWC3  # noqa: E402  (caption-gap pass, day_week_context#3/3: engine glue)
INDEX_SYMBOLS = _DWC3.INDEX_SYMBOLS   # OT-stocks-swing-only: the labels that are not individual stocks (the spec lists eight; the set is wider - owner question)
from . import setups as _SM   # noqa: E402  (setups_models package; imports this module back)
from . import entries as _EN  # noqa: E402  (entries_stops_sizing package; imports this module back)
from . import targets as _TP  # noqa: E402  (targets_partials package: speed bump, rung plan, partials)
from . import manage as _MG  # noqa: E402  (management_exits package: exits, stops, re-entry)
from . import ld2 as _LD  # noqa: E402  (caption-gap pass, levels_detectors #1/3: engine glue)
from . import ld3 as _LD3  # noqa: E402  (caption-gap pass, levels_detectors #2/3: engine glue)
from . import ld4 as _LD4  # noqa: E402  (caption-gap pass, levels_detectors #3/3: engine glue)
from . import sm2 as _SM2  # noqa: E402  (caption-gap pass, setups_models: engine glue)
from . import sm3 as _SM3  # noqa: E402  (caption-gap pass, setups_models #3/7: engine glue)
from . import sm4 as _SM4  # noqa: E402  (caption-gap pass, setups_models #4/7: engine glue)
from . import sm5 as _SM5  # noqa: E402  (caption-gap pass, setups_models #5/7: engine glue)
from . import sm6 as _SM6  # noqa: E402  (caption-gap pass, setups_models #6/7: engine glue)
from . import sm7 as _SM7  # noqa: E402  (caption-gap pass, setups_models #7/7: engine glue)
from . import es1 as _ES1  # noqa: E402  (caption-gap pass, entries_stops_sizing #1/3: engine glue)
from . import es2 as _ES2  # noqa: E402  (caption-gap pass, entries_stops_sizing #2/3: engine glue)
from . import es3 as _ES3  # noqa: E402  (caption-gap pass, entries_stops_sizing #3/3: engine glue)
from . import tp1 as _TP1  # noqa: E402  (caption-gap pass, targets_partials #1/4: engine glue)
from . import tp2 as _TP2  # noqa: E402  (caption-gap pass, targets_partials #2/4: engine glue)
from . import tp3 as _TP3  # noqa: E402  (caption-gap pass, targets_partials #3/4: engine glue)
from . import me1 as _ME1  # noqa: E402  (caption-gap pass, management_exits #1/3: engine glue)
from . import me2 as _ME2  # noqa: E402  (caption-gap pass, management_exits #2/3: engine glue)
from . import me3 as _ME3  # noqa: E402  (caption-gap pass, management_exits #3/3: engine glue)
from . import tp4 as _TP4  # noqa: E402  (caption-gap pass, targets_partials #4/4: engine glue)
from . import bh1e as _BH1E  # noqa: E402  (caption-gap pass, bias_htf#1/7: engine glue)
from . import bh2e as _BH2E  # noqa: E402  (caption-gap pass, bias_htf#2/7: engine glue)
from . import bh3e as _BH3E  # noqa: E402  (caption-gap pass, bias_htf#3/7: engine glue)
