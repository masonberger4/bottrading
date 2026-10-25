# 077 ICT Mentorship 2023 - July 23, 2023 Market Review (OnFifO44Kzo)
Recorded Sunday July 23, 2023, before the Sunday open (around 16:00 his local time). Markets: DXY, EURUSD, ES (Sep 2023), NQ (Sep 2023). Timeframes: weekly, daily, 1h, 15m. Duration about 17.5 min. Review only; no trades taken in the video.

## Summary
The multi-month EURUSD draw (a weekly volume imbalance) was reached and price rejected back to its low end. ES and NQ hit their weekly upside draws too. With both directions now 50/50, he drops the daily bias for the coming week, waits for Monday's price action, trades only from Tuesday, and stays intraday (session liquidity and inefficiencies). For ES and NQ he leans toward sell-side early in the week unless Friday's high is taken.

## Rules
- A weekly volume imbalance can count even when the wicks of the two candles overlap. What matters is that no candle body trades into the zone between one close and the next open. The algorithm treats the zone as inefficient and comes back to it. ~2:40-3:46 [chart]. This adds to the existing volume-imbalance definition; the zone is between bodies, not wicks.
- A volume imbalance is a pair of levels. Price can reach the high end, then return to the low end. EURUSD did this within a single week. ~4:08-4:31, ~6:43-7:03 [chart]
- Liquidity void on the daily: one candle's high to the next candle's low with no trading between them. It is a reprice target, but if price leaves it and trades away it can stay open for a long time. ~1:59-2:30 [chart] (partly in the rules file under Liquidity void)
- Watch the CE (midpoint) of a weekly candle's wick as a reaction level. Extend it right and watch how price trades at it. ~1:18-1:42 [new]
- After a higher-TF draw is delivered, the next move can be 50/50 between a premium inefficiency above and a discount inefficiency below. In that case, do not pick a direction. Drop to intraday (London/NY sessions) and trade only liquidity runs and inefficiencies, with no daily bias. ~5:50-6:37, ~12:53-13:16, ~16:49-17:00 [new]
- Do not set a weekly bias before the Sunday open. Let Monday's trading shape the weekly-range expectation, and start trading Tuesday. ~7:30-8:07, ~16:32-16:49, ~17:41-17:49 [new]
- Intermediate-term high filter (ES/NQ weekly): if a weekly candle closes below the low of the most recent down-close weekly candle, assume an intermediate-term high. Then favor lower-TF sell setups until the market shows bullishness again. It must be a close, not a wick. ~9:19-10:16 [chart] [new]
- Daily invalidation: the bearish retrace idea holds unless price closes above Friday's high. ~10:53-10:56, ~11:38-11:45 [new]
- A retrace into a daily inefficiency above the swing low (where trailed stops sit) does not damage the bullish swing. Ideally the lower FVG stays open as a breakaway gap. ~11:00-11:38
- Balanced price range: a single up candle (BISI) and a later single down candle (SIBI) overlapping make a BPR. Price rallied into it, rejected hard and returned to it again. Extend it to the right as resistance. ~13:34-14:13 [chart?]. The rules file says price should not re-enter a BPR; here it was revisited and rejected. [conflict, mild]
- Consolidation just above sell-side liquidity looks too enticing. Expect a run below it early in the week. ~14:16-15:05

## Trade examples
- EURUSD (weekly/daily/1h), week of July 17, 2023. This completes the July 9 forecast: retrace into the weekly inversion FVG, run buy-side (~1.1095), then draw into the weekly volume imbalance (~1.113-1.127). The week opened, traded to the high end (~1.1276), then fell back. On the 1h it aggressively returned to the low end (~1.113) and closed near it (~1.1125). ~4:42-5:21, ~6:43-7:03 [chart]
- DXY weekly: target was the April 11, 2022 week's FVG high (~99.57; the March 28 week's high is ~99.37). Price came within one pipette of the April 11 week's low (the level he cites) and bounced to ~101.08. On the daily, price pulled up toward a small liquidity void, with a daily FVG (~101.8-101.9), breaker and weekly FVG above. ~0:31-2:30 [chart]
- ES (weekly/daily/15m): the upside weekly inefficiency (~4575-4670 dark zone over a lighter ~4500-4575 zone) was reached with a high near 4609, and price closed the week at 4564. The bearish daily idea is to retrace into the lower daily inefficiency, possibly to the CE of the wick, while staying above the swing low and the blue daily FVG (~4370-4380). ~10:24-11:38 [chart]. Friday he traded into the lower edge of the dark zone (~4574) and rejected. ~13:17-14:13
- NQ (daily/15m): the high touched the weekly inefficiency (~16010-16300) near 16060, then dropped. The target is the order block / mean threshold below and a run below the 15m lows (~15520). The blue daily OB is ~14880-14960. He traded NQ on Friday off a small 15m FVG that ran sell-side; no details given. ~11:45-12:25, ~15:10-16:30 [chart]

## Definitions
- Weekly volume imbalance: the space between one weekly candle's close and the next one's open, with no body inside it. Overlapping wicks are allowed. He says most traders miss it for that reason. ~2:40-3:46
- Liquidity void (as used here): a true gap with no trading between candle A's high and candle B's low. ~2:02-2:12
- Intermediate-term high: confirmed when a weekly close lands below the last down-close weekly candle's low. ~9:24-10:03

## Seen only on the charts
- DXY labels: "Week Beginning April 11, 2022 FVG High" (99.571) and "Week Beginning March 28, 2022 High / FVG Low" (99.369); sell-side liquidity at 100.788; 104.540 line.
- EURUSD weekly labels: Weekly Volume Imbalance, Buyside Liquidity, Weekly IFVG (~1.091-1.094), Weekly FVG (~1.079-1.085). The daily also shows a "Daily FVG" outline (~1.069-1.071) and an "IOFED" box on the 1h.
- ES weekly shows two stacked red zones. The darker upper one starts around 4575 and the lighter one around 4500. A blue weekly FVG sits ~4370-4380.
- NQ 15m: a blue horizontal line at ~15745 from the July 13 high (an old high level).

## Open questions
- What counts as "the most recent down-close weekly candle" for the intermediate-high test: the last one before the high, or the one in the circled consolidation?
- Both "the low end of the weekly VI" and the "close" are references. Which edge should a bot use: body close/open levels only, or wick extremes?
- The exact rule for which daily inefficiency ES should fill is unclear from the words. It is marked only as "this inefficiency" on the daily chart.
- Whether "no trading until Tuesday" is a general rule after a big draw completes, or specific to this week.
