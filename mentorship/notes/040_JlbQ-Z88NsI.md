# 040 Drawdown Mitigation - March 09, 2023 Homework Assignment (JlbQ-Z88NsI)
Date discussed: Thu 2023-03-09 (pre-market and 08:30 jobless-claims release). Market: ES (E-mini S&P 500, Mar 2023 contract, ESH2023), DXY overlaid. Timeframes shown: 1m and 2m (daily mentioned, not shown). Duration ~2:16 (sped-up screen recording, no full lesson).

## Summary
A short demonstration of the week's "homework": deliberately take losing shorts on ES to put a funded-account challenge into drawdown, then recover it the same day. After the 08:30 unemployment data he goes long on a daily-chart bullish reason, builds the position on an order block up to 15 contracts (the challenge's cap for a $150k account) and targets a swing projection.

## Rules
- Funded-account challenge size cap: 15 contracts maximum on the $150k challenge; his build-up stops at that cap. ~0:01:56 [new] [chart: final position 15 contracts]
- Daily-chart bias decides direction after the news: after the 08:30 release he checks the daily, sees reason for higher prices, and goes long. ~0:01:35 [new] (top-down sequence is in the rules file; the explicit post-news daily check is not)
- Target from a swing projection (measured move of the swing). ~0:01:43 [new] [chart: target line at 4007.50] Projection anchors not shown.
- Pyramid by adding at the order block after the initial long. ~0:01:51 [chart: "+OB" label near 3994.5, added 2 contracts at market 3997.75] Consistent with the existing pyramiding rules.
- Step aside before high-impact 08:30 data; the release is expected to blow through an open intraday position. ~0:01:08 Consistent with existing news rules (rules lines 89, 104).
- "Five handle run" is cited as an acceptable intraday move to bank and then step aside. ~0:00:39, ~0:01:03 Consistent with the ~5-handle goal already in the rules.
- The deliberate losing shorts are a drill, not a trading rule. A bot must NOT copy the pre-08:30 shorts. ~0:00:00

## Trade examples
All ES, 2023-03-09, 1m/2m, read from the TradingView paper-trading tags (stop = red/orange, target = green).
- Drill shorts (intentional drawdown), ~07:30-08:30 ET, inside the range just below the Jan 22 NWOG (3987.00-3988.00):
  - 10 short @ ~3982.25, stop 3983.75 (-$800), target 3974.75 (+$3,700) near the Feb 26 NWOG low. ~0:00:00 [chart]
  - 6 short @ 3984.25, stop 3985.50 (-$375), target 3975.75. ~0:00:20 [chart]
  - 9 short @ 3985.25, stop 3986.50 (-$562.50), target 3975.50. ~0:00:40 [chart]
  - 13 short @ 3984.25, stop 3985.25 (-$725), target 3974.75 (+$6,100); showed +$1,875 open at 08:18, i.e. the "five handle run" he let come back. ~0:01:00 [chart]
  - At the 08:30 release price spiked through the Jan 22 NWOG to ~3989.75 (2m). Stopped/flattened; outcome net negative by design. ~0:01:20 [chart]
- Recovery long, ~08:30-08:53 ET:
  - Initial 13 long @ 3995.00, stop 3991.50 (-$2,287.50). Added 2 at market 3997.75 at the "+OB" order block. Final 15 long, avg ~3995.25, stop raised to 3993.00 (-$1,712.50), target 4007.50. ~0:01:40-0:02:00 [chart]
  - Chart note: "I created the Drawdown for this week. I have to make it back inside today." Price ~3997.75 at the last frame; he says the target is hit at the end (~0:02:16), not confirmed on any frame.
  - PD array: order block on the 1m after the news displacement; liquidity: the drill range high / Jan 22 NWOG run by the release.

## Definitions
- Drawdown (homework sense): equity given back toward the funded challenge's loss limit; the exercise is to practice recovering inside its rules. ~0:00:17
- Five handle run: a 5-point ES move. ~0:00:39

## Seen only on the charts
- NWOG levels drawn: Jan 22 2023 NWOG 3987.00-3988.00 (with a red dotted mid ~3987.50); Feb 26 2023 NWOG 3974.50-3976.50 (red dotted ~3975.50). Upper lines 4018.25-4020.00 (mid ~4019.25), unlabeled in frame, likely another NWOG.
- Short targets sat at the Feb 26 NWOG; shorts were placed just under the Jan 22 NWOG.
- Shaded box marks the drill range (~07:45-08:30, ~3981-3987).
- Post-news long stop sat below the post-release consolidation, above the Jan 22 NWOG top (3988); the OB add was at ~3994.5.
- Stop moved up from 3991.50 to 3993.00 after the add (not mentioned verbally).

## Open questions
- Which daily-chart feature gave the bullish reason? Not shown or named.
- Swing projection anchors (which swing low/high, what multiple) that gave 4007.50 are not shown.
- Is 15 contracts a hard per-trade cap or a total open-position cap? The challenge's daily-loss/trailing-drawdown limits are not stated.
- Exact OB candle used for the add is not legible beyond the "+OB" tag.
- Whether he flattened before 08:30 or was stopped by the spike is unclear (one contract still open at 08:30).
