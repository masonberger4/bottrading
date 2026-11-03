# te62 Trade Review - Price Delivery (Jackson Hole Day 1 recap) (MD1Ts09dkYs)
Recorded 2026-08-28 07:50 ET (Friday, JH day 2), reviewing 2026-08-27 / NQ daily + 1m / ~60 min. Captions only.
Source tier: Trade Executions (2026). 2023 Mentorship wins on conflicts. NQ points.

## Summary
Full explanation of the te61 trade. Daily context: price failed to reach a daily BISI's volume-imbalance high → return to premium, look for longs. Intraday at 09:30 the "megaphone" seek-and-destroy sweeps both sides; price respected the upper octant (0.125 = 29,451) of the daily BISI on a body basis; long after relative equal lows swept, confirmed by a candle unable to close below the midpoint between lows and last Friday's first presented FVG. Explains the pyramiding-at-or-below-equilibrium rule, the "upper half of the wick" order-flow rule, and a stop-placement error (should have been at the open of the last up-close candles = order block). PM session: 14:50-15:10 macro, 15:15-15:45 run, 15:50 MOC run into the daily iFVG CE (29,662).

## Rules
- Daily: if price fails to reach an expected discount objective (VI high of a daily BISI) → expect return to premium ~0:01-2:42
- Daily BISI graded in octants (0, 0.125, 0.25, 0.375, CE, ...); intraday lows that hold on the 0.125 level on a BODY basis = key level, bullish ~6:55-9:10
- Seek & destroy: expanding "megaphone" sweeps of highs and lows; trade nimbly; day 1 of Jackson Hole highest likelihood ~4:46, ~9:10
- Minimum criterion to buy sell-side: price is below the low (buying where sell stops rest) ~15:47
- Entry trigger: a candle failing to close below the midpoint between the swept low and the high of last Friday's first presented FVG (first FVG after 09:30) → enter; if it had closed below, wait for touch of that FPFVG high ~11:39-15:47
- First target: limit 1 tick below the intraday high; terminus extended to the higher old high (buy side) ~15:47-17:50
- Confirmations: close above the wick CE; close above the iFVG; retest of iFVG = fulfilled ~17:50-19:52
- Stop rolled to 29,501.75 (low came within 1 tick at 29,502.0); if stopped, re-enter same position immediately with stop below the next low ~19:52-21:54
- Futures preferred for tight stops (same high/low for everyone); forex brokers widen spreads ~19:52-21:54
- PYRAMIDING RULE: add longs only at or below equilibrium of the range from the entry low to the target (terminus); shorts at or above; once price passes equilibrium, no more adds; range is re-measured when terminus is extended ~21:54-23:55, ~28:21-32:43
- Fib reading: find the leftmost anchor and read levels straight down (octants, quadrants, CE) ~23:55
- Upper half of a wick (bullish): bodies must stay in the upper half and wicks not reach CE; open slightly below mid of upper half then immediate rally = confirmation; apply same logic from a candle's open to half the wick ~26:00-39:07
- "Event horizon": midpoint between the iFVG high and the wick CE ~28:21
- Partials: 4 off just above first high; plan 5 of remaining 6 at second target, runner to higher buy side; exit at the high of the green-shaded imbalance ~41:30
- Lesson: after the last up-close candles form, stop belongs at that candle's open (order block) — not below; ICT left it and was stopped ~41:30-43:51
- Gaps near the target rarely fill before target (in a hurry to the liquidity) ~46:12
- Liquidity engineering: run close to a high, drop to discount, build buy stops, then run ~46:12
- Bearish respect: at a key daily PD array, bodies unable to reach CE = respecting lower half ~54:59
- PM macros: 14:50-15:10 ("macro one"), 15:15-15:45 run, 15:40 last 20 min, 15:50 MOC final 10 minutes supercharges into daily PD array ~50:38-52:44
- Daily PD arrays drive big intraday runs: grade daily wicks (CE), old highs/lows, inefficiencies ~57:02
- Pyramid on the iFVG retest aiming for the old gap CE (PM example) ~50:38

## Trade examples
- 2026-08-27 NQ: 6 initial + 4 pyramid in discount = 10; 4 off at first high; remaining stopped near target. Stop 1 tick from being hit

## Definitions
- First presented FVG (FPFVG): the first FVG after 09:30 ET
- Megaphone (seek & destroy): expanding sweeps of both sides
- Event horizon: midpoint between two adjacent PD arrays' key levels

## Open questions
- Pyramid only at/below equilibrium of entry-to-terminus range: switch `pyramid_eq_rule` [conflict check vs Charter OSOK/Model 6 pyramiding]
- Stop at open of last up-close candle once trade runs: switch [check 2023 trailing]
- Re-entry after stop with same size: switch [conflict check vs risk halving after a loss]
- FPFVG prior day as discount array: switch [check rulebook]
- PM macro 14:50-15:10 and MOC 15:50: [check macro list]
