# ch03 ICT Charter Price Action Model 1 \ Trade Plan & Algorithmic Theory (4f1vjQMlV50)
Recorded ~2019 (uploaded 2023-12-29) / FX generic / slides, 5m / 58 min. Captions only.
Source tier: Charter. 2023 wins on conflicts. FX units.

## Summary
The written trade plan and if/then "algorithmic theory" for Model 1 (intraday scalp, 15-20 pips/trade). Five plan stages used in every Charter trade plan: preparation, opportunity discovery, trade planning, execution, management. Adds the generic Charter money-management block (position-size formula, risk cut after losses, risk cut after 5 wins) and a stop-reduction schedule.

## Rules
### Preparation
- Weekly: note all medium and high impact calendar events for your markets (Forex Factory, filtered) ~11:14
- Dealing range = last 20 trading days (no Sundays): note its highest high / lowest low; only if price is in a tight consolidation that reaches beyond 20 days use 40 days (changes the model slightly) ~12:00-13:27
- Bias = the next draw: a liquidity pool (old high/low) or a PD array to rebalance (e.g. FVG). No obvious one-sidedness = no trade, wait ~13:27, ~17:41
- Frame scenarios: bias + a calendar event that injects volatility; not a plan A / plan B up-or-down ~16:13
- Bearish: mark sell-side pools under old daily lows and premium PD arrays inside the 20-day range; bullish mirror ~18:12
### Trade planning
- Want convergence: manipulation opposite to bias (Judas swing / protraction) at a time the calendar says volatility comes ~19:17
- Bearish frame: price traded up into a daily premium PD array, then lower; then a retracement off a near-term discount into a NEW swing high -> short the next NY session OTE. Aggressive version: once price fills an FVG / runs an old high (turtle soup) you may short the next NY session without waiting for the 3rd candle of the swing high ~20:16-22:16
- Bullish mirror: daily discount array, retrace off premium into a new swing low, buy next NY session OTE ~22:16
- Target: the next logical old daily low (high) inside the 20-day range that frames at least 15-20 pips ~22:51
### Execution
- Window 07:00-10:00 NY (kill zone); can extend to 11:00 when a 10:30 release (e.g. crude inventories) is due ~23:49-24:53
- 5m OTE inside a retracement between those times ~24:53
- Short: sell limit at 62% minus 5 pips; all orders same entry price; limit TP1 = +15 pips, TP2 = +20 pips; optional 3rd position as runner ~25:21
- Stop: short = 07:00-10:00 highest high + 5 pips; long = lowest low - 5 pips (algorithmic version: fib anchor high/low +/- 5 pips) ~27:28, ~49:26
- One and done: no re-entry after a stop-out ~27:28
- Split total risk across the orders (1% total / 3 orders = 1/3% each), never risk per order ~26:29
### Management
- Profit at 25% of objective -> stop may be reduced by 25% of initial risk; at 50% -> reduced 50%; at 75% -> stop must be at breakeven including costs ~29:00-29:58
- Algorithmic version: first partial at the OTE anchor high (long), then raise stop to lock 5-10 pips; 2nd partial at previous high or fib extension #2; close balance at previous high or the symmetrical swing extension (= 1x the OTE range, measured move) ~50:13-51:34
### Money management (repeated in every Charter plan)
- Position size = equity x R% / (stop pips x pip value), round down ~30:24
- After a full-R loss: next trade at 50% risk; return to full R once the loss is 50% recovered; another loss halves again ~34:46
- After 5 consecutive wins: halve risk (expect a loss) ~35:19
### Algorithmic checklist (bullish; bearish mirrors)
- Previous highs of last 20 trading days; daily order flow bullish AND daily broke a swing high AND price not in premium (premium = no trade) ~47:51
- Mon/Tue/Wed ideal; Thursday only if price has not yet reached a previous high; Friday = no trade ~48:37, ~49:26
- No trade after 10:00 ~51:34

## Definitions
- Symmetrical swing extension = the OTE leg's range projected once more (measured move) ~51:00
- Anchor high/low = the fib's swing high/low used for the OTE ~50:13

## Open questions
- Stop: 07:00-10:00 extreme vs fib anchor (two statements). Our interpretation: fib anchor (algorithmic version).
- "Fib extension #2" level not given numerically.
- 2023 rules allow later sessions; this model hard-stops at 10:00 (switch).
