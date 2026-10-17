# cc08_008 ICT Mentorship Core Content - Month 08 - Integrating Daytrades With HTF Trade Entries (1MnfiqKx5Uo)
April 2017 content, lesson 8 of the ICT day trading model (~0:06) / forex (pips, Forex Ltd demo platform) / daily candle schematics only / 23m. Slides only: power-of-three candle diagrams with "0 GMT", "Buy At 0 GMT", "Sell At 0 GMT Open Plus 20 Pips", "Use 5 Day ADR As Stop". No real chart, no trade.

## Summary
A low-effort way to enter higher-timeframe trades (or a one-day range trade) without watching the London kill zone: once the daily chart has already reacted from a discount (or premium) PD array, place the order at the next 0 GMT daily open (or a few pips beyond it toward the expected Judas swing), with a stop one 5-day average daily range away, and hold to the HTF objective.

## Rules
- Power of three on the daily candle: bullish day opens near the low, small wick below the open, expansion up, close a bit off the high; bearish is the mirror. Open and close sit at opposite extremes of the day ~1:34-2:33 [chart] (already in rules as midnight-open PO3, Ep 04)
- Two "reset" openings monitored daily: 0 GMT (daily candle open on his platform) and midnight New York ~4:02-4:31, ~5:46-6:08 [chart] [new] (rules only use midnight / 08:30 / 09:30)
- Precondition for longs: on the daily chart price has ALREADY traded into and respected a discount PD array (e.g. bullish order block) and shown willingness to rally away, the day before the trade day ~8:56-10:06, ~11:26-11:38 [new]
- Precondition for shorts: price has already hit a premium PD array (bearish OB, or a turtle soup of an old high) and failed to go higher the previous session ~9:19-9:34, ~15:19-15:54 [new]
- Confluence that makes it a "loaded deal": daily PD array respected, institutional order flow bullish, quarterly shift still bullish, bullish seasonal tendency, and the day is Monday, Tuesday or Wednesday ~11:07-11:26, ~14:26-14:46 [new]
- Long entry: buy at the 0 GMT open, or with a limit 10-20 pips below it to catch the Judas swing ~12:49-13:01, ~20:02-20:16 [chart] [new]
- Short entry: sell at the 0 GMT open, or a limit 10-20 pips above it (slide: "plus 20 pips") ~15:56-16:10, ~19:02-19:24 [chart] [new]
- Split entry so the move is not missed: half the planned size at the open, the other half at the +/-20 pip limit ~18:07-18:56 [new]
- Stop = 5-day average daily range measured from the entry (long: entry minus ADR5; short: entry plus ADR5) ~13:03-14:07, ~16:15-17:07 [chart] [new]. Example: limit sell at 1.0500 with a 50-pip ADR -> stop 1.0550 ~16:48-17:07 (captions garble the numbers)
- Rationale: after a daily premium/discount reaction, a 60-70 pip move against the open before the close is unlikely ~17:23-17:30, ~19:49-20:46
- Targets: the higher-timeframe objective (next premium PD array for longs); hold for several hundred pips, or close same day if used as a one-day range trade ~14:09-14:15, ~17:56-18:05 [new]
- Wide stop is acceptable because the target is HTF; this is not a small-risk 20R day trade ~13:22-13:52
- ADR5 can be approximated with a 5-period ATR on the daily ~22:12-22:44 [new]

## Trade examples
None. Homework: find three recent examples (one buy that worked, one sell that worked, one failure), noting how far price went beyond the 0 GMT open relative to the 5-day ADR ~20:49-23:33 [chart]

## Definitions
- IPDA true day open / reset: the 0 GMT daily open (start of the daily candle on his platform); "true day" when trading London is the NY midnight open ~5:46-6:08 [chart]
- London protraction / Judas swing: the early move against the day's direction below (bullish) or above (bearish) the open to seek liquidity ~10:37-10:57
- Central Bank Dealers Range (CBDR): closes at 0 GMT; its standard deviations hint at how far the protraction goes ~12:15-12:47 (not defined here)

## Seen only on the charts
- Slides mark the unknown protraction distance with a "?" box between the 0 GMT open and the stop; the stop line sits at the tip of the wick in the diagram ~13:20, ~16:20 [chart]
- The final sell slide drops "plus 20 pips" and reads simply "Sell At 0 GMT Open" ~19:40 [chart]

## Open questions
- 0 GMT is 19:00 ET (EST) / 20:00 ET (EDT); on index futures that is near the Globex open, not the midnight open used in rules. Which open should a futures bot use? (He says the method works for anyone not awake for London.)
- Index equivalent of "10-20 pips" offset and how ADR5 compares to typical ES stops; ADR5 on ES is ~50-80+ handles, far wider than the bot's intraday risk.
- "Respected a discount PD array" is not quantified (close off the array? up-close day?).
- Daily bias inputs (quarterly shift, seasonal tendency, IOF) are referenced but not defined here.
