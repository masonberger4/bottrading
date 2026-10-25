# cc07_007 ICT Mentorship Core Content - Month 07 - Intraweek Market Reversals & Overlapping Models (jvc105qaCJs)
Date discussed: week of Mon 27 - Fri 31 Mar 2017 (recorded that weekend) / market: GBPUSD (forex only; no index example) / timeframes: daily, 4h, 1h / duration ~28m.
Part of the 2016-17 "short-term trading" module (lesson 7). Concepts are weekly-profile level; for an index-futures day-trading bot they work as a weekly context filter, not an entry model.

## Summary
An intraweek market reversal profile: Monday/Tuesday move fast and far in one direction (well above the recent average daily range), reach a higher-timeframe PD array (here a daily bullish order block's mean threshold), and the week then reverses, often around the Tuesday-Wednesday changeover. Reversals happen where two trading models disagree (short-term/one-shot-one-kill says continue, swing model says reverse); the higher timeframe always wins.

## Rules
- Telltale sign: Monday and/or Tuesday range far above the average daily range of the last ~5 days, moving with speed -> start considering a midweek reversal; does not always happen ~20:45 [new]
- Speed = price reaching for a specific institutional reference level (valuation point); do not assume a fast move will extend into an equal leg later in the week ~14:00-14:36 [new]
- When the early-week move is fast, immediately look for higher-timeframe PD arrays (monthly, weekly, daily, no lower than 4h) in its path as the reversal candidate ~13:57, ~26:24 [new]
- Context: the market was in the premium of the larger dealing range (lesson 5 PD array matrix) and refused to leave the premium; a drop into a smaller-range discount array while still in the larger premium = buy, not continuation ~4:15, ~8:46, ~16:57 [new][chart]
- Reversal day: Wednesday (or Thursday) reversals form roughly every month in any pair ~22:51 [new]
- After the reversal low: Wednesday breaks a short-term high (market structure shift), then each new bullish order block (down-close candle or series of them) is defended and price leaves it quickly = "institutional sponsorship" ~17:24-17:53 [chart]
- Target after an intraweek reversal: return to the previous price balanced range (the consolidation the move left from), or exceed it to take the liquidity above; here a lower high on Tuesday than Monday ~18:06-19:40 [new][chart]
- Managing an open trade: if a profitable trade stops working as expected, exit and look for a new entry; if no strong re-entry appears it is probably a reversal profile ~22:29-22:45 [new]
- Overlapping models: when a higher-timeframe model (swing buy at a daily OB) opposes the lower-timeframe one (short-term sell continuation), expect the higher timeframe to win ~26:06-26:24, ~28:09 [new]
- Day-trading ideas not aligned with daily/weekly/monthly (minimum 4h) PD arrays are not high probability ~26:34-26:48 [new]

## Trade examples
- GBPUSD, week of 27 Mar 2017 (no trade taken, profile review). Daily: price in premium half of the Dec 2016-Mar 2017 range; Tuesday 28 Mar large down candle (~200 pips in ~24 h) into "Daily Bullish Orderblock Mean Threshold" (~1.238, read from chart axis, approx). Low of week formed at the Tue-Wed changeover. Then 1h MSS Wed, bullish OBs Wed/Thu/Fri, rally Friday 31 Mar into "4H Bearish Orderblock" / "Fair Value Gap Premium PD array" just below the "Daily Rejection Block" (~1.255). He framed it as a market maker buy model: consolidation (price balanced range Mon), sell-off Tue, smart money reversal Tue/Wed, low-risk buy Thu, reaccumulation Fri. [chart]

## Definitions
- Intraweek market reversal profile: early-week (Mon/Tue) high-magnitude move into a HTF PD array, then reversal for the rest of the week ~12:40-13:57.
- Institutional sponsorship: bullish OBs that are revisited and immediately left with displacement ~17:36.
- Price balanced range: the consolidation before the expansion leg; intraweek reversals aim back to it ~18:36.
- Overlapping models: two trading disciplines (e.g. swing vs short-term) giving opposite signals at the same point ~26:06.

## Seen only on the charts
- Daily chart levels drawn: Old High & Rejection Block (top), Weekly Rejection Block, red "Daily OB" box, Daily Bearish Orderblock Premium 50% Level, Daily Bullish Orderblock Mean Threshold, Daily Rejection Block, Weekly Bullish OB Open / Mean Threshold, two FVGs, Old Low & Rejection Block (bottom). Pink = premium, white = discount of the larger range [chart 4:20].
- The yellow box (10:20) brackets the week's daily candles; the week's range nearly all came from Tuesday.
- On 1h the sweep low only slightly pierced the daily OB mean threshold line; very little trade below it [chart 13:20].
- Swing overlap chart (24:40, 26:20): the week's range itself is graded into premium (red) / discount (green) quarters; the reversal low sits on the daily bullish OB in the lower quarter (red arrow).

## Open questions
- "Well above" the 5-day average daily range is not quantified (1.5x? 2x?).
- Index analogue untested: does a Mon/Tue ADR spike into a daily OB/FVG predict a Wed/Thu reversal in ES/NQ?
- How to pick which HTF PD array is "the" reversal level when several lie in the path.
- Return to the price balanced range vs exceeding it: no rule for choosing the target.
