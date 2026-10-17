# 012 ICT 2023 Mentorship Analysis \ January 25, 2023 (HkiPAi1Mdu8)
Date discussed: Wed Jan 25 2023 (review recorded that evening, ~17:15-18:08 ET by the chart clock). Markets: DXY, EURUSD, GBPUSD (daily, brief), NQ and ES March futures. Timeframes: daily, 1h, 15m, 5m, 2m (NQ), 1m (ES). Duration ~36 min.

## Summary
Review of a day where both indices dropped in the AM into a daily bullish FVG / order block, swept sell-side around 10:35-10:40, then shifted bullish and ran through lunch and the last hour. Key teaching: which half of a higher-TF FVG should hold or be filled, wicks as gaps (CE of a wick), mitigation defined, MSS needs no close. ICT shorted the ES 9:40ish Judas swing and called a 5-handle long off a 1m FVG (no long fill shown).

## Rules
- A daily wick is treated as a gap; its 50% (CE) is a target/reaction level. NQ upper wick CE 12149, ES wick CEs 4117.75 and 4072.75; ES 4043.25 next objective ~4:12, ~15:22, ~20:32 [chart] [new]
- Daily bullish OB key levels = the down-close candle's open and high ("sensitive price points"); expect price to hold there and rally ~5:13, ~9:30 [chart] (consistent with Ep 03 OB anchoring)
- Bullish context in a large daily FVG: reactions should come from its upper (premium) half, above CE. Smaller FVGs in the upper half should get filled; those in the lower half should stay open. If price fills the lower half, bullishness weakens, expect chop, wait ~18:00-19:37 [chart] [new]
- Price trading back into the upper half of a higher-TF bullish FVG is still a discount relative to the larger swing range (low to high, equilibrium) ~20:48 [new]
- Inside day (high below and low above previous day) -> expect a large range day next ~16:17 [new]
- If ES traded to 3977.75 the bearish idea was over and he would flip bullish (a pre-stated invalidation level) ~27:58 [new]
- MSS does not require a candle close beyond the short-term high (bullish) or swing low (bearish); a wick through counts ~30:30 [chart] [new] (rules file does not state this; the bot must not demand a close)
- Swing high definition used for the MSS: a candle whose high is higher than the candles on both sides ~30:08 [chart] [new]
- Bullish breaker: low, high, lower low; use the body of the up-close candle (uppermost), extend forward. Bearish breaker uses the down-close candle ~11:07 [chart]
- When several down-close candles are run through strongly, use the original (highest) one as the OB, not the whole series; skip a candidate OB whose body extends lower than the chosen one ~14:06-14:38 [chart] [new]
- Last hour macro 15:00-16:00 runs buy-side after a final OB retest ~14:52, ~34:58 [chart] (consistent with Ep 01)
- AM target method: pick a short-term high offering ~5 handles from the FVG entry (homework: find two 5-handle runs before noon) ~31:46-32:14 [chart]
- Exit with a limit just above the projected level (3962.75 vs 3962.50 for a short); it did not fill ~29:44 [new]

## Trade examples
- ES short (ICT live, sizes not given): ~09:40-09:45 ET run above a short-term high ~3992 into the 15m FVG = Judas swing after taking buy-side. Sold there, added larger, rode it down, re-shorted lower and built again. Limit exit at 3962.75 (target 3962.50 from fibs/HTF levels) not filled; low ~3963.25 (daily L) at ~10:40, one tick into the hourly FVG ~28:46-29:56 [chart]
- ES long (called live on Twitter, no fill stated): after the 10:40 low at the daily FVG CE (~3964), price broke the ~10:45 swing high (~3974.5) without closing above it (MSS), retraced into an FVG to CE, then a 1m FVG candle ~10:55 (~3975-3976) was named. Target: buy-side at short-term high 3982 (~5 handles). Price ran far past, to ~4006 by 11:45 ~30:05-32:50 [chart]
- ES continuation: lunch held above ~3994, OB retest, accumulation at the low end of the hourly pink imbalance (~4000-4005), break of 4009 after 13:00, OB at ~4022 at 15:55, run through buy-side ~4035.5 to the 4038.75 rejection block level just after 16:00 ~33:00-35:10 [chart]
- NQ (no trade by ICT): daily FVG ~11490-11650, daily OB lines ~11620 (open) and ~11760 (high). 2m: sell-side below ~11622 swept ~10:35 (low ~11605) into the +OB / OB open, MSS above ~11665, FVG CE + bullish breaker ~11650-11662 held, mitigation block ~11700-11712 traded through, IOFED ~11717, buy-side ~11727 and 11760 taken before lunch. PM: OBs ~11810, ~11830, ~11840; ~15:55 OB then run above highs to ~11910 ~9:48-15:05 [chart]

## Definitions
- Wick = gap; CE of a gap = its midpoint; mean threshold = midpoint of an OB; gap theory and OB theory are distinct ~4:14-4:37
- Mitigation: the act of an offside trader reducing or removing drawdown when price returns to their entry. Candles/OBs do not mitigate. A last up-close candle reclaimed after price is elongated away = mitigation block, not breaker ~11:41-12:40 [chart]
- Retrade: price returns to a level briefly and leaves (vs retest) ~2:49
- Inversion: when price trades back into the premium (upper) half of a higher-TF bullish FVG, premium becomes discount; to be revisited ~18:33
- Balanced price range: shaded FVG delivered both directions; CE is the last line of defense ~22:27-22:48 [chart]
- IOFED: partial dip into an FVG that leaves part of it open, then continuation ~12:52 [chart, labelled IOFED]

## Seen only on the charts
- ES hourly annotations: "Upper Half Of The FVG" and "Best To Leave Unfilled" (lower half); fib 0.5 of 3912.25-4056.75 at 3984.50 drawn; daily FVG CE ~3964.
- ES levels on right axis: 4056.75 (buy-side), 4043.25, 4038.75, 4009.00, 3978.00, 3969.50.
- NQ chart labels "New York Lunch Begins" 12:00 and "Ends" ~12:58; lunch ranged in both markets.
- The final ES buy-side run printed just after 16:00, not inside 15:00-16:00.

## Open questions
- Exact boundaries of the hourly ES FVG (purple ~3980-3984?) and pink imbalance not legible to the tick.
- How to decide algorithmically which daily-FVG half "should" hold before the fact (only bullish case given).
- The inversion idea is explicitly left incomplete.
- Entry price/stop for the ES short and the long are not stated; the 1m FVG candle price is approximate.
- Does the last-hour macro window extend to ~16:05-16:15 (ES run printed after 16:00)?
