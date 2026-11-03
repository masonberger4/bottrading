# te63 Jackson Hole Day 2 (iSWZOe3aUFE)
Recorded 2026-08-28 (Friday, JH day 2) / NQ 1m / ~25 min. Captions only.
Source tier: Trade Executions (2026). 2023 Mentorship wins on conflicts. NQ points.

## Summary
Long on JH day 2: grade the 07:00 range (high 29,665, low 29,597.50 within the window), take the projected low below it, then long inside an iFVG (from a 09:30 SIBI displacement) aiming for relative equal highs and an old gap; exited mostly before the 10:00 Fed chair speech, remainder stopped. Price then dropped into Thursday's 09:55 discount wick (bodies held its upper half), then ran to 29,757.25 and 29,808 (named targets from te62). Mostly commentary on not trading Fridays/high-volatility weeks and on the beginner path.

## Rules
- Grade the range from 07:00 (highest high / lowest low inside the window; ignore highs outside the window - "no form fitting"); use fib projections below the range for the low ~0:00-2:21
- 09:30 displacement (SIBI) is not treated as FPFVG; it's a gap that can become an iFVG if it qualifies ~4:44
- Entry inside the iFVG after the low projection is hit (1-2 ticks below OK) → target buy side / relative equal highs / old gap ~4:44-6:56
- Bodies supported by the half (CE) of the iFVG = bullish ~4:44-6:56
- Before a scheduled 10:00 Fed chair speech: exit/fund the trade, raise stop; don't try to be perfect ~6:56-8:57
- Previous day's discount wick (Thu 09:55) upper half respected on a body basis ~6:56
- Jackson Hole week: expect volatility and "second runs" (the start of a run gets retested/swept); seek & destroy profile ~11:25
- Experienced traders can trade every day including report days and HRLR; ICT trades every Monday of NFP week; Fridays optional (take 3-day weekend if profitable) ~13:34
- New traders: JH week → tape reading only, not even demo ~18:03-20:08
- Lesson: when bodies fail at a midpoint again, roll stop to just below the CE of the longest wick ~22:10
- Learning path: log observations → backtest for months → demo/paper minimum 3 months (2 if very good) → live with small leverage ~22:10-24:16

## Definitions
- Second runs: price re-takes the low/high where a run began before continuing

## Open questions
- No-trade/flat before scheduled 10:00 Fed speaker: switch `flat_before_fed_speech` [check 2023 news rules]
- JH week filter: switch `skip_jackson_hole` (day 1 / days 1-2 / whole week) [new]
- Friday trading after a profitable week: switch `skip_friday_if_week_profitable` [new; conflict check vs Model 1 Friday ban]
- 07:00 range low projection as entry zone: switch [check vs te60 07:00-07:30 grading]
