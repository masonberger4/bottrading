# ch20 ICT Charter Price Action Model 6 \ Algorithmic Theory (beTnmkbuUjg)
Recorded 2022-05-31 / slides + ES charts / 30 min. Captions only.
Source tier: Charter. 2023 wins on conflicts. Index (ES June 2022) examples.

## Summary
Model 6 algorithmic discussion: trade the buy side of the curve of a MM sell model (or of a MM buy model) from discount to a premium array, buying stage-1 accumulation and stage-2 reaccumulation. Pyramiding is allowed only while there is "unrealized range" left; if the first run passes 50% of the expected range and retraces, assume a single stage and do not pyramid. A FVG is "trusted" when it overlaps an old distribution area that has become reaccumulation. The draw on liquidity matters more than the entry.

## Rules
- Go through time frames highest to lowest for a narrative that draws price to a specific premium array ~0:30-1:35
- If there is enough range between market price and where the short should form, use the buy side of the MM sell model; you may miss stage 1 and use stage-2 reaccumulation ~1:35-2:02
- ES 2022-05-31: failure to make a lower low and not breaking at 8:30 news into the sell-side low -> MSS, entry in the FVG (it overshot the FVG; stop below the low); in discount ahead of the 9:30 open, so expect a premium ~2:36-3:35
- When the objective is unknown, use an easy target: a FVG below an old high ~3:35-4:05
- Entries on stage 1/2: Model 13 (YouTube model) entry or a simple FVG ~4:58-5:36
- Pyramiding rule: if the run exceeds 50% of the distance from the start to the premium target and then retraces, assume only one stage of accumulation -> no pyramiding; if it reaches about half or less and pulls back, you may pyramid ~7:35-9:11, ~22:22-23:21
- Pyramid sizing example: 10 contracts, then 5, then 2-3 (10/5/2 or 10/5/3) ~22:52-23:21
- Pyramid only while unrealized range remains to the target ~8:42-9:11
- One stage of accumulation only -> expect a parabolic run (or bearish: press the sell side) ~11:52-12:21
- Carry up-close candles (sell side of the curve) across to the buy side: old distribution becomes new accumulation; the stage-2 reaccumulation gives the most dynamic move ~16:18-17:11, ~27:57-28:21
- Trust a FVG when it overlaps an old area of distribution now acting as reaccumulation, plus HTF bias, time of day, day of week (seasonal tendency optional) ~17:11-18:59
- No model from one element alone ("FVG alone is useless in the hands of a neophyte") ~18:37-19:24
- Retail stop engineering into the discount array: short-term low, rally, lower low stops out buyers twice, then the array (HTF FVG, OB, breaker, or old high) ~21:05-21:25
- Pattern is fractal (15s to quarterly); knowing the draw on liquidity is the most important thing, not the entry ~28:21-29:45

## Trade examples
- ES 2022-05-31 morning: bought FVG ahead of 9:30, partial below old high, BSL above relative equal highs; then sell side of the curve took out the original consolidation; second MM buy model on 1m and 15s ~25:00-28:21

## Definitions
- Unrealized range: distance from current low / entry to the target not yet traded
- Buy side of the curve: right half of a MM model, rising back to the original consolidation / premium array

## Open questions
- Pyramid threshold 50% of expected range: switch `pyramid_max_progress=0.5` (vs off)
- Pyramid sizing ratios 10/5/2 vs 10/5/3: switch
- "Trusted FVG" filter (FVG overlaps old distribution): switch `fvg_require_distribution_overlap`
