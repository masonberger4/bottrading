# 2026 SMC 022: Jackson Hole day 2 trade review, NQ (Friday, Jackson Hole week, Aug 2026)
Full read (4.2k words). Clean caption. Frames laptop-only. Playlist order is not chronological (023 = Fri Aug 28).
## Summary
Long trade in the 07:00-09:30 range on Fed-chair-speech day: inversion FVG entry after a sell-side run into Thursday's 09:55 discount wick; target relative equal highs; partials before the 10:00 speech. Then psychology: respect Jackson Hole week, don't trade Fridays after a good week, path from tape reading to demo to live.
## Rules in ICT's wording
- Range 07:00 to the 09:30 open: anchor fib on the highest high / lowest low of that window ("there's no form fitting ... outside the range").
- Jackson Hole week = "seek and destroy" conditions: "wherever you think a run's going to start, they'll come back and take that low out or that high out ... That right there that is the seek and destroy model ... the profile." Anticipate heavy volatility; "these are not the weeks that you want to over-leverage."
- Prior-day 09:55 discount wick: price traded into its upper half and "look where the body stopped" (bodies respected the wick's half).
- 09:30 displacement lower = SIBI; "I'm not treating that as first presented fair value gap. It's just simply ... an inefficiency that allows me to grade that as a potential inversion fair value gap if it can qualify it." Qualifies when price trades above it; then bodies supported at its half; buy.
- Low projection of the fib hit ("one or two ticks below it, that's fine") then expect run back to take out buy side into the inefficiency above; target relative equal highs.
- News at 10:00 (Fed chair speech): take partials before, "fund the trade", raise stop; "not worrying about trying to be perfect."
- Reclaimed bearish FVG drove price back to the prior-day 09:55 discount wick's half; then order block / change in state of delivery higher.
- Better management: when it was "failing right there at that midpoint", roll the stop to just below the CE of the longest wick.
- Trading days: "We trade every single Monday of non-farm payroll week." Advanced students can trade every day including report days and high resistance liquidity run conditions; beginners should not. After a profitable week, Friday can be skipped.
- Learning path: log observations and screenshot daily -> backtesting campaign for a couple of months -> demo minimum 3 months (2 if really good) -> live with small leverage.
## Our interpretation / switches (all off)
- [off] range_0700_0930_fib_projection (low projection as reversal level)
- [off] jackson_hole_week_seek_and_destroy flag (expect double-sided runs; reduce size / skip for beginners) [new event filter]
- [off] prior_day_0955_discount_wick_half as support (extends L22-2025 wick grading)
- [off] 0930_displacement_fvg_as_ifvg_candidate (not FPFVG)
- [off] partials_before_1000_news (news-time management)
- [off] stop_to_longest_wick_ce_when_failing_at_midpoint
- [principle] skip Friday after profitable week (beginner/management, not backtestable as edge)
