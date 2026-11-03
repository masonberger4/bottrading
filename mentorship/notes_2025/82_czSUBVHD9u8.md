# 2025 Lecture 82 (czSUBVHD9u8): series intro + first worked trade, Mon 2025-01-06 (NQ/MNQ)
Full read (8.8k words). Source tier: 2025 Lecture Series (below 2023 Mentorship on conflicts). Framing: "if I were a new student of my own 2024 Mentorship" [beginner framing]. ~20 lectures in January, Mon-Fri only.

## Five central tenets
1. Settle on one market (NQ index futures; chosen for volatility/intraday setups; one-minute or higher charts).
2. Know how price delivers by time (economic calendar, macros, parts of the daily range: when markets run, consolidate, reverse).
3. Understand key pools of liquidity and why price draws to them.
4. Identify which inefficiencies matter in this model (filters out the problematic ones).
5. Simple entries and low-hanging-fruit targets, repeated ("wash, rinse, repeat").

## Rules and practice (what ICT says)
- Progression: back test, tape read (watch, don't click), forward test in demo, then live; the student decides when. Not prop accounts (he calls prop rules a handicap). Live minimum $1,000; start on MICRO contracts (MNQ $2/pt vs NQ $20/pt), never straight into minis. Goal: cover a real monthly bill, not Olympic-level returns. February is when he shows the live rollout.
- Opening range = the first 30 minutes ("the only range the algorithm worries about"). First 60 minutes = separate "dealing range" (own lecture later). Power of three / daily range character covered later. If the rules aren't met, don't trade.
- Opening range gap (ORG): RTH settlement (prior day 16:00 close) to 09:30 open, measured on the 1-minute chart in RTH data. When larger than about 20 handles, run the Fib with: 0 and 1 (gap edges), lower quadrant, 50% = consequent encroachment (CE), upper quadrant (settings: 0, 0.25, 0.5, 0.75, 1). His example: several-hundred-handle premium gap opening.
- Huge gap: do not chase long in the gap direction and do not pick the top. Gaps tend to keep going in the gap direction early; expect a shift in market structure into the 10:00-11:00 lunch-hour area, then a move back into the gap. Upper quadrant of the ORG = high-probability draw (not required to reach CE; 50% level a wildcard).
- Reference ranges: old dealing range high/low; price below the old low = bearish; take the sell side then reclaim. Premium/discount from that range's equilibrium (premium = sell/target for longs; discount = buy/target for shorts).
- Bullish breaker: lower low that takes liquidity then trades back above the high; rally has several buy-side pools above.
- Sell-side imbalance buy-side inefficiency (SIBI) anchoring: use candle CLOSE (of the first candle) and OPEN (of the third) only where a volume imbalance exists (closes/opens differ by even one tick); if the close overlaps the next open there is no volume imbalance and you use the candle's WICK high/low instead. Draw the rectangle from those prices; consequent encroachment/quadrants come from there.
- Hourly (60-min) inefficiency sitting in premium relative to the day's hourly range: price trades into the upper quadrant (around OTE), is completely overlapped (all inefficiency filled by buy-side delivery), and bodies respect CE. 
- PM session: gears change at 13:30. Once the morning's up-leg has fully delivered into the 60-min SIBI and price breaks below its midpoint, don't expect more upside, look to short.
- Entry (example): timed to a macro (14:50-15:10), at the lower half of the 60-min SIBI, target liquidity/ORG upper quadrant, and "catch a runner" toward ORG CE. Entry = the 1-minute candle's open on the candle after a down candle, using the previous candle's range as an immediate rebalance (sell at its open; stop above its high of 1.25 away in the example, essentially zero drawdown). Wait for the entry, don't enter early in a gap/time without sign.
- Stop: 15 handles on the example (MNQ = $30 risk), target ORG upper quadrant (~50 handles; 3R+). He prefers aiming for 3:1 to 5:1 over 1:1 because it invites fewer trades; 1:1 produces more trading ideas.
- Exit: stop-out after the target zone, with a runner idea; last RTH hour (15:00) can draw back into the range.
- Wait for the first 60 minutes of trading; it tells you whether to sit or to wait for the reversal and play after it proves itself. Don't try to capture every high and low ("33 years of experience can; a beginner can't").
- The trades shown are with his son Caleb's live account (execution by Caleb, logic by ICT); no live streaming of trades so students don't pile onto his levels.

## Our interpretation / conflicts to check
- ORG "RTH settlement to 09:30" matches rulebook NDOG/ORG? check. [in rulebook?]
- Fib settings 0/.25/.5/.75/1 [in rulebook: quadrants].
- Entry uses "immediate rebalance" of the previous 1-minute candle after a down candle; conflicts possible with rulebook entry models. [conflict check]
- 3:1 minimum RR stated as preferred, not a rule. [beginner]
- Macro 14:50-15:10 [in rulebook: macros].
