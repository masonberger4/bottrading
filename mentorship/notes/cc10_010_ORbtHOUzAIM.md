# cc10_010 ICT Mentorship Core Content - Month 10 - Index Futures - Basics & Opening Range Concept (ORbtHOUzAIM)
Recorded June 2017 (ESU17 quote dated Tue Jun 20 2017) / ES, NQ, YM futures / 5m and 15m Barchart charts shown in CENTRAL time (shaded 08:30-09:30 CT = 09:30-10:30 NY) / 12 min.
First lesson of the INDEX FUTURES section. Directly relevant to the bot.

## Summary
Defines the index "true day" (09:30-16:00 NY) and the opening range (OR) as the full first hour, 09:30-10:30 NY, with the first 30 minutes (09:30-10:00) as the highest-volume sub-range. The OR tends to form the high or low of the day, via a stop run or a fair-value setup. OR high/low and order blocks/rejection blocks around it are reference levels for later entries; a wide OR implies its opposite end gets run later in the day.

## Rules
- Day-trade window: NY session 09:30-16:00 ("true day") for ES, NQ and YM; ignore the 24h session for day trading ~1:04-1:11, ~2:51-3:04, ~8:14-8:21 [chart] [new]
- OPENING RANGE = 09:30 to 10:30 NY (60 minutes), same for ES, NQ, YM. OR high = highest high and OR low = lowest low of 09:30-10:30 ~3:07-3:23, ~7:23-7:26, ~8:33-8:38, ~11:09-11:15 [chart] [new]. Note: the 2023 mentorship notes use 09:30-10:00 as the opening range; here 09:30-10:00 is only the highest-volume first half. Treat as two nested ranges: OR30 (09:30-10:00) and OR60 (09:30-10:30) [conflict with 2023 notes, not with mentorship_rules.md]
- The first 30 min (09:30-10:00) carries the day's highest volume; the OR high/low and the first-30-min high/low have a specific relationship, deferred to the next lesson ("trading the AM trend") ~2:35-2:48, ~11:15-11:23, ~11:43-11:53 [chart] [new]
- The OR tends to create the high or low of the day; it can be a run on stops or a fair-value (PD array) setup ~3:18-3:28 [chart] [new]
- Inside/around the OR, use order blocks and rejection blocks as entry reference points; the same reference point can be reused later in the day for a second entry ~4:34-4:55, ~7:43-8:02 [chart] [new]
- Wide/extended OR: expect the opposite end to be violated or traded to later. Bullish day -> OR high is the target; bearish -> OR low. The OR gives a range to reach back into for stops on the opposite end ~6:08-6:57 [chart] [new]
- Turtle soup below the OR low later in the morning, then rally back to the OR high to run the stops left during the OR (mirror for shorts) ~6:51-7:05 [chart] [new]
- Volume confirmation (futures): a retest of the OR low/high on lower volume than the bar that made the low/high is weak and likely fails; a real break should come with higher volume ("volume precedes price") ~9:24-10:30 [chart] [new]
- Use OR levels together with bias and higher-timeframe institutional order flow; blending ES/NQ/YM signals comes later ~10:53-11:00, ~11:25-11:34 [new]

## Trade examples (all Barchart CT; NY = CT + 1h)
- ES 5m (~3:31-3:59): OR shaded 08:30-09:30 CT; huge up-move in the OR from ~2439 to ~2449, then grind higher; OR made the day's main leg [chart].
- ESU17 15m (~4:08-5:00): OR roughly 2434.5-2442. A bearish order block (up-close candles just before the open, ~2440-2443) is revisited inside the OR (starburst ~2440) for a short; a red line at ~2440.5 extended to the right is hit again around 12:30-13:00 CT (13:30-14:00 NY) for a second short, then a drop to ~2426 [chart].
- ESU17 5m (~5:04-5:45): OR about 2416-2425 (day low set inside the OR, ~2416). Price returns to a bullish order block, the last down-close candle just before 11:00 NY, near 2419 (labelled "+OB & Rally"), then rallies to ~2436 by the evening [chart].
- ESU17 5m (~5:53-7:05): wide OR about 2420.75-2433. Later in the morning (~10:00 CT = 11:00 NY) price runs just below the OR low (~2420) = turtle soup ("+TS & Rally"), then trends up and reaches the OR high ~2433 around 14:45-15:00 CT (15:45-16:00 NY), running the stops above it [chart].
- NQU17 15m (~7:12-8:10): OR about 5755-5782. Bearish OB before the OR plus a rejection block (last up-close candle inside the OR) just below it; short on the return to ~5777 (red line, starburst ~11:00 CT = 12:00 NY), again near 13:30 CT, then a sell-off to ~5690 [chart].
- YMU17 15m (~8:29-10:40): price fell from overnight into the OR, which made the day's low ~21265; OR high ~21312. Rejection block = lowest down-close candle's close ~21275 (red line). Around 10:15 CT a wick probes back toward/below 21275 but fails to take the OR low, on a red volume bar smaller than the OR-low volume bar; rally to ~21359 by the close [chart].

## Definitions
- ES contract: tick 0.25 = $12.50, $50 per point; months H (Mar), M (Jun), U (Sep), Z (Dec); symbol ES + month + yy, e.g. ESU17 ~1:15-1:52 [chart]
- True day (indices): 09:30-16:00 NY ~2:51, ~8:14
- Opening range: 09:30-10:30 NY, first 30 min = highest volume ~3:07, ~11:09
- Rejection block (as used here): the extreme candle body inside the range, e.g. the lowest down-close candle's close (bullish) or last up-close candle (bearish); reference level for re-entry ~7:43-7:55, ~9:03-9:19 [chart] [new]
- Spoos: slang for S&P futures ~2:14

## Seen only on the charts
- Every chart shades the full hour 08:30-09:30 CT green with a blue band on the volume bars: the OR is unmistakably 60 minutes.
- The OR box is drawn from OR high to OR low over the shaded hour (red outline), and the reference line (OB/rejection level) is extended right to show the later revisit.
- In all ES/NQ/YM examples the day's high or low was inside the OR or within ~30 min after it.

## Open questions
- Is the OR low/high measured with wicks (charts suggest yes, box covers wicks) or bodies?
- What counts as "extended" vs small OR for indices? No point threshold (the bond lesson used 12 ticks).
- The OR30/OR60 relationship is promised for the next lesson; until then, which one should the bot treat as the default? The 2023 lessons use 09:30-10:00.
- Is the 10:30-11:00 window (where several returns to the OB/OR occurred) a defined entry window?
