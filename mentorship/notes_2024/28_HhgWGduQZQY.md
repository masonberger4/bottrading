# 2024 Mentorship Lecture 28 (HhgWGduQZQY): "How to trade FVGs correctly": candle 1/2/3 roles, entry at candle 3 extreme +/- 1 tick, stop at candle 1 (conservative) or candle 2 (max leverage), adds at the near quadrant and CE, the far half should stay open, first FVG must form at 09:31 or later
Live Mon Sep 16 2024, ~09:30-11:42 ET, NQ (Sep contract; roll to NQZ24 next day), 15s + 1m, 5m, 1h. ~2h12m (Twitter, critics, signal-service rant; skipped). Captions only.
Source tier: 2024 Mentorship. Week-long entry drills for Caleb start here. No live trade taken ("when I can find the balls to trade in front of you"); entries are shown as drills.

## Summary
Discount ORG (open below Friday's settlement), straight drop from the bell below sell side, then a Judas low and a rally. ICT lays out his FVG mechanics precisely: candle 2 is the FVG ("trigger") candle; candle 3 is the entry candle; for a short, enter at candle 3's high less one tick, add at the near (lower) quadrant and again at CE; bodies must not close beyond CE; the ideal is price entering only the near half, once (at most twice), leaving the far half open. Stop goes above candle 1 (conservative, one-contract trader) or candle 2 (maximum leverage). A failed FVG usually means an inversion FVG is forming: trade it the other way at half the size. Targets are the easiest exits first: the first gap, the ORG lower quadrant, the ORG mid-gap (70% in the first 30 minutes), the smooth highs. He corrects himself mid-lecture: the first presented FVG cannot be on the 09:30 candle; it can only appear at 09:31 or after.

## Rules
- FVG CANDLE ROLES: candle 1, candle 2 (the FVG / "trigger" candle, the one with the imbalance; frames the gap), candle 3 (entry candle; its low does not overlap candle 1's high in a bullish FVG) ~20:00, ~25:00, ~41:00
  - ENTRY: long at candle 3's low + 1 tick; short at candle 3's high - 1 tick; "that's how ICT enters it" ~30:00, ~41:00
  - ADD: on a retrace into the near quadrant (long: upper quadrant; short: lower quadrant) add more; add again at CE if reached ~30:00, ~41:00-43:00
  - STOP (adds to conflict 39 / STOP-PLACE): conservative (one-contract trader) = beyond candle 1; maximum leverage = beyond candle 2 ~20:00
  - ADVANCED STOP (only after months of practice): one tick beyond a wick's CE when it is two layers of gaps; then trail to near the FVG's far quadrant as price leaves ~2:02
- FVG HEALTH: wicks may go through CE but bodies must not close beyond it ~32:00
  - Bullish ideal: price drops only into the upper half, one candle (at most two) enters, the lower half stays open = "extremely bullish", trust the stop ~55:00, ~2:03
  - CE (include the separation between candle 1's body and candle 3 when measuring) is the most important level ~43:00
  - A gap that is traded deep into its far half after an entry was not a valid short/long ("you would have been stopped") ~17:00
- FAILED FVG = INVERSION: if stopped out on an FVG you are probably watching an inversion FVG form; trade it the other way with half the size of the loss trade ~52:00
- FIRST PRESENTED FVG TIMING (adds to FPFVG-DEF): it cannot be on the 09:30 candle; it can only appear at 09:31 or after ~1:14-1:15
- ORG MID-GAP (restated): 70% of the time half of the ORG is hit by 10:00; "we've seen one or two times where it hasn't"; it's still on the table later ~25:00, ~46:00-47:00, ~59:00
- TARGETS: the easiest exit you can comfortably wait for: the first gap, the ORG lower quadrant, the ORG CE, high of day, opening price; any can be a partial or the terminus ~1:13-1:14
  - Beginner: one exit; after 2-3 weeks of drills: first partial at the first liquidity, terminus at the next ~1:46-1:47
  - Minimum range: the setup must afford at least ~20 handles; 10 handles is static noise in NQ (you can be stopped and still be right) ~1:39, ~1:47
- ORDERS: entries and exits on limits (rarely a stop entry); market orders only to get out to protect money ~36:00
- Let the first few minutes after 09:30 do whatever they want; don't predict before price shows a gap ~5:00
- 08:30 medium-impact news: trust price, not the data ~8:00
- CONTRACT ROLL: watch the volume numbers (barchart.com), not influencers; roll to NQZ24 on Sep 17 ~13:00-14:00

## Risk / Process [beginner]
- Learn on micros (MNQ $2/point, MES $5/point; NQ mini $20/point) ~37:00
- Drills: log entry, risk, target, time to stop or target, drawdown ~1:40
- Don't trade ICT's drills with real or funded money ~1:55

## Trade examples
- 2024-09-16 AM (drill, no live trade): discount ORG; drop below sell side; failed bearish FVG (traded into its lower half); bullish first presented FVG ~19,365-19,378 (CE to candle 3 low); fill at ~19,405 example with ~3 handles heat, lower half left open; rally to the ORG lower quadrant, missed the ORG CE; high-low-higher "valid trap" left.

## Definitions
- Trigger candle: candle 2 of the FVG.
- Mohawk: price coloring outside the lines (a wick past a level) before reversing.

## Open questions / conflict checks
- [conflict check] Stop beyond candle 1 (conservative) vs beyond candle 2 (max leverage): third source for m2024 conflict 39 (STOP-PLACE).
- [conflict check] First FVG must form at 09:31 or later: FPFVG-DEF card.
- [conflict check] Failed FVG -> inversion at half size: re-entry after stop-out theme (RE-ENTRY card if present).
- [new] `fvg_entry_c3_plus1tick` (entry at candle 3 extreme +/- 1 tick with adds at near quadrant and CE); default off.
- [new] `fvg_far_half_open_filter` (bodies must not close beyond CE); default off.
- [new] `min_range_20_handles`; default off.
