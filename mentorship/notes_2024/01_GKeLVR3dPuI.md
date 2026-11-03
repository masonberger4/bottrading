# 2024 Mentorship Lecture 01 (GKeLVR3dPuI): Mindset + "smooth vs jagged" bias framework
Live 2024-08-05 (Mon), ~08:00-10:15 ET, NQ (Sep 2024), 15m / 5m / 1m. ~2h15m. Captions only (frames on laptop).
Source tier: 2024 Mentorship (below 2023 Mentorship on conflicts). Taught "to Caleb" = beginner framing unless noted.

## Summary
Mostly mindset. One core technical idea: daily/session bias for a NEW trader comes only from time windows (07:00-07:30, 08:00-08:30, 09:00-09:30 pre-market ranges) and "smooth" relative equal highs/lows on the 15m/5m/1m. Smooth (equal) side gets raided; jagged side has already been "attacked" and is moved away from. If both sides are smooth, wait for one to be disrupted and then work toward the other. Live example: relative equal highs at 17,820.75 forecast before 09:30; 09:30 Judas drop into a bullish breaker / FVG near equilibrium, then the run to the highs.

## Rules
- Price is delivered on the basis of TIME first; a run happens at a specific time or within a 20-minute window ("macro") ~14:00
- Always New York local time ~29:30, ~1:20:00
- Two things price reaches for: old highs/lows and inefficiencies (FVG); "it's going to go for both" ~53:00-58:00
- Beginner chart set: 15m, 5m, 1m only. No daily/hourly, nothing below 1m needed (15s optional) ~56:00
- 15m is static; check it once in the morning ~1:43:00
- Sit down before 08:30 (preferably 08:00) and mark highs/lows on 15m/5m/1m ~56:00
- Draw on liquidity is "an initial reasonable assumption", not the terminus ~1:06:00
- SMOOTH vs JAGGED: market goes to areas of smoothness (relative equal highs/lows, "still water") to disrupt resting orders; jagged price delivery = already raided ("shark attack"), don't trade INTO it; move away from it ~1:08:00-1:10:00, ~2:02:00
  - Holds on every timeframe (sub-1m to quarterly) ~1:10:00
- High-probability relative equal highs: two swing highs close together where the LEFT one is slightly HIGHER than the right ("priming") → high probability it is swept ~1:14:00-1:16:00
  - Mirror: relative equal lows where the left low is slightly LOWER than the right (right one = higher low) ~1:17:30
  - Filter on how close they must be: ICT won't say ("not very much in terms of difference") ~1:18:40
  - Doesn't have to be swept in THAT session ~1:21:30
- Bullish breaker: after the relative equal lows are run, the up-close candles before the drop; whole up-close run = breaker, most sensitive = LAST up-close candle; bodies matter ("the damage is done by the bodies") ~1:22:00-1:24:00
- Include the volume imbalance with an FVG when present; bodies stop at it ~1:24:30
- Balanced price delivery (every candle overlapping) = no liquidity of interest ~1:26:00
- PRE-MARKET RANGE (ICT's definition): first 30 minutes of 07:00, 08:00 or 09:00 (07:00-07:30, 08:00-08:30, 09:00-09:30) ~1:51:00
- OPENING RANGE: the 30 minutes AFTER the pre-market range: 07:30-08:00, 09:30-10:00. "There is no 15-minute opening range" ~1:52:00
- BIAS RULE: look at highs/lows formed BEFORE the pre-market range start (to the left of 07:00/08:00/09:00); whichever side has smooth relative equal highs/lows is the draw → that's the bias ~1:53:00
  - If BOTH sides have them: wait for the first one to be disrupted, then work toward the other ~1:53:30
  - Look for them to form AT/after 07:00, not before 07:00 (London overlap not demanded) ~2:04:00-2:06:00
  - Each window that passes without the raid (07:00 → 08:00 → 09:00) increases the likelihood ("builds trust") ~2:04:00
  - No HTF draw used; only 15m/5m/1m + time ~2:06:00
- AM session starts 07:00 NY for any market ~1:42:00
- FVG as discount array: wick into "mid gap" (CE) of a bullish FVG below price ~1:30:00
- Equilibrium measurement: from slightly above the relative equal highs (target) down to the relative equal LOWS (not the lowest manipulation low); FVG near equilibrium = entry zone, can be slightly above EQ if the target highs aren't taken yet ~2:00:00-2:01:30
- 09:30 opening range drop = Judas swing opposite the real move ~2:02:30
- Manual intervention (FOMC, CPI, NFP) = untradeable once it starts; standard delivery = up a little/back a little ~54:00

## Risk and process ([beginner] unless noted)
- [beginner] Trade ONE micro contract; one trade a day; no pyramiding until ~a year after trading one contract ~1:02:00-1:04:00
- [beginner] First live trade: coin flip, lowest size, 15-point stop, to break the ice ~50:30
- ICT himself: "I would use the maximum leverage" when the setup is obvious (experienced) ~46:00
- Journal: screenshot each run, count candles/minutes it took, record feelings; study 07:00-11:00 on 15m/5m/1m daily ~1:01:00, ~2:00:00
- No market replay ~1:11:00
- Trade only obvious days; missing moves is fine ~2:09:00

## Trade examples
- 2024-08-05 NQ: relative equal highs 17,820.75 (pre-09:30) forecast; 09:30 drop into bullish breaker + FVG CE near EQ; run to and through the highs. No trade disclosed (teaching only).

## Definitions
- Priming: left swing high slightly above right one (or left low slightly below right one) → relative equal pool that the algorithm returns to
- Smooth / jagged price delivery
- Pre-market range vs opening range (above)
- SIBI = FVG formed by a down-close candle; BISI = by an up-close candle ~1:02:00

## Open questions / conflict checks
- [conflict check] Pre-market range definition (07:00-07:30 / 08:00-08:30 / 09:00-09:30) vs TE te58/te60 (07:00-08:29, 07:00-07:30, 07:00-08:00) and rulebook
- [conflict check] "Opening range" 07:30-08:00 for the 07:00 window (rulebook only has 09:30-10:00)
- Switch: `smooth_pool_bias` (bias = side with smooth relative equal pool before the window); `primed_equal_pool` (left higher than right)
- Switch: `bias_window_start` 07:00 / 08:00 / 09:00
- "Relative equal" tolerance: ICT withholds → our interpretation needed
