# 039 NWOG - New Week Opening Gap (WKKnlIIkBTk)
Recorded Mar 8 2023 / ES (E-mini S&P, Mar 2023 contract, ETH session) / 1m, 5m, 1h / ~16 min.

## Summary
Dedicated definition of the ICT New Week Opening Gap: the gap between the prior Friday's
16:59 ET close and the Sunday 18:00 ET open, with its 50% (CE) as a third level. Keep the
last 4-5 NWOGs on the chart; price gravitates back to old ones as "fair value" and treats
their edges/CE as support and resistance. A second variant (Friday close to Monday 09:30
open) is given as homework.

## Rules
- NWOG ("actual") = range between the previous week's Friday close price at 16:59 ET and the Sunday opening price at 18:00 ET (first tick of the new week) ~0:57, ~6:12 [chart] [new]
- Locate it on a 1m or 5m chart, not the daily: the daily uses a settlement price that will not match ~0:45 [new]
- Levels per NWOG: high edge, low edge, and CE = 50% of the two (Fib from Friday close to Sunday open) ~1:26, ~6:40 [chart] [new]
- Optional quarter levels (25% / 75%) between edge and CE; he uses them by eye ~9:29 [new]
- Do NOT discard an NWOG once filled; price commonly trades straight back into it after the Sunday open, and old NWOGs keep acting as reference weeks or a month+ later ~5:26, ~3:39 [new]
- Keep at least 4, preferably 5 most recent NWOGs (rolling ~1 month lookback, with overlap); no hard upper limit ~3:49, ~4:17, ~11:01 [new]
- Use: treat NWOG edges and CE as support/resistance and as targets ("large fund fair value"), same way as an FVG; price gyrates from one NWOG level to the next ~2:15, ~10:52, ~11:30 [chart] [new]
- Regime read: price staying near / returning to the current week's NWOG = range-bound/consolidation; leaving it and not returning = trending (expansion) week ~12:26-12:45 [new]
- He keeps NWOGs for NQ, ES, Dow, DXY, EURUSD, GBPUSD ~13:39 [new]
- Variant "NWOG" (vs "NWOG actual"): Friday 16:59 close to Monday 09:30 open, ignoring Sunday/overnight trading; homework, kept as a second template ~14:41-15:32 [new]
- Ep 05 note said the definition was not given there; it is given here (Friday close to Sunday open) ~1:00 [conflict resolved, update rule 105]

## Trade examples
No trades. Gaps read from the ES charts (Friday close 16:59 / Sunday open 18:00 / CE):
- Feb 5 2023: 4146.00 / 4134.25 / CE 4140.25 (5m chart) [chart]
- Feb 12 2023: 4099.50 / 4105.00 / CE 4102.25 (gap up) [chart]
- Feb 19 2023: 4085.75 / 4083.00 / CE 4084.50 (1m) [chart]
- Feb 26 2023: 3974.50 / 3976.50 / CE 3975.50 (gap up, 2 handles) [chart]
- Mar 5 2023: 4052.50 / 4049.25 / CE 4050.75 [chart]
Reactions on the 1h chart (Feb 5 - Mar 8): Feb 13-16 price oscillated around the Feb 5 NWOG
then dropped through the Feb 12 NWOG; the Feb 19 NWOG capped the Feb 21 bounce; Mar 6-7
rally stalled just under the Feb 19 NWOG (~4080) then fell back through the Mar 5 NWOG;
by Mar 8 price (~3995) had come down near the Feb 26 NWOG (~3975) [chart]. Read from the
picture, exact touches not legible.

## Definitions
- NWOG actual: Friday 16:59 ET close to Sunday 18:00 ET open ~15:18
- NWOG (Monday version): Friday 16:59 ET close to Monday 09:30 ET open ~15:25
- Real liquidity void: no prints between two price points; the weekend gap is one ~3:06
- CE applies because the NWOG is an inefficiency/gap; on an order block the 50% is called mean threshold ~6:57

## Seen only on the charts
- Each NWOG drawn as two black rays (labels "Friday Close Price 04:59 pm EST", "Sunday Open Price 06:00 pm EST") plus a red dotted CE line, extended right indefinitely [chart]
- Vertical lines on the 1h chart mark each Sunday 18:00 open (start of each week's NWOG) [chart]
- Friday close = close of the 16:59 1m candle; Sunday open = open of the 18:00 candle, which can be the wick extreme of that candle [chart]
- Gap sizes vary from 2 handles (Feb 26) to ~12 handles (Feb 5); there is no minimum size mentioned
- Shown CE prices are rounded to the 0.25 tick (e.g. 4084.375 shown 4084.50, 4050.875 shown 4050.75) [chart]

## Open questions
- No minimum gap size; what if Friday close == Sunday open (no NWOG, or zero-width level)?
- CE rounding to tick is inconsistent (up vs down); bot should keep the exact midpoint.
- How to trade it: no entry model given; NWOG is a level/target only. Which of the 5 is the "draw" on a given day is left to the other PD-array logic.
- For SPY/QQQ (no Sunday session) only the Monday-09:30 variant, or Friday 16:00 close vs Monday open, is available; ICT's 16:59 is futures-specific. Using ES futures data for levels and mapping to SPY would be needed for "NWOG actual".
- Holiday weeks (Monday holiday, early Friday close) not addressed.
- "Five weeks keeps a dynamic four months perspective" (~4:30) is likely a slip for ~one month.
