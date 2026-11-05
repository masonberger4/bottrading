# 2026 SMC 084: Grade the range between two sell-side pools; short an IFVG that sits on a gradient level after the 09:50-10:10 macro; low resistance vs sticky conditions (undated 2026, pre-open review)
Full read (2.9k words). Clean caption. Frames laptop-only. Pre-open review of a short taken the previous trading day (09:50-10:10 macro), after "yesterday in the live stream in the afternoon"; NQ pools 30,055.75 / 29,886 and target 29,818. Date not pinned (he says he is 53; likely June-July 2026).
## Summary
After a blow-off move, ICT profiled a two-stage delivery: consolidate in the PM, then sell off. Delivery was deferred. He graded the range between two sell-side pools (anchored exactly to their lows), wanted shorts above its equilibrium, let 07:00-10:00 "tomfoolery" settle, then after a 10:00 stop hunt shorted a BISI-turned-IFVG that sat on the upper quadrant of that graded range. Confirmation: breaking the CE between the two pools. Target filled one tick below the lower objective.
## Rules in ICT's wording
- **Grade between two liquidity pools**: "this low and this low is specifically anchored to its lows. Because it's using two pools of liquidity to grade that range." Short "in the premium side of that range that's divided by ... equilibrium."
- **Let the early session settle**: "whatever tomfoolery that was going to be done between 7:00 and 10:00 ... I wanted to let that kind of like settle."
- **Macro**: run "out of an algorithmic macro, which is 9:50 to 10:10"; a 10:00 failed high = stop hunt.
- **PD array selection**: "I'm going to look at a candlestick that just so happens to lay over top of one of these gradient levels ... upper quadrant, it's a buy-side imbalance sell-side inefficiency ... could be utilized as an inversion fair value gap ... What makes this one so good is because it's anchored to a gradient level." "The candlestick has to be laying on a gradient level. That's what validates." [same as 073 anchored FVG]
- **Confirmation**: "speed and distance and velocity. Once we get through the halfway point ... between these two pools of liquidity ... There's your signal."
- **Deferred delivery**: two-stage profile (drop, consolidate, drop) can be "prolonged" and come back up first.
- **Low resistance liquidity run conditions** = runs that leave small inefficiencies with shallow retracements ("imbalance, imbalance, imbalance"). Sticky = one inefficiency sharing many candles: "That's not an environment you want to be a part of." If a trade turns sticky: dial back risk, don't add, take profit earlier.
## Our interpretation / switches (all off)
- [off] grade_between_two_pools (dealing range = two same-side liquidity pools; trade the premium/discount half) [new; backtestable]
- [off] no_entries_0700_1000_settle (wait for the 09:50-10:10 macro) [new; conflict check: 2023 NY AM kill zone]
- [off] fvg_valid_only_if_first_presented_or_anchored [same as 073]
- [off] eq_break_confirmation (break of the pools' CE confirms the run) [new]
- [off] sticky_market_filter (count candles overlapping one FVG; skip/de-risk above N) [new; backtestable LRLR proxy, refines B2 HRLR/LRLR]
