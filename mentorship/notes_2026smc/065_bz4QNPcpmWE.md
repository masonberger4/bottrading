# 2026 SMC 065: Low-probability opening range probe to the daily VI, London unicorn, no holding through CPI (Tuesday pre-market, CPI day)
Full read (2.1k words). Clean caption. Frames laptop-only. Tuesday of the 058 week (Monday was the Caleb lecture on the daily suspension block).
## Summary
Monday's lecture with Caleb was about "probing of a low probability opening range": how far can price drop? ICT chose the first relative equal lows to the left of 09:30 that sit inside the daily VI's low end; that was Monday's low (one tick away, 29,325.75). Overnight: Model 2022 sell-off, midnight open, London long via breaker + FVG (unicorn), market structure shift back toward Monday's ORG. Expectation: up into Monday's ORG CE (~29,881.5), its upper half, then the NWOG that did not fully close. No trading or holding through CPI/PPI.
## Rules in ICT's wording
- **Low-probability opening range probe**: "How far can it go down?" Look left from the 09:30 candle for the first relative equal lows that sit inside a HTF level (here the daily VI's low end). "It's the first one dropping down in from where we were at 9:30."
- Only the relevant side of a daily VI matters (the upper bound is "not pertinent" when price is already below it).
- "Unless you have a daily chart perspective, you don't have the highest degree of probability on your favor."
- Higher low of the day/session forms at a HTF key level (predominantly daily).
- Breaker: "High, lower low" (bearish) / "Low, high, lower low. Here's your breaker" (as stated; bullish breaker from a sweep).
- **Unicorn**: "it has a fair value gap at the same location that the breaker forms ... Super strong."
- OB change in state of delivery "is the open" of the OB candle.
- Model 2022 named for the overnight sell-off.
- NWOG that "didn't do a full gap closure ... That's why it was decidedly weak."
- Prior day's ORG: unfinished business = its CE, upper half, then the NWOG; if not today, on the next day's PPI.
- **News risk**: "squaring positions ahead of CPI is warranted ... managing risk impeccably does not entail trading CPI and PPI numbers." Don't hold open profit through the release.
## Our interpretation / switches (all off)
- [off] opening_range_probe_target = first relative equal lows left of 09:30 inside a daily array [new, backtestable]
- [off] unicorn_breaker_plus_fvg [conflict check: 2023/2024 unicorn definition]
- [off] ob_change_of_state_at_open_price [refines 059]
- [off] nwog_not_fully_closed_weakness [new]
- [off] flatten_before_cpi_ppi_nfp (no positions through 08:30 release) [conflict check: 062/064 traded news days after the release; refines A1 news rules]
