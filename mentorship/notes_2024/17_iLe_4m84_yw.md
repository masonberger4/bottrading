# 2024 Mentorship Lecture 17 (iLe_4m84_yw): "Impeding barriers" week begins: small ORG (under 30-40 handles) means wait until 10:00, immediate rebalance defined, bodies tell the narrative, nested NDOG/NWOG draw, no setup = a win
Live Mon Aug 26 2024, ~09:25-13:30 ET, NQ, 1m/2m/15m, then 5m/60m/4h. ~4h04m (from ~1:10 onward almost entirely psychology: stop losses, impulsiveness, women as traders, his early losses; no market content after ~1:50). Captions only.
Source tier: 2024 Mentorship. No trade. Week theme: things that are "problematic" for a trade (when to stand down).

## Summary
NQ opened just below Friday's settlement: a small discount ORG of about 20 handles. ICT's protocol: when the ORG is under ~30-40 handles ("little unchanged"), sit on your hands until 10:00 and let the algorithm have the first 30 minutes; the open was sloppy and two-sided. He defines the immediate rebalance (a large displacement candle whose range the very next candle fully re-delivers back to the prior candle's low/high) as one of the purest one-directional signatures. The bodies never confirmed a turn, a 15m BISI was finally traded through and used as an inversion, and price drew down into the nested Aug 23 NDOG / Aug 18 NWOG. Caleb had no setup: the lesson is that a day without your model is a win (no loss, no commission). Higher time frame: a single-candle daily overlap (balanced range) below; if price enters it fast, expect weeks lower into the holidays.

## Rules
- SMALL ORG FILTER: ORG under ~30-40 handles (open "little unchanged" vs prior 16:14/16:15 settlement) = no trades 09:30-10:00; wait for the full 30-minute opening range (or the 10:00 SB) ~9:00-10:00, ~12:00-14:00, ~17:00
  - Large ORGs invite volatility and protraction; small ones a reluctant market ~3:00, ~12:00
  - Forcing a liquidity target in the first 30 minutes on a small gap "tends to be wrong" (25 years of ORG use) ~17:00
  - A 20-handle move on NQ shown (19,732 to 19,752) ~16:30
- First rule of engagement for an easy morning: did we open significantly higher or lower than settlement? ~11:00
- Monday: previous settlement = Friday 16:14 RTH price ~11:30
- Sentiment: other streamers' chats chomping at the bit on the other side = confidence for ICT (retail indicator) ~14:30-15:00
- Note in your journal which first-30-minute sessions are clean vs spotty/disorganized; clean ones are what you trade ~24:00
- IMMEDIATE REBALANCE: a big range candle (larger than recent ranges) closing beyond the prior candle; the NEXT candle trades all the way back to the prior candle's low (bearish) / high (bullish), re-delivering the whole range; valid only on the very next candle ~27:00-33:00
  - Bearish context: signals speed and range lower; it is not a reversal; add or enter when you see it ~29:00-33:30
  - Works on all time frames ~32:30
  - Highest-order FVG use: you want gaps NOT to close; an immediate rebalance is the one case of full re-delivery that is strong ~28:30-29:00
- BODIES TELL THE NARRATIVE: wicks through a level prove nothing; until bodies close back, "nothing has changed"; don't pick the bottom ~35:00-36:00, ~39:00, ~44:00
- Rejection block level = lowest down-close candle's close (bullish RB) ~36:00
- INVERSION of a higher TF gap: once a 15m BISI is traded through, treat it as an inversion; bearish as long as price does not get back above its midpoint; best if it wicks just under the CE and leaves ~37:30-38:00, ~50:00
  - After leaving the inversion, the next 15s/30s/45s FVG = institutional order flow entry drill; target the next sell-side or inefficiency ~50:30-51:00
- NESTED NDOG + NWOG = "black hole" draw; Caleb targets NDOGs/NWOGs for his draw ~38:30-39:30, ~51:00
- Reclaimed FVG vs inversion: a gap price only wicks through (no displacement away from it) is not reclaimed; Friday's was an inversion (L16) ~21:00-22:00
- Balanced price range (HTF): single-candle overlap that offered both sides; if price later re-enters it quickly, the higher time frame has turned (weeks, not days) ~1:10-1:11
- Three drives (same as L14) / "three Indians" in Street Smarts ~1:15
- Hidden (type two) divergence on momentum indicators as retail-logic support only ~1:23-1:24
- ORDER BLOCK correction: change in state of delivery is the opening price of the highest down-close candle in a succession (bullish OB), not the lowest ~1:25-1:26
- COIN-FLIP CHALLENGE (mechanical, not a recommendation): heads buy, tails sell, the first return to the ORG; stop at the other end of the opening range; risk 0.25%; "profitable at the end of the year" (run it in a system tester) ~1:42-1:43

## Risk / Process [beginner]
- No model setup today = no trade; a day without a loss or commission is a win ~51:00-58:00, ~1:28
- Always use a real stop (structure-based, not 2 handles); the stop defines where you are wrong ~1:34-1:38
- Caleb: funded account until $5,000, then withdraw to AMP Global, micro contract, one standard lot only at 1.5x full exchange margin; one win = done, one loss = done ~1:56-1:58
- Exercise ICT used on himself: only allowed a time-based trade Friday PM 14:00-16:00 ~1:51-1:54
- One good trade a week beats 99% of retail ~1:51
- Logging assignment: every up-close candle on 1m/5m mapped to the 15m; every inefficiency that stayed open; the 12:00 close (AM session ends at noon) ~1:07-1:08

## Trade examples
- 2024-08-26 (no trade): small discount ORG (~20 handles) inside the Aug 25 NWOG; buy-side above the open taken first, sell-side relative equal lows displaced; immediate rebalance on the drop; 15m BISI inverted; draw to the Aug 23 NDOG nested in the Aug 18 NWOG; old 15m low 19,591.75.

## Definitions
- Immediate rebalance: displacement candle whose range the next candle fully re-delivers to the prior candle's extreme.
- Little-unchanged open: ORG smaller than ~30-40 NQ handles.
- Models named: OTE (flagship), 2022 model (daughter), Silver Bullet (Cameron), first-presentation FVG with NDOG/NWOG (Caleb) ~1:17.

## Open questions / conflict checks
- [conflict check] Small ORG (<30-40 NQ handles) = wait to 10:00 vs rulebook N8 large-ORG wait (conflict 15 ORG-SIZE is about quadrants, not this). Switch `small_org_wait_1000` default off. Handle threshold is ICT's ("30 to 40"); ES equivalent not given.
- [conflict check] Bullish OB change of state = opening price of the HIGHEST down-close candle of the succession; L14 used "lowest opening price of consecutive up-close candles" for bearish (consistent mirror). Check rulebook OB definition.
- [new] `immediate_rebalance_continuation` (enter/add on the next-candle full re-delivery); default off.
- [new] `coin_flip_org_return` (ICT's mechanical challenge: first return to the ORG, stop at the other OR extreme, 0.25% risk); default off. A pure baseline test.
- [new] `noon_am_close` (AM session closes at 12:00 for logging); study only.
