# cc06_003 ICT Mentorship Core Content - Month 06 - Classic Swing Trading Approach (g--tikwaupk)
Recorded for the Feb 2017 mentorship content (lesson 3, stated ~0:25) / market: generic, Swiss franc named as the example (forex) / timeframes: monthly, weekly, daily, 4-hour / 40m. Slide lecture only: text slides plus schematic swing diagrams, no real price charts, no prices or dates.

## Summary
Defines the PD array matrix (premium arrays above price, discount arrays below) and the classic swing model: top-down monthly -> weekly -> daily -> 4H alignment ("buy/sell programs"), wait for impulse swing + retracement, buy every 4H discount array inside the impulse range, scale out at daily/weekly/monthly premium arrays, need 3:1+ to the nearest opposing array, and a failure protocol (next array at 50% size). Bearish side is the exact mirror. Specific setups are promised for lesson 4.

## Rules
- Direction principle: the side of the PD array matrix that price most recently traded to/reacted from implies the opposite side is the next draw. Discount arrays supported price -> premium arrays above are sought; premium resisted -> discount sought ~0:50-1:16 [chart] [new]
- Find the side that most recently showed displacement (speed, large ranges away from a level); trade in that direction ~4:39-5:06 [new]
- Sell program on a timeframe = price moving away from a premium array (bearish OB, old high, historical low acting as resistance) and seeking discount arrays; buy program = mirror ~5:25-7:20 [chart] [new]
- Highest probability: monthly, weekly, daily and 4H all in the same program; 4H is the execution timeframe for swings ~6:37-7:48, ~9:07-9:31 [chart] [new]
- Bullish HTF bias needs "a few" macro factors, not all: seasonal tendency, interest rates (differential; he ranks rates highest), COT commercials net long / reducing shorts, intermarket (SMT divergence, structure) ~10:21-11:51 [chart] [new; forex/macro, hard to code]
- Do not chase the impulse. Sequence: condition (HTF bias) -> impulse swing with displacement from a point of origin -> wait for the retracement -> enter during the retracement -> profit on the expansion swing ~12:43-14:31 [chart] [new]
- Discount PD array matrix for the setup = the whole range from the point of origin (impulse low) to the intermediate-term high before the retracement; map all discount arrays inside it (mitigation block, bullish breaker, liquidity void, FVG, bullish OB, rejection block, old low / historical high) ~17:02-18:27 [chart] [new]
- 12-step procedure (bullish) ~18:41-22:54 [chart]:
  1. 9-18 month market profile on monthly and weekly: trending or range? Prefer a market leaving a consolidation aggressively (displacement) ~18:58-19:19 [new]
  2-4. Monthly PD arrays: identify the active discount arrays; if one is supporting price, map the monthly premium arrays (targets); then go to weekly, transposing the monthly levels.
  5-7. Same on weekly; transpose to daily. 8-9. Same on daily; transpose to 4H. 10. Map the 4H discount arrays (only the ones that exist).
  11. Buy all 4H discount arrays; scale out at daily, weekly and monthly premium arrays ~21:43-22:25 [new]
  12. Only take setups offering at least 3x the distance from entry to the closest premium array on any timeframe (he prefers ~5:1) ~22:25-22:43, ~37:12-37:25 [chart] [new]
- Entries named: bullish OB, breaker, mitigation block, turtle soup long below a violated old low, and rejection block (price dips just below the candle bodies of long-wicked candles, need not reach the wicks) ~21:59-22:14 [new]
- Scaling: aim for the monthly level but take partials at 4H, daily and weekly premium arrays; hold only a small remainder as price nears monthly/weekly targets ~22:54-23:06, ~36:47-37:00 [new]
- Setup failure protocol ~23:24-24:07 [chart] [new]:
  1. If the 4H buy fails (loss), buy the next lower 4H discount array.
  2. If no 4H discount arrays remain, use daily, then weekly, then monthly discount arrays below.
  3. Re-entry size = 50% of the failed trade's size (halves again after each failure, per "previous failed trade").
  4. Do not try to win back the whole loss in one trade; partial recovery (e.g. 60%) is fine.
- Trade management confirmation: as price moves your way, 4H premium arrays (bearish breakers, mitigation blocks, up-close candles/OBs) should give way and old highs should break without deep retracements, while new discount arrays hold ~24:07-24:59 [chart] [new]
- Fractal: each monthly/weekly impulse/expansion swing contains daily impulse-retracement-expansion, and each daily swing contains 4H ones. If a buy fails, drop to the next higher-timeframe discount array ~25:17-28:33 [chart] [new]
- Bearish = mirror: premium matrix from the short-term low up to the point of origin; sell every 4H premium array (bearish OB, breaker, mitigation, FVG/void, old high turtle soup, rejection block just above bodies); scale out at daily/weekly/monthly discount arrays; failure -> next higher premium array at 50% size ~29:08-39:35 [chart]

## Trade examples
None. Only schematic diagrams.

## Definitions
- PD array matrix: premium (top to bottom on slide): old high or low, rejection block, bearish OB, FVG, liquidity void, bearish breaker, bearish mitigation block. Discount: bullish mitigation block, bullish breaker, liquidity void, FVG, bullish OB, rejection block, old low or high ~3:49-4:22 [chart] [new]
- Rejection block: candles with long wicks at a short-term high/low; liquidity rests just beyond the bodies; enter as price trades just past the bodies, often not through the wicks ~3:04-3:34, ~36:06-36:18 [new; fills the gap noted at rules line 69]
- Liquidity void: a large range of one-directional delivery ~2:08-2:43 (rules file defines it as no overlap between candles; consistent).
- Point of origin / impulse swing / retracement / expansion swing ~16:47-17:13 [chart] [new]
- Sell/buy program ~5:25 [new]

## Seen only on the charts
- The slide order of arrays is the same in both halves, mirrored around "Market Price" (old high/low outermost, mitigation block nearest) ~5:00 [chart]. He does not say this order is a priority ranking.
- The discount matrix box spans from the retracement high down to the point-of-origin line, i.e. the full impulse range, not only its lower half ~18:20 [chart].
- Progression slide: a bullish trend of impulse/retracement/expansion legs with a long retracement between two cycles; mini copies of the pattern drawn inside each leg (fractal) ~28:40 [chart].

## Open questions
- "Active" array is not defined precisely (untraded? within the current range?).
- No stop placement given for the swing entries; the failure protocol implies a stop beyond each array, but where (array low? MT 50%?) is not stated.
- "Buy all 4H discount arrays": one position per array (scaling in) or only the first touched? Combined with the 50% failure rule it reads as sequential.
- How to quantify "displacement" and "9-18 month profile trending vs range".
- Does "closest premium array on all time frames" mean the nearest of any timeframe (strictest) for the 3:1 filter? Literal reading: yes.
- Discount vs equilibrium: unlike intraday rules (discount = below 50%), here the whole impulse range is the "discount matrix"; unclear whether entries above 50% are allowed.
- Macro filters (seasonals, rates, COT) are forex-oriented; for index futures a coder needs substitutes or must skip them.
