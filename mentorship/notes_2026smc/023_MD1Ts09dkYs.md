# 2026 SMC 023: Jackson Hole day 1 long, explained (review recorded Fri Aug 28 2026, 07:50)
Full read (10.2k words). Clean caption. Frames laptop-only. (So 022 is a later Jackson Hole review; ICT says "day two" in 022 and 023 is recorded the morning of day 2.)
## Summary
Detailed breakdown of Thursday's long: daily BISI (with VI at its low) as the higher-timeframe draw, upper octant as intraday support, seek-and-destroy megaphone sweeps, entry below relative equal lows, wick CE / IFVG confirmations, pyramiding rule at equilibrium, stop management, order-block stop lesson, and an afternoon replay (macros 14:50-15:10, 15:15-15:45, MOC last 10 minutes).
## Rules in ICT's wording
- Suspension block (named here; "stop block" in 021's translation) = SIBI/BISI "has a volume imbalance at the high and the low of it." A BISI with VI only at the low "is not a suspension block ... just simple buy side imbalance sell side inefficiency".
- When price fails to reach an obvious lower objective, "the market is undergoing a return back to premium" -> look higher. Draw ladder: VI high -> wick CE -> gap -> remaining portion of the SIBI.
- "Day one of Jackson Hole Symposium is the highest likelihood of a seek and destroy day" (can also be day two). Profile: up, down, up, sweeping each side, expanding "megaphone"; trade nimbly.
- Octant levels inside a daily array: 0, 0.125 (octant), 0.25 (quadrant), 0.375, 0.5 (CE), ... ; first drop stopped at the upper octant 29,451 ("it's not random"); bodies did not close at/below it -> key level.
- Entry: below relative equal lows is "the minimum criteria for trading and buying sell side liquidity"; ideally he waits for a close below the midpoint of the leg to the prior Friday's FPFVG high; when the candle couldn't close below that midpoint he bought immediately. Limit for first target one tick below the high.
- Confirmations long: close above the CE of the premium wick of the low ("false break below the low"), then close above the inversion FVG; once confirmed so close to the stop run, "there should be no reason for the price to trade back down."
- Stop rolled to 29,501.75 below the wick; went within one tick. If stopped, "I would have went back in immediately ... the full position back on again." Futures = same high/low for everyone, tight stops OK; forex brokers widen spreads.
- **Pyramiding rule**: "if I'm long it needs to be at consequent encroachment or equilibrium of the range that you're trading in or lower. If I'm shorting ... at equilibrium or higher. ... once it goes beyond equilibrium, I'm not permitted to add more." Range = entry low to target (terminus); widens when the target is extended.
- Wick rule: when bullish, "the upper half of that wick should support price ... the body should stay in that section"; event horizon = midpoint between the IFVG high and the wick CE. Wick measured from candle open to the low for the next level.
- Position: 6 initial + 4 pyramid = 10; 4 off just above the first high; plan 5 of the remaining 6 at the next high, 1 runner to the next target; exit at the high of the green gap.
- Lesson: "I should have put my stop loss right at this candlestick's open" (last two up-close candles = order block; don't hold a stop below the change in state of delivery).
- In a price run near the target, "you rarely get the gaps fill in before it goes to target"; upper half of the inefficiency should stay unfilled.
- "Cork": a small square block sloping slightly up (not a down-sloping bull flag), pops higher.
- Afternoon macros: "the 2:50 to 3:10 macro for final hour", then 3:15 through 3:45, then last 10 minutes = market on close (MOC) "supercharge".
- Daily bearish array: bodies can't reach CE (respect lower half) = bearish confirmation; big runs come off key daily PD arrays.
## Our interpretation / switches (all off)
- [off] suspension_block definition (VI at both ends) [new name; compare 2023 definitions]
- [off] failed_lower_objective -> return_to_premium bias flip
- [off] jackson_hole_day1_seek_and_destroy (event filter; see 022)
- [off] octant_levels inside daily arrays (see 021)
- [off] buy_below_relative_equal_lows_minimum_criterion; wait_for_close_below_leg_midpoint
- [off] pyramid_only_at_or_beyond_equilibrium_of_entry_to_target (2023 conflict check: rulebook scaling rules)
- [off] reentry_full_size_after_one_tick_stopout (not recommended for backtest)
- [off] stop_at_order_block_open (last up-close candles' open) after displacement
- [off] macros_1450_1510_1515_1545_MOC_last10 [conflict check: 2023 PM macro times 13:10-13:40, 15:15-15:45]
