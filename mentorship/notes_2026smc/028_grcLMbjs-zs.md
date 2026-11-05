# 2026 SMC 028: Review of a missed 09:30 short, NQ (Mon Aug 24 2026, Jackson Hole week)
Full read (3.4k words). Clean caption. Frames laptop-only.
## Summary
Daily BISI graded in octants drives the whole overnight; 07-09 consolidates around its middle so a one-directional 09:30 move is expected; price fell straight out of the open (no entry); then order block and FVG validity "tethered to an octant"; 10:00 Silver Bullet IFVG long.
## Rules in ICT's wording
- Daily: "did we get a close below midpoint of this wick" (wick CE) = first sign lower. Grade the daily BISI from its high to the VI low (candle close); bodies separated by a VI carry information even if wicks overlap.
- Overnight: price moved between the octant / quadrant / CE levels of the daily BISI (6pm open, Asia, Europe).
- 07:00-09:00: "a little bit of a pop here, but that's just running liquidity. That's not a trend." Range gyrating around its middle = consolidation. "When we're consolidating ... we're going to see big movement one directional at 9:30." Direction from the weekly view/seasonal tendency.
- Liquidity in a consolidation: "Forget the wicks ... Look at the bodies"; smooth bodies = the liquidity; the big wick is "where the damage is allowed to be done".
- **Validity by anchoring**: "this order block is anchored and tethered to an octant. So that means this order block is a valid order block if you know where the market is likely to go." "Why ... is this a fair value gap that's valid? Because ... candlestick three is tethered to that octant."
- Silver Bullet 10:00-11:00: "the first presented fair value gap is a SIBI" that price came back above = bullish inversion FVG; draw up to the SIBI low, then the smallest gap above.
- Missed trade: "moved too fast, too far"; he planned to short 6 contracts at an IFVG on the retrace; no chase.
- New day opening gap marked at 18:00.
- Jackson Hole week: "don't over leverage this week."
## Our interpretation / switches (all off)
- [off] daily_array_octant_levels as intraday reaction levels (see 021, 023)
- [off] 0700_0900_consolidation -> expect one-directional 09:30 move [new; pairs with 027 rule]
- [off] pd_array_valid_only_if_anchored_to_daily_octant/quadrant [new filter]
- [off] body_based_liquidity_in_consolidation (ignore wicks)
- Silver Bullet IFVG noted only (Silver Bullet settled off; don't re-propose)
