# ch27 ICT Charter Price Action Model 9 \ OSOK Trade Plan + Algorithmic Theory (YIxurbDNrWM)
Trade plan Dec 2020 + lecture ~2022 / slides + EURUSD, GBPUSD 5m / 36 min. Captions only.
Source tier: Charter. 2023 wins on conflicts. FX units.

## Summary
OSOK trade plan: IPDA data range = last 20 WEEKS (not days); target 50 pips (preferably), up to 75, that run to buy-side (bullish) or sell-side (bearish). Buy discount sell-side pools / short premium buy-side pools at a calendar volatility injection; 15m OTE in London/NY kill zones or stop raid; MARKET order at the PD array/OTE convergence; TP 50 pips, close 80% and let the rest try for 75 with partials at short-term highs/lows. Lecture: ICT gives up Monday (Tuesday makes the weekly low/high 70% of the time); runs OSOK as two separate 1% orders: order A = Model 8 logic (partials at the low, 10 pips below, limit remainder, BE when low taken); order B = OSOK (first partial at 1 SD projection of the entry swing, then 1.5 SD, then the relative equal lows; pyramid only while price is above equilibrium).

## Rules
- Preparation: medium/high impact events; weekly profile ~1:41-2:08
- IPDA range for OSOK: highest high / lowest low of last 20 weeks ~2:08-3:12
- Opportunity: 50-75 pip range framing a run to buy-side (bullish) or sell-side (bearish); ICT prefers easy 50 pips ~3:42-4:43
- Trade planning: buy discount sell-side liquidity pools / short premium buy-side liquidity pools at a calendar volatility injection, with manipulation opposite your bias ~4:43-5:17
- Execution: 15m OTE inside a retracement in London open and/or NY open kill zones, or a stop raid ~5:17-5:49
- Entry: market order at PD array convergence / OTE inside a kill zone ~5:49-6:18
- TP 50 pips (single limit); at 50 close 80%, try 75 with partials at logical short-term lows/highs ~6:18-7:20
- Stop: at 50% of objective reduce 25%; at 75% break-even; 20-pip stop in the sizing example; no standard lots ~7:20-9:34
- Loss/win-streak risk rules as other plans ~9:34-10:39
- Skip Monday (intel); Tuesday makes the weekly low/high ~70% of the time; trade Tue and/or Wed; if no textbook setup, small scalps ~16:00-17:59
- Two-order structure (each 1%, total 2%): order A = Model 8 (stop 1-2 pipettes above the FVG candle high; partial at the low, then 10 pips below, remainder on limit 5-20 pips below; BE once the low is taken) ~20:45-21:51, ~23:37-24:11
- Order B (OSOK): no partial until 1 SD projection of the entry swing (low to OTE/FVG high); then 1.5 SD; then the relative equal lows (hourly) ~21:51-23:37, ~26:38-27:35
- Limit at relative equal lows: midpoint between the two lows (no spread fluff); if the lows are very close, at or 1 pipette below ~25:43-27:35
- Pyramiding (order B only): add while price is still above equilibrium of the dealing range; add half the size on an immediate rebalance, stop above the gap; no adds below equilibrium ~27:35-31:39
- Partial sizing suggestion: half off at first, 25% at second, last 25% to the limit; with high conviction no partials and add instead ~30:11-31:10

## Trade examples
- EURUSD Tue 2020-12-01: weekly FVG + 20-week old high; Fed chair 10:00 NY; NY open 15m OTE on bodies; 50 pips via limit, scaled out above premium arrays ~10:39-14:57
- GBPUSD (Model 8 example) with two-order structure: ~14.5% on order B no partials, ~20% total; $5k account ~18:34-29:41

## Definitions
- 1 SD projection: measured move of the entry swing range projected from the extreme

## Open questions
- 20-week IPDA range (vs 20/40/60 days): switch `ipda_lookback_unit = {days, weeks}`
- Two-order split (scalp order + runner order): switch `osok_two_order` [new]
- Pyramid-above-equilibrium rule: switch
- Tuesday 70% weekly low/high claim: testable statistic; check on our data
- 50/75 pips: index mapping is our interpretation
