# The narrow morning engine with ICT's own calls as its direction (2026-11-17)

Asked by Mase ("Ok for both", 2026-11-17). Results only: no engine code, default or data changed.

Question: if the direction is right, can it be turned into money? The narrow morning engine (PR #89, `Params.narrow='am'`)
had no direction input. PR #87 to #92 found that ICT's dated calls are right about 79% of the time when they are for
the morning. Here his call is the engine's side on the days he made one.

## Short answer

1. **The engine cannot answer it: it trades too rarely.** On the 63 morning calls that were clearly made before the
   move, the engine found a setup on his side 5 times: 4 winners, +5.0 R (+$4.8k), worst drawdown -$1.0k. The other
   side also traded 5 times and lost 2.7 R. That gap points the right way, but 3 in 100 coin-flip side choices on the
   same days do as well, and with no entry allowed before the call time it is 3 trades. The engine fires about one day in
   nine with or without his call.
2. **His direction by itself did make money in this test.** Entering his side at the 09:30 open (or at the call time
   when the call came later), stop 0.25% away, target 2R, flat at 12:00: 63 trades, 56% winners, **+0.46 R a trade
   (t 2.7), +$29.0k at $1,000 risk, max drawdown -$5.0k**, longest losing run 5. The same entry on the other side:
   -0.72 R a trade (-$45.3k). The same side, time and stop on every other day within 60 days of each call (4,265
   trades): +0.01 R. So the money is in the call, not in the entry.
3. **A right direction would rescue the engine.** On every day 2019-26, the engine held to the side of that morning's
   09:30 to 12:00 move (known only afterwards) makes +0.73 R a trade on NQ and +0.75 on ES; held to the wrong side it
   loses 0.53 and 0.64. But that is only about 14 trades a year a market.
4. **This is not a tradable system yet.** The calls exist only as his published videos (63 in under four years), the
   call times are estimates, and PR #93 found no coded rule that reproduces them. What it shows is where the edge is:
   in the short-term read of direction, which is the thing still missing.

## What was run

- Engine: mentorship @ `e68ef84` plus the stop guard commit (base narrow settings, guard has no effect on this mode),
  1-minute fixed-roll bars, $1,000 risk a trade, no sizing cap, $5 a side per contract. `run.py` wraps the engine's own
  direction filter for one day at a time, so no engine code changed. Check: with no side, NQ 2019-26 gives the same 229
  trades and +$20,163 as PR #89.
- Calls: the four scored sets in `runs/ict_calls_2026-11-17/` (114 one-sided calls). Each call is traded on its own
  market (NQ, or ES for the 2023 ES calls).
  - **Main group: 63 calls made in the morning (before 11:30), ending by 12:00, marked clearly before the move**
    (60 market-days, 78% right at his horizon). With the "partly" and "unclear" ones: 71 calls.
  - Morning calls with a longer horizon (to 16:00 or beyond): 12.
  - Evening calls and outlooks: 24, traded on the next morning only.
  - 7 afternoon calls that ended the same day are left out (there is no morning to trade).
- For each call day the engine was run long only, short only and with no side. Then, with entries not allowed before
  the call time (and not after a later opposite call the same morning).
- Plain entry (the "is it the call or the entry" control): his side at the open of the 09:30 bar, or the first bar at
  the call time when that is later; stop 0.25% of price away on NQ and 0.21% on ES (the engine's median stop
  distance); 2R target; flat at 12:00; stop first when a bar touches both. These settings were fixed before the result
  was seen. One-setting changes are shown as a check.

## Results, main group (63 calls)

R = result a trade in units of its own risk (x $1,000 = $). t under about 2 cannot be told from zero.

| | trades | winners | R a trade (t) | 95% range for R | total | max drawdown |
|---|---|---|---|---|---|---|
| engine, his side | 5 | 80% | +1.00 (1.8) | -0.08 to +1.86 | +$4.8k | -$1.0k |
| engine, no side | 10 | 50% | +0.23 (0.5) | -0.55 to +1.03 | +$2.2k | -$2.0k |
| engine, other side | 5 | 20% | -0.54 (-1.1) | -1.02 to +0.42 | -$2.7k | -$2.7k |
| engine, his side, not before the call | 3 | 67% | +0.54 (0.6) | -1.01 to +1.99 | +$1.5k | -$1.0k |
| plain entry, his side, with the engine's stop that day | 5 | 80% | +1.06 (1.9) | -0.07 to +1.93 | +$5.3k | -$1.0k |
| **plain entry, his side** | 63 | 56% | **+0.46 (2.7)** | +0.14 to +0.79 | **+$29.0k** | **-$5.0k** |
| plain entry, other side | 63 | 10% | -0.72 (-7.2) | -0.90 to -0.51 | -$45.3k | -$45.3k |
| plain entry, 15 minutes later | 63 | 52% | +0.33 (2.0) | 0.00 to +0.65 | +$20.6k | -$5.6k |
| plain entry, 30 minutes later | 63 | 57% | +0.47 (2.9) | +0.15 to +0.77 | +$29.3k | -$5.1k |
| plain entry, same side and time on other days (chance) | 4,265 | 37% | +0.01 (0.5) | -0.03 to +0.05 | | |

Risk: the engine risked $986 a trade (median; largest $1,000). The plain entry risks $1,000 by construction; its worst
trade is -1.01 R. Plain entry by year: 2023 +$12.3k (16 trades), 2024 +$5.7k (14), 2025 +$4.3k (3), 2026 +$6.7k (30).
NQ +$18.7k (48), ES +$10.3k (15). Longs +0.52 R (34), shorts +0.40 R (29). Exits: 26 stops, 24 targets, 13 at noon.

Plain entry with one setting changed (63 trades each): half the stop +0.51 R; twice the stop +0.49 R; 1R target
+0.38 R; 3R target +0.39 R; no stop or target, held to noon, +0.97 in units of the same stop (drawdown -$10.5k). All
positive, so the result does not hang on the settings.

Other groups (`results/summary.txt` has every row):

- All 71 morning calls ending by 12:00: engine his side is the same 5 trades; plain entry +0.46 R (t 2.8), +$32.7k,
  drawdown -$5.0k.
- 12 morning calls with a longer horizon: plain entry -0.26 R. These calls are right 42% of the time.
- 24 evening calls and outlooks, next morning: plain entry -0.11 R, the other side -0.09 R; the engine never traded
  his side. No information by the next morning, as PR #92 found.
- When his call was right at his horizon (56 calls) the plain entry made +0.74 R; when it was wrong (15), -0.57 R.
  That cannot be known beforehand; it shows the entry adds nothing the call does not already carry.

Every day 2019-26, engine only (`trades_alldays.csv`):

| | trades | R a trade (t) | total | max drawdown |
|---|---|---|---|---|
| NQ, no side | 229 | +0.09 (1.1) | +$20.2k | -$11.1k |
| NQ, side of the morning move (hindsight) | 113 | +0.73 (7.0) | +$80.9k | -$3.5k |
| NQ, wrong side | 120 | -0.53 (-6.4) | -$62.3k | -$62.3k |
| ES, no side | 239 | 0.00 (0.0) | +$0.1k | -$21.7k |
| ES, side of the morning move (hindsight) | 112 | +0.75 (6.8) | +$83.8k | -$3.1k |
| ES, wrong side | 133 | -0.64 (-10.1) | -$84.2k | -$86.1k |

The hindsight rows are a ceiling, not a strategy: the side is read from the same morning's move.

## Limits

- Small sample: 63 calls, and for the engine 5 trades. The plain-entry result (t 2.7) would turn up by luck about
  one time in a hundred, but it is one test on one set of calls.
- The calls are the ones he chose to publish, logged from the videos by an earlier thread. Call times are estimates;
  entering 15 or 30 minutes later still works, which helps.
- "Clearly before the move" is the earlier thread's marking. Including the 8 less certain calls changes nothing.
- 2023 ES prices are back-adjusted (fixed-roll), so the 0.21% stop is a few percent wider there than on real prices.
- Nothing here can be traded forward: there is no way yet to produce his call without him.

## Files

- `run.py` (run from an engine checkout, `python <path>/run.py OUTDIR`), `summary.py`.
- `results/summary.txt`, `results/call_days.csv` (which day each call was applied to), `results/trades_calls.csv`
  (every trade, every variant), `results/trades_alldays.csv`, `results/ENGINE.txt`.
