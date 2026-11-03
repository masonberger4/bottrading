# ch21 ICT Charter Price Action Model 7 \ Sell-side Low Resistance Liquidity Runs (_7oZZ2bhEGU)
Recorded 2018 (Charter) / slides + USDCHF weekly->15m / 92 min. Captions only.
Source tier: Charter. 2023 wins on conflicts. FX units.

## Summary
Model 7 (universal, any style): trade only the sell-side delivery of a MM sell model or MM buy model. Stage = HTF liquidity draw; setup = sell-side MM profile; pattern = return to fair value. Core is the "liquidity distribution profile": a qualified market structure shift is a break of the HIGHEST reaccumulation-of-longs swing low on the buy side of the curve, after the buy-side liquidity / premium array has been taken. Then expect sell stops below it to be run, a return into the down-close candle bodies of that swing low (fair value), and sell from there. If price blows through the first (lower) reaccumulation too, expect a larger distribution leg. Take profits at the targeted sell-side pool.

## Rules
- Range of opportunity = between the price where the draw is identified and the targeted sell-side liquidity (e.g. equal lows) ~1:54-2:49
- MM sell model: two key points = point 1 (return to original consolidation) and point 2 (second reaccumulation of longs) on the buy side; the curve midpoint is carried right ~2:49-4:27
- On lower TFs (1h, 15m) price need not return to point 2; if it doesn't, the move down is larger ~4:27-4:56
- Qualified MSS = break of the highest reaccumulation-of-longs swing low that formed before the premium array / buy-side liquidity was run; minor short-term breaks are NOT the MSS ("if it doesn't fit this criteria it is not a break in market structure") ~10:32-13:12, ~16:10-16:37
- After the break: sell stops below that swing low get run, then price returns into the bodies of the down-close candle(s) of that swing low (mitigation of the longs) -> sell there ~7:38-8:36, ~12:16-12:40
- If there are 3 accumulations, always use the highest one ~11:26-12:16
- Breaking also below the first (point 1) reaccumulation = heavy distribution -> larger, longer price swing, not just a stop run ~10:32-11:57, ~33:11-34:04
- Low-risk short at the smart money reversal needs high experience; may "fish" a very small position near an expected long-term high ~10:32-11:26
- HTF narrative governs: large funds frame from daily up (monthly/weekly/daily); weekly profile refined to daily, daily refined to 4h/60m; fair value on 4h/60m = down-close candle(s) ~26:35-30:30
- Day trade timing example: sell stops run Thursday/Friday, ignore Sunday, Monday rally into the down-close bodies = sell, then use power of three / day-trading concepts ~30:30-31:25
- Premium array for the return can be weekly bearish OB, weekly FVG / liquidity void; a bearish OB with a prior stop run to its left is more likely to hold than a new higher high ~31:53-32:44
- If you cannot read the profile, do not touch the market ~24:40-25:07
- MM buy model sell side: sell at point 1 (return to consolidation, or a FVG on the swing away) and point 2 redistribution; cover majority/all at the sell-side pool (may bounce, consolidate, or continue) ~48:25-51:02, ~58:26-61:19
- If stopped and price runs back above the equal highs, there is no MM buy model; wait ~51:31-52:00
- SMT as basis for accumulation of shorts (e.g. EURUSD higher high, GBPUSD fails) ~58:48-59:49
- Stick with one model and one or two markets ~53:51-54:16, ~55:33-56:26
- Do not trade against institutional order flow (HTF bias); counter-trend expectations are limited ~69:10-70:25
- Level calibration: weekly OB open 0.9547 -> 0.9540/0.9545 (5/0 levels) ~66:50-67:30
- Rejection block = lowest close of the down-close candle in a cluster of wicks (0.9542) ~71:24-73:13
- Grading a price swing: origin, level 1, 2, 3; by level 3 price often skips opportunity on the way to terminus ~75:48-77:03
- Balanced price range: once both buy-side and sell-side have been offered across a range (e.g. 0.9747-0.9723), it acts as natural support/resistance ~78:54-79:34
- Grade targets 10/20/30 pips below a calibrated old low (0.9575 -> 0.9565/0.9555/0.9545) ~87:13-88:20
- Everything is rebalancing; bias from the weekly, entry from the daily ~89:35-91:01

## Trade examples
- USDCHF 2018 Q3-Q4: weekly bullish OB 0.9547 (Sept 16 low) in the dollar's Sept-Oct seasonal bullishness; MM buy model to equal highs; daily rejection block 0.9542; 4h/1h/15m redistribution sells to terminus; 30-pip grade below 0.9575 = 0.9545 (low printed 0.9542) ~62:10-91:01

## Definitions
- Liquidity distribution profile: pairing of buy-side and sell-side delivery across the curve of a MM model
- Terminus: the predetermined final target of the price swing
- Balanced price range: range where both sides have been delivered

## Open questions
- MSS definition (highest reaccumulation low after the premium array is hit) vs 2023 MSS: [conflict check] switch `mss_definition = {2023_default, charter_highest_reaccumulation}`
- Grade targets 10/20/30 pips: index mapping is our interpretation (e.g. ES points); switch
- Rejection block = lowest body close among wick cluster: switch to add as PD array
