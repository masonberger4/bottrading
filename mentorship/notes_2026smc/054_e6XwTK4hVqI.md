# 2026 SMC 054: Caleb's ORG half-gap model and a short from last Wednesday's 1H BISI (Tuesday review)
Full read (1.9k words). Clean caption. Frames laptop-only. Same week as 055 (Wed).
## Summary
Tuesday opened ~450 handles above Monday's RTH settlement (premium ORG). ICT explains the simple first-hour model he teaches his son Caleb: aim for the ORG CE (half gap). ICT shorted at the 09:30 open as price ran into last Wednesday's noon 1H BISI (an old hourly swing low), targeting relative equal lows and then the ORG CE. He was stopped once, re-entered, took partials, and was stopped again on a run of relative equal highs ("Phil"). The ORG CE was never reached that day. Afterwards price displaced up, the first presented FVG became the reference, and price ran to the 1H BISI CE and its high, then chopped (leave it alone).
## Rules in ICT's wording
- **Caleb's ORG model (first hour)**: "aim for ... half gap relative to the regular trading hours opening range gap." Gap up above settlement = "start the session off looking for shorts. It's just that simple." It "doesn't require a whole lot of thought process."
- **Minimum gap filter**: if the CE is only ~15 handles from the open, "He doesn't trade." "You want to see a large enough gap to ferret out at least 20 handles, 30 handles"; "It must be enough of a range between the opening and consequent encroachment to warrant at least 30 to 40 handles."
- Entry trigger: price opens, runs up into a key PD array (1H BISI), then "overlaps that opening price and trades below it" = fill; stop above.
- 1H BISI from an old hourly swing low is the reference instead of "old lows broken become resistance. Cuz I'm not a support resistance trader."
- Premium arrays rejected: "leaving a body below the low" of the 1H BISI; the wick touched and stopped short.
- **No 9:30 candle FPFVG when gapped**: "He can't use the 9:30 candlestick if there's a gap there like this." The first presented FVG is the first one formed by displacement through a swing low after the open (in the direction of the CE draw).
- FPFVG polarity: "first utilization ... sell-side delivery. ... if it ever overcomes that to the upside, then it becomes a bullish inversion fair value gap."
- Choppy price around a level: "When it's doing this, you just got to leave it alone."
- Re-entry logic after a stop: if price runs the relative equal highs, re-enter short toward the relative equal lows.
- ORG defined here as "Monday's regular trading hours settlement price at 4:14 p.m. Eastern time to 9:30 a.m." (matches the 16:14 definition).
- NDOG noted ("we settled where we opened"); keep on the chart.
## Our interpretation / switches (all off)
- [off] org_half_gap_first_hour_bias: gap above settlement = shorts only for 09:30-10:30 toward ORG CE (gap below = longs) [refines A3 ORG]
- [off] org_min_open_to_ce_distance (20/30/40 handles; ~15 = no trade) [new filter, backtest 20 vs 30 vs 40]
- [off] org_entry_on_open_overlap_after_run_into_htf_array [new]
- [off] fpfvg_excludes_0930_candle_when_gapped [conflict check: 2023 FPFVG starting at 09:30]
- [off] fpfvg_inversion_flip (FPFVG overcome = IFVG opposite) [refines 053 first utilization]
