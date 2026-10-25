# cc07_004 ICT Mentorship Core Content - Month 07 - Short Term Trading Blending IPDA Data Ranges & PD Arrays (YV4fEF4d2wA)
Core Content 2016-17, Month 07 lesson 4 / example: AUDUSD (forex), week of ~20-24 Mar 2017 (dates on chart axis, partly legible) / daily and 4h charts / ~16 min.

## Summary
"Time" = IPDA data ranges (look back 20, 40, 60 trading days); "price" = the PD array matrix (premium arrays above market price, discount arrays below). Frame the 20-day range high/low, split it at 50% into premium/discount, list the unused PD arrays on each side in hierarchy order, and use them as entry points and targets. Example: AUDUSD Tuesday high of week (manipulation template from cc07_003) traded down to close a 4h liquidity void.

## Rules
- Look back 20, 40 and 60 trading days (about 1, 2, 3 months) from today; roll the window forward each day ~00:00:09, ~00:04:00 [chart] [new]
- Primary dealing range = highest high and lowest low of the last 20 trading days; 50% splits premium (above) and discount (below) ~00:07:00, ~00:08:00 [chart] [new]
- If the 20-day low (high) is violated, the next target is the next lower low (higher high) in the 40-day, else the 60-day look back ~00:07:00 [chart] [new]
- PD array matrix order from market price outward, premium side: bearish mitigation block, bearish breaker, liquidity void, FVG, bearish order block, rejection block, old high/low. Discount side mirrors (bullish mitigation block ... old low/high). The algorithm seeks them in that order ~00:01:01-00:02:00 [chart] [new]
- Not every array exists; price may skip straight to an OB or rejection block. Absence does not change setup validity, only reduces choices ~00:02:00, ~00:05:00 [new]
- An array price has already traded into and reacted from is exhausted; use the next one ~00:04:00 [new]
- Bearish: premium arrays are sell/resistance points, discount arrays are targets; bullish the mirror ~00:05:00 [new]
- Short at daily premium arrays -> target taken on a lower TF (4h or 1h) discount array ~00:12:02, ~00:14:02 (same as cc07_003's lower-timeframe target rule) [new]
- Failure swing: if the expected breakout fails (no higher high on Tuesday) and Tuesday breaks down, reverse the analysis and look for shorts in premium ~00:11:02 [new]; note it is a reversal of weekly bias, not of a losing intraday trade (Ep 01 "do not reverse" is about same-session AM losses)
- Mean threshold of an order block measured on the bodies (highest body to lowest body of the OB candles), not wicks ~00:10:02 [conflict: Ep 02 measures MT high-to-low including wicks]

## Trade examples
- AUDUSD, daily then 4h. Monday made a high; Tuesday traded slightly above Monday's high (daily-high liquidity pool raid) and rejected = Classic Tuesday High of Week. After Tuesday broke down, short ideas at 0.7680 (institutional level, at a mitigation block / breaker / short-term old high on the 4h) with objective 0.7605 = bottom of a 4h liquidity void; the void closed "to the pip" ~00:12:02-00:14:02 [chart]. Size, stop and exact entry time not given. 0.7680 box is visible on the 4h chart ~00:10:40 [chart]; the 0.7605 line not legible.

## Definitions
- IPDA data ranges: 20/40/60 trading-day look-back windows (and cast-forward of the same lengths) the interbank price delivery algorithm references ~00:00:09 [chart]
- PD array matrix: premium/discount list of arrays relative to the current market price ~00:01:01 [chart]
- Market price for weekly analysis = Friday's close ~00:08:00
- Institutional price level: round number such as 0.7680 ~00:12:02

## Seen only on the charts
- Slide 1: left panel shows 60/40/20 look back and 20/40/60 cast forward columns; right panel lists the arrays top to bottom: Old High or Low, Rejection Block, Bearish Orderblock, Fair Value Gap, Liquidity Void, Bearish Breaker, Bearish Mitigation Block, Market Price, then the bullish mirror ~00:01:40 [chart]
- Daily chart (~00:07:20): 60/40/20-day columns; pink premium / green discount shading over the 60-day range; old low and a rejection block at the bottom, old high at top; red arrow at the low inside the 20-day window [chart]. Prices largely illegible (~0.74-0.78).
- Daily 20-day close-up (~00:09:40): top-down labels Old High, Rejection Block, -OB MT, -OB; below 50%: +OB, +OB MT, Rejection Block, Old Low [chart]
- 4h chart (~00:10:40): 20-day shading; bracket marking the "Liquidity Void" from a strong up leg; labels Old High, Rejection Block, OB MT, Old High (0.7680 box), Old Low, OB; price sitting at the void's low near the 50% line [chart]
- Final slide overlays the Tuesday High of Week template on the 4h chart, with the Tuesday high at the old daily high and the Thursday low at the discount array ~00:13:40 [chart]

## Open questions
- Is the 50% split taken from the 20-day range only, or from the 60-day range? The daily slide shades the 60-day range, the close-up the 20-day.
- Hierarchy order as spoken (mitigation, breaker, void, FVG, OB, rejection, old high) differs slightly from the slide (FVG above void) - which order does the bot use?
- "Mitigation block" and "rejection block" are not defined here.
- Mean threshold on bodies here vs wicks in Ep 02: pick one or test both.
- Applying 20/40/60 trading days to index futures needs a session calendar (holidays).
