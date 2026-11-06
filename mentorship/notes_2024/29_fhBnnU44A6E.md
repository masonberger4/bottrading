# 2024 Mentorship Lecture 29 (fhBnnU44A6E): "How to manage missed entries" + the ORG mid-gap model in full (gap > 40 handles, first FVG 09:31-10:00 toward the mid-gap, 75-80% off at mid-gap, rest to full gap fill), day-before-FOMC = muddy, wait for the mohawk
Live Tue Sep 17 2024, ~09:30-11:45 ET, NQ (Dec NQZ24), ES for SMT, 15s + 1m, 5m, 1h. ~2h13m (migraine, overlay complaints, critics, carrying-charge aside; skipped). Captions only.
Source tier: 2024 Mentorship. No live trade; a late "pretend" short is framed with stop and partials. No stream on FOMC day (Sep 18).

## Summary
Day before FOMC. Premium ORG of over 100 handles (settlement ~19,661 vs ~19,795 open). ICT restates his opening-range-gap model as a complete, codable model: gap of more than 40 handles (larger is better), bias = toward the gap's midpoint, wait for the first presented FVG (earliest at 09:31, before 10:00) and enter it in that direction, target the mid-gap (70% by 10:00), take a partial below a short-term low and move the stop to cover costs once it breaks, take 75-80% off at the mid-gap and let the rest try for the full gap fill with the stop above the short-term low. Hold until stop or target. On the day before FOMC price is careless (mohawks past the FVG), so wait for the run to the FVG's extreme and sell inside the wick it leaves. Missed entries: use the next lower timeframe (a missed hourly setup can be entered on 15m/5m).

## Rules
- ORG MID-GAP MODEL (the clearest statement so far; adds to ORG-CE-WINDOW, OPEN-RANGE-TRADE, FPFVG-DEF) ~25:00-30:00, ~34:00-35:00, ~55:00-59:00, ~1:04, ~1:10
  - Filter: ORG of more than 40 handles; the larger the better (today >100) ~50:00, ~52:00
  - Bias for the first 30 minutes = toward the mid-gap (premium ORG = short) ~34:00
  - Entry: the first FVG that forms 09:31-10:00 on the 1m chart ("it can't be on the 9:30 candle") ~34:00, ~55:00
  - Target: 50% of the gap; 70% strike by 10:00, not 100% ~25:00-26:00, ~58:00
  - Management: once price breaks a short-term low, move the stop to cover costs; with >1 contract take a partial below that short-term low ~57:00
  - At the mid-gap take 75-80% off; the rest can aim for the full gap fill with the stop above the short-term low ~58:00
  - Hold until stopped or target, as long as price stays on the right side of the stop and the mid-gap has not traded ~1:04
  - "You have an entire trading model right there and you're done in 30 minutes" ~35:00
- DAY BEFORE FOMC: price is muddier, colors outside the lines; don't use the lowest entry threshold; let it run to the FVG's extreme first (mohawk), then sell inside that wick toward the mid-gap; stop above the candle (wick past the FVG is fine) ~18:00, ~32:00, ~36:00
  - Trade the morning session only the day before FOMC; keep expectations light; no one positions big ahead of FOMC ~11:00, ~14:00
- FOMC DAY: inexperienced traders avoid trading it completely; no stream ~4:00
- MISSED ENTRY: drop a timeframe; treat "my 1m as your hourly" and use 15m/5m to enter a move already started on the hourly ~8:00-9:00
- SMT: prefer ES vs NQ; Dow only as an early warning (price-weighted, skewed by large stocks); body-based SMT: a higher wick but lower bodies is still a divergence ("wicks do the damage") ~39:00-41:00
- MIN RANGE: the trade must afford at least 20 handles from entry to target; if not framable, sit still ~1:33
- Breaker mean threshold: midpoint of the order block/breaker range; a rally that stays below it keeps the breaker valid; wick or gap midpoint = CE ~1:33, ~1:49
- PM pretend short: stop one tick above the wick CE of the entry candle; two partials, then roll the stop and let the market take the rest out (no chasing a recent high) ~2:00-2:07
- Large relative equal highs (Aug 27-29 2024, ~19,926 Dec equivalent) as the likely FOMC-day draw ~43:00

## Risk / Process [beginner]
- Use the 30-minute model as a daily lab: one contract, no pyramids, record stops and feelings ~1:04, ~1:18
- Don't force trades in lethargic, two-sided conditions; "this is where you do not want to trade" ~1:44

## Trade examples
- 2024-09-17 AM (no live trade): premium ORG >100 handles; mid-gap ~19,728.25; first FVG at the 09:33 candle; short entry framed at ~19,794.75 (candle 3 high); mohawk above the FVG then delivery to the mid-gap; ES/NQ body SMT at the high.
- 2024-09-17 late AM (pretend): short from a 15s/1m gap near a breaker; stop one tick above a wick CE; two partials, then stopped out on the balance near a rejection block.

## Definitions
- Mean threshold: 50% of an order block / breaker range. Consequent encroachment: 50% of a gap or wick.

## Open questions / conflict checks
- [conflict check] ORG > 40 handles threshold for the mid-gap model: ORG-SIZE card (second 2024 source with L27 "small ORG").
- [conflict check] Trading inside 09:31-10:00 toward the mid-gap: OPEN-RANGE-TRADE and ORG-CE-WINDOW cards.
- [conflict check] Day-before-FOMC morning only; FOMC day avoid: FOMC-DAY card.
- [conflict check] Body SMT (lower bodies despite higher wick): SMT definition (new conflict 45, SMT-BODY).
- [new] `org_midgap_model` (gap > 40 handles, first FVG 09:31-10:00 toward the mid-gap, 75-80% off at the mid-gap); default off.
- [new] `pre_fomc_mohawk_entry` (wait for a wick past the FVG extreme before entering); default off.
