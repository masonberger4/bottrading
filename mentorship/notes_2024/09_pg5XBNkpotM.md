# 2024 Mentorship Lecture 09 (pg5XBNkpotM): Gap-up open, don't buy premium, opening range gap high as fair value, exhaustion gap, SMT with ES not Dow
Live 2024-08-15 (Thu, 08:30 news), ~09:28-10:35 ET, NQ (+ES, YM), 1m/5m/15m + weekly. ~1h06m. Captions only.
Source tier: 2024 Mentorship. No trade (observation only; ICT left for an appointment).

## Summary
Large gap-up at 09:30 above yesterday's RTH settlement after an 08:30 impulse. ICT refuses to buy ("too rich, too long in the tooth"): early-session chop is a trap holding breakout longs. He waits for a break below an FVG to act as an inversion FVG and a return to fair value, defined as the opening range gap high (the 09:30 opening price). NQ made a higher high while YM did not (and ES lagged). By ~10:30 no trade: Caleb's window has expired; expect the opening price / gap to be revisited in the afternoon.

## Rules
- RTH OPENING RANGE GAP: mark yesterday's RTH settlement and today's 09:30 opening price; on a gap-up, the 09:30 open = the opening range gap high ~3:00-5:00
  - A complete return to the settlement isn't required, but look for signs of a try ~4:00
  - "Initial fair value" after a gap-up run = the 09:30 opening price; expect price to come back to touch it even if it goes higher later ~34:44, ~40:00
- Opening range = 09:30-10:00; watch it first before acting ~4:00, ~20:00
- DON'T BUY PREMIUM: after an 08:30 run + gap-up open + initial run to buy-side, don't chase; wait for a discount (below old lows / relative equal lows / gaps) ~12:00-16:00, ~24:00-30:00
  - Rule for the journal: "nothing forces you to pay too much" ~14:05
- Early-session chop after news = trap; wait ~20:00-23:00
- Three drives into buy-side (jagged highs) → watch for a break lower ~16:01
- INVERSION FVG validation: wicks may spike above it ("permissible") as long as bodies stay inside; the upper half should stay open; if price fully rolls over the gap and trades higher → no bias, no trade ~42:00-47:00
  - EXHAUSTION GAP: a gap price should NOT return to; if it does fill, the idea is weakened ~44:00, ~54:00
  - Quadrants on a large inversion FVG: want the upper half left open, work done in the lower half, then acceleration below with large-range candles ~1:04:03
- If the morning gives nothing, wait until 11:00-11:30 and fade the run of the morning in the lunch macro ~47:00
- SMT: prefer ES vs NQ; YM (Dow) is usually the one that "doesn't listen" and is the first sign of cracking; don't make a case for SMT on Dow alone; if ES/NQ breadth agree there's strength, otherwise don't chase continuation ~38:00, ~50:16, ~1:02:01-1:04:03
  - ES lagging NQ → either ES catches up or NQ breaks down ~26:04
- Wanted setup: a stop run above the high by a meaningful amount (10-20 handles), then failure ~1:00:03
- Election-year bias: built-in buy model; shorting every "broken wing" gets chopped ~28:00
- Weekly wick CE (treated as a gap) as a reference; inversion of that level if traded through and back ~32:00
- Breaker inside the NDOG; respond without waiting for a close ~10:00
- Afternoon expectation: if the levels (opening price, gap) aren't hit before 13:00, expect them after lunch ~1:02:01

## Risk / Process [beginner]
- Caleb's time window ends ~11:00; after that, charts off, back-test in the evening ~1:00:03
- Future streams: ~09:15-11:00 ~1:00:03

## Trade examples
- None taken. Watched a short idea: break below the FVG → IFVG → target the 09:30 opening price / opening range gap high.

## Definitions
- Opening range gap: gap between prior RTH settlement (16:15 ES/NQ) and the 09:30 open.
- Exhaustion gap: late-run FVG that should not be revisited if the reversal is real.

## Open questions / conflict checks
- [conflict check] ORG definition: rulebook ORG = prior close (ES 16:15) to 09:30 → consistent. 09:30 opening price as the first "fair value" target after a gap-up is [new]: switch `org_open_price_first_target`; default off.
- [new] `no_long_after_gap_up_and_news_run` (no longs in premium after gap-up + 08:30 run); default off.
- [new] `smt_exclude_dow` (SMT only ES vs NQ); check rulebook SMT pairs.
- [new] `ifvg_body_inside_rule` (bodies must stay inside IFVG, wicks allowed); default off.
- [new] `lunch_macro_fade_if_no_am_trade` (11:00-11:30); default off; check against the rulebook's lunch rules.
