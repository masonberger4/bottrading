# 2024 Mentorship Lecture 22 (Ipjk9S8HTbA): day after a large range day = sit out the AM (trade from 13:30), distorted first presentation FVG, discount ORG mid-gap then NDOG, 70% statistic "back to 1987"
Live Wed Sep 4 2024, ~09:27-10:45 ET, NQ, 15m/5m/1m. ~1h15m. Captions only.
Source tier: 2024 Mentorship. No trade (Caleb is told to sit out; ICT says he would have shorted at the daily VI CE on Sep 3 and traded the 13:30 PM session).

## Summary
Tuesday Sep 3 (first day after Labor Day) was a large-range down day. Wednesday NQ opened with a large discount ORG, ranging between the Aug 13 daily FVG high and its CE, near Tuesday's daily low. Rule: after a large range day (up or down), beginners sit still in the morning session; the AM is "fickle" and arrays get colored outside the lines (bodies outside the first FVG); the cleaner setups are in the afternoon (PM session from 13:30, 13:50-14:10 macro). Today: a small drop, first FVG formed, mid-gap hit (the 70% statistic, which he says he tracked back to 1987 Globex data), run to the NDOG (low-hanging fruit), a 10:00 news drop took the sell-side, then a rally to the ORG upper quadrant and the relative equal highs at the NDOG top. Yesterday's discount ORG did the opposite (never reached even the first quarter), the 30% case.

## Rules
- POST LARGE RANGE DAY: after a large range day (daily candle much larger than normal, up or down), beginners do not trade the AM session; trade the PM session (from 13:30) or later in the week ~7:00-8:00, ~13:00-14:00, ~19:00, ~23:00, ~27:00-28:00
  - Taught in CC 2016-17 too: high-probability setups after large range days are in the afternoon ~19:00
  - In the AM after a large range day, bodies may sit outside the FVG (distortion); normally bodies respect the FVG range and only wicks poke out ~13:00, ~16:00, ~42:00
  - Late public goes short at the open after a big down day; that becomes buy-side fuel ("engineering liquidity") ~14:00, ~47:00
- ORG MID-GAP: on a discount ORG the 70% case is a move up to the mid-gap between 09:30 and 10:00; statistic tracked "back to 1987 using Globex numbers" ~15:00-17:00, ~30:00-34:00
  - If an NDOG/NWOG sits inside the ORG above the mid-gap, it is the next target after the mid-gap (low-hanging fruit) ~33:00
  - Model stated: first FVG (09:31-10:00) entry, partial at the mid-gap, terminus at the NDOG low; it need not be NDOG, NWOG works; the first one traded to ~37:00, ~59:00
  - Contrarian alternative: short the inversion FVG, target the sell-side ~59:00-1:00
- Trending days give only one chance at the first presentation FVG; non-trending days return to it several times ~12:30
- Bullish BISI: if the idea is bullish, better that price does not return to its CE ~22:00
- 10:00 news: used as a smokescreen to run the obvious sell-side under new longs ~35:00-36:00
- Upper quadrant of the ORG + relative equal highs + NDOG top as the session target ~48:00-49:00
- PM session starts 13:30; 13:50-14:10 macro ~27:00

## Risk / Process [beginner]
- First 6-12 months: very low expectations; celebrate milestones in the journal, not on social media; confide in a fellow student, not a spouse ~20:00-21:00
- Screenshot with full-size candles (bodies visible) ~23:00-24:00

## Trade examples
- 2024-09-04 AM (no trade): large discount ORG after the Sep 3 large range down day; first FVG distorted (bodies outside); mid-gap hit; NDOG (18,993.75-18,999.75); 10:00 news drop to sell-side near Tuesday's low; rally to the ORG upper quadrant and relative equal highs.
- 2024-09-03 (ICT, described): would have shorted at the CE of the daily VI in the AM and held 2-3 contracts into the 13:30 PM session.

## Definitions
- Large range day: a daily candle with a range well beyond recent days (not quantified).

## Open questions / conflict checks
- [conflict check] No AM trades after a large range day (trade PM from 13:30) vs rulebook day filters. Switch `skip_am_after_large_range_day` default off; "large range" needs a proxy (ours, e.g. daily range > 1.5x 20-day ATR).
- [conflict check] ORG mid-gap model with the NDOG as terminus restates L13/L14; same switches (`org_midgap_target`, `org_ce_open_trade`).
- [conflict check] Trading the 09:30-10:00 OR (first FVG to mid-gap) again vs rulebook no-trade 09:30-10:00 (conflict 3).
