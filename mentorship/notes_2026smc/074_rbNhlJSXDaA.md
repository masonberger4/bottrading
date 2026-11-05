# 2026 SMC 074: Unrealized dealing range projection (1.25 of the power-three open-to-low, body vs VI), wick precedence over the OB, SMT via the rollover toggle (weekend review, late June 2026)
Full read (11.5k words). Clean caption. Frames laptop-only. Weekend review of a week whose Wednesday saw DXY stall and EUR/GBP shorts hit target; refers back to "June 7th, 2026 ... this month", so a June 2026 weekend (exact week not pinned; inferred Sat Jun 13-27). Second half (~40%) is channel/persona talk, not for the engine. Daily-chart examples are DXY, EURUSD, GBPUSD, gold, silver, crude, BTC; index part is ES/NQ daily.
## Summary
Teaching: how ICT projected the DXY daily high to the tick. On the day the displacement started (power three), take the range from that day's opening price to its low, project 1.25 = "low hanging fruit objective"; repeat using the close of the prior candle (the volume imbalance edge, i.e. the body) = "extreme". The CE between the two projections was the high (101.80). He calls this an "unrealized" or "implied dealing range". Then: a VI created by sell-side delivery that later gets traded through becomes a balanced price range read as an inversion FVG; on ES daily a huge wick next to the largest down-close candle takes precedence over the OB; NQ daily suspension block (one candle between two VIs) treated as an IFVG; close below the wick CE needed before targeting 28,517 relative equal lows. SMT spotted by toggling TradingView's contract-rollover adjustment.
## Rules in ICT's wording
- **Unrealized / implied dealing range**: "when this candlestick starts and opens higher than this one, it trades down and starts to rally up ... from this candlestick's open all the way up to this high [not yet formed]. That's an unrealized dealing range."
- **1.25 projection, two anchors**: "plot that fib from the low of this candlestick body, which is the opening, and drag it on up to the low of this candlestick ... add a level ... 1.25 ... that's the low hanging fruit objective." Then "we have a volume imbalance ... use the point at which the day closed. So, the body tells you the story, the wicks do the damage" = the extreme. Target = "consequent encroachment of those two levels" (hit 101.80 to the tick).
- "There are two distinct approaches to how I teach ... an extreme and then ... the low hanging fruit objective. So in between that's where the story is going to be the clearest."
- **Event horizon close**: closing above the CE between two old highs "gives confidence that we're likely to draw to this level. It's not a guarantee."
- **One down-close candle in a sustained run** + target nearby + Wednesday = "reasonable for it to slow down"; "we're on hump day, Wednesday, and we could see a midweek retracement or reversal."
- **Volume imbalance definitions**: VI = next open beyond prior close with no bodies touching; FVG including VI goes "right down to the candlestick's close" not the wick.
- **VI becomes BPR/IFVG**: a VI created by sell-side delivery, later traded up through and left = balanced price range used "through the lens of a fair value gap"; traded above it = inversion. A bullish-delivered VI traded down through = bearish (resistance). Caveat: "it's more likely to fail."
- **Wicks take precedence over the OB**: next to the largest down-close candle (CISD) "we have this enormous wick ... whenever you have that, just like a gap, wicks take precedence ... Because they're balanced price ranges." Need a close below its CE before the target is high probability.
- **Premium vs discount wick** depends on where market price is relative to it.
- **Suspension block** = "one candlestick is being suspended between ... two volume imbalances"; treat as an IFVG; bodies staying in the middle then failing to reach CE = weakness. [B1]
- **SMT via contract rollover**: toggling the adjustment shows whether ES made a higher high vs YM/NQ; "you can see SMT divergence."
- "Knowing when not to do something is the most important thing ... Control your losses and your wins don't have to be stellar."
- Study path: 2022 mentorship, then 2016-2017 paid mentorship.
## Our interpretation / switches (all off)
- [off] power3_open_to_low_1p25_projection (two anchors: day open vs prior close/VI edge; target = CE of both) [new; directly backtestable on daily and intraday]
- [off] event_horizon_close_confirms_draw [refines B1 event horizon]
- [off] midweek_reversal_watch (Wed after a one-down-close run into target: take profit) [conflict check: 2023 weekly profiles]
- [off] vi_to_bpr_inversion [refines B1 IFVG]
- [off] wick_precedence_over_ob (large adjacent wick's CE governs over the OB) [new; conflict check: 2023 OB priority]
- [off] smt_from_rollover_adjusted_highs [research; conflict check: 2023 SMT]
