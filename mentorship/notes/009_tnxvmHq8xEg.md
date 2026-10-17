# 009 ICT 2023 Mentorship \ ES Live Execution & Mean Threshold Risk Management (tnxvmHq8xEg)
Tue Jan 17 2023 (date from chart axis tooltip) / ES H2023 (CME mini) / 1-min chart only / ~19.5 min, real-time replay 09:44-10:03 ET. Rules file label: Ep 07.

## Summary
Long ES from the 4030 weekly target (Dec 14 2022 daily close). After 09:30, the 09:40 drop swept sell-side below the 09:20 lows. He bought a down-close candle inside the FVG left by the 09:41 displacement candle. His stop sat under the mean threshold of the sweep candle. He pyramided to 14 contracts on down-close candles and trailed to breakeven, then to the volume-imbalance low. He sold everything at 4030.75 during the 09:50-10:10 macro.

## Rules
- Target = old daily close (4030 = Dec 14 close), set before the week; take the bulk at or above it ~00:28, ~01:18, ~05:12 [chart]
- Wait for 09:30; sell-side under the 09:20 low purged around 09:40, then the rally leaves an FVG; buy inside it as price nears its middle ~01:00, ~03:00 [chart]
- Initial stop below the mean threshold of the down-close candle nearest the 09:40 low. On the chart this is the MT of the 09:40 candle's body (open to close), not its full range ~04:17 [chart] [conflict] (Ep 02 defines MT with wicks included)
- Volume imbalance (gap between one body's close and the next body's open) must stay open. Price may touch either edge but not pierce it; the stop goes at its low ~02:14, ~13:46, ~16:31 [chart]
- Enter longs on down-close candles and take profits on up-close candles ~08:11 [chart]
- Second-stage OB: a down-close candle that trades into the volume imbalance is a bullish OB. Add near its mean threshold, not in the nearer FVG ~12:07-13:41 [chart]
- Trail the stop to breakeven (= low of the 09:50 OB candle) when price stalls/consolidates after trading through the bodies of the prior swing high ~09:46-10:25 [chart] [new: the stated reason is "stalling too much"]
- Trigger: a small SIBI's high must be broken fast ("needs to rip thru this"). After that, expect acceleration to buy-side above the 09:30 / 09:54 highs ~15:51-17:09 [chart]
- After the trigger, price should not trade below the lowest open/close of the current swing low ~16:19
- Macro 09:50-10:10 drives a run to liquidity or an inefficiency ~18:24 [chart: the run happened 10:00-10:02]
- Risk 1.2% initially, 1.3% after the add (100k account) ~05:27, ~08:24 [chart]
- Read price in 5-handle steps (20 ticks; $250 per ES contract) ~05:56, ~06:23 [chart box]
- [new] Futures only: he says this precision fails in retail forex ~14:00

## Trade examples
ES H23, 1-min, Jan 17 2023.
- 09:44 bought 8 @ 4014.50, stop 4011.50 (-$1,200), limit target 4036.00, later 4037.75.
- 09:51 bought 4 @ 4017.25 (market) for 12 @ 4015.50 avg. Stop still 4011.50; by 09:51:44 it was 4013.25.
- ~09:53 stop moved to 4015.50 (breakeven) with the note "risk removed, stalling too much, free look".
- ~09:56-57 added 2 (~4017.25-4017.75 implied) for 14 @ 4015.75.
- ~10:00 stop moved to 4016.00 (volume imbalance low).
- ~10:02 sold 9 @ 4030.75. A second 9-lot sell by mistake left him short 4, covered @ 4029.50. Flat.
- Stated result: $10,400.
- PD arrays: 1-min FVG ~4013.50-4014.95, volume imbalance ~4016.00-4016.25, +OB (09:50 down-close candle) open ~4019.50.
- Liquidity: sell-side under the 09:18-09:21 lows (~4011.4-4012) swept by the 09:40 low (~4009.0-4009.25). Buy-side at the 09:30 high ~4023.50 and the 09:54 high ~4024.

## Definitions
- Volume imbalance: no body overlap between two adjacent candles; the next candle opens above the prior close. Wicks may overlap ~02:16, ~07:18
- Market efficiency paradigm: buy down-close candles, sell up-close candles ~08:19
- Unrealized premium array = the 4030 old-close objective ~12:38
- 5 handles = 20 ticks = $250 per ES contract ~06:23

## Seen only on the charts
- Labels: "Stoploss is UNDER Mean Threshold", "The Risk is 1.2% (later 1.3%) of Total Equity", "Volume Imbalance", "Want To see Speed & Distance when it goes above this high", "Buyside Liquidity" at ~4023.50, "+OB" line at 4019.50, "Needs to rip thru this" ~4020.6-4020.75, "6 (then 9) Contracts come off above this level" at 4030.
- The intermediate stop of 4013.25 (≈ the 09:43 entry candle's wick low / the 09:40 candle's open) is not mentioned in the audio.
- Breakeven 4015.50 coincides with the wick low of the 09:50 +OB candle.

## Check of rules file vs charts (Ep 07)
- Old daily close as the draw: 4030.00 line drawn; the Dec 14 date can't be checked on a 1-min chart. Confirmed (level).
- Sweep then FVG entry: confirmed. The 09:40 low (~4009.0-4009.25) runs under the 09:18-21 lows. The entry at 4014.50 is on the 09:43 down-close candle, in the upper half of the FVG (~4013.50-4014.95, mid ~4014.25). "Near its midpoint" is approximate.
- Stop / which candle: the stop is under the MT of the 09:40 candle, the down-close candle that makes the sweep low. Pixel reading of the 00-04-00 frame gives high ~4013.50, open ~4013.25, close ~4010.50, low ~4009.0-4009.25.
  - Body MT is ~4011.875; the stop at 4011.50 is under it.
  - Full-range MT is ~4011.25-4011.375; the stop is ABOVE it.
  - So the frame contradicts Ep 02's wick-to-wick MT. For a stop, use the body midpoint (or confirm).
  - Not the 09:38 down-close candle (MT ~4013.6-4014). Not the 09:43 entry candle (MT ~4014.5; the blue arrow marks this one).
  - The stop also roughly equals the swept 09:18-21 lows (~4011.4); the frames can't separate the two readings. The [corrected] note in the rules file is confirmed.
- Trail "to the low of the retracement candle once price trades through the bodies": partly confirmed. Steps were 4013.25 → 4015.50 (low of the 09:50 down-close OB, = breakeven) → 4016.00 (volume imbalance low). The chart gives stalling/consolidation as the reason.
- Volume imbalance holds, stop at its low: confirmed (~4016.00-4016.25; stop 4016.00).
- Pyramid on down-close, exit on up-close: confirmed (adds at 09:51 and 09:56-57 after down candles; exit on the 10:01-02 up candle).
- Trigger / speed and distance: confirmed. The drawn line is at the high of a small candle after the 09:56 drop, ~4020.6-4020.75. Price broke it at ~10:00 and ran to 4031.75.
- Invalidation (lowest open/close of the swing low): nothing drawn; not checkable. The 09:56-57 swing low's bodies are ~4017.25-4017.5.
- Macro 09:50-10:10: confirmed (the run was 10:00-10:02).
- "Exit bulk 9 of 14": the plan label said 9, but fills show all 14 out at 4030.75 (an accidental double sell, then the short was covered). Risk of 1.2-1.3% is confirmed by the labels.
- 5-handle increments: confirmed by the drawn 4020-4025 box. 15 handles/day ≈ 4015.75 → 4030.75.
- Timing nit: audio says "9:43" for the big shaded bullish candle. On the axis the displacement candle is 09:41, and 09:43 is the down-close entry candle.

## Open questions
- MT for stops: body or full range? This trade fits the body midpoint; Ep 02 says wicks are included.
- Is the 4011.50 stop really the 09:40 body MT, or the 09:20-low area that was just swept? Both fit within ~0.25.
- Third-add price isn't shown in a fill (it is inferred from the average). Was it exactly the 09:50 OB candle's MT (~4017.9 range / ~4018.5 body)?
- When to move to breakeven: a time-in-consolidation rule needs a concrete bar count.
- "Speed and distance" has no numeric threshold.
