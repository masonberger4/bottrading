# 2024 Mentorship Lecture 21 (eYYyonGwTRs): Friday before a US holiday (Labor Day) = no trade for Caleb, prior day's first presentation FVG kept for three days, layered NDOG/NWOG = congestion ("time distortion"), wide-spaced gaps = clean runs, raw levels in a notepad with a naked chart
Live Fri Aug 30 2024, ~09:27-11:05 ET, NQ, 1m + 15s. ~1h37m. Captions only.
Source tier: 2024 Mentorship. No trade. No live streams Mon/Tue Sep 2-3 (holiday and the first day after it).

## Summary
NQ opened with a large premium ORG under the quadruple relative equal highs at ~19,694 (left untouched Thursday). Price first popped off the CE of Thursday's first presentation FVG (09:31-10:00), made an immediate rebalance, then the day's first FVG formed and price chopped among layered NDOGs/NWOG (falling one tick short of the Aug 18 NWOG low). ICT calls this classic pre-holiday Friday action: erratic, two-sided, light volume; Caleb is told not to trade Fridays before holiday weekends (treat like an NFP week: the clean action is early in the week). When gaps are layered close together near price the session is congested; when they are spaced out, runs extend. If price slices through layered arrays without respect, it is tipping its hand toward a farther draw.

## Rules
- HOLIDAY FILTER: no live stream / trading the day after a US holiday (Monday holiday, plus Tuesday) to let post-holiday volume iron out ~4:00, ~29:00
  - Caleb: no trades on Fridays going into holiday weekends; the higher-probability setups form early in the week (treat it like an NFP week) ~28:00-29:00, ~48:00-51:00, ~56:00
  - Pre-holiday Friday: price "skitzo", disorganized, light volume; big players are not initiating ~18:00, ~20:00, ~50:00-53:00
- FIRST PRESENTATION FVG LIFE: carry each day's first presentation FVG (09:31-10:00) for a 3-day life cycle; interest wanes after day 3 (can still be used) ~6:00
  - Today: the open popped off the CE of Thursday's first presentation FVG after tapping relative equal lows and the 09:30 open; "that could be your model" ~7:00, ~10:30-11:30
- Immediate rebalance (bullish): the expansion candle's prior-candle high is touched by the next candle; it should then go immediately; if it closes back on the body and doesn't go, problematic ~12:00-14:00
- Important price action into a holiday weekend should happen before noon (people cut size) ~14:00
- EVENT HORIZON: halfway between the NWOG above (Aug 18) and the NDOG below ~19:00
- Keep levels in raw number form on a notepad; chart naked; compare the price axis to the notes ~23:30-24:00
- LAYERED GAPS: clusters of NDOG/NWOG near price act first as a draw, then as speed bumps (congestion, short-lived runs); failure to reach the lowest threshold of the cluster (e.g. the NWOG low) then dropping below = not interested in higher prices ~24:00-27:00, ~31:00-33:00
  - Spaced-out gaps = cleaner, longer runs ("interstate before 9-to-5 traffic") ~31:00
  - Price slicing through layered arrays with no respect = in a hurry toward a farther liquidity pool or imbalance ~32:00-33:30
  - The chop from congestion = "time distortion" ~44:00
- Manual intervention: FOMC/NFP-type reactions are heavily manually intervened; brokers may widen or block execution ~34:00-35:00
- Fridays generally: in a bullish week Friday tends to work inside Thursday's range, maybe a marginal higher high; make money before Friday ~49:00-50:00
- If you can't name the daily / 4h / 1h draw, don't trade that day (on a day like this) ~48:30
- "Engineering liquidity" is real; "inducement" and "smart money traps" are not ICT terms ~1:16-1:18
- Bearish OB opening price = change in state of delivery (restated) ~1:33

## Risk / Process [beginner]
- Back-test with NDOG/NWOG on the chart plus the economic calendar (holidays, big news early or late in the week) ~55:00
- Don't share live opinions on social media (it raises the need to be right) ~41:00-42:00
- Start with the first setup your eye "remembers"; it need not be your model for life ~40:00

## Trade examples
- 2024-08-30 (no trade): premium ORG; pop off Thursday's first presentation FVG CE; immediate rebalance; first FVG of the day; fell one tick short of the Aug 18 NWOG low (19,628.75 vs 19,629); chop among the Aug 16/27 NDOGs and the Aug 18 NWOG; late drift back toward Tuesday's low.

## Definitions
- Time distortion: congested, erratic delivery caused by layered PD arrays/gaps near price.
- Engineering liquidity: price building obvious levels where stops will sit, for later delivery.

## Open questions / conflict checks
- [conflict check] Pre-holiday Friday and post-holiday Monday/Tuesday skip vs rulebook holiday handling (B7 holiday weeks). Switch `skip_preholiday_friday` / `skip_postholiday_two_days` default off.
- [new] `first_presentation_fvg_life_days` (3); default off.
- [new] `layered_gap_congestion_filter` (count of NDOG/NWOG within X handles of price); same family as L20 layered_gap_high_resistance; default off.
- [conflict check] Friday in a bullish week stays inside Thursday's range: compare rulebook Friday/TGIF rules (conflict 7, B7 Friday one-sided).
