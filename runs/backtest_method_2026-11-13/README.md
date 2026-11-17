# How to backtest the engine: recommendation (2026-11-13)

Question from Mase: are we backtesting different switch combinations? **No.** Every screen so far changed one switch at a
time (2021 card screen, weekly-rule screen in PR #67), plus one two-switch run (week rule + AM / PM Silver Bullet off).
This note says how to add combinations without fooling ourselves. Nothing here changes the engine or a default, and no
backtest was run for it; the numbers come from the saved trade files of PR #67 (`noise.py`, `noise_output.txt`).

## 1. What the current results can and cannot tell us

ES 5m, fixed-roll data, $1k risk, 2019-26:

| variant | trades | total $ | $ / trade | t-stat | 90% range of the total |
|---|---|---|---|---|---|
| defaults | 166 | -490 | -3 | -0.06 | -13.5k to +12.8k |
| week rule high/low only (wd_pwhl) | 338 | +4,441 | +13 | 0.37 | -13.6k to +23.3k |
| same, AM + PM SB off (pwhl_x) | 276 | +7,441 | +27 | 0.62 | -9.8k to +25.4k |
| week rule off, AM + PM SB off (off_x) | 664 | +10,213 | +15 | 0.59 | -16.5k to +38.0k |

- One trade swings about $650 (sd), so 300 trades have a chance range of roughly +/- $18k. Every result we have,
  including the best one, sits inside that range. A t-stat of 2 is the usual bar; the best we have is 0.6.
- Random-filter test: take the "week rule off" trades, keep random days until the trade count matches the high/low-only
  rule. 27% of random filters do as well as the real rule (35% with AM / PM SB off). The weekly rule is not yet shown to
  beat a coin-flip filter.
- At $27 a trade it would take roughly 2,500 trades to reach t = 2. We have 276. **Trade count is the limit, not compute.**
- Costs: the engine charges 0.10 pt per side (about $16 a trade here). At 2x costs pwhl_x falls to +$2.9k and off_x to
  -$0.7k; at 3x both lose. Real ES costs (commission plus a tick of slippage on stop exits) are likely between 1x and 2x, so 2x is the stress case.
- The 2023-26 "check" half has now been looked at for every variant, so it is no longer a clean check.

## 2. Why not search all combinations

The engine has about 1,900 switches (68 cards). Pairs alone are 1.8 million; at 3 min per variant-year that is not
runnable, and it would not help: the best of N noise results looks good by chance. With 72 variants the luckiest one is
expected to be about 2.4 sd above the truth, which on a 300-trade total is roughly $25k of pure luck. A blind
grid or optimizer would hand us that luck as a "winner".

## 3. Recommended method

1. **One harness, one report.** Turn `funnel_x.py` into the standard runner: pinned commit, per-year trade files cached,
   setup on/off as a proper switch, and a report that always prints trades, $ by half and by year, max drawdown, t-stat,
   bootstrap range, result at 2x costs, and the running count of variants tried so far.
2. **Raise the trade count first.** Run the same variant on ES, NQ and YM (data is there, rolls fixed) and report the
   three together and apart. That roughly triples trades and is a check on a second market for free. Screen on a
   baseline that trades (week rule off or high/low only); on the 166-trade defaults 43 of 72 switches changed nothing.
3. **Filters: test combinations for free from one run.** Switches that only remove trades (week rule, setups on/off,
   lunch, day of week, news days) can be combined in pandas from one "everything on" trade file in seconds, with the
   random-filter test as the bar. Confirm the short list with real runs (the one time we compared, post hoc said 281
   trades / +$6.6k and the real run 276 / +$7.4k).
4. **Entry / stop / target switches: screen singly, then combine only a short list.** Single-switch screen on all of
   2019-22 (not one year). Keep at most 6-8 switches that move the result by more than about 2 sd of the paired
   difference and have an ICT source for why. Run those as a full grid (6 switches = 64 combinations).
5. **Pick with a rule written down before the run:** best 2019-22 total among combinations with at least 200 trades,
   up in at least 3 of 4 years, and whose one-switch-away neighbours are also positive (a plateau, not a spike).
6. **Check once.** That one pick gets a single 2023-26 run, then NQ / YM, 1m entries and 2x costs. Also report a
   walk-forward table (choose on 2019-21, trade 2022; choose on 2019-22, trade 2023; and so on). It needs no new runs.
7. **Paper trade the survivor.** It is the only clean test left, since 2023-26 has been seen.

## 4. What it costs to run

5m is about 3 min per variant-year; laptop and cloud each have 4 cores.

| step | jobs | time |
|---|---|---|
| harness + filter combinations from existing trade files | none new | build only |
| ES + NQ + YM for the 4 baselines above, 8 years | about 100 | about 1.5 h on the laptop |
| single-switch screen, 72 cards, 2019-22 | 288 | about 3.5 h laptop, 2 h if split with cloud |
| grid of the top 6, 2019-22 | 256 | about 3 h |
| final check (2023-26, NQ / YM, 1m, 2x costs) | under 40 | 1-2 h |

As far as I can tell the cloud copy of the data still has the old late rolls; the 93 roll files need copying over before cloud shards match
the laptop.

## 5. Decisions for Mase

1. OK to build the harness and do the free filter-combination pass (no long runs)?
2. OK to run the ES + NQ + YM baselines (about 1.5 h laptop)?
3. Hold the weekly-rule default choice until those are in? The evidence so far does not separate the readings.
