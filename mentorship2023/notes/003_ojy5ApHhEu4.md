# 003 Deep Learning On Nasdaq Futures Trade - January 04, 2023 (ojy5ApHhEu4)
Date discussed: Wed Jan 4 2023 (FOMC day, NFP week). Market: NQ March 2023 (NQH2023), ES and US100 CFD for comparison. Timeframes: daily, 60m, 15m, 5m, 1m. Duration 1:32:38. ("Ep 03" in mentorship2023_rules.md.)

## Summary
Review of a paper-traded market maker buy model on NQ: Jan 3 1m BISI / 5m OB under price, Jan 4 10:00 drop into it, long from the 5m-ish OB at 10:40, structure shift at 10:44, pyramid to 10 contracts, partials at the rejection block, the 10:00 wick high and the 11048 relative equal highs, last units stopped just before noon short of the daily volume imbalance. NQ picked over ES by relative strength.

## Rules
- NFP week: trade Mon, Tue, Wed up to the end of the NY AM session; Wed PM, Thu, Fri imprecise; don't trade the FOMC release ~2:44, ~36:56.
- Draw: daily volume imbalance above (bottom edge ~11075.50) plus 1m relative equal highs at 11048 ~0:11, ~17:43 [chart].
- Discount PD array: Jan 3 1m BISI ~10868-10889; 5m OB anchored on the HIGH of the Jan 3 down-close candle = 10864.75. Price may overshoot the BISI fully and hit the OB ~10:38, ~16:20 [chart].
- First entry is in the bullish OB after the sweep of a short-term low, before the shift: 6 long @10901 ~10:41, stop 10883.50 (below the OB box, inside the BISI), $2,100 = 2.1% of $100k ~39:00 [chart] [conflict].
- The break of the short-term highs (~10928, labelled "Buyside Liquidity") is the shift; stop to breakeven right after it ~40:15 [chart] [new].
- The 10:02 bearish FVG (10931.75-10945) that price rallies through becomes a balanced price range; price should not trade back below it; stop trailed to 10930.50, just under it ~42:40 [chart] [new].
- Adds go into the new bullish FVG above the BPR (~10945-10957) when its top holds; he added 2 (not 3) because price dug into it twice ~44:20 [chart]. Final size 10, avg 10925.25 [chart].
- IOFED add: one more contract only if price dips just below the FVG/up-close candle line (~10940); not filled ~50:20, ~52:03 [chart].
- Rejection block: the 10:00 candle; its body edge 10987 = first partial (2 off), its wick high 11018.25 = next target ~47:43 [chart] [new].
- A level like 10987 is a "speed bump", not resistance; expect expansion through it ~1:03:13 [new].
- Partials one contract at a time on each new high above the level (3 above 11018.25, 3 above 11048) ~1:04:25, ~1:07:15 [chart].
- After two partial rounds, stop to just below the measuring gap: 10963.25 ~1:05:00 [chart]. After the 11048 highs are run, stop to 11027.50, then 11045 (3 pts under them) ~1:09:15 [chart] [new].
- Final target: limit for the last units at the bottom edge of the daily VI (11075.50); high reached ~11068, not filled ~1:09:00 [chart].
- When the runner fails near the target, peel one off on a return to the last down-close candle; going into noon expect a retrace ~1:12:15, ~1:18:23.
- Never widen a stop ~1:14:05.

## Trade examples
- NQH2023, Jan 4, 1m. Sweep low ~10:05 at ~10865 (OB line 10864.75), short-term low retaken ~10:33, entry 6 @10901 ~10:40, MSS ~10:44, add 2 @10964.75 market 10:52, 2 more by ~10:57 (10 @10925.25 avg). Exits: 2 above 10987 ~11:28; 3 above 11018.25 ~11:30-11:32; 3 above 11048 ~11:35-11:37; 1 off ~11:45-11:55; last 1 stopped at 11045 ~11:58. Paper account 100,000 to 121,185 (+21.1%), "over 500 ticks". PD arrays: Jan 3 1m BISI, 5m OB, BPR, FVG, measuring gap; liquidity: short-term low (sell side), 10928 short-term highs, 11018.25, 11048 equal highs.
- US100 CFD, same day: same structure; it did reach its daily VI (~10975) ~1:25:15 [chart].

## Definitions
- BISI: up candle that leaves an FVG in one pass; bought for longs, target for shorts. SIBI: mirror ~28:05.
- IOFED: partial entry into an FVG that does not reach 50%, then the run ~30:30.
- Measuring gap: FVG left mid-move; from the low to it is about half the move ~31:35. Chart: gap ~10968-10972 vs low 10865 and high ~11068 (mid ~10966).
- Liquidity void is a true no-trade gap; a BISI is not a void ~32:50.
- Reclaimed OB: price leaves an OB, comes back into it as support; normal ~54:36.
- Market maker buy model phases: original consolidation, distribution, redistribution, smart money reversal, low-risk buy, reaccumulation (x2), return to the original consolidation's buy side ~1:27:50.

## Seen only on the charts
- 11048 equal highs = 08:35 and ~09:43 highs; the 10:00 1m candle opened ~10987 with a wick to 11018.25 and dropped ~110 pts to ~10875.
- OB box ~10888-10898 marked "+OB"; a second "+OB" at ~10955 after the 11:00 dip.
- Bull flag stop run ~11:00 dipped to ~10945 (bottom of the add FVG), held above the BPR.
- ES pane: same low time; ES's small gap after its shift was fully closed, NQ's was not.

## Open questions
- Exact OB candle(s) for the 10:40 entry and why 10883.50 for the stop (17.5 pts) are not stated.
- Fill prices of most partials not legible.
- Whether entering before the MSS is the model or a discretionary early entry; he says one can also wait for the shift ~1:28:30.

## Check of rules file vs charts
- Daily VI as draw: confirmed (shaded ~11075.5 up; last limit at its bottom, never filled).
- Price drops into discount into a 5m OB / 1m BISI: confirmed; the BISI was fully closed and the OB line 10864.75 (5m down-close candle high) was hit to about a tick.
- OB anchored on the down-close candle's high: confirmed for 10864.75.
- Takes short-term low, breaks short-term high leaving an FVG: confirmed (MSS ~10:44 over ~10928, FVG ~10945-10957). "9:30 open dropped below the lows": the big drop on the chart was at 10:00-10:05; the 09:30 dip was smaller and price ran back to 11048 by ~09:43.
- Setup in 10:30-11:00: confirmed (entry 10:40, MSS 10:44, adds 10:52-10:57).
- "Entry: long at the FVG": contradicted for the first entry; the 6-lot went in at 10901 in the OB before the MSS. The FVG was used for the adds.
- ~10 contracts, 2.1% risk: confirmed; the 2.1% is the initial 6-lot risk.
- Breakeven after buy side is run: confirmed, but the buy side was the internal ~10928 highs, not 11048.
- First FVG after the shift as protected zone: the zone on the chart is the pink 10:02 bearish FVG turned BPR (10931.75-10945); stop at 10930.50 sits under it.
- Bull-flag stop run before continuation: confirmed ~11:00.
- Scale out one at a time: confirmed for the 3-lots; the first 2 at 10987 went together.
- Trail below measuring gap after two partial rounds: confirmed (10963.25).
- Rejection block: the chart shows it as the 10:00 candle (body edge 10987, wick high 11018.25).
- Lunch retrace: confirmed; last contract stopped ~11:58 at 11045.
- 5 handles / NFP/FOMC / time-based charts: not chart-dependent.
