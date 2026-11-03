# 2024 Mentorship Lecture 10 (qoNQfVzVXZQ): Friday after TGIF hit, opening range quadrants (3-day look-back), lunch macro, TGIF timing, partial rule
Live 2024-08-16 (Fri, 10:00 medium-impact news), ~09:15-12:05 ET, NQ, 1m/5m/15m/60m + weekly. ~3h18m. Captions only.
Source tier: 2024 Mentorship. No trade (observation only). ICT mentions a Thursday 08-15 short (turtle soup near the lunch high, 15 contracts, 5 off, rest stopped on a trailed stop).

## Summary
Early Friday, NQ traded down to a confluence of the 20% TGIF level of the week's range and the upper quadrant of Thursday's opening range, then chopped all morning. ICT defines the opening range (09:30-10:00) and the opening range gap precisely, has students carry both, with quadrants, for 3 days, and explains the lunch macro (11:30-13:30) and the full TGIF rules: it can begin at 13:00 Thursday, and once a 20% weekly retracement prints, he is done for the week. Most of the stream is about logging "price delivery measurements" (time from identification to target, heat) as a progress baseline.

## Rules
- OPENING RANGE (OR) = high/low from 09:30 to 10:00 ET; there is no 15-minute opening range ~10:01, ~20:01, ~38:02
  - Mark OR high, CE, upper/lower quadrants, and the 09:30 open ~12:02, ~20:01
- OPENING RANGE GAP (ORG) = prior RTH settlement (16:15) to the 09:30 first print; can also be split into quadrants ~8:04, ~24:03-26:00
  - On a gap-up, ORG high = 09:30 open; on a gap-down, ORG high = prior settlement, ORG low = 09:30 open ~26:00
- CARRY OVER: any OR or ORG not fully used (CE/quadrants not traded to) is carried forward 3 days as key levels ~8:04, ~20:01
- Keep these on a notepad (price list) and keep the chart naked (personal preference) ~12:02-16:01
- Confluence + macro: when 2+ levels align (prior OR/ORG level, weekly 20% TGIF) with a PD array inside a macro (xx:50-xx:10), expect a strong reaction; then trade toward the smooth side ~48:00
- LUNCH MACRO: lunch = 11:30-13:30 ET ~30:01
  - If price runs up into 11:30 (impulsive or staggered), expect a retracement to the easiest relative equal low or single low formed AFTER 10:00; reverse for a sell-off into 11:30 (relative equal highs/short-term high after 10:00) ~30:01-32:01
  - The lunch run goes against the morning's winning side; midday retracements can become reversals for the day or week ~1:50:00
- TGIF (full rules) ~3:00-6:00, ~1:56:00-2:10:00
  - Weekly fib drawn low → high for an up week (high → low for down week); levels 20% and 30% ~4:01
  - TGIF can form from 13:00 Thursday (after the noon-13:00 lunch hour) through Friday's close; expect 20-30% retracement from the highest high formed at/after Thursday 13:00, when the weekly range is larger than the last few weeks ~2:00:00
  - Once a 20% retracement of the weekly range occurs: if you haven't traded, stop for the week ~2:00:00
  - If the 20% retracement happens on Thursday before the close, don't trade Friday ~1:58:01
  - After 20-30% weekly retracement, Fridays tend to be lackluster/choppy ("fickle"); a new high after that is "manual intervention" ~2:08:02, ~2:18:00
  - Take 75-80% of the position off at upside targets before Thursday 13:00 ~2:08:02
  - If Friday doesn't deliver TGIF, look for it on Monday (see lecture 06) ~5:00
- DAILY POWER OF THREE: after a bullish daily candle reaches its objective it tends to retrace 20-30% and close in the upper third; once that retracement happens, a return to the day's high is less likely; a daily close on the high hints at a retracement/short the next day ~2:04:00-2:06:01
- MINIMUM MOVE: NQ 10 handles (ICT prefers 15, so the setup needs ~20 handles of room); ES 5 handles ~1:14:01, ~2:26:15
- PARTIAL RULE (private students): in a long, if a short-term high sits between entry and target and is beyond 50% of the run, take a partial when price passes it once ~2:34:00
- ENTRY (NDOG example): limit at NDOG high + 1 tick (easiest fill); stop below the opening candle/volume imbalance ~2:28:02
- Caleb's entry technique: buy one tick below the high of a bullish FVG; sell one tick above the low of a bearish FVG ~3:16:00
- Valid relative equal highs: the pair where the left high is above the right high (primed) ~2:20:02
- Model: an inversion FVG followed by a fresh bearish FVG in the direction of bias is "very nice" ~1:20:13
  - Weak signature: a wick trades up into a gap but doesn't reach its CE ~1:20:13
- Friday afternoons: if no money was made in the morning, don't trade the afternoon ~3:00:02
- Clean vs sloppy: clean = impulsive legs with one inefficiency, run to an obvious level, retrace with one FVG; if you don't see that, don't push the day ~1:38:29
- Don't post stop levels publicly; crowded stops get run ~2:38:00

## Risk / Process [beginner]
- Log every "price delivery measurement": time identified, time to target or failure, heat; keep a daily tally of observations as a progress baseline ~54:28-1:06:01
- Expect no monetary success in the first 6 months ~1:06:01
- Draw your framework (entry, stop, first partial, terminus) ~3:06:00

## Trade examples
- 2024-08-16: confluence low at the 20% weekly TGIF level + Thursday OR upper quadrant just before 09:00 (inside a macro); choppy day afterward, no trade.
- 2024-08-15 (mentioned): turtle soup short near the lunch high, 15 contracts, 5 off, rest stopped on a trailed stop.

## Definitions
- Opening range: 09:30-10:00 high/low.
- Opening range gap: prior RTH settlement to 09:30 open.
- Lunch: 11:30-13:30 ET.

## Open questions / conflict checks
- [conflict check] Rulebook "opening range 09:30-10:00, no trades inside" vs here: OR used as levels; trading inside it not discussed in this lecture.
- [new] `or_quadrants_3day` and `org_quadrants_3day` (carry levels 3 days); default off.
- [new] `lunch_macro_retrace` (11:30-13:30, target relative equal/single low after 10:00); default off; check rulebook lunch rules.
- [conflict check] TGIF: start at Thursday 13:00, stop for the week after a 20% weekly retrace, no Friday if Thursday already did 20%, scale 75-80% before Thursday 13:00 vs rulebook tgif_exits "066". Switches `tgif_start_thu_1300`, `stop_week_after_20pct_retrace`, `skip_friday_if_thu_tgif`; default off.
- [new] `partial_at_obstacle_past_50pct`; default off.
- [new] `min_target_handles` NQ 10 / ES 5 (setup room 20 NQ); default off.
- [new] `no_friday_pm_if_flat_am`; default off.
- [new] `daily_po3_upper_third` (daily retrace 20-30% after objective); test as a filter; default off.
