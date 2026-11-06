# 2024 Mentorship Lecture 19 (i3olkndPmEE): PM session, previous three days' highs/lows as liquidity, dynamic trailed partial on one contract, intraday-low vs daily-low partial rules, speed past the midpoint of the dealing range, first FVG rule re-stated (09:31 earliest; today 09:35), 14:50 macro
Live Wed Aug 28 2024, ~13:30-15:00 ET, NQ, 1m + 15s. ~1h32m. Captions only.
Source tier: 2024 Mentorship. No trade on stream; teaching on the morning (calls made in Tanja Trades' stream chat) and a live observation of the 14:50 macro. Nvidia earnings after the close.

## Summary
Price traded around Tuesday's daily low. ICT teaches that the previous three days' highs and lows are always reference points (the algorithm refers back to them even after their stops are hit; new stops get trailed under them). Partial management: when targeting a previous daily low, don't take the first partial right below it; wait for the first short-term low to form after the break, then partial below that, or use a dynamic trailed partial (one contract trailed one tick above each prior 1m candle high). Once price gets past the midpoint of the dealing range toward the target low, delivery should speed up. Morning: discount ORG; the first FVG formed at 09:35 (none at 09:31-09:34), the 08:15 FVG was called as an inversion; Judas up to minor buy-side, then the opening range gap low + first FVG rejected and price ran to the Aug 27 and Aug 16 NDOGs with a breakaway gap. 14:50 macro rallied to Tuesday's low.

## Rules
- PRIOR-DAY LIQUIDITY: keep the last three days' highs and lows on the chart; the algorithm refers back to them even if already traded through (stops are re-placed/trailed); they are draws and turtle soup catalysts; work on daily/weekly/monthly too ~8:00-14:00, ~40:00
- PARTIALS when targeting a PREVIOUS DAY LOW (bearish): do not take the first partial right below it on the first pierce; wait for the first short-term low after the break, let it retrace, then partial below that short-term low ~18:00-20:00
  - Do NOT use this rule for intraday lows (inside today's range) ~18:00
  - For a break of today's (intraday) low: partial at a one-quadrant (25%) extension of high-to-low of the range ~26:00-27:00
  - Graduated: step 1 exit just below the low; step 2 the dynamic trailed partial ~31:00-32:00
- DYNAMIC TRAILED PARTIAL: with 2+ contracts, put a buy stop on ONE contract one tick above the high of each prior down-close imbalance candle (1m chart only, never sub-1m), trailing it down candle by candle; the core position stays on ~20:00-22:00, ~51:00-57:00
  - Example: trailed out at 302.75 vs the low 278.50 (NQ 19,3xx) ~56:00
  - Trailing to the prior candle high is for intraday; trailing by candle structure (wider) is for swing trades ~53:00
- Track intraday highs/lows dynamically: each new low of the day is the next reference; study after 17:00 ~33:00-35:00
- Stop hunt above relative equal highs that then spends time there = fake bull flag (CC 2016-17) ~36:00
- Several models can stack in one move (OTE 79/62, 2022 model, Silver Bullet / IOFED); later model entries = pyramid adds ~38:00-39:00
- SPEED INTO A LIQUIDITY POOL: once price is past the 50% of the range from the last high to the target low, it should move quickly, each candle lower, accelerating into and through the low (they won't let stops be pulled) ~41:00-48:00
  - Heaviness (no higher candle highs) = bearish; lightness = bullish ~45:00, ~48:00
- BREAKAWAY GAP: a gap left open by the first run below the first low after a market structure shift (redistribution/reaccumulation) = expect speed and distance; better if it stays unfilled but it can fill and still work ~43:30-45:00, ~1:15-1:16
- FIRST PRESENTATION FVG: middle (imbalance) candle can be 09:31 at the earliest, because the 09:30 candle does not exist on the RTH session chart; today the first was 09:35 ~1:00-1:03
- ORG: discount gap (open below prior 16:14 settlement); here the ORG mid overlapped the Aug 27 NDOG by two ticks; half then full closure, then a sweep of buy-side ~1:07-1:09
  - Short at the inversion FVG / ORG low (= 09:30 open) + first FVG confluence; stop one tick above the high of the wick that forms; "the next candle should only reach about halfway of that wick" ~1:11-1:13
- 14:50-15:10 macro ("2:50 algorithm"): start of a run at 14:50 on the dot; 15s breakaway gap; IOFED into the gap; target was Tuesday's low ~1:19-1:29
  - OB mean threshold (half) is the most sensitive; bodies respect, wicks do the damage ~1:21, ~1:26
- Dealing range: from the relevant high to low; don't just target the obvious level ~1:23

## Risk / Process [beginner]
- Study after 17:00: what catalysts led to the move ~35:00
- Journal positively; don't beat yourself up over exits ~33:00, ~54:00
- Futures symbols: H/M/U/Z (Mar/Jun/Sep/Dec), expiry third Friday of the month; rollover before then ~29:00-31:00

## Trade examples
- 2024-08-28 AM (called in another stream's chat): 08:15 FVG called as an inversion, minor buy-side above relative equal highs as the Judas target; first FVG 09:35; ORG low / first FVG rejection; runs to the Aug 27 and Aug 16 NDOGs; breakaway gap.
- 2024-08-28 PM: around Tuesday's daily low; trailed partial example 302.75 vs low 278.50; 14:50 macro rally back to Tuesday's low.

## Definitions
- Dynamic trailed partial: one contract on a stop trailed above each prior 1m candle high.
- Breakaway gap: the gap left by the first displacement from a consolidation (start of the run).
- Dealing range: the high-to-low range being worked between two liquidity points.

## Open questions / conflict checks
- [conflict check] Partial rule for previous-day lows (wait for the next short-term low) vs rulebook partial rules and L13 "partial at every broken high" (PARTIAL-TRIGGER card). Switch `pdl_partial_after_next_swing` default off.
- [new] `dynamic_trailed_partial_1m` (one contract trailed above each prior 1m candle high); default off. Exit test.
- [new] `prior_3day_hl_liquidity`; default off (with L18 prior_day_thu_fri_hl_draws).
- [new] `speed_past_mid_range` (expect acceleration past 50% of the dealing range; e.g. hold through); study.
- [conflict check] 14:50-15:10 macro vs owner #1 last-hour window 15:00-15:50 (conflict 5 LAST-HOUR).
