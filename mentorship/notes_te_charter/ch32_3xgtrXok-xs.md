# ch32 ICT Charter Price Action Model 12 \ Scalping, 20 Pips Per Trade (3xgtrXok-xs)
Recorded ~2019 / slides + EURUSD, GBPJPY, GBPUSD 5m / 25 min. Captions only.
Source tier: Charter. 2023 wins on conflicts. FX units.

## Summary
Model 12 (scalping, 20 pips/trade, 5m, scalable to any TF): stage = daily range expansion (direction of today's candle); setup = order block + FVG; pattern = internal range to 20-pip runs. Sequence: an order block (down-close candle at the start of an impulse, FVG not required) -> price retests the OB (upper half to mean threshold) -> an expansion swing away -> the FVG formed INSIDE that expansion swing is the entry. Long at the FVG high (top of the gap) + spread; short at the FVG low. Take 20 pips with ~80% of size, leave ~20% for the next opposing PD array. Answers "which gap do I use?"

## Rules
- Stage: identify the likely direction of the current daily candle ~0:47-1:17
- Setup: OB = down-close (up-close) candle at the start of an initial expansion; a FVG directly linked to the OB is not required for this model ~1:17-3:25
- Wait for the OB to be retested; use the upper portion of a bullish OB (high to mean threshold) as most sensitive ~3:25-4:21, ~10:20-11:18
- Do NOT buy at the OB retest itself; wait for the expansion swing that proves the OB ~11:18-11:53
- Entry FVG = the FVG inside the expansion swing after the retest; long limit at the FVG high (prior candle high / next candle low boundary) + spread; short at the FVG low ~11:53-12:31, ~28:26-29:21
- Filter (bearish): the entry FVG must be at/above 50% of the expansion swing (premium); ignore gaps too far extended ~21:44-23:23
- Stop beyond the far side of the gap (accept the gap closing or going to CE) ~29:51-32:21
- Small ranges bring large ranges; the OB displacement + retest + expansion is the sequence ~15:15-16:05, ~32:21-33:25
- TP 20 pips; take ~80% off (e.g. 8 of 10 minis), leave ~20% for the next PD array or other models' targets ~19:38-20:44, ~40:56-41:23
- Higher probability: inside a kill zone and with daily institutional order flow ~36:21-37:14
- Can be used to add to an existing larger position ~44:23-44:55
- Do not trade every FVG; the gap must follow the OB-retest-expansion order ~24:22-25:25

## Trade examples
- EURUSD 5m (two examples): OB without FVG, retest, expansion FVG, 1-2 pip drawdown, 20 pips ~7:52-10:14
- GBPJPY 5m: bearish OB (two up-close candles), expansion lower, premium FVG short, 20 pips; second same-day example ~10:44-13:55
- GBPUSD 5m: bearish OB retest then expansion FVG short ~16:21-17:25

## Definitions
- Expansion swing: the move away from the OB after it is retested
- Mean threshold: midpoint of the OB

## Open questions
- Model 12 sequence (OB retest -> expansion FVG) may duplicate 2023 FVG entry logic: [conflict check] switch `m12_require_ob_retest`
- 80/20 scale at 20 pips: index mapping is our interpretation
