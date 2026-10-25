# cc05_003 ICT Mentorship Core Content - Month 05 - Using IPDA Data Ranges (LRKtiysz4nA)
Recorded Jan 12 2017 (stated ~1:20:45) / AUDUSD: March 2017 AUD futures daily (OHLC bars, then candles with volume + open interest), AUD weekly candles, MT4 AUDUSD daily / timeframes: weekly, daily only / 2h02m. Forex case study; the charts are static slides (the picture barely changes after ~1:14, the last ~45 min is talk only). No intraday content.

## Summary
Teaches the IPDA data ranges: the algorithm looks back 20, 40 and 60 trading days for the highs and lows (stops), gaps and equilibrium, and the trader projects 20/40/60 days forward from the start of the month of the most recent obvious "quarterly" market structure shift. Adds futures open interest as a tell for smart money covering at higher-timeframe support. AUDUSD Nov 2016 to Jan 2017 is the worked example. Everything is daily/weekly: a higher-timeframe draw/bias filter for the bot, not an entry model.

## Rules
- Find the most obvious daily market structure shift of the last ~3 months (a "quarterly shift"; one happens roughly every 3-4 months). Don't pick a minor one; go back up to 3 months if needed ~15:57-16:22 [new] [chart]
- Anchor on the first trading day of the month in which that shift happened (Nov 1 2016 in the example), not the shift day itself ~19:15, ~39:03 [new] [chart]
- From the anchor, look back 20, 40 and 60 trading days: the highest high (buy stops) and lowest low (sell stops) in each window are the liquidity IPDA will reach for ~27:50-28:38, ~1:17:37 [new]
- In the same windows, the unfilled FVGs/liquidity voids are fair-value targets and the 50% of the consolidations are equilibrium levels ~17:12-17:58, ~1:18:00 [new]
- Cast forward 20, 40 and 60 trading days from the anchor (vertical lines). Expect a significant daily high/low or turn within those windows (about 20 days; if not, within the next 20 to day 40). It can land a day or two either side; turns are not guaranteed on day 20/40/60 ~29:30-30:16, ~35:51-38:35 [new] [chart]
- From each new forward point, look back 20/40/60 days again for the next targets. When the forward and backward windows overlap, he says "that's when the magic happens" ~42:28-44:12, ~2:01:39 [new]
- Bias: bearish structure -> target the lows of the 20/40/60-day windows; bullish -> the highs. If price rejects a low and breaks structure bullish, that is a new quarterly shift: switch to the highs ~1:23:44-1:24:26 [new]
- Expansion trigger: if every 20/40/60-day high and low has already been run, price must look outside the 60-day range. Expect a large, fast move to the nearest older high/low just beyond 60 days ~28:38-29:30, ~32:28-33:39, ~45:39 [new]
- Sideways day filter: if price sits near the equilibrium (50%) of the 20/40/60-day ranges and both sides have been cleared, expect a range/"Z day" until high-impact news brings manipulation ~1:18:26-1:19:30 [new]
- The 60-day high and low act as the real overbought/oversold levels (no indicator needed) ~1:55:26 [new]
- Higher-timeframe bias persists. Two down days in a daily uptrend are a retracement, not a change ~1:34:51 [new]
- Open interest (futures only): an OI drop of 15% or more while price falls/consolidates into a major HTF support = commercials/"central bank" covering shorts -> bullish. Rising OI into highs = they are selling. A real turtle soup sell should follow a big OI build-up ~58:26, ~1:47:59-1:48:20 [new] [chart] (FX framing; usable on ES/NQ, which publish OI)
- Bullish order block = the last down-close daily candle before the up move. Once price trades above its high, that high is support the banks defend; retraces should only wick slightly below it ~1:05:48-1:09:05 [chart]

## Trade examples
No trade taken; analysis only (AUDUSD, daily).
- Anchor: quarterly shift in the second week of Nov 2016. Price ran equal highs above ~0.7700 (false breakout of the Aug-Oct 0.7450-0.7700 range), then broke structure lower ~14:41-15:05 [chart]
- 20 days forward from Nov 1 ~ late Nov: the consolidation low near 0.7300 (the old October-area low) ~34:03 [chart]
- 40 days forward ~ late Dec: low at 0.7150 (a mid-figure level; weekly support at the Feb/May 2016 levels), then the rally. The actual low printed about two daily bars before day 40 ~35:23-36:38 [chart]
- From the day-40 point, 20 days back gives the mid-December equal highs (~0.7520) as the buy-side draw. 40 days back gives the ~0.7300 late-Nov low as a turning point ~43:16-44:42 [chart]
- Weekly: blue zone ~0.7130-0.7255 = Feb 2016 last down candle (bullish OB) plus the May 2016 lows. Bearish OB = last up week of late Oct 2016 -> upside range 0.7570-0.7580 ~46:25-48:25 [chart]
- Futures OI: peaks in late Sep, mid-Oct and 2nd week of Nov matched price highs (selling). OI slid from roughly 137k to ~85k into late Dec at 0.7150 (read from the chart; much more than 15%) ~59:22-1:04:36 [chart]
- MT4 daily (Jan 2017): bullish OB line ~0.7230. New down candle (Jan 5-6) high 0.7355. Price retraced to 0.7352 (3 pips under), then rallied 0.7380 -> 0.7434, filling the Dec 2016 FVG. It then cleared a "mean threshold" (~0.746). Next targets: equal highs ~0.7520-0.7525, then 0.7570-0.7580, extended 0.7650 (yellow band) ~1:06:35-1:10:17 [chart]

## Definitions
- IPDA = interbank price delivery algorithm ~15:31
- IPDA data range: 20/40/60 trading-day look-back and cast-forward windows (up to 120 days of range in total) ~13:21, ~31:35
- Quarterly shift: the obvious daily structure shift that comes about every 3-4 months. He divides the daily chart at Mar/Jun/Sep/Dec, but the shifts don't have to fall in those months ~16:22-16:46
- Time on the higher timeframe means calendar trading days, not time of day ~1:23:20
- Relative equal highs: tops whose candle bodies sit nearly level count as equal, even when the wicks differ a little ~1:07:26
- Mean threshold of a range: 50% from one candle's open to another candle's close ~1:06:59 (see open questions)

## Seen only on the charts
- The 20/40/60 day labels are drawn as arrows from the Nov 1 red line on the futures bar chart. The day-40 arrow ends at the 0.7150 low area in late Dec [chart 34:20, 35:00]
- The futures chart shows volume bars plus a purple OI line. The blue box over December marks the OI collapse (~85k at the arrow) [chart 49:00, 1:05:20]
- MT4 lines: 0.7434, 0.7380, 0.7355, the "Mean Threshold" ~0.7462, the Bullish Orderblock ~0.7230, and a top line ~0.7525 (equal highs). The Jan 12 candle traded to ~0.7518 [chart 1:05:40]
- Yellow band ~0.7650-0.7665 on the early-Nov up candles = bearish OB / 76.50 objective [chart 1:10:20]

## Open questions
- Trading days vs calendar days: he counts bars (trading days) but also says "calendar days" ~1:23:20. Use trading days (bars).
- Is the anchor the first trading day of the shift month, or the shift bar? He says roll back to the month start, but also casts lines from new turning points. Exercise version: put a line on every month's first trading day ~1:50:28.
- "Mean threshold" here is a multi-candle range (open to close, bodies), not one order block's high-to-low. That may [conflict] with the rules file (MT = 50% of the OB, wicks included). Which candles he uses is not legible.
- How do we decide which window's high/low is the next target when several are open? He implies nearest first, then outward; not stated.
- OI 15% drop: over what period, and measured from which peak? Not specified.
- Applying this to ES/SPY intraday: these windows give the daily draw/bias only. The intraday trigger still comes from the existing session models.
