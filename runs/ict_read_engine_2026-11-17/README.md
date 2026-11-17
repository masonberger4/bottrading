# The coded ICT direction read inside the engine (option B), 2026-11-17

Mase: "Do A B C" (2026-11-17). This is B: the read from PR #101 added to the narrow morning engine as switches, all off
by default, then backtested. It also covers the coordinator's follow-up: test the option C (PR #103) 09:30 day
filter inside the engine.

## Switches (mentorship/narrow.py, mentorship/ict_read.py)

| switch | what it does |
|---|---|
| `nar_bias="read"` | take a trade only on the side of the read (four votes: toward yesterday's settlement, away from the side of the overnight range made last, toward the side with more recent opening gaps, toward untouched equal highs / lows) |
| `nar_on_block=0.67` | no trade toward the overnight extreme price already sits at |
| `nar_entry="open"` | no setup: buy / sell the first open of the window on the read's side, stop `nar_open_stop_pct` % away, 2R target, flat 12:00 (the option C entry) |
| `nar_day_skip=(...)` | skip days he says he passes on: `news`, `holiday_eve`, `prev_big`, `small_gap`, `friday` |

The engine's read was checked against the research code (feat.py) on 2,400 day / time pairs: identical. The engine's
09:30 trades take the same side as the research code on every day (1,682 NQ, 1,689 ES).

## How it was run

`run.py`, 1-minute fixed-roll bars, NQ and ES, 2019-22 to choose and 2023-26 to check, $1,000 risk a trade, no sizing
cap (median risk $981-$996, largest $1,000), $5 a side. "skip" = his four conditions from option C (NFP / CPI / FOMC,
holiday eve, day after a range over 1.5x normal, opening gap under 0.10 of the average range).
Full table: `results/summary.txt`. Trades: `/mnt/project-files/mentorship/runs/ict_read_engine_2026-11-17/trades.tgz`.

## Result

R = average result a trade in units of its risk (x $1,000 = $). t under about 2 cannot be told from zero.

### A. The sweep / shift / gap engine (PR #89) with the read as a filter

| | 2019-22 | 2023-26 | max drawdown 2019-26 |
|---|---|---|---|
| NQ base | 128 trades, +0.07 R, +$8.9k | 101, +0.12 R, +$11.3k | -$11.1k |
| NQ read only | 96, +0.04 R, +$4.0k | 78, +0.01 R, +$0.7k | -$13.9k |
| NQ block toward the extreme | 119, +0.08 R, +$9.5k | 93, +0.08 R, +$6.9k | -$12.6k |
| NQ read + block | 94, +0.04 R, +$3.6k | 74, +0.04 R, +$2.2k | -$12.7k |
| NQ skip days | 78, +0.11 R, +$8.6k | 63, +0.04 R, +$2.0k | -$11.2k |
| ES base | 108, +0.08 R, +$9.0k | 131, -0.07 R, -$8.9k | -$21.7k |
| ES read only | 77, +0.07 R, +$5.7k | 95, -0.00 R, -$0.4k | -$14.5k |
| ES block toward the extreme | 102, +0.04 R, +$3.8k | 121, -0.07 R, -$8.1k | -$21.2k |
| ES read + block | 76, +0.07 R, +$5.2k | 89, +0.03 R, +$2.8k | -$14.1k |
| ES skip days | 61, +0.07 R, +$4.2k | 72, +0.05 R, +$3.5k | -$10.9k |

**Neither filter improves the setup engine.** The read removes about a quarter of the trades and the ones left are
no better (NQ worse in both halves; ES a little better in 2023-26, t 0.2). The block removes 18 trades a market and
changes nothing. Every t is under 1. Both markets, by day: base +0.03 R (t 0.6), read +0.02 R (t 0.3), block +0.02 R
(t 0.3).

### B. Option C in the engine: the read's side at the 09:30 open

| | 2019-22 | 2023-26 | max drawdown 2019-26 |
|---|---|---|---|
| NQ every day | 853, +0.07 R, +$57.4k (dd -$21.1k) | 829, +0.00 R, +$0.1k (dd -$34.3k) | -$36.5k |
| NQ skip days | 516, +0.06 R, +$31.5k (dd -$20.0k) | 517, +0.05 R, +$25.1k (dd -$27.3k) | -$36.0k |
| NQ skip days + block | 499, +0.08 R, +$40.9k (dd -$20.9k) | 499, +0.06 R, +$28.6k (dd -$26.2k) | -$34.9k |
| ES every day | 859, +0.02 R, +$15.5k (dd -$38.7k) | 830, +0.09 R, +$77.5k (dd -$21.5k) | -$38.7k |
| ES skip days | 516, +0.07 R, +$38.1k (dd -$13.5k) | 501, +0.17 R, +$83.2k (dd -$17.2k) | -$17.2k |
| ES skip days + block | 504, +0.07 R, +$32.5k (dd -$13.5k) | 482, +0.18 R, +$86.0k (dd -$16.3k) | -$16.3k |
| NQ at 10:00, skip days | 531, -0.09 R, -$47.7k | 514, +0.07 R, +$32.9k | -$104.7k |
| ES at 10:00, skip days | 510, -0.16 R, -$79.0k | 506, +0.18 R, +$90.7k | -$95.5k |

Both markets together by day, skip days: 2019-22 +0.06 R (t 1.2), 2023-26 +0.08 R (t 1.7), all eight years +0.07 R
(t 2.0), +$178k trading both, drawdown -$32.7k. With the block added: +0.08 R (t 2.3), +$188k, drawdown -$31.5k.

1. **The engine reproduces option C.** Same sides, and the same result within a few trades (PR #103: NQ +0.06 / +0.06,
   ES +0.08 / +0.17).
2. **It is the only thing here positive in both halves on both markets, and it is still weak.** ES carries it (t 2.9
   over eight years, 7 of 8 years up). NQ alone is t 1.3 with 4 of 8 years up and a drawdown larger than half its
   total.
3. **It depends on the stop width.** The first pass measured the 0.25% stop on the engine's back-adjusted prices
   (about 1.4x wider in 2019). With that wider stop the 2019-22 half was flat on both markets (NQ +0.01 R, ES
   -0.01 R). An edge that disappears when the stop is a third wider is not robust.
4. **The block toward the overnight extreme adds a little at 09:30** (+$10k over eight years across both markets, on
   about 30 fewer trades a market). Too small to tell from noise; it agrees in direction with option A's new calls.
5. **10:00 fails as in option C**: large losses in 2019-22.
6. Adding Friday to the skip days does not help (NQ 2019-22 drops to +0.03 R).

## What this means

As a filter on the setup engine, the read adds nothing. As its own entry at the 09:30 open on days he would not
skip, it holds up inside the engine at about +0.07 R a trade, mostly from ES, with drawdowns of $17k (ES) to $36k
(NQ) at $1k risk. That is a lead, not something to trade: about ten day conditions were tried in option C before
this one, the t-stat is about 2, and it is sensitive to the stop.

## Caveats

- The 09:30 entry is the open of the 09:30 bar plus the standard cost. Slippage at the bell can be more.
- `nar_open_stop_pct` is a % of the price in the engine's frame. On back-adjusted bars the runner scales it each day
  by traded price / adjusted price so the stop is a % of what traded.
- PPI days are in the engine's default news list but not in the run (option C's dates file had no PPI for 2019-26).
- The full test suite was not run; the 18 new tests and 238 related tests pass.
