# ch14 ICT Price Action Model 5 \ Algorithmic Theory (2fgXDt3T3XE)
Recorded Jun-Jul 2018 + later AUDUSD part (uploaded 2024-01-19) / EURUSD, DXY, GBPUSD, AUDUSD / daily, 15m / 49 min. Captions only.
Source tier: Charter. 2023 wins on conflicts. FX units.

## Summary
Hands-on use of Model 5's SD rules: how to set the fib expansion tool, when CBDR / Asian / flout qualify, flout projected from its midpoint (50% grades), two-day SD confluence plus 10/20/30 pip sweeps of fresh 15m swing highs, and the level calibration rule (round toward the sweep when expecting a run, toward the range when exiting). Adds an order-block nuance: a one-pip gap between consecutive OB candles is the level price returns to.

## Rules
- Range check example: Asian range 23 pips (>=20) qualifies; CBDR 14 pips (<15) does not -> use Asian; if both fail -> flout ~2:28-6:00, ~6:47-8:22
- Flout projection: fib from the flout range's EQUILIBRIUM to its high (half-range units) so SDs step in 50% grades of the flout ~8:22-9:07, ~58:40-41:19
- Two-day confluence: e.g. today's SD7 and SD4 of the prior day both at 1.1673; combined with 10/20/30 pip runs above fresh 15m swing highs (1.1642 + 30 = 1.1672) and kill-zone time = the high (1.1673 at London open) ~11:00-12:10
- Always compute 10/20/30 pip runs beyond each new 15m swing high/low as the day makes them ~12:44-13:15
- 15m is the "bellwether" chart for these measurements ~16:35, ~38:49
- Calibration (sweep expected): if price is BELOW a level it should run (equal highs 0.9553), round it UP to the next 5/0 (0.9555), then add 10/20/30 for the sweep (0.9565 = actual high, also SD4). Mirror for lows (0.94997 -> 0.9495). For EXITS round toward the smaller range (take profit early) ~28:00-35:03
- Thursday NY open in a bullish week = likely reversal (market reversal profile) ~35:39-36:19
- 18:00 (his platform; ~bond close area) highs/lows often end the daily range ~47:48
- OB detail: in a series of down-close candles, a 1-pip body gap (close 1.2998 vs next open 1.2997) is the precise level price returns to (low 1.2996); for a rebalance target use the OB candle's OPEN, not its wick (1.3070 open hit exactly) ~42:42-51:51
- When an OB's mean threshold is violated but its low holds, check for such a gap/open inside the OB; it decides open vs wick entries ~52:33-53:18
- SD tolerance 3-5 pips; pick the range (bodies vs wicks, CBDR/Asian/flout) giving the most confluences between the previous day and today ~61:19-46:57
- Model 5 bias via seasonal + daily breaker; London open kill zone sets the high of day, NY continues; objectives: relative equal lows first partial, then 1 pip below previous day's low ~54:54-48:43
- Swing projection -1 of the London leg = exact NY low (0.73921) ~43:39

## Trade examples
- EURUSD Jun 20-21 2018 SD confluence 1.1673 ~2:00-12:10
- DXY Jul 19 2018: 9430-9440 bullish OB low 94.29; equal highs 95.53 -> calibrated 95.55 -> +10 = 95.65 = high at Thursday NY open (SD4) then reversal ~18:00-40:00
- GBPUSD Jul 19-20 2018: low 1.2959 at SD; OB gap 1.2997 (low 1.2996); London high 1.3141 at SD3 and 18:00 ~40:40-51:51
- AUDUSD (seasonal bearish): flout SD1.5 0.73944 vs prior-day SD 0.73907; London FVG at 02:00; NY low 0.73921 = -1 swing projection ~54:54-44:19

## Open questions
- Timestamps in this file restart (two recordings joined); citations after ~38:00 may be off.
