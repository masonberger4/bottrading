# cc05_001 ICT Mentorship Core Content - Month 05 - Quarterly Shifts & IPDA Data Ranges (n7SPAK_tpN8)
Recorded Jan 2017 (title slide: "Long Term Analysis, Implementing Macro Market Analysis, Lesson 1.1, January 2017"). Market: forex (DXY as benchmark, EURUSD, USDCHF, GBPUSD, USDJPY); ICT says the quarterly shift applies to all asset classes. Timeframes: monthly, weekly, daily (MT4). Duration ~55 min. Slides plus 3 chart screens, no trades.

## Summary
The price algorithm (IPDA) works from data ranges: it refers back about 3 trading months (60 trading days) for liquidity, and it shifts direction every 3-4 months. Procedure: anchor a vertical line at the first trading day of the last fully closed calendar month. **Look back** 20/40/60 trading days to find order flow and liquidity. **Cast forward** 20/40/60 trading days to find when the next daily setup/shift should occur. Benchmark-vs-underlying divergence (SMT on the daily) confirms accumulation or distribution.

## Rules
- The market makes a major shift every 3-4 months (consolidation or retracement against the prior swing). Expect an intermediate-term play in that window on every asset class ~5:05, ~7:11 [new]
- Strong trend -> the shift usually shows as consolidation, or a run below a daily short-term low, not a deep retracement ~7:26 [new]
- **Anchor:** put a vertical line on the first trading day of the most recent fully closed calendar month. On Jan 6 2017 that is Dec 1 2016; on Nov 14 2016 it is Oct 1 2016. Any other answer is "wrong" ~21:48, ~25:21, ~53:29 [chart] [new]
- **Look back:** from that line, mark 20, 40 and 60 trading days to the left (trading days, not calendar days). The algorithm on average reaches back ~3 trading months; sometimes further ~22:42-23:45 [chart] [new]
- In the 60-day look-back, judge institutional order flow: did price trade up or down collectively? Was there an obvious significant intermediate-term low or high? ~26:22-27:01 [new]
- Then **re-anchor** the vertical line on that intermediate high/low, i.e. the previous market structure shift (slide: "Anchor Vertical Line To Previous Market Shift") ~27:01-27:13 [chart] [new]
- Order flow was up -> frame off the range low; liquidity is the sell stops under the short-term lows inside the 20/40/60 ranges. Order flow was down -> frame off the high ~26:08, ~33:42-34:13 [new]
- Reference points to mark inside the look-back: old highs, old lows, bearish and bullish OBs, FVGs and liquidity voids. Use a rejection block if the highs/lows have long wicks ~24:10-25:21 [chart] [new]
- **Cast forward:** expect the next market shift within 20-60 trading days. Always cover 60 days in total: cast 20 forward if the last shift was 40 days ago, 40 if it was 20 days ago. Cap it at the projected 3-month limit (the next quarterly vertical line) ~34:49-36:15 [chart] [new]
- After a bearish structure break in the new quarter, retracements up are expected to close the liquidity void above and then sell off. Expect a daily setup within 60 trading days of the anchor ~37:19-37:58, ~43:25 [chart] [new]
- Use it for daily bias and long-term objectives that lower-TF trades can marry into ~38:11-38:26 [new]
- **Accumulation (buy program), daily chart only:** (a) benchmark makes a lower low while the underlying makes a higher low; (b) the underlying makes a lower low while an inverse benchmark makes a lower high (turtle-soup long); (c) the benchmark makes a higher high while an inverse underlying makes a higher low ~10:44-13:16 [chart] [new]
- **Distribution (sell program), daily only:** mirror of the above: (a) benchmark higher high + underlying lower high; (b) underlying higher high + inverse benchmark higher low (turtle-soup short); (c) benchmark lower low + inverse underlying lower high ~13:41-15:47 [chart] [new]
- Position management: on long-term positions, take part off into the expected 3-4 month retracement and add it back afterwards ~6:45 [new]

## Trade examples
No trades. Worked examples (forex only):
- DXY daily, anchor Dec 1 2015. The look-back shows bullish order flow (Oct 2015 low to the Dec 1 high). Price then broke a short-term low after Dec 1 -> bearish. Rallies to new highs inside the 60-day cast-forward only closed a liquidity void and failed ~29:09-31:14, ~43:08-43:42 [chart]
- EURUSD (inverse): low on Dec 1 2015, bullish structure break. Its lows stayed higher while DXY made higher highs, which is accumulation. The 60-day cast-forward mark lines up with the swing high (early/mid Feb 2016 on the chart) ~39:39, ~44:01-45:38 [chart]
- Jun 2016: DXY made lower lows but EURUSD failed to make a higher high above its May 2016 old high (a "?" line is drawn on the chart). This was distribution and price fell ~48:24-49:46 [chart]
- Nov 2016 US election day: the EURUSD spike high came ~60 trading days after the Sep 1 2016 line (per MT4). DXY made no lower low, so it was a turtle-soup sell ~50:30-51:28 [chart]

## Definitions
- **IPDA (Interbank Price Delivery Algorithm):** a central-bank price engine. It lets price move within predefined ranges and refers to specific dates, highs and lows ~3:50-4:33
- **IPDA data range:** the 20/40/60 trading-day windows measured from the anchor line. Look back = liquidity and reference points; cast forward = time window for the next shift/setup ~22:42, ~36:46
- **Quarterly shift:** a 3-4 month change in direction or sentiment ~5:05
- **Buy/sell program:** a run of consecutive up (down) sessions on any timeframe, reaching for liquidity beyond recent highs (lows) ~9:01
- **Underlying vs benchmark:** underlying = what you trade; benchmark = what you measure manipulation against (DXY for FX). USDCHF, USDJPY and USDCAD (when oil isn't a factor) move with DXY; EURUSD moves inversely ~10:28, ~17:25

## Seen only on the charts
- The monthly DXY chart is split at 2016.01/04/07/10 and again at 2016.01/05/09 to compare 3-month vs 4-month splits. The daily chart uses Jan 1/May 1/Sep 1 2016/Jan 1 2017, then 2015.12.01, 2016.03.01, 2016.06.01 and 2016.09.01 (every 3 months) ~19:00-28:00 [chart]
- Look-back markers are horizontal segments labelled 20, 40, 60 that extend left from the Dec 1 2015 line. The 20 mark reaches about early Nov and the 60 mark about mid-Sep 2015 ~29:40 [chart]
- Cast-forward markers extend right from Dec 1 2015. The 60 mark ends around early Feb 2016 on screen, before the Mar 1 line. His drawing is approximate, not exact bar counts ~36:40 [chart]
- On the DXY chart a white box highlights the Dec 2015-Feb 2016 highs inside the 60-day window (~98.5-100.5) ~43:20 [chart]
- In MT4 he counts days by dragging a trend line from the vertical line until the bar count reads 20/40/60 ~39:09

## Open questions
- What exactly is the anchor? First the month-start line, then re-anchored to the intermediate high/low. In his example the two coincide (Dec 1 2015 was the DXY high). He also says he chose not to re-calibrate at the May 2016 shift ~47:47. A bot needs one rule.
- The look-back is counted from the anchor, not from today. Later ICT material counts IPDA ranges back from the current day. This is not stated here, so check later videos.
- Cast-forward days 20 and 40: is that 20/40 days since the last shift, or since the anchor? The slide wording ("last shift was 40 days ago") is ambiguous.
- How to apply this to index futures: no benchmark is named for ES/NQ (DXY, or ES vs NQ?). Daily only, so it is a bias filter for the intraday bot at most.
- "Trading days" here are MT4 FX daily bars (Sunday bars may count). Use exchange sessions for ES.
