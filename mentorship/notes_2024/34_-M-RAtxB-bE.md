# 2024 Mentorship Lecture 34 (-M-RAtxB-bE): NDOGs & tape reading: two new day opening gaps (16:14 RTH settlement or 16:59 ETH close to the 18:00 open), ORG mid-gap 70% held, no trade ahead of 10:00 news, inefficiencies must be left within 1-2 candles, NWOG half-working sequence, measuring gap from the swept level
Live Tue Sep 24 2024, AM session (~09:00-11:45 ET, approx.), NQ (Dec), 15m/1m/15s. ~1h44m stream, mostly silent chart work ("the chart did all the talking"). Whisper transcript (no YouTube captions), sparse.
Source tier: 2024 Mentorship. No trade by ICT; a hindsight market maker buy model walkthrough for students (Caleb named).

## Summary
Morning: ORG mid-gap ~20,103.75; wanted a sweep of the 20,085 sell-side before 10:00 news, then a run toward the Aug 22 high. He does not trade ahead of the news: after the 10:00 release's initial hit, give it a few minutes and look again. The 20,085 run happened before 10:00; price had already traded half the ORG ("the 70% strike rate still holds"). FVGs drawn while price dropped were expected to be re-used as inversion discount arrays. Too much time inside a gap = it won't perform: an inefficiency should get one or two candles inside it and then be left. Late morning: three drives into Monday's London 03:30 low, then the NWOG's lower half worked, a wick below the NWOG low, then the upper half; once the midpoint is breached price should work the upper half; back into the small area below = go to the sidelines and wait for the afternoon. Measuring gap: measure from the swept LEVEL (not the candle wick) to ~50% of the gap low; the full projection overlapped the ORG lower quadrant; the low-hanging objective was the 09:30 open (ORG low). Final segment: the two new day opening gaps.

## Rules
- TWO NDOGs [new]: (a) ETH close (16:59 1m candle's close) to the 18:00 ETH open, the one used "for several months"; (b) RTH settlement (final print of the 16:14 1m candle; "there is no 4:15") to the 18:00 open. Both work, no advantage either way; when (a) has no gap (17:00 close = 18:00 open), annotate that level and use (b). There is no 16:45 gap ("something you're making up"). Mark them on a 1m chart ~1:31-1:42 (NDOG-DEF)
- ORG = the 16:14 settlement to the 09:30 open, quadrants with the fib; RTH view to see it ~0:15 (ORG-CLOSE A)
- ORG MID-GAP [in rulebook]: half the ORG traded between 09:30 and 10:00, "the 70% strike rate still holds"; the lower quadrant may stay unfilled ~0:15, ~0:20 (ORG-CE-WINDOW A)
- NEWS (10:00): no trading ahead of the release; after the initial hit "give it a few minutes" and then look for the setup; a pre-news stop run (here 20,085) primes the move ("smokescreen") ~0:16-0:19 (NEWS-WAIT)
- FVG TIME [conflict check]: "inefficiencies have to stay with one or two candles and leave it"; price building multiple candles inside one = it won't perform; too much time inside the NWOG flagged ~0:57-0:58 (FVG-VALID D)
- INVERSION AS DISCOUNT: FVGs formed on the drop are colored for re-use; once price trades above, they should support price toward the minor buy-side (initial high of the day) ~0:20-0:21, ~1:27
- NWOG HALF-WORKING [new]: normal to work the lower half, go to or just below the midpoint, wick below the NWOG low into a discount array, then reach for the upper half; once the midpoint is breached it should work the upper half; a return into the area below = sidelines until the afternoon ~1:14-1:22
- ACCUMULATION SIGNATURE: inside each bullish FVG and the breaker low, price stays long enough "to absorb anyone that would be trying to sell against it" (HFT accumulating longs); bodies respect the breaker, stabs inside are normal ~1:27-1:28
- MEASURING GAP [in rulebook]: measure from the swept level (not the wick low) to ~50% of the gap's low; the doubled distance is the projection; here it overlapped the ORG lower quadrant ~1:29-1:31 (measuring_gap_projection, L38)
- THREE DRIVES: three lows into a previous session low (Monday London 03:30) before the reversal ~1:11
- PATIENCE: many small setups after the news were ignored; he waits for one specific setup ~0:54-0:57

## Trade examples
- 2024-09-24 AM (no trade): 20,085 sell-side run before 10:00 news; ORG half filled; three drives into Monday's London low, NWOG lower half then upper half; target the 09:30 open (ORG low), stretch = ORG lower quadrant / measuring gap projection.

## Open questions / conflict checks
- [conflict] NDOG: rulebook L6 (052) uses 17:00 close to 18:00 only; L34 adds the 16:14 settlement version and makes it the fallback: new card NDOG-DEF.
- [conflict check] ORG anchor 16:14 (with L47): ORG-CLOSE A.
- [conflict check] 1-2 candles inside an inefficiency (L28, L33, L36): FVG-VALID D.
- [new] `ndog_rth_settlement` (16:14 -> 18:00, fallback when the ETH gap is empty); `nwog_half_sequence`; default off.
- Whisper transcript, ~25 KB of VTT for a 1h44m stream: long silent stretches; levels named from speech only.
