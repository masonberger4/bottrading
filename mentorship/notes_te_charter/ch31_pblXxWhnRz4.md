# ch31 ICT Charter Price Action Model 11 \ 30 Pip Day Trade Plan + Algorithmic Theory (pblXxWhnRz4)
Trade plan ~2020 + lecture 2022-06-01 / slides + AUDUSD daily/15m/5m / 23 min. Captions only.
Source tier: Charter. 2023 wins on conflicts. FX units.

## Summary
Model 11 trade plan: 20-day IPDA range only (no Sundays); target external range liquidity (old daily highs/lows). Look for 30-pip ranges on the 60m; short 60m premium OTE / buy 60m discount OTE at a calendar volatility injection; execute on a 15m or 5m OTE formed by the 60m retracement in London/NY open kill zones. Limit at the 62% fib -/+ 5 pips; one position, TP 30 pips; stop 20 pips; at +15 reduce stop by 5 pips; at +20 move to break-even. Models 11 and 12 are "bread and butter": frequent, higher strike rate, lower R, not for beginners. Lecture: weekly target need not be reached; take partials at the previous day's high and 10/20 pips above it.

## Rules
- Preparation: medium/high events; weekly profile ~1:54-2:26
- IPDA: last 20 trading days only (no Sundays) ~2:26-2:54
- Target external range liquidity; anticipate OTE on a calendar volatility day ~2:54-3:28
- Opportunity: 60m chart expansion that covers > 30 pips toward buy-side (bullish) / sell-side (bearish) ~3:28-3:54
- Trade planning: short 60m premium OTE / buy 60m discount OTE with manipulation opposite your bias at a volatility injection ~3:54-4:24
- Execution: 15m or 5m OTE formed within the 60m retracement during London open and/or NY open kill zones ~4:24-5:27
- Entry: sell limit at 62% retracement - 5 pips; buy limit at 62% + 5 pips ~5:27-6:02
- TP 30 pips single position; then wait for another opportunity ~6:02-6:36
- Stop 20 pips; at +15 pips reduce stop by 5 pips; at +20 pips stop to break-even ~6:36-7:16
- Sizing and loss / 5-win risk rules as other plans; no standard lots at $10k ~7:16-9:47
- Draws: previous day's high/low, intra-week highs/lows, last week's high/low ~10:18-10:46
- Weekly bias is a filter; trades against it are allowed with reduced risk (advanced) ~19:58-20:52
- Partials: just below the previous day's high, 10 pips above it, 20 pips above it (10-pip increments from a calibrated level, e.g. 0.7205 -> 0.7215 -> 0.7225) ~16:25-17:40
- 15m is the "bellwether chart" ~14:57
- London open (2:00-5:00 NY): FVG CE buy after the midnight Judas swing; 5:00-7:00 consolidation then straight run into NY open can set up a NY reversal profile ~15:33-16:01, ~22:26-22:58

## Trade examples
- AUDUSD 2022-06-01: draw = weekly relative equal highs / gap; midnight Judas below, London FVG CE long, ran ~25 pips above the previous day's high into NY open, then collapsed (DXY bullish) ~12:20-22:58

## Definitions
- Bellwether chart: 15m used to read the intraday story

## Open questions
- 62% fib +/- 5 pip limit entry: switch `m11_entry = {fib62_offset, fvg_ce}`; pip offset mapping to index is our interpretation
- Stop step at +15 (reduce 5) and BE at +20: switch
- 20-day IPDA only for Model 11 vs 20/40/60 elsewhere: per-model switch
