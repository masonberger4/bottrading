# 014 Institutional Market Structure & Standard Deviations With Buyside Liquidity (g8bhZReDK-Q)
Date discussed: Fri Feb 10 2023 (recap). Market: ES (E-mini S&P, Mar 2023), 1-minute chart, 09:30-16:00 shown. Duration ~6:30.

## Summary
Short follow-up to a Twitter Space. He labels short/intermediate/long-term lows on the Feb 10 PM session, then anchors a fib on the down-swing into each of several lows and projects standard deviations above. The first SD level past the buy-side liquidity, from several lows, clusters at 4104.00-4104.25. The actual high of day printed 4104.25 to the tick on the 15:54 candle, after the final-hour macro.

## Rules
- Swing hierarchy: a short-term low (STL) is a plain swing low. An intermediate-term low (ITL) is a low with a higher STL on each side. A long-term low (LTL) is the low between two ITLs (lower than both). [new] ~00:12-00:58 [chart]
- When bullish, the target is buy-side liquidity above (here the "Buyside Liquidity" line at 4100.75, an old high from ~09:58). [chart] ~01:00
- SD projection anchor: price level 1 sits on the swing low's wick low. Level 0 sits on the wick high of the swing high just before that low, i.e. the down-leg into the low, not the rally after it. Levels are projected above the 0 point: hi + k*(hi-lo), k = 1, 1.5, 2, 2.5, ... (fib levels -1, -1.5, -2...). [conflict] with the bot's leg (sweep low to the highest high after it) and with the Ep06 "low to the high" wording. ~01:58-03:46 [chart]
- Do this for several recent swing lows, not just one: STL, ITL and LTL in the same leg. [new] ~01:50-03:50 [chart]
- Target choice: skip any SD level that is at or below the buy-side liquidity (or below a higher high that has since formed). Use the first SD level beyond it. [new] ~02:54-03:46
- If a newer, higher high forms (13:20 high ~4101.50 above the 4100.75 line), it becomes the buy-side reference and SD levels below it are skipped. [new] ~03:27-03:37
- Confluence: when the first-past-liquidity SD levels from several lows land within a tick or two, that cluster is the high-probability turning point. [new] ~04:36-04:43
- Final hour macro 15:15-15:45 (box on chart). The algorithm does a market-on-close run to obvious untouched liquidity; bulk of volume is done by 16:00. The 15:15-15:45 window is already in the rules file; the MOC-run idea is [new]. ~05:19-05:56 [chart]

## Trade examples
No trade taken; a level-projection recap. ES 1m, Feb 10 2023 (all levels read from fib labels on the chart):
- Fib A: LTL ~12:20 low 4072.25 to the preceding swing high 4080.50 (range 8.25). -2.5 = 4101.25 is the first level past the 4100.75 buy-side; -3 = 4105.25. ~01:42-01:50 [chart]
- Fib B: STL ~12:28 low 4075.25 to the preceding high 4080.50 (range 5.25). -4 = 4101.50, which matches the later 13:20 high. -4.5 = 4104.25. ~01:58-02:28 [chart]
- Fib C: ITL ~14:25 low 4082.00 to the preceding high ~14:16 at 4090.75 (range 8.75). -1 = 4099.50 is below buy-side, so it is skipped; -1.5 = 4104.00. ~02:43-03:07 [chart]
- Fib D: STL ~14:43 low 4084.75 to the preceding high ~14:33 at 4091.25 (range 6.5). -1.5 = 4101.00 is below the 4101.50 high, so it is skipped; -2 = 4104.25. ~03:14-03:46 [chart]
- Outcome: the macro pulled back into blue FVGs ~4088-4092 (15:27-15:34), then ran up. HOD 4104.25 came on the 15:54 candle, exactly the cluster. ~04:16-05:19 [chart]

## Definitions
- STL / ITL / LTL: see Rules (~00:39-00:58).
- Institutional market structure: his name for using this swing hierarchy plus SD confluence to find turning points (~04:43).
- Final hour macro: 15:15-15:45 ET (~05:35).

## Seen only on the charts
- Every anchor uses wicks (handles sit on the wick tip), never bodies or closes. Fibs A and B share the same 0 point 4080.50: two equal swing highs at ~12:08 and ~12:24 bracket the LTL.
- His fib template has 0, 1, 0.5, 0.62, 0.79 and -0.5 to -10 in half steps up to -6.5, then whole steps. He says he ignores the OTE, equilibrium and daily-range levels here (~01:21-01:43).
- Swing labels on the chart: STL 10:40, ITL ~10:45 (4078.00 line), STL 11:10, STL 12:05, LTL 12:20, STL 12:28, STL 14:10, ITL 14:25, STL 14:45. Low of day is 4069.75 (~09:35) and the 09:30 open is marked.
- The SD levels used go as deep as 4.5 SD. The bot's default sd_levels (1, 1.5, 2, 2.5) would miss Fib B's 4104.25.

## Open questions
- "Preceding high" in a coder's terms: is it the most recent pivot high before the low, or the highest high since the prior swing low? For A-D these give the same answer.
- He says the cluster came from "two ITLs and an LTL" (~03:48), but the chart labels Fibs B and D as STLs. It is unclear which lows count, or whether every swing low in the leg is used.
- How many lows are needed for "confluence", and what tolerance? Here 4104.00 vs 4104.25, 1 tick.
- Fib A's first-past level (4101.25) was not the final high. How should a coder weight per-low levels against the cluster?
- Is there a cap on SD multiples? -4.5 was used here.
- Mirror for sell-side (anchor on the up-leg into a swing high, project below) is implied but not shown.
