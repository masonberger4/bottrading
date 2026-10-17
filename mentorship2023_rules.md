# 2023 Mentorship bot: rules from transcripts

All times New York (ET); ICT stresses charts must be set to New York local time, daylight
saving included (Ep 01 ~25:15, Ep 03 ~9:46, Ep 04 ~4:07). ICT trades ES/NQ futures; our bot
trades what Schwab allows (SPY/QQQ) with ES-equivalent targets.

Verified 2026-10-17 against the YouTube auto-captions of playlist PLVgHx4Z63pabpjlduWBaEsn8VMtALhjGV
(captions kept locally in data/mentorship2023/captions/, not committed). Notation: "~mm:ss"
= approximate time in that video; [corrected] = the earlier note overstated or misstated it;
[added] = in the transcript but missing from the earlier notes.

Episode -> playlist position: Ep 01=#1, Ep 02=#2, Ep 03=#3 (#5 is the same video again),
Ep 04=#6, Ep 05=#7, Ep 06=#8, Ep 07=#9, Ep 08=#10. Playlist #4 (AUbdCTzc19k, "ICT Emini NQ
Futures Market Maker Live Execution", 2 min) has no captions and is not covered. Next new
video: #11 (w0CYBeFTzcM, "ICT Premarket Commentary for Week Ending 01/20/23").

## Ep 01 (XN8tuO4QIRw), Jan 1 2023
Definitions
- Buy-side liquidity: buy stops above old highs / relative equal highs. Sell-side liquidity: below old lows / relative equal lows.
- Fair value gap (FVG): 3-candle pattern, gap between candle 1 high and candle 3 low (bullish = BISI) or candle 1 low and candle 3 high (bearish = SIBI). Consequent encroachment = 50% of the gap. [corrected] Only the bullish form is defined in this video; SIBI is named in Ep 02/03.
- Liquidity void: an actual gap between candles (no overlap at all).
- Balanced price range: an FVG price has passed through both ways; price should not re-enter it.
- Breakaway gap: FVG formed as price accelerates away; expected to stay open (don't expect retrace).
- Breaker: low, high, lower low, then price breaks back above the high (use the candle body, not wick).
- Narrative (how the day trades, what liquidity it aims for) is separate from bias (direction).

Day context
- Low-volatility days (e.g. last trading day of year) -> expect an inside day vs previous day's high/low, framed before the 08:30/09:30 open (~16:42). Monday refers to Friday's range.
- Year end: price is expected to reprice up to buy-side liquidity. [corrected] ICT says the algorithm reprices to the buy stops; short covering is a consequence, not the cause (~31:47-34:45).

Sessions
- AM session 08:30-11:00. PM session 14:00-16:00; focus on last hour 15:00-16:00.
- PM setup window 15:15-15:45. No setup by ~10 minutes before the close (15:50) -> no trade. [corrected] He says "10 minutes before", not the clock time (~1:00:45).
- Lose in AM -> do NOT reverse; stop for the morning, wait for PM. [corrected] Stated firmly for new traders and "never" for funded accounts; he allows that experienced traders sometimes reverse (~46:57-48:43). The bot keeps the strict rule.
- [added] The last-hour run to an old high, old low or imbalance happens nearly every trading day (~49:28).

PM "last hour" setup (the trade shown)
- Mark draw on liquidity: old high/low, relative equal highs/lows, or an unfilled imbalance. Bullish -> target above; bearish -> below.
- Look for nested FVGs aligned on 4h / 1h / 15m / 5m; price trading back into the higher-TF FVG and holding (bodies refuse to close beyond it).
- [added] Context: in the last hour price should hold above the midpoint of the 4h FVG (~30:48).
- [added] Trigger: bodies refuse to close through the low end of the 60m FVG, then price accelerates away, leaving a breakaway FVG (~39:00-40:00). By about 15:25 the move toward the liquidity should have started (~38:57).
- Entry: at the top of the 1-min bullish FVG (mirror for shorts); can add on retests and on a breaker. (He says he bought the top of the gap; "limit order" is our reading.)
- [added] If price dips back into the breakaway gap, buy it with the stop just below the candle bodies (~42:19).
- Stop: just below the opening of the FVG candle, later below the candle bodies and trailed up (~37:45, ~42:19).
- Target: the liquidity pool (e.g. relative equal highs), with a nearer short-term high as an intermediate target (~42:19). Goal ~5 ES handles. [corrected] The 1-point drawdown was one entry, not described as typical.
- [added] A clean delivery has few, small down-close candles; the speed is in the up-closes (~34:45).
- Chart reference points pulled down to 5m and 1m for execution.

## Ep 02 ES review Jan 3 2023 (GHaD0mebgMU)
- News days: when data drops at 9:45 (PMI), wait for the release, not just the 9:30 open. A Judas swing (fake run into nearby liquidity/imbalance during the news) was expected, then the real move. [corrected] The video only covers the 9:45 release (8:30 is not mentioned), and the expected Judas run did not happen: price failed early, so he waited for the structure shift instead (~0:00, ~7:03).
- AM short setup: run up into buy-side liquidity (old high / round number), then market structure shift (break of a swing low with displacement), then short on retrace into the FVG / bearish order block / breaker. Can add on later FVG retests (three entries in the example).
- Order block: last up-close candle(s) before the down move (bearish OB). Mean threshold = 50% of the OB measured from its high to its low (wicks included); bodies should respect it.
- CE = 50% of FVG; MT = 50% of OB.
- Targets: higher-TF FVGs (15m, 30m) and sell-side liquidity below lows; take partials at each level, hold runners while price stays "heavy" (below the 30m FVG). [corrected] He would "probably" exit if price goes back above that FVG, not specifically on a close (~8:39-9:19).
- If no daily range breakout / no higher-TF daily narrative -> intraday scalping only, small targets.
- First trading day of year: don't rush in.
- [added] Top-down chart sequence: daily volume imbalance, then 60m, 30m, 15m, 5m, 1m (~0:56-2:29). On news days the draw was the daily volume imbalance (~9:19).
- [added] An FVG left open on the way down is a breakaway gap (~4:08).

## Ep 03 NQ trade review Jan 4 2023 (ojy5ApHhEu4)
Day type (important)
- Non-farm payroll (NFP) week: trade only Mon, Tue, and Wed up to the end of the NY AM session. Wed PM, Thu, Fri of NFP week are choppy/imprecise -> no trade.
- FOMC day (2pm release): do not trade the release ("carnival ride"). Standing aside for the whole PM is our reading (~4:02, ~36:56).
Definitions
- Volume imbalance: between two consecutive candle bodies (close to next open) where the only overlap is wicks. Draw on liquidity on the daily chart.
- BISI = bullish FVG (bought for longs, target for shorts); SIBI = bearish FVG.
- Measuring gap: an FVG that stays open mid-move; roughly half of the move -> project the target.
- Institutional order flow entry drill: a shallow dip into an FVG that does not reach 50% (CE), then continuation.
- Rejection block: named as the next draw on liquidity. [corrected] It is not defined in this video; "a level of wicks" was our gloss.
- Reclaimed order block: price leaves an OB and trades back into it as support; normal.
- [added] Order blocks are anchored on the down-close candle: its high or its open (~10:34, ~30:58).
- [added] The first FVG after the shift should act as a breakaway gap and not be fully closed; with price leaving it, the range it leaves is a protected zone, which justifies trailing the stop under it (~27:46, ~29:20, ~41:54).
Instrument selection (SMT / relative strength)
- Compare NQ vs ES on the same timeframe. Trade the stronger one for longs (made the cleaner higher high, cleaner FVG). Divergence between them = SMT.
Market maker buy model (long)
- Higher-TF draw above (daily volume imbalance, relative equal highs). Price drops into a discount (lower half of range) into a 5m order block / 1m BISI.
- Takes a short-term low, then breaks a short-term high (market structure shift in discount) leaving an FVG. [added] In the example the 9:30 open dropped below the lows and the setup formed in 10:30-11:00 (~16:45).
- Entry: long at the FVG (he watched its top for support and added there); stop below. Move stop to breakeven after buy-side is run. Pyramid on retests of new FVGs that hold (up to ~10 contracts, ~2.1% risk of a $100k account).
- Expect stop-run of retail bull-flag stops before continuation.
- [added] After large candles turn into small-range candles, expect large candles in the bias direction next (~45:55).
Exits ("running down equity")
- Scale out one contract at a time as each new high prints near each liquidity pool/target, not all at once. Trail stop below the latest measuring gap after two rounds of partials (~1:05:10); the aim is a "funded" position. Never widen a stop (~1:14:05).
- Final target: higher-TF PD array (daily volume imbalance). Accept getting stopped on the last few units.
- [corrected] Lunch: going into noon usually retraces; he says he should have taken off the last contract before it (~1:18:16). The 12:00-13:00 window and "tighten" are our wording.
- Goal: 1 good setup per week; low-hanging target 5 handles (20 ticks).
- [added] Use time-based charts only (no Heikin Ashi, range or renko bars) (~44:23).

## Ep 04 NFP review Jan 6 2023 (VKkn8uckkW0)
- NFP Friday: no live trading (paper/study only). High-impact news (NFP, FOMC) can overshoot FVGs. [corrected] He ignores the immediate reaction to the 08:30 release and waits for the real range; no fixed minute count (~8:35, ~27:45).
- Midnight NY open (00:00 ET 15m candle open) = the true daily open. Power of three (accumulation, manipulation, distribution):
  - Bullish day: buy at or below the midnight open (worst case near it); expect a fake move against bias, then expansion away and a close near the day's high.
  - Bearish day: mirror (sell at/above midnight open).
- Dealing range: after the news, the high/low of the post-manipulation range is the framework. Expect expansion to external range liquidity (beyond that range's high/low).
- Entry trigger: market structure shift (break of a short-term high) while an FVG/BISI stays open; enter on retrace to order block / FVG near midnight open.
- [added] He wanted two structure shifts, each leaving an open FVG, before calling himself "on side" (~49:29).
- Institutional order flow entry drill = retrace that stops ~1 tick into the FVG. Pyramid: largest size first, smaller adds lower (e.g. 6,3,2,1), never larger adds; no adds after partials have been taken. [added] If price closes into the FVG instead, add again at the FVG's low end (~51:00).
- Smooth/"too clean" relative equal highs or lows are magnets; price will run them.
- Targets in order: nearby relative equal highs, old daily highs (previous days' highs/lows hold real liquidity), then daily volume imbalance. Take the bulk (e.g. 10 of 12) at the first target, rest at next ones.
- If target hit by 15:00, be done; last hour tends to retrace into the range.
- SMT: compare ES vs MES for divergence at lows/highs. [corrected] NQ is not used in this video.

## Ep 05 ES review Jan 9 2023 (bGtQOXrrK9c)
- Bearish breaker: high, low, higher high, then the move back down; mean threshold (50% of the OB/breaker) and CE of FVGs as reaction levels. [corrected] "Break below the low" and "resistance" are implied, not stated (~0:00, ~1:42).
- No 8:30 news -> wait for 9:30 open before acting.
- New Week Opening Gap (NWOG): a target/PD array. [corrected] The definition (Friday close to the Sunday open) is not given in this video.
- "Unicorn" (strongest entry): FVG that sits inside a breaker, right after a run on sell-side (bullish) at the 9:30 open. Buy at FVG/CE inside the breaker; add on each new imbalance.
- Accumulate inside the breaker/consolidation before the breakout, not on the breakout.
- [corrected] The 10-12 handle "bread and butter" move was the pre-9:30 move off the 08:00 order block, not the AM setup; the partial was ~1 handle above the relative equal highs (~14:25-15:15, ~19:09).
- [corrected] Lunch: at noon that day price reversed off the hourly FVG's CE; one observation, not a stated rule (~9:16).
- Market maker sell model: consolidation with sell-side below, rally (bought inside a breaker) into relative equal highs, MSS down, sell when price fails to reach the imbalance's CE, run to sell-side, NWOG, imbalances.
- Weekly bias filter: after the strong down day, favor shorts the rest of the week unless price gets back above 50% of that day's wick on a closing basis (~2:36, ~24:20). [corrected] Stated for that week, not as a general rule.
- Watch one market only (he lost track switching between ES and the US500 CFD).
- [added] The stop was placed just below the FVG's high when he couldn't watch, and it was hit (~19:09).

## Ep 06 Forex review Jan 9 2023 (cxdjcXec3eA) - mostly FX, general timing rules
- Kill zones (NY time): London open 02:00-05:00, NY open 07:00-09:00 (FX), London close 10:00-12:00.
- Trending day template: low of day (bullish) forms in London open, continuation in NY open, high of day forms in London close 10:00-12:00; reversal/end of move often at noon.
- Retracement into a SIBI often stops at CE (50%), not the old lows (S/R fails).
- Projection: anchor fib on the manipulation swing (London low to the high) and project standard deviations 1, 1.5, 2, 2.5, 3... as targets. [corrected] Projections only apply after price takes out that high; the 1.5 SD matched closing prices, not wicks, in the 10:00-12:00 window (~6:01-6:49).
- Correlation: DXY bearish = risk-on (EURUSD up). [corrected] "Indices up" and "optional filter" were our additions.
- [added] The midnight opening price is the reference: if bearish, look for price below it (~0:51).
- [added] Relative equal highs/lows are the preferred liquidity pools (~4:31).

## Ep 07 ES live execution & mean threshold risk (tnxvmHq8xEg)
- Draw on liquidity can be an old daily close (e.g. prior daily close level) = "unrealized premium array" target set before the week.
- AM model: wait for 9:30; sell-side purged (e.g. below 9:20 low at ~9:40), then rally leaves an FVG/volume imbalance; buy inside the FVG near its midpoint.
- Stop: below the mean threshold (50%) of the down-close candle (bullish OB) closest to the sweep low. [corrected] Not the candle nearest under the entry (~4:07). Later trail to the low of the retracement candle once price trades through the bodies of the prior swing high.
- Volume imbalance (gap between one candle's close and next candle's open) should hold; stop at its low.
- Pyramid on down-close candles into bullish OB/volume imbalance; take profit on up-close candles ("market efficiency paradigm": buy down candles, sell up candles).
- Trigger: price must break the high of the small SIBI/swing quickly ("speed and distance"); once broken, expect acceleration to buy-side above recent highs.
- [added] Invalidation: after the trigger, price should not trade below the lowest open or close of the swing low (~15:36).
- Macro: 09:50-10:10 ET often produces a run to liquidity or an inefficiency.
- Exit bulk (e.g. 9 of 14) at the target; risk per trade ~1-1.3% of account.
- Think in 5-handle increments; ~15 handles/day possible.

## Ep 08 ES review Jan 18 2023 (cWekmMLqiNM)
- Daily levels: 50% of a daily candle's wick (high to open / low to open) is a key level; daily FVG edges hit to the tick.
- Neutral bias allowed: when unclear (price stuck at a premium array, choppy consolidation), wait for 9:30 open to reveal direction. Choppy = small 2.5-5 handle scalps. [corrected] Sitting out entirely is advice for seasoned traders; new traders should study the chop (~76:36).
- Three opening prices: midnight (preferred), 08:30, 09:30 (and 13:30 for PM). Bearish: sell above the opening price (premium). [corrected] "Bullish: buy below" is the mirror; only the bearish side is stated here.
- MSS validity: the swing low that counts is the one that led to the high that ran liquidity (e.g. previous day high). Don't trust a shift until the relevant liquidity run happened.
- Bearish order block: series of up-close candles before the drop; price returns exactly to their open, then reprices lower; the next wick stops at the up-close candle's mean threshold.
- PM session uses 13:30 open as a Judas swing reference: rally above 13:30 open into premium/FVG then sell. Last hour 15:00-16:15 setups at old daily highs/lows.
- Equilibrium: after a break of short-term low, look for FVG at or above 50% of the swing (premium) to sell.
- Partials: never target the exact low/high of an FVG; exit 0.5-1 point before. [added] A first partial can go at the FVG's CE or the top of a daily FVG (~58:28, ~68:17).
- Measured move: projection of range high-to-low equal distance as target.
- Liquidity matrix: highs and lows of the last 3 trading days (today, yesterday, day before), plus the 3-day highest high and lowest low = targets/entry framework.
- Old daily low/high alone is not an entry; need a PD array (FVG, OB, breaker) there plus time of day.
- Max size ~6 contracts initial, build to 10-16 via pyramiding within risk. [added] After a loss on the day, no max size (~49:51).
- [corrected] "Done for the week" was a personal remark once the week's expected range was delivered (~78:05), not a stated rule.
- [added] Institutional order flow entry drill only needs price to touch the candle that created the FVG (~47:36).
- [added] Turtle soup plan: let price spike above an old high (buy stops), short the failure, target the next draw, add on new FVGs/breakers (~25:13, ~36:53).
- [added] Multi-timeframe shift: price breaks below 5m equal lows on the 1m chart, then retraces into the 5m FVG to sell (~60:04-61:38).
- [added] Stops about one tick beyond the level (~16:01). He wants ~10 handles of range before engaging fully (~75:10).
