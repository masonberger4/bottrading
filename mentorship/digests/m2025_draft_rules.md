# 2025 Lecture Series: DRAFT rules for Mase's review

**Status: DRAFT. Nothing here is wired into the engine and nothing has been backtested.**
Built 2026-11-03 from the per-lecture notes in `mentorship/notes_2025/` (captions only; frames are on the laptop, so "this level / that candle" is resolved from context and prices from captions can be garbled).

## How to read this
- Source tier: **2023 Mentorship wins on every conflict.** The 2025 series sits below it, with 2024 Mentorship and TE/Charter. ICT frames the series as "if I were a new student of my 2024 Mentorship" (L83, L82): the **experienced-trader version stays the default** and beginner rules become switches only.
- Tags: **[new]** not found in the rulebook (not exhaustively grepped; check before wiring), **[refines]** adds detail to an existing idea, **[conflict: X]** differs from 2023 or an owner directive (2023 stays in force), **[conflict check]** maybe differs. All switches are default OFF.
- Lecture refs = `notes_2025/NN_*.md`. Times New York local.

## Coverage (lower-usage, core-only option chosen by Mase 2026-11-03)
- **Read in full and noted (28 lectures):** 01 (live sample), 83, 82, 80, 78, 77, 76, 75, 74, 73, 72, 70, 66, 65, 64, 62, 58, 57, 51, 34, 32, 31, 29, 27, 26, 23, 22, 21. (58, 62, 64, 70 were re-read in full in part 6; the originals were accurate, addenda added.)
- **Daily reviews (46 videos) read 2026-11-08:** 02-20, 24, 28, 30, 33, 36-45, 47-50, 52-56, 60, 61, 63, 68; see Part F. The series is now fully noted (every video with speech).
- **Missing captions:** 25, 35, 59, 67, 69, 71, 79, 81 (most are silent per data/ict_no_commentary.txt).
- **Added 2026-11-06:** L46 (Wed Apr 23 2025 review), read in full from the late captions (PR #40); note `notes_2025/46_28M9ouiKmSY.md`. Rules folded in below, tagged (L46). No new conflicts; it repeats L-series rules and adds one entry model.
- **Caption 29 is truncated** (ends mid-sentence "then I'll touch"); 27 and 26/23/22 end only in sign-offs, but 27 also ends mid-sentence ("the last time we look at this particular"). Use as partial.
- The core set is mostly the January "how I'd build a model" series plus the Storytellers (June) and September ATH lectures.

## Part A. Rules by topic (DRAFT)

### A1. Charting, time, opening ranges
- DRAFT: Everything in New York time; electronic hours on; 1-minute chart. New trading day starts 18:00. (L80, L62) [in rulebook]
- DRAFT: Algorithmic opening range = exactly 30 minutes: 09:30-10:00, and 00:00-00:30 ("midnight opening range"); "if it's less than 30 minutes it ain't algorithmic." First 60 minutes = separate dealing range. (L82, L80) [midnight OR new]
- DRAFT: Pre-market equities session opens 07:00; ETH 08:00-09:30 is the 90-minute window whose high = buy side, low = sell side for the open (Venom frame). (L22, L51) [new]
- DRAFT: Wait for the 09:30 open before acting on a daily bias; if premarket ignores the levels, sit out and trade the 10:00 Silver Bullet as fallback (L26, L77; Silver Bullet kept off, project says no edge).
- DRAFT: Midnight OR projections -0.5 / -1 give "a rough idea" of the day's high, weaker on NFP/FOMC/CPI days. Opening range high-low projected -1.5 SD targeted London/Asia liquidity (L80, L77, L34). [new]
- DRAFT: PM opening range 13:30-14:00. (L34, L51) [new]

### A2. Opening range gap (ORG) and new week opening gap (NWOG)
- DRAFT: ORG = prior RTH settlement (16:14/16:15 close) to 09:30 open on RTH data; fib 0/0.25/0.5 (CE)/0.75/1. Premium if gap up. (L78, L82, L70) [in rulebook]
- DRAFT: Size buckets (NQ points): 20-75: likes CE, at least; 75-120: gray, may sit until 10:00; over ~120: keeps going in gap direction, return usually stops at the quadrant nearest the open and may not fill for days. (L78, L77, L51) [new; conflict check vs 2023 gap handling]
- DRAFT: "70% likelihood" the ORG CE is hit by 10:00 (L34, L57, L26). [refines]
- DRAFT: NWOG = Friday settlement to Sunday 18:00 open, fib likewise; blend with ORG; support where quadrants converge; draw to NWOG CE; price can trade to NWOG CE ("permissible range"), bodies respect the low/high. (L70, L76, L73, L26) [in rulebook, refines]
- DRAFT: Prior ORG levels are reused the next sessions. (L78)
- DRAFT: A discount ORG plus draw on relative equal highs = long bias; premium ORG = short. (L66, L26)

### A3. Bias, draw on liquidity, narrative
- DRAFT: Draw on liquidity first; "knowing where the market is going to draw to is the most critical thing." Bias from weekly/daily; bullish means look to the sell side in the 08:00-09:30 window. (L77, L51)
- DRAFT: Long/intermediate-term swing highs/lows (Larry Williams) with imbalances inside them are high-probability zones; project old arrays 60 days forward and back (120-day frame). (L26, L23)
- DRAFT: At all-time highs avoid picking the top; grade every recent premium/discount wick (25/50/75, body to high) and trade shorts only intraday; daily trend stays up. (L27, L23, L22) [new]
- DRAFT: Troubled market = price sharing prior bar ranges (time distortion); use old daily CIBI/BISI quadrants, drop classic S/R; hold-off until structure breaks. (L27, L29) [new]
- DRAFT: Weekly: Thursday forms fake or true high of a bullish week; Friday after a strong week and before a weekend with event risk = sell rallies / low-hanging targets only. (L22, L21, L26)
- DRAFT: Days of CPI/FOMC/NFP: heavy intervention; NFP week: new traders done by 07:00 Wed; FOMC afternoon: first FVG after 14:00, second wave 14:30. (L29, L31, L23) [conflict check: 2023 news rules]

### A4. PD arrays and definitions
- DRAFT: FVG gradient: low, lower quadrant, CE, upper quadrant, high; always include the volume imbalance; bodies stay in the discount (bullish) or premium (bearish) half. (L80, L65, L66, L26)
- DRAFT: First presented FVG (FPFVG): first FVG in the 09:31-10:00 window on the 1-minute chart (L77 "can't form on the 9:30 candle" is Caleb's rule; L34 uses 9:31); extend through the day/week; character flips when target is reached. (L77, L34, L66, L58) [new vs 2023]
- DRAFT: Inversion FVG: broken FVG must keep bodies out of the "wrong" half; reclaimed FVG (crossed then re-entered from the original side) resumes its original polarity; not an inversion. (L65, L22, L21, L58, L74) [new distinction]
- DRAFT: Premium wick = wick above the body; discount wick = below; both graded with quadrants. (L23, L22)
- DRAFT: Venom model: raid candle closes above equal highs with a gap, next candle closes back below with a gap ("two fangs"); entries at the run, the Venom candle open, or first FVG; needs trend context; one-candle versions seen. (L51, L22, L62) [new; details partly withheld]
- DRAFT: Model 2022 (retrace above 50% of the break leg, OTE 62-79%, 70.5% sweet spot) re-shown. (L23) [in rulebook]
- DRAFT: Cycling the clock: check 60m at the hour, 15m on 15-minute close, 5m on 5-minute close, then trade the 1m; one FVG per 15 minutes if a draw exists, else high resistance liquidity run conditions (sit 15 min). (L65) [new]
- DRAFT: Algorithm sees only time and OHLC; no DOM, VWAP, level 2, volume profile, Wyckoff, Elliott, S&D. (L65, L21, L22)

### A5. Macros and session windows
- DRAFT: NY lunch macro 10:50-11:10 (L58); lunch window targets the first prominent sell side (bullish) / buy side (bearish) that forms AFTER 10:00; best when the morning ran one way with no retrace on the minor pool; 11:30 pull back into the range. (L57, L58, L22, L51) [refines; check vs 2023 11:30 macros]
- DRAFT: Avoid the morning session (09:30-10:30) after a very large down day. (L57, L58, L66) [new]
- DRAFT: Market-on-close macro 15:45-16:00, "a script" ripping for liquidity. (L72) [in 2024 notes]
- DRAFT: London macro "exactly 03:30"; midnight OR to London link. (L80) [conflict check: 2023 London macro times]
- DRAFT: 08:30 news injection: pre-market buy-side raid, short back to pre-market sell side. (L22)

### A6. Entries
- DRAFT: Entry arrays: FVG CE and lower/upper half, inversion FVG, rejection block, bearish breaker, order block (change in state of delivery = open of the last candle, or wick high if a wick), immediate rebalance (candle returns to the prior candle's level) . (L57, L58, L22, L70, L72, L75, L76)
- DRAFT: Scale in at CE/upper end with max sizes (4 to 16 in examples) while bodies respect half. (L75, L72)
- DRAFT: Timeframe: use whichever 1-5 minute chart shows the cleanest single inefficiency. (L75)
- DRAFT: "Failure then inversion" long: a bullish PD array fails (snare), price recovers above the 9:31 FPFVG and flips a bearish FVG into an inversion; buy CE. (L70)
- DRAFT: Counter-macro-trend: exit 1-2 ticks before the target liquidity and take only low-hanging fruit. (L21, L22)

### A7. Stops, management, size
- DRAFT: Stop above/below the array high/low, 1-2 ticks beyond the invalidation level; stops 15-20 handles in examples; bigger stops and less size in high resistance runs. (L27, L82, L66, L70)
- DRAFT: Minimum 15 NQ handles net of spread/slippage or skip; 3:1 to 5:1 reward preferred. (L27, L82)
- DRAFT: Partials at turning-point candles and low-hanging liquidity; stop to cost+fees after first partial or after the quadrant is lost; trail to short-term high/low; sometimes remove the target and manage by respect of the array. (L62, L64, L72, L76, L21)
- DRAFT: Size for volatility (e.g. 3 contracts instead of 10-15 when volatile); beginners trade micros, $1,000 minimum. (L70, L82) [beginner]
- DRAFT: One setup, one instrument; no trade every day. (L62, L82) [beginner/principle]

### A7b. L46 additions (Apr 23 2025 review)
- DRAFT: **Wick CE is measured from the body (open) to the extreme**; daily premium/discount wick CE as an HTF level (L46). [repeats; see L-series wick rules]
- DRAFT: **Back-and-forth wicks after the open = manual intervention: stop trading the session** unless positioned early with a large stop and tiny size (L46). [refines HRLR/troubled market]
- DRAFT: **10:50-11:10 entry drill**: in bias, a bearish OB with a SIBI inside an IFVG, plus a premium wick CE inside it, = one entry model ("three PD arrays all in one") (L46). [new]
- DRAFT: **PDA expiry by 20/40/60-day lookback**; beyond 40 days only with experience (L46; same in 2026 SMC 140). [repeats]
- DRAFT: **Planned three-step partials on a turtle-soup short**: 2 at the FPFVG, 1 below the next low, rest below the last; initial stop 3 ticks above the high (L46). [repeats]

### A8. Forex
- DRAFT: Triad: only with the correlated pair and DXY confirming; leader hits the pool first. (L66) ; NWOG short example GBPUSD; reclaimed FVG London long. (L73, L74)

### A9. Not extractable
- ICT states he withholds an ultra-tight stop-management PD array (L27), the 10:12 / IMP-24 daily range logic (L66), Venom details (L51, L62), and "81" other PD arrays. Not backtestable.

## Part C. Conflicts to decide (2023 rule or owner directive stays in force meanwhile)
1. ORG size buckets and extreme-gap quadrant rule vs 2023 gap handling (L78, L77, L51).
2. Midnight opening range 00:00-00:30 and "exactly 03:30" London macro vs 2023 sessions/macros (L80).
3. FPFVG 09:31-10:00 (new) vs 2023 "no trades 09:30-10:00" and the owner decision on the opening range (L34, L77, L66).
4. Lunch macro as "first prominent low/high after 10:00" at 11:30 vs 2023 lunch/macro times (L57, L58, L22, L51).
5. FOMC 14:00/14:30 trading, NFP-week filters, Friday/Thursday weekly rules vs 2023 news rules (L23, L29, L31, L26, L21).
6. Reclaimed FVG vs inversion FVG definition vs 2023 IFVG wording (L22, L21, L65).
7. 15-handle net minimum vs owner #2 (5 handles) (L27).
8. Avoid morning session after a large down day vs "trade every day" defaults (L57, L58).
9. 08:00-09:30 Venom window vs TE/2024 pre-market range definitions (L51; see PR #9/#10).
10. ATH rule (shorts only intraday) vs unrestricted two-way bias (L27, L23, L22).

## Part D. Backtestable switches (all default OFF; DRAFT names)
Midnight/OR: `midnight_or_enabled`, `mor_displacement_cegrade`, `mor_fib_projection(-0.5,-1)`, `mor_displacement_deviation_projection`, `london_330_macro_target`, `rth_gap_vi_reference`, `opening_range_minus_1p5_sd_target`, `wait_for_0930_before_acting_on_daily_bias`, `skip_big_event_days_for_mor_projection`, `sit_out_if_levels_not_respected`.
Gaps: `org_enabled`, `org_size_buckets(20/75/120)`, `org_extreme_uq_target`, `org_premium_prerun_to_london_high`, `org_ce_min_target`, `org_75_120_skip_until_10`, `orgap_nwog_blend_fib`, `nwog_draw`, `orf_ce_hit_by_1000_probability_70`, `opg_extreme_gap_no_ce_retrace`, `trail_stop_by_nwog_levels`.
FVG family: `fpfvg_after_930`, `fpfvg_body_overlap_drawing`, `first_fvg_0931_to_1000_1m`, `first_fvg_character_flip`, `first_fvg_requires_raid_of_rth_equal_highs_for_931_choice`, `two_recent_15m_fvg_canvas`, `fvg_gradient_25_75`, `carry_forward_friday_first_fvg`, `fvg_upper_half_balanced_no_fill`, `reclaimed_fvg_short`, `reclaimed_fvg_vs_ifvg_distinction`, `forex_reclaimed_fvg_long`, `bodies_respect_half_filter`, `premium_discount_wick_quadrants`, `ath_grade_recent_premium_discount_wicks`, `bullish_breaker_after_ssl_raid_inside_fvg`, `immediate_rebalance_after_bisi_high`, `ob_entry_to_daily_cibi_low`, `one_candle_venom_pattern`.
Venom: `venom_window_8_to_930_hl`, `venom_raid_close_above_then_close_below`, `venom_entry_variants`, `venom_requires_trend_context`.
Bias/filters: `session_open_vs_close_bias`, `avoid_picking_top_near_ath`, `htf_swing_with_imbalance_priority`, `troubled_market_flag`, `daily_cibi_ce_failure_bearish`, `daily_cibi_support_resistance_with_wick_only_raid_fade`, `prior_day_inefficiency_as_next_target_below_range`, `open_dips_to_prior_high_then_above_open_bullish`, `friday_pre_weekend_no_new_highs_bias`, `friday_after_bull_week_take_low_hanging_target`, `thursday_fake_high_of_week_reversal_before_0830`, `nfp_week_monday_trade_ok`, `nfp_week_midweek_skip`, `nfp_week_trade_window_ends_0700_wed`, `avoid_morning_after_large_range_day`, `single_model_no_daily_trade_required`.
Macros: `lunch_macro_target_first_high_after_1000`, `lunch_macro_first_high_after_1000`, `lunch_macro_seeks_first_prominent_sellside_after_1000`, `pm_macro_2250_to_310_first_gap_entry`, `pm_first_fvg_1330_to_1400`, `pm_opening_range_1330_to_1400_first_fvg`, `market_on_close_macro_345`, `fomc_2pm_first_fvg_trade_with_230_second_stage`, `premium_raid_before_0830_short_to_premarket_sellside`.
Entries/mgmt: `model2022_premium_above_50_fib_entry`, `ote_62_79_with_705_sweet_spot`, `failure_then_inversion_fvg_long`, `scale_in_at_ce(max 4)`, `scale_in_to_16`, `stay_in_lower_half_confirmation`, `target_ticks_before_liquidity_in_counter_trend`, `stop_two_ticks_beyond_invalidation_level`, `min_net_handles_15_nq`, `move_stop_to_be_after_quadrant_lost_plus_fees`, `stop_to_cost_after_first_partial`, `partial_on_break_of_short_term_low_hrlr`, `hrlr_wide_stop_small_size`, `vol_scaled_size`.
L46: `wick_ce_from_open`, `intervention_wicks_stop_session`, `m1050_ob_sibi_ifvg_drill`, `pda_lookback_20_40_60`.

## Part E. Questions for Mase (list only; not asked now, ask in the full review)
1. 2025 FPFVG window 09:31-10:00 vs 09:30 candle itself (ICT's own rule for Caleb vs for experienced): which?
2. Do the Venom / midnight opening range / FPFVG blocks replace or sit under 2023 ranking?
3. ORG size buckets: adopt 20/75/120 as filters?
4. Is the 15-handle net minimum also the owner's 5-handle room rule?
5. Reclaimed vs inversion FVG: separate switches or merged?
6. Priority of 2025 lunch macro (first prominent low after 10:00) vs 2023 lunch/11:30 macros.
7. Pending lectures: read the 24-36k-word live streams (02, 04) and a sample of the daily reviews, or stop here?

## Part F. Daily reviews (added 2026-11-08; DRAFT)
Read in full from captions (cloud, four readers in parallel), one note per video in `notes_2025/`. 46 videos: 02-20, 24, 28, 30, 33, 36-45, 47-50, 52-56, 60, 61, 63, 68. None is a silent video. Dates: stated by ICT except those marked "inferred" in the note title (09, 10, 06, 28, 33, 36, 37, 39, 40, 43, 45, 47, 49, 60); L61 is undated (Feb 2025). Lecture numbers run backward in time (L68 = Feb 4 2025, L02 = Nov 14 2025). Tags as in Part A; frames not available.

### F1. Feb-Apr 2025: L47, 48, 52, 53, 54, 55, 56, 60, 61, 63, 68
- DRAFT: Every hour has a macro: last 10 minutes of the hour to first 10 of the next (:50-:10), 20 minutes; mark all of them on the 1m/5m. Named ones he lists: 06:50-07:10, 10:50-11:10, 12:50-13:10, 13:50-14:10, 14:50-15:10, 15:15-15:45 ("final hour ... not power hour"), 15:50 market-on-close candle. (L54, L47, L55) [refines]
- DRAFT: NY lunch = 11:30-13:30 as one two-hour window ("collectively referred to by me as the New York lunch"); at 11:30 expect a retracement against the morning toward buy/sell side resting beyond the AM move; with bias, enter on IFVG, turtle soup or the run back plus first FVG/immediate rebalance. (L54) [refines]
- DRAFT: Opening range quadrants: bullish and price trades down inside the 09:30-10:00 OR into its upper quadrant = long entry timing (lunch macro start); OR standard deviations (1, 1.5, 2.5 up; -1, -2.5 down) are the day's targets, also used by the PM session. (L54) [new]
- DRAFT: The 30-minute OR (09:30-10:00) and PM OR (13:30-14:00) are static; the first presented FVG inside each is the array. (L54, L55) [refines]
- DRAFT: FPFVG selection by context: the first FVG in 09:31-10:00 is skipped if tiny, against the narrative, or if the target is already reached; take the first significant displacement in the narrative's direction. First FVG "can't be 9:30 but can be as early as 9:31". (L54, L63) [refines]
- DRAFT: Other FVG anchors: first inefficiency after a news number (PPI 08:30), first inefficiency of the week after the Sunday open in the draw's direction (extended all week, candidate breakaway gap), first FVG of the PM OR. (L63, L55, L54) [new]
- DRAFT: FPFVG anchored on top of the ORG high; with price below the ORG high into the 10:00 data, short the FPFVG spike; fallback short on the ORG CE retest after price leaves the gap. (L52) [refines]
- DRAFT: RTH confirms ETH: a gap filled only in ETH is still expected to be revisited in RTH; an ETH high taken before ~06:00 is a high-probability revisit candidate at the 09:30 open. (L52) [new]
- DRAFT: After the first move away from the ORG CE, the next FVG is a measuring gap; duplicate that range for the target. Measuring gap midpoint sits on the 50% fib of the move; breakaway gap forms near 20-30% of the implied dealing range (the run not yet complete), measuring gap near 50%. (L52, L54) [new]
- DRAFT: PD array failing to reach its CE (gap) or mean threshold (OB) signals excess one-sidedness; a NWOG whose CE is never retested after the break is "exceedingly" directional. (L55) [new]
- DRAFT: Daily gap with no wick overlap = gap/VI hybrid ("pseudo VI"); grade from close to prior open: high, CE, low (levels, not zone). (L55, L56) [new]
- DRAFT: Inside day = coiled spring that releases in the direction of the draw; a day that opens but cannot touch the prior day's high rolls over. (L55) [new]
- DRAFT: Smooth (straight) highs/lows are "suspect" liquidity that tends to be made jagged; a modest bullish read into them before continuing the larger bias; he also keeps a smooth line left intact as a build-up of stops. (L56, L55) [new]
- DRAFT: Model he wants to use in 2025: after 09:30, price above the FPFVG that acts as bullish IFVG, long on the next FVG to the buy side, take it off, then short if it breaks the FPFVG after taking the buy side. (L56) [new]
- DRAFT: Failure to launch off an IFVG (CE becomes barrier) = short entry; re-entering the upper half of the last small gap ("last line of the fence") = stop. (L56) [refines]
- DRAFT: Large trading range: do not require extremes; use 75-80% / 20-25% fib of the range for intraday turtle soup entries and targets. (L54) [new]
- DRAFT: Gray pool = two or more wick CE levels (premium wick CE with discount wick CE), blended with the last three days' H/L/O/C; marks where a daily higher low is expected; short exits there, long needs a PD array on arrival. (L53, L61) [new]
- DRAFT: A wick-overlapped FVG (no candle body inside the gap) is revisited about 90% of the time. (L47) [new]
- DRAFT: Post-holiday protocol: one day of buffer before trading after a holiday week; low expectations. (L47) [new]
- DRAFT: Weekly range projection of the high/low of the week by Fibonacci 0.5, -1, -1.5 to guess the Sunday open or the weekly low (minimum -1). (L53) [new]
- DRAFT: After 16:00 RTH close, Judas swing into the 16:00 hour then acceleration toward an old daily low (market-on-close style) when everything is bearish on a Friday; he held 4 short contracts over the weekend with a limit at the low. (L53, L52) [refines]
- DRAFT: IOFED entry: when a BPR sits in the FVG price trades into, 9 of 10 times it does not close the gap fully; enter on a shallow run above the high, not the CE. (L54) [refines]
- DRAFT: NY kill zone 07:00-09:00, optionally extended an hour either side to avoid daylight-saving problems. (L54) [new]
- DRAFT: Shallow run into liquidity (bodies line up with equal lows) = expect a deeper run into the next discount array. (L60) [new]
- DRAFT: Trail gate: wait for a close beyond the CE of the extreme wick before lowering the stop; before then, sit with the initial risk. (L60) [new]
- DRAFT: If the limit target is almost touched (a tick or two) without filling, bring the stop to that level instead of demanding the target. (L60) [new]
- DRAFT: No revenge after a stop-out or an unfilled limit; "enough is enough". (L60) [new]
- DRAFT: Remove risk when price is in close proximity to the target and the prior high ("a trade near the target should never turn into a loss"); partials then stop to CE of the gap. (L63) [new]
- DRAFT: Stop for a long entry: one tick below the previous candle's wick low; for IFVG entries just above/below the CE. (L63, L53, L60) [refines]
- DRAFT: Re-entry after being stopped at cost: rebuild size (3, then add) between the low of the FPFVG and the ORG edge while the draw is intact; cap 15 contracts. (L63) [new]
- DRAFT: Elevated-vol/manual-intervention days (tariff pause): stops do not protect; lower leverage, do not trade, stop live commentary. (L48) [refines]
- DRAFT: Bearish OB = a series of up candles taken as one block (open of the first/lowest-open candle). (L48, L54) [refines]
- DRAFT: Hourly inefficiency/liquidity void CE ("candle low to candle body") is influential in the session. (L48) [new]
- DRAFT: Weekly/daily wick CE (discount wick when below, premium wick when above) as an HTF level; close back beyond that wick CE invalidates the idea; weekly FVG as bearish IFVG then drop to 4h/1h for the next bearish FVG. (L68) [refines]
- DRAFT: Midpoint between two liquidity pools is an algorithmic partial/target level ("buy-sell equity pool"). (L68) [new]
- DRAFT: London Open Killzone and 10:00 Silver Bullets are valid in forex (BISI/SIBI entry to the upper quadrant). (L68) [new]
- DRAFT: Time reference 08:45: 15m bullish OB open in the 08:45 candle starts the spool (call time). (L68) [new]

### F2. Apr-Sep 2025: L13-15, 17-20, 24, 28, 30, 33, 36-45, 49, 50
- DRAFT: At all-time highs ICT's slide checklist: (1) price trades under down-close candles' closes = rejection blocks that promote new runs; (2) look for BISI FVGs to offer redelivery; (3) grade all premium candle wicks and expect the gradient levels to give discount sensitivity; (4) look through up-close candles to premium wicks, they need not be isolated; (5) price trades under up-close candles' closes: near ATHs the market overshoots the previous close (bear trap); (6) immediate rebalance is typically very strong and gives discount sensitivity; (7) "Avoid predicting the reversal high ... stay bullish until the market proves ... completely and utterly broke down and reversed." (L24, L18, L28) [refines]
- DRAFT: At ATHs "the only thing you can do is focus on taking continuous buy signals until they no longer work"; "Until the market completely collapses ... don't look for shorts." (L24, L18) [refines; stronger than the ATH rule in the digest, which allowed intraday shorts]
- DRAFT: Gap fill at ATHs overshoots: open below the prior day's close (past an opening range gap) traps "gap closure then buy" traders; the reversal comes at the CE/lower quadrant of a premium wick or an immediate-rebalance level. (L24) [new]
- DRAFT: ATH blowoff context: breaking out to new highs "leaving inefficiencies open, not coming back into the volume imbalance" and parabolic runs mark when an intermediate-term high is likely forming; intermediate-term high = high with two lower short-term highs either side (Larry Williams), fractal; wait for the break of relative equal lows, do not anticipate. (L17, L18, L13) [refines]
- DRAFT: Premium wick that price closes above becomes a discount array at its CE ("now acting as a discount array is 19,980"); bullish: expect lower-half respect, bodies in the upper half; bearish: resistance in the lower half of discount wicks. (L41, L43, L19) [new]
- DRAFT: Premium/discount wick gradient is drawn open-to-extreme in either direction (direction of the fib is irrelevant); five levels: low/open, lower quadrant, CE, upper quadrant, high; the open of a down-close premium wick candle is the low of the range. (L14, L41, L40) [refines]
- DRAFT: Choosing between adjacent wicks: grade both, plot them, watch which one price respects; "not a hard and fast rule"; use all wicks at ATHs; PD-array overlap with one wick favours it. (L15) [new; judgment, our interpretation]
- DRAFT: Discount wick used in the first 30-60 minutes: when the open equals the prior close and a daily discount wick exists in a bearish case, grade it, price is sensitive to it early. (L20) [new]
- DRAFT: Wick traded into an opposing FVG is not an MSS: "a wick inside of a BISI ... two PD arrays that conflict, we don't want to look at that as a market structure shift." (L20) [new]
- DRAFT: Indecisive-candle FVG rule: ignore a middle candle that closed where it opened; use the low of the one candle to the high of the other as the gap. (L30, L28) [new]
- DRAFT: FVG by bodies: if only wicks overlap and the bodies leave no gap, there is no inefficiency; a small gap inside a balanced price range is not an FPFVG. (L49) [refines]
- DRAFT: FPFVG selection: choose the more pronounced displacement gap, not a one-tick crack; a gap that is not "breaking away" from the prior candles (balanced price range) is not valid; PM FPFVG must be prominent and include the volume imbalance. (L17, L49, L50, L44) [refines]
- DRAFT: FPFVG is the first one that formed, "not using 9:30" (09:31 anchor); Monday's FPFVG of the week is bordered, extended and reused every time until the last 30 minutes of Friday. (L15, L39) [refines]
- DRAFT: FPFVG reaction logic: bodies respect the CE; if price trades through and closes, the gap flips character (bearish FPFVG becomes bullish IFVG); a gap that is only tagged one candle after it forms has not been redelivered, so it stays a draw. (L13, L38) [refines]
- DRAFT: Session first-FVG workspaces: keep only the last 5-10 of each: PM first FVG, New York 09:30-10:00 FPFVG, Asian, London; "overkill" otherwise; Asian-session FPFVG and PM FPFVG used as next-day London entries. (L36) [new]
- DRAFT: IFVG validation after news: price must trade above/below the gap, return and refuse the lower half/CE, sometimes after one failed attempt ("You have to wait"); a 10:00 release (ISM) counts as a volatility injection to wait out. (L42, L30) [refines]
- DRAFT: Entry price discipline: frame premium/discount from the entry IFVG to the terminus (draw); the 50% line splits it; entering a long below it is a discount entry, not chasing. (L42) [new]
- DRAFT: "Gray pool" entry: CE of the discount wick of each of the last candles, extended forward; long entry at the low of the cluster, exit at the high of the daily VI. (L42) [new; entry-price rule is our interpretation]
- DRAFT: "Gauntlet" FVG: inside a breaker leg that sweeps a larger pool, the first (lowest, bullish) SIBI counted from the sweep low including its VI; enter/add on return after price closes above; reverse for bearish. (L40) [new]
- DRAFT: Silver Bullet restated: SIBI going into an inversion FVG; a candle low can equal the FVG upper quadrant; 09:50-10:10 macro delivery. (L40, L38) [refines]
- DRAFT: Venom model (full): SIBI down through a sell-side low, a few candles underneath absorbing sell stops, then one BISI displacement back above ("two fangs"); entry buy stop at the BISI high or limit at its open or less (power of 3); five-minute framing. (L39, L43) [refines]
- DRAFT: Venom stop is not settled: below the candle that pierces back above the low (L39) vs below the CE of the SIBI+BISI balanced price range, because price should not return there (L43). (L39, L43) [new conflict between lectures, see New conflicts]
- DRAFT: Low-hanging fruit: target the first relative equal highs/lows found looking left from the 09:30 open; stop 1 tick beyond; 15-second chart not enough reward for the risk; exit at the pool without demanding more. (L40, L49, L36) [refines]
- DRAFT: Pre-market pools: the 07:00-09:30 range's highs/lows (and London/Asia relatives) are the draws "you don't need anything else": no NWOG/NDOG required; 08:30 is a delivery time even with no news; 08:00 low as a daily-bias line. (L40, L44, L49, L41) [refines]
- DRAFT: Time gating: the break comes when the macro window opens ("Why didn't it start the sell-off from here? Because it wasn't time to"); fixed macros 09:50-10:10, 10:50-11:10, 13:50-14:10 (as captioned), 15:15-15:45; no "20/40 minutes after the hour" macros. (L44, L50, L38) [refines]
- DRAFT: PM opening range 13:30-14:00: first obvious displacement FVG, not "tiny cracks between two candles". (L44, L50, L38) [refines]
- DRAFT: London close window 10:00-13:00 ET ("the latest portion of the PM session I'd be concerned about"); London kill zone for forex 01:00-05:00; London open 03:00 in one NQ example; New York kill zone from 07:00. (L14, L20, L39, L19) [new]
- DRAFT: NFP week: new traders dial back, trade Mon/Tue and London/Asia Tue night; paper-trade Wed/Thu/Fri; no last-hour trading on Wed/Thu; ICT trades NFP Friday; NFP Thursday is the "decaffeinated" report and the real show is Friday; do not trade NFP Thursday/Friday unless seasoned. (L43, L42, L30) [refines]
- DRAFT: CPI/PPI climate: "Molotov cocktail ... should not be trying to trade aggressively"; if in a position and the number reaches the FVG, move to the sidelines; CPI can be a one-way railroad or two-stage; no confidence forecasting the number. Close a trade before Fed Chair speech. (L28, L36) [new]
- DRAFT: CPI-candle wick graded open-to-extreme; its upper quadrant overlapped the FPFVG. (L38) [new]
- DRAFT: -0.5 expansion of any defined range: a CIBI, a consolidation, an opening range, a NWOG: price moves outside by half its range or one full range; NWOG fib -0.5 nailed the day's high; CIBI -0.5 coincided with a premium wick CE. (L28, L44) [refines]
- DRAFT: Event horizon: halfway between two annotated PD arrays/pools of useful range is a target level ("every PD array"). (L30) [new; relates ladder partials]
- DRAFT: Re-risk: take part of realized profit, risk it, add at a fresh array; stop to CE of the entry gap; add at CE on retest; lock a small base (300-400) then let the rest run. (L36, L40, L45) [new; our interpretation]
- DRAFT: Order block = candle series: two consecutive closed candles = one OB, change in state of delivery at the open; propulsion block = bullish OB trading into a prior OB but not below the mean threshold (half) of its body. (L13, L17, L19, L30) [refines]
- DRAFT: Timeframe handling: when 1-minute chops, toggle up (1m, 5m, 15m, optionally 30m, 1h, 4h, daily); when a cluster forms look at every minute interval 1-12 for refinement; HTF FVG drawn from a higher time frame view on a lower chart. (L39, L19) [new]
- DRAFT: Continuous contract (NQ1!) for higher-time-frame charts, not the front month. (L33) [new]
- DRAFT: Gap risk: large gaps slow the frequency of setups; be selective and nimble; never chase a premium open on good news, always look for a discount. (L39) [refines]
- DRAFT: SMT: NQ lower low vs ES higher low in Asia Sunday night marked the weekly low; used as a qualifier after an extreme gap, not as a signal alone. (L49) [new]
- DRAFT: Run range for the challenge: two 30-handle AM runs and two 20-handle PM runs per week on a demo; low-hanging first pool of 20-30 handles. (L42, L44, L43) [new]
- DRAFT: Day-after expectations: after a large Thursday range keep expectations low for Friday. (L13) [new]
- DRAFT: Index lookbacks: NWOG/ORG/PDA freshness 20, 40, 60 days. (L43, L44) [repeats L46; not counted as new]
- DRAFT: Stop after the weekly objective is met: "I'm done for the week." (L42) [new]

### F3. Sep-Oct 2025: L04, 05, 06, 08, 11, 12, 16 (04, 06 = live streams; 04 = 20-day lookback grading)
- DRAFT: 20-day lookback grading is the first step of every analysis: count the last close as day 1, take the highest high and lowest low of 20 days, 50% line = equilibrium (premium above, discount below), grade quadrants; the useful PD arrays sit between the lower quadrant and the upper quadrant, ignore the extreme lower (bullish) area until a daily close breaches the lower quadrant. 40/60 days only in a runaway (parabolic) market. (L04) [refines]
- DRAFT: After a huge daily candle (e.g. Oct 10), that candle's high-low is the "band of volatility": grade and carry its quadrants, work PD arrays inside it (about 90% of setups between the lower quadrant and upper quadrant), no breakout trading, stand aside until its high or low is taken, then go back to the 20-day range. (L04) [new]
- DRAFT: Wick grading: premium wick measured from the close (body edge) up to the high, 25/50/75; only wicks on the path of the draw count (a premium wick above a market planning to go lower is ignored); a premium wick that price is above acts as a discount array. (L04, L06) [refines]
- DRAFT: Ignore a wick whose edge shares a value with another PDA and use the next, different one as the filter. (L05) [new]
- DRAFT: Bullish order flow after an MSS = down-close candles support price and bodies stay above the lower quadrant (wicks may pierce); bearish mirror; "treat that as your real support and resistance." (L04) [refines]
- DRAFT: Order block = the whole series of same-colour candles, graded high/UQ/mean threshold/LQ/low; bullish OB must hold from the mean threshold up (bearish: from the low up to MT); a close beyond MT sharply lowers the probability. (L04) [refines]
- DRAFT: Lower half of a bullish graded array (low to CE) must be clean (bodies and down-close candles support); in the upper half (CE to high) dirty action, stop hunts and retracements below short-term lows are permissible; after the run starts from CE no retracement to CE is expected. (L04) [new]
- DRAFT: A daily wick equals bodies on the 5-minute: allow lower-timeframe bodies below the quadrant; only a daily close/body beyond is a problem. (L04) [new]
- DRAFT: High-probability FVG test: some part of the FVG-forming candle/gap must lie on a quadrant of a graded range (wick, ORG, NDOG, NWOG); otherwise it is a "common gap, 50/50." Price comes from the quadrant, timing from the macro or window; both must agree. (L04, L06, L16) [new]
- DRAFT: 14:50-15:10 entry recipe: carry the quadrant FVG forward until the macro, look left for a lower sell-side low or equal highs, buy the raid with bodies respecting the lower quadrant/CE; last-hour trades are scalps ("cookie cutter shark"), first-30-minute trades take a partial to pay for the trade then let it run. (L04) [new]
- DRAFT: DXY is a risk barometer only: DXY up = risk off, down = risk on; DXY below a key low qualifies NQ longs. (L04) [refines]
- DRAFT: Hourly :50-:10 macros are used by ICT: 06:50 DXY run into the 07:00-10:00 window and 07:50-08:10 quadrant tag. (L04, L05) [new; conflicts with named-list reading, see MACRO-GRID]
- DRAFT: A setup forms every NY morning between 07:00 and 10:00 (7-10 window); "you can make your entire career just with this." (L05, L06, L04) [new]
- DRAFT: Suspension block: one candle with a volume imbalance at its high and one at its low acts like a FVG regardless of wicks to the left; zone = open to close (body) with CE between the bodies; strong; becomes an inversion/premium array when traded through; in the FVG family. (L11, L08, L04) [new]
- DRAFT: FPFVG not respected (no support, no resistance, no bodies inside) = "trouble waters"; with DXY/gold/NQ decoupling expect high resistance liquidity run conditions; sit through 10:00 news; skill = knowing when not to risk. (L11) [new]
- DRAFT: Inversion FVG fade at highs: last one or two bullish FVGs of the run; wait for price to break through, return into it, then short with a small stop; "about 80% of the time" it forms. (L12) [new]
- DRAFT: Unfinished business: a buy-side/sell-side pool raided by a wick only (no body beyond) must be revisited; model = sweep the other side, drop into a discount array (OB), then run the unfinished high; "an everyday model." (L06) [new]
- DRAFT: Bodies above the draw wick's CE/UQ while the trend is intact = explosive run; no bodies in the upper half at the quadrants = turtle soup back down. (L06) [new]
- DRAFT: Bullish markets leave FVGs open; do not buy the full closure of a bullish FVG; if it closes, wait for a lower-timeframe MSS and a new unfilled FVG. (L06) [refines]
- DRAFT: Failed-long handling: exit when price trades below the upper quadrant of the FVG with a stop at CE or one tick below; re-enter at half the original size once a lower-timeframe FVG holds. (L06) [new]
- DRAFT: Stop to break-even plus commission after about 40% of the way (example 40 of 100 handles, 10-handle risk); take partials at halfway of a run at ATH; adds on short-term retracements only in a confirmed strong bull. (L04, L06) [new]
- DRAFT: Gold uses the same rules; use the December contract (GC Z) and match CFD candles to the futures candle; CFD users build RTH levels from the 16:14 close and 09:30 open. (L06, L08) [refines]
- DRAFT: Chart opening prices: midnight, 09:30 RTH open, 18:00 reopen, 17:00 and 16:14; keep about 20 days of 09:30 opens. (L06) [new]
- DRAFT: Prior day's RTH ORG levels carry to the next day and are used inside its range. (L08, L04) [repeats L78]
- DRAFT: TGIF drawn at 20/30/40% of the week's range (retracement almost to 50% still called TGIF). (L08) [refines]
- DRAFT: Breakaway gap = a gap left inside a consolidation or at the CE of a higher-timeframe PD array; measuring gap about halfway of the move; IOFED here = partial fill of FVG short of CE. (L16, L05, L04) [refines]
- DRAFT: Forex session window is London open to noon; nothing after 12:00 except rate news; London close often forms the day's opposite extreme. (L16) [new]
- DRAFT: Avoid shorting all-time highs unless experienced; "don't think top"; inside day with a bias = continuation. (L11, L12) [repeats]
- DRAFT: Wick-CE-as-box convention and unicorn: a FVG on a wick quadrant in a macro is called a "unicorn" in L16; second-stage MM-model arrays "always lay on a quadrant" in L04. (L16, L04) [refines; see conflicts]
- DRAFT: Seasonal sketch: fall low, rally into late Jan/early Feb, April-May highs, summer into fall lows. (L06) [new, context only]

### F4. Oct-Nov 2025: L02, 03, 07, 09, 10 (02 = market maker model live stream)
- DRAFT: Anticipate, do not react: frame the idea in advance from rule-based, time-based delivery (he called the IFVG before it formed). (L02) [new]
- DRAFT: Smart money reversal (SMR, "turtle soup" = false breakout, not only a 20-day high/low) is the base of every market maker buy/sell model; model 2022 is the low-risk entry piece. Stages: SMR, low-risk entry, first-stage accumulation, retracement into an inefficiency = second-stage reaccumulation/redistribution, which he calls the "unicorn", then run to opposing liquidity. (L02, L03) [new]
- DRAFT: Low-risk entry after the SMR is the inversion FVG if one forms, else the very first FVG after the turn. (L02) [new]
- DRAFT: Buy program (or sell) starts when price trades back through the opening price of the candle that took the low (one tick above = long). All model PD arrays form inside that range. (L02) [new]
- DRAFT: Low-hanging fruit target = 70.5 (OTE sweet spot) of the dealing range, from the highest high before the drop to the SMR low, or 3/4 of the move; the full return to the original consolidation is only the best case. (L02) [refines]
- DRAFT: Purge and revert: after a low is taken the draw is the high three days back (mirror for highs); can be a complete daily-chart model. (L02) [new]
- DRAFT: "Working class hero" daily model: when the daily candle opens in close proximity to an old low, expect it to trade through that low; buy stop above the taken low, stop at/just under the low, target 70.5 or the first swing high; settlement vs non-settlement open to be tested. (L02) [new]
- DRAFT: A candle (daily or hourly) opening close to an old low/high is likely to reach and trade beyond it within that candle. (L02) [new]
- DRAFT: Raid test: you want price to trade through the old low to show raid vs continuation; sell stops rest below (long stops and breakout shorts). (L02) [new]
- DRAFT: Premise (it may go down to go up) vs narrative (it will take the sell side) vs bias (bullish once it did). (L02) [new]
- DRAFT: Second-stage reaccumulation/redistribution never gets a stop hunt; trail the stop under each new swing low after the candle closes; never roll a stop under an IFVG until structure breaks, trail with intermediate swing points. (L02, L09) [new]
- DRAFT: If a body closes beyond the CE of the PD array you are in, cut half the position and re-establish at the next PDA. (L02) [new]
- DRAFT: Wick selection: grade the lowest-reaching (lows) or highest-reaching (highs) wick among neighbours, not simply the longest; wick treated as a gap, measured close/open to extreme, reused after filled. (L02, L07, L09) [refines]
- DRAFT: When an FVG/suspension block forms on a wick, the wick to its left that shares the range takes precedence and is graded. (L02) [new]
- DRAFT: A new wick inside an array re-bases what is permissible; bodies must not close beyond the new wick's CE. (L02) [refines]
- DRAFT: IFVG validated by a candle close through the gap; also anticipated at structure: a low made with a lower low and an imbalance inside the leg has a "huge probability" of becoming an IFVG. (L02, L09, L03) [refines]
- DRAFT: Volume imbalance after sell-side delivery becomes SIBI/BISI ("paint roller"), balanced price range once both sides delivered; common gap = vacuum block; do not use liquidity voids, cut through candles. (L02) [refines]
- DRAFT: Relative equal lows/highs are validated when the later extreme is slightly inside the anchor's; right side higher than left (for highs) means less likely to be run. (L02, L07) [new]
- DRAFT: Dollar-led forex: frame everything on DXY; USD-second pairs buy while DXY drops, sell when its low is taken; USD-first pairs mirror DXY; SMT with USDJPY/USDCHF at the low is a reversal warning. (L02) [refines]
- DRAFT: Index SMT weights S&P > NQ > Dow; a Dow-only divergence is ignored; S&P failing a low in a bullish premise = loaded turtle soup long. (L02) [new]
- DRAFT: With no SMT, the weaker pair is the one with larger, more prominent candles in the trade direction; short the first premium array in it. (L02) [new]
- DRAFT: For spotty daily charts (gaps) go up to the weekly; same VI logic. (L02) [new]
- DRAFT: No overnight holding; gap risk between 17:00 settlement and 18:00 reopen (and weekend). (L02, L07) [new]
- DRAFT: Opening ranges are exactly 30 minutes: London 01:30-02:00 ET; NY open kill zone 07:00-09:00 (10:00 forex) with its opening range 07:00-07:30; other kill zones use the 30 minutes before. Read what happened at 06:30. (L03) [new]
- DRAFT: Inside an opening range the first presented FVG must show displacement and a market structure shift after the raid (it lies across the swing low taken); tick-sized earlier gaps are not used. Same for 09:30-10:00. (L03, L09) [new]
- DRAFT: That bearish FPFVG after a buy-side raid is a bearish suspension block and "90% of the time" acts as an inversion FVG (stop at CE, upper half untouched), then runs to sell side. (L03) [new]
- DRAFT: Low resistance runs always need an opposing run first (bearish needs buy side taken). (L03) [new]
- DRAFT: Session trading is independent of daily/weekly bias; only time and price at the session open matter. (L03) [new]
- DRAFT: Weekly/daily VI frame: defend the upper half after trading above it = bullish; lose the low and defend the lower half = bearish; premium/discount sensitivity (how far price can trade into an array) measures strength. (L03) [refines]
- DRAFT: Premium wick CE can be used intraday before the day closes (open to day's high). (L03) [refines]
- DRAFT: Suspension block = candle with a VI at its high end and one at its low end; mark VI low to VI high, not the wicks; it need not itself be an inefficiency; price below it makes it a premium PDA. (L07, L09) [new]
- DRAFT: Breakaway/measuring gap: a gap between two quadrant levels of a graded array, in the direction of the narrative, should stay open; a breakout inefficiency that is traded back into is not bullish order flow. (L07) [new]
- DRAFT: Swing projection A-B-C with -2 standard deviations lands at a graded wick quadrant. (L09) [new]
- DRAFT: Every PDA has an inversion aspect (bearish breaker flips to a bullish inversion breaker, MT of the last down candle). (L07) [refines]
- DRAFT: Opening range gap quadrants: keep today's plus the last three RTH sessions' ORGs (four sets), skipping holidays. (L07, L10) [refines]
- DRAFT: Carry forward the ORG of a day whose BODY left above an old all-time/market high (wick-only pokes do not count); its open, quadrants and CE were respected for days. (L07) [new]
- DRAFT: At an ATH mark each up-close; anything above those closes is smart-money short staging in three stages; fade when bodies cannot close above the CE of the key array and the IFVG fails, especially into a macro (10:50-11:10 on Fri Oct 10). Beginners should not pick tops. (L07) [new]
- DRAFT: First presented FVG = the prominent displacement gap, not a few-tick common gap; first fully-delivered full gap closure with intermediate sell side untaken = bullish. (L09) [refines]
- DRAFT: NDOG = RTH-session-independent ETH gap: last print 16:59 (17:00 settlement) to the 18:00 reopen; RTH close for ORG is the 16:14 last 1-minute print. (L10) [refines]
- DRAFT: Pre-open read: stack several PD arrays on one side (RTH close ORG high, NDOG, minor buy side); ORG CE 70% by 10:00; scale off at the first array (NDOG low). Beginners: track last three ORGs plus NDOG plus equal highs. (L10) [refines]
- DRAFT: Thursday often prints the high of a rising week and Friday fades it (Thursday effect). (L07, L09) [refines]

## Part F conflicts (numbered on from Part C; scored in `scorecard/`, see digest_map.csv)
11. Which of several adjacent wicks to grade: lowest/highest-reaching (L02, L07, L12, L16) vs longest meeting a criterion (L09) vs the one on the path of the draw (L04, L06) vs judgment (L15, L05). New card WICK-SELECT.
12. IFVG anticipated from structure before the close (L03, L09) vs validated only by the close (L02 and card A/B). IFVG-CONFIRM D.
13. Suspension block definition (L07, L09, L11): compatible wordings; new array, not scored.
14. Holding overnight: never (L02, L07) vs weekend hold of a short with a limit (L53). OVERNIGHT-HOLD.
15. NY open kill zone 07:00-09:00 with its 07:00-07:30 opening range (L03, L54). PREMARKET-RANGE D.
16. PDA lookback: 20 days is enough, 40/60 only in a parabolic market (L04) vs 20/40/60 all used (L43, L44, L46, SMC 140). New card PDA-LOOKBACK.
17. IOFED: partial fill short of CE (L04, L05, L16, L54) vs OB+SIBI inside an IFVG drill (L46). Not scored: the depth question was decided by Mase on SMC 17 (1 tick past candle 1); these add four videos to the "short of CE" switch.
18. Unicorn = FVG on a wick quadrant during a macro (L16) vs second-stage MM redistribution (L02, L04). UNICORN C.
19. Order block = the whole same-colour series, open of the series (L04, L13, L19, L48, L54). OB-CANDLE A evidence; L04 also requires the OB to hold from its mean threshold (not scored).
20. At ATHs: no shorts at all until a complete collapse (L24, L18) vs intraday shorts when seasoned (L07, L11, L12, L20). ATH-RULE C.
21. How long FPFVGs are kept: the week (L39), last 5-10 per session (L36), up to 20+ days (L38, L44, L55, L56). FVG-CARRY C, D.
22. Venom stop: below the candle that pierces back above the low (L39) vs below the CE of the SIBI+BISI BPR (L43). New card VENOM-STOP (1-1 tie, for Mase).
23. Doji middle candle ignored when drawing an FVG (L30, L28). One-sided; not scored.
24. London close window 10:00-13:00 ET (L14, forex). Not scored; excluded (engine trades indices).
25. "The 90-minute window": 07:00-09:30 (L40) vs 08:00-09:30 (L51). PREMARKET-RANGE G.
26. Hourly :50-:10 macros (L47, L50, L54, L55, L04, L05) vs named macros only (L38, L44). MACRO-GRID.
27. ETH taps must be confirmed in RTH (L52). One source; not scored.
28. Unfilled limit a tick from target: L54 (precision) vs L60 (move the stop to the near-touch). Compatible; not scored.
29. After a one-way week, lean toward a squeeze into smooth highs (L56). One source; not scored.
30. FPFVG short taken before the 10:00 data (L52). OPEN-RANGE-TRADE B evidence.
31. Cover costs after 40% of the way (L04), near the target (L63), or on a structural trigger (L52). STOP-MGMT I, J, K.
32. Stop one tick beyond the previous candle's wick (L63). STOP-PLACE I.
33. Session bias independent of daily/weekly bias (L03). BIAS-SOURCE E.
34. Add on every short-term retracement in a confirmed strong trend (L06). PYRAMID-WHERE D.
35. After a large range day keep expectations low next day (L13). AFTER-BIG-DAY C.
36. A 10:00 release is waited out like 08:30 (L42). NEWS-WAIT H.
37. RTH ORGs: today plus the last three sessions (L07, L10). GAP-LIFE E.
38. Practice targets 30 handles AM / 20 PM (L42, L43, L44). MIN-ROOM D.
39. NY lunch = 11:30-13:30 as one window (L54). LUNCH-WINDOW C evidence.

## Part F switches (DRAFT names, default OFF)
`wick_select(reach|longest|path|judgment)`, `ifvg_anticipate_from_structure`, `suspension_block_array`, `pda_lookback(20|20_40_60)`, `band_of_volatility_big_day`, `fvg_on_quadrant_only`, `unfinished_business_wick_raid`, `purge_and_revert_3day`, `working_class_hero_daily`, `cut_half_on_body_past_ce`, `stop_be_at_40pct`, `stop_be_near_target`, `stop_one_tick_prior_wick`, `venom_stop(pierce_candle|bpr_ce)`, `fpfvg_week_carry_monday`, `session_fpfvg_workspaces(5..10)`, `ath_buy_only_until_collapse`, `smr_three_stage_short_at_ath`, `org_keep_last3_plus_today`, `org_carry_body_above_ath`, `gray_pool_wick_ce_cluster`, `gauntlet_fvg`, `doji_ignored_in_fvg`, `wick_overlapped_fvg_90pct_revisit`, `post_holiday_buffer_day`, `rth_confirms_eth`, `weekly_objective_stop`, `news_1000_wait`, `macro_grid_hourly`, `or_sd_targets(1,1.5,2.5)`.

## Part F questions for Mase (ties only; everything else follows the count rule)
See the PR: MONDAY, PYRAMID-WHERE, FIXED-RR, OVERNIGHT-HOLD, CONTRACT and VENOM-STOP are tied after this append.
