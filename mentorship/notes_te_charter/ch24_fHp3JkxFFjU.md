# ch24 ICT Charter Price Action Model 8 \ 6% Per Month, 25 Pips Per Week (fHp3JkxFFjU)
Recorded ~2018 / slides + USDCHF weekly/15m / 46 min. Captions only.
Source tier: Charter. 2023 wins on conflicts. FX units.

## Summary
Model 8: aim for 6% per month (double equity per year) by capturing 25 pips per week inside a weekly range expansion. Stage = weekly range expansion (bias from the weekly chart, seasonals help); setup = day of week: anchor point = Monday, Tuesday or Wednesday high (bearish) or low (bullish); pattern = inefficiencies (FVG, liquidity voids) and runs on liquidity. Enter in the FVG/OTE above equilibrium of the anchor range; the goal is to LOCK IN 25 pips (move the stop to +25) rather than bank partials, then scale out 10/20/30 pips beyond the weekly extreme. Don't trade range-bound pairs.

## Rules
- Do not "kitchen sink": swing traders don't need intraday SDs, CBDR, flout, Asian range ~2:22-3:20
- Stage: identify whether the next weekly candle expands up or down using institutional order flow on the weekly (month 12 top-down) ~10:21-11:14, ~18:55-19:23
- Mental model: weekly range 150-200 pips; 25 pips is modest; focus on where price reaches in the next 50-75 pips ~11:14-12:13, ~15:01-16:29
- Skip pairs expected to be range-bound ~15:33-15:54
- Setup: let the Monday/Tuesday/Wednesday high (bearish) or low (bullish) form; do not chase; no need to catch the weekly high/low ~16:29-17:56, ~19:23-20:46
- Wednesday higher high into Monday's equal highs -> probable high of the week, trade Thursday ~19:52-20:18, ~21:42-22:14
- Pattern: FVG / liquidity void off the anchor point, targeting liquidity below old lows ~20:46-21:42
- Anchor range: anchor high (Wed) to the low before the run-up = PD matrix; sell in the premium FVG / OTE above equilibrium ~33:47-35:16
- Do not nickel-and-dime intermediate PD arrays; target the run below the week's low ~35:16-35:41
- Management: once +25 pips, move stop to lock in 25 pips; no partials until price expands the weekly range; then partials at 10, 20, 30 pips below the old low; close all or take more when the weekly low is taken on Friday ~14:07-14:32, ~36:12-38:44
- Model 8 can be used as an entry for swing / position trades (lock in 25 pips) ~38:44-39:11
- Breaker re-entry: lowest down-close body between the highs (close 0.9935); stop above the void / bearish OB; risk < 20 pips ~39:11-41:33
- FVG midpoint = consequent encroachment (sufficient fill); OB midpoint = mean threshold ~28:57-29:54
- Enter at the low end of the FVG; stop above the up-close rejection block ~42:41-43:53
- Weekly downside expansion in the direction of weekly bias can exceed the usual 10/20/30 pip grades ~23:23-23:53
- Weekly Judas swing: rally above the weekly open = more institutional selling ~31:40-32:15, ~35:41-35:41
- Stick with the HTF narrative after a stop-out ~30:46-31:11

## Trade examples
- USDCHF week of 2018-12-03: Monday equal highs, Wednesday raid of them then MSS + FVG; Thursday Dec 6 London rally into FVG at 0.9985/0.9990 near the 0.9980 institutional level; 30+ pip grade below the old low; Friday breaker short at 0.9935 with < 12 pip stop for ~55 pips ~22:14-24:24, ~31:40-44:26
- USDCHF weekly: buy stops above equal highs raided, closed back below = rebalancing down to the weekly FVG CE ~25:20-30:23

## Definitions
- Anchor point: Monday/Tuesday/Wednesday high (bearish week) or low (bullish week) used to frame the PD matrix
- Consequent encroachment: midpoint of a FVG; mean threshold: midpoint of an OB
- Lock in 25 pips: stop moved to entry +/- 25 pips

## Open questions
- 25 pips/week target: index mapping is our interpretation (e.g. NQ/ES points); switch `weekly_lockin_points`
- "Stop to +25 then no partials until the weekly extreme breaks": management switch vs 2023 partials
- Wednesday-high-of-week rule for Thursday entries: switch `anchor_day_set = {Mon,Tue,Wed}`
