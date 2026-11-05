# 2026 SMC 076: Short for the stops, then long from a reclaimed bearish FVG to the event horizon below the 1h minor buy side (Mon Jun 22 2026, live with Caleb)
Full read (1.4k words). Clean caption. Frames laptop-only. Matches the "Monday ... with my son" trade reviewed in 075 (TradingView paper fills lagging in the first minutes; take-profit dragged by accident closed the whole position near event horizon). Short clip.
## Summary
ICT shorted at an octant (.375) near the open to take the sell side, got poor paper fills, covered inside a bearish FVG he expected to be reclaimed, and went long treating it as an inversion (bullish). Target: event horizon = halfway between the 1-hour minor buy-side pool and an old high. Fat-fingered exit filled close to event horizon; no re-entry. Then watched bodies hold above the CE of the newest small gap (wick-only tap) and called the position neutral.
## Rules in ICT's wording
- Short at "the .37 ... it's an octant" to take nearby sell side first, then reverse.
- **Bearish FVG reclaimed = IFVG long**: "This was a bearish fair value gap, so if it can trade above it, we should see that as a inversion fair value gap ... utilized as something as a discount sensitivity."
- **Event horizon target** = "the halfway point between the 1-hour minor buy side liquidity pool and then the old high"; take one off "just below" it; trail the stop "just underneath this inversion fair value gap."
- **No re-entry** after the stop/exit: "I'm not willing to enter again."
- **Opening range wick rule**: the last small gap should hold above its halfway point; "It can wick down below it. We don't want to see it leave a body down there. Otherwise, it makes it more difficult for the market to continue, at least for the remaining portion of the opening range" (first 30 minutes).
- At event horizon, bodies not laying on the halfway point yet = still neutral/undecided.
- Paper trading platforms are unreliable in the first minutes after the opening bell (fill-quality caveat).
## Our interpretation / switches (all off)
- [off] stop_hunt_then_reverse (quick octant short into nearby sell side, then long from the reclaimed FVG) [conflict check: B1 IFVG; 071 stop-and-reverse]
- [off] event_horizon_1h_pool_target [refines B1 event horizon]
- [off] opening_range_last_gap_body_filter (first 30 min: no body below the CE of the latest gap) [refines 073 wick CE filter]
- [off] open_fill_slippage_model (wider slippage for 09:30-09:35 entries in backtests) [new; execution realism]
