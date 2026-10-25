# cc02_002 ICT Mentorship - Core Content - Month 02 - Framing Low Risk Trade Setups (Zsg8IeBtfu0)
2016-17 Private Mentorship, Month 02 teaching 2 of 8 (slide footer: "October 2016"). Market: AUDUSD (forex). Example date Oct 13 2016. Timeframes shown: daily level, 1h, 15m, 5m. Duration ~10 min.

## Summary
Same AUDUSD daily bullish order block (0.7512) setup as the previous teaching, refined top-down: the 1h setup (entry 0.7542, ~20 pip stop) is re-framed on 15m (entry 0.7520) and 5m (limit buy 0.7515, stop 0.7507, ~8 pips). Point: the higher timeframe supplies the reason and level; lower timeframes only shrink the stop and improve entry price, giving ~3R before the 5m buy stops are even reached.

## Rules
- Bias, institutional order flow and the support/resistance level framing the trade come from the higher timeframe (monthly/weekly/daily); the HTF has more influence on price. ~00:00:45, ~00:02:11
- Refine (transpose) the HTF level onto lower timeframes to cut stop size; entry logic must stay the same as on the HTF. ~00:02:27-00:02:44 [new]
- A run below an old low is not enough to expect a reversal; it needs an HTF premise, e.g. the sweep reaches an old daily bullish order block. ~00:03:46-00:04:04 [chart] [new] (consistent with Ep 08 "old daily low/high alone is not an entry")
- Turtle soup long: price sweeps sell stops under an old low into an HTF support level; smart money pairs buy orders with those sell stops. ~00:05:54-00:06:04 [chart] (Ep 08 has the short version)
- Lower-TF bullish order block is "valid" once a later candle trades through (above) it; buy zone = from the OB's midpoint up to its high. ~00:06:13-00:06:28 [chart] [new]
- On the smallest TF the OB zone is its open/high down to the midpoint; alternatively just buy the HTF level plus spread. ~00:07:45-00:08:02 [chart]
- Stop: below the sweep low ("protective sell stop"); the same stop is kept across the 1h/15m/5m refinements, only the entry moves lower. ~00:06:34, ~00:08:05 [chart] [new]
- Measure R from the entry TF's own structure: first targets can sit below the buy stops on the execution timeframe, not only the 1h objectives. ~00:08:28-00:08:41 [chart]
- Tight stops are only valid if you understand why price should react at that level; no ultra-short stops without the HTF reason. ~00:09:44-00:09:54 [new]

## Trade examples
- AUDUSD, Oct 13 2016 (the low prints around 06:45-07:00 on the 5m chart axis; chart time zone not stated).
  - HTF level: daily bullish order block 0.7512 (red line). Old 1h low at 0.7533 swept ("sell stops under old low - buy orders paired"). [chart]
  - 1h version (from the previous teaching): long 0.7542 at the 1h bullish OB (down candle), ~20 pip stop below that candle's mean threshold. Targets: two buy-stop pools above 1h highs (labels "Buy Stops", ~0.7590 and ~0.7630, read approx). ~00:04:44 [chart]
  - 15m version: long 0.7520 in the 15m bullish OB (cyan box, labeled "15 min Bullish Orderblock"), stop 0.7507. Captions say "17 pip stop"; the chart arithmetic is 13 pips (likely a caption error). ~00:06:31 [chart]
  - 5m version: limit buy 0.7515 (about 0.7512 + spread), protective sell stop 0.7507, 8 pips risk. Box drawn shows 3R (~24 pips, to ~0.7539) reached before the 5m buy stops above a pre-drop 5m high (~0.7542). The 3R level coincides with the 1h entry 0.7542 (green band ~0.7535-0.7540). Outcome on chart: price rallied to ~0.7565 later in the day. Size not given. ~00:08:13-00:09:26 [chart]

## Definitions
- Turtle soup long: buying the false break below an old low into a support level. ~00:06:04
- Protective sell stop: the stop-loss for a long, under the sweep low (chart label). [chart]
- Daily bullish order block: a daily down candle where banks bought before; re-tests are expected to attract buying. ~00:04:04
- R multiple: reward stated as multiple of risk (3R = 3 earned per 1 risked). ~00:08:25

## Seen only on the charts
- Slide note: the 8-pip profit steps only illustrate the reward-to-risk model, not actual exits. [chart, 00:08:20]
- Slide note: the hourly long entry is where the 5m 3:1 unfolds. [chart, 00:09:20]
- Slide note: smart money buys under old lows and sells above old highs. [chart, 00:05:40]
- The 5m entry is shown as a limit order (label "Limit Buy .7515"). [chart]
- The 0.7507 stop is a few pips below the actual wick low (~0.7509), i.e. not one tick. [chart]

## Open questions
- Stop placement rule: is it "below the sweep low by a few pips" or "below the HTF level by a fixed buffer"? Chart only shows the number.
- "Midpoint up to the high" vs "open/high to midpoint": which body/wick points define the OB zone on each TF is loose.
- No time-of-day filter stated (forex example; kill zones not mentioned). For ES, the day trading time windows from the 2023 rules must be added.
- How to pick the execution TF (1h vs 15m vs 5m) programmatically: smallest TF with a valid OB at the HTF level?
- Forex-only: pips, adding the spread to the entry. For ES, translate to ticks/handles; the refinement logic itself carries over.
