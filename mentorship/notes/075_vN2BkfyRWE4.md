# 075 ICT Mentorship 2023 - Deep Dive Into Institutional Order Flow (vN2BkfyRWE4)
Recorded Jul 16 2023; reviews NQ (E-mini Nasdaq) week of Jul 10-14 2023. Charts: weekly, daily, 1h, 15m, 5m, 4/3/2/1m. 1h50m. First ~19 min is a rant against DOM/footprint tools (no rules).

## Summary
"Institutional order flow" = reading price action (candle bodies) off PD arrays toward a predetermined draw on liquidity, not DOM/footprint. Case study: weekly mitigation block as weekly target, daily propulsion block as support, 1h breaker / balanced price range, CPI day lunch macro long, then Friday (TGIF) PM short to sell-side using breakaway and measuring gaps.

## Rules
- Bias first: weekly expansion sets the week's bias; each daily candle expected to gravitate to the weekly draw ~31:00 [chart]
- Mitigation block (high, low, higher high, no lower low; the down candle at the low) = weaker than a breaker, can be traded through; use it as a TARGET, not an entry ~21:40-22:40 [new][chart]
- Propulsion block: a down-close candle (bullish OB) that digs into an earlier bullish OB. Valid while no daily CLOSE below its mean threshold (wicks through MT are allowed) ~28:00 [new][chart]
- Wicks/tails are gaps: the CE (50%) of a wick is a reaction level; graded 75% / 50%. In a bullish context, retraces into an upper wick should not close below its 50% ~29:00, ~1:04:00-1:05:20 [new]
- MSS on the 1h only needs price to trade above a short-term high after sell-side is taken; no close required ~33:20 [conflict with Ep02/Ep05 "displacement"/body emphasis; he says a close is not needed] [chart]
- Read bodies, not wicks: bodies refusing to close inside the PD array = confirmation; bodies form the "real" relative equal lows/highs ~34:00, ~47:50
- Order block validation (bullish): after MSS, mark the OPEN of the last down-close candle before the run. The first time price trades above that open = "change in the state of delivery"; only then is it a valid bullish OB, and its low must not be violated ~1:16:40-1:19:00 [new][chart]
- If that low breaks, wait for a new MSS and a new CISD; if stop below it is too wide, wait for an FVG/breaker/IOFED instead ~1:19:20-1:20:00 [new]
- Bullish order flow core rule: down-close candles should support price; any short-term low taken out is a stop run that should reverse immediately (mirror for bearish) ~1:21:40-1:22:40 [new]
- Buy only at/below equilibrium of the current dealing range (low after CISD to the range high); above 50% = premium, lower odds ~1:23:00-1:24:00 [chart]
- Stop placement: don't put a long stop just under a random swing low; expect the algorithm to sweep it, especially near equilibrium ~1:25:00, ~1:31:00 [new]
- Inversion FVG (IFVG): a bearish FVG in a down-leg that price later closes through becomes support after a CISD; enter on retrace to it/its CE ~1:27:00-1:31:40 [new][chart]
- Balanced price range: once price breaks above a high that was previously sold off from and retraced, no reason for price to return below the range low; stop can sit there; he is comfortable with stop below 75% of that range ~54:20-55:20, ~1:07:00 [chart]
- First FVG after a run starts (out of consolidation / time distortion) = breakaway gap, should stay open; if traded into, treat as IOFED (partial entry) and must not close beyond its CE ~58:00, ~1:44:40-1:45:00 [chart]
- Measuring gap: FVG roughly halfway between the start and the expected draw; should not be filled ~1:46:00 [chart]
- Fib from broken old high to the draw: consolidation tends to form at its 50%, stop hunts in lower quadrant, surge in upper quadrant ~1:35:00-1:36:40 [new][chart]
- NY lunch macro: after an AM run up, expect a run on the first post-news swing low (sell stops of the 8:30 longs) ~1:10:00 [new][chart]
- Time distortion: chop between session windows (e.g. 12:00-14:00) is not a signal; wait for 14:00 then displacement ~1:40:00, ~1:44:00 [new][chart]
- PM macro 14:50-15:10 spools price toward un-purged liquidity (7:00, 8:30, 9:30-11:00 lows) ~1:45:00 [new][chart]
- TGIF: Friday after a strong bullish week, expect a 20-30% retracement of the weekly range from the week's high, valid once the week's high is confirmed by a bearish shift ~1:40:00-1:41:20 [new]
- Use the higher-TF PD array (here daily propulsion block high/MT/low) noted on the execution chart; act only when wrong (bail) ~46:00-47:00

## Trade examples
- NQ weekly: draw = weekly mitigation block ~15,693.75 (blue line), above daily relative equal highs; reached and closed on it Fri Jul 14 ~25:00 [chart]
- NQ daily propulsion block shaded ~15,050-15,300 (1h view); Monday low formed at its CE; price swept 1h relative equal lows, broke a short-term high, retraced to the block's MT ~33:00-36:00 [chart]
- Jul 12 (CPI 8:30) 5m: BISI at 8:30 ~15,318-15,365; breakaway gap ~15,318-15,344; 1h breaker line ~15,360 (Jul 7 high). AM high ~15,507.75 ~10:15; lunch macro dropped to ~15,344 ~11:58, sweeping post-news lows but bodies held the breaker ~1:09:00-1:12:00 [chart]
- Jul 12 1m long: CISD line ~15,370 ~12:00; dealing range 15,344-15,507.75 (25% 15,385, EQ 15,426, 75% 15,466.75). Down-close candle opens (green lines) supported each leg; IFVGs ~15,388-15,407, ~15,412-15,420, ~15,441-15,449 used as footholds; ~15,466 by 14:15 ~1:21:00-1:31:40 [chart]
- Jul 12-13 15m: fib 15,507.75 (old high) to 15,687.50 (target); 75% 15,552.75, 50% 15,597.75, 25% 15,642.50 ~1:35:20 [chart]
- Jul 14 (Fri) 5m: 9:30 rally from ~15,720 to ~15,858; IFVG ~15,815-15,830; IOFED short ~15,800 ~12:10; BISI 15,722-15,755 = "time distortion inside BISI" until 14:00; sell-side liquidity 15,680 (Jul 13 evening low) ~1:38:40 [chart]
- Jul 14 1m PM short: after 14:15, breakaway gap ~15,741-15,749; retrace to ~15,729 at ~14:55 (2:50-3:10 macro), pink left-side FVG ~15,718-15,721, measuring gap ~15,711-15,715; low ~15,665 ~15:00-15:50, through 15,680 sell-side ~1:43:20-1:47:00 [chart]. No entries/size stated; NQ chosen over ES for cleaner inefficiencies.

## Definitions
- Sell-side delivery / buy-side delivery: a price run high-to-low (or low-to-high), as opposed to sell/buy-side liquidity ~55:00, ~1:26:00
- Change in the state of delivery: first trade through the opening price of the last opposite candle before an MSS ~1:16:40
- Mitigation block, propulsion block, IFVG: see Rules
- Time distortion: back-and-forth price between macro/session times ~1:47:00

## Seen only on the charts
- Labels: "ICT +Breaker", "Change In The State Of Delivery", "IFVG", "IOFED", "Time Distortion Inside BISI", "2:50 To 3:10 Macro", "NY Index PM Session" (~14:00-15:15 box), "Buyside Liquidity NY Lunch Macro".
- Orange box on 1h (~15,365-15,505, Jul 12) = balanced price range.
- Gradient lines drawn inside the Friday BISI (25/50/75).

## Open questions
- CISD crossing: trade through the open vs close above it? He says "crossed" (trade-through).
- Which "short-term low" counts for IFVG/stop-run logic on 1m is not defined numerically.
- TGIF 20-30% measured on wick range of current week (high to week's low?) - he says high-to-low of the week.
- No explicit entry, stop or size for either trade; examples are hindsight reads.
