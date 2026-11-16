# Price check of the overnight-gap scalp (`ndog_scalp`), 2026-11-16

Mase (19:07 UTC): price-check the one positive setup from `runs/bt/RESULTS_2026-11-16.md` (50 trades, +0.52 R, t 2.5).
Engine 2101d04, fixed-roll data, run in the cloud. Results only: no engine code or default was changed.
`ndog.py` (run + 1-minute replay), `report.py` (tables), `ndog_all_trades.csv` (every trade), `output.txt` (all tables).

## 1. The prices are right

- All 50 trades of the engine run, and all 76 of the larger sample below, match the 1-minute bars exactly: the entry is
  the first 1-minute open of the fill bar, and replaying stop and target minute by minute gives the same exit for every
  trade (0 differences). Every winning target was traded through, not just touched.
- Against the raw front-month contract prices: entry minus the back-adjust offset equals the raw 1-minute open on 76 of 76.
- Why PR #75 could not line them up: the engine's daytime trades are booked in real contract prices, but the scalp runs
  on the back-adjusted evening bars and its rows keep those prices, with `adj = 0` and no `contract`. That is a
  labelling fault only. The offset is constant through each evening, so points, R and $ are the same in either frame.
- Rolls: 4 of 76 trades fall on a roll evening (the contract changes at 18:00). The adjusted series gives the right gap
  there (the raw files would compare two different contracts). Without those 4: +0.42 R instead of +0.45 R.
- No look-ahead found in the rule: the 17:00 close, the 18:00 open, closed 5m bars, market fill at the next open, stop
  beyond the extreme seen so far.

So back-adjustment and roll handling do not inflate the result. The numbers are what the rule earns on this data.

## 2. A larger sample barely exists

The engine only reaches the scalp on days its daytime rules did not skip. Running the engine's own function on every
complete session's evening, ES + NQ + YM, 2016-26, gives 76 trades on 60 evenings (about 7 a year). The 50 engine
trades are all in there, identical.

$ at a true $1,000 risk per trade. "t by evening" counts one evening as one result, because the three markets move
together. "1 tick" adds one tick of slippage on the market entry and on stop and time exits.

| | trades | evenings | avg R | total $ | win | t by trade | t by evening | max drawdown | avg R with 1 tick | t by evening, 1 tick |
|---|---|---|---|---|---|---|---|---|---|---|
| all 2016-26 | 76 | 60 | +0.45 | +33.8k | 55% | 2.63 | 2.16 | -8.1k (8.1 R) | +0.36 | 1.72 |
| ES | 26 | 26 | +0.07 | +1.9k | 38% | 0.24 | 0.24 | -7.6k | -0.08 | -0.24 |
| NQ | 30 | 30 | +0.41 | +12.3k | 57% | 1.67 | 1.67 | -4.8k | +0.38 | 1.51 |
| YM | 20 | 20 | +0.98 | +19.6k | 75% | 3.08 | 3.08 | -2.2k | +0.89 | 2.76 |
| 2019-22 (choose) | 20 | 15 | +0.92 | +18.4k | 75% | 3.09 | 2.18 | -2.1k | +0.83 | 1.96 |
| 2023-26 (check) | 34 | 30 | +0.21 | +7.1k | 44% | 0.81 | 0.79 | -8.1k | +0.13 | 0.48 |
| 2016-18 (extra) | 22 | 15 | +0.38 | +8.3k | 55% | 1.17 | 0.86 | -6.0k | +0.28 | 0.63 |

With two ticks of slippage: +0.27 R overall (t by evening 1.28), 2023-26 +0.05 R.

By year (R): 2016 -0.2, 2017 +1.2 (1 trade), 2018 +7.3, 2019 +2.9, 2020 +3.7, 2021 +1.5, 2022 +10.3, 2023 -1.9,
2024 -5.6, 2025 +13.4, 2026 +1.3. Longs +0.39 R (43), shorts +0.51 R (33).

## 3. What this means

- The result is real on this data but weak as evidence. It is positive in all three periods, yet outside 2019-22 it is
  not distinguishable from zero (2023-26: +0.21 R, t 0.8), and most of the profit sits in 2022 and 2025.
- ES, the market ICT teaches it on, is flat (+0.07 R, negative with one tick of slippage). YM carries the result, and
  YM is where it is least tradeable: the median entry minute trades 14 contracts and a $1k-risk position is about 12.
- It was the best of 9 setups, so a t near 2.2 is roughly what the best of nine coin flips produces.
- Stops are tight (median 12 ticks on ES, 16 on YM), so each tick of slippage costs about 0.05-0.09 R a trade.
- At about 7 trades a year and $1k risk it would make about $3k a year before slippage, with an $8k drawdown.

Suggested (Mase's call): do not build on this setup yet. If wanted, the cheap next steps are (a) stamp the scalp and
Venom trade rows with the contract and real prices so they line up with raw data (labelling fix, engine change with a
test), and (b) paper-trade the scalp to see real fills in the thin 18:00 hour before trusting it.
