# te09 NQ Employment Number Live Execution \ 2023-12-07 (UOpmn7JqBEY)
Recorded 2023-12-07 (Thursday of NFP week) / live NQ 1m, TradingView / 47 min. Captions only.
Source tier: Trade Executions (post-2023). 2023 Mentorship wins on conflicts. NQ points.

## Summary
Live long on NQ after the 8:30 employment data: sell-side raid below a low at 8:30, then breaker; ICT says the up-close candle inside the breaker is the most sensitive and price returned to its body. Entry from an OB / FVG with an inversion FVG above expected to flip to support. Managed with partials at each new short-term high ("running down equity"), stop rolled to just below half (mean threshold) of the down-close OB candle on a blow-off, targets from body-anchored fib standard deviations (-1, -1.5, -2, -2.5) of the Judas swing. 10 contracts.

## Rules
- ICT doesn't like trading NFP week after Wednesday; a profitable Monday usually caps his week ~1:57-2:23
- Thursday and Friday of NFP week are "highly problematic for precision" ~9:12-9:51
- Inversion FVG (iFVG): a FVG that failed and is expected to act in the opposite direction; price should treat it as support after trading through ~2:23-4:39
- Volume imbalance under it is permissible as the retracement; a breakaway gap left open is better ~4:39-5:23
- Breaker after the sell-side was overshot: most sensitive point is the up-close candle (its body); a wick slightly beyond the close is normal because of the ~1 tick spread ~5:50-7:43, ~30:28-31:19
- While learning, take a partial each time price breaks a new short-term high in a long (running down equity) ~7:43-8:43, ~15:08-16:15, ~18:36-19:56
- Partial profit is always profitable; partials are correct while learning ~19:32-20:54
- Targets: fib standard deviation projections anchored on bodies (highest up-close/open to lowest close/open of the Judas swing): -1, -1.5, -2, -2.5; midpoint between levels also reacts; wick-anchored version for extreme blow-offs ~11:24-13:29, ~38:39-40:22, ~44:58-45:27
- Limit exits placed ~3 ticks before the level to allow for spread ~13:29-14:39
- Stop: below the midpoint of the down-close OB candle; roll it there only on a blow-off candle above the prior high ~17:03-18:36
- Fibs are only for measuring objectives (symmetry, SDs), not entries ~13:29
- Bodies show the volume, wicks are where damage is done ~39:25
- 8:30 news drove a raid of sell-side that flooded sell orders for smart money to buy ~30:01-30:52

## Trade examples
- NQ Dec 7 2023 8:30: Judas swing down below a low, breaker + iFVG, long; partials at highs; -1.5 SD midpoint 15,890.25 hit exactly; ran to -2.5 SD then stopped on the remaining runner ~0:00-45:27

## Definitions
- Inversion fair value gap: FVG that is traded through and then respected from the other side
- Running down equity: taking a partial each time a new short-term high is broken

## Open questions
- NFP-week Thursday/Friday avoidance: switch `skip_nfp_thu_fri` (2023 rulebook check)
- Body-anchored SD targets (-1/-1.5/-2/-2.5) of the Judas swing: switch `target_sd_anchor = {bodies, wicks}`
- Partial at each broken short-term high: management switch
