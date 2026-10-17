# 076 ICT Mentorship 2023 - ICT Reaper PD Array Introduction & Market Review (cgsltOB736E)
Date discussed: Tue Jul 18 2023 (recorded that evening). Markets: DXY (daily), ES (weekly/daily/5m), NQ Sep 2023 (daily, 1h, 5m, 1m). Duration ~30:40.

## Summary
Short market review (DXY reached its weekly volume imbalance; ES/NQ completing weekly volume imbalances) and the public introduction of the "ICT Reaper inversion fair value gap": an FVG in the discount half of the impulse leg of a bullish breaker. Price is allowed to cut through it; it later acts as support, with wicks reaching its CE. NQ long 6 @ 15781.00, closed 6 @ 15902.50 (~121 handles).

## Rules
- In a "buy program" (algorithmic repricing higher), never try to pick tops; mirror for sell programs. A bot should not take counter-trend reversal shorts while the higher-TF draw is above ~5:21, ~11:01, ~15:00 [new]
- Retail continuation patterns (bull flag, three drives) are traps: expect the 9:30 delivery to break them the other way first (Judas swing) before the real move ~12:42-13:43 [chart]
- Keep the weekly volume imbalance high and low on the chart as support/resistance and as draws ~3:29-3:40 [new]
- Projection: anchor on the breaker's impulse leg, swing low to swing high, and project -1 SD as the target (not the lower low). NQ: 15685.75 -> 15857.25 gives -1 = 16028.75, hit to about 1 handle ~16:36-17:16 [chart] [new]
- Bullish day: best long fills are at or below equilibrium (50%) of the reference range, measured from Monday's midnight open/low to Monday's high (0.5 = 15778.00), unless a Reaper is present, in which case expect price to cut deeper to the Reaper ~20:09-20:40 [chart] [new]
- Classic support/resistance (an old high drawn forward) only counts if an FVG sits there; here the Reaper's CE held ~21:09-21:29 [chart] [new]
- A dip into the previous day's range with bodies respecting its 50% (wicks may go below) and a reaction signature candle = entry ~22:24-22:45 [chart] [new]
- The Reaper needs context: a bias already set, plus a retail idea luring traders the wrong way ~22:10-22:20 [new]
- Silver bullet window 10:00-11:00: buy a down-close displacement candle as it trades down ~28:45 [chart]
- Hold for the big run: set the stop, no trailing, no partials, walk away; expect the high of day in the PM / last hour (~15:00) then a retracement (power of three) ~26:32-27:07 [conflict: Ep 03/04 scale out at each liquidity pool]
- Standard model: 6 contracts initial, up to 4 more on a qualifying dip for 10 total ~27:54, ~28:58 [chart]
- Settlement price toggle: check both settlement and regular closes when looking for volume imbalances and the Friday (TGIF) close ~3:47-4:33 [new]

## Trade examples
- NQ Sep23, Tue Jul 18 2023. Context: Mon Jul 17 rallied through last week's high (15857.25) to 15882.75. The 07:43 tweet expected the 08:30 retail sales release then a drop and a rally. 9:30 drop (Judas) to ~15736 (5m wick into the Reaper); bodies held ~15755. Entry: Buy 6 @ 15781.00 at ~10:40 on the 1m (silver bullet window), inside the standard IFVG 15767.00-15782.25. Stop below the low of the entry candle (exact price not legible; ~15765-15770 on the 1m). He did not add on the 11:30 dip into the 1m FVG (~15775). Exit: manual market close, Sell 6 @ 15902.50 ~12:55, +121.5 handles (~$14k). The high of day ~16028 printed ~15:00, matching the -1 SD projection. PD arrays: Reaper IFVG (1h), standard IFVG in the breaker, Monday equilibrium. Liquidity swept: 9:30 sell-side (short-term lows) after the bull flag ~22:51-29:12 [chart]
- ES Jul 18: dropped to take sell-side, then ran above Monday's high into the higher weekly volume imbalance; 15m FVGs and 15m order blocks were the reaction points ~6:05-7:08 (5m chart; levels not read)

## Definitions
- ICT Reaper inversion FVG (bullish), ~18:30-21:52 [chart] [new]:
  1. Bullish breaker: low, high, lower low (stops out longs), then price rallies through the high.
  2. The impulse leg (low -> high, the first leg of the breaker) leaves an FVG in its lower half, i.e. below 50% of that leg (discount). Example: leg 15685.75 -> 15857.25 (50% = 15771.50), FVG ~15727-15757 (1h, Jul 14 morning).
  3. On the way to the lower low price trades down through that FVG without respecting it (runs trailing stops; it is not a liquidity void).
  4. Price takes the breaker high (Monday), then returns. The Reaper is the expected support: wicks can stab into it ("wicks do the damage"), its CE holds, bodies stay at or above it, then a signature reaction candle confirms the entry.
  Bearish Reaper = mirror: bearish breaker with an FVG in the premium half of its impulse leg ~21:52-22:07.
- Buy program: algorithmic delivery repricing higher (not a "trend" or "bull market") ~11:07
- Standard inversion FVG within a breaker: separate, shallower array (15767.00-15782.25, from the Jul 14 midday drop) ~23:01 [chart]

## Seen only on the charts
- 1h chart (frame 18:40): blue box = Monday's range from the 15673-ish low (label partly hidden) to 15882.75, with 0.5 = 15778.00; orange "ICT Reaper IFVG" sits in its lower half ~15727-15757.
- Tuesday's 1h wick reached ~15740 (near the Reaper's CE); the 1h body closed back above ~15775.
- 5m (frame 12:40): Reaper box ~15718-15755; 9:30-10:00 lows ~15755 with one wick ~15735; teal FVGs ~15780 (10:30-11:15) and ~15900 (13:00) were the reload levels.
- Lower low of the breaker: ~15665 (Fri Jul 14 afternoon).
- DXY daily and ES weekly frames were not inspected in detail.

## Open questions
- Is "inversion" in the name literal? The bullish FVG is traded through (an inversion), yet it is used as support again in the original direction, so a coder can't tell whether to use the original FVG bounds or a re-formed gap.
- Which FVG goes to the timeframe? Here 1h. Does it need to be the lowest FVG in the leg, or just any FVG below 50%?
- The confirming "signature" candle is not defined (close back above the CE? a 1m MSS?); the entry was at 15781, well above the Reaper.
- Must the breaker high be taken on a different day (Mon here) and the return happen the next day?
- Exact stop price not read; "below this candle's low" on the 1m.
- He says more details will only be in his book.
