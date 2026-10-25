# cc08_006 ICT Mentorship Core Content - Month 08 - When To Avoid The London Session (stK2gNqhLaM)
Recorded April 2017 (lesson 6 of the Month 08 day-trading model) / forex, London session / no charts: three text slides only / 34 min.

## Summary
A no-chart rules lesson: a list of filters that rule out a London-session day trade, a list of characteristics of the overnight ranges (CBDR = Central Bank Dealers Range, Asian range) that make London sloppy, and a short list of conditions that make the London open kill zone ideal. The filters are written for London in FX, but most are day-level filters (ADR, consecutive closes, FOMC, NFP, holidays, news count) that a bot can apply to the NY session in index futures. Pip thresholds are FX-only. He says the filters override the daily bias.

## Rules
Day filters ("London not ideal"), slide at ~08:20 [chart]
- Skip the day after a large-range day: previous day's range > 2x the 5-day average daily range (ADR); expect consolidation or chop (~01:22) [chart] [new]
- After 3 consecutive up closes on the daily, avoid longs on the 4th day; after 3 consecutive down closes, avoid shorts. Expect a pause or a deep retracement (down day or long wick); a big range day is unlikely on the 4th day (~02:07-03:32) [chart] [new]
- After an FOMC (14:00 NY) that produced extreme whipsaw up and down, skip the next London open; the reaction, not the decision, is what counts (~03:36-04:40) [chart] [new]; compare Ep 03 (don't trade the FOMC release itself)
- NFP Friday (usually the first Friday of the month): no London trade at all (~04:45) [chart]; consistent with Ep 03/04
- The trading day before a long weekend or holiday (usually Friday, sometimes Thursday): skip, expect a quiet session (~05:06) [chart] [new]
- Multiple high/medium-impact news releases for the market in the session: tricky, avoid. Ideal is exactly one high- or medium-impact release, giving one manipulation leg then expansion into NY (~05:59-07:32) [chart] [new]
- No news at all in the session = "wildcard" day; can be clean or can be hit by a surprise (~07:32) [chart] [new]

Overnight-range characteristics, slide at ~20:00 [chart]
- CBDR > 50 pips: possibly pass on London (~08:33) [chart] [new] (FX-only threshold)
- Asian range > 40 pips: only consider the "delayed protraction" profile from lesson 5, and only if all its criteria are met; otherwise sit out (~09:28) [chart] [new] (FX-only threshold)
- Sustained rally or decline starting at 20:00 NY = poor London; the move continues with little retracement, which comes, if at all, in NY (~09:45, ~12:51) [chart] [new]
- CBDR (from 14:00 the prior day to 20:00) and/or Asian range must be visibly a small, tight consolidation, distinct from prior days' ranges on the 15m chart. Wide, erratic or trending in either = avoid London (~10:07-11:49) [chart] [new]
- Aim for days when the banks "hold" the market in a narrow range to build orders above and below (open float) (~11:52) [chart] [new]
- When conditioned for "London slop": sleep in and trade the NY open (~13:20) [chart] [new]
- If you trade anyway against these filters, use very small risk (~14:09) [new]
- These filters rank above the daily bias: with them present, bias doesn't matter (~19:14-19:35) [new]

When the London open kill zone is ideal, slide at ~30:00 [chart]
- Daily chart is clearly respecting PD arrays (going to order blocks, closing gaps as expected) (~20:42) [chart]
- Market recently responded off a higher-timeframe PD array and has not yet met an opposing PD array (slide only, not spoken) [chart] [new]
- Daily poised to trade up to a premium array -> London longs; down to a discount array -> London shorts. The distance from price to the next premium/discount array sizes the expected move; it can take several days, giving setups on consecutive days (~21:29-23:21) [chart]
- These only apply when none of the avoid conditions are present (~23:04-23:31) [new]
- If the daily range has not recently exceeded its 5-day ADR (previous day did not reach it), an expansion day is due: often 1.5-2x the 5-day ADR (~23:33-25:21) [chart] [new]
- Keep a running log per instrument of each day's range vs the 5-day ADR; trade one or two instruments (~23:42-24:12) [new]

## Trade examples
None; the lesson is slides only by design (~00:29).

## Definitions
- CBDR (Central Bank Dealers Range): the window from 14:00 to 20:00 NY of the prior day (~10:30) [chart: slide uses "CBDR"].
- Asian range: from the Asian open to midnight NY (~12:16). (Lesson 5 gives the exact window.)
- Open float: orders building above and below a held, narrow range (~11:52).
- London slop: a sloppy London session caused by the conditions above (~13:20).
- Expansion day: a day whose range reaches 1.5-2x the 5-day ADR (~25:12).
- Accumulation-manipulation-distribution: the intraday business: accumulate in the tight range, run price against the bias to induce traders, distribute near the day's extreme at London close or late NY (~16:16) [chart].

## Seen only on the charts
- Slide wording: "The Daily chart is clearing [clearly] respecting PD Arrays"; "Market has recently responded off a HTF PD Array & not meet [met] an opposing PD Array" (frame 00-30-00).
- Slide tags: CBDR > 50 [Possibly Pass On London]; Asian > 40 [Consider Delayed Protraction]; trend from 20:00 [Poor] (frame 00-20-00).

## Open questions
- Index-futures equivalents of the pip thresholds (50 / 40 pips) are not given; a bot would have to express them as a fraction of ADR.
- "Large range day" is measured against the 5-day ADR including or excluding that day? Not said.
- "Extreme whipsaw" after FOMC has no numeric definition.
- Whether these London filters should gate the NY AM session for the bot: he applies them to London and says to trade NY instead, so they may not disqualify NY at all.
- "Three consecutive up closes": close > open, or close > previous close? Not specified.
