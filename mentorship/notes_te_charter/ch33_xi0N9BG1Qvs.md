# ch33 ICT Charter Price Action Model 12 \ 20 Pip Scalp Trade Plan + Algorithmic Theory (xi0N9BG1Qvs)
Trade plan ~2020 + lecture 2022-06 / slides + USDCHF daily/5m / 48 min. Captions only.
Source tier: Charter. 2023 wins on conflicts. FX units; ICT gives ES/NQ equivalents.

## Summary
Model 12 trade plan: 20-day IPDA range only (no Sundays); target external range liquidity. Look for 20-pip ranges on the 15m; short 15m premium FVG + bearish OB / buy 15m discount FVG + bullish OB. The OB may form outside a kill zone (e.g. 05:00-07:00, CBDR) but the RETURN to the OB/FVG must be inside the London or NY kill zone, or no trade. Execute on the 5m: limit at the institutional order flow entry drill -/+ 5 pips; TP 20 pips via a fixed limit (no fiddling); stop 20 pips; at +10 cut stop by 10, at +15 break-even. Lecture: daily-range-based bread-and-butter model (previous day high/low as draw); for ES/NQ use 20 ticks (5 handles) or 10 handles; take 80% one pip ahead of the old high, then 10/20/30 beyond.

## Rules
- Preparation: medium/high events; only the weekly expansion direction is needed, not the close ~2:18-3:18
- IPDA: last 20 trading days only (no Sundays) ~3:18-3:49
- Target external range liquidity; anticipate an OB with a FVG supporting weekly bias on a news day ~3:49-4:50
- Opportunity: 20-pip ranges on the 15m to buy-side (bullish) / sell-side (bearish), using kill zones ~4:50-5:58
- Trade planning: short 15m premium FVG + bearish OB / buy 15m discount FVG + bullish OB with manipulation opposite your bias at a volatility injection ~5:58-6:30
- OB may form outside a kill zone (05:00-07:00 NY lull, CBDR), but the return into OB+FVG must be during London or NY kill zone, otherwise not viable ~6:30-8:07
- Stage = 15m retracement; setup forms on the 5m: 5m premium FVG + bearish OB (or discount + bullish) during London/NY open ~8:07-8:42
- Entry: limit at institutional order flow entry drill - 5 pips (short) / + 5 pips (long), from the 5m ~8:42-9:22
- TP 20 pips with a counter limit placed at entry; don't touch it ~9:22-10:23
- Stop 20 pips; at +10 reduce stop by 10; at +15 move to break-even (ICT: setups often give 12-15 then reverse) ~10:23-13:02
- ICT's personal minimum stop 15 pips; teaching threshold 20; never 2-5 pip stops ~0:31-1:31
- Sizing, loss halving, 5-win halving as other plans ~13:02-16:11
- Draw: previous day's high or low; 20 pips before reaching it qualifies ~16:43-17:45
- Daily-range model; London overnight direction often continues into NY ~30:13-31:09
- Index version: 20 ticks = 5 handles ES/NQ, or 10 handles; once per session (AM and PM sessions may differ in direction) ~42:40-44:39, ~50:21-51:21
- Avoid NFP weeks after Wednesday NY session (ICT's bias most often wrong) ~35:55-36:24
- Exit: 80% off one pip ahead of the old high; roll stop to break-even plus a little; then partials 10/20/30 pips beyond; or trail under closed candles ~38:17-39:13
- Don't over-trade (frequent setups attract gamblers) ~19:48-20:17

## Trade examples
- USDCHF (2022): daily FVG above, two up-close candles -> bias to run the previous day's high; 5m sweep of the prior high, down into OB, MSS, FVG retrace with 1-pipette drill below the low; buy ~0.9605, +20 at 0.9625 before the relative equal highs ~31:38-34:01
- Ted (ICT's son), 2022-05-31: one NQ/ES mini, model 12 blended with the 2022 YouTube model ~44:39-49:39

## Definitions
- Institutional order flow entry drill: the short dip/raid one pipette beyond a low/high inside the FVG retracement (here 1 pipette below the low)

## Open questions
- "Return to OB+FVG must be in a kill zone" filter: switch `m12_return_in_killzone` [check vs 2023 kill zones]
- 5 / 10 handles per session for NQ/ES (ICT's own mapping); ticks mapping for NQ (20 ticks = 5 points) ok
- Stop steps at +10 (-10) and +15 (BE): switch
- NFP-week blackout after Wednesday NY: switch `skip_nfp_week_after_wed` [new]
