# 2026 SMC 095: Live MNQ short inside the suspension block after a failed run at the all-time high; scaling out as price "stutters"; market out when a limit is touched but not filled (likely the Wednesday after 096/097; mid-April 2026; MNQ ATH region 26,901.75, targets 26,830 and 26,805)
Full read (5.2k words). Clean caption ("consequent coaching/curshment/corrosion" = CE, "Siby/CIVI" = SIBI). Frames laptop-only. Live from mid-trade, no intro or outro. Monday's and Tuesday's RTH ORGs on the chart.
## Summary
Price ran from 07:45 to 26,901.75, just short of the all-time high, without taking sell-side first. ICT shorted inside the last suspension block (a bullish up-close candle), adding at its high (averaging about one quarter into it), targeting the relative equal lows at 26,830 and 26,805. He layered limit exits, took two partials, then watched price stall inside a SIBI and around the CE of a premium wick while defending 26,804. He took profit manually when a limit was touched but not filled, kept a runner "for the culture", and was stopped on it.
## Rules in ICT's wording
- **Fade the failed ATH run**: "they ran higher and they got real close to all-time high and failed to go there. So now everybody's holding on to it looking for that bull flag"; "they'll leave all-time highs there intact until they pick out sell-side." [refines B3 sell stop after a refused draw]
- **Short inside the suspension block**: "selling short inside of that last suspension block. It's a bullish up close candle ... It can trade to the high of that suspension block again. But I don't want to see any bodies outside of it. If it looks like it's going to do that, I'll just collapse the trade." [refines B1/B3 suspension block]
- **Bodies below the premium wick's CE**: "The body's got to stay below that wick, consequent encroachment"; "I don't want to see it trade above the wick high ... I'll have to bail on half the position." [B3 wick CE]
- **Too many candles inside a SIBI**: "It's already spending too many candles inside that SIBI ... that's indicative of wanting to go back to at least consequent encroachment of the [SIBI] or ... [the] inversion fair value gap just above us." "Too deep in the ... curve to add anything."
- **Stuttering = expect a stop**: "it's printing slightly lower lows, slightly lower lows, and they're defending 26,804s"; "See how it's stuttering and doesn't want to go lower? Yeah, something's up."
- **Limit touched, not filled -> market out**: "if I have a limit order and I'm near the end of a price run ... and I see my order not get filled ... it's the best scenario just to simply take a market order and peel it off." "Nobody's ever wrong by taking profits."
- **Last line of defense**: "the high of that Monday regular trading hours opening range gap ... If it starts putting a body above that, I'm going to look to peel something else off." Monday's ORG CE was the next focus. [refines 096 three ORGs]
- **2026 volatility**: "this year we're seeing the actual birth of them ... 100-handle candles come out of nowhere. Trump tweeting." Keep the stop high: "I don't want to lower my stop yet because I don't trust the ... order block."
- Model named: "a nice little market maker sell model. Selling short at the smart money reversal."
## Our interpretation / switches (all off)
- [off] failed_ath_run_short (run toward the ATH that stops short with untaken sell-side below = short) [new; backtestable]
- [off] suspension_block_short_entry (enter inside the last up-close suspension block; exit if a body closes outside it) [refines B1/B3]
- [off] sibi_dwell_scale_out (more than N candles inside a SIBI near the target = scale out) [new; backtestable, needs N]
- [off] touched_unfilled_limit_market_exit (if price trades to the limit but it doesn't fill near the target, exit that part at market) [new; backtest assumption about fills]
- [off] premium_wick_high_half_exit (body/trade above the premium wick high = cut half) [new]
- Not for the engine: "Phil" manipulation narrative, X/recording remarks.
