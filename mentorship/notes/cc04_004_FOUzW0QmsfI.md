# cc04_004 ICT Mentorship Core Content - Month 04 - Mitigation Blocks (FOUzW0QmsfI)
2016-17 Private Mentorship, December 2016, "ICT Teaching 3.1 of 8" (slide footer). Market: forex only (EURUSD H1 and M30, 10-24 Mar 2016). Duration ~15 min: ~9 min of line-drawing slides, then one chart example. Frames viewed: 7.

## Summary
Defines the mitigation block: after a failure swing (lower high, no stop run above the old high) breaks the swing low between the two highs, the last down candle at that swing low becomes resistance. Longs bought there are underwater and sell to break even when price returns. Sell the return, target the next lower low / higher-TF support. The example chains several mitigation blocks on the way down to the 50% of a liquidity void.

## Rules
- Context first: a bearish (or bullish) higher-TF scenario, with price rallying into an anticipated resistance (old high, old low, bearish OB, breaker...) ~1:02-2:08 [chart]
- Bearish setup ("M pattern"): high A-side, pullback to swing low A, rally to a LOWER high B (failure swing, does not take out the first high), then a break below low A = market structure shift ~2:42-3:12 [chart] [new]
- Mitigation block = the last down candle inside swing low A (the candle before the short rally to B). When price returns to it, sell ~4:07-5:06, ~7:31-8:03 [chart] [new]
- No time limit between forming low A and breaking it ~4:32-4:44 [new]
- Target: run the sell-side below the new low C, and potentially the higher-TF support (old high/low, bullish OB). Close the whole trade at that support and wait ~8:07-8:53 [new]
- Repeat on each lower leg: every new short-term low that is broken gives a new last-down-candle mitigation block to sell into (stair-step selling of rallies) ~7:08-8:03, ~11:47-12:10 [chart] [new]
- Zone = the whole down candle (body and wicks), not just its low. Entry anywhere in it; stop above the candle's high ~13:51-14:11 [chart] [new]
- Hallmark: on the retest, price may overshoot slightly but should not violate the down candle's body ~12:31-12:37, ~14:29-14:35 [new]
- Bullish mirror (stated in one line only): buy declines in bull markets ~0:55-1:00

## Trade examples
- EURUSD H1, 16-23 Mar 2016 ~10:05-13:05 [chart]: a big up move left a liquidity void. He marks its equilibrium (50% of the bodies, open to close) at 1.1148 as the final target. After a high near 1.1340, a failure swing broke the swing low. Orange lines mark successive mitigation-block levels at 1.1306, 1.1262 and 1.1232 [chart; read from axis]. Each retest overshoots a little, stays inside the candle body, then breaks to a new low. Price reached the 1.1148 mean threshold, then turned up.
- Same move on M30 ~13:12-14:45 [chart]: short at 1.1262 (inside the last down candle), stop above that candle's high 1.1289, about 20 pips of drawdown, then a clean break lower to the void's mean threshold. He did not give a size.

## Definitions
- Mitigation block (bearish): the last down-close candle in the swing low between a high and a lower high (failure swing). Once that low is broken, the candle's range is a sell zone ~3:39-5:06 [chart] [new]
- Points A/B/C (slide): A = swing low, B = lower high, C = new low after the break. Longs from A to B lose money on B to C and mitigate it at A. The result is either a retest of C or a deeper move to support ~5:29-6:06 [chart] [new]
- Liquidity void equilibrium: 50% of the void measured on bodies (open/close) ~10:17-10:31 [chart]
- "Support broken turns resistance" = buyer's remorse at the old low ~8:57-9:24

## Seen only on the charts
- In the M slide, B is clearly lower than the first high, and the break of A is a plain close through, with no FVG required.
- In the EURUSD example the mitigation levels sit about 30-45 pips apart, and he drags a line to each new broken low.

## Open questions
- Mitigation vs breaker: the only stated difference is the lower high (no stop run above the old high). A coder needs a rule: if B > first high, then breaker (cc04_005); else mitigation block.
- "Last down candle" when the low is made of several down candles: is it the last one before the up move, or the lowest one? The slide does not say. cc04_005 picks the extreme candle for breakers.
- Is a close below low A required, or does a wick through count? He says "break below that old low", without saying close or wick.
- He gives no invalidation besides the stop above the candle high. Does a body close above the candle high kill the block?
