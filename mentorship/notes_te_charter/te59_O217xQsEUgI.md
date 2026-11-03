# te59 High Resistance Liquidity Run Conditions (O217xQsEUgI)
Live NQ 1m, New York AM (CPI/PPI week, Tuesday) / ~27 min. Captions only.
Source tier: Trade Executions (2026). 2023 Mentorship wins on conflicts. NQ points.

## Summary
Long from an inversion FVG that was "qualified twice" before entry; scale in at the iFVG high on the retest; draw = New York local midnight opening price (29,878.25) then Monday London relative equal highs. Messy, high-resistance conditions: several overlapping iFVGs and midnight open as resistance. Teaches wick-CE "no bodies buried below" rule, the "leave part of the gap open" strength signature, and taking a partial on a stop order during a retracement.

## Rules
- Entry: inside the inversion FVG, after it is qualified/confirmed twice (closes that respect it after it inverts) ~11:20-12:49
- Initial stop at the entry candle's low ± a tick or two ~0:03
- Add on a retest that "kisses" the high of the iFVG ~0:44-1:15, ~4:49
- After adds, stop to just below the iFVG low minus one tick (average = iFVG high) ~2:50
- Wick CE rule: no candle BODIES closing below the CE of the reference wick; if one does, the very next candle must show immediate willingness higher; prefer a close above it ~1:15-4:21
- Close above the reference level → roll stop to cover costs ~5:52-7:45
- Midnight New York opening price is a strong magnet/draw; take most of the position (5 of 7) just below it ~6:55-7:45, ~10:48-11:20
- Best case target: Monday London relative equal highs (buy side) ~7:15
- Strength signature: a bullish FVG/volume imbalance with a small portion left open (not fully filled) = still bullish; full fill makes higher harder; untouched = breakaway/measuring gap ~9:54-10:22, ~13:16-14:41
- iFVG resistance overhead (formed 07:29 that morning) = expect messiness; partial just above minor buy side ~15:12-16:29
- Raise stop ("increase paycheck") to just below a wick high after partials ~16:29
- Bullish confirmation level: a close above the open of the down candle (873.75 → 874) ~19:42-20:21
- PD-array defense: wick = PD array 2; last defense = the swing low with the stop just below ~19:12-19:42
- Partial via STOP order on a retracement (2 of 7 contracts) when price may come back; reduces need to be right ~22:43-24:06
- Anticipate/predict, don't just react ~18:40-19:12
- No market replay; trade the hard right edge ~1:51, ~8:59

## Trade examples
- NQ: 12 contracts total built (4 + 2 + adds); 5 off below midnight open (~$4,000 hypothetical); 2 off on a stop partial; remainder stopped at the swing low. Session bias, not daily bias ~10:48-11:20, ~20:21-20:50

## Definitions
- High resistance liquidity run (HRLR): price path cluttered with overlapping iFVGs/old opens; expect slow messy delivery
- Qualified iFVG: inverted gap that has been respected by closes at least twice before used for entry

## Open questions
- iFVG "qualified twice" before entry: switch `ifvg_min_qualifications` (0/1/2) [conflict check: 2023 iFVG use]
- Midnight open as first target: switch `tp1_midnight_open` [check 2023]
- Partial-on-stop during retrace: switch [new]
- "Leave part of the gap open" as continuation filter: switch [new]
