# 2024 Mentorship Lecture 31 (XiZHGOeVAOk): "Micro vs mini": day after FOMC, several-hundred-handle ORG = let them make the initial high first, live micro short from the first presented FVG, $75-100 per micro as a drill target, 20-handle filter, re-entry after an inversion FVG is touched once
Live Thu Sep 19 2024, ~09:29-10:53 ET, NQ and MNQ (Dec), 15s + 1m. ~1h24m (CFD legality, phone calls, "they're your food" rant, support/resistance rant; skipped). Captions only.
Source tier: 2024 Mentorship. Live trade: one micro (MNQ) short at the first presented FVG area ~09:49, "poor execution" but $75-100 offered.

## Summary
Day after FOMC (50 bp cut). Huge premium ORG of several hundred handles toward the Aug 27-29 relative equal highs. ICT normally would already have an entry drill on (a 40-60 handle gap would have been an entry from the first 15s gap), but on a very large ORG he waits for the market to make an initial high of the day and run it, then expects a deeper retracement. He walks the 1m candles (09:31 no gap, 09:32 no gap, ... first presented FVG) and shorts a micro at the FVG; a second, smaller FVG above the first is reached first ("Model 2022: expect it to go up into the higher one"). Drill target for Caleb: one micro, $75-100, then stop for the day; record how it feels to hold beyond it. Later re-entry rule: after price leaves an inversion FVG, allow one candle to touch it once; the next displacement lower that forms an FVG is the short, only if it offers 20 handles.

## Rules
- VERY LARGE ORG (several hundred handles): don't take the first gap; let the market make the initial high of the day and run it; then expect a deeper retracement toward the ORG upper quadrant / mid-gap; continuation is likely later ~7:00, ~9:00-11:00, ~56:00-57:00
  - With a 40-60 handle ORG the first 15s gap would already have been an entry ~7:00, ~9:00 (adds to ORG-SIZE)
- FIRST PRESENTED FVG: check each 1m candle from 09:31 forward; the first one with a gap is it ~12:00-13:00 (FPFVG-DEF)
- MODEL 2022 STACKED FVGs: if there is a smaller FVG just above the first one, expect price to trade up into the higher one before reversing ~21:00, ~36:00
- MICRO vs MINI: on a micro you don't need precise entries; risk is small; wider stops don't hurt much; on a mini be more precise ~19:00, ~41:00
- DRILL TARGET [beginner]: one micro contract, aim for $75-100 open profit, take it, stop for the day (then tape read); record feelings if you hold past it ~22:00-27:00, ~57:00
- 20-HANDLE FILTER (restated): the setup must afford at least 20 handles to its target; 18 handles = pass ~29:00, ~38:00-39:00
- RE-ENTRY AFTER INVERSION FVG: once price leaves the inversion FVG, one candle touches it once; the next displacement lower that forms an FVG is the short; if a candle wick re-touches the prior candle (no gap), wait for another displacement ~38:00-43:00
- PARTIAL at half of the run (~$75-100 on a micro), then target the ORG upper quadrant, then a 1 SD projection of the high-low ~56:00
- Balanced price range: the stop-run area that took out the initial high is a BPR (real orders were brought in) ~53:00
- ORDER BLOCK = two specific price levels: smart money's initial entry and the add if given; not supply/demand zones ~1:16
- Caleb's progression: back test the 50%-of-gap draw 2 weeks, tape read live 2-3 weeks, then one micro ~1:23

## Risk / Process [beginner]
- Capital: micro if you can't afford a mini; $75-100 a day on one micro is a meaningful goal for many ~17:00
- Journal what you feel holding a trade past your target ~23:00-26:00

## Trade examples
- 2024-09-19 AM (live, MNQ, 1 contract): several-hundred-handle premium ORG; initial high run; short at the first presented FVG area (15s), price first stabbed the higher stacked FVG (Model 2022), then sold off; ~$75-100 offered; later inversion FVG at the first FVG's midpoint; ORG upper quadrant as the next draw.

## Definitions
- Model 2022 (stacked FVGs): a smaller FVG above the first one tends to be reached first.

## Open questions / conflict checks
- [conflict check] Very large ORG = wait for the initial high before entering vs L29 "first FVG 09:31-10:00 toward the mid-gap": ORG-SIZE and OPEN-RANGE-TRADE cards.
- [conflict check] Re-entry after a stop or failed setup: REENTRY card.
- [conflict check] 20-handle minimum: MIN-ROOM card.
- [new] `large_org_wait_initial_high` (ORG > ~200 handles: skip the first gap until the initial high is run); default off.
- [new] `stacked_fvg_higher_first`; default off.
