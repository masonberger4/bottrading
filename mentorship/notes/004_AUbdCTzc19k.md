# 004 ICT Emini NQ Futures Market Maker Live Execution - January 04, 2023 (AUbdCTzc19k)
NQ March 2023 (CME mini), 1-minute chart, Jan 4 2023. About 2 minutes long with no captions: a
sped-up replay of the trade reviewed in video 003 (Ep 03). Notes come from the chart frames
only (6 frames, all viewed).

## Summary
This is the live execution of the market maker buy model from Ep 03. Before 10:00 he labels the
draw: buy-side liquidity at 11048. Price drops after 10:00, he buys at a bullish order block
around 10:35-10:45, and he scales out into 11048. The final target is the daily volume
imbalance at about 11075.

## Rules
- Draw on liquidity marked before the setup: the buy-side at old highs, 11048, labeled "Buyside Liquidity Will Be The Draw On Liquidity" (0:00) [chart].
- Entry is at a bullish order block (+OB, blue box ~10890-10900) after the post-10:00 sell-off made a low, at about 10:35-10:45 (0:00) [chart]. This matches Ep 03's 10:30-11:00 window.
- After the displacement up, the FVG at ~10930-10945 is annotated: the algorithm won't let price back below this FVG because it is targeting 11050. He waits for "support" to form there (0:00) [chart] [new]. In bot terms, the first FVG after the shift is a protected zone, so trail the stop under it.
- Adds: blue OB zones at ~10945-10955 (11:00) and ~10968 (11:15) mark later adds or support (1:00) [chart].
- An intermediate level at 10987 is labeled a "speed bump", not a reversal level. He sold 2 there (1:00) [chart] [new]. In bot terms: partials at pause levels, not full exits.
- Scale-out plan (labels say "as stated I would"), all [chart]:
  - Sell 2 at ~10987.75.
  - Sell 3 above 11018.25 (fills at 11019.50 / 11029 / 11031.75).
  - Sell 3 at the 11048 buy-side (11047.25 / 11051 / 11056).
  - Last contract out at 11050.50 around 11:56.
- The final target is the daily volume imbalance, about 11075.50 at its bottom, labeled the trade "terminus". Price never reached it; the last unit was stopped/sold before noon. Annotation: if the last contract stops out, "who cares" (1:00) [chart].

## Trade examples
- NQ, Jan 4 2023, long. Size 6 contracts initially (frames show "6 / +3540 USD" and "6 / +6540 USD" order lines at 10930.50 and 10901).
  - Entry around 10:40 at the +OB, ~10895-10901.
  - Exits in 2/3/3/1 sequence from 11:30 to 11:56 between 10987 and 11056.
  - The run lasted about 11:25-11:40.
- Result shown on the final contract: about +601 ticks. Lunch approach: last unit closed near 12:00.

## Seen only on the charts
- Exact levels: draw 11048; protected FVG ~10930-10945; speed bump 10987; partial line 11018.25; daily VI bottom ~11075.50.
- Exact fills: the scale-out prices listed above.
- The order block he bought is the last down-close candles at the 10:35-10:40 low (blue box). The entry line sits at the top of that box.

## Open questions
- The exact first entry price and the stop location aren't visible in these 6 frames.
