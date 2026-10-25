# 104 ICT Mentorship 2023 - Market Maker Models (iKsIbUblSWM)
Lecture, no live trade. Example is GBPUSD (FOREX.com feed), the 30th into the 31st (month
not shown; price ~1.2120-1.2200). Timeframes: close-line chart, 60m, 15m, 5m. ~58 min.
ICT bills it as his last public teaching video.

## Summary
Defines the market maker sell model (buy model = exact mirror). It is a full swing:
original consolidation, buy-side delivery up through accumulation stages into a
higher-TF PD array above buy-side liquidity, a smart money reversal at the highest high,
then sell-side delivery down through distribution stages to below the original
consolidation. Its premise: PD arrays from the buy-side half of the curve flip roles on the
sell-side half. Traders may trade any one segment; no single stop/target formula is given.

## Rules
- Markets go up for two reasons only: to take buy stops (liquidity) or to fill an inefficiency (FVG); otherwise they consolidate or are being manipulated by news ~14:19, ~28:32 [new]
- Draw selection: after spotting the obvious liquidity (relative equal highs), look just beyond it for the nearest inefficiency; that is how far the run can go (here a 60m SIBI above the equal highs) ~16:18, ~20:37 [chart] [new]
- Qualify the PD array by bodies: wicks may pierce the 60m SIBI but bodies stay inside or below it, on the 60m, 15m and 5m alike ~15:59, ~21:53, ~34:55 [chart]
- Sell model sequence (each label read from the 5m chart) [chart] [new]:
  1. Original consolidation: sideways range where smart money accumulates; top = repeated smooth edge of bodies/wicks, bottom = lowest low ~27:28-29:22
  2. Leave it with a body closing out of the range; if price returns to the top of it, that is the original entry (long) ~31:17-32:17
  3. +Order block = 1st stage accumulation (down-close candle inside a bullish breaker: low, high, lower low, break up) ~36:38-36:52
  4. +FVG CE = 2nd stage reaccumulation (bullish FVG retraced only to its midpoint) ~42:03-42:20
  5. Buy-side delivery runs above the buy-side liquidity into the higher-TF PD array (60m SIBI)
  6. Smart money reversal = selling the wicks above the PD array high, within a tick or two of the extreme; flagged as expert-only ~42:41-45:09
  7. Low risk short = rally back to CE of the 60m SIBI after the break lower; stop just above (the high, or CE of the upper wick) ~45:17-45:58
  8. -Breaker = 1st stage distribution: high, low, higher high, then the low taken out with an FVG; short the retrace into the breaker ~47:52-48:44
  9. -Order block = 2nd stage redistribution: up-close candle, price retraces to its mean threshold (half the body); expected to be the fastest leg ~49:40-50:13
  10. Further pyramid where price retests a buy-side-curve array from below ~53:00-53:32
  11. Target: below the original consolidation low (sell-side liquidity of the longs); take ~80% off there, then see if it goes deeper ~47:27, ~53:35
- Stage labels shift with skill: if you missed the earlier stage, the next one becomes your 1st stage (e.g. the bullish OB becomes 1st-stage accumulation if the return to consolidation was not seen); both readings are valid ~37:12-38:20, ~50:19-51:00 [new]
- Curve: a vertical line at the highest high splits the buy-side of the curve (left) from the sell-side (right). Discount arrays on the buy side (bullish OB lows, FVG CE) act as resistance on the sell side; bodies should respect them ~46:56-47:27, ~51:45-53:32 [chart] [new]
- Re-entry: if stopped on the low-risk short, wait for price to drop below the FVG low; if it trades back to the FVG bottom, short again, stop above the highest high or the CE of the new top wick ~45:41-46:00 [new]
- Do not pick tops in bull markets; top-picking (smart money reversal) only in bearish conditions ~43:51-44:41 [new]
- Time: return to the original consolidation in London open; buy-side run and reversal into the NY open kill zone (07:00-09:00 for FX); target reached in London close 10:00-12:00 ~54:30-57:11 [chart]
- Inside one MM sell model he also spots OTE, a Model 2022 short (buy-side taken, MSS, FVG) and an NY open Silver Bullet ~55:24-55:52

## Trade examples
- GBPUSD 5m, illustrative only (no fills given). Prices read off the axis, approximate:
  original consolidation ~21:50 (30th) to ~04:15 (31st), about 1.2137-1.2148; return to it
  ~04:00; +OB 1st stage ~1.2172 (~05:00-05:40); buy-side liquidity (relative equal highs)
  ~1.2176; +FVG CE 2nd stage ~1.2181; 60m SIBI ~1.2193-1.2198; smart money reversal high
  ~1.2200 (~07:10); low risk short ~1.2195; -breaker 1st stage ~1.2190; drop back to
  ~1.2176 (the old buy-side level); -OB 2nd stage ~1.2186 (~08:35), then a large down
  candle; reprice line under the consolidation ~1.2137 (~09:45); low ~1.2120 ~11:00-12:00
  ET, at the relative equal lows (dashed line). [chart]

## Definitions
- Buy-side delivery: price actively moving up (offering buy side); buy-side liquidity is the static stop pool above highs. Same split for sell side ~10:30-11:45 [new]
- Market maker sell/buy model: the swing from original consolidation to a liquidity/PD-array extreme and back below (above) the consolidation; "swing trading" in ICT's sense ~5:20, ~28:19
- Original consolidation: where the move is accumulated; framed by a repeatedly referenced level ~27:28 [new]
- Balanced price range (refined): a SIBI and BISI overlapping in the same range after a sharp drop and sharp rip (few candles); marks trapped shorts, implies higher prices ~24:35-26:45 [chart]
- Rejection block: the lowest down-close candle area, named as a sell-side target ~22:33
- Inversion FVG: a SIBI that price closes above and later uses as a discount (support) ~34:28 [new]
- Unicorn: here equated with 2nd stage redistribution in the sell model, the most energetic drop ~41:02 [conflict: Ep 05 uses unicorn for an FVG inside a breaker]
- Smart money reversal: entry at the extreme wick beyond a PD array ~43:31 [new]

## Seen only on the charts
- The 2nd-stage redistribution rally came after price fell back to the old buy-side
  liquidity line (~1.2176); its body stopped at the gray line marking a buy-side-curve
  down-close candle low (~1.2185).
- The second "buy-side of curve used in reverse" line sits at the +OB (1st stage) low
  (~1.2167); the big down candle sliced through it.
- The 15m chart had trapped shorts / BPR below the consolidation; the final low was at
  the relative equal lows, not at the BPR.

## Open questions
- No fixed stop/target per stage; only the low-risk-short stop is stated (above high /
  wick CE). Coder must choose stops for breaker and OB entries (likely above the array).
- "Unicorn" naming conflicts with Ep 05; which wins?
- Exact original-consolidation boundary is discretionary ("a knack").
- How to detect the highest high (curve divider) in real time before the breaker forms.
- FX example; kill zones are FX hours. Index futures mapping is not given.
