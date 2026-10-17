# cc06_007 ICT Mentorship Core Content - Month 06 - Keys To Selecting Markets That Will Move Explosively (Hoo_wTMgdcY)
Lesson 7 of the February 2017 swing-trading month (~0:14) / no specific market traded. Slides show the CRB vs USD monthly (1991-2011), an unnamed futures COT and open-interest chart (Jan 2016 - Feb 2017), a seasonal chart and Williams %R / 27m. All slides, no trade.

## Summary
Eight "hallmarks" that raise the odds a swing trade will be explosive (one-sided, large range) rather than sluggish. They are filters on market selection and conviction, not entry triggers:
1. trending major markets
2. intermarket confluence
3. COT commercial hedging
4. open interest
5. seasonality
6. volatility contraction
7. contrary news headlines
8. Williams %R sentiment

Lesson 8 will turn these into the step-by-step swing model.

## Rules
- Hallmark 1, trending major markets: of the four asset classes (interest rates, stocks, commodities, currencies), at least two must be trending, not consolidating. Specifically, one of {stocks, commodities} and one of {currencies, interest rates} must trend; all four is ideal ~0:53-1:28, ~7:58-9:35 [chart] [new]
- Hallmark 2, intermarket confluence. Bullish dollar: commodities sit at resistance, fail to make higher highs (or make false breakouts), break lows easily, and EURUSD/GBPUSD/AUDUSD/NZDUSD sit at resistance. Bearish dollar is the mirror; commodity lows taken out then become turtle-soup longs. Check several commodity sectors (grains etc.), not just the CRB ~1:45-3:30, ~10:34-12:43 [chart] [new]. Forex/commodity-specific; the index analogue is not given.
- Hallmark 3, COT hedging: take the commercials' net position over the last 12 months, and use the midpoint of its high-low range as a new zero line (ignore the real zero line). Above the midpoint = commercials buying = bullish; below = bearish. A short while commercials are above the midpoint is "at odds"; wait for it to drop back below ~3:34-3:56, ~13:18-17:55 [chart] [new]
- Hallmark 4, open interest: a 10-15%+ drop in open interest while the commercial net line rises toward zero = commercial short covering = bullish, explosive move expected. A 10-15%+ rise in open interest while the commercials sell more (red line falling) = bearish ~18:08-19:50 [chart] [new]
- Hallmark 5, seasonality: take swings when the seasonal tendency agrees with the trade direction ~5:04-5:19, ~20:14-20:56 [chart] [new]
- Hallmark 6, volatility contraction: an inside bar (lower high and higher low than the prior candle, judged on the bodies, not the wicks; candle color irrelevant), or the smallest range of the last 3 days, or of the last 7 days. Any timeframe (monthly/weekly/daily). Expect a large-range candle on the next bar or the one after. It gives no direction and no timing, only the setup ~5:26-6:24, ~21:24-23:27 [chart] [new]
- Hallmark 7, news: when you want to buy, bearish headlines (explaining why price fell) are fuel. When you want to short into a premium level, bullish or record-high headlines are fuel ~6:27-7:27, ~23:30-25:31 [new]
- Hallmark 8, sentiment: daily 15-period Williams %R. At or below the 50 level = oversold, a buying area; above 50 = overbought, a selling area. When hovering near 50, side with whichever extreme it left most recently ~25:36-26:37 [chart] [new]
- More hallmarks aligned = higher odds of a fast, one-sided move; five aligned is already a strong case ~20:56-21:21 [new]

## Trade examples
None. The COT/OI example is an unnamed market. Commercial net position went from about 0 in Jan 2016 to about -350k in Jul 2016, then back up to about -120k by Jan-Feb 2017. That is above the 12-month midpoint (~-180k) from about Dec 2016 = buying while still below the real zero. Open interest fell from ~520k to ~400k in Nov-Dec 2016 as the red line rose = bullish ~15:59-19:30 [chart].

## Definitions
- Commercials: the producers/holders of the underlying (growers, manufacturers, banks for currencies). They hedge using the prior 12 months of prices ~13:23-14:23
- Adjusted COT zero line: the 50% of the commercials' 12-month net-position range ~15:25-15:57 [chart]
- Inside bar: lower high and higher low than the prior candle (bodies, per him) = volatility contraction ~21:47-22:05 [chart]

## Seen only on the charts
- COT slide: blue box around the 12-month range with a thick black midpoint line at about -180k. The red fill marks the stretch below it [chart].
- OI chart: purple line peaks ~650k in Jul 2016 and falls to ~400k by Nov 2016, with a sharp drop at the right edge (Feb 2017) [chart].
- Seasonal chart: two lines (likely 5- and 15-year averages; the legend is not legible) rising from Aug/Sep into Dec-Feb [chart].
- The Williams %R panel spans Mar 2015 - Feb 2017 with ~100 points, so it looks weekly, not daily. The last value is -2.3 (overbought) [chart].

## Open questions
- "Bodies, not wicks" for the inside bar, yet the drawing labels lower high / higher low on the wicks. Which one does a bot test?
- The Williams %R threshold is "50", but the indicator runs 0 to -100. Presumably -50. The daily vs weekly mismatch with the slide is unresolved.
- How are "trending" vs "consolidating" defined for an asset class? No measure is given; lesson 8 may define it.
- For SPY/QQQ, the COT/OI equivalent would be the ES/NQ commercial (dealer/asset manager) data. Which category maps to "commercials" in the financial futures report is not covered.
- Hallmarks 7 (headlines) are discretionary and not automatable as stated.
