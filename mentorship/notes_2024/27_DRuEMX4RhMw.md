# 2024 Mentorship Lecture 27 (DRuEMX4RhMw): morning after a large range day = chop, small ORG and shrinking premarket ORG = muddy open, FVG quadrant grading (upper half / lower quadrant must hold), scale in at CE and lower quadrant, PM session is the easiest
Live Thu Sep 12 2024, ~09:35-11:08 ET, NQ, 15s + 1m, 5m, 1h/60m, daily. ~1h33m (Twitter, critics, Caleb asides; skipped). Captions only.
Source tier: 2024 Mentorship. No live trade taken; the lecture is a lesson in high-resistance conditions after the Sep 11 large range up day.

## Summary
The day after a large range up close (Sep 11). Small premium ORG (~15 handles), half-gap done in minutes, open inside today's NDOG. Price chopped: dropped into a 5m BISI, ran minor buy side, swept short-term lows inside the ORG, tagged the NDOG and previous settlement several times. ICT uses the chop to teach: on the morning after a large range day, new traders don't trade the AM session; the day's first low is a suspect trap low; FVGs are graded by quadrants (bullish = sensitivity in the upper half; if it goes deeper it must respect the lower quadrant and leave the far boundary untouched); scale in with one contract at CE and one at the lower quadrant, stop 2-3 ticks past the gap. The better trading is the PM session from 13:30, aiming at whichever of the lunch high/low or day high/low is the obvious draw.

## Rules
- LARGE RANGE DAY (restated, "since 1995, never deviated"): the morning after a large range day is high resistance; if you're new, don't trade the AM session; if experienced, be careful; trade the PM session instead ~21:00, ~34:00-35:00, ~1:12-1:13, ~1:25
  - The first low of the day (after a large range up close) is always a suspect low; expect it to be a trap (turtle soup / scalp the run) ~26:00, ~57:00
  - Going in at 09:30 after a large range day: met with adversity, likely stopped out even when right on direction ~49:00
- SMALL ORG (adds to ORG-SIZE): a very small ORG (~15 handles) = don't expect big volatility, don't get excited ~3:00, ~16:00
  - PREMARKET ORG SHRINK: before 09:30 watch whether the ORG is maintained or shrinks; if it shrinks into the open, expect a muddy first 30 minutes ~16:00-17:00 [new]
- OPENING RANGE = 09:30-10:00 (30-minute algorithmic period, "15 minutes is not enough"); it sets the initial buy side and sell side; the first FVG 09:30-10:00 is also the "first presentation" ~12:00-14:00, ~18:00
  - Standard deviations of the first 30-minute high-low projected up/down give intermediate and long-term daily highs/lows ~18:00-19:00 [new]
- FVG QUADRANT GRADING: fib on the gap (low of candle 1 to high of candle 3): 25/50/75%; if bullish, sensitivity in the upper half; ideally it doesn't fill; if it trades below CE it must respect the lower quadrant and must not trade to the far boundary ~6:00-8:00, ~53:00-56:00
- SCALE-IN ENTRY: one contract at the gap CE, one at the lower quadrant; stop at least 2-3 ticks past the gap's far boundary (it can touch it) ~1:02-1:04
  - Don't buy just because a down candle reached the level; wait for a little more information (immediate rebalance, wick CE, volume imbalance confluence) ~1:04-1:07
  - Some prop firms forbid adding to a losing trade; then wait for the confirmation entry instead ~1:04
- PM SESSION (13:30 to close): identify the lunch high/low and the day's high/low (two buy sides, two sell sides); price will go to one of them and it will be obvious; write your guess in the journal before 13:30 ~1:22, ~1:29-1:31
  - If the morning range holds into 13:00-13:15, expect them to release it in the PM ~41:00
  - Last hour: on expansion days it reaches a higher high (bull) or lower low (bear); last 45 minutes = how they settle ~1:31
  - "The PM session is the easiest trading session for index futures, always"; you never need to trade the morning ~1:31
- Same frame for London: previous day high/low plus the high/low formed up to 02:00 ET ~1:22
- Busy fall ahead: lower leverage; trade frequency on lower TFs can rise ~11:00

## Risk / Process [beginner]
- After a large range day, sit still and tape it (don't even demo trade) ~1:25
- Multi-timeframe matrix: daily, 4h, 1h, 15m, 5m, then 5-4-3-2-1m and 45s-30s-15s-5s ~30:00

## Trade examples
- 2024-09-12 AM (no trade): day after the Sep 11 large range up day; ORG ~15 handles; drop into a 5m BISI, run of minor buy side; repeated sweeps of short-term lows inside the ORG; 1h BISI graded: low formed just above CE, swept the lower quadrant, then immediate rebalance + volume imbalance + order block sent price higher toward ORG high and relative equal highs ~19,288.75.

## Definitions
- Immediate rebalance: price retraces only to the prior candle's close; "the wick is a gap".
- Opening range: 09:30-10:00 ET (vs opening range gap = previous settlement to 09:30 open).

## Open questions / conflict checks
- [conflict check] No AM trading for beginners after a large range day; PM session preferred: supports the large-range-day filter (LARGE-RANGE-DAY / PM card if present).
- [conflict check] Opening range is 30 minutes; first FVG 09:30-10:00 as first presentation: supports FPFVG-DEF and OPEN-RANGE-TRADE.
- [conflict check] Small ORG means less volatility: ORG-SIZE card.
- [new] `fvg_quadrant_grade` (bullish FVG must hold the lower quadrant, never touch the far boundary); default off.
- [new] `scale_in_ce_lowerq` (1 contract at CE, 1 at lower quadrant, stop 2-3 ticks past the gap); default off.
- [new] `premarket_org_shrink_filter`; default off.
- [new] `opening_range_sd_projection`; default off.
