# cc07_005 ICT Mentorship Core Content - Month 07 - Short Term Trading Low Resistance Liquidity Runs Part 1 (y0lVKWLsZeM)
2016-17 Core Content (slides). Market: GBPUSD daily (Dec 2016 - end of Mar 2017) [forex example; concept is market-agnostic]. Timeframes: daily chart, with monthly/weekly/daily PD arrays drawn; 4h/1h mentioned for exits. Duration ~25 min.

## Summary
Framework for "one shot one kill" short-term (1 day to 1 week) trading inside a consolidation. Define the last-60-trading-day range by candle bodies, split it at 50% into premium/discount, then keep halving each half (quadrants, then eighths). Buy discount PD arrays in a discount sub-range, take first profit at a 4h/1h premium PD array once price enters the premium sub-range; mirror for shorts. Best trades sit at the outer edges of the big range; the middle chops traders up.

## Rules
- Short-term (one shot one kill) look-back = IPDA data ranges of the last 20, 40, 60 trading days; 60 days (~3 months) is the maximum look-back ~0:40-1:16, ~2:46 [new]
- Classify the daily market first: trending vs consolidation (range-bound for the visible ~3 months) ~2:14 [new]
- Range definition: highest candle body (open or close, whichever is higher) and lowest body (open or close) in the last 60 trading days; wicks ignored ~3:10-4:31 [chart] [new]
- Draw the 50% of that body range on the daily (horizontal line). Above = premium (sell / take long profits), below = discount (buy / cover shorts) ~4:39-6:39 [chart]
- Then take the 50% of each half (upper half: body high to mid; lower half: mid to body low) -> quadrants ~5:15-6:05 [chart] [new]
- Keep subdividing: each quadrant is again split in half, giving its own premium/discount band (frames show 8 bands of the range) ~9:02-14:14 [chart] [new]
- Range location alone means nothing; it needs a PD array (OB, breaker, FVG, rejection block, old low/high run) in the right sub-zone ~14:52-15:24 [new]
- Longs: enter a discount PD array in a discount sub-range; first profit when price enters the premium sub-range, at a 4h or 1h premium PD array (not visible on the daily) ~9:36-11:44, ~16:47 [new]
- Longs are allowed even in the upper half of the overall range if bought in a discount sub-band with room to a higher premium array; probabilities fall off sharply near the top ~11:53-13:20, ~17:19 [new]
- Best longs: lower half + lowest quadrant. Best shorts / long exits: the top quadrant (top eighth reacts strongest to premium arrays) ~18:21-18:45, ~21:08-21:50 [new]
- The middle of the range is where you get chopped; avoid without strong bias/liquidity read ~22:50-24:06 [new]
- Prefer PD arrays that have NOT been traded to yet; a reused OB has lower odds because price seeks new liquidity ~23:13-23:43 [new]
- Holding period: one day up to one week; not necessarily Monday-in, Friday-out ~22:29-22:44 [new]
- Ideal pairing: entry array in one zone, target = opposite-type array in the next zone (low resistance liquidity run between PD arrays) ~8:01-8:49, ~20:03 [new]
- Overbought/oversold judged by range position, not indicators ~13:05, ~16:01

## Trade examples
- GBPUSD, Feb -> Mar 2017 (pairing only): sell from the daily FVG + bearish OB in premium (red box, Feb), target weekly bullish OB mean threshold in discount (Mar) ~8:26-8:49 [chart]
- GBPUSD, late Mar 2017: rally into the weekly rejection block and above the Feb old high in the top band -> strong selloff to the daily bullish OB mean threshold; then a ~100 pip rally from there to the daily bearish OB that overlapped the premium 50% level ~17:58-19:28 [chart]. Prices on the axis not legible (range roughly 1.20 to 1.27).

## Definitions
- Consolidation range (for this model): 60-day highest body to lowest body ~4:01
- Premium / discount: above / below 50% of the range; recursively applied to each half ~6:16, ~9:22
- Low resistance liquidity run: price moving from one PD array to the opposite one (discount -> premium or reverse) inside the range ~20:03, ~24:52
- One shot one kill: short-term trading, 1 day to 1 week, framed in the last 3 months ~22:29

## Seen only on the charts
- Labels on the daily: Old High & Rejection Block (top, near range top), Weekly Rejection Block, red Bearish OB box (early Feb), Daily Rejection Block, "Daily Bearish Orderblock Premium 50% Level", Daily Bullish Orderblock Mean Threshold, Daily Rejection Block, Weekly Bullish Orderblock Open, Fair Value Gap (mid Mar), Weekly Bullish Orderblock Mean Threshold, large Fair Value Gap (mid Jan), Old Low & Rejection Block (bottom) [7:20]
- Range anchors: red arrows at the early-Dec high body and mid-Jan low body [3:40]
- Shaded pink "Premium"/green "Discount" boxes walk up the range one eighth-pair at a time [9:40, 10:40, 12:20, 17:40, 21:20, 23:00]

## Open questions
- Which day the 60-day window ends on (today vs yesterday), and whether it rolls daily.
- Exactly how deep the subdivision goes (frames show eighths; he says halves "incrementally").
- Whether the bot should require "trend vs consolidation" classification and how (no rule given).
- For index futures, does this daily framework feed an intraday bias, or only multi-day holds?
