# 2026 SMC 046: Day-after-FOMC review, running between two daily suspension blocks (Thursday after FOMC, likely Jul 30 2026)
Full read (11.4k words). Clean caption, much commentary. Frames laptop-only. Date inferred: "overlapping yesterday's FOMC", NQ Sep futures near 28,431.
## Summary
Open sat in the empty space between two daily suspension blocks (a lower gray one traded into at FOMC, and a higher blue one). Price took buy side, then the relative equal lows at 09:33, then ran fast to the blue block. Every intraday PD array is validated by being anchored to an octant or quadrant of the daily blue block. The lecture gives the "time-price grid" (horizontal = octants, vertical = macro start and top of the hour), wick-grading rules, and IFVG first-utilization behavior.
## Rules in ICT's wording
- **Space between two daily inefficiencies**: "you can predict how price will move when it's moving from one area of inefficiency that's been traded back and forth" into the next. When price is in the open space between two daily arrays with no overlap, expect a "low resistance liquidity run": "big candles, speed". Example: 10 one-minute candles in a row, about 200 handles in 10 minutes.
- Sequence at open: opened above a short-term high (buy side taken first), then the sell side under the relative equal lows ("where the books tell you it's support"), then the run.
- **Wick grading after a stop hunt**: measure the wick from the candle body (close) to the wick low. "When it's bullish ... the upper half's going to support the narrative. We can wick down through it, but the body, and preferably not even touch the halfway point." Failing to reach the CE of the discount wick = bullish. "Engulfing" is irrelevant; he is focused on the low.
- Order block as body: "this body is the order block ... the algorithm is reaching into this opening price here down to the body." The longest wick "sets the tone for where the bodies should not trade below."
- **Efficient buy program** (overnight): "very short little candle ranges, but just keeps building higher ... Trying to short this is murder." Contrasted with a low-resistance liquidity run (big fast candles).
- **Validity rule**: grade the turns, OBs, breakers, FVGs and IFVGs "when it has to anchor to one of the octants or quadrant levels. That's how you know an ICT PD array is valid." For an FVG, "the number two candle that makes the inefficiency ... has to be touching an octant or a higher low of an inefficiency or whatever range you're measuring." The low of the daily suspension block also counts as a key level.
- Valid bullish OB: bodies must not violate its mean threshold. "Ideal valid ICT bullish order block within a bullish fair value gap anchored to the lower octant."
- **Macros**: 09:50-10:10 low at 10:10; 10:50-11:10 lowest candle formed "at the close of the macro"; last IFVG candle at 11:10 ("the close of my macro"). "You don't have to be in the macro. You just have to know what the macro should be putting in motion." "You don't have to take trades only in macro time." You can short an IFVG "just ahead of the macro".
- **Time-price grid**: "horizontal" = octant and quadrant levels of what you're grading (an inefficiency, ORG, NWOG, NDOG); "vertical" = macro start time and the top of the hour (dividing the macro). "Every single time we get to a octant or a quadrant level, you're looking for a PDA to form."
- **IFVG**: a failure plus a close outside a validated BISI "validates this as an inversion fair value gap. It's first utilization is that of buy side delivery." As a bearish IFVG, "the bodies need to stay out of the upper half. It can wick into it." Wicks may reach the high, "but no bodies are allowed to be buried in the upper half." When price crosses back over, "it reverts back to first utilization."
- Blended arrays: a bearish FVG crossed over becomes a bullish IFVG and overlaps a fresh BISI. Both anchored to the lower quadrant: "stops dead right there."
- Wick entry: "if it does that, and then we open up here, we trade down to the wick, that's a perfect buy. Anything in here to here is perfect." Stop below the wick CE.
- Fib levels used in grading: 0.125, 0.25, 0.5, 0.75, 0.875 (uppers only in one example). "There's no magic to the fib. All it does is just tells you where the reference points are going to be."
- Pre-session bias (posted on X) was to trade up into the lowest octant and then the upper half of the daily BISI. It did.
- Learning: learn one PD array as your entry model first, then learn all the others in time. Tape-read without trading first.
- Example precision: low 28,431.75 vs gap 28,432, one tick short = bullish.
## Our interpretation / switches (all off)
- [off] open_between_two_daily_arrays -> expect low-resistance run to the next array [new]
- [off] pd_array_valid_only_if_anchored_to_octant (candle 2 of FVG touches a graded level) [refines 044/045]
- [off] wick_ce_body_rule (body must not close past a wick's CE in trend direction; wicks allowed) [conflict check: 2023 CE rules]
- [off] ifvg_first_utilization_revert (IFVG undone -> original polarity) [new]
- [off] time_price_grid entries at macro start / top of hour [conflict check: 2023 macro list]
- [off] efficient_buy_program_no_fade filter [new]
