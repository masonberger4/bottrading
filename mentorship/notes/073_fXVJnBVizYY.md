# 073 ICT Mentorship 2023 - Algorithmic Price Delivery & Time Macros Intro (fXVJnBVizYY)
Date discussed: Fri Jul 7 2023 (NFP day). Market: NQ (E-mini Nasdaq-100 Sep 2023). Timeframes shown: 1D, 1h, 15m, 5m, 3m, 1m. Duration ~35 min.

## Summary
Introduces "macros": short (mostly 20-minute) clock windows in which the algorithm starts a run ("spooling") to liquidity or to an inefficiency. Two macros are named with exact times: 09:50-10:10 and 10:50-11:10 ET. A macro gives timing only, never direction; direction comes from narrative (here the NFP profile plus a daily bullish propulsion block). If price does not move during the macro, close the charts for that session.

## Macro / time windows (exact, ET)
| Window | Type | Expected behaviour |
|---|---|---|
| 07:00-09:00 | NY open kill zone | mostly quiet until 08:30 news (~14:24, ~23:16) [chart] |
| 08:30-12:00 | NY AM session (index futures) | session container (~14:36) [chart] |
| 10:00-11:00 | AM Silver Bullet | the main run happened inside it (~14:44, ~24:07) [chart] |
| **09:50-10:10** | macro | 20 min framing the first 20-40 min after the 09:30 equity open; price delivered to buy-side + a premium inefficiency, rebalanced it, then began the run to the opposite liquidity (~19:41-19:46, ~21:14, ~24:37-26:16) [chart] |
| **10:50-11:10** | macro | end of the 10:00-11:00 hour (first 90 min of trading), ~London close peak for FX, last hour before NY lunch; market begins its run for liquidity / inefficiency; here a bullish breaker formed and price rallied (~27:57-29:20) [chart] |
| NY lunch | has its own macro (time not given) | consolidates, runs for liquidity, or reverses (~28:18, ~29:37-29:44) |
| PM, lunch hour, London | more macros exist; times not given in this video (~31:33-31:40) |

## Rules
- A macro is a time window (mostly 20 min, not all) where price begins to "spool": reach for liquidity or for an inefficiency. It does not give direction or bias (~14:54, ~31:45-32:38). [new]
- Macro 10:50-11:10 ET is a valid window for the run to liquidity/inefficiency (~27:57, ~18:14). [new]
- 09:50-10:10 macro refined: it can deliver to liquidity AND an inefficiency first, rebalance it, then start the run to the opposing liquidity; i.e. the macro may mark the reversal, not continuation (~21:14-22:40, ~25:41-26:16) [chart]. Existing rule is consistent; this adds the "two functions" detail. [new]
- Filter: if the macro produces no movement toward the expected draw, close the charts and skip that session (maybe the whole day) (~30:51-31:30, ~35:28-35:39). [new]
- Macros only work with narrative: identify liquidity and inefficiency above and below price first (previous day H/L, session H/L, last 3 days H/L, previous week H/L) (~7:47-8:21). [new]
- NFP profile: the side taken first right after 08:30 is usually the false run; then the opposite side is taken, then the real move. Three variants: up-down-up, down-up-down, or chop (~10:42-11:41, ~26:27-26:46). [new]
- On NFP, CPI and FOMC days breakers do not give the cleanest rejections; price may trade through them (~4:36-5:20). [new]
- Opening range: first 30 min after 09:30 but can be useful after 20 min; liquidity taken outside its H/L hints where price goes next (~25:00-25:23). [new]
- Lunch does one of three things: consolidate, run for liquidity, or reverse (~29:35-29:44). Consistent with existing lunch notes.
- Treat wicks as gaps: midpoint (CE) of a daily wick is a key level (~1:25, ~9:56). Already in rules (Ep 08).

## Trade examples
- NQ Jul 7 2023, long bias. Daily: Thursday Jul 6 down-close candle dug into a prior down-close candle (Jun 29) but stayed above half of its body = bullish propulsion block. Levels: its wick high 15202.75 and open 15161.00; CE 15182.00 (labelled "Daily +OB Premium Wick C.E.") [chart] (~1:14-3:08, ~9:17).
- Hourly FVG (blue, ~15175-15192) inside it; hourly premium FVG (orange, ~15300-15340) above [chart].
- 1m sequence [chart]: 08:30 NFP spike to ~15313 into the orange FVG (buy-side), dump to sell-side at ~15185 near 09:00 (relative equal lows / into the blue FVG), chop, then during 09:50-10:10 rally into the pink "Buyside Liquidity" box (~15263-15275), stall, drop during the Silver Bullet to ~15179 at ~10:37 (CE of the daily propulsion block and of the hourly FVG). 5m/1m bullish OB (green, ~15217-15222, high to open of the last down-close candle) held; bullish breaker (light blue, ~15232-15245) formed in 10:50-11:10; rally to ~15358 by ~13:30 into/through the orange FVG.
- Executions were toggled on the chart at ~34:40 but no frame shows them legibly; entries, stops and size not readable. He calls it a market maker sell model (~34:56).

## Definitions
- Macro: a short list of directives the algorithm runs in a fixed time window, seeking liquidity and/or inefficiency (~25:41-25:56).
- Spooling: price being cast away from its current location toward a draw, like line running off a fishing reel (~31:45-32:29).
- Propulsion block: an order block that trades into an earlier OB but does not close below half of the earlier candle's body; levels are its high (wick) and open, not the body's mean threshold (~1:55-3:08).
- Bullish OB variant: last down-close candle measured from high to open (~11:47-11:54).

## Seen only on the charts
- Macro boxes drawn as labels "09:50 To 10:10" and "10:50 To 11:10" on the 1m chart.
- The 09:50-10:10 top (~15275) sat inside the pink buy-side box; the 10:35 low touched the CE line almost exactly.
- An inversion FVG is mentioned (~12:45) but not marked clearly.

## Open questions
- Lunch, PM and London macro times are not given here; need later videos.
- Is a macro "failure" judged by range, displacement, or reaching a specific level? No threshold given.
- Exact entry for the long (green OB vs breaker) and stop are not stated.
- Propulsion block "half of the body" - which candle's body (earlier OB) - our reading.
