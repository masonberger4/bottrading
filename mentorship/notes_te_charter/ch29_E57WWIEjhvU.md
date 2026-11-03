# ch29 ICT Charter Price Action Model 10 \ Swing Trade Plan + Algorithmic Theory (E57WWIEjhvU)
Trade plan ~2020 + lecture ~2022 / slides + ES 1m / 20 min. Captions only.
Source tier: Charter. 2023 wins on conflicts. FX units; ES example.

## Summary
Model 10 trade plan: IPDA 20/40/60-day ranges (no Sundays) for the liquidity run used as entry AND exit. 50-75 pip ranges; short premium buy-side liquidity pools / buy discount sell-side pools at a calendar volatility injection; 15m buy-side (sell-side) liquidity pool raid from a retracement during London/NY open kill zones. Limit order at convergence -/+ 5 pips. Two orders: order 1 TP 50 pips, order 2 TP up to 75 pips. Lecture: dealing ranges are fractal rectangles; external range liquidity = stops outside the current dealing range; ES 1m long below a dealing-range low, exit above the opposing high. Price runs to the larger pool by algorithmic delivery, not "buying pressure".

## Rules
- Preparation: medium/high impact events; weekly profile ~0:51
- IPDA: 20, 40 and 60 trading day ranges (no Sundays) for both entry and exit liquidity runs ~0:51-1:51
- Opportunity: 50-75 pip ranges to buy-side (bullish order flow) or sell-side (bearish); bulk at 50, remainder at 75 ~1:51-3:27
- Trade planning: short premium buy-side liquidity pools / buy discount sell-side liquidity pools, manipulation opposite bias at a volatility injection ~3:27-3:56
- Execution: 15m buy-side liquidity pool raid from a retracement higher (bearish) / sell-side raid from a retracement lower (bullish) during London or NY open kill zones ~3:56-4:33
- Orders: sell limit at convergence - 5 pips / buy limit at convergence + 5 pips ~4:33-5:06
- Two orders: order 1 TP 50 pips; order 2 limit for 50-75 pips ~5:06-5:36
- Stop: 20 pips; at 50% of objective reduce stop 25%; at 75% break-even ~5:36-6:41
- Sizing and loss / 5-win risk rules as other plans ~6:41-9:05
- Short: wait for a short-term high to be pierced (sell buy stops), ride to a short-term low in discount, cover when price drives below it (buy sell stops) ~10:11-11:21
- External vs internal depends on which dealing range you reference; use the most recent dealing range (rectangle) ~11:21-14:17, ~24:00-15:53
- Dealing ranges are fractal and nested; for a long below a dealing-range low, target the opposing buy-side external liquidity above its high ~14:53-16:24
- The algorithm spools to the larger liquidity pool; not buying pressure ~17:27-18:50
- Still requires bias, time of day and day of week ~18:50-19:25

## Trade examples
- ES 1m (2022): bullish week; price traded into a discount FVG and below the dealing-range low (sell-side external), ICT long, exited at the buy-side above the larger range high ~12:23-17:27

## Definitions
- Dealing range: the current trading range (high to low) price stays inside; fractal

## Open questions
- Two-order 50 / 75 pips: index mapping is our interpretation; switch
- Which dealing range defines "external": switch `dealing_range_def = {last_swing_pair, ipda_20d}` [interpretation]
