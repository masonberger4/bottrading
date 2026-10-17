# cc02_008 ICT Mentorship Core Content - Month 02 - Market Maker Trap False Breakouts (pv2-R-STviA)
Recorded October 2016 ("October 2016 - ICT Teaching 8 of 8"), 2016-17 Private Mentorship. Market: EURUSD (forex), 15m and daily. Duration ~20 min. Prices are spoken without the leading "1." (e.g. "108.55" = 1.0855).

## Summary
In a bullish market, each consolidation's break BELOW its low is a false breakout: smart money buys the sell stops there, then reprices up to the buy stops above the next old high, where it exits longs. Repeated "sweep below range -> rally through highs" reveals the bullish profile (mirror for bearish). Measured moves from the sweep lows projected the next highs, which met a daily bearish order block.

## Rules
- False breakout ABOVE a consolidation is expected in a bearish market (runs buy stops, then down); false breakout BELOW is expected in a bullish market. ~01:00-01:19, ~02:25-03:05 [new]
- Breakout traders bracket the range: buy stops above the high (long breakouts + short stops), sell stops below the low (long stops + short breakouts). Market makers drive price to the side that fits their bias. ~03:14-04:04, ~02:05 [chart] (consistent with buy-side/sell-side liquidity)
- Bullish model: sweep of sell stops below the consolidation low = smart-money long accumulation; exits are paired with buy stops above the next old high / equal highs. ~04:38-07:27 [chart]
- Once a sweep below a range has been followed by a rally, expect EVERY later drop below a consolidation to be a false breakout and a buy, until the pattern changes. ~15:57-16:20 [new]
- Bias read: watch which side of each consolidation price reaches for and where it goes afterward; repeated sell-stop raids followed by expansion up = bullish profile. ~14:28-14:44, ~19:03-19:21 [new]
- Draw on liquidity: the nearest untapped liquidity with the least resistance gives the directional bias. ~13:07-13:22 (consistent with draw on liquidity in the rules file)
- Old-high liquidity sits just above candle BODIES (most volume), not necessarily above wicks; targets can be the body highs. ~09:03-09:24, ~09:53-09:58 [chart] [new]
- Clean (equal) highs with no other voids/pools above are the next objective. ~07:43-08:05 [chart] (consistent with relative equal highs as magnets)
- Smart money buys a little higher on each successive sweep (stacked entries) and scales out at each buy-stop pool. ~10:00-10:14 [chart]
- Measured move: the leg from the first sweep low to the first high, added to the next sweep low, projects the next high (1.0875 -> 1.0925; 1.0885 -> ~1.0980). ~16:41-18:03 [chart] (rules file has "measured move" from Ep 08; this anchors it on sweep lows) [new detail]
- Higher-TF confluence: the projected high coincided with a daily bearish order block (1.0990). ~18:06-18:19 [chart]

## Trade examples
- EURUSD 15m, 21-28 Oct 2016 (bullish model). Range 1 (21-25 Oct, grey box ~1.0860-1.0900); sweep below to ~1.0852 on 25 Oct (cyan box "below 108.55"), rally above 1.0900. Range 2 (25 Oct, ~1.0885-1.0905); sweep to ~1.0875 (cyan), rally to the clean highs then 1.0940 ("109.40", body highs) swept on 26 Oct. Range 3 (26-27 Oct, ~1.0890-1.0950); sweeps to ~1.0890 (blue) and 1.0885 (cyan, "108.85"); rally to 1.0945-1.0950 on 28 Oct, red band "Buy Stops Used To Pair Long Exits". ~05:40-11:40 [chart]
- Measured moves (red boxes): first leg from the 1.0852 sweep to ~1.0905 high; same size from the 1.0875 re-entry reaches ~1.0925. Larger leg 1.0850 -> 1.0945 added to the 1.0885 sweep projects ~1.0980, hit; ultimately 1.0990. ~16:40-18:03 [chart]
- EURUSD daily (Sep-Oct 2016): downtrend from ~1.1250 to ~1.0850; red line 1.0990 at the bearish order block (down candles of 13-20 Oct), thick red line ~1.0965; 27-28 Oct up candle reaches ~1.0990. ~18:00 [chart]

## Definitions
- False breakout: a move beyond a consolidation's high/low that only runs the stops there and reverses; a market-maker trap. ~00:46, ~15:03-15:09
- Breakout traders / neophytes: bracket ranges with stop entries, accept many losses to catch a trend. ~01:26-02:03
- Market efficiency paradigm: think like the liquidity provider; buyers rest above old highs, sellers below old lows. ~06:50, ~14:06-14:17

## Seen only on the charts
- "What's In Here?" callout (08:00) points at the 20 Oct consolidation ~1.0930-1.0935 under the late-Oct high: a red line there marks the buy-side target; checkmark when hit on 26 Oct. [chart]
- "Body Of The Candle Most Volume - Liquidity Above It" label at ~1.0940 (26 Oct). ~09:40 [chart]
- The 15m chart is in a daily DOWNTREND (higher-TF bearish) while the intraday model is bullish into a daily bearish OB; i.e. a retracement up into premium. ~18:00 [chart]

## Open questions
- How is "the market is bullish" established before the first false breakout? Here it is inferred only after a sweep and rally; the daily trend was down.
- When does the "every drop below a range is a buy" assumption end (e.g. reaching the daily bearish OB)?
- Consolidation detection: minimum duration/range for a box; boxes here span hours to days on 15m.
- Entry/stop for the false breakout are not specified (no order block or FVG entry shown); a coder needs to add e.g. MSS + FVG/OB entry with stop under the sweep low.
- Forex only; ES application would use the same range-sweep logic on intraday ranges.
