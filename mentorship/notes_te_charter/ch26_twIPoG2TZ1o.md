# ch26 ICT Charter Price Action Model 9 \ One Shot One Kill (twIPoG2TZ1o)
Recorded Dec 2018 / slides + USDCHF weekly->1h / 65 min. Captions only.
Source tier: Charter. 2023 wins on conflicts. FX units.

## Summary
Model 9 (OSOK): stalk 50-75 pips per week by catching the weekly high (bearish) or low (bullish) on Monday-Wednesday and covering in the lower (upper) third of the expected weekly range. Stage = weekly range expansion from weekly institutional order flow; setup = day of week (Mon/Tue/Wed); pattern = inefficiencies to liquidity runs. Key "coder key": internal range liquidity entries (OB, FVG, void) run to external range liquidity (old highs/lows); external range entries (turtle soup) run to internal range liquidity. Stop management: only move the OSOK stop when a lower-time-frame model (scalp/day trade) would have hit its objective; leave at break-even until Friday, then trail aggressively. If OSOK is missed or stopped, drop to Model 8 or scalping to mitigate.

## Rules
- Weekly bias = direction the weekly chart is reaching for (month 12 top-down); trade daily in that direction; monthly helps ~1:34-3:44
- Stick with the narrative until trades are clearly failing; then cut losses and check the opposite direction ~5:37-6:27
- Setup: Monday, Tuesday or Wednesday forms the weekly high/low; this model DOES hunt the weekly extreme (unlike Model 8) ~10:10-11:06
- Expected range: next 50-100 pips; sell near the weekly high, cover in the lower 1/3 of the expected weekly range; objective 50-75 pips ~11:39-12:06, ~20:17-20:41
- Internal range liquidity (FVG, void, OB) entry -> target external range liquidity (beyond the dealing range); external range entry (turtle soup at double tops/bottoms) -> target internal range liquidity (FVG, equilibrium, OB) ~9:39-13:30
- Buy-side imbalance = sell-side inefficiency (fast rally leaves gaps to rebalance); sell-side imbalance = buy-side inefficiency ~14:00-17:00
- Contingency: if OSOK entry missed or stopped, use Model 8 (25 pips) or the scalping/day-trading model to mitigate; don't force ~23:21-28:43
- Stop management: do not jam the stop to break-even early; move the OSOK stop only when a lower-TF model (scalp/day trade) reaches its objective (e.g. sell stops below equal lows, 10/20/30 pip sweep); then stop just above the highs; break-even only after the liquidity run; no micromanaging until Friday, then trail aggressively aiming for Thursday's low ~29:10-35:33, ~38:45-39:19
- Take partials (fund the trade) when a day-trader objective is reached ~36:33-37:25
- Do top-down and bottom-up analysis; resolve disagreements ~33:50-34:11
- PD array matrix: go in order of the PD arrays that exist ~43:34-44:47
- Bearish breaker rule: after equal highs taken and MSS, the breaker is the down-close candle that went down the most (sell-side origin); candles inside its range are insignificant ~46:43-48:25
- If price respects the breaker repeatedly (mitigation) it need not run nearby equal highs ~48:51-49:17
- Real support/resistance = institutional order flow levels (breakers, after stops taken), not lines ~50:27-50:51
- Daily FVG overlapping weekly FVG CE refines the target; calibrate 0.9783 -> 0.9785 / 0.9780 ~51:45-53:23
- Entry: bottom of the gap with stop beyond the far side; if live and certain, limit at CE ~56:40-57:29
- Volume imbalance (body separation even with wicks overlapping) gets rebalanced like an OB ~57:57-58:22
- Grades 10/20/30 pips below the close of the low (0.9841 -> 0.9831/0.9821/0.9811) ~59:27-59:55
- Expect losing weeks (Dec 7-13: no successful shorts while price filled an old order-flow area) ~54:22-55:12

## Trade examples
- USDCHF Dec 2018: weekly equal highs raided (external range), back inside range; daily MSS + bearish breaker, repeated mitigation; daily FVG over weekly CE; 4h CE hammered twice; 1h volume imbalances -> external lows; drop ~50 pips to 0.9791 ~41:06-63:38
- USDCHF Wed Dec 5 London: double highs raid, OTE + FVG at bottom of bearish OB; stop management example ~30:32-32:48

## Definitions
- Internal range liquidity: FVG, liquidity void, OB inside the dealing range
- External range liquidity: stops above old highs / below old lows outside the dealing range
- Volume imbalance: gap between candle bodies (wicks may overlap)

## Open questions
- "Move stop only after a lower-TF model would have hit its objective" -> switch `osok_stop_trigger = {ltf_objective, fixed_R}`
- Internal->external / external->internal targeting rule: switch `target_by_entry_liquidity_type` [new]
- Breaker = down-close candle with the largest down move: [conflict check vs 2023 breaker] switch
- 50-75 pips: index mapping is our interpretation
