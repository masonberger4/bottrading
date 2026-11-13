# Standard backtest runner, first passes (2026-11-13)

Mase approved (00:46 UTC): build the runner, do the free filter-combination pass, run ES + NQ + YM baselines, and hold
the weekly-rule default until these are in. No engine code or default was changed.

## Tools (this folder)

- `run.py`: runs any switch set on ES, NQ or YM from a pinned engine checkout; per-year trade files are cached.
- `report.py`: one table per run folder: trades, $, both halves, by year, max drawdown, t-stat, 90% chance range,
  result at 2x costs, total R, and the paired weekly difference to a base variant.
- `filters.py`: evaluates every on/off combination of 9 trade-removing filters from saved trade files.
- Engine 2101d04 (= `mentorship`), 5m, fixed-roll Databento data copied from the laptop, run in the cloud (4 cores,
  about 50 s per variant-year; all 120 jobs took 44 min). The laptop was not used.
- Check: the cloud run gives the laptop's trades exactly for defaults, wd_pwhl, pwhl_x and off_x (all years). wd_off
  differs by two `release_ob` trades out of 899 (2020-04-07 only on the laptop, 2022-04-08 only in the cloud; total
  -2,173 vs -2,106). Cause not found yet.
- Trade files: `/mnt/project-files/mentorship/runs/bt_base_2026-11-13/trades_and_skips.tgz`. Outputs: `results_2026-11-13/`.

## Result 1: NQ and YM do not confirm the ES results

$ at "$1k risk", 2019-26 (full table with years in `results_2026-11-13/report.txt`):

| variant | ES | NQ | YM | all three | trades | t-stat | all three at 2x costs |
|---|---|---|---|---|---|---|---|
| defaults | -490 | -4,292 | -3,845 | -8,627 | 544 | -0.60 | -17,683 |
| week rule high/low only (wd_pwhl) | +4,441 | -8,436 | -13,636 | -17,631 | 1,069 | -0.81 | -35,332 |
| same, AM + PM SB off (pwhl_x) | +7,441 | -6,111 | -8,219 | -6,889 | 848 | -0.33 | -21,064 |
| week rule off (wd_off) | -2,173 | -38,396 | -49,160 | -89,728 | 2,897 | -2.74 | -136,864 |
| week rule off, AM + PM SB off (off_x) | +10,213 | -28,726 | -37,056 | -55,569 | 2,143 | -1.80 | -90,813 |

- Every variant loses on NQ and on YM, and all three markets together lose in every variant. The ES gains look like luck.
- With the week rule off (most trades), the three-market loss is large enough to be real (t = -2.7): the setups as
  built lose money after costs.
- The week rule does help in all three markets (paired difference to wd_off: t = 2.0 to 2.7 per market), but it helps
  by trading less of a losing set, not by making it profitable.
- By setup, week rule off, all three markets (`by_setup.txt`): lunch 1,658 trades / -$53.5k; AM 387 / -$12.0k; PM
  Silver Bullet 355 / -$18.8k (t = -3.1); last hour 215 / -$1.3k. ES lunch +$5.8k is the outlier (NQ -$24.8k, YM -$34.5k).
  Only `ndog_scalp` is positive on two markets, on 50 trades.
- Caveat: NQ and YM as the traded market is new for this runner. Point-based settings are scaled by the price ratio to
  ES (the engine's own two-market method) and costs are $5 a side per contract. Rules that ICT states in NQ or ES
  points may not scale cleanly to YM.

## Result 2: "$1k risk" is not $1k

The engine caps a position at $400k notional. With ES near 4,000-6,000 that cap binds on most trades: the median trade
risks about $340-490, not $1,000, and tight-stop trades risk far less than wide-stop ones. In R (each trade counted
as one unit of its own risk) ES looks worse than in $: wd_off -82 R, off_x -8 R (while +$10.2k), pwhl_x +11.5 R. The $
totals are being carried by the wide-stop trades. The report now prints both.

## Result 3: filter combinations on ES find nothing

512 on/off combinations of: week rule, AM off, PM SB off, lunch off, last hour off, Monday off, Friday off, 08:30-news
days off, 10:00-news days off (`filters_ES.txt`).

- Best t-stat of any combination: 1.17. None beats a random day filter at the 5% level (0 of 205 with enough trades).
- Choosing on 2019-22 does not carry over: rank correlation with 2023-26 is -0.27. Of the 10 best 2019-22 picks, 8
  lose in 2023-26 (the best pick: +$14.6k then -$6.2k).
- On all three markets together no combination is up in 3 of 4 years of 2019-22 (`filters_ALL.txt`).

## What this means

Combining switches cannot rescue this: the filters only choose which trades to skip, and the trades themselves have no
measurable edge across the three markets. The useful next question is the entries (why lunch, AM and PM SB lose on
every market), not which filter set looks best on ES.

## Suggested next steps (Mase's call)

1. Keep the weekly-rule default on hold: no reading is profitable across markets; "high/low only" just loses least.
2. Decide how results should be sized: lift the $400k cap for backtests so $1k risk is real, or report in R.
3. Entry study per setup on all three markets (lunch first: 1,658 trades), using the saved trade columns before any
   new runs: what separates winners from losers, checked on one half and confirmed on the other.
4. Find the cause of the two-trade `release_ob` difference between laptop and cloud.
