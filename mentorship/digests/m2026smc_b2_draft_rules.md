# 2026 ICT Smart Money Concept Lectures, batch 2 (videos 054-060, 062-070): DRAFT rules for Mase's review

**Status: DRAFT. Nothing here is wired into the engine and nothing has been backtested.**
Built 2026-11-05 from the per-lecture notes in `mentorship/notes_2026smc/` (054-070). Same structure and tags as batch 1 (`m2026smc_draft_rules.md`): A rules by topic, C conflicts, D switches, E questions. Captions only; frames are on the laptop.

## How to read this
- **Source tier: 2023 Mentorship wins on every conflict.** This batch sits in the same non-2023 tier as batch 1. Experienced-trader version stays the default; beginner rules are switches only.
- Tags: **[new]**, **[refines]**, **[conflict: X]**, **[conflict check]** as in batch 1. "B1 A3" = batch 1 digest section A3.
- All switches default OFF. Times are New York local.
- Deferred per Mase (2026-11-03): conflict and priority questions wait for one full review. Nothing here was asked.

## Coverage
- **Read in full and noted (16):** 054-060, 062-070. **Skipped:** 061 (no captions; whisper pending).
- **Caption quality:** all usable. 055 and 056 have mis-hearings ("balance sell sign efficiency" = BISI, "cibby" = SIBI, "octin" = octant, "consequent corrosion" = CE). 057 ends mid-sentence.
- **Order (playlist is not chronological).** Three blocks:
  - Early July 2026 (post-July 4 holiday): 070 (Mon Jul 6) > 069 (Tue Jul 7 AM) > 068 (Tue Jul 7 review).
  - A CPI/PPI week with the Fed chair at 10:00 Tue and Wed: 066 (Mon, with Caleb) > 065 (Tue pre-market) > 064 (Tue live) > 063 (Wed pre-market) > 062 (Wed review) > 060 (Thu) > 059, 058 (Fri).
  - The following no-news week: 057 (Mon pre-market) > 056 (Mon review) > 054 (Tue) > 055 (Wed live, with Caleb).
  - 067 is a Wednesday from an unidentified week.
- **Not for the engine:** 057's crude oil, gold, silver and BTC opinions; persona and critic talk in 056, 058, 062; Silver Bullet mention in 057 (noted only; project rule).

## Part A. Rules by topic (DRAFT)

### A1. ORG half-gap model (Caleb's model) and the opening
- DRAFT: **First-hour bias from the ORG.** "Where did we gap? Did we gap higher or gap lower? Find the mid gap. There's your target." Gap above settlement = shorts only from 09:30 to 10:30/11:00 toward the ORG CE; gap below = longs. "It doesn't require a whole lot of thought process." (054, 055) [refines B1 A3 ORG; directly backtestable]
- DRAFT: **Minimum distance filter.** No trade when the open-to-CE distance is about 15 handles; want "at least 20 handles, 30 handles" / "30 to 40 handles". (054) [new]
- DRAFT: **Entry trigger.** Price runs into a HTF PD array after the open, then "overlaps that opening price and trades below it" = fill, stop above. (054) [new]
- DRAFT: **ORG CE fib routine.** Anchor at the prior settlement, drag to ~09:32, show all levels; at 09:30 move the low anchor to the opening price. ORG = 16:14 RTH last print to 09:30. 70% "about 10:00", but 10:55 also happened (056) and some days it never came (054, 055). (055, 056, 066, 067) [refines B1 A3; adds hit-time tracking]
- DRAFT: **No 09:30 candle FPFVG on gap days.** "He can't use the 9:30 candlestick if there's a gap there like this." The FPFVG is the first FVG made by displacement through a swing in the direction of the CE draw. (054) [conflict check: B1 A3 "FPFVG uses the 09:31 middle candle"]
- DRAFT: **Judas swing at 09:30.** A straight run from the open into a gap-up "is going to run out of steam somewhere"; fade it at the HTF array (056, 060). Up-to-go-down from 09:30 into a gap's CE, then sell side (068, 069). [conflict check: 2023 Judas timing]
- DRAFT: **Abort rule.** If 09:30 runs the opposing relative equal highs/inefficiency first, skip AM shorts and wait for the PM session (069). Time stop 10:10 for opening-range probes (066). [new]
- DRAFT: **Low-probability opening range probe.** "How far can it go down?" Use the first relative equal lows to the left of 09:30 that sit inside a daily array (here the daily VI low end). (065) [new]
- DRAFT: **No bias until 10:00** when the open gives nothing obvious (057); no bias when the open sits at the 50% of the dealing range (070). [new]
- DRAFT: Prior-day ORG grades are next-day levels: buy side taken at its lower quadrant, run to its CE (064); unfinished business = its CE, upper half, then the NWOG (065). [refines B1 A3 ORG CE ledger]

### A2. Daily framing, wicks and the weekly range
- DRAFT: **High probability needs a daily or weekly anchor.** "Unless you have a daily chart perspective, you don't have the highest degree of probability." "If you can't structure or frame an idea from the daily chart, then you need to probably sit on your hands." (060, 065, 068) [refines 2023 HTF draw]
- DRAFT: **Daily wick CE flips.** A meaningful run below a discount wick's CE makes it a premium array (056). A daily close below a wick's CE = "We don't want any bodies above that wick's halfway point"; failing even to touch it = "weak ... bearish" (058). A daily close above a discount wick CE "would warrant likely higher prices" (066). If there is no inefficiency to the left, "you have to grade that" wick (067). [refines B1 A5 wick-as-gap]
- DRAFT: **Daily boundaries.** The open of the last up-close candle (OB) and a discount wick frame the day; "Only until we close below consequent encroachment, do we then refer back to this area and only use the lower half." (068) [new]
- DRAFT: Daily close below a volume imbalance = lower prices; invalidated only by taking out the prior day's open (060). [new]
- DRAFT: **Weekly premium draw = NWOG** inside the premium half of a daily suspension block; the weekly discount draw = daily relative equal lows. The NWOG is rejected when a day "can't overcome the new week opening gap and it leaves the body lower than where the open was." (058, 062) [new]
- DRAFT: An NWOG that "didn't do a full gap closure" is weak (065). [new]
- DRAFT: **TGIF as a close forecast.** From the week's high to Friday's low, after Friday pierces and works back above the low, price retraces "20 to the 30% of the weekly range"; "You're forecasting where the close of the week is going to be." Also seen as last week's range in 057. (058) [refines B1 A4 TGIF]
- DRAFT: **Friday priority.** If the weekly draw is unmet, ignore nearby opposite liquidity: "It only has today, Friday." The 07:00 pre-market start and the 09:30 Judas swing are the "rocket fuel". (058, 059) [new]
- DRAFT: **Midnight open as fulcrum.** Bearish power three goes above the midnight open, then lower. If London highs are well below the midnight open while the daily objective is unmet, "don't hold with the expectation that we're going to go all the way back up to the opening price"; target the relative equal highs. 07:00 "is when it accelerates." (059) [refines 2023 power of three]
- DRAFT: **ETH vs RTH.** "Whatever electronic trading hours does, regular trading hours will tend to overlap that and redeliver those price runs." The settlement-to-open gap with no RTH prints is a "liquidity void"; "I place more emphasis on regular trading hours." (058, 066) [new research tag]
- DRAFT: **15m bellwether and lay of the land.** The 15m frames all day trading. Lay of the land = dealing range high and low, minor buy side and minor sell side, and the two extreme inefficiencies. (068, 069, 070) [conflict check: 2023 timeframe stack; see B1 A9]

### A3. Day-of-week, news and holiday filters
- DRAFT: **CPI/PPI + Fed week profile.** Mon-Wed are hard; "after Wednesday's PM session, things should get really easy ... low resistance liquidity run conditions" Thu-Fri to the weekly draw. On Tue/Wed trade the PM session, not the morning. (058, 066) [refines B1 A7; conflict check: 2023 day-of-week]
- DRAFT: **News-day plan.** "Nobody knows" the release direction. Build two if/then parameters; whichever array is hit first acts as counterparty to the other. A relative equal low formed at the 08:30 release is a high-probability target. (062, 063) [new]
- DRAFT: **Flatten before CPI/PPI/NFP.** "Managing risk impeccably does not entail trading CPI and PPI numbers"; don't hold open profit through the release. (065) [conflict check: 062 and 064 traded after the release; B1 A7 "skip 08:30/08:31"]
- DRAFT: **Fed chair speaking at 10:00.** No trades until 10:00; wider stops ("don't strangle your position"). (064) [new]
- DRAFT: **Mondays.** New traders "try not to trade on Mondays", except NFP week ("always trading Monday"). Mondays with no news before big Tue/Wed news are where new traders "fail most." (066) [conflict check: 2023 day-of-week; new-trader switch only]
- DRAFT: **Weekend bank holiday.** "If Saturday or Sunday has a US holiday that would usually close the banks down, then Monday is a no touch day." Normal delivery returns Tue/Wed. (070) [new]
- DRAFT: **Summer doldrums.** July-August: dial back participation, take only one-directional setups. (070) [new seasonal filter]
- DRAFT: **Stop after the target.** Weekly draw hit on Friday = done for the week (058); target hit in the first half of the week = done (068); daily target hit = done for the day (059). [refines B1 A4 "weekly range fulfilled"]

### A4. Order flow: bodies, wicks and conditions
- DRAFT: **Bodies tell the story.** "The wicks do the damage, but the bodies tell you the real story ... That open and close is the most important two prices you're ever going to have." (056, 060, 068) [refines B1 A5]
- DRAFT: **Continuation vs reversal at a target low.** Bodies buried below the low = confirmation; only wicks below with bodies at/above = retracement or reversal. "The bodies are showing the narrative" even when a level is taken wick to wick. (055, 066, 070) [refines 2023 body rule]
- DRAFT: **Three-failure short signature.** Bodies can't touch the range CE; bodies can't lay on the 0.375 octant; the wick can't touch the upper quadrant; plus a buy-side run = "turtle soup false breakout run on engineered liquidity." (056) [new, backtestable]
- DRAFT: **Hangman.** Bodies sit just past the CE (suggesting continuation), then a wick pokes further and price rejects back = "It's done. It's over." Not a doji. (060) [new]
- DRAFT: **Five-candle rule inside an inefficiency.** "You want to have one, two at most. Three, the probability start to shift lower ... No more than five candles." A market in a hurry enters the gap with one candle and leaves no body. (066, 069) [new, backtestable]
- DRAFT: **Single-candle breach.** A run below a low in one candle bodes well for the next target; several candles do not. (064) [new]
- DRAFT: **High vs low resistance liquidity runs.** HRLR = "Lots of price action shared in a few number of candlesticks", very manipulated: sideline it. LRLR = "one or two candles in a range ... stretching out like taffy": engage. LRLR comes from blending calendar, structure, day of week, time of day and obvious daily/4H/1H draws. (055) [conflict check: 2023 HRLR/LRLR; needs a numeric definition]
- DRAFT: **Chain of custody.** Price moves from one PD array to the next; "As long as it's affording lower prices by not having a close above that, lower prices are in order." A wick through needs a close beyond ("crossroads") or the bias flips. (063) [new framing; B1 A9 had listed it as not extractable]
- DRAFT: **Suspect liquidity.** Relative equal highs against heavy HTF flow are "suspect", not a draw (060). New relative equal lows framed by an old pool are suspect and likely drawn to (068). Smooth highs/lows are targets (057, 066). [refines B1 A4]
- DRAFT: **Staging.** A news run making successive higher highs builds buy stops that become counterparty for shorts (062). Toothpick: a large structure supported by one candle is weak; expect a revisit (its CE as an exit). (062, 063) [new]
- DRAFT: Don't sell in a deep discount (or buy in a deep premium): an FVG short at the daily low after a straight drop "goes against what I taught in the very first month of ... 2016 private mentorship." (066) [conflict check: 2016 M01]
- DRAFT: Public sentiment (live-stream chats) is usually wrong (060). [not for the engine]

### A5. PD arrays and definitions
- DRAFT: **First utilization.** "First utilization is when a PD array forms." An FPFVG that is overcome becomes an IFVG the other way (054). After a failed bearish FPFVG, let price take the opposing short-term high and close back below; "that resets first utilization ... a turtle soup" (060). If the bearish read fails, the array "changes its characteristic back to its first utilization" (reclaimed FVG) (063). An array formed by buy-side delivery reverses its role in a bearish market (057, 067). [refines B1 A5 IFVG]
- DRAFT: **Suspension block.** VI at the high and the low (057, 058, 068). Daily suspension block halves: premium half = sell zone when bearish (058). Failed daily suspension block: its lower quadrant was the 09:30 Judas high (060). It stops price at an octant "to the tick" (062). Hybrid VI + suspension block (057). [refines B1 A5]
- DRAFT: **Shadow** = a blend of two overlapping inefficiencies; grade the blended range (060). [new]
- DRAFT: **Breaker.** "High, low, higher high"; valid only if bodies don't trade outside it (056). Anchor on the body that goes lowest, not the wick (067). Unicorn = breaker plus an FVG at the same location, "Super strong" (065, 067). [refines B1 A5 breaker; conflict check: 2023/2024 unicorn]
- DRAFT: **Order block.** "The last up close candle, if it's the largest one, consecutive candles make one order block" (067). Change in state of delivery = the open; no close beyond required (059, 065, 068). [conflict check: 2023 OB definition]
- DRAFT: **NDOG** = 17:00 settlement to 18:00 restart. A straight run from 09:30 into the NDOG that fails to leave a body at or above its CE = bearish; its low not reached = bearish. The NDOG can sit inside the ORG. (067) [refines B1 A3 NDOG]
- DRAFT: **NWOG as a premium short zone.** Build shorts between the NWOG lower quadrant and the next octant; "I just don't want it to go up here and touch the halfway point. Why? Because if it's bearish, it won't even go there." (062) [refines B1 A3 NWOG]
- DRAFT: **Event horizon** generalised: midpoint between two key PD arrays (056), two old lows (063, 066), an old low and relative equal lows (067), or one FVG's low and another's high (068, 069). A close beyond it projects the next pool. (056, 062-064, 066-069) [refines B1 A8]
- DRAFT: **FVG anchors.** A one-tick VI between close and next open moves the anchor (067, 068, 069, 070). BISI with no VI at the low: use the wick high (063). [refines 2023 FVG definition]
- DRAFT: **IOFED** = "a partial entry into but not even consequent encroachment" of the FVG. (063, 062) [conflict check: B1 A5 IOFED = 1 tick past candle 1]
- DRAFT: **Market maker models.** MMSM stages named (058, 067). MMSM "can go up to go down and clear the original consolidation. But when it's bullish it will not do that": exit in deep discount without the original consolidation when the daily hasn't confirmed (067). MMBM / smart money reversal language (057). Model 2022 = OTE (065, 068). [refines 2023 MMXM]

### A6. Macros and time windows
- DRAFT: **Lunch macro.** Lunch 11:30-13:30; the setup "usually forms in the first hour"; buy side taken "during the 11:50 a.m. to 12:10 macro" and the target is the 10:00 low; if not, hold into the PM session. (060, 068) [conflict check: 2023 lunch avoidance; B1 A6 macro list]
- DRAFT: 10:50-11:10 macro as confluence for a turn at a daily OB + breaker (067). [refines B1 A6]
- DRAFT: Pre-market 07:00-09:00 (can start ~06:30) (059). Time distortion = lingering inside an FPFVG before the false run (060, 064). [refines B1 A1]

### A7. Entries, exits, management
- DRAFT: **Exits.** Bulk at the low-hanging-fruit objective, one or two contracts as a runner to the best case (069). Partials just below relative equal lows "where retail may be wanting to take the opposite side" (056); at event horizon (063, 064, 067); at the 1H BISI CE (060). [refines B1 A8]
- DRAFT: **Partial on concern.** "As soon as that thought jumps in your head, the first thing you do is take something off." (055, 062) [same idea as B1 A8 "if nervous, take one off"]
- DRAFT: Stops: at the entry candle's open (060); below the wick CE for a long (066); at the IFVG low on Fed days, not tighter (064). Trail only after a close beyond the wick/gap (064). [refines B1 A8]
- DRAFT: Max two stops in hostile conditions, then stop for the session (055, 070). [new]
- DRAFT: Holding period: short-term = past the 18:00 restart (2-5 days); day trading = out before 17:00. "I would not hold anything over the weekend now." (068) [new risk rule]
- DRAFT: Pyramiding into a swing high from the NWOG lower quadrant up to the octant, up to 16 lots (062). [conflict check: B1 C3 pyramiding]

## Part C. Conflicts to decide (2023 rule or owner directive stays in force meanwhile)
Numbering continues from batch 1 (1-12).
13. **FPFVG on gap days:** exclude the 09:30 candle and use the first displacement FVG (054) vs B1's 09:31 middle candle rule.
14. **News handling:** flatten before CPI/PPI and don't trade the release (065) vs trading right after the release (062, 064) vs B1 #5 (skip 08:30/08:31) vs 2023 08:30 entries.
15. **Lunch macro:** an active 11:50-12:10 raid toward the 10:00 low (060, 068) vs the 2023 lunch avoidance and fixed macro list.
16. **Order block:** "consecutive up candles make one block, use the largest" and "no close required" (059, 067) vs 2023 OB definition and confirmation.
17. **IOFED:** "partial entry short of CE" (063) vs B1 "1 tick past candle 1" (024, 032).
18. **Day-of-week:** CPI/PPI week Tue/Wed PM-only and Mondays off for new traders except NFP week (058, 066) vs 2023 day-of-week rules.
19. **HRLR/LRLR:** 2026 "candles sharing a range" definition (055) vs the 2023 wording; needs a numeric threshold.
20. **15m bellwether as the framing timeframe** (068) vs the 2023 timeframe pairs (also B1 A9).
21. **Unicorn** = breaker + FVG at the same location (065, 067) vs the 2023/2024 definitions.

## Part D. Backtestable switches (all default OFF; DRAFT names)
- **Strongest candidates** (clear mechanics, testable on 1m data):
  - `org_half_gap_first_hour_bias` (+ `org_min_open_to_ce_distance` 20/30/40)
  - `org_entry_on_open_overlap_after_htf_array`
  - `org_ce_hit_time_tracking` (10:00 vs later)
  - `three_failure_short_signature`
  - `fvg_max_candles_inside` (1/2/3/5)
  - `single_candle_breach_quality`
  - `opening_range_probe_first_rel_eq_lows_in_daily_array`
  - `tgif_20_30_friday_close_target`
  - `friday_weekly_draw_priority`
  - `lunch_macro_1150_1210_to_1000_low`
  - `no_trade_open_at_dealing_range_equilibrium`
  - `event_horizon_between_two_arrays_partial`
- **Definitions needed before testing:**
  - `first_utilization_reset_turtle_soup`
  - `hangman_pattern`
  - `shadow_blended_inefficiency`
  - `daily_wick_ce_flip` / `daily_ob_open_and_wick_boundaries`
  - `ndog_ce_body_failure`
  - `nwog_premium_short_zone`
  - `mmsm_skip_original_consolidation`
  - `toothpick_single_candle_support`
  - `hrlr_filter` (numeric)
- **Filters:**
  - `cpi_ppi_fed_week_pm_only_tue_wed`
  - `flatten_before_cpi_ppi_nfp`
  - `no_entries_before_1000_fed_speech`
  - `skip_monday_after_weekend_bank_holiday`
  - `skip_mondays_except_nfp_week` (beginner only)
  - `summer_reduced_participation`
  - `require_daily_framing`
  - `abort_am_if_0930_runs_opposing_liquidity`
  - `stop_after_target_hit` (day / week)
- **Management:**
  - `bulk_at_lhf_runner_to_best_case`
  - `partial_on_concern` (not mechanical; skip in backtests)
  - `max_two_stops_per_session`
  - `stop_at_entry_candle_open`
  - `fed_day_wider_stop`
  - `no_weekend_holds`
- Full per-lecture switch lists are in each note's last section.

## Part E. Questions for Mase (list only; not asked now, ask in the full review)
1. Caleb's ORG half-gap model is the simplest mechanical rule in the series. Should it be the first 2026 switch tested (with the 20/30/40-handle filter)?
2. News days: which version governs (flatten before, skip 08:30/08:31, or trade after the release)?
3. Should the five-candle rule apply to every FVG entry, or only to entries in the bias direction?
4. 061 is pending whisper; draft it on its own when the transcript lands?
