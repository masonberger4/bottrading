# 2024 Mentorship Lecture 26 (A1mLNIoEsq0): CPI-day open, wick consequent encroachment (CE) as a model, bodies building at a wick CE = continuation, stop above the order block opening price, break-even only after 25% of the target
Live Wed Sep 11 2024, ~09:26-10:46 ET, NQ, 15s + 1m, 5m, daily/weekly. ~1h20m (long passages on clout chasers, critics, mindset; skipped). Captions only.
Source tier: 2024 Mentorship. No clear live trade in the captions; teaching is on the 15s chart after the 08:30 CPI print.

## Summary
CPI (08:30) day. Large premium ORG (previous settlement ~18,846 vs ~18,920s open) into a daily/weekly inefficiency. Price dropped from an inversion FVG into the half-gap and full gap closure, then chopped around several PD arrays with "no real clear framework". ICT turns the session into a lesson on micro structure: the consequent encroachment (CE, 50%) of a long 1m wick is a level the algorithm refers back to; price ran a short-term high into the wick CE, built bodies around it, then flushed into the NDOG and expanded lower. Main teaching points: you don't need the full higher-TF gap to trade (the wick CE is enough), stops must "color outside the lines" (allow a wick to reach the CE of the neighbouring gap and sit above the order block opening price), and break-even only after the trade has run 25% of the way to the target.

## Rules
- WICK CE MODEL: "opposing premium and discount consequent encroachments on the wicks" can be your whole model; wait for price to respect the high (or low) of the inefficiency, run a short-term high/low, and reach the 50% of a long wick ~43:00-44:00
  - Don't need the low end of the daily inefficiency traded to: a wick already did the damage; its CE is enough ~43:00
  - Bodies building (consolidating, blocky) around a wick's CE when everything leans one way = it goes that way; "very few absolutes, but this is one" ~49:00-50:00, ~54:00
  - Price lingering too long at the wick CE = expect a run outside the inefficiency (flush into the NDOG) ~49:00, ~1:09
  - A wick that retraces only half of the previous wick = signature for the swing high holding ~56:00
- STOP PLACEMENT (adds to conflict 39 / STOP-PLACE): the stop has to allow a wick to trade to the CE of the gap above the entry; if the entry candle area contains an up-close candle among down-close candles (a bearish OB), the stop goes one tick above that order block's opening price (the change in state of delivery) ~1:00-1:01, ~1:07-1:08
  - Entry at the low of the 15s/1m gap rectangle; stop references the higher-TF wick CE and the OB open ~1:07
  - Once the next candle opens and trades down without the body closing at the high end, upper half of the gap should not be traded again ~1:08-1:09
- BREAK-EVEN ONLY AFTER 25%: don't jam the stop to break even immediately; once the trade reaches 25% of the profit target, then you can move to break even and cover commissions ~1:01-1:02
- ADD SMALL: when a premium array forms near a wick CE while already short, toss on one or two more contracts (a small add, not a full position) ~54:00-55:00
- EXITS: a limit exactly at a wick CE may not fill; "fluff up" exits to afford being slightly off; missing the last 15-20 handles is fine ~1:15-1:16
- Micro structure: 2-3 small setups a day at 1.5-3% each compounds; liquidity sits at short-term highs/lows, not only old highs/lows ~29:00, ~32:00-33:00
- Real volume imbalance: defined when an indecisive candle sits in the middle (bodies separated) ~53:00

## Risk / Process [beginner]
- Caleb: screenshot, write the signature in your own words, then find it on old charts in any timeframe ~50:00
- Don't follow anyone who shows open profit without a stop loss ~1:03

## Trade examples
- 2024-09-11 AM (no live trade in captions): CPI day; large premium ORG; drop from an inversion FVG to half-gap and full gap closure; run up into a 1m wick CE ~18,775; bodies built there; flush into the NDOG and lower expansion; a 15s wick CE low matched "to the tick" at ~18,741.75.

## Definitions
- Wick CE: 50% of a candle's wick; the algorithm "hand-shakes" with this level.
- Real volume imbalance: separation between two bodies with an indecisive candle in the middle.

## Open questions / conflict checks
- [conflict check] Stop one tick above the OB opening price, allow a wick to the CE of the neighbouring gap: second source for m2024 conflict 39 (stop placement, STOP-PLACE card).
- [conflict check] Break-even only after 25% of the target vs L22/L24 "cover costs at half the way to the first partial" and rulebook break-even rules (new conflict 44, BE-TRIGGER).
- [new] `wick_ce_entry` (enter at a long wick's CE after bodies build around it); default off.
- [new] `stop_above_ob_open` (stop one tick past the order block opening price inside the entry gap); default off.
- [new] `be_after_25pct_target`; default off.
