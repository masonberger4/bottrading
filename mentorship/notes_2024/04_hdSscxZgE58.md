# 2024 Mentorship Lecture 04 (hdSscxZgE58): Opening-gap cluster decides the 08:30 direction (live)
Live 2024-08-08 (Thu, ICT's birthday), ~08:00-10:00 ET, NQ, 15m / 1m / 15s / 1s. ~2h17m. Captions only.
Source tier: 2024 Mentorship. Walk-forward demo of Lecture 03 rules; no trade taken.

## Summary
Before the 08:30 jobless-claims release price sat between Wednesday's NDOG (above) and Thursday's NDOG (below), with Tuesday's NDOG and Sunday's NWOG also above. Cluster above → expect the 08:30 run up. It ran >100 handles in one second at 08:30 into Wednesday and Tuesday NDOGs; then traded to the CE/quadrants of those gaps to the tick. Teaches: 08:30 spools even without news (news makes it faster/larger), NDOG quadrants only for large gaps, equilibrium of the latest large range, reclaimed FVG, balanced price range, 15s/1s chart behaviour.

## Rules
- Don't care about the number on any report; it's "baked in" ~5:00
- 08:30 is a key time even with NO news: the algorithm "spools" anyway; medium/high-impact news makes the run larger and faster (looser bands of volatility) ~9:00-12:00, ~33:00
- When price is "sandwiched" between two opening gaps before 08:30 with no inefficiency to lean on → wait (breakout traders get trapped) ~12:00, ~26:00, ~50:00
- Direction at 08:30 = side with the cluster of NDOGs/NWOG, even if those gaps were already traded into ("not stale") ~26:00-28:00; "out of 100% you're probably in 80% or higher that that's the right direction" ~34:00
- NDOG labelling: e.g. "NDOG Wed" = the gap made Tue 17:00-18:00. Up gap: high = 18:00 open, low = 17:00 close (and vice versa) ~13:00
- Quadrants (0.25/0.75) on an opening gap only when it's large; < ~20 handles just eyeball the CE. NWOG same ~14:00-18:00
- Bodies respect gap levels; wicks "do the damage" ~19:00
- Fib use: ONLY to find the midpoint (equilibrium) of the most recent large directional range → premium/discount ("overbought/oversold"); indicators/divergence useless ~1:16:00
- Target choice: the FVG ABOVE equilibrium of the latest down-range, inside a bearish breaker (potential iFVG) ~30:00-32:00, ~1:22:00
- Breaker reminder: in a breaker (high, low, higher high that runs buy stops), focus on the FVG inside the leg, not just the down-close candles ~32:00
- Orange FVG = ICT is viewing it as an inversion; a BISI that price traded through after hitting the NWOG is NOT a buy ~34:30
- If price rallies into the NWOG before 09:30 → stand aside until the 10:00 Silver Bullet and only trade that premise ~22:30
- ICT's own trigger: a shift in market structure in the expected direction, inside a MACRO (last 10 min of the hour + first 10 min of the next) ~23:00, ~1:21:00
- 08:30 initial run is untradeable unless already positioned (1s chart: 17,986.75 → 18,0x7.75 in ONE second) ~43:30, ~1:56:00
- After a run, a down-close candle converging with an NDOG high/low/CE, when bullish → entry catalyst (15s) ~1:24:00
- Overlap of two candle bodies (top of one = open of next) is a PD array ("one of the 81"); hit to the tick ~38:30
- BISI: want an inability to reach its CE (or immediate repel); volume imbalance left open = bullish; each down-close candle should act as a bullish OB ~39:00-41:00
- If price falters below the supporting OB candle low before 09:30 → stand aside until 09:30 ~41:00
- BALANCED PRICE RANGE: a range offered both up and down (paint-roller analogy); price doesn't need to go deep into it again; use its quadrants ~1:22:30, ~1:58:00
- RECLAIMED FVG: a second return into an FVG is still tradeable; the wick may reach into the adjacent volume imbalance (+1 tick), but must fail at CE; then expect a breakaway gap (15-20+ handles) ~1:30:00-1:33:00
  - Stop: just beyond the volume imbalance / short-term high; partial at the next NDOG level ~1:32:30
- Stop example (long from an OB containing a VI): fill = OB candle open (worst case), stop = that candle's close (rejection block); may wick 1 tick below ~1:08:00
- Hypothetical: OB open 18,173 → target FVG CE 18,250 = 70-80 handles ~1:12:00
- Projected: if making the market, drop into the BPR, then run relative equal highs in PM ~1:36:00 (later did run the highs at ~10:00 ~1:52:00)
- Objective reached → done for the day ~2:10:00
- SMT (ICT): "Matrix" of 5m/4m/3m/2m/1m for NQ, ES, YM; wants one to fail (diverge) before an FVG or run; a qualifier, not a necessity ~2:07:00-2:09:00
- ICT's charts: 15s, 1m, 5m, 15m, 1h, D, W, M ~2:07:30
- If distracted mid-trade, close at least 50% ~1:48:00
- Don't show open P&L while trading (trade price, not equity) ~1:44:00
- Use a hard stop, never a mental stop ~1:02:00

## Process ([beginner])
- Homework: from 08:30 on, how much could you reasonably harvest (low end): one 10-handle trade? 25? 50? → discover your model (15, 20, 75 handles/day all fine) ~1:52:00

## Trade examples
- 2024-08-08 NQ: no trade. 08:30 run up into Wed/Tue NDOGs, NDOG CE/quadrant reactions to the tick; later 10:00 run of relative equal highs.

## Definitions
- Spooling: the algorithm entering a buy/sell program at a key time
- Balanced price range (BPR); reclaimed FVG

## Open questions / conflict checks
- [conflict check] "Direction toward opening-gap cluster ~80%" vs rulebook daily bias definition (rulebook already uses daily/weekly opening gaps as bias inputs)
- [conflict check] Stand aside until 10:00 SB if price reaches NWOG before 09:30 (Silver Bullet settled OFF in the bot)
- Switches: `gap_cluster_bias_0830`, `wait_if_sandwiched_between_gaps`, `reclaimed_fvg_entry`, `bpr_no_deep_retrace`, `ndog_quadrants_min_size` (20 handles)
