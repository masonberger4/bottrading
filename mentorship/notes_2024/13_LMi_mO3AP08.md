# 2024 Mentorship Lecture 13 (LMi_mO3AP08): Caleb's model stated (NDOG/NWOG draw with relative equal highs/lows), gap-down ORG CE trade, partial at every broken short-term high
Live 2024-08-20 (Tue), ~09:29-10:30 ET, NQ, 1m + 15s + daily. ~1h02m. Captions only.
Source tier: 2024 Mentorship. No trade executed on stream; hindsight walkthrough of the long from the gap-down open.

## Summary
NQ gapped down at 09:30 below the Aug 20 NDOG. ICT states Caleb's model: the draw is an NDOG or NWOG with relative equal highs just below it (bullish) or relative equal lows just above it (bearish). He also teaches the opening range gap trade: on a gap-down open, its CE is the highest-probability target; ICT says he often goes long right at the open toward the ORG CE "with no bias". Price filled the ORG, used the NDOG as support, then reached the lower quadrant and CE of a daily volume imbalance. Partial rule: every short-term high broken in a long is a partial candidate; take partials rather than moving the stop early.

## Rules
- CALEB'S MODEL (draw on liquidity): bullish = relative equal highs just below an NDOG or NWOG (the gap is the magnet); bearish = relative equal lows just above an NDOG/NWOG; NDOGs up to 5 days old, NWOGs up to 5 weeks ~6:00
- NDOG labeling: the 17:00-18:00 gap formed Monday evening is labeled for the NEXT trading day (Tuesday) and carried forward ~10:03
  - A filled NDOG is still used (bodies respect it); don't discard it once filled ~10:03
- OPENING RANGE GAP (ORG): prior RTH settlement (16:15) to the 09:30 first print ~0:30, ~44:01
  - Keep the ORG high/low and quadrants on the chart all day; the algorithm refers back to them repeatedly ~38:01
  - GAP-DOWN OPEN: drop the fib on the first tick; the ORG CE is the highest-probability target; ICT often buys right at the open if there's room to the ORG CE ("you don't even need to be right on the bias") ~38:01, ~48:00-50:00
  - If the gap is going to fail (bearish), it trades about halfway (or a bit more), fails to close, then drops ~50:00
  - If bullish, it closes the gap and then uses the ORG high (and nearby NDOG) as support; bodies stop at the ORG high ~40:00
- CE vs mean threshold: CE = midpoint of a gap (FVG, VI, wick); mean threshold = midpoint of an order block ~14:01
- DAILY VI: a daily gap formed only by connecting wicks; split into quadrants; watch the CE; a 1m body closing exactly on the upper quadrant and leaving the rest open = attention there ~8:02-16:00
- 15s FVG forming in the upper half of a 1m FVG = extreme strength; max overshoot of the 1m FVG = CE of the highest wick to the left ~20:17-26:01
- After price reaches the lower quadrant with speed, look for the CE; a short-term high after a target is reached = distribution ~22:00, ~52:01
- PARTIALS (important): in a long, every short-term high that gets broken is a partial candidate; take a partial rather than moving your stop loss early in development ~30:01-32:00
  - "Running down equity": taking partials at premium levels while the move reaches for the target ~32:00, ~46:10
- If price is reaching for a target, it shouldn't spend a long time in consolidation below relative equal highs; you want it to plow through ~36:00
- Early session: you don't need to know right away; read the first minutes ~2:07
- Wick CE stops a move like a gap; in a macro (after 09:50) it would run directly to the target ~4:01

## Risk / Process [beginner]
- Caleb works 12-hour shifts; limited time window ~44:01
- Graduated step: reach for a target but don't require it to be hit to exit profitably ~46:10

## Trade examples
- 2024-08-20 long (hindsight): gap-down open below the Aug 20 NDOG; ORG CE (~08:34 per caption; actual price unclear) and ORG fill; NDOG used as support; 15s FVG in the upper half of the 1m FVG; rally to the daily VI lower quadrant and CE. ORG high noted at 19,850.25.

## Definitions
- Caleb's model: NDOG/NWOG magnet with relative equal highs/lows in front of it; FVG entry (IOFED) after the opposite side is taken.
- Mean threshold: midpoint of an order block (CE is for gaps and wicks).

## Open questions / conflict checks
- [conflict check] Gap-down open long at 09:30 toward ORG CE vs rulebook "no trades inside the 09:30-10:00 opening range". Switch `org_ce_open_trade`; default off; flag as conflicting with 2023 (2023 wins).
- [conflict check] RTH gap target: here "CE is highest probability" vs lecture 03 (~70% return to mid-gap) and TE te64. Consistent direction; check the exact rulebook text.
- [new] `draw_gap_with_eq_pool` (target an NDOG/NWOG only if relative equal highs/lows sit just in front of it); default off.
- [new] `partial_every_broken_high`; default off; compare with rulebook partial rules and add_ladder 631.
- [new] `ndog_valid_after_fill`; default off; check NDOG handling in rulebook.
