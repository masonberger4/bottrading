# Trades stopped out in their entry bar: audit (2026-11-16)

Mase asked (2026-11-16) to check whether the many trades stopped inside their own entry bar are a fill / stop-ordering
bug. Results only: no engine code or default was changed.

**Answer: not a bug. The stops are real, and they come from stops that are smaller than one normal 5-minute bar.**

Data: the saved week-rule-off trades (`wd_off`, engine 2101d04, ES + NQ + YM, 2019-26, 2,897 trades) from
`/mnt/project-files/mentorship/runs/bt_base_2026-11-13/trades_and_skips.tgz`, replayed against the raw Databento
1-minute bars. `check.py` reproduces everything here; `output.txt` is its printout; `same_bar_all.csv` has every
checked trade with its five 1-minute extremes.

## 1. How many

528 of 2,897 trades (18%) are stopped in the bar they entered. By setup: AM 46%, PM 48%, last hour 40%,
PM Silver Bullet 30%, lunch 4%. Nearly all of it is one entry type: the pre-break order-block limit (`ob_pre`, the
default for AM / PM / last hour / PM Silver Bullet), where 38% of 1,126 trades stop in the entry bar. Lunch uses a
different entry and is at 4%.

## 2. Hand check against 1-minute bars

- 489 of 490 checkable trades are confirmed: the limit trades through first, and the stop is reached in the same
  or a later minute of that 5-minute bar. For a limit entry the stop is always on the far side of the entry, so
  price has to pass the entry before it can reach the stop. There is no ordering guess to get wrong.
- No trade fills on the bar its order was armed on (0 of 2,897), so there is no look-ahead in the fill.
- 79% fill in the first minute of the entry bar, and 42% are stopped within that same minute.
- Only 1 stop in 528 is an exact touch, so the "stop on touch" rule is not driving it.
- 38 trades could not be checked because the trade row's prices are in a different price frame from the raw file:
  roll weeks (the engine's fixed roll holds a different contract) and the `venom` / `ndog_scalp` rows, whose prices
  look back-adjusted rather than contract prices. One more (NQ 2020-12-14, a roll week) did not reach its stop in the
  raw file. Worth a separate look, but it is small.

20 of the confirmed trades (random, seed 7):

| market | setup | side | entry bar (NY) | limit | stop | risk (ticks) | bar open | 1m lows (long) / highs (short) | filled in min | stopped in min |
|---|---|---|---|---|---|---|---|---|---|---|
| ES | am_mm | short | 2021-10-19 09:45 | 4493 | 4494 | 4 | 4490 | 4491.5 4492.25 4494.5 4495.75 4491.75 | 3 | 3 |
| ES | lunch | short | 2022-12-20 11:55 | 3847.25 | 3848.25 | 4 | 3845 | 3845 3844.5 3847.25 3848 3851 | 4 | 5 |
| ES | pm_sb | long | 2024-12-12 14:15 | 6072 | 6070.5 | 6 | 6072.25 | 6071.5 6069.75 6070 6070 6070.25 | 1 | 2 |
| ES | lunch | long | 2026-05-07 12:10 | 7375.5 | 7374.5 | 4 | 7381.75 | 7378.5 7377 7374.25 7374.25 7374.75 | 3 | 3 |
| ES | am_mm | short | 2026-07-13 10:10 | 7599.5 | 7602.5 | 12 | 7599 | 7602.25 7603.5 7602 7604 7604.25 | 1 | 2 |
| NQ | am_mm | long | 2021-09-16 10:40 | 15407.4 | 15394.9 | 50 | 15408.2 | 15401.8 15400 15387.8 15396.8 15391.5 | 1 | 3 |
| NQ | am_mm | short | 2022-03-09 10:55 | 13636.6 | 13664.6 | 112 | 13635.8 | 13646.2 13648.5 13651.5 13683.8 13682.5 | 1 | 4 |
| NQ | am_mm | short | 2024-01-10 09:55 | 16833 | 16837.3 | 17.3 | 16823 | 16823.8 16821.2 16824.8 16831.5 16838.5 | 5 | 5 |
| NQ | pm | long | 2024-03-21 13:50 | 18637.4 | 18630.7 | 27 | 18638.5 | 18637.8 18633.5 18629.8 18619.5 18615.2 | 2 | 3 |
| NQ | am_mm | short | 2026-01-26 09:35 | 25770.8 | 25776.6 | 23 | 25769.8 | 25786.5 25797.8 25797 25794.8 25793.8 | 1 | 1 |
| YM | pm | short | 2019-03-27 14:00 | 25617 | 25635 | 18 | 25614 | 25625 25623 25634 25657 25667 | 1 | 4 |
| YM | lunch | long | 2019-06-20 12:10 | 26652 | 26644.2 | 7.8 | 26663 | 26629 26633 26627 26611 26595 | 1 | 1 |
| YM | am_mm | long | 2019-09-26 10:05 | 26936 | 26926 | 10 | 26939 | 26929 26927 26912 26907 26908 | 1 | 3 |
| YM | lunch | long | 2019-12-11 11:55 | 27841 | 27833.2 | 7.8 | 27855 | 27854 27847 27845 27839 27833 | 4 | 5 |
| YM | pm_last_hour | short | 2020-04-13 15:35 | 23287 | 23299 | 12 | 23284 | 23307 23298 23286 23304 23310 | 1 | 1 |
| YM | pm_sb | long | 2021-03-23 14:15 | 32505 | 32496 | 9 | 32505 | 32491 32488 32491 32504 32500 | 1 | 1 |
| YM | pm | short | 2023-10-05 13:35 | 33248 | 33259 | 11 | 33245 | 33275 33290 33284 33287 33282 | 1 | 1 |
| YM | pm_sb | short | 2025-01-14 14:35 | 42765 | 42782 | 17 | 42762 | 42772 42783 42773 42773 42775 | 1 | 2 |
| YM | pm_sb | short | 2025-06-26 14:05 | 43660 | 43707 | 47 | 43659 | 43707 43687 43676 43678 43681 | 1 | 1 |
| YM | pm_last_hour | short | 2026-08-03 15:10 | 53299 | 53321 | 22 | 53299 | 53312 53316 53310 53309 53321 | 1 | 5 |

## 3. Why it happens

The pre-break order-block entry puts a limit at the order block's body and the stop at the block's midpoint, or one
tick past the sweep extreme when that is under the 1-point minimum. That stop is often 4 to 6 ticks on ES (median 6
on the same-bar stops; NQ 30, YM 16). The order is armed with price sitting just past the limit, so it fills on the
next bar's first minute, and any ordinary bar then covers the stop distance.

Pre-break order-block trades, by stop size against the typical 5-minute bar (median range of the 12 bars before entry):

| stop size / typical 5m bar | trades | stopped in entry bar | average R | net $ |
|---|---|---|---|---|
| under 0.5 | 409 | 66% | -0.37 | -22,610 |
| 0.5 to 0.75 | 189 | 31% | -0.15 | -3,871 |
| 0.75 to 1 | 135 | 26% | -0.13 | +402 |
| 1 to 1.5 | 188 | 19% | -0.22 | -12,253 |
| 1.5 to 2 | 90 | 6% | -0.17 | -5,151 |
| over 2 | 65 | 5% | +0.33 | +6,313 |

The pattern is the same in 2019-22 and 2023-26 (stops under half a bar: 65% and 68% stopped in the entry bar,
-0.46 R and -0.30 R). Costs make it worse: on the same-bar stops costs are about 10% of the risk, so each one
loses about 1.1 R.

## 4. What it means

- The backtest is reporting these losses correctly.
- The tightest stops (under half a normal bar) are 38% of these entries and lose the most per trade. But wider
  stops lose too, except the widest 6% (65 trades, too few to trust), so a minimum stop size alone is unlikely to
  make the entry profitable.
- With the sizing cap lifted, tiny stops mean very large positions, so costs on these trades grow as a share of risk.
- Candidates for the entry study (each a switch, chosen on 2019-22 and checked on 2023-26): a minimum stop tied to
  recent bar size, the stop at the order-block low or sweep extreme instead of the midpoint (`ob_stop`), and a
  1-minute entry so the stop can be judged against 1-minute structure.
