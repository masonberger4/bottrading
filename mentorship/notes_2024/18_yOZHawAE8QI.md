# 2024 Mentorship Lecture 18 (yOZHawAE8QI): discount ORG with mid-gap and 3/4 fill, accumulation below sell-side vs quick use of inefficiencies, FVG role changes (support, inversion, reclaimed), breaker upper half, 20/40/60-day PD array lookback, pre-stream short with rejection-block stop and propulsion block
Live Tue Aug 27 2024, ~09:25-12:55 ET, NQ (pre-stream ES and NQ trades reviewed), 1m/5m/15m. ~3h33m (long rants on "no algorithm", CFTC disclaimers, gold; skipped). Captions only.
Source tier: 2024 Mentorship. No live trade on stream; review of ICT's pre-session short (12 contracts, demo/execution video) and a hindsight walk of the AM long.

## Summary
NQ opened below the prior settlement (inside the Aug 16 NDOG): a discount ORG of more than 30 handles. Price first dropped through minor sell-side (relative equal lows), spent time below them (accumulation), then used the first FVG of 09:31-10:00 as support, ran to 3/4 of the ORG, inverted and reclaimed the same FVG, and closed the gap. ICT stresses: smart money buys only on down-close (sell-side) delivery, never on an uptick; time spent below a sell-side pool = accumulation for a longer run; inefficiencies should be used quickly (one touch and go). A bullish breaker with a long discount wick: use the body, and only the upper half should be respected. PD-array lookback: 60 trading days maximum, 40 more sensitive, 20 most active. Pre-stream short: entry at an OB inside a BISI whose true range includes its volume imbalance, add at the wick CE, stop above the rejection block, propulsion block confirmation, limit exits at the Aug 16 NDOG.

## Rules
- ORG checklist: a "significant" gap = more than ~20-30 handles; mid-gap is the first threshold; ~70% hit inside 09:30-10:00 when the ORG is more than 30 handles; you don't need a daily or session bias for it ~8:00-10:30, ~31:00
  - Profile: no FVG yet in the OR, price drops to clear minor sell-side, then returns to the mid-gap ("a nice little dandy of a profile") ~10:00
  - After a lower-quadrant hit, if price cannot get back above the mid-gap it stays heavy all day ~22:00
- Quick target method: a one-quadrant (25%) extension of the range you are working within ~18:30-20:30
- First FVG 09:31-10:00 again carried all day; can be support, then an inversion, then a reclaimed bullish FVG on the same day: role is defined by how price uses it, not by the pattern ~25:00, ~1:04-1:05, ~1:12
- ACCUMULATION vs REDELIVERY: time spent below sell-side (relative equal lows) = smart money absorbing sell stops for a longer, protracted run; one fast touch-and-go = redelivery ~47:00-49:00, ~57:00-59:00, ~1:42
  - Inefficiencies (FVGs) are best used once, quickly; price should not meander inside them ~58:00
  - Smart money buys on down-close candles (sell-side delivery) only, never on an uptick or breakout ~1:03
  - Speed of delivery is proportional to how close the liquidity/inefficiency is to price ~41:00
- Shift in market structure: should be sudden and abrupt ~1:11
- BULLISH BREAKER: the up-close candle that broke structure after taking the longs below; with a long discount wick, measure the BODY, and price should stay in the upper half of it (bodies may poke 1-2 ticks out on NQ; ES ~1 tick) ~1:19-1:24
  - Any bullish PD array: the lower half should not be traded to; if price reaches the deepest part it must reject immediately or it is a dud: scratch the trade ~1:23, ~1:35
- Consolidation (marking time) at the ORG high (prior settlement) after a bullish fill = support ~1:25
- PD ARRAY LOOKBACK: 60 trading days maximum (not calendar days); 40 days more sensitive; inside 20 days = most active ~1:26-1:28
- Lunch macro 11:30-13:30: expect a deeper retracement toward the first low before price in that range; 11:30 = London close (CFD traders flat) ~1:30-1:31
- "If I ever say hope in a trade, I close it" ~1:44
- PRE-STREAM SHORT (ES/NQ) mechanics ~2:35-2:57:
  - A volume imbalance that is part of a BISI/SIBI: use the VI, not just the wick, as the true range of the inefficiency ~2:35
  - Order block forming inside an inefficiency, with a second OB digging into it whose body does not cross the first OB's half = strong conviction (propulsion block) ~2:36-2:40
  - Inversion FVG: price should stay out of its upper (premium) part; wicks may do the damage ~2:42, ~2:50
  - Stop above the rejection block (highest up-close close in the swing); an RB is traded to once, then should not be revisited ~2:43-2:44
  - Add at the wick CE ~2:45, ~2:55
  - Partial plan: limit orders at a halfway level (3 of 12) and the old Aug 16 NDOG ("lowest hanging fruit") ~2:56-2:57
- DAILY HIGHS/LOWS as liquidity: prior day, Thursday and Friday highs and lows are draws (Sunday: only its opening price/NWOG matters) ~3:09-3:11
- Reclaimed bearish OB: price returns to an OB it already left and must respond immediately ~3:15
- First run into a stop pool is fast and sudden (they won't let the orders be pulled) ~3:24-3:25

## Risk / Process [beginner]
- Caleb starts with the first run off the first foothold (e.g. long near the low, out just above the next high), then watches the rest of the day ~1:45
- Back-test each run: candles to reach the target, drawdown in handles, log the language "I am pleased to see..." ~1:49-1:50
- Demo/paper is used for CFTC reasons; real-account examples exist (AMP, TD Ameritrade playlist) ~27:00

## Trade examples
- 2024-08-27 AM (hindsight long): discount ORG, sell-side relative equal lows taken and accumulated below, first FVG 09:31-10:00 low 19,555.25 held "to the tick", 3/4 ORG fill, bullish breaker, full ORG closure, then the nested NDOG/NWOG.
- 2024-08-27 pre-session short (ICT, 12 contracts: 6 at an OB inside a BISI, +6 at the wick CE): stop above the RB (592.75 high = close); propulsion block; limit exits at a halfway level and the Aug 16 NDOG.

## Definitions
- Accumulation: price spending time below sell-side (or above buy-side) while smart money absorbs orders.
- Reclaimed FVG: a gap that was inverted and is regained, reverting to its original role.
- Propulsion block: an OB that trades into a prior OB without its body crossing that OB's half.

## Open questions / conflict checks
- [conflict check] ORG threshold here 20-30 handles ("significant gap") vs L17 30-40 handles; same SMALL-ORG idea. One switch `small_org_wait_1000` with threshold values 20 / 30 / 40.
- [conflict check] PD array lookback 60 trading days (40, 20 more sensitive) vs L03/L08/L13 NDOG 5 days / NWOG 5 weeks (conflict 1 GAP-LIFE). Evidence for the 60-day side.
- [conflict check] Breaker: use the body and its upper half (bullish) vs owner #14 full-range breaker (conflict 13 BREAKER-ZONE). New position.
- [new] `accumulation_below_pool` (time below sell-side before a long = longer target); needs a measurable proxy (ours); default off.
- [new] `quadrant_range_extension_target` (25% extension of the working range); compare L08 quarter_range_projection_target.
- [new] `vi_true_range_of_fvg` (include an adjacent VI in the FVG range); compare L02 vi_extends_fvg.
- [new] `prior_day_thu_fri_hl_draws`; default off.
