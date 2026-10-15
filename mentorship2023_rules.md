# 2023 Mentorship bot: rules from transcripts

All times New York (ET). ICT trades ES/NQ futures; our bot will trade what Schwab allows (SPY/QQQ) with ES-equivalent targets.

## Ep 01 (XN8tuO4QIRw), Jan 1 2023
Definitions
- Buy-side liquidity: buy stops above old highs / relative equal highs. Sell-side liquidity: below old lows / relative equal lows.
- Fair value gap (FVG): 3-candle pattern, gap between candle 1 high and candle 3 low (bullish = BISI) or candle 1 low and candle 3 high (bearish = SIBI). Consequent encroachment = 50% of the gap.
- Liquidity void: an actual gap between candles (no overlap at all).
- Balanced price range: an FVG price has passed through both ways; price should not re-enter it.
- Breakaway gap: FVG formed as price accelerates away; expected to stay open (don't expect retrace).
- Breaker: low, high, lower low, then price breaks back above the high (use the candle body, not wick).
- Narrative (how the day trades, what liquidity it aims for) is separate from bias (direction).

Day context
- Low-volatility days (e.g. last trading day of year) -> expect an inside day vs previous day's high/low. Monday refers to Friday's range.
- Year end: position squaring / short covering drives price to buy-side liquidity.

Sessions
- AM session 08:30-11:00. PM session 14:00-16:00; focus on last hour 15:00-16:00.
- PM setup window 15:15-15:45. No setup by 15:50 -> no trade.
- Lose in AM -> do NOT reverse; stop for the morning, wait for PM. Never reverse (esp. funded accounts).

PM "last hour" setup (the trade shown)
- Mark draw on liquidity: old high/low, relative equal highs/lows, or an unfilled imbalance. Bullish -> target above; bearish -> below.
- Look for nested FVGs aligned on 4h / 1h / 15m / 5m; price trading back into the higher-TF FVG and holding (bodies refuse to close beyond it).
- Entry: limit at the top of the 1-min bullish FVG (mirror for shorts); can add on retests and on a breaker.
- Stop: just below the opening of the FVG candle / below the candle bodies; trail up as new FVGs form.
- Target: the liquidity pool (e.g. relative equal highs). Goal ~5 ES handles; 1-pt drawdown typical.
- Chart reference points pulled down to 5m and 1m for execution.

## Ep 02 ES review Jan 3 2023 (GHaD0mebgMU)
- News days: when data drops at 9:45 (PMI) or 8:30, wait for the release, not just the 9:30 open. Expect a Judas swing (fake run into nearby liquidity/imbalance during the news) then the real move.
- AM short setup: run up into buy-side liquidity (old high / round number), then market structure shift (break of a swing low with displacement), then short on retrace into the FVG / bearish order block / breaker. Can add on later FVG retests.
- Order block: last up-close candle before the down move (bearish OB). Mean threshold = 50% of the OB; bodies should respect it.
- CE = 50% of FVG; MT = 50% of OB.
- Targets: higher-TF FVGs (15m, 30m) and sell-side liquidity below lows; take partials at each level, hold runners while price stays "heavy" (below the 30m FVG). Exit if price closes back above that FVG.
- If no daily range breakout / no higher-TF daily narrative -> intraday scalping only, small targets.
- First trading day of year: don't rush in.

## Ep 03 NQ trade review Jan 4 2023 (ojy5ApHhEu4)
Day type (important)
- Non-farm payroll (NFP) week: trade only Mon, Tue, and Wed up to the end of the NY AM session. Wed PM, Thu, Fri of NFP week are choppy/imprecise -> no trade.
- FOMC day (2pm release): do not trade around the release ("carnival ride"). Stand aside in the PM.
Definitions
- Volume imbalance: between two consecutive candle bodies (close to next open) where the only overlap is wicks. Draw on liquidity on the daily chart.
- BISI = bullish FVG (bought for longs, target for shorts); SIBI = bearish FVG.
- Measuring gap: an FVG that stays open mid-move; roughly half of the move -> project the target.
- Institutional order flow entry drill: a shallow dip into an FVG that does not reach 50% (CE), then continuation.
- Rejection block: a level of wicks that becomes the next draw on liquidity.
- Reclaimed order block: price leaves an OB and trades back into it as support; normal.
Instrument selection (SMT / relative strength)
- Compare NQ vs ES on the same timeframe. Trade the stronger one for longs (made the cleaner higher high, cleaner FVG). Divergence between them = SMT.
Market maker buy model (long)
- Higher-TF draw above (daily volume imbalance, relative equal highs). Price drops into a discount (lower half of range) into a 5m order block / 1m BISI.
- Takes a short-term low, then breaks a short-term high (market structure shift in discount) leaving an FVG.
- Entry: long at top of that FVG; stop below. Move stop to breakeven after buy-side is run. Pyramid on retests of new FVGs that hold (up to ~10 contracts, risk ~2% of a $100k account).
- Expect stop-run of retail bull-flag stops before continuation.
Exits ("running down equity")
- Scale out one contract at a time as each new high prints near each liquidity pool/target, not all at once. Trail stop below the latest measuring gap.
- Final target: higher-TF PD array (daily volume imbalance). Accept getting stopped on the last few units.
- Lunch hour (12:00-13:00) usually retraces: tighten or close before noon.
- Goal: 1 good setup per week; low-hanging target 5 handles (20 ticks).

## Ep 04 NFP review Jan 6 2023 (VKkn8uckkW0)
- NFP Friday: no live trading (paper/study only). High-impact news (NFP, FOMC) can overshoot FVGs; ignore price action in the first ~30 min after 08:30 release.
- Midnight NY open (00:00 ET 15m candle open) = the true daily open. Power of three (accumulation, manipulation, distribution):
  - Bullish day: buy at or below the midnight open (worst case near it); expect a fake move against bias, then expansion away and a close near the day's high.
  - Bearish day: mirror (sell at/above midnight open).
- Dealing range: after the news, the high/low of the post-manipulation range is the framework. Expect expansion to external range liquidity (beyond that range's high/low).
- Entry trigger: market structure shift (break of a short-term high) while an FVG/BISI stays open; enter on retrace to order block / FVG near midnight open.
- Institutional order flow entry drill = retrace that stops ~1 tick into the FVG. Pyramid: largest size first, smaller adds lower (e.g. 6,3,2,1), never larger adds; no adds after partials have been taken.
- Smooth/"too clean" relative equal highs or lows are magnets; price will run them.
- Targets in order: nearby relative equal highs, old daily highs (previous days' highs/lows hold real liquidity), then daily volume imbalance. Take the bulk (e.g. 10 of 12) at the first target, rest at next ones.
- If target hit by 15:00, be done; last hour tends to retrace into the range.
- SMT: compare ES vs MES/NQ for divergence at lows/highs.

## Ep 05 ES review Jan 9 2023 (bGtQOXrrK9c)
- Bearish breaker: high, low, higher high, then break below the low; mean threshold (50% of the OB/breaker) and CE of FVGs act as resistance.
- No 8:30 news -> wait for 9:30 open before acting.
- New Week Opening Gap (NWOG): gap between Friday close and Sunday/Monday open; a target/PD array.
- "Unicorn" (strongest entry): FVG that sits inside a breaker, right after a run on sell-side (bullish) at the 9:30 open. Buy at FVG/CE inside the breaker; add on each new imbalance.
- Accumulate inside the breaker/consolidation before the breakout, not on the breakout.
- Bread-and-butter target ~10-12 handles from AM setup; take partial above relative equal highs.
- Lunch (12:00) often reverses the morning move.
- Market maker sell model: consolidation with sell-side below, rally into premium/breaker, MSS down, sell FVG/CE, run to sell-side, NWOG, imbalances.
- Weekly bias filter: after a strong down day, favor shorts the rest of the week unless price closes back above 50% of that day's wick.
- Watch one market only (don't flip between correlated instruments mid-session).

## Ep 06 Forex review Jan 9 2023 (cxdjcXec3eA) - mostly FX, general timing rules
- Kill zones (NY time): London open 02:00-05:00, NY open 07:00-09:00 (FX), London close 10:00-12:00.
- Trending day template: low of day (bullish) forms in London open, continuation in NY open, high of day forms in London close 10:00-12:00; reversal/end of move often at noon.
- Retracement into a SIBI often stops at CE (50%), not the old lows (S/R fails).
- Projection: anchor fib on the manipulation swing (low to the high that broke structure) and project standard deviations 1, 1.5, 2, 2.5, 3... as targets; stop when a kill-zone time window ends.
- Correlation: DXY bearish = risk-on (EURUSD up, indices up) -- optional bias filter.

## Ep 07 ES live execution & mean threshold risk (tnxvmHq8xEg)
- Draw on liquidity can be an old daily close (e.g. prior daily close level) = "unrealized premium array" target set before the week.
- AM model: wait for 9:30; sell-side purged (e.g. below 9:20 low at ~9:40), then rally leaves an FVG/volume imbalance; buy inside the FVG near its midpoint.
- Stop: below the mean threshold (50%) of the nearest down-close candle (bullish OB) under entry. Later trail to the low of the retracement candle once price trades through the bodies of the prior swing high.
- Volume imbalance (gap between one candle's close and next candle's open) should hold; stop at its low.
- Pyramid on down-close candles into bullish OB/volume imbalance; take profit on up-close candles ("market efficiency paradigm": buy down candles, sell up candles).
- Trigger: price must break the high of the small SIBI/swing quickly ("speed and distance"); once broken, expect acceleration to buy-side above recent highs.
- Macro: 09:50-10:10 ET often produces a run to liquidity or an inefficiency.
- Exit bulk (e.g. 9 of 14) at the target; risk per trade ~1-1.3% of account.
- Think in 5-handle increments; ~15 handles/day possible.

## Ep 08 ES review Jan 18 2023 (cWekmMLqiNM)
- Daily levels: 50% of a daily candle's wick (high to open / low to open) is a key level; daily FVG edges hit to the tick.
- Neutral bias allowed: when unclear (price stuck at a premium array, choppy consolidation), wait for 9:30 open to reveal direction. Choppy = small 2.5-5 handle scalps only or nothing.
- Three opening prices: midnight, 08:30, 09:30 (and 13:30 for PM). Bearish: sell above the opening price (premium); bullish: buy below.
- MSS validity: the swing low that counts is the one that led to the high that ran liquidity (e.g. previous day high). Don't trust a shift until the relevant liquidity run happened.
- Bearish order block: series of up-close candles before the drop; price returns exactly to their open, then reprices lower.
- PM session uses 13:30 open as a Judas swing reference: rally above 13:30 open into premium/FVG then sell. Last hour 15:00-16:15 setups at old daily highs/lows.
- Equilibrium: after a break of short-term low, look for FVG at or above 50% of the swing (premium) to sell.
- Partials: never target the exact low/high of an FVG; exit 0.5-1 point before.
- Measured move: projection of range high-to-low equal distance as target.
- Liquidity matrix: highs and lows of the last 3 trading days (today, yesterday, day before) = targets/entry framework.
- Old daily low/high alone is not an entry; need a PD array (FVG, OB, breaker) there plus time of day.
- Max size ~6 contracts initial, build to 10-16 via pyramiding within risk.
- Once the weekly range objective is delivered, stop trading for the week.
