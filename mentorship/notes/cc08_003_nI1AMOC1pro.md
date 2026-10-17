# cc08_003 ICT Mentorship Core Content - Month 08 - Central Bank Dealers Range (nI1AMOC1pro)
April 2017 Core Content, lesson 3 of the "ICT Day Trading Model" month. Market: forex (GBPUSD H1, late March 2017 on the example chart); no index futures shown. Timeframe: 1h. Duration ~16 min, slide lecture.

## Summary
Defines the Central Bank Dealers Range (CBDR): the 14:00-20:00 NY range. Its height is repeated above and below as "standard deviations" (SD 1-4) to project where the London-session high of day (sell days) or low of day (buy days) should form. Only valid when the range is small (<40 pips, ideally 20-30) and only together with a directional bias. FX-centric; for index futures the time window and pip thresholds would need re-calibration.

## Rules
- CBDR window = 14:00 to 20:00 New York time; mark both with vertical lines in NY time ~4:29-5:39 [chart] [new]
- Range = highest high to lowest low in that window (wicks), or alternatively highest body (open/close) to lowest body. ICT prefers bodies: wicks differ between brokers, bodies show institutional accumulation/distribution ~6:04-10:06 [chart] [new]
- SD projection: SD1 above = CBDR high + range; SD2 = SD1 + range; and so on to SD4. Mirror below from the CBDR low ~2:00-3:01 [chart] [new]
- Size filter: range should be < 40 pips, preferably 20-30. Above ~30 projections tend to be unfruitful; a too-large range day (58 pips) is not used for day trading (scalp only) ~4:43-5:52, ~11:52-12:13 [chart] [new]
- Reason for the size filter: about one third of a ~100-pip average daily range (~33 pips), which is the expected Power-of-Three drop below the open on a bullish day (mirror for bearish) ~12:29-13:31 [new]
- Sell days: high of day typically forms within SD1-SD3 above the CBDR; ideally no more than SD2, often just SD1 ~3:05, ~3:27 [chart] [new]
- Buy days: low of day typically forms within SD1-SD3 below the CBDR; ideally no more than SD2, often SD1 ~3:17, ~3:41 [chart] [new]
- SD4 is reached only on very high impact news in London, or as part of a New York session market reversal profile ~3:56-4:23 [new]
- Projections give a zone, not a tick level: price may overshoot or fall short slightly ~11:41 [new]
- Must be combined with directional bias (weekly/seasonal/quarterly, premium vs discount PD array on the daily). CBDR helps pick the most likely LOD (bullish) or HOD (bearish), which forms predominantly in London ~6:28-7:07, ~14:27-16:05 [chart] [new]
- Bullish week ("one shot one kill"): look for the London LOD each day, preferably Tue/Wed/Thu, possibly Mon ~8:18-8:31 [new]
- Do not trade every day; use only days where conditions favor the London HOD/LOD ~7:11-7:50

## Trade examples
No trades. Four illustrative days on GBPUSD H1 (dates on the axis around 27-31 Mar 2017, partly legible):
- Day 1: body CBDR 13 pips (wicks 22). SD2 up projected the London high almost exactly (red 2SD box, down arrow) ~10:44-11:41 [chart]
- Day 2: body CBDR 58 pips (wicks 92) - labelled "Too Large", skipped ~11:52 [chart]
- Day 3: body 19 pips (wicks 34). SD1 below; LOD formed just inside SD1, then strong rally ~13:35 [chart]
- Day 4: body 16 pips (wicks 51). SD2 below; LOD about 1 pip beyond SD2, formed in London ~13:56 [chart]

## Definitions
- Central Bank Dealers Range (CBDR): price range 14:00-20:00 NY, body- or wick-based ~4:34 [new]
- Standard deviation (in this context): one multiple of the CBDR height added above its high / subtracted below its low; not a statistical SD ~2:08 [new]
- 20:00 NY = start of the Asian range; London session follows ~11:31

## Seen only on the charts
- Summary slide: "Ideal Sell Days Create HOD" bracket spans SD1-SD2 above; "Ideal Buy Days Create LOD" spans SD1-SD2 below; SD3/SD4 sit outside the brackets ~3:40 [chart]
- Wick vs body ranges differ a lot (22/13, 92/58, 34/19, 51/16 pips): the body version passes the size filter on 3 of 4 days, the wick version on only 2 (22 and 34) ~5:00, ~9:20 [chart]
- Day 4 is filtered as OK on bodies (16) although its wick range is 51 - so the filter is applied to the body range ~9:20, ~14:20 [chart]

## Open questions
- Index futures: what replaces 14:00-20:00? (Futures settle 16:00-17:00 ET, so the window spans the daily break.) Later ICT material uses this window for FX only; the bot needs its own index CBDR window and a size threshold in handles (e.g. one third of ES ADR?).
- Does "body" range include the 14:00 candle open and the last candle before 20:00 close? Which timeframe for bodies (chart is H1; 15m likely later)?
- How to choose between SD1 and SD2 as the expected HOD/LOD in advance - no rule given beyond "ideal ≤ SD2".
- "Range > 30 unfruitful" vs "< 40 acceptable": 30-40 is a grey zone.
