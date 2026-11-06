# 2026 ICT Smart Money Concept Lectures (videos 021-053): DRAFT rules for Mase's review

**Status: DRAFT. Nothing here is wired into the engine and nothing has been backtested.**
Built 2026-11-05 from the per-lecture notes in `mentorship/notes_2026smc/`. The source is captions only. Frames are on the laptop, so "this level / that candle" is resolved from context, and prices taken from captions can be garbled.

See also batch 2 (054-070): `m2026smc_b2_draft_rules.md`.
See also batch 3 (071-082, 084-087): `m2026smc_b3_draft_rules.md`.
See also batch 4 (088, 089, 091-093, 095-097): `m2026smc_b4_draft_rules.md`.
See also batch 5 (098-105): `m2026smc_b5_draft_rules.md`.
See also batch 6 (106-112): `m2026smc_b6_draft_rules.md`.
See also batch 7 (113-124): `m2026smc_b7_draft_rules.md`.
See also batch 8 (001-020, the newest lectures, Aug 31 - Oct 28 2026): `m2026smc_b8_draft_rules.md`.
See also batch 9 (125-136, Feb 9 - Mar 9 2026): `m2026smc_b9_draft_rules.md`.
See also batch 10 (138-143, Jan 1 - Jan 13 2026, the oldest videos): `m2026smc_b10_draft_rules.md`.

## How to read this
- **Source tier: 2023 Mentorship wins on every conflict.** This series sits below 2023, alongside 2024 Mentorship, 2025 lectures and TE/Charter. The 2026 series is ICT's free YouTube clinic (Jul 31 to ~Sep 2026, NQ Sep contract). It is mostly daily reviews and live executions built on one framework: grade every range in octants, and a PD array is valid only if it is tethered to a grade. The **experienced-trader version stays the default**, and beginner rules become switches only.
- Tags:
  - **[new]**: not found in the rulebook (grepped against the digests but not exhaustively).
  - **[refines]**: adds detail to an existing rule.
  - **[conflict: X]**: differs from 2023 or an owner directive; 2023 stays in force.
  - **[conflict check]**: may differ.
- All switches default OFF.
- Lecture refs = `notes_2026smc/NNN_*.md`. Times are New York local.
- Deferred per Mase (2026-11-03): conflict and priority questions wait for one full review. Nothing here was asked.

## Coverage
- **Read in full and noted (29):** 021-025, 027-032, 034-047, 049-051, 053.
- **Not in this batch:** 001-020 and 026, 033, 048, 052 (not synced in PR #16). There is no `playlist.json`, so titles are unknown; the note titles are descriptive.
- **Caption quality:**
  - 021 is a machine back-translation of a dubbed track (garbled; use with care).
  - 050 has heavy mis-hearings ("consequent corrosion", "positive balance" = buy side imbalance).
- **Audio checks needed:**
  - 032's "Thursday 19:00-22:00 dealing range" contradicts itself.
  - 038's term "gray pole" is unclear, and its projection value is not stated.
- **Order:** the playlist is not chronological. 044 (part 1) and 043 (part 2) are one Sat Aug 1 lecture. 045 is the same-day (Fri Jul 31) review.
- **Silver Bullet:** the examples in 028 and 034 are noted only. Project rule: no edge, off by default, not re-proposed.

## Part A. Rules by topic (DRAFT)

### A1. The 07:00-09:00 pre-market range (core rule of the series)
- DRAFT: Grade the 07:00-09:00 range (highest high, lowest low) as a "time-based range": high, low, CE, quadrants, octants. "That 2-hour window gives you all the ideas ... where is the opening range the first 30 minutes or at the very minimum the first 60 minutes dealing range." (029, 044, 045) [new]
- DRAFT: **Regime.** If 07:00-09:00 trends, the AM session (09:30-11:30) is choppy or range-bound: trade only traps and macros, use smaller targets, take partials inside the range. If 07:00-09:00 consolidates, expect a one-directional AM. (027, 028, 029, 030) [new]
- DRAFT: **Session alternation.** A consolidating session is followed by expansion, and there are "rarely three trending sessions in a row". If London (02:00-05:00) and 07:00-09:00 both trended, fade the RTH continuation. (025, 027, 029) [conflict check: 2023 session bias logic]
- DRAFT: On 08:30 news days the window is 07:00-08:30 (NFP example: 041). On CPI/PPI weeks, Mon and Tue trend in ETH but are range-bound in RTH; grade 07:00-07:30 instead (otherwise 07:00-08:00 in that lecture). (029, 039, 041) [new; 039 conflicts internally with the 7-9 window]
- DRAFT: **Projections.**
  - The -0.5 projection of the 7-9 range is the projected daily (or session) high or low: "when I'm looking for the daily highs and lows ... I'm going to use this one." (044, 045)
  - NFP: -2 SD into the 08:50-09:10 macro is a reversal zone (041).
  - The 7-9 low to the first post-open high, projected -0.5 and -1, gives targets (031).
  - The 07:00-09:30 low projection is a reversal level (022). [new]
- DRAFT: **Tethering.** After 09:00, an FVG, OB or IFVG counts only if it touches a 7-9 grade. With a VI, "you have to refer to the candlestick that allows for the volume imbalance to be there." (031, 044, 045) [new filter]
- DRAFT: A 7-9 range that hits a daily key level means a higher chance of hard AM conditions (030). [new]

### A2. Grading any range: octants and the validity rule
- DRAFT: "All inefficiencies need to be graded."
  - Daily or weekly arrays, ORG, NWOG, NDOG and 7-9 all get high, low, CE, 25/75 and the octants (0.125, 0.375, 0.625, 0.875).
  - Daily-array grades are projected onto the 1m chart as the intraday map. (021, 023, 028, 046, 049, 050) [refines 2023 "five levels": adds octants; 2023 skips quadrants on small gaps]
- DRAFT: **Validity rule.** "Candlestick number two that creates the inefficiency needs to be connected to an octant or a gradient level within a range that is your analysis leading to a draw on liquidity." An OB must "touch or lay on" a grade. (028, 036, 046, 049, 051) [new filter; the central claim of the series]
- DRAFT: Candle 2 touching two grades means "significant contraction" (a strong move) in the bias direction (049). [new]
- DRAFT: **Fib anchor on bodies.** Where an array's edge is a body, anchor to the higher of open and close (bullish discount case): "the higher one is what it's going to reach down for." (049) [new]
- DRAFT: **Time-price grid.** "Horizontal" = grades of what you're measuring. "Vertical" = macro start and the top of the hour. "Every single time we get to a octant or a quadrant level, you're looking for a PDA to form." (046) [new]
- DRAFT: Lingering between grades (and lunch) means sit out (050). [refines 2023 lunch rule: matches the new-trader side]

### A3. Opening range gap, opening ranges, weekly and daily gaps
- DRAFT: **ORG** = 09:30 open to the prior session's last RTH print at **16:14** ("the only two reference points you really need"). Graded in octants. Its CE is reached by 10:00 70% of the time. "We're always aiming for consequent encroachment. It doesn't have to be the same day." (021, 043, 045, 049, 053) [conflict check: 2023 ORG = "prior RTH close" (16:00 vs 16:14 futures RTH last print); 70% already in 2025 L34 draft]
- DRAFT: **ORG short plan** (premium ORG, bearish). (043, 025) [new, directly backtestable]
  - Entry on a retest of the 09:30 open.
  - Targets in order: the 16:00 candle high if above the settlement (the "low-hanging" target), the ORG CE (have 75-80% off there), full fill, then -0.2, -0.5 and -1.
  - Variant: the prior-session low first, then the ORG CE.
- DRAFT: **ORG-only model.** Use only the day's ORG grades. Trade the FVG or IFVG whose candle 2 is on a grade, and target the full gap fill. "You don't need to even confer with the daily." Confluence with the daily arrays = high probability. (049) [new]
- DRAFT: **ORG CE ledger.** Collect every day's ORG CE through the week. Once traded through, a CE flips to premium or discount. When Mon/Tue/Thu CEs converge in a trading range, "above this ... likely to sell off ... below it ... likely to want to rally", filtered by the HTF bias. (051, 053) [new; 2023 says ORG/NDOG expire after 3-5 days: consistent with a week]
- DRAFT: Opening range = exactly 30 min, 09:30-10:00. First-hour dealing range = 09:30-10:30, and its equilibrium is a retrace target. 09:30 opening price = reference line. Yesterday's 09:30 open is a target (it became the RTH high in 047). (025, 029, 030, 047) [refines; 30-min OR in 2025 draft]
- DRAFT: **FPFVG.** Uses the 09:31 middle candle. Monday's FPFVG is "crucial information ... carry it through the entirety of the week". Monday/Friday FPFVGs of the last 2 weeks are key arrays. Yesterday's FPFVG is a next-day level. (025, 049, 051, 053) [new]
- DRAFT: **NWOG.** Keep the last 5 weeks (025) [in rulebook: `nwog_keep=5`]. On Mondays, the NWOG is the draw if Asia and London never traded to it and there is no runaway move (032) [new]. A failed hold above the NWOG means short (027) [refines].
- DRAFT: NDOG CE as an Asia array, with the NDOG extended. Last week's Mon/Fri NDOG and ORG serve as HTF arrays. Friday's NDOG plus a daily VI = Monday-open short (029, 044, 050). Midnight opening price = magnet and session target, partial just before (039, 040) [midnight open in rulebook; target use new].

### A4. Bias, weekly framework, draws
- DRAFT: Weekly draw by proximity: previous week/month high vs previous week/month low, plus the primary trend (034) [conflict check: 2023 weekly bias rules]. Monthly and weekly high/low/close levels serve as draws (021) [monthly close new].
- DRAFT: Weekly profiles matched to the economic calendar (034) [refines 2017 core content]. The weekly range is "fulfilled" once both announced weekly pools are taken: stop trading (036) [new].
- DRAFT: **TGIF.** On Fridays of trending weeks price retraces 20-30% of the weekly range (aim 25%, 40% rare). The Friday 09:30-10:00 OR forms the high (034). TGIF is **canceled** when Friday takes buy side first and then breaks lower inside an HTF sell program (051). [refines 2023 TGIF 20-30%/25%; conflict check: 2023 calls >30-40% reversal territory]
- DRAFT: **Liquidity universe** = the last 3 days (or sessions). Pools include session ranges, the London lunch range, the NY lunch range, the Friday final-hour range and midpoints. Body-based equal highs count. (029, 034, 038, 039, 044) [new]
- DRAFT: A smooth low is not how markets bottom: expect a return later in the week (051). A failed lower objective flips the bias back to premium (023). [new]
- DRAFT: Open sitting between two daily arrays that don't overlap means a "low resistance liquidity run" (big fast candles) to the next array. An "efficient buy program" (tight small candles grinding) means don't fade. (046) [new]
- DRAFT: A daily PD-array touch means expect a tradable run. A daily close below a SIBI low with no gap open = early warning, bias to the NWOG. Under the CE of a daily bullish suspension block, "hunt something", especially when time agrees. (031, 042, 047) [refines]
- DRAFT: Guarded liquidity: don't target equal highs that are guarded by a rejection block plus a failed IFVG (034). [new]
- DRAFT: Daily-low cluster = the CE of the prior-day range projection and the grade of a 3-day-old wick (044). [new]

### A5. PD arrays and definitions
- DRAFT: **Suspension block** = a SIBI or BISI with a VI at both its high and its low (021 calls it a "stop block"). Verify from open/close prices. Its CE is the entry, with the stop under the adjacent wick CE. (021, 023, 042, 047, 049) [new name]
- DRAFT: **Wick as a gap.** Grade from the body to the wick extreme. Bodies must respect the wick CE ("wicks can do the damage"). Grade the *first* wick on a key level; "any other wick ... would be considered a candle with a wick. Don't use those." The wick CE alone is not enough; a body close beyond it shows willingness. (021, 025, 046, 051) [refines 2025 L22/L23]
- DRAFT: **Premium/discount sensitivity.** Bearish: bodies stay in the lower half, and the upper half must show strong rejection. Bullish is the mirror image. **Order-flow ladder:** a premium array not traded to, its CE not reached, or no body left in its upper half all mean bearish; "if it can't even touch it ... extremely bearish." (046, 051, 053) [refines 2023 CE body rule]
- DRAFT: **IFVG.**
  - "First presentation is in reference to time ... How it forms is the first utilization." An IFVG that is undone reverts to its first utilization.
  - Two qualifications are needed before entry: a close through, then a retest with no body beyond the CE.
  - A "mohawk" (a small wick overshoot) is tolerated.
  - (040, 041, 046, 047, 053) [refines 2023 IFVG; the two-qualification rule is stricter]
- DRAFT: **Reclaimed bearish FVG** has 5 quality stages; the "mohawk" is the weakest (027). [new]
- DRAFT: **Obsidian array:** two opposing wicks (when bearish, the second wick is higher). The zone runs between the two wick CEs. (027, 031) [new]
- DRAFT: **Breaker.** The real breaker is "high, low, higher high. Down close candle with the lowest close" (053). Fill levels run from the mean threshold to the low, in octants (036). [refines 2023 breaker; conflict check on the anchor]
- DRAFT: **Bearish OB on a grade:** once price trades down through the up-close candle's open, "it need not close below it ... that validates this as a change in the state of delivery"; retraces into it are sell or add points (051). Prefer the OB whose open coincides with a pool (038). [refines 2023 OB]
- DRAFT: **Measuring / breakaway gap.** A gap at the CE of the range being run (7-9, ORG, or an implied dealing range) is a measuring gap. Expect acceleration and no deep retrace: "drop, consolidate, and drop harder." A gap left partly unfilled = continuation. (040, 043, 045, 049, 051) [new placement rule]
- DRAFT: **Implied (unrealized) dealing range:** anchor at the SIBI or OB *body* high (never the wick) down to the draw, then grade it. Every array on its grades is valid. (051) [new; conflict check: 2023 dealing-range anchors]
- DRAFT: Other terms:
  - institutional order flow entry drill = a retrace to 1 tick past candle 1 of the FVG; continuation if the gap stays half unfilled (024, 032);
  - immediate rebalance = short with the stop 1 tick above 50% of the displacement candle (021, 043);
  - "cork" = a small block just below a target;
  - fulcrum = equal-leg measured move (037, 043);
  - "gladhand" = a retrace failing to reach the FVG CE, meaning strong continuation (034);
  - last inefficiency of the displacement leg = the entry gap (042);
  - the FVG just before the equal-highs run = the valid IFVG afterward (043);
  - rejection block = the highest up-close body in a swing high.
  - [new, mostly discretionary]

### A6. Macros and time windows
- DRAFT: Macros run :50 to :10 every hour. Named: 07:50-08:10, 08:50-09:10, 09:50-10:10, 10:50-11:10, 13:50-14:10, 14:50-15:10, 15:15-15:45, and MOC in the last 10 min. Lows and highs often form at the macro close (10:10, 11:10). "You don't have to be in the macro. You just have to know what the macro should be putting in motion." Shorting just ahead of a macro is fine. A consolidation through a macro means expect the move after :10. (021, 023, 024, 030, 037, 039, 045, 046) [conflict check: 2023 lists 09:50-10:10, 10:50-11:10, 11:50-12:10, 13:30, ~13:39-14:00, 14:50-15:10, 15:15-15:45; 07:50-08:10, 08:50-09:10 and 13:50-14:10 not in the 2023 list]
- DRAFT: Price can be right without the time: "You got the right price ... But it's just simply not time." 08:30 is an algorithmic expansion time with or without news. (032, 045) [refines 2023 "08:30 trigger time"]

### A7. News and event days
- DRAFT: No entries on the 08:30 or 08:31 1m candles (036). [conflict check: 2023 news rules]
- DRAFT: CPI, NFP and FOMC are two-stage deliveries: first a run, then a reversal for the stops (036, 041). [refines 2023 NFP profile: "first side false"]
- DRAFT: Experienced only: flip on the news candle when the first direction fails (035). [new; very risky to backtest]
- DRAFT: Jackson Hole week, especially day 1, is a "seek and destroy" profile: double-sided runs, reduce size or skip (022, 023). [new event filter]
- DRAFT: New traders: avoid Thu and Fri of NFP week; the clean window is Mon-Wed until 11:00. Take partials before 10:00 news, and wait for the first 30 min before 10:00 news. Reduce size on report days. (021, 022, 041, 042) [conflict check: 2023 new-student NFP ban; experienced default unchanged]

### A8. Entries, stops, management, size
- DRAFT: Pyramid only at or beyond the equilibrium of the entry-to-target range; a single add in the upper half of the supporting wick (023, 024). Pyramid in drawdown to the wick or VI low (043). [conflict: 2023 022 ~52:00 bans adding past the leg threshold; 043 pyramid-in-drawdown conflicts with adds in profit]
- DRAFT: **Event horizon** = 50% between the low and the target. Take a partial there (1/3 off) and move the stop to the last short-term high. Partials go only above 50% of entry-to-target. (021, 030, 035, 041, 053) [refines 2023 event horizon (50% between NWOGs)]
- DRAFT: Partials at each grade: lowest octant, lowest quadrant, octant below CE, CE. Treat each grade "just like ... sellside liquidity". Exit a few ticks ahead of relative equal lows. Exit early before a major draw. (032, 037, 050) [conflict check: 2023 partial rules]
- DRAFT: Stops:
  - at the OB open after displacement;
  - beyond a daily VI for swings;
  - to the longest wick CE when failing at a midpoint;
  - breakeven on a close beyond the wick CE;
  - never lower a stop;
  - split the stop or use a buy-stop partial above a short-term high (OCO).
  - (022, 023, 024, 032, 040, 042, 050) [refines]
- DRAFT: Confirm on a body close, not the open (032). Three-PD-array confluence (024). Hold through consolidation: "Submit yourself to time"; if nervous, take one off (051). [refines]
- DRAFT: Execution, not an edge: probe a single contract "to get a read" on order flow, then "load the boat" (045). Re-entry at full size after a 1-tick stop-out is not recommended for backtesting (023).

### A9. Not extractable
- Long commentary sections (critics, Matrix analogies, "chain of custody" framing); hindsight-only annotations without prices; ES/NQ chart-only references; the 1m-vs-15s chart choice.
- Timeframe multiples of 4 (15m "bellwether" -> 1H -> 4H -> 8H) for blending HTF levels (051). [conflict check: 2023 TF pairs]
- Continuous-contract levels for HTF arrays (034). [data check: the engine uses front month or back-adjusted]

## Part C. Conflicts to decide (2023 rule or owner directive stays in force meanwhile)
1. **ORG close reference:** 16:14 last RTH print (2026) vs "prior RTH close" (2023). (049)
2. **Macro list:** :50-:10 every hour (2026) vs the fixed 2023 list. 07:50-08:10, 08:50-09:10 and 13:50-14:10 are new. (021, 023, 039, 045)
3. **Pyramiding:** at or beyond equilibrium (023), and in drawdown (043), vs 2023 022 ~52:00 banning adds past the leg threshold.
4. **TGIF depth:** 40% "rare" (2026) vs >30-40% = reversal territory (2023). (034)
5. **News candles:** skip 08:30/08:31 (2026) vs 2023 entries off the 08:30 open, CE and stop rules. (036)
6. **Session alternation / three-session rule** vs the 2023 session bias logic. (025, 029)
7. **Pre-market window on news weeks:** 07:00-07:30 (039) vs 07:00-09:00 (029, 044) vs 07:00-08:30 (041). This is internal to 2026; 2023 has no grading rule.
8. **Breaker anchor:** lowest-close down candle (053) vs the 2023 high-low-higher-high wording.
9. **IFVG entry:** two qualifications required (040) vs the 2023 close-beyond-and-retest.
10. **Weekly draw by proximity** (034) vs the 2023 weekly bias rules.
11. **Implied-dealing-range anchor:** body, not wick (051) vs 2023 dealing-range anchors (check `levels.md`).
12. **Partial ladder at grades** (050) vs the 2023 partial rules.

## Part D. Backtestable switches (all default OFF; DRAFT names)
- **Strongest candidates** (clear mechanics, testable on 1m data):
  - `r0709_regime` (trend vs consolidation -> AM mode)
  - `r0709_minus05_daily_extreme`
  - `pd_array_tether_to_grade` (applies to 7-9, ORG, daily and implied ranges)
  - `org_short_plan` (043)
  - `org_ce_by_1000`
  - `org_ce_ledger_convergence`
  - `monday_nwog_draw`
  - `monday_fpfvg_week_level`
  - `measuring_gap_at_range_ce`
  - `event_horizon_partial`
  - `news_skip_0830_0831`
  - `weekly_range_fulfilled_stop`
  - `tgif_retrace_20_30` (+ `tgif_cancel_htf_sell_program`)
  - `session_rarely_three_trend_fade`
- **Definitions needed before testing:**
  - `suspension_block`
  - `obsidian_array`
  - `wick_ce_body_rule`
  - `first_wick_on_key_level`
  - `ifvg_two_qualifications` / `ifvg_first_utilization_revert`
  - `breaker_lowest_close_anchor`
  - `implied_dealing_range_body_anchor`
  - `reclaimed_fvg_quality_stage`
- **Filters:**
  - `jackson_hole_seek_and_destroy`
  - `cpi_ppi_week_mon_tue_rth_range`
  - `nfp_week_beginner_window` (beginner only)
  - `between_grades_sit_out`
  - `open_between_two_daily_arrays_run`
  - `efficient_program_no_fade`
- **Management:**
  - `pyramid_at_equilibrium` (conflict)
  - `partials_at_grades`
  - `stop_ob_open`
  - `breakeven_wick_ce`
  - `swing_stop_beyond_daily_vi`
- Full per-lecture switch lists are in each note's last section.

## Part E. Questions for Mase (list only; not asked now, ask in the full review)
1. Should octant grading plus the tethering filter become a global PD-array validity rule (big change: it rejects most untethered gaps)? Or should it stay a switch per range type?
2. ORG: use the 16:14 futures last print (2026) or the 16:00 close (current)?
3. Rank 2026 vs 2024/2025/TE-Charter for the non-2023 tier.
4. Audio checks: 032 "Thursday 19:00-22:00" range; 038 "gray pole"; 021 (dubbed back-translation) worth re-fetching the English track?
5. Fetch the missing 026, 033, 048, 052 and 001-020 captions for a follow-up batch?
